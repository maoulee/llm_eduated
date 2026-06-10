"""Draft parser — bidirectional conversion between markdown drafts and JSON.

Handles parsing agent-generated markdown drafts into structured DraftData,
rendering pruning annotations back to markdown, and detecting drafts in
agent responses.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from api.schemas.interact_v2 import (
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

# Option line: starts with [ ], [✓], [✗], or "- "
_RE_OPTION_LINE = re.compile(r"^\s*(?:\[[ x✓✗]\]\s*|-\s+)(.+)$")

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

    # --- Scenario heuristic ---
    scenario = _detect_scenario(md_text)

    # --- Split into sections by level-2 heading positions ---
    h2_positions = [m.start() for m in _RE_H2.finditer(md_text)]
    h2_headers = [m.group(1).strip() for m in _RE_H2.finditer(md_text)]

    if not h2_positions:
        # No sections found — return DraftData with raw_md only
        return DraftData(
            draft_id=draft_id,
            title=title,
            scenario=scenario,
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

        # Slot ID
        slot_match = _RE_SLOT_ID.search(header_text)
        slot_id = slot_match.group(1).upper() if slot_match else f"Q{idx + 1}"

        # Parse options and annotation from body
        options, annotation = _parse_section_body(body, idx + 1)

        sections.append(
            DraftSlot(
                slot_id=slot_id,
                title=header_text,
                options=options,
                annotation=annotation,
            )
        )

    return DraftData(
        draft_id=draft_id,
        title=title,
        scenario=scenario,
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
    lines: list[str] = []

    for sa in annotation.slots:
        slot = slot_map.get(sa.slot_id)
        if slot is None:
            continue

        lines.append(f"## {slot.title}")

        # Build option id → DraftOption map
        opt_map = {o.id: o for o in slot.options}

        for opt_id in sa.kept_options:
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

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Skip level-2 header line itself
        if stripped.startswith("## "):
            continue

        # Check for annotation / blockquote
        annot_match = _RE_ANNOTATION.match(stripped)
        if annot_match:
            annotation = annot_match.group(1).strip()
            continue

        # Try checkbox / dash option line
        opt_match = _RE_OPTION_LINE.match(stripped)
        if opt_match:
            opt_counter += 1
            raw_text = opt_match.group(1).strip()
            text, cog = _split_cognitive(raw_text)
            options.append(
                DraftOption(
                    id=f"opt_{section_idx}_{opt_counter}",
                    text=text,
                    cognitive_desc=cog,
                )
            )
            continue

        # Plain text line — treat as option only if substantive (>10 chars)
        # and not a header or obvious non-option text
        if len(stripped) > 10 and _RE_PLAIN_OPTION.match(stripped) and not stripped.startswith("#"):
            opt_counter += 1
            text, cog = _split_cognitive(stripped)
            options.append(
                DraftOption(
                    id=f"opt_{section_idx}_{opt_counter}",
                    text=text,
                    cognitive_desc=cog,
                )
            )

    return options, annotation


def _split_cognitive(text: str) -> tuple[str, str]:
    """Split trailing cognitive description from option text.

    "地址字段划分计算（需一步公式推导）" → ("地址字段划分计算", "需一步公式推导")
    """
    match = _RE_COGNITIVE.search(text)
    if not match:
        return text, ""

    cog = match.group(1).strip()
    # Remove the trailing cognitive parenthetical from display text
    clean = text[: match.start()].strip()
    return clean, cog
