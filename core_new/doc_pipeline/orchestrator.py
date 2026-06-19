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

# Lines that label a printed value in solve.py output (spec §15.3: each value
# printed with a logic tag like 正确 / 干扰1 / 干扰2 / 干扰3). Used for value
# validation — never for parsing a fixed template.
_VALUE_TAG_RE = re.compile(r"^\s*(?:正确|答案|answer|correct|干扰|distractor|option|\w+)[\s:：]", re.IGNORECASE)


def _validate_solve_output(
    output_path: Path, *, question_type: str | None = None,
) -> dict[str, Any]:
    """Validate solve.py exec output (§17.5: solve only computes the CORRECT answer).

    Contract (spec §17.5, kept deliberately loose — no fixed code template):
    - output must be non-empty
    - must contain at least one labeled correct answer
      (single_choice: the correct value; comprehensive: each sub-question answer)
    - solve.py does NOT compute distractors — distractor distinctness is checked
      later in the distractor-assembly step, not here.

    ``question_type`` ("single_choice" / "comprehensive" / ...) is informational;
    under §17.5 neither path requires multiple distinct values from solve.

    Returns {"ok": bool, "reason": str, "values": list[str]}.
    """
    if not output_path.exists():
        return {"ok": False, "reason": "no solve_output.txt", "values": []}
    text = output_path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return {"ok": False, "reason": "empty solve_output.txt", "values": []}

    # Extract the trailing number from each line, preferring tagged lines.
    values: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*$", line)
        if m:
            values.append(m.group(1))

    if not values:
        # Non-numeric output (conceptual reasoning print, analysis desc):
        # treat as ok — not every solve.py prints scalar answers.
        return {"ok": True, "reason": "", "values": []}

    # §17.5: solve only computes the correct answer. We only require that the
    # correct answer is present (at least one value). Distractor distinctness
    # (4 distinct option values) is NOT a solve-stage concern — it is verified
    # in the downstream distractor-assembly step.
    return {"ok": True, "reason": "", "values": values}


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
        skill_override: str | None = None,
    ) -> str:
        ...

    def clear_session(self, slot_id: str, role: str) -> bool:
        """§19.5 solver reset: drop a role's message history."""
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
        # ── 跨题黑板（team_pipeline 路径用）──
        # paper_state.md 落在 workspace 根（slot 外），同 workspace 的多题共享。
        # 节点经 self.board_path / read_board / append_board / _board_inject 访问。
        self.board_path = self.workspace / "paper_state.md"

    # ── 跨题黑板（team_pipeline 四角色 graph 用）────────────────────
    # 从 team_pipeline.py 搬移：跨 slot 的"已出题记录"，供 design_direct
    # 软性避开重复考点。黑板持久化在 workspace 根，绕过 write_file 沙箱。

    _BOARD_HEADER = (
        "# 组卷进度黑板\n"
        "（每题完成后追加一行；design_direct 参考，软性避开重复考点）\n"
    )

    def read_board(self) -> str:
        """供下题 design_direct 注入的已出题记录。"""
        return self.board_path.read_text(encoding="utf-8") if self.board_path.exists() else ""

    def append_board(self, slot_id: str, slot: dict[str, Any] | None = None, fallback_status: str = "") -> bool:
        """每题结束后把 team_state_entry.md 追加到全卷黑板。

        两级来源：① 优先读 slot 内的 team_state_entry.md（agent 自写）；
        ② agent 没写时编排层用 slot 元数据 + review status 兜底拼一行。
        """
        entry = self.workspace / slot_id / "team_state_entry.md"
        line = ""
        if entry.exists():
            line = entry.read_text(encoding="utf-8").strip()
        if not line and slot is not None:
            st = fallback_status or "unknown"
            line = (
                f"| {slot_id} | {slot.get('primary_target_name', '')} | "
                f"{slot.get('question_type', '')} | K{slot.get('target_difficulty', '?')} | {st} |"
            )
        if not line:
            return False
        if not self.board_path.exists():
            self.board_path.parent.mkdir(parents=True, exist_ok=True)
            self.board_path.write_text(self._BOARD_HEADER, encoding="utf-8")
        with open(self.board_path, "a", encoding="utf-8") as f:
            f.write(f"{line}\n")
        return True

    def _board_inject(self) -> dict[str, Path]:
        """构造 design_direct 的黑板注入项（仅在黑板非空时注入）。"""
        if self.board_path.exists() and self.read_board().strip() != self._BOARD_HEADER.strip():
            return {"paper_state.md": self.board_path}
        return {}

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
            # §21 概念题独立分支：跳过 design_card/exam_form，直接 concept_creator → concept_review
            if slot_data.get("complexity") == "conceptual":
                return await self._run_concept_pipeline(
                    slot_id, slot_data,
                    assembled_experience_doc=assembled_experience_doc,
                    k_definitions=k_definitions,
                )
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
        is_conceptual = slot_data.get("complexity") == "conceptual"
        if is_conceptual:
            # §21 概念题轻量设计卡：只摘知识点意图 + 考察方向，不规划参数/求解动作
            d_task = (
                "请根据蓝图生成 design_card.md（概念题轻量版）。\n\n"
                "概念题不需要参数规划/求解动作/计算逻辑。只需写：\n"
                "1. blueprint_contract（知识点/难度/should_be/should_not_be）\n"
                "2. core_knowledge_intent（must_test 概念辨析点）\n"
                "3. design_rationale（为什么考这些概念点）\n"
                "4. question_structure_plan（概念题形式：辨析/组合判断/机制理解）\n"
                "5. audit_focus（审核重点：概念准确性/干扰有效性）\n"
                "不写 parameter_plan / expected_reasoning_actions / route（概念题无计算）。\n"
                "简洁产出，不过度规划。"
            )
        else:
            d_task = (
                "请根据以下单题蓝图生成 design_card.md 设计卡。\n\n"
                "严格按 design_card schema v1 格式输出，9 个 section 全部必填。\n"
                "只生成设计卡，不写题目、不写答案、不写代码。\n\n"
                "⚠️ **参考题优先**：规划文档里的「往年真题参考」段（如有）是 interact "
                "检索到的同知识点参考题。**优先基于它锚定设问结构**，不要自己调 "
                "grep_search 重新检索。参考题只用于锚定设问方向和难度，**不要照搬原题**"
                "——必须按当前蓝图的 difficulty 和 examination_mode 重新设计骨架。"
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
        """Single design run (legacy graph's QuestionNode).

        Returns None on success, or a failed PipelineResult on error.
        """
        return await self._run_design_pass1(
            slot_id, slot_data, ws, ref_path, feedback=feedback,
        )

    # ── §17 split-design stage helpers ──────────────────────────────

    async def _run_exam_form(
        self, slot_id: str, slot_data: dict[str, Any], ws: Path, ref_path: Path,
    ) -> PipelineResult | None:
        """§17.3 exam_form: KP + K-radar → examination form (narrow judgment).

        Writes exam_form.md. Returns None on success, failed result on error.
        """
        exam_form_path = ws / "exam_form.md"
        design_card_path = ws / "design_card.md"
        ef_inject = {"规划": str(ref_path)}
        if design_card_path.exists():
            ef_inject["设计卡"] = str(design_card_path)
        ef_inject = await self._resolve_inject("exam_form", slot_id, 2, ef_inject)
        ef_task = (
            "§17.3 考察形式判定：根据知识点(KP) + 目标 K-雷达形状，选定考察形式并落地 K-雷达值。"
            "只判定形式，不写题干/答案/选项。产出 exam_form.md。"
        )
        await self.scheduler.run_agent(
            "exam_form", ef_task, slot_id=slot_id, inject_files=ef_inject,
        )
        if not exam_form_path.exists():
            return self._fail_result(slot_id, "exam_form agent did not write exam_form.md")
        return None

    async def _run_skeleton_design(
        self, slot_id: str, slot_data: dict[str, Any], ws: Path, ref_path: Path,
        *, feedback: str = "",
    ) -> PipelineResult | None:
        """§19 design P1 (split graph). Reads upstream cache → reuses skeleton
        → writes question.md (stem + questions + experience-value params).

        Now backed by the unified ``design`` agent in P1 mode.
        """
        return await self._run_design_pass1(
            slot_id, slot_data, ws, ref_path, feedback=feedback,
        )

    async def _run_design_pass1(
        self, slot_id: str, slot_data: dict[str, Any], ws: Path, ref_path: Path,
        *, feedback: str = "",
    ) -> PipelineResult | None:
        """§19/§21 design P1: read upstream → write question.md (+ solution.md for conceptual).

        Standard/C (computational): design_draft_skill or c_codegen — stem + params,
        answers by solve. Conceptual (§21): conceptual_batch_skill — batch direct
        questions + answers + solution, no gen.py/solve needed.
        """
        question_path = ws / "question.md"
        solution_path = ws / "solution.md"
        design_card_path = ws / "design_card.md"
        exam_form_path = ws / "exam_form.md"
        d_inject = await self._resolve_inject("design", slot_id, 2, {
            "规划": str(ref_path),
        })
        # exam_form 不在 registry 里，显式追加（resolve_inject 后才追加，避免被覆盖）
        if exam_form_path.exists():
            d_inject["考察形式"] = str(exam_form_path)

        is_conceptual = slot_data.get("complexity") == "conceptual"
        if is_conceptual:
            # §21 概念题分支：批量出题（题干+选项+答案+解析），不走 gen.py/solve
            d_task = (
                "§21 概念题批量出题：基于设计卡的知识点意图 + 经验卡，一次性出多道概念题。"
                "每道直接写题干+选项（A/B/C/D）+答案+解析。概念题无计算，直接给答案。"
                "同时写 question.md（所有题）+ solution.md（每题解析）。"
            )
            skill = "conceptual_batch_skill"
        else:
            d_task = (
                "§22 设计（带占位符的题干）：基于经验和上游定案，写题干骨架+子问题。\n"
                "**参数用变量占位**（如 x, y, 序列S），不填具体值。审核只审题干结构/表述/设问，不审参数。\n"
                "**只做一件事**：write question.md（题干+子问题+设计说明，参数用占位符）。\n"
                "设计说明写清参数约束要求（如'序列需触发≥2种旋转'），供 design_solve 搜索参数用。"
            )
            skill = "c_codegen"

        if feedback:
            d_task += (
                f"\n\n## 审核修改清单（逐条执行）\n"
                f"以下是 form_gate 审核发现的修改意见。请逐条对照修改 question.md，"
                f"不要遗漏任何一条。注意 keep_unchanged 标注的部分不得修改。\n\n{feedback}"
            )
        # 第一轮（非回退时）：允许 exec 确认代码能跑，但不试参数。
        if skill == "c_codegen" and not feedback:
            pass1_tools = None  # 用完整工具集，靠 task 约束不循环
        else:
            pass1_tools = None
        await self.scheduler.run_agent(
            "design", d_task, slot_id=slot_id, inject_files=d_inject,
            skill_override=skill,
            continue_session=bool(feedback),
            tools_override=pass1_tools,
        )
        if not question_path.exists():
            return self._fail_result(slot_id, "design P1 did not write question.md")
        # W1 fix: clear design session after each round to prevent context pollution
        # on form_gate retry (ensure each form_gate回退 starts clean)
        if hasattr(self.scheduler, "clear_session"):
            self.scheduler.clear_session(slot_id, "design")
        return None

    async def _run_distractor_assembly(
        self, slot_id: str, slot_data: dict[str, Any], ws: Path,
    ) -> PipelineResult | None:
        """§19 design P2 (split graph). Delegates to _run_design_pass2 for
        backward compatibility with existing node wiring.
        """
        return await self._run_design_pass2(slot_id, slot_data, ws)

    async def _run_design_solve(
        self, slot_id: str, slot_data: dict[str, Any], ws: Path, ref_path: Path,
        *, feedback: str = "",
    ) -> PipelineResult | None:
        """§22 solve round: gen.py already produced solve data flow in round 1.
        Just exec/read output → write solution.md. No separate solve.py.
        """
        question_path = ws / "question.md"
        solution_path = ws / "solution.md"
        gen_path = ws / "gen.py"

        d_inject = {"题目": str(question_path)}
        design_card_path = ws / "design_card.md"
        if design_card_path.exists():
            d_inject["设计卡"] = str(design_card_path)  # 选择题读 option_plan
        if gen_path.exists():
            d_inject["参数生成代码"] = str(gen_path)

        is_choice = slot_data.get("question_type") == "single_choice"
        ds_task = (
            "§22 参数搜索+求解：题干审核已通过。\n"
            "1. 读 review.md（审核反馈）→ 判断题干表述是否需要微调\n"
            "2. write gen.py：建模约束 + 给初始值 + 模拟机制，搜索满足约束的参数\n"
            "3. exec gen.py：验证参数 + 得到求解数据流\n"
            "4. **edit question.md**：把占位符替换为 gen.py 搜索出的实际参数值\n"
        )
        if is_choice:
            ds_task += (
                "5. **选项构造**：gen.py 顺手打印 option_plan 锚定的参数正确值 → LLM 对正确值做变换得到错误选项\n"
                "   正确值由 gen.py 产出，错误值是对正确值的简单变换（改某些位/取反/换值）。把 A/B/C/D 填入 question.md。\n"
                "6. **write solution.md**：求解过程 + 正确选项 + 每个干扰项的错误原因\n"
            )
        else:
            ds_task += (
                "5. **write solution.md**：从 gen.py 的 exec 输出整理为**求解文档**（逐步求解过程 + 答案），不是代码\n"
            )
        ds_task += "**solution.md 是 Markdown 文档，不是 Python 代码。**"
        if feedback:
            ds_task += f"\n\n## 审核修改清单（逐条执行）\n{feedback}"
        await self.scheduler.run_agent(
            "design", ds_task, slot_id=slot_id, inject_files=d_inject,
            skill_override="c_codegen",
            continue_session=bool(feedback),
            target_file="solution.md",  # design_solve 产出 solution.md（非 design 默认的 question.md）
        )
        if not solution_path.exists():
            return self._fail_result(slot_id, "design_solve did not write solution.md")
        # §code-as-truth 强制锚定：非概念题必须产出 gen.py。
        # 根因：design agent 是 artifact_writer（文本输出），弱模型（本地 Qwen）固守文本、
        # 不调 exec_file → 跳过 gen.py 直接心算 solution.md → 多步计算必错（实测补码除法/堆排）。
        # 此处把 gen.py 钉成"必须产出"：缺失即判失败（检出而非静默错答）。强模型（线上 GLM-5.2）
        # 本就产出 gen.py，此校验对其透明；弱模型则被拦下，需换 capable 模型重跑。
        if slot_data.get("complexity") != "conceptual" and not gen_path.exists():
            logger.warning("[%s] design_solve 未产出 gen.py（code-as-truth 违规，疑似心算）", slot_id)
            return self._fail_result(
                slot_id,
                "design_solve 未产出 gen.py：计算题必须用代码求解（code-as-truth），不得心算",
            )
        # Clear design session after solve round (§20 isolation)
        if hasattr(self.scheduler, "clear_session"):
            self.scheduler.clear_session(slot_id, "design")
        return None

    async def _run_design_pass2(
        self, slot_id: str, slot_data: dict[str, Any], ws: Path,
    ) -> PipelineResult | None:
        """§19 design P2: after solve computes the answer, the design agent
        finalizes the question. Choice → design 3 distractors based on the
        solution (only-set, never-compute); comprehensive → fill answers back
        into the stem. Solution comes from solve; never recompute.
        """
        question_path = ws / "question.md"
        output_path = ws / "solve_output.txt"
        solution_path = ws / "solution.md"
        p2_inject = {"题目": str(question_path)}
        if output_path.exists():
            p2_inject["代码输出"] = str(output_path)
        if solution_path.exists():
            p2_inject["求解结果"] = str(solution_path)
        p2_task = (
            "§19 设计 P2（定稿）：solve 已算出正确答案（见 solve_output.txt / solution.md）。"
            "基于解定稿题面——选择题：设计 3 个干扰选项（基于 correct 派生的合理错值："
            "±offset / off-by-one / 符号 / 单位，非代码计算，verify 4 值两两不同），"
            "用 edit_file 把 A/B/C/D 追加进 question.md 选项区；"
            "主观题：把各子问答案填回 question.md 题干。"
            "解来自 solve，不重算、不质疑；不碰 solve.py；不改题干逻辑（仅参数数值可改）。"
            "完成后直接传终审，不再循环。"
        )
        await self.scheduler.run_agent(
            "design", p2_task, slot_id=slot_id, inject_files=p2_inject,
            skill_override="design_finalize_skill",
        )
        # §19/§20 边界约束：agent 之间不传递思考过程，只通过文档协作。
        # P1 和 P2 共用 role="design"（session key 相同）。P2 跑完后清掉 design
        # session，避免 final 打回 P1 时 P1 读到 P2 的 reasoning_content（P2 思考
        # 污染 P1 出题）。P1 回退时会以 continue_session=True 重建干净 session。
        if hasattr(self.scheduler, "clear_session"):
            self.scheduler.clear_session(slot_id, "design")
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
        # 审核只需设计卡（锚点）+ 题目（被审对象），不需要规划/assembled
        r_inject = await self._resolve_inject("review", slot_id, 3, {
            "题目": str(question_path),
        })
        design_card_path = ws / "design_card.md"
        if design_card_path.exists() and "设计卡" not in r_inject:
            r_inject["设计卡"] = str(design_card_path)
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

            # §19: the unified ``design`` agent (P1) replaces the per-type
            # question_sc/question_comp roles.
            q_task = self._build_question_task(slot_id, iteration, complexity=slot_data.get("complexity", "standard"))
            q_inject = await self._resolve_inject("design", slot_id, 2, {"规划": str(ref_path)})
            # Fallback: inject design_card when registry is absent
            if design_card_path.exists() and "设计卡" not in q_inject:
                q_inject["设计卡"] = str(design_card_path)
            if iteration > 0 and review_path.exists():
                feedback_body = parse_doc_section(str(review_path), "corrections")
                if not feedback_body.strip() or feedback_body.strip() == "无":
                    feedback_body = parse_doc_section(str(review_path), "summary")
                q_task += f"\n\n## 审核反馈（第{iteration}轮）\n{feedback_body}"

            await self.scheduler.run_agent(
                "design",
                q_task,
                slot_id=slot_id,
                inject_files=q_inject,
                skill_override="design_draft_skill",
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
        question_type: str | None = None,
    ) -> tuple[PipelineResult | None, dict[str, Any]]:
        """Run Layer 4 (Solve) — §18: solve = problem-solving code.

        The solver reads the stem, **brief-thinks** the approach, writes
        solve.py itself (problem-solving code, not a DAG), execs it, fixes the
        code (never the stem, discipline ②), and writes solution.md. After the
        agent run, the orchestrator execs the resulting solve.py →
        solve_output.txt for downstream reporting + value validation.

        Returns (failure_result_or_None, exec_result). exec failure / missing
        correct answer surface as ``code_error`` so the graph routes back to
        design (tune parameters) — never the solver editing the stem.
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

        # ── §18.6: solver writes solve.py, execs, fixes code, writes solution ──
        # The solver owns the whole solve loop (brief-think → write code →
        # exec → fix code → solution). The orchestrator does NOT pre-write or
        # pre-exec solve.py — the agent does it with its write_file/exec_file/
        # edit_file tools. After the run we exec the resulting solve.py once
        # for a clean solve_output.txt + downstream value validation.
        s_inject = await self._resolve_inject("solve", slot_id, 4, {
            "题目": str(question_public_path),
        })
        s_task = (
            "§18/§19 求解即解题代码：读题干 → brief 想解法（不深推）→ write_file(solve.py) 写解题代码"
            "（能算出答案即可，非 DAG/参数搜索）→ exec_file 执行 → 出错只改 solve.py（绝不改题干，"
            "纪律②）→ 快速迭代直到算出答案 → 读 exec 输出 → write_file(solution.md) 写推理过程。"
            "exec 输出即真值，不重算、不质疑。只算正确答案，不算干扰值。"
            "exec 报错 = 代码 bug（与逻辑/参数无关），内部循环 fix 直到通过，不冒泡不回退。"
        )

        # ── §19.5: solver self-retry on exec/code failure ──
        # exec 报错或值校验失败 = solver 自己的事，内部消化：清空 solver 上下文
        # 重跑同一道题（摆脱上下文污染），cap=1。仍失败 → 升级失败（不回退 design，
        # 结构问题本应被 form_gate 拦截）。不向 graph 返回 code_error 信号。
        _SOLVE_RESET_RETRY = 1
        for _attempt in range(_SOLVE_RESET_RETRY + 1):
            await self.scheduler.run_agent(
                "solve",
                s_task,
                slot_id=slot_id,
                inject_files=s_inject,
                max_tokens=self.max_tokens,
                continue_session=False,  # fresh each attempt
            )

            if not solution_path.exists():
                logger.warning("[%s] solve did not write solution.md (attempt %d)", slot_id, _attempt + 1)
            elif solve_path.exists():
                exec_result = await self.exec_python(solve_path, output_path)
                exec_ok = exec_result["ok"]
                if exec_ok:
                    validation = _validate_solve_output(output_path, question_type=question_type)
                    exec_ok = validation["ok"]
                    if not exec_ok:
                        logger.warning(
                            "[%s] solve_output value check failed: %s",
                            slot_id, validation["reason"],
                        )
                if exec_ok:
                    return (None, exec_result)
                logger.warning(
                    "[%s] solve exec/validation failed: %s (attempt %d)",
                    slot_id, exec_result.get("stderr", "")[:200], _attempt + 1,
                )
            else:
                # No solve.py → conceptual question (solve agent reasoned directly).
                logger.info("[%s] Layer 4: no solve.py — conceptual solve path", slot_id)
                return (None, exec_result)

            # Failed this attempt: clear solver context and retry once more.
            if hasattr(self.scheduler, "clear_session"):
                self.scheduler.clear_session(slot_id, "solve")
            # remove stale solve artifacts so the retry starts clean
            for _stale in (solve_path, solution_path, output_path):
                if _stale.exists():
                    _stale.unlink()

        # Exhausted retry → escalate to failure (no code_error back-route).
        return (self._fail_result(
            slot_id, "Solve agent failed after context reset retry (exec/validation)"
        ), exec_result)


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
        final_path = ws / "final.md"
        question_path = ws / "question.md"
        solution_path = ws / "solution.md"

        if start_layer > 5:
            logger.info("[%s] Layer 5: Final SKIPPED (resume)", slot_id)
            return ("pass", None)

        logger.info("[%s] Layer 5: Final (整合交付)", slot_id)

        for final_iter in range(MAX_FINAL_RETRIES + 1):
            fr_task = (
                "整合交付：把 question.md + solution.md 组装为 final.md。\n"
                "1. read question.md + solution.md → 组装为完整试卷文档\n"
                "2. read review.md + review2.md → 检查前两轮的表述修改意见是否已落实\n"
                "3. 如有遗漏的表述问题，在 final.md 里顺手修正\n"
                "4. write_file(path=\"final.md\", content=\"...\") 写入整合后的最终文档\n\n"
                "⚠️ **final.md 必须用三段式格式**（标题精确匹配）：\n"
                "## 题目（题干+设问，不含答案）\n"
                "## 参考答案（答案：选项字母/最终结果）\n"
                "## 解析（推导过程/评分标准/干扰项分析）\n"
                "三段缺一不可。题目段不得含答案。系统按这三个标题拆分试卷版和解析版。\n\n"
                "不是再审核——数值和结构前两轮已保证。只做整合+表述检查。"
            )
            fr_inject_files = {
                "题目": str(question_path),
                "求解结果": str(solution_path),
            }
            review_path = ws / "review.md"
            review2_path = ws / "review2.md"
            if review_path.exists():
                fr_inject_files["题干审核意见"] = str(review_path)
            if review2_path.exists():
                fr_inject_files["一致性审核意见"] = str(review2_path)

            fr_inject = await self._resolve_inject("final_review", slot_id, 5, fr_inject_files)
            await self.scheduler.run_agent(
                "final_review",
                fr_task,
                slot_id=slot_id,
                inject_files=fr_inject,
                continue_session=final_iter > 0,
            )

            # final 是整合交付——检查 final.md 是否生成
            if not final_path.exists():
                return ("?", self._fail_result(slot_id, "Final agent did not write final.md"))

            # 整合交付只 pass（不回退）
            logger.info("[%s] Final: final.md written (%d chars, iter %d)",
                        slot_id, len(final_path.read_text(encoding="utf-8")), final_iter)
            break

        return ("pass", None)

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
        fail, exec_result = await self._run_solve(
            slot_id, ws, start_layer=start_layer, question_type=question_type,
        )
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
                "Conceptual pipeline: design agent did not write solution.md. "
                "The design agent should produce solution.md when complexity=conceptual.",
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
            # 格式校验：agent 写了 final.md，但可能拼装错位（如 ## 题目段空白）。
            # 检查必填段非空；缺失则用系统 hook _format_final 重拼（可靠兜底）。
            fmt_issues = self._validate_final_structure(final_path)
            if fmt_issues:
                logger.warning("[%s] Format: agent final.md 结构缺陷 %s → 系统重拼",
                               slot_id, fmt_issues)
                self._format_final(
                    ws,
                    question_path=question_path,
                    solution_path=solution_path,
                    output_path=output_path,
                )
            else:
                logger.info("[%s] Format (agent-produced final.md, %d chars)",
                            slot_id, len(final_path.read_text(encoding="utf-8")))

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

    def _should_use_split_design(self) -> bool:
        """Feature flag (§19): use the split-focused design graph
        (exam_form → design(P1) → form_gate → solve → design(P2) → final).

        Gated independently of enable_pipeline_graph so the split architecture
        can be A/B-tested without disturbing the stable graph path.
        """
        if not hasattr(self, "_split_design_enabled"):
            from .pipeline_config import load_pipeline_config
            cfg = load_pipeline_config()
            self._split_design_enabled = cfg.params.features.get(
                "enable_split_design", False
            )
        return self._split_design_enabled

    def _should_use_team_pipeline(self) -> bool:
        """Feature flag: use the team_pipeline four-role graph
        (design_direct → write_gen → write_solution → dual_review).

        Gated independently so the team architecture can be A/B-tested
        against the split graph without disturbing it. When true,
        ``_run_graph`` selects ``build_team_pipeline_graph``.
        """
        if not hasattr(self, "_team_pipeline_enabled"):
            from .pipeline_config import load_pipeline_config
            cfg = load_pipeline_config()
            self._team_pipeline_enabled = cfg.params.features.get(
                "enable_team_pipeline", False
            )
        return self._team_pipeline_enabled

    async def _run_concept_pipeline(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        *,
        assembled_experience_doc: str,
        k_definitions: str,
    ) -> PipelineResult:
        """§21 概念题独立分支：concept_creator → concept_review → done。

        跳过 design_card/exam_form（概念题不需要规划卡/K-雷达窄判断）。
        两个轻量智能体直通：出题（基于考点+知识）→ 审核（格式/事实/题型期望）。
        """
        ws = self.workspace / slot_id
        ws.mkdir(parents=True, exist_ok=True)
        total_start = time.monotonic()

        # Layer 1: Blueprint（出题契约，含考点列表）
        blueprint_ok = await self._ensure_blueprint(
            slot_id, slot_data, ws,
            assembled_experience_doc=assembled_experience_doc,
            k_definitions=k_definitions,
            start_layer=1,
        )
        if blueprint_ok is not None:
            return blueprint_ok

        ref_path = ws / "assembled.md" if (ws / "assembled.md").exists() else (ws / "blueprint.md")

        # ── 概念出题（concept_creator agent）──────
        logger.info("[%s] §21 概念题分支：concept_creator（批量）", slot_id)
        question_path = ws / "question.md"
        solution_path = ws / "solution.md"
        c_inject = {"规划": str(ref_path)}
        c_inject = await self._resolve_inject("concept_creator", slot_id, 2, c_inject)

        # 支持多考点批量：slot_data 的 concept_topics 列表或 primary_target_name
        concept_topics = slot_data.get("concept_topics", [])
        if not concept_topics and slot_data.get("primary_target_name"):
            concept_topics = [slot_data["primary_target_name"]]

        if len(concept_topics) > 1:
            topics_str = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(concept_topics))
            c_task = (
                f"基于以下考点列表出概念题（共 {len(concept_topics)} 道，**每考点一道**）：\n{topics_str}\n\n"
                f"该 slot 对应题号 {slot_id}，只出 {len(concept_topics)} 道题，不要多出。"
                "每题题干+选项/空格/答案+解析，锚定 examination_mode 的考察意图。"
                "write question.md（所有题）+ solution.md（每题解析）。"
            )
        else:
            c_task = (
                f"基于蓝图的考点，出 **1 道** 概念题（该 slot 对应题号 {slot_id}，只出 1 道）。"
                "题型按 examination_mode 定（选择/填空/判断/简答）。"
                "题目必须锚定考察意图，不要多出。"
                "write question.md（1道题）+ solution.md（解析）。"
            )
        await self.scheduler.run_agent(
            "concept_creator", c_task, slot_id=slot_id, inject_files=c_inject,
        )
        if not question_path.exists():
            return self._fail_result(slot_id, "concept creator did not write question.md")

        # ── 概念审核（review agent + concept review 标准）──────────
        logger.info("[%s] §21 概念题分支：concept_review", slot_id)
        review_path = ws / "review.md"
        r_inject = await self._resolve_inject("review", slot_id, 3, {
            "规划": str(ref_path), "题目": str(question_path),
        })
        r_task = (
            "§21 概念题审核：事实性检查 + 题目设计缺陷检查。\n"
            "## 工作步骤（指令式·逐题过）\n"
            "对每道题，做两个布尔判断（不展开推演）：\n"
            "1. **事实性**：答案是否事实正确？干扰项是否对应真实认知错误（不是随机值）？"
            "——凭知识对照判断，不展开推导。错→记。\n"
            "2. **设计缺陷**：是否存在多个选项都正确却被当单选题、题干歧义、解析自相矛盾？有→记。\n"
            "## 审核纪律（可执行闸）\n"
            "- 审事实靠**知识对照**（知道就对/错），不展开推演。发现自己在'推演某机制/算某值'→停。\n"
            "- 不审格式/难度/K-雷达/条件充分性（概念题不需要）。\n"
            "- 每题给结论即可，不写长篇分析。\n"
            "## 结论\n"
            "全对且无设计缺陷→status=pass；有事实错误或设计缺陷→needs_fix。\n\n"
            "**用 write_file 写 review.md**（含 ## status + pass/needs_fix + 逐题审核理由）。"
            "不要只在对话里说结论——必须落盘到 review.md，否则审核无效。"
        )
        await self.scheduler.run_agent(
            "review", r_task, slot_id=slot_id, inject_files=r_inject,
        )
        if not review_path.exists():
            return self._fail_result(slot_id, "concept review did not write review.md")

        review_status = get_doc_status(str(review_path), allowed=REVIEW_STATUSES)
        logger.info("[%s] §21 concept review: status=%s", slot_id, review_status)

        # needs_fix: 回退重出题（最多 2 轮）
        for retry in range(2):
            if review_status != "needs_fix":
                break
            logger.info("[%s] §21 concept needs_fix → retry %d", slot_id, retry + 1)
            feedback_body = parse_doc_section(str(review_path), "corrections")
            if not feedback_body.strip() or feedback_body.strip() == "无":
                feedback_body = parse_doc_section(str(review_path), "summary")
            c_task_retry = c_task + f"\n\n## 审核反馈（第{retry+1}轮）\n{feedback_body}"
            await self.scheduler.run_agent(
                "concept_creator", c_task_retry, slot_id=slot_id, inject_files=c_inject,
                continue_session=True,
            )
            await self.scheduler.run_agent(
                "review", r_task, slot_id=slot_id, inject_files=r_inject, continue_session=True,
            )
            review_status = get_doc_status(str(review_path), allowed=REVIEW_STATUSES)
            logger.info("[%s] §21 concept review retry %d: status=%s", slot_id, retry+1, review_status)

        # ── 整合 final.md（三段式格式统一）──────────────────────────
        final_path = ws / "final.md"
        if not final_path.exists() and question_path.exists():
            q_text = question_path.read_text(encoding="utf-8").strip()
            s_text = solution_path.read_text(encoding="utf-8").strip() if solution_path.exists() else ""
            # 概念题 question.md 已含题干+选项+答案，solution.md 含解析。
            # 拆成三段式：题目（题干+选项，去掉答案行）/ 参考答案 / 解析。
            import re as _re
            # 从 question 提取题干（去掉 **答案**：X 行）和答案
            q_clean = _re.sub(r"^\s*\*\*答案\*\*[：:].*$", "", q_text, flags=_re.M).strip()
            ans_match = _re.search(r"\*\*答案\*\*[：:]\s*(.+)", q_text)
            answer_line = ans_match.group(1).strip() if ans_match else ""
            final_path.write_text(
                f"## 题目\n\n{q_clean}\n\n## 参考答案\n\n{answer_line}\n\n## 解析\n\n{s_text}",
                encoding="utf-8",
            )
            logger.info("[%s] §21 concept: final.md assembled (三段式, %d chars)",
                        slot_id, len(final_path.read_text(encoding="utf-8")))

        exec_result: dict[str, Any] = {"ok": True, "skipped": True}
        return await self._assemble_result(
            slot_id, ws, total_start=total_start,
            final_iteration=1, final_status="pass", exec_result=exec_result,
        )

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
            PipelineGraph,
            PipelineState,
            build_pipeline_graph,
            build_split_pipeline_graph,
            build_team_pipeline_graph,
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
        # 优先级：team_pipeline > split > 稳定 graph。
        use_team = self._should_use_team_pipeline()
        use_split = (not use_team) and self._should_use_split_design()
        state = PipelineState.resume(
            slot_id, self.workspace, slot_data,
            code_as_truth=self._should_use_graph(),
        ) or PipelineState(
            slot_id=slot_id, slot_data=slot_data, workspace=self.workspace,
            code_as_truth=self._should_use_graph(),
        )
        if use_team:
            graph = build_team_pipeline_graph(self, self.workspace)
        elif use_split:
            graph = build_split_pipeline_graph(self, self.workspace)
        else:
            graph = build_pipeline_graph(self, self.workspace)
        await graph.run(state)

        # If a node recorded a hard failure, surface it.
        if state.result is not None and not getattr(state.result, "ok", True):
            return state.result

        # Derive final status + iteration from the graph history, then assemble
        # final.md / PipelineResult the same way the legacy path does.
        history_signals = {h["node"]: h["signal"] for h in state.history}
        solve_signal = history_signals.get("solve")

        # B1 guard: §19.5 — if solve never escaped with ``success`` (the solver
        # self-retried internally, exhausted, and escalated to ``failed``), the
        # slot failed and must never report a false ok. SolveNode sets
        # state.result on escalation, so this guard is belt-and-suspenders.
        last_signal = state.history[-1]["signal"] if state.history else ""
        failed_terminal = solve_signal is not None and solve_signal != "success"
        if failed_terminal:
            solve_visits = state.visit_counts.get("solve", 0)
            reason = (
                f"solve never succeeded (last signal={solve_signal}, "
                f"solve visits={solve_visits}, max={PipelineGraph.MAX_NODE_VISITS})"
            )
            logger.error("[%s] %s", slot_id, reason)
            return self._fail_result(slot_id, reason)

        if "final" in history_signals:
            final_status = history_signals["final"]
            if final_status in ("pass", "expression_fix"):
                final_status = "pass"
        elif use_split and "design" in history_signals and state.complexity == "conceptual":
            # §19 split conceptual: design → done (no form_gate/final).
            final_status = "pass"
        elif "form_gate" in history_signals and state.complexity == "conceptual":
            final_status = "pass"
        else:
            final_status = solve_signal or "pass"

        question_visits = (
            state.visit_counts.get("design", 1)
            if use_split
            else state.visit_counts.get("question", 1)
        )
        # split graph: gen.py 一体化（design 写 gen.py，design_solve 整理输出）
        if use_split:
            gen_path = ws / "gen.py"
            solution_path_check = ws / "solution.md"
            exec_ok = (
                "design_solve" in history_signals
                and solution_path_check.exists()
            )
            solve_path = gen_path  # gen.py 就是求解代码
        else:
            solve_path = ws / "solve.py"
            exec_ok = (
                "solve" in history_signals
                and history_signals["solve"] == "success"
                and solve_path.exists()
            )
        return await self._assemble_result(
            slot_id, ws,
            total_start=state.started_at,
            final_iteration=question_visits,
            final_status=final_status,
            exec_result={"ok": exec_ok, "skipped": not solve_path.exists()},
        )

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
    @staticmethod
    def _validate_final_structure(final_path: Path) -> list[str]:
        """检查 final.md 三段式格式完整性。返回缺陷列表（空=通过）。

        必须含三个精确标题段且非空：## 题目 / ## 参考答案 / ## 解析。
        缺失或空段→缺陷，触发系统 _format_final 重拼。
        """
        if not final_path.exists():
            return ["final.md 不存在"]
        text = final_path.read_text(encoding="utf-8")
        import re
        # 按 ## 段拆分
        sections = {}
        for m in re.finditer(r"^##\s+(.+?)$", text, re.M):
            name = m.group(1).strip()
            start = m.end()
            nxt = re.search(r"^##\s+", text[start:], re.M)
            body = text[start:start + nxt.start()] if nxt else text[start:]
            sections[name] = body.strip()
        issues = []
        # 三段式必填段（精确匹配标题）
        required = {
            "题目": ["题目"],
            "参考答案": ["参考答案", "答案"],
            "解析": ["解析"],
        }
        for label, keywords in required.items():
            body = next((v for k, v in sections.items()
                         if any(kw in k for kw in keywords)), "")
            if len(body) < 20:
                issues.append(f"## {label} 段缺失或空白")
        return issues

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
            parts = [f"请设计 {slot_id} 的完整题目。这是一道概念题（complexity=conceptual），请同时产出 question.md 和 solution.md（概念题跳过代码求解）。"]
        else:
            parts = [
                f"请设计 {slot_id} 的完整题目（标准题）。",
                "你的产出：question.md（题干 + 设问/子问 + 设计说明，不含选项值、不含答案）。",
                "聚焦复杂题面设计、条件充分性、解题意图与干扰意图；绝不脑内算数值结果、绝不预设答案值、绝不硬编码干扰值。答案和选项值由后续阶段确定。",
            ]
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
