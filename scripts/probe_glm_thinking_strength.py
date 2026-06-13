"""Probe: does GLM accept thinking strength control (adaptive + effort)?

Tests the form_gate review case against GLM with several thinking configs to see
if `thinking.type=adaptive` + `output_config.effort` gives fine-grained control
over reasoning depth (vs our current binary enabled/disabled).

Configs tested:
  1. enabled            (current default — known to over-think: 14k tokens, fails)
  2. adaptive + low     (light thinking — target for form_gate)
  3. adaptive + medium
  4. adaptive + high
  5. disabled           (known: works, 0 reasoning)

Measures per config: HTTP status (accepted?), time, reasoning tokens, content,
verdict. Answers: can we control thinking STRENGTH, not just on/off?

Usage (env from main repo .env):
  set -a && source /zhaoshu/llm_eduated/.env && set +a && \
  python3 scripts/probe_glm_thinking_strength.py
"""
import asyncio
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ARTIFACT_DIR = Path("docs/test_output/code_as_truth_e2e/single/TEST_SC")

CONFIGS = [
    ("1_enabled",         {"thinking": {"type": "enabled"}}),
    ("2_adaptive_low",    {"thinking": {"type": "adaptive"}, "output_config": {"effort": "low"}}),
    ("3_adaptive_medium", {"thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"}}),
    ("4_adaptive_high",   {"thinking": {"type": "adaptive"}, "output_config": {"effort": "high"}}),
    ("5_disabled",        {"thinking": {"type": "disabled"}}),
]


def build_messages():
    from core_new.doc_pipeline.config import AGENT_PROMPTS, ROLE_SKILLS
    system = AGENT_PROMPTS.get("review", "")
    skill = ROLE_SKILLS.get("review", "")
    q = (ARTIFACT_DIR / "question.md").read_text(encoding="utf-8")
    dc = (ARTIFACT_DIR / "design_card.md").read_text(encoding="utf-8")
    user = (f"请审核以下题目的设计质量（此阶段无答案，不评估答案正确性）。\n\n"
            f"## 工作规范\n{skill}\n\n## 规划\n{dc}\n\n## 题目\n{q}\n")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


async def probe(client, model, label, extra_body):
    messages = build_messages()
    t0 = time.time()
    reasoning = 0
    content_parts = []
    status = "ok"
    try:
        stream = await client.chat.completions.create(
            model=model, messages=messages, max_tokens=8192,
            stream=True, extra_body=extra_body,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                content_parts.append(delta.content)
            r = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None) or ""
            if r:
                reasoning += len(r)
        finish = chunk.choices[0].finish_reason if chunk.choices else "?"
    except Exception as e:
        status = f"ERR {type(e).__name__}: {str(e)[:120]}"
        finish = "-"
    elapsed = time.time() - t0
    text = "".join(content_parts)
    # verdict (handle **status** markdown bold)
    vm = re.search(r"status\**\s*[:：]\s*\*{0,2}(pass|needs_fix)", text, re.I)
    verdict = vm.group(1).lower() if vm else "—"
    computed = bool(re.search(r"[A-D][.．、]\s*\d{2,}|正确答案[应为：:]+\s*\d", text))
    print(f"\n  [{label}] {elapsed:5.1f}s  reasoning={reasoning:6d}  "
          f"content={len(text):5d}  finish={finish}  verdict={verdict}  "
          f"computed={'⚠️' if computed else 'ok'}  [{status}]")
    if text:
        print(f"    head: {text[:200].replace(chr(10),' ')}")
    return {"label": label, "time": elapsed, "reasoning": reasoning,
            "content": len(text), "verdict": verdict, "status": status}


async def main():
    from openai import AsyncOpenAI
    base = os.environ.get("GLM_API_BASE", "https://open.bigmodel.cn/api/coding/paas/v4/")
    key = os.environ.get("GLM_API_KEY")
    model = os.environ.get("GLM_MODEL", "glm-5.2")
    if not key:
        print("  ✗ GLM_API_KEY not set — source /zhaoshu/llm_eduated/.env"); return
    client = AsyncOpenAI(base_url=base, api_key=key)

    print("=" * 72)
    print(f"  GLM thinking-strength probe — model={model}")
    print(f"  case: form_gate review (single-choice, no options)")
    print("=" * 72)

    results = []
    for label, eb in CONFIGS:
        results.append(await probe(client, model, label, eb))

    print("\n" + "=" * 72)
    print("  SUMMARY (does effort control thinking strength?)")
    print("=" * 72)
    print(f"  {'config':22s} {'time':>6s} {'reasoning':>9s} {'content':>7s} {'verdict':>9s} status")
    for r in results:
        print(f"  {r['label']:22s} {r['time']:5.1f}s {r['reasoning']:9d} "
              f"{r['content']:7d} {r['verdict']:>9s} {r['status'][:30]}")
    print("=" * 72)
    print("  → if adaptive_low reasoning << enabled and verdict still valid: EFFORT WORKS")


if __name__ == "__main__":
    asyncio.run(main())
