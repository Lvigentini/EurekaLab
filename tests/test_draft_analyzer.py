"""Tests for DraftAnalyzer — extract structure from draft papers."""
import pytest
from pathlib import Path
from eurekalab.analyzers.draft_analyzer import DraftAnalyzer, DraftAnalysis


SAMPLE_LATEX = r"""
\documentclass{article}
\title{Optimal Bounds for Contextual Bandits with Linear Payoffs}
\author{John Smith \and Jane Doe}
\begin{document}
\maketitle
\begin{abstract}
We prove optimal regret bounds for contextual bandits with linear payoff functions.
\end{abstract}

\section{Introduction}
This paper addresses the problem of contextual bandits.
We cite prior work \cite{smith2023,jones2024} and build on \cite{lee2022}.

\section{Main Results}
\begin{theorem}[Main Bound]
The regret is bounded by $O(\sqrt{dT \log T})$.
\end{theorem}

\begin{lemma}[Concentration]
For all $\delta > 0$, with probability $1-\delta$...
\end{lemma}

\section{Experiments}
\todo{Add experimental results}

\section{Conclusion}
% TODO: write conclusion

\bibliography{references}
\end{document}
"""

SAMPLE_MARKDOWN = """
# Optimal Bounds for Contextual Bandits

## Abstract
We prove optimal regret bounds for contextual bandits.

## Introduction
This paper addresses contextual bandits. See [@smith2023] and [@jones2024].

## Main Results
**Theorem 1.** The regret is bounded by O(sqrt(dT log T)).

**Lemma 2.** For all delta > 0, with probability 1-delta...

## Experiments
TODO: Add experimental results

## Conclusion
"""


@pytest.fixture
def latex_file(tmp_path) -> Path:
    p = tmp_path / "draft.tex"
    p.write_text(SAMPLE_LATEX)
    return p


@pytest.fixture
def md_file(tmp_path) -> Path:
    p = tmp_path / "draft.md"
    p.write_text(SAMPLE_MARKDOWN)
    return p


def test_analyze_latex_extracts_title(latex_file):
    result = DraftAnalyzer.analyze(latex_file)
    assert "Optimal Bounds" in result.title


def test_analyze_latex_extracts_abstract(latex_file):
    result = DraftAnalyzer.analyze(latex_file)
    assert "regret bounds" in result.abstract


def test_analyze_latex_extracts_citations(latex_file):
    result = DraftAnalyzer.analyze(latex_file)
    assert "smith2023" in result.citation_keys
    assert "jones2024" in result.citation_keys
    assert "lee2022" in result.citation_keys


def test_analyze_latex_extracts_claims(latex_file):
    result = DraftAnalyzer.analyze(latex_file)
    assert len(result.claims) >= 2
    assert any("theorem" in c.lower() or "regret" in c.lower() for c in result.claims)


def test_analyze_latex_detects_todos(latex_file):
    result = DraftAnalyzer.analyze(latex_file)
    assert len(result.gaps) >= 1


def test_analyze_latex_extracts_sections(latex_file):
    result = DraftAnalyzer.analyze(latex_file)
    assert "Introduction" in result.sections
    assert "Main Results" in result.sections


def test_analyze_markdown(md_file):
    result = DraftAnalyzer.analyze(md_file)
    assert "Optimal Bounds" in result.title
    assert len(result.citation_keys) >= 2


def test_analyze_returns_full_text(latex_file):
    result = DraftAnalyzer.analyze(latex_file)
    assert len(result.full_text) > 100


def test_draft_analysis_model():
    da = DraftAnalysis(
        title="Test", abstract="abs", full_text="text",
        citation_keys=["a"], claims=["c"], sections=["s"], gaps=["g"],
    )
    assert da.title == "Test"
