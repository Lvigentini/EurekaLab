"""UnionMerger — combines survey results with deduplication."""

from __future__ import annotations

import logging
from typing import Any

from eurekalab.ensemble.mergers.base import BaseMerger
from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.types.agents import AgentResult, AgentRole
from eurekalab.types.tasks import Task

logger = logging.getLogger(__name__)


class UnionMerger(BaseMerger):
    """Merge survey results: combine all papers, deduplicate by ID, union open problems."""

    async def merge(
        self,
        results: dict[str, AgentResult],
        task: Task | None,
        bus: KnowledgeBus,
    ) -> AgentResult:
        valid = self._filter_successes(results)

        # Collect papers from all models
        per_model_counts: dict[str, int] = {}
        all_papers: list[tuple[str, dict]] = []  # (model_name, paper_dict)

        for model_name, result in valid.items():
            papers = result.output.get("papers", [])
            per_model_counts[model_name] = len(papers)
            for paper in papers:
                all_papers.append((model_name, paper))

        # Deduplicate by arxiv_id (or title as fallback)
        merged_papers: dict[str, dict] = {}  # key -> paper
        paper_sources: dict[str, list[str]] = {}  # key -> [model_names]

        for model_name, paper in all_papers:
            key = paper.get("arxiv_id") or paper.get("title", "").lower().strip()
            if not key:
                continue

            if key in merged_papers:
                paper_sources[key].append(model_name)
                # Keep the richer version (longer abstract)
                existing = merged_papers[key]
                if len(paper.get("abstract", "")) > len(existing.get("abstract", "")):
                    paper["source_models"] = paper_sources[key]
                    merged_papers[key] = paper
                else:
                    existing["source_models"] = paper_sources[key]
            else:
                merged_papers[key] = paper
                paper_sources[key] = [model_name]
                paper["source_models"] = [model_name]

        merged_list = list(merged_papers.values())
        overlap_count = sum(1 for sources in paper_sources.values() if len(sources) > 1)
        total = len(merged_list)

        # Union open problems and key objects
        all_problems: list[str] = []
        all_objects: list[str] = []
        seen_problems: set[str] = set()
        seen_objects: set[str] = set()

        for result in valid.values():
            for p in result.output.get("open_problems", []):
                p_str = str(p)
                if p_str not in seen_problems:
                    all_problems.append(p_str)
                    seen_problems.add(p_str)
            for o in result.output.get("key_mathematical_objects", []):
                o_str = str(o)
                if o_str not in seen_objects:
                    all_objects.append(o_str)
                    seen_objects.add(o_str)

        # Store stats on bus
        bus.put("ensemble_survey_stats", {
            "per_model": per_model_counts,
            "merged_total": total,
            "overlap_count": overlap_count,
            "overlap_ratio": round(overlap_count / max(total, 1), 2),
        })

        # Build merged output
        first_result = next(iter(valid.values()))
        merged_output = dict(first_result.output)
        merged_output["papers"] = merged_list
        merged_output["open_problems"] = all_problems
        merged_output["key_mathematical_objects"] = all_objects

        # Combine token usage
        total_tokens: dict[str, int] = {"input": 0, "output": 0}
        for result in valid.values():
            for k in ("input", "output"):
                total_tokens[k] += result.token_usage.get(k, 0)

        return AgentResult(
            task_id=first_result.task_id,
            agent_role=first_result.agent_role,
            success=True,
            output=merged_output,
            text_summary=f"Ensemble survey: {total} papers from {len(valid)} models (overlap: {overlap_count})",
            token_usage=total_tokens,
        )
