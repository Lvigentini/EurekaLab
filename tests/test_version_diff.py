"""Tests for version diff logic."""
import pytest
from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.types.artifacts import (
    Bibliography, Paper, ProofRecord, ResearchBrief, TheoryState,
)
from eurekalab.versioning.diff import diff_versions
from eurekalab.versioning.store import VersionStore


@pytest.fixture
def store(tmp_path) -> VersionStore:
    return VersionStore("test-diff-001", tmp_path / "runs" / "test-diff-001")


def _make_bus(domain="ML theory", papers=None, proven=None) -> KnowledgeBus:
    bus = KnowledgeBus("test-diff-001")
    bus.put_research_brief(ResearchBrief(
        session_id="test-diff-001",
        input_mode="exploration",
        domain=domain,
        query="test",
    ))
    if papers:
        bus.put_bibliography(Bibliography(
            session_id="test-diff-001",
            papers=[Paper(paper_id=pid, title=t, authors=[]) for pid, t in papers],
        ))
    if proven is not None:
        state = TheoryState(
            session_id="test-diff-001",
            theorem_id="thm-001",
            informal_statement="test",
            status="in_progress",
        )
        for lid, stmt in proven:
            state.proven_lemmas[lid] = ProofRecord(
                lemma_id=lid, proof_text=stmt,
            )
        bus.put_theory_state(state)
    return bus


def test_diff_detects_added_papers(store):
    bus1 = _make_bus(papers=[("p1", "Paper One")])
    bus2 = _make_bus(papers=[("p1", "Paper One"), ("p2", "Paper Two")])
    v1 = store.commit(bus1, trigger="v1")
    v2 = store.commit(bus2, trigger="v2")
    changes = diff_versions(store, v1.version_number, v2.version_number)
    assert any("Paper Two" in c or "p2" in c for c in changes)


def test_diff_detects_proven_lemma(store):
    bus1 = _make_bus(proven=[])
    bus2 = _make_bus(proven=[("L1", "Concentration bound")])
    v1 = store.commit(bus1, trigger="v1")
    v2 = store.commit(bus2, trigger="v2")
    changes = diff_versions(store, v1.version_number, v2.version_number)
    assert any("L1" in c or "lemma" in c.lower() for c in changes)


def test_diff_detects_domain_change(store):
    bus1 = _make_bus(domain="ML theory")
    bus2 = _make_bus(domain="Information theory")
    v1 = store.commit(bus1, trigger="v1")
    v2 = store.commit(bus2, trigger="v2")
    changes = diff_versions(store, v1.version_number, v2.version_number)
    assert any("domain" in c.lower() or "Information theory" in c for c in changes)


def test_diff_identical_versions(store):
    bus = _make_bus()
    v1 = store.commit(bus, trigger="v1")
    v2 = store.commit(bus, trigger="v2")
    changes = diff_versions(store, v1.version_number, v2.version_number)
    assert len(changes) == 0 or all("no changes" in c.lower() for c in changes)
