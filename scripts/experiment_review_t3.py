"""测试重写后的 review 能否发现 T3 的'只1种旋转'问题。

用已有的 T3 产出（只插1节点触发1种旋转，design_card 要求≥2种）喂给 review，
看重写后的 review 是否判 needs_fix（而非旧版的 pass）。
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="api_vllm", choices=["glm5.1", "api_vllm"])
    args = ap.parse_args()
    if args.provider == "api_vllm":
        os.environ.setdefault("VLLM_MODEL", "/zhaoshu/llm/Qwen3.6-27B-FP8")
        os.environ.setdefault("VLLM_API_BASE", "http://127.0.0.1:8000/v1")

    from core_new.doc_pipeline.scheduler import DocScheduler
    from core_new.llm_gateway import get_gateway

    gw = get_gateway(args.provider)
    out = Path("docs/test_output/review_test_t3")
    ws = out / "TEST_C3"
    ws.mkdir(parents=True, exist_ok=True)

    # 复制 T3 的 design_card + question（只1种旋转的 case）
    import shutil
    src_dc = Path("docs/test_output/timing_vllm/T3_正常综合/TEST_C3/design_card.md")
    src_q = Path("docs/test_output/timing_vllm/T3_正常综合/TEST_C3/question.md")
    src_asm = Path("docs/test_output/timing_vllm/T3_正常综合/TEST_C3/assembled.md")
    for src in [src_dc, src_q, src_asm]:
        if src.exists():
            shutil.copy(src, ws / src.name)

    sched = DocScheduler(gw, workspace=out)
    print(f"测试重写后 review | T3 case（只1种旋转，design_card 要求≥2种）| provider={args.provider}")
    print(f"预期：重写后 review 应判 needs_fix（旧版 pass 漏审）\n")

    r_task = (
        "审核这道 AVL 题：design_card 要求'至少2种旋转类型'，"
        "判断题干是否真正满足这个约束。"
    )
    r_inject = {
        "规划": str(ws / "assembled.md"),
        "设计卡": str(ws / "design_card.md"),
        "题目": str(ws / "question.md"),
    }

    await sched.run_agent(
        "review", r_task, slot_id="TEST_C3",
        inject_files=r_inject, enable_thinking=True,
    )

    review_path = ws / "review.md"
    if review_path.exists():
        text = review_path.read_text(encoding="utf-8")
        print("="*60)
        print(review_path.read_text(encoding="utf-8")[:3000])
        print("="*60)
        # 判断 pass/needs_fix
        if "needs_fix" in text.lower():
            print("\n✅ 重写后 review 发现了问题（needs_fix）！")
        elif "pass" in text.lower():
            print("\n❌ 重写后 review 仍然 pass（未发现问题）")
        else:
            print("\n? review 状态不明确")
    else:
        print("✗ review.md 未产出")


if __name__ == "__main__":
    asyncio.run(main())
