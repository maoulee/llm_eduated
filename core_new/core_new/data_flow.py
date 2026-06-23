"""Data-flow contracts: what each pipeline step MUST receive,
MAY optionally pull, and MUST NOT see.

Design principles:
  * mandatory  — pipeline injects directly into build_input()
  * optional   — registered in context_store; agent decides whether to pull
  * forbidden  — never registered; read_context() returns error
  * revision upgrades — optional → mandatory during revision rounds
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .data_keys import (
    BLUEPRINT, DESIGN, OPTIONS, SOLVER_RESULT, SOLUTION, REVIEW,
    EXPERIENCE, FIX_INSTRUCTION, QUESTION_TYPE, RUBRIC, SUMMARY,
    canonical,
)

# ── Per-step input declarations ─────────────────────────────────

@dataclass(frozen=True)
class StepInputs:
    """Declare what a pipeline step needs."""
    mandatory: frozenset[str] = frozenset()
    optional: frozenset[str] = frozenset()
    forbidden: frozenset[str] = frozenset()


# fmt: off
STEP_INPUTS: dict[str, StepInputs] = {
    # ── Generation ──────────────────────────────────────────────
    "design_sc": StepInputs(
        mandatory={BLUEPRINT, EXPERIENCE},
        optional={FIX_INSTRUCTION},
        forbidden={SOLVER_RESULT, REVIEW, OPTIONS},
    ),
    "design_comp": StepInputs(
        mandatory={BLUEPRINT, EXPERIENCE},
        optional={FIX_INSTRUCTION},
        forbidden={SOLVER_RESULT, REVIEW, OPTIONS},
    ),
    "options": StepInputs(
        mandatory={DESIGN},
        optional={BLUEPRINT},
        forbidden={SOLVER_RESULT, REVIEW},
    ),
    "solve": StepInputs(
        mandatory={DESIGN},
        optional=set(),
        forbidden={BLUEPRINT, REVIEW, EXPERIENCE},
    ),

    # ── Formatting ──────────────────────────────────────────────
    "format_sc": StepInputs(
        mandatory={DESIGN, OPTIONS, SOLVER_RESULT},
        optional=set(),
        forbidden={BLUEPRINT, REVIEW, EXPERIENCE},
    ),
    "format_comp": StepInputs(
        mandatory={DESIGN, SOLVER_RESULT},
        optional=set(),
        forbidden={BLUEPRINT, REVIEW, EXPERIENCE},
    ),

    # ── Review / audit ──────────────────────────────────────────
    "gate": StepInputs(
        mandatory={DESIGN, BLUEPRINT},
        optional={OPTIONS, EXPERIENCE},
        forbidden={SOLVER_RESULT, SOLUTION},
    ),
    "verify": StepInputs(
        mandatory={DESIGN, SOLVER_RESULT},
        optional={BLUEPRINT, OPTIONS, QUESTION_TYPE},
        forbidden={EXPERIENCE, FIX_INSTRUCTION},
    ),
    "review": StepInputs(
        mandatory={DESIGN, OPTIONS, SOLUTION},
        optional={SOLVER_RESULT},
        forbidden={EXPERIENCE, FIX_INSTRUCTION},
    ),
    "fixer": StepInputs(
        mandatory={REVIEW},
        optional={DESIGN, OPTIONS, SOLUTION, SOLVER_RESULT},
        forbidden={EXPERIENCE, BLUEPRINT},
    ),

    # ── Post-processing ─────────────────────────────────────────
    "summary": StepInputs(
        mandatory={DESIGN, SOLUTION},
        optional={OPTIONS, SOLVER_RESULT, REVIEW},
        forbidden={EXPERIENCE, FIX_INSTRUCTION},
    ),
    "rubric": StepInputs(
        mandatory={DESIGN, SOLUTION, BLUEPRINT},
        optional=set(),
        forbidden={EXPERIENCE, REVIEW},
    ),

    # ── Paper-level ─────────────────────────────────────────────
    "paper_compose": StepInputs(
        mandatory=set(),
        optional=set(),
        forbidden=set(),
    ),
    "paper_review": StepInputs(
        mandatory=set(),
        optional=set(),
        forbidden=set(),
    ),
}
# fmt: on

# ── Revision upgrades (optional → mandatory in revision rounds) ─

REVISION_UPGRADES: dict[str, dict[str, str]] = {
    "design_sc":   {FIX_INSTRUCTION: "mandatory"},
    "design_comp": {FIX_INSTRUCTION: "mandatory"},
}

# ── Validation ──────────────────────────────────────────────────


def get_step_inputs(step: str, *, is_revision: bool = False) -> StepInputs:
    """Return effective StepInputs for a step, applying revision upgrades."""
    base = STEP_INPUTS.get(step)
    if base is None:
        return StepInputs()  # unknown step — no restrictions

    if not is_revision:
        return base

    upgrades = REVISION_UPGRADES.get(step, {})
    new_mandatory = set(base.mandatory)
    new_optional = set(base.optional)
    for key, target in upgrades.items():
        if target == "mandatory" and key in new_optional:
            new_optional.discard(key)
            new_mandatory.add(key)

    return StepInputs(
        mandatory=frozenset(new_mandatory),
        optional=frozenset(new_optional),
        forbidden=base.forbidden,
    )


def validate_initial_state(
    step: str,
    initial_state: dict[str, Any],
    *,
    is_revision: bool = False,
) -> list[str]:
    """Validate initial_state keys against the step's data-flow contract.

    Returns a list of violation descriptions (empty = valid).
    """
    inputs = get_step_inputs(step, is_revision=is_revision)
    violations: list[str] = []

    for raw_key in initial_state:
        key = canonical(raw_key)
        if key in inputs.forbidden:
            violations.append(
                f"FORBIDDEN: step '{step}' must not receive '{key}' "
                f"(key '{raw_key}')"
            )

    return violations


def classify_keys(
    step: str,
    keys: list[str],
    *,
    is_revision: bool = False,
) -> dict[str, list[str]]:
    """Classify a list of keys into mandatory / optional / forbidden / unknown.

    Returns {"mandatory": [...], "optional": [...], "forbidden": [...], "unknown": [...]}.
    """
    inputs = get_step_inputs(step, is_revision=is_revision)
    result: dict[str, list[str]] = {
        "mandatory": [],
        "optional": [],
        "forbidden": [],
        "unknown": [],
    }
    for raw_key in keys:
        key = canonical(raw_key)
        if key in inputs.mandatory:
            result["mandatory"].append(raw_key)
        elif key in inputs.optional:
            result["optional"].append(raw_key)
        elif key in inputs.forbidden:
            result["forbidden"].append(raw_key)
        else:
            result["unknown"].append(raw_key)
    return result


def build_context_catalog(
    step: str,
    available_data: dict[str, Any],
    *,
    is_revision: bool = False,
) -> dict[str, str]:
    """Build the catalog for read_context tools — only optional + allowed data.

    Returns {canonical_key: description} for data the agent may pull.
    Mandatory data is already in the prompt; forbidden data is excluded.
    """
    inputs = get_step_inputs(step, is_revision=is_revision)
    catalog: dict[str, str] = {}

    _DESCRIPTIONS: dict[str, str] = {
        BLUEPRINT: "题位蓝图（出题要求、知识点、难度）",
        DESIGN: "题目设计（题干、子问题、给定条件）",
        OPTIONS: "选项内容（option_A~D，仅选择题）",
        SOLVER_RESULT: "求解器输出（computed_results, code）",
        SOLUTION: "格式化答案（explanation, answer）",
        REVIEW: "审核结果（status, quality, issues, fix_instruction）",
        EXPERIENCE: "经验卡（参考真题、知识点雷达）",
        FIX_INSTRUCTION: "修复指令（需要修改什么）",
        QUESTION_TYPE: "题目类型（single_choice / comprehensive）",
        RUBRIC: "评分标准",
        SUMMARY: "题目摘要",
    }

    for raw_key, value in available_data.items():
        key = canonical(raw_key)
        # Only include optional data that exists and is not None
        if key in inputs.optional and value is not None:
            desc = _DESCRIPTIONS.get(key, key)
            catalog[key] = desc

    return catalog
