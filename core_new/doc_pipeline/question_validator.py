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
    """提取选项标记 {A,B,C,D}。

    容忍：A. / A、 / A) / A） / A: / A： 分隔符；- A. / * A. list marker；
    (A) 包裹；**A.** / **A** 加粗包裹。行首 ^|\\n 锚定保证精度，
    不误匹配句中 "Fig.A." / "A、B、C、D 都对" 等大写字母+点/顿号。

    顿号/括号是强分隔符，不要求后随空白（中文约定 A、选项 无空格）；
    点/逗号/冒号为弱分隔，要求后随空白以防误匹配。
    """
    # 行首锚定；\s*[-*]? list marker；\*{0,2} 加粗前缀；\(? (A) 包裹；
    # 弱分隔 [.,:：]+可选加粗+空白  |  强分隔 [、)）]（不要求空白）。
    return set(re.findall(
        r'(?:^|\n)\s*[-*]?\s*\*{0,2}\(?([A-D])(?:[.,:：]\*{0,2}\s|[、)）])', text))


def _has_blank(text: str) -> bool:
    """是否有空格标记（___/＿/（  ）/(  ) 连续空格占位）或显式填空指令。

    计算型填空常无字面下划线，而用"（填写一个正整数）/（结果保留两位小数）"
    指示作答位——这类也算有效空格标记，避免误判"填空题无空格"。
    """
    return bool(re.search(
        r'_{2,}|＿|（\s{3,}）|\(\s{3,}\)|【\s*】|'
        r'[（(]\s*(?:填写|填入|结果|答案)\s*[^）)]*[）)]',
        text,
    ))


def _has_judge(text: str) -> bool:
    """是否有判断标记：√/×/✓/✗/✔/✘/（对）/（错）/对错/判断/是否正确。

    ✓✗✔✘ 与 √× 同义（不同 unicode），GLM 实际产出 ✓(U+2713)/✗(U+2717)，
    一并纳入以防"判断题无标记"误判。
    """
    return bool(re.search(r'[√×✓✗✔✘]|（\s*[对错]\s*）|\(\s*[对错]\s*\)|对错|判断|是否正确', text))


def _has_answer_mark(text: str) -> bool:
    """Exam-facing question text must not contain answer markers.

    判断标记 √/×/✓/✗ 用上下文锚定：夹在字母数字之间（如芯片规格 "32K×8位"、
    "4K×4位"、算式 "2^n × m"）的 × 是乘号，不算答案标记；仅孤立的 √/× 才算。
    """
    return bool(re.search(
        r"(?:\*\*)?\s*(?:答案|正确答案|参考答案|解析|理由)\s*(?:\*\*)?\s*[：:]|"
        r"(?<![A-Za-z0-9])[√✓✗✔✘](?![A-Za-z0-9])|[（(]\s*×\s*[)）]",
        text,
    ))


def _has_explicit_prompt(text: str) -> bool:
    """Whether a subjective/computational stem contains an actionable ask."""
    return bool(re.search(
        r"(?:请|要求|回答|计算(?:出|该|并|结果|数值|时间|容量|位数)|求出?|写出|说明|判断|分析|给出|证明|填入|完成|指出|比较|设计|画出|列出|转换|推导|问|问题|小问|第\s*[（(]?\d+[）)]?\s*(?:问|题))",
        text,
    ))


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
    has_answer_mark = _has_answer_mark(text)

    if has_answer_mark:
        return False, "题面包含答案/解析/√/× 等泄漏标记"

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
        # 判断题：一句可判断的陈述即可（标准单陈述判断题就是一句断言，无 "判断/对错/①②③④" 标记）。
        # 旧捆绑式才有那些标记；非空检查已在顶部完成，此处不再强制标记。
        pass
    else:
        is_prompt_required = any(k in q for k in ("综合", "应用", "计算", "设计"))
        if is_prompt_required and not _has_explicit_prompt(text):
            return False, "题面缺少明确设问/作答要求，疑似生成截断"
    return True, ""
