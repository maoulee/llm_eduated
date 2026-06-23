"""Trace records for tool-agent runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolTrace:
    iteration: int
    tool_name: str
    arguments: dict[str, Any]
    observation: str


@dataclass
class AgentTrace:
    task: str
    final: str = ""
    tool_traces: list[ToolTrace] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_jsonl(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as f:
            for item in self.tool_traces:
                f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
            if self.final:
                f.write(json.dumps({"final": self.final}, ensure_ascii=False) + "\n")
