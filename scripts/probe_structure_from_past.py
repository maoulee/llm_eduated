"""Probe: structure from past-question ANALYSIS (not invention).

Hypothesis: the 13-25k over-thinking happens because the design agent INVENTS a
concrete structure (then mentally verifies it works). If instead it ANALYZES the
structure of past same-type questions and ADAPTS (proven structure, new params),
there's nothing to invent/verify → no over-thinking.

Feed 3 past comprehensive AVL/binary-tree questions. Agent analyzes their structure
(sub-question chain, examination intent, asking style), then designs a NEW question
using a similar PROVEN structure with different params + solve.py.

Compare reasoning vs: combined 25k / split-B 13.8k (both failed).

Usage:
  set -a && source /zhaoshu/llm_eduated/.env && set +a && \
  python3 scripts/probe_structure_from_past.py
"""
import asyncio
import os
import re
import sys
import time
from pathlib import Path
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 3 same-type comprehensive AVL/binary-tree questions (structure references)
PAST = []
for fn in ["2026_Q41.md", "exercise_00266.md", "exercise_00262.md"]:
    p = Path(f"data/question_experiences/{fn}")
    if not p.exists():
        p = Path(f"/zhaoshu/llm_eduated/data/question_experiences/{fn}")
    if p.exists():
        # take 题干 + 考察模式 + 结构 sections (skip verbose K-radar)
        txt = p.read_text(encoding="utf-8")
        PAST.append(f"=== 往年综合题 {fn} ===\n{txt[:1800]}")
PAST_CTX = "\n\n".join(PAST) if PAST else "(无往年题)"

SYS = """你是出题设计者。你的核心原则：**结构来自往年题分析，不是发明**。

发明一道新结构需要验证它成立（容易陷入脑内模拟）。但往年真题的结构是已被验证的成熟结构。
你的工作方式：
1. 分析给的往年综合题的【结构】：子问怎么组织（基础问→核心问→区分度问）、考察意图怎么递进、设问方式
2. 选定一种成熟的往年结构作为本题骨架
3. 用新参数（符号占位）套这个骨架，写新题干 + solve.py

纪律：
- 你不发明新结构，你分析+复用往年结构。所以不需要验证"这题成不成立"——结构是往年验证过的。
- 题干参数用符号占位（如序列 S=[s₁..sₙ]），不写算出的具体答案。
- 禁止脑内模拟（不写"插入30→BF=2→旋转"）。具体值由 solve.py 算。
- 输出用 === question.md === 和 === solve.py === 分隔。"""

ASK = """考点：平衡二叉树 AVL（插入与旋转）
题型：综合应用题 | 目标难度：K3-K4（多步串行推演+陷阱）| 13 分

【往年同类型综合题（用于结构分析）】
{past}

【任务】
1. 先分析上面往年综合题的结构（子问组织、考察意图递进、设问方式）—— 用几句话概括结构骨架
2. 选定一种成熟结构作为本题骨架
3. 套用该结构，用新参数设计 AVL 综合题：题干（符号占位）+ solve.py（实例化+算答案+干扰）

记住：结构是分析复用的，不是你发明的。你只换参数 + 写 solve.py。"""


async def main():
    base = os.environ.get("GLM_API_BASE"); key = os.environ.get("GLM_API_KEY")
    model = os.environ.get("GLM_MODEL", "glm-5.2")
    if not key:
        print("✗ GLM_API_KEY not set"); return
    client = AsyncOpenAI(base_url=base, api_key=key)

    print("=" * 72)
    print(f"  structure-from-past probe — 综合 K3-K4 | model={model}")
    print(f"  往年同类型题喂入: {len(PAST)} 道（结构分析素材）")
    print(f"  对比: 合并25k失败 / 拆分B 13.8k失败 / 本探针=分析复用结构")
    print("=" * 72)

    messages = [{"role": "system", "content": SYS},
                {"role": "user", "content": ASK.replace("{past}", PAST_CTX)}]
    t0 = time.time()
    resp = await client.chat.completions.create(
        model=model, messages=messages, max_tokens=10000,
        extra_body={"thinking": {"type": "enabled"}})
    elapsed = time.time() - t0
    msg = resp.choices[0].message
    content = msg.content or ""
    reasoning = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None) or ""

    sim = len(re.findall(r"[Ss]tep\s*\d|Insert\s+\d+\s*→|BF\s*=\s*-?\d|插入\s*\d+\s*[→后]", reasoning + content))
    has_q = "=== question.md ===" in content or "## 题干" in content
    has_py = "=== solve.py ===" in content or "def " in content
    analyzed = "结构" in content[:800] and ("分析" in content[:800] or "骨架" in content[:800])

    print(f"\n  time {elapsed:.1f}s | reasoning {len(reasoning)}c | content {len(content)}c | finish {resp.choices[0].finish_reason}")
    print(f"  先分析往年结构: {'✓' if analyzed else '✗'} | 脑内模拟痕迹: {sim}")
    print(f"  产出 question.md: {'✓' if has_q else '✗'} | solve.py: {'✓' if has_py else '✗'}")
    print(f"\n  ── 输出（前 2500 字符）──")
    print(content[:2500])

    print(f"\n{'='*72}")
    print(f"  对比")
    print(f"  合并单 agent:     ~25000c reasoning | ✗ 失败")
    print(f"  拆分 B 设计求解:  ~13800c reasoning | ✗ 失败")
    print(f"  分析复用结构:     {len(reasoning)}c reasoning | {'✓ 成功' if (has_q and has_py) else '✗'}")
    win = len(reasoning) < 8000 and has_q and has_py
    print(f"  → {'✓ 分析复用结构消除过度思考' if win else '✗ 仍需改进'}")


if __name__ == "__main__":
    asyncio.run(main())
