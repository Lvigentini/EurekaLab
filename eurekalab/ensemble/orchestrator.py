"""EnsembleOrchestrator — dispatches agents to multiple models and merges results."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

from eurekalab.agents.base import BaseAgent
from eurekalab.ensemble.config import EnsembleConfig, EnsembleRecommendation
from eurekalab.ensemble.model_pool import ModelPool
from eurekalab.ensemble.recommender import EnsembleRecommender
from eurekalab.ensemble.scoped_bus import ScopedBus
from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.llm.base import LLMClient
from eurekalab.types.agents import AgentResult
from eurekalab.types.tasks import Task

logger = logging.getLogger(__name__)

PER_MODEL_TIMEOUT = 300  # seconds


class EnsembleOrchestrator:
    """Coordinates multi-model execution for pipeline stages."""

    def __init__(
        self,
        model_pool: ModelPool,
        config: EnsembleConfig,
        bus: KnowledgeBus,
        gate_mode: str,
    ) -> None:
        self.model_pool = model_pool
        self.config = config
        self.bus = bus
        self.gate_mode = gate_mode
        self.recommender = EnsembleRecommender()

    def is_ensemble_stage(self, stage_name: str) -> bool:
        """Return True if this stage has multi-model ensemble configured."""
        stage = self.config.get_stage(stage_name)
        return stage.strategy != "single" and len(stage.models) > 1

    async def execute_stage(
        self,
        task: Task,
        agent_factory: Callable[[LLMClient], BaseAgent],
    ) -> AgentResult:
        """Run a stage with ensemble if configured, single-model otherwise."""
        stage_config = self.config.get_stage(task.name)

        # Fast path: single model
        if stage_config.strategy == "single" or len(stage_config.models) <= 1:
            model_name = stage_config.models[0] if stage_config.models else "default"
            client = self.model_pool.get(model_name)
            agent = agent_factory(client)
            return await agent.execute(task)

        # Asymmetric: primary + reviewer
        if stage_config.strategy == "asymmetric":
            return await self._run_asymmetric(task, agent_factory, stage_config)

        # Parallel: union / adversarial / consensus
        results = await self._run_parallel(task, agent_factory, stage_config)

        # Merge
        from eurekalab.ensemble.mergers import get_merger
        merger = get_merger(stage_config.strategy)
        if merger is None:
            # Unknown strategy — return first successful result
            for r in results.values():
                if r.success:
                    return r
            raise RuntimeError("All ensemble models failed and no merger available")

        # Pass model_pool to adversarial merger for cross-review
        if hasattr(merger, '_model_pool'):
            merger._model_pool = self.model_pool

        merged = await merger.merge(results, task, self.bus)

        # Generate recommendation
        rec = self.recommender.recommend(
            task.name, self.bus, self.model_pool.list_available(), self.config,
        )
        if rec:
            self.bus.put("ensemble_recommendation", rec)
            logger.info("Ensemble recommendation for %s: %s (confidence=%.2f)",
                        rec.stage, rec.reason, rec.confidence)

        return merged

    async def _run_parallel(
        self,
        task: Task,
        agent_factory: Callable[[LLMClient], BaseAgent],
        stage_config: Any,
    ) -> dict[str, AgentResult]:
        """Run N agents concurrently, return {model_name: result}."""

        async def run_one(model_name: str) -> AgentResult:
            client = self.model_pool.get(model_name)
            agent = agent_factory(client)
            scoped = ScopedBus(self.bus, namespace=model_name)
            agent.bus = scoped
            return await asyncio.wait_for(
                agent.execute(task.model_copy()),
                timeout=PER_MODEL_TIMEOUT,
            )

        coros = {name: run_one(name) for name in stage_config.models}
        raw = await asyncio.gather(*coros.values(), return_exceptions=True)

        results: dict[str, AgentResult] = {}
        for name, result in zip(coros.keys(), raw):
            if isinstance(result, Exception):
                logger.warning("Ensemble model '%s' failed: %s", name, result)
            else:
                results[name] = result

        if not results:
            raise RuntimeError(
                f"All ensemble models failed for stage '{task.name}': "
                + ", ".join(f"{n}: {r}" for n, r in zip(coros.keys(), raw))
            )

        return results

    async def _run_asymmetric(
        self,
        task: Task,
        agent_factory: Callable[[LLMClient], BaseAgent],
        stage_config: Any,
    ) -> AgentResult:
        """Primary model executes, reviewer model critiques."""
        primary_name = stage_config.models[0]
        primary_client = self.model_pool.get(primary_name)
        primary_agent = agent_factory(primary_client)
        primary_result = await primary_agent.execute(task)

        if not stage_config.reviewer:
            return primary_result

        # Run review
        reviewer_client = self.model_pool.get(stage_config.reviewer)
        review = await self._run_review(
            reviewer_client, stage_config.reviewer, primary_result, task,
        )
        primary_result.output["ensemble_review"] = review

        # Re-run if high-severity issues found
        if review.get("issues") and any(
            i.get("severity") == "high" for i in review["issues"]
        ):
            logger.info("Reviewer found high-severity issues — re-running primary with feedback")
            revised_task = task.model_copy()
            revised_task.description = (revised_task.description or "") + \
                f"\n\n[Reviewer feedback]: {json.dumps(review['issues'])}"
            primary_result = await primary_agent.execute(revised_task)
            primary_result.output["ensemble_review"] = review
            primary_result.output["ensemble_revision"] = True

        return primary_result

    async def _run_review(
        self,
        reviewer_client: LLMClient,
        reviewer_name: str,
        primary_result: AgentResult,
        task: Task,
    ) -> dict:
        """Ask a reviewer model to critique the primary model's output."""
        from eurekalab.config import settings

        review_prompt = (
            "You are an independent reviewer. Examine the following proof/analysis output "
            "and identify logical gaps, unjustified steps, missing edge cases, or errors.\n\n"
            f"Original task: {(task.description or '')[:500]}\n\n"
            f"Output to review:\n{json.dumps(primary_result.output, default=str)[:4000]}\n\n"
            "Respond with a JSON object:\n"
            '{"review_passed": bool, "issues": [{"lemma_id": "...", "severity": "high|medium|low", '
            '"description": "..."}], "confidence": 0.0-1.0, "summary": "1-2 sentence overall assessment"}'
        )

        try:
            response = await reviewer_client.messages.create(
                model=self.model_pool.get_model_name(reviewer_name),
                max_tokens=settings.max_tokens_verifier,
                system="You are a rigorous mathematical reviewer. Output only valid JSON.",
                messages=[{"role": "user", "content": review_prompt}],
            )
            text = response.content[0].text
            return json.loads(text)
        except Exception as e:
            logger.warning("Reviewer returned non-JSON or failed: %s", e)
            return {"review_passed": True, "issues": [], "confidence": 0.5}
