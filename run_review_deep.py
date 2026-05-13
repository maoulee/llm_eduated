"""
Deep review + OrphanResolver + DomainIssueFixer for extraction results.

Reads existing extraction results (fast mode), identifies high-risk questions,
runs deep DomainCritic review, resolves orphan references, fixes fixable
domain issues via localized patches, and outputs updated results.

Pipeline flow:
  1. RuleChecker
  2. OrphanReferenceResolver + LinkRepairer
  3. RuleChecker (re-validate)
  4. DomainCritic (deep, with thinking)
  5. ReadinessAggregator (initial status)
  6. IF needs_content_fix: DomainIssueFixer → RuleChecker → DomainCritic recheck
  7. ReadinessAggregator (final status)

Usage:
    # Deep review all questions with orphans or major issues
    python run_review_deep.py

    # Deep review specific question IDs
    python run_review_deep.py --ids 2009-12 2009-14

    # Skip deep review, only resolve orphans
    python run_review_deep.py --resolve-only

    # Skip auto-fix (no DomainIssueFixer)
    python run_review_deep.py --no-fix

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
    LinkRepairer,
    DomainIssueFixer,
)


def classify_risk(result: Dict[str, Any]) -> str:
    """Classify a result's risk level based on review status."""
    review = result.get("review", {})
    if not review:
        return "no_review"

    # Use final_readiness if available, else initial_readiness, else readiness
    readiness = review.get("final_readiness") or review.get("initial_readiness") or review.get("readiness", {})
    status = readiness.get("status", "")

    if status in ("rejected", "needs_human_judgment", "auto_fixed_recheck_failed"):
        return "high"
    if status in ("needs_content_fix", "needs_link_fix", "auto_fix_partial"):
        return "medium"
    if status in ("auto_fixed_recheck_passed", "candidate"):
        return "low"

    # Fallback: check raw fields
    rv = review.get("rule_validation", {})
    ac = rv.get("answer_consistency", {})
    orphans = len(rv.get("link_validation", {}).get("orphan_targets", []))
    mismatches = len(rv.get("link_validation", {}).get("type_mismatches", []))
    dr = review.get("initial_domain_review", review.get("domain_review", {})).get("domain_review", {})
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
    run_fix: bool = True,
) -> Dict[str, Any]:
    """Run full deep review pipeline on a single result.

    Steps:
      1. RuleChecker
      2. OrphanReferenceResolver + LinkRepairer (if orphans)
      3. RuleChecker (re-validate)
      4. DomainCritic (deep)
      5. ReadinessAggregator (initial)
      6. IF needs_content_fix AND run_fix: DomainIssueFixer → re-validate → recheck
      7. ReadinessAggregator (final)
    """
    import copy

    updated = copy.deepcopy(result)

    # Step 1: Re-run RuleChecker
    rule_result = RuleChecker.validate(updated)

    # Step 2: Resolve orphans + repair links
    if resolve_orphans and rule_result.get("link_validation", {}).get("orphan_targets"):
        resolver = OrphanReferenceResolver(provider)
        resolution = await resolver.resolve(updated, rule_result)

        if resolution.get("resolutions"):
            updated = OrphanReferenceResolver.apply_resolutions(updated, resolution)
            updated["orphan_resolution"] = resolution

            repairer = LinkRepairer()
            updated = repairer.repair(updated, resolution)
            updated["link_repairs"] = repairer.summary()

            # Step 3: Re-validate after resolution + repair
            rule_result = RuleChecker.validate(updated)

    # Step 4: Deep DomainCritic (optional)
    if run_deep_critic:
        critic = DomainCritic(provider, max_tokens=10000, enable_thinking=True)
        domain_result = await critic.review(updated, rule_result)
    else:
        domain_result = {
            "domain_review": {"major_issues": [], "minor_issues": [], "uncertain_items": []},
            "review_summary": "Deep critic skipped after link repair; prior review is stale.",
            "recommended_status": "candidate",
            "stale": True,
        }

    # Step 5: Aggregate (initial status)
    readiness = ReadinessAggregator.aggregate(rule_result, domain_result)

    # Step 6: Fix loop (max 1 iteration)
    fix_result = None
    recheck_domain_result = None
    final_readiness = readiness

    if run_fix and readiness.get("status") == "needs_content_fix" and run_deep_critic:
        fixer = DomainIssueFixer(provider, max_tokens=8192)
        fix_raw = await fixer.fix(updated, domain_result)

        # Apply patched result and strip to prevent circular reference
        if fix_raw.get("fix_count", 0) > 0:
            updated = fix_raw["fixed_result"]
        # Build serializable summary (no fixed_result reference)
        fix_result = {
            "fix_count": fix_raw.get("fix_count", 0),
            "patches_applied": fix_raw.get("patches_applied", []),
            "patches_rejected": fix_raw.get("patches_rejected", []),
            "patches_skipped": fix_raw.get("patches_skipped", []),
        }

        if fix_result["fix_count"] > 0:
            # Re-validate after patches
            rule_result = RuleChecker.validate(updated)

            # DomainCritic recheck (max 1 iteration)
            critic = DomainCritic(provider, max_tokens=10000, enable_thinking=True)
            recheck_domain_result = await critic.review(updated, rule_result)

            # Final aggregation
            final_readiness = ReadinessAggregator.aggregate(
                rule_result, recheck_domain_result, fix_result=fix_result,
            )

    # Build versioned review structure:
    # - initial_domain_review: pre-fix critic results (always present)
    # - fix_result: patches applied/rejected/skipped (only if fix ran)
    # - domain_recheck: post-fix critic results (only if fix ran + recheck)
    # - rule_validation: latest rule check (after all mutations)
    # - initial_readiness: status before fix
    # - final_readiness: final status (based on recheck if fix ran)
    review = {
        "initial_domain_review": domain_result,
        "rule_validation": rule_result,
        "initial_readiness": readiness,
        "final_readiness": final_readiness,
    }

    if fix_result:
        review["fix_result"] = fix_result
    if recheck_domain_result:
        review["domain_recheck"] = recheck_domain_result

    updated["review"] = review

    return updated


async def main():
    parser = argparse.ArgumentParser(description="Deep review + orphan resolution + auto-fix")
    parser.add_argument("--input", default="docs/extraction_sample_results.json")
    parser.add_argument("--output", default="docs/extraction_deep_results.json")
    parser.add_argument("--ids", nargs="*", help="Specific question IDs to review")
    parser.add_argument("--resolve-only", action="store_true", help="Only resolve orphans, skip deep critic")
    parser.add_argument("--no-fix", action="store_true", help="Skip DomainIssueFixer auto-fix")
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
                run_fix=not args.no_fix,
            )
            elapsed = time.time() - start

            # Replace in results
            for j, r in enumerate(updated_results):
                if r.get("question_id") == q_id:
                    updated_results[j] = updated
                    break

            final_readiness = updated.get("review", {}).get("final_readiness", {})
            initial_readiness = updated.get("review", {}).get("initial_readiness", {})
            orphan_res = updated.get("orphan_resolution", {})
            fix_res = updated.get("review", {}).get("fix_result", {})

            print(f"  Time: {elapsed:.1f}s")
            initial_status = initial_readiness.get("status", "?")
            final_status = final_readiness.get("status", initial_status)
            if initial_status != final_status:
                print(f"  Readiness: {initial_status} → {final_status}")
            else:
                print(f"  Readiness: {final_status}")

            if orphan_res.get("resolutions"):
                for res in orphan_res["resolutions"]:
                    print(f"  Orphan '{res.get('orphan_name')}': {res.get('verdict')}")

            if fix_res.get("patches_applied"):
                for p in fix_res["patches_applied"]:
                    print(f"  Patch: {p.get('path', '?')} → fixed")
            if fix_res.get("patches_rejected"):
                for p in fix_res["patches_rejected"]:
                    print(f"  Patch rejected: {p.get('path', '?')} — {p.get('rejection_reason', '?')}")

        except Exception as e:
            print(f"  ERROR: {e}")

    total_elapsed = time.time() - total_start
    print(f"\nTotal: {len(targets)} questions in {total_elapsed:.1f}s")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(updated_results, f, ensure_ascii=False, indent=2)
    print(f"Saved to: {args.output}")

    # Summary statistics
    stats = {
        "fix_attempted": 0, "fix_applied": 0, "fix_rejected": 0,
        "recheck_passed": 0, "recheck_failed": 0, "auto_fix_partial": 0,
        "needs_human_judgment": 0, "needs_link_fix": 0,
        "candidate": 0, "rejected": 0,
    }
    for r in updated_results:
        if "error" in r:
            continue
        rev = r.get("review", {})
        fr = rev.get("final_readiness", {})
        fix = rev.get("fix_result")
        status = fr.get("status", "unknown")
        stats[status] = stats.get(status, 0) + 1
        if fix:
            stats["fix_attempted"] += 1
            stats["fix_applied"] += fix.get("fix_count", 0)
            stats["fix_rejected"] += len(fix.get("patches_rejected", []))
        if status == "auto_fixed_recheck_passed":
            stats["recheck_passed"] += 1
        elif status == "auto_fixed_recheck_failed":
            stats["recheck_failed"] += 1
        elif status == "auto_fix_partial":
            stats["auto_fix_partial"] += 1

    print("\n=== Summary ===")
    for k, v in stats.items():
        if v > 0:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
