# tests/test_ensemble_orchestrator.py
"""Tests for EnsembleOrchestrator — dispatch + merge coordination."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from eurekalab.ensemble.orchestrator import EnsembleOrchestrator
from eurekalab.ensemble.model_pool import ModelPool
from eurekalab.ensemble.config import EnsembleConfig
from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.types.agents import AgentResult, AgentRole
from eurekalab.types.tasks import Task


@pytest.fixture
def bus():
    return KnowledgeBus("test")


@pytest.fixture
def pool():
    p = ModelPool()
    p.register("claude", MagicMock(), "claude-sonnet-4-6", "anthropic")
    p.register("gemini", MagicMock(), "gemini-2.0-flash", "google")
    return p


def test_is_ensemble_stage_true():
    config = EnsembleConfig()
    config.update_stage("survey", ["claude", "gemini"], "union")
    orch = EnsembleOrchestrator(ModelPool(), config, KnowledgeBus("t"), "auto")
    assert orch.is_ensemble_stage("survey")


def test_is_ensemble_stage_false_single():
    config = EnsembleConfig()
    orch = EnsembleOrchestrator(ModelPool(), config, KnowledgeBus("t"), "auto")
    assert not orch.is_ensemble_stage("survey")


@pytest.mark.asyncio
async def test_single_model_fast_path(pool, bus):
    config = EnsembleConfig()
    config.update_stage("survey", ["claude"], "single")
    orch = EnsembleOrchestrator(pool, config, bus, "none")

    expected = AgentResult(
        task_id="t1", agent_role=AgentRole.SURVEY, success=True,
        output={"papers": []}, text_summary="",
    )
    mock_agent = MagicMock()
    mock_agent.execute = AsyncMock(return_value=expected)

    task = Task(task_id="t1", name="survey", agent_role="survey")
    result = await orch.execute_stage(task, lambda client: mock_agent)
    assert result is expected
