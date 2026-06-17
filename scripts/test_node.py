"""分段测试：从指定节点开始跑，跳过上游已验证的阶段。

用法：
  # 从 design_solve 开始测（复制上游产出 + 改 state 的 current_node）
  python3 scripts/test_node.py --from design_solve

  # 从 form_gate2 开始测
  python3 scripts/test_node.py --from form_gate2

  # 从 final 开始测
  python3 scripts/test_node.py --from final

前置：上游产物在 SOURCE_DIR（默认上次成功 run 的目录）。
"""
import argparse
import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("VLLM_MODEL", "/zhaoshu/llm/Qwen3.6-27B-FP8")
os.environ.setdefault("VLLM_API_BASE", "http://127.0.0.1:8000/v1")

SOURCE_DIR = Path("docs/test_output/pipeline_linked_test/TEST_AVL")
OUTPUT_DIR = Path("docs/test_output/node_test")

# graph 节点顺序（用于确定哪些上游节点需要标记为已完成）
NODE_ORDER = ["design_card", "exam_form", "design", "form_gate", "design_solve", "form_gate2", "final"]


def setup_from_node(target_node: str, slot_id: str = "TEST_AVL"):
    """复制上游产物到 OUTPUT_DIR，构造 pipeline_state 从 target_node 开始。"""
    out_ws = OUTPUT_DIR / slot_id
    out_ws.mkdir(parents=True, exist_ok=True)

    # 复制上游产物（但跳过 target 节点及之后的产出文件）
    target_idx = NODE_ORDER.index(target_node)
    # 各节点产出的文件（target 及之后的文件不复制，让目标节点从零产出）
    downstream_files = {
        "design": ["gen.py", "question.md"],
        "form_gate": ["review.md"],
        "design_solve": ["solve.py", "solution.md", "solve_output.txt"],
        "form_gate2": ["review.md"],
        "final": ["final_review.md", "final.md"],
    }
    skip_files = set()
    for i in range(target_idx, len(NODE_ORDER)):
        skip_files.update(downstream_files.get(NODE_ORDER[i], []))

    if SOURCE_DIR.exists():
        for f in SOURCE_DIR.iterdir():
            if f.is_file() and f.name not in skip_files:
                shutil.copy2(f, out_ws / f.name)
        print(f"  已复制上游产物: {SOURCE_DIR} → {out_ws}")
    else:
        print(f"  ⚠️ 源目录不存在: {SOURCE_DIR}")
        return None

    # 构造 pipeline_state：current_node 设为 target 的前一个节点
    # graph resume 时会 next_node(current_node, signal) 跳到 target
    target_idx = NODE_ORDER.index(target_node)
    if target_idx == 0:
        # 从第一个节点开始，不需要前置
        state = {
            "slot_id": slot_id,
            "current_node": "",
            "visit_counts": {},
            "history": [],
        }
    else:
        # current_node = target 的前一个节点
        prev_node = NODE_ORDER[target_idx - 1]
        history = []
        visit_counts = {}
        for i in range(target_idx):
            node = NODE_ORDER[i]
            if node in ("form_gate", "form_gate2", "final"):
                signal = "pass"
            else:
                signal = "ok"
            history.append({"node": node, "signal": signal, "feedback": ""})
            visit_counts[node] = 1

        state = {
            "slot_id": slot_id,
            "current_node": prev_node,  # 最后完成的节点
            "visit_counts": visit_counts,
            "history": history,
        }
    print(f"  pipeline_state: current_node={state['current_node']}, "
          f"history={len(state['history'])} nodes completed → will resume at {target_node}")
    state_path = out_ws / "pipeline_state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"  pipeline_state: current_node={target_node}, history={len(state['history'])} nodes completed")

    return out_ws


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_node", required=True, choices=NODE_ORDER,
                    help="从哪个节点开始测试")
    ap.add_argument("--slot", default="TEST_AVL")
    args = ap.parse_args()

    print("=" * 60)
    print(f"  分段测试: 从 {args.from_node} 开始")
    print("=" * 60)

    # Step 1: 复制上游产物 + 构造 state
    out_ws = setup_from_node(args.from_node, args.slot)
    if out_ws is None:
        return

    # Step 2: 强制重新生成 assembled.md（注入 expected_form），清 stale 下游产物强制重生成
    assembled_path = out_ws / "assembled.md"
    for stale in ("design_card.md", "exam_form.md", "question.md", "review.md", "gen.py"):
        (out_ws / stale).unlink(missing_ok=True)
    from compose.artifact_store import assemble_slot_experience_doc
    outline_entry = {
        "slot_id": args.slot,
        "question_type": "comprehensive",
        "score": 13,
        "primary_target_name": "平衡二叉树 AVL 的插入与旋转",
        "target_family": "DS-5 > 树与二叉树",
        "target_difficulty": 4,
        "examination_mode": "结构操作与状态维护模拟",
        "difficulty_rationale": "需多步串行推演树的形态变化",
        "reference_questions": ["exercise_00272.md", "exercise_00261.md", "simulation_00030.md"],
        "expected_form": "题干给一组插入/删除关键字序列，要求逐次画出 AVL 树形态变化并标注旋转类型",
    }
    doc = assemble_slot_experience_doc(
        slot_id=args.slot, examination_mode="结构操作与状态维护模拟",
        slot_md_path="", experience_card_path="", outline_entry=outline_entry,
    )
    assembled_path.write_text(doc, encoding="utf-8")
    (out_ws / "blueprint.md").write_text(doc, encoding="utf-8")
    print(f"  生成 assembled.md ({len(doc)} chars, 含 expected_form)")

    # Step 3: 跑 pipeline（从 target_node resume）
    print(f"\n[Step 2] 启动 pipeline（从 {args.from_node} resume）...")
    from core_new.doc_pipeline import DocPipeline
    from core_new.llm_gateway import get_gateway

    gateway = get_gateway("api_vllm")
    dp = DocPipeline(
        gateway=gateway,
        workspace=str(OUTPUT_DIR),
        model_routing={"_default": "api_vllm"},
        enable_thinking=True,
    )

    slot_data = {
        "slot_id": args.slot,
        "subject": "数据结构",
        "knowledge_tag": "DS-5 > 树与二叉树 > 平衡二叉树AVL",
        "primary_target_name": "平衡二叉树 AVL 的插入与旋转",
        "examination_mode": "结构操作与状态维护模拟",
        "target_difficulty": 4,
        "difficulty": "hard",
        "question_type": "comprehensive",
        "complexity": "standard",
    }

    t0 = time.time()
    try:
        result = await dp.run(
            slot_id=args.slot,
            slot_data=slot_data,
            assembled_experience_doc=assembled_path.read_text(encoding="utf-8"),
            question_type="comprehensive",
        )
    except Exception as e:
        import traceback
        print(f"\n  ✗ pipeline 崩溃: {e}")
        traceback.print_exc()
        return
    elapsed = time.time() - t0

    # Step 4: 结果
    print(f"\n{'='*60}")
    print(f"  [结果] elapsed={elapsed:.1f}s  result.ok={result.ok}")
    print(f"  review_status={result.review_status}")
    print(f"{'='*60}")

    # 检查 target_node 之后产出的文件
    for fname in ["review.md", "solution.md", "final_review.md", "final.md"]:
        fpath = out_ws / fname
        if fpath.exists():
            mtime = fpath.stat().st_mtime
            if mtime > t0:  # 本次 run 写的
                size = fpath.stat().st_size
                print(f"  ✓ {fname} ({size} chars) — 本次产出")
            else:
                print(f"  - {fname} — 上游残留（未更新）")


if __name__ == "__main__":
    asyncio.run(main())
