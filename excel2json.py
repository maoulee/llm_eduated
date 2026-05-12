# excel_to_json.py (可配置版本)

import pandas as pd
import json
import os
import argparse

def convert_excel_to_json(excel_path: str, json_path: str, prompt_col: str, answer_col: str = None, sheet_name=0):
    """
    读取Excel文件，并将其转换为符合系统输入格式的JSON文件。
    
    Args:
        excel_path (str): 输入的Excel文件路径。
        json_path (str): 输出的JSON文件路径。
        prompt_col (str): 问题所在的列名。
        answer_col (str, optional): 答案所在的列名。如果为None，则答案字段为"N/A"。
        sheet_name (str or int, optional): 要读取的Excel工作表名或索引。默认为0 (第一个表)。
    """
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
    except FileNotFoundError:
        print(f"错误：找不到Excel文件 '{excel_path}'。")
        return
    except ValueError as e:
        print(f"错误：读取工作表 '{sheet_name}' 失败。请检查名称是否正确。错误信息: {e}")
        return

    # 验证必要的列是否存在
    if prompt_col not in df.columns:
        print(f"错误：Excel文件中缺少名为 '{prompt_col}' 的列。请检查表头或您的参数。")
        return
    if answer_col and answer_col not in df.columns:
        print(f"警告：指定了答案列 '{answer_col}'，但在Excel中未找到。所有答案将被设为 'N/A'。")
        answer_col = None # 将其重置为None，走无答案逻辑

    questions_list = []
    for index, row in df.iterrows():
        prompt_text = row[prompt_col]
        
        # 处理prompt为空的情况
        if pd.isna(prompt_text) or not str(prompt_text).strip():
            print(f"警告：第 {index + 2} 行的prompt为空，已跳过。")
            continue
            
        # 处理答案
        answer_text = "N/A"
        if answer_col:
            # 如果答案列存在，并且单元格不为空，则使用其内容
            if pd.notna(row[answer_col]):
                answer_text = str(row[answer_col]).strip()

        question_obj = {
            "id": f"eval_{index}",
            "prompt": str(prompt_text).strip(),
            "answer": answer_text
        }
        questions_list.append(question_obj)

    # 创建输出目录
    os.makedirs(os.path.dirname(json_path), exist_ok=True)

    # 写入JSON文件
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(questions_list, f, ensure_ascii=False, indent=2)

    print(f"成功！已将 {len(questions_list)} 个问题从 '{excel_path}' (Sheet: {sheet_name}) 转换并保存到 '{json_path}'。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="将Excel文件转换为用于模型评估的JSON格式。")
    
    parser.add_argument("excel_file", type=str, help="输入的Excel文件路径。")
    parser.add_argument("json_file", type=str, help="输出的JSON文件路径。")
    
    parser.add_argument(
        "--prompt_col", 
        type=str, 
        default="prompt", 
        help="问题所在的列名 (默认为 'prompt')。"
    )
    
    parser.add_argument(
        "--answer_col", 
        type=str, 
        default=None, 
        help="答案所在的列名 (默认为不读取答案)。"
    )

    parser.add_argument(
        "--sheet_name",
        type=str,
        default="0", # argparse会将0解析为字符串'0'，我们需要处理
        help="要读取的工作表名称或索引 (默认为第一个表)。"
    )

    args = parser.parse_args()
    print(1)

    # argparse读取的sheet_name是字符串，需要尝试转为整数
    sheet = args.sheet_name
    if sheet.isdigit():
        sheet = int(sheet)

    convert_excel_to_json(
        excel_path=args.excel_file,
        json_path=args.json_file,
        prompt_col=args.prompt_col,
        answer_col=args.answer_col,
        sheet_name=sheet
    )