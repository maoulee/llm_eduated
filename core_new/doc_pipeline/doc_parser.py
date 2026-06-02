"""Document header parser — extract structured sections from agent-written markdown files."""

from __future__ import annotations

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
    """
    header = parse_doc_header(filepath)
    status = header.get("status", "")
    return str(status).strip().lower()
