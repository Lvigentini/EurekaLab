"""Integration tests — VersionStore wired into KnowledgeBus."""
import json
import pytest
from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.types.artifacts import ResearchBrief, Bibliography, Paper


@pytest.fixture
def bus(tmp_path, monkeypatch) -> KnowledgeBus:
    monkeypatch.setattr("eurekalab.config.settings.eurekalab_dir", tmp_path)
    b = KnowledgeBus("test-int-001")
    b._session_dir = tmp_path / "runs" / "test-int-001"
    return b


def test_persist_incremental_creates_version(bus):
    bus.put_research_brief(ResearchBrief(
        session_id="test-int-001",
        input_mode="exploration",
        domain="test",
        query="test",
    ))
    bus.persist_incremental(completed_stage="survey")
    assert bus.version_store is not None
    assert bus.version_store.head is not None
    assert bus.version_store.head.trigger == "stage:survey:completed"


def test_multiple_stages_create_multiple_versions(bus):
    bus.put_research_brief(ResearchBrief(
        session_id="test-int-001",
        input_mode="exploration",
        domain="test",
        query="test",
    ))
    bus.persist_incremental(completed_stage="survey")
    bus.persist_incremental(completed_stage="ideation")
    versions = bus.version_store.log()
    assert len(versions) == 2


def test_version_store_still_writes_stage_progress(bus):
    bus.persist_incremental(completed_stage="survey")
    marker = bus._session_dir / "_stage_progress.json"
    assert marker.exists()
    data = json.loads(marker.read_text())
    assert "survey" in data["completed_stages"]


def test_failed_stage_recorded_in_version(bus):
    bus.persist_incremental(completed_stage="survey_FAILED")
    head = bus.version_store.head
    assert head is not None
    assert "FAILED" in head.trigger


def test_version_store_loaded_on_bus_load(bus, tmp_path):
    bus.put_research_brief(ResearchBrief(
        session_id="test-int-001",
        input_mode="exploration",
        domain="test",
        query="test",
    ))
    bus.persist_incremental(completed_stage="survey")
    restored = KnowledgeBus.load("test-int-001", tmp_path / "runs" / "test-int-001")
    assert restored.version_store is not None
    assert len(restored.version_store.log()) == 1


def test_version_store_uses_sqlite(bus, tmp_path):
    bus.put_research_brief(ResearchBrief(
        session_id="test-int-001",
        input_mode="exploration",
        domain="test",
        query="test",
    ))
    bus.persist_incremental(completed_stage="survey")
    # Verify SQLite DB was created
    db_path = tmp_path / "eurekalab.db"
    assert db_path.exists()
