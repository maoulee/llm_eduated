"""Shared configuration for the document pipeline.

This module owns agent metadata and runtime defaults.  Scheduler/executor code
and orchestration code import from here instead of each loading AgentMD files or
duplicating constants.
"""

from __future__ import annotations

from .agent_loader import get_agent_dicts

MAX_ANALYSIS_ITERATIONS = 3
MAX_AGENT_ATTEMPTS = 3
DEFAULT_MAX_TOKENS = 20000
DEFAULT_THINKING_BUDGET = 10000
PYTHON_EXEC_TIMEOUT = 30

# Keep the doc pipeline deterministic enough to preserve tool-call shape.
DOC_SAMPLING_OVERRIDES = {
    "temperature": 0.2,
    "top_p": 0.9,
}

# Load AgentMD files once at module level.
AGENT_PROMPTS, AGENT_OUTPUT_FILES, MULTI_TURN_AGENTS, _LOADED_THINKING_BUDGET = get_agent_dicts()

# Per-role thinking budget (tokens). None = no cap.
# Values loaded from AgentMD frontmatter override these defaults.
_ROLE_THINKING_DEFAULTS = {
    "design": 8000,
    "question": 10000,
    "analysis": 10000,
    "coding": 10000,
    "review": 8000,
    "fix": 10000,
}
ROLE_THINKING_BUDGET = {**_ROLE_THINKING_DEFAULTS, **_LOADED_THINKING_BUDGET}
