"""Knowledge Profile Builder — aggregate per-knowledge-domain profiles from K ratings.

Reads per_question_k_ratings.json + slot_observations.json,
groups by target_family, and produces:
  data/knowledge_profiles/{family_slug}.md

Each profile contains:
  - K value distribution (K1-K5)
  - Common target difficulty range
  - Examination pattern distribution
  - Solving mode distribution
  - Trap type distribution
  - Parameter type distribution
  - Cross-system coupling distribution
  - High-difficulty triggers (K4+ characteristics)
  - Sample count

Usage:
    python -m core_new.doc_pipeline.knowledge_profile_builder
"""

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def _slugify(name: str) -> str:
    """Convert Chinese/mixed name to URL-safe slug."""
    slug = name.strip()
    slug = re.sub(r"[^\w一-鿿-]", "_", slug)
    slug = re.sub(r"_+", "_", slug)
    slug = slug.strip("_")
    return slug


def _pct(counter: Counter, total: int) -> dict:
    """Convert counter to percentage dict, sorted by frequency."""
    return {k: round(v / total, 2) for k, v in counter.most_common()}


def build_profiles(
    ratings_path: str = "data/per_question_k_ratings.json",
    observations_path: str = "data/slot_observations.json",
    output_dir: str = "data/knowledge_profiles",
) -> dict:
    """Build knowledge domain profiles from ratings and observations.

    Returns dict of {family_slug: profile_dict}.
    """
    # Load data
    if not os.path.exists(ratings_path):
        print(f"Ratings not found: {ratings_path}")
        return {}

    with open(ratings_path, encoding="utf-8") as f:
        ratings = json.load(f)

    if not ratings:
        print("No ratings data")
        return {}

    # Build lookup: (year, slot_id) → observation
    obs_lookup = {}
    if os.path.exists(observations_path):
        with open(observations_path, encoding="utf-8") as f:
            obs_data = json.load(f)
        for obs in obs_data.get("observations", []):
            key = f"{obs.get('year')}_{obs.get('slot_id')}"
            obs_lookup[key] = obs

    # Group ratings by target_family
    from collections import defaultdict
    by_family = defaultdict(list)

    for ev in ratings:
        family = ev.get("target_family", "未知")
        by_family[family].append(ev)

    # Build profiles
    profiles = {}
    os.makedirs(output_dir, exist_ok=True)

    for family, evals in sorted(by_family.items()):
        n = len(evals)
        slug = _slugify(family)

        # K distribution
        k_dists = {}
        for k_dim in ("K1", "K2", "K3", "K4", "K5"):
            scores = Counter(ev.get(k_dim, 1) for ev in evals)
            k_dists[k_dim] = _pct(scores, n)

        # Target difficulty range
        all_k3 = [ev.get("K3", 2) for ev in evals]
        k3_min, k3_max = min(all_k3), max(all_k3)
        target_range = f"K{k3_min}-K{k3_max}"

        # Examination pattern distribution
        exam_dist = _pct(
            Counter(ev.get("examination_pattern", "") for ev in evals if ev.get("examination_pattern")),
            n,
        )

        # Solving mode distribution
        solving_dist = _pct(
            Counter(ev.get("solving_mode", "") for ev in evals if ev.get("solving_mode")),
            n,
        )

        # Trap type distribution
        trap_dist = _pct(
            Counter(ev.get("trap_type", "") for ev in evals if ev.get("trap_type")),
            n,
        )

        # Parameter type distribution
        param_dist = _pct(
            Counter(ev.get("parameter_type", "") for ev in evals if ev.get("parameter_type")),
            n,
        )

        # Cross-system coupling distribution
        coupling_dist = _pct(
            Counter(ev.get("cross_system_coupling", "") for ev in evals if ev.get("cross_system_coupling")),
            n,
        )

        # High difficulty triggers (K4 >= 4 or K3 >= 4)
        high_diff = [ev for ev in evals if ev.get("K4", 1) >= 4 or ev.get("K3", 1) >= 4]
        high_diff_features = []
        for ev in high_diff:
            features = []
            if ev.get("K4", 1) >= 4:
                features.append(f"K4={ev['K4']}(深隐含前提)")
            if ev.get("K3", 1) >= 4:
                features.append(f"K3={ev['K3']}(长程推演)")
            exam = ev.get("examination_pattern", "")
            if exam:
                features.append(exam)
            trap = ev.get("trap_type", "")
            if trap and trap != "无":
                features.append(trap)
            high_diff_features.append({
                "year": ev.get("year"),
                "name": ev.get("primary_target_name", ""),
                "features": features,
            })

        # Knowledge points covered
        kp_list = sorted(set(ev.get("primary_target_name", "") for ev in evals))

        # Paper roles
        role_dist = _pct(
            Counter(ev.get("paper_role", "") for ev in evals),
            n,
        )

        # Build profile
        profile = {
            "family": family,
            "slug": slug,
            "sample_count": n,
            "target_range": target_range,
            "k_distribution": k_dists,
            "examination_pattern_distribution": exam_dist,
            "solving_mode_distribution": solving_dist,
            "trap_type_distribution": trap_dist,
            "parameter_type_distribution": param_dist,
            "cross_system_coupling_distribution": coupling_dist,
            "paper_role_distribution": role_dist,
            "knowledge_points": kp_list,
            "high_difficulty_triggers": high_diff_features,
        }
        profiles[slug] = profile

        # Generate MD
        md = _generate_profile_md(profile)
        md_path = os.path.join(output_dir, f"{slug}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)

    # Generate index
    _generate_index(profiles, output_dir)

    return profiles


def _generate_profile_md(profile: dict) -> str:
    """Generate a knowledge profile markdown file."""
    lines = [
        f"# {profile['family']}",
        "",
        f"## 基本信息",
        f"- **样本数**: {profile['sample_count']}道真题",
        f"- **典型难度范围**: {profile['target_range']}",
        "",
    ]

    # K distribution
    lines.append("## K值分布")
    for k_dim in ("K1", "K2", "K3", "K4", "K5"):
        dist = profile["k_distribution"].get(k_dim, {})
        if dist:
            items = ", ".join(f"{k}={v:.0%}" for k, v in dist.items())
            lines.append(f"- **{k_dim}**: {items}")
    lines.append("")

    # Examination patterns
    if profile["examination_pattern_distribution"]:
        lines.append("## 考察模式分布")
        for k, v in profile["examination_pattern_distribution"].items():
            lines.append(f"- {k}: {v:.0%}")
        lines.append("")

    # Solving modes
    if profile["solving_mode_distribution"]:
        lines.append("## 解题模式分布")
        for k, v in profile["solving_mode_distribution"].items():
            lines.append(f"- {k}: {v:.0%}")
        lines.append("")

    # Trap types
    if profile["trap_type_distribution"]:
        lines.append("## 陷阱类型分布")
        for k, v in profile["trap_type_distribution"].items():
            lines.append(f"- {k}: {v:.0%}")
        lines.append("")

    # Parameter types
    if profile["parameter_type_distribution"]:
        lines.append("## 参数类型分布")
        for k, v in profile["parameter_type_distribution"].items():
            lines.append(f"- {k}: {v:.0%}")
        lines.append("")

    # Cross-system coupling
    if profile["cross_system_coupling_distribution"]:
        lines.append("## 跨系统耦合分布")
        for k, v in profile["cross_system_coupling_distribution"].items():
            lines.append(f"- {k}: {v:.0%}")
        lines.append("")

    # Paper roles
    if profile["paper_role_distribution"]:
        lines.append("## 功能角色分布")
        for k, v in profile["paper_role_distribution"].items():
            lines.append(f"- {k}: {v:.0%}")
        lines.append("")

    # Knowledge points
    if profile["knowledge_points"]:
        lines.append("## 覆盖知识点")
        for kp in profile["knowledge_points"]:
            lines.append(f"- {kp}")
        lines.append("")

    # High difficulty triggers
    if profile["high_difficulty_triggers"]:
        lines.append("## 高难度触发条件")
        lines.append("以下题目K4>=4或K3>=4，分析其共同特征：")
        lines.append("")
        for hd in profile["high_difficulty_triggers"]:
            lines.append(f"- **{hd['year']}年 {hd['name']}**: {'、'.join(hd['features'])}")
        lines.append("")

    return "\n".join(lines)


def _generate_index(profiles: dict, output_dir: str):
    """Generate an index file listing all profiles."""
    lines = [
        "# Knowledge Profiles Index",
        "",
        f"共 {len(profiles)} 个知识领域 profile。",
        "",
        "| 领域 | 样本数 | 难度范围 |",
        "|------|--------|----------|",
    ]
    for slug, p in sorted(profiles.items(), key=lambda x: -x[1]["sample_count"]):
        lines.append(f"| [{p['family']}]({slug}.md) | {p['sample_count']} | {p['target_range']} |")
    lines.append("")

    with open(os.path.join(output_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    profiles = build_profiles()
    print(f"Built {len(profiles)} knowledge profiles:")
    for slug, p in sorted(profiles.items(), key=lambda x: -x[1]["sample_count"]):
        print(f"  {p['sample_count']}x {p['family']}")
    print(f"\nOutput: data/knowledge_profiles/")
