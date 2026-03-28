"""Tests for PdfDownloader with mocked HTTP and PDF extraction."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock

from eurekalab.services.pdf_downloader import PdfDownloader
from eurekalab.types.artifacts import Paper


def _make_paper(**kwargs) -> Paper:
    defaults = {
        "paper_id": "test-paper",
        "title": "Test Paper",
        "authors": ["Alice"],
    }
    defaults.update(kwargs)
    return Paper(**defaults)


class TestCacheKey:
    def test_doi_based(self):
        paper = _make_paper(doi="10.1234/test")
        key = PdfDownloader._cache_key(paper)
        assert key is not None
        assert len(key) == 16

    def test_arxiv_based(self):
        paper = _make_paper(arxiv_id="2401.12345")
        key = PdfDownloader._cache_key(paper)
        assert key is not None

    def test_no_identifier(self):
        paper = _make_paper()
        key = PdfDownloader._cache_key(paper)
        assert key is None

    def test_deterministic(self):
        paper = _make_paper(doi="10.1234/test")
        assert PdfDownloader._cache_key(paper) == PdfDownloader._cache_key(paper)


class TestBestPdfUrl:
    def test_picks_url_for_pdf(self):
        data = {
            "best_oa_location": {"url_for_pdf": "https://repo.org/paper.pdf", "url": "https://repo.org/paper"},
            "oa_locations": [],
        }
        assert PdfDownloader._best_pdf_url(data) == "https://repo.org/paper.pdf"

    def test_falls_back_to_url(self):
        data = {
            "best_oa_location": {"url_for_pdf": "", "url": "https://repo.org/paper"},
            "oa_locations": [],
        }
        assert PdfDownloader._best_pdf_url(data) == "https://repo.org/paper"

    def test_empty_locations(self):
        data = {"best_oa_location": None, "oa_locations": []}
        assert PdfDownloader._best_pdf_url(data) == ""


class TestDownloadAndExtract:
    @pytest.fixture
    def downloader(self, tmp_path):
        with patch("eurekalab.services.pdf_downloader.settings") as mock_settings:
            mock_settings.pdf_cache_dir = str(tmp_path / "cache")
            mock_settings.pdf_download_timeout = 10
            mock_settings.paper_reader_pdf_backend = "pdfplumber"
            mock_settings.library_contact_email = "test@uni.edu"
            dl = PdfDownloader()
        return dl

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_paper(self, downloader):
        paper = _make_paper()
        result = await downloader.download_and_extract(paper)
        assert result is None

    @pytest.mark.asyncio
    async def test_uses_local_pdf_path(self, downloader, tmp_path):
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"fake pdf content")

        paper = _make_paper(local_pdf_path=str(pdf_path))

        with patch.object(downloader, "_extract_local", return_value="Extracted text"):
            result = await downloader.download_and_extract(paper)

        assert result == "Extracted text"
        assert paper.content_tier == "full_text"
        assert paper.full_text == "Extracted text"

    @pytest.mark.asyncio
    async def test_arxiv_fallback(self, downloader):
        paper = _make_paper(arxiv_id="2401.12345")

        with patch.object(
            downloader, "_download_and_extract_url",
            new_callable=AsyncMock, return_value="arXiv text",
        ):
            result = await downloader.download_and_extract(paper)

        assert result == "arXiv text"
        assert paper.content_tier == "full_text"

    @pytest.mark.asyncio
    async def test_unpaywall_fallback(self, downloader):
        paper = _make_paper(doi="10.1234/test")

        with patch.object(
            downloader, "_try_unpaywall",
            new_callable=AsyncMock, return_value="OA text",
        ):
            result = await downloader.download_and_extract(paper)

        assert result == "OA text"
        assert paper.content_tier == "full_text"

    @pytest.mark.asyncio
    async def test_crossref_fallback(self, downloader):
        paper = _make_paper(doi="10.1234/test")

        with patch.object(downloader, "_try_unpaywall", new_callable=AsyncMock, return_value=None), \
             patch.object(downloader, "_try_crossref_links", new_callable=AsyncMock, return_value="CrossRef text"):
            result = await downloader.download_and_extract(paper)

        assert result == "CrossRef text"
        assert paper.content_tier == "full_text"

    @pytest.mark.asyncio
    async def test_cascade_stops_on_first_success(self, downloader):
        """Once arXiv succeeds, Unpaywall should not be called."""
        paper = _make_paper(arxiv_id="2401.12345", doi="10.1234/test")

        unpaywall_mock = AsyncMock(return_value="OA text")

        with patch.object(
            downloader, "_download_and_extract_url",
            new_callable=AsyncMock, return_value="arXiv text",
        ), patch.object(downloader, "_try_unpaywall", unpaywall_mock):
            result = await downloader.download_and_extract(paper)

        assert result == "arXiv text"
        unpaywall_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_direct_url_pdf(self, downloader):
        paper = _make_paper(url="https://example.com/paper.pdf")

        with patch.object(
            downloader, "_download_and_extract_url",
            new_callable=AsyncMock, return_value="URL text",
        ):
            result = await downloader.download_and_extract(paper)

        assert result == "URL text"


class TestCachePdf:
    def test_caches_with_doi(self, tmp_path):
        with patch("eurekalab.services.pdf_downloader.settings") as mock_settings:
            mock_settings.pdf_cache_dir = str(tmp_path / "cache")
            mock_settings.pdf_download_timeout = 10
            mock_settings.paper_reader_pdf_backend = "pdfplumber"
            dl = PdfDownloader()

        paper = _make_paper(doi="10.1234/test")
        path = dl.cache_pdf(paper, b"PDF bytes here")

        assert path is not None
        assert path.exists()
        assert path.read_bytes() == b"PDF bytes here"
        assert paper.local_pdf_path == str(path)

    def test_no_cache_without_identifier(self, tmp_path):
        with patch("eurekalab.services.pdf_downloader.settings") as mock_settings:
            mock_settings.pdf_cache_dir = str(tmp_path / "cache")
            mock_settings.pdf_download_timeout = 10
            mock_settings.paper_reader_pdf_backend = "pdfplumber"
            dl = PdfDownloader()

        paper = _make_paper()
        path = dl.cache_pdf(paper, b"PDF bytes here")
        assert path is None


class TestDoi:
    """Test that doi field propagates correctly through the Paper model."""

    def test_paper_doi_field(self):
        paper = Paper(
            paper_id="test",
            title="Test",
            authors=["Alice"],
            doi="10.1234/test",
        )
        assert paper.doi == "10.1234/test"

    def test_paper_doi_default_none(self):
        paper = Paper(paper_id="test", title="Test", authors=["Alice"])
        assert paper.doi is None

    def test_paper_serialization_includes_doi(self):
        paper = Paper(
            paper_id="test",
            title="Test",
            authors=["Alice"],
            doi="10.1234/test",
        )
        data = paper.model_dump()
        assert data["doi"] == "10.1234/test"
