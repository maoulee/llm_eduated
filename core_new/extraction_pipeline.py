# core_new/extraction_pipeline.py

"""
Multi-pass extraction pipeline for 408 question structuring.

Usage:
    from core_new.llm_gateway import get_gateway
    from core_new.extraction_pipeline import ExtractionPipeline

    gateway = get_gateway("glm5.1")
    pipeline = ExtractionPipeline(gateway, review_mode="deep")
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
    PASS1_QUESTION_STRUCTURE_MD,
    PASS2_KNOWLEDGE_UNITS_MD,
    PASS3_TRIGGER_RULES_MD,
    PASS4_REASONING_PATTERN_MD,
)
from .extraction_review import RuleChecker, DomainCritic, ReadinessAggregator

try:
    from .markdown_parser import parse_extraction_markdown
except ImportError:
    parse_extraction_markdown = None  # type: ignore[assignment]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _ensure_gateway(obj):
    """Ensure obj is an LLMGateway. Wrap raw providers automatically."""
    from core_new.llm_gateway import LLMGateway
    if isinstance(obj, LLMGateway):
        return obj
    return LLMGateway.from_provider(obj, "wrapped")


class ExtractionPipeline:
    """Orchestrates the 5-pass extraction pipeline for a single question.

    Accepts either an LLMGateway or a raw LLM provider (auto-wrapped).
    All LLM calls go through the gateway for structured error handling.
    """

    def __init__(
        self,
        llm_provider,
        max_tokens: int = 8192,
        enable_thinking: bool = False,
        review_mode: str = "fast",
        review_max_tokens: int = 10000,
        review_provider=None,
        output_format: str = "json",
    ):
        self.llm = _ensure_gateway(llm_provider)
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking
        self.review_mode = review_mode
        self.review_max_tokens = review_max_tokens
        self.review_llm = _ensure_gateway(review_provider) if review_provider else self.llm
        self.output_format = output_format

    async def _run_pass(self, pass_name: str, prompt: str) -> Optional[Dict]:
        logger.info("Running extraction pass: %s", pass_name)
        messages = [[{"role": "user", "content": prompt}]]
        results = await self.llm.generate_json_batch(
            messages, max_tokens=self.max_tokens, enable_thinking=self.enable_thinking,
        )
        r = results[0]
        if not r.ok:
            logger.warning("Pass %s failed: [%s] %s", pass_name, r.error_code, r.error_message)
            return None
        logger.info("Pass %s completed successfully", pass_name)
        return r.parsed_json

    async def _run_pass_md(self, pass_name: str, prompt: str) -> Optional[Dict]:
        """Run extraction pass using Markdown output + thinking mode."""
        messages = [[{"role": "user", "content": prompt}]]
        results = await self.llm.generate_reasoned_batch(
            messages, max_tokens=self.max_tokens, enable_thinking=True,
        )
        r = results[0]
        if not r.ok or not r.content:
            logger.warning("Pass %s (md) failed: [%s] %s", pass_name, r.error_code, r.error_message)
            return None

        content = r.content

        # Try Markdown parse first
        if parse_extraction_markdown is not None:
            parsed = parse_extraction_markdown(content, pass_name)
        else:
            parsed = None

        # Fallback: try JSON parse
        if parsed is None:
            try:
                if "```json" in content:
                    clean = content.split("```json\n", 1)[1].rsplit("```", 1)[0]
                else:
                    start, end = content.find("{"), content.rfind("}")
                    clean = content[start:end + 1] if start != -1 and end != -1 else content
                parsed = json.loads(clean)
            except (json.JSONDecodeError, IndexError, TypeError):
                pass

        return parsed

    async def _run_review(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        if self.review_mode == "none":
            return {}

        if self.review_mode == "legacy":
            return await self._run_legacy_review(extraction_result)

        # P5a: RuleChecker
        logger.info("Running P5a: RuleChecker")
        rule_result = RuleChecker.validate(extraction_result)
        logger.info(
            "RuleChecker: schema_valid=%s, answer_consistent=%s, orphans=%d",
            rule_result.get("schema_valid"),
            rule_result.get("answer_consistency", {}).get("consistent", "N/A"),
            len(rule_result.get("link_validation", {}).get("orphan_targets", [])),
        )

        # P5b: DomainCritic
        enable_thinking = self.review_mode == "deep"
        critic = DomainCritic(
            self.review_llm,
            max_tokens=self.review_max_tokens,
            enable_thinking=enable_thinking,
        )
        domain_result = await critic.review(extraction_result, rule_result)

        # P5c: ReadinessAggregator
        readiness = ReadinessAggregator.aggregate(rule_result, domain_result, fix_result=None)

        return {
            "rule_validation": rule_result,
            "domain_review": domain_result,
            "readiness": readiness,
        }

    async def _run_legacy_review(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        question = extraction_result.get("raw_question", {})
        stem = question.get("prompt", "")
        answer = question.get("answer", "")

        structure = json.dumps(extraction_result.get("question_structure", {}), ensure_ascii=False)
        ku = json.dumps(extraction_result.get("knowledge_units", {}), ensure_ascii=False)
        tr = json.dumps(extraction_result.get("trigger_rules", {}), ensure_ascii=False)
        rp = json.dumps(extraction_result.get("reasoning_pattern", {}), ensure_ascii=False)

        p5_prompt = PASS5_LINK_AND_VALIDATE.format(
            stem=stem, answer=answer, structure=structure,
            knowledge_units=ku, trigger_rules=tr, reasoning_pattern=rp,
        )
        logger.info("Running P5_legacy with review provider")
        messages = [[{"role": "user", "content": p5_prompt}]]
        results = await self.review_llm.generate_json_batch(
            messages, max_tokens=self.max_tokens, enable_thinking=self.enable_thinking,
        )
        r = results[0]
        return r.parsed_json if r.ok else {}

    async def extract(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """Run the full 5-pass extraction pipeline on a single question."""
        q_type = question.get("type", "单选题")
        stem = question.get("prompt", "")
        answer = question.get("answer", "")
        q_id = question.get("id", "unknown")

        logger.info("Starting extraction pipeline for question: %s", q_id)

        # --- P1: Question Structure ---
        if self.output_format == "markdown":
            p1_prompt = PASS1_QUESTION_STRUCTURE_MD.format(question_type=q_type, stem=stem, answer=answer)
            p1_result = await self._run_pass_md("P1", p1_prompt)
        else:
            p1_prompt = PASS1_QUESTION_STRUCTURE.format(question_type=q_type, stem=stem, answer=answer)
            p1_result = await self._run_pass("P1_question_structure", p1_prompt)
        if p1_result is None:
            return self._error_result(q_id, "P1 failed: could not extract question structure")

        structure_str = json.dumps(p1_result.get("structure", {}), ensure_ascii=False)
        distractor_str = json.dumps(p1_result.get("distractor_analysis", []), ensure_ascii=False)

        # --- P2: Knowledge Units ---
        if self.output_format == "markdown":
            p2_prompt = PASS2_KNOWLEDGE_UNITS_MD.format(stem=stem, structure=structure_str, answer=answer)
            p2_result = await self._run_pass_md("P2", p2_prompt)
        else:
            p2_prompt = PASS2_KNOWLEDGE_UNITS.format(stem=stem, structure=structure_str, answer=answer)
            p2_result = await self._run_pass("P2_knowledge_units", p2_prompt)
        if p2_result is None:
            return self._error_result(q_id, "P2 failed: could not extract knowledge units")

        ku_str = json.dumps(p2_result, ensure_ascii=False)

        # --- P3: Trigger Rules ---
        if self.output_format == "markdown":
            p3_prompt = PASS3_TRIGGER_RULES_MD.format(stem=stem, structure=structure_str, knowledge_units=ku_str, answer=answer)
            p3_result = await self._run_pass_md("P3", p3_prompt)
        else:
            p3_prompt = PASS3_TRIGGER_RULES.format(stem=stem, structure=structure_str, knowledge_units=ku_str, answer=answer)
            p3_result = await self._run_pass("P3_trigger_rules", p3_prompt)
        if p3_result is None:
            return self._error_result(q_id, "P3 failed: could not extract trigger rules")

        tr_str = json.dumps(p3_result, ensure_ascii=False)

        # --- P4: Reasoning Pattern ---
        if self.output_format == "markdown":
            p4_prompt = PASS4_REASONING_PATTERN_MD.format(stem=stem, structure=structure_str, knowledge_units=ku_str, trigger_rules=tr_str, answer=answer)
            p4_result = await self._run_pass_md("P4", p4_prompt)
        else:
            p4_prompt = PASS4_REASONING_PATTERN.format(stem=stem, structure=structure_str, knowledge_units=ku_str, trigger_rules=tr_str, answer=answer)
            p4_result = await self._run_pass("P4_reasoning_pattern", p4_prompt)
        if p4_result is None:
            return self._error_result(q_id, "P4 failed: could not extract reasoning pattern")

        # --- P5: Review ---
        extraction_result = {
            "question_structure": p1_result,
            "knowledge_units": p2_result,
            "trigger_rules": p3_result,
            "reasoning_pattern": p4_result,
            "raw_question": question,
        }
        review_result = await self._run_review(extraction_result)

        logger.info("Extraction pipeline completed for question: %s", q_id)

        return {
            "question_id": q_id,
            "question_structure": p1_result,
            "knowledge_units": p2_result,
            "trigger_rules": p3_result,
            "reasoning_pattern": p4_result,
            "review": review_result,
            "raw_question": question,
        }

    @staticmethod
    def _error_result(q_id: str, error: str) -> Dict[str, Any]:
        return {"question_id": q_id, "error": error, "raw_question": None}


async def extract_batch(
    provider,
    questions: List[Dict[str, Any]],
    max_tokens: int = 8192,
    concurrency: int = 2,
    review_mode: str = "fast",
    review_provider=None,
) -> List[Dict[str, Any]]:
    """Run the extraction pipeline on a batch of questions with limited concurrency."""
    pipeline = ExtractionPipeline(
        provider, max_tokens=max_tokens, review_mode=review_mode,
        review_provider=review_provider,
    )
    semaphore = asyncio.Semaphore(concurrency)

    async def process(q):
        async with semaphore:
            return await pipeline.extract(q)

    results = await asyncio.gather(*[process(q) for q in questions])
    return list(results)
