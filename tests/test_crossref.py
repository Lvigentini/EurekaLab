"""Tests for CrossRefTool with mocked httpx."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from eurekalab.tools.crossref import CrossRefTool, _format_item


MOCK_SEARCH_RESPONSE = {
    "message": {
        "items": [
            {
                "DOI": "10.1145/1234567.1234568",
                "title": ["Attention Is All You Need"],
                "author": [
                    {"given": "Ashish", "family": "Vaswani"},
                    {"given": "Noam", "family": "Shazeer"},
                ],
                "published-print": {"date-parts": [[2017]]},
                "container-title": ["NeurIPS"],
                "type": "journal-article",
                "URL": "https://doi.org/10.1145/1234567.1234568",
                "publisher": "ACM",
                "is-referenced-by-count": 50000,
                "link": [
                    {
                        "URL": "https://publisher.com/full.pdf",
                        "content-type": "application/pdf",
                        "intended-application": "text-mining",
                    }
                ],
                "license": [{"URL": "https://creativecommons.org/licenses/by/4.0"}],
            }
        ]
    }
}

MOCK_DOI_RESPONSE = {
    "message": MOCK_SEARCH_RESPONSE["message"]["items"][0]
}


class TestFormatItem:
    def test_extracts_title(self):
        result = _format_item(MOCK_SEARCH_RESPONSE["message"]["items"][0])
        assert result["title"] == "Attention Is All You Need"

    def test_extracts_doi(self):
        result = _format_item(MOCK_SEARCH_RESPONSE["message"]["items"][0])
        assert result["doi"] == "10.1145/1234567.1234568"

    def test_extracts_authors(self):
        result = _format_item(MOCK_SEARCH_RESPONSE["message"]["items"][0])
        assert result["authors"] == ["Ashish Vaswani", "Noam Shazeer"]

    def test_extracts_year(self):
        result = _format_item(MOCK_SEARCH_RESPONSE["message"]["items"][0])
        assert result["year"] == 2017

    def test_extracts_links(self):
        result = _format_item(MOCK_SEARCH_RESPONSE["message"]["items"][0])
        assert len(result["links"]) == 1
        assert result["links"][0]["content_type"] == "application/pdf"

    def test_handles_empty_item(self):
        result = _format_item({})
        assert result["title"] == ""
        assert result["authors"] == []
        assert result["year"] is None
        assert result["links"] == []


class TestCrossRefTool:
    @pytest.fixture
    def tool(self):
        return CrossRefTool()

    def test_name(self, tool):
        assert tool.name == "crossref_search"

    def test_schema_has_query_and_doi(self, tool):
        schema = tool.input_schema()
        assert "query" in schema["properties"]
        assert "doi" in schema["properties"]

    @pytest.mark.asyncio
    async def test_requires_query_or_doi(self, tool):
        result = json.loads(await tool.call())
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_mode(self, tool):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = MOCK_SEARCH_RESPONSE

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eurekalab.tools.crossref.httpx.AsyncClient", return_value=mock_client):
            result = json.loads(await tool.call(query="attention"))

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["doi"] == "10.1145/1234567.1234568"

    @pytest.mark.asyncio
    async def test_doi_mode(self, tool):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = MOCK_DOI_RESPONSE

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("eurekalab.tools.crossref.httpx.AsyncClient", return_value=mock_client):
            result = json.loads(await tool.call(doi="10.1145/1234567.1234568"))

        assert isinstance(result, dict)
        assert result["title"] == "Attention Is All You Need"
