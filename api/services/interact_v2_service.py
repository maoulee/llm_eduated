"""Service layer for V2 interact API.

Wraps core_new.doc_pipeline.scheduler for web consumption.
Scheduler is zero-change; this layer does MD<->JSON conversion and
session lifecycle management.

Architecture:
    InteractV2Service (facade)
    +-- SessionManager -- session CRUD, message persistence
    +-- ClarificationHandler -- Scenario C heuristics + GLM outline
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import time
from pathlib import Path
from typing import Optional

from api.schemas_interact_v2 import (
    AnnotationSubmission,
    DraftData,
    InteractSessionInfo,
    InteractTurnResponse,
)
from api.services.interact_clarification import ClarificationHandler
from api.services.interact_session_manager import SessionManager, validate_session_id

logger = logging.getLogger(__name__)

_HANDOFF_YAML_NAMES = ("slot_blueprint.yaml", "paper_request.yaml", "retrieval_query.yaml")


# Lazy imports for draft_parser — may not exist yet during development.
# When the module is available these will resolve; otherwise we fall back
# to simple heuristics.


def _try_import_draft_parser():
    """Import draft_parser functions if available."""
    try:
        from api.services.draft_parser import (
            detect_draft_in_response,
            parse_draft_md,
            parse_yaml_result,
            render_annotated_md,
        )
        return detect_draft_in_response, parse_draft_md, parse_yaml_result, render_annotated_md
    except ImportError:
        return None, None, None, None


(_detect_draft, _parse_draft, _parse_yaml, _render_annotated) = _try_import_draft_parser()

if _detect_draft is None:
    logger.warning("draft_parser module not available — draft features disabled")


class InteractV2Service:
    """Service layer for V2 interact API.

    Wraps DocScheduler for web consumption.  The scheduler is created per
    provider and cached; session state lives inside the scheduler's
    ``_interact_sessions`` dict.

    Delegates to:
        - ``SessionManager`` for session CRUD and message persistence
        - ``ClarificationHandler`` for Scenario C detection and outline
    """

    def __init__(self) -> None:
        self._session_mgr = SessionManager()
        self._drafts: dict[str, DraftData] = {}  # session_id -> latest draft
        self._annotations: dict[str, AnnotationSubmission] = {}  # session_id -> latest draft annotation
        self._scheduler_cache: dict[str, object] = {}  # cache_key -> DocScheduler
        self._clarification = ClarificationHandler

    def _restore_sessions_from_disk(self) -> None:
        """Delegate to SessionManager for backward compat with tests.

        Resolves workspace path here (using this module's Path import) so that
        tests which mock ``api.services.interact_v2_service.Path`` still work.
        """
        workspace = Path("workspace")
        self._session_mgr._restore_sessions_from_disk(workspace_root=workspace)

    # ------------------------------------------------------------------
    # Convenience properties for backward compat with tests / display service
    # ------------------------------------------------------------------

    @property
    def _sessions(self) -> dict[str, dict]:
        return self._session_mgr._sessions

    @property
    def _messages(self) -> dict[str, list[dict]]:
        return self._session_mgr._messages

    @property
    def _session_locks(self) -> dict[str, asyncio.Lock]:
        return self._session_mgr._session_locks

    # ------------------------------------------------------------------
    # Session lifecycle — delegates to SessionManager
    # ------------------------------------------------------------------

    def create_session(
        self,
        provider: str = "api_vllm",
        thinking: bool = True,
        ui_mode: str = "api",
        user_id: str = "default",
    ) -> InteractSessionInfo:
        """Create a new interact session."""
        return self._session_mgr.create_session(provider, thinking, ui_mode, user_id)

    def get_session_info(self, session_id: str) -> Optional[InteractSessionInfo]:
        """Get session info."""
        validate_session_id(session_id)
        return self._session_mgr.get_session_info(session_id)

    def list_sessions(self, user_id: str | None = None) -> list[InteractSessionInfo]:
        """List all sessions."""
        return self._session_mgr.list_sessions(user_id)

    def delete_session(self, session_id: str) -> None:
        """Delete a session, its workspace, and cleanup."""
        validate_session_id(session_id)
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        # Remove workspace
        ws = self._get_session_workspace(session_id)
        if ws and ws.exists():
            shutil.rmtree(ws, ignore_errors=True)
            logger.info("[%s] Deleted workspace: %s", session_id, ws)
        # Delegate to session manager for memory cleanup
        self._session_mgr.delete_session(
            session_id,
            scheduler_cache=self._scheduler_cache,
            drafts=self._drafts,
            annotations=self._annotations,
        )

    def get_session_history(self, session_id: str) -> dict:
        """Return chat history for a session."""
        validate_session_id(session_id)
        ws = self._get_session_workspace(session_id)
        return self._session_mgr.get_session_history(session_id, workspace_path=ws)

    # ------------------------------------------------------------------
    # Conversation turns
    # ------------------------------------------------------------------

    async def send_turn(
        self, session_id: str, message: str
    ) -> InteractTurnResponse:
        """Send a teacher message and get agent response.

        Creates scheduler + gateway lazily, then delegates to
        ``DocScheduler.run_conversation_turn()``.
        """
        validate_session_id(session_id)
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        scheduler = self._get_scheduler(
            provider=session["provider"],
            thinking=session["thinking"],
        )

        # ── Scenario C: collect paper structure before outline generation ──
        # Broad requests such as "出一套数据结构期末卷" need one clarification
        # pass for question count and type mix before we ask GLM for an outline.
        outline_context = ""
        scenario_c_requirements = ""
        raw_message = message.strip()
        # Save first message as session title
        if session["turn_count"] == 0 and raw_message:
            session["title"] = raw_message[:60]
        ws = self._get_session_workspace(session_id)
        self._session_mgr._append_session_message(session_id, "teacher", raw_message, workspace_path=ws)

        pending = session.get("pending_clarification")
        if pending and pending.get("kind") == "scenario_c_structure":
            scenario_c_requirements = self._merge_scenario_c_requirements(
                str(pending.get("requirements", "")),
                raw_message,
            )
            if not self._has_scenario_c_structure(scenario_c_requirements):
                session["pending_clarification"] = {
                    "kind": "scenario_c_structure",
                    "requirements": scenario_c_requirements,
                }
                session["state"] = "collecting"
                session["scenario"] = "C"
                session["turn_count"] = int(session.get("turn_count", 0)) + 1
                # Persist updated clarification to disk
                self._session_mgr._persist_pending_clarification(
                    session_id, session["pending_clarification"], workspace_path=ws,
                )
                response_text = self._scenario_c_clarification_message(scenario_c_requirements)
                self._session_mgr._append_session_message(session_id, "agent", response_text, workspace_path=ws)
                return InteractTurnResponse(
                    response_text=response_text,
                    session_state=session["state"],
                    has_draft=False,
                    has_result=False,
                    files_written=[],
                )
            session.pop("pending_clarification", None)
            # Delete persisted clarification file
            self._session_mgr._clear_pending_clarification_file(session_id, workspace_path=ws)
        elif session["turn_count"] == 0 and self._needs_scenario_c_clarification(raw_message):
            session["pending_clarification"] = {
                "kind": "scenario_c_structure",
                "requirements": raw_message,
            }
            session["state"] = "collecting"
            session["scenario"] = "C"
            session["turn_count"] = 1
            # Persist clarification to disk
            self._session_mgr._persist_pending_clarification(
                session_id, session["pending_clarification"], workspace_path=ws,
            )
            response_text = self._scenario_c_clarification_message(raw_message)
            self._session_mgr._append_session_message(session_id, "agent", response_text, workspace_path=ws)
            return InteractTurnResponse(
                response_text=response_text,
                session_state=session["state"],
                has_draft=False,
                has_result=False,
                files_written=[],
            )

        should_prepare_scenario_c = bool(scenario_c_requirements) or (
            session["turn_count"] == 0 and self._looks_like_scenario_c(raw_message)
        )
        if should_prepare_scenario_c:
            outline_requirements = scenario_c_requirements or raw_message
            outline_context = await self._pregenerate_outline(outline_requirements)
            if outline_context:
                logger.info("[%s] Scenario C: pre-generated GLM outline (%d chars)",
                            session_id, len(outline_context))
                # Write outline to workspace for the agent to reference
                if ws:
                    compose_dir = ws / "compose"
                    compose_dir.mkdir(parents=True, exist_ok=True)
                    (compose_dir / "glm_outline.md").write_text(
                        outline_context, encoding="utf-8"
                    )

        revision_pending = self._annotation_requests_revision(session_id)
        if revision_pending:
            self._quarantine_result_files(session_id, reason="stale-before-revision")

        # Acquire per-session lock to prevent concurrent turn races
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            # Append GLM outline context to teacher message if pre-generated
            effective_message = message
            if revision_pending:
                effective_message = self._build_revision_turn_message(message)
            elif outline_context:
                outline_requirements = scenario_c_requirements or raw_message
                effective_message = (
                    f"{outline_requirements}\n\n"
                    f"═══ 系统预生成大纲（基于知识点图谱 + GLM-5.1）═══\n"
                    f"{outline_context}\n"
                    f"═══ 大纲结束 ═══\n\n"
                    f"请基于以上大纲生成自由组卷第一轮草案，文件头必须写 [SCENARIO: C]、"
                    f"[ROUND: 1]、[PHASE: knowledge]。第一轮只展示粗粒度考察范围，"
                    f"不要展开最终考察方式；每个题位还必须包含一个 `## Qn 题型` section，"
                    f"供教师确认或调整题型。大纲已写入 compose/glm_outline.md 供参考。"
                )

            result = await scheduler.run_conversation_turn(
                session_id=session_id,
                teacher_message=effective_message,
                role="interact",
            )

            response_text = result.get("response_text", "")
            files_written = result.get("files_written", [])

            # Extract scenario tag from response_text: [SCENARIO: A/B/C]
            _scenario_tag = None
            _scenario_match = re.search(r"\[SCENARIO:\s*([ABC])\]", response_text)
            if _scenario_match:
                _scenario_tag = _scenario_match.group(1)
                # Strip the tag from displayed text
                response_text = re.sub(r"\[SCENARIO:\s*[ABC]\]\s*", "", response_text).strip()
            # Also try reading scenario from draft file content
            if not _scenario_tag:
                if ws:
                    for rel in ("compose/interact_draft.md", "interact_draft.md"):
                        dp = self._safe_workspace_path(ws, rel)
                        if dp and dp.exists():
                            try:
                                head = dp.read_text(encoding="utf-8")[:200]
                                fm = re.search(r"\[SCENARIO:\s*([ABC])\]", head)
                                if fm:
                                    _scenario_tag = fm.group(1)
                                    break
                            except Exception:
                                pass
            if response_text.strip():
                self._session_mgr._append_session_message(session_id, "agent", response_text.strip(), workspace_path=ws)
            if _scenario_tag:
                session["scenario"] = _scenario_tag

            # Update session metadata from the scheduler's InteractSession
            interact_session = scheduler._interact_sessions.get(session_id)
            if interact_session:
                session["state"] = interact_session.status
                if session.get("scenario") in ("unknown", "") and interact_session.scenario not in ("unknown", ""):
                    session["scenario"] = interact_session.scenario
                session["turn_count"] = interact_session.turn_count

        if revision_pending:
            self._quarantine_result_files(session_id, reason="blocked-by-revision")
        has_result = self._find_result_path(session_id) is not None

        # Prefer draft files written by the agent; fall back to response text.
        has_draft = False
        draft = self._load_draft_from_files(
            session_id,
            files_written,
            allow_fallback=not revision_pending,
        )
        if draft:
            self._drafts[session_id] = draft
            self._annotations.pop(session_id, None)
            has_draft = True
        elif _detect_draft:
            has_draft = _detect_draft(response_text)
            if has_draft and _parse_draft:
                try:
                    draft = _parse_draft(
                        response_text,
                        draft_id=f"{session_id}_turn{session['turn_count']}",
                    )
                    self._drafts[session_id] = draft
                    self._annotations.pop(session_id, None)
                except Exception:
                    logger.warning(
                        "[%s] Draft parsing failed, skipping", session_id
                    )
                    has_draft = False

        if has_result:
            session["state"] = "confirmed"
            # Auto-trigger question generation pipeline
            self._trigger_generation(session_id, session)
        elif revision_pending:
            session["state"] = "reviewing"
        elif has_draft and session.get("state") == "collecting":
            session["state"] = "reviewing"

        return InteractTurnResponse(
            response_text=response_text,
            session_state=session["state"],
            has_draft=has_draft,
            has_result=has_result,
            files_written=files_written,
        )

    # ------------------------------------------------------------------
    # Pipeline trigger
    # ------------------------------------------------------------------

    def _trigger_generation(self, session_id: str, session: dict) -> None:
        """Fire-and-forget question generation from handoff YAML."""
        from api.services.pipeline_trigger import get_job, mark_job_failed, trigger_generation

        # Skip if a non-setup-failed job already exists for this result.
        existing_job = get_job(session_id)
        if existing_job and not existing_job.error:
            logger.info("[%s] Pipeline already recorded (%s), skip", session_id, existing_job.status)
            return

        ws = self._get_session_workspace(session_id)
        if not ws:
            logger.warning("[%s] No workspace, cannot trigger pipeline", session_id)
            return

        # Find handoff YAML
        result_path = self._find_result_path(session_id)
        if not result_path:
            logger.warning("[%s] No handoff YAML found", session_id)
            return

        logger.info("[%s] Triggering generation from %s", session_id, result_path)

        async def _run() -> None:
            try:
                await trigger_generation(
                    session_id=session_id,
                    handoff_yaml_path=result_path,
                    workspace=ws,
                    provider="glm5.1",
                )
            except Exception as exc:
                logger.exception("[%s] Pipeline generation failed", session_id)
                mark_job_failed(session_id, str(exc))

        # Fire-and-forget as background task
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.create_task(_run())
        else:
            logger.warning("[%s] No running event loop for pipeline trigger", session_id)

    def get_pipeline_progress(self, session_id: str) -> dict | None:
        """Return pipeline generation progress for a session."""
        validate_session_id(session_id)
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")
        from api.services.pipeline_trigger import get_job
        job = get_job(session_id)
        return job.to_dict() if job else None

    # ------------------------------------------------------------------
    # Scenario C: backward-compat delegates to ClarificationHandler
    # ------------------------------------------------------------------

    @classmethod
    def _needs_scenario_c_clarification(cls, message: str) -> bool:
        return ClarificationHandler.needs_clarification(message)

    @staticmethod
    def _looks_like_scenario_c(message: str) -> bool:
        return ClarificationHandler.looks_like_scenario_c(message)

    @staticmethod
    def _has_scenario_c_structure(message: str) -> bool:
        return ClarificationHandler.has_structure(message)

    @staticmethod
    def _merge_scenario_c_requirements(previous: str, latest: str) -> str:
        return ClarificationHandler.merge_requirements(previous, latest)

    @staticmethod
    def _scenario_c_clarification_message(requirements: str) -> str:
        return ClarificationHandler.clarification_message(requirements)

    @staticmethod
    async def _pregenerate_outline(user_requirements: str) -> str:
        return await ClarificationHandler.pregenerate_outline(user_requirements)

    # ------------------------------------------------------------------
    # Draft & annotation
    # ------------------------------------------------------------------

    def get_draft(self, session_id: str) -> Optional[DraftData]:
        """Get the latest parsed draft for a session."""
        validate_session_id(session_id)
        return self._drafts.get(session_id)

    def submit_annotation(
        self, session_id: str, annotation: AnnotationSubmission
    ) -> bool:
        """Submit pruning annotation.

        Converts to annotated MD and writes to
        ``compose/interact_draft.md`` so the scheduler can read it on
        the next turn.
        """
        validate_session_id(session_id)
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        draft = self._drafts.get(session_id)
        if not draft:
            return False

        if annotation.draft_id != draft.draft_id:
            raise ValueError(
                f"Draft ID mismatch: got {annotation.draft_id!r}, expected {draft.draft_id!r}"
            )

        if not _render_annotated:
            logger.error("draft_parser not available, cannot render annotation")
            return False

        annotated_md = _render_annotated(draft, annotation)
        self._annotations[session_id] = annotation
        revision_requested = self._annotation_payload_requests_revision(annotation)

        # Write to workspace draft path
        scheduler = self._get_scheduler(
            provider=session["provider"],
            thinking=session["thinking"],
        )
        # Scheduler workspace for session: scheduler.workspace / session_id
        # Agent writes to compose/interact_draft.md within that workspace
        draft_path = Path(scheduler.workspace) / session_id / "compose" / "interact_draft.md"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(annotated_md, encoding="utf-8")
        session["state"] = "reviewing"
        self._quarantine_result_files(
            session_id,
            reason="annotation-revision" if revision_requested else "annotation-selection",
        )
        selected_count = sum(
            1
            for item in annotation.slots
            if item.selected_option_id or item.kept_options
        )
        ws = self._get_session_workspace(session_id)
        if revision_requested:
            self._session_mgr._append_session_message(
                session_id,
                "teacher",
                "已提交草案批注，请先修订方案。",
                workspace_path=ws,
            )
        elif selected_count:
            self._session_mgr._append_session_message(
                session_id,
                "teacher",
                f"已提交草案选择，共确认 {selected_count} 项。",
                workspace_path=ws,
            )
        else:
            self._session_mgr._append_session_message(
                session_id, "teacher", "已提交草案选择。", workspace_path=ws,
            )
        logger.info("[%s] Annotation written to %s", session_id, draft_path)
        return True

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    def get_result(self, session_id: str) -> Optional[dict]:
        """Get the parsed YAML result for a session."""
        validate_session_id(session_id)
        session = self._sessions.get(session_id)
        if not session:
            return None

        p = self._find_result_path(session_id)
        if p:
            logger.info("[%s] Found result YAML: %s", session_id, p)
            if _parse_yaml:
                return _parse_yaml(str(p))
            # Fallback: parse YAML ourselves
            try:
                import yaml
                return yaml.safe_load(p.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    # ------------------------------------------------------------------
    # Annotation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _annotation_payload_requests_revision(annotation: AnnotationSubmission) -> bool:
        """Return True when an annotation asks for plan revision, not just selection."""
        for slot in annotation.slots:
            if (slot.annotation or "").strip():
                return True
            if any(str(value).strip() for value in slot.modified_text.values()):
                return True
        return False

    def _annotation_requests_revision(self, session_id: str) -> bool:
        """Return True if the latest annotated draft contains teacher comments."""
        annotation = self._annotations.get(session_id)
        if annotation and self._annotation_payload_requests_revision(annotation):
            return True

        ws = self._get_session_workspace(session_id)
        if ws is None:
            return False
        draft_path = self._safe_workspace_path(ws, "compose/interact_draft.md")
        if not draft_path or not draft_path.exists():
            return False
        try:
            text = draft_path.read_text(encoding="utf-8")
        except Exception:
            return False
        return bool(re.search(r"^>\s*教师批注[:：]\s*\S+", text, re.MULTILINE))

    @staticmethod
    def _build_revision_turn_message(message: str) -> str:
        """Wrap a client turn so annotated drafts cannot accidentally enter handoff."""
        return (
            f"{message.strip()}\n\n"
            "【系统约束：当前草案含教师批注】\n"
            "必须先读取 compose/interact_draft.md，并逐条处理 `> 教师批注:`。\n"
            "本轮唯一允许的产物是修订后的 compose/interact_draft.md；"
            "请重新 write_file 到该路径，并等待教师再次确认。\n"
            "禁止生成 paper_request.yaml、slot_blueprint.yaml 或 retrieval_query.yaml；"
            "禁止进入出题流水线。"
        )

    def get_latest_annotation(self, session_id: str) -> AnnotationSubmission | None:
        """Return the latest draft annotation for a session."""
        validate_session_id(session_id)
        return self._annotations.get(session_id)

    def get_session_workspace(self, session_id: str) -> Path | None:
        """Return the session workspace path for result aggregation."""
        validate_session_id(session_id)
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        cache_key = f"{session['provider']}_{session['thinking']}"
        scheduler = self._scheduler_cache.get(cache_key)
        if scheduler is not None:
            return Path(scheduler.workspace) / session_id
        for cached_scheduler in self._scheduler_cache.values():
            workspace = getattr(cached_scheduler, "workspace", None)
            if not workspace:
                continue
            candidate = Path(workspace) / session_id
            if candidate.exists():
                return candidate
        return Path("workspace").resolve() / session_id

    # ------------------------------------------------------------------
    # Scheduler factory
    # ------------------------------------------------------------------

    def _get_scheduler(self, provider: str, thinking: bool):
        """Get or create a DocScheduler for the given provider.

        Follows the same pattern as ``scripts/test_interact_cli.py``:
        ``get_gateway(provider)`` creates the gateway, then
        ``DocScheduler(gateway, ...)`` creates the scheduler.
        """
        cache_key = f"{provider}_{thinking}"
        if cache_key not in self._scheduler_cache:
            from core_new.llm_gateway import get_gateway
            from core_new.doc_pipeline.scheduler import DocScheduler

            gateway = get_gateway(provider)
            scheduler = DocScheduler(
                gateway,
                workspace="workspace",
                enable_thinking=thinking,
                model_routing={"_default": provider},
            )
            self._scheduler_cache[cache_key] = scheduler
        return self._scheduler_cache[cache_key]

    # ------------------------------------------------------------------
    # Workspace helpers
    # ------------------------------------------------------------------

    def _get_session_workspace(self, session_id: str) -> Path | None:
        """Return the scheduler workspace directory for a session."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        scheduler = self._get_scheduler(
            provider=session["provider"],
            thinking=session["thinking"],
        )
        return Path(scheduler.workspace) / session_id

    @staticmethod
    def _safe_workspace_path(ws: Path, rel_path: str) -> Path | None:
        """Resolve a relative tool path under a session workspace."""
        clean = rel_path.lstrip("/").lstrip("\\")
        path = (ws / clean).resolve()
        try:
            path.relative_to(ws.resolve())
        except ValueError:
            return None
        return path

    def _load_draft_from_files(
        self,
        session_id: str,
        files_written: list[str],
        allow_fallback: bool = True,
    ) -> DraftData | None:
        """Load a parseable draft from files written by the agent."""
        if not _parse_draft:
            return None

        session = self._sessions.get(session_id)
        ws = self._get_session_workspace(session_id)
        if not session or ws is None:
            return None

        candidates: list[Path] = []
        for rel in files_written:
            if not rel.endswith(".md"):
                continue
            if "interact_draft" not in rel and "interact_response" not in rel:
                continue
            path = self._safe_workspace_path(ws, rel)
            if path:
                candidates.append(path)

        if allow_fallback:
            for rel in (
                "compose/interact_draft.md",
                "interact_draft.md",
                "interact_response.md",
            ):
                path = self._safe_workspace_path(ws, rel)
                if path:
                    candidates.append(path)

        seen: set[Path] = set()
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            if not path.exists() or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
                if not text.strip():
                    continue
                draft = _parse_draft(
                    text,
                    draft_id=f"{session_id}_turn{session['turn_count']}",
                )
                if draft.sections:
                    return draft
            except Exception:
                logger.warning("[%s] Failed to parse draft file %s", session_id, path)
        return None

    def _result_file_candidates(self, session_id: str) -> list[Path]:
        """Return candidate handoff YAML paths under a session workspace."""
        ws = self._get_session_workspace(session_id)
        if ws is None:
            return []

        candidates: list[Path] = []
        for name in _HANDOFF_YAML_NAMES:
            for rel in (name, f"compose/{name}"):
                path = self._safe_workspace_path(ws, rel)
                if path:
                    candidates.append(path)

        if ws.exists():
            candidates.extend(
                path for path in ws.rglob("*.yaml")
                if path.name in _HANDOFF_YAML_NAMES and path.is_file()
            )

        seen: set[Path] = set()
        unique: list[Path] = []
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            unique.append(path)
        return unique

    def _quarantine_result_files(self, session_id: str, reason: str) -> None:
        """Move stale handoff YAMLs aside while a teacher revision is pending."""
        timestamp = int(time.time())
        for path in self._result_file_candidates(session_id):
            if not path.exists() or not path.is_file():
                continue
            target = path.with_name(f"{path.name}.blocked.{reason}.{timestamp}")
            suffix = 1
            while target.exists():
                target = path.with_name(f"{path.name}.blocked.{reason}.{timestamp}.{suffix}")
                suffix += 1
            try:
                path.rename(target)
                logger.info("[%s] Quarantined stale handoff %s -> %s", session_id, path, target)
            except Exception:
                logger.warning("[%s] Failed to quarantine stale handoff: %s", session_id, path)

    def _find_result_path(self, session_id: str) -> Path | None:
        """Find a handoff YAML result in the session workspace."""
        for path in self._result_file_candidates(session_id):
            if path.exists() and path.is_file():
                return path
        return None
