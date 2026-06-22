"""ExecPythonTool — agents execute Python code and get stdout/stderr back."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from core_new.agent_runtime.base import Tool


class ExecPythonTool(Tool):
    """Execute a Python script and return stdout + stderr.

    The agent passes complete source code; the tool writes it to a temp file,
    runs it, and returns structured JSON with stdout, stderr, and exit_code.
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "exec_python"

    @property
    def description(self) -> str:
        return (
            "执行 Python 代码并返回输出。"
            "code 参数为完整可执行的 Python 代码。"
            "返回 JSON 包含 stdout、stderr、exit_code。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "完整可执行的 Python 代码",
                },
            },
            "required": ["code"],
        }

    async def execute(self, code: str = "") -> str:
        if not code.strip():
            return json.dumps(
                {"ok": False, "error": "code is required"},
                ensure_ascii=False,
            )

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8",
            ) as f:
                f.write(code)
                tmp_path = f.name

            proc = subprocess.run(
                ["python3", tmp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                encoding="utf-8",
                errors="replace",
            )

            return json.dumps(
                {
                    "ok": proc.returncode == 0,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout or "",
                    "stderr": proc.stderr or "",
                },
                ensure_ascii=False,
            )
        except subprocess.TimeoutExpired:
            return json.dumps(
                {"ok": False, "exit_code": -1, "stdout": "", "stderr": "Timeout"},
                ensure_ascii=False,
            )
        except Exception as exc:
            return json.dumps(
                {"ok": False, "exit_code": -1, "stdout": "", "stderr": str(exc)},
                ensure_ascii=False,
            )
        finally:
            try:
                Path(tmp_path).unlink()
            except Exception:
                pass
