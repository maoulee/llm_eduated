# llm_providers_new/remote_api.py

"""
Remote LLM provider implementations.

Supported online API protocols:

1. openai_chat
   - OpenAI-compatible `/v1/chat/completions`.
   - Use this for GLM 5.1 and other online OpenAI-compatible models.

2. vllm_chat_batch
   - vLLM `/v1/chat/completions/batch`.
   - Payload uses `messages` as a list of conversations.
   - Response contains one choice per conversation, with `choice.index` mapping
     back to the input conversation index.

3. openai_completions_batch
   - Legacy fallback for `/v1/completions` with `prompt` as a list.
"""

import asyncio
import copy
import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from openai import AsyncOpenAI

from .base import BaseLLMProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class RemoteAPIProvider(BaseLLMProvider):
    """OpenAI-compatible remote provider with configurable thinking control."""

    def __init__(self, model_name: str, api_base_url: str, api_key: str = "EMPTY", **kwargs):
        self.model_name = model_name
        self.provider_type = "api"
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key or "EMPTY"
        self.request_timeout = float(kwargs.get("request_timeout", 300.0))
        self.max_retries = int(kwargs.get("max_retries", 0))

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_base_url,
            timeout=self.request_timeout,
            max_retries=self.max_retries,
        )

        self.api_protocol = kwargs.get("api_protocol", "openai_chat")

        # Thinking control methods:
        # - none: do not modify request/prompt.
        # - prompt: append /no_think when thinking is disabled.
        # - param: send provider-specific extra_body {"thinking": {"type": ...}}.
        # - chat_template_kwargs: send vLLM-style
        #   {"chat_template_kwargs": {"enable_thinking": bool}}.
        self.thinking_control_method = kwargs.get("thinking_control_method", "prompt")
        self.prompt_template_style = kwargs.get("prompt_template_style", "qwen")
        self.supports_response_format = bool(kwargs.get("supports_response_format", True))
        self.batch_size = max(1, int(kwargs.get("batch_size", 8)))

        self.sampling_params = {
            "temperature": float(kwargs.get("temperature", 0.6)),
            "top_p": float(kwargs.get("top_p", 0.9)),
            "top_k": int(kwargs.get("top_k", -1)),
            "max_tokens": int(kwargs.get("default_max_tokens", 4096)),
        }

        logger.info(
            "RemoteAPIProvider initialized: model=%s base_url=%s protocol=%s batch_size=%s thinking=%s",
            self.model_name,
            self.api_base_url,
            self.api_protocol,
            self.batch_size,
            self.thinking_control_method,
        )

    def _base_server_url(self) -> str:
        """Return server root URL. Handles configs ending in /v1."""
        if self.api_base_url.endswith("/v1"):
            return self.api_base_url[:-3].rstrip("/")
        return self.api_base_url

    def _prepare_messages(self, messages: List[Dict[str, Any]], enable_thinking: bool, json_mode: bool) -> List[Dict[str, Any]]:
        """Copy and lightly modify messages according to prompt/json control."""
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
        """Provider-specific thinking parameter support."""
        if self.thinking_control_method == "param":
            return {"thinking": {"type": "enabled" if enable_thinking else "disabled"}}
        if self.thinking_control_method == "chat_template_kwargs":
            return {"chat_template_kwargs": {"enable_thinking": bool(enable_thinking)}}
        return {}

    def _messages_to_prompt(self, messages: List[Dict[str, Any]], enable_thinking: bool, json_mode: bool) -> str:
        """Convert chat messages into a text prompt for legacy batched completions."""
        processed = self._prepare_messages(messages, enable_thinking=enable_thinking, json_mode=json_mode)

        if self.prompt_template_style == "qwen":
            chunks = []
            for msg in processed:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                chunks.append(f"<|im_start|>{role}\n{content}<|im_end|>")
            chunks.append("<|im_start|>assistant\n")
            return "\n".join(chunks)

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
    ) -> Dict[str, Any]:
        processed_messages = self._prepare_messages(messages, enable_thinking=enable_thinking, json_mode=json_mode)
        # OpenAI client doesn't accept top_k; pass it via extra_body for vLLM
        sampling = {k: v for k, v in self.sampling_params.items() if k != "top_k"}
        params: Dict[str, Any] = {
            "model": self.model_name,
            "messages": processed_messages,
            **sampling,
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

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(**params)
                msg = response.choices[0].message
                reasoning_content = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None) or ""
                return {"content": msg.content or "", "reasoning_content": reasoning_content}
            except Exception as e:
                import asyncio as _asyncio
                is_retryable = (
                    "500" in str(e)
                    or "ConnectionError" in type(e).__name__
                    or "Connection error" in str(e)
                    or "TimeoutExpired" in type(e).__name__
                )
                if is_retryable and attempt < max_retries - 1:
                    wait_s = 60
                    logger.warning("Retryable API error (attempt %d/%d), waiting %ds: %s",
                                   attempt + 1, max_retries, wait_s, str(e)[:200])
                    await _asyncio.sleep(wait_s)
                    continue
                logger.error("OpenAI-compatible chat call failed: %s", e, exc_info=True)
                return {"content": f"Error: API call failed. Details: {e}", "reasoning_content": ""}

    async def _vllm_chat_batch_call(
        self,
        messages_batch: List[List[Dict[str, Any]]],
        stop_sequences: Optional[List[str]],
        max_tokens: Optional[int],
        enable_thinking: bool,
        json_mode: bool,
    ) -> List[Dict[str, Any]]:
        processed_batch = [
            self._prepare_messages(msgs, enable_thinking=enable_thinking, json_mode=json_mode)
            for msgs in messages_batch
        ]
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": processed_batch,
            **self.sampling_params,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if stop_sequences:
            payload["stop"] = stop_sequences
        if json_mode and self.supports_response_format:
            payload["response_format"] = {"type": "json_object"}

        # vLLM Qwen-family thinking control can be passed through chat_template_kwargs.
        # This is useful when the server applies chat templates itself.
        extra_body = self._extra_body_for_thinking(enable_thinking)
        payload.update(extra_body)

        url = f"{self._base_server_url()}/v1/chat/completions/batch"
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "EMPTY":
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("vLLM batch endpoint not available (404), falling back to sequential calls")
                return await self._fallback_sequential_chat(processed_batch, stop_sequences, max_tokens, enable_thinking, json_mode)
            logger.error("vLLM chat batch call failed: %s", e, exc_info=True)
            return [{"content": f"Error: vLLM chat batch call failed. Details: {e}", "reasoning_content": ""} for _ in processed_batch]
        except Exception as e:
            logger.error("vLLM chat batch call failed: %s", e, exc_info=True)
            return [{"content": f"Error: vLLM chat batch call failed. Details: {e}", "reasoning_content": ""} for _ in processed_batch]

        ordered: List[Dict[str, Any]] = [{"content": "", "reasoning_content": ""} for _ in processed_batch]
        for choice in data.get("choices", []):
            idx = choice.get("index")
            if idx is None or idx >= len(ordered):
                continue
            message = choice.get("message") or {}
            ordered[idx] = {
                "content": message.get("content") or "",
                "reasoning_content": message.get("reasoning_content") or message.get("reasoning") or "",
            }
        return ordered

    async def _fallback_sequential_chat(
        self,
        messages_batch: List[List[Dict[str, Any]]],
        stop_sequences: Optional[List[str]],
        max_tokens: Optional[int],
        enable_thinking: bool,
        json_mode: bool,
    ) -> List[Dict[str, Any]]:
        """Fallback: send batch requests as individual concurrent chat calls."""
        semaphore = asyncio.Semaphore(self.batch_size)

        async def single_call(msgs):
            async with semaphore:
                return await self._chat_call(
                    msgs,
                    stop_sequences=stop_sequences,
                    max_tokens=max_tokens,
                    enable_thinking=enable_thinking,
                    json_mode=json_mode,
                )

        return list(await asyncio.gather(*[single_call(msgs) for msgs in messages_batch]))

    async def _completion_batch_call(
        self,
        messages_batch: List[List[Dict[str, Any]]],
        stop_sequences: Optional[List[str]],
        max_tokens: Optional[int],
        enable_thinking: bool,
        json_mode: bool,
    ) -> List[Dict[str, Any]]:
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
            ordered: List[Dict[str, Any]] = [{"content": "", "reasoning_content": ""} for _ in prompts]
            for choice in response.choices:
                idx = getattr(choice, "index", None)
                if idx is None or idx >= len(ordered):
                    continue
                ordered[idx] = {"content": choice.text or "", "reasoning_content": ""}
            return ordered
        except Exception as e:
            logger.error("online completion batch call failed: %s", e, exc_info=True)
            return [{"content": f"Error: batch API call failed. Details: {e}", "reasoning_content": ""} for _ in prompts]

    async def _generate_raw_batch(
        self,
        messages_batch: List[List[Dict[str, Any]]],
        stop_sequences: Optional[List[str]],
        max_tokens: Optional[int],
        enable_thinking: bool,
        json_mode: bool,
    ) -> List[Dict[str, Any]]:
        if not messages_batch:
            return []

        if self.api_protocol in {"vllm_chat_batch", "openai_chat_batch"}:
            outputs: List[Dict[str, Any]] = []
            for start in range(0, len(messages_batch), self.batch_size):
                chunk = messages_batch[start:start + self.batch_size]
                outputs.extend(
                    await self._vllm_chat_batch_call(
                        chunk,
                        stop_sequences=stop_sequences,
                        max_tokens=max_tokens,
                        enable_thinking=enable_thinking,
                        json_mode=json_mode,
                    )
                )
            return outputs

        if self.api_protocol in {"openai_completions_batch", "vllm_completions_batch"}:
            outputs: List[Dict[str, Any]] = []
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

        semaphore = asyncio.Semaphore(self.batch_size)

        async def guarded_call(msgs: List[Dict[str, Any]]) -> Dict[str, Any]:
            async with semaphore:
                return await self._chat_call(
                    msgs,
                    stop_sequences=stop_sequences,
                    max_tokens=max_tokens,
                    enable_thinking=enable_thinking,
                    json_mode=json_mode,
                )

        return list(await asyncio.gather(*[guarded_call(msgs) for msgs in messages_batch]))

    @staticmethod
    @staticmethod
    def _parse_think_answer(output: Dict[str, Any], enable_thinking: bool) -> Dict[str, str]:
        """Parse thinking and answer from API response.

        Args:
            output: Dict with 'content' and 'reasoning_content' keys from API response.
            enable_thinking: Whether thinking mode was enabled.

        Returns:
            Dict with 'think' and 'answer' keys.
        """
        reasoning = output.get("reasoning_content", "")
        content = output.get("content", "")

        if reasoning:
            # GLM thinking mode may put XML output into reasoning_content
            # instead of content. Extract XML-tagged tail as answer.
            if not content and enable_thinking:
                xml_match = re.search(r'(<\w+>.*?</\w+>\s*)+$', reasoning, re.DOTALL)
                if xml_match:
                    xml_part = xml_match.group(0)
                    think_part = reasoning[:xml_match.start()].strip()
                    return {"think": think_part, "answer": xml_part.strip()}
                # Fallback: extract code blocks or content after thinking
                code_match = re.search(r'(```\w*\n.*?```)', reasoning, re.DOTALL)
                if code_match:
                    code_part = code_match.group(1)
                    think_part = reasoning[:code_match.start()].strip()
                    return {"think": think_part, "answer": code_part.strip()}
                # Fallback: extract markdown sections (## ...) from reasoning
                md_match = re.search(r'(^|\n)(#{1,3}\s+.+)', reasoning, re.MULTILINE)
                if md_match:
                    md_part = reasoning[md_match.start():].strip()
                    think_part = reasoning[:md_match.start()].strip()
                    return {"think": think_part, "answer": md_part}
            return {"think": reasoning, "answer": content}

        # Fallback for legacy responses without reasoning_content field
        if enable_thinking and "<think" in content:
            try:
                parts = content.split("<think", 1)[1].split("</think", 1)
                return {"think": parts[0].strip(), "answer": parts[1].strip()}
            except IndexError:
                return {"think": "N/A (parse error)", "answer": content.strip()}
        return {"think": "N/A (thinking disabled or not present)", "answer": content.strip()}

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
        results = []
        retry_indices = []
        for i, output in enumerate(raw_outputs):
            parsed = self._parse_think_answer(output, enable_thinking=enable_thinking)
            # GLM thinking mode sometimes empties content into reasoning_content only.
            # Retry once for affected messages.
            if enable_thinking and not parsed.get("answer"):
                retry_indices.append(i)
            results.append(parsed)

        if retry_indices:
            logger.warning("GLM returned empty content for %d messages, retrying", len(retry_indices))
            retry_batch = [messages_batch[i] for i in retry_indices]
            retry_outputs = await self._generate_raw_batch(
                messages_batch=retry_batch,
                stop_sequences=stop_sequences,
                max_tokens=max_token,
                enable_thinking=enable_thinking,
                json_mode=False,
            )
            for j, idx in enumerate(retry_indices):
                retry_parsed = self._parse_think_answer(retry_outputs[j], enable_thinking=enable_thinking)
                if retry_parsed.get("answer"):
                    results[idx] = retry_parsed
                    logger.info("Retry succeeded for message %d", idx)

        return results

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
        return [self._parse_json(output.get("content", "")) for output in raw_outputs]
