"""Subject code translation."""
import re

CHAPTER_MAP = {
    "CN-1": "计算机网络-1",
    "CN-2": "计算机网络-2",
    "CN-3": "计算机网络-3",
    "CN-4": "计算机网络-4",
    "CN-5": "计算机网络-5",
    "CN-6": "计算机网络-6",
    "CO-1": "组成原理-1",
    "CO-2": "组成原理-2",
    "CO-3": "组成原理-3",
    "CO-4": "组成原理-4",
    "CO-5": "组成原理-5",
    "CO-6": "组成原理-6",
    "CO-7": "组成原理-7",
    "DS-1": "数据结构-1",
    "DS-2": "数据结构-2",
    "DS-3": "数据结构-3",
    "DS-4": "数据结构-4",
    "DS-5": "数据结构-5",
    "DS-6": "数据结构-6",
    "DS-7": "数据结构-7",
    "DS-8": "数据结构-8",
    "OS-1": "操作系统-1",
    "OS-2": "操作系统-2",
    "OS-3": "操作系统-3",
    "OS-4": "操作系统-4",
    "OS-5": "操作系统-5",
}

SUBJECT_MAP = {"DS": "数据结构", "CO": "计算机组成原理", "OS": "操作系统", "CN": "计算机网络"}


def translate_code(text: str) -> str:
    """Replace abbreviated codes like DS-1 with full names like 数据结构-1 绪论."""
    def _repl(m):
        code = m.group(0)
        return CHAPTER_MAP.get(code, code)
    return re.sub(r"\b(DS|CO|OS|CN)-(\d+)\b", _repl, text)
