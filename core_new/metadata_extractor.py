# core_new/metadata_extractor.py

"""
元数据提取器模块。
负责从 (问题, 答案) 对中，利用LLM提取结构化的元数据，
如知识点、关键实体和常见陷阱。
"""

import json
import logging
from typing import List, Dict, Any

from tqdm.asyncio import tqdm  # 使用tqdm的异步版本
from .prompts import METADATA_EXTRACTION_PROMPT
# 注意：这里我们导入的是抽象基类，而不是具体的实现
from llm_providers_new.base import BaseLLMProvider

# 配置日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MetadataExtractor:
    """
    使用LLM从问题和答案中异步批量提取元数据。
    """
    def __init__(self, llm_provider: BaseLLMProvider):
        """
        初始化元数据提取器。

        Args:
            llm_provider: 一个实现了 BaseLLMProvider 接口的LLM服务提供者实例。
        """
        if not hasattr(llm_provider, 'generate_json_batch'):
            raise TypeError("llm_provider must have an async method 'generate_json_batch'")
        self.llm = llm_provider

    async def extract_batch(self, qa_pairs: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        异步地为一批问题-答案对提取元数据。

        Args:
            qa_pairs: 一个字典列表，每个字典包含 "prompt" 和 "answer" 键。

        Returns:
            一个元数据字典的列表，每个字典对应一个输入QA对。
            如果某个提取失败，则对应的元素为None。
        """
        if not qa_pairs:
            return []

        logger.info(f"Building {len(qa_pairs)} metadata extraction requests...")
        messages_batch = []
        for qa_pair in qa_pairs:
            content = METADATA_EXTRACTION_PROMPT.format(
                prompt=qa_pair.get("prompt", ""),
                answer=qa_pair.get("answer", "")
            )
            messages_batch.append([{"role": "user", "content": content}])

        logger.info(f"Sending batch of {len(messages_batch)} requests to LLM for metadata extraction...")
        # 调用统一的异步接口
        metadata_results = await self.llm.generate_json_batch(messages_batch)
        
        # 将原始QA信息与提取结果合并，便于后续处理
        processed_results = []
        for i, metadata in enumerate(metadata_results):
            if metadata:
                # 成功提取，将原始信息加入
                metadata['original_prompt'] = qa_pairs[i].get("prompt")
                metadata['original_answer'] = qa_pairs[i].get("answer")
                processed_results.append(metadata)
            else:
                # 提取失败
                logger.warning(f"Failed to extract metadata for prompt: {qa_pairs[i].get('prompt', 'N/A')[:50]}...")
                processed_results.append(None) # 保留占位符

        return processed_results

    async def build_database_from_file(self, questions_file_path: str, output_db_path: str):
        """
        从问题文件读取，提取元数据，并保存为数据库文件。
        这是一个高级便利函数。
        """
        logger.info(f"Loading questions from {questions_file_path}...")
        try:
            with open(questions_file_path, 'r', encoding='utf-8') as f:
                questions = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load or parse questions file: {e}", exc_info=True)
            return

        # 调用核心的批量提取方法
        extracted_metadata_list = await self.extract_batch(questions)

        # 过滤掉失败的结果，构建最终的数据库
        metadata_db = {}
        for i, metadata in enumerate(extracted_metadata_list):
            if metadata:
                # 使用一个稳定的ID，例如 "q_文件中的索引"
                metadata_db[f"q_{i}"] = metadata
        
        logger.info(f"Successfully extracted metadata for {len(metadata_db)} out of {len(questions)} questions.")
        
        logger.info(f"Saving metadata database to {output_db_path}...")
        with open(output_db_path, 'w', encoding='utf--8') as f:
            json.dump(metadata_db, f, ensure_ascii=False, indent=2)
        
        logger.info("Metadata database build complete.")