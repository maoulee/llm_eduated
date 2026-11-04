#!/usr/bin/env python3
"""组卷测试：读 paper_request.yaml，用 TeamPipeline（常驻团队）处理整张试卷。

验证团队持久化（路径 B：编排层搬运黑板）：
  - 一个 TeamPipeline 实例 = 一张试卷 = 一个前端 session。
  - scheduler/gateway 全卷复用，不重新拉起。
  - 跨题记忆：paper_state.md（黑板），design_direct 注入（软提示去重）。
  - 单题工作记忆仍每题 clear（防 token 膨胀）。

四类型分发：
  概念题(complexity=conceptual) → concept_creator 批量
  选择题(single_choice)         → design_direct → write_gen → 派生干扰项 → dual_review
  综合题(comprehensive K3)      → design_direct → write_gen → write_solution → dual_review
  融合题(comprehensive K4)      → 同综合题，但 design_direct 触发考点融合
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

import yaml
from core_new.llm_gateway import get_gateway
from core_new.doc_pipeline.scheduler import DocScheduler
from core_new.doc_pipeline.config import ROLE_PARAMS
from core_new.doc_pipeline.team_pipeline import TeamPipeline

# 各 agent 策略（新四角色未进 pipeline.yaml，运行时注入）
ROLE_PARAMS["design_direct"] = {"max_tokens": 16000, "max_attempts": 4, "multi_turn": True, "enable_thinking": True}
ROLE_PARAMS["write_gen"] = {"max_tokens": 12000, "max_attempts": 8, "multi_turn": True, "enable_thinking": True}
ROLE_PARAMS["write_solution"] = {"max_tokens": 8000, "max_attempts": 4, "multi_turn": True, "enable_thinking": True}
ROLE_PARAMS["dual_review"] = {"max_tokens": 16000, "max_attempts": 3, "multi_turn": True, "enable_thinking": True}
ROLE_PARAMS["concept_creator"] = {"max_tokens": 8000, "max_attempts": 3, "multi_turn": True, "enable_thinking": True}
ROLE_PARAMS["review"] = {"max_tokens": 6000, "max_attempts": 3, "multi_turn": True, "enable_thinking": True}

WS = Path("/tmp/compose_test4")
PAPER_REQUEST = ROOT / "docs/compose/paper_request_test4.yaml"


def _load_slots():
    pr = yaml.safe_load(PAPER_REQUEST.read_text(encoding="utf-8"))
    return pr.get("slots", []), pr.get("teacher_preferences", {})


async def main():
    slots, prefs = _load_slots()
    WS.mkdir(parents=True, exist_ok=True)
    for f in WS.glob("*"):
        if f.is_dir():
            for sf in f.glob("*"):
                sf.unlink()
        elif f.is_file():
            f.unlink()  # 清掉旧 paper_state.md

    # ── 团队持久化：一个 TeamPipeline 实例 = 一张试卷 ──
    gw = get_gateway("glm5.2_anthropic")
    sched = DocScheduler(gateway=gw, workspace=str(WS), enable_thinking=True)
    team = TeamPipeline(sched, WS, paper_id="test4")
    gw_id = id(gw)
    sched_id = id(sched)
    print(f"模型: glm-5.2 | 共 {len(slots)} 个 slot | workspace: {WS}", flush=True)
    print(f"团队实例: scheduler={sched_id} gateway={gw_id}（全卷复用，不重新拉起）\n", flush=True)

    # 分发
    concept_slots = [s for s in slots if s.get("complexity") == "conceptual"]
    calc_slots = [s for s in slots if s.get("complexity") != "conceptual"]

    timings: dict[str, float] = {}
    total_start = time.monotonic()
    results: list[dict] = []

    # 概念题批量（先做，team 持续待命）
    if concept_slots:
        r = await team.run_concept_batch(concept_slots, timings)
        results.append(r)

    # 计算题（选择/综合/融合）逐个做，team 持续待命，跨题记忆靠 paper_state.md
    for s in calc_slots:
        kd = s.get("k_dominant", "")
        qtype = s.get("question_type", "")
        if qtype == "single_choice":
            label = f"选择题({s['slot_id']})"
        elif kd in ("K4", "K5") or s.get("target_difficulty", 0) >= 4:
            label = f"融合题({s['slot_id']},K4)"
        else:
            label = f"综合题({s['slot_id']},K3)"
        r = await team.run_question(s, label, timings)
        results.append(r)

    # ── 验证：团队实例未重建 ──
    assert id(team.scheduler) == sched_id, "scheduler 被重建了！"
    assert id(team.scheduler.gateway) == gw_id, "gateway 被重建了！"

    # 汇总
    total = time.monotonic() - total_start
    print("\n" + "=" * 60, flush=True)
    print("组卷测试汇总", flush=True)
    print("=" * 60, flush=True)
    for name, dt in timings.items():
        print(f"  {name:28s} {dt:6.0f}s", flush=True)
    print(f"  {'总耗时':28s} {total:6.0f}s ({total/60:.1f}min)", flush=True)

    # 团队黑板（跨题记忆）
    print("\n团队黑板 paper_state.md：", flush=True)
    print(team.read_board(), flush=True)

    # 产出齐全度
    print("各 slot 产出:", flush=True)
    for s in slots:
        sid = s["slot_id"]
        sw = WS / sid
        if s.get("complexity") == "conceptual":
            print(f"  {sid}: question.md={'✓' if (sw/'question.md').exists() else '✗'} solution.md={'✓' if (sw/'solution.md').exists() else '✗'} review.md={'✓' if (sw/'review.md').exists() else '✗'}", flush=True)
        else:
            print(f"  {sid}: question.md={'✓' if (sw/'question.md').exists() else '✗'} gen.py={'✓' if (sw/'gen.py').exists() else '✗'} solution.md={'✓' if (sw/'solution.md').exists() else '✗'} review.md={'✓' if (sw/'review.md').exists() else '✗'}", flush=True)

    print(f"\n✓ 团队持久化验证：scheduler({sched_id})/gateway({gw_id}) 全卷未重建", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
