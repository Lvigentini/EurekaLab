"""VersionStore — git-like version management for research sessions."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from eurekaclaw.knowledge_bus.bus import KnowledgeBus
from eurekaclaw.versioning.snapshot import BusSnapshot

logger = logging.getLogger(__name__)


class ResearchVersion(BaseModel):
    """A single point-in-time snapshot of the research state."""
    version_number: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trigger: str
    completed_stages: list[str] = Field(default_factory=list)
    snapshot_json: str = ""
    changes: list[str] = Field(default_factory=list)


class VersionStore:
    """Manages version history for a research session.

    Uses SessionDB (SQLite) when available, falls back to JSON files
    for backward compatibility with existing sessions.
    """

    def __init__(self, session_id: str, session_dir: Path, db_path: Path | None = None) -> None:
        self.session_id = session_id
        self._session_dir = session_dir
        self._db = self._get_db(db_path)

    def _get_db(self, db_path: Path | None = None):
        """Get or create the SessionDB instance."""
        from eurekaclaw.storage.db import SessionDB
        if db_path:
            return SessionDB(db_path)
        from eurekaclaw.config import settings
        return SessionDB(settings.eurekaclaw_dir / "eurekaclaw.db")

    def _ensure_session(self) -> None:
        """Ensure the session record exists in the DB before writing versions."""
        if not self._db.get_session(self.session_id):
            self._db.create_session(self.session_id)

    def commit(
        self,
        bus: KnowledgeBus,
        trigger: str,
        completed_stages: list[str] | None = None,
        changes: list[str] | None = None,
    ) -> ResearchVersion:
        snap = BusSnapshot.from_bus(bus)

        self._ensure_session()

        # Get next version number
        latest = self._db.get_latest_version(self.session_id)
        version_number = (latest["version_number"] + 1) if latest else 1

        stages = completed_stages or []
        change_list = changes or []

        self._db.add_version(
            session_id=self.session_id,
            version_number=version_number,
            trigger=trigger,
            completed_stages=stages,
            snapshot_json=snap.to_json(),
            changes=change_list,
        )

        # Also update session record with latest stages
        self._db.update_session(self.session_id, completed_stages=stages)

        version = ResearchVersion(
            version_number=version_number,
            trigger=trigger,
            completed_stages=stages,
            snapshot_json=snap.to_json(),
            changes=change_list,
        )
        logger.info("Version v%03d committed: %s", version_number, trigger)
        return version

    @property
    def head(self) -> ResearchVersion | None:
        latest = self._db.get_latest_version(self.session_id)
        if not latest:
            return None
        return self._dict_to_version(latest)

    def log(self) -> list[ResearchVersion]:
        rows = self._db.get_versions(self.session_id)
        return [self._dict_to_version(r) for r in rows]

    def get(self, version_number: int) -> ResearchVersion | None:
        row = self._db.get_version(self.session_id, version_number)
        if not row:
            return None
        return self._dict_to_version(row)

    def checkout(self, version_number: int) -> KnowledgeBus:
        v = self.get(version_number)
        if v is None:
            raise ValueError(f"Version {version_number} not found")
        snap = BusSnapshot.from_json(v.snapshot_json)
        return snap.to_bus()

    @staticmethod
    def _dict_to_version(d: dict) -> ResearchVersion:
        ts = d.get("timestamp", "")
        if isinstance(ts, str) and ts:
            try:
                timestamp = datetime.fromisoformat(ts)
            except ValueError:
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)
        return ResearchVersion(
            version_number=d["version_number"],
            timestamp=timestamp,
            trigger=d["trigger"],
            completed_stages=d.get("completed_stages", []),
            snapshot_json=d.get("snapshot_json", ""),
            changes=d.get("changes", []),
        )
