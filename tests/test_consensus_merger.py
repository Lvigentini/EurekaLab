# tests/test_consensus_merger.py
"""Tests for ConsensusMerger — independent experiment validation."""
import pytest
from eurekalab.ensemble.mergers.consensus import ConsensusMerger
from eurekalab.types.agents import AgentResult, AgentRole
from eurekalab.knowledge_bus.bus import KnowledgeBus


def _make_experiment_result(bounds, alignment_score):
    return AgentResult(
        task_id="t1",
        agent_role=AgentRole.EXPERIMENT,
        success=True,
        output={
            "bounds": bounds,
            "alignment_score": alignment_score,
            "code": "print('test')",
        },
        text_summary="",
    )


@pytest.fixture
def bus():
    return KnowledgeBus("test")


@pytest.mark.asyncio
async def test_consensus_confirmed_bounds(bus):
    results = {
        "claude": _make_experiment_result(
            [{"name": "regret", "theoretical": 1.0, "empirical": 0.95}], 0.9
        ),
        "gemini": _make_experiment_result(
            [{"name": "regret", "theoretical": 1.0, "empirical": 0.97}], 0.92
        ),
    }
    merger = ConsensusMerger()
    merged = await merger.merge(results, None, bus)
    assert len(merged.output["confirmed_bounds"]) == 1
    assert len(merged.output["contested_bounds"]) == 0
    assert merged.output["agreement_ratio"] == 1.0


@pytest.mark.asyncio
async def test_consensus_contested_bounds(bus):
    results = {
        "claude": _make_experiment_result(
            [{"name": "error", "theoretical": 0.01, "empirical": 0.02}], 0.8
        ),
        "gemini": _make_experiment_result(
            [{"name": "error", "theoretical": 0.01, "empirical": 0.5}], 0.4
        ),
    }
    merger = ConsensusMerger()
    merged = await merger.merge(results, None, bus)
    assert len(merged.output["contested_bounds"]) == 1
    assert merged.output["agreement_ratio"] == 0.0


@pytest.mark.asyncio
async def test_consensus_single_model_passthrough(bus):
    results = {
        "claude": _make_experiment_result(
            [{"name": "bound", "theoretical": 1.0, "empirical": 0.9}], 0.85
        ),
    }
    merger = ConsensusMerger()
    merged = await merger.merge(results, None, bus)
    assert merged.output["alignment_score"] == 0.85
