"""Quick test: run SCQuestionAgent only (no review) with local model for Q12 and Q18."""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core_new.agents.single_choice_team import SCQuestionAgent
from core_new.blackboard import Blackboard
from core_new.provider_router import get_routed_gateway


async def test_one(slot_id: str, assembled_doc_path: str, outline_entry: dict):
    with open(assembled_doc_path, encoding="utf-8") as f:
        assembled_doc = f.read()

    print(f"\n{'='*60}")
    print(f"Testing SCQuestionAgent for {slot_id}")
    print(f"  doc size: {len(assembled_doc)} chars")
    print(f"  outline: {outline_entry.get('primary_target_name', '?')}, d={outline_entry.get('difficulty_level', '?')}, mode={outline_entry.get('examination_mode', '?')}")
    print(f"{'='*60}\n")

    bb = Blackboard(
        task_id=f"test_{slot_id}",
        task_type="test_sc_question",
        initial_state={
            "outline_entry": outline_entry,
            "outline_entry_md": "",
            "slot_contract": {},
            "assembled_experience_doc": assembled_doc,
        },
    )

    gw = get_routed_gateway("review")  # review routes to local Qwen
    agent = SCQuestionAgent(gw, experience_card_path="")

    t0 = time.monotonic()
    result = await agent.execute(bb)
    elapsed = time.monotonic() - t0

    if not result or result.get("error"):
        print(f"  ERROR: {result.get('error', 'empty result')}")
        return

    print(f"  elapsed: {elapsed:.1f}s")
    print(f"  stem: {str(result.get('stem', ''))[:200]}...")
    print(f"  options:")
    for letter in "ABCD":
        print(f"    {letter}: {str(result.get(f'option_{letter}', ''))[:120]}")
    print(f"  correct_answer: {result.get('correct_answer', '?')}")
    print(f"  code_verified: {result.get('code_verified', '?')}")
    print(f"  verified_answer: {result.get('verified_answer', '?')}")
    print(f"  adjustment_summary: {result.get('adjustment_summary', '?')}")
    print(f"  difficulty_self: {result.get('difficulty_self_assessment', '?')}")
    print(f"  knowledge_points: {result.get('knowledge_points', '?')}")
    print(f"  selected_knowledge_rationale: {result.get('selected_knowledge_rationale', '?')}")
    print(f"  distractor intents:")
    for letter in "ABCD":
        di = result.get(f'distractor_intent_{letter}', '')
        if di:
            print(f"    {letter}: {str(di)[:100]}")
    print(f"  _attempts: {result.get('_attempts', '?')}")
    print(f"  _elapsed_s: {result.get('_elapsed_s', '?')}")


async def main():
    # Q12: 概念辨析型, difficulty=2
    q12_entry = {
        "slot_id": "Q12",
        "primary_target_name": "计算机性能指标（如CPI、主频、MIPS关系）",
        "target_family": "CO-1 > 计算机系统概述",
        "difficulty_level": 2,
        "k_target": "K1概念型",
        "examination_mode": "概念辨析型——四选一定义",
    }

    # Q18: 计算型, difficulty=4
    q18_entry = {
        "slot_id": "Q18",
        "primary_target_name": "指令流水线的基本概念与性能计算",
        "target_family": "CO-5 > 中央处理器 > 指令流水线",
        "difficulty_level": 4,
        "k_target": "K2计算型",
        "examination_mode": "计算型",
    }

    await test_one("Q12", "docs/assembled_Q12.md", q12_entry)
    await test_one("Q18", "docs/assembled_Q18.md", q18_entry)


if __name__ == "__main__":
    asyncio.run(main())
