# core_new/utils.py

"""
通用辅助函数模块。
存放与业务逻辑解耦的、可被多处复用的工具函数，如文本解析、代码执行等。
"""
import json
import re
import subprocess
from typing import Dict, Optional


def parse_code(text: str) -> str:
    """
    从LLM返回的文本中，健壮地提取Python代码。
    按以下优先级顺序查找：
    1. <execute_code>...</execute_code>
    2. ```python...```
    3. ```...```
    """
    if not isinstance(text, str):
        return ""
    try:
        # 优先级1: <execute_code> 标签
        outer_match = re.search(r'<execute_code>(.*?)</execute_code>', text, re.DOTALL)
        if outer_match:
            return outer_match.group(1).strip()
        
        # 优先级2: ```python 标签
        inner_match = re.search(r'```python\n(.*?)\n```', text, re.DOTALL)
        if inner_match:
            return inner_match.group(1).strip()

        # 优先级3: 通用 ``` 标签
        fallback_match = re.search(r'```(.*?)```', text, re.DOTALL)
        if fallback_match:
            code = fallback_match.group(1).strip()
            # 移除可选的 'python' 前缀
            if code.lower().startswith('python'):
                code = re.sub(r'^[pP][yY][tT][hH][oO][nN]\s*', '', code, count=1)
            return code
        
        # 如果都找不到，则认为整个文本可能是代码（容错）
        return text.strip()
    except Exception:
        # 发生任何异常都返回空字符串，保证函数健壮性
        return ""


def execute_code(code: str, context: str = "") -> Dict:
    """
    在沙箱环境中执行Python代码字符串。

    Args:
        code (str): 要执行的Python代码。
        context (str): 在执行代码前注入的上下文代码（例如，历史变量定义）。

    Returns:
        一个包含 'code', 'output', 'error' 的字典。
    """
    full_code = context.strip() + "\n" + code.strip()
    if not code.strip():
        return {'code': code, 'output': None, 'error': 'Generated code was empty.'}

    try:
        # 使用 subprocess.run 创建一个隔离的Python进程来执行代码
        process = subprocess.run(
            ['python', '-c', full_code],
            capture_output=True,
            text=True,
            timeout=20,  # 设置20秒超时，防止无限循环
            check=False  # 不检查返回码，手动处理stderr
        )
        
        return {
            'code': code,
            'output': process.stdout,
            'error': process.stderr if process.returncode != 0 else None
        }
    except subprocess.TimeoutExpired:
        return {'code': code, 'output': None, 'error': 'Code execution timed out after 20 seconds.'}
    except Exception as e:
        return {'code': code, 'output': None, 'error': f"An unexpected error occurred during execution: {e}"}


def parse_json_from_llm_output(text: str) -> Optional[Dict]:
    """
    从LLM可能返回的、带有格式标记的文本中健壮地提取JSON对象。

    Args:
        text (str): LLM的原始输出文本。

    Returns:
        解析出的字典，如果失败则返回 None。
    """
    if not isinstance(text, str):
        return None
        
    try:
        # 策略1: 寻找被 ```json ... ``` 包裹的内容
        match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            return json.loads(json_str)

        # 策略2: 寻找第一个 '{' 和最后一个 '}' 之间的内容 (最常见)
        start_index = text.find('{')
        end_index = text.rfind('}')
        if start_index != -1 and end_index != -1 and end_index > start_index:
            json_str = text[start_index : end_index + 1]
            return json.loads(json_str)

        # 策略3: 尝试直接解析整个文本 (如果LLM返回了纯净JSON)
        return json.loads(text)

    except (json.JSONDecodeError, AttributeError):
        # 如果所有策略都失败，安全地返回 None
        return None