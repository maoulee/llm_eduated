"""Document-pipeline orchestration.

The orchestrator owns the 4-layer workflow and system hooks.  It deliberately
does not know how to talk to an LLM provider; agent execution is delegated to a
scheduler-like object with a ``run_agent`` method.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Protocol

from core_new.markdown_parser import _extract_sections

from .config import (
    DEFAULT_MAX_TOKENS,
    MAX_ANALYSIS_ITERATIONS,
    PYTHON_EXEC_TIMEOUT,
)
from .contracts import PipelineResult
from .context import ContextRegistry
from .doc_parser import get_doc_status, parse_doc_section

logger = logging.getLogger(__name__)


class AgentScheduler(Protocol):
    """Minimal contract needed by doc-pipeline orchestration."""

    async def run_agent(
        self,
        role: str,
        task: str,
        *,
        slot_id: str,
        inject_files: dict[str, str] | None = None,
        continue_session: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        ...


class DocPipelineOrchestrator:
    """Four-layer document workflow: design, question/analysis, code, review."""

    def __init__(
        self,
        scheduler: AgentScheduler,
        workspace: str | Path = "workspace",
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_analysis_iterations: int = MAX_ANALYSIS_ITERATIONS,
        context_registry: ContextRegistry | None = None,
    ) -> None:
        self.scheduler = scheduler
        self.workspace = Path(workspace).resolve()
        self.max_tokens = max_tokens
        self.max_analysis_iterations = max_analysis_iterations
        self._registry = context_registry

    async def _resolve_inject(
        self,
        role: str,
        slot_id: str,
        phase: int,
        fallback: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Resolve context injection for a role via registry, or use fallback."""
        if self._registry is not None:
            return await self._registry.resolve_for_role(
                role, self.workspace, slot_id, phase,
                runtime_args=self._runtime_args,
            )
        return dict(fallback or {})

    async def run_pipeline(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        *,
        experience_card: str = "",
        k_definitions: str = "",
        assembled_experience_doc: str = "",
        start_layer: int = 1,
    ) -> PipelineResult:
        """Run the full document pipeline for one slot.

        When assembled_experience_doc is provided, skips Layer 1 (Design)
        and uses the assembled doc as the reference for the Question agent.
        Otherwise runs the full 4-layer pipeline with Design.

        start_layer: Resume from a specific layer (1-4). Earlier layers must
        have their output files already present in workspace.
        """
        ws = self.workspace / slot_id
        ws.mkdir(parents=True, exist_ok=True)
        total_start = time.monotonic()

        # Runtime args for inline providers (experience_doc, k_definitions)
        self._runtime_args: dict[str, Any] = {
            "experience_doc": assembled_experience_doc,
            "k_definitions": k_definitions,
        }

        # Layer 1: Design (skip if assembled doc is provided or resuming from layer 2+)
        blueprint_path = ws / "blueprint.md"
        if assembled_experience_doc:
            # Write the assembled doc as blueprint.md for downstream compatibility
            if start_layer > 1:
                logger.info(
                    "[%s] Layer 1: Design SKIPPED (resume from layer %d, refreshing assembled doc)",
                    slot_id,
                    start_layer,
                )
            else:
                logger.info("[%s] Layer 1: Design SKIPPED (using assembled experience doc)", slot_id)
            blueprint_path.write_text(assembled_experience_doc, encoding="utf-8")
        elif start_layer > 1:
            if not blueprint_path.exists():
                return self._fail_result(slot_id, f"Cannot resume from layer {start_layer}: blueprint.md not found")
            logger.info("[%s] Layer 1: Design SKIPPED (resume from layer %d)", slot_id, start_layer)
        else:
            logger.info("[%s] Layer 1: Design", slot_id)
            design_task = self._build_design_task(slot_data, k_definitions)
            await self.scheduler.run_agent("design", design_task, slot_id=slot_id)

            if not blueprint_path.exists():
                return self._fail_result(slot_id, "Design agent did not write blueprint.md")

        # Layer 2: Question <-> Analysis (skip if resuming from layer 3+)
        question_path = ws / "question.md"
        feedback_path = ws / "feedback.md"
        final_iteration = 0

        if start_layer > 2:
            if not question_path.exists():
                return self._fail_result(slot_id, f"Cannot resume from layer {start_layer}: question.md not found")
            logger.info("[%s] Layer 2: Question/Analysis SKIPPED (resume from layer %d)", slot_id, start_layer)
        else:
            logger.info("[%s] Layer 2: Question ↔ Analysis", slot_id)
            for iteration in range(self.max_analysis_iterations):
                final_iteration = iteration + 1

                q_task = self._build_question_task(
                    slot_id,
                    iteration,
                    experience_card=experience_card,
                )
                q_inject = await self._resolve_inject("question", slot_id, 2, {"蓝图": str(blueprint_path)})
                if iteration > 0 and feedback_path.exists():
                    feedback_body = parse_doc_section(str(feedback_path), "detailed_feedback")
                    q_task += f"\n\n## 审核反馈（第{iteration}轮）\n{feedback_body}"

                await self.scheduler.run_agent(
                    "question",
                    q_task,
                    slot_id=slot_id,
                    inject_files=q_inject,
                    continue_session=False,
                )

                if not question_path.exists():
                    return self._fail_result(slot_id, f"Question agent did not write question.md (iter {iteration})")

                a_task = "请审核以下题目，检查参数一致性和难度对标。"
                await self.scheduler.run_agent(
                    "analysis",
                    a_task,
                    slot_id=slot_id,
                    inject_files=await self._resolve_inject("analysis", slot_id, 2, {
                        "蓝图": str(blueprint_path),
                        "题目": str(question_path),
                    }),
                )

                if not feedback_path.exists():
                    return self._fail_result(slot_id, f"Analysis agent did not write feedback.md (iter {iteration})")

                status = get_doc_status(str(feedback_path))
                logger.info("[%s] Analysis iter %d: status=%s", slot_id, iteration, status)
                if status in ("pass", "pass_with_warnings"):
                    break
            else:
                logger.warning(
                    "[%s] Analysis max iterations reached (%d), proceeding anyway",
                    slot_id,
                    self.max_analysis_iterations,
                )

        # Layer 3: Coding (skip if resuming from layer 4+ or pure conceptual)
        needs_coding = parse_doc_section(str(question_path), "needs_coding")
        skip_coding = needs_coding.strip().lower() == "false"
        solve_path = ws / "solve.py"
        output_path = ws / "solve_output.txt"

        if start_layer > 3:
            logger.info("[%s] Layer 3: Coding SKIPPED (resume from layer %d)", slot_id, start_layer)
            if not skip_coding and not output_path.exists():
                return self._fail_result(
                    slot_id,
                    f"Cannot resume from layer {start_layer}: solve_output.txt not found",
                )
            exec_result = {
                "ok": output_path.exists() or skip_coding,
                "skipped": True,
                "reused_output": output_path.exists(),
            }
        elif skip_coding:
            logger.info("[%s] Layer 3: Coding SKIPPED (pure conceptual question)", slot_id)
            exec_result = {"ok": True, "skipped": True}
        else:
            logger.info("[%s] Layer 3: Coding", slot_id)
            solve_task = "请编写完整的 Python 求解代码。"
            await self.scheduler.run_agent(
                "coding",
                solve_task,
                slot_id=slot_id,
                inject_files=await self._resolve_inject("coding", slot_id, 3, {"题目": str(question_path)}),
                max_tokens=self.max_tokens,
            )

            if not solve_path.exists():
                return self._fail_result(slot_id, "Coding agent did not write solve.py")

            exec_result = await self.exec_python(solve_path, output_path)
            if not exec_result["ok"]:
                logger.warning("[%s] Code execution failed: %s", slot_id, exec_result.get("stderr", "")[:200])

        # Layer 4: Review -> Fix? -> Format
        logger.info("[%s] Layer 4: Review", slot_id)
        if skip_coding:
            review_task = "请全局审核题目。本题为纯概念题，无需代码验证，请从概念正确性、选项干扰质量、表述精确性角度审核。"
            review_fallback = {
                "蓝图": str(blueprint_path),
                "题目": str(question_path),
            }
        else:
            review_task = "请全局审核题目和求解结果。"
            review_fallback = {
                "蓝图": str(blueprint_path),
                "题目": str(question_path),
                "求解结果": str(output_path),
            }
        review_inject = await self._resolve_inject("review", slot_id, 4, review_fallback)
        await self.scheduler.run_agent(
            "review",
            review_task,
            slot_id=slot_id,
            inject_files=review_inject,
        )
        review_path = ws / "review.md"

        if not review_path.exists():
            return self._fail_result(slot_id, "Review agent did not write review.md")

        fixed_path: Path | None = None
        review_status = get_doc_status(str(review_path))
        if review_status == "needs_fix":
            logger.info("[%s] Review: needs_fix -> running fix agent", slot_id)
            fixed_path = ws / "fixed.md"
            fix_task = "请根据审核意见修复题目中的问题。优先使用 edit_file 做局部修改。"
            await self.scheduler.run_agent(
                "fix",
                fix_task,
                slot_id=slot_id,
                inject_files=await self._resolve_inject("fix", slot_id, 4, {
                    "题目": str(question_path),
                    "求解结果": str(output_path),
                    "审核意见": str(review_path),
                }),
                pre_copy_source=str(question_path),
            )
            if not fixed_path.exists():
                return self._fail_result(slot_id, "Fix agent did not write fixed.md")

        logger.info("[%s] Layer 4: Format (system hook)", slot_id)
        self._format_final(
            ws,
            question_path=question_path,
            output_path=output_path,
            review_path=review_path,
            fixed_path=fixed_path if fixed_path and fixed_path.exists() else None,
        )

        final_path = ws / "final.md"
        total_time = time.monotonic() - total_start

        final_content = ""
        if final_path.exists():
            final_content = final_path.read_text(encoding="utf-8")

        result = PipelineResult(
            slot_id=slot_id,
            ok=final_path.exists(),
            pipeline_type="doc_4layer",
            total_time_s=round(total_time, 1),
            analysis_iterations=final_iteration,
            review_status=review_status,
            code_exec_ok=exec_result.get("ok", False) and not exec_result.get("skipped", False),
            code_skipped=skip_coding,
            files={
                "blueprint": str(blueprint_path),
                "question": str(question_path),
                "feedback": str(feedback_path),
                "solve": str(solve_path),
                "solve_output": str(output_path),
                "review": str(review_path),
                "fixed": str(fixed_path) if fixed_path and fixed_path.exists() else "",
                "final": str(final_path) if final_path.exists() else "",
            },
            final_content=final_content,
        )

        logger.info(
            "[%s] Pipeline done: %.1fs, review=%s, iters=%d",
            slot_id,
            total_time,
            result.review_status,
            final_iteration,
        )
        return result

    async def exec_python(self, script_path: str | Path, output_path: str | Path) -> dict[str, Any]:
        """Execute a Python script and redirect stdout to output_path."""
        script_path = Path(script_path)
        output_path = Path(output_path)

        if not script_path.exists():
            return {"ok": False, "error": f"Script not found: {script_path}"}

        try:
            proc = subprocess.run(
                ["python3", str(script_path)],
                capture_output=True,
                text=True,
                timeout=PYTHON_EXEC_TIMEOUT,
                encoding="utf-8",
                errors="replace",
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(stdout, encoding="utf-8")

            return {
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "exit_code": -1, "stdout": "", "stderr": "Timeout", "timed_out": True}
        except Exception as exc:
            return {"ok": False, "exit_code": -1, "stdout": "", "stderr": str(exc), "timed_out": False}

    @staticmethod
    def _format_final(
        ws: Path,
        *,
        question_path: Path,
        output_path: Path,
        review_path: Path | None = None,
        fixed_path: Path | None = None,
    ) -> None:
        """Assemble final.md from component files without another LLM call."""
        source_path = fixed_path or question_path
        question_text = source_path.read_text(encoding="utf-8") if source_path.exists() else ""
        sections = _extract_sections(question_text)

        stem = sections.get("题干", question_text)
        sub_questions = sections.get("子问题", "")
        options = sections.get("选项", "")
        answer = sections.get("答案", "")
        solve_output = output_path.read_text(encoding="utf-8") if output_path.exists() else "（纯概念题，无需代码验证）"

        review_summary = ""
        if review_path and review_path.exists():
            review_sections = _extract_sections(review_path.read_text(encoding="utf-8"))
            review_summary = review_sections.get("summary", "")

        design_notes = sections.get("设计说明", "")

        parts = [f"## 题目\n{stem.strip()}"]
        if sub_questions:
            parts.append(f"\n\n## 子问题\n{sub_questions.strip()}")
        if options:
            parts.append(f"\n\n## 选项\n{options.strip()}")

        parts.append(f"\n\n## 解题过程\n{solve_output.strip()}")
        parts.append(f"\n\n## 答案\n{answer.strip()}")

        if design_notes:
            parts.append(f"\n\n## 设计说明\n{design_notes.strip()}")
        if review_summary:
            parts.append(f"\n\n## 审核总结\n{review_summary.strip()}")

        (ws / "final.md").write_text("\n".join(parts), encoding="utf-8")

    @staticmethod
    def _build_design_task(slot_data: dict, k_definitions: str) -> str:
        parts = [
            "请根据以下 slot 数据设计出题蓝图。",
            f"\n## Slot 数据\n{json.dumps(slot_data, ensure_ascii=False, indent=2)}",
        ]
        if k_definitions:
            parts.append(f"\n## K值难度定义\n{k_definitions}")
        return "\n".join(parts)

    @staticmethod
    def _build_question_task(slot_id: str, iteration: int, *, experience_card: str = "") -> str:
        parts = [f"请设计 {slot_id} 的完整题目。"]
        if iteration > 0:
            parts.append(f"\n这是第 {iteration + 1} 次迭代，请根据审核反馈修正题目。")
        if experience_card:
            parts.append(f"\n## 经验卡（往届题目题干参考，仅供风格参考）\n{experience_card}")
        return "\n".join(parts)

    @staticmethod
    def _fail_result(slot_id: str, reason: str) -> PipelineResult:
        return PipelineResult(
            slot_id=slot_id,
            ok=False,
            error=reason,
        )
