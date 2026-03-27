"""SessionDB — SQLite backend for session metadata and version history."""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SessionRecord:
    """A session's metadata (not the full artifact state)."""
    session_id: str
    domain: str = ""
    query: str = ""
    mode: str = "exploration"
    status: str = "running"  # running, completed, failed, paused
    created_at: str = ""
    updated_at: str = ""
    completed_stages: list[str] = field(default_factory=list)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    domain TEXT NOT NULL DEFAULT '',
    query TEXT NOT NULL DEFAULT '',
    mode TEXT NOT NULL DEFAULT 'exploration',
    status TEXT NOT NULL DEFAULT 'running',
    completed_stages TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS versions (
    session_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    trigger TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL,
    completed_stages TEXT NOT NULL DEFAULT '[]',
    snapshot_json TEXT NOT NULL DEFAULT '',
    changes TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (session_id, version_number),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
"""


class SessionDB:
    """SQLite database for session metadata and version history."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ── Sessions ──────────────────────────────────────────────────

    def create_session(
        self,
        session_id: str,
        domain: str = "",
        query: str = "",
        mode: str = "exploration",
        status: str = "running",
    ) -> SessionRecord:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT OR IGNORE INTO sessions
               (session_id, domain, query, mode, status, completed_stages, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, '[]', ?, ?)""",
            (session_id, domain, query, mode, status, now, now),
        )
        self._conn.commit()
        return SessionRecord(
            session_id=session_id, domain=domain, query=query,
            mode=mode, status=status, created_at=now, updated_at=now,
        )

    def get_session(self, session_id: str) -> SessionRecord | None:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def update_session(self, session_id: str, **kwargs) -> None:
        allowed = {"status", "domain", "query", "completed_stages"}
        updates = []
        values = []
        for key, val in kwargs.items():
            if key not in allowed:
                continue
            if key == "completed_stages":
                val = json.dumps(val)
            updates.append(f"{key} = ?")
            values.append(val)
        if not updates:
            return
        updates.append("updated_at = ?")
        values.append(datetime.now(timezone.utc).isoformat())
        values.append(session_id)
        self._conn.execute(
            f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?",
            values,
        )
        self._conn.commit()

    def list_sessions(self) -> list[SessionRecord]:
        rows = self._conn.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def list_sessions_older_than(self, days: int) -> list[SessionRecord]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE created_at < ? ORDER BY created_at DESC",
            (cutoff,),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def delete_session(self, session_id: str) -> None:
        self._conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self._conn.commit()

    def _row_to_record(self, row: sqlite3.Row) -> SessionRecord:
        stages = json.loads(row["completed_stages"]) if row["completed_stages"] else []
        return SessionRecord(
            session_id=row["session_id"],
            domain=row["domain"],
            query=row["query"],
            mode=row["mode"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_stages=stages,
        )

    # ── Versions ──────────────────────────────────────────────────

    def add_version(
        self,
        session_id: str,
        version_number: int,
        trigger: str,
        completed_stages: list[str],
        snapshot_json: str,
        changes: list[str],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT INTO versions
               (session_id, version_number, trigger, timestamp, completed_stages, snapshot_json, changes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, version_number, trigger, now,
             json.dumps(completed_stages), snapshot_json, json.dumps(changes)),
        )
        self._conn.commit()

    def get_versions(self, session_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM versions WHERE session_id = ? ORDER BY version_number ASC",
            (session_id,),
        ).fetchall()
        return [self._version_row_to_dict(r) for r in rows]

    def get_version(self, session_id: str, version_number: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM versions WHERE session_id = ? AND version_number = ?",
            (session_id, version_number),
        ).fetchone()
        return self._version_row_to_dict(row) if row else None

    def get_latest_version(self, session_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM versions WHERE session_id = ? ORDER BY version_number DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return self._version_row_to_dict(row) if row else None

    def _version_row_to_dict(self, row: sqlite3.Row) -> dict:
        return {
            "session_id": row["session_id"],
            "version_number": row["version_number"],
            "trigger": row["trigger"],
            "timestamp": row["timestamp"],
            "completed_stages": json.loads(row["completed_stages"]),
            "snapshot_json": row["snapshot_json"],
            "changes": json.loads(row["changes"]),
        }
