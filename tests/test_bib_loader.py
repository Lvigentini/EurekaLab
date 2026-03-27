"""Tests for BibLoader — .bib file parsing and PDF matching."""
import pytest
from pathlib import Path
from eurekalab.analyzers.bib_loader import BibLoader
from eurekalab.types.artifacts import Paper


SAMPLE_BIB = """\
@article{smith2024,
  title = {Optimal Bounds for Contextual Bandits},
  author = {Smith, John and Doe, Jane},
  year = {2024},
  journal = {arXiv preprint arXiv:2401.12345},
}

@inproceedings{jones2023,
  title = {Concentration Inequalities for RL},
  author = {Jones, Alice},
  year = {2023},
  booktitle = {NeurIPS},
}

@misc{noauthor2022,
  title = {A Survey of Methods},
  year = {2022},
}
"""


@pytest.fixture
def bib_file(tmp_path) -> Path:
    path = tmp_path / "references.bib"
    path.write_text(SAMPLE_BIB)
    return path


def test_load_parses_all_entries(bib_file):
    papers = BibLoader.load_bib(bib_file)
    assert len(papers) == 3


def test_load_extracts_title(bib_file):
    papers = BibLoader.load_bib(bib_file)
    titles = {p.title for p in papers}
    assert "Optimal Bounds for Contextual Bandits" in titles


def test_load_extracts_authors(bib_file):
    papers = BibLoader.load_bib(bib_file)
    smith = next(p for p in papers if "Optimal" in p.title)
    assert len(smith.authors) == 2
    assert any("Smith" in a for a in smith.authors)


def test_load_extracts_year(bib_file):
    papers = BibLoader.load_bib(bib_file)
    smith = next(p for p in papers if "Optimal" in p.title)
    assert smith.year == 2024


def test_load_extracts_arxiv_id(bib_file):
    papers = BibLoader.load_bib(bib_file)
    smith = next(p for p in papers if "Optimal" in p.title)
    assert smith.arxiv_id == "2401.12345"


def test_load_sets_source_bib_import(bib_file):
    papers = BibLoader.load_bib(bib_file)
    assert all(p.source == "bib_import" for p in papers)


def test_load_sets_content_tier_metadata(bib_file):
    papers = BibLoader.load_bib(bib_file)
    assert all(p.content_tier == "metadata" for p in papers)


def test_load_handles_missing_author(bib_file):
    papers = BibLoader.load_bib(bib_file)
    noauth = next(p for p in papers if "Survey" in p.title)
    assert noauth.authors == [] or noauth.authors == [""]


def test_match_pdfs(bib_file, tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "2401.12345.pdf").write_bytes(b"%PDF-fake")
    papers = BibLoader.load_bib(bib_file)
    matched = BibLoader.match_pdfs(papers, pdf_dir)
    smith = next(p for p in matched if "Optimal" in p.title)
    assert smith.local_pdf_path is not None


def test_match_pdfs_no_match(bib_file, tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    papers = BibLoader.load_bib(bib_file)
    matched = BibLoader.match_pdfs(papers, pdf_dir)
    assert all(p.local_pdf_path is None for p in matched)
