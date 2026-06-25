"""question_validator.py — 题面结构校验（确定性兜底，L1）。

按题型声明校验 question.md（题面）结构完整性，防止：
- 单选题选项被截断（Q15 类：题干后无 A/B/C/D）
- 题型错位（Q16-18 类：声明填空却出成四选一）
- 判断题无对/错标记
- 题面为空

供 TeamGenNode（team 路径）+ concept 路径在生成后校验；不合规 → 越界退回重写。
确定性、无 LLM、快。"""
import re


def _option_markers(text: str) -> set[str]:
    """提取选项标记 {A,B,C,D}（支持 A. / A、 / A) / A） / - A. / * A. / (A) 等）。"""
    # 行首或换行后，可选 list marker(-/*)，可选空白，然后 A-D + ./,/)/）/:/：
    return set(re.findall(r'(?:^|\n)\s*[-*]?\s*\(?([A-D])[\.\.\)）：：]\s', text))


def _has_blank(text: str) -> bool:
    """是否有空格标记（___/＿/（  ）/(  ) 连续空格占位）。"""
    return bool(re.search(r'_{2,}|＿|（\s{3,}）|\(\s{3,}\)|【\s*】', text))


def _has_judge(text: str) -> bool:
    """是否有判断标记（√/×/（对）/（错）/对错/判断）。"""
    return bool(re.search(r'[√×]|（\s*[对错]\s*）|\(\s*[对错]\s*\)|对错|判断|是否正确', text))


def validate_question_structure(text: str | None, qtype: str | None) -> tuple[bool, str]:
    """校验题面结构是否符合题型声明。

    Args:
        text: question.md（题面）内容。
        qtype: 题型（单项选择题/填空题/判断题/简答题/应用题/设计题/综合题，
               或 single_choice/fill_blank/subjective 等）。
    Returns:
        (ok, reason): ok=True 合规；ok=False 时 reason 指出缺陷。
    """
    if not text or not text.strip():
        return False, "题面为空"
    q = (qtype or "").strip()
    is_choice = (q in ("单项选择题", "single_choice", "选择题", "多选题", "多项选择题")
                 or "选择" in q)
    is_fill = q in ("填空题", "fill_blank", "填空") or "填空" in q
    is_judge = q in ("判断题", "判断", "true_false") or "判断" in q

    opts = _option_markers(text)
    has_blank = _has_blank(text)
    has_judge = _has_judge(text)

    if is_choice:
        if len(opts) < 4:
            return False, f"单选题选项不足（找到 {len(opts)}/4 个 A-D 标记），疑似题干截断"
    elif is_fill:
        # 声明填空却出成四选一 = 题型错位
        if not has_blank and len(opts) >= 4:
            return False, "声明为填空题，但题面是四选一（题型错位）"
        if not has_blank:
            return False, "填空题无空格标记（___/（  ））"
    elif is_judge:
        if not has_judge:
            return False, "判断题无对/错/√/× 标记"
    # 综合/简答/应用/设计：非空即过（上面已查空）
    return True, ""
