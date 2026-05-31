"""Unified Question Pipeline — one workflow for both single-choice and comprehensive questions.

Provider routing: review/gate/format agents use local Qwen when available,
generation agents always use remote GLM.

Architecture:
  Step 1: Design (SC: stem; Comp: stem + sub_questions + intent — merged with slot reading)
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
from core_new.agents.file_code_solver import FileCodeSolverAgent, RuntimeFileCodeSolver, CodeSolution
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
    StemVerifierAgent,
    PostReviewAgent,
    QuestionSummaryAgent,
)
from core_new.agents.final_review_team import FinalReviewAgent, FinalFixerAgent
from core_new.blackboard import Blackboard
from core_new.validators import structural_validate
from core_new.fallback_executor import FallbackExecutor, FallbackResult
from core_new.provider_router import get_routed_gateway as _rgw
from core_new.markdown_parser import try_parse_json_object, parse_md_kv, parse_md_sections, parse_structured_output

logger = logging.getLogger(__name__)

MAX_REVISION_ROUNDS = 1


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
- fix_target = "question" 表示题目参数或条件自相矛盾（如地址位数不够、容量参数不匹配），需要重新出题
- fix_target = "options" 表示需要重新生成选项（选项设计有误但题干合理）
- fix_target = "answer" 表示题目设计合理但求解器计算出错

注意：不要因为答案错误就盲目路由到 answer。先检查题目条件是否合理，如果题目参数自相矛盾，必须路由到 question。

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
                enable_thinking=False,
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
        # Try JSON first for nested key + fix_instruction handling
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

        # Shared markdown parser
        result = parse_structured_output(text, md_sections=("review", "fix_instruction"))

        # Also check Chinese section name variants
        if not result:
            sections = parse_md_sections(text)
            result = {}
            for key in ("review", "结果", "检查"):
                if key in sections:
                    result.update(sections[key])
            if "fix_instruction" in sections:
                result["fix_instruction"] = sections["fix_instruction"]

        # Fallback: regex extraction for critical fields
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
    knowledge_gate_result: Optional[Dict[str, Any]] = None
    environment_gate_result: Optional[Dict[str, Any]] = None


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
        enable_stem_gate: bool = False,
        use_runtime_solver: bool = True,
        enable_post_review: bool = True,
        enable_summary: bool = True,
        debug_dir: Optional[str] = None,
    ):
        self.max_revision_rounds = max_revision_rounds
        self.use_runtime_sc_design = use_runtime_sc_design
        self.runtime_fallback = runtime_fallback
        self.enable_post_review = enable_post_review
        self.enable_summary = enable_summary
        self.enable_stem_gate = enable_stem_gate
        self.use_runtime_solver = use_runtime_solver
        self.debugger = None
        if debug_dir:
            from core_new.debug_pipeline import PipelineDebugger
            self.debugger = PipelineDebugger(debug_dir)
            logger.info("[Debug] Pipeline debug output: %s", debug_dir)
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
        logger.warning(
            "blueprint missing question_type, cannot determine question kind: slot_id=%s",
            blueprint.get("slot_id", "?"),
        )
        raise ValueError(
            f"blueprint must contain 'question_type' ('single_choice' or 'comprehensive'); "
            f"got {q_type!r} for slot {blueprint.get('slot_id', '?')}"
        )

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

    @staticmethod
    def _build_round_snapshot(
        rnd: int,
        design: Dict[str, Any],
        options: Dict[str, Any],
        solution: Dict[str, Any],
        review: Dict[str, Any],
        is_sc: bool,
        design_intent: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Build message-list entries for one round's output.

        Returns a list of message dicts (no truncation):
          [{role: "assistant", content: question_output, round: N},
           {role: "review", content: review_feedback, round: N}]
        """
        messages: List[Dict[str, Any]] = []

        # Build question output text (no truncation)
        parts = []
        stem = design.get("stem", "")
        if stem:
            parts.append(f"题干: {stem}")
        if is_sc:
            for k in ("option_A", "option_B", "option_C", "option_D"):
                if options.get(k):
                    parts.append(f"{k}: {options[k]}")
            if options.get("correct_answer"):
                parts.append(f"正确答案: {options['correct_answer']}")
            if solution.get("explanation"):
                parts.append(f"解析: {solution['explanation']}")
        else:
            subs = design.get("sub_questions", [])
            if subs:
                parts.append(f"子问题({len(subs)}问): {json.dumps(subs, ensure_ascii=False, indent=2)}")
        if parts:
            messages.append({"role": "assistant", "content": "\n".join(parts), "round": rnd})

        # Build review feedback text (no truncation)
        review_parts = []
        status = review.get("status", review.get("audit_result", {}).get("status", ""))
        if status:
            review_parts.append(f"审查状态: {status}")
        quality = review.get("overall_quality", review.get("quality", ""))
        if quality:
            review_parts.append(f"质量评分: {quality}")
        comment = review.get("comment", "")
        if comment:
            review_parts.append(f"审查意见: {comment}")
        fix_detail = review.get("fix_detail", review.get("audit_result", {}).get("fix_detail", ""))
        if fix_detail:
            review_parts.append(f"修复建议: {fix_detail}")
        issue_type = review.get("audit_result", {}).get("issue_type", "")
        if issue_type:
            review_parts.append(f"问题类型: {issue_type}")
        if review_parts:
            messages.append({"role": "review", "content": "\n".join(review_parts), "round": rnd})

        return messages

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
        *,
        previous_question: Optional[Dict[str, Any]] = None,
        fix_instruction: str = "",
        is_regen: bool = False,
        resume_from: Optional[str] = None,
        resume_state: Optional[Dict[str, Any]] = None,
    ) -> UnifiedPipelineResult:
        is_sc = self._is_single_choice(slot_blueprint)
        slot_id = slot_blueprint.get("slot_id", "Q1")
        total_start = time.monotonic()

        design: Dict[str, Any] = {}
        options: Dict[str, Any] = {}
        code_solution: Optional[CodeSolution] = None
        solver_dict: Dict[str, Any] = {}
        solution: Dict[str, Any] = {}
        rubric: Dict[str, Any] = {}
        review: Dict[str, Any] = {}
        verify_result: Dict[str, Any] = {}
        gate_result: Dict[str, Any] = {"status": "skipped"}
        final_review: Dict[str, Any] = {}
        fix_target: Optional[str] = None
        stem_fix_instruction: Optional[str] = None
        round_history: List[Dict[str, Any]] = []

        # ── Resume support ──
        _RESUME_STAGES = {
            "design", "options", "gate", "solve", "verify",
            "format", "rubric", "final_review", "final_fixer",
        }
        _STAGE_ORDER = [
            "design", "options", "gate", "solve", "verify",
            "format", "rubric", "final_review", "final_fixer",
        ]

        if resume_from:
            if resume_from not in _RESUME_STAGES:
                raise ValueError(f"Invalid resume_from: {resume_from!r}")
            if not resume_state:
                raise ValueError("resume_state required when resume_from is set")
            # Restore state from resume_state
            is_sc = resume_state.get("is_sc", is_sc)
            design = resume_state.get("design", design)
            options = resume_state.get("options", options)
            solver_dict = resume_state.get("solver_dict", solver_dict)
            if solver_dict and not code_solution:
                code_solution = CodeSolution.from_dict(solver_dict)
            solution = resume_state.get("solution", solution)
            rubric = resume_state.get("rubric", rubric)
            verify_result = resume_state.get("verify_result", verify_result)
            review = resume_state.get("review", review)
            gate_result = resume_state.get("gate_result", gate_result)
            final_review = resume_state.get("final_review", final_review)
            logger.info("[%s] Resuming from stage: %s", slot_id, resume_from)

        # Compute which stages to skip when resuming
        if resume_from and resume_from in _STAGE_ORDER:
            resume_idx = _STAGE_ORDER.index(resume_from)
            _skip_stages = set(s for s in _STAGE_ORDER if _STAGE_ORDER.index(s) < resume_idx)
        else:
            _skip_stages = set()

        # When resuming, skip the entire revision loop
        if _skip_stages and resume_from in _STAGE_ORDER:
            resume_idx = _STAGE_ORDER.index(resume_from)
            _skip_loop = resume_from not in {"design", "options", "gate", "solve", "verify"}
        else:
            _skip_loop = False

        for rnd in range(self.max_revision_rounds + 1):
            if _skip_loop:
                break
            if rnd > 0:
                logger.info("[%s] Revision round %d, fix_target=%s",
                            slot_id, rnd, fix_target)

            # ── Step 1: Design ──
            need_design = rnd == 0 or fix_target in ("question", "stem")
            if "design" in _skip_stages:
                logger.info("[%s] Resuming: skipping design", slot_id)
            elif need_design:
                if is_sc:
                    design = await self._design_sc(
                        slot_blueprint, experience_card, gateway,
                        stem_fix_instruction=stem_fix_instruction,
                        round_history=round_history,
                    )
                else:
                    design = await self._design_comp(
                        slot_blueprint, experience_card, gateway,
                        stem_fix_instruction=stem_fix_instruction,
                        round_history=round_history,
                    )
                if not design:
                    logger.error("[%s] Design produced empty result", slot_id)
                    break
                if design.get("status") in {"needs_human_review", "needs_human_check"}:
                    if self.debugger:
                        self.debugger.dump_step(slot_id, "design", rnd, design)
                    total_time = time.monotonic() - total_start
                    return UnifiedPipelineResult(
                        final_question=design,
                        solver_result={},
                        review={
                            "status": design.get("status"),
                            "reason": design.get("reason", ""),
                            "fallback_target": design.get("fallback_target", ""),
                        },
                        generation_time_s=round(total_time, 1),
                        pipeline_type="unified_sc" if is_sc else "unified_comp",
                    )

                # Structural pre-check (pure Python, no LLM)
                struct_errors = structural_validate(design, "single_choice" if is_sc else "comprehensive")
                if struct_errors:
                    logger.warning("[%s] Structural validation failed: %s", slot_id, struct_errors)
                    if self.debugger:
                        self.debugger.dump_step(slot_id, "design", rnd, {"structural_errors": struct_errors})
                    # For structural errors, route to redesign immediately
                    if rnd >= self.max_revision_rounds:
                        logger.warning("[%s] Structural validation failed, revision budget exhausted", slot_id)
                        break
                    fix_target = "stem"
                    stem_fix_instruction = f"Structural errors detected: {', '.join(struct_errors)}. Please fix these format issues."
                    round_history.append({"role": "review", "content": stem_fix_instruction, "round": rnd})
                    continue

                if self.debugger:
                    self.debugger.dump_step(slot_id, "design", rnd, design)

            # ── Step 2: Options (SC only) ──
            need_options = is_sc and (rnd == 0 or fix_target in ("question", "options"))
            if "options" in _skip_stages:
                logger.info("[%s] Resuming: skipping options", slot_id)
            elif need_options:
                options = await self._generate_options(
                    design, slot_blueprint, gateway,
                    round_history=round_history,
                )
                if self.debugger:
                    self.debugger.dump_step(slot_id, "options", rnd, options)

            # ── Step 3: StemBlueprintGate (replaces gates + stem_verify + post_review) ──
            auto_gate = not is_sc  # comprehensive questions always gate
            need_gate = (self.enable_stem_gate or auto_gate) and (rnd == 0 or fix_target in ("question", "stem"))
            if "gate" in _skip_stages:
                logger.info("[%s] Resuming: skipping gate", slot_id)
            elif need_gate:
                gate_result = await self._run_stem_blueprint_gate(
                    design, options if is_sc else None,
                    slot_blueprint, None, experience_card,
                    slot_id, gateway,
                )
                gate_status = gate_result.get("status", "needs_fix")
                gate_severity = gate_result.get("severity", "none")

                minor_text = gate_result.get("fix_detail", "")

                # needs_fix (any severity) → route based on severity
                if gate_status == "needs_fix":
                    if gate_severity == "critical":
                        # Critical → back to design
                        fix_target = "stem"
                        raw_text = gate_result.get("_raw_text", "")
                        if raw_text:
                            round_history.append({"role": "review", "content": raw_text, "round": rnd})
                        else:
                            round_history.append({"role": "review", "content": gate_result.get("fix_detail", ""), "round": rnd})
                        logger.info("[%s] StemBlueprintGate FAILED (critical), routing to stem redesign", slot_id)
                        if rnd >= self.max_revision_rounds:
                            logger.warning("[%s] Gate failed, revision budget exhausted", slot_id)
                            break
                        continue
                    else:
                        # minor needs_fix → treat as pass_with_notes, polish inline
                        if minor_text and minor_text != "无":
                            design = await self._polish_stem_minor(design, minor_text)
                            logger.info("[%s] StemBlueprintGate: minor needs_fix polished", slot_id)

                # pass_with_notes → inline polish
                elif gate_status == "pass_with_notes" and minor_text and minor_text != "无":
                    design = await self._polish_stem_minor(design, minor_text)
                    logger.info("[%s] StemBlueprintGate: minor polish applied", slot_id)

                logger.info("[%s] StemBlueprintGate PASSED (status=%s severity=%s)", slot_id, gate_status, gate_severity)
                if self.debugger:
                    self.debugger.dump_step(slot_id, "gate", rnd, gate_result)

            # ── Step 4: Solve (unified computation) ──
            need_solve = rnd == 0 or fix_target in ("question", "options", "answer", "solver")
            if "solve" in _skip_stages:
                logger.info("[%s] Resuming: skipping solve", slot_id)
            elif need_solve:
                code_solution = await self._solve(
                    design, options if is_sc else None, is_sc, slot_id, gateway,
                )
                solver_dict = code_solution.to_dict() if code_solution else {}
                if self.debugger:
                    self.debugger.dump_step(slot_id, "solve", rnd, solver_dict)

            # ── Step 5: SolverVerify (replaces review) ──
            if "verify" in _skip_stages:
                logger.info("[%s] Resuming: skipping verify", slot_id)
            else:
                verify_result = await self._run_solver_verify(
                    design, options if is_sc else None,
                    solver_dict, None, is_sc, slot_id, gateway,
                    slot_blueprint=slot_blueprint,
                )
            review = verify_result  # Use verify_result as review for downstream compat

            verify_status = verify_result.get("status", "needs_fix")
            verify_fix_target = verify_result.get("fix_target", "none")

            logger.info("[%s] SolverVerify: status=%s fix_target=%s trusted=%s",
                        slot_id, verify_status, verify_fix_target, verify_result.get("trusted", "?"))
            if self.debugger:
                self.debugger.dump_step(slot_id, "verify", rnd, verify_result)

            # Save round snapshot
            snapshot = self._build_round_snapshot(
                rnd, design, options if is_sc else {}, solution, review, is_sc,
                design_intent=None,
            )
            round_history.extend(snapshot)

            if verify_status == "needs_fix":
                if verify_fix_target == "stem":
                    fix_target = "stem"
                    raw_text = verify_result.get("_raw_text", "")
                    if raw_text:
                        round_history.append({"role": "review", "content": raw_text, "round": rnd})
                    if rnd >= self.max_revision_rounds:
                        logger.warning("[%s] SolverVerify found stem issue, budget exhausted", slot_id)
                        break
                    continue
                else:
                    # solver issue → rerun solver only
                    fix_target = "solver"
                    if rnd >= self.max_revision_rounds:
                        logger.warning("[%s] SolverVerify failed, budget exhausted", slot_id)
                        break
                    continue

            # ── Step 6: Format solution ──
            if "format" in _skip_stages:
                logger.info("[%s] Resuming: skipping format", slot_id)
            elif is_sc:
                solution = await self._format_sc(
                    design, options, solver_dict, gateway,
                )
            else:
                solution = await self._format_comp(design, solver_dict, gateway)
            if self.debugger:
                self.debugger.dump_step(slot_id, "format", rnd, solution)

            # ── Step 7: Rubric (Comp only) ──
            if "rubric" in _skip_stages:
                logger.info("[%s] Resuming: skipping rubric", slot_id)
            elif not is_sc:
                rubric = await self._write_rubric(
                    design, solution, slot_blueprint, gateway,
                )
                if self.debugger:
                    self.debugger.dump_step(slot_id, "rubric", rnd, rubric)

            # All checks passed, break out of revision loop
            break

        # ── Step 8: Final Review + Fixer (after format, before summary) ──
        if "final_review" in _skip_stages:
            logger.info("[%s] Resuming: skipping final_review", slot_id)
        else:
            final_review = await self._run_final_review(
                design, options if is_sc else None, solution, solver_dict,
                is_sc, slot_id, gateway
            )
            if self.debugger:
                self.debugger.dump_step(slot_id, "final_review", 0,
                                        final_review,
                                        input_data={"design": design, "solution": solution})

            if final_review.get("status") == "needs_fix":
                logger.info("Final review found issues (quality=%s): %s",
                            final_review.get("overall_quality"),
                            final_review.get("issues", "")[:200])

                fix_result = await self._run_final_fixer(
                    design, options if is_sc else None, solution, solver_dict,
                    final_review, is_sc, slot_id, gateway
                )
                if self.debugger:
                    self.debugger.dump_step(slot_id, "final_fixer", 0,
                                            fix_result,
                                            input_data={"review": final_review})

                if fix_result.get("status") == "ok":
                    if fix_result.get("fixed_stem"):
                        design["stem"] = fix_result["fixed_stem"]
                    if fix_result.get("fixed_answer") and solution:
                        solution.update(
                            self._safe_parse(fix_result["fixed_answer"])
                            if isinstance(fix_result["fixed_answer"], str)
                            else fix_result["fixed_answer"]
                        )
                    if fix_result.get("fixed_options") and is_sc and options:
                        options = fix_result["fixed_options"]
                    if fix_result.get("fixed_sub_questions") and not is_sc and design:
                        design["sub_questions"] = fix_result["fixed_sub_questions"]
                    logger.info("Final fixer applied: %s", fix_result.get("fix_applied", ""))
                elif fix_result.get("status") not in ("skipped",):
                    logger.warning("Final fixer failed (status=%s), using original output (degraded)",
                                    fix_result.get("status"))

        # ── Step 9: Summary (consolidate all outputs) ──
        summary = {}
        if self.enable_summary and not is_regen:
            summary = await self._summarize(
                design, options, solution, solver_dict, review, {},
                is_sc, slot_id, gateway,
            )
            if self.debugger:
                self.debugger.dump_step(slot_id, "summary", 0, summary)

        # ── Assemble final result ──
        total_time = time.monotonic() - total_start
        final_question = self._assemble(
            slot_id, design, options, code_solution, solution, rubric, is_sc,
            summary=summary,
        )

        if summary:
            final_question["summary"] = summary

        # ── Step 10: Artifact consistency check (non-LLM) ──
        from core_new.artifact_consistency import (
            check_artifact_consistency,
            can_export,
        )
        consistency = check_artifact_consistency(
            final_question, solver_dict, summary, rubric, is_sc=is_sc,
        )
        if self.debugger:
            self.debugger.dump_step(slot_id, "consistency", 0, consistency)

        # ── Step 11: Export gate ──
        review_records = [
            {"phase": "stem_blueprint_gate", "status": gate_result.get("status", "unknown")},
            {"phase": "solver_verify", "status": verify_result.get("status", "unknown")},
            {"phase": "final_review", "status": final_review.get("status", "unknown")},
        ]
        export_gate = can_export(final_question, review_records, consistency)
        final_question["export_status"] = "exported" if export_gate["allowed"] else "blocked"
        final_question["block_reasons"] = export_gate["block_reasons"]

        if self.debugger:
            self.debugger.dump_full_run(slot_id, final_question, solver_dict,
                                        review, total_time, rnd + 1)

        logger.info("[%s] Unified pipeline done in %.1fs (%d rounds, type=%s, export=%s)",
                     slot_id, total_time, rnd + 1, "SC" if is_sc else "Comp",
                     final_question["export_status"])

        return UnifiedPipelineResult(
            final_question=final_question,
            solver_result=solver_dict,
            review=review,
            generation_time_s=round(total_time, 1),
            pipeline_type="unified_sc" if is_sc else "unified_comp",
        )

    # ── Gates ───────────────────────────────────────────────────

    async def _run_gates(
        self,
        design: Dict[str, Any],
        slot_blueprint: Dict[str, Any],
        slot_id: str,
        gateway,
    ):
        """Run Knowledge Gate then Environment Closure Gate."""
        from core_new.agents.gate_agents import run_gates

        stem = design.get("stem", "")
        if not stem:
            logger.warning("[%s] No stem to review, skipping gates", slot_id)
            from core_new.gate_protocol import GateResult
            return None, GateResult(gate_name="environment_closure")

        slot_intent = json.dumps(slot_blueprint.get("primary_knowledge", []), ensure_ascii=False)
        outline_scope = slot_blueprint.get("slot_guidance", "")
        question_prompt = design.get("question_prompt", "")

        return await run_gates(
            gateway,
            slot_intent=slot_intent,
            outline_scope=outline_scope,
            knowledge_terms_or_stem=stem,
            stem=stem,
            question_prompt=question_prompt,
            slot_id=slot_id,
        )

    async def _run_stem_blueprint_gate(
        self,
        design: Dict[str, Any],
        options: Optional[Dict[str, Any]],
        slot_blueprint: Dict[str, Any],
        question_design: Optional[Dict[str, Any]],
        experience_card: str,
        slot_id: str,
        gateway,
    ) -> Dict[str, Any]:
        """Pre-solve gate: validate stem + blueprint compliance."""
        from core_new.agents.stem_blueprint_gate import StemBlueprintGateAgent

        stem = design.get("stem", "")
        if not stem:
            logger.warning("[%s] No stem to gate-review", slot_id)
            return {"status": "needs_fix", "severity": "high", "fix_target": "stem"}

        initial = {
            "stem": stem,
            "blueprint": slot_blueprint,
            "question_design": question_design or design,
            "experience_radar": experience_card,
        }
        if options:
            initial["options"] = options

        bb = Blackboard(
            task_id=f"gate_{slot_id}",
            task_type="gate",
            initial_state=initial,
        )
        agent = StemBlueprintGateAgent(_rgw("gate"))
        record = await agent.execute(bb)
        if record.error:
            logger.warning("[%s] StemBlueprintGate agent error: %s", slot_id, record.error)
            return {"status": "needs_fix", "severity": "high", "note": f"gate_error: {record.error}"}

        result = bb.get("stem_blueprint_gate_result", {})
        logger.info("[%s] StemBlueprintGate: status=%s severity=%s",
                    slot_id, result.get("status"), result.get("severity"))
        return result

    async def _run_solver_verify(
        self,
        design: Dict[str, Any],
        options: Optional[Dict[str, Any]],
        solver_dict: Dict[str, Any],
        question_design: Optional[Dict[str, Any]],
        is_sc: bool,
        slot_id: str,
        gateway,
        *,
        slot_blueprint: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Post-solve verify: is the solver result trustworthy?"""
        from core_new.agents.solver_verify import SolverVerifyAgent

        stem = design.get("stem", "")
        if not stem or not solver_dict:
            logger.warning("[%s] No stem or solver result to verify", slot_id)
            return {
                "status": "needs_fix",
                "trusted": "false",
                "fix_target": "solver",
                "overall_quality": 2,
                "note": "verify_missing_input",
            }

        initial = {
            "stem": stem,
            "solver_result": solver_dict,
            "question_design": question_design or design,
            "question_type": "single_choice" if is_sc else "comprehensive",
        }
        if options:
            initial["options"] = options
        if slot_blueprint:
            initial["blueprint"] = slot_blueprint

        bb = Blackboard(
            task_id=f"verify_{slot_id}",
            task_type="verify",
            initial_state=initial,
        )
        agent = SolverVerifyAgent(_rgw("verify"))
        record = await agent.execute(bb)
        if record.error:
            logger.warning("[%s] SolverVerify agent error: %s", slot_id, record.error)
            return {
                "status": "needs_fix",
                "trusted": "false",
                "fix_target": "solver",
                "overall_quality": 1,
                "note": f"verify_agent_error: {record.error}",
            }

        result = bb.get("solver_verify_result", {})
        logger.info("[%s] SolverVerify: status=%s trusted=%s",
                    slot_id, result.get("status"), result.get("trusted"))
        return result

    async def _run_final_review(
        self,
        design: Dict[str, Any],
        options: Optional[Dict[str, Any]],
        solution: Dict[str, Any],
        solver_dict: Dict[str, Any],
        is_sc: bool,
        slot_id: str,
        gateway,
    ) -> Dict[str, Any]:
        """Run comprehensive final review on pipeline output."""
        parts = []
        if design:
            parts.append(f"### 题干\n{design.get('stem', '')}")
        if options and is_sc:
            parts.append(f"### 选项\n{options}")
        if solution:
            parts.append(f"### 解答\n{solution}")

        initial = {
            "content_to_review": "\n\n".join(parts),
            "sc_design": design,
            "sc_options_result": options,
            "sc_solution_result": solution,
            "solver_result": solver_dict,
            "is_sc": is_sc,
        }
        bb = Blackboard(
            task_id=f"final_review_{slot_id}",
            task_type="final_review",
            initial_state=initial,
        )

        agent = FinalReviewAgent(_rgw("final_review"))
        record = await agent.execute(bb)
        if record.error:
            return {"status": "error", "overall_quality": 0, "issues": record.error, "fix_instruction": {"fix_target": "none", "fix_detail": ""}}
        parsed = bb.get("final_review")
        if isinstance(parsed, dict) and parsed:
            return parsed
        return {
            "status": "needs_human_review",
            "overall_quality": 0,
            "issues": "FinalReview output unparseable",
            "fix_instruction": {"fix_target": "none", "fix_detail": "终审输出无法解析，需要人工复核"},
        }

    async def _run_final_fixer(
        self,
        design: Dict[str, Any],
        options: Optional[Dict[str, Any]],
        solution: Dict[str, Any],
        solver_dict: Dict[str, Any],
        review_result: Dict[str, Any],
        is_sc: bool,
        slot_id: str,
        gateway,
    ) -> Dict[str, Any]:
        """Run targeted fixer based on final review feedback."""
        fix_instruction = review_result.get("fix_instruction", {})
        fix_target = fix_instruction.get("fix_target", "none")
        fix_detail = fix_instruction.get("fix_detail", "")

        if fix_target == "none":
            if review_result.get("status") == "needs_fix":
                logger.warning(
                    "[%s] FinalReview needs_fix but fix_target=none, needs human review",
                    slot_id,
                )
                return {
                    "status": "needs_human_review",
                    "fix_applied": "FinalReview reported needs_fix but fix_target=none",
                    "reason": "invalid_review_contract",
                }
            return {"status": "skipped"}

        initial = {
            "sc_design": design,
            "sc_options_result": options,
            "sc_solution_result": solution,
            "solver_result": solver_dict,
            "final_review_result": review_result,
            "is_sc": is_sc,
        }
        bb = Blackboard(
            task_id=f"final_fixer_{slot_id}",
            task_type="final_fixer",
            initial_state=initial,
        )

        agent = FinalFixerAgent(_rgw("final_fixer"))
        record = await agent.execute(bb)
        if record.error:
            return {"status": "error", "fix_applied": record.error}
        parsed = bb.get("final_fixer")
        if isinstance(parsed, dict) and parsed:
            return parsed
        return {"status": "failed", "fix_applied": "no output"}

    @staticmethod
    def _safe_parse(text: str) -> Dict[str, Any]:
        """Safely parse JSON string, returning empty dict on failure."""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return {}

    # ── Step methods ───────────────────────────────────────────

    async def _design_sc(
        self,
        blueprint: Dict[str, Any],
        experience_card: str,
        gateway,
        stem_fix_instruction: Optional[str] = None,
        round_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """SC Step 1: generate question stem."""
        def make_blackboard() -> Blackboard:
            initial = {
                "current_blueprint": blueprint,
                "experience_card": experience_card,
            }
            if stem_fix_instruction:
                initial["stem_fix_instruction"] = stem_fix_instruction
            return Blackboard(
                task_id=f"sc_design_{blueprint.get('slot_id', 'unknown')}",
                task_type="unified_sc",
                initial_state=initial,
            )

        bb = make_blackboard()
        if self.use_runtime_sc_design:
            runtime_agent = RuntimeSingleChoiceDraftAgent(_rgw("sc_draft"))
            if round_history:
                runtime_agent.set_memory(round_history)
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

        agent = SingleChoiceDraftAgent(_rgw("sc_draft"))
        if round_history:
            agent.set_memory(round_history)
        record = None
        for attempt in range(5):
            record = await agent.execute(bb)
            if not record.error:
                break
            logger.warning("[SC design] Error (attempt %d/5): %s",
                           attempt + 1, str(record.error)[:200])
            if attempt < 4:
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
            raise RuntimeError(
                f"SC design failed (agent error: {record.error}). "
                f"Fallback={fb_result.fallback_target} did not produce usable output."
            )

        result = bb.get("sc_draft_result", {})
        self._require_step_fields("SC design", result, ["stem"])
        logger.info("[SC design] stem=%s", str(result.get("stem", ""))[:80])
        return result

    async def _design_comp(
        self,
        blueprint: Dict[str, Any],
        experience_card: str,
        gateway,
        stem_fix_instruction: Optional[str] = None,
        round_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Comp Step 1: generate question design with sub-questions and intent."""
        initial = {
            "current_blueprint": blueprint,
            "experience_card": experience_card,
            "reference_questions": experience_card,
        }
        if stem_fix_instruction:
            initial["stem_fix_instruction"] = stem_fix_instruction
        bb = Blackboard(
            task_id=f"comp_design_{blueprint.get('slot_id', 'unknown')}",
            task_type="unified_comp",
            initial_state=initial,
        )
        agent = QuestionDesignerAgent(_rgw("design_comp"))
        if round_history:
            agent.set_memory(round_history)
        record = None
        result = {}
        for attempt in range(5):
            record = await agent.execute(bb)
            if not record.error:
                result = bb.get("question_design", {})
                missing = [f for f in ("stem", "sub_questions") if not result.get(f)]
                if not missing:
                    break
                logger.warning("[Comp design] Incomplete output (attempt %d/5), missing: %s",
                               attempt + 1, ", ".join(missing))
                if attempt < 4:
                    await asyncio.sleep(15)
                    continue
            else:
                logger.warning("[Comp design] Error (attempt %d/5): %s",
                               attempt + 1, str(record.error)[:200])
                if attempt < 4:
                    await asyncio.sleep(15)
                    continue
            break

        if record and record.error:
            bb_data = bb.get_relevant_state(agent.config.name)
            fb_result = await self.fallback_executor.try_fallback(record, bb_data)
            if fb_result.used_fallback and not fb_result.error:
                logger.info("[Comp design] Fallback succeeded: %s", fb_result.fallback_target)
                if fb_result.fallback_target in ("human_review", "needs_human_check"):
                    return {"status": "needs_human_review",
                            "reason": fb_result.result_data.get("reason", "Comp design failed, routed to human review"),
                            "fallback_target": fb_result.fallback_target}
            raise RuntimeError(
                f"Comp design failed (agent error: {record.error}). "
                f"Fallback={fb_result.fallback_target} did not produce usable output."
            )

        self._require_step_fields("Comp design", result, ["stem", "sub_questions"])
        logger.info("[Comp design] stem=%s", str(result.get("stem", ""))[:80])
        return result

    async def _generate_options(
        self,
        design: Dict[str, Any],
        blueprint: Dict[str, Any],
        gateway,
        round_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """SC Step 2: generate 4 options with distractor intent."""
        initial = {
            "sc_draft_result": design,
            "current_blueprint": blueprint,
        }
        bb = Blackboard(
            task_id=f"sc_opts_{blueprint.get('slot_id', 'unknown')}",
            task_type="unified_sc",
            initial_state=initial,
        )
        agent = OptionAndDistractorAgent(_rgw("options"))
        if round_history:
            agent.set_memory(round_history)
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

    async def _verify_stem(
        self,
        design: Dict[str, Any],
        options: Optional[Dict[str, Any]],
        question_design: Optional[Dict[str, Any]],
        is_sc: bool,
        slot_id: str,
        gateway,
    ) -> Dict[str, Any]:
        """Step 2.5: Stem verification — check conditions before solving."""
        initial = {
            "sc_draft_result": design,
            "question_design": question_design or {},
        }
        if is_sc and options:
            initial["sc_options_result"] = options

        bb = Blackboard(
            task_id=f"stem_verify_{slot_id}",
            task_type="stem_verification",
            initial_state=initial,
        )
        agent = StemVerifierAgent(_rgw("stem_verify"))
        record = await agent.execute(bb)
        if record.error:
            logger.warning("[%s] Stem verification agent error: %s", slot_id, record.error)
            return {"status": "needs_fix", "note": f"verification_error: {record.error}"}
        result = bb.get("stem_verification_result", {})
        # Attach raw review text for conversation-style fix
        if hasattr(record, 'raw_text') and record.raw_text:
            result["_raw_text"] = record.raw_text
        logger.info("[%s] Stem verification: status=%s", slot_id, result.get("status"))
        return result

    async def _polish_stem_minor(
        self,
        design: Dict[str, Any],
        minor_issues: str,
    ) -> Dict[str, Any]:
        """Polish stem wording for minor issues — single LLM call."""
        if not minor_issues or minor_issues == "无":
            return design

        stem = design.get("stem", "")
        prompt = (
            "以下是一道408考研题的题干。审核发现了一些措辞/术语小问题，请修正。\n"
            "重要约束：只修改措辞和术语，不得改变任何数值、条件或数学内容。\n\n"
            f"## 题干\n{stem}\n\n"
            f"## 需要修正的问题\n{minor_issues}\n\n"
            "请直接输出修正后的题干全文（不输出其他内容）。"
        )

        result = await _rgw("formatter").generate_text(
            [{"role": "user", "content": prompt}],
            max_tokens=4096,
            enable_thinking=False,
        )

        if result.ok and result.content and len(result.content.strip()) > 20:
            design = dict(design)
            design["stem"] = result.content.strip()
            design["stem_polished_for_minor"] = True
            logger.info("[Stem polish] Applied minor fixes: %d -> %d chars",
                        len(stem), len(design["stem"]))
        return design

    async def _solve(
        self,
        design: Dict[str, Any],
        options: Optional[Dict[str, Any]],
        is_sc: bool,
        slot_id: str,
        gateway,
    ) -> CodeSolution:
        """Step 3: Solve — pure computation engine (runtime or text-parsing)."""
        if self.use_runtime_solver:
            solver = RuntimeFileCodeSolver(_rgw("solver"), max_tokens=16384, max_iterations=8)
        else:
            solver = FileCodeSolverAgent(_rgw("solver"), max_tokens=16384, max_steps=5)

        question_text = design.get("stem", "")

        if is_sc and options:
            options_dict = {
                "A": options.get("option_A", ""),
                "B": options.get("option_B", ""),
                "C": options.get("option_C", ""),
                "D": options.get("option_D", ""),
            }
            result = await solver.solve(
                question_draft=question_text,
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
                question_draft=question_text,
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
        solver_dict: Dict[str, Any],
        gateway,
    ) -> Dict[str, Any]:
        """SC Step 4: format solution from solver verification result."""
        bb = Blackboard(
            task_id=f"sc_format_{design.get('slot_id', 'unknown')}",
            task_type="unified_sc",
            initial_state={
                "sc_draft_result": design,
                "sc_options_result": options,
                "sc_solver_result": solver_dict,
            },
        )
        agent = SCSolutionFormatterAgent(_rgw("formatter"))
        record = await agent.execute(bb)
        self._raise_if_failed("SC format", record)
        result = bb.get("sc_solution_result", {})
        self._require_step_fields("SC format", result, ["correct_answer", "explanation"])
        return result

    async def _format_comp(
        self,
        design: Dict[str, Any],
        solver_dict: Dict[str, Any],
        gateway,
    ) -> Dict[str, Any]:
        """Comp Step 4: format solution from solver output."""
        bb = Blackboard(
            task_id=f"comp_format_{design.get('slot_id', 'unknown')}",
            task_type="unified_comp",
            initial_state={
                "question_design": design,
                "solver_result": solver_dict,
            },
        )
        agent = HybridSolutionFormatter(_rgw("formatter"))
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
            task_id=f"comp_rubric_{design.get('slot_id', 'unknown')}",
            task_type="unified_comp",
            initial_state={
                "question_design": design,
                "formatted_solution": solution,
                "current_blueprint": blueprint,
            },
        )
        agent = HybridRubricWriter(_rgw("rubric"))
        await agent.execute(bb)
        return bb.get("rubric", {})

    async def _post_review(
        self,
        design: Dict[str, Any],
        options: Dict[str, Any],
        solution: Dict[str, Any],
        solver_dict: Dict[str, Any],
        review: Dict[str, Any],
        question_design: Optional[Dict[str, Any]],
        is_sc: bool,
        slot_id: str,
        gateway,
        *,
        slot_blueprint: Optional[Dict[str, Any]] = None,
        experience_card: str = "",
    ) -> Dict[str, Any]:
        """Step 7: Post-review — blueprint-driven compliance check."""
        initial = {
            "sc_draft_result": design,
            "sc_solution_result": solution,
            "review": review,
            "solver_result": solver_dict,
            "is_sc": is_sc,
            "question_design": question_design or design,
        }
        if is_sc:
            initial["sc_options_result"] = options
        if slot_blueprint:
            initial["slot_blueprint"] = slot_blueprint
        if experience_card:
            initial["experience_card"] = experience_card

        bb = Blackboard(
            task_id=f"post_review_{slot_id}",
            task_type="post_review",
            initial_state=initial,
        )
        agent = PostReviewAgent(_rgw("post_review"))
        record = await agent.execute(bb)
        if record.error:
            logger.warning("[%s] Post-review agent error: %s", slot_id, record.error)
            return {"status": "needs_fix", "note": f"post_review_error: {record.error}"}
        result = bb.get("post_review_result", {})
        logger.info("[%s] Post-review: status=%s quality=%s",
                    slot_id, result.get("status"), result.get("overall_quality"))
        return result

    async def _summarize(
        self,
        design: Dict[str, Any],
        options: Dict[str, Any],
        solution: Dict[str, Any],
        solver_dict: Dict[str, Any],
        review: Dict[str, Any],
        post_review: Dict[str, Any],
        is_sc: bool,
        slot_id: str,
        gateway,
    ) -> Dict[str, Any]:
        """Step 8: Summary — consolidate all outputs into final structured result."""
        initial = {
            "sc_draft_result": design,
            "sc_solution_result": solution,
            "solver_result": solver_dict,
            "review": review,
            "post_review_result": post_review,
            "is_sc": is_sc,
        }
        if is_sc:
            initial["sc_options_result"] = options

        bb = Blackboard(
            task_id=f"summary_{slot_id}",
            task_type="summary",
            initial_state=initial,
        )
        agent = QuestionSummaryAgent(_rgw("summary"))
        record = await agent.execute(bb)
        if record.error:
            logger.warning("[%s] Summary failed: %s, using assemble fallback", slot_id, record.error)
            return None
        result = bb.get("question_summary", {})
        logger.info("[%s] Summary done: %d fields", slot_id, len(result))
        return result

    async def _review(
        self,
        design: Dict[str, Any],
        options: Dict[str, Any],
        solver_dict: Dict[str, Any],
        solution: Dict[str, Any],
        rubric: Dict[str, Any],
        blueprint: Dict[str, Any],
        is_sc: bool,
        gateway,
        round_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Step 6: review — compare computation vs intent."""
        if is_sc:
            initial_state = {
                "sc_design": design,
                "sc_options": options,
                "solver_result": solver_dict,
                "current_blueprint": blueprint,
            }
            bb = Blackboard(
                task_id=f"sc_review_{blueprint.get('slot_id', 'unknown')}",
                task_type="unified_sc",
                initial_state=initial_state,
            )
            reviewer = UnifiedSCReviewer(_rgw("review"))
        else:
            initial_state = {
                "question_design": design,
                "formatted_solution": solution,
                "rubric": rubric,
                "current_blueprint": blueprint,
            }
            bb = Blackboard(
                task_id=f"comp_review_{blueprint.get('slot_id', 'unknown')}",
                task_type="unified_comp",
                initial_state=initial_state,
            )
            reviewer = IntentBasedReviewer(_rgw("review"))
        if round_history:
            reviewer.set_memory(round_history)

        # Append Gate 3 restriction instruction when gates were used
        if self.enable_stem_gate:
            from core_new.prompts.gate_prompts import GATE3_RESTRICTION_INSTRUCTION
            reviewer.config.system_prompt = reviewer.config.system_prompt + "\n\n" + GATE3_RESTRICTION_INSTRUCTION

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
        summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Assemble final question dict from pipeline outputs."""
        solver_confidence = "high"
        if code_solution and (not code_solution.computed_results or code_solution.error):
            solver_confidence = "low"

        # If summary agent produced cleaned output, prefer its fields
        if summary and is_sc:
            return {
                "slot_id": slot_id,
                "stem": summary.get("final_stem", design.get("stem", "")),
                "option_A": summary.get("final_option_A", options.get("option_A", "")),
                "option_B": summary.get("final_option_B", options.get("option_B", "")),
                "option_C": summary.get("final_option_C", options.get("option_C", "")),
                "option_D": summary.get("final_option_D", options.get("option_D", "")),
                "correct_answer": summary.get("correct_answer",
                    solution.get("correct_answer", options.get("correct_answer", ""))),
                "explanation": summary.get("final_explanation", solution.get("explanation", "")),
                "solution_steps": summary.get("final_solution_steps", solution.get("solution_steps", "")),
                "knowledge_tags": summary.get("knowledge_tags", solution.get("knowledge_points", "")),
                "difficulty_summary": summary.get("difficulty_summary", ""),
                "quality_notes": summary.get("quality_notes", ""),
                "solver_confidence": solver_confidence,
                "python_exec_count": code_solution.python_exec_count if code_solution else 0,
                "code_files": code_solution.code_files if code_solution else [],
                "pipeline_type": "unified_sc",
            }

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
