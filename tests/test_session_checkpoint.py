"""Tests for full-pipeline session checkpoint."""
import json
import pytest
from eurekaclaw.orchestrator.session_checkpoint import SessionCheckpoint


@pytest.fixture
def cp(tmp_path, monkeypatch):
    monkeypatch.setattr("eurekaclaw.config.settings.eurekaclaw_dir", tmp_path)
    return SessionCheckpoint("test-session-456")


def test_detect_last_stage_from_marker(cp, tmp_path):
    runs_dir = tmp_path / "runs" / "test-session-456"
    runs_dir.mkdir(parents=True)
    marker = runs_dir / "_stage_progress.json"
    marker.write_text(json.dumps({
        "session_id": "test-session-456",
        "completed_stages": ["survey", "ideation"],
    }))
    last, stages = cp.detect_progress()
    assert last == "ideation"
    assert stages == ["survey", "ideation"]


def test_detect_no_progress(cp):
    last, stages = cp.detect_progress()
    assert last is None
    assert stages == []


def test_next_stage_after_survey(cp):
    assert cp.next_stage_after("survey") == "ideation"


def test_next_stage_after_ideation(cp):
    assert cp.next_stage_after("ideation") == "direction_selection_gate"


def test_next_stage_after_last(cp):
    assert cp.next_stage_after("writer") is None
