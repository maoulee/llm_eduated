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

PROMPT_REASON = """请解答以下{question_type}题目，给出你的推理过程和最终答案。

{stem}

{options}
正确答案：{answer}

请按以下JSON格式输出：
{{
  "reasoning": "你的详细推理过程",
  "answer": "你的最终答案（选项字母或计算结果）",
  "confidence": "high/medium/low"
}}"""


PROMPT_CODE = """请为以下{question_type}题目编写Python代码来独立计算并验证答案。

{stem}

{options}
正确答案：{answer}

要求：
1. 代码必须独立计算，不要依赖上面的"正确答案"
2. 逐步计算并打印中间结果
3. 最后打印最终答案
4. 只输出Python代码，不要输出其他内容

请用以下格式输出JSON：
{{
  "code": "完整的Python代码字符串",
  "expected_output": "你预期代码运行后得到的答案"
}}"""


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
    restricted_globals = {
        "__builtins__": __builtins__,
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


def compare_answers(reasoning_answer: str, code_output: str, ground_truth: str) -> Dict[str, Any]:
    """Compare reasoning answer, code output, and ground truth."""
    ra = extract_answer_letter(str(reasoning_answer))
    ca = extract_answer_letter(code_output)

    # For ground truth, extract key answer from potentially long text
    # First try to find option letter, then number
    gt_raw = str(ground_truth)
    gt = extract_answer_letter(gt_raw)
    # Special handling: if ground truth starts with a known option letter
    if gt_raw.strip() in ("A", "B", "C", "D"):
        gt = gt_raw.strip()
    # If ground truth contains answer_key info, extract key answer
    for pattern in [
        r'CRC校验码为(\d+)',
        r'余数为(\d+)',
        r'即([+-]?\d+)',
        r'叶子结点数为(\d+)',
        r'([+-]?\d+)',
    ]:
        m = re.search(pattern, gt_raw)
        if m:
            gt = m.group(1)
            break

    reasoning_correct = ra is not None and gt is not None and ra == gt
    code_correct = ca is not None and gt is not None and ca == gt
    consistent = ra is not None and ca is not None and ra == ca

    return {
        "reasoning_answer": ra,
        "code_answer": ca,
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
    extraction: Dict[str, Any],
) -> Dict[str, Any]:
    """Solve a question: reasoning pass + code pass + compare."""

    q_type = question.get("type", "单选题")
    stem = question.get("prompt", "")
    answer = question.get("answer", "")
    options = format_options(extraction)

    # --- Pass 1: Reasoning ---
    reason_prompt = PROMPT_REASON.format(
        question_type=q_type, stem=stem, options=options, answer=answer,
    )
    reason_messages = [[{"role": "user", "content": reason_prompt}]]
    reason_results = await provider.generate_json_batch(
        reason_messages, max_tokens=4096, enable_thinking=True,
    )
    reason_raw = reason_results[0] if reason_results else {}

    # Parse reasoning output
    reason_text = ""
    if isinstance(reason_raw, dict):
        reason_text = reason_raw.get("answer", reason_raw.get("reasoning", str(reason_raw)))
        if isinstance(reason_text, dict):
            reason_text = reason_text.get("reasoning", str(reason_text))
    reasoning_answer = reason_raw.get("answer", "") if isinstance(reason_raw, dict) else ""
    if isinstance(reasoning_answer, dict):
        reasoning_answer = str(reasoning_answer)

    # Try dict extraction if answer not clean
    if not reasoning_answer or reasoning_answer == str(reason_raw):
        parsed = extract_dict_from_text(str(reason_raw))
        if parsed:
            reasoning_answer = parsed.get("answer", "")
            reason_text = parsed.get("reasoning", reason_text)

    # --- Pass 2: Code generation ---
    code_prompt = PROMPT_CODE.format(
        question_type=q_type, stem=stem, options=options, answer=answer,
    )
    code_messages = [[{"role": "user", "content": code_prompt}]]
    code_results = await provider.generate_json_batch(
        code_messages, max_tokens=4096, enable_thinking=True,
    )
    code_raw = code_results[0] if code_results else {}

    # Extract code from model output
    code_output_text = ""
    if isinstance(code_raw, dict):
        code_output_text = code_raw.get("answer", code_raw.get("code", str(code_raw)))
    else:
        code_output_text = str(code_raw)
    if isinstance(code_output_text, dict):
        code_output_text = str(code_output_text)
    code = extract_code_from_text(code_output_text)

    # --- Pass 3: Execute code ---
    exec_result = {"success": False, "output": "", "error": "no code generated"}
    if code:
        exec_result = execute_code_safely(code)

    # --- Pass 4: Compare ---
    comparison = compare_answers(
        str(reasoning_answer),
        exec_result.get("output", ""),
        answer,
    )

    return {
        "question_id": question.get("id", "?"),
        "ground_truth": answer,
        "reasoning": {
            "answer": reasoning_answer,
            "confidence": reason_raw.get("confidence", "") if isinstance(reason_raw, dict) else "",
            "preview": str(reason_text)[:300],
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

    # Load extraction results
    extraction_path = os.path.join(os.path.dirname(__file__), "docs", "extraction_deep_v4.json")
    with open(extraction_path, encoding="utf-8") as f:
        extractions = json.load(f)

    ext_map = {r.get("question_id"): r for r in extractions if "error" not in r}

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
        ext = ext_map.get(qid)
        if not ext:
            print(f"[{i+1}] {qid}: no extraction data, skipping")
            continue

        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(QUESTIONS)}] {qid}: {q['prompt'][:50]}...")
        start = time.time()

        result = await solve_with_code(provider, q, ext)
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

    print(f"\n--- Summary ---")
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
