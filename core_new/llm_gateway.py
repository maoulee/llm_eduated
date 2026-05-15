# core_new/llm_gateway.py

"""
Unified LLM Gateway - Single entry point for all LLM operations.

This module provides a clean, unified interface for LLM calls across the entire codebase.
It wraps the existing provider layer and adds structured error handling, latency tracking,
and consistent result formatting.

Usage:
    from core_new.llm_gateway import get_gateway

    gateway = get_gateway("glm5.1")
    results = await gateway.generate_json_batch(messages_batch)
    for result in results:
        if result.ok:
            print(f"Got {result.parsed_json}")
        else:
            print(f"Error: {result.error_message}")

Migration Guide:
    OLD: provider.generate_json_batch(messages) -> returns dict|None
    NEW: gateway.generate_json_batch(messages) -> returns LLMResult

    OLD: Check for None or "Error: " prefix in content
    NEW: Check result.ok flag and result.error_code
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from config import get_provider_config
from llm_providers_new import get_llm_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base error for all LLM operations."""

    def __init__(
        self,
        message: str,
        error_code: str = "llm_error",
        provider: str = "",
        model: str = "",
        detail: str = "",
    ):
        super().__init__(message)
        self.error_code = error_code
        self.provider = provider
        self.model = model
        self.detail = detail


class LLMTimeoutError(LLMError):
    """LLM request timed out."""

    def __init__(self, message: str, provider: str = "", model: str = "", detail: str = ""):
        super().__init__(message, error_code="timeout", provider=provider, model=model, detail=detail)


class LLMRateLimitError(LLMError):
    """LLM rate limit exceeded."""

    def __init__(self, message: str, provider: str = "", model: str = "", detail: str = ""):
        super().__init__(message, error_code="rate_limit", provider=provider, model=model, detail=detail)


class LLMParseError(LLMError):
    """Failed to parse LLM JSON response."""

    def __init__(self, message: str, provider: str = "", model: str = "", detail: str = ""):
        super().__init__(message, error_code="parse_error", provider=provider, model=model, detail=detail)


class LLMProtocolError(LLMError):
    """LLM provider returned an error in content."""

    def __init__(self, message: str, provider: str = "", model: str = "", detail: str = ""):
        super().__init__(message, error_code="protocol_error", provider=provider, model=model, detail=detail)


@dataclass
class LLMResult:
    """Unified result object for all LLM operations."""

    ok: bool
    content: Optional[str]
    reasoning: Optional[str]
    parsed_json: Optional[Dict[str, Any]]
    error_code: Optional[str]
    error_message: Optional[str]
    provider: str
    model: str
    latency_ms: int
    retries: int

    @classmethod
    def success(
        cls,
        *,
        content: str = "",
        reasoning: str = "",
        parsed_json: Optional[Dict[str, Any]] = None,
        provider: str,
        model: str,
        latency_ms: int,
        retries: int = 0,
    ) -> "LLMResult":
        return cls(
            ok=True,
            content=content or None,
            reasoning=reasoning or None,
            parsed_json=parsed_json,
            error_code=None,
            error_message=None,
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            retries=retries,
        )

    @classmethod
    def failure(
        cls,
        *,
        error_code: str,
        error_message: str,
        provider: str,
        model: str,
        latency_ms: int,
        content: str = "",
        reasoning: str = "",
        retries: int = 0,
    ) -> "LLMResult":
        return cls(
            ok=False,
            content=content or None,
            reasoning=reasoning or None,
            parsed_json=None,
            error_code=error_code,
            error_message=error_message,
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            retries=retries,
        )


class LLMGateway:
    """
    Unified gateway for all LLM operations.

    Wraps the existing provider layer with:
    - Structured error handling
    - Latency tracking
    - Consistent result formatting
    - Error detection from "Error: " prefixes
    """

    def __init__(self, provider_name: str):
        """
        Initialize the gateway with a provider configuration.

        Args:
            provider_name: Name of the provider (e.g., "glm5.1", "api_vllm")
        """
        self._provider_name = provider_name
        self._config = get_provider_config(provider_name)
        self._provider = get_llm_provider(self._config)
        self._model_name = self._config.get("model_path", provider_name)

        logger.info(
            "LLMGateway initialized: provider=%s model=%s",
            self._provider_name,
            self._model_name,
        )

    async def generate_json_batch(
        self,
        messages_batch: List[List[Dict]],
        max_tokens: Optional[int] = None,
        enable_thinking: bool = False,
    ) -> List[LLMResult]:
        """
        Generate structured JSON outputs for a batch of message lists.

        Args:
            messages_batch: List of message lists, each representing a conversation
            max_tokens: Optional max tokens per response
            enable_thinking: Whether to enable thinking mode

        Returns:
            List of LLMResult objects with parsed_json populated on success
        """
        if not messages_batch:
            return []

        start_time = time.monotonic()
        results = []

        try:
            raw_results = await self._provider.generate_json_batch(
                messages_batch=messages_batch,
                max_tokens=max_tokens,
                enable_thinking=enable_thinking,
            )
        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("generate_json_batch failed: %s", e, exc_info=True)
            error_code = self._classify_error(e)
            return [
                LLMResult.failure(
                    error_code=error_code,
                    error_message=str(e),
                    provider=self._provider_name,
                    model=self._model_name,
                    latency_ms=latency_ms,
                )
                for _ in messages_batch
            ]

        latency_ms = int((time.monotonic() - start_time) * 1000)

        for i, raw in enumerate(raw_results):
            if raw is None:
                results.append(
                    LLMResult.failure(
                        error_code="parse_error",
                        error_message="Provider returned None (JSON parse failed)",
                        provider=self._provider_name,
                        model=self._model_name,
                        latency_ms=latency_ms,
                    )
                )
            elif isinstance(raw, dict) and raw.get("content", "").startswith("Error:"):
                results.append(
                    LLMResult.failure(
                        error_code="protocol_error",
                        error_message=raw["content"],
                        provider=self._provider_name,
                        model=self._model_name,
                        latency_ms=latency_ms,
                        content=raw["content"],
                    )
                )
            else:
                results.append(
                    LLMResult.success(
                        parsed_json=raw,
                        provider=self._provider_name,
                        model=self._model_name,
                        latency_ms=latency_ms,
                    )
                )

        return results

    async def generate_reasoned_batch(
        self,
        messages_batch: List[List[Dict]],
        max_tokens: Optional[int] = None,
        enable_thinking: bool = True,
    ) -> List[LLMResult]:
        """
        Generate responses with reasoning/thinking for a batch of message lists.

        Args:
            messages_batch: List of message lists, each representing a conversation
            max_tokens: Optional max tokens per response
            enable_thinking: Whether to enable thinking mode (default True)

        Returns:
            List of LLMResult objects with reasoning and content fields populated
        """
        if not messages_batch:
            return []

        start_time = time.monotonic()
        results = []

        try:
            raw_results = await self._provider.generate_with_think_and_parse_batch(
                messages_batch=messages_batch,
                stop_sequences=None,
                enable_thinking=enable_thinking,
                max_token=max_tokens,
            )
        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("generate_reasoned_batch failed: %s", e, exc_info=True)
            error_code = self._classify_error(e)
            return [
                LLMResult.failure(
                    error_code=error_code,
                    error_message=str(e),
                    provider=self._provider_name,
                    model=self._model_name,
                    latency_ms=latency_ms,
                )
                for _ in messages_batch
            ]

        latency_ms = int((time.monotonic() - start_time) * 1000)

        for raw in raw_results:
            answer = raw.get("answer", "")
            think = raw.get("think", "")

            if answer.startswith("Error:"):
                results.append(
                    LLMResult.failure(
                        error_code="protocol_error",
                        error_message=answer,
                        provider=self._provider_name,
                        model=self._model_name,
                        latency_ms=latency_ms,
                        content=answer,
                        reasoning=think,
                    )
                )
            else:
                results.append(
                    LLMResult.success(
                        content=answer,
                        reasoning=think,
                        provider=self._provider_name,
                        model=self._model_name,
                        latency_ms=latency_ms,
                    )
                )

        return results

    async def generate_text_batch(
        self,
        messages_batch: List[List[Dict]],
        max_tokens: Optional[int] = None,
        enable_thinking: bool = False,
    ) -> List[LLMResult]:
        """
        Generate raw text responses for a batch of message lists.

        Args:
            messages_batch: List of message lists, each representing a conversation
            max_tokens: Optional max tokens per response
            enable_thinking: Whether to enable thinking mode

        Returns:
            List of LLMResult objects with content field populated (raw text)
        """
        if not messages_batch:
            return []

        start_time = time.monotonic()

        try:
            raw_results = await self._provider.generate_with_think_and_parse_batch(
                messages_batch=messages_batch,
                enable_thinking=enable_thinking,
                max_token=max_tokens,
            )
        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("generate_text_batch failed: %s", e, exc_info=True)
            error_code = self._classify_error(e)
            return [
                LLMResult.failure(
                    error_code=error_code,
                    error_message=str(e),
                    provider=self._provider_name,
                    model=self._model_name,
                    latency_ms=latency_ms,
                )
                for _ in messages_batch
            ]

        latency_ms = int((time.monotonic() - start_time) * 1000)

        results = []
        for raw in raw_results:
            content = raw.get("answer", "")
            reasoning = raw.get("think", "")

            if content.startswith("Error:"):
                results.append(
                    LLMResult.failure(
                        error_code="protocol_error",
                        error_message=content,
                        provider=self._provider_name,
                        model=self._model_name,
                        latency_ms=latency_ms,
                        content=content,
                        reasoning=reasoning or None,
                    )
                )
            else:
                results.append(
                    LLMResult.success(
                        content=content,
                        reasoning=reasoning or None,
                        provider=self._provider_name,
                        model=self._model_name,
                        latency_ms=latency_ms,
                    )
                )

        return results

    # ── Single-item convenience wrappers ──────────────────────

    async def generate_json(
        self,
        messages: List[Dict],
        max_tokens: Optional[int] = None,
        enable_thinking: bool = False,
    ) -> LLMResult:
        """Single-item wrapper for generate_json_batch."""
        results = await self.generate_json_batch(
            [messages], max_tokens=max_tokens, enable_thinking=enable_thinking,
        )
        return results[0]

    async def generate_reasoned(
        self,
        messages: List[Dict],
        max_tokens: Optional[int] = None,
        enable_thinking: bool = True,
    ) -> LLMResult:
        """Single-item wrapper for generate_reasoned_batch."""
        results = await self.generate_reasoned_batch(
            [messages], max_tokens=max_tokens, enable_thinking=enable_thinking,
        )
        return results[0]

    async def generate_text(
        self,
        messages: List[Dict],
        max_tokens: Optional[int] = None,
        enable_thinking: bool = False,
    ) -> LLMResult:
        """Single-item wrapper for generate_text_batch."""
        results = await self.generate_text_batch(
            [messages], max_tokens=max_tokens, enable_thinking=enable_thinking,
        )
        return results[0]

    def _classify_error(self, error: Exception) -> str:
        """Classify an exception into an error code."""
        error_str = str(error).lower()
        if "timeout" in error_str or "timed out" in error_str:
            return "timeout"
        if "rate limit" in error_str or "429" in error_str:
            return "rate_limit"
        if "json" in error_str or "parse" in error_str:
            return "parse_error"
        if "connection" in error_str or "network" in error_str:
            return "network_error"
        return "unknown_error"

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return self._provider_name

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model_name

    @property
    def raw_provider(self):
        """Access the underlying provider instance (for gradual migration only)."""
        return self._provider


def get_gateway(provider_name: str) -> LLMGateway:
    """
    Quick factory function to create an LLMGateway.

    Args:
        provider_name: Name of the provider (e.g., "glm5.1", "api_vllm")

    Returns:
        Initialized LLMGateway instance

    Example:
        gateway = get_gateway("glm5.1")
        results = await gateway.generate_json_batch(messages)
    """
    return LLMGateway(provider_name)
