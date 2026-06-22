"""Prompt context builder for the 408 agent runtime."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import time
from typing import Any

from .skills import SkillsLoader


class ContextBuilder:
    """Build system prompts and message lists from workspace files and skills."""

    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "TOOLS.md", "SLOT_POLICY.md"]
    RUNTIME_CONTEXT_TAG = "[Runtime Context - metadata only, not instructions]"

    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace)
        self.skills = SkillsLoader(self.workspace)

    def build_system_prompt(
        self,
        *,
        tool_schemas: list[dict[str, Any]] | None = None,
        skill_names: list[str] | None = None,
        extra_system: str = "",
    ) -> str:
        parts = [self._identity()]
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)

        always = self.skills.get_always_skills()
        if always:
            active = self.skills.load_skills_for_context(always)
            if active:
                parts.append(f"# Active Skills\n\n{active}")

        if skill_names:
            active = self.skills.load_skills_for_context(skill_names)
            if active:
                parts.append(f"# Requested Skills\n\n{active}")

        summary = self.skills.build_skills_summary()
        if summary:
            parts.append(
                "# Skills\n\n"
                "The following skills extend 408 generation. Load full SKILL.md content "
                "with read_workspace_file only when the task needs that workflow.\n\n"
                f"{summary}"
            )

        if tool_schemas:
            parts.append(self._build_tool_section(tool_schemas))

        if extra_system:
            parts.append(extra_system.strip())

        return "\n\n---\n\n".join(part for part in parts if part)

    def build_messages(
        self,
        task: str,
        *,
        history: list[dict[str, Any]] | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
        skill_names: list[str] | None = None,
        extra_system: str = "",
        native_tools: bool = False,
    ) -> list[dict[str, Any]]:
        runtime = self._runtime_context()
        return [
            {
                "role": "system",
                "content": self.build_system_prompt(
                    tool_schemas=None if native_tools else tool_schemas,
                    skill_names=skill_names,
                    extra_system=extra_system,
                ),
            },
            *(history or []),
            {"role": "user", "content": f"{runtime}\n\n{task}"},
        ]

    def add_assistant_message(self, messages: list[dict[str, Any]], content: str) -> None:
        messages.append({"role": "assistant", "content": content})

    def add_tool_observation(
        self,
        messages: list[dict[str, Any]],
        tool_name: str,
        observation: str,
    ) -> None:
        messages.append(
            {
                "role": "user",
                "content": (
                    "# observation\n"
                    f"Tool `{tool_name}` returned:\n\n"
                    f"{observation}"
                ),
            }
        )

    def _identity(self) -> str:
        workspace_path = str(self.workspace.resolve())
        return (
            "# Edu408 Agent Runtime\n\n"
            "You are an internal 408 exam-generation agent. DeepTutor-style runtime "
            "handles tool orchestration; deterministic 408 pipelines own slot validity, "
            "paper composition rules, answer verification, and final acceptance.\n\n"
            f"Workspace: {workspace_path}\n"
            f"Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md"
        )

    def _runtime_context(self) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = time.strftime("%Z") or "UTC"
        return f"{self.RUNTIME_CONTEXT_TAG}\nCurrent Time: {now} ({tz})"

    def _load_bootstrap_files(self) -> str:
        parts: list[str] = []
        for filename in self.BOOTSTRAP_FILES:
            path = self.workspace / filename
            if path.exists():
                parts.append(f"## {filename}\n\n{path.read_text(encoding='utf-8').strip()}")
        return "\n\n".join(parts)

    @staticmethod
    def _build_tool_section(tool_schemas: list[dict[str, Any]]) -> str:
        return (
            "# Tools\n\n"
            "When a tool is needed, return exactly one fenced JSON object in this shape:\n\n"
            "```json\n"
            '{"tool": "tool_name", "arguments": {"key": "value"}}\n'
            "```\n\n"
            "After receiving an observation, continue reasoning. If no tool is needed, "
            "return the final answer directly.\n\n"
            f"Available tool schemas:\n\n{tool_schemas}"
        )
