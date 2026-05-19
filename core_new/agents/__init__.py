"""Agent implementations for multi-agent workflows."""

from .slot_agents import (
    PaperComposerAgent,
    BlueprintReviewerAgent,
    QuestionFixerAgent,
    PaperReviewerAgent,
)
from .file_code_solver import FileCodeSolverAgent, CodeSolution
from .hybrid_subjective_team import (
    QuestionDesignerAgent,
    HybridSolutionFormatter,
    HybridRubricWriter,
    IntentBasedReviewer,
    HybridSubjectivePipeline,
    HybridSubjectiveResult,
)
from .agent_registry import AgentRegistry
from .paper_formatter import PaperFormatterAgent
from . import solver_utils

__all__ = [
    "PaperComposerAgent",
    "BlueprintReviewerAgent",
    "QuestionFixerAgent",
    "PaperReviewerAgent",
    "FileCodeSolverAgent",
    "CodeSolution",
    "QuestionDesignerAgent",
    "HybridSolutionFormatter",
    "HybridRubricWriter",
    "IntentBasedReviewer",
    "HybridSubjectivePipeline",
    "HybridSubjectiveResult",
    "AgentRegistry",
    "PaperFormatterAgent",
    "solver_utils",
]
