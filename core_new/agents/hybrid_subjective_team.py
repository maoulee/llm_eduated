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
from core_new.agent_roles import AuditMode, RoleType, source_policy_for_audit_mode
from core_new.audit_protocol import AuditResultNormalizer, FixRouter
from core_new.agents.file_code_solver import FileCodeSolverAgent, CodeSolution
from core_new.agents.agent_registry import AgentRegistry
from core_new.blackboard import Blackboard
from core_new.experience_view import build_design_experience_view
from core_new.fallback_executor import FallbackExecutor
from core_new.markdown_parser import try_parse_json_object, parse_md_kv, parse_md_sections, parse_structured_output

logger = logging.getLogger(__name__)


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


def _dump_blueprint_md(blueprint: dict) -> str:
    """Convert blueprint dict to readable Markdown for the merged design prompt."""
    if not blueprint:
        return "（无特殊蓝图要求）"

    lines = []
    lines.append(f"- **科目**: {blueprint.get('target_subject', '未指定')}")
    lines.append(f"- **知识族**: {blueprint.get('target_family', '未指定')}")
    lines.append(f"- **核心考点**: {blueprint.get('primary_target_name', '未指定')}")
    lines.append(f"- **目标难度**: {blueprint.get('target_difficulty', '未指定')}")
    lines.append(f"- **子问数量**: {blueprint.get('sub_questions', '未指定')}（必须严格遵守）")
    lines.append(f"- **答案格式**: {blueprint.get('answer_format', '未指定')}")
    lines.append(f"- **功能角色**: {blueprint.get('primary_paper_role', '未指定')}")
    lines.append(f"- **必考要素**: {blueprint.get('must_include', '无')}")
    lines.append(f"- **禁止内容**: {blueprint.get('must_avoid', '无')}")

    dp = blueprint.get("difficulty_profile", {})
    if dp:
        lines.append(f"- **难度配置**: 知识深度={dp.get('knowledge_depth', '?')}, 推理步数={dp.get('reasoning_steps', '?')}, 计算量={dp.get('calculation_load', '?')}")

    return "\n".join(lines)


# ── Slot philosophy extraction ─────────────────────────────


_SLOT_PHILOSOPHY_SECTIONS = [
    "认知雷达锚点",
    "考察理念",
    "设计理念",
    "推理形式分析",
    "出题指导",
]


def _extract_slot_philosophy(slot_id: str) -> str:
    """Extract key design philosophy sections from slot file for pre-injection.

    Extracts: 认知雷达锚点, 考察理念, 设计理念, 推理形式分析, 出题指导.
    Skips large reference sections (往年案例, 参考题目 K1-K5 评分).
    Returns combined text or empty string if slot file not found.
    """
    import os as _os
    path = _os.path.join("data", "slots", f"{slot_id}_slot.md")
    if not _os.path.exists(path):
        return ""

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    extracted_parts = []

    for target in _SLOT_PHILOSOPHY_SECTIONS:
        capturing = False
        match_level = 0
        result = []
        for line in lines:
            if line.startswith("### "):
                heading_level = 3
            elif line.startswith("## "):
                heading_level = 2
            elif line.startswith("# "):
                heading_level = 1
            else:
                heading_level = 0

            if not capturing and heading_level >= 2 and target in line:
                capturing = True
                match_level = heading_level
                result.append(line)
                continue
            if capturing:
                if heading_level > 0 and heading_level <= match_level:
                    break
                result.append(line)

        section_text = "\n".join(result).strip()
        if section_text and len(section_text) > 20:
            extracted_parts.append(section_text)

    if not extracted_parts:
        return ""
    return "\n\n---\n\n".join(extracted_parts)


# ── Step 1: Question Designer ────────────────────────────────


class QuestionDesignerAgent(BaseAgent):
    """Design question with explicit intent — merged architecture+design in one step.

    Reads slot philosophy via read_slot tool, then produces question + design intent
    in a single LLM call.
    """

    def __init__(self, llm_backend, *, max_tokens: int = 32768):
        super().__init__(
            AgentConfig(
                name="question_designer",
                phase="design",
                step_name="design_comp",
                output_format="markdown",
                output_key="question_design",
                max_tokens=max_tokens,
                enable_thinking=False,
                timeout_s=300.0,
                max_retries=2,
                required_fields=["stem", "sub_questions"],
                repair_on_parse_failure=True,
                repair_max_retries=1,
                role_type=RoleType.GENERATOR,
                tools=[],  # Designer is pure NL — no tools
                max_tool_rounds=0,
                expected_output_format=(
                    "# question Qxx\n\n"
                    "## 题目\n"
                    "- **stem**: 题干全文\n"
                    "- **sub_questions**: [\"(1) 子问1\", \"(2) 子问2\"]\n"
                    "- **given_conditions**: [\"条件1\"]\n"
                    "- **difficulty_self_assessment**: 1-5\n"
                    "- **knowledge_points**: 知识点\n"
                    "- **parameter_notes**: 参数说明\n\n"
                    "## 推理模式\n"
                    "- **reasoning_form**: multi_step/simulation/one_formula/elimination\n"
                    "- **reasoning_rationale**: ...\n"
                    "- **condition_utilization**: ...\n\n"
                    "## 设计意图\n"
                    "- **sub_q1_intent**: 考察内容和解题路径\n"
                    "- **trap_design**: 陷阱设计\n"
                    "- **sub_question_logic**: 子问逻辑关系\n\n"
                    "## 自检清单\n"
                    "- **parameter_consistency**: PASS/FAIL\n"
                    "- **unique_solution**: PASS/FAIL\n"
                    "- **all_conditions_used**: PASS/FAIL"
                ),
                system_prompt="你是一位408考研出题专家，擅长按照蓝图精确设计综合应用题。使用提供的工具读取题位文件，获取考察理念和往年案例，然后一次性完成出题。你必须写清设计意图，但不写答案。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import K_RADAR_DEFINITIONS, SUBJECTIVE_DESIGN_MERGED_PROMPT

        blueprint = blackboard.get("blueprint", {})
        slot_id = blueprint.get("slot_id", "unknown")
        blueprint_md = _dump_blueprint_md(blueprint)
        slot_philosophy = _extract_slot_philosophy(slot_id)

        prompt = SUBJECTIVE_DESIGN_MERGED_PROMPT.format(
            slot_id=slot_id,
            blueprint_md=blueprint_md,
            k_definitions=K_RADAR_DEFINITIONS,
            slot_philosophy=slot_philosophy or "（未找到题位设计哲学，请用 read_slot 工具读取）",
        )

        fix_instruction = blackboard.get("fix_instruction", "")
        has_fix = bool(self._memory and any(
            m.get("role") == "review" for m in self._memory
        ))
        if fix_instruction:
            has_fix = True

        if has_fix:
            prompt += (
                "\n\n## 重要提示\n"
                "你正在**修改**前一轮生成的题干，不是重新出一道不同的题。\n"
                "请查看下方历史记录中的审查反馈，针对审核指出的具体问题进行精确修改。\n"
                "保持题干整体结构、考察方向和知识点不变，仅修正被指出的问题。\n"
            )
            if fix_instruction:
                prompt += f"\n补充修复指令：{fix_instruction}\n"

        return prompt

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        # Strip code fences that GLM-5.1 sometimes wraps around output
        stripped = re.sub(r"^```(?:\w+)?\s*\n?", "", text)
        stripped = re.sub(r"\n?```\s*$", "", stripped)
        if len(stripped.strip()) > 50:
            text = stripped

        result = parse_structured_output(text, md_sections=("题目", "推理模式", "设计意图", "自检清单"))
        if not result:
            # Fallback: search all sections for stem/sub_questions
            from core_new.markdown_parser import parse_md_sections as _pms
            all_sections = _pms(text)
            logger.warning("[question_designer] Primary parse empty, sections found: %s",
                           list(all_sections.keys()))
            for _name, sec in all_sections.items():
                if isinstance(sec, dict) and sec.get("stem"):
                    result.update(sec)
                    logger.info("[question_designer] Found stem in section '%s'", _name)
                    break
        if not result:
            # Fallback: try JSON with common keys
            data = try_parse_json_object(text)
            if data and isinstance(data, dict):
                result = data
                logger.info("[question_designer] Fallback to JSON parse succeeded")
        if not result:
            logger.warning("[question_designer] All parse strategies failed. Raw (first 500 chars): %s",
                           text[:500])
        # Flatten design intent sub-keys
        intent = result.get("design_intent", {})
        for key in ("sub_q1_intent", "sub_q2_intent", "sub_q3_intent",
                     "trap_design", "sub_question_logic"):
            if key in intent:
                result[key] = intent[key]
        # Extract slot_id from heading
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

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        super().__init__(
            AgentConfig(
                name="subjective_solution_formatter",
                phase="format_solution",
                step_name="format_comp",
                output_format="markdown",
                output_key="formatted_solution",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=["answers"],
                repair_max_retries=1,
                role_type=RoleType.SUMMARIZER,
                system_prompt="你是一位408考研解题专家，擅长根据计算结果整理标准答案。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import SUBJECTIVE_SOLUTION_FORMATTER_PROMPT

        question = blackboard.get("design", {})
        solver_result = blackboard.get("solver_result", {})

        return SUBJECTIVE_SOLUTION_FORMATTER_PROMPT.format(
            question_json=json.dumps(question, ensure_ascii=False, indent=2),
            solver_result_json=json.dumps(solver_result, ensure_ascii=False, indent=2),
            slot_id=question.get("slot_id", "unknown"),
        )

    def parse_output(self, raw: Any) -> Any:
        data = try_parse_json_object(str(raw))
        if data:
            nested = data.get("answers")
            if nested is not None:
                return data
            if isinstance(data.get("solution"), dict):
                return data["solution"]
        sections = parse_md_sections(str(raw))
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

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        super().__init__(
            AgentConfig(
                name="subjective_rubric_writer",
                phase="rubric",
                output_format="markdown",
                output_key="rubric",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=[],
                role_type=RoleType.SUMMARIZER,
                system_prompt="你是一位408考研评分标准制定专家。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import SUBJECTIVE_RUBRIC_PROMPT

        question = blackboard.get("design", {})
        solution = blackboard.get("solution", {})
        blueprint = blackboard.get("blueprint", {})

        return SUBJECTIVE_RUBRIC_PROMPT.format(
            question_json=json.dumps(question, ensure_ascii=False, indent=2),
            solution_json=json.dumps(solution, ensure_ascii=False, indent=2),
            slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            slot_id=question.get("slot_id", "unknown"),
        )

    def parse_output(self, raw: Any) -> Any:
        sections = parse_md_sections(str(raw))
        result: Dict[str, Any] = {}
        if "评分点" in sections:
            result.update(sections["评分点"])
        if "评分说明" in sections:
            result.update(sections["评分说明"])
        return result


# ── Step 5: Intent-based Reviewer ─────────────────────────────


class IntentBasedReviewer(BaseAgent):
    """Review: compare design intent + slot blueprint vs solver results, route fixes."""

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        super().__init__(
            AgentConfig(
                name="intent_reviewer",
                phase="review",
                output_format="markdown",
                output_key="review",
                max_tokens=max_tokens,
                enable_thinking=False,
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

        question = blackboard.get("design", {})
        solution = blackboard.get("solution", {})
        rubric = blackboard.get("rubric", {})
        blueprint = blackboard.get("blueprint", {})

        design_intent = {}
        for key in ("sub_q1_intent", "sub_q2_intent", "sub_q3_intent",
                     "trap_design", "sub_question_logic"):
            val = question.get(key)
            if val:
                design_intent[key] = val
        if "design_intent" in question:
            design_intent.update(question["design_intent"])

        prompt = SUBJECTIVE_QUESTION_REVIEW_PROMPT.format(
            design_intent_json=json.dumps(design_intent, ensure_ascii=False, indent=2),
            question_json=json.dumps(question, ensure_ascii=False, indent=2),
            solution_json=json.dumps(solution, ensure_ascii=False, indent=2),
            rubric_json=json.dumps(rubric, ensure_ascii=False, indent=2),
            slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            slot_id=question.get("slot_id", "unknown"),
        )
        checklist = self.get_audit_checklist()
        if checklist:
            prompt += "\n\n" + checklist
        return prompt

    def parse_output(self, raw: Any) -> Any:
        text = str(raw)
        # Try JSON first for nested key extraction and fix_instruction handling
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
            return result

        # Shared markdown parser
        result = parse_structured_output(text, md_sections=("review", "fix_instruction"))

        # Also check Chinese section name variants
        if not result:
            sections = parse_md_sections(text)
            result = {}
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
        self.fallback_executor = FallbackExecutor()
        self.fallback_executor.register("human_review", self._fallback_human_review)
        self.fallback_executor.register("needs_human_check", self._fallback_human_review)

    @staticmethod
    async def _fallback_human_review(data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "needs_human_review",
            "reason": "Agent failed, routed to human review",
        }

    async def run(
        self,
        slot_blueprint: Dict[str, Any],
        experience_card: str,
        gateway,
    ) -> HybridSubjectiveResult:
        slot_id = slot_blueprint.get("slot_id", "unknown")
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
                    source_policy=source_policy_for_audit_mode(AuditMode.QUESTION_REVIEW),
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
                    bb_data = design_bb.get_relevant_state(designer.config.name)
                    fb_result = await self.fallback_executor.try_fallback(design_record, bb_data)
                    if fb_result.used_fallback and not fb_result.error:
                        logger.info("[%s] Design fallback succeeded: %s", slot_id, fb_result.fallback_target)
                        if fb_result.fallback_target in ("human_review", "needs_human_check"):
                            return HybridSubjectiveResult(
                                final_question={"status": "needs_human_review",
                                                "reason": fb_result.result_data.get("reason", "Design failed, routed to human review"),
                                                "fallback_target": fb_result.fallback_target},
                                solver_result={}, formatted_solution={},
                                rubric={}, review={},
                                generation_time_s=time.monotonic() - total_start,
                            )
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

            solver = FileCodeSolverAgent(gateway, max_tokens=16384, max_steps=5)
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
            review_record = await reviewer.execute(review_bb)
            if review_record.error:
                bb_data = review_bb.get_relevant_state(reviewer.config.name)
                fb_result = await self.fallback_executor.try_fallback(review_record, bb_data)
                if fb_result.used_fallback and not fb_result.error:
                    logger.info("[%s] Review fallback succeeded: %s", slot_id, fb_result.fallback_target)
                    if fb_result.fallback_target in ("human_review", "needs_human_check"):
                        review = {"status": "needs_human_review",
                                  "reason": fb_result.result_data.get("reason", "Review failed, routed to human review"),
                                  "fallback_target": fb_result.fallback_target}
                        break
            review = review_bb.get("review") or {}
            audit = AuditResultNormalizer.normalize(
                review,
                mode=AuditMode.QUESTION_REVIEW,
            )
            route = self.fix_router.route(
                audit,
                current_round=revision_round,
                is_single_choice=False,
                source_policy=source_policy_for_audit_mode(AuditMode.QUESTION_REVIEW),
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
