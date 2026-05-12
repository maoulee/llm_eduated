# core_new/solver.py (Transitional Refactor)

"""
遗留的求解器模块。
这个模块包含了早期版本的解题、一致性检查和代码重构的逻辑。
在新架构中，其功能已被 core/workflow.py 中的 IterativeSolverWorkflow 取代和优化。
保留此文件用于参考和向后兼容。
"""

import logging
import re
from typing import List, Dict, Tuple, Any

# 从新工具模块导入
from .utils import parse_json_from_llm_output, execute_code 
from .prompts import (
    SUBQUESTION_SOLVER_PROMPT,
    CODE_GENERATION_FROM_PSEUDOCODE_PROMPT,
    STEP_RECONSTRUCTION_PROMPT,
    SOLUTION_CONSISTENCY_CHECK_PROMPT_V2,
    GLOBAL_RECONSTRUCTION_PROMPT
)
from llm_providers_new.base import BaseLLMProvider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LegacySolver:
    """
    一个封装了多种解题策略的遗留求解器。
    """
    def __init__(self, llm_provider: BaseLLMProvider):
        self.llm = llm_provider

    def _parse_subquestions(self, text: str) -> List[str]:
        """从文本中分割子问题解答。"""
        if not isinstance(text, str):
            return []
        return [sq.strip() for sq in text.split("[end_of_subquestion]") if sq.strip()]

    async def solve_by_subquestion_batch(
        self,
        prompt: str,
        plan: str,
        num_solutions: int = 3
    ) -> List[List[str]]:
        """根据计划，异步生成多个版本的子问题解答。"""
        content = SUBQUESTION_SOLVER_PROMPT.format(
            final_pseudocode=plan, # 沿用旧的变量名
            new_question_prompt=prompt
        )
        messages = [{"role": "user", "content": content}]
        messages_batch = [messages for _ in range(num_solutions)]

        logger.info(f"Generating {num_solutions} solutions by subquestion for: {prompt[:50]}...")
        llm_outputs = await self.llm.generate_with_think_and_parse_batch(messages_batch)
        
        return [self._parse_subquestions(output['answer']) for output in llm_outputs]

    async def check_consistency_with_llm(self, prompt: str, plan: str, solutions: List[List[str]]) -> Dict:
        """使用LLM进行一致性检查。"""
        if not solutions or len(solutions) < 2:
            return {"is_consistent": True, "reason": "Not enough solutions to compare."}

        formatted_sols = "".join(
            [f"[版本 {j+1}]\n" + "\n[end_of_subquestion]\n".join(sol) + "\n---\n" for j, sol in enumerate(solutions)]
        )
        content = SOLUTION_CONSISTENCY_CHECK_PROMPT_V2.format(
            question=prompt,
            pseudocode=plan,
            formatted_solutions=formatted_sols
        )
        messages = [[{"role": "user", "content": content}]]
        
        logger.info(f"Performing LLM-based consistency check for: {prompt[:50]}...")
        json_output = await self.llm.generate_json_batch(messages)
        
        return json_output[0] if json_output and json_output[0] else {"is_consistent": True, "reason": "Failed to get LLM check result."}

    async def generate_and_run_code_from_plan(self, prompt: str, plan: str) -> Dict[str, Any]:
        """根据计划生成代码并执行。"""
        key_values_str = " ".join(re.findall(r'[-+]?\d*\.\d+|\d+', prompt)) or "无"
        content = CODE_GENERATION_FROM_PSEUDOCODE_PROMPT.format(
            final_pseudocode=plan,
            key_values=key_values_str
        )
        messages = [[{"role": "user", "content": content}]]

        logger.info(f"Generating verification code for: {prompt[:50]}...")
        llm_output = (await self.llm.generate_with_think_and_parse_batch(messages))[0]
        
        executable_code = parse_json_from_llm_output(llm_output['answer'])
        
        if not executable_code:
            return {"executable_code": None, "output": None, "error": "Failed to parse code from LLM response."}
            
        logger.info("Executing generated code...")
        execution_result = execute_code(executable_code)
        
        return {
            "executable_code": executable_code,
            **execution_result # 合并 'output' 和 'error'
        }

    async def reconstruct_solution(self, prompt: str, inconsistency_report: str, code_result: Dict) -> List[str]:
        """使用代码执行结果重构不一致的解决方案。"""
        # 注意：这里的逻辑与 main_local.py 中的非常相似，但被简化了
        content = GLOBAL_RECONSTRUCTION_PROMPT.format(
            original_question=prompt,
            initial_solution_draft=inconsistency_report, # 复用字段
            inconsistency_report=inconsistency_report,
            executable_code=code_result.get('executable_code', 'N/A'),
            code_output=code_result.get('output', 'N/A')
        )
        messages = [[{"role": "user", "content": content}]]

        logger.info(f"Reconstructing solution based on code execution for: {prompt[:50]}...")
        reconstructed_output = (await self.llm.generate_with_think_and_parse_batch(messages))[0]
        
        return self._parse_subquestions(reconstructed_output['answer'])