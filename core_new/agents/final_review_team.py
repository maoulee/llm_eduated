"""FinalReview and Fixer agents for post-pipeline quality assurance."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core_new.agent_base import BaseAgent, AgentConfig
from core_new.agent_tools import CONTEXT_AWARE_TOOLS, SOLVER_TOOLS, SLOT_TOOLS
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
            required_fields=["status", "overall_quality", "issues"],
            repair_on_parse_failure=True,
            repair_max_retries=1,
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
            output_format="markdown",
            enable_thinking=True,
            max_tokens=4096,
            tools=CONTEXT_AWARE_TOOLS,
            max_tool_rounds=3,
            context_sources={
                "sc_design": "题目设计（stem, sub_questions, given_conditions 等）",
                "sc_options_result": "选项内容（option_A~D，仅选择题）",
                "sc_solution_result": "格式化答案（explanation, answer 等）",
                "solver_result": "求解器输出（computed_results, code 等）",
                "final_review_result": "终审结果（status, quality, issues, fix_instruction 等）",
            },
            required_fields=["status", "fix_applied"],
            repair_on_parse_failure=True,
            repair_max_retries=1,
        )
        super().__init__(config, gateway)

    def build_input(self, blackboard) -> str:
        review_result = blackboard.get("final_review_result", {})
        review_issues = review_result.get("issues", "")
        fix_detail = review_result.get("fix_instruction", {}).get("fix_detail", "")
        fix_target = review_result.get("fix_instruction", {}).get("fix_target", "none")

        catalog = self._context_catalog_text()

        return FINAL_FIXER_PROMPT.format(
            original_content="(请通过 read_context 工具获取)",
            review_issues=review_issues,
            fix_detail=fix_detail,
        ) + "\n\n" + catalog + f"\n\n修复目标: {fix_target}"

    def parse_output(self, raw_output) -> Dict[str, Any]:
        text = str(raw_output).strip()
        if not text:
            return {"status": "failed", "fix_applied": "empty output"}

        # 1. JSON backward compat
        parsed = try_parse_json_object(text)
        if parsed:
            return parsed

        # 2. Markdown sections parse
        sections = parse_md_sections(text)
        fix_result = sections.get("fix_result", {})
        fixed_content = sections.get("fixed_content", {})

        if not fix_result and not fixed_content:
            return {"status": "failed", "fix_applied": "parse error: no fix_result section found"}

        result: Dict[str, Any] = {}

        # Extract status
        if isinstance(fix_result, dict):
            status_val = str(fix_result.get("status", "failed")).lower()
            result["status"] = "ok" if status_val in ("ok", "success", "applied") else status_val
            result["fix_applied"] = fix_result.get("fix_applied", "")
            # Top-level fixed fields (LLM may flatten into fix_result)
            for key in ("fixed_stem", "fixed_answer", "fixed_options", "fixed_sub_questions"):
                if fix_result.get(key):
                    result[key] = fix_result[key]
        else:
            result["status"] = "failed"
            result["fix_applied"] = ""

        # Extract fixed_content section
        if isinstance(fixed_content, dict):
            for key in ("fixed_stem", "fixed_answer", "fixed_options", "fixed_sub_questions"):
                if fixed_content.get(key) and key not in result:
                    result[key] = fixed_content[key]

        # Fallback: extract raw text between ## fixed_content and next ## header
        _has_fixed_field = any(k in result for k in ("fixed_stem", "fixed_answer", "fixed_options", "fixed_sub_questions"))
        if not _has_fixed_field and "## fixed_content" in text:
            import re
            parts = re.split(r"## fixed_content", text, maxsplit=1)
            if len(parts) > 1:
                after = re.split(r"## ", parts[1])
                raw_body = after[0].strip()
                if raw_body:
                    fix_target = ""
                    if isinstance(fix_result, dict):
                        fix_target = str(fix_result.get("fix_target", ""))
                    if "stem" in fix_target:
                        result["fixed_stem"] = raw_body
                    elif "answer" in fix_target:
                        result["fixed_answer"] = raw_body
                    elif "option" in fix_target:
                        result["fixed_options"] = raw_body
                    else:
                        result["fixed_content_raw"] = raw_body

        # Warn if status=ok but no actual fixed content
        if result.get("status") == "ok":
            has_fix = any(k in result for k in ("fixed_stem", "fixed_answer", "fixed_options", "fixed_sub_questions", "fixed_content_raw"))
            if not has_fix:
                logger.warning("[FinalFixer] status=ok but no fixed content fields found, downgrading to failed")
                result["status"] = "failed"
                result["fix_applied"] = "LLM reported ok but produced no fixable content"

        return result
