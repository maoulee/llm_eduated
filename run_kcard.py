# run_kcard.py (Final "Meta-Knowledge" Version)

import asyncio
import json
import logging
import os
import argparse
from typing import List, Dict, Any

try:
    from tqdm.asyncio import tqdm
except ImportError:
    tqdm = None
    print("Warning: tqdm is not installed. Progress bar will not be shown. Run 'pip install tqdm'.")

# 导入项目模块
from config import get_provider_config
from llm_providers_new import get_llm_provider
from kcard.generator import KnowledgeEngineer
# --- CHANGE: Import the final, powerful meta-extraction prompt ---
from kcard.prompt import PROMPT_A_KNOWLEDGE_EXTRACTION

# --- 配置日志 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 文件I/O与断点续传函数 (保持健壮) ---
file_lock = asyncio.Lock()

async def load_existing_results(filename: str) -> Dict[str, Any]:
    """Safely load existing results from the output file."""
    async with file_lock:
        if not os.path.exists(filename):
            return {}
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content: return {}
                return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

async def append_result_to_file(filename: str, question_key: str, result_kb: Dict[str, Any]):
    """Safely append a new result to the JSON file."""
    async with file_lock:
        existing_data = {}
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content: existing_data = json.loads(content)
            except json.JSONDecodeError:
                logger.error(f"Output file {filename} is corrupted. Cannot append.")
                return
        
        existing_data[question_key] = result_kb
        try:
            # Ensure the directory exists
            output_dir = os.path.dirname(filename)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Failed to write updated results to {filename}: {e}")

# --- 提示语构建与文件加载函数 (最终版) ---
def build_prompt_from_jsonl_data(q_data: Dict) -> str:
    """为特定格式的JSONL数据构建丰富的提示字符串。"""
    question_text = q_data.get("Question", "")
    q_format = q_data.get("Format", "Open-ended")
    q_tag = q_data.get("Tag", "Knowledge")
    
    prompt_parts = [f"请为以下【{q_format}】类型的【{q_tag}】问题，提取其核心知识。"]
    prompt_parts.append("---")
    prompt_parts.append(f"问题描述：{question_text}")

    if q_format == "Multiple-choice":
        options_parts = ["\n选项："]
        options_exist = False
        for key in sorted(q_data.keys()):
            if key in ["A", "B", "C", "D", "E"]:
                options_parts.append(f"- {key}: {q_data[key]}")
                options_exist = True
        if options_exist: prompt_parts.extend(options_parts)

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
                    if line.strip(): question_data_list.append(json.loads(line))
        else:
            logger.error(f"Unsupported file type: {ext}. Please use .jsonl.")
            return []
    except Exception as e:
        logger.error(f"Failed to load file {filepath}: {e}", exc_info=True)
    logger.info(f"Loaded {len(question_data_list)} question data objects from {filepath}")
    return question_data_list

# --- 核心处理逻辑 ---
async def process_and_save_question(
    question_key: str, 
    llm_input_prompt: str,
    engineer: KnowledgeEngineer, 
    output_file: str,
    pbar: Any
):
    """处理单个问题并保存结果。"""
    logger.info(f"Processing question: '{question_key[:70]}...'")
    try:
        # --- CHANGE: Use the correct meta-extraction prompt ---
        request_content = PROMPT_A_KNOWLEDGE_EXTRACTION.format(question=llm_input_prompt)
        # ----------------------------------------------------
        
        # The KnowledgeEngineer now receives the fully formatted request content
        knowledge_base = await engineer.generate_knowledge_base(request_content)
        
        if knowledge_base:
            await append_result_to_file(output_file, question_key, knowledge_base)
            logger.info(f"Successfully processed and saved result for: '{question_key[:70]}...'")
        else:
            logger.warning(f"Failed to generate knowledge base for: '{question_key[:70]}...'. Skipping.")
    except Exception as e:
        logger.error(f"An unexpected error occurred for question '{question_key[:70]}...': {e}", exc_info=True)
    finally:
        if pbar: pbar.update(1)

async def main(args: argparse.Namespace):
    """主执行函数，支持断点续传和并发控制。"""
    all_question_data = load_question_data(args.input_file)
    if not all_question_data:
        logger.error("No questions to process. Exiting.")
        return

    get_prompt_text_for_llm = build_prompt_from_jsonl_data if args.use_specialized_prompt_builder else lambda q_data: q_data.get(args.json_key, "")

    existing_results = await load_existing_results(args.output_file)
    
    # Use the original, unprocessed question text as the unique key for results
    questions_to_process_data = [
        q_data for q_data in all_question_data 
        if q_data.get("Question") and q_data["Question"] not in existing_results
    ]
    
    if not questions_to_process_data:
        logger.info("All questions have already been processed. Nothing to do. Exiting.")
        return
    
    logger.info(f"Found {len(existing_results)} already processed questions.")
    logger.info(f"Starting to process {len(questions_to_process_data)} remaining questions.")

    provider_config = get_provider_config(args.model)
    engineer_llm_provider = get_llm_provider(provider_config)
    knowledge_engineer = KnowledgeEngineer(engineer_model_provider=engineer_llm_provider)
    
    semaphore = asyncio.Semaphore(args.concurrency)
    pbar = tqdm(total=len(questions_to_process_data), desc="Generating Meta-Knowledge Cards") if tqdm else None
    
    async def limited_task(q_data):
        question_key = q_data["Question"]
        llm_input_prompt = get_prompt_text_for_llm(q_data)
        async with semaphore:
            await process_and_save_question(question_key, llm_input_prompt, knowledge_engineer, args.output_file, pbar)

    tasks = [limited_task(q_data) for q_data in questions_to_process_data]
    await asyncio.gather(*tasks)

    if pbar: pbar.close()
    
    logger.info("--- Processing Complete ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate Meta-Knowledge Cards from authoritative questions using high-concurrency real-time API.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--input-file", type=str, required=True, help="Path to input .jsonl file with questions.")
    # --- CHANGE: Updated default output filename ---
    parser.add_argument("--output-file", type=str, default="./kcard_data/meta_knowledge_base.json", help="Path for the output JSON file.")
    # --- CHANGE: Updated help text for model ---
    parser.add_argument("--model", type=str, default="glm4.5", help="The powerful model for meta-knowledge extraction (e.g., 'glm4.5').")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent requests to the LLM API.")
    
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--use-specialized-prompt-builder", action="store_true", help="Enable the specialized prompt builder for the specific JSONL format.")
    prompt_group.add_argument("--json-key", type=str, help="The key for the main question text in a generic .jsonl file.")
    
    args = parser.parse_args()
    
    asyncio.run(main(args))