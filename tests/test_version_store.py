"""Tests for VersionStore: commit, log, head, checkout."""
import pytest
from eurekaclaw.knowledge_bus.bus import KnowledgeBus
from eurekaclaw.types.artifacts import ResearchBrief
from eurekaclaw.versioning.store import VersionStore, ResearchVersion


@pytest.fixture
def store(tmp_path) -> VersionStore:
    return VersionStore("test-vs-001", tmp_path / "runs" / "test-vs-001")


@pytest.fixture
def bus_v1() -> KnowledgeBus:
    bus = KnowledgeBus("test-vs-001")
    bus.put_research_brief(ResearchBrief(
        session_id="test-vs-001",
        input_mode="exploration",
        domain="ML theory",
        query="initial query",
    ))
    return bus


@pytest.fixture
def bus_v2() -> KnowledgeBus:
    bus = KnowledgeBus("test-vs-001")
    bus.put_research_brief(ResearchBrief(
        session_id="test-vs-001",
        input_mode="exploration",
        domain="ML theory",
        query="revised query",
    ))
    return bus


def test_commit_creates_version(store, bus_v1):
    v = store.commit(bus_v1, trigger="stage:survey:completed")
    assert v.version_number == 1
    assert v.trigger == "stage:survey:completed"


def test_commit_increments_version_number(store, bus_v1, bus_v2):
    v1 = store.commit(bus_v1, trigger="stage:survey:completed")
    v2 = store.commit(bus_v2, trigger="stage:ideation:completed")
    assert v1.version_number == 1
    assert v2.version_number == 2


def test_head_returns_latest(store, bus_v1, bus_v2):
    store.commit(bus_v1, trigger="stage:survey:completed")
    store.commit(bus_v2, trigger="stage:ideation:completed")
    head = store.head
    assert head is not None
    assert head.version_number == 2


def test_head_none_when_empty(store):
    assert store.head is None


def test_log_returns_all_versions(store, bus_v1, bus_v2):
    store.commit(bus_v1, trigger="stage:survey:completed")
    store.commit(bus_v2, trigger="stage:ideation:completed")
    versions = store.log()
    assert len(versions) == 2
    assert versions[0].version_number == 1
    assert versions[1].version_number == 2


def test_commit_writes_to_disk(store, bus_v1):
    store.commit(bus_v1, trigger="test")
    files = list(store._versions_dir.glob("v*.json"))
    assert len(files) == 1


def test_log_survives_reload(store, bus_v1, bus_v2, tmp_path):
    store.commit(bus_v1, trigger="stage:survey:completed")
    store.commit(bus_v2, trigger="stage:ideation:completed")
    store2 = VersionStore("test-vs-001", tmp_path / "runs" / "test-vs-001")
    versions = store2.log()
    assert len(versions) == 2
    assert store2.head.version_number == 2


def test_commit_records_completed_stages(store, bus_v1, bus_v2):
    store.commit(bus_v1, trigger="stage:survey:completed",
                 completed_stages=["survey"])
    store.commit(bus_v2, trigger="stage:ideation:completed",
                 completed_stages=["survey", "ideation"])
    assert store.head.completed_stages == ["survey", "ideation"]
