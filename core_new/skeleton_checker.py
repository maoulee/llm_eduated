"""SlotSkeletonRuleChecker: code-level hard rule validation for blueprints.

Validates structural constraints that should not require LLM judgment:
- Question type field protocols (choice vs comprehensive)
- Budget consistency (distribution sums = total_questions) — only for V1 blueprints
- Required field presence

V1 blueprints (PAPER_COMPOSER_PROMPT) include design-level fields (option_style,
reasoning_shape, budget distributions). V2 outlines (PAPER_OUTLINE_PROMPT) do not —
the checker skips those checks when the fields are absent.
"""

from __future__ import annotations

from typing import Any, Dict, List


def check_blueprint_skeleton(blueprint: Dict[str, Any]) -> List[Dict[str, str]]:
    """Validate blueprint skeleton rules. Returns list of violations.

    Each violation: {"slot_id": ..., "rule": ..., "detail": ...}
    Empty list = all checks pass.

    Silently skips checks for fields that don't exist in V2 outline format.
    """
    violations: List[Dict[str, str]] = []

    total = blueprint.get("total_questions", 0)
    if isinstance(total, str):
        try:
            total = int(total)
        except ValueError:
            total = 0

    # ── Budget consistency (V1 only — skip if not present) ──────
    _check_budget_sum(violations, "primary_role_distribution", blueprint.get("primary_role_distribution"), total)
    _check_budget_sum(violations, "difficulty_distribution", blueprint.get("difficulty_distribution"), total)
    _check_budget_sum(violations, "calculation_load_distribution", blueprint.get("calculation_load_distribution"), total)
    _check_budget_sum(violations, "reasoning_steps_distribution", blueprint.get("reasoning_steps_distribution"), total)

    # ── Per-slot field protocol ─────────────────────────────────
    for slot in blueprint.get("slots", []):
        slot_id = slot.get("slot_id", "??")
        qtype = _infer_question_type(slot)

        if qtype == "comprehensive":
            _check_comprehensive_slot(violations, slot_id, slot)
        else:
            _check_choice_slot(violations, slot_id, slot)

    return violations


def _infer_question_type(slot: Dict[str, Any]) -> str:
    """Infer question type from slot fields."""
    # V2 outline format: use question_type field directly
    qt = slot.get("question_type", "")
    if qt == "comprehensive":
        return "comprehensive"
    if qt == "single_choice":
        return "single_choice"

    # V1 blueprint format: infer from option_style
    opt = slot.get("option_style", "")
    if opt == "none":
        return "comprehensive"
    if slot.get("sub_questions") is not None and slot.get("answer_format"):
        return "comprehensive"
    return "single_choice"


def _check_comprehensive_slot(
    violations: List[Dict[str, str]], slot_id: str, slot: Dict[str, Any]
) -> None:
    """Comprehensive questions must not have choice-only fields."""
    opt = slot.get("option_style")
    shape = slot.get("reasoning_shape")

    # Only check if fields are present (V1 format)
    if opt is not None and opt != "none":
        violations.append({
            "slot_id": slot_id,
            "rule": "comprehensive_option_style",
            "detail": f"option_style must be 'none', got '{opt}'",
        })

    if shape is not None and shape != "none":
        violations.append({
            "slot_id": slot_id,
            "rule": "comprehensive_reasoning_shape",
            "detail": f"reasoning_shape must be 'none', got '{shape}'",
        })

    if "option_A" in slot or "option_B" in slot:
        violations.append({
            "slot_id": slot_id,
            "rule": "comprehensive_has_options",
            "detail": "comprehensive question must not have option_A/B/C/D",
        })

    if not slot.get("sub_questions"):
        violations.append({
            "slot_id": slot_id,
            "rule": "comprehensive_missing_sub_questions",
            "detail": "comprehensive question must have sub_questions",
        })

    if not slot.get("answer_format"):
        violations.append({
            "slot_id": slot_id,
            "rule": "comprehensive_missing_answer_format",
            "detail": "comprehensive question must have answer_format",
        })


def _check_choice_slot(
    violations: List[Dict[str, str]], slot_id: str, slot: Dict[str, Any]
) -> None:
    """Choice questions: check required style fields (V1 only — skip if absent)."""
    # V2 outline format doesn't have option_style/reasoning_shape — skip silently
    if "option_style" not in slot and "reasoning_shape" not in slot:
        return

    if not slot.get("option_style") or slot.get("option_style") == "none":
        violations.append({
            "slot_id": slot_id,
            "rule": "choice_missing_option_style",
            "detail": "choice question must have option_style (not none)",
        })

    if not slot.get("reasoning_shape") or slot.get("reasoning_shape") == "none":
        violations.append({
            "slot_id": slot_id,
            "rule": "choice_missing_reasoning_shape",
            "detail": "choice question must have reasoning_shape (not none)",
        })


def _check_budget_sum(
    violations: List[Dict[str, str]],
    name: str,
    distribution: Any,
    expected_total: int,
) -> None:
    """Check that a distribution dict sums to expected_total.

    Silently skips if distribution is None (V2 outline format doesn't have budgets).
    """
    if distribution is None:
        return

    if not isinstance(distribution, dict):
        violations.append({
            "slot_id": "GLOBAL",
            "rule": "budget_missing",
            "detail": f"{name} is missing or not a dict",
        })
        return
    try:
        actual = sum(int(v) for v in distribution.values())
    except (ValueError, TypeError):
        violations.append({
            "slot_id": "GLOBAL",
            "rule": "budget_parse_error",
            "detail": f"{name} has non-integer values",
        })
        return
    if actual != expected_total:
        violations.append({
            "slot_id": "GLOBAL",
            "rule": "budget_sum_mismatch",
            "detail": f"{name} sums to {actual}, expected {expected_total}",
        })
