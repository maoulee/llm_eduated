"""Compose + Generate for CO and DS sections separately using WebGPT.

Phase A (Compose): GPT generates outlines for each subject independently
Phase B (Generate): WebGPT generates questions one by one for each slot

Usage:
    python scripts/compose_co_ds.py compose   # Step 1: Generate outlines
    python scripts/compose_co_ds.py generate  # Step 2: Generate questions
    python scripts/compose_co_ds.py all       # Run both
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Subject configs ──────────────────────────────────────────

# CO slots (all existing slots are CO)
CO_SLOTS = ["Q12", "Q13", "Q14", "Q15", "Q16", "Q17", "Q18", "Q19", "Q20", "Q21", "Q22",
            "Q43", "Q44", "Q45"]

# DS slots — reuse slot structure, composer assigns DS knowledge points
# 5 选择题 + 1 综合题 for DS section
DS_SLOTS = ["Q12", "Q13", "Q14", "Q15", "Q16", "Q17", "Q43"]

SUBJECTS = {
    "co": {
        "name": "计算机组成原理",
        "slots": CO_SLOTS,
        "requirements": (
            "出一份408模拟卷的【计算机组成原理】部分。"
            "所有题位必须覆盖计算机组成原理的知识点，"
            "包括：计算机系统概述、数据的表示和运算、存储器层次结构、"
            "指令系统、中央处理器(CPU)、总线、I/O系统。"
            "难度中等偏上，覆盖主要知识域，避免连续多题考同一知识点。"
            "综合应用题需要涉及计算或设计分析。"
        ),
    },
    "ds": {
        "name": "数据结构",
        "slots": DS_SLOTS,
        "requirements": (
            "出一份408模拟卷的【数据结构】部分。"
            "所有题位必须覆盖数据结构的知识点，"
            "包括：线性表、栈/队列/数组、树与二叉树、图、查找、排序、"
            "散列表、字符串模式匹配。"
            "选择题覆盖基础概念和算法分析，综合应用题需要涉及算法设计或手动模拟。"
            "难度中等偏上，覆盖主要知识域。"
        ),
    },
}


def _load_templates(slot_ids: list[str]) -> dict:
    """Load slot templates from JSON, filtered to given slot IDs."""
    tpl_path = Path("data/config/slot_templates.json")
    if not tpl_path.exists():
        print(f"ERROR: {tpl_path} not found")
        return {}
    with open(tpl_path, encoding="utf-8") as f:
        all_templates = json.load(f).get("templates", {})
    return {k: v for k, v in all_templates.items() if k in slot_ids}


def _load_exp_cards(slot_ids: list[str]) -> dict:
    """Load experience cards for given slots."""
    cards = {}
    exp_dir = Path("data/slot_experiences")
    if not exp_dir.is_dir():
        return cards
    for fname in os.listdir(exp_dir):
        if fname.endswith("_experience.md"):
            sid = fname.replace("_experience.md", "")
            if sid in slot_ids:
                cards[sid] = (exp_dir / fname).read_text(encoding="utf-8")
    return cards


# ── WebGPT routing config ────────────────────────────────────

WEBGPT_ROUTING = {
    "paper_composer": "hybrid",    # GPT composes outline
    "question_sc": "webgpt",
    "question_comp": "webgpt",
    "review": "webgpt",
    "solve": "webgpt",
    "final_review": "webgpt",
}

# Compose uses gpt-instant (no thinking delay), generate uses gpt-thinking
COMPOSE_MODEL = "gpt-instant"
GENERATE_MODEL = "gpt-thinking"


# ── Phase A: Compose ─────────────────────────────────────────

async def compose_subject(subject_key: str) -> dict | None:
    """Run compose for a single subject."""
    # Use gpt-instant for compose (no thinking delay issues)
    os.environ["WEBGPT_MODEL"] = COMPOSE_MODEL
    cfg = SUBJECTS[subject_key]
    print(f"\n{'='*60}")
    print(f"Compose: {cfg['name']} ({len(cfg['slots'])} slots)")
    print(f"{'='*60}")

    templates = _load_templates(cfg["slots"])
    if not templates:
        print(f"  ERROR: no templates loaded for {subject_key}")
        return None

    exp_cards = _load_exp_cards(cfg["slots"])
    print(f"  Templates: {len(templates)}, Experience cards: {len(exp_cards)}")

    from core_new.provider_router import get_routed_gateway
    from compose.compose_runner import run_compose

    gateway = get_routed_gateway("paper_composer")

    output_dir = f"docs/compose_{subject_key}"
    result = await run_compose(
        gateway,
        templates,
        exp_cards,
        user_requirements=cfg["requirements"],
        slot_ids=cfg["slots"],
        output_dir=output_dir,
        model_routing=WEBGPT_ROUTING,
    )

    if result.get("status") != "ok":
        print(f"  ERROR: compose failed — {result}")
        return None

    print(f"  Done: {result['slot_count']} slots, run_id={result.get('run_id')}")
    return result


async def run_compose_all():
    """Compose both CO and DS sections."""
    results = {}
    for key in ["co", "ds"]:
        result = await compose_subject(key)
        if result:
            results[key] = result
        else:
            print(f"\n  WARNING: {key} compose failed, skipping")

    # Save compose summary
    summary_path = Path("docs/compose_summary.json")
    summary = {}
    for key, result in results.items():
        summary[key] = {
            "compose_dir": result["compose_dir"],
            "slot_count": result["slot_count"],
            "run_id": result.get("run_id"),
            "skeleton_violations": result.get("skeleton_violations", []),
        }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nCompose summary saved: {summary_path}")
    return results


# ── Phase B: Generate ────────────────────────────────────────

async def generate_subject(subject_key: str, compose_result: dict | None = None):
    """Generate questions for a single subject using WebGPT."""
    # Use gpt-thinking for generate (deeper reasoning for question creation)
    os.environ["WEBGPT_MODEL"] = GENERATE_MODEL
    cfg = SUBJECTS[subject_key]

    # Determine compose dir
    if compose_result:
        compose_dir = compose_result["compose_dir"]
    else:
        compose_dir = f"docs/compose_{subject_key}/compose"
        if not Path(compose_dir).exists():
            print(f"  ERROR: {compose_dir} not found. Run compose first.")
            return []

    run_id = None
    if compose_result:
        run_id = compose_result.get("run_id")
    else:
        # Try reading from manifest
        from compose.generate_runner import _read_run_id_from_manifest
        run_id = _read_run_id_from_manifest(compose_dir)

    print(f"\n{'='*60}")
    print(f"Generate: {cfg['name']} (run_id={run_id})")
    print(f"{'='*60}")

    from core_new.llm_gateway import get_gateway
    from compose.generate_runner import run_generate

    gateway = get_gateway("glm5.1")

    output_dir = f"docs/output_{subject_key}"
    result = await run_generate(
        gateway,
        compose_dir=compose_dir,
        output_dir=output_dir,
        model_routing=WEBGPT_ROUTING,
        run_id=run_id,
    )

    print(f"\n  Generated {len(result.get('final_questions', []))} questions in {result.get('total_time_s', 0):.1f}s")
    return result


async def run_generate_all():
    """Generate questions for both subjects."""
    # Load compose summary
    summary_path = Path("docs/compose_summary.json")
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = {}

    results = {}
    for key in ["co", "ds"]:
        compose_result = summary.get(key)
        result = await generate_subject(key, compose_result)
        if result:
            results[key] = result

    return results


# ── Aggregate ────────────────────────────────────────────────

async def aggregate():
    """Aggregate both sections into final exam paper."""
    print(f"\n{'='*60}")
    print("Aggregating CO + DS sections")
    print(f"{'='*60}")

    all_questions = []
    for key in ["co", "ds"]:
        result_path = Path(f"docs/output_{key}/slot_composition_result.json")
        if not result_path.exists():
            print(f"  WARNING: {result_path} not found, skipping {key}")
            continue
        data = json.loads(result_path.read_text(encoding="utf-8"))
        questions = data.get("final_questions", [])
        print(f"  {SUBJECTS[key]['name']}: {len(questions)} questions")
        all_questions.extend(questions)

    if not all_questions:
        print("  ERROR: no questions to aggregate")
        return

    # Sort by slot_id
    all_questions.sort(key=lambda q: q.get("slot_id", "Z99"))

    # Write aggregated result
    output = {
        "paper_title": "408模拟卷 — 计算机组成原理 + 数据结构",
        "total_questions": len(all_questions),
        "sections": list(SUBJECTS.keys()),
        "questions": all_questions,
        "aggregated_at": datetime.now().isoformat(),
    }
    out_path = Path("docs/exam_co_ds.json")
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n  Aggregated {len(all_questions)} questions → {out_path}")

    # Build markdown exam paper
    md_lines = [
        f"# 408模拟卷 — 计算机组成原理 + 数据结构",
        "",
        f"- 总题数: {len(all_questions)}",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
    ]
    for q in all_questions:
        sid = q.get("slot_id", "?")
        final_md = q.get("final_md", "")
        if final_md:
            md_lines.append(final_md)
        else:
            md_lines.append(f"## {sid}\n\n(生成失败)")
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    md_path = Path("docs/exam_co_ds.md")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"  Markdown exam → {md_path}")


# ── Main ─────────────────────────────────────────────────────

async def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if cmd == "compose":
        await run_compose_all()
    elif cmd == "generate":
        await run_generate_all()
        await aggregate()
    elif cmd == "aggregate":
        await aggregate()
    elif cmd == "all":
        compose_results = await run_compose_all()
        if compose_results:
            await run_generate_all()
            await aggregate()
    else:
        print(f"Usage: python {sys.argv[0]} [compose|generate|aggregate|all]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
