# core_new/workflow.py

"""
现代 408 解题工作流引擎。

相比去年为弱开源模型设计的“先规划、多代码投票、自反思、fallback 仲裁”链路，
当前默认采用更适合强开源模型的轻量流程：

1. 检索候选知识与常见陷阱；
2. 本地模型一次性结构化推理；
3. 按需生成一份 Python 验证代码并执行；
4. 比较推理结果与代码验证结果；
5. 基于解题轨迹做后置知识点标注。

注意：Solver 只负责解题和验证；知识点标注只在解题完成后执行。
"""

import json
import logging
from typing import Dict, Any, Tuple

from .prompts import (
    ANSWER_VERIFICATION_PROMPT,
    CODE_VERIFICATION_PROMPT,
    DIRECT_ANSWER_PROMPT,
    MODERN_REASONING_PROMPT,
    QUESTION_CLASSIFICATION_PROMPT,
    TRACE_ANNOTATION_PROMPT,
)
from .retrieval_api_client import RetrievalAPIClient
from .utils import execute_code, parse_code
from llm_providers_new.base import BaseLLMProvider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class IterativeSolverWorkflow:
    """
    现代解题工作流。

    类名暂时保持 IterativeSolverWorkflow，避免破坏 server/batch runner 等既有导入。
    实际默认实现已经从旧的 iterative solver 改为 reasoning-first solver。
    """

    def __init__(self, llm_provider: BaseLLMProvider, retriever_client: RetrievalAPIClient):
        self.llm = llm_provider
        self.retriever = retriever_client
        logger.info("IterativeSolverWorkflow initialized in modern reasoning-first mode.")

    async def _retrieve_and_aggregate(self, prompt: str) -> Tuple[str, Dict[str, Any]]:
        """检索候选知识点与常见陷阱。检索结果只作为候选，不直接等同最终标注。"""
        logger.info(f"Retrieving knowledge for prompt: {prompt[:70]}...")
        retrieved_results = self.retriever.search(prompt, k=3)

        aggregated_knowledge: Dict[str, Any] = {"knowledge_points": [], "common_pitfalls": []}
        if retrieved_results:
            for res in retrieved_results:
                aggregated_knowledge["knowledge_points"].extend(res.get("knowledge_points", []))
                aggregated_knowledge["common_pitfalls"].extend(res.get("common_pitfalls", []))

            unique_points = []
            seen_points = set()
            for point in aggregated_knowledge["knowledge_points"]:
                key = json.dumps(point, ensure_ascii=False, sort_keys=True)
                if key not in seen_points:
                    unique_points.append(point)
                    seen_points.add(key)
            aggregated_knowledge["knowledge_points"] = unique_points
            aggregated_knowledge["common_pitfalls"] = list(set(aggregated_knowledge["common_pitfalls"]))

        knowledge_str = "\n".join(
            [f"- {p.get('point', '')}: {p.get('description', '')}" for p in aggregated_knowledge.get("knowledge_points", [])]
        ) or "无相关知识点"
        pitfalls_str = "\n".join(
            [f"- {p}" for p in aggregated_knowledge.get("common_pitfalls", [])]
        ) or "无常见陷阱"

        return f"知识点:\n{knowledge_str}\n\n常见陷阱:\n{pitfalls_str}", aggregated_knowledge

    async def _classify_question(self, prompt: str) -> str:
        """轻量判断题目是否需要推理。失败时默认走 reasoning。"""
        logger.info(f"Classifying question: {prompt[:70]}...")
        messages = [[{"role": "user", "content": QUESTION_CLASSIFICATION_PROMPT.format(question_prompt=prompt)}]]
        json_outputs = await self.llm.generate_json_batch(messages)
        if json_outputs and isinstance(json_outputs[0], dict):
            q_type = json_outputs[0].get("question_type", "reasoning")
            if q_type in {"direct", "reasoning"}:
                logger.info(f"Question classified as: {q_type}")
                return q_type
        logger.warning("Failed to classify question, defaulting to reasoning.")
        return "reasoning"

    async def _solve_direct(self, prompt: str, knowledge_str: str, aggregated_knowledge: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
        """直接回答纯概念类问题。"""
        logger.info(f"Executing direct answer path for: {prompt[:70]}...")
        content = DIRECT_ANSWER_PROMPT.format(
            new_question_prompt=prompt,
            knowledge_and_pitfalls=knowledge_str,
        )
        outputs = await self.llm.generate_with_think_and_parse_batch(
            [[{"role": "user", "content": content}]],
            enable_thinking=False,
            max_token=max_tokens,
        )
        return {
            "response": outputs[0].get("answer", ""),
            "metadata": {
                "workflow": "direct",
                "question_type": "direct",
                "retrieved_knowledge": aggregated_knowledge,
            },
        }

    async def _solve_reasoning_only(self, prompt: str, knowledge_str: str, aggregated_knowledge: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
        """单次结构化推理。该阶段不写代码、不标注知识点。"""
        logger.info(f"Executing modern reasoning path for: {prompt[:70]}...")
        content = MODERN_REASONING_PROMPT.format(
            question=prompt,
            knowledge_and_pitfalls=knowledge_str,
        )
        json_outputs = await self.llm.generate_json_batch([[{"role": "user", "content": content}]])
        reasoning_json = json_outputs[0] if json_outputs and isinstance(json_outputs[0], dict) else None

        if not reasoning_json:
            logger.warning("Reasoning JSON generation failed. Falling back to plain direct generation.")
            fallback = await self._solve_direct(prompt, knowledge_str, aggregated_knowledge, max_tokens)
            return {
                "response": fallback.get("response", ""),
                "metadata": {
                    "workflow": "reasoning_only_fallback",
                    "question_type": "reasoning",
                    "reasoning_json": None,
                    "fallback": fallback,
                    "retrieved_knowledge": aggregated_knowledge,
                },
            }

        response = reasoning_json.get("final_response") or reasoning_json.get("answer") or ""
        return {
            "response": response,
            "metadata": {
                "workflow": "reasoning_only",
                "question_type": "reasoning",
                "reasoning_json": reasoning_json,
                "retrieved_knowledge": aggregated_knowledge,
            },
        }

    async def _run_code_verification(self, prompt: str, reasoning_result: Dict[str, Any]) -> Dict[str, Any]:
        """按需生成一份最小验证代码并执行。"""
        reasoning_json = reasoning_result.get("metadata", {}).get("reasoning_json") or {}
        needs_code = bool(reasoning_json.get("needs_code_verification", False))
        targets = reasoning_json.get("verification_targets", [])

        if not needs_code:
            return {
                "status": "skipped",
                "reason": "Reasoning branch indicated that code verification is unnecessary.",
                "verification_targets": targets,
                "code": "",
                "output": None,
                "error": None,
            }

        logger.info("Generating a single minimal code verifier...")
        content = CODE_VERIFICATION_PROMPT.format(
            question=prompt,
            reasoning_json=json.dumps(reasoning_json, ensure_ascii=False, indent=2),
            verification_targets=json.dumps(targets, ensure_ascii=False, indent=2),
        )
        outputs = await self.llm.generate_with_think_and_parse_batch(
            [[{"role": "user", "content": content}]],
            enable_thinking=False,
        )
        code = parse_code(outputs[0].get("answer", ""))

        if not code.strip():
            return {
                "status": "skipped",
                "reason": "Model did not produce executable verification code.",
                "verification_targets": targets,
                "code": "",
                "output": None,
                "error": None,
            }

        result = execute_code(code)
        return {
            "status": "success" if result.get("error") is None else "failed",
            "reason": None,
            "verification_targets": targets,
            "code": code,
            "output": result.get("output"),
            "error": result.get("error"),
        }

    async def _verify_reasoning_and_code(self, prompt: str, reasoning_result: Dict[str, Any], code_result: Dict[str, Any]) -> Dict[str, Any]:
        """比较推理结果和代码验证结果。该阶段不做知识点标注。"""
        logger.info("Verifying consistency between reasoning and code verification...")
        content = ANSWER_VERIFICATION_PROMPT.format(
            question=prompt,
            reasoning_result=json.dumps(reasoning_result, ensure_ascii=False, indent=2),
            code_result=json.dumps(code_result, ensure_ascii=False, indent=2),
        )
        json_outputs = await self.llm.generate_json_batch([[{"role": "user", "content": content}]])
        verification = json_outputs[0] if json_outputs and isinstance(json_outputs[0], dict) else None
        if verification:
            verification.setdefault("consistency", "unknown")
            verification.setdefault("preferred_source", "uncertain")
            verification.setdefault("needs_remote_judge", verification.get("consistency") not in {"consistent", "code_skipped"})
            return verification

        return {
            "consistency": "unknown",
            "preferred_source": "uncertain",
            "needs_remote_judge": True,
            "final_answer": None,
            "reason": "Verification model did not return valid JSON.",
            "disagreements": [],
        }

    async def _annotate_from_traces(
        self,
        prompt: str,
        aggregated_knowledge: Dict[str, Any],
        reasoning_result: Dict[str, Any],
        code_result: Dict[str, Any],
        verification: Dict[str, Any],
    ) -> Dict[str, Any]:
        """后置知识点标注。该阶段不重新解题。"""
        logger.info("Annotating knowledge points from solving traces...")
        content = TRACE_ANNOTATION_PROMPT.format(
            question=prompt,
            retrieved_candidates=json.dumps(aggregated_knowledge, ensure_ascii=False, indent=2),
            reasoning_result=json.dumps(reasoning_result, ensure_ascii=False, indent=2),
            code_result=json.dumps(code_result, ensure_ascii=False, indent=2),
            verification=json.dumps(verification, ensure_ascii=False, indent=2),
        )
        json_outputs = await self.llm.generate_json_batch([[{"role": "user", "content": content}]])
        annotation = json_outputs[0] if json_outputs and isinstance(json_outputs[0], dict) else None
        if annotation:
            annotation.setdefault("label_confidence", 0.0)
            annotation.setdefault("review_status", "needs_review" if annotation.get("label_confidence", 0.0) < 0.75 else "auto_pass")
            return annotation

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
            "annotation_error": "Annotation model did not return valid JSON.",
        }

    async def _solve_modern(self, prompt: str, knowledge_str: str, aggregated_knowledge: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
        """默认现代流程：结构化推理 -> 按需代码验证 -> 一致性检查 -> 后置标注。"""
        reasoning_result = await self._solve_reasoning_only(prompt, knowledge_str, aggregated_knowledge, max_tokens)
        code_result = await self._run_code_verification(prompt, reasoning_result)
        verification = await self._verify_reasoning_and_code(prompt, reasoning_result, code_result)
        annotation = await self._annotate_from_traces(
            prompt,
            aggregated_knowledge,
            reasoning_result,
            code_result,
            verification,
        )

        preferred_source = verification.get("preferred_source")
        if preferred_source == "code" and code_result.get("output"):
            final_response = verification.get("final_answer") or code_result.get("output")
        else:
            final_response = verification.get("final_answer") or reasoning_result.get("response", "")

        return {
            "response": final_response,
            "metadata": {
                "workflow": "modern_reasoning_verified_annotated",
                "question_type": "reasoning",
                "reasoning_result": reasoning_result,
                "code_result": code_result,
                "verification": verification,
                "annotation": annotation,
                "retrieved_knowledge": aggregated_knowledge,
            },
        }

    async def run(self, prompt: str, workflow_mode: str = "full", max_tokens: int = 8192) -> Dict[str, Any]:
        """
        执行单个问题的完整求解流程。

        workflow_mode:
        - direct: 强制直接回答；
        - full: 自动路由，direct 或 modern；
        - hybrid / modern: 强制执行现代推理+验证+标注流程。
        """
        logger.info(f"Starting workflow '{workflow_mode}' for prompt: {prompt[:70]}...")
        try:
            knowledge_str, aggregated_knowledge = await self._retrieve_and_aggregate(prompt)

            if workflow_mode == "direct":
                result = await self._solve_direct(prompt, knowledge_str, aggregated_knowledge, max_tokens=max_tokens)
            elif workflow_mode in {"hybrid", "modern"}:
                result = await self._solve_modern(prompt, knowledge_str, aggregated_knowledge, max_tokens=max_tokens)
            elif workflow_mode == "full":
                q_type = await self._classify_question(prompt)
                if q_type == "direct":
                    result = await self._solve_direct(prompt, knowledge_str, aggregated_knowledge, max_tokens=max_tokens)
                else:
                    result = await self._solve_modern(prompt, knowledge_str, aggregated_knowledge, max_tokens=max_tokens)
            else:
                raise ValueError(f"Unknown workflow mode: {workflow_mode}")

            logger.info(f"Workflow '{workflow_mode}' completed successfully.")
            return result

        except Exception as e:
            logger.error(f"An unexpected error occurred in the workflow: {e}", exc_info=True)
            return {
                "response": f"Error: An internal error occurred during processing. Details: {e}",
                "metadata": {"workflow": "failed_unexpectedly"},
            }
