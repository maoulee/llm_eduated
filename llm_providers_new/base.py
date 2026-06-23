# llm_providers_new/base.py

"""
定义所有LLM Provider实现的抽象基类 (ABC)。
这个文件确保了所有provider都提供统一的异步接口，
使得上层应用代码可以与任何provider无缝交互，无需关心其内部是同步还是异步。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Union, Optional

class BaseLLMProvider(ABC):
    """
    所有LLM Provider都必须继承这个抽象基类。
    """

    @abstractmethod
    async def generate_with_think_and_parse_batch(
        self,
        messages_batch: List[List[Dict]],
        stop_sequences: Optional[List[str]] = None,
        enable_thinking: bool = True,
        max_token: Optional[int] = None
    ) -> List[Dict]:
        """
        异步地批量生成带思考模式的答案。

        Args:
            messages_batch: 多个对话列表组成的批次。
            stop_sequences: 可选的停止序列。
            enable_thinking: 是否启用 <think> 标签的解析。
            max_token: 可选的最大生成 token 数。

        Returns:
            一个字典列表，每个字典包含 'think' 和 'answer' 键。
        """
        pass

    @abstractmethod
    async def generate_json_batch(
        self,
        messages_batch: List[List[Dict]],
        max_tokens: Optional[int] = None,  # <-- 添加此参数
        enable_thinking: bool = True
    ) -> List[Optional[Dict]]:
        """
        异步地批量生成并解析JSON对象。

        Args:
            messages_batch: 多个对话列表组成的批次。

        Returns:
            一个字典或None的列表，每个元素对应一个输入的解析结果。
        """
        pass