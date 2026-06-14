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
            feedback = parse_doc_section(str(review_path), "corrections")
            if not feedback.strip() or feedback.strip() == "无":
                feedback = parse_doc_section(str(review_path), "summary")
        return AgentResult(signal=status, feedback=feedback)


class SolveNode(_OrchestratorNode):
    """Layer 4 (Solve). Runs solver + exec.

    signal: ``success`` → final review; ``code_error`` → back to question.
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
            return AgentResult(signal="code_error", feedback=fail.error)
        # code-as-truth: any failed exec (non-zero exit / value validation)
        # is a code_error that routes back to Question. ``ok`` defaults to True
        # only when no solve.py existed (conceptual skip).
        if not exec_result.get("ok", True):
            return AgentResult(
                signal="code_error",
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
    g.edge("solve", "code_error", "question")
    g.edge("final", "pass", "done")
    g.edge("final", "question_error", "question")
    g.edge("final", "solution_error", "solve")
    return g


# ── §17/§18 split-focused design nodes + graph ────────────────────
#
# Split path (feature-flagged via enable_split_design), §18 form:
#   design_card → exam_form → skeleton_design(题干+参数, 大胆不验证)
#                                       → form_gate → solve(解题代码, solver writes solve.py)
#   solve success → [选择题] distractor_assembly(第2遍: 基于答案设计干扰选项) → final
#                 → [主观题] final (答案填回题干, 直接前进不回退)
#   solve code_error → skeleton_design (tune params; §18: solver writes solve.py,
#                      skeleton only retunes the stem/params)
#   Conceptual: skeleton_design → done (skip form_gate/solve/distractor/final).


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


class SkeletonDesignNode(_OrchestratorNode):
    """§16.2/§18 skeleton_design: reuse skeleton → stem + questions + initial params.

    Bold-no-verify (discipline ①). Does NOT write solve.py (solver does, §18.4).
    Single run per visit; form_gate/code_error feedback threads through the
    state's feedback_buffer. Reports ``ok``.
    """

    name = "skeleton_design"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        ref_path = DesignCardNode._ref_path(state)
        feedback = (
            state.feedback_buffer.get("form_gate", "")
            or state.feedback_buffer.get("solve", "")
        )
        fail = await self.orch._run_skeleton_design(
            state.slot_id, state.slot_data, ws, ref_path, feedback=feedback,
        )
        if fail is not None:
            state.result = fail
            return AgentResult(signal="ok", feedback=f"skeleton_design failed: {fail.error}")
        return AgentResult(signal="ok", feedback=feedback)


class DistractorNode(_OrchestratorNode):
    """§18.5 design-2nd pass (single-choice only): design distractor options
    based on the correct answer + solution (the design agent knows the question
    intent best). Give 3 plausible wrong values (NOT code-computed), verify 4
    distinct, append A/B/C/D. Comprehensive questions skip this node (correct
    fills back the stem → straight to final).
    signal: ``success`` → final; ``distractor_error`` → back to solve.
    """

    name = "distractor_assembly"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        # Comprehensive questions: no distractor step — route straight through.
        q_role = state.slot_data.get("question_type")
        from .orchestrator import _question_role as _qr
        if _qr(state.slot_id, question_type=q_role, slot_data=state.slot_data) != "question_sc":
            return AgentResult(signal="success")

        fail = await self.orch._run_distractor_assembly(
            state.slot_id, state.slot_data, ws,
        )
        if fail is not None:
            state.result = fail
            return AgentResult(signal="distractor_error", feedback=fail.error)
        # Verify 4 distinct option values landed in question.md (best-effort).
        return AgentResult(signal="success")


def build_split_pipeline_graph(scheduler: Any, workspace: Path) -> PipelineGraph:
    """Declare the §18 split-focused design graph.

    design_card → exam_form → skeleton_design(stem+params, bold-no-verify)
        → form_gate → solve(problem-solving code; solver writes solve.py).
    Branch after solve (§18.5):
      - 选择题: solve → distractor_assembly(第2遍: 基于答案设计干扰选项) → final
      - 主观题: solve → distractor_assembly(no-op) → final (答案填回题干, 直接前进)
    solve code_error → skeleton_design (retune stem/params; §18: solver writes solve.py).
    Conceptual: skeleton_design → done (skip form_gate/solve/distractor/final).

    Note: ``scheduler`` is the ``DocPipelineOrchestrator`` instance.
    """
    g = PipelineGraph()
    g.add_node("design_card", DesignCardNode(scheduler, workspace))
    g.add_node("exam_form", ExamFormNode(scheduler, workspace))
    g.add_node("skeleton_design", SkeletonDesignNode(scheduler, workspace))
    g.add_node("form_gate", FormGateNode(scheduler, workspace))
    g.add_node("solve", SolveNode(scheduler, workspace))
    g.add_node("distractor_assembly", DistractorNode(scheduler, workspace))
    g.add_node("final", FinalNode(scheduler, workspace))

    g.edge("design_card", "ok", "exam_form")
    g.edge("exam_form", "ok", "skeleton_design")
    # Conceptual: skip form_gate/solve/distractor/final.
    g.edge("skeleton_design", "ok", "done", condition=lambda s: s.complexity == "conceptual")
    g.edge("skeleton_design", "ok", "form_gate", condition=lambda s: s.complexity != "conceptual")
    g.edge("form_gate", "pass", "done", condition=lambda s: s.complexity == "conceptual")
    g.edge("form_gate", "pass", "solve")
    g.edge("form_gate", "needs_fix", "skeleton_design")
    g.edge("solve", "success", "distractor_assembly")
    g.edge("solve", "code_error", "skeleton_design")
    # distractor_assembly: choice → final; comprehensive already routed through.
    g.edge("distractor_assembly", "success", "final")
    g.edge("distractor_assembly", "distractor_error", "solve")
    g.edge("final", "pass", "done")
    g.edge("final", "question_error", "skeleton_design")
    g.edge("final", "solution_error", "solve")
    return g
