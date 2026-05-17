# core_new/llm_gateway.py

"""
Unified LLM Gateway - Single entry point for all LLM operations.

Usage:
    from core_new.llm_gateway import get_gateway

    gateway = get_gateway("glm5.1")
    results = await gateway.generate_json_batch(messages_batch)
    for result in results:
        if result.ok:
            print(f"Got {result.parsed_json}")
        else:
            print(f"Error: {result.error_message}")

Migration:
    OLD: provider.generate_json_batch(messages) -> dict|None
    NEW: gateway.generate_json_batch(messages) -> LLMResult
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from config import get_provider_config
from core_new.agent_roles import TransportRetryPolicy
from llm_providers_new import get_llm_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Global concurrency control — all gateway instances share this semaphore
_MAX_CONCURRENCY = int(os.getenv("LLM_MAX_CONCURRENCY", "2"))
_concurrency_sem: Optional[asyncio.Semaphore] = None


def _get_sem() -> asyncio.Semaphore:
    global _concurrency_sem
    if _concurrency_sem is None:
        _concurrency_sem = asyncio.Semaphore(_MAX_CONCURRENCY)
    return _concurrency_sem


# ── Error hierarchy ────────────────────────────────────────

class LLMError(Exception):
    def __init__(self, message: str, error_code: str = "llm_error", provider: str = "", model: str = "", detail: str = ""):
        super().__init__(message)
        self.error_code = error_code
        self.provider = provider
        self.model = model
        self.detail = detail


class LLMTimeoutError(LLMError):
    def __init__(self, message: str, provider: str = "", model: str = "", detail: str = ""):
        super().__init__(message, error_code="timeout", provider=provider, model=model, detail=detail)


class LLMRateLimitError(LLMError):
    def __init__(self, message: str, provider: str = "", model: str = "", detail: str = ""):
        super().__init__(message, error_code="rate_limit", provider=provider, model=model, detail=detail)


class LLMParseError(LLMError):
    def __init__(self, message: str, provider: str = "", model: str = "", detail: str = ""):
        super().__init__(message, error_code="parse_error", provider=provider, model=model, detail=detail)


class LLMProtocolError(LLMError):
    def __init__(self, message: str, provider: str = "", model: str = "", detail: str = ""):
        super().__init__(message, error_code="protocol_error", provider=provider, model=model, detail=detail)


# ── Result type ────────────────────────────────────────────

@dataclass
class LLMResult:
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
    tokens_used: int = 0

    @classmethod
    def success(cls, *, content: str = "", reasoning: str = "",
                parsed_json: Optional[Dict[str, Any]] = None,
                provider: str, model: str, latency_ms: int, retries: int = 0,
                tokens_used: int = 0) -> "LLMResult":
        return cls(ok=True, content=content or None, reasoning=reasoning or None,
                   parsed_json=parsed_json, error_code=None, error_message=None,
                   provider=provider, model=model, latency_ms=latency_ms, retries=retries,
                   tokens_used=tokens_used)

    @classmethod
    def failure(cls, *, error_code: str, error_message: str,
                provider: str, model: str, latency_ms: int,
                content: str = "", reasoning: str = "", retries: int = 0) -> "LLMResult":
        return cls(ok=False, content=content or None, reasoning=reasoning or None,
                   parsed_json=None, error_code=error_code, error_message=error_message,
                   provider=provider, model=model, latency_ms=latency_ms, retries=retries)


# ── Gateway ────────────────────────────────────────────────

class LLMGateway:
    """
    Unified gateway for all LLM operations.

    Key guarantees:
    - Every batch method returns exactly len(messages_batch) LLMResult objects
    - Errors are classified (timeout, rate_limit, parse_error, api_error)
    - "Error:" prefix in provider content is detected and classified correctly
    """

    def __init__(self, provider_name: str, *, transport_retry: TransportRetryPolicy | None = None):
        self._provider_name = provider_name
        self._config = get_provider_config(provider_name)
        self._provider = get_llm_provider(self._config)
        self._model_name = self._config.get("model_path", provider_name)
        self._transport_retry = transport_retry or TransportRetryPolicy()
        logger.info("LLMGateway initialized: provider=%s model=%s max_attempts=%d",
                     self._provider_name, self._model_name, self._transport_retry.max_attempts)

    @classmethod
    def from_provider(cls, provider, name: str = "wrapped", *, transport_retry: TransportRetryPolicy | None = None) -> "LLMGateway":
        """Wrap an existing raw provider instance in a gateway."""
        instance = cls.__new__(cls)
        instance._provider_name = name
        instance._config = {}
        instance._provider = provider
        instance._model_name = name
        instance._transport_retry = transport_retry or TransportRetryPolicy()
        return instance

    # ── Retry helpers ──────────────────────────────────────

    def _should_retry(self, error_code: str) -> bool:
        """Check if an error code should be retried per transport policy."""
        ec = error_code.lower()
        if ec in self._transport_retry.not_retry_on:
            return False
        if ec in self._transport_retry.retry_on:
            return True
        # Default: network-adjacent errors retry, parse/validation don't
        if ec in ("network_error", "timeout", "rate_limit", "server_error", "connection_error"):
            return True
        return False

    async def _wait_with_backoff(self, attempt: int) -> None:
        """Exponential backoff with jitter."""
        base = min(2 ** attempt, 30)  # cap at 30s
        jitter = random.uniform(0, base * 0.5)
        delay = base + jitter
        logger.info("Transport retry attempt %d, waiting %.1fs", attempt + 1, delay)
        await asyncio.sleep(delay)

    # ── Batch methods ──────────────────────────────────────

    async def generate_json_batch(
        self, messages_batch: List[List[Dict]],
        max_tokens: Optional[int] = None, enable_thinking: bool = False,
    ) -> List[LLMResult]:
        if not messages_batch:
            return []

        last_error_code = None
        last_error_msg = None

        for attempt in range(self._transport_retry.max_attempts):
            async with _get_sem():
                start_time = time.monotonic()
                has_raw = hasattr(self._provider, "_generate_raw_batch")

                try:
                    if has_raw:
                        raw_outputs = await self._provider._generate_raw_batch(
                            messages_batch=messages_batch, stop_sequences=None,
                            max_tokens=max_tokens, enable_thinking=enable_thinking, json_mode=True,
                        )
                    else:
                        raw_dicts = await self._provider.generate_json_batch(
                            messages_batch=messages_batch, max_tokens=max_tokens,
                            enable_thinking=enable_thinking,
                        )
                        raw_outputs = None

                    latency_ms = int((time.monotonic() - start_time) * 1000)

                    if raw_outputs is not None:
                        return _pad([_process_json_raw(out, self._provider_name, self._model_name, latency_ms)
                                     for out in raw_outputs], messages_batch, self._provider_name, self._model_name, latency_ms)

                    return _pad([_process_json_fallback(d, self._provider_name, self._model_name, latency_ms)
                                 for d in raw_dicts], messages_batch, self._provider_name, self._model_name, latency_ms)

                except Exception as e:
                    latency_ms = int((time.monotonic() - start_time) * 1000)
                    error_code = _classify_exception(e)
                    last_error_code = error_code
                    last_error_msg = str(e)

                    if not self._should_retry(error_code) or attempt >= self._transport_retry.max_attempts - 1:
                        logger.error("generate_json_batch failed (attempt %d/%d): [%s] %s",
                                     attempt + 1, self._transport_retry.max_attempts, error_code, e)
                        return [LLMResult.failure(
                            error_code=error_code, error_message=str(e),
                            provider=self._provider_name, model=self._model_name,
                            latency_ms=latency_ms, retries=attempt,
                        ) for _ in messages_batch]

                    logger.warning("generate_json_batch retryable error (attempt %d/%d): [%s] %s",
                                   attempt + 1, self._transport_retry.max_attempts, error_code, e)
                    await self._wait_with_backoff(attempt)

        return [LLMResult.failure(
            error_code=last_error_code or "unknown", error_message=last_error_msg or "",
            provider=self._provider_name, model=self._model_name, latency_ms=0,
            retries=self._transport_retry.max_attempts - 1,
        ) for _ in messages_batch]

    async def generate_reasoned_batch(
        self, messages_batch: List[List[Dict]],
        max_tokens: Optional[int] = None, enable_thinking: bool = True,
    ) -> List[LLMResult]:
        if not messages_batch:
            return []

        last_error_code = None
        last_error_msg = None

        for attempt in range(self._transport_retry.max_attempts):
            async with _get_sem():
                start_time = time.monotonic()

                try:
                    raw_results = await self._provider.generate_with_think_and_parse_batch(
                        messages_batch=messages_batch, stop_sequences=None,
                        enable_thinking=enable_thinking, max_token=max_tokens,
                    )

                    latency_ms = int((time.monotonic() - start_time) * 1000)

                    results = []
                    for raw in raw_results:
                        answer = raw.get("answer", "")
                        think = raw.get("think", "")
                        if answer.startswith("Error:"):
                            results.append(LLMResult.failure(
                                error_code=_classify_error_content(answer), error_message=answer,
                                provider=self._provider_name, model=self._model_name,
                                latency_ms=latency_ms, content=answer, reasoning=think or None,
                            ))
                        else:
                            results.append(LLMResult.success(
                                content=answer, reasoning=think or None,
                                provider=self._provider_name, model=self._model_name, latency_ms=latency_ms,
                            ))

                    return _pad(results, messages_batch, self._provider_name, self._model_name, latency_ms)

                except Exception as e:
                    latency_ms = int((time.monotonic() - start_time) * 1000)
                    error_code = _classify_exception(e)
                    last_error_code = error_code
                    last_error_msg = str(e)

                    if not self._should_retry(error_code) or attempt >= self._transport_retry.max_attempts - 1:
                        logger.error("generate_reasoned_batch failed (attempt %d/%d): [%s] %s",
                                     attempt + 1, self._transport_retry.max_attempts, error_code, e)
                        return [LLMResult.failure(
                            error_code=error_code, error_message=str(e),
                            provider=self._provider_name, model=self._model_name,
                            latency_ms=latency_ms, retries=attempt,
                        ) for _ in messages_batch]

                    logger.warning("generate_reasoned_batch retryable error (attempt %d/%d): [%s] %s",
                                   attempt + 1, self._transport_retry.max_attempts, error_code, e)
                    await self._wait_with_backoff(attempt)

        return [LLMResult.failure(
            error_code=last_error_code or "unknown", error_message=last_error_msg or "",
            provider=self._provider_name, model=self._model_name, latency_ms=0,
            retries=self._transport_retry.max_attempts - 1,
        ) for _ in messages_batch]

    async def generate_text_batch(
        self, messages_batch: List[List[Dict]],
        max_tokens: Optional[int] = None, enable_thinking: bool = False,
    ) -> List[LLMResult]:
        if not messages_batch:
            return []

        last_error_code = None
        last_error_msg = None

        for attempt in range(self._transport_retry.max_attempts):
            async with _get_sem():
                start_time = time.monotonic()

                try:
                    raw_results = await self._provider.generate_with_think_and_parse_batch(
                        messages_batch=messages_batch, enable_thinking=enable_thinking,
                        max_token=max_tokens,
                    )

                    latency_ms = int((time.monotonic() - start_time) * 1000)

                    results = []
                    for raw in raw_results:
                        content = raw.get("answer", "")
                        reasoning = raw.get("think", "")
                        if content.startswith("Error:"):
                            results.append(LLMResult.failure(
                                error_code=_classify_error_content(content), error_message=content,
                                provider=self._provider_name, model=self._model_name,
                                latency_ms=latency_ms, content=content, reasoning=reasoning or None,
                            ))
                        else:
                            results.append(LLMResult.success(
                                content=content, reasoning=reasoning or None,
                                provider=self._provider_name, model=self._model_name, latency_ms=latency_ms,
                            ))

                    return _pad(results, messages_batch, self._provider_name, self._model_name, latency_ms)

                except Exception as e:
                    latency_ms = int((time.monotonic() - start_time) * 1000)
                    error_code = _classify_exception(e)
                    last_error_code = error_code
                    last_error_msg = str(e)

                    if not self._should_retry(error_code) or attempt >= self._transport_retry.max_attempts - 1:
                        logger.error("generate_text_batch failed (attempt %d/%d): [%s] %s",
                                     attempt + 1, self._transport_retry.max_attempts, error_code, e)
                        return [LLMResult.failure(
                            error_code=error_code, error_message=str(e),
                            provider=self._provider_name, model=self._model_name,
                            latency_ms=latency_ms, retries=attempt,
                        ) for _ in messages_batch]

                    logger.warning("generate_text_batch retryable error (attempt %d/%d): [%s] %s",
                                   attempt + 1, self._transport_retry.max_attempts, error_code, e)
                    await self._wait_with_backoff(attempt)

        return [LLMResult.failure(
            error_code=last_error_code or "unknown", error_message=last_error_msg or "",
            provider=self._provider_name, model=self._model_name, latency_ms=0,
            retries=self._transport_retry.max_attempts - 1,
        ) for _ in messages_batch]

    # ── Single-item convenience wrappers ──────────────────

    async def generate_json(self, messages: List[Dict], **kw) -> LLMResult:
        return (await self.generate_json_batch([messages], **kw))[0]

    async def generate_reasoned(self, messages: List[Dict], **kw) -> LLMResult:
        return (await self.generate_reasoned_batch([messages], **kw))[0]

    async def generate_text(self, messages: List[Dict], **kw) -> LLMResult:
        return (await self.generate_text_batch([messages], **kw))[0]

    # ── Properties ────────────────────────────────────────

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def raw_provider(self):
        return self._provider


# ── Helpers ────────────────────────────────────────────────

def _parse_json(raw: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    try:
        if "```json" in raw:
            clean = raw.split("```json\n", 1)[1].rsplit("```", 1)[0]
        else:
            s, e = raw.find("{"), raw.rfind("}")
            clean = raw[s:e + 1] if s != -1 and e != -1 else raw
        return json.loads(clean)
    except (json.JSONDecodeError, IndexError):
        return None


def _classify_exception(error: Exception) -> str:
    s = str(error).lower()
    if "timeout" in s or "timed out" in s:
        return "timeout"
    if "rate limit" in s or "429" in s:
        return "rate_limit"
    if "connection" in s or "network" in s:
        return "connection_error"
    if "server" in s or "500" in s or "502" in s or "503" in s:
        return "server_error"
    return "api_error"


def _classify_error_content(content: str) -> str:
    """Classify an 'Error: ...' content string from provider."""
    s = content.lower()
    if "timeout" in s or "timed out" in s:
        return "timeout"
    if "rate limit" in s or "429" in s:
        return "rate_limit"
    if "connection" in s or "network" in s:
        return "connection_error"
    if "server" in s or "500" in s or "502" in s or "503" in s:
        return "server_error"
    return "api_error"


def _process_json_raw(raw: Dict[str, Any], provider: str, model: str, latency_ms: int) -> LLMResult:
    """Process a raw output dict from _generate_raw_batch for JSON mode."""
    content = raw.get("content", "")
    reasoning = raw.get("reasoning_content", "")

    if content.startswith("Error:"):
        return LLMResult.failure(
            error_code=_classify_error_content(content), error_message=content,
            provider=provider, model=model, latency_ms=latency_ms,
            content=content, reasoning=reasoning or None,
        )

    parsed = _parse_json(content)
    if parsed is None:
        return LLMResult.failure(
            error_code="json_parse_error",
            error_message=f"JSON parse failed for content: {content[:200]}",
            provider=provider, model=model, latency_ms=latency_ms,
            content=content, reasoning=reasoning or None,
        )

    return LLMResult.success(
        parsed_json=parsed, provider=provider, model=model,
        latency_ms=latency_ms, content=content, reasoning=reasoning or None,
    )


def _process_json_fallback(raw: Optional[Dict], provider: str, model: str, latency_ms: int) -> LLMResult:
    """Process a result from provider.generate_json_batch (may be None)."""
    if raw is None:
        return LLMResult.failure(
            error_code="json_parse_or_api_error",
            error_message="Provider returned None (JSON parse failed or API error swallowed)",
            provider=provider, model=model, latency_ms=latency_ms,
        )
    if isinstance(raw, dict) and raw.get("content", "").startswith("Error:"):
        return LLMResult.failure(
            error_code=_classify_error_content(raw["content"]),
            error_message=raw["content"],
            provider=provider, model=model, latency_ms=latency_ms,
            content=raw["content"],
        )
    return LLMResult.success(parsed_json=raw, provider=provider, model=model, latency_ms=latency_ms)


def _pad(results: List[LLMResult], messages_batch: List, provider: str, model: str, latency_ms: int) -> List[LLMResult]:
    """Ensure results length matches messages_batch length."""
    expected = len(messages_batch)
    if len(results) == expected:
        return results
    if len(results) < expected:
        results.extend([
            LLMResult.failure(
                error_code="missing_result",
                error_message=f"Provider returned {len(results)}/{expected} results",
                provider=provider, model=model, latency_ms=latency_ms,
            )
            for _ in range(expected - len(results))
        ])
    return results[:expected]


def get_gateway(provider_name: str) -> LLMGateway:
    """Factory function to create an LLMGateway."""
    return LLMGateway(provider_name)
