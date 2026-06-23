"""SQLite-based session persistence layer."""

import json
import os
import sqlite3
import time
from typing import Optional

from interact.session_manager import SessionData, SessionState


class SessionStore:
    """SQLite-based persistent store for session data."""

    def __init__(self, db_path: str = "data/sessions.db") -> None:
        """Initialize the session store.

        Args:
            db_path: Path to the SQLite database file.
        """
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize the database schema."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at REAL,
                updated_at REAL
            )
        """)
        self.conn.commit()

    def save(self, session: SessionData) -> None:
        """Save a session to the database.

        Args:
            session: The session data to save.
        """
        data = {
            "session_id": session.session_id,
            "state": session.state.value,
            "mode": session.mode,
            "collected_params": session.collected_params,
            "blueprint_id": session.blueprint_id,
            "blueprint_md": session.blueprint_md,
            "annotation_round": session.annotation_round,
            "generation_results": session.generation_results,
            "error_message": session.error_message,
            "pending_candidates": session.pending_candidates,
        }
        now = time.time()
        self.conn.execute(
            """INSERT OR REPLACE INTO sessions
               (session_id, data, created_at, updated_at)
               VALUES (?, ?, COALESCE((SELECT created_at FROM sessions WHERE session_id=?), ?), ?)""",
            (session.session_id, json.dumps(data, ensure_ascii=False),
             session.session_id, now, now),
        )
        self.conn.commit()

    def load(self, session_id: str) -> Optional[SessionData]:
        """Load a session from the database.

        Args:
            session_id: The session ID to load.

        Returns:
            The session data if found, None otherwise.
        """
        row = self.conn.execute(
            "SELECT data FROM sessions WHERE session_id = ?",
            (session_id,)
        ).fetchone()
        if not row:
            return None

        data = json.loads(row[0])
        return SessionData(
            session_id=data["session_id"],
            state=SessionState(data["state"]),
            mode=data.get("mode", ""),
            collected_params=data.get("collected_params", {}),
            blueprint_id=data.get("blueprint_id", ""),
            blueprint_md=data.get("blueprint_md", ""),
            annotation_round=data.get("annotation_round", 0),
            generation_results=data.get("generation_results", []),
            error_message=data.get("error_message", ""),
            pending_candidates=data.get("pending_candidates", []),
        )

    def list_sessions(self) -> list[dict]:
        """List all sessions in the database.

        Returns:
            A list of session dictionaries with basic info.
        """
        rows = self.conn.execute(
            "SELECT session_id, data, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()

        results = []
        for sid, data_json, created, updated in rows:
            data = json.loads(data_json)
            results.append({
                "session_id": sid,
                "state": data.get("state", "idle"),
                "mode": data.get("mode", ""),
                "created_at": created,
                "updated_at": updated,
            })
        return results

    def delete(self, session_id: str) -> None:
        """Delete a session from the database.

        Args:
            session_id: The session ID to delete.
        """
        self.conn.execute(
            "DELETE FROM sessions WHERE session_id = ?",
            (session_id,)
        )
        self.conn.commit()
