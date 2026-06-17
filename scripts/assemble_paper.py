#!/usr/bin/env python3
"""把所有 slot 的 final.md 集成成完整试卷 + 解析卷。

输出两份 md：
  - {output}_试卷.md：只有题干（教师发给学生）
  - {output}_解析.md：题干 + 参考答案 + 解析（教师参考）

题干/答案分界启发式：遇到 ## 参考答案 / ## .*解析 / ## 答案 / ### 参考答案
之前的视为题目，之后视为答案。
"""
import argparse
import re
import sys
from pathlib import Path


# 答案段开始标记（## 或 ### 级别）
ANSWER_MARKERS = re.compile(
    r"^#{2,3}\s+(参考答案|答案|.*解析|解析|求解过程|逐[步步]求解)",
    re.M,
)
# 题目段开始标记
TITLE_MARKERS = re.compile(r"^#{2,3}\s+(题目|题干|第\s*\d+\s*题)", re.M)


def extract_question_only(text: str) -> str:
    """只抽 ## 题目 段（三段式格式：## 题目 / ## 参考答案 / ## 解析）。"""
    # 去掉 ## status 段（混进来的审核元数据）
    text = re.sub(r"^##\s*status\s*$.*?(?=^##\s)", "", text, flags=re.M | re.S)
    # 找 ## 题目 段到 ## 参考答案 之间
    m_q = re.search(r"^##\s*题目\s*$", text, re.M)
    m_a = re.search(r"^##\s*(参考答案|答案)\s*$", text, re.M)
    if m_q and m_a and m_q.start() < m_a.start():
        return text[m_q.end():m_a.start()].strip()
    # 兜底：旧格式，用启发式拆
    q, _ = _split_legacy(text)
    return q


def _split_legacy(text: str) -> tuple[str, str]:
    """旧格式兜底拆分（非三段式时）。"""
    text = re.sub(r"^##\s*status\s*$.*?(?=^##\s)", "", text, flags=re.M | re.S)
    m = ANSWER_MARKERS.search(text)
    if m:
        q = text[:m.start()].strip()
    else:
        q = text.strip()
    q = re.sub(r"^\s*\*\*答案\*\*[：:].*$", "", q, flags=re.M)
    q = re.sub(r"\n{3,}", "\n\n", q)
    return q.strip(), ""


def format_score(score: int) -> str:
    return f"（{score} 分）" if score else ""


def assemble(workspace: str, output_base: str, paper_request: str | None):
    """集成所有 slot 的 final.md 成试卷 + 解析卷。"""
    ws = Path(workspace)

    # 读 paper_request 拿分值/题型分组信息
    slot_meta = {}
    if paper_request:
        import yaml
        req = yaml.safe_load(open(paper_request, encoding="utf-8"))
        for s in req.get("slots", []):
            slot_meta[s["slot_id"]] = {
                "score": s.get("score", 0),
                "type": s.get("question_type", ""),
                "complexity": s.get("complexity", "standard"),
                "topic": s.get("primary_target_name", ""),
            }

    # 收集所有有 final.md 的 slot，按 slot_id 排序
    slots = []
    for d in sorted(ws.iterdir()):
        final = d / "final.md"
        if final.exists() and d.name.startswith("Q"):
            slots.append((d.name, final.read_text(encoding="utf-8")))
    slots.sort(key=lambda x: int(re.search(r"\d+", x[0]).group()) if re.search(r"\d+", x[0]) else 0)

    if not slots:
        print("未找到任何 final.md", file=sys.stderr)
        sys.exit(1)

    # ── 构建试卷（题干）──
    exam_lines = [
        "# 计算机组成原理 期末试卷",
        "",
        f"（共 {len(slots)} 题）",
        "",
        "---",
        "",
    ]
    # ── 构建解析（题干+答案）──
    sol_lines = [
        "# 计算机组成原理 期末试卷 · 参考答案与解析",
        "",
        f"（共 {len(slots)} 题）",
        "",
        "---",
        "",
    ]

    for sid, final_text in slots:
        meta = slot_meta.get(sid, {})
        score = meta.get("score", 0)
        topic = meta.get("topic", "")
        score_str = format_score(score)

        exam_lines.append(f"## {sid}{score_str}")
        if topic:
            exam_lines.append(f"*考点：{topic}*")
        exam_lines.append("")
        exam_lines.append(extract_question_only(final_text))
        exam_lines.append("")
        exam_lines.append("---")
        exam_lines.append("")

        sol_lines.append(f"## {sid}{score_str}")
        if topic:
            sol_lines.append(f"*考点：{topic}*")
        sol_lines.append("")
        sol_lines.append(final_text)
        sol_lines.append("")
        sol_lines.append("---")
        sol_lines.append("")

    # 写出
    exam_path = Path(f"{output_base}_试卷.md")
    sol_path = Path(f"{output_base}_解析.md")
    exam_path.write_text("\n".join(exam_lines), encoding="utf-8")
    sol_path.write_text("\n".join(sol_lines), encoding="utf-8")

    print(f"✅ 试卷：{exam_path}（{len(slots)} 题，{exam_path.stat().st_size} bytes）")
    print(f"✅ 解析：{sol_path}（{sol_path.stat().st_size} bytes）")


def main():
    parser = argparse.ArgumentParser(description="集成所有 slot final.md 成试卷+解析")
    parser.add_argument("--workspace", default="/tmp/paper_full/workspace",
                        help="slot workspace 目录")
    parser.add_argument("--output", default="/tmp/paper_full/计算机组成原理期末",
                        help="输出文件前缀（生成 _试卷.md 和 _解析.md）")
    parser.add_argument("--paper-request",
                        default="docs/output_interact_cli/workspace/org_arch_mm/compose/paper_request.yaml",
                        help="paper_request.yaml（取分值/考点）")
    args = parser.parse_args()
    assemble(args.workspace, args.output, args.paper_request)


if __name__ == "__main__":
    main()
