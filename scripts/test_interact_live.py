"""Live interact agent test — simulates teacher conversation via scheduler.

Uses real LLM (local vLLM or remote GLM) to test the interact agent pipeline:
1. Teacher sends "出一套计算机组成原理期末卷"
2. Agent collects info, searches knowledge index, generates draft
3. Print the draft document
4. Teacher confirms → agent generates handoff yaml

Usage:
  python scripts/test_interact_live.py                    # default: api_vllm
  GLM_API_KEY=xxx python scripts/test_interact_live.py glm5.1  # remote GLM
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core_new.doc_pipeline.scheduler import DocScheduler
from core_new.llm_gateway import get_gateway


OUTPUT_DIR = Path("docs/output_interact_live_test")


def create_gateway(provider_name: str = "api_vllm") -> "LLMGateway":
    """Create a gateway for the given provider."""
    print(f"Using provider: {provider_name}")
    return get_gateway(provider_name)


async def run_scenario_b():
    """Scenario B: 单知识点出题 — "出一道AVL树旋转的选择题"."""
    provider = sys.argv[1] if len(sys.argv) > 1 else "api_vllm"
    gateway = create_gateway(provider)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    workspace = OUTPUT_DIR / "workspace"

    scheduler = DocScheduler(
        gateway,
        workspace=workspace,
        enable_thinking=False,
        model_routing={"_default": provider},
    )

    session_id = "test_scenario_b"

    # Turn 1: Teacher request
    print("\n" + "=" * 60)
    print("教师: 出一道AVL树旋转的选择题，难度中等")
    print("=" * 60)

    t0 = time.monotonic()
    result = await scheduler.run_conversation_turn(
        session_id=session_id,
        teacher_message="出一道AVL树旋转的选择题，难度中等",
        role="interact",
    )
    elapsed = time.monotonic() - t0

    print(f"\n[Turn 1 | {elapsed:.1f}s] status={result['status']}")
    print(f"files_written: {result['files_written']}")
    print(f"\n智能体回复:")
    print(result["response_text"][:2000])

    # Show written files
    for fn in result["files_written"]:
        fpath = workspace / session_id / fn
        if fpath.exists():
            content = fpath.read_text(encoding="utf-8")
            print(f"\n--- {fn} ({len(content)} chars) ---")
            print(content[:3000])

    # Turn 2: Teacher confirms
    print("\n" + "=" * 60)
    print("教师: 看起来不错，请确认并生成交接文档")
    print("=" * 60)

    t0 = time.monotonic()
    result2 = await scheduler.run_conversation_turn(
        session_id=session_id,
        teacher_message="看起来不错，请确认并生成slot_blueprint.yaml",
        role="interact",
    )
    elapsed = time.monotonic() - t0

    print(f"\n[Turn 2 | {elapsed:.1f}s] status={result2['status']}")
    print(f"files_written: {result2['files_written']}")
    print(f"\n智能体回复:")
    print(result2["response_text"][:2000])

    for fn in result2["files_written"]:
        fpath = workspace / session_id / fn
        if fpath.exists():
            content = fpath.read_text(encoding="utf-8")
            print(f"\n--- {fn} ({len(content)} chars) ---")
            print(content[:3000])


async def run_scenario_c():
    """Scenario C: 自由组卷 — "出一套计算机组成原理期末卷"."""
    provider = sys.argv[1] if len(sys.argv) > 1 else "api_vllm"
    gateway = create_gateway(provider)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    workspace = OUTPUT_DIR / "workspace"

    scheduler = DocScheduler(
        gateway,
        workspace=workspace,
        enable_thinking=False,
        model_routing={"_default": provider},
    )

    session_id = "test_scenario_c"

    # Turn 1: Teacher request
    print("\n" + "=" * 60)
    print("教师: 出一套计算机组成原理期末卷，10道选择+2道综合")
    print("=" * 60)

    t0 = time.monotonic()
    result = await scheduler.run_conversation_turn(
        session_id=session_id,
        teacher_message="出一套计算机组成原理期末卷，10道选择+2道综合",
        role="interact",
    )
    elapsed = time.monotonic() - t0

    print(f"\n[Turn 1 | {elapsed:.1f}s] status={result['status']}")
    print(f"files_written: {result['files_written']}")
    print(f"\n智能体回复:")
    print(result["response_text"][:3000])

    for fn in result["files_written"]:
        fpath = workspace / session_id / fn
        if fpath.exists():
            content = fpath.read_text(encoding="utf-8")
            outpath = OUTPUT_DIR / fn
            outpath.write_text(content, encoding="utf-8")
            print(f"\n--- {fn} ({len(content)} chars) → {outpath} ---")
            print(content[:3000])


if __name__ == "__main__":
    scenario = sys.argv[2] if len(sys.argv) > 2 else "b"

    if scenario == "c":
        asyncio.run(run_scenario_c())
    else:
        asyncio.run(run_scenario_b())
