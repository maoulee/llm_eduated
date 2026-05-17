"""ToolCard and AgentCard — lightweight metadata for the unified runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ToolCard:
    """Metadata for a tool registered in ToolRegistry."""

    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)
    mode: str = "sync"  # "sync" or "async"


@dataclass
class AgentCard:
    """Metadata for an agent managed by AgentRuntime."""

    name: str
    role: str
    allowed_tools: List[str] = field(default_factory=list)
    max_steps: int = 5
    input_format: str = ""
    output_format: str = "dict"

    # Lazy-loaded module path: "core_new.agents.file_code_solver:FileCodeSolverAgent"
    module_path: str = ""
