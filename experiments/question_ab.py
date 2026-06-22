"""A/B test: question agent with brief thinking vs deep thinking.

Only runs the question agent (not full pipeline) for fast comparison.
Uses the existing blueprint from workspace/FULL_V5/Q43/blueprint.md.
"""

import asyncio
import json
import logging
import os
import sys
import time
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-30s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("q_ab_test")

BLUEPRINT_PATH = Path("workspace/FULL_V5/Q43/blueprint.md")


async def run_question_variant(variant: str, slot_id: str):
    """Run question agent once.

    variant: "brief" (current two-phase) or "deep" (full verification with answers)
    """
    import core_new.provider_router as pr
    # Use local provider directly, no need to force remote off
    pr._local_available = True

    from core_new.doc_pipeline.scheduler import DocScheduler
    from core_new.provider_router import get_gateway

    gateway = get_gateway("api_vllm")
    ws = Path("workspace") / slot_id
    ws.mkdir(parents=True, exist_ok=True)

    scheduler = DocScheduler(
        gateway=gateway,
        workspace="workspace",
        model_routing=None,
    )

    # Read blueprint
    blueprint_text = BLUEPRINT_PATH.read_text(encoding="utf-8")

    # Build task
    task = f"请根据以下蓝图设计完整题目。\n\n## 蓝图\n{blueprint_text}"

    if variant == "deep":
        task += (
            "\n\n【深度模式】请完整验证所有参数，计算每个子问题的最终答案。"
            "验证脚本必须从参数推导到最终答案，确保每一步数值正确。"
        )
    else:
        task += (
            "\n\n【两步模式】"
            "第1步：深度思考知识点覆盖、逻辑关联、题干表述，消除歧义，选参数但不验证。"
            "第2步：用exec_python验证参数闭环（封闭性、推导路径等价、换算自洽），不计算最终答案。"
        )

    start = time.monotonic()
    result = await scheduler.run_agent(
        "question",
        task,
        slot_id=slot_id,
        inject_files={"蓝图": str(BLUEPRINT_PATH)},
    )
    elapsed = time.monotonic() - start

    question_path = ws / "question.md"
    content = question_path.read_text(encoding="utf-8") if question_path.exists() else result

    return {
        "variant": variant,
        "slot_id": slot_id,
        "elapsed_s": round(elapsed, 1),
        "content_len": len(content),
        "content": content,
    }


async def main():
    logger.info("=== Question Agent A/B Test ===")
    logger.info("Blueprint: %s", BLUEPRINT_PATH)

    results = {}

    # Run brief mode (current two-phase)
    logger.info("\n--- Variant A: Brief thinking (两步模式) ---")
    r_a = await run_question_variant("brief", "AB_TEST_BRIEF")
    results["brief"] = r_a
    logger.info(
        "Brief: %.1fs, %d chars",
        r_a["elapsed_s"], r_a["content_len"],
    )

    # Run deep mode (full verification)
    logger.info("\n--- Variant B: Deep thinking (完整验证) ---")
    r_b = await run_question_variant("deep", "AB_TEST_DEEP")
    results["deep"] = r_b
    logger.info(
        "Deep: %.1fs, %d chars",
        r_b["elapsed_s"], r_b["content_len"],
    )

    # Compare
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)
    print(f"{'Metric':<20} {'Brief':>12} {'Deep':>12}")
    print("-" * 44)
    print(f"{'Time (s)':<20} {r_a['elapsed_s']:>12.1f} {r_b['elapsed_s']:>12.1f}")
    print(f"{'Content (chars)':<20} {r_a['content_len']:>12} {r_b['content_len']:>12}")
    print(f"{'Time ratio':<20} {'1.0x':>12} {r_b['elapsed_s']/max(r_a['elapsed_s'],0.1):>11.1f}x")

    # Save outputs
    out_dir = Path("workspace/AB_COMPARE")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "brief_question.md").write_text(r_a["content"], encoding="utf-8")
    (out_dir / "deep_question.md").write_text(r_b["content"], encoding="utf-8")
    (out_dir / "compare.json").write_text(
        json.dumps({
            "brief": {"elapsed_s": r_a["elapsed_s"], "content_len": r_a["content_len"]},
            "deep": {"elapsed_s": r_b["elapsed_s"], "content_len": r_b["content_len"]},
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Outputs saved to %s", out_dir)


if __name__ == "__main__":
    asyncio.run(main())
