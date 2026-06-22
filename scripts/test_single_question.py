"""Test 2: Single question pipeline — DocPipeline 5-layer with real Qwen."""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core_new.doc_pipeline import DocPipeline

OUTPUT_DIR = "docs/test_output/single_question"
os.makedirs(OUTPUT_DIR, exist_ok=True)


async def main():
    print("=" * 60)
    print("Test 2: Single Question Pipeline — 5-layer Qwen")
    print("=" * 60)

    # Use an existing assembled doc from a slot
    # Q12 = CO选择题 (计算机组成原理)
    assembled_path = "docs/compose/Q12_assembled.md"
    if not os.path.exists(assembled_path):
        print(f"  ERROR: {assembled_path} not found")
        return

    with open(assembled_path, "r", encoding="utf-8") as f:
        assembled_doc = f.read()

    print(f"  Loaded assembled doc: {len(assembled_doc)} chars")

    slot_data = {
        "slot_id": "Q12",
        "subject": "CO",
        "knowledge_tag": "CO-3 > 存储系统 > Cache",
        "difficulty": "medium",
        "question_type": "single_choice",
    }

    dp = DocPipeline(
        workspace=OUTPUT_DIR,
        model_routing={"_default": "api_vllm"},
    )

    t0 = time.time()
    result = await dp.run(
        slot_id="Q12",
        slot_data=slot_data,
        assembled_experience_doc=assembled_doc,
        question_type="single_choice",
    )
    elapsed = time.time() - t0

    print(f"\n  Pipeline result ({elapsed:.1f}s):")
    print(f"    ok: {result.ok}")
    print(f"    review_status: {result.review_status}")
    print(f"    final_content: {len(result.final_content or '')} chars")
    print(f"    total_time_s: {result.total_time_s}")

    # List all generated files
    print(f"\n  Generated files:")
    for fname in sorted(os.listdir(OUTPUT_DIR)):
        fpath = os.path.join(OUTPUT_DIR, fname)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            print(f"    {fname}: {size} chars")

    print(f"\n{'=' * 60}")
    print(f"Test 2 complete. Outputs in {OUTPUT_DIR}/")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
