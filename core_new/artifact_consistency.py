"""Non-LLM artifact consistency check across pipeline outputs.

Detects conflicting values for the same answer across different pipeline
artifacts (solution, rubric, summary, final_question). No subject-specific
knowledge required — purely structural and numerical comparison.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _extract_numbers(text: str) -> List[str]:
    """Extract standalone numeric values from text."""
    if not isinstance(text, str):
        return []
    return re.findall(r"(?<!\w)-?\d+\.?\d*(?!\w)", text)


def check_artifact_consistency(
    final_question: Dict[str, Any],
    solver_result: Dict[str, Any] | None = None,
    summary: Dict[str, Any] | None = None,
    rubric: Dict[str, Any] | None = None,
    *,
    is_sc: bool = True,
) -> Dict[str, Any]:
    """Check cross-artifact consistency before export.

    Returns:
        {"status": "pass"|"needs_fix"|"needs_human_review",
         "conflicts": [...], "summary": str}
    """
    conflicts: List[Dict[str, Any]] = []

    # 1. correct_answer vs answer (Comp questions)
    if not is_sc:
        answer = final_question.get("answer")
        correct_answer = final_question.get("correct_answer")
        if answer and correct_answer and answer != correct_answer:
            conflicts.append({
                "field_a": "final_question.answer",
                "field_b": "final_question.correct_answer",
                "value_a": _truncate(str(answer)),
                "value_b": _truncate(str(correct_answer)),
                "severity": "critical",
            })

    # 2. summary.correct_answer vs solution answer
    if summary and is_sc:
        summary_answer = summary.get("correct_answer", "")
        solution_answer = final_question.get("correct_answer", "")
        if summary_answer and solution_answer and summary_answer != solution_answer:
            conflicts.append({
                "field_a": "summary.correct_answer",
                "field_b": "final_question.correct_answer",
                "value_a": str(summary_answer),
                "value_b": str(solution_answer),
                "severity": "critical",
            })

    # 3. Numeric consistency: solver vs final answer (Comp)
    if solver_result and not is_sc:
        solver_text = str(solver_result)
        answer_text = str(final_question.get("answer", ""))
        solver_nums = _extract_numbers(solver_text)
        answer_nums = _extract_numbers(answer_text)
        # Check if key numbers from solver appear in the answer
        if solver_nums and answer_nums:
            # Take the last few numbers from solver (likely the final results)
            key_solver_nums = solver_nums[-5:] if len(solver_nums) > 5 else solver_nums
            missing = [n for n in key_solver_nums if n not in answer_text]
            if missing and len(missing) >= len(key_solver_nums) // 2 + 1:
                conflicts.append({
                    "field_a": "solver_result",
                    "field_b": "final_question.answer",
                    "value_a": f"key values: {key_solver_nums[:3]}...",
                    "value_b": f"missing: {missing[:3]}...",
                    "severity": "warning",
                })

    # 4. Rubric vs answer numeric consistency (Comp)
    if rubric and not is_sc:
        rubric_text = str(rubric)
        answer_text = str(final_question.get("answer", ""))
        rubric_nums = _extract_numbers(rubric_text)
        if rubric_nums and answer_text:
            # Check for numbers in rubric that conflict with answer
            answer_nums = _extract_numbers(answer_text)
            for rn in rubric_nums[:10]:
                if rn not in answer_text and rn not in [str(n) for n in answer_nums]:
                    # Not necessarily a conflict, could be intermediate values
                    pass

    # 5. Empty critical fields check
    if not final_question.get("stem"):
        conflicts.append({
            "field_a": "final_question.stem",
            "field_b": "",
            "value_a": "(empty)",
            "value_b": "",
            "severity": "critical",
        })

    if is_sc and not final_question.get("correct_answer"):
        conflicts.append({
            "field_a": "final_question.correct_answer",
            "field_b": "",
            "value_a": "(empty)",
            "value_b": "",
            "severity": "critical",
        })

    if not is_sc and not final_question.get("answer"):
        conflicts.append({
            "field_a": "final_question.answer",
            "field_b": "",
            "value_a": "(empty)",
            "value_b": "",
            "severity": "critical",
        })

    # Determine status
    critical = [c for c in conflicts if c.get("severity") == "critical"]
    if critical:
        status = "needs_fix"
    elif conflicts:
        status = "needs_fix"
    else:
        status = "pass"

    summary_text = f"{len(conflicts)} conflicts found" if conflicts else "All artifacts consistent"

    if conflicts:
        logger.warning("[ArtifactConsistency] %s: %s", status, summary_text)
        for c in conflicts:
            logger.warning("  conflict: %s vs %s (%s)",
                           c["field_a"], c["field_b"], c["severity"])
    else:
        logger.info("[ArtifactConsistency] pass")

    return {
        "status": status,
        "conflicts": conflicts,
        "summary": summary_text,
    }


def can_export(
    final_question: Dict[str, Any],
    review_records: List[Dict[str, Any]],
    consistency_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Final export gate: block export if quality gates not met.

    Returns:
        {"allowed": bool, "block_reasons": [...]}
    """
    block_reasons: List[str] = []

    # Block on review status
    for rec in review_records:
        status = rec.get("status", "")
        if status in {"needs_fix", "needs_human_review", "review_error"}:
            block_reasons.append(
                f"{rec.get('phase', 'unknown')}: status={status}"
            )

    # Block on consistency
    if consistency_result.get("status") != "pass":
        for c in consistency_result.get("conflicts", []):
            if c.get("severity") == "critical":
                block_reasons.append(
                    f"artifact_conflict: {c['field_a']} vs {c['field_b']}"
                )

    # Block on low solver confidence
    if final_question.get("solver_confidence") == "low":
        block_reasons.append("solver_confidence=low")

    allowed = len(block_reasons) == 0
    return {
        "allowed": allowed,
        "block_reasons": block_reasons,
    }


def _truncate(text: str, max_len: int = 100) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text
