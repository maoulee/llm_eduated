"""Tool registry for DeepTutor-style agent execution."""

from __future__ import annotations

from typing import Any

from .base import Tool


class ToolRegistry:
    """Register and execute named tools with schema validation."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def get_definitions(self, allowed_tools: list[str] | None = None) -> list[dict[str, Any]]:
        if not allowed_tools:
            tools = self._tools.values()
        else:
            allowed = set(allowed_tools)
            tools = [tool for name, tool in self._tools.items() if name in allowed]
        return [tool.to_schema() for tool in tools]

    async def execute(self, name: str, params: dict[str, Any] | None = None) -> str:
        hint = "\n\n[Analyze the error above and try a different approach.]"
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found. Available: {', '.join(self.tool_names)}"

        params = params or {}
        try:
            casted = tool.cast_params(params)
            errors = tool.validate_params(casted)
            if errors:
                return f"Error: Invalid parameters for tool '{name}': " + "; ".join(errors) + hint
            result = await tool.execute(**casted)
            if isinstance(result, str) and result.startswith("Error"):
                return result + hint
            return result
        except Exception as exc:
            return f"Error executing {name}: {exc}" + hint

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
