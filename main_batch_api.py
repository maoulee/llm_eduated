# main_api.py

import argparse, json, os, re, subprocess, time, uuid, asyncio
from typing import Dict, List
from rich.console import Console
from rich.progress import Progress

from core.prompts import *
from core.retrieval_api_client import RetrievalAPIClient
from core.solver import Solver
from llm_providers.remote_api import VLLMAPIClient # 直接导入异步客户端

# --- 配置 (只关心 api) ---
CONFIG = {
    "base": {
        "test_questions_file": "/zhaoshu/mcts_reason/data/evaluation_questions.json",
        "batch_results_file": "/zhaoshu/mcts_reason/data/batch_results_{mode}_api.json",
        "retrieval_api_url": "http://localhost:8001"
    },
    "api": {
        "model_path": "/zhaoshu/llm/qwen3-32b/",
        "api_url": "http://localhost:8000/v1"
    }
}

# ============================= 流水线阶段函数 (异步版本) =============================
def stage_1_batch_retrieval(prompts: List[str], retriever: RetrievalAPIClient) -> List[Dict]:
    """第一阶段：通过API批量检索和知识聚合。"""
    console = Console()
    console.print("  - Performing batch retrieval for all prompts via API...")
    batch_retrieved_results = retriever.search(prompts, k=3)
    final_aggregated_info = []
    for retrieved_results in batch_retrieved_results:
        aggregated_knowledge = {'knowledge_points': [], 'common_pitfalls': []}
        if retrieved_results:
            for res in retrieved_results:
                aggregated_knowledge['knowledge_points'].extend(res.get('knowledge_points', []))
                aggregated_knowledge['common_pitfalls'].extend(res.get('common_pitfalls', []))
            aggregated_knowledge['knowledge_points'] = [dict(t) for t in {tuple(d.items()) for d in aggregated_knowledge['knowledge_points']}]
            aggregated_knowledge['common_pitfalls'] = list(set(aggregated_knowledge['common_pitfalls']))
        final_aggregated_info.append(aggregated_knowledge)
    return final_aggregated_info

async def stage_1_5_classify_questions_batch(prompts: List[str], llm_service: VLLMAPIClient) -> List[str]:
    """1.5阶段: 批量分类问题类型"""
    messages_batch = [[{"role": "user", "content": QUESTION_CLASSIFICATION_PROMPT.format(question_prompt=prompt)}] for prompt in prompts]
    json_outputs = await llm_service.generate_json_batch(messages_batch)
    return [output.get("question_type", "procedural") if isinstance(output, dict) else "procedural" for output in json_outputs]

async def stage_2_batch_pseudocode_generation(prompts: List[str], retrieved_info_batch: List[Dict], llm_service: VLLMAPIClient) -> List[str]:
    """第二阶段：批量生成伪代码"""
    messages_batch = []
    for i in range(len(prompts)):
        knowledge_points_str = "\n".join([f"- {p['point']}: {p['description']}" for p in retrieved_info_batch[i].get('knowledge_points', [])]) or "无"
        pitfalls_str = "\n".join([f"- {p}" for p in retrieved_info_batch[i].get('common_pitfalls', [])]) or "无"
        content = PSEUDOCODE_GENERATION_PROMPT_V2.format(new_question_prompt=prompts[i], knowledge_points=knowledge_points_str, common_pitfalls=pitfalls_str)
        messages_batch.append([{"role": "user", "content": content}])
    llm_outputs = await llm_service.generate_with_think_and_parse_batch(messages_batch, enable_thinking=True)
    def _extract_procedure(text: str) -> str:
        try: return re.search(r'<PROCEDURE>(.*?)</PROCEDURE>', text, re.DOTALL).group(1).strip()
        except Exception: return text.strip()
    return [_extract_procedure(output['answer']) for output in llm_outputs]

async def stage_3_batch_solving(prompts: List[str], final_pseudocodes: List[str], solver: Solver, num_solutions: int = 3, enable_thinking: bool = True) -> List[List[List[str]]]:
    """第三阶段：批量生成多种解法，支持关闭思考模式"""
    messages_batch = []
    for i in range(len(prompts)):
        content = SUBQUESTION_SOLVER_PROMPT.format(final_pseudocode=final_pseudocodes[i], new_question_prompt=prompts[i])
        for _ in range(num_solutions):
            messages_batch.append([{"role": "user", "content": content}])
    llm_outputs = await solver.llm.generate_with_think_and_parse_batch(messages_batch, enable_thinking=enable_thinking)
    all_solutions_flat = [solver._parse_subquestions(output['answer']) for output in llm_outputs]
    return [all_solutions_flat[i:i + num_solutions] for i in range(0, len(all_solutions_flat), num_solutions)]

async def stage_4_batch_reconstruction(prompts: List[str], final_pseudocodes: List[str], all_solutions_lists: List[List[List[str]]], solver: Solver, llm_service: VLLMAPIClient):
    """第四阶段：批量检查、验证与重构 (异步版)"""
    final_solutions = [sol[0] if sol else [] for sol in all_solutions_lists]
    was_reconstructed_flags = [False] * len(prompts)
    consistency_check_messages_batch, task_map_for_llm_check = [], {}
    for i, solutions_sq_list in enumerate(all_solutions_lists):
        if solutions_sq_list and len(solutions_sq_list) >= 2:
            formatted_sols = "".join([f"[版本 {j+1}]\n" + "\n[end_of_subquestion]\n".join(sol) + "\n---\n" for j, sol in enumerate(solutions_sq_list)])
            content = SOLUTION_CONSISTENCY_CHECK_PROMPT_V2.format(question=prompts[i], pseudocode=final_pseudocodes[i], formatted_solutions=formatted_sols)
            consistency_check_messages_batch.append([{"role": "user", "content": content}])
            task_map_for_llm_check[len(consistency_check_messages_batch) - 1] = i
    if not consistency_check_messages_batch: return final_solutions, was_reconstructed_flags
    check_results_json = await llm_service.generate_json_batch(consistency_check_messages_batch)
    reconstruction_tasks = []
    for batch_idx, res in enumerate(check_results_json):
        if res and not res.get("is_consistent", True):
            original_idx = task_map_for_llm_check[batch_idx]
            reconstruction_tasks.append({'index': original_idx, 'inconsistency_report': json.dumps(res, indent=2, ensure_ascii=False)})
            was_reconstructed_flags[original_idx] = True
    if not reconstruction_tasks: return final_solutions, was_reconstructed_flags
    code_gen_messages_batch, code_gen_task_map = [], {}
    for task in reconstruction_tasks:
        i = task['index']
        key_values = " ".join(re.findall(r'[-+]?\d*\.\d+|\d+', prompts[i])) or "无"
        content = CODE_GENERATION_FROM_PSEUDOCODE_PROMPT.format(final_pseudocode=final_pseudocodes[i] or "无", key_values=key_values)
        code_gen_messages_batch.append([{"role": "user", "content": content}])
        code_gen_task_map[len(code_gen_messages_batch) - 1] = i
    if not code_gen_messages_batch: return final_solutions, was_reconstructed_flags
    code_gen_outputs = await llm_service.generate_with_think_and_parse_batch(code_gen_messages_batch, enable_thinking=True)
    def _parse_executable_code(llm_answer: str) -> str:
        try:
            if "<execute_code>" in llm_answer: return llm_answer.split("<execute_code>")[1].split("</execute_code>")[0].strip()
            if "```python" in llm_answer: return llm_answer.split("```python\n")[1].split("```")[0].strip()
            return llm_answer.strip()
        except (IndexError, AttributeError): return llm_answer.strip()
    executable_codes = {code_gen_task_map[batch_idx]: _parse_executable_code(output['answer']) for batch_idx, output in enumerate(code_gen_outputs)}
    code_run_results = {}
    for original_idx, code in executable_codes.items():
        try:
            process = subprocess.run(['python', '-c', code], capture_output=True, text=True, timeout=15, check=False)
            output, error = process.stdout, process.stderr if process.returncode != 0 else None
            code_run_results[original_idx] = {'output': output, 'error': error}
        except Exception as e:
            code_run_results[original_idx] = {'output': None, 'error': str(e)}
    reconstruction_messages_batch, reconstruction_task_map = [], {}
    for task in reconstruction_tasks:
        original_idx = task['index']
        if original_idx in code_run_results and code_run_results[original_idx]['error'] is None:
            content = GLOBAL_RECONSTRUCTION_PROMPT.format(original_question=prompts[original_idx], initial_solution_draft="\n[end_of_subquestion]\n".join(all_solutions_lists[original_idx][0]), inconsistency_report=task['inconsistency_report'], executable_code=executable_codes.get(original_idx, "N/A"), code_output=code_run_results[original_idx].get('output', "N/A"))
            reconstruction_messages_batch.append([{"role": "user", "content": content}])
            reconstruction_task_map[len(reconstruction_messages_batch) - 1] = original_idx
    if reconstruction_messages_batch:
        reconstructed_outputs = await llm_service.generate_with_think_and_parse_batch(reconstruction_messages_batch, enable_thinking=True)
        for batch_idx, output in enumerate(reconstructed_outputs):
            original_idx = reconstruction_task_map[batch_idx]
            final_solutions[original_idx] = solver._parse_subquestions(output['answer'])
    return final_solutions, was_reconstructed_flags

async def stage_direct_answer_batch(direct_tasks: List[Dict], llm_service: VLLMAPIClient):
    """直接回答路径: 批量为'direct'类型问题生成答案"""
    if not direct_tasks: return {}
    messages_batch = []
    for task in direct_tasks:
        knowledge_points_str = "\n".join([f"- {p['point']}: {p['description']}" for p in task['retrieved_info'].get('knowledge_points', [])]) or "无"
        content = DIRECT_ANSWER_PROMPT.format(new_question_prompt=task['prompt'])
        messages_batch.append([{"role": "user", "content": content}])
    outputs = await llm_service.generate_with_think_and_parse_batch(messages_batch, enable_thinking=False)
    direct_results = {}
    for i, task in enumerate(direct_tasks):
        direct_results[task['original_index']] = {"response": outputs[i]['answer'], "metadata": {"retrieved_knowledge": task['retrieved_info'], "was_reconstructed": False, "question_type": "direct"}}
    return direct_results

# ============================= 主函数 (异步版) =============================
async def main(mode: str):
    console = Console()
    
    config = {**CONFIG['base'], **CONFIG['api']}
    config['batch_results_file'] = config['batch_results_file'].format(mode=mode)
    
    console.print(f"[bold magenta]Running ASYNC mode: '{mode}'[/bold magenta]")
    os.makedirs(os.path.dirname(config['batch_results_file']), exist_ok=True)

    console.print("[bold cyan]Initializing API clients...[/bold cyan]")
    retriever = RetrievalAPIClient(base_url=config["retrieval_api_url"])
    llm_service = VLLMAPIClient(model_name=config["model_path"], api_base_url=config["api_url"])
    solver = Solver(llm_service)
    console.print("[bold green]API clients initialized.[/bold green]")

    with open(config['test_questions_file'], 'r', encoding='utf-8') as f:
        test_questions = json.load(f)
    all_prompts = [q['prompt'] for q in test_questions]
    
    all_results = []
    if mode == 'direct':
        console.print("[bold yellow]Executing 'direct' baseline workflow via API...[/bold yellow]")
        retrieved_info_batch = stage_1_batch_retrieval(all_prompts, retriever)
        direct_tasks = [{"original_index": i, "prompt": prompt, "retrieved_info": retrieved_info_batch[i]} for i, prompt in enumerate(all_prompts)]
        direct_results_map = await stage_direct_answer_batch(direct_tasks, llm_service)
        for i, q in enumerate(test_questions):
            res_data = direct_results_map.get(i, {"response": "ERROR", "metadata": {}})
            res_data['metadata']['question_type'] = "direct_api_baseline"
            all_results.append({"id": q.get('id', uuid.uuid4()), "prompt": q['prompt'], "ground_truth_answer": q.get('answer', 'N/A'), **res_data})
            
    elif mode == 'api':
        final_results_map = {}
        with Progress(console=console) as progress:
            p1 = progress.add_task("[cyan]1. Retrieving & Classifying...", total=len(all_prompts))
            retrieved_info_batch = stage_1_batch_retrieval(all_prompts, retriever)
            question_types = await stage_1_5_classify_questions_batch(all_prompts, llm_service)
            progress.update(p1, completed=len(all_prompts))
            
            procedural_tasks = [{"original_index": i, "prompt": all_prompts[i], "retrieved_info": retrieved_info_batch[i]} for i, q_type in enumerate(question_types) if q_type == "procedural"]
            direct_tasks = [{"original_index": i, "prompt": all_prompts[i], "retrieved_info": retrieved_info_batch[i]} for i, q_type in enumerate(question_types) if q_type != "procedural"]
            console.print(f"[bold]Routing:[/bold] [blue]{len(procedural_tasks)} procedural[/blue], [green]{len(direct_tasks)} direct[/green].")

            if procedural_tasks:
                proc_prompts, proc_retrieved = [t['prompt'] for t in procedural_tasks], [t['retrieved_info'] for t in procedural_tasks]
                p2 = progress.add_task("[blue]  - 2. Generating pseudocodes...", total=1)
                final_pseudocodes = await stage_2_batch_pseudocode_generation(proc_prompts, proc_retrieved, llm_service)
                progress.update(p2, completed=1)
                p3 = progress.add_task("[blue]  - 3. Solving (thinking disabled)...", total=1)
                all_solutions_lists = await stage_3_batch_solving(proc_prompts, final_pseudocodes, solver, enable_thinking=False)
                progress.update(p3, completed=1)
                p4 = progress.add_task("[blue]  - 4. Reconstructing...", total=1)
                final_solutions, was_reconstructed = await stage_4_batch_reconstruction(proc_prompts, final_pseudocodes, all_solutions_lists, solver, llm_service)
                progress.update(p4, completed=1)
                for i, task in enumerate(procedural_tasks):
                    final_results_map[task['original_index']] = {"response": "\n[end_of_subquestion]\n".join(final_solutions[i]), "metadata": {"retrieved_knowledge": proc_retrieved[i], "consensus_pseudocode": final_pseudocodes[i], "was_reconstructed": was_reconstructed[i], "question_type": "procedural"}}
            if direct_tasks:
                p_dir = progress.add_task("[green]Direct Path...", total=1)
                direct_results = await stage_direct_answer_batch(direct_tasks, llm_service)
                final_results_map.update(direct_results)
                progress.update(p_dir, completed=1)
            
            p_agg = progress.add_task("[yellow]5. Aggregating results...", total=len(test_questions))
            for i, q in enumerate(test_questions):
                res_data = final_results_map.get(i, {"response": "ERROR", "metadata": {}})
                all_results.append({"id": q.get('id', uuid.uuid4()), "prompt": q['prompt'], "ground_truth_answer": q.get('answer', 'N/A'), **res_data})
                progress.update(p_agg, advance=1)

    with open(config['batch_results_file'], 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    console.print(f"\n[bold bright_green]'{mode}' mode processing complete! Results saved to {config['batch_results_file']}.[/bold bright_green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the 408 Solver using API-based LLM inference.")
    parser.add_argument("--mode", type=str, choices=["api", "direct"], default="api", help="Workflow mode: 'api' for full workflow, 'direct' for baseline test.")
    args = parser.parse_args()
    asyncio.run(main(args.mode))