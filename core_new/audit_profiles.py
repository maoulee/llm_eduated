"""Audit mode profiles: per-mode checklists for audit agents."""

from __future__ import annotations

from dataclasses import dataclass

from core_new.agent_roles import AuditMode, normalize_audit_mode


@dataclass(frozen=True)
class AuditCheckItem:
    """A single audit checklist item."""
    key: str
    description: str
    severity: str = "major"  # minor, major, blocker


@dataclass(frozen=True)
class AuditProfile:
    """Audit checklist profile for a specific audit mode."""
    mode: AuditMode
    description: str
    check_items: tuple[AuditCheckItem, ...]
    focus_areas: tuple[str, ...]


# ── Extraction Review ──
EXTRACTION_REVIEW_PROFILE = AuditProfile(
    mode=AuditMode.EXTRACTION_REVIEW,
    description="Validate knowledge extraction from source material",
    check_items=(
        AuditCheckItem("faithfulness", "Extraction is faithful to source material, no hallucination", "blocker"),
        AuditCheckItem("mechanism_accuracy", "Technical mechanisms are accurately captured", "major"),
        AuditCheckItem("difficulty_appropriate", "Difficulty labels match actual content complexity", "major"),
        AuditCheckItem("role_valid", "Functional roles (memory hierarchy, pipeline stage, etc.) are correctly assigned", "major"),
        AuditCheckItem("no_orphans", "No orphan references or broken type links", "minor"),
        AuditCheckItem("coverage", "All important knowledge points from source are captured", "minor"),
    ),
    focus_areas=("faithfulness", "mechanism_accuracy", "difficulty_appropriate"),
)


# ── Blueprint Review ──
BLUEPRINT_REVIEW_PROFILE = AuditProfile(
    mode=AuditMode.BLUEPRINT_REVIEW,
    description="Validate exam paper blueprint/planning quality",
    check_items=(
        AuditCheckItem("difficulty_distribution", "Difficulty distribution matches target profile", "major"),
        AuditCheckItem("calculation_load_balance", "Calculation load is balanced across questions", "major"),
        AuditCheckItem("reasoning_steps_distribution", "Reasoning complexity varies appropriately", "major"),
        AuditCheckItem("knowledge_coverage", "Knowledge point coverage is comprehensive, no gaps", "major"),
        AuditCheckItem("no_duplication", "No duplicated knowledge points across slots", "major"),
        AuditCheckItem("slot_structure", "Slot types and question types are correctly assigned", "minor"),
        AuditCheckItem("score_allocation", "Score allocation is reasonable", "minor"),
    ),
    focus_areas=("difficulty_distribution", "knowledge_coverage", "no_duplication"),
)


# ── Question Review ──
QUESTION_REVIEW_PROFILE = AuditProfile(
    mode=AuditMode.QUESTION_REVIEW,
    description="Validate individual question quality",
    check_items=(
        AuditCheckItem("question_structure", "Question structure is complete and well-formed (stem, options/sub-questions, answer)", "blocker"),
        AuditCheckItem("answer_unique", "Correct answer is unique and unambiguous", "blocker"),
        AuditCheckItem("computed_vs_intended", "Computed answer matches intended answer", "blocker"),
        AuditCheckItem("slot_match", "Question matches its slot blueprint (type, difficulty, knowledge point)", "major"),
        AuditCheckItem("difficulty_match", "Actual difficulty matches target difficulty", "major"),
        AuditCheckItem("no_ambiguity", "No ambiguous wording that could confuse examinees", "major"),
        AuditCheckItem("option_quality", "Distractors are plausible but clearly wrong (for SC)", "major"),
        AuditCheckItem("rubric_quality", "Rubric covers all scoring dimensions (for comprehensive)", "major"),
        AuditCheckItem("calculation_stability", "Calculation is numerically stable with no edge case failures", "minor"),
    ),
    focus_areas=("computed_vs_intended", "slot_match", "answer_unique"),
)


# ── Final Paper Review ──
FINAL_PAPER_REVIEW_PROFILE = AuditProfile(
    mode=AuditMode.FINAL_PAPER_REVIEW,
    description="Validate full exam paper coherence and quality",
    check_items=(
        AuditCheckItem("no_cross_duplication", "No duplicated content or knowledge points across questions", "blocker"),
        AuditCheckItem("difficulty_curve", "Overall difficulty curve is appropriate for the exam", "major"),
        AuditCheckItem("knowledge_balance", "Knowledge coverage is balanced across domains", "major"),
        AuditCheckItem("score_integrity", "Total score and per-question scores are correct", "blocker"),
        AuditCheckItem("style_consistency", "Writing style and formatting are consistent throughout", "minor"),
        AuditCheckItem("answer_question_consistency", "All answers match their respective questions", "blocker"),
        AuditCheckItem("time_feasibility", "Total exam can be reasonably completed within time limit", "minor"),
    ),
    focus_areas=("no_cross_duplication", "difficulty_curve", "answer_question_consistency"),
)


AUDIT_PROFILES: dict[AuditMode, AuditProfile] = {
    AuditMode.EXTRACTION_REVIEW: EXTRACTION_REVIEW_PROFILE,
    AuditMode.BLUEPRINT_REVIEW: BLUEPRINT_REVIEW_PROFILE,
    AuditMode.QUESTION_REVIEW: QUESTION_REVIEW_PROFILE,
    AuditMode.FINAL_PAPER_REVIEW: FINAL_PAPER_REVIEW_PROFILE,
}


def get_audit_profile(mode: AuditMode | str) -> AuditProfile:
    """Get the audit profile for a given mode."""
    mode_enum = normalize_audit_mode(mode)
    if mode_enum is None:
        return QUESTION_REVIEW_PROFILE
    return AUDIT_PROFILES.get(mode_enum, QUESTION_REVIEW_PROFILE)


def build_audit_checklist_prompt(mode: AuditMode | str) -> str:
    """Build a prompt section listing the checklist items for a given audit mode."""
    profile = get_audit_profile(mode)
    lines = [f"## 审核检查清单 ({profile.description})\n"]
    for i, item in enumerate(profile.check_items, 1):
        marker = "【关键】" if item.key in profile.focus_areas else ""
        lines.append(f"{i}. {marker}{item.description} [{item.severity}]")
    lines.append(f"\n请逐项检查，重点关注: {', '.join(profile.focus_areas)}")
    return "\n".join(lines)
