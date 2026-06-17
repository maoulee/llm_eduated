"""Shared configuration for the document pipeline.

Loads runtime defaults from config/pipeline.yaml (via pipeline_config.py),
then overlays AgentMD frontmatter values.  Downstream modules import
constants from here — the names stay stable regardless of the config source.
"""

from __future__ import annotations

from .agent_loader import get_agent_dicts
from .pipeline_config import load_pipeline_config

# Load YAML config once at module level.
_pipeline_cfg = load_pipeline_config()
_params = _pipeline_cfg.params

MAX_ANALYSIS_ITERATIONS = _params.max_analysis_iterations
MAX_AGENT_ATTEMPTS = _params.max_agent_attempts
DEFAULT_MAX_TOKENS = _params.default_max_tokens
DEFAULT_THINKING_BUDGET = _params.default_thinking_budget
PYTHON_EXEC_TIMEOUT = _params.python_exec_timeout

DOC_SAMPLING_OVERRIDES = {
    "temperature": _params.temperature,
    "top_p": _params.top_p,
}

# Load AgentMD files once at module level.
(
    AGENT_PROMPTS,
    AGENT_OUTPUT_FILES,
    MULTI_TURN_AGENTS,
    _LOADED_THINKING_BUDGET,
    ROLE_REQUIRED_TOOLS,
    ROLE_SKILLS,
) = get_agent_dicts()

# Per-role thinking budget (tokens). None = no cap.
# Priority: AgentMD frontmatter > YAML thinking_budget > hardcoded defaults.
ROLE_THINKING_BUDGET = {**_params.thinking_budget, **_LOADED_THINKING_BUDGET}

# Per-role 生成+思考配置（enable_thinking / max_tokens，来自 pipeline.yaml roles:）。
# scheduler 按 role 动态取用，None=用全局默认。这是 Qwen3.6 上唯一有效的"思考强度控制"
# （chat_template 只支持 enable_thinking 开关，不支持 thinking_budget 数值上限）。
ROLE_PARAMS = _params.roles

# Re-export the full config object for modules that need registry or routing.
PIPELINE_CONFIG = _pipeline_cfg
