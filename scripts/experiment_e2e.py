"""端到端测试：三种题型统一跑，统计时间。

题型：
  T1 选择题（standard, single_choice）
  T3 计算综合（standard, comprehensive, AVL）
  TC 概念题（conceptual, single_choice）
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

COMP_ASSEMBLED = "docs/compose/Q41_assembled.md"
CONCEPT_ASSEMBLED = "docs/compose/Q45_assembled.md"

SLOTS = [
    ("T1_选择题", "E2E_SC", {
        "slot_id": "E2E_SC", "subject": "数据结构",
        "knowledge_tag": "DS-5 > 树与二叉树 > 二叉树带权路径长度(WPL)",
        "primary_target_name": "二叉树带权路径长度", "difficulty": "medium",
        "question_type": "single_choice", "complexity": "standard",
    }, "single_choice", ""),
    ("T3_计算综合", "E2E_C3", {
        "slot_id": "E2E_C3", "subject": "数据结构",
        "knowledge_tag": "DS-5 > 树与二叉树 > 平衡二叉树AVL",
        "primary_target_name": "平衡二叉树AVL插入旋转", "difficulty": "hard",
        "question_type": "comprehensive", "complexity": "standard",
    }, "comprehensive",
     Path(COMP_ASSEMBLED).read_text(encoding="utf-8") if Path(COMP_ASSEMBLED).exists() else ""),
    ("TC_概念题", "E2E_CONCEPT", {
        "slot_id": "E2E_CONCEPT", "subject": "操作系统",
        "knowledge_tag": "OS-2 > 进程与线程 > 死锁 > 死锁概念",
        "primary_target_name": "死锁的概念与产生条件", "difficulty": "easy",
        "question_type": "single_choice", "complexity": "conceptual",
    }, "single_choice",
     Path(CONCEPT_ASSEMBLED).read_text(encoding="utf-8") if Path(CONCEPT_ASSEMBLED).exists() else ""),
]


async def run_one(dp_factory, label, slot_id, slot_data, qtype, assembled):
    print(f"\n{'='*70}\n  [{label}] complexity={slot_data['complexity']} | {qtype}\n{'='*70}")
    t0 = time.time()
    try:
        result = await dp_factory().run(
            slot_id=slot_id, slot_data=slot_data,
            assembled_experience_doc=assembled, question_type=qtype,
        )
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"  ✗ crash: {e}")
        return {"label": label, "ok": False, "time": time.time()-t0, "branch": slot_data["complexity"]}
    elapsed = time.time() - t0
    print(f"  {elapsed:.1f}s | ok={result.ok} | review={result.review_status}")
    return {"label": label, "ok": result.ok, "time": elapsed,
            "branch": slot_data["complexity"], "review": result.review_status}


async def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="glm5.1", choices=["glm5.1", "api_vllm"])
    args = ap.parse_args()
    if args.provider == "api_vllm":
        os.environ.setdefault("VLLM_MODEL", "/zhaoshu/llm/Qwen3.6-27B-FP8")
        os.environ.setdefault("VLLM_API_BASE", "http://127.0.0.1:8000/v1")

    from core_new.doc_pipeline import DocPipeline
    from core_new.llm_gateway import get_gateway
    gw = get_gateway(args.provider)

    out = Path(f"docs/test_output/e2e_{args.provider}")
    out.mkdir(parents=True, exist_ok=True)

    print(f"端到端测试 | provider={args.provider} | 3 题型（选择+计算综合+概念）")
    results = []
    for label, sid, sd, qt, asm in SLOTS:
        r = await run_one(
            lambda: DocPipeline(gateway=gw, workspace=str(out),
                model_routing={"_default": args.provider}, enable_thinking=True),
            label, sid, sd, qt, asm,
        )
        results.append(r)

    print(f"\n{'='*70}\n  端到端结果（provider={args.provider}）\n{'='*70}")
    print(f"  {'题型':14s} {'分支':12s} {'时间':>7s} {'ok':>5s} {'review':>8s}")
    total_time = 0
    for r in results:
        total_time += r["time"]
        print(f"  {r['label']:14s} {r['branch']:12s} {r['time']:6.1f}s {str(r['ok']):>5s} {r.get('review','?'):>8s}")
    print(f"  {'总计':14s} {'':12s} {total_time:6.1f}s")
    all_ok = all(r["ok"] for r in results)
    print(f"\n  → {'✓ 三题型全部成功' if all_ok else '✗ 有失败'}")


if __name__ == "__main__":
    asyncio.run(main())
