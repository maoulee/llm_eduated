# main_evaluate_results_new.py

"""
评估脚本：
1. 加载指定批量运行（run_name）的结果文件。
2. 使用LLM对每个答案进行多次评分，以确保结果的稳定性。
3. 使用中位数计算最终分数，以抵抗异常值。
4. 生成并打印详细的评估报告，并保存到文件。
"""

import argparse
import asyncio
import json
import logging
import os
import re
from typing import Optional

import numpy as np
from rich.console import Console
from rich.table import Table

# --- 从重构后的模块导入 ---
from config import settings, get_provider_config
from llm_providers_new import get_llm_provider
from core_new.prompts import SCORING_PROMPT

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def parse_score(scoring_text: str) -> Optional[float]:
    """从LLM的评分文本中健壮地解析出0.0到1.0之间的分数。"""
    if not isinstance(scoring_text, str):
        return None
    score = None
    try:
        match = re.search(r'\\boxed\{([\d.]+)\}', scoring_text)
        if match:
            score = float(match.group(1))
        else:
            numbers = re.findall(r'[\d.]+', scoring_text)
            if numbers:
                score = float(numbers[-1])
        
        if score is not None and 0.0 <= score <= 1.0:
            return score
        return None
    except (ValueError, IndexError):
        return None


async def main(run_name: str, provider_name: str):
    """
    异步主函数，执行评估流程。
    """
    console = Console()
    console.rule(f"[bold cyan]Evaluating Batch Run: '{run_name}'[/bold cyan]")

    # 1. 确定文件路径
    batch_results_file = settings.paths.batch_results_template.format(run_name=run_name)
    evaluation_report_file = settings.paths.evaluation_report_template.format(run_name=run_name)

    console.print(f"--> Loading results from: [green]{batch_results_file}[/green]")
    if not os.path.exists(batch_results_file):
        console.print(f"[bold red]Error: Input file not found![/bold red]")
        return

    # 2. 初始化LLM服务 (用于评分)
    console.print(f"--> Initializing LLM Service for scoring (Provider: '{provider_name}')...")
    try:
        provider_config = get_provider_config(provider_name)
        llm_service = get_llm_provider(provider_config)
    except Exception as e:
        console.print(f"[bold red]Error initializing LLM Provider: {e}[/bold red]")
        return

    # 3. 加载结果并准备评分请求
    with open(batch_results_file, 'r', encoding='utf-8') as f:
        solved_questions = json.load(f)

    scoring_messages_batch, task_map = [], []
    for i, item in enumerate(solved_questions):
        if not item.get('response') or "ERROR" in item.get('response', ''):
            continue
        content = SCORING_PROMPT.format(response=item['response'], ground_truth=item['ground_truth_answer'])
        messages = [{"role": "user", "content": content}]
        for _ in range(settings.evaluation_runs):
            scoring_messages_batch.append(messages)
            task_map.append(i)

    if not scoring_messages_batch:
        console.print("[bold yellow]No valid questions to score.[/bold yellow]")
        return

    # 4. 批量评分
    console.print(f"\n--> Sending {len(scoring_messages_batch)} scoring requests to LLM...")
    scoring_outputs = await llm_service.generate_with_think_and_parse_batch(scoring_messages_batch, enable_thinking=False)
    scoring_texts = [output['answer'] for output in scoring_outputs]

    # 5. 解析并计算最终得分
    console.print("--> Parsing scores and calculating final results...")
    scores_per_question = [[] for _ in range(len(solved_questions))]
    for i, raw_score_text in enumerate(scoring_texts):
        original_question_index = task_map[i]
        score = parse_score(raw_score_text)
        if score is not None:
            scores_per_question[original_question_index].append(score)

    evaluation_results, total_final_score, scored_question_count = [], 0, 0
    for i, item in enumerate(solved_questions):
        scores = scores_per_question[i]
        final_score = float(np.median(scores)) if scores else None
        if final_score is not None:
            total_final_score += final_score
            scored_question_count += 1
        evaluation_results.append({"id": item.get('id'), "prompt": item['prompt'], "individual_scores": scores, "final_score_median": final_score})

    overall_average_score = (total_final_score / scored_question_count) if scored_question_count > 0 else 0.0

    # 6. 生成并打印/保存报告
    console.rule("[bold bright_green]Evaluation Report[/bold bright_green]")
    table = Table(title=f"Evaluation for Run: '{run_name}'")
    table.add_column("ID", style="cyan"); table.add_column("Prompt (Snippet)", max_width=60); table.add_column("Scores", style="yellow"); table.add_column("Final (Median)", style="green")
    for result in evaluation_results:
        table.add_row(
            str(result['id'])[:8],
            result['prompt'][:70].replace("\n", " "),
            ", ".join([f"{s:.2f}" for s in result['individual_scores']]) if result['individual_scores'] else "N/A",
            f"{result['final_score_median']:.2f}" if result['final_score_median'] is not None else "N/A"
        )
    console.print(table)
    console.print(f"\n[bold]Total Scored Questions:[/bold] {scored_question_count} / {len(solved_questions)}")
    console.print(f"[bold bright_green]Overall Average Score: {overall_average_score:.4f}[/bold bright_green]")

    report_data = {"overall_average_score": overall_average_score, "details": evaluation_results}
    with open(evaluation_report_file, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    console.print(f"\n--> Detailed report saved to [green]{evaluation_report_file}[/green]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate batch run results using an LLM.")
    parser.add_argument("run_name", type=str, help="The unique name of the batch run to evaluate.")
    parser.add_argument("--provider", type=str, default="local", choices=settings.providers.keys(), help="LLM provider for scoring.")
    args = parser.parse_args()
    asyncio.run(main(args.run_name, args.provider))