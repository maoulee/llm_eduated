"""2-Agent pipeline orchestration.

Creator ↔ Reviewer collaborative loop with two checkpoints:
  Checkpoint 1: Question design review (pass/needs_fix)
  Checkpoint 2: Solution consistency review (pass/expression_fix/question_error/solution_error)

The creator agent handles design → verify → solve → final in one continuous session.
The reviewer agent handles both checkpoints, auto-detected from available files.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

from .config import DEFAULT_MAX_TOKENS, PYTHON_EXEC_TIMEOUT
from .contracts import PipelineResult
from .doc_parser import (
    FINAL_REVIEW_STATUSES,
    REVIEW_STATUSES,
    extract_h2_section,
    get_doc_status,
    parse_doc_section,
)

logger = logging.getLogger(__name__)

MAX_CP1_RETRIES = 2
MAX_CP2_RETRIES = 1


class DualAgentOrchestrator:
    """2-agent pipeline: creator (design+verify+solve) + reviewer (dual checkpoint)."""

    def __init__(
        self,
        scheduler,
        workspace: str | Path = "workspace",
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self.scheduler = scheduler
        self.workspace = Path(workspace).resolve()
        self.max_tokens = max_tokens

    async def run_pipeline(
        self,
        slot_id: str,
        assembled_doc: str = "",
        question_type: str = "comprehensive",
    ) -> PipelineResult:
        ws = self.workspace / slot_id
        ws.mkdir(parents=True, exist_ok=True)
        total_start = time.monotonic()

        # Write assembled doc as blueprint reference
        assembled_path = ws / "assembled.md"
        if assembled_doc:
            assembled_path.write_text(assembled_doc, encoding="utf-8")

        question_path = ws / "question.md"
        review_path = ws / "review.md"
        solution_path = ws / "solution.md"
        solve_path = ws / "solve.py"
        output_path = ws / "solve_output.txt"
        final_path = ws / "final.md"

        # ── Phase 1a: Creator designs question framework (placeholders) ──
        logger.info("[%s] Phase 1a: Creator Step 1a — Design question framework", slot_id)

        creator_task_1a = (
            f"请设计 {slot_id} 的题干框架。所有数值用占位符 ⟨P1⟩ ⟨P2⟩ ... 代替，"
            f"在 ## 参数槽位 中声明每个占位符的 role/type/seed_hint/checks。"
            f"不写答案，不写约束推导理由，不出现具体数值。\n"
            f"严格按照 Step 1a 工作：read_file(assembled.md) → write_file(question.md) → 停止。"
        )
        creator_inject = {"规划": str(assembled_path)} if assembled_path.exists() else {}

        question_text = await self.scheduler.run_agent(
            "creator", creator_task_1a,
            slot_id=slot_id,
            inject_files=creator_inject,
            target_file="question.md",
        )

        if not question_text or not question_path.exists():
            return self._fail(slot_id, "Creator did not write question.md in Step 1a")

        # ── CP1: Review framework quality (before parameter filling) ──
        final_review_status = ""
        cp1_iters = 0

        for cp1_iter in range(MAX_CP1_RETRIES + 1):
            cp1_iters = cp1_iter + 1
            logger.info("[%s] Reviewer CP1: question framework review (iter %d)", slot_id, cp1_iter)

            r_task = (
                "请审核以下题目的设计框架质量。\n"
                "当前处于**检查点 1**（仅有题目框架，数值为占位符）。\n"
                "按 checklist 检查：格式红线、408风格、知识覆盖、经验卡、选项/子问题结构、K难度。\n"
                "状态值使用 pass 或 needs_fix。"
            )
            r_inject = {"题目": str(question_path)}
            if assembled_path.exists():
                r_inject["规划"] = str(assembled_path)

            review_text = await self.scheduler.run_agent(
                "reviewer", r_task,
                slot_id=slot_id,
                inject_files=r_inject,
                continue_session=cp1_iter > 0,
                target_file="review.md",
            )

            if not review_text or not review_path.exists():
                return self._fail(slot_id, "Reviewer did not write review.md at CP1")

            cp1_status = get_doc_status(str(review_path), allowed=REVIEW_STATUSES)
            logger.info("[%s] CP1 iter %d: status=%s", slot_id, cp1_iter, cp1_status)

            if not cp1_status:
                return self._fail(slot_id, "Reviewer returned invalid CP1 status")
            if cp1_status == "pass":
                break
            if cp1_iter >= MAX_CP1_RETRIES:
                return self._fail(
                    slot_id,
                    f"CP1 still needs_fix after {MAX_CP1_RETRIES + 1} iterations",
                )

            # needs_fix: feed corrections back to creator (framework only, keep placeholders)
            feedback = parse_doc_section(str(review_path), "corrections")
            if not feedback.strip() or feedback.strip() == "无":
                feedback = parse_doc_section(str(review_path), "summary")

            creator_fix_task = (
                f"## 审核反馈（CP1 第{cp1_iter + 1}轮）\n{feedback}\n\n"
                "请根据审核反馈修正题目框架。保持占位符 ⟨Pn⟩ 格式不变，"
                "修正后重新 write_file(question.md)。"
            )
            fixed_question = await self.scheduler.run_agent(
                "creator", creator_fix_task,
                slot_id=slot_id,
                continue_session=True,
                target_file="question.md",
                preserve_existing=True,
            )
            if not fixed_question or not question_path.exists():
                return self._fail(slot_id, "Creator did not apply CP1 fixes to question.md")

        # ── Phase 1b: Creator fills parameters via code (after CP1 passes) ──
        has_placeholders = bool(re.search(r"⟨P\d+⟩", question_path.read_text(encoding="utf-8")))

        if has_placeholders:
            logger.info("[%s] Phase 1b: Creator Step 1b — Parameter design via code", slot_id)
            creator_task_1b = (
                "现在执行 Step 1b：短代码合约。\n"
                "1. read_file(question.md) 提取参数槽位\n"
                "2. write_file(param_design.py) — 只填 CANDIDATES 种子区，代码自动算派生和验证\n"
                "3. exec_file(param_design.py)\n"
                "4. write_file(question.md) — 用代码输出替换所有 ⟨Pn⟩ 占位符\n"
                "禁止在 Markdown 中解释为什么种子能通过验证。完成后停止。"
            )
            param_result = await self.scheduler.run_agent(
                "creator", creator_task_1b,
                slot_id=slot_id,
                continue_session=True,
                target_file="question.md",
                preserve_existing=True,
            )
            if not param_result or not question_path.exists():
                return self._fail(slot_id, "Creator did not fill parameters in Step 1b")
            # Verify no placeholders remain
            remaining = re.findall(r"⟨P\d+⟩", question_path.read_text(encoding="utf-8"))
            if remaining:
                logger.warning("[%s] Unreplaced placeholders remain: %s", slot_id, remaining)

        # ── Phase 2: Creator solve ────────────────────────────────
        logger.info("[%s] Phase 2: Creator Step 2 — Verify + Solve", slot_id)

        self._remove_files(solve_path, output_path)
        MAX_PHASE2_ATTEMPTS = 3
        for p2_attempt in range(MAX_PHASE2_ATTEMPTS):
            if p2_attempt == 0:
                phase2_task = (
                    "现在进入 Step 2（独立求解）。\n"
                    "严格按序执行：\n"
                    "1. read_file(question.md) 读取题干（跳过设计说明）\n"
                    "2. 数值题：write_file(solve.py) → exec_file(solve.py) → 用题面参数独立求解\n"
                    "3. 若计算结果不匹配题干/选项，先定位最小不一致，再 edit question.md 中的数值、单位或选项值\n"
                    "4. write_file(solution.md) 写求解过程\n"
                    "5. 数值题复跑 solve.py，对比 solution.md 答案\n"
                    "完成后停止，等待终审。\n"
                    "概念题跳过代码验证和不匹配处理，直接求解。\n\n"
                    "注意：你的最终目标文件是 solution.md，不是 question.md。"
                )
            else:
                phase2_task = (
                    "solution.md 尚未写入。请立即执行：\n"
                    "1. 如果已完成 solve.py 验证，直接 write_file(solution.md)\n"
                    "2. 如果未完成验证，先 write_file(solve.py) → exec_file → 再 write_file(solution.md)\n"
                    "你的最终目标是 write_file(solution.md)。"
                )

            solution_text = await self.scheduler.run_agent(
                "creator", phase2_task,
                slot_id=slot_id,
                continue_session=True,
                max_tokens=self.max_tokens,
                target_file="solution.md",
            )

            if solution_text and solution_path.exists():
                break
            logger.warning("[%s] Phase 2 attempt %d: solution.md not yet written", slot_id, p2_attempt + 1)

        if not solution_path.exists():
            return self._fail(slot_id, f"Creator did not write solution.md after {MAX_PHASE2_ATTEMPTS} attempts")

        # Execute solve.py if exists
        exec_result: dict[str, Any] = {"ok": False, "skipped": True}
        if solve_path.exists():
            exec_result = await self._exec_python(solve_path, output_path)
            if not exec_result["ok"]:
                logger.warning("[%s] solve.py execution failed: %s", slot_id, exec_result.get("stderr", "")[:200])

        # ── Phase 3: Reviewer CP2 + Creator final ──────────────────
        logger.info("[%s] Phase 3: Reviewer CP2 — solution consistency review", slot_id)
        expression_fix_feedback = ""

        for cp2_iter in range(MAX_CP2_RETRIES + 1):
            logger.info("[%s] Reviewer CP2 (iter %d)", slot_id, cp2_iter)

            r2_task = (
                "请终审题目和求解结果。\n"
                "当前处于**检查点 2**（有题目 + 求解结果 + 代码证据），审核交付一致性。\n"
                "状态值使用 pass / expression_fix / question_error / solution_error。"
            )
            r2_inject = {
                "题目": str(question_path),
                "求解结果": str(solution_path),
            }
            if output_path.exists():
                r2_inject["代码输出"] = str(output_path)
            if solve_path.exists():
                r2_inject["求解代码"] = str(solve_path)
            if assembled_path.exists():
                r2_inject["规划"] = str(assembled_path)

            review_text = await self.scheduler.run_agent(
                "reviewer", r2_task,
                slot_id=slot_id,
                inject_files=r2_inject,
                continue_session=cp2_iter > 0,
                target_file="review.md",
            )

            if not review_text or not review_path.exists():
                return self._fail(slot_id, "Reviewer did not write review.md at CP2")

            cp2_status = get_doc_status(str(review_path), allowed=FINAL_REVIEW_STATUSES)
            logger.info("[%s] CP2 iter %d: status=%s", slot_id, cp2_iter, cp2_status)

            if not cp2_status:
                return self._fail(slot_id, "Reviewer returned invalid CP2 status")

            final_review_status = cp2_status

            if cp2_status == "pass":
                break
            elif cp2_status == "expression_fix":
                feedback = parse_doc_section(str(review_path), "routing_feedback")
                if not feedback.strip():
                    feedback = parse_doc_section(str(review_path), "summary")
                if feedback.strip():
                    expression_fix_feedback = feedback
                break
            elif cp2_status == "question_error" and cp2_iter < MAX_CP2_RETRIES:
                feedback = parse_doc_section(str(review_path), "routing_feedback")
                logger.info("[%s] CP2 question_error → back to Creator Step 1", slot_id)
                fixed_question = await self.scheduler.run_agent(
                    "creator",
                    f"## 终审反馈（题目错误）\n{feedback}\n\n请修正题目，重新 write_file(question.md)。",
                    slot_id=slot_id,
                    continue_session=True,
                    max_tokens=self.max_tokens,
                    target_file="question.md",
                    preserve_existing=True,
                )
                if not fixed_question or not question_path.exists():
                    return self._fail(slot_id, "Creator did not fix question.md")

                # Re-enter CP1 for the redesigned question
                logger.info("[%s] Re-entering CP1 for redesigned question", slot_id)
                for cp1_r_iter in range(MAX_CP1_RETRIES + 1):
                    cp1_r_task = (
                        "请审核修正后的题目设计质量。\n"
                        "当前处于**检查点 1**（仅有题目），审核题干设计质量。\n"
                        "状态值使用 pass 或 needs_fix。"
                    )
                    cp1_r_inject = {"题目": str(question_path)}
                    if assembled_path.exists():
                        cp1_r_inject["规划"] = str(assembled_path)
                    cp1_review = await self.scheduler.run_agent(
                        "reviewer", cp1_r_task,
                        slot_id=slot_id,
                        inject_files=cp1_r_inject,
                        continue_session=True,
                        target_file="review.md",
                    )
                    if not cp1_review or not review_path.exists():
                        return self._fail(slot_id, "Reviewer did not write review.md during CP1 re-review")

                    cp1_r_status = get_doc_status(str(review_path), allowed=REVIEW_STATUSES)
                    logger.info("[%s] CP1 re-review iter %d: status=%s", slot_id, cp1_r_iter, cp1_r_status)
                    if not cp1_r_status:
                        return self._fail(slot_id, "Reviewer returned invalid CP1 re-review status")
                    if cp1_r_status == "pass":
                        break
                    if cp1_r_iter >= MAX_CP1_RETRIES:
                        return self._fail(
                            slot_id,
                            f"CP1 re-review still needs_fix after {MAX_CP1_RETRIES + 1} iterations",
                        )

                    cp1_feedback = parse_doc_section(str(review_path), "corrections")
                    if not cp1_feedback.strip() or cp1_feedback.strip() == "无":
                        cp1_feedback = parse_doc_section(str(review_path), "summary")
                    fixed_question = await self.scheduler.run_agent(
                        "creator",
                        f"## CP1 审核反馈（修正后第{cp1_r_iter + 1}轮）\n{cp1_feedback}\n请修正题目后继续。",
                        slot_id=slot_id,
                        continue_session=True,
                        target_file="question.md",
                        preserve_existing=True,
                    )
                    if not fixed_question or not question_path.exists():
                        return self._fail(slot_id, "Creator did not apply CP1 re-review fixes")

                # Re-verify + re-solve (full Step 2+3 cycle)
                self._remove_files(solution_path, solve_path, output_path)
                solved_again = await self.scheduler.run_agent(
                    "creator",
                    "题目已修正。请重新执行 Step 2（独立求解）：\n"
                    "1. write_file(solve.py) → exec_file(solve.py)\n"
                    "2. 如计算结果不匹配题干/选项，先定位最小不一致，再 edit question.md\n"
                    "3. write_file(solution.md)\n"
                    "4. 复跑 solve.py → exec_file(solve.py) → 对比答案",
                    slot_id=slot_id,
                    continue_session=True,
                    max_tokens=self.max_tokens,
                    target_file="solution.md",
                )
                if not solved_again or not solution_path.exists():
                    return self._fail(slot_id, "Creator did not re-write solution.md")
                if solve_path.exists():
                    exec_result = await self._exec_python(solve_path, output_path)

            elif cp2_status == "solution_error" and cp2_iter < MAX_CP2_RETRIES:
                feedback = parse_doc_section(str(review_path), "routing_feedback")
                logger.info("[%s] CP2 solution_error → back to Creator Step 3", slot_id)
                fixed_solution = await self.scheduler.run_agent(
                    "creator",
                    f"## 终审反馈（求解错误）\n{feedback}\n\n请修正求解过程（最小修改），重新 write solution.md。",
                    slot_id=slot_id,
                    continue_session=True,
                    max_tokens=self.max_tokens,
                    target_file="solution.md",
                    preserve_existing=True,
                )
                if not fixed_solution or not solution_path.exists():
                    return self._fail(slot_id, "Creator did not fix solution.md")
                if solve_path.exists():
                    exec_result = await self._exec_python(solve_path, output_path)
            else:
                # Max retries exceeded for question_error or solution_error
                return self._fail(
                    slot_id,
                    f"CP2 unresolved after {MAX_CP2_RETRIES + 1} iterations: {cp2_status}",
                )

        # ── Phase 4: Creator assembles final.md ────────────────────
        logger.info("[%s] Phase 4: Creator Step 4 — Assemble final.md", slot_id)

        phase4_task = "终审已通过。请执行 Step 4：组装最终交付文档 final.md。"
        if expression_fix_feedback:
            phase4_task += f"\n\n## 表述修正建议\n{expression_fix_feedback}\n请在 final.md 中落实上述修正。"
        final_text = await self.scheduler.run_agent(
            "creator",
            phase4_task,
            slot_id=slot_id,
            continue_session=True,
            target_file="final.md",
        )

        # Fallback if agent didn't write final.md
        if not final_text or not final_path.exists():
            logger.info("[%s] Creator did not write final.md — system hook fallback", slot_id)
            if expression_fix_feedback:
                logger.warning("[%s] expression_fix feedback lost in fallback (no final.md to apply to)", slot_id)
                return self._fail(slot_id, "Creator did not write final.md for expression_fix feedback")
            self._format_final(ws, question_path=question_path, solution_path=solution_path, output_path=output_path)

        total_time = time.monotonic() - total_start
        final_content = final_path.read_text(encoding="utf-8") if final_path.exists() else ""

        result = PipelineResult(
            slot_id=slot_id,
            ok=final_path.exists(),
            pipeline_type="dual_agent",
            total_time_s=round(total_time, 1),
            analysis_iterations=cp1_iters,
            review_status=final_review_status,
            code_exec_ok=bool(solve_path.exists() and exec_result.get("ok") is True),
            code_skipped=not solve_path.exists(),
            files={
                "assembled": str(assembled_path),
                "question": str(question_path),
                "review": str(review_path),
                "solution": str(solution_path),
                "solve": str(solve_path),
                "verify": str(ws / "verify.py"),
                "solve_output": str(output_path),
                "final": str(final_path) if final_path.exists() else "",
            },
            final_content=final_content,
        )

        logger.info(
            "[%s] Pipeline done: %.1fs, review=%s, cp1_iters=%d",
            slot_id, total_time, result.review_status, cp1_iters,
        )
        return result

    async def _exec_python(self, script_path: Path, output_path: Path) -> dict[str, Any]:
        import asyncio
        if not script_path.exists():
            return {"ok": False, "error": f"Script not found: {script_path}"}
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3", str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(script_path.parent),
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=PYTHON_EXEC_TIMEOUT,
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_text = stdout
            if stderr or proc.returncode != 0:
                output_text += (
                    "\n\n## execution_status\n"
                    f"exit_code: {proc.returncode}\n"
                    f"stderr:\n{stderr}"
                )
            output_path.write_text(output_text, encoding="utf-8")
            return {
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "timed_out": False,
            }
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {"ok": False, "exit_code": -1, "stdout": "", "stderr": "Timeout", "timed_out": True}
        except Exception as exc:
            return {"ok": False, "exit_code": -1, "stdout": "", "stderr": str(exc), "timed_out": False}

    @staticmethod
    def _format_final(ws: Path, *, question_path: Path, solution_path: Path, output_path: Path) -> None:
        from core_new.markdown_parser import _extract_sections

        question_text = question_path.read_text(encoding="utf-8") if question_path.exists() else ""
        q_sections = _extract_sections(question_text)

        stem = q_sections.get("题干") or q_sections.get("题目", "")
        sub_questions = q_sections.get("子问题", "")
        options = q_sections.get("选项", "")

        solution_text = solution_path.read_text(encoding="utf-8") if solution_path.exists() else ""
        process = extract_h2_section(solution_text, "求解过程") or solution_text
        answer = _extract_sections(solution_text).get("最终答案", "")

        code_output = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
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
    def _remove_files(*paths: Path) -> None:
        for path in paths:
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                logger.warning("Failed to remove stale artifact: %s", path)

    @staticmethod
    def _fail(slot_id: str, reason: str) -> PipelineResult:
        return PipelineResult(slot_id=slot_id, ok=False, error=reason)
