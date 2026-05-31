"""Provider Router — route agent roles to local (Qwen) or remote (GLM) providers.

Principle: local Qwen is an accelerator, not a hard dependency.
When unavailable, all agents fall back to the remote GLM provider.

Usage:
    from core_new.provider_router import get_routed_gateway

    gw = get_routed_gateway("review")   # local Qwen if available, else GLM
    gw = get_routed_gateway("solver")   # always GLM (generation task)
"""

import logging
import time
from typing import Optional

from core_new.llm_gateway import LLMGateway, get_gateway

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────

FALLBACK_PROVIDER = "glm5.1"
LOCAL_PROVIDER = "api_vllm"
HEALTH_CHECK_TTL = 60  # seconds to cache health check result

# Agent role → "local" (prefer Qwen) or "remote" (always GLM).
AGENT_ROUTING = {
    # All local — fast iteration with new coding-agent stem verifier
    "architecture":     "local",
    "sc_draft":         "local",
    "options":          "local",
    "design_comp":      "local",
    "solver":           "local",
    "paper_composer":   "local",
    "gate":             "local",
    "stem_verify":      "local",
    "review":           "local",
    "post_review":      "local",
    "rubric":           "local",
    "formatter":        "local",
    "summary":          "local",
    "blueprint_review": "local",
    "paper_review":     "local",
    "fixer":            "local",
    "minor_fix":        "local",
    "format_fix":       "local",
    "verify":           "local",
    "final_review":     "local",
    "final_fixer":      "local",
}

# ── Health Check ───────────────────────────────────────────────

_local_available: Optional[bool] = None
_last_health_check: float = 0


async def _check_local_available() -> bool:
    """Async health check: can we reach the local vLLM server?"""
    global _local_available, _last_health_check

    if _local_available is not None and (time.monotonic() - _last_health_check) < HEALTH_CHECK_TTL:
        return _local_available

    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get("http://localhost:8000/v1/models")
            _local_available = r.status_code == 200 and bool(r.json().get("data"))
    except Exception:
        _local_available = False

    _last_health_check = time.monotonic()
    status = "available" if _local_available else "unavailable"
    logger.info("Local provider health check: %s", status)
    return _local_available


def _check_local_available_sync() -> bool:
    """Sync health check for non-async contexts."""
    global _local_available, _last_health_check

    if _local_available is not None and (time.monotonic() - _last_health_check) < HEALTH_CHECK_TTL:
        return _local_available

    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:8000/v1/models")
        with urllib.request.urlopen(req, timeout=5) as resp:
            import json
            data = json.loads(resp.read())
            _local_available = bool(data.get("data"))
    except Exception:
        _local_available = False

    _last_health_check = time.monotonic()
    return _local_available


def clear_cache():
    """Clear health check and routing cache."""
    global _local_available, _last_health_check
    _local_available = None
    _last_health_check = 0


# ── Gateway Routing ────────────────────────────────────────────

_gateway_cache: dict[str, LLMGateway] = {}


def _get_or_create_gateway(provider_name: str) -> LLMGateway:
    if provider_name not in _gateway_cache:
        _gateway_cache[provider_name] = get_gateway(provider_name)
    return _gateway_cache[provider_name]


def get_routed_gateway(agent_role: str) -> LLMGateway:
    """Return the appropriate gateway for an agent role.

    Routes "local" roles to Qwen when available, otherwise falls back to GLM.
    """
    routing = AGENT_ROUTING.get(agent_role, "remote")

    if routing == "local" and _check_local_available_sync():
        logger.debug("Routing '%s' → local (api_vllm)", agent_role)
        return _get_or_create_gateway(LOCAL_PROVIDER)

    provider = FALLBACK_PROVIDER
    if routing == "local" and not _check_local_available_sync():
        logger.debug("Routing '%s' → %s (local unavailable, fallback)", agent_role, provider)
    return _get_or_create_gateway(provider)


async def get_routed_gateway_async(agent_role: str) -> LLMGateway:
    """Async variant — uses async health check."""
    routing = AGENT_ROUTING.get(agent_role, "remote")

    if routing == "local" and await _check_local_available():
        logger.debug("Routing '%s' → local (api_vllm)", agent_role)
        return _get_or_create_gateway(LOCAL_PROVIDER)

    provider = FALLBACK_PROVIDER
    logger.debug("Routing '%s' → %s", agent_role, provider)
    return _get_or_create_gateway(provider)
