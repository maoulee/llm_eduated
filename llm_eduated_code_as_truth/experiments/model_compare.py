"""Quick comparison: Qwen (local) vs GLM 5.1 (remote) question generation for Q14."""
import asyncio
import json
import os
import time

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core_new.llm_gateway import LLMGateway
from core_new.slot_prompts import SLOT_QUESTION_WRITER


async def main():
    # Load Q14 template
    with open("data/slot_templates.json", encoding="utf-8") as f:
        templates = json.load(f)["templates"]
    q14_tmpl = templates.get("Q14")
    if not q14_tmpl:
        print("Q14 template not found")
        return

    # Load Q14 experience card
    with open("data/slot_experiences/Q14_experience.md", encoding="utf-8") as f:
        exp_card = f.read()

    # Load a few reference observations for Q14
    with open("data/slot_observations.json", encoding="utf-8") as f:
        all_obs = json.load(f)["observations"]
    q14_obs = [o for o in all_obs if o.get("slot_id") == "Q14"][:3]

    # Build a simple blueprint for Q14
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

    # Format reference questions summary
    ref_lines = []
    for obs in q14_obs:
        ref_lines.append(
            f"- {obs.get('year')}年: {obs.get('primary_target_name')} "
            f"({obs.get('target_family')})"
        )
    ref_questions = "\n".join(ref_lines)

    # Build prompt
    prompt = SLOT_QUESTION_WRITER.format(
        slot_blueprint_json=json.dumps(blueprint, ensure_ascii=False, indent=2),
        experience_card_md=exp_card,
        reference_questions=ref_questions,
        slot_id="Q14",
    )

    messages = [{"role": "user", "content": prompt}]

    # ── Generate with both models in parallel ──
    print("=" * 60)
    print("Generating Q14 question: Qwen (local) vs GLM 5.1 (remote)")
    print("=" * 60)

    qwen_gw = LLMGateway("api_vllm")
    glm_gw = LLMGateway("glm5.1")

    t0 = time.monotonic()
    qwen_result, glm_result = await asyncio.gather(
        qwen_gw.generate_text(messages, enable_thinking=False),
        glm_gw.generate_text(messages, enable_thinking=False),
    )
    elapsed = time.monotonic() - t0

    print(f"\nBoth completed in {elapsed:.1f}s\n")

    # ── Print results side by side ──
    print("=" * 60)
    print("【Qwen 本地模型输出】")
    print("=" * 60)
    if qwen_result.ok:
        print(qwen_result.content)
    else:
        print(f"ERROR: {qwen_result.error_message}")

    print("\n")
    print("=" * 60)
    print("【GLM 5.1 远程模型输出】")
    print("=" * 60)
    if glm_result.ok:
        print(glm_result.content)
    else:
        print(f"ERROR: {glm_result.error_message}")


if __name__ == "__main__":
    asyncio.run(main())
