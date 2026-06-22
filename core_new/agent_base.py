"""Base classes for multi-agent workflows."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from .agent_roles import AuditMode, ExecutionPolicy, RoleType, resolve_execution_policy
from .blackboard import AgentRecord, Blackboard
from .llm_gateway import LLMGateway, LLMResult

logger = logging.getLogger(__name__)

_UNSET = object()


@dataclass
class AgentConfig:
    name: str
    phase: str
    system_prompt: str = ""
    output_format: str = "markdown"
    output_key: Optional[str] = None
    max_tokens: int = 8192
    enable_thinking: bool = True
    max_retries: int = _UNSET  # type: ignore[assignment]
    timeout_s: float = 300.0
    required_fields: list[str] = field(default_factory=list)
    allow_empty_parse: bool = False
    repair_on_parse_failure: bool = True
    repair_max_retries: int = _UNSET  # type: ignore[assignment]
    expected_output_format: str = ""
    role_type: RoleType | str = RoleType.GENERATOR
    audit_mode: AuditMode | str | None = None
    execution_policy: ExecutionPolicy | None = None
    # Pull-based context sources (legacy, overridden by step_name)
    context_sources: dict[str, str] = field(default_factory=dict)
    # Data-flow step name (links to core_new.data_flow.STEP_INPUTS)
    step_name: Optional[str] = None
    # Tool-calling support
    tools: list = field(default_factory=list)      # List[ToolDef]
    max_tool_rounds: int = 10
    max_tool_calls: int = 0  # 0 = unlimited (governed by max_tool_rounds)


class BaseAgent(ABC):
    """Base class for LLM-backed agents.

    Memory is a message-list: each entry is {role, content, round?}.
    Agents auto-save their own I/O in execute(); the pipeline appends
    review/feedback context via receive_context().
    """

    def __init__(self, config: AgentConfig, llm_backend):
        self.config = config
        self.llm = _ensure_gateway(llm_backend)
        self.execution_policy = resolve_execution_policy(
            config.role_type,
            config.execution_policy,
        )
        if config.max_retries is _UNSET:
            config.max_retries = max(0, self.execution_policy.transport_retry.max_attempts - 1)
        if config.repair_max_retries is _UNSET:
            config.repair_max_retries = self.execution_policy.format_repair.max_attempts
        self._memory: list[dict[str, Any]] = []

    def receive_context(self, context: dict[str, Any]) -> None:
        """Receive a context message from the pipeline or another agent."""
        self._memory.append(context)

    def set_memory(self, history: list[dict[str, Any]]) -> None:
        """Replace the full memory (e.g. when reusing an agent across rounds)."""
        self._memory = list(history)

    def clear_memory(self) -> None:
        """Clear all accumulated memory."""
        self._memory = []

    def get_memory_text(self, max_rounds: int = 3) -> str:
        """Render memory as conversation-style text for prompt inclusion.

        Memory entries are message-list style:
          {role: "user", content: "..."}       — input to the agent
          {role: "assistant", content: "..."}   — agent's output
          {role: "review", content: "..."}      — review/feedback from pipeline

        No truncation — thinking is already stripped, remaining text is kept intact.
        Only the most recent max_rounds rounds are included (by round number).
        """
        if not self._memory:
            return ""
        # Find which rounds to include (messages with round=None are always included)
        rounds_seen: set = set()
        for msg in reversed(self._memory):
            rnd = msg.get("round")
            if rnd is not None:
                rounds_seen.add(rnd)
            if len(rounds_seen) >= max_rounds:
                break
        # Filter to recent rounds + round-less messages
        if rounds_seen:
            recent = [m for m in self._memory
                      if m.get("round") is None or m.get("round") in rounds_seen]
        else:
            recent = self._memory[-(max_rounds * 3):]

        parts = []
        for msg in recent:
            role = msg.get("role", "system")
            content = msg.get("content", "")
            rnd = msg.get("round")
            if not content:
                continue
            prefix = f"[第{rnd}轮] " if rnd is not None else ""
            if role == "user":
                parts.append(f"{prefix}## 输入\n{content}")
            elif role == "assistant":
                parts.append(f"{prefix}## 生成结果\n{content}")
            elif role == "review":
                parts.append(f"{prefix}## 审查反馈\n{content}")
            else:
                parts.append(f"{prefix}## {role}\n{content}")
        return "\n\n".join(parts)

    def get_audit_checklist(self) -> str:
        """Return audit checklist text if this agent has an audit_mode configured."""
        if not self.config.audit_mode:
            return ""
        from core_new.audit_profiles import build_audit_checklist_prompt
        return build_audit_checklist_prompt(self.config.audit_mode)

    def _prepare_context_store(self, blackboard: Blackboard) -> dict[str, Any]:
        """Build context store respecting data-flow contracts.

        If step_name is set, uses data_flow to determine what the agent
        may pull (optional) and must not see (forbidden).
        Otherwise falls back to legacy context_sources.

        Preserves pipeline-injected fields (prefixed with __) from existing
        context store (e.g., __blueprint__, __experience__, __agent_name__).
        """
        from .data_keys import canonical

        if self.config.step_name:
            store = self._prepare_context_store_from_flow(blackboard)
        else:
            # Legacy path (backward compat)
            store: dict[str, Any] = {"__catalog__": {}}
            for key, desc in self.config.context_sources.items():
                value = blackboard.get(key)
                store[key] = value
                store["__catalog__"][key] = (desc, value is not None)

        # Merge pipeline-injected metadata (preserved across execute())
        from .agent_tools import _context_store as _existing
        if _existing:
            for k, v in _existing.items():
                if k.startswith("__") and k not in store:
                    store[k] = v
        return store

    def _prepare_context_store_from_flow(self, blackboard: Blackboard) -> dict[str, Any]:
        """Build context store from data-flow contracts (step_name based)."""
        from .data_flow import build_context_catalog

        # Collect ALL available data from blackboard
        all_data: dict[str, Any] = {}
        for key in blackboard._state:
            all_data[key] = blackboard.get(key)

        catalog = build_context_catalog(
            self.config.step_name,
            all_data,
            is_revision=self._is_revision_round(),
        )

        store: dict[str, Any] = {"__catalog__": {}}
        for canon_key, desc in catalog.items():
            value = blackboard.get(canon_key)
            store[canon_key] = value
            store["__catalog__"][canon_key] = (desc, value is not None)
        return store

    def _is_revision_round(self) -> bool:
        """Heuristic: if memory contains review feedback, this is a revision."""
        for msg in self._memory:
            if msg.get("role") == "review":
                return True
        return False

    def _context_catalog_text(self) -> str:
        """Generate context catalog description for the prompt."""
        if self.config.step_name:
            from .data_flow import build_context_catalog, get_step_inputs
            inputs = get_step_inputs(
                self.config.step_name,
                is_revision=self._is_revision_round(),
            )
            if not inputs.optional:
                return ""
            from .data_keys import BLUEPRINT, DESIGN, OPTIONS, SOLVER_RESULT, SOLUTION, REVIEW, EXPERIENCE, FIX_INSTRUCTION
            _DESC = {
                "blueprint": "题位蓝图（出题要求、知识点、难度）",
                "design": "题目设计（题干、子问题、给定条件）",
                "options": "选项内容（option_A~D，仅选择题）",
                "solver_result": "求解器输出（computed_results, code）",
                "solution": "格式化答案（explanation, answer）",
                "review": "审核结果（status, quality, issues）",
                "experience": "经验卡（参考真题、知识点雷达）",
                "fix_instruction": "修复指令",
            }
            lines = ["你可以通过工具获取以下上下文信息（先调用 list_context 查看目录，再调用 read_context(key) 获取详细内容）："]
            for key in sorted(inputs.optional):
                desc = _DESC.get(key, key)
                lines.append(f"  - {key}: {desc}")
            return "\n".join(lines)

        # Legacy path
        if not self.config.context_sources:
            return ""
        lines = ["你可以通过工具获取以下上下文信息（先调用 list_context 查看目录，再调用 read_context(key) 获取详细内容）："]
        for key, desc in self.config.context_sources.items():
            lines.append(f"  - {key}: {desc}")
        return "\n".join(lines)

    @abstractmethod
    def build_input(self, blackboard: Blackboard) -> str:
        """Build the user prompt from blackboard state."""

    @abstractmethod
    def parse_output(self, raw: Any) -> Any:
        """Parse model output into structured data."""

    def validate_parsed(self, parsed: Any) -> tuple[bool, str]:
        """Validate parsed output before it is written as a successful record."""
        if parsed is None:
            return False, "parsed output is None"

        if isinstance(parsed, dict):
            if not parsed and not self.config.allow_empty_parse:
                return False, "parsed output is an empty dict"
            for field_name in self.config.required_fields:
                found, value = _get_required_value(parsed, field_name)
                if not found or _is_empty_value(value):
                    return False, f"missing required field `{field_name}`"
            return True, ""

        if isinstance(parsed, list):
            if not parsed and not self.config.allow_empty_parse:
                return False, "parsed output is an empty list"
            return True, ""

        if _is_empty_value(parsed) and not self.config.allow_empty_parse:
            return False, "parsed output is empty"
        return True, ""

    async def execute(self, blackboard: Blackboard) -> AgentRecord:
        input_snapshot = blackboard.get_relevant_state(self.config.name)
        start = time.monotonic()
        last_error = ""
        repair_attempts = 0

        try:
            for attempt in range(self.config.max_retries + 1):
                try:
                    # Prepare context store for pull-based tools
                    if self.config.context_sources or self.config.step_name:
                        from .agent_tools import set_context_store
                        set_context_store(self._prepare_context_store(blackboard))
                    prompt = self.build_input(blackboard)
                    memory_text = self.get_memory_text()
                    if memory_text:
                        prompt += (
                            "\n\n## 历史尝试记录（请参考，避免重复相同错误）\n"
                            + memory_text
                        )
                    result = await asyncio.wait_for(
                        self._call_llm(prompt),
                        timeout=self.config.timeout_s,
                    )
                    if not result.ok:
                        raise RuntimeError(f"{result.error_code}: {result.error_message}")
                    raw_text, parsed, repair_attempts = await self._parse_validate_repair(
                        prompt=prompt,
                        result=result,
                    )
                    if not raw_text and parsed is not None:
                        raw_text = json.dumps(parsed, ensure_ascii=False, indent=2, default=str)
                    # Auto-save this exchange to memory
                    self._memory.append({
                        "role": "user",
                        "content": prompt,
                    })
                    self._memory.append({
                        "role": "assistant",
                        "content": raw_text,
                    })
                    latency_s = time.monotonic() - start
                    record = await blackboard.write(
                        self.config.name,
                        raw_text,
                        self.config.phase,
                        output_key=self.config.output_key,
                        parsed=parsed,
                        input_snapshot=input_snapshot,
                        tokens_used=result.tokens_used,
                        latency_s=latency_s,
                    )
                    self._attach_metadata(record, repair_attempts)
                    return record
                except Exception as exc:
                    last_error = str(exc)
                    if attempt >= self.config.max_retries:
                        latency_s = time.monotonic() - start
                        record = await blackboard.mark_failed(
                            self.config.name,
                            last_error,
                            phase=self.config.phase,
                            input_snapshot=input_snapshot,
                            latency_s=latency_s,
                        )
                        self._attach_metadata(record, repair_attempts)
                        if self.execution_policy.fallback.enabled:
                            record.metadata["fallback"] = {
                                "enabled": True,
                                "target": self.execution_policy.fallback.target,
                                "original_error": last_error,
                            }
                            logger.warning(
                                "[%s] Agent failed, fallback target: %s",
                                self.config.name,
                                self.execution_policy.fallback.target,
                            )
                        return record
                    await asyncio.sleep(min(2 ** attempt, 5))
        finally:
            # Clean up context store to prevent leakage between agents
            if self.config.context_sources:
                from .agent_tools import set_context_store
                set_context_store({})

    def _attach_metadata(self, record: AgentRecord, repair_attempts: int) -> None:
        record.metadata = {
            "role_type": self.execution_policy.role_type.value,
            "execution_policy": self.execution_policy.to_dict(),
            "repair_attempts": repair_attempts,
            "fallback_enabled": self.execution_policy.fallback.enabled,
            "fallback_target": self.execution_policy.fallback.target if self.execution_policy.fallback.enabled else "",
        }

    async def _parse_validate_repair(
        self,
        *,
        prompt: str,
        result: LLMResult,
    ) -> tuple[str, Any, int]:
        raw_text = result.content or ""
        raw_for_parse = result.parsed_json if self.config.output_format == "json" else raw_text
        parsed, validation_error = self._parse_and_validate(raw_for_parse)
        if validation_error is None:
            return raw_text, parsed, 0

        if not self.config.repair_on_parse_failure or self.config.repair_max_retries <= 0:
            raise ValueError(validation_error)

        last_raw = raw_text
        last_error = validation_error
        repair_attempts = 0
        for _ in range(self.config.repair_max_retries):
            repair_attempts += 1
            repair_prompt = self._build_repair_prompt(
                original_prompt=prompt,
                bad_output=last_raw,
                validation_error=last_error,
            )
            repair_result = await asyncio.wait_for(
                self._call_llm(repair_prompt),
                timeout=self.config.timeout_s,
            )
            if not repair_result.ok:
                raise RuntimeError(f"{repair_result.error_code}: {repair_result.error_message}")

            repaired_raw = repair_result.content or ""
            repaired_for_parse = (
                repair_result.parsed_json
                if self.config.output_format == "json"
                else repaired_raw
            )
            repaired, repaired_error = self._parse_and_validate(repaired_for_parse)
            if repaired_error is None:
                return repaired_raw, repaired, repair_attempts

            last_raw = repaired_raw
            last_error = repaired_error

        raise ValueError(last_error)

    def _parse_and_validate(self, raw_for_parse: Any) -> tuple[Any, str | None]:
        try:
            parsed = self.parse_output(raw_for_parse)
        except Exception as exc:
            return None, f"parse_output failed: {exc}"

        ok, detail = self.validate_parsed(parsed)
        if not ok:
            return parsed, f"invalid parsed output: {detail}"
        return parsed, None

    def _build_repair_prompt(
        self,
        *,
        original_prompt: str,
        bad_output: str,
        validation_error: str,
    ) -> str:
        required = ", ".join(self.config.required_fields) or "(no explicit required fields)"
        expected = self.config.expected_output_format.strip() or (
            "Return the same markdown format requested in the original task. "
            "Make sure every required field is present and parseable."
        )
        return f"""The previous output could not be parsed by the system.

Validation error:
{validation_error}

Required fields:
{required}

Expected output format:
{expected}

Original task:
{_truncate(original_prompt, 6000)}

Previous invalid output:
{_truncate(bad_output, 6000)}

Rewrite the previous output so it strictly matches the expected format.
Do not add explanations, apologies, code fences unless the expected format asks for them, or meta commentary.
Return only the corrected final content."""

    async def _call_llm(self, prompt: str) -> LLMResult:
        messages = []
        if self.config.system_prompt:
            messages.append({"role": "system", "content": self.config.system_prompt})
        messages.append({"role": "user", "content": prompt})

        # If tools are registered, use tool-calling loop
        if self.config.tools:
            return await self._call_llm_with_tools(messages)

        max_tokens = self.config.max_tokens

        fmt = self.config.output_format.lower()
        if fmt == "json":
            return await self.llm.generate_json(
                messages,
                max_tokens=max_tokens,
                enable_thinking=self.config.enable_thinking,
            )
        if fmt in {"text", "plain"}:
            return await self.llm.generate_text(
                messages,
                max_tokens=max_tokens,
                enable_thinking=self.config.enable_thinking,
            )
        return await self.llm.generate_reasoned(
            messages,
            max_tokens=max_tokens,
            enable_thinking=self.config.enable_thinking,
        )

    async def _call_llm_with_tools(self, messages: list) -> LLMResult:
        """Call LLM with tool-calling support. Runs a multi-turn loop."""
        from .agent_tools import ToolExecutor

        tools_list = self.config.tools
        executor = ToolExecutor(tools_list)
        openai_tools = executor.get_openai_tools()

        return await self.llm.generate_with_tools(
            messages,
            tools=openai_tools,
            tool_executor=executor,
            max_tokens=self.config.max_tokens,
            enable_thinking=self.config.enable_thinking,
            max_rounds=self.config.max_tool_rounds,
            max_tool_calls=self.config.max_tool_calls,
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


def _get_required_value(data: dict[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict, tuple, set)) and len(value) == 0:
        return True
    return False


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def _ensure_gateway(obj) -> LLMGateway:
    if isinstance(obj, LLMGateway):
        return obj
    return LLMGateway.from_provider(obj, "wrapped")
