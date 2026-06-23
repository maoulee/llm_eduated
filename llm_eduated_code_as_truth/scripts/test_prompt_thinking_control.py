"""A/B test: can prompt engineering control GLM's thinking behavior?

Same form_gate review case, thinking ENABLED, two prompts:
  A. ORIGINAL review prompt (current)
  B. ENHANCED with hard "thinking discipline" directives (CLAUDE.md-style)

Measures: reasoning tokens, time, verdict validity. If B's reasoning << A's
while verdict still valid → prompt engineering controls thinking depth.

Usage:
  set -a && source /zhaoshu/llm_eduated/.env && set +a && \
  python3 scripts/test_prompt_thinking_control.py
"""
import asyncio
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ARTIFACT_DIR = Path("docs/test_output/code_as_truth_e2e/single/TEST_SC")

# Hard thinking-discipline prefix (CLAUDE.md-style red lines)
THINKING_DISCIPLINE = """
## 思考纪律（强制红线，违反即失败）

本任务是 **checklist 逐项快速判定**，不是深度分析。你的思考必须极简：

- 每个检查项：读题干 → 一句话判定 pass/fail → 立即下一项。禁止展开推理链。
- 禁止反复推演、反复验证、来回斟酌。
- 禁止计算任何数值（答案由 solve.py 决定，不归你管）。
- 7 项判定完，立即输出 review.md，结束。
- 目标：思考量 < 1500 tokens，全程不超过 30 秒。

记住：这是审核，不是解题。想得越多越错。
"""


def build_messages(enhanced: bool):
    from core_new.doc_pipeline.config import AGENT_PROMPTS, ROLE_SKILLS
    system = AGENT_PROMPTS.get("review", "")
    if enhanced:
        system = THINKING_DISCIPLINE.strip() + "\n\n" + system
    skill = ROLE_SKILLS.get("review", "")
    q = (ARTIFACT_DIR / "question.md").read_text(encoding="utf-8")
    dc = (ARTIFACT_DIR / "design_card.md").read_text(encoding="utf-8")
    user = (f"请审核以下题目的设计质量（此阶段无答案，不评估答案正确性）。\n\n"
            f"## 工作规范\n{skill}\n\n## 规划\n{dc}\n\n## 题目\n{q}\n")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


async def run(client, model, label, enhanced):
    messages = build_messages(enhanced)
    t0 = time.time()
    reasoning = 0
    parts = []
    extra_body = {"thinking": {"type": "enabled"}}  # thinking ON for both
    stream = await client.chat.completions.create(
        model=model, messages=messages, max_tokens=8192,
        stream=True, extra_body=extra_body,
    )
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            parts.append(delta.content)
        r = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None) or ""
        if r:
            reasoning += len(r)
    elapsed = time.time() - t0
    text = "".join(parts)
    vm = re.search(r"status\**\s*[:：]\s*\*{0,2}(pass|needs_fix)", text, re.I)
    verdict = vm.group(1).lower() if vm else "—"
    computed = bool(re.search(r"[A-D][.．、]\s*\d{2,}|正确答案[应为：:]+\s*\d", text))
    print(f"\n  [{label}] {elapsed:5.1f}s  reasoning={reasoning:6d}  "
          f"content={len(text):5d}  verdict={verdict}  computed={'⚠️' if computed else 'ok'}")
    print(f"    head: {text[:240].replace(chr(10),' ')}")
    return {"label": label, "time": elapsed, "reasoning": reasoning,
            "content": len(text), "verdict": verdict}


async def main():
    from openai import AsyncOpenAI
    base = os.environ.get("GLM_API_BASE")
    key = os.environ.get("GLM_API_KEY")
    model = os.environ.get("GLM_MODEL", "glm-5.2")
    if not key:
        print("  ✗ GLM_API_KEY not set"); return
    client = AsyncOpenAI(base_url=base, api_key=key)

    print("=" * 72)
    print(f"  prompt thinking-control A/B — model={model}, thinking=enabled")
    print(f"  A = original review prompt | B = + thinking discipline prefix")
    print("=" * 72)

    a = await run(client, model, "A_original", enhanced=False)
    b = await run(client, model, "B_disciplined", enhanced=True)

    print("\n" + "=" * 72)
    print("  VERDICT: does prompt control thinking?")
    print("=" * 72)
    d_reason = a["reasoning"] - b["reasoning"]
    d_time = a["time"] - b["time"]
    print(f"  reasoning: {a['reasoning']} → {b['reasoning']}  ({'↓'+str(d_reason) if d_reason>0 else '↑'+str(-d_reason)})")
    print(f"  time:      {a['time']:.1f}s → {b['time']:.1f}s  ({'↓'+str(round(d_time,1)) if d_time>0 else '↑'+str(round(-d_time,1))})")
    works = b["reasoning"] < a["reasoning"] * 0.6 and b["verdict"] != "—"
    print(f"  → {'✓ YES — prompt cut thinking >40% with valid verdict' if works else '✗ weak — prompt did not meaningfully cut thinking'}")


if __name__ == "__main__":
    asyncio.run(main())
