# core_new/agent_router.py
"""Agent name -> LLMGateway router (thin layer).

Reads config/agents_llm.yaml. Per-agent thinking config is returned separately;
callers pass it into gateway.stream_chat(thinking_effort=...). This is the
canonical router for the agent pipeline going forward; provider_router.py
(role -> local/remote acceleration) is retained for legacy/experiments — there
is no local model in the current environment, so this layer routes to glm5.2
directly.
"""
from functools import lru_cache
from pathlib import Path

import yaml

from core_new.llm_gateway import get_gateway

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "agents_llm.yaml"


@lru_cache(maxsize=1)
def _load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _agent_cfg(agent_name: str) -> dict:
    cfg = _load_config()
    return cfg.get("agents", {}).get(agent_name, cfg.get("default", {}))


@lru_cache(maxsize=None)
def _gateway_for_provider(provider_name: str):
    """Single provider -> gateway cache (shared across all agents on that provider)."""
    return get_gateway(provider_name)


def get_gateway_for(agent_name: str):
    """Return the gateway bound to this agent's provider.

    Cached per PROVIDER name (not per agent), so all agents bound to the same provider
    (e.g. every agent on glm5.2) share one gateway/connection pool — per spec §3.4's
    cache-dedup requirement.
    """
    provider_name = _agent_cfg(agent_name)["provider"]
    return _gateway_for_provider(provider_name)


def get_thinking_config(agent_name: str) -> dict:
    """Return this agent's thinking config, e.g. {"enabled": bool, "effort": str}."""
    return _agent_cfg(agent_name).get("thinking", {})
