"""Tests for SessionDB SQLite backend."""
import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from eurekalab.storage.db import SessionDB, SessionRecord


@pytest.fixture
def db(tmp_path) -> SessionDB:
    return SessionDB(tmp_path / "test.db")


def test_create_session(db):
    rec = db.create_session(
        session_id="sess-001",
        domain="ML theory",
        query="prove bounds",
        mode="exploration",
    )
    assert rec.session_id == "sess-001"
    assert rec.domain == "ML theory"
    assert rec.status == "running"


def test_get_session(db):
    db.create_session(session_id="sess-001", domain="ML theory", query="q", mode="exploration")
    rec = db.get_session("sess-001")
    assert rec is not None
    assert rec.domain == "ML theory"


def test_get_session_not_found(db):
    assert db.get_session("nonexistent") is None


def test_update_session_status(db):
    db.create_session(session_id="sess-001", domain="test", query="q", mode="detailed")
    db.update_session("sess-001", status="completed")
    rec = db.get_session("sess-001")
    assert rec.status == "completed"


def test_list_sessions(db):
    db.create_session(session_id="s1", domain="ML", query="q1", mode="exploration")
    db.create_session(session_id="s2", domain="Physics", query="q2", mode="detailed")
    sessions = db.list_sessions()
    assert len(sessions) == 2


def test_list_sessions_ordered_by_date(db):
    db.create_session(session_id="s1", domain="Old", query="q1", mode="exploration")
    db.create_session(session_id="s2", domain="New", query="q2", mode="detailed")
    sessions = db.list_sessions()
    assert sessions[0].session_id == "s2"  # newest first


def test_add_version(db):
    db.create_session(session_id="sess-001", domain="test", query="q", mode="detailed")
    db.add_version(
        session_id="sess-001",
        version_number=1,
        trigger="stage:survey:completed",
        completed_stages=["survey"],
        snapshot_json='{"test": true}',
        changes=["Added survey results"],
    )
    versions = db.get_versions("sess-001")
    assert len(versions) == 1
    assert versions[0]["trigger"] == "stage:survey:completed"


def test_get_versions_ordered(db):
    db.create_session(session_id="sess-001", domain="test", query="q", mode="detailed")
    db.add_version("sess-001", 1, "stage:survey:completed", ["survey"], "{}", [])
    db.add_version("sess-001", 2, "stage:ideation:completed", ["survey", "ideation"], "{}", [])
    versions = db.get_versions("sess-001")
    assert len(versions) == 2
    assert versions[0]["version_number"] == 1
    assert versions[1]["version_number"] == 2


def test_get_version(db):
    db.create_session(session_id="sess-001", domain="test", query="q", mode="detailed")
    db.add_version("sess-001", 1, "test-trigger", ["survey"], '{"snap": 1}', ["change1"])
    v = db.get_version("sess-001", 1)
    assert v is not None
    assert v["trigger"] == "test-trigger"
    assert v["snapshot_json"] == '{"snap": 1}'


def test_get_version_not_found(db):
    db.create_session(session_id="sess-001", domain="test", query="q", mode="detailed")
    assert db.get_version("sess-001", 99) is None


def test_get_latest_version(db):
    db.create_session(session_id="sess-001", domain="test", query="q", mode="detailed")
    db.add_version("sess-001", 1, "v1", [], "{}", [])
    db.add_version("sess-001", 2, "v2", [], "{}", [])
    latest = db.get_latest_version("sess-001")
    assert latest is not None
    assert latest["version_number"] == 2


def test_delete_session(db):
    db.create_session(session_id="sess-001", domain="test", query="q", mode="detailed")
    db.add_version("sess-001", 1, "v1", [], "{}", [])
    db.delete_session("sess-001")
    assert db.get_session("sess-001") is None
    assert db.get_versions("sess-001") == []


def test_list_sessions_older_than(db):
    db.create_session(session_id="s-old", domain="old", query="q", mode="detailed")
    # Manually update created_at to make it old
    db._conn.execute(
        "UPDATE sessions SET created_at = ? WHERE session_id = ?",
        ((datetime.now(timezone.utc) - timedelta(days=60)).isoformat(), "s-old"),
    )
    db._conn.commit()
    db.create_session(session_id="s-new", domain="new", query="q", mode="detailed")
    old = db.list_sessions_older_than(days=30)
    assert len(old) == 1
    assert old[0].session_id == "s-old"


def test_db_survives_reopen(tmp_path):
    db1 = SessionDB(tmp_path / "test.db")
    db1.create_session(session_id="s1", domain="test", query="q", mode="detailed")
    db1.add_version("s1", 1, "trigger", ["survey"], "{}", [])
    db1.close()

    db2 = SessionDB(tmp_path / "test.db")
    rec = db2.get_session("s1")
    assert rec is not None
    versions = db2.get_versions("s1")
    assert len(versions) == 1
    db2.close()


def test_update_session_completed_stages(db):
    db.create_session(session_id="sess-001", domain="test", query="q", mode="detailed")
    db.update_session("sess-001", completed_stages=["survey", "ideation"])
    rec = db.get_session("sess-001")
    assert rec.completed_stages == ["survey", "ideation"]
