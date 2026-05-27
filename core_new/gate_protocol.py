"""Gate protocol: shared data types for the multi-gate review system.

Three gates: Knowledge/Slot Gate → Stem Gate → Question/Option/Answer Gate.
Each gate produces a GateResult. The Stem Gate additionally produces a
StemContract on pass, which all downstream agents must respect.
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
class StemContract:
    """Canonical interpretation of a passed stem.

    Produced by StemGateCoordinator after all three lenses pass.
    All downstream agents (solver, option generator, reviewer) must use
    this instead of re-interpreting the raw stem text.
    """

    slot_id: str
    stem_text: str
    canonical_interpretation: str
    participating_conditions: list[str] = field(default_factory=list)
    non_participating_conditions: list[str] = field(default_factory=list)
    defined_terms: dict[str, str] = field(default_factory=dict)
    semantic_frame: str = ""
    constraint_summary: str = ""
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "stem_text": self.stem_text,
            "canonical_interpretation": self.canonical_interpretation,
            "participating_conditions": self.participating_conditions,
            "non_participating_conditions": self.non_participating_conditions,
            "defined_terms": self.defined_terms,
            "semantic_frame": self.semantic_frame,
            "constraint_summary": self.constraint_summary,
            "caveats": self.caveats,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StemContract:
        return cls(
            slot_id=data.get("slot_id", ""),
            stem_text=data.get("stem_text", ""),
            canonical_interpretation=data.get("canonical_interpretation", ""),
            participating_conditions=data.get("participating_conditions", []),
            non_participating_conditions=data.get("non_participating_conditions", []),
            defined_terms=data.get("defined_terms", {}),
            semantic_frame=data.get("semantic_frame", ""),
            constraint_summary=data.get("constraint_summary", ""),
            caveats=data.get("caveats", []),
        )


@dataclass
class GateResult:
    """Result from any gate review."""

    gate_name: str  # "knowledge_slot" | "stem" | "question"
    decision: GateDecision = GateDecision.PASS
    error_types: list[str] = field(default_factory=list)
    fix_instruction: str = ""
    fix_target: str = "none"  # "blueprint" | "stem" | "question" | "options" | "answer" | "none"
    stem_contract: Optional[StemContract] = None
    confidence: str = "medium"
    evidence: str = ""
    lens_results: dict[str, dict] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.decision in (GateDecision.PASS, GateDecision.WARNING)

    @property
    def blocked(self) -> bool:
        return self.decision == GateDecision.BLOCKED

    def to_dict(self) -> dict[str, Any]:
        d = {
            "gate_name": self.gate_name,
            "decision": self.decision.value,
            "error_types": self.error_types,
            "fix_instruction": self.fix_instruction,
            "fix_target": self.fix_target,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }
        if self.stem_contract:
            d["stem_contract"] = self.stem_contract.to_dict()
        if self.lens_results:
            d["lens_results"] = self.lens_results
        return d

    @classmethod
    def from_dict(cls, data: dict) -> GateResult:
        sc = None
        if "stem_contract" in data and data["stem_contract"]:
            sc = StemContract.from_dict(data["stem_contract"])
        return cls(
            gate_name=data.get("gate_name", "unknown"),
            decision=GateDecision(data.get("decision", "pass")),
            error_types=data.get("error_types", []),
            fix_instruction=data.get("fix_instruction", ""),
            fix_target=data.get("fix_target", "none"),
            stem_contract=sc,
            confidence=data.get("confidence", "medium"),
            evidence=data.get("evidence", ""),
            lens_results=data.get("lens_results", {}),
        )
