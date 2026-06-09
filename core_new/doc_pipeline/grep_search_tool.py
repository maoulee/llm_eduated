"""GrepSearchTool — search question experience files by knowledge point keywords.

Wraps compose/knowledge_index.py:search_questions() so the scheduler's agent
can discover relevant experience files without raw grep.
"""

from __future__ import annotations

import json
from typing import Any

from core_new.agent_runtime.base import Tool
from compose.knowledge_index import search_questions


class GrepSearchTool(Tool):
    """Search question experience files by knowledge point keywords."""

    @property
    def name(self) -> str:
        return "grep_search"

    @property
    def description(self) -> str:
        return (
            "按知识点关键词搜索题目经验文件。"
            "query 为关键词（字符串或数组），返回匹配文件列表及分数。"
            "可按科目 subject 过滤。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                    "description": "知识点关键词，支持单个字符串或字符串数组",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回条数（默认 30）",
                },
                "subject": {
                    "type": "string",
                    "description": "按科目过滤（如 '数据结构'）",
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str | list[str] | None = None,
        max_results: int = 30,
        subject: str | None = None,
        **_kwargs: Any,
    ) -> str:
        if not query:
            return json.dumps(
                {"ok": False, "error": "query is required"},
                ensure_ascii=False,
            )

        # Normalize: ensure list form for multi-keyword handling
        if isinstance(query, str):
            query = [query]

        hits = search_questions(
            query=query,
            max_results=max_results,
            subject=subject,
        )

        results = [
            {
                "file": h.file_name,
                "score": h.score,
                "snippet": h.snippet[:200] if h.snippet else "",
                "matched_tags": h.matched_tags,
            }
            for h in hits
        ]

        return json.dumps(
            {"ok": True, "count": len(results), "results": results},
            ensure_ascii=False,
        )
