# llm_providers_new/anthropic_provider.py
"""GLM anthropic endpoint provider (Anthropic Messages protocol).

Thinking control: thinking.type (on/off) + reasoning_effort (GLM extension via extra_body).
Message preparation and thinking-field translation live HERE (gateway is protocol-agnostic).
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import anthropic
import httpx

from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """GLM /api/anthropic provider implementing BaseLLMProvider + stream()."""

    def __init__(self, model_name: str, api_base_url: str, api_key: str = "EMPTY", **kwargs):
        self.model_name = model_name
        self.provider_type = "api"
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key or "EMPTY"
        self.request_timeout = float(kwargs.get("request_timeout", 300.0))
        self.max_retries = int(kwargs.get("max_retries", 2))
        self.thinking_control_method = kwargs.get("thinking_control_method", "none")
        self.supports_response_format = False
        self.batch_size = max(1, int(kwargs.get("batch_size", 4)))

        self.sampling_params = {
            "temperature": float(kwargs.get("temperature", 1.0)),
            "top_p": float(kwargs.get("top_p", 0.95)),
            "max_tokens": int(kwargs.get("default_max_tokens", 30000)),
        }

        timeout = httpx.Timeout(self.request_timeout, connect=30.0)
        limits = httpx.Limits(
            max_connections=int(kwargs.get("max_connections", 20)),
            max_keepalive_connections=int(kwargs.get("max_keepalive_connections", 10)),
            keepalive_expiry=float(kwargs.get("keepalive_expiry", 120)),
        )
        self.http_client = httpx.AsyncClient(timeout=timeout, limits=limits)
        # GLM's anthropic endpoint: SDK appends /v1/messages to base_url.
        self.client = anthropic.AsyncAnthropic(
            api_key=self.api_key,
            base_url=self.api_base_url,
            timeout=self.request_timeout,
            max_retries=self.max_retries,
            http_client=self.http_client,
        )
        logger.info("AnthropicProvider initialized: model=%s base_url=%s", model_name, self.api_base_url)

    def _prepare_messages(self, messages: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """OpenAI-style messages -> (anthropic messages, system). anthropic requires system separate."""
        system_parts: List[str] = []
        converted: List[Dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
            else:
                converted.append({"role": role, "content": content})
        return converted, ("\n\n".join(system_parts) if system_parts else None)

    def _convert_tools(self, openai_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for tool in openai_tools:
            fn = tool.get("function", tool)
            out.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })
        return out

    def _thinking_kwargs(self, intent: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Translate neutral thinking_intent -> anthropic request kwargs.

        Default enabled shape is bare {"type": "enabled"} — exactly what 附录 A test 3
        verified (~173 thinking tokens at effort=high). budget_tokens is ONLY added when
        the caller explicitly passes a budget; the SDK does not runtime-enforce it
        (ThinkingConfigEnabledParam.budget_tokens is Required for typecheck only), and
        GLM's anthropic-compatible endpoint accepts bare enabled.
        """
        kw: Dict[str, Any] = {}
        if not intent:
            return kw
        if intent.get("enabled"):
            thinking: Dict[str, Any] = {"type": "enabled"}
            if intent.get("budget") is not None:
                thinking["budget_tokens"] = max(1024, int(intent["budget"]))
            kw["thinking"] = thinking
            if intent.get("effort"):
                kw["extra_body"] = {"reasoning_effort": intent["effort"]}
        else:
            kw["thinking"] = {"type": "disabled"}
        return kw

    async def stream(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Unified stream interface. params has: model, messages, max_tokens?, temperature?,
        thinking_intent?, tools?, stream?. Returns {content, reasoning_content, tool_calls, finish_reason}.

        Streaming only: the gateway always passes stream=True, so non-stream is out of
        scope (the gateway is the sole consumer). A `stream` key in params is ignored,
        never forwarded to messages.stream().
        """
        messages, system = self._prepare_messages(params["messages"])
        kwargs: Dict[str, Any] = {
            "model": params["model"],
            "messages": messages,
            "max_tokens": params.get("max_tokens", self.sampling_params["max_tokens"]),
            "temperature": params.get("temperature", self.sampling_params["temperature"]),
        }
        if system:
            kwargs["system"] = system
        kwargs.update(self._thinking_kwargs(params.get("thinking_intent")))
        if params.get("tools"):
            kwargs["tools"] = self._convert_tools(params["tools"])
        return await self._read_stream(kwargs)

    async def _read_stream(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Run messages.stream() and reduce the final message to the unified shape."""
        content_parts: List[str] = []
        reasoning_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        finish_reason: Optional[str] = None
        async with self.client.messages.stream(**kwargs) as s:
            final = await s.get_final_message()
        finish_reason = final.stop_reason
        for block in final.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                content_parts.append(getattr(block, "text", ""))
            elif btype == "thinking":
                reasoning_parts.append(getattr(block, "thinking", ""))
            elif btype == "tool_use":
                tool_calls.append({
                    "id": getattr(block, "id", ""),
                    "type": "function",
                    "function": {
                        "name": getattr(block, "name", ""),
                        "arguments": json.dumps(getattr(block, "input", {})),
                    },
                })
        return {
            "content": "".join(content_parts),
            "reasoning_content": "".join(reasoning_parts),
            "tool_calls": tool_calls or None,
            "finish_reason": finish_reason,
        }

    # BaseLLMProvider batch interface — not supported (batch annotation uses remote_api)
    async def generate_with_think_and_parse_batch(self, *args, **kwargs):
        raise NotImplementedError("AnthropicProvider does not support batch; use remote_api")

    async def generate_json_batch(self, *args, **kwargs):
        raise NotImplementedError("AnthropicProvider does not support batch; use remote_api")
