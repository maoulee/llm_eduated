"""Slot-template driven composition and generation agents.

Agents:
  PaperComposerAgent    — SlotTemplates + requirements → PaperBlueprint
  BlueprintReviewerAgent — PaperBlueprint → blueprint quality review
  QuestionWriterAgent   — SlotBlueprint → question
  QuestionFixerAgent    — question + fix instructions → fixed question
  PaperReviewerAgent    — generated paper + templates → categorized review
  QualityReviewerAgent  — (legacy) generated paper + templates → review
"""

from __future__ import annotations

import json
import re
import os
from typing import Any, Dict, List, Optional

from core_new.agent_base import AgentConfig, BaseAgent
from core_new.blackboard import AgentRecord, Blackboard


# ── Helpers ────────────────────────────────────────────────────


def _parse_xml_to_dict(text: str) -> Dict[str, Any]:
    """Parse XML-tagged fields into a dict, handling JSON values."""
    result = {}
    for m in re.finditer(r"<(\w+)>(.*?)</\1>", text, re.DOTALL):
        key = m.group(1)
        value = m.group(2).strip()
        # Try JSON parse for complex values
        if value.startswith("{") or value.startswith("["):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
        result[key] = value
    return result


def _parse_slot_blueprints(raw: str) -> List[Dict[str, Any]]:
    """Parse multiple <slot_blueprint> blocks from PaperComposer output."""
    blueprints = []
    for m in re.finditer(
        r"<slot_blueprint\s+slot_id=\"(\w+)\">(.*?)</slot_blueprint>",
        raw,
        re.DOTALL,
    ):
        slot_id = m.group(1)
        inner = m.group(2)
        parsed = _parse_xml_to_dict(inner)
        parsed["slot_id"] = slot_id
        blueprints.append(parsed)
    return blueprints


def _parse_questions(raw: str) -> List[Dict[str, Any]]:
    """Parse multiple <question> blocks from QuestionWriter output."""
    questions = []
    for m in re.finditer(
        r"<question\s+slot_id=\"(\w+)\">(.*?)</question>", raw, re.DOTALL
    ):
        slot_id = m.group(1)
        inner = m.group(2)
        parsed = _parse_xml_to_dict(inner)
        parsed["slot_id"] = slot_id
        questions.append(parsed)
    return questions


def _parse_slot_reviews(raw: str) -> List[Dict[str, Any]]:
    """Parse multiple <slot_review> blocks from QualityReviewer output."""
    reviews = []
    for m in re.finditer(
        r"<slot_review\s+slot_id=\"(\w+)\">(.*?)</slot_review>", raw, re.DOTALL
    ):
        slot_id = m.group(1)
        inner = m.group(2)
        parsed = _parse_xml_to_dict(inner)
        parsed["slot_id"] = slot_id
        reviews.append(parsed)
    return reviews


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
                system_prompt="你是一位408考研组卷专家，擅长基于题位模板规划试卷结构。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import PAPER_COMPOSER_PROMPT

        templates = blackboard.get("slot_templates", {})
        templates_json = json.dumps(templates, ensure_ascii=False, indent=2)
        requirements = blackboard.read("user_requirements", "出一套标准难度的408模拟卷（选择题部分）")
        total_slots = blackboard.get("total_slots", len(templates))

        return PAPER_COMPOSER_PROMPT.format(
            user_requirements=requirements,
            slot_templates_json=templates_json,
            total_slots=total_slots,
        )

    def parse_output(self, raw: Any) -> Any:
        # Extract the paper_blueprint block
        m = re.search(r"<paper_blueprint>(.*?)</paper_blueprint>", raw, re.DOTALL)
        text = m.group(1) if m else raw

        result = _parse_xml_to_dict(text)

        # Parse slot blueprints
        result["slots"] = _parse_slot_blueprints(raw)

        # Parse distribution
        if "difficulty_distribution" in result and isinstance(
            result["difficulty_distribution"], str
        ):
            try:
                result["difficulty_distribution"] = json.loads(
                    result["difficulty_distribution"]
                )
            except json.JSONDecodeError:
                pass

        return result


# ── QuestionWriterAgent ────────────────────────────────────────


class QuestionWriterAgent(BaseAgent):
    """Generate a single question from SlotBlueprint + experience card."""

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        super().__init__(
            AgentConfig(
                name="question_writer",
                phase="generate",
                output_format="markdown",
                output_key="generated_question",
                max_tokens=max_tokens,
                enable_thinking=True,
                system_prompt="你是一位408考研出题专家，擅长按照蓝图精确出题。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import SLOT_QUESTION_WRITER

        blueprint = blackboard.get("current_blueprint", {})
        slot_id = blueprint.get("slot_id", "Q12")

        # Load experience card
        exp_card = _load_experience_card(slot_id)

        # Reference questions from template
        ref_questions = blackboard.read("reference_questions", "无参考真题")

        return SLOT_QUESTION_WRITER.format(
            slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            experience_card_md=exp_card,
            reference_questions=ref_questions,
            slot_id=slot_id,
        )

    def parse_output(self, raw: Any) -> Any:
        questions = _parse_questions(raw)
        if questions:
            return questions[0]
        # Fallback: parse the whole thing
        return _parse_xml_to_dict(raw)


# ── QualityReviewerAgent ──────────────────────────────────────


class QualityReviewerAgent(BaseAgent):
    """Review generated paper against SlotTemplates."""

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        super().__init__(
            AgentConfig(
                name="quality_reviewer",
                phase="review",
                output_format="markdown",
                output_key="paper_review",
                max_tokens=max_tokens,
                enable_thinking=True,
                system_prompt="你是一位408考研试卷质量评审专家，严格按题位模板评审。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import PAPER_QUALITY_REVIEWER

        blueprint = blackboard.get("paper_blueprint", {})
        questions = blackboard.get("generated_questions", [])
        templates = blackboard.get("slot_templates", {})

        return PAPER_QUALITY_REVIEWER.format(
            paper_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            generated_questions_json=json.dumps(questions, ensure_ascii=False, indent=2),
            slot_templates_json=json.dumps(templates, ensure_ascii=False, indent=2),
        )

    def parse_output(self, raw: Any) -> Any:
        m = re.search(r"<paper_review>(.*?)</paper_review>", raw, re.DOTALL)
        text = m.group(1) if m else raw

        result = _parse_xml_to_dict(text)

        # Parse slot reviews
        result["slot_reviews"] = _parse_slot_reviews(raw)

        # Parse distribution check
        m2 = re.search(
            r"<distribution_check>(.*?)</distribution_check>", text, re.DOTALL
        )
        if m2:
            result["distribution_check"] = _parse_xml_to_dict(m2.group(1))

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
                system_prompt="你是一位408考研组卷审核专家，负责审核组卷蓝图的合理性。",
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.slot_prompts import BLUEPRINT_REVIEWER_PROMPT

        blueprint = blackboard.get("paper_blueprint", {})
        templates = blackboard.get("slot_templates", {})
        requirements = blackboard.read("user_requirements", "")

        return BLUEPRINT_REVIEWER_PROMPT.format(
            user_requirements=requirements,
            paper_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
            slot_templates_json=json.dumps(templates, ensure_ascii=False, indent=2),
        )

    def parse_output(self, raw: Any) -> Any:
        m = re.search(r"<blueprint_review>(.*?)</blueprint_review>", raw, re.DOTALL)
        text = m.group(1) if m else raw

        result = _parse_xml_to_dict(text)
        result["slot_reviews"] = _parse_slot_reviews(raw)
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
                system_prompt="你是一位408考研出题专家，擅长精确修正题目中的错误。",
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
        questions = _parse_questions(raw)
        if questions:
            return questions[0]
        return _parse_xml_to_dict(raw)


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
                system_prompt="你是一位408考研试卷质量评审专家，严格区分内容问题和答案问题。",
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
        m = re.search(r"<paper_review>(.*?)</paper_review>", raw, re.DOTALL)
        text = m.group(1) if m else raw

        result = _parse_xml_to_dict(text)
        result["slot_reviews"] = _parse_slot_reviews(raw)

        m2 = re.search(
            r"<distribution_check>(.*?)</distribution_check>", text, re.DOTALL
        )
        if m2:
            result["distribution_check"] = _parse_xml_to_dict(m2.group(1))

        return result
