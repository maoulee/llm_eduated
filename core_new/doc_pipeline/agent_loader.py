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

# ── Shared instruction suffix ────────────────────────────────────
# Placed at the end of every prompt for maximum model attention.

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
        "required_tools",  # list of tool names this agent needs
        "prompt",  # assembled system prompt (body + write_file suffix)
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
        # Assemble prompt: body + mandatory write_file suffix
        suffix = _WRITE_FILE_SUFFIX.replace("{filename}", self.output_file)
        self.prompt = body.strip() + suffix


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
) -> tuple[dict[str, str], dict[str, str], set[str], dict[str, int], dict[str, list[str]]]:
    """Load AgentMD files and return the same dicts agents.py exported.

    Returns:
        (AGENT_PROMPTS, AGENT_OUTPUT_FILES, MULTI_TURN_AGENTS, ROLE_THINKING_BUDGET, ROLE_REQUIRED_TOOLS)
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
    return prompts, output_files, multi_turn, thinking_budget, required_tools
