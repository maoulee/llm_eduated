"""Test question generation with GLM 5.1.

Uses existing extraction data as knowledge base for the generation pipeline.
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


TEST_PROFILES = [
    {
        "name": "cache_mapping_confusion",
        "error_history": "Cache组相联映射题连续做错2次，混淆直接映射和组相联映射的地址划分方式",
        "mastery_info": "Cache命中率计算：已掌握；Cache替换策略：已掌握；Cache地址映射：薄弱",
        "training_goal": "强化Cache地址映射的理解，区分直接映射、全相联映射和组相联映射",
    },
    {
        "name": "float_ieee754",
        "error_history": "IEEE754浮点数表示题做错3次，阶码偏移量计算错误，混淆单精度和双精度格式",
        "mastery_info": "定点数表示：已掌握；浮点数规格化：部分掌握；IEEE754编码：薄弱",
        "training_goal": "掌握IEEE754单精度浮点数的编码过程",
    },
    {
        "name": "pipeline_hazard",
        "error_history": "流水线数据冒险分析题连续做错，无法正确识别RAW/WAR/WAW冒险和插入气泡的位置",
        "mastery_info": "流水线基本原理：已掌握；流水线性能计算：已掌握；冒险检测与处理：薄弱",
        "training_goal": "强化流水线数据冒险的识别和forwarding策略",
    },
]


async def main():
    # Load extraction data as knowledge base
    extraction_file = "docs/extraction_deep_v4.json"
    with open(extraction_file, encoding="utf-8") as f:
        knowledge_base = json.load(f)
    print(f"Loaded {len(knowledge_base)} extractions from {extraction_file}")

    # Initialize GLM 5.1
    print("Initializing GLM 5.1 provider...")
    config = get_provider_config("glm5.1")
    provider = get_llm_provider(config)
    pipeline = GenerationPipeline(provider, max_tokens=4096)
    print("GLM 5.1 ready\n")

    results = []
    for i, profile in enumerate(TEST_PROFILES):
        print(f"{'='*60}")
        print(f"Test {i+1}/{len(TEST_PROFILES)}: {profile['name']}")
        print(f"{'='*60}")

        profile_info = {
            "name": profile["name"],
            "error_history": profile["error_history"],
            "mastery_info": profile["mastery_info"],
            "training_goal": profile["training_goal"],
        }

        t0 = time.time()
        try:
            result = await pipeline.generate(profile_info, knowledge_base)
            dt = time.time() - t0
            result["profile_name"] = profile["name"]
            result["generation_time"] = dt

            # Print results
            agg = result.get("aggregation", {})
            status = agg.get("decision", agg.get("status", "unknown"))
            print(f"  Status: {status}, Time: {dt:.1f}s")

            q = result.get("question", {})
            if q and q.get("stem"):
                print(f"\n  题干: {q['stem']}")
                for opt in ["A", "B", "C", "D"]:
                    key = f"option_{opt}"
                    if key in q:
                        print(f"  {key}: {q[key]}")
                print(f"  答案: {q.get('answer', 'N/A')}")
                sol = q.get("solution", "")
                if sol:
                    print(f"  解析: {sol[:200]}...")

            solver = result.get("solver_results", [])
            if solver:
                s = solver[0] if isinstance(solver, list) else solver
                print(f"\n  求解器答案: {s.get('answer', 'N/A')}")

            sim = result.get("simulation_result", {})
            if sim:
                print(f"  用户模拟选择: {sim.get('chosen_option', 'N/A')}")

            results.append(result)

        except Exception as e:
            dt = time.time() - t0
            print(f"  ERROR ({dt:.1f}s): {e}")
            import traceback
            traceback.print_exc()
            results.append({"profile_name": profile["name"], "error": str(e)})

    # Save
    with open("docs/glm_generation_test.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\n{'='*60}")
    print("QUALITY SUMMARY")
    print(f"{'='*60}")
    for r in results:
        name = r.get("profile_name", "?")
        if "error" in r:
            print(f"  {name}: FAILED - {r['error'][:80]}")
            continue

        q = r.get("question", {})
        agg = r.get("aggregation", {})
        status = agg.get("decision", agg.get("status", "?"))
        dt = r.get("generation_time", 0)

        has_stem = bool(q.get("stem"))
        has_all_opts = all(q.get(f"option_{o}") for o in "ABCD")
        has_answer = bool(q.get("answer"))
        has_solution = bool(q.get("solution"))

        print(f"  {name}: {status} ({dt:.0f}s)")
        print(f"    完整性: stem={'Y' if has_stem else 'N'} opts={'Y' if has_all_opts else 'N'} answer={'Y' if has_answer else 'N'} sol={'Y' if has_solution else 'N'}")
        reason = agg.get("reason", agg.get("reasons", [""])[0] if agg.get("reasons") else "")
        print(f"    原因: {str(reason)[:100]}")

    print(f"\nSaved to docs/glm_generation_test.json")


if __name__ == "__main__":
    asyncio.run(main())
