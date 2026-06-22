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

import httpx
import openai

from config import get_provider_config
from core_new.agent_roles import TransportRetryPolicy
from llm_providers_new import get_llm_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Separate concurrency limits for local (vLLM) and remote (GLM) providers
_LOCAL_CONCURRENCY = int(os.getenv("LLM_LOCAL_CONCURRENCY", "10"))
_REMOTE_CONCURRENCY = int(os.getenv("LLM_REMOTE_CONCURRENCY", "5"))
_RETRYABLE_HTTP_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
_local_sem: Optional[asyncio.Semaphore] = None
_remote_sem: Optional[asyncio.Semaphore] = None


def _get_local_sem() -> asyncio.Semaphore:
    global _local_sem
    if _local_sem is None:
        _local_sem = asyncio.Semaphore(_LOCAL_CONCURRENCY)
    return _local_sem


def _get_remote_sem() -> asyncio.Semaphore:
    global _remote_sem
    if _remote_sem is None:
        _remote_sem = asyncio.Semaphore(_REMOTE_CONCURRENCY)
    return _remote_sem


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
        # Determine scope: local (vLLM) vs remote (cloud API)
        self._is_local = provider_name in ("api_vllm", "vllm") or "vllm" in provider_name.lower()
        logger.info("LLMGateway initialized: provider=%s model=%s scope=%s max_attempts=%d",
                    self._provider_name, self._model_name,
                    "local" if self._is_local else "remote",
                    self._transport_retry.max_attempts)

    @classmethod
    def from_provider(cls, provider, name: str = "wrapped", *, transport_retry: TransportRetryPolicy | None = None) -> "LLMGateway":
        """Wrap an existing raw provider instance in a gateway."""
        instance = cls.__new__(cls)
        instance._provider_name = name
        instance._config = {}
        instance._provider = provider
        instance._model_name = name
        instance._transport_retry = transport_retry or TransportRetryPolicy()
        instance._is_local = "vllm" in name.lower()
        return instance

    # ── Retry helpers ──────────────────────────────────────

    def _get_sem(self) -> asyncio.Semaphore:
        """Return the appropriate semaphore for this gateway's scope."""
        return _get_local_sem() if self._is_local else _get_remote_sem()

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
        """Fixed 3s backoff."""
        logger.info("Transport retry attempt %d, waiting 3.0s", attempt + 1)
        await asyncio.sleep(3.0)

    # ── Batch methods ──────────────────────────────────────

    @staticmethod
    def _floor_max_tokens(max_tokens: Optional[int], enable_thinking: bool) -> Optional[int]:
        return max_tokens

    async def generate_json_batch(
        self, messages_batch: List[List[Dict]],
        max_tokens: Optional[int] = None, enable_thinking: bool = False,
    ) -> List[LLMResult]:
        if not messages_batch:
            return []

        max_tokens = self._floor_max_tokens(max_tokens, enable_thinking)
        last_error_code = None
        last_error_msg = None

        for attempt in range(self._transport_retry.max_attempts):
            async with self._get_sem():
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
                        results = [_process_json_raw(out, self._provider_name, self._model_name, latency_ms)
                                   for out in raw_outputs]
                    else:
                        results = [_process_json_fallback(d, self._provider_name, self._model_name, latency_ms)
                                   for d in raw_dicts]

                    has_retryable = any(
                        not r.ok and self._should_retry(r.error_code or "")
                        for r in results
                    )
                    if has_retryable and attempt < self._transport_retry.max_attempts - 1:
                        retry_codes = {r.error_code for r in results if not r.ok and self._should_retry(r.error_code or "")}
                        logger.warning("generate_json_batch content error retryable (attempt %d/%d): [%s]",
                                       attempt + 1, self._transport_retry.max_attempts, ",".join(retry_codes))
                        await self._wait_with_backoff(attempt)
                        continue

                    return _pad(results, messages_batch, self._provider_name, self._model_name, latency_ms)

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

        max_tokens = self._floor_max_tokens(max_tokens, enable_thinking)
        last_error_code = None
        last_error_msg = None

        for attempt in range(self._transport_retry.max_attempts):
            async with self._get_sem():
                start_time = time.monotonic()

                try:
                    raw_results = await self._provider.generate_with_think_and_parse_batch(
                        messages_batch=messages_batch, stop_sequences=None,
                        enable_thinking=enable_thinking, max_token=max_tokens,
                    )

                    latency_ms = int((time.monotonic() - start_time) * 1000)

                    results = []
                    has_retryable_content_error = False
                    content_error_code = None
                    for raw in raw_results:
                        answer = raw.get("answer", "")
                        think = raw.get("think", "")
                        if answer.startswith("Error:"):
                            ec = _classify_error_content(answer)
                            results.append(LLMResult.failure(
                                error_code=ec, error_message=answer,
                                provider=self._provider_name, model=self._model_name,
                                latency_ms=latency_ms, content=answer, reasoning=think or None,
                            ))
                            if self._should_retry(ec):
                                has_retryable_content_error = True
                                content_error_code = ec
                        else:
                            results.append(LLMResult.success(
                                content=answer, reasoning=think or None,
                                provider=self._provider_name, model=self._model_name, latency_ms=latency_ms,
                            ))

                    if has_retryable_content_error and attempt < self._transport_retry.max_attempts - 1:
                        logger.warning("generate_reasoned_batch content error retryable (attempt %d/%d): [%s]",
                                       attempt + 1, self._transport_retry.max_attempts, content_error_code)
                        await self._wait_with_backoff(attempt)
                        continue

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

        max_tokens = self._floor_max_tokens(max_tokens, enable_thinking)
        last_error_code = None
        last_error_msg = None

        for attempt in range(self._transport_retry.max_attempts):
            async with self._get_sem():
                start_time = time.monotonic()

                try:
                    raw_results = await self._provider.generate_with_think_and_parse_batch(
                        messages_batch=messages_batch, enable_thinking=enable_thinking,
                        max_token=max_tokens,
                    )

                    latency_ms = int((time.monotonic() - start_time) * 1000)

                    results = []
                    has_retryable_content_error = False
                    content_error_code = None
                    for raw in raw_results:
                        content = raw.get("answer", "")
                        reasoning = raw.get("think", "")
                        if content.startswith("Error:"):
                            ec = _classify_error_content(content)
                            results.append(LLMResult.failure(
                                error_code=ec, error_message=content,
                                provider=self._provider_name, model=self._model_name,
                                latency_ms=latency_ms, content=content, reasoning=reasoning or None,
                            ))
                            if self._should_retry(ec):
                                has_retryable_content_error = True
                                content_error_code = ec
                        else:
                            results.append(LLMResult.success(
                                content=content, reasoning=reasoning or None,
                                provider=self._provider_name, model=self._model_name, latency_ms=latency_ms,
                            ))

                    if has_retryable_content_error and attempt < self._transport_retry.max_attempts - 1:
                        logger.warning("generate_text_batch content error retryable (attempt %d/%d): [%s]",
                                       attempt + 1, self._transport_retry.max_attempts, content_error_code)
                        await self._wait_with_backoff(attempt)
                        continue

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

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: Optional[int] = None,
        enable_thinking: Optional[bool] = None,
        thinking_budget: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        sampling_overrides: Optional[Dict[str, Any]] = None,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """Run one streaming chat request through the shared gateway policy.

        This is the common infrastructure path for agent-style streaming calls:
        provider message preparation, local/remote concurrency limits, transport
        retries, retryable error classification, and provider-specific extension
        filtering all live here.  Orchestrators should vary prompts, sampling,
        tools, and routing, not reimplement transport behavior.
        """
        provider = self._provider
        max_tokens = self._floor_max_tokens(max_tokens, bool(enable_thinking))
        params = self._build_chat_params(
            provider,
            messages,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
            thinking_budget=thinking_budget,
            tools=tools,
            tool_choice=tool_choice,
            sampling_overrides=sampling_overrides,
            json_mode=json_mode,
            stream=True,
        )

        last_exc: Exception | None = None
        attempts = max(1, self._transport_retry.max_attempts)
        for attempt in range(attempts):
            async with self._get_sem():
                try:
                    return await self._read_chat_stream(provider, params)
                except Exception as exc:
                    if not self._is_retryable_stream_error(exc) or attempt >= attempts - 1:
                        raise
                    last_exc = exc

            await self._wait_with_backoff(attempt)

        raise last_exc or RuntimeError("stream_chat failed without an exception")

    def _build_chat_params(
        self,
        provider,
        messages: List[Dict[str, Any]],
        *,
        max_tokens: Optional[int],
        enable_thinking: Optional[bool],
        thinking_budget: Optional[int],
        tools: Optional[List[Dict[str, Any]]],
        tool_choice: Optional[Any],
        sampling_overrides: Optional[Dict[str, Any]],
        json_mode: bool,
        stream: bool,
    ) -> Dict[str, Any]:
        if enable_thinking is not None and hasattr(provider, "_prepare_messages"):
            processed = provider._prepare_messages(
                messages,
                enable_thinking=enable_thinking,
                json_mode=json_mode,
            )
        else:
            processed = list(messages)

        sampling = {k: v for k, v in getattr(provider, "sampling_params", {}).items() if k != "top_k"}
        if sampling_overrides:
            sampling.update({k: v for k, v in sampling_overrides.items() if v is not None})

        params: Dict[str, Any] = {
            "model": provider.model_name,
            "messages": processed,
            "stream": stream,
            **sampling,
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        if json_mode and getattr(provider, "supports_response_format", False):
            params["response_format"] = {"type": "json_object"}
        if tools:
            params["tools"] = tools
        if tool_choice and tools:
            params["tool_choice"] = tool_choice

        if thinking_budget and self._supports_thinking_budget(provider):
            params.setdefault("extra_body", {})
            params["extra_body"]["thinking_token_budget"] = thinking_budget
            # Thinking models count reasoning tokens against max_tokens.
            # Inflate output budget so reasoning doesn't consume it entirely.
            current_max = params.get("max_tokens", 0)
            if current_max and current_max > 0:
                params["max_tokens"] = max(current_max, thinking_budget + 16000)

        if enable_thinking is not None and hasattr(provider, "_extra_body_for_thinking"):
            extra_body = provider._extra_body_for_thinking(enable_thinking)
            if extra_body:
                params.setdefault("extra_body", {}).update(extra_body)

        return params

    async def _read_chat_stream(self, provider, params: Dict[str, Any]) -> Dict[str, Any]:
        content_parts: List[str] = []
        reasoning_parts: List[str] = []
        tool_calls_accum: Dict[int, Dict[str, str]] = {}
        finish_reason: str | None = None

        logger.debug(
            "[stream_chat] provider=%s model=%s tool_choice=%s tools=%d max_tokens=%s",
            self._provider_name,
            params.get("model"),
            params.get("tool_choice"),
            len(params.get("tools", [])),
            params.get("max_tokens"),
        )

        stream = await provider.client.chat.completions.create(**params)
        _chunk_count = 0
        _last_monitor = 0
        async for chunk in stream:
            _chunk_count += 1
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta

            # Monitor: log every 50 chunks to detect stuck streams
            if _chunk_count - _last_monitor >= 50:
                _last_monitor = _chunk_count
                logger.info(
                    "[stream_chat] streaming... chunks=%d reasoning=%d content=%d provider=%s",
                    _chunk_count, sum(len(p) for p in reasoning_parts), sum(len(p) for p in content_parts),
                    self._provider_name,
                )

            if choice.finish_reason:
                finish_reason = choice.finish_reason

            if delta.content:
                content_parts.append(delta.content)

            reasoning = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None) or ""
            if reasoning:
                reasoning_parts.append(reasoning)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_accum:
                        tool_calls_accum[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        tool_calls_accum[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_accum[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_accum[idx]["arguments"] += tc_delta.function.arguments

        tool_calls = None
        if tool_calls_accum:
            tool_calls = []
            for idx in sorted(tool_calls_accum):
                tc = tool_calls_accum[idx]
                tool_calls.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                })

        content = "".join(content_parts)
        reasoning_content = "".join(reasoning_parts)
        logger.info(
            "[stream_chat] provider=%s content=%d reasoning=%d tool_calls=%s finish_reason=%s",
            self._provider_name,
            len(content),
            len(reasoning_content),
            len(tool_calls) if tool_calls else 0,
            finish_reason,
        )
        return {
            "content": content,
            "reasoning_content": reasoning_content,
            "tool_calls": tool_calls,
            "finish_reason": finish_reason,
        }

    @staticmethod
    def _supports_thinking_budget(provider) -> bool:
        method = getattr(provider, "thinking_control_method", "")
        base_url = str(getattr(provider, "api_base_url", "")).lower()
        provider_type = getattr(provider, "provider_type", "")
        return (
            provider_type == "local"
            or method == "chat_template_kwargs"
            or "127.0.0.1" in base_url
            or "localhost" in base_url
        )

    @staticmethod
    def _is_retryable_stream_error(exc: Exception) -> bool:
        # OpenAI SDK exceptions (APITimeoutError inherits APIConnectionError, order matters)
        if isinstance(exc, (
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.RateLimitError,
            openai.InternalServerError,
        )):
            return True

        if isinstance(exc, (
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.PoolTimeout,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            ConnectionError,
            OSError,
        )):
            return True

        status_code = getattr(exc, "status_code", None)
        response = getattr(exc, "response", None)
        if status_code is None and response is not None:
            status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int):
            return status_code in _RETRYABLE_HTTP_STATUS or status_code >= 500

        name = exc.__class__.__name__.lower()
        return any(
            marker in name
            for marker in ("timeout", "connection", "ratelimit", "rate_limit")
        )

    async def generate_with_tools(
        self,
        messages: List[Dict],
        *,
        tools: List[Dict[str, Any]],
        tool_executor: Any,
        max_tokens: Optional[int] = None,
        enable_thinking: bool = True,
        max_rounds: int = 10,
        max_tool_calls: int = 0,
        tool_choice: Optional[Any] = None,
    ) -> LLMResult:
        """Generate with tool-calling loop.

        The LLM can call tools multiple rounds. Each round:
        1. Send messages + tools to LLM
        2. If response has tool_calls, execute them and append results
        3. If response has content, return as final result

        Budget controls:
        - max_rounds: max conversation turns with the LLM
        - max_tool_calls: max total tool invocations (0 = unlimited)
        - Circuit breaker: same tool + same args twice → inject stop message
        """
        max_tokens = self._floor_max_tokens(max_tokens, enable_thinking)
        conversation = list(messages)
        total_latency = 0
        tool_call_count = 0
        seen_calls: Dict[str, int] = {}  # (tool_name + args_hash) → count
        tool_name_counts: Dict[str, int] = {}  # tool_name → total call count
        total_circuit_breaks = [0]  # mutable counter for circuit breaker triggers

        for round_idx in range(max_rounds):
            # Early exit if too many circuit breaker triggers
            if total_circuit_breaks[0] >= 4:
                logger.warning(
                    "[generate_with_tools] Circuit breaker budget exhausted (%d breaks), forcing output",
                    total_circuit_breaks[0],
                )
                break

            start_time = time.monotonic()
            try:
                raw = await self._chat_call_with_policy(
                    conversation,
                    stop_sequences=None,
                    max_tokens=max_tokens,
                    enable_thinking=enable_thinking,
                    json_mode=False,
                    tools=tools,
                    tool_choice=tool_choice,
                )
            except Exception as e:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                return LLMResult.failure(
                    error_code="api_error",
                    error_message=str(e),
                    provider=self._provider_name,
                    model=self._model_name,
                    latency_ms=latency_ms,
                )

            latency_ms = int((time.monotonic() - start_time) * 1000)
            total_latency += latency_ms

            tool_calls = raw.get("tool_calls")
            content = raw.get("content", "")
            if content.startswith("Error:"):
                error_code = _classify_error_content(content)
                return LLMResult.failure(
                    error_code=error_code,
                    error_message=content,
                    provider=self._provider_name,
                    model=self._model_name,
                    latency_ms=total_latency,
                    content=content,
                )

            if tool_calls:
                # Build assistant message with tool_calls
                assistant_msg = {"role": "assistant", "content": content or None}
                assistant_msg["tool_calls"] = tool_calls
                conversation.append(assistant_msg)

                # Execute each tool call and append results
                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args_str = tc["function"]["arguments"]
                    try:
                        fn_args = json.loads(fn_args_str) if isinstance(fn_args_str, str) else fn_args_str
                    except json.JSONDecodeError:
                        fn_args = {}

                    # Budget check
                    tool_call_count += 1
                    if max_tool_calls > 0 and tool_call_count > max_tool_calls:
                        logger.warning(
                            "[generate_with_tools] Tool budget exhausted (%d/%d), forcing output",
                            tool_call_count - 1, max_tool_calls,
                        )
                        conversation.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": "工具调用次数已达上限。请立即基于已有信息输出最终结果，不要再调用工具。",
                        })
                        # Force one more LLM turn to get the final output
                        force_raw = await self._chat_call_with_policy(
                            conversation,
                            stop_sequences=None,
                            max_tokens=max_tokens,
                            enable_thinking=enable_thinking,
                            json_mode=False,
                            tools=[],  # No more tools
                        )
                        force_latency = int((time.monotonic() - start_time) * 1000)
                        total_latency += force_latency
                        force_content = force_raw.get("content", "")
                        if force_content.startswith("Error:"):
                            error_code = _classify_error_content(force_content)
                            return LLMResult.failure(
                                error_code=error_code,
                                error_message=force_content,
                                provider=self._provider_name,
                                model=self._model_name,
                                latency_ms=total_latency,
                                content=force_content,
                            )
                        force_reasoning = force_raw.get("reasoning") or force_raw.get("reasoning_content", "")
                        return LLMResult.success(
                            content=force_content,
                            reasoning=force_reasoning or None,
                            provider=self._provider_name,
                            model=self._model_name,
                            latency_ms=total_latency,
                        )

                    # Circuit breaker: detect repeated calls (same args or same tool name)
                    args_key = f"{fn_name}:{json.dumps(fn_args, sort_keys=True)}"
                    seen_calls[args_key] = seen_calls.get(args_key, 0) + 1
                    tool_name_counts[fn_name] = tool_name_counts.get(fn_name, 0) + 1

                    # Hard stop: same tool name called 5+ times → force return
                    if tool_name_counts[fn_name] >= 5:
                        logger.warning(
                            "[generate_with_tools] Circuit breaker HARD STOP: %s called %d times, forcing output",
                            fn_name, tool_name_counts[fn_name],
                        )
                        conversation.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps({"ok": True, "note": "工具调用已达上限，请立即输出最终结果。"}),
                        })
                        # Continue to let the model see this response and produce final output
                        # but if it tries to call tools again next round, the outer loop
                        # will catch it via total_circuit_breaks below.
                        total_circuit_breaks[0] += 1
                        continue

                    # Soft stop: same exact args called 2+ times → inject warning
                    if seen_calls[args_key] >= 2:
                        logger.warning(
                            "[generate_with_tools] Circuit breaker: %s called %d times with same args",
                            fn_name, seen_calls[args_key],
                        )
                        conversation.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": (
                                f"你已经用相同参数调用了 {fn_name} {seen_calls[args_key]} 次，结果不会改变。"
                                "请立即基于已有信息输出最终结果，停止调用工具。"
                            ),
                        })
                        total_circuit_breaks[0] += 1
                        if total_circuit_breaks[0] >= 3:
                            logger.warning("[generate_with_tools] Too many circuit breaks (%d), forcing final output",
                                           total_circuit_breaks[0])
                        continue

                    logger.info("[generate_with_tools] Executing tool: %s(%s)", fn_name, str(fn_args)[:100])
                    result_str = await tool_executor.execute(fn_name, fn_args)
                    logger.info("[generate_with_tools] Tool %s done, result_len=%d", fn_name, len(result_str))
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result_str,
                    })
                # Continue loop — LLM will see tool results and respond
                continue

            # No tool calls — this is the final content
            logger.info("[generate_with_tools] Final content len=%d, reasoning len=%d, rounds=%d, tool_calls=%d",
                        len(content or ""), len(raw.get("reasoning") or raw.get("reasoning_content") or ""), round_idx + 1, tool_call_count)
            reasoning = raw.get("reasoning") or raw.get("reasoning_content", "")
            return LLMResult.success(
                content=content,
                reasoning=reasoning or None,
                provider=self._provider_name,
                model=self._model_name,
                latency_ms=total_latency,
            )

        # Exhausted max rounds — return last content
        return LLMResult.failure(
            error_code="max_tool_rounds",
            error_message=f"Exceeded {max_rounds} tool-call rounds",
            provider=self._provider_name,
            model=self._model_name,
            latency_ms=total_latency,
            content=content,
        )

    async def _chat_call_with_policy(
        self,
        messages: List[Dict[str, Any]],
        *,
        stop_sequences: Optional[List[str]] = None,
        max_tokens: Optional[int] = None,
        enable_thinking: bool = True,
        json_mode: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Run provider._chat_call through gateway concurrency and retry policy."""
        attempts = max(1, self._transport_retry.max_attempts)
        last_error: Exception | None = None
        last_error_content = ""

        for attempt in range(attempts):
            retry_error_code: str | None = None
            async with self._get_sem():
                try:
                    raw = await self._provider._chat_call(
                        messages,
                        stop_sequences=stop_sequences,
                        max_tokens=max_tokens,
                        enable_thinking=enable_thinking,
                        json_mode=json_mode,
                        tools=tools,
                        tool_choice=tool_choice,
                    )
                except Exception as exc:
                    error_code = _classify_exception(exc)
                    if not self._should_retry(error_code) or attempt >= attempts - 1:
                        raise
                    last_error = exc
                    retry_error_code = error_code

            if retry_error_code:
                logger.warning(
                    "_chat_call retryable error (attempt %d/%d): [%s] %s",
                    attempt + 1,
                    attempts,
                    retry_error_code,
                    last_error,
                )
                await self._wait_with_backoff(attempt)
                continue

            content = raw.get("content", "") if isinstance(raw, dict) else ""
            if content.startswith("Error:"):
                error_code = _classify_error_content(content)
                if self._should_retry(error_code) and attempt < attempts - 1:
                    last_error_content = content
                    logger.warning(
                        "_chat_call retryable content error (attempt %d/%d): [%s]",
                        attempt + 1,
                        attempts,
                        error_code,
                    )
                    await self._wait_with_backoff(attempt)
                    continue
            return raw

        if last_error is not None:
            raise last_error
        return {"content": last_error_content or "Error: chat call failed", "reasoning_content": ""}

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
    # OpenAI SDK exceptions (most specific first — APITimeoutError inherits APIConnectionError)
    if isinstance(error, openai.APITimeoutError):
        return "timeout"
    if isinstance(error, openai.APIConnectionError):
        return "connection_error"
    if isinstance(error, openai.RateLimitError):
        return "rate_limit"
    if isinstance(error, openai.InternalServerError):
        return "server_error"
    if isinstance(error, openai.APIStatusError):
        status = error.status_code
        if status == 429:
            return "rate_limit"
        if status in {408, 425}:
            return "timeout"
        if status >= 500:
            return "server_error"
        return "api_error"

    # httpx exceptions (below OpenAI SDK, which wraps them)
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status == 429:
            return "rate_limit"
        if status in {408, 425}:
            return "timeout"
        if status in {500, 502, 503, 504}:
            return "server_error"
        return "api_error"
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.TransportError):
        return "connection_error"

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
    reasoning = raw.get("reasoning") or raw.get("reasoning_content", "")

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
