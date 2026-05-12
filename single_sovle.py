# solve_interactively.py

import json
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown

from llm_providers import get_llm_provider
from core.retriever import Retriever
from llm_providers.interactive_solver import InteractiveSolver

# --- 配置 (主要用于API模式) ---
CONFIG = {
    "provider_type": "api",
    "model_path": "/zhaoshu/llm/qwen3-32b/",
    "api_url": "http://localhost:8000/v1",
    "embedding_model_path": "/zhaoshu/llm/BAAI/bge-m3/",
    "metadata_db_file": "/zhaoshu/mcts_reason/artifacts/metadata_db_full.json",
    "faiss_index_file": "/zhaoshu/mcts_reason/artifacts/faiss_index_full.bin"
}

def display_result(result: dict, console: Console):
    """使用Rich库格式化并打印单次解题结果"""
    metadata = result.get('metadata', {})
    question_type = metadata.get('question_type', 'unknown')

    console.rule(f"[bold yellow]解题报告[/bold yellow]", style="yellow")
    console.print(Panel(f"[bold]题目：[/bold]{result['prompt']}", title="[blue]Question[/blue]", border_style="blue"))
    
    console.print(f"\n[bold]解题路径分析：[/bold]模型判断此题为 [magenta]{question_type}[/magenta] 类型。")

    if question_type == 'direct':
        # 直接回答路径的展示
        retrieved_knowledge = metadata.get('retrieved_knowledge', {})
        if retrieved_knowledge and retrieved_knowledge.get('knowledge_points'):
            md_text = "#### 参考知识点:\n" + "\n".join([f"- **{p.get('point')}**: {p.get('description')}" for p in retrieved_knowledge['knowledge_points']])
            console.print(Panel(Markdown(md_text), title="[cyan]参考知识[/cyan]", border_style="cyan"))
        
        console.print(Panel(result['response'], title="[green bold]最终答案 (直接生成)[/green bold]", border_style="green"))

    elif question_type == 'procedural':
        # 程序化路径的展示
        retrieved_knowledge = metadata.get('retrieved_knowledge', {})
        if retrieved_knowledge and retrieved_knowledge.get('knowledge_points'):
             md_text = "#### 参考知识点:\n" + "\n".join([f"- **{p.get('point')}**: {p.get('description')}" for p in retrieved_knowledge['knowledge_points']])
             console.print(Panel(Markdown(md_text), title="[cyan]1. 知识检索[/cyan]", border_style="cyan"))
        
        pseudocode = metadata.get('consensus_pseudocode', 'N/A')
        console.print(Panel(Syntax(pseudocode, "pseudocode", theme="monokai"), title="[magenta]2. 解题计划 (伪代码)[/magenta]", border_style="magenta"))

        reconstruction_status = "[bold red]是" if metadata.get('was_reconstructed') else "[bold green]否"
        final_answer_panel = Panel(
            f"**自我修正:** {reconstruction_status}\n\n---\n\n**解题步骤:**\n{result['response']}",
            title="[green]3. 解题执行与最终答案[/green]",
            border_style="green"
        )
        console.print(final_answer_panel)
    else:
        console.print(Panel(result['response'], title="[yellow]未知类型答案[/yellow]", border_style="yellow"))


def main():
    console = Console()
    console.print("[bold cyan]初始化交互式解题引擎 (API模式)...[/bold cyan]")
    
    # 初始化服务
    try:
        llm_provider = get_llm_provider(CONFIG)
        retriever = Retriever(model_name=CONFIG["embedding_model_path"])
        retriever.load_index(CONFIG['metadata_db_file'], CONFIG['faiss_index_file'])
        solver = InteractiveSolver(llm_provider, retriever)
    except Exception as e:
        console.print(f"[bold red]初始化失败: {e}[/bold red]")
        console.print("请确保：\n1. vLLM API服务器正在运行。\n2. 所有文件路径都正确。")
        return

    console.print("[bold green]引擎就绪！[/bold green] 您现在可以输入问题。输入 'exit' 或 'quit' 退出。")
    
    while True:
        try:
            question = console.input("[bold yellow]请输入您的问题 > [/bold yellow]")
            if question.lower() in ['exit', 'quit']:
                break
            if not question.strip():
                continue

            with console.status("[bold blue]正在思考，请稍候...", spinner="dots"):
                solution_result = solver.solve(question)
            
            display_result(solution_result, console)

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[bold red]发生错误: {e}[/bold red]")
            
    console.print("\n[bold cyan]再见！[/bold cyan]")


if __name__ == "__main__":
    main()