# generate_reports.py

import json
import os
from typing import Dict, List
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.rule import Rule
from rich.table import Table
import argparse

def generate_single_report_markdown(result: Dict) -> str:
    """
    为单个问题生成纯 Markdown 格式的报告字符串。
    【新】智能适应 'full' 和 'direct' 两种模式的结果。
    """
    md = []
    metadata = result.get('metadata', {})
    
    # --- 共通部分 ---
    md.append(f"# 解题报告: {result.get('id', 'N/A')}")
    md.append("---")
    md.append("## 1. 原始问题")
    md.append(f"```\n{result.get('prompt', 'N/A')}\n```")

    # --- 【核心修改】根据工作流类型选择报告模板 ---
    workflow = metadata.get('workflow', 'unknown')
    # 兼容旧的 'question_type' 字段
    if 'direct' in workflow or metadata.get('question_type', '').startswith('direct'):
        # --- Direct 模式报告模板 ---
        md.append("## 2. AI 解题策略分析")
        md.append(f"**工作流模式**: **直接回答 (Direct Answer)**")
        md.append("> AI被指示不使用复杂的代码生成或验证流程，而是直接根据其内部知识和少量检索信息进行回答。这通常用作评估复杂流程效果的基线。")

        md.append("## 3. 最终解题步骤")
        md.append("> 这是AI直接生成的答案，可用于评分。")
        response_formatted = result.get('response', 'N/A').replace("[end_of_subquestion]", "\n---\n")
        md.append(response_formatted)

    else: # 默认视为 'full' (self-consistent) 模式
        # --- Full 模式报告模板 ---
        md.append("## 2. AI 解题策略分析")
        consensus_method = metadata.get('consensus_method', '未知')
        if consensus_method == "majority_vote":
            strategy = f"**工作流模式**: **自洽性完整流程 (Self-Consistent Full Workflow)**\n\n**共识方法**: **多数派投票 (Majority Vote)**\n- **投票结果**: 在 {metadata.get('total_codes', '?')} 个代码版本中，有 {metadata.get('votes', '?')} 个版本的结果达成一致。"
        elif consensus_method == "self_correction_success":
            strategy = f"**工作流模式**: **自洽性完整流程 (Self-Consistent Full Workflow)**\n\n**共识方法**: **自我修正 (Self-Correction)**\n- **过程**: 初始代码版本结果不一致，AI通过分析分歧，成功生成了一个修正后的版本。"
        elif consensus_method == "fallback":
            strategy = f"**工作流模式**: **自洽性完整流程 (Self-Consistent Full Workflow)**\n\n**共识方法**: **修正失败后回退 (Fallback)**\n- **过程**: AI在尝试自我修正失败后，采纳了第一个成功执行的原始代码版本作为备用方案。"
        else:
            strategy = f"**工作流模式**: **自洽性完整流程 (Self-Consistent Full Workflow)**\n\n**共识方法**: {consensus_method}"
        md.append(strategy)
        
        md.append("### 最终采纳的代码")
        md.append(f"> 这是AI最终信任的、用于生成答案的“事实标准”。")
        md.append(f"```python\n{metadata.get('final_code_used', 'N/A')}\n```")

        md.append("## 3. 最终解题步骤")
        md.append("> 这是根据最终采纳的代码及其运行结果生成的自然语言解释，可用于评分。")
        response_formatted = result.get('response', 'N/A').replace("[end_of_subquestion]", "\n---\n")
        md.append(response_formatted)
        
        # 附录部分
        if metadata.get('all_execution_results'):
            md.append("\n---\n")
            md.append("## 附录: AI的“草稿纸” - 所有代码版本执行详情")
            for i, res in enumerate(metadata['all_execution_results']):
                md.append(f"### 版本 #{i+1}")
                md.append(f"```python\n{res.get('code', 'N/A')}\n```")
                if res.get('error'):
                    md.append(f"**错误**:\n```\n{res['error']}\n```")
                else:
                    md.append(f"**输出**:\n```\n{res.get('output', '无输出')}\n```")

    return "\n\n".join(md)


def main(results_file_path: str, reports_output_dir: str):
    if not os.path.exists(results_file_path):
        print(f"错误: 找不到结果文件 '{results_file_path}'")
        return

    with open(results_file_path, 'r', encoding='utf-8') as f:
        all_results = json.load(f)

    os.makedirs(reports_output_dir, exist_ok=True)
    console = Console(record=True, width=120)

    for i, result in enumerate(all_results):
        console.rule(f"[bold cyan]正在生成报告 {i+1}/{len(all_results)}[/bold cyan]", style="cyan")
        
        markdown_content = generate_single_report_markdown(result)
        
        console.print(Markdown(markdown_content))
        
        # 为了避免文件名冲突，可以从原始结果文件名中提取模式信息
        base_name = os.path.splitext(os.path.basename(results_file_path))[0]
        report_id = result.get('id', f'q_{i}')
        
        md_filename = os.path.join(reports_output_dir, f"{base_name}_{report_id}.md")
        with open(md_filename, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        console.print(f"\n[green]报告已保存:[/green]")
        console.print(f"  - Markdown: [underline]{md_filename}[/underline]")

    print(f"所有 {len(all_results)} 份报告已生成完毕，存放于 '{reports_output_dir}' 目录。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="为解题系统的JSON输出结果生成美化的Markdown和HTML报告。")
    parser.add_argument(
        "--results_file", 
        type=str, 
        help="输入的JSON结果文件路径。"
    )
    parser.add_argument(
        "--output_dir", 
        type=str, 
        default="reports/", 
        help="报告输出的目录。(默认: 'reports/')"
    )
    args = parser.parse_args()
    
    main(results_file_path=args.results_file, reports_output_dir=args.output_dir)