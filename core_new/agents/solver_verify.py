"""SolverVerify — post-solve verification of code solver results.

Merges: SC Reviewer (computed vs intended) + Comp IntentBasedReviewer + PostReview solution phase.
Runs AFTER solver to verify the answer is trustworthy.
Pure text review, no code execution tools.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from core_new.agent_base import AgentConfig, BaseAgent
from core_new.agent_roles import RoleType
from core_new.blackboard import Blackboard
from core_new.markdown_parser import parse_md_sections, FieldExtractor


class SolverVerifyAgent(BaseAgent):
    """Post-solve verification: is the solver result trustworthy?"""

    def __init__(self, llm_backend, *, max_tokens: int = 8192):
        super().__init__(
            AgentConfig(
                name="solver_verify",
                phase="verify",
                output_format="markdown",
                output_key="solver_verify_result",
                max_tokens=max_tokens,
                enable_thinking=False,
                required_fields=[],
                role_type=RoleType.AUDIT,
                system_prompt=(
                    "你是一位408考研解答审核专家。你验证代码解答智能体的结果是否可信。"
                    "你不重新运行代码，但必须验证求解器使用的公式和推理路径是否正确。"
                    "严格按markdown格式输出。"
                ),
                tools=[],
                max_tool_rounds=1,
            ),
            llm_backend,
        )

    def build_input(self, blackboard: Blackboard) -> str:
        from core_new.prompts.solver_verify_prompt import SOLVER_VERIFY_PROMPT

        stem = blackboard.get("stem", "")
        options = blackboard.get("options")
        question_design = blackboard.get("question_design", {})
        solver_result = blackboard.get("solver_result", {})
        question_type = blackboard.get("question_type", "single_choice")
        blueprint = blackboard.get("blueprint", {})

        options_md = _dump_options_md(options)
        question_design_md = question_design.get("raw_design_md", "") if isinstance(question_design, dict) else str(question_design)[:2000]
        solver_result_json = json.dumps(solver_result, ensure_ascii=False, indent=2) if solver_result else "（无 solver 结果）"
        blueprint_md = _dump_blueprint_for_verify(blueprint)

        return SOLVER_VERIFY_PROMPT.format(
            stem=stem,
            options_md=options_md,
            question_design_md=question_design_md,
            solver_result_json=solver_result_json,
            question_type="选择题" if question_type == "single_choice" else "综合应用题",
            blueprint_md=blueprint_md,
        )

    def parse_output(self, raw: Any) -> Any:
        text = str(raw).strip()
        if not text or len(text) < 20:
            return {
                "status": "needs_fix",
                "next_action": "rerun_solver",
                "fix_target": "solver",
                "checks": {},
                "trusted": "false",
                "computed_answer": "",
                "evidence": "（审核输出为空，无法验证）",
                "fix_detail": "审核智能体未返回有效内容，默认判定需要重跑 solver",
                "comment": "审核输出为空",
                "_raw_text": text,
                "overall_quality": 3,
            }
        sections = parse_md_sections(text)

        # Normalize section names (handle English/Chinese variants)
        name_map = {
            "verified result": "verified_result",
            "fix instruction": "fix_instruction",
        }
        for old, new in name_map.items():
            if old in sections and new not in sections:
                sections[new] = sections.pop(old)

        verdict = sections.get("verdict", {})
        checks = sections.get("checks", {})
        if not isinstance(checks, dict):
            checks = {}
        verified = sections.get("verified_result", {})
        if not isinstance(verified, dict):
            verified = {}
        fix_instruction = sections.get("fix_instruction", {})
        if not isinstance(fix_instruction, dict):
            fix_instruction = {}

        status = verdict.get("status", "pass") if isinstance(verdict, dict) else "pass"
        fix_target = verdict.get("fix_target", "none") if isinstance(verdict, dict) else "none"

        # Default: if needs_fix but no explicit target, assume solver
        if status == "needs_fix" and fix_target == "none":
            fix_target = "solver"

        evidence_text = sections.get("evidence", "")
        if isinstance(evidence_text, dict):
            evidence_text = evidence_text.get("text", str(evidence_text))

        result = {
            "status": status,
            "next_action": verdict.get("next_action", "continue") if isinstance(verdict, dict) else "continue",
            "fix_target": fix_target,
            "checks": checks,
            "trusted": verified.get("trusted", "true"),
            "computed_answer": verified.get("computed_answer", ""),
            "evidence": str(evidence_text),
            "fix_detail": fix_instruction.get("fix_detail", ""),
            "comment": str(evidence_text)[:300],
        }

        result["_raw_text"] = text

        # Provide overall_quality from LLM output, fallback to default
        result["overall_quality"] = checks.get("overall_quality", 8 if result["status"] == "pass" else 5)
        return result


def _dump_blueprint_for_verify(blueprint: dict) -> str:
    """Convert blueprint to readable Markdown for the verify agent."""
    if not blueprint:
        return "（无蓝图）"

    lines = []
    lines.append(f"- **核心考点**: {blueprint.get('primary_target_name', '未指定')}")
    lines.append(f"- **目标难度**: {blueprint.get('target_difficulty', '未指定')}")
    lines.append(f"- **题目类型**: {blueprint.get('question_type', '未指定')}")

    must_include = blueprint.get("must_include", [])
    if must_include:
        lines.append(f"- **必考要素**: {', '.join(must_include) if isinstance(must_include, list) else must_include}")

    must_avoid = blueprint.get("must_avoid", [])
    if must_avoid:
        lines.append(f"- **禁止内容**: {', '.join(must_avoid) if isinstance(must_avoid, list) else must_avoid}")

    lines.append(f"- **选项风格**: {blueprint.get('option_style', '未指定')}")
    lines.append(f"- **推理形式**: {blueprint.get('reasoning_shape', '未指定')}")

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
