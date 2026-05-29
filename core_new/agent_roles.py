"""Role-level execution policies for Edu408 agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RoleType(str, Enum):
    EXTRACTOR = "extractor"
    PLANNER = "planner"
    GENERATOR = "generator"
    REASONER = "reasoner"
    AUDIT = "audit"
    SUMMARIZER = "summarizer"


class AuditMode(str, Enum):
    EXTRACTION_REVIEW = "extraction_review"
    BLUEPRINT_REVIEW = "blueprint_review"
    KNOWLEDGE_GATE = "knowledge_gate"
    ENVIRONMENT_CLOSURE_GATE = "environment_closure_gate"
    STEM_VERIFICATION = "stem_verification"
    QUESTION_REVIEW = "question_review"
    FINAL_PAPER_REVIEW = "final_paper_review"


class PipelineFixTarget(str, Enum):
    NONE = "none"
    EXTRACTION = "extraction"
    BLUEPRINT = "blueprint"
    QUESTION = "question"
    OPTIONS = "options"
    ANSWER = "answer"
    SOLUTION = "solution"
    RUBRIC = "rubric"
    FINAL_FORMAT = "final_format"
    HUMAN = "human"
    STEM = "stem"


@dataclass(frozen=True)
class TransportRetryPolicy:
    max_attempts: int = 3
    backoff: str = "exponential_jitter"
    retry_on: tuple[str, ...] = (
        "connection_error",
        "timeout",
        "rate_limit",
        "server_error",
        "empty_content",
        "malformed_envelope",
    )
    not_retry_on: tuple[str, ...] = (
        "validation_error",
        "format_error",
        "domain_error",
    )


@dataclass(frozen=True)
class FormatRepairPolicy:
    max_attempts: int = 1
    repair_on_empty_parse: bool = True
    repair_on_missing_fields: bool = True
    repair_on_validation_error: bool = True


@dataclass(frozen=True)
class SemanticRevisionPolicy:
    max_rounds: int = 1
    handled_by: str = "audit_fix_router"


@dataclass(frozen=True)
class FallbackPolicy:
    enabled: bool = False
    target: str = ""


@dataclass(frozen=True)
class TracePolicy:
    enabled: bool = True
    include_prompts: bool = False
    include_tool_observations: bool = True


@dataclass(frozen=True)
class ExecutionPolicy:
    role_type: RoleType
    transport_retry: TransportRetryPolicy = field(default_factory=TransportRetryPolicy)
    format_repair: FormatRepairPolicy = field(default_factory=FormatRepairPolicy)
    semantic_revision: SemanticRevisionPolicy = field(default_factory=SemanticRevisionPolicy)
    fallback: FallbackPolicy = field(default_factory=FallbackPolicy)
    trace: TracePolicy = field(default_factory=TracePolicy)
    human_review_after_major_failures: int = 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_type": self.role_type.value,
            "transport_retry": self.transport_retry.__dict__,
            "format_repair": self.format_repair.__dict__,
            "semantic_revision": self.semantic_revision.__dict__,
            "fallback": self.fallback.__dict__,
            "trace": self.trace.__dict__,
            "human_review_after_major_failures": self.human_review_after_major_failures,
        }


DEFAULT_EXECUTION_POLICIES: dict[RoleType, ExecutionPolicy] = {
    RoleType.EXTRACTOR: ExecutionPolicy(
        role_type=RoleType.EXTRACTOR,
        semantic_revision=SemanticRevisionPolicy(max_rounds=1),
        fallback=FallbackPolicy(enabled=True, target="needs_human_check"),
    ),
    RoleType.PLANNER: ExecutionPolicy(
        role_type=RoleType.PLANNER,
        semantic_revision=SemanticRevisionPolicy(max_rounds=2),
        fallback=FallbackPolicy(enabled=True, target="conservative_template"),
    ),
    RoleType.GENERATOR: ExecutionPolicy(
        role_type=RoleType.GENERATOR,
        semantic_revision=SemanticRevisionPolicy(max_rounds=1),
        fallback=FallbackPolicy(enabled=True, target="legacy_generator"),
    ),
    RoleType.REASONER: ExecutionPolicy(
        role_type=RoleType.REASONER,
        transport_retry=TransportRetryPolicy(max_attempts=2),
        semantic_revision=SemanticRevisionPolicy(max_rounds=0),
        fallback=FallbackPolicy(enabled=True, target="second_reasoner"),
    ),
    RoleType.AUDIT: ExecutionPolicy(
        role_type=RoleType.AUDIT,
        semantic_revision=SemanticRevisionPolicy(max_rounds=0),
        fallback=FallbackPolicy(enabled=True, target="human_review"),
    ),
    RoleType.SUMMARIZER: ExecutionPolicy(
        role_type=RoleType.SUMMARIZER,
        transport_retry=TransportRetryPolicy(max_attempts=2),
        semantic_revision=SemanticRevisionPolicy(max_rounds=0),
        fallback=FallbackPolicy(enabled=True, target="rule_based_router"),
    ),
}


def normalize_role_type(role_type: RoleType | str | None) -> RoleType:
    if isinstance(role_type, RoleType):
        return role_type
    if not role_type:
        return RoleType.GENERATOR
    try:
        return RoleType(str(role_type).lower())
    except ValueError:
        return RoleType.GENERATOR


def normalize_audit_mode(audit_mode: AuditMode | str | None) -> AuditMode | None:
    if isinstance(audit_mode, AuditMode):
        return audit_mode
    if not audit_mode:
        return None
    try:
        return AuditMode(str(audit_mode).lower())
    except ValueError:
        return None


def resolve_execution_policy(
    role_type: RoleType | str | None,
    override: ExecutionPolicy | None = None,
) -> ExecutionPolicy:
    if override is not None:
        return override
    return DEFAULT_EXECUTION_POLICIES[normalize_role_type(role_type)]


_AUDIT_MODE_OWNER: dict[AuditMode, RoleType] = {
    AuditMode.EXTRACTION_REVIEW: RoleType.EXTRACTOR,
    AuditMode.BLUEPRINT_REVIEW: RoleType.PLANNER,
    AuditMode.KNOWLEDGE_GATE: RoleType.PLANNER,
    AuditMode.ENVIRONMENT_CLOSURE_GATE: RoleType.AUDIT,
    AuditMode.STEM_VERIFICATION: RoleType.AUDIT,
    AuditMode.QUESTION_REVIEW: RoleType.GENERATOR,
    AuditMode.FINAL_PAPER_REVIEW: RoleType.SUMMARIZER,
}


def source_policy_for_audit_mode(
    mode: AuditMode | str | None = None,
) -> ExecutionPolicy:
    """Return the ExecutionPolicy for the role that owns the artifact being audited.

    This determines the semantic revision budget and human-review threshold
    based on which role produced the audited output.

    Examples:
        question_review -> Generator policy (max_rounds=1)
        blueprint_review -> Planner policy (max_rounds=2)
        extraction_review -> Extractor policy (max_rounds=1)
        final_paper_review -> Summarizer policy (max_rounds=0)
    """
    mode_enum = normalize_audit_mode(mode)
    if mode_enum is None:
        return DEFAULT_EXECUTION_POLICIES[RoleType.GENERATOR]
    owner_role = _AUDIT_MODE_OWNER.get(mode_enum, RoleType.GENERATOR)
    return DEFAULT_EXECUTION_POLICIES[owner_role]
