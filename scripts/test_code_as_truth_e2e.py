"""E2E test: code-as-truth pipeline (graph path) on local Qwen vLLM.

Tests BOTH question types against a local vLLM server (api_vllm provider):
  - single_choice (选择题): Question writes stem + solve.py; Solve execs → assembles options
  - comprehensive (主观题/综合题): Question writes stem + sub-questions + solve.py; Solve execs → answers

Verifies code-as-truth contract:
  1. question stage produced solve.py (NOT solve agent)
  2. solve.py was exec'd (solve_output.txt exists, non-empty)
  3. options assembled into question.md (choice) / answers in solution.md (comp)
  4. final result ok

Prerequisite: vLLM running on port 8000 with /zhaoshu/llm/Qwen3.6-27B-FP8:
  python -m vllm.entrypoints.openai.api_server --model /zhaoshu/llm/Qwen3.6-27B-FP8 ...

Usage:
  VLLM_MODEL=/zhaoshu/llm/Qwen3.6-27B-FP8 python3 scripts/test_code_as_truth_e2e.py [--only single|comp]
"""
import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force local Qwen vLLM as the provider for all roles
os.environ.setdefault("VLLM_MODEL", "/zhaoshu/llm/Qwen3.6-27B-FP8")
os.environ.setdefault("VLLM_API_BASE", "http://127.0.0.1:8000/v1")

OUTPUT_DIR = Path("docs/test_output/code_as_truth_e2e")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Test cases (based on prior trajectories) ──────────────────────────

SINGLE_CHOICE_SLOT = {
    "slot_id": "TEST_SC",
    "subject": "数据结构",
    "knowledge_tag": "DS-5 > 树与二叉树 > 二叉树带权路径长度(WPL)",
    "primary_target_name": "二叉树带权路径长度",
    "examination_mode": "计算型——WPL公式计算与树结构分析",
    "difficulty": "medium",
    "question_type": "single_choice",
    "complexity": "standard",
}

COMP_ASSEMBLED_PATH = "docs/compose/Q41_assembled.md"  # AVL tree (comprehensive)


async def run_one(label, slot_id, slot_data, output_sub, question_type,
                  assembled_doc=""):
    from core_new.doc_pipeline import DocPipeline
    from core_new.llm_gateway import get_gateway

    out = OUTPUT_DIR / output_sub
    out.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*70}")
    print(f"  [{label}] question_type={question_type}")
    print(f"{'='*70}")

    provider = "api_vllm"
    try:
        gateway = get_gateway(provider)
    except Exception as e:
        print(f"  ✗ cannot build gateway '{provider}': {e}")
        print(f"    → is vLLM running on port 8000? (VLLM_API_BASE={os.environ.get('VLLM_API_BASE')})")
        return None

    dp = DocPipeline(
        gateway=gateway,
        workspace=str(out),
        model_routing={"_default": provider},
        enable_thinking=True,
    )

    t0 = time.time()
    try:
        result = await dp.run(
            slot_id=slot_id,
            slot_data=slot_data,
            assembled_experience_doc=assembled_doc,
            question_type=question_type,
        )
    except Exception as e:
        import traceback
        print(f"  ✗ pipeline crashed: {e}")
        traceback.print_exc()
        return None
    elapsed = time.time() - t0

    # ── Verify code-as-truth artifacts ──
    ws = out / slot_id
    artifacts = {
        "question.md": (ws / "question.md").exists(),
        "solve.py": (ws / "solve.py").exists(),          # ← must be written by QUESTION stage
        "solve_output.txt": (ws / "solve_output.txt").exists(),  # ← exec happened
        "solution.md": (ws / "solution.md").exists(),
        "final.md": (ws / "final.md").exists(),
    }
    # options assembled into question.md?
    qtext = (ws / "question.md").read_text(encoding="utf-8") if artifacts["question.md"] else ""
    has_options = any(f"{L}." in qtext or f"{L}．" in qtext for L in "ABCD") if question_type == "single_choice" else True
    solve_out_size = (ws / "solve_output.txt").stat().st_size if artifacts["solve_output.txt"] else 0

    print(f"\n  elapsed: {elapsed:.1f}s")
    print(f"  result.ok: {result.ok}  | review_status: {result.review_status}")
    print(f"  final_content: {len(result.final_content or '')} chars")
    print(f"\n  code-as-truth artifacts:")
    for k, v in artifacts.items():
        mark = "✓" if v else "✗"
        print(f"    {mark} {k}")
    print(f"    options in question.md: {'✓' if has_options else '✗'} (choice)")
    print(f"    solve_output.txt size: {solve_out_size} bytes")

    # ── Dump key files for inspection ──
    print(f"\n  ── solve.py (first 25 lines) ──")
    sp = ws / "solve.py"
    if sp.exists():
        for i, line in enumerate(sp.read_text(encoding="utf-8").splitlines()[:25]):
            print(f"    {line}")
    else:
        print("    (missing — code-as-truth FAILED: question did not write solve.py)")

    print(f"\n  ── solve_output.txt ──")
    so = ws / "solve_output.txt"
    print("    " + (so.read_text(encoding="utf-8")[:500].replace("\n", "\n    ") if so.exists() else "(missing)"))

    return {
        "label": label, "ok": result.ok, "elapsed": elapsed,
        "artifacts": artifacts, "has_options": has_options,
        "solve_output_size": solve_out_size,
    }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["single", "comp"], default=None)
    args = ap.parse_args()

    print("=" * 70)
    print("  code-as-truth E2E test (local Qwen vLLM, graph path)")
    print(f"  VLLM_MODEL={os.environ.get('VLLM_MODEL')}")
    print(f"  VLLM_API_BASE={os.environ.get('VLLM_API_BASE')}")
    print("=" * 70)

    results = []

    if args.only in (None, "single"):
        r = await run_one("SINGLE_CHOICE", "TEST_SC", SINGLE_CHOICE_SLOT,
                          "single", "single_choice")
        if r:
            results.append(r)

    if args.only in (None, "comp"):
        if not Path(COMP_ASSEMBLED_PATH).exists():
            print(f"\n  skip comprehensive: {COMP_ASSEMBLED_PATH} not found")
        else:
            assembled = Path(COMP_ASSEMBLED_PATH).read_text(encoding="utf-8")
            comp_slot = {
                "slot_id": "TEST_COMP",
                "subject": "数据结构",
                "knowledge_tag": "DS-5 > 树与二叉树 > 平衡二叉树AVL",
                "difficulty": "hard",
                "question_type": "comprehensive",
                "complexity": "standard",
            }
            r = await run_one("COMPREHENSIVE", "TEST_COMP", comp_slot,
                              "comp", "comprehensive", assembled_doc=assembled)
            if r:
                results.append(r)

    # ── Summary ──
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    for r in results:
        cat_ok = (
            r["artifacts"]["solve.py"]
            and r["solve_output_size"] > 0
            and r["has_options"]
        )
        verdict = "✓ code-as-truth OK" if cat_ok else "✗ code-as-truth BROKEN"
        print(f"  {r['label']:14s} pipeline_ok={r['ok']!s:5s}  "
              f"solve.py={r['artifacts']['solve.py']!s:5s}  "
              f"exec_output={r['solve_output_size']:>5d}B  "
              f"options={r['has_options']!s:5s}  → {verdict}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
