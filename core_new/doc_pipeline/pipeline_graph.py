"""Declarative pipeline graph — signal + conditional edges.

Replaces the orchestrator's centralized if/else routing with a graph where
nodes emit signals and a declarative edge table decides the next node.
``conceptual`` / ``code-as-truth`` / back-routing loops are all expressed as
conditional edges, so no bespoke pipeline methods are needed.

A node never decides routing — it only reports a signal. The graph's
``next_node`` resolves the outgoing edge (preferring edges whose ``condition``
matches the current state, falling back to unconditional edges).

Feature-flagged: only used when ``features.enable_pipeline_graph`` is true.
Otherwise the orchestrator keeps its legacy ``_run_standard_pipeline`` /
``_run_conceptual_pipeline`` paths untouched.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from .doc_parser import REVIEW_STATUSES, get_doc_status, parse_doc_section

logger = logging.getLogger(__name__)


# ── Core data structures ─────────────────────────────────────────


@dataclass
class AgentResult:
    """What a node reports back to the graph.

    ``signal`` is the natural outcome of the node's work (pass/needs_fix/
    code_error/ok/...). The node does NOT decide routing — that is the graph's
    job via the edge table.
    """

    signal: str
    feedback: str = ""
    params: dict = field(default_factory=dict)


@dataclass
class Edge:
    from_node: str
    signal: str
    to_node: str
    condition: Callable[["PipelineState"], bool] | None = None


class PipelineNode(Protocol):
    name: str

    async def run(self, state: "PipelineState") -> AgentResult: ...


@dataclass
class PipelineState:
    """Mutable per-slot state, persisted to ``pipeline_state.json``.

    Replaces the legacy ``start_layer`` resume mechanism with a string
    ``current_node`` plus visit counters and a history log.
    """

    slot_id: str
    slot_data: dict
    workspace: Path
    complexity: str = "standard"
    code_as_truth: bool = False
    current_node: str = ""
    visit_counts: dict = field(default_factory=dict)
    history: list = field(default_factory=list)
    feedback_buffer: dict = field(default_factory=dict)
    started_at: float = field(default_factory=time.monotonic)
    result: Any = None  # PipelineResult on completion

    def __post_init__(self) -> None:
        self.complexity = self.slot_data.get("complexity", "standard")

    def record(self, node: str, result: AgentResult) -> None:
        self.current_node = node
        self.visit_counts[node] = self.visit_counts.get(node, 0) + 1
        self.history.append(
            {"node": node, "signal": result.signal, "feedback": result.feedback[:200]}
        )
        if result.feedback:
            self.feedback_buffer[node] = result.feedback
        self._checkpoint()

    def _state_path(self) -> Path:
        return self.workspace / self.slot_id / "pipeline_state.json"

    def _checkpoint(self) -> None:
        try:
            p = self._state_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                json.dumps(
                    {
                        "slot_id": self.slot_id,
                        "current_node": self.current_node,
                        "visit_counts": self.visit_counts,
                        "history": self.history,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:  # pragma: no cover - checkpoint is best-effort
            logger.warning("checkpoint failed: %s", exc)

    @classmethod
    def resume(
        cls,
        slot_id: str,
        workspace: Path,
        slot_data: dict,
        **kw: Any,
    ) -> "PipelineState | None":
        """Rebuild state from a checkpoint, or None if none exists."""
        p = workspace / slot_id / "pipeline_state.json"
        if not p.exists():
            return None
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            s = cls(
                slot_id=slot_id,
                slot_data=slot_data,
                workspace=workspace,
                **kw,
            )
            s.current_node = d.get("current_node", "")
            s.visit_counts = d.get("visit_counts", {})
            s.history = d.get("history", [])
            return s
        except Exception:
            return None


# ── Graph engine ─────────────────────────────────────────────────


class PipelineGraph:
    """Declarative graph: nodes + conditional edge table + scheduler loop."""

    MAX_NODE_VISITS = 8  # global safety net per node

    def __init__(self) -> None:
        self.nodes: dict[str, PipelineNode] = {}
        self.edges: list[Edge] = []
        self.initial = "design_card"

    def add_node(self, name: str, node: PipelineNode) -> None:
        self.nodes[name] = node

    def edge(
        self,
        from_node: str,
        signal: str,
        to_node: str,
        condition: Callable[[PipelineState], bool] | None = None,
    ) -> None:
        self.edges.append(Edge(from_node, signal, to_node, condition))

    def next_node(self, from_node: str, signal: str, state: PipelineState) -> str:
        """Resolve the outgoing edge for a (node, signal) pair.

        Prefer the first edge whose ``condition`` evaluates True; fall back to
        the first unconditional edge; default to ``done``.
        """
        fallback: str | None = None
        for e in self.edges:
            if e.from_node != from_node or e.signal != signal:
                continue
            if e.condition is None:
                fallback = e.to_node
            elif e.condition(state):
                return e.to_node
        return fallback or "done"

    async def run(self, state: PipelineState) -> PipelineState:
        """Drive the slot through the graph until reaching ``done``.

        On resume, ``current_node`` holds the *last completed* node, so we look
        up its trailing edge via the recorded signal in history.
        """
        history_signals = {h["node"]: h["signal"] for h in state.history}
        if state.current_node and state.current_node != self.initial:
            last_signal = history_signals.get(state.current_node, "")
            current = self.next_node(state.current_node, last_signal, state)
        else:
            current = state.current_node or self.initial

        while current != "done":
            if current not in self.nodes:
                raise ValueError(f"Unknown pipeline node: {current}")
            if state.visit_counts.get(current, 0) >= self.MAX_NODE_VISITS:
                logger.error(
                    "[%s] node %s exceeded max visits, forcing done",
                    state.slot_id,
                    current,
                )
                break
            node = self.nodes[current]
            logger.info(
                "[%s] graph node=%s visit=%d",
                state.slot_id,
                current,
                state.visit_counts.get(current, 0) + 1,
            )
            result = await node.run(state)
            state.record(current, result)
            current = self.next_node(current, result.signal, state)
        return state


# ── Node implementations ─────────────────────────────────────────
#
# Each node wraps an existing ``DocPipelineOrchestrator._run_*`` method. The
# node performs the work and reports a signal; it does NOT decide routing.
# Nodes hold an orchestrator reference (``self.orch``) to reuse scheduler.run_agent,
# _resolve_inject, exec_python, _format_final, etc.


class _OrchestratorNode:
    """Base node: holds the orchestrator reference."""

    name = ""

    def __init__(self, orch: Any, workspace: Path) -> None:
        self.orch = orch
        self.workspace = workspace

    async def run(self, state: PipelineState) -> AgentResult:  # pragma: no cover
        raise NotImplementedError


class DesignCardNode(_OrchestratorNode):
    name = "design_card"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        ref_path = self._ref_path(state)
        await self.orch._run_design_card(
            state.slot_id, state.slot_data, ws, ref_path, start_layer=1
        )
        return AgentResult(signal="ok")

    @staticmethod
    def _ref_path(state: PipelineState) -> Path:
        ws = state.workspace / state.slot_id
        assembled = ws / "assembled.md"
        outline = ws / "outline.md"
        return assembled if assembled.exists() else (outline if outline.exists() else ws / "blueprint.md")


class QuestionNode(_OrchestratorNode):
    """Layer 2 (Question). Single question-writing run.

    Internally branches on ``complexity`` / ``code_as_truth`` but always reports
    the same signal ``ok`` — routing is the graph's concern. Review feedback
    (when re-entered via form_gate's needs_fix edge) is threaded through the
    state's feedback_buffer.
    """

    name = "question"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        ref_path = DesignCardNode._ref_path(state)
        feedback = state.feedback_buffer.get("form_gate", "")
        fail = await self.orch._run_question_only(
            state.slot_id,
            state.slot_data,
            ws,
            ref_path,
            question_type=state.slot_data.get("question_type"),
            assembled_experience_doc=self.orch._runtime_args.get("experience_doc", ""),
            feedback=feedback,
        )
        if fail is not None:
            state.result = fail
            return AgentResult(signal="ok", feedback=f"question failed: {fail.error}")
        return AgentResult(signal="ok", feedback=feedback)


class FormGateNode(_OrchestratorNode):
    """Layer 3 (Review gate). Runs review and reports its status.

    signal: ``pass`` → proceed; ``needs_fix`` → back to question. For
    ``conceptual`` complexity a ``pass`` routes to ``done`` (graph condition).
    """

    name = "form_gate"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        ref_path = DesignCardNode._ref_path(state)
        status, fail = await self.orch._run_review_only(
            state.slot_id, state.slot_data, ws, ref_path
        )
        if fail is not None:
            state.result = fail
            return AgentResult(signal="pass", feedback=f"review failed: {fail.error}")
        review_path = ws / "review.md"
        feedback = ""
        if review_path.exists():
            # §22: review 重写后用 fix_instructions + feedback_for_agent 段
            # （旧版用 corrections + summary）。按优先级抽取。
            feedback = parse_doc_section(str(review_path), "fix_instructions")
            if not feedback.strip() or feedback.strip() == "无":
                feedback = parse_doc_section(str(review_path), "feedback_for_agent")
            if not feedback.strip() or feedback.strip() == "无":
                feedback = parse_doc_section(str(review_path), "corrections")
            if not feedback.strip() or feedback.strip() == "无":
                feedback = parse_doc_section(str(review_path), "summary")
        return AgentResult(signal=status, feedback=feedback)


class SolveNode(_OrchestratorNode):
    """Layer 4 (Solve). Runs solver + exec.

    §19.5: solver self-retries internally (context-clear + rerun) and only
    surfaces a hard failure. signal ``success`` → next; ``failed`` → terminal
    (no back-route to design; structural issues are form_gate's job).
    """

    name = "solve"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        fail, exec_result = await self.orch._run_solve(
            state.slot_id, ws, start_layer=1,
            question_type=state.slot_data.get("question_type"),
        )
        if fail is not None:
            state.result = fail
            return AgentResult(signal="failed", feedback=fail.error)
        if not exec_result.get("ok", True):
            # Defensive: _run_solve returns a fail result on exhaustion, so
            # reaching here means a soft skip (no solve.py / conceptual).
            return AgentResult(
                signal="failed",
                feedback=exec_result.get("stderr", "")[:200],
                params={"exec_result": exec_result},
            )
        return AgentResult(
            signal="success", params={"exec_result": exec_result}
        )


class FinalNode(_OrchestratorNode):
    """Layer 5 (Final Review). Reads final_review.md status.

    signal mapping: ``pass``/``expression_fix`` → ``pass``; ``question_error``
    → back to question; ``solution_error`` → back to solve.
    """

    name = "final"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        ref_path = DesignCardNode._ref_path(state)
        final_status, fail = await self.orch._run_final_review_loop(
            state.slot_id,
            state.slot_data,
            ws,
            ref_path,
            question_type=state.slot_data.get("question_type"),
            assembled_experience_doc=self.orch._runtime_args.get("experience_doc", ""),
            start_layer=1,
        )
        if fail is not None:
            state.result = fail
            return AgentResult(signal="pass", feedback=f"final failed: {fail.error}")
        # expression_fix is treated as pass per spec.
        if final_status in ("pass", "expression_fix"):
            return AgentResult(signal="pass")
        feedback = ""
        final_review_path = ws / "final_review.md"
        if final_review_path.exists():
            feedback = parse_doc_section(str(final_review_path), "routing_feedback")
        return AgentResult(signal=final_status or "pass", feedback=feedback)


# ── Graph builder ────────────────────────────────────────────────


def build_pipeline_graph(scheduler: Any, workspace: Path) -> PipelineGraph:
    """Declare the pipeline graph.

    ``conceptual`` / ``code-as-truth`` / back-routing are all expressed via
    conditional edges, so the graph auto-accommodates them without bespoke
    pipeline methods.

    Note: ``scheduler`` here is the ``DocPipelineOrchestrator`` instance (it owns
    scheduler.run_agent, _resolve_inject, exec_python, _format_final, ...).
    """
    g = PipelineGraph()
    g.add_node("design_card", DesignCardNode(scheduler, workspace))
    g.add_node("question", QuestionNode(scheduler, workspace))
    g.add_node("form_gate", FormGateNode(scheduler, workspace))
    g.add_node("solve", SolveNode(scheduler, workspace))
    g.add_node("final", FinalNode(scheduler, workspace))

    g.edge("design_card", "ok", "question")
    g.edge("question", "ok", "form_gate", condition=lambda s: s.complexity != "conceptual")
    g.edge("question", "ok", "done", condition=lambda s: s.complexity == "conceptual")
    g.edge("form_gate", "pass", "done", condition=lambda s: s.complexity == "conceptual")
    g.edge("form_gate", "pass", "solve")
    g.edge("form_gate", "needs_fix", "question")
    g.edge("solve", "success", "final")
    # §19.5: solve never back-routes; failure is terminal.
    g.edge("solve", "failed", "done")
    g.edge("final", "pass", "done")
    g.edge("final", "question_error", "question")
    g.edge("final", "solution_error", "solve")
    return g


# ── §19 split-focused design nodes + graph ──────────────────────
#
# Split path (feature-flagged via enable_split_design), §19 form:
#   design_card → exam_form → design(P1: 题干+设问+经验值参数, 大胆不验证)
#                                       → form_gate → solve(解题代码, solver writes solve.py)
#   solve success → design2(P2: 基于解设选项/答案填回) → final
#   solve failed → done (terminal; no back-route — §19.5 solver self-retry only)
#   Conceptual: design → done (skip form_gate/solve/design2/final).


class ExamFormNode(_OrchestratorNode):
    """§17.3 exam_form: KP + K-radar → examination form (narrow judgment).

    Always reports signal ``ok`` — routing is the graph's concern.
    """

    name = "exam_form"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        ref_path = DesignCardNode._ref_path(state)
        fail = await self.orch._run_exam_form(
            state.slot_id, state.slot_data, ws, ref_path
        )
        if fail is not None:
            state.result = fail
            return AgentResult(signal="ok", feedback=f"exam_form failed: {fail.error}")
        return AgentResult(signal="ok")


class DesignNode(_OrchestratorNode):
    """§19 design Pass 1: read upstream cache → reuse skeleton → stem +
    questions + experience-value params (bold-give, discipline ①). Writes
    question.md. Single run per visit; form_gate feedback threads through
    the state's feedback_buffer. Reports ``ok``.
    """

    name = "design"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        ref_path = DesignCardNode._ref_path(state)
        feedback = state.feedback_buffer.get("form_gate", "")
        fail = await self.orch._run_design_pass1(
            state.slot_id, state.slot_data, ws, ref_path, feedback=feedback,
        )
        if fail is not None:
            state.result = fail
            return AgentResult(signal="ok", feedback=f"design P1 failed: {fail.error}")
        return AgentResult(signal="ok", feedback=feedback)


class DesignFinalizeNode(_OrchestratorNode):
    """§19 design Pass 2: after solve computes the answer, finalize the
    question. Choice → design 3 distractors based on the solution (only-set,
    never-compute, verify distinct); comprehensive → fill answers back into the
    stem. Solution comes from solve; never recompute. Reports ``ok``.
    """

    name = "design2"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        fail = await self.orch._run_design_pass2(
            state.slot_id, state.slot_data, ws,
        )
        if fail is not None:
            state.result = fail
            return AgentResult(signal="ok", feedback=f"design P2 failed: {fail.error}")
        return AgentResult(signal="ok")


def build_split_pipeline_graph(scheduler: Any, workspace: Path) -> PipelineGraph:
    """Declare the §19 split-focused design graph.

    design_card → exam_form → design(P1: 题干+设问+经验值参数, 大胆不验证)
        → form_gate → solve(解题代码, solver writes solve.py; 自重试不回退).
    Branch after solve (§19):
      solve success → design2(P2: 基于解设选项/答案填回) → final
      solve failed → terminal (no back-route; structural issues are form_gate's job).
    Conceptual: design → done (skip form_gate/solve/design2/final).

    Note: ``scheduler`` is the ``DocPipelineOrchestrator`` instance.
    """
    g = PipelineGraph()
    g.add_node("design_card", DesignCardNode(scheduler, workspace))
    g.add_node("exam_form", ExamFormNode(scheduler, workspace))
    g.add_node("design", DesignNode(scheduler, workspace))
    g.add_node("form_gate", FormGateNode(scheduler, workspace))
    g.add_node("solve", SolveNode(scheduler, workspace))
    g.add_node("design2", DesignFinalizeNode(scheduler, workspace))
    g.add_node("final", FinalNode(scheduler, workspace))

    g.edge("design_card", "ok", "exam_form")
    g.edge("exam_form", "ok", "design")
    # §21: conceptual 不走此 graph（_run_concept_pipeline 独立处理）。
    g.edge("design", "ok", "form_gate")
    g.edge("form_gate", "pass", "solve")
    g.edge("form_gate", "needs_fix", "design")
    g.edge("solve", "success", "design2")
    # §19.5: solve never back-routes; failure is terminal.
    g.edge("solve", "failed", "done")
    # design2 always → final (both choice and comprehensive finalize here).
    g.edge("design2", "ok", "final")
    g.edge("final", "pass", "done")
    g.edge("final", "question_error", "design")
    g.edge("final", "solution_error", "solve")
    return g
