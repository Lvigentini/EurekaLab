"""Full-pipeline session checkpoint — detects progress and enables resume from any stage."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from eurekalab.config import settings

logger = logging.getLogger(__name__)

STAGE_ORDER = [
    "survey",
    "ideation",
    "direction_selection_gate",
    "theory",
    "theory_review_gate",
    "experiment",
    "writer",
]


class SessionCheckpoint:
    """Manages full-pipeline progress detection and resume logic."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._runs_dir = settings.runs_dir / session_id

    def detect_progress(self) -> tuple[str | None, list[str]]:
        """Detect how far a session got before it stopped."""
        marker = self._runs_dir / "_stage_progress.json"
        if not marker.exists():
            return None, []
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
            stages = data.get("completed_stages", [])
            last = stages[-1] if stages else None
            return last, stages
        except (json.JSONDecodeError, KeyError):
            return None, []

    def next_stage_after(self, stage_name: str) -> str | None:
        """Return the stage that should run after the given stage."""
        # Strip _FAILED suffix if present
        clean = stage_name.replace("_FAILED", "")
        try:
            idx = STAGE_ORDER.index(clean)
            if idx + 1 < len(STAGE_ORDER):
                return STAGE_ORDER[idx + 1]
        except ValueError:
            pass
        return None
