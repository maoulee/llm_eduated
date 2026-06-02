"""StemBlueprintGate — unified pre-solve review combining knowledge, closure, numerical, and blueprint checks.

Merges: KnowledgeGate + EnvironmentClosureGate + StemVerifier + PostReview blueprint phase.
Runs BEFORE solver to catch questions not worth computing.
Uses python_exec tool for numerical verification.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from core_new.agent_base import AgentConfig, BaseAgent
from core_new.agent_roles import RoleType
from core_new.agent_tools import PYTHON_EXEC_TOOL
from core_new.blackboard import Blackboard
from core_new.markdown_parser import parse_md_sections


class StemBlueprintGateAgent(BaseAgent):
    """Pre-solve gate: validate stem + blueprint compliance before sending to solver."""

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        super().__init__(
            AgentConfig(
                name="stem_blueprint_gate",
                phase="gate",
                step_name="gate",
                output_format="markdown",
                output_key="stem_blueprint_gate_result",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=[],
                role_type=RoleType.AUDIT,
                system_prompt=(
                    "你是一位408考研命题审核专家。你在解答前完成题干+蓝图的联合审核。"
                    "你不解答题目，只判断是否值得交给代码解答智能体。"
                    "使用 python_exec 工具验证数值断言。严格按markdown格式输出。"
                ),
                tools=[PYTHON_EXEC_TOOL],
                max_tool_rounds=5,
                max_tool_calls=3,
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.stem_blueprint_gate_prompt import STEM_BLUEPRINT_GATE_PROMPT

        stem = blackboard.get("stem", "")
        options = blackboard.get("options")
        blueprint = blackboard.get("blueprint", {})
        question_design = blackboard.get("design", {})
        experience_radar = blackboard.get("experience", "")

        blueprint_md = _dump_blueprint_for_gate(blueprint)
        options_md = _dump_options_md(options)
        question_design_md = question_design.get("raw_design_md", "") if isinstance(question_design, dict) else str(question_design)[:3000]

        return STEM_BLUEPRINT_GATE_PROMPT.format(
            blueprint_md=blueprint_md,
            question_design_md=question_design_md,
            stem=stem,
            options_md=options_md,
            experience_radar=experience_radar or "（无经验卡）",
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw).strip()
        if not text or len(text) < 20:
            return {
                "status": "needs_fix",
                "severity": "critical",
                "next_action": "revise_stem",
                "fix_target": "stem",
                "checks": {},
                "evidence": "（审核输出为空，无法验证）",
                "code_verification": "",
                "fix_detail": "审核智能体未返回有效内容，默认判定需要修改题干",
                "comment": "审核输出为空",
                "_raw_text": text,
            }
        sections = _parse_gate_sections(text)

        verdict = sections.get("verdict", {})
        if not isinstance(verdict, dict):
            verdict = {}
        checks = sections.get("checks", {})
        if not isinstance(checks, dict):
            checks = {}
        fix_instruction = sections.get("fix_instruction", {})
        if not isinstance(fix_instruction, dict):
            fix_instruction = {}

        status = verdict.get("status", "pass")
        severity = verdict.get("severity", "none")
        fix_target = verdict.get("fix_target", "none")

        if status == "needs_fix" and severity not in ("critical", "minor"):
            severity = "critical"

        evidence_text = _extract_text(sections.get("evidence", ""))
        code_verification_text = _extract_text(sections.get("code_verification", ""))

        result = {
            "status": status,
            "severity": severity,
            "next_action": verdict.get("next_action", "continue"),
            "fix_target": fix_target,
            "checks": checks,
            "evidence": str(evidence_text),
            "code_verification": str(code_verification_text),
            "fix_detail": fix_instruction.get("fix_detail", ""),
            "comment": str(evidence_text)[:300],
        }

        result["_raw_text"] = text
        return result


def _normalize_gate_section_name(name: str) -> str:
    normalized = name.strip().lower()
    aliases = {
        "code verification": "code_verification",
        "code verification results": "code_verification",
        "code_verification": "code_verification",
        "fix instruction": "fix_instruction",
        "fix_instruction": "fix_instruction",
    }
    return aliases.get(normalized, normalized.replace("_", " "))


def _parse_section_kv(lines: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^\s*[-*]\s+\*\*(.+?)\*\*[:：]\s*(.*)\s*$", line)
        if not match:
            match = re.match(r"^\s*[-*]\s+([^*:：]+?)[:：]\s*(.*)\s*$", line)
        if match:
            parsed[match.group(1).strip()] = match.group(2).strip()
    return parsed


def _parse_gate_sections(text: str) -> dict[str, dict[str, str]]:
    """Parse gate markdown into normalized section dictionaries."""
    if not text or not str(text).strip():
        return {}

    sections: dict[str, dict[str, str]] = {}
    current_name: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if not current_name:
            return
        key = _normalize_gate_section_name(current_name)
        content = "\n".join(current_lines).strip()
        if key in {"evidence", "code_verification"}:
            sections[key] = {"text": content}
        else:
            sections[key] = _parse_section_kv(current_lines)

    for line in str(text).splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            flush()
            current_name = match.group(1).strip()
            current_lines = []
        elif current_name:
            current_lines.append(line)

    flush()
    return sections


def _extract_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text", ""))
    if value is None:
        return ""
    return str(value)


def _dump_blueprint_for_gate(blueprint: dict) -> str:
    """Convert blueprint to readable Markdown for the gate agent."""
    if not blueprint:
        return "（无蓝图）"

    lines = []
    lines.append(f"- **题位**: {blueprint.get('slot_id', '未指定')}")
    lines.append(f"- **科目**: {blueprint.get('target_subject', '未指定')}")
    lines.append(f"- **核心考点**: {blueprint.get('primary_target_name', '未指定')}")
    lines.append(f"- **题目类型**: {blueprint.get('question_type', '未指定')}")
    lines.append(f"- **目标难度**: {blueprint.get('target_difficulty', '未指定')}")

    sub_q = blueprint.get("sub_questions", "未指定")
    lines.append(f"- **子问数量**: {sub_q}（必须匹配）")

    must_include = blueprint.get("must_include", [])
    if must_include:
        lines.append(f"- **必考要素**: {', '.join(must_include) if isinstance(must_include, list) else must_include}")

    must_avoid = blueprint.get("must_avoid", [])
    if must_avoid:
        lines.append(f"- **禁止内容**: {', '.join(must_avoid) if isinstance(must_avoid, list) else must_avoid}")

    lines.append(f"- **答案格式**: {blueprint.get('answer_format', '未指定')}")
    lines.append(f"- **选项风格**: {blueprint.get('option_style', '未指定')}")
    lines.append(f"- **功能角色**: {blueprint.get('primary_paper_role', '未指定')}")
    lines.append(f"- **知识族**: {blueprint.get('target_family', '未指定')}")

    dp = blueprint.get("difficulty_profile", {})
    if dp:
        lines.append(f"- **难度配置**: 知识深度={dp.get('knowledge_depth', '?')}, 推理步数={dp.get('reasoning_steps', '?')}")

    return "\n".join(lines)


def _dump_options_md(options) -> str:
    """Convert options dict to readable Markdown."""
    if not options:
        return "（综合应用题，无选项）"
    if isinstance(options, dict):
        parts = []
        for key in ("option_A", "option_B", "option_C", "option_D"):
            if key in options:
                label = key.replace("option_", "")
                parts.append(f"- **{label}**: {options[key]}")
        return "\n".join(parts) if parts else "（无选项）"
    return str(options)
