"""Slot-template driven extraction pipeline.

Groups historical 408 exam questions by slot_id (question position),
sends each group to GLM5.1 for comprehensive analysis:
  - SlotObservation per question (逐题分析)
  - SlotTemplate for the slot position (题位模板)
  - TypeDifficultyGuide (出题指导)

Usage:
    .venv/bin/python slot_extractor.py --slot Q12          # single slot
    .venv/bin/python slot_extractor.py --all                # all slots
    .venv/bin/python slot_extractor.py --all --concurrency 3
"""

import asyncio
import json
import os
import re
import sys
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(__file__))

from core_new.llm_gateway import get_gateway
from core_new.slot_prompts import SLOT_BATCH_ANALYSIS_PROMPT

# ── P1: Programmatic Grouping ──────────────────────────────────


def parse_slot_info(prompt: str) -> Optional[Tuple[int, str]]:
    """Extract (year, slot_id) from prompt text."""
    m = re.search(r"(\d{4})年考研真题第(\d+)题", prompt)
    if not m:
        return None
    year = int(m.group(1))
    slot_num = int(m.group(2))
    slot_id = f"Q{slot_num:02d}"
    return year, slot_id


def get_section(slot_num: int) -> str:
    if slot_num <= 40:
        return "选择题"
    return "综合应用题"


def get_question_type(slot_num: int) -> str:
    if slot_num <= 40:
        return "single_choice"
    return "comprehensive"


def group_by_slot(
    questions: List[Dict], indices: List[int]
) -> Dict[str, List[Dict]]:
    """Group valid questions by slot_id, preserving year and original index."""
    groups = defaultdict(list)
    for idx in indices:
        q = questions[idx]
        result = parse_slot_info(q.get("prompt", ""))
        if not result:
            continue
        year, slot_id = result
        slot_num = int(slot_id[1:])
        groups[slot_id].append(
            {
                "year": year,
                "slot_num": slot_num,
                "slot_id": slot_id,
                "index": idx,
                "prompt": q.get("prompt", ""),
                "answer": q.get("answer", ""),
                "type": q.get("type", ""),
                "section": get_section(slot_num),
                "question_type": get_question_type(slot_num),
            }
        )
    # Sort each group by year
    for slot_id in groups:
        groups[slot_id].sort(key=lambda x: x["year"])
    return dict(groups)


# ── P2: Format questions for prompt ────────────────────────────


def format_questions_for_prompt(slot_questions: List[Dict]) -> str:
    """Format all questions for one slot into the prompt data section."""
    parts = []
    for q in slot_questions:
        parts.append(
            f"[{q['year']}-{q['slot_id']}] "
            f"类型: {q['type']}\n"
            f"题目: {q['prompt']}\n"
            f"标准答案: {q['answer']}"
        )
    return "\n\n".join(parts)


# ── P2/P3: LLM Call and Parsing ───────────────────────────────


def parse_obs_block(text: str) -> Optional[Dict[str, Any]]:
    """Parse a single <obs> block into a SlotObservation dict."""
    result = {}
    # Extract year attribute
    m = re.search(r'<obs\s+year="(\d+)"', text)
    if m:
        result["year"] = int(m.group(1))

    # Extract all inner XML tags
    for m in re.finditer(r"<(\w+)>(.*?)</\1>", text, re.DOTALL):
        key = m.group(1)
        value = m.group(2).strip()
        result[key] = value

    # Parse numeric fields
    numeric_fields = {
        "difficulty_overall": 3,
        "difficulty_knowledge_depth": 2,
        "difficulty_mechanism_depth": 1,
        "difficulty_reasoning_steps": 2,
        "difficulty_calculation_load": 1,
        "difficulty_trap_strength": 1,
        "difficulty_cross_topic": 0,
        "condition_count": 2,
    }
    for field, default in numeric_fields.items():
        if field in result:
            try:
                result[field] = int(float(result[field]))
            except (ValueError, TypeError):
                result[field] = default

    # Parse JSON fields
    json_fields = [
        "why_wrong_options",
        "distractor_patterns",
        "subject_distribution",
        "target_family_distribution",
        "target_depth_distribution",
        "paper_role_distribution",
        "difficulty_anchor",
        "style_mode",
        "expected_shape",
        "suitable_targets",
        "distractor_style",
        "bad_examples",
    ]
    for field in json_fields:
        if field in result and isinstance(result[field], str):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass  # keep as string

    return result if result.get("year") else None


def parse_slot_template_block(text: str) -> Dict[str, Any]:
    """Parse the <slot_template> block."""
    result = {}
    for m in re.finditer(r"<(\w+)>(.*?)</\1>", text, re.DOTALL):
        key = m.group(1)
        value = m.group(2).strip()
        result[key] = value

    # Parse JSON fields
    json_fields = [
        "subject_distribution",
        "target_family_distribution",
        "target_depth_distribution",
        "paper_role_distribution",
        "difficulty_anchor",
        "style_mode",
    ]
    for field in json_fields:
        if field in result and isinstance(result[field], str):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass

    # Parse numeric fields
    if "typical_score" in result:
        try:
            result["typical_score"] = int(float(result["typical_score"]))
        except (ValueError, TypeError):
            pass

    return result


def parse_type_difficulty_guide(text: str) -> Dict[str, Any]:
    """Parse the <type_difficulty_guide> block."""
    result = {}
    for m in re.finditer(r"<(\w+)>(.*?)</\1>", text, re.DOTALL):
        key = m.group(1)
        value = m.group(2).strip()
        result[key] = value

    # Parse JSON fields
    json_fields = [
        "expected_shape",
        "suitable_targets",
        "distractor_style",
        "bad_examples",
    ]
    for field in json_fields:
        if field in result and isinstance(result[field], str):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass

    if "difficulty" in result:
        try:
            result["difficulty"] = int(float(result["difficulty"]))
        except (ValueError, TypeError):
            pass

    return result


def parse_full_output(raw: str, slot_id: str) -> Dict[str, Any]:
    """Parse the complete LLM output into structured data."""
    observations = []
    slot_template = {}
    guide = {}

    # Extract <obs> blocks
    for m in re.finditer(r"<obs\s+year.*?</obs>", raw, re.DOTALL):
        obs = parse_obs_block(m.group(0))
        if obs:
            obs["slot_id"] = slot_id
            observations.append(obs)

    # Extract <slot_template> block
    m = re.search(r"<slot_template>(.*?)</slot_template>", raw, re.DOTALL)
    if m:
        slot_template = parse_slot_template_block(m.group(1))

    # Extract <type_difficulty_guide> block
    m = re.search(
        r"<type_difficulty_guide>(.*?)</type_difficulty_guide>", raw, re.DOTALL
    )
    if m:
        guide = parse_type_difficulty_guide(m.group(1))

    return {
        "observations": observations,
        "slot_template": slot_template,
        "type_difficulty_guide": guide,
    }


# ── Main Extraction ────────────────────────────────────────────


async def extract_slot(
    gateway,
    slot_id: str,
    slot_questions: List[Dict],
) -> Dict[str, Any]:
    """Extract SlotObservations + SlotTemplate for one slot_id."""
    slot_num = int(slot_id[1:])
    questions_data = format_questions_for_prompt(slot_questions)

    prompt = SLOT_BATCH_ANALYSIS_PROMPT.format(
        slot_num=slot_num,
        count=len(slot_questions),
        questions_data=questions_data,
    )

    messages = [{"role": "user", "content": prompt}]

    start = time.monotonic()

    result = await gateway.generate_reasoned(
        messages, max_tokens=16384, enable_thinking=True
    )
    latency = time.monotonic() - start

    if not result.ok:
        return {
            "slot_id": slot_id,
            "status": "error",
            "error": result.error_message[:500],
            "latency_s": round(latency, 2),
        }

    raw_answer = result.content or ""
    thinking = result.reasoning or ""

    parsed = parse_full_output(raw_answer, slot_id)

    print(
        f"  [{slot_id}] Done in {latency:.1f}s — "
        f"{len(parsed['observations'])} observations, "
        f"template={'ok' if parsed['slot_template'] else 'MISSING'}, "
        f"guide={'ok' if parsed['type_difficulty_guide'] else 'MISSING'}"
    )

    return {
        "slot_id": slot_id,
        "status": "success",
        "observations": parsed["observations"],
        "slot_template": parsed["slot_template"],
        "type_difficulty_guide": parsed["type_difficulty_guide"],
        "raw_answer": raw_answer[:8000],
        "thinking_preview": thinking[:2000],
        "latency_s": round(latency, 2),
    }


async def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", type=str, help="Single slot to extract (e.g., Q12)")
    parser.add_argument(
        "--all", action="store_true", help="Extract all slot groups"
    )
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument(
        "--output-dir", default="data", help="Output directory"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force re-extract even if slot already exists"
    )
    args = parser.parse_args()

    if not args.slot and not args.all:
        print("Specify --slot Q12 or --all")
        return

    # Load data
    with open("data/full_question.json", encoding="utf-8") as f:
        all_q = json.load(f)
    with open("data/all_questions_filtered.json", encoding="utf-8") as f:
        filtered = json.load(f)

    all_valid = filtered["choice_indices"] + filtered["subjective_indices"]
    print(f"Loaded {len(all_valid)} valid question indices")

    # P1: Group by slot
    groups = group_by_slot(all_q, all_valid)
    print(f"Found {len(groups)} slot groups: {sorted(groups.keys())}")

    for sid in sorted(groups.keys()):
        years = [q["year"] for q in groups[sid]]
        print(f"  {sid}: {len(groups[sid])} questions ({min(years)}-{max(years)})")

    # Select slots to process
    if args.slot:
        slot_id = args.slot.upper()
        if slot_id not in groups:
            print(f"Slot {slot_id} not found. Available: {sorted(groups.keys())}")
            return
        slots_to_process = [(slot_id, groups[slot_id])]
    else:
        slots_to_process = sorted(groups.items())

    # Load existing data for merge
    existing_observations = []
    existing_templates = {}
    existing_guides = {}
    obs_path = os.path.join(args.output_dir, "slot_observations.json")
    tpl_path = os.path.join(args.output_dir, "slot_templates.json")
    guide_path = os.path.join(args.output_dir, "type_difficulty_guides.json")

    if os.path.exists(obs_path):
        with open(obs_path, encoding="utf-8") as f:
            existing_observations = json.load(f).get("observations", [])
    if os.path.exists(tpl_path):
        with open(tpl_path, encoding="utf-8") as f:
            existing_templates = json.load(f).get("templates", {})
    if os.path.exists(guide_path):
        with open(guide_path, encoding="utf-8") as f:
            existing_guides = json.load(f).get("guides", {})

    existing_slots = set(existing_templates.keys())

    # Skip already-extracted slots unless --force
    if not args.force:
        skipped = []
        remaining = []
        for item in slots_to_process:
            if item[0] in existing_slots:
                skipped.append(item[0])
            else:
                remaining.append(item)
        if skipped:
            print(f"Skipping already-extracted slots: {skipped}")
        slots_to_process = remaining

    if not slots_to_process:
        print("All slots already extracted. Use --force to re-extract.")
        return

    # P2: Extract (concurrent)
    gateway = get_gateway("glm5.1")
    sem = asyncio.Semaphore(args.concurrency)

    async def _extract_one(slot_id, slot_questions):
        async with sem:
            print(f"  [{slot_id}] Calling GLM5.1 with {len(slot_questions)} questions...")
            t0 = time.monotonic()
            result = await extract_slot(gateway, slot_id, slot_questions)
            elapsed = time.monotonic() - t0

            if result["status"] == "success":
                # Enrich observations with original question data
                obs_by_year = {
                    o.get("year"): o for o in result.get("observations", [])
                }
                for sq in slot_questions:
                    obs = obs_by_year.get(sq["year"])
                    if obs:
                        obs["original_index"] = sq["index"]
                        obs["section"] = sq["section"]
                        obs["question_type"] = sq["question_type"]

                tpl_ok = "ok" if result.get("slot_template") else "MISSING"
                guide_ok = "ok" if result.get("type_difficulty_guide") else "MISSING"
                n_obs = len(result.get("observations", []))
                print(f"  [{slot_id}] Done in {elapsed:.1f}s — {n_obs} observations, template={tpl_ok}, guide={guide_ok}")
            else:
                print(f"  [{slot_id}] ERROR: {result.get('error', 'unknown')[:200]}")

            return result

    total_start = time.monotonic()
    tasks = [
        _extract_one(slot_id, sq) for slot_id, sq in slots_to_process
    ]
    results = await asyncio.gather(*tasks)

    all_observations = []
    all_templates = {}
    all_guides = {}

    for result in results:
        if result["status"] == "success":
            slot_id = result["slot_id"]
            all_observations.extend(result.get("observations", []))

            if result.get("slot_template"):
                all_templates[slot_id] = result["slot_template"]

            if result.get("type_difficulty_guide"):
                guide_id = result["type_difficulty_guide"].get("guide_id", slot_id)
                all_guides[guide_id] = result["type_difficulty_guide"]

    total_time = time.monotonic() - total_start

    # P3: Merge with existing data and save
    os.makedirs(args.output_dir, exist_ok=True)

    # Collect slot_ids that were (re-)extracted in this run
    processed_slot_ids = [r["slot_id"] for r in results]
    new_slot_ids_set = set(processed_slot_ids)

    # Remove old data for re-extracted slots, keep the rest
    merged_observations = [
        o for o in existing_observations
        if o.get("slot_id") not in new_slot_ids_set
    ] + all_observations

    merged_templates = {k: v for k, v in existing_templates.items() if k not in new_slot_ids_set}
    merged_templates.update(all_templates)

    merged_guides = {k: v for k, v in existing_guides.items()}
    merged_guides.update(all_guides)

    # Save observations
    with open(obs_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total": len(merged_observations),
                "observations": merged_observations,
            },
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    print(f"\nSlotObservations saved: {obs_path} ({len(merged_observations)} records, {len(all_observations)} new)")

    # Save templates
    with open(tpl_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total": len(merged_templates),
                "templates": merged_templates,
            },
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    print(f"SlotTemplates saved: {tpl_path} ({len(merged_templates)} records)")

    # Save guides
    with open(guide_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total": len(merged_guides),
                "guides": merged_guides,
            },
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    print(f"TypeDifficultyGuides saved: {guide_path} ({len(merged_guides)} records)")

    # Print summary
    success = sum(1 for r in results if r["status"] == "success")
    errors = sum(1 for r in results if r["status"] == "error")
    total_obs_new = len(all_observations)

    print(f"\n{'='*60}")
    print(f"Slot extraction complete ({total_time:.1f}s)")
    print(f"{'='*60}")
    print(f"  Slots processed: {len(results)}")
    print(f"  Success: {success}, Errors: {errors}")
    print(f"  New observations: {total_obs_new}")
    print(f"  Total observations (merged): {len(merged_observations)}")
    print(f"  Total templates (merged): {len(merged_templates)}")
    print(f"  Total guides (merged): {len(merged_guides)}")


if __name__ == "__main__":
    asyncio.run(main())
