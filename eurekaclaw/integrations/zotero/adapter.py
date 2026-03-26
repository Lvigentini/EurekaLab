"""ZoteroAdapter — connect to Zotero via pyzotero and import papers."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from pyzotero import zotero

from eurekaclaw.types.artifacts import Paper

logger = logging.getLogger(__name__)

# Zotero item types that represent papers (not notes, attachments, etc.)
_PAPER_TYPES = {
    "journalArticle", "conferencePaper", "preprint", "book",
    "bookSection", "thesis", "report", "manuscript", "document",
}


def _extract_arxiv_id(extra: str) -> str | None:
    """Extract arXiv ID from Zotero's 'extra' field."""
    m = re.search(r"arXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", extra, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", extra)
    return m.group(1) if m else None


def _extract_authors(creators: list[dict]) -> list[str]:
    """Convert Zotero creator dicts to author name strings."""
    authors = []
    for c in creators:
        if c.get("creatorType") != "author":
            continue
        first = c.get("firstName", "")
        last = c.get("lastName", "")
        name = c.get("name", "")  # single-field name
        if name:
            authors.append(name)
        elif first and last:
            authors.append(f"{first} {last}")
        elif last:
            authors.append(last)
    return authors


def _strip_html(text: str) -> str:
    """Strip HTML tags from Zotero note content."""
    return re.sub(r"<[^>]+>", "", text).strip()


class ZoteroAdapter:
    """Connect to Zotero via pyzotero and import/export papers."""

    def __init__(
        self,
        library_id: str,
        api_key: str,
        library_type: str = "user",
        local_data_dir: str | None = None,
    ) -> None:
        self._zot = zotero.Zotero(library_id, library_type, api_key)
        self._local_data_dir = Path(local_data_dir) if local_data_dir else None
        logger.info("ZoteroAdapter: connected to %s library %s", library_type, library_id)

    def import_collection(self, collection_id: str) -> list[Paper]:
        """Import all papers from a Zotero collection."""
        items = self._zot.collection_items(collection_id)

        # Separate papers from notes
        paper_items = []
        notes_by_parent: dict[str, list[str]] = {}

        for item in items:
            data = item.get("data", {})
            item_type = data.get("itemType", "")

            if item_type == "note":
                parent = data.get("parentItem", "")
                if parent:
                    note_text = _strip_html(data.get("note", ""))
                    if note_text:
                        notes_by_parent.setdefault(parent, []).append(note_text)
            elif item_type in _PAPER_TYPES:
                paper_items.append(item)

        papers: list[Paper] = []
        for item in paper_items:
            paper = self._item_to_paper(item)
            # Attach notes
            key = item.get("key", "")
            if key in notes_by_parent:
                paper.user_notes = "\n---\n".join(notes_by_parent[key])
            papers.append(paper)

        logger.info("ZoteroAdapter: imported %d papers from collection %s", len(papers), collection_id)
        return papers

    def _item_to_paper(self, item: dict) -> Paper:
        """Convert a Zotero item dict to a Paper object."""
        data = item.get("data", {})
        key = item.get("key", "")

        title = data.get("title", "")
        creators = data.get("creators", [])
        authors = _extract_authors(creators)

        date_str = data.get("date", "")
        year = None
        if date_str:
            m = re.search(r"(\d{4})", date_str)
            if m:
                year = int(m.group(1))

        abstract = data.get("abstractNote", "")
        venue = (data.get("publicationTitle", "")
                 or data.get("proceedingsTitle", "")
                 or data.get("bookTitle", ""))

        extra = data.get("extra", "")
        arxiv_id = _extract_arxiv_id(extra)
        doi = data.get("DOI", "")
        url = data.get("url", "") or (f"https://doi.org/{doi}" if doi else "")

        paper_id = arxiv_id or doi or key
        content_tier = "abstract" if abstract.strip() else "metadata"

        return Paper(
            paper_id=paper_id,
            title=title,
            authors=authors,
            year=year,
            abstract=abstract,
            venue=venue,
            arxiv_id=arxiv_id,
            url=url,
            source="zotero",
            content_tier=content_tier,
            zotero_item_key=key,
        )
