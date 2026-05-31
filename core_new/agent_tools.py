"""Agent tool definitions and executor for function-calling support.

Each agent can register tools (file reading, search, etc.) that the LLM
can invoke during generation. The executor handles dispatching tool calls
and returning results.

OpenAI-compatible tool schema:
  tools = [{"type": "function", "function": {"name", "description", "parameters"}}]
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolDef:
    """Definition of a callable tool for LLM function-calling."""

    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema
    handler: Callable[..., str] = field(repr=False)

    def to_openai_tool(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolExecutor:
    """Dispatches tool calls and returns results."""

    def __init__(self, tools: List[ToolDef]):
        self._tools: Dict[str, ToolDef] = {t.name: t for t in tools}

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        return [t.to_openai_tool() for t in self._tools.values()]

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        tool = self._tools.get(tool_name)
        if not tool:
            return json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
        try:
            if asyncio.iscoroutinefunction(tool.handler):
                return await tool.handler(**arguments)
            return tool.handler(**arguments)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)


# ── Built-in tool implementations ─────────────────────────────


async def _python_exec(code: str, timeout: int = 10) -> str:
    """Execute Python code and return stdout/stderr."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace")
        if stderr:
            output += f"\nSTDERR: {stderr.decode('utf-8', errors='replace')}"
        return output or "(no output)"
    except asyncio.TimeoutError:
        return f"Error: execution timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"


def _read_file(file_path: str, encoding: str = "utf-8") -> str:
    """Read a file and return its content."""
    if not os.path.exists(file_path):
        return json.dumps({"error": f"File not found: {file_path}"}, ensure_ascii=False)
    with open(file_path, "r", encoding=encoding) as f:
        content = f.read()
    # Limit to 20K chars to avoid blowing context
    if len(content) > 20000:
        content = content[:20000] + "\n... (truncated)"
    return content


def _read_slot_section(slot_id: str, section: str = "") -> str:
    """Read a slot file, optionally extracting a specific section.

    Supports both ## and ### headings. Returns content from the
    matched heading until the next heading of the same or higher level.
    """
    path = os.path.join("data", "slots", f"{slot_id}_slot.md")
    content = _read_file(path)
    if content.startswith('{"error"'):
        return content
    if not section:
        return content
    lines = content.split("\n")
    capturing = False
    match_level = 0
    result = []
    for line in lines:
        # Detect heading level
        if line.startswith("### "):
            heading_level = 3
        elif line.startswith("## "):
            heading_level = 2
        elif line.startswith("# "):
            heading_level = 1
        else:
            heading_level = 0

        if not capturing and heading_level > 0 and section in line:
            capturing = True
            match_level = heading_level
            continue
        if capturing:
            # Stop at same or higher level heading
            if heading_level > 0 and heading_level <= match_level:
                break
            result.append(line)
    extracted = "\n".join(result).strip()
    if not extracted:
        return json.dumps({"error": f"Section '{section}' not found in {slot_id}"}, ensure_ascii=False)
    return extracted


def _list_directory(dir_path: str, pattern: str = "") -> str:
    """List files in a directory, optionally filtered by pattern."""
    if not os.path.isdir(dir_path):
        return json.dumps({"error": f"Directory not found: {dir_path}"}, ensure_ascii=False)
    entries = os.listdir(dir_path)
    if pattern:
        entries = [e for e in entries if pattern in e]
    return json.dumps(sorted(entries), ensure_ascii=False)


# ── Pre-built tool sets ────────────────────────────────────────

SLOT_TOOLS: List[ToolDef] = [
    ToolDef(
        name="read_slot",
        description="读取题位Slot文件。不传section返回完整文件，传section只返回对应章节（如'考察理念'、'难度维度'、'往年案例'、'设计理念'）。",
        parameters={
            "type": "object",
            "properties": {
                "slot_id": {"type": "string", "description": "题位ID，如Q44"},
                "section": {"type": "string", "description": "章节名（可选），如'考察理念'"},
            },
            "required": ["slot_id"],
        },
        handler=_read_slot_section,
    ),
    ToolDef(
        name="read_file",
        description="读取指定路径的文件内容。",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件路径"},
            },
            "required": ["file_path"],
        },
        handler=_read_file,
    ),
    ToolDef(
        name="list_files",
        description="列出目录下的文件。",
        parameters={
            "type": "object",
            "properties": {
                "dir_path": {"type": "string", "description": "目录路径"},
                "pattern": {"type": "string", "description": "文件名过滤（可选）"},
            },
            "required": ["dir_path"],
        },
        handler=_list_directory,
    ),
]

SOLVER_TOOLS: List[ToolDef] = SLOT_TOOLS + [
    ToolDef(
        name="python_exec",
        description="执行Python代码验证计算。仅用于数学验证，不要执行文件操作。",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "要执行的Python代码"},
                "timeout": {"type": "integer", "description": "超时秒数，默认10"},
            },
            "required": ["code"],
        },
        handler=_python_exec,
    ),
]
