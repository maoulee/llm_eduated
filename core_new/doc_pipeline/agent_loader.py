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
    "你是一个工具调用智能体。按步骤执行任务，每步只做一件事。\n\n"
    "执行节奏：\n"
    "1. 读当前步骤要求 → 2. 调工具行动 → 3. 看返回结果 → 4. 决定下一步\n\n"
    "纪律：\n"
    "- 禁止在工具调用前完成全部推理\n"
    "- 文本生成 → 直接写，不反复斟酌\n\n"
    "输出：只通过 write_file 工具写入，禁止正文输出。"
)

_BEHAVIOR_VARIANTS = {
    "question": "question_create",
    "coding": "create_verify",
    "fix": "fix_verify",
    "analysis": "audit_judge",
    "review": "audit_fix",
    "design": "plan_design",
}

_BEHAVIOR_VARIANT_TEXT = {
    "question_create": (
        "你的模式是「深度思考知识设计→代码验证参数闭环→输出」。\n"
        "第1步（纯思考）：深入设计知识点覆盖、逻辑关联、题干表述、消除歧义，选参数但不验证数值。\n"
        "第2步（exec_python）：验证参数封闭性、推导路径等价、单位换算自洽，不计算最终答案。\n"
        "代码为王：参数不一致时以代码为准，改题干参数不改代码。只有审核指出题干问题时才修题干。\n"
        "顺序：思考设计 → exec_python验证参数闭环 → write_file输出。"
    ),
    "create_verify": (
        "你的模式是「大胆构造→代码验证→修正→输出」。"
        "数值计算直接写代码(exec_python)验证，不在脑内推演。"
        "快速选值→exec_python验证→write_file输出。"
    ),
    "fix_verify": (
        "你的模式是「判断修改级别→修正→输出」。"
        "措辞级问题：edit_file直接修改表述，不走代码校验。"
        "结构级问题：修改推理/参数后用exec_python重新校验参数闭环，以代码为准调整题干参数。"
        "代码为王：参数不一致改题干，不改代码。"
    ),
    "audit_judge": (
        "你的模式是「结构化审核→结论→输出」。"
        "按检查清单逐项判断，每项给结论不给推导。"
    ),
    "audit_fix": (
        "你的模式是「结构化审核→最小修复→输出」。"
        "按检查清单逐项判断，需要修复时用exec_python验证数值。"
        "审核结论或修复结果通过write_file输出。"
    ),
    "format_convert": (
        "你的模式是「读取→组装→输出」。"
        "原样搬运内容，不修改不增加不推理，直接组装后输出。"
    ),
    "plan_design": (
        "你的模式是「分析输入→构建框架→填充细节→输出」。"
        "先搭骨架再填充，不要一开始就写完整内容。"
    ),
}

# ── Shared instruction suffix ────────────────────────────────────

_WRITE_FILE_SUFFIX = (
    "\n\n【强制要求】你必须调用 write_file 工具将结果写入文件。"
    "禁止直接输出内容文本，必须通过 OpenAI tool_calls 字段调用 "
    "write_file(path=\"{filename}\", content=\"你的完整内容\") 完成输出。"
    "不要在工具调用之外输出任何正文内容；如果把 JSON 或函数调用写在正文里，系统会判定失败。"
)

_RETRY_FEEDBACK = (
    "\n\n【系统警告】你上一轮没有调用 write_file 工具写入文件。"
    "这次必须通过 OpenAI tool_calls 字段调用 write_file 工具，不要直接输出内容。"
    "调用格式：write_file(path=\"{filename}\", content=\"你的完整内容\")"
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

        # Assemble system prompt: behavior core + variant + write_file suffix
        variant_text = _BEHAVIOR_VARIANT_TEXT.get(self.behavior_type, "")
        suffix = _WRITE_FILE_SUFFIX.replace("{filename}", self.output_file)
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

    Returns:
        (AGENT_PROMPTS, AGENT_OUTPUT_FILES, MULTI_TURN_AGENTS, ROLE_THINKING_BUDGET, ROLE_REQUIRED_TOOLS, ROLE_SKILLS)
    """
    specs = load_agents(agents_dir)
    prompts = {name: s.prompt for name, s in specs.items()}
    output_files = {name: s.output_file for name, s in specs.items()}
    multi_turn = {name for name, s in specs.items() if s.multi_turn}
    thinking_budget = {
        name: s.thinking_budget
        for name, s in specs.items()
        if s.thinking_budget is not None
    }
    required_tools = {name: s.required_tools for name, s in specs.items()}
    skills = {name: s.skill_content for name, s in specs.items() if s.skill_content}
    return prompts, output_files, multi_turn, thinking_budget, required_tools, skills
