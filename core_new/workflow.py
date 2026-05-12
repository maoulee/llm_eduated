# core_new/workflow.py

"""
核心工作流引擎模块。
定义了 IterativeSolverWorkflow 类，该类封装了从问题接收到最终答案生成的完整、
多Agent、自洽的求解流程。
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Tuple

# 导入重构后的核心组件
from .prompts import (
    FRAMEWORK_GENERATION_PROMPT,
    DIVERSE_CODE_GENERATION_PROMPT,
    CODE_SELF_REFLECTION_PROMPT,
    FALLBACK_DECISION_PROMPT,
    FINAL_SYNTHESIS_PROMPT,
    DIRECT_ANSWER_PROMPT,
    QUESTION_CLASSIFICATION_PROMPT,
    INDEPENDENT_REASONING_PROMPT,
    ANSWER_VERIFICATION_PROMPT,
    TRACE_ANNOTATION_PROMPT,
)
from .retrieval_api_client import RetrievalAPIClient
from .workflow_components import (
    find_majority_result,
    format_divergent_codes_for_reflection
)
from .utils import parse_code, execute_code, parse_json_from_llm_output

# 导入统一的Provider抽象基类
from llm_providers_new.base import BaseLLMProvider

# 配置日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class IterativeSolverWorkflow:
    """
    一个异步的、迭代式的问题求解工作流引擎。
    它整合了检索、规划、执行、反思、验证、标注和合成等多个阶段。
    """

    def __init__(self, llm_provider: BaseLLMProvider, retriever_client: RetrievalAPIClient):
        """
        初始化工作流引擎。

        Args:
            llm_provider: 一个实现了 BaseLLMProvider 接口的LLM服务提供者实例。
            retriever_client: 一个 RetrievalAPIClient 实例。
        """
        self.llm = llm_provider
        self.retriever = retriever_client
        logger.info("IterativeSolverWorkflow initialized.")

    async def _retrieve_and_aggregate(self, prompt: str) -> Tuple[str, Dict]:
        """
        第一阶段：为单个问题进行知识检索和聚合。

        Returns:
            一个元组 (knowledge_and_pitfalls_str, aggregated_knowledge_dict)。
        """
        logger.info(f"Retrieving knowledge for prompt: {prompt[:70]}...")
        # 检索客户端的 search 方法可以处理单个字符串
        retrieved_results = self.retriever.search(prompt, k=3)
        
        aggregated_knowledge = {'knowledge_points': [], 'common_pitfalls': []}
        if retrieved_results:
            for res in retrieved_results:
                aggregated_knowledge['knowledge_points'].extend(res.get('knowledge_points', []))
                aggregated_knowledge['common_pitfalls'].extend(res.get('common_pitfalls', []))
            
            # 去重
            aggregated_knowledge['knowledge_points'] = [
                dict(t) for t in {tuple(d.items()) for d in aggregated_knowledge['knowledge_points']}
            ]
            aggregated_knowledge['common_pitfalls'] = list(set(aggregated_knowledge['common_pitfalls']))
        
        knowledge_str = "\n".join(
            [f"- {p.get('point', '')}: {p.get('description', '')}" for p in aggregated_knowledge.get('knowledge_points', [])]
        ) or "无相关知识点"
        
        pitfalls_str = "\n".join(
            [f"- {p}" for p in aggregated_knowledge.get('common_pitfalls', [])]
        ) or "无常见陷阱"

        knowledge_and_pitfalls_str = f"知识点:\n{knowledge_str}\n\n常见陷阱:\n{pitfalls_str}"
        
        return knowledge_and_pitfalls_str, aggregated_knowledge

    async def _classify_question(self, prompt: str) -> str:
        """
        对问题进行分类，以决定解题路径。
        """
        logger.info(f"Classifying question: {prompt[:70]}...")
        messages = [[{"role": "user", "content": QUESTION_CLASSIFICATION_PROMPT.format(question_prompt=prompt)}]]
        
        json_outputs = await self.llm.generate_json_batch(messages)
        
        if json_outputs and isinstance(json_outputs[0], dict):
            q_type = json_outputs[0].get("question_type", "procedural")
            logger.info(f"Question classified as: '{q_type}'")
            return q_type
        
        logger.warning("Failed to classify question, defaulting to 'procedural'.")
        return "procedural"

    async def _solve_direct(self, prompt: str, knowledge_str: str, aggregated_knowledge: Dict, max_tokens: int) -> Dict:
        """
        执行直接回答路径。
        """
        logger.info(f"Executing direct answer path for: {prompt[:70]}...")
        content = DIRECT_ANSWER_PROMPT.format(
            new_question_prompt=prompt,
            knowledge_and_pitfalls=knowledge_str
        )
        messages = [[{"role": "user", "content": content}]]
        
        # 直接回答通常不需要思考模式
        outputs = await self.llm.generate_with_think_and_parse_batch(messages, enable_thinking=False, max_token=max_tokens)
        
        return {
            "response": outputs[0]['answer'],
            "metadata": {
                "workflow": "direct",
                "question_type": "direct",
                "retrieved_knowledge": aggregated_knowledge
            }
        }

    async def _solve_reasoning_only(self, prompt: str, knowledge_str: str, aggregated_knowledge: Dict, max_tokens: int) -> Dict:
        """
        独立推理分支：只让本地模型进行自然语言推理和作答，不生成代码、不做知识点标注。
        """
        logger.info(f"Executing independent reasoning path for: {prompt[:70]}...")
        content = INDEPENDENT_REASONING_PROMPT.format(
            question=prompt,
            knowledge_and_pitfalls=knowledge_str
        )
        messages = [[{"role": "user", "content": content}]]
        outputs = await self.llm.generate_with_think_and_parse_batch(
            messages,
            enable_thinking=True,
            max_token=max_tokens
        )
        raw_output = outputs[0]
        return {
            "response": raw_output.get('answer', ''),
            "metadata": {
                "workflow": "reasoning_only",
                "question_type": "reasoning",
                "raw_output": raw_output,
                "retrieved_knowledge": aggregated_knowledge
            }
        }
    
    async def _solve_procedural(self, prompt: str, knowledge_str: str, aggregated_knowledge: Dict, max_tokens: int = 8192) -> Dict:
        """
        执行核心的、迭代式的程序化解题路径。
        """
        logger.info(f"Executing procedural iterative path for: {prompt[:70]}...")
        # 1. 生成解题规划 (Framework Generation)
        logger.info("Step 1: Generating solving plan...")
        plan_content = FRAMEWORK_GENERATION_PROMPT.format(question=prompt, knowledge_and_pitfalls=knowledge_str)
        plan_messages = [[{"role": "user", "content": plan_content}]]
        framework_outputs = await self.llm.generate_with_think_and_parse_batch(plan_messages, enable_thinking=True, max_token=6000)
        
        solving_plan_str = framework_outputs[0]['answer']
        solving_plan = parse_json_from_llm_output(solving_plan_str)

        if solving_plan is None:
            logger.error("Failed to parse a valid solving plan JSON.")
            return {
                "response": "Error: Failed to generate a valid solving plan.",
                "metadata": {
                    "workflow": "procedural_iterative_failed",
                    "raw_plan_output": solving_plan_str,
                    "retrieved_knowledge": aggregated_knowledge
                }
            }

        # 2. 迭代执行每个子问题
        execution_context = "# Execution context starts here.\n"
        full_trace = ""
        structured_trace: List[Dict[str, Any]] = []
        all_steps_succeeded = True

        for subquestion_key, steps in solving_plan.items():
            logger.info(f"Step 2: Solving sub-problem '{subquestion_key}'...")
            subproblem_framework = f"Instructions for {subquestion_key}:\n" + "\n".join([f"- {s['step']}: {s['core_operation']}" for s in steps])
            step_trace: Dict[str, Any] = {
                "subquestion_key": subquestion_key,
                "framework_steps": steps,
                "subproblem_framework": subproblem_framework,
                "code_candidates": [],
                "selection": {
                    "strategy": None,
                    "majority_votes": 0,
                    "reason": None
                }
            }
            
            # 2a. 生成多种代码方案
            logger.info("  - Generating 3 diverse code versions...")
            code_gen_content = DIVERSE_CODE_GENERATION_PROMPT.format(
                original_question=prompt,
                execution_context=execution_context,
                subproblem_framework=subproblem_framework
            )
            code_gen_messages = [[{"role": "user", "content": code_gen_content}] for _ in range(3)]
            code_gen_outputs = await self.llm.generate_with_think_and_parse_batch(code_gen_messages, enable_thinking=False)
            code_candidates = [parse_code(out['answer']) for out in code_gen_outputs]

            # 2b. 执行并投票
            logger.info("  - Executing and voting on code versions...")
            step_exec_results = [execute_code(code, execution_context) for code in code_candidates]
            for i, result in enumerate(step_exec_results):
                step_trace["code_candidates"].append({
                    "index": i + 1,
                    "code": result.get('code', code_candidates[i] if i < len(code_candidates) else ''),
                    "output": result.get('output'),
                    "error": result.get('error')
                })

            majority_result, majority_votes = find_majority_result(step_exec_results)
            
            best_code_for_step, best_result_for_step = None, None

            if majority_result:
                logger.info("  - Majority consensus found. Proceeding with the majority result.")
                best_code_for_step, best_result_for_step = majority_result['code'], majority_result
                step_trace["selection"] = {
                    "strategy": "majority_vote",
                    "majority_votes": majority_votes,
                    "reason": "At least two independently generated code versions produced the same comparable output."
                }
            else:
                logger.warning("  - No majority consensus. Activating self-reflection and correction.")
                successful_results = [r for r in step_exec_results if r['error'] is None and r['output']]
                
                if successful_results:
                    # 2c. 反思与修正
                    analysis_str = format_divergent_codes_for_reflection(successful_results)
                    reflection_content = CODE_SELF_REFLECTION_PROMPT.format(
                        original_question=prompt,
                        subproblem_framework=subproblem_framework,
                        execution_context=execution_context,
                        divergent_codes_analysis=analysis_str
                    )
                    reflection_messages = [[{"role": "user", "content": reflection_content}]]
                    reflection_outputs = await self.llm.generate_with_think_and_parse_batch(reflection_messages, enable_thinking=False)
                    revised_code = parse_code(reflection_outputs[0]['answer'])
                    
                    if revised_code:
                        revised_result = execute_code(revised_code, execution_context)
                        step_trace["reflection"] = {
                            "revised_code": revised_code,
                            "output": revised_result.get('output'),
                            "error": revised_result.get('error')
                        }
                        if revised_result['error'] is None:
                            logger.info("  - Self-correction successful.")
                            best_code_for_step, best_result_for_step = revised_code, revised_result
                            step_trace["selection"] = {
                                "strategy": "self_reflection",
                                "majority_votes": 0,
                                "reason": "Initial code outputs diverged; a reflected revised implementation executed successfully."
                            }
                    
                    # 2d. 仲裁与回退
                    if best_code_for_step is None:
                        logger.warning("  - Self-correction failed. Activating arbiter for fallback.")
                        fallback_content = FALLBACK_DECISION_PROMPT.format(
                            original_question=prompt,
                            subproblem_framework=subproblem_framework,
                            successful_solutions_analysis=analysis_str
                        )
                        decision_json_list = await self.llm.generate_json_batch([[{"role": "user", "content": fallback_content}]])
                        decision = decision_json_list[0] if decision_json_list else {}
                        best_index = int(decision.get("best_fallback_index", 1)) - 1 if decision else 0
                        best_index = max(0, min(best_index, len(successful_results) - 1))
                        best_code_for_step = successful_results[best_index]['code']
                        best_result_for_step = successful_results[best_index]
                        step_trace["selection"] = {
                            "strategy": "fallback_arbiter",
                            "majority_votes": 0,
                            "reason": decision.get("reasoning", "Arbiter selected the most plausible successful code candidate.") if decision else "Arbiter fallback selected the first successful code candidate."
                        }
                        logger.info(f"  - Arbiter chose fallback index: {best_index + 1}")

            # 检查当前步骤是否成功解决
            if best_code_for_step is None:
                logger.error(f"Failed to solve sub-problem '{subquestion_key}'. Aborting workflow for this question.")
                step_trace["selection"]["strategy"] = "failed"
                structured_trace.append(step_trace)
                all_steps_succeeded = False
                break

            # 2e. 更新上下文
            step_trace["selected_code"] = best_code_for_step
            step_trace["selected_output"] = best_result_for_step.get('output')
            step_trace["selected_error"] = best_result_for_step.get('error')
            structured_trace.append(step_trace)

            execution_context += f"\n# --- Code for {subquestion_key} ---\n{best_code_for_step}\n"
            full_trace += f"--- {subquestion_key} ---\n[Code]:\n{best_code_for_step}\n[Result]:\n{best_result_for_step['output']}\n\n"
        
        # 3. 最终合成
        if all_steps_succeeded:
            logger.info("Step 3: All sub-problems solved. Synthesizing final answer...")
            synthesis_content = FINAL_SYNTHESIS_PROMPT.format(original_question=prompt, full_execution_trace=full_trace)
            final_answer_output = await self.llm.generate_with_think_and_parse_batch(
                [[{"role": "user", "content": synthesis_content}]],
                enable_thinking=False,
                max_token=max_tokens
            )
            return {
                "response": final_answer_output[0]['answer'],
                "metadata": {
                    "workflow": "procedural_iterative",
                    "question_type": "procedural",
                    "trace": full_trace,
                    "structured_trace": structured_trace,
                    "plan": solving_plan,
                    "retrieved_knowledge": aggregated_knowledge
                }
            }
        else:
            return {
                "response": "Error: Failed during the iterative solving process.",
                "metadata": {
                    "workflow": "procedural_iterative_failed",
                    "question_type": "procedural",
                    "trace": full_trace,
                    "structured_trace": structured_trace,
                    "plan": solving_plan,
                    "retrieved_knowledge": aggregated_knowledge
                }
            }

    async def _verify_reasoning_and_code(self, prompt: str, reasoning_result: Dict, code_result: Dict) -> Dict:
        """
        对独立推理分支和代码验证分支进行一致性检查。
        这里只做验证和仲裁信号生成，不做知识点标注。
        """
        logger.info("Verifying consistency between reasoning answer and code-backed answer...")
        content = ANSWER_VERIFICATION_PROMPT.format(
            question=prompt,
            reasoning_answer=reasoning_result.get("response", ""),
            code_answer=code_result.get("response", ""),
            code_trace=json.dumps(code_result.get("metadata", {}).get("structured_trace", []), ensure_ascii=False, indent=2)
        )
        json_outputs = await self.llm.generate_json_batch([[{"role": "user", "content": content}]])
        verification = json_outputs[0] if json_outputs and isinstance(json_outputs[0], dict) else None
        if verification:
            verification.setdefault("consistency", "unknown")
            verification.setdefault("preferred_source", "uncertain")
            verification.setdefault("needs_remote_judge", verification.get("consistency") != "consistent")
            return verification

        logger.warning("Verification output was not valid JSON. Falling back to conservative verification metadata.")
        return {
            "consistency": "unknown",
            "preferred_source": "uncertain",
            "needs_remote_judge": True,
            "final_answer": None,
            "reason": "Verification model did not return valid JSON.",
            "disagreements": []
        }

    async def _annotate_from_traces(
        self,
        prompt: str,
        aggregated_knowledge: Dict,
        reasoning_result: Dict,
        code_result: Dict,
        verification: Dict
    ) -> Dict:
        """
        后置知识点标注：基于原题、推理结果、代码验证轨迹和一致性检查结果进行标注。
        注意：该阶段不重新解题，只做知识点/难度/陷阱/能力要求标注。
        """
        logger.info("Annotating knowledge points from verified traces...")
        content = TRACE_ANNOTATION_PROMPT.format(
            question=prompt,
            retrieved_candidates=json.dumps(aggregated_knowledge, ensure_ascii=False, indent=2),
            reasoning_trace=json.dumps(reasoning_result, ensure_ascii=False, indent=2),
            code_trace=json.dumps(code_result.get("metadata", {}), ensure_ascii=False, indent=2),
            verification=json.dumps(verification, ensure_ascii=False, indent=2)
        )
        json_outputs = await self.llm.generate_json_batch([[{"role": "user", "content": content}]])
        annotation = json_outputs[0] if json_outputs and isinstance(json_outputs[0], dict) else None
        if annotation:
            annotation.setdefault("label_confidence", 0.0)
            annotation.setdefault("review_status", "needs_review" if annotation.get("label_confidence", 0.0) < 0.75 else "auto_pass")
            return annotation

        logger.warning("Annotation output was not valid JSON. Marking annotation as needs_review.")
        return {
            "subject": "unknown",
            "primary_knowledge_points": [],
            "secondary_knowledge_points": [],
            "difficulty": None,
            "exam_level": "unknown",
            "question_pattern": "unknown",
            "common_error_tags": [],
            "reasoning_requirements": [],
            "label_confidence": 0.0,
            "review_status": "needs_review",
            "annotation_error": "Annotation model did not return valid JSON."
        }

    async def _solve_hybrid_verified(self, prompt: str, knowledge_str: str, aggregated_knowledge: Dict, max_tokens: int) -> Dict:
        """
        新的混合工作流：
        1. 本地模型独立推理；
        2. 本地模型并行生成代码并执行验证；
        3. 对两个答案做一致性验证；
        4. 基于推理/代码轨迹进行后置知识点标注。
        """
        logger.info(f"Executing hybrid reasoning+code verification workflow for: {prompt[:70]}...")
        reasoning_task = self._solve_reasoning_only(prompt, knowledge_str, aggregated_knowledge, max_tokens)
        code_task = self._solve_procedural(prompt, knowledge_str, aggregated_knowledge, max_tokens=max_tokens)
        reasoning_result, code_result = await asyncio.gather(reasoning_task, code_task)

        verification = await self._verify_reasoning_and_code(prompt, reasoning_result, code_result)
        annotation = await self._annotate_from_traces(
            prompt,
            aggregated_knowledge,
            reasoning_result,
            code_result,
            verification
        )

        preferred_source = verification.get("preferred_source")
        if preferred_source == "reasoning":
            final_response = reasoning_result.get("response", "")
        elif preferred_source == "code":
            final_response = code_result.get("response", "")
        else:
            final_response = verification.get("final_answer") or code_result.get("response") or reasoning_result.get("response", "")

        return {
            "response": final_response,
            "metadata": {
                "workflow": "hybrid_verified_annotated",
                "question_type": "hybrid",
                "reasoning_result": reasoning_result,
                "code_result": code_result,
                "verification": verification,
                "annotation": annotation,
                "retrieved_knowledge": aggregated_knowledge
            }
        }

    async def run(self, prompt: str, workflow_mode: str = "full", max_tokens: int = 8192) -> Dict:
        """
        执行单个问题的完整求解流程。

        Args:
            prompt (str): 用户输入的问题。
            workflow_mode (str): 'full' (智能路由)、'direct' (强制直接回答)、'hybrid' (推理+代码验证+标注)。
            max_tokens (int): 传给模型的最大生成长度。

        Returns:
            一个包含 "response" 和 "metadata" 的字典，代表最终结果。
        """
        logger.info(f"Starting workflow '{workflow_mode}' for prompt: {prompt[:70]}...")
        try:
            knowledge_str, aggregated_knowledge = await self._retrieve_and_aggregate(prompt)
            
            if workflow_mode == "direct":
                result = await self._solve_direct(prompt, knowledge_str, aggregated_knowledge, max_tokens=max_tokens)
            elif workflow_mode == "hybrid":
                result = await self._solve_hybrid_verified(prompt, knowledge_str, aggregated_knowledge, max_tokens=max_tokens)
            elif workflow_mode == "full":
                q_type = await self._classify_question(prompt)
                if q_type == "direct":
                    result = await self._solve_direct(prompt, knowledge_str, aggregated_knowledge, max_tokens=max_tokens)
                else:
                    result = await self._solve_procedural(prompt, knowledge_str, aggregated_knowledge, max_tokens=max_tokens)
            else:
                raise ValueError(f"Unknown workflow mode: {workflow_mode}")
            
            logger.info(f"Workflow '{workflow_mode}' completed successfully.")
            return result
        
        except Exception as e:
            logger.error(f"An unexpected error occurred in the workflow: {e}", exc_info=True)
            return {
                "response": f"Error: An internal error occurred during processing. Details: {e}",
                "metadata": {"workflow": "failed_unexpectedly"}
            }
