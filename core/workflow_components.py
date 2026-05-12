# core/workflow_components.py

import re
from typing import List, Dict, Tuple
from collections import Counter

def extract_key_values_from_output(output_str: str) -> Tuple:
    """
    从代码的标准输出中提取关键值用于比较。
    优先提取 'key: value' 格式，其次是 boxed 内容，最后是所有数字。
    """
    if not output_str:
        return tuple()
    
    # 优先匹配 key: value 格式
    key_value_pairs = re.findall(r'(\w+):\s*(-?\d+\.?\d*)', output_str)
    if key_value_pairs:
        # 按key排序，确保比较顺序一致
        return tuple(sorted(key_value_pairs))
        
    # 其次匹配 \boxed{}
    boxed_values = re.findall(r'\\boxed\{(.*?)\}', output_str)
    if boxed_values:
        return tuple(sorted(boxed_values))
    
    # 最后匹配所有数字
    numbers = re.findall(r'[-+]?\d*\.\d+|\d+', output_str)
    return tuple(sorted([float(n) for n in numbers]))


def find_majority_result(execution_results: List[Dict]):
    """
    对执行结果进行投票，找到多数派。
    返回: (多数派结果字典, 多数派票数)，如果不存在则返回 (None, 0)
    """
    successful_results = [res for res in execution_results if res['error'] is None and res['output']]
    if not successful_results:
        return None, 0

    key_values_list = [extract_key_values_from_output(res['output']) for res in successful_results]
    
    # 过滤掉没有提取到关键值的结果
    valid_votes = [kv for kv in key_values_list if kv]
    if not valid_votes:
        return None, 0
        
    vote_counts = Counter(valid_votes)
    most_common = vote_counts.most_common(1)[0]
    majority_key_value, majority_count = most_common
    
    # 检查是否构成严格多数派 (超过一半)
    if majority_count > len(valid_votes) / 2:
        for i, kv in enumerate(key_values_list):
            if kv == majority_key_value:
                return successful_results[i], majority_count
    
    return None, 0

def format_divergent_codes_for_reflection(divergent_results: List[Dict]) -> str:
    """格式化有分歧的代码及其输出，用于反思Prompt。"""
    analysis_str = ""
    for i, item in enumerate(divergent_results):
        analysis_str += f"[代码版本 {i+1}]\n"
        analysis_str += "```python\n"
        analysis_str += item.get('code', 'N/A') + "\n"
        analysis_str += "```\n"
        analysis_str += f"[运行输出 {i+1}]\n"
        analysis_str += item.get('output', 'N/A') + "\n"
        if item.get('error'):
            analysis_str += f"[错误信息 {i+1}]\n"
            analysis_str += item['error'] + "\n"
        analysis_str += "---\n"
    return analysis_str