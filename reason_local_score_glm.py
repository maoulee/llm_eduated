"""Re-reason subjective questions via local vLLM + score via GLM 5.1.

Phase 1: Local Qwen3.6 re-reasons all 31 questions (fast, ~5 min)
Phase 2: GLM 5.1 scores full answers (thinking OFF, ~5 min)
"""
import asyncio
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(line_buffering=True)

from openai import AsyncOpenAI
from dotenv import load_dotenv
load_dotenv()
from config import get_provider_config
from llm_providers_new import get_llm_provider

DATA_PATH = os.environ.get("SEED_QUESTIONS_FILE", "/home/dev/full_question.json")
RESULTS_PATH = "docs/batch_200_results_v2.json"
DST = "docs/subjective_reason_score.json"

LOCAL_URL = "http://localhost:8000/v1"
LOCAL_MODEL = "qwen3.6"

REASON_PROMPT = """请解答以下考研408真题（主观题/综合题），给出完整的解答过程。

{question}

要求：
- 按小题逐一给出详细解答
- 写出计算过程和推导步骤
- 给出每小题的最终答案
- 将所有小题的最终答案汇总放在最后一行，格式：\\boxed{{小题1答案; 小题2答案; ...}}"""

SCORE_PROMPT = """你是考研408阅卷专家。请评分以下主观题作答。

## 题目
{question}

## 参考答案
{reference}

## 考生作答
{answer}

请自由评价该考生的作答质量。按小题逐一分析得分点覆盖情况，最后给出总分。
不需要严格XML格式，自由书写即可。最后单独一行用以下格式给出总分：

<score>得分/满分</score>"""


async def reason_batch(client, questions_data, subjective_indices):
    """Re-reason all questions via local vLLM with thinking ON."""
    sem = asyncio.Semaphore(8)
    results = {}

    async def reason_one(idx):
        async with sem:
            q = questions_data[idx]
            prompt = REASON_PROMPT.format(question=q.get("prompt", ""))
            t0 = time.time()
            try:
                resp = await client.chat.completions.create(
                    model=LOCAL_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=1.0, top_p=0.95,
                    max_tokens=8192,
                    extra_body={"chat_template_kwargs": {"enable_thinking": True}},
                )
                dt = time.time() - t0
                choice = resp.choices[0]
                msg = choice.message

                # Parse thinking vs answer
                content = msg.content or ""
                thinking = ""
                answer = content
                m = re.match(r'<think[^>]*>(.*?)</think[^>]*>(.*)', content, re.DOTALL)
                if m:
                    thinking = m.group(1)
                    answer = m.group(2).strip()

                print(f"  [{idx}] {len(answer)}字 ({dt:.0f}s) {answer[:60]}...")
                results[idx] = {"think": thinking, "answer": answer, "time": dt}
            except Exception as e:
                dt = time.time() - t0
                print(f"  [{idx}] FAILED ({dt:.0f}s): {e}")
                results[idx] = {"think": "", "answer": "", "time": dt, "error": str(e)}

    tasks = [reason_one(idx) for idx in subjective_indices]
    await asyncio.gather(*tasks)
    return results


async def score_batch(provider, questions_data, reason_results, subjective_indices):
    """Score all answers via GLM 5.1 with thinking OFF."""
    sem = asyncio.Semaphore(4)
    results = {}

    async def score_one(idx):
        async with sem:
            rr = reason_results[idx]
            if rr.get("error") or not rr["answer"]:
                print(f"  [{idx}] SKIPPED (no answer)")
                results[idx] = {"scoring": "", "time": 0}
                return

            q = questions_data[idx]
            msg = SCORE_PROMPT.format(
                question=q.get("prompt", "")[:3000],
                reference=q.get("answer", "")[:3000],
                answer=rr["answer"][:6000],
            )

            t0 = time.time()
            try:
                res = await provider.generate_with_think_and_parse_batch(
                    [[{"role": "user", "content": msg}]],
                    enable_thinking=False,
                    max_token=4096,
                )
                dt = time.time() - t0
                scoring = res[0].get("answer", "") if res else ""
                got, mx = parse_score(scoring)
                tag = f"{got}/{mx}" if got is not None else "?/?"
                print(f"  [{idx}] {tag} ({dt:.0f}s)")
                results[idx] = {"scoring": scoring, "time": dt}
            except Exception as e:
                dt = time.time() - t0
                print(f"  [{idx}] FAILED ({dt:.0f}s): {e}")
                results[idx] = {"scoring": "", "time": dt, "error": str(e)}

    tasks = [score_one(idx) for idx in subjective_indices]
    await asyncio.gather(*tasks)
    return results


def parse_score(text):
    m = re.search(r'<score>\s*([\d.]+)\s*/\s*(\d+)\s*</score>', text)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


async def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        questions = json.load(f)
    with open(RESULTS_PATH, encoding="utf-8") as f:
        results = json.load(f)

    subjective = [r for r in results if r.get("question_type") == "主观题"]
    indices = [r["_index"] for r in subjective]
    print(f"Subjective questions: {len(subjective)}")

    # Phase 1: Local vLLM reasoning
    print(f"\n{'='*60}")
    print("Phase 1: Local vLLM reasoning (thinking ON, concurrency=8)")
    print(f"{'='*60}")

    client = AsyncOpenAI(base_url=LOCAL_URL, api_key="EMPTY")
    t0 = time.time()
    reason_results = await reason_batch(client, questions, indices)
    dt = time.time() - t0
    ok = sum(1 for r in reason_results.values() if not r.get("error"))
    print(f"\nDone: {ok}/{len(indices)} in {dt:.0f}s\n")

    # Phase 2: GLM scoring
    print(f"{'='*60}")
    print("Phase 2: GLM 5.1 scoring (thinking OFF, concurrency=4)")
    print(f"{'='*60}")

    glm_config = get_provider_config("glm5.1")
    provider = get_llm_provider(glm_config)
    t0 = time.time()
    score_results = await score_batch(provider, questions, reason_results, indices)
    dt = time.time() - t0
    print(f"\nDone in {dt:.0f}s\n")

    # Combine
    output = []
    total_got, total_max, scored_count = 0, 0, 0

    for idx in indices:
        rr = reason_results[idx]
        sr = score_results[idx]
        got, mx = parse_score(sr.get("scoring", ""))

        entry = {
            "_index": idx,
            "question_preview": questions[idx].get("prompt", "")[:100],
            "model_answer": rr["answer"],
            "model_answer_len": len(rr["answer"]),
            "reference_answer": questions[idx].get("answer", ""),
            "scoring_text": sr.get("scoring", ""),
            "score_got": got,
            "score_max": mx,
            "reason_time": rr["time"],
            "score_time": sr.get("time", 0),
        }
        if got is not None and mx is not None:
            total_got += got
            total_max += mx
            scored_count += 1
        output.append(entry)

    with open(DST, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"{'='*60}")
    print(f"SUMMARY ({scored_count}/{len(indices)} scored)")
    print(f"{'='*60}")
    if total_max > 0:
        print(f"Total: {total_got}/{total_max} = {100*total_got/total_max:.1f}%\n")

    tiers = {"excellent": [], "good": [], "partial": [], "poor": [], "zero": [], "unknown": []}
    for e in output:
        g, m = e["score_got"], e["score_max"]
        if g is None or m is None:
            tiers["unknown"].append(e)
        else:
            p = g / m if m > 0 else 0
            if p >= 0.8: tiers["excellent"].append(e)
            elif p >= 0.6: tiers["good"].append(e)
            elif p >= 0.4: tiers["partial"].append(e)
            elif p > 0: tiers["poor"].append(e)
            else: tiers["zero"].append(e)

    for tier, label in [("excellent",">=80%"),("good","60-80%"),("partial","40-60%"),
                        ("poor","<40%"),("zero","0%"),("unknown","?")]:
        if not tiers[tier]:
            continue
        print(f"{label} ({len(tiers[tier])}题):")
        for e in tiers[tier]:
            g, m = e["score_got"], e["score_max"]
            if g is not None:
                print(f"  [{e['_index']}] {g}/{m} ({100*g/m:.0f}%) ans={e['model_answer_len']}字")
            else:
                print(f"  [{e['_index']}] ?/? ans={e['model_answer_len']}字")

    print(f"\nSaved to {DST}")


if __name__ == "__main__":
    asyncio.run(main())
