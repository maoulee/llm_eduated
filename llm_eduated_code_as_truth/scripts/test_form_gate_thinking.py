"""Isolated form_gate (review) test: thinking ON vs OFF on a real blocked case.

Takes the REAL question.md + design_card.md from a prior single-choice run (the
code-as-truth case that form_gate kept failing because it had no options), and
calls ONLY the review agent — twice, thinking on then off. Measures:
  - time
  - verdict (pass / needs_fix)
  - BAD BEHAVIOR: did the reviewer compute answer/option values? (code-as-truth violation)

Provider defaults to glm5.1 (reads GLM_MODEL env = the new model). Override with
--provider api_vllm to compare on local Qwen.

Usage:
  python3 scripts/test_form_gate_thinking.py                 # GLM new model
  python3 scripts/test_form_gate_thinking.py --provider api_vllm  # local Qwen
"""
import argparse
import asyncio
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Real artifacts from the single-choice run that form_gate kept blocking
ARTIFACT_DIR = Path("docs/test_output/code_as_truth_e2e/single/TEST_SC")


def build_review_messages():
    """Replicate the review agent's system + user message."""
    from core_new.doc_pipeline.config import AGENT_PROMPTS, ROLE_SKILLS

    system = AGENT_PROMPTS.get("review", "")
    skill = ROLE_SKILLS.get("review", "")

    q = (ARTIFACT_DIR / "question.md").read_text(encoding="utf-8")
    dc = (ARTIFACT_DIR / "design_card.md").read_text(encoding="utf-8")

    # user message: task + skill (injected per double-injection fix) + files
    user = (
        "请审核以下题目的设计质量（此阶段无答案，不评估答案正确性）。\n\n"
        f"## 工作规范\n{skill}\n\n"
        f"## 规划（design_card）\n{dc}\n\n"
        f"## 题目（question.md）\n{q}\n"
    )
    return [{"role": "system", "content": system},
            {"role": "user", "content": user}]


def parse_verdict(text: str) -> tuple[str, bool]:
    """Return (status, computed_answers)."""
    status = "unknown"
    m = re.search(r"status[:：]\s*\*{0,2}(pass|needs_fix)", text, re.I)
    if m:
        status = m.group(1).lower()
    # BAD BEHAVIOR: reviewer computed option/answer values (A.123 / 正确答案：X / 选项值)
    computed = bool(re.search(r"[A-D][.．、]\s*\d{2,}|正确答案[应为：:]+\s*\d|选项[值应为]+[：:\d]", text))
    # also flag if it literally proposes 4 numeric options
    has_options = len(re.findall(r"[A-D][.．、]\s*\d", text)) >= 3
    return status, (computed or has_options)


async def call_review(gateway, label, enable_thinking):
    messages = build_review_messages()
    t0 = time.time()
    result = await gateway.stream_chat(
        messages, enable_thinking=enable_thinking, max_tokens=4096,
    )
    elapsed = time.time() - t0
    text = (result or {}).get("content", "") or ""
    reasoning = (result or {}).get("reasoning_content", "") or ""
    status, computed = parse_verdict(text)
    print(f"\n  [{label}] thinking={'ON ' if enable_thinking else 'OFF'}")
    print(f"    time: {elapsed:.1f}s")
    print(f"    verdict: {status}")
    print(f"    computed answer values (BAD): {'⚠️ YES — code-as-truth violation' if computed else '✓ no'}")
    print(f"    output (first 400 chars): {text[:400].replace(chr(10),' ')}")
    return {"label": label, "thinking": enable_thinking, "time": elapsed,
            "status": status, "computed": computed}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="glm5.1", choices=["glm5.1", "api_vllm"])
    args = ap.parse_args()

    if not ARTIFACT_DIR.exists():
        print(f"  ✗ artifacts not found: {ARTIFACT_DIR}")
        print("    run scripts/test_code_as_truth_e2e.py --only single first")
        return

    from core_new.llm_gateway import get_gateway
    if args.provider == "api_vllm":
        os.environ.setdefault("VLLM_MODEL", "/zhaoshu/llm/Qwen3.6-27B-FP8")
        os.environ.setdefault("VLLM_API_BASE", "http://127.0.0.1:8000/v1")
    gateway = get_gateway(args.provider)

    print("=" * 70)
    print(f"  form_gate isolated test — provider={args.provider}")
    print(f"  case: real single-choice question.md (code-as-truth, NO options yet)")
    print(f"  expected verdict: pass (form OK; no options is normal at form_gate)")
    print("=" * 70)

    results = []
    results.append(await call_review(gateway, "A_thinking_ON", enable_thinking=True))
    results.append(await call_review(gateway, "B_thinking_OFF", enable_thinking=False))

    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    for r in results:
        correct = "✓" if r["status"] == "pass" else "✗"
        bad = "⚠️computed" if r["computed"] else "clean"
        print(f"  {r['label']:16s} {r['time']:6.1f}s  verdict={r['status']:10s} "
              f"{correct}  {bad}")
    on_t = results[0]["time"]; off_t = results[1]["time"]
    print(f"\n  speedup (thinking OFF): {on_t/off_t:.2f}x  ({on_t:.0f}s → {off_t:.0f}s)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
