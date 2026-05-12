# run_solver_pipeline.py

import asyncio
import json
import logging
import argparse
import os
from tqdm import tqdm
# 导入所有需要的模块
from config import get_provider_config, settings
from llm_providers_new import get_llm_provider
from core_new.graph_retriever import KnowledgeGraphRetriever
from core_new.retrieval_api_client import RetrievalAPIClient
from core_new.utils import execute_code, parse_code
from typing import Dict, Any, List
# 新的、正确的导入
from kcard.planner import Planner
# --- 从统一的prompts模块导入所有需要的Prompts ---

from kcard.prompt import (
    PROMPT_B_PSEUDOCODE_PLANNING,
    PROMPT_C_CODE_EXECUTION, 
    PROMPT_D_FINAL_SYNTHESIS,
    PROMPT_E_QUESTION_CLASSIFICATION,
    PROMPT_F_DIRECT_ANSWER,
    PROMPT_G_DIRECT_ANSWER_ZERO_KNOWLEDGE,
    PROMPT_H_CODE_CORRECTION
)

# --- 配置日志 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def build_prompt_from_jsonl_data(q_data: Dict) -> str:
    """
    Builds a rich, descriptive prompt string from a specialized JSONL data object.
    This version intelligently injects the required answer format into the question itself.

    Args:
        q_data: A dictionary representing one line from the JSONL file.

    Returns:
        A formatted string to be used as input for the Solver Pipeline.
    """
    question_text = q_data.get("Question", "")
    if not question_text:
        return ""

    q_format = q_data.get("Format", "Open-ended")
    
    # --- 1. Start with the base question text ---
    prompt_parts = [question_text]

    # --- 2. Append options for multiple-choice questions ---
    if q_format == "Multiple-choice":
        options_parts = ["\n\n选项："]
        options_exist = False
        for key in sorted(q_data.keys()):
            if key in ["A", "B", "C", "D", "E"]:
                options_parts.append(f"{key}. {q_data[key]}")
                options_exist = True
        if options_exist:
            prompt_parts.append("\n".join(options_parts))
    
    # --- 3. Inject the format requirement into the prompt ---
    format_instruction = ""
    if q_format == "Multiple-choice":
        format_instruction = "\n\n(请分析问题和选项，并在最终答案中明确指出A, B, C, D中的哪一个选项是正确的。)"
    elif q_format == "Fill-in-the-blank":
        format_instruction = "\n\n(请计算出需要填入括号中的最终数值或内容。)"
    elif q_format == "Assertion":
        format_instruction = "\n\n(请判断该论述的正确性，并在最终答案中明确指出“True”或“False”。)"
    
    if format_instruction:
        prompt_parts.append(format_instruction)

    return "\n".join(prompt_parts)

def load_question_data(filepath: str) -> List[Dict]:
    """从文件加载问题数据，返回字典列表。"""
    if not os.path.exists(filepath):
        logger.error(f"Input file not found: {filepath}")
        return []
    
    question_data_list = []
    try:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.jsonl':
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        question_data_list.append(json.loads(line))
        else:
            logger.error(f"Unsupported file type for batch processing: {ext}. Please use .jsonl.")
            return []
    except Exception as e:
        logger.error(f"Failed to load file {filepath}: {e}", exc_info=True)
    
    logger.info(f"Loaded {len(question_data_list)} question data objects from {filepath}")
    return question_data_list

class SolverPipeline:
    """
    封装了完整的、带智能分流的 检索->规划->执行->合成 工作流。
    支持多种运行模式，包括 'full' 模式和 'direct_answer' 基线模式。
    """
    def __init__(self, retriever=None, planner=None, executor_llm=None, synthesizer_llm=None, classifier_llm=None, baseline_llm=None):
        """
        初始化 SolverPipeline。所有组件都是可选的，具体取决于所选的运行模式。
        """
        self.retriever = retriever
        self.planner = planner
        self.executor_llm = executor_llm
        self.synthesizer_llm = synthesizer_llm
        self.classifier_llm = classifier_llm
        self.baseline_llm = baseline_llm

    async def _classify_question(self, question: str) -> str:
        """使用LLM对问题进行分类，决定使用哪条路径。"""
        logger.info("--- [Stage 0: Classifying Question] ---")
        prompt = PROMPT_E_QUESTION_CLASSIFICATION.format(question=question)
        messages = [[{"role": "user", "content": prompt}]]
        json_outputs = await self.classifier_llm.generate_json_batch(messages)
        
        if json_outputs and isinstance(json_outputs[0], dict):
            q_type = json_outputs[0].get("question_type", "procedural_reasoning")
            logger.info(f"Question classified as: '{q_type}'")
            return q_type
        
        logger.warning("Failed to classify question, defaulting to 'procedural_reasoning'.")
        return "procedural_reasoning"

    # --- FIX: Added 'retrieval_mode' to the function signature ---
    async def _run_direct_path(self, question: str, full_trace: dict, retrieval_mode: str) -> str:
        """执行直接回答路径：检索 -> 直接合成。"""
        logger.info("--- [Executing Direct Answer Path] ---")
        # 1. 检索
        logger.info("  - Stage 1: Retrieving Knowledge...")
        kn_modules, constraints = await self.retriever.retrieve(question, mode=retrieval_mode)
        full_trace["retrieved_knowledge"] = {"kn_modules": kn_modules, "constraints": constraints}
        
        # 2. 直接合成
        logger.info("  - Stage 2: Synthesizing Direct Answer...")
        knowledge_str = json.dumps(full_trace["retrieved_knowledge"], ensure_ascii=False, indent=2)
        prompt = PROMPT_F_DIRECT_ANSWER.format(
            original_question=question,
            retrieved_knowledge_str=knowledge_str
        )
        messages = [[{"role": "user", "content": prompt}]]
        result = await self.synthesizer_llm.generate_with_think_and_parse_batch(messages, enable_thinking=False)
        return result[0]['answer']

    # --- FIX: Added 'retrieval_mode' to the function signature ---
    async def _run_procedural_path(self, question: str, full_trace: dict, retrieval_mode: str) -> str:
        """执行程序化推理路径：检索 -> 规划 -> 执行 -> 合成。"""
        logger.info("--- [Executing Procedural Reasoning Path] ---")
        # 1. 检索
        logger.info("  - Stage 1: Retrieving Knowledge...")
        kn_modules, constraints = await self.retriever.retrieve(question, mode=retrieval_mode)
        full_trace["retrieved_knowledge"] = {"kn_modules": kn_modules, "constraints": constraints}
        if not kn_modules:
            logger.warning("  - No relevant knowledge modules found. Planner may struggle.")
        
        # 2. 规划
        logger.info("  - Stage 2: Generating Solution Plan...")
        plan = await self.planner.generate_plan(question, kn_modules, constraints)
        full_trace["plan"] = plan
        if not plan: 
            raise ValueError("Failed to generate a valid plan.")

        # 3. 执行
        logger.info("  - Stage 3: Generating and Executing Code...")
        
        # 从完整知识列表中，只挑选出Planner承诺要使用的那些
        selected_names = set(plan["knowledge_selection"])
        knowledge_for_executor = {
            "universal_knowledge_modules": [
                mod for mod in kn_modules if mod.get("canonical_name") in selected_names
            ]
        }
        knowledge_json_str = json.dumps(knowledge_for_executor, ensure_ascii=False, indent=2)
        
        # Planner的plan部分
        plan_json_str = json.dumps(full_trace["plan"], ensure_ascii=False, indent=2)
        
        executable_code = ""
        exec_result = None
        
        # --- NEW: 引入重试循环 ---
        max_attempts = 3
        for attempt in range(max_attempts):
            logger.info(f"    - Attempt {attempt + 1}/{max_attempts}...")
            
            if attempt == 0:
                # 第一次尝试：正常生成代码
                prompt = PROMPT_C_CODE_EXECUTION.format(
                    question=question,
                    knowledge_modules_json=knowledge_json_str,
                    planner_plan_json=plan_json_str
                )
            else:
                # 后续尝试：使用修正Prompt
                logger.warning("    - Code execution failed. Attempting to correct...")
                prompt = PROMPT_H_CODE_CORRECTION.format(
                    question=question,
                    knowledge_modules_json=knowledge_json_str,
                    planner_plan_json=plan_json_str,
                    erroneous_code=executable_code, # 上一次失败的代码
                    error_traceback=exec_result['error'] # 上一次的错误信息
                )

            messages = [[{"role": "user", "content": prompt}]]
            code_gen_result_raw = (await self.executor_llm.generate_with_think_and_parse_batch(messages, enable_thinking=False, max_token=8192))[0]['answer']
            
            executable_code = parse_code(code_gen_result_raw)
            if not executable_code:
                logger.error("    - Executor failed to generate any valid code snippet.")
                # 如果连代码都生成不了，直接跳到下一次尝试
                exec_result = {'error': 'Executor returned empty code.'}
                continue

            logger.info("    - Executing generated code...")
            exec_result = execute_code(executable_code)
            
            # 检查执行结果
            if not exec_result.get('error'):
                logger.info("    - Code executed successfully!")
                break # 成功，跳出循环
            else:
                logger.error(f"    - Execution error on attempt {attempt + 1}: {exec_result['error']}")
        # ------------------------------------
        
        if exec_result['error']: 
            logger.error(f"    - Execution error: {exec_result['error']}")
            raise ValueError(f"Execution of generated code failed: {exec_result['error']}")
        
        code_execution_output = exec_result['output']
        full_trace["generated_code"] = executable_code
        full_trace["code_execution_output"] = code_execution_output

        # 4. 合成
        logger.info("  - Stage 4: Synthesizing Final Answer with complete context...")
        
        # --- NEW: 准备知识点摘要 ---
        # 我们只传递被Planner最终选择的知识点
        selected_names = set(plan.get("knowledge_selection", []))
        knowledge_for_synthesis = [
            mod for mod in kn_modules if mod.get("canonical_name") in selected_names
        ]
        
        # 创建一个简洁的摘要字符串
        knowledge_summary_str = ""
        for mod in knowledge_for_synthesis:
            summary = mod.get("concept_definition", {}).get("summary", "N/A")
            knowledge_summary_str += f"- **{mod['canonical_name']}**: {summary}\\n"
        # ---------------------------

        synthesis_prompt = PROMPT_D_FINAL_SYNTHESIS.format(
            original_question=question,
            knowledge_points_summary=knowledge_summary_str, # <-- 新增
            generated_code=executable_code,                 # <-- 新增
            code_execution_output=code_execution_output
        )
        messages = [[{"role": "user", "content": synthesis_prompt}]]
        synthesis_result = (await self.synthesizer_llm.generate_with_think_and_parse_batch(messages, enable_thinking=True))[0]['answer']
        return synthesis_result

    async def _run_zero_knowledge_path(self, question: str, full_trace: dict) -> str:
        """执行零知识直接回答路径，用于基线对比。"""
        logger.info("--- [Executing Zero-Knowledge Direct Answer Path] ---")
        if not self.baseline_llm:
            raise ValueError("Baseline LLM is not configured for 'direct_answer' mode.")
        
        prompt = PROMPT_G_DIRECT_ANSWER_ZERO_KNOWLEDGE.format(question=question)
        messages = [[{"role": "user", "content": prompt}]]
        result = await self.baseline_llm.generate_with_think_and_parse_batch(messages, enable_thinking=False, max_token=4096)
        return result[0]['answer']

    async def run(self, question: str, mode: str, retrieval_mode: str) -> Dict[str, Any]:
        """
        执行总入口，根据模式选择不同的工作流。
        """
        full_trace = {"question": question, "mode": mode, "retrieval_mode": retrieval_mode}
        try:
            if mode == "full":
                question_type = await self._classify_question(question)
                full_trace["question_type"] = question_type
                if question_type == "direct_knowledge":
                    final_answer = await self._run_direct_path(question, full_trace, retrieval_mode)
                else: 
                    final_answer = await self._run_procedural_path(question, full_trace, retrieval_mode)
            
            elif mode == "direct_answer":
                final_answer = await self._run_zero_knowledge_path(question, full_trace)
            
            else:
                raise ValueError(f"Unknown mode: {mode}")
            
            full_trace["final_answer"] = final_answer
            return full_trace

        except Exception as e:
            logger.error(f"Pipeline failed for question '{question[:50]}...': {e}", exc_info=True)
            full_trace["error"] = str(e)
            return full_trace

    async def run(self, question: str, mode: str, retrieval_mode: str) -> Dict[str, Any]:
        """
        执行总入口，根据模式选择不同的工作流。
        """
        full_trace = {"question": question, "mode": mode, "retrieval_mode": retrieval_mode}
        try:
            if mode == "full":
                # 完整流程：分类 -> [直接路径 或 程序化路径]
                question_type = await self._classify_question(question)
                full_trace["question_type"] = question_type
                if question_type == "direct_knowledge":
                    # 注意：直接路径现在也使用新的retriever
                    final_answer = await self._run_direct_path(question, full_trace, retrieval_mode)
                else: # procedural_reasoning or fallback
                    final_answer = await self._run_procedural_path(question, full_trace, retrieval_mode)
            
            elif mode == "direct_answer":
                # 零知识基线流程
                final_answer = await self._run_zero_knowledge_path(question, full_trace)
            
            else:
                raise ValueError(f"Unknown mode: {mode}")
            

            if isinstance(final_answer, str):
                # Replace single backslashes with double backslashes
                # This makes it a valid JSON string literal
                safe_final_answer = final_answer.replace('\\', '\\\\')
            else:
                safe_final_answer = final_answer
            
            full_trace["final_answer"] = safe_final_answer
            return full_trace

        except Exception as e:
            logger.error(f"Pipeline failed for question '{question[:50]}...': {e}", exc_info=True)
            full_trace["error"] = str(e)
            return full_trace

async def main(args: argparse.Namespace):
    """主函数：根据模式初始化组件并批量运行解题流程。"""
    
    questions_data = []
    if args.question:
        questions_data.append({"Question": args.question})
    elif args.input_file:
        questions_data = load_question_data(args.input_file)

    if not questions_data:
        logger.error("No questions to process. Exiting.")
        return
    
    if args.use_specialized_prompt_builder:
        get_question_text = build_prompt_from_jsonl_data
        logger.info("Using specialized prompt builder to format questions.")
    else:
        get_question_text = lambda q_data: q_data.get(args.json_key, "")
        logger.info(f"Using default question key: '{args.json_key}'.")

    # --- 根据模式初始化所需组件 ---
    pipeline = None
    if args.mode == 'full':
        api_url = f"http://{settings.servers.host}:{settings.servers.retrieval_api_port}"
        api_client = RetrievalAPIClient(base_url=api_url)
        
        reranker_llm = get_llm_provider(get_provider_config(args.reranker_model))
        retriever = KnowledgeGraphRetriever(db_dir=args.db_dir, api_client=api_client, reranker_llm=reranker_llm)
        
        classifier_llm = get_llm_provider(get_provider_config(args.classifier_model))
        planner_llm = get_llm_provider(get_provider_config(args.planner_model))
        executor_llm = get_llm_provider(get_provider_config(args.executor_model))
        synthesizer_llm = get_llm_provider(get_provider_config(args.synthesizer_model))
        
        planner = Planner(planner_model_provider=planner_llm)
        pipeline = SolverPipeline(retriever, planner, executor_llm, synthesizer_llm, classifier_llm)
        logger.info("Initialized pipeline in 'full' mode.")

    elif args.mode == 'direct_answer':
        baseline_llm = get_llm_provider(get_provider_config(args.baseline_model))
        pipeline = SolverPipeline(baseline_llm=baseline_llm)
        logger.info(f"Initialized pipeline in 'direct_answer' mode using baseline model '{args.baseline_model}'.")
    
    if not pipeline:
        logger.error(f"Could not initialize pipeline for mode '{args.mode}'.")
        return

    # --- 批量处理循环 ---
    all_results = []
    pbar = tqdm(total=len(questions_data), desc=f"Solving Questions (Mode: {args.mode})") if tqdm else None
    
    for q_data in questions_data:
        # --- 使用 get_question_text 函数 ---
        question_for_pipeline = get_question_text(q_data)
        if not question_for_pipeline:
            logger.warning(f"Skipping item with no question text: {q_data}")
            if pbar: pbar.update(1)
            continue
            
        result_trace = await pipeline.run(
            question_for_pipeline, 
            mode=args.mode, 
            retrieval_mode=args.retrieval_mode
        )
        
        full_result = {**q_data, "solver_trace": result_trace}
        all_results.append(full_result)
        if pbar: pbar.update(1)

    if pbar: pbar.close()

    # --- 保存所有结果 ---
    output_filename = f"batch_solver_results_{args.mode}_{args.retrieval_mode}.jsonl"
    with open(output_filename, 'w', encoding='utf-8') as f:
        for result in all_results:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
    
    logger.info(f"Batch processing complete. All results saved to {output_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full solver pipeline with multiple modes for evaluation.")
    
    parser.add_argument(
        "--mode", 
        type=str, 
        choices=['full', 'direct_answer'], 
        default='full',
        help="Running mode: 'full' for the complete pipeline, 'direct_answer' for the zero-knowledge baseline."
    )
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-q", "--question", type=str, help="A single question to solve.")
    input_group.add_argument("-i", "--input-file", type=str, help="Path to an input .jsonl file with questions.")
    
    parser.add_argument("--json-key", type=str, default="Question", help="The key for the question text in the .jsonl file.")
    
    full_mode_group = parser.add_argument_group('full mode arguments')
    full_mode_group.add_argument("--db-dir", type=str, default="structured_knowledge_base", help="Directory of the structured knowledge base.")
    full_mode_group.add_argument("--reranker-model", type=str, default="qwen3", help="Lightweight model for the Reranker agent.")
    full_mode_group.add_argument("--classifier-model", type=str, default="qwen3", help="Model for the Classifier agent.")
    full_mode_group.add_argument("--planner-model", type=str, default="glm4.5", help="Model for the Planner agent.")
    full_mode_group.add_argument("--executor-model", type=str, default="qwen3", help="Model for the Executor agent.")
    full_mode_group.add_argument("--synthesizer-model", type=str, default="glm4.5", help="Model for the Synthesizer agent.")
    full_mode_group.add_argument(
        "--retrieval-mode", 
        type=str, 
        choices=['full', 'knowledge_only'], 
        default='full',
        help="Retrieval mode for the 'full' pipeline: 'full' uses all recall paths, 'knowledge_only' disables scene/example retrieval."
    )
    full_mode_group.add_argument(
        "--linking-threshold", 
        type=float, 
        default=0.9,
        help="Cosine similarity threshold for linking LLM-identified knowledge to the knowledge base (Path A)."
    )
    parser.add_argument(
        "--use-specialized-prompt-builder",
        action="store_true",
        help="Enable the specialized prompt builder to format questions from the specific JSONL format."
    )
    direct_mode_group = parser.add_argument_group('direct_answer mode arguments')
    direct_mode_group.add_argument("--baseline-model", type=str, default="glm4.5", help="The powerful LLM to use for direct answering.")
    
    args = parser.parse_args()
    asyncio.run(main(args))