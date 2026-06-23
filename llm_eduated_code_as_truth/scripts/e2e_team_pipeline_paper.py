"""E2E: 用 team_pipeline 跑完整试卷（复用已验证的 scheme-C handoff yaml）。

复用 interact 已产出的 paper_request.yaml（方案C，18 题），直接 trigger_generation →
DocPipeline → orchestrator graph → build_team_pipeline_graph（enable_team_pipeline=true），
测我们做的 team_pipeline 改进在整卷上的时间/质量。跳过 interact 重跑（已验证）。

用法: python scripts/e2e_team_pipeline_paper.py
"""
import asyncio
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
for _e in ("/zhaoshu/llm_eduated/.env", str(ROOT / ".env")):
    if Path(_e).exists():
        load_dotenv(_e)

from api.services.pipeline_trigger import trigger_generation
from core_new.doc_pipeline.pipeline_config import load_pipeline_config

SRC_YAML = ROOT / "workspace/f5ff5ba7a629/compose/paper_request.yaml"
OUT = ROOT / "docs/test_output/team_pipeline_paper" / time.strftime("%Y%m%dT%H%M%S")


async def main():
    cfg = load_pipeline_config()
    print(f"=== team_pipeline full-paper run | enable_team_pipeline="
          f"{cfg.params.features.get('enable_team_pipeline')} ===", flush=True)
    assert cfg.params.features.get("enable_team_pipeline"), "flag not on!"
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy(SRC_YAML, OUT / "paper_request.yaml")
    print(f"handoff: {SRC_YAML} → {OUT}", flush=True)

    t0 = time.time()
    milestones: dict[str, float] = {}

    def on_done(sid, status):
        dt = time.time() - t0
        milestones[sid] = dt
        n = len(milestones)
        print(f"[{dt:6.1f}s] ({n}/18) {sid}: {status}", flush=True)

    progress = await trigger_generation(
        "team_e2e", OUT / "paper_request.yaml", OUT,
        provider=os.getenv("E2E_PROVIDER", "glm5.2_anthropic"),
        on_slot_complete=on_done,
    )
    dt = time.time() - t0
    done = sum(1 for s in progress.slot_status.values() if s["status"] == "completed")
    failed = sum(1 for s in progress.slot_status.values() if s["status"] == "failed")
    print(f"\n=== TOTAL {dt:.0f}s ({dt/60:.1f} min) | completed={done}/{progress.total_slots} "
          f"failed={failed} | avg {dt/max(done,1):.0f}s/q ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
