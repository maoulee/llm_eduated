"""Knowledge injection test: generate questions for wrong MCQs.

For each wrong MCQ, we:
1. Use its extraction (knowledge_units, trigger_rules, reasoning_pattern) as knowledge base
2. Create a profile based on the wrong answer diagnosis
3. Generate a similar question via GenerationPipeline
4. Solve the generated question independently to check correctness
5. Compare: does knowledge injection help the model answer correctly?
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
from core_new.generation_team import GenerationPipeline

DATA_PATH = os.environ.get("SEED_QUESTIONS_FILE", "/home/dev/full_question.json")
RESULTS_PATH = "docs/batch_200_results_v2.json"
EXTRACTIONS_PATH = "docs/wrong_mcq_extractions.json"
DST = "docs/knowledge_injection_results.json"


async def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        questions = json.load(f)
    with open(RESULTS_PATH, encoding="utf-8") as f:
        results = json.load(f)

    # Load extractions (from extract_wrong_mcqs.py)
    try:
        with open(EXTRACTIONS_PATH, encoding="utf-8") as f:
            extractions = json.load(f)
        print(f"Loaded {len(extractions)} extractions from {EXTRACTIONS_PATH}")
    except FileNotFoundError:
        print(f"ERROR: {EXTRACTIONS_PATH} not found. Run extract_wrong_mcqs.py first.")
        return

    # Build extraction lookup by _index
    ext_by_idx = {}
    for e in extractions:
        idx = e.get("_index")
        if idx is not None:
            ext_by_idx[idx] = e

    # Find wrong MCQs
    wrong_mcqs = [
        r for r in results
        if r.get("question_type") == "单选题"
        and not r.get("final", {}).get("correct", False)
    ]
    print(f"Found {len(wrong_mcqs)} wrong MCQs")

    # Filter to only those with successful extractions
    testable = []
    for r in wrong_mcqs:
        idx = r["_index"]
        ext = ext_by_idx.get(idx)
        if ext and "error" not in ext:
            testable.append((r, ext))
        else:
            err = ext.get("error", "no extraction") if ext else "no extraction"
            print(f"  Skipping [{idx}]: {err}")
    print(f"Testable: {len(testable)} (with successful extractions)\n")

    if not testable:
        print("No testable questions. Exiting.")
        return

    # Initialize GLM 5.1
    config = get_provider_config("glm5.1")
    provider = get_llm_provider(config)
    pipeline = GenerationPipeline(provider, max_tokens=4096)
    print("GLM 5.1 generation pipeline ready\n")

    injection_results = []
    for i, (r, ext) in enumerate(testable):
        idx = r["_index"]
        gt = r.get("gt_key", "?")
        wrong_ans = r.get("final", {}).get("answer", "?")
        q = questions[idx]
        preview = q.get("prompt", "")[:80]

        print(f"{'='*60}")
        print(f"Test {i+1}/{len(testable)}: [{idx}] gt={gt} wrong={wrong_ans}")
        print(f"  {preview}...")
        print(f"{'='*60}")

        # Build profile from extraction's knowledge + wrong answer diagnosis
        ku = ext.get("knowledge_units", {})
        tr = ext.get("trigger_rules", {})
        rp = ext.get("reasoning_pattern", {})

        # Extract key concepts for error history
        weak_concepts = []
        for k in ku.get("knowledge_units", []):
            name = k.get("name", "")
            if name:
                weak_concepts.append(name)
        concept_str = "、".join(weak_concepts[:3]) if weak_concepts else "相关知识点"

        # Build the error history from the actual wrong answer
        import re
        m = re.search(r'\[(\d+年考研真题第\d+题)', q.get("prompt", ""))
        exam_info = m.group(1) if m else f"题{idx}"

        profile_info = {
            "name": f"wrong_mcq_{idx}",
            "error_history": f"{exam_info}做错，正确答案是{gt}但选择了{wrong_ans}，涉及知识点：{concept_str}",
            "mastery_info": f"已掌握：基本概念；薄弱：{concept_str}",
            "training_goal": f"针对{exam_info}的知识薄弱点，生成类似题目强化理解",
        }

        # Knowledge base: use the extraction as knowledge base
        knowledge_base = [ext]

        t0 = time.time()
        try:
            result = await pipeline.generate(profile_info, knowledge_base)
            dt = time.time() - t0

            result["_index"] = idx
            result["_gt"] = gt
            result["_wrong_answer"] = wrong_ans
            result["generation_time"] = dt

            # Print results
            agg = result.get("aggregation", {})
            status = agg.get("decision", agg.get("status", "unknown"))
            print(f"  Status: {status}, Time: {dt:.1f}s")

            q_gen = result.get("question", {})
            if q_gen and q_gen.get("stem"):
                print(f"\n  生成题干: {q_gen['stem'][:150]}")
                for opt in ["A", "B", "C", "D"]:
                    key = f"option_{opt}"
                    opts = q_gen.get("options", {})
                    if opts and opt in opts:
                        print(f"  {opt}: {opts[opt][:80]}")
                    elif key in q_gen:
                        print(f"  {opt}: {q_gen[key][:80]}")
                print(f"  生成答案: {q_gen.get('answer', 'N/A')}")

            solver = result.get("solver_results", [])
            if solver:
                s = solver[0] if isinstance(solver, list) else solver
                print(f"\n  求解器答案: {s.get('derived_answer', s.get('answer', 'N/A'))}")
                print(f"  求解器判定: solvable={s.get('solvable', '?')} unique={s.get('unique_answer', '?')}")

            sim = result.get("simulation_result", {})
            if sim:
                print(f"  模拟选择: {sim.get('simulated_answer', 'N/A')} matched_failure={sim.get('matched_expected_failure', '?')}")

            injection_results.append(result)

        except Exception as e:
            dt = time.time() - t0
            print(f"  ERROR ({dt:.1f}s): {e}")
            import traceback
            traceback.print_exc()
            injection_results.append({
                "_index": idx, "_gt": gt, "_wrong_answer": wrong_ans,
                "error": str(e), "generation_time": dt,
            })

    # Save
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(injection_results, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\n{'='*60}")
    print("KNOWLEDGE INJECTION SUMMARY")
    print(f"{'='*60}")
    ok = sum(1 for r in injection_results if "error" not in r)
    err = sum(1 for r in injection_results if "error" in r)
    accepted = sum(1 for r in injection_results
                   if "error" not in r and r.get("aggregation", {}).get("status") == "accept_candidate")

    print(f"  Total: {len(injection_results)}, Success: {ok}, Failed: {err}")
    print(f"  Accepted: {accepted}/{ok}")

    for r in injection_results:
        idx = r.get("_index", "?")
        gt = r.get("_gt", "?")
        wrong = r.get("_wrong_answer", "?")
        if "error" in r:
            print(f"  [{idx}] gt={gt} wrong={wrong} → FAILED: {r['error'][:60]}")
        else:
            agg = r.get("aggregation", {})
            status = agg.get("decision", agg.get("status", "?"))
            q = r.get("question", {})
            gen_ans = q.get("answer", "?")
            dt = r.get("generation_time", 0)
            print(f"  [{idx}] gt={gt} wrong={wrong} → {status} gen_ans={gen_ans} ({dt:.0f}s)")

    print(f"\nSaved to {DST}")


if __name__ == "__main__":
    asyncio.run(main())
