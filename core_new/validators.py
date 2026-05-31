"""Structural validators for question output — no LLM calls needed.

Catches format errors before expensive LLM verification.
"""

from __future__ import annotations

from typing import Any, Dict, List


def structural_validate(question: Dict[str, Any], question_type: str) -> List[str]:
    """Validate question structure with pure Python checks.

    Returns list of error strings. Empty list = valid.
    """
    errors: List[str] = []

    # Common checks for all question types
    stem = question.get("stem", "")
    if not stem or not str(stem).strip():
        errors.append("Missing or empty stem")

    if question_type == "single_choice":
        _validate_single_choice(question, errors)
    elif question_type == "comprehensive":
        _validate_comprehensive(question, errors)

    return errors


def _validate_single_choice(question: Dict[str, Any], errors: List[str]) -> None:
    options = question.get("options", [])
    if isinstance(options, list):
        if len(options) != 4:
            errors.append(f"Expected 4 options, got {len(options)}")
    elif isinstance(options, dict):
        if len(options) != 4:
            errors.append(f"Expected 4 options, got {len(options)}")

    answer = question.get("correct_answer", "")
    if str(answer).upper() not in ("A", "B", "C", "D"):
        errors.append(f"Invalid correct_answer: {answer!r}, expected A/B/C/D")

    explanation = question.get("explanation", "")
    if not explanation or not str(explanation).strip():
        errors.append("Missing explanation")


def _validate_comprehensive(question: Dict[str, Any], errors: List[str]) -> None:
    # Comp questions should NOT have options field
    if question.get("options"):
        errors.append("Comprehensive question should not have options field")

    if question.get("correct_answer"):
        errors.append("Comprehensive question should not have correct_answer field (use sub_questions)")

    sub_questions = question.get("sub_questions", [])
    if isinstance(sub_questions, list):
        for i, sq in enumerate(sub_questions):
            if not isinstance(sq, dict):
                errors.append(f"sub_question[{i}] is not a dict")
                continue
            if not sq.get("answer") and not sq.get("standard_answer"):
                errors.append(f"sub_question[{i}] missing answer")
    elif not sub_questions:
        errors.append("Comprehensive question missing sub_questions")
