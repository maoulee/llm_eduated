"""Offline batch inference with vLLM LLM class — optimized for Qwen3.6.

Uses ReasoningConfig for proper thinking/answer separation.
Best practice sampling params from Qwen3 docs.

Usage:
  1. Stop API server
  2. /root/shared-nvme/llm_edu/.venv/bin/python run_offline_batch.py
"""

import json
import os
import re
import sys
import time
import traceback
from contextlib import redirect_stdout
from io import StringIO
from typing import Any, Dict, Optional

sys.stdout.reconfigure(line_buffering=True)

DST = "docs/batch_offline_results.json"
PROGRESS = "docs/batch_offline_progress.log"
DATA_PATH = os.environ.get("SEED_QUESTIONS_FILE", "/home/dev/full_question.json")
MODEL_PATH = "/root/shared-nvme/llm_edu/models/Qwen3.6-27B-AWQ-INT4"


def log(msg: str):
    print(msg, flush=True)
    with open(PROGRESS, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


# ── Prompts ──

PROMPT_ROUTE = """请判断以下题目是否需要编写代码（数值计算、公式推导、进制转换等）才能准确回答。
只回答 code 或 concept，不要解释。

{question}"""

PROMPT_REASON = """请解答以下考研408真题，给出详细推理过程和最终答案。

{raw_question}

要求：
- 给出详细的推理和分析过程
- 将最终答案放在 \\boxed{{}} 中
- 选择题：答案是选项字母，如 \\boxed{{A}}
- 数值题：答案是具体数值，如 \\boxed{{350}}
- 如果是综合题/主观题，分小题给出答案"""

PROMPT_CODE = """请为以下题目编写Python代码来独立计算答案。这是真题，不要质疑题目。

{raw_question}

代码规范：
- 完整可执行的Python代码，从第一列开始写（无前导缩进）
- 中间步骤用 print() 逐行输出
- 最后一行 print 最终答案：
  - 选择题：print选项字母，如 print("A")
  - 数值题：print数值，如 print(350)
- 只用Python内置函数和标准库
- 禁用 input()、open()

请只输出代码：
```python
# 你的代码
```"""


# ── Utility Functions ──

def extract_answer(text: str) -> str:
    """Extract answer from \\boxed{} or <answer> tags."""
    m = re.search(r'\\boxed\{([^}]+)\}', text)
    if m:
        return m.group(1).strip()
    m = re.search(r'<answer>\s*(.*?)\s*</answer>', text, re.DOTALL)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return text.strip()[:100]


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
    options = {}
    for m in re.finditer(r'([A-D])[.．、)\s]+(.+?)(?=\s*[A-D][.．、)\s]+|$)', prompt, re.DOTALL):
        letter = m.group(1)
        text = m.group(2).strip()
        text = re.sub(r'\s*\\n\s*', ' ', text).strip()
        if text:
            options[letter] = text
    return options


def normalize_for_matching(s: str) -> str:
    s = s.strip().upper()
    s = re.sub(r'\s+', '', s)
    s = s.rstrip('H')
    return s


def match_value_to_option(code_value: str, options: Dict[str, str]) -> Optional[str]:
    if not code_value or not options:
        return None
    cv = code_value.strip()
    if re.match(r'^[A-Da-d]$', cv):
        return cv.upper()
    cv_norm = normalize_for_matching(cv)
    for letter, text in options.items():
        if normalize_for_matching(text) == cv_norm:
            return letter
    try:
        cv_num = float(cv)
        for letter, text in options.items():
            nums = re.findall(r'[-+]?\d+(?:\.\d+)?', text)
            for n in nums:
                if float(n) == cv_num:
                    return letter
    except (ValueError, IndexError):
        pass
    for letter, text in options.items():
        opt_norm = normalize_for_matching(text)
        if len(cv_norm) >= 4 and cv_norm in opt_norm:
            return letter
        if len(opt_norm) >= 4 and opt_norm in cv_norm:
            return letter
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


def main():
    t_start = time.time()

    with open(DATA_PATH, encoding="utf-8") as f:
        questions = json.load(f)
    log(f"Loaded {len(questions)} questions")

    from vllm import LLM, SamplingParams
    from vllm.config import ReasoningConfig

    log("Initializing offline vLLM engine with ReasoningConfig...")
    llm = LLM(
        model=MODEL_PATH,
        tensor_parallel_size=1,
        gpu_memory_utilization=0.95,
        max_model_len=15000,
        max_num_batched_tokens=4096,
        trust_remote_code=True,
        kv_cache_dtype="fp8",
        enable_prefix_caching=True,
        enable_chunked_prefill=True,
        compilation_config={
            "cudagraph_capture_sizes": [1, 2, 4, 8],
            "max_cudagraph_capture_size": 8,
        },
        language_model_only=True,
        reasoning_config=ReasoningConfig(
            reasoning_start_str="<think",
            reasoning_end_str="</think",
        ),
    )
    log(f"vLLM engine initialized in {time.time()-t_start:.0f}s")

    # ── Phase 0: Route Classification (NO thinking) ──
    log(f"\n{'='*60}")
    log("Phase 0: Route Classification (no thinking)")
    log(f"{'='*60}")

    route_msgs = []
    for q in questions:
        rp = PROMPT_ROUTE.format(question=q.get("prompt", "")[:500])
        route_msgs.append([{"role": "user", "content": rp}])

    # Non-thinking mode: chat_template_kwargs disables thinking at template level
    route_sp = SamplingParams(
        temperature=0.7, top_p=0.80, top_k=20,
        presence_penalty=1.5, repetition_penalty=1.0,
        max_tokens=64,
    )

    log(f"Routing {len(route_msgs)} questions (no thinking)...")
    t0 = time.time()
    route_outputs = llm.chat(
        route_msgs, sampling_params=route_sp,
        chat_template_kwargs={"enable_thinking": False},
    )
    dt = time.time() - t0
    log(f"Routing done in {dt:.1f}s ({len(route_msgs)/dt:.1f} prompts/s)")

    routes = []
    for i, out in enumerate(route_outputs):
        text = out.outputs[0].text.strip().lower()
        if "concept" in text:
            routes.append("concept")
        elif "code" in text:
            routes.append("code")
        else:
            routes.append("code")
        if i < 5 or i % 50 == 0:
            log(f"  [{i}] route={routes[-1]} raw={text[:30]}")

    n_code = sum(1 for r in routes if r == "code")
    n_concept = sum(1 for r in routes if r == "concept")
    log(f"Routes: {n_code} code, {n_concept} concept")

    # ── Phase 1: Reasoning (all questions, thinking mode) ──
    log(f"\n{'='*60}")
    log("Phase 1: Reasoning (all questions, thinking)")
    log(f"{'='*60}")

    # Thinking mode best practice: temp=1.0, top_p=0.95, top_k=20
    reason_sp = SamplingParams(
        temperature=1.0, top_p=0.95, top_k=20,
        presence_penalty=0.0, repetition_penalty=1.0,
        max_tokens=8192,
    )

    reason_msgs = []
    for q in questions:
        rp = PROMPT_REASON.format(raw_question=q.get("prompt", ""))
        reason_msgs.append([{"role": "user", "content": rp}])

    log(f"Reasoning {len(reason_msgs)} questions...")
    t0 = time.time()
    reason_outputs = llm.chat(
        reason_msgs, sampling_params=reason_sp,
        chat_template_kwargs={"enable_thinking": True},
    )
    dt = time.time() - t0
    total_r_toks = sum(len(o.outputs[0].token_ids) for o in reason_outputs)
    log(f"Reasoning done in {dt:.0f}s ({total_r_toks/dt:.0f} tok/s)")

    # ── Phase 2: Code Generation (code-routed, thinking mode) ──
    code_indices = [i for i, r in enumerate(routes) if r == "code"]
    log(f"\n{'='*60}")
    log(f"Phase 2: Code Generation ({len(code_indices)} questions)")
    log(f"{'='*60}")

    # Code task: temperature=0.6 for precision
    code_sp = SamplingParams(
        temperature=0.6, top_p=0.95, top_k=20,
        presence_penalty=0.0, repetition_penalty=1.0,
        max_tokens=8192,
    )

    code_outputs_list = []
    if code_indices:
        code_msgs = []
        for idx in code_indices:
            q = questions[idx]
            cp = PROMPT_CODE.format(raw_question=q.get("prompt", ""))
            code_msgs.append([{"role": "user", "content": cp}])

        log(f"Generating code for {len(code_msgs)} questions...")
        t0 = time.time()
        try:
            code_outputs_list = llm.chat(
                code_msgs, sampling_params=code_sp,
                chat_template_kwargs={"enable_thinking": True},
            )
            dt = time.time() - t0
            total_c_toks = sum(len(o.outputs[0].token_ids) for o in code_outputs_list)
            log(f"Code generation done in {dt:.0f}s ({total_c_toks/dt:.0f} tok/s)")
        except Exception as e:
            log(f"Code generation FAILED: {e}")
            code_outputs_list = []

    # ── Phase 3: Process Results ──
    log(f"\n{'='*60}")
    log("Phase 3: Processing Results")
    log(f"{'='*60}")

    results = []
    code_output_map = {idx: code_outputs_list[j] for j, idx in enumerate(code_indices)}

    for i, q in enumerate(questions):
        prompt = q.get("prompt", "")
        answer = q.get("answer", "")
        gt_key = extract_gt_key(answer)

        qm = re.search(r'(单选题|多选题|判断题|主观题|综合题|填空题)', prompt)
        qtype = qm.group(1) if qm else "未知"
        route = routes[i]
        is_mcq = qtype == "单选题"

        # Reasoning - with ReasoningConfig, output.text is clean answer (no thinking)
        r_content = reason_outputs[i].outputs[0].text.strip()
        # If ReasoningConfig didn't strip thinking, do it manually
        think_m = re.match(r'<think[^>]*>(.*?)</think[^>]*>(.*)', r_content, re.DOTALL)
        if think_m:
            r_thinking = think_m.group(1).strip()
            r_content = think_m.group(2).strip()
        else:
            r_thinking = ""

        r_answer = extract_answer(r_content)
        r_correct = answers_match(r_answer, gt_key) if (is_mcq and r_answer) else None

        result = {
            "_index": i,
            "question_type": qtype,
            "question_preview": prompt[:200],
            "route": route,
            "gt_key": gt_key,
            "reasoning": {
                "thinking_preview": r_thinking[:500],
                "answer": r_content[:1000],
                "extracted_answer": r_answer,
                "correct": r_correct,
            },
            "code": {
                "extracted_code": "",
                "exec_success": False,
                "exec_output": "",
                "exec_error": None,
                "code_answer": "",
                "correct": None,
            },
            "comparison": {"consistent": False},
            "final": {"answer": "", "source": "", "correct": None},
        }

        # Code channel
        if i in code_output_map:
            c_text = code_output_map[i].outputs[0].text.strip()
            think_m_c = re.match(r'<think[^>]*>(.*?)</think[^>]*>(.*)', c_text, re.DOTALL)
            if think_m_c:
                c_content = think_m_c.group(2).strip()
            else:
                c_content = c_text

            code = extract_code_from_text(c_content) or ""
            if code:
                eres = execute_code(code)
                c_ans_raw = extract_code_answer(eres["output"]) if eres["success"] else ""

                if is_mcq and c_ans_raw:
                    options = parse_options(prompt)
                    matched = match_value_to_option(c_ans_raw, options)
                    c_ans = matched or c_ans_raw
                else:
                    c_ans = c_ans_raw
                    matched = None

                result["code"] = {
                    "extracted_code": code[:1000],
                    "exec_success": eres["success"],
                    "exec_output": eres.get("output", "")[:500],
                    "exec_error": eres.get("error"),
                    "code_answer": c_ans,
                    "raw_code_answer": c_ans_raw,
                    "matched_option": matched or "",
                    "correct": answers_match(c_ans, gt_key) if (is_mcq and c_ans) else None,
                }
            else:
                result["code"]["exec_error"] = "no code extracted"

        # Comparison and final
        r_ans = r_answer
        c_ans = result["code"].get("code_answer", "")
        consistent = answers_match(r_ans, c_ans) if (r_ans and c_ans) else False
        result["comparison"]["consistent"] = consistent

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
        result["final"] = {"answer": final, "source": src,
                          "correct": answers_match(final, gt_key) if (is_mcq and final) else None}

        results.append(result)

    # ── Summary ──
    mcq = [r for r in results if r.get("question_type") == "单选题"]
    n_code_total = sum(1 for r in results if r.get("route") == "code")

    r_ok = sum(1 for r in mcq if r["reasoning"]["correct"])
    c_ok = sum(1 for r in mcq if r["code"].get("correct"))
    c_exec = sum(1 for r in results if r["code"]["exec_success"])
    cons = sum(1 for r in results if r["comparison"]["consistent"])
    f_ok = sum(1 for r in mcq if r["final"]["correct"])

    log(f"\n{'='*60}")
    log(f"OFFLINE BATCH SUMMARY ({len(results)} questions)")
    log(f"{'='*60}")
    log(f"  Total wall time: {time.time()-t_start:.0f}s")
    log(f"  MCQ ({len(mcq)}):")
    log(f"    Reasoning correct:  {r_ok}/{len(mcq)} ({100*r_ok/len(mcq):.1f}%)")
    log(f"    Code correct:       {c_ok}/{n_code_total} ({100*c_ok/max(n_code_total,1):.1f}%)")
    log(f"    Code executed OK:   {c_exec}/{n_code_total} ({100*c_exec/max(n_code_total,1):.1f}%)")
    log(f"    Consistent:         {cons}/{n_code_total}")
    log(f"    Final correct:      {f_ok}/{len(mcq)} ({100*f_ok/len(mcq):.1f}%)")

    code_rescue = sum(1 for r in mcq if not r["reasoning"]["correct"] and r["final"]["correct"])
    code_hurt = sum(1 for r in mcq if r["reasoning"]["correct"] and not r["final"]["correct"])
    log(f"    Code rescued: {code_rescue}, hurt: {code_hurt}")

    log(f"\n  Code-wrong MCQs:")
    for r in mcq:
        if r.get("route") != "code" or r["code"].get("correct") != False:
            continue
        idx = r["_index"]
        gt = r["gt_key"]
        raw = r["code"].get("raw_code_answer", r["code"].get("code_answer", ""))
        matched = r["code"].get("matched_option", "")
        log(f"    [{idx}] gt={gt} raw={raw[:30]} matched={matched}")

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
    log(f"Total wall time: {time.time()-t_start:.0f}s")


if __name__ == "__main__":
    main()
