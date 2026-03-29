"""ReviewerAgent — critical reviewer with pluggable persona registry."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eurekalab.agents.reviewer.persona import ReviewerPersona
from eurekalab.agents.reviewer.registry import ReviewerRegistry
from eurekalab.config import settings
from eurekalab.llm import LLMClient, create_client

logger = logging.getLogger(__name__)


@dataclass
class ReviewComment:
    """A single review comment."""
    severity: str  # "major", "minor", "suggestion"
    section: str = ""
    comment: str = ""
    suggestion: str = ""
    resolved: bool = False
    user_response: str = ""  # "addressed" or user's disagreement explanation


@dataclass
class ReviewResult:
    """Structured output from a review."""
    persona_name: str
    persona_icon: str = ""
    summary: str = ""
    strengths: list[str] = field(default_factory=list)
    comments: list[ReviewComment] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    recommendation: str = ""
    questions: list[str] = field(default_factory=list)
    missing_references: list[str] = field(default_factory=list)

    @property
    def major_count(self) -> int:
        return sum(1 for c in self.comments if c.severity == "major")

    @property
    def minor_count(self) -> int:
        return sum(1 for c in self.comments if c.severity == "minor")

    @property
    def suggestion_count(self) -> int:
        return sum(1 for c in self.comments if c.severity == "suggestion")

    @property
    def resolved_count(self) -> int:
        return sum(1 for c in self.comments if c.resolved)

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona_name": self.persona_name,
            "persona_icon": self.persona_icon,
            "summary": self.summary,
            "strengths": self.strengths,
            "comments": [
                {
                    "severity": c.severity,
                    "section": c.section,
                    "comment": c.comment,
                    "suggestion": c.suggestion,
                    "resolved": c.resolved,
                    "user_response": c.user_response,
                }
                for c in self.comments
            ],
            "scores": self.scores,
            "recommendation": self.recommendation,
            "questions": self.questions,
            "missing_references": self.missing_references,
            "major_count": self.major_count,
            "minor_count": self.minor_count,
            "suggestion_count": self.suggestion_count,
            "resolved_count": self.resolved_count,
        }


_PARSE_INSTRUCTION = """

Output your review as JSON with this structure:
{
  "summary": "2-3 sentence summary of the paper and its contribution",
  "strengths": ["strength 1", "strength 2", ...],
  "comments": [
    {
      "severity": "major" | "minor" | "suggestion",
      "section": "Section name or number where the issue is",
      "comment": "Description of the issue",
      "suggestion": "Specific actionable fix"
    }
  ],
  "scores": {"dimension_name": score_number, ...},
  "recommendation": "Your overall recommendation",
  "questions": ["Question 1 for authors", ...],
  "missing_references": ["Reference that should be cited", ...]
}

Return ONLY valid JSON. No markdown, no preamble.
"""


class ReviewerAgent:
    """Critical reviewer with pluggable persona registry."""

    def __init__(self, client: LLMClient | None = None) -> None:
        self.client: LLMClient = client or create_client()
        user_dir = settings.eurekalab_dir / "reviewers"
        self._registry = ReviewerRegistry(user_dir=user_dir)

    def list_personas(self) -> list[ReviewerPersona]:
        return self._registry.list_all()

    def get_persona(self, name: str) -> ReviewerPersona | None:
        return self._registry.get(name)

    async def review(
        self,
        paper_text: str,
        persona_name: str = "rigorous",
        custom_instructions: str = "",
        previous_comments: list[dict] | None = None,
    ) -> ReviewResult:
        """Run a review using the specified persona."""
        persona = self._registry.get(persona_name)
        if persona is None:
            raise ValueError(f"Reviewer persona '{persona_name}' not found. Available: {[p.name for p in self._registry.list_all()]}")

        # Build system prompt from persona + optional custom instructions
        system = persona.review_prompt.strip()
        if custom_instructions:
            system += f"\n\nAdditional reviewer instructions: {custom_instructions}"
        if previous_comments:
            unresolved = [c for c in previous_comments if not c.get("resolved")]
            if unresolved:
                system += f"\n\nThis is a RE-REVIEW. The previous review had {len(previous_comments)} comments, {len(unresolved)} still unresolved. Check if the unresolved issues have been addressed in this revised version."
        system += _PARSE_INSTRUCTION

        # Build user message
        user_msg = f"Please review the following paper:\n\n{paper_text[:50000]}"  # cap at ~50K chars

        try:
            response = await self.client.messages.create(
                model=settings.active_model,
                max_tokens=settings.max_tokens_agent,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = response.content[0].text
            result = self._parse_review(text, persona)
            logger.info(
                "Review complete (%s): %d major, %d minor, %d suggestions",
                persona.name, result.major_count, result.minor_count, result.suggestion_count,
            )
            return result
        except Exception as e:
            logger.error("Review failed (%s): %s", persona_name, e)
            return ReviewResult(
                persona_name=persona.name,
                persona_icon=persona.icon,
                summary=f"Review failed: {e}",
                comments=[ReviewComment(severity="major", comment=f"Review could not be completed: {e}")],
            )

    def _parse_review(self, text: str, persona: ReviewerPersona) -> ReviewResult:
        """Parse LLM output into structured ReviewResult."""
        # Try to extract JSON
        try:
            # Handle markdown-wrapped JSON
            if "```json" in text:
                start = text.index("```json") + 7
                end = text.index("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.index("```") + 3
                end = text.index("```", start)
                text = text[start:end].strip()

            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            # Fallback: try to find JSON object in text
            try:
                start = text.index("{")
                end = text.rindex("}") + 1
                data = json.loads(text[start:end])
            except (json.JSONDecodeError, ValueError):
                # Last resort: return raw text as a single comment
                return ReviewResult(
                    persona_name=persona.name,
                    persona_icon=persona.icon,
                    summary="Review completed (unstructured output)",
                    comments=[ReviewComment(severity="major", comment=text[:2000])],
                )

        comments = []
        for c in data.get("comments", []):
            comments.append(ReviewComment(
                severity=c.get("severity", "minor"),
                section=c.get("section", ""),
                comment=c.get("comment", ""),
                suggestion=c.get("suggestion", ""),
            ))

        return ReviewResult(
            persona_name=persona.name,
            persona_icon=persona.icon,
            summary=data.get("summary", ""),
            strengths=data.get("strengths", []),
            comments=comments,
            scores=data.get("scores", {}),
            recommendation=data.get("recommendation", ""),
            questions=data.get("questions", []),
            missing_references=data.get("missing_references", []),
        )
