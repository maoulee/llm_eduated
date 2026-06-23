"""概念题批量出题实验（§21）。

测试概念题专用 skill：一次性出多道概念题 → 审核 → 发布。
概念题无计算，不走 gen.py/solve，基于知识点直接写题干+选项+答案。

测试样本：
  - OS 死锁概念辨析（complexity=conceptual）
"""
import asyncio
import os
import sys
import time
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


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

    # 概念题 slot_data（OS 死锁概念辨析）
    slot_data = {
        "slot_id": "TEST_CONCEPT",
        "subject": "操作系统",
        "knowledge_tag": "OS-2 > 进程与线程 > 死锁 > 死锁概念",
        "primary_target_name": "死锁的概念与产生条件",
        "difficulty": "easy",
        "question_type": "single_choice",
        "complexity": "conceptual",  # ← 概念题分支
    }

    out = Path("docs/test_output/conceptual_test")
    out.mkdir(parents=True, exist_ok=True)

    # 复用 Q45 assembled（死锁相关经验）
    src = Path("docs/compose/Q45_assembled.md")
    assembled = src.read_text(encoding="utf-8") if src.exists() else ""

    print(f"概念题批量出题实验（§21）| provider={args.provider}")
    print(f"考点：{slot_data['primary_target_name']}")
    print(f"complexity=conceptual → conceptual_batch_skill 分支\n")

    dp = DocPipeline(gateway=gw, workspace=str(out),
                     model_routing={"_default": args.provider}, enable_thinking=True)

    t0 = time.time()
    try:
        result = await dp.run(
            slot_id="TEST_CONCEPT",
            slot_data=slot_data,
            assembled_experience_doc=assembled,
            question_type="single_choice",
        )
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"  ✗ crash: {e}"); return

    elapsed = time.time() - t0
    ws = out / "TEST_CONCEPT"
    print(f"\n{'='*60}")
    print(f"  {elapsed:.1f}s | ok={result.ok} | review={result.review_status}")
    print(f"{'='*60}")

    for f in ["question.md", "solution.md", "review.md", "final.md"]:
        p = ws / f
        if p.exists():
            content = p.read_text(encoding="utf-8")
            # 数概念题数量（按 A. B. C. D. 选项组）
            n_questions = content.count("A.") + content.count("A．")
            print(f"  ✓ {f} ({len(content)} chars, ~{n_questions} 选项组)")
        else:
            print(f"  ✗ {f}")

    # 展示题目
    q = ws / "question.md"
    if q.exists():
        print(f"\n--- question.md 前 40 行 ---")
        print(q.read_text(encoding="utf-8")[:2000])


if __name__ == "__main__":
    asyncio.run(main())
