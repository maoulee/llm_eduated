"""Standalone full pipeline test — saves to docs/test_composition_result.json.

Does NOT overwrite docs/slot_composition_result.json.

Usage:
    python run_test_composition.py                    # All 14 slots
    python run_test_composition.py --slots Q12 Q13 Q43  # Subset for quick test
    python run_test_composition.py --max-fix-rounds 0    # Skip fix loop
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_slot_composition import (
    compose_paper,
    review_blueprint,
    generate_questions,
    review_and_fix,
)
from core_new.llm_gateway import get_gateway

OUTPUT_PATH = "docs/test_composition_result.json"


def load_inputs():
    with open("data/slot_templates.json", encoding="utf-8") as f:
        tpl_data = json.load(f)
    templates = tpl_data.get("templates", {})

    exp_cards = {}
    exp_dir = "data/slot_experiences"
    if os.path.isdir(exp_dir):
        for fname in os.listdir(exp_dir):
            if fname.endswith("_experience.md"):
                slot_id = fname.replace("_experience.md", "")
                with open(os.path.join(exp_dir, fname), encoding="utf-8") as f:
                    exp_cards[slot_id] = f.read()

    return templates, exp_cards


async def run_test(slot_ids=None, max_bp_revisions=1, max_fix_rounds=1):
    templates, exp_cards = load_inputs()

    if slot_ids:
        templates = {k: v for k, v in templates.items() if k in slot_ids}
    if not templates:
        print("No templates selected!")
        return

    print(f"Loaded {len(templates)} templates, {len(exp_cards)} experience cards")
    print(f"Slots: {sorted(templates.keys())}")
    print(f"Output: {OUTPUT_PATH}")
    print()

    gateway = get_gateway("glm5.1")
    total_start = time.monotonic()
    user_requirements = "出一套标准难度的408模拟卷（计算机组成原理选择题部分），难度分布均匀，覆盖主要知识点"

    # Step 1: Compose
    blueprint = await compose_paper(gateway, templates, user_requirements)
    if not blueprint:
        print("Compose failed!")
        return

    # Step 1b: Skeleton check
    from core_new.skeleton_checker import check_blueprint_skeleton
    skeleton_violations = check_blueprint_skeleton(blueprint)
    if skeleton_violations:
        print(f"  Skeleton: {len(skeleton_violations)} violations")
        for v in skeleton_violations:
            print(f"    [{v['slot_id']}] {v['rule']}: {v['detail']}")
    else:
        print("  Skeleton: pass")

    # Step 2: Review blueprint
    blueprint, blueprint_review = await review_blueprint(
        gateway, blueprint, templates, user_requirements, max_revisions=max_bp_revisions,
    )
    if not blueprint:
        print("Blueprint review failed!")
        return

    slot_blueprints = blueprint.get("slots", [])
    if not slot_blueprints:
        print("No slot blueprints!")
        return

    # Step 3: Generate questions (parallel)
    initial_questions = await generate_questions(
        gateway, slot_blueprints, exp_cards, pipeline_mode="new",
    )

    # Step 4-5: Review + fix loop
    final_questions, final_review, revision_rounds = await review_and_fix(
        gateway, blueprint, initial_questions, templates, exp_cards,
        max_rounds=max_fix_rounds,
    )

    total_time = time.monotonic() - total_start

    # Save to separate file
    output = {
        "test_run": True,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "user_requirements": user_requirements,
        "paper_blueprint": blueprint,
        "blueprint_review": blueprint_review,
        "skeleton_violations": skeleton_violations,
        "initial_questions": initial_questions,
        "revision_rounds": revision_rounds,
        "final_questions": final_questions,
        "final_review": final_review,
        "total_time_s": round(total_time, 1),
    }

    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total time: {total_time:.1f}s")
    print(f"Questions generated: {len(final_questions)}")
    print(f"Review status: {final_review.get('overall_status', '?')}")
    print(f"Review score: {final_review.get('overall_score', '?')}/100")
    print(f"Revision rounds: {len(revision_rounds)}")

    # Per-question summary
    for q in final_questions:
        sid = q.get("slot_id", "?")
        pipeline = q.get("pipeline_type", "legacy")
        answer = str(q.get("correct_answer", q.get("answer", "?")))[:50]
        verified = q.get("codeact_verified", {})
        exec_count = q.get("python_exec_count", 0)
        v_match = ""
        if isinstance(verified, dict) and verified.get("match") is not None:
            v_match = " [MATCH]" if verified["match"] else " [MISMATCH]"
        print(f"  {sid} [{pipeline}]: answer={answer}{v_match} python_execs={exec_count}")

    print(f"\nSaved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--slots", nargs="+", help="Specific slots (e.g., Q12 Q13 Q43)")
    parser.add_argument("--max-bp-revisions", type=int, default=1)
    parser.add_argument("--max-fix-rounds", type=int, default=1)
    args = parser.parse_args()

    print(f"Start: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    asyncio.run(run_test(
        slot_ids=args.slots,
        max_bp_revisions=args.max_bp_revisions,
        max_fix_rounds=args.max_fix_rounds,
    ))
    print(f"\nDone: {time.strftime('%Y-%m-%d %H:%M:%S')}")
