"""Experiment 3: Knowledge injection (Setting 2 + injection = Setting 3).

Uses extraction results from Experiment 2 to inject knowledge into the solve prompt.

Setting 2: reasoning + code (no knowledge)
Setting 3: reasoning + code (with knowledge injection from extraction)

Results saved to docs/experiment_3_results.json
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

PROMPT_SETTING3_REASON = """请解答以下题目。这是真题，不要质疑题目的合理性，直接推理作答。将最终答案放在 \\boxed{{}} 中。

参考知识点：
{knowledge_summary}

题目：
{raw_question}"""


PROMPT_SETTING3_CODE = """请为以下题目编写Python代码来独立计算答案。这是真题，不要质疑题目。

参考知识点：
{knowledge_summary}

题目：
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


PROMPT_SETTING2_REASON = """请解答以下题目。这是真题，不要质疑题目的合理性，直接推理作答。将最终答案放在 \\boxed{{}} 中。

{raw_question}"""


PROMPT_SETTING2_CODE = """请为以下题目编写Python代码来独立计算答案。这是真题，不要质疑题目。

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
    for match in re.finditer(r"```(?:python)?\s*\n?(.*?)```", text, re.DOTALL):
        return match.group(1).strip()

    parsed = _extract_xml_tags(text)
    if "code" in parsed:
        return parsed["code"]

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

    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    if lines:
        last = lines[-1]
        m = re.search(r'\b([A-D])\b', last, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        m = re.search(r'[-+]?\d+(?:\.\d+)?', last)
        if m:
            return m.group(0)

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


def get_ground_truth_key(answer: str) -> str:
    """Extract the key value from a ground truth answer."""
    gt = normalize_answer(answer)
    for pattern in [r'CRC校验码为(\d+)', r'余数为(\d+)', r'即([+-]?\d+)', r'叶子结点数为(\d+)', r'([+-]?\d+)']:
        m = re.search(pattern, str(answer))
        if m:
            return m.group(1)
    return gt


# ---------------------------------------------------------------------------
# Knowledge summary builder
# ---------------------------------------------------------------------------

def build_knowledge_summary(extraction: Dict[str, Any]) -> str:
    """Build natural language knowledge summary from extraction results.

    Format:
        - 知识名称: 描述
        - 机制名称: 如何影响推导
    """
    parts = []

    ku = extraction.get("knowledge_units", {})
    if isinstance(ku, dict):
        for unit in ku.get("knowledge_units", []):
            if isinstance(unit, dict):
                name = unit.get("name", "")
                desc = unit.get("description", "")
                if name:
                    parts.append(f"- 知识: {name}: {desc}")

        for mech in ku.get("mechanisms", []):
            if isinstance(mech, dict):
                name = mech.get("name", "")
                desc = mech.get("description", "")
                affects = mech.get("affects_what", "")
                if name:
                    detail = desc
                    if affects:
                        detail += f" (影响: {affects})"
                    parts.append(f"- 机制: {name}: {detail}")

    # Also include relevant trigger rules as context hints
    tr = extraction.get("trigger_rules", {})
    if isinstance(tr, dict):
        for rule in tr.get("trigger_rules", []):
            if isinstance(rule, dict):
                name = rule.get("name", "")
                condition = rule.get("condition", "")
                if name and condition:
                    parts.append(f"- 触发条件: {name}: {condition}")

    if not parts:
        return "（未能提取到知识点）"

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Setting 2: Reasoning + Code (no knowledge) — re-run for fair comparison
# ---------------------------------------------------------------------------

async def run_setting2(provider, question: Dict[str, Any]) -> Dict[str, Any]:
    """Setting 2: Reasoning + code without knowledge injection."""
    raw_question = question.get("prompt", "")
    ground_truth = question.get("answer", "")

    start = time.time()

    # Reasoning pass
    reason_prompt = PROMPT_SETTING2_REASON.format(raw_question=raw_question)
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

    # Code pass
    code_prompt = PROMPT_SETTING2_CODE.format(raw_question=raw_question)
    code_messages = [[{"role": "user", "content": code_prompt}]]
    code_results = await provider.generate_with_think_and_parse_batch(
        code_messages, max_token=4096, enable_thinking=True,
    )
    code_raw = code_results[0] if code_results else {}
    code_output_text = code_raw.get("answer", "") if isinstance(code_raw, dict) else ""

    code = extract_code_from_text(code_output_text) or ""
    if not code:
        code = _extract_xml_tags(code_output_text).get("code", "")

    # Execute
    exec_result = {"success": False, "output": "", "error": "no code generated"}
    if code:
        exec_result = execute_code_safely(code)

    code_answer = ""
    if exec_result.get("success"):
        code_answer = extract_answer_letter(exec_result.get("output", "")) or ""

    elapsed = time.time() - start

    gt = get_ground_truth_key(ground_truth)
    return {
        "reasoning_answer": reasoning_answer,
        "reasoning_correct": normalize_answer(reasoning_answer) == gt if reasoning_answer else False,
        "code_answer": code_answer,
        "code_correct": normalize_answer(code_answer) == gt if code_answer else False,
        "code_executed": exec_result.get("success", False),
        "consistent": normalize_answer(reasoning_answer) == normalize_answer(code_answer) if (reasoning_answer and code_answer) else False,
        "time": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# Setting 3: Knowledge injection + Reasoning + Code
# ---------------------------------------------------------------------------

async def run_setting3(
    provider,
    question: Dict[str, Any],
    knowledge_summary: str,
) -> Dict[str, Any]:
    """Setting 3: Knowledge injection + reasoning + code."""
    raw_question = question.get("prompt", "")
    ground_truth = question.get("answer", "")

    start = time.time()

    # Reasoning pass with knowledge
    reason_prompt = PROMPT_SETTING3_REASON.format(
        knowledge_summary=knowledge_summary,
        raw_question=raw_question,
    )
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

    # Code pass with knowledge
    code_prompt = PROMPT_SETTING3_CODE.format(
        knowledge_summary=knowledge_summary,
        raw_question=raw_question,
    )
    code_messages = [[{"role": "user", "content": code_prompt}]]
    code_results = await provider.generate_with_think_and_parse_batch(
        code_messages, max_token=4096, enable_thinking=True,
    )
    code_raw = code_results[0] if code_results else {}
    code_output_text = code_raw.get("answer", "") if isinstance(code_raw, dict) else ""

    code = extract_code_from_text(code_output_text) or ""
    if not code:
        code = _extract_xml_tags(code_output_text).get("code", "")

    # Execute
    exec_result = {"success": False, "output": "", "error": "no code generated"}
    if code:
        exec_result = execute_code_safely(code)

    code_answer = ""
    if exec_result.get("success"):
        code_answer = extract_answer_letter(exec_result.get("output", "")) or ""

    elapsed = time.time() - start

    gt = get_ground_truth_key(ground_truth)
    return {
        "reasoning_answer": reasoning_answer,
        "reasoning_correct": normalize_answer(reasoning_answer) == gt if reasoning_answer else False,
        "code_answer": code_answer,
        "code_correct": normalize_answer(code_answer) == gt if code_answer else False,
        "code_executed": exec_result.get("success", False),
        "consistent": normalize_answer(reasoning_answer) == normalize_answer(code_answer) if (reasoning_answer and code_answer) else False,
        "time": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# Load extraction results
# ---------------------------------------------------------------------------

def load_extraction_results() -> Dict[str, Dict[str, Any]]:
    """Load Experiment 2 results, keyed by question_id."""
    exp2_path = os.path.join(os.path.dirname(__file__), "docs", "experiment_2_results.json")
    if not os.path.exists(exp2_path):
        print(f"WARNING: {exp2_path} not found. Run experiment 2 first.")
        return {}

    with open(exp2_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    # The experiment 2 results are summary-level. We need the full extraction
    # from the saved Markdown/JSON files. Try loading the pipeline output directly.
    extraction_map = {}
    for item in results:
        qid = item.get("question_id", "")
        if not qid:
            continue
        extraction_map[qid] = item

    return extraction_map


def load_full_extractions() -> Dict[str, Dict[str, Any]]:
    """Load the full extraction pipeline outputs for knowledge injection.

    Tries to load from the saved per-question JSON in docs/extractions/,
    or falls back to re-reading the Experiment 2 raw pipeline output.
    """
    extractions_dir = os.path.join(os.path.dirname(__file__), "docs", "extractions")

    # Check for extraction_sample_results.json (the raw pipeline output)
    raw_path = os.path.join(os.path.dirname(__file__), "docs", "extraction_sample_results.json")
    if not os.path.exists(raw_path):
        # Try other possible names
        for candidate in ["extraction_sample_api_vllm.json", "extraction_deep_results.json"]:
            alt_path = os.path.join(os.path.dirname(__file__), "docs", candidate)
            if os.path.exists(alt_path):
                raw_path = alt_path
                break

    extraction_map = {}
    if os.path.exists(raw_path):
        with open(raw_path, "r", encoding="utf-8") as f:
            results = json.load(f)
        for item in results:
            qid = item.get("question_id", "")
            if qid:
                extraction_map[qid] = item

    return extraction_map


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

    # Load extraction results from Experiment 2
    exp2_results = load_extraction_results()
    full_extractions = load_full_extractions()

    has_extractions = bool(full_extractions)
    if not has_extractions:
        print("\nWARNING: No full extraction results found. Run Experiment 2 first.")
        print("Knowledge injection will use empty context (degrading to Setting 2).\n")
    else:
        print(f"Loaded full extractions for {len(full_extractions)} questions")

    all_results = []
    total_start = time.time()

    for i, q in enumerate(QUESTIONS):
        qid = q.get("id", "?")
        ground_truth = q.get("answer", "")
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(QUESTIONS)}] {qid}: {q['prompt'][:50]}...")

        # Build knowledge summary from extraction
        extraction = full_extractions.get(qid, {})
        knowledge_summary = ""
        if extraction and "error" not in extraction:
            knowledge_summary = build_knowledge_summary(extraction)
            print(f"  Knowledge summary ({len(knowledge_summary)} chars):")
            for line in knowledge_summary.split("\n")[:5]:
                print(f"    {line}")
            if len(knowledge_summary.split("\n")) > 5:
                print(f"    ... ({len(knowledge_summary.split(chr(10))) - 5} more lines)")
        else:
            print(f"  No extraction available for {qid}, using empty knowledge")

        # Setting 2: reasoning + code (no knowledge)
        print(f"  Running Setting 2 (reasoning + code, no knowledge)...")
        s2 = await run_setting2(provider, q)
        r2_status = "CORRECT" if s2["reasoning_correct"] else "WRONG"
        c2_status = "CORRECT" if s2["code_correct"] else "WRONG"
        exec2 = "OK" if s2["code_executed"] else "FAIL"
        print(f"  S2: reasoning={s2['reasoning_answer']}({r2_status}) "
              f"code={s2['code_answer']}({c2_status}) exec={exec2} [{s2['time']:.1f}s]")

        # Setting 3: reasoning + code (with knowledge injection)
        print(f"  Running Setting 3 (reasoning + code, with knowledge)...")
        s3 = await run_setting3(provider, q, knowledge_summary)
        r3_status = "CORRECT" if s3["reasoning_correct"] else "WRONG"
        c3_status = "CORRECT" if s3["code_correct"] else "WRONG"
        exec3 = "OK" if s3["code_executed"] else "FAIL"
        print(f"  S3: reasoning={s3['reasoning_answer']}({r3_status}) "
              f"code={s3['code_answer']}({c3_status}) exec={exec3} [{s3['time']:.1f}s]")

        print(f"  Ground truth: {ground_truth}")

        # Track improvement
        gt = get_ground_truth_key(ground_truth)
        s2_any_correct = s2["reasoning_correct"] or s2["code_correct"]
        s3_any_correct = s3["reasoning_correct"] or s3["code_correct"]
        improvement = ""
        if s3_any_correct and not s2_any_correct:
            improvement = "IMPROVED"
        elif not s3_any_correct and s2_any_correct:
            improvement = "REGRESSED"
        elif s3_any_correct and s2_any_correct:
            improvement = "SAME (both correct)"
        else:
            improvement = "SAME (both wrong)"
        print(f"  Change: {improvement}")

        all_results.append({
            "question_id": qid,
            "ground_truth": ground_truth,
            "has_extraction": bool(knowledge_summary),
            "knowledge_summary_preview": knowledge_summary[:300] if knowledge_summary else "",
            "setting2": s2,
            "setting3": s3,
            "improvement": improvement,
        })

    total_elapsed = time.time() - total_start
    total = len(all_results)

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"Experiment 3 Summary ({total} questions, {total_elapsed:.1f}s total)")
    print(f"{'='*60}")

    # Setting 2 stats
    s2_r = sum(1 for r in all_results if r["setting2"]["reasoning_correct"])
    s2_c = sum(1 for r in all_results if r["setting2"]["code_correct"])
    s2_cons = sum(1 for r in all_results if r["setting2"]["consistent"])

    # Setting 3 stats
    s3_r = sum(1 for r in all_results if r["setting3"]["reasoning_correct"])
    s3_c = sum(1 for r in all_results if r["setting3"]["code_correct"])
    s3_cons = sum(1 for r in all_results if r["setting3"]["consistent"])

    # Improvement tracking
    improved = sum(1 for r in all_results if r["improvement"] == "IMPROVED")
    regressed = sum(1 for r in all_results if r["improvement"] == "REGRESSED")
    same_both = sum(1 for r in all_results if "SAME" in r["improvement"])

    print(f"\n  Setting 2 (no knowledge):")
    print(f"    Reasoning correct:  {s2_r}/{total}")
    print(f"    Code correct:       {s2_c}/{total}")
    print(f"    Both consistent:    {s2_cons}/{total}")

    print(f"\n  Setting 3 (with knowledge injection):")
    print(f"    Reasoning correct:  {s3_r}/{total}")
    print(f"    Code correct:       {s3_c}/{total}")
    print(f"    Both consistent:    {s3_cons}/{total}")

    print(f"\n  Improvement analysis:")
    print(f"    Improved:    {improved}/{total}")
    print(f"    Regressed:   {regressed}/{total}")
    print(f"    Same:        {same_both}/{total}")

    # Per-question breakdown
    print(f"\n  Per-question comparison:")
    for r in all_results:
        qid = r["question_id"]
        s2_r_ok = "Y" if r["setting2"]["reasoning_correct"] else "N"
        s2_c_ok = "Y" if r["setting2"]["code_correct"] else "N"
        s3_r_ok = "Y" if r["setting3"]["reasoning_correct"] else "N"
        s3_c_ok = "Y" if r["setting3"]["code_correct"] else "N"
        inj = "+" if r["has_extraction"] else "-"
        print(f"    {qid}: S2(R={s2_r_ok},C={s2_c_ok}) -> S3(R={s3_r_ok},C={s3_c_ok}) [{inj}] {r['improvement']}")

    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "docs", "experiment_3_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
