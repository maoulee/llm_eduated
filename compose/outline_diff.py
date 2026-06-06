"""Outline diff engine — dual-channel change detection for hybrid outlines.

Channel 1 (diff): Compare machine contract YAML fields between base and annotated.
Channel 2 (annotation): Extract non-empty teacher annotations from annotated.

Also provides validation of changes against slot templates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── Data structures ──────────────────────────────────────────────

@dataclass
class FieldChange:
    """A single field change detected by diff."""
    field: str       # e.g. "difficulty_level"
    old_value: str   # e.g. "4"
    new_value: str   # e.g. "3"


@dataclass
class SlotDiff:
    """Detected changes for a single slot."""
    slot_id: str
    field_changes: list[FieldChange] = field(default_factory=list)
    annotation: str = ""              # Teacher annotation text (non-empty)
    has_changes: bool = False


@dataclass
class OutlineDiff:
    """Complete diff result between base and annotated outlines."""
    changed_slots: list[SlotDiff] = field(default_factory=list)
    unchanged_slots: list[str] = field(default_factory=list)

    @property
    def has_any_changes(self) -> bool:
        return any(s.has_changes for s in self.changed_slots)


# ── Slot splitting ───────────────────────────────────────────────

def _split_slots(outline_md: str) -> dict[str, str]:
    """Split outline into {slot_id: content} by ## Qxx headings."""
    parts = re.split(r"## (Q\d+)", outline_md)
    result = {}
    for i in range(1, len(parts), 2):
        slot_id = parts[i]
        content = parts[i + 1] if i + 1 < len(parts) else ""
        result[slot_id] = content
    return result


# ── YAML contract extraction (reuse logic from compose_runner) ──

def _extract_yaml_contract(content: str) -> dict:
    """Extract YAML contract from ```yaml block under ### 机器契约."""
    m = re.search(r"###\s*机器契约\s*\n```ya?m?l?\s*\n(.*?)```", content, re.DOTALL)
    if not m:
        return {}
    try:
        import yaml
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


def _extract_legacy_fields(content: str) -> dict:
    """Extract fields from legacy **field**: value format."""
    result = {}
    for m in re.finditer(r"\* \*(\w+)\*[*:\s]*(.+?)(?:\n|$)", content):
        result[m.group(1)] = m.group(2).strip()
    return result


def extract_slot_contract(content: str) -> dict:
    """Extract machine contract from a slot's content (YAML or legacy)."""
    yaml_data = _extract_yaml_contract(content)
    if yaml_data:
        return yaml_data
    return _extract_legacy_fields(content)


# ── Teacher annotation extraction ────────────────────────────────

def _extract_teacher_annotation(content: str) -> str:
    """Extract text after > [教师] in the annotation area.

    Returns empty string if no annotation or annotation is blank.
    """
    m = re.search(
        r"###\s*教师批注区\s*\n>\s*\[教师\]\s*(.*?)(?:\n###|\n## )",
        content,
        re.DOTALL,
    )
    if not m:
        return ""
    text = m.group(1).strip()
    return text if len(text) > 0 else ""


# ── Dual-channel diff ────────────────────────────────────────────

def compute_outline_diff(base_md: str, annotated_md: str) -> OutlineDiff:
    """Detect changes between base and annotated outlines.

    Channel 1 (diff): Compare YAML contract fields.
    Channel 2 (annotation): Extract non-empty teacher annotations.

    Returns OutlineDiff with changed_slots and unchanged_slots.
    """
    base_slots = _split_slots(base_md)
    annotated_slots = _split_slots(annotated_md)

    all_slot_ids = list(dict.fromkeys(list(base_slots.keys()) + list(annotated_slots.keys())))

    changed: list[SlotDiff] = []
    unchanged: list[str] = []

    for slot_id in all_slot_ids:
        base_content = base_slots.get(slot_id, "")
        annotated_content = annotated_slots.get(slot_id, "")

        # Channel 1: diff machine contracts
        base_contract = extract_slot_contract(base_content)
        annotated_contract = extract_slot_contract(annotated_content)

        field_changes: list[FieldChange] = []
        all_fields = set(list(base_contract.keys()) + list(annotated_contract.keys()))
        for f in all_fields:
            old_val = str(base_contract.get(f, ""))
            new_val = str(annotated_contract.get(f, ""))
            if old_val != new_val and new_val:
                field_changes.append(FieldChange(field=f, old_value=old_val, new_value=new_val))

        # Channel 2: extract annotation
        annotation = _extract_teacher_annotation(annotated_content)

        has_changes = bool(field_changes) or bool(annotation)
        if has_changes:
            changed.append(SlotDiff(
                slot_id=slot_id,
                field_changes=field_changes,
                annotation=annotation,
                has_changes=True,
            ))
        else:
            unchanged.append(slot_id)

    return OutlineDiff(changed_slots=changed, unchanged_slots=unchanged)


# ── Validation ───────────────────────────────────────────────────

def validate_changes(
    slot_diffs: list[SlotDiff],
    templates: dict,
) -> list[str]:
    """Validate detected changes against slot templates.

    Checks:
    - difficulty_level is 1-5 integer
    - examination_mode is in the slot's available modes (if templates provide them)
    - primary_target_name is non-empty

    Returns list of validation warning strings (empty = all valid).
    """
    warnings: list[str] = []

    for sd in slot_diffs:
        slot_id = sd.slot_id
        tpl = templates.get(slot_id, {})

        for fc in sd.field_changes:
            # difficulty_level range check
            if fc.field == "difficulty_level":
                try:
                    val = int(fc.new_value)
                    if not (1 <= val <= 5):
                        warnings.append(
                            f"[{slot_id}] difficulty_level={val} 超出范围(1-5)"
                        )
                except ValueError:
                    warnings.append(
                        f"[{slot_id}] difficulty_level={fc.new_value!r} 不是有效整数"
                    )

            # examination_mode validity (if template has available modes)
            if fc.field == "examination_mode" and tpl:
                available_modes = _get_available_modes(tpl)
                if available_modes and fc.new_value not in available_modes:
                    warnings.append(
                        f"[{slot_id}] examination_mode={fc.new_value!r} "
                        f"不在可选列表中 (可用: {', '.join(available_modes[:3])}...)"
                    )

            # primary_target_name non-empty
            if fc.field == "primary_target_name" and not fc.new_value.strip():
                warnings.append(f"[{slot_id}] primary_target_name 不能为空")

    return warnings


def _get_available_modes(template: dict) -> list[str]:
    """Extract available examination mode names from a slot template."""
    # Templates may store modes under various keys
    modes = template.get("examination_modes", [])
    if not modes and "modes" in template:
        modes = template["modes"]
    if isinstance(modes, list):
        return [m if isinstance(m, str) else m.get("name", "") for m in modes]
    return []


# ── Revision report formatting ──────────────────────────────────

def format_diff_summary(outline_diff: OutlineDiff, warnings: list[str] | None = None) -> str:
    """Format detected changes into a human-readable summary for the revision prompt."""
    lines: list[str] = []

    for sd in outline_diff.changed_slots:
        lines.append(f"### {sd.slot_id}")

        if sd.field_changes:
            lines.append("字段变更:")
            for fc in sd.field_changes:
                lines.append(f"  - {fc.field}: {fc.old_value!r} → {fc.new_value!r}")

        if sd.annotation:
            lines.append(f"教师批注: {sd.annotation}")

        lines.append("")

    if warnings:
        lines.append("### 验证警告")
        for w in warnings:
            lines.append(f"  - {w}")

    return "\n".join(lines)
