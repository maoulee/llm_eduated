"""Top-level interactive orchestrator."""

from __future__ import annotations

import asyncio
import json
import logging
import os

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
                results = result.get("results", [])
                all_ok = all(r.get("ok") for r in results) if results else False
                session.generation_results = results
                if all_ok:
                    session.state = SessionState.COMPLETE
                    response += "\n\n题目生成完成！"
                else:
                    session.state = SessionState.ERROR
                    session.error_message = "部分题目生成失败"
                    response += f"\n\n部分题目生成失败，请检查生成结果。"
            except Exception as exc:
                logger.exception("Generation failed for session %s", session_id)
                session.state = SessionState.ERROR
                session.error_message = str(exc)
                response += f"\n\n生成题目时出错：{exc}"

        return response

    async def run_generation(self, session_id: str) -> dict:
        """After approval, trigger the generation pipeline.

        For knowledge_point mode:
          - Write assembled.md to a workspace directory
          - Call DocPipeline with the assembled doc
          - Return generation results

        For compose mode:
          - Call compose_runner.run_compose() + generate_runner.run_generate()

        Returns generation result metadata.
        """
        session = self.session_manager.get_or_create(session_id)
        session.state = SessionState.GENERATING

        if session.mode == "knowledge_point":
            return await self._generate_knowledge_point(session)
        elif session.mode == "compose":
            return await self._generate_compose(session)

        return {
            "session_id": session_id,
            "mode": session.mode,
            "blueprint_id": session.blueprint_id,
            "results": [],
        }

    async def _generate_knowledge_point(self, session) -> dict:
        """Generate questions for knowledge_point mode using DocPipeline."""
        import hashlib
        import os
        from datetime import datetime

        from core_new.doc_pipeline import DocPipeline

        p = session.collected_params
        knowledge_tag = p.get("knowledge_tag", "")
        if not knowledge_tag and p.get("knowledge_topic"):
            knowledge_tag = (
                self.knowledge_retriever.resolve_knowledge_tag(
                    p["knowledge_topic"]
                )
                or ""
            )

        # Build a synthetic slot_id from knowledge_tag
        tag_hash = hashlib.md5(knowledge_tag.encode("utf-8")).hexdigest()[:8] if knowledge_tag else "untagged"
        slot_id = f"KP-{tag_hash}"

        # Prepare workspace directory
        run_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")
        workspace = os.path.join("docs", "workspace", run_id)
        os.makedirs(workspace, exist_ok=True)

        # Write assembled doc to workspace root
        assembled_path = os.path.join(workspace, "assembled.md")
        with open(assembled_path, "w", encoding="utf-8") as f:
            f.write(session.blueprint_md)

        # Determine subject from knowledge_tag prefix or explicit param
        subject = self._resolve_subject(knowledge_tag, p)

        # Build slot_data for DocPipeline
        q_type_raw = p.get("question_type", "") or ""
        slot_data = {
            "slot_id": slot_id,
            "subject": subject,
            "knowledge_tag": knowledge_tag,
            "difficulty": p.get("difficulty", "medium"),
            "question_type": q_type_raw,
        }

        question_type = q_type_raw or None
        question_count = int(p.get("question_count", 1) or 1)
        results: list[dict] = []

        async def _run_one(idx: int) -> dict:
            q_workspace = os.path.join(workspace, f"q{idx + 1}")
            q_slot_id = f"{slot_id}-{idx + 1}" if question_count > 1 else slot_id

            logger.info(
                "DocPipeline session=%s slot_id=%s question=%d/%d",
                session.session_id, q_slot_id, idx + 1, question_count,
            )

            dp = DocPipeline(
                workspace=q_workspace,
                model_routing=self.model_routing,
            )
            result = await dp.run(
                slot_id=q_slot_id,
                slot_data=dict(slot_data),
                assembled_experience_doc=session.blueprint_md,
                question_type=question_type,
            )

            return {
                "slot_id": q_slot_id,
                "ok": result.ok,
                "review_status": result.review_status,
                "final_content": result.final_content if result.ok else None,
                "total_time_s": result.total_time_s,
            }

        if question_count > 1:
            results = await asyncio.gather(*[_run_one(i) for i in range(question_count)])
        else:
            results = [await _run_one(0)]

        return {
            "session_id": session.session_id,
            "mode": "knowledge_point",
            "blueprint_id": session.blueprint_id,
            "slot_id": slot_id,
            "workspace": workspace,
            "results": results,
        }

    @staticmethod
    def _resolve_subject(knowledge_tag: str, params: dict) -> str:
        """Determine the 408 subject code from knowledge_tag prefix or params."""
        if knowledge_tag.startswith("CN"):
            return "CN"
        if knowledge_tag.startswith("DS"):
            return "DS"
        if knowledge_tag.startswith("OS"):
            return "OS"

        subj = params.get("subject", "")
        if "网络" in subj:
            return "CN"
        if "数据" in subj:
            return "DS"
        if "操作" in subj:
            return "OS"
        return "CO"

    async def _generate_compose(self, session) -> dict:
        """Generate a full paper via compose_runner + generate_runner."""
        from compose import compose_runner, generate_runner

        templates, exp_cards = self._load_compose_assets()
        if not templates:
            raise RuntimeError("slot_templates.json not found — run slot_extractor first")

        p = session.collected_params
        user_requirements = self._build_compose_requirements(p)

        # Phase A: outline + assembly
        compose_result = await compose_runner.run_compose(
            gateway=self.gateway,
            slot_templates=templates,
            experience_cards=exp_cards,
            user_requirements=user_requirements,
            model_routing=self.model_routing,
        )
        if compose_result.get("status") != "ok":
            raise RuntimeError(f"Compose failed: {compose_result}")

        # Phase B: question generation
        generate_result = await generate_runner.run_generate(
            gateway=self.gateway,
            compose_dir=compose_result["compose_dir"],
            model_routing=self.model_routing,
            run_id=compose_result.get("run_id"),
        )

        return {
            "session_id": session.session_id,
            "mode": "compose",
            "blueprint_id": session.blueprint_id,
            "compose_result": compose_result,
            "generate_result": generate_result,
        }

    @staticmethod
    def _load_compose_assets() -> tuple[dict, dict]:
        """Load slot templates and experience cards from disk."""
        tpl_path = "data/config/slot_templates.json"
        templates = {}
        if os.path.exists(tpl_path):
            with open(tpl_path, encoding="utf-8") as f:
                templates = json.load(f).get("templates", {})

        exp_cards = {}
        exp_dir = "data/slot_experiences"
        if os.path.isdir(exp_dir):
            for fname in os.listdir(exp_dir):
                if fname.endswith("_experience.md"):
                    sid = fname.replace("_experience.md", "")
                    with open(os.path.join(exp_dir, fname), encoding="utf-8") as f:
                        exp_cards[sid] = f.read()

        return templates, exp_cards

    @staticmethod
    def _build_compose_requirements(params: dict) -> str:
        """Build user_requirements string from collected compose params."""
        parts = []
        subject = params.get("subject", "")
        if subject:
            parts.append(f"科目: {subject}")
        difficulty = params.get("difficulty", "")
        if difficulty:
            parts.append(f"难度: {difficulty}")
        q_count = params.get("question_count", "")
        if q_count:
            parts.append(f"题目数量: {q_count}")
        q_types = params.get("question_types") or params.get("question_type", "")
        if q_types:
            if isinstance(q_types, list):
                q_types = "、".join(q_types)
            parts.append(f"题型: {q_types}")
        return "；".join(parts) if parts else "408考研标准试卷"
