"""
Extraction result statistics — run on any batch of extraction results.

Usage:
    python docs/extraction_result_summary.py [path_to_results.json]

If no path given, defaults to docs/extraction_sample_results.json
"""

import json
import sys
from collections import Counter
from typing import Any, Dict, List


def summarize(results: List[Dict[str, Any]]) -> None:
    total = len(results)
    errors = sum(1 for r in results if "error" in r)
    valid = total - errors

    print(f"=== Extraction Result Summary ({total} questions, {errors} errors) ===\n")

    # --- Extraction stats ---
    knowledge_counts = []
    mechanism_counts = []
    trigger_counts = []
    step_counts = []

    for r in results:
        if "error" in r:
            continue
        ku = r.get("knowledge_units", {})
        knowledge_counts.append(len(ku.get("knowledge_units", [])))
        mechanism_counts.append(len(ku.get("mechanisms", [])))

        tr = r.get("trigger_rules", {})
        trigger_counts.append(len(tr.get("trigger_rules", [])))

        rp = r.get("reasoning_pattern", {})
        step_counts.append(len(rp.get("steps", [])))

    print("--- Extraction ---")
    print(f"  Knowledge units:  min={min(knowledge_counts)}, max={max(knowledge_counts)}, avg={sum(knowledge_counts)/valid:.1f}")
    print(f"  Mechanisms:       min={min(mechanism_counts)}, max={max(mechanism_counts)}, avg={sum(mechanism_counts)/valid:.1f}")
    print(f"  Trigger rules:    min={min(trigger_counts)}, max={max(trigger_counts)}, avg={sum(trigger_counts)/valid:.1f}")
    print(f"  Reasoning steps:  min={min(step_counts)}, max={max(step_counts)}, avg={sum(step_counts)/valid:.1f}")

    # --- Review stats ---
    has_review = sum(1 for r in results if r.get("review"))
    if not has_review:
        print("\n  (No review data found)")
        return

    print(f"\n--- Review ({has_review} reviewed) ---")

    schema_valid = 0
    answer_consistent = 0
    answer_unchecked = 0
    orphan_counts = []
    mismatch_counts = []
    domain_major_counts = []
    domain_minor_counts = []
    readiness_dist = Counter()

    for r in results:
        if "error" in r:
            continue
        review = r.get("review", {})
        if not review:
            continue

        rv = review.get("rule_validation", {})
        if rv.get("schema_valid"):
            schema_valid += 1

        ac = rv.get("answer_consistency", {})
        if ac.get("checked"):
            if ac.get("consistent"):
                answer_consistent += 1
        else:
            answer_unchecked += 1

        orphan_counts.append(len(rv.get("link_validation", {}).get("orphan_targets", [])))
        mismatch_counts.append(len(rv.get("link_validation", {}).get("type_mismatches", [])))

        dr = review.get("domain_review", {}).get("domain_review", {})
        domain_major_counts.append(len(dr.get("major_issues", [])))
        domain_minor_counts.append(len(dr.get("minor_issues", [])))

        readiness = review.get("readiness", {}).get("status", "unknown")
        readiness_dist[readiness] += 1

    print(f"  Schema valid:     {schema_valid}/{valid}")
    print(f"  Answer consistent: {answer_consistent}/{valid} (unchecked: {answer_unchecked})")
    print(f"  Orphan refs:      total={sum(orphan_counts)}, avg={sum(orphan_counts)/valid:.1f}, max={max(orphan_counts)}")
    print(f"  Type mismatches:  total={sum(mismatch_counts)}, avg={sum(mismatch_counts)/valid:.1f}, max={max(mismatch_counts)}")
    print(f"  Domain major:     total={sum(domain_major_counts)}, avg={sum(domain_major_counts)/valid:.1f}")
    print(f"  Domain minor:     total={sum(domain_minor_counts)}, avg={sum(domain_minor_counts)/valid:.1f}")

    print(f"\n--- Readiness Distribution ---")
    for status, count in readiness_dist.most_common():
        print(f"  {status}: {count}/{valid} ({count/valid*100:.0f}%)")

    # --- Classification ---
    clean = 0
    link_repair = 0
    semantic_review = 0
    format_unsupported = 0

    for r in results:
        if "error" in r:
            continue
        review = r.get("review", {})
        if not review:
            continue
        rv = review.get("rule_validation", {})
        dr = review.get("domain_review", {}).get("domain_review", {})
        orphans = len(rv.get("link_validation", {}).get("orphan_targets", []))
        mismatches = len(rv.get("link_validation", {}).get("type_mismatches", []))
        major = len(dr.get("major_issues", []))
        ac = rv.get("answer_consistency", {})

        if not ac.get("checked"):
            format_unsupported += 1
        elif orphans > 0 or mismatches > 0:
            link_repair += 1
        elif major > 0:
            semantic_review += 1
        else:
            clean += 1

    print(f"\n--- Classification ---")
    print(f"  A. clean_candidate:      {clean}")
    print(f"  B. link_repair_needed:    {link_repair}")
    print(f"  C. semantic_review_needed:{semantic_review}")
    print(f"  D. format_unsupported:    {format_unsupported}")

    # --- Resolver stats ---
    has_resolver = sum(1 for r in results if r.get("orphan_resolution"))
    if has_resolver:
        total_orphans_input = 0
        total_new_knowledge = 0
        total_new_mechanism = 0
        total_map_to_existing = 0
        total_uncertain = 0
        remaining_orphans = 0

        for r in results:
            res = r.get("orphan_resolution", {})
            if not res:
                continue
            total_orphans_input += res.get("orphan_count", 0)
            for s in res.get("resolutions", []):
                v = s.get("verdict", "")
                if v == "new_knowledge":
                    total_new_knowledge += 1
                elif v == "new_mechanism":
                    total_new_mechanism += 1
                elif v == "map_to_existing":
                    total_map_to_existing += 1
                elif v == "uncertain":
                    total_uncertain += 1

            # Count remaining orphans after repair
            rv = r.get("review", {}).get("rule_validation", {})
            remaining_orphans += len(rv.get("link_validation", {}).get("orphan_targets", []))

        resolved = total_orphans_input - remaining_orphans
        rate = (resolved / total_orphans_input * 100) if total_orphans_input > 0 else 0

        print(f"\n--- Resolver Stats ({has_resolver} resolved) ---")
        print(f"  Input orphans:       {total_orphans_input}")
        print(f"  new_knowledge:       {total_new_knowledge}")
        print(f"  new_mechanism:       {total_new_mechanism}")
        print(f"  map_to_existing:     {total_map_to_existing}")
        print(f"  uncertain:           {total_uncertain}")
        print(f"  Remaining orphans:   {remaining_orphans}")
        print(f"  Resolve rate:        {rate:.0f}% ({resolved}/{total_orphans_input})")

        # Link repair stats
        has_repair = sum(1 for r in results if r.get("link_repairs"))
        if has_repair:
            total_repairs = sum(len(r.get("link_repairs", {}).get("repairs", [])) for r in results)
            print(f"\n--- Link Repair Stats ({has_repair} repaired) ---")
            print(f"  Total link repairs:  {total_repairs}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "docs/extraction_sample_results.json"
    with open(path, encoding="utf-8") as f:
        results = json.load(f)
    summarize(results)
