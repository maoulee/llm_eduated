"""Convert slot extraction JSON results into MD experience cards.

Reads: data/slot_observations.json, data/slot_templates.json, data/type_difficulty_guides.json
Writes: data/slot_experiences/Q{NN}_experience.md for each slot

Usage:
    .venv/bin/python generate_slot_experiences.py
"""

import json
import os
from collections import defaultdict


def format_observation(o: dict) -> str:
    """Format a single SlotObservation as markdown."""
    lines = []
    lines.append(f"### {o.get('year', '?')}-{o.get('slot_id', '?')}")
    lines.append("")

    # Primary target
    lines.append(f"- **考点**: {o.get('primary_target_name', 'N/A')} ({o.get('primary_target_type', '?')})")
    lines.append(f"- **知识领域**: {o.get('target_family', 'N/A')}")
    if o.get("supporting_targets"):
        lines.append(f"- **辅助考点**: {o['supporting_targets']}")
    if o.get("prerequisite_targets"):
        lines.append(f"- **前置知识**: {o['prerequisite_targets']}")

    # Difficulty
    lines.append("")
    lines.append(f"- **难度**: {o.get('difficulty_overall', '?')}/5")
    lines.append(
        f"  - 知识深度={o.get('difficulty_knowledge_depth', '?')} "
        f"机制深度={o.get('difficulty_mechanism_depth', '?')} "
        f"推理步数={o.get('difficulty_reasoning_steps', '?')} "
        f"计算量={o.get('difficulty_calculation_load', '?')} "
        f"陷阱强度={o.get('difficulty_trap_strength', '?')} "
        f"跨章节={o.get('difficulty_cross_topic', '?')}"
    )
    if o.get("difficulty_reason"):
        lines.append(f"  - 理由: {o['difficulty_reason']}")

    # Role
    lines.append(f"- **功能角色**: {o.get('paper_role', 'N/A')}")
    if o.get("paper_role_reason"):
        lines.append(f"  - {o['paper_role_reason']}")

    # Answer analysis
    lines.append("")
    if o.get("why_correct"):
        lines.append(f"- **答案分析**: {o['why_correct']}")
    if isinstance(o.get("why_wrong_options"), dict):
        lines.append("- **错误选项**:")
        for opt, reason in o["why_wrong_options"].items():
            lines.append(f"  - {opt}: {reason}")
    if o.get("solution_steps"):
        steps = o["solution_steps"]
        if isinstance(steps, str):
            steps = steps.split(";")
        lines.append(f"- **解题步骤**: {' → '.join(s.strip() for s in steps)}")

    # Distractors
    if o.get("distractor_patterns"):
        dp = o["distractor_patterns"]
        if isinstance(dp, list):
            lines.append(f"- **干扰项模式**: {', '.join(dp)}")

    # Style
    lines.append("")
    lines.append(
        f"- **风格**: 题干={o.get('stem_length', '?')} 条件数={o.get('condition_count', '?')} "
        f"选项={o.get('option_style', '?')} 推理={o.get('reasoning_shape', '?')}"
    )
    if o.get("trap_style"):
        lines.append(f"  - 陷阱: {o['trap_style']}")

    return "\n".join(lines)


def format_template(t: dict) -> str:
    """Format SlotTemplate as markdown."""
    lines = []
    lines.append(f"## 题位模板")
    lines.append("")
    lines.append(f"- **题位**: {t.get('slot_id', '?')}")
    lines.append(f"- **题型**: {t.get('question_type', '?')} ({t.get('section', '?')})")
    lines.append(f"- **分值**: {t.get('typical_score', '?')}")
    lines.append(f"- **科目稳定性**: {t.get('subject_stability', '?')}")
    lines.append("")

    if isinstance(t.get("subject_distribution"), dict):
        lines.append("### 科目分布")
        for subj, freq in t["subject_distribution"].items():
            pct = f"{freq:.0%}" if isinstance(freq, float) else str(freq)
            lines.append(f"- {subj}: {pct}")
        lines.append("")

    if isinstance(t.get("target_family_distribution"), dict):
        lines.append("### 考点领域分布")
        for fam, freq in t["target_family_distribution"].items():
            pct = f"{freq:.0%}" if isinstance(freq, float) else str(freq)
            lines.append(f"- {fam}: {pct}")
        lines.append("")

    if isinstance(t.get("target_depth_distribution"), dict):
        lines.append("### 考察深度分布")
        for depth, freq in t["target_depth_distribution"].items():
            pct = f"{freq:.0%}" if isinstance(freq, float) else str(freq)
            lines.append(f"- {depth}: {pct}")
        lines.append("")

    if isinstance(t.get("paper_role_distribution"), dict):
        lines.append("### 功能角色分布")
        for role, freq in t["paper_role_distribution"].items():
            pct = f"{freq:.0%}" if isinstance(freq, float) else str(freq)
            lines.append(f"- {role}: {pct}")
        lines.append("")

    if isinstance(t.get("difficulty_anchor"), dict):
        lines.append("### 难度锚点")
        da = t["difficulty_anchor"]
        for k, v in da.items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    if t.get("slot_guidance"):
        lines.append("### 出题指导")
        lines.append(f"{t['slot_guidance']}")
        lines.append("")

    if t.get("should_be"):
        lines.append(f"- **应该是**: {t['should_be']}")
    if t.get("should_not_be"):
        lines.append(f"- **不应是**: {t['should_not_be']}")
    if t.get("generation_style"):
        lines.append(f"- **生成风格**: {t['generation_style']}")
    if t.get("stability_assessment"):
        lines.append(f"- **稳定性评价**: {t['stability_assessment']}")

    return "\n".join(lines)


def format_guide(g: dict) -> str:
    """Format TypeDifficultyGuide as markdown."""
    lines = []
    lines.append("## 出题类型-难度指导")
    lines.append("")
    lines.append(f"- **Guide ID**: {g.get('guide_id', '?')}")
    lines.append(f"- **科目**: {g.get('subject', '?')}")
    lines.append(f"- **深度**: {g.get('target_depth', '?')}")
    lines.append(f"- **难度**: {g.get('difficulty', '?')}")
    lines.append(f"- **功能角色**: {g.get('paper_role', '?')}")
    lines.append("")

    if isinstance(g.get("expected_shape"), dict):
        lines.append("### 预期形态")
        for k, v in g["expected_shape"].items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    if isinstance(g.get("suitable_targets"), list):
        lines.append(f"### 适合考点")
        for t in g["suitable_targets"]:
            lines.append(f"- {t}")
        lines.append("")

    if isinstance(g.get("distractor_style"), list):
        lines.append(f"### 干扰项风格")
        for d in g["distractor_style"]:
            lines.append(f"- {d}")
        lines.append("")

    if isinstance(g.get("bad_examples"), list):
        lines.append(f"### 不应出现的特征")
        for b in g["bad_examples"]:
            lines.append(f"- {b}")
        lines.append("")

    return "\n".join(lines)


def generate_experience_card(
    slot_id: str,
    observations: list,
    template: dict,
    guide: dict,
) -> str:
    """Generate a complete MD experience card for one slot."""
    lines = []
    lines.append(f"# {slot_id} 题位经验 ({len(observations)}年汇总)")
    lines.append("")

    # Template section
    if template:
        lines.append(format_template(template))
        lines.append("")

    # Guide section
    if guide:
        lines.append(format_guide(guide))
        lines.append("")

    # Observations section
    lines.append("## 逐题分析")
    lines.append("")

    # Sort by year
    sorted_obs = sorted(observations, key=lambda x: x.get("year", 0))
    for o in sorted_obs:
        lines.append(format_observation(o))
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def main():
    base_dir = "data"
    out_dir = os.path.join(base_dir, "slot_experiences")
    os.makedirs(out_dir, exist_ok=True)

    # Load JSON results
    with open(os.path.join(base_dir, "slot_observations.json"), encoding="utf-8") as f:
        obs_data = json.load(f)
    with open(os.path.join(base_dir, "slot_templates.json"), encoding="utf-8") as f:
        tpl_data = json.load(f)
    with open(os.path.join(base_dir, "type_difficulty_guides.json"), encoding="utf-8") as f:
        guide_data = json.load(f)

    observations = obs_data.get("observations", [])
    templates = tpl_data.get("templates", {})
    guides = guide_data.get("guides", {})

    # Group observations by slot_id
    obs_by_slot = defaultdict(list)
    for o in observations:
        sid = o.get("slot_id", "unknown")
        obs_by_slot[sid].append(o)

    # Generate MD cards
    all_slots = sorted(set(list(obs_by_slot.keys()) + list(templates.keys())))
    generated = 0

    for slot_id in all_slots:
        slot_obs = obs_by_slot.get(slot_id, [])
        slot_tpl = templates.get(slot_id, {})

        # Find matching guide
        slot_guide = {}
        for gid, g in guides.items():
            if slot_id in gid or g.get("guide_id", "").endswith(slot_id.lower()):
                slot_guide = g
                break
        # Fallback: use first guide if none matched
        if not slot_guide and guides:
            slot_guide = list(guides.values())[0]

        md_content = generate_experience_card(slot_id, slot_obs, slot_tpl, slot_guide)

        out_path = os.path.join(out_dir, f"{slot_id}_experience.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"  {slot_id}: {len(slot_obs)} observations → {out_path}")
        generated += 1

    # Generate index
    index_path = os.path.join(out_dir, "README.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("# 题位经验卡索引\n\n")
        for slot_id in all_slots:
            obs_count = len(obs_by_slot.get(slot_id, []))
            tpl = templates.get(slot_id, {})
            stability = tpl.get("subject_stability", "N/A") if tpl else "N/A"
            guidance = tpl.get("should_be", "N/A") if tpl else "N/A"
            f.write(f"## [{slot_id}]({slot_id}_experience.md)\n")
            f.write(f"- 数据量: {obs_count}年\n")
            f.write(f"- 科目: {stability}\n")
            f.write(f"- 定位: {guidance}\n\n")

    print(f"\nGenerated {generated} experience cards in {out_dir}/")
    print(f"Index: {index_path}")


if __name__ == "__main__":
    main()
