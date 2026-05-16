"""Run slot-template driven paper composition and generation.

Pipeline:
  1. PaperComposer → PaperBlueprint (SlotBlueprint per position)
  2. BlueprintReviewer → review blueprint (revise if needed)
  3. QuestionWriter × N → question per slot (parallel, gateway handles concurrency)
  4. PaperReviewer → whole-paper review with issue categorization
  5. Fix loop: answer_error → QuestionFixer, content_mismatch → regenerate
  6. Repeat review until pass or max iterations

Usage:
    GLM_API_KEY=xxx .venv/bin/python run_slot_composition.py
    GLM_API_KEY=xxx .venv/bin/python run_slot_composition.py --slots Q12 Q13 Q14
    GLM_API_KEY=xxx .venv/bin/python run_slot_composition.py --max-fix-rounds 2
"""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from core_new.agents.slot_agents import (
    PaperComposerAgent,
    BlueprintReviewerAgent,
    QuestionWriterAgent,
    QuestionFixerAgent,
    PaperReviewerAgent,
)
from core_new.blackboard import Blackboard
from core_new.llm_gateway import get_gateway


# ── Step 1: Compose ───────────────────────────────────────────


async def compose_paper(gateway, templates, user_requirements) -> dict:
    """Step 1: PaperComposer → PaperBlueprint."""
    print("=" * 60)
    print("Step 1: PaperComposer — 规划试卷蓝图")
    print("=" * 60)

    bb = Blackboard(
        task_id="compose",
        task_type="slot_composition",
        initial_state={
            "slot_templates": templates,
            "user_requirements": user_requirements,
            "total_slots": len(templates),
        },
    )

    composer = PaperComposerAgent(gateway)
    t0 = time.monotonic()
    record = await composer.execute(bb)
    elapsed = time.monotonic() - t0

    if record.error:
        print(f"  ERROR: {record.error}")
        return {}

    blueprint = bb.get("paper_blueprint") or {}
    slots = blueprint.get("slots", [])

    print(f"  耗时: {elapsed:.1f}s")
    print(f"  题位数: {len(slots)}")
    print(f"  组卷思路: {blueprint.get('composition_rationale', 'N/A')[:200]}")

    for sb in slots:
        print(
            f"    {sb.get('slot_id')}: {sb.get('target_subject','?')}/{sb.get('primary_target_name','?')} "
            f"d={sb.get('target_difficulty','?')} role={sb.get('paper_role','?')}"
        )

    return blueprint


# ── Step 2: Review Blueprint ──────────────────────────────────


async def review_blueprint(gateway, blueprint, templates, user_requirements, max_revisions=1) -> dict:
    """Step 2: BlueprintReviewer → pass or revise blueprint."""
    print("\n" + "=" * 60)
    print("Step 2: BlueprintReviewer — 审核蓝图")
    print("=" * 60)

    reviewer = BlueprintReviewerAgent(gateway)

    for attempt in range(max_revisions + 1):
        bb = Blackboard(
            task_id=f"review_bp_{attempt}",
            task_type="slot_composition",
            initial_state={
                "paper_blueprint": blueprint,
                "slot_templates": templates,
                "user_requirements": user_requirements,
            },
        )

        t0 = time.monotonic()
        record = await reviewer.execute(bb)
        elapsed = time.monotonic() - t0

        if record.error:
            print(f"  ERROR: {record.error}")
            return blueprint

        review = bb.get("blueprint_review") or {}
        status = review.get("status", "unknown")
        print(f"  耗时: {elapsed:.1f}s")
        print(f"  状态: {status}")
        print(f"  评价: {review.get('comment', 'N/A')[:200]}")

        for sr in review.get("slot_reviews", []):
            if sr.get("status") == "revise":
                print(f"    {sr.get('slot_id')}: REVISE — {sr.get('issue','?')[:100]}")

        if status == "pass":
            print("  蓝图审核通过")
            return blueprint

        if attempt >= max_revisions:
            print(f"  达到最大修订次数({max_revisions})，使用当前蓝图")
            return blueprint

        # Revise blueprint based on review feedback
        print(f"  蓝图需要修订，重新组卷... (attempt {attempt + 1}/{max_revisions})")
        blueprint = await compose_paper(gateway, templates, user_requirements)
        if not blueprint:
            return blueprint

    return blueprint


# ── Step 3: Generate Questions (parallel) ─────────────────────


async def generate_questions(gateway, slot_blueprints, experience_cards) -> list:
    """Step 3: QuestionWriter × N in parallel (gateway controls concurrency)."""
    print("\n" + "=" * 60)
    print(f"Step 3: QuestionWriter — 出题 ({len(slot_blueprints)}题，并行)")
    print("=" * 60)

    writer = QuestionWriterAgent(gateway)

    async def _write_one(sb):
        slot_id = sb.get("slot_id", "Q12")
        print(f"  [{slot_id}] Generating...")

        qbb = Blackboard(
            task_id=f"write_{slot_id}",
            task_type="slot_composition",
            initial_state={
                "current_blueprint": sb,
                "reference_questions": experience_cards.get(slot_id, ""),
            },
        )

        t0 = time.monotonic()
        record = await writer.execute(qbb)
        elapsed = time.monotonic() - t0

        if record.error:
            print(f"  [{slot_id}] ERROR: {record.error[:200]}")
            return {"slot_id": slot_id, "status": "error", "error": record.error}

        q_data = qbb.get("generated_question") or {}
        q_data["slot_id"] = slot_id
        q_data["generation_time_s"] = round(elapsed, 1)

        answer = q_data.get("correct_answer", "?")
        stem_preview = q_data.get("stem", "")[:80]
        print(f"  [{slot_id}] Done ({elapsed:.1f}s): answer={answer} — {stem_preview}...")
        return q_data

    tasks = [_write_one(sb) for sb in slot_blueprints]
    questions = await asyncio.gather(*tasks)
    return list(questions)


# ── Step 4: Review Paper + Fix Loop ───────────────────────────


async def review_and_fix(
    gateway,
    blueprint,
    questions,
    templates,
    experience_cards,
    max_rounds=2,
) -> tuple:
    """Step 4-5: PaperReviewer → categorize issues → fix/regenerate loop."""
    print("\n" + "=" * 60)
    print("Step 4: PaperReviewer — 整卷审核")
    print("=" * 60)

    reviewer = PaperReviewerAgent(gateway)
    fixer = QuestionFixerAgent(gateway)
    writer = QuestionWriterAgent(gateway)

    current_questions = list(questions)

    for round_num in range(max_rounds + 1):
        rbb = Blackboard(
            task_id=f"review_r{round_num}",
            task_type="slot_composition",
            initial_state={
                "paper_blueprint": blueprint,
                "generated_questions": current_questions,
                "slot_templates": templates,
            },
        )

        t0 = time.monotonic()
        record = await reviewer.execute(rbb)
        elapsed = time.monotonic() - t0

        if record.error:
            print(f"  ERROR: {record.error}")
            break

        review = rbb.get("paper_review") or {}
        status = review.get("overall_status", "unknown")
        score = review.get("overall_score", "N/A")
        comment = review.get("overall_comment", "N/A")

        print(f"  耗时: {elapsed:.1f}s")
        print(f"  状态: {status}")
        print(f"  评分: {score}/100")
        print(f"  评价: {comment[:200]}")

        slot_reviews = review.get("slot_reviews", [])
        issues = []
        for sr in slot_reviews:
            s = sr.get("status", "?")
            sc = sr.get("quality_score", "?")
            issue = sr.get("issue", "无")[:100]
            print(f"    {sr.get('slot_id')}: {s} ({sc}/10) — {issue}")
            if s in ("answer_error", "content_mismatch"):
                issues.append(sr)

        if status == "pass" or not issues:
            print("  审核通过!")
            break

        if round_num >= max_rounds:
            print(f"  达到最大修复轮次({max_rounds})，停止")
            break

        # Fix issues
        print(f"\n  修复轮次 {round_num + 1}/{max_rounds}: {len(issues)} 题需要处理")

        fix_tasks = []
        for sr in issues:
            slot_id = sr.get("slot_id")
            fix_type = sr.get("status")
            fix_instruction = sr.get("fix_instruction", "")

            # Find the question
            q_idx = None
            for i, q in enumerate(current_questions):
                if q.get("slot_id") == slot_id:
                    q_idx = i
                    break

            if q_idx is None:
                continue

            if fix_type == "answer_error":
                fix_tasks.append(("fix", q_idx, slot_id, fix_instruction))
                print(f"    [{slot_id}] answer_error → Fixer")
            elif fix_type == "content_mismatch":
                fix_tasks.append(("regen", q_idx, slot_id, fix_instruction))
                print(f"    [{slot_id}] content_mismatch → Regenerate")

        # Execute fixes in parallel
        async def _do_fix(task):
            ftype, q_idx, slot_id, instruction = task
            if ftype == "fix":
                fbb = Blackboard(
                    task_id=f"fix_{slot_id}",
                    task_type="slot_composition",
                    initial_state={
                        "question_to_fix": current_questions[q_idx],
                        "fix_instructions": instruction,
                    },
                )
                record = await fixer.execute(fbb)
                if record.error:
                    return q_idx, current_questions[q_idx]
                fixed = fbb.get("fixed_question") or {}
                fixed["slot_id"] = slot_id
                print(f"    [{slot_id}] Fixed: answer={fixed.get('correct_answer','?')}")
                return q_idx, fixed
            else:  # regen
                # Find blueprint for this slot
                sb = None
                for s in blueprint.get("slots", []):
                    if s.get("slot_id") == slot_id:
                        sb = s
                        break
                if not sb:
                    return q_idx, current_questions[q_idx]

                qbb = Blackboard(
                    task_id=f"regen_{slot_id}",
                    task_type="slot_composition",
                    initial_state={
                        "current_blueprint": sb,
                        "reference_questions": experience_cards.get(slot_id, ""),
                    },
                )
                record = await writer.execute(qbb)
                if record.error:
                    return q_idx, current_questions[q_idx]
                regen = qbb.get("generated_question") or {}
                regen["slot_id"] = slot_id
                print(f"    [{slot_id}] Regenerated: answer={regen.get('correct_answer','?')}")
                return q_idx, regen

        results = await asyncio.gather(*[_do_fix(t) for t in fix_tasks])
        for q_idx, fixed_q in results:
            current_questions[q_idx] = fixed_q

        print(f"\n  修复完成，重新审核...")

    return current_questions, review


# ── Main ──────────────────────────────────────────────────────


async def run_composition(
    gateway,
    slot_templates: dict,
    experience_cards: dict,
    user_requirements: str,
    slot_ids: list = None,
    max_bp_revisions: int = 1,
    max_fix_rounds: int = 2,
) -> dict:
    """Run the full composition pipeline."""
    if slot_ids:
        templates = {k: v for k, v in slot_templates.items() if k in slot_ids}
    else:
        templates = slot_templates

    if not templates:
        print("No templates to compose from!")
        return {}

    total_start = time.monotonic()

    # Step 1: Compose
    blueprint = await compose_paper(gateway, templates, user_requirements)
    if not blueprint:
        return {"status": "error", "step": "compose"}

    # Step 2: Review blueprint
    blueprint = await review_blueprint(
        gateway, blueprint, templates, user_requirements, max_revisions=max_bp_revisions
    )
    if not blueprint:
        return {"status": "error", "step": "review_blueprint"}

    slot_blueprints = blueprint.get("slots", [])
    if not slot_blueprints:
        print("  ERROR: No slot blueprints generated")
        return {"status": "error", "step": "compose", "error": "empty slots"}

    # Step 3: Generate questions (parallel)
    questions = await generate_questions(gateway, slot_blueprints, experience_cards)

    # Step 4-5: Review + fix loop
    final_questions, final_review = await review_and_fix(
        gateway, blueprint, questions, templates, experience_cards, max_rounds=max_fix_rounds
    )

    total_time = time.monotonic() - total_start

    # Save results
    output = {
        "user_requirements": user_requirements,
        "paper_blueprint": blueprint,
        "generated_questions": final_questions,
        "quality_review": final_review,
        "total_time_s": round(total_time, 1),
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
    parser.add_argument("--max-bp-revisions", type=int, default=1, help="Max blueprint revision rounds")
    parser.add_argument("--max-fix-rounds", type=int, default=2, help="Max question fix rounds")
    args = parser.parse_args()

    tpl_path = "data/slot_templates.json"
    if not os.path.exists(tpl_path):
        print(f"Templates not found: {tpl_path}")
        print("Run slot_extractor.py first.")
        return

    with open(tpl_path, encoding="utf-8") as f:
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

    print(f"Loaded {len(templates)} templates, {len(exp_cards)} experience cards")

    gateway = get_gateway("glm5.1")
    await run_composition(
        gateway,
        slot_templates=templates,
        experience_cards=exp_cards,
        user_requirements=args.requirements,
        slot_ids=args.slots,
        max_bp_revisions=args.max_bp_revisions,
        max_fix_rounds=args.max_fix_rounds,
    )


if __name__ == "__main__":
    asyncio.run(main())
