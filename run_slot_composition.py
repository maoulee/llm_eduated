"""Run slot-template driven paper composition and generation.

Pipeline:
  1. Load SlotTemplates + experience cards
  2. PaperComposer → PaperBlueprint (SlotBlueprint per position)
  3. QuestionWriter → question per slot (parallel)
  4. QualityReviewer → review + revision loop

Usage:
    GLM_API_KEY=xxx .venv/bin/python run_slot_composition.py
    GLM_API_KEY=xxx .venv/bin/python run_slot_composition.py --slots Q12 Q13 Q14
"""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from core_new.agents.slot_agents import (
    PaperComposerAgent,
    QuestionWriterAgent,
    QualityReviewerAgent,
)
from core_new.blackboard import Blackboard
from core_new.llm_gateway import get_gateway


async def run_composition(
    gateway,
    slot_templates: dict,
    experience_cards: dict,
    user_requirements: str,
    slot_ids: list = None,
    max_revisions: int = 1,
) -> dict:
    """Run the full composition pipeline."""
    # Filter templates if specific slots requested
    if slot_ids:
        templates = {k: v for k, v in slot_templates.items() if k in slot_ids}
    else:
        templates = slot_templates

    if not templates:
        print("No templates to compose from!")
        return {}

    total_start = time.monotonic()

    # ══════════════════════════════════════════════════════════
    # Step 1: PaperComposer → PaperBlueprint
    # ══════════════════════════════════════════════════════════
    print("=" * 60)
    print("Step 1: PaperComposer — 规划试卷蓝图")
    print("=" * 60)

    composer = PaperComposerAgent(gateway)
    bb = Blackboard(
        task_id="compose",
        task_type="slot_composition",
        initial_state={
            "slot_templates": templates,
            "user_requirements": user_requirements,
            "total_slots": len(templates),
        },
    )

    t0 = time.monotonic()
    record = await composer.execute(bb)
    compose_time = time.monotonic() - t0

    if record.error:
        print(f"  ERROR: {record.error}")
        return {"status": "error", "step": "compose", "error": record.error}

    blueprint = bb.get("paper_blueprint") or {}
    slot_blueprints = blueprint.get("slots", [])

    print(f"  耗时: {compose_time:.1f}s")
    print(f"  题位数: {len(slot_blueprints)}")
    print(f"  组卷思路: {blueprint.get('composition_rationale', 'N/A')[:200]}")

    for sb in slot_blueprints:
        print(
            f"    {sb.get('slot_id')}: {sb.get('target_subject','?')}/{sb.get('primary_target_name','?')} "
            f"d={sb.get('target_difficulty','?')} role={sb.get('paper_role','?')}"
        )

    # ══════════════════════════════════════════════════════════
    # Step 2: QuestionWriter → questions per slot
    # ══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print(f"Step 2: QuestionWriter — 出题 ({len(slot_blueprints)}题)")
    print("=" * 60)

    writer = QuestionWriterAgent(gateway)
    questions = []

    for sb in slot_blueprints:
        slot_id = sb.get("slot_id", "Q12")
        print(f"  [{slot_id}] Generating question...")

        qbb = Blackboard(
            task_id=f"write_{slot_id}",
            task_type="slot_composition",
            initial_state={
                "current_blueprint": sb,
                "reference_questions": experience_cards.get(slot_id, ""),
            },
        )

        t0 = time.monotonic()
        q_record = await writer.execute(qbb)
        q_time = time.monotonic() - t0

        if q_record.error:
            print(f"  [{slot_id}] ERROR: {q_record.error[:200]}")
            questions.append({"slot_id": slot_id, "status": "error", "error": q_record.error})
        else:
            q_data = qbb.get("generated_question") or {}
            q_data["slot_id"] = slot_id
            q_data["generation_time_s"] = round(q_time, 1)
            questions.append(q_data)
            answer = q_data.get("correct_answer", "?")
            stem_preview = q_data.get("stem", "")[:80]
            print(f"  [{slot_id}] Done ({q_time:.1f}s): answer={answer} — {stem_preview}...")

    # ══════════════════════════════════════════════════════════
    # Step 3: QualityReviewer → review
    # ══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("Step 3: QualityReviewer — 质量评审")
    print("=" * 60)

    reviewer = QualityReviewerAgent(gateway)
    rbb = Blackboard(
        task_id="review",
        task_type="slot_composition",
        initial_state={
            "paper_blueprint": blueprint,
            "generated_questions": questions,
            "slot_templates": templates,
        },
    )

    t0 = time.monotonic()
    r_record = await reviewer.execute(rbb)
    review_time = time.monotonic() - t0

    review = rbb.get("paper_review") or {}
    print(f"  耗时: {review_time:.1f}s")
    print(f"  状态: {review.get('overall_status', 'N/A')}")
    print(f"  评分: {review.get('overall_score', 'N/A')}/100")
    print(f"  评价: {review.get('overall_comment', 'N/A')[:200]}")

    for sr in review.get("slot_reviews", []):
        status = sr.get("status", "?")
        score = sr.get("quality_score", "?")
        issue = sr.get("issue", "无")[:100]
        print(f"    {sr.get('slot_id')}: {status} ({score}/10) — {issue}")

    total_time = time.monotonic() - total_start

    # ══════════════════════════════════════════════════════════
    # Save results
    # ══════════════════════════════════════════════════════════
    output = {
        "user_requirements": user_requirements,
        "paper_blueprint": blueprint,
        "generated_questions": questions,
        "quality_review": review,
        "total_time_s": round(total_time, 1),
        "compose_time_s": round(compose_time, 1),
        "review_time_s": round(review_time, 1),
    }

    os.makedirs("docs", exist_ok=True)
    output_path = "docs/slot_composition_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n结果已保存到: {output_path}")

    return output


async def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--slots", nargs="+", help="Specific slots (e.g., Q12 Q13)")
    parser.add_argument("--requirements", default="出一套标准难度的408模拟卷（计算机组成原理选择题部分），难度分布均匀，覆盖主要知识点")
    args = parser.parse_args()

    # Load templates
    tpl_path = "data/slot_templates.json"
    if not os.path.exists(tpl_path):
        print(f"Templates not found: {tpl_path}")
        print("Run slot_extractor.py first.")
        return

    with open(tpl_path, encoding="utf-8") as f:
        tpl_data = json.load(f)
    templates = tpl_data.get("templates", {})

    # Load experience cards
    exp_cards = {}
    exp_dir = "data/slot_experiences"
    if os.path.isdir(exp_dir):
        for fname in os.listdir(exp_dir):
            if fname.endswith("_experience.md"):
                slot_id = fname.replace("_experience.md", "")
                with open(os.path.join(exp_dir, fname), encoding="utf-8") as f:
                    exp_cards[slot_id] = f.read()

    print(f"Loaded {len(templates)} templates, {len(exp_cards)} experience cards")

    gateway = get_gateway("glm5.1")
    await run_composition(
        gateway,
        slot_templates=templates,
        experience_cards=exp_cards,
        user_requirements=args.requirements,
        slot_ids=args.slots,
    )


if __name__ == "__main__":
    asyncio.run(main())
