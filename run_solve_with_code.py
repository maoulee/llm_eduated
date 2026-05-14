"""
Solve questions with dual-channel verification: model reasoning + code execution.

Flow per question:
  1. Model reasons through the problem (LLM call) → text answer
  2. Model writes Python code to compute the answer (LLM call) → code
  3. Execute the code → computed answer
  4. Compare reasoning answer vs code answer vs ground truth

Supports bare and inject modes (same as run_ab_solve_test.py).

Uses local vLLM (Qwen3.6-27B) for inference.
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

def format_options(extraction: Dict[str, Any]) -> str:
    opts = extraction.get("question_structure", {}).get("options", {})
    if not opts:
        return ""
    lines = []
    for k in sorted(opts.keys()):
        lines.append(f"{k}. {opts[k]}")
    return "\n".join(lines)


def extract_dict_from_text(text: str) -> Optional[Dict]:
    """Try to parse dict from model output (JSON or Python repr)."""
    # Try direct JSON parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try extracting from ```json ... ``` blocks
    for match in re.finditer(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL):
        try:
            return json.loads(match.group(1).strip())
        except (json.JSONDecodeError, TypeError):
            continue

    # Try finding first { ... } block
    depth = 0
    start = None
    for i, c in enumerate(text):
        if c == '{':
            if depth == 0:
                start = i
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0 and start is not None:
                chunk = text[start:i+1]
                # Try JSON
                try:
                    return json.loads(chunk)
                except (json.JSONDecodeError, TypeError):
                    pass
                # Try Python dict repr (single quotes)
                try:
                    import ast
                    return ast.literal_eval(chunk)
                except (ValueError, SyntaxError):
                    pass
                start = None
    return None


def extract_code_from_text(text: str) -> Optional[str]:
    """Extract Python code from model output."""
    # Try dict/JSON parse first
    parsed = extract_dict_from_text(text)
    if isinstance(parsed, dict) and "code" in parsed:
        return parsed["code"]

    # Try ```python ... ``` blocks
    for match in re.finditer(r"```(?:python)?\s*\n?(.*?)```", text, re.DOTALL):
        return match.group(1).strip()

    # If text looks like pure code (has def/print/import at line start)
    lines = text.strip().split("\n")
    code_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]
    if code_lines and any(
        code_lines[0].strip().startswith(kw) for kw in ["def ", "import ", "from ", "print(", "#"]
    ):
        return text.strip()
    return None


def execute_code_safely(code: str, timeout: int = 10) -> Dict[str, Any]:
    """Execute Python code, capture print output."""
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

    # Look for explicit answer patterns first (most reliable)
    for pattern in [
        r'[最终答案|答案|answer][：:]\s*([A-D])\b',
        r'[最终答案|答案|answer][：:]\s*(.+)',
        r'最终CRC校验码[：:]\s*(\d+)',
        r'结果[：:]\s*(.+)',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            # If it's a single letter, return it
            if re.match(r'^[A-D]$', val, re.IGNORECASE):
                return val.upper()
            return val[:50]

    # Check last line of output for answer
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    if lines:
        last = lines[-1]
        # Single letter in last line
        m = re.search(r'\b([A-D])\b', last, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        # Number in last line
        m = re.search(r'[-+]?\d+(?:\.\d+)?', last)
        if m:
            return m.group(0)

    # Fallback: first single letter in entire text
    m = re.search(r'\b([A-D])\b', text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # First number
    m = re.search(r'[-+]?\d+(?:\.\d+)?', text)
    if m:
        return m.group(0)
    return text.strip()[:50]


def _extract_xml_tags(text: str) -> Dict[str, str]:
    """Extract XML-tagged fields from model output."""
    result = {}
    for m in re.finditer(r'<(\w+)>(.*?)</\1>', text, re.DOTALL):
        result[m.group(1)] = m.group(2).strip()
    return result


def _extract_boxed_answer(text: str) -> str:
    """Extract answer from \\boxed{} notation."""
    m = re.search(r'\\boxed\{([^}]+)\}', text)
    return m.group(1).strip() if m else ""


def compare_offline(reasoning_answer: str, code_answer: str, ground_truth: str) -> Dict[str, Any]:
    """Offline comparison: model answers vs ground truth (not shown to model)."""
    gt = str(ground_truth).strip().upper()
    # For numeric ground truths, try to extract the key number
    for pattern in [r'CRC校验码为(\d+)', r'余数为(\d+)', r'即([+-]?\d+)', r'叶子结点数为(\d+)', r'([+-]?\d+)']:
        m = re.search(pattern, str(ground_truth))
        if m:
            gt = m.group(1)
            break

    ra = str(reasoning_answer).strip().upper() if reasoning_answer else ""
    ca = str(code_answer).strip().upper() if code_answer else ""

    reasoning_correct = ra == gt if ra else False
    code_correct = ca == gt if ca else False
    consistent = ra == ca if (ra and ca) else False

    return {
        "reasoning_answer": ra or None,
        "code_answer": ca or None,
        "ground_truth": gt,
        "reasoning_correct": reasoning_correct,
        "code_correct": code_correct,
        "consistent": consistent,
    }


# ---------------------------------------------------------------------------
# Main solve logic
# ---------------------------------------------------------------------------

async def solve_with_code(
    provider,
    question: Dict[str, Any],
) -> Dict[str, Any]:
    """Solve a question: reasoning pass + code pass + offline compare."""

    raw_question = question.get("prompt", "")
    answer = question.get("answer", "")

    # --- Pass 1: Reasoning (blind — no answer) ---
    reason_prompt = PROMPT_REASON.format(raw_question=raw_question)
    reason_messages = [[{"role": "user", "content": reason_prompt}]]
    reason_results = await provider.generate_with_think_and_parse_batch(
        reason_messages, max_token=4096, enable_thinking=True,
    )
    reason_raw = reason_results[0] if reason_results else {}

    # Parse answer from \boxed{} or XML tags
    reason_text = reason_raw.get("answer", "") if isinstance(reason_raw, dict) else ""
    reason_parsed = _extract_xml_tags(reason_text)
    reasoning_answer = _extract_boxed_answer(reason_text)
    if not reasoning_answer:
        reasoning_answer = reason_parsed.get("answer_option", "") or reason_parsed.get("answer_value", "")
    reasoning_confidence = ""

    # --- Pass 2: Code generation (blind — no answer) ---
    code_prompt = PROMPT_CODE.format(raw_question=raw_question)
    code_messages = [[{"role": "user", "content": code_prompt}]]
    code_results = await provider.generate_with_think_and_parse_batch(
        code_messages, max_token=4096, enable_thinking=True,
    )
    code_raw = code_results[0] if code_results else {}

    code_output_text = code_raw.get("answer", "") if isinstance(code_raw, dict) else ""
    code = extract_code_from_text(code_output_text) or ""
    if not code:
        code_parsed = _extract_xml_tags(code_output_text)
        code = code_parsed.get("code", "")

    # --- Pass 3: Execute code ---
    exec_result = {"success": False, "output": "", "error": "no code generated"}
    if code:
        exec_result = execute_code_safely(code)

    # --- Pass 4: Offline comparison against ground truth ---
    code_answer = extract_answer_letter(exec_result.get("output", "")) if exec_result.get("success") else ""
    comparison = compare_offline(reasoning_answer, code_answer, answer)

    return {
        "question_id": question.get("id", "?"),
        "ground_truth": answer,
        "reasoning": {
            "answer_option": reason_parsed.get("answer_option", ""),
            "answer_value": reason_parsed.get("answer_value", ""),
            "confidence": reasoning_confidence,
            "preview": reason_parsed.get("reasoning", "")[:300],
        },
        "code": {
            "generated": bool(code),
            "source": code[:500] if code else None,
            "exec_success": exec_result.get("success", False),
            "output": exec_result.get("output", "")[:300],
            "error": exec_result.get("error"),
        },
        "comparison": comparison,
    }


async def main():
    from run_extraction_sample import QUESTIONS

    # Init provider
    config = get_provider_config("api_vllm")
    served_model = os.environ.get("VLLM_SERVED_MODEL")
    if served_model:
        config["model_path"] = served_model
    provider = get_llm_provider(config)
    print(f"Provider: {config.get('model_path', 'api_vllm')}")

    all_results = []
    total_start = time.time()

    for i, q in enumerate(QUESTIONS):
        qid = q.get("id", "?")

        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(QUESTIONS)}] {qid}: {q['prompt'][:50]}...")
        start = time.time()

        result = await solve_with_code(provider, q)
        elapsed = time.time() - start
        result["elapsed"] = elapsed
        all_results.append(result)

        comp = result["comparison"]
        r_ok = "Y" if comp["reasoning_correct"] else "N"
        c_ok = "Y" if comp["code_correct"] else "N"
        match = "Y" if comp["consistent"] else "N"
        code_ok = "OK" if result["code"]["exec_success"] else "FAIL"

        print(f"  {elapsed:.1f}s | reasoning={comp['reasoning_answer']}({r_ok}) "
              f"code={comp['code_answer']}({c_ok}) match={match} "
              f"exec={code_ok} | truth={comp['ground_truth']}")

        if not result["code"]["exec_success"] and result["code"].get("error"):
            print(f"  Code error: {result['code']['error'][:100]}")

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"Total: {len(all_results)} questions in {total_elapsed:.1f}s")

    # Summary
    r_correct = sum(1 for r in all_results if r["comparison"]["reasoning_correct"])
    c_correct = sum(1 for r in all_results if r["comparison"]["code_correct"])
    consistent = sum(1 for r in all_results if r["comparison"]["consistent"])
    code_ok = sum(1 for r in all_results if r["code"]["exec_success"])
    total = len(all_results)

    print(f"\n--- Summary (blind solve, offline eval) ---")
    print(f"  Reasoning correct: {r_correct}/{total}")
    print(f"  Code correct:      {c_correct}/{total}")
    print(f"  Both consistent:   {consistent}/{total}")
    print(f"  Code executed OK:  {code_ok}/{total}")

    # Save
    output_path = os.path.join(os.path.dirname(__file__), "docs", "solve_with_code_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
