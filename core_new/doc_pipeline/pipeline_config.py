"""Load and validate pipeline configuration from YAML.

Provides PipelineConfig dataclass with pipeline params, routing profiles,
and context registry. Falls back to hardcoded defaults when YAML is absent.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .context import (
    ContextRegistry,
    FileProvider,
    InlineProvider,
    ProviderDef,
)

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "pipeline.yaml"


@dataclass
class PipelineParams:
    max_analysis_iterations: int = 3
    max_agent_attempts: int = 30
    default_max_tokens: int = 20000
    default_thinking_budget: int = 10000
    python_exec_timeout: int = 30
    slot_concurrency: int = 2
    temperature: float = 0.2
    top_p: float = 0.9
    thinking_budget: dict[str, int] = field(default_factory=dict)


@dataclass
class RoutingProfile:
    role_routing: dict[str, str]      # role → "local"/"remote"
    model_routing: dict[str, str]     # role → provider name (for DocPipeline)
    default_routing: str = "local"    # fallback for roles not in role_routing


@dataclass
class PipelineConfig:
    params: PipelineParams
    routing_profiles: dict[str, RoutingProfile]
    default_profile: str
    context_registry: ContextRegistry
    fallback_provider: str
    local_provider: str
    health_check_ttl: int


def load_pipeline_config(path: str | Path | None = None) -> PipelineConfig:
    """Load full pipeline config from YAML file."""
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH
    if not config_path.exists():
        logger.info("Pipeline config not found at %s, using defaults", config_path)
        return _default_config()

    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    logger.info("Loaded pipeline config from %s", config_path)
    return _parse_config(raw)


def _parse_config(raw: dict) -> PipelineConfig:
    # 1. Pipeline params
    p = raw.get("pipeline", {})
    params = PipelineParams(
        max_analysis_iterations=p.get("max_analysis_iterations", 3),
        max_agent_attempts=p.get("max_agent_attempts", 30),
        default_max_tokens=p.get("default_max_tokens", 20000),
        default_thinking_budget=p.get("default_thinking_budget", 10000),
        python_exec_timeout=p.get("python_exec_timeout", 30),
        slot_concurrency=int(os.getenv(
            "PIPELINE_SLOT_CONCURRENCY", str(p.get("slot_concurrency", 2)),
        )),
        temperature=p.get("sampling", {}).get("temperature", 0.2),
        top_p=p.get("sampling", {}).get("top_p", 0.9),
        thinking_budget=p.get("thinking_budget", {}),
    )

    # 2. Routing
    r = raw.get("routing", {})
    providers = r.get("providers", {})
    fallback = providers.get("fallback", "glm5.1")
    local = providers.get("local", "api_vllm")
    ttl = providers.get("health_check_ttl", 60)

    profiles: dict[str, RoutingProfile] = {}
    for name, prof_raw in r.get("profiles", {}).items():
        default_val = prof_raw.get("_default", "local")
        role_routing: dict[str, str] = {}
        for k, v in prof_raw.items():
            if k in ("_default", "model_routing"):
                continue
            role_routing[k] = v

        model_routing_raw = prof_raw.get("model_routing", {})
        model_routing: dict[str, str] = {}
        for k, v in model_routing_raw.items():
            if isinstance(v, str):
                v = v.replace("{fallback}", fallback).replace("{local}", local)
            model_routing[k] = v

        profiles[name] = RoutingProfile(
            role_routing=role_routing,
            model_routing=model_routing,
            default_routing=default_val,
        )

    # 3. Context registry
    registry = _build_context_registry(raw.get("context_providers", {}))

    return PipelineConfig(
        params=params,
        routing_profiles=profiles,
        default_profile=r.get("default_profile", "all_local"),
        context_registry=registry,
        fallback_provider=fallback,
        local_provider=local,
        health_check_ttl=ttl,
    )


def _build_context_registry(cp_raw: dict) -> ContextRegistry:
    registry = ContextRegistry()

    for defn_raw in cp_raw.get("builtins", []):
        defn = ProviderDef(
            name=defn_raw["name"],
            type=defn_raw.get("type", "file"),
            label=defn_raw.get("label", defn_raw["name"]),
            phases=defn_raw.get("phases", []),
            optional=defn_raw.get("optional", False),
            path_pattern=defn_raw.get("path_pattern", ""),
        )
        if defn.type == "file":
            registry.register(FileProvider(defn))
        elif defn.type == "inline":
            registry.register(InlineProvider(defn))
        else:
            logger.warning("Unknown context provider type: %s", defn.type)

    for role, bindings in cp_raw.get("role_bindings", {}).items():
        registry.set_role_binding(role, bindings)

    return registry


def _default_config() -> PipelineConfig:
    """Fallback config matching current hardcoded values."""
    params = PipelineParams()
    registry = ContextRegistry()
    # Populate with the same bindings as the YAML
    for defn_raw in _DEFAULT_PROVIDERS:
        defn = ProviderDef(**defn_raw)
        if defn.type == "file":
            registry.register(FileProvider(defn))
        else:
            registry.register(InlineProvider(defn))
    for role, bindings in _DEFAULT_ROLE_BINDINGS.items():
        registry.set_role_binding(role, bindings)

    profiles = {
        name: RoutingProfile(
            role_routing=prof["_role_routing"],
            model_routing=prof["_model_routing"],
            default_routing=prof["_default_routing"],
        )
        for name, prof in _DEFAULT_PROFILES.items()
    }

    return PipelineConfig(
        params=params,
        routing_profiles=profiles,
        default_profile="all_local",
        context_registry=registry,
        fallback_provider="glm5.1",
        local_provider="api_vllm",
        health_check_ttl=60,
    )


# Default values for fallback when no YAML exists
_DEFAULT_PROVIDERS = [
    {"name": "assembled", "type": "file", "path_pattern": "{workspace}/{slot_id}/blueprint.md", "label": "规划", "phases": [2, 3, 5]},
    {"name": "question", "type": "file", "path_pattern": "{workspace}/{slot_id}/question.md", "label": "题目", "phases": [3, 5]},
    {"name": "question_public", "type": "file", "path_pattern": "{workspace}/{slot_id}/question_public.md", "label": "题目", "phases": [4]},
    {"name": "solution", "type": "file", "path_pattern": "{workspace}/{slot_id}/solution.md", "label": "求解结果", "phases": [5]},
    {"name": "solve_output", "type": "file", "path_pattern": "{workspace}/{slot_id}/solve_output.txt", "label": "代码输出", "phases": [5], "optional": True},
    {"name": "review_comments", "type": "file", "path_pattern": "{workspace}/{slot_id}/review.md", "label": "审核意见", "phases": [2], "optional": True},
    {"name": "experience_doc", "type": "inline", "label": "经验文档", "phases": [1], "optional": True},
    {"name": "k_definitions", "type": "inline", "label": "K值定义", "phases": [1], "optional": True},
]

_DEFAULT_ROLE_BINDINGS = {
    "outline": ["experience_doc", "k_definitions"],
    "question_sc": ["assembled", "review_comments"],
    "question_comp": ["assembled", "review_comments"],
    "review": ["assembled", "question"],
    "solve": ["question_public"],
    "final_review": ["assembled", "question", "solution", "solve_output"],
}

_DEFAULT_PROFILES = {
    "all_local": {"_role_routing": {}, "_model_routing": {}, "_default_routing": "local"},
    "all_remote": {"_role_routing": {}, "_model_routing": {}, "_default_routing": "remote"},
    "hybrid": {
        "_role_routing": {},
        "_model_routing": {
            "paper_composer": "hybrid",
            "question_sc": "hybrid",
            "question_comp": "hybrid",
            "solve": "hybrid",
            "review": "hybrid",
            "final_review": "hybrid",
        },
        "_default_routing": "local",
    },
}
