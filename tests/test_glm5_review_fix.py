"""
Test: GLM-5.1 作为 question_comp 接收 review 反馈后的修改质量对比。

重建 workspace/2026-06-07T13-19-36-279984 中 question_comp 收到 review needs_fix
反馈后的精确上下文，分别发送给 GLM-5.1 和 Qwen3.6，对比修改质量。

Usage:
    python tests/test_glm5_review_fix.py              # 测试 GLM-5.1
    python tests/test_glm5_review_fix.py --model qwen  # 测试 Qwen3.6
    python tests/test_glm5_review_fix.py --model both  # 两个都测
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from core_new.llm_gateway import get_gateway

# ── 1. 精确重建 agent_loader 的系统提示词 ──────────────────────────

_BEHAVIOR_CORE = (
    "你是一个自主智能体。系统提供工具供你使用，你可以自由选择推理、调用工具或直接输出内容。\n\n"
    "系统工作方式：\n"
    "- 正文输出若符合文件格式（Markdown标题开头），系统会自动写入目标文件\n"
    "- 中间推理不会被保存——只保存最终产出\n"
    "- 工具使用由你决定，按需调用\n\n"
    "增量修改规则：\n"
    "- 首次调用：读输入材料 → write_file 全量输出\n"
    "- 收到修正反馈后：你已经有多轮对话上下文，不需要重新读取原始材料\n"
    "- 分析反馈要求 → edit_file 最小修改 → 不要全量重写\n"
    "- 只改反馈指出的问题，其余保持不变\n"
)

_QUESTION_COMP_BODY = """# 综合应用题出题智能体

## 角色身份

你是408考研综合应用题出题智能体。你专门负责设计符合408考试风格的综合应用题（8-13分/题，含多个子问题）。

## 综合题核心特征

408综合题是**连续推演式考察**，核心在于子问之间的逻辑链条：
- 第一步：基础参数计算或机制推导（基础分）
- 中间步：过程模拟或状态跟踪（核心分）
- 最后一步：结果分析或边界讨论（区分度分）
- 子问之间存在串行依赖（前问结果作为后问输入）

## 408综合题风格约束

1. **题干结构化**：给出完整的系统状态/数据结构/网络配置，作为所有子问题的共享上下文
2. **子问题递进**：每个子问题建立在前面子问题的结果之上，形成连贯的推理链
3. **分值合理**：基础问2-3分，核心问3-4分，区分度问2-3分
4. **无编程代码**：题干中禁止出现任何编程语言代码（算法题用自然语言+数学符号描述）
5. **参数友好**：优先使用2^n相关值，便于心算
6. **考察结构对齐**：严格按照经验卡中的考察结构模式设计子问
7. **子问独立可解**：每个子问题的答案可从前序结果+题干条件推导，不需要跳步

## 行为约束

1. **契约忠实**：保留 assembled.md 中的所有知识点，不得遗漏、替换或新增
2. **K难度忠实**：保留契约指定的 K 难度系数目标，不得自行降低或升高
3. **子问结构忠实**：保留契约要求的子问题数量与结构
4. **子问依赖**：子问之间必须有逻辑依赖（串行或混合），不允许完全独立
5. **不写答案**：不写答案、不写求解过程——只输出题干、子问题、设计说明
6. **条件充分不冗余**：每个给定条件都要被子问题用到
7. **迭代上限**：从设计到产出最多3轮工具调用。超过则直接基于最佳理解产出
8. **工具使用**：
   - 新建文件：write_file
   - 修改已有文件：先 read_file 查看当前内容，再 edit_file 做最小修改
   - 最终产出通过 write_file(path="question.md", content="完整题目") 写入
   - 不执行代码验证——数值参数校验由求解智能体负责

## 格式红线（违反即判定 needs_fix）

1. **禁止选项格式**：子问题不得包含A/B/C/D选项。综合题的每个子问题要求考生产出推导过程或计算结果
2. **禁止独立子问**：不得出现与前后子问无逻辑关联的独立问题
3. **禁止编程代码题干**：题干不得包含C/Java/Python代码片段（算法题的结构体/类型定义除外）
4. **禁止背景故事**：题干不得包含与考察无关的叙述
5. **禁止答案出现在题目中**：设计说明与题干严格分离"""

_QUESTION_CREATE_VARIANT = (
    "你的模式是「设计→输出」。\n"
    "设计阶段：深入思考知识点覆盖、逻辑关联、题干表述、消除歧义。\n"
    "数值参数校验不在此阶段——由求解智能体负责。\n"
    "不写答案：答案由独立的求解智能体产出，你只输出题干+选项/子问题+设计说明。"
)

_WRITE_FILE_SUFFIX = (
    "\n\n产出文件：question.md"
    "（可通过 write_file 工具写入，或直接输出完整Markdown内容由系统自动保存。）"
)

SYSTEM_PROMPT = (
    _BEHAVIOR_CORE
    + "\n\n"
    + _QUESTION_COMP_BODY
    + "\n\n"
    + _QUESTION_CREATE_VARIANT
    + _WRITE_FILE_SUFFIX
)

# ── 2. 工作区文件 ─────────────────────────────────────────────────

WORKSPACE = (
    Path(__file__).resolve().parent.parent
    / "docs" / "workspace" / "2026-06-07T13-19-36-279984" / "q1" / "KP-untagged"
)


def load_file(name: str) -> str:
    p = WORKSPACE / name
    if not p.exists():
        print(f"  [WARN] {name} not found")
        return ""
    return p.read_text(encoding="utf-8")


def parse_section(md: str, heading: str) -> str:
    """Extract content under ## heading until next ## or end."""
    lines = md.split("\n")
    capture = False
    result = []
    for line in lines:
        if line.strip().startswith("## ") and capture:
            break
        if line.strip() == f"## {heading}":
            capture = True
            continue
        if capture:
            result.append(line)
    return "\n".join(result).strip()


# ── 3. 精确重建消息上下文 ────────────────────────────────────────


def build_messages() -> list[dict]:
    """Recreate the exact messages question_comp received at iteration 1."""

    skill_path = (
        Path(__file__).resolve().parent.parent
        / "core_new" / "doc_pipeline" / "skills" / "question_create" / "question_comp_skill.md"
    )
    skill_content = skill_path.read_text(encoding="utf-8").strip() if skill_path.exists() else ""
    assembled = load_file("assembled.md")
    question_original = load_file("question.md")
    review_md = load_file("review.md")

    corrections = parse_section(review_md, "corrections")
    if not corrections.strip() or corrections.strip() == "无":
        corrections = parse_section(review_md, "summary")

    # Turn 1: Initial question generation
    first_task = "请设计 Q1 的完整题目。注意：不写答案，答案由独立求解智能体产出。"
    if skill_content:
        first_task += f"\n\n## 工作规范\n{skill_content}"
    if assembled:
        first_task += f"\n\n## 规划\n{assembled}"

    # Turn 1 assistant: Qwen's original output (question.md)
    first_assistant = question_original

    # Turn 2: Review feedback (iteration 1, continue_session=True)
    second_task = (
        "请设计 Q1 的完整题目。注意：不写答案，答案由独立求解智能体产出。\n\n"
        "这是第 2 次迭代，请根据审核反馈修正题目。"
    )
    second_task += f"\n\n## 审核反馈（第1轮）\n{corrections}"
    if skill_content:
        second_task += f"\n\n## 工作规范\n{skill_content}"
    if assembled:
        second_task += f"\n\n## 规划\n{assembled}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": first_task},
        {"role": "assistant", "content": first_assistant},
        {"role": "user", "content": second_task},
    ]
    return messages


# ── 4. 通过网关调用 ──────────────────────────────────────────────


async def call_model(messages: list[dict], backend: str) -> dict:
    """Call a model via LLMGateway and return response info."""
    provider_name = "glm5.1" if backend == "glm" else "api_vllm"
    print(f"\n{'='*60}")
    print(f"Calling {backend.upper()} via gateway: {provider_name}")
    print(f"Messages: {len(messages)} turns")
    print(f"System prompt: {len(messages[0]['content'])} chars")
    print(f"Last user msg: {len(messages[-1]['content'])} chars")
    print(f"{'='*60}")

    gateway = get_gateway(provider_name)

    start = time.time()
    try:
        results = await gateway.generate_reasoned_batch(
            messages_batch=[messages],
            max_tokens=16000,
            enable_thinking=True,
        )
        elapsed = time.time() - start

        if not results:
            return {"backend": backend, "content": "ERROR: no results", "content_len": 0, "elapsed": elapsed}

        r = results[0]
        return {
            "backend": backend,
            "model": r.model,
            "content": r.content or "",
            "content_len": len(r.content or ""),
            "reasoning": r.reasoning or "",
            "reasoning_len": len(r.reasoning or ""),
            "ok": r.ok,
            "error": r.error_message,
            "elapsed": round(elapsed, 1),
            "latency_ms": r.latency_ms,
            "tokens": r.tokens_used,
        }
    except Exception as e:
        elapsed = time.time() - start
        return {"backend": backend, "content": f"ERROR: {e}", "content_len": 0, "elapsed": round(elapsed, 1), "error": str(e)}


# ── 5. 质量评估 ───────────────────────────────────────────────────


def evaluate_response(result: dict) -> dict:
    """Check if the model properly addressed review feedback."""
    content = result.get("content", "")
    if content.startswith("ERROR"):
        return {"pass": False, "reason": "API call failed"}

    checks = {
        # 核心：是否移除了伪代码块
        "removed_pseudo_code": "AVL_Insert" not in content and "right_rotate(y)" not in content,
        "removed_code_fence": content.count("```") <= 2,
        # 结构完整性
        "has_question_body": "## 题干" in content or "## 题目" in content,
        "has_sub_questions": "### (1)" in content or "### （1）" in content,
        "has_design_notes": "设计说明" in content,
        # 保留必要内容
        "kept_insertion_sequence": "10" in content and "20" in content and "30" in content,
        "kept_balance_factor_def": "平衡因子" in content,
        # 格式红线
        "no_ABCD_options": not any(f"### ({c})" in content and f"{c}." in content[:500] for c in "ABCD"),
    }

    score = sum(1 for v in checks.values() if v)
    total = len(checks)
    checks["score"] = f"{score}/{total}"

    # 核心判定：是否解决了 review 指出的关键问题（伪代码）
    checks["FIXED_CORE_ISSUE"] = checks["removed_pseudo_code"] and checks["removed_code_fence"]

    return checks


# ── 6. Main ───────────────────────────────────────────────────────


async def main():
    parser = argparse.ArgumentParser(description="Test GLM-5.1 vs Qwen3.6 review fix quality")
    parser.add_argument("--model", choices=["glm", "qwen", "both"], default="glm")
    args = parser.parse_args()

    print("=" * 60)
    print("Review Fix Quality Comparison: GLM-5.1 vs Qwen3.6")
    print("=" * 60)
    print(f"\nWorkspace: {WORKSPACE}")

    messages = build_messages()

    print(f"\nMessage structure:")
    for i, m in enumerate(messages):
        role = m["role"]
        clen = len(m["content"])
        preview = m["content"][:80].replace("\n", " ")
        print(f"  [{i}] {role}: {clen} chars — {preview}...")

    results = []

    if args.model in ("glm", "both"):
        r = await call_model(messages, "glm")
        results.append(r)

    if args.model in ("qwen", "both"):
        r = await call_model(messages, "qwen")
        results.append(r)

    # Save outputs
    output_dir = Path(__file__).resolve().parent.parent / "docs" / "test_output"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    for r in results:
        print(f"\n{'─'*50}")
        print(f"Backend: {r['backend']}")
        print(f"OK: {r.get('ok', 'N/A')}")
        print(f"Time: {r.get('elapsed', '?')}s (latency: {r.get('latency_ms', '?')}ms)")
        print(f"Content: {r.get('content_len', 0)} chars")
        print(f"Reasoning: {r.get('reasoning_len', 0)} chars")
        print(f"Tokens: {r.get('tokens', 'N/A')}")

        if r.get("error"):
            print(f"ERROR: {r['error']}")
            continue

        checks = evaluate_response(r)
        print(f"\nQuality checks:")
        for k, v in checks.items():
            if k == "score":
                print(f"  >>> Score: {v}")
            elif k == "FIXED_CORE_ISSUE":
                icon = "✓✓✓" if v else "✗✗✗"
                print(f"  {icon} {k}: {v}")
            else:
                icon = "✓" if v is True else "✗" if v is False else str(v)
                print(f"  {icon} {k}")

        # Save response
        fname = f"review_fix_{r['backend']}.md"
        out_path = output_dir / fname
        out_path.write_text(r["content"], encoding="utf-8")
        print(f"\nSaved: {out_path}")

        # Save reasoning if available
        if r.get("reasoning"):
            reason_path = output_dir / f"review_fix_{r['backend']}_reasoning.md"
            reason_path.write_text(r["reasoning"], encoding="utf-8")
            print(f"Reasoning: {reason_path}")

        # Preview
        print(f"\nFirst 600 chars:")
        print("─" * 40)
        print(r["content"][:600])
        if len(r["content"]) > 600:
            print(f"\n... ({len(r['content']) - 600} more chars)")

    # Summary
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H-%M-%S"),
        "workspace": str(WORKSPACE),
        "results": [
            {
                "backend": r["backend"],
                "ok": r.get("ok"),
                "content_len": r.get("content_len", 0),
                "reasoning_len": r.get("reasoning_len", 0),
                "elapsed": r.get("elapsed"),
                "quality": evaluate_response(r) if not r.get("error") else {"error": r["error"]},
            }
            for r in results
        ],
    }
    summary_path = output_dir / "review_fix_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSummary: {summary_path}")


if __name__ == "__main__":
    asyncio.run(main())
