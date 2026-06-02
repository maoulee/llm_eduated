"""DocScheduler — thin orchestrator for the document-based 4-layer pipeline.

Responsibilities:
  1. Read files → inject into prompts
  2. Call agents via Edu408AgentLoop + write_file tool
  3. Parse document headers for routing decisions
  4. Execute Python scripts, redirect stdout to files
  5. Manage multi-turn sessions for iterative agents
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

from core_new.agent_runtime.registry import ToolRegistry
from core_new.agent_tools import ToolExecutor
from core_new.llm_gateway import LLMGateway
from core_new.provider_router import get_gateway

from .agents import AGENT_PROMPTS, AGENT_OUTPUT_FILES, MULTI_TURN_AGENTS, _RETRY_FEEDBACK
from .doc_parser import get_doc_status, parse_doc_header, parse_doc_section
from .write_file_tool import WriteFileTool
from core_new.markdown_parser import _extract_sections

logger = logging.getLogger(__name__)

MAX_ANALYSIS_ITERATIONS = 3
MAX_AGENT_ATTEMPTS = 2
DEFAULT_MAX_TOKENS = 20000
DEFAULT_THINKING_BUDGET = 10000
PYTHON_EXEC_TIMEOUT = 30

# Keep the doc pipeline deterministic enough to preserve tool-call shape.
DOC_SAMPLING_OVERRIDES = {
    "temperature": 0.2,
    "top_p": 0.9,
}

# Per-role thinking budget (tokens).  None = no cap.
ROLE_THINKING_BUDGET = {
    "design": 8000,
    "question": 10000,
    "analysis": 10000,
    "coding": 10000,
    "review": 8000,
    "fix": 10000,
}


class DocScheduler:
    """Thin orchestrator: read files, route agents, execute code."""

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

        # 5. Streaming tool-calling loop via provider directly
        gateway = self._get_gateway_for_role(role)
        provider = gateway._provider
        effective_max_tokens = max_tokens or self.max_tokens
        effective_thinking_budget = ROLE_THINKING_BUDGET.get(role, DEFAULT_THINKING_BUDGET)
        expected_fn = AGENT_OUTPUT_FILES.get(role, "output.md")
        expected_path = ws / expected_fn
        final_text = ""

        # Avoid accepting stale artifacts from previous attempts/runs.
        if expected_path.exists():
            expected_path.unlink()

        # "required" forces a tool call — we only register write_file, so it's
        # equivalent to a named choice but works reliably across vLLM versions.
        forced_tool_choice = "required"

        for attempt in range(MAX_AGENT_ATTEMPTS):
            raw = await self._streaming_chat_call(
                provider, messages,
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
                len(raw.get("reasoning_content") or ""),
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
        provider,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int,
        thinking_budget: int | None = None,
        tools: list[dict[str, Any]],
        tool_choice: Any | None = None,
    ) -> dict[str, Any]:
        """Streaming chat call — avoids timeout by reading chunks incrementally.

        Returns the same dict format as provider._chat_call():
        {"content": str, "reasoning_content": str, "tool_calls": list | None}
        """
        if hasattr(provider, "_prepare_messages"):
            processed = provider._prepare_messages(
                messages,
                enable_thinking=self.enable_thinking,
                json_mode=False,
            )
        else:
            processed = list(messages)  # shallow copy
        sampling = {k: v for k, v in provider.sampling_params.items() if k != "top_k"}
        sampling.update(DOC_SAMPLING_OVERRIDES)

        params: dict[str, Any] = {
            "model": provider.model_name,
            "messages": processed,
            "stream": True,
            **sampling,
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        if tools:
            params["tools"] = tools
        if tool_choice and tools:
            params["tool_choice"] = tool_choice

        # Thinking budget: caps reasoning tokens so the model has room
        # for the actual output (tool call or content).
        if thinking_budget:
            params.setdefault("extra_body", {})
            params["extra_body"]["thinking_token_budget"] = thinking_budget

        # Only pass thinking control when explicitly requested (True or False).
        # None = let the model decide naturally (no parameter sent).
        if self.enable_thinking is not None and hasattr(provider, "_extra_body_for_thinking"):
            extra_body = provider._extra_body_for_thinking(self.enable_thinking)
            if extra_body:
                params.setdefault("extra_body", {}).update(extra_body)

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls_accum: dict[int, dict[str, str]] = {}
        finish_reason: str | None = None

        logger.debug(
            "[stream] params: model=%s tool_choice=%s tools=%d max_tokens=%s",
            params.get("model"), params.get("tool_choice"),
            len(params.get("tools", [])), params.get("max_tokens"),
        )

        stream = await provider.client.chat.completions.create(**params)

        chunk_count = 0
        async for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta

            if choice.finish_reason:
                finish_reason = choice.finish_reason
            chunk_count += 1

            if delta.content:
                content_parts.append(delta.content)

            # vLLM with reasoning parser returns "reasoning" (not "reasoning_content")
            rc = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None) or ""
            if rc:
                reasoning_parts.append(rc)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_accum:
                        tool_calls_accum[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        tool_calls_accum[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_accum[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_accum[idx]["arguments"] += tc_delta.function.arguments

        # Assemble result
        content = "".join(content_parts)
        reasoning_content = "".join(reasoning_parts)

        tool_calls = None
        if tool_calls_accum:
            tool_calls = []
            for idx in sorted(tool_calls_accum):
                tc = tool_calls_accum[idx]
                tool_calls.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                })

        logger.info(
            "[stream] content=%d, reasoning=%d, tool_calls=%s, "
            "finish_reason=%s, chunks=%d",
            len(content), len(reasoning_content),
            len(tool_calls) if tool_calls else 0,
            finish_reason, chunk_count,
        )

        return {
            "content": content,
            "reasoning_content": reasoning_content,
            "tool_calls": tool_calls,
            "finish_reason": finish_reason,
        }

    # ── Code execution ───────────────────────────────────────────

    async def exec_python(self, script_path: str | Path, output_path: str | Path) -> dict[str, Any]:
        """Execute a Python script and redirect stdout to output_path.

        Returns a dict with ok, exit_code, stdout, stderr, timed_out.
        """
        script_path = Path(script_path)
        output_path = Path(output_path)

        if not script_path.exists():
            return {"ok": False, "error": f"Script not found: {script_path}"}

        try:
            proc = subprocess.run(
                ["python3", str(script_path)],
                capture_output=True,
                text=True,
                timeout=PYTHON_EXEC_TIMEOUT,
                encoding="utf-8",
                errors="replace",
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""

            # Write stdout to output file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(stdout, encoding="utf-8")

            return {
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "exit_code": -1, "stdout": "", "stderr": "Timeout", "timed_out": True}
        except Exception as exc:
            return {"ok": False, "exit_code": -1, "stdout": "", "stderr": str(exc), "timed_out": False}

    # ── Full pipeline ────────────────────────────────────────────

    async def run_pipeline(
        self,
        slot_id: str,
        slot_data: dict[str, Any],
        *,
        experience_card: str = "",
        k_definitions: str = "",
    ) -> dict[str, Any]:
        """Run the full 4-layer document pipeline for one slot.

        Returns a result dict with final output and metadata.
        """
        ws = self.workspace / slot_id
        ws.mkdir(parents=True, exist_ok=True)
        total_start = time.monotonic()

        # ── Layer 1: Design ──────────────────────────────────────
        logger.info("[%s] Layer 1: Design", slot_id)
        design_task = self._build_design_task(slot_data, k_definitions)
        await self.run_agent("design", design_task, slot_id=slot_id)
        blueprint_path = ws / "blueprint.md"

        if not blueprint_path.exists():
            return self._fail_result(slot_id, "Design agent did not write blueprint.md")

        # ── Layer 2: Question ↔ Analysis (max 3) ────────────────
        logger.info("[%s] Layer 2: Question ↔ Analysis", slot_id)
        question_path = ws / "question.md"
        feedback_path = ws / "feedback.md"
        final_iteration = 0

        for iteration in range(MAX_ANALYSIS_ITERATIONS):
            final_iteration = iteration + 1

            # Question agent
            q_task = self._build_question_task(
                slot_id, iteration, experience_card=experience_card,
            )
            q_inject = {"蓝图": str(blueprint_path)}
            if iteration > 0 and feedback_path.exists():
                # Incremental: only send feedback body
                feedback_body = parse_doc_section(str(feedback_path), "detailed_feedback")
                q_task += f"\n\n## 审核反馈（第{iteration}轮）\n{feedback_body}"

            await self.run_agent(
                "question", q_task,
                slot_id=slot_id,
                inject_files=q_inject,
                continue_session=False,  # fresh session each iteration for reliability
            )

            if not question_path.exists():
                return self._fail_result(slot_id, f"Question agent did not write question.md (iter {iteration})")

            # Analysis agent
            a_task = "请审核以下题目，检查参数一致性和难度对标。"
            await self.run_agent(
                "analysis", a_task,
                slot_id=slot_id,
                inject_files={
                    "蓝图": str(blueprint_path),
                    "题目": str(question_path),
                },
            )

            if not feedback_path.exists():
                return self._fail_result(slot_id, f"Analysis agent did not write feedback.md (iter {iteration})")

            # Check status
            status = get_doc_status(str(feedback_path))
            logger.info("[%s] Analysis iter %d: status=%s", slot_id, iteration, status)

            if status == "pass":
                break

            # needs_fix → loop continues, feedback already in question agent session
        else:
            logger.warning("[%s] Analysis max iterations reached (%d), proceeding anyway", slot_id, MAX_ANALYSIS_ITERATIONS)

        # ── Layer 3: Coding ──────────────────────────────────────
        logger.info("[%s] Layer 3: Coding", slot_id)
        solve_task = "请编写完整的 Python 求解代码。"
        await self.run_agent(
            "coding", solve_task,
            slot_id=slot_id,
            inject_files={"题目": str(question_path)},
            max_tokens=self.max_tokens,
        )
        solve_path = ws / "solve.py"
        output_path = ws / "solve_output.txt"

        if not solve_path.exists():
            return self._fail_result(slot_id, "Coding agent did not write solve.py")

        exec_result = await self.exec_python(solve_path, output_path)
        if not exec_result["ok"]:
            logger.warning("[%s] Code execution failed: %s", slot_id, exec_result.get("stderr", "")[:200])

        # ── Layer 4: Review → Fix? → Format ─────────────────────
        logger.info("[%s] Layer 4: Review", slot_id)
        review_task = "请全局审核题目和求解结果。"
        await self.run_agent(
            "review", review_task,
            slot_id=slot_id,
            inject_files={
                "蓝图": str(blueprint_path),
                "题目": str(question_path),
                "求解结果": str(output_path),
            },
        )
        review_path = ws / "review.md"

        if not review_path.exists():
            return self._fail_result(slot_id, "Review agent did not write review.md")

        fixed_path: Path | None = None
        if review_path.exists():
            review_status = get_doc_status(str(review_path))
            if review_status == "needs_fix":
                logger.info("[%s] Review: needs_fix → running fix agent", slot_id)
                fix_task = "请根据审核意见修复题目中的问题。"
                await self.run_agent(
                    "fix", fix_task,
                    slot_id=slot_id,
                    inject_files={
                        "题目": str(question_path),
                        "求解结果": str(output_path),
                        "审核意见": str(review_path),
                    },
                )
                fixed_path = ws / "fixed.md"
                if not fixed_path.exists():
                    return self._fail_result(slot_id, "Fix agent did not write fixed.md")

        # Format — system hook, no LLM needed
        logger.info("[%s] Layer 4: Format (system hook)", slot_id)
        self._format_final(
            ws,
            question_path=question_path,
            output_path=output_path,
            review_path=review_path if review_path.exists() else None,
            fixed_path=fixed_path if fixed_path and fixed_path.exists() else None,
        )

        final_path = ws / "final.md"
        total_time = time.monotonic() - total_start

        # ── Build result ─────────────────────────────────────────
        result = {
            "slot_id": slot_id,
            "pipeline_type": "doc_4layer",
            "ok": final_path.exists(),
            "total_time_s": round(total_time, 1),
            "analysis_iterations": final_iteration,
            "review_status": get_doc_status(str(review_path)) if review_path.exists() else "unknown",
            "code_exec_ok": exec_result.get("ok", False),
            "files": {
                "blueprint": str(blueprint_path),
                "question": str(question_path),
                "feedback": str(feedback_path),
                "solve": str(solve_path),
                "solve_output": str(output_path),
                "review": str(review_path) if review_path.exists() else "",
                "fixed": str(fixed_path) if fixed_path and fixed_path.exists() else "",
                "final": str(final_path) if final_path.exists() else "",
            },
        }

        if final_path.exists():
            result["final_content"] = final_path.read_text(encoding="utf-8")

        logger.info("[%s] Pipeline done: %.1fs, review=%s, iters=%d",
                     slot_id, total_time, result["review_status"], final_iteration)
        return result

    # ── System hooks ─────────────────────────────────────────────

    @staticmethod
    def _format_final(
        ws: Path,
        *,
        question_path: Path,
        output_path: Path,
        review_path: Path | None = None,
        fixed_path: Path | None = None,
    ) -> None:
        """Assemble final.md from component files — no LLM needed.

        Reads question.md sections + solve_output.txt (+ optional
        fixed.md / review.md) and assembles a clean final document.
        """
        # Source: use fixed version if available, otherwise original question
        source_path = fixed_path or question_path
        question_text = source_path.read_text(encoding="utf-8") if source_path.exists() else ""

        # Extract sections from question
        sections = _extract_sections(question_text)

        # Build question section
        stem = sections.get("题干", question_text)
        sub_questions = sections.get("子问题", "")
        options = sections.get("选项", "")
        answer = sections.get("答案", "")

        # Read solve output
        solve_output = output_path.read_text(encoding="utf-8") if output_path.exists() else "（无求解输出）"

        # Read review summary if available
        review_summary = ""
        if review_path and review_path.exists():
            review_sections = _extract_sections(review_path.read_text(encoding="utf-8"))
            review_summary = review_sections.get("summary", "")

        # Read design notes if available
        design_notes = sections.get("设计说明", "")

        # Assemble final.md
        parts = [f"## 题目\n{stem.strip()}"]

        if sub_questions:
            parts.append(f"\n\n## 子问题\n{sub_questions.strip()}")

        if options:
            parts.append(f"\n\n## 选项\n{options.strip()}")

        parts.append(f"\n\n## 解题过程\n{solve_output.strip()}")

        parts.append(f"\n\n## 答案\n{answer.strip()}")

        if design_notes:
            parts.append(f"\n\n## 设计说明\n{design_notes.strip()}")

        if review_summary:
            parts.append(f"\n\n## 审核总结\n{review_summary.strip()}")

        final_content = "\n".join(parts)
        (ws / "final.md").write_text(final_content, encoding="utf-8")

    # ── Task builders ────────────────────────────────────────────

    def _build_design_task(self, slot_data: dict, k_definitions: str) -> str:
        parts = [
            "请根据以下 slot 数据设计出题蓝图。",
            f"\n## Slot 数据\n{json.dumps(slot_data, ensure_ascii=False, indent=2)}",
        ]
        if k_definitions:
            parts.append(f"\n## K值难度定义\n{k_definitions}")
        return "\n".join(parts)

    def _build_question_task(self, slot_id: str, iteration: int, *, experience_card: str = "") -> str:
        parts = [f"请设计 {slot_id} 的完整题目。"]
        if iteration > 0:
            parts.append(f"\n这是第 {iteration + 1} 次迭代，请根据审核反馈修正题目。")
        if experience_card:
            parts.append(f"\n## 经验卡（往届题目题干参考，仅供风格参考）\n{experience_card}")
        return "\n".join(parts)

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _fail_result(slot_id: str, reason: str) -> dict[str, Any]:
        return {
            "slot_id": slot_id,
            "pipeline_type": "doc_4layer",
            "ok": False,
            "error": reason,
            "total_time_s": 0,
        }
