# core_new/extraction_pipeline.py

"""
Multi-pass extraction pipeline for 408 question structuring.

Uses GLM-5.1 (or any OpenAI-compatible provider) to extract structured
entities from raw 408 exam questions through 5 sequential passes:

  P1: question_structure  → conditions, target, constraints, distractors
  P2: knowledge_units     → concepts, facts, mechanisms
  P3: trigger_rules       → question signals → mechanism activation
  P4: reasoning_pattern   → step-by-step reasoning procedure
  P5: link_and_validate   → cross-reference and consistency check

Usage:
    from config import get_provider_config
    from llm_providers_new import get_llm_provider
    from core_new.extraction_pipeline import ExtractionPipeline

    config = get_provider_config("glm5.1")
    provider = get_llm_provider(config)
    pipeline = ExtractionPipeline(provider)

    result = await pipeline.extract(raw_question)
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from .extraction_prompts import (
    PASS1_QUESTION_STRUCTURE,
    PASS2_KNOWLEDGE_UNITS,
    PASS3_TRIGGER_RULES,
    PASS4_REASONING_PATTERN,
    PASS5_LINK_AND_VALIDATE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ExtractionPipeline:
    """Orchestrates the 5-pass extraction pipeline for a single question."""

    def __init__(self, llm_provider, max_tokens: int = 8192, enable_thinking: bool = False):
        self.llm = llm_provider
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking

    def _parse_json_output(self, raw: Optional[Dict]) -> Optional[Dict]:
        if raw is None:
            return None
        return raw

    async def _run_pass(
        self,
        pass_name: str,
        prompt: str,
    ) -> Optional[Dict]:
        logger.info("Running extraction pass: %s", pass_name)
        messages = [[{"role": "user", "content": prompt}]]
        results = await self.llm.generate_json_batch(
            messages,
            max_tokens=self.max_tokens,
            enable_thinking=self.enable_thinking,
        )
        result = results[0] if results else None
        if result is None:
            logger.warning("Pass %s returned None", pass_name)
        else:
            logger.info("Pass %s completed successfully", pass_name)
        return result

    async def extract(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the full 5-pass extraction pipeline on a single question.

        Args:
            question: dict with keys 'type', 'prompt', 'answer' (and optionally 'id')

        Returns:
            dict with keys: question_structure, knowledge_units, trigger_rules,
                            reasoning_pattern, validation, raw_question
        """
        q_type = question.get("type", "单选题")
        stem = question.get("prompt", "")
        answer = question.get("answer", "")
        q_id = question.get("id", "unknown")

        logger.info("Starting extraction pipeline for question: %s", q_id)

        # --- P1: Question Structure ---
        p1_prompt = PASS1_QUESTION_STRUCTURE.format(
            question_type=q_type,
            stem=stem,
            answer=answer,
        )
        p1_result = await self._run_pass("P1_question_structure", p1_prompt)
        if p1_result is None:
            return self._error_result(q_id, "P1 failed: could not extract question structure")

        structure_str = json.dumps(p1_result.get("structure", {}), ensure_ascii=False)
        distractor_str = json.dumps(p1_result.get("distractor_analysis", []), ensure_ascii=False)

        # --- P2: Knowledge Units ---
        p2_prompt = PASS2_KNOWLEDGE_UNITS.format(
            stem=stem,
            structure=structure_str,
            answer=answer,
        )
        p2_result = await self._run_pass("P2_knowledge_units", p2_prompt)
        if p2_result is None:
            return self._error_result(q_id, "P2 failed: could not extract knowledge units")

        ku_str = json.dumps(p2_result, ensure_ascii=False)

        # --- P3: Trigger Rules ---
        p3_prompt = PASS3_TRIGGER_RULES.format(
            stem=stem,
            structure=structure_str,
            knowledge_units=ku_str,
            answer=answer,
        )
        p3_result = await self._run_pass("P3_trigger_rules", p3_prompt)
        if p3_result is None:
            return self._error_result(q_id, "P3 failed: could not extract trigger rules")

        tr_str = json.dumps(p3_result, ensure_ascii=False)

        # --- P4: Reasoning Pattern ---
        p4_prompt = PASS4_REASONING_PATTERN.format(
            stem=stem,
            structure=structure_str,
            knowledge_units=ku_str,
            trigger_rules=tr_str,
            answer=answer,
        )
        p4_result = await self._run_pass("P4_reasoning_pattern", p4_prompt)
        if p4_result is None:
            return self._error_result(q_id, "P4 failed: could not extract reasoning pattern")

        rp_str = json.dumps(p4_result, ensure_ascii=False)

        # --- P5: Link & Validate ---
        p5_prompt = PASS5_LINK_AND_VALIDATE.format(
            stem=stem,
            answer=answer,
            structure=structure_str,
            knowledge_units=ku_str,
            trigger_rules=tr_str,
            reasoning_pattern=rp_str,
        )
        p5_result = await self._run_pass("P5_link_and_validate", p5_prompt)

        logger.info("Extraction pipeline completed for question: %s", q_id)

        return {
            "question_id": q_id,
            "question_structure": p1_result,
            "knowledge_units": p2_result,
            "trigger_rules": p3_result,
            "reasoning_pattern": p4_result,
            "validation": p5_result,
            "raw_question": question,
        }

    @staticmethod
    def _error_result(q_id: str, error: str) -> Dict[str, Any]:
        return {
            "question_id": q_id,
            "error": error,
            "raw_question": None,
        }


async def extract_batch(
    provider,
    questions: List[Dict[str, Any]],
    max_tokens: int = 8192,
    concurrency: int = 2,
) -> List[Dict[str, Any]]:
    """
    Run the extraction pipeline on a batch of questions with limited concurrency.

    Args:
        provider: LLM provider instance
        questions: list of question dicts
        max_tokens: max tokens per pass
        concurrency: number of concurrent extractions

    Returns:
        list of extraction results
    """
    pipeline = ExtractionPipeline(provider, max_tokens=max_tokens)
    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async def process(q):
        async with semaphore:
            return await pipeline.extract(q)

    results = await asyncio.gather(*[process(q) for q in questions])
    return list(results)
