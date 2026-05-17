"""Hybrid Subjective Pipeline — question designer + CodeAct solver + intent review.

Architecture:
  1. QuestionDesigner → question + design intent (no answer)
  2. CodeActSolver → solve via Python execution (single path)
  3. Solution formatter → merge solver output into explanation
  4. Rubric writer → grading rubric
  5. Intent-based reviewer → compare design intent vs solver results
     - design mismatch → regenerate question
     - answer error → regenerate answer only
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
from core_new.agent_roles import AuditMode, RoleType
from core_new.audit_protocol import AuditResultNormalizer, FixRouter
from core_new.agents.file_code_solver import FileCodeSolverAgent, CodeSolution
from core_new.agents.agent_registry import AgentRegistry
from core_new.blackboard import Blackboard
from core_new.experience_view import build_design_experience_view
from core_new.markdown_parser import try_parse_json_object

logger = logging.getLogger(__name__)


# ── Markdown parsing ──────────────────────────────────────────


def _parse_md_kv(lines: List[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    current_key = None
    for line in lines:
        # Match: - **key**: value  or  - **key**：value  or  - key: value
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
    name = None
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


def _fuzzy_get(d: Dict[str, Any], *keys) -> Any:
    """Get value from dict with fuzzy key matching (handles Chinese variants)."""
    for key in keys:
        if key in d:
            return d[key]
    # Fallback: case-insensitive substring match
    keys_lower = [k.lower() for k in keys]
    for k, v in d.items():
        kl = k.lower()
        for target in keys_lower:
            if target in kl or kl in target:
                return v
    return None


# ── Step 1: Question Designer ────────────────────────────────


class QuestionDesignerAgent(BaseAgent):
    """Design question with explicit intent — what each sub-question tests,
    expected solving path, trap design, sub-question logic."""

    def __init__(self, llm_backend, *, max_tokens: int = 2048):
        super().__init__(
            AgentConfig(
                name="question_designer",
                phase="design",
                output_format="markdown",
                output_key="question_design",
                max_tokens=max_tokens,
                enable_thinking=True,
                timeout_s=300.0,
                max_retries=2,
                required_fields=["stem", "sub_questions"],
                repair_max_retries=1,
                role_type=RoleType.GENERATOR,
                expected_output_format=(
                    "# question Qxx\n\n"
                    "## 题目\n"
                    "- **stem**: ...\n"
                    "- **sub_questions**: [\"...\", \"...\"]\n"
                    "- **given_conditions**: [\"...\"]\n"
                    "- **difficulty_self_assessment**: 1-5\n"
                    "- **knowledge_points**: ...\n"
                    "- **parameter_notes**: ...\n\n"
                    "## 设计意图\n"
                    "- **sub_q1_intent**: ...\n"
                    "- **trap_design**: ...\n"
                    "- **sub_question_logic**: ..."
                ),
                system_prompt="你是一位408考研出题专家，擅长按照蓝图精确设计综合应用题。你必须写清设计意图，但不写答案。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import SUBJECTIVE_DRAFT_ONLY_PROMPT

        blueprint = blackboard.get("current_blueprint", {})
        slot_id = blueprint.get("slot_id", "Q43")
        exp_card = build_design_experience_view(blackboard.read("experience_card", ""))
        ref_questions = build_design_experience_view(blackboard.read("reference_questions", ""))

        return SUBJECTIVE_DRAFT_ONLY_PROMPT.format(
            slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            experience_card_md=exp_card,
            reference_questions=ref_questions,
            slot_id=slot_id,
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        data = try_parse_json_object(text)
        if data:
            result = {}
            question = data.get("question")
            if isinstance(question, dict):
                result.update(question)
            else:
                result.update(data)
            intent = data.get("design_intent")
            if isinstance(intent, dict):
                result["design_intent"] = intent
                for key in ("sub_q1_intent", "sub_q2_intent", "sub_q3_intent",
                            "trap_design", "sub_question_logic"):
                    if key in intent:
                        result[key] = intent[key]
            return result
        sections = _parse_md_sections(text)
        result: Dict[str, Any] = {}

        if "题目" in sections:
            result.update(sections["题目"])

        if "设计意图" in sections:
            result["design_intent"] = sections["设计意图"]

        intent = result.get("design_intent", {})
        for key in ("sub_q1_intent", "sub_q2_intent", "sub_q3_intent",
                     "trap_design", "sub_question_logic"):
            if key in intent:
                result[key] = intent[key]

        m = re.match(r"#\s+question\s+(Q\d+)", text)
        if m:
            result["slot_id"] = m.group(1)

        return result

    def validate_parsed(self, parsed: Any) -> tuple[bool, str]:
        ok, detail = super().validate_parsed(parsed)
        if not ok:
            return ok, detail
        stem = str(parsed.get("stem", ""))
        if "```" in stem or re.search(r"\b(int\s+main|#include|def\s+\w+\(|print\s*\()", stem):
            return False, "stem appears to contain copied code instead of a question stem"
        sub_questions = parsed.get("sub_questions")
        if isinstance(sub_questions, str):
            try:
                sub_questions = json.loads(sub_questions)
            except json.JSONDecodeError:
                sub_questions = [sub_questions] if sub_questions.strip() else []
        if not isinstance(sub_questions, list) or not sub_questions:
            return False, "sub_questions must be a non-empty list or parseable JSON array"
        return True, ""


# ── Step 3: Solution formatter ────────────────────────────────


class HybridSolutionFormatter(BaseAgent):
    """Format solution from solver output — no re-solving."""

    def __init__(self, llm_backend, *, max_tokens: int = 2048):
        super().__init__(
            AgentConfig(
                name="subjective_solution_formatter",
                phase="format_solution",
                output_format="markdown",
                output_key="formatted_solution",
                max_tokens=max_tokens,
                enable_thinking=True,
                required_fields=["answers"],
                repair_max_retries=1,
                role_type=RoleType.SUMMARIZER,
                system_prompt="你是一位408考研解题专家，擅长根据计算结果整理标准答案。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import SUBJECTIVE_SOLUTION_FORMATTER_PROMPT

        question = blackboard.get("question_design", {})
        solver_result = blackboard.get("solver_result", {})

        return SUBJECTIVE_SOLUTION_FORMATTER_PROMPT.format(
            question_json=json.dumps(question, ensure_ascii=False, indent=2),
            solver_result_json=json.dumps(solver_result, ensure_ascii=False, indent=2),
            slot_id=question.get("slot_id", "Q43"),
        )

    def parse_output(self, raw: Any) -> Any:
        data = try_parse_json_object(str(raw))
        if data:
            nested = data.get("answers")
            if nested is not None:
                return data
            if isinstance(data.get("solution"), dict):
                return data["solution"]
        sections = _parse_md_sections(str(raw))
        result: Dict[str, Any] = {}
        if "标准答案" in sections:
            result.update(sections["标准答案"])
        answers = {}
        for name, kv in sections.items():
            if re.match(r"第\d+问", name):
                answers[name] = kv
        if answers:
            result["sub_answer_details"] = answers
        return result


# ── Step 4: Rubric writer ─────────────────────────────────────


class HybridRubricWriter(BaseAgent):
    """Write grading rubric."""

    def __init__(self, llm_backend, *, max_tokens: int = 1024):
        super().__init__(
            AgentConfig(
                name="subjective_rubric_writer",
                phase="rubric",
                output_format="markdown",
                output_key="rubric",
                max_tokens=max_tokens,
                enable_thinking=True,
                role_type=RoleType.SUMMARIZER,
                system_prompt="你是一位408考研评分标准制定专家。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import SUBJECTIVE_RUBRIC_PROMPT

        question = blackboard.get("question_design", {})
        solution = blackboard.get("formatted_solution", {})
        blueprint = blackboard.get("current_blueprint", {})

        return SUBJECTIVE_RUBRIC_PROMPT.format(
            question_json=json.dumps(question, ensure_ascii=False, indent=2),
            solution_json=json.dumps(solution, ensure_ascii=False, indent=2),
            slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            slot_id=question.get("slot_id", "Q43"),
        )

    def parse_output(self, raw: Any) -> Any:
        sections = _parse_md_sections(str(raw))
        result: Dict[str, Any] = {}
        if "评分点" in sections:
            result.update(sections["评分点"])
        if "评分说明" in sections:
            result.update(sections["评分说明"])
        return result


# ── Step 5: Intent-based Reviewer ─────────────────────────────


class IntentBasedReviewer(BaseAgent):
    """Review: compare design intent + slot blueprint vs solver results, route fixes."""

    def __init__(self, llm_backend, *, max_tokens: int = 1500):
        super().__init__(
            AgentConfig(
                name="intent_reviewer",
                phase="review",
                output_format="markdown",
                output_key="review",
                max_tokens=max_tokens,
                enable_thinking=True,
                required_fields=["status"],
                repair_max_retries=1,
                role_type=RoleType.AUDIT,
                audit_mode=AuditMode.QUESTION_REVIEW,
                system_prompt="你是一位408考研出题审核专家，负责对比出题意图与解题结果，并对照slot蓝图评估。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import SUBJECTIVE_QUESTION_REVIEW_PROMPT

        question = blackboard.get("question_design", {})
        solution = blackboard.get("formatted_solution", {})
        rubric = blackboard.get("rubric", {})
        blueprint = blackboard.get("current_blueprint", {})

        design_intent = {}
        for key in ("sub_q1_intent", "sub_q2_intent", "sub_q3_intent",
                     "trap_design", "sub_question_logic"):
            val = question.get(key)
            if val:
                design_intent[key] = val
        if "design_intent" in question:
            design_intent.update(question["design_intent"])

        return SUBJECTIVE_QUESTION_REVIEW_PROMPT.format(
            design_intent_json=json.dumps(design_intent, ensure_ascii=False, indent=2),
            question_json=json.dumps(question, ensure_ascii=False, indent=2),
            solution_json=json.dumps(solution, ensure_ascii=False, indent=2),
            rubric_json=json.dumps(rubric, ensure_ascii=False, indent=2),
            slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            slot_id=question.get("slot_id", "Q43"),
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        data = try_parse_json_object(text)
        if data:
            result = {}
            nested_review = data.get("review")
            if isinstance(nested_review, dict):
                result.update(nested_review)
            else:
                result.update(data)
            if isinstance(data.get("fix_instruction"), dict):
                result["fix_instruction"] = data["fix_instruction"]
            if result.get("status"):
                result["status"] = str(result["status"]).lower()
            return result
        sections = _parse_md_sections(text)
        result: Dict[str, Any] = {}

        # Collect from all known section name variants
        for section_key in ("结果", "检查", "修复指令", "修复"):
            for name, kv in sections.items():
                if section_key in name:
                    result.update(kv)

        # Fallback: regex extraction for critical fields if missing
        if "status" not in result:
            m = re.search(r"\*\*status\*\*[:：]\s*(\w+)", text)
            if not m:
                m = re.search(r"status[:：]\s*(\w+)", text, re.IGNORECASE)
            if m:
                result["status"] = m.group(1).strip().lower()

        if "score" not in result:
            m = re.search(r"\*\*score\*\*[:：]\s*(\d+)", text)
            if not m:
                m = re.search(r"score[:：]\s*(\d+)", text, re.IGNORECASE)
            if m:
                result["score"] = int(m.group(1))

        if "needs_fix" not in result:
            m = re.search(r"\*\*needs_fix\*\*[:：]\s*(\w+)", text)
            if not m:
                m = re.search(r"needs.?fix[:：]\s*(\w+)", text, re.IGNORECASE)
            if m:
                result["needs_fix"] = m.group(1).strip().lower()

        if "fix_target" not in result:
            m = re.search(r"\*\*fix_target\*\*[:：]\s*(\w+)", text)
            if not m:
                m = re.search(r"fix.?target[:：]\s*(question|answer|rubric)", text, re.IGNORECASE)
            if m:
                result["fix_target"] = m.group(1).strip().lower()

        if "issue" not in result:
            m = re.search(r"\*\*issue\*\*[:：]\s*(.+?)(?:\n|$)", text)
            if m:
                result["issue"] = m.group(1).strip()

        # If status is revise but fix_target is missing, infer from checks
        if result.get("status") == "revise" and not result.get("fix_target"):
            design_vs_bp = _fuzzy_get(result, "design_vs_blueprint", "design_vs_bp")
            answer_corr = _fuzzy_get(result, "answer_correctness", "answer_corr")
            if design_vs_bp and str(design_vs_bp).lower() == "fail":
                result["fix_target"] = "question"
            elif answer_corr and str(answer_corr).lower() == "fail":
                result["fix_target"] = "answer"
            else:
                result["fix_target"] = "answer"  # default: re-solve

        # Normalize status
        if result.get("status"):
            result["status"] = str(result["status"]).lower()

        return result


# ── Pipeline Orchestrator ─────────────────────────────────────


@dataclass
class HybridSubjectiveResult:
    final_question: Dict[str, Any]
    solver_result: Dict[str, Any]
    formatted_solution: Dict[str, Any]
    rubric: Dict[str, Any]
    review: Dict[str, Any]
    generation_time_s: float
    pipeline_type: str = "hybrid_subjective_v2"


class HybridSubjectivePipeline:
    """Question designer + CodeAct solver + intent review.

    Step 1: QuestionDesigner → question + design intent
    Step 2: CodeActSolver → solve via Python execution
    Step 3: Formatter → create explanation
    Step 4: Rubric writer → grading points
    Step 5: Intent reviewer → compare intent + blueprint vs results, route fixes

    Revision loop:
    - fix_target=question → regenerate question (back to Step 1)
    - fix_target=answer → re-solve only (back to Step 2)
    """

    def __init__(self, *, max_revision_rounds: int = 1):
        self.max_revision_rounds = max_revision_rounds
        self.fix_router = FixRouter(max_revision_rounds=max_revision_rounds)

    async def run(
        self,
        slot_blueprint: Dict[str, Any],
        experience_card: str,
        gateway,
    ) -> HybridSubjectiveResult:
        slot_id = slot_blueprint.get("slot_id", "Q43")
        total_start = time.monotonic()

        design: Dict[str, Any] = {}
        solver_dict: Dict[str, Any] = {}
        solution: Dict[str, Any] = {}
        rubric: Dict[str, Any] = {}
        review: Dict[str, Any] = {}

        for revision_round in range(self.max_revision_rounds + 1):
            if revision_round > 0:
                logger.info("[%s] Revision round %d, fix_target=%s",
                            slot_id, revision_round, review.get("fix_target", ""))

                # ── Use AgentRegistry for targeted revision ──
                fix_route = review.get("fix_route", {}) if isinstance(review.get("fix_route"), dict) else {}
                fix_target = fix_route.get("pipeline_fix_target") or review.get("fix_target", "answer")
                revision_bb = Blackboard(
                    task_id=f"revise_{slot_id}_r{revision_round}",
                    task_type="hybrid_subjective",
                    initial_state={
                        "current_blueprint": slot_blueprint,
                        "question_design": design,
                        "formatted_solution": solution,
                        "rubric": rubric,
                    },
                )
                fix_results = await AgentRegistry.invoke_fix(
                    fix_target, revision_bb, gateway,
                )

                if fix_target == "question":
                    design = revision_bb.get("question_design") or design
                if fix_target in ("question", "answer"):
                    code_solution = revision_bb.get("code_solution") or code_solution
                    solver_dict = code_solution.to_dict() if hasattr(code_solution, "to_dict") else solver_dict
                    solution = revision_bb.get("formatted_solution") or solution
                if fix_target == "rubric":
                    rubric = revision_bb.get("rubric") or rubric

                # Re-run review after fix
                review_bb = Blackboard(
                    task_id=f"review_{slot_id}_r{revision_round}",
                    task_type="hybrid_subjective",
                    initial_state={
                        "question_design": design,
                        "formatted_solution": solution,
                        "rubric": rubric,
                        "current_blueprint": slot_blueprint,
                    },
                )
                reviewer = IntentBasedReviewer(gateway)
                await reviewer.execute(review_bb)
                review = review_bb.get("review") or {}
                audit = AuditResultNormalizer.normalize(
                    review,
                    mode=AuditMode.QUESTION_REVIEW,
                )
                route = self.fix_router.route(
                    audit,
                    current_round=revision_round,
                    is_single_choice=False,
                )
                review["audit_result"] = audit.to_dict()
                review["fix_route"] = route.to_dict()

                logger.info(
                    "[%s] Post-fix review: status=%s issue=%s route=%s",
                    slot_id,
                    audit.status,
                    audit.issue_type,
                    route.next_action,
                )
                if route.next_action != "revise":
                    break
                continue

            # ── Initial run (revision_round == 0): manual pipeline ──

            # ── Step 1: Design question ──
            need_new_question = (
                revision_round == 0
                or review.get("fix_target") == "question"
            )

            if need_new_question:
                logger.info("[%s] Step 1: Question designer", slot_id)
                designer = QuestionDesignerAgent(gateway)
                design_bb = Blackboard(
                    task_id=f"design_{slot_id}_r{revision_round}",
                    task_type="hybrid_subjective",
                    initial_state={
                        "current_blueprint": slot_blueprint,
                        "experience_card": experience_card,
                        "reference_questions": experience_card,
                    },
                )
                # Retry loop for network errors
                design_record = None
                for design_attempt in range(3):
                    design_record = await designer.execute(design_bb)
                    if not design_record.error:
                        break
                    is_network = "network" in str(design_record.error).lower() or "connection" in str(design_record.error).lower()
                    if is_network and design_attempt < 2:
                        logger.warning("[%s] Design network error (attempt %d), retrying in 15s...",
                                       slot_id, design_attempt + 1)
                        await asyncio.sleep(15)
                        continue
                    break

                if design_record.error:
                    logger.error("[%s] Design failed after retries: %s", slot_id, design_record.error)
                    return HybridSubjectiveResult(
                        final_question={"error": design_record.error},
                        solver_result={}, formatted_solution={},
                        rubric={}, review={},
                        generation_time_s=time.monotonic() - total_start,
                    )
                design = design_bb.get("question_design") or {}
                logger.info("[%s] Design done: stem=%s...", slot_id,
                            str(design.get("stem", ""))[:80])

            # ── Step 2: FileCodeSolver (writes scripts to disk) ──
            logger.info("[%s] Step 2: FileCodeSolver", slot_id)

            sub_questions = design.get("sub_questions", [])
            if isinstance(sub_questions, str):
                try:
                    sub_questions = json.loads(sub_questions)
                except json.JSONDecodeError:
                    sub_questions = [sub_questions]

            solver = FileCodeSolverAgent(gateway, max_tokens=4096, max_steps=5)
            code_solution = await solver.solve(
                question_draft=design.get("stem", ""),
                sub_questions=sub_questions if sub_questions else None,
                question_type="comprehensive",
                slot_id=slot_id,
            )
            solver_dict = code_solution.to_dict()
            # Add raw outputs for downstream agents
            solver_dict["raw_outputs"] = [o[:2000] for o in code_solution.outputs]
            solver_dict["last_raw_output"] = code_solution.get_last_output()[:3000]
            logger.info("[%s] Solver done: %d files, %d execs, %.1fs, raw_outputs=%d",
                        slot_id, len(code_solution.code_files),
                        code_solution.python_exec_count,
                        code_solution.total_time_s,
                        len(code_solution.outputs))

            # ── Step 3: Format solution ──
            logger.info("[%s] Step 3: Solution formatter", slot_id)
            format_bb = Blackboard(
                task_id=f"format_{slot_id}_r{revision_round}",
                task_type="hybrid_subjective",
                initial_state={
                    "question_design": design,
                    "solver_result": solver_dict,
                },
            )
            formatter = HybridSolutionFormatter(gateway)
            await formatter.execute(format_bb)
            solution = format_bb.get("formatted_solution") or {}

            # ── Step 4: Rubric ──
            logger.info("[%s] Step 4: Rubric writer", slot_id)
            rubric_bb = Blackboard(
                task_id=f"rubric_{slot_id}_r{revision_round}",
                task_type="hybrid_subjective",
                initial_state={
                    "question_design": design,
                    "formatted_solution": solution,
                    "current_blueprint": slot_blueprint,
                },
            )
            rubric_agent = HybridRubricWriter(gateway)
            await rubric_agent.execute(rubric_bb)
            rubric = rubric_bb.get("rubric") or {}

            # ── Step 5: Intent-based review ──
            logger.info("[%s] Step 5: Intent reviewer", slot_id)
            review_bb = Blackboard(
                task_id=f"review_{slot_id}_r{revision_round}",
                task_type="hybrid_subjective",
                initial_state={
                    "question_design": design,
                    "formatted_solution": solution,
                    "rubric": rubric,
                    "current_blueprint": slot_blueprint,
                },
            )
            reviewer = IntentBasedReviewer(gateway)
            await reviewer.execute(review_bb)
            review = review_bb.get("review") or {}
            audit = AuditResultNormalizer.normalize(
                review,
                mode=AuditMode.QUESTION_REVIEW,
            )
            route = self.fix_router.route(
                audit,
                current_round=revision_round,
                is_single_choice=False,
            )
            review["audit_result"] = audit.to_dict()
            review["fix_route"] = route.to_dict()

            logger.info(
                "[%s] Review: status=%s issue=%s route=%s target=%s",
                slot_id,
                audit.status,
                audit.issue_type,
                route.next_action,
                route.pipeline_fix_target,
            )

            if route.next_action != "revise":
                break

        # Build final question
        # Prefer formatted_solution (structured by formatter agent) over raw solver output
        formatted_answer = solution.get("answers", solution)
        if isinstance(formatted_answer, dict) and not formatted_answer:
            formatted_answer = code_solution.get_last_output()[:3000] or ""

        final_question = {
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
            "solver_confidence": "high" if code_solution.computed_results and not code_solution.error else "low",
            "solver_evidence": code_solution.get_last_output()[:3000],
            "python_exec_count": code_solution.python_exec_count,
            "code_files": code_solution.code_files,
        }

        total_time = time.monotonic() - total_start
        logger.info("[%s] Pipeline done in %.1fs (rounds=%d)",
                     slot_id, total_time, revision_round + 1)

        return HybridSubjectiveResult(
            final_question=final_question,
            solver_result=solver_dict,
            formatted_solution=solution,
            rubric=rubric,
            review=review,
            generation_time_s=round(total_time, 1),
        )
