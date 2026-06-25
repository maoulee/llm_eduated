"""Paper assembler — per-slot question/solution → 排版 试卷.md(题面) + 答案解析.md。

通用版：大题/小题结构从 handoff 的 slots **推导**（保序按题型分组），任意卷通用。
- 大题(一/二/三…) + 小题(1,2,3…) 顺序编号，对齐原卷层级
- 题面只取 题干/题目/第N题(concept) 段，滤 参数/考察点/通过条件/REASONING 等内部脚手架
- 解析取 求解过程/答案/干扰项/推导，去 参数 echo
- 残留题号头/一级标题一律清除

入口: assemble_paper(handoff_path, questions_dir, title) —— 供 trigger_generation 自动调用。"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root for core_new import

import yaml

from core_new.doc_pipeline.question_validator import validate_question_structure

CN_NUM = "一二三四五六七八九十"


def _qtype(slot: dict) -> str:
    """题型分类。优先用显式 `题型` 字段；否则从 question_type + examination_mode 关键词推断。"""
    explicit = slot.get("题型") or slot.get("question_category")
    if explicit:
        return str(explicit)
    qt = (slot.get("question_type") or "").lower()
    em = slot.get("examination_mode") or ""
    if qt == "single_choice" or "单选" in em or "选择题" in em:
        return "单项选择题"
    if "判断" in em:
        return "判断题"
    if "填空" in em:
        return "填空题"
    if "设计" in em:
        return "设计题"
    if "应用" in em:
        return "应用题"
    if "计算" in em:
        return "计算题"
    if "简答" in em:
        return "简答题"
    return "综合题"


def derive_sections(slots: list) -> list:
    """保序按题型分组 → [(大题标题, [slot_ids])]。题型相同的连续 slot 合为一大题。"""
    groups = []  # [(qtype, [sids], [scores])]
    for s in slots:
        qt = _qtype(s)
        sid = str(s.get("slot_id", ""))
        score = s.get("score") or 0
        if groups and groups[-1][0] == qt:
            groups[-1][1].append(sid)
            groups[-1][2].append(score)
        else:
            groups.append([qt, [sid], [score]])
    out = []
    for i, (qtype, sids, scores) in enumerate(groups):
        total = sum(scores)
        n = len(sids)
        cn = CN_NUM[i] if i < len(CN_NUM) else str(i + 1)
        if n > 1 and scores and len(set(scores)) == 1:
            title = f"{cn}、{qtype}（{n}×{scores[0]}={total}分）"
        else:
            title = f"{cn}、{qtype}（{total}分）"
        out.append((title, sids))
    return out


def _read_slot(questions_dir: Path, sid: str, kind: str) -> str:
    """读单层(拆回)或双层(DocPipeline)产物。kind = question | solution。"""
    for p in (questions_dir / sid / f"{kind}.md", questions_dir / sid / sid / f"{kind}.md"):
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return f"_(缺失 {sid}/{kind})_"


def _keep_sections(t: str, keep_kws: list) -> str:
    """按 ^## 分段，保留 header 含 keep_kws 或 '第N题'(concept 批量格式) 的段
    （去 ## header 行，只要正文）。滤内部段。残留题号头/一级标题一律清除（含 fallback）。"""
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


def clean_question(t: str) -> str:
    return _keep_sections(t, ["题干", "题目", "设问", "问题"])


def clean_solution(t: str) -> str:
    return _keep_sections(t, ["求解", "解答", "答案", "解析", "过程", "推导", "干扰项", "说明"])


def assemble_paper(handoff_path, questions_dir: Path, title: str = "期末试卷") -> dict:
    """读 handoff 推导结构 + per-slot 产物 → 写 试卷.md + 答案解析.md。返回统计。"""
    slots = yaml.safe_load(Path(handoff_path).read_text(encoding="utf-8")).get("slots", [])
    sections = derive_sections(slots)
    sid_qtype = {str(s.get("slot_id", "")): _qtype(s) for s in slots}  # L1 结构校验用
    paper = [f"# {title}\n"]
    ans = [f"# {title} · 答案与解析\n"]
    total_q = 0
    malformed = []
    for sec_title, sids in sections:
        paper.append(f"\n## {sec_title}\n")
        ans.append(f"\n## {sec_title}\n")
        for i, sid in enumerate(sids, 1):
            total_q += 1
            q = clean_question(_read_slot(questions_dir, sid, "question"))
            ok, reason = validate_question_structure(q, sid_qtype.get(sid, ""))
            if not ok:
                malformed.append({"slot": sid, "reason": reason})
                q = f"> ⚠️ **[L1 结构校验未过：{reason}]**\n\n" + q
            paper.append(f"\n### {i}.\n\n{q}\n")
            ans.append(f"\n### {i}.\n\n{clean_solution(_read_slot(questions_dir, sid, 'solution'))}\n")
    questions_dir = Path(questions_dir)
    (questions_dir / "试卷.md").write_text("\n".join(paper), encoding="utf-8")
    (questions_dir / "答案解析.md").write_text("\n".join(ans), encoding="utf-8")
    missing = "".join(paper).count("_(缺失")
    return {"小题数": total_q, "缺失": missing, "题面字数": len("".join(paper)),
            "解析字数": len("".join(ans)), "结构校验未过": malformed}


if __name__ == "__main__":
    _handoff = Path(sys.argv[1])
    _qdir = Path(sys.argv[2])
    _title = sys.argv[3] if len(sys.argv) > 3 else "期末试卷"
    _stats = assemble_paper(_handoff, _qdir, _title)
    print(f"已生成: {_qdir}/试卷.md + {_qdir}/答案解析.md  →  {_stats}")
