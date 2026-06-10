"""Service layer for V2 interact API.

Wraps core_new.doc_pipeline.scheduler for web consumption.
Scheduler is zero-change; this layer does MD<->JSON conversion and
session lifecycle management.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Optional

from api.schemas_interact_v2 import (
    AnnotationSubmission,
    DraftData,
    InteractSessionInfo,
    InteractTurnResponse,
)

logger = logging.getLogger(__name__)

# Session ID validation — must be hex string from uuid4
_RE_SESSION_ID = re.compile(r"^[a-f0-9]{12}$")


def validate_session_id(sid: str) -> str:
    """Validate session ID format to prevent path traversal."""
    if not _RE_SESSION_ID.match(sid):
        raise ValueError(f"Invalid session ID format: {sid!r}")
    return sid


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
    """

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}  # session_id -> metadata
        self._drafts: dict[str, DraftData] = {}  # session_id -> latest draft
        self._scheduler_cache: dict[str, object] = {}  # cache_key -> DocScheduler
        self._session_locks: dict[str, asyncio.Lock] = {}  # session_id -> lock

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(
        self,
        provider: str = "api_vllm",
        thinking: bool = False,
        ui_mode: str = "api",
    ) -> InteractSessionInfo:
        """Create a new interact session."""
        session_id = uuid.uuid4().hex[:12]
        self._sessions[session_id] = {
            "session_id": session_id,
            "provider": provider,
            "thinking": thinking,
            "ui_mode": ui_mode,
            "state": "collecting",
            "scenario": "unknown",
            "created_at": time.time(),
            "turn_count": 0,
        }
        return InteractSessionInfo(
            session_id=session_id,
            state="collecting",
            scenario="unknown",
            provider=provider,
            created_at=self._sessions[session_id]["created_at"],
            turn_count=0,
        )

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

        # Acquire per-session lock to prevent concurrent turn races
        lock = self._session_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            result = await scheduler.run_conversation_turn(
                session_id=session_id,
                teacher_message=message,
                role="interact",
            )

            response_text = result.get("response_text", "")
            files_written = result.get("files_written", [])

            # Update session metadata from the scheduler's InteractSession
            interact_session = scheduler._interact_sessions.get(session_id)
            if interact_session:
                session["state"] = interact_session.status
                session["scenario"] = interact_session.scenario
                session["turn_count"] = interact_session.turn_count

        has_result = self._find_result_path(session_id) is not None

        # Prefer draft files written by the agent; fall back to response text.
        has_draft = False
        draft = self._load_draft_from_files(session_id, files_written)
        if draft:
            self._drafts[session_id] = draft
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
                except Exception:
                    logger.warning(
                        "[%s] Draft parsing failed, skipping", session_id
                    )
                    has_draft = False

        if has_result:
            session["state"] = "confirmed"
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
    # Session info
    # ------------------------------------------------------------------

    def get_session_info(self, session_id: str) -> Optional[InteractSessionInfo]:
        """Get session info."""
        validate_session_id(session_id)
        session = self._sessions.get(session_id)
        if not session:
            return None
        return InteractSessionInfo(
            session_id=session["session_id"],
            state=session["state"],
            scenario=session["scenario"],
            provider=session["provider"],
            created_at=session["created_at"],
            turn_count=session["turn_count"],
        )

    def list_sessions(self) -> list[InteractSessionInfo]:
        """List all sessions."""
        return [
            info for sid in self._sessions
            if (info := self.get_session_info(sid)) is not None
        ]

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

    def _find_result_path(self, session_id: str) -> Path | None:
        """Find a handoff YAML result in the session workspace."""
        ws = self._get_session_workspace(session_id)
        if ws is None:
            return None

        names = ("slot_blueprint.yaml", "paper_request.yaml", "retrieval_query.yaml")
        candidates: list[Path] = []
        for name in names:
            for rel in (name, f"compose/{name}"):
                path = self._safe_workspace_path(ws, rel)
                if path:
                    candidates.append(path)

        for path in candidates:
            if path.exists() and path.is_file():
                return path

        if not ws.exists():
            return None
        for path in ws.rglob("*.yaml"):
            if path.name in names and path.is_file():
                return path
        return None
