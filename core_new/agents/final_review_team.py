"""FinalReview and Fixer agents for post-pipeline quality assurance."""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional

from core_new.agent_base import BaseAgent, AgentConfig
from core_new.agent_tools import SOLVER_TOOLS, SLOT_TOOLS
from core_new.prompts.final_review_prompt import FINAL_REVIEW_PROMPT
from core_new.prompts.fixer_prompt import FINAL_FIXER_PROMPT

logger = logging.getLogger(__name__)


class FinalReviewAgent(BaseAgent):
    """Comprehensive post-pipeline quality audit agent."""

    def __init__(self, gateway):
        config = AgentConfig(
            name="final_review",
            phase="final_review",
            system_prompt="你是一名严格的408考试出题终审专家。对完整题目输出进行全面质量审查。",
            output_format="text",
            enable_thinking=True,
            max_tokens=4096,
            tools=SOLVER_TOOLS,  # has python_exec for math verification
            max_tool_rounds=3,
        )
        super().__init__(config, gateway)

    def build_input(self, blackboard) -> str:
        content_to_review = blackboard.get("content_to_review", "")
        if not content_to_review:
            # Build from blackboard components
            draft_result = blackboard.get("sc_draft_result", blackboard.get("sc_design", {}))
            options_result = blackboard.get("sc_options_result", blackboard.get("sc_options", {}))
            solution_result = blackboard.get("sc_solution_result", {})
            is_sc = blackboard.get("is_sc", True)

            stem = draft_result.get("stem", "")
            parts = [f"## 题干\n{stem}"]

            if is_sc:
                parts.append("\n## 选项")
                for opt in ("A", "B", "C", "D"):
                    parts.append(f"- {opt}: {options_result.get(f'option_{opt}', '')}")
            else:
                sub_qs = draft_result.get("sub_questions", [])
                if sub_qs:
                    parts.append("\n## 子问题")
                    for i, sq in enumerate(sub_qs, 1):
                        parts.append(f"- ({i}) {sq}")

            parts.append(f"\n## 答案/解析\n{solution_result.get('explanation', '')}")
            content_to_review = "\n".join(parts)

        return FINAL_REVIEW_PROMPT.format(content_to_review=content_to_review)

    def parse_output(self, raw_output) -> Dict[str, Any]:
        text = str(raw_output).strip()
        if not text or len(text) < 20:
            return {"status": "pass", "overall_quality": 0, "issues": [], "fix_instruction": {"fix_target": "none", "fix_detail": ""}, "_raw_text": text}

        # Parse Markdown sections
        sections = _parse_md_sections(text)

        # Extract review fields
        review_text = sections.get("review", "")
        status = "pass"
        if "needs_fix" in review_text.lower():
            status = "needs_fix"

        quality = _extract_quality(review_text)
        issues_text = sections.get("issues", "无")
        fix_text = sections.get("fix_instruction", "")

        fix_target = _extract_field(fix_text, "fix_target") or "none"
        fix_detail = _extract_field(fix_text, "fix_detail") or ""

        return {
            "status": status,
            "overall_quality": quality,
            "issues": issues_text,
            "fix_instruction": {
                "fix_target": fix_target,
                "fix_detail": fix_detail,
            },
            "_raw_text": text,
        }


class FinalFixerAgent(BaseAgent):
    """Targeted repair agent based on FinalReview feedback."""

    def __init__(self, gateway):
        config = AgentConfig(
            name="final_fixer",
            phase="final_fix",
            system_prompt="你是一名408考试出题修复专家。根据终审反馈对题目进行定向修复。",
            output_format="json",
            enable_thinking=True,
            max_tokens=4096,
        )
        super().__init__(config, gateway)

    def build_input(self, blackboard) -> str:
        # Build original content from blackboard
        draft_result = blackboard.get("sc_draft_result", blackboard.get("sc_design", {}))
        options_result = blackboard.get("sc_options_result", blackboard.get("sc_options", {}))
        solution_result = blackboard.get("sc_solution_result", {})
        review_result = blackboard.get("final_review_result", {})

        stem = draft_result.get("stem", "")
        parts = [f"题干: {stem}"]

        is_sc = blackboard.get("is_sc", True)
        if is_sc:
            parts.append("选项:")
            for opt in ("A", "B", "C", "D"):
                parts.append(f"- {opt}: {options_result.get(f'option_{opt}', '')}")
        else:
            sub_qs = draft_result.get("sub_questions", [])
            if sub_qs:
                parts.append("子问题:")
                for i, sq in enumerate(sub_qs, 1):
                    parts.append(f"- ({i}) {sq}")

        parts.append(f"答案/解析: {solution_result.get('explanation', '')}")
        original_content = "\n".join(parts)

        review_issues = review_result.get("issues", "")
        fix_detail = review_result.get("fix_instruction", {}).get("fix_detail", "")

        return FINAL_FIXER_PROMPT.format(
            original_content=original_content,
            review_issues=review_issues,
            fix_detail=fix_detail,
        )

    def parse_output(self, raw_output) -> Dict[str, Any]:
        text = str(raw_output).strip()
        if not text:
            return {"status": "failed", "fix_applied": "empty output"}

        # Try JSON parse
        parsed = _try_parse_json(text)
        if parsed:
            return parsed

        return {"status": "failed", "fix_applied": f"parse error: {text[:200]}"}


# ── Helpers ──────────────────────────────────────────────────

def _parse_md_sections(text: str) -> Dict[str, str]:
    """Parse Markdown ## sections into a dict."""
    sections = {}
    current_key = None
    current_lines = []
    for line in text.split("\n"):
        if line.startswith("## "):
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = line[3:].strip().lower()
            current_lines = []
        elif current_key:
            current_lines.append(line)
    if current_key:
        sections[current_key] = "\n".join(current_lines).strip()
    return sections


def _extract_quality(text: str) -> int:
    match = re.search(r"overall_quality[*:\s]*(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0


def _extract_field(text: str, field_name: str) -> str:
    pattern = rf"\*\*{field_name}\*\*[*:\s]*(.+?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _try_parse_json(text: str) -> Optional[Dict]:
    import json
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extract from code block
    if "```json" in text:
        try:
            clean = text.split("```json\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(clean)
        except (json.JSONDecodeError, IndexError):
            pass
    # Try find first { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None
