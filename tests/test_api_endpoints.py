"""Tests for new UI API endpoints."""
import json
import threading
import time
import pytest
import urllib.request
import urllib.error
from pathlib import Path


@pytest.fixture
def server_url(tmp_path, monkeypatch):
    """Start a test UI server on a random port with temp storage."""
    monkeypatch.setattr("eurekaclaw.config.settings.eurekaclaw_dir", tmp_path)

    # Create runs dir
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    from eurekaclaw.ui.server import bind_ui_server
    server = bind_ui_server("127.0.0.1", 0)  # port 0 = random
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)

    url = f"http://127.0.0.1:{port}"
    yield url

    server.shutdown()


def _get(url: str, path: str) -> dict:
    resp = urllib.request.urlopen(f"{url}{path}")
    return json.loads(resp.read())


def _post(url: str, path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{url}{path}", data=data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def _post_expect_error(url: str, path: str, body: dict) -> int:
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{url}{path}", data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req)
        return 200
    except urllib.error.HTTPError as e:
        return e.code


# ── GET /api/sessions ────────────────────────────────────────────

def test_get_sessions_empty(server_url):
    result = _get(server_url, "/api/sessions")
    assert "sessions" in result
    assert isinstance(result["sessions"], list)


def test_get_sessions_with_data(server_url, tmp_path):
    from eurekaclaw.storage.db import SessionDB
    db = SessionDB(tmp_path / "eurekaclaw.db")
    db.create_session("test-001", domain="ML theory", query="test q", mode="exploration")
    result = _get(server_url, "/api/sessions")
    assert len(result["sessions"]) == 1
    assert result["sessions"][0]["domain"] == "ML theory"


# ── GET /api/runs/<id>/versions ──────────────────────────────────

def test_get_versions_no_session(server_url):
    try:
        _get(server_url, "/api/runs/nonexistent/versions")
        assert False, "Should have returned 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_get_versions_with_data(server_url, tmp_path):
    # Create a session with a version
    session_id = "test-ver-001"
    session_dir = tmp_path / "runs" / session_id
    session_dir.mkdir(parents=True)

    from eurekaclaw.storage.db import SessionDB
    db = SessionDB(tmp_path / "eurekaclaw.db")
    db.create_session(session_id, domain="test", query="q", mode="detailed")
    db.add_version(session_id, 1, "stage:survey:completed", ["survey"], '{"test": true}', ["Added survey"])

    result = _get(server_url, f"/api/runs/{session_id}/versions")
    assert len(result["versions"]) == 1
    assert result["versions"][0]["trigger"] == "stage:survey:completed"


# ── GET /api/runs/<id>/content-gap ───────────────────────────────

def test_get_content_gap_no_bib(server_url):
    try:
        _get(server_url, "/api/runs/nonexistent/content-gap")
        assert False, "Should 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_get_content_gap_with_bib(server_url, tmp_path):
    session_id = "test-gap-001"
    session_dir = tmp_path / "runs" / session_id
    session_dir.mkdir(parents=True)
    from eurekaclaw.types.artifacts import Bibliography, Paper
    bib = Bibliography(
        session_id=session_id,
        papers=[
            Paper(paper_id="p1", title="Full", authors=[], content_tier="full_text"),
            Paper(paper_id="p2", title="Abstract Only", authors=[], content_tier="abstract"),
        ],
    )
    (session_dir / "bibliography.json").write_text(bib.model_dump_json())

    result = _get(server_url, f"/api/runs/{session_id}/content-gap")
    assert result["full_text"] == 1
    assert result["abstract_only"] == 1
    assert result["has_gaps"] is True


# ── GET /api/runs/<id>/ideation-pool ─────────────────────────────

def test_get_ideation_pool_empty(server_url):
    result = _get(server_url, "/api/runs/nonexistent/ideation-pool")
    assert result["directions"] == []
    assert result["version"] == 0


def test_get_ideation_pool_with_data(server_url, tmp_path):
    session_id = "test-pool-001"
    session_dir = tmp_path / "runs" / session_id
    session_dir.mkdir(parents=True)
    from eurekaclaw.orchestrator.ideation_pool import IdeationPool
    pool = IdeationPool()
    pool.inject_idea("Test idea", source="user")
    (session_dir / "ideation_pool.json").write_text(pool.model_dump_json())

    result = _get(server_url, f"/api/runs/{session_id}/ideation-pool")
    assert len(result["injected_ideas"]) == 1
    assert result["version"] == 1


# ── GET /api/zotero/status ───────────────────────────────────────

def test_get_zotero_status_unconfigured(server_url):
    result = _get(server_url, "/api/zotero/status")
    assert result["configured"] is False


# ── POST /api/runs/<id>/ideation-pool/inject ─────────────────────

def test_inject_idea(server_url, tmp_path):
    session_id = "test-inject-001"
    session_dir = tmp_path / "runs" / session_id
    session_dir.mkdir(parents=True)
    # Create minimal session artifacts so bus.load works
    from eurekaclaw.types.artifacts import ResearchBrief
    brief = ResearchBrief(session_id=session_id, input_mode="exploration", domain="test", query="q")
    (session_dir / "research_brief.json").write_text(brief.model_dump_json())
    # Create session in DB
    from eurekaclaw.storage.db import SessionDB
    db = SessionDB(tmp_path / "eurekaclaw.db")
    db.create_session(session_id, domain="test", query="q", mode="exploration")

    result = _post(server_url, f"/api/runs/{session_id}/ideation-pool/inject", {
        "type": "idea",
        "text": "What about spectral methods?",
    })
    assert result["ok"] is True
    assert result["pool_version"] >= 1


def test_inject_empty_text(server_url):
    code = _post_expect_error(server_url, "/api/runs/fake/ideation-pool/inject", {
        "type": "idea",
        "text": "",
    })
    assert code == 400


# ── POST /api/sessions/clean ─────────────────────────────────────

def test_clean_sessions_none_to_clean(server_url):
    result = _post(server_url, "/api/sessions/clean", {"older_than_days": 30})
    assert result["removed"] == 0
