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
from core_new.blackboard import Blackboard


# ── Markdown parsing helpers ─────────────────────────────────


# Known LLM key spelling drift
_FIELD_ALIASES = {
    "hard_viation": "hard_violation",
    "hard_violation_count": "hard_violation_count",
    "soft_devation": "soft_deviation",
    "soft_deviation_count": "soft_deviation_count",
    "major_devation_count": "major_deviation_count",
    "minor_devation_count": "minor_deviation_count",
    "diffculty": "difficulty",
}


def _parse_md_kv(lines: List[str]) -> Dict[str, Any]:
    """Parse '- **key**: value' lines into a dict."""
    result = {}
    current_key = None

    for line in lines:
        m = re.match(r"^- \*\*(.+?)\*\*:\s*(.*)", line)
        if m:
            key = m.group(1).strip()
            value = m.group(2).strip()
            if value and (value.startswith("{") or value.startswith("[")):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            result[key] = value
            current_key = key
        elif line.startswith("  ") and current_key and current_key in result:
            existing = result[current_key]
            if isinstance(existing, str):
                result[current_key] = existing + "\n" + line.strip()
        elif current_key and current_key in result and isinstance(result[current_key], str):
            result[current_key] = result[current_key] + "\n" + line

    # Normalize known misspellings
    for wrong, correct in _FIELD_ALIASES.items():
        if wrong in result and correct not in result:
            result[correct] = result.pop(wrong)

    return result


def _parse_md_sections(text: str) -> Dict[str, Any]:
    """Split markdown by ## headers, parse each section's key-value pairs."""
    sections = {}
    current_name = None
    current_lines: List[str] = []

    for line in text.split("\n"):
        m = re.match(r"^##\s+(.+)", line)
        if m:
            if current_name:
                sections[current_name] = _parse_md_kv(current_lines)
            current_name = m.group(1).strip()
            current_lines = []
        elif current_name:
            current_lines.append(line)

    if current_name:
        sections[current_name] = _parse_md_kv(current_lines)

    return sections


def _is_slot_id(name: str) -> bool:
    """Check if a section name looks like a slot ID (Q12, Q43, etc.)."""
    return bool(re.match(r"^Q\d+$", name))


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
                enable_thinking=True,
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
        sections = _parse_md_sections(raw)

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
                kv["slot_id"] = name
                slots.append(kv)
        result["slots"] = slots

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
                enable_thinking=True,
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

        return BLUEPRINT_REVIEWER_PROMPT.format(
            user_requirements=requirements,
            paper_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            slot_contracts_md=slot_contracts_md,
        )

    def parse_output(self, raw: Any) -> Any:
        sections = _parse_md_sections(raw)

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
                enable_thinking=True,
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
        sections = _parse_md_sections(raw)

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
                enable_thinking=True,
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
        sections = _parse_md_sections(raw)

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
                enable_thinking=True,
                system_prompt="你是一位408考研试卷质量评审专家，严格区分内容问题和答案问题。严格按markdown格式输出。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import PAPER_REVIEWER_PROMPT

        blueprint = blackboard.get("paper_blueprint", {})
        questions = blackboard.get("generated_questions", [])
        templates = blackboard.get("slot_templates", {})

        return PAPER_REVIEWER_PROMPT.format(
            paper_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            generated_questions_json=json.dumps(questions, ensure_ascii=False, indent=2),
            slot_templates_json=json.dumps(templates, ensure_ascii=False, indent=2),
        )

    def parse_output(self, raw: Any) -> Any:
        sections = _parse_md_sections(raw)

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

