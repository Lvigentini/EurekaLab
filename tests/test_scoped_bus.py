# tests/test_scoped_bus.py
"""Tests for ScopedBus — namespaced bus wrapper for parallel isolation."""
import pytest
from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.ensemble.scoped_bus import ScopedBus


@pytest.fixture
def bus():
    return KnowledgeBus("test-session")


def test_scoped_put_namespaces_key(bus):
    scoped = ScopedBus(bus, namespace="claude")
    scoped.put("result", {"score": 0.9})
    assert bus.get("result__claude") == {"score": 0.9}
    assert bus.get("result") is None


def test_scoped_get_reads_namespaced(bus):
    scoped = ScopedBus(bus, namespace="gemini")
    bus._store["result__gemini"] = {"score": 0.8}
    assert scoped.get("result") == {"score": 0.8}


def test_scoped_get_falls_back_to_canonical(bus):
    scoped = ScopedBus(bus, namespace="claude")
    bus._store["research_brief"] = "shared_brief"
    assert scoped.get("research_brief") == "shared_brief"


def test_two_scopes_dont_collide(bus):
    scope_a = ScopedBus(bus, namespace="claude")
    scope_b = ScopedBus(bus, namespace="gemini")
    scope_a.put("result", {"model": "claude"})
    scope_b.put("result", {"model": "gemini"})
    assert bus.get("result__claude")["model"] == "claude"
    assert bus.get("result__gemini")["model"] == "gemini"


def test_read_only_methods_delegate(bus):
    from eurekalab.types.artifacts import ResearchBrief
    brief = ResearchBrief(session_id="test", domain="test", query="test", input_mode="detailed")
    bus.put_research_brief(brief)
    scoped = ScopedBus(bus, namespace="claude")
    assert scoped.get_research_brief() is not None
    assert scoped.get_research_brief().domain == "test"
