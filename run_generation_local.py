#!/usr/bin/env python3
"""
Test the generation team pipeline with local vLLM (Qwen3.6-27B).

Original design uses GLM5.1, this script tests whether the local model
can drive the 6-agent pipeline:
  ProfileInterpreter → BlueprintPlanner → QuestionWriter
  → SolverVerifier → UserSimulator → GenerationAggregator
"""

import asyncio
import json
import os
import time

from dotenv import load_dotenv
load_dotenv()

from config import get_provider_config
from llm_providers_new import get_llm_provider
from core_new.generation_team import GenerationPipeline


PROFILES = [
    {
        "name": "dram_mechanism_gap",
        "error_history": "DRAM地址引脚数计算题连续做错3次，直接把完整地址位数当引脚数",
        "mastery_info": "掌握：主存编址、地址位数计算。薄弱：DRAM行列地址复用机制",
        "training_goal": "诊断并强化DRAM地址引脚数计算中行列地址复用的理解",
    },
    {
        "name": "cache_pattern_gap",
        "error_history": "Cache映射题容易混淆直接映射和组相联映射的计算公式",
        "mastery_info": "掌握：Cache基本概念、命中率的计算。薄弱：不同映射方式的地址划分和组号计算",
        "training_goal": "强化组相联映射中Cache组号计算的推理模式",
    },
    {
        "name": "unsigned_int_wrong_route",
        "error_history": "C语言混合类型运算题中，忽略int与unsigned的隐式类型转换，直接按有符号数计算",
        "mastery_info": "掌握：基本数据类型表示范围、补码运算。薄弱：混合类型运算中的隐式类型提升机制",
        "training_goal": "诊断int/unsigned混合运算中隐式类型转换的理解",
    },
]


def load_knowledge_base():
    """Load extraction results as knowledge base."""
    # Try deep v4 first (more complete), fall back to sample results
    for path in [
        os.path.join(os.path.dirname(__file__), "docs", "extraction_deep_v4.json"),
        os.path.join(os.path.dirname(__file__), "docs", "extraction_sample_results.json"),
    ]:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            print(f"Loaded {len(data)} extraction results from {os.path.basename(path)}")
            return data

    print("Warning: No knowledge base found")
    return []


def prepare_knowledge_for_profile(profile_name: str, knowledge_base: list) -> list:
    """Select relevant knowledge entries for each profile."""
    profile_mapping = {
        "dram_mechanism_gap": ["DRAM", "主存", "地址", "引脚"],
        "cache_pattern_gap": ["Cache", "映射", "组相联", "直接映射"],
        "unsigned_int_wrong_route": ["unsigned", "类型转换", "int", "混合运算"],
    }

    keywords = profile_mapping.get(profile_name, [])
    relevant = []

    for extraction in knowledge_base:
        structure = extraction.get("question_structure", {})
        subject = structure.get("subject", "")
        stem = structure.get("stem", "")

        if any(kw in subject or kw in stem for kw in keywords):
            relevant.append(extraction)

    return relevant[:3] if relevant else knowledge_base[:3]


async def main():
    print("=" * 60)
    print("Question Generation Team — Local vLLM Test")
    print("=" * 60)

    # Use local vLLM instead of GLM5.1
    config = get_provider_config("api_vllm")
    served_model = os.environ.get("VLLM_SERVED_MODEL")
    if served_model:
        config["model_path"] = served_model
    provider = get_llm_provider(config)
    print(f"Provider: {config.get('model_path', 'api_vllm')}")

    # Load knowledge base
    knowledge_base = load_knowledge_base()

    pipeline = GenerationPipeline(provider, max_tokens=4096)

    results = []
    total_start = time.time()

    for i, profile in enumerate(PROFILES, 1):
        profile_name = profile.get("name", "unknown")
        print(f"\n{'=' * 60}")
        print(f"Profile {i}/{len(PROFILES)}: {profile_name}")
        print(f"{'=' * 60}")

        relevant_kb = prepare_knowledge_for_profile(profile_name, knowledge_base)
        print(f"Using {len(relevant_kb)} relevant knowledge base entries")

        start = time.time()
        try:
            result = await pipeline.generate(profile, relevant_kb)
            elapsed = time.time() - start
            results.append(result)

            aggregation = result.get("aggregation", {})
            status = aggregation.get("status", "unknown")
            reasons = aggregation.get("reasons", [])

            print(f"\n  Time: {elapsed:.1f}s")
            print(f"  Status: {status}")
            if reasons:
                print("  Reasons:")
                for reason in reasons:
                    print(f"    - {reason}")

            if "question" in result:
                q = result["question"]
                print(f"\n  Generated Question:")
                print(f"    Subject: {result.get('blueprint', {}).get('subject', 'N/A')}")
                print(f"    Difficulty: {q.get('difficulty_self_assessment', 'N/A')}")
                print(f"    Answer: {q.get('answer', 'N/A')}")
                stem_preview = q.get("stem", "")[:100].replace("\n", " ")
                print(f"    Stem: {stem_preview}...")

            # Show revision rounds if any
            for round_num in range(1, 3):
                rev = result.get(f"revision_round_{round_num}")
                if rev:
                    print(f"\n  Revision Round {round_num}: {rev['aggregation'].get('status', '?')}")

        except Exception as e:
            elapsed = time.time() - start
            print(f"\n  ERROR after {elapsed:.1f}s: {e}")
            import traceback
            traceback.print_exc()
            results.append({"profile_name": profile_name, "error": str(e), "elapsed": elapsed})

    total_elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"Total: {len(PROFILES)} profiles in {total_elapsed:.1f}s")
    print(f"Successful: {sum(1 for r in results if 'question' in r)}")
    print(f"Failed: {sum(1 for r in results if 'error' in r)}")

    # Save
    output_path = os.path.join(os.path.dirname(__file__), "docs", "generation_local_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
