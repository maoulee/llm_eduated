"""Outline contract parser — extract active_selection from outline_approved.md.

Delegates to markdown_contract_parser for unified parsing.
Legacy functions kept as thin wrappers for backward compatibility.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml


@dataclass
class SlotContract:
    slot_id: str
    question_type: str
    score: int
    examination_mode: str
    active_selection: dict = field(default_factory=dict)
    candidate_pool_visible: list[str] = field(default_factory=list)
    excluded_modes: list[str] = field(default_factory=list)
    excluded_knowledge: list[str] = field(default_factory=list)
    teacher_annotation: str = ""


def parse_outline_contracts(outline_md: str) -> list[SlotContract]:
    """从 outline_approved.md 抽取每题的机器契约。

    Uses markdown_contract_parser for robust CONTRACT marker + legacy parsing.
    """
    from compose.markdown_contract_parser import parse_outline_to_selection
    result = parse_outline_to_selection(outline_md)
    return result.slots


def write_paper_selection(contracts: list[SlotContract], output_path: str) -> None:
    """写 paper_selection.yaml。"""
    selection = []
    for c in contracts:
        entry = {
            "slot_id": c.slot_id,
            "question_type": c.question_type,
            "score": c.score,
            "examination_mode": c.examination_mode,
            "active_selection": c.active_selection,
        }
        if c.candidate_pool_visible:
            entry["candidate_pool_visible"] = c.candidate_pool_visible
        if c.excluded_modes:
            entry["excluded_modes"] = c.excluded_modes
        if c.excluded_knowledge:
            entry["excluded_knowledge"] = c.excluded_knowledge
        if c.teacher_annotation:
            entry["teacher_annotation"] = c.teacher_annotation
        selection.append(entry)

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(selection, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _extract_yaml_block(content: str) -> dict:
    """Deprecated: use markdown_contract_parser instead."""
    from compose.markdown_contract_parser import scan_contract_blocks, load_yaml_contract
    blocks = scan_contract_blocks(content)
    for block in blocks:
        loaded = load_yaml_contract(block)
        if loaded.data:
            return loaded.data
    return {}


def _extract_teacher_annotation(content: str) -> str:
    """Deprecated: use markdown_contract_parser instead."""
    m = re.search(
        r"###\s*教师可编辑说明[^\n]*\n(.*?)(?=\n###|\n## |\Z)",
        content,
        re.DOTALL,
    )
    if not m:
        return ""
    return m.group(1).strip()
