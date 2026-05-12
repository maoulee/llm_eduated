# core/solver.py (修复版)
from .prompts import (
    SUBQUESTION_SOLVER_PROMPT, 
    CODE_GENERATION_FROM_PSEUDOCODE_PROMPT, 
    STEP_RECONSTRUCTION_PROMPT,
    SOLUTION_CONSISTENCY_CHECK_PROMPT_V2, # <--- 导入新的Prompt
    GLOBAL_RECONSTRUCTION_PROMPT # 确保这个也在这里
)
from .llm_service import LLMService
import subprocess
import re
import json

class Solver:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    def _parse_subquestions(self, text: str) -> list[str]:
        if not isinstance(text, str):
            return []
        return [sq.strip() for sq in text.split("[end_of_subquestion]") if sq.strip()]

    def solve_by_subquestion_batch(self, new_question, final_pseudocode, num_solutions=3):
        content = SUBQUESTION_SOLVER_PROMPT.format(
            final_pseudocode=final_pseudocode,
            new_question_prompt=new_question
        )
        messages = [{"role": "user", "content": content}]
        
        messages_batch = [messages for _ in range(num_solutions)]
        llm_outputs = self.llm.generate_with_think_and_parse_batch(messages_batch)
        
        solutions_sq_list = [self._parse_subquestions(output['answer']) for output in llm_outputs]

    
        return solutions_sq_list
    
    def format_consistency_check_prompt(self, solutions_sq_list: list[list[str]]) -> dict | None:
        """
        [新] 准备用于批量一致性检查的单个消息。
        返回一个包含 "role" 和 "content" 的字典，如果无法格式化则返回 None。
        """
        if not solutions_sq_list or len(solutions_sq_list) < 2:
            return None # 不需要检查

        # 快速的结构性预检查
        num_sqs = [len(s) for s in solutions_sq_list]
        if len(set(num_sqs)) > 1:
            # 这种情况也需要报告，但可以在main中处理
            return None

        formatted_solutions = ""
        for i, solution_steps in enumerate(solutions_sq_list):
            formatted_solutions += f"[版本 {i+1}]\n"
            # 为了让LLM更好地理解步骤，我们可以在前面加上“子问题X”
            for step_idx, step_text in enumerate(solution_steps):
                 formatted_solutions += f"**子问题{step_idx+1}**:\n{step_text}\n[end_of_subquestion]\n"
            formatted_solutions += "---\n"

        content = SOLUTION_CONSISTENCY_CHECK_PROMPT_V2.format(formatted_solutions=formatted_solutions)
        return {"role": "user", "content": content}

    def check_subquestions_consistency(self, solutions_sq_list):
        if not solutions_sq_list or len(solutions_sq_list) < 2:
            return True, [], "Not enough solutions to check."

        num_sqs = [len(s) for s in solutions_sq_list]
        if len(set(num_sqs)) > 1:
            return False, [{"sq_index": -1, "error": f"Subquestion count mismatch: {num_sqs}"}], "Subquestion count mismatch."
        
        inconsistent_sqs = []
        for i in range(num_sqs[0]):
            sq_answers = []
            for solution_sqs in solutions_sq_list:
                # 提取并排序数字，以处理顺序不一致但结果相同的情况
                numbers = tuple(sorted(re.findall(r'[-+]?\d*\.\d+|\d+', solution_sqs[i])))
                sq_answers.append(numbers)
            
            if len(set(sq_answers)) > 1:
                inconsistent_sqs.append({
                    "sq_index": i,
                    "versions": [s[i] for s in solutions_sq_list]
                })

        if inconsistent_sqs:
            return False, inconsistent_sqs, "Inconsistency found in numerical results."
        else:
            return True, [], "All subquestions are consistent."

    def generate_and_run_code(self, new_question, final_pseudocode):
        key_values = " ".join(re.findall(r'[-+]?\d*\.\d+|\d+', new_question))
        key_values = key_values if key_values else "无"

        content = CODE_GENERATION_FROM_PSEUDOCODE_PROMPT.format(
            final_pseudocode=final_pseudocode if final_pseudocode else "无",
            key_values=key_values
        )
        messages = [{"role": "user", "content": content}]
        
        # --- 核心改动：解析和执行 ---
        llm_output = self.llm.generate_with_think_and_parse_batch([messages])[0]
        
        # 1. 精确提取代码
        executable_code = ""
        try:
            # 使用正则表达式或字符串分割来提取代码
            if "<execute_code>" in llm_output['answer']:
                executable_code = llm_output['answer'].split("<execute_code>")[1].split("</execute_code>")[0].strip()
            else:
                # 如果模型没有遵循格式，作为备用方案，尝试提取```python```块
                if "```python" in llm_output['answer']:
                    executable_code = llm_output['answer'].split("```python\n")[1].split("```")[0].strip()
                else: # 如果都找不到，就认为整个answer是代码，可能会失败
                    executable_code = llm_output['answer']

            if not executable_code:
                raise ValueError("Extracted empty code from LLM response.")

        except (IndexError, ValueError) as e:
            error_message = f"Failed to extract executable code from LLM response. Error: {e}. Raw response: {llm_output['answer']}"
            return llm_output['answer'], None, error_message

        # 2. 执行纯净的代码
        try:
            process = subprocess.run(
                ['python', '-c', executable_code],
                capture_output=True, text=True, timeout=15, check=True
            )
            code_run_output = process.stdout
            return executable_code, code_run_output, None
        except Exception as e:
            return executable_code, None, str(e)

    def reconstruct_subquestion(self, inconsistent_sq_info, executable_code, code_output):
        content = STEP_RECONSTRUCTION_PROMPT.format(
            inconsistent_subquestion="\n---\n".join(inconsistent_sq_info['versions']),
            executable_code=executable_code,
            code_output=code_output
        )
        messages = [{"role": "user", "content": content}]

        # --- 错误修复 ---
        # 同样，将单个请求包装成列表，调用批量接口，然后取第一个结果
        reconstructed_output = self.llm.generate_with_think_and_parse_batch([messages])[0]
        return reconstructed_output['answer'].replace("[end_of_subquestion]", "").strip()