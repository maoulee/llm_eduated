"""Experience doc assembly for slot-based question generation.

Builds per-slot assembled markdown from outline entries, experience cards,
slot templates, past exam data, and K-radar definitions.
"""

import json
import os
import re


def assemble_slot_experience_doc(
    slot_id: str,
    examination_mode: str,
    slot_md_path: str,
    experience_card_path: str,
    outline_entry: dict = None,
) -> str:
    """Assemble a complete experience document for a slot based on chosen examination mode.

    Structure:
      1. 本次出题要求 (from outline entry — 考点 + 难度 + 考察模式)
      2. 基本信息 (from slot experience card)
      3. 模式概览 (matching mode from slot experience card)
      4. 相关细纲 (relevant syllabus from slot MD, filtered by knowledge point)
      5. 往年真题经验 (per-question: full stem + K-values + option analysis + trap)
      6. K值锚点 (from slot experience card)
      7. K-radar完整定义 (from slot_prompts)
    """
    from core_new.slot_prompts import K_RADAR_DEFINITIONS

    parts = []

    # ── Load sources ──
    exp_card = ""
    if experience_card_path and os.path.exists(experience_card_path):
        with open(experience_card_path, encoding="utf-8") as f:
            exp_card = f.read()

    slot_md = ""
    if slot_md_path and os.path.exists(slot_md_path):
        with open(slot_md_path, encoding="utf-8") as f:
            slot_md = f.read()

    # ── 1. 本次出题要求 (from outline entry) ──
    if outline_entry:
        req_lines = [f"# {slot_id} 出题参考文档（考察模式：{examination_mode}）"]
        req_lines.append("")
        req_lines.append("## 本次出题要求（来自组卷大纲）")
        if outline_entry.get("primary_target_name"):
            req_lines.append(f"- **考点**: {outline_entry['primary_target_name']}")
        if outline_entry.get("target_family"):
            req_lines.append(f"- **知识域**: {outline_entry['target_family']}")
        if outline_entry.get("difficulty_level") or outline_entry.get("target_difficulty"):
            dl = outline_entry.get("difficulty_level", outline_entry.get("target_difficulty", ""))
            req_lines.append(f"- **难度**: {dl}")
        if outline_entry.get("k_target"):
            req_lines.append(f"- **K目标**: {outline_entry['k_target']}")
        if outline_entry.get("difficulty_rationale"):
            req_lines.append(f"- **难度说明**: {outline_entry['difficulty_rationale']}")
        req_lines.append(f"- **考察模式**: {examination_mode}")
        parts.append("\n".join(req_lines))
    else:
        parts.append(f"# {slot_id} 出题参考文档（考察模式：{examination_mode}）")

    # ── 2. 基本信息 ──
    basic_info = _extract_basic_info(exp_card)
    if basic_info:
        parts.append(f"## 基本信息\n\n{basic_info}")

    # ── 3. 模式概览 ──
    if exp_card and examination_mode:
        mode_section = _extract_matching_mode(exp_card, examination_mode)
        if mode_section:
            parts.append(f"## 模式概览（来自题位经验卡）\n\n{mode_section}")
        mode_years = _extract_mode_years(mode_section)
    else:
        mode_years = []

    # ── 4. 相关细纲 ──
    syllabus = _extract_relevant_syllabus(slot_md)
    if syllabus:
        parts.append(f"## 相关细纲\n\n{syllabus}")

    # ── 5. 往年真题经验 ──
    if mode_years:
        question_entries = _build_question_entries(slot_id, mode_years)
        if question_entries:
            parts.append(f"## 往年真题经验（{examination_mode}，共{len(question_entries)}题）\n\n" + "\n\n---\n\n".join(question_entries))

    # ── 6. K值锚点 ──
    k_anchors = _extract_k_anchors(exp_card)
    if k_anchors:
        parts.append(f"## K值锚点（{slot_id} 题位历史分布）\n\n{k_anchors}")

    # ── 7. K-radar完整定义 ──
    radar_text = K_RADAR_DEFINITIONS.strip()
    radar_text = re.sub(r"^##\s+K1-K5.*?\n", "", radar_text)
    parts.append(f"## K1-K5 认知雷达评分标准\n\n{radar_text.strip()}")

    return "\n\n---\n\n".join(parts)


def _extract_basic_info(exp_card: str) -> str:
    m = re.search(r"## 基本信息\n(.*?)(?=\n## )", exp_card, re.DOTALL)
    return m.group(1).strip() if m else ""


def _extract_k_anchors(exp_card: str) -> str:
    m = re.search(r"## K值锚点\n(.*?)(?=\n## )", exp_card, re.DOTALL)
    return m.group(1).strip() if m else ""


def _extract_mode_years(mode_section: str) -> list:
    if not mode_section:
        return []
    ref_match = re.search(r"\*?\*?参考题\*?\*?[:：]\s*(.+)", mode_section)
    if not ref_match:
        ref_match = re.search(r"\*?\*?出现频率\*?\*?[:：]\s*(.+)", mode_section)
    if not ref_match:
        return []
    return re.findall(r"(\d{4})", ref_match.group(1))


def _extract_matching_mode(exp_card: str, examination_mode: str) -> str:
    """Extract the experience card section matching examination_mode."""
    mode_pattern = re.compile(r"^## (模式[A-Z][：:].+)$", re.MULTILINE)
    mode_starts = list(mode_pattern.finditer(exp_card))

    if not mode_starts:
        mode_pattern = re.compile(r"^### (模式[A-Z][：:].+)$", re.MULTILINE)
        mode_starts = list(mode_pattern.finditer(exp_card))

    if not mode_starts:
        struct_match = re.search(r"^## 考察结构模式\n(.*?)(?=\n## |\Z)", exp_card, re.MULTILINE | re.DOTALL)
        return struct_match.group(1).strip() if struct_match else ""

    modes = []
    for i, m in enumerate(mode_starts):
        start = m.start()
        end = mode_starts[i + 1].start() if i + 1 < len(mode_starts) else len(exp_card)
        sep_match = re.search(r"\n---\n", exp_card[start:])
        if sep_match and start + sep_match.start() < end:
            end = start + sep_match.start()
        modes.append((m.group(1), start, end))

    for heading, start, end in modes:
        if examination_mode in heading:
            return exp_card[start:end].strip()

    core_type = examination_mode.split("——")[0].split("—")[0].strip()
    if core_type:
        for heading, start, end in modes:
            if core_type in heading:
                return exp_card[start:end].strip()

    words = [w for w in re.split(r"[——\-\s,，、]", examination_mode) if len(w) >= 2]
    best_match = None
    best_score = 0
    for heading, start, end in modes:
        score = sum(1 for w in words if w in heading)
        if score > best_score:
            best_score = score
            best_match = (start, end)
    if best_match and best_score > 0:
        return exp_card[best_match[0]:best_match[1]].strip()

    return exp_card[modes[0][1]:modes[0][2]].strip()


def _extract_relevant_syllabus(slot_md: str) -> str:
    if not slot_md:
        return ""
    m = re.search(r"## 细纲参考\n(.*?)(?=\n## (?:认知雷达|往年题干)|$)", slot_md, re.DOTALL)
    if not m:
        return ""
    syllabus = m.group(1).strip()
    lines = syllabus.split("\n")
    compact = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            level = len(re.match(r"^(#+)", stripped).group(1))
            if level <= 3:
                compact.append(stripped)
        elif stripped.startswith("- ") and "属性:" not in stripped and "来源" not in stripped:
            compact.append("  " + stripped)
    return "\n".join(compact) if compact else ""


def _build_question_entries(slot_id: str, years: list) -> list:
    raw_index = _load_raw_questions()
    entries = []
    for year in years:
        qnum = int(slot_id[1:])
        exp_path = os.path.join("data", "question_experiences", f"{year}_{slot_id}.md")
        full_stem = raw_index.get((int(year), qnum), "")
        analysis = ""
        if os.path.exists(exp_path):
            with open(exp_path, encoding="utf-8") as f:
                analysis = f.read()
        if not full_stem and not analysis:
            continue
        entry = _format_question_entry(year, slot_id, full_stem, analysis)
        if entry:
            entries.append(entry)
    return entries


def _load_raw_questions() -> dict:
    raw_path = "/zhaoshu/mcts_reason/data/full_question.json"
    if not os.path.exists(raw_path):
        return {}
    with open(raw_path, encoding="utf-8") as f:
        data = json.load(f)
    index = {}
    for item in data:
        prompt = item.get("prompt", "")
        m = re.match(r"\[(\d{4})年考研真题第(\d+)题\]", prompt)
        if m:
            year, qnum = int(m.group(1)), int(m.group(2))
            clean = re.sub(r"^\[\d{4}年考研真题第\d+题\]", "", prompt).strip()
            clean = clean.replace("\\n", "\n")
            index[(year, qnum)] = clean
    return index


def _format_question_entry(year: str, slot_id: str, full_stem: str, analysis: str) -> str:
    parts = []
    title_match = re.search(r"^# .+$", analysis, re.MULTILINE)
    title = title_match.group(0) if title_match else f"### {year}年 — {slot_id}"
    parts.append(title)

    basic_section = _extract_section(analysis, "基本信息")
    kp_text = _extract_knowledge_points(basic_section)
    radar = _extract_radar_shape(analysis)
    kp_line = f"**知识点**: {kp_text} | **雷达形状**: {radar}" if kp_text else f"**雷达形状**: {radar}"
    parts.append(kp_line)

    k_values = _extract_k_values(analysis)
    if k_values:
        parts.append("**K值**:\n" + "\n".join(f"  - K{i+1}={v}" for i, v in enumerate(k_values)))
    else:
        parts.append("")

    if full_stem:
        parts.append(f"**题干**: {full_stem}")
    else:
        stem = _extract_section(analysis, "题干原文")
        if stem:
            parts.append(f"**题干**: {stem}")

    options = _extract_option_analysis(analysis)
    if options:
        parts.append("**选项分析**:\n" + options)

    strategy = _extract_field(analysis, "干扰策略")
    if strategy:
        parts.append(f"**干扰策略**: {strategy}")

    trap = _extract_core_trap(analysis)
    if trap:
        parts.append(f"核心陷阱: {trap}")

    return "\n\n".join(parts)


def _extract_section(text: str, heading: str, single_line: bool = False) -> str:
    pattern = rf"## {re.escape(heading)}\n(.*?)(?=\n## |\Z)"
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return ""
    content = m.group(1).strip()
    if single_line:
        return content.split("\n")[0]
    return content


def _extract_knowledge_points(basic_info: str) -> str:
    m = re.search(r"\*?\*?知识点\*?\*?[:：]\s*(.+)", basic_info)
    return m.group(1).strip() if m else ""


def _extract_radar_shape(analysis: str) -> str:
    m = re.search(r"\*?\*?雷达形状\*?\*?[:：]\s*(.+)", analysis)
    return m.group(1).strip() if m else "N/A"


def _extract_k_values(analysis: str) -> list:
    k_section = _extract_section(analysis, "K1-K5 评分与解析")
    if not k_section:
        return []
    values = []
    for i in range(1, 6):
        m = re.search(rf"\*?\*?K{i}\s*=\s*(\d+)\*?\*?[:：]\s*(.+?)(?:\n|$)", k_section)
        if m:
            score = m.group(1)
            explanation = m.group(2).strip()
            explanation = re.sub(r"^\d+\s*[—\-]\s*", "", explanation)
            explanation = explanation[:120]
            values.append(f"{score}: {explanation}")
        else:
            values.append("?")
    return values


def _extract_option_analysis(analysis: str) -> str:
    section = _extract_section(analysis, "选项级分析")
    if not section:
        return ""
    cleaned = re.sub(r"^\s*-\s*\*?\*?干扰策略\*?\*?[:：].*$", "", section, flags=re.MULTILINE)
    return cleaned.strip()


def _extract_field(text: str, field_name: str) -> str:
    m = re.search(rf"\*?\*?{re.escape(field_name)}\*?\*?[:：]\s*(.+?)(?:\n|$)", text)
    return m.group(1).strip() if m else ""


def _extract_core_trap(analysis: str) -> str:
    section = _extract_section(analysis, "核心陷阱")
    if not section:
        return ""
    lines = [l for l in section.split("\n") if l.strip()]
    if not lines:
        return ""
    first = lines[0].strip()
    first = re.sub(r"^-\s*\*?\*?核心陷阱\*?\*?\s*[:：]\s*", "", first).strip()
    first = first.replace("**", "")
    first = re.sub(r"^核心陷阱\s*[:：]\s*", "", first).strip()
    return first
