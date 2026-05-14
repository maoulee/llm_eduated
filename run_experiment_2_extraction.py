"""Experiment 2: Markdown extraction pipeline.

Phase 1: Local 27B extracts each question into Markdown (P1-P4)
Phase 2: GLM reviews and corrects the extraction

Results saved to docs/experiment_2_results.json
Each question's raw Markdown also saved to docs/extractions/{question_id}.md
"""

import asyncio
import json
import os
import time
from typing import Any, Dict

from dotenv import load_dotenv
load_dotenv()

from config import get_provider_config
from llm_providers_new import get_llm_provider
from core_new.extraction_pipeline import ExtractionPipeline
from core_new.extraction_review import RuleChecker, DomainCritic, ReadinessAggregator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_fields(d: Any, max_depth: int = 3) -> int:
    """Count non-empty leaf fields in a dict."""
    if not isinstance(d, dict):
        return 0
    count = 0
    for v in d.values():
        if isinstance(v, dict) and max_depth > 0:
            count += _count_fields(v, max_depth - 1)
        elif isinstance(v, list):
            count += len(v)
        elif v:
            count += 1
    return count


def _safe_get_nested(data: Dict, *keys, default=None):
    """Safely navigate nested dicts."""
    obj = data
    for k in keys:
        if isinstance(obj, dict):
            obj = obj.get(k, default)
        else:
            return default
        if obj is None:
            return default
    return obj


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    from run_extraction_sample import QUESTIONS

    # --- Init local extraction provider ---
    extract_config = get_provider_config("api_vllm")
    served_model = os.environ.get("VLLM_SERVED_MODEL")
    if served_model:
        extract_config["model_path"] = served_model
    extract_provider = get_llm_provider(extract_config)
    print(f"Extraction provider: {extract_config.get('model_path', 'api_vllm')}")

    # --- Init GLM review provider (optional) ---
    glm_provider = None
    glm_available = False
    glm_api_key = os.environ.get("GLM_API_KEY")
    if glm_api_key:
        try:
            glm_config = get_provider_config("glm5.1")
            glm_provider = get_llm_provider(glm_config)
            glm_available = True
            print(f"GLM review provider: {glm_config.get('model_path', 'glm5.1')}")
        except Exception as e:
            print(f"GLM provider init failed (will skip GLM review): {e}")
    else:
        print("GLM_API_KEY not set — skipping GLM review (RuleChecker only)")

    # --- Create output directories ---
    extractions_dir = os.path.join(os.path.dirname(__file__), "docs", "extractions")
    os.makedirs(extractions_dir, exist_ok=True)

    # --- Build pipeline ---
    pipeline = ExtractionPipeline(
        extract_provider,
        max_tokens=8192,
        enable_thinking=True,
        review_mode="none",  # We handle review manually below
        output_format="markdown",
    )

    all_results = []
    total_start = time.time()

    for i, q in enumerate(QUESTIONS):
        qid = q.get("id", "unknown")
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(QUESTIONS)}] Question: {qid} — {q['prompt'][:50]}...")
        start = time.time()

        # --- Phase 1: Extraction (P1-P4) ---
        try:
            result = await pipeline.extract(q)
        except Exception as e:
            print(f"  EXTRACTION ERROR: {e}")
            all_results.append({
                "question_id": qid,
                "extraction_success": False,
                "error": str(e),
                "time": round(time.time() - start, 1),
            })
            continue

        elapsed = time.time() - start

        if "error" in result:
            print(f"  EXTRACTION FAILED: {result['error']}")
            all_results.append({
                "question_id": qid,
                "extraction_success": False,
                "error": result["error"],
                "time": round(elapsed, 1),
            })
            continue

        # --- Save raw Markdown for each pass ---
        # The pipeline returns parsed dicts; we serialize them as Markdown-like text
        md_content = _build_extraction_markdown(result, q)
        md_path = os.path.join(extractions_dir, f"{qid}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"  Saved extraction to: {md_path}")

        # --- Count extraction quality metrics ---
        p1 = result.get("question_structure", {})
        p2 = result.get("knowledge_units", {})
        p3 = result.get("trigger_rules", {})
        p4 = result.get("reasoning_pattern", {})

        p1_fields = _count_fields(p1)
        ku_count = len(p2.get("knowledge_units", []))
        mech_count = len(p2.get("mechanisms", []))
        trigger_count = len(p3.get("trigger_rules", []))
        steps_count = len(p4.get("steps", []))

        # --- Phase 2: Review ---
        # Build extraction_result structure expected by RuleChecker
        extraction_for_review = {
            "question_structure": p1,
            "knowledge_units": p2,
            "trigger_rules": p3,
            "reasoning_pattern": p4,
            "raw_question": q,
        }

        # P5a: RuleChecker (always runs, no LLM needed)
        rule_result = RuleChecker.validate(extraction_for_review)
        rule_valid = rule_result.get("schema_valid", False)
        ac = rule_result.get("answer_consistency", {})
        ac_consistent = ac.get("consistent", "N/A") if ac.get("checked") else "not checked"
        orphan_count = len(rule_result.get("link_validation", {}).get("orphan_targets", []))

        print(f"  P1 fields={p1_fields}, KU={ku_count}, mechanisms={mech_count}, "
              f"triggers={trigger_count}, steps={steps_count}")
        print(f"  RuleChecker: schema_valid={rule_valid}, answer_consistent={ac_consistent}, "
              f"orphans={orphan_count}")

        # P5b: DomainCritic (GLM, if available)
        domain_result = {}
        readiness_status = "candidate"
        if glm_available and glm_provider is not None:
            try:
                critic = DomainCritic(
                    glm_provider,
                    max_tokens=10000,
                    enable_thinking=True,
                )
                domain_result = await critic.review(extraction_for_review, rule_result)
                domain_major = len(domain_result.get("domain_review", {}).get("major_issues", []))
                domain_minor = len(domain_result.get("domain_review", {}).get("minor_issues", []))
                print(f"  DomainCritic: {domain_major} major, {domain_minor} minor issues")
            except Exception as e:
                print(f"  DomainCritic error (skipping): {e}")
                domain_result = {"error": str(e)}

        # P5c: ReadinessAggregator
        readiness = ReadinessAggregator.aggregate(rule_result, domain_result)
        readiness_status = readiness.get("status", "unknown")
        requires_human = readiness.get("requires_human_or_rule_check", False)
        print(f"  Readiness: {readiness_status} (requires_human={requires_human})")

        all_results.append({
            "question_id": qid,
            "extraction_success": True,
            "p1_fields_found": p1_fields,
            "p1_fields_total": 10,  # approximate expected count
            "knowledge_units_count": ku_count,
            "mechanisms_count": mech_count,
            "trigger_rules_count": trigger_count,
            "reasoning_steps_count": steps_count,
            "rule_validation": {
                "schema_valid": rule_valid,
                "answer_consistent": ac_consistent,
                "orphan_count": orphan_count,
            },
            "domain_review_available": glm_available,
            "review_readiness": readiness_status,
            "requires_human": requires_human,
            "md_file": f"docs/extractions/{qid}.md",
            "time": round(elapsed, 1),
        })

    total_elapsed = time.time() - total_start
    total = len(QUESTIONS)

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"Experiment 2 Summary ({total} questions, {total_elapsed:.1f}s total)")
    print(f"{'='*60}")

    successful = [r for r in all_results if r.get("extraction_success")]
    failed = [r for r in all_results if not r.get("extraction_success")]

    print(f"Extraction success: {len(successful)}/{total}")
    if failed:
        print(f"Failed: {[r['question_id'] for r in failed]}")

    if successful:
        avg_p1 = sum(r["p1_fields_found"] for r in successful) / len(successful)
        avg_ku = sum(r["knowledge_units_count"] for r in successful) / len(successful)
        avg_mech = sum(r["mechanisms_count"] for r in successful) / len(successful)
        avg_trig = sum(r["trigger_rules_count"] for r in successful) / len(successful)
        avg_steps = sum(r["reasoning_steps_count"] for r in successful) / len(successful)
        avg_time = sum(r["time"] for r in successful) / len(successful)

        schema_ok = sum(1 for r in successful if r.get("rule_validation", {}).get("schema_valid"))
        candidate_count = sum(1 for r in successful if r.get("review_readiness") == "candidate")

        print(f"\n  Avg P1 fields:     {avg_p1:.1f}")
        print(f"  Avg knowledge:     {avg_ku:.1f}")
        print(f"  Avg mechanisms:    {avg_mech:.1f}")
        print(f"  Avg triggers:      {avg_trig:.1f}")
        print(f"  Avg steps:         {avg_steps:.1f}")
        print(f"  Avg time:          {avg_time:.1f}s/question")
        print(f"  Schema valid:      {schema_ok}/{len(successful)}")
        print(f"  Candidate status:  {candidate_count}/{len(successful)}")
        print(f"  GLM review used:   {'yes' if glm_available else 'no (GLM_API_KEY not set)'}")

    # --- Save results ---
    output_path = os.path.join(os.path.dirname(__file__), "docs", "experiment_2_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {output_path}")


def _build_extraction_markdown(result: Dict[str, Any], question: Dict[str, Any]) -> str:
    """Build a Markdown representation of the extraction result for saving."""
    qid = result.get("question_id", question.get("id", "unknown"))
    parts = [f"# Extraction: {qid}\n"]

    # Question structure
    p1 = result.get("question_structure", {})
    if p1:
        parts.append("## Question Structure (P1)\n")
        parts.append(f"```json\n{json.dumps(p1, ensure_ascii=False, indent=2)}\n```\n")

    # Knowledge units
    p2 = result.get("knowledge_units", {})
    if p2:
        parts.append("## Knowledge Units (P2)\n")
        for ku in p2.get("knowledge_units", []):
            parts.append(f"### {ku.get('name', 'unnamed')}\n")
            parts.append(f"- Description: {ku.get('description', '')}\n")
            parts.append(f"- Subtype: {ku.get('subtype', '')}\n")
            parts.append(f"- Subject: {ku.get('subject', '')}\n\n")
        for mech in p2.get("mechanisms", []):
            parts.append(f"### Mechanism: {mech.get('name', 'unnamed')}\n")
            parts.append(f"- Description: {mech.get('description', '')}\n")
            parts.append(f"- Affects: {mech.get('affects_what', '')}\n\n")

    # Trigger rules
    p3 = result.get("trigger_rules", {})
    if p3:
        parts.append("## Trigger Rules (P3)\n")
        parts.append(f"```json\n{json.dumps(p3, ensure_ascii=False, indent=2)}\n```\n")

    # Reasoning pattern
    p4 = result.get("reasoning_pattern", {})
    if p4:
        parts.append("## Reasoning Pattern (P4)\n")
        parts.append(f"```json\n{json.dumps(p4, ensure_ascii=False, indent=2)}\n```\n")

    # Review
    review = result.get("review", {})
    if review:
        parts.append("## Review (P5)\n")
        parts.append(f"```json\n{json.dumps(review, ensure_ascii=False, indent=2)}\n```\n")

    return "\n".join(parts)


if __name__ == "__main__":
    asyncio.run(main())
