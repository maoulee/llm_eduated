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

from api.schemas.interact_v2 import (
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

        # Detect draft in response
        has_draft = False
        if _detect_draft:
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

        # Check for result YAML files
        has_result = False
        if interact_session:
            for f in files_written:
                if f.endswith((".yaml", ".yml")) and (
                    "paper_request" in f or "slot_blueprint" in f
                ):
                    has_result = True
                    break

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
        draft = self._drafts.get(session_id)
        if not draft:
            return False

        if not _render_annotated:
            logger.error("draft_parser not available, cannot render annotation")
            return False

        annotated_md = _render_annotated(draft, annotation)

        # Write to workspace draft path
        session = self._sessions.get(session_id)
        if not session:
            return False

        scheduler = self._get_scheduler(
            provider=session["provider"],
            thinking=session["thinking"],
        )
        # Scheduler workspace for session: scheduler.workspace / session_id
        # Agent writes to compose/interact_draft.md within that workspace
        draft_path = Path(scheduler.workspace) / session_id / "compose" / "interact_draft.md"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(annotated_md, encoding="utf-8")
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

        scheduler = self._get_scheduler(
            provider=session["provider"],
            thinking=session["thinking"],
        )
        # Scheduler workspace for this session
        ws = Path(scheduler.workspace) / session_id

        # Try common YAML filenames the agent writes
        for yaml_name in ["slot_blueprint.yaml", "paper_request.yaml"]:
            p = ws / yaml_name
            if p.exists():
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
