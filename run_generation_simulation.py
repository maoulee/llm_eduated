#!/usr/bin/env python3
"""
Test script for the question generation pipeline.

Runs the generation pipeline with 3 simulated user profiles to verify
end-to-end functionality.
"""

import asyncio
import json
import os
from datetime import datetime
from dotenv import load_dotenv

from config import get_provider_config
from llm_providers_new import get_llm_provider
from core_new.generation_team import GenerationPipeline

# Load environment variables
load_dotenv()

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
    kb_path = "/data/amax/home/E22101006/mcts_reason/docs/extraction_sample_results.json"
    if not os.path.exists(kb_path):
        print(f"Warning: Knowledge base file not found: {kb_path}")
        return []

    with open(kb_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Loaded {len(data)} extraction results as knowledge base")
    return data


def prepare_knowledge_for_profile(profile_name: str, knowledge_base: list) -> list:
    """Select relevant knowledge entries for each profile."""
    # Map profile names to relevant subjects/concepts
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

        # Check if any keyword matches
        if any(kw in subject or kw in stem for kw in keywords):
            relevant.append(extraction)

    return relevant[:3] if relevant else knowledge_base[:3]


async def main():
    """Run generation simulation for all profiles."""
    print("=" * 60)
    print("Question Generation Simulation")
    print("=" * 60)

    # Initialize provider
    provider_name = "glm5.1"
    print(f"\nInitializing provider: {provider_name}")

    config = get_provider_config(provider_name)
    provider = get_llm_provider(config)

    # Load knowledge base
    print("\nLoading knowledge base...")
    knowledge_base = load_knowledge_base()

    if not knowledge_base:
        print("Warning: Empty knowledge base, using empty list")
        knowledge_base = []

    # Initialize pipeline
    pipeline = GenerationPipeline(provider, max_tokens=4096)

    # Run generation for each profile
    results = []

    for i, profile in enumerate(PROFILES, 1):
        profile_name = profile.get("name", "unknown")
        print(f"\n{'=' * 60}")
        print(f"Profile {i}/{len(PROFILES)}: {profile_name}")
        print(f"{'=' * 60}")

        # Select relevant knowledge for this profile
        relevant_kb = prepare_knowledge_for_profile(profile_name, knowledge_base)
        print(f"Using {len(relevant_kb)} relevant knowledge base entries")

        try:
            result = await pipeline.generate(profile, relevant_kb)
            results.append(result)

            # Print summary
            aggregation = result.get("aggregation", {})
            status = aggregation.get("status", "unknown")
            reasons = aggregation.get("reasons", [])

            print(f"\nResult Status: {status}")
            if reasons:
                print("Reasons:")
                for reason in reasons:
                    print(f"  - {reason}")

            if "question" in result:
                q = result["question"]
                print(f"\nGenerated Question:")
                print(f"  Subject: {result.get('blueprint', {}).get('subject', 'N/A')}")
                print(f"  Difficulty: {q.get('difficulty_self_assessment', 'N/A')}")
                print(f"  Answer: {q.get('answer', 'N/A')}")

        except Exception as e:
            print(f"\nError during generation: {e}")
            import traceback
            traceback.print_exc()
            results.append({"profile_name": profile_name, "error": str(e)})

    # Save results
    output_path = "/data/amax/home/E22101006/mcts_reason/docs/generation_simulation_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print("Summary")
    print(f"{'=' * 60}")
    print(f"Total profiles processed: {len(PROFILES)}")
    print(f"Successful generations: {sum(1 for r in results if 'question' in r)}")
    print(f"Failed: {sum(1 for r in results if 'error' in r)}")
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
