"""IdeationPool — continuously evolving pool of research directions and ideas."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from eurekaclaw.types.artifacts import ResearchDirection


class InjectedIdea(BaseModel):
    """An idea injected by the user at any point in the process."""
    text: str
    injected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "user"  # "user", "draft", "paper:<id>", "theory:failure"
    incorporated: bool = False


class IdeationPool(BaseModel):
    """Continuously evolving pool of research directions and ideas."""
    directions: list[ResearchDirection] = Field(default_factory=list)
    selected_direction: ResearchDirection | None = None
    injected_ideas: list[InjectedIdea] = Field(default_factory=list)
    emerged_insights: list[str] = Field(default_factory=list)
    discarded: list[tuple[str, str]] = Field(default_factory=list)  # (title, reason)
    idea_sources: dict[str, str] = Field(default_factory=dict)  # title → source
    version: int = 0

    def add_direction(self, direction: ResearchDirection, source: str = "") -> None:
        self.directions.append(direction)
        if source:
            self.idea_sources[direction.title] = source

    def inject_idea(self, text: str, source: str = "user") -> None:
        self.injected_ideas.append(InjectedIdea(text=text, source=source))
        self.version += 1

    def add_insight(self, insight: str) -> None:
        self.emerged_insights.append(insight)

    def discard_direction(self, title: str, reason: str) -> None:
        self.discarded.append((title, reason))
        self.directions = [d for d in self.directions if d.title != title]

    @property
    def unincorporated_ideas(self) -> list[InjectedIdea]:
        return [i for i in self.injected_ideas if not i.incorporated]

    @property
    def has_new_input(self) -> bool:
        return bool(self.unincorporated_ideas or self.emerged_insights)
