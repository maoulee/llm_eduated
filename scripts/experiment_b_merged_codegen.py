"""B 实验：融合合并 agent（代码先行流程），A/B 对比 A（分工版）。

核心假设验证：设计与验证的边界模糊是过度思考根源。
融合版用"代码先行"流程替代脑内构造：
  1. 读设计卡（固定）→ 规划考察形式（短）
  2. 写 param_gen.py 代码构造树结构/资源矩阵/参数 → exec 验证合法性
  3. 读 exec 输出 → 写 question.md（题干，不含答案）
  4. 写 solve.py（基于已构造参数算答案）→ exec → solution.md

对比 A（分工 design P1 → solve → design P2）：
  A 的 AVL 推演做 2 次（design 脑内 + solve 代码）
  B 的 AVL 推演做 1 次（代码构造时算完，直接用）

测试样本：
  - Q41 AVL（DS 类，树结构）
  - Q45 银行家算法（OS 类，资源矩阵）
"""
import asyncio
import os
import sys
import time
import json
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MERGED_CODEGEN_TASK = """你是融合出题求解智能体（B 实验，设计+求解合一，代码先行流程）。
设计卡已固定（考察形式/骨架/K-雷达已定案）。请用"代码先行"流程一步完成：

## 流程（严格按序）

### Step 1：读设计卡，规划参数方案（短，不推演）
读 design_card.md 的 question_structure_plan + parameter_plan + design_rationale。
确定要构造什么（AVL树/资源矩阵/图等）+ 需要满足的约束（如"触发2种旋转""安全序列存在"）。
不脑内构造，不脑内推演——只列"代码要生成什么"。

### Step 2：写 param_gen.py（代码构造参数，exec 验证）
write_file(param_gen.py) 写一个脚本，构造题目所需的具体数据结构/参数：
- 用代码生成（如随机+约束校验，或硬编码+合法性检查）
- 脚本必须 print 生成的参数（树结构/节点值/插入序列/资源矩阵等）+ 合法性校验结果
- exec_file 执行。若不合法（如初始树非 AVL、无安全序列），改 param_gen.py 重跑。

### Step 3：读 exec 输出，写 question.md（基于代码生成的参数）
read param_gen 的输出 → write_file(question.md) 写题干+设问+设计说明。
题干描述 param_gen 生成的具体数据（如"节点{10,20,...}，插入序列80,90,5,1"）。
不写答案（答案由 solve.py 算）。

### Step 4：写 solve.py + solution.md（基于已构造参数算答案）
write_file(solve.py) 写解题代码（用 param_gen 的参数算正确答案）→ exec → read 输出 → write solution.md。

## 约束
- 不脑内算数值结果。所有数值由代码（param_gen + solve.py）exec 确定。
- param_gen 必须先跑通且校验合法，才能写 question.md。
- question.md 不含答案。答案只在 solution.md + solve_output.txt。
"""


async def run_b(label, slot_id, assembled_path, out_root):
    os.environ.setdefault("VLLM_MODEL", "/zhaoshu/llm/Qwen3.6-27B-FP8")
    os.environ.setdefault("VLLM_API_BASE", "http://127.0.0.1:8000/v1")
    from core_new.doc_pipeline.scheduler import DocScheduler
    from core_new.llm_gateway import get_gateway

    gw = get_gateway("api_vllm")
    ws_dir = out_root / label / slot_id
    ws_dir.mkdir(parents=True, exist_ok=True)

    # 复制 assembled 经验缓存
    if assembled_path and Path(assembled_path).exists():
        shutil.copy(assembled_path, ws_dir / "assembled.md")

    sched = DocScheduler(gw, workspace=out_root / label)
    print(f"\n{'='*70}\n  [B 融合版] {label} (slot={slot_id})\n{'='*70}")

    inject = {"规划": str(ws_dir / "assembled.md")} if (ws_dir / "assembled.md").exists() else {}

    t0 = time.time()
    try:
        result = await sched.run_agent(
            "design",  # 复用 design agent（有 exec_file/edit_file/write_file tools）
            MERGED_CODEGEN_TASK,
            slot_id=slot_id,
            inject_files=inject,
            enable_thinking=True,
            # 不传 skill_override — 让 MERGED_CODEGEN_TASK 驱动，靠思考记忆收敛
        )
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"  ✗ crash: {e}")
        return {"label": label, "ok": False, "time": time.time()-t0}

    elapsed = time.time() - t0
    arts = {n: (ws_dir / n).exists() for n in
            ["param_gen.py", "question.md", "solve.py", "solution.md"]}
    # exec solve.py if exists
    import subprocess
    so_size = 0
    if arts["solve.py"]:
        r = subprocess.run([sys.executable, str(ws_dir/"solve.py")],
                          capture_output=True, text=True, timeout=30, cwd=str(ws_dir))
        so_size = len(r.stdout)
        arts["solve_exec_ok"] = (r.returncode == 0)

    print(f"  {elapsed:.1f}s | question={arts['question.md']} solve={arts['solve.py']} "
          f"solution={arts['solution.md']} exec_ok={arts.get('solve_exec_ok','?')}")
    for k in ["param_gen.py", "question.md", "solve.py", "solution.md"]:
        print(f"    {'✓' if arts[k] else '✗'} {k}")
    return {"label": label, "ok": all(arts[k] for k in
            ["question.md","solve.py","solution.md"]) and arts.get("solve_exec_ok",False),
            "time": elapsed, "arts": arts, "so_size": so_size}


async def main():
    out_root = Path("docs/test_output/b_merged_codegen")
    out_root.mkdir(parents=True, exist_ok=True)

    cases = [
        ("Q41_AVL", "TEST_C3", "docs/compose/Q41_assembled.md"),
        ("Q45_银行家", "TEST_Q45", "docs/compose/Q45_assembled.md"),
    ]

    results = []
    for label, sid, asm in cases:
        r = await run_b(label, sid, asm, out_root)
        results.append(r)

    print(f"\n{'='*70}\n  B 融合版结果\n{'='*70}")
    print(f"  {'题型':16s} {'time':>7s} {'ok':>5s}")
    for r in results:
        print(f"  {r['label']:16s} {r['time']:6.1f}s {str(r['ok']):>5s}")
    all_ok = all(r["ok"] for r in results)
    print(f"\n  → {'✓ 融合版全部成功' if all_ok else '✗ 有失败'}")


if __name__ == "__main__":
    asyncio.run(main())
