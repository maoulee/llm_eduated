"""Workspace SKILL.md loader.

This mirrors the useful part of DeepTutor's SkillsLoader: progressive skill
summary injection plus explicit full-skill loading when needed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil


class SkillsLoader:
    """Load skills from ``<workspace>/skills/<name>/SKILL.md``."""

    def __init__(self, workspace: str | Path, builtin_skills_dir: str | Path | None = None):
        self.workspace = Path(workspace)
        self.workspace_skills = self.workspace / "skills"
        self.builtin_skills = Path(builtin_skills_dir) if builtin_skills_dir else None

    def list_skills(self, filter_unavailable: bool = True) -> list[dict[str, str]]:
        skills: list[dict[str, str]] = []
        if self.workspace_skills.exists():
            for skill_dir in sorted(self.workspace_skills.iterdir()):
                skill_file = skill_dir / "SKILL.md"
                if skill_dir.is_dir() and skill_file.exists():
                    skills.append({"name": skill_dir.name, "path": str(skill_file), "source": "workspace"})

        if self.builtin_skills and self.builtin_skills.exists():
            existing = {s["name"] for s in skills}
            for skill_dir in sorted(self.builtin_skills.iterdir()):
                skill_file = skill_dir / "SKILL.md"
                if skill_dir.is_dir() and skill_file.exists() and skill_dir.name not in existing:
                    skills.append({"name": skill_dir.name, "path": str(skill_file), "source": "builtin"})

        if filter_unavailable:
            return [s for s in skills if self._check_requirements(self._get_skill_meta(s["name"]))]
        return skills

    def load_skill(self, name: str) -> str | None:
        workspace_skill = self.workspace_skills / name / "SKILL.md"
        if workspace_skill.exists():
            return workspace_skill.read_text(encoding="utf-8")
        if self.builtin_skills:
            builtin_skill = self.builtin_skills / name / "SKILL.md"
            if builtin_skill.exists():
                return builtin_skill.read_text(encoding="utf-8")
        return None

    def load_skills_for_context(self, skill_names: list[str]) -> str:
        parts: list[str] = []
        for name in skill_names:
            content = self.load_skill(name)
            if content:
                parts.append(f"### Skill: {name}\n\n{self._strip_frontmatter(content)}")
        return "\n\n---\n\n".join(parts)

    def build_skills_summary(self) -> str:
        skills = self.list_skills(filter_unavailable=False)
        if not skills:
            return ""

        lines = ["<skills>"]
        for skill in skills:
            name = self._escape_xml(skill["name"])
            desc = self._escape_xml(self._get_skill_description(skill["name"]))
            meta = self._get_skill_meta(skill["name"])
            available = self._check_requirements(meta)
            lines.append(f'  <skill available="{str(available).lower()}">')
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{desc}</description>")
            lines.append(f"    <location>{self._escape_xml(skill['path'])}</location>")
            if not available:
                missing = self._get_missing_requirements(meta)
                if missing:
                    lines.append(f"    <requires>{self._escape_xml(missing)}</requires>")
            lines.append("  </skill>")
        lines.append("</skills>")
        return "\n".join(lines)

    def get_always_skills(self) -> list[str]:
        result: list[str] = []
        for skill in self.list_skills(filter_unavailable=True):
            meta = self.get_skill_metadata(skill["name"]) or {}
            skill_meta = self._parse_metadata(meta.get("metadata", ""))
            if skill_meta.get("always") or str(meta.get("always", "")).lower() == "true":
                result.append(skill["name"])
        return result

    def get_skill_metadata(self, name: str) -> dict[str, str] | None:
        content = self.load_skill(name)
        if not content or not content.startswith("---"):
            return None
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return None
        metadata: dict[str, str] = {}
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip("\"'")
        return metadata

    def _get_skill_description(self, name: str) -> str:
        meta = self.get_skill_metadata(name)
        return meta.get("description", name) if meta else name

    def _get_skill_meta(self, name: str) -> dict:
        meta = self.get_skill_metadata(name) or {}
        return self._parse_metadata(meta.get("metadata", ""))

    def _parse_metadata(self, raw: str) -> dict:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        if not isinstance(data, dict):
            return {}
        return data.get("nanobot", data.get("openclaw", data))

    def _check_requirements(self, skill_meta: dict) -> bool:
        requires = skill_meta.get("requires", {})
        for binary in requires.get("bins", []):
            if not shutil.which(binary):
                return False
        for env in requires.get("env", []):
            if not os.environ.get(env):
                return False
        return True

    def _get_missing_requirements(self, skill_meta: dict) -> str:
        missing: list[str] = []
        requires = skill_meta.get("requires", {})
        for binary in requires.get("bins", []):
            if not shutil.which(binary):
                missing.append(f"CLI: {binary}")
        for env in requires.get("env", []):
            if not os.environ.get(env):
                missing.append(f"ENV: {env}")
        return ", ".join(missing)

    @staticmethod
    def _strip_frontmatter(content: str) -> str:
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end() :].strip()
        return content

    @staticmethod
    def _escape_xml(value: str) -> str:
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
