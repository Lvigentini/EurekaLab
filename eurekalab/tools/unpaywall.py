"""Unpaywall API tool — find legal open-access PDFs for any DOI."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from eurekalab.config import settings
from eurekalab.tools.base import BaseTool

logger = logging.getLogger(__name__)

UNPAYWALL_BASE = "https://api.unpaywall.org/v2"


class UnpaywallTool(BaseTool):
    name = "unpaywall_lookup"
    description = (
        "Given a DOI, find legal open-access copies of the paper. "
        "Returns OA status and direct PDF URLs from repositories, preprint servers, "
        "and publisher sites. Requires a DOI."
    )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "doi": {
                    "type": "string",
                    "description": "DOI to look up (e.g. '10.1145/1234567.1234568')",
                },
            },
            "required": ["doi"],
        }

    async def call(self, doi: str = "", **kwargs: Any) -> str:
        if not doi:
            return json.dumps({"error": "DOI is required"})

        email = settings.library_contact_email
        if not email:
            return json.dumps({
                "error": "LIBRARY_CONTACT_EMAIL is required for Unpaywall API. "
                "Set it in .env or environment."
            })

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"{UNPAYWALL_BASE}/{doi}",
                    params={"email": email},
                )
                r.raise_for_status()
                data = r.json()
                return json.dumps(_format_result(data), indent=2)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return json.dumps({"doi": doi, "is_oa": False, "message": "DOI not found in Unpaywall"})
            return json.dumps({"error": f"Unpaywall API error {e.response.status_code}"})
        except Exception as e:
            logger.exception("Unpaywall lookup failed")
            return json.dumps({"error": str(e)})


def _format_result(data: dict) -> dict[str, Any]:
    """Extract the fields we care about from an Unpaywall response."""
    best = data.get("best_oa_location") or {}
    oa_locations = data.get("oa_locations", [])

    # Find the best PDF URL — prefer pdf_url, fall back to url_for_pdf, then url
    pdf_url = ""
    for loc in [best] + oa_locations:
        if not loc:
            continue
        candidate = loc.get("url_for_pdf") or loc.get("url", "")
        if candidate and candidate.endswith(".pdf"):
            pdf_url = candidate
            break
        if candidate and not pdf_url:
            pdf_url = candidate

    return {
        "doi": data.get("doi", ""),
        "title": data.get("title", ""),
        "is_oa": data.get("is_oa", False),
        "oa_status": data.get("oa_status", "closed"),
        "journal_is_oa": data.get("journal_is_oa", False),
        "pdf_url": pdf_url,
        "best_oa_host": best.get("host_type", ""),
        "best_oa_version": best.get("version", ""),
        "best_oa_license": best.get("license", ""),
        "oa_locations_count": len(oa_locations),
    }
