"""Base classes for multi-agent workflows."""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from .blackboard import AgentRecord, Blackboard
from .llm_gateway import LLMGateway, LLMResult


@dataclass
class AgentConfig:
    name: str
    phase: str
    system_prompt: str = ""
    output_format: str = "markdown"
    output_key: Optional[str] = None
    max_tokens: int = 8192
    enable_thinking: bool = True
    max_retries: int = 1
    timeout_s: float = 300.0


class BaseAgent(ABC):
    """Base class for LLM-backed agents."""

    def __init__(self, config: AgentConfig, llm_backend):
        self.config = config
        self.llm = _ensure_gateway(llm_backend)

    @abstractmethod
    def build_input(self, blackboard: Blackboard) -> str:
        """Build the user prompt from blackboard state."""

    @abstractmethod
    def parse_output(self, raw: Any) -> Any:
        """Parse model output into structured data."""

    async def execute(self, blackboard: Blackboard) -> AgentRecord:
        input_snapshot = blackboard.get_relevant_state(self.config.name)
        start = time.monotonic()
        last_error = ""

        for attempt in range(self.config.max_retries + 1):
            try:
                prompt = self.build_input(blackboard)
                result = await asyncio.wait_for(
                    self._call_llm(prompt),
                    timeout=self.config.timeout_s,
                )
                if not result.ok:
                    raise RuntimeError(f"{result.error_code}: {result.error_message}")
                raw_text = result.content or ""
                raw_for_parse = result.parsed_json if self.config.output_format == "json" else raw_text
                parsed = self.parse_output(raw_for_parse)
                if not raw_text and parsed is not None:
                    raw_text = json.dumps(parsed, ensure_ascii=False, indent=2, default=str)
                latency_s = time.monotonic() - start
                return await blackboard.write(
                    self.config.name,
                    raw_text,
                    self.config.phase,
                    output_key=self.config.output_key,
                    parsed=parsed,
                    input_snapshot=input_snapshot,
                    tokens_used=result.tokens_used,
                    latency_s=latency_s,
                )
            except Exception as exc:
                last_error = str(exc)
                if attempt >= self.config.max_retries:
                    latency_s = time.monotonic() - start
                    return await blackboard.mark_failed(
                        self.config.name,
                        last_error,
                        phase=self.config.phase,
                        input_snapshot=input_snapshot,
                        latency_s=latency_s,
                    )
                await asyncio.sleep(min(2 ** attempt, 5))

    async def _call_llm(self, prompt: str) -> LLMResult:
        messages = []
        if self.config.system_prompt:
            messages.append({"role": "system", "content": self.config.system_prompt})
        messages.append({"role": "user", "content": prompt})

        fmt = self.config.output_format.lower()
        if fmt == "json":
            return await self.llm.generate_json(
                messages,
                max_tokens=self.config.max_tokens,
                enable_thinking=self.config.enable_thinking,
            )
        if fmt in {"text", "plain"}:
            return await self.llm.generate_text(
                messages,
                max_tokens=self.config.max_tokens,
                enable_thinking=self.config.enable_thinking,
            )
        return await self.llm.generate_reasoned(
            messages,
            max_tokens=self.config.max_tokens,
            enable_thinking=self.config.enable_thinking,
        )


class NoLLMAgent(BaseAgent):
    """Base class for agents that compute locally instead of calling an LLM."""

    async def _call_llm(self, prompt: str) -> LLMResult:
        raise NotImplementedError("NoLLMAgent.execute should be overridden")


def parse_json_text(raw: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if raw is None:
        raise ValueError("empty model output")
    text = str(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    else:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]
    return json.loads(text)


def _ensure_gateway(obj) -> LLMGateway:
    if isinstance(obj, LLMGateway):
        return obj
    return LLMGateway.from_provider(obj, "wrapped")
