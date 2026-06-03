"""Slot extractor — two-layer trajectory extraction via local vLLM.

Phase 1: Per-question trajectory extraction (LLM batch)
  slot_observations.json (165 questions)
  → SLOT_SINGLE_EVAL_PROMPT per question
  → generate_text_batch via local vLLM
  → Parse Markdown → data/per_question_k_ratings.json + data/question_experiences/*.md

Phase 2: Per-slot structural pattern synthesis (LLM batch)
  per_question trajectories grouped by slot_id
  → SLOT_SYNTHESIS_PROMPT per slot
  → generate_text_batch via local vLLM
  → Parse Markdown → slot_templates.json + slots/*.md + slot_experiences/*.md

Usage:
    python slot_extractor.py
    python slot_extractor.py --slots Q14 Q15
    python slot_extractor.py --concurrency 16
    python slot_extractor.py --eval-only
    python slot_extractor.py --resume
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(__file__))

from core_new.llm_gateway import LLMGateway
from core_new.prompts.cognitive_radar import COGNITIVE_RADAR_SCALE
from core_new.slot_prompts import (
    _SYLLABUS_REF,
    SLOT_SINGLE_EVAL_PROMPT_SC,
    SLOT_SINGLE_EVAL_PROMPT_COMP,
    SLOT_SYNTHESIS_PROMPT_SC,
    SLOT_SYNTHESIS_PROMPT_COMP,
)


# ── Markdown parser ────────────────────────────────────────────

def parse_markdown_fields(text: str, section: str = "evaluation") -> Dict[str, str]:
    """Parse '## section\n- **key**: value' format from LLM output."""
    fields: Dict[str, str] = {}
    in_section = False

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(f"## {section}"):
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if not in_section:
            continue

        m = re.match(r"-\s+\*\*(.+?)\*\*:\s*(.+)", stripped)
        if m:
            fields[m.group(1).strip()] = m.group(2).strip()

    return fields


def parse_k_score(value: str) -> int:
    """Extract integer K score from value like '3 — 理由' or just '3'."""
    m = re.match(r"(\d+)", value.strip())
    if m:
        return max(1, min(5, int(m.group(1))))
    return 1


def parse_k_range(value: str) -> List[int]:
    """Extract [min, max] range from value like '[2, 4] — 理由'."""
    m = re.search(r"\[(\d+)\s*,\s*(\d+)\]", value)
    if m:
        return [int(m.group(1)), int(m.group(2))]
    return [1, 5]



# ── Phase 1: Per-question K1-K5 evaluation ─────────────────────

def format_single_eval_message(obs: Dict) -> List[Dict]:
    """Format a single observation into a chat message, branching by question type."""
    q_type = obs.get("question_type", "single_choice")

    if q_type == "single_choice":
        prompt = SLOT_SINGLE_EVAL_PROMPT_SC.format(
            cognitive_radar_scale=COGNITIVE_RADAR_SCALE,
            _syllabus_ref=_SYLLABUS_REF,
            year=obs.get("year", "?"),
            slot_id=obs.get("slot_id", "?"),
            primary_target_name=obs.get("primary_target_name", "?"),
            target_family=obs.get("target_family", "?"),
            question_type="选择题",
            question_stem=obs.get("question_stem", "（题干未收录）"),
            why_correct=obs.get("why_correct", "?"),
            why_wrong_options=obs.get("why_wrong_options", "{}"),
            distractor_patterns=obs.get("distractor_patterns", "[]"),
            trap_style=obs.get("trap_style", "无"),
            option_style=obs.get("option_style", "?"),
            reasoning_shape=obs.get("reasoning_shape", "?"),
            stem_length=obs.get("stem_length", "?"),
            condition_count=obs.get("condition_count", "?"),
            paper_role=obs.get("paper_role", "?"),
            paper_role_reason=obs.get("paper_role_reason", "?"),
        )
    else:
        prompt = SLOT_SINGLE_EVAL_PROMPT_COMP.format(
            cognitive_radar_scale=COGNITIVE_RADAR_SCALE,
            _syllabus_ref=_SYLLABUS_REF,
            year=obs.get("year", "?"),
            slot_id=obs.get("slot_id", "?"),
            primary_target_name=obs.get("primary_target_name", "?"),
            target_family=obs.get("target_family", "?"),
            question_type="综合应用题",
            question_stem=obs.get("question_stem", "（题干未收录）"),
            why_correct=obs.get("why_correct", "?"),
            solution_steps=obs.get("solution_steps", "?"),
            trap_style=obs.get("trap_style", "无"),
            reasoning_shape=obs.get("reasoning_shape", "?"),
            paper_role=obs.get("paper_role", "?"),
            paper_role_reason=obs.get("paper_role_reason", "?"),
        )
    return [{"role": "user", "content": prompt}]


def parse_section_lines(text: str, section_header: str) -> List[str]:
    """Extract all lines under a ## section until the next ## section."""
    lines = []
    in_section = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped == f"## {section_header}":
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section:
            lines.append(stripped)
    return lines


def parse_trajectory(raw: str, section: str = "考察轨迹") -> List[str]:
    """Parse numbered steps from a trajectory section."""
    steps = []
    for line in parse_section_lines(raw, section):
        m = re.match(r"\d+\.\s*(.+)", line)
        if m:
            steps.append(m.group(1).strip())
    return steps


def parse_trap_options(raw: str) -> Dict[str, str]:
    """Parse option-level trap descriptions from 陷阱机制 section."""
    traps = {}
    for line in parse_section_lines(raw, "陷阱机制"):
        m = re.match(r"-\s*\*\*选项([A-Z])\*\*:\s*(.+)", line)
        if m:
            traps[m.group(1)] = m.group(2).strip()
    return traps


def parse_eval_result(raw: str, obs: Dict) -> Dict:
    """Parse phase 1 LLM output into a structured evaluation."""
    fields = parse_markdown_fields(raw, "evaluation")
    q_type = obs.get("question_type", "single_choice")

    result = {
        "year": obs.get("year"),
        "slot_id": obs.get("slot_id"),
        "primary_target_name": obs.get("primary_target_name"),
        "target_family": obs.get("target_family"),
        "paper_role": obs.get("paper_role"),
        "question_type": q_type,
        "question_stem": obs.get("question_stem", ""),
    }

    # K1-K5 scores with reasons (shared)
    for k_dim in ("K1", "K2", "K3", "K4", "K5"):
        val = fields.get(k_dim, "1")
        result[k_dim] = parse_k_score(val)
        result[f"{k_dim}_reason"] = val

    result["radar_shape_name"] = fields.get("radar_shape_name", "")
    result["reasoning_shape"] = fields.get("reasoning_shape", obs.get("reasoning_shape", ""))
    result["reasoning_shape_reason"] = fields.get("reasoning_shape_reason", "")

    # Knowledge points and syllabus mapping — from separate section
    kp_fields = parse_markdown_fields(raw, "知识点与考纲")
    result["knowledge_points"] = kp_fields.get("知识点", obs.get("primary_target_name", ""))
    result["syllabus_mapping"] = kp_fields.get("考纲对应", "")

    if q_type == "single_choice":
        # SC: option-level analysis, examination mode
        option_lines = parse_section_lines(raw, "选项级分析")
        result["option_analysis"] = {}
        result["distractor_strategy"] = ""
        result["distractor_strategy_desc"] = ""
        for line in option_lines:
            m_opt = re.match(r"-\s*\*\*选项([A-Z])\*\*:\s*(.+)", line)
            m_strat = re.match(r"-\s*\*\*干扰策略\*\*:\s*(.+)", line)
            m_strat_desc = re.match(r"-\s*\*\*干扰策略说明\*\*:\s*(.+)", line)
            if m_opt:
                result["option_analysis"][m_opt.group(1)] = m_opt.group(2).strip()
            elif m_strat:
                result["distractor_strategy"] = m_strat.group(1).strip()
            elif m_strat_desc:
                result["distractor_strategy_desc"] = m_strat_desc.group(1).strip()

        # Examination mode
        mode_fields = parse_markdown_fields(raw, "考察模式")
        result["mode_label"] = mode_fields.get("mode_label", "")
        result["mode_name"] = mode_fields.get("mode_name", "")
        result["mode_reason"] = mode_fields.get("mode_reason", "")

        # No trajectory for choice questions
        result["trajectory"] = []
        result["key_point"] = ""
        result["sub_q_dependency"] = ""
        result["condition_utilization"] = ""
    else:
        # COMP: trajectory, sub-question dependency, condition utilization
        result["trajectory"] = parse_trajectory(raw, "解题轨迹") if raw else []

        key_point_lines = parse_section_lines(raw, "关键考察点")
        result["key_point"] = "\n".join(l for l in key_point_lines if l).strip()

        # Sub-question dependency
        subq_fields = parse_markdown_fields(raw, "子问依赖")
        result["sub_q_count"] = subq_fields.get("sub_q_count", "")
        result["sub_q_dependency"] = subq_fields.get("dependency_type", "")
        subq_lines = parse_section_lines(raw, "子问依赖")
        result["sub_questions"] = []
        for line in subq_lines:
            m = re.match(r"-\s*\*\*sub_q(\d+)\*\*:\s*(.+)", line)
            if m:
                result["sub_questions"].append({"q": int(m.group(1)), "desc": m.group(2).strip()})

        # Condition utilization
        cond_lines = parse_section_lines(raw, "条件利用映射")
        result["condition_utilization"] = "\n".join(l for l in cond_lines if l).strip()

        # No option analysis for comprehensive
        result["option_analysis"] = {}
        result["distractor_strategy"] = ""
        result["distractor_strategy_desc"] = ""
        result["mode_label"] = ""
        result["mode_name"] = ""
        result["mode_reason"] = ""

    # Trap mechanism (shared) — section header differs by type
    trap_header = "核心陷阱" if q_type == "single_choice" else "陷阱机制"
    trap_lines = parse_section_lines(raw, trap_header)
    result["core_trap"] = ""
    result["wrong_path"] = ""
    for line in trap_lines:
        m_core = re.match(r"-\s*\*\*核心陷阱\*\*:\s*(.+)", line)
        m_wrong = re.match(r"-\s*\*\*错误路径\*\*:\s*(.+)", line)
        if m_core:
            result["core_trap"] = m_core.group(1).strip()
        elif m_wrong:
            result["wrong_path"] = m_wrong.group(1).strip()

    # Examination ability (shared)
    ability_lines = parse_section_lines(raw, "考察能力")
    result["examination_ability"] = "\n".join(l for l in ability_lines if l).strip()

    return result


# ── Phase 2: Per-slot synthesis ─────────────────────────────────

def format_synthesis_message(slot_id: str, evals: List[Dict], obs_list: List[Dict]) -> List[Dict]:
    """Format per-slot synthesis prompt, branching by question type."""
    first_obs = obs_list[0] if obs_list else {}
    q_type = first_obs.get("question_type", "single_choice")
    subject_stability = _infer_subject_stability(obs_list)
    typical_score = 2 if q_type == "single_choice" else 10

    # Build evaluations text
    eval_lines = []
    for ev in evals:
        year = ev.get('year', '?')
        name = ev.get('primary_target_name', '?')
        stem = ev.get('question_stem', '（题干未收录）')
        k_str = f"K1={ev['K1']}, K2={ev['K2']}, K3={ev['K3']}, K4={ev['K4']}, K5={ev['K5']}"

        parts = [
            f"### {year}年 — {name}",
            f"- **K值**: {k_str}",
            f"- **雷达形状**: {ev.get('radar_shape_name', '?')}",
            f"- **知识点**: {ev.get('knowledge_points', '?')}",
            f"- **考纲对应**: {ev.get('syllabus_mapping', '?')}",
        ]

        if q_type == "single_choice":
            # SC: option-level analysis + examination mode
            opt_analysis = ev.get('option_analysis', {})
            if opt_analysis:
                parts.append("- **选项分析**:")
                for opt_key in sorted(opt_analysis.keys()):
                    parts.append(f"  - 选项{opt_key}: {opt_analysis[opt_key]}")

            distractor = ev.get('distractor_strategy', '')
            if distractor:
                parts.append(f"- **干扰策略**: {distractor}")
            mode_name = ev.get('mode_name', '')
            if mode_name:
                parts.append(f"- **考察模式**: {mode_name}")
        else:
            # COMP: trajectory + sub-question dependency
            trajectory = ev.get('trajectory', [])
            if trajectory:
                parts.append("- **解题轨迹**:")
                for i, step in enumerate(trajectory, 1):
                    parts.append(f"  {i}. {step}")

            subq_dep = ev.get('sub_q_dependency', '')
            if subq_dep:
                parts.append(f"- **子问依赖**: {subq_dep}")

        core_trap = ev.get('core_trap', '')
        if core_trap:
            parts.append(f"- **核心陷阱**: {core_trap}")
        ability = ev.get('examination_ability', '')
        if ability:
            parts.append(f"- **考察能力**: {ability}")

        # Always include stem for reference
        parts.append(f"- **题干原文**: {stem}")

        eval_lines.append("\n".join(parts))

    evaluations_data = "\n\n".join(eval_lines)

    # Year range
    years = sorted(ev.get('year', 0) for ev in evals)
    year_range = f"{years[0]}-{years[-1]}" if years else "N/A"

    # Select prompt by type
    if q_type == "single_choice":
        prompt = SLOT_SYNTHESIS_PROMPT_SC.format(
            slot_id=slot_id,
            subject_stability=subject_stability,
            typical_score=typical_score,
            question_count=len(evals),
            evaluations_data=evaluations_data,
        )
    else:
        prompt = SLOT_SYNTHESIS_PROMPT_COMP.format(
            slot_id=slot_id,
            subject_stability=subject_stability,
            typical_score=typical_score,
            question_count=len(evals),
            year_range=year_range,
            evaluations_data=evaluations_data,
        )
    return [{"role": "user", "content": prompt}]


def parse_synthesis_result(raw: str, slot_id: str) -> Dict:
    """Parse phase 2 LLM output into a slot template."""
    fields = parse_markdown_fields(raw, "slot_synthesis")

    difficulty_anchor = {}
    for k_dim in ("K1", "K2", "K3", "K4", "K5"):
        mode_val = fields.get(f"{k_dim}_mode", "")
        range_val = fields.get(f"{k_dim}_range", "")
        difficulty_anchor[f"{k_dim}_mode"] = parse_k_score(mode_val) if mode_val else 1
        difficulty_anchor[f"{k_dim}_range"] = parse_k_range(range_val) if range_val else [1, 5]

    rep_years_raw = fields.get("representative_years", "")
    rep_years = [y.strip() for y in re.split(r"[,，\s]+", rep_years_raw) if y.strip().isdigit()]

    return {
        "slot_id": slot_id,
        "difficulty_anchor": difficulty_anchor,
        "radar_shape": fields.get("radar_shape", ""),
        "representative_years": rep_years,
        "reasoning_shape_mode": fields.get("reasoning_shape_mode", ""),
        "pattern_count": fields.get("pattern_count", ""),
        "should_be": fields.get("should_be", ""),
        "should_not_be": fields.get("should_not_be", ""),
    }


# ── Output generation ──────────────────────────────────────────

def _infer_subject_stability(obs_list: List[Dict]) -> str:
    """Infer subject stability from observations."""
    subjects = Counter(o.get("target_family", "未知") for o in obs_list)
    if len(subjects) == 1:
        return list(subjects.keys())[0]
    top = subjects.most_common(1)[0]
    if top[1] / len(obs_list) > 0.7:
        return top[0]
    return "跨领域"


def compute_slot_template(slot_id: str, synthesis: Dict, evals: List[Dict], obs_list: List[Dict]) -> Dict:
    """Build a full slot template from synthesis + evaluations."""
    first_obs = obs_list[0] if obs_list else {}
    q_type = first_obs.get("question_type", "single_choice")
    section = first_obs.get("section", "选择题")

    # Compute distributions from evaluations
    target_family_dist = Counter(ev.get("target_family", "未知") for ev in evals)
    target_family_dist = {k: round(v / len(evals), 2) for k, v in target_family_dist.most_common()}

    target_depth_dist = Counter(
        obs.get("target_depth", "knowledge") for obs in obs_list
    )
    target_depth_dist = {k: round(v / len(obs_list), 2) for k, v in target_depth_dist.most_common()}

    paper_role_dist = Counter(ev.get("paper_role", "未知") for ev in evals)
    paper_role_dist = {k: round(v / len(evals), 2) for k, v in paper_role_dist.most_common()}

    # Style mode from observations
    option_styles = Counter(o.get("option_style", "") for o in obs_list)
    reasoning_shapes = Counter(o.get("reasoning_shape", "") for o in obs_list)
    stem_lengths = Counter(o.get("stem_length", "") for o in obs_list)
    style_mode = {
        "option_style": option_styles.most_common(1)[0][0] if option_styles else "",
        "reasoning_shape": reasoning_shapes.most_common(1)[0][0] if reasoning_shapes else "",
        "stem_length": stem_lengths.most_common(1)[0][0] if stem_lengths else "",
    }

    subject_stability = _infer_subject_stability(obs_list)

    # Reasoning shape distribution from evals
    reasoning_dist = Counter(ev.get("reasoning_shape", "") for ev in evals)
    reasoning_shape_distribution = {k: round(v / len(evals), 2) for k, v in reasoning_dist.most_common()}

    return {
        "slot_id": slot_id,
        "section": section,
        "question_type": q_type,
        "typical_score": 2 if q_type == "single_choice" else 10,
        "subject_stability": subject_stability,
        "subject_distribution": target_family_dist,
        "target_family_distribution": target_family_dist,
        "target_depth_distribution": target_depth_dist,
        "paper_role_distribution": paper_role_dist,
        "difficulty_anchor": synthesis.get("difficulty_anchor", {}),
        "style_mode": style_mode,
        "radar_shape": synthesis.get("radar_shape", ""),
        "reasoning_shape_mode": synthesis.get("reasoning_shape_mode", ""),
        "reasoning_shape_distribution": reasoning_shape_distribution,
        "pattern_count": synthesis.get("pattern_count", ""),
        "should_be": synthesis.get("should_be", ""),
        "should_not_be": synthesis.get("should_not_be", ""),
        "stability_assessment": f"基于{len(evals)}道真题分析",
    }


def generate_slot_md(slot_id: str, template: Dict, evals: List[Dict], raw_synthesis: str = "") -> str:
    """Generate a slot analysis markdown file.

    Structure:
      1. 基本信息 + 认知雷达锚点 (programmatic)
      2. 考察模式 (from LLM synthesis — patterns first)
      3. 往年题干索引 (lightweight — stem + mode label per question)
    """
    da = template.get("difficulty_anchor", {})
    q_type = template.get("question_type", "?")
    subject = template.get("subject_stability", "?")
    score = template.get("typical_score", "?")
    radar_shape = template.get("radar_shape", "?")

    lines = [
        f"# {slot_id} 考察理念",
        "",
        "## 基本信息",
        "",
        f"- **题位**: {slot_id}",
        f"- **分值**: {score}",
        f"- **科目**: {subject}",
        f"- **题型**: {'选择题' if q_type == 'single_choice' else '综合应用题'}",
    ]

    # Knowledge domain distribution
    family_dist = template.get("target_family_distribution", {})
    if family_dist:
        lines.extend(["", "### 往年知识点分布", ""])
        for domain, pct in family_dist.items():
            lines.append(f"- {domain}: {pct:.0%}")

    # K-value anchors
    lines.extend(["", "## 认知雷达锚点", ""])
    for k_dim in ("K1", "K2", "K3", "K4", "K5"):
        mode = da.get(f"{k_dim}_mode", "?")
        rng = da.get(f"{k_dim}_range", [1, 5])
        lines.append(f"- **{k_dim}**: 众数={mode} [{rng[0]}, {rng[1]}]")
    lines.extend([f"- **典型雷达形状**: {radar_shape}", ""])

    # ── Section: 考察模式 (from LLM synthesis — patterns first) ──
    if raw_synthesis:
        body = raw_synthesis
        synthesis_start = body.find("## slot_synthesis")
        if synthesis_start != -1:
            body = body[:synthesis_start].rstrip()
        # Strip the LLM's own top-level title and basic info (we have our own)
        body_lines = body.split("\n")
        filtered = []
        skip_until_next_section = False
        for bl in body_lines:
            stripped = bl.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                continue
            if stripped.startswith("## 基本信息") or stripped.startswith("## 考察模式分布"):
                skip_until_next_section = True
                continue
            if skip_until_next_section and stripped.startswith("## "):
                skip_until_next_section = False
            if skip_until_next_section:
                continue
            filtered.append(bl)
        lines.extend(filtered)
        lines.append("")

    # ── Section: 往年题干索引 (lightweight per-question with full stems) ──
    lines.extend(["## 往年题干索引", ""])
    sorted_evals = sorted(evals, key=lambda x: x.get("year", 0))
    for ev in sorted_evals:
        year = ev.get("year", "?")
        name = ev.get("primary_target_name", "?")
        stem = ev.get("question_stem", "")
        radar = ev.get("radar_shape_name", "")

        if q_type == "single_choice":
            mode = ev.get("mode_name", "")
            tag = f"模式={mode}  雷达={radar}"
        else:
            subq = ev.get("sub_q_count", "?")
            dep = ev.get("sub_q_dependency", "")
            tag = f"子问={subq}  依赖={dep}  雷达={radar}"

        lines.append(f"### {year}年 — {name}")
        lines.append(f"**标签**: {tag}")
        if stem:
            lines.append(f"**题干**: {stem}")
        lines.append("")

    return "\n".join(lines)


def generate_experience_md(slot_id: str, template: Dict, raw_synthesis: str = "") -> str:
    """Generate a slot experience card — structural patterns + full stems.

    The experience card is the raw LLM synthesis output (which now includes
    patterns and full stems) with programmatic K-value metadata prepended.
    """
    da = template.get("difficulty_anchor", {})
    q_type = template.get("question_type", "?")
    q_type_display = "选择题" if q_type == "single_choice" else "综合应用题"

    lines = [
        f"# {slot_id} 题位经验",
        "",
        "## 基本信息",
        f"- **题位**: {slot_id}",
        f"- **科目**: {template.get('subject_stability', '?')}",
        f"- **题型**: {q_type_display}",
        f"- **分值**: {template.get('typical_score', '?')}分",
        "",
        "## K值锚点",
    ]

    for k_dim in ("K1", "K2", "K3", "K4", "K5"):
        mode = da.get(f"{k_dim}_mode", "?")
        rng = da.get(f"{k_dim}_range", [1, 5])
        lines.append(f"- **{k_dim}**: 众数={mode} [{rng[0]}, {rng[1]}]")

    lines.extend([
        f"- **典型雷达形状**: {template.get('radar_shape', '?')}",
        "",
    ])

    # Append LLM synthesis body (patterns + stems from synthesis prompt)
    if raw_synthesis:
        body = raw_synthesis
        synthesis_start = body.find("## slot_synthesis")
        if synthesis_start != -1:
            body = body[:synthesis_start].rstrip()
        # Strip the LLM's own top-level title (we have our own)
        body_lines = body.split("\n")
        filtered = []
        skip_until_next_section = False
        for bl in body_lines:
            stripped = bl.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                continue
            if stripped.startswith("## 基本信息"):
                skip_until_next_section = True
                continue
            if skip_until_next_section and stripped.startswith("## "):
                skip_until_next_section = False
            if skip_until_next_section:
                continue
            filtered.append(bl)
        lines.extend(filtered)
        lines.append("")

    return "\n".join(lines)


def generate_question_experience_md(ev: Dict, obs: Dict) -> str:
    """Generate a per-question experience document, branching by question type."""
    year = ev.get("year", "?")
    slot_id = ev.get("slot_id", "?")
    name = ev.get("primary_target_name", "?")
    q_type = ev.get("question_type", "single_choice")
    q_type_display = "选择题" if q_type == "single_choice" else "综合应用题"
    stem = ev.get("question_stem", "")

    lines = [
        f"# {year}年 {slot_id} — {name}",
        "",
        "## 基本信息",
        f"- **年份**: {year}  **题位**: {slot_id}  **题型**: {q_type_display}",
        f"- **知识点**: {ev.get('knowledge_points', '')}",
        f"- **考纲对应**: {ev.get('syllabus_mapping', '')}",
        "",
    ]

    # Question stem
    if stem:
        lines.extend([
            "## 题干原文",
            stem,
            "",
        ])

    # K1-K5 with reasons
    lines.append("## K1-K5 评分与解析")
    for k_dim in ("K1", "K2", "K3", "K4", "K5"):
        score_val = ev.get(k_dim, "?")
        reason = ev.get(f"{k_dim}_reason", "")
        lines.append(f"- **{k_dim} = {score_val}**: {reason}")
    lines.append(f"- **雷达形状**: {ev.get('radar_shape_name', '')}")
    lines.append("")

    if q_type == "single_choice":
        # SC: option-level analysis + examination mode
        mode_name = ev.get("mode_name", "")
        if mode_name:
            lines.extend([
                "## 考察模式",
                f"- **模式**: {mode_name}",
                f"- **理由**: {ev.get('mode_reason', '')}",
                "",
            ])

        opt_analysis = ev.get("option_analysis", {})
        if opt_analysis:
            lines.append("## 选项级分析")
            for opt_key in sorted(opt_analysis.keys()):
                lines.append(f"- **选项{opt_key}**: {opt_analysis[opt_key]}")
            distractor = ev.get("distractor_strategy", "")
            if distractor:
                lines.append(f"- **干扰策略**: {distractor}")
            lines.append("")
    else:
        # COMP: trajectory + sub-question dependency + condition utilization
        subq_dep = ev.get("sub_q_dependency", "")
        if subq_dep:
            lines.extend([
                "## 子问依赖",
                f"- **子问数**: {ev.get('sub_q_count', '?')}",
                f"- **依赖类型**: {subq_dep}",
            ])
            for sq in ev.get("sub_questions", []):
                lines.append(f"- **子问{sq['q']}**: {sq['desc']}")
            lines.append("")

        trajectory = ev.get("trajectory", [])
        if trajectory:
            lines.append("## 解题轨迹")
            for i, step in enumerate(trajectory, 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        cond_util = ev.get("condition_utilization", "")
        if cond_util:
            lines.extend([
                "## 条件利用映射",
                cond_util,
                "",
            ])

        key_point = ev.get("key_point", "")
        if key_point:
            lines.extend([
                "## 关键考察点",
                key_point,
                "",
            ])

    # Trap mechanism (shared)
    core_trap = ev.get("core_trap", "")
    if core_trap:
        lines.extend([
            "## 核心陷阱",
            f"- **核心陷阱**: {core_trap}",
        ])
        wrong_path = ev.get("wrong_path", "")
        if wrong_path:
            lines.append(f"- **错误路径**: {wrong_path}")
        lines.append("")

    # Examination ability (shared)
    ability = ev.get("examination_ability", "")
    if ability:
        lines.extend([
            "## 考察能力",
            ability,
            "",
        ])

    return "\n".join(lines)


# ── Main pipeline ──────────────────────────────────────────────

async def run_phase1(
    observations: List[Dict],
    gateway: LLMGateway,
    concurrency: int = 16,
    resume_path: Optional[str] = None,
) -> List[Dict]:
    """Phase 1: Evaluate K1-K5 for each question."""
    # Resume support
    existing: Dict[str, Dict] = {}
    if resume_path and os.path.exists(resume_path):
        with open(resume_path, encoding="utf-8") as f:
            existing = {f"{r['year']}_{r['slot_id']}": r for r in json.load(f)}
        print(f"  Resuming: {len(existing)} evaluations already done")

    # Filter out already-evaluated
    todo = []
    for obs in observations:
        key = f"{obs.get('year')}_{obs.get('slot_id')}"
        if key not in existing:
            todo.append(obs)

    print(f"  Phase 1: {len(todo)} questions to evaluate ({len(existing)} cached)")

    if not todo:
        return list(existing.values())

    # Batch processing
    all_evals = list(existing.values())
    batch_size = concurrency

    for start in range(0, len(todo), batch_size):
        batch = todo[start:start + batch_size]
        messages_batch = [format_single_eval_message(obs) for obs in batch]

        print(f"  Batch {start // batch_size + 1}/{(len(todo) + batch_size - 1) // batch_size}: "
              f"{len(batch)} questions")

        t0 = time.monotonic()
        results = await gateway.generate_text_batch(messages_batch, enable_thinking=False)
        elapsed = time.monotonic() - t0

        success = 0
        for obs, result in zip(batch, results):
            if result.ok and result.content:
                ev = parse_eval_result(result.content, obs)
                all_evals.append(ev)
                success += 1
            else:
                print(f"    WARNING: {obs.get('year')}/{obs.get('slot_id')} failed: "
                      f"{result.error_message or 'empty'}")
                # Fallback: default K values
                ev = parse_eval_result("", obs)
                all_evals.append(ev)

        print(f"    {success}/{len(batch)} OK, {elapsed:.1f}s")

        # Save intermediate results
        if resume_path:
            with open(resume_path, "w", encoding="utf-8") as f:
                json.dump(all_evals, f, ensure_ascii=False, indent=2)

    return all_evals


async def run_phase2(
    evals: List[Dict],
    observations: List[Dict],
    slot_ids: Optional[List[str]],
    gateway: LLMGateway,
) -> Tuple[Dict[str, Dict], Dict[str, List[Dict]], Dict[str, List[Dict]]]:
    """Phase 2: Synthesize per-slot K patterns."""
    # Group evals by slot_id
    from collections import defaultdict
    evals_by_slot: Dict[str, List[Dict]] = defaultdict(list)
    obs_by_slot: Dict[str, List[Dict]] = defaultdict(list)

    for ev in evals:
        evals_by_slot[ev["slot_id"]].append(ev)
    for obs in observations:
        obs_by_slot[obs["slot_id"]].append(obs)

    target_slots = slot_ids or sorted(evals_by_slot.keys())
    print(f"  Phase 2: {len(target_slots)} slots to synthesize")

    # Build messages batch
    messages_batch = []
    slot_order = []
    for sid in target_slots:
        slot_evals = evals_by_slot.get(sid, [])
        slot_obs = obs_by_slot.get(sid, [])
        if not slot_evals:
            continue
        msg = format_synthesis_message(sid, slot_evals, slot_obs)
        messages_batch.append(msg)
        slot_order.append(sid)

    if not messages_batch:
        print("  No slots to synthesize")
        return {}, {}, {}

    t0 = time.monotonic()
    results = await gateway.generate_text_batch(messages_batch, enable_thinking=False)
    elapsed = time.monotonic() - t0

    templates = {}
    evals_map = {}
    obs_map = {}
    raw_synthesis = {}  # Store raw LLM output for slot MD

    success = 0
    for sid, result in zip(slot_order, results):
        slot_evals = evals_by_slot[sid]
        slot_obs = obs_by_slot[sid]
        evals_map[sid] = slot_evals
        obs_map[sid] = slot_obs

        if result.ok and result.content:
            synthesis = parse_synthesis_result(result.content, sid)
            raw_synthesis[sid] = result.content
            success += 1
        else:
            print(f"    WARNING: slot {sid} synthesis failed: "
                  f"{result.error_message or 'empty'}")
            synthesis = {"slot_id": sid, "difficulty_anchor": {}}
            raw_synthesis[sid] = ""

        templates[sid] = compute_slot_template(sid, synthesis, slot_evals, slot_obs)

    print(f"  {success}/{len(slot_order)} OK, {elapsed:.1f}s")
    return templates, evals_map, obs_map, raw_synthesis


def save_outputs(
    templates: Dict[str, Dict],
    evals_map: Dict[str, List[Dict]],
    obs_map: Dict[str, List[Dict]],
    output_dir: str = "data",
    raw_synthesis: Optional[Dict[str, str]] = None,
):
    """Save all outputs to disk."""
    # 1. per_question_k_ratings.json
    all_evals = []
    for evals in evals_map.values():
        all_evals.extend(evals)
    ratings_path = os.path.join(output_dir, "per_question_k_ratings.json")
    with open(ratings_path, "w", encoding="utf-8") as f:
        json.dump(all_evals, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {ratings_path} ({len(all_evals)} ratings)")

    # 2. slot_templates.json
    tpl_data = {
        "version": "3.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "templates": templates,
    }
    tpl_path = os.path.join(output_dir, "slot_templates.json")
    with open(tpl_path, "w", encoding="utf-8") as f:
        json.dump(tpl_data, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {tpl_path} ({len(templates)} slots)")

    # 3. question_experiences/*.md (per-question experience docs)
    qe_dir = os.path.join(output_dir, "question_experiences")
    os.makedirs(qe_dir, exist_ok=True)
    qe_count = 0
    for sid, slot_evals in evals_map.items():
        slot_obs = obs_map.get(sid, [])
        obs_by_key = {f"{o.get('year')}_{o.get('slot_id')}": o for o in slot_obs}
        for ev in slot_evals:
            key = f"{ev.get('year')}_{ev.get('slot_id')}"
            obs = obs_by_key.get(key, {})
            md = generate_question_experience_md(ev, obs)
            md_path = os.path.join(qe_dir, f"{ev.get('year')}_{sid}.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md)
            qe_count += 1
    print(f"  Saved: {qe_dir}/ ({qe_count} question experiences)")

    # 4. slots/*.md (slot analysis with trajectories)
    slots_dir = os.path.join(output_dir, "slots")
    os.makedirs(slots_dir, exist_ok=True)
    for sid, tmpl in templates.items():
        slot_evals = evals_map.get(sid, [])
        md = generate_slot_md(sid, tmpl, slot_evals,
                              raw_synthesis=(raw_synthesis or {}).get(sid, ""))
        md_path = os.path.join(slots_dir, f"{sid}_slot.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)
    print(f"  Saved: {slots_dir}/ ({len(templates)} slot MDs)")

    # 5. slot_experiences/*.md (structural pattern catalogs)
    exp_dir = os.path.join(output_dir, "slot_experiences")
    os.makedirs(exp_dir, exist_ok=True)
    for sid, tmpl in templates.items():
        md = generate_experience_md(sid, tmpl,
                                    raw_synthesis=(raw_synthesis or {}).get(sid, ""))
        exp_path = os.path.join(exp_dir, f"{sid}_experience.md")
        with open(exp_path, "w", encoding="utf-8") as f:
            f.write(md)
    print(f"  Saved: {exp_dir}/ ({len(templates)} experience cards)")


async def main():
    parser = argparse.ArgumentParser(description="Slot K1-K5 extractor")
    parser.add_argument("--slots", nargs="+", help="Specific slots (e.g., Q14 Q15)")
    parser.add_argument("--concurrency", type=int, default=16, help="Batch size for vLLM")
    parser.add_argument("--eval-only", action="store_true", help="Only run phase 1")
    parser.add_argument("--resume", action="store_true", help="Resume from cached evaluations")
    args = parser.parse_args()

    # Load observations
    obs_path = "data/slot_observations.json"
    if not os.path.exists(obs_path):
        print(f"Observations not found: {obs_path}")
        return

    with open(obs_path, encoding="utf-8") as f:
        obs_data = json.load(f)
    observations = obs_data.get("observations", [])

    # Filter by requested slots
    if args.slots:
        slot_set = set(args.slots)
        observations = [o for o in observations if o.get("slot_id") in slot_set]
        print(f"Filtered: {len(observations)} observations for slots {args.slots}")
    else:
        print(f"Total: {len(observations)} observations")

    # Override concurrency
    import core_new.llm_gateway as gw_mod
    gw_mod._LOCAL_CONCURRENCY = args.concurrency

    # Create gateway to local vLLM
    gateway = LLMGateway("api_vllm")

    # Phase 1
    print("\n" + "=" * 60)
    print("Phase 1: Per-question K1-K5 evaluation")
    print("=" * 60)
    resume_path = "data/per_question_k_ratings.json" if args.resume else None
    evals = await run_phase1(observations, gateway, concurrency=args.concurrency, resume_path=resume_path)

    if args.eval_only:
        # Save just the evaluations
        with open("data/per_question_k_ratings.json", "w", encoding="utf-8") as f:
            json.dump(evals, f, ensure_ascii=False, indent=2)
        print(f"\nSaved evaluations: {len(evals)} ratings")
        return

    # Phase 2
    print("\n" + "=" * 60)
    print("Phase 2: Per-slot K pattern synthesis")
    print("=" * 60)
    templates, evals_map, obs_map, raw_synthesis = await run_phase2(
        evals, observations, args.slots, gateway,
    )

    # Save outputs
    print("\n" + "=" * 60)
    print("Saving outputs")
    print("=" * 60)
    save_outputs(templates, evals_map, obs_map, raw_synthesis=raw_synthesis)
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
