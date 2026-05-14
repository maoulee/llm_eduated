"""Patch: re-execute code with unrestricted env + re-run GLM subjective eval.

Reads existing batch_200_results.json, only re-runs:
  1. Code execution for code-routed questions (unrestricted exec)
  2. GLM subjective eval with improved prompt
"""

import asyncio
import json
import os
import re
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from typing import Any, Dict, List

sys.stdout.reconfigure(line_buffering=True)

SRC = "docs/batch_200_results.json"
DST = "docs/batch_200_results_v2.json"
PROGRESS = "docs/batch_200_v2_progress.log"

def log(msg: str):
    print(msg, flush=True)
    with open(PROGRESS, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

from dotenv import load_dotenv
load_dotenv()
from config import get_provider_config
from llm_providers_new import get_llm_provider


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


def execute_code(code: str) -> Dict[str, Any]:
    stdout_buf = StringIO()
    try:
        with redirect_stdout(stdout_buf):
            exec(code)
        return {"success": True, "output": stdout_buf.getvalue().strip()}
    except Exception:
        return {"success": False, "output": stdout_buf.getvalue().strip(),
                "error": traceback.format_exc()}


PROMPT_SUBJECTIVE = """你是一位考研408科目评分专家。请评估以下学生作答。

题目：
{question}

标准答案：
{reference}

学生作答：
{student}

评分要求：
- 逐小题评分
- 给出百分制得分（学生得分/满分×100）
- 只输出得分数字，放在最后

评分结果（0-100分）："""


async def main():
    with open(SRC, encoding="utf-8") as f:
        results = json.load(f)

    with open('/home/dev/full_question.json', encoding="utf-8") as f:
        questions = json.load(f)

    log(f"Loaded {len(results)} results")

    # ── Part 1: Re-execute code with unrestricted env ──
    code_rerun = 0
    code_fixed = 0
    for r in results:
        if r.get("route") != "code":
            continue
        idx = r["_index"]
        # Get the original model output (thinking + answer for code prompt)
        # We need the raw answer text to re-extract code
        # The stored extracted_code might be truncated, use the raw answer
        q = questions[idx]
        code_ans_text = r["code"].get("thinking_preview", "") + r["code"].get("extracted_code", "")

        # Actually we need the full answer text. Let's check what we have.
        code_preview = r["code"].get("extracted_code", "")
        if not code_preview:
            continue

        code_rerun += 1
        eres = execute_code(code_preview)
        old_success = r["code"]["exec_success"]

        r["code"]["exec_success"] = eres["success"]
        r["code"]["exec_output"] = eres.get("output", "")[:300]
        r["code"]["exec_error"] = eres.get("error")

        if eres["success"]:
            c_ans = extract_code_answer(eres["output"])
            r["code"]["code_answer"] = c_ans
            gt_key = r["gt_key"]
            is_mcq = r.get("question_type") == "单选题"
            r["code"]["correct"] = answers_match(c_ans, gt_key) if (is_mcq and c_ans) else None
            if not old_success:
                code_fixed += 1
                log(f"  [{idx}] FIXED: exec now OK, code_ans={c_ans[:20]}")
        else:
            r["code"]["code_answer"] = ""
            r["code"]["correct"] = None
            if not old_success:
                log(f"  [{idx}] still FAIL: {eres.get('error','')[:100]}")

        # Recompute final
        r_ans = r["reasoning"]["extracted_answer"]
        c_ans = r["code"].get("code_answer", "")
        is_mcq = r.get("question_type") == "单选题"
        gt_key = r["gt_key"]
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

    log(f"\nCode re-execution: {code_rerun} rerun, {code_fixed} newly fixed")

    # ── Part 2: Re-run GLM subjective eval ──
    subj_results = [r for r in results if r.get("question_type") == "主观题"]
    log(f"\nRe-evaluating {len(subj_results)} subjective questions with GLM...")

    try:
        config_glm = get_provider_config("glm5.1")
        provider_glm = get_llm_provider(config_glm)
        glm_ok = True
    except Exception as e:
        log(f"GLM unavailable: {e}")
        glm_ok = False

    if glm_ok:
        glm_msgs = []
        glm_indices = []
        for r in subj_results:
            idx = r["_index"]
            q = questions[idx]
            student = r["reasoning"]["answer"]
            if not student or student.startswith("Error"):
                continue
            prompt = PROMPT_SUBJECTIVE.format(
                question=q.get("prompt", ""),
                reference=q.get("answer", ""),
                student=student,
            )
            glm_msgs.append([{"role": "user", "content": prompt}])
            glm_indices.append(idx)

        log(f"  Sending {len(glm_msgs)} evals to GLM...")
        t0 = __import__("time").time()

        for start in range(0, len(glm_msgs), 4):
            chunk = glm_msgs[start:start+4]
            chunk_idx = glm_indices[start:start+4]
            try:
                batch = await provider_glm.generate_with_think_and_parse_batch(
                    chunk, max_token=2048, enable_thinking=True,
                )
            except Exception as e:
                log(f"  GLM batch failed: {e}")
                batch = [{}] * len(chunk)

            for j, idx in enumerate(chunk_idx):
                ar = batch[j] if j < len(batch) else {}
                a_full = ar.get("answer", "")

                # Extract score: try <score>X</score>, then last number
                score = None
                m = re.search(r'<score>\s*(\d+)\s*</score>', a_full)
                if m:
                    score = int(m.group(1))
                else:
                    # Fallback: last standalone number 0-100
                    nums = re.findall(r'\b(\d{1,3})\b', a_full)
                    if nums:
                        last = int(nums[-1])
                        if 0 <= last <= 100:
                            score = last

                results[idx]["subjective_eval"] = {
                    "score": score,
                    "evaluation": a_full[:500],
                }
                log(f"  [{idx}] GLM score: {score}")

            await __import__("asyncio").sleep(1)

        log(f"  GLM done in {__import__('time').time()-t0:.0f}s")

    # ── Summary ──
    mcq = [r for r in results if r.get("question_type") == "单选题"]
    subj = [r for r in results if r.get("question_type") == "主观题"]
    n_code = sum(1 for r in results if r.get("route") == "code")

    r_ok = sum(1 for r in mcq if r["reasoning"]["correct"])
    c_ok = sum(1 for r in mcq if r["code"].get("correct"))
    c_exec = sum(1 for r in results if r["code"]["exec_success"])
    cons = sum(1 for r in results if r["comparison"]["consistent"])
    f_ok = sum(1 for r in mcq if r["final"]["correct"])

    log(f"\n{'='*60}")
    log(f"V2 SUMMARY ({len(results)} questions)")
    log(f"{'='*60}")
    log(f"  MCQ ({len(mcq)}):")
    log(f"    Reasoning correct:  {r_ok}/{len(mcq)} ({100*r_ok/len(mcq):.1f}%)")
    log(f"    Code correct:       {c_ok}/{n_code} ({100*c_ok/n_code:.1f}% of code-routed)")
    log(f"    Code executed OK:   {c_exec}/{n_code} ({100*c_exec/n_code:.1f}%)")
    log(f"    Consistent:         {cons}/{n_code}")
    log(f"    Final correct:      {f_ok}/{len(mcq)} ({100*f_ok/len(mcq):.1f}%)")

    scored = [r for r in subj if r.get("subjective_eval", {}).get("score") is not None]
    if scored:
        avg = sum(r["subjective_eval"]["score"] for r in scored) / len(scored)
        log(f"  Subjective ({len(subj)}): avg score {avg:.1f}/100 ({len(scored)} evaluated)")

    # Year breakdown
    year_stats = {}
    for r in results:
        m = re.search(r'\[(\d{4})年', r.get("question_preview", ""))
        year = m.group(1) if m else "?"
        if year not in year_stats:
            year_stats[year] = {"total": 0, "mcq": 0, "mcq_ok": 0}
        year_stats[year]["total"] += 1
        if r.get("question_type") == "单选题":
            year_stats[year]["mcq"] += 1
            if r["final"].get("correct"):
                year_stats[year]["mcq_ok"] += 1

    log(f"\n  By year:")
    for y in sorted(year_stats):
        s = year_stats[y]
        pct = 100*s["mcq_ok"]/s["mcq"] if s["mcq"] else 0
        log(f"    {y}: {s['mcq_ok']}/{s['mcq']} ({pct:.0f}%)")

    with open(DST, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log(f"\nSaved to {DST}")


if __name__ == "__main__":
    asyncio.run(main())
