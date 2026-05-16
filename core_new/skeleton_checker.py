"""SlotSkeletonRuleChecker: code-level hard rule validation for blueprints.

Validates structural constraints that should not require LLM judgment:
- Question type field protocols (choice vs comprehensive)
- Budget consistency (distribution sums = total_questions)
- Required field presence
"""

from __future__ import annotations

from typing import Any, Dict, List


def check_blueprint_skeleton(blueprint: Dict[str, Any]) -> List[Dict[str, str]]:
    """Validate blueprint skeleton rules. Returns list of violations.

    Each violation: {"slot_id": ..., "rule": ..., "detail": ...}
    Empty list = all checks pass.
    """
    violations: List[Dict[str, str]] = []

    total = blueprint.get("total_questions", 0)
    if isinstance(total, str):
        try:
            total = int(total)
        except ValueError:
            total = 0

    # ── Budget consistency ──────────────────────────────────
    _check_budget_sum(violations, "primary_role_distribution", blueprint.get("primary_role_distribution"), total)
    _check_budget_sum(violations, "difficulty_distribution", blueprint.get("difficulty_distribution"), total)
    _check_budget_sum(violations, "calculation_load_distribution", blueprint.get("calculation_load_distribution"), total)

    # ── Per-slot field protocol ─────────────────────────────
    for slot in blueprint.get("slots", []):
        slot_id = slot.get("slot_id", "??")
        # Determine question type from contract or option_style hint
        qtype = _infer_question_type(slot)

        if qtype == "comprehensive":
            _check_comprehensive_slot(violations, slot_id, slot)
        else:
            _check_choice_slot(violations, slot_id, slot)

    return violations


def _infer_question_type(slot: Dict[str, Any]) -> str:
    """Infer question type from slot fields."""
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
    opt = slot.get("option_style", "MISSING")
    shape = slot.get("reasoning_shape", "MISSING")

    if opt != "none":
        violations.append({
            "slot_id": slot_id,
            "rule": "comprehensive_option_style",
            "detail": f"option_style must be 'none', got '{opt}'",
        })

    if shape != "none":
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
    """Choice questions must have required style fields."""
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
    """Check that a distribution dict sums to expected_total."""
    if not isinstance(distribution, dict):
        return
    try:
        actual = sum(int(v) for v in distribution.values())
    except (ValueError, TypeError):
        return
    if actual != expected_total:
        violations.append({
            "slot_id": "GLOBAL",
            "rule": "budget_sum_mismatch",
            "detail": f"{name} sums to {actual}, expected {expected_total}",
        })
