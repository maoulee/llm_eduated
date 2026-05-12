# llm_providers_new/local_batch.py

"""
本地vLLM推理客户端。
它直接与vLLM的LLM类交互，提供与远程API相同的异步接口，但其内部执行是同步的。
"""

import json
import logging
from typing import List, Dict, Union, Optional

from vllm import LLM, SamplingParams
from transformers import AutoTokenizer

# 导入抽象基类
from .base import BaseLLMProvider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LocalVLLMProvider(BaseLLMProvider):
    """
    一个实现了 BaseLLMProvider 接口的本地vLLM客户端。
    它的公共方法是异步的，以匹配接口，但其内部实现调用的是vLLM的同步generate方法。
    """
    def __init__(self, model_name: str, **vllm_kwargs):
        """
        初始化本地vLLM引擎。

        Args:
            model_name: 模型的路径或HuggingFace标识符。
            **vllm_kwargs: 其他要传递给 vllm.LLM 的参数，如
                           tensor_parallel_size, quantization, gpu_memory_utilization, etc.
        """
        default_kwargs = {
            "trust_remote_code": True,
            "max_model_len": 10000,
        }
        # 使用用户传入的参数覆盖默认值
        final_kwargs = {**default_kwargs, **vllm_kwargs}

        logger.info(f"Initializing LocalVLLMProvider with model '{model_name}' and params: {final_kwargs}")
        self.llm = LLM(model=model_name, **final_kwargs)
        
        # 使用模型的路径来加载分词器
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.provider_type = "local" # 用于服务器端校验

    def _apply_template_sync(self, messages: List[Dict]) -> str:
        """同步地将单个对话应用模板。"""
        # 移除 enable_thinking，因为它不是标准参数，应在prompt内容中处理
        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

    def _generate_sync(
        self,
        prompts_batch: List[str],
        stop_sequences: Optional[List[str]] = None,
        max_tokens: Optional[int] = None
    ) -> List[str]:
        """同步地对一批文本进行生成。"""
        sampling_params = SamplingParams(
            temperature=0.6,
            top_p=0.9,
            max_tokens=max_tokens or 8192,
            stop=stop_sequences or []
        )
        outputs = self.llm.generate(prompts_batch, sampling_params)
        return [output.outputs[0].text for output in outputs]
    
    # --- 实现统一的异步接口 ---

    async def generate_with_think_and_parse_batch(
        self,
        messages_batch: List[List[Dict]],
        stop_sequences: Optional[List[str]] = None,
        enable_thinking: bool = True,
        max_token: Optional[int] = None
    ) -> List[Dict]:
        """异步接口，内部调用同步的vLLM实现。"""
        # 虽然是 async def，但内部没有 await，所以它会同步执行，
        # 但因为方法是异步的，所以可以在事件循环中被 await。
        logger.info(f"LocalVLLMProvider: Generating batch of {len(messages_batch)} with thinking.")
        prompts = [self._apply_template_sync(msgs) for msgs in messages_batch]
        raw_outputs = self._generate_sync(prompts, stop_sequences, max_token)
        
        results = []
        for raw_output in raw_outputs:
            if enable_thinking and "<think>" in raw_output and "</think>" in raw_output:
                try:
                    parts = raw_output.split("<think>", 1)[1].split("</think>", 1)
                    results.append({"think": parts[0].strip(), "answer": parts[1].strip()})
                except IndexError:
                    logger.warning(f"Could not parse <think> tags from response: {raw_output[:100]}...")
                    results.append({"think": "N/A (parse error)", "answer": raw_output.strip()})
            else:
                results.append({"think": "N/A (thinking disabled or not present)", "answer": raw_output.strip()})
        return results

    async def generate_json_batch(self, messages_batch: List[List[Dict]],max_tokens: Optional[int] = None) -> List[Optional[Dict]]:
        """异步接口，内部调用同步的vLLM实现以生成JSON。"""
        logger.info(f"LocalVLLMProvider: Generating JSON batch of {len(messages_batch)}.")
        prompts = [self._apply_template_sync(msgs) for msgs in messages_batch]
        raw_outputs = self._generate_sync(prompts, max_tokens=max_tokens)
        
        results = []
        for raw_output in raw_outputs:
            try:
                # 同样，可以调用 core.utils.parse_json_from_llm_output
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