"""Probe: autonomous design agent — only type+difficulty given, agent self-derives 考察形式.

NO hardcoded 考察形式 / reasoning steps / structure (unlike probe_direct_design which
pre-fed "构造作图标旋转" + RR+RL). The agent gets ONLY: 考点 + 题型 + 目标难度 + 分值.
It must autonomously use tools (read KG, search questions) to derive how to test, then design.

Tests 3 types to see if difficulty/style autonomously varies:
  1. 简单选择  (选择题, K1-K2, 2分)
  2. 简单综合  (综合题, K2-K3, 8分)
  3. 正常综合  (综合题, K3-K4, 13分)

Agentic tool loop (GLM tool_calls): read_kg → search_questions → ... → design.

Usage:
  set -a && source /zhaoshu/llm_eduated/.env && set +a && \
  python3 scripts/probe_autonomous_design.py
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

TOOLS = [
    {"type": "function", "function": {
        "name": "read_kg", "description": "读取指定科目的知识点图谱(KG)，理解知识点的结构、子知识点、边界。",
        "parameters": {"type": "object", "properties": {
            "subject": {"type": "string", "description": "科目，如 数据结构"}},
            "required": ["subject"]}}},
    {"type": "function", "function": {
        "name": "search_questions", "description": "检索往年/练习题目经验（含考察模式、陷阱、K值标注）。用于参考往年怎么考。",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "array", "items": {"type": "string"}, "description": "检索关键词"},
            "subject": {"type": "string", "description": "科目"}},
            "required": ["query"]}}},
]

KG_FILE = {"数据结构": "data/kg/data_structure.md"}


def exec_tool(name, args):
    try:
        if name == "read_kg":
            subj = args.get("subject", "数据结构")
            p = Path(KG_FILE.get(subj, "data/kg/data_structure.md"))
            if not p.exists():
                return f"(KG 文件不存在: {p})"
            txt = p.read_text(encoding="utf-8")
            # 截取 AVL/平衡 相关段落 + 总览
            if "平衡" in txt or "AVL" in txt:
                idx = txt.find("平衡")
                seg = txt[max(0, idx-200):idx+2000] if idx > 0 else txt[:3000]
                return f"[KG {subj} 平衡二叉树相关段落]\n{seg}\n...(KG 共 {len(txt)} 字符)"
            return f"[KG {subj} 前 3000 字符]\n{txt[:3000]}"
        if name == "search_questions":
            q = args.get("query", [])
            if isinstance(q, str):
                q = [q]
            subj = args.get("subject", "")
            # grep question_experiences
            try:
                cmd = ["grep", "-rl"] + q + ["data/question_experiences"]
                files = subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip().split("\n")
                files = [f for f in files if f][:8]
            except Exception:
                files = []
            if not files:
                return f"(未检索到含 {q} 的题目)"
            snippets = []
            for f in files:
                t = Path(f).read_text(encoding="utf-8")[:600]
                snippets.append(f"--- {Path(f).name} ---\n{t}")
            return f"检索到 {len(files)} 道相关题:\n" + "\n\n".join(snippets)
    except Exception as e:
        return f"(工具执行错误: {e})"
    return "(未知工具)"


SYS = """你是出题设计者。你只做以下 4 步（严格按序，每步聚焦，不要展开成大推理链）：

Step 1 — 锚定知识点 + 列考察形式：
  read_kg 读 AVL 知识点结构。然后基于 KG + 你的命题经验，列出"AVL 的常见考察形式"（3-5 种，每种一句话怎么考）。

Step 2 — 考察形式 ↔ 难度对应（核心）：
  对每种形式判断它对应什么难度档：K1-K2（简单：单步/概念）/ K2-K3（中等：少量串行）/ K3-K4（较难：多步+陷阱）。
  根据【目标难度】选定匹配的形式。说明为什么这个形式对应目标难度。

Step 3 — 构建符号题干：
  用选定形式构建题干 + 子问/选项结构。参数用符号占位（如关键字序列 S=[s₁..sₙ]），
  只描述"考什么结构"，不写算出的具体答案/具体树形/具体旋转结果。

Step 4 — 交付 solve：
  写 solve.py（实例化参数 + 算正确答案 + 算干扰值），print 各值。solve.py 负责所有数值计算。

纪律（防止过度思考）：
- 这是 4 个独立聚焦步骤，不是一个大推理。Step1 列形式、Step2 判难度、Step3 套符号、Step4 写代码，每步做完即止。
- 禁止脑内模拟：不写"插入30→...BF=2→旋转"这类带具体数值的逐步推演。具体值由 solve.py 算。
- 难度对应靠判断（这个形式是单步还是多步、有无陷阱），不是靠推演验证。
- 最终输出用 === question.md === 和 === solve.py === 分隔。"""


def user_prompt(kp, qtype, k_target, score):
    return f"""【设计任务】
考点：{kp}
题型：{qtype}
目标难度：{k_target}
分值：{score} 分

请自主决策考察形式并设计题目。先调用工具（read_kg / search_questions）了解知识点和往年考法，再设计。
注意：我只给了考点+题型+难度，没有给考察形式——由你基于知识和经验自己定。"""


TYPES = [
    ("T1_简单选择", "平衡二叉树 AVL（插入与旋转）", "选择题（单选，4选1）", "K1-K2（基础：单步判断或简单概念辨析）", "2 分"),
    ("T2_简单综合", "平衡二叉树 AVL（插入与旋转）", "综合应用题", "K2-K3（中等：少量串行推演）", "8 分"),
    ("T3_正常综合", "平衡二叉树 AVL（插入与旋转）", "综合应用题", "K3-K4（较难：多步串行推演 + 陷阱辨析）", "13 分"),
]


async def run_type(client, model, label, kp, qtype, k_target, score):
    print(f"\n{'='*72}\n  [{label}] {qtype} | {k_target} | {score}\n{'='*72}")
    messages = [{"role": "system", "content": SYS},
                {"role": "user", "content": user_prompt(kp, qtype, k_target, score)}]
    tool_log = []
    total_reasoning = 0
    t0 = time.time()
    for rnd in range(8):
        resp = await client.chat.completions.create(
            model=model, messages=messages, tools=TOOLS,
            max_tokens=8000, extra_body={"thinking": {"type": "enabled"}})
        msg = resp.choices[0].message
        reasoning = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None) or ""
        total_reasoning += len(reasoning)
        # record message (strip reasoning for next turn, keep content+tool_calls)
        m = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            m["tool_calls"] = [{"id": tc.id, "type": "function",
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                               for tc in msg.tool_calls]
        messages.append(m)
        if not msg.tool_calls:
            final = msg.content or ""
            break
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            res = exec_tool(tc.function.name, args)
            tool_log.append(f"{tc.function.name}({args}) → {len(res)}c")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": res})
    else:
        final = "(达到最大轮次未出最终设计)"
    elapsed = time.time() - t0

    sim = len(re.findall(r"[Ss]tep\s*\d|Insert\s+\d+\s*→|BF\s*=\s*-?\d|插入\s*\d+\s*[→后]", final))
    has_q = "=== question.md ===" in final or "## 题干" in final
    has_py = "=== solve.py ===" in final or "def " in final
    # extract 考察形式 the agent self-derived (from design notes)
    form_match = re.search(r"考察(?:形式|模式)[：:]\s*([^\n]+)", final)

    print(f"  工具调用: {tool_log}")
    print(f"  耗时 {elapsed:.1f}s | 累计 reasoning {total_reasoning}c | 脑内模拟痕迹 {sim}")
    print(f"  自定考察形式: {form_match.group(1) if form_match else '(未明确标注)'}")
    print(f"  产出 question.md: {'✓' if has_q else '✗'} | solve.py: {'✓' if has_py else '✗'}")
    print(f"  ── 设计输出（前 1800 字符）──")
    print(final[:1800])
    return {"label": label, "qtype": qtype, "k": k_target, "tools": tool_log,
            "reasoning": total_reasoning, "sim": sim, "form": form_match.group(1) if form_match else "",
            "has_q": has_q, "has_py": has_py, "time": elapsed, "final_head": final[:120]}


async def main():
    base = os.environ.get("GLM_API_BASE"); key = os.environ.get("GLM_API_KEY")
    model = os.environ.get("GLM_MODEL", "glm-5.2")
    if not key:
        print("✗ GLM_API_KEY not set"); return
    client = AsyncOpenAI(base_url=base, api_key=key)
    print(f"autonomous design probe — model={model} | 只给题型+难度，agent 自主挖考察形式")

    results = []
    for label, kp, qtype, k_target, score in TYPES:
        results.append(await run_type(client, model, label, kp, qtype, k_target, score))

    print(f"\n{'='*72}\n  对比：难度是否自主驱动设计风格差异？\n{'='*72}")
    print(f"  {'类型':14s} {'工具':20s} {'reasoning':>9s} {'模拟':>4s} {'自定考察形式'}")
    for r in results:
        tools_short = ",".join(t.split("(")[0] for t in r["tools"])[:20] or "(无工具)"
        print(f"  {r['label']:14s} {tools_short:20s} {r['reasoning']:9d}c {r['sim']:4d}  {r['form'][:40]}")
    print(f"\n  风格是否随难度分化？看三个 '自定考察形式' + reasoning 是否递增（K越高推理越多）")


if __name__ == "__main__":
    asyncio.run(main())
