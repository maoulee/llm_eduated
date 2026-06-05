# core_new/slot_contract.py
"""SlotContract: layered constraint system for slot-template driven composition.

Converts SlotTemplate JSON into a structured Markdown contract with three layers:
- L0 Hard constraints: objective exam structure (question type, score, option count)
- L1 Strong soft constraints: statistical patterns with deviation policy
- L2 Preference constraints: scoring/ranking guidance

Usage:
    from core_new.slot_contract import build_slot_contract

    contract_md = build_slot_contract("Q12", template_dict, experience_card_md)
"""

from __future__ import annotations

from typing import Dict, Optional


def build_slot_contract(
    slot_id: str,
    template: Dict,
    experience_card_md: Optional[str] = None,
    slot_md_content: Optional[str] = None,
) -> str:
    """Build a SlotContract markdown from template and experience data.

    Args:
        slot_id: Slot identifier (e.g. "Q12").
        template: Slot template dict from slot_templates.json.
        experience_card_md: Raw experience card markdown (from data/slot_experiences/).
        slot_md_content: Raw slot knowledge doc markdown (from data/slots/).
    """
    lines = []
    lines.append(f"# slot_contract {slot_id}")
    lines.append("")

    # ── L0: Hard constraints ──────────────────────────────────
    lines.append("## 硬约束（必须遵守，违反直接拦截）")
    lines.append("")
    lines.append(f"- **slot_id**: {slot_id}")
    lines.append(f"- **section**: {template.get('section', '?')}")
    qtype = template.get('question_type', 'single_choice')
    lines.append(f"- **question_type**: {qtype}")
    lines.append(f"- **score**: {template.get('typical_score', 2)}")

    if qtype == 'single_choice':
        lines.append("- **option_count**: 4")
        lines.append("- **answer_rule**: 只能有一个正确答案")
        lines.append("- **output_format**: stem, option_A, option_B, option_C, option_D, correct_answer, explanation")
    else:
        lines.append("- **answer_rule**: 需要完整的解答过程和最终结果")
        lines.append("- **output_format**: stem, standard_answer, solution_steps, explanation")
        lines.append("- **option_style**: none")
        lines.append("- **reasoning_shape**: none")
    lines.append("")

    # ── L1: Strong soft constraints ───────────────────────────
    lines.append("## 强软约束（默认遵守，偏离需说明理由）")
    lines.append("")

    # Subject
    subj = template.get("subject_stability", "未知")
    lines.append(f"- **preferred_subject**: {subj}")

    # Difficulty — K1-K5 cognitive radar anchors
    da = template.get("difficulty_anchor", {})
    if isinstance(da, dict):
        for k_dim in ("K1", "K2", "K3", "K4", "K5"):
            mode_key = f"{k_dim}_mode"
            range_key = f"{k_dim}_range"
            mode_val = da.get(mode_key)
            range_val = da.get(range_key)
            if mode_val is not None:
                lines.append(f"- **{k_dim}_mode**: {mode_val}")
            if isinstance(range_val, list) and len(range_val) == 2:
                lines.append(f"- **{k_dim}_range**: {range_val[0]}-{range_val[1]}")
        # Fallback: if old-style difficulty_anchor present but no K1-K5, emit legacy
        if not any(f"{k}_mode" in da for k in ("K1", "K2", "K3", "K4", "K5")):
            lines.append(f"- **difficulty_mode**: {da.get('overall_mode', '?')}")
            r = da.get("overall_range", [])
            if isinstance(r, list) and len(r) == 2:
                lines.append(f"- **difficulty_reasonable_range**: {r[0]}-{r[1]}")
            lines.append(f"- **knowledge_depth_mode**: {da.get('knowledge_depth_mode', '?')}")
            lines.append(f"- **calculation_load_mode**: {da.get('calculation_load_mode', '?')}")
            lines.append(f"- **reasoning_steps_mode**: {da.get('reasoning_steps_mode', '?')}")
    lines.append("")

    # ── L2: Preference constraints ─────────────────────────────
    lines.append("## 偏好约束（尽量满足，用于排序打分）")
    lines.append("")

    # Target families
    tfd = template.get("target_family_distribution", {})
    if isinstance(tfd, dict) and tfd:
        sorted_families = sorted(tfd.items(), key=lambda x: -x[1] if isinstance(x[1], (int, float)) else 0)
        preferred = ", ".join(f"{k}({v:.0%})" if isinstance(v, float) else f"{k}({v})" for k, v in sorted_families[:3])
        lines.append(f"- **preferred_target_families**: {preferred}")

    # Paper roles
    prd = template.get("paper_role_distribution", {})
    if isinstance(prd, dict) and prd:
        sorted_roles = sorted(prd.items(), key=lambda x: -x[1] if isinstance(x[1], (int, float)) else 0)
        top_roles = [k for k, v in sorted_roles[:3]]
        lines.append(f"- **preferred_paper_roles**: {', '.join(top_roles)}")

    # Depth
    tdd = template.get("target_depth_distribution", {})
    if isinstance(tdd, dict) and tdd:
        sorted_depths = sorted(tdd.items(), key=lambda x: -x[1] if isinstance(x[1], (int, float)) else 0)
        lines.append(f"- **preferred_target_depths**: {', '.join(k for k, v in sorted_depths[:2])}")

    # Style mode
    sm = template.get("style_mode", {})
    if isinstance(sm, dict):
        parts = [f"{k}={v}" for k, v in sm.items()]
        if parts:
            lines.append(f"- **typical_style**: {', '.join(parts)}")

    lines.append("")

    # ── Deviation policy ──────────────────────────────────────
    lines.append("## 偏离策略")
    lines.append("")
    lines.append("- **allowed_deviation**: yes")
    lines.append("- **deviation_requires_reason**: yes")
    lines.append("- **major_deviation_requires_review**: yes")
    lines.append("- **hard_fail_only_if**: 题型错误, 分值错误, 多个正确答案, 无法作答, 输出格式缺失, 综合题出现选项字段, 综合题option_style不为none, 综合题reasoning_shape不为none")
    lines.append("")

    # ── Evidence ──────────────────────────────────────────────
    lines.append("## 历年证据")
    lines.append("")
    should_be = template.get("should_be", "无")
    should_not = template.get("should_not_be", "无")
    guidance = template.get("slot_guidance", "无")
    stability = template.get("stability_assessment", "无")
    gen_style = template.get("generation_style", "无")

    lines.append(f"- **should_be**: {should_be}")
    lines.append(f"- **should_not_be**: {should_not}")
    lines.append(f"- **slot_guidance**: {guidance}")
    lines.append(f"- **generation_style**: {gen_style}")
    lines.append(f"- **stability_assessment**: {stability}")
    lines.append("")

    # Attach experience card guidance sections if available
    if experience_card_md:
        # Extract mode distribution (fine-grained mode names for outline composer)
        mode_lines = []
        in_mode_dist = False
        for line in experience_card_md.split("\n"):
            if line.startswith("## 考察模式分布"):
                in_mode_dist = True
                continue
            if in_mode_dist and line.startswith("## "):
                in_mode_dist = False
            if in_mode_dist and line.strip():
                mode_lines.append(line)
        if mode_lines:
            lines.append("## 可选考察模式（从以下模式中选择 examination_mode）")
            lines.append("")
            lines.extend(mode_lines)
            lines.append("")

        # Legacy: attach 出题类型-难度指导 section if it exists
        in_guide = False
        in_detail = False
        guide_lines = []
        for line in experience_card_md.split("\n"):
            if line.startswith("## 出题类型-难度指导"):
                in_guide = True
                in_detail = False
                continue
            elif line.startswith("## 逐题分析"):
                in_detail = True
                continue
            if in_detail:
                continue
            if in_guide and line.startswith("## "):
                in_guide = False
            if in_guide:
                guide_lines.append(line)
        if guide_lines:
            lines.append("## 出题类型-难度指导（来自经验卡）")
            lines.append("")
            lines.extend(guide_lines)

    # ── Historical topic distribution (from slot.md) ───────────
    slot_summary = _extract_slot_summary(slot_md_content)
    if slot_summary:
        lines.append("## 历史考点分布")
        lines.append("")
        lines.append("> 以下是该题位历年考察的知识点分布，供选择考点时参考。")
        lines.append("")
        lines.append(slot_summary)
        lines.append("")

    # ── Mode → knowledge mapping (from experience card) ────────
    if experience_card_md:
        mode_kp_map = _extract_mode_knowledge_map(experience_card_md)
        if mode_kp_map:
            lines.append("## 模式与知识点对应")
            lines.append("")
            lines.append("> 各考察模式适合考察的知识点范围，帮助选择知识点后确定考察模式。")
            lines.append("")
            lines.extend(mode_kp_map)
            lines.append("")

    return "\n".join(lines)


def _extract_slot_summary(slot_md_content: Optional[str]) -> str:
    """Extract concise topic distribution from slot.md for compose decisions.

    Returns a formatted string with core knowledge domains and yearly topic
    distribution, or empty string if unavailable.
    """
    import re

    if not slot_md_content:
        return ""

    parts: list[str] = []

    # Extract core knowledge domains
    m = re.search(r"### 核心知识域\n(.*?)(?=\n###|\n## )", slot_md_content, re.DOTALL)
    if m:
        domain_lines = [l.strip() for l in m.group(1).strip().split("\n") if l.strip().startswith("-")]
        if domain_lines:
            parts.append("### 核心知识域")
            parts.append("")
            parts.extend(domain_lines)
            parts.append("")

    # Extract yearly topic distribution
    m = re.search(r"### 往年知识点分布\n(.*?)(?=\n###|\n## )", slot_md_content, re.DOTALL)
    if m:
        year_lines = [l.strip() for l in m.group(1).strip().split("\n") if l.strip().startswith("-")]
        if year_lines:
            parts.append("### 往年考点")
            parts.append("")
            parts.extend(year_lines)

    return "\n".join(parts)


def _extract_mode_knowledge_map(experience_card_md: str) -> list[str]:
    """Extract mode→knowledge mapping from experience card.

    For each examination mode in the card, extract its "适用知识点范围"
    field to show which knowledge points suit each mode.
    Returns a list of formatted lines, or empty list if unavailable.
    """
    import re

    result: list[str] = []
    # Match mode headings: ## 模式A: ... or ## 模式A — ...
    mode_pattern = re.compile(r"^## 模式([A-Z])[：:]\s*(.+?)$", re.MULTILINE)
    mode_starts = list(mode_pattern.finditer(experience_card_md))

    for i, m in enumerate(mode_starts):
        mode_name = m.group(2).strip()
        start = m.end()
        end = mode_starts[i + 1].start() if i + 1 < len(mode_starts) else len(experience_card_md)

        # Also stop at --- separator
        sep_match = re.search(r"\n---\n", experience_card_md[start:])
        if sep_match and start + sep_match.start() < end:
            end = start + sep_match.start()

        section = experience_card_md[start:end]

        # Extract 适用知识点范围
        kp_match = re.search(
            r"\*?\*?适用知识点范围\*?\*?[:：]\s*(.+?)(?:\n\*|\n-|\n\n|$)",
            section, re.DOTALL,
        )
        if kp_match:
            kp_text = kp_match.group(1).strip()
            # Truncate to keep concise
            if len(kp_text) > 120:
                kp_text = kp_text[:117] + "..."
            result.append(f"- **{mode_name}**: {kp_text}")

    return result
