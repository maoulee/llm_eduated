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
from core_new.blackboard import Blackboard
from core_new.fallback_executor import FallbackExecutor, FallbackResult
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
        enable_architecture: bool = True,
        enable_post_review: bool = True,
        enable_summary: bool = True,
    ):
        self.max_revision_rounds = max_revision_rounds
        self.use_runtime_sc_design = use_runtime_sc_design
        self.runtime_fallback = runtime_fallback
        self.enable_architecture = enable_architecture
        self.enable_post_review = enable_post_review
        self.enable_summary = enable_summary
        self.enable_stem_gate = enable_stem_gate
        self.use_runtime_solver = use_runtime_solver
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
        stem_fix_instruction: Optional[str] = None

        # Step 0: Architecture — design question structure from slot philosophy
        question_design = None
        if self.enable_architecture:
            question_design = await self._run_architecture(
                slot_blueprint, experience_card, gateway,
            )

        for rnd in range(self.max_revision_rounds + 1):
            if rnd > 0:
                logger.info("[%s] Revision round %d, fix_target=%s",
                            slot_id, rnd, fix_target)

            # ── Step 1: Design ──
            need_design = rnd == 0 or fix_target in ("question", "stem")
            if need_design:
                if is_sc:
                    design = await self._design_sc(
                        slot_blueprint, experience_card, gateway,
                        question_design=question_design,
                        stem_fix_instruction=stem_fix_instruction,
                    )
                else:
                    design = await self._design_comp(
                        slot_blueprint, experience_card, gateway,
                        question_design=question_design,
                        stem_fix_instruction=stem_fix_instruction,
                    )
                if not design:
                    logger.error("[%s] Design produced empty result", slot_id)
                    break
                if design.get("status") in {"needs_human_review", "needs_human_check"}:
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

            # ── Step 1.5: Gates (Knowledge + Environment Closure, if enabled) ──
            knowledge_gate_result = None
            environment_gate_result = None
            if self.enable_stem_gate and need_design:
                knowledge_gate_result, environment_gate_result = await self._run_gates(
                    design, slot_blueprint, slot_id, gateway,
                )
                blocked_gate = None
                if knowledge_gate_result and knowledge_gate_result.blocked:
                    blocked_gate = knowledge_gate_result
                elif environment_gate_result and environment_gate_result.blocked:
                    blocked_gate = environment_gate_result

                if blocked_gate:
                    logger.warning(
                        "[%s] Gate BLOCKED (%s): %s",
                        slot_id,
                        blocked_gate.gate_name,
                        blocked_gate.summary[:200],
                    )
                    fix_target = "stem"
                    if rnd >= self.max_revision_rounds:
                        logger.warning("[%s] Gate blocked, revision budget exhausted", slot_id)
                        break
                    continue
                logger.info("[%s] Gates PASSED", slot_id)

            # ── Step 2: Options (SC only) ──
            need_options = is_sc and (rnd == 0 or fix_target in ("question", "options"))
            if need_options:
                options = await self._generate_options(design, slot_blueprint, gateway,
                                                        question_design=question_design)

            # ── Step 2.5: Stem verification (before solving) ──
            need_stem_verify = (rnd == 0 or fix_target in ("question", "stem"))
            if need_stem_verify:
                stem_verification = await self._verify_stem(
                    design, options if is_sc else None,
                    question_design, is_sc, slot_id, gateway,
                )
                if stem_verification.get("status") == "needs_fix":
                    fix_target = "stem"
                    fix_detail = stem_verification.get("fix_detail", "")
                    contradiction = stem_verification.get("contradiction_detail", "")
                    parts = [p for p in [fix_detail, contradiction] if p and p != "无"]
                    stem_fix_instruction = "；".join(parts)
                    logger.info("[%s] Stem verification failed, routing to stem redesign: %s",
                                slot_id, stem_fix_instruction[:200])
                    if rnd >= self.max_revision_rounds:
                        logger.warning("[%s] Stem verification failed, revision budget exhausted", slot_id)
                        break
                    continue

            # ── Step 3: Solve (unified computation) ──
            need_solve = rnd == 0 or fix_target in ("question", "options", "answer")
            if need_solve:
                code_solution = await self._solve(
                    design, options if is_sc else None, is_sc, slot_id, gateway,
                )
                solver_dict = code_solution.to_dict() if code_solution else {}

            # ── Step 4: Format solution ──
            need_format = rnd == 0 or fix_target in ("question", "options", "answer")
            if need_format:
                if is_sc:
                    solution = await self._format_sc(
                        design, options, solver_dict, gateway,
                    )
                else:
                    solution = await self._format_comp(design, solver_dict, gateway)

            # ── Step 5: Rubric (Comp only) ──
            if not is_sc and need_format:
                rubric = await self._write_rubric(
                    design, solution, slot_blueprint, gateway,
                )

            # ── Step 6: Review ──
            review = await self._review(
                design, options, solver_dict, solution, rubric,
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

        # ── Step 7: Post-review (final quality check) ──
        post_review = {}
        if self.enable_post_review:
            post_review = await self._post_review(
                design, options, solution, solver_dict, review, question_design,
                is_sc, slot_id, gateway,
            )

        # ── Step 8: Summary (consolidate all outputs) ──
        summary = {}
        if self.enable_summary:
            summary = await self._summarize(
                design, options, solution, solver_dict, review, post_review,
                is_sc, slot_id, gateway,
            )

        # ── Assemble final result ──
        total_time = time.monotonic() - total_start
        final_question = self._assemble(
            slot_id, design, options, code_solution, solution, rubric, is_sc,
            summary=summary,
        )

        final_question["post_review"] = post_review
        if summary:
            final_question["summary"] = summary

        logger.info("[%s] Unified pipeline done in %.1fs (%d rounds, type=%s)",
                     slot_id, total_time, rnd + 1, "SC" if is_sc else "Comp")

        kgr_dict = knowledge_gate_result.to_dict() if knowledge_gate_result else None
        egr_dict = environment_gate_result.to_dict() if environment_gate_result else None

        return UnifiedPipelineResult(
            final_question=final_question,
            solver_result=solver_dict,
            review=review,
            generation_time_s=round(total_time, 1),
            pipeline_type="unified_sc" if is_sc else "unified_comp",
            knowledge_gate_result=kgr_dict,
            environment_gate_result=egr_dict,
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

    # ── Step methods ───────────────────────────────────────────

    async def _run_architecture(
        self,
        blueprint: Dict[str, Any],
        experience_card: str,
        gateway,
    ) -> Dict[str, Any]:
        """Step 0: ArchitectureAgent — design question structure from slot philosophy."""
        from core_new.agents.architecture_agent import ArchitectureAgent
        from core_new.pattern_cards import SlotMeta

        slot_id = blueprint.get("slot_id", "Q1")
        slot = SlotMeta.load(slot_id)
        if not slot:
            logger.warning("[%s] No slot content found, skipping architecture step", slot_id)
            return {}

        agent = ArchitectureAgent(gateway)
        bb = Blackboard(
            task_id=f"arch_{slot_id}",
            task_type="architecture",
            initial_state={
                "slot_id": slot_id,
                "slot_meta": slot,
                "blueprint": blueprint,
                "knowledge_point": blueprint.get("primary_target_name", ""),
            },
        )

        record = await agent.execute(bb)
        if record.error:
            logger.warning("[%s] Architecture step failed: %s", slot_id, record.error)
            return {}

        question_design = bb.get("question_design", {})
        logger.info("[%s] Architecture done: %d chars", slot_id,
                    len(question_design.get("raw_design_md", "")))
        return question_design

    async def _design_sc(
        self,
        blueprint: Dict[str, Any],
        experience_card: str,
        gateway,
        question_design: Optional[Dict[str, Any]] = None,
        stem_fix_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """SC Step 1: generate question stem."""
        def make_blackboard() -> Blackboard:
            initial = {
                "current_blueprint": blueprint,
                "experience_card": experience_card,
            }
            if question_design:
                initial["question_design"] = question_design
            if stem_fix_instruction:
                initial["stem_fix_instruction"] = stem_fix_instruction
            return Blackboard(
                task_id=f"sc_design_{blueprint.get('slot_id', 'Q1')}",
                task_type="unified_sc",
                initial_state=initial,
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
        question_design: Optional[Dict[str, Any]] = None,
        stem_fix_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Comp Step 1: generate question design with sub-questions and intent."""
        initial = {
            "current_blueprint": blueprint,
            "experience_card": experience_card,
            "reference_questions": experience_card,
        }
        if question_design:
            initial["question_design"] = question_design
        if stem_fix_instruction:
            initial["stem_fix_instruction"] = stem_fix_instruction
        bb = Blackboard(
            task_id=f"comp_design_{blueprint.get('slot_id', 'Q43')}",
            task_type="unified_comp",
            initial_state=initial,
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
            raise RuntimeError(
                f"Comp design failed (agent error: {record.error}). "
                f"Fallback={fb_result.fallback_target} did not produce usable output."
            )

        result = bb.get("question_design", {})
        self._require_step_fields("Comp design", result, ["stem", "sub_questions"])
        logger.info("[Comp design] stem=%s", str(result.get("stem", ""))[:80])
        return result

    async def _generate_options(
        self,
        design: Dict[str, Any],
        blueprint: Dict[str, Any],
        gateway,
        question_design: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """SC Step 2: generate 4 options with distractor intent."""
        initial = {
            "sc_draft_result": design,
            "current_blueprint": blueprint,
        }
        if question_design:
            initial["question_design"] = question_design
        bb = Blackboard(
            task_id=f"sc_opts_{blueprint.get('slot_id', 'Q1')}",
            task_type="unified_sc",
            initial_state=initial,
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
        agent = StemVerifierAgent(gateway)
        record = await agent.execute(bb)
        if record.error:
            logger.warning("[%s] Stem verification failed: %s, proceeding anyway",
                           slot_id, record.error)
            return {"status": "pass", "note": "verification_skipped"}
        result = bb.get("stem_verification_result", {})
        logger.info("[%s] Stem verification: status=%s", slot_id, result.get("status"))
        return result

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
            solver = RuntimeFileCodeSolver(gateway, max_tokens=4096, max_iterations=8)
        else:
            solver = FileCodeSolverAgent(gateway, max_tokens=16384, max_steps=5)

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
        solver_dict: Dict[str, Any],
        gateway,
    ) -> Dict[str, Any]:
        """Comp Step 4: format solution from solver output."""
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
    ) -> Dict[str, Any]:
        """Step 7: Post-review — final quality check on complete question."""
        initial = {
            "sc_draft_result": design,
            "sc_solution_result": solution,
            "review": review,
            "solver_result": solver_dict,
        }
        if question_design:
            initial["question_design"] = question_design
        if is_sc:
            initial["sc_options_result"] = options

        bb = Blackboard(
            task_id=f"post_review_{slot_id}",
            task_type="post_review",
            initial_state=initial,
        )
        agent = PostReviewAgent(gateway)
        record = await agent.execute(bb)
        if record.error:
            logger.warning("[%s] Post-review failed: %s, proceeding", slot_id, record.error)
            return {"status": "pass", "note": "post_review_skipped"}
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
        }
        if is_sc:
            initial["sc_options_result"] = options

        bb = Blackboard(
            task_id=f"summary_{slot_id}",
            task_type="summary",
            initial_state=initial,
        )
        agent = QuestionSummaryAgent(gateway)
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
                task_id=f"sc_review_{blueprint.get('slot_id', 'Q1')}",
                task_type="unified_sc",
                initial_state=initial_state,
            )
            reviewer = UnifiedSCReviewer(gateway)
        else:
            initial_state = {
                "question_design": design,
                "formatted_solution": solution,
                "rubric": rubric,
                "current_blueprint": blueprint,
            }
            bb = Blackboard(
                task_id=f"comp_review_{blueprint.get('slot_id', 'Q43')}",
                task_type="unified_comp",
                initial_state=initial_state,
            )
            reviewer = IntentBasedReviewer(gateway)

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
