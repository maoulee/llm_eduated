"""Design card schema validator — Phase 0.

Validates that a design_card.md file conforms to the v1 schema:
- All 9 required sections present
- Key fields within each section are non-empty
- No forbidden values in constrained fields
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


REQUIRED_SECTIONS = [
    "status",
    "blueprint_contract",
    "route",
    "core_knowledge_intent",
    "expected_reasoning_actions",
    "question_structure_plan",
    "parameter_plan",
    "terminology_and_expression_constraints",
    "audit_focus",
]

# Fields that must appear as list items within their section
REQUIRED_FIELDS: dict[str, list[str]] = {
    "blueprint_contract": [
        "slot_id",
        "question_type",
        "primary_target_name",
        "examination_mode",
        "k_target",
        "difficulty_level",
    ],
    "route": [
        "question_form",
        "question_type",
        "requires_parameter_verification",
        "requires_solver",
        "requires_code",
    ],
    "core_knowledge_intent": [
        "must_test",
        "must_not_shift_to",
        "coverage_success_criteria",
    ],
    "expected_reasoning_actions": [],  # at least 1 action_X
    "audit_focus": [
        "final_review_must_check",
        "solve_output_should_contain",
        "fail_if_missing",
    ],
}

FORBIDDEN_STATUS_VALUES = {"pass", "needs_fix", "final", "solved"}
VALID_QUESTION_FORMS = {"single_choice", "comprehensive"}
VALID_QUESTION_TYPES = {"conceptual", "computational", "mixed"}


@dataclass
class ValidationResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.ok = False
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_design_card(content: str) -> ValidationResult:
    """Validate a design_card.md against the v1 schema."""
    result = ValidationResult()

    # 1. Check all required sections exist
    sections: dict[str, str] = {}
    for section_name in REQUIRED_SECTIONS:
        pattern = rf"^## {re.escape(section_name)}\n(.*?)(?=^## |\Z)"
        m = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if not m:
            result.error(f"Missing required section: ## {section_name}")
        else:
            sections[section_name] = m.group(1).strip()

    if not result.ok:
        return result

    # 2. Validate status
    status_text = sections["status"].strip().lower()
    if status_text in FORBIDDEN_STATUS_VALUES:
        result.error(f"status must be 'draft', got '{status_text}'")
    elif status_text != "draft":
        result.warn(f"status is '{status_text}', expected 'draft'")

    # 3. Validate required fields within sections
    for section_name, required_fields in REQUIRED_FIELDS.items():
        section_text = sections.get(section_name, "")
        for field_name in required_fields:
            # Look for "- field_name:" or "- **field_name**:" pattern
            pattern = rf"[-*]\s+\*?\*?{re.escape(field_name)}\*?\*?\s*[:：]"
            if not re.search(pattern, section_text):
                result.error(
                    f"Section '{section_name}' missing required field: {field_name}"
                )

    # 4. Validate expected_reasoning_actions has at least 1 action
    era_text = sections.get("expected_reasoning_actions", "")
    actions = re.findall(r"-\s+action_\d+\s*[:：]", era_text)
    if not actions:
        # Also check for "- action_1:" without colon
        actions = re.findall(r"-\s+action_\d+", era_text)
    if not actions:
        result.error("expected_reasoning_actions must have at least 1 action")

    # 5. Validate route fields
    route_text = sections.get("route", "")

    q_form_match = re.search(
        r"question_form\s*[:：]\s*(.+)", route_text
    )
    if q_form_match:
        q_form = q_form_match.group(1).strip().lower()
        if q_form not in VALID_QUESTION_FORMS:
            result.error(
                f"route.question_form must be one of {VALID_QUESTION_FORMS}, got '{q_form}'"
            )

    q_type_match = re.search(
        r"question_type\s*[:：]\s*(.+)", route_text
    )
    if q_type_match:
        q_type = q_type_match.group(1).strip().lower()
        if q_type not in VALID_QUESTION_TYPES:
            result.error(
                f"route.question_type must be one of {VALID_QUESTION_TYPES}, got '{q_type}'"
            )

    # 6. Warnings for common issues
    bp_text = sections.get("blueprint_contract", "")
    if "should_be" not in bp_text:
        result.warn("blueprint_contract missing should_be (recommended)")
    if "should_not_be" not in bp_text:
        result.warn("blueprint_contract missing should_not_be (recommended)")

    # Check for numeric answers in expected_reasoning_actions (leakage risk)
    if re.search(r"=\s*\d+", era_text):
        result.warn(
            "expected_reasoning_actions contains numeric assignments — "
            "this may leak answers to solver"
        )

    return result


def validate_design_card_file(path: str) -> ValidationResult:
    """Validate a design_card.md file by path."""
    with open(path, encoding="utf-8") as f:
        return validate_design_card(f.read())
