"""Tests for incremental bus persistence."""
import json
import pytest
from pathlib import Path
from eurekaclaw.knowledge_bus.bus import KnowledgeBus


@pytest.fixture
def bus(tmp_path):
    b = KnowledgeBus("test-session-123")
    b._session_dir = tmp_path / "sessions" / "test-session-123"
    return b


def test_persist_incremental_creates_dir(bus):
    bus.put("test_key", {"hello": "world"})
    bus.persist_incremental()
    assert bus._session_dir.exists()


def test_persist_incremental_writes_artifacts(bus):
    bus.put("test_key", {"hello": "world"})
    bus.persist_incremental()
    path = bus._session_dir / "test_key.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["hello"] == "world"


def test_persist_incremental_writes_stage_marker(bus):
    bus.persist_incremental(completed_stage="survey")
    marker = bus._session_dir / "_stage_progress.json"
    assert marker.exists()
    data = json.loads(marker.read_text())
    assert "survey" in data["completed_stages"]


def test_persist_incremental_accumulates_stages(bus):
    bus.persist_incremental(completed_stage="survey")
    bus.persist_incremental(completed_stage="ideation")
    marker = bus._session_dir / "_stage_progress.json"
    data = json.loads(marker.read_text())
    assert data["completed_stages"] == ["survey", "ideation"]
