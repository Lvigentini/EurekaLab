"""ReviewerPersona — loadable reviewer persona from YAML files."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ReviewerPersona:
    """A reviewer persona loaded from a YAML file."""
    name: str
    type: str = "builtin"  # builtin, journal, expert, custom
    icon: str = "🟡"
    description: str = ""
    author: str = ""
    version: str = "1.0"
    review_prompt: str = ""
    scoring_dimensions: list[str] = field(default_factory=list)
    scoring_scale: str = "1-10"
    recommendation_options: list[str] = field(default_factory=list)
    # Journal-specific
    scope: str = ""
    standards: dict[str, Any] = field(default_factory=dict)
    common_rejections: list[str] = field(default_factory=list)
    # Expert-specific
    expertise: str = ""
    focus_areas: list[str] = field(default_factory=list)
    # Source tracking
    file_path: str = ""

    @classmethod
    def from_yaml(cls, path: Path) -> ReviewerPersona:
        """Load a persona from a YAML file."""
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Invalid persona file: {path}")
        return cls(
            name=data.get("name", path.stem),
            type=data.get("type", "custom"),
            icon=data.get("icon", "🟡"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            version=data.get("version", "1.0"),
            review_prompt=data.get("review_prompt", ""),
            scoring_dimensions=data.get("scoring_dimensions", []),
            scoring_scale=data.get("scoring_scale", "1-10"),
            recommendation_options=data.get("recommendation_options", []),
            scope=data.get("scope", ""),
            standards=data.get("standards", {}),
            common_rejections=data.get("common_rejections", []),
            expertise=data.get("expertise", ""),
            focus_areas=data.get("focus_areas", []),
            file_path=str(path),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        return {
            "name": self.name,
            "type": self.type,
            "icon": self.icon,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "scoring_dimensions": self.scoring_dimensions,
            "scoring_scale": self.scoring_scale,
            "recommendation_options": self.recommendation_options,
            "expertise": self.expertise,
            "focus_areas": self.focus_areas,
            "scope": self.scope,
        }
