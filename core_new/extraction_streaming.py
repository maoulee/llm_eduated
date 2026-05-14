"""Streaming extraction pipeline: producer-consumer architecture.

Producer (local vLLM): Extracts P1-P4, pushes to review queue.
Consumer (GLM API or same provider): Runs P5 review, pushes to output.

Uses asyncio.Queue for backpressure control.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Wrapper for a single question's extraction + metadata."""
    question_id: str
    question: Dict[str, Any]
    extraction: Optional[Dict[str, Any]] = None
    review: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class StreamingExtractionPipeline:
    """Producer-consumer pipeline for extraction + review.

    Usage:
        extract_config = get_provider_config("api_vllm")
        review_config = get_provider_config("glm5.1")
        extract_provider = get_llm_provider(extract_config)
        review_provider = get_llm_provider(review_config)

        pipeline = StreamingExtractionPipeline(
            extract_provider=extract_provider,
            review_provider=review_provider,
            output_format="markdown",
        )
        results = await pipeline.run(questions)
    """

    def __init__(
        self,
        extract_provider,
        review_provider=None,  # If None, use extract_provider for review too
        max_tokens: int = 8192,
        output_format: str = "markdown",
        review_mode: str = "deep",
        review_max_tokens: int = 10000,
        review_queue_size: int = 3,
    ):
        self.extract_llm = extract_provider
        self.review_llm = review_provider or extract_provider
        self.max_tokens = max_tokens
        self.output_format = output_format
        self.review_mode = review_mode
        self.review_max_tokens = review_max_tokens
        self.review_queue_size = review_queue_size

    async def _extract_single(self, question: Dict) -> ExtractionResult:
        """Run P1-P4 extraction for a single question."""
        from .extraction_pipeline import ExtractionPipeline

        pipeline = ExtractionPipeline(
            self.extract_llm,
            max_tokens=self.max_tokens,
            review_mode="none",  # Skip review in extraction; consumer handles P5
        )

        q_id = question.get("id", "unknown")
        try:
            result = await pipeline.extract(question)
            if "error" in result:
                return ExtractionResult(q_id, question, error=result["error"])

            # Build extraction dict from pipeline result
            extraction = {
                "question_structure": result.get("question_structure", {}),
                "knowledge_units": result.get("knowledge_units", {}),
                "trigger_rules": result.get("trigger_rules", {}),
                "reasoning_pattern": result.get("reasoning_pattern", {}),
                "raw_question": question,
            }
            return ExtractionResult(q_id, question, extraction=extraction)
        except Exception as e:
            logger.error("Extraction failed for %s: %s", q_id, e)
            return ExtractionResult(q_id, question, error=str(e))

    async def _review_single(self, item: ExtractionResult) -> ExtractionResult:
        """Run P5 review for a single extraction result."""
        if item.error or item.extraction is None:
            return item

        try:
            from .extraction_review import RuleChecker, DomainCritic, ReadinessAggregator

            # P5a: RuleChecker (pure code, no LLM)
            rule_result = RuleChecker.validate(item.extraction)

            # P5b: DomainCritic (LLM)
            enable_thinking = self.review_mode == "deep"
            critic = DomainCritic(
                self.review_llm,
                max_tokens=self.review_max_tokens,
                enable_thinking=enable_thinking,
            )
            domain_result = await critic.review(item.extraction, rule_result)

            # P5c: ReadinessAggregator (pure code)
            readiness = ReadinessAggregator.aggregate(rule_result, domain_result)

            item.review = {
                "rule_validation": rule_result,
                "domain_review": domain_result,
                "readiness": readiness,
            }
        except Exception as e:
            logger.error("Review failed for %s: %s", item.question_id, e)
            item.review = {"error": str(e)}

        return item

    async def _producer(
        self,
        questions: List[Dict],
        review_queue: asyncio.Queue,
        semaphore: asyncio.Semaphore,
    ):
        """Producer: extract P1-P4 for each question, push to review queue."""
        async def process_and_enqueue(q):
            async with semaphore:
                result = await self._extract_single(q)
            await review_queue.put(result)
            logger.info("Produced extraction for: %s", q.get("id", "?"))

        tasks = [process_and_enqueue(q) for q in questions]
        await asyncio.gather(*tasks)
        # Signal done
        await review_queue.put(None)
        logger.info("Producer finished: %d questions processed", len(questions))

    async def _consumer(
        self,
        review_queue: asyncio.Queue,
        output_queue: asyncio.Queue,
    ):
        """Consumer: pull from review_queue, run P5, push to output_queue."""
        count = 0
        while True:
            item = await review_queue.get()
            if item is None:
                review_queue.task_done()
                await output_queue.put(None)  # propagate sentinel
                break

            reviewed = await self._review_single(item)
            await output_queue.put(reviewed)
            review_queue.task_done()
            count += 1
            logger.info("Reviewed: %s (%d done)", item.question_id, count)

        logger.info("Consumer finished: %d reviews completed", count)

    async def run(
        self,
        questions: List[Dict],
        extract_concurrency: int = 2,
        on_result: Optional[Callable] = None,
    ) -> List[Dict]:
        """Run the full streaming pipeline.

        Args:
            questions: List of question dicts with id, type, prompt, answer.
            extract_concurrency: Max concurrent extractions on local vLLM.
            on_result: Optional async callback called for each completed result.

        Returns:
            List of final result dicts.
        """
        review_queue = asyncio.Queue(maxsize=self.review_queue_size)
        output_queue = asyncio.Queue()
        semaphore = asyncio.Semaphore(extract_concurrency)

        results = []

        async def result_collector():
            while True:
                item = await output_queue.get()
                if item is None:
                    output_queue.task_done()
                    break

                # Convert to output dict
                if item.error:
                    out = {
                        "question_id": item.question_id,
                        "error": item.error,
                        "raw_question": item.question,
                    }
                else:
                    out = {
                        "question_id": item.question_id,
                        **item.extraction,
                        "review": item.review,
                        "raw_question": item.question,
                    }

                if on_result:
                    try:
                        await on_result(out)
                    except Exception as e:
                        logger.error("on_result callback failed: %s", e)

                results.append(out)
                output_queue.task_done()

        # Run all three coroutines concurrently
        await asyncio.gather(
            self._producer(questions, review_queue, semaphore),
            self._consumer(review_queue, output_queue),
            result_collector(),
        )

        return results
