"""Probe: independent-agent split vs combined — does splitting reduce wasteful thinking?

For the comprehensive K3-K4 case (combined agent = 25k reasoning, failed to produce):
  SPLIT:
    Agent A (考察形式): 考点 + 难度 → 选定考察形式（窄任务，不设计题目）
    Agent B (设计求解): 考点 + 选定形式 → 符号题干 + solve.py（窄任务，形式已定）
  Compare: A.reasoning + B.reasoning vs combined 25k; does each succeed?

Usage:
  set -a && source /zhaoshu/llm_eduated/.env && set +a && \
  python3 scripts/probe_split_agents.py
"""
import asyncio
import os
import re
import sys
import time
import json
import subprocess
from pathlib import Path
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KP = "平衡二叉树 AVL（插入与旋转）"
K_TARGET = "K3-K4（较难：多步串行推演 + 陷阱辨析）"
QTYPE = "综合应用题（13分）"

SYS_A = """你是考点分析者。只做一件事：为给定考点+难度，选定【考察形式】。
基于你的命题经验 + 知识点结构，列出该考点常见考察形式（3-5种），判断每种对应的难度档，选定匹配目标难度的形式。
只输出：考察形式列表 + 难度对应 + 选定形式及理由。不设计题目、不写题干、不算数值。聚焦，快速判断。"""

SYS_B = """你是出题设计者。考察形式已由上游定好，你只基于该形式设计题干+求解。
任务：
1. 按给定考察形式构建题干（符号占位参数，如序列 S=[s₁..sₙ]，不写算出的具体答案）
2. 写 solve.py（实例化参数 + 算正确答案 + 算干扰值），print 各值
纪律：考察形式已定，不要再纠结选什么形式。禁止脑内模拟（不写"插入30→BF=2→旋转"）。数值由 solve.py 算。
输出用 === question.md === 和 === solve.py === 分隔。"""

ASK_A = f"""考点：{KP}
目标难度：{K_TARGET}
题型：{QTYPE}

请选定匹配该难度的考察形式（只做这一步）。"""

def ask_b(form_output):
    return f"""考点：{KP}
目标难度：{K_TARGET}
题型：{QTYPE}

【上游选定的考察形式】
{form_output}

请基于此形式设计题干 + solve.py（考察形式已定，直接设计）。"""


async def call(client, model, sys_p, user_p, label):
    t0 = time.time()
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": sys_p}, {"role": "user", "content": user_p}],
        max_tokens=6000, extra_body={"thinking": {"type": "enabled"}})
    elapsed = time.time() - t0
    msg = resp.choices[0].message
    content = msg.content or ""
    reasoning = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None) or ""
    print(f"\n  [{label}] {elapsed:.1f}s | reasoning {len(reasoning)}c | content {len(content)}c | finish {resp.choices[0].finish_reason}")
    print(f"  ── {label} 输出（前 1000 字符）──")
    print(content[:1000])
    return content, len(reasoning), elapsed


async def main():
    base = os.environ.get("GLM_API_BASE"); key = os.environ.get("GLM_API_KEY")
    model = os.environ.get("GLM_MODEL", "glm-5.2")
    if not key:
        print("✗ GLM_API_KEY not set"); return
    client = AsyncOpenAI(base_url=base, api_key=key)

    print("=" * 72)
    print(f"  split-agents probe — 综合 K3-K4 | model={model}")
    print(f"  对比：合并单 agent = 25k reasoning 失败；拆分 = A(考察形式)+B(设计)")
    print("=" * 72)

    # Agent A: 考察形式
    form_out, ra, ta = await call(client, model, SYS_A, ASK_A, "A_考察形式")

    # Agent B: 设计求解（用 A 的输出）
    design_out, rb, tb = await call(client, model, SYS_B, ask_b(form_out), "B_设计求解")

    # 评估
    sim = len(re.findall(r"[Ss]tep\s*\d|Insert\s+\d+\s*→|BF\s*=\s*-?\d|插入\s*\d+\s*[→后]", design_out))
    has_q = "=== question.md ===" in design_out or "## 题干" in design_out
    has_py = "=== solve.py ===" in design_out or "def " in design_out
    total_r = ra + rb
    total_t = ta + tb

    print(f"\n{'='*72}")
    print("  对比结果")
    print(f"{'='*72}")
    print(f"  合并单 agent:        reasoning ~25000c | 失败（无产出）")
    print(f"  拆分 A(考察形式):    reasoning {ra}c | {ta:.1f}s")
    print(f"  拆分 B(设计求解):    reasoning {rb}c | {tb:.1f}s")
    print(f"  拆分合计:            reasoning {total_r}c | {total_t:.1f}s")
    print(f"  B 产出 question.md: {'✓' if has_q else '✗'} | solve.py: {'✓' if has_py else '✗'} | 脑内模拟: {sim}")
    win = total_r < 15000 and has_q and has_py
    print(f"\n  → {'✓ 拆分更优：总 reasoning < 合并，且成功产出' if win else '✗ 拆分未明显改善'}")


if __name__ == "__main__":
    asyncio.run(main())
