"""端到端测试：打通后的 pipeline（含往年题参考的 assembled.md → design_card → 全流程）。

验证：
1. assemble 能生成含往年真题参考的 assembled.md
2. design_card 能读到往年题参考，锚定设问结构
3. 全流程不卡死（design 不死循环）

前置：vLLM 在 127.0.0.1:8000 运行。
用法：
  python3 scripts/test_pipeline_linked.py
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("VLLM_MODEL", "/zhaoshu/llm/Qwen3.6-27B-FP8")
os.environ.setdefault("VLLM_API_BASE", "http://127.0.0.1:8000/v1")

OUTPUT_DIR = Path("docs/test_output/pipeline_linked_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_assembled_with_refs():
    """用打通后的 assemble 逻辑生成含往年题参考的 assembled.md。"""
    from compose.artifact_store import assemble_slot_experience_doc

    # AVL 往年题（从 question_experiences 检索到的同知识点题）
    outline_entry = {
        "slot_id": "TEST_AVL",
        "question_type": "comprehensive",
        "score": 13,
        "primary_target_name": "平衡二叉树 AVL 的插入与旋转",
        "target_family": "DS-5 > 树与二叉树",
        "target_difficulty": 4,
        "examination_mode": "结构操作与状态维护模拟",
        "difficulty_rationale": "需多步串行推演树的形态变化，且需精准辨析旋转类型的触发条件",
        "reference_questions": [
            "exercise_00272.md",
            "exercise_00261.md",
            "simulation_00030.md",
        ],
    }

    doc = assemble_slot_experience_doc(
        slot_id="TEST_AVL",
        examination_mode="结构操作与状态维护模拟",
        slot_md_path="",
        experience_card_path="",  # 无题位经验卡（模拟现场组卷）
        outline_entry=outline_entry,
    )
    return doc, outline_entry


async def main():
    print("=" * 70)
    print("  打通后端到端测试：往年题参考 → design_card → 全流程")
    print("=" * 70)

    # Step 1: 生成含往年题参考的 assembled.md
    print("\n[Step 1] 生成含往年题参考的 assembled.md...")
    assembled_doc, outline_entry = build_assembled_with_refs()
    has_ref = "## 往年真题参考" in assembled_doc
    print(f"  assembled.md 长度: {len(assembled_doc)} chars")
    print(f"  含往年真题参考段: {'✓' if has_ref else '✗'}")
    if not has_ref:
        print("  ✗ assemble 未生成往年题参考段，终止测试")
        return

    # 段落标题
    print("  段落结构:")
    for line in assembled_doc.split("\n"):
        if line.startswith("# ") or line.startswith("## "):
            print(f"    {line}")

    # Step 2: 跑 pipeline
    print(f"\n[Step 2] 启动 pipeline（本地 vLLM）...")
    from core_new.doc_pipeline import DocPipeline
    from core_new.llm_gateway import get_gateway

    gateway = get_gateway("api_vllm")
    dp = DocPipeline(
        gateway=gateway,
        workspace=str(OUTPUT_DIR),
        model_routing={"_default": "api_vllm"},
        enable_thinking=True,
    )

    slot_id = "TEST_AVL"
    slot_data = {
        "slot_id": slot_id,
        "subject": "数据结构",
        "knowledge_tag": "DS-5 > 树与二叉树 > 平衡二叉树AVL",
        "primary_target_name": "平衡二叉树 AVL 的插入与旋转",
        "examination_mode": "结构操作与状态维护模拟",
        "target_difficulty": 4,
        "difficulty": "hard",
        "question_type": "comprehensive",
        "complexity": "standard",
        "reference_questions": outline_entry["reference_questions"],
    }

    t0 = time.time()
    result = None
    try:
        result = await dp.run(
            slot_id=slot_id,
            slot_data=slot_data,
            assembled_experience_doc=assembled_doc,
            question_type="comprehensive",
        )
    except Exception as e:
        import traceback
        print(f"\n  ✗ pipeline 崩溃: {e}")
        traceback.print_exc()
    elapsed = time.time() - t0

    # Step 3: 验证产出
    print(f"\n{'='*70}")
    print(f"  [结果] elapsed={elapsed:.1f}s")
    print(f"{'='*70}")

    if result:
        print(f"  result.ok: {result.ok}")
        print(f"  review_status: {result.review_status}")
        print(f"  final_content: {len(result.final_content or '')} chars")

    ws = OUTPUT_DIR / slot_id
    artifacts = {
        "design_card.md": (ws / "design_card.md").exists(),
        "exam_form.md": (ws / "exam_form.md").exists(),
        "question.md": (ws / "question.md").exists(),
        "gen.py": (ws / "gen.py").exists(),
        "solve.py": (ws / "solve.py").exists(),
        "solve_output.txt": (ws / "solve_output.txt").exists(),
        "solution.md": (ws / "solution.md").exists(),
        "review.md": (ws / "review.md").exists(),
        "final.md": (ws / "final.md").exists(),
    }
    print(f"\n  产出文件:")
    for k, v in artifacts.items():
        print(f"    {'✓' if v else '✗'} {k}")

    # 检查 design_card 是否引用了往年题
    dc = ws / "design_card.md"
    if dc.exists():
        dc_text = dc.read_text(encoding="utf-8")
        # 检查 question_structure_plan 段是否提到往年参考
        print(f"\n  ── design_card.md question_structure_plan 段 ──")
        import re
        m = re.search(r"## question_structure_plan(.*?)(?=\n## |\Z)", dc_text, re.DOTALL)
        if m:
            plan = m.group(1).strip()
            print("    " + plan[:800].replace("\n", "\n    "))
            # 检查是否引用了往年题
            ref_keywords = ["往年", "参考", "复用骨架", "exercise_", "simulation_"]
            has_ref_in_plan = any(kw in plan for kw in ref_keywords)
            print(f"\n    design_card 引用往年题: {'✓' if has_ref_in_plan else '✗（未明确引用）'}")
        else:
            print("    (question_structure_plan 段缺失)")

    print(f"\n{'='*70}")
    print(f"  测试完成 — 总耗时 {elapsed:.1f}s")
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(main())
