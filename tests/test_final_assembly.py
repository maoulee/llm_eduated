"""回归测试：_format_final 概念题兜底（final 装配 ## 题目 不再空）。

bug：概念题 question.md 用 `## 第 N 题` 格式（conceptual_batch），无 `## 题干` 段。
_format_final 原只从 `## 题干` 提题干 → 概念题 stem 空 → final.md `## 题目` 空。
修复：stem 空时兜底用整个 question.md（去 **答案** 行）作为题目。

Run: python3 -m pytest tests/test_final_assembly.py -v
"""
import re
from pathlib import Path

from core_new.doc_pipeline.orchestrator import DocPipelineOrchestrator

CONCEPT_Q = """# 概念题

## 第 1 题

**题干**：关于顺序表与链表的随机访问特性，下列说法正确的是：

A. 顺序表和链表都支持随机访问，但顺序表的访问速度更快
B. 顺序表支持随机访问，链表不支持随机访问
C. 链表支持随机访问，顺序表只支持顺序访问
D. 两者都不支持随机访问

**答案**：B
"""

STD_Q = """# Q3 二维数组列优先存储

## 题干

设二维数组 A[5][6] 按列优先存储，每个元素 4 字节，base=1000。求 A[2][3] 的地址。

## 通过条件（成功判据，可机检）

- A/B/C/D 互异；A 为正确值（列优先公式）。

## 设计说明

考察列优先地址计算。
"""

SOLUTION = """## 求解过程

列优先：LOC(A[i][j]) = base + (j*M+i)*L。
A[2][3] = 1000 + (3*5+2)*4 = 1068。

## 最终答案

1068
"""


def _run_format(tmp_path: Path, q: str, s: str = SOLUTION) -> str:
    (tmp_path / "question.md").write_text(q, encoding="utf-8")
    (tmp_path / "solution.md").write_text(s, encoding="utf-8")
    DocPipelineOrchestrator._format_final(
        tmp_path,
        question_path=tmp_path / "question.md",
        solution_path=tmp_path / "solution.md",
        output_path=tmp_path / "solve_output.txt",  # 不存在 → 跳过
    )
    return (tmp_path / "final.md").read_text(encoding="utf-8")


def _topic_body(final: str) -> str:
    """final.md 的 ## 题目 段（到 ## 求解过程 为止；概念题 stem 含内部 ## 第N题）。"""
    i = final.find("## 题目")
    assert i >= 0, "final.md 缺 ## 题目 段"
    j = final.find("## 求解过程")
    if j < 0:
        j = len(final)
    return final[i + len("## 题目"):j].strip()


def test_format_final_concept_stem_not_empty(tmp_path):
    """概念题（## 第 N 题，无 ## 题干）→ final.md ## 题目 非空、含题干。"""
    final = _run_format(tmp_path, CONCEPT_Q)
    body = _topic_body(final)
    assert len(body) > 50, f"概念题题目段不应为空，实得 {len(body)}b"
    assert "顺序表与链表" in body  # 题干内容进来了
    assert "第 1 题" in body  # 概念批量结构保留


def test_format_final_concept_strips_answer(tmp_path):
    """概念题兜底应去掉 **答案** 行（答案不进题目段）。"""
    final = _run_format(tmp_path, CONCEPT_Q)
    body = _topic_body(final)
    assert "**答案**" not in body, "题目段不应含 **答案** 行"


def test_format_final_std_stem_still_works(tmp_path):
    """综合题（## 题干）→ final.md ## 题目 仍正确（回归保护）。"""
    final = _run_format(tmp_path, STD_Q)
    body = _topic_body(final)
    assert "列优先" in body  # 题干内容
    assert "二维数组" in body
