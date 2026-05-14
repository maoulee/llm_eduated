"""Re-reason subjective questions (no code path) + score with full answer.

Pipeline:
  1. GLM 5.1 re-solves 31 subjective questions with thinking ON
  2. Stores full answer (no truncation)
  3. GLM 5.1 scores each answer with free-form output, score tagged only at end
"""
import asyncio
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(line_buffering=True)

from dotenv import load_dotenv
load_dotenv()
from config import get_provider_config
from llm_providers_new import get_llm_provider

DATA_PATH = os.environ.get("SEED_QUESTIONS_FILE", "/home/dev/full_question.json")
RESULTS_PATH = "docs/batch_200_results_v2.json"
DST = "docs/subjective_reason_score.json"

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


async def reason_one(provider, question, idx, sem):
    """Re-reason a single subjective question."""
    async with sem:
        prompt = question.get("prompt", "")
        msg = REASON_PROMPT.format(question=prompt)

        t0 = time.time()
        results = await provider.generate_with_think_and_parse_batch(
            [[{"role": "user", "content": msg}]],
            enable_thinking=True,
            max_token=8192,
        )
        dt = time.time() - t0

        think = results[0].get("think", "") if results else ""
        answer = results[0].get("answer", "") if results else ""
        return {"idx": idx, "think": think, "answer": answer, "time": dt}


async def score_one(provider, question, reference, model_answer, idx, sem):
    """Score a single subjective question answer."""
    async with sem:
        msg = SCORE_PROMPT.format(
            question=question[:3000],
            reference=reference[:3000],
            answer=model_answer[:6000],
        )

        t0 = time.time()
        results = await provider.generate_with_think_and_parse_batch(
            [[{"role": "user", "content": msg}]],
            enable_thinking=False,
            max_token=4096,
        )
        dt = time.time() - t0
        answer = results[0].get("answer", "") if results else ""
        return {"idx": idx, "scoring": answer, "time": dt}


def parse_score(text):
    """Extract score from <score>X/Y</score> or \\boxed{X/Y}."""
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
    print(f"Subjective questions: {len(subjective)}")

    config = get_provider_config("glm5.1")
    provider = get_llm_provider(config)
    print("GLM 5.1 ready\n")

    # ── Phase 1: Re-reason all subjective questions ──
    print(f"{'='*60}")
    print("Phase 1: Re-reasoning (no code, thinking ON)")
    print(f"{'='*60}")

    sem = asyncio.Semaphore(4)
    reason_results = []
    for i, r in enumerate(subjective):
        idx = r["_index"]
        q = questions[idx]
        print(f"  Reasoning [{i+1}/{len(subjective)}] [{idx}]...", end="", flush=True)
        t0 = time.time()
        try:
            rr = await reason_one(provider, q, idx, sem)
            print(f" {len(rr['answer'])}字 ({rr['time']:.0f}s)")
            reason_results.append(rr)
        except Exception as e:
            print(f" FAILED: {e}")
            reason_results.append({"idx": idx, "think": "", "answer": "", "time": 0, "error": str(e)})

    total_dt = time.time() - t0
    print(f"\nRe-reasoning done: {len([r for r in reason_results if not r.get('error')])}/{len(reason_results)} OK\n")

    # Build lookup
    reason_by_idx = {rr["idx"]: rr for rr in reason_results}

    # ── Phase 2: Score with full answers ──
    print(f"{'='*60}")
    print("Phase 2: Scoring (full answer, free-form)")
    print(f"{'='*60}")

    sem = asyncio.Semaphore(4)
    score_results = []
    for i, rr in enumerate(reason_results):
        idx = rr["idx"]
        if rr.get("error") or not rr["answer"]:
            print(f"  Scoring [{i+1}/{len(reason_results)}] [{idx}] SKIPPED (no answer)")
            score_results.append({"idx": idx, "scoring": "", "time": 0})
            continue
        q = questions[idx]
        gt = q.get("answer", "")
        model_ans = rr["answer"]
        print(f"  Scoring [{i+1}/{len(reason_results)}] [{idx}]...", end="", flush=True)
        t0 = time.time()
        try:
            sr = await score_one(provider, q.get("prompt", ""), gt, model_ans, idx, sem)
            got, mx = parse_score(sr["scoring"])
            tag = f"{got}/{mx}" if got is not None else "?/?"
            print(f" {tag} ({sr['time']:.0f}s)")
            score_results.append(sr)
        except Exception as e:
            print(f" FAILED: {e}")
            score_results.append({"idx": idx, "scoring": "", "time": 0, "error": str(e)})
    print(f"\nScoring done\n")

    # ── Combine results ──
    output = []
    total_got = 0
    total_max = 0
    scored_count = 0

    for sr in score_results:
        idx = sr["idx"]
        rr = reason_by_idx[idx]
        q = questions[idx]
        gt = q.get("answer", "")
        model_ans = rr["answer"]
        scoring_text = sr["scoring"]

        got, mx = parse_score(scoring_text)
        entry = {
            "_index": idx,
            "question_preview": q.get("prompt", "")[:100],
            "model_answer": model_ans,
            "model_answer_len": len(model_ans),
            "reference_answer": gt,
            "scoring_text": scoring_text,
            "score_got": got,
            "score_max": mx,
            "reason_time": rr["time"],
            "score_time": sr["time"],
        }

        if got is not None and mx is not None:
            total_got += got
            total_max += mx
            scored_count += 1
            pct = 100 * got / mx if mx > 0 else 0
            print(f"  [{idx}] {got}/{mx} ({pct:.0f}%) | ans={len(model_ans)}字 | {scoring_text[:60]}...")
        else:
            print(f"  [{idx}] ?/? | ans={len(model_ans)}字 | score parse failed")

        output.append(entry)

    # Save
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY ({scored_count}/{len(subjective)} scored)")
    print(f"{'='*60}")
    if total_max > 0:
        print(f"Total: {total_got}/{total_max} = {100*total_got/total_max:.1f}%")

    # By score tier
    tiers = {"excellent": [], "good": [], "partial": [], "poor": [], "zero": [], "unknown": []}
    for e in output:
        got, mx = e["score_got"], e["score_max"]
        if got is None or mx is None:
            tiers["unknown"].append(e)
        else:
            pct = got / mx if mx > 0 else 0
            if pct >= 0.8:
                tiers["excellent"].append(e)
            elif pct >= 0.6:
                tiers["good"].append(e)
            elif pct >= 0.4:
                tiers["partial"].append(e)
            elif pct > 0:
                tiers["poor"].append(e)
            else:
                tiers["zero"].append(e)

    for tier, label in [("excellent", ">=80%"), ("good", "60-80%"), ("partial", "40-60%"),
                        ("poor", "<40%"), ("zero", "0%"), ("unknown", "?")]:
        if not tiers[tier]:
            continue
        print(f"\n{label} ({len(tiers[tier])}题):")
        for e in tiers[tier]:
            g, m = e["score_got"], e["score_max"]
            if g is not None:
                print(f"  [{e['_index']}] {g}/{m} ({100*g/m:.0f}%) ans={e['model_answer_len']}字")
            else:
                print(f"  [{e['_index']}] ?/? ans={e['model_answer_len']}字")

    print(f"\nSaved to {DST}")


if __name__ == "__main__":
    asyncio.run(main())
