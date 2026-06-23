"""Dependency injection and singleton instances for the API layer."""

import os
import sys

# Ensure project root is in path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core_new.llm_gateway import LLMGateway
from interact.orchestrator import InteractiveOrchestrator
from config import get_provider_config
from api.event_bus import event_bus
from api.persistence import SessionStore

# Singleton instances
_gateway: LLMGateway | None = None
_orchestrator: InteractiveOrchestrator | None = None
_store: SessionStore | None = None


def get_store() -> SessionStore:
    """Get or create the singleton SessionStore instance."""
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


def get_gateway() -> LLMGateway:
    """Get or create the singleton LLMGateway instance."""
    global _gateway
    if _gateway is None:
        # Use local Qwen provider by default (vLLM)
        provider_name = os.getenv("EDUCATE_PROVIDER", "api_vllm")
        provider_cfg = get_provider_config(provider_name)
        _gateway = LLMGateway(provider_name)
    return _gateway


def get_orchestrator() -> InteractiveOrchestrator:
    """Get or create the singleton InteractiveOrchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        gateway = get_gateway()
        model_routing = {"paper_composer": os.getenv("COMPOSER_ROUTING", "local")}
        _orchestrator = InteractiveOrchestrator(
            gateway=gateway,
            model_routing=model_routing,
        )
    return _orchestrator
