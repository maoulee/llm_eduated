"""Top-level interactive orchestrator."""

from __future__ import annotations

import logging

from core_new.llm_gateway import LLMGateway
from interact.intent_router import IntentRouter
from interact.knowledge_retriever import KnowledgeRetriever
from interact.blueprint_synthesizer import BlueprintSynthesizer
from interact.session_manager import SessionManager, SessionState

logger = logging.getLogger(__name__)


class InteractiveOrchestrator:
    """Top-level coordinator for the interactive question-generation workflow.

    Owns all components and delegates state management to SessionManager.
    """

    def __init__(self, gateway: LLMGateway, model_routing: dict | None = None) -> None:
        """Initialize all components.

        Args:
            gateway: LLMGateway instance (Qwen local).
            model_routing: Optional dict for pipeline model selection.
        """
        self.gateway = gateway
        self.model_routing = model_routing or {}

        self.intent_router = IntentRouter(gateway)
        self.knowledge_retriever = KnowledgeRetriever()
        self.blueprint_synthesizer = BlueprintSynthesizer(gateway, self.knowledge_retriever)
        self.session_manager = SessionManager(
            self.intent_router,
            self.knowledge_retriever,
            self.blueprint_synthesizer,
        )

    async def handle_input(self, session_id: str, user_message: str) -> str:
        """Process one user message. Returns response to show the user.

        Delegates to SessionManager.handle_message().
        Wraps exceptions in user-friendly error messages.
        """
        try:
            response = await self.session_manager.handle_message(session_id, user_message)
        except Exception as exc:
            logger.exception("Orchestrator error for session %s", session_id)
            response = f"处理您的请求时出现错误：{exc}\n请重新描述您的需求。"

        # Check if session transitioned to APPROVED — trigger generation
        session = self.session_manager.get_or_create(session_id)
        if session.state == SessionState.APPROVED:
            try:
                result = await self.run_generation(session_id)
                session.state = SessionState.COMPLETE
                session.generation_results = result.get("results", [])
                response += "\n\n题目生成完成！"
            except Exception as exc:
                logger.exception("Generation failed for session %s", session_id)
                session.state = SessionState.ERROR
                session.error_message = str(exc)
                response += f"\n\n生成题目时出错：{exc}"

        return response

    async def run_generation(self, session_id: str) -> dict:
        """After approval, trigger the generation pipeline.

        For knowledge_point mode:
          - Parse blueprint into slot-like entries
          - Call doc_pipeline for each question in parallel

        For compose mode:
          - Call compose_runner.run_compose() + generate_runner.run_generate()

        Returns generation result metadata.

        TODO: Integrate with actual generation pipeline after interaction layer
              is tested. Currently returns a placeholder result.
        """
        session = self.session_manager.get_or_create(session_id)
        session.state = SessionState.GENERATING

        # TODO: Wire up actual generation pipeline
        # if session.mode == "knowledge_point":
        #     entries = _parse_blueprint_to_slots(session.blueprint_md)
        #     results = await asyncio.gather(*[
        #         doc_pipeline.generate(entry) for entry in entries
        #     ])
        # elif session.mode == "compose":
        #     from compose.compose_runner import run_compose
        #     result = await run_compose(...)
        #     results = [result]

        logger.info(
            "Generation triggered for session %s mode=%s (stub)",
            session_id,
            session.mode,
        )

        return {
            "session_id": session_id,
            "mode": session.mode,
            "blueprint_id": session.blueprint_id,
            "results": [],
        }
