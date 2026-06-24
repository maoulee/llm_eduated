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
    """§19 design Pass 2 (legacy, kept for backward compat)."""

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


class DesignSolveNode(_OrchestratorNode):
    """§22 design second round: gen.py exec validates constraints + computes
    answer + writes solution.md. gen.py IS the solver (no separate solve step).
    form_gate2 feedback threads through feedback_buffer. Reports ``ok``.
    """

    name = "design_solve"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        ref_path = DesignCardNode._ref_path(state)
        feedback = state.feedback_buffer.get("form_gate2", "")
        fail = await self.orch._run_design_solve(
            state.slot_id, state.slot_data, ws, ref_path, feedback=feedback,
        )
        if fail is not None:
            state.result = fail
            return AgentResult(signal="ok", feedback=f"design_solve failed: {fail.error}")
        return AgentResult(signal="ok", feedback=feedback)


class FormGateNode2(_OrchestratorNode):
    """§22 consistency review: question + solution aligned? Uses review2 agent
    (separate from form_gate's review agent) to avoid review.md overwrite.
    """

    name = "form_gate2"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        question_path = ws / "question.md"
        solution_path = ws / "solution.md"
        r_inject = {"题目": str(question_path)}
        if solution_path.exists():
            r_inject["求解结果"] = str(solution_path)
        r_task = (
            "§22 一致性审核：解题流程是否正确。\n"
            "**数值默认正确**（由 gen.py exec 保证），你不审数值对不对，不推演数值。\n"
            "你只做定性审核：\n"
            "① 解题流程：solution 的求解步骤方法对不对、逻辑链通不通\n"
            "② 设问-答案对应：题干每个问 solution 都回答了吗\n"
            "差距小→pass，差距大→needs_fix。"
        )
        await self.orch.scheduler.run_agent(
            "review2", r_task, slot_id=state.slot_id, inject_files=r_inject,
        )
        review_path = ws / "review2.md"
        status = "pass"
        feedback = ""
        if review_path.exists():
            status = get_doc_status(str(review_path), allowed=REVIEW_STATUSES) or "pass"
            # W4 fix: match FormGateNode's 4-level fallback for consistency
            feedback = parse_doc_section(str(review_path), "fix_instructions")
            if not feedback.strip() or feedback.strip() == "无":
                feedback = parse_doc_section(str(review_path), "feedback_for_agent")
            if not feedback.strip() or feedback.strip() == "无":
                feedback = parse_doc_section(str(review_path), "corrections")
            if not feedback.strip() or feedback.strip() == "无":
                feedback = parse_doc_section(str(review_path), "summary")
        return AgentResult(signal=status, feedback=feedback)


# team_pipeline 审求解(review_solve) 的 needs_fix 轮数上限。超过即 exhausted→done
# （显式 fail），防止 inherent 缺陷在 fix_gen↔review_solve 间烧满 MAX_NODE_VISITS。
REVIEW_SOLVE_MAX_ROUNDS = 3


# ── team_pipeline 四角色节点（build_team_pipeline_graph 用）──────────
# 把 team_pipeline.run_question 的手写过程式编排 graph 化：每个角色一个节点，
# 回退靠 edge（review_solve --fix_gen/fix_design--> 目标节点；fix_solution 已折叠进 fix_gen），feedback 靠
# feedback_buffer（fix_instructions，键=节点名）。黑板/experience 经 self.orch 注入。


class TeamDesignNode(_OrchestratorNode):
    """design_direct：读 design_card + 黑板 + 经验卡，一步直出 question.md。

    逻辑搬自 team_pipeline.run_question:229-233。黑板（paper_state.md）经
    ``self.orch._board_inject()`` 注入，软性避开已出考点。
    """

    name = "design_direct"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        ref_path = DesignCardNode._ref_path(state)
        inject: dict[str, Any] = {"design_card": str(ref_path)}
        # 跨题黑板注入（软提示去重）
        inject.update({k: str(v) for k, v in self.orch._board_inject().items()})
        board_hint = " 参考注入的 paper_state.md（已出题记录），软性避开重复考点。" if self.orch._board_inject() else ""
        # 教师个人需求/批注（前端锚定 → handoff → slot_data.teacher_annotation）。
        # design_card 生成时已参考，但这里显式再注入，确保 design_direct 稳定识别并
        # 落到题干设计 + 通过条件里（不依赖 design_card 是否逐字保留）。
        teacher_ann = state.slot_data.get("teacher_annotation", "")
        ann_hint = (
            f"\n\n## 教师个人需求/批注（务必参考——题干设计、通过条件都要体现）\n{teacher_ann}"
            if teacher_ann else ""
        )
        # 审核回退反馈：审题干 needs_fix（review_stem）或 审求解 fix_design（review_solve）
        feedback = state.feedback_buffer.get("review_solve") or state.feedback_buffer.get("review_stem") or ""
        fix_hint = (
            f"\n\n## 审核反馈需修正\n{feedback}\n按 fix_instructions 修正 question.md（含声明的通过条件）。"
            "注意：声明通过条件 ≠ 脑内计算。"
            if feedback else ""
        )
        await self.orch.scheduler.run_agent(
            "design_direct",
            task=f"根据 design_card 设计题干（含设计意图 + 声明「通过条件」——本题成立需要满足的可机检特征），写出 question.md。{board_hint}{ann_hint}{fix_hint}",
            slot_id=state.slot_id, inject_files=inject, target_file="question.md",
        )
        if not (ws / "question.md").exists():
            state.result = self.orch._fail_result(state.slot_id, "design_direct 未产出 question.md")
            return AgentResult(signal="ok", feedback="design_direct failed: no question.md")
        return AgentResult(signal="ok")


class TeamGenNode(_OrchestratorNode):
    """write_gen：读 question.md，写 gen.py + exec 验证。选择题派生干扰项。

    逻辑搬自 team_pipeline.run_question:244-253。回退轮次（review_solve 的
    fix_gen 后重入）携带 fix_instructions feedback，经 feedback_buffer["review_solve"] 传入。
    """

    name = "write_gen"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        is_choice = state.slot_data.get("question_type") == "single_choice"
        # 审求解(review_solve) 打回时的 fix_instructions（revisit 携带）
        feedback = state.feedback_buffer.get("review_solve", "")
        is_revisit = bool(feedback)
        assert_hint = " 务必把 question.md 声明的「通过条件」翻译成 assert（打到特征、禁弱化为结构判据/禁恒真）。"
        # 节点上下文 delta：通用 gen.py→exec→solution.md→finish 流程已在 write_gen.md / code_writer /
        # func_model 详述（agent 系统提示即载入它们），这里只注入【契约 + 选择题提示】，避免 4 处重复。
        choice_hint = "（选择题）用 exec 正确值派生 BCD 干扰项填 A/B/C/D→" if is_choice else ""
        cycle_hint = (
            "\n\n## 本轮契约（合并 write_solution 后，做完调 finish）\n"
            "做完整闭环：写 gen.py→exec 验证通过条件→" + choice_hint
            + "写 solution.md 忠实转写 exec 输出→调 finish。"
            "边界：gen.py 必须 exec 通过且 assert 命中通过条件；solution.md 必须忠实转写 exec 输出。"
            "你 finish 了但 gen.py/solution.md 缺或不一致=越界，系统退回让你重写。"
        )
        fix_hint = (
            f"\n\n## 审核反馈（review_solve 打回，按反馈修）\n{feedback}\n"
            "按 fix_instructions 自己判断改哪个：gen.py 建模/assert/充分性问题 → edit gen.py 重 exec 再更新 solution.md；"
            "solution.md 不忠实 → edit solution.md（不重算）；question.md 抄写错 → edit question.md。"
            "小改 edit / 大改重写，你判断。改完调 finish。"
        ) if is_revisit else ""
        inject = {"question.md": str(ws / "question.md"), "design_card": str(DesignCardNode._ref_path(state))}
        # 越界退回重写：首次正常跑 + 至多 2 次补齐重写（合并了原先重复的 run_agent 调用点，行为不变）
        MAX_REWRITE = 2
        full_task = f"读 question.md 完成出题闭环（gen.py→exec→核对→solution.md）。{assert_hint}{cycle_hint}{fix_hint}"
        for attempt in range(MAX_REWRITE + 1):
            if attempt == 0:
                task, preserve = full_task, is_revisit
            else:
                missing = [f for f in ("gen.py", "solution.md") if not (ws / f).exists()]
                logger.warning("[%s] write_gen finish 但产物缺失 %s，越界退回重写 (attempt %d)",
                               state.slot_id, missing, attempt)
                task = (f"你上一轮 finish 了但产物缺失：{missing}。补齐（gen.py 必须 exec 通过；"
                        "solution.md 忠实转写 exec 输出），再调 finish。")
                preserve = True
            await self.orch.scheduler.run_agent(
                "write_gen", task=task, slot_id=state.slot_id, inject_files=inject,
                target_file="gen.py",            # 仅 unlink 语义用；完成由 finish 决定（见 gate_on_file=False）
                gate_on_file=False,              # 完成只认 finish（多产物，不靠文件闸）
                preserve_existing=preserve,      # 首次按 is_revisit；重写恒 True（保住已验证文件做最小 edit）
                continue_session=(is_revisit or attempt > 0),
            )
            if all((ws / f).exists() for f in ("gen.py", "solution.md")):
                return AgentResult(signal="ok")
        state.result = self.orch._fail_result(
            state.slot_id, "write_gen 越界：finish 后 gen.py/solution.md 经重写仍缺失",
        )
        return AgentResult(signal="ok", feedback="write_gen 越界重写仍缺产物")


# TeamSolutionNode 已合并入 TeamGenNode（write_gen 全闭环产出 gen.py + solution.md）。


def _parse_review(review_path: Path) -> tuple[str, str]:
    """Parse review.md → (status, fix_instructions). status ∈ pass/needs_fix."""
    if not review_path.exists():
        return "pass", ""
    status = get_doc_status(str(review_path), allowed=REVIEW_STATUSES) or "pass"
    feedback = parse_doc_section(str(review_path), "fix_instructions")
    return status, feedback


def _review_signal(status: str, routing: str) -> str:
    """Map merged 审求解 review (status, routing) → graph signal.

    pass → 'pass'; needs_fix → 'fix_gen'/'fix_design' by routing (fix_solution 已折叠进 fix_gen——合并后 write_gen 单节点)
    (default write_gen). Extracted as a pure function so the adequacy/routing
    contract is unit-testable without running the LLM agent.
    """
    if status != "needs_fix":
        return "pass"
    routing = (routing or "").lower()
    if "design" in routing:
        return "fix_design"
    # 合并后 write_gen 单节点承担 gen.py + solution.md，fix_solution 折叠进 fix_gen
    return "fix_gen"


class TeamReviewStemNode(_OrchestratorNode):
    """dual_review 阶段1（审题干）：write_gen 之前，审 question.md 自洽 + 通过条件合格。

    needs_fix → 回退 design_direct（fix_instructions 经 feedback_buffer 传递）。这是
    team_pipeline 原本缺失的审题干 gate（split graph 的 form_gate 对应物），也是堵
    "参数打败考点"的第一道：通过条件是否声明、可证伪、覆盖考察目标。
    """

    name = "review_stem"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        await self.orch.scheduler.run_agent(
            "dual_review",
            task=(
                "## 本轮阶段\n本轮审题干（阶段1，write_gen 之前）。审 question.md："
                "题干自洽 + 通过条件合格（存在/可证伪/覆盖考察目标）。"
            ),
            slot_id=state.slot_id,
            inject_files={"question.md": str(ws / "question.md"),
                          "design_card": str(DesignCardNode._ref_path(state))},
            target_file="review.md", enable_thinking=True,
        )
        status, feedback = _parse_review(ws / "review.md")
        return AgentResult(signal=status, feedback=feedback)


class TeamReviewNode(_OrchestratorNode):
    """dual_review 阶段2（审求解）：write_gen 完成 gen.py+solution.md 之后，合并审核（原 审代码+审文档 合一）。

    一次审 gen.py+solution.md+exec：建模忠实 + 断言合适（assert 打到通过条件、非弱化、
    非恒真）+ 充分性（exec 满足声明条件=合围，"参数打败考点"的唯一可靠卡口）+ 设计一致性
    + 文档忠实。按 review.md 的 routing 决定回退目标（write_gen/design_direct）。
    审完搬运 entry 到全卷黑板。
    """

    name = "review_solve"

    async def run(self, state: PipelineState) -> AgentResult:
        ws = self.workspace / state.slot_id
        await self.orch.scheduler.run_agent(
            "dual_review",
            task=(
                "## 本轮阶段\n本轮审求解（阶段2，write_gen 完成 gen.py+solution.md 之后，合并审核）。"
                "审 gen.py+solution.md：建模忠实 + 断言合适 + 充分性（exec 满足通过条件）"
                "+ 设计一致性 + 文档忠实。读 gen.py exec 输出比对声明条件，不代入算、不重跑。"
            ),
            slot_id=state.slot_id,
            inject_files={"question.md": str(ws / "question.md"),
                          "gen.py": str(ws / "gen.py"),
                          "solution.md": str(ws / "solution.md")},
            target_file="review.md", enable_thinking=True,
        )
        review_path = ws / "review.md"
        if not review_path.exists():
            # review.md 缺失 = agent 异常未产出，按 pass 兜底（routing 此分支不生效）
            status, feedback, routing = "pass", "", "write_gen"
        else:
            status = get_doc_status(str(review_path), allowed=REVIEW_STATUSES) or "pass"
            feedback = parse_doc_section(str(review_path), "fix_instructions")
            routing = (parse_doc_section(str(review_path), "routing") or "write_gen").strip()
        signal = _review_signal(status, routing)
        # 环路安全：review_solve 的 needs_fix 轮数兜底。inherent 缺陷（参数 inherently
        # 不触发考点）会在 fix_gen↔review_solve 间反复；超阈值→显式 fail 终止（exhausted→done），
        # 不留半成品 final（orchestrator 见 state.result fail 会 surface）。
        if signal != "pass" and state.visit_counts.get("review_solve", 0) >= REVIEW_SOLVE_MAX_ROUNDS:
            state.result = self.orch._fail_result(
                state.slot_id,
                f"review_solve {state.visit_counts.get('review_solve', 0)} 轮 needs_fix 未收敛，终止（防死循环）",
            )
            return AgentResult(signal="exhausted", feedback=feedback)
        # 仅在通过时登记全卷黑板（对齐原 team_pipeline "review 退出后登记一次" 语义；
        # needs_fix 重试不重复登记，避免同一 slot 在 paper_state.md 写多行）
        if signal == "pass":
            self.orch.append_board(state.slot_id, slot=state.slot_data, fallback_status=status)
        return AgentResult(signal=signal, feedback=feedback)


def build_split_pipeline_graph(scheduler: Any, workspace: Path) -> PipelineGraph:
    """Declare the §22 suggestion-driven iteration graph.

    §22 flow (suggestion-driven, code-first for computational questions):
      design_card → exam_form
        → design（第一轮：gen.py 构造参数 + write question.md 题干，停止）
        → form_gate（审题干结构：考察形式/考点对齐，给建议）
           needs_fix → design（带建议优化）
        → design_solve（第二轮：gen.py exec 验证约束 + 算答案 + write solution.md）
        → form_gate2（审一致性：题干设问与求解对齐，给建议）
           needs_fix → design_solve（带建议优化）
        → final（产出最终文档）

    Conceptual: _run_concept_pipeline 独立处理，不走此 graph。

    Note: ``scheduler`` is the ``DocPipelineOrchestrator`` instance.
    """
    g = PipelineGraph()
    g.add_node("design_card", DesignCardNode(scheduler, workspace))
    g.add_node("exam_form", ExamFormNode(scheduler, workspace))
    g.add_node("design", DesignNode(scheduler, workspace))
    g.add_node("form_gate", FormGateNode(scheduler, workspace))
    g.add_node("design_solve", DesignSolveNode(scheduler, workspace))
    g.add_node("form_gate2", FormGateNode2(scheduler, workspace))
    g.add_node("final", FinalNode(scheduler, workspace))

    g.edge("design_card", "ok", "exam_form")
    g.edge("exam_form", "ok", "design")
    # design 写 gen.py（约束建模）+ question.md → form_gate 审题干
    g.edge("design", "ok", "form_gate")
    g.edge("form_gate", "needs_fix", "design")
    # form_gate suggestion → 直接前进到 design_solve（表述小问题不回退）
    g.edge("form_gate", "suggestion", "design_solve")
    # form_gate 通过 → design_solve（exec gen.py 求解 + write solution.md）
    g.edge("form_gate", "pass", "design_solve")
    # design_solve → form_gate2 审一致性
    g.edge("design_solve", "ok", "form_gate2")
    g.edge("form_gate2", "needs_fix", "design_solve")
    g.edge("form_gate2", "suggestion", "final")
    # form_gate2 通过 → final（整合交付）
    g.edge("form_gate2", "pass", "final")
    # final 是整合交付，pass/expression_fix 都直接 done（不回退）
    g.edge("final", "pass", "done")
    g.edge("final", "expression_fix", "done")
    return g


def build_team_pipeline_graph(scheduler: Any, workspace: Path) -> PipelineGraph:
    """Declare the team_pipeline three-role graph (write_gen 合并 write_solution 全闭环).

    team flow (code-as-truth 三角色常驻团队):
      design_direct → 审题干(review_stem)
                        needs_fix → design_direct（带 fix_instructions）
                        pass → write_gen（全闭环：gen.py→exec→solution.md，完成调 finish）
                                   → 审求解(review_solve，合并审核)
                        fix_gen → write_gen（gen/solution 都回流 write_gen）/ fix_design → design_direct
                        pass → final（产出 final.md 三段式）

    vs split graph：三角色合一（design_direct 一步出题干，write_gen 全闭环建模+求解，
    dual_review 两阶段审核——审题干 + 审求解合并）。审题干是 team_pipeline 原本缺失的 gate；
    审求解合并原 审代码+审文档，新增断言合适 + 充分性判据堵"参数打败考点"。
    黑板（paper_state.md）由 orchestrator 持有，design_direct 经 ``self.orch._board_inject()`` 注入。

    复用现有 FinalNode（调 _run_final_review_loop 产 final.md + experience 注入）。

    Note: ``scheduler`` is the ``DocPipelineOrchestrator`` instance.
    Gated by ``features.enable_team_pipeline``.
    """
    g = PipelineGraph()
    g.initial = "design_direct"  # team graph 从 design_direct 开始（非默认的 design_card）
    g.add_node("design_direct", TeamDesignNode(scheduler, workspace))
    g.add_node("review_stem", TeamReviewStemNode(scheduler, workspace))
    g.add_node("write_gen", TeamGenNode(scheduler, workspace))
    g.add_node("review_solve", TeamReviewNode(scheduler, workspace))
    g.add_node("final", FinalNode(scheduler, workspace))

    # design_direct 写 question.md → 审题干（自洽 + 通过条件合格）
    g.edge("design_direct", "ok", "review_stem")
    # 审题干 needs_fix → 回 design_direct（带 fix_instructions feedback）
    g.edge("review_stem", "needs_fix", "design_direct")
    # 审题干 suggestion（表述小问题，不阻塞建模）→ write_gen，对齐 split form_gate 语义
    g.edge("review_stem", "suggestion", "write_gen")
    # 审题干通过 → write_gen 建模
    g.edge("review_stem", "pass", "write_gen")
    # write_gen 全闭环（gen.py + solution.md）→ 审求解（合并审核）
    g.edge("write_gen", "ok", "review_solve")
    # 审求解按 routing 回退（fix_solution 已折叠进 fix_gen——合并后 write_gen 单节点）
    g.edge("review_solve", "fix_gen", "write_gen")
    g.edge("review_solve", "fix_design", "design_direct")
    # 审求解 exhausted（needs_fix 轮数超 REVIEW_SOLVE_MAX_ROUNDS）→ done（显式 fail）
    g.edge("review_solve", "exhausted", "done")
    # 审求解通过 → final（整合交付，复用 FinalNode）
    g.edge("review_solve", "pass", "final")
    # final 是整合交付，pass/expression_fix 都直接 done
    g.edge("final", "pass", "done")
    g.edge("final", "expression_fix", "done")
    return g
