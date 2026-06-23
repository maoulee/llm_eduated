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

    def __init__(self, tools: List[Any]):
        self._tools: Dict[str, Any] = {t.name: t for t in tools}

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        return [t.to_openai_tool() for t in self._tools.values()]

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    async def execute(self, tool_name: str, arguments: Dict[str, Any] | None) -> str:
        tool = self._tools.get(tool_name)
        if not tool:
            return json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)
        arguments = arguments or {}
        try:
            # Runtime Tool objects provide schema-aware cast/validation helpers.
            if hasattr(tool, "cast_params") and hasattr(tool, "validate_params"):
                arguments = tool.cast_params(arguments)
                errors = tool.validate_params(arguments)
                if errors:
                    return json.dumps(
                        {"ok": False, "error": "; ".join(errors)},
                        ensure_ascii=False,
                    )

            # ToolDef objects have .handler; runtime Tool objects have .execute().
            handler = getattr(tool, "handler", None)
            if handler is not None:
                result = handler(**arguments)
            else:
                execute = getattr(tool, "execute", None)
                if execute is None:
                    return json.dumps(
                        {"ok": False, "error": f"Tool {tool_name} has no callable handler"},
                        ensure_ascii=False,
                    )
                result = execute(**arguments)

            if asyncio.iscoroutine(result):
                result = await result
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)


# ── Built-in tool implementations ─────────────────────────────


async def _python_exec(code: str, timeout: int = 10) -> str:
    """Execute Python code via MCP server (shared, sandboxed)."""
    try:
        from core_new.mcp_servers.client import mcp_python_exec
        result = await mcp_python_exec(code, timeout=timeout)
        if result.get("ok"):
            output = result.get("stdout", "")
            stderr = result.get("stderr", "")
            if stderr:
                output += f"\nSTDERR: {stderr}"
            return output or "(no output)"
        else:
            error = result.get("stderr", "") or result.get("error", "unknown error")
            if result.get("timed_out"):
                return f"Error: execution timed out after {timeout}s"
            return f"Error: {error}"
    except Exception as e:
        return f"Error: {e}"


async def _gpt_delegate(action: str, content: str, **kwargs) -> str:
    """Delegate task to GPT via WebGPT gateway with full design context."""
    import logging as _log
    _logger = _log.getLogger("gpt_delegate")
    from core_new.webgpt_client import get_webgpt_client
    client = get_webgpt_client()
    if client is None:
        _logger.warning("WebGPT not configured")
        return json.dumps({"ok": False, "error": "WebGPT not configured"}, ensure_ascii=False)
    try:
        agent_name = _context_store.get("__agent_name__", "unknown")
        slot_id = _context_store.get("__slot_id__", "")
        base_prompt = _context_store.get("__system_prompt__", "")

        # Build enriched system prompt with design context
        parts = [base_prompt] if base_prompt else []
        blueprint = _context_store.get("__blueprint__", "")
        experience = _context_store.get("__experience__", "")
        design_ctx = _context_store.get("__design_context__", "")

        if blueprint:
            parts.append("\n\n## 当前题位蓝图\n" + blueprint)
        if experience:
            parts.append("\n\n## 往年经验与范式\n" + experience)
        if design_ctx and design_ctx != "{}":
            parts.append("\n\n## 设计上下文\n" + design_ctx)

        enriched_prompt = "\n".join(parts)

        _logger.info("[%s:%s] Calling GPT (action=%s, content_len=%d, prompt_len=%d)",
                     agent_name, slot_id, action, len(content), len(enriched_prompt))
        result = await client.delegate(
            agent_name=agent_name,
            slot_id=slot_id,
            system_prompt=enriched_prompt,
            content=content,
        )
        _logger.info("[%s:%s] GPT response len=%d", agent_name, slot_id, len(result))
        return json.dumps({"ok": True, "response": result}, ensure_ascii=False)
    except Exception as e:
        _logger.error("[%s] GPT delegate failed: %s", agent_name, e)
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


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


# ── Context pull tools ──────────────────────────────────────────

# 全局上下文存储，由 BaseAgent.execute() 在调用前设置
_context_store: dict[str, Any] = {}


def set_context_store(store: dict[str, Any]) -> None:
    """Set the global context store (called by BaseAgent.execute)."""
    global _context_store
    _context_store = store


def _list_context() -> str:
    """列出当前可用的上下文信息源目录。"""
    if not _context_store:
        return json.dumps({"info": "当前无可用上下文信息"}, ensure_ascii=False)
    catalog = {}
    for key, (desc, _) in _context_store.get("__catalog__", {}).items():
        catalog[key] = desc
    return json.dumps(catalog, ensure_ascii=False, indent=2)


def _read_context(key: str) -> str:
    """读取指定上下文信息源的详细内容。"""
    if key.startswith("__"):
        return json.dumps({"error": f"信息源 '{key}' 不存在"}, ensure_ascii=False)
    if not _context_store or key not in _context_store:
        available = list(_context_store.get("__catalog__", {}).keys()) if _context_store else []
        return json.dumps({"error": f"信息源 '{key}' 不存在", "available": available}, ensure_ascii=False)
    content = _context_store.get(key)
    if content is None:
        return json.dumps({"error": f"信息源 '{key}' 内容为空"}, ensure_ascii=False)
    if isinstance(content, (dict, list)):
        return json.dumps(content, ensure_ascii=False, indent=2)[:8000]
    return str(content)[:8000]


CONTEXT_TOOLS: List[ToolDef] = [
    ToolDef(
        name="list_context",
        description="列出当前可用的上下文信息源目录（名称+简要描述）。先调用此工具了解有哪些信息，再调用 read_context 获取具体内容。",
        parameters={
            "type": "object",
            "properties": {},
        },
        handler=_list_context,
    ),
    ToolDef(
        name="read_context",
        description="读取指定上下文信息源的详细内容。参数 key 为信息源名称（如 design、solver_result、review 等）。",
        parameters={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "信息源名称，如 design、solver_result、review 等"},
            },
            "required": ["key"],
        },
        handler=_read_context,
    ),
]


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

# ── python_exec tool (MCP-backed, shared by all agents) ─────────

PYTHON_EXEC_TOOL = ToolDef(
    name="python_exec",
    description="执行Python代码进行数学计算和验证。所有数值计算必须通过此工具完成，禁止手动推导。仅使用标准库: math, decimal, fractions, itertools, collections, struct, random。禁止导入 numpy、pandas、scipy 等第三方库，会导致超时。",
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "要执行的Python代码"},
            "timeout": {"type": "integer", "description": "超时秒数，默认10"},
        },
        "required": ["code"],
    },
    handler=_python_exec,
)

GPT_DELEGATE_TOOL = ToolDef(
    name="gpt_delegate",
    description=(
        "将任务委托给更强的 GPT 模型处理，获取专业判断结果。"
        "适用场景：\n"
        "- design: 题目设计、题干构思、参数设计、知识点选择\n"
        "- review: 题目审核、答案验证、蓝图合规检查\n"
        "- validate: 计算验证、公式检查、数值一致性校验\n"
        "- fix: 根据反馈修复题目、修正参数、改进设计\n"
        "优先在以下情况使用：(1)设计复杂综合题时委托GPT构建初始方案;"
        "(2)审核计算题答案时委托GPT验证公式和数值;"
        "(3)不确定如何处理时咨询GPT获取建议。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "需要处理的文本内容。设计任务传入蓝图要求和约束；审核任务传入题目和答案；验证任务传入计算过程和结果。",
            },
            "action": {
                "type": "string",
                "enum": ["design", "review", "validate", "fix", "check"],
                "description": "任务类型：design=设计构建, review=综合审核, validate=验证正确性, fix=修复问题, check=结构检查",
            },
        },
        "required": ["content", "action"],
    },
    handler=_gpt_delegate,
)

# ── Pre-built tool sets ────────────────────────────────────────
# NOTE: GPT_DELEGATE_TOOL is included in REVIEW_TOOLS but currently unused by agents.
# Pipeline-level GPT calls (via GptWorkflow) are the primary mechanism.
# The tool is kept for potential future use.

DESIGN_TOOLS: List[ToolDef] = []  # Designer is pure NL — no tools, no python_exec

CONTEXT_AWARE_TOOLS: List[ToolDef] = SLOT_TOOLS + CONTEXT_TOOLS

SOLVER_TOOLS: List[ToolDef] = SLOT_TOOLS + CONTEXT_TOOLS + [PYTHON_EXEC_TOOL]

REVIEW_TOOLS: List[ToolDef] = SLOT_TOOLS + CONTEXT_TOOLS + [PYTHON_EXEC_TOOL, GPT_DELEGATE_TOOL]
