"""EditFileTool — agents make targeted string replacements in files.

Replicates Claude Code's Edit tool patterns:
- Exact string match with uniqueness requirement
- replace_all option for batch replacements (e.g. renaming)
- Error messages include line numbers for debugging
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core_new.agent_runtime.base import Tool


class EditFileTool(Tool):
    """Agent edits a file by replacing old_string with new_string.

    Safer and more efficient than rewriting entire files via write_file.
    """

    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace).resolve()

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return (
            "对文件进行局部修改：将指定旧文本替换为新文本。"
            "old_string 必须与文件中的文本完全匹配且唯一（除非 replace_all=true）。"
            "适合小幅修改，避免整体重写文件。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件名（如 fixed.md, solve.py）",
                },
                "old_string": {
                    "type": "string",
                    "description": "要被替换的精确文本（必须与文件中的文本完全匹配）",
                },
                "new_string": {
                    "type": "string",
                    "description": "替换后的新文本",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "设为 true 则替换所有匹配项（适合批量重命名）",
                },
            },
            "required": ["path", "old_string", "new_string"],
        }

    async def execute(
        self,
        path: str = "",
        old_string: str = "",
        new_string: str = "",
        replace_all: bool = False,
    ) -> str:
        if not path:
            return json.dumps(
                {"ok": False, "error": "path is required"},
                ensure_ascii=False,
            )
        if not old_string:
            return json.dumps(
                {"ok": False, "error": "old_string is required"},
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

        content = target.read_text(encoding="utf-8")
        count = content.count(old_string)

        if count == 0:
            return json.dumps(
                {
                    "ok": False,
                    "error": "old_string not found in file",
                    "path": path,
                },
                ensure_ascii=False,
            )

        if count > 1 and not replace_all:
            line_numbers = self._find_line_numbers(content, old_string)
            return json.dumps(
                {
                    "ok": False,
                    "error": (
                        f"old_string found {count} times at lines {line_numbers}. "
                        "Either include more context to make it unique, "
                        "or set replace_all=true to replace all occurrences."
                    ),
                    "path": path,
                    "match_count": count,
                    "match_lines": line_numbers,
                },
                ensure_ascii=False,
            )

        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        target.write_text(new_content, encoding="utf-8")

        rel = str(target.relative_to(self.workspace))
        return json.dumps(
            {"ok": True, "path": rel, "replaced": count},
            ensure_ascii=False,
        )

    @staticmethod
    def _find_line_numbers(content: str, substring: str) -> list[int]:
        """Find all line numbers where substring occurs."""
        lines = content.splitlines()
        line_numbers = []
        # Combine lines with newlines to search across line boundaries
        # But also search line by line for simpler matches
        for i, line in enumerate(lines, start=1):
            if substring in line:
                line_numbers.append(i)
        if not line_numbers and "\n" in substring:
            # Multi-line match: search in full content
            pos = 0
            while True:
                idx = content.find(substring, pos)
                if idx == -1:
                    break
                line_num = content[:idx].count("\n") + 1
                line_numbers.append(line_num)
                pos = idx + 1
        return line_numbers[:10]  # Cap at 10 to keep message short

    def _resolve(self, path: str) -> Path:
        clean = path.lstrip("/").lstrip("\\")
        return (self.workspace / clean).resolve()
