# llm_providers/remote_api.py

import asyncio
import json
from typing import List, Dict, Union, Optional
from openai import AsyncOpenAI
import copy

class VLLMAPIClient:
    """
    一个【异步】客户端，用于与vLLM的原生OpenAI兼容API服务进行高效交互。
    使用官方 openai 库和 asyncio 实现高吞吐量。
    """
    def __init__(self, model_name: str, api_base_url="http://localhost:8000/v1", api_key: str = "EMPTY"):
        # 初始化异步OpenAI客户端
        self.client = AsyncOpenAI(
            api_key="EMPTY",  # vLLM不需要API Key
            base_url=api_base_url
        )
        self.model_name = model_name
        # 通用的采样参数
        self.sampling_params = {
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 4000
        }

    async def _make_api_call(self, messages: List[Dict], stop_sequences: Optional[List[str]] = None,max_tokens:Optional[int]=None) -> str:
        """
        对单个请求进行【异步】API调用。
        """
        params = {
            "model": self.model_name,
            "messages": messages,
            **self.sampling_params
        }
        if max_tokens:
            params['max_tokens'] = max_tokens
        if stop_sequences:
            params['stop'] = stop_sequences
        
        try:
            # 使用 await 调用异步方法
            response = await self.client.chat.completions.create(**params)
            return response.choices[0].message.content
        except Exception as e:
            print(f"API call failed: {e}")
            # 在异步上下文中，最好也返回错误信息，而不是中断整个批次
            return f"Error: API call failed. Details: {e}"

    async def generate_with_think_and_parse_batch(
        self,
        messages_batch: List[List[Dict]],
        stop_sequences: Optional[List[str]] = None,
        enable_thinking: bool = True,
        max_token:int=None
    ) -> List[Dict]:
        """
        【异步】批量生成和解析，支持开关思考模式。
        """
        processed_messages_batch = []
        for messages in messages_batch:
            processed_messages = copy.deepcopy(messages)
            if len(processed_messages) > 0 and processed_messages[-1]['role'] == 'user':
                if not enable_thinking:
                    processed_messages[-1]['content'] += " /no_think"
            processed_messages_batch.append(processed_messages)

        # --- 【核心修改】使用 asyncio.gather 来并发执行所有API调用 ---
        tasks = [
            self._make_api_call(msgs, stop_sequences)
            for msgs in processed_messages_batch
        ]
        # asyncio.gather 会并发地运行所有 tasks，并按顺序返回结果
        raw_outputs = await asyncio.gather(*tasks)
        # --- 修改结束 ---

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

    async def generate_json_batch(self, messages_batch: List[List[Dict]]) -> List[Union[Dict, None]]:
        """
        【异步】批量生成JSON。
        """
        processed_messages_batch = []
        for messages in messages_batch:
            processed_messages = copy.deepcopy(messages)
            if len(processed_messages) > 0 and processed_messages[-1]['role'] == 'user':
                processed_messages[-1]['content'] += " /no_think"
            processed_messages_batch.append(processed_messages)

        tasks = [self._make_api_call(msgs) for msgs in processed_messages_batch]
        raw_outputs = await asyncio.gather(*tasks)

        results = []
        for raw_output in raw_outputs:
            try:
                # JSON解析逻辑不变
                if "```json" in raw_output:
                    clean_output = raw_output.split("```json\n", 1)[1].rsplit("```", 1)[0]
                else:
                    start, end = raw_output.find('{'), raw_output.rfind('}')
                    clean_output = raw_output[start : end+1] if start != -1 and end != -1 else raw_output
                results.append(json.loads(clean_output))
            except (json.JSONDecodeError, IndexError) as e:
                print(f"Warning: Failed to parse JSON. Error: {e}\nRaw output: {raw_output}")
                results.append(None)
        
        return results