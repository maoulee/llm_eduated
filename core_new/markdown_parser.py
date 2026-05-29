# core_new/markdown_parser.py

"""
Markdown-to-dict parser for LLM extraction output (P1-P4).

Drop-in replacement for the JSON extraction pipeline: converts structured
Markdown that a model may emit into the same dict format that the current
JSON-based extraction pipeline produces.

Usage:
    from core_new.markdown_parser import parse_extraction_markdown

    result = parse_extraction_markdown(md_text, "P1")
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known boolean / numeric fields so we can coerce string values
# ---------------------------------------------------------------------------
_BOOLEAN_FIELDS = {
    "can_verify_with_code",
    "is_consistent",
    "structure_complete",
    "knowledge_units_complete",
    "triggers_accurate",
    "pattern_consistent",
    "distractors_aligned_with_errors",
    "is_ready_for_review",
    "is_ready_for_db",
    "requires_human_or_rule_check",
}

_INT_FIELDS = {
    "order",
    "step",
}

_FLOAT_FIELDS = {
    "diagnostic_value",
    "overall_quality_score",
}

# ---------------------------------------------------------------------------
# Core helper functions
# ---------------------------------------------------------------------------

_THINKING_RE = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.DOTALL | re.IGNORECASE)
_REASONING_RE = re.compile(r"<reasoning\b[^>]*>.*?</reasoning\s*>", re.DOTALL | re.IGNORECASE)
# Match only ## and ### level headers for top-level section splitting.
# #### headers are left inside their parent section so that
# _extract_subsection can find them.
_SECTION_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
# Matches any header level 2-4 (used by _extract_subsection internally).
_SUBSECTION_HEADER_RE = re.compile(r"^#{2,4}\s+", re.MULTILINE)


def _strip_thinking(text: str) -> str:
    """Remove <think ...>...</think or <reasoning ...>...</reasoning blocks."""
    text = _THINKING_RE.sub("", text)
    text = _REASONING_RE.sub("", text)
    return text.strip()


def _extract_sections(text: str) -> Dict[str, str]:
    """Parse ### or ## headers into ``{header: content_between_headers}``.

    Only ``##`` and ``###`` level headers are recognised as section
    boundaries.  ``####`` sub-headers remain inside their parent section
    so they can be extracted by :func:`_extract_subsection`.
    """
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return {}

    sections: Dict[str, str] = {}
    for i, m in enumerate(matches):
        header = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[header] = text[start:end].strip()
    return sections


def _extract_subsection(text: str, heading: str) -> str:
    """Return the content under a ``#### heading`` (or ``### heading``)
    within *text*, up to the next same-or-higher-level header.

    Tolerates leading whitespace before the header markers.
    """
    pat = re.compile(
        r"^\s*#{2,4}\s+" + re.escape(heading) + r"\s*\n",
        re.MULTILINE,
    )
    m = pat.search(text)
    if not m:
        return ""
    start = m.end()
    # next header at level 2-4 (allowing leading whitespace)
    next_header = re.search(r"^\s*#{2,4}\s+", text[start:], re.MULTILINE)
    end = start + next_header.start() if next_header else len(text)
    return text[start:end].strip()


def _extract_list_items(text: str) -> List[str]:
    """Extract ``- list items`` from *text*.

    Returns each item as the full text including any continuation lines
    that are indented relative to the bullet.
    """
    items: List[str] = []
    lines = text.split("\n")
    current: Optional[str] = None

    for line in lines:
        bullet_match = re.match(r"^\s*[-*]\s+(.*)", line)
        if bullet_match:
            if current is not None:
                items.append(current.strip())
            current = bullet_match.group(1)
        elif current is not None and line.strip():
            # Continuation line -- must be indented or non-empty
            current += "\n" + line
        elif current is not None and not line.strip():
            # Blank line terminates the current item only if next line
            # is not a continuation.
            items.append(current.strip())
            current = None

    if current is not None:
        items.append(current.strip())

    return [item for item in items if item]


def _extract_key_value_pairs(text: str) -> Dict[str, str]:
    """Extract ``key: value`` pairs from a text block.

    Handles lines like:
        question_type: 单选题
        stem: 题干内容...

    Lines may have leading whitespace.  Keys that start with ``- `` are
    excluded (those are list items, not key-value pairs).
    """
    pairs: Dict[str, str] = {}
    for m in re.finditer(r"^\s*(\S+)\s*[:：]\s*(.+)$", text, re.MULTILINE):
        key = m.group(1).strip()
        # Skip list markers
        if key.startswith("-") or key.startswith("*"):
            continue
        value = m.group(2).strip()
        pairs[key] = value
    return pairs


def _parse_pipe_record(text: str) -> Dict[str, str]:
    """Parse a record with ``|`` separated fields.

    Example::
        选项: A | 错误类型: xxx | 针对的误解: yyy

    Returns ``{"选项": "A", "错误类型": "xxx", "针对的误解": "yyy"}``.
    """
    result: Dict[str, str] = {}
    parts = text.split("|")
    for part in parts:
        part = part.strip()
        m = re.match(r"(.+?)\s*[:：]\s*(.*)", part)
        if m:
            result[m.group(1).strip()] = m.group(2).strip()
    return result


def _coerce_value(key: str, value: Any) -> Any:
    """Coerce string values to the expected type for known fields."""
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if key in _BOOLEAN_FIELDS:
        low = stripped.lower()
        if low in ("true", "yes", "1"):
            return True
        if low in ("false", "no", "0"):
            return False
    if key in _INT_FIELDS:
        try:
            return int(float(stripped))
        except (ValueError, TypeError):
            return value
    if key in _FLOAT_FIELDS:
        try:
            return float(stripped)
        except (ValueError, TypeError):
            return value
    return value


def _parse_nested_list_items(text: str) -> List[Dict[str, str]]:
    """Parse list items that have sub-properties on indented lines.

    Example::

        - name: 知识名称
          description: 具体内容
          subtype: definition
          subject: 计算机组成原理
        - name: 另一个知识
          ...

    Returns a list of dicts.
    """
    items: List[Dict[str, str]] = []
    # Split on bullet markers at the start of a line
    raw_items = _extract_list_items(text)
    for raw in raw_items:
        props: Dict[str, str] = {}
        for m in re.finditer(r"(\w[\w_]*)\s*[:：]\s*(.+?)(?:\n|$)", raw):
            props[m.group(1).strip()] = m.group(2).strip()
        if props:
            items.append(props)
    return items


def _try_json_parse(text: str) -> Optional[Dict[str, Any]]:
    """Attempt to extract and parse JSON from *text*.

    Looks for a ```json ... ``` fence first, then tries the whole text.
    """
    # Try fenced JSON block first
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # Try the whole text
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            result = json.loads(stripped)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    return None


def parse_md_kv(lines: List[str]) -> Dict[str, Any]:
    """Parse '- **key**: value' or '- key: value' lines into a dict.

    Handles both English (:) and Chinese (：) colons, and keys with or
    without bold markers (**).
    """
    result: Dict[str, Any] = {}
    current_key = None

    for line in lines:
        m = re.match(r"^-\s+\*\*(.+?)\*\*[:：]\s*(.*)", line)
        if not m:
            m = re.match(r"^-\s+([^*:：]+?)[:：]\s*(.*)", line)
        if m:
            key = m.group(1).strip()
            value = m.group(2).strip()
            if value and (value.startswith("{") or value.startswith("[")):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
            result[key] = value
            current_key = key
        elif line.startswith("  ") and current_key and current_key in result:
            existing = result[current_key]
            if isinstance(existing, str):
                result[current_key] = existing + "\n" + line.strip()
        elif current_key and current_key in result and isinstance(result[current_key], str):
            result[current_key] = result[current_key] + "\n" + line

    return result


def parse_md_sections(text: str) -> Dict[str, Any]:
    """Split markdown by ## headers, parse each section's key-value pairs."""
    sections: Dict[str, Any] = {}
    current_name = None
    current_lines: List[str] = []

    for line in text.split("\n"):
        m = re.match(r"^##\s+(.+)", line)
        if m:
            if current_name:
                sections[current_name] = parse_md_kv(current_lines)
            current_name = m.group(1).strip()
            current_lines = []
        elif current_name:
            current_lines.append(line)

    if current_name:
        sections[current_name] = parse_md_kv(current_lines)

    return sections


# ---------------------------------------------------------------------------
# Unified structured output parser for LLM agents
# ---------------------------------------------------------------------------

def parse_structured_output(
    raw: str,
    *,
    md_sections: tuple[str, ...] = (),
    json_nested_key: str | None = None,
) -> Dict[str, Any]:
    """Unified LLM output parser with automatic fallback chain.

    Strategy:
    1. Try JSON: if json_nested_key, extract that sub-dict; else use flat.
    2. Try markdown ## sections: merge all specified section dicts.
    3. Try any ## section that contains a requested key.
    4. Return empty dict.

    Args:
        raw: Raw LLM output text.
        md_sections: Ordered section names to merge (e.g. ``("stem",)`` or
            ``("options", "distractors", "answer")``).
        json_nested_key: If the JSON output has a nested dict under this key,
            return that instead of the top-level dict.

    Returns:
        Merged dict from whichever parsing strategy succeeded.
    """
    text = str(raw).strip()
    if not text:
        return {}

    # Strip code fences (GLM-5.1 sometimes wraps markdown in ```...```)
    text = re.sub(r"^```(?:\w+)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    # ── Strategy 1: JSON ──
    data = try_parse_json_object(text)
    if data:
        if json_nested_key:
            nested = data.get(json_nested_key)
            if isinstance(nested, dict):
                return nested
        # Use flat if it has any useful keys
        if any(not k.startswith("_") for k in data):
            return data

    # ── Strategy 2: Markdown ## sections ──
    sections = parse_md_sections(text)
    if md_sections:
        merged: Dict[str, Any] = {}
        for sec_name in md_sections:
            sec = sections.get(sec_name)
            if isinstance(sec, dict):
                merged.update(sec)
        if merged:
            return merged

    # ── Strategy 3: Any section with requested keys ──
    if md_sections:
        for _name, sec in sections.items():
            if isinstance(sec, dict) and any(sec.get(k) for k in md_sections):
                return sec

    return {}


def try_parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Public helper: parse a dict from fenced JSON or whole-text JSON."""
    return _try_json_parse(text)


# ---------------------------------------------------------------------------
# P1 parser
# ---------------------------------------------------------------------------

def _parse_p1(md_text: str) -> Dict[str, Any]:
    """Parse P1 (question structure) Markdown into the P1 schema dict."""
    result: Dict[str, Any] = {}
    sections = _extract_sections(md_text)

    # --- 基本信息 ---
    basic = sections.get("基本信息", "")
    kv = _extract_key_value_pairs(basic)
    result["question_type"] = kv.get("question_type", kv.get("题目类型", ""))
    result["subject"] = kv.get("subject", kv.get("科目", ""))
    result["year"] = kv.get("year", kv.get("年份", ""))
    result["stem"] = kv.get("stem", kv.get("题干", ""))
    result["correct_answer"] = kv.get("correct_answer", kv.get("正确答案", ""))

    # --- 选项 ---
    options_text = sections.get("选项", "")
    options: Dict[str, str] = {}
    for m in re.finditer(
        r"^\s*[-*]\s*([A-Da-d])\s*[:：]\s*(.+)$", options_text, re.MULTILINE
    ):
        options[m.group(1).upper()] = m.group(2).strip()
    # Fallback: look for A: xxx style without bullet
    if not options:
        for m in re.finditer(
            r"^([A-Da-d])\s*[:：]\s*(.+)$", options_text, re.MULTILINE
        ):
            options[m.group(1).upper()] = m.group(2).strip()
    result["options"] = options

    # --- 结构分析 ---
    structure_text = sections.get("结构分析", "")
    structure: Dict[str, Any] = {
        "given_conditions": [],
        "asked_target": "",
        "hidden_constraints": [],
        "unit_constraints": [],
        "key_terms": [],
    }

    sub_map = {
        "已知条件": "given_conditions",
        "given_conditions": "given_conditions",
        "求解目标": "asked_target",
        "asked_target": "asked_target",
        "隐含条件": "hidden_constraints",
        "hidden_constraints": "hidden_constraints",
        "单位约束": "unit_constraints",
        "unit_constraints": "unit_constraints",
        "关键术语": "key_terms",
        "key_terms": "key_terms",
    }

    for cn_name, en_name in sub_map.items():
        sub_text = _extract_subsection(structure_text, cn_name)
        if not sub_text:
            continue
        if en_name == "asked_target":
            # Single value, not a list
            structure[en_name] = sub_text.strip()
        else:
            structure[en_name] = _extract_list_items(sub_text)

    result["structure"] = structure

    # --- 干扰项分析 ---
    distractor_text = sections.get("干扰项分析", "")
    distractors: List[Dict[str, str]] = []
    for item in _extract_list_items(distractor_text):
        pipe_rec = _parse_pipe_record(item)
        if pipe_rec:
            distractors.append({
                "option": pipe_rec.get("选项", pipe_rec.get("option", "")),
                "content": pipe_rec.get("内容", pipe_rec.get("content", "")),
                "error_type": pipe_rec.get("错误类型", pipe_rec.get("error_type", "")),
                "targeted_misconception": pipe_rec.get(
                    "针对的误解",
                    pipe_rec.get("targeted_misconception", ""),
                ),
            })
        else:
            # Fallback: try key: value pairs in the item
            kv2 = _extract_key_value_pairs(item)
            if kv2:
                distractors.append({
                    "option": kv2.get("选项", kv2.get("option", "")),
                    "content": kv2.get("内容", kv2.get("content", "")),
                    "error_type": kv2.get("错误类型", kv2.get("error_type", "")),
                    "targeted_misconception": kv2.get(
                        "针对的误解",
                        kv2.get("targeted_misconception", ""),
                    ),
                })

    result["distractor_analysis"] = distractors

    # --- 正确答案诊断 ---
    diagnosis_text = sections.get("正确答案诊断", "")
    diag_kv = _extract_key_value_pairs(diagnosis_text)
    result["correct_answer_diagnosis"] = {
        "answer_status": diag_kv.get(
            "answer_status",
            diag_kv.get("答案状态", ""),
        ),
        "diagnostic_note": diag_kv.get(
            "diagnostic_note",
            diag_kv.get("诊断备注", ""),
        ),
    }

    return result


# ---------------------------------------------------------------------------
# P2 parser
# ---------------------------------------------------------------------------

def _parse_p2(md_text: str) -> Dict[str, Any]:
    """Parse P2 (knowledge units) Markdown into the P2 schema dict."""
    result: Dict[str, Any] = {}
    sections = _extract_sections(md_text)

    # --- 知识单元 ---
    ku_text = sections.get("知识单元", "")
    ku_items = _parse_nested_list_items(ku_text)
    knowledge_units: List[Dict[str, str]] = []
    for item in ku_items:
        knowledge_units.append({
            "name": item.get("name", item.get("名称", "")),
            "description": item.get("description", item.get("描述", item.get("具体内容", ""))),
            "subtype": item.get("subtype", item.get("子类型", "")),
            "subject": item.get("subject", item.get("科目", "")),
        })
    result["knowledge_units"] = knowledge_units

    # --- 机制 ---
    mech_text = sections.get("机制", "")
    mech_items = _parse_nested_list_items(mech_text)
    mechanisms: List[Dict[str, str]] = []
    for item in mech_items:
        mechanisms.append({
            "name": item.get("name", item.get("名称", "")),
            "description": item.get("description", item.get("描述", item.get("具体内容", ""))),
            "affects_what": item.get("affects_what", item.get("影响什么", "")),
            "common_misunderstanding": item.get(
                "common_misunderstanding",
                item.get("常见误解", ""),
            ),
            "subject": item.get("subject", item.get("科目", "")),
        })
    result["mechanisms"] = mechanisms

    return result


# ---------------------------------------------------------------------------
# P3 parser
# ---------------------------------------------------------------------------

def _parse_source_signals(text: str) -> List[Dict[str, str]]:
    """Parse source_signals from a trigger rule block.

    Expected sub-format::

        - signal_type: keyword
          value: 具体信号
    """
    items = _parse_nested_list_items(text)
    signals: List[Dict[str, str]] = []
    for item in items:
        if "signal_type" in item or "value" in item:
            signals.append({
                "signal_type": item.get("signal_type", ""),
                "value": item.get("value", ""),
            })
    return signals


def _parse_activation_condition(text: str) -> Dict[str, Any]:
    """Parse an activation_condition block."""
    kv = _extract_key_value_pairs(text)
    logic = kv.get("logic", "AND")
    # Extract conditions as list items
    cond_items = _extract_list_items(text)
    return {
        "logic": logic,
        "conditions": cond_items if cond_items else [],
    }


def _parse_activates(text: str) -> Dict[str, Any]:
    """Parse an activates block.

    Handles both forms:
    1. ``targets`` array with ``target_type``, ``target_name``, ``action``
    2. ``mechanism_names`` list + ``action`` scalar
    """
    kv = _extract_key_value_pairs(text)
    action = kv.get("action", "activate")

    # Look for mechanism_names or target lines
    mechanism_names: List[str] = []
    targets: List[Dict[str, str]] = []

    # Try to parse nested target items
    target_items = _parse_nested_list_items(text)
    for item in target_items:
        if "target_type" in item or "target_name" in item:
            targets.append({
                "target_type": item.get("target_type", ""),
                "target_name": item.get("target_name", ""),
                "action": item.get("action", action),
            })
        elif "name" in item:
            mechanism_names.append(item["name"])

    # Also try to extract plain list items that might be mechanism names
    list_items = _extract_list_items(text)
    for li in list_items:
        # Skip items that look like key-value pairs (already handled)
        if re.match(r"\w[\w_]*\s*[:：]", li):
            continue
        mechanism_names.append(li.strip())

    if targets:
        return {"targets": targets}
    if mechanism_names:
        return {"mechanism_names": mechanism_names, "action": action}
    return {"action": action}


def _parse_generation_constraints(text: str) -> Dict[str, Any]:
    """Parse generation_constraints sub-block."""
    kv = _extract_key_value_pairs(text)
    must_include = _extract_list_items(
        _extract_subsection(text, "must_include_signals")
        if _extract_subsection(text, "must_include_signals")
        else text
    )

    # Filter list items that are actually signal items (not key:value)
    signals = [
        item for item in must_include
        if not re.match(r"^\w[\w_]*\s*[:：]", item)
    ]

    return {
        "must_include_signals": signals if signals else [],
        "must_expose_failure_mode": kv.get(
            "must_expose_failure_mode",
            kv.get("必须暴露的错误模式", ""),
        ),
        "expected_wrong_reason_if_missed": kv.get(
            "expected_wrong_reason_if_missed",
            kv.get("漏掉时的典型错误", ""),
        ),
    }


def _strip_leading_bullet(text: str) -> str:
    """Remove leading ``- `` or ``* `` from the first line of *text*."""
    return re.sub(r"^[-*]\s+", "", text, count=1)


def _dedent_lines(text: str) -> str:
    """Remove common leading whitespace from all lines in *text*.

    This is a simple left-strip: removes the minimum leading spaces shared
    by all non-empty lines (or just the first-line indent if that is easier).
    In practice we just strip leading spaces from each line.
    """
    lines = text.split("\n")
    # Find minimum indent (ignoring blank lines)
    min_indent = float("inf")
    for line in lines:
        stripped = line.lstrip()
        if stripped:
            indent = len(line) - len(stripped)
            min_indent = min(min_indent, indent)
    if min_indent == float("inf"):
        min_indent = 0
    return "\n".join(
        line[min_indent:] if len(line) >= min_indent else line
        for line in lines
    )


def _parse_single_trigger_rule(text: str) -> Dict[str, Any]:
    """Parse a single trigger rule from its text block."""
    rule: Dict[str, Any] = {}

    # Normalise: strip the leading "- " and dedent so #### sub-headers
    # are at column 0.
    text = _strip_leading_bullet(text)
    text = _dedent_lines(text)

    # Only extract top-level key:value pairs (before the first #### header)
    first_sub = _SUBSECTION_HEADER_RE.search(text)
    top_text = text[:first_sub.start()] if first_sub else text
    kv = _extract_key_value_pairs(top_text)

    rule["name"] = kv.get("name", kv.get("名称", ""))
    rule["diagnostic_role"] = kv.get(
        "diagnostic_role",
        kv.get("诊断角色", ""),
    )
    rule["difficulty"] = kv.get("difficulty", kv.get("难度", "medium"))
    rule["diagnostic_value"] = _coerce_value(
        "diagnostic_value", kv.get("diagnostic_value", "0.0")
    )

    # source_signals sub-section
    sig_text = _extract_subsection(text, "source_signals")
    if sig_text:
        rule["source_signals"] = _parse_source_signals(sig_text)
    else:
        rule["source_signals"] = []

    # activation_condition sub-section
    ac_text = _extract_subsection(text, "activation_condition")
    if ac_text:
        rule["activation_condition"] = _parse_activation_condition(ac_text)
    else:
        rule["activation_condition"] = {"logic": "AND", "conditions": []}

    # activates sub-section
    act_text = _extract_subsection(text, "activates")
    if act_text:
        rule["activates"] = _parse_activates(act_text)
    else:
        rule["activates"] = {"action": "activate"}

    # wrong_if_missing list
    wim_text = _extract_subsection(text, "wrong_if_missing")
    if wim_text:
        rule["wrong_if_missing"] = _extract_list_items(wim_text)
    else:
        rule["wrong_if_missing"] = []

    # generation_constraints sub-section
    gc_text = _extract_subsection(text, "generation_constraints")
    if gc_text:
        rule["generation_constraints"] = _parse_generation_constraints(gc_text)
    else:
        rule["generation_constraints"] = {
            "must_include_signals": [],
            "must_expose_failure_mode": "",
            "expected_wrong_reason_if_missed": "",
        }

    return rule


def _split_top_level_bullets(text: str) -> List[str]:
    """Split *text* at top-level ``- `` bullets only.

    A top-level bullet is a ``- `` (or ``* ``) that appears at the start of
    a line with no indentation.  Continuation lines (indented or ``####``
    sub-headers) are collected as part of the current bullet.  Nested
    bullets (indented ``- ``) are kept inside their parent.
    """
    items: List[str] = []
    lines = text.split("\n")
    current_lines: List[str] = []

    for line in lines:
        # A top-level bullet starts with "- " or "* " at column 0
        if re.match(r"^[-*]\s", line):
            if current_lines:
                items.append("\n".join(current_lines).strip())
            current_lines = [line]
        elif current_lines:
            # Continuation -- anything that follows a top-level bullet
            current_lines.append(line)
        # else: text before the first bullet is ignored

    if current_lines:
        items.append("\n".join(current_lines).strip())

    return [item for item in items if item]


def _parse_p3(md_text: str) -> Dict[str, Any]:
    """Parse P3 (trigger rules) Markdown into the P3 schema dict."""
    result: Dict[str, Any] = {}
    sections = _extract_sections(md_text)

    # --- 触发规则 ---
    tr_text = sections.get("触发规则", "")
    trigger_rules: List[Dict[str, Any]] = []
    for raw in _split_top_level_bullets(tr_text):
        rule = _parse_single_trigger_rule(raw)
        if rule.get("name"):
            trigger_rules.append(rule)
    result["trigger_rules"] = trigger_rules

    # --- 负触发 ---
    nt_text = sections.get("负触发", "")
    negative_triggers: List[Dict[str, str]] = []
    for item in _parse_nested_list_items(nt_text):
        negative_triggers.append({
            "signal": item.get("signal", item.get("信号", "")),
            "blocks_pattern": item.get("blocks_pattern", item.get("阻断模式", "")),
            "reason": item.get("reason", item.get("原因", "")),
        })
    result["negative_triggers"] = negative_triggers

    return result


# ---------------------------------------------------------------------------
# P4 parser
# ---------------------------------------------------------------------------

def _parse_p4(md_text: str) -> Dict[str, Any]:
    """Parse P4 (reasoning pattern) Markdown into the P4 schema dict."""
    result: Dict[str, Any] = {}
    sections = _extract_sections(md_text)

    # Top-level key:value pairs (before the first ### header)
    top_match = _SECTION_RE.search(md_text)
    top_text = md_text[:top_match.start()] if top_match else md_text
    top_kv = _extract_key_value_pairs(top_text)

    result["pattern_name"] = top_kv.get("pattern_name", top_kv.get("模式名称", ""))
    result["subject"] = top_kv.get("subject", top_kv.get("科目", ""))

    # --- 适用条件 ---
    ac_text = sections.get("适用条件", "")
    result["applicable_conditions"] = _extract_list_items(ac_text)

    # --- 推理步骤 ---
    steps_text = sections.get("推理步骤", "")
    step_items = _parse_nested_list_items(steps_text)
    steps: List[Dict[str, Any]] = []
    for item in step_items:
        step: Dict[str, Any] = {}
        step["order"] = _coerce_value("order", item.get("order", item.get("顺序", 0)))
        step["name"] = item.get("name", item.get("名称", ""))
        step["description"] = item.get("description", item.get("描述", ""))
        step["input"] = item.get("input", item.get("输入", ""))
        step["output"] = item.get("output", item.get("输出", ""))

        # required_knowledge may be comma-separated or a sub-list
        rk = item.get("required_knowledge", item.get("所需知识", ""))
        if rk:
            # Try splitting on commas or Chinese commas
            parts = re.split(r"[,，]", rk)
            step["required_knowledge"] = [p.strip() for p in parts if p.strip()]
        else:
            step["required_knowledge"] = []

        step["common_error_at_this_step"] = item.get(
            "common_error_at_this_step",
            item.get("常见错误", ""),
        )
        steps.append(step)
    result["steps"] = steps

    # --- 常见断点 ---
    bp_text = sections.get("常见断点", "")
    bp_items = _parse_nested_list_items(bp_text)
    breakpoints: List[Dict[str, Any]] = []
    for item in bp_items:
        breakpoints.append({
            "step": _coerce_value("step", item.get("step", item.get("步骤", 0))),
            "reason": item.get("reason", item.get("原因", "")),
            "error_manifestation": item.get(
                "error_manifestation",
                item.get("错误表现", ""),
            ),
        })
    result["common_breakpoints"] = breakpoints

    # Bottom-level key:value pairs (can_verify_with_code, verification_approach)
    # Look in the text after the last ### section
    all_section_matches = list(_SECTION_RE.finditer(md_text))
    if all_section_matches:
        last_end = all_section_matches[-1].end()
        # Find where the content of the last section effectively ends
        # by looking for trailing key:value lines at the root level
        remaining = md_text[last_end:]
        # Extract trailing key:value lines that are NOT inside a list
        trailing_lines: List[str] = []
        for line in remaining.split("\n"):
            stripped = line.strip()
            if re.match(r"^\w[\w_]*\s*[:：]", stripped) and not stripped.startswith("-"):
                trailing_lines.append(stripped)
        trailing_text = "\n".join(trailing_lines)
        trail_kv = _extract_key_value_pairs(trailing_text)
    else:
        trail_kv = {}

    result["can_verify_with_code"] = _coerce_value(
        "can_verify_with_code",
        trail_kv.get("can_verify_with_code", top_kv.get("can_verify_with_code", False)),
    )
    result["verification_approach"] = trail_kv.get(
        "verification_approach",
        top_kv.get("verification_approach", ""),
    )

    return result


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

_PASS_PARSERS = {
    "P1": _parse_p1,
    "P2": _parse_p2,
    "P3": _parse_p3,
    "P4": _parse_p4,
}


def parse_extraction_markdown(
    md_text: str,
    pass_name: str,
) -> Optional[Dict[str, Any]]:
    """Parse structured Markdown into a dict matching the current JSON schema.

    This is the main entry point.  It strips thinking artifacts from the
    model output, attempts Markdown parsing first, and falls back to a
    plain JSON parse if the Markdown route returns an empty or obviously
    broken result.

    Args:
        md_text: Raw Markdown (or mixed Markdown/JSON) from the model output.
        pass_name: One of ``"P1"``, ``"P2"``, ``"P3"``, ``"P4"``.

    Returns:
        A dict conforming to the pass-specific JSON schema, or ``None``
        on unrecoverable failure.
    """
    if not md_text or not md_text.strip():
        logger.warning("parse_extraction_markdown: empty input for %s", pass_name)
        return None

    pass_name = pass_name.upper()
    if pass_name not in _PASS_PARSERS:
        logger.error("parse_extraction_markdown: unknown pass %s", pass_name)
        return None

    cleaned = _strip_thinking(md_text)

    # --- Try JSON fallback first if the text looks like JSON ---
    json_result = _try_json_parse(cleaned)
    if json_result is not None:
        logger.info("parse_extraction_markdown: %s parsed as JSON directly", pass_name)
        return json_result

    # --- Markdown path ---
    try:
        parser = _PASS_PARSERS[pass_name]
        result = parser(cleaned)
        if result:
            logger.info(
                "parse_extraction_markdown: %s parsed from Markdown", pass_name
            )
            return result
    except Exception:
        logger.exception(
            "parse_extraction_markdown: Markdown parse failed for %s", pass_name
        )

    return None
