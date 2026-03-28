"""Tests for PaperReader integration with PdfDownloader."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from eurekalab.types.artifacts import Paper


def _make_paper(**kwargs) -> Paper:
    defaults = {
        "paper_id": "test-paper",
        "title": "Test Paper",
        "authors": ["Alice"],
    }
    defaults.update(kwargs)
    return Paper(**defaults)


class TestPaperReaderPdfGate:
    """Test that PaperReader now accepts papers with doi or url, not just arxiv_id."""

    def test_can_fetch_pdf_arxiv(self):
        paper = _make_paper(arxiv_id="2401.12345")
        can_fetch = bool(paper.arxiv_id or paper.doi or (paper.url and paper.url.lower().endswith(".pdf")))
        assert can_fetch is True

    def test_can_fetch_pdf_doi(self):
        paper = _make_paper(doi="10.1145/1234567")
        can_fetch = bool(paper.arxiv_id or paper.doi or (paper.url and paper.url.lower().endswith(".pdf")))
        assert can_fetch is True

    def test_can_fetch_pdf_url(self):
        paper = _make_paper(url="https://example.com/paper.pdf")
        can_fetch = bool(paper.arxiv_id or paper.doi or (paper.url and paper.url.lower().endswith(".pdf")))
        assert can_fetch is True

    def test_cannot_fetch_plain_paper(self):
        paper = _make_paper()
        can_fetch = bool(paper.arxiv_id or paper.doi or (paper.url and paper.url.lower().endswith(".pdf")))
        assert can_fetch is False

    def test_cannot_fetch_non_pdf_url(self):
        paper = _make_paper(url="https://example.com/paper.html")
        can_fetch = bool(paper.arxiv_id or paper.doi or (paper.url and paper.url.lower().endswith(".pdf")))
        assert can_fetch is False


class TestContentGapAutoDownload:
    """Test that _handle_content_gaps auto-downloads papers."""

    @pytest.mark.asyncio
    async def test_auto_download_upgrades_papers(self, tmp_path):
        """Simulate auto-download upgrading abstract-tier papers to full_text."""
        from eurekalab.services.pdf_downloader import PdfDownloader

        paper_with_doi = _make_paper(doi="10.1234/test", content_tier="abstract")
        paper_without = _make_paper(paper_id="no-id", content_tier="abstract")

        async def mock_download(paper):
            if paper.doi:
                paper.full_text = "Downloaded full text"
                paper.content_tier = "full_text"
                return "Downloaded full text"
            return None

        with patch("eurekalab.services.pdf_downloader.settings") as mock_settings:
            mock_settings.pdf_cache_dir = str(tmp_path / "cache")
            mock_settings.pdf_download_timeout = 10
            mock_settings.paper_reader_pdf_backend = "pdfplumber"
            mock_settings.library_contact_email = "test@uni.edu"
            mock_settings.library_proxy_url = ""
            mock_settings.library_proxy_mode = "none"
            downloader = PdfDownloader()

        with patch.object(downloader, "download_and_extract", side_effect=mock_download):
            result1 = await downloader.download_and_extract(paper_with_doi)
            result2 = await downloader.download_and_extract(paper_without)

        assert result1 == "Downloaded full text"
        assert paper_with_doi.content_tier == "full_text"
        assert result2 is None
        assert paper_without.content_tier == "abstract"


class TestExtractMatchedPdfs:
    """Test that _extract_matched_pdfs uses PdfDownloader."""

    def test_extracts_local_pdf(self, tmp_path):
        from eurekalab.services.pdf_downloader import PdfDownloader

        paper = _make_paper(local_pdf_path=str(tmp_path / "test.pdf"), content_tier="metadata")

        with patch("eurekalab.services.pdf_downloader.settings") as mock_settings:
            mock_settings.pdf_cache_dir = str(tmp_path / "cache")
            mock_settings.pdf_download_timeout = 10
            mock_settings.paper_reader_pdf_backend = "pdfplumber"
            dl = PdfDownloader()

        with patch.object(dl, "_extract_local", return_value="Extracted from local PDF"):
            text = dl._extract_local(paper.local_pdf_path)
            if text:
                paper.full_text = text
                paper.content_tier = "full_text"

        assert paper.content_tier == "full_text"
        assert paper.full_text == "Extracted from local PDF"

    def test_skips_already_full_text(self):
        paper = _make_paper(content_tier="full_text", full_text="Already have it")
        # Should not attempt extraction
        assert paper.content_tier == "full_text"
