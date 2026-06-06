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


def _extract_terminology_ref(task: str) -> str:
    """Extract condensed terminology reference from a full task.

    The full task may contain the entire assembled doc (~13K+ chars) injected
    as "## 蓝图" which GPT already processed. For the Qwen formatting step,
    we only need key terms for alignment — not the full reference.

    Keeps:
      - The original question instruction (first paragraph)
      - Key field values (primary_target_name, examination_mode, etc.)
      - Working spec (## 工作规范)

    Strips:
      - The full assembled doc (## 蓝图 section, often 10K+ chars)
      - K-radar definitions, past questions, K anchors, etc.
    """
    lines = task.split("\n")
    result: list[str] = []
    in_blueprint = False

    for line in lines:
        # Detect blueprint injection boundary
        if line.startswith("## 蓝图") or line.startswith("## 藍圖"):
            in_blueprint = True
            continue
        # Blueprint section runs to the end of the task (it's always the
        # last injected section), so once in_blueprint, skip everything.
        if in_blueprint:
            continue

        result.append(line)

    condensed = "\n".join(result)

    # Safety: if still too large, truncate to first 2000 chars
    if len(condensed) > 2000:
        condensed = condensed[:2000] + "\n\n[... 省略完整蓝图参考，GPT 已处理]"

    return condensed


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
        Checks role-specific key first, then "_default".
        """
        if not self.model_routing:
            return self.gateway
        provider_name = self.model_routing.get(role) or self.model_routing.get("_default")
        if not provider_name:
            return self.gateway
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
        if not self.model_routing:
            return False
        provider_name = self.model_routing.get(role) or self.model_routing.get("_default")
        return self._is_webgpt_provider(provider_name)

    def _uses_hybrid_for_role(self, role: str) -> bool:
        if not self.model_routing:
            return False
        provider_name = self.model_routing.get(role) or self.model_routing.get("_default")
        return str(provider_name or "").strip().lower() == "hybrid"

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
            "你是408考研组卷专家，以教师的视角规划试卷大纲。大纲同时面向教师阅读和下游出题智能体。\n\n"
            "## 输出格式（混合大纲）\n"
            "Markdown格式，包含以下部分：\n\n"
            "### 全局部分\n"
            "- `# 试卷大纲` 标题\n"
            "- `## 整体规划` — difficulty_target 和 composition_rationale\n"
            "- `## 1. 教师阅读版总览` — 自然语言描述整卷定位、知识点覆盖策略；附题位总览表格\n\n"
            "### 每个题位（`## Qxx（题型）`）包含三个子节：\n"
            "1. `### 教师可读说明` — 自然语言描述考查知识点、难度定位、能力要求和风险点\n"
            "2. `### 教师批注区` — 固定格式 `> [教师] ` 后留空\n"
            "3. `### 机器契约` — ```yaml 代码块包含：target_subject, target_family, "
            "primary_target_name, difficulty_level, k_target, difficulty_rationale, examination_mode\n\n"
            "## 核心约束\n"
            "- examination_mode 必须精确复制自题位的'可选考察模式'列表，不得缩写、翻译或自创\n"
            "- 综合应用题（Q43-Q45）的 examination_mode 写'综合型'\n"
            "- 不要输出选项风格、干扰策略等设计级决策\n"
            "- 确保知识点覆盖主要知识域，避免连续多题考同一知识点\n\n"
            "直接输出 Markdown 内容，不要用代码块包裹。"
        ),
        "paper_outline_composer": (
            "# 408考研组卷专家\n\n"
            "你是408考研组卷专家，以教师的视角规划试卷大纲。大纲同时面向教师阅读和下游出题智能体。\n\n"
            "## 输出格式（混合大纲）\n"
            "Markdown格式，包含以下部分：\n\n"
            "### 全局部分\n"
            "- `# 试卷大纲` 标题\n"
            "- `## 整体规划` — difficulty_target 和 composition_rationale\n"
            "- `## 1. 教师阅读版总览` — 自然语言描述整卷定位、知识点覆盖策略；附题位总览表格\n\n"
            "### 每个题位（`## Qxx（题型）`）包含三个子节：\n"
            "1. `### 教师可读说明` — 自然语言描述考查知识点、难度定位、能力要求和风险点\n"
            "2. `### 教师批注区` — 固定格式 `> [教师] ` 后留空\n"
            "3. `### 机器契约` — ```yaml 代码块包含：target_subject, target_family, "
            "primary_target_name, difficulty_level, k_target, difficulty_rationale, examination_mode\n\n"
            "## 核心约束\n"
            "- examination_mode 必须精确复制自题位的'可选考察模式'列表，不得缩写、翻译或自创\n"
            "- 综合应用题（Q43-Q45）的 examination_mode 写'综合型'\n"
            "- 不要输出选项风格、干扰策略等设计级决策\n"
            "- 确保知识点覆盖主要知识域，避免连续多题考同一知识点\n\n"
            "直接输出 Markdown 内容，不要用代码块包裹。"
        ),
        "question": (
            "# 408考研出题专家\n\n"
            "你是408考研出题专家。你将收到出题契约（assembled.md，包含知识点、难度、结构要求），"
            "请直接产出完整的考试题目。\n\n"
            "## 输出格式\n"
            "Markdown格式，按顺序包含以下章节：\n"
            "- `## status` — 内容固定为 `draft`\n"
            "- `## 题干` — 完整题干，包含所有给定条件和背景\n"
            "- `## 选项`（选择题）或 `## 子问题`（综合题）\n"
            "- `## 设计说明` — 知识点选取理由、参数选择理由、干扰策略、难度自评\n\n"
            "注意：不写答案！答案由独立的求解智能体产出。\n\n"
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
        "question_sc": (
            "# 408考研选择题出题专家\n\n"
            "你是408考研选择题出题专家。你将收到出题契约（assembled.md），"
            "请产出符合408风格的单选题（4选1，2分）。\n\n"
            "选择题是选项级考察，核心在选项设计上：计算型4结果竞争、概念辨析型命题判断、"
            "机制理解型对应理解、组合判断型I/II/III。\n\n"
            "## 输出格式\n"
            "- `## status` — `draft`\n"
            "- `## 题干` — 简洁题干（1-3句话），包含所有给定条件\n"
            "- `## 选项` — 4个选项（A/B/C/D），恰好1个正确\n"
            "- `## 设计说明` — 考察模式、干扰策略、K值对齐\n\n"
            "注意：不写答案！答案由独立的求解智能体产出。\n\n"
            "## 核心规则\n"
            "1. 题干简洁精炼，不冗长铺垫\n"
            "2. 干扰项针对具体错误认知，不是随机值\n"
            "3. 参数优先选用 2^n 相关值\n"
            "4. 禁止在题干中出现编程语言代码\n"
            "5. 题目完全原创，不得照搬历史原题\n\n"
            "直接输出 Markdown 内容，不要用代码块包裹。"
        ),
        "question_comp": (
            "# 408考研综合应用题出题专家\n\n"
            "你是408考研综合应用题出题专家。你将收到出题契约（assembled.md），"
            "请产出符合408风格的综合应用题（含多个子问题，连续推演式考察）。\n\n"
            "综合题是连续推演式考察：基础问→核心问→区分度问，子问之间存在串行依赖。\n\n"
            "## 输出格式\n"
            "- `## status` — `draft`\n"
            "- `## 题干` — 完整的系统状态/配置描述，作为所有子问题的共享上下文\n"
            "- `## 子问题` — 2-4个子问题，每个标明分值，前问结果作为后问输入\n"
            "- `## 设计说明` — 考察结构、子问依赖关系、K值对齐\n\n"
            "注意：不写答案！答案由独立的求解智能体产出。\n\n"
            "## 核心规则\n"
            "1. 子问之间必须有逻辑依赖，不允许完全独立\n"
            "2. 每个子问题可从前序结果+题干条件推导\n"
            "3. 参数优先选用 2^n 相关值\n"
            "4. 禁止在题干中出现编程语言代码\n"
            "5. 题目完全原创，不得照搬历史原题\n\n"
            "直接输出 Markdown 内容，不要用代码块包裹。"
        ),
        "solve": (
            "# 408考研独立求解专家\n\n"
            "你是408考研独立求解专家。你将收到一道考试题目，请独立推导出所有答案。\n\n"
            "## 求解策略\n"
            "- 概念/逻辑题：直接推理分析，不需要代码\n"
            "- 数值题：编写 solve.py 代码验证，代码只使用标准库\n\n"
            "## 输出格式\n"
            "Markdown格式（solution.md），按顺序包含以下章节：\n"
            "- `## status` — 内容固定为 `solved`\n"
            "- `## 求解过程` — 每个子问题/选项的推理或计算过程\n"
            "- `## 最终答案` — 选择题给出正确选项和理由，综合题给出各子问题答案\n\n"
            "## 核心规则\n"
            "1. 禁止阅读设计说明——只看题干和子问题\n"
            "2. 所有结果必须从题干参数推导，禁止硬编码\n"
            "3. 每个子问题/选项必须逐一求解\n"
            "4. 数值题代码只用标准库，变量命名体现物理含义\n\n"
            "直接输出 Markdown 内容，不要用代码块包裹。"
        ),
        "review": (
            "# 408考研题目审核专家\n\n"
            "你是408考研题目审核专家（此阶段无答案）。审核题目设计质量。\n\n"
            "## 审核维度\n"
            "1. 知识点覆盖 — 是否与规划一致\n"
            "2. K难度评估 — 实际K值 vs 目标K值（差异>=2级标 needs_fix）\n"
            "3. 条件充分性 — 充分且不冗余\n"
            "4. 题干清晰度 — 精确无歧义\n"
            "5. 选项质量 — 恰好1个正确，干扰项有效（选择题）\n"
            "6. 子问题结构 — 编号连续、分值合理（综合题）\n\n"
            "注意：此阶段无答案，不评估答案正确性。\n\n"
            "## 输出格式\n"
            "Markdown格式，按顺序包含以下章节：\n"
            "- `## status` — `pass` 或 `needs_fix`\n"
            "- `## summary` — 审核总结\n"
            "- `## corrections` — pass写'无'，needs_fix写具体问题\n"
            "- `## detailed_feedback` — 逐项审核发现\n"
            "- `## quality_score` — 分维度打分\n"
            "- `## improvement_suggestions` — 即使 pass 也必须填写\n\n"
            "直接输出 Markdown 内容，不要用代码块包裹。"
        ),
        "final_review": (
            "# 408考研终审专家\n\n"
            "你是408考研终审专家，审核题目和求解结果的整体质量。\n\n"
            "## 审核维度\n"
            "1. 求解正确性 — solution 是否正确回答 question\n"
            "2. 答案唯一性 — 题目是否有唯一解\n"
            "3. 条件利用率 — 每个条件都在求解中使用\n"
            "4. 答案自洽性 — 推理链无跳步无矛盾\n\n"
            "## 路由判定\n"
            "- pass — 通过，输出 final.md\n"
            "- expression_fix — 仅措辞/格式问题，就地修正\n"
            "- question_error — 参数矛盾、条件缺失等根本设计错误，回出题\n"
            "- solution_error — 求解逻辑或计算错误，回求解做最小修改\n\n"
            "## 输出格式\n"
            "Markdown格式，按顺序包含以下章节：\n"
            "- `## status` — pass / expression_fix / question_error / solution_error\n"
            "- `## summary` — 审核总结\n"
            "- `## corrections` — 仅 expression_fix 时写修正内容，否则写'无'\n"
            "- `## detailed_feedback` — 逐项审核发现\n"
            "- `## quality_score` — 按维度打分(1-10): overall, knowledge, self_consistency, difficulty_match, expression_precision\n"
            "- `## improvement_suggestions` — 即使 pass 也必须填写\n"
            "- `## routing_feedback` — 仅 question_error/solution_error 时填写具体修正要求\n\n"
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
        if role == "solve":
            adapter += (
                "\n数值题需先编写 solve.py 并运行验证。"
                "`solve.py` 必须是可直接运行的纯 Python 源码；不要使用 Markdown 代码块；"
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
        if role in {"question", "question_sc", "question_comp", "solve", "review", "final_review"}:
            suffix += "\n如需计算或校验，请在你自己的推理过程中完成，并把必要的校验证据写入目标内容。"
        return task + suffix

    @staticmethod
    def _webgpt_role_output_contract(role: str, expected_fn: str) -> str:
        """Extra constraints for direct-output WebGPT roles.

        These constraints translate the tool/file contract into plain output,
        because WebGPT cannot call local tools.
        """
        if role == "outline":
            return (
                "## 目标文件协议：outline.md\n"
                "必须包含且按顺序输出章节：`## status`、`## 考点`、`## 难度目标`、"
                "`## 考察模式`、`## 出题要求`、`## 子问题规划`、`## 参数约束`、"
                "`## 参考经验`、`## 教师批注区`。\n"
                "`## status` 的内容固定为 `ready`。规划只定义结构、约束和参数范围，"
                "不要提前指定具体数值或完整题干。"
            )
        if role in ("question", "question_sc", "question_comp"):
            return (
                "## 目标文件协议：question.md\n"
                "必须包含且按顺序输出章节：`## status`、`## 题干`、"
                "`## 子问题` 或 `## 选项`、`## 设计说明`。\n"
                "`## status` 的内容固定为 `draft`。题目必须严格遵循契约，"
                "所有给定条件都要被使用。不写答案——答案由独立的求解智能体产出。"
                "参数校验证据写入设计说明，避免暴露冗长思考。"
            )
        if role == "review":
            return (
                "## 目标文件协议：review.md\n"
                "必须包含且按顺序输出章节：`## status`、`## summary`、"
                "`## corrections`、`## detailed_feedback`、"
                "`## quality_score`、`## improvement_suggestions`。\n"
                "`## status` 使用 `pass` 或 `needs_fix`。此阶段无答案，不评估答案正确性。\n"
                "`## quality_score` 按维度打分（1-10）：overall, knowledge, difficulty_match, "
                "condition_quality, expression_precision。\n"
                "`## improvement_suggestions` 即使 pass 也必须填写具体改进方向。"
            )
        if role == "solve":
            return (
                "## 目标文件协议：solution.md\n"
                "必须包含且按顺序输出章节：`## status`、`## 求解过程`、`## 最终答案`。\n"
                "`## status` 的内容固定为 `solved`。概念题直接推理，数值题需先编写并运行 solve.py。"
                "禁止阅读设计说明——只看题干。从题干公开条件推导答案，覆盖每个子问题或每个选项。"
            )
        if role == "final_review":
            return (
                "## 目标文件协议：final_review.md\n"
                "必须包含且按顺序输出章节：`## status`、`## summary`、"
                "`## corrections`（仅expression_fix时）、`## detailed_feedback`、"
                "`## quality_score`、`## improvement_suggestions`、"
                "`## routing_feedback`（仅question_error/solution_error时）。\n"
                "`## status` 使用 `pass`、`expression_fix`、`question_error`、`solution_error`。\n"
                "`## quality_score` 按维度打分（1-10）：overall, knowledge, self_consistency, "
                "difficulty_match, expression_precision。\n"
                "`## improvement_suggestions` 即使 pass 也必须填写。"
            )
        return f"## 目标文件协议：{expected_fn}\n直接输出目标文件完整内容。"

    @classmethod
    def _extract_direct_output(cls, raw: str, *, role: str, expected_fn: str) -> str:
        text = (raw or "").strip()
        extracted = cls._extract_tool_text_content(text)
        if extracted:
            text = extracted.strip()
        if role == "solve" or expected_fn.endswith(".py"):
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

        # Extract a condensed terminology reference from the full task.
        # The full task may contain the entire assembled doc (~13K chars)
        # which GPT already processed — Qwen only needs key terms for
        # alignment, not the full reference again.
        task_ref = _extract_terminology_ref(task)

        qwen_user = (
            f"## GPT 产出的内容\n\n{gpt_content}\n\n"
            f"---\n\n"
            f"## 原始任务参考（用于名词对齐）\n\n{task_ref}\n\n"
            f"---\n\n"
            f"请完成以下工作：\n"
            f"1. 校验GPT内容的格式是否符合 `{expected_fn}` 要求的章节结构\n"
            f"2. 对照任务参考修正专业术语和名词\n"
            f"3. 如果GPT内容包含对已有文件的修改指令（如修正、编辑），先 read_file 读取目标文件，"
            f"   按修改指令调整后再 write_file 写入\n"
            f"4. 如果是全新产出，直接 write_file 写入 `{expected_fn}`\n\n"
            f"最终必须通过 write_file 写入目标文件。"
        )

        # Build tool registry for Qwen
        ws = expected_path.parent
        registry = ToolRegistry()
        registry.register(WriteFileTool(workspace=ws))
        registry.register(ReadFileTool(workspace=ws))
        required_tools = ROLE_REQUIRED_TOOLS.get(role, ["write_file"])
        if "exec_python" in required_tools:
            registry.register(ExecPythonTool(timeout=PYTHON_EXEC_TIMEOUT))

        # Always include read_file + write_file for hybrid modification support
        hybrid_tool_names = list(set(required_tools) | {"write_file", "read_file"})
        tool_list = [registry.get(name) for name in hybrid_tool_names if registry.get(name) is not None]
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
        question_type: str | None = None,
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
            question_type=question_type,
        )
