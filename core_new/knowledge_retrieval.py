"""Knowledge base retrieval for slot composition.

Searches the 408 computer organization knowledge base (思维导图式知识点库)
to find relevant exam points for a given slot's knowledge requirements.

Usage:
    from core_new.knowledge_retrieval import retrieve_knowledge
    results = retrieve_knowledge("虚拟存储器 TLB Cache 地址映射")
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

_KB_PATH = Path(__file__).resolve().parent.parent / "data" / "computer_organization.md"
_kb_cache: Optional[str] = None
_kb_sections: Optional[list[tuple[str, str]]] = None


def _load_kb() -> str:
    global _kb_cache
    if _kb_cache is None:
        if _KB_PATH.exists():
            _kb_cache = _KB_PATH.read_text(encoding="utf-8")
        else:
            _kb_cache = ""
    return _kb_cache


def _parse_sections(kb_text: str) -> list[tuple[str, str]]:
    """Parse knowledge base into (header_path, content) sections.

    Each section is identified by its full header path like
    "CO-3 存储器 > 主存储器 > SRAM和DRAM".
    """
    global _kb_sections
    if _kb_sections is not None:
        return _kb_sections

    sections: list[tuple[str, str]] = []
    header_stack: list[str] = []
    current_lines: list[str] = []

    for line in kb_text.split("\n"):
        m = re.match(r"^(#{1,6})\s+(.+)", line)
        if m:
            # Save previous section
            if header_stack:
                path = " > ".join(header_stack)
                sections.append((path, "\n".join(current_lines).strip()))

            level = len(m.group(1))
            title = m.group(2).strip()
            # Pop stack to current level
            header_stack = header_stack[: level - 1]
            header_stack.append(title)
            current_lines = []
        else:
            if header_stack:
                current_lines.append(line)

    # Last section
    if header_stack:
        path = " > ".join(header_stack)
        sections.append((path, "\n".join(current_lines).strip()))

    _kb_sections = sections
    return sections


def _extract_leaf_topics(content: str) -> list[str]:
    """Extract leaf topic names from a section's content."""
    topics = []
    for line in content.split("\n"):
        m = re.match(r"^\s*-\s+(.+?)(?:\s*$|\s+\(属性)", line)
        if m:
            topics.append(m.group(1).strip())
    return topics


def retrieve_knowledge(
    query: str,
    top_sections: int = 3,
    max_chars: int = 2000,
) -> str:
    """Search the knowledge base for topics matching the query.

    Returns a formatted string with relevant knowledge sections,
    suitable for injection into slot contracts or prompts.
    """
    kb_text = _load_kb()
    if not kb_text:
        return ""

    sections = _parse_sections(kb_text)
    if not sections:
        return ""

    # Tokenize query into keywords
    keywords = re.split(r"[,\s、，]+", query.strip())
    keywords = [k for k in keywords if len(k) >= 2]

    if not keywords:
        return ""

    # Score each section by keyword matches
    scored: list[tuple[int, str, str]] = []
    for header_path, content in sections:
        score = 0
        full_text = header_path + " " + content
        for kw in keywords:
            count = full_text.count(kw)
            # Weight header matches more heavily
            header_count = header_path.count(kw)
            score += header_count * 3 + count
        if score > 0:
            scored.append((score, header_path, content))

    scored.sort(key=lambda x: -x[0])

    # Build result
    result_parts: list[str] = []
    total_chars = 0

    for score, header_path, content in scored[:top_sections]:
        section_text = f"### {header_path}\n{content}"
        if total_chars + len(section_text) > max_chars:
            break
        result_parts.append(section_text)
        total_chars += len(section_text)

    if not result_parts:
        return ""

    return "\n\n".join(result_parts)


def retrieve_for_slot(slot_id: str, slot_template: dict) -> str:
    """Retrieve knowledge relevant to a specific slot.

    Uses the slot's subject, knowledge points, and guidance to
    build a search query.
    """
    # Build query from slot metadata
    parts: list[str] = []

    subject = slot_template.get("subject_stability", "")
    if subject:
        parts.append(subject)

    guidance = slot_template.get("slot_guidance", "")
    if guidance:
        parts.append(guidance)

    must_include = slot_template.get("must_include", "")
    if must_include:
        parts.append(must_include)

    # Extract CO-X section hint from slot_id range
    # Q1-Q11: basic concepts, Q12-Q22: data representation, etc.
    slot_num = 0
    m = re.match(r"Q(\d+)", slot_id)
    if m:
        slot_num = int(m.group(1))

    # Map slot ranges to likely CO sections
    co_hints = []
    if slot_num <= 11:
        co_hints.append("计算机系统概述")
    if 1 <= slot_num <= 15:
        co_hints.extend(["数据表示", "运算器"])
    if 12 <= slot_num <= 25:
        co_hints.extend(["存储器", "主存储器", "Cache"])
    if 20 <= slot_num <= 30:
        co_hints.extend(["指令系统", "指令格式"])
    if 25 <= slot_num <= 35:
        co_hints.extend(["CPU", "中央处理器", "流水线"])
    if 30 <= slot_num <= 42:
        co_hints.extend(["总线", "I/O", "中断", "DMA"])
    if slot_num >= 43:
        co_hints.extend(["综合", "虚拟存储", "TLB", "Cache", "流水线"])

    query = " ".join(parts + co_hints)

    return retrieve_knowledge(query, top_sections=3, max_chars=2000)
