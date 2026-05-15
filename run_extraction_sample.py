"""Run extraction pipeline on a diverse sample of questions for PR review."""

import asyncio
import json
import os
import sys
import time

# Ensure env vars are loaded before config import
from dotenv import load_dotenv
load_dotenv()

from core_new.llm_gateway import get_gateway
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


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run extraction sample")
    parser.add_argument("--provider", default=os.environ.get("EXTRACTION_PROVIDER", "glm5.1"))
    args = parser.parse_args()

    provider_name = args.provider
    print(f"Initializing gateway: {provider_name}")
    gateway = get_gateway(provider_name)
    review_mode = os.environ.get("REVIEW_MODE", "fast")
    pipeline = ExtractionPipeline(gateway, max_tokens=6144, enable_thinking=True, review_mode=review_mode, review_max_tokens=10000)
    print(f"Review mode: {review_mode}")

    results = []
    total_start = time.time()

    for i, q in enumerate(QUESTIONS):
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(QUESTIONS)}] Question: {q['id']} — {q['prompt'][:50]}...")
        start = time.time()
        result = await pipeline.extract(q)
        elapsed = time.time() - start
        print(f"  Completed in {elapsed:.1f}s")

        if "error" in result:
            print(f"  ERROR: {result['error']}")
        else:
            # Quick quality summary
            ks = result.get("knowledge_units", {})
            n_knowledge = len(ks.get("knowledge_units", []))
            n_mechanisms = len(ks.get("mechanisms", []))
            tr = result.get("trigger_rules", {})
            n_triggers = len(tr.get("trigger_rules", []))
            rp = result.get("reasoning_pattern", {})
            n_steps = len(rp.get("steps", []))
            review = result.get("review", {})
            readiness = review.get("readiness", {})
            db_status = readiness.get("status", "N/A")
            rule_valid = review.get("rule_validation", {}).get("schema_valid", "N/A")
            ac_consistent = review.get("rule_validation", {}).get("answer_consistency", {}).get("consistent", "N/A")
            domain_major = len(review.get("domain_review", {}).get("domain_review", {}).get("major_issues", []))
            domain_minor = len(review.get("domain_review", {}).get("domain_review", {}).get("minor_issues", []))
            print(f"  knowledge={n_knowledge}, mechanisms={n_mechanisms}, triggers={n_triggers}, steps={n_steps}")
            print(f"  review: schema={rule_valid}, answer_consistent={ac_consistent}, domain_issues={domain_major}M/{domain_minor}m, status={db_status}")

        results.append(result)

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"Total: {len(results)} questions in {total_elapsed:.1f}s ({total_elapsed/len(results):.1f}s/question avg)")

    output_path = os.path.join(os.path.dirname(__file__), "docs", "extraction_sample_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
