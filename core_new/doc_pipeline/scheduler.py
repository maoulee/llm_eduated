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
from .exec_file_tool import ExecFileTool
from .exec_python_tool import ExecPythonTool
from .read_file_tool import ReadFileTool
from .write_file_tool import WriteFileTool

logger = logging.getLogger(__name__)


# Roles that must write a secondary file in addition to the primary expected file.
# After the primary file is written, the agent gets one follow-up turn for the secondary.
_SECONDARY_OUTPUTS: dict[str, str] = {
    "final_review": "final.md",
}


def _tool_result_ok(messages: list[dict], tool_call_id: str) -> bool:
    """Check if a tool call produced a successful result (ok=True)."""
    for msg in messages:
        if msg.get("role") == "tool" and msg.get("tool_call_id") == tool_call_id:
            try:
                return json.loads(msg["content"]).get("ok") is True
            except (json.JSONDecodeError, ValueError, TypeError):
                return False
    return False


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
        self.model_routing = model_routing  # role → provider name (for prompt selection only)
        # Multi-turn session state: role → message list
        self._sessions: dict[str, list[dict[str, Any]]] = {}
        # WebGPT session bookkeeping.  ChatGPT conversations are remote state,
        # so track every key we open and clean it when the pipeline finishes.
        self._webgpt_session_keys: set[str] = set()
        self._webgpt_call_counts: dict[str, int] = {}

    def _get_gateway_for_role(self, role: str) -> LLMGateway:
        """Return the unified gateway for all roles.

        All LLM calls go through the single gateway passed at construction time.
        model_routing only controls system prompt selection and WebGPT behavior.
        """
        return self.gateway

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
            "- 确保知识点覆盖主要知识域，避免连续多题考同一知识点\n"
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
            "- 确保知识点覆盖主要知识域，避免连续多题考同一知识点\n"
        ),
        "question_sc": (
            "# 408考研选择题出题专家\n\n"
            "你是408考研选择题出题专家。你将收到出题契约（assembled.md），"
            "请产出符合408风格的单选题（4选1，2分）。\n\n"
            "选择题是选项级考察，核心在选项设计上：计算型4结果竞争、概念辨析型命题判断、"
            "机制理解型对应理解、组合判断型I/II/III。\n\n"
            "## 交付协议\n"
            "你的产出必须且只能通过 write_file 工具调用写入 question.md。\n"
            "正文若符合目标文件结构（含 ## status），系统会自动保存；否则视为中间输出。\n\n"
            "## 输出格式\n"
            "- `## status` — `draft`\n"
            "- `## 题干` — 简洁题干（1-3句话），包含所有给定条件\n"
            "- `## 选项` — 4个选项（A/B/C/D），恰好1个正确\n"
            "- `## 设计说明` — 考察模式、干扰策略、K值对齐\n\n"
            "注意：不写答案！答案由独立的求解智能体产出。数值参数校验由求解智能体负责。\n\n"
            "## 行为约束\n"
            "1. 契约忠实：保留 assembled.md 中的所有知识点和K难度目标，不得遗漏、替换或新增\n"
            "2. 参数优先选用 2^n 相关值\n"
            "3. 干扰项必须针对具体错误认知，不是随机值\n"
            "4. 题目完全原创，不得照搬历史原题\n\n"
            "## 格式红线（违反即判定不合格）\n"
            "1. 禁止子问题格式 — 选择题只有一个题干+四个选项\n"
            "2. 禁止编程代码 — 题干不得包含任何编程语言代码\n"
            "3. 禁止冗长题干 — 题干不超过3句话、80字（不含选项）\n"
            "4. 禁止答案出现在题目中\n"
            "5. 禁止背景故事 — 题干不得包含与考察无关的叙述\n"
        ),
        "question_comp": (
            "# 408考研综合应用题出题专家\n\n"
            "你是408考研综合应用题出题专家。你将收到出题契约（assembled.md），"
            "请产出符合408风格的综合应用题（含多个子问题，连续推演式考察）。\n\n"
            "综合题是连续推演式考察：基础问→核心问→区分度问，子问之间存在串行依赖。\n\n"
            "## 交付协议\n"
            "你的产出必须且只能通过 write_file 工具调用写入 question.md。\n"
            "正文若符合目标文件结构（含 ## status），系统会自动保存；否则视为中间输出。\n\n"
            "## 输出格式\n"
            "- `## status` — `draft`\n"
            "- `## 题干` — 完整的系统状态/配置描述，作为所有子问题的共享上下文\n"
            "- `## 子问题` — 2-4个子问题，每个标明分值，前问结果作为后问输入\n"
            "- `## 设计说明` — 考察结构、子问依赖关系、K值对齐\n\n"
            "注意：不写答案！答案由独立的求解智能体产出。\n\n"
            "## 行为约束\n"
            "1. 契约忠实：保留 assembled.md 中的所有知识点、K难度目标和子问结构，不得遗漏\n"
            "2. 子问之间必须有逻辑依赖（串行或混合），不允许完全独立\n"
            "3. 每个子问题可从前序结果+题干条件推导\n"
            "4. 参数优先选用 2^n 相关值\n"
            "5. 条件充分不冗余——每个给定条件都要被子问题用到\n"
            "6. 题目完全原创，不得照搬历史原题\n\n"
            "## 格式红线（违反即判定不合格）\n"
            "1. 禁止选项格式 — 子问题不得包含A/B/C/D选项\n"
            "2. 禁止独立子问 — 每个子问题必须引用前序结果或共享题干条件\n"
            "3. 禁止编程代码题干 — 题干不得包含C/Java/Python代码（结构体/类型定义除外）\n"
            "4. 禁止背景故事 — 题干不得包含与考察无关的叙述\n"
            "5. 禁止答案出现在题目中\n"
        ),
        "solve": (
            "# 408考研独立求解专家\n\n"
            "你是408考研独立求解专家。你将收到一道考试题目，请独立推导出所有答案。\n\n"
            "## 交付协议\n"
            "你的产出必须且只能通过 write_file 工具调用写入 solution.md。\n"
            "正文若符合目标文件结构（含 ## status），系统会自动保存；否则视为中间输出。\n\n"
            "## 工作流程（数值题）\n"
            "1. read_file(question.md) 读取题干\n"
            "2. 参数校验：write_file(verify.py) → exec_file(verify.py)\n"
            "   - 校验参数封闭性、整除性、单位换算、推导路径等价\n"
            "   - 参数不自洽时：edit_file 修改 question.md 中的数值（只改数值，不改结构）\n"
            "3. 求解：write_file(solution.md) 写出完整求解过程\n"
            "4. 代码验证：write_file(solve.py) → exec_file(solve.py)，对比答案\n"
            "   - 不一致时 edit_file 修正\n\n"
            "概念题跳过步骤2和4，直接推理后 write_file(solution.md)。\n\n"
            "## 求解策略\n"
            "- 概念/逻辑题：直接推理分析，不需要代码\n"
            "- 数值题：必须先校验参数再求解，代码只使用标准库\n"
            "- 有数值就必须有 solve.py — 这是硬性要求\n\n"
            "## 输出格式\n"
            "Markdown格式（solution.md），按顺序包含以下章节：\n"
            "- `## status` — 内容固定为 `solved`\n"
            "- `## 求解过程` — 每个子问题/选项的推理或计算过程\n"
            "- `## 最终答案` — 选择题给出正确选项和理由，综合题给出各子问题答案\n\n"
            "如果有可运行代码，同时输出 solve.py（不包裹Markdown代码块）。\n\n"
            "## 核心规则\n"
            "1. 禁止阅读设计说明——只看题干和子问题\n"
            "2. 所有结果必须从题干参数推导，禁止硬编码\n"
            "3. 每个子问题/选项必须逐一求解\n"
            "4. 数值题代码只用标准库，变量命名体现物理含义\n"
            "5. 代码必须打印 ANSWER: ... 行\n"
            "6. 结果对比验证：代码计算出答案后，选择至少一个子问题用手算交叉验证\n"
        ),
        "review": (
            "# 408考研题目审核专家\n\n"
            "你是408考研题目审核专家（此阶段无答案）。审核题目设计质量。\n\n"
            "## 交付协议\n"
            "你的审核结论必须且只能通过 write_file 工具调用写入 review.md。\n"
            "正文若符合目标文件结构（含 ## status），系统会自动保存；否则视为中间输出。\n"
            "不要在正文中展开完整审核推导——在思考中完成推理，直接产出审核结论文件。\n\n"
            "## 审核维度\n"
            "1. 知识点覆盖 — 是否与规划一致，不得遗漏或新增\n"
            "2. K难度评估 — 实际K值 vs 目标K值（差异>=2级标 needs_fix）\n"
            "3. 条件充分性 — 充分且不冗余，每个条件被子问题/选项使用\n"
            "4. 题干清晰度 — 精确无歧义\n"
            "5. 选项质量 — 恰好1个正确，干扰项有效（选择题）\n"
            "6. 子问题结构 — 编号连续、分值合理、子问有依赖（综合题）\n"
            "7. 格式红线 — 选择题:禁止子问题/代码/冗长/背景故事; 综合题:禁止选项/独立子问/代码/背景故事\n"
            "8. 题干风格与考察形式 — 是否像408真题（非教科书例题）、考察形式是否匹配规划、区分度如何\n"
            "9. 经验卡对齐 — should_be满足、should_not_be未触犯、考察模式在建议范围内\n\n"
            "违反格式红线或should_not_be应标记 needs_fix。\n"
            "题干风格不像408真题（教科书感、过度铺垫、无区分度）也应标记 needs_fix。\n\n"
            "注意：此阶段无答案，不评估答案正确性。\n\n"
            "## 评分理由要求\n"
            "每个维度的 detailed_feedback 必须包含具体理由：\n"
            "- 通过: 说明为什么通过（如'K1=3 与目标一致，锚点匹配'）\n"
            "- 偏差: 说明具体偏差值和原因（如'K3 实际=1 目标=3，偏差2级，当前只需1步代入'）\n"
            "禁止只写'通过'或'偏差'不给理由。\n\n"
            "## 最小修改原则\n"
            "needs_fix 时 corrections 必须：\n"
            "- 指出需要修改的具体部分（具体参数/选项/措辞）\n"
            "- 明确标注已达标、不需要改的部分\n"
            "- 修正建议必须是可操作的最小变更\n"
            "- 禁止要求全文重写\n\n"
            "## 输出格式\n"
            "Markdown格式，按顺序包含以下章节：\n"
            "- `## status` — `pass` 或 `needs_fix`\n"
            "- `## summary` — 审核总结\n"
            "- `## corrections` — pass写'无'，needs_fix按问题逐条列出（当前状态/期望状态/修正建议/不要修改）\n"
            "- `## detailed_feedback` — 逐项审核发现，每项必须附理由\n"
            "- `## quality_score` — 分维度打分，每项附理由\n"
            "- `## improvement_suggestions` — 即使 pass 也必须填写\n"
        ),
        "final_review": (
            "# 408考研终审专家\n\n"
            "你是408考研终审专家，审核题目和求解结果的交付一致性。\n"
            "通过时你还需要产出最终交付文档（final.md）。\n\n"
            "## 交付协议\n"
            "你的审核结论必须通过 write_file 工具调用写入 final_review.md。\n"
            "正文若符合目标文件结构（含 ## status），系统会自动保存；否则视为中间输出。\n"
            "不要在正文中展开完整审核推导——在思考中完成推理，直接产出审核结论文件。\n"
            "通过时需同时写入 final.md（最终交付文档，不含审核元数据）。\n\n"
            "## 审核方法\n"
            "**禁止写代码、禁止执行代码** — 数值验证由 solve 阶段完成，你只读取证据核对。\n\n"
            "数值题：\n"
            "1. read_file 读取 solution.md，提取最终答案中的数值\n"
            "2. read_file 读取 solve_output.txt，提取代码输出的数值\n"
            "3. 对比两者是否一致\n\n"
            "概念题：\n"
            "1. read_file 读取 question.md + solution.md\n"
            "2. 检查推理链完整性和答案唯一性\n\n"
            "## 审核维度\n"
            "1. 证据核对（数值题）— solution 答案 vs solve_output 是否一致\n"
            "2. 答案唯一性 — 题目是否有唯一解\n"
            "3. 条件利用率 — 每个条件都在求解中使用\n"
            "4. 答案自洽性 — 推理链无跳步无矛盾\n"
            "5. 蓝图匹配 — 知识点覆盖与规划一致，K难度实际 vs 目标（差异>=2级需标记）\n\n"
            "## 路由判定\n"
            "- pass — 证据一致、求解正确，写 final_review.md + 写 final.md\n"
            "- expression_fix — 仅措辞/格式问题，final.md中修正后写 final_review.md + final.md\n"
            "- question_error — 参数矛盾、条件缺失等根本设计错误，回出题（不写 final.md）\n"
            "- solution_error — 数值不一致或求解逻辑错误，回求解重新求解（不写 final.md）\n\n"
            "## 评分理由要求\n"
            "每个维度的 detailed_feedback 必须包含具体理由：\n"
            "- 通过: 说明为什么（如'solve_output=9, solution答案=9，一致'）\n"
            "- 偏差: 说明具体问题（如'solve_output=9, solution答案=10，不一致'）\n"
            "禁止只给分数不给理由。\n\n"
            "## 最小修改原则\n"
            "- expression_fix: 只改措辞/格式，不改参数/逻辑/答案\n"
            "- question_error routing_feedback: 指出具体参数/条件需要改的最小范围\n"
            "- solution_error routing_feedback: 指出具体哪步推导有误\n"
            "- 明确标注已达标、不需要改的部分\n\n"
            "## final.md 格式（仅 pass/expression_fix 时写入）\n"
            "- `## 题目` — 题干原文\n"
            "- `## 选项`（选择题）或 `## 子问题`（综合题） — 原文\n"
            "- `## 求解过程` — 从 solution.md 提取的关键步骤\n"
            "- `## 答案` — 最终答案\n"
            "- `## 设计说明`（可选） — 仅保留有教学参考价值的内容\n"
            "注意：final.md 中不包含 status、summary、score 等审核元数据\n\n"
            "## 输出格式\n"
            "Markdown格式，按顺序包含以下章节：\n"
            "- `## status` — pass / expression_fix / question_error / solution_error\n"
            "- `## summary` — 审核总结\n"
            "- `## detailed_feedback` — 逐项审核发现，每项必须附理由\n"
            "- `## quality_score` — 按维度打分(1-10): overall, self_consistency, difficulty_match, expression\n"
            "- `## improvement_suggestions` — 即使 pass 也必须填写\n"
            "- `## routing_feedback` — 仅 question_error/solution_error 时填写具体修正要求\n"
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
        target_file: str | None = None,
        preserve_existing: bool = False,
        enable_thinking: bool | None = None,
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
            target_file: Override the role's default output file for this call.
            preserve_existing: Keep an existing target file so the agent can
                edit_file it during feedback rounds. Stale files are still not
                accepted as success unless this call writes/edits the target.

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
        if continue_session and f"{slot_id}:{role}" in self._sessions:
            messages = list(self._sessions[f"{slot_id}:{role}"])
            messages.append({"role": "user", "content": full_task})
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_task},
            ]

        expected_fn = target_file or AGENT_OUTPUT_FILES.get(role, "output.md")
        expected_path = ws / expected_fn

        # Avoid accepting stale artifacts from previous attempts/runs. Feedback
        # rounds intentionally preserve the file so edit_file has something to
        # modify; success is still gated on this call writing/editing target_fn.
        if expected_path.exists() and not preserve_existing:
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
        if "exec_file" in required_tools:
            registry.register(ExecFileTool(workspace=ws, timeout=PYTHON_EXEC_TIMEOUT))
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
        write_tool = registry.get("write_file")
        write_only_tools = [write_tool.to_openai_tool()] if write_tool is not None else []
        forced_write_choice = {
            "type": "function",
            "function": {"name": "write_file"},
        }

        # 5. Streaming tool-calling loop via shared gateway transport.
        gateway = self._get_gateway_for_role(role)
        effective_max_tokens = max_tokens or self.max_tokens
        effective_thinking_budget = ROLE_THINKING_BUDGET.get(role, DEFAULT_THINKING_BUDGET)

        # Thinking models (Qwen3, etc.) count reasoning tokens against
        # max_tokens.  Ensure enough headroom so reasoning doesn't consume
        # the entire output budget before tool calls land.
        if effective_thinking_budget and effective_thinking_budget > 0:
            effective_max_tokens = max(effective_max_tokens, effective_thinking_budget + 16000)
        final_text = ""

        # Model decides when to call tools. Boundary detection (streak counters)
        # and commit-only mode handle stuck situations — no need to force tool
        # calls upfront.  Qwen3's text-embedded tool calls are handled by
        # _extract_textual_tool_call and reasoning_content extraction fallbacks.
        forced_tool_choice = "auto"

        # Progress tracking — distinguishes productive intermediate steps
        # from genuine stuck loops.
        #
        # no_file_streak: consecutive rounds with ZERO file writes (any file).
        #   Resets whenever write_file or edit_file succeeds.  Only triggers
        #   commit-only when the model keeps calling exec/read without ever
        #   producing a file artifact — a genuine stuck signal.
        #
        # total_non_target_rounds: total rounds without writing the *expected*
        #   file.  Catches endless verification loops where intermediate .py
        #   files keep being written but the target .md is never produced.
        no_file_streak = 0
        total_non_target_rounds = 0
        no_output_streak = 0
        intermediate_text_count = 0
        commit_only_mode = False
        commit_only_entered_at = -1  # attempt index when commit-only started

        # Trace file for per-round diagnostics
        _trace_path = ws / "trace.jsonl"

        def _write_trace(event: dict) -> None:
            import json as _json
            event.setdefault("agent", role)
            event.setdefault("slot_id", slot_id)
            with open(_trace_path, "a", encoding="utf-8") as _tf:
                _tf.write(_json.dumps(event, ensure_ascii=False) + "\n")

        _COMMIT_ONLY_BUDGET = 3  # max attempts after entering commit-only
        _MAX_INTERMEDIATE_TEXT = 2  # max intermediate reasoning rounds before boundary

        def enter_commit_only_mode(reason: str) -> None:
            nonlocal openai_tools, forced_tool_choice
            nonlocal messages, commit_only_mode, commit_only_entered_at
            if commit_only_mode:
                return
            commit_only_entered_at = attempt
            logger.warning(
                "[%s] Agent '%s': entering commit-only mode for %s (%s)",
                slot_id, role, expected_fn, reason,
            )
            commit_only_mode = True
            openai_tools = write_only_tools
            forced_tool_choice = forced_write_choice
            messages = self._build_commit_only_messages(
                system_prompt=system_prompt,
                full_task=full_task,
                history=messages,
                workspace=ws,
                expected_fn=expected_fn,
                reason=reason,
            )

        for attempt in range(MAX_AGENT_ATTEMPTS):
            # Cap attempts after entering commit-only to prevent infinite loops.
            if commit_only_mode and attempt - commit_only_entered_at >= _COMMIT_ONLY_BUDGET:
                logger.warning(
                    "[%s] Agent '%s': commit-only budget exhausted after %d attempts",
                    slot_id, role, _COMMIT_ONLY_BUDGET,
                )
                break

            try:
                raw = await self._streaming_chat_call(
                    gateway, messages,
                    max_tokens=effective_max_tokens,
                    thinking_budget=effective_thinking_budget,
                    tools=openai_tools,
                    tool_choice=forced_tool_choice,
                )
            except Exception as exc:
                # API errors (400 malformed messages, 500, timeouts) are
                # recoverable — drop the last assistant+tool pair if present
                # and inject a fresh retry prompt.
                exc_name = type(exc).__name__
                logger.warning(
                    "[%s] Agent '%s' attempt %d: API error (%s: %s), recovering",
                    slot_id, role, attempt + 1, exc_name, str(exc)[:200],
                )
                # Remove trailing assistant + tool messages that may contain
                # malformed data (e.g. tool_call with empty arguments).
                while messages and messages[-1]["role"] in ("assistant", "tool"):
                    messages.pop()
                messages.append({
                    "role": "user",
                    "content": (
                        f"系统错误，请重新调用 "
                        f"write_file(path=\"{expected_fn}\", content=\"完整内容\") "
                        f"写入你的最终产出。"
                    ),
                })
                continue

            tool_calls = raw.get("tool_calls")
            content = raw.get("content", "")

            # Qwen3 sometimes embeds tool calls in reasoning_content instead
            # of the protocol channel or content.  Try extracting from there
            # if the primary channels yielded nothing.
            if not tool_calls and not content:
                reasoning = raw.get("reasoning_content") or raw.get("reasoning") or ""
                if reasoning and ("write_file" in reasoning or "exec_file" in reasoning):
                    extracted = self._extract_textual_tool_call(reasoning)
                    if extracted:
                        tool_calls = extracted
                        logger.info(
                            "[%s] Agent '%s': extracted tool call from reasoning_content",
                            slot_id, role,
                        )

            action, payload = self._resolve_output(
                content, tool_calls, expected_fn,
            )

            # Write trace for this round
            reasoning_text = raw.get("reasoning") or raw.get("reasoning_content") or ""
            _write_trace({
                "attempt": attempt + 1,
                "action": action,
                "content_len": len(content or ""),
                "reasoning_len": len(reasoning_text),
                "finish_reason": raw.get("finish_reason"),
                "tool_calls": [tc["function"]["name"] for tc in tool_calls] if tool_calls else [],
            })
            if action == "execute_tools":
                no_output_streak = 0
                # Sanitize tool_call arguments — vLLM may return
                # empty/malformed JSON that breaks the next request.
                for tc in payload:
                    args_raw = tc["function"]["arguments"]
                    if not args_raw or not isinstance(args_raw, str) or not args_raw.strip():
                        tc["function"]["arguments"] = "{}"
                    else:
                        try:
                            json.loads(args_raw)
                        except (json.JSONDecodeError, ValueError):
                            tc["function"]["arguments"] = "{}"

                assistant_msg = {"role": "assistant", "content": content or None}
                assistant_msg["tool_calls"] = payload
                messages.append(assistant_msg)

                wrote_expected_file = False
                available_names = {t["function"]["name"] for t in openai_tools}
                for tc in payload:
                    fn_name = tc["function"]["name"]
                    fn_args_str = tc["function"]["arguments"]
                    try:
                        fn_args = json.loads(fn_args_str) if isinstance(fn_args_str, str) else fn_args_str
                    except json.JSONDecodeError:
                        fn_args = {}

                    logger.info("[%s] Executing tool: %s(%s)", slot_id, fn_name, str(fn_args)[:100])
                    if fn_name in available_names:
                        result_str = await executor.execute(fn_name, fn_args)
                    else:
                        result_str = json.dumps(
                            {"ok": False, "error": f"tool '{fn_name}' not available; available: {available_names}"},
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
                    break

                # Track progress: did the model write ANY file this round?
                wrote_any_file = any(
                    tc["function"]["name"] in ("write_file", "edit_file")
                    and _tool_result_ok(messages, tc["id"])
                    for tc in payload
                )
                if wrote_any_file:
                    no_file_streak = 0
                else:
                    no_file_streak += 1

                total_non_target_rounds += 1
                logger.info(
                    "[%s] Agent '%s' attempt %d: tools executed, %s not written "
                    "(no_file=%d, total=%d, continuing)",
                    slot_id, role, attempt + 1, expected_fn,
                    no_file_streak, total_non_target_rounds,
                )

                # Intervention tier 1: no files written at all for 4+ rounds
                # (model keeps calling exec/read without producing artifacts)
                if no_file_streak >= 4:
                    if not commit_only_mode:
                        enter_commit_only_mode(
                            f"no file progress: {no_file_streak} rounds without any file write"
                        )
                    else:
                        messages.append({
                            "role": "user",
                            "content": (
                                f"仍未写入 {expected_fn}。当前阶段只有 write_file 可用；"
                                f"请调用 write_file(path=\"{expected_fn}\", content=\"完整最终内容\")。"
                            ),
                        })
                    continue

                # Intervention tier 2: files being written but never the target
                # (endless verification loop with intermediate .py files)
                if total_non_target_rounds >= 7:
                    if not commit_only_mode:
                        enter_commit_only_mode(
                            f"verification loop: {total_non_target_rounds} rounds without {expected_fn}"
                        )
                    else:
                        messages.append({
                            "role": "user",
                            "content": (
                                f"已执行 {total_non_target_rounds} 轮验证但未写入 {expected_fn}。"
                                f"请调用 write_file(path=\"{expected_fn}\", content=\"完整最终内容\")。"
                            ),
                        })
                    continue
                continue

            # ── Path B: Direct write from text content ──────────────
            if action == "direct_write":
                no_output_streak = 0
                write_args = {"path": expected_fn, "content": payload}
                result_str = await executor.execute("write_file", write_args)
                try:
                    parsed = json.loads(result_str)
                except json.JSONDecodeError:
                    parsed = {}
                if parsed.get("ok") and expected_path.exists():
                    logger.info(
                        "[%s] Agent '%s' attempt %d: direct_write %s (%d chars)",
                        slot_id, role, attempt + 1, expected_fn, len(payload),
                    )
                    final_text = expected_path.read_text(encoding="utf-8")
                    break
                logger.warning(
                    "[%s] Agent '%s' attempt %d: direct_write failed, retrying",
                    slot_id, role, attempt + 1,
                )
                messages.append({
                    "role": "user",
                    "content": f"文件写入失败，请重新调用 write_file(path=\"{expected_fn}\", content=\"完整内容\")。",
                })
                continue

            # ── Path B2: Intermediate reasoning — continue (capped) ──
            if action == "intermediate_text":
                no_output_streak = 0
                intermediate_text_count += 1
                logger.info(
                    "[%s] Agent '%s' attempt %d: intermediate_text (%d chars, %d/%d)",
                    slot_id, role, attempt + 1, len(payload),
                    intermediate_text_count, _MAX_INTERMEDIATE_TEXT,
                )
                # Boundary: too many reasoning rounds — enter commit-only
                if intermediate_text_count > _MAX_INTERMEDIATE_TEXT:
                    if not commit_only_mode:
                        enter_commit_only_mode(
                            f"intermediate_text limit: {intermediate_text_count} reasoning rounds"
                        )
                    continue
                # Keep full reasoning text in context (incremental mode — no truncation)
                messages.append({"role": "assistant", "content": payload})
                total_non_target_rounds += 1
                continue

            # ── Path C: No output — retry ───────────────────────────
            no_output_streak += 1
            reasoning_text = raw.get("reasoning") or raw.get("reasoning_content") or ""
            logger.warning(
                "[%s] Agent '%s' attempt %d: no_output "
                "(content=%d chars, reasoning=%d chars, finish=%s); retrying",
                slot_id, role, attempt + 1, len(content or ""),
                len(reasoning_text),
                raw.get("finish_reason"),
            )
            if reasoning_text:
                logger.info(
                    "[%s] Agent '%s' attempt %d reasoning (first 2000 chars): %s",
                    slot_id, role, attempt + 1, reasoning_text[:2000],
                )
            if content:
                logger.info(
                    "[%s] Agent '%s' attempt %d content (first 500 chars): %s",
                    slot_id, role, attempt + 1, content[:500],
                )
            if not commit_only_mode and (total_non_target_rounds >= 3 or no_output_streak >= 2):
                enter_commit_only_mode(
                    f"unusable output: no_output_streak={no_output_streak}, "
                    f"total_non_target_rounds={total_non_target_rounds}"
                )
                continue

            retry_prompt = (
                f"上一轮输出未被保存。\n"
                f"1. 正文若含 ## status 等目标文件结构会自动保存，否则视为中间输出\n"
                f"2. 可直接输出完整Markdown，也可调用 write_file 写入\n"
                f"3. 目标文件：{expected_fn}\n"
            )
            messages.append({"role": "user", "content": retry_prompt})

        # 5b. Secondary file follow-up — if role has a secondary output that
        # wasn't written in the same batch, give the agent one more turn.
        secondary_fn = _SECONDARY_OUTPUTS.get(role)
        if secondary_fn and final_text and not (ws / secondary_fn).exists():
            logger.info(
                "[%s] Agent wrote %s but not secondary %s — sending follow-up",
                slot_id, expected_fn, secondary_fn,
            )
            messages.append({
                "role": "user",
                "content": (
                    f"已收到 {expected_fn}。"
                    f"请现在通过 write_file(path=\"{secondary_fn}\", content=\"...\") "
                    f"写入 {secondary_fn}（最终交付文档）。"
                    f"不要修改 {expected_fn}，只写 {secondary_fn}。"
                ),
            })
            for sec_attempt in range(2):
                sec_raw = await self._streaming_chat_call(
                    gateway, messages,
                    max_tokens=effective_max_tokens,
                    thinking_budget=effective_thinking_budget,
                    tools=write_only_tools,
                    tool_choice=forced_write_choice,
                )
                sec_tcs = sec_raw.get("tool_calls")
                sec_content = sec_raw.get("content", "")
                if not sec_tcs and sec_content and sec_content.lstrip().startswith("["):
                    extracted = self._extract_textual_tool_call(sec_content)
                    if extracted:
                        sec_tcs = extracted

                if not sec_tcs:
                    messages.append({
                        "role": "user",
                        "content": f"请通过 write_file 写入 {secondary_fn}，不要输出正文。",
                    })
                    continue

                # Sanitize secondary tool_call arguments
                for tc in sec_tcs:
                    args_raw = tc["function"]["arguments"]
                    if not args_raw or not isinstance(args_raw, str) or not args_raw.strip():
                        tc["function"]["arguments"] = "{}"
                    else:
                        try:
                            json.loads(args_raw)
                        except (json.JSONDecodeError, ValueError):
                            tc["function"]["arguments"] = "{}"

                assistant_msg = {"role": "assistant", "content": sec_content or None}
                assistant_msg["tool_calls"] = sec_tcs
                messages.append(assistant_msg)

                for tc in sec_tcs:
                    fn_name = tc["function"]["name"]
                    fn_args_str = tc["function"]["arguments"]
                    try:
                        fn_args = json.loads(fn_args_str) if isinstance(fn_args_str, str) else fn_args_str
                    except json.JSONDecodeError:
                        fn_args = {}
                    logger.info("[%s] Executing tool: %s(%s)", slot_id, fn_name, str(fn_args)[:100])
                    if fn_name == "write_file":
                        result_str = await executor.execute(fn_name, fn_args)
                    else:
                        result_str = json.dumps(
                            {"ok": False, "error": f"unexpected tool: {fn_name}"},
                            ensure_ascii=False,
                        )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result_str,
                    })

                if (ws / secondary_fn).exists():
                    logger.info(
                        "[%s] Secondary file %s written (attempt %d)",
                        slot_id, secondary_fn, sec_attempt + 1,
                    )
                    break
                logger.warning(
                    "[%s] Secondary file %s not written (attempt %d), retrying",
                    slot_id, secondary_fn, sec_attempt + 1,
                )
                messages.append({
                    "role": "user",
                    "content": f"请只通过 write_file(path=\"{secondary_fn}\", content=\"...\") 写入 {secondary_fn}。",
                })

        # 6. Update session state for multi-turn agents
        if role in MULTI_TURN_AGENTS:
            self._sessions[f"{slot_id}:{role}"] = messages

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
            "因此即使上文角色合约提到 write_file、edit_file、read_file、exec_python 或 exec_file，"
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
        if role in {"question_sc", "question_comp", "solve", "review", "final_review"}:
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
        if role in ("question_sc", "question_comp"):
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
        if expected_fn.endswith(".py"):
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
        if "edit_file" in required_tools:
            registry.register(EditFileTool(workspace=ws))

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

    # ── Commit-only recovery ─────────────────────────────────────────

    @staticmethod
    def _build_commit_only_messages(
        *,
        system_prompt: str,
        full_task: str,
        history: list[dict[str, Any]],
        workspace: Path,
        expected_fn: str,
        reason: str,
    ) -> list[dict[str, str]]:
        """Build a short, clean context for the final write_file turn.

        Once an agent has spent several turns validating without writing the
        target file, keeping the full assistant/tool history tends to amplify
        malformed tool-call output.  This recovery prompt preserves the original
        task and compact verification evidence, but removes prior assistant
        tool-call messages from the next request.
        """
        override = (
            "\n\n【提交阶段覆盖规则】验证/探索阶段已经结束。"
            "现在只有 write_file 工具可用。禁止调用或书写 exec_file、edit_file、read_file、"
            "exec_python、JSON工具调用正文或XML工具调用。"
            f"必须一次调用 write_file(path=\"{expected_fn}\", content=\"完整最终内容\")。"
            "不要输出正文说明。"
        )
        evidence_parts = []
        tool_summary = DocScheduler._summarize_tool_history(history)
        if tool_summary:
            evidence_parts.append("## 已执行工具摘要\n" + tool_summary)
        artifact_summary = DocScheduler._summarize_workspace_artifacts(workspace, expected_fn)
        if artifact_summary:
            evidence_parts.append("## 当前工作区已写文件摘要\n" + artifact_summary)

        recovery_prompt = (
            f"系统进入最终提交阶段。\n\n"
            f"触发原因: {reason}\n\n"
            f"目标文件: {expected_fn}\n\n"
            "请基于原始任务和以下验证事实，直接提交最终文件。"
            "不要再验证、不要重写验证脚本、不要请求额外工具。\n"
        )
        if evidence_parts:
            recovery_prompt += "\n\n" + "\n\n".join(evidence_parts)
        recovery_prompt += (
            f"\n\n唯一允许动作: write_file(path=\"{expected_fn}\", content=\"完整最终内容\")"
        )

        return [
            {"role": "system", "content": (system_prompt or "") + override},
            {"role": "user", "content": full_task},
            {"role": "user", "content": recovery_prompt},
        ]

    @staticmethod
    def _summarize_tool_history(history: list[dict[str, Any]], max_items: int = 8) -> str:
        summaries: list[str] = []
        for msg in history:
            if msg.get("role") != "tool":
                continue
            content = str(msg.get("content") or "")
            try:
                data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                summaries.append(DocScheduler._truncate_text(content, 600))
                continue

            if "path" in data and "size" in data:
                summaries.append(
                    f"- write_file: path={data.get('path')}, ok={data.get('ok')}, size={data.get('size')}"
                )
                continue

            if "exit_code" in data or "stdout" in data or "stderr" in data:
                stdout = DocScheduler._truncate_text(str(data.get("stdout") or ""), 900)
                stderr = DocScheduler._truncate_text(str(data.get("stderr") or ""), 600)
                line = f"- exec_file: ok={data.get('ok')}, exit_code={data.get('exit_code')}"
                if stdout:
                    line += f"\n  stdout:\n{stdout}"
                if stderr:
                    line += f"\n  stderr:\n{stderr}"
                summaries.append(line)
                continue

            summaries.append("- tool: " + DocScheduler._truncate_text(content, 600))

        return "\n".join(summaries[-max_items:])

    @staticmethod
    def _summarize_workspace_artifacts(workspace: Path, expected_fn: str) -> str:
        if not workspace.exists():
            return ""
        chunks: list[str] = []
        total_chars = 0
        for path in sorted(workspace.iterdir()):
            if not path.is_file() or path.name == expected_fn:
                continue
            if path.suffix not in {".py", ".txt", ".md"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            snippet = DocScheduler._truncate_text(text, 1800)
            chunk = f"### {path.name}\n{snippet}"
            chunks.append(chunk)
            total_chars += len(chunk)
            if total_chars >= 6000:
                break
        return "\n\n".join(chunks)

    @staticmethod
    def _truncate_text(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        half = max(0, (max_chars - 32) // 2)
        return text[:half] + "\n...[truncated]...\n" + text[-half:]

    # ── Text tool-call extraction ─────────────────────────────────

    @staticmethod
    def _extract_textual_tool_call(content: str) -> list[dict] | None:
        """Extract tool calls from text when the model types them as JSON.

        Qwen3 sometimes outputs tool calls as plain text instead of through
        the protocol ``tool_calls`` channel.  Handles both array format
        ``[{"name": "write_file", ...}]`` and single-object format
        ``{"name": "write_file", ...}``.
        """
        text = content.strip()
        if not text.startswith(("[", "{")):
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None

        # Normalize single-object to list for uniform processing.
        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list) or not parsed:
            return None

        _ALLOWED = ("write_file", "exec_file", "edit_file", "read_file")
        tool_calls = []
        for item in parsed:
            name = item.get("name") or (item.get("function", {}) or {}).get("name")
            if not name or name not in _ALLOWED:
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

    # ── Unified output resolution ──────────────────────────────────

    @staticmethod
    def _resolve_output(
        content: str,
        tool_calls: list[dict] | None,
        expected_fn: str,
    ) -> tuple[str, Any]:
        """Resolve model output into an actionable result.

        Returns one of:
          ("execute_tools", tool_calls)     — protocol or extracted tool calls
          ("direct_write", file_content)    — text to write directly
          ("intermediate_text", text)        — reasoning/intermediate, continue
          ("no_output", None)               — cannot resolve, needs retry
        """
        # 1. Protocol tool_calls present
        if tool_calls:
            return ("execute_tools", tool_calls)

        if not content or len(content) < 50:
            return ("no_output", None)

        stripped = content.strip()

        # 2. JSON array of tool calls
        if stripped.startswith("["):
            extracted = DocScheduler._extract_textual_tool_call(content)
            if extracted:
                return ("execute_tools", extracted)

        # 3. JSON wrapper {"path": "...", "content": "..."}
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict) and "content" in obj and len(str(obj["content"])) > 50:
                return ("direct_write", obj["content"])
        except (json.JSONDecodeError, ValueError):
            pass

        # 4. Valid markdown content — must look like structured target output
        # (not just a random "# 分析" reasoning section)
        if stripped.startswith("#") and len(stripped) > 200:
            if "## status" in stripped:
                return ("direct_write", stripped)
            # Has markdown headers but no ## status — likely reasoning, not target
            return ("intermediate_text", stripped)

        # 5. Intermediate reasoning text — model is thinking, continue
        if len(stripped) > 100:
            return ("intermediate_text", stripped)

        return ("no_output", None)

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
