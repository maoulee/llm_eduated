"""Minimal DeepTutor-style action-observation loop for 408 generation."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core_new.llm_gateway import LLMGateway

from .context import ContextBuilder
from .registry import ToolRegistry
from .trace import AgentTrace, ToolTrace

logger = logging.getLogger(__name__)


@dataclass
class AgentLoopResult:
    final: str
    tools_used: list[str]
    messages: list[dict[str, Any]]
    trace: AgentTrace


class Edu408AgentLoop:
    """A small tool loop for 408 agent nodes.

    Existing providers in this repo are text/chat oriented, so this loop uses
    a JSON-in-text action protocol while preserving DeepTutor's registry and
    action-observation control flow. A native tool-call provider can be added
    later behind the same ToolRegistry boundary.
    """

    def __init__(
        self,
        gateway: LLMGateway,
        tools: ToolRegistry,
        *,
        workspace: str | Path,
        max_iterations: int = 8,
        max_tokens: int = 4096,
        enable_thinking: bool = False,
    ):
        self.gateway = gateway
        self.tools = tools
        self.context = ContextBuilder(workspace)
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking

    async def run(
        self,
        task: str,
        *,
        allowed_tools: list[str] | None = None,
        skill_names: list[str] | None = None,
        history: list[dict[str, Any]] | None = None,
        extra_system: str = "",
        trace_path: str | Path | None = None,
    ) -> AgentLoopResult:
        messages = self.context.build_messages(
            task,
            history=history,
            tool_schemas=self.tools.get_definitions(allowed_tools),
            skill_names=skill_names,
            extra_system=extra_system,
        )
        trace = AgentTrace(task=task, messages=messages)
        tools_used: list[str] = []
        allowed = set(allowed_tools or self.tools.tool_names)

        final = ""
        for iteration in range(1, self.max_iterations + 1):
            result = await self.gateway.generate_text(
                messages,
                max_tokens=self.max_tokens,
                enable_thinking=self.enable_thinking,
            )
            if not result.ok:
                final = f"Error: LLM call failed: {result.error_message}"
                break

            content = result.content or ""
            self.context.add_assistant_message(messages, content)
            calls = _extract_tool_calls(content)

            if not calls:
                final = content.strip()
                break

            for call in calls:
                tool_name = call.get("tool") or call.get("name")
                arguments = call.get("arguments") or call.get("params") or {}
                if not isinstance(tool_name, str) or not tool_name:
                    observation = "Error: tool call missing `tool` name"
                elif tool_name not in allowed:
                    observation = f"Error: Tool '{tool_name}' is not allowed for this run."
                elif not isinstance(arguments, dict):
                    observation = "Error: tool arguments must be an object"
                else:
                    logger.info("AgentLoop tool call: %s(%s)", tool_name, json.dumps(arguments)[:200])
                    observation = await self.tools.execute(tool_name, arguments)
                    tools_used.append(tool_name)

                trace.tool_traces.append(
                    ToolTrace(
                        iteration=iteration,
                        tool_name=str(tool_name),
                        arguments=arguments if isinstance(arguments, dict) else {},
                        observation=observation,
                    )
                )
                self.context.add_tool_observation(messages, str(tool_name), observation[:16000])
        else:
            final = f"Max iterations ({self.max_iterations}) reached without a final answer."

        trace.final = final
        trace.messages = messages
        if trace_path:
            trace.write_jsonl(trace_path)
        return AgentLoopResult(final=final, tools_used=tools_used, messages=messages, trace=trace)


def _extract_tool_calls(content: str) -> list[dict[str, Any]]:
    """Extract JSON tool calls from model output."""
    candidates: list[str] = []

    for match in re.finditer(r"```(?:json)?\s*(.*?)```", content, re.DOTALL | re.IGNORECASE):
        candidates.append(match.group(1).strip())

    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)
    if stripped.startswith("[") and stripped.endswith("]"):
        candidates.append(stripped)

    calls: list[dict[str, Any]] = []
    for raw in candidates:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            if "tool" in data or "name" in data:
                calls.append(data)
            elif isinstance(data.get("tool_calls"), list):
                calls.extend([item for item in data["tool_calls"] if isinstance(item, dict)])
        elif isinstance(data, list):
            calls.extend([item for item in data if isinstance(item, dict) and ("tool" in item or "name" in item)])
    return calls
