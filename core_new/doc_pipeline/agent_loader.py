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
_BEHAVIOR_DIR = Path(__file__).parent / "behavior"

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
    "design": "artifact_writer",
    "exam_form": "artifact_writer",
    "question_design": "artifact_writer",
    "review": "audit_judge",
    "solve": "solve_create",
    "final_review": "final_review",
}

_BEHAVIOR_VARIANT_TEXT = {
    "audit_judge": (
        "你的模式是「结构化审核→结论→输出」。"
        "按检查清单逐项判断，每项给结论不给推导。"
        "此阶段无答案，不评估答案正确性，不审选项值，不算答案数值（code-as-truth：答案由 solve.py 执行确定）。"
        "form_gate 阶段选择题 question.md 无 A/B/C/D 选项值是正常的（选项由 solve 阶段组装），不得因此打回。"
    ),
    "solve_create": (
        "你的模式是「读题干→brief想解法→写解题代码→exec→fix代码→答案+solution」（§18/§19 求解即解题代码）。\n"
        "solve.py 是这道题的解题代码（非 DAG/参数搜索），你自己从题干写。exec 出错只改代码（绝不改题干，纪律②），快速迭代。\n"
        "exec 输出即真值，不重算、不质疑。只算正确答案，不算干扰值（干扰项由 design P2 给）。\n"
        "exec 报错 = 代码 bug（与逻辑/参数无关），内部循环 fix 直到通过，不冒泡不回退；反复修不好时编排层会清空你的上下文让你重跑。"
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

# ── Behavior file cache ──────────────────────────────────────────

_behavior_cache: dict[str, str] = {}


def _load_behavior_file(name: str) -> str:
    if name not in _behavior_cache:
        path = _BEHAVIOR_DIR / f"{name}.md"
        if path.exists():
            _behavior_cache[name] = path.read_text(encoding="utf-8").strip()
        else:
            _behavior_cache[name] = ""
    return _behavior_cache[name]


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
        "behavior",       # new: e.g. "artifact_writer" or None
        "skills",         # new: e.g. ["design_card_v1"] or []
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
        self.behavior = meta.get("behavior")
        self.skills = meta.get("skills", [])

        suffix = _WRITE_FILE_SUFFIX.replace("{filename}", self.output_file)
        self.prompt = self._build_prompt(body, suffix)

        # Skills: prefer new path if skills list is declared, else fall back to old path
        if self.skills:
            self.skill_content = self._load_skills_new()
        else:
            self.skill_content = self._load_skill()

    def _load_skill(self) -> str:
        """Load domain-specific skill content from the skills directory."""
        skill_path = _SKILLS_DIR / self.behavior_type / f"{self.name}_skill.md"
        if skill_path.exists():
            return skill_path.read_text(encoding="utf-8").strip()
        return ""

    def _load_skills_new(self) -> str:
        """Load skills from new path: skills/<skill_name>/SKILL.md"""
        parts = []
        for skill_name in self.skills:
            path = _SKILLS_DIR / skill_name / "SKILL.md"
            if path.exists():
                parts.append(path.read_text(encoding="utf-8").strip())
        return "\n\n".join(parts)

    def _build_prompt(self, body: str, suffix: str) -> str:
        if self.behavior is not None:
            core = _load_behavior_file("CORE")
            mode = _load_behavior_file(self.behavior)
            role = body.strip()
            # NOTE: skill content is intentionally NOT added here.
            # self.skill_content is returned by get_agent_dicts() as ROLE_SKILLS,
            # and the scheduler already injects it into the user message
            # (scheduler.py ROLE_SKILLS). Adding it to the system prompt too
            # caused the SKILL to be injected twice. Keep it in one place.
            parts = [p for p in [core, mode, role] if p]
            return "\n\n".join(parts) + suffix
        # Old path: _BEHAVIOR_CORE + identity + variant_text + suffix
        variant_text = _BEHAVIOR_VARIANT_TEXT.get(self.behavior_type, "")
        identity = body.strip() if body.strip() else ""
        if identity:
            return _BEHAVIOR_CORE + "\n\n" + identity + "\n\n" + variant_text + suffix
        return _BEHAVIOR_CORE + "\n" + variant_text + suffix


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
