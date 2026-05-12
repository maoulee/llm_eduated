# core/pseudocode_generator.py (最终确认版)
from .prompts import PSEUDOCODE_GENERATION_PROMPT, PSEUDOCODE_SYNTHESIS_PROMPT
from .llm_service import LLMService
import re

class PseudocodeGenerator:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    def _extract_procedure(self, text: str) -> str:
        """从文本中精准提取 <PROCEDURE> 标签内的内容。"""
        try:
            match = re.search(r'<PROCEDURE>(.*?)</PROCEDURE>', text, re.DOTALL)
            return match.group(1).strip() if match else text.strip()
        except Exception:
            return text.strip()

    def generate_individual_pseudocodes(self, new_question, retrieved_info, num_versions=3):
        """
        为单个问题批量生成多个版本的伪代码。
        这是一个内部批量操作。
        """
        knowledge_points_str = "\n".join([f"- {p['point']}: {p['description']}" for p in retrieved_info.get('knowledge_points', [])]) or "无"
        pitfalls_str = "\n".join([f"- {p}" for p in retrieved_info.get('common_pitfalls', [])]) or "无"

        content = PSEUDOCODE_GENERATION_PROMPT.format(
            new_question_prompt=new_question,
            knowledge_points=knowledge_points_str,
            common_pitfalls=pitfalls_str
        )
        messages = [{"role": "user", "content": content}]
        messages_batch = [messages for _ in range(num_versions)]
        
        llm_outputs = self.llm.generate_with_think_and_parse_batch(messages_batch)
        
        pseudocodes = [self._extract_procedure(output['answer']) for output in llm_outputs]
        return pseudocodes

    def synthesize_pseudocode(self, new_question, pseudocodes):
        """
        为单个问题汇总多个伪代码版本。
        """
        if not pseudocodes: return ""
        if len(pseudocodes) == 1: return pseudocodes[0]

        p1 = pseudocodes[0] if len(pseudocodes) > 0 else "N/A"
        p2 = pseudocodes[1] if len(pseudocodes) > 1 else "N/A"
        p3 = pseudocodes[2] if len(pseudocodes) > 2 else "N/A"

        content = PSEUDOCODE_SYNTHESIS_PROMPT.format(
            question=new_question,
            pseudocode_1=p1,
            pseudocode_2=p2,
            pseudocode_3=p3
        )
        messages = [{"role": "user", "content": content}]
        
        # 调用批量接口处理单个任务
        final_output = self.llm.generate_with_think_and_parse_batch([messages])[0]
        
        final_pseudocode = self._extract_procedure(final_output['answer'])
        return final_pseudocode