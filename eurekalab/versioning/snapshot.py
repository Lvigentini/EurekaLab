"""BusSnapshot — serialize/deserialize full KnowledgeBus state.

NOTE: This module uses lazy imports for KnowledgeBus to avoid circular
imports (bus.py imports versioning, versioning imports bus.py).
"""
from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from eurekalab.knowledge_bus.bus import KnowledgeBus


def _model_map() -> dict[str, type]:
    """Lazy-load the model map to avoid import-time circular deps."""
    from eurekalab.types.artifacts import (
        Bibliography,
        ExperimentResult,
        ResearchBrief,
        TheoryState,
    )
    from eurekalab.types.tasks import TaskPipeline
    from eurekalab.orchestrator.ideation_pool import IdeationPool
    return {
        "research_brief": ResearchBrief,
        "theory_state": TheoryState,
        "experiment_result": ExperimentResult,
        "bibliography": Bibliography,
        "pipeline": TaskPipeline,
        "ideation_pool": IdeationPool,
    }


class BusSnapshot:
    """A serializable snapshot of the full KnowledgeBus state."""

    def __init__(self, session_id: str, artifacts: dict[str, Any]) -> None:
        self.session_id = session_id
        self.artifacts = artifacts

    @classmethod
    def from_bus(cls, bus: KnowledgeBus) -> BusSnapshot:
        artifacts: dict[str, str] = {}
        for key, value in bus._store.items():
            if hasattr(value, "model_dump_json"):
                artifacts[key] = value.model_dump_json()
            else:
                artifacts[key] = json.dumps(value, default=str)
        return cls(session_id=bus.session_id, artifacts=artifacts)

    def to_bus(self) -> KnowledgeBus:
        from eurekalab.knowledge_bus.bus import KnowledgeBus
        bus = KnowledgeBus(self.session_id)
        models = _model_map()
        for key, raw_json in self.artifacts.items():
            model_cls = models.get(key)
            if model_cls is not None:
                bus._store[key] = model_cls.model_validate_json(raw_json)
            else:
                bus._store[key] = json.loads(raw_json)
        return bus

    def to_json(self) -> str:
        return json.dumps({
            "session_id": self.session_id,
            "artifacts": self.artifacts,
        })

    @classmethod
    def from_json(cls, raw: str) -> BusSnapshot:
        data = json.loads(raw)
        return cls(
            session_id=data["session_id"],
            artifacts=data["artifacts"],
        )
