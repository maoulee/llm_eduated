"""Test local Qwen3.6 extraction quality against GLM-5.1 sample results.

Runs the same 6 sample questions through local vLLM provider and compares
output quality with the existing GLM-5.1 results in docs/extraction_sample_results.json.

Usage:
    # 1. Start vLLM server:
    python -m vllm.entrypoints.openai.api_server \
        --model /root/shared-nvme/llm_edu/models/Qwen3.6-27B-AWQ-INT4 \
        --port 8000 --tensor-parallel-size 2 --gpu-memory-utilization 0.85 \
        --max-model-len 8192

    # 2. Run comparison:
    python run_local_extraction_test.py
    python run_local_extraction_test.py --provider glm5.1  # use online model
"""

import argparse
import asyncio
import json
import os
import time

from dotenv import load_dotenv
load_dotenv()

from config import get_provider_config
from llm_providers_new import get_llm_provider
from core_new.extraction_pipeline import ExtractionPipeline


QUESTIONS = [
    {
        "id": "2009-12",
        "type": "单选题",
        "prompt": "[2009年考研真题第12题]一个C语言程序在一台32位机器上运行。程序中定义了三个变量x、y和z，其中x和z为int型，y为unsigned型。若x=127，y=127，z=x-y，则z的值为（ ）。\nA. 0  B. -254  C. 127  D. 溢出",
        "answer": "A",
    },
    {
        "id": "2009-14",
        "type": "单选题",
        "prompt": "[2009年考研真题第14题]某计算机的Cache共有16块，采用2路组相联映射方式（即每组2块）。每个主存块大小为32字节，按字节编址。主存第129号单元所在的主存块应装入的Cache组号是（ ）。\nA. 0  B. 2  C. 4  D. 6",
        "answer": "C",
    },
    {
        "id": "2010-33",
        "type": "单选题",
        "prompt": "[2010年考研真题第33题]下列选项中，不属于网络体系结构中所描述的内容是（ ）。\nA. 每一层的功能  B. 层与层之间的接口  C. 协议的实现细节  D. 每一层使用的协议",
        "answer": "C",
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

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "docs", "extraction_sample_results.json")


def load_golden_results() -> dict:
    if not os.path.exists(GOLDEN_PATH):
        return {}
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {r["question_id"]: r for r in data if "question_id" in r and "error" not in r}


def compare_results(local: dict, golden: dict) -> dict:
    """Compare local result with golden GLM-5.1 result."""
    qid = local.get("question_id", "?")
    if "error" in local:
        return {"question_id": qid, "status": "ERROR", "error": local["error"]}

    metrics = {"question_id": qid}

    # Knowledge units count
    local_ku = len(local.get("knowledge_units", {}).get("knowledge_units", []))
    golden_ku = len(golden.get("knowledge_units", {}).get("knowledge_units", []))
    metrics["knowledge_units"] = {"local": local_ku, "golden": golden_ku}

    # Mechanisms count
    local_mech = len(local.get("knowledge_units", {}).get("mechanisms", []))
    golden_mech = len(golden.get("knowledge_units", {}).get("mechanisms", []))
    metrics["mechanisms"] = {"local": local_mech, "golden": golden_mech}

    # Trigger rules count
    local_tr = len(local.get("trigger_rules", {}).get("trigger_rules", []))
    golden_tr = len(golden.get("trigger_rules", {}).get("trigger_rules", []))
    metrics["trigger_rules"] = {"local": local_tr, "golden": golden_tr}

    # Reasoning steps count
    local_steps = len(local.get("reasoning_pattern", {}).get("steps", []))
    golden_steps = len(golden.get("reasoning_pattern", {}).get("steps", []))
    metrics["reasoning_steps"] = {"local": local_steps, "golden": golden_steps}

    # Review status
    local_status = local.get("review", {}).get("readiness", {}).get("status", "N/A")
    golden_status = golden.get("review", {}).get("readiness", {}).get("status", "N/A")
    metrics["review_status"] = {"local": local_status, "golden": golden_status}

    # Orphan references
    local_orphans = len(local.get("review", {}).get("rule_validation", {}).get("link_validation", {}).get("orphan_targets", []))
    golden_orphans = len(golden.get("review", {}).get("rule_validation", {}).get("link_validation", {}).get("orphan_targets", []))
    metrics["orphans"] = {"local": local_orphans, "golden": golden_orphans}

    # Schema valid
    local_schema = local.get("review", {}).get("rule_validation", {}).get("schema_valid", None)
    golden_schema = golden.get("review", {}).get("rule_validation", {}).get("schema_valid", None)
    metrics["schema_valid"] = {"local": local_schema, "golden": golden_schema}

    metrics["status"] = "OK"
    return metrics


async def run_test(args):
    golden = load_golden_results()
    print(f"Loaded {len(golden)} golden results from {GOLDEN_PATH}")

    provider_name = args.provider
    print(f"Initializing provider: {provider_name}")
    config = get_provider_config(provider_name)
    if args.model_path:
        config["model_path"] = args.model_path
    provider = get_llm_provider(config)

    review_mode = os.environ.get("REVIEW_MODE", "fast")
    pipeline = ExtractionPipeline(
        provider, max_tokens=args.max_tokens,
        enable_thinking=False, review_mode=review_mode,
    )

    results = []
    comparisons = []
    total_start = time.time()

    for i, q in enumerate(QUESTIONS):
        qid = q["id"]
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(QUESTIONS)}] {qid} — {q['prompt'][:50]}...")
        start = time.time()
        result = await pipeline.extract(q)
        elapsed = time.time() - start
        print(f"  Completed in {elapsed:.1f}s")

        if "error" in result:
            print(f"  ERROR: {result['error']}")
        else:
            ks = result.get("knowledge_units", {})
            n_ku = len(ks.get("knowledge_units", []))
            n_mech = len(ks.get("mechanisms", []))
            tr = result.get("trigger_rules", {})
            n_tr = len(tr.get("trigger_rules", []))
            rp = result.get("reasoning_pattern", {})
            n_steps = len(rp.get("steps", []))
            review = result.get("review", {})
            status = review.get("readiness", {}).get("status", "N/A")
            print(f"  ku={n_ku}, mech={n_mech}, trig={n_tr}, steps={n_steps}, status={status}")

        results.append(result)

        # Compare with golden
        if qid in golden:
            cmp = compare_results(result, golden[qid])
            comparisons.append(cmp)
            if cmp["status"] == "OK":
                ku_cmp = cmp["knowledge_units"]
                mech_cmp = cmp["mechanisms"]
                tr_cmp = cmp["trigger_rules"]
                steps_cmp = cmp["reasoning_steps"]
                print(f"  vs GLM: ku {ku_cmp['local']}vs{ku_cmp['golden']}, "
                      f"mech {mech_cmp['local']}vs{mech_cmp['golden']}, "
                      f"trig {tr_cmp['local']}vs{tr_cmp['golden']}, "
                      f"steps {steps_cmp['local']}vs{steps_cmp['golden']}")
        else:
            print(f"  No golden result to compare")

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"Total: {len(results)} questions in {total_elapsed:.1f}s ({total_elapsed/len(results):.1f}s/q avg)")

    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "docs", f"extraction_sample_{provider_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Results saved to: {output_path}")

    # Summary comparison table
    if comparisons:
        print(f"\n{'='*60}")
        print(f"COMPARISON: {provider_name} vs GLM-5.1 (golden)")
        print(f"{'='*60}")
        print(f"{'QID':<15} {'KU':>8} {'MECH':>8} {'TRIG':>8} {'STEPS':>8} {'ORPHANS':>10} {'STATUS':>20}")
        print(f"{'':15} {'L vs G':>8} {'L vs G':>8} {'L vs G':>8} {'L vs G':>8} {'L vs G':>10} {'L vs G':>20}")
        print("-" * 85)
        for c in comparisons:
            if c["status"] != "OK":
                print(f"{c['question_id']:<15} ERROR: {c.get('error', '')}")
                continue
            ku = c["knowledge_units"]
            mech = c["mechanisms"]
            tr = c["trigger_rules"]
            steps = c["reasoning_steps"]
            orph = c["orphans"]
            st = c["review_status"]
            print(f"{c['question_id']:<15} "
                  f"{ku['local']:>3}vs{ku['golden']:<3} "
                  f"{mech['local']:>3}vs{mech['golden']:<3} "
                  f"{tr['local']:>3}vs{tr['golden']:<3} "
                  f"{steps['local']:>3}vs{steps['golden']:<3} "
                  f"{orph['local']:>4}vs{orph['golden']:<4} "
                  f"{st['local']:>8}vs{st['golden']:<8}")

        # Aggregate
        all_ok = [c for c in comparisons if c["status"] == "OK"]
        if all_ok:
            avg_ku_diff = sum(c["knowledge_units"]["local"] - c["knowledge_units"]["golden"] for c in all_ok) / len(all_ok)
            avg_mech_diff = sum(c["mechanisms"]["local"] - c["mechanisms"]["golden"] for c in all_ok) / len(all_ok)
            avg_orphan_diff = sum(c["orphans"]["local"] - c["orphans"]["golden"] for c in all_ok) / len(all_ok)
            schema_match = sum(1 for c in all_ok if c["schema_valid"]["local"] == c["schema_valid"]["golden"]) / len(all_ok) * 100
            print(f"\nAvg KU diff: {avg_ku_diff:+.1f}, Avg mech diff: {avg_mech_diff:+.1f}, "
                  f"Avg orphan diff: {avg_orphan_diff:+.1f}, Schema match: {schema_match:.0f}%")

    # Save comparison report
    report_path = os.path.join(os.path.dirname(__file__), "docs", f"extraction_comparison_{provider_name}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"provider": provider_name, "comparisons": comparisons}, f, ensure_ascii=False, indent=2)
    print(f"Comparison report saved to: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Test local model extraction vs GLM-5.1 golden results")
    parser.add_argument("--provider", default="api_vllm", help="Provider to test (default: api_vllm)")
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max tokens per pass")
    parser.add_argument("--model-path", default=None, help="Override model_path in provider config")
    args = parser.parse_args()
    asyncio.run(run_test(args))


if __name__ == "__main__":
    main()
