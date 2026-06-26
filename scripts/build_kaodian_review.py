"""为"考点对齐"卷生成 考点对照.md（每题：原卷知识点 claim + 考法 + 新题题干摘要）。

用法:
  python scripts/build_kaodian_review.py \
    --handoff OUT/paper_request.yaml --questions OUT/questions \
    --reference data/xxx.md --subject 数据结构
"""
import argparse
import sys
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def first_line(qdir: Path, sid: str) -> str:
    for p in (qdir / sid / "question.md", qdir / sid / sid / "question.md"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").strip().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return line[:60]
    return "(缺)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--handoff", required=True)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--reference", default="")
    ap.add_argument("--subject", default="")
    args = ap.parse_args()

    hf = yaml.safe_load(Path(args.handoff).read_text(encoding="utf-8"))
    qdir = Path(args.questions)
    ref = args.reference or hf.get("source", {}).get("reference_paper", "(见 handoff)")
    subj = args.subject or (hf.get("assessment", {}).get("subjects") or ["?"])[0]
    slots = hf["slots"]

    lines = [
        f"# 考点对照 · {subj} · 考点对齐(Entry D)\n",
        f"- **原卷(参考)**: `{ref}`",
        f"- **新卷**: {qdir}/试卷.md\n",
        f"- 共 {len(slots)} 题，逐题锚定原卷每题知识点，考察角度可换\n",
        "| 题号 | 题型 | 原卷知识点(claim) | 考法 | 新题题干摘要 |",
        "|---|---|---|---|---|",
    ]
    for s in slots:
        sid = s.get("slot_id", "?")
        qt = s.get("题型") or s.get("question_type") or "?"
        kp = s.get("primary_target_name", "?")
        em = (s.get("examination_mode") or "").replace("\n", " ")[:30]
        stem = first_line(qdir, sid).replace("|", "/")
        lines.append(f"| {sid} | {qt} | {kp} | {em} | {stem} |")
    out = qdir / "考点对照.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", out, "rows:", len(slots))


if __name__ == "__main__":
    main()
