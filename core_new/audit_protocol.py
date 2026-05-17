"""Shared audit result protocol and fix routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core_new.agent_roles import AuditMode, ExecutionPolicy, PipelineFixTarget, RoleType


AUDIT_STATUS_PASS = "pass"
AUDIT_STATUS_NEEDS_FIX = "needs_fix"
AUDIT_STATUS_REJECT = "reject"
AUDIT_STATUS_HUMAN = "needs_human_review"


@dataclass
class AuditResult:
    status: str
    severity: str = "none"
    issue_type: str = "none"
    fix_target: str = "none"
    fix_instruction: str = ""
    confidence: str = "medium"
    mode: str = AuditMode.QUESTION_REVIEW.value
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "severity": self.severity,
            "issue_type": self.issue_type,
            "fix_target": self.fix_target,
            "fix_instruction": self.fix_instruction,
            "confidence": self.confidence,
            "mode": self.mode,
            "raw": self.raw,
        }


@dataclass
class FixRoute:
    next_action: str
    target_role: str = "none"
    pipeline_fix_target: str = PipelineFixTarget.NONE.value
    instruction: str = ""
    reuse_previous_outputs: bool = True
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "next_action": self.next_action,
            "target_role": self.target_role,
            "pipeline_fix_target": self.pipeline_fix_target,
            "instruction": self.instruction,
            "reuse_previous_outputs": self.reuse_previous_outputs,
            "reason": self.reason,
        }


class AuditResultNormalizer:
    """Normalize legacy reviewer outputs into the shared audit protocol."""

    @classmethod
    def normalize(
        cls,
        data: dict[str, Any] | None,
        *,
        mode: AuditMode | str = AuditMode.QUESTION_REVIEW,
    ) -> AuditResult:
        raw = dict(data or {})
        mode_value = mode.value if isinstance(mode, AuditMode) else str(mode)

        status = cls._normalize_status(raw)
        issue_type = cls._infer_issue_type(raw, status)
        fix_target = cls._normalize_fix_target(raw, issue_type, status)
        severity = cls._normalize_severity(raw, status, issue_type)
        instruction = cls._extract_fix_instruction(raw)
        confidence = cls._normalize_confidence(raw)

        return AuditResult(
            status=status,
            severity=severity,
            issue_type=issue_type,
            fix_target=fix_target,
            fix_instruction=instruction,
            confidence=confidence,
            mode=mode_value,
            raw=raw,
        )

    @staticmethod
    def _normalize_status(raw: dict[str, Any]) -> str:
        status = str(raw.get("status") or raw.get("decision") or "").strip().lower()
        needs_fix = str(raw.get("needs_fix") or "").strip().lower()
        if needs_fix in {"yes", "true", "1"}:
            return AUDIT_STATUS_NEEDS_FIX
        if status in {"pass", "ok", "accept", "accepted", "verified", "auto_pass", "auto_fixed_recheck_passed"}:
            return AUDIT_STATUS_PASS
        if status in {
            "needs_fix",
            "revise",
            "revision",
            "fail",
            "failed",
            "has_issues",
            "needs_content_fix",
            "needs_link_fix",
            "auto_fix_partial",
        }:
            return AUDIT_STATUS_NEEDS_FIX
        if status in {"reject", "rejected"}:
            return AUDIT_STATUS_REJECT
        if status in {"needs_human_review", "needs_human_check", "needs_human_judgment"}:
            return AUDIT_STATUS_HUMAN
        return AUDIT_STATUS_PASS if not raw else AUDIT_STATUS_HUMAN

    @staticmethod
    def _infer_issue_type(raw: dict[str, Any], status: str) -> str:
        explicit = str(raw.get("issue_type") or raw.get("issue") or "").strip().lower()
        if explicit:
            if "answer" in explicit or "computed" in explicit:
                return "answer_error"
            if "ambig" in explicit:
                return "ambiguity"
            if "slot" in explicit or "blueprint" in explicit:
                return "slot_mismatch"
            if "difficulty" in explicit:
                return "difficulty"
            if "coverage" in explicit:
                return "coverage"
            if "extract" in explicit:
                return "extraction_error"
            if "structure" in explicit or "format" in explicit or "option" in explicit:
                return "structure"

        if status == AUDIT_STATUS_PASS:
            return "none"

        computed = _lower(raw.get("computed_vs_intended"))
        answer = _lower(raw.get("answer_correctness"))
        options = _lower(raw.get("option_consistency"))
        slot = _lower(raw.get("slot_match") or raw.get("design_vs_blueprint"))
        difficulty = _lower(raw.get("difficulty_match") or raw.get("difficulty"))

        if computed in {"mismatch", "fail", "failed"} or answer in {"fail", "failed", "wrong"}:
            return "answer_error"
        if options in {"fail", "failed"}:
            return "structure"
        if slot in {"fail", "failed", "mismatch"}:
            return "slot_mismatch"
        if difficulty in {"fail", "failed", "mismatch"}:
            return "difficulty"
        return "structure"

    @staticmethod
    def _normalize_fix_target(raw: dict[str, Any], issue_type: str, status: str) -> str:
        if status == AUDIT_STATUS_PASS:
            return "none"
        fix = raw.get("fix_target")
        if not fix and isinstance(raw.get("fix_instruction"), dict):
            fix = raw["fix_instruction"].get("fix_target")
        value = str(fix or "").strip().lower()

        if value in {"none", "no", "na", "n/a"}:
            return "none"
        if value in {"extractor", "extraction"}:
            return RoleType.EXTRACTOR.value
        if value in {"planner", "blueprint", "paper", "compose"}:
            return RoleType.PLANNER.value
        if value in {"generator", "question", "draft", "options", "option"}:
            return RoleType.GENERATOR.value
        if value in {"reasoner", "answer", "solution", "solve", "solver"}:
            return RoleType.REASONER.value
        if value in {"summarizer", "formatter", "format", "rubric"}:
            return RoleType.SUMMARIZER.value
        if value in {"human", "manual"}:
            return "human"

        if issue_type in {"answer_error"}:
            return RoleType.REASONER.value
        if issue_type in {"slot_mismatch", "difficulty", "structure", "ambiguity"}:
            return RoleType.GENERATOR.value
        if issue_type == "coverage":
            return RoleType.PLANNER.value
        if issue_type == "extraction_error":
            return RoleType.EXTRACTOR.value
        return "human"

    @staticmethod
    def _normalize_severity(raw: dict[str, Any], status: str, issue_type: str) -> str:
        value = str(raw.get("severity") or "").strip().lower()
        if value in {"none", "minor", "major", "blocker"}:
            return value
        if status == AUDIT_STATUS_PASS:
            return "none"
        if status in {AUDIT_STATUS_REJECT, AUDIT_STATUS_HUMAN}:
            return "blocker"
        if issue_type in {"answer_error", "ambiguity", "slot_mismatch"}:
            return "major"
        return "minor"

    @staticmethod
    def _extract_fix_instruction(raw: dict[str, Any]) -> str:
        detail = raw.get("fix_detail") or raw.get("fix_instruction") or raw.get("comment") or ""
        if isinstance(detail, dict):
            detail = detail.get("fix_detail") or detail.get("instruction") or detail.get("detail") or ""
        return str(detail).strip()

    @staticmethod
    def _normalize_confidence(raw: dict[str, Any]) -> str:
        value = str(raw.get("confidence") or "").strip().lower()
        if value in {"high", "medium", "low"}:
            return value
        return "medium"


class FixRouter:
    """Route semantic revision decisions from normalized audit results."""

    def __init__(self, *, max_revision_rounds: int = 1, human_after_major_failures: int = 2):
        self.max_revision_rounds = max_revision_rounds
        self.human_after_major_failures = human_after_major_failures

    def route(
        self,
        audit: AuditResult,
        *,
        current_round: int,
        is_single_choice: bool = True,
        previous_major_failures: int = 0,
        source_policy: ExecutionPolicy | None = None,
    ) -> FixRoute:
        max_rounds = self.max_revision_rounds
        human_threshold = self.human_after_major_failures
        if source_policy is not None:
            max_rounds = source_policy.semantic_revision.max_rounds
            human_threshold = source_policy.human_review_after_major_failures

        if audit.status == AUDIT_STATUS_PASS:
            return FixRoute(next_action="complete", reason="audit passed")
        if audit.status == AUDIT_STATUS_REJECT:
            return FixRoute(
                next_action="reject",
                target_role="human",
                pipeline_fix_target=PipelineFixTarget.NONE.value,
                instruction=audit.fix_instruction,
                reuse_previous_outputs=False,
                reason="audit rejected output",
            )
        if audit.status == AUDIT_STATUS_HUMAN:
            return self._human_route(audit, "audit requested human review")
        if current_round >= max_rounds:
            return self._human_route(audit, "revision budget exhausted")
        if audit.severity == "blocker" or previous_major_failures >= human_threshold:
            return self._human_route(audit, "major failure threshold reached")

        target_role = audit.fix_target
        pipeline_target = self._pipeline_target(audit, is_single_choice=is_single_choice)
        return FixRoute(
            next_action="revise",
            target_role=target_role,
            pipeline_fix_target=pipeline_target,
            instruction=audit.fix_instruction,
            reuse_previous_outputs=True,
            reason=f"{audit.issue_type} -> {target_role}",
        )

    @staticmethod
    def _human_route(audit: AuditResult, reason: str) -> FixRoute:
        return FixRoute(
            next_action="human_review",
            target_role="human",
            pipeline_fix_target=PipelineFixTarget.NONE.value,
            instruction=audit.fix_instruction,
            reuse_previous_outputs=False,
            reason=reason,
        )

    @staticmethod
    def _pipeline_target(audit: AuditResult, *, is_single_choice: bool) -> str:
        raw_target = str(audit.raw.get("fix_target") or "").strip().lower()
        if is_single_choice and raw_target in {"options", "option"}:
            return PipelineFixTarget.OPTIONS.value
        if not is_single_choice and raw_target == "rubric":
            return PipelineFixTarget.RUBRIC.value
        if audit.fix_target == RoleType.GENERATOR.value:
            return PipelineFixTarget.QUESTION.value
        if audit.fix_target == RoleType.REASONER.value:
            return PipelineFixTarget.ANSWER.value
        if audit.fix_target == RoleType.SUMMARIZER.value:
            return PipelineFixTarget.ANSWER.value
        if audit.fix_target == RoleType.PLANNER.value:
            return PipelineFixTarget.QUESTION.value
        if audit.fix_target == RoleType.EXTRACTOR.value:
            return PipelineFixTarget.QUESTION.value
        return PipelineFixTarget.ANSWER.value


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()
