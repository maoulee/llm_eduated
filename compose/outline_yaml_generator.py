"""Outline YAML generator — Convert teacher-selected slot cards to outline_draft.md.

This module implements the Python-side YAML generation for compose routes.
Pure template filling, no LLM involved.
"""

from __future__ import annotations

from typing import Any


def generate_outline_from_cards(selected_cards: list[dict], templates: dict) -> str:
    """Generate outline_draft.md from teacher-confirmed slot_cards.

    Args:
        selected_cards: List of slot_card dicts (teacher selected/confirmed)
        templates: Slot templates dict {slot_id: {type, score, ...}}

    Returns:
        outline_draft.md string with CONTRACT markers and YAML blocks
    """
    lines = ["# 试卷大纲\n"]
    lines.append("## 整体规划\n")
    lines.append("- **difficulty_target**: 3\n")
    lines.append("- **composition_rationale**: 基于教师选择的经验模式组卷\n")
    lines.append("\n")

    for card in selected_cards:
        slot_data = card.get("slot_card", {})
        slot_id = slot_data.get("slot_id", "")

        if not slot_id:
            continue

        # Get template info
        template = templates.get(slot_id, {})
        q_type = template.get("type", slot_data.get("type", "single_choice"))
        score = template.get("score", slot_data.get("score", 2))

        # Build human-readable sections
        lines.append(f"## {slot_id}（{q_type}）\n")
        lines.append("### 当前推荐\n")
        lines.append(f"- **考察模式**: {slot_data.get('recommended_mode', '')}\n")
        lines.append(f"- **核心知识点**: {', '.join(slot_data.get('applicable_knowledge', []))}\n")
        lines.append(f"- **推荐理由**: 频率最高 {slot_data.get('recommended_frequency', '')}\n")
        lines.append("\n")

        lines.append("### 候选替换池\n")
        for alt in slot_data.get("alternatives", []):
            lines.append(f"- {alt.get('mode', '')}: {alt.get('frequency', '')}\n")
        lines.append("\n")

        lines.append("### 教师可编辑说明\n")
        lines.append("（教师可直接修改的命题说明区）\n")
        lines.append("\n")

        # CONTRACT marker + YAML block
        lines.append(f"<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot={slot_id} -->\n")
        lines.append("```yaml\n")
        lines.extend(_build_yaml_lines(slot_data, template, slot_id))
        lines.append("```\n")
        lines.append(f"<!-- CONTRACT:END slot={slot_id} -->\n")
        lines.append("\n")

    return "".join(lines)


def _build_yaml_lines(slot_data: dict, template: dict, slot_id: str) -> list[str]:
    """Build YAML contract lines for a single slot."""
    lines = []

    # Basic fields
    q_type = template.get("type", slot_data.get("type", "single_choice"))
    score = template.get("score", slot_data.get("score", 2))
    subject = slot_data.get("target_subject", "")
    family = slot_data.get("target_family", "")
    primary = slot_data.get("primary_target_name",
                           slot_data.get("applicable_knowledge", [""])[0] if slot_data.get("applicable_knowledge") else "")

    lines.append(f"slot_id: {slot_id}\n")
    lines.append(f"question_type: {q_type}\n")
    lines.append(f"score: {score}\n")

    if subject:
        lines.append(f"target_subject: {subject}\n")
    if family:
        lines.append(f"target_family: {family}\n")
    if primary:
        lines.append(f"primary_target_name: {primary}\n")

    # Difficulty
    difficulty = slot_data.get("target_difficulty", template.get("target_difficulty", 3))
    lines.append(f"target_difficulty: {difficulty}\n")

    # K target
    k_target = slot_data.get("k_target", "")
    if k_target:
        lines.append(f"k_target: {k_target}\n")

    # Examination mode
    exam_mode = slot_data.get("recommended_mode", "")
    if exam_mode:
        lines.append(f"examination_mode: {exam_mode}\n")

    # Active selection
    lines.append("active_selection:\n")
    mode_id = slot_data.get("mode_id", "推荐模式")
    lines.append(f"  mode_id: {mode_id}\n")
    lines.append(f"  mode_name: {exam_mode}\n")

    knowledge = slot_data.get("applicable_knowledge", [])
    if knowledge:
        lines.append("  selected_knowledge:\n")
        for k in knowledge:
            lines.append(f"    - {k}\n")

    # Candidate pool
    alternatives = slot_data.get("alternatives", [])
    if alternatives or exam_mode:
        lines.append("candidate_pool_visible:\n")
        if exam_mode:
            lines.append(f"  - {exam_mode}\n")
        for alt in alternatives:
            lines.append(f"  - {alt.get('mode', '')}\n")

    # Excluded
    lines.append("excluded:\n")
    lines.append("  modes: []\n")
    lines.append("  knowledge: []\n")

    return lines


def generate_from_topic_mode(topic_card: dict, slot_id: str, template: dict) -> str:
    """Generate outline section from topic_mode_card (Route 2).

    Args:
        topic_card: topic_mode_card dict with modes and selected mode
        slot_id: Slot identifier (Q12, TOPIC_001, etc.)
        template: Slot template {type, score, ...}

    Returns:
        Markdown section with CONTRACT marker
    """
    lines = [f"## {slot_id}（{template.get('type', 'single_choice')}）\n"]
    lines.append("### 当前推荐\n")
    lines.append(f"- **考察模式**: {topic_card.get('title', '')}\n")
    lines.append(f"- **知识点**: {topic_card.get('knowledge', '')}\n")
    lines.append("\n")

    lines.append("### 候选替换池\n")
    for mode in topic_card.get("modes", []):
        lines.append(f"- {mode.get('name', '')}: {mode.get('count', 0)}题\n")
    lines.append("\n")

    lines.append("### 教师可编辑说明\n")
    lines.append("（教师可直接修改的命题说明区）\n")
    lines.append("\n")

    # CONTRACT marker
    lines.append(f"<!-- CONTRACT:BEGIN type=outline_slot schema=outline_v2 slot={slot_id} -->\n")
    lines.append("```yaml\n")
    lines.extend(_build_topic_yaml_lines(topic_card, template, slot_id))
    lines.append("```\n")
    lines.append(f"<!-- CONTRACT:END slot={slot_id} -->\n")
    lines.append("\n")

    return "".join(lines)


def _build_topic_yaml_lines(topic_card: dict, template: dict, slot_id: str) -> list[str]:
    """Build YAML contract lines from topic_mode_card."""
    lines = []

    q_type = template.get("type", "single_choice")
    score = template.get("score", 2)
    knowledge = topic_card.get("knowledge", "")

    lines.append(f"slot_id: {slot_id}\n")
    lines.append(f"question_type: {q_type}\n")
    lines.append(f"score: {score}\n")
    lines.append(f"primary_target_name: {knowledge}\n")

    # Use first source info if available
    sources = topic_card.get("sources", [])
    if sources:
        kg_node = sources[0].get("kg_node", "") if isinstance(sources[0], dict) else ""
        if kg_node:
            lines.append(f"target_family: {kg_node}\n")

    lines.append(f"target_difficulty: 3\n")

    # Selected mode (first one as default)
    modes = topic_card.get("modes", [])
    if modes:
        selected = modes[0]
        lines.append(f"examination_mode: {selected.get('name', '')}\n")

        lines.append("active_selection:\n")
        lines.append(f"  mode_id: {selected.get('name', '')}\n")
        lines.append(f"  mode_name: {selected.get('name', '')}\n")

        # Extract knowledge from description or use topic knowledge
        desc = selected.get("description", "")
        if desc:
            lines.append("  selected_knowledge:\n")
            lines.append(f"    - {knowledge}\n")

        # All modes as candidate pool
        lines.append("candidate_pool_visible:\n")
        for m in modes:
            lines.append(f"  - {m.get('name', '')}\n")

    lines.append("excluded:\n")
    lines.append("  modes: []\n")
    lines.append("  knowledge: []\n")

    return lines
