"""StemBlueprintGate — unified pre-solve review combining knowledge, closure, numerical, and blueprint checks.

Merges: KnowledgeGate + EnvironmentClosureGate + StemVerifier + PostReview blueprint phase.
Runs BEFORE solver to catch questions not worth computing.
Uses python_exec tool for numerical verification.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from core_new.agent_base import AgentConfig, BaseAgent
from core_new.agent_roles import RoleType
from core_new.blackboard import Blackboard


class StemBlueprintGateAgent(BaseAgent):
    """Pre-solve gate: validate stem + blueprint compliance before sending to solver."""

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        from core_new.agent_tools import ToolDef
        from core_new.code_exec import execute_python

        def _python_exec_handler(**kwargs):
            code = kwargs.get("code", "")
            result = execute_python(code, timeout=kwargs.get("timeout", 10.0))
            return json.dumps({
                "ok": result.ok,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }, ensure_ascii=False)

        python_exec_tool = ToolDef(
            name="python_exec",
            description=(
                "Execute Python code in a sandbox environment. "
                "Available: math, struct, itertools, collections, functools, and standard library. "
                "Write any code you need for verification."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute for verification",
                    },
                },
                "required": ["code"],
            },
            handler=_python_exec_handler,
        )

        super().__init__(
            AgentConfig(
                name="stem_blueprint_gate",
                phase="gate",
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
                tools=[python_exec_tool],
                max_tool_rounds=5,
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.stem_blueprint_gate_prompt import STEM_BLUEPRINT_GATE_PROMPT

        stem = blackboard.get("stem", "")
        options = blackboard.get("options")
        blueprint = blackboard.get("blueprint", {})
        question_design = blackboard.get("question_design", {})
        experience_radar = blackboard.get("experience_radar", "")

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
        sections = _parse_gate_sections(text)

        verdict = sections.get("verdict", {})
        checks = sections.get("checks", {})
        fix_instruction = sections.get("fix_instruction", {})

        status = verdict.get("status", "pass")
        severity = verdict.get("severity", "none")
        fix_target = verdict.get("fix_target", "none")

        # Map severity from text values
        if status == "needs_fix" and severity not in ("critical", "minor"):
            severity = "critical"

        result = {
            "status": status,
            "severity": severity,
            "next_action": verdict.get("next_action", "continue"),
            "fix_target": fix_target,
            "checks": checks,
            "evidence": _extract_text(sections.get("evidence", "")),
            "code_verification": _extract_text(sections.get("code_verification", "")),
            "fix_detail": fix_instruction.get("fix_detail", ""),
            "comment": _extract_text(sections.get("evidence", ""))[:300],
        }

        # Attach raw text for round history
        result["_raw_text"] = text
        return result


def _extract_text(val) -> str:
    if isinstance(val, dict):
        return val.get("text", "")
    return str(val) if val else ""


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


def _parse_gate_sections(text: str) -> dict[str, dict]:
    """Parse gate output into sections with key-value pairs."""
    sections: dict[str, dict] = {}
    current_section = None

    for line in text.split("\n"):
        stripped = line.strip()

        # Section header
        if stripped.startswith("## "):
            section_name = stripped[3:].strip().lower()
            # Normalize section names
            name_map = {
                "verdict": "verdict",
                "checks": "checks",
                "evidence": "evidence",
                "code_verification": "code_verification",
                "code verification": "code_verification",
                "code verification results": "code_verification",
                "fix_instruction": "fix_instruction",
                "fix instruction": "fix_instruction",
            }
            current_section = name_map.get(section_name, section_name)
            if current_section not in sections:
                sections[current_section] = {}
            continue

        # Key-value line
        if current_section and stripped.startswith("- **"):
            match_start = stripped.find("**")
            match_end = stripped.find("**", match_start + 2)
            if match_start >= 0 and match_end > match_start:
                key = stripped[match_start + 2:match_end].strip()
                value = stripped[match_end + 2:].strip()
                # Remove leading colon
                if value.startswith(":"):
                    value = value[1:].strip()
                if current_section in ("evidence", "code_verification"):
                    sections[current_section] = {"text": sections[current_section].get("text", "") + stripped + "\n"}
                else:
                    sections[current_section][key] = value
        elif current_section in ("evidence", "code_verification") and stripped:
            sections.setdefault(current_section, {})
            sections[current_section]["text"] = sections[current_section].get("text", "") + stripped + "\n"

    return sections
