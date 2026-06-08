"""Outline contract parser — extract active_selection from outline_approved.md."""

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


def parse_outline_contracts(outline_md: str) -> list[SlotContract]:
    """从 outline_approved.md 抽取每题的机器契约。"""
    contracts: list[SlotContract] = []
    parts = re.split(r"## (Q\d+)", outline_md)

    for i in range(1, len(parts), 2):
        slot_id = parts[i]
        content = parts[i + 1] if i + 1 < len(parts) else ""

        yaml_data = _extract_yaml_block(content)
        if not yaml_data:
            continue

        # excluded is nested: {modes: [], knowledge: []}
        excluded_data = yaml_data.get("excluded") or {}
        if isinstance(excluded_data, list):
            excluded_data = {}

        contracts.append(SlotContract(
            slot_id=slot_id,
            question_type=yaml_data.get("question_type", "single_choice"),
            score=yaml_data.get("score", 2),
            examination_mode=yaml_data.get("examination_mode", ""),
            active_selection=yaml_data.get("active_selection", {}),
            candidate_pool_visible=yaml_data.get("candidate_pool_visible", []),
            excluded_modes=excluded_data.get("modes", []),
            excluded_knowledge=excluded_data.get("knowledge", []),
        ))

    return contracts


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
        selection.append(entry)

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(selection, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _extract_yaml_block(content: str) -> dict:
    """Extract first ```yaml code block from slot content."""
    m = re.search(r"###\s*机器(?:选择)?契约\s*\n```(?:yaml|yml)\s*\n(.*?)```", content, re.DOTALL)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}
