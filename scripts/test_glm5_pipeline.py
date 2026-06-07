"""Direct pipeline test with GLM-5.1 — bypasses interactive layer.

Uses the existing assembled.md from a previous run and calls DocPipeline
directly with GLM-5.1 as the gateway for all agents.

Usage:
    python scripts/test_glm5_pipeline.py
"""
import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from core_new.llm_gateway import get_gateway
from core_new.doc_pipeline import DocPipeline


# Use the assembled.md from the previous successful run
PREV_WORKSPACE = (
    Path(__file__).resolve().parent.parent
    / "docs" / "workspace" / "2026-06-07T13-19-36-279984" / "q1" / "KP-untagged"
)
ASSEMBLED_PATH = PREV_WORKSPACE / "assembled.md"


async def main():
    print("=" * 60)
    print("  GLM-5.1 Direct Pipeline Test")
    print("=" * 60)
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    if not ASSEMBLED_PATH.exists():
        print(f"  ERROR: assembled.md not found at {ASSEMBLED_PATH}")
        return

    assembled_content = ASSEMBLED_PATH.read_text(encoding="utf-8")
    print(f"  Assembled doc: {len(assembled_content)} chars")

    # Create workspace
    run_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")
    workspace = os.path.join("docs", "workspace", run_id)
    os.makedirs(workspace, exist_ok=True)
    print(f"  Workspace: {workspace}")

    # Use GLM-5.1 for all agents
    gateway = get_gateway("glm5.1")
    print(f"  Gateway: GLM-5.1 ({gateway._model_name})")

    # Run pipeline
    slot_id = "KP-untagged"
    slot_data = {
        "slot_id": slot_id,
        "subject": "DS",
        "knowledge_tag": "DS-树-二叉搜索树-平衡二叉树",
        "difficulty": "hard",
        "question_type": "comprehensive",
    }

    print(f"\n  Starting pipeline (5 layers: outline → question → review → solve → final_review)...")
    print("=" * 60)

    t0 = time.time()
    dp = DocPipeline(
        workspace=workspace,
        gateway=gateway,
        model_routing={"_default": "glm5.1"},
    )
    result = await dp.run(
        slot_id=slot_id,
        slot_data=slot_data,
        assembled_experience_doc=assembled_content,
        question_type="comprehensive",
    )
    elapsed = time.time() - t0

    # Print results
    print("\n" + "=" * 60)
    print("  Pipeline Results")
    print("=" * 60)
    print(f"  OK: {result.ok}")
    print(f"  Review status: {result.review_status}")
    print(f"  Final review status: {result.final_review_status}")
    print(f"  Total time: {elapsed:.1f}s")

    # List workspace files
    print(f"\n  Workspace files:")
    for root, dirs, files in os.walk(workspace):
        for fn in sorted(files):
            fp = os.path.join(root, fn)
            size = os.path.getsize(fp)
            rel = os.path.relpath(fp, workspace)
            print(f"    {rel} ({size} bytes)")

    # Check for trace
    trace_path = os.path.join(workspace, slot_id, "trace.jsonl")
    if os.path.exists(trace_path):
        with open(trace_path, encoding="utf-8") as f:
            lines = f.readlines()
        print(f"\n  Trace: {len(lines)} rounds")
        for line in lines:
            try:
                entry = __import__("json").loads(line)
                print(f"    [{entry.get('agent', '?')}] attempt={entry.get('attempt', '?')} "
                      f"action={entry.get('action', '?')} "
                      f"content={entry.get('content_len', '?')} "
                      f"reasoning={entry.get('reasoning_len', '?')} "
                      f"tools={entry.get('tool_calls', [])}")
            except Exception:
                pass

    # Show question preview
    q_path = os.path.join(workspace, slot_id, "question.md")
    if os.path.exists(q_path):
        content = open(q_path, encoding="utf-8").read()
        print(f"\n  Question preview ({len(content)} chars):")
        print("  " + "-" * 50)
        for line in content[:600].splitlines():
            print(f"    {line}")
        if len(content) > 600:
            print(f"    ... ({len(content) - 600} more chars)")

        # Quick quality check
        has_code = "```" in content
        has_avl_insert = "AVL_Insert" in content
        print(f"\n  Quality: has_code_blocks={'YES' if has_code else 'NO'} "
              f"has_pseudo_code={'YES' if has_avl_insert else 'NO'}")

    # Show final.md preview
    final_path = os.path.join(workspace, slot_id, "final.md")
    if os.path.exists(final_path):
        content = open(final_path, encoding="utf-8").read()
        print(f"\n  Final output: {len(content)} chars → {final_path}")
    else:
        print(f"\n  WARNING: final.md not generated")

    print(f"\n  Workspace: {workspace}")


if __name__ == "__main__":
    asyncio.run(main())
