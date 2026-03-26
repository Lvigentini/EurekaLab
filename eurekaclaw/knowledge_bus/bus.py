"""KnowledgeBus — in-memory artifact store with JSON persistence and reactive subscriptions.

All agents read and write through this interface, never to disk directly during a session.
At the end of a session, call bus.persist(session_dir) to write all artifacts to disk.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from eurekaclaw.types.artifacts import (
    Bibliography,
    ExperimentResult,
    Paper,
    ResearchBrief,
    TheoryState,
)
from eurekaclaw.types.tasks import TaskPipeline

logger = logging.getLogger(__name__)


class KnowledgeBus:
    """Central shared artifact store for a single research session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._store: dict[str, Any] = {}
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._session_dir: Path | None = None
        self._completed_stages: list[str] = []
        self.version_store = None  # VersionStore, lazy-initialized to avoid circular import

    # ------------------------------------------------------------------
    # Research Brief
    # ------------------------------------------------------------------

    def put_research_brief(self, brief: ResearchBrief) -> None:
        brief.updated_at = datetime.now().astimezone()
        self._store["research_brief"] = brief
        self._notify("research_brief", brief)

    def get_research_brief(self) -> ResearchBrief | None:
        return self._store.get("research_brief")

    # ------------------------------------------------------------------
    # Theory State
    # ------------------------------------------------------------------

    def put_theory_state(self, state: TheoryState) -> None:
        state.updated_at = datetime.now().astimezone()
        self._store["theory_state"] = state
        self._notify("theory_state", state)

    def get_theory_state(self) -> TheoryState | None:
        return self._store.get("theory_state")

    # ------------------------------------------------------------------
    # Experiment Result
    # ------------------------------------------------------------------

    def put_experiment_result(self, result: ExperimentResult) -> None:
        self._store["experiment_result"] = result
        self._notify("experiment_result", result)

    def get_experiment_result(self) -> ExperimentResult | None:
        return self._store.get("experiment_result")

    # ------------------------------------------------------------------
    # Bibliography
    # ------------------------------------------------------------------

    def put_bibliography(self, bib: Bibliography) -> None:
        bib.updated_at = datetime.now().astimezone()
        self._store["bibliography"] = bib
        self._notify("bibliography", bib)

    def get_bibliography(self) -> Bibliography | None:
        return self._store.get("bibliography")

    def append_citations(self, papers: list[Paper]) -> None:
        bib = self._store.get("bibliography") or Bibliography(session_id=self.session_id)
        existing_ids = {p.paper_id for p in bib.papers}
        new_papers = [p for p in papers if p.paper_id not in existing_ids]
        bib.papers.extend(new_papers)
        bib.updated_at = datetime.now().astimezone()
        self._store["bibliography"] = bib
        self._notify("bibliography", bib)
        logger.debug("Appended %d new citations (total: %d)", len(new_papers), len(bib.papers))

    # ------------------------------------------------------------------
    # Task Pipeline
    # ------------------------------------------------------------------

    def put_pipeline(self, pipeline: TaskPipeline) -> None:
        self._store["pipeline"] = pipeline
        self._notify("pipeline", pipeline)

    def get_pipeline(self) -> TaskPipeline | None:
        return self._store.get("pipeline")

    # ------------------------------------------------------------------
    # Generic key-value store (for agents to share arbitrary data)
    # ------------------------------------------------------------------

    def put(self, key: str, value: Any) -> None:
        self._store[key] = value
        self._notify(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    # ------------------------------------------------------------------
    # Reactive subscriptions
    # ------------------------------------------------------------------

    def subscribe(self, artifact_type: str, callback: Callable) -> None:
        """Register a callback to fire whenever an artifact is updated."""
        self._subscribers[artifact_type].append(callback)

    def _notify(self, artifact_type: str, value: Any) -> None:
        for cb in self._subscribers.get(artifact_type, []):
            try:
                cb(value)
            except Exception as e:
                logger.warning("Subscriber error for %s: %s", artifact_type, e)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def persist(self, session_dir: Path) -> None:
        """Write all artifacts to session_dir as JSON files."""
        session_dir.mkdir(parents=True, exist_ok=True)
        for key, value in self._store.items():
            path = session_dir / f"{key}.json"
            if hasattr(value, "model_dump_json"):
                path.write_text(value.model_dump_json(indent=2), encoding="utf-8")
            else:
                path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
        logger.info("Persisted %d artifacts to %s", len(self._store), session_dir)

    def persist_incremental(self, completed_stage: str | None = None) -> None:
        """Write current bus state to disk incrementally.

        Called after each pipeline stage to ensure partial work survives crashes.
        """
        if self._session_dir is None:
            from eurekaclaw.config import settings
            self._session_dir = settings.runs_dir / self.session_id

        self._session_dir.mkdir(parents=True, exist_ok=True)

        for key, value in self._store.items():
            path = self._session_dir / f"{key}.json"
            if hasattr(value, "model_dump_json"):
                path.write_text(value.model_dump_json(indent=2), encoding="utf-8")
            else:
                path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")

        if completed_stage and completed_stage not in self._completed_stages:
            self._completed_stages.append(completed_stage)

        marker = self._session_dir / "_stage_progress.json"
        marker.write_text(json.dumps({
            "session_id": self.session_id,
            "completed_stages": self._completed_stages,
        }, indent=2), encoding="utf-8")

        # Version store: auto-commit on every incremental persist
        if self._session_dir is not None:
            from eurekaclaw.versioning.store import VersionStore  # lazy import
            if self.version_store is None:
                self.version_store = VersionStore(self.session_id, self._session_dir)
            trigger = f"stage:{completed_stage}:completed" if completed_stage else "persist"
            if completed_stage and "_FAILED" in completed_stage:
                trigger = f"stage:{completed_stage}"
            self.version_store.commit(
                self,
                trigger=trigger,
                completed_stages=list(self._completed_stages),
            )

        logger.debug("Incremental persist: %d artifacts, stages=%s",
                     len(self._store), self._completed_stages)

    @classmethod
    def load(cls, session_id: str, session_dir: Path) -> "KnowledgeBus":
        """Reconstruct a KnowledgeBus from a persisted session directory."""
        bus = cls(session_id)
        model_map = {
            "research_brief": ResearchBrief,
            "theory_state": TheoryState,
            "experiment_result": ExperimentResult,
            "bibliography": Bibliography,
            "pipeline": TaskPipeline,
        }
        for key, model_cls in model_map.items():
            path = session_dir / f"{key}.json"
            if path.exists():
                bus._store[key] = model_cls.model_validate_json(path.read_text())
        bus._session_dir = session_dir
        from eurekaclaw.versioning.store import VersionStore  # lazy import
        bus.version_store = VersionStore(session_id, session_dir)
        return bus
