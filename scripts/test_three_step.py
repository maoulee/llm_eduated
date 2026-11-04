#!/usr/bin/env python3
"""3步窄边界测试（thinking 全 ON，靠边界压思考）：
  ①design_direct 锚题干 → question.md
  ②write_gen 写gen.py + 就地exec → gen.py
  ③write_solution 读exec输出整理 → solution.md
验证：每步 reasoning 是否被【边界】压住（非思考开关）、gen.py产出+自洽、答案对。
"""
import asyncio, os, shutil, sys, time, subprocess, json
from pathlib import Path
from collections import defaultdict

os.environ.setdefault("GLM_MODEL", "glm-5.2")
os.environ.setdefault("GLM_API_BASE", "https://open.bigmodel.cn/api/paas/v4/")
os.environ.setdefault("GLM_API_KEY", os.environ.get("ANTHROPIC_AUTH_TOKEN", ""))

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
WS = Path("/tmp/three_step_test")
SLOT = "Q_DIV"

async def main():
    from core_new.doc_pipeline.scheduler import DocScheduler
    from core_new.llm_gateway import get_gateway

    slot_ws = WS / "workspace" / SLOT
    if slot_ws.exists(): shutil.rmtree(slot_ws)
    slot_ws.mkdir(parents=True)
    card = slot_ws / "design_card.md"
    src = Path("/tmp/paper_full/workspace/Q6/design_card.md")
    shutil.copy(src, card) if src.exists() else card.write_text("# design_card\n补码加减交替除法\n", encoding="utf-8")

    # 新 agent 配 design 级 ROLE_PARAMS：线上无界 thinking 对复杂题≈2万tok，
    # 默认 max_tokens=20000 会被撑爆→no_output。提 max_tokens 容纳 + 加 attempts 容忍偶尔 overflow。
    from core_new.doc_pipeline.config import ROLE_PARAMS
    ROLE_PARAMS["design_direct"] = {"max_tokens": 16000, "max_attempts": 4, "multi_turn": True, "enable_thinking": True}
    ROLE_PARAMS["write_gen"] = {"max_tokens": 32000, "max_attempts": 8, "multi_turn": True, "enable_thinking": True}
    ROLE_PARAMS["write_solution"] = {"max_tokens": 12000, "max_attempts": 3, "multi_turn": True, "enable_thinking": True}

    gw = get_gateway("glm5.1")
    sched = DocScheduler(gateway=gw, workspace=str(WS / "workspace"))  # thinking 默认ON
    print(f"gateway: {gw.model_name} | 3步窄边界测试（thinking 全 ON，靠边界压）\n", flush=True)
    print(f"ROLE_PARAMS: write_gen max_tokens={ROLE_PARAMS['write_gen']['max_tokens']} max_attempts={ROLE_PARAMS['write_gen']['max_attempts']}\n", flush=True)

    q = slot_ws / "question.md"
    g = slot_ws / "gen.py"
    s = slot_ws / "solution.md"

    # ① design_direct
    t0=time.monotonic()
    print("=== ① design_direct 锚题干 ===", flush=True)
    await sched.run_agent("design_direct",
        "锚定补码加减交替除法题题干：读「设计卡」+ grep_search 检索参考过往补码除法题，"
        "参考其形式锚定题干骨架+经验初始参数，产出 question.md。不算、不建模、不写码。",
        slot_id=SLOT, inject_files={"设计卡": str(card)}, target_file="question.md")
    print(f"① {time.monotonic()-t0:.0f}s | question.md {'✅' if q.exists() else '❌'}\n", flush=True)

    # ② write_gen（写码+就地exec）
    t0=time.monotonic()
    print("=== ② write_gen 写gen.py + 就地exec ===", flush=True)
    await sched.run_agent("write_gen",
        "读 question.md，把【当前这道补码除法题】的机制写成 gen.py（补码加减交替法迭代模拟，"
        "用 PARAMS/REASONING/ANSWER 标签 print），写完就地 exec 验证能跑。只建当前题，不写 solution、不脑内算。",
        slot_id=SLOT, inject_files={"题目": str(q)}, target_file="gen.py")
    print(f"② {time.monotonic()-t0:.0f}s | gen.py {'✅' if g.exists() else '❌'}\n", flush=True)

    # 系统跑 gen.py → gen_output.txt（供③读）
    out = slot_ws / "gen_output.txt"
    if g.exists():
        r = subprocess.run(["python3", str(g)], capture_output=True, text=True, timeout=30)
        out.write_text(r.stdout if r.returncode==0 else f"EXEC_FAILED:\n{r.stderr}", encoding="utf-8")

    # ③ write_solution
    t0=time.monotonic()
    print("=== ③ write_solution 整理exec输出 ===", flush=True)
    await sched.run_agent("write_solution",
        "读 gen_output.txt（gen.py 的 exec 输出：PARAMS/REASONING/ANSWER）+ question.md 设问，"
        "整理成 solution.md。只整理，不重算、不exec、不质疑输出。",
        slot_id=SLOT, inject_files={"代码输出": str(out), "题目": str(q)}, target_file="solution.md")
    print(f"③ {time.monotonic()-t0:.0f}s | solution.md {'✅' if s.exists() else '❌'}\n", flush=True)

    # 评估
    print("========== 评估 ==========", flush=True)
    print(f"question.md: {q.stat().st_size if q.exists() else 0}B | gen.py: {g.stat().st_size if g.exists() else 0}B | solution.md: {s.stat().st_size if s.exists() else 0}B", flush=True)
    if q.exists():
        print("\n--- question.md（题干·看①锚的参数）---\n"+q.read_text(encoding="utf-8")[:500], flush=True)
    if g.exists():
        print("\n--- gen.py（前900字）---\n"+g.read_text(encoding="utf-8")[:900], flush=True)
    if out.exists():
        print("\n--- gen.py exec 输出（前900字·看推理流程+答案）---\n"+out.read_text(encoding="utf-8")[:900], flush=True)
    if s.exists():
        print("\n--- solution.md（前700字）---\n"+s.read_text(encoding="utf-8")[:700], flush=True)

    # 反过载指标：各 agent reasoning 峰值（核心验证：边界是否压住）
    tr = slot_ws / "trace.jsonl"
    if tr.exists():
        peak=defaultdict(int)
        for line in open(tr):
            r=json.loads(line); a=r.get("agent","?"); peak[a]=max(peak[a], r.get("reasoning_len",0))
        print("\n--- 反过载：各 agent reasoning 峰值（thinking全ON，靠边界压）---", flush=True)
        for a,v in peak.items():
            flag="✅压住" if v<8000 else ("⚠️偏高" if v<20000 else "❌过载")
            print(f"  {a}: {v}字 {flag}", flush=True)

if __name__=="__main__":
    asyncio.run(main())
