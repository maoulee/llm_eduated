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
# Lazy-loaded from PIPELINE_CONFIG (single source of truth)

_active_routing: dict[str, str] = {}
_default_routing: str = "remote"
_routing_initialized = False
_config_cache: dict | None = None


def _get_config() -> dict:
    """Get PIPELINE_CONFIG values with deferred import to avoid circular deps."""
    global _config_cache
    if _config_cache is None:
        from core_new.doc_pipeline.config import PIPELINE_CONFIG
        _config_cache = {
            "fallback_provider": PIPELINE_CONFIG.fallback_provider,
            "local_provider": PIPELINE_CONFIG.local_provider,
            "health_check_ttl": PIPELINE_CONFIG.health_check_ttl,
        }
    return _config_cache


def _discover_all_roles() -> set[str]:
    """Collect all unique role names from all routing profiles."""
    from core_new.doc_pipeline.config import PIPELINE_CONFIG
    roles: set[str] = set()
    for prof in PIPELINE_CONFIG.routing_profiles.values():
        roles.update(prof.role_routing.keys())
        if prof.model_routing:
            roles.update(prof.model_routing.keys())
    return roles


def _ensure_routing_initialized():
    """Initialize routing from PIPELINE_CONFIG default profile."""
    global _active_routing, _default_routing, _routing_initialized
    if _routing_initialized:
        return

    from core_new.doc_pipeline.config import PIPELINE_CONFIG

    default_profile = PIPELINE_CONFIG.default_profile
    prof = PIPELINE_CONFIG.routing_profiles.get(default_profile)
    if prof:
        _default_routing = prof.default_routing
        for role in _discover_all_roles():
            _active_routing[role] = prof.role_routing.get(role, prof.default_routing)
    _routing_initialized = True

# ── Health Check ───────────────────────────────────────────────

_local_available: Optional[bool] = None
_last_health_check: float = 0


async def _check_local_available() -> bool:
    """Async health check: can we reach the local vLLM server?"""
    global _local_available, _last_health_check

    cfg = _get_config()
    ttl = cfg["health_check_ttl"]
    if _local_available is not None and (time.monotonic() - _last_health_check) < ttl:
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

    cfg = _get_config()
    ttl = cfg["health_check_ttl"]
    if _local_available is not None and (time.monotonic() - _last_health_check) < ttl:
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
    _ensure_routing_initialized()
    cfg = _get_config()

    routing = _active_routing.get(agent_role, _default_routing)

    if routing == "local" and _check_local_available_sync():
        logger.debug("Routing '%s' → local (%s)", agent_role, cfg["local_provider"])
        return _get_or_create_gateway(cfg["local_provider"])

    provider = cfg["fallback_provider"]
    if routing == "local" and not _check_local_available_sync():
        logger.debug("Routing '%s' → %s (local unavailable, fallback)", agent_role, provider)
    return _get_or_create_gateway(provider)


# ── Routing Profiles (config-driven) ────────────────────────────────

def set_routing_profile(profile: str) -> dict[str, str] | None:
    """Set the routing profile for all agents.

    Returns a model_routing dict for DocPipeline (role → provider name),
    or None if no per-role override is needed.

    Profiles are loaded from config/pipeline.yaml. See routing.profiles section.
    """
    global _active_routing, _default_routing, _routing_initialized
    from core_new.doc_pipeline.config import PIPELINE_CONFIG

    prof = PIPELINE_CONFIG.routing_profiles.get(profile)
    if prof is None:
        raise ValueError(f"Unknown routing profile: {profile}")

    _default_routing = prof.default_routing
    for role in _discover_all_roles():
        _active_routing[role] = prof.role_routing.get(role, prof.default_routing)
    _routing_initialized = True
    clear_cache()
    logger.info("Routing profile: %s", profile)
    return prof.model_routing if prof.model_routing else None


async def get_routed_gateway_async(agent_role: str) -> LLMGateway:
    """Async variant — uses async health check."""
    _ensure_routing_initialized()
    cfg = _get_config()

    routing = _active_routing.get(agent_role, _default_routing)

    if routing == "local" and await _check_local_available():
        logger.debug("Routing '%s' → local (%s)", agent_role, cfg["local_provider"])
        return _get_or_create_gateway(cfg["local_provider"])

    provider = cfg["fallback_provider"]
    logger.debug("Routing '%s' → %s", agent_role, provider)
    return _get_or_create_gateway(provider)
