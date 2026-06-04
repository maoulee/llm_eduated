"""A/B test: run analysis agent with different prompts on the same input.

Compares:
  A: current analysis.md prompt (from AgentMD)
  B: enhanced prompt with K-value difficulty checking and condition utilization audit

Both get the same blueprint + question as input.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import time
from pathlib import Path

from core_new.doc_pipeline.agent_loader import load_agents
from core_new.doc_pipeline.write_file_tool import WriteFileTool
from core_new.agent_runtime.registry import ToolRegistry
from core_new.agent_tools import ToolExecutor
from core_new.provider_router import get_routed_gateway

# ── Load inputs ──

WORKSPACE = Path("workspace/Q43")
BLUEPRINT = (WORKSPACE / "blueprint.md").read_text(encoding="utf-8")
QUESTION = (WORKSPACE / "question.md").read_text(encoding="utf-8")

# ── Prompt variants ──

# A: Current prompt from AgentMD
spec_a = load_agents()["analysis"]
PROMPT_A = spec_a.prompt

# B: Enhanced prompt with K-value checking and condition utilization
PROMPT_B = """你是408出题审核专家。你需要从以下维度严格审核题目：

## 审核维度

### 1. 参数一致性（Critical）
题干、子问题、答案中的所有数值参数是否前后一致。逐一核对每个数值。

### 2. 条件利用率（Critical）
**重点检查**：题目给出的每个条件是否在解题过程中被实际使用。
- 列出题干中的所有给定条件
- 检查每个条件是否在答案中被用到
- 如果某个条件未被使用或被假设规避了，标记为 needs_fix
- 示例：如果题目给出"写策略=写直达"但又声明"所有访问均为读操作"，则该条件未被实际考察

### 3. 难度K值对标（Important）
对照蓝图中的K1-K5难度定义，检查题目实际考察难度是否匹配：
- K4(条件路由)：蓝图是否要求存在条件分支或陷阱？题目是否通过假设规避了这些条件？
- 逐条检查每个K维度是否被实际体现

### 4. 题干清晰度（Standard）
描述是否精确无歧义。

## 审判原则
- 严格判定：任何一个条件未被实际考察 = needs_fix
- 任何K维度被假设规避 = needs_fix
- 宁可标记为 needs_fix 也不要放过问题

## 输出格式

## status
pass 或 needs_fix

## summary
一句话总结审核结论

## detailed_feedback
### 参数一致性
结论

### 条件利用率
列出所有给定条件及其使用情况：
- 条件1: [使用/未使用/被假设规避] — 说明
- 条件2: ...

### 难度K值对标
逐维度结论

### 建议修改
（仅 needs_fix 时）具体修正建议

【强制要求】你必须调用 write_file 工具将结果写入文件。禁止直接输出内容文本，必须通过 OpenAI tool_calls 字段调用 write_file(path="feedback.md", content="你的完整内容") 完成输出。不要在工具调用之外输出任何正文内容；如果把 JSON 或函数调用写在正文里，系统会判定失败。"""

TASK = "请审核以下题目，检查参数一致性、条件利用率和难度对标。"


async def run_analysis(prompt_variant: str, label: str, output_file: str) -> dict:
    """Run analysis agent with a given prompt, return result dict."""
    gateway = get_routed_gateway("doc_design")
    provider = gateway._provider

    ws = Path("workspace") / "ab_test" / label
    ws.mkdir(parents=True, exist_ok=True)

    # Clean any existing file
    out_path = ws / "feedback.md"
    if out_path.exists():
        out_path.unlink()

    # Build messages
    full_task = TASK + f"\n\n## 蓝图\n{BLUEPRINT}\n\n## 题目\n{QUESTION}"
    messages = [
        {"role": "system", "content": prompt_variant},
        {"role": "user", "content": full_task},
    ]

    # Build tools
    registry = ToolRegistry()
    registry.register(WriteFileTool(workspace=ws))
    tool_list = [registry.get("write_file")]
    executor = ToolExecutor(tool_list)
    openai_tools = [t.to_openai_tool() for t in tool_list]

    t0 = time.monotonic()

    # Streaming call (same as scheduler)
    raw = await _stream(provider, messages, tools=openai_tools)
    elapsed = time.monotonic() - t0

    content = raw.get("content", "")
    tool_calls = raw.get("tool_calls")

    # Handle textual tool call
    if not tool_calls and content and content.lstrip().startswith("["):
        from core_new.doc_pipeline.scheduler import DocScheduler
        extracted = DocScheduler._extract_textual_tool_call(content)
        if extracted:
            tool_calls = extracted

    # Execute tool calls
    final_text = ""
    if tool_calls:
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            fn_args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
            result_str = await executor.execute(fn_name, fn_args)
            if out_path.exists():
                final_text = out_path.read_text(encoding="utf-8")

    return {
        "label": label,
        "elapsed_s": round(elapsed, 1),
        "has_tool_call": tool_calls is not None,
        "content_len": len(content),
        "reasoning_len": len(raw.get("reasoning_content", "")),
        "wrote_file": out_path.exists(),
        "final_text": final_text,
    }


async def _stream(provider, messages, tools):
    """Streaming chat call."""
    processed = provider._prepare_messages(messages, enable_thinking=None, json_mode=False)
    sampling = {k: v for k, v in provider.sampling_params.items() if k != "top_k"}
    sampling.update({"temperature": 0.2, "top_p": 0.9})

    params = {
        "model": provider.model_name,
        "messages": processed,
        "stream": True,
        "max_tokens": 20000,
        "tools": tools,
        "tool_choice": "required",
        **sampling,
    }
    params.setdefault("extra_body", {})
    params["extra_body"]["thinking_token_budget"] = 10000

    content_parts = []
    reasoning_parts = []
    tool_calls_accum = {}

    stream = await provider.client.chat.completions.create(**params)
    async for chunk in stream:
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        delta = choice.delta
        if delta.content:
            content_parts.append(delta.content)
        rc = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None) or ""
        if rc:
            reasoning_parts.append(rc)
        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = tc_delta.index
                if idx not in tool_calls_accum:
                    tool_calls_accum[idx] = {"id": "", "name": "", "arguments": ""}
                if tc_delta.id:
                    tool_calls_accum[idx]["id"] = tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name:
                        tool_calls_accum[idx]["name"] = tc_delta.function.name
                    if tc_delta.function.arguments:
                        tool_calls_accum[idx]["arguments"] += tc_delta.function.arguments

    tool_calls = None
    if tool_calls_accum:
        tool_calls = []
        for idx in sorted(tool_calls_accum):
            tc = tool_calls_accum[idx]
            tool_calls.append({"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}})

    return {
        "content": "".join(content_parts),
        "reasoning_content": "".join(reasoning_parts),
        "tool_calls": tool_calls,
    }


async def main():
    print("=" * 70)
    print("Analysis A/B Test")
    print("=" * 70)

    print("\n▶ Running Variant A (current prompt)...")
    result_a = await run_analysis(PROMPT_A, "A", "feedback.md")
    print(f"  Done: {result_a['elapsed_s']}s, tool_call={result_a['has_tool_call']}, wrote={result_a['wrote_file']}")

    print("\n▶ Running Variant B (enhanced prompt)...")
    result_b = await run_analysis(PROMPT_B, "B", "feedback.md")
    print(f"  Done: {result_b['elapsed_s']}s, tool_call={result_b['has_tool_call']}, wrote={result_b['wrote_file']}")

    print("\n" + "=" * 70)
    print("RESULTS COMPARISON")
    print("=" * 70)

    for r in [result_a, result_b]:
        print(f"\n### Variant {r['label']} ({r['elapsed_s']}s) ###")
        if r['wrote_file']:
            text = r['final_text']
            # Extract status and summary
            for line in text.split('\n'):
                if line.startswith('## status'):
                    continue
                if line.strip() in ('pass', 'needs_fix'):
                    print(f"  Status: {line.strip()}")
            print(f"  Content length: {len(text)} chars")
            # Show first 500 chars of feedback
            if '## detailed_feedback' in text:
                feedback_start = text.index('## detailed_feedback')
                print(f"  Feedback preview:\n{text[feedback_start:feedback_start+500]}...")
        else:
            print(f"  FAILED to write file")

    # Show files for manual comparison
    print(f"\nFiles:")
    print(f"  A: workspace/ab_test/A/feedback.md")
    print(f"  B: workspace/ab_test/B/feedback.md")


if __name__ == "__main__":
    asyncio.run(main())
