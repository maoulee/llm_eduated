"""Document header parser — extract structured sections from agent-written markdown files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core_new.markdown_parser import _strip_thinking, _extract_sections

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

        for cn, status in _STATUS_CN_MAP.items():
            if cn in line and status in allowed_values:
                return status

        match = re.search(
            r"\b(pass|needs_fix|expression_fix|question_error|solution_error|draft|ready|solved|error)\b",
            line,
            flags=re.IGNORECASE,
        )
        if match:
            status = match.group(1).lower()
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
