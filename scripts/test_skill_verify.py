#!/usr/bin/env python3
"""验证两个新 skill：func_model（write_gen）+ dual_review（审求解）。

手动串两步（不用 orchestrator），验证 skill 本身能用：
  步骤A: write_gen 用新 func_model skill，走真实流程：
         读 design_card → 尝试 read_file 拉参考题（补码除法无→兜底）→ 写 gen.py + VERSION 标记 → exec
  步骤B: dual_review 阶段2（审求解）：读 gen.py + solution + question → 审建模可行 + 题干合围 → review.md

判定：
  - write_gen 是否走兜底（gen.py 含 # VERSION 标记）、不崩溃、产出 gen.py + exec 通过
  - dual_review 是否产出合规 review.md（status/stage/issue_type/routing）、A/B 判定是否合理
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("GLM_MODEL", "glm-5.2")
os.environ.setdefault("GLM_API_BASE", "https://open.bigmodel.cn/api/coding/paas/v4/")
os.environ.setdefault("GLM_API_KEY", "d6f4904cd7d7462c8e82c5c4e097bebe.hQln0yGBA2muYhJU")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core_new.llm_gateway import get_gateway

WS = Path("/tmp/skill_verify")
MAX_TOKENS_GEN = 32000
MAX_TOKENS_REVIEW = 16000

QUESTION = """# 补码加减交替法除法（10分）

## 题干

设 $X = -0.1011$，$Y = 0.1101$，$X$ 和 $Y$ 均为定点小数，采用补码表示（含双符号位，即模4补码）。请回答：

**（1）**（3分）写出 $[X]_补$ 和 $[Y]_补$，并求出 $[-Y]_补$。说明补码加减交替法除法的初始状态。

**（2）**（5分）用**补码加减交替法（不恢复余数法）**计算 $[X \\div Y]_补$，写出每一步的余数、商位及操作说明（包括加减操作和移位操作）。

**（3）**（2分）给出最终的商 $[Q]_补$ 和余数 $[R]_补$，并说明是否需要对商的末位进行修正。
"""

# design_card（含空的 reference_questions，模拟补码除法无参考题 → write_gen 应走兜底）
DESIGN_CARD = """# design_card

## blueprint_contract
```yaml
slot_id: Q6
question_type: subjective
score: 10
examination_mode: 计算型——补码加减交替法除法逐步计算
primary_target_name: 补码不恢复余数法除法运算
target_difficulty: 3
k_dominant: K3
hard_constraints:
  - 被除数和除数均为定点小数
  - 必须使用补码表示
  - 必须使用加减交替法（不恢复余数法）
should_be:
  - 考察补码加减交替法除法的完整计算过程
  - 要求写出每一步的余数、商位、操作说明
should_not_be:
  - 不考察原码除法或恢复余数法
  - 不考察浮点数运算
```

## core_knowledge_intent
考察补码加减交替法除法的算法流程：符号判断、加减操作、移位、商位确定、末位修正。

## reference_questions
（无——本题算法在 question_experiences 中无对应参考题）
"""


def _setup_workspace():
    WS.mkdir(parents=True, exist_ok=True)
    for f in WS.glob("*"):
        f.unlink()
    # 写入 design_card 和 question.md（供 write_gen read_file）
    (WS / "design_card.md").write_text(DESIGN_CARD, encoding="utf-8")
    (WS / "question.md").write_text(QUESTION, encoding="utf-8")


async def _run_agent(gateway, system, user, tools_schema, executor, tool_names,
                     max_tokens, max_rounds, expected_file=None, ws=None, enable_thinking=True):
    """通用干净 agent loop：保留 reasoning、不 trim、连续工具调用直到产出 expected_file 或轮数耗尽。"""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    peak_r = 0
    for rnd in range(1, max_rounds + 1):
        t0 = time.time()
        try:
            raw = await gateway.stream_chat(
                messages, max_tokens=max_tokens, enable_thinking=enable_thinking,
                thinking_budget=None, tools=tools_schema, tool_choice="auto",
                sampling_overrides={"temperature": 0.2, "top_p": 0.9},
            )
        except Exception as exc:
            print(f"  [r{rnd}] ✗ stream 异常: {type(exc).__name__}: {str(exc)[:150]}", flush=True)
            await asyncio.sleep(2)
            continue

        tool_calls = raw.get("tool_calls")
        content = raw.get("content", "")
        reasoning = raw.get("reasoning") or raw.get("reasoning_content") or ""
        finish = raw.get("finish_reason")
        peak_r = max(peak_r, len(reasoning))
        tcs = [tc["function"]["name"] for tc in tool_calls] if tool_calls else []
        print(f"  [r{rnd}] {time.time()-t0:.0f}s reasoning={len(reasoning)} content={len(content or '')} finish={finish} tools={tcs}", flush=True)
        if reasoning:
            (ws / f"r{rnd}_reasoning.txt").write_text(reasoning, encoding="utf-8")
        if content:
            (ws / f"r{rnd}_content.txt").write_text(content, encoding="utf-8")

        assistant_msg = {"role": "assistant", "content": content or None}
        if reasoning:
            assistant_msg["reasoning_content"] = reasoning
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        messages.append(assistant_msg)

        if not tool_calls:
            if len(content or '') > 50:
                messages.append({"role": "user", "content": "请用 write_file 写出目标文件。"})
            else:
                messages.append({"role": "user", "content": "继续。完成思考后用 write_file 写出文件。"})
            continue

        wrote_expected = False
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            args_raw = tc["function"]["arguments"]
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except (json.JSONDecodeError, ValueError):
                args = {}
            result_str = await executor.execute(fn_name, args)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result_str})
            if expected_file and fn_name == "write_file" and args.get("path", "").endswith(expected_file):
                try:
                    p = json.loads(result_str)
                    if p.get("ok"):
                        wrote_expected = True
                except (json.JSONDecodeError, ValueError):
                    pass
        if wrote_expected:
            print(f"  ✓ 产出 {expected_file}", flush=True)
            break
    return peak_r


async def main():
    from core_new.agent_runtime.registry import ToolRegistry
    from core_new.agent_tools import ToolExecutor
    from core_new.doc_pipeline.exec_file_tool import ExecFileTool
    from core_new.doc_pipeline.write_file_tool import WriteFileTool
    from core_new.doc_pipeline.read_file_tool import ReadFileTool
    from core_new.doc_pipeline.edit_file_tool import EditFileTool
    from core_new.doc_pipeline.config import PYTHON_EXEC_TIMEOUT

    _setup_workspace()
    gateway = get_gateway("glm5.1")
    print(f"模型: glm-5.2 | workspace: {WS}\n", flush=True)

    # ========== 步骤A: write_gen（新 func_model skill，真实流程）==========
    FUNC_SKILL = (ROOT / "core_new/doc_pipeline/skills/func_model/SKILL.md").read_text(encoding="utf-8")
    gen_system = (
        "你是建模代码编写者。读 design_card + question.md → 写 gen.py（按工作规范）→ exec 验证。"
        "design_card 的 reference_questions 字段含前端检索的参考题路径（可能为空）。"
    )
    gen_user = (
        f"## 任务\n按工作规范写 gen.py 并 exec 验证。\n\n"
        f"## design_card（含 reference_questions）\n{DESIGN_CARD}\n\n"
        f"## question.md（题干）\n{QUESTION}\n\n"
        f"## 工作规范\n{FUNC_SKILL}\n\n"
        f"## 可读文件\ndesign_card.md 和 question.md 已在工作目录。参考题在 data/question_experiences/（若 reference_questions 给了路径就读）。"
    )
    gen_registry = ToolRegistry()
    gen_registry.register(WriteFileTool(workspace=WS))
    gen_registry.register(EditFileTool(workspace=WS))
    gen_registry.register(ReadFileTool(workspace=WS, read_roots=[ROOT / "data"]))
    gen_registry.register(ExecFileTool(workspace=WS, timeout=PYTHON_EXEC_TIMEOUT))
    gen_tool_names = ["write_file", "edit_file", "read_file", "exec_file"]
    gen_executor = ToolExecutor([gen_registry.get(n) for n in gen_tool_names])
    gen_tools_schema = [gen_registry.get(n).to_openai_tool() for n in gen_tool_names]

    print("=" * 60, flush=True)
    print("步骤A: write_gen（兜底场景，enable_thinking=False）", flush=True)
    print("=" * 60, flush=True)
    gen_start = time.time()
    gen_peak = await _run_agent(
        gateway, gen_system, gen_user, gen_tools_schema, gen_executor, gen_tool_names,
        max_tokens=MAX_TOKENS_GEN, max_rounds=12, expected_file="gen.py", ws=WS,
        enable_thinking=False,  # 兜底场景关思考：模型凭参数知识直接写码，exec 验证
    )
    gen_elapsed = time.time() - gen_start

    gen_path = WS / "gen.py"
    gen_ok = gen_path.exists()
    has_version = gen_ok and "# VERSION" in gen_path.read_text(encoding="utf-8")
    print(f"\n>>> write_gen 结果: 耗时{gen_elapsed:.0f}s | reasoning峰值{gen_peak} | gen.py={'✓' if gen_ok else '✗'} | VERSION标记={'✓' if has_version else '✗(或走参考题消歧)'}\n", flush=True)

    if not gen_ok:
        print("write_gen 未产出 gen.py，终止。", flush=True)
        return

    # 看 gen.py 内容摘要
    gen_content = gen_path.read_text(encoding="utf-8")
    print("--- gen.py 前15行 ---", flush=True)
    for line in gen_content.split("\n")[:15]:
        print(f"  {line}", flush=True)
    print(f"  ...（共 {gen_content.count(chr(10))} 行）\n", flush=True)

    # ========== 步骤B: dual_review 阶段2（审求解）==========
    REVIEW_SKILL = (ROOT / "core_new/doc_pipeline/skills/dual_review/SKILL.md").read_text(encoding="utf-8")
    solution_text = ""
    if (WS / "solution.md").exists():
        solution_text = (WS / "solution.md").read_text(encoding="utf-8")
    else:
        # write_gen 可能没单独写 solution.md（它的产出是 gen.py + exec 输出）。给 review 看 gen.py 即可
        solution_text = "(write_gen 未单独写 solution.md；gen.py 的 exec 输出即为求解结果)"

    review_system = "你是双阶段审核智能体。本轮审求解（阶段2）。"
    review_user = (
        f"## 本轮阶段\n本轮审求解（阶段2）\n\n"
        f"## question.md（题干）\n{QUESTION}\n\n"
        f"## gen.py（建模代码）\n{gen_content}\n\n"
        f"## solution.md（求解结果/exec输出整理）\n{solution_text}\n\n"
        f"## design_card（考察意图，供合围判断参考）\n{DESIGN_CARD}\n\n"
        f"## 工作规范（dual_review skill）\n{REVIEW_SKILL}\n\n"
        f"## 输出\nwrite_file(path=\"review.md\")，按 skill 的输出格式。"
    )
    review_registry = ToolRegistry()
    review_registry.register(WriteFileTool(workspace=WS))
    review_registry.register(ReadFileTool(workspace=WS, read_roots=[ROOT / "data"]))
    review_tool_names = ["write_file", "read_file"]
    review_executor = ToolExecutor([review_registry.get(n) for n in review_tool_names])
    review_tools_schema = [review_registry.get(n).to_openai_tool() for n in review_tool_names]

    print("=" * 60, flush=True)
    print("步骤B: dual_review 阶段2（审求解：建模可行 + 题干合围）", flush=True)
    print("=" * 60, flush=True)
    review_start = time.time()
    review_peak = await _run_agent(
        gateway, review_system, review_user, review_tools_schema, review_executor, review_tool_names,
        max_tokens=MAX_TOKENS_REVIEW, max_rounds=6, expected_file="review.md", ws=WS,
    )
    review_elapsed = time.time() - review_start

    review_path = WS / "review.md"
    review_ok = review_path.exists()
    print(f"\n>>> dual_review 结果: 耗时{review_elapsed:.0f}s | reasoning峰值{review_peak} | review.md={'✓' if review_ok else '✗'}\n", flush=True)

    if review_ok:
        print("--- review.md 全文 ---", flush=True)
        print(review_path.read_text(encoding="utf-8"), flush=True)

    # ========== 总结 ==========
    print("\n" + "=" * 60, flush=True)
    print("验证总结", flush=True)
    print("=" * 60, flush=True)
    print(f"write_gen:   gen.py={'✓' if gen_ok else '✗'} | VERSION={'✓' if has_version else '-'} | reasoning峰值={gen_peak} | 耗时={gen_elapsed:.0f}s", flush=True)
    print(f"dual_review: review.md={'✓' if review_ok else '✗'} | reasoning峰值={review_peak} | 耗时={review_elapsed:.0f}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
