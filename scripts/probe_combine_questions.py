"""Probe 3: organic combination of multiple questions' examination points.

Can the model judge which past questions can be ORGANICALLY COMBINED (考察点 fused
coherently, not stacked), and design a combined question that raises difficulty /
enriches gradient?

Part A — judge combinability: which 2-3 of the 5 AVL questions fuse organically? why?
Part B — design the fused question: 考察点 merged coherently, higher K / richer gradient.

Usage:
  set -a && source /zhaoshu/llm_eduated/.env && set +a && \
  python3 scripts/probe_combine_questions.py
"""
import asyncio
import os
import sys
import time
from pathlib import Path
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 同考点(AVL插入旋转)不同侧重的题：name, 侧重角度, 题干摘要
QS = [
    ("simulation_00175", "侧重【定位失衡】", "由序列构造 AVL，找首次出现的最小不平衡子树的根（从插入点回溯找 BF=±2 节点）"),
    ("exercise_00266", "侧重【执行旋转】", "给定 AVL 树+新插入节点，执行 RL 双旋的子树重连细节（第一步右旋、第二步左旋的中间节点归属）"),
    ("exercise_00261", "侧重【高度/结点边界】", "二叉树高度 h 与结点数 n 的关系（最坏情况上界，N_h 类公式）"),
    ("exercise_00270", "侧重【性质适用】", "AVL/平衡树满足哪些 O(logn) 操作（性质/适用性判断）"),
]
QS_CTX = "\n".join(f"- {n}：{ang} — {desc}" for n, ang, desc in QS)

SYS_A = """你是命题分析者。判断【同一考点】（AVL 插入与旋转）的不同【侧重考法】能否融合成一道更丰富的单考点题。

关键区分（务必遵守）：
- ✅ 同考点不同侧重融合：都是 AVL 插入旋转，但侧重不同（定位失衡 / 判断旋转类型 / 执行旋转 / 旋转后结果如高度结点），把这些侧重融成一道题。
- ❌ 跨考点融合：把 AVL 和别的考点（如 BST 搜索、复杂度辨析）拼一起——这是练习题风格，考研/期末是单题单考点，不要。
- ❌ 堆计算量：单纯增加操作步数不算高明融合。
融合的好处：单题单考点，但多个侧重角度（定位→判断→执行→结果），考察更全面、梯度更丰富。"""

SYS_B = """你是出题设计者。把【同一考点（AVL 插入旋转）的不同侧重】融合成一道单考点的丰富综合题。
- 必须同考点（AVL 插入旋转），不跨考点。
- 融合的是【侧重角度】：如一道题里依次问 定位失衡 → 判断旋转类型 → 执行旋转 → 旋转后高度/结点。每个侧重来自不同往年题的角度。
- 连贯：前一个侧重（如定位失衡）的结果自然引出后一个（如判断类型、执行、结果）。
- 不是堆计算量：是单考点多角度，考察更全面。
- 符号化题干（参数占位，不写算出的具体答案）；输出 === question.md ===，标注每个子问融合了哪个侧重。"""

ASK_A = """考点：平衡二叉树 AVL 的插入与旋转（单一考点）

【往年同考点的不同侧重题】
{qs}

任务：判断哪些【侧重角度】可以融合成一道更丰富的单考点 AVL 题（同考点、不跨考点、不堆计算量）：
1. 选哪几个侧重融合
2. 这些侧重怎么按逻辑顺序串起来（如 定位→判断→执行→结果）
3. 融合后单题更丰富在哪（考察更全面/梯度更好），不是堆计算量"""

ASK_B = """基于上面的同考点侧重融合判断，设计一道【单考点（AVL插入旋转）、多侧重】的丰富综合题：

【融合方案】（来自 Part A）
{a_out}

任务：
1. 设计单考点多侧重题：子问链，每个子问标注融合了哪个侧重（定位/判断/执行/结果），前后怎么连贯
2. 说明这题是单考点（AVL 插入旋转）但角度丰富，不是跨考点、不是堆计算量
3. 符号化题干（参数占位）
输出 === question.md === + 设计说明（融合逻辑）。"""


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
    print(content[:2000])
    return content


async def main():
    base = os.environ.get("GLM_API_BASE"); key = os.environ.get("GLM_API_KEY")
    model = os.environ.get("GLM_MODEL", "glm-5.2")
    if not key:
        print("✗ GLM_API_KEY not set"); return
    client = AsyncOpenAI(base_url=base, api_key=key)

    print("=" * 72)
    print(f"  combine-questions probe — model={model}")
    print(f"  Part A: 判断哪些题可有机组合 | Part B: 设计融合题")
    print("=" * 72)

    a_out = await call(client, model, SYS_A, ASK_A.replace("{qs}", QS_CTX), "A_判断侧重融合")
    b_out = await call(client, model, SYS_B, ASK_B.replace("{a_out}", a_out[:1500]), "B_设计单考点多侧重题")

    # 评估
    n_emph = sum(1 for n, _, _ in QS if n in a_out)
    fusion_words = sum(1 for k in ["定位", "判断", "执行", "结果", "侧重", "角度", "连贯"] if k in b_out)
    # 同考点检查：b_out 不应跨考点（不应把 AVL 和 BST搜索/复杂度 拼一起）
    cross_kp = any(k in b_out for k in ["BST 搜索", "最邻近", "复杂度辨析", "中序遍历搜索", "剪枝搜索"])
    has_q = "=== question.md ===" in b_out or "## 题干" in b_out
    print(f"\n{'='*72}")
    print(f"  评估")
    print(f"  Part A 涉及侧重数: {n_emph}/4（同考点不同侧重）")
    print(f"  Part B 侧重融合词: {fusion_words} 个 {'✓ 多角度' if fusion_words >= 3 else '⚠️ 角度单一'}")
    print(f"  Part B 同考点（非跨考点）: {'✓' if not cross_kp else '⚠️ 仍跨考点融合'}")
    print(f"  Part B 产出题骨架: {'✓' if has_q else '✗'}")


if __name__ == "__main__":
    asyncio.run(main())
