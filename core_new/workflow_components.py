# core_new/workflow_components.py

"""
包含特定于求解工作流的组件函数。
例如，用于结果投票、格式化Prompt输入的函数。
"""

import re
from typing import List, Dict, Tuple, Optional
from collections import Counter


def extract_key_values_from_output(output_str: str) -> Tuple:
    """
    从代码的标准输出中提取关键值用于比较。
    这是一个稳定的比较策略，按优先级提取：
    1. 'key: value' 或 'key = value' 格式。
    2. \boxed{...} LaTeX 格式。
    3. 所有数字。
    """
    if not isinstance(output_str, str) or not output_str.strip():
        return tuple()
    
    # 策略1: 匹配 key: value 或 key = value 格式
    # 匹配更灵活，允许等号和冒号，以及周围的空格
    key_value_pairs = re.findall(r'([\w\s]+?)\s*[:=]\s*(-?\d+\.?\d*)', output_str)
    if key_value_pairs:
        # 清理key中的空白并按key排序，确保比较顺序一致
        cleaned_pairs = [(key.strip(), float(value)) for key, value in key_value_pairs]
        return tuple(sorted(cleaned_pairs))
        
    # 策略2: 匹配 \boxed{}
    boxed_values = re.findall(r'\\boxed\{(.*?)\}', output_str)
    if boxed_values:
        # 对找到的所有 boxed 内容排序
        return tuple(sorted(boxed_values))
    
    # 策略3: 匹配所有数字
    numbers = re.findall(r'[-+]?\d*\.\d+|\d+', output_str)
    if numbers:
        # 将所有数字转换为浮点数并排序
        return tuple(sorted([float(n) for n in numbers]))
    
    # 如果都找不到，返回空元组
    return tuple()


def find_majority_result(execution_results: List[Dict]) -> Tuple[Optional[Dict], int]:
    """
    对代码执行结果进行投票，找到严格多数派（票数 > 总票数 / 2）。

    Args:
        execution_results: 一系列代码执行结果的字典列表。

    Returns:
        一个元组 (多数派结果字典, 多数派票数)。如果不存在多数派，则返回 (None, 0)。
    """
    successful_results = [
        res for res in execution_results if res.get('error') is None and res.get('output')
    ]
    if not successful_results:
        return None, 0

    # 提取每个成功结果的关键值用于投票
    key_values_list = [extract_key_values_from_output(res['output']) for res in successful_results]
    
    # 过滤掉那些虽然成功执行但没有提取到可比较关键值的结果
    valid_votes = [kv for kv in key_values_list if kv]
    if not valid_votes:
        return None, 0
        
    # 计票
    vote_counts = Counter(valid_votes)
    
    # 如果没有投票，直接返回
    if not vote_counts:
        return None, 0

    most_common = vote_counts.most_common(1)[0]
    majority_key_value, majority_count = most_common
    
    # 检查是否构成严格多数派 (超过一半)
    if majority_count > len(valid_votes) / 2:
        # 找到第一个匹配多数派关键值的结果并返回
        for i, res in enumerate(successful_results):
            if extract_key_values_from_output(res['output']) == majority_key_value:
                return res, majority_count
    
    # 如果没有严格多数派
    return None, 0


def format_divergent_codes_for_reflection(divergent_results: List[Dict]) -> str:
    """
    格式化有分歧的代码及其输出，用于反思Prompt。
    这将生成一个清晰的、供LLM分析的文本块。
    """
    analysis_str = ""
    for i, item in enumerate(divergent_results):
        analysis_str += f"--- [代码版本 {i+1}] ---\n"
        analysis_str += "```python\n"
        analysis_str += item.get('code', '# 代码未提供') + "\n"
        analysis_str += "```\n"
        analysis_str += f"[运行输出 {i+1}]\n"
        analysis_str += item.get('output', '# 无输出').strip() + "\n"
        
        if item.get('error'):
            analysis_str += f"[错误信息 {i+1}]\n"
            analysis_str += item['error'].strip() + "\n"
            
    return analysis_str.strip()