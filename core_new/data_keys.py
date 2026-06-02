"""Canonical key-name registry for pipeline data.

Eliminates key-name aliasing: sc_draft_result / question_design / sc_design
all map to the canonical "design".  Every pipeline step and agent should
use canonical names; the normalisation helper accepts legacy aliases.
"""

from __future__ import annotations

# ── Canonical names ─────────────────────────────────────────────

BLUEPRINT = "blueprint"
DESIGN = "design"
OPTIONS = "options"
SOLVER_RESULT = "solver_result"
SOLUTION = "solution"
REVIEW = "review"
RUBRIC = "rubric"
SUMMARY = "summary"
EXPERIENCE = "experience"
FIX_INSTRUCTION = "fix_instruction"
QUESTION_TYPE = "question_type"

# ── Alias → canonical mapping ───────────────────────────────────

_ALIAS_MAP: dict[str, str] = {
    # blueprint aliases
    "current_blueprint": BLUEPRINT,
    "slot_blueprint": BLUEPRINT,
    "paper_blueprint": BLUEPRINT,
    # design aliases
    "sc_draft_result": DESIGN,
    "question_design": DESIGN,
    "sc_design": DESIGN,
    # options aliases
    "sc_options_result": OPTIONS,
    "sc_options": OPTIONS,
    # solver aliases
    "sc_solver_result": SOLVER_RESULT,
    "solver_result": SOLVER_RESULT,
    # solution aliases
    "sc_solution_result": SOLUTION,
    "formatted_solution": SOLUTION,
    # review aliases
    "sc_review_result": REVIEW,
    "review": REVIEW,
    "final_review_result": REVIEW,
    "post_review_result": REVIEW,
    "solver_verify_result": REVIEW,
    "stem_blueprint_gate_result": REVIEW,
    # experience aliases
    "experience_card": EXPERIENCE,
    "experience_radar": EXPERIENCE,
    "reference_questions": EXPERIENCE,
    # fix instruction aliases
    "stem_fix_instruction": FIX_INSTRUCTION,
    # rubric
    "rubric": RUBRIC,
    # summary
    "question_summary": SUMMARY,
    # question type
    "question_type": QUESTION_TYPE,
    "is_sc": QUESTION_TYPE,
}

# Keys that are already canonical (self-mapping)
_CANONICAL_SET: frozenset[str] = frozenset({
    BLUEPRINT, DESIGN, OPTIONS, SOLVER_RESULT, SOLUTION,
    REVIEW, RUBRIC, SUMMARY, EXPERIENCE, FIX_INSTRUCTION, QUESTION_TYPE,
})

# Pipeline control keys that are NOT agent outputs — excluded from data flow
PIPELINE_CONTROL_KEYS: frozenset[str] = frozenset({
    "content_to_review",
    "slot_id",
    "is_sc",
})


def canonical(key: str) -> str:
    """Normalise a key name to its canonical form.

    Returns the key unchanged if it is already canonical or unknown.
    """
    if key in _CANONICAL_SET:
        return key
    return _ALIAS_MAP.get(key, key)


def is_canonical(key: str) -> bool:
    """Check whether a key is a canonical name."""
    return key in _CANONICAL_SET
