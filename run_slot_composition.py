"""Run slot-template driven paper composition and generation.

Pipeline:
  1. PaperComposer → PaperBlueprint (SlotBlueprint per position)
  2. BlueprintReviewer → review blueprint (revise if needed)
  3. Generate questions per slot via UnifiedQuestionPipeline
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
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from core_new.agents.slot_agents import (
    PaperComposerAgent,
    BlueprintReviewerAgent,
    QuestionFixerAgent,
    PaperReviewerAgent,
)
from core_new.agents.unified_pipeline import UnifiedQuestionPipeline
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
    record = None
    for attempt in range(3):
        record = await composer.execute(bb)
        if not record.error:
            break
        is_network = "connection" in str(record.error).lower() or "network" in str(record.error).lower()
        if is_network and attempt < 2:
            print(f"  Network error (attempt {attempt + 1}), retrying in 15s...")
            await asyncio.sleep(15)
            continue
        break

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


async def review_blueprint(gateway, blueprint, templates, user_requirements, max_revisions=1) -> tuple:
    """Step 2: BlueprintReviewer → pass or revise blueprint. Returns (blueprint, review)."""
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
            return blueprint, {"status": "review_error", "comment": record.error, "slot_reviews": []}

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
            return blueprint, review

        if attempt >= max_revisions:
            print(f"  达到最大修订次数({max_revisions})，使用当前蓝图")
            return blueprint, review

        # Revise blueprint based on review feedback
        print(f"  蓝图需要修订，重新组卷... (attempt {attempt + 1}/{max_revisions})")
        blueprint = await compose_paper(gateway, templates, user_requirements)
        if not blueprint:
            return blueprint, review

    return blueprint, review


# ── Step 2b: Knowledge/Slot Gate ────────────────────────────────


async def knowledge_slot_gate(gateway, blueprint, templates, user_requirements):
    """Step 2b: Gate 1 — validate knowledge points before generation."""
    from core_new.agents.gate_agents import KnowledgeSlotGateAgent
    from core_new.gate_protocol import GateDecision

    print("\n" + "=" * 60)
    print("Step 2b: Knowledge/Slot Gate — 知识点审核")
    print("=" * 60)

    bb = Blackboard(
        task_id="knowledge_slot_gate",
        task_type="gate",
        initial_state={
            "paper_blueprint": blueprint,
            "slot_templates": templates,
            "user_requirements": user_requirements,
        },
    )

    agent = KnowledgeSlotGateAgent(gateway)
    record = await agent.execute(bb)

    if record.error:
        print(f"  Gate agent error: {record.error}")
        return None

    result = record.parsed or {}
    decision = result.get("decision", "pass")
    print(f"  Gate decision: {decision}")
    if result.get("issue_types"):
        for it in result["issue_types"]:
            print(f"    - {it}")
    if result.get("evidence"):
        print(f"  Evidence: {str(result['evidence'])[:300]}")
    if result.get("required_fix"):
        print(f"  Required fix: {str(result['required_fix'])[:300]}")

    return result


# ── Step 3: Generate Questions (parallel) ─────────────────────


def _is_comprehensive_slot(sb: dict) -> bool:
    """Determine if a slot blueprint is a comprehensive/subjective question."""
    q_type = sb.get("question_type", "")
    if q_type == "comprehensive":
        return True
    slot_id = sb.get("slot_id", "")
    if slot_id.startswith("Q") and slot_id[1:].isdigit() and int(slot_id[1:]) >= 43:
        return True
    sub_q = sb.get("sub_questions", "0")
    try:
        if int(sub_q) >= 2:
            return True
    except (ValueError, TypeError):
        pass
    return False


async def generate_questions(gateway, slot_blueprints, experience_cards, enable_stem_gate=False) -> list:
    """Step 3: Generate questions per slot via UnifiedQuestionPipeline."""
    print("\n" + "=" * 60)
    print(f"Step 3: 出题 ({len(slot_blueprints)}题，并行)")
    print("=" * 60)

    async def _generate_one(sb):
        slot_id = sb.get("slot_id", "Q12")
        exp_card = experience_cards.get(slot_id, "")
        return await _generate_unified(gateway, sb, slot_id, exp_card,
                                       enable_stem_gate=enable_stem_gate)

    tasks = [_generate_one(sb) for sb in slot_blueprints]
    questions = await asyncio.gather(*tasks)
    return list(questions)


async def _generate_unified(gateway, sb, slot_id, exp_card, enable_stem_gate=False):
    """Generate a question using the unified pipeline (both SC and Comp).

    UnifiedQuestionPipeline:
      Design → Options(SC) → FileCodeSolver → Format → Review → Fix loop
    Solver verifies all 4 options for SC, computes sub-questions for Comp.
    """
    is_sc = UnifiedQuestionPipeline._is_single_choice(sb)
    q_kind = "SC" if is_sc else "Comp"
    print(f"  [{slot_id}] UnifiedPipeline ({q_kind})...")
    t0 = time.monotonic()

    try:
        pipeline = UnifiedQuestionPipeline(
            max_revision_rounds=1,
            enable_stem_gate=enable_stem_gate,
        )
        result = await pipeline.run(sb, exp_card, gateway)
        elapsed = time.monotonic() - t0

        q_data = dict(result.final_question or {})
        q_data["generation_time_s"] = result.generation_time_s
        q_data["pipeline_type"] = result.pipeline_type
        q_data["review"] = result.review or {}
        q_data["solver_result"] = result.solver_result or {}
        q_data["slot_id"] = slot_id
        q_data["_blueprint"] = sb
        q_data["_experience_card"] = exp_card
        if result.stem_contract:
            q_data["stem_contract"] = result.stem_contract
        if result.stem_gate_result:
            q_data["stem_gate_result"] = result.stem_gate_result

        if is_sc:
            answer = q_data.get("correct_answer", "?")
            execs = q_data.get("python_exec_count", 0)
            review_status = result.review.get("status", "?")
            print(f"  [{slot_id}] Unified SC done ({elapsed:.1f}s): "
                  f"answer={answer} python_execs={execs} review={review_status}")
        else:
            answer = str(q_data.get("answer", "?"))[:80]
            execs = q_data.get("python_exec_count", 0)
            review_status = result.review.get("status", "?")
            print(f"  [{slot_id}] Unified Comp done ({elapsed:.1f}s): "
                  f"answer={answer} python_execs={execs} review={review_status}")

        return q_data

    except (asyncio.TimeoutError, Exception) as e:
        elapsed = time.monotonic() - t0
        reason = "timeout" if isinstance(e, asyncio.TimeoutError) else str(e)[:100]
        print(f"  [{slot_id}] Unified pipeline failed ({elapsed:.1f}s): {reason}")
        return {"slot_id": slot_id, "status": "error", "error": str(e), "pipeline_type": "unified"}



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

    current_questions = list(questions)
    revision_rounds = []

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

        # P0-1: return immediately on reviewer error instead of breaking to unbound review
        if record.error:
            print(f"  ERROR: {record.error}")
            return current_questions, {
                "overall_status": "review_error",
                "overall_comment": record.error,
                "slot_reviews": [],
            }, revision_rounds

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

        # P0-2: only pass on explicit "pass"; flag unparseable issues
        if status == "pass":
            print("  审核通过!")
            break

        if status != "pass" and not issues:
            print("  WARNING: reviewer reported issues but no actionable fix targets parsed")
            review["overall_status"] = "needs_human_review"
            review["overall_comment"] = str(review.get("overall_comment") or "") + (
                " Reviewer reported issues but no actionable fix targets were parsed."
            )
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
        async def _do_regen(slot_id: str, q_idx: int, instruction: str):
            """Regenerate a question, routing by pipeline type."""
            sb = None
            for s in blueprint.get("slots", []):
                if s.get("slot_id") == slot_id:
                    sb = s
                    break
            if not sb:
                return q_idx, current_questions[q_idx]

            orig_q = current_questions[q_idx]

            # Always use UnifiedQuestionPipeline for regeneration (handles both SC and Comp)
            print(f"    [{slot_id}] Regenerating via UnifiedQuestionPipeline...")
            try:
                pipeline = UnifiedQuestionPipeline(max_revision_rounds=1)
                result = await pipeline.run(sb, experience_cards.get(slot_id, ""), gateway)
                regen = dict(result.final_question or {})
                regen["slot_id"] = slot_id
                regen["pipeline_type"] = result.pipeline_type
                regen["review"] = result.review or {}
                regen["solver_result"] = result.solver_result or {}
                regen["revision_type"] = "regenerate"
                regen["regenerate_reason"] = instruction
                regen["revision_round"] = round_num + 1
                answer_preview = str(regen.get("correct_answer", regen.get("answer", "?")))[:80]
                print(f"    [{slot_id}] Unified regen done: answer={answer_preview}")
                return q_idx, regen
            except Exception as e:
                print(f"    [{slot_id}] Unified regen failed ({e}), keeping original")
                return q_idx, current_questions[q_idx]
            return q_idx, regen

        async def _do_fix(task):
            ftype, q_idx, slot_id, instruction = task
            orig_q = current_questions[q_idx]
            orig_pipeline_type = orig_q.get("pipeline_type", "")

            if ftype == "fix":
                # For comprehensive questions, answer_fix should upgrade to regen
                # because QuestionFixerAgent produces single-choice format
                sb = None
                for s in blueprint.get("slots", []):
                    if s.get("slot_id") == slot_id:
                        sb = s
                        break

                if sb and _is_comprehensive_slot(sb):
                    print(f"    [{slot_id}] answer_error on comprehensive → upgrading to regen")
                    return await _do_regen(slot_id, q_idx, instruction)

                fbb = Blackboard(
                    task_id=f"fix_{slot_id}",
                    task_type="slot_composition",
                    initial_state={
                        "question_to_fix": orig_q,
                        "fix_instructions": instruction,
                    },
                )
                record = await fixer.execute(fbb)
                if record.error:
                    return q_idx, orig_q
                fixed = fbb.get("fixed_question") or {}
                fixed["slot_id"] = slot_id
                fixed["revision_type"] = "answer_fix"
                fixed["fix_instruction"] = instruction
                fixed["revision_round"] = round_num + 1
                fixed["pipeline_type"] = fixed.get("pipeline_type") or orig_pipeline_type
                print(f"    [{slot_id}] Fixed: answer={fixed.get('correct_answer','?')}")
                return q_idx, fixed
            else:  # regen
                return await _do_regen(slot_id, q_idx, instruction)

        # Snapshot questions before fix for round record
        questions_before_fix = [dict(q) for q in current_questions]

        results = await asyncio.gather(*[_do_fix(t) for t in fix_tasks])
        fix_actions = []
        for q_idx, fixed_q in results:
            slot_id = fixed_q.get("slot_id", "?")
            fix_actions.append({
                "slot_id": slot_id,
                "revision_type": fixed_q.get("revision_type", "unknown"),
                "instruction": (
                    fixed_q.get("fix_instruction")
                    or fixed_q.get("regenerate_reason")
                    or ""
                ),
            })
            current_questions[q_idx] = fixed_q

        # Record this round
        revision_rounds.append({
            "round": round_num + 1,
            "issues_found": [{"slot_id": sr.get("slot_id"), "status": sr.get("status"), "issue": sr.get("issue", "")} for sr in issues],
            "fix_actions": fix_actions,
            "questions_before_fix": questions_before_fix,
            "questions_after_fix": [dict(q) for q in current_questions],
        })

        print(f"\n  修复完成，重新审核...")

    return current_questions, review, revision_rounds


# ── Main ──────────────────────────────────────────────────────


async def run_composition(
    gateway,
    slot_templates: dict,
    experience_cards: dict,
    user_requirements: str,
    slot_ids: list = None,
    max_bp_revisions: int = 1,
    max_fix_rounds: int = 2,
    gate_config: dict = None,
) -> dict:
    """Run the full composition pipeline."""
    if slot_ids:
        templates = {k: v for k, v in slot_templates.items() if k in slot_ids}
    else:
        templates = slot_templates

    if not templates:
        print("No templates to compose from!")
        return {}

    # When specific slots are given, append slot-type info to requirements
    # to avoid mismatch (e.g. user_requirements says 选择题 but slot is 综合题)
    if slot_ids:
        slot_types = []
        for sid, tmpl in templates.items():
            q_type = tmpl.get("question_type", "")
            if q_type == "comprehensive" or (sid.startswith("Q") and sid[1:].isdigit() and int(sid[1:]) >= 43):
                slot_types.append(f"{sid}(综合应用题)")
            else:
                slot_types.append(f"{sid}(选择题)")
        type_hint = "、".join(slot_types)
        user_requirements = f"{user_requirements}。指定题位：{type_hint}。"

    total_start = time.monotonic()

    # Step 1: Compose
    blueprint = await compose_paper(gateway, templates, user_requirements)
    if not blueprint:
        return {"status": "error", "step": "compose"}

    # Step 1b: Skeleton check (code-level hard rules)
    from core_new.skeleton_checker import check_blueprint_skeleton
    skeleton_violations = check_blueprint_skeleton(blueprint)
    if skeleton_violations:
        print(f"  骨架检查: {len(skeleton_violations)} violations")
        for v in skeleton_violations:
            print(f"    [{v['slot_id']}] {v['rule']}: {v['detail']}")
    else:
        print("  骨架检查: pass")

    # Step 2: Review blueprint
    blueprint, blueprint_review = await review_blueprint(
        gateway, blueprint, templates, user_requirements, max_revisions=max_bp_revisions
    )
    if not blueprint:
        return {"status": "error", "step": "review_blueprint"}

    slot_blueprints = blueprint.get("slots", [])
    if not slot_blueprints:
        print("  ERROR: No slot blueprints generated")
        return {"status": "error", "step": "compose", "error": "empty slots"}

    # Step 2b: Knowledge/Slot Gate (optional)
    gate_config = gate_config or {}
    knowledge_gate_result = None
    if gate_config.get("enable_knowledge_gate"):
        knowledge_gate_result = await knowledge_slot_gate(
            gateway, blueprint, templates, user_requirements,
        )
        if knowledge_gate_result and knowledge_gate_result.get("decision") == "blocked":
            print("  Knowledge gate BLOCKED — returning to compose")
            return {
                "status": "error",
                "step": "knowledge_gate",
                "gate_result": knowledge_gate_result,
            }

    # Step 3: Generate questions (parallel, routed by question_type)
    enable_stem_gate = gate_config.get("enable_stem_gate", False)
    initial_questions = await generate_questions(
        gateway, slot_blueprints, experience_cards,
        enable_stem_gate=enable_stem_gate,
    )

    # Step 4-5: Review + fix loop
    final_questions, final_review, revision_rounds = await review_and_fix(
        gateway, blueprint, initial_questions, templates, experience_cards, max_rounds=max_fix_rounds
    )

    total_time = time.monotonic() - total_start

    # Save results with full observability
    output = {
        "user_requirements": user_requirements,
        "paper_blueprint": blueprint,
        "blueprint_review": blueprint_review,
        "skeleton_violations": skeleton_violations,
        "knowledge_gate_result": knowledge_gate_result,
        "initial_questions": initial_questions,
        "revision_rounds": revision_rounds,
        "final_questions": final_questions,
        "final_review": final_review,
        "total_time_s": round(total_time, 1),
    }

    os.makedirs("docs", exist_ok=True)
    output_path = "docs/slot_composition_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n结果已保存到: {output_path}")

    # Step 5: Format & Export
    try:
        from core_new.agents.paper_formatter import PaperFormatterAgent

        formatter = PaperFormatterAgent(gateway=gateway)
        md = await formatter.format(final_questions, blueprint, final_review)
        md_path = Path("docs/exam_paper_clean.md")
        md_path.write_text(md, encoding="utf-8")
        print(f"排版完成: {md_path}")
    except Exception as exc:
        print(f"排版步骤跳过: {exc}")

    return output


async def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--slots", nargs="+", help="Specific slots (e.g., Q12 Q13)")
    parser.add_argument("--requirements", default="出一套标准难度的408模拟卷（计算机组成原理选择题部分），难度分布均匀，覆盖主要知识点")
    parser.add_argument("--max-bp-revisions", type=int, default=1, help="Max blueprint revision rounds")
    parser.add_argument("--max-fix-rounds", type=int, default=2, help="Max question fix rounds")
    parser.add_argument("--enable-knowledge-gate", action="store_true", default=False,
                        help="Enable Gate 1: knowledge/slot review before generation")
    parser.add_argument("--enable-stem-gate", action="store_true", default=False,
                        help="Enable Gate 2: stem review before options/solver")
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
    gate_config = {
        "enable_knowledge_gate": args.enable_knowledge_gate,
        "enable_stem_gate": args.enable_stem_gate,
    }
    await run_composition(
        gateway,
        slot_templates=templates,
        experience_cards=exp_cards,
        user_requirements=args.requirements,
        slot_ids=args.slots,
        max_bp_revisions=args.max_bp_revisions,
        max_fix_rounds=args.max_fix_rounds,
        gate_config=gate_config,
    )


if __name__ == "__main__":
    asyncio.run(main())
