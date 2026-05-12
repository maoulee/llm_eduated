# main_evaluate_results.py
from core.llm_service import LLMService
from core.prompts import SCORING_PROMPT
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
import json
import os
import re
import numpy as np
from typing import List, Dict, Optional

# --- 配置 ---
LLM_MODEL_PATH = "/zhaoshu/llm/qwen3-32b/"
BATCH_RESULTS_FILE = "/zhaoshu/mcts_reason/data/batch_results.json"
EVALUATION_REPORT_FILE = "/zhaoshu/mcts_reason/data/evaluation_report1.json"
NUM_SCORING_RUNS = 3 # 每个答案评分3次

def parse_score(scoring_text: str) -> Optional[float]:
    """
    从LLM的评分文本中解析出分数。
    增强版：只接受 0.0 到 1.0 之间的有效分数。
    """
    score = None
    try:
        # 优先寻找 <score>\boxed{...}</score> 结构
        match = re.search(r'<score>\s*\\boxed\{([\d.]+)\}\s*</score>', scoring_text)
        if match:
            score = float(match.group(1))
        else:
            # 备用方案：直接从文本中找最后一个数字
            numbers = re.findall(r'[\d.]+', scoring_text)
            if numbers:
                score = float(numbers[-1])
        
        # --- 核心改进：验证分数的有效性 ---
        if score is not None and 0.0 <= score <= 1.0:
            return score
        else:
            # 如果分数无效 (None, >1, <0, inf, etc.)，则返回 None
            return None
            
    except (ValueError, IndexError):
        # 解析失败返回 None
        return None

def main():
    console = Console()
    
    # 1. 检查结果文件是否存在
    if not os.path.exists(BATCH_RESULTS_FILE):
        console.print(f"[bold red]Error: Batch results file not found at {BATCH_RESULTS_FILE}. Please run main_batch_solve.py first.[/bold red]")
        return

    # 2. 初始化LLM服务
    console.print("[bold cyan]Initializing LLM Service for evaluation...[/bold cyan]")
    llm_service = LLMService(model_name=LLM_MODEL_PATH)

    # 3. 加载所有已解决的问题
    with open(BATCH_RESULTS_FILE, 'r', encoding='utf-8') as f:
        solved_questions = json.load(f)

    console.print(f"Loaded {len(solved_questions)} solved questions for evaluation.")

    # 4. 准备批量评分请求
    console.print(f"[bold]Preparing batch scoring requests (each question will be scored {NUM_SCORING_RUNS} times)...[/bold]")
    scoring_messages_batch = []
    task_map = [] 
    
    for i, item in enumerate(solved_questions):
        # 跳过处理失败或没有答案的条目
        if not item.get('response') or "ERROR" in item.get('response'):
            continue
            
        content = SCORING_PROMPT.format(
            response=item['response'],
            ground_truth=item['ground_truth_answer']
        )
        messages = [{"role": "user", "content": content}]
        for _ in range(NUM_SCORING_RUNS):
            scoring_messages_batch.append(messages)
            task_map.append(i)

    if not scoring_messages_batch:
        console.print("[bold yellow]No valid questions to score.[/bold yellow]")
        return

    # 5. 一次性批量评分
    console.print(f"[bold cyan]Sending {len(scoring_messages_batch)} scoring requests to LLM...[/bold cyan]")
    scoring_outputs = llm_service._generate_batch(
        llm_service._apply_template_batch(scoring_messages_batch, enable_thinking=False)
    )

    # 6. 解析并计算最终得分（使用中位数）
    console.print("[bold cyan]Parsing scores and calculating final scores using median...[/bold cyan]")
    
    scores_per_question = [[] for _ in range(len(solved_questions))]
    
    for i, raw_score_text in enumerate(scoring_outputs):
        original_question_index = task_map[i]
        # parse_score 现在会过滤掉所有无效分数
        score = parse_score(raw_score_text)
        if score is not None:
            scores_per_question[original_question_index].append(score)

    evaluation_results = []
    total_final_score = 0
    scored_question_count = 0

    for i, item in enumerate(solved_questions):
        scores = scores_per_question[i]
        
        # --- 核心改进：使用中位数代替平均数，以提高对异常值的鲁棒性 ---
        final_score = float(np.median(scores)) if scores else None
        
        # 只对成功评分的问题计算总分
        if final_score is not None:
            total_final_score += final_score
            scored_question_count += 1
            
        evaluation_results.append({
            "id": item.get('id'),
            "prompt": item['prompt'],
            "individual_scores": scores,
            "final_score_median": final_score
        })

    overall_average_score = (total_final_score / scored_question_count) if scored_question_count > 0 else 0.0

    # 7. 生成并打印评估报告
    console.print("\n" + "="*50)
    console.print("[bold bright_green]EVALUATION REPORT[/bold bright_green]")
    console.print("="*50 + "\n")

    table = Table(title="Individual Question Scores")
    table.add_column("ID", justify="left", style="cyan")
    table.add_column("Prompt (Snippet)", justify="left", style="magenta", max_width=60)
    table.add_column("Valid Scores", justify="center", style="yellow")
    table.add_column("Final Score (Median)", justify="right", style="green")

    for result in evaluation_results:
        prompt_snippet = result['prompt'][:70] + "..." if len(result['prompt']) > 70 else result['prompt']
        scores_str = ", ".join([f"{s:.2f}" for s in result['individual_scores']]) if result['individual_scores'] else "[No Valid Scores]"
        score_val = result['final_score_median']
        
        table.add_row(
            result['id'],
            prompt_snippet,
            scores_str,
            f"{score_val:.2f}" if score_val is not None else "N/A"
        )
    
    console.print(table)
    # --- BUG 修复：确保所有打开的标签都被关闭 ---
    console.print(f"\n[bold]Total Scored Questions:[/bold] {scored_question_count} / {len(solved_questions)}")
    console.print(f"[bold bright_green]Overall Average Score: {overall_average_score:.4f}[/bold bright_green]")

    # 8. 保存详细报告到文件
    report_data = {
        "overall_average_score": float(overall_average_score),
        "total_questions": len(solved_questions),
        "scored_questions": scored_question_count,
        "scoring_runs_per_question": NUM_SCORING_RUNS,
        "details": evaluation_results
    }
    os.makedirs(os.path.dirname(EVALUATION_REPORT_FILE), exist_ok=True)
    with open(EVALUATION_REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    console.print(f"\n[bold]Detailed evaluation report saved to {EVALUATION_REPORT_FILE}[/bold]")


if __name__ == "__main__":
    main()