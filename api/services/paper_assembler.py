#!/usr/bin/env python3
"""Paper assembler — per-slot question/solution → 排版好的 试卷.md(题面) + 答案解析.md。
约定格式：大题(一/二/三/四/五) + 小题(1,2,3…) 顺序编号；题面/解析分两份；一题一解析；
滤工作段(四选项汇总/PARAMS/批量残留头)。

用法: paper_assembler.py <questions_dir> [subject_title]
结构 spec 当前内嵌（应来自 paper plan/handoff 的 sections 字段）。"""
import sys
import re
from pathlib import Path

OUT = Path(sys.argv[1])
TITLE = sys.argv[2] if len(sys.argv) > 2 else "计算机组成原理 期末试卷（系统生成）"

# 结构 spec：大题 -> (标题, 分值, [slot_ids])。来自 paper plan，这里内嵌 V6 合肥师范方案C。
SECTIONS = [
    ("一、单项选择题", "15×2=30分", [f"Q{n:02d}" for n in range(1, 16)]),
    ("二、填空题", "10分", ["Q16"]),
    ("三、简答题", "5×6=30分", [f"Q{n:02d}" for n in range(17, 22)]),
    ("四、应用题", "10分", ["Q22"]),
    ("五、设计题", "2×10=20分", ["Q23", "Q24"]),
]


def read_slot(sid, kind):
    """kind = question | solution。读单层(拆回)或双层(DocPipeline)产物。"""
    for p in (OUT / sid / f"{kind}.md", OUT / sid / sid / f"{kind}.md"):
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return f"_(缺失 {sid}/{kind})_"


def keep_sections(t, keep_kws):
    """按 ^## 分段，保留 header 含 keep_kws 或 '第N题'(concept 批量格式) 的段
    （去 ## header 行，只要正文）。滤内部段（参数/考察点/通过条件/REASONING）。
    残留题号头/一级标题一律清除（含 fallback）。"""
    parts = re.split(r"(?=^## )", t, flags=re.M)
    kept = []
    for p in parts:
        m = re.match(r"^## (.+)", p.strip())
        if not m:
            continue
        h = m.group(1)
        if any(k in h for k in keep_kws) or re.match(r"第\s*\d+\s*题", h):
            body = re.sub(r"^## .+\n", "", p.strip(), count=1).strip()
            if body:
                kept.append(body)
    out = "\n\n".join(kept) if kept else t
    out = re.sub(r"^##+ 第\s*\d+\s*题(解析)?\s*$", "", out, flags=re.M)
    out = re.sub(r"^# .*题.*$", "", out, flags=re.M)
    return out.strip()


def clean_question(t):
    # 题面：只要题干/题目/设问段（含选项/空格），去内部 参数/考察点/通过条件
    return keep_sections(t, ["题干", "题目", "设问", "问题"])


def clean_solution(t):
    # 解析：求解过程/答案/干扰项/推导，去 参数 echo
    return keep_sections(t, ["求解", "解答", "答案", "解析", "过程", "推导", "干扰项", "说明"])


paper = [f"# {TITLE}\n"]
ans = [f"# {TITLE} · 答案与解析\n"]
total_q = 0
for title, score, sids in SECTIONS:
    paper.append(f"\n## {title}（{score}）\n")
    ans.append(f"\n## {title}（{score}）\n")
    for i, sid in enumerate(sids, 1):
        total_q += 1
        paper.append(f"\n### {i}.\n\n{clean_question(read_slot(sid, 'question'))}\n")
        ans.append(f"\n### {i}.\n\n{clean_solution(read_slot(sid, 'solution'))}\n")

Path(OUT / "试卷.md").write_text("\n".join(paper), encoding="utf-8")
Path(OUT / "答案解析.md").write_text("\n".join(ans), encoding="utf-8")
missing = "".join(paper).count("_(缺失")
print(f"已生成: {OUT}/试卷.md + {OUT}/答案解析.md")
print(f"小题数: {total_q} | 缺失: {missing}")
print(f"题面字数: {len(''.join(paper))} | 解析字数: {len(''.join(ans))}")
