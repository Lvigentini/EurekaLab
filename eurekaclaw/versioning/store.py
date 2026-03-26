"""VersionStore — git-like version management for research sessions."""
from __future__ import annotations

import json
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
    """Manages version history for a research session."""

    def __init__(self, session_id: str, session_dir: Path) -> None:
        self.session_id = session_id
        self._session_dir = session_dir
        self._versions_dir = session_dir / "versions"
        self._versions: list[ResearchVersion] = []
        self._load_existing()

    def _load_existing(self) -> None:
        if not self._versions_dir.exists():
            return
        files = sorted(self._versions_dir.glob("v*.json"))
        for f in files:
            try:
                v = ResearchVersion.model_validate_json(f.read_text())
                self._versions.append(v)
            except Exception as e:
                logger.warning("Failed to load version file %s: %s", f, e)

    def commit(
        self,
        bus: KnowledgeBus,
        trigger: str,
        completed_stages: list[str] | None = None,
        changes: list[str] | None = None,
    ) -> ResearchVersion:
        snap = BusSnapshot.from_bus(bus)
        version_number = len(self._versions) + 1
        version = ResearchVersion(
            version_number=version_number,
            trigger=trigger,
            completed_stages=completed_stages or [],
            snapshot_json=snap.to_json(),
            changes=changes or [],
        )
        self._versions.append(version)
        self._write_version(version)
        logger.info("Version v%03d committed: %s", version_number, trigger)
        return version

    def _write_version(self, v: ResearchVersion) -> None:
        self._versions_dir.mkdir(parents=True, exist_ok=True)
        path = self._versions_dir / f"v{v.version_number:03d}.json"
        path.write_text(v.model_dump_json(indent=2), encoding="utf-8")

    @property
    def head(self) -> ResearchVersion | None:
        return self._versions[-1] if self._versions else None

    def log(self) -> list[ResearchVersion]:
        return list(self._versions)

    def get(self, version_number: int) -> ResearchVersion | None:
        for v in self._versions:
            if v.version_number == version_number:
                return v
        return None

    def checkout(self, version_number: int) -> KnowledgeBus:
        v = self.get(version_number)
        if v is None:
            raise ValueError(f"Version {version_number} not found")
        snap = BusSnapshot.from_json(v.snapshot_json)
        return snap.to_bus()
