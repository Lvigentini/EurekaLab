"""EnsembleRecommender — heuristic suggestions for ensemble adjustments."""

from __future__ import annotations

import logging
from typing import Any

from eurekaclaw.ensemble.config import EnsembleConfig, EnsembleRecommendation
from eurekaclaw.knowledge_bus.bus import KnowledgeBus

logger = logging.getLogger(__name__)


class EnsembleRecommender:
    """Generates ensemble recommendations based on stage results."""

    def recommend(
        self,
        completed_stage: str,
        bus: KnowledgeBus,
        available_models: list[str],
        current_config: EnsembleConfig,
    ) -> EnsembleRecommendation | None:
        """Check heuristic rules and return a recommendation, or None."""
        handler = getattr(self, f"_after_{completed_stage}", None)
        if handler:
            return handler(bus, available_models, current_config)
        return None

    def _after_survey(
        self, bus: KnowledgeBus, available: list[str], config: EnsembleConfig,
    ) -> EnsembleRecommendation | None:
        stats = bus.get("ensemble_survey_stats")
        if not stats:
            return None

        overlap = stats.get("overlap_ratio", 0.5)
        per_model = stats.get("per_model", {})

        # Check for dead models
        dead = [m for m, count in per_model.items() if count == 0]
        if dead:
            alive = [m for m in available if m not in dead]
            return EnsembleRecommendation(
                stage="ideation",
                suggested_models=alive,
                suggested_strategy="adversarial",
                reason=f"Model(s) {dead} found 0 papers — excluding from ideation",
                confidence=0.9,
            )

        # Low overlap — widen
        if overlap < 0.20 and len(available) > 2:
            return EnsembleRecommendation(
                stage="ideation",
                suggested_models=available,
                suggested_strategy="adversarial",
                reason=f"Low overlap ({overlap:.0%}) — widen ideation to {len(available)} models for broader creative coverage",
                confidence=0.8,
            )

        # High overlap — narrow
        if overlap > 0.65:
            narrowed = list(per_model.keys())[:2] if len(per_model) > 2 else list(per_model.keys())
            return EnsembleRecommendation(
                stage="ideation",
                suggested_models=narrowed,
                suggested_strategy="adversarial",
                reason=f"High overlap ({overlap:.0%}) — 2 models sufficient for ideation, save tokens",
                confidence=0.6,
            )

        return None

    def _after_ideation(
        self, bus: KnowledgeBus, available: list[str], config: EnsembleConfig,
    ) -> EnsembleRecommendation | None:
        return None  # Placeholder — can add clustering detection later

    def _after_theory(
        self, bus: KnowledgeBus, available: list[str], config: EnsembleConfig,
    ) -> EnsembleRecommendation | None:
        state = bus.get_theory_state()
        if not state:
            return None

        # Count low-confidence lemmas
        low_conf = sum(
            1 for p in state.proven_lemmas.values()
            if hasattr(p, 'confidence') and p.confidence and p.confidence < 0.7
        )
        if low_conf > 2 and len(available) > 1:
            return EnsembleRecommendation(
                stage="experiment",
                suggested_models=available[:2],
                suggested_strategy="consensus",
                reason=f"{low_conf} low-confidence lemmas — add consensus validation in experiment",
                confidence=0.7,
            )
        return None

    def _after_experiment(
        self, bus: KnowledgeBus, available: list[str], config: EnsembleConfig,
    ) -> EnsembleRecommendation | None:
        return None  # Writer is always single-model
