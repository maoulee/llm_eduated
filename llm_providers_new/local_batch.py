# llm_providers_new/local_batch.py

"""
本地 vLLM 推理客户端。

它直接与 vLLM 的 LLM 类交互，提供与远程 API 相同的异步接口。
注意：该实现内部仍调用同步 generate，因此适合离线批处理；在线服务推荐使用
RemoteAPIProvider + vLLM OpenAI-compatible online batch 接口。
"""

import json
import logging
from typing import List, Dict, Optional

from vllm import LLM, SamplingParams
from transformers import AutoTokenizer

from .base import BaseLLMProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class LocalVLLMProvider(BaseLLMProvider):
    """实现 BaseLLMProvider 接口的本地 vLLM 客户端。"""

    # Application-level config keys that are NOT vLLM EngineArgs
    _NON_VLLM_KEYS = frozenset({
        "request_timeout", "max_retries", "supports_response_format",
        "prompt_template_style", "thinking_control_method", "serve_as_api",
        "temperature", "top_p", "top_k", "default_max_tokens",
    })

    def __init__(self, model_name: str, **vllm_kwargs):
        default_kwargs = {
            "trust_remote_code": True,
            "max_model_len": 10000,
        }
        merged = {**default_kwargs, **vllm_kwargs}
        # Strip non-vLLM params before passing to EngineArgs
        engine_kwargs = {k: v for k, v in merged.items() if k not in self._NON_VLLM_KEYS}

        logger.info("Initializing LocalVLLMProvider with model '%s' and params: %s", model_name, engine_kwargs)
        self.llm = LLM(model=model_name, **engine_kwargs)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.provider_type = "local"

    def _apply_template_sync(self, messages: List[Dict]) -> str:
        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    def _generate_sync(
        self,
        prompts_batch: List[str],
        stop_sequences: Optional[List[str]] = None,
        max_tokens: Optional[int] = None,
    ) -> List[str]:
        sampling_params = SamplingParams(
            temperature=0.6,
            top_p=0.9,
            max_tokens=max_tokens or 8192,
            stop=stop_sequences or [],
        )
        outputs = self.llm.generate(prompts_batch, sampling_params)
        return [output.outputs[0].text for output in outputs]

    async def generate_with_think_and_parse_batch(
        self,
        messages_batch: List[List[Dict]],
        stop_sequences: Optional[List[str]] = None,
        enable_thinking: bool = True,
        max_token: Optional[int] = None,
    ) -> List[Dict]:
        logger.info("LocalVLLMProvider: generating batch size=%s", len(messages_batch))
        processed_messages_batch = []
        for messages in messages_batch:
            copied = [dict(msg) for msg in messages]
            if copied and copied[-1].get("role") == "user" and not enable_thinking:
                copied[-1]["content"] = f"{copied[-1].get('content', '')} /no_think"
            processed_messages_batch.append(copied)

        prompts = [self._apply_template_sync(msgs) for msgs in processed_messages_batch]
        raw_outputs = self._generate_sync(prompts, stop_sequences, max_token)

        results = []
        for raw_output in raw_outputs:
            if enable_thinking and "<think>" in raw_output and "</think>" in raw_output:
                try:
                    parts = raw_output.split("<think>", 1)[1].split("</think>", 1)
                    results.append({"think": parts[0].strip(), "answer": parts[1].strip()})
                except IndexError:
                    logger.warning("Could not parse <think> tags from response: %s", raw_output[:100])
                    results.append({"think": "N/A (parse error)", "answer": raw_output.strip()})
            else:
                results.append({"think": "N/A (thinking disabled or not present)", "answer": raw_output.strip()})
        return results

    async def generate_json_batch(
        self,
        messages_batch: List[List[Dict]],
        max_tokens: Optional[int] = None,
        enable_thinking: bool = False,
    ) -> List[Optional[Dict]]:
        logger.info("LocalVLLMProvider: generating JSON batch size=%s", len(messages_batch))
        processed_messages_batch = []
        for messages in messages_batch:
            copied = [dict(msg) for msg in messages]
            if copied and copied[-1].get("role") == "user":
                if not enable_thinking:
                    copied[-1]["content"] = f"{copied[-1].get('content', '')} /no_think"
                copied[-1]["content"] = f"{copied[-1].get('content', '')}\n\n请只输出一个合法 JSON 对象，不要输出 Markdown 或额外解释。"
            processed_messages_batch.append(copied)

        prompts = [self._apply_template_sync(msgs) for msgs in processed_messages_batch]
        raw_outputs = self._generate_sync(prompts, max_tokens=max_tokens)

        results: List[Optional[Dict]] = []
        for raw_output in raw_outputs:
            try:
                if "```json" in raw_output:
                    clean_output = raw_output.split("```json\n", 1)[1].rsplit("```", 1)[0]
                else:
                    start, end = raw_output.find("{"), raw_output.rfind("}")
                    clean_output = raw_output[start:end + 1] if start != -1 and end != -1 else raw_output
                results.append(json.loads(clean_output))
            except (json.JSONDecodeError, IndexError) as e:
                logger.warning("Failed to parse JSON. Error: %s Raw output: %s", e, raw_output[:100])
                results.append(None)
        return results
