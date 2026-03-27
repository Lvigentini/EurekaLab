"""Gemini-powered web + academic search — runs in parallel with arXiv/S2 for broader coverage."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from eurekalab.config import settings
from eurekalab.tools.base import BaseTool

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


class GeminiSearchTool(BaseTool):
    name = "gemini_search"
    description = (
        "Use Google Gemini with grounding to search the web for academic papers, "
        "recent research, and supplementary material. Provides broader coverage "
        "than arXiv alone — especially for interdisciplinary topics, non-arXiv venues, "
        "and very recent work. Returns structured results with titles, snippets, and URLs."
    )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Research-focused search query. Be specific and academic.",
                },
                "focus": {
                    "type": "string",
                    "enum": ["papers", "definitions", "recent_advances", "open_problems"],
                    "default": "papers",
                    "description": "What kind of results to prioritize.",
                },
            },
            "required": ["query"],
        }

    async def call(self, query: str, focus: str = "papers") -> str:
        if not settings.gemini_api_key:
            return json.dumps({"error": "GEMINI_API_KEY not configured."})

        focus_instructions = {
            "papers": "Find academic papers, their authors, publication venues, and key results.",
            "definitions": "Find formal mathematical definitions and key theorems related to the query.",
            "recent_advances": "Find the most recent research advances and breakthroughs.",
            "open_problems": "Find open problems, conjectures, and unsolved questions.",
        }

        prompt = (
            f"You are an academic research assistant. Search for: {query}\n\n"
            f"Focus: {focus_instructions.get(focus, focus_instructions['papers'])}\n\n"
            "Return a JSON array of results. Each result should have:\n"
            '- "title": paper/resource title\n'
            '- "authors": list of author names (if available)\n'
            '- "year": publication year (if available)\n'
            '- "url": source URL\n'
            '- "snippet": 1-2 sentence summary of the key finding\n'
            '- "venue": publication venue (if available)\n'
            "Return 5-10 results. Output ONLY the JSON array, no other text."
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{GEMINI_API_URL}?key={settings.gemini_api_key}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "tools": [{"google_search": {}}],
                        "generationConfig": {
                            "temperature": 0.1,
                            "maxOutputTokens": 4096,
                        },
                    },
                )
                r.raise_for_status()
                data = r.json()

            candidates = data.get("candidates", [])
            if not candidates:
                return json.dumps({"error": "No response from Gemini"})

            text = ""
            for part in candidates[0].get("content", {}).get("parts", []):
                if "text" in part:
                    text += part["text"]

            grounding = candidates[0].get("groundingMetadata", {})
            web_results = grounding.get("groundingChunks", [])

            results = self._parse_results(text)

            if len(results) < 3 and web_results:
                for chunk in web_results[:5]:
                    web = chunk.get("web", {})
                    if web:
                        results.append({
                            "title": web.get("title", ""),
                            "url": web.get("uri", ""),
                            "snippet": web.get("title", ""),
                        })

            return json.dumps(results[:10], indent=2)
        except httpx.HTTPStatusError as e:
            logger.warning("Gemini search API error %d: %s", e.response.status_code, e.response.text[:200])
            return json.dumps({"error": f"Gemini API error: {e.response.status_code}"})
        except Exception as e:
            logger.exception("Gemini search failed")
            return json.dumps({"error": str(e)})

    def _parse_results(self, text: str) -> list[dict]:
        text = text.strip()
        if text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        if "```json" in text:
            try:
                start = text.index("```json") + 7
                end = text.index("```", start)
                return json.loads(text[start:end].strip())
            except (json.JSONDecodeError, ValueError):
                pass
        if "[" in text and "]" in text:
            try:
                start = text.index("[")
                end = text.rindex("]") + 1
                return json.loads(text[start:end])
            except (json.JSONDecodeError, ValueError):
                pass
        logger.warning("Could not parse Gemini search results as JSON")
        return []
