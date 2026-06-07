"""ReadFileTool — agents read file content from the workspace.

Replicates Claude Code's Read tool patterns:
- Line numbers (cat -n format) so agent knows exact strings for edit_file
- offset/limit for large files
- Max chars truncation to prevent context overflow
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core_new.agent_runtime.base import Tool

_MAX_CHARS = 30000


class ReadFileTool(Tool):
    """Agent reads a file from the slot workspace.

    Returns content with line numbers (cat -n format).
    """

    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace).resolve()

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "读取指定文件的内容并返回（带行号）。"
            "path 参数为相对文件名，offset 为起始行号（从1开始），limit 为最大行数。"
            "适合在 edit_file 之前查看文件当前状态和精确行号。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件名（如 question.md, solve.py）",
                },
                "offset": {
                    "type": "integer",
                    "description": "起始行号（从1开始，默认为1）",
                },
                "limit": {
                    "type": "integer",
                    "description": "最大返回行数（默认读取全部）",
                },
            },
            "required": ["path"],
        }

    async def execute(
        self, path: str = "", offset: int | None = None, limit: int | None = None
    ) -> str:
        if not path:
            return json.dumps(
                {"ok": False, "error": "path is required"},
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

        if not target.exists():
            return json.dumps(
                {"ok": False, "error": f"file not found: {path}"},
                ensure_ascii=False,
            )

        raw = target.read_text(encoding="utf-8")
        lines = raw.splitlines(keepends=True)
        total_lines = len(lines)

        # Apply offset/limit
        start = max(1, offset or 1) - 1  # 0-indexed
        end = start + limit if limit else total_lines
        sliced = lines[start:end]

        # Format with line numbers (cat -n style)
        numbered = []
        for i, line in enumerate(sliced, start=start + 1):
            stripped = line.rstrip("\n")
            numbered.append(f"{i:>4}\t{stripped}")

        content = "\n".join(numbered)

        # Truncate if too long
        truncated = False
        if len(content) > _MAX_CHARS:
            content = content[:_MAX_CHARS]
            truncated = True

        rel = str(target.relative_to(self.workspace))
        result = {"ok": True, "path": rel, "total_lines": total_lines}
        if offset:
            result["offset"] = offset
        if truncated:
            result["truncated"] = True
            result["hint"] = "文件过长，使用 offset/limit 参数读取更多内容"

        result["content"] = content
        return json.dumps(result, ensure_ascii=False)

    def _resolve(self, path: str) -> Path:
        clean = path.lstrip("/").lstrip("\\")
        return (self.workspace / clean).resolve()
