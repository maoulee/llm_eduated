"""Score subjective question answers using GLM 5.1.

Compares model answers against ground truth, scores each sub-question,
and produces a detailed score report.
"""
import asyncio
import json
import os
import sys
import time

sys.stdout.reconfigure(line_buffering=True)

from dotenv import load_dotenv
load_dotenv()
from config import get_provider_config
from llm_providers_new import get_llm_provider

DATA_PATH = os.environ.get("SEED_QUESTIONS_FILE", "/home/dev/full_question.json")
RESULTS_PATH = "docs/batch_200_results_v2.json"
DST = "docs/subjective_scores.json"

SCORING_PROMPT = """你是一位考研408阅卷专家。请评分以下主观题的模型回答。

## 题目
{question}

## 参考答案
{reference_answer}

## 模型回答
{model_answer}

## 评分要求
1. 将参考答案按小题拆分，每个小题独立评分
2. 对每个小题：
   - 列出参考答案的关键得分点
   - 判断模型回答是否覆盖每个得分点（覆盖/部分覆盖/未覆盖）
   - 给出该小题的得分（0-满分）
3. 最后给出总分

请按以下格式输出：
<scoring>
<sub_questions>
<sub id="1">
<ref_points>得分点列表</ref_points>
<model_coverage>模型覆盖情况</model_coverage>
<score>X/Y</score>
</sub>
...
</sub_questions>
<total_score>X/Y</total_score>
<brief>一句话评价模型回答质量</brief>
</scoring>"""


async def score_one(provider, messages, idx, sem):
    async with sem:
        t0 = time.time()
        results = await provider.generate_with_think_and_parse_batch(
            [messages], enable_thinking=True, max_token=4096,
        )
        dt = time.time() - t0
        answer = results[0].get("answer", "") if results else ""
        return {"idx": idx, "answer": answer, "time": dt}


async def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        questions = json.load(f)
    with open(RESULTS_PATH, encoding="utf-8") as f:
        results = json.load(f)

    subjective = [r for r in results if r.get("question_type") == "主观题"]
    print(f"Scoring {len(subjective)} subjective questions")

    config = get_provider_config("glm5.1")
    provider = get_llm_provider(config)
    print("GLM 5.1 ready")

    sem = asyncio.Semaphore(4)
    tasks = []

    for r in subjective:
        idx = r["_index"]
        q = questions[idx]
        prompt = q.get("prompt", "")
        gt_answer = q.get("answer", "")
        model_answer = r.get("final", {}).get("answer", "")
        if not model_answer:
            model_answer = r.get("reasoning", {}).get("answer", "")

        scoring_msg = SCORING_PROMPT.format(
            question=prompt[:2000],
            reference_answer=gt_answer[:2000],
            model_answer=model_answer[:2000],
        )
        messages = [{"role": "user", "content": scoring_msg}]
        tasks.append(score_one(provider, messages, idx, sem))

    print(f"Scoring {len(tasks)} questions (concurrency=4)...")
    t0 = time.time()
    score_results = await asyncio.gather(*tasks)
    total_dt = time.time() - t0
    print(f"Done in {total_dt:.0f}s")

    scored = []
    for sr, r in zip(score_results, subjective):
        idx = sr["idx"]
        answer = sr["answer"]
        # Parse score from XML
        import re
        total_m = re.search(r'<total_score>(.*?)</total_score>', answer)
        brief_m = re.search(r'<brief>(.*?)</brief>', answer)

        total_score = total_m.group(1) if total_m else "?/?"
        brief = brief_m.group(1) if brief_m else answer[:100]

        scored.append({
            "_index": idx,
            "question_preview": r.get("question_preview", "")[:100],
            "gt_answer": questions[idx].get("answer", "")[:200],
            "model_answer": r.get("final", {}).get("answer", "")[:200],
            "score_detail": total_score,
            "brief": brief,
            "full_scoring": answer,
            "time": sr["time"],
        })

        print(f"  [{idx}] {total_score} | {brief[:80]}")

    # Save
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(scored, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\n{'='*60}")
    print("SUBJECTIVE SCORING SUMMARY")
    print(f"{'='*60}")
    for s in scored:
        print(f"  [{s['_index']}] {s['score_detail']} | {s['brief'][:60]}")
    print(f"\nSaved to {DST}")


if __name__ == "__main__":
    asyncio.run(main())
