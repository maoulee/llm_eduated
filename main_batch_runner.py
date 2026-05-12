import argparse
import asyncio
import json
import logging
import uuid
from typing import List, Dict, Any

from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

# --- 从重构后的模块导入 ---
# 确保你的文件夹名称与导入路径一致 (例如 core_new, llm_providers_new)
from config import settings, get_provider_config, get_retrieval_api_url
from core_new.workflow import IterativeSolverWorkflow
from llm_providers_new import get_llm_provider
from core_new.retrieval_api_client import RetrievalAPIClient

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def controlled_worker(
    semaphore: asyncio.Semaphore,
    workflow_engine: IterativeSolverWorkflow,
    question: Dict[str, Any],
    workflow_mode: str,
    progress: Progress,
    task_id: Any,
    max_tokens: int,
) -> Dict[str, Any]:
    """
    一个被信号量控制的异步 worker 函数。

    它会先获取一个信号量“许可”，执行核心工作流，然后在完成后释放许可。
    这个函数还负责将原始问题信息与工作流的输出结果进行合并，以保证数据的完整性。

    Args:
        semaphore: asyncio.Semaphore 实例用于并发控制。
        workflow_engine: IterativeSolverWorkflow 的实例。
        question: 单个问题的数据字典 (包含 'prompt', 'id', 'answer')。
        workflow_mode: 要执行的工作流模式 ('full' 或 'direct')。
        progress: Rich Progress 实例用于更新进度条。
        task_id: Rich Progress 分配的任务ID。

    Returns:
        一个包含所有信息的完整结果字典。
    """
    async with semaphore:
        # 信号量确保这里同时执行的任务不会超过限制
        prompt = question.get('prompt', '')
        if not prompt:
            logger.warning(f"Skipping question with empty prompt: {question.get('id', 'N/A')}")
            # 即使输入有问题，也返回一个结构一致的错误结果
            result = {
                "prompt": "",
                "response": "Error: Input prompt was empty.",
                "metadata": {"workflow": "input_error"}
            }
        else:
            # 调用核心工作流
            result = await workflow_engine.run(prompt,max_tokens, workflow_mode)
        
        # 更新进度条
        progress.update(task_id, advance=1)
        
        # 将原始问题信息与工作流的结果合并
        # result 已经包含了 "prompt", "response", "metadata"
        final_result = {
            "id": question.get('id', str(uuid.uuid4())),
            "ground_truth_answer": question.get('answer', 'N/A'),
            **result
        }
        return final_result


async def run_batch_workflow(
    provider_name: str,
    workflow_mode: str,
    questions_file: str,
    output_file: str,
    max_concurrency: int,
    max_tokens: int
):
    """
    主函数，编排整个批量处理流程。
    """
    console = Console()
    console.rule(f"[bold magenta]Batch Runner v2.1 (Final)[/bold magenta]")
    console.print(f"  - Provider: [cyan]{provider_name}[/cyan]")
    console.print(f"  - Workflow: [cyan]{workflow_mode}[/cyan]")
    console.print(f"  - Max Concurrency: [yellow]{max_concurrency}[/yellow]")
    console.print(f"  - Input File: [green]{questions_file}[/green]")

    # 1. 初始化服务
    console.print("\n[bold]Initializing services...[/bold]")
    try:
        provider_config = get_provider_config(provider_name)
        llm_provider = get_llm_provider(provider_config)
        retriever_client = RetrievalAPIClient(base_url=get_retrieval_api_url())
        workflow_engine = IterativeSolverWorkflow(llm_provider, retriever_client)
    except Exception as e:
        console.print(f"[bold red]Error during initialization: {e}[/bold red]")
        logger.error("Initialization failed", exc_info=True)
        return

    # 2. 加载问题
    try:
        with open(questions_file, 'r', encoding='utf-8') as f:
            questions = json.load(f)
        console.print(f"Loaded {len(questions)} questions.")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[bold red]Error loading questions file at '{questions_file}': {e}[/bold red]")
        return

    # 3. 设置并发控制器
    semaphore = asyncio.Semaphore(max_concurrency)

    # 4. 创建并发任务
    # 设置一个更美观的进度条
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed} of {task.total})"),
        TimeElapsedColumn(),
        console=console
    )

    with progress:
        task_progress_id = progress.add_task(f"[cyan]Solving questions...[/cyan]", total=len(questions))
        
        tasks = [
            controlled_worker(semaphore, workflow_engine, q, workflow_mode, progress, task_progress_id,max_tokens)
            for q in questions
        ]

        # 使用 asyncio.gather 来并发执行所有任务
        # gather 会等待所有任务完成，并按原始顺序返回结果列表，完美解决顺序问题。
        try:
            final_output_list = await asyncio.gather(*tasks)
        except Exception as e:
            console.print(f"[bold red]An unrecoverable error occurred during batch processing: {e}[/bold red]")
            logger.error("asyncio.gather failed", exc_info=True)
            return

    # 5. 保存结果
    console.print(f"\n[bold]Saving {len(final_output_list)} results to [green]{output_file}[/green]...[/bold]")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_output_list, f, ensure_ascii=False, indent=2)
        console.print(f"\n[bold bright_green]✅ Batch run complete![/bold bright_green]")
    except IOError as e:
        console.print(f"[bold red]Error saving results to file: {e}[/bold red]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Unified Batch Solver with Concurrency Control.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # 让--help输出更好看
    )
    
    parser.add_argument(
        "--provider",
        type=str,
        default="api_vllm",
        choices=list(settings.providers.keys()),
        help="The LLM provider to use, as defined in config.py."
    )
    parser.add_argument(
        "--workflow",
        type=str,
        default="full",
        choices=["full", "direct"],
        help="The solving workflow to execute."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=settings.paths.evaluation_questions,
        help="Path to the input JSON file containing questions."
    )
    parser.add_argument(
        "--output-name",
        type=str,
        default="default_run",
        help="A unique name for this batch run, used to generate the output file name."
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Maximum number of concurrent requests to the LLM API."
    )
    
    args = parser.parse_args()

    # 根据 --output-name 参数，从配置模板生成最终的输出文件路径
    output_file_path = settings.paths.batch_results_template.format(run_name=args.output_name)
    
    # 启动异步事件循环来运行我们的主函数
    asyncio.run(run_batch_workflow(
        provider_name=args.provider,
        workflow_mode=args.workflow,
        max_tokens=15000,
        questions_file=args.input,
        output_file=output_file_path,
        max_concurrency=args.concurrency
    ))