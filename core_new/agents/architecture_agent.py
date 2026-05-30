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
                required_fields=["raw_design_md"],
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
                score = int(blueprint.get("target_difficulty", 2))
                question_type = "comprehensive" if score > 2 else "single_choice"

        score = int(blueprint.get("target_difficulty", 2))
        subject = blueprint.get("target_subject", "计算机组成原理")
        blueprint_md = _dump_blueprint_md(blueprint)

        # Build feedback sections for regeneration
        feedback_section, feedback_workflow = _build_feedback_sections(blackboard)

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
            blueprint_md=blueprint_md,
            feedback_section=feedback_section,
            feedback_workflow=feedback_workflow,
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

        return {"raw_design_md": text}


def _build_feedback_sections(blackboard: Blackboard) -> tuple[str, str]:
    """Build feedback injection sections for regeneration scenarios."""
    previous_question = blackboard.get("previous_question")
    fix_instruction = blackboard.get("fix_instruction", "")

    if not previous_question and not fix_instruction:
        return "", ""

    parts = ["\n## 上次出题反馈（重要！请针对以下问题调整设计方案）\n"]
    if fix_instruction:
        parts.append(f"### 审核意见\n{fix_instruction}\n")

    if previous_question:
        stem = previous_question.get("stem", "")
        answer = previous_question.get("correct_answer", previous_question.get("answer", ""))
        if stem:
            parts.append(f"### 上次题干（仅供对照，不要复制）\n{stem[:1500]}\n")
        if answer:
            parts.append(f"### 上次答案\n{str(answer)[:500]}\n")

    workflow = (
        "\n6. **重要：针对审核反馈调整设计**，确保新方案不重复上次的问题"
    )

    return "\n".join(parts), workflow


def _dump_blueprint_md(blueprint: dict) -> str:
    """Convert blueprint dict to readable Markdown for architecture agent."""
    if not blueprint:
        return "（无特殊蓝图要求）"

    lines = []
    lines.append(f"- **科目**: {blueprint.get('target_subject', '未指定')}")
    lines.append(f"- **知识族**: {blueprint.get('target_family', '未指定')}")
    lines.append(f"- **核心考点**: {blueprint.get('primary_target_name', '未指定')}")
    lines.append(f"- **目标难度**: {blueprint.get('target_difficulty', '未指定')}")
    lines.append(f"- **子问数量**: {blueprint.get('sub_questions', '未指定')}（必须严格遵守）")
    lines.append(f"- **答案格式**: {blueprint.get('answer_format', '未指定')}")
    lines.append(f"- **选项风格**: {blueprint.get('option_style', '未指定')}")
    lines.append(f"- **推理形状**: {blueprint.get('reasoning_shape', '未指定')}")
    lines.append(f"- **功能角色**: {blueprint.get('primary_paper_role', '未指定')}")
    lines.append(f"- **必考要素**: {blueprint.get('must_include', '无')}")
    lines.append(f"- **禁止内容**: {blueprint.get('must_avoid', '无')}")

    dp = blueprint.get("difficulty_profile", {})
    if dp:
        lines.append(f"- **难度配置**: 知识深度={dp.get('knowledge_depth', '?')}, 推理步数={dp.get('reasoning_steps', '?')}, 计算量={dp.get('calculation_load', '?')}")

    return "\n".join(lines)
