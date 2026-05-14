"""Batch test 195 questions with routed dual-path solver.

Architecture:
  - Phase 0: Route — classify each question as computational (needs code) or conceptual
  - Phase 1: vLLM batch — reasoning for ALL + code for computational only
  - Phase 2: Parse + execute code + compare answers
  - Phase 3: GLM 5.1 evaluates subjective questions

Batch 20 questions per vLLM call. Checkpoint after each batch.
"""

import asyncio
import json
import os
import re
import sys
import time
import traceback
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from typing import Any, Dict, List, Optional

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Progress log file for monitoring
_PROGRESS_LOG = "docs/batch_200_progress.log"

def log(msg: str):
    print(msg, flush=True)
    with open(_PROGRESS_LOG, "a", encoding="utf-8") as _f:
        _f.write(msg + "\n")

from dotenv import load_dotenv
load_dotenv()

from config import get_provider_config
from llm_providers_new import get_llm_provider


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BATCH_SIZE = 20
DATA_PATH = os.environ.get("SEED_QUESTIONS_FILE", "/home/dev/full_question.json")
OUTPUT_PATH = "docs/batch_200_results.json"
CHECKPOINT_PATH = "docs/batch_200_checkpoint.json"
VLLM_TIMEOUT = 900.0


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PROMPT_ROUTE = """判断以下题目是否需要编写代码来计算答案。

题目：
{raw_question}

分类标准：
- 需要代码（code）：涉及数值计算、位运算、CRC校验、浮点运算、地址映射计算、总线带宽计算等
- 概念推理（concept）：概念辨析、定性分析、对比选择、只需理解不需计算的题目

只回答一个词：code 或 concept"""

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

PROMPT_SUBJECTIVE_EVAL = """你是一位考研408科目评分专家。请评估以下学生的作答。

题目：
{question}

参考答案：
{reference_answer}

学生作答：
{student_answer}

请评估学生作答的质量：
1. 对每个小题分别评分（如果有多问）
2. 给出每部分的得分（0-满分）
3. 总结总体评价

将评分放在 <score> 标签内，格式为百分制得分：
<score>85</score>（表示获得85%的分数）"""


# ---------------------------------------------------------------------------
# Answer extraction
# ---------------------------------------------------------------------------

def extract_answer_tag(text: str, thinking: str = "") -> str:
    m = re.search(r'<answer>\s*(.*?)\s*</answer>', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r'\\boxed\{([^}]+)\}', text)
    if m:
        return m.group(1).strip()
    # If answer text is empty, try extracting from thinking
    if not text.strip() and thinking:
        # Look for common patterns in thinking: "选D", "答案是B", "选 A"
        for pat in [r'选\s*([A-D])\b', r'答案[是为]\s*([A-D])\b', r'因此.*选\s*([A-D])']:
            m = re.search(pat, thinking, re.IGNORECASE)
            if m:
                return m.group(1).upper()
        # Last resort: last number from thinking
        nums = re.findall(r'[-+]?\d+(?:\.\d+)?', thinking)
        if nums:
            return nums[-1]
    # Fallback: last non-empty line
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    return lines[-1][:80] if lines else ""


def extract_code_from_text(text: str) -> Optional[str]:
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
    m = re.search(r'<code>(.*?)</code>', text, re.DOTALL)
    if m:
        return m.group(1).strip()
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
    if nums:
        return nums[-1]
    return gt


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


# ---------------------------------------------------------------------------
# Code execution
# ---------------------------------------------------------------------------

def execute_code_safely(code: str) -> Dict[str, Any]:
    stdout_buf = StringIO()
    stderr_buf = StringIO()
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(code)
        return {"success": True, "output": stdout_buf.getvalue().strip()}
    except Exception:
        return {"success": False, "output": stdout_buf.getvalue().strip(),
                "error": traceback.format_exc()}


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

def save_checkpoint(results: Dict[int, Dict], path: str = CHECKPOINT_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def load_checkpoint(path: str = CHECKPOINT_PATH) -> Dict[int, Dict]:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # Convert string keys back to int
        return {int(k): v for k, v in data.items()}
    return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        questions = json.load(f)
    log(f"Loaded {len(questions)} questions from {DATA_PATH}")

    mcq_count = sum(1 for q in questions if q.get("type") == "单选题")
    subj_count = sum(1 for q in questions if q.get("type") == "主观题")
    log(f"  MCQ: {mcq_count}, Subjective: {subj_count}")

    # Init providers
    config_vllm = get_provider_config("api_vllm")
    config_vllm["request_timeout"] = VLLM_TIMEOUT
    provider_vllm = get_llm_provider(config_vllm)
    log(f"vLLM: {config_vllm.get('model_path', 'api_vllm')}")

    glm_available = False
    provider_glm = None
    try:
        config_glm = get_provider_config("glm5.1")
        provider_glm = get_llm_provider(config_glm)
        glm_available = True
        log("GLM: available")
    except Exception as e:
        log(f"GLM: unavailable ({e})")

    # Resume from checkpoint
    results_map = load_checkpoint()
    log(f"Checkpoint: {len(results_map)} already done")

    total_start = time.time()
    remaining = [(i, q) for i, q in enumerate(questions) if i not in results_map]

    if not remaining:
        log("All questions already completed!")
    else:
        batch_num = 0
        for batch_start in range(0, len(remaining), BATCH_SIZE):
            batch_items = remaining[batch_start:batch_start + BATCH_SIZE]
            batch_num += 1
            n = len(batch_items)
            log(f"\n{'='*60}")
            log(f"Batch {batch_num}: {n} questions [{batch_items[0][0]}-{batch_items[-1][0]}]")
            t0 = time.time()

            # ── Step 0: Route — classify computational vs conceptual ──
            route_msgs = []
            for idx, q in batch_items:
                rp = PROMPT_ROUTE.format(raw_question=q.get("prompt", ""))
                route_msgs.append([{"role": "user", "content": rp}])

            log(f"  Routing {n} questions...")
            try:
                route_results = await provider_vllm.generate_with_think_and_parse_batch(
                    route_msgs, max_token=64, enable_thinking=False,
                )
            except Exception as e:
                log(f"  Route failed: {e}, defaulting all to code")
                route_results = [{"think": "", "answer": "code"}] * n

            # Parse routes
            routes = []
            for j, (idx, q) in enumerate(batch_items):
                r = route_results[j] if j < len(route_results) else {}
                ans = r.get("answer", "code").strip().lower()
                if "concept" in ans:
                    route = "concept"
                else:
                    route = "code"
                routes.append(route)

            n_code = sum(1 for r in routes if r == "code")
            n_concept = sum(1 for r in routes if r == "concept")
            log(f"  Routes: {n_code} code, {n_concept} concept")

            # ── Step 1: Batch reasoning (all) + code (computational only) ──
            all_messages = []
            prompt_meta = []  # (idx, q, route, prompt_type)

            for j, (idx, q) in enumerate(batch_items):
                raw_q = q.get("prompt", "")
                route = routes[j]
                # Reasoning for all
                rp = PROMPT_REASON.format(raw_question=raw_q)
                all_messages.append([{"role": "user", "content": rp}])
                prompt_meta.append((idx, q, route, "reason"))
                # Code only for computational
                if route == "code":
                    cp = PROMPT_CODE.format(raw_question=raw_q)
                    all_messages.append([{"role": "user", "content": cp}])
                    prompt_meta.append((idx, q, route, "code"))

            log(f"  Sending {len(all_messages)} prompts ({n} reason + {n_code} code)...")
            try:
                batch_results = await provider_vllm.generate_with_think_and_parse_batch(
                    all_messages, max_token=8192, enable_thinking=True,
                )
            except Exception as e:
                log(f"  vLLM batch FAILED: {e}, retrying in 10s...")
                await asyncio.sleep(10)
                try:
                    batch_results = await provider_vllm.generate_with_think_and_parse_batch(
                        all_messages, max_token=8192, enable_thinking=True,
                    )
                except Exception as e2:
                    log(f"  Retry failed: {e2}")
                    batch_results = [{"think": "", "answer": f"Error: {e2}"}] * len(all_messages)

            batch_elapsed = time.time() - t0
            log(f"  vLLM done in {batch_elapsed:.0f}s")

            # ── Step 2: Parse results ──
            # Walk through batch_results paired with prompt_meta
            res_idx = 0
            for j, (idx, q) in enumerate(batch_items):
                route = routes[j]
                is_mcq = q.get("type") == "单选题"
                gt = q.get("answer", "")
                gt_key = extract_gt_key(gt)

                # Reasoning result
                rr = batch_results[res_idx] if res_idx < len(batch_results) else {}
                res_idx += 1
                r_think = rr.get("think", "")
                r_full = rr.get("answer", "")
                r_ans = extract_answer_tag(r_full, r_think)

                # Code result (if routed to code)
                c_think = ""
                c_full = ""
                code = ""
                c_ans = ""
                exec_res = {"success": False, "output": "", "error": "not routed"}

                if route == "code":
                    cr = batch_results[res_idx] if res_idx < len(batch_results) else {}
                    res_idx += 1
                    c_think = cr.get("think", "")
                    c_full = cr.get("answer", "")
                    code = extract_code_from_text(c_full) or ""
                    if code:
                        exec_res = execute_code_safely(code)
                        if exec_res["success"]:
                            c_ans = extract_code_answer(exec_res["output"])

                # Compare
                r_correct = answers_match(r_ans, gt_key) if is_mcq else None
                c_correct = answers_match(c_ans, gt_key) if (is_mcq and c_ans) else None
                consistent = answers_match(r_ans, c_ans) if (r_ans and c_ans) else False

                # Final answer
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

                final_correct = answers_match(final, gt_key) if (is_mcq and final) else None

                results_map[idx] = {
                    "_index": idx,
                    "question_id": str(idx),
                    "question_type": q.get("type", ""),
                    "question_preview": q.get("prompt", "")[:100],
                    "ground_truth": gt[:200],
                    "gt_key": gt_key,
                    "route": route,
                    "reasoning": {
                        "thinking_preview": r_think[:300],
                        "answer": r_full[:500],
                        "extracted_answer": r_ans,
                        "correct": r_correct,
                    },
                    "code": {
                        "thinking_preview": c_think[:300],
                        "extracted_code": code[:500] if code else "",
                        "exec_success": exec_res.get("success", False),
                        "exec_output": exec_res.get("output", "")[:300],
                        "exec_error": exec_res.get("error"),
                        "code_answer": c_ans,
                        "correct": c_correct,
                    },
                    "comparison": {"consistent": consistent},
                    "final": {"answer": final, "source": src, "correct": final_correct},
                }

                r_ok = "Y" if r_correct else ("?" if r_correct is None else "N")
                c_ok = "Y" if c_correct else ("?" if c_correct is None else "-")
                cons = "Y" if consistent else ("-" if route == "concept" else "N")
                exec_st = "OK" if exec_res.get("success") else ("-" if route == "concept" else "FAIL")
                f_ok = "Y" if final_correct else ("?" if final_correct is None else "N")
                log(f"  [{idx:3d}] {route:8s} R={r_ans[:12]:<12}({r_ok}) C={c_ans[:12]:<12}({c_ok}) "
                      f"cons={cons} exec={exec_st} final={f_ok}")

            save_checkpoint(results_map)
            log(f"  Checkpoint: {len(results_map)}/{len(questions)}")

    # ── Phase 3: GLM evaluation for subjective questions ──
    subj_indices = [i for i, q in enumerate(questions) if q.get("type") == "主观题"]
    if glm_available and subj_indices:
        log(f"\n{'='*60}")
        log(f"Phase 3: GLM evaluation for {len(subj_indices)} subjective questions")
        glm_msgs = []
        glm_indices = []

        for idx in subj_indices:
            r = results_map.get(idx)
            if not r:
                continue
            q = questions[idx]
            student_answer = r["reasoning"]["answer"]
            if not student_answer or student_answer.startswith("Error"):
                continue
            prompt = PROMPT_SUBJECTIVE_EVAL.format(
                question=q.get("prompt", ""),
                reference_answer=q.get("answer", ""),
                student_answer=student_answer,
            )
            glm_msgs.append([{"role": "user", "content": prompt}])
            glm_indices.append(idx)

        if glm_msgs:
            log(f"  Sending {len(glm_msgs)} evaluations to GLM 5.1...")
            t0 = time.time()
            for start in range(0, len(glm_msgs), 8):
                chunk_msgs = glm_msgs[start:start+8]
                chunk_indices = glm_indices[start:start+8]
                try:
                    arb_batch = await provider_glm.generate_with_think_and_parse_batch(
                        chunk_msgs, max_token=2048, enable_thinking=True,
                    )
                except Exception as e:
                    log(f"  GLM batch failed: {e}")
                    arb_batch = [{}] * len(chunk_msgs)

                for j, idx in enumerate(chunk_indices):
                    ar = arb_batch[j] if j < len(arb_batch) else {}
                    a_full = ar.get("answer", "")
                    score_m = re.search(r'<score>\s*(\d+)\s*</score>', a_full)
                    score = int(score_m.group(1)) if score_m else None
                    results_map[idx]["subjective_eval"] = {
                        "score": score,
                        "evaluation": a_full[:500],
                    }
                    log(f"  [{idx}] GLM score: {score}")

                await asyncio.sleep(2)

            log(f"  GLM done in {time.time()-t0:.0f}s")

    # ── Final summary ──
    all_results = list(results_map.values())
    total = len(all_results)
    elapsed = time.time() - total_start

    mcq_results = [r for r in all_results if r.get("question_type") == "单选题"]
    subj_results = [r for r in all_results if r.get("question_type") == "主观题"]
    mcq_total = len(mcq_results)

    r_ok = sum(1 for r in mcq_results if r["reasoning"]["correct"])
    c_ok = sum(1 for r in mcq_results if r["code"]["correct"])
    c_exec = sum(1 for r in all_results if r["code"]["exec_success"])
    n_routed_code = sum(1 for r in all_results if r.get("route") == "code")
    n_routed_concept = sum(1 for r in all_results if r.get("route") == "concept")
    cons = sum(1 for r in all_results if r["comparison"]["consistent"])
    f_ok = sum(1 for r in mcq_results if r["final"]["correct"])

    log(f"\n{'='*60}")
    log(f"SUMMARY ({total} questions, {elapsed:.0f}s)")
    log(f"{'='*60}")
    log(f"  Routing: {n_routed_code} code, {n_routed_concept} concept")
    log(f"  MCQ ({mcq_total}):")
    log(f"    Reasoning correct:  {r_ok}/{mcq_total} ({100*r_ok/mcq_total:.1f}%)")
    if n_routed_code:
        log(f"    Code correct:       {c_ok}/{n_routed_code} ({100*c_ok/n_routed_code:.1f}% of code-routed)")
        log(f"    Code executed OK:   {c_exec}/{n_routed_code} ({100*c_exec/n_routed_code:.1f}%)")
    log(f"    Consistent:         {cons}/{n_routed_code}")
    log(f"    Final correct:      {f_ok}/{mcq_total} ({100*f_ok/mcq_total:.1f}%)")

    if subj_results:
        scored = [r for r in subj_results if r.get("subjective_eval", {}).get("score") is not None]
        if scored:
            avg_score = sum(r["subjective_eval"]["score"] for r in scored) / len(scored)
            log(f"  Subjective ({len(subj_results)}): avg score {avg_score:.1f}/100")

    # Per-year breakdown
    year_stats = {}
    for r in all_results:
        m = re.search(r'\[(\d{4})年', r.get("question_preview", ""))
        year = m.group(1) if m else "unknown"
        if year not in year_stats:
            year_stats[year] = {"total": 0, "correct": 0, "mcq_total": 0, "mcq_correct": 0}
        year_stats[year]["total"] += 1
        if r.get("question_type") == "单选题":
            year_stats[year]["mcq_total"] += 1
            if r["final"].get("correct"):
                year_stats[year]["mcq_correct"] += 1
                year_stats[year]["correct"] += 1

    log(f"\n  By year (MCQ accuracy):")
    for year in sorted(year_stats.keys()):
        s = year_stats[year]
        pct = 100 * s["mcq_correct"] / s["mcq_total"] if s["mcq_total"] else 0
        log(f"    {year}: {s['mcq_correct']}/{s['mcq_total']} ({pct:.0f}%) [{s['total']} total questions]")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    log(f"\nResults saved to {OUTPUT_PATH}")

    if os.path.exists(CHECKPOINT_PATH):
        os.remove(CHECKPOINT_PATH)
        log("Checkpoint cleaned up")


if __name__ == "__main__":
    asyncio.run(main())
