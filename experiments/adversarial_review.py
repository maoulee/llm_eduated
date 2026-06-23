"""Adversarial review: Qwen (local) reviews both Qwen's and GLM 5.1's generated questions."""
import asyncio
import json
import os
import time

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core_new.llm_gateway import LLMGateway
from core_new.prompts.single_choice_prompts import SC_REVIEWER_PROMPT


def parse_question(raw) -> dict:
    """Parse markdown question output into structured fields."""
    fields = {}
    if not raw:
        return fields
    current_key = None
    current_val = []

    for line in raw.split("\n"):
        stripped = line.strip()
        m = __import__("re").match(r"-\s+\*\*(.+?)\*\*:\s*(.*)", stripped)
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
    # Re-generate both questions first, then review
    from test_model_compare import main as gen_main
    import core_new.llm_gateway as gw_mod
    from core_new.slot_prompts import SLOT_QUESTION_WRITER

    # Load Q14 template
    with open("data/slot_templates.json", encoding="utf-8") as f:
        templates = json.load(f)["templates"]
    q14_tmpl = templates.get("Q14")

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

    ref_lines = []
    for obs in q14_obs:
        ref_lines.append(
            f"- {obs.get('year')}年: {obs.get('primary_target_name')} "
            f"({obs.get('target_family')})"
        )
    ref_questions = "\n".join(ref_lines)

    gen_prompt = SLOT_QUESTION_WRITER.format(
        slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
        experience_card_md=exp_card,
        reference_questions=ref_questions,
        slot_id="Q14",
    )

    gen_messages = [{"role": "user", "content": gen_prompt}]

    print("=" * 60)
    print("Step 1: Generating questions with both models")
    print("=" * 60)

    qwen_gw = LLMGateway("api_vllm")
    glm_gw = LLMGateway("glm5.1")

    t0 = time.monotonic()
    qwen_q, glm_q = await asyncio.gather(
        qwen_gw.generate_text(gen_messages, enable_thinking=False),
        glm_gw.generate_text(gen_messages, enable_thinking=False),
    )
    elapsed = time.monotonic() - t0
    print(f"Generation done in {elapsed:.1f}s\n")

    if not qwen_q.ok or not glm_q.ok:
        print(f"Qwen: {'OK' if qwen_q.ok else qwen_q.error_message}")
        print(f"GLM: {'OK' if glm_q.ok else glm_q.error_message}")
        return

    # Parse both questions
    qwen_parsed = parse_question(qwen_q.content)
    glm_parsed = parse_question(glm_q.content)

    # Build review prompts
    def build_review_prompt(parsed: dict, label: str) -> list:
        stem = parsed.get("stem", "?")
        opt_a = parsed.get("option_A", "?")
        opt_b = parsed.get("option_B", "?")
        opt_c = parsed.get("option_C", "?")
        opt_d = parsed.get("option_D", "?")
        solution = (
            f"正确答案: {parsed.get('correct_answer', '?')}\n"
            f"解析: {parsed.get('explanation', '?')}\n"
            f"解题步骤: {parsed.get('solution_steps', '?')}\n"
            f"陷阱说明: {parsed.get('trap_description', '?')}"
        )

        prompt = SC_REVIEWER_PROMPT.format(
            stem=stem,
            option_A=opt_a,
            option_B=opt_b,
            option_C=opt_c,
            option_D=opt_d,
            solution_md=solution,
            slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
        )
        return [{"role": "user", "content": prompt}]

    qwen_review_msgs = build_review_prompt(qwen_parsed, "Qwen")
    glm_review_msgs = build_review_prompt(glm_parsed, "GLM 5.1")

    print("=" * 60)
    print("Step 2: Qwen adversarial review on both questions")
    print("=" * 60)

    t0 = time.monotonic()
    review_qwen_q, review_glm_q = await asyncio.gather(
        qwen_gw.generate_text(qwen_review_msgs, enable_thinking=False),
        qwen_gw.generate_text(glm_review_msgs, enable_thinking=False),
    )
    elapsed = time.monotonic() - t0
    print(f"Review done in {elapsed:.1f}s\n")

    # Print questions + reviews
    print("=" * 60)
    print("【题目1: Qwen 生成】")
    print("=" * 60)
    print(f"题干: {qwen_parsed.get('stem', '?')[:200]}")
    print(f"A: {qwen_parsed.get('option_A', '?')}")
    print(f"B: {qwen_parsed.get('option_B', '?')}")
    print(f"C: {qwen_parsed.get('option_C', '?')}")
    print(f"D: {qwen_parsed.get('option_D', '?')}")
    print(f"答案: {qwen_parsed.get('correct_answer', '?')}")

    print("\n" + "=" * 60)
    print("【Qwen 对 Qwen题目的对抗审查】")
    print("=" * 60)
    if review_qwen_q.ok:
        print(review_qwen_q.content)
    else:
        print(f"ERROR: {review_qwen_q.error_message}")

    print("\n\n" + "=" * 60)
    print("【题目2: GLM 5.1 生成】")
    print("=" * 60)
    print(f"题干: {glm_parsed.get('stem', '?')[:200]}")
    print(f"A: {glm_parsed.get('option_A', '?')}")
    print(f"B: {glm_parsed.get('option_B', '?')}")
    print(f"C: {glm_parsed.get('option_C', '?')}")
    print(f"D: {glm_parsed.get('option_D', '?')}")
    print(f"答案: {glm_parsed.get('correct_answer', '?')}")

    print("\n" + "=" * 60)
    print("【Qwen 对 GLM 5.1题目的对抗审查】")
    print("=" * 60)
    if review_glm_q.ok:
        print(review_glm_q.content)
    else:
        print(f"ERROR: {review_glm_q.error_message}")


if __name__ == "__main__":
    asyncio.run(main())
