#!/usr/bin/env python3
"""真实流水线测试：新 6 步架构，用 DocScheduler.run_agent 调度，测单题总耗时。

6 步：
  ① design_direct → question.md（锚题干）
  ② dual_review(阶段1·审题干) → review.md  [pass/退回①]
  ③ write_gen → gen.py + exec  [兜底场景关思考]
  ④ write_solution → solution.md
  ⑤ dual_review(阶段2·审求解) → review.md  [pass/退回③或①]
  ⑥ done

测试题：补码加减交替法除法（无参考题→write_gen 走兜底，关思考）。
记录每步耗时 + 总耗时 + 各步产出。
"""
import asyncio
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("GLM_MODEL", "glm-5.2")
os.environ.setdefault("GLM_API_BASE", "https://open.bigmodel.cn/api/coding/paas/v4/")
os.environ.setdefault("GLM_API_KEY", "d6f4904cd7d7462c8e82c5c4e097bebe.hQln0yGBA2muYhJU")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core_new.llm_gateway import get_gateway
from core_new.doc_pipeline.scheduler import DocScheduler
from core_new.doc_pipeline.config import ROLE_PARAMS

SLOT = "Q6_DIV"
WS = Path("/tmp/pipeline_test")

QUESTION_STEM = """设 $X = -0.1011$，$Y = 0.1101$，$X$ 和 $Y$ 均为定点小数，采用补码表示（含双符号位，即模4补码）。请回答：

**（1）**（3分）写出 $[X]_补$ 和 $[Y]_补$，并求出 $[-Y]_补$。说明补码加减交替法除法的初始状态。

**（2）**（5分）用**补码加减交替法（不恢复余数法）**计算 $[X \\div Y]_补$，写出每一步的余数、商位及操作说明（包括加减操作和移位操作）。

**（3）**（2分）给出最终的商 $[Q]_补$ 和余数 $[R]_补$，并说明是否需要对商的末位进行修正。
"""

DESIGN_CARD = """# design_card

## blueprint_contract
```yaml
slot_id: Q6_DIV
question_type: subjective
score: 10
examination_mode: 计算型——补码加减交替法除法逐步计算
primary_target_name: 补码不恢复余数法除法运算
target_difficulty: 3
k_dominant: K3
hard_constraints:
  - 被除数和除数均为定点小数
  - 必须使用补码表示
  - 必须使用加减交替法（不恢复余数法）
should_be:
  - 考察补码加减交替法除法的完整计算过程
  - 要求写出每一步的余数、商位、操作说明
should_not_be:
  - 不考察原码除法或恢复余数法
  - 不考察浮点数运算
```

## core_knowledge_intent
考察补码加减交替法除法的算法流程：符号判断、加减操作、移位、商位确定、末位修正。

## reference_questions
（无——本题算法在 question_experiences 中无对应参考题）
"""


def _status_of(review_text: str) -> str:
    import re
    m = re.search(r"##\s*status\s*\n\s*(\w+)", review_text or "")
    return m.group(1).strip().lower() if m else "unknown"


def _routing_of(review_text: str) -> str:
    import re
    m = re.search(r"##\s*routing\s*\n\s*([a-z_]+)", review_text or "")
    return m.group(1).strip().lower() if m else "none"


async def main():
    # ── 配置 ROLE_PARAMS（各步策略：已验证的配置）──
    ROLE_PARAMS["design_direct"] = {"max_tokens": 16000, "max_attempts": 4, "multi_turn": True, "enable_thinking": True}
    ROLE_PARAMS["write_gen"] = {"max_tokens": 12000, "max_attempts": 8, "multi_turn": True, "enable_thinking": False}  # 关思考+分步流程
    ROLE_PARAMS["write_solution"] = {"max_tokens": 8000, "max_attempts": 4, "multi_turn": True, "enable_thinking": False}  # 整理文档，关思考（待后续优化加skill）
    ROLE_PARAMS["dual_review"] = {"max_tokens": 16000, "max_attempts": 3, "multi_turn": True, "enable_thinking": True}  # 审建模不代入，思考ON

    # 准备 workspace
    WS.mkdir(parents=True, exist_ok=True)
    for f in WS.glob(f"{SLOT}/*"):
        f.unlink()
    slot_ws = WS / SLOT
    slot_ws.mkdir(parents=True, exist_ok=True)
    (slot_ws / "design_card.md").write_text(DESIGN_CARD, encoding="utf-8")

    gw = get_gateway("glm5.1")
    sched = DocScheduler(gateway=gw, workspace=str(WS), enable_thinking=True)
    print(f"模型: glm-5.2 | slot: {SLOT} | workspace: {WS}/{SLOT}\n", flush=True)

    timings = {}
    total_start = time.monotonic()

    def _step(name, t0):
        dt = time.monotonic() - t0
        timings[name] = dt
        print(f"  [{name}] {dt:.0f}s\n", flush=True)

    # ── ① design_direct → question.md ──────────────────────────
    print("=" * 60, flush=True)
    print("① design_direct（锚题干）", flush=True)
    print("=" * 60, flush=True)
    t0 = time.monotonic()
    q_text = await sched.run_agent(
        "design_direct",
        task="根据 design_card 设计题干，写出 question.md。题干要完整、自洽、符合 design_card 的考察意图。",
        slot_id=SLOT,
        inject_files={"design_card": slot_ws / "design_card.md"},
        target_file="question.md",
    )
    _step("①design_direct", t0)
    print("--- question.md 摘要 ---", flush=True)
    print((q_text or "")[:300], "...\n", flush=True)

    # ── ② dual_review 阶段1（审题干）──────────────────────────
    print("=" * 60, flush=True)
    print("② dual_review 阶段1（审题干自洽）", flush=True)
    print("=" * 60, flush=True)
    t0 = time.monotonic()
    review_q = await sched.run_agent(
        "dual_review",
        task="## 本轮阶段\n本轮审题干（阶段1）。审 question.md 是否自洽（知识点/参数/条件/符合 design_card）。",
        slot_id=SLOT,
        inject_files={"design_card": slot_ws / "design_card.md", "question.md": slot_ws / "question.md"},
        target_file="review.md",
    )
    _step("②review_question", t0)
    status_q = _status_of(review_q)
    print(f"--- 阶段1审核结果: status={status_q} ---\n", flush=True)
    if status_q != "pass":
        print(f"⚠️ 题干审核未通过（{status_q}），按真实流程应退回 design_direct。本次测试先继续后续步骤看全流程耗时。\n", flush=True)

    # ── ③ write_gen → gen.py（兜底关思考）─────────────────────
    print("=" * 60, flush=True)
    print("③ write_gen（建模，兜底场景 enable_thinking=False）", flush=True)
    print("=" * 60, flush=True)
    t0 = time.monotonic()
    gen_text = await sched.run_agent(
        "write_gen",
        task="读 design_card + question.md，写 gen.py（按工作规范：解法封装成 def solve，调用取值，print PARAMS/REASONING/ANSWER），然后 exec_file 验证能跑。",
        slot_id=SLOT,
        inject_files={"design_card": slot_ws / "design_card.md", "question.md": slot_ws / "question.md"},
        target_file="gen.py",
        enable_thinking=False,  # 兜底关思考
    )
    _step("③write_gen", t0)
    gen_exists = (slot_ws / "gen.py").exists()
    has_version = gen_exists and "# VERSION" in (slot_ws / "gen.py").read_text(encoding="utf-8")
    print(f"--- gen.py: {'✓' if gen_exists else '✗'} | VERSION标记: {'✓' if has_version else '-'} ---\n", flush=True)

    # ── ④ write_solution → solution.md ─────────────────────────
    print("=" * 60, flush=True)
    print("④ write_solution（整理 gen 输出）", flush=True)
    print("=" * 60, flush=True)
    t0 = time.monotonic()
    sol_text = await sched.run_agent(
        "write_solution",
        task="读 gen.py + 它的 exec 输出，整理成 solution.md（解题过程，基于 gen 的输出，不自行重算）。",
        slot_id=SLOT,
        inject_files={"gen.py": slot_ws / "gen.py", "question.md": slot_ws / "question.md"},
        target_file="solution.md",
    )
    _step("④write_solution", t0)

    # ── ⑤ dual_review 阶段2·A（审代码建模）─────────────────────
    print("=" * 60, flush=True)
    print("⑤ dual_review 阶段2·A（审代码建模，不代入参数）", flush=True)
    print("=" * 60, flush=True)
    t0 = time.monotonic()
    review_a = await sched.run_agent(
        "dual_review",
        task="## 本轮阶段\n本轮审求解-代码（阶段2·子阶段A）。审 gen.py 的建模思路对不对（看代码结构/规则映射，不代入参数推演）。",
        slot_id=SLOT,
        inject_files={"question.md": slot_ws / "question.md", "gen.py": slot_ws / "gen.py"},
        target_file="review.md",
    )
    _step("⑤review_code", t0)
    status_a = _status_of(review_a)
    print(f"--- 子阶段A结果: status={status_a} ---\n", flush=True)

    # ── ⑥ dual_review 阶段2·B（审文档忠实，仅A通过后）──────────
    status_b = "skipped(A未通过)"
    routing_s = _routing_of(review_a)
    if status_a == "pass":
        print("=" * 60, flush=True)
        print("⑥ dual_review 阶段2·B（审文档忠实：solution是否忠实转写代码）", flush=True)
        print("=" * 60, flush=True)
        t0 = time.monotonic()
        review_b = await sched.run_agent(
            "dual_review",
            task="## 本轮阶段\n本轮审求解-文档（阶段2·子阶段B）。审 solution.md 是否忠实转写 gen.py（形式一致/单步抄写无误/无幻觉）。",
            slot_id=SLOT,
            inject_files={"gen.py": slot_ws / "gen.py", "solution.md": slot_ws / "solution.md"},
            target_file="review.md",
        )
        _step("⑥review_doc", t0)
        status_b = _status_of(review_b)
        routing_s = _routing_of(review_b)
        print(f"--- 子阶段B结果: status={status_b} | routing={routing_s} ---\n", flush=True)
    else:
        print(f"⚠️ 子阶段A未通过（{status_a}），跳过B。routing={routing_s}\n", flush=True)

    # ── 总结 ──────────────────────────────────────────────────
    total = time.monotonic() - total_start
    print("=" * 60, flush=True)
    print("流水线总结", flush=True)
    print("=" * 60, flush=True)
    for name, dt in timings.items():
        print(f"  {name:24s} {dt:6.0f}s", flush=True)
    print(f"  {'总耗时':24s} {total:6.0f}s ({total/60:.1f}min)", flush=True)
    print("", flush=True)
    print(f"产出: question.md={'✓' if (slot_ws/'question.md').exists() else '✗'} | gen.py={'✓' if gen_exists else '✗'} | solution.md={'✓' if (slot_ws/'solution.md').exists() else '✗'} | review.md={'✓' if (slot_ws/'review.md').exists() else '✗'}", flush=True)
    print(f"审核: 阶段1(题干)={status_q} | 阶段2·A(代码)={status_a} | 阶段2·B(文档)={status_b}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
