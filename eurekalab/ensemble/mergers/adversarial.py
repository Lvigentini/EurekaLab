"""AdversarialMerger — cross-review and rank ideation directions from multiple models."""

from __future__ import annotations

import json
import logging
from typing import Any

from eurekalab.ensemble.mergers.base import BaseMerger
from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.types.agents import AgentResult, AgentRole
from eurekalab.types.tasks import Task

logger = logging.getLogger(__name__)

# Simple word-overlap similarity for detecting convergent directions
def _title_similarity(a: str, b: str) -> float:
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0

SIMILARITY_THRESHOLD = 0.7


class AdversarialMerger(BaseMerger):
    """Merge ideation results: combine directions, detect convergence/uniqueness, rank."""

    def __init__(self, model_pool=None):
        self._model_pool = model_pool  # needed for cross-review LLM calls

    async def merge(
        self,
        results: dict[str, AgentResult],
        task: Task | None,
        bus: KnowledgeBus,
    ) -> AgentResult:
        valid = self._filter_successes(results)

        if len(valid) == 1 or self._model_pool is None:
            return await self._merge_without_review(valid, bus)

        # Phase 1: Collect all directions
        all_directions = self._collect_directions(valid)

        # Phase 2: Cross-review (if model_pool available)
        try:
            all_directions = await self._cross_review(all_directions, valid)
        except Exception as e:
            logger.warning("Cross-review failed, proceeding without: %s", e)

        # Phase 3: Rank
        ranked = self._rank_directions(all_directions)

        return self._build_result(ranked, valid, bus)

    async def _merge_without_review(
        self, results: dict[str, AgentResult], bus: KnowledgeBus,
    ) -> AgentResult:
        """Merge without cross-review — used when only 1 model or no model_pool."""
        valid = self._filter_successes(results)
        all_directions = self._collect_directions(valid)
        ranked = self._rank_directions(all_directions)
        return self._build_result(ranked, valid, bus)

    def _collect_directions(self, results: dict[str, AgentResult]) -> list[dict]:
        """Collect all directions from all models, tagging source."""
        all_dirs = []
        for model_name, result in results.items():
            for d in result.output.get("directions", []):
                d["source_model"] = model_name
                d["cross_scores"] = {}
                all_dirs.append(d)
        return all_dirs

    async def _cross_review(self, directions: list[dict], results: dict[str, AgentResult]) -> list[dict]:
        """Each model reviews the other models' directions."""
        from eurekalab.config import settings

        model_names = list(results.keys())

        for reviewer_name in model_names:
            others = [d for d in directions if d["source_model"] != reviewer_name]
            if not others:
                continue

            reviewer_client = self._model_pool.get(reviewer_name)
            prompt = (
                "Score each research direction on three dimensions (0.0-1.0):\n"
                "- novelty: How original is this idea?\n"
                "- soundness: Is the mathematical reasoning plausible?\n"
                "- feasibility: Can this be proved with known techniques?\n\n"
                "Directions to review:\n"
                f"{json.dumps([{'title': d['title'], 'hypothesis': d['hypothesis'], 'direction_id': d['direction_id']} for d in others], indent=2)}\n\n"
                'Return JSON array: [{"direction_id": "...", "novelty": 0.8, "soundness": 0.7, "feasibility": 0.6, "critique": "..."}]'
            )

            try:
                response = await reviewer_client.messages.create(
                    model=self._model_pool.get_model_name(reviewer_name),
                    max_tokens=2048,
                    system="You are a rigorous research reviewer. Output only valid JSON.",
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text
                scores = json.loads(text if text.strip().startswith("[") else text[text.index("["):text.rindex("]")+1])
                score_map = {s["direction_id"]: s for s in scores}

                for d in directions:
                    if d["direction_id"] in score_map:
                        s = score_map[d["direction_id"]]
                        cross_score = 0.4 * s.get("novelty", 0.5) + 0.35 * s.get("soundness", 0.5) + 0.25 * s.get("feasibility", 0.5)
                        d["cross_scores"][reviewer_name] = round(cross_score, 3)
            except Exception as e:
                logger.warning("Cross-review by %s failed: %s", reviewer_name, e)

        return directions

    def _rank_directions(self, directions: list[dict]) -> list[dict]:
        """Rank directions by composite score with bonuses."""
        # Detect convergent pairs (similar titles from different models)
        convergent_ids: set[str] = set()
        for i, a in enumerate(directions):
            for b in directions[i+1:]:
                if a["source_model"] != b["source_model"]:
                    if _title_similarity(a.get("title", ""), b.get("title", "")) > SIMILARITY_THRESHOLD:
                        convergent_ids.add(a["direction_id"])
                        convergent_ids.add(b["direction_id"])

        for d in directions:
            self_score = (
                0.4 * d.get("novelty_score", 0.5)
                + 0.35 * d.get("soundness_score", 0.5)
                + 0.25 * d.get("transformative_score", 0.5)
            )
            cross_scores = list(d.get("cross_scores", {}).values())
            avg_cross = sum(cross_scores) / len(cross_scores) if cross_scores else self_score

            is_convergent = d["direction_id"] in convergent_ids
            bonus = 0.15 if is_convergent else 0.2  # convergence vs originality
            d["consensus"] = "converged" if is_convergent else "unique"

            d["final_score"] = round(0.4 * avg_cross + 0.3 * self_score + 0.3 * bonus, 3)

        directions.sort(key=lambda d: d["final_score"], reverse=True)
        return directions[:7]  # top 7

    def _build_result(self, directions: list[dict], results: dict[str, AgentResult], bus: KnowledgeBus) -> AgentResult:
        first = next(iter(results.values()))
        total_tokens: dict[str, int] = {"input": 0, "output": 0}
        for r in results.values():
            for k in ("input", "output"):
                total_tokens[k] += r.token_usage.get(k, 0)

        return AgentResult(
            task_id=first.task_id,
            agent_role=first.agent_role,
            success=True,
            output={"directions": directions},
            text_summary=f"Ensemble ideation: {len(directions)} directions from {len(results)} models",
            token_usage=total_tokens,
        )
