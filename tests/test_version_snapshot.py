"""Tests for BusSnapshot serialization."""
import json
import pytest
from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.types.artifacts import ResearchBrief, Bibliography, Paper, TheoryState
from eurekalab.versioning.snapshot import BusSnapshot


@pytest.fixture
def populated_bus() -> KnowledgeBus:
    bus = KnowledgeBus("test-snap-001")
    bus.put_research_brief(ResearchBrief(
        session_id="test-snap-001",
        input_mode="exploration",
        domain="ML theory",
        query="test query",
    ))
    bus.put_bibliography(Bibliography(
        session_id="test-snap-001",
        papers=[Paper(paper_id="p1", title="Paper One", authors=["A"])],
    ))
    bus.put("custom_key", {"foo": "bar"})
    return bus


def test_snapshot_captures_all_artifacts(populated_bus):
    snap = BusSnapshot.from_bus(populated_bus)
    assert "research_brief" in snap.artifacts
    assert "bibliography" in snap.artifacts
    assert "custom_key" in snap.artifacts


def test_snapshot_round_trip_json(populated_bus):
    snap = BusSnapshot.from_bus(populated_bus)
    json_str = snap.to_json()
    restored = BusSnapshot.from_json(json_str)
    assert restored.artifacts.keys() == snap.artifacts.keys()
    assert restored.session_id == snap.session_id


def test_snapshot_restore_to_bus(populated_bus):
    snap = BusSnapshot.from_bus(populated_bus)
    new_bus = snap.to_bus()
    brief = new_bus.get_research_brief()
    assert brief is not None
    assert brief.domain == "ML theory"
    bib = new_bus.get_bibliography()
    assert bib is not None
    assert len(bib.papers) == 1


def test_snapshot_preserves_custom_keys(populated_bus):
    snap = BusSnapshot.from_bus(populated_bus)
    new_bus = snap.to_bus()
    assert new_bus.get("custom_key") == {"foo": "bar"}


def test_snapshot_handles_empty_bus():
    bus = KnowledgeBus("empty-session")
    snap = BusSnapshot.from_bus(bus)
    assert snap.artifacts == {}
    restored = snap.to_bus()
    assert restored.get_research_brief() is None
