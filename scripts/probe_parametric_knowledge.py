"""Probe: does GLM's parametric knowledge contain rich exam-pattern info per knowledge point?

Tests whether we can MINE the model's internal knowledge ("AVL 旋转常见考察形式")
instead of relying on the lossy cluster+induce assembled-doc pipeline.

For each knowledge point, asks GLM: 常见考察形式 + 设问类型 + 典型陷阱 + 难度.
If answers are concrete & usable → parametric knowledge can drive design directly.

Usage:
  set -a && source /zhaoshu/llm_eduated/.env && set +a && \
  python3 scripts/probe_parametric_knowledge.py
"""
import asyncio
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KPrompts = [
    ("AVL树插入与旋转", "数据结构，平衡二叉树 AVL 的插入与旋转"),
    ("Cache地址映射", "计算机组成原理，Cache 地址映射（直接/组相联）与命中率"),
    ("指令流水线冒险", "计算机组成原理，指令流水线的数据/控制冒险与阻塞"),
]

SYS = "你是资深 408 考研命题专家。请基于你的专业知识，给出下列考点的考试常见考察形式。"
ASK = """考点：{kp}

请给出（要具体、可操作，不要空泛）：
1. **常见考察形式**（3-5 种）：每种用一句话描述"怎么考"（如"给定插入序列，画出每次插入后的树形并标注旋转类型"）
2. **典型设问类型**：子问题通常怎么问（计算/判断/画图/分析）
3. **典型陷阱/易错点**（3-4 个）：学生常犯的错（如"把 RL 误判为 LR"）
4. **难度定位**：这个考点通常对应 K3-K4 还是更高，为什么

直接给结论，不要寒暄。"""


async def ask(client, model, kp, desc):
    t0 = asyncio.get_event_loop().time()
    res = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYS},
                  {"role": "user", "content": ASK.format(kp=desc)}],
        max_tokens=3000, extra_body={"thinking": {"type": "enabled"}},
    )
    elapsed = asyncio.get_event_loop().time() - t0
    msg = res.choices[0].message
    content = msg.content or ""
    reasoning = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None) or ""
    print(f"\n{'='*72}")
    print(f"  考点：{kp}  ({elapsed:.1f}s, reasoning={len(reasoning)}, content={len(content)})")
    print(f"{'='*72}")
    print(content)
    return content


async def main():
    from openai import AsyncOpenAI
    base = os.environ.get("GLM_API_BASE"); key = os.environ.get("GLM_API_KEY")
    model = os.environ.get("GLM_MODEL", "glm-5.2")
    if not key:
        print("✗ GLM_API_KEY not set"); return
    client = AsyncOpenAI(base_url=base, api_key=key)
    print(f"probe: GLM parametric knowledge of exam patterns — model={model}")
    results = {}
    for kp, desc in KPrompts:
        results[kp] = await ask(client, model, kp, desc)

    print(f"\n{'='*72}")
    print("  评估：参数知识是否够 rich 驱动设计？")
    print(f"{'='*72}")
    for kp, c in results.items():
        concrete = sum(c.count(k) for k in ["画", "求", "判断", "计算", "标注", "识别"])
        print(f"  {kp}: content={len(c)}c  具体动作词={concrete}  "
              f"→ {'✓ rich 可挖' if concrete >= 4 and len(c) > 400 else '⚠️ 偏空'}")


if __name__ == "__main__":
    asyncio.run(main())
