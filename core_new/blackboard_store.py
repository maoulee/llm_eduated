"""SQLite persistence for Blackboard state."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
from typing import Dict, List, Optional

from config import DATA_DIR_PATH

from .blackboard import Blackboard


class BlackboardStore:
    """SQLite-backed persistence for Blackboard state."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(DATA_DIR_PATH, "blackboard.db")
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    raw_md TEXT NOT NULL DEFAULT '',
                    state_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS state_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    raw_md TEXT NOT NULL DEFAULT '',
                    state_json TEXT NOT NULL,
                    timestamp REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agent_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    status TEXT NOT NULL,
                    tokens_used INTEGER NOT NULL DEFAULT 0,
                    latency_s REAL NOT NULL DEFAULT 0,
                    error TEXT,
                    output_md TEXT NOT NULL DEFAULT '',
                    timestamp REAL NOT NULL,
                    record_json TEXT NOT NULL
                );
                """
            )
        self._ensure_column("tasks", "raw_md", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("state_versions", "raw_md", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("agent_logs", "output_md", "TEXT NOT NULL DEFAULT ''")

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        with self._connect() as conn:
            columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if column not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    async def save(self, blackboard: Blackboard) -> None:
        await asyncio.to_thread(self._save_sync, blackboard)

    def _save_sync(self, blackboard: Blackboard) -> None:
        data = blackboard.to_dict()
        now = time.time()
        state_json = json.dumps(data, ensure_ascii=False, default=str)
        raw_md = blackboard.to_markdown()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks(task_id, task_type, status, created_at, updated_at, raw_md, state_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    task_type=excluded.task_type,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    raw_md=excluded.raw_md,
                    state_json=excluded.state_json
                """,
                (
                    blackboard.task_id,
                    blackboard.task_type,
                    blackboard.status,
                    data["created_at"],
                    data["updated_at"],
                    raw_md,
                    state_json,
                ),
            )
            last_record = data["history"][-1] if data["history"] else {}
            conn.execute(
                """
                INSERT INTO state_versions(task_id, agent_name, phase, version, raw_md, state_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    blackboard.task_id,
                    last_record.get("agent_name", data["raw"].get("_last_agent", "snapshot")),
                    last_record.get("phase", data["raw"].get("_last_phase", "snapshot")),
                    data["version"],
                    str(last_record.get("output", "") or ""),
                    state_json,
                    now,
                ),
            )
            conn.execute("DELETE FROM agent_logs WHERE task_id = ?", (blackboard.task_id,))
            for record in data["history"]:
                conn.execute(
                    """
                    INSERT INTO agent_logs(
                        task_id, agent_name, phase, status, tokens_used,
                        latency_s, error, output_md, timestamp, record_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        blackboard.task_id,
                        record["agent_name"],
                        record["phase"],
                        record["status"],
                        int(record.get("tokens_used", 0)),
                        float(record.get("latency_s", 0.0)),
                        record.get("error"),
                        str(record.get("output", "") or ""),
                        float(record.get("timestamp", now)),
                        json.dumps(record, ensure_ascii=False, default=str),
                    ),
                )

    async def load(self, task_id: str) -> Blackboard:
        return await asyncio.to_thread(self._load_sync, task_id)

    def _load_sync(self, task_id: str) -> Blackboard:
        with self._connect() as conn:
            row = conn.execute("SELECT state_json FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"Blackboard task not found: {task_id}")
        return Blackboard.from_dict(json.loads(row["state_json"]))

    async def list_tasks(self, status: Optional[str] = None) -> List[Dict]:
        return await asyncio.to_thread(self._list_tasks_sync, status)

    def _list_tasks_sync(self, status: Optional[str]) -> List[Dict]:
        query = "SELECT task_id, task_type, status, created_at, updated_at FROM tasks"
        params = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    async def get_progress(self, task_id: str) -> Dict:
        return await asyncio.to_thread(self._get_progress_sync, task_id)

    def _get_progress_sync(self, task_id: str) -> Dict:
        with self._connect() as conn:
            task = conn.execute(
                "SELECT task_id, task_type, status, created_at, updated_at FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            logs = conn.execute(
                """
                SELECT agent_name, phase, status, tokens_used, latency_s, error, output_md, timestamp
                FROM agent_logs WHERE task_id = ? ORDER BY id
                """,
                (task_id,),
            ).fetchall()
        if task is None:
            raise KeyError(f"Blackboard task not found: {task_id}")
        return {**dict(task), "logs": [dict(row) for row in logs]}
