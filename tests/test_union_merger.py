# tests/test_union_merger.py
"""Tests for UnionMerger — combines survey results with deduplication."""
import pytest
from eurekalab.ensemble.mergers.union import UnionMerger
from eurekalab.types.agents import AgentResult, AgentRole
from eurekalab.knowledge_bus.bus import KnowledgeBus


def _make_result(papers, open_problems=None):
    return AgentResult(
        task_id="t1",
        agent_role=AgentRole.SURVEY,
        success=True,
        output={
            "papers": papers,
            "open_problems": open_problems or [],
            "key_mathematical_objects": [],
        },
        text_summary="",
    )


@pytest.fixture
def bus():
    return KnowledgeBus("test")


@pytest.mark.asyncio
async def test_union_dedup_by_arxiv_id(bus):
    results = {
        "claude": _make_result([
            {"arxiv_id": "2301.001", "title": "Paper A", "abstract": "Short"},
        ]),
        "gemini": _make_result([
            {"arxiv_id": "2301.001", "title": "Paper A", "abstract": "Longer abstract here"},
            {"arxiv_id": "2301.002", "title": "Paper B", "abstract": "New"},
        ]),
    }
    merger = UnionMerger()
    merged = await merger.merge(results, None, bus)
    papers = merged.output["papers"]
    assert len(papers) == 2
    # Should keep the richer version (longer abstract)
    paper_a = next(p for p in papers if p["arxiv_id"] == "2301.001")
    assert "Longer" in paper_a["abstract"]


@pytest.mark.asyncio
async def test_union_tags_source_models(bus):
    results = {
        "claude": _make_result([{"arxiv_id": "2301.001", "title": "P1", "abstract": "a"}]),
        "gemini": _make_result([{"arxiv_id": "2301.001", "title": "P1", "abstract": "a"}]),
    }
    merger = UnionMerger()
    merged = await merger.merge(results, None, bus)
    paper = merged.output["papers"][0]
    assert "claude" in paper["source_models"]
    assert "gemini" in paper["source_models"]


@pytest.mark.asyncio
async def test_union_stats_on_bus(bus):
    results = {
        "claude": _make_result([{"arxiv_id": "1", "title": "A", "abstract": ""}]),
        "gemini": _make_result([
            {"arxiv_id": "1", "title": "A", "abstract": ""},
            {"arxiv_id": "2", "title": "B", "abstract": ""},
        ]),
    }
    merger = UnionMerger()
    await merger.merge(results, None, bus)
    stats = bus.get("ensemble_survey_stats")
    assert stats["per_model"]["claude"] == 1
    assert stats["per_model"]["gemini"] == 2
    assert stats["merged_total"] == 2
    assert stats["overlap_count"] == 1


@pytest.mark.asyncio
async def test_union_handles_partial_failure(bus):
    results = {
        "claude": _make_result([{"arxiv_id": "1", "title": "A", "abstract": ""}]),
        "gemini": AgentResult(
            task_id="t1", agent_role=AgentRole.SURVEY, success=False,
            output={}, text_summary="", error="API error",
        ),
    }
    merger = UnionMerger()
    merged = await merger.merge(results, None, bus)
    assert len(merged.output["papers"]) == 1
