"""Test the new 2-agent pipeline (creator + reviewer) with GLM-5.1.

Usage:
    python scripts/test_dual_agent_pipeline.py
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from core_new.llm_gateway import get_gateway
from core_new.doc_pipeline.dual_agent_orchestrator import DualAgentOrchestrator
from core_new.doc_pipeline.scheduler import DocScheduler

# Reuse the assembled.md from a previous successful run
ASSEMBLED_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs" / "workspace" / "2026-06-07T13-19-36-279984" / "q1" / "KP-untagged"
    / "assembled.md"
)


async def main():
    print("=" * 60)
    print("  GLM-5.1 Dual-Agent Pipeline Test (creator + reviewer)")
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

    slot_id = "KP-untagged"
    print(f"\n  Starting dual-agent pipeline (creator → reviewer CP1 → creator verify+solve → reviewer CP2 → creator final)...")
    print("=" * 60)

    t0 = time.time()

    scheduler = DocScheduler(
        gateway=gateway,
        workspace=workspace,
        model_routing={"_default": "glm5.1"},
    )
    orchestrator = DualAgentOrchestrator(
        scheduler=scheduler,
        workspace=workspace,
    )

    result = await orchestrator.run_pipeline(
        slot_id=slot_id,
        assembled_doc=assembled_content,
        question_type="comprehensive",
    )
    elapsed = time.time() - t0

    # Print results
    print("\n" + "=" * 60)
    print("  Pipeline Results")
    print("=" * 60)
    print(f"  OK: {result.ok}")
    print(f"  Pipeline type: {result.pipeline_type}")
    print(f"  Review status: {result.review_status}")
    print(f"  CP1 iterations: {result.analysis_iterations}")
    print(f"  Code exec OK: {result.code_exec_ok}")
    print(f"  Total time: {elapsed:.1f}s")
    if result.error:
        print(f"  Error: {result.error}")

    # List workspace files
    slot_dir = os.path.join(workspace, slot_id)
    print(f"\n  Workspace files:")
    if os.path.isdir(slot_dir):
        for fn in sorted(os.listdir(slot_dir)):
            fp = os.path.join(slot_dir, fn)
            if os.path.isfile(fp):
                size = os.path.getsize(fp)
                print(f"    {fn} ({size} bytes)")

    # Trace analysis
    trace_path = os.path.join(slot_dir or workspace, "trace.jsonl")
    if os.path.exists(trace_path):
        with open(trace_path, encoding="utf-8") as f:
            lines = f.readlines()
        print(f"\n  Trace: {len(lines)} rounds")
        for line in lines:
            try:
                entry = json.loads(line)
                print(f"    [{entry.get('agent', '?')}] attempt={entry.get('attempt', '?')} "
                      f"content={entry.get('content_len', '?')} "
                      f"reasoning={entry.get('reasoning_len', '?')} "
                      f"tools={entry.get('tool_calls', [])}")
            except Exception:
                pass

    # Show key outputs
    for label, fn in [("Question", "question.md"), ("Review", "review.md"),
                      ("Solution", "solution.md"), ("Final", "final.md")]:
        fp = os.path.join(slot_dir or workspace, fn)
        if os.path.exists(fp):
            content = open(fp, encoding="utf-8").read()
            print(f"\n  {label} ({len(content)} chars):")
            print("  " + "-" * 50)
            for line in content[:500].splitlines():
                print(f"    {line}")
            if len(content) > 500:
                print(f"    ... ({len(content) - 500} more chars)")

    # Verify step check
    verify_path = os.path.join(slot_dir or workspace, "verify.py")
    print(f"\n  verify.py exists: {os.path.exists(verify_path)}")
    if os.path.exists(verify_path):
        print(f"  verify.py size: {os.path.getsize(verify_path)} bytes")

    print(f"\n  Workspace: {workspace}")


if __name__ == "__main__":
    asyncio.run(main())
