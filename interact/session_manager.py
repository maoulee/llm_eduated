"""FSM-based session manager for multi-turn interaction."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

from interact.intent_router import IntentRouter, IntentResult
from interact.knowledge_retriever import KnowledgeRetriever
from interact.blueprint_synthesizer import BlueprintSynthesizer, SynthesisRequest

logger = logging.getLogger(__name__)

# Keywords the user might say to approve a blueprint
# Negative lookbehind for "不" to exclude "不可以", "不行"
# Negative lookahead for "吗|的" to exclude "可以这样吗", "行的吗"
_APPROVAL_PATTERNS = re.compile(
    r"(?<!不)(确认|没问题|ok|好的|批准|通过|approve|就这样|同意)"
    r"|(?<!不)(可以|行)(?!吗|的)",
    re.IGNORECASE,
)


class SessionState(Enum):
    IDLE = "idle"
    COLLECTING = "collecting"            # gathering params from user
    BLUEPRINT_READY = "blueprint_ready"  # blueprint generated, awaiting approval
    ANNOTATING = "annotating"            # user is reviewing/annotating blueprint
    APPROVED = "approved"                # user approved, triggering generation
    GENERATING = "generating"            # questions being generated
    COMPLETE = "complete"                # all done
    ERROR = "error"


@dataclass
class SessionData:
    session_id: str
    state: SessionState = SessionState.IDLE
    mode: str = ""                        # "compose" | "knowledge_point"
    collected_params: dict = field(default_factory=dict)
    missing_params: list[str] = field(default_factory=list)
    blueprint_md: str = ""               # current blueprint text
    blueprint_id: str = ""               # blueprint identifier
    annotation_round: int = 0
    max_annotation_rounds: int = 3
    generation_results: list = field(default_factory=list)
    error_message: str = ""


class SessionManager:
    """FSM-based session manager driving multi-turn interaction."""

    def __init__(
        self,
        intent_router: IntentRouter,
        knowledge_retriever: KnowledgeRetriever,
        blueprint_synthesizer: BlueprintSynthesizer,
    ) -> None:
        self.intent_router = intent_router
        self.knowledge_retriever = knowledge_retriever
        self.blueprint_synthesizer = blueprint_synthesizer
        self.sessions: dict[str, SessionData] = {}

    def get_or_create(self, session_id: str) -> SessionData:
        """Get existing session or create a new one."""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionData(session_id=session_id)
        return self.sessions[session_id]

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def handle_message(self, session_id: str, user_message: str) -> str:
        """Process a user message within the current session state.

        Returns the response string to display to the user.
        """
        session = self.get_or_create(session_id)

        try:
            if session.state == SessionState.IDLE:
                return await self._handle_idle(session, user_message)
            elif session.state == SessionState.COLLECTING:
                return await self._handle_collecting(session, user_message)
            elif session.state == SessionState.BLUEPRINT_READY:
                return await self._handle_blueprint_ready(session, user_message)
            elif session.state == SessionState.ANNOTATING:
                return await self._handle_annotating(session, user_message)
            elif session.state == SessionState.GENERATING:
                return "题目正在生成中，请稍候..."
            elif session.state == SessionState.COMPLETE:
                return await self._handle_restart(session, user_message)
            elif session.state == SessionState.ERROR:
                return await self._handle_restart(session, user_message)
            else:
                return "未知状态，请重新描述您的需求。"
        except Exception as exc:
            logger.exception("Session %s error in state %s", session_id, session.state)
            session.state = SessionState.ERROR
            session.error_message = str(exc)
            return f"处理时发生错误：{exc}\n请重新描述您的需求以开始新的会话。"

    # ------------------------------------------------------------------
    # State handlers
    # ------------------------------------------------------------------

    async def _handle_idle(self, session: SessionData, user_message: str) -> str:
        """IDLE: classify intent, either start collection or synthesize."""
        result: IntentResult = await self.intent_router.route(user_message)

        session.collected_params.update(result.params)

        # Fully ambiguous — no direction at all
        if result.intent == "clarify" and not result.params:
            session.missing_params = result.missing_params or ["subject", "difficulty", "question_count"]
            session.state = SessionState.COLLECTING
            return result.response or self._ask_missing(session)

        # Compose mode — needs compose_runner, not blueprint_synthesizer
        if result.intent == "compose":
            session.mode = "compose"
            if result.missing_params:
                session.missing_params = result.missing_params
                session.state = SessionState.COLLECTING
                return result.response or self._ask_missing(session)
            # Params complete — confirm understanding before compose_runner call
            session.state = SessionState.BLUEPRINT_READY
            return self._format_compose_confirmation(session)

        # Knowledge point mode with partial params — collect more
        if result.missing_params:
            session.mode = "knowledge_point"
            session.missing_params = result.missing_params
            session.state = SessionState.COLLECTING
            return result.response or self._ask_missing(session)

        # Knowledge point mode with all params — synthesize blueprint
        session.mode = "knowledge_point"
        return await self._synthesize_blueprint(session)

    async def _handle_collecting(self, session: SessionData, user_message: str) -> str:
        """COLLECTING: accumulate params until complete."""
        accumulated = self._build_accumulated_message(session, user_message)
        result: IntentResult = await self.intent_router.route(accumulated)

        session.collected_params.update(result.params)

        if result.missing_params:
            session.missing_params = result.missing_params
            return result.response or self._ask_missing(session)

        # All params collected
        if result.intent in ("compose", "knowledge_point"):
            session.mode = result.intent
            session.collected_params.update(result.params)

        if session.mode == "compose":
            session.state = SessionState.BLUEPRINT_READY
            return self._format_compose_confirmation(session)

        return await self._synthesize_blueprint(session)

    async def _handle_blueprint_ready(self, session: SessionData, user_message: str) -> str:
        """BLUEPRINT_READY: user approves or provides feedback."""
        if self._is_approval(user_message):
            session.state = SessionState.APPROVED
            return "已确认！正在开始生成题目..."

        # User provided feedback — transition to annotating
        session.state = SessionState.ANNOTATING
        return await self._handle_annotating(session, user_message)

    async def _handle_annotating(self, session: SessionData, user_message: str) -> str:
        """ANNOTATING: process annotation, revise blueprint."""
        session.annotation_round += 1

        if self._is_approval(user_message):
            session.state = SessionState.APPROVED
            return "已确认！正在开始生成题目..."

        if session.annotation_round >= session.max_annotation_rounds:
            session.state = SessionState.APPROVED
            return "已达到最大修订次数，使用当前版本开始生成题目。"

        # Revise blueprint via LLM
        revised = await self._revise_blueprint(session, user_message)
        session.blueprint_md = revised
        session.state = SessionState.BLUEPRINT_READY
        summary = self._format_blueprint_summary(revised)
        return (
            f"已根据您的反馈修订蓝图（第 {session.annotation_round} 次修订）：\n\n"
            f"{summary}\n\n"
            "请确认或继续提出修改意见。"
        )

    async def _handle_restart(self, session: SessionData, user_message: str) -> str:
        """COMPLETE / ERROR: user can start a new session."""
        # Reset session and treat message as a fresh request
        self.sessions.pop(session.session_id, None)
        return await self.handle_message(session.session_id, user_message)

    # ------------------------------------------------------------------
    # Blueprint synthesis
    # ------------------------------------------------------------------

    async def _synthesize_blueprint(self, session: SessionData) -> str:
        """Trigger blueprint synthesis and transition to BLUEPRINT_READY."""
        p = session.collected_params

        # Resolve knowledge_topic → knowledge_tag if needed
        knowledge_tag = p.get("knowledge_tag", "")
        if not knowledge_tag and p.get("knowledge_topic"):
            knowledge_tag = self.knowledge_retriever.resolve_knowledge_tag(
                p["knowledge_topic"]
            ) or ""
            # Ambiguous: multiple candidates → ask user to pick
            if not knowledge_tag:
                candidates = self.knowledge_retriever.search(p["knowledge_topic"])
                if len(candidates) > 1:
                    session.missing_params = ["knowledge_topic"]
                    session.state = SessionState.COLLECTING
                    labels = "\n".join(
                        f"  {i+1}. {c}" for i, c in enumerate(candidates[:5])
                    )
                    return (
                        f"「{p['knowledge_topic']}」匹配到多个知识点，请选择：\n"
                        f"{labels}\n\n请输入编号或更精确的描述。"
                    )
                if candidates:
                    knowledge_tag = candidates[0]

        request = SynthesisRequest(
            knowledge_tag=knowledge_tag,
            user_intent=p.get("user_intent", p.get("knowledge_topic", "")),
            subject=p.get("subject", ""),
            difficulty=p.get("difficulty", ""),
            question_count=int(p.get("question_count", 1) or 1),
            question_type=p.get("question_type", ""),
        )
        result = await self.blueprint_synthesizer.synthesize(request)
        session.blueprint_md = result.assembled_md
        session.blueprint_id = result.blueprint_id
        session.state = SessionState.BLUEPRINT_READY

        summary = self._format_blueprint_summary(result.assembled_md)
        return (
            f"蓝图已生成：\n\n{summary}\n\n"
            "请确认此蓝图，或提出修改意见。"
        )

    async def _revise_blueprint(self, session: SessionData, feedback: str) -> str:
        """Revise the current blueprint based on user feedback.

        Uses the blueprint synthesizer to re-synthesize with the same
        params plus the user's annotation feedback appended.
        """
        p = session.collected_params
        knowledge_tag = p.get("knowledge_tag", "")
        if not knowledge_tag and p.get("knowledge_topic"):
            knowledge_tag = self.knowledge_retriever.resolve_knowledge_tag(
                p["knowledge_topic"]
            ) or ""

        request = SynthesisRequest(
            knowledge_tag=knowledge_tag,
            user_intent=p.get("user_intent", p.get("knowledge_topic", "")),
            subject=p.get("subject", ""),
            difficulty=p.get("difficulty", ""),
            question_count=int(p.get("question_count", 1) or 1),
            question_type=p.get("question_type", ""),
            existing_blueprint=session.blueprint_md,
            feedback=feedback,
        )
        result = await self.blueprint_synthesizer.synthesize(request)
        return result.assembled_md

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_accumulated_message(self, session: SessionData, new_message: str) -> str:
        """Combine collected context with the new user message for re-routing."""
        parts = []
        for key, value in session.collected_params.items():
            parts.append(f"{key}: {value}")
        context_line = "；".join(parts)
        if context_line:
            return f"已有信息：{context_line}\n用户新输入：{new_message}"
        return new_message

    def _is_approval(self, text: str) -> bool:
        """Check if user message indicates approval."""
        return bool(_APPROVAL_PATTERNS.search(text.strip()))

    def _ask_missing(self, session: SessionData) -> str:
        """Generate a clarification prompt for missing parameters."""
        param_labels = {
            "subject": "科目",
            "difficulty": "难度（easy/medium/hard）",
            "question_count": "题目数量",
            "question_types": "题型（如 选择题、综合应用题）",
            "question_type": "题型（选择题 或 综合应用题）",
            "knowledge_topic": "知识点名称",
        }
        labels = [param_labels.get(p, p) for p in session.missing_params]
        return f"请补充以下信息：{', '.join(labels)}"

    def _format_compose_confirmation(self, session: SessionData) -> str:
        """Format a confirmation message for compose mode params."""
        p = session.collected_params
        subject = p.get("subject", "未指定")
        q_count = p.get("question_count", "未指定")
        q_types = p.get("question_types") or p.get("question_type", "未指定")
        difficulty = p.get("difficulty", "未指定")

        lines = [
            "组卷模式已确认，已理解您的需求：",
            f"  - 科目：{subject}",
            f"  - 题目数量：{q_count}",
            f"  - 题型：{q_types}",
            f"  - 难度：{difficulty}",
            "",
            "（组卷功能对接中，当前版本请使用知识点出题模式）",
        ]
        return "\n".join(lines)

    def _format_blueprint_summary(self, blueprint_md: str) -> str:
        """Extract key info from blueprint for user display."""
        lines = blueprint_md.strip().splitlines()
        summary_parts: list[str] = []

        # Extract title line (first # heading)
        for line in lines:
            if line.startswith("# ") and not line.startswith("## "):
                summary_parts.append(line.lstrip("# ").strip())
                break

        # Extract key-value pairs from first two sections (本次出题要求 + 基本信息)
        in_section = False
        for line in lines:
            if re.match(r"^## (本次出题要求|基本信息|模式概览)", line):
                in_section = True
                continue
            if in_section and line.startswith("## "):
                in_section = False
                continue
            if in_section and line.strip().startswith("- **"):
                summary_parts.append("  " + line.strip())

        # Count historical questions
        exp_count = sum(1 for l in lines if re.match(r"^# \d{4}年", l))
        if exp_count:
            summary_parts.append(f"\n  参考真题: {exp_count}道")

        return "\n".join(summary_parts) if summary_parts else "(蓝图摘要不可用)"
