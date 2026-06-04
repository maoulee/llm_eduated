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
) -> str:
    """Build a SlotContract markdown from template and experience data."""
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

    # ── Knowledge base retrieval ────────────────────────────────
    kb_text = _retrieve_kb_for_slot(slot_id, template)
    if kb_text:
        lines.append("## 大纲知识点参考（来自知识库）")
        lines.append("")
        lines.append("> 以下是从知识点库中检索到的与本题位相关的考点，供出题时参考。")
        lines.append("> 这些是大纲覆盖的考点名词，不是定义或公式。")
        lines.append("")
        lines.append(kb_text)
        lines.append("")

    return "\n".join(lines)


def _retrieve_kb_for_slot(slot_id: str, template: Dict) -> str:
    """Retrieve relevant knowledge base sections for a slot."""
    try:
        from core_new.knowledge_retrieval import retrieve_for_slot
        return retrieve_for_slot(slot_id, template)
    except Exception:
        return ""
