# solve_interactively_new.py

"""
交互式命令行解题工具。
允许用户输入问题，并实时查看由核心工作流引擎生成的完整解题过程。
"""

import asyncio
import logging
import json
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown

# --- 从重构后的模块导入 ---
from config import settings, get_provider_config, get_retrieval_api_url
from core_new.workflow import IterativeSolverWorkflow
from llm_providers_new import get_llm_provider
from core_new.retrieval_api_client import RetrievalAPIClient

# --- 日志配置 ---
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')


def display_result(result: dict, console: Console):
    """使用Rich库格式化并打印单次解题结果。"""
    metadata = result.get('metadata', {})
    workflow_type = metadata.get('workflow', 'unknown')
    
    console.rule(f"[bold yellow]解题报告[/bold yellow]", style="yellow")
    
    # 打印最终答案
    console.print(Panel(result.get('response', '无答案'), title="[green bold]最终答案[/green bold]", border_style="green", expand=True))
    
    # 打印元数据作为详细信息
    md_text = f"### 工作流详情\n- **工作流类型**: `{workflow_type}`\n- **问题分类**: `{metadata.get('question_type', 'N/A')}`\n"
    
    if 'plan' in metadata:
        plan_str = json.dumps(metadata['plan'], ensure_ascii=False, indent=2)
        md_text += f"### 解题规划\n```json\n{plan_str}\n```\n"

    if 'trace' in metadata and metadata['trace']:
        md_text += f"### 执行轨迹\n```\n{metadata['trace']}\n```\n"
        
    if 'retrieved_knowledge' in metadata and metadata['retrieved_knowledge'].get('knowledge_points'):
        md_text += "### 参考知识点\n"
        for p in metadata['retrieved_knowledge']['knowledge_points']:
            md_text += f"- **{p.get('point')}**: {p.get('description')}\n"

    console.print(Panel(Markdown(md_text), title="[cyan]详细元数据[/cyan]", border_style="cyan", expand=True))


async def main():
    """异步主函数，处理交互式会话。"""
    console = Console()
    console.rule("[bold cyan]Interactive Solver CLI[/bold cyan]")
    
    # 1. 初始化服务
    console.print("--> Initializing services (local provider by default)...")
    try:
        # 交互模式通常用本地模型，因为它响应快且不耗费API额度
        provider_config = get_provider_config("local")
        llm_provider = get_llm_provider(provider_config)
        retriever_client = RetrievalAPIClient(base_url=get_retrieval_api_url())
        workflow_engine = IterativeSolverWorkflow(llm_provider, retriever_client)
    except Exception as e:
        console.print(f"[bold red]Initialization failed: {e}[/bold red]")
        return

    console.print("[bold green]✅ Engine ready! Type your question or 'exit' to quit.[/bold green]")
    
    while True:
        try:
            question = console.input("\n[bold yellow]>>> [/bold yellow]")
            if question.lower().strip() in ['exit', 'quit']:
                break
            if not question.strip():
                continue

            with console.status("[bold blue]Thinking...", spinner="dots"):
                # 2. 调用核心工作流
                solution_result = await workflow_engine.run(question, workflow_mode="full")
            
            # 3. 展示结果
            display_result(solution_result, console)

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
            logging.error("Interactive loop error", exc_info=True)
            
    console.print("\n[bold cyan]Goodbye![/bold cyan]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting.")