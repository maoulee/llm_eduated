"""Minimal DeepTutor-style action-observation loop for 408 generation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core_new.llm_gateway import LLMGateway

from core_new.agent_tools import ToolExecutor

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
    policy_applied: dict | None = None


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
        execution_policy=None,
    ):
        self.gateway = gateway
        self.tools = tools
        self.context = ContextBuilder(workspace)
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking
        self.execution_policy = execution_policy

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
        allowed = set(allowed_tools or self.tools.tool_names)

        # Build messages WITHOUT tool schemas in system prompt (native tool calling)
        messages = self.context.build_messages(
            task,
            history=history,
            tool_schemas=None,
            skill_names=skill_names,
            extra_system=extra_system,
            native_tools=True,
        )
        trace = AgentTrace(task=task, messages=messages)
        if self.execution_policy and not self.execution_policy.trace.enabled:
            trace = None

        # Build OpenAI-format tools and executor
        filtered_tools = [t for name, t in self.tools._tools.items() if name in allowed]
        openai_tools = [t.to_openai_tool() for t in filtered_tools]
        executor = ToolExecutor(filtered_tools)

        result = await self.gateway.generate_with_tools(
            messages,
            tools=openai_tools,
            tool_executor=executor,
            max_tokens=self.max_tokens,
            enable_thinking=self.enable_thinking,
            max_rounds=self.max_iterations,
        )

        # Extract tools used from messages for trace
        tools_used = []
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tools_used.append(tc["function"]["name"])

        final = result.content or ""

        if trace is not None:
            trace.final = final
            trace.messages = messages
            if trace_path:
                trace.write_jsonl(trace_path)

        return AgentLoopResult(
            final=final,
            tools_used=tools_used,
            messages=messages,
            trace=trace if trace is not None else AgentTrace(task=task),
            policy_applied=self.execution_policy.to_dict() if self.execution_policy else None,
        )
