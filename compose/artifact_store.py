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
      0. final_machine_contract (YAML summary from outline entry)
      1. 本次出题要求 (from outline entry — 考点 + 难度 + 考察模式)
      2. 基本信息 (from slot experience card)
      3. 模式概览 (matching mode from slot experience card)
      4. 相关细纲 (relevant syllabus from slot MD, filtered by knowledge point)
      5. 往年真题经验 (per-question: full stem + K-values + option analysis + trap)
      6. K值锚点 (from slot experience card)
      7. K-radar完整定义 (from slot_prompts)
    """
    import yaml
    from core_new.slot_prompts import K_RADAR_DEFINITIONS

    parts = []

    # Extract v2 fields for filtering
    active_selection = (outline_entry or {}).get("active_selection", {})
    selected_knowledge = active_selection.get("selected_knowledge", [])
    if isinstance(selected_knowledge, str):
        selected_knowledge = [selected_knowledge]
    excluded_knowledge = (outline_entry or {}).get("excluded_knowledge", [])

    # ── 0. final_machine_contract ──
    contract_fields = {}
    for key in ("slot_id", "question_type", "score", "examination_mode",
                "active_selection", "candidate_pool_visible"):
        val = (outline_entry or {}).get(key)
        if val:
            contract_fields[key] = val
    # excluded uses nested structure per schema v2
    excluded = {}
    if val := (outline_entry or {}).get("excluded_modes"):
        excluded["modes"] = val
    if val := (outline_entry or {}).get("excluded_knowledge"):
        excluded["knowledge"] = val
    if excluded:
        contract_fields["excluded"] = excluded
    if contract_fields:
        contract_yaml = yaml.dump(contract_fields, allow_unicode=True, default_flow_style=False, sort_keys=False)
        parts.append(f"## final_machine_contract\n\n```yaml\n{contract_yaml}```")

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
        mode_section_raw = _extract_matching_mode(exp_card, examination_mode)
        # Extract years from raw (unfiltered) section to preserve 参考题
        mode_years = _extract_mode_years(mode_section_raw)
        if mode_section_raw:
            mode_section = _filter_mode_by_knowledge(mode_section_raw, selected_knowledge)
            if excluded_knowledge:
                mode_section = _mark_excluded_knowledge(mode_section, excluded_knowledge)
            parts.append(f"## 模式概览（来自题位经验卡）\n\n{mode_section}")
    else:
        mode_years = []

    # ── 4. 相关知识点细纲 ──
    target_family = ""
    if outline_entry:
        target_family = outline_entry.get("target_family", "")
    syllabus = _extract_knowledge_graph_section(target_family)
    if syllabus:
        if excluded_knowledge:
            syllabus = _mark_excluded_knowledge(syllabus, excluded_knowledge)
        parts.append(f"## 相关知识点细纲\n\n{syllabus}")

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

    # Translate abbreviated codes (DS-1, CO-1 etc.) to full chapter names
    from core_new.subject_map import translate_code
    return translate_code("\n\n---\n\n".join(parts))


def _extract_basic_info(exp_card: str) -> str:
    m = re.search(r"## 基本信息\n(.*?)(?=\n## )", exp_card, re.DOTALL)
    return m.group(1).strip() if m else ""


def _filter_mode_by_knowledge(mode_section: str, selected_knowledge: list[str]) -> str:
    """Keep structural lines (考察方式, 选项架构, 陷阱, 干扰策略, etc.) intact;
    only filter the 适用知识点范围 line to highlight selected knowledge.
    """
    if not selected_knowledge:
        return mode_section
    lines = mode_section.split("\n")
    filtered = []
    for line in lines:
        # Always keep headings and blank lines
        if line.startswith("#") or line.strip() == "":
            filtered.append(line)
        # Filter only the knowledge scope line
        elif "适用知识点范围" in line:
            # Keep the line but it will be marked by excluded logic later
            filtered.append(line)
        else:
            # Keep all structural lines: 考察方式, 选项架构, 常见参数,
            # 常见陷阱, 典型干扰策略, 参考题, 难度范围, 出现频率
            filtered.append(line)
    return "\n".join(filtered)


def _mark_excluded_knowledge(syllabus: str, excluded_knowledge: list[str]) -> str:
    """Mark lines containing excluded knowledge points with [已排除]."""
    if not excluded_knowledge:
        return syllabus
    lines = syllabus.split("\n")
    result = []
    for line in lines:
        if any(ek in line for ek in excluded_knowledge):
            result.append(f"{line.rstrip()} [已排除]")
        else:
            result.append(line)
    return "\n".join(result)


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
    """Extract the experience card section matching examination_mode.

    All slot cards use ## 模式A/B/C headings (normalized format).
    Matching strategy: exact → core-type → word-level fuzzy → first mode.
    """
    mode_pattern = re.compile(r"^(##|###) (模式[A-Z][：:].+)$", re.MULTILINE)
    mode_starts = list(mode_pattern.finditer(exp_card))

    if not mode_starts:
        return ""

    modes = []
    for i, m in enumerate(mode_starts):
        start = m.start()
        end = mode_starts[i + 1].start() if i + 1 < len(mode_starts) else len(exp_card)
        sep_match = re.search(r"\n---\n", exp_card[start:])
        if sep_match and start + sep_match.start() < end:
            end = start + sep_match.start()
        modes.append((m.group(2), start, end))

    # 1. Exact substring match
    for heading, start, end in modes:
        if examination_mode in heading:
            return exp_card[start:end].strip()

    # 2. Core type match (before em-dash)
    core_type = examination_mode.split("——")[0].split("—")[0].strip()
    if core_type:
        for heading, start, end in modes:
            if core_type in heading:
                return exp_card[start:end].strip()

    # 3. Word-level fuzzy match
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

    # 4. Fallback: first mode
    return exp_card[modes[0][1]:modes[0][2]].strip()


def _extract_relevant_syllabus(slot_md: str) -> str:
    """Legacy: extract syllabus from slot.md. Kept for backward compatibility."""
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


_KG_FILE_MAP = {
    "CO": "computer_organization.md",
    "DS": "data_structure.md",
    "OS": "operating_system_knowledge.md",
    "CN": "computer_network.md",
}

_KG_DOMAIN_ALIASES = {
    "CO": "CO",
    "组成原理": "CO",
    "计算机组成原理": "CO",
    "DS": "DS",
    "数据结构": "DS",
    "OS": "OS",
    "操作系统": "OS",
    "CN": "CN",
    "计算机网络": "CN",
}


def _extract_knowledge_graph_section(target_family: str) -> str:
    """Extract relevant knowledge graph section from subject-specific file.

    Given a target_family like "CO-1 > 计算机系统概述" or "DS-5 > 树与二叉树",
    finds the corresponding section in the knowledge graph and returns its full subtree.
    Both English codes and translated codes such as "数据结构-5" are accepted.
    """
    if not target_family:
        return ""

    parts = [p.strip() for p in target_family.split(">")]
    top_level = parts[0] if parts else ""
    sub_level = parts[1] if len(parts) > 1 else ""
    domain, chapter_no, canonical_top = _parse_kg_top_level(top_level)
    if not domain or not chapter_no:
        return ""

    kg_filename = _KG_FILE_MAP.get(domain, "computer_organization.md")
    kg_path = os.path.join("data", kg_filename)
    if not os.path.exists(kg_path):
        return ""

    with open(kg_path, encoding="utf-8") as f:
        text = f.read()

    top_match = _find_kg_top_section(text, domain, chapter_no, canonical_top)
    if not top_match:
        return ""

    # Find the end of this top-level section (next ## or end of file)
    next_top = re.search(r"\n##\s+(?!#)", text[top_match.end():])
    top_end = top_match.end() + next_top.start() if next_top else len(text)
    top_section = text[top_match.start():top_end]

    # If there's a sub-level, try to find it within the top section
    if sub_level:
        # Try to match ### or #### heading containing the sub-level name
        sub_pattern = re.compile(
            rf"^(#{2,6})\s+.*{re.escape(sub_level)}", re.MULTILINE
        )
        sub_match = sub_pattern.search(top_section)
        if sub_match:
            sub_level_heading = len(sub_match.group(1))  # e.g. 3 for ###
            sub_start = sub_match.start()

            # Find the end of this sub-section (next heading at same or higher level)
            sub_end = len(top_section)
            heading_pattern = re.compile(rf"^(#{2,{sub_level_heading}})\s+", re.MULTILINE)
            for hm in heading_pattern.finditer(top_section[sub_match.end():]):
                sub_end = sub_match.end() + hm.start()
                break

            result = top_section[sub_start:sub_end]
            return _clean_knowledge_section(result)

    # Return the entire top-level section
    return _clean_knowledge_section(top_section)


def _parse_kg_top_level(top_level: str) -> tuple[str, str, str]:
    """Return (domain, chapter_no, canonical_top) from a target-family prefix."""
    raw = (top_level or "").strip()
    if not raw:
        return "", "", ""

    m = re.match(
        r"^(CO|DS|OS|CN|组成原理|计算机组成原理|数据结构|操作系统|计算机网络)-(\d+)\b",
        raw,
        flags=re.IGNORECASE,
    )
    if not m:
        return "", "", ""

    domain_key = m.group(1).upper() if m.group(1).isascii() else m.group(1)
    domain = _KG_DOMAIN_ALIASES.get(domain_key, "")
    chapter_no = m.group(2)
    canonical_top = f"{domain}-{chapter_no}" if domain else ""
    return domain, chapter_no, canonical_top


def _find_kg_top_section(text: str, domain: str, chapter_no: str, canonical_top: str):
    """Find the top-level heading in a subject knowledge graph file."""
    patterns = []
    if domain == "CO":
        patterns.append(rf"^##\s+{re.escape(canonical_top)}\b")
        # Fallback for future files that may switch to numeric headings.
        patterns.append(rf"^##\s+{re.escape(chapter_no)}\.\s+")
    else:
        # DS/OS/CN knowledge files use numeric chapter headings.
        patterns.append(rf"^##\s+{re.escape(chapter_no)}\.\s+")
        patterns.append(rf"^##\s+{re.escape(canonical_top)}\b")

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.MULTILINE)
        if match:
            return match
    return None


def _clean_knowledge_section(section: str) -> str:
    """Clean a knowledge graph section: keep headings and leaf names, remove attributes/sources."""
    lines: list[str] = []
    for line in section.split("\n"):
        stripped = line.rstrip()
        # Keep headings
        if re.match(r"^#{1,6}\s", stripped):
            lines.append(stripped)
        # Keep top-level bullet items (not sub-bullets with 属性/来源)
        elif stripped.startswith("- ") and not stripped.startswith("  "):
            if "来源页" not in stripped and "属性:" not in stripped:
                lines.append(stripped)
        elif stripped.startswith("  - ") and "属性:" not in stripped and "来源" not in stripped:
            lines.append(stripped)
        # Add blank lines for readability between heading groups
        elif not stripped.strip():
            if lines and lines[-1].strip():
                lines.append("")

    # Collapse consecutive blank lines
    result: list[str] = []
    prev_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank

    return "\n".join(result).strip()


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
