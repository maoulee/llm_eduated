"""ExecFileTool — agents execute a Python file already written in the workspace."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from core_new.agent_runtime.base import Tool


class ExecFileTool(Tool):
    """Execute a Python file in the workspace and return stdout + stderr.

    The agent must first write the file via write_file, then call exec_file
    with the same path.  This enforces the "write before execute" discipline
    and ensures every execution is traceable to a persisted file.
    """

    def __init__(self, workspace: str | Path, timeout: int = 30):
        self.workspace = Path(workspace).resolve()
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "exec_file"

    @property
    def description(self) -> str:
        return (
            "执行工作目录中已存在的 Python 文件并返回输出。"
            "path 参数为工作目录中的相对路径。"
            "文件必须先通过 write_file 写入。"
            "返回 JSON 包含 stdout、stderr、exit_code。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "工作目录中的 .py 文件路径（相对路径）",
                },
            },
            "required": ["path"],
        }

    def _resolve(self, path: str) -> Path:
        """Resolve *path* relative to workspace and verify it stays inside."""
        resolved = (self.workspace / path).resolve()
        resolved.relative_to(self.workspace)  # raises ValueError if escape
        return resolved

    async def execute(self, path: str = "") -> str:
        if not path.strip():
            return json.dumps(
                {"ok": False, "error": "path is required"},
                ensure_ascii=False,
            )

        try:
            resolved = self._resolve(path)
        except ValueError:
            return json.dumps(
                {"ok": False, "error": f"path escapes workspace: {path}"},
                ensure_ascii=False,
            )

        if not resolved.exists():
            return json.dumps(
                {"ok": False, "error": f"file not found: {path}. Write it first via write_file."},
                ensure_ascii=False,
            )

        if not resolved.suffix == ".py":
            return json.dumps(
                {"ok": False, "error": f"only .py files can be executed, got: {resolved.suffix}"},
                ensure_ascii=False,
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                "python3", str(resolved),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return json.dumps(
                    {"ok": False, "exit_code": -1, "stdout": "", "stderr": "Timeout"},
                    ensure_ascii=False,
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            return json.dumps(
                {
                    "ok": proc.returncode == 0,
                    "exit_code": proc.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                },
                ensure_ascii=False,
            )
        except Exception as exc:
            return json.dumps(
                {"ok": False, "exit_code": -1, "stdout": "", "stderr": str(exc)},
                ensure_ascii=False,
            )
