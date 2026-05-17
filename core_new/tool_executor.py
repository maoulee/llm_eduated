"""Sandboxed Python executor for CodeActSolver.

Executes Python code snippets with safety restrictions:
- Timeout (default 5s)
- Forbidden imports (os, subprocess, socket, etc.)
- stdout/stderr truncation
- No file system writes unless explicitly allowed
"""

from __future__ import annotations

import sys
import traceback
from io import StringIO
from typing import Dict, Optional

# Forbidden modules to prevent sandbox escapes
_FORBIDDEN_IMPORTS = {
    "os", "subprocess", "socket", "requests", "pathlib",
    "shutil", "signal", "ctypes", "multiprocessing",
    "importlib", "sys", "builtins",
}

_SAFE_BUILTIN_NAMES = {
    "abs", "all", "any", "bin", "bool", "chr", "dict", "divmod",
    "enumerate", "filter", "float", "format", "hex", "int", "isinstance",
    "len", "list", "map", "max", "min", "oct", "ord", "pow", "print",
    "range", "repr", "round", "set", "sorted", "str", "sum", "tuple",
    "type", "zip",
}


def _safe_builtins() -> Dict:
    """Build a restricted __builtins__ dict with only safe functions."""
    import builtins
    result = {}
    for name in _SAFE_BUILTIN_NAMES:
        if hasattr(builtins, name):
            result[name] = getattr(builtins, name)
    result["True"] = True
    result["False"] = False
    result["None"] = None
    return result


class ExecutionResult:
    """Result of a sandboxed Python execution."""

    def __init__(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        timed_out: bool = False,
    ):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def to_dict(self) -> Dict:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
        }


def _check_code_safety(code: str) -> Optional[str]:
    """Static check for forbidden patterns. Returns error message or None."""
    import ast
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e}"

    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod in _FORBIDDEN_IMPORTS:
                    return f"Forbidden import: {alias.name}"
        if isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".")[0]
                if mod in _FORBIDDEN_IMPORTS:
                    return f"Forbidden import from: {node.module}"
        # Check exec/eval
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in ("exec", "eval", "compile", "__import__"):
                return f"Forbidden call: {func.id}"

    return None


def execute_python(
    code: str,
    timeout: float = 5.0,
    max_stdout: int = 4096,
    extra_globals: Optional[Dict] = None,
) -> ExecutionResult:
    """Execute Python code in a restricted environment.

    Args:
        code: Python source code to execute.
        timeout: Maximum execution time in seconds.
        max_stdout: Maximum stdout/stderr length before truncation.
        extra_globals: Additional globals to inject (e.g. tools_408 functions).

    Returns:
        ExecutionResult with stdout, stderr, exit_code.
    """
    safety_error = _check_code_safety(code)
    if safety_error:
        return ExecutionResult(exit_code=1, stdout="", stderr=f"Safety check failed: {safety_error}")

    # Build restricted globals
    exec_globals: Dict = {"__builtins__": _safe_builtins()}

    # Inject math and struct
    import math
    import struct
    exec_globals["math"] = math
    exec_globals["struct"] = struct

    # Inject tools_408 helpers
    from core_new.tools_408 import (
        twos_complement_value, twos_complement_hex,
        ieee754_single_hex, ieee754_single_from_hex, ieee754_double_hex,
        cache_address_fields, cache_decompose_address, simulate_cache,
        crc_remainder, simulate_page_replacement, cpu_time,
        pipeline_performance, address_translation, booth_multiply,
    )
    exec_globals.update({
        "twos_complement_value": twos_complement_value,
        "twos_complement_hex": twos_complement_hex,
        "ieee754_single_hex": ieee754_single_hex,
        "ieee754_single_from_hex": ieee754_single_from_hex,
        "ieee754_double_hex": ieee754_double_hex,
        "cache_address_fields": cache_address_fields,
        "cache_decompose_address": cache_decompose_address,
        "simulate_cache": simulate_cache,
        "crc_remainder": crc_remainder,
        "simulate_page_replacement": simulate_page_replacement,
        "cpu_time": cpu_time,
        "pipeline_performance": pipeline_performance,
        "address_translation": address_translation,
        "booth_multiply": booth_multiply,
    })

    if extra_globals:
        exec_globals.update(extra_globals)

    stdout_buf = StringIO()
    stderr_buf = StringIO()
    exec_globals["__builtins__"]["print"] = lambda *a, **kw: print(*a, file=stdout_buf, flush=True, **kw)

    try:
        import signal
        import threading

        result_holder = [None]
        error_holder = [None]

        def _run():
            try:
                exec(code, exec_globals)
                result_holder[0] = True
            except Exception:
                error_holder[0] = traceback.format_exc()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            return ExecutionResult(
                exit_code=1, stdout="", stderr=f"Timeout after {timeout}s", timed_out=True
            )

        if error_holder[0]:
            return ExecutionResult(
                exit_code=1,
                stdout=stdout_buf.getvalue()[:max_stdout],
                stderr=error_holder[0][:max_stdout],
            )

        return ExecutionResult(
            exit_code=0,
            stdout=stdout_buf.getvalue()[:max_stdout],
            stderr="",
        )

    except Exception as e:
        return ExecutionResult(
            exit_code=1,
            stdout=stdout_buf.getvalue()[:max_stdout],
            stderr=f"Executor error: {traceback.format_exc()}"[:max_stdout],
        )
