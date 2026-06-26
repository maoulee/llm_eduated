#!/usr/bin/env python3
"""生成"考点对齐"卷（Entry D）：从一个 paper_request.yaml handoff 跑 trigger_generation。

用法:
  python scripts/gen_kaodian_paper.py --handoff workspace/xxx/compose/paper_request.yaml --tag data_structure
"""
import argparse
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

from api.services.pipeline_trigger import trigger_generation  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--handoff", required=True, help="paper_request.yaml path")
    ap.add_argument("--tag", default="kaodian", help="output dir tag")
    ap.add_argument("--provider", default=os.getenv("E2E_PROVIDER", "glm5.2_anthropic"))
    args = ap.parse_args()

    src = Path(args.handoff).resolve()
    assert src.exists(), f"handoff not found: {src}"
    out = ROOT / "docs/test_output" / f"kaodian_{args.tag}" / time.strftime("%Y%m%dT%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, out / "paper_request.yaml")
    print(f"=== 考点对齐生成 | handoff={src.name} -> {out} | provider={args.provider} ===", flush=True)

    t0 = time.time()

    def on_done(sid: str, status: str) -> None:
        dt = time.time() - t0
        print(f"[{dt:6.1f}s] {sid}: {status}", flush=True)

    progress = await trigger_generation(
        f"kaodian_{args.tag}", out / "paper_request.yaml", out,
        provider=args.provider, on_slot_complete=on_done,
    )
    dt = time.time() - t0
    done = sum(1 for s in progress.slot_status.values() if s["status"] == "completed")
    failed = sum(1 for s in progress.slot_status.values() if s["status"] == "failed")
    print(f"\n=== TOTAL {dt:.0f}s ({dt/60:.1f} min) | completed={done}/{progress.total_slots} failed={failed} ===", flush=True)
    print(f"=== OUT: {out} ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
