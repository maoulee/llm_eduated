"""Structural validators for question output — no LLM calls needed.

Two validation levels:
  - validate_design_draft: checks structural fields only (stem, sub_question count, conditions).
    Used after the Designer step. Does NOT require answers or explanations.
  - validate_final_question: full validation including answers, explanations, rubric.
    Used on the final assembled output.
"""

from __future__ import annotations

from typing import Any, Dict, List


# ── Design draft validation (lightweight, no answer checks) ─────────


def validate_design_draft(question: Dict[str, Any], question_type: str) -> List[str]:
    """Validate design draft structure — stem, fields, sub_question count.

    Does NOT require answers, explanations, or scoring rubrics.
    Used after Designer step to catch format errors early.
    Returns list of error strings. Empty list = valid.
    """
    errors: List[str] = []

    stem = question.get("stem", "")
    if not stem or not str(stem).strip():
        errors.append("Missing or empty stem")

    if question_type == "single_choice":
        _validate_sc_draft(question, errors)
    elif question_type == "comprehensive":
        _validate_comp_draft(question, errors)

    return errors


def _validate_sc_draft(question: Dict[str, Any], errors: List[str]) -> None:
    """Draft-level SC validation: just check that option-related structure exists."""
    # Check that options field is present (can be list or dict with A/B/C/D)
    options = question.get("options")
    if options is None:
        # Options may come later (OptionAndDistractorAgent step), so at draft
        # stage we only warn if they're present but wrong count.
        pass
    elif isinstance(options, (list, dict)):
        if len(options) != 4:
            errors.append(f"Expected 4 options, got {len(options)}")


def _validate_comp_draft(question: Dict[str, Any], errors: List[str]) -> None:
    """Draft-level comprehensive validation: sub_questions exist and are non-empty.

    Does NOT require sub_questions to have answers — those are filled by the
    Solver step.
    """
    if question.get("options"):
        errors.append("Comprehensive question should not have options field")

    sub_questions = question.get("sub_questions", [])
    if isinstance(sub_questions, list):
        if not sub_questions:
            errors.append("Comprehensive question has empty sub_questions")
        for i, sq in enumerate(sub_questions):
            if isinstance(sq, str):
                if not sq.strip():
                    errors.append(f"sub_question[{i}] is empty")
            elif isinstance(sq, dict):
                # At draft stage, sub-question dict only needs text/content
                text = sq.get("text") or sq.get("content") or sq.get("question")
                if not text and not sq.get("index"):
                    # Might be a minimal sub_question, don't fail hard
                    pass
            else:
                errors.append(f"sub_question[{i}] has unexpected type: {type(sq).__name__}")
    elif not sub_questions:
        errors.append("Comprehensive question missing sub_questions")


# ── Final question validation (full, includes answers) ──────────────


def validate_final_question(question: Dict[str, Any], question_type: str) -> List[str]:
    """Validate final question with full checks — answers, explanations, etc.

    Returns list of error strings. Empty list = valid.
    """
    errors: List[str] = []

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
    if question.get("options"):
        errors.append("Comprehensive question should not have options field")

    if question.get("correct_answer"):
        errors.append("Comprehensive question should not have correct_answer field (use sub_questions)")

    sub_questions = question.get("sub_questions", [])
    if isinstance(sub_questions, list):
        if not sub_questions:
            errors.append("Comprehensive question has empty sub_questions")
        for i, sq in enumerate(sub_questions):
            if isinstance(sq, str):
                if not sq.strip():
                    errors.append(f"sub_question[{i}] is empty")
            elif isinstance(sq, dict):
                if not sq.get("answer") and not sq.get("standard_answer"):
                    errors.append(f"sub_question[{i}] missing answer")
            else:
                errors.append(f"sub_question[{i}] has unexpected type: {type(sq).__name__}")
    elif not sub_questions:
        errors.append("Comprehensive question missing sub_questions")


# ── Backward-compatible alias ───────────────────────────────────────

def structural_validate(question: Dict[str, Any], question_type: str) -> List[str]:
    """Alias for validate_final_question — kept for backward compatibility."""
    return validate_final_question(question, question_type)
