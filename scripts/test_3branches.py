"""三分支并发测试：综合题 + 选择题 + 概念题。

每个分支独立 timeout，互不影响。最多 4 并发（本地 vLLM 支持）。

用法：
  python3 scripts/test_3branches.py

前置：vLLM 在 127.0.0.1:8000 运行（--enable-prefix-caching）。
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("VLLM_MODEL", "/zhaoshu/llm/Qwen3.6-27B-FP8")
os.environ.setdefault("VLLM_API_BASE", "http://127.0.0.1:8000/v1")

OUTPUT_DIR = Path("docs/test_output/3branches_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 每个分支独立 timeout（秒）
TIMEOUTS = {
    "comprehensive": 600,  # 综合题 10 分钟
    "single_choice": 600,  # 选择题 10 分钟
    "conceptual": 300,     # 概念题 5 分钟
}


def build_assembled_for_comprehensive():
    """综合题的 assembled.md（含往年题参考）。"""
    from compose.artifact_store import assemble_slot_experience_doc
    outline_entry = {
        "slot_id": "TEST_COMP",
        "question_type": "comprehensive",
        "score": 13,
        "primary_target_name": "平衡二叉树 AVL 的插入与旋转",
        "target_family": "DS-5 > 树与二叉树",
        "target_difficulty": 4,
        "examination_mode": "结构操作与状态维护模拟",
        "difficulty_rationale": "需多步串行推演树的形态变化",
        "reference_questions": ["exercise_00272.md", "exercise_00261.md", "simulation_00030.md"],
    }
    return assemble_slot_experience_doc(
        slot_id="TEST_COMP", examination_mode="结构操作与状态维护模拟",
        slot_md_path="", experience_card_path="", outline_entry=outline_entry,
    ), outline_entry


def build_assembled_for_choice():
    """选择题的 assembled.md。"""
    from compose.artifact_store import assemble_slot_experience_doc
    outline_entry = {
        "slot_id": "TEST_SC",
        "question_type": "single_choice",
        "score": 2,
        "primary_target_name": "二叉树带权路径长度",
        "target_family": "DS-5 > 树与二叉树",
        "target_difficulty": 3,
        "examination_mode": "计算型——WPL公式计算与树结构分析",
        "difficulty_rationale": "需理解WPL定义并代入计算",
        "reference_questions": ["exercise_00261.md", "exercise_00255.md"],
    }
    return assemble_slot_experience_doc(
        slot_id="TEST_SC", examination_mode="计算型——WPL公式计算与树结构分析",
        slot_md_path="", experience_card_path="", outline_entry=outline_entry,
    ), outline_entry


def build_assembled_for_concept():
    """概念题的 assembled.md。"""
    from compose.artifact_store import assemble_slot_experience_doc
    outline_entry = {
        "slot_id": "TEST_CONCEPT",
        "question_type": "single_choice",
        "score": 2,
        "primary_target_name": "栈和队列的基本概念",
        "target_family": "DS-3 > 栈、队列",
        "target_difficulty": 2,
        "examination_mode": "概念辨析",
        "difficulty_rationale": "纯概念记忆题",
        "reference_questions": [],
    }
    return assemble_slot_experience_doc(
        slot_id="TEST_CONCEPT", examination_mode="概念辨析",
        slot_md_path="", experience_card_path="", outline_entry=outline_entry,
    ), outline_entry


async def run_branch(label, slot_id, slot_data, assembled_doc, output_sub, timeout_s):
    """跑单个分支。"""
    from core_new.doc_pipeline import DocPipeline
    from core_new.llm_gateway import get_gateway

    out = OUTPUT_DIR / output_sub
    out.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  [{label}] slot={slot_id} timeout={timeout_s}s")
    print(f"{'='*60}")

    try:
        gateway = get_gateway("api_vllm")
    except Exception as e:
        print(f"  ✗ gateway 失败: {e}")
        return {"label": label, "ok": False, "error": str(e), "elapsed": 0}

    dp = DocPipeline(
        gateway=gateway,
        workspace=str(out),
        model_routing={"_default": "api_vllm"},
        enable_thinking=True,
    )

    t0 = time.time()
    result = None
    try:
        result = await asyncio.wait_for(
            dp.run(
                slot_id=slot_id,
                slot_data=slot_data,
                assembled_experience_doc=assembled_doc,
                question_type=slot_data.get("question_type"),
            ),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        elapsed = time.time() - t0
        print(f"  ✗ TIMEOUT ({elapsed:.0f}s)")
        return {"label": label, "ok": False, "error": "timeout", "elapsed": elapsed}
    except Exception as e:
        import traceback
        elapsed = time.time() - t0
        print(f"  ✗ CRASH ({elapsed:.0f}s): {e}")
        traceback.print_exc()
        return {"label": label, "ok": False, "error": str(e), "elapsed": elapsed}

    elapsed = time.time() - t0
    ws = out / slot_id
    artifacts = {
        "question.md": (ws / "question.md").exists(),
        "solution.md": (ws / "solution.md").exists(),
        "final.md": (ws / "final.md").exists(),
        "gen.py": (ws / "gen.py").exists(),
        "design_card.md": (ws / "design_card.md").exists(),
    }

    print(f"  elapsed: {elapsed:.1f}s")
    print(f"  result.ok: {result.ok if result else '?'}")
    for k, v in artifacts.items():
        print(f"    {'✓' if v else '✗'} {k}")

    # 选择题检查是否有 A/B/C/D
    qpath = ws / "question.md"
    if qpath.exists() and slot_data.get("question_type") == "single_choice":
        qtext = qpath.read_text(encoding="utf-8")
        has_options = any(f"{L}." in qtext or f"{L}．" in qtext for L in "ABCD")
        print(f"    选项 A/B/C/D: {'✓' if has_options else '✗'}")

    return {
        "label": label, "ok": result.ok if result else False,
        "elapsed": elapsed, "artifacts": artifacts,
    }


async def main():
    print("=" * 60)
    print("  三分支并发测试（综合题 + 选择题 + 概念题）")
    print("=" * 60)

    # 构建 assembled docs
    print("\n[Step 1] 构建 assembled docs...")
    comp_assembled, _ = build_assembled_for_comprehensive()
    choice_assembled, _ = build_assembled_for_choice()
    concept_assembled, _ = build_assembled_for_concept()
    print(f"  综合: {len(comp_assembled)} chars")
    print(f"  选择: {len(choice_assembled)} chars")
    print(f"  概念: {len(concept_assembled)} chars")

    # slot data
    comp_slot = {
        "slot_id": "TEST_COMP", "subject": "数据结构",
        "knowledge_tag": "DS-5 > 平衡二叉树AVL",
        "primary_target_name": "平衡二叉树 AVL 的插入与旋转",
        "examination_mode": "结构操作与状态维护模拟",
        "target_difficulty": 4, "difficulty": "hard",
        "question_type": "comprehensive", "complexity": "standard",
    }
    choice_slot = {
        "slot_id": "TEST_SC", "subject": "数据结构",
        "knowledge_tag": "DS-5 > WPL",
        "primary_target_name": "二叉树带权路径长度",
        "examination_mode": "计算型——WPL公式计算",
        "target_difficulty": 3, "difficulty": "medium",
        "question_type": "single_choice", "complexity": "standard",
    }
    concept_slot = {
        "slot_id": "TEST_CONCEPT", "subject": "数据结构",
        "knowledge_tag": "DS-3 > 栈、队列",
        "primary_target_name": "栈和队列的基本概念",
        "examination_mode": "概念辨析",
        "target_difficulty": 2, "difficulty": "easy",
        "question_type": "single_choice", "complexity": "conceptual",
    }

    # 并发跑三个分支（各自独立 timeout）
    print(f"\n[Step 2] 并发启动三个分支...")
    tasks = [
        ("综合题", run_branch("COMPREHENSIVE", "TEST_COMP", comp_slot, comp_assembled,
                              "comp", TIMEOUTS["comprehensive"])),
        ("选择题", run_branch("SINGLE_CHOICE", "TEST_SC", choice_slot, choice_assembled,
                              "choice", TIMEOUTS["single_choice"])),
        ("概念题", run_branch("CONCEPTUAL", "TEST_CONCEPT", concept_slot, concept_assembled,
                              "concept", TIMEOUTS["conceptual"])),
    ]

    results = await asyncio.gather(*[t for _, t in tasks], return_exceptions=True)

    # 汇总
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for (label, _), r in zip(tasks, results):
        if isinstance(r, Exception):
            print(f"  {label:8s} ✗ CRASH: {r}")
        else:
            verdict = "✓ PASS" if r["ok"] else "✗ FAIL"
            print(f"  {label:8s} {verdict}  {r['elapsed']:.0f}s  error={r.get('error', '')}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
