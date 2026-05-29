"""Architecture Agent — designs question structure based on slot examination philosophy.

Sits between Composition Agent (decides what to test) and Writing Agent (writes the question).
Takes a Slot's 考察理念 + a knowledge point assignment, outputs a Markdown design document.

Uses tool-calling to read slot files autonomously — the model decides what sections
to read (考察理念, 难度维度, 设计理念, 往年案例) and fetches them itself.
"""

from __future__ import annotations

import re
from typing import Any, Dict

from core_new.agent_base import AgentConfig, BaseAgent
from core_new.agent_roles import RoleType
from core_new.agent_tools import SLOT_TOOLS
from core_new.blackboard import Blackboard
from core_new.prompts.architecture_prompts import (
    CHOICE_ARCHITECTURE_PROMPT,
    SUBJECTIVE_ARCHITECTURE_PROMPT,
)


class ArchitectureAgent(BaseAgent):
    """Design question structure from slot philosophy + knowledge point.

    Input (via blackboard):
      - slot_id: str
      - knowledge_point: str (or from blueprint.primary_target_name)
      - blueprint: dict (from PaperComposer)
      - question_type: str (optional, inferred if missing)

    The model uses read_slot tool to fetch slot sections autonomously.
    """

    def __init__(self, llm_backend, *, max_tokens: int = 32768):
        super().__init__(
            AgentConfig(
                name="architecture_agent",
                phase="architecture",
                output_format="markdown",
                output_key="question_design",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=["slot_id", "knowledge_point"],
                role_type=RoleType.PLANNER,
                system_prompt=(
                    "你是一位408考研出题架构师。你基于题位的考察理念，设计题目结构。"
                    "你不写题，只设计怎么考。"
                    "使用提供的工具读取题位文件，获取考察理念、难度维度、设计理念和往年案例，然后生成设计方案。"
                    "严格按Markdown格式输出。"
                ),
                tools=SLOT_TOOLS,
                max_tool_rounds=5,
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        slot_id = blackboard.get("slot_id", "")
        blueprint = blackboard.get("blueprint", {})
        knowledge_point = blackboard.get(
            "knowledge_point",
            blueprint.get("primary_target_name", ""),
        )

        # Determine question type
        question_type = blackboard.get("question_type", "")
        if not question_type:
            qt = blueprint.get("question_type", "")
            if qt:
                question_type = qt
            else:
                score = blueprint.get("target_difficulty", 2)
                question_type = "comprehensive" if score > 2 else "single_choice"

        score = blueprint.get("target_difficulty", 2)
        subject = blueprint.get("target_subject", "计算机组成原理")
        blueprint_json = _dump_blueprint(blueprint)

        template = (
            SUBJECTIVE_ARCHITECTURE_PROMPT
            if question_type == "comprehensive"
            else CHOICE_ARCHITECTURE_PROMPT
        )

        return template.format(
            slot_id=slot_id,
            knowledge_point=knowledge_point,
            subject=subject,
            score=score,
            blueprint_json=blueprint_json,
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw).strip()

        # Remove code block wrapping if present
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        result = _parse_architecture_md(text)
        result["raw_design_md"] = text
        return result


def _dump_blueprint(blueprint: dict) -> str:
    import json
    if not blueprint:
        return "（无特殊蓝图要求）"
    return json.dumps(blueprint, ensure_ascii=False, indent=2)


def _parse_architecture_md(text: str) -> Dict[str, Any]:
    """Parse architecture markdown into a dict with key fields."""
    result: Dict[str, Any] = {}

    # Extract basic info
    for line in text.split("\n"):
        m = re.match(r"^-\s+\*\*(.+?)\*\*[:：]\s*(.*)", line)
        if not m:
            m = re.match(r"^-\s+([^*:：]+?)[:：]\s*(.*)", line)
        if m:
            key, value = m.group(1).strip(), m.group(2).strip()
            result[key] = value

    # Map Chinese keys to standard keys
    key_map = {
        "题位": "slot_id",
        "知识点": "knowledge_point",
        "题目类型": "question_type",
        "分值": "score",
        "option_style": "option_style",
        "reasoning_shape": "reasoning_shape",
    }
    for cn_key, en_key in key_map.items():
        if cn_key in result and en_key not in result:
            result[en_key] = result[cn_key]

    # Extract difficulty values
    for dim in ("knowledge_depth", "calculation_load", "reasoning_steps"):
        m = re.search(rf"\*\*{dim}\*\*[:：]\s*(\d+)", text)
        if m:
            result[dim] = int(m.group(1))

    # Extract sub-question design sections
    sub_questions = []
    for m in re.finditer(r"###\s*第(\d+)问", text):
        sub_questions.append({"index": int(m.group(1))})
    if sub_questions:
        result["sub_question_count"] = len(sub_questions)

    # Extract reference years
    ref_match = re.search(r"参考真题风格[:：]\s*(.*)", text)
    if ref_match:
        result["reference_years"] = ref_match.group(1).strip()

    return result
