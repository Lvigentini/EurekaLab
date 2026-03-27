"""Tests for Paper content tier tracking."""
import pytest
from eurekalab.types.artifacts import Paper


def test_paper_default_content_tier():
    p = Paper(paper_id="p1", title="Test", authors=["A"])
    assert p.content_tier == "metadata"


def test_paper_content_tier_full_text():
    p = Paper(paper_id="p1", title="Test", authors=["A"],
              content_tier="full_text", full_text="some content")
    assert p.content_tier == "full_text"
    assert p.full_text == "some content"


def test_paper_local_pdf_path():
    p = Paper(paper_id="p1", title="Test", authors=["A"],
              local_pdf_path="/tmp/paper.pdf")
    assert p.local_pdf_path == "/tmp/paper.pdf"


def test_paper_source_default():
    p = Paper(paper_id="p1", title="Test", authors=["A"])
    assert p.source == "search"


def test_paper_source_zotero():
    p = Paper(paper_id="p1", title="Test", authors=["A"], source="zotero")
    assert p.source == "zotero"


def test_paper_user_notes():
    p = Paper(paper_id="p1", title="Test", authors=["A"],
              user_notes="Important theorem in section 3")
    assert p.user_notes == "Important theorem in section 3"


def test_paper_backward_compatible():
    p = Paper(
        paper_id="old-paper", title="Old Style", authors=["B"],
        year=2024, abstract="An abstract", venue="NeurIPS",
        arxiv_id="2401.12345", relevance_score=0.8,
    )
    assert p.content_tier == "metadata"
    assert p.full_text is None
    assert p.local_pdf_path is None
    assert p.source == "search"


from eurekalab.types.artifacts import Bibliography
from eurekalab.analyzers.content_gap import ContentGapAnalyzer, ContentGapReport


def test_gap_report_categorizes_tiers():
    papers = [
        Paper(paper_id="p1", title="Full", authors=[], content_tier="full_text"),
        Paper(paper_id="p2", title="Abstract", authors=[], content_tier="abstract"),
        Paper(paper_id="p3", title="Meta", authors=[], content_tier="metadata"),
        Paper(paper_id="p4", title="Missing", authors=[], content_tier="missing"),
    ]
    bib = Bibliography(session_id="test", papers=papers)
    report = ContentGapAnalyzer.analyze(bib)
    assert len(report.full_text) == 1
    assert len(report.abstract_only) == 1
    assert len(report.metadata_only) == 1
    assert len(report.missing) == 1


def test_gap_report_empty_bibliography():
    bib = Bibliography(session_id="test", papers=[])
    report = ContentGapAnalyzer.analyze(bib)
    assert len(report.full_text) == 0
    assert len(report.abstract_only) == 0


def test_gap_report_all_full_text():
    papers = [
        Paper(paper_id="p1", title="A", authors=[], content_tier="full_text"),
        Paper(paper_id="p2", title="B", authors=[], content_tier="full_text"),
    ]
    bib = Bibliography(session_id="test", papers=papers)
    report = ContentGapAnalyzer.analyze(bib)
    assert report.has_gaps is False


def test_gap_report_has_gaps():
    papers = [
        Paper(paper_id="p1", title="A", authors=[], content_tier="full_text"),
        Paper(paper_id="p2", title="B", authors=[], content_tier="abstract"),
    ]
    bib = Bibliography(session_id="test", papers=papers)
    report = ContentGapAnalyzer.analyze(bib)
    assert report.has_gaps is True
