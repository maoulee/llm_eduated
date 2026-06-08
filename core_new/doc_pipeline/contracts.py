"""Typed contracts for the document pipeline.

Replaces bare dicts with dataclasses for IDE completion and runtime clarity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SlotBlueprint:
    slot_id: str
    target_subject: str = ""
    target_family: str = ""
    primary_target_name: str = ""
    target_difficulty: int = 3
    examination_mode: str = ""
    k_target: str = ""
    difficulty_rationale: str = ""
    question_type: str = "single_choice"
    # v2 fields for mode selection
    score: int = 2
    active_selection: dict = field(default_factory=dict)
    candidate_pool_visible: list[str] = field(default_factory=list)
    excluded_modes: list[str] = field(default_factory=list)
    excluded_knowledge: list[str] = field(default_factory=list)


@dataclass
class ComposeArtifact:
    slot_id: str
    assembled_md: str
    assembled_path: str


@dataclass
class PipelineResult:
    slot_id: str
    ok: bool
    pipeline_type: str = "doc_5layer"
    total_time_s: float = 0.0
    analysis_iterations: int = 0
    review_status: str = "?"
    error: str = ""
    files: dict[str, str] = field(default_factory=dict)
    final_content: str = ""
    code_exec_ok: bool = False
    code_skipped: bool = False
