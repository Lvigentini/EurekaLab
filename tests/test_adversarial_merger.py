# tests/test_adversarial_merger.py
"""Tests for AdversarialMerger — cross-review ideation directions."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from eurekalab.ensemble.mergers.adversarial import AdversarialMerger
from eurekalab.types.agents import AgentResult, AgentRole
from eurekalab.knowledge_bus.bus import KnowledgeBus


def _make_ideation_result(directions):
    return AgentResult(
        task_id="t1",
        agent_role=AgentRole.IDEATION,
        success=True,
        output={"directions": directions},
        text_summary="",
    )


@pytest.fixture
def bus():
    return KnowledgeBus("test")


@pytest.mark.asyncio
async def test_merge_combines_directions(bus):
    results = {
        "claude": _make_ideation_result([
            {"direction_id": "d1", "title": "Approach A", "hypothesis": "H1",
             "novelty_score": 0.8, "soundness_score": 0.7, "transformative_score": 0.6},
        ]),
        "gemini": _make_ideation_result([
            {"direction_id": "d2", "title": "Approach B", "hypothesis": "H2",
             "novelty_score": 0.9, "soundness_score": 0.8, "transformative_score": 0.7},
        ]),
    }
    merger = AdversarialMerger()
    # Skip cross-review in unit test (requires LLM) — test the merge logic
    merged = await merger._merge_without_review(results, bus)
    assert len(merged.output["directions"]) == 2


@pytest.mark.asyncio
async def test_unique_directions_get_originality_bonus(bus):
    results = {
        "claude": _make_ideation_result([
            {"direction_id": "d1", "title": "Unique Idea", "hypothesis": "H1",
             "novelty_score": 0.8, "soundness_score": 0.7, "transformative_score": 0.6},
        ]),
        "gemini": _make_ideation_result([
            {"direction_id": "d2", "title": "Different Topic", "hypothesis": "H2",
             "novelty_score": 0.7, "soundness_score": 0.6, "transformative_score": 0.5},
        ]),
    }
    merger = AdversarialMerger()
    merged = await merger._merge_without_review(results, bus)
    for d in merged.output["directions"]:
        assert d["consensus"] == "unique"


@pytest.mark.asyncio
async def test_handles_single_model(bus):
    results = {
        "claude": _make_ideation_result([
            {"direction_id": "d1", "title": "Solo", "hypothesis": "H1",
             "novelty_score": 0.8, "soundness_score": 0.7, "transformative_score": 0.6},
        ]),
    }
    merger = AdversarialMerger()
    merged = await merger._merge_without_review(results, bus)
    assert len(merged.output["directions"]) == 1
