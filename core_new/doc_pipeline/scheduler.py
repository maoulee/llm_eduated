"""Agent scheduler for the document-based pipeline.

Responsibilities:
  1. Read files → inject into prompts
  2. Call agents via Edu408AgentLoop + write_file tool
  3. Manage multi-turn sessions for iterative agents
  4. Normalize protocol/textual tool-call output
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from core_new.agent_runtime.registry import ToolRegistry
from core_new.agent_tools import ToolExecutor
from core_new.llm_gateway import LLMGateway
from core_new.provider_router import get_gateway

from .config import (
    AGENT_OUTPUT_FILES,
    AGENT_PROMPTS,
    DEFAULT_MAX_TOKENS,
    DEFAULT_THINKING_BUDGET,
    DOC_SAMPLING_OVERRIDES,
    MAX_AGENT_ATTEMPTS,
    MAX_ANALYSIS_ITERATIONS,
    MULTI_TURN_AGENTS,
    PYTHON_EXEC_TIMEOUT,
    ROLE_THINKING_BUDGET,
)
from .write_file_tool import WriteFileTool

logger = logging.getLogger(__name__)


class DocScheduler:
    """Agent scheduler: read inputs, route providers, execute tool calls."""

    def __init__(
        self,
        gateway: LLMGateway,
        workspace: str | Path = "workspace",
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        enable_thinking: bool | None = None,
        model_routing: dict[str, str] | None = None,
    ):
        self.gateway = gateway
        self.workspace = Path(workspace).resolve()
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking
        self.model_routing = model_routing  # role → provider name
        # Multi-turn session state: role → message list
        self._sessions: dict[str, list[dict[str, Any]]] = {}
        # Gateway cache: provider name → LLMGateway
        self._gateway_cache: dict[str, LLMGateway] = {}

    def _get_gateway_for_role(self, role: str) -> LLMGateway:
        """Resolve the gateway for a given agent role.

        If model_routing specifies a provider for this role, create/return
        the corresponding gateway.  Otherwise fall back to self.gateway.
        """
        if not self.model_routing or role not in self.model_routing:
            return self.gateway
        provider_name = self.model_routing[role]
        if provider_name not in self._gateway_cache:
            self._gateway_cache[provider_name] = get_gateway(provider_name)
            logger.info("Resolved gateway for role '%s': %s", role, provider_name)
        return self._gateway_cache[provider_name]

    # ── Agent execution ──────────────────────────────────────────

    async def run_agent(
        self,
        role: str,
        task: str,
        *,
        slot_id: str,
        inject_files: dict[str, str] | None = None,
        continue_session: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        """Run an agent and return the final text content.

        Uses generate_with_tools() directly for full control over message order.
        vLLM requires system message at the very start of the conversation.

        Args:
            role: Agent role key (design, question, analysis, etc.)
            task: The user prompt for this turn.
            slot_id: Slot identifier for file namespacing.
            inject_files: {label: filepath} — files to read and append to task.
            continue_session: If True, append to existing session (incremental).
            max_tokens: Override default max_tokens for this call.

        Returns:
            The final text content from the agent.
        """
        ws = self.workspace / slot_id
        ws.mkdir(parents=True, exist_ok=True)

        # 1. Read inject files and append to task
        full_task = task
        if inject_files:
            for label, fpath in inject_files.items():
                path = Path(fpath)
                if not path.exists():
                    logger.warning("Inject file not found: %s", fpath)
                    continue
                content = path.read_text(encoding="utf-8")
                full_task += f"\n\n## {label}\n{content}"

        # 2. Build or continue message history
        if continue_session and role in self._sessions:
            messages = list(self._sessions[role])
            messages.append({"role": "user", "content": full_task})
        else:
            system_prompt = AGENT_PROMPTS.get(role, "")
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_task},
            ]

        # 3. Build tool registry with write_file tool
        registry = ToolRegistry()
        registry.register(WriteFileTool(workspace=ws))

        # 4. Convert to OpenAI tool schemas and build executor
        tool_list = [registry.get("write_file")]
        executor = ToolExecutor(tool_list)
        openai_tools = [t.to_openai_tool() for t in tool_list]

        # 5. Streaming tool-calling loop via shared gateway transport.
        gateway = self._get_gateway_for_role(role)
        effective_max_tokens = max_tokens or self.max_tokens
        effective_thinking_budget = ROLE_THINKING_BUDGET.get(role, DEFAULT_THINKING_BUDGET)
        expected_fn = AGENT_OUTPUT_FILES.get(role, "output.md")
        expected_path = ws / expected_fn
        final_text = ""

        # Avoid accepting stale artifacts from previous attempts/runs.
        if expected_path.exists():
            expected_path.unlink()

        # Force a tool call — we only register write_file, so naming it
        # explicitly is equivalent to "required" but works on both vLLM and GLM.
        forced_tool_choice = {
            "type": "function",
            "function": {"name": "write_file"},
        }

        for attempt in range(MAX_AGENT_ATTEMPTS):
            raw = await self._streaming_chat_call(
                gateway, messages,
                max_tokens=effective_max_tokens,
                thinking_budget=effective_thinking_budget,
                tools=openai_tools,
                tool_choice=forced_tool_choice,
            )

            tool_calls = raw.get("tool_calls")
            content = raw.get("content", "")

            # ── Text tool-call extraction ──
            # Qwen3 sometimes outputs the tool call as JSON text
            # (e.g. `[{"name": "write_file", ...}]`) instead of via the
            # protocol tool_calls channel.  Detect and convert.
            if not tool_calls and content and content.lstrip().startswith("["):
                extracted = self._extract_textual_tool_call(content)
                if extracted:
                    tool_calls = extracted
                    logger.info(
                        "[%s] Agent '%s' attempt %d: extracted tool_call from text",
                        slot_id, role, attempt + 1,
                    )

            if tool_calls:
                # Append assistant message with tool_calls to history
                assistant_msg = {"role": "assistant", "content": content or None}
                assistant_msg["tool_calls"] = tool_calls
                messages.append(assistant_msg)

                # Execute each tool call
                wrote_expected_file = False
                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args_str = tc["function"]["arguments"]
                    try:
                        fn_args = json.loads(fn_args_str) if isinstance(fn_args_str, str) else fn_args_str
                    except json.JSONDecodeError:
                        fn_args = {}

                    logger.info("[%s] Executing tool: %s(%s)", slot_id, fn_name, str(fn_args)[:100])
                    if fn_name != "write_file":
                        result_str = json.dumps(
                            {"ok": False, "error": f"unexpected tool: {fn_name}; expected write_file"},
                            ensure_ascii=False,
                        )
                    else:
                        result_str = await executor.execute(fn_name, fn_args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result_str,
                    })

                    try:
                        parsed_result = json.loads(result_str)
                    except json.JSONDecodeError:
                        parsed_result = {}
                    wrote_expected_file = wrote_expected_file or (
                        parsed_result.get("ok") is True
                        and parsed_result.get("path") == expected_fn
                        and expected_path.exists()
                    )

                if wrote_expected_file:
                    final_text = expected_path.read_text(encoding="utf-8")
                    break  # protocol-level success

                logger.warning(
                    "[%s] Agent '%s' attempt %d: tool_calls did not write %s, retrying",
                    slot_id, role, attempt + 1, expected_fn,
                )
                retry_prompt = (
                    f"上一轮工具调用没有成功写入 {expected_fn}。"
                    f"请只通过 tool_calls 调用 write_file(path=\"{expected_fn}\", content=\"你的完整内容\")。"
                )
                messages.append({"role": "user", "content": retry_prompt})
                continue

            logger.warning(
                "[%s] Agent '%s' attempt %d: no protocol tool_calls "
                "(content=%d chars, reasoning=%d chars, finish=%s); retrying",
                slot_id, role, attempt + 1, len(content or ""),
                len(raw.get("reasoning") or raw.get("reasoning_content") or ""),
                raw.get("finish_reason"),
            )

            logger.debug(
                "[%s] Failed content preview (first 500 chars): %s",
                slot_id, (content or "")[:500],
            )
            retry_prompt = (
                f"上一轮没有返回 OpenAI tool_calls，正文输出已被忽略。"
                f"请只通过 tool_calls 调用 write_file(path=\"{expected_fn}\", content=\"你的完整内容\")，"
                f"不要把 JSON 或函数调用写在正文里。"
            )
            messages.append({"role": "user", "content": retry_prompt})

        # 6. Update session state for multi-turn agents
        if role in MULTI_TURN_AGENTS:
            self._sessions[role] = messages

        if not final_text:
            logger.error(
                "[%s] Agent '%s' failed to write %s via protocol tool_calls",
                slot_id, role, expected_fn,
            )

        return final_text

    # ── Text tool-call extraction ─────────────────────────────────

    @staticmethod
    def _extract_textual_tool_call(content: str) -> list[dict] | None:
        """Extract tool calls from text when the model types them as JSON.

        Qwen3 sometimes outputs ``[{"name": "write_file", ...}]`` as
        plain text instead of through the protocol ``tool_calls`` channel.
        This method detects and converts those into the standard format.
        """
        text = content.strip()
        if not text.startswith("["):
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, list) or not parsed:
            return None

        tool_calls = []
        for item in parsed:
            name = item.get("name") or (item.get("function", {}) or {}).get("name")
            if not name:
                continue
            # Two possible schemas:
            # 1. {"name": "write_file", "parameters": {...}}
            # 2. {"function": {"name": "...", "arguments": "..."}, "id": "..."}
            if "function" in item and isinstance(item["function"], dict):
                fn = item["function"]
                args = fn.get("arguments", {})
            else:
                fn = None
                args = item.get("parameters", {})

            args_str = json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)
            tool_calls.append({
                "id": item.get("id", f"txt_{len(tool_calls)}"),
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": args_str,
                },
            })

        return tool_calls or None

    # ── Streaming LLM call ────────────────────────────────────────

    async def _streaming_chat_call(
        self,
        gateway,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int,
        thinking_budget: int | None = None,
        tools: list[dict[str, Any]],
        tool_choice: Any | None = None,
    ) -> dict[str, Any]:
        """Delegate streaming transport to the shared LLMGateway."""
        return await gateway.stream_chat(
            messages,
            max_tokens=max_tokens,
            enable_thinking=self.enable_thinking,
            thinking_budget=thinking_budget,
            tools=tools,
            tool_choice=tool_choice,
            sampling_overrides=DOC_SAMPLING_OVERRIDES,
        )

    # ── Pipeline compatibility facade ────────────────────────────

    async def run_pipeline(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        *,
        experience_card: str = "",
        k_definitions: str = "",
    ) -> dict[str, Any]:
        """Compatibility wrapper; orchestration lives in orchestrator.py."""
        from .orchestrator import DocPipelineOrchestrator

        orchestrator = DocPipelineOrchestrator(
            scheduler=self,
            workspace=self.workspace,
            max_tokens=self.max_tokens,
        )
        return await orchestrator.run_pipeline(
            slot_id,
            slot_data,
            experience_card=experience_card,
            k_definitions=k_definitions,
        )
