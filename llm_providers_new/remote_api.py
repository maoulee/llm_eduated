# llm_providers_new/remote_api.py

"""
Remote LLM provider implementations.

This provider supports two API protocols:

1. openai_chat
   - OpenAI-compatible `/v1/chat/completions`.
   - Used for GLM 5.1 and other online OpenAI-compatible models.

2. openai_completions_batch
   - OpenAI-compatible `/v1/completions` with `prompt` as a list.
   - Used for vLLM online batch inference, so multiple prompts are sent in one
     HTTP request instead of launching one request per prompt.
"""

import asyncio
import copy
import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from .base import BaseLLMProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class RemoteAPIProvider(BaseLLMProvider):
    """OpenAI-compatible remote provider with optional vLLM online batching."""

    def __init__(self, model_name: str, api_base_url: str, api_key: str = "EMPTY", **kwargs):
        self.client = AsyncOpenAI(
            api_key=api_key or "EMPTY",
            base_url=api_base_url,
            timeout=float(kwargs.get("request_timeout", 120.0)),
            max_retries=int(kwargs.get("max_retries", 2)),
        )
        self.model_name = model_name
        self.provider_type = "api"
        self.api_protocol = kwargs.get("api_protocol", "openai_chat")
        self.thinking_control_method = kwargs.get("thinking_control_method", "prompt")
        self.prompt_template_style = kwargs.get("prompt_template_style", "qwen")
        self.supports_response_format = bool(kwargs.get("supports_response_format", True))
        self.batch_size = max(1, int(kwargs.get("batch_size", 8)))

        self.sampling_params = {
            "temperature": float(kwargs.get("temperature", 0.6)),
            "top_p": float(kwargs.get("top_p", 0.9)),
            "max_tokens": int(kwargs.get("default_max_tokens", 4096)),
        }

        logger.info(
            "RemoteAPIProvider initialized: model=%s base_url=%s protocol=%s batch_size=%s thinking=%s",
            self.model_name,
            api_base_url,
            self.api_protocol,
            self.batch_size,
            self.thinking_control_method,
        )

    def _prepare_messages(self, messages: List[Dict[str, Any]], enable_thinking: bool, json_mode: bool) -> List[Dict[str, Any]]:
        """Copy and lightly modify messages according to thinking/json mode."""
        processed = copy.deepcopy(messages)
        if not processed:
            return processed

        last = processed[-1]
        if last.get("role") == "user":
            if self.thinking_control_method == "prompt" and (not enable_thinking or json_mode):
                last["content"] = f"{last.get('content', '')} /no_think"
            if json_mode:
                last["content"] = f"{last.get('content', '')}\n\n请只输出一个合法 JSON 对象，不要输出 Markdown 或额外解释。"
        return processed

    def _extra_body_for_thinking(self, enable_thinking: bool) -> Dict[str, Any]:
        """Provider-specific thinking parameter support.

        GLM 5.1 OpenAI-compatible mode should use thinking_control_method='none'
        so no proprietary ZAI/BigModel body is sent.
        """
        if self.thinking_control_method == "param":
            return {"thinking": {"type": "enabled" if enable_thinking else "disabled"}}
        return {}

    def _messages_to_prompt(self, messages: List[Dict[str, Any]], enable_thinking: bool, json_mode: bool) -> str:
        """Convert chat messages into a text prompt for batched vLLM completions."""
        processed = self._prepare_messages(messages, enable_thinking=enable_thinking, json_mode=json_mode)

        if self.prompt_template_style == "qwen":
            chunks = []
            for msg in processed:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                chunks.append(f"<|im_start|>{role}\n{content}<|im_end|>")
            chunks.append("<|im_start|>assistant\n")
            return "\n".join(chunks)

        # Conservative fallback that still preserves roles.
        parts = []
        for msg in processed:
            parts.append(f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}")
        parts.append("ASSISTANT:")
        return "\n".join(parts)

    async def _chat_call(
        self,
        messages: List[Dict[str, Any]],
        stop_sequences: Optional[List[str]],
        max_tokens: Optional[int],
        enable_thinking: bool,
        json_mode: bool,
    ) -> str:
        processed_messages = self._prepare_messages(messages, enable_thinking=enable_thinking, json_mode=json_mode)
        params: Dict[str, Any] = {
            "model": self.model_name,
            "messages": processed_messages,
            **self.sampling_params,
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        if stop_sequences:
            params["stop"] = stop_sequences
        if json_mode and self.supports_response_format:
            params["response_format"] = {"type": "json_object"}

        extra_body = self._extra_body_for_thinking(enable_thinking)
        if extra_body:
            params["extra_body"] = extra_body

        try:
            response = await self.client.chat.completions.create(**params)
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("OpenAI-compatible chat call failed: %s", e, exc_info=True)
            return f"Error: API call failed. Details: {e}"

    async def _completion_batch_call(
        self,
        messages_batch: List[List[Dict[str, Any]]],
        stop_sequences: Optional[List[str]],
        max_tokens: Optional[int],
        enable_thinking: bool,
        json_mode: bool,
    ) -> List[str]:
        prompts = [
            self._messages_to_prompt(msgs, enable_thinking=enable_thinking, json_mode=json_mode)
            for msgs in messages_batch
        ]
        params: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompts,
            **self.sampling_params,
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        if stop_sequences:
            params["stop"] = stop_sequences

        try:
            response = await self.client.completions.create(**params)
            ordered = [""] * len(prompts)
            for choice in response.choices:
                idx = getattr(choice, "index", None)
                if idx is None or idx >= len(ordered):
                    continue
                ordered[idx] = choice.text or ""
            return ordered
        except Exception as e:
            logger.error("vLLM online batch completion call failed: %s", e, exc_info=True)
            return [f"Error: batch API call failed. Details: {e}" for _ in prompts]

    async def _generate_raw_batch(
        self,
        messages_batch: List[List[Dict[str, Any]]],
        stop_sequences: Optional[List[str]],
        max_tokens: Optional[int],
        enable_thinking: bool,
        json_mode: bool,
    ) -> List[str]:
        if not messages_batch:
            return []

        if self.api_protocol in {"openai_completions_batch", "vllm_completions_batch"}:
            outputs: List[str] = []
            for start in range(0, len(messages_batch), self.batch_size):
                chunk = messages_batch[start:start + self.batch_size]
                outputs.extend(
                    await self._completion_batch_call(
                        chunk,
                        stop_sequences=stop_sequences,
                        max_tokens=max_tokens,
                        enable_thinking=enable_thinking,
                        json_mode=json_mode,
                    )
                )
            return outputs

        # Standard OpenAI-compatible chat endpoint has no multi-message batch API,
        # so use bounded concurrency.
        semaphore = asyncio.Semaphore(self.batch_size)

        async def guarded_call(msgs: List[Dict[str, Any]]) -> str:
            async with semaphore:
                return await self._chat_call(
                    msgs,
                    stop_sequences=stop_sequences,
                    max_tokens=max_tokens,
                    enable_thinking=enable_thinking,
                    json_mode=json_mode,
                )

        return await asyncio.gather(*[guarded_call(msgs) for msgs in messages_batch])

    @staticmethod
    def _parse_think_answer(raw_output: str, enable_thinking: bool) -> Dict[str, str]:
        if enable_thinking and "<think>" in raw_output and "</think>" in raw_output:
            try:
                parts = raw_output.split("<think>", 1)[1].split("</think>", 1)
                return {"think": parts[0].strip(), "answer": parts[1].strip()}
            except IndexError:
                return {"think": "N/A (parse error)", "answer": raw_output.strip()}
        return {"think": "N/A (thinking disabled or not present)", "answer": raw_output.strip()}

    @staticmethod
    def _parse_json(raw_output: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(raw_output)
        except json.JSONDecodeError:
            pass

        try:
            if "```json" in raw_output:
                clean_output = raw_output.split("```json\n", 1)[1].rsplit("```", 1)[0]
            else:
                start, end = raw_output.find("{"), raw_output.rfind("}")
                clean_output = raw_output[start:end + 1] if start != -1 and end != -1 else raw_output
            return json.loads(clean_output)
        except (json.JSONDecodeError, IndexError) as e:
            logger.warning("Failed to parse JSON. Error: %s Raw output: %s", e, raw_output[:200])
            return None

    async def generate_with_think_and_parse_batch(
        self,
        messages_batch: List[List[Dict]],
        stop_sequences: Optional[List[str]] = None,
        enable_thinking: bool = True,
        max_token: Optional[int] = None,
    ) -> List[Dict]:
        raw_outputs = await self._generate_raw_batch(
            messages_batch=messages_batch,
            stop_sequences=stop_sequences,
            max_tokens=max_token,
            enable_thinking=enable_thinking,
            json_mode=False,
        )
        return [self._parse_think_answer(output, enable_thinking=enable_thinking) for output in raw_outputs]

    async def generate_json_batch(
        self,
        messages_batch: List[List[Dict]],
        max_tokens: Optional[int] = None,
        enable_thinking: bool = False,
    ) -> List[Optional[Dict]]:
        raw_outputs = await self._generate_raw_batch(
            messages_batch=messages_batch,
            stop_sequences=None,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
            json_mode=True,
        )
        return [self._parse_json(output) for output in raw_outputs]
