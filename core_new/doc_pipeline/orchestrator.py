"""Document-pipeline orchestration.

Unified 5-layer workflow:
  Layer 1: Outline   — Generate outline.md + assembled.md
  Layer 1.5: Design Card — Feature-flagged question design card
  Layer 2: Question  — Design question with internal parameter validation
  Layer 3: Review    — Question-only review (pass/needs_fix)
  Layer 4: Solve     — Independent solving (concept or numerical)
  Layer 5: Final Review — Review with conditional routing

The orchestrator owns the workflow and system hooks.  It deliberately
does not know how to talk to an LLM provider; agent execution is delegated to a
scheduler-like object with a ``run_agent`` method.
"""

from __future__ import annotations

import json
import logging
import re
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
from .doc_parser import (
    FINAL_REVIEW_STATUSES,
    REVIEW_STATUSES,
    extract_h2_section,
    get_doc_status,
    parse_doc_section,
)

logger = logging.getLogger(__name__)

MAX_REVIEW_RETRIES = 2
MAX_FINAL_RETRIES = 1

# Q41-Q47 are comprehensive questions; Q1-Q40 are single choice.
_COMP_SLOTS = {f"Q{i}" for i in range(41, 48)}


def _question_role(
    slot_id: str,
    *,
    question_type: str | None = None,
    slot_data: dict[str, Any] | None = None,
    assembled_doc: str = "",
) -> str:
    """Return the question agent role name based on slot type.

    Resolution order:
    1. Explicit question_type parameter ("single_choice" / "comprehensive")
    2. slot_data metadata (question_type / section field)
    3. slot_id pattern (Q41-Q47 → comp, rest → sc)
    """
    if question_type in ("single_choice", "sc", "选择题"):
        return "question_sc"
    if question_type in ("comprehensive", "comp", "综合应用题", "综合题"):
        return "question_comp"

    # Infer from slot_data metadata
    if slot_data:
        qt = slot_data.get("question_type", "")
        if qt in ("single_choice", "选择题"):
            return "question_sc"
        if qt in ("comprehensive", "综合应用题", "综合题"):
            return "question_comp"
        section = slot_data.get("section", "")
        if "综合" in section or "应用" in section:
            return "question_comp"

    # Infer from assembled doc header
    if assembled_doc and "综合应用题" in assembled_doc[:500]:
        return "question_comp"

    # Fallback: slot_id pattern
    return "question_comp" if slot_id in _COMP_SLOTS else "question_sc"


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
    """Unified 5-layer document workflow."""

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

    # ── Public entry point ────────────────────────────────────────

    async def run_pipeline(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        *,
        experience_card: str = "",
        k_definitions: str = "",
        assembled_experience_doc: str = "",
        start_layer: int = 1,
        question_type: str | None = None,
    ) -> PipelineResult:
        """Run the unified 5-layer pipeline for one slot.

        When assembled_experience_doc is provided, skips Layer 1 (Outline)
        and uses the assembled doc as input for Question agent.
        start_layer: Resume from a specific layer (1-5).
        question_type: Override question type ("single_choice" / "comprehensive").
            If not set, inferred from slot_data metadata or slot_id pattern.
        """
        # ── Feature flag: declarative pipeline graph (signal + edges) ──
        # When enabled, routing is expressed declaratively in pipeline_graph.py.
        # Legacy _run_standard_pipeline / _run_conceptual_pipeline stay as fallback.
        if self._should_use_graph():
            self._runtime_args = {
                "experience_doc": assembled_experience_doc,
                "k_definitions": k_definitions,
            }
            return await self._run_graph(
                slot_id, slot_data,
                assembled_experience_doc=assembled_experience_doc,
                k_definitions=k_definitions,
            )

        ws = self.workspace / slot_id
        ws.mkdir(parents=True, exist_ok=True)
        total_start = time.monotonic()

        self._runtime_args: dict[str, Any] = {
            "experience_doc": assembled_experience_doc,
            "k_definitions": k_definitions,
        }

        # ── Layer 1: Outline / Blueprint ──────────────────────────
        blueprint_ok = await self._ensure_blueprint(
            slot_id, slot_data, ws,
            assembled_experience_doc=assembled_experience_doc,
            k_definitions=k_definitions,
            start_layer=start_layer,
        )
        if blueprint_ok is not None:
            return blueprint_ok  # early failure

        # Reference paths for downstream agents
        outline_path = ws / "outline.md"
        assembled_path = ws / "assembled.md"
        ref_path = assembled_path if assembled_path.exists() else (
            outline_path if outline_path.exists() else ws / "blueprint.md"
        )

        # ── Route by complexity ────────────────────────────────────
        complexity = slot_data.get("complexity", "standard")
        if complexity == "conceptual":
            result = await self._run_conceptual_pipeline(
                slot_id, slot_data, ws, ref_path,
                total_start=total_start,
                question_type=question_type,
                assembled_experience_doc=assembled_experience_doc,
                start_layer=start_layer,
            )
        else:
            result = await self._run_standard_pipeline(
                slot_id, slot_data, ws, ref_path,
                total_start=total_start,
                question_type=question_type,
                assembled_experience_doc=assembled_experience_doc,
                start_layer=start_layer,
                k_definitions=k_definitions,
            )
        return result

    # ── Layer 1: Blueprint ────────────────────────────────────────

    async def _ensure_blueprint(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        ws: Path,
        *,
        assembled_experience_doc: str,
        k_definitions: str,
        start_layer: int,
    ) -> PipelineResult | None:
        """Ensure blueprint/assembled docs exist for downstream layers.

        Returns None on success, or a failed PipelineResult on error.
        """
        outline_path = ws / "outline.md"
        assembled_path = ws / "assembled.md"

        if assembled_experience_doc:
            if start_layer <= 1:
                logger.info("[%s] Layer 1: Outline SKIPPED (using assembled experience doc)", slot_id)
            blueprint_sub = ws / "blueprint.md"
            blueprint_sub.write_text(assembled_experience_doc, encoding="utf-8")
            assembled_path.write_text(assembled_experience_doc, encoding="utf-8")
        elif start_layer > 1:
            blueprint_sub = ws / "blueprint.md"
            if not blueprint_sub.exists() and not assembled_path.exists():
                return self._fail_result(slot_id, f"Cannot resume from layer {start_layer}: no outline/assembled doc found")
            logger.info("[%s] Layer 1: Outline SKIPPED (resume from layer %d)", slot_id, start_layer)
        else:
            logger.info("[%s] Layer 1: Outline", slot_id)
            outline_task = self._build_outline_task(slot_data, k_definitions)
            await self.scheduler.run_agent("outline", outline_task, slot_id=slot_id)

            if not outline_path.exists():
                return self._fail_result(slot_id, "Outline agent did not write outline.md")

            blueprint_sub = ws / "blueprint.md"
            if assembled_path.exists():
                blueprint_sub.write_text(assembled_path.read_text(encoding="utf-8"), encoding="utf-8")
            elif outline_path.exists():
                blueprint_sub.write_text(outline_path.read_text(encoding="utf-8"), encoding="utf-8")

        return None  # success

    # ── Layer 1.5: Design Card ────────────────────────────────────

    async def _run_design_card(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        ws: Path,
        ref_path: Path,
        *,
        start_layer: int,
    ) -> None:
        """Run design-card layer (feature-flagged). Non-blocking on failure."""
        design_card_path = ws / "design_card.md"
        if not self._should_run_design_layer():
            return
        if start_layer > 1:
            logger.info("[%s] Layer 1.5: Design Card SKIPPED (resume from layer %d)", slot_id, start_layer)
            return

        logger.info("[%s] Layer 1.5: Design Card", slot_id)
        d_task = (
            "请根据以下单题蓝图生成 design_card.md 设计卡。\n\n"
            "严格按 design_card schema v1 格式输出，9 个 section 全部必填。\n"
            "只生成设计卡，不写题目、不写答案、不写代码。"
        )
        teacher_ann = slot_data.get("teacher_annotation", "")
        if teacher_ann:
            d_task += (
                f"\n\n---\n**教师批注（请务必参考）：**\n{teacher_ann}\n---"
            )
        d_inject = await self._resolve_inject(
            "question_design", slot_id, 1.5, {"规划": str(ref_path)},
        )
        await self.scheduler.run_agent(
            "question_design",
            d_task,
            slot_id=slot_id,
            inject_files=d_inject,
        )
        if not design_card_path.exists():
            logger.warning("[%s] Design card agent did not write design_card.md, continuing without it", slot_id)
            return

        # Validate design_card (warn-only, non-blocking)
        try:
            from .design_card_validator import validate_design_card_file
            result = validate_design_card_file(str(design_card_path))
            if not result.ok:
                logger.warning("[%s] Design card validation failed: %s", slot_id, result.errors)
            if result.warnings:
                logger.info("[%s] Design card warnings: %s", slot_id, result.warnings)
        except Exception as exc:
            logger.warning("[%s] Design card validator error: %s", slot_id, exc)

    # ── Layer 2-3: Question + Review loop ─────────────────────────

    async def _run_question_only(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        ws: Path,
        ref_path: Path,
        *,
        question_type: str | None,
        assembled_experience_doc: str,
        feedback: str = "",
    ) -> PipelineResult | None:
        """Single Question-agent run (graph's QuestionNode).

        Returns None on success, or a failed PipelineResult on error.
        """
        question_path = ws / "question.md"
        design_card_path = ws / "design_card.md"
        q_role = _question_role(
            slot_id, question_type=question_type, slot_data=slot_data,
            assembled_doc=assembled_experience_doc,
        )
        q_task = self._build_question_task(
            slot_id, 0, complexity=slot_data.get("complexity", "standard")
        )
        if feedback:
            q_task += f"\n\n## 审核反馈\n{feedback}"
        q_inject = await self._resolve_inject(q_role, slot_id, 2, {"规划": str(ref_path)})
        if design_card_path.exists() and "设计卡" not in q_inject:
            q_inject["设计卡"] = str(design_card_path)
        await self.scheduler.run_agent(
            q_role, q_task, slot_id=slot_id, inject_files=q_inject,
            continue_session=bool(feedback),
        )
        if not question_path.exists():
            return self._fail_result(slot_id, "Question agent did not write question.md")
        return None

    async def _run_review_only(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        ws: Path,
        ref_path: Path,
    ) -> tuple[str, PipelineResult | None]:
        """Single Review-agent run (graph's FormGateNode).

        Returns (status, None) on success or (status, failed_result) on error.
        """
        question_path = ws / "question.md"
        review_path = ws / "review.md"
        logger.info("[%s] Layer 3: Review", slot_id)
        r_task = "请审核以下题目的设计质量（此阶段无答案，不评估答案正确性）。"
        r_inject = await self._resolve_inject("review", slot_id, 3, {
            "规划": str(ref_path),
            "题目": str(question_path),
        })
        await self.scheduler.run_agent("review", r_task, slot_id=slot_id, inject_files=r_inject)
        if not review_path.exists():
            return ("", self._fail_result(slot_id, "Review agent did not write review.md"))
        status = get_doc_status(str(review_path), allowed=REVIEW_STATUSES)
        if not status:
            return ("", self._fail_result(slot_id, "Review agent returned invalid or missing status"))
        return (status, None)

    async def _run_question_review_loop(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        ws: Path,
        ref_path: Path,
        *,
        question_type: str | None,
        assembled_experience_doc: str,
        start_layer: int,
        max_iterations: int = MAX_REVIEW_RETRIES,
    ) -> tuple[int, PipelineResult | None]:
        """Run Layer 2 (Question) + Layer 3 (Review) loop.

        Returns (iteration_count, None) on success,
        or (iteration_count, failed_result) on error.
        """
        question_path = ws / "question.md"
        review_path = ws / "review.md"
        design_card_path = ws / "design_card.md"
        final_iteration = 0

        if start_layer > 2:
            if not question_path.exists():
                return (0, self._fail_result(slot_id, f"Cannot resume from layer {start_layer}: question.md not found"))
            logger.info("[%s] Layer 2: Question SKIPPED (resume from layer %d)", slot_id, start_layer)
            return (0, None)

        for iteration in range(max_iterations + 1):
            final_iteration = iteration + 1

            q_role = _question_role(
                slot_id,
                question_type=question_type,
                slot_data=slot_data,
                assembled_doc=assembled_experience_doc,
            )
            q_task = self._build_question_task(slot_id, iteration, complexity=slot_data.get("complexity", "standard"))
            q_inject = await self._resolve_inject(q_role, slot_id, 2, {"规划": str(ref_path)})
            # Fallback: inject design_card when registry is absent
            if design_card_path.exists() and "设计卡" not in q_inject:
                q_inject["设计卡"] = str(design_card_path)
            if iteration > 0 and review_path.exists():
                feedback_body = parse_doc_section(str(review_path), "corrections")
                if not feedback_body.strip() or feedback_body.strip() == "无":
                    feedback_body = parse_doc_section(str(review_path), "summary")
                q_task += f"\n\n## 审核反馈（第{iteration}轮）\n{feedback_body}"

            await self.scheduler.run_agent(
                q_role,
                q_task,
                slot_id=slot_id,
                inject_files=q_inject,
                continue_session=iteration > 0,
            )

            if not question_path.exists():
                return (final_iteration, self._fail_result(slot_id, f"Question agent did not write question.md (iter {iteration})"))

            # ── Layer 3: Review (question-only) ────────────────
            logger.info("[%s] Layer 3: Review (iter %d)", slot_id, iteration)
            r_task = "请审核以下题目的设计质量（此阶段无答案，不评估答案正确性）。"
            r_inject = await self._resolve_inject("review", slot_id, 3, {
                "规划": str(ref_path),
                "题目": str(question_path),
            })
            await self.scheduler.run_agent(
                "review",
                r_task,
                slot_id=slot_id,
                inject_files=r_inject,
            )

            if not review_path.exists():
                return (final_iteration, self._fail_result(slot_id, "Review agent did not write review.md"))

            review_status = get_doc_status(str(review_path), allowed=REVIEW_STATUSES)
            logger.info("[%s] Review iter %d: status=%s", slot_id, iteration, review_status)
            if not review_status:
                return (final_iteration, self._fail_result(slot_id, "Review agent returned invalid or missing status"))
            if review_status == "pass":
                break
            if iteration >= max_iterations:
                logger.warning(
                    "[%s] Review still needs_fix after %d iterations — proceeding with current question",
                    slot_id, max_iterations + 1,
                )
                break
            # needs_fix: loop back to question

        return (final_iteration, None)

    # ── Layer 4: Solve ────────────────────────────────────────────

    async def _run_solve(
        self,
        slot_id: str,
        ws: Path,
        *,
        start_layer: int,
    ) -> tuple[PipelineResult | None, dict[str, Any]]:
        """Run Layer 4 (Solve) including code execution.

        Returns (failure_result_or_None, exec_result) where exec_result
        tracks code execution status for downstream reporting.
        """
        solution_path = ws / "solution.md"
        solve_path = ws / "solve.py"
        output_path = ws / "solve_output.txt"
        question_path = ws / "question.md"
        question_public_path = ws / "question_public.md"

        exec_result: dict[str, Any] = {"ok": True, "skipped": True}

        if start_layer > 4:
            logger.info("[%s] Layer 4: Solve SKIPPED (resume from layer %d)", slot_id, start_layer)
            if not solution_path.exists():
                return (self._fail_result(slot_id, "Cannot resume: solution.md not found"), exec_result)
            return (None, exec_result)

        logger.info("[%s] Layer 4: Solve", slot_id)
        question_public_path = self._write_public_question_view(question_path)
        s_task = "请独立求解以下题目。先判断是概念题还是数值题，选择对应的求解策略。"
        s_inject = await self._resolve_inject("solve", slot_id, 4, {
            "题目": str(question_public_path),
        })
        await self.scheduler.run_agent(
            "solve",
            s_task,
            slot_id=slot_id,
            inject_files=s_inject,
            max_tokens=self.max_tokens,
        )

        if not solution_path.exists():
            return (self._fail_result(slot_id, "Solve agent did not write solution.md"), exec_result)

        # Execute solve.py if it exists (numerical questions)
        if solve_path.exists():
            exec_result = await self.exec_python(solve_path, output_path)
            if not exec_result["ok"]:
                logger.warning("[%s] Code execution failed: %s", slot_id, exec_result.get("stderr", "")[:200])

        return (None, exec_result)

    # ── Layer 5: Final Review ─────────────────────────────────────

    async def _run_final_review_loop(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        ws: Path,
        ref_path: Path,
        *,
        question_type: str | None,
        assembled_experience_doc: str,
        start_layer: int,
    ) -> tuple[str, PipelineResult | None]:
        """Run Layer 5 (Final Review) with back-routing.

        Returns (final_status, None) on success,
        or (status, failed_result) on error.
        """
        final_review_path = ws / "final_review.md"
        question_path = ws / "question.md"
        solution_path = ws / "solution.md"
        solve_path = ws / "solve.py"
        output_path = ws / "solve_output.txt"
        design_card_path = ws / "design_card.md"

        if start_layer > 5:
            logger.info("[%s] Layer 5: Final Review SKIPPED (resume)", slot_id)
            return ("pass", None)

        logger.info("[%s] Layer 5: Final Review", slot_id)

        for final_iter in range(MAX_FINAL_RETRIES + 1):
            fr_task = "请终审题目和求解结果的整体质量，判定 pass/expression_fix/question_error/solution_error。通过时需写入 final_review.md 和 final.md（最终交付文档）两个文件。"
            fr_inject_files = {
                "规划": str(ref_path),
                "题目": str(question_path),
                "求解结果": str(solution_path),
            }
            if design_card_path.exists() and "设计卡" not in fr_inject_files:
                fr_inject_files["设计卡"] = str(design_card_path)
            if output_path.exists():
                fr_inject_files["代码输出"] = str(output_path)
            if solve_path.exists():
                fr_inject_files["求解代码"] = str(solve_path)

            fr_inject = await self._resolve_inject("final_review", slot_id, 5, fr_inject_files)
            await self.scheduler.run_agent(
                "final_review",
                fr_task,
                slot_id=slot_id,
                inject_files=fr_inject,
                continue_session=final_iter > 0,
            )

            if not final_review_path.exists():
                return ("?", self._fail_result(slot_id, "Final Review agent did not write final_review.md"))

            final_status = get_doc_status(str(final_review_path), allowed=FINAL_REVIEW_STATUSES)
            logger.info("[%s] Final Review: status=%s (iter %d)", slot_id, final_status, final_iter)
            if not final_status:
                return ("?", self._fail_result(slot_id, "Final Review agent returned invalid or missing status"))

            if final_status == "pass":
                break
            elif final_status == "expression_fix":
                break
            elif final_status == "question_error" and final_iter < MAX_FINAL_RETRIES:
                # Back to Question Agent
                logger.info("[%s] Final Review: question_error -> re-running Question Agent", slot_id)
                feedback = parse_doc_section(str(final_review_path), "routing_feedback")
                q_role = _question_role(
                    slot_id,
                    question_type=question_type,
                    slot_data=slot_data,
                    assembled_doc=assembled_experience_doc,
                )
                q_task = self._build_question_task(slot_id, final_iter + 1, complexity=slot_data.get("complexity", "standard"))
                q_task += f"\n\n## 终审反馈（题目错误）\n{feedback}"
                await self.scheduler.run_agent(
                    q_role,
                    q_task,
                    slot_id=slot_id,
                    inject_files=await self._resolve_inject(q_role, slot_id, 2, {"规划": str(ref_path)}),
                    continue_session=True,
                )
                if not question_path.exists():
                    return (final_status, self._fail_result(slot_id, "Question agent (retry) did not write question.md"))

                # Re-solve
                logger.info("[%s] Re-solving after question fix", slot_id)
                question_public_path = self._write_public_question_view(question_path)
                s_task = "请独立求解以下题目。先判断是概念题还是数值题，选择对应的求解策略。"
                await self.scheduler.run_agent(
                    "solve",
                    s_task,
                    slot_id=slot_id,
                    inject_files=await self._resolve_inject("solve", slot_id, 4, {"题目": str(question_public_path)}),
                    max_tokens=self.max_tokens,
                )
                if not solution_path.exists():
                    return (final_status, self._fail_result(slot_id, "Solve agent (retry) did not write solution.md"))
                if solve_path.exists():
                    await self.exec_python(solve_path, output_path)

            elif final_status == "solution_error" and final_iter < MAX_FINAL_RETRIES:
                # Back to Solve Agent (minimal fix)
                logger.info("[%s] Final Review: solution_error -> re-running Solve Agent", slot_id)
                feedback = parse_doc_section(str(final_review_path), "routing_feedback")
                s_task = "请修正求解过程中的错误（最小修改）。"
                s_task += f"\n\n## 终审反馈（求解错误）\n{feedback}"
                question_public_path = self._write_public_question_view(question_path)
                await self.scheduler.run_agent(
                    "solve",
                    s_task,
                    slot_id=slot_id,
                    inject_files=await self._resolve_inject("solve", slot_id, 4, {"题目": str(question_public_path)}),
                    max_tokens=self.max_tokens,
                    continue_session=True,
                )
                if not solution_path.exists():
                    return (final_status, self._fail_result(slot_id, "Solve agent (retry) did not write solution.md"))
                if solve_path.exists():
                    await self.exec_python(solve_path, output_path)
            else:
                return (final_status, self._fail_result(slot_id, f"Final Review unresolved status: {final_status}"))

        return (final_status, None)

    # ── Standard pipeline (all 5 layers) ──────────────────────────

    async def _run_standard_pipeline(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        ws: Path,
        ref_path: Path,
        *,
        total_start: float,
        question_type: str | None,
        assembled_experience_doc: str,
        start_layer: int,
        k_definitions: str,
    ) -> PipelineResult:
        """Run the full 5-layer pipeline for standard-complexity questions."""
        # ── Layer 1.5: Design Card ─────────────────────────────
        await self._run_design_card(slot_id, slot_data, ws, ref_path, start_layer=start_layer)

        # ── Layer 2-3: Question + Review loop ─────────────────
        final_iteration, fail = await self._run_question_review_loop(
            slot_id, slot_data, ws, ref_path,
            question_type=question_type,
            assembled_experience_doc=assembled_experience_doc,
            start_layer=start_layer,
        )
        if fail is not None:
            return fail

        # ── Layer 4: Solve ────────────────────────────────────
        fail, exec_result = await self._run_solve(slot_id, ws, start_layer=start_layer)
        if fail is not None:
            return fail

        # ── Layer 5: Final Review ─────────────────────────────
        final_status, fail = await self._run_final_review_loop(
            slot_id, slot_data, ws, ref_path,
            question_type=question_type,
            assembled_experience_doc=assembled_experience_doc,
            start_layer=start_layer,
        )
        if fail is not None:
            return fail

        # ── Format: Assemble final.md ─────────────────────────
        return await self._assemble_result(
            slot_id, ws, total_start=total_start,
            final_iteration=final_iteration,
            final_status=final_status,
            exec_result=exec_result,
        )

    # ── Conceptual pipeline (Layer 2-3 only, skip 4-5) ────────

    async def _run_conceptual_pipeline(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        ws: Path,
        ref_path: Path,
        *,
        total_start: float,
        question_type: str | None,
        assembled_experience_doc: str,
        start_layer: int,
    ) -> PipelineResult:
        """Lightweight pipeline for conceptual questions.

        Runs Layer 2-3 (one iteration only, no review retries).
        Skips Layer 4 (Solve) and Layer 5 (Final Review).
        The question agent writes solution.md directly for conceptual questions.
        """
        # ── Layer 1.5: Design Card (same as standard) ─────────
        await self._run_design_card(slot_id, slot_data, ws, ref_path, start_layer=start_layer)

        # ── Layer 2-3: Question + Review (single iteration) ──
        final_iteration, fail = await self._run_question_review_loop(
            slot_id, slot_data, ws, ref_path,
            question_type=question_type,
            assembled_experience_doc=assembled_experience_doc,
            start_layer=start_layer,
            max_iterations=0,  # one shot, no retries
        )
        if fail is not None:
            return fail

        # ── Skip Layer 4 (Solve) and Layer 5 (Final Review) ──
        # For conceptual questions, the question agent writes solution.md directly.
        solution_path = ws / "solution.md"
        if not solution_path.exists():
            logger.warning("[%s] Conceptual pipeline: question agent did not write solution.md", slot_id)
            return self._fail_result(
                slot_id,
                "Conceptual pipeline: question agent did not write solution.md. "
                "The question_sc agent should produce solution.md when complexity=conceptual.",
            )

        # ── Format: Assemble final.md ─────────────────────────
        # Conceptual questions skip solve, so no code execution result
        _conceptual_exec_result: dict[str, Any] = {"ok": True, "skipped": True}
        return await self._assemble_result(
            slot_id, ws, total_start=total_start,
            final_iteration=final_iteration,
            final_status="pass",  # conceptual skips final review
            exec_result=_conceptual_exec_result,
        )

    # ── Final assembly & result ───────────────────────────────────

    async def _assemble_result(
        self,
        slot_id: str,
        ws: Path,
        *,
        total_start: float,
        final_iteration: int,
        final_status: str,
        exec_result: dict[str, Any] | None = None,
    ) -> PipelineResult:
        """Assemble final.md and build the PipelineResult."""
        question_path = ws / "question.md"
        solution_path = ws / "solution.md"
        output_path = ws / "solve_output.txt"
        solve_path = ws / "solve.py"
        outline_path = ws / "outline.md"
        assembled_path = ws / "assembled.md"
        review_path = ws / "review.md"
        final_review_path = ws / "final_review.md"
        question_public_path = ws / "question_public.md"
        design_card_path = ws / "design_card.md"

        final_path = ws / "final.md"
        if not final_path.exists():
            logger.info("[%s] Format (system hook — agent did not write final.md)", slot_id)
            self._format_final(
                ws,
                question_path=question_path,
                solution_path=solution_path,
                output_path=output_path,
            )
        else:
            logger.info("[%s] Format (agent-produced final.md, %d chars)", slot_id, len(final_path.read_text(encoding="utf-8")))

        final_path = ws / "final.md"
        total_time = time.monotonic() - total_start

        final_content = ""
        if final_path.exists():
            final_content = final_path.read_text(encoding="utf-8")

        result = PipelineResult(
            slot_id=slot_id,
            ok=final_path.exists(),
            pipeline_type="doc_5layer",
            total_time_s=round(total_time, 1),
            analysis_iterations=final_iteration,
            review_status=final_status,
            code_exec_ok=(
                exec_result.get("ok", False) and not exec_result.get("skipped", True)
            ) if exec_result else False,
            code_skipped=not solve_path.exists(),
            files={
                "outline": str(outline_path),
                "assembled": str(assembled_path),
                "question": str(question_path),
                "question_public": str(question_public_path),
                "review": str(review_path),
                "solution": str(solution_path),
                "solve": str(solve_path),
                "solve_output": str(output_path),
                "final_review": str(final_review_path),
                "final": str(final_path) if final_path.exists() else "",
            },
            final_content=final_content,
        )

        logger.info(
            "[%s] Pipeline done: %.1fs, final_review=%s, iters=%d",
            slot_id,
            total_time,
            result.review_status,
            final_iteration,
        )
        return result

    # ── Utility / static methods ──────────────────────────────────

    def _should_run_design_layer(self) -> bool:
        """Check if question_design layer is enabled via pipeline features."""
        if not hasattr(self, "_design_layer_enabled"):
            from .pipeline_config import load_pipeline_config
            cfg = load_pipeline_config()
            self._design_layer_enabled = cfg.params.features.get("enable_question_design", False)
        return self._design_layer_enabled

    def _should_use_graph(self) -> bool:
        """Feature flag: use the declarative pipeline_graph for routing."""
        if not hasattr(self, "_use_graph_enabled"):
            from .pipeline_config import load_pipeline_config
            cfg = load_pipeline_config()
            self._use_graph_enabled = cfg.params.features.get("enable_pipeline_graph", False)
        return self._use_graph_enabled

    async def _run_graph(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        *,
        assembled_experience_doc: str,
        k_definitions: str,
    ) -> PipelineResult:
        """Run the slot through the declarative pipeline graph.

        Layer 1 (Blueprint) still runs here so downstream nodes can read the
        assembled/blueprint files. Routing from Layer 1.5 onward is the graph's
        job.
        """
        from .pipeline_graph import (
            PipelineState,
            build_pipeline_graph,
        )

        ws = self.workspace / slot_id
        ws.mkdir(parents=True, exist_ok=True)

        # ── Layer 1: Blueprint ───────────────────────────────────
        blueprint_ok = await self._ensure_blueprint(
            slot_id, slot_data, ws,
            assembled_experience_doc=assembled_experience_doc,
            k_definitions=k_definitions,
            start_layer=1,
        )
        if blueprint_ok is not None:
            return blueprint_ok

        # ── Graph: Layer 1.5 → done ──────────────────────────────
        state = PipelineState.resume(
            slot_id, self.workspace, slot_data,
            code_as_truth=self._should_use_graph(),
        ) or PipelineState(
            slot_id=slot_id, slot_data=slot_data, workspace=self.workspace,
            code_as_truth=self._should_use_graph(),
        )
        graph = build_pipeline_graph(self, self.workspace)
        await graph.run(state)
        return state.result or self._fail_result(slot_id, "graph produced no result")

    async def _resolve_inject(
        self,
        role: str,
        slot_id: str,
        phase: int,
        fallback: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Resolve context injection for a role via registry, or use fallback."""
        if self._registry is not None:
            resolved = await self._registry.resolve_for_role(
                role, self.workspace, slot_id, phase,
                runtime_args=self._runtime_args,
            )
            if resolved:
                return resolved
        return dict(fallback or {})

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
    def _write_public_question_view(question_path: Path) -> Path:
        """Write a solver-facing question view without design notes."""
        public_path = question_path.with_name("question_public.md")
        question_text = question_path.read_text(encoding="utf-8") if question_path.exists() else ""

        stem = extract_h2_section(question_text, "题干")
        options = extract_h2_section(question_text, "选项")
        sub_questions = extract_h2_section(question_text, "子问题")

        parts = ["## status\ndraft"]
        if stem:
            parts.append(f"\n\n## 题干\n{stem.strip()}")
        if options:
            parts.append(f"\n\n## 选项\n{options.strip()}")
        if sub_questions:
            parts.append(f"\n\n## 子问题\n{sub_questions.strip()}")

        if len(parts) == 1 and question_text.strip():
            # Malformed question fallback: drop explicit design sections by H2 boundary.
            public_text = re.sub(
                r"^##\s+设计说明\s*\n.*?(?=^##\s+|\Z)",
                "",
                question_text,
                flags=re.MULTILINE | re.DOTALL,
            ).strip()
            parts.append(f"\n\n## 题干\n{public_text}")

        public_path.write_text("\n".join(parts), encoding="utf-8")
        return public_path

    @staticmethod
    def _format_final(
        ws: Path,
        *,
        question_path: Path,
        solution_path: Path,
        output_path: Path,
    ) -> None:
        """Assemble final.md from component files without another LLM call."""
        question_text = question_path.read_text(encoding="utf-8") if question_path.exists() else ""
        q_sections = _extract_sections(question_text)

        stem = q_sections.get("题干") or q_sections.get("题目") or extract_h2_section(question_text, "题干") or extract_h2_section(question_text, "题目")
        sub_questions = q_sections.get("子问题", "")
        options = q_sections.get("选项", "")

        solution_text = solution_path.read_text(encoding="utf-8") if solution_path.exists() else ""
        s_sections = _extract_sections(solution_text)
        process = extract_h2_section(solution_text, "求解过程") or solution_text
        answer = s_sections.get("最终答案", "") or extract_h2_section(solution_text, "最终答案")

        code_output = ""
        if output_path.exists():
            code_output = output_path.read_text(encoding="utf-8")

        design_notes = q_sections.get("设计说明", "")

        parts = [f"## 题目\n{stem.strip()}"]
        if sub_questions:
            parts.append(f"\n\n## 子问题\n{sub_questions.strip()}")
        if options:
            parts.append(f"\n\n## 选项\n{options.strip()}")
        parts.append(f"\n\n## 求解过程\n{process.strip()}")
        if code_output:
            parts.append(f"\n\n## 代码验证输出\n{code_output.strip()}")
        if answer:
            parts.append(f"\n\n## 答案\n{answer.strip()}")
        if design_notes:
            parts.append(f"\n\n## 设计说明\n{design_notes.strip()}")

        (ws / "final.md").write_text("\n".join(parts), encoding="utf-8")

    @staticmethod
    def _build_outline_task(slot_data: dict, k_definitions: str) -> str:
        parts = [
            "请根据以下 slot 数据和历史经验，生成出题规划（outline.md + assembled.md）。",
            f"\n## Slot 数据\n{json.dumps(slot_data, ensure_ascii=False, indent=2)}",
        ]
        if k_definitions:
            parts.append(f"\n## K值难度定义\n{k_definitions}")
        return "\n".join(parts)

    @staticmethod
    def _build_question_task(
        slot_id: str,
        iteration: int,
        *,
        complexity: str = "standard",
    ) -> str:
        if complexity == "conceptual":
            parts = [f"请设计 {slot_id} 的完整题目。这是一道概念题（complexity=conceptual），请同时产出 question.md 和 solution.md。"]
        else:
            parts = [f"请设计 {slot_id} 的完整题目。注意：不写答案，答案由独立求解智能体产出。"]
        if iteration > 0:
            parts.append(f"\n这是第 {iteration + 1} 次迭代，请根据审核反馈修正题目。")
        return "\n".join(parts)

    @staticmethod
    def _fail_result(slot_id: str, reason: str) -> PipelineResult:
        return PipelineResult(
            slot_id=slot_id,
            ok=False,
            error=reason,
        )
