"""Run slot-template driven paper composition and generation.

Pipeline:
  1. PaperComposer → PaperBlueprint (SlotBlueprint per position)
  2. BlueprintReviewer → review blueprint (revise if needed)
  3. Generate questions per slot (routed by question_type):
     - single_choice → SingleChoicePipeline (Draft→Options→CodeAct→Format→Review)
     - comprehensive → SubjectivePipeline (Sketch→Params→Draft→CodeAct→Format→Rubric→Review)
     - fallback → legacy QuestionWriterAgent
  4. PaperReviewer → whole-paper review with issue categorization
  5. Fix loop: answer_error → QuestionFixer, content_mismatch → regenerate
  6. Repeat review until pass or max iterations

Usage:
    GLM_API_KEY=xxx .venv/bin/python run_slot_composition.py
    GLM_API_KEY=xxx .venv/bin/python run_slot_composition.py --slots Q12 Q13 Q14
    GLM_API_KEY=xxx .venv/bin/python run_slot_composition.py --max-fix-rounds 2
    GLM_API_KEY=xxx .venv/bin/python run_slot_composition.py --pipeline new
"""

import asyncio
import json
import os
import re
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
from core_new.agents.subjective_team import SubjectivePipeline
from core_new.agents.hybrid_subjective_team import HybridSubjectivePipeline
from core_new.agents.codeact_solver import CodeActSolverAgent
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


# ── Step 3: Generate Questions (parallel) ─────────────────────


async def generate_questions(gateway, slot_blueprints, experience_cards, pipeline_mode="new") -> list:
    """Step 3: Generate questions per slot, routed by question_type.

    pipeline_mode:
      "new"    — single_choice uses legacy QuestionWriter (proven quality),
                 comprehensive uses new SubjectivePipeline (prevents timeout)
      "legacy" — use original QuestionWriterAgent for all slots
    """
    print("\n" + "=" * 60)
    print(f"Step 3: 出题 ({len(slot_blueprints)}题，并行) [pipeline={pipeline_mode}]")
    print("=" * 60)

    # New mode: legacy for single_choice, hybrid pipeline for comprehensive
    subj_pipeline = HybridSubjectivePipeline(max_revision_rounds=1) if pipeline_mode == "new" else None
    legacy_writer = QuestionWriterAgent(gateway)

    def _is_comprehensive(sb):
        """Determine if a slot is comprehensive/subjective."""
        q_type = sb.get("question_type", "")
        if q_type == "comprehensive":
            return True
        # Blueprint may not set question_type — check slot_id pattern
        slot_id = sb.get("slot_id", "")
        if slot_id.startswith("Q") and int(slot_id[1:]) >= 43:
            return True
        # Check sub_questions count
        sub_q = sb.get("sub_questions", "0")
        try:
            if int(sub_q) >= 2:
                return True
        except (ValueError, TypeError):
            pass
        return False

    async def _generate_one(sb):
        slot_id = sb.get("slot_id", "Q12")
        exp_card = experience_cards.get(slot_id, "")
        is_comp = _is_comprehensive(sb)

        if pipeline_mode == "new" and is_comp:
            return await _generate_subjective(gateway, sb, slot_id, exp_card, subj_pipeline)
        else:
            return await _generate_legacy(legacy_writer, sb, slot_id, exp_card, gateway=gateway)

    tasks = [_generate_one(sb) for sb in slot_blueprints]
    questions = await asyncio.gather(*tasks)
    return list(questions)


async def _generate_subjective(gateway, sb, slot_id, exp_card, subj_pipeline):
    """Generate a comprehensive/subjective question via HybridSubjectivePipeline.

    Designer → FileCodeSolver → Formatter → Rubric → IntentReviewer.
    On failure, falls back to legacy QuestionWriterAgent.
    """
    print(f"  [{slot_id}] HybridSubjectivePipeline (FileCodeSolver)...")
    t0 = time.monotonic()

    try:
        result = await asyncio.wait_for(
            subj_pipeline.run(sb, exp_card, gateway),
            timeout=600,
        )
        elapsed = time.monotonic() - t0

        q_data = dict(result.final_question or {})
        q_data["review"] = result.review or {}
        q_data["rubric"] = result.rubric or {}
        q_data["formatted_solution"] = result.formatted_solution or {}
        q_data["generation_time_s"] = result.generation_time_s
        q_data["slot_id"] = slot_id
        q_data["pipeline_type"] = "hybrid_v2"
        q_data["correct_answer"] = q_data.get("answer", "")

        answer = str(q_data.get("answer", "?"))[:80]
        execs = q_data.get("python_exec_count", 0)
        code_files = q_data.get("code_files", [])
        review_score = result.review.get("score", "?")
        print(f"  [{slot_id}] Hybrid done ({elapsed:.1f}s): "
              f"answer={answer} python_execs={execs} "
              f"files={len(code_files)} review={review_score}/100")
        return q_data

    except (asyncio.TimeoutError, Exception) as e:
        elapsed = time.monotonic() - t0
        reason = "timeout" if isinstance(e, asyncio.TimeoutError) else str(e)[:100]
        print(f"  [{slot_id}] Hybrid failed ({elapsed:.1f}s): {reason}")
        print(f"  [{slot_id}] Falling back to legacy writer...")

    # Fallback: legacy writer
    try:
        legacy_writer = QuestionWriterAgent(gateway)
        qbb = Blackboard(
            task_id=f"write_{slot_id}_fallback",
            task_type="slot_composition",
            initial_state={
                "current_blueprint": sb,
                "reference_questions": exp_card,
            },
        )
        record = await asyncio.wait_for(legacy_writer.execute(qbb), timeout=120)
        elapsed = time.monotonic() - t0

        if record.error:
            raise RuntimeError(record.error)

        q_data = qbb.get("generated_question") or {}
        q_data["slot_id"] = slot_id
        q_data["generation_time_s"] = round(elapsed, 1)
        q_data["pipeline_type"] = "legacy_fallback"

        answer = q_data.get("correct_answer", "?")
        stem_preview = q_data.get("stem", "")[:80]
        print(f"  [{slot_id}] Legacy fallback done ({elapsed:.1f}s): answer={answer} — {stem_preview}...")
        return q_data

    except Exception as e2:
        elapsed = time.monotonic() - t0
        print(f"  [{slot_id}] Both pipelines failed ({elapsed:.1f}s): {e2}")
        return {"slot_id": slot_id, "status": "error", "error": str(e2)}


async def _generate_legacy(writer, sb, slot_id, exp_card, gateway=None):
    """Generate a question using the legacy QuestionWriterAgent, then verify with CodeActSolver."""
    print(f"  [{slot_id}] Generating via legacy writer...")
    t0 = time.monotonic()

    qbb = Blackboard(
        task_id=f"write_{slot_id}",
        task_type="slot_composition",
        initial_state={
            "current_blueprint": sb,
            "reference_questions": exp_card,
        },
    )

    record = await writer.execute(qbb)

    # Retry on network errors
    for retry in range(2):
        if not record.error:
            break
        is_network = "connection" in str(record.error).lower() or "network" in str(record.error).lower()
        if is_network:
            print(f"  [{slot_id}] Network error (attempt {retry + 1}), retrying in 15s...")
            await asyncio.sleep(15)
            record = await writer.execute(qbb)
        else:
            break

    gen_elapsed = time.monotonic() - t0

    if record.error:
        print(f"  [{slot_id}] ERROR: {record.error[:200]}")
        return {"slot_id": slot_id, "status": "error", "error": record.error}

    q_data = qbb.get("generated_question") or {}
    q_data["slot_id"] = slot_id
    q_data["generation_time_s"] = round(gen_elapsed, 1)
    q_data["pipeline_type"] = "legacy_verified"
    q_data["_blueprint"] = sb
    q_data["_experience_card"] = exp_card

    legacy_answer = q_data.get("correct_answer", "?")
    stem_preview = q_data.get("stem", "")[:80]
    print(f"  [{slot_id}] Generated ({gen_elapsed:.1f}s): answer={legacy_answer} — {stem_preview}...")

    # Verify answer with CodeActSolver for calculation-heavy questions
    q_type = sb.get("question_type", "single_choice")
    calc_load = sb.get("difficulty_profile", {}).get("calculation_load", 0)

    if gateway and calc_load >= 1 and q_type == "single_choice":
        verified = await _verify_answer_with_codeact(gateway, q_data, slot_id)
        q_data["codeact_verified"] = verified
    elif gateway and q_type == "comprehensive":
        verified = await _verify_answer_with_codeact(gateway, q_data, slot_id)
        q_data["codeact_verified"] = verified
    else:
        verified = {}

    # If solver computed a different answer, fix immediately
    if verified.get("match") is False and verified.get("solver_confidence") in ("high", "medium"):
        q_data = await _fix_answer_mismatch(gateway, q_data, verified, slot_id)

    total_elapsed = time.monotonic() - t0
    q_data["generation_time_s"] = round(total_elapsed, 1)
    return q_data


async def _verify_answer_with_codeact(gateway, q_data, slot_id):
    """Use FileCodeSolverAgent to independently verify the generated answer.

    Writes Python scripts to disk, runs them, and compares computed result
    with the marked answer. More reliable than inline CodeActSolver.
    """
    from core_new.agents.file_code_solver import FileCodeSolverAgent

    solver = FileCodeSolverAgent(gateway, max_tokens=2048, max_steps=3)
    stem = q_data.get("stem", "")
    if not stem:
        return {"verified": False, "reason": "no stem"}

    q_type = q_data.get("question_type",
                        q_data.get("pipeline_type", "").replace("legacy", "").replace("verified", "").strip() or "single_choice")

    # Build full question text with options for the solver
    question_text = stem
    options = {}
    if q_type == "single_choice":
        for letter in ["A", "B", "C", "D"]:
            opt = q_data.get(f"option_{letter}", "")
            if opt:
                options[letter] = opt
                question_text += f"\n选项{letter}: {opt}"
        question_text += "\n\n请编写Python脚本计算正确答案，并在最后输出: 最终答案: X (X为A/B/C/D之一)"

    print(f"  [{slot_id}] FileCodeSolver verifying...")
    t0 = time.monotonic()
    try:
        result = await solver.solve(
            question_draft=question_text,
            options=options,
            question_type=q_type,
            slot_id=f"{slot_id}_verify",
        )
        verify_elapsed = time.monotonic() - t0

        # Extract answer from solver output
        solver_answer = "?"
        last_output = result.get_last_output()

        # Try to find letter answer in output
        m = re.search(r'(?:最终答案|答案|选项|正确选项|answer|option)\s*[是为:：]\s*([A-D])', last_output, re.IGNORECASE)
        if not m:
            m = re.search(r'\b([A-D])\s*[是为]\s*正确', last_output)
        if not m:
            m = re.search(r'选择\s*([A-D])', last_output)
        if m:
            solver_answer = m.group(1).upper()
        elif result.computed_results:
            # Try matching computed value with option text
            for key, val in result.computed_results.items():
                val_str = str(val).strip()
                for letter, opt_text in options.items():
                    if val_str in opt_text:
                        solver_answer = letter
                        break
                if solver_answer != "?":
                    break

        confidence = "high" if result.python_exec_count > 0 and not result.error else "low"

        legacy_answer = q_data.get("correct_answer", "?")
        match = solver_answer != "?" and solver_answer == legacy_answer.upper()

        print(f"  [{slot_id}] Verify ({verify_elapsed:.1f}s): "
              f"legacy={legacy_answer} solver={solver_answer} "
              f"{'MATCH' if match else 'MISMATCH'} "
              f"(confidence={confidence}, python_execs={result.python_exec_count})")

        return {
            "verified": True,
            "match": match,
            "solver_answer": solver_answer,
            "solver_raw_output": last_output[:1000],
            "solver_confidence": confidence,
            "solver_evidence": last_output[:500],
            "python_exec_count": result.python_exec_count,
            "code_files": result.code_files,
            "verify_time_s": round(verify_elapsed, 1),
        }
    except Exception as e:
        verify_elapsed = time.monotonic() - t0
        print(f"  [{slot_id}] Verify failed ({verify_elapsed:.1f}s): {e}")
        return {"verified": False, "reason": str(e)}


async def _fix_answer_mismatch(gateway, q_data, verified, slot_id):
    """Fix question when verification shows answer mismatch.

    Strategy:
    - Answer error (solver computed a value ≠ marked answer): fix options only
    - Question error (solver couldn't compute): regenerate the question
    """
    solver_answer = verified.get("solver_answer", "?")
    solver_raw = verified.get("solver_raw_output", "")
    solver_evidence = verified.get("solver_evidence", "")
    legacy_answer = q_data.get("correct_answer", "?")
    solver_confidence = verified.get("solver_confidence", "low")
    python_execs = verified.get("python_exec_count", 0)

    print(f"  [{slot_id}] MISMATCH detected: legacy={legacy_answer}, solver={solver_answer}")

    # Determine fix strategy
    solver_computed = solver_answer != "?" and python_execs > 0 and solver_confidence == "high"
    q_data.setdefault("codeact_verified", {})
    q_data["codeact_verified"]["fix_attempted"] = True

    if solver_computed:
        # ── Strategy A: Answer error → fix options only ──
        print(f"  [{slot_id}] Strategy: fix options (solver computed {solver_answer})")
        return await _fix_options_only(gateway, q_data, verified, slot_id)
    else:
        # ── Strategy B: Question error → regenerate ──
        print(f"  [{slot_id}] Strategy: regenerate question (solver could not compute)")
        return await _regenerate_question(gateway, q_data, verified, slot_id)


async def _fix_options_only(gateway, q_data, verified, slot_id):
    """Fix options to match solver's computed answer. Keep question stem unchanged."""
    solver_answer = verified.get("solver_answer", "?")
    solver_raw = verified.get("solver_raw_output", "")
    legacy_answer = q_data.get("correct_answer", "?")

    fix_instruction = (
        f"Python代码验证计算得出的正确答案为: {solver_answer}\n"
        f"当前题目标记的正确答案为: {legacy_answer}\n"
        f"代码执行的完整输出:\n{solver_raw[:800]}\n\n"
        f"修正要求:\n"
        f"1. 保持题干(stem)完全不变\n"
        f"2. 如果正确答案{solver_answer}已在选项中，只需更新 correct_answer 为 {solver_answer}\n"
        f"3. 如果正确答案不在选项中，将当前标记为正确的选项替换为正确答案对应的值，然后更新 correct_answer\n"
        f"4. 保持题目考点和难度不变，只修正数值"
    )

    fix_bb = Blackboard(
        task_id=f"fix_opts_{slot_id}",
        task_type="slot_composition",
        initial_state={
            "question_to_fix": q_data,
            "fix_instructions": fix_instruction,
        },
    )

    try:
        fixer = QuestionFixerAgent(gateway)
        record = await fixer.execute(fix_bb)
        if record.error:
            print(f"  [{slot_id}] Option fix failed: {record.error}")
            q_data["codeact_verified"]["fix_error"] = record.error
            return q_data

        fixed = fix_bb.get("fixed_question") or {}
        fixed["slot_id"] = slot_id
        fixed["pipeline_type"] = q_data.get("pipeline_type", "legacy_verified")
        fixed["codeact_verified"] = verified
        fixed["codeact_verified"]["fix_status"] = "options_fixed"
        fixed["correct_answer"] = fixed.get("correct_answer", solver_answer)

        # Re-verify
        re_verified = await _verify_answer_with_codeact(gateway, fixed, slot_id)
        fixed["codeact_verified_post_fix"] = re_verified

        new_answer = fixed.get("correct_answer", "?")
        re_match = re_verified.get("match", False)
        print(f"  [{slot_id}] Options fixed: answer={new_answer} re-verify={'MATCH' if re_match else 'STILL MISMATCH'}")

        return fixed

    except Exception as e:
        print(f"  [{slot_id}] Option fix exception: {e}")
        q_data["codeact_verified"]["fix_error"] = str(e)
        return q_data


async def _regenerate_question(gateway, q_data, verified, slot_id):
    """Regenerate the question when solver couldn't compute (question parameters may be wrong)."""
    from core_new.agents.slot_agents import QuestionWriterAgent

    # Get the original blueprint
    sb = q_data.get("_blueprint", {})
    if not sb:
        print(f"  [{slot_id}] No blueprint available, falling back to option fix")
        return await _fix_options_only(gateway, q_data, verified, slot_id)

    exp_card = q_data.get("_experience_card", "")

    fix_instruction = (
        f"原始题目经代码验证无法得到一致结果，可能是题目参数设计有误。\n"
        f"验证器输出: {verified.get('solver_evidence', '')[:300]}\n"
        f"请重新设计该题目，确保所有参数和数值正确、可计算。"
    )

    print(f"  [{slot_id}] Regenerating question...")
    qbb = Blackboard(
        task_id=f"regen_{slot_id}",
        task_type="slot_composition",
        initial_state={
            "current_blueprint": sb,
            "reference_questions": exp_card,
            "regeneration_hint": fix_instruction,
        },
    )

    try:
        writer = QuestionWriterAgent(gateway)
        record = await writer.execute(qbb)
        if record.error:
            print(f"  [{slot_id}] Regeneration failed: {record.error}")
            q_data["codeact_verified"]["fix_error"] = record.error
            return q_data

        regen = qbb.get("generated_question") or {}
        regen["slot_id"] = slot_id
        regen["pipeline_type"] = q_data.get("pipeline_type", "legacy_verified")
        regen["codeact_verified"] = verified
        regen["codeact_verified"]["fix_status"] = "regenerated"

        # Verify the regenerated question
        re_verified = await _verify_answer_with_codeact(gateway, regen, slot_id)
        regen["codeact_verified_post_fix"] = re_verified

        new_answer = regen.get("correct_answer", "?")
        re_match = re_verified.get("match", False)
        print(f"  [{slot_id}] Regenerated: answer={new_answer} re-verify={'MATCH' if re_match else 'STILL MISMATCH'}")

        return regen

    except Exception as e:
        print(f"  [{slot_id}] Regeneration exception: {e}")
        q_data["codeact_verified"]["fix_error"] = str(e)
        return q_data


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
                fixed["revision_type"] = "answer_fix"
                fixed["fix_instruction"] = instruction
                fixed["revision_round"] = round_num + 1
                print(f"    [{slot_id}] Fixed: answer={fixed.get('correct_answer','?')}")
                return q_idx, fixed
            else:  # regen
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
                regen["revision_type"] = "regenerate"
                regen["regenerate_reason"] = instruction
                regen["revision_round"] = round_num + 1
                print(f"    [{slot_id}] Regenerated: answer={regen.get('correct_answer','?')}")
                return q_idx, regen

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
    pipeline_mode: str = "new",
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

    # Step 3: Generate questions (parallel, routed by question_type)
    initial_questions = await generate_questions(gateway, slot_blueprints, experience_cards, pipeline_mode=pipeline_mode)

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

    return output


async def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--slots", nargs="+", help="Specific slots (e.g., Q12 Q13)")
    parser.add_argument("--requirements", default="出一套标准难度的408模拟卷（计算机组成原理选择题部分），难度分布均匀，覆盖主要知识点")
    parser.add_argument("--max-bp-revisions", type=int, default=1, help="Max blueprint revision rounds")
    parser.add_argument("--max-fix-rounds", type=int, default=2, help="Max question fix rounds")
    parser.add_argument("--pipeline", default="new", choices=["new", "legacy"], help="Pipeline mode: new (legacy for SC + SubjectivePipeline for comprehensive) or legacy (QuestionWriter for all)")
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
        pipeline_mode=args.pipeline,
    )


if __name__ == "__main__":
    asyncio.run(main())
