"""ConsensusMerger — independent experiment validation with agreement scoring."""

from __future__ import annotations

import logging
from typing import Any

from eurekalab.ensemble.mergers.base import BaseMerger
from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.types.agents import AgentResult, AgentRole
from eurekalab.types.tasks import Task

logger = logging.getLogger(__name__)

AGREEMENT_TOLERANCE = 0.10  # 10% tolerance for "agreement"


class ConsensusMerger(BaseMerger):
    """Compare experiment results across models — agreement = high confidence."""

    async def merge(
        self,
        results: dict[str, AgentResult],
        task: Task | None,
        bus: KnowledgeBus,
    ) -> AgentResult:
        valid = self._filter_successes(results)

        if len(valid) == 1:
            return next(iter(valid.values()))

        # Collect bounds from all models, keyed by bound name
        bounds_by_name: dict[str, dict[str, Any]] = {}  # name -> {model: empirical}
        theoretical_by_name: dict[str, float] = {}

        for model_name, result in valid.items():
            for bound in result.output.get("bounds", []):
                name = bound.get("name", "")
                if not name:
                    continue
                if name not in bounds_by_name:
                    bounds_by_name[name] = {}
                    theoretical_by_name[name] = bound.get("theoretical", 0)
                try:
                    bounds_by_name[name][model_name] = float(bound.get("empirical", 0))
                except (ValueError, TypeError):
                    pass

        # Compare bounds across models
        confirmed: list[dict] = []
        contested: list[dict] = []

        for name, model_values in bounds_by_name.items():
            values = list(model_values.values())
            if len(values) < 2:
                # Only one model measured this bound — include but can't confirm
                confirmed.append({
                    "name": name,
                    "theoretical": theoretical_by_name.get(name),
                    "empirical": values[0],
                    "models_agree": False,
                    "single_model": True,
                })
                continue

            # Check if all values are within tolerance of each other
            min_val = min(values)
            max_val = max(values)
            mean_val = sum(values) / len(values)
            spread = (max_val - min_val) / max(abs(mean_val), 1e-10)

            if spread <= AGREEMENT_TOLERANCE:
                confirmed.append({
                    "name": name,
                    "theoretical": theoretical_by_name.get(name),
                    "empirical": round(mean_val, 6),
                    "models_agree": True,
                    "per_model": model_values,
                })
            else:
                contested.append({
                    "name": name,
                    "theoretical": theoretical_by_name.get(name),
                    "per_model": model_values,
                    "gap": round(spread, 4),
                })

        total_bounds = len(confirmed) + len(contested)
        confirmed_count = len([b for b in confirmed if b.get("models_agree")])
        agreement_ratio = round(confirmed_count / max(total_bounds, 1), 2)

        # Average alignment scores across models
        alignment_scores = [r.output.get("alignment_score", 0) for r in valid.values()]
        avg_alignment = round(sum(alignment_scores) / len(alignment_scores), 3)

        # Total tokens
        total_tokens: dict[str, int] = {"input": 0, "output": 0}
        for r in valid.values():
            for k in ("input", "output"):
                total_tokens[k] += r.token_usage.get(k, 0)

        first = next(iter(valid.values()))
        return AgentResult(
            task_id=first.task_id,
            agent_role=first.agent_role,
            success=True,
            output={
                "confirmed_bounds": confirmed,
                "contested_bounds": contested,
                "agreement_ratio": agreement_ratio,
                "alignment_score": avg_alignment,
                "code": first.output.get("code", ""),
                "bounds": first.output.get("bounds", []),  # keep original for writer
            },
            text_summary=f"Ensemble experiment: {confirmed_count}/{total_bounds} bounds confirmed, {len(contested)} contested",
            token_usage=total_tokens,
        )
