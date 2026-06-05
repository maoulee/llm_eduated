# core_new/slot_contract.py
"""SlotContract: concise slot info for the compose (outline) agent.

Builds a streamlined markdown per slot with:
- 考点定位 (subject + radar shape)
- 可选考察模式 (mode name + frequency + 3-line summary for SC / full for COMP)
- 出题指导 (should_be / should_not_be / suggested distribution)

Usage:
    from core_new.slot_contract import build_slot_contract

    contract_md = build_slot_contract("Q12", template_dict, experience_card_md)
"""

from __future__ import annotations

import re
from typing import Dict, Optional


def build_slot_contract(
    slot_id: str,
    template: Dict,
    experience_card_md: Optional[str] = None,
    slot_md_content: Optional[str] = None,
) -> str:
    """Build concise slot contract markdown for the compose agent.

    Args:
        slot_id: Slot identifier (e.g. "Q12").
        template: Slot template dict from slot_templates.json.
        experience_card_md: Raw experience card markdown (from data/slot_experiences/).
        slot_md_content: Unused (kept for API compatibility).
    """
    lines: list[str] = []

    qtype = template.get("question_type", "single_choice")
    qtype_label = "选择题" if qtype == "single_choice" else "综合应用题"
    score = template.get("typical_score", 2)

    lines.append(f"# {slot_id} — {qtype_label} · {score}分")
    lines.append("")

    # ── 考点定位 ──────────────────────────────────────────────
    lines.append("## 考点定位")
    lines.append("")
    subj = template.get("subject_stability", "未知")
    # Map subject_stability to display subject
    if subj == "跨领域":
        lines.append("- **科目**: 计算机组成原理（跨知识域）")
    else:
        lines.append(f"- **科目**: 计算机组成原理（{subj}）")
    radar = template.get("radar_shape", "")
    if radar:
        lines.append(f"- **典型雷达**: {radar}")
    lines.append("")

    # ── 可选考察模式 ──────────────────────────────────────────
    if experience_card_md:
        is_comp = qtype == "comprehensive"
        if is_comp:
            _append_comp_modes(lines, experience_card_md)
        else:
            _append_sc_modes(lines, experience_card_md)

    # ── 出题指导 ──────────────────────────────────────────────
    if experience_card_md:
        guidance = _extract_guidance(experience_card_md)
        if guidance:
            lines.append("## 出题指导")
            lines.append("")
            lines.extend(guidance)
            lines.append("")

    return "\n".join(lines)


# ── SC mode extraction ────────────────────────────────────────

def _append_sc_modes(lines: list[str], exp_card: str) -> None:
    """Append concise mode sections for single-choice slots."""
    # 1. Get mode distribution (name → frequency)
    dist = _extract_mode_distribution(exp_card)

    # 2. Get full mode sections
    mode_sections = _extract_mode_sections(exp_card)

    if not mode_sections:
        return

    lines.append("## 可选考察模式")
    lines.append("")

    for mode_letter, mode_heading_name, content in mode_sections:
        # Find frequency from distribution
        freq_str = _match_frequency(mode_heading_name, dist)

        # Build heading
        if freq_str:
            lines.append(f"### 模式{mode_letter}: {mode_heading_name} ({freq_str})")
        else:
            lines.append(f"### 模式{mode_letter}: {mode_heading_name}")
        lines.append("")

        # Extract 3 key fields: 考察方式, 适用知识点范围, 难度范围
        for field in ("考察方式", "适用知识点范围", "难度范围"):
            val = _extract_field_from_section(content, field)
            if val:
                display_name = "适用知识点" if field == "适用知识点范围" else (
                    "难度" if field == "难度范围" else field)
                if len(val) > 150:
                    val = val[:147] + "..."
                lines.append(f"- **{display_name}**: {val}")
        lines.append("")


def _extract_mode_distribution(exp_card: str) -> list[tuple[str, str]]:
    """Extract mode distribution entries as (name, freq_str) pairs.

    Returns list of ("计算型——单结果/多结果竞争", "7/13, 53.8%") etc.
    """
    results: list[tuple[str, str]] = []
    in_dist = False
    for line in exp_card.split("\n"):
        if line.strip().startswith("## 考察模式分布"):
            in_dist = True
            continue
        if in_dist and line.startswith("## "):
            in_dist = False
        if in_dist and line.strip().startswith("- **"):
            m = re.match(r"- \*\*(.+?)\*\*[：:]\s*(.+)", line.strip())
            if m:
                results.append((m.group(1).strip(), m.group(2).strip()))
    return results


def _extract_mode_sections(exp_card: str) -> list[tuple[str, str, str]]:
    """Extract full mode sections from experience card.

    Returns list of (letter, heading_name, content_text).
    E.g. ("A", "计算型——公式应用与单位换算", "- **考察方式**: ...\n...")
    """
    results: list[tuple[str, str, str]] = []
    mode_pattern = re.compile(r"^## 模式([A-Z])[：:]\s*(.+?)$", re.MULTILINE)
    mode_starts = list(mode_pattern.finditer(exp_card))

    for i, m in enumerate(mode_starts):
        letter = m.group(1)
        heading_name = m.group(2).strip()
        start = m.end()
        end = mode_starts[i + 1].start() if i + 1 < len(mode_starts) else len(exp_card)

        # Stop at --- separator
        sep = re.search(r"\n---\n", exp_card[start:])
        if sep and start + sep.start() < end:
            end = start + sep.start()

        content = exp_card[start:end].strip()
        results.append((letter, heading_name, content))

    return results


def _match_frequency(mode_heading_name: str, dist: list[tuple[str, str]]) -> str:
    """Match a mode section heading to its frequency in the distribution.

    The distribution uses names like "计算型——单结果/多结果竞争",
    while mode sections use names like "计算型——公式应用与单位换算".
    We match on shared prefix (before ——) + shared keywords.
    """
    if not dist:
        return ""

    # Strategy 1: exact match
    for name, freq in dist:
        if name == mode_heading_name:
            return freq

    # Strategy 2: match by prefix (before —— or —)
    def prefix(s: str) -> str:
        return s.split("——")[0].split("—")[0].strip()

    mode_prefix = prefix(mode_heading_name)
    for name, freq in dist:
        if prefix(name) == mode_prefix:
            return freq

    # Strategy 3: keyword overlap
    mode_words = set(re.findall(r"[一-鿿]+", mode_heading_name))
    best_match = None
    best_score = 0
    for name, freq in dist:
        name_words = set(re.findall(r"[一-鿿]+", name))
        score = len(mode_words & name_words)
        if score > best_score:
            best_score = score
            best_match = freq

    return best_match or ""


def _extract_field_from_section(section: str, field_name: str) -> str:
    """Extract a single field value from a mode section."""
    # Match patterns like: - **考察方式**: value  or  - **考察方式**: value
    patterns = [
        rf"\*?\*?{re.escape(field_name)}\*?\*?\s*[：:]\s*(.+?)(?:\n- \*\*|\n\n|\Z)",
        rf"\*?\*?{re.escape(field_name)}\*?\*?\s*[：:]\s*(.+?)(?:\n|$)",
    ]
    for pat in patterns:
        m = re.search(pat, section, re.DOTALL)
        if m:
            val = m.group(1).strip()
            # If empty after colon, try next line (nested bullet)
            if not val:
                rest = section[m.end():]
                next_line = rest.split("\n")[1] if "\n" in rest else ""
                if next_line.strip():
                    val = next_line.strip()
            # Clean up multiline values — take first meaningful line
            val = val.split("\n")[0].strip()
            # Strip leading "- " from nested bullets
            if val.startswith("- "):
                val = val[2:].strip()
            return val
    return ""


# ── COMP mode extraction ──────────────────────────────────────

def _append_comp_modes(lines: list[str], exp_card: str) -> None:
    """Append full mode sections for comprehensive slots."""
    # Extract from ## 考察结构模式 → ### 模式A/B/C
    struct_match = re.search(
        r"## 考察结构模式\n(.*?)(?=\n## |\Z)", exp_card, re.DOTALL
    )
    if not struct_match:
        return

    struct_text = struct_match.group(1).strip()
    if not struct_text:
        return

    lines.append("## 可选考察模式")
    lines.append("")
    lines.append(struct_text)
    lines.append("")


# ── Guidance extraction ───────────────────────────────────────

def _extract_guidance(exp_card: str) -> list[str]:
    """Extract 出题指导 section as a list of formatted lines."""
    m = re.search(r"## 出题指导\n(.*?)(?=\n## |\Z)", exp_card, re.DOTALL)
    if not m:
        return []

    content = m.group(1).strip()
    result: list[str] = []

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # Skip the slot_synthesis program-parsed section
        if stripped.startswith("- **K1_mode**"):
            break
        if stripped.startswith("## slot_synthesis"):
            break
        # Clean up nested bullet formatting
        if stripped.startswith("- **should_be**:") or stripped.startswith("- **should_not_be**:"):
            # Extract the value after the colon
            val_m = re.match(r"- \*\*(should_be|should_not_be)\*\*[：:]\s*", stripped)
            if val_m:
                val = stripped[val_m.end():]
                label = "应该" if "should_be" in val_m.group(0) else "避免"
                # Handle nested list
                if val:
                    result.append(f"- **{label}**: {val.lstrip('- ').strip()}")
        elif stripped.startswith("- **建议"):
            result.append(stripped)
        elif stripped.startswith("- "):
            result.append(stripped)
        elif stripped.startswith("  "):
            # Nested item under should_be / should_not_be
            result.append(stripped)
        else:
            result.append(stripped)

    return result
