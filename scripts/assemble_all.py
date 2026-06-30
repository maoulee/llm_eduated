#!/usr/bin/env python3
"""批量装订考点卷：对每个 run 目录跑 assemble_paper(strict) → 试卷.md + 答案解析.md。

用法:
  # 装订单套
  python scripts/assemble_all.py docs/test_output/kaodian_full_计组1卷/20260626T221639 --title "计算机组成原理·期末试卷"
  # 装订多套（自动取每个 tag 下的最新时间戳子目录）
  python scripts/assemble_all.py --tags kaodian_full_计组1卷:计算机组成原理试卷 kaodian_full_试卷A卷:数据结构试卷
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.services.paper_assembler import assemble_paper, AssemblyValidationError  # noqa: E402


def _latest_run(tag: str) -> Path | None:
    base = ROOT / "docs/test_output" / tag
    if not base.is_dir():
        return None
    runs = sorted([p for p in base.iterdir() if p.is_dir() and p.name[:8].isdigit()])
    return runs[-1] if runs else None


def assemble_one(run: Path, title: str, *, strict: bool = True) -> dict:
    handoff = run / "paper_request.yaml"
    qdir = run / "questions"
    return assemble_paper(handoff, qdir, title, strict=strict)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", nargs="?", help="单个 run 目录（装订单套）")
    ap.add_argument("--title", default="期末试卷", help="试卷标题（单套模式）")
    ap.add_argument("--tags", help="多套模式：tag:title tag:title ...（空格分隔）")
    ap.add_argument("--no-strict", action="store_true", help="宽松模式（不阻断泄漏）")
    args = ap.parse_args()

    strict = not args.no_strict

    if args.tags:
        specs = []
        for part in args.tags.split():
            tag, _, title = part.partition(":")
            specs.append((tag, title or tag))
        results = []
        for tag, title in specs:
            run = _latest_run(tag)
            if not run:
                print(f"[SKIP] {tag}: 无 run 目录")
                continue
            try:
                s = assemble_one(run, title, strict=strict)
                print(f"[OK]   {tag} -> {run.name} | 小题={s['小题数']} 缺失={s['缺失']} "
                      f"未过={len(s['结构校验未过'])} 泄漏={len(s['疑似答案泄漏'])}")
                results.append((tag, s))
            except AssemblyValidationError as e:
                print(f"[FAIL] {tag}: {str(e)[:300]}")
                results.append((tag, {"error": str(e)[:200]}))
        print(f"\n=== 装订 {len(results)} 套 ===")
        return

    run = Path(args.run).resolve()
    s = assemble_one(run, args.title, strict=strict)
    print(f"[OK] {run.name} | {s}")


if __name__ == "__main__":
    main()
