"""Slot-template driven composition and generation agents.

Agents:
  PaperComposerAgent    — SlotContract + requirements → PaperBlueprint
  BlueprintReviewerAgent — PaperBlueprint → hard_violation / soft_deviation review
  QuestionWriterAgent   — SlotBlueprint → question
  QuestionFixerAgent    — question + fix instructions → fixed question (reasoning + code verification)
  PaperReviewerAgent    — generated paper + contracts → categorized review
"""

from __future__ import annotations

import json
import re
import os
from typing import Any, Dict, List, Optional

from core_new.agent_base import AgentConfig, BaseAgent
from core_new.agent_roles import AuditMode, RoleType
from core_new.blackboard import Blackboard
from core_new.markdown_parser import parse_md_sections_with_aliases


def _is_slot_id(name: str) -> bool:
    """Check if a section name looks like a slot ID (Q12, Q43, etc.).

    Accepts: Q43, Q43综合应用题, Q43（综合应用题）, Q43 综合题示例
    """
    return bool(re.match(r"^Q\d+", name.strip()))


def _load_experience_card(slot_id: str, exp_dir: str = "data/slot_experiences") -> str:
    """Load the MD experience card for a slot."""
    path = os.path.join(exp_dir, f"{slot_id}_experience.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return f"(经验卡 {slot_id} 不存在)"


# ── PaperComposerAgent ─────────────────────────────────────────


class PaperComposerAgent(BaseAgent):
    """Generate PaperBlueprint from SlotTemplates + user requirements."""

    def __init__(self, llm_backend, *, max_tokens: int = 16384):
        super().__init__(
            AgentConfig(
                name="paper_composer",
                phase="compose",
                output_format="markdown",
                output_key="paper_blueprint",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=["slots"],
                role_type=RoleType.PLANNER,
                system_prompt="你是一位408考研组卷专家，擅长基于题位模板规划试卷结构。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import PAPER_COMPOSER_PROMPT
        from core_new.slot_contract import build_slot_contract

        templates = blackboard.get("slot_templates", {})
        requirements = blackboard.read("user_requirements", "出一套标准难度的408模拟卷（选择题部分）")
        total_slots = blackboard.get("total_slots", len(templates))

        # Build SlotContracts for each slot
        contracts = []
        for slot_id, tpl in templates.items():
            card = _load_experience_card(slot_id)
            contract = build_slot_contract(slot_id, tpl, card)
            contracts.append(contract)
        slot_contracts_md = "\n\n---\n\n".join(contracts) if contracts else "（无题位契约）"

        return PAPER_COMPOSER_PROMPT.format(
            user_requirements=requirements,
            slot_contracts_md=slot_contracts_md,
            total_slots=total_slots,
        )

    def parse_output(self, raw: Any) -> Any:
        sections = parse_md_sections_with_aliases(raw)

        # Extract overall section
        overall = sections.get("整体", {})
        result = dict(overall)

        # Extract difficulty budget section (try multiple section names)
        for budget_key in ("难度预算", "计算量预算", "整体难度预算", "难度分布"):
            if budget_key in sections:
                result.update(sections[budget_key])
                break

        # Extract slot blueprints
        slots = []
        for name, kv in sections.items():
            if _is_slot_id(name):
                slot_id_match = re.match(r"^(Q\d+)", name)
                kv["slot_id"] = slot_id_match.group(1)
                slots.append(kv)
        result["slots"] = slots

        return result


def _validate_mode_against_card(slot_id: str, mode: str) -> str:
    """Validate examination_mode against the slot's experience card mode list.

    Strict validation: must match a mode from the experience card.
    No invented or partial modes allowed.
    """
    # Comprehensive questions always use "综合型"
    if slot_id.startswith("Q4") or mode == "综合型":
        return mode

    # Load experience card and extract available modes
    card_path = f"data/slot_experiences/{slot_id}_experience.md"
    if not os.path.exists(card_path):
        return mode

    with open(card_path, encoding="utf-8") as f:
        card = f.read()

    # Extract mode names from ## 考察模式分布 section
    available_modes = []
    in_dist = False
    for line in card.split("\n"):
        if line.startswith("## 考察模式分布"):
            in_dist = True
            continue
        if in_dist and line.startswith("## "):
            break
        if in_dist:
            m = re.match(r"-\s*\*\*(.+?)\*\*", line)
            if m:
                # Strip "模式X：" prefix if present
                cleaned = re.sub(r"^模式[A-Z][：:]\s*", "", m.group(1))
                available_modes.append(cleaned)

    if not available_modes:
        return mode

    # 1. Exact match
    if mode in available_modes:
        return mode

    # 2. Strip English parenthetical from both sides, try exact match
    def _strip_english(s):
        return re.sub(r"\s*\([A-Za-z/\s]+\)\s*$", "", s).strip()

    mode_stripped = _strip_english(mode)
    for am in available_modes:
        if _strip_english(am) == mode_stripped:
            return am

    # 3. Extract Chinese type prefix (e.g., "计算型", "概念辨析型")
    #    and match against available modes with the same prefix
    prefix_match = re.match(r"^([一-鿿型]+)", mode)
    if prefix_match:
        cn_prefix = prefix_match.group(1)
        for am in available_modes:
            if am.startswith(cn_prefix):
                return am
        # Also try matching against stripped available modes
        for am in available_modes:
            am_stripped = _strip_english(am)
            if am_stripped.startswith(cn_prefix):
                return am

    # 4. No match found — use first available mode (safest fallback)
    return available_modes[0]


class PaperOutlineComposerAgent(BaseAgent):
    """Generate paper outline (MD format) — only planning, no question design."""

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        super().__init__(
            AgentConfig(
                name="paper_outline_composer",
                phase="compose",
                output_format="markdown",
                output_key="paper_outline",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=["slots"],
                role_type=RoleType.PLANNER,
                system_prompt="你是一位408考研组卷专家，擅长规划试卷大纲（考点+难度+考察模式）。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import PAPER_OUTLINE_PROMPT
        from core_new.slot_contract import build_slot_contract

        templates = blackboard.get("slot_templates", {})
        requirements = blackboard.read("user_requirements", "出一套标准难度的408模拟卷")

        # Build SlotContracts for each slot
        contracts = []
        for slot_id, tpl in templates.items():
            card = _load_experience_card(slot_id)
            contract = build_slot_contract(slot_id, tpl, card)
            contracts.append(contract)
        slot_contracts_md = "\n\n---\n\n".join(contracts) if contracts else "（无题位信息）"

        return PAPER_OUTLINE_PROMPT.format(
            user_requirements=requirements,
            slot_contracts_md=slot_contracts_md,
        )

    def parse_output(self, raw: Any) -> Any:
        sections = parse_md_sections_with_aliases(raw)

        # Extract overall planning section
        result = {}
        overall_keys = ("整体规划", "整体", "规划")
        for ok in overall_keys:
            if ok in sections:
                result = dict(sections[ok])
                break

        # Extract per-slot outline entries
        slots = []
        for name, kv in sections.items():
            if _is_slot_id(name):
                slot_id_match = re.match(r"^(Q\d+)", name)
                kv["slot_id"] = slot_id_match.group(1)
                # Normalize field names to match downstream expectations
                if "考点" in kv and "primary_target_name" not in kv:
                    kv["primary_target_name"] = kv.pop("考点")
                if "知识域" in kv and "target_family" not in kv:
                    kv["target_family"] = kv.pop("知识域")
                if "难度" in kv and "difficulty_level" not in kv:
                    kv["difficulty_level"] = kv.pop("难度")
                if "认知雷达" in kv and "k_target" not in kv:
                    kv["k_target"] = kv.pop("认知雷达")
                if "难度说明" in kv and "difficulty_rationale" not in kv:
                    kv["difficulty_rationale"] = kv.pop("难度说明")
                if "考察模式" in kv and "examination_mode" not in kv:
                    kv["examination_mode"] = kv.pop("考察模式")
                # Legacy compatibility: ensure target_difficulty exists
                if "difficulty_level" in kv and "target_difficulty" not in kv:
                    kv["target_difficulty"] = kv["difficulty_level"]

                # Validate examination_mode against experience card
                sid = kv.get("slot_id", "")
                mode = kv.get("examination_mode", "")
                if sid and mode:
                    validated = _validate_mode_against_card(sid, mode)
                    if validated != mode:
                        kv["examination_mode"] = validated
                slots.append(kv)
        result["slots"] = slots

        # Store raw MD for downstream consumption
        result["outline_md"] = raw

        return result


class OutlineReviewerAgent(BaseAgent):
    """Review paper outline — focus on planning quality, not design."""

    def __init__(self, llm_backend, *, max_tokens: int = 4096):
        super().__init__(
            AgentConfig(
                name="outline_reviewer",
                phase="review_outline",
                output_format="markdown",
                output_key="outline_review",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=["status"],
                role_type=RoleType.AUDIT,
                system_prompt="你是一位408考研组卷审核专家，专注于审核试卷大纲的规划质量。严格按markdown格式输出。",
                max_retries=1,
                repair_max_retries=1,
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import BLUEPRINT_OUTLINE_REVIEW_PROMPT
        from core_new.slot_contract import build_slot_contract

        outline = blackboard.get("paper_outline", {})
        outline_md = outline.get("outline_md", "")
        templates = blackboard.get("slot_templates", {})
        requirements = blackboard.read("user_requirements", "")

        # Build contracts for reference
        contracts = []
        for slot_id, tpl in templates.items():
            card = _load_experience_card(slot_id)
            contract = build_slot_contract(slot_id, tpl, card)
            contracts.append(contract)
        slot_contracts_md = "\n\n---\n\n".join(contracts) if contracts else "（无题位信息）"

        return BLUEPRINT_OUTLINE_REVIEW_PROMPT.format(
            user_requirements=requirements,
            outline_md=outline_md,
            slot_contracts_md=slot_contracts_md,
        )

    def parse_output(self, raw: Any) -> Any:
        sections = parse_md_sections_with_aliases(raw)

        overall = sections.get("总体", sections.get("审核结论", {}))
        result = dict(overall)

        slot_reviews = []
        for name, kv in sections.items():
            if _is_slot_id(name):
                kv["slot_id"] = name
                slot_reviews.append(kv)
        result["slot_reviews"] = slot_reviews

        if "建议" in sections:
            result["suggestions"] = sections["建议"]

        # Ensure status field exists (required_field check)
        if "status" not in result:
            # Try to infer from content
            raw_lower = str(raw).lower()
            if "pass" in raw_lower or "通过" in raw_lower:
                result["status"] = "pass"
            elif "revise" in raw_lower or "修订" in raw_lower or "需修改" in raw_lower:
                result["status"] = "revise"
            else:
                result["status"] = "pass"  # Default to pass for outline review

        return result


# ── BlueprintReviewerAgent ──────────────────────────────────────


class BlueprintReviewerAgent(BaseAgent):
    """Review PaperBlueprint before sending to question writers."""

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        super().__init__(
            AgentConfig(
                name="blueprint_reviewer",
                phase="review_blueprint",
                output_format="markdown",
                output_key="blueprint_review",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=[],
                role_type=RoleType.AUDIT,
                audit_mode=AuditMode.BLUEPRINT_REVIEW,
                system_prompt="你是一位408考研组卷审核专家，负责审核组卷蓝图的合理性。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import BLUEPRINT_REVIEWER_PROMPT
        from core_new.slot_contract import build_slot_contract

        blueprint = blackboard.get("paper_blueprint", {})
        templates = blackboard.get("slot_templates", {})
        requirements = blackboard.read("user_requirements", "")

        # Build SlotContracts for reviewer to check against
        contracts = []
        for slot_id, tpl in templates.items():
            card = _load_experience_card(slot_id)
            contract = build_slot_contract(slot_id, tpl, card)
            contracts.append(contract)
        slot_contracts_md = "\n\n---\n\n".join(contracts) if contracts else "（无题位契约）"

        prompt = BLUEPRINT_REVIEWER_PROMPT.format(
            user_requirements=requirements,
            paper_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            slot_contracts_md=slot_contracts_md,
        )
        checklist = self.get_audit_checklist()
        if checklist:
            prompt += "\n\n" + checklist
        return prompt

    def parse_output(self, raw: Any) -> Any:
        sections = parse_md_sections_with_aliases(raw)

        overall = sections.get("总体", {})
        result = dict(overall)

        slot_reviews = []
        for name, kv in sections.items():
            if _is_slot_id(name):
                kv["slot_id"] = name
                slot_reviews.append(kv)

        result["slot_reviews"] = slot_reviews

        # Extract global issues (last free-text section)
        if "全局问题" in sections:
            result["global_issues"] = sections["全局问题"]

        return result


# ── QuestionWriterAgent ────────────────────────────────────────


class QuestionWriterAgent(BaseAgent):
    """Generate a single question from SlotBlueprint."""

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        super().__init__(
            AgentConfig(
                name="question_writer",
                phase="generate",
                output_format="markdown",
                output_key="generated_question",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=[],
                timeout_s=900.0,
                role_type=RoleType.GENERATOR,
                system_prompt="你是一位408考研出题专家，擅长按照蓝图精确出题。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import SLOT_QUESTION_WRITER

        blueprint = blackboard.get("current_blueprint", {})
        slot_id = blueprint.get("slot_id", "Q12")

        exp_card = _load_experience_card(slot_id)
        ref_questions = blackboard.read("reference_questions", "无参考真题")

        return SLOT_QUESTION_WRITER.format(
            slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            experience_card_md=exp_card,
            reference_questions=ref_questions,
            slot_id=slot_id,
        )

    def parse_output(self, raw: Any) -> Any:
        sections = parse_md_sections_with_aliases(raw)

        result = {}

        # Merge 题目 section (stem + options)
        if "题目" in sections:
            result.update(sections["题目"])

        # Merge 答案 section
        if "答案" in sections:
            result.update(sections["答案"])

        # Extract slot_id from # heading
        m = re.match(r"#\s+question\s+(Q\d+)", raw)
        if m:
            result["slot_id"] = m.group(1)

        return result


# ── QuestionFixerAgent ──────────────────────────────────────────


class QuestionFixerAgent(BaseAgent):
    """Fix specific issues in a question without regenerating it."""

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        super().__init__(
            AgentConfig(
                name="question_fixer",
                phase="fix",
                output_format="markdown",
                output_key="fixed_question",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=[],
                timeout_s=900.0,
                role_type=RoleType.GENERATOR,
                system_prompt="你是一位408考研出题专家，擅长精确修正题目中的错误。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import QUESTION_FIXER_PROMPT

        question = blackboard.get("question_to_fix", {})
        fix_instructions = blackboard.read("fix_instructions", "")
        slot_id = question.get("slot_id", "Q12")

        return QUESTION_FIXER_PROMPT.format(
            question_json=json.dumps(question, ensure_ascii=False, indent=2),
            fix_instructions=fix_instructions,
            slot_id=slot_id,
        )

    def parse_output(self, raw: Any) -> Any:
        # Same format as QuestionWriter
        sections = parse_md_sections_with_aliases(raw)

        result = {}
        if "题目" in sections:
            result.update(sections["题目"])
        if "答案" in sections:
            result.update(sections["答案"])

        m = re.match(r"#\s+question\s+(Q\d+)", raw)
        if m:
            result["slot_id"] = m.group(1)

        return result


# ── PaperReviewerAgent ──────────────────────────────────────────


class PaperReviewerAgent(BaseAgent):
    """Review whole paper with issue categorization (content vs answer)."""

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        super().__init__(
            AgentConfig(
                name="paper_reviewer",
                phase="review_paper",
                output_format="markdown",
                output_key="paper_review",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=[],
                timeout_s=900.0,
                role_type=RoleType.AUDIT,
                audit_mode=AuditMode.FINAL_PAPER_REVIEW,
                system_prompt="你是一位408考研试卷质量评审专家，严格区分内容问题和答案问题。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import PAPER_REVIEWER_PROMPT

        blueprint = blackboard.get("paper_blueprint", {})
        questions = blackboard.get("generated_questions", [])
        templates = blackboard.get("slot_templates", {})

        prompt = PAPER_REVIEWER_PROMPT.format(
            paper_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            generated_questions_json=json.dumps(questions, ensure_ascii=False, indent=2),
            slot_templates_json=json.dumps(templates, ensure_ascii=False, indent=2),
        )
        checklist = self.get_audit_checklist()
        if checklist:
            prompt += "\n\n" + checklist
        return prompt

    def parse_output(self, raw: Any) -> Any:
        sections = parse_md_sections_with_aliases(raw)

        overall = sections.get("总体", {})
        result = dict(overall)

        slot_reviews = []
        for name, kv in sections.items():
            if _is_slot_id(name):
                kv["slot_id"] = name
                slot_reviews.append(kv)
        result["slot_reviews"] = slot_reviews

        if "distribution" in sections:
            result["distribution_check"] = sections["distribution"]

        return result

