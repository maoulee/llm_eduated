"""Probe: direct-design agent — strong model + rich context, no multi-layer split.

Tests the hypothesis: for a strong parametric model (GLM-5.2), feeding
(考点 + related past questions + 考察形式/难度锚定) DIRECTLY to one design agent
produces a good question+solve.py WITHOUT the lossy aggregate→design_card→question
decomposition (which caused 56k-token mental simulation).

Compares: direct-design (this probe) vs the decomposed pipeline (56k over-think).

Usage:
  set -a && source /zhaoshu/llm_eduated/.env && set +a && \
  python3 scripts/probe_direct_design.py
"""
import asyncio
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Feed 2 real AVL question experiences (rich: 考察模式/陷阱/K雷达)
RELATED = []
for fn in ["exercise_00272.md", "simulation_00176.md"]:
    p = Path(f"data/question_experiences/{fn}")
    if p.exists():
        RELATED.append(f"--- 往年题：{fn} ---\n" + p.read_text(encoding="utf-8")[:1500])
RELATED_CTX = "\n\n".join(RELATED) if RELATED else "(无往年题)"

SYS = """你是资深 408 命题专家兼出题者。你直接设计一道完整题目，不分阶段。
核心纪律（符号化设计，禁脑内模拟）：
- 用符号/结构设计，不代入具体数值心算。如"设计触发 RR+LR 双旋的插入序列"，不算具体树形/BF。
- 禁止逐步模拟（不写"Step1: Insert 30 → tree: 30"这类带数值的推演）。具体值由 solve.py 算。
- 你只定结构意图 + 写 solve.py（用占位参数，代码算具体值）。"""

ASK = """考点：平衡二叉树 AVL 的插入与旋转
难度锚定：K3-K4（多步串行推演 + 旋转类型辨析）
题型：综合应用题（8分，含 3-4 个串行子问）

【参考】该考点常见考察形式（基于命题经验）：
- 构造作图：给定插入序列，画出每次插入后的 AVL 树并标注旋转类型（LL/RR/LR/RL）
- 旋转类型判断：给定树+新插入位置，判断引发何种旋转
- 最少结点公式推导：N_h = N_{h-1}+N_{h-2}+1
- 算法设计：补全左旋/右旋指针操作
典型陷阱：最小不平衡子树定位错、LR/RL 误判、BF 更新漏算上层

【参考往年题】
{related}

【任务】设计一道 AVL 综合题的【框架 + 计算逻辑】，输出两部分：
1. question.md：题干 + 3-4 个串行子问 + 设计说明。题干用【符号占位】描述参数结构（如"关键字序列 S = [s₁, s₂, ..., sₙ]，其中 s_k 的插入触发旋转"），**不在题干里写算出的具体答案/具体树形/具体旋转结果**——那些是 solve.py 算出来的。题干只描述"考什么结构"。
2. solve.py：参数实例化（由你选定一组具体关键字值）+ 正确算法（AVL 插入模拟，计算每次旋转类型/最终树形/各子问答案）+ 错误算法（产生干扰）。print 各子问正确值 + 干扰值。

要求（核心纪律）：
- 设计阶段你只定【结构意图】：如"本题考察 RR 单旋 + LR 双旋的识别，序列前 3 个升序触发 RR，第 6 个插入触发 LR"。这是结构判断，不算数值。
- **禁止脑内模拟**：不写"Step1: 插入30→...Step2:插入20→...BF=2→旋转"这类带具体数值的逐步推演。具体树形/BF/旋转结果由 solve.py 算。
- 题干用符号占位（S=[s₁..sₙ]），具体数值（哪些关键字、算出什么树）由 solve.py 实例化+计算。
- 子问串行：(1)画出/描述插入过程中的旋转 → (2)判断某次旋转类型 → (3)求最终树高/结点数。

直接输出 question.md 内容和 solve.py 内容（用 === question.md === 和 === solve.py === 分隔）。"""


async def main():
    from openai import AsyncOpenAI
    base = os.environ.get("GLM_API_BASE"); key = os.environ.get("GLM_API_KEY")
    model = os.environ.get("GLM_MODEL", "glm-5.2")
    if not key:
        print("✗ GLM_API_KEY not set"); return
    client = AsyncOpenAI(base_url=base, api_key=key)

    print("=" * 72)
    print(f"  direct-design probe — model={model}, single agent, rich context")
    print(f"  related questions fed: {len(RELATED)}")
    print("=" * 72)

    messages = [{"role": "system", "content": SYS},
                {"role": "user", "content": ASK.replace("{related}", RELATED_CTX)}]
    t0 = time.time()
    res = await client.chat.completions.create(
        model=model, messages=messages, max_tokens=12000,
        extra_body={"thinking": {"type": "enabled"}},
    )
    elapsed = time.time() - t0
    msg = res.choices[0].message
    content = msg.content or ""
    reasoning = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None) or ""

    print(f"\n  time: {elapsed:.1f}s | reasoning: {len(reasoning)} chars | content: {len(content)} chars")
    print(f"  finish: {res.choices[0].finish_reason}")

    # Did it mentally simulate? (bad)
    sim_patterns = len(re.findall(r"[Ss]tep\s*\d|Insert\s+\d+\s*→|BF\s*=\s*-?\d|旋转后.*为根", reasoning))
    has_q = "=== question.md ===" in content or "## 题干" in content
    has_py = "=== solve.py ===" in content or "def " in content
    print(f"\n  脑内模拟痕迹（reasoning 里）: {sim_patterns} 处 {'⚠️ 仍在模拟' if sim_patterns > 3 else '✓ 基本没模拟'}")
    print(f"  产出 question.md: {'✓' if has_q else '✗'}")
    print(f"  产出 solve.py: {'✓' if has_py else '✗'}")

    print("\n  ── 输出（content，前 3000 字符）──")
    print(content[:3000])
    if len(content) > 3000:
        print(f"\n  ... (共 {len(content)} 字符)")

    print("\n" + "=" * 72)
    verdict = "✓ 强模型+rich直喂 成功" if (has_q and has_py and sim_patterns <= 3) else "✗ 仍需改进"
    print(f"  VERDICT: {verdict}")
    print(f"  对比：分解流水线 question_comp = 56868 reasoning / 失败；本探针 = {len(reasoning)} reasoning")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
