"""
Dual-path solver: reasoning + code execution with GLM arbitration.

Flow:
  1. 27B reasoning call → extract <answer> tag
  2. 27B code call → execute → last line = answer
  3. Compare: consistent → output, inconsistent → GLM arbitrates

All 2n calls batched in one vLLM request for throughput.
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

PROMPT_REASON = """请解答以下题目。这是真题，不要质疑题目，直接推理作答。

推理过程写在 <answer> 标签外面，最终答案放在 <answer> 标签内。
- <answer> 标签内只写答案本身，不要加说明、标点、单位
- 选择题填选项字母：<answer>A</answer>
- 数值题填十进制数值：<answer>350</answer>、<answer>-127</answer>、<answer>0.5</answer>
- 不要填二进制/十六进制，统一用十进制

{raw_question}"""

PROMPT_CODE = """请为以下题目编写Python代码来独立计算答案。这是真题，不要质疑题目。

{raw_question}

代码规范：
- 完整可执行的Python代码，从第一列开始写（无前导缩进）
- 中间步骤用 print() 逐行输出
- 最后一行 print 最终答案：
  - 选择题：print选项字母，如 print("A")
  - 数值题：print数值，如 print(350)
- 只用Python内置函数和math模块
- 禁用 input()、open()、__import__

请只输出代码：
```python
# 你的代码
```"""

PROMPT_ARBiter = """你是一个仲裁裁判。两个独立通道对同一题目给出了不同答案，请判断哪个正确。

题目：
{raw_question}

通道A（推理答案）：{reasoning_answer}
通道B（代码计算答案）：{code_answer}

请分析两个答案，给出你认为正确的最终答案。
将答案放在 <answer> 标签内，如 <answer>A</answer> 或 <answer>350</answer>。
简要说明理由。"""


# ---------------------------------------------------------------------------
# Generic answer extraction
# ---------------------------------------------------------------------------

def extract_answer_tag(text: str) -> str:
    """Extract answer from <answer>...</answer>. Fallback: \\boxed{} or last line."""
    m = re.search(r'<answer>\s*(.*?)\s*</answer>', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Fallback: \boxed{}
    m = re.search(r'\\boxed\{([^}]+)\}', text)
    if m:
        return m.group(1).strip()
    # Fallback: last non-empty line
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    return lines[-1][:80] if lines else ""


def extract_code_from_text(text: str) -> Optional[str]:
    """Extract Python code from ```python blocks with auto-dedent."""
    for match in re.finditer(r"```(?:python)?\s*\n?(.*?)```", text, re.DOTALL):
        code = match.group(1)
        lines = code.split('\n')
        min_indent = float('inf')
        for line in lines:
            stripped = line.lstrip()
            if stripped:
                min_indent = min(min_indent, len(line) - len(stripped))
        if min_indent == float('inf'):
            min_indent = 0
        return '\n'.join(
            line[min_indent:] if len(line) >= min_indent else line
            for line in lines
        ).strip()
    # Try XML <code>
    m = re.search(r'<code>(.*?)</code>', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def extract_code_answer(output: str) -> str:
    """Extract answer from code output — last non-empty line."""
    lines = [l.strip() for l in output.split('\n') if l.strip()]
    return lines[-1] if lines else ""


def extract_gt_key(gt: str) -> str:
    """Extract the comparable key from ground truth.

    Generic rules (no question-specific regex):
    - Single letter A-D → use as-is
    - Otherwise → extract the last number (including optional sign and decimal)
    """
    gt = str(gt).strip()
    # Single option letter
    if re.match(r'^[A-Da-d]$', gt):
        return gt.upper()
    # Extract last number from descriptive GT
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?', gt)
    if nums:
        return nums[-1]
    return gt


def answers_match(a: str, b: str) -> bool:
    """Check if two answers match (case-insensitive string or numeric)."""
    sa, sb = a.strip(), b.strip()
    if not sa or not sb:
        return False
    if sa.upper() == sb.upper():
        return True
    # Numeric comparison (float to handle +8 vs 8)
    na = re.search(r'[-+]?\d+(?:\.\d+)?', sa)
    nb = re.search(r'[-+]?\d+(?:\.\d+)?', sb)
    if na and nb:
        try:
            if float(na.group(0)) == float(nb.group(0)):
                return True
        except ValueError:
            pass
    return False


# ---------------------------------------------------------------------------
# Code execution
# ---------------------------------------------------------------------------

def execute_code_safely(code: str) -> Dict[str, Any]:
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
    restricted_globals = {"__builtins__": SAFE_BUILTINS, "math": math}
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(code, restricted_globals)
        return {"success": True, "output": stdout_buf.getvalue().strip()}
    except Exception:
        return {"success": False, "output": stdout_buf.getvalue().strip(),
                "error": traceback.format_exc()}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    from run_extraction_sample import QUESTIONS

    # 27B provider
    config_27b = get_provider_config("api_vllm")
    served_model = os.environ.get("VLLM_SERVED_MODEL")
    if served_model:
        config_27b["model_path"] = served_model
    config_27b["request_timeout"] = 600.0
    provider_27b = get_llm_provider(config_27b)
    print(f"27B: {config_27b.get('model_path', 'api_vllm')}")

    # GLM provider
    glm_available = False
    try:
        config_glm = get_provider_config("glm5.1")
        provider_glm = get_llm_provider(config_glm)
        glm_available = True
        print(f"GLM: {config_glm.get('model_path', 'glm5.1')}")
    except Exception as e:
        print(f"GLM unavailable: {e}")

    total_start = time.time()
    n = len(QUESTIONS)

    # ── Phase 1: Batch all 2n prompts (reason + code) in one call ──
    print(f"\nPhase 1: Batch {n*2} prompts to vLLM...")
    all_messages = []
    prompts = []  # (reason_prompt, code_prompt) per question

    for q in QUESTIONS:
        rp = PROMPT_REASON.format(raw_question=q.get("prompt", ""))
        cp = PROMPT_CODE.format(raw_question=q.get("prompt", ""))
        prompts.append((rp, cp))
        all_messages.append([{"role": "user", "content": rp}])
        all_messages.append([{"role": "user", "content": cp}])

    t0 = time.time()
    batch = await provider_27b.generate_with_think_and_parse_batch(
        all_messages, max_token=8192, enable_thinking=True,
    )
    print(f"  vLLM batch done in {time.time()-t0:.0f}s")

    # ── Phase 2: Parse + execute + compare ──
    print(f"\nPhase 2: Parse results...")
    all_results = []
    need_arb = []

    for i, q in enumerate(QUESTIONS):
        qid = q.get("id", "?")
        gt = q.get("answer", "")
        gt_key = extract_gt_key(gt)

        # Reasoning result (index i*2)
        rr = batch[i*2] if i*2 < len(batch) else {}
        r_think = rr.get("think", "")
        r_full = rr.get("answer", "")
        r_ans = extract_answer_tag(r_full)

        # Code result (index i*2+1)
        cr = batch[i*2+1] if i*2+1 < len(batch) else {}
        c_think = cr.get("think", "")
        c_full = cr.get("answer", "")
        code = extract_code_from_text(c_full) or ""
        exec_res = {"success": False, "output": "", "error": "no code"}
        c_ans = ""
        if code:
            exec_res = execute_code_safely(code)
            if exec_res["success"]:
                c_ans = extract_code_answer(exec_res["output"])

        # Compare
        r_correct = answers_match(r_ans, gt_key)
        c_correct = answers_match(c_ans, gt_key)
        consistent = answers_match(r_ans, c_ans)

        print(f"  [{i+1}/{n}] {qid}: reason={r_ans[:20]}({'Y' if r_correct else 'N'}) "
              f"code={c_ans[:20]}({'Y' if c_correct else 'N'}) "
              f"cons={'Y' if consistent else 'N'} exec={'OK' if exec_res['success'] else 'FAIL'}")

        result = {
            "question_id": qid, "ground_truth": gt, "gt_key": gt_key,
            "reasoning": {
                "prompt": prompts[i][0], "thinking": r_think,
                "answer": r_full, "extracted_answer": r_ans, "correct": r_correct,
            },
            "code": {
                "prompt": prompts[i][1], "thinking": c_think,
                "answer": c_full, "extracted_code": code,
                "exec_success": exec_res.get("success", False),
                "exec_output": exec_res.get("output", ""),
                "exec_error": exec_res.get("error"),
                "code_answer": c_ans, "correct": c_correct,
            },
            "comparison": {
                "consistent": consistent,
                "reasoning_correct": r_correct,
                "code_correct": c_correct,
            },
        }

        if not consistent and r_ans and c_ans:
            need_arb.append((i, q, r_ans, c_ans))

        all_results.append(result)

    # ── Phase 3: GLM arbitration (batch) ──
    if need_arb and glm_available:
        print(f"\nPhase 3: GLM arbitration for {len(need_arb)} cases...")
        arb_msgs = []
        for idx, q, ra, ca in need_arb:
            p = PROMPT_ARBiter.format(raw_question=q.get("prompt", ""),
                                      reasoning_answer=ra, code_answer=ca)
            arb_msgs.append([{"role": "user", "content": p}])

        t0 = time.time()
        arb_batch = await provider_glm.generate_with_think_and_parse_batch(
            arb_msgs, max_token=2048, enable_thinking=True,
        )
        print(f"  GLM batch done in {time.time()-t0:.0f}s")

        for j, (idx, q, ra, ca) in enumerate(need_arb):
            ar = arb_batch[j] if j < len(arb_batch) else {}
            a_full = ar.get("answer", "")
            a_ans = extract_answer_tag(a_full)
            gt_key = extract_gt_key(q.get("answer", ""))

            all_results[idx]["arbitration"] = {
                "answer": a_ans, "correct": answers_match(a_ans, gt_key),
            }
            print(f"  [{idx+1}] {q.get('id','')}: arb={a_ans[:20]}({'Y' if answers_match(a_ans, gt_key) else 'N'})")

    # ── Final answers ──
    print(f"\nFinal answers:")
    for r in all_results:
        c = r["comparison"]
        arb = r.get("arbitration")
        if c["consistent"]:
            final, src = r["reasoning"]["extracted_answer"], "consensus"
        elif arb:
            final, src = arb["answer"], "arbitration"
        elif r["reasoning"]["extracted_answer"]:
            final, src = r["reasoning"]["extracted_answer"], "reasoning_only"
        else:
            final, src = r["code"].get("code_answer", ""), "code_only"

        correct = answers_match(final, r["gt_key"])
        r["final"] = {"answer": final, "source": src, "correct": correct}
        print(f"  {r['question_id']}: {final[:20]}({src}) {'OK' if correct else 'WRONG'}")

    # ── Summary ──
    elapsed = time.time() - total_start
    total = len(all_results)
    r_ok = sum(1 for r in all_results if r["reasoning"]["correct"])
    c_ok = sum(1 for r in all_results if r["code"]["correct"])
    c_exec = sum(1 for r in all_results if r["code"]["exec_success"])
    cons = sum(1 for r in all_results if r["comparison"]["consistent"])
    arb_n = sum(1 for r in all_results if r.get("arbitration"))
    f_ok = sum(1 for r in all_results if r["final"]["correct"])

    print(f"\n{'='*60}")
    print(f"Summary ({total} questions, {elapsed:.0f}s)")
    print(f"{'='*60}")
    print(f"  Reasoning correct:  {r_ok}/{total}")
    print(f"  Code correct:       {c_ok}/{total}")
    print(f"  Code executed OK:   {c_exec}/{total}")
    print(f"  Consistent:         {cons}/{total}")
    print(f"  Arbitrated:         {arb_n}/{total}")
    print(f"  Final correct:      {f_ok}/{total}")

    for r in all_results:
        c = r["comparison"]
        f = r["final"]
        print(f"  {r['question_id']}: R={'Y' if c['reasoning_correct'] else 'N'} C={'Y' if c['code_correct'] else 'N'} "
              f"cons={'Y' if c['consistent'] else 'N'} final={f['answer'][:20]}({f['source']}) "
              f"{'OK' if f['correct'] else 'WRONG'}")

    output_path = "docs/experiment_full_trace.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
