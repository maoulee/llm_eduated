# main_self_consistent.py

import argparse, json, os, re, subprocess, time, uuid, asyncio
from typing import Dict, List
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from core.prompts import (
    FRAMEWORK_GENERATION_PROMPT,
    DIVERSE_CODE_GENERATION_PROMPT,
    CODE_SELF_REFLECTION_PROMPT,
    FALLBACK_DECISION_PROMPT,
    FINAL_SYNTHESIS_PROMPT,
    DIRECT_ANSWER_PROMPT,
    QUESTION_CLASSIFICATION_PROMPT
)
from core.retrieval_api_client import RetrievalAPIClient
from llm_providers import get_llm_provider
from core.workflow_components import (find_majority_result, 
                                      format_divergent_codes_for_reflection)

# --- 配置 ---
CONFIG = {
    "base": {
        "test_questions_file": "/data2/home/E22101006/mcts_reason/data/evaluation_questions.json",
        "batch_results_file": "/data2/home/E22101006/mcts_reason/data/batch_results_iterative_{workflow}_{provider}.json",
        "retrieval_api_url": "http://localhost:8001"
    },
    "providers": {
        "local": {"provider_type": "local", "model_path": "/zhaoshu/llm/qwen3-32b/"},
        "api": {"provider_type": "api", "model_path": "/zhaoshu/llm/qwen3-32b/", "api_url": "http://localhost:8000/v1"},
        "glm4.5": {"provider_type": "api", "model_path": "glm-4.5", "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",'api_key':'aa6c598ff745960ef447bf4f55ad1f2a.ZYtqw25sXCBOkw5h'},
    }
}

# ============================= 辅助函数 =============================
def _parse_code(text: str) -> str:
    if not isinstance(text, str): return ""
    try:
        outer_match = re.search(r'<execute_code>(.*?)</execute_code>', text, re.DOTALL)
        content_to_search = outer_match.group(1) if outer_match else text
        inner_match = re.search(r'```python\n(.*?)\n```', content_to_search, re.DOTALL)
        if inner_match: return inner_match.group(1).strip()
        if outer_match: return content_to_search.strip()
        fallback_match = re.search(r'```(.*?)```', text, re.DOTALL)
        if fallback_match:
            code = fallback_match.group(1).strip()
            if code.lower().startswith('python'):
                code = re.sub(r'^[pP][yY][tT][hH][oO][nN]\s*', '', code, count=1)
            return code
        return text.strip()
    except Exception: return ""

def _execute_code(code: str, context: str = "") -> Dict:
    full_code = context + "\n" + code
    if not code: return {'code': code, 'output': None, 'error': 'Generated code was empty.'}
    try:
        process = subprocess.run(['python', '-c', full_code], capture_output=True, text=True, timeout=20, check=False)
        return {'code': code, 'output': process.stdout, 'error': process.stderr if process.returncode != 0 else None}
    except Exception as e: return {'code': code, 'output': None, 'error': str(e)}

def _parse_json_from_llm_output(text: str) -> Dict:
    """
    【健壮版】从LLM可能返回的、带有格式标记的文本中提取JSON对象。
    """
    if not isinstance(text, str):
        return None
        
    try:
        # 策略1: 寻找被 ```json ... ``` 包裹的内容
        match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            return json.loads(json_str)

        # 策略2: 寻找第一个 '{' 和最后一个 '}' 之间的内容
        start_index = text.find('{')
        end_index = text.rfind('}')
        if start_index != -1 and end_index != -1 and end_index > start_index:
            json_str = text[start_index : end_index + 1]
            return json.loads(json_str)

        # 策略3: 尝试直接解析整个文本 (如果LLM返回了纯净JSON)
        return json.loads(text)

    except (json.JSONDecodeError, AttributeError):
        # 如果所有策略都失败，返回 None
        return None

def stage_1_batch_retrieval(prompts: List[str], retriever: RetrievalAPIClient) -> List[Dict]:
    console = Console(); console.print("  - Performing batch retrieval for all prompts via API...")
    batch_retrieved_results = retriever.search(prompts, k=3)
    final_aggregated_info = []
    for retrieved_results in batch_retrieved_results:
        agg_knowledge = {'knowledge_points': [], 'common_pitfalls': []}
        if retrieved_results:
            for res in retrieved_results:
                agg_knowledge['knowledge_points'].extend(res.get('knowledge_points', [])); agg_knowledge['common_pitfalls'].extend(res.get('common_pitfalls', []))
            agg_knowledge['knowledge_points'] = [dict(t) for t in {tuple(d.items()) for d in agg_knowledge['knowledge_points']}]
            agg_knowledge['common_pitfalls'] = list(set(agg_knowledge['common_pitfalls']))
        final_aggregated_info.append(agg_knowledge)
    return final_aggregated_info

# ============================= 主工作流 =============================
async def run_workflow(workflow: str, provider: str):
    is_async = (provider == 'api')
    console = Console()
    
    provider_config = CONFIG['providers'][provider]
    config = {**CONFIG['base'], **provider_config}
    config['batch_results_file'] = config['batch_results_file'].format(workflow=workflow, provider=provider)
    
    console.print(f"[bold magenta]Running workflow: '{workflow}' with provider: '{provider}' (Async: {is_async})[/bold magenta]")
    os.makedirs(os.path.dirname(config['batch_results_file']), exist_ok=True)

    console.print("[bold cyan]Initializing services...[/bold cyan]")
    retriever = RetrievalAPIClient(base_url=config["retrieval_api_url"])
    llm_service = get_llm_provider(provider_config)
    
    with open(config['test_questions_file'], 'r', encoding='utf-8') as f:
        test_questions = json.load(f)
    all_prompts = [q['prompt'] for q in test_questions]

    final_results_map = {}

    retrieved_info_batch = stage_1_batch_retrieval(all_prompts, retriever)

    if workflow == 'direct':
        # --- `direct` 模式: 强制所有问题走直接回答路径 ---
        console.print("[bold yellow]Executing 'direct' baseline workflow...[/bold yellow]")
        messages_batch = []
        for i, prompt in enumerate(all_prompts):
            knowledge_and_pitfalls = f"知识点:\n" + "\n".join([f"- {p['point']}: {p['description']}" for p in retrieved_info_batch[i].get('knowledge_points', [])])
            content = DIRECT_ANSWER_PROMPT.format(new_question_prompt=prompt, knowledge_and_pitfalls=knowledge_and_pitfalls)
            messages_batch.append([{"role": "user", "content": content}])
        if is_async: outputs = await llm_service.generate_with_think_and_parse_batch(messages_batch, enable_thinking=False)
        else: outputs = llm_service.generate_with_think_and_parse_batch(messages_batch, enable_thinking=False)
        for i, task_idx in enumerate(range(len(all_prompts))):
            final_results_map[task_idx] = {"response": outputs[i]['answer'], "metadata": {"workflow": f"direct_{provider}"}}

    elif workflow == 'full':
        console.print("[bold blue]Executing 'full' workflow with intelligent routing...[/bold blue]")
        
        # 批量分类
        messages_batch = [[{"role": "user", "content": QUESTION_CLASSIFICATION_PROMPT.format(question_prompt=p)}] for p in all_prompts]
        if is_async: json_outputs = await llm_service.generate_json_batch(messages_batch)
        else: json_outputs = llm_service.generate_json_batch(messages_batch)
        question_types = [o.get("question_type", "procedural") if isinstance(o, dict) else "procedural" for o in json_outputs]

        direct_tasks, procedural_tasks = [], []
        for i, q_type in enumerate(question_types):
            task_data = {"original_index": i, "prompt": all_prompts[i], "retrieved_info": retrieved_info_batch[i]}
            if q_type == 'direct': direct_tasks.append(task_data)
            else: procedural_tasks.append(task_data)
        console.print(f"[bold]Routing:[/bold] [green]{len(direct_tasks)} direct tasks[/green], [blue]{len(procedural_tasks)} procedural tasks[/blue].")

        if direct_tasks:
            console.print("\n[bold green]Processing routed Direct Answer Tasks...[/bold green]")
            messages_batch = []
            for task in direct_tasks:
                knowledge_and_pitfalls = f"知识点:\n" + "\n".join([f"- {p['point']}: {p['description']}" for p in task['retrieved_info'].get('knowledge_points', [])])
                content = DIRECT_ANSWER_PROMPT.format(new_question_prompt=task['prompt'], knowledge_and_pitfalls=knowledge_and_pitfalls)
                messages_batch.append([{"role": "user", "content": content}])
            if is_async: outputs = await llm_service.generate_with_think_and_parse_batch(messages_batch, enable_thinking=False)
            else: outputs = llm_service.generate_with_think_and_parse_batch(messages_batch, enable_thinking=False)
            for i, task in enumerate(direct_tasks):
                final_results_map[task['original_index']] = {"response": outputs[i]['answer'], "metadata": {"workflow": f"full_routed_direct_{provider}"}}
        
        if procedural_tasks:
            console.print(f"\n[bold blue]Processing {len(procedural_tasks)} Procedural Tasks with Iterative Solving...[/bold blue]")
            
            # 批量生成所有规划
            messages_batch = []
            for task in procedural_tasks:
                knowledge_and_pitfalls = f"知识点:\n" + "\n".join([f"- {p['point']}: {p['description']}" for p in task['retrieved_info'].get('knowledge_points', [])]) + "\n\n常见陷阱:\n" + "\n".join([f"- {p}" for p in task['retrieved_info'].get('common_pitfalls', [])])
                content = FRAMEWORK_GENERATION_PROMPT.format(question=task['prompt'], knowledge_and_pitfalls=knowledge_and_pitfalls)
                messages_batch.append([{"role": "user", "content": content}])
            if is_async: framework_outputs = await llm_service.generate_with_think_and_parse_batch(messages_batch, enable_thinking=True,max_token=6000)
            else: framework_outputs = llm_service.generate_with_think_and_parse_batch(messages_batch, enable_thinking=True,max_token=6000)
            solving_plans_str = [out['answer'] for out in framework_outputs]
            solving_plans = [_parse_json_from_llm_output(s) for s in solving_plans_str]

            for i, task in enumerate(procedural_tasks):
                original_index = task['original_index']
                prompt = task['prompt']
                solving_plan = solving_plans[i] # 获取已经解析好的JSON对象
                
                console.rule(f"[bold yellow]Processing Procedural Q#{original_index} (Iterative Mode)[/bold yellow]")
                
                # 【核心修正】检查解析是否成功
                if solving_plan is None:
                    console.print("[red]Error: Failed to parse solving plan JSON. Skipping question.[/red]")
                    # 在元数据中保存原始的、失败的输出来帮助调试
                    raw_plan = solving_plans_str[i]
                    final_results_map[original_index] = {"response": "Error: Failed to generate a valid solving plan.", "metadata": {"raw_plan_output": raw_plan}}
                    continue

                execution_context, full_trace, all_steps_succeeded = "# Execution context starts here.\n", "", True
                
                for subquestion_key, steps in solving_plan.items():
                    console.rule(f"Solving {subquestion_key}", style="cyan")
                    subproblem_framework = f"Instructions for {subquestion_key}:\n" + "\n".join([f"- {s['step']}: {s['core_operation']}" for s in steps])
                    
                    content = DIVERSE_CODE_GENERATION_PROMPT.format(original_question=prompt, execution_context=execution_context, subproblem_framework=subproblem_framework)
                    messages_batch = [[{"role": "user", "content": content}] for _ in range(3)]
                    if is_async: code_gen_outputs = await llm_service.generate_with_think_and_parse_batch(messages_batch, enable_thinking=False)
                    else: code_gen_outputs = llm_service.generate_with_think_and_parse_batch(messages_batch, enable_thinking=False)
                    code_candidates = [_parse_code(out['answer']) for out in code_gen_outputs]

                    step_exec_results = [_execute_code(code, execution_context) for code in code_candidates]
                    majority_result, _ = find_majority_result(step_exec_results)
                    
                    best_code_for_step, best_result_for_step = None, None
                    if majority_result:
                        best_code_for_step, best_result_for_step = majority_result['code'], majority_result
                    else:
                        successful_results = [r for r in step_exec_results if r['error'] is None and r['output']]
                        if successful_results:
                            analysis_str = format_divergent_codes_for_reflection(successful_results)
                            content = CODE_SELF_REFLECTION_PROMPT.format(original_question=prompt, subproblem_framework=subproblem_framework, execution_context=execution_context, divergent_codes_analysis=analysis_str)
                            reflection_messages = [[{"role": "user", "content": content}] for _ in range(3)]
                            if is_async: reflection_outputs = await llm_service.generate_with_think_and_parse_batch(reflection_messages, enable_thinking=False)
                            else: reflection_outputs = llm_service.generate_with_think_and_parse_batch(reflection_messages, enable_thinking=False)
                            revised_code_candidates = [_parse_code(out['answer']) for out in reflection_outputs]
                            
                            for revised_code in revised_code_candidates:
                                if not revised_code: continue
                                revised_result = _execute_code(revised_code, execution_context)
                                if revised_result['error'] is None:
                                    best_code_for_step, best_result_for_step = revised_code, revised_result
                                    break
                            
                            if best_code_for_step is None: # If all corrections failed
                                content = FALLBACK_DECISION_PROMPT.format(original_question=prompt, subproblem_framework=subproblem_framework, successful_solutions_analysis=analysis_str)
                                if is_async: decision_json_list = await llm_service.generate_json_batch([[{"role": "user", "content": content}]])
                                else: decision_json_list = llm_service.generate_json_batch([[{"role": "user", "content": content}]])
                                decision = decision_json_list[0]
                                best_index = int(decision.get("best_fallback_index", 1)) - 1 if decision else 0
                                best_code_for_step, best_result_for_step = successful_results[best_index]['code'], successful_results[best_index]

                    if best_code_for_step is None:
                        console.print(f"[red]❌ Failed to solve {subquestion_key}. Aborting workflow for this question.[/red]")
                        all_steps_succeeded = False; break

                    execution_context += f"\n# --- Code for {subquestion_key} ---\n{best_code_for_step}\n"
                    full_trace += f"--- {subquestion_key} ---\n[Code]:\n{best_code_for_step}\n[Result]:\n{best_result_for_step['output']}\n\n"
                
                if all_steps_succeeded:
                    console.print("\n[bold blue]All sub-questions solved. Synthesizing final answer...[/bold blue]")
                    content = FINAL_SYNTHESIS_PROMPT.format(original_question=prompt, full_execution_trace=full_trace)
                    if is_async: final_answer_output = await llm_service.generate_with_think_and_parse_batch([[{"role": "user", "content": content}]], enable_thinking=False)
                    else: final_answer_output = llm_service.generate_with_think_and_parse_batch([[{"role": "user", "content": content}]], enable_thinking=False)
                    final_results_map[original_index] = {"response": final_answer_output[0]['answer'], "metadata": {"workflow": f"full_iterative_{provider}", "trace": full_trace}}
                else:
                    final_results_map[original_index] = {"response": "Error: Failed during iterative solving process.", "metadata": {"workflow": f"full_iterative_failed_{provider}", "trace": full_trace}}

    all_final_results = []
    for i, q in enumerate(test_questions):
        result_data = final_results_map.get(i, {"response": "ERROR: Task was not processed.", "metadata": {}})
        all_final_results.append({"id": q.get('id', str(uuid.uuid4())), "prompt": q['prompt'], "ground_truth_answer": q.get('answer', 'N/A'), **result_data})

    with open(config['batch_results_file'], 'w', encoding='utf-8') as f:
        json.dump(all_final_results, f, ensure_ascii=False, indent=2)
    console.print(f"\n[bold bright_green]'{workflow}' workflow with '{provider}' provider complete! Results saved to {config['batch_results_file']}.[/bold bright_green]")


# ============================= 入口点 =============================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Self-Consistent and Iterative 408 Solver.")
    parser.add_argument("--workflow", type=str, choices=["full", "direct"], default="full", help="Workflow: 'full' for intelligent iterative solving, 'direct' for baseline.")
    parser.add_argument("--provider", type=str, choices=["local", "api","glm4.5"], default="api", help="LLM Provider: 'local' for sync local inference, 'api' for async API inference.")
    args = parser.parse_args()
    asyncio.run(run_workflow(args.workflow, args.provider))