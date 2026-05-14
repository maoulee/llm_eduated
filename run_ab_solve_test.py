"""
A/B test: solve questions with injection vs without injection.

Mode A (bare):    model sees only the raw question prompt
Mode B (inject):  model sees the raw question + extracted structured data
                  (knowledge_units, trigger_rules, reasoning_pattern)

Uses local vLLM (Qwen3.6-27B) for inference.
"""

import asyncio
import json
import os
import time
from typing import Any, Dict, List

from dotenv import load_dotenv
load_dotenv()

from config import get_provider_config
from llm_providers_new import get_llm_provider

PROMPT_BARE = """请解答以下{question_type}题目。请逐步推理，并将最终答案放在 \\boxed{{}} 中。

{stem}

{options}"""


PROMPT_INJECT = """请解答以下{question_type}题目。以下提供了该题的结构化分析数据（由专家系统提取），供你参考。

## 题目
{stem}

{options}

## 结构化分析数据（参考）

### 已知条件与目标
{structure}

### 相关知识单元
{knowledge_units}

### 触发规则
{trigger_rules}

### 推理模式
{reasoning_pattern}

请基于以上结构化分析数据，给出详细解答过程，并在最后明确写出你的答案。"""


def format_options(result: Dict[str, Any]) -> str:
    opts = result.get("question_structure", {}).get("options", {})
    if not opts:
        return ""
    lines = []
    for k in sorted(opts.keys()):
        lines.append(f"{k}. {opts[k]}")
    return "\n".join(lines)


async def solve_question(
    provider,
    question: Dict[str, Any],
    extraction: Dict[str, Any],
    mode: str,
) -> Dict[str, Any]:
    """Solve a single question in given mode (blind — no answer in prompt)."""

    q_type = question.get("type", "单选题")
    stem = question.get("prompt", "")
    answer = question.get("answer", "")
    options = format_options(extraction)

    if mode == "bare":
        prompt = PROMPT_BARE.format(
            question_type=q_type, stem=stem, options=options,
        )
    else:
        structure = json.dumps(
            extraction.get("question_structure", {}).get("structure", {}),
            ensure_ascii=False, indent=2,
        )
        ku = json.dumps(
            extraction.get("knowledge_units", {}),
            ensure_ascii=False, indent=2,
        )
        tr = json.dumps(
            extraction.get("trigger_rules", {}),
            ensure_ascii=False, indent=2,
        )
        rp = json.dumps(
            extraction.get("reasoning_pattern", {}),
            ensure_ascii=False, indent=2,
        )
        prompt = PROMPT_INJECT.format(
            question_type=q_type, stem=stem, options=options,
            structure=structure, knowledge_units=ku,
            trigger_rules=tr, reasoning_pattern=rp,
        )

    messages = [[{"role": "user", "content": prompt}]]
    results = await provider.generate_with_think_and_parse_batch(
        messages, max_token=4096, enable_thinking=True,
    )

    raw = results[0] if results else {}
    content = raw.get("answer", str(raw)) if raw else ""

    # Offline comparison: extract model's answer from \boxed{} first, then fallback
    import re
    model_answer = ""
    boxed = re.search(r'\\boxed\{([^}]+)\}', content)
    if boxed:
        model_answer = boxed.group(1).strip().upper()
    if not model_answer:
        for pat in [r'[最终答案|答案|answer][：:]\s*([A-D])\b', r'\b([A-D])\b']:
            m = re.search(pat, content, re.IGNORECASE)
            if m:
                model_answer = m.group(1).upper()
                break
    ground_truth = str(answer).strip().upper()
    correct = model_answer == ground_truth if model_answer else None

    return {
        "mode": mode,
        "question_id": question.get("id", "?"),
        "model_answer": model_answer,
        "ground_truth": ground_truth,
        "correct": correct,
        "response": content,
        "thinking": raw.get("think", "")[:500] if raw else "",
    }


async def main():
    # Load questions
    from run_extraction_sample import QUESTIONS

    # Load extraction results (deep v4)
    extraction_path = os.path.join(os.path.dirname(__file__), "docs", "extraction_deep_v4.json")
    with open(extraction_path, encoding="utf-8") as f:
        extractions = json.load(f)

    # Build lookup: question_id -> extraction result
    ext_map = {r.get("question_id"): r for r in extractions if "error" not in r}

    # Init local vLLM provider
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

        for mode in ("bare", "inject"):
            print(f"  Running {mode}...", end=" ", flush=True)
            start = time.time()
            result = await solve_question(provider, q, ext, mode)
            elapsed = time.time() - start
            result["elapsed"] = elapsed
            all_results.append(result)
            resp_preview = result.get("response", "")[:100].replace("\n", " ")
            print(f"{elapsed:.1f}s → {resp_preview}...")

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"Total: {len(all_results)} results in {total_elapsed:.1f}s")

    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "docs", "ab_solve_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
