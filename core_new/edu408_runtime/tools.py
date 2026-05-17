"""408 business tools for the DeepTutor-style runtime adapter."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

from core_new.agent_runtime import Tool, ToolRegistry
from core_new.llm_gateway import LLMGateway
from core_new.tool_executor import execute_python


REPO_ROOT = Path(__file__).resolve().parents[2]
SOLUTIONS_DIR = REPO_ROOT / "tmp" / "solutions"
DEFAULT_WORKSPACE = Path(__file__).resolve().parent / "workspace"


def build_408_tools(
    gateway: LLMGateway | None = None,
    *,
    workspace: str | Path = DEFAULT_WORKSPACE,
    include_llm_tools: bool = True,
) -> ToolRegistry:
    """Build the allowed 408 tool registry.

    The registry intentionally avoids DeepTutor's generic shell/web tools.
    """
    registry = ToolRegistry()
    registry.register(CodeExec408Tool())
    registry.register(CheckQuestion408Tool())
    registry.register(SearchKnowledge408Tool())
    registry.register(ReadWorkspaceFileTool(workspace))
    if include_llm_tools:
        registry.register(GenerateQuestion408Tool(gateway))
        registry.register(ComposePaper408Tool(gateway))
    return registry


class CodeExec408Tool(Tool):
    """Execute 408 Python verification code through a single controlled tool."""

    @property
    def name(self) -> str:
        return "code_exec_408"

    @property
    def description(self) -> str:
        return (
            "Execute Python code for 408 calculations. Use sandbox mode for inline "
            "CodeAct checks and subprocess mode for persisted solver scripts."
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
                "timeout": {"type": "number", "default": 5.0, "minimum": 0.1, "maximum": 60},
                "max_stdout": {"type": "integer", "default": 5000, "minimum": 200, "maximum": 20000},
                "execution_mode": {
                    "type": "string",
                    "enum": ["sandbox", "subprocess"],
                    "default": "sandbox",
                },
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
        timeout: float = 5.0,
        max_stdout: int = 5000,
        execution_mode: str = "sandbox",
        persist: bool = False,
    ) -> str:
        if file_path:
            script_path = _resolve_solution_path(file_path)
            if not script_path.exists():
                return _json({"ok": False, "error": f"File not found: {file_path}"})
            code_text = script_path.read_text(encoding="utf-8", errors="ignore")
            safety_error = _check_subprocess_safety(code_text)
            if safety_error:
                return _json({"ok": False, "error": safety_error, "mode": "subprocess"})
            return await _run_subprocess(script_path, timeout=timeout, max_stdout=max_stdout)

        if not code.strip():
            return _json({"ok": False, "error": "No code provided."})

        if execution_mode == "sandbox" and not persist:
            result = execute_python(code, timeout=timeout, max_stdout=max_stdout)
            return _json(
                {
                    "ok": result.ok,
                    "mode": "sandbox",
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "timed_out": result.timed_out,
                }
            )

        safety_error = _check_subprocess_safety(code)
        if safety_error:
            return _json({"ok": False, "error": safety_error, "mode": "subprocess"})

        script_path = _save_script(slot_id=slot_id, step=step, code=code)
        return await _run_subprocess(
            script_path,
            timeout=timeout,
            max_stdout=max_stdout,
            extra={"file_path": str(script_path.relative_to(REPO_ROOT))},
        )


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


class GenerateQuestion408Tool(Tool):
    """Wrap existing question-generation pipelines as a runtime tool."""

    def __init__(self, gateway: LLMGateway | None):
        self.gateway = gateway

    @property
    def name(self) -> str:
        return "generate_question_408"

    @property
    def description(self) -> str:
        return "Generate one 408 question from a SlotBlueprint using the existing deterministic pipeline."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "slot_blueprint": {"type": "object"},
                "experience_card": {"type": "string"},
                "question_type": {
                    "type": "string",
                    "enum": ["auto", "single_choice", "comprehensive"],
                    "default": "auto",
                },
            },
            "required": ["slot_blueprint"],
        }

    async def execute(
        self,
        slot_blueprint: dict[str, Any],
        experience_card: str = "",
        question_type: str = "auto",
    ) -> str:
        if self.gateway is None:
            return "Error: generate_question_408 requires a configured LLMGateway."

        qtype = _infer_question_type(slot_blueprint, question_type)
        if qtype == "single_choice":
            from core_new.agents.single_choice_team import SingleChoicePipeline

            result = await SingleChoicePipeline(self.gateway).run(
                slot_blueprint=slot_blueprint,
                experience_card=experience_card,
                gateway=self.gateway,
            )
            return _json({"ok": True, "question_type": qtype, "question": result})

        from core_new.agents.hybrid_subjective_team import HybridSubjectivePipeline

        result = await HybridSubjectivePipeline().run(
            slot_blueprint=slot_blueprint,
            experience_card=experience_card,
            gateway=self.gateway,
        )
        return _json(
            {
                "ok": True,
                "question_type": qtype,
                "question": result.final_question,
                "review": result.review,
            }
        )


class ComposePaper408Tool(Tool):
    """Wrap existing paper composition as a runtime tool."""

    def __init__(self, gateway: LLMGateway | None):
        self.gateway = gateway

    @property
    def name(self) -> str:
        return "compose_paper_408"

    @property
    def description(self) -> str:
        return "Compose a 408 PaperBlueprint from slot templates and teacher requirements."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "teacher_request": {"type": "string"},
                "slot_templates": {"type": "object"},
                "total_slots": {"type": "integer", "minimum": 1, "default": 0},
            },
            "required": ["teacher_request", "slot_templates"],
        }

    async def execute(
        self,
        teacher_request: str,
        slot_templates: dict[str, Any],
        total_slots: int = 0,
    ) -> str:
        if self.gateway is None:
            return "Error: compose_paper_408 requires a configured LLMGateway."

        from core_new.agents.slot_agents import PaperComposerAgent
        from core_new.blackboard import Blackboard
        from core_new.skeleton_checker import check_blueprint_skeleton

        bb = Blackboard(
            task_id=f"compose_{int(time.time())}",
            task_type="compose_paper_408",
            initial_state={
                "slot_templates": slot_templates,
                "user_requirements": teacher_request,
                "total_slots": total_slots or len(slot_templates),
            },
        )
        record = await PaperComposerAgent(self.gateway).execute(bb)
        if record.error:
            return _json({"ok": False, "error": record.error})

        blueprint = bb.get("paper_blueprint", {})
        violations = check_blueprint_skeleton(blueprint) if isinstance(blueprint, dict) else []
        return _json({"ok": not violations, "paper_blueprint": blueprint, "violations": violations})


_SUBPROCESS_FORBIDDEN_IMPORTS = {
    "socket", "requests", "http", "urllib",
    "ftplib", "smtplib", "telnetlib",
}


def _check_subprocess_safety(code: str) -> str | None:
    """Lightweight AST check for subprocess mode — block network imports."""
    import ast as _ast
    try:
        tree = _ast.parse(code)
    except SyntaxError:
        return None  # let subprocess report the syntax error
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _SUBPROCESS_FORBIDDEN_IMPORTS:
                    return f"Forbidden import in subprocess mode: {alias.name}"
        if isinstance(node, _ast.ImportFrom):
            if node.module and node.module.split(".")[0] in _SUBPROCESS_FORBIDDEN_IMPORTS:
                return f"Forbidden import in subprocess mode: {node.module}"
    return None


def _save_script(slot_id: str, step: int, code: str) -> Path:
    safe_slot = re.sub(r"[^A-Za-z0-9_.-]+", "_", slot_id or "Q")
    dir_path = SOLUTIONS_DIR / safe_slot
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / f"step{step}.py"
    path.write_text(code, encoding="utf-8")
    return path


async def _run_subprocess(
    script_path: Path,
    *,
    timeout: float,
    max_stdout: int,
    extra: dict[str, Any] | None = None,
) -> str:
    abs_path = script_path.resolve()
    if not _is_relative_to(abs_path, SOLUTIONS_DIR.resolve()):
        return _json({"ok": False, "error": f"Script path escapes solutions dir: {script_path}"})

    def _run() -> dict[str, Any]:
        try:
            proc = subprocess.run(
                [sys.executable, str(abs_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(abs_path.parent),
            )
            return {
                "ok": proc.returncode == 0,
                "mode": "subprocess",
                "exit_code": proc.returncode,
                "stdout": proc.stdout[:max_stdout],
                "stderr": proc.stderr[:max_stdout],
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "mode": "subprocess",
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Timeout after {timeout}s",
                "timed_out": True,
            }
        except Exception as exc:
            return {
                "ok": False,
                "mode": "subprocess",
                "exit_code": -1,
                "stdout": "",
                "stderr": str(exc),
                "timed_out": False,
            }

    result = await asyncio.to_thread(_run)
    if extra:
        result.update(extra)
    return _json(result)


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
