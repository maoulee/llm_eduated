"""AgentMD loader — reads agents/*.md files and produces the same
data structures that agents.py exported (AGENT_PROMPTS, AGENT_OUTPUT_FILES, etc.).

Each AgentMD file has YAML frontmatter + markdown body:

    ---
    name: design
    phase: 1
    output_file: blueprint.md
    thinking_budget: 8000
    multi_turn: false
    ...
    ---

    (markdown body = system prompt)

The loader:
1. Reads all *.md from the agents/ directory
2. Parses YAML frontmatter into metadata
3. Appends the mandatory write_file suffix to each prompt body
4. Exports the same dicts the scheduler imports from agents.py
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_AGENTS_DIR = Path(__file__).parent / "agents"
_SKILLS_DIR = Path(__file__).parent / "skills"

# ── Behavior layer ────────────────────────────────────────────────
# Universal behavior control shared across all agents.
# Replaces the long per-agent role contracts.

_BEHAVIOR_CORE = (
    "你是408考研出题流程的执行角色。按指令直接行动，工具调用无需解释理由。\n"
    "正文输出若符合文件格式（Markdown标题开头），系统会自动写入目标文件。\n"
    "收到修正反馈时：分析反馈 → edit_file 最小修改 → 不要全量重写。\n"
)

_BEHAVIOR_VARIANTS = {
    "outline": "plan_design",
    "question_sc": "question_create",
    "question_comp": "question_create",
    "review": "audit_judge",
    "solve": "solve_create",
    "final_review": "final_review",
    # --- 2-agent pipeline ---
    "creator": "creator_solve",
    "reviewer": "checkpoint_review",
}

_BEHAVIOR_VARIANT_TEXT = {
    "plan_design": (
        "你的模式是「分析输入→构建框架→填充细节→输出」。"
        "先搭骨架再填充，不要一开始就写完整内容。"
    ),
    "question_create": (
        "你的模式是「设计→输出」。\n"
        "设计阶段：深入思考知识点覆盖、逻辑关联、题干表述、消除歧义。\n"
        "数值参数校验不在此阶段——由求解智能体负责。\n"
        "不写答案：答案由独立的求解智能体产出，你只输出题干+选项/子问题+设计说明。"
    ),
    "audit_judge": (
        "你的模式是「结构化审核→结论→输出」。"
        "按检查清单逐项判断，每项给结论不给推导。"
        "此阶段无答案，不评估答案正确性。"
    ),
    "solve_create": (
        "你的模式是「读题→参数校验→参数修订（如有冲突）→求解→代码验证→输出」。\n"
        "数值题必须先校验参数再求解：write verify.py → exec，参数不自洽时edit question.md改数值（代码为王）。\n"
        "概念题直接推理，跳过校验。\n"
        "禁止阅读设计说明——只看题干。"
    ),
    "final_review": (
        "你的模式是「读取证据→核对一致性→路由判定→输出」。\n"
        "数值题：read_file 读取 solve 证据，对比 solution 答案与代码输出，不一致则 solution_error 回求解。\n"
        "概念题：检查推理链完整性和答案唯一性。\n"
        "不写代码、不执行代码——数值验证由 solve 阶段完成。"
    ),
    # --- 2-agent pipeline ---
    "creator_solve": (
        "你负责：设计题干框架(占位符)→代码设计参数→独立求解→等待终审→组装交付，严格按序。\n"
        "Step 1a 只写框架不写具体数值；Step 1b 用代码计算参数并替换占位符。\n"
        "暂停点：写入 question.md 后停止；写入 solution.md 后停止。禁止评价自己的设计质量。"
    ),
    "checkpoint_review": (
        "你负责双检查点审核。根据可用文件判定检查点：\n"
        "检查点1（仅有题目）：审核设计质量，状态值 pass/needs_fix。\n"
        "检查点2（有题目+求解）：审核交付一致性，状态值 pass/expression_fix/question_error/solution_error。\n"
        "不写代码、不执行代码。"
    ),
}

# ── Shared instruction suffix ────────────────────────────────────

_WRITE_FILE_SUFFIX = (
    "\n\n产出文件：{filename}"
    "（可通过 write_file 工具写入，或直接输出完整Markdown内容由系统自动保存。）"
)

_RETRY_FEEDBACK = (
    "\n\n上一轮没有产生可保存的目标文件。"
    "请现在提交目标文件：可直接输出完整 Markdown 内容，"
    "也可调用 write_file(path=\"{filename}\", content=\"完整内容\")。"
)


# ── AgentMD dataclass ────────────────────────────────────────────

class AgentSpec:
    """Parsed representation of a single AgentMD file."""

    __slots__ = (
        "name", "phase", "description", "output_file",
        "required_sections", "status_values",
        "thinking_budget", "max_tokens", "model_routing",
        "multi_turn", "max_attempts", "inject_files",
        "required_tools",
        "behavior_type",  # create_verify / audit_judge / format_convert / plan_design
        "prompt",         # assembled system prompt (behavior core + variant + suffix)
        "skill_content",  # domain knowledge loaded from skills/ directory
    )

    def __init__(self, meta: dict[str, Any], body: str) -> None:
        self.name = meta["name"]
        self.phase = meta.get("phase", 0)
        self.description = meta.get("description", "")
        self.output_file = meta.get("output_file", "output.md")
        self.required_sections = meta.get("required_sections", [])
        self.status_values = meta.get("status_values", [])
        self.thinking_budget = meta.get("thinking_budget")
        self.max_tokens = meta.get("max_tokens")
        self.model_routing = meta.get("model_routing")
        self.multi_turn = meta.get("multi_turn", False)
        self.max_attempts = meta.get("max_attempts", 2)
        self.inject_files = meta.get("inject_files", [])
        self.required_tools = meta.get("required_tools", ["write_file"])
        self.behavior_type = _BEHAVIOR_VARIANTS.get(self.name, "plan_design")

        # Assemble system prompt: behavior core + identity + variant + write_file suffix
        variant_text = _BEHAVIOR_VARIANT_TEXT.get(self.behavior_type, "")
        suffix = _WRITE_FILE_SUFFIX.replace("{filename}", self.output_file)
        identity = body.strip() if body.strip() else ""
        if identity:
            self.prompt = _BEHAVIOR_CORE + "\n\n" + identity + "\n\n" + variant_text + suffix
        else:
            self.prompt = _BEHAVIOR_CORE + "\n" + variant_text + suffix

        # Skill content: loaded from skills/<behavior_type>/<name>_skill.md
        self.skill_content = self._load_skill()

    def _load_skill(self) -> str:
        """Load domain-specific skill content from the skills directory."""
        skill_path = _SKILLS_DIR / self.behavior_type / f"{self.name}_skill.md"
        if skill_path.exists():
            return skill_path.read_text(encoding="utf-8").strip()
        return ""


# ── Frontmatter parser ───────────────────────────────────────────

_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n(.*)",
    re.DOTALL,
)


def _parse_agent_md(path: Path) -> AgentSpec:
    """Parse a single AgentMD file into an AgentSpec."""
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"AgentMD file {path} has no valid YAML frontmatter")
    meta = yaml.safe_load(m.group(1))
    if not isinstance(meta, dict) or "name" not in meta:
        raise ValueError(f"AgentMD file {path} frontmatter missing 'name'")
    body = m.group(2)
    return AgentSpec(meta, body)


# ── Loader ───────────────────────────────────────────────────────

def load_agents(agents_dir: Path | str | None = None) -> dict[str, AgentSpec]:
    """Load all AgentMD files from the agents directory.

    Returns:
        dict mapping role name → AgentSpec
    """
    d = Path(agents_dir) if agents_dir else _AGENTS_DIR
    specs: dict[str, AgentSpec] = {}
    if not d.is_dir():
        logger.warning("AgentMD directory not found: %s", d)
        return specs
    for path in sorted(d.glob("*.md")):
        try:
            spec = _parse_agent_md(path)
            specs[spec.name] = spec
            logger.debug("Loaded agent: %s → %s", path.name, spec.name)
        except Exception as exc:
            logger.error("Failed to parse AgentMD %s: %s", path, exc)
    logger.info("Loaded %d AgentMD specs from %s", len(specs), d)
    return specs


def get_agent_dicts(
    agents_dir: Path | str | None = None,
) -> tuple[dict[str, str], dict[str, str], set[str], dict[str, int], dict[str, list[str]], dict[str, str]]:
    """Load AgentMD files and return the same dicts agents.py exported.

    System params (multi_turn, max_attempts, thinking_budget) are read from
    pipeline.yaml, not from agent MD frontmatter.

    Returns:
        (AGENT_PROMPTS, AGENT_OUTPUT_FILES, MULTI_TURN_AGENTS, ROLE_THINKING_BUDGET, ROLE_REQUIRED_TOOLS, ROLE_SKILLS)
    """
    from .pipeline_config import load_pipeline_config
    config = load_pipeline_config()
    role_params = config.params.roles

    specs = load_agents(agents_dir)
    prompts = {name: s.prompt for name, s in specs.items()}
    output_files = {name: s.output_file for name, s in specs.items()}

    # System params from pipeline.yaml
    multi_turn = {
        name for name in specs
        if role_params.get(name, {}).get("multi_turn", False)
    }
    thinking_budget = config.params.thinking_budget

    required_tools = {name: s.required_tools for name, s in specs.items()}
    skills = {name: s.skill_content for name, s in specs.items() if s.skill_content}
    return prompts, output_files, multi_turn, thinking_budget, required_tools, skills
