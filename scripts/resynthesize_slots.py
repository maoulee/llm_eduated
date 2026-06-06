"""Re-synthesize slot experience cards from existing question experiences.

Reads data/question_experiences/*.md (Phase 1 output already exists),
groups by slot_id, formats SLOT_SYNTHESIS_PROMPT_SC/COMP, and calls
local vLLM to produce high-quality experience cards.

Preserves the 13 existing good cards in data/slot_experiences/.
Only re-synthesizes the 34 missing slots.

Usage:
    python scripts/resynthesize_slots.py
    python scripts/resynthesize_slots.py --slots Q1 Q2 Q3
    python scripts/resynthesize_slots.py --force          # overwrite existing
    python scripts/resynthesize_slots.py --concurrency 4
    python scripts/resynthesize_slots.py --dry-run        # preview only
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core_new.llm_gateway import LLMGateway
from core_new.slot_prompts import SLOT_SYNTHESIS_PROMPT_SC, SLOT_SYNTHESIS_PROMPT_COMP


# Slot → subject / question_type mapping
SUBJECT_MAP = {
    "Q1": "数据结构", "Q2": "数据结构", "Q3": "数据结构", "Q4": "数据结构",
    "Q5": "数据结构", "Q6": "数据结构", "Q7": "数据结构", "Q8": "数据结构",
    "Q9": "数据结构", "Q10": "数据结构", "Q11": "数据结构",
    "Q12": "计算机组成原理", "Q13": "计算机组成原理", "Q14": "计算机组成原理",
    "Q15": "计算机组成原理", "Q16": "计算机组成原理", "Q17": "计算机组成原理",
    "Q18": "计算机组成原理", "Q19": "计算机组成原理", "Q20": "计算机组成原理",
    "Q21": "计算机组成原理", "Q22": "计算机组成原理",
    "Q23": "操作系统", "Q24": "操作系统", "Q25": "操作系统", "Q26": "操作系统",
    "Q27": "操作系统", "Q28": "操作系统", "Q29": "操作系统", "Q30": "操作系统",
    "Q31": "操作系统", "Q32": "操作系统",
    "Q33": "计算机网络", "Q34": "计算机网络", "Q35": "计算机网络", "Q36": "计算机网络",
    "Q37": "计算机网络", "Q38": "计算机网络", "Q39": "计算机网络", "Q40": "计算机网络",
    "Q41": "数据结构", "Q42": "数据结构",
    "Q43": "计算机组成原理", "Q44": "计算机组成原理",
    "Q45": "操作系统", "Q46": "操作系统", "Q47": "操作系统",
}

COMP_SLOTS = {"Q41", "Q42", "Q43", "Q44", "Q45", "Q46", "Q47"}


def extract_k_values(text: str) -> dict:
    """Extract K1-K5 from question experience markdown."""
    ks = {}
    for m in re.finditer(r"\*\*K(\d)\s*=\s*(\d+)\*\*", text):
        ks[f"K{m.group(1)}"] = int(m.group(2))
    return ks


def extract_field(text: str, label: str) -> str:
    """Extract a - **label**: value line from markdown."""
    m = re.search(rf"\*\*{re.escape(label)}\*\*:\s*(.+)", text)
    return m.group(1).strip() if m else ""


def extract_section(text: str, heading: str) -> str:
    """Extract content under a ## heading."""
    pattern = rf"^##\s+{re.escape(heading)}\s*$"
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        return ""
    start = m.end()
    next_h = re.search(r"^##\s+", text[start:], re.MULTILINE)
    end = start + next_h.start() if next_h else len(text)
    return text[start:end].strip()


def build_eval_entry(filepath: str) -> str | None:
    """Build a single evaluation entry string from a question experience MD file."""
    text = Path(filepath).read_text(encoding="utf-8")
    if not text.strip():
        return None

    # Extract basics from header
    year_match = re.search(r"\*\*年份\*\*:\s*(\d+)", text)
    slot_match = re.search(r"\*\*题位\*\*:\s*(Q\d+)", text)
    year = year_match.group(1) if year_match else "?"
    slot_id = slot_match.group(1) if slot_match else Path(filepath).stem.split("_")[1]

    # Extract knowledge point name from title or basic info
    title_match = re.search(rf"# {year} {slot_id}\s*—\s*(.+)", text)
    name = title_match.group(1).strip() if title_match else extract_field(text, "知识点")

    # K values
    ks = extract_k_values(text)
    k_str = ", ".join(f"K{i}={ks.get(f'K{i}', '?')}" for i in range(1, 6))

    # Radar shape
    radar = extract_field(text, "雷达形状")

    # Knowledge points
    kp = extract_field(text, "知识点")

    # Examination mode
    mode = extract_field(text, "模式")

    # Core trap
    trap = extract_field(text, "核心陷阱")

    # Examination ability
    ability = extract_section(text, "考察能力")

    # Stem
    stem_section = extract_section(text, "题干原文")

    # Option analysis (for SC)
    opt_section = extract_section(text, "选项级分析")

    # Interference strategy
    distractor = extract_field(text, "干扰策略")

    # Build entry
    parts = [f"### {year}年 — {name}"]
    parts.append(f"- **K值**: {k_str}")
    parts.append(f"- **雷达形状**: {radar}")
    parts.append(f"- **知识点**: {kp}")

    if opt_section:
        parts.append(f"- **选项分析**:\n{opt_section}")
    if distractor:
        parts.append(f"- **干扰策略**: {distractor}")
    if mode:
        parts.append(f"- **考察模式**: {mode}")
    if trap:
        parts.append(f"- **核心陷阱**: {trap}")
    if ability:
        parts.append(f"- **考察能力**: {ability}")

    parts.append(f"- **题干原文**: {stem_section[:500]}")

    return "\n".join(parts)


def build_synthesis_prompt(slot_id: str, entries: list[str]) -> list[dict]:
    """Build the synthesis prompt message for a slot."""
    is_comp = slot_id in COMP_SLOTS
    subject = SUBJECT_MAP.get(slot_id, "未知")
    typical_score = 10 if is_comp else 2
    question_count = len(entries)
    evaluations_data = "\n\n".join(entries)

    prompt_template = SLOT_SYNTHESIS_PROMPT_COMP if is_comp else SLOT_SYNTHESIS_PROMPT_SC
    prompt = prompt_template.format(
        slot_id=slot_id,
        subject_stability=subject,
        typical_score=typical_score,
        question_count=question_count,
        evaluations_data=evaluations_data,
    )

    return [{"role": "user", "content": prompt}]


async def resynthesize(
    slots: list[str] | None = None,
    concurrency: int = 4,
    force: bool = False,
    dry_run: bool = False,
):
    """Main re-synthesis logic."""
    repo_root = Path(__file__).parent.parent
    qexp_dir = repo_root / "data" / "question_experiences"
    slot_exp_dir = repo_root / "data" / "slot_experiences"
    slot_exp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Group question experiences by slot (ONLY real exam questions, not exercise_*)
    files_by_slot: dict[str, list[str]] = defaultdict(list)
    for f in sorted(os.listdir(qexp_dir)):
        if not f.endswith(".md"):
            continue
        # Only include real exam questions: YYYY_Qxx format (e.g. 2009_Q1)
        m = re.match(r"(19|20)\d{2}_(Q\d+)", f)
        if m:
            files_by_slot[m.group(2)].append(str(qexp_dir / f))

    # 2. Determine which slots need synthesis
    target_slots = slots or sorted(files_by_slot.keys(), key=lambda x: int(x[1:]))

    todo = []
    for sid in target_slots:
        if sid not in files_by_slot:
            print(f"  SKIP {sid}: no question experiences found")
            continue
        out_path = slot_exp_dir / f"{sid}_experience.md"
        if out_path.exists() and not force:
            print(f"  SKIP {sid}: already exists (use --force to overwrite)")
            continue
        todo.append(sid)

    if not todo:
        print("Nothing to do. All slot experiences exist.")
        return

    print(f"Slots to synthesize: {len(todo)} ({', '.join(todo)})")
    total_qexp = sum(len(files_by_slot[s]) for s in todo)
    print(f"Total question experiences to process: {total_qexp}")

    if dry_run:
        for sid in todo:
            is_comp = sid in COMP_SLOTS
            print(f"  {sid}: {len(files_by_slot[sid])} experiences, "
                  f"type={'综合题' if is_comp else '选择题'}")
        return

    # 3. Build eval entries and prompts
    slot_prompts = {}
    slot_entry_counts = {}
    for sid in todo:
        entries = []
        for fp in files_by_slot[sid]:
            entry = build_eval_entry(fp)
            if entry:
                entries.append(entry)
        if not entries:
            print(f"  WARN {sid}: no valid entries built, skipping")
            continue
        slot_prompts[sid] = build_synthesis_prompt(sid, entries)
        slot_entry_counts[sid] = len(entries)

    print(f"Built {len(slot_prompts)} prompts")

    # 4. Initialize local vLLM gateway
    print("Initializing local vLLM gateway...")
    gateway = LLMGateway("api_vllm")
    print(f"  Gateway: {gateway._model_name}")

    # 5. Batch synthesize
    slot_order = sorted(slot_prompts.keys(), key=lambda x: int(x[1:]))

    for start in range(0, len(slot_order), concurrency):
        batch = slot_order[start:start + concurrency]
        print(f"\nBatch {start // concurrency + 1}: {', '.join(batch)}")

        messages_batch = [slot_prompts[sid] for sid in batch]
        t0 = time.monotonic()
        results = await gateway.generate_text_batch(messages_batch, enable_thinking=False)
        elapsed = time.monotonic() - t0

        success = 0
        for sid, result in zip(batch, results):
            out_path = slot_exp_dir / f"{sid}_experience.md"
            if result.ok and result.content:
                is_comp = sid in COMP_SLOTS
                header = (
                    f"# {sid} 题位经验\n\n"
                    f"## 基本信息\n"
                    f"- **题位**: {sid}\n"
                    f"- **科目**: {SUBJECT_MAP.get(sid, '未知')}\n"
                    f"- **题型**: {'综合应用题' if is_comp else '选择题'}\n"
                    f"- **分值**: {'10' if is_comp else '2'}分\n\n"
                    f"---\n\n"
                )
                out_path.write_text(header + result.content, encoding="utf-8")
                success += 1
                print(f"  {sid}: OK ({len(result.content)} chars, {elapsed:.1f}s)")
            else:
                print(f"  {sid}: FAILED — {result.error_message or 'empty'}")

        print(f"  Batch result: {success}/{len(batch)} OK, {elapsed:.1f}s")

    print(f"\nDone. Slot experiences saved to {slot_exp_dir}/")


def main():
    parser = argparse.ArgumentParser(description="Re-synthesize slot experience cards")
    parser.add_argument("--slots", nargs="+", help="Specific slots to synthesize (e.g. Q1 Q2 Q3)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing experience cards")
    parser.add_argument("--concurrency", type=int, default=4, help="Batch size for LLM calls")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no LLM calls")
    args = parser.parse_args()

    asyncio.run(resynthesize(
        slots=args.slots,
        concurrency=args.concurrency,
        force=args.force,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    main()
