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
import re
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
    ROLE_REQUIRED_TOOLS,
    ROLE_SKILLS,
    ROLE_THINKING_BUDGET,
)
from .edit_file_tool import EditFileTool
from .exec_python_tool import ExecPythonTool
from .read_file_tool import ReadFileTool
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
        # WebGPT session bookkeeping.  ChatGPT conversations are remote state,
        # so track every key we open and clean it when the pipeline finishes.
        self._webgpt_session_keys: set[str] = set()
        self._webgpt_call_counts: dict[str, int] = {}

    def _get_gateway_for_role(self, role: str) -> LLMGateway:
        """Resolve the gateway for a given agent role.

        If model_routing specifies a provider for this role, create/return
        the corresponding gateway.  Otherwise fall back to self.gateway.
        """
        if not self.model_routing or role not in self.model_routing:
            return self.gateway
        provider_name = self.model_routing[role]
        if self._is_webgpt_provider(provider_name):
            return self.gateway
        if provider_name not in self._gateway_cache:
            self._gateway_cache[provider_name] = get_gateway(provider_name)
            logger.info("Resolved gateway for role '%s': %s", role, provider_name)
        return self._gateway_cache[provider_name]

    @staticmethod
    def _is_webgpt_provider(provider_name: str | None) -> bool:
        return str(provider_name or "").strip().lower() in {"webgpt", "gpt", "chatgpt"}

    def _uses_webgpt_for_role(self, role: str) -> bool:
        if not self.model_routing or role not in self.model_routing:
            return False
        return self._is_webgpt_provider(self.model_routing.get(role))

    def _uses_hybrid_for_role(self, role: str) -> bool:
        if not self.model_routing or role not in self.model_routing:
            return False
        return str(self.model_routing.get(role, "")).strip().lower() == "hybrid"

    # ── GPT prompt loader ──────────────────────────────────────────

    _GPT_AGENTS_DIR = Path(__file__).parent / "agents_gpt"
    _hybrid_spec_cache: dict[str, str] = {}

    @classmethod
    def _load_hybrid_spec(cls, role: str) -> str:
        """Load Qwen's hybrid-mode behavior spec from agents_gpt/{role}.md."""
        if role in cls._hybrid_spec_cache:
            return cls._hybrid_spec_cache[role]
        path = cls._GPT_AGENTS_DIR / f"{role}.md"
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            cls._hybrid_spec_cache[role] = text
            return text
        return ""

    # ── GPT system prompts (what GPT sees) ─────────────────────────

    _GPT_SYSTEM_PROMPTS = {
        "paper_composer": (
            "# 408考研组卷专家\n\n"
            "你是408考研组卷专家，以教师的视角规划试卷大纲。大纲是给下游出题智能体的'命题指令'。\n\n"
            "## 输出格式\n"
            "Markdown格式，包含：\n"
            "- `# 试卷大纲` 标题\n"
            "- `## 整体规划` — difficulty_target 和 composition_rationale\n"
            "- 每个题位一个 `## Qxx` 段落，包含：target_subject, target_family, primary_target_name, "
            "difficulty_level, k_target, difficulty_rationale, examination_mode\n\n"
            "## 核心约束\n"
            "- examination_mode 必须精确复制自题位的'可选考察模式'列表，不得缩写、翻译或自创\n"
            "- 综合应用题（Q43-Q45）的 examination_mode 写'综合型'\n"
            "- 不要输出选项风格、干扰策略等设计级决策\n"
            "- 确保知识点覆盖主要知识域，避免连续多题考同一知识点\n\n"
            "直接输出 Markdown 内容，不要用代码块包裹。"
        ),
        "paper_outline_composer": (
            "# 408考研组卷专家\n\n"
            "你是408考研组卷专家，以教师的视角规划试卷大纲。大纲是给下游出题智能体的'命题指令'。\n\n"
            "## 输出格式\n"
            "Markdown格式，包含：\n"
            "- `# 试卷大纲` 标题\n"
            "- `## 整体规划` — difficulty_target 和 composition_rationale\n"
            "- 每个题位一个 `## Qxx` 段落，包含：target_subject, target_family, primary_target_name, "
            "difficulty_level, k_target, difficulty_rationale, examination_mode\n\n"
            "## 核心约束\n"
            "- examination_mode 必须精确复制自题位的'可选考察模式'列表，不得缩写、翻译或自创\n"
            "- 综合应用题（Q43-Q45）的 examination_mode 写'综合型'\n"
            "- 不要输出选项风格、干扰策略等设计级决策\n"
            "- 确保知识点覆盖主要知识域，避免连续多题考同一知识点\n\n"
            "直接输出 Markdown 内容，不要用代码块包裹。"
        ),
        "question": (
            "# 408考研出题专家\n\n"
            "你是408考研出题专家。你将收到蓝图（blueprint.md，包含知识点、难度、结构要求）"
            "和经验卡（命题风格参考），请直接产出完整的考试题目。\n\n"
            "## 输出格式\n"
            "Markdown格式，按顺序包含以下章节：\n"
            "- `## status` — 内容固定为 `draft`\n"
            "- `## 题干` — 完整题干，包含所有给定条件和背景\n"
            "- `## 选项`（选择题）或 `## 子问题`（综合题）\n"
            "- `## 答案` — 正确答案及完整推导过程\n"
            "- `## 设计说明` — 知识点选取理由、参数选择理由、干扰策略、难度自评\n\n"
            "## 核心规则\n"
            "1. 所有给定条件必须被使用，不允许废弃条件\n"
            "2. 参数自洽，确保唯一解\n"
            "3. 题目完全原创，不得照搬参考文档中的历史原题\n"
            "4. 参数优先选用 2^n 相关值（如4KB、64、256MB），便于考生心算\n"
            "5. 推理路径完整无跳步\n"
            "6. 禁止在题干中出现编程语言代码\n"
            "7. 题干简洁精炼，避免冗长背景描述\n\n"
            "直接输出 Markdown 内容，不要用代码块包裹，不要在正文前后添加说明。"
        ),
        "coding": (
            "# 408考研解题专家\n\n"
            "你是408考研解题专家。你将收到一道完整的考试题目，请编写可直接运行的Python代码，"
            "从题目参数推导出所有答案。\n\n"
            "## 代码要求\n"
            "1. 只使用标准库：math, decimal, fractions, itertools, collections, struct, random\n"
            "2. 每个子问题/选项必须有对应的计算代码\n"
            "3. 每步用 print() 输出，包含清晰标签\n"
            "4. 最终答案单独一行打印：`ANSWER: ...`\n"
            "5. 严禁硬编码答案——所有值必须从给定参数计算得出\n"
            "6. 变量命名体现物理含义（如 cache_index_bits 而非 x）\n"
            "7. 选择题：逐选项验证；综合题：逐子问题求解\n\n"
            "直接输出纯Python源码，不要用Markdown代码块包裹，不要添加说明文字。"
        ),
        "review": (
            "# 408考研对抗审核专家\n\n"
            "你是408考研出题对抗审核专家。你的目标不是确认题目'没问题'，而是主动寻找每个潜在缺陷。\n\n"
            "## 两种审核场景\n\n"
            "### 场景 A：有求解代码结果\n"
            "你将收到题目和求解代码执行结果。\n"
            "审核策略：\n"
            "1. 验证答案：求解结果是否支持题目答案\n"
            "2. 攻击选项（选择题）：错误选项是否太明显、正确答案是否唯一、排除法是否秒杀\n"
            "3. 攻击题干：歧义表述、条件缺失、条件矛盾、废弃条件\n"
            "4. 大纲匹配：考点和难度是否合理\n\n"
            "### 场景 B：纯概念题（无代码验证）\n"
            "你只收到题目，没有求解代码结果。这是纯概念题，无需计算验证。\n"
            "审核策略：\n"
            "1. 概念正确性：答案是否符合教材定义\n"
            "2. 攻击选项：错误选项是否有合理干扰、正确答案是否唯一\n"
            "3. 攻击题干：表述歧义、分类标准是否清晰\n"
            "4. 大纲匹配：考点和难度是否合理\n\n"
            "## 输出格式\n"
            "Markdown格式，按顺序包含以下章节：\n"
            "- `## status` — `pass` 或 `needs_fix`\n"
            "- `## summary` — 审核总结\n"
            "- `## corrections` — pass写'无'，needs_fix写具体问题及修正方向\n"
            "- `## detailed_feedback` — 逐项审核发现：求解正确性(或概念正确性)、条件利用率、答案自洽性、选项质量、表述精确性、大纲匹配、总体评分(1-10)\n\n"
            "## 判定规则\n"
            "- 实质性问题（答案错误、条件矛盾、选项不唯一）→ needs_fix\n"
            "- 无法攻破 → pass\n"
            "- 润色建议不算问题\n\n"
            "直接输出 Markdown 内容，不要用代码块包裹。"
        ),
    }

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
        pre_copy_source: str | Path | None = None,
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
            pre_copy_source: If set, copy this file to expected_path after unlink
                (so the agent can use edit_file on a pre-populated file).

        Returns:
            The final text content from the agent.
        """
        ws = self.workspace / slot_id
        ws.mkdir(parents=True, exist_ok=True)

        # 1. Build task with skill content and inject files
        full_task = task

        # Inject domain-specific skill content into user message
        skill_content = ROLE_SKILLS.get(role, "")
        if skill_content:
            full_task += f"\n\n## 工作规范\n{skill_content}"

        # Read and append inject files
        if inject_files:
            for label, fpath in inject_files.items():
                path = Path(fpath)
                if not path.exists():
                    logger.warning("Inject file not found: %s", fpath)
                    continue
                content = path.read_text(encoding="utf-8")
                full_task += f"\n\n## {label}\n{content}"

        # 2. Build or continue message history
        system_prompt = AGENT_PROMPTS.get(role, "")
        if continue_session and role in self._sessions:
            messages = list(self._sessions[role])
            messages.append({"role": "user", "content": full_task})
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_task},
            ]

        expected_fn = AGENT_OUTPUT_FILES.get(role, "output.md")
        expected_path = ws / expected_fn

        # Avoid accepting stale artifacts from previous attempts/runs.
        if expected_path.exists():
            expected_path.unlink()

        # Pre-copy source file (e.g. question.md → fixed.md) so agent can edit_file.
        if pre_copy_source:
            import shutil
            shutil.copy2(str(pre_copy_source), str(expected_path))

        if self._uses_hybrid_for_role(role):
            final_text = await self._run_hybrid_agent(
                role=role,
                task=full_task,
                slot_id=slot_id,
                expected_fn=expected_fn,
                expected_path=expected_path,
            )
            if final_text:
                return final_text
            logger.warning(
                "[%s] Agent '%s': Hybrid mode failed, falling back to gateway",
                slot_id, role,
            )

        if self._uses_webgpt_for_role(role):
            final_text = await self._run_webgpt_direct_agent(
                role=role,
                task=full_task,
                slot_id=slot_id,
                system_prompt=system_prompt,
                expected_fn=expected_fn,
                expected_path=expected_path,
                continue_session=continue_session,
            )
            if final_text:
                return final_text
            logger.warning(
                "[%s] Agent '%s': WebGPT direct mode unavailable/failed, falling back to gateway",
                slot_id,
                role,
            )

        # 3. Build tool registry based on role's required tools
        registry = ToolRegistry()
        registry.register(WriteFileTool(workspace=ws))

        required_tools = ROLE_REQUIRED_TOOLS.get(role, ["write_file"])
        if "exec_python" in required_tools:
            registry.register(ExecPythonTool(timeout=PYTHON_EXEC_TIMEOUT))
        if "edit_file" in required_tools:
            registry.register(EditFileTool(workspace=ws))
        if "read_file" in required_tools:
            registry.register(ReadFileTool(workspace=ws))

        # 4. Convert to OpenAI tool schemas and build executor
        tool_list = [registry.get(name) for name in required_tools if registry.get(name) is not None]
        executor = ToolExecutor(tool_list)
        openai_tools = [t.to_openai_tool() for t in tool_list]

        # 5. Streaming tool-calling loop via shared gateway transport.
        gateway = self._get_gateway_for_role(role)
        effective_max_tokens = max_tokens or self.max_tokens
        effective_thinking_budget = ROLE_THINKING_BUDGET.get(role, DEFAULT_THINKING_BUDGET)

        # Remote providers (GLM) count reasoning tokens against max_tokens.
        # Generation roles need extra headroom so reasoning doesn't consume
        # the entire output budget before tool calls land.
        if self._is_remote_gateway(gateway):
            effective_max_tokens = max(effective_max_tokens, 40000)
        final_text = ""

        # Force a tool call. Single tool: name it explicitly (works everywhere).
        # Multiple tools: "required" works on vLLM but not GLM — use "auto"
        # for remote providers. The prompt + retry loop ensures write_file is called.
        if len(openai_tools) == 1:
            forced_tool_choice = {
                "type": "function",
                "function": {"name": openai_tools[0]["function"]["name"]},
            }
        elif self._is_remote_gateway(gateway):
            forced_tool_choice = "auto"
        else:
            forced_tool_choice = "required"

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
                    if fn_name in required_tools:
                        result_str = await executor.execute(fn_name, fn_args)
                    else:
                        result_str = json.dumps(
                            {"ok": False, "error": f"unexpected tool: {fn_name}; allowed: {required_tools}"},
                            ensure_ascii=False,
                        )
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
                        and fn_name in ("write_file", "edit_file")
                    )

                if wrote_expected_file:
                    final_text = expected_path.read_text(encoding="utf-8")
                    break  # protocol-level success

                logger.warning(
                    "[%s] Agent '%s' attempt %d: tool_calls did not write %s, retrying",
                    slot_id, role, attempt + 1, expected_fn,
                )
                if "edit_file" in required_tools:
                    retry_prompt = (
                        f"上一轮工具调用没有成功写入 {expected_fn}。"
                        f"请通过 write_file(path=\"{expected_fn}\", content=\"...\") 写入，"
                        f"或通过 edit_file(path=\"{expected_fn}\", old_string=\"...\", new_string=\"...\") 做局部修改。"
                    )
                else:
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

    # ── WebGPT direct-output adapter ───────────────────────────────

    async def _run_webgpt_direct_agent(
        self,
        *,
        role: str,
        task: str,
        slot_id: str,
        system_prompt: str,
        expected_fn: str,
        expected_path: Path,
        continue_session: bool,
    ) -> str:
        """Ask WebGPT to produce the target file body; write it locally.

        WebGPT cannot access this workspace or call our tools.  In this mode it
        only produces content; this scheduler remains responsible for file I/O.
        """
        from core_new.webgpt_client import get_webgpt_client

        client = get_webgpt_client()
        if client is None:
            return ""

        session_key = self._webgpt_session_key(slot_id, role, continue_session)
        self._webgpt_session_keys.add(session_key)

        adapted_system_prompt = self._build_webgpt_system_prompt(
            role=role,
            system_prompt=system_prompt,
            expected_fn=expected_fn,
        )
        content = self._build_webgpt_user_prompt(role=role, task=task, expected_fn=expected_fn)

        logger.info(
            "[%s] Agent '%s': delegating direct output to WebGPT (target=%s, task_len=%d)",
            slot_id,
            role,
            expected_fn,
            len(task),
        )
        try:
            raw = await client.delegate(
                agent_name=f"doc_{role}",
                slot_id=session_key,
                system_prompt=adapted_system_prompt,
                content=content,
            )
        except Exception as exc:
            logger.warning("[%s] Agent '%s': WebGPT failed: %s", slot_id, role, exc)
            return ""

        final_text = self._extract_direct_output(raw, role=role, expected_fn=expected_fn)
        if not final_text.strip():
            logger.warning("[%s] Agent '%s': WebGPT returned empty direct output", slot_id, role)
            return ""

        expected_path.parent.mkdir(parents=True, exist_ok=True)
        expected_path.write_text(final_text, encoding="utf-8")
        logger.info(
            "[%s] Agent '%s': WebGPT wrote %s (%d chars)",
            slot_id,
            role,
            expected_fn,
            len(final_text),
        )
        return final_text

    def _webgpt_session_key(self, slot_id: str, role: str, continue_session: bool) -> str:
        base = f"{slot_id}:doc:{role}"
        if continue_session:
            return base
        call_no = self._webgpt_call_counts.get(base, 0) + 1
        self._webgpt_call_counts[base] = call_no
        return f"{base}:{call_no}"

    @staticmethod
    def _build_webgpt_system_prompt(*, role: str, system_prompt: str, expected_fn: str) -> str:
        adapter = (
            "\n\n## WebGPT直接产出模式\n"
            "本次由远端GPT负责生成目标文件内容，本地调度器已经把所需文件内容注入到用户消息中，"
            "并会在收到你的回复后负责写文件、读文件和执行代码。\n"
            "因此即使上文角色合约提到 write_file、edit_file、read_file 或 exec_python，"
            "你也不能输出工具调用、函数调用、JSON tool_calls 或让用户代为保存。\n"
            f"请直接输出 `{expected_fn}` 的完整文件内容。你收到的注入材料就是可用事实来源，"
            "不要声称无法访问本地文件。"
        )
        if role == "coding":
            adapter += (
                "\n`solve.py` 必须是可直接运行的纯 Python 源码；不要使用 Markdown 代码块；"
                "只依赖 Python 标准库；必须打印清晰求解过程，最终单独打印 `ANSWER: ...`。"
            )
        else:
            adapter += "\nMarkdown 文件直接从第一个章节标题开始；不要包裹在代码块中。"
        role_contract = DocScheduler._webgpt_role_output_contract(role, expected_fn)
        if role_contract:
            adapter += "\n\n" + role_contract
        return (system_prompt or "") + adapter

    @staticmethod
    def _build_webgpt_user_prompt(*, role: str, task: str, expected_fn: str) -> str:
        suffix = (
            f"\n\n## 输出约束\n"
            f"只输出 `{expected_fn}` 的完整内容。不要解释你将如何写文件，"
            "不要输出工具调用 JSON，不要在正文前后添加额外说明。\n"
            "如果输出 Markdown，第一行必须是目标文件的第一个 `##` 章节标题；"
            "如果输出 Python，第一行必须是 Python 源码或注释。"
        )
        if role in {"question", "coding", "review", "fix"}:
            suffix += "\n如需计算或校验，请在你自己的推理过程中完成，并把必要的校验证据写入目标内容。"
        return task + suffix

    @staticmethod
    def _webgpt_role_output_contract(role: str, expected_fn: str) -> str:
        """Extra constraints for direct-output WebGPT roles.

        These constraints translate the tool/file contract into plain output,
        because WebGPT cannot call local tools.
        """
        if role == "design":
            return (
                "## 目标文件协议：blueprint.md\n"
                "必须包含且按顺序输出章节：`## status`、`## 知识点`、`## 难度`、"
                "`## 出题要求`、`## 子问题规划`、`## 参数约束`。\n"
                "`## status` 的内容固定为 `ready`。蓝图只定义结构、约束和参数范围，"
                "不要提前指定具体数值或完整题干。"
            )
        if role == "question":
            return (
                "## 目标文件协议：question.md\n"
                "必须包含且按顺序输出章节：`## status`、`## 题干`、"
                "`## 子问题` 或 `## 选项`、`## 答案`、`## 设计说明`。\n"
                "`## status` 的内容固定为 `draft`。题目必须严格遵循蓝图，"
                "所有给定条件都要被使用；参数校验证据写入设计说明，避免暴露冗长思考。"
            )
        if role == "analysis":
            return (
                "## 目标文件协议：feedback.md\n"
                "必须包含且按顺序输出章节：`## status`、`## summary`、`## detailed_feedback`。\n"
                "`## status` 只能是 `pass`、`pass_with_warnings`、`needs_fix`。"
                "只有发现阻塞问题才使用 `needs_fix`。"
            )
        if role == "coding":
            return (
                "## 目标文件协议：solve.py\n"
                "只输出 Python 源码，不要 Markdown。代码必须自包含，不能读取本地文件或联网；"
                "从题干公开条件推导答案，覆盖每个子问题或每个选项。"
            )
        if role == "review":
            return (
                "## 目标文件协议：review.md\n"
                "必须包含且按顺序输出章节：`## status`、`## summary`、"
                "`## corrections`、`## detailed_feedback`。\n"
                "`## status` 使用 `pass` 或 `needs_fix`；发现可由 Fix 阶段最小修复的阻塞问题时，"
                "必须使用 `needs_fix` 以触发后续修复。不要在 review.md 中直接输出 fixed.md。"
            )
        if role == "fix":
            return (
                "## 目标文件协议：fixed.md\n"
                "必须包含且按顺序输出章节：`## status`、`## 题干`、`## 子问题`、"
                "`## 答案`、`## 修改说明`。\n"
                "`## status` 只能是 `fixed` 或 `unfixable`。只做审核意见要求的最小修复，"
                "不要重写整题或改变蓝图知识点。"
            )
        return f"## 目标文件协议：{expected_fn}\n直接输出目标文件完整内容。"

    @classmethod
    def _extract_direct_output(cls, raw: str, *, role: str, expected_fn: str) -> str:
        text = (raw or "").strip()
        extracted = cls._extract_tool_text_content(text)
        if extracted:
            text = extracted.strip()
        if role == "coding" or expected_fn.endswith(".py"):
            return cls._extract_code_block(text).rstrip() + "\n"
        return cls._strip_outer_fence(text).rstrip() + "\n"

    @staticmethod
    def _extract_tool_text_content(text: str) -> str:
        """Recover content if GPT ignored instructions and emitted tool-call JSON."""
        if not text or text[0] not in "[{":
            return ""
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return ""

        candidates = parsed if isinstance(parsed, list) else [parsed]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            args = item.get("parameters") or item.get("arguments") or {}
            fn = item.get("function")
            if isinstance(fn, dict):
                args = fn.get("arguments", args)
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    continue
            if isinstance(args, dict):
                content = args.get("content") or args.get("text") or args.get("code")
                if isinstance(content, str) and content.strip():
                    return content
            for key in ("content", "text", "code"):
                content = item.get(key)
                if isinstance(content, str) and content.strip():
                    return content
        return ""

    @staticmethod
    def _strip_outer_fence(text: str) -> str:
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if len(lines) >= 2 and lines[-1].strip().startswith("```"):
            return "\n".join(lines[1:-1]).strip()
        return stripped

    @classmethod
    def _extract_code_block(cls, text: str) -> str:
        stripped = text.strip()
        fenced = re.search(r"```(?:python|py)?\s*\n(.*?)```", stripped, re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1).strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        code_lines: list[str] = []
        in_block = False
        for line in lines:
            if line.strip().startswith("```"):
                if in_block:
                    break
                in_block = True
                continue
            if in_block:
                code_lines.append(line)
        return "\n".join(code_lines).strip() if code_lines else cls._strip_outer_fence(stripped)

    # ── Hybrid agent: GPT thinks, Qwen writes ──────────────────────

    async def _run_hybrid_agent(
        self,
        *,
        role: str,
        task: str,
        slot_id: str,
        expected_fn: str,
        expected_path: Path,
    ) -> str:
        """Hybrid mode: GPT generates content, Qwen validates format and writes.

        Step 1: Send task to GPT via WebGPT → get raw content.
        Step 2: Pass GPT content + hybrid behavior spec to Qwen with tools.
        Step 3: Qwen validates, adjusts, and writes to expected file.
        """
        from core_new.webgpt_client import get_webgpt_client

        client = get_webgpt_client()
        if client is None:
            return ""

        # ── Step 1: GPT generates content ──
        gpt_system = self._GPT_SYSTEM_PROMPTS.get(role, "")
        if not gpt_system:
            logger.warning("[%s] No GPT system prompt for role '%s'", slot_id, role)
            return ""

        session_key = f"{slot_id}:hybrid:{role}"
        self._webgpt_session_keys.add(session_key)

        logger.info(
            "[%s] Hybrid '%s': sending to GPT (task_len=%d)",
            slot_id, role, len(task),
        )
        try:
            gpt_raw = await client.delegate(
                agent_name=f"hybrid_{role}",
                slot_id=session_key,
                system_prompt=gpt_system,
                content=task,
            )
        except Exception as exc:
            logger.warning("[%s] Hybrid '%s': GPT call failed: %s", slot_id, role, exc)
            return ""

        gpt_content = self._extract_direct_output(gpt_raw, role=role, expected_fn=expected_fn)
        if not gpt_content.strip():
            logger.warning("[%s] Hybrid '%s': GPT returned empty content", slot_id, role)
            return ""

        logger.info(
            "[%s] Hybrid '%s': GPT returned %d chars, delegating to Qwen for formatting",
            slot_id, role, len(gpt_content),
        )

        # ── Step 2: Qwen validates and writes ──
        hybrid_spec = self._load_hybrid_spec(role)
        qwen_system = hybrid_spec if hybrid_spec else AGENT_PROMPTS.get(role, "")

        # Include a truncated version of the original task for terminology alignment
        task_ref = task[:2000] if len(task) > 2000 else task

        qwen_user = (
            f"## GPT 产出的原始内容\n\n{gpt_content}\n\n"
            f"---\n\n"
            f"## 原始任务参考（用于名词对齐）\n\n{task_ref}\n\n"
            f"---\n\n"
            f"请校验以上内容的格式，对照原始任务参考中的标准术语修正名词后，"
            f"通过 write_file 写入 `{expected_fn}`。"
        )

        # Build tool registry for Qwen
        ws = expected_path.parent
        registry = ToolRegistry()
        registry.register(WriteFileTool(workspace=ws))
        required_tools = ROLE_REQUIRED_TOOLS.get(role, ["write_file"])
        if "exec_python" in required_tools:
            registry.register(ExecPythonTool(timeout=PYTHON_EXEC_TIMEOUT))

        tool_list = [registry.get(name) for name in required_tools if registry.get(name) is not None]
        executor = ToolExecutor(tool_list)
        openai_tools = [t.to_openai_tool() for t in tool_list]

        # Force write_file
        forced_tool_choice = (
            {"type": "function", "function": {"name": openai_tools[0]["function"]["name"]}}
            if len(openai_tools) == 1
            else "auto"
        )

        messages = [
            {"role": "system", "content": qwen_system},
            {"role": "user", "content": qwen_user},
        ]

        final_text = ""
        for attempt in range(2):  # max 2 attempts for Qwen formatting
            raw = await self._streaming_chat_call(
                self.gateway,
                messages,
                max_tokens=self.max_tokens,
                thinking_budget=ROLE_THINKING_BUDGET.get(role, DEFAULT_THINKING_BUDGET),
                tools=openai_tools,
                tool_choice=forced_tool_choice,
            )

            tool_calls = raw.get("tool_calls")
            content = raw.get("content", "")

            # Handle text tool calls (Qwen sometimes puts tool calls in text)
            if not tool_calls and content and content.lstrip().startswith("["):
                extracted = self._extract_textual_tool_call(content)
                if extracted:
                    tool_calls = extracted

            if tool_calls:
                assistant_msg = {"role": "assistant", "content": content or None}
                assistant_msg["tool_calls"] = tool_calls
                messages.append(assistant_msg)

                wrote_file = False
                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args_str = tc["function"]["arguments"]
                    try:
                        fn_args = json.loads(fn_args_str) if isinstance(fn_args_str, str) else fn_args_str
                    except json.JSONDecodeError:
                        fn_args = {}

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
                    wrote_file = wrote_file or (
                        parsed_result.get("ok") is True
                        and expected_path.exists()
                    )

                if wrote_file:
                    final_text = expected_path.read_text(encoding="utf-8")
                    break

                messages.append({
                    "role": "user",
                    "content": f"未成功写入 {expected_fn}，请通过 write_file 写入。",
                })
            else:
                messages.append({
                    "role": "user",
                    "content": f"请通过 write_file 工具写入 {expected_fn}。",
                })

        if final_text:
            logger.info(
                "[%s] Hybrid '%s': Qwen wrote %s (%d chars)",
                slot_id, role, expected_fn, len(final_text),
            )
        else:
            # Fallback: if Qwen failed to write, save GPT content directly
            logger.warning(
                "[%s] Hybrid '%s': Qwen failed to write, saving GPT content directly",
                slot_id, role,
            )
            expected_path.parent.mkdir(parents=True, exist_ok=True)
            expected_path.write_text(gpt_content, encoding="utf-8")
            final_text = gpt_content

        return final_text

    async def cleanup_webgpt(self, slot_id: str = "") -> None:
        """Delete remote WebGPT conversations opened by this scheduler."""
        if not self._webgpt_session_keys:
            return
        from core_new.webgpt_client import get_webgpt_client

        client = get_webgpt_client()
        if client is None:
            self._webgpt_session_keys.clear()
            return

        if slot_id:
            keys = [k for k in self._webgpt_session_keys if k.startswith(f"{slot_id}:")]
        else:
            keys = list(self._webgpt_session_keys)

        for key in keys:
            try:
                await client.cleanup(slot_id=key)
            except Exception as exc:
                logger.warning("[%s] WebGPT cleanup error: %s", key, exc)
            finally:
                self._webgpt_session_keys.discard(key)

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

    # ── Provider detection ─────────────────────────────────────────

    @staticmethod
    def _is_remote_gateway(gateway) -> bool:
        """Return True if gateway connects to a remote provider (not local vLLM)."""
        provider = getattr(gateway, "_provider", None)
        provider_type = getattr(provider, "provider_type", "")
        if provider_type == "local":
            return False
        base_url = str(getattr(provider, "api_base_url", "")).lower()
        if "localhost" in base_url or "127.0.0.1" in base_url:
            return False
        return True

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
