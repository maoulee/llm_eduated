import argparse
import asyncio
import json
import logging
import uuid
from typing import Dict, Any

from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn

from config import settings, get_provider_config, get_retrieval_api_url
from core_new.workflow import IterativeSolverWorkflow
from llm_providers_new import get_llm_provider
from core_new.retrieval_api_client import RetrievalAPIClient

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
    """Run one question through the selected workflow with concurrency control."""
    async with semaphore:
        prompt = question.get("prompt", "")
        if not prompt:
            logger.warning(f"Skipping question with empty prompt: {question.get('id', 'N/A')}")
            result = {
                "prompt": "",
                "response": "Error: Input prompt was empty.",
                "metadata": {"workflow": "input_error"},
            }
        else:
            result = await workflow_engine.run(
                prompt=prompt,
                workflow_mode=workflow_mode,
                max_tokens=max_tokens,
            )

        progress.update(task_id, advance=1)
        return {
            "id": question.get("id", str(uuid.uuid4())),
            "prompt": prompt,
            "ground_truth_answer": question.get("answer", "N/A"),
            **result,
        }


async def run_batch_workflow(
    provider_name: str,
    workflow_mode: str,
    questions_file: str,
    output_file: str,
    max_concurrency: int,
    max_tokens: int,
):
    """Run a batch of questions through the modern solver workflow."""
    console = Console()
    console.rule("[bold magenta]Batch Runner v3.0[/bold magenta]")
    console.print(f"  - Provider: [cyan]{provider_name}[/cyan]")
    console.print(f"  - Workflow: [cyan]{workflow_mode}[/cyan]")
    console.print(f"  - Max Tokens: [yellow]{max_tokens}[/yellow]")
    console.print(f"  - Max Concurrency: [yellow]{max_concurrency}[/yellow]")
    console.print(f"  - Input File: [green]{questions_file}[/green]")

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

    try:
        with open(questions_file, "r", encoding="utf-8") as f:
            questions = json.load(f)
        console.print(f"Loaded {len(questions)} questions.")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[bold red]Error loading questions file at '{questions_file}': {e}[/bold red]")
        return

    semaphore = asyncio.Semaphore(max_concurrency)
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed} of {task.total})"),
        TimeElapsedColumn(),
        console=console,
    )

    with progress:
        task_progress_id = progress.add_task("[cyan]Solving questions...[/cyan]", total=len(questions))
        tasks = [
            controlled_worker(
                semaphore=semaphore,
                workflow_engine=workflow_engine,
                question=q,
                workflow_mode=workflow_mode,
                progress=progress,
                task_id=task_progress_id,
                max_tokens=max_tokens,
            )
            for q in questions
        ]

        try:
            final_output_list = await asyncio.gather(*tasks)
        except Exception as e:
            console.print(f"[bold red]An unrecoverable error occurred during batch processing: {e}[/bold red]")
            logger.error("asyncio.gather failed", exc_info=True)
            return

    console.print(f"\n[bold]Saving {len(final_output_list)} results to [green]{output_file}[/green]...[/bold]")
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_output_list, f, ensure_ascii=False, indent=2)
        console.print("\n[bold bright_green]Batch run complete.[/bold bright_green]")
    except IOError as e:
        console.print(f"[bold red]Error saving results to file: {e}[/bold red]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Batch solver for modern 408 reasoning / verification / annotation workflow.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="api_vllm",
        choices=list(settings.providers.keys()),
        help="The LLM provider to use, as defined in config.py.",
    )
    parser.add_argument(
        "--workflow",
        type=str,
        default="full",
        choices=["full", "direct", "modern", "hybrid"],
        help="The solving workflow to execute. 'modern' and 'hybrid' run reasoning + optional code verification + annotation.",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=settings.paths.evaluation_questions,
        help="Path to the input JSON file containing questions.",
    )
    parser.add_argument(
        "--output-name",
        type=str,
        default="default_run",
        help="A unique name for this batch run, used to generate the output file name.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Maximum number of concurrent requests to the LLM API.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8192,
        help="Maximum tokens passed to the solver workflow.",
    )

    args = parser.parse_args()
    output_file_path = settings.paths.batch_results_template.format(run_name=args.output_name)

    asyncio.run(
        run_batch_workflow(
            provider_name=args.provider,
            workflow_mode=args.workflow,
            max_tokens=args.max_tokens,
            questions_file=args.input,
            output_file=output_file_path,
            max_concurrency=args.concurrency,
        )
    )
