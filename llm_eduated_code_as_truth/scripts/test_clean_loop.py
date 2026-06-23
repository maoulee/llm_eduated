#!/usr/bin/env python3
"""决定性实验：干净 agent loop vs DocScheduler(write_gen)。

控制变量（完全相同）：
- 模型：GLM-5.2（线上，enable_thinking=ON）
- 题：补码除法（X=-0.1011, Y=0.1101）—— 历次过载的同款
- skill：func_model（解法封装成函数）

唯一变量 = loop 行为：
- DocScheduler(write_gen)：no_output→丢弃该轮 reasoning→trim→retry；中间态走 intermediate_text 阈值
- clean loop（本脚本）：保留每轮 reasoning_content 原样回传；不 trim；不丢；
  哪怕单轮 content=0（思考占满），下一轮仍带着上一轮思考继续——模拟"真正连续思考的 agent"

判定标准：
- 能否产出 gen.py（核心）
- reasoning 累计峰值（单轮 vs 跨轮累计）
- gen.py 是否 exec 通过（exec_file）

跑法：python scripts/test_clean_loop.py
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# 复用线上配置（GLM-5.2，coding 接口）
os.environ.setdefault("GLM_MODEL", "glm-5.2")
os.environ.setdefault("GLM_API_BASE", "https://open.bigmodel.cn/api/coding/paas/v4/")
os.environ.setdefault("GLM_API_KEY", "d6f4904cd7d7462c8e82c5c4e097bebe.hQln0yGBA2muYhJU")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core_new.llm_gateway import get_gateway  # noqa: E402

# ── 固定输入（与历史测试同款补码除法题 + func_model skill）──────────────
QUESTION = """# 补码加减交替法除法（10分）

## 题干

设 $X = -0.1011$，$Y = 0.1101$，$X$ 和 $Y$ 均为定点小数，采用补码表示（含双符号位，即模4补码）。请回答：

**（1）**（3分）写出 $[X]_补$ 和 $[Y]_补$，并求出 $[-Y]_补$。说明补码加减交替法除法的初始状态。

**（2）**（5分）用**补码加减交替法（不恢复余数法）**计算 $[X \\div Y]_补$，写出每一步的余数、商位及操作说明（包括加减操作和移位操作）。

**（3）**（2分）给出最终的商 $[Q]_补$ 和余数 $[R]_补$，并说明是否需要对商的末位进行修正。
"""

SKILL = (ROOT / "core_new/doc_pipeline/skills/func_model/SKILL.md").read_text(encoding="utf-8")

SYSTEM = (
    "你是建模代码编写者。读题干 → 写 gen.py（把当前题的解法封装成 def solve(参数)→答案，"
    "调用取值、print 关键步骤）→ 就地 exec 验证能跑。只建当前题，不写 solution。"
    "算法版本已在「算法标准」段钉死，照此实现，勿自行选择版本、勿重新推导算法、勿在思考里手算验证。"
)

MAX_ROUNDS = 12          # 消歧后应能少轮完成，留够上限
MAX_TOKENS = 32000       # 不人为截断——测"消歧后到底要不要深想"
WS = Path("/tmp/clean_loop_test")


async def run_clean_loop():
    """干净 agent loop：保留每轮 reasoning，不 trim，连续工作直到写出 gen.py + exec 通过。"""
    from core_new.agent_runtime.registry import ToolRegistry
    from core_new.agent_tools import ToolExecutor
    from core_new.doc_pipeline.exec_file_tool import ExecFileTool
    from core_new.doc_pipeline.write_file_tool import WriteFileTool
    from core_new.doc_pipeline.read_file_tool import ReadFileTool
    from core_new.doc_pipeline.edit_file_tool import EditFileTool
    from core_new.doc_pipeline.config import PYTHON_EXEC_TIMEOUT

    WS.mkdir(parents=True, exist_ok=True)
    gen_path = WS / "gen.py"

    # 清掉旧产物
    for f in WS.glob("*"):
        f.unlink()

    registry = ToolRegistry()
    registry.register(WriteFileTool(workspace=WS))
    registry.register(EditFileTool(workspace=WS))
    registry.register(ReadFileTool(workspace=WS, read_roots=[ROOT / "data"]))
    registry.register(ExecFileTool(workspace=WS, timeout=PYTHON_EXEC_TIMEOUT))
    tool_names = ["write_file", "edit_file", "read_file", "exec_file"]
    executor = ToolExecutor([registry.get(n) for n in tool_names])
    openai_tools = [registry.get(n).to_openai_tool() for n in tool_names]

    gateway = get_gateway("glm5.1")  # provider key=glm5.1, 但 GLM_MODEL=glm-5.2 → 实际跑 5.2
    print(f"模型: {getattr(gateway._provider, 'model_path', '?')} | thinking=ON | max_tokens={MAX_TOKENS}", flush=True)
    print(f"workspace: {WS}\n", flush=True)

    # ── 注入消歧信息（模拟 read_file 拉到的参考题算法标准）──
    DISAMBIG = Path("/tmp/disambig_ref.md").read_text(encoding="utf-8")

    full_task = (
        f"## 任务\n读下面题干，写 gen.py（按工作规范：解法封装成 def solve(X, Y)，调用取值，print PARAMS/REASONING/ANSWER），"
        f"然后 exec_file 验证能跑。\n\n"
        f"## 题干\n{QUESTION}\n\n"
        f"## 工作规范\n{SKILL}\n\n"
        f"## 算法标准（设计者检索到的参考题解法，权威无歧义，照此版本实现）\n{DISAMBIG}\n\n"
        f"## 工具\n用 write_file(path=\"gen.py\", content=...) 写代码；用 exec_file(path=\"gen.py\") 跑它。"
    )

    # 干净 loop 的核心：messages 累积，每一轮 assistant 消息都原样带回 reasoning_content
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": full_task},
    ]

    peak_reasoning = 0
    total_reasoning = 0
    start = time.time()
    gen_written = False
    gen_exec_ok = None  # None=没跑 / True=通过 / False=失败

    for rnd in range(1, MAX_ROUNDS + 1):
        t0 = time.time()
        try:
            raw = await gateway.stream_chat(
                messages,
                max_tokens=MAX_TOKENS,
                enable_thinking=True,
                thinking_budget=None,  # 线上忽略，但不报错
                tools=openai_tools,
                tool_choice="auto",
                sampling_overrides={"temperature": 0.2, "top_p": 0.9},
            )
        except Exception as exc:
            print(f"[r{rnd}] ✗ stream 异常: {type(exc).__name__}: {str(exc)[:200]}", flush=True)
            # 干净 loop 也容错：重试一次（不 trim 不丢历史）
            await asyncio.sleep(2)
            continue

        tool_calls = raw.get("tool_calls")
        content = raw.get("content", "")
        reasoning = raw.get("reasoning") or raw.get("reasoning_content") or ""
        finish = raw.get("finish_reason")

        rlen = len(reasoning)
        clen = len(content or "")
        peak_reasoning = max(peak_reasoning, rlen)
        total_reasoning += rlen
        dt = time.time() - t0
        tcs = [tc["function"]["name"] for tc in tool_calls] if tool_calls else []
        print(f"[r{rnd}] {dt:.0f}s reasoning={rlen} content={clen} finish={finish} tools={tcs}", flush=True)

        # ── 落地完整 reasoning + content 供事后分析（为什么这么久/是否重复）──
        (WS / f"r{rnd}_reasoning.txt").write_text(reasoning, encoding="utf-8")
        (WS / f"r{rnd}_content.txt").write_text(content or "(empty)", encoding="utf-8")

        # ── 干净 loop 核心：无论哪种输出，都保留 reasoning 回传 ──
        assistant_msg = {"role": "assistant", "content": content or None}
        if reasoning:
            assistant_msg["reasoning_content"] = reasoning
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        messages.append(assistant_msg)

        # 没 tool_call：要么是纯文本（让模型继续），要么是空（思考占满）
        if not tool_calls:
            if clen > 50:
                # 有正文但没工具调用 → 提示一下该写文件了，但不 trim、不丢思考
                messages.append({"role": "user", "content": "请用 write_file(path=\"gen.py\") 写出代码并 exec_file 验证。"})
            else:
                # content≈0（思考占满）→ 干净 loop 的关键：温和提示继续，不丢思考
                messages.append({"role": "user", "content": "继续。完成思考后用 write_file 写 gen.py。"})
            continue

        # 有 tool_call → 执行
        wrote_gen = False
        exec_result_preview = ""
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            args_raw = tc["function"]["arguments"]
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except (json.JSONDecodeError, ValueError):
                args = {}
            print(f"[r{rnd}] 执行 {fn_name}({str(args)[:80]})", flush=True)
            result_str = await executor.execute(fn_name, args)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result_str})

            if fn_name == "write_file" and args.get("path", "").endswith("gen.py"):
                try:
                    p = json.loads(result_str)
                    if p.get("ok") and gen_path.exists():
                        wrote_gen = True
                        gen_written = True
                except (json.JSONDecodeError, ValueError):
                    pass
            if fn_name == "exec_file" and args.get("path", "").endswith("gen.py"):
                exec_result_preview = result_str[:300]
                try:
                    p = json.loads(result_str)
                    gen_exec_ok = bool(p.get("ok") and p.get("exit_code") == 0)
                except (json.JSONDecodeError, ValueError):
                    gen_exec_ok = False

        # 写完 gen.py 且 exec 过了 → 成功
        if gen_written and gen_exec_ok:
            print(f"\n[r{rnd}] ✓✓ 成功：gen.py 已写 + exec 通过", flush=True)
            break
        if gen_written and gen_exec_ok is None:
            # 写了但还没 exec，下一轮让它 exec
            messages.append({"role": "user", "content": "gen.py 已写。现在用 exec_file(path=\"gen.py\") 验证它。"})
        if gen_written and gen_exec_ok is False:
            print(f"[r{rnd}] exec 失败，预览: {exec_result_preview.replace(chr(10), ' | ')}", flush=True)
            messages.append({"role": "user", "content": "exec 报错，请 edit_file 修正 gen.py 后重新 exec_file。"})

    elapsed = time.time() - start
    print("\n" + "=" * 60, flush=True)
    print(f"耗时 {elapsed:.0f}s | 轮数 {min(rnd, MAX_ROUNDS)} | 单轮reasoning峰值 {peak_reasoning} | 累计 {total_reasoning}", flush=True)
    print(f"gen.py 产出: {'✓' if gen_written else '✗'}", flush=True)
    print(f"exec 通过: {'✓' if gen_exec_ok else '✗' if gen_exec_ok is False else '未跑'}", flush=True)
    if gen_path.exists():
        lines = gen_path.read_text(encoding="utf-8").count("\n")
        print(f"gen.py: {lines} 行", flush=True)

    return {"gen_written": gen_written, "gen_exec_ok": gen_exec_ok,
            "peak_reasoning": peak_reasoning, "total_reasoning": total_reasoning,
            "rounds": min(rnd, MAX_ROUNDS), "elapsed": elapsed}


if __name__ == "__main__":
    asyncio.run(run_clean_loop())
