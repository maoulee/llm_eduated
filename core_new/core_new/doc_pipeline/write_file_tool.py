"""WriteFileTool — agents write output to slot-specific files."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from core_new.agent_runtime.base import Tool


class WriteFileTool(Tool):
    """Agent writes output to a file under the slot workspace.

    Path safety: only files under ``self.workspace`` are writable.
    Each call overwrites the target file (idempotent).
    """

    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "将生成内容写入指定文件。每次调用会覆盖文件内容。"
            "path 参数为相对文件名（如 blueprint.md），content 为写入内容。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件名（如 blueprint.md, question.md, solve.py）",
                },
                "content": {
                    "type": "string",
                    "description": "要写入的文件内容",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str = "", content: str = "") -> str:
        if not path or not content.strip():
            return json.dumps(
                {"ok": False, "error": "path and content are required"},
                ensure_ascii=False,
            )

        target = self._resolve(path)

        # Path safety: must be under workspace
        try:
            target.relative_to(self.workspace)
        except ValueError:
            return json.dumps(
                {"ok": False, "error": f"path escapes workspace: {path}"},
                ensure_ascii=False,
            )

        # Create parent directories if needed
        target.parent.mkdir(parents=True, exist_ok=True)

        target.write_text(content, encoding="utf-8")
        size = len(content.encode("utf-8"))
        rel = str(target.relative_to(self.workspace))

        return json.dumps(
            {"ok": True, "path": rel, "size": size},
            ensure_ascii=False,
        )

    def _resolve(self, path: str) -> Path:
        """Resolve a relative path against the workspace root."""
        # Strip leading slashes to prevent absolute-path tricks
        clean = path.lstrip("/").lstrip("\\")
        return (self.workspace / clean).resolve()
