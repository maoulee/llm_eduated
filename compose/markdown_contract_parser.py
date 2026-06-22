"""Unified markdown contract parser — CONTRACT marker + YAML parse + validate.

Principle: Markdown is for humans, YAML contracts are for machines.
System reads contracts via HTML comment anchors, never guesses from prose.

Layers:
  1. MarkdownBlockScanner  — find contract blocks in MD
  2. YamlContractLoader    — parse YAML with error capture
  3. ContractNormalizer    — normalize field aliases
  4. ContractValidator     — schema + consistency checks
  5. parse_outline_to_selection — top-level entry point
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from compose.outline_contract_parser import SlotContract


# ── Data types ──────────────────────────────────────────────

@dataclass
class ContractBlock:
    """A located contract block within a markdown document."""
    yaml_text: str
    slot_id: str = ""
    block_type: str = "outline_slot"
    schema_version: str = ""
    start_line: int = 0
    end_line: int = 0
    source: str = ""  # "marker" | "legacy_heading"
    surrounding_text: str = ""  # text around block (for teacher_annotation)


@dataclass
class LoadedContract:
    """Result of YAML parsing a ContractBlock."""
    data: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class OutlineHeader:
    """Global outline metadata from the header section."""
    difficulty_target: int = 3
    composition_rationale: str = ""


@dataclass
class ValidationIssue:
    check: str
    severity: str  # "error" | "warning" | "info"
    slot_id: str
    message: str


@dataclass
class ValidationResult:
    status: str  # "pass" | "warning" | "error"
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]


@dataclass
class ParseResult:
    """Full output of parse_outline_to_selection."""
    slots: list[SlotContract]
    header: OutlineHeader
    validation: ValidationResult
    report: str  # markdown parse report


# ── Layer 1: MarkdownBlockScanner ───────────────────────────

# HTML comment markers
_MARKER_BEGIN = re.compile(
    r"<!--\s*CONTRACT:BEGIN\s+"
    r"type=(\S+)\s+"
    r"schema=(\S+)\s+"
    r"slot=(Q?\d+(?:\w*)?)\s*-->",
)
_MARKER_END = re.compile(
    r"<!--\s*CONTRACT:END\s+slot=(Q?\d+(?:\w*)?)\s*-->",
)

# Legacy: heading + fenced yaml
_LEGACY_HEADING = re.compile(
    r"###\s*机器(?:选择)?契约\s*\n```(?:yaml|yml)\s*\n(.*?)```",
    re.DOTALL,
)

# Slot splitter for surrounding text
_SLOT_SPLIT = re.compile(r"## (Q\d+)")
_TEACHER_ANNOTATION = re.compile(
    r"###\s*教师可编辑说明[^\n]*\n(.*?)(?=\n###|\n## |\n<!-- CONTRACT:|\Z)",
    re.DOTALL,
)


def scan_contract_blocks(md: str) -> list[ContractBlock]:
    """Find all contract blocks in markdown.

    Priority: CONTRACT:BEGIN/END markers > legacy heading + yaml.
    """
    blocks: list[ContractBlock] = []
    lines = md.split("\n")

    # Pass 1: CONTRACT markers
    marker_slots_seen: set[str] = set()
    i = 0
    while i < len(lines):
        m_begin = _MARKER_BEGIN.search(lines[i])
        if m_begin:
            block_type, schema_ver, slot_id = m_begin.group(1), m_begin.group(2), m_begin.group(3)
            begin_line = i
            yaml_lines: list[str] = []
            j = i + 1
            found_end = False
            while j < len(lines):
                if _MARKER_END.search(lines[j]):
                    # Extract slot from end marker for cross-check
                    end_slot_m = _MARKER_END.search(lines[j])
                    end_slot = end_slot_m.group(1) if end_slot_m else ""
                    marker_slots_seen.add(slot_id)
                    blocks.append(ContractBlock(
                        yaml_text="\n".join(yaml_lines),
                        slot_id=slot_id,
                        block_type=block_type,
                        schema_version=schema_ver,
                        start_line=begin_line,
                        end_line=j,
                        source="marker",
                        surrounding_text=_extract_surrounding_text(md, begin_line, j),
                    ))
                    found_end = True
                    i = j + 1
                    break
                yaml_lines.append(lines[j])
                j += 1
            if not found_end:
                # Unclosed marker — skip
                i += 1
            continue
        i += 1

    # Pass 2: legacy heading-based (for slots not already found via marker)
    legacy_blocks = _scan_legacy_blocks(md)
    for lb in legacy_blocks:
        if lb.slot_id not in marker_slots_seen:
            blocks.append(lb)

    return blocks


def _scan_legacy_blocks(md: str) -> list[ContractBlock]:
    """Scan for legacy heading-based YAML blocks."""
    blocks: list[ContractBlock] = []
    parts = _SLOT_SPLIT.split(md)

    for i in range(1, len(parts), 2):
        slot_id = parts[i]
        content = parts[i + 1] if i + 1 < len(parts) else ""

        m = _LEGACY_HEADING.search(content)
        if not m:
            continue

        blocks.append(ContractBlock(
            yaml_text=m.group(1),
            slot_id=slot_id,
            source="legacy_heading",
            surrounding_text=content,
        ))

    return blocks


def _extract_surrounding_text(md: str, begin_line: int, end_line: int) -> str:
    """Extract text around a contract block for teacher_annotation extraction."""
    lines = md.split("\n")
    # Walk backward to find ## Qxx heading
    heading_line = begin_line
    for k in range(begin_line - 1, max(0, begin_line - 30), -1):
        if _SLOT_SPLIT.search(lines[k]):
            heading_line = k
            break
    # Walk forward to find next ## heading or end
    stop_line = end_line + 1
    for k in range(end_line + 1, min(len(lines), end_line + 60)):
        if _SLOT_SPLIT.search(lines[k]):
            stop_line = k
            break
    return "\n".join(lines[heading_line:stop_line])


# ── Layer 2: YamlContractLoader ─────────────────────────────

def _strip_fenced_block(text: str) -> str:
    """Strip fenced code block delimiters (```yaml ... ```) from captured text."""
    lines = text.strip().split("\n")
    # Strip opening fence (```yaml or ```yml)
    if lines and re.match(r"^```(?:yaml|yml)?\s*$", lines[0]):
        lines = lines[1:]
    # Strip closing fence (```)
    if lines and re.match(r"^```\s*$", lines[-1]):
        lines = lines[:-1]
    return "\n".join(lines)


def load_yaml_contract(block: ContractBlock) -> LoadedContract:
    """Parse YAML text from a ContractBlock. Never silently returns empty."""
    text = _strip_fenced_block(block.yaml_text)

    if not text.strip():
        return LoadedContract(
            data={},
            errors=[f"empty YAML block for slot {block.slot_id}"],
        )

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return LoadedContract(
            data={},
            errors=[f"YAML syntax error in slot {block.slot_id}: {e}"],
        )

    if not isinstance(data, dict):
        return LoadedContract(
            data={},
            errors=[f"YAML block for slot {block.slot_id} is not a mapping (got {type(data).__name__})"],
        )

    warnings: list[str] = []

    # Cross-check slot_id if marker provided one
    if block.slot_id and data.get("slot_id") and data["slot_id"] != block.slot_id:
        warnings.append(
            f"slot_id mismatch: marker says {block.slot_id}, YAML says {data['slot_id']}"
        )

    if block.source == "legacy_heading":
        warnings.append(f"slot {block.slot_id}: using legacy heading format, recommend CONTRACT markers")

    return LoadedContract(data=data or {}, warnings=warnings)


# ── Layer 3: ContractNormalizer ─────────────────────────────

# Field aliases: old name → canonical name
_FIELD_ALIASES: dict[str, str] = {
    "difficulty_level": "target_difficulty",
    "mode": "mode_id",
}

# Fields that should be nested under "excluded" if found flat
_FLAT_EXCLUDED_FIELDS = {
    "excluded_modes": ("modes", list),
    "excluded_knowledge": ("knowledge", list),
}


def normalize_outline_slot(data: dict) -> dict:
    """Normalize field aliases and structure."""
    out = dict(data)

    # 1. Rename aliases
    for old, canonical in _FIELD_ALIASES.items():
        if old in out and canonical not in out:
            out[canonical] = out.pop(old)

    # 2. Normalize active_selection aliases
    active = out.get("active_selection")
    if isinstance(active, dict):
        for old, canonical in _FIELD_ALIASES.items():
            if old in active and canonical not in active:
                active[canonical] = active.pop(old)

    # 3. Flatten excluded if it's a list (old broken format)
    excluded = out.get("excluded")
    if isinstance(excluded, list):
        out["excluded"] = {}

    # 4. Lift flat excluded fields into nested structure
    for flat_key, (sub_key, _type) in _FLAT_EXCLUDED_FIELDS.items():
        if flat_key in out:
            val = out.pop(flat_key)
            if isinstance(val, list) and val:
                excluded_dict = out.get("excluded")
                if not isinstance(excluded_dict, dict):
                    out["excluded"] = {}
                    excluded_dict = out["excluded"]
                excluded_dict[sub_key] = val

    # 5. Clean None/empty strings from top level
    for k in list(out.keys()):
        if out[k] is None:
            del out[k]

    return out


# ── Layer 4: ContractValidator ──────────────────────────────

# Fields whose absence is an error
_REQUIRED_FIELDS = ["slot_id", "question_type", "score", "examination_mode"]

# Fields whose absence is a warning
_RECOMMENDED_FIELDS = ["active_selection", "candidate_pool_visible"]


def validate_outline_slot(data: dict, teacher_annotation: str = "") -> ValidationResult:
    """Validate a normalized outline slot contract."""
    issues: list[ValidationIssue] = []
    slot_id = data.get("slot_id", "?")

    # Required fields
    for f in _REQUIRED_FIELDS:
        if f not in data or data[f] == "" or data[f] is None:
            issues.append(ValidationIssue(
                check=f"required_{f}", severity="error", slot_id=slot_id,
                message=f"missing required field: {f}",
            ))

    # Active selection checks
    active = data.get("active_selection")
    if isinstance(active, dict):
        mode_id = active.get("mode_id", "")
        selected = active.get("selected_knowledge", [])
        if isinstance(selected, str):
            selected = [selected]

        if not mode_id:
            issues.append(ValidationIssue(
                check="active_mode_id", severity="error", slot_id=slot_id,
                message="active_selection.mode_id is empty",
            ))

        if not selected:
            issues.append(ValidationIssue(
                check="selected_knowledge", severity="error", slot_id=slot_id,
                message="active_selection.selected_knowledge is empty",
            ))

        # active mode in candidate pool?
        pool = data.get("candidate_pool_visible", [])
        if mode_id and pool and mode_id not in pool:
            issues.append(ValidationIssue(
                check="mode_in_pool", severity="warning", slot_id=slot_id,
                message=f"mode_id={mode_id!r} not in candidate_pool_visible",
            ))

        # active mode not excluded
        excluded_modes = (data.get("excluded") or {}).get("modes", [])
        if mode_id and mode_id in excluded_modes:
            issues.append(ValidationIssue(
                check="excluded_not_active", severity="error", slot_id=slot_id,
                message=f"active mode {mode_id!r} is in excluded.modes",
            ))

        # selected vs excluded knowledge overlap
        excluded_knowledge = (data.get("excluded") or {}).get("knowledge", [])
        if selected and excluded_knowledge:
            overlap = set(selected) & set(excluded_knowledge)
            if overlap:
                issues.append(ValidationIssue(
                    check="knowledge_overlap", severity="error", slot_id=slot_id,
                    message=f"selected and excluded knowledge overlap: {sorted(overlap)}",
                ))
    else:
        issues.append(ValidationIssue(
            check="active_selection", severity="warning", slot_id=slot_id,
            message="no active_selection dict",
        ))

    # Warnings
    pool = data.get("candidate_pool_visible", [])
    if not pool:
        issues.append(ValidationIssue(
            check="pool_empty", severity="warning", slot_id=slot_id,
            message="candidate_pool_visible is empty",
        ))

    if not teacher_annotation:
        issues.append(ValidationIssue(
            check="annotation_empty", severity="info", slot_id=slot_id,
            message="teacher_annotation is empty",
        ))

    has_errors = any(i.severity == "error" for i in issues)
    has_warnings = any(i.severity == "warning" for i in issues)

    if has_errors:
        status = "error"
    elif has_warnings:
        status = "warning"
    else:
        status = "pass"

    return ValidationResult(status=status, issues=issues)


# ── Layer 5: Top-level entry ────────────────────────────────

def _parse_header(md: str) -> OutlineHeader:
    """Extract global outline metadata from header section."""
    header = md.split("## Q")[0] if "## Q" in md else md
    diff = 3
    dm = re.search(r"difficulty_target[*:\s]*(\d)", header)
    if dm:
        diff = int(dm.group(1))
    cm = re.search(r"composition_rationale[*:\s]*(.+?)(?:\n|$)", header)
    rationale = cm.group(1).strip() if cm else ""
    return OutlineHeader(difficulty_target=diff, composition_rationale=rationale)


def _extract_teacher_annotation(text: str) -> str:
    """Extract teacher annotation from surrounding text."""
    m = _TEACHER_ANNOTATION.search(text)
    if not m:
        return ""
    return m.group(1).strip()


def _generate_report(header: OutlineHeader, slots: list[SlotContract],
                     validation: ValidationResult) -> str:
    """Generate parse_report.md content."""
    lines = ["# Outline Parse Report\n"]
    lines.append(f"## status\n{validation.status}\n")

    errors = validation.errors
    warnings = validation.warnings
    infos = [i for i in validation.issues if i.severity == "info"]

    if errors:
        lines.append("## errors")
        for e in errors:
            lines.append(f"- {e.slot_id}: {e.message}")
        lines.append("")

    if warnings:
        lines.append("## warnings")
        for w in warnings:
            lines.append(f"- {w.slot_id}: {w.message}")
        lines.append("")

    if infos:
        lines.append("## info")
        for info in infos:
            lines.append(f"- {info.slot_id}: {info.message}")
        lines.append("")

    lines.append("## extracted_slots")
    for s in slots:
        lines.append(f"- {s.slot_id}: {s.question_type}, mode={s.examination_mode}")

    return "\n".join(lines)


def parse_outline_to_selection(md: str) -> ParseResult:
    """Full pipeline: scan → load → normalize → validate → SlotContracts.

    One call replaces all scattered regex parsing.
    """
    header = _parse_header(md)
    blocks = scan_contract_blocks(md)
    all_issues: list[ValidationIssue] = []
    slots: list[SlotContract] = []

    for block in blocks:
        # Load
        loaded = load_yaml_contract(block)
        for e in loaded.errors:
            all_issues.append(ValidationIssue(
                check="yaml_load", severity="error",
                slot_id=block.slot_id, message=e,
            ))
        for w in loaded.warnings:
            all_issues.append(ValidationIssue(
                check="yaml_load", severity="warning",
                slot_id=block.slot_id, message=w,
            ))
        if loaded.errors:
            continue

        # Normalize
        normalized = normalize_outline_slot(loaded.data)

        # Teacher annotation
        annotation = _extract_teacher_annotation(block.surrounding_text)

        # Validate
        slot_validation = validate_outline_slot(normalized, annotation)
        all_issues.extend(slot_validation.issues)

        # Build SlotContract
        excluded_data = normalized.get("excluded") or {}
        if isinstance(excluded_data, list):
            excluded_data = {}

        slots.append(SlotContract(
            slot_id=normalized.get("slot_id", block.slot_id),
            question_type=str(normalized.get("question_type", "single_choice")),
            score=int(normalized.get("score", 2)),
            examination_mode=normalized.get("examination_mode", ""),
            active_selection=normalized.get("active_selection", {}),
            candidate_pool_visible=normalized.get("candidate_pool_visible", []),
            excluded_modes=excluded_data.get("modes", []),
            excluded_knowledge=excluded_data.get("knowledge", []),
            teacher_annotation=annotation,
        ))

    # Aggregate validation
    has_errors = any(i.severity == "error" for i in all_issues)
    has_warnings = any(i.severity == "warning" for i in all_issues)
    agg_status = "error" if has_errors else ("warning" if has_warnings else "pass")
    validation = ValidationResult(status=agg_status, issues=all_issues)

    report = _generate_report(header, slots, validation)

    return ParseResult(
        slots=slots,
        header=header,
        validation=validation,
        report=report,
    )
