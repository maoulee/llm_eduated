"""Document header parser — extract structured sections from agent-written markdown files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core_new.markdown_parser import _strip_thinking, _extract_sections

_H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def extract_h2_section(text: str | None, heading: str) -> str:
    """Extract content under a ## heading, preserving ### subsections.

    Returns empty string if the heading is not found or *text* is None/empty.
    """
    text = text or ""
    matches = list(_H2_RE.finditer(text))
    for i, m in enumerate(matches):
        if m.group(1).strip() == heading:
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            return text[start:end].strip()
    return ""


REVIEW_STATUSES = frozenset({"pass", "needs_fix"})
FINAL_REVIEW_STATUSES = frozenset({"pass", "expression_fix", "question_error", "solution_error"})
DOC_STATUS_VALUES = frozenset({
    "draft",
    "ready",
    "solved",
    "error",
    *REVIEW_STATUSES,
    *FINAL_REVIEW_STATUSES,
})

_STATUS_CN_MAP = {
    "通过": "pass",
    "合格": "pass",
    "无需修改": "pass",
    "需要修改": "needs_fix",
    "需修改": "needs_fix",
    "有问题": "needs_fix",
    "需要完善": "needs_fix",
    "基本通过": "needs_fix",
    "有条件通过": "needs_fix",
    "表述修正": "expression_fix",
    "格式修正": "expression_fix",
    "题目错误": "question_error",
    "设计错误": "question_error",
    "求解错误": "solution_error",
    "计算错误": "solution_error",
}


def parse_doc_header(filepath: str | Path) -> dict[str, Any]:
    """Parse ## sections from a markdown file, returning a dict.

    Uses _extract_sections (raw text between ## headings) instead of
    parse_md_sections (which expects - **key**: value format).

    Strips <think/> blocks before parsing.

    Example input (feedback.md):
        ## status
        pass

        ## summary
        题目质量良好

    Returns:
        {"status": "pass", "summary": "题目质量良好"}
    """
    text = Path(filepath).read_text(encoding="utf-8")
    text = _strip_thinking(text)
    sections = _extract_sections(text)

    # Fallback: WebGPT sometimes outputs bare headers (e.g. "status\npass")
    # instead of "## status\npass". Normalize known bare headers.
    if not sections:
        known = (
            "status", "summary", "corrections", "detailed_feedback",
            "quality_score", "improvement_suggestions", "routing_feedback",
            "issue_type", "fix_instructions", "keep_unchanged", "feedback_for_agent",
            "题干", "选项", "设计说明", "子问题", "求解过程", "最终答案",
        )
        pattern = "|".join(known)
        text = re.sub(
            rf"^(({pattern})\s*)$",
            r"## \1",
            text,
            flags=re.MULTILINE,
        )
        sections = _extract_sections(text)

    # Normalize values: strip whitespace
    result: dict[str, Any] = {}
    for key, value in sections.items():
        if isinstance(value, str):
            value = value.strip()
        result[key] = value

    return result


def parse_doc_section(filepath: str | Path, section_name: str) -> str:
    """Read a specific ## section from a markdown file.

    Returns empty string if the section doesn't exist.
    """
    sections = parse_doc_header(filepath)
    value = sections.get(section_name, "")
    return value if isinstance(value, str) else ""


# Patterns that qualify a "pass" into a conditional (non-pass) result.
# Only triggers when the qualifier appears near a pass keyword on the same line.
_PASS_QUALIFIERS_EN = re.compile(
    r"(?:with\s+suggestions?|with\s+reservations?|with\s+caveats?)",
    re.IGNORECASE,
)
_PASS_QUALIFIERS_CN = re.compile(
    r"通过.*?但|合格.*?但|通过.*?需要|合格.*?需要|有条件通过|基本通过|需要完善",
    re.IGNORECASE,
)


def normalize_doc_status(value: str, allowed: set[str] | frozenset[str] | None = None) -> str:
    """Normalize a status value and reject anything outside the allowed set."""
    allowed_values = set(allowed or DOC_STATUS_VALUES)
    text = str(value or "").strip()
    if not text:
        return ""

    cleaned = re.sub(r"[`*]", "", text).strip().lower()
    cleaned = re.sub(r"^[\-:：\s✅✔❌]+", "", cleaned)

    for line in cleaned.splitlines():
        line = re.sub(r"^[\-:：\s✅✔❌]+", "", line.strip())
        if not line:
            continue

        # CN keyword matching (ordered: longer keys first for precision)
        for cn, status in sorted(_STATUS_CN_MAP.items(), key=lambda x: -len(x[0])):
            if cn in line and status in allowed_values:
                # "pass" with qualifying language → needs_fix
                if status == "pass" and _PASS_QUALIFIERS_CN.search(line):
                    return "needs_fix" if "needs_fix" in allowed_values else ""
                return status

        match = re.search(
            r"\b(pass|needs_fix|expression_fix|question_error|solution_error|draft|ready|solved|error)\b",
            line,
            flags=re.IGNORECASE,
        )
        if match:
            status = match.group(1).lower()
            if status == "pass" and _PASS_QUALIFIERS_EN.search(line):
                return "needs_fix" if "needs_fix" in allowed_values else ""
            return status if status in allowed_values else ""

        token = re.split(r"\s+", line, maxsplit=1)[0]
        if token in allowed_values:
            return token

    return ""


def get_doc_status(filepath: str | Path, allowed: set[str] | frozenset[str] | None = None) -> str:
    """Extract the ## status field from a document.

    Returns "" if the field is missing.
    Falls back to keyword extraction if ## status is absent.
    """
    header = parse_doc_header(filepath)
    status = normalize_doc_status(header.get("status", ""), allowed)
    if status:
        return status

    # Fallback: search for status keywords in the full text
    try:
        text = Path(filepath).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""

    # Review agent: pass / needs_fix
    # Final review: pass / expression_fix / question_error / solution_error
    for pattern in (
        r"审核结论[：:]\s*[✅✔❌]*\s*\*?\*?\s*(pass|needs_fix|expression_fix|question_error|solution_error)\b",
        r"最终判定[：:]\s*[✅✔❌]*\s*\*?\*?\s*(pass|needs_fix|expression_fix|question_error|solution_error)\b",
        r"路由判定[：:]\s*[✅✔❌]*\s*\*?\*?\s*(pass|expression_fix|question_error|solution_error)\b",
        r"\*\*(?:审核结论|判定|状态|status)\*\*[：:]\s*[✅✔❌]*\s*\*?\*?\s*(pass|needs_fix|expression_fix|question_error|solution_error)\b",
        r"##\s*(?:审核结论|判定)\s*\n+\s*[✅✔❌]*\s*\*?\*?\s*(pass|needs_fix|expression_fix|question_error|solution_error)\b",
    ):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return normalize_doc_status(m.group(1), allowed)

    # Bare-header fallback: "status\n\npass" (WebGPT sometimes omits ##)
    m = re.search(
        r"(?:^|\n)\s*status\s*\n+\s*(pass|needs_fix|expression_fix|question_error|solution_error)\b",
        text, re.IGNORECASE,
    )
    if m:
        return normalize_doc_status(m.group(1), allowed)

    return ""
