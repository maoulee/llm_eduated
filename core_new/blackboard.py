"""Shared blackboard state for multi-agent workflows."""

from __future__ import annotations

import asyncio
import copy
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional

from .markdown_parser import parse_extraction_markdown


Parser = Callable[[str], Any]


@dataclass
class AgentRecord:
    agent_name: str
    timestamp: float
    phase: str
    status: str
    input_snapshot: Dict[str, Any]
    output: Any
    error: Optional[str] = None
    tokens_used: int = 0
    latency_s: float = 0.0
    version: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentRecord":
        return cls(**data)


class Blackboard:
    """Shared state for one pipeline run."""

    def __init__(
        self,
        task_id: str,
        task_type: str,
        initial_state: Optional[Dict[str, Any]] = None,
    ):
        self.task_id = task_id
        self.task_type = task_type
        self.status = "pending"
        self.created_at = time.time()
        self.updated_at = self.created_at
        self._raw: Dict[str, str] = {}
        self._state: Dict[str, Any] = {}
        self._parsed_cache: Dict[str, Any] = {}
        self._parsers: Dict[str, Parser] = {}
        for key, value in (initial_state or {}).items():
            if isinstance(value, str):
                self._raw[key] = value
            else:
                self._state[key] = copy.deepcopy(value)
                self._parsed_cache[key] = copy.deepcopy(value)
        self._history: List[AgentRecord] = []
        self._version = 0
        self._lock = asyncio.Lock()

    def get(self, key: str, default=None) -> Any:
        return self.get_parsed(key, default=default)

    def read(self, key: str, default: str = "") -> str:
        """Return raw Markdown/text for a blackboard key."""
        if key in self._raw:
            return self._raw[key]
        if key in self._state:
            return _value_to_markdown(self._state[key])
        return default

    def get_parsed(
        self,
        key: str,
        *,
        parser: Optional[Parser] = None,
        default=None,
    ) -> Any:
        """Return parsed data for a key, parsing raw Markdown lazily."""
        if key in self._parsed_cache:
            return copy.deepcopy(self._parsed_cache[key])
        if key in self._state:
            return copy.deepcopy(self._state[key])
        if key not in self._raw:
            return default

        parse_fn = parser or self._parsers.get(key) or _default_parser_for_key(key)
        raw = self._raw[key]
        if parse_fn is None:
            return raw
        try:
            parsed = parse_fn(raw)
        except Exception:
            return default
        if parsed is None:
            return default
        self._parsed_cache[key] = copy.deepcopy(parsed)
        self._state[key] = copy.deepcopy(parsed)
        self._promote_routing_fields(parsed)
        return copy.deepcopy(parsed)

    def raw_state(self) -> Dict[str, str]:
        return copy.deepcopy(self._raw)

    def state(self) -> Dict[str, Any]:
        merged = copy.deepcopy(self._state)
        for key in self._raw:
            if key not in merged:
                parsed = self.get_parsed(key, default=None)
                merged[key] = parsed if parsed is not None else self._raw[key]
        return merged

    def get_relevant_state(self, agent_name: str) -> Dict[str, Any]:
        """Return a state snapshot.

        This hook is intentionally simple for now. Specific agents can choose
        fields inside build_input(), while future schema maps can narrow this.
        """
        snapshot = self.state()
        snapshot["_raw"] = self.raw_state()
        snapshot["_agent_name"] = agent_name
        return snapshot

    async def set_input(self, key: str, value: Any, agent_name: str = "input") -> AgentRecord:
        if isinstance(value, str):
            return await self.write(
                agent_name=agent_name,
                md_text=value,
                phase="input",
                output_key=key,
                input_snapshot={},
            )
        return await self.update(agent_name=agent_name, output=value, phase="input", output_key=key, input_snapshot={})

    async def write(
        self,
        agent_name: str,
        md_text: str,
        phase: str,
        *,
        output_key: Optional[str] = None,
        parsed: Any = None,
        parser: Optional[Parser] = None,
        input_snapshot: Optional[Dict[str, Any]] = None,
        status: str = "success",
        tokens_used: int = 0,
        latency_s: float = 0.0,
        error: Optional[str] = None,
    ) -> AgentRecord:
        async with self._lock:
            self._version += 1
            key = output_key or agent_name
            raw = md_text or ""
            self._raw[key] = raw
            self._raw[f"{phase}_result"] = raw
            if parser:
                self._parsers[key] = parser
                self._parsers[f"{phase}_result"] = parser
            self._parsed_cache.pop(key, None)
            self._parsed_cache.pop(f"{phase}_result", None)
            self._state.pop(key, None)
            self._state.pop(f"{phase}_result", None)
            if parsed is not None:
                self._state[key] = copy.deepcopy(parsed)
                self._state[f"{phase}_result"] = copy.deepcopy(parsed)
                self._parsed_cache[key] = copy.deepcopy(parsed)
                self._parsed_cache[f"{phase}_result"] = copy.deepcopy(parsed)
                self._promote_routing_fields(parsed)
            self._set_meta(agent_name, phase)
            self._update_status(status)

            record = AgentRecord(
                agent_name=agent_name,
                timestamp=self.updated_at,
                phase=phase,
                status=status,
                input_snapshot=copy.deepcopy(input_snapshot or self.state()),
                output=raw,
                error=error,
                tokens_used=tokens_used,
                latency_s=latency_s,
                version=self._version,
            )
            self._history.append(record)
            return record

    async def update(
        self,
        agent_name: str,
        output: Any,
        phase: str,
        *,
        output_key: Optional[str] = None,
        input_snapshot: Optional[Dict[str, Any]] = None,
        status: str = "success",
        tokens_used: int = 0,
        latency_s: float = 0.0,
        error: Optional[str] = None,
    ) -> AgentRecord:
        if isinstance(output, str):
            return await self.write(
                agent_name=agent_name,
                md_text=output,
                phase=phase,
                output_key=output_key,
                input_snapshot=input_snapshot,
                status=status,
                tokens_used=tokens_used,
                latency_s=latency_s,
                error=error,
            )
        async with self._lock:
            self._version += 1
            key = output_key or agent_name
            self._state[key] = output
            self._state[f"{phase}_result"] = output
            self._parsed_cache[key] = copy.deepcopy(output)
            self._parsed_cache[f"{phase}_result"] = copy.deepcopy(output)
            self._raw[key] = _value_to_markdown(output)
            self._raw[f"{phase}_result"] = self._raw[key]
            if isinstance(output, dict):
                self._promote_routing_fields(output)
                state_updates = output.get("_state_updates")
                if isinstance(state_updates, dict):
                    self._state.update(state_updates)
            self._set_meta(agent_name, phase)
            self._update_status(status)

            record = AgentRecord(
                agent_name=agent_name,
                timestamp=self.updated_at,
                phase=phase,
                status=status,
                input_snapshot=copy.deepcopy(input_snapshot or self.state()),
                output=self._raw[key],
                error=error,
                tokens_used=tokens_used,
                latency_s=latency_s,
                version=self._version,
            )
            self._history.append(record)
            return record

    async def mark_failed(
        self,
        agent_name: str,
        error: str,
        *,
        phase: str = "unknown",
        input_snapshot: Optional[Dict[str, Any]] = None,
        latency_s: float = 0.0,
    ) -> AgentRecord:
        return await self.update(
            agent_name=agent_name,
            output=None,
            phase=phase,
            input_snapshot=input_snapshot,
            status="failed",
            error=error,
            latency_s=latency_s,
        )

    def get_history(self, agent_name: Optional[str] = None) -> List[AgentRecord]:
        if agent_name is None:
            return list(self._history)
        return [record for record in self._history if record.agent_name == agent_name]

    def get_latest(self, phase: str) -> Optional[AgentRecord]:
        for record in reversed(self._history):
            if record.phase == phase:
                return record
        return None

    def get_next_agents(self) -> List[str]:
        """Placeholder for schema-driven routing."""
        return []

    def mark_completed(self) -> None:
        self.status = "completed"
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self._version,
            "state": self.state(),
            "raw": self.raw_state(),
            "history": [record.to_dict() for record in self._history],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Blackboard":
        bb = cls(data["task_id"], data["task_type"], {})
        bb.status = data.get("status", "pending")
        bb.created_at = data.get("created_at", time.time())
        bb.updated_at = data.get("updated_at", bb.created_at)
        bb._version = int(data.get("version", 0))
        bb._raw = dict(data.get("raw", {}))
        bb._state = copy.deepcopy(data.get("state", {}))
        bb._parsed_cache = copy.deepcopy(bb._state)
        bb._history = [AgentRecord.from_dict(item) for item in data.get("history", [])]
        return bb

    def to_markdown(self) -> str:
        lines = [
            f"# Blackboard: {self.task_id}",
            "",
            f"- task_type: `{self.task_type}`",
            f"- status: `{self.status}`",
            f"- version: `{self._version}`",
            "",
            "## Raw Agent Outputs",
            "",
        ]
        for key, value in self._raw.items():
            if key.startswith("_"):
                continue
            lines.extend([f"### {key}", "", value.strip(), ""])
        if not self._raw:
            lines.extend(["_No raw Markdown outputs yet._", ""])

        structured_inputs = {
            key: value
            for key, value in self._state.items()
            if not key.startswith("_") and key not in self._raw and not key.endswith("_result")
        }
        if structured_inputs:
            lines.extend([
                "## Structured Inputs",
                "",
                "```json",
                _json_dumps(structured_inputs, indent=2),
                "```",
                "",
            ])

        lines.extend([
            "## History",
        ])
        for record in self._history:
            lines.append(
                f"- v{record.version} `{record.phase}` `{record.agent_name}` "
                f"{record.status} ({record.latency_s:.2f}s)"
            )
            if record.error:
                lines.append(f"  - error: {record.error}")
        return "\n".join(lines)

    def _set_meta(self, agent_name: str, phase: str) -> None:
        self._state["_last_agent"] = agent_name
        self._state["_last_phase"] = phase
        self._state["_version"] = self._version
        self._raw["_last_agent"] = agent_name
        self._raw["_last_phase"] = phase
        self._raw["_version"] = str(self._version)
        self.updated_at = time.time()

    def _update_status(self, status: str) -> None:
        if status == "failed":
            self.status = "failed"
        elif self.status == "pending":
            self.status = "running"

    def _promote_routing_fields(self, output: Any) -> None:
        if not isinstance(output, dict):
            return
        for decision_key in (
            "decision",
            "aggregator_decision",
            "paper_review_decision",
            "route",
            "consistent",
        ):
            if decision_key in output:
                self._state[decision_key] = output[decision_key]
                self._parsed_cache[decision_key] = output[decision_key]


def _json_dumps(value: Any, *, indent: Optional[int] = None) -> str:
    return json.dumps(value, ensure_ascii=False, indent=indent, default=str)


def _value_to_markdown(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return "```json\n" + _json_dumps(value, indent=2) + "\n```"


def _default_parser_for_key(key: str) -> Optional[Parser]:
    phase_map = {
        "question_structure": "P1",
        "P1_result": "P1",
        "knowledge_units": "P2",
        "P2_result": "P2",
        "trigger_rules": "P3",
        "P3_result": "P3",
        "reasoning_pattern": "P4",
        "P4_result": "P4",
    }
    phase = phase_map.get(key)
    if phase:
        return lambda raw, p=phase: parse_extraction_markdown(raw, p)
    return _parse_json_or_markdown_value


def _parse_json_or_markdown_value(raw: str) -> Any:
    text = raw.strip()
    if not text:
        return None
    if text.startswith("```"):
        fence = text.split("```", 2)
        if len(fence) >= 3:
            text = fence[1]
            if text.lstrip().startswith("json"):
                text = text.lstrip()[4:].strip()
    if text.startswith("{") or text.startswith("["):
        return json.loads(text)
    return raw
