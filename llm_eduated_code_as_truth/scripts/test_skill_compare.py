#!/usr/bin/env python3
"""write_gen × 2 skill 对比：c_codegen(已验证) vs func_model(函数封装风格)。
同一 question.md，比 reasoning 峰值（是否巨想溢出）+ 是否产出 gen.py + 正确性。
"""
import asyncio, os, shutil, sys, time, subprocess, json
from pathlib import Path
from collections import defaultdict

os.environ.setdefault("GLM_MODEL", "glm-5.2")
os.environ.setdefault("GLM_API_BASE", "https://open.bigmodel.cn/api/paas/v4/")
os.environ.setdefault("GLM_API_KEY", os.environ.get("ANTHROPIC_AUTH_TOKEN", ""))
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
WS = Path("/tmp/skill_compare")

async def run_write_gen(sched, skill, slot, qpath):
    sw = WS / "workspace" / slot
    if sw.exists(): shutil.rmtree(sw)
    sw.mkdir(parents=True)
    t0 = time.monotonic()
    print(f"\n=== write_gen × skill={skill} (slot={slot}) ===", flush=True)
    try:
        await sched.run_agent("write_gen",
            f"读 question.md，把【当前这道补码除法题】的解法写成 gen.py 并就地 exec 验证能跑。用【{skill}】工作规范。只建当前题，不写 solution、不脑内算。",
            slot_id=slot, inject_files={"题目": str(qpath)},
            target_file="gen.py", skill_override=skill)
    except Exception as e:
        print(f"  异常: {e}", flush=True)
    dt = time.monotonic() - t0
    g = sw / "gen.py"
    # reasoning 峰值
    peak = 0
    tr = sw / "trace.jsonl"
    if tr.exists():
        for line in open(tr):
            r = json.loads(line)
            if r.get("agent") == "write_gen":
                peak = max(peak, r.get("reasoning_len", 0))
    produced = g.exists()
    # 重跑 gen.py 验自洽
    rerun = ""
    if produced:
        rr = subprocess.run(["python3", str(g)], capture_output=True, text=True, timeout=30)
        rerun = rr.stdout[:400] if rr.returncode == 0 else f"EXEC_FAIL: {rr.stderr[:200]}"
    flag = "✅压住" if peak < 8000 else ("⚠️偏高" if peak < 25000 else "❌巨想溢出")
    print(f"  耗时{dt:.0f}s | reasoning峰值={peak}字 {flag} | gen.py={'✅'+str(g.stat().st_size)+'B' if produced else '❌未产出'}", flush=True)
    return {"skill": skill, "time": dt, "reasoning_peak": peak, "produced": produced, "rerun": rerun, "gen_path": str(g) if produced else None}

async def main():
    from core_new.doc_pipeline.scheduler import DocScheduler
    from core_new.doc_pipeline.config import ROLE_PARAMS
    from core_new.llm_gateway import get_gateway
    ROLE_PARAMS["design_direct"] = {"max_tokens": 16000, "max_attempts": 4, "multi_turn": True, "enable_thinking": True}
    ROLE_PARAMS["write_gen"] = {"max_tokens": 32000, "max_attempts": 8, "multi_turn": True, "enable_thinking": True}

    if WS.exists(): shutil.rmtree(WS)
    (WS / "workspace").mkdir(parents=True)
    # design_card
    stem_ws = WS / "workspace" / "Q_STEM"
    stem_ws.mkdir()
    card = stem_ws / "design_card.md"
    src = Path("/tmp/paper_full/workspace/Q6/design_card.md")
    shutil.copy(src, card) if src.exists() else card.write_text("# design_card\n补码加减交替除法\n", encoding="utf-8")

    gw = get_gateway("glm5.1")
    sched = DocScheduler(gateway=gw, workspace=str(WS / "workspace"))
    print(f"gateway: {gw.model_name} | write_gen × 2 skill 对比\n", flush=True)

    # ① 锚题干（共享）
    print("=== ① design_direct 锚题干（共享 question.md）===", flush=True)
    t0 = time.monotonic()
    await sched.run_agent("design_direct",
        "锚定补码加减交替除法题题干：读「设计卡」+ grep_search 检索参考过往补码除法题，参考其形式锚定题干骨架+经验初始参数，产出 question.md。不算、不建模。",
        slot_id="Q_STEM", inject_files={"设计卡": str(card)}, target_file="question.md")
    print(f"① {time.monotonic()-t0:.0f}s\n", flush=True)
    qpath = stem_ws / "question.md"
    print("question.md 题干：", flush=True)
    print(qpath.read_text(encoding="utf-8")[:500] if qpath.exists() else "❌无", flush=True)

    # ② 两 skill 对比
    results = []
    for skill in ["c_codegen", "func_model"]:
        r = await run_write_gen(sched, skill, f"Q_{skill}", qpath)
        results.append(r)

    # 汇总
    print("\n========== 对比汇总 ==========", flush=True)
    print(f"{'skill':<14} {'reasoning峰值':>14} {'gen.py':>10} {'耗时':>8}", flush=True)
    for r in results:
        print(f"{r['skill']:<14} {r['reasoning_peak']:>14}字 {'✅' if r['produced'] else '❌':>10} {r['time']:>7.0f}s", flush=True)
    for r in results:
        if r["produced"]:
            print(f"\n--- {r['skill']} gen.py exec 输出（前400字）---\n{r['rerun']}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
