# run_kcard_batch.py

import json
import logging
import os
import argparse
from typing import List, Dict

# 导入项目模块
from config import get_provider_config
from llm_providers_new.glm_batch_client import GLMBatchClient
from kcard.prompt import PROMPT_A_KNOWLEDGE_EXTRACTION

# --- 配置日志 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 提示语构建与文件加载函数 (从之前的run_kcard.py迁移并优化) ---

def build_prompt_from_jsonl_data(q_data: Dict) -> str:
    """为特定格式的JSONL数据构建丰富的提示字符串。"""
    question_text = q_data.get("Question", "")
    q_format = q_data.get("Format", "Open-ended")
    q_tag = q_data.get("Tag", "Knowledge")
    
    prompt_parts = [
        f"请为以下【{q_format}】类型的【{q_tag}】问题，提取其核心知识。",
        "---",
        f"问题描述：{question_text}"
    ]

    if q_format == "Multiple-choice":
        options_parts = ["\n选项："]
        options_exist = False
        for key in sorted(q_data.keys()):
            if key in ["A", "B", "C", "D", "E"]:
                options_parts.append(f"- {key}: {q_data[key]}")
                options_exist = True
        if options_exist:
            prompt_parts.extend(options_parts)

    if "Answer" in q_data:
        answer = q_data["Answer"]
        answer_context = ""
        if q_format == "Multiple-choice" and str(answer) in q_data:
            answer_context = f" ({q_data[str(answer)]})"
        prompt_parts.append(f"\n正确答案：{answer}{answer_context}")

    prompt_parts.append("---")
    prompt_parts.append("请基于以上完整信息，分析并提取解决此问题所需的通用知识模块和特定约束。")
    
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

# --- 主执行逻辑 ---

def main(args: argparse.Namespace):
    """主执行函数，使用Batch API提交“元知识”抽取任务。"""
    
    all_question_data = load_question_data(args.input_file)
    if not all_question_data:
        logger.error("No questions to process. Exiting.")
        return

    get_prompt_text = build_prompt_from_jsonl_data if args.use_specialized_prompt_builder else lambda q_data: q_data.get(args.json_key, "")

    # --- 断点续传逻辑 ---
    existing_results = {}
    if os.path.exists(args.output_file):
        try:
            with open(args.output_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if content: existing_results = json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"Output file {args.output_file} is corrupted. It will be overwritten.")
    
    # --- 准备Batch API的请求列表 ---
    batch_requests = []
    custom_id_to_prompt = {}

    for i, q_data in enumerate(all_question_data):
        prompt_text = get_prompt_text(q_data)
        if prompt_text and prompt_text not in existing_results:
            custom_id = f"kcard-meta-gen-{i+1}-{hash(prompt_text)}"
            # --- 使用最终版的Prompt ---
            request_content = PROMPT_A_KNOWLEDGE_EXTRACTION.format(question=prompt_text)
            
            request_body = {
                "model": args.model,
                "messages": [{"role": "user", "content": request_content}],
                "response_format": {"type": "json_object"}
            }
            batch_requests.append({
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v4/chat/completions",
                "body": request_body
            })
            # 我们现在使用原始问题作为key，而不是整个prompt
            custom_id_to_prompt[custom_id] = prompt_text

    if not batch_requests:
        logger.info("All questions have already been processed. Nothing to do.")
        return

    logger.info(f"Preparing a batch job for {len(batch_requests)} new questions.")

    # --- 执行批处理流程 ---
    provider_config = get_provider_config(args.model)
    api_key = provider_config.get("api_key")
    if not api_key: raise ValueError(f"API key not found in config for model '{args.model}'")

    batch_client = GLMBatchClient(api_key=api_key)
    batch_results = batch_client.run_full_batch_process(
        requests=batch_requests,
        job_description="Meta-Knowledge Card Generation"
    )

    # --- 处理并合并结果 ---
    if not batch_results:
        logger.error("Batch processing failed or returned no results.")
        return

    newly_generated_kbs = {}
    for result in batch_results:
        custom_id = result.get("custom_id")
        original_prompt = custom_id_to_prompt.get(custom_id)
        if not original_prompt: continue

        if result.get("response", {}).get("status_code") == 200:
            try:
                content_str = result["response"]["body"]["choices"][0]["message"]["content"]
                kb_json = json.loads(content_str)
                newly_generated_kbs[original_prompt] = kb_json
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                logger.error(f"Failed to parse result for custom_id {custom_id}: {e}")
        else:
            logger.error(f"Request failed for custom_id {custom_id}: {result.get('response')}")

    final_knowledge_base = {**existing_results, **newly_generated_kbs}
    with open(args.output_file, 'w', encoding='utf-8') as f:
        json.dump(final_knowledge_base, f, ensure_ascii=False, indent=4)
    
    logger.info("--- Batch Processing Complete ---")
    logger.info(f"Total knowledge bases in output file: {len(final_knowledge_base)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate Meta-Knowledge Cards using the GLM Batch API.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    # --- 简化并明确参数 ---
    parser.add_argument("--input-file", type=str, required=True, help="Path to input .jsonl file with questions.")
    parser.add_argument("--output-file", type=str, default="meta_knowledge_base.json", help="Path for the output JSON file.")
    # 明确指出这个脚本需要强大的模型
    parser.add_argument("--model", type=str, default="glm-4.5", help="The powerful model for meta-knowledge extraction (e.g., 'glm-4.5').")
    
    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--use-specialized-prompt-builder", action="store_true", help="Enable the specialized prompt builder for the specific JSONL format.")
    prompt_group.add_argument("--json-key", type=str, help="The key for the main question text in a generic .jsonl file.")
    
    args = parser.parse_args()
    
    if not args.use_specialized_prompt_builder and not args.json_key:
        parser.error("You must specify either --use-specialized-prompt-builder or --json-key.")

    main(args)