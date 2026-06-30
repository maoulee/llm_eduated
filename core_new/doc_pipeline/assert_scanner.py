"""assert_scanner.py — 静态扫描 gen.py 的 assert，标记疑似"假 todo"。

确定性 AST 分析（无 LLM）。gen.py 写完后由 scheduler 调用，产出 assert_scan.md
供 dual_review 审阅。**只抓语法层高置信的假 todo**；语义层（如 `n_int != D` 只对
当前参数成立、变量算后未用）仍需 dual_review 判断。本扫描器是"便宜的初筛"，把
明显的橡皮图章 assert 拦在 dual_review 之前。

三类：
  tautology     —— assert 恒真：`assert True` / `x == x` / `len(x) >= 0`
  answer_recipe —— 答案配方：答案名变量 `==` 硬编码字面量（`== 2MB`/`== 6336`/`== "0x4C3F4"`）
  low_value     —— 弱断言：`assert x is not None`（几乎必过，无区分力）

判据（一条好的 assert 必须"可证伪 + 可推广"）：
  - 可证伪：建错模型时真能 fail（恒真 = 不可证伪 → 假 todo）。
  - 可推广：断言的是定律/关系，不是当前答案字面量（== 答案魔数 = 不可推广 → 假 todo）。
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

# 变量名含这些片段 → 更可能是"答案变量"，== 大整数/hex = 高置信答案配方。
# 故意只用无歧义的长片段：短的（"ea"/"sum"/"ans"）会误伤 feasible/sum_overflow 等。
_ANSWER_NAME_HINTS = (
    "answer", "result", "final", "a_val", "b_val", "c_val", "d_val",
    "capacity", "n_int", "n_dma", "hex_", "machine_code", "truth_val",
    "correct", "expected_ans",
)


def _is_answer_literal(val) -> bool:
    """是否"答案级字面量"：大整数(>1000 且非整千) 或 十六进制字符串。
    排除 True/False/None/小整数/非hex短串（这些多是布尔标志/符号位检查，非答案配方）。"""
    if isinstance(val, bool):
        return False
    if isinstance(val, int):
        return val > 1000 and val % 1000 != 0
    if isinstance(val, str):
        return val.lower().startswith("0x") and len(val) >= 4
    return False


@dataclass
class Finding:
    kind: str        # tautology | answer_recipe | low_value
    severity: str    # high | med | low
    line: int
    snippet: str
    reason: str


def _flatten_and(node: ast.AST) -> list[ast.AST]:
    """把 `a and b and c` 拆成 [a, b, c]，逐项判。"""
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
        out: list[ast.AST] = []
        for v in node.values:
            out.extend(_flatten_and(v))
        return out
    return [node]


def _is_len_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "len"


def _is_self_compare(node: ast.AST) -> bool:
    """`x == x` / `x is x`（左右同构 → 恒真）。"""
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.Is)):
        return ast.dump(node.left) == ast.dump(node.comparators[0])
    return False


def _is_len_nonneg(node: ast.AST) -> bool:
    """`len(...) >= 0` / `len(...) > -1`（len 永远非负 → 恒真）。"""
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        left, op, right = node.left, node.ops[0], node.comparators[0]
        if _is_len_call(left) and isinstance(right, ast.Constant) and isinstance(right.value, int):
            if isinstance(op, ast.GtE) and right.value <= 0:
                return True
            if isinstance(op, ast.Gt) and right.value < 0:
                return True
    return False


def _classify_atom(node: ast.AST) -> Finding | None:
    """判定单个原子断言（已拆 and）。"""
    # assert True / assert <正整数常量>
    if isinstance(node, ast.Constant):
        v = node.value
        if v is True or v == 1:
            return Finding("tautology", "high", 0, "", "assert 常量恒真")
        return None
    if _is_self_compare(node):
        return Finding("tautology", "high", 0, "", "自等恒真 (x == x / x is x)")
    if _is_len_nonneg(node):
        return Finding("tautology", "high", 0, "", "len() 非负恒真")
    # assert X is not None（弱断言：几乎必过，无区分力）
    if (isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.IsNot)
            and isinstance(node.comparators[0], ast.Constant) and node.comparators[0].value is None):
        return Finding("low_value", "low", 0, "", "... is not None（弱断言，几乎必过）")
    # 答案配方：Name == 答案级字面量（大整数/hex串）；bool/小整数/非hex串不算
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.Is)):
        left, right = node.left, node.comparators[0]
        for a, b in ((left, right), (right, left)):
            if isinstance(a, ast.Name) and isinstance(b, ast.Constant) and _is_answer_literal(b.value):
                name, val = a.id.lower(), b.value
                if any(h in name for h in _ANSWER_NAME_HINTS):
                    return Finding("answer_recipe", "high", 0, "",
                                   f"{a.id} == {val!r}（答案名变量硬编码字面量）")
                return Finding("answer_recipe", "med", 0, "",
                               f"{a.id} == {val!r}（硬编码答案级字面量）")
    return None


def scan_asserts(source: str) -> list[Finding]:
    """扫描 Python 源码，返回所有疑似假 todo 的 assert。"""
    findings: list[Finding] = []
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        for atom in _flatten_and(node.test):
            f = _classify_atom(atom)
            if f is None:
                continue
            f.line = node.lineno
            f.snippet = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
            findings.append(f)
    return findings


def render_md(findings: list[Finding], genpy_name: str = "gen.py") -> str:
    """渲染 assert_scan.md（dual_review 读）。"""
    if not findings:
        return (f"## assert_scan\n\n{genpy_name} 通过语法层筛查：未检出恒真/答案配方/弱断言。"
                f"（注：语义层假 todo 如'只对当前参数成立的不等式'仍需 dual_review 判断。）\n")
    high = sum(1 for f in findings if f.severity == "high")
    out = [f"## assert_scan\n",
           f"检出 **{len(findings)}** 处疑似假 todo（high={high}）——请 dual_review 逐条复核，"
           f"确认是假 todo 的判 needs_fix：\n"]
    for f in findings:
        snip = f.snippet[:90].replace("`", "'")
        out.append(f"- **[{f.kind}/{f.severity}]** L{f.line} `{snip}` — {f.reason}")
    return "\n".join(out) + "\n"


def scan_file(genpy_path: str | Path) -> list[Finding]:
    return scan_asserts(Path(genpy_path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    import sys
    _p = Path(sys.argv[1])
    _f = scan_file(_p)
    print(render_md(_f, _p.name))
