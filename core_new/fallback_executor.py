"""Pipeline-layer fallback execution when primary agents fail."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class FallbackResult:
    """Result of a fallback execution attempt."""
    used_fallback: bool
    fallback_target: str
    result_data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    latency_ms: int = 0


# Type: async function(blackboard_data) -> dict[str, Any]
FallbackHandler = Callable[..., Any]


class FallbackExecutor:
    """Execute role-specific fallbacks when primary agents fail.

    Pipelines register fallback handlers by target name. When an agent
    fails and fallback is enabled, the pipeline calls
    `fallback_executor.try_fallback(record, blackboard_data)`.
    """

    def __init__(self):
        self._handlers: dict[str, FallbackHandler] = {}

    def register(self, target: str, handler: FallbackHandler) -> None:
        """Register a fallback handler for a target name."""
        self._handlers[target] = handler

    async def try_fallback(
        self,
        failed_record,
        blackboard_data: dict[str, Any],
    ) -> FallbackResult:
        """Try to execute a fallback based on the failed record's metadata.

        Args:
            failed_record: AgentRecord from the failed primary agent.
            blackboard_data: Current blackboard state to pass to handler.

        Returns:
            FallbackResult indicating whether fallback was attempted and its result.
        """
        metadata = getattr(failed_record, "metadata", None) or {}
        fallback_info = metadata.get("fallback", {})

        if not fallback_info.get("enabled"):
            return FallbackResult(
                used_fallback=False,
                fallback_target="none",
            )

        target = fallback_info.get("target", "")
        original_error = fallback_info.get("original_error", "")

        handler = self._handlers.get(target)
        if handler is None:
            logger.warning(
                "No fallback handler registered for target=%s, original_error=%s",
                target, original_error,
            )
            return FallbackResult(
                used_fallback=False,
                fallback_target=target,
                error=f"no handler for target: {target}",
            )

        try:
            start = time.monotonic()
            result_data = await handler(blackboard_data)
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "Fallback succeeded: target=%s, latency=%dms",
                target, latency_ms,
            )
            return FallbackResult(
                used_fallback=True,
                fallback_target=target,
                result_data=result_data if isinstance(result_data, dict) else {"output": result_data},
                latency_ms=latency_ms,
            )
        except Exception as exc:
            logger.error(
                "Fallback failed: target=%s, error=%s",
                target, str(exc),
            )
            return FallbackResult(
                used_fallback=True,
                fallback_target=target,
                error=str(exc),
            )


# ── Built-in fallback handlers ─────────────────────────────────

async def human_review_handler(data: dict[str, Any]) -> dict[str, Any]:
    """Mark the item for human review. No actual execution."""
    return {
        "status": "needs_human_review",
        "reason": "Primary agent failed, routed to human review",
        "original_data": data,
    }


async def needs_human_check_handler(data: dict[str, Any]) -> dict[str, Any]:
    """Mark for human check (lighter than full review)."""
    return {
        "status": "needs_human_check",
        "reason": "Agent output requires human verification",
        "original_data": data,
    }


def create_default_executor() -> FallbackExecutor:
    """Create a FallbackExecutor with built-in handlers registered."""
    executor = FallbackExecutor()
    executor.register("human_review", human_review_handler)
    executor.register("needs_human_check", needs_human_check_handler)
    # Pipeline-specific handlers (legacy_generator, second_reasoner,
    # conservative_template, rule_based_router) should be registered
    # by the pipeline itself since they need access to specific agents.
    return executor
