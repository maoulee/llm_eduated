"""Session lifecycle, message persistence, and workspace management.

Extracted from InteractV2Service to keep the service layer focused on
orchestration while this module handles session CRUD and chat history.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Optional

from api.schemas_interact_v2 import InteractSessionInfo

logger = logging.getLogger(__name__)

_RE_SESSION_ID = re.compile(r"^[a-f0-9]{12}$")
_RE_USER_ID_SAFE = re.compile(r"[^0-9A-Za-z_.@-]+")


def validate_session_id(sid: str) -> str:
    """Validate session ID format to prevent path traversal."""
    if not _RE_SESSION_ID.match(sid):
        raise ValueError(f"Invalid session ID format: {sid!r}")
    return sid


def _normalize_user_id(user_id: str | None) -> str:
    """Normalize a tester/user namespace for session isolation."""
    cleaned = _RE_USER_ID_SAFE.sub("_", (user_id or "default").strip())
    cleaned = cleaned.strip("._-")[:64]
    return cleaned or "default"


class SessionManager:
    """Session lifecycle, message persistence, and workspace management."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}  # session_id -> metadata
        self._messages: dict[str, list[dict]] = {}  # session_id -> chat messages
        self._session_locks: dict[str, asyncio.Lock] = {}  # session_id -> lock

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def _restore_sessions_from_disk(self, workspace_root: Path | None = None) -> None:
        """Scan workspace directory and restore sessions from disk.

        Args:
            workspace_root: Override the default "workspace" directory path.
                Used by InteractV2Service to pass a mocked path for testing.
        """
        workspace = workspace_root or Path("workspace")
        if not workspace.is_dir():
            return

        for d in sorted(workspace.iterdir()):
            if not d.is_dir():
                continue
            sid = d.name
            # Validate session ID format (hex, 12 chars)
            if not _RE_SESSION_ID.match(sid):
                continue

            # Determine state by checking what files exist
            has_questions = (d / "questions").is_dir()
            has_compose = (d / "compose").is_dir()
            has_blueprint = False
            has_draft = False
            scenario = "unknown"

            if has_compose:
                for bp_name in ("slot_blueprint.yaml", "paper_request.yaml"):
                    bp = d / "compose" / bp_name
                    if bp.exists():
                        has_blueprint = True
                        break
                draft = d / "compose" / "interact_draft.md"
                if draft.exists():
                    has_draft = True
                    # Try to read scenario from draft
                    try:
                        head = draft.read_text(encoding="utf-8")[:200]
                        fm = re.search(r"\[SCENARIO:\s*([ABC])\]", head)
                        if fm:
                            scenario = fm.group(1)
                    except Exception:
                        pass
                # If no scenario from draft, check pending clarification
                if scenario == "unknown":
                    pc_file = d / "compose" / "pending_clarification.json"
                    if pc_file.exists():
                        try:
                            pc = json.loads(pc_file.read_text(encoding="utf-8"))
                            if isinstance(pc, dict) and pc.get("kind") == "scenario_c_structure":
                                scenario = "C"
                        except Exception:
                            pass

            if has_questions:
                state = "completed"
            elif has_blueprint:
                state = "confirmed"
            elif has_draft:
                state = "reviewing"
            else:
                state = "collecting"

            self._sessions[sid] = {
                "session_id": sid,
                "provider": "api_vllm",
                "thinking": False,
                "ui_mode": "api",
                "user_id": "default",
                "state": state,
                "scenario": scenario,
                "created_at": d.stat().st_ctime,
                "turn_count": 0,
            }
            # Restore pending clarification for Scenario C if persisted
            if state == "collecting" and scenario == "C":
                pc_path = d / "compose" / "pending_clarification.json"
                if pc_path.exists():
                    try:
                        pc_data = json.loads(pc_path.read_text(encoding="utf-8"))
                        if isinstance(pc_data, dict) and pc_data.get("kind") == "scenario_c_structure":
                            self._sessions[sid]["pending_clarification"] = pc_data
                            self._sessions[sid]["turn_count"] = 1
                    except Exception:
                        pass
            logger.info("Restored session %s (state=%s, scenario=%s)", sid, state, scenario)

    def create_session(
        self,
        provider: str = "api_vllm",
        thinking: bool = True,
        ui_mode: str = "api",
        user_id: str = "default",
    ) -> InteractSessionInfo:
        """Create a new interact session."""
        session_id = uuid.uuid4().hex[:12]
        normalized_user_id = _normalize_user_id(user_id)
        self._sessions[session_id] = {
            "session_id": session_id,
            "provider": provider,
            "thinking": thinking,
            "ui_mode": ui_mode,
            "user_id": normalized_user_id,
            "state": "collecting",
            "scenario": "unknown",
            "title": "",
            "created_at": time.time(),
            "turn_count": 0,
        }
        return InteractSessionInfo(
            session_id=session_id,
            state="collecting",
            scenario="unknown",
            provider=provider,
            thinking=thinking,
            user_id=normalized_user_id,
            title="",
            created_at=self._sessions[session_id]["created_at"],
            turn_count=0,
        )

    def get_session_info(self, session_id: str) -> Optional[InteractSessionInfo]:
        """Get session info."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        return InteractSessionInfo(
            session_id=session["session_id"],
            state=session["state"],
            scenario=session["scenario"],
            provider=session["provider"],
            thinking=session.get("thinking", False),
            user_id=session.get("user_id", "default"),
            title=self._display_session_title(session_id, session),
            created_at=session["created_at"],
            turn_count=session["turn_count"],
        )

    def list_sessions(self, user_id: str | None = None) -> list[InteractSessionInfo]:
        """List all sessions."""
        normalized_user_id = _normalize_user_id(user_id) if user_id else None
        infos: list[InteractSessionInfo] = []
        for sid, session in self._sessions.items():
            if normalized_user_id and session.get("user_id", "default") != normalized_user_id:
                continue
            info = self.get_session_info(sid)
            if info is not None:
                infos.append(info)
        return infos

    def delete_session(
        self,
        session_id: str,
        scheduler_cache: dict | None = None,
        drafts: dict | None = None,
        annotations: dict | None = None,
    ) -> None:
        """Delete a session's in-memory state and cleanup scheduler.

        Args:
            session_id: The session to delete.
            scheduler_cache: The service's _scheduler_cache, used to clean up
                the scheduler's internal session state.
            drafts: The service's _drafts dict, to remove draft state.
            annotations: The service's _annotations dict, to remove annotation state.
        """
        validate_session_id(session_id)
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Cleanup scheduler session
        if scheduler_cache:
            cache_key = f"{session['provider']}_{session['thinking']}"
            scheduler = scheduler_cache.get(cache_key)
            if scheduler and session_id in scheduler._interact_sessions:
                del scheduler._interact_sessions[session_id]

        # Remove from memory
        self._sessions.pop(session_id, None)
        self._messages.pop(session_id, None)
        self._session_locks.pop(session_id, None)
        if drafts is not None:
            drafts.pop(session_id, None)
        if annotations is not None:
            annotations.pop(session_id, None)
        logger.info("[%s] Session deleted", session_id)

    def get_session_history(
        self,
        session_id: str,
        workspace_path: Path | None = None,
    ) -> dict:
        """Return chat history for a session.

        Args:
            session_id: The session to get history for.
            workspace_path: The session workspace path, resolved by the service.
        """
        validate_session_id(session_id)
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Try loading messages from disk if not yet cached
        logged_messages = self._load_session_messages(session_id, workspace_path)
        if logged_messages:
            return {
                "session_id": session_id,
                "title": self._display_session_title(session_id, session),
                "state": session["state"],
                "scenario": session.get("scenario", "unknown"),
                "user_id": session.get("user_id", "default"),
                "messages": logged_messages,
            }

        ws = workspace_path
        messages = []

        # 1. Teacher's initial message (from title, or reconstruct from files)
        teacher_msg = session.get("title", "")
        if not teacher_msg and ws:
            # Try to reconstruct from blueprint/draft
            bp_path = ws / "compose" / "slot_blueprint.yaml"
            if bp_path.exists():
                try:
                    import yaml
                    bp = yaml.safe_load(bp_path.read_text(encoding="utf-8"))
                    if isinstance(bp, dict):
                        target = bp.get("primary_target_name", "")
                        mode = bp.get("examination_mode", "")
                        if target:
                            teacher_msg = f"出一道{target}的题目" + (f"（{mode}）" if mode else "")
                except Exception:
                    pass
        if teacher_msg:
            messages.append({
                "role": "teacher",
                "content": teacher_msg,
            })

        # 2. Agent draft response
        if ws:
            draft_path = ws / "compose" / "interact_draft.md"
            response_path = ws / "compose" / "interact_response.md"

            if response_path.exists():
                try:
                    resp_text = response_path.read_text(encoding="utf-8")
                    messages.append({
                        "role": "agent",
                        "content": resp_text[:2000],
                    })
                except Exception:
                    pass
            elif draft_path.exists():
                try:
                    draft_text = draft_path.read_text(encoding="utf-8")
                    messages.append({
                        "role": "agent",
                        "content": "草案已生成：\n" + draft_text[:2000],
                    })
                except Exception:
                    pass

        # 3. Generation result
        if session["state"] == "completed":
            messages.append({
                "role": "agent",
                "content": "题目已全部生成完成。你可以在右侧查看题目或预览整卷。",
            })
        elif session["state"] == "confirmed":
            messages.append({
                "role": "agent",
                "content": "已确认选择，出题流水线已启动。",
            })
        elif session["state"] == "generating":
            messages.append({
                "role": "agent",
                "content": "出题流水线正在运行中…",
            })

        return {
            "session_id": session_id,
            "title": self._display_session_title(session_id, session),
            "state": session["state"],
            "scenario": session.get("scenario", "unknown"),
            "user_id": session.get("user_id", "default"),
            "messages": messages,
        }

    # ------------------------------------------------------------------
    # Message persistence
    # ------------------------------------------------------------------

    def _display_session_title(self, session_id: str, session: dict) -> str:
        title = (session.get("title") or "").strip()
        if title:
            return title
        messages = self._load_session_messages(session_id)
        for msg in messages:
            if msg.get("role") == "teacher" and msg.get("content"):
                return str(msg["content"])[:60]
        scenario = session.get("scenario", "unknown")
        if scenario in ("A", "B", "C"):
            return {"A": "408组卷", "B": "知识点出题", "C": "自由组卷"}[scenario]
        created = session.get("created_at")
        if created:
            return time.strftime("任务 %m-%d %H:%M", time.localtime(float(created)))
        return "未命名任务"

    def _load_session_messages(
        self,
        session_id: str,
        workspace_path: Path | None = None,
    ) -> list[dict]:
        """Load session messages from in-memory cache, or from disk if a workspace path is given."""
        cached = self._messages.get(session_id)
        if cached is not None:
            return cached

        # Try loading from disk if workspace_path available
        if workspace_path is not None:
            path = workspace_path / "compose" / "session_messages.json"
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        messages = [
                            {
                                "role": str(item.get("role", "")),
                                "content": str(item.get("content", "")),
                                "created_at": float(item.get("created_at", 0) or 0),
                            }
                            for item in data
                            if isinstance(item, dict) and item.get("role") and item.get("content")
                        ]
                        self._messages[session_id] = messages
                        return messages
                except Exception:
                    logger.warning("[%s] Failed to load session message log: %s", session_id, path)

        self._messages[session_id] = []
        return self._messages[session_id]

    def _append_session_message(
        self,
        session_id: str,
        role: str,
        content: str,
        workspace_path: Path | None = None,
    ) -> None:
        content = (content or "").strip()
        if not content:
            return

        messages = self._load_session_messages(session_id, workspace_path)
        if messages and messages[-1].get("role") == role and messages[-1].get("content") == content:
            return

        messages.append({"role": role, "content": content, "created_at": time.time()})

        if workspace_path is None:
            return
        path = workspace_path / "compose" / "session_messages.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(messages, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.warning("[%s] Failed to persist session message log: %s", session_id, path)

    def _persist_pending_clarification(
        self,
        session_id: str,
        clarification: dict,
        workspace_path: Path | None = None,
    ) -> None:
        """Persist pending clarification state to disk."""
        if workspace_path is None:
            return
        path = workspace_path / "compose" / "pending_clarification.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(clarification, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.warning("[%s] Failed to persist clarification: %s", session_id, path)

    def _clear_pending_clarification_file(
        self,
        session_id: str,
        workspace_path: Path | None = None,
    ) -> None:
        """Delete the persisted pending clarification JSON file."""
        if workspace_path is None:
            return
        pc_path = workspace_path / "compose" / "pending_clarification.json"
        if pc_path.exists():
            try:
                pc_path.unlink()
            except Exception:
                pass
