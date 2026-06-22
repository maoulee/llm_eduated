"""compose — modular slot composition and question generation.

Public API:
    run_compose       — Phase A: compose outline + assemble experience docs
    run_generate      — Phase B: load artifacts + generate questions
    run_composition   — Full pipeline (compose + generate)
    compose_paper     — Generate paper outline/blueprint
    assemble_slot_experience_doc — Build per-slot assembled markdown
    main              — CLI entry point
"""

from .artifact_store import assemble_slot_experience_doc
from .cli import main, run_composition
from .compose_runner import compose_paper, run_compose
from .generate_runner import run_generate

__all__ = [
    "run_compose",
    "run_generate",
    "run_composition",
    "compose_paper",
    "assemble_slot_experience_doc",
    "main",
]
