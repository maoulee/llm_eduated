# core_new/pseudocode_generator.py

"""
伪代码生成器模块。
负责为给定的问题，结合检索到的知识，生成和优化解题计划（伪代码）。
"""

import logging
import re
from typing import List, Dict

# 从我们的新工具模块导入
from .utils import parse_code 
# 从新的prompts模块导入（假设未来会统一命名）
from .prompts import FRAMEWORK_GENERATION_PROMPT, FINAL_SYNTHESIS_PROMPT 
from llm_providers_new.base import BaseLLMProvider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 注意：这个类和Solver的功能有重叠，可以考虑合并。
# 但为了保持当前结构，我们先独立重构它。
# 这里的 "pseudocode" 实际上就是 "framework/plan"。
class PlanGenerator:
    """
    使用LLM为问题生成解题计划。
    注意：在我们的新架构中，这个角色由 `IterativeSolverWorkflow` 的第一步承担。
    这个文件可以被视为一个遗留组件或一个独立的规划工具。
    为了完整性，我们仍然重构它。
    """
    def __init__(self, llm_provider: BaseLLMProvider):
        if not hasattr(llm_provider, 'generate_with_think_and_parse_batch'):
            raise TypeError("llm_provider must have an async method 'generate_with_think_and_parse_batch'")
        self.llm = llm_provider

    async def generate_diverse_plans(
        self,
        prompt: str,
        retrieved_info: Dict,
        num_versions: int = 3
    ) -> List[str]:
        """
        为单个问题异步地生成多个版本的解题计划。

        Args:
            prompt: 用户问题。
            retrieved_info: 检索到的知识点和陷阱。
            num_versions: 要生成的版本数量。

        Returns:
            一个包含多个计划文本的列表。
        """
        knowledge_points_str = "\n".join(
            [f"- {p.get('point', '')}: {p.get('description', '')}" for p in retrieved_info.get('knowledge_points', [])]
        ) or "无"
        pitfalls_str = "\n".join(
            [f"- {p}" for p in retrieved_info.get('common_pitfalls', [])]
        ) or "无"
        knowledge_and_pitfalls = f"知识点:\n{knowledge_points_str}\n\n常见陷阱:\n{pitfalls_str}"

        content = FRAMEWORK_GENERATION_PROMPT.format(
            question=prompt,
            knowledge_and_pitfalls=knowledge_and_pitfalls
        )
        messages_batch = [[{"role": "user", "content": content}] for _ in range(num_versions)]

        logger.info(f"Generating {num_versions} diverse plans for the prompt: {prompt[:50]}...")
        # 注意：这里我们假设LLM返回的“answer”部分就是计划文本
        llm_outputs = await self.llm.generate_with_think_and_parse_batch(messages_batch, enable_thinking=True)
        
        # 这里的解析逻辑可能需要根据你的Prompt调整，例如，如果计划是JSON，应该用parse_json
        plans = [output['answer'] for output in llm_outputs]
        return plans

    async def synthesize_plan(self, prompt: str, plans: List[str]) -> str:
        """
        异步地将多个版本的计划合成为一个最终版本。

        Args:
            prompt: 用户问题。
            plans: 多个计划文本的列表。

        Returns:
            一个最终的、综合的计划文本。
        """
        if not plans:
            return ""
        if len(plans) == 1:
            return plans[0]

        # 动态构建用于合成的Prompt
        formatted_plans = ""
        for i, plan in enumerate(plans):
            formatted_plans += f"--- [计划版本 {i+1}] ---\n{plan}\n"
        
        # 复用 FINAL_SYNTHESIS_PROMPT 可能不是最合适的，最好有一个专用的合成Prompt
        # 但为了演示，我们先用它
        content = FINAL_SYNTHESIS_PROMPT.format(
            original_question=prompt,
            full_execution_trace=formatted_plans  # 将计划作为"trace"输入
        )
        messages = [[{"role": "user", "content": content}]]
        
        logger.info(f"Synthesizing {len(plans)} plans into a final version...")
        final_output = await self.llm.generate_with_think_and_parse_batch(messages, enable_thinking=False)
        
        return final_output[0]['answer']