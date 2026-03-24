"""EnsembleConfig — per-stage ensemble configuration with dynamic overrides."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

KNOWN_STAGES = ["survey", "ideation", "theory", "experiment", "writer"]
VALID_STRATEGIES = {"single", "union", "adversarial", "consensus", "asymmetric"}


@dataclass
class StageEnsembleConfig:
    """Configuration for one pipeline stage's ensemble behavior."""
    models: list[str] = field(default_factory=list)
    strategy: str = "single"
    reviewer: str | None = None
    locked: bool = False


@dataclass
class EnsembleRecommendation:
    """A suggested ensemble adjustment for an upcoming stage."""
    stage: str
    suggested_models: list[str]
    suggested_strategy: str
    reason: str
    confidence: float  # 0-1


class EnsembleConfig:
    """Manages per-stage ensemble configuration."""

    def __init__(self) -> None:
        self._stages: dict[str, StageEnsembleConfig] = {}

    def get_stage(self, stage_name: str) -> StageEnsembleConfig:
        return self._stages.get(stage_name, StageEnsembleConfig())

    def update_stage(
        self,
        stage_name: str,
        models: list[str],
        strategy: str,
        locked: bool = False,
        reviewer: str | None = None,
    ) -> None:
        self._stages[stage_name] = StageEnsembleConfig(
            models=models,
            strategy=strategy,
            reviewer=reviewer,
            locked=locked,
        )

    @classmethod
    def from_env(cls) -> "EnsembleConfig":
        """Parse ENSEMBLE_{STAGE}_MODELS/STRATEGY/REVIEWER from environment."""
        config = cls()
        for stage in KNOWN_STAGES:
            prefix = f"ENSEMBLE_{stage.upper()}_"
            models_str = os.environ.get(f"{prefix}MODELS", "")
            strategy = os.environ.get(f"{prefix}STRATEGY", "")
            reviewer = os.environ.get(f"{prefix}REVIEWER", "")

            if not models_str and not strategy:
                continue

            models = [m.strip() for m in models_str.split(",") if m.strip()]
            strategy = strategy or "single"

            if strategy not in VALID_STRATEGIES:
                logger.warning("Invalid strategy '%s' for stage '%s' — using 'single'", strategy, stage)
                strategy = "single"

            config._stages[stage] = StageEnsembleConfig(
                models=models,
                strategy=strategy,
                reviewer=reviewer or None,
            )

        return config
