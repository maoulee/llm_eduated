"""Experiment 1: Setting 1 (pure reasoning) vs Setting 2 (reasoning + code).

Setting 1: Model answers questions with thinking mode, answer in \\boxed{}
Setting 2: Model answers with thinking + generates code, executes code, compares

Uses local vLLM (Qwen3.6-27B) with optimal params (temp=1.0, top_p=0.95).
Results saved to docs/experiment_1_results.json
"""

import asyncio
import json
import os
import re
import time
import traceback
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

from config import get_provider_config
from llm_providers_new import get_llm_provider


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PROMPT_REASON_ONLY = """请解答以下题目。这是真题，不要质疑题目的合理性，直接推理作答。将最终答案放在 \\boxed{{}} 中。

{raw_question}"""


PROMPT_REASON = """请解答以下题目。这是真题，不要质疑题目的合理性，直接推理作答。将最终答案放在 \\boxed{{}} 中。

{raw_question}"""


PROMPT_CODE = """请为以下题目编写Python代码来独立计算答案。这是真题，不要质疑题目。

{raw_question}

代码规范：
- 代码必须是完整的、可直接执行的Python代码
- 不要有前导缩进（从第一列开始写）
- 使用 print() 输出中间步骤和最终答案
- 如果需要位运算，使用 & | ^ << >> 等运算符
- 只允许使用Python内置函数和math模块
- 不要使用input()、open()、__import__等

请只输出代码，不要输出其他内容：
```python
# 你的代码
```"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_boxed_answer(text: str) -> str:
    """Extract answer from \\boxed{} notation."""
    m = re.search(r'\\boxed\{([^}]+)\}', text)
    return m.group(1).strip() if m else ""


def _extract_xml_tags(text: str) -> Dict[str, str]:
    """Extract XML-tagged fields from model output."""
    result = {}
    for m in re.finditer(r'<(\w+)>(.*?)</\1>', text, re.DOTALL):
        result[m.group(1)] = m.group(2).strip()
    return result


def extract_code_from_text(text: str) -> Optional[str]:
    """Extract Python code from model output."""
    # Try ```python ... ``` blocks
    for match in re.finditer(r"```(?:python)?\s*\n?(.*?)```", text, re.DOTALL):
        return match.group(1).strip()

    # Try XML <code>...</code>
    parsed = _extract_xml_tags(text)
    if "code" in parsed:
        return parsed["code"]

    # If text looks like pure code (has def/print/import at line start)
    lines = text.strip().split("\n")
    code_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]
    if code_lines and any(
        code_lines[0].strip().startswith(kw) for kw in ["def ", "import ", "from ", "print("]
    ):
        return text.strip()
    return None


def execute_code_safely(code: str, timeout: int = 10) -> Dict[str, Any]:
    """Execute Python code with restricted builtins, capture print output."""
    stdout_buf = StringIO()
    stderr_buf = StringIO()

    import math
    SAFE_BUILTINS = {
        "range": range, "len": len, "int": int, "str": str, "float": float,
        "bin": bin, "hex": hex, "oct": oct, "bool": bool, "list": list,
        "dict": dict, "tuple": tuple, "set": set, "sorted": sorted,
        "print": print, "sum": sum, "min": min, "max": max, "abs": abs,
        "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
        "isinstance": isinstance, "type": type, "round": round, "pow": pow,
        "reversed": reversed, "all": all, "any": any, "divmod": divmod,
        "chr": chr, "ord": ord, "format": format,
    }
    restricted_globals = {
        "__builtins__": SAFE_BUILTINS,
        "math": math,
    }

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(code, restricted_globals)
        output = stdout_buf.getvalue().strip()
        return {"success": True, "output": output, "stderr": stderr_buf.getvalue().strip()}
    except Exception:
        return {
            "success": False,
            "output": stdout_buf.getvalue().strip(),
            "error": traceback.format_exc(),
        }


def extract_answer_letter(text: str) -> Optional[str]:
    """Extract answer letter (A/B/C/D) or number from text."""
    if not text:
        return None

    # Look for explicit answer patterns first
    for pattern in [
        r'[最终答案|答案|answer][：:]\s*([A-D])\b',
        r'[最终答案|答案|answer][：:]\s*(.+)',
        r'最终CRC校验码[：:]\s*(\d+)',
        r'结果[：:]\s*(.+)',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if re.match(r'^[A-D]$', val, re.IGNORECASE):
                return val.upper()
            return val[:50]

    # Check last line of output
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    if lines:
        last = lines[-1]
        m = re.search(r'\b([A-D])\b', last, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        m = re.search(r'[-+]?\d+(?:\.\d+)?', last)
        if m:
            return m.group(0)

    # Fallback
    m = re.search(r'\b([A-D])\b', text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    m = re.search(r'[-+]?\d+(?:\.\d+)?', text)
    if m:
        return m.group(0)
    return text.strip()[:50]


def normalize_answer(answer: str) -> str:
    """Normalize answer for comparison."""
    return str(answer).strip().upper()


# ---------------------------------------------------------------------------
# Setting 1: Pure reasoning
# ---------------------------------------------------------------------------

async def run_setting1(provider, question: Dict[str, Any]) -> Dict[str, Any]:
    """Setting 1: Single LLM call with thinking, answer in \\boxed{}."""
    raw_question = question.get("prompt", "")
    ground_truth = question.get("answer", "")

    prompt = PROMPT_REASON_ONLY.format(raw_question=raw_question)
    messages = [[{"role": "user", "content": prompt}]]

    start = time.time()
    results = await provider.generate_with_think_and_parse_batch(
        messages, max_token=4096, enable_thinking=True,
    )
    elapsed = time.time() - start

    raw_result = results[0] if results else {}
    answer_text = raw_result.get("answer", "") if isinstance(raw_result, dict) else ""

    # Extract answer from \boxed{}
    answer = _extract_boxed_answer(answer_text)
    if not answer:
        # Fallback: try XML tags
        xml_tags = _extract_xml_tags(answer_text)
        answer = xml_tags.get("answer_option", "") or xml_tags.get("answer_value", "")
    if not answer:
        # Last resort: extract letter or number
        answer = extract_answer_letter(answer_text) or ""

    gt = normalize_answer(ground_truth)
    # Extract key number from ground truth if it contains Chinese context
    for pattern in [r'CRC校验码为(\d+)', r'余数为(\d+)', r'即([+-]?\d+)', r'叶子结点数为(\d+)', r'([+-]?\d+)']:
        m = re.search(pattern, str(ground_truth))
        if m:
            gt = m.group(1)
            break

    correct = normalize_answer(answer) == gt

    return {
        "answer": answer,
        "correct": correct,
        "time": round(elapsed, 1),
        "raw_answer_preview": answer_text[:200],
    }


# ---------------------------------------------------------------------------
# Setting 2: Reasoning + Code
# ---------------------------------------------------------------------------

async def run_setting2(provider, question: Dict[str, Any]) -> Dict[str, Any]:
    """Setting 2: Reasoning pass + code pass + execute + compare."""
    raw_question = question.get("prompt", "")
    ground_truth = question.get("answer", "")

    start = time.time()

    # --- Pass 1: Reasoning ---
    reason_prompt = PROMPT_REASON.format(raw_question=raw_question)
    reason_messages = [[{"role": "user", "content": reason_prompt}]]
    reason_results = await provider.generate_with_think_and_parse_batch(
        reason_messages, max_token=4096, enable_thinking=True,
    )
    reason_raw = reason_results[0] if reason_results else {}
    reason_text = reason_raw.get("answer", "") if isinstance(reason_raw, dict) else ""
    reasoning_answer = _extract_boxed_answer(reason_text)
    if not reasoning_answer:
        xml_tags = _extract_xml_tags(reason_text)
        reasoning_answer = xml_tags.get("answer_option", "") or xml_tags.get("answer_value", "")

    # --- Pass 2: Code generation ---
    code_prompt = PROMPT_CODE.format(raw_question=raw_question)
    code_messages = [[{"role": "user", "content": code_prompt}]]
    code_results = await provider.generate_with_think_and_parse_batch(
        code_messages, max_token=4096, enable_thinking=True,
    )
    code_raw = code_results[0] if code_results else {}
    code_output_text = code_raw.get("answer", "") if isinstance(code_raw, dict) else ""

    code = extract_code_from_text(code_output_text) or ""
    if not code:
        code = _extract_xml_tags(code_output_text).get("code", "")

    # --- Pass 3: Execute code ---
    exec_result = {"success": False, "output": "", "error": "no code generated"}
    if code:
        exec_result = execute_code_safely(code)

    code_answer = ""
    if exec_result.get("success"):
        code_answer = extract_answer_letter(exec_result.get("output", "")) or ""

    elapsed = time.time() - start

    # --- Comparison ---
    gt = normalize_answer(ground_truth)
    for pattern in [r'CRC校验码为(\d+)', r'余数为(\d+)', r'即([+-]?\d+)', r'叶子结点数为(\d+)', r'([+-]?\d+)']:
        m = re.search(pattern, str(ground_truth))
        if m:
            gt = m.group(1)
            break

    reasoning_correct = normalize_answer(reasoning_answer) == gt if reasoning_answer else False
    code_correct = normalize_answer(code_answer) == gt if code_answer else False
    consistent = normalize_answer(reasoning_answer) == normalize_answer(code_answer) if (reasoning_answer and code_answer) else False

    return {
        "reasoning_answer": reasoning_answer,
        "reasoning_correct": reasoning_correct,
        "code_answer": code_answer,
        "code_correct": code_correct,
        "code_executed": exec_result.get("success", False),
        "consistent": consistent,
        "time": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    from run_extraction_sample import QUESTIONS

    # Init provider
    config = get_provider_config("api_vllm")
    served_model = os.environ.get("VLLM_SERVED_MODEL")
    if served_model:
        config["model_path"] = served_model
    provider = get_llm_provider(config)
    print(f"Provider: {config.get('model_path', 'api_vllm')}")
    print(f"Questions: {len(QUESTIONS)}")

    all_results = []
    total_start = time.time()

    for i, q in enumerate(QUESTIONS):
        qid = q.get("id", "?")
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(QUESTIONS)}] {qid}: {q['prompt'][:50]}...")

        # Setting 1
        print(f"  Running Setting 1 (reasoning only)...")
        s1 = await run_setting1(provider, q)
        s1_status = "CORRECT" if s1["correct"] else "WRONG"
        print(f"  Setting 1: answer={s1['answer']} ({s1_status}) [{s1['time']:.1f}s]")

        # Setting 2
        print(f"  Running Setting 2 (reasoning + code)...")
        s2 = await run_setting2(provider, q)
        r_status = "CORRECT" if s2["reasoning_correct"] else "WRONG"
        c_status = "CORRECT" if s2["code_correct"] else "WRONG"
        exec_status = "OK" if s2["code_executed"] else "FAIL"
        match_status = "YES" if s2["consistent"] else "NO"
        print(f"  Setting 2: reasoning={s2['reasoning_answer']}({r_status}) "
              f"code={s2['code_answer']}({c_status}) exec={exec_status} match={match_status} [{s2['time']:.1f}s]")
        print(f"  Ground truth: {q.get('answer', '?')}")

        all_results.append({
            "question_id": qid,
            "ground_truth": q.get("answer", ""),
            "setting1": s1,
            "setting2": s2,
        })

    total_elapsed = time.time() - total_start
    total = len(all_results)

    # Summary
    s1_correct = sum(1 for r in all_results if r["setting1"]["correct"])
    s2_r_correct = sum(1 for r in all_results if r["setting2"]["reasoning_correct"])
    s2_c_correct = sum(1 for r in all_results if r["setting2"]["code_correct"])
    s2_consistent = sum(1 for r in all_results if r["setting2"]["consistent"])

    print(f"\n{'='*60}")
    print(f"Experiment 1 Summary ({total} questions, {total_elapsed:.1f}s total)")
    print(f"{'='*60}")
    print(f"Setting 1 (reasoning only):     {s1_correct}/{total} correct")
    print(f"Setting 2 (reasoning):          {s2_r_correct}/{total} correct")
    print(f"Setting 2 (code):               {s2_c_correct}/{total} correct")
    print(f"Setting 2 (both consistent):    {s2_consistent}/{total}")

    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "docs", "experiment_1_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
