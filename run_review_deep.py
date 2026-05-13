"""
Deep review + OrphanResolver for extraction results.

Reads existing extraction results (fast mode), identifies high-risk questions,
runs deep DomainCritic review, resolves orphan references, and outputs
updated results with readiness upgrade.

Usage:
    # Deep review all questions with orphans or major issues
    python run_review_deep.py

    # Deep review specific question IDs
    python run_review_deep.py --ids 2009-12 2009-14

    # Skip deep review, only resolve orphans
    python run_review_deep.py --resolve-only

    # Specify input/output
    python run_review_deep.py --input docs/extraction_sample_results.json --output docs/extraction_deep_results.json
"""

import argparse
import asyncio
import json
import os
import time
from typing import Any, Dict, List

from dotenv import load_dotenv
load_dotenv()

from config import get_provider_config
from llm_providers_new import get_llm_provider
from core_new.extraction_review import (
    RuleChecker,
    DomainCritic,
    ReadinessAggregator,
    OrphanReferenceResolver,
)


def classify_risk(result: Dict[str, Any]) -> str:
    """Classify a result's risk level based on rule_validation."""
    review = result.get("review", {})
    if not review:
        return "no_review"

    rv = review.get("rule_validation", {})
    ac = rv.get("answer_consistency", {})
    orphans = len(rv.get("link_validation", {}).get("orphan_targets", []))
    mismatches = len(rv.get("link_validation", {}).get("type_mismatches", []))
    dr = review.get("domain_review", {}).get("domain_review", {})
    major = len(dr.get("major_issues", []))

    if not ac.get("checked") or not ac.get("consistent", True):
        return "high"
    if orphans > 2 or mismatches > 0:
        return "high"
    if orphans > 0 or major > 0:
        return "medium"
    return "low"


async def deep_review_question(
    provider,
    result: Dict[str, Any],
    resolve_orphans: bool = True,
    run_deep_critic: bool = True,
) -> Dict[str, Any]:
    """Run deep DomainCritic + OrphanResolver + LinkRepairer on a single result."""
    import copy
    from core_new.extraction_review import LinkRepairer

    updated = copy.deepcopy(result)

    # Re-run RuleChecker (in case data was modified)
    rule_result = RuleChecker.validate(updated)

    # Resolve orphans + repair links
    if resolve_orphans and rule_result.get("link_validation", {}).get("orphan_targets"):
        resolver = OrphanReferenceResolver(provider)
        resolution = await resolver.resolve(updated, rule_result)

        if resolution.get("resolutions"):
            updated = OrphanReferenceResolver.apply_resolutions(updated, resolution)
            updated["orphan_resolution"] = resolution

            # Repair links: rewrite P3/P4 references to match new/canonical names
            repairer = LinkRepairer()
            updated = repairer.repair(updated, resolution)
            updated["link_repairs"] = repairer.summary()

            # Re-validate after resolution + repair
            rule_result = RuleChecker.validate(updated)

    # Deep DomainCritic (optional)
    if run_deep_critic:
        critic = DomainCritic(provider, max_tokens=16384, enable_thinking=True)
        domain_result = await critic.review(updated, rule_result)
    else:
        domain_result = {
            "domain_review": {"major_issues": [], "minor_issues": [], "uncertain_items": []},
            "review_summary": "Deep critic skipped after link repair; prior review is stale.",
            "recommended_status": "candidate",
            "stale": True,
        }

    # Aggregate
    readiness = ReadinessAggregator.aggregate(rule_result, domain_result)

    updated["review"] = {
        "rule_validation": rule_result,
        "domain_review": domain_result,
        "readiness": readiness,
    }

    return updated


async def main():
    parser = argparse.ArgumentParser(description="Deep review + orphan resolution")
    parser.add_argument("--input", default="docs/extraction_sample_results.json")
    parser.add_argument("--output", default="docs/extraction_deep_results.json")
    parser.add_argument("--ids", nargs="*", help="Specific question IDs to review")
    parser.add_argument("--resolve-only", action="store_true", help="Only resolve orphans, skip deep critic")
    parser.add_argument("--provider", default="glm5.1")
    args = parser.parse_args()

    with open(args.input, encoding="utf-8") as f:
        results = json.load(f)

    config = get_provider_config(args.provider)
    provider = get_llm_provider(config)

    # Select which questions to process
    targets: List[Dict[str, Any]] = []
    if args.ids:
        targets = [r for r in results if r.get("question_id") in args.ids]
    else:
        # Process all high/medium risk questions
        for r in results:
            if "error" in r:
                continue
            risk = classify_risk(r)
            if risk in ("high", "medium", "no_review"):
                targets.append(r)

    if not targets:
        print("No questions need deep review.")
        return

    print(f"Selected {len(targets)} questions for deep review:")
    for r in targets:
        risk = classify_risk(r)
        orphans = len(r.get("review", {}).get("rule_validation", {})
                       .get("link_validation", {}).get("orphan_targets", []))
        print(f"  {r.get('question_id', '?')}: risk={risk}, orphans={orphans}")

    updated_results = list(results)  # copy
    total_start = time.time()

    for i, target in enumerate(targets):
        q_id = target.get("question_id", "?")
        print(f"\n[{i+1}/{len(targets)}] Deep reviewing: {q_id}")
        start = time.time()

        try:
            updated = await deep_review_question(
                provider, target,
                resolve_orphans=True,
                run_deep_critic=not args.resolve_only,
            )
            elapsed = time.time() - start

            # Replace in results
            for j, r in enumerate(updated_results):
                if r.get("question_id") == q_id:
                    updated_results[j] = updated
                    break

            readiness = updated.get("review", {}).get("readiness", {})
            orphan_res = updated.get("orphan_resolution", {})
            print(f"  Time: {elapsed:.1f}s")
            print(f"  Readiness: {readiness.get('status', '?')}")
            if orphan_res.get("resolutions"):
                for res in orphan_res["resolutions"]:
                    print(f"  Orphan '{res.get('orphan_name')}': {res.get('verdict')}")

        except Exception as e:
            print(f"  ERROR: {e}")

    total_elapsed = time.time() - total_start
    print(f"\nTotal: {len(targets)} questions in {total_elapsed:.1f}s")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(updated_results, f, ensure_ascii=False, indent=2)
    print(f"Saved to: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
