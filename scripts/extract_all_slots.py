"""Extract slot templates and experience cards for ALL 408 subjects.

Reads question_experiences/ (2058 files), groups by Q-number,
generates slot_templates.json entries and per-slot experience cards.

408 Exam Structure:
  数据结构:     Q1-Q11  (选择),  Q41-Q42 (综合)
  计算机组成原理: Q12-Q22 (选择),  Q43-Q45 (综合)
  操作系统:     Q23-Q32 (选择),  Q46-Q47 (综合)
  计算机网络:   Q33-Q40 (选择)
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

EXP_DIR = Path("data/question_experiences")
OUTPUT_TPL = Path("data/slot_templates_all.json")
OUTPUT_EXP_DIR = Path("data/slot_experiences_all")

# 408 standard slot → subject mapping
SLOT_SUBJECT_MAP = {
    **{f"Q{i}": "数据结构" for i in range(1, 12)},
    **{f"Q{i}": "计算机组成原理" for i in range(12, 23)},
    **{f"Q{i}": "操作系统" for i in range(23, 33)},
    **{f"Q{i}": "计算机网络" for i in range(33, 41)},
    **{f"Q{i}": "数据结构" for i in range(41, 43)},
    **{f"Q{i}": "计算机组成原理" for i in range(43, 46)},
    **{f"Q{i}": "操作系统" for i in range(46, 48)},
}

QUESTION_TYPE_MAP = {}
for i in range(1, 41):
    QUESTION_TYPE_MAP[f"Q{i}"] = "single_choice"
for i in range(41, 48):
    QUESTION_TYPE_MAP[f"Q{i}"] = "comprehensive"

SCORE_MAP = {**{f"Q{i}": 2 for i in range(1, 41)}, **{f"Q{i}": 10 for i in range(41, 48)}}


def parse_experience(filepath: str) -> dict:
    """Parse a single question experience file."""
    with open(filepath, encoding="utf-8") as f:
        text = f.read()

    info = {"raw_text": text, "filepath": filepath}

    # Extract basic info
    m = re.search(r"\*\*年份\*\*:\s*(\d+)\s+\*\*题位\*\*:\s*Q(\d+)\s+\*\*题型\*\*:\s*(\S+)", text)
    if m:
        info["year"] = int(m.group(1))
        info["qnum"] = int(m.group(2))
        info["qtype"] = m.group(3)

    # Extract subject
    m = re.search(r"\*\*科目\*\*:\s*(.+)", text)
    if m:
        info["subject"] = m.group(1).strip()

    # Extract knowledge points
    m = re.search(r"\*\*知识点\*\*:\s*(.+)", text)
    if m:
        info["knowledge"] = m.group(1).strip()

    # Extract K-values
    k_values = {}
    for k in range(1, 6):
        m = re.search(rf"K{k}\s*=\s*(\d+)", text)
        if m:
            k_values[f"K{k}"] = int(m.group(1))
    info["k_values"] = k_values

    # Extract exam pattern
    m = re.search(r"\*\*模式\*\*:\s*(.+)", text)
    if m:
        info["pattern"] = m.group(1).strip()

    # Extract radar shape
    m = re.search(r"\*\*雷达形状\*\*:\s*(.+)", text)
    if m:
        info["radar_shape"] = m.group(1).strip()

    # Extract stem
    m = re.search(r"## 题干原文\n+(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if m:
        info["stem"] = m.group(1).strip()[:500]

    return info


def extract_k_stats(entries: list[dict]) -> dict:
    """Extract K-value statistics from a list of parsed experiences."""
    k_data = defaultdict(list)
    for e in entries:
        for k, v in e.get("k_values", {}).items():
            k_data[k].append(v)

    result = {}
    for k in ["K1", "K2", "K3", "K4", "K5"]:
        vals = k_data.get(k, [])
        if vals:
            from statistics import mode as stat_mode
            try:
                k_mode = stat_mode(vals)
            except:
                k_mode = max(set(vals), key=vals.count)
            result[f"{k}_mode"] = k_mode
            result[f"{k}_range"] = [min(vals), max(vals)]
        else:
            result[f"{k}_mode"] = 2
            result[f"{k}_range"] = [1, 4]
    return result


def extract_pattern_distribution(entries: list[dict]) -> dict:
    """Extract pattern distribution."""
    patterns = Counter()
    for e in entries:
        p = e.get("pattern", "")
        if p:
            patterns[p] += 1
    total = sum(patterns.values())
    if total == 0:
        return {"概念型": 1.0}
    return {p: c / total for p, c in patterns.most_common(10)}


def extract_subject_distribution(entries: list[dict], slot_id: str) -> dict:
    """Extract subject distribution from entries."""
    subjects = Counter()
    for e in entries:
        subj = e.get("subject", SLOT_SUBJECT_MAP.get(slot_id, "未知"))
        # Normalize
        if "数据结构" in subj:
            subjects["数据结构"] += 1
        elif "网络" in subj:
            subjects["计算机网络"] += 1
        elif "操作" in subj:
            subjects["操作系统"] += 1
        elif "组成" in subj or "CO-" in subj:
            subjects["计算机组成原理"] += 1
        else:
            # Use slot mapping as fallback
            mapped = SLOT_SUBJECT_MAP.get(slot_id, "未知")
            subjects[mapped] += 1

    total = sum(subjects.values())
    if total == 0:
        return {SLOT_SUBJECT_MAP.get(slot_id, "未知"): 1.0}
    return {s: c / total for s, c in subjects.most_common(5)}


def extract_knowledge_family(entries: list[dict]) -> str:
    """Extract dominant knowledge family from entries."""
    families = Counter()
    for e in entries:
        kn = e.get("knowledge", "")
        if kn:
            # Take first component as family
            parts = re.split(r"[,，>]", kn)
            if parts:
                families[parts[0].strip()] += 1
    if families:
        return families.most_common(1)[0][0]
    return "综合"


def build_slot_template(slot_id: str, entries: list[dict]) -> dict:
    """Build a slot template from collected experience entries."""
    subj_dist = extract_subject_distribution(entries, slot_id)
    dominant_subject = max(subj_dist, key=subj_dist.get) if subj_dist else "未知"
    k_stats = extract_k_stats(entries)
    pattern_dist = extract_pattern_distribution(entries)

    # Determine depth distribution from K-values
    k1_vals = [e.get("k_values", {}).get("K1", 2) for e in entries if e.get("k_values")]
    knowledge_pct = sum(1 for v in k1_vals if v <= 2) / max(len(k1_vals), 1)
    mechanism_pct = sum(1 for v in k1_vals if v >= 4) / max(len(k1_vals), 1)
    pattern_pct = 1 - knowledge_pct - mechanism_pct
    depth_dist = {
        "knowledge": round(knowledge_pct, 2),
        "pattern": round(max(pattern_pct, 0), 2),
        "mechanism": round(mechanism_pct, 2),
    }

    # Determine reasoning shape distribution
    reasoning_shapes = Counter()
    for e in entries:
        shape = e.get("radar_shape", "")
        if "计算" in shape:
            reasoning_shapes["计算型"] += 1
        elif "概念" in shape or "认知" in shape:
            reasoning_shapes["概念型"] += 1
        elif "陷阱" in shape:
            reasoning_shapes["陷阱型"] += 1
        elif "联动" in shape or "跨域" in shape:
            reasoning_shapes["联动型"] += 1
        else:
            reasoning_shapes["综合型"] += 1

    reasoning_dist = {}
    total_r = sum(reasoning_shapes.values()) or 1
    for shape, cnt in reasoning_shapes.most_common(5):
        reasoning_dist[shape] = round(cnt / total_r, 2)

    return {
        "slot_id": slot_id,
        "section": "选择题" if slot_id.startswith("Q") and int(slot_id[1:]) <= 40 else "综合应用题",
        "question_type": QUESTION_TYPE_MAP.get(slot_id, "single_choice"),
        "typical_score": SCORE_MAP.get(slot_id, 2),
        "subject_stability": dominant_subject,
        "subject_distribution": subj_dist,
        "target_family_distribution": subj_dist,
        "target_depth_distribution": depth_dist,
        "paper_role_distribution": {"foundation_check": 0.4, "trap_diagnosis": 0.3, "calculation_stability": 0.3},
        "difficulty_anchor": k_stats,
        "style_mode": {
            "option_style": "数字结果" if "计算" in str(pattern_dist) else "概念判断",
            "reasoning_shape": list(pattern_dist.keys())[0] if pattern_dist else "概念型",
            "stem_length": "medium",
        },
        "radar_shape": entries[0].get("radar_shape", "") if entries else "",
        "reasoning_shape_mode": " / ".join(list(pattern_dist.keys())[:3]) if pattern_dist else "",
        "reasoning_shape_distribution": reasoning_dist,
        "pattern_count": str(len(set(e.get("pattern", "") for e in entries))),
        "should_be": "",
        "should_not_be": "",
        "stability_assessment": f"基于{len(entries)}道真题分析",
    }


def build_experience_card(slot_id: str, entries: list[dict]) -> str:
    """Build an experience card markdown for a slot."""
    lines = [f"# {slot_id} 题位经验卡\n"]
    lines.append(f"基于 {len(entries)} 道真题分析\n")

    # Group by pattern
    pattern_groups = defaultdict(list)
    for e in entries:
        p = e.get("pattern", "未知")
        pattern_groups[p].append(e)

    for pattern, group in sorted(pattern_groups.items(), key=lambda x: -len(x[1])):
        lines.append(f"\n## 模式: {pattern} ({len(group)}题)\n")
        for e in sorted(group, key=lambda x: x.get("year", 0)):
            year = e.get("year", "?")
            kn = e.get("knowledge", "")
            kv = e.get("k_values", {})
            stem = e.get("stem", "")[:200]
            lines.append(f"### {year}年 {slot_id} — {kn}\n")
            if kv:
                lines.append(f"K值: " + ", ".join(f"{k}={v}" for k, v in kv.items()))
            if e.get("radar_shape"):
                lines.append(f"雷达: {e['radar_shape']}")
            if stem:
                lines.append(f"\n题干摘要: {stem}\n")

    return "\n".join(lines)


def main():
    # Parse all experiences
    print("解析题库经验文件...")
    all_entries = []
    for fname in sorted(os.listdir(EXP_DIR)):
        if not fname.endswith(".md"):
            continue
        entry = parse_experience(os.path.join(EXP_DIR, fname))
        if entry.get("qnum"):
            entry["slot_id"] = f"Q{entry['qnum']}"
            all_entries.append(entry)

    print(f"共解析 {len(all_entries)} 条经验")

    # Group by slot_id
    slot_entries = defaultdict(list)
    for e in all_entries:
        sid = e["slot_id"]
        slot_entries[sid].append(e)

    print(f"覆盖 {len(slot_entries)} 个题位: {sorted(slot_entries.keys())}")

    # Build templates and experience cards
    templates = {}
    os.makedirs(OUTPUT_EXP_DIR, exist_ok=True)

    for sid in sorted(slot_entries.keys()):
        entries = slot_entries[sid]
        # Build template
        tpl = build_slot_template(sid, entries)
        templates[sid] = tpl

        # Build experience card
        card = build_experience_card(sid, entries)
        card_path = OUTPUT_EXP_DIR / f"{sid}_experience.md"
        card_path.write_text(card, encoding="utf-8")

        subj = tpl["subject_stability"]
        n = len(entries)
        print(f"  {sid}: {subj} ({n}题) — {tpl['section']}")

    # Save templates
    output = {
        "metadata": {
            "source": "question_experiences",
            "total_experiences": len(all_entries),
            "total_slots": len(templates),
            "subjects": list(set(SLOT_SUBJECT_MAP.values())),
        },
        "templates": templates,
    }

    OUTPUT_TPL.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TPL.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    # Also print subject summary
    print("\n=== 科目覆盖 ===")
    subj_slots = defaultdict(list)
    for sid, tpl in templates.items():
        subj_slots[tpl["subject_stability"]].append(sid)
    for subj, slots in sorted(subj_slots.items()):
        print(f"  {subj}: {len(slots)} slots — {', '.join(slots)}")

    print(f"\nSlot模板写入: {OUTPUT_TPL}")
    print(f"经验卡写入: {OUTPUT_EXP_DIR}/")


if __name__ == "__main__":
    main()
