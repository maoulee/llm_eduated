# evaluator.py

import json
import logging
import argparse
import re
import asyncio
from typing import Dict, Any,List
from collections import defaultdict

# 导入我们项目的LLM Provider
from config import get_provider_config
from llm_providers_new import get_llm_provider

# --- 配置日志 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 从 csbench 借鉴并适配的Prompt ---

def create_open_ended_prompt(question: str, correct_answer: str, student_output: str, language: str) -> str:
    """为开放题创建评估Prompt。"""
    if language == "Chinese":
        return (f"你现在是一名严格、公正的计算机科学考试阅卷人。你的任务是批改一份主观题的答案。"
                f"你将会看到[标准答案]（经过验证完全正确）和[待评估的答案]。"
                f"请严格按照以下[评分标准]，在1到10分之间给出一个整数分数。"
                f"你的输出必须严格遵循指定的JSON格式。不要添加任何额外的解释。\n\n"
                f"[评分标准]:\n"
                f"- **第四档 (0l9-1.0分)**: 答案完全正确，逻辑严谨，覆盖了所有关键点，与标准答案的核心思想完全一致。\n"
                f"- **第三档 (0.7-0.8分)**: 答案基本正确，只有极少数小错误或遗漏，核心逻辑正确。\n"
                f"- **第二档 (0.4-0.6分)**: 答案部分正确，理解了问题的部分核心概念，但存在明显的逻辑错误或关键信息遗漏。\n"
                f"- **第一档 (0.1-0.3分)**: 答案包含多个基本概念错误，或与问题相关性很低。\n\n"
                f"[原始问题]: {question}\n"
                f"[标准答案]: {correct_answer}\n"
                f"[待评估的答案]: {student_output}\n\n"
                f"[输出格式]:\n"
                f"```json\n"
                f'{{"score": <你的0-1分评分>, "reasoning": "<你给出该评分的简要理由>"}}\n'
                f"```")
    # 可以按需添加英文版本
    return ""

# --- 核心评分逻辑 ---

async def score_single_item(json_obj: Dict, evaluator_llm) -> Dict:
    """对单个JSON对象进行评分。"""
    
    # 从我们的solver_trace中提取模型生成的答案
    student_output = json_obj.get("solver_trace", {}).get("final_answer", "")
    if not student_output:
        json_obj["evaluation"] = {"score": 0.0, "reasoning": "No final_answer found in solver_trace."}
        return json_obj

    # 提取标准答案和问题
    standard_answer = str(json_obj.get("Answer", "")).strip()
    question = json_obj.get("Question", "")
    q_format = json_obj.get("Format", "Open-ended")
    language = json_obj.get("Language", "Chinese")
    
    evaluation_result = {}

    try:
        if q_format == "Multiple-choice":
            # 使用正则表达式进行精确匹配
            # 寻找 \boxed{A} 或 A. 或 (A) 等格式
            matches = re.findall(r'(?:\\boxed\{|[(（\s])([A-D])(?:[.)）\s]|\})', student_output, re.IGNORECASE)
            if not matches: # 如果找不到，尝试直接匹配单个字母
                matches = re.findall(r'\b([A-D])\b', student_output, re.IGNORECASE)
            
            if matches:
                final_choice = matches[-1].upper() # 取最后一个匹配项，防止思考过程中出现其他字母
                evaluation_result["score"] = 1.0 if final_choice == standard_answer.upper() else 0.0
                evaluation_result["reasoning"] = f"Regex matched choice: {final_choice}. Standard answer: {standard_answer}."
            else:
                evaluation_result["score"] = 0.0
                evaluation_result["reasoning"] = "Regex could not find a valid choice (A, B, C, or D)."

        elif q_format == "Assertion":
            # 同样使用正则
            if re.search(r'正确|true', student_output, re.IGNORECASE):
                final_choice = 'true'
            elif re.search(r'错误|false', student_output, re.IGNORECASE):
                final_choice = 'false'
            else:
                final_choice = None
            
            if final_choice:
                evaluation_result["score"] = 1.0 if final_choice == standard_answer.lower() else 0.0
                evaluation_result["reasoning"] = f"Regex matched assertion: {final_choice}. Standard answer: {standard_answer}."
            else:
                evaluation_result["score"] = 0.0
                evaluation_result["reasoning"] = "Regex could not find a valid assertion (true/false)."
        
        else: # Fill-in-the-blank 和 Open-ended
            if not evaluator_llm:
                evaluation_result["score"] = -1.0 # 标记为未评估
                evaluation_result["reasoning"] = "Evaluator LLM not provided for this format."
            else:
                # 统一使用强大的开放题评估Prompt
                prompt = create_open_ended_prompt(question, standard_answer, student_output, language)
                messages = [[{"role": "user", "content": prompt}]]
                
                # 调用LLM进行评估
                gpt_response_list = await evaluator_llm.generate_json_batch(messages,max_tokens=4096,enable_thinking=True)
                
                if gpt_response_list and isinstance(gpt_response_list[0], dict):
                    gpt_response = gpt_response_list[0]
                    score = gpt_response.get("score", 0)
                    # 将1-10分制转换为0.1-1.0分制
                    evaluation_result["score"] = float(score) / 10.0
                    evaluation_result["reasoning"] = gpt_response.get("reasoning", "")
                    evaluation_result["evaluator_output"] = gpt_response
                else:
                    evaluation_result["score"] = -1.0
                    evaluation_result["reasoning"] = "Failed to get valid JSON from evaluator LLM."

    except Exception as e:
        logger.error(f"Error scoring item ID {json_obj.get('ID')}: {e}", exc_info=True)
        evaluation_result["score"] = -1.0
        evaluation_result["reasoning"] = f"An unexpected error occurred: {e}"

    json_obj["evaluation"] = evaluation_result
    return json_obj


def analyze_and_print_results(processed_results: List[Dict]):
    """
    对评分后的结果进行多维度统计分析并打印报告。
    """
    if not processed_results:
        logger.warning("No results to analyze.")
        return

    # --- 数据结构初始化 ---
    # 用于存储每个Domain的分数列表
    domain_scores = defaultdict(list)
    # 用于存储总分
    total_scores = []
    
    # --- 数据收集 ---
    for result in processed_results:
        score = result.get("evaluation", {}).get("score", -1.0)
        domain = result.get("Domain", "Unknown Domain")

        # 只统计有效评分 (>= 0)
        if score >= 0:
            total_scores.append(score)
            domain_scores[domain].append(score)

    # --- 统计计算与报告打印 ---
    print("\n" + "="*50)
    print("           EVALUATION RESULTS SUMMARY")
    print("="*50)

    # 1. 总体平均分
    if total_scores:
        overall_avg = (sum(total_scores) / len(total_scores)) * 100
        print(f"\n[ Overall Performance ]")
        print(f"  - Total Scored Items: {len(total_scores)}")
        print(f"  - Average Score: {overall_avg:.2f}%")
    else:
        print("\n[ Overall Performance ]")
        print("  - No valid scores found to calculate an average.")

    # 2. 按科目 (Domain) 分组统计
    if domain_scores:
        print("\n[ Performance by Domain ]")
        # 按Domain名称排序，保证报告顺序一致
        for domain, scores in sorted(domain_scores.items()):
            domain_avg = (sum(scores) / len(scores)) * 100
            print(f"  - Domain: {domain}")
            print(f"    - Scored Items: {len(scores)}")
            print(f"    - Average Score: {domain_avg:.2f}%")
    
    print("\n" + "="*50)

async def main(args: argparse.Namespace):
    """主执行函数。"""
    
    # --- NEW: Analyze-Only Mode Logic ---
    if args.analyze_only:
        logger.info(f"--- Running in Analyze-Only Mode ---")
        processed_results = []
        try:
            with open(args.input_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        processed_results.append(json.loads(line.strip()))
            analyze_and_print_results(processed_results)
        except FileNotFoundError:
            logger.error(f"Input file not found: {args.input_file}")
        except Exception as e:
            logger.error(f"Failed to load or analyze the file: {e}", exc_info=True)
        return # 任务完成，直接退出
    # ------------------------------------

    # --- 原始的评分流程 (当不使用 --analyze-only 时执行) ---
    logger.info(f"--- Running in Scoring Mode ---")
    evaluator_llm = None
    if args.use_llm_evaluator:
        try:
            eval_config = get_provider_config(args.evaluator_model)
            evaluator_llm = get_llm_provider(eval_config)
            logger.info(f"Initialized LLM evaluator with model: {args.evaluator_model}")
        except Exception as e:
            logger.error(f"Could not initialize evaluator LLM. Error: {e}")

    lines = []
    try:
        with open(args.input_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        logger.error(f"Input file not found: {args.input_file}")
        return

    tasks = [score_single_item(json.loads(line.strip()), evaluator_llm) for line in lines if line.strip()]
    processed_results = await asyncio.gather(*tasks)

    analyze_and_print_results(processed_results)

    output_filename = args.input_file.replace(".jsonl", "_evaluated.jsonl")
    with open(output_filename, "w", encoding="utf-8") as f:
        for result in processed_results:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
    logger.info(f"Full evaluation results saved to: {output_filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate solver pipeline results and generate a performance report.")
    parser.add_argument(
        "input_file", 
        type=str, 
        help="Path to the batch_solver_results_*.jsonl file to be evaluated OR an already *_evaluated.jsonl file for analysis."
    )
    # --- NEW: Analyze-Only Switch ---
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Skip the scoring process and directly generate a statistical report from an already evaluated file."
    )
    # --------------------------------
    
    scoring_group = parser.add_argument_group('scoring mode arguments')
    scoring_group.add_argument(
        "--use-llm-evaluator",
        action="store_true",
        help="Enable scoring for Open-ended/Fill-in-the-blank questions using an LLM."
    )
    scoring_group.add_argument(
        "--evaluator-model",
        type=str,
        default="glm4.5_remote",
        help="The powerful LLM provider name to use as the evaluator."
    )
    args = parser.parse_args()
    asyncio.run(main(args))