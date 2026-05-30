"""Slot extractor — two-phase K1-K5 extraction via local vLLM batch.

Phase 1: Per-question K1-K5 evaluation (LLM batch)
  slot_observations.json (165 questions)
  → SLOT_SINGLE_EVAL_PROMPT per question
  → generate_text_batch via local vLLM
  → Parse Markdown → data/per_question_k_ratings.json

Phase 2: Per-slot K pattern synthesis (LLM batch)
  per_question_k_ratings.json grouped by slot_id
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

from core_new.llm_gateway import LLMGateway, _get_sem
from core_new.prompts.cognitive_radar import COGNITIVE_RADAR_SCALE
from core_new.slot_prompts import (
    SLOT_SINGLE_EVAL_PROMPT,
    SLOT_SYNTHESIS_PROMPT,
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
    """Format a single observation into a chat message for SLOT_SINGLE_EVAL_PROMPT."""
    prompt = SLOT_SINGLE_EVAL_PROMPT.format(
        cognitive_radar_scale=COGNITIVE_RADAR_SCALE,
        year=obs.get("year", "?"),
        slot_id=obs.get("slot_id", "?"),
        primary_target_name=obs.get("primary_target_name", "?"),
        target_family=obs.get("target_family", "?"),
        question_type=obs.get("question_type", "?"),
        solution_steps=obs.get("solution_steps", "?"),
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
    return [{"role": "user", "content": prompt}]


def parse_eval_result(raw: str, obs: Dict) -> Dict:
    """Parse phase 1 LLM output into a structured evaluation."""
    fields = parse_markdown_fields(raw, "evaluation")

    result = {
        "year": obs.get("year"),
        "slot_id": obs.get("slot_id"),
        "primary_target_name": obs.get("primary_target_name"),
        "target_family": obs.get("target_family"),
        "paper_role": obs.get("paper_role"),
    }

    for k_dim in ("K1", "K2", "K3", "K4", "K5"):
        val = fields.get(k_dim, "1")
        result[k_dim] = parse_k_score(val)
        result[f"{k_dim}_reason"] = val

    result["radar_shape_name"] = fields.get("radar_shape_name", "")
    result["reasoning_shape"] = fields.get("reasoning_shape", obs.get("reasoning_shape", ""))
    result["reasoning_shape_reason"] = fields.get("reasoning_shape_reason", "")
    result["summary"] = fields.get("summary", "")

    return result


# ── Phase 2: Per-slot synthesis ─────────────────────────────────

def format_synthesis_message(slot_id: str, evals: List[Dict], obs_list: List[Dict]) -> List[Dict]:
    """Format per-slot synthesis prompt with all K1-K5 evaluations."""
    # Build evaluations text
    eval_lines = []
    for ev in evals:
        line = (
            f"### {ev['year']}年 — {ev.get('primary_target_name', '?')}\n"
            f"- K1={ev['K1']}, K2={ev['K2']}, K3={ev['K3']}, K4={ev['K4']}, K5={ev['K5']}\n"
            f"- 雷达形状: {ev.get('radar_shape_name', '?')}\n"
            f"- 摘要: {ev.get('summary', '?')}"
        )
        eval_lines.append(line)

    evaluations_data = "\n\n".join(eval_lines)

    # Determine slot metadata from observations
    first_obs = obs_list[0] if obs_list else {}
    subject_stability = _infer_subject_stability(obs_list)
    question_type = first_obs.get("question_type", "single_choice")
    typical_score = 2 if question_type == "single_choice" else 10

    prompt = SLOT_SYNTHESIS_PROMPT.format(
        slot_id=slot_id,
        subject_stability=subject_stability,
        question_type=question_type,
        typical_score=typical_score,
        question_count=len(evals),
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

    # Parse representative years
    rep_years_raw = fields.get("representative_years", "")
    rep_years = [y.strip() for y in re.split(r"[,，\s]+", rep_years_raw) if y.strip().isdigit()]

    return {
        "slot_id": slot_id,
        "difficulty_anchor": difficulty_anchor,
        "radar_shape": fields.get("radar_shape", ""),
        "representative_years": rep_years,
        "reasoning_shape_mode": fields.get("reasoning_shape_mode", ""),
        "reasoning_shape_distribution": fields.get("reasoning_shape_distribution", ""),
        "reasoning_shape_guidance": fields.get("reasoning_shape_guidance", ""),
        "slot_K_guidance": fields.get("slot_K_guidance", ""),
        "slot_style_guidance": fields.get("slot_style_guidance", ""),
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

    # Subject distribution
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
        "reasoning_shape_guidance": synthesis.get("reasoning_shape_guidance", ""),
        "slot_guidance": synthesis.get("slot_K_guidance", ""),
        "should_be": synthesis.get("should_be", ""),
        "should_not_be": synthesis.get("should_not_be", ""),
        "generation_style": synthesis.get("slot_style_guidance", ""),
        "stability_assessment": f"基于{len(evals)}道真题分析",
    }


def generate_slot_md(slot_id: str, template: Dict, evals: List[Dict], raw_synthesis: str = "") -> str:
    """Generate a slot analysis markdown file.

    Structure:
      1. 基本信息 (programmatic)
      2. 认知雷达锚点 (programmatic from synthesis)
      3. 逐题 K1-K5 评价 — with reasons + reasoning_shape (from phase 1 evals)
      4. 题位设计经验 (from LLM phase 2 synthesis — 往年案例/设计理念/出题指导/选项设计经验)
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
    ]

    if q_type != "single_choice":
        lines.append(f"- **子问数量**: 通常为 2-4 个小问，累计分值 {score} 分")

    # Knowledge domain distribution
    family_dist = template.get("target_family_distribution", {})
    if family_dist:
        lines.extend(["", "### 往年知识点分布", ""])
        for domain, pct in family_dist.items():
            lines.append(f"- {domain}: {pct:.0%}")

    # ── Section: 认知雷达锚点 ──
    lines.extend([
        "",
        "## 认知雷达锚点",
        "",
    ])

    # K dimension brief descriptions for context
    k_desc = {
        "K1": "基础认知需求",
        "K2": "单步代入需求",
        "K3": "机制推演需求",
        "K4": "条件路由需求",
        "K5": "跨域联动需求",
    }
    for k_dim in ("K1", "K2", "K3", "K4", "K5"):
        mode = da.get(f"{k_dim}_mode", "?")
        rng = da.get(f"{k_dim}_range", [1, 5])
        lines.append(f"- **{k_dim}**: 众数={mode} [{rng[0]}, {rng[1]}]")

    lines.extend([
        f"- **典型雷达形状**: {radar_shape}",
        "",
    ])

    # ── Section: 逐题 K1-K5 评价 (from phase 1, with reasons) ──
    lines.extend([
        "## 参考题目 K1-K5 评分",
        "",
    ])

    sorted_evals = sorted(evals, key=lambda x: x.get("year", 0), reverse=True)
    for ev in sorted_evals:
        year = ev.get("year", "?")
        name = ev.get("primary_target_name", "?")
        radar = ev.get("radar_shape_name", "")
        rshape = ev.get("reasoning_shape", "")
        rshape_reason = ev.get("reasoning_shape_reason", "")

        lines.append(f"### {year}年 — {name}")
        lines.append("")

        # K scores with reasons
        for k_dim in ("K1", "K2", "K3", "K4", "K5"):
            score_val = ev.get(k_dim, "?")
            reason = ev.get(f"{k_dim}_reason", "")
            # reason already contains "N — 理由", extract just the reason part
            reason_text = reason
            if "—" in reason:
                reason_text = reason.split("—", 1)[1].strip()
            elif "–" in reason:
                reason_text = reason.split("–", 1)[1].strip()
            lines.append(f"- **{k_dim}**: {score_val} — {reason_text}")

        lines.append(f"- **雷达形状**: {radar}")

        if rshape:
            shape_label = {
                "one_formula": "单公式代入",
                "multi_step": "多步推导",
                "elimination": "排除法",
                "simulation": "过程模拟",
            }.get(rshape, rshape)
            lines.append(f"- **推理形式**: {rshape}（{shape_label}）")
            if rshape_reason:
                lines.append(f"- **推理形式理由**: {rshape_reason}")

        lines.append("")

    # ── Section: 题位设计经验 (from LLM synthesis) ──
    if raw_synthesis:
        # Strip the ## slot_synthesis section (machine-readable part at end)
        body = raw_synthesis
        synthesis_start = body.find("## slot_synthesis")
        if synthesis_start != -1:
            body = body[:synthesis_start].rstrip()

        # Strip any top-level title the LLM might have added
        # (we already have our own # {slot_id} 考察理念)
        lines.append(body.strip())
        lines.append("")

    return "\n".join(lines)


def generate_experience_md(slot_id: str, template: Dict, evals: List[Dict]) -> str:
    """Generate an experience card markdown file."""
    da = template.get("difficulty_anchor", {})
    lines = [
        f"# 经验卡 — {slot_id}",
        "",
        "## 题位模板摘要",
        f"- 题位: {slot_id}",
        f"- 科目: {template.get('subject_stability', '?')}",
        f"- 题型: {template.get('question_type', '?')}",
        f"- 分值: {template.get('typical_score', '?')}分",
        "",
        "## 认知雷达锚点",
    ]

    for k_dim in ("K1", "K2", "K3", "K4", "K5"):
        mode = da.get(f"{k_dim}_mode", "?")
        rng = da.get(f"{k_dim}_range", [1, 5])
        lines.append(f"- {k_dim}: 众数={mode} {rng}")
    lines.append("")

    # Distributions
    lines.append("## 知识领域分布")
    for k, v in template.get("target_family_distribution", {}).items():
        lines.append(f"- {k}: {v:.0%}")
    lines.append("")

    lines.append("## 功能角色分布")
    for k, v in template.get("paper_role_distribution", {}).items():
        lines.append(f"- {k}: {v:.0%}")
    lines.append("")

    lines.extend([
        "## 出题指导",
        f"- should_be: {template.get('should_be', '无')}",
        f"- should_not_be: {template.get('should_not_be', '无')}",
        f"- generation_style: {template.get('generation_style', '无')}",
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
        "version": "2.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "templates": templates,
    }
    tpl_path = os.path.join(output_dir, "slot_templates.json")
    with open(tpl_path, "w", encoding="utf-8") as f:
        json.dump(tpl_data, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {tpl_path} ({len(templates)} slots)")

    # 3. slots/*.md
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

    # 4. slot_experiences/*.md
    exp_dir = os.path.join(output_dir, "slot_experiences")
    os.makedirs(exp_dir, exist_ok=True)
    for sid, tmpl in templates.items():
        slot_evals = evals_map.get(sid, [])
        md = generate_experience_md(sid, tmpl, slot_evals)
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
    gw_mod._MAX_CONCURRENCY = args.concurrency
    gw_mod._concurrency_sem = asyncio.Semaphore(args.concurrency)

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
