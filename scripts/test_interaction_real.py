"""End-to-end interaction layer test — simulates user conversations.

Tests three scenarios through the interactive orchestrator:
  1. 单知识点出题 (single knowledge point)
  2. 指定知识点+详细参数 (specific params: difficulty, question type, count)
  3. 组卷流程 (full paper compose)

Uses local Qwen for both interaction and pipeline.
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interact.orchestrator import InteractiveOrchestrator
from core_new.llm_gateway import get_gateway


OUTPUT_DIR = "docs/test_output/interaction_e2e"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


async def run_conversation(
    orch: InteractiveOrchestrator,
    session_id: str,
    messages: list[str],
    label: str,
) -> list[str]:
    """Run a multi-turn conversation and print each turn."""
    responses = []
    for i, msg in enumerate(messages):
        print(f"\n  [Turn {i+1}] User: {msg}")
        t0 = time.time()
        resp = await orch.handle_input(session_id, msg)
        elapsed = time.time() - t0
        print(f"    Response ({elapsed:.1f}s):")
        for line in resp[:600].splitlines():
            print(f"      {line}")
        if len(resp) > 600:
            print(f"      ... ({len(resp)} chars total)")
        responses.append(resp)

        session = orch.session_manager.get_or_create(session_id)
        print(f"    State: {session.state.value}")
        if session.mode:
            print(f"    Mode: {session.mode}")
        if session.collected_params:
            p = json.dumps(session.collected_params, ensure_ascii=False, indent=2)
            print(f"    Params: {p}")

        # Save response
        out_path = os.path.join(OUTPUT_DIR, f"{label}_turn{i+1}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"State: {session.state.value}\n")
            if session.mode:
                f.write(f"Mode: {session.mode}\n")
            f.write(f"\nResponse:\n{resp}\n")

        if session.state.value in ("complete", "error"):
            break

    return responses


async def test_scenario_1(orch: InteractiveOrchestrator):
    """Scenario 1: 单知识点出题 — 用户只给知识点和基本要求."""
    _header("Scenario 1: 单知识点出题 (进程调度算法)")
    await run_conversation(
        orch,
        session_id="test-s1-schedule",
        messages=[
            "出1道关于进程调度算法的选择题，中等难度",
            "确认",
        ],
        label="s1_schedule",
    )


async def test_scenario_2(orch: InteractiveOrchestrator):
    """Scenario 2: 指定知识点+详细参数 — 综合应用题."""
    _header("Scenario 2: 指定知识点+参数 (AVL树旋转, 综合题, 高难度)")
    await run_conversation(
        orch,
        session_id="test-s2-avl",
        messages=[
            "出一道数据结构的综合应用题，关于平衡二叉树AVL的插入旋转，难度较高",
            "确认",
        ],
        label="s2_avl",
    )


async def test_scenario_3(orch: InteractiveOrchestrator):
    """Scenario 3: 组卷流程 — 完整组卷."""
    _header("Scenario 3: 组卷流程 (计算机网络)")
    await run_conversation(
        orch,
        session_id="test-s3-compose",
        messages=[
            "帮我组一套计算机网络的试卷，5道选择题，2道综合题，难度中等",
            "确认",
        ],
        label="s3_compose",
    )


async def main():
    _header("Interaction Layer E2E Test — Local Qwen")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    gateway = get_gateway("api_vllm")
    orch = InteractiveOrchestrator(gateway, model_routing={"_default": "api_vllm"})

    # Scenario selection via command line args
    scenarios = sys.argv[1:] if len(sys.argv) > 1 else ["1"]

    if "1" in scenarios:
        await test_scenario_1(orch)
    if "2" in scenarios:
        await test_scenario_2(orch)
    if "3" in scenarios:
        await test_scenario_3(orch)
    if "all" in scenarios:
        await test_scenario_1(orch)
        await test_scenario_2(orch)
        await test_scenario_3(orch)

    _header("Tests complete")
    workspace_base = "docs/workspace"
    if os.path.isdir(workspace_base):
        dirs = sorted(os.listdir(workspace_base))
        recent = dirs[-3:] if len(dirs) > 3 else dirs
        print(f"  Recent workspaces: {recent}")


if __name__ == "__main__":
    asyncio.run(main())
