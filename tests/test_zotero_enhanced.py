"""Tests for enhanced Zotero adapter — PDF upload/download and sync improvements."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from eurekalab.integrations.zotero.adapter import ZoteroAdapter
from eurekalab.types.artifacts import Paper


def _make_paper(**kwargs) -> Paper:
    defaults = {
        "paper_id": "test-paper",
        "title": "Test Paper",
        "authors": ["Alice"],
    }
    defaults.update(kwargs)
    return Paper(**defaults)


@pytest.fixture
def adapter():
    with patch("eurekalab.integrations.zotero.adapter.zotero.Zotero"):
        a = ZoteroAdapter(library_id="123", api_key="fake-key")
    return a


# ---------------------------------------------------------------------------
# upload_pdf_attachment
# ---------------------------------------------------------------------------

class TestUploadPdfAttachment:
    def test_uploads_existing_pdf(self, adapter, tmp_path):
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-fake-content")

        adapter._zot.attachment_simple = MagicMock(return_value={
            "successful": {"0": {"key": "ATT_KEY_123", "data": {}}},
        })

        key = adapter.upload_pdf_attachment("PARENT_KEY", str(pdf_path), "My Paper")
        assert key == "ATT_KEY_123"
        adapter._zot.attachment_simple.assert_called_once()

    def test_returns_none_for_missing_file(self, adapter):
        key = adapter.upload_pdf_attachment("PARENT_KEY", "/nonexistent/paper.pdf")
        assert key is None

    def test_returns_none_on_api_failure(self, adapter, tmp_path):
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-fake-content")

        adapter._zot.attachment_simple = MagicMock(side_effect=Exception("API error"))
        key = adapter.upload_pdf_attachment("PARENT_KEY", str(pdf_path))
        assert key is None

    def test_returns_none_on_empty_result(self, adapter, tmp_path):
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-fake-content")

        adapter._zot.attachment_simple = MagicMock(return_value={"successful": {}})
        key = adapter.upload_pdf_attachment("PARENT_KEY", str(pdf_path))
        assert key is None


# ---------------------------------------------------------------------------
# download_attachment
# ---------------------------------------------------------------------------

class TestDownloadAttachment:
    def test_downloads_pdf_attachment(self, adapter, tmp_path):
        adapter._zot.children = MagicMock(return_value=[
            {
                "key": "ATT_001",
                "data": {
                    "itemType": "attachment",
                    "contentType": "application/pdf",
                    "filename": "paper.pdf",
                },
            },
        ])
        adapter._zot.file = MagicMock(return_value=b"%PDF-content-here")

        result = adapter.download_attachment("ITEM_KEY", tmp_path)
        assert result is not None
        assert Path(result).exists()
        assert Path(result).read_bytes() == b"%PDF-content-here"

    def test_skips_non_pdf_attachments(self, adapter, tmp_path):
        adapter._zot.children = MagicMock(return_value=[
            {
                "key": "ATT_001",
                "data": {
                    "itemType": "attachment",
                    "contentType": "text/html",
                    "filename": "snapshot.html",
                },
            },
        ])

        result = adapter.download_attachment("ITEM_KEY", tmp_path)
        assert result is None

    def test_returns_none_when_no_children(self, adapter, tmp_path):
        adapter._zot.children = MagicMock(return_value=[])
        result = adapter.download_attachment("ITEM_KEY", tmp_path)
        assert result is None

    def test_returns_none_on_api_failure(self, adapter, tmp_path):
        adapter._zot.children = MagicMock(side_effect=Exception("Network error"))
        result = adapter.download_attachment("ITEM_KEY", tmp_path)
        assert result is None

    def test_skips_notes(self, adapter, tmp_path):
        adapter._zot.children = MagicMock(return_value=[
            {
                "key": "NOTE_001",
                "data": {
                    "itemType": "note",
                    "note": "Some note",
                },
            },
        ])
        result = adapter.download_attachment("ITEM_KEY", tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# push_papers with key persistence
# ---------------------------------------------------------------------------

class TestPushPapersKeyPersistence:
    def test_keys_can_be_persisted_back(self, adapter):
        """Verify the pattern used in push-to-zotero CLI for persisting keys."""
        papers = [
            _make_paper(paper_id="p1", title="Paper 1"),
            _make_paper(paper_id="p2", title="Paper 2"),
        ]
        keys = ["ZOT_KEY_1", "ZOT_KEY_2"]

        # Simulate what the CLI does after push_papers
        for paper, key in zip(papers, keys):
            paper.zotero_item_key = key

        assert papers[0].zotero_item_key == "ZOT_KEY_1"
        assert papers[1].zotero_item_key == "ZOT_KEY_2"


# ---------------------------------------------------------------------------
# DOI field in Zotero adapter
# ---------------------------------------------------------------------------

class TestZoteroDoi:
    def test_doi_propagated(self, adapter):
        item = {
            "key": "ABC123",
            "data": {
                "itemType": "journalArticle",
                "title": "Test",
                "creators": [],
                "date": "2024",
                "abstractNote": "",
                "publicationTitle": "",
                "DOI": "10.1234/test",
                "url": "",
                "extra": "",
            },
        }
        paper = adapter._item_to_paper(item)
        assert paper.doi == "10.1234/test"

    def test_doi_empty_becomes_none(self, adapter):
        item = {
            "key": "DEF456",
            "data": {
                "itemType": "journalArticle",
                "title": "No DOI Paper",
                "creators": [],
                "date": "2024",
                "abstractNote": "",
                "publicationTitle": "",
                "DOI": "",
                "url": "",
                "extra": "",
            },
        }
        paper = adapter._item_to_paper(item)
        assert paper.doi is None
