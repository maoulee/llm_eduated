"""Unified Question Pipeline — one workflow for both single-choice and comprehensive questions.

Architecture:
  Step 1: Design (SC: stem; Comp: stem + sub_questions + intent)
  Step 2: Options (SC only — 4 options with distractor strategies)
  Step 3: Solve (FileCodeSolver — pure computation engine)
    SC: verify each option A/B/C/D via Python code
    Comp: compute each sub-question via Python code
  Step 4: Format (SC: explanation + steps; Comp: structured answers)
  Step 5: Rubric (Comp only)
  Step 6: Review (compare computation vs intent, route fixes)

  Revision loop: route fix to appropriate step (max 1 round by default).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core_new.agent_base import AgentConfig, BaseAgent
from core_new.agent_roles import AuditMode, RoleType, source_policy_for_audit_mode
from core_new.audit_protocol import AuditResultNormalizer, FixRouter
from core_new.agents.file_code_solver import FileCodeSolverAgent, CodeSolution
from core_new.agents.hybrid_subjective_team import (
    QuestionDesignerAgent,
    HybridSolutionFormatter,
    HybridRubricWriter,
    IntentBasedReviewer,
)
from core_new.agents.single_choice_team import (
    SingleChoiceDraftAgent,
    RuntimeSingleChoiceDraftAgent,
    OptionAndDistractorAgent,
    SCSolutionFormatterAgent,
)
from core_new.blackboard import Blackboard
from core_new.fallback_executor import FallbackExecutor, FallbackResult
from core_new.markdown_parser import try_parse_json_object

logger = logging.getLogger(__name__)

MAX_REVISION_ROUNDS = 1


# ── Markdown parsing (local) ──────────────────────────────────


def _parse_md_kv(lines: List[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    current_key: Optional[str] = None
    for line in lines:
        m = re.match(r"^-\s+\*\*(.+?)\*\*[:：]\s*(.*)", line)
        if not m:
            m = re.match(r"^-\s+([^*:：]+?)[:：]\s*(.*)", line)
        if m:
            key, value = m.group(1).strip(), m.group(2).strip()
            if value and (value.startswith("{") or value.startswith("[")):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            result[key] = value
            current_key = key
        elif line.startswith("  ") and current_key and current_key in result:
            if isinstance(result[current_key], str):
                result[current_key] += "\n" + line.strip()
    return result


def _parse_md_sections(text: str) -> Dict[str, Any]:
    sections: Dict[str, Any] = {}
    name: Optional[str] = None
    lines: List[str] = []
    for line in text.split("\n"):
        m = re.match(r"^##\s+(.+)", line)
        if m:
            if name:
                sections[name] = _parse_md_kv(lines)
            name = m.group(1).strip()
            lines = []
        elif name:
            lines.append(line)
    if name:
        sections[name] = _parse_md_kv(lines)
    return sections


# ── Unified SC Reviewer ───────────────────────────────────────


UNIFIED_SC_REVIEW_PROMPT = """你是一位408考研出题审核专家。请审核以下单选题，重点对比代码验证结果与出题意图。

## 题目
{stem}

## 选项
- A: {option_A}
- B: {option_B}
- C: {option_C}
- D: {option_D}

## 出题意图
- 正确答案: {intended_correct}
- 干扰策略:
{distractor_strategies}

## 求解器验证结果（Python代码逐选项计算）
{solver_verification_json}

## 出题蓝图（用于对照）
{slot_blueprint_json}

## 审核要求

请逐一检查：
1. **computed_vs_intended**: 求解器计算得出的正确答案（computed_correct）是否与出题意图中的正确答案一致
2. **option_consistency**: 4个选项的验证结果是否逻辑自洽（恰好1个正确，3个错误）
3. **slot_match**: 考点、难度、风格是否匹配蓝图要求
4. **answer_correctness**: 结合计算结果，最终答案是否正确

如果 computed_correct 与 intended_correct 不一致：
- 仔细分析是求解器计算有误，还是选项设计本身有问题
- fix_target = "answer" 表示需要重新计算（求解器可能出错）
- fix_target = "options" 表示需要重新生成选项（选项设计有误）
- fix_target = "question" 表示题目参数或条件有问题

请严格按以下markdown格式输出：

## review
- **status**: pass 或 needs_fix
- **computed_vs_intended**: match 或 mismatch（附说明）
- **option_consistency**: pass 或 fail（附说明）
- **slot_match**: pass 或 fail（附说明）
- **answer_correctness**: pass 或 fail（附说明）
- **overall_quality**: 1-10
- **comment**: 总体评价（2-3句话）

## fix_instruction
- **fix_target**: question 或 options 或 solution 或 none
- **fix_detail**: 具体修复指令（status为pass则写"无"）"""


class UnifiedSCReviewer(BaseAgent):
    """Review SC question: compare solver verification vs intended options."""

    def __init__(self, llm_backend, *, max_tokens: int = 1500):
        super().__init__(
            AgentConfig(
                name="unified_sc_reviewer",
                phase="unified_review",
                output_format="markdown",
                output_key="review",
                max_tokens=max_tokens,
                enable_thinking=True,
                required_fields=["status"],
                repair_max_retries=1,
                role_type=RoleType.AUDIT,
                audit_mode=AuditMode.QUESTION_REVIEW,
                expected_output_format=(
                    "## review\n"
                    "- **status**: pass|needs_fix\n"
                    "- **computed_vs_intended**: match|mismatch\n"
                    "- **option_consistency**: pass|fail\n"
                    "- **slot_match**: pass|fail\n"
                    "- **answer_correctness**: pass|fail\n"
                    "- **overall_quality**: 1-10\n\n"
                    "## fix_instruction\n"
                    "- **fix_target**: question|options|solution|none\n"
                    "- **fix_detail**: ..."
                ),
                system_prompt="你是一位408考研出题审核专家，负责对比代码验证结果与出题意图。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        design = blackboard.get("sc_design", {})
        options = blackboard.get("sc_options", {})
        solver_result = blackboard.get("solver_result", {})
        blueprint = blackboard.get("current_blueprint", {})

        computed = solver_result.get("computed_results", {})
        verification_json = json.dumps(computed, ensure_ascii=False, indent=2)

        distractor_parts = []
        for letter in "ABCD":
            intent = options.get(f"distractor_intent_{letter}", "")
            if intent:
                distractor_parts.append(f"  {letter}: {intent}")
        distractor_strategies = "\n".join(distractor_parts) if distractor_parts else "  未提供"

        prompt = UNIFIED_SC_REVIEW_PROMPT.format(
            stem=design.get("stem", ""),
            option_A=options.get("option_A", ""),
            option_B=options.get("option_B", ""),
            option_C=options.get("option_C", ""),
            option_D=options.get("option_D", ""),
            intended_correct=options.get("correct_answer", "未知"),
            distractor_strategies=distractor_strategies,
            solver_verification_json=verification_json,
            slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
        )
        checklist = self.get_audit_checklist()
        if checklist:
            prompt += "\n\n" + checklist
        return prompt

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        data = try_parse_json_object(text)
        if data:
            result: Dict[str, Any] = {}
            nested_review = data.get("review")
            if isinstance(nested_review, dict):
                result.update(nested_review)
            else:
                result.update(data)
            if isinstance(data.get("fix_instruction"), dict):
                result["fix_instruction"] = data["fix_instruction"]
            if result.get("status"):
                result["status"] = str(result["status"]).lower()
                if result["status"] in {"revise", "fail", "failed"}:
                    result["status"] = "needs_fix"
            return result

        sections = _parse_md_sections(text)
        result: Dict[str, Any] = {}

        for key in ("review", "结果", "检查"):
            if key in sections:
                result.update(sections[key])

        if "fix_instruction" in sections:
            result["fix_instruction"] = sections["fix_instruction"]

        if "status" not in result:
            m = re.search(r"\*\*status\*\*[:：]\s*(\w+)", text)
            if m:
                result["status"] = m.group(1).strip().lower()

        if "fix_target" not in result:
            m = re.search(r"\*\*fix_target\*\*[:：]\s*(\w+)", text)
            if m:
                result["fix_target"] = m.group(1).strip().lower()

        if "computed_vs_intended" not in result:
            m = re.search(r"\*\*computed_vs_intended\*\*[:：]\s*(\w+)", text)
            if m:
                result["computed_vs_intended"] = m.group(1).strip().lower()

        if result.get("status"):
            result["status"] = str(result["status"]).lower()
            if result["status"] in {"revise", "fail", "failed"}:
                result["status"] = "needs_fix"

        return result

    def validate_parsed(self, parsed: Any) -> tuple[bool, str]:
        ok, detail = super().validate_parsed(parsed)
        if not ok:
            return ok, detail
        status = str(parsed.get("status", "")).strip().lower()
        if status not in {"pass", "needs_fix"}:
            return False, "status must be pass or needs_fix"
        return True, ""


# ── Result ────────────────────────────────────────────────────


@dataclass
class UnifiedPipelineResult:
    final_question: Dict[str, Any]
    solver_result: Dict[str, Any]
    review: Dict[str, Any]
    generation_time_s: float
    pipeline_type: str = "unified"


# ── Pipeline ──────────────────────────────────────────────────


class UnifiedQuestionPipeline:
    """One pipeline for both SC and comprehensive questions.

    Solver is ALWAYS a pure computation engine:
    - SC: computes all 4 options, outputs per-option verification
    - Comp: computes all sub-questions

    Reviewer compares computation vs intent and routes fixes.
    """

    def __init__(
        self,
        *,
        max_revision_rounds: int = MAX_REVISION_ROUNDS,
        use_runtime_sc_design: bool = True,
        runtime_fallback: bool = True,
    ):
        self.max_revision_rounds = max_revision_rounds
        self.use_runtime_sc_design = use_runtime_sc_design
        self.runtime_fallback = runtime_fallback
        self.fix_router = FixRouter(max_revision_rounds=max_revision_rounds)
        self.fallback_executor = FallbackExecutor()
        self.fallback_executor.register("human_review", self._fallback_human_review)
        self.fallback_executor.register("needs_human_check", self._fallback_human_review)
        self.fallback_executor.register("legacy_generator", self._fallback_legacy_generator)

    @staticmethod
    def _is_single_choice(blueprint: Dict[str, Any]) -> bool:
        q_type = blueprint.get("question_type", "")
        if q_type == "single_choice":
            return True
        if q_type == "comprehensive":
            return False
        slot_id = blueprint.get("slot_id", "")
        if slot_id.startswith("Q") and slot_id[1:].isdigit():
            return int(slot_id[1:]) < 43
        return True

    @staticmethod
    def _require_step_fields(
        step_name: str,
        data: Dict[str, Any],
        fields: List[str],
    ) -> None:
        missing = [field for field in fields if not data.get(field)]
        if missing:
            raise RuntimeError(f"{step_name} produced incomplete output; missing: {', '.join(missing)}")

    @staticmethod
    def _raise_if_failed(step_name: str, record) -> None:
        if record and getattr(record, "error", None):
            raise RuntimeError(f"{step_name} failed: {record.error}")

    # ── Fallback handlers ─────────────────────────────────────

    @staticmethod
    async def _fallback_human_review(data: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "needs_human_review",
            "reason": "Agent failed, routed to human review",
        }

    @staticmethod
    async def _fallback_legacy_generator(data: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "fallback_used",
            "fallback_target": "legacy_generator",
            "note": "Legacy generator fallback — pipeline should re-run design step",
        }

    async def _execute_with_fallback(
        self,
        agent,
        blackboard: Blackboard,
    ) -> tuple[Any, Optional[FallbackResult]]:
        """Execute agent, attempt fallback on failure."""
        record = await agent.execute(blackboard)

        if record.error is None:
            return record, None

        metadata = getattr(record, "metadata", None) or {}
        fallback_info = metadata.get("fallback", {})
        if fallback_info.get("enabled"):
            bb_data = blackboard.get_relevant_state(agent.config.name)
            fallback_result = await self.fallback_executor.try_fallback(record, bb_data)
            if fallback_result.used_fallback and not fallback_result.error:
                logger.info(
                    "[Fallback] succeeded: target=%s, latency=%dms",
                    fallback_result.fallback_target,
                    fallback_result.latency_ms,
                )
                return record, fallback_result
            logger.warning(
                "[Fallback] target=%s failed: %s",
                fallback_result.fallback_target,
                fallback_result.error,
            )

        return record, None

    # ── Main run loop ──────────────────────────────────────────

    async def run(
        self,
        slot_blueprint: Dict[str, Any],
        experience_card: str,
        gateway,
    ) -> UnifiedPipelineResult:
        is_sc = self._is_single_choice(slot_blueprint)
        slot_id = slot_blueprint.get("slot_id", "Q1")
        total_start = time.monotonic()

        design: Dict[str, Any] = {}
        options: Dict[str, Any] = {}
        code_solution: Optional[CodeSolution] = None
        solution: Dict[str, Any] = {}
        rubric: Dict[str, Any] = {}
        review: Dict[str, Any] = {}
        fix_target: Optional[str] = None

        for rnd in range(self.max_revision_rounds + 1):
            if rnd > 0:
                logger.info("[%s] Revision round %d, fix_target=%s",
                            slot_id, rnd, fix_target)

            # ── Step 1: Design ──
            need_design = rnd == 0 or fix_target in ("question",)
            if need_design:
                if is_sc:
                    design = await self._design_sc(
                        slot_blueprint, experience_card, gateway,
                    )
                else:
                    design = await self._design_comp(
                        slot_blueprint, experience_card, gateway,
                    )
                if not design:
                    logger.error("[%s] Design produced empty result", slot_id)
                    break

            # ── Step 2: Options (SC only) ──
            need_options = is_sc and (rnd == 0 or fix_target in ("question", "options"))
            if need_options:
                options = await self._generate_options(design, slot_blueprint, gateway)

            # ── Step 3: Solve (unified computation) ──
            need_solve = rnd == 0 or fix_target in ("question", "options", "answer")
            if need_solve:
                code_solution = await self._solve(
                    design, options if is_sc else None, is_sc, slot_id, gateway,
                )

            # ── Step 4: Format solution ──
            need_format = rnd == 0 or fix_target in ("question", "options", "answer")
            if need_format:
                if is_sc:
                    solution = await self._format_sc(
                        design, options, code_solution, gateway,
                    )
                else:
                    solution = await self._format_comp(design, code_solution, gateway)

            # ── Step 5: Rubric (Comp only) ──
            if not is_sc and need_format:
                rubric = await self._write_rubric(
                    design, solution, slot_blueprint, gateway,
                )

            # ── Step 6: Review ──
            review = await self._review(
                design, options, code_solution, solution, rubric,
                slot_blueprint, is_sc, gateway,
            )

            audit = AuditResultNormalizer.normalize(
                review,
                mode=AuditMode.QUESTION_REVIEW,
            )
            route = self.fix_router.route(
                audit,
                current_round=rnd,
                is_single_choice=is_sc,
                source_policy=source_policy_for_audit_mode(AuditMode.QUESTION_REVIEW),
            )
            review["audit_result"] = audit.to_dict()
            review["fix_route"] = route.to_dict()

            logger.info(
                "[%s] Review round %d: status=%s issue=%s route=%s target=%s",
                slot_id,
                rnd,
                audit.status,
                audit.issue_type,
                route.next_action,
                route.pipeline_fix_target,
            )

            if route.next_action != "revise":
                break

            fix_target = route.pipeline_fix_target

        # ── Assemble final result ──
        total_time = time.monotonic() - total_start
        final_question = self._assemble(
            slot_id, design, options, code_solution, solution, rubric, is_sc,
        )
        solver_dict = code_solution.to_dict() if code_solution else {}

        logger.info("[%s] Unified pipeline done in %.1fs (%d rounds, type=%s)",
                     slot_id, total_time, rnd + 1, "SC" if is_sc else "Comp")

        return UnifiedPipelineResult(
            final_question=final_question,
            solver_result=solver_dict,
            review=review,
            generation_time_s=round(total_time, 1),
            pipeline_type="unified_sc" if is_sc else "unified_comp",
        )

    # ── Step methods ───────────────────────────────────────────

    async def _design_sc(
        self,
        blueprint: Dict[str, Any],
        experience_card: str,
        gateway,
    ) -> Dict[str, Any]:
        """SC Step 1: generate question stem."""
        def make_blackboard() -> Blackboard:
            return Blackboard(
                task_id=f"sc_design_{blueprint.get('slot_id', 'Q1')}",
                task_type="unified_sc",
                initial_state={
                    "current_blueprint": blueprint,
                    "experience_card": experience_card,
                },
            )

        bb = make_blackboard()
        if self.use_runtime_sc_design:
            runtime_agent = RuntimeSingleChoiceDraftAgent(gateway)
            runtime_record = await runtime_agent.execute(bb)
            if not runtime_record.error:
                result = bb.get("sc_draft_result", {})
                self._require_step_fields("Runtime SC design", result, ["stem"])
                logger.info("[Runtime SC design] stem=%s", str(result.get("stem", ""))[:80])
                return result

            logger.warning("[Runtime SC design] failed: %s", runtime_record.error)
            if not self.runtime_fallback:
                self._raise_if_failed("Runtime SC design", runtime_record)

            bb = make_blackboard()

        agent = SingleChoiceDraftAgent(gateway)
        record = None
        for attempt in range(3):
            record = await agent.execute(bb)
            if not record.error:
                break
            is_net = "network" in str(record.error).lower() or "connection" in str(record.error).lower()
            if is_net and attempt < 2:
                logger.warning("[SC design] Network error (attempt %d), retrying in 15s",
                               attempt + 1)
                await asyncio.sleep(15)
                continue
            break

        if record.error:
            bb_data = bb.get_relevant_state(agent.config.name)
            fb_result = await self.fallback_executor.try_fallback(record, bb_data)
            if fb_result.used_fallback and not fb_result.error:
                logger.info("[SC design] Fallback succeeded: %s", fb_result.fallback_target)
                if fb_result.fallback_target in ("human_review", "needs_human_check"):
                    return {"status": "needs_human_review",
                            "reason": fb_result.result_data.get("reason", "SC design failed, routed to human review"),
                            "fallback_target": fb_result.fallback_target}
                # For non-human fallbacks (legacy_generator), continue with original error
                # — pipeline-specific handler should have produced usable output

        self._raise_if_failed("SC design", record)

        result = bb.get("sc_draft_result", {})
        self._require_step_fields("SC design", result, ["stem"])
        logger.info("[SC design] stem=%s", str(result.get("stem", ""))[:80])
        return result

    async def _design_comp(
        self,
        blueprint: Dict[str, Any],
        experience_card: str,
        gateway,
    ) -> Dict[str, Any]:
        """Comp Step 1: generate question design with sub-questions and intent."""
        bb = Blackboard(
            task_id=f"comp_design_{blueprint.get('slot_id', 'Q43')}",
            task_type="unified_comp",
            initial_state={
                "current_blueprint": blueprint,
                "experience_card": experience_card,
                "reference_questions": experience_card,
            },
        )
        agent = QuestionDesignerAgent(gateway)
        record = None
        for attempt in range(3):
            record = await agent.execute(bb)
            if not record.error:
                break
            is_net = "network" in str(record.error).lower() or "connection" in str(record.error).lower()
            if is_net and attempt < 2:
                logger.warning("[Comp design] Network error (attempt %d), retrying in 15s",
                               attempt + 1)
                await asyncio.sleep(15)
                continue
            break

        if record.error:
            bb_data = bb.get_relevant_state(agent.config.name)
            fb_result = await self.fallback_executor.try_fallback(record, bb_data)
            if fb_result.used_fallback and not fb_result.error:
                logger.info("[Comp design] Fallback succeeded: %s", fb_result.fallback_target)
                if fb_result.fallback_target in ("human_review", "needs_human_check"):
                    return {"status": "needs_human_review",
                            "reason": fb_result.result_data.get("reason", "Comp design failed, routed to human review"),
                            "fallback_target": fb_result.fallback_target}

        self._raise_if_failed("Comp design", record)

        result = bb.get("question_design", {})
        self._require_step_fields("Comp design", result, ["stem", "sub_questions"])
        logger.info("[Comp design] stem=%s", str(result.get("stem", ""))[:80])
        return result

    async def _generate_options(
        self,
        design: Dict[str, Any],
        blueprint: Dict[str, Any],
        gateway,
    ) -> Dict[str, Any]:
        """SC Step 2: generate 4 options with distractor intent."""
        bb = Blackboard(
            task_id=f"sc_opts_{blueprint.get('slot_id', 'Q1')}",
            task_type="unified_sc",
            initial_state={
                "sc_draft_result": design,
                "current_blueprint": blueprint,
            },
        )
        agent = OptionAndDistractorAgent(gateway)
        record = await agent.execute(bb)
        self._raise_if_failed("SC options", record)
        result = bb.get("sc_options_result", {})
        self._require_step_fields(
            "SC options",
            result,
            ["option_A", "option_B", "option_C", "option_D", "correct_answer"],
        )
        logger.info("[SC options] correct=%s", result.get("correct_answer", "?"))
        return result

    async def _solve(
        self,
        design: Dict[str, Any],
        options: Optional[Dict[str, Any]],
        is_sc: bool,
        slot_id: str,
        gateway,
    ) -> CodeSolution:
        """Step 3: FileCodeSolver — pure computation engine."""
        solver = FileCodeSolverAgent(gateway, max_tokens=4096, max_steps=5)

        if is_sc and options:
            options_dict = {
                "A": options.get("option_A", ""),
                "B": options.get("option_B", ""),
                "C": options.get("option_C", ""),
                "D": options.get("option_D", ""),
            }
            result = await solver.solve(
                question_draft=design.get("stem", ""),
                options=options_dict,
                question_type="single_choice",
                slot_id=slot_id,
            )
        else:
            sub_questions = design.get("sub_questions", [])
            if isinstance(sub_questions, str):
                try:
                    sub_questions = json.loads(sub_questions)
                except json.JSONDecodeError:
                    sub_questions = [sub_questions]

            result = await solver.solve(
                question_draft=design.get("stem", ""),
                sub_questions=sub_questions if sub_questions else None,
                question_type="comprehensive",
                slot_id=slot_id,
            )

        logger.info("[%s] Solver done: %d execs, %.1fs, error=%s",
                     slot_id, result.python_exec_count, result.total_time_s,
                     result.error[:100] if result.error else "none")
        return result

    async def _format_sc(
        self,
        design: Dict[str, Any],
        options: Dict[str, Any],
        code_solution: Optional[CodeSolution],
        gateway,
    ) -> Dict[str, Any]:
        """SC Step 4: format solution from solver verification result."""
        solver_dict = code_solution.to_dict() if code_solution else {}
        bb = Blackboard(
            task_id=f"sc_format_{design.get('slot_id', 'Q1')}",
            task_type="unified_sc",
            initial_state={
                "sc_draft_result": design,
                "sc_options_result": options,
                "sc_solver_result": solver_dict,
            },
        )
        agent = SCSolutionFormatterAgent(gateway)
        record = await agent.execute(bb)
        self._raise_if_failed("SC format", record)
        result = bb.get("sc_solution_result", {})
        self._require_step_fields("SC format", result, ["correct_answer", "explanation"])
        return result

    async def _format_comp(
        self,
        design: Dict[str, Any],
        code_solution: Optional[CodeSolution],
        gateway,
    ) -> Dict[str, Any]:
        """Comp Step 4: format solution from solver output."""
        solver_dict = code_solution.to_dict() if code_solution else {}
        if code_solution:
            solver_dict["raw_outputs"] = [o[:2000] for o in (code_solution.outputs or [])]
            solver_dict["last_raw_output"] = code_solution.get_last_output()[:3000]

        bb = Blackboard(
            task_id=f"comp_format_{design.get('slot_id', 'Q43')}",
            task_type="unified_comp",
            initial_state={
                "question_design": design,
                "solver_result": solver_dict,
            },
        )
        agent = HybridSolutionFormatter(gateway)
        record = await agent.execute(bb)
        self._raise_if_failed("Comp format", record)
        result = bb.get("formatted_solution", {})
        self._require_step_fields("Comp format", result, ["answers"])
        return result

    async def _write_rubric(
        self,
        design: Dict[str, Any],
        solution: Dict[str, Any],
        blueprint: Dict[str, Any],
        gateway,
    ) -> Dict[str, Any]:
        """Comp Step 5: write grading rubric."""
        bb = Blackboard(
            task_id=f"comp_rubric_{design.get('slot_id', 'Q43')}",
            task_type="unified_comp",
            initial_state={
                "question_design": design,
                "formatted_solution": solution,
                "current_blueprint": blueprint,
            },
        )
        agent = HybridRubricWriter(gateway)
        await agent.execute(bb)
        return bb.get("rubric", {})

    async def _review(
        self,
        design: Dict[str, Any],
        options: Dict[str, Any],
        code_solution: Optional[CodeSolution],
        solution: Dict[str, Any],
        rubric: Dict[str, Any],
        blueprint: Dict[str, Any],
        is_sc: bool,
        gateway,
    ) -> Dict[str, Any]:
        """Step 6: review — compare computation vs intent."""
        solver_dict = code_solution.to_dict() if code_solution else {}

        if is_sc:
            bb = Blackboard(
                task_id=f"sc_review_{blueprint.get('slot_id', 'Q1')}",
                task_type="unified_sc",
                initial_state={
                    "sc_design": design,
                    "sc_options": options,
                    "solver_result": solver_dict,
                    "current_blueprint": blueprint,
                },
            )
            reviewer = UnifiedSCReviewer(gateway)
        else:
            bb = Blackboard(
                task_id=f"comp_review_{blueprint.get('slot_id', 'Q43')}",
                task_type="unified_comp",
                initial_state={
                    "question_design": design,
                    "formatted_solution": solution,
                    "rubric": rubric,
                    "current_blueprint": blueprint,
                },
            )
            reviewer = IntentBasedReviewer(gateway)

        record = await reviewer.execute(bb)
        if record.error:
            bb_data = bb.get_relevant_state(reviewer.config.name)
            fb_result = await self.fallback_executor.try_fallback(record, bb_data)
            if fb_result.used_fallback and not fb_result.error:
                logger.info("[Review] Fallback succeeded: %s", fb_result.fallback_target)
                if fb_result.fallback_target in ("human_review", "needs_human_check"):
                    return {"status": "needs_human_review",
                            "reason": fb_result.result_data.get("reason", "Review failed, routed to human review"),
                            "fallback_target": fb_result.fallback_target}
        self._raise_if_failed("Review", record)
        result = bb.get("review", {})
        self._require_step_fields("Review", result, ["status"])
        return result

    # ── Assembly ───────────────────────────────────────────────

    def _assemble(
        self,
        slot_id: str,
        design: Dict[str, Any],
        options: Dict[str, Any],
        code_solution: Optional[CodeSolution],
        solution: Dict[str, Any],
        rubric: Dict[str, Any],
        is_sc: bool,
    ) -> Dict[str, Any]:
        """Assemble final question dict from pipeline outputs."""
        solver_confidence = "high"
        if code_solution and (not code_solution.computed_results or code_solution.error):
            solver_confidence = "low"

        if is_sc:
            return {
                "slot_id": slot_id,
                "stem": design.get("stem", ""),
                "option_A": options.get("option_A", ""),
                "option_B": options.get("option_B", ""),
                "option_C": options.get("option_C", ""),
                "option_D": options.get("option_D", ""),
                "correct_answer": solution.get(
                    "correct_answer", options.get("correct_answer", ""),
                ),
                "explanation": solution.get("explanation", ""),
                "solution_steps": solution.get("solution_steps", ""),
                "difficulty_self_assessment": solution.get("difficulty_self_assessment", ""),
                "trap_description": solution.get("trap_description", ""),
                "knowledge_points": solution.get("knowledge_points", ""),
                "solver_confidence": solver_confidence,
                "python_exec_count": code_solution.python_exec_count if code_solution else 0,
                "code_files": code_solution.code_files if code_solution else [],
                "pipeline_type": "unified_sc",
            }

        # Comprehensive
        formatted_answer = solution.get("answers", solution)
        if isinstance(formatted_answer, dict) and not formatted_answer:
            formatted_answer = code_solution.get_last_output()[:3000] if code_solution else ""

        sub_questions = design.get("sub_questions", [])
        if isinstance(sub_questions, str):
            try:
                sub_questions = json.loads(sub_questions)
            except json.JSONDecodeError:
                sub_questions = [sub_questions]

        return {
            "slot_id": slot_id,
            "stem": design.get("stem", ""),
            "sub_questions": sub_questions,
            "given_conditions": design.get("given_conditions", []),
            "difficulty_self_assessment": design.get("difficulty_self_assessment"),
            "knowledge_points": design.get("knowledge_points", ""),
            "parameter_notes": design.get("parameter_notes", ""),
            "design_intent": design.get("design_intent", {}),
            "answer": formatted_answer,
            "correct_answer": formatted_answer,
            "solver_confidence": solver_confidence,
            "solver_evidence": code_solution.get_last_output()[:3000] if code_solution else "",
            "python_exec_count": code_solution.python_exec_count if code_solution else 0,
            "code_files": code_solution.code_files if code_solution else [],
            "rubric": rubric,
            "pipeline_type": "unified_comp",
        }
