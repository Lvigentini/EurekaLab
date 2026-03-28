"""CrossRef API tool — DOI resolution and academic paper search."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from eurekalab.config import settings
from eurekalab.tools.base import BaseTool

logger = logging.getLogger(__name__)

CROSSREF_BASE = "https://api.crossref.org"


class CrossRefTool(BaseTool):
    name = "crossref_search"
    description = (
        "Search CrossRef for academic papers by query or resolve a specific DOI. "
        "Returns metadata including DOI, publisher links, and license info. "
        "Useful for finding papers outside arXiv and resolving DOIs to full-text URLs."
    )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (ignored if doi is provided)",
                },
                "doi": {
                    "type": "string",
                    "description": "Specific DOI to resolve (e.g. '10.1145/1234567.1234568')",
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Max results for query search (default 10, max 20)",
                },
            },
            "required": [],
        }

    async def call(
        self,
        query: str = "",
        doi: str = "",
        limit: int = 10,
    ) -> str:
        if not query and not doi:
            return json.dumps({"error": "Provide either 'query' or 'doi'"})

        headers = _build_headers()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                if doi:
                    return await _resolve_doi(client, doi, headers)
                return await _search(client, query, min(limit, 20), headers)
        except httpx.HTTPStatusError as e:
            return json.dumps({"error": f"CrossRef API error {e.response.status_code}"})
        except Exception as e:
            logger.exception("CrossRef request failed")
            return json.dumps({"error": str(e)})


def _build_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    email = settings.library_contact_email
    if email:
        headers["User-Agent"] = f"EurekaLab/0.4 (mailto:{email})"
    return headers


async def _resolve_doi(
    client: httpx.AsyncClient,
    doi: str,
    headers: dict[str, str],
) -> str:
    r = await client.get(f"{CROSSREF_BASE}/works/{doi}", headers=headers)
    r.raise_for_status()
    item = r.json().get("message", {})
    return json.dumps(_format_item(item), indent=2)


async def _search(
    client: httpx.AsyncClient,
    query: str,
    limit: int,
    headers: dict[str, str],
) -> str:
    params = {"query": query, "rows": limit}
    r = await client.get(f"{CROSSREF_BASE}/works", params=params, headers=headers)
    r.raise_for_status()
    items = r.json().get("message", {}).get("items", [])
    return json.dumps([_format_item(it) for it in items], indent=2)


def _format_item(item: dict) -> dict[str, Any]:
    """Extract the fields we care about from a CrossRef work item."""
    titles = item.get("title", [])
    title = titles[0] if titles else ""

    authors = []
    for a in item.get("author", [])[:5]:
        name = f"{a.get('given', '')} {a.get('family', '')}".strip()
        if name:
            authors.append(name)

    year = None
    for date_field in ("published-print", "published-online", "created"):
        parts = (item.get(date_field) or {}).get("date-parts", [[]])
        if parts and parts[0] and parts[0][0]:
            year = parts[0][0]
            break

    container = item.get("container-title", [])
    venue = container[0] if container else ""

    # Full-text links from the publisher
    links = []
    for link in item.get("link", []):
        links.append({
            "url": link.get("URL", ""),
            "content_type": link.get("content-type", ""),
            "intended_application": link.get("intended-application", ""),
        })

    return {
        "doi": item.get("DOI", ""),
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue,
        "type": item.get("type", ""),
        "url": item.get("URL", ""),
        "publisher": item.get("publisher", ""),
        "is_referenced_by_count": item.get("is-referenced-by-count", 0),
        "links": links,
        "license": [
            lic.get("URL", "") for lic in item.get("license", [])
        ],
    }
