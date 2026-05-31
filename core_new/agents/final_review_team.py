"""FinalReview and Fixer agents for post-pipeline quality assurance."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core_new.agent_base import BaseAgent, AgentConfig
from core_new.agent_tools import SOLVER_TOOLS, SLOT_TOOLS
from core_new.markdown_parser import (
    parse_md_sections,
    try_parse_json_object,
    FieldExtractor,
)
from core_new.prompts.final_review_prompt import FINAL_REVIEW_PROMPT
from core_new.prompts.fixer_prompt import FINAL_FIXER_PROMPT

logger = logging.getLogger(__name__)

# Keywords for inferring fix target from issue text
_FIX_TARGET_KEYWORDS = {
    "stem": ["题干", "条件", "题目", "stem", "题目描述", "给定条件"],
    "answer": ["答案", "解析", "解答", "计算", "求解", "answer", "solution", "公式", "数值"],
    "options": ["选项", "干扰", "option", "distractor", "正确答案"],
    "sub_questions": ["子问题", "子题", "小问", "sub_question"],
}


def _infer_fix_target(issues_text: str, raw_text: str) -> str:
    """Infer fix_target from issue descriptions when structured field is missing."""
    combined = f"{issues_text} {raw_text[:2000]}"
    scores = {}
    for target, keywords in _FIX_TARGET_KEYWORDS.items():
        scores[target] = sum(1 for kw in keywords if kw in combined)
    if not scores or max(scores.values()) == 0:
        return "none"
    return max(scores, key=scores.get)


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
            return {
                "status": "needs_human_review",
                "overall_quality": 0,
                "issues": "FinalReview output empty or invalid",
                "fix_instruction": {"fix_target": "none", "fix_detail": "终审未返回有效输出，需要人工复核"},
                "_raw_text": text,
            }

        # Parse Markdown sections
        sections = parse_md_sections(text)
        if isinstance(sections, dict):
            review_section = sections.get("review")
            q_raw = review_section.get("overall_quality", "?") if isinstance(review_section, dict) else "no-review"
            logger.info("[FinalReview] sections=%s quality_raw=%s", list(sections.keys()), q_raw)

        # Extract review fields directly from parsed dict
        review = sections.get("review", {})
        if not isinstance(review, dict):
            review = {}

        status = review.get("status", "needs_human_review")
        if not isinstance(status, str):
            status = str(status)
        if "needs_fix" in status.lower():
            status = "needs_fix"
        elif "pass" in status.lower():
            status = "pass"
        else:
            status = "needs_human_review"

        quality_val = review.get("overall_quality", 0)
        quality = int(quality_val) if isinstance(quality_val, (int, float, str)) and str(quality_val).strip().isdigit() else FieldExtractor.quality(str(review))

        issues_val = sections.get("issues", "无")
        if isinstance(issues_val, dict):
            issues_text = "\n".join(f"- **{k}**: {v}" for k, v in issues_val.items()) if issues_val else "无"
        elif isinstance(issues_val, list):
            issues_text = "\n".join(f"- {item}" for item in issues_val) if issues_val else "无"
        else:
            issues_text = str(issues_val) if issues_val else "无"

        # Fallback: parse_md_sections may lose plain-text issues (no **key**: value)
        if issues_text == "无" and "## issues" in text:
            import re
            parts = re.split(r"## issues", text, maxsplit=1)
            if len(parts) > 1:
                after = re.split(r"## ", parts[1])
                raw_issues = after[0].strip()
                if raw_issues and raw_issues != "无":
                    issues_text = raw_issues

        fix = sections.get("fix_instruction", {})
        if isinstance(fix, dict):
            fix_target = fix.get("fix_target", "none") or "none"
            fix_detail = fix.get("fix_detail", "") or ""
        else:
            fix_target = FieldExtractor.fix_target(str(fix)) if fix else "none"
            fix_detail = FieldExtractor.fix_detail(str(fix)) if fix else ""

        # ── Consistency enforcement ──
        # If issues found but status is pass → force needs_fix
        if issues_text and issues_text != "无" and status == "pass":
            logger.warning("[FinalReview] Issues found but status=pass, overriding to needs_fix")
            status = "needs_fix"

        # If quality is low → force needs_fix
        if quality < 6 and status == "pass":
            status = "needs_fix"

        # If status=needs_fix but fix_target=none → force a target from issues
        if status == "needs_fix" and fix_target == "none":
            inferred = _infer_fix_target(issues_text, text)
            if inferred != "none":
                fix_target = inferred
                logger.info("[FinalReview] Inferred fix_target=%s from issues", fix_target)
            else:
                logger.warning("[FinalReview] needs_fix but fix_target=none and cannot infer")

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
        parsed = try_parse_json_object(text)
        if parsed:
            return parsed

        return {"status": "failed", "fix_applied": f"parse error: {text[:200]}"}
