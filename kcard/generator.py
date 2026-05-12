# kcard/generator.py (修订版 1.2 - 引入智能重试)

import logging
import copy  # <-- NEW: 导入copy模块用于深拷贝
from typing import Dict, Any, Optional

from llm_providers_new.base import BaseLLMProvider
from . import prompt as kcard_prompts

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class KnowledgeEngineer:
    """
    一个实现了“项目重启蓝图”中知识工程师角色的类。
    它使用一个强大的LLM，从权威问题中直接提取和构建结构化的知识库。
    这个版本包含了智能重试机制，以处理JSON解析失败的情况。
    """
    def __init__(self, engineer_model_provider: BaseLLMProvider):
        """
        初始化知识工程师。

        Args:
            engineer_model_provider: 用于执行知识提取的强大LLM provider (e.g., GLM-4.5)。
        """
        self.llm = engineer_model_provider
        logger.info("KnowledgeEngineer initialized with smart retry mechanism.")

    async def generate_knowledge_base(
        self,
        authoritative_question: str,
        max_attempts: int = 3  # <-- NEW: 定义最大尝试次数
    ) -> Optional[Dict[str, Any]]:
        """
        从单个权威问题生成一个完整的、结构化的知识库。
        如果初次尝试因LLM输出格式问题失败，将进行智能重试。

        Args:
            authoritative_question: 一个高质量、典型的计算机科学问题。
            max_attempts: 生成知识库的总尝试次数。

        Returns:
            一个包含 "universal_knowledge_modules" 和 "problem_specific_constraints" 的字典，
            如果所有尝试都失败则返回 None。
        """
        logger.info(f"Generating knowledge base for question: '{authoritative_question[:70]}...'")

        # 1. 准备初始Prompt
        initial_content = kcard_prompts.PROMPT_A_KNOWLEDGE_EXTRACTION.format(question=authoritative_question)
        messages = [[{"role": "user", "content": initial_content}]]
        
        knowledge_base = None

        # --- NEW: 引入重试循环 ---
        for attempt in range(max_attempts):
            current_messages = messages
            max_tokens_for_call = 10000  # 默认值

            if attempt > 0:
                logger.warning(f"Attempt {attempt + 1}/{max_attempts}: Retrying with enhanced instructions and larger context.")
                
                # 策略1: 强化指令
                current_messages = copy.deepcopy(messages) # 使用深拷贝以避免修改原始列表
                retry_instruction = "\n\n[重要提醒] 你的上一次输出未能成功解析。请严格遵循指令，只返回一个完整的、无任何额外文本或思考过程的JSON对象。"
                current_messages[0][-1]['content'] += retry_instruction
                
                # 策略2: 扩展上下文窗口
                max_tokens_for_call = 16000

            # 2. 调用LLM的JSON生成方法
            json_outputs = await self.llm.generate_json_batch(current_messages, max_tokens=max_tokens_for_call,enable_thinking=False)

            # 3. 验证结果
            if json_outputs and isinstance(json_outputs[0], dict):
                result = json_outputs[0]
                if "universal_knowledge_modules" in result and "problem_specific_constraints" in result:
                    logger.info(f"Successfully generated and validated knowledge base on attempt {attempt + 1}.")
                    knowledge_base = result
                    break  # 成功，跳出重试循环
            
            # 如果即将结束最后一次循环仍未成功，记录日志
            if attempt == max_attempts - 1 and knowledge_base is None:
                logger.error(f"All {max_attempts} attempts failed to generate a valid knowledge base.")

        # 4. 返回最终结果
        return knowledge_base