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
from core_new.doc_pipeline.stem_contract import (
    META_BULLET_KW as _META_BULLET_KW,
    PRE_STEM_HEADER_KW as _PRE_STEM_KW,
    STOP_HEADER_KW as _STOP_KW,
)

CN_NUM = "一二三四五六七八九十"


class AssemblyValidationError(ValueError):
    """Raised when the exam paper would contain unsafe or malformed content."""


_ANSWER_LINE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?\s*(?:答案|正确答案|参考答案|解析|理由|设计说明|通过条件|参数|考察点|REASONING)\s*(?:\*\*)?\s*[：:：]?.*$",
    re.I,
)
_INLINE_LEAK_PATTERNS = [
    re.compile(r"[（(]\s*(?:正确答案|正确选项|正确结果|正确|答案|解析|理由|误算|错误路径|干扰)\s*[：:：][^）)]*[）)]"),
    re.compile(r"[（(]\s*(?:正确|误算|错误|干扰)[^）)]*[）)]"),
    re.compile(r"\s+[√×✓✗✔✘]\s*$"),
    re.compile(r"\s*(?:--|——|：|:)\s*(?:正确答案|正确选项|正确结果|答案)\s*[A-D0-9一二三四五六七八九十].*$"),
]
_LEAK_SCAN_RE = re.compile(
    r"(?:\*\*)?\s*(?:答案|正确答案|参考答案|正确选项|正确结果|解析|理由)\s*(?:\*\*)?\s*[：:]|"
    r"(?:正确答案|正确选项|正确结果)\s*(?:为|是)|"
    r"(?<![A-Za-z0-9])[√✓✗✔✘](?![A-Za-z0-9])|[（(]\s*×\s*[)）]|"
    r"[（(]\s*(?:正确|误算|错误|干扰|答案|解析|理由)\s*[：:：]?|"
    r"\|\s*\*\*[A-D]\*\*\s*\|\s*正确答案",
    re.I,
)
_INTERNAL_TABLE_HEADER_RE = re.compile(r"^\s*\|.*(?:错误类型|正误|正确结果|错误结果|干扰项|误算|错误路径).*\|\s*$")


def _qtype(slot: dict) -> str:
    """题型分类。优先用显式 `题型` 字段；否则从 question_type + examination_mode 关键词推断。"""
    explicit = slot.get("题型") or slot.get("question_category")
    if explicit:
        return str(explicit)
    qt = (slot.get("question_type") or "").lower()
    em = slot.get("examination_mode") or ""
    # 多选优先于单选（多项选择含"选择"，更具体；408 标准题型）
    if "多选" in em or "多项选择" in em or qt == "multiple_choice":
        return "多项选择题"
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


# 三态机：从 question.md 抽题干段。
#   STOP     = 题干之后的脚手架/求解段（场景规则/通过条件/参数/解析/答案…）→ 截断
#   PRE_STEM = 题干"之前"可能出现的设计意图段（设计意图/考察意图/设计说明…）→ 跳过不停止
#   其余     = 题干本身（题干/题目/选项/第N题）或 H1 题目标题 → 保留
# 顺序变体：有的"设计意图在前、题干在后"(Q7)，有的"题干在前、设计意图在后"(Q28)，
# 三态机都能正确剥离设计意图、保留题干、在场景规则处停。
def _kw_alt(kws):
    """从关键词元组构造 'a|b|c' 正则片段（逐字转义）。"""
    return "|".join(re.escape(k) for k in kws)


# 三个黑名单均派生自 stem_contract（单一事实源）：新增一种泄漏词，只改 stem_contract.py 一处，
# clean_question（剥离）与 format_fix_paper（整体兜底）同步生效，无需多处补丁。
_STOP_HEADER_RE = re.compile(_kw_alt(_STOP_KW))
# PRE_STEM：设计/元数据段，可能在题干前（考察说明/设计意图）也可能在后（评分/陷阱说明）。
# 跳过整段（到下个 H2 续读）——两种顺序都安全：在前则跳过到题干，在后则题干已收。
_PRE_STEM_HEADER_RE = re.compile(_kw_alt(_PRE_STEM_KW))
# 题干后内联残留的"考点/元数据"bullet（**XXX**：… / - XXX：…）——设计元数据，不是题面。
_META_BULLET_RE = re.compile(
    r"^\s*[-*]\s*\*{0,2}(?:" + _kw_alt(_META_BULLET_KW) + r"|K\d)\*{0,2}\s*[：:]"
)


def _cut_at_scaffold(t: str) -> str:
    """从 question.md 抽题干段：跳过设计意图、保留题干/选项/子问、在场景规则处截断。

    H3+（### 第N问 / 表格 / 正文）随当前段一起保留或跳过——只有 H1/H2 改变状态。
    """
    out: list[str] = []
    skip = False
    for line in t.splitlines():
        m = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line)
        if m and len(m.group(1)) <= 2:
            header = m.group(2)
            if _STOP_HEADER_RE.search(header):
                break
            skip = bool(_PRE_STEM_HEADER_RE.search(header))
            if skip:
                continue
        if skip:
            continue
        out.append(line)
    return "\n".join(out).strip()


def clean_question(t: str) -> str:
    stem = _cut_at_scaffold(t)
    if not stem:  # 极少见：整篇都是脚手架 → 退回按段保留
        stem = _keep_sections(t, ["题干", "题目", "设问", "问题", "选项"])
    stem = _strip_exam_leaks(stem)
    # 归一化（试卷题号由 assembler 给，去掉冗余/设计性/考点泄漏内容）：
    # 0) 解题"提示"剥离（> 提示：公式 / **提示**： / 句内（提示：…））——提示给思路/公式，不该进试卷
    stem = re.sub(r"(?m)^\s*>\s*\*{0,2}\s*提示.*$", "", stem)      # blockquote 提示行
    stem = re.sub(r"(?m)^\s*\*{0,2}\s*提示\s*[:：].*$", "", stem)  # **提示**：独立行
    stem = re.sub(r"[（(]\s*提示\s*[:：][^）)]*[）)]", "", stem)    # 句内（提示：…）括号
    # 1) 元数据 bullet（**考点**：/**知识点**：/**难度**：…）——设计元数据，不该进试卷
    lines = [ln for ln in stem.splitlines() if not _META_BULLET_RE.match(ln)]
    stem = "\n".join(lines)
    # 2) H1 题目标题（# 补码加减运算…）——命名考点、且与 assembler 的 ### i. 编号重复
    #    （试卷大标题由 assembler 单独给，题内 H1 一律剥）
    stem = re.sub(r"^\s*#\s+[^\n]+$", "", stem, flags=re.M)
    # 3) 裸"题干"/"题目：xxx"/"题目信息"/"选项" 冗余标题行（保留其后正文/选项）
    stem = re.sub(r"^\s*#{1,6}\s*题干\s*$", "", stem, flags=re.M)
    stem = re.sub(r"^\s*#{1,6}\s*题目(?:正文|描述|内容|信息|要求)?(?:\s*[：:].*|\s*[（(][^）)\n]*[)）])?\s*$", "", stem, flags=re.M)
    stem = re.sub(r"^\s*#{1,6}\s*(?:题目信息|题目描述|信息)\s*$", "", stem, flags=re.M)
    stem = re.sub(r"^\s*#{1,6}\s*选项(?:\s*[（(][^)\n]*[)）])?\s*$", "", stem, flags=re.M)
    # 4) 概念批次 H2 "第N题"（与 assembler 的 ### i. 重复；H3 子问 ### 第(N)题 保留）
    stem = re.sub(r"^\s*##\s+第\s*\d+\s*题\s*(?:[（(][^）)\n]*[)）])?\s*$", "", stem, flags=re.M)
    # 5) 分隔线、"**题干**："前缀
    stem = re.sub(r"^\s*-{3,}\s*$", "", stem, flags=re.M)
    stem = re.sub(r"(?m)^\*\*题干\*\*\s*[：:]\s*", "", stem)
    return _squeeze_blank(stem).strip()


def _squeeze_blank(t: str) -> str:
    """合并 3+ 连续空行为 2 个（选项段被剥头后常留多余空行）。"""
    return re.sub(r"\n{3,}", "\n\n", t)


def clean_solution(t: str) -> str:
    return _keep_sections(t, ["求解", "解答", "答案", "解析", "过程", "推导", "干扰项", "说明"])


def _strip_exam_leaks(text: str) -> str:
    """Remove answer-only lines and inline answer annotations from exam text.

    This is intentionally conservative: it strips common metadata/answer
    markers, then the caller scans the result and fails closed if anything
    answer-like remains.
    """
    out: list[str] = []
    skip_table = False
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            skip_table = False
            out.append(line)
            continue
        if _ANSWER_LINE_RE.match(stripped):
            continue
        if _INTERNAL_TABLE_HEADER_RE.match(stripped):
            skip_table = True
            continue
        if skip_table and stripped.startswith("|"):
            continue
        skip_table = False
        for pat in _INLINE_LEAK_PATTERNS:
            line = pat.sub("", line).rstrip()
        if line.strip():
            out.append(line)
    return "\n".join(out).strip()


def detect_exam_leaks(text: str) -> list[str]:
    """Return suspicious answer leakage lines in assembled exam text."""
    leaks: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        if _LEAK_SCAN_RE.search(stripped):
            leaks.append(f"L{i}: {stripped[:120]}")
    return leaks


def assemble_paper(handoff_path, questions_dir: Path, title: str = "期末试卷", *, strict: bool = True) -> dict:
    """读 handoff 推导结构 + per-slot 产物 → 写 试卷.md + 答案解析.md。返回统计。"""
    slots = yaml.safe_load(Path(handoff_path).read_text(encoding="utf-8")).get("slots", [])
    sections = derive_sections(slots)
    sid_qtype = {str(s.get("slot_id", "")): _qtype(s) for s in slots}  # L1 结构校验用
    paper = [f"# {title}\n"]
    ans = [f"# {title} · 答案与解析\n"]
    total_q = 0
    malformed = []
    leak_findings = []
    for sec_title, sids in sections:
        paper.append(f"\n## {sec_title}\n")
        ans.append(f"\n## {sec_title}\n")
        for i, sid in enumerate(sids, 1):
            total_q += 1
            q = clean_question(_read_slot(questions_dir, sid, "question"))
            ok, reason = validate_question_structure(q, sid_qtype.get(sid, ""))
            if not ok:
                malformed.append({"slot": sid, "reason": reason})
            leaks = detect_exam_leaks(q)
            if leaks:
                leak_findings.append({"slot": sid, "leaks": leaks[:5]})
            paper.append(f"\n### {i}.\n\n{q}\n")
            ans.append(f"\n### {i}.\n\n{clean_solution(_read_slot(questions_dir, sid, 'solution'))}\n")
    questions_dir = Path(questions_dir)
    if strict and (malformed or leak_findings):
        raise AssemblyValidationError(
            "试卷导出阻断："
            f"结构校验未过={malformed}; "
            f"疑似答案泄漏={leak_findings}"
        )
    (questions_dir / "试卷.md").write_text("\n".join(paper), encoding="utf-8")
    (questions_dir / "答案解析.md").write_text("\n".join(ans), encoding="utf-8")
    missing = "".join(paper).count("_(缺失")
    return {"小题数": total_q, "缺失": missing, "题面字数": len("".join(paper)),
            "解析字数": len("".join(ans)), "结构校验未过": malformed,
            "疑似答案泄漏": leak_findings}


if __name__ == "__main__":
    _handoff = Path(sys.argv[1])
    _qdir = Path(sys.argv[2])
    _title = sys.argv[3] if len(sys.argv) > 3 else "期末试卷"
    _stats = assemble_paper(_handoff, _qdir, _title)
    print(f"已生成: {_qdir}/试卷.md + {_qdir}/答案解析.md  →  {_stats}")
