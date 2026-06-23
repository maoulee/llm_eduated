"""Probe: difficulty-driven skeleton selection + K-scaling via expression optimization.

Two local experiments (before aligning upstream):
  Part A — K-radar target → select best-matching skeleton from past questions (难度驱动选择)
  Part B — on selected skeleton, RAISE a specific K-dimension by OPTIMIZING EXPRESSION
           (not just param swap — reword/restructure for 考察意图 to lift that K)

Feeds 5 AVL/binary-tree questions with diverse K-radar shapes.

Usage:
  set -a && source /zhaoshu/llm_eduated/.env && set +a && \
  python3 scripts/probe_difficulty_driven.py
"""
import asyncio
import os
import sys
import time
from pathlib import Path
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 5 questions with diverse K-radar (radar summary pre-extracted)
QS = [
    ("2026_Q41", "综合题", "K1=3,K2=2,K3=3,K4=4,K5=2 (K4主导：条件路由/陷阱，BST性质深度利用+剪枝)"),
    ("exercise_00266", "综合题", "K1=3,K2=2,K3=4,K4=3,K5=1 (K3主导：多步串行旋转推演)"),
    ("exercise_00272", "选择题", "K1=4,K2=1,K3=1,K4=3,K5=1 (K1主导：概念辨析 AVL vs BST)"),
    ("simulation_00175", "选择题", "K1=3,K2=2,K3=4,K4=4,K5=1 (K3-K4双高：多步插入推演+定义陷阱)"),
    ("exercise_00255", "选择题", "K1=3,K2=2,K3=1,K4=2,K5=1 (K1主导：概念记忆+单步公式)"),
]
QS_CTX = "\n".join(f"- {n} ({t}): {r}" for n, t, r in QS)

SYS_A = """你是命题分析者。给定目标 K-雷达形状，从往年题里选【骨架最匹配】的一道，并说明匹配理由。
K-雷达是 5 维（K1基础认知/K2单步代入/K3机制推演/K4条件路由陷阱/K5跨域联动），形状=各维组合。
匹配看【形状相似】（哪几维主导），不是单一难度数字。"""

SYS_B = """你是出题设计者。给定一个往年骨架，你要通过【优化表述/结构】来【提高指定的 K 维度】——不是换参数，是调整考察意图的呈现方式。
- 提高 K3（机制推演）：增加串行步骤、加状态依赖（前问结果作后问输入）
- 提高 K4（条件路由/陷阱）：加隐含前提、设反直觉陷阱、加边界条件辨析
- 提高 K1（概念辨析）：加易混概念对比
优化的是【怎么问/怎么设坑】（表述+结构），让题目在目标 K 维上更难。保持知识点不变。"""

ASK_A = """【目标考察需求】
考点：平衡二叉树 AVL（插入与旋转）
目标 K-雷达：K3=4, K4=4 双高（多步串行推演 + 定义陷阱辨析），K1=3,K2=2,K5=1

【往年题候选（含 K-雷达）】
{qs}

任务：选出骨架最匹配目标雷达的一道，说明为什么它的形状匹配（哪几维主导对得上）。只选一道+理由。"""

ASK_B = """【选定的骨架】（来自 Part A 的选择）
{selected}

【任务】在保持知识点（AVL 插入旋转）不变的前提下，通过优化【表述与设问结构】把 **K4（条件路由/陷阱）维度** 从当前值提高 1 档：
- 不要只换参数。要调整"怎么问、设什么坑"——加隐含前提、反直觉陷阱、边界辨析。
- 输出：优化后的设问结构（说明你在哪加陷阱、为什么这提高 K4），以及对应的符号化题干。
记住：优化表述提难度，不是堆参数。"""


async def call(client, model, sys_p, user_p, label, max_tokens=5000):
    t0 = time.time()
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": sys_p}, {"role": "user", "content": user_p}],
        max_tokens=max_tokens, extra_body={"thinking": {"type": "enabled"}})
    elapsed = time.time() - t0
    msg = resp.choices[0].message
    content = msg.content or ""
    reasoning = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None) or ""
    print(f"\n  [{label}] {elapsed:.1f}s | reasoning {len(reasoning)}c | content {len(content)}c")
    print(content[:1800])
    return content


async def main():
    base = os.environ.get("GLM_API_BASE"); key = os.environ.get("GLM_API_KEY")
    model = os.environ.get("GLM_MODEL", "glm-5.2")
    if not key:
        print("✗ GLM_API_KEY not set"); return
    client = AsyncOpenAI(base_url=base, api_key=key)

    print("=" * 72)
    print(f"  difficulty-driven probe — model={model}")
    print(f"  Part A: K-radar target → select skeleton")
    print(f"  Part B: skeleton → raise K4 via expression optimization")
    print("=" * 72)

    a_out = await call(client, model, SYS_A, ASK_A.replace("{qs}", QS_CTX), "A_选骨架")

    # extract selected name from A's output
    import re
    sel = ""
    for name, _, _ in QS:
        if name in a_out:
            sel = name; break
    sel_full = next((f"{n} ({t}): {r}" for n, t, r in QS if n == sel), a_out[:400])

    print(f"\n  >> Part A 选定: {sel}")
    b_out = await call(client, model, SYS_B, ASK_B.replace("{selected}", sel_full), "B_提K4优化表述")

    print(f"\n{'='*72}")
    print("  评估")
    print(f"  Part A 选骨架: {'✓ 选了 ' + sel if sel else '✗ 未明确选'}")
    print("  (预期：目标 K3-K4 双高 → 应选 simulation_00175 或 00266)")
    has_trap = any(k in b_out for k in ["陷阱", "隐含", "反直觉", "边界", "辨析"])
    print(f"  Part B 提K4优化表述: {'✓ 加了陷阱/隐含前提' if has_trap else '✗ 没优化表述'}")


if __name__ == "__main__":
    asyncio.run(main())
