# core/interactive_solver.py

from core.retriever import Retriever
from core.pseudocode_generator import PseudocodeGenerator
from core.solver import Solver
from core.prompts import QUESTION_CLASSIFICATION_PROMPT, DIRECT_ANSWER_PROMPT
import json

class InteractiveSolver:
    def __init__(self, llm_provider, retriever: Retriever):
        """
        初始化一个可以解决单个问题的引擎。
        llm_provider 可以是 LLMService 或 VLLMAPIClient。
        """
        self.llm = llm_provider
        self.retriever = retriever
        self.pseudocode_gen = PseudocodeGenerator(self.llm)
        self.solver_engine = Solver(self.llm)

    def _classify_question(self, question: str) -> str:
        """对单个问题进行分类"""
        content = QUESTION_CLASSIFICATION_PROMPT.format(question_prompt=question)
        messages = [{"role": "user", "content": content}]
        json_output = self.llm.generate_json_batch([messages])[0]
        q_type = json_output.get("question_type", "procedural") if isinstance(json_output, dict) else "procedural"
        return q_type

    def _solve_direct_question(self, question: str, retrieved_info: dict) -> dict:
        """处理直接回答型问题"""
        knowledge_points_str = "\n".join([f"- {p['point']}: {p['description']}" for p in retrieved_info.get('knowledge_points', [])]) or "无"
        content = DIRECT_ANSWER_PROMPT.format(
            new_question_prompt=question,
            knowledge_points=knowledge_points_str
        )
        messages = [{"role": "user", "content": content}]
        llm_output = self.llm.generate_with_think_and_parse_batch([messages], enable_thinking=True)[0]
        
        return {
            "prompt": question,
            "response": llm_output['answer'],
            "metadata": {
                "question_type": "direct",
                "retrieved_knowledge": retrieved_info,
                "reasoning_trace": {
                    "stage_1_retrieval": retrieved_info,
                    "stage_2_direct_answer_generation_think": llm_output['think']
                }
            }
        }

    def _solve_procedural_question(self, question: str, retrieved_info: dict) -> dict:
        """处理程序化计算型问题"""
        # 1. 生成伪代码 (简化为单版本生成，可按需改回多版本合成)
        individual_pseudocodes = self.pseudocode_gen.generate_individual_pseudocodes(question, retrieved_info, num_versions=1)
        final_pseudocode = individual_pseudocodes[0] if individual_pseudocodes else "Error: Failed to generate pseudocode."

        # 2. 解题与验证
        solutions_sq_list = self.solver_engine.solve_by_subquestion_batch(question, final_pseudocode, num_solutions=3)
        final_solution_subquestions = solutions_sq_list[0] if solutions_sq_list else ["Error: Failed to generate solution."]
        was_reconstructed = False
        
        is_consistent, inconsistent_info, _ = self.solver_engine.check_subquestions_consistency(solutions_sq_list)
        if not is_consistent and inconsistent_info:
            was_reconstructed = True
            executable_code, code_output, error = self.solver_engine.generate_and_run_code(question, final_pseudocode)
            if not error:
                for sq_info in inconsistent_info:
                    if sq_info.get("sq_index", -1) != -1:
                        reconstructed_sq = self.solver_engine.reconstruct_subquestion(sq_info, executable_code, code_output)
                        final_solution_subquestions[sq_info['sq_index']] = reconstructed_sq

        final_answer_text = "\n[end_of_subquestion]\n".join(final_solution_subquestions)

        return {
            "prompt": question,
            "response": final_answer_text,
            "metadata": {
                "question_type": "procedural",
                "retrieved_knowledge": retrieved_info,
                "consensus_pseudocode": final_pseudocode,
                "was_reconstructed": was_reconstructed
            }
        }

    def solve(self, question: str) -> dict:
        """
        解决一个用户提出的任意问题，并返回结构化的解答过程。
        """
        # 阶段 1: 检索与知识聚合
        retrieved_results = self.retriever.search(question, k=3)
        aggregated_knowledge = {'knowledge_points': [], 'common_pitfalls': []}
        if retrieved_results:
            for res in retrieved_results:
                aggregated_knowledge['knowledge_points'].extend(res.get('knowledge_points', []))
                aggregated_knowledge['common_pitfalls'].extend(res.get('common_pitfalls', []))
            aggregated_knowledge['knowledge_points'] = [dict(t) for t in {tuple(d.items()) for d in aggregated_knowledge['knowledge_points']}]
            aggregated_knowledge['common_pitfalls'] = list(set(aggregated_knowledge['common_pitfalls']))

        # 阶段 1.5: 分类与分流
        question_type = self._classify_question(question)

        # 阶段 2: 根据类型选择解题路径
        if question_type == "direct":
            return self._solve_direct_question(question, aggregated_knowledge)
        else: # "procedural"
            return self._solve_procedural_question(question, aggregated_knowledge)