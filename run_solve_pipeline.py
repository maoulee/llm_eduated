"""Run solve pipeline integrating all components: experience retrieval, dual-path solving, consistency checking, and GLM arbitration."""

import asyncio
import json
import os
import sys
import time
from typing import Dict, Any, List

from dotenv import load_dotenv
load_dotenv()

from config import get_provider_config
from llm_providers_new import get_llm_provider
from core_new.experience_retriever import ExperienceRetriever
from core_new.dual_path_solver import DualPathSolver
from core_new.consistency_checker import ConsistencyChecker
from core_new.glm_arbiter import GLMArbiter


# Test questions from run_extraction_sample.py
QUESTIONS = [
    {
        "id": "2009-12",
        "type": "单选题",
        "prompt": "[2009年考研真题第12题]一个C语言程序在一台32位机器上运行。程序中定义了三个变量x、y和z，其中x和z为int型，y为unsigned型。若x=127，y=127，z=x-y，则z的值为（ ）。\nA. 0  B. -254  C. 127  D. 溢出",
        "answer": "A",
        "options": {"A": "0", "B": "-254", "C": "127", "D": "溢出"},
    },
    {
        "id": "2009-14",
        "type": "单选题",
        "prompt": "[2009年考研真题第14题]某计算机的Cache共有16块，采用2路组相联映射方式（即每组2块）。每个主存块大小为32字节，按字节编址。主存第129号单元所在的主存块应装入的Cache组号是（ ）。\nA. 0  B. 2  C. 4  D. 6",
        "answer": "C",
        "options": {"A": "0", "B": "2", "C": "4", "D": "6"},
    },
    {
        "id": "2010-33",
        "type": "单选题",
        "prompt": "[2010年考研真题第33题]下列选项中，不属于网络体系结构中所描述的内容是（ ）。\nA. 每一层的功能  B. 层与层之间的接口  C. 协议的实现细节  D. 每一层使用的协议",
        "answer": "C",
        "options": {"A": "每一层的功能", "B": "层与层之间的接口", "C": "协议的实现细节", "D": "每一层使用的协议"},
    },
    {
        "id": "2012-02",
        "type": "单选题",
        "prompt": "[2012年考研真题第2题]已知一棵完全二叉树有700个结点，则该二叉树中有100个叶子结点。该说法是否正确？若不正确，请给出正确答案。",
        "answer": "不完全正确。700个结点的完全二叉树，叶子结点数为350个。由完全二叉树性质：n0 = (n+1)/2 向下取整 = 350。",
    },
    {
        "id": "crc-link",
        "type": "综合题",
        "prompt": "小亮在开发物联网设备时，想要为设备的网络通讯定制专用的数据链路层。其中，为确保数据传输的正确性，拟使用循环冗余校验码（CRC）进行差错检测。设待发送的数据比特串为101001，生成多项式G(x)=x³+1。请计算CRC校验码。",
        "answer": "CRC校验码为001。计算过程：数据101001后补3个0得到101001000，除以生成多项式对应的除数1001，余数为001。",
    },
    {
        "id": "complement-8bit",
        "type": "计算题",
        "prompt": "某8位计算机系统中，所有整数均采用补码表示，每个数由1位符号位和7位数值位组成（即为8位补码整数）。已知X=-75，Y=+83，用补码求X+Y的结果，并判断是否溢出。",
        "answer": "X=-75的8位补码为10110101，Y=+83的8位补码为01010011。X+Y=10110101+01010011=00001000（丢弃进位），即+8。未溢出（两个异号数相加不会溢出）。",
    },
]


def load_extraction_results(path: str) -> List[Dict[str, Any]]:
    """Load extraction results from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run solve pipeline")
    parser.add_argument("--extraction-results",
                        default=os.path.join(os.path.dirname(__file__), "docs", "extraction_deep_v4.json"),
                        help="Path to extraction results JSON file")
    parser.add_argument("--output",
                        default=os.path.join(os.path.dirname(__file__), "docs", "solve_pipeline_results.json"),
                        help="Path to output results JSON file")
    args = parser.parse_args()

    print("=" * 60)
    print("Initializing Solve Pipeline")
    print("=" * 60)

    # Init providers
    print("\n[1/4] Initializing LLM providers...")
    config = get_provider_config("api_vllm")
    served_model = os.environ.get("VLLM_SERVED_MODEL")
    if served_model:
        config["model_path"] = served_model
    local_provider = get_llm_provider(config)
    print(f"  Local provider: {config['model_path']}")

    glm_config = get_provider_config("glm5.1")
    glm_provider = get_llm_provider(glm_config)
    print(f"  GLM provider: {glm_config['model_path']}")

    # Load experience
    print("\n[2/4] Loading extraction results...")
    extraction_results = load_extraction_results(args.extraction_results)
    print(f"  Loaded {len(extraction_results)} extraction results")
    retriever = ExperienceRetriever(extraction_results)
    print(f"  Built {len(retriever.all_cards)} experience cards")

    # Init components
    print("\n[3/4] Initializing pipeline components...")
    solver = DualPathSolver(local_provider)
    print("  DualPathSolver ready")
    arbiter = GLMArbiter(glm_provider)
    print("  GLMArbiter ready")

    # Run pipeline
    print("\n[4/4] Running solve pipeline...")
    results = []
    stats = {
        "total": len(QUESTIONS),
        "matched": 0,
        "need_glm": 0,
        "errors": 0,
    }

    total_start = time.time()

    for i, question in enumerate(QUESTIONS):
        question_id = question.get("id", f"q{i}")
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(QUESTIONS)}] Question: {question_id}")
        print(f"  Prompt: {question['prompt'][:80]}...")

        try:
            # Step 1: Retrieve experience
            cards = retriever.retrieve(question["prompt"])
            experience_text = retriever.format_cards(cards)
            print(f"  Retrieved {len(cards)} experience cards")

            # Step 2: Dual path solve (parallel)
            print("  Running dual-path solve...")
            dual_result = await solver.solve(question, experience_text)
            reasoning_result = dual_result["reasoning_result"]
            code_result = dual_result["code_result"]

            reasoning_answer = reasoning_result.get("answer", "")
            code_answer = code_result.get("computed_answer", "")
            print(f"  Reasoning answer: {reasoning_answer}")
            print(f"  Code answer: {code_answer}")

            # Step 3: Check consistency
            consistency = ConsistencyChecker.check(reasoning_result, code_result)
            matched = consistency["matched"]
            need_glm = consistency["need_glm"]
            final_answer = consistency.get("final_answer", "")

            print(f"  Consistency: {'MATCH' if matched else 'NO MATCH'}")
            if matched:
                print(f"  Final answer (local): {final_answer}")

            # Step 4: If not matched, call GLM arbiter
            arbiter_result = None
            if need_glm:
                print("  Calling GLM arbiter...")
                arbiter_result = await arbiter.arbitrate(
                    question,
                    reasoning_result,
                    code_result,
                    consistency,
                    experience_text,
                )
                final_answer = arbiter_result["final_answer"]
                trusted_source = arbiter_result.get("trusted_source", "")
                print(f"  GLM final answer: {final_answer}")
                print(f"  Trusted source: {trusted_source}")
                stats["need_glm"] += 1
            else:
                stats["matched"] += 1

            # Step 5: Collect result
            result = {
                "question_id": question_id,
                "question_prompt": question["prompt"],
                "question_answer": question.get("answer", ""),
                "retrieved_experiences": [c.target for c in cards],
                "reasoning_result": {
                    "answer": reasoning_answer,
                    "confidence": reasoning_result.get("confidence", ""),
                },
                "code_result": {
                    "computed_answer": code_answer,
                    "code_applicable": code_result.get("code_applicable", False),
                    "exec_success": code_result.get("exec_success", False),
                },
                "consistency": {
                    "matched": matched,
                    "need_glm": need_glm,
                    "match_method": consistency.get("match_method", ""),
                },
                "arbiter_result": arbiter_result,
                "final_answer": final_answer,
            }
            results.append(result)

        except Exception as e:
            print(f"  ERROR: {e}")
            stats["errors"] += 1
            results.append({
                "question_id": question_id,
                "error": str(e),
            })

    total_elapsed = time.time() - total_start

    # Print summary
    print("\n" + "=" * 60)
    print("Pipeline Summary")
    print("=" * 60)
    print(f"Total questions: {stats['total']}")
    print(f"Matched locally: {stats['matched']}")
    print(f"Needed GLM arbitration: {stats['need_glm']}")
    print(f"Errors: {stats['errors']}")
    print(f"Total time: {total_elapsed:.1f}s ({total_elapsed/len(QUESTIONS):.1f}s/question avg)")

    # Save results
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
