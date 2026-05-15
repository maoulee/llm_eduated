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

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from config import get_provider_config
from llm_providers_new import get_llm_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


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

    @classmethod
    def success(cls, *, content: str = "", reasoning: str = "",
                parsed_json: Optional[Dict[str, Any]] = None,
                provider: str, model: str, latency_ms: int, retries: int = 0) -> "LLMResult":
        return cls(ok=True, content=content or None, reasoning=reasoning or None,
                   parsed_json=parsed_json, error_code=None, error_message=None,
                   provider=provider, model=model, latency_ms=latency_ms, retries=retries)

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

    def __init__(self, provider_name: str):
        self._provider_name = provider_name
        self._config = get_provider_config(provider_name)
        self._provider = get_llm_provider(self._config)
        self._model_name = self._config.get("model_path", provider_name)
        logger.info("LLMGateway initialized: provider=%s model=%s", self._provider_name, self._model_name)

    @classmethod
    def from_provider(cls, provider, name: str = "wrapped") -> "LLMGateway":
        """Wrap an existing raw provider instance in a gateway."""
        instance = cls.__new__(cls)
        instance._provider_name = name
        instance._config = {}
        instance._provider = provider
        instance._model_name = name
        return instance

    # ── Batch methods ──────────────────────────────────────

    async def generate_json_batch(
        self, messages_batch: List[List[Dict]],
        max_tokens: Optional[int] = None, enable_thinking: bool = False,
    ) -> List[LLMResult]:
        if not messages_batch:
            return []

        start_time = time.monotonic()

        # Use raw batch if available (preserves json_mode + gives error visibility)
        has_raw = hasattr(self._provider, "_generate_raw_batch")

        try:
            if has_raw:
                raw_outputs = await self._provider._generate_raw_batch(
                    messages_batch=messages_batch, stop_sequences=None,
                    max_tokens=max_tokens, enable_thinking=enable_thinking, json_mode=True,
                )
            else:
                # Fallback: lose error visibility but keep JSON mode
                raw_dicts = await self._provider.generate_json_batch(
                    messages_batch=messages_batch, max_tokens=max_tokens,
                    enable_thinking=enable_thinking,
                )
                raw_outputs = None
        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("generate_json_batch failed: %s", e, exc_info=True)
            return [LLMResult.failure(
                error_code=_classify_exception(e), error_message=str(e),
                provider=self._provider_name, model=self._model_name, latency_ms=latency_ms,
            ) for _ in messages_batch]

        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Path A: raw batch — we see the content and can classify errors
        if raw_outputs is not None:
            return _pad([_process_json_raw(out, self._provider_name, self._model_name, latency_ms)
                         for out in raw_outputs], messages_batch, self._provider_name, self._model_name, latency_ms)

        # Path B: fallback from generate_json_batch — can't see underlying errors
        return _pad([_process_json_fallback(d, self._provider_name, self._model_name, latency_ms)
                     for d in raw_dicts], messages_batch, self._provider_name, self._model_name, latency_ms)

    async def generate_reasoned_batch(
        self, messages_batch: List[List[Dict]],
        max_tokens: Optional[int] = None, enable_thinking: bool = True,
    ) -> List[LLMResult]:
        if not messages_batch:
            return []

        start_time = time.monotonic()

        try:
            raw_results = await self._provider.generate_with_think_and_parse_batch(
                messages_batch=messages_batch, stop_sequences=None,
                enable_thinking=enable_thinking, max_token=max_tokens,
            )
        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("generate_reasoned_batch failed: %s", e, exc_info=True)
            return [LLMResult.failure(
                error_code=_classify_exception(e), error_message=str(e),
                provider=self._provider_name, model=self._model_name, latency_ms=latency_ms,
            ) for _ in messages_batch]

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

    async def generate_text_batch(
        self, messages_batch: List[List[Dict]],
        max_tokens: Optional[int] = None, enable_thinking: bool = False,
    ) -> List[LLMResult]:
        if not messages_batch:
            return []

        start_time = time.monotonic()

        try:
            raw_results = await self._provider.generate_with_think_and_parse_batch(
                messages_batch=messages_batch, enable_thinking=enable_thinking,
                max_token=max_tokens,
            )
        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("generate_text_batch failed: %s", e, exc_info=True)
            return [LLMResult.failure(
                error_code=_classify_exception(e), error_message=str(e),
                provider=self._provider_name, model=self._model_name, latency_ms=latency_ms,
            ) for _ in messages_batch]

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
        return "network_error"
    return "api_error"


def _classify_error_content(content: str) -> str:
    """Classify an 'Error: ...' content string from provider."""
    s = content.lower()
    if "timeout" in s or "timed out" in s:
        return "timeout"
    if "rate limit" in s or "429" in s:
        return "rate_limit"
    if "connection" in s or "network" in s:
        return "network_error"
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
