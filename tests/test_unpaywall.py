"""Tests for UnpaywallTool with mocked httpx."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from eurekalab.tools.unpaywall import UnpaywallTool, _format_result


MOCK_OA_RESPONSE = {
    "doi": "10.1234/example",
    "title": "Open Access Paper",
    "is_oa": True,
    "oa_status": "gold",
    "journal_is_oa": True,
    "best_oa_location": {
        "url_for_pdf": "https://repo.org/paper.pdf",
        "url": "https://repo.org/paper",
        "host_type": "repository",
        "version": "publishedVersion",
        "license": "cc-by",
    },
    "oa_locations": [
        {
            "url_for_pdf": "https://repo.org/paper.pdf",
            "url": "https://repo.org/paper",
            "host_type": "repository",
            "version": "publishedVersion",
            "license": "cc-by",
        },
        {
            "url_for_pdf": "",
            "url": "https://publisher.com/paper",
            "host_type": "publisher",
            "version": "publishedVersion",
            "license": "cc-by-nc",
        },
    ],
}

MOCK_CLOSED_RESPONSE = {
    "doi": "10.1234/closed",
    "title": "Closed Paper",
    "is_oa": False,
    "oa_status": "closed",
    "journal_is_oa": False,
    "best_oa_location": None,
    "oa_locations": [],
}


class TestFormatResult:
    def test_oa_paper(self):
        result = _format_result(MOCK_OA_RESPONSE)
        assert result["is_oa"] is True
        assert result["oa_status"] == "gold"
        assert result["pdf_url"] == "https://repo.org/paper.pdf"
        assert result["best_oa_host"] == "repository"

    def test_closed_paper(self):
        result = _format_result(MOCK_CLOSED_RESPONSE)
        assert result["is_oa"] is False
        assert result["pdf_url"] == ""
        assert result["oa_locations_count"] == 0


class TestUnpaywallTool:
    @pytest.fixture
    def tool(self):
        return UnpaywallTool()

    def test_name(self, tool):
        assert tool.name == "unpaywall_lookup"

    def test_schema_requires_doi(self, tool):
        schema = tool.input_schema()
        assert "doi" in schema["required"]

    @pytest.mark.asyncio
    async def test_requires_doi(self, tool):
        result = json.loads(await tool.call())
        assert "error" in result

    @pytest.mark.asyncio
    async def test_requires_email(self, tool):
        with patch("eurekalab.tools.unpaywall.settings") as mock_settings:
            mock_settings.library_contact_email = ""
            result = json.loads(await tool.call(doi="10.1234/example"))
            assert "error" in result
            assert "LIBRARY_CONTACT_EMAIL" in result["error"]

    @pytest.mark.asyncio
    async def test_oa_lookup(self, tool):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = MOCK_OA_RESPONSE

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eurekalab.tools.unpaywall.httpx.AsyncClient", return_value=mock_client), \
             patch("eurekalab.tools.unpaywall.settings") as mock_settings:
            mock_settings.library_contact_email = "test@uni.edu"
            result = json.loads(await tool.call(doi="10.1234/example"))

        assert result["is_oa"] is True
        assert result["pdf_url"] == "https://repo.org/paper.pdf"

    @pytest.mark.asyncio
    async def test_404_returns_not_found(self, tool):
        import httpx as real_httpx

        mock_response = MagicMock()
        mock_response.status_code = 404
        exc = real_httpx.HTTPStatusError("Not Found", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=exc)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eurekalab.tools.unpaywall.httpx.AsyncClient", return_value=mock_client), \
             patch("eurekalab.tools.unpaywall.settings") as mock_settings:
            mock_settings.library_contact_email = "test@uni.edu"
            result = json.loads(await tool.call(doi="10.9999/nonexistent"))

        assert result["is_oa"] is False
        assert "not found" in result.get("message", "").lower()
