"""Document header parser — extract structured sections from agent-written markdown files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core_new.markdown_parser import _strip_thinking, _extract_sections


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


def get_doc_status(filepath: str | Path) -> str:
    """Extract the ## status field from a document.

    Returns "" if the field is missing.
    Falls back to keyword extraction if ## status is absent.
    """
    header = parse_doc_header(filepath)
    status = header.get("status", "")
    status = str(status).strip().lower()
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
            return m.group(1).lower()

    # Bare-header fallback: "status\n\npass" (WebGPT sometimes omits ##)
    m = re.search(
        r"(?:^|\n)\s*status\s*\n+\s*(pass|needs_fix|expression_fix|question_error|solution_error)\b",
        text, re.IGNORECASE,
    )
    if m:
        return m.group(1).lower()

    return ""
