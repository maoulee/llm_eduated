"""Batch extraction pipeline: run 5-pass extraction on N questions with local vLLM.

Usage:
    # 1. Start vLLM server first:
    python -m vllm.entrypoints.openai.api_server \
        --model /root/shared-nvme/llm_edu/models/Qwen3.6-27B-AWQ-INT4 \
        --port 8000 --tensor-parallel-size 2 --gpu-memory-utilization 0.85

    # 2. Run batch extraction:
    python run_extraction_batch.py \
        --provider api_vllm \
        --input data/full_question.json \
        --output data/extraction_batch_results.json \
        --limit 100 \
        --concurrency 2 \
        --review-mode fast \
        --max-tokens 4096

    # Resume from checkpoint (skip already processed questions):
    python run_extraction_batch.py --resume --output data/extraction_batch_results.json
"""

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
load_dotenv()

from config import get_provider_config
from llm_providers_new import get_llm_provider
from core_new.extraction_pipeline import ExtractionPipeline


def load_questions(path: str, limit: int = 0, offset: int = 0) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        questions = json.load(f)
    if not isinstance(questions, list):
        raise ValueError(f"Expected a JSON array, got {type(questions).__name__}")
    # Assign stable IDs if missing
    for i, q in enumerate(questions):
        if "id" not in q:
            q["id"] = f"q_{offset + i:04d}"
    if offset:
        questions = questions[offset:]
    if limit > 0:
        questions = questions[:limit]
    return questions


def load_checkpoint(output_path: str) -> set:
    """Load already-processed question IDs from a previous run."""
    if not os.path.exists(output_path):
        return set()
    try:
        with open(output_path, encoding="utf-8") as f:
            existing = json.load(f)
        if isinstance(existing, list):
            return {r.get("question_id") for r in existing if "question_id" in r}
    except (json.JSONDecodeError, OSError):
        pass
    return set()


def save_checkpoint(output_path: str, results: List[Dict[str, Any]]):
    """Atomically save results to JSON."""
    tmp = output_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    os.replace(tmp, output_path)


def print_summary(result: Dict[str, Any], idx: int, total: int, elapsed: float):
    qid = result.get("question_id", "?")
    if "error" in result:
        print(f"  [{idx}/{total}] {qid} — ERROR: {result['error']} ({elapsed:.1f}s)")
        return

    ks = result.get("knowledge_units", {})
    n_ku = len(ks.get("knowledge_units", []))
    n_mech = len(ks.get("mechanisms", []))
    tr = result.get("trigger_rules", {})
    n_tr = len(tr.get("trigger_rules", []))
    rp = result.get("reasoning_pattern", {})
    n_steps = len(rp.get("steps", []))
    review = result.get("review", {})
    readiness = review.get("readiness", {})
    status = readiness.get("status", "N/A")

    print(f"  [{idx}/{total}] {qid} — ku={n_ku} mech={n_mech} trig={n_tr} steps={n_steps} status={status} ({elapsed:.1f}s)")


async def run_batch(args):
    print(f"Loading questions from: {args.input}")
    questions = load_questions(args.input, limit=args.limit, offset=args.offset)
    print(f"Loaded {len(questions)} questions")

    # Resume support
    done_ids: set = set()
    existing_results: List[Dict[str, Any]] = []
    if args.resume:
        done_ids = load_checkpoint(args.output)
        existing_results = []
        if os.path.exists(args.output):
            with open(args.output, encoding="utf-8") as f:
                existing_results = json.load(f)
        print(f"Resuming: {len(done_ids)} already done, {len(questions) - len(done_ids)} remaining")

    remaining = [q for q in questions if q.get("id") not in done_ids]
    if not remaining:
        print("All questions already processed.")
        return

    # Filter by type if requested
    if args.types:
        type_set = set(args.types.split(","))
        remaining = [q for q in remaining if q.get("type") in type_set]
        print(f"Filtered to types {type_set}: {len(remaining)} questions")

    # Init provider
    print(f"Initializing extraction provider: {args.provider}")
    config = get_provider_config(args.provider)
    if args.model_path:
        config["model_path"] = args.model_path
    provider = get_llm_provider(config)

    # Optional separate review provider (e.g. GLM-5.1 for deep review)
    review_provider = None
    if args.review_provider:
        print(f"Initializing review provider: {args.review_provider}")
        review_config = get_provider_config(args.review_provider)
        review_provider = get_llm_provider(review_config)

    pipeline = ExtractionPipeline(
        provider,
        max_tokens=args.max_tokens,
        enable_thinking=False,
        review_mode=args.review_mode,
        review_provider=review_provider,
    )
    review_info = f"review={args.review_provider}" if review_provider else f"review=same({args.provider})"
    print(f"Review mode: {args.review_mode}, review_provider: {review_info}, concurrency: {args.concurrency}, max_tokens: {args.max_tokens}")

    semaphore = asyncio.Semaphore(args.concurrency)
    results = list(existing_results)
    completed = len(existing_results)
    total = len(questions)
    start_time = time.time()

    async def process(q):
        nonlocal completed
        async with semaphore:
            return await pipeline.extract(q)

    # Process in chunks for periodic checkpointing
    chunk_size = args.checkpoint_every
    for chunk_start in range(0, len(remaining), chunk_size):
        chunk = remaining[chunk_start:chunk_start + chunk_size]
        chunk_tasks = [process(q) for q in chunk]
        chunk_results = await asyncio.gather(*chunk_tasks)

        for q, result in zip(chunk, chunk_results):
            completed += 1
            elapsed = time.time() - start_time
            print_summary(result, completed, total, elapsed)
            results.append(result)

        # Periodic checkpoint
        save_checkpoint(args.output, results)
        avg_time = (time.time() - start_time) / max(completed - len(existing_results), 1)
        remaining_count = total - completed
        eta = avg_time * remaining_count
        print(f"  Checkpoint saved ({completed}/{total}). Avg: {avg_time:.1f}s/q, ETA: {eta/60:.1f}min")

    # Final save
    save_checkpoint(args.output, results)
    total_elapsed = time.time() - start_time
    processed_count = completed - len(existing_results)
    print(f"\nDone: {completed}/{total} questions in {total_elapsed:.1f}s ({total_elapsed/max(processed_count,1):.1f}s/q avg)")
    print(f"Results saved to: {args.output}")

    # Quick stats
    statuses = {}
    for r in results:
        s = r.get("review", {}).get("readiness", {}).get("status", "error")
        statuses[s] = statuses.get(s, 0) + 1
    print(f"Status distribution: {statuses}")


def main():
    parser = argparse.ArgumentParser(description="Batch extraction pipeline for 408 questions")
    parser.add_argument("--provider", default="api_vllm", help="Provider name from config.py (default: api_vllm)")
    parser.add_argument("--input", default="data/full_question.json", help="Input questions JSON file")
    parser.add_argument("--output", default="data/extraction_batch_results.json", help="Output results JSON file")
    parser.add_argument("--limit", type=int, default=100, help="Max questions to process (0=all)")
    parser.add_argument("--offset", type=int, default=0, help="Start offset in question list")
    parser.add_argument("--concurrency", type=int, default=2, help="Concurrent extractions")
    parser.add_argument("--review-mode", default="fast", choices=["none", "fast", "deep", "legacy"])
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max tokens per extraction pass")
    parser.add_argument("--resume", action="store_true", help="Skip already-processed questions")
    parser.add_argument("--checkpoint-every", type=int, default=10, help="Save checkpoint every N questions")
    parser.add_argument("--types", default=None, help="Comma-separated question types to include (e.g. 单选题,主观题)")
    parser.add_argument("--model-path", default=None, help="Override model_path in provider config")
    parser.add_argument("--review-provider", default=None, help="Separate provider for P5 review (e.g. glm5.1)")
    args = parser.parse_args()
    asyncio.run(run_batch(args))


if __name__ == "__main__":
    main()
