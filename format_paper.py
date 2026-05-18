"""Format generated questions into real 408 exam paper style."""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

# Load Q12-Q22, Q43
with open("docs/test_composition_result.json", encoding="utf-8") as f:
    full_data = json.load(f)
review = full_data.get("final_review", {})

# Load slot results (Q44, Q45, etc.)
with open("docs/slot_composition_result.json", encoding="utf-8") as f:
    slot_data = json.load(f)
slot_review = slot_data.get("final_review", {})

questions = list(full_data.get("final_questions", []))
for sq in slot_data.get("final_questions", []):
    if sq.get("stem"):
        for i, q in enumerate(questions):
            if q.get("slot_id") == sq.get("slot_id"):
                questions[i] = sq
                break
        else:
            questions.append(sq)

sc_qs = sorted(
    [q for q in questions if int(q.get("slot_id", "Q99")[1:]) < 43 and q.get("stem")],
    key=lambda x: x.get("slot_id", ""),
)
comp_qs = sorted(
    [q for q in questions if int(q.get("slot_id", "Q99")[1:]) >= 43 and q.get("stem")],
    key=lambda x: x.get("slot_id", ""),
)

lines = []

# ==================== TITLE ====================
lines.append("# 408计算机组成原理 模拟试卷")
lines.append("")
lines.append(
    "> 本试卷涵盖计算机组成原理选择题（第1-11题）和综合应用题（第43-45题），难度对标全国统考408真题。"
)
lines.append("")

# ==================== PART 1: QUESTIONS ====================
lines.append("---")
lines.append("")
lines.append("## 第一部分 选择题（每题2分，共22分）")
lines.append("")
lines.append("下列每题给出的四个选项中，只有一个选项最符合题目要求。")
lines.append("")

for idx, q in enumerate(sc_qs, 1):
    sid = q.get("slot_id", "?")
    stem = q.get("stem", "").strip()
    lines.append(f"**{idx}.** ({sid}) {stem}")
    lines.append("")
    for opt in ["A", "B", "C", "D"]:
        val = q.get(f"option_{opt}", "").strip()
        lines.append(f"&emsp;&emsp;{opt}. {val}")
    lines.append("")

lines.append("---")
lines.append("")
lines.append("## 第二部分 综合应用题")
lines.append("")

for q in comp_qs:
    sid = q.get("slot_id", "?")
    stem = q.get("stem", "").strip()
    sub_qs = q.get("sub_questions", [])

    lines.append(f"**{sid}.** {stem}")
    lines.append("")

    if sub_qs:
        for si, sq in enumerate(sub_qs, 1):
            if isinstance(sq, str):
                lines.append(f"({si}) {sq}")
                lines.append("")
    lines.append("")

# ==================== PART 2: ANSWERS ====================
lines.append("---")
lines.append("")
lines.append("## 参考答案")
lines.append("")
lines.append("### 选择题")
lines.append("")

header = "| 题号 | " + " | ".join([str(i) for i in range(1, len(sc_qs) + 1)]) + " |"
sep = "|------|" + "|".join(["----" for _ in sc_qs]) + "|"
vals = "| 答案 | " + " | ".join([q.get("correct_answer", "?") for q in sc_qs]) + " |"
lines.append(header)
lines.append(sep)
lines.append(vals)
lines.append("")

lines.append("### 综合应用题")
lines.append("")
for q in comp_qs:
    sid = q.get("slot_id", "?")
    answer = q.get("correct_answer", q.get("answer", ""))
    if isinstance(answer, dict):
        lines.append(f"**{sid}：**")
        for k, v in sorted(answer.items()):
            lines.append(f"- {k}: {v}")
    elif answer and answer not in ("无选项（综合应用题）", "无"):
        lines.append(f"**{sid}：** {answer}")
    else:
        lines.append(f"**{sid}：** 见详细解析")
    lines.append("")

# ==================== PART 3: EXPLANATIONS ====================
lines.append("---")
lines.append("")
lines.append("## 答案解析")
lines.append("")
lines.append("### 选择题解析")
lines.append("")

for idx, q in enumerate(sc_qs, 1):
    sid = q.get("slot_id", "?")
    answer = q.get("correct_answer", "?")
    explanation = q.get("explanation", "").strip()
    lines.append(f"**{idx}.({sid}) 答案：{answer}**")
    lines.append("")
    lines.append(explanation)
    lines.append("")

lines.append("### 综合应用题解析")
lines.append("")

for q in comp_qs:
    sid = q.get("slot_id", "?")
    explanation = q.get("explanation", "").strip()
    answer = q.get("correct_answer", q.get("answer", ""))
    rubric = q.get("rubric", {})

    # Get score
    score = "?"
    for sr in review.get("slot_reviews", []):
        if sr.get("slot_id") == sid:
            score = sr.get("quality_score", "?")
    for sr in slot_review.get("slot_reviews", []):
        if sr.get("slot_id") == sid:
            score = sr.get("quality_score", "?")

    lines.append(f"**{sid} (审核评分：{score}/10)**")
    lines.append("")

    if explanation:
        lines.append(explanation)
    elif rubric:
        lines.append("**评分标准与解题要点：**")
        lines.append("")
        for k, v in sorted(rubric.items()):
            if k.startswith("point_") and isinstance(v, str):
                lines.append(f"- {v}")
            elif k == "评分要点概述":
                lines.append(f"- **总评**：{v}")
        lines.append("")
        if isinstance(answer, dict):
            lines.append("**参考答案：**")
            for k, v in sorted(answer.items()):
                lines.append(f"- {k}: {v}")

    lines.append("")

# ==================== PART 4: KNOWLEDGE POINTS ====================
lines.append("---")
lines.append("")
lines.append("## 考点与设计分析")
lines.append("")
lines.append("### 选择题考点")
lines.append("")

for idx, q in enumerate(sc_qs, 1):
    sid = q.get("slot_id", "?")
    kps = q.get("knowledge_points", "").strip()
    trap = q.get("trap_description", "").strip()
    difficulty = q.get("difficulty_self_assessment", "?")

    lines.append(f"**{idx}.({sid})** 难度：{difficulty}/5")
    lines.append(f"- 考点：{kps}")
    if trap:
        lines.append(f"- 陷阱设计：{trap[:200]}")
    lines.append("")

lines.append("### 综合应用题考点与设计意图")
lines.append("")

for q in comp_qs:
    sid = q.get("slot_id", "?")
    kps = q.get("knowledge_points", "").strip()
    difficulty = q.get("difficulty_self_assessment", "?")
    design_intent = q.get("design_intent", {})
    param_notes = q.get("parameter_notes", "").strip()

    lines.append(f"**{sid}** 难度：{difficulty}/5")
    lines.append(f"- 考点：{kps}")
    if param_notes:
        lines.append(f"- 参数设计说明：{param_notes[:500]}")
    if isinstance(design_intent, dict):
        for k, v in design_intent.items():
            if isinstance(v, str) and len(v) > 10 and k != "trap_design":
                label = k.replace("_", " ")
                lines.append(f"- {label}：{v[:300]}")
    lines.append("")

paper_text = "\n".join(lines)
with open("docs/exam_paper_final.md", "w", encoding="utf-8") as f:
    f.write(paper_text)

print(f"Formatted paper saved: {len(sc_qs)} SC + {len(comp_qs)} Comp questions")
print(f"Total lines: {len(lines)}")
