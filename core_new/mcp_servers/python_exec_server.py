"""MCP Server: Python code execution with safety checks and resource limits.

Starts as a subprocess, communicates via stdio (MCP protocol).
All agents share this single execution service.

Usage:
    python -m core_new.mcp_servers.python_exec_server
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Safety ──────────────────────────────────────────────────────

FORBIDDEN_IMPORTS = frozenset({
    "socket", "requests", "http", "urllib",
    "ftplib", "smtplib", "telnetlib", "xmlrpc",
    "multiprocessing", "threading", "subprocess",
    "ctypes", "shutil", "signal", "os", "sys",
    "pathlib", "io", "tempfile", "glob",
    "builtins", "importlib", "runpy",
})

FORBIDDEN_CALLS = frozenset({
    "open", "exec", "eval", "compile", "__import__", "input", "breakpoint",
    "getattr", "setattr", "delattr",
})

DEFAULT_TIMEOUT = int(os.getenv("PYTHON_EXEC_TIMEOUT", "10"))
DEFAULT_MAX_OUTPUT = int(os.getenv("PYTHON_EXEC_MAX_OUTPUT", "10000"))
MEMORY_LIMIT_MB = int(os.getenv("PYTHON_EXEC_MEMORY_MB", "512"))


def _check_safety(code: str) -> str | None:
    """AST-based safety check. Returns error message or None."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_mod = alias.name.split(".")[0]
                if root_mod in FORBIDDEN_IMPORTS:
                    return f"Forbidden import: {root_mod}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_mod = node.module.split(".")[0]
                if root_mod in FORBIDDEN_IMPORTS:
                    return f"Forbidden import from: {root_mod}"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                return f"Forbidden call: {node.func.id}"
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                return f"Forbidden dunder attribute access: {node.attr}"
    return None


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _safe_builtins_script() -> str:
    """Build snippet that creates a restricted builtins dict."""
    return (
        "_bltins = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)\n"
        "_safe_builtins = {k: v for k, v in _bltins.items()\n"
        "                  if k not in {'open', 'exec', 'eval', 'compile',\n"
        "                               'input', 'breakpoint', 'globals', 'locals'}}\n"
    )


def _execute_subprocess(
    code: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_output: int = DEFAULT_MAX_OUTPUT,
    memory_mb: int = MEMORY_LIMIT_MB,
) -> dict[str, Any]:
    """Execute code in a subprocess with resource limits and isolated globals."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8",
    ) as f:
        f.write(code)
        f.flush()
        tmp_path = f.name

    try:
        # Wrapper that sets memory limit, then exec's user code in a
        # restricted namespace so it cannot reach wrapper-local symbols
        # like sys/resource to escape the sandbox.
        wrapper = (
            "import sys as _w_sys\n"
            "_w_path = _w_sys.argv[1]\n"
            "try:\n"
            "    import resource as _w_res\n"
            f"    _w_res.setrlimit(_w_res.RLIMIT_AS, "
            f"({memory_mb * 1024 * 1024}, {memory_mb * 1024 * 1024}))\n"
            "except Exception:\n"
            "    _w_res = None\n"
            "with open(_w_path, encoding='utf-8') as _w_f:\n"
            "    _w_code = _w_f.read()\n"
            + _safe_builtins_script() +
            "del _w_sys, _w_res, _w_f, _bltins, _w_path\n"
            "exec(compile(_w_code, '<user>', 'exec'), {'__builtins__': _safe_builtins})\n"
        )

        proc = subprocess.run(
            [sys.executable, "-c", wrapper, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[:max_output],
            "stderr": proc.stderr[:max_output],
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout}s",
            "timed_out": True,
        }
    except Exception as e:
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "timed_out": False,
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ── MCP Server ──────────────────────────────────────────────────

server = Server("python-exec")

_PYTHON_EXEC_TOOL = Tool(
    name="python_exec",
    description=(
        "Execute Python code in a sandboxed subprocess. "
        "Returns structured JSON: {ok, exit_code, stdout, stderr, timed_out}. "
        "Network, file I/O, and system calls are blocked. "
        "Only standard math/science libraries (math, struct, itertools, etc.) are allowed."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python source code to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default 10, max 60).",
                "default": DEFAULT_TIMEOUT,
            },
            "max_output": {
                "type": "integer",
                "description": "Maximum stdout/stderr characters to return.",
                "default": DEFAULT_MAX_OUTPUT,
            },
        },
        "required": ["code"],
    },
)


@server.list_tools()
async def list_tools():
    return [_PYTHON_EXEC_TOOL]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name != "python_exec":
        return [TextContent(type="text", text=json.dumps({"ok": False, "error": f"Unknown tool: {name}"}))]

    code = arguments.get("code", "")
    timeout = _bounded_int(arguments.get("timeout", DEFAULT_TIMEOUT), DEFAULT_TIMEOUT, 1, 60)
    max_output = _bounded_int(
        arguments.get("max_output", DEFAULT_MAX_OUTPUT),
        DEFAULT_MAX_OUTPUT,
        1000,
        50000,
    )

    if not code.strip():
        return [TextContent(type="text", text=json.dumps({
            "ok": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": "No code provided",
            "timed_out": False,
            "error": "No code provided",
        }))]

    # Safety check
    safety_error = _check_safety(code)
    if safety_error:
        msg = f"Safety: {safety_error}"
        return [TextContent(type="text", text=json.dumps({
            "ok": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": msg,
            "timed_out": False,
            "error": msg,
        }, ensure_ascii=False))]

    # Execute
    result = _execute_subprocess(code, timeout=timeout, max_output=max_output)
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
