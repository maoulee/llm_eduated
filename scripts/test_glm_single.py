"""Test: Single question pipeline — 5-layer GLM (remote)."""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core_new.doc_pipeline import DocPipeline
from core_new.provider_router import set_routing_profile

OUTPUT_DIR = "docs/test_output/glm_single"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Use Q41 (AVL tree) assembled doc for a different topic from previous tests
ASSEMBLED_PATH = "docs/compose/Q41_assembled.md"


async def main():
    print("=" * 60)
    print("Test: Single Question Pipeline — 5-layer GLM")
    print("=" * 60)

    if not os.path.exists(ASSEMBLED_PATH):
        print(f"  ERROR: {ASSEMBLED_PATH} not found")
        return

    with open(ASSEMBLED_PATH, "r", encoding="utf-8") as f:
        assembled_doc = f.read()

    print(f"  Loaded assembled doc: {len(assembled_doc)} chars")

    # Route all agents to remote GLM
    model_routing = set_routing_profile("all_remote")
    print(f"  Routing: all_remote (model_routing={model_routing})")

    slot_data = {
        "slot_id": "Q41",
        "subject": "DS",
        "knowledge_tag": "DS-5 > 树与二叉树 > 平衡二叉树AVL",
        "difficulty": "hard",
        "question_type": "comprehensive",
    }

    dp = DocPipeline(
        workspace=OUTPUT_DIR,
        model_routing=model_routing,
    )

    t0 = time.time()
    result = await dp.run(
        slot_id="Q41",
        slot_data=slot_data,
        assembled_experience_doc=assembled_doc,
        question_type="comprehensive",
    )
    elapsed = time.time() - t0

    print(f"\n  Pipeline result ({elapsed:.1f}s):")
    print(f"    ok: {result.ok}")
    print(f"    review_status: {result.review_status}")
    print(f"    final_content: {len(result.final_content or '')} chars")
    print(f"    total_time_s: {result.total_time_s}")

    # List all generated files
    print(f"\n  Generated files:")
    ws = os.path.join(OUTPUT_DIR, "Q41")
    if os.path.isdir(ws):
        for fname in sorted(os.listdir(ws)):
            fpath = os.path.join(ws, fname)
            if os.path.isfile(fpath):
                size = os.path.getsize(fpath)
                print(f"    {fname}: {size} bytes")

    print(f"\n{'=' * 60}")
    print(f"Test complete. Outputs in {OUTPUT_DIR}/")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
