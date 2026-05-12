# llm_providers_new/remote_api.py (Final Reinforced Version)

import asyncio
import json
import logging
import copy
from typing import List, Dict, Union, Optional

from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APIStatusError
from .base import BaseLLMProvider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RemoteAPIProvider(BaseLLMProvider):
    """
    一个实现了 BaseLLMProvider 接口的异步客户端。
    此版本将所有思考模式和JSON模式的控制逻辑集中在 _make_api_call 中，
    以确保行为的一致性和健壮性。
    """
    def __init__(self, model_name: str, api_base_url: str, api_key: str, **kwargs):
        self.client = AsyncOpenAI(api_key=api_key, base_url=api_base_url)
        self.model_name = model_name
        self.provider_type = "api"
        self.thinking_control_method = kwargs.get("thinking_control_method", "prompt")
        logger.info(f"Thinking control method for '{self.model_name}' is set to: '{self.thinking_control_method}'")

        self.sampling_params = {
            "temperature": 0.6,
            "top_p": 0.9,
            "max_tokens": 4096
        }
        logger.info(f"RemoteAPIProvider initialized for model '{model_name}' at '{api_base_url}'")

    async def _make_api_call(
        self,
        messages: List[Dict],
        stop_sequences: Optional[List[str]] = None,
        max_tokens: Optional[int] = None,
        enable_thinking: bool = True,
        json_mode: bool = False
    ) -> str:
        """
        对单个请求进行健壮的、异步的API调用。
        所有控制逻辑都在此函数内部处理。
        """
        
        # --- 核心改动：在此处统一处理所有控制逻辑 ---
        
        # 1. 复制 messages 以安全地进行修改
        processed_messages = copy.deepcopy(messages)
        
        # 2. 准备参数字典
        params = {
            "model": self.model_name,
            "messages": processed_messages,
            **self.sampling_params
        }
        if max_tokens:
            params['max_tokens'] = max_tokens
        if stop_sequences:
            params['stop'] = stop_sequences

        # 3. 根据策略应用控制
        extra_body = {}
        if self.thinking_control_method == 'param':
            # 策略1: 使用原生参数 (for GLM-4.5)
            extra_body["thinking"] = {"type": "enabled" if enable_thinking else "disabled"}
            if json_mode:
                extra_body["response_format"] = {"type": "json_object"}
        
        elif self.thinking_control_method == 'prompt':
            # 策略2: 使用Prompt注入 (for Qwen)
            # 如果需要关闭思考，或者强制进入JSON模式（JSON模式下不应思考）
            if not enable_thinking or json_mode:
                if len(processed_messages) > 0 and processed_messages[-1]['role'] == 'user':
                    logger.info("Injecting '/no_think' into prompt to disable thinking.")
                    processed_messages[-1]['content'] += " /no_think"
        
        if extra_body:
            params["extra_body"] = extra_body
        # ----------------------------------------------------

        try:
            response = await self.client.chat.completions.create(**params)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"An unexpected error occurred during API call: {e}", exc_info=True)
            return f"Error: An unexpected error occurred. Details: {e}"

    async def generate_with_think_and_parse_batch(
        self,
        messages_batch: List[List[Dict]],
        stop_sequences: Optional[List[str]] = None,
        enable_thinking: bool = True,
        max_token: Optional[int] = None
    ) -> List[Dict]:
        """
        异步批量生成和解析。现在只负责传递意图。
        """
        # 不再需要处理 processed_messages_batch，所有逻辑都在 _make_api_call 中
        tasks = [
            self._make_api_call(
                msgs, 
                stop_sequences, 
                max_token,
                enable_thinking=enable_thinking,
                json_mode=False # 普通模式下关闭json_mode
            )
            for msgs in messages_batch
        ]
        
        raw_outputs = await asyncio.gather(*tasks)

        # 解析逻辑保持不变
        results = []
        for raw_output in raw_outputs:
            if enable_thinking and "<think>" in raw_output and "</think>" in raw_output:
                try:
                    parts = raw_output.split("<think>", 1)[1].split("</think>", 1)
                    results.append({"think": parts[0].strip(), "answer": parts[1].strip()})
                except IndexError:
                    results.append({"think": "N/A (parse error)", "answer": raw_output.strip()})
            else:
                results.append({"think": "N/A (thinking disabled or not present)", "answer": raw_output.strip()})
        
        return results

    async def generate_json_batch(
        self, 
        messages_batch: List[List[Dict]], 
        max_tokens: Optional[int] = None,
        enable_thinking: bool = True,
    ) -> List[Optional[Dict]]:
        """
        异步批量生成并解析JSON。现在只负责传递意图。
        """
        # 之前版本的 enable_thinking=None 可能会导致问题，现在我们明确意图
        tasks = [
            self._make_api_call(
                msgs, 
                max_tokens=max_tokens,
                enable_thinking=enable_thinking, # 明确关闭思考
                json_mode=True         # 明确开启JSON模式
            ) 
            for msgs in messages_batch
        ]
        raw_outputs = await asyncio.gather(*tasks)

        # 解析逻辑保持不变
        results = []
        for raw_output in raw_outputs:
            try:
                results.append(json.loads(raw_output))
            except json.JSONDecodeError:
                try:
                    if "```json" in raw_output:
                        clean_output = raw_output.split("```json\n", 1)[1].rsplit("```", 1)[0]
                    else:
                        start, end = raw_output.find('{'), raw_output.rfind('}')
                        clean_output = raw_output[start : end+1] if start != -1 and end != -1 else raw_output
                    results.append(json.loads(clean_output))
                except (json.JSONDecodeError, IndexError) as e:
                    logger.warning(f"Failed to parse JSON. Error: {e}\nRaw output: {raw_output[:100]}...")
                    results.append(None)
        
        return results