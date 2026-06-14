"""Formal experiment: §17 split architecture end-to-end, 3 types.

enable_split_design=true (split graph: exam_form→skeleton→form_gate→solve→distractor).
Runs DocPipeline on 3 slots, measures time + output success + code-as-truth artifacts.

Validates: split architecture succeeds on all 3 (esp. comprehensive, which the
integrated one-agent failed at 25k reasoning).

Usage:
  set -a && source /zhaoshu/llm_eduated/.env && set +a && \
  python3 scripts/experiment_split_3types.py [--provider glm5.1]
"""
import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

COMP_ASSEMBLED = "docs/compose/Q41_assembled.md"
OUT = Path("docs/test_output/split_3types")

SLOTS = [
    ("T1_简单选择", "TEST_SC", {"slot_id": "TEST_SC", "subject": "数据结构",
        "knowledge_tag": "DS-5 > 树与二叉树 > 二叉树带权路径长度(WPL)",
        "primary_target_name": "二叉树带权路径长度", "difficulty": "medium",
        "question_type": "single_choice", "complexity": "standard"}, "single_choice", ""),
    ("T2_简单综合", "TEST_C2", {"slot_id": "TEST_C2", "subject": "数据结构",
        "knowledge_tag": "DS-5 > 树与二叉树 > 二叉树遍历",
        "primary_target_name": "二叉树遍历序列还原", "difficulty": "medium",
        "question_type": "comprehensive", "complexity": "standard"}, "comprehensive", ""),
    ("T3_正常综合", "TEST_C3", {"slot_id": "TEST_C3", "subject": "数据结构",
        "knowledge_tag": "DS-5 > 树与二叉树 > 平衡二叉树AVL",
        "primary_target_name": "平衡二叉树AVL插入旋转", "difficulty": "hard",
        "question_type": "comprehensive", "complexity": "standard"}, "comprehensive",
        Path(COMP_ASSEMBLED).read_text(encoding="utf-8") if Path(COMP_ASSEMBLED).exists() else ""),
]


async def run_one(dp_factory, label, slot_id, slot_data, qtype, assembled):
    out = OUT / label
    out.mkdir(parents=True, exist_ok=True)
    dp = dp_factory(out)
    print(f"\n{'='*70}\n  [{label}] {qtype}\n{'='*70}")
    t0 = time.time()
    try:
        result = await dp.run(slot_id=slot_id, slot_data=slot_data,
                              assembled_experience_doc=assembled, question_type=qtype)
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"  ✗ crash: {e}"); return {"label": label, "ok": False, "time": time.time()-t0}
    elapsed = time.time() - t0
    ws = out / slot_id
    arts = {n: (ws / n).exists() for n in ["question.md", "solve.py", "solve_output.txt", "solution.md", "final.md"]}
    so_size = (ws / "solve_output.txt").stat().st_size if arts["solve_output.txt"] else 0
    qtext = (ws / "question.md").read_text(encoding="utf-8") if arts["question.md"] else ""
    has_opts = any(f"{L}." in qtext or f"{L}．" in qtext for L in "ABCD")
    print(f"  {elapsed:.1f}s | ok={result.ok} | review={result.review_status}")
    for k, v in arts.items():
        print(f"    {'✓' if v else '✗'} {k}")
    print(f"    solve_output={so_size}B | options_in_q={has_opts}")
    return {"label": label, "ok": result.ok, "time": elapsed, "arts": arts,
            "so_size": so_size, "has_opts": has_opts}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="glm5.1", choices=["glm5.1", "api_vllm"])
    ap.add_argument("--only", default=None, help="只跑某类型: T1/T2/T3")
    args = ap.parse_args()
    if args.provider == "api_vllm":
        os.environ.setdefault("VLLM_MODEL", "/zhaoshu/llm/Qwen3.6-27B-FP8")
        os.environ.setdefault("VLLM_API_BASE", "http://127.0.0.1:8000/v1")
    from core_new.doc_pipeline import DocPipeline
    from core_new.llm_gateway import get_gateway
    gw = get_gateway(args.provider)
    print(f"formal experiment: §17 split architecture | provider={args.provider} | enable_split_design=ON")

    results = []
    for label, sid, sd, qt, asm in SLOTS:
        if args.only and not label.startswith(args.only):
            continue
        results.append(await run_one(lambda o: DocPipeline(gateway=gw, workspace=str(o),
            model_routing={"_default": args.provider}, enable_thinking=True),
            label, sid, sd, qt, asm))

    print(f"\n{'='*70}\n  正式实验结果（§17 split 架构，3 类型）\n{'='*70}")
    print(f"  {'类型':14s} {'time':>7s} {'ok':>5s} {'solve.py':>8s} {'exec':>8s} {'产出':>6s}")
    for r in results:
        sp = r["arts"].get("solve.py", False); so = r["so_size"]
        prod = "✓" if (r["arts"].get("question.md") and (r["has_opts"] or r["arts"].get("solution.md"))) else "✗"
        print(f"  {r['label']:14s} {r['time']:6.1f}s {str(r['ok']):>5s} {str(sp):>8s} {str(so)+'B':>8s} {prod:>6s}")
    all_ok = all(r["ok"] for r in results)
    print(f"\n  → {'✓ 3 类型全部成功（split 架构端到端通过）' if all_ok else '✗ 有失败'}")


if __name__ == "__main__":
    asyncio.run(main())
