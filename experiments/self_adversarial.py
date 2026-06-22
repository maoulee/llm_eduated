"""Qwen self-adversarial loop: generate → review → fix → review → ... until pass."""
import asyncio
import json
import os
import re
import time

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core_new.llm_gateway import LLMGateway
from core_new.prompts.single_choice_prompts import SC_REVIEWER_PROMPT
from core_new.slot_prompts import SLOT_QUESTION_WRITER, QUESTION_FIXER_PROMPT


def parse_md_fields(raw: str) -> dict:
    """Parse markdown '- **key**: value' fields."""
    if not raw:
        return {}
    fields = {}
    current_key = None
    current_val = []
    for line in raw.split("\n"):
        stripped = line.strip()
        m = re.match(r"-\s+\*\*(.+?)\*\*:\s*(.*)", stripped)
        if m:
            if current_key:
                fields[current_key] = "\n".join(current_val).strip()
            current_key = m.group(1).strip()
            current_val = [m.group(2).strip()]
        elif current_key and stripped:
            current_val.append(stripped)
    if current_key:
        fields[current_key] = "\n".join(current_val).strip()
    return fields


async def main():
    max_rounds = 5

    # Load Q14 blueprint
    with open("data/slot_templates.json", encoding="utf-8") as f:
        templates = json.load(f)["templates"]
    q14_tmpl = templates["Q14"]

    with open("data/slot_experiences/Q14_experience.md", encoding="utf-8") as f:
        exp_card = f.read()

    with open("data/slot_observations.json", encoding="utf-8") as f:
        all_obs = json.load(f)["observations"]
    q14_obs = [o for o in all_obs if o.get("slot_id") == "Q14"][:3]

    da = q14_tmpl.get("difficulty_anchor", {})
    blueprint = {
        "slot_id": "Q14",
        "section": "选择题",
        "question_type": "single_choice",
        "target_subject": "计算机组成原理",
        "target_family": "数据表示与运算",
        "primary_target_name": "IEEE 754浮点数表示",
        "target_depth": "mechanism",
        "primary_paper_role": "trap_diagnosis",
        "target_difficulty": 3,
        "target_K1": da.get("K1_mode", 3),
        "target_K2": da.get("K2_mode", 2),
        "target_K3": da.get("K3_mode", 2),
        "target_K4": da.get("K4_mode", 4),
        "target_K5": da.get("K5_mode", 1),
        "radar_shape_name": q14_tmpl.get("radar_shape", "K4陷阱型"),
        "option_style": "数字结果",
        "reasoning_shape": "elimination",
        "stem_length": "medium",
        "condition_count": 3,
        "distractor_strategy": "规则误用、边界遗漏、符号偏移混淆",
        "must_include": "IEEE 754 非规格化数/规格化数辨析, 至少一个反直觉陷阱",
        "must_avoid": "纯记忆题, 计算量过大的繁杂运算",
        "reference_experience": "2018, 2020, 2023",
    }

    ref_lines = [f"- {o.get('year')}年: {o.get('primary_target_name')}" for o in q14_obs]
    ref_questions = "\n".join(ref_lines)

    gw = LLMGateway("api_vllm")
    # Increase timeout for long prompts
    gw._provider.request_timeout = 600.0

    # ── Round 0: Generate initial question ──
    print("=" * 60)
    print("Round 0: Qwen generates initial question")
    print("=" * 60)

    gen_prompt = SLOT_QUESTION_WRITER.format(
        slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
        experience_card_md=exp_card,
        reference_questions=ref_questions,
        slot_id="Q14",
    )

    t0 = time.monotonic()
    result = await gw.generate_text([{"role": "user", "content": gen_prompt}], enable_thinking=False)
    current_question = result.content if result.ok else ""
    print(f"Generation: {time.monotonic()-t0:.1f}s")

    if not current_question:
        print("Generation failed!")
        return

    # ── Iterative review-fix loop ──
    for round_i in range(1, max_rounds + 1):
        print(f"\n{'='*60}")
        print(f"Round {round_i}: Qwen adversarial review")
        print(f"{'='*60}")

        q = parse_md_fields(current_question)
        stem = q.get("stem", "?")
        opt_a = q.get("option_A", "?")
        opt_b = q.get("option_B", "?")
        opt_c = q.get("option_C", "?")
        opt_d = q.get("option_D", "?")
        solution = (
            f"正确答案: {q.get('correct_answer', '?')}\n"
            f"解析: {q.get('explanation', '?')}\n"
            f"解题步骤: {q.get('solution_steps', '?')}\n"
            f"陷阱说明: {q.get('trap_description', '?')}"
        )

        review_prompt = SC_REVIEWER_PROMPT.format(
            stem=stem,
            option_A=opt_a,
            option_B=opt_b,
            option_C=opt_c,
            option_D=opt_d,
            solution_md=solution,
            slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
        )

        t0 = time.monotonic()
        review_result = await gw.generate_text(
            [{"role": "user", "content": review_prompt}], enable_thinking=False
        )
        review_text = review_result.content if review_result.ok else ""
        print(f"Review: {time.monotonic()-t0:.1f}s")

        if not review_text:
            print("Review failed!")
            break

        # Parse review
        rv = parse_md_fields(review_text)
        status = rv.get("status", "needs_fix")
        quality = rv.get("overall_quality", "?")
        comment = rv.get("comment", "")
        fix_detail = rv.get("fix_detail", "")

        print(f"\n  Status: {status} | Quality: {quality}/10")
        print(f"  Comment: {comment[:200]}")

        if "pass" in status.lower():
            print(f"\n{'='*60}")
            print(f"PASSED after {round_i} review rounds!")
            print(f"{'='*60}")
            print(f"\nFinal question:\n")
            print(current_question)
            print(f"\nFinal review:\n")
            print(review_text)
            return

        # ── Fix the question ──
        print(f"\n  Fix needed: {fix_detail[:200]}")
        print(f"\n  Fixing question...")

        fix_prompt = QUESTION_FIXER_PROMPT.format(
            question_json=current_question,
            fix_instructions=fix_detail,
            slot_id="Q14",
        )

        t0 = time.monotonic()
        fix_result = await gw.generate_text(
            [{"role": "user", "content": fix_prompt}], enable_thinking=False
        )
        if fix_result.ok and fix_result.content:
            current_question = fix_result.content
            print(f"  Fix: {time.monotonic()-t0:.1f}s")
        else:
            print(f"  Fix failed: {fix_result.error_message}")
            break

    print(f"\n{'='*60}")
    print(f"Did not pass after {max_rounds} rounds")
    print(f"{'='*60}")
    print(f"\nLast question:\n")
    print(current_question)
    print(f"\nLast review:\n")
    print(review_text if 'review_text' in dir() else "N/A")


if __name__ == "__main__":
    asyncio.run(main())
