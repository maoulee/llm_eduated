"""Extract knowledge from selected subjective questions for injection experiment.

Targets: [51] 0%, [38] 46%, [50] 70%, [154] 100%
Focus: reasoning patterns + deep knowledge points, not verbose prompts.
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
DST = "docs/subjective_sample_extractions.json"

SELECTED = [51, 38, 50, 154]


async def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    config = get_provider_config("glm5.1")
    provider = get_llm_provider(config)
    pipeline = ExtractionPipeline(
        provider,
        max_tokens=4096,
        enable_thinking=False,
        review_mode="fast",
    )
    print("GLM 5.1 ready (thinking OFF, review=fast)\n")

    extractions = []
    for i, idx in enumerate(SELECTED):
        q = questions[idx]
        import re
        m = re.search(r'\[(\d+年考研真题第\d+题)', q.get("prompt", ""))
        q_id = m.group(1) if m else f"subjective_{idx}"

        print(f"{'='*60}")
        print(f"[{i+1}/4] Extracting [{idx}] {q_id}")
        print(f"{'='*60}")

        t0 = time.time()
        try:
            result = await pipeline.extract({
                "id": q_id,
                "type": q.get("type", "主观题"),
                "prompt": q.get("prompt", ""),
                "answer": q.get("answer", ""),
            })
            dt = time.time() - t0
            result["_index"] = idx

            if "error" in result:
                print(f"  ERROR ({dt:.1f}s): {result['error']}")
            else:
                review = result.get("review", {})
                readiness = review.get("readiness", {})
                ku = result.get("knowledge_units", {})
                rp = result.get("reasoning_pattern", {})
                n_units = len(ku.get("knowledge_units", []))
                n_mechs = len(ku.get("mechanisms", []))
                steps = rp.get("steps", [])
                print(f"  OK ({dt:.1f}s) units={n_units} mechs={n_mechs} steps={len(steps)}")

            extractions.append(result)

        except Exception as e:
            dt = time.time() - t0
            print(f"  EXCEPTION ({dt:.1f}s): {e}")
            import traceback
            traceback.print_exc()
            extractions.append({"question_id": q_id, "_index": idx, "error": str(e)})

    with open(DST, "w", encoding="utf-8") as f:
        json.dump(extractions, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to {DST}")


if __name__ == "__main__":
    asyncio.run(main())
