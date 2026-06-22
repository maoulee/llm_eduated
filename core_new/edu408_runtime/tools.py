"""408 business tools for the DeepTutor-style runtime adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any

from core_new.agent_runtime import Tool, ToolRegistry


REPO_ROOT = Path(__file__).resolve().parents[2]
SOLUTIONS_DIR = REPO_ROOT / "tmp" / "solutions"
DEFAULT_WORKSPACE = Path(__file__).resolve().parent / "workspace"


def build_408_tools(
    *,
    workspace: str | Path = DEFAULT_WORKSPACE,
) -> ToolRegistry:
    """Build the allowed 408 tool registry."""
    registry = ToolRegistry()
    registry.register(CodeExec408Tool())
    registry.register(CheckQuestion408Tool())
    registry.register(SearchKnowledge408Tool())
    registry.register(ReadWorkspaceFileTool(workspace))
    return registry


class CodeExec408Tool(Tool):
    """Execute 408 Python verification code through MCP sandbox."""

    @property
    def name(self) -> str:
        return "python_exec"

    @property
    def description(self) -> str:
        return (
            "执行Python代码进行数学计算和验证。常规调用仅传 code；"
            "需要审计落盘时可传 persist/slot_id/step，重跑脚本时传 file_path。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source code to execute."},
                "file_path": {
                    "type": "string",
                    "description": "Existing script path to re-run. Must be under tmp/solutions.",
                },
                "slot_id": {"type": "string", "default": "Q"},
                "step": {"type": "integer", "default": 1, "minimum": 1},
                "timeout": {"type": "number", "default": 10, "minimum": 1, "maximum": 60},
                "max_stdout": {"type": "integer", "default": 5000, "minimum": 1000, "maximum": 50000},
                "persist": {
                    "type": "boolean",
                    "default": False,
                    "description": "When true, save code to tmp/solutions/<slot_id>/stepN.py.",
                },
            },
        }

    async def execute(
        self,
        code: str = "",
        file_path: str = "",
        slot_id: str = "Q",
        step: int = 1,
        timeout: float = 10,
        max_stdout: int = 5000,
        persist: bool = False,
    ) -> str:
        extra: dict[str, Any] = {}

        if file_path:
            try:
                script_path = _resolve_solution_path(file_path)
            except ValueError as exc:
                return _json({"ok": False, "error": str(exc), "mode": "mcp"})
            if not script_path.exists():
                return _json({"ok": False, "error": f"File not found: {file_path}", "mode": "mcp"})
            code = script_path.read_text(encoding="utf-8", errors="ignore")
            extra["file_path"] = str(script_path.relative_to(REPO_ROOT))

        if not code.strip():
            return _json({"ok": False, "error": "No code provided."})

        if persist and not file_path:
            script_path = _save_script(slot_id=slot_id, step=step, code=code)
            extra["file_path"] = str(script_path.relative_to(REPO_ROOT))

        try:
            from core_new.mcp_servers.client import mcp_python_exec

            result = await mcp_python_exec(
                code,
                timeout=int(timeout),
                max_output=int(max_stdout),
            )
            payload = {
                "ok": result.get("ok", False),
                "mode": "mcp",
                "exit_code": result.get("exit_code", -1),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "timed_out": result.get("timed_out", False),
            }
            payload.update(extra)
            return _json(payload)
        except Exception as e:
            return _json({"ok": False, "error": str(e), "mode": "mcp"})


class CheckQuestion408Tool(Tool):
    """Run deterministic 408 structure checks."""

    @property
    def name(self) -> str:
        return "check_question_408"

    @property
    def description(self) -> str:
        return "Check paper blueprints or generated questions for required 408 structural fields."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "blueprint": {"type": "object"},
                "question": {"type": "object"},
                "question_type": {
                    "type": "string",
                    "enum": ["auto", "single_choice", "comprehensive"],
                    "default": "auto",
                },
                "slot_blueprint": {"type": "object"},
            },
        }

    async def execute(
        self,
        blueprint: dict[str, Any] | None = None,
        question: dict[str, Any] | None = None,
        question_type: str = "auto",
        slot_blueprint: dict[str, Any] | None = None,
    ) -> str:
        violations: list[dict[str, str]] = []

        if blueprint:
            from core_new.skeleton_checker import check_blueprint_skeleton

            violations.extend(check_blueprint_skeleton(blueprint))

        if question:
            violations.extend(_check_question_fields(question, question_type, slot_blueprint or {}))

        return _json(
            {
                "ok": not violations,
                "violation_count": len(violations),
                "violations": violations,
            }
        )


class SearchKnowledge408Tool(Tool):
    """Lightweight local knowledge search until the real KB is connected."""

    SEARCH_DIRS = (
        REPO_ROOT / "data" / "slot_experiences",
        REPO_ROOT / "docs" / "extractions",
        REPO_ROOT / "kcard",
    )

    @property
    def name(self) -> str:
        return "search_knowledge_408"

    @property
    def description(self) -> str:
        return "Search local 408 slot experience cards, extracted questions, and k-card prompts."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
        }

    async def execute(self, query: str, limit: int = 5) -> str:
        terms = [t.lower() for t in re.split(r"\s+", query.strip()) if t]
        hits: list[dict[str, Any]] = []
        for base in self.SEARCH_DIRS:
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if path.suffix.lower() not in {".md", ".txt", ".py", ".json"} or not path.is_file():
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                lowered = text.lower()
                score = sum(lowered.count(term) for term in terms)
                if score <= 0:
                    continue
                snippet = _snippet(text, terms)
                hits.append(
                    {
                        "path": str(path.relative_to(REPO_ROOT)),
                        "score": score,
                        "snippet": snippet,
                    }
                )
        hits.sort(key=lambda item: item["score"], reverse=True)
        return _json({"query": query, "hits": hits[:limit]})


class ReadWorkspaceFileTool(Tool):
    """Read a file under the 408 runtime workspace."""

    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace).resolve()

    @property
    def name(self) -> str:
        return "read_workspace_file"

    @property
    def description(self) -> str:
        return "Read AGENTS.md, TOOLS.md, SLOT_POLICY.md, or SKILL.md files under the 408 workspace."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path relative to the 408 workspace, e.g. skills/solve-408/SKILL.md.",
                }
            },
            "required": ["path"],
        }

    async def execute(self, path: str) -> str:
        target = (self.workspace / path).resolve()
        if not _is_relative_to(target, self.workspace):
            return f"Error: path escapes workspace: {path}"
        if not target.exists() or not target.is_file():
            return f"Error: file not found: {path}"
        return target.read_text(encoding="utf-8")


def _save_script(slot_id: str, step: int, code: str) -> Path:
    safe_slot = re.sub(r"[^A-Za-z0-9_.-]+", "_", slot_id or "Q")
    dir_path = SOLUTIONS_DIR / safe_slot
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / f"step{step}.py"
    path.write_text(code, encoding="utf-8")
    return path


def _resolve_solution_path(file_path: str) -> Path:
    path = Path(file_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    resolved = path.resolve()
    solutions = SOLUTIONS_DIR.resolve()
    if not _is_relative_to(resolved, solutions):
        raise ValueError(f"script must be under {solutions}")
    return resolved


def _check_question_fields(
    question: dict[str, Any],
    question_type: str,
    slot_blueprint: dict[str, Any],
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    slot_id = str(question.get("slot_id") or slot_blueprint.get("slot_id") or "QUESTION")
    qtype = _infer_question_type(slot_blueprint or question, question_type)

    def require(field: str) -> None:
        if not question.get(field):
            violations.append(
                {
                    "slot_id": slot_id,
                    "rule": f"missing_{field}",
                    "detail": f"question must include non-empty `{field}`",
                }
            )

    require("stem")
    if qtype == "single_choice":
        for field in ("option_A", "option_B", "option_C", "option_D"):
            require(field)
        if not question.get("correct_answer") and not question.get("answer"):
            violations.append(
                {
                    "slot_id": slot_id,
                    "rule": "missing_correct_answer",
                    "detail": "single-choice question must include correct_answer or answer",
                }
            )
    else:
        if not question.get("sub_questions"):
            violations.append(
                {
                    "slot_id": slot_id,
                    "rule": "missing_sub_questions",
                    "detail": "comprehensive question must include sub_questions",
                }
            )
        if not question.get("answer") and not question.get("correct_answer"):
            violations.append(
                {
                    "slot_id": slot_id,
                    "rule": "missing_answer",
                    "detail": "comprehensive question must include answer or correct_answer",
                }
            )

    return violations


def _infer_question_type(slot_blueprint: dict[str, Any], explicit: str = "auto") -> str:
    if explicit in {"single_choice", "comprehensive"}:
        return explicit
    if slot_blueprint.get("option_style") == "none":
        return "comprehensive"
    if slot_blueprint.get("sub_questions") is not None and slot_blueprint.get("answer_format"):
        return "comprehensive"
    return "single_choice"


def _snippet(text: str, terms: list[str], radius: int = 120) -> str:
    lowered = text.lower()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    if not positions:
        return text[: radius * 2]
    pos = min(positions)
    start = max(0, pos - radius)
    end = min(len(text), pos + radius)
    return text[start:end].replace("\n", " ")


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)
