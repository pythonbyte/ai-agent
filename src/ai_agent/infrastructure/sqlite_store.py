"""SQLite-backed session and memory stores (stdlib sqlite3)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ai_agent.domain.state import ConversationState


class SqliteStore:
    """
    Dual-purpose store: conversation sessions + key/value memory.

    Implements SessionStore and MemoryStore protocols.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    agent_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS memory (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def save(self, agent_id: str, state: ConversationState) -> None:
        payload = state.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (agent_id, payload, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(agent_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (agent_id, payload),
            )

    def load(self, agent_id: str) -> ConversationState | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM sessions WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
        if row is None:
            return None
        data = json.loads(row["payload"])
        return ConversationState.model_validate(data)

    def put(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )

    def get(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM memory WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return str(row["value"])

    def list_keys(self, prefix: str = "") -> list[str]:
        with self._connect() as conn:
            if prefix:
                rows = conn.execute(
                    "SELECT key FROM memory WHERE key LIKE ? ORDER BY key",
                    (f"{prefix}%",),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT key FROM memory ORDER BY key",
                ).fetchall()
        return [str(row["key"]) for row in rows]
