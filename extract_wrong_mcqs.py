"""Extract knowledge from wrong MCQs for knowledge injection testing.

Uses GLM 5.1 for all extraction passes (thinking OFF) + review.
The extractions will feed into the generation pipeline to produce
simulated questions targeting the same knowledge gaps.
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
from core_new.extraction_pipeline import ExtractionPipeline

DATA_PATH = os.environ.get("SEED_QUESTIONS_FILE", "/home/dev/full_question.json")
RESULTS_PATH = "docs/batch_200_results_v2.json"
DST = "docs/wrong_mcq_extractions.json"


async def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        questions = json.load(f)
    with open(RESULTS_PATH, encoding="utf-8") as f:
        results = json.load(f)

    # Find wrong MCQs
    wrong_mcqs = [
        r for r in results
        if r.get("question_type") == "单选题"
        and not r.get("final", {}).get("correct", False)
    ]
    print(f"Found {len(wrong_mcqs)} wrong MCQs to extract")

    # Build question dicts for extraction
    extract_questions = []
    for r in wrong_mcqs:
        idx = r["_index"]
        q = questions[idx]
        # Extract year + number from preview for ID
        import re
        m = re.search(r'\[(\d+年考研真题第\d+题)', r.get("question_preview", ""))
        q_id = m.group(1) if m else f"wrong_{idx}"

        extract_questions.append({
            "id": q_id,
            "type": q.get("type", "单选题"),
            "prompt": q.get("prompt", ""),
            "answer": q.get("answer", ""),
            "_index": idx,
            "_wrong_answer": r.get("final", {}).get("answer", ""),
        })

    for eq in extract_questions:
        print(f"  [{eq['_index']}] {eq['id']}: got={eq['_wrong_answer']}")

    # Initialize GLM 5.1 for extraction (thinking OFF)
    config = get_provider_config("glm5.1")
    provider = get_llm_provider(config)
    pipeline = ExtractionPipeline(
        provider,
        max_tokens=4096,
        enable_thinking=False,
        review_mode="fast",
    )
    print("GLM 5.1 extraction pipeline ready (thinking OFF, review=fast)\n")

    # Extract with concurrency=2
    extractions = []
    for i, eq in enumerate(extract_questions):
        q_id = eq["id"]
        idx = eq["_index"]
        print(f"{'='*60}")
        print(f"Extracting {i+1}/{len(extract_questions)}: [{idx}] {q_id}")
        print(f"{'='*60}")

        t0 = time.time()
        try:
            result = await pipeline.extract(eq)
            dt = time.time() - t0

            result["_index"] = idx
            result["_wrong_answer"] = eq["_wrong_answer"]
            extractions.append(result)

            # Quick status
            has_error = "error" in result
            if has_error:
                print(f"  ERROR ({dt:.1f}s): {result['error']}")
            else:
                review = result.get("review", {})
                readiness = review.get("readiness", {})
                status = readiness.get("status", "?")
                print(f"  OK ({dt:.1f}s) readiness={status}")

        except Exception as e:
            dt = time.time() - t0
            print(f"  EXCEPTION ({dt:.1f}s): {e}")
            import traceback
            traceback.print_exc()
            extractions.append({
                "question_id": q_id,
                "_index": idx,
                "_wrong_answer": eq["_wrong_answer"],
                "error": str(e),
            })

    # Save
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(extractions, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\n{'='*60}")
    print("EXTRACTION SUMMARY")
    print(f"{'='*60}")
    ok = sum(1 for e in extractions if "error" not in e)
    err = sum(1 for e in extractions if "error" in e)
    print(f"  Success: {ok}, Failed: {err}")

    for e in extractions:
        qid = e.get("question_id", "?")
        idx = e.get("_index", "?")
        if "error" in e:
            print(f"  [{idx}] {qid}: FAILED - {e['error'][:80]}")
        else:
            review = e.get("review", {})
            readiness = review.get("readiness", {})
            status = readiness.get("status", "?")
            ku = e.get("knowledge_units", {})
            n_units = len(ku.get("knowledge_units", []))
            n_mechs = len(ku.get("mechanisms", []))
            print(f"  [{idx}] {qid}: {status} (units={n_units}, mechs={n_mechs})")

    print(f"\nSaved to {DST}")


if __name__ == "__main__":
    asyncio.run(main())
