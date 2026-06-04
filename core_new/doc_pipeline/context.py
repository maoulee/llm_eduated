"""Plugin-style context injection registry for the doc pipeline.

ContextProvider protocol + FileProvider/InlineProvider implementations +
ContextRegistry that resolves per-role bindings at runtime.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass
class ProviderDef:
    """Declarative definition of a context provider, loaded from YAML."""
    name: str
    type: str                    # "file" | "inline"
    label: str                   # Chinese label for prompt injection (e.g. "蓝图")
    phases: list[int] = field(default_factory=list)
    optional: bool = False
    path_pattern: str = ""       # for type=file: e.g. "{workspace}/{slot_id}/blueprint.md"


@dataclass
class ResolvedContext:
    """Result of resolving a provider for a specific pipeline run."""
    label: str
    content: str
    source_name: str
    skipped: bool = False


@runtime_checkable
class ContextProvider(Protocol):
    """Protocol for a context injection source."""

    @property
    def name(self) -> str: ...

    async def resolve(
        self,
        workspace: Path,
        slot_id: str,
        phase: int,
        runtime_args: dict[str, Any] | None = None,
    ) -> ResolvedContext: ...


class FileProvider:
    """Resolves to a file path from workspace (for inject_files consumption)."""

    def __init__(self, defn: ProviderDef) -> None:
        self._defn = defn

    @property
    def name(self) -> str:
        return self._defn.name

    async def resolve(
        self,
        workspace: Path,
        slot_id: str,
        phase: int,
        runtime_args: dict[str, Any] | None = None,
    ) -> ResolvedContext:
        if self._defn.phases and phase not in self._defn.phases:
            return ResolvedContext(
                label=self._defn.label,
                content="",
                source_name=self._defn.name,
                skipped=True,
            )
        path = Path(
            self._defn.path_pattern.format(
                workspace=str(workspace), slot_id=slot_id,
            )
        )
        if not path.exists():
            return ResolvedContext(
                label=self._defn.label,
                content="",
                source_name=self._defn.name,
                skipped=self._defn.optional,
            )
        return ResolvedContext(
            label=self._defn.label,
            content=str(path),
            source_name=self._defn.name,
        )


class InlineProvider:
    """Returns content from runtime_args (e.g. experience_doc, k_definitions)."""

    def __init__(self, defn: ProviderDef) -> None:
        self._defn = defn

    @property
    def name(self) -> str:
        return self._defn.name

    async def resolve(
        self,
        workspace: Path,
        slot_id: str,
        phase: int,
        runtime_args: dict[str, Any] | None = None,
    ) -> ResolvedContext:
        if self._defn.phases and phase not in self._defn.phases:
            return ResolvedContext(
                label=self._defn.label,
                content="",
                source_name=self._defn.name,
                skipped=True,
            )
        args = runtime_args or {}
        content = str(args.get(self._defn.name, ""))
        return ResolvedContext(
            label=self._defn.label,
            content=content,
            source_name=self._defn.name,
            skipped=(not content and self._defn.optional),
        )


class ContextRegistry:
    """Registry of named ContextProviders with per-role binding resolution."""

    def __init__(self) -> None:
        self._providers: dict[str, ContextProvider] = {}
        self._role_bindings: dict[str, list[str]] = {}

    def register(self, provider: ContextProvider) -> None:
        self._providers[provider.name] = provider

    def set_role_binding(self, role: str, provider_names: list[str]) -> None:
        self._role_bindings[role] = list(provider_names)

    def get_provider(self, name: str) -> ContextProvider | None:
        return self._providers.get(name)

    @property
    def provider_names(self) -> list[str]:
        return list(self._providers.keys())

    @property
    def bound_roles(self) -> list[str]:
        return list(self._role_bindings.keys())

    async def resolve_for_role(
        self,
        role: str,
        workspace: Path,
        slot_id: str,
        phase: int,
        runtime_args: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Resolve all context for a role. Returns {label: content} for non-skipped providers."""
        provider_names = self._role_bindings.get(role, [])
        result: dict[str, str] = {}
        for pname in provider_names:
            provider = self._providers.get(pname)
            if provider is None:
                logger.warning("Unknown context provider '%s' for role '%s'", pname, role)
                continue
            ctx = await provider.resolve(workspace, slot_id, phase, runtime_args)
            if ctx.skipped or not ctx.content:
                continue
            result[ctx.label] = ctx.content
        return result

    def __repr__(self) -> str:
        return (
            f"ContextRegistry(providers={self.provider_names}, "
            f"roles={self.bound_roles})"
        )
