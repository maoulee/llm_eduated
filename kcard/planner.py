# kcard/planner.py

import logging
import json
from typing import Dict, Any, Optional, List

from llm_providers_new.base import BaseLLMProvider
# 导入 prompts 模块
from .prompt import PROMPT_B_PSEUDOCODE_PLANNING

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Planner:
    """
    一个实现了“项目重启蓝图”中规划器角色的类。
    它使用一个LLM，基于给定的知识库和新问题，
    生成一个结构化的、包含伪代码的解题计划。
    """
    def __init__(self, planner_model_provider: BaseLLMProvider):
        """
        初始化规划器。
        """
        self.llm = planner_model_provider
        logger.info("Planner initialized.")

    async def generate_plan(
        self,
        question: str,
        # --- NEW: 接收带分数的知识列表 ---
        scored_kn_modules: List[Dict], 
        problem_constraints: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        为给定的问题和带分数的知识库生成解题计划。
        """
        logger.info(f"Generating solution plan for question: '{question[:70]}...'")

        # --- NEW: 准备带分数的知识输入 ---
        # 为了让LLM更好地理解，我们只传入关键信息
        knowledge_for_prompt = []
        for mod in scored_kn_modules:
            # 先获取 python_implementation 字段，可能是字典或None
            py_impl = mod.get("python_implementation")

            entry = {
                "knowledge_point_name": mod.get("canonical_name"),
                "relevance_score": mod.get("relevance_score"),
                "concept_summary": mod.get("concept_definition", {}).get("summary"),
                # 只有当 py_impl 是一个字典时，才尝试获取内部的键
                "tool_description": py_impl.get("description") if isinstance(py_impl, dict) else None,
                "tool_signature": py_impl.get("function_signature") if isinstance(py_impl, dict) else None
            }
            # 清理掉值为None的键，保持prompt整洁
            knowledge_for_prompt.append({k: v for k, v in entry.items() if v is not None})
        
        knowledge_str = json.dumps(knowledge_for_prompt, ensure_ascii=False, indent=2)
        # ------------------------------------

        constraints_str = json.dumps(problem_constraints, ensure_ascii=False, indent=2)

        content = PROMPT_B_PSEUDOCODE_PLANNING.format(
            knowledge_modules_json=knowledge_str,
            problem_constraints_json=constraints_str,
            question=question
        )
        messages = [[{"role": "user", "content": content}]]

        json_outputs = await self.llm.generate_json_batch(messages, max_tokens=10000,enable_thinking=True)

        if json_outputs and isinstance(json_outputs[0], dict):
            plan_obj = json_outputs[0]
            # --- NEW: 验证输出结构 ---
            if "knowledge_selection" in plan_obj and "plan" in plan_obj:
                logger.info(f"Successfully generated a plan with knowledge selection: {plan_obj['knowledge_selection']}")
                return plan_obj
            else:
                logger.error(f"Generated plan has incorrect structure. Keys found: {plan_obj.keys()}")
                return None
        else:
            logger.error("Failed to generate a valid JSON plan from the LLM.")
            return None