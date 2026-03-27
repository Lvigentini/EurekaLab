"""BaseMerger — abstract interface for ensemble merge strategies."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.types.agents import AgentResult, AgentRole
from eurekalab.types.tasks import Task

logger = logging.getLogger(__name__)


class BaseMerger(ABC):
    """All ensemble merge strategies implement this interface."""

    @abstractmethod
    async def merge(
        self,
        results: dict[str, AgentResult],
        task: Task | None,
        bus: KnowledgeBus,
    ) -> AgentResult:
        ...

    def _filter_successes(self, results: dict[str, AgentResult]) -> dict[str, AgentResult]:
        """Keep only successful results. Raises if all failed."""
        valid = {k: v for k, v in results.items() if v.success}
        if not valid:
            errors = {k: v.error for k, v in results.items()}
            raise RuntimeError(f"All ensemble models failed: {errors}")
        return valid
