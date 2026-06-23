"""Integrated end-to-end test: the validated design pattern, 3 types, measure speedup.

Combines everything validated into ONE design flow:
  1. retrieve same-TYPE past questions
  2. analyze skeleton (from past, NOT invent)
  3. select/adjust skeleton by K-radar shape (+ same-考点 emphasis fusion if rich)
  4. symbolic framework (params as symbols, no computed values)
  5. DAG solve.py (parametrized computation path, model gives initial params)

Run 3 types. Compare reasoning/time vs original (comprehensive = 25k, failed).

Usage:
  set -a && source /zhaoshu/llm_eduated/.env && set +a && \
  python3 scripts/probe_integrated_pipeline.py
"""
import asyncio
import os
import re
import sys
import time
import subprocess
from pathlib import Path
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
QEXP = "/zhaoshu/llm_eduated/data/question_experiences"


def retrieve(kp_terms, type_filter):
    """grep same-type past questions, return top snippets."""
    try:
        files = subprocess.run(["grep", "-rl"] + kp_terms + [QEXP],
                               capture_output=True, text=True, timeout=10).stdout.strip().split("\n")
    except Exception:
        files = []
    out = []
    for f in [f for f in files if f]:
        try:
            t = Path(f).read_text(encoding="utf-8")
            if type_filter in t:  # same type
                head = t[:700]
                out.append(f"--- {Path(f).name} ---\n{head}")
                if len(out) >= 3:
                    break
        except Exception:
            pass
    return "\n\n".join(out) if out else "(无同类型题)"


SYS = """你是出题设计者。用【验证过的模式】设计一道题——按模式执行，不发明、不脑内模拟。

模式（严格按序）：
1. 分析给的往年【同题型】题的结构（骨架）：提炼子问组织、考察意图递进、设问方式
2. 按目标 K-雷达形状 选/调骨架：
   - K1 主导→概念辨析骨架；K3 主导→多步串行推演骨架；K4 主导→陷阱辨析骨架
   - 同考点不同侧重可融合（定位→判断→执行→结果），但单题单考点，不跨考点
3. 套骨架 + 符号参数 → 题干（符号占位，不算具体值）
4. DAG solve.py：把考察形式写成参数化代码，计算路径固定（有向无环图），你给初始参数，代码算出全部参数+结果+推理
5. 禁止脑内模拟（不写"插入30→BF=2→旋转"）；所有数值由 solve.py 算

输出 === question.md ===（符号题干）和 === solve.py ===（参数化 DAG 代码）。"""


def ask(qtype, kradar, score, past):
    return f"""考点：平衡二叉树 AVL（插入与旋转）
题型：{qtype}
目标 K-雷达：{kradar}
分值：{score}

【往年同题型题（骨架分析素材）】
{past}

按上面的【验证过的模式】设计。先分析骨架→按K雷达选/调→符号题干→DAG solve.py。"""


TYPES = [
    ("T1_简单选择", "选择题（4选1）", "K1=3,K2=2,K3=1,K4=2,K5=1（K1主导：概念辨析/单步）", "2 分",
     ["AVL", "平衡二叉树"], "选择题"),
    ("T2_简单综合", "综合应用题", "K1=3,K2=2,K3=3,K4=2,K5=1（K3中等：少量串行推演）", "8 分",
     ["AVL", "平衡二叉树", "旋转"], "综合题"),
    ("T3_正常综合", "综合应用题", "K1=3,K2=2,K3=4,K4=4,K5=1（K3-K4双高：多步串行+陷阱）", "13 分",
     ["AVL", "平衡二叉树", "旋转"], "综合题"),
]


async def run_type(client, model, label, qtype, kradar, score, kp_terms, tf):
    past = retrieve(kp_terms, tf)
    print(f"\n{'='*72}\n  [{label}] {qtype} | {kradar}\n  同题型往年题: {past[:60].replace(chr(10),' ')}...\n{'='*72}")
    messages = [{"role": "system", "content": SYS}, {"role": "user", "content": ask(qtype, kradar, score, past)}]
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
    print(f"  {elapsed:.1f}s | reasoning {len(reasoning)}c | content {len(content)}c | finish {resp.choices[0].finish_reason} | 模拟 {sim}")
    print(f"  question.md {'✓' if has_q else '✗'} | solve.py {'✓' if has_py else '✗'}")
    print(f"  ── 输出前 600 字符 ──\n{content[:600]}")
    return {"label": label, "time": elapsed, "reasoning": len(reasoning),
            "has_q": has_q, "has_py": has_py, "sim": sim}


async def main():
    base = os.environ.get("GLM_API_BASE"); key = os.environ.get("GLM_API_KEY")
    model = os.environ.get("GLM_MODEL", "glm-5.2")
    if not key:
        print("✗ GLM_API_KEY not set"); return
    client = AsyncOpenAI(base_url=base, api_key=key)
    print(f"integrated pipeline probe — model={model} | 验证过的模式，3 类型，测提速")
    results = []
    for label, qtype, kradar, score, kp, tf in TYPES:
        results.append(await run_type(client, model, label, qtype, kradar, score, kp, tf))

    print(f"\n{'='*72}\n  对比（vs 原始：综合题 25k reasoning 失败）\n{'='*72}")
    print(f"  {'类型':14s} {'time':>7s} {'reasoning':>9s} {'模拟':>4s} {'产出':>6s}")
    for r in results:
        prod = "✓" if (r["has_q"] and r["has_py"]) else "✗"
        print(f"  {r['label']:14s} {r['time']:6.1f}s {r['reasoning']:9d}c {r['sim']:4d}   {prod}")
    t3 = next((r for r in results if r["label"] == "T3_正常综合"), None)
    if t3:
        win = t3["reasoning"] < 10000 and t3["has_q"] and t3["has_py"]
        print(f"\n  T3 正常综合: {'✓ 提速且成功（<10k reasoning）' if win else '✗ 仍过度/失败'}")


if __name__ == "__main__":
    asyncio.run(main())
