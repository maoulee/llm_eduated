"""Draft parser — bidirectional conversion between markdown drafts and JSON.

Handles parsing agent-generated markdown drafts into structured DraftData,
rendering pruning annotations back to markdown, and detecting drafts in
agent responses.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from api.schemas_interact_v2 import (
    AnnotationSubmission,
    DraftData,
    DraftOption,
    DraftSlot,
)

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

# Level-1 heading: # Title
_RE_H1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)

# Level-2 heading: ## Q1（选择题·2分） ...
_RE_H2 = re.compile(r"^##\s+(.+)$", re.MULTILINE)

# Slot ID extraction from header text: Q1, Q2, etc.
_RE_SLOT_ID = re.compile(r"(Q\d+)", re.IGNORECASE)

# Option line: starts with [ ], [✓], [✗]
_RE_CHECKBOX_LINE = re.compile(r"^\s*\[[ x✓✗]\]\s*(.+)$")

# Dash list line: starts with "- " (used as option detail, not a separate option)
_RE_DASH_LINE = re.compile(r"^\s*-\s+(.+)$")

# Plain option line (text that is not a header, blockquote, empty, or checkbox)
# Used after checkbox/dash patterns have been exhausted.
_RE_PLAIN_OPTION = re.compile(r"^[^\s#>].*[^\s]$")

# Cognitive description in parentheses: （需一步公式推导） or (needs derivation)
_RE_COGNITIVE = re.compile(r"[（(]([^）)]+)[）)]")

# Annotation / blockquote: > 教师批注: xxx  or  > xxx
_RE_ANNOTATION = re.compile(r"^>\s*(?:教师批注[:：]\s*)?(.+)$", re.MULTILINE)

# Scenario hints from title / content
_SCENARIO_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"408"), "A"),
    (re.compile(r"考察模式"), "C"),
    (re.compile(r"专项练习|强化训练"), "B"),
]

_K_TERM_MAP = {
    "1": "基础认知",
    "2": "单步代入",
    "3": "多步推演",
    "4": "组合分析",
    "5": "综合设计",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_draft_md(md_text: str, draft_id: str = "") -> DraftData:
    """Parse agent-generated markdown into structured DraftData.

    Splits on level-2 headers (##), extracts slot IDs, options, cognitive
    descriptions, and teacher annotations.
    """
    if not md_text or not md_text.strip():
        return _empty_draft(md_text or "", draft_id)

    # --- Title from level-1 heading ---
    h1_match = _RE_H1.search(md_text)
    title = h1_match.group(1).strip() if h1_match else ""

    # --- Extract [SCENARIO: X], [ROUND: N], and optional [PHASE: X] from file header ---
    scenario = "A"
    current_round = 1
    global_phase: str | None = None
    _sc_match = re.search(r"\[SCENARIO:\s*([ABC])\]", md_text[:500])
    if _sc_match:
        scenario = _sc_match.group(1)
    else:
        scenario = _detect_scenario(md_text)
    _round_match = re.search(r"\[ROUND:\s*(\d+)\]", md_text[:500])
    if _round_match:
        current_round = int(_round_match.group(1))
    _phase_match = re.search(
        r"\[PHASE:\s*(knowledge|examination|combined|question_type)\]",
        md_text[:500],
        re.I,
    )
    if _phase_match:
        global_phase = _phase_match.group(1).lower()

    # Strip metadata lines so they don't pollute options
    md_text = re.sub(r"\[SCENARIO:\s*[ABC]\]\s*", "", md_text)
    md_text = re.sub(r"\[ROUND:\s*\d+\]\s*", "", md_text)
    md_text = re.sub(
        r"\[PHASE:\s*(?:knowledge|examination|combined|question_type)\]\s*",
        "",
        md_text,
        flags=re.I,
    )

    # --- Split into sections by level-2 heading positions ---
    h2_positions = [m.start() for m in _RE_H2.finditer(md_text)]
    h2_headers = [m.group(1).strip() for m in _RE_H2.finditer(md_text)]

    if not h2_positions:
        # No ## sections — try parsing as a flat option list
        # Handles drafts like:
        #   # Title
        #   [ ] **模式1：xxx**（认知描述）
        #   [ ] **模式2：yyy**（认知描述）
        flat_options, flat_annotation = _parse_section_body(md_text, 1)
        if flat_options:
            return DraftData(
                draft_id=draft_id,
                title=title,
                scenario=scenario,
                current_round=current_round,
                sections=[
                    DraftSlot(
                        slot_id="Q1",
                        display_id="1",
                        title=title or "考察模式草案",
                        phase=_infer_draft_phase(
                            title or "",
                            is_question_type_section=False,
                            current_round=current_round,
                            global_phase=global_phase,
                        ),
                        options=flat_options,
                        annotation=flat_annotation,
                    )
                ],
                raw_md=md_text,
            )
        # No options found at all — return raw_md fallback
        return DraftData(
            draft_id=draft_id,
            title=title,
            scenario=scenario,
            current_round=current_round,
            sections=[],
            raw_md=md_text,
        )

    sections: list[DraftSlot] = []
    for idx, (header_text, start) in enumerate(
        zip(h2_headers, h2_positions)
    ):
        # Determine the end of this section (start of next section or EOF)
        end = h2_positions[idx + 1] if idx + 1 < len(h2_positions) else len(md_text)
        body = md_text[start:end]

        # Skip non-question sections: summary, notes, instructions, etc.
        _skip_keywords = ("需求确认", "摘要", "使用说明", "注意事项", "K-radar", "参考",
                          "补充说明", "数据汇总", "确认摘要")
        if any(kw in header_text for kw in _skip_keywords):
            continue

        # Slot ID — handle "Q1 题型" sections by appending suffix
        slot_match = _RE_SLOT_ID.search(header_text)
        slot_id = slot_match.group(1).upper() if slot_match else f"Q{idx + 1}"
        is_question_type_section = False
        if "题型" in header_text and slot_match:
            slot_id = f"{slot_id}_type"
            is_question_type_section = True
        # Also detect 题型 sections by "考察方向" pattern: ## Q1 考察方向
        is_content_section = "考察方向" in header_text or "考察内容" in header_text

        # Parse options and annotation from body
        options, annotation = _parse_section_body(body, idx + 1)

        # Skip sections with no options (empty headings)
        if not options:
            continue

        # Display ID for teacher-facing UI — plain numeric (1, 2, …)
        # Internal slot_id keeps Q-prefix for extraction; display_id is number-only.
        _q_num_match = re.search(r"Q(\d+)", slot_id)
        _num = _q_num_match.group(1) if _q_num_match else str(idx + 1)
        if is_question_type_section:
            display_id = f"{_num} · 题型"
        elif is_content_section:
            display_id = f"{_num} · 考察方向"
        else:
            display_id = _num
        phase = _infer_draft_phase(
            header_text,
            is_question_type_section=is_question_type_section,
            current_round=current_round,
            global_phase=global_phase,
        )

        sections.append(
            DraftSlot(
                slot_id=slot_id,
                display_id=display_id,
                title=header_text,
                phase=phase,
                options=options,
                annotation=annotation,
            )
        )

    return DraftData(
        draft_id=draft_id,
        title=title,
        scenario=scenario,
        current_round=current_round,
        sections=sections,
        raw_md=md_text,
    )


def render_annotated_md(
    original: DraftData, annotation: AnnotationSubmission
) -> str:
    """Convert pruning annotation back to markdown for scheduler consumption.

    For each SlotAnnotation, finds the matching DraftSlot in *original*,
    keeps only the options listed in ``kept_options``, applies any text
    modifications, and includes the annotation blockquote.
    """
    # Index original slots by slot_id for fast lookup
    slot_map = {s.slot_id: s for s in original.sections}
    selected_slots = [slot_map[sa.slot_id] for sa in annotation.slots if sa.slot_id in slot_map]
    selected_phase = next(
        (slot.phase for slot in selected_slots if slot.phase != "question_type"),
        "combined",
    )
    lines: list[str] = [
        f"[SCENARIO: {original.scenario}]",
        f"[ROUND: {original.current_round}]",
        f"[PHASE: {selected_phase}]",
        "",
    ]

    for sa in annotation.slots:
        slot = slot_map.get(sa.slot_id)
        if slot is None:
            continue

        lines.append(f"## {slot.title}")

        # Build option id → DraftOption map
        opt_map = {o.id: o for o in slot.options}
        kept_options = list(sa.kept_options)
        if not kept_options and sa.selected_option_id:
            kept_options = [sa.selected_option_id]

        for opt_id in kept_options:
            opt = opt_map.get(opt_id)
            if opt is None:
                continue

            # Apply modified text if provided
            text = sa.modified_text.get(opt_id, opt.text)
            # Preserve cognitive description if present (avoid duplication)
            cog = opt.cognitive_desc
            if cog and not _RE_COGNITIVE.search(text):
                text = f"{text}（{cog}）"
            lines.append(text)

        if sa.annotation:
            lines.append(f"> 教师批注: {sa.annotation}")

        lines.append("")  # blank line between sections

    return "\n".join(lines).rstrip() + "\n"


def detect_draft_in_response(response_text: str) -> bool:
    """Quick check if an agent response contains a parseable draft.

    Looks for level-2 headers with Q-patterns and option markers.
    """
    if not response_text:
        return False

    # Level-2 header with Q pattern
    if re.search(r"^##\s+Q\d+", response_text, re.MULTILINE):
        return True

    # Level-2 header with checkbox option markers
    has_h2 = bool(re.search(r"^##\s+", response_text, re.MULTILINE))
    has_options = bool(re.search(r"^\s*\[[ x✓✗]\]", response_text, re.MULTILINE))
    if has_h2 and has_options:
        return True

    return False


def parse_yaml_result(yaml_path: str) -> dict | None:
    """Parse a final YAML file (paper_request / slot_blueprint) from the agent.

    Returns None if the file does not exist or cannot be parsed.
    """
    p = Path(yaml_path)
    if not p.exists():
        return None
    try:
        text = p.read_text(encoding="utf-8")
        return yaml.safe_load(text)
    except (yaml.YAMLError, OSError):
        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _empty_draft(raw_md: str, draft_id: str) -> DraftData:
    """Return a minimal DraftData for malformed / empty input."""
    return DraftData(
        draft_id=draft_id,
        title="",
        scenario="A",
        sections=[],
        raw_md=raw_md,
    )


def _detect_scenario(text: str) -> str:
    """Heuristic scenario detection from draft text."""
    for pattern, scenario in _SCENARIO_PATTERNS:
        if pattern.search(text):
            return scenario
    return "A"


def _infer_draft_phase(
    header_text: str,
    *,
    is_question_type_section: bool,
    current_round: int,
    global_phase: str | None,
) -> str:
    """Infer what the teacher is being asked to choose in a draft section."""
    if is_question_type_section:
        return "question_type"

    if global_phase in {"knowledge", "examination", "combined"}:
        return global_phase

    text = header_text.lower()
    if any(
        marker in header_text
        for marker in ("知识点", "知识范围", "考察范围", "粗知识", "第一层")
    ):
        return "knowledge"

    if any(
        marker in header_text
        for marker in ("考察方式", "考察模式", "第二层", "细化")
    ):
        return "examination"

    if current_round >= 2:
        return "examination"

    if "knowledge" in text:
        return "knowledge"
    if "examination" in text:
        return "examination"
    return "combined"


def _parse_section_body(
    body: str, section_idx: int
) -> tuple[list[DraftOption], str]:
    """Parse a section body into options and annotation.

    Parameters
    ----------
    body:
        Full text of the section including its ## header line.
    section_idx:
        1-based index used for generating option IDs.
    """
    lines = body.splitlines()
    options: list[DraftOption] = []
    annotation = ""
    opt_counter = 0
    # Accumulate continuation lines (e.g. "- detail line") into the
    # previous checkbox option rather than treating them as separate options.
    _pending_detail: list[str] = []

    def _flush_detail():
        """Append accumulated detail lines to the last option's text."""
        if _pending_detail and options:
            detail = " ".join(_pending_detail)
            last = options[-1]
            last.text = f"{last.text} — {detail}" if last.text else detail
            _pending_detail.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            _flush_detail()
            continue

        # Skip level-1 heading
        if stripped.startswith("# ") and not stripped.startswith("## "):
            continue

        # Skip level-2 header line itself
        if stripped.startswith("## "):
            continue

        # Skip horizontal rules
        if stripped == "---":
            continue

        # Skip instruction lines that look like options
        # (e.g. "**使用说明：**" or lines containing "把 `[ ]` 改为")
        if ("使用说明" in stripped or "改为" in stripped or "表示选中" in stripped
                or "可以添加" in stripped or "每题" in stripped and "选择" in stripped):
            continue

        # Skip K-radar / internal data lines (should never reach teacher)
        if ("K-radar" in stripped or "K-radar" in stripped.replace("‑", "-")
                or "k_radar" in stripped or "供下游使用" in stripped):
            continue
        # Skip markdown table rows (|---|---|) and table content about K values
        if stripped.startswith("|") and ("K1" in stripped or "主导" in stripped
                or "---" in stripped or "题号" in stripped):
            continue

        # Skip preamble / context lines (not actual options)
        if ("以下是" in stripped or "请选择" in stripped or "请审阅" in stripped
                or "请你选择" in stripped or "已选方向" in stripped
                or "具体考察模式细化" in stripped or "参考真题" in stripped):
            continue

        # Check for annotation / blockquote
        annot_match = _RE_ANNOTATION.match(stripped)
        if annot_match:
            _flush_detail()
            annotation = annot_match.group(1).strip()
            continue

        # Try checkbox option line [ ] or [✓] or [✗]
        opt_match = _RE_CHECKBOX_LINE.match(stripped)
        if opt_match:
            _flush_detail()
            opt_counter += 1
            raw_text = opt_match.group(1).strip()
            text, cog = _split_cognitive(raw_text)
            options.append(
                DraftOption(
                    id=f"opt_{section_idx}_{opt_counter}",
                    text=_sanitize_teacher_text(_strip_markdown(text)),
                    cognitive_desc=_sanitize_teacher_text(cog),
                )
            )
            continue

        # Continuation lines after a checkbox option: accumulate as detail
        # (e.g. "- 给出一组元素序列..." or plain description lines)
        # Dash lines that are NOT checkbox options go here
        dash_match = _RE_DASH_LINE.match(stripped)
        if dash_match and options:
            _pending_detail.append(dash_match.group(1).strip())
            continue

        # Plain text line — treat as option only if substantive (>10 chars)
        # and not a header or obvious non-option text
        if len(stripped) > 10 and _RE_PLAIN_OPTION.match(stripped) and not stripped.startswith("#"):
            opt_counter += 1
            text, cog = _split_cognitive(stripped)
            options.append(
                DraftOption(
                    id=f"opt_{section_idx}_{opt_counter}",
                    text=_sanitize_teacher_text(text),
                    cognitive_desc=_sanitize_teacher_text(cog),
                )
            )

    _flush_detail()
    return options, _sanitize_teacher_text(annotation)


def _split_cognitive(text: str) -> tuple[str, str]:
    """Split trailing cognitive description from option text.

    "地址字段划分计算（需一步公式推导）" → ("地址字段划分计算", "需一步公式推导")
    """
    matches = list(_RE_COGNITIVE.finditer(text))
    if not matches:
        return text, ""

    match = matches[-1]
    if text[match.end():].strip():
        return text, ""

    cog = match.group(1).strip()
    # Remove the trailing cognitive parenthetical from display text
    clean = text[: match.start()].strip()
    return clean, cog


def _strip_markdown(text: str) -> str:
    """Strip markdown formatting from option text for clean display."""
    if not text:
        return text
    # Remove bold markers **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # Remove italic markers *text*
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # Remove inline code markers `text`
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


def _sanitize_teacher_text(text: str) -> str:
    """Remove internal K1-K5 labels from teacher-facing API text."""
    if not text:
        return text

    sanitized = re.sub(r"K([1-5])\s*[:=]\s*[1-5]", lambda m: _K_TERM_MAP[m.group(1)], text)

    def replace_k_term(match: re.Match) -> str:
        label = _K_TERM_MAP[match.group(1)]
        following = sanitized[match.end():].lstrip(" ：:=，,")
        if following.startswith(label):
            return ""
        if following.startswith(f"（{label}") or following.startswith(f"({label}"):
            return ""
        return label

    return re.sub(r"K([1-5])", replace_k_term, sanitized)
