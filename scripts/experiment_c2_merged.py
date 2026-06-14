"""C2 实验：合并 agent（设计+求解合一）+ 思考记忆，对比 C1 分工版。

验证核心问题：之前过度思考的根因是"agent 职责太重没拆分"还是"没保留思考"？
如果合并 agent + 思考记忆能跑通，说明保留思考才是治本，拆分可能多余。

本脚本不改主线架构——它临时构造一个合并 agent 调用（设计题干+写 solve.py+求解），
用 §20 思考记忆（reasoning_content 回传 + preserve_thinking）跑 T3 AVL hard。

对比基准（C1）：§19 分工（design P1 → solve → design P2）+ 思考记忆
- C1 design reasoning: 10317 收敛
- C2（本脚本）：合并 agent，看 reasoning 是否更低/更高，是否跑通
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MERGED_TASK = """你是合并出题求解智能体（C2 实验，设计+求解合一）。请一步完成：

1. 读 design_card.md（含 design_rationale 设计理念交接）+ assembled.md 经验缓存 + exam_form.md。
2. 基于骨架+经验值，设计题干+设问+经验值参数（AVL 题，凭经验甩值不脑内算）。
3. 直接写 solve.py（解题代码，从你设计的题干参数算出正确答案，exec 验证）。
4. 写 question.md（题干+设问+设计说明，含 design_rationale 告诉你的考察意图）+ solve.py + solution.md（基于 exec 输出）。

约束：
- 经验值参数大胆给（AVL n=7-8 友好值），不脑内算数值结果。
- solve.py 只算正确答案，exec 输出即真值。
- 一次完成设计+求解，不拆分。"""


async def run_c2():
    os.environ.setdefault("VLLM_MODEL", "/zhaoshu/llm/Qwen3.6-27B-FP8")
    os.environ.setdefault("VLLM_API_BASE", "http://127.0.0.1:8000/v1")
    from core_new.doc_pipeline.scheduler import DocScheduler
    from core_new.llm_gateway import get_gateway

    gw = get_gateway("api_vllm")
    workspace = Path("docs/test_output/c2_merged_t3")
    (workspace / "T3_正常综合" / "TEST_C3").mkdir(parents=True, exist_ok=True)
    ws = workspace / "T3_正常综合" / "TEST_C3"

    # 复用 baseline 的 assembled.md（T3 经验缓存）
    import shutil
    src_assembled = Path("docs/compose/Q41_assembled.md")
    if src_assembled.exists():
        shutil.copy(src_assembled, ws / "assembled.md")

    sched = DocScheduler(gw, workspace=ws.parent)
    print(f"C2 实验：合并 agent（设计+求解合一）+ 思考记忆 | T3 AVL hard")
    print(f"preserve_thinking={os.environ.get('VLLM_PRESERVE_THINKING','')}, workspace={ws}")

    inject = {"规划": str(ws / "assembled.md")} if (ws / "assembled.md").exists() else {}
    t0 = time.time()
    try:
        result = await sched.run_agent(
            "design",  # 复用 design agent（有 thinking budget + exec_file/edit_file tools）
            MERGED_TASK,
            slot_id="TEST_C3",
            inject_files=inject,
            enable_thinking=True,
            # C2: 不传 design_draft_skill（P1 skill 会说"不写 solve.py"，与合并冲突）
            # 让 MERGED_TASK 文本驱动，靠思考记忆收敛。
        )
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"  ✗ crash: {e}"); return
    elapsed = time.time() - t0
    print(f"\n  {elapsed:.1f}s | merged agent 完成")
    print(f"  question.md: {(ws / 'question.md').exists()}")
    print(f"  solve.py: {(ws / 'solve.py').exists()}")
    print(f"  solution.md: {(ws / 'solution.md').exists()}")
    if (ws / "solve.py").exists():
        import subprocess
        r = subprocess.run([sys.executable, str(ws / "solve.py")], capture_output=True, text=True, timeout=30, cwd=str(ws))
        print(f"  solve.py exec: rc={r.returncode}, stdout[:200]={r.stdout[:200]!r}")


if __name__ == "__main__":
    asyncio.run(run_c2())
