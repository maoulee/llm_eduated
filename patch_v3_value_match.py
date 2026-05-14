"""Patch V3: Re-generate code with VALUE-first output + post-hoc option matching.

Key changes from V2:
  1. Code prompt tells model to print the COMPUTED VALUE, not option letter
  2. Post-processing extracts options from question and matches computed value
  3. Fallback to letter matching if value matching fails
"""

import asyncio
import json
import os
import re
import sys
import time
import traceback
from contextlib import redirect_stdout
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

sys.stdout.reconfigure(line_buffering=True)

SRC = "docs/batch_200_results_v2.json"
DST = "docs/batch_200_results_v3.json"
PROGRESS = "docs/batch_200_v3_progress.log"
DATA_PATH = os.environ.get("SEED_QUESTIONS_FILE", "/home/dev/full_question.json")
BATCH_SIZE = 20


def log(msg: str):
    print(msg, flush=True)
    with open(PROGRESS, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


from dotenv import load_dotenv
load_dotenv()
from config import get_provider_config
from llm_providers_new import get_llm_provider


PROMPT_CODE_V3 = """请为以下题目编写Python代码来独立计算答案。这是真题，不要质疑题目。

{raw_question}

代码规范：
- 完整可执行的Python代码，从第一列开始写（无前导缩进）
- 中间步骤用 print() 逐行输出
- 最后一行 print 计算得到的最终数值或结果（不要输出选项字母）
  - 例如：print("C1040000H")  而不是 print("A")
  - 例如：print("FFFFFFFFFF9EH")  而不是 print("C")
  - 例如：print(32)  而不是 print("B")
  - 如果是判断哪个选项错误/正确，print该选项的字母，如 print("B")
- 只用Python内置函数和标准库
- 禁用 input()、open()

请只输出代码：
```python
# 你的代码
```"""


def extract_code_from_text(text: str):
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
    return None


def extract_code_answer(output: str) -> str:
    lines = [l.strip() for l in output.split('\n') if l.strip()]
    return lines[-1] if lines else ""


def extract_gt_key(gt: str) -> str:
    gt = str(gt).strip()
    m = re.search(r'【参考答案】\s*([A-D])', gt)
    if m:
        return m.group(1).upper()
    if re.match(r'^[A-Da-d]$', gt):
        return gt.upper()
    nums = re.findall(r'[-+]?\d+(?:\.\d+)?', gt)
    return nums[-1] if nums else gt


def answers_match(a: str, b: str) -> bool:
    sa, sb = a.strip(), b.strip()
    if not sa or not sb:
        return False
    if sa.upper() == sb.upper():
        return True
    na = re.search(r'[-+]?\d+(?:\.\d+)?', sa)
    nb = re.search(r'[-+]?\d+(?:\.\d+)?', sb)
    if na and nb:
        try:
            if float(na.group(0)) == float(nb.group(0)):
                return True
        except ValueError:
            pass
    return False


def parse_options(prompt: str) -> Dict[str, str]:
    """Extract option letter -> option text from question prompt."""
    options = {}
    # Match patterns like A.xxx B.xxx or A、xxx or A)xxx
    for m in re.finditer(r'([A-D])[.．、)\s]+(.+?)(?=\s*[A-D][.．、)\s]+|$)', prompt, re.DOTALL):
        letter = m.group(1)
        text = m.group(2).strip()
        # Clean up
        text = re.sub(r'\s*\\n\s*', ' ', text)
        text = text.strip()
        if text:
            options[letter] = text
    return options


def normalize_for_matching(s: str) -> str:
    """Normalize a string for comparison: remove spaces, lowercase, strip H/h suffix."""
    s = s.strip().upper()
    s = re.sub(r'\s+', '', s)  # remove all whitespace
    s = s.rstrip('H')  # strip hex suffix
    return s


def match_value_to_option(code_value: str, options: Dict[str, str]) -> Optional[str]:
    """Match a computed value to the best matching option. Returns option letter or None."""
    if not code_value or not options:
        return None

    cv = code_value.strip()

    # 1. If code output is a single letter A-D, return it directly
    if re.match(r'^[A-Da-d]$', cv):
        return cv.upper()

    cv_norm = normalize_for_matching(cv)

    # 2. Exact normalized match against option text
    for letter, text in options.items():
        if normalize_for_matching(text) == cv_norm:
            return letter

    # 3. Numeric match
    try:
        cv_num = float(cv)
        for letter, text in options.items():
            nums = re.findall(r'[-+]?\d+(?:\.\d+)?', text)
            for n in nums:
                if float(n) == cv_num:
                    return letter
    except (ValueError, IndexError):
        pass

    # 4. Code value is a substring of option text (or vice versa)
    for letter, text in options.items():
        opt_norm = normalize_for_matching(text)
        if len(cv_norm) >= 4 and cv_norm in opt_norm:
            return letter
        if len(opt_norm) >= 4 and opt_norm in cv_norm:
            return letter

    # 5. Extract hex/numeric from code value and try matching
    hex_m = re.search(r'[0-9A-Fa-f]{4,}', cv)
    if hex_m:
        cv_hex = hex_m.group(0).upper()
        for letter, text in options.items():
            opt_hex = re.findall(r'[0-9A-Fa-f]{4,}', text)
            if any(cv_hex == h.upper() for h in opt_hex):
                return letter

    return None


def execute_code(code: str) -> Dict[str, Any]:
    stdout_buf = StringIO()
    try:
        with redirect_stdout(stdout_buf):
            exec(code)
        return {"success": True, "output": stdout_buf.getvalue().strip()}
    except Exception:
        return {"success": False, "output": stdout_buf.getvalue().strip(),
                "error": traceback.format_exc()}


async def main():
    with open(SRC, encoding="utf-8") as f:
        results = json.load(f)
    with open(DATA_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    log(f"Loaded {len(results)} results, {len(questions)} questions")

    # Find code-routed MCQs
    code_items = []
    for r in results:
        if r.get("route") != "code":
            continue
        if r.get("question_type") != "单选题":
            continue
        idx = r["_index"]
        q = questions[idx]
        code_items.append((idx, r, q))

    log(f"Code-routed MCQs: {len(code_items)}")

    # Init vLLM
    config = get_provider_config("api_vllm")
    config["request_timeout"] = 900.0
    provider = get_llm_provider(config)

    # Re-generate code in batches
    all_new_code = {}
    total = len(code_items)

    for batch_start in range(0, total, BATCH_SIZE):
        batch = code_items[batch_start:batch_start + BATCH_SIZE]
        n = len(batch)
        log(f"\nBatch [{batch_start}-{batch_start+n-1}]: sending {n} code prompts...")

        msgs = []
        for idx, r, q in batch:
            cp = PROMPT_CODE_V3.format(raw_question=q.get("prompt", ""))
            msgs.append([{"role": "user", "content": cp}])

        t0 = time.time()
        try:
            batch_res = await provider.generate_with_think_and_parse_batch(
                msgs, max_token=8192, enable_thinking=True,
            )
        except Exception as e:
            log(f"  FAILED: {e}, retrying...")
            await asyncio.sleep(10)
            batch_res = await provider.generate_with_think_and_parse_batch(
                msgs, max_token=8192, enable_thinking=True,
            )

        log(f"  vLLM done in {time.time()-t0:.0f}s")

        for j, (idx, r, q) in enumerate(batch):
            cr = batch_res[j] if j < len(batch_res) else {}
            c_full = cr.get("answer", "")
            code = extract_code_from_text(c_full) or ""

            if code:
                eres = execute_code(code)
                raw_answer = extract_code_answer(eres["output"]) if eres["success"] else ""
            else:
                eres = {"success": False, "output": "", "error": "no code"}
                raw_answer = ""

            # Value-to-option matching
            prompt = q.get("prompt", "")
            options = parse_options(prompt)
            matched_option = match_value_to_option(raw_answer, options)

            all_new_code[idx] = {
                "code": code,
                "exec_success": eres["success"],
                "exec_output": eres.get("output", "")[:500],
                "exec_error": eres.get("error"),
                "raw_code_answer": raw_answer,
                "matched_option": matched_option or "",
                "options_parsed": options,
                "raw_answer": c_full[:500],
            }

            gt_key = r["gt_key"]
            is_mcq = r.get("question_type") == "单选题"
            c_correct = answers_match(matched_option or raw_answer, gt_key) if (is_mcq and (matched_option or raw_answer)) else None
            exec_st = "OK" if eres["success"] else "FAIL"
            match_st = f"->{matched_option}" if matched_option and matched_option != raw_answer else ""
            log(f"  [{idx}] exec={exec_st} raw={raw_answer[:20]:<20} match={match_st} gt={gt_key} {'Y' if c_correct else 'N'}")

    # Update results
    log(f"\nUpdating results...")
    improved = 0
    regressed = 0
    for r in results:
        idx = r["_index"]
        if idx not in all_new_code:
            continue
        nc = all_new_code[idx]
        gt_key = r["gt_key"]
        is_mcq = r.get("question_type") == "单选题"

        old_code_correct = r["code"].get("correct")

        r["code"]["extracted_code"] = nc["code"][:1000] if nc["code"] else ""
        r["code"]["exec_success"] = nc["exec_success"]
        r["code"]["exec_output"] = nc["exec_output"]
        r["code"]["exec_error"] = nc["exec_error"]
        r["code"]["raw_code_answer"] = nc["raw_code_answer"]
        r["code"]["matched_option"] = nc["matched_option"]
        r["code"]["code_answer"] = nc["matched_option"] or nc["raw_code_answer"]

        c_ans = r["code"]["code_answer"]
        new_code_correct = answers_match(c_ans, gt_key) if (is_mcq and c_ans) else None
        r["code"]["correct"] = new_code_correct

        if old_code_correct == False and new_code_correct == True:
            improved += 1
            log(f"  IMPROVED [{idx}]: {old_code_correct} -> {new_code_correct}")
        elif old_code_correct == True and new_code_correct == False:
            regressed += 1
            log(f"  REGRESSED [{idx}]: {old_code_correct} -> {new_code_correct}")

        # Recompute comparison and final
        r_ans = r["reasoning"]["extracted_answer"]
        consistent = answers_match(r_ans, c_ans) if (r_ans and c_ans) else False
        r["comparison"]["consistent"] = consistent

        if consistent:
            final, src = r_ans, "consensus"
        elif r_ans and c_ans:
            final, src = r_ans, "reasoning_only"
        elif r_ans:
            final, src = r_ans, "reasoning_only"
        elif c_ans:
            final, src = c_ans, "code_only"
        else:
            final, src = "", "none"
        r["final"] = {"answer": final, "source": src,
                      "correct": answers_match(final, gt_key) if (is_mcq and final) else None}

    # Summary
    mcq = [r for r in results if r.get("question_type") == "单选题"]
    n_code = sum(1 for r in results if r.get("route") == "code")

    r_ok = sum(1 for r in mcq if r["reasoning"]["correct"])
    c_ok = sum(1 for r in mcq if r["code"].get("correct"))
    c_exec = sum(1 for r in results if r["code"]["exec_success"])
    cons = sum(1 for r in results if r["comparison"]["consistent"])
    f_ok = sum(1 for r in mcq if r["final"]["correct"])

    log(f"\n{'='*60}")
    log(f"V3 SUMMARY ({len(results)} questions)")
    log(f"{'='*60}")
    log(f"  MCQ ({len(mcq)}):")
    log(f"    Reasoning correct:  {r_ok}/{len(mcq)} ({100*r_ok/len(mcq):.1f}%)")
    log(f"    Code correct:       {c_ok}/{n_code} ({100*c_ok/n_code:.1f}% of code-routed)")
    log(f"    Code executed OK:   {c_exec}/{n_code} ({100*c_exec/n_code:.1f}%)")
    log(f"    Consistent:         {cons}/{n_code}")
    log(f"    Final correct:      {f_ok}/{len(mcq)} ({100*f_ok/len(mcq):.1f}%)")
    log(f"    Improved:           {improved}")
    log(f"    Regressed:          {regressed}")

    code_rescue = sum(1 for r in mcq if not r["reasoning"]["correct"] and r["final"]["correct"])
    code_hurt = sum(1 for r in mcq if r["reasoning"]["correct"] and not r["final"]["correct"])
    log(f"    Code rescued wrong reasoning: {code_rescue}")
    log(f"    Code hurt correct reasoning:  {code_hurt}")

    # Detail of code-wrong cases
    log(f"\n  Code-wrong MCQs:")
    for r in mcq:
        if r.get("route") != "code":
            continue
        if r["code"].get("correct") == False:
            idx = r["_index"]
            gt = r["gt_key"]
            raw = r["code"].get("raw_code_answer", "")
            matched = r["code"].get("matched_option", "")
            opts = r["code"].get("options_parsed", {})
            log(f"    [{idx}] gt={gt} raw={raw[:30]} matched={matched}")
            for letter, text in opts.items():
                log(f"      {letter}: {text[:60]}")

    year_stats = {}
    for r in results:
        m = re.search(r'\[(\d{4})年', r.get("question_preview", ""))
        y = m.group(1) if m else "?"
        if y not in year_stats:
            year_stats[y] = {"mcq": 0, "ok": 0}
        if r.get("question_type") == "单选题":
            year_stats[y]["mcq"] += 1
            if r["final"].get("correct"):
                year_stats[y]["ok"] += 1

    log(f"\n  By year:")
    for y in sorted(year_stats):
        s = year_stats[y]
        pct = 100*s["ok"]/s["mcq"] if s["mcq"] else 0
        log(f"    {y}: {s['ok']}/{s['mcq']} ({pct:.0f}%)")

    with open(DST, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log(f"\nSaved to {DST}")


if __name__ == "__main__":
    asyncio.run(main())
