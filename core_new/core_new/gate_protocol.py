"""Gate protocol: shared data types for the 2-gate review system.

Gate 1: Knowledge Gate — validates knowledge points before stem generation
Gate 2: Environment Closure Gate — validates stem environment before solving

Each gate produces a GateResult with:
- Control fields (verdict, severity, can_continue) — parsed from YAML front matter
- Natural language report (report_md) — stored but not structurally parsed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class GateDecision(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    BLOCKED = "blocked"


@dataclass
class GateResult:
    """Result from any gate review.

    Control fields are for pipeline routing.
    report_md is the full natural language review — for humans and downstream agents.
    """

    gate_name: str  # "knowledge" | "environment_closure"
    verdict: GateDecision = GateDecision.PASS
    severity: str = "pass"  # pass / info / warning / blocking
    issue_types: list[str] = field(default_factory=list)
    can_continue: bool = True
    can_send_to_solver: bool = True
    fix_instruction: str = ""
    fix_target: str = "none"  # "blueprint" | "stem" | "none"
    confidence: str = "medium"
    summary: str = ""
    report_md: str = ""
    raw_response: str = ""

    @property
    def passed(self) -> bool:
        return self.verdict in (GateDecision.PASS, GateDecision.WARNING)

    @property
    def blocked(self) -> bool:
        return self.verdict == GateDecision.BLOCKED

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "verdict": self.verdict.value,
            "severity": self.severity,
            "issue_types": self.issue_types,
            "can_continue": self.can_continue,
            "can_send_to_solver": self.can_send_to_solver,
            "fix_instruction": self.fix_instruction,
            "fix_target": self.fix_target,
            "confidence": self.confidence,
            "summary": self.summary,
            "report_md": self.report_md[:2000],
        }

    @classmethod
    def from_dict(cls, data: dict) -> GateResult:
        return cls(
            gate_name=data.get("gate_name", "unknown"),
            verdict=GateDecision(data.get("verdict", "pass")),
            severity=data.get("severity", "pass"),
            issue_types=data.get("issue_types", []),
            can_continue=data.get("can_continue", True),
            can_send_to_solver=data.get("can_send_to_solver", True),
            fix_instruction=data.get("fix_instruction", ""),
            fix_target=data.get("fix_target", "none"),
            confidence=data.get("confidence", "medium"),
            summary=data.get("summary", ""),
            report_md=data.get("report_md", ""),
        )
