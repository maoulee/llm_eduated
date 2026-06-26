#!/usr/bin/env python3
"""Entry D (考点对应) 全自动：interact agent 读参考卷 → 逐题对齐 handoff → 生成 → 装订。

用法: python scripts/gen_entry_d_paper.py --reference data/计算机组成原理A卷_题干与表格.md --tag coA
依赖: run_api.py 在 localhost:3001 运行中。
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import requests  # noqa: E402

API = "http://localhost:3001/api/v2/interact"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--provider", default="glm5.2_anthropic")
    args = ap.parse_args()
    tag, ref = args.tag, args.reference

    # 1. create session
    sid = requests.post(
        f"{API}/sessions",
        json={"provider": args.provider, "thinking": True, "ui_mode": "api", "user_id": f"entryd_{tag}"},
        timeout=60,
    ).json()["session_id"]
    print(f"[{tag}] session={sid}", flush=True)

    # 2. discuss: read reference + 考点对应 (逐题锚定)
    msg = (
        f"请参考 {ref} 出一套【考点对应】的卷——逐题锚定原卷每道题的知识点（1-to-1），"
        f"考察角度可换不同切面，题干全新产出。请先 read_file 读卷、提取每题知识点，"
        f"再生成 paper_request.yaml 交接文档。"
    )
    t = requests.post(f"{API}/sessions/{sid}/turn", json={"message": msg, "intent": "discuss"}, timeout=300).json()
    print(f"[{tag}] discuss: state={t.get('session_state')} has_draft={t.get('has_draft')} has_result={t.get('has_result')}", flush=True)

    # 若还没产出 handoff YAML，再推一句
    if not t.get("has_result"):
        t2 = requests.post(
            f"{API}/sessions/{sid}/turn",
            json={"message": "请直接生成 paper_request.yaml 交接文档（逐题锚定原卷每题知识点），进入出题。", "intent": "discuss"},
            timeout=300,
        ).json()
        print(f"[{tag}] discuss2: has_result={t2.get('has_result')}", flush=True)

    # 3. confirm_handoff → 触发生成
    tc = requests.post(
        f"{API}/sessions/{sid}/turn",
        json={"message": "确认考点对应方案，开始出题", "intent": "confirm_handoff"},
        timeout=300,
    ).json()
    print(f"[{tag}] confirm: state={tc.get('session_state')} has_result={tc.get('has_result')}", flush=True)

    # 4. poll generation
    last = None
    for i in range(200):
        try:
            p = requests.get(f"{API}/sessions/{sid}/pipeline-progress", timeout=30).json()
        except Exception:
            time.sleep(15); continue
        status = p.get("status")
        slots = p.get("slots") or {}
        done = sum(1 for s in slots.values() if s.get("status") == "completed")
        fail = sum(1 for s in slots.values() if s.get("status") == "failed")
        key = (status, done, fail)
        if key != last:
            print(f"[{tag}] poll {i}: {status} {done}/{p.get('total_slots', 0)} fail={fail}", flush=True)
            last = key
        if status in ("completed", "partial", "failed"):
            break
        time.sleep(15)

    # 5. 装订 试卷.md/答案解析.md + 考点对照.md
    ws_q = ROOT / "workspace" / sid / "questions"
    handoff = ROOT / "workspace" / sid / "compose" / "paper_request.yaml"
    try:
        if handoff.exists() and ws_q.is_dir():
            from api.services.paper_assembler import assemble_paper
            stats = assemble_paper(handoff, ws_q, f"{Path(ref).stem} · 考点对齐(Entry D)")
            print(f"[{tag}] assemble: {stats}", flush=True)
            subprocess.run(
                [sys.executable, "scripts/build_kaodian_review.py",
                 "--handoff", str(handoff), "--questions", str(ws_q),
                 "--reference", ref, "--subject", "计算机组成原理"],
                check=False, cwd=str(ROOT),
            )
    except Exception as e:
        print(f"[{tag}] assemble err: {e}", flush=True)
    print(f"[{tag}] DONE -> workspace/{sid}", flush=True)


if __name__ == "__main__":
    main()
