"""BibLoader — parse .bib files into Paper objects and match local PDFs."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import bibtexparser

from eurekalab.types.artifacts import Paper

logger = logging.getLogger(__name__)


def _extract_arxiv_id(fields: dict[str, str]) -> str | None:
    for field_name in ("journal", "eprint", "url", "note", "doi"):
        val = fields.get(field_name, "")
        m = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", val)
        if m:
            return m.group(1)
    return None


def _parse_authors(raw: str) -> list[str]:
    if not raw:
        return []
    parts = [a.strip() for a in raw.split(" and ") if a.strip()]
    return parts


class BibLoader:

    @staticmethod
    def load_bib(bib_path: Path) -> list[Paper]:
        text = bib_path.read_text(encoding="utf-8")
        bib_db = bibtexparser.loads(text)
        papers: list[Paper] = []
        for entry in bib_db.entries:
            # bibtexparser v1: entries are plain dicts
            fields: dict[str, str] = entry  # type: ignore[assignment]
            title = fields.get("title", "").strip("{}")
            authors_raw = fields.get("author", "")
            year_str = fields.get("year", "")
            venue = fields.get("booktitle", "") or fields.get("journal", "")
            arxiv_id = _extract_arxiv_id(fields)
            url = fields.get("url", "") or fields.get("doi", "")
            year = None
            if year_str:
                try:
                    year = int(year_str.strip())
                except ValueError:
                    pass
            doi_raw = fields.get("doi", "")
            doi = doi_raw.strip() if doi_raw else None
            paper_id = arxiv_id or doi or fields.get("ID", "") or title[:30]
            papers.append(Paper(
                paper_id=paper_id,
                title=title,
                authors=_parse_authors(authors_raw),
                year=year,
                venue=venue.strip("{}"),
                arxiv_id=arxiv_id,
                doi=doi,
                url=url,
                source="bib_import",
                content_tier="metadata",
            ))
        logger.info("BibLoader: parsed %d entries from %s", len(papers), bib_path)
        return papers

    @staticmethod
    def match_pdfs(papers: list[Paper], pdf_dir: Path) -> list[Paper]:
        if not pdf_dir.exists():
            return papers
        pdf_files = {f.stem.lower(): f for f in pdf_dir.glob("*.pdf")}
        for paper in papers:
            candidates = []
            if paper.arxiv_id:
                candidates.append(paper.arxiv_id.lower())
                base = re.sub(r"v\d+$", "", paper.arxiv_id.lower())
                candidates.append(base)
            candidates.append(paper.paper_id.lower())
            for cand in candidates:
                if cand in pdf_files:
                    paper.local_pdf_path = str(pdf_files[cand])
                    break
            else:
                if paper.arxiv_id:
                    for stem, path in pdf_files.items():
                        if paper.arxiv_id.lower() in stem:
                            paper.local_pdf_path = str(path)
                            break
        matched = sum(1 for p in papers if p.local_pdf_path)
        logger.info("BibLoader: matched %d/%d papers to local PDFs", matched, len(papers))
        return papers
