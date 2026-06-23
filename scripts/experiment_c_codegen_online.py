"""C 实验：代码一次性产出全部（参数+题干+求解路径+答案），线上模型测试。

核心洞察（来自 B 实验发现）：
  param_gen.py 构造参数时已经算了答案（旋转/安全序列）。
  所以融合后不需要单独 solve.py——param_gen 就是求解。
  问题只是输出格式没组织成"题目+答案"。

C 方案：让代码一次性产出"参数+题干描述+求解路径+答案"，
模型只做"基于考察形式规划→代码生成→组装题目"。

流程：
  1. 读设计卡 → 规划考察形式（短，已知）
  2. write gen.py — 一个脚本，构造参数 + print 题干格式描述 + print 求解路径 + print 答案
     exec 验证。改 gen.py 重跑直到合法。
  3. read exec 输出 → write question.md（题干，直接复制 gen 的输出）+ write solution.md（求解+答案，直接复制）

不写 solve.py（gen.py 就是求解）。
"""
import asyncio
import os
import sys
import time
import shutil
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

C_TASK = """你是融合出题智能体（C 方案，代码一次性产出全部）。
按工作规范（c_codegen skill）的三步流程执行：①规划 → ②写 gen.py + exec → ③组装 question.md + solution.md。
gen.py 一次 print 4 段（参数/题干描述/求解路径/答案），exec 通过后复制输出组装题目。
不写 solve.py（gen.py 即求解）。不脑内算（代码 exec 即真值）。"""


async def run_c(provider, label, slot_id, assembled_path, out_root):
    if provider == "api_vllm":
        os.environ.setdefault("VLLM_MODEL", "/zhaoshu/llm/Qwen3.6-27B-FP8")
        os.environ.setdefault("VLLM_API_BASE", "http://127.0.0.1:8000/v1")
    from core_new.doc_pipeline.scheduler import DocScheduler
    from core_new.llm_gateway import get_gateway

    gw = get_gateway(provider)
    ws_dir = out_root / label / slot_id
    ws_dir.mkdir(parents=True, exist_ok=True)

    if assembled_path and Path(assembled_path).exists():
        shutil.copy(assembled_path, ws_dir / "assembled.md")

    sched = DocScheduler(gw, workspace=out_root / label)
    print(f"\n{'='*70}\n  [C 代码一次性] {label} | provider={provider}\n{'='*70}")

    inject = {"规划": str(ws_dir / "assembled.md")} if (ws_dir / "assembled.md").exists() else {}
    t0 = time.time()
    try:
        await sched.run_agent(
            "design", C_TASK, slot_id=slot_id,
            inject_files=inject, enable_thinking=True,
            skill_override="c_codegen",
        )
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"  ✗ crash: {e}")
        return {"label": label, "ok": False, "time": time.time()-t0}

    elapsed = time.time() - t0
    arts = {n: (ws_dir / n).exists() for n in ["gen.py", "question.md", "solution.md"]}
    gen_exec_ok = False
    if arts["gen.py"]:
        r = subprocess.run([sys.executable, str(ws_dir/"gen.py")],
                          capture_output=True, text=True, timeout=30, cwd=str(ws_dir))
        gen_exec_ok = (r.returncode == 0)
        has_4_sections = all(s in r.stdout for s in ["参数","题干描述","求解路径","答案"]) if gen_exec_ok else False
        arts["gen_4_sections"] = has_4_sections

    print(f"  {elapsed:.1f}s | gen={arts['gen.py']} question={arts['question.md']} "
          f"solution={arts['solution.md']} exec_ok={gen_exec_ok} 4段={arts.get('gen_4_sections','?')}")
    for k in ["gen.py", "question.md", "solution.md"]:
        print(f"    {'✓' if arts[k] else '✗'} {k}")
    return {"label": label, "ok": arts["gen.py"] and arts["question.md"] and arts["solution.md"],
            "time": elapsed, "arts": arts, "exec_ok": gen_exec_ok}


async def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="glm5.1", choices=["glm5.1", "api_vllm"])
    ap.add_argument("--only", default=None)
    args = ap.parse_args()

    out_root = Path(f"docs/test_output/c_codegen_{args.provider}")
    out_root.mkdir(parents=True, exist_ok=True)

    cases = [
        ("Q41_AVL", "TEST_C3", "docs/compose/Q41_assembled.md"),
        ("Q45_银行家", "TEST_Q45", "docs/compose/Q45_assembled.md"),
    ]
    results = []
    for label, sid, asm in cases:
        if args.only and not label.startswith(args.only):
            continue
        r = await run_c(args.provider, label, sid, asm, out_root)
        results.append(r)

    print(f"\n{'='*70}\n  C 代码一次性 结果（provider={args.provider}）\n{'='*70}")
    for r in results:
        print(f"  {r['label']:16s} {r['time']:6.1f}s ok={r['ok']} exec={r.get('exec_ok','?')}")
    print(f"  → {'✓ 全部成功' if all(r['ok'] for r in results) else '✗ 有失败'}")


if __name__ == "__main__":
    asyncio.run(main())
