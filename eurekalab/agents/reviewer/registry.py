"""Reviewer persona registry — discover and load from built-in + user directories."""
from __future__ import annotations

import logging
from pathlib import Path

from eurekalab.agents.reviewer.persona import ReviewerPersona

logger = logging.getLogger(__name__)

# Built-in personas shipped with the package
_BUILTIN_DIR = Path(__file__).resolve().parents[1].parent / "reviewer_personas"


class ReviewerRegistry:
    """Discovers and loads reviewer personas from multiple sources."""

    def __init__(self, user_dir: Path | None = None) -> None:
        self._personas: dict[str, ReviewerPersona] = {}
        self._load_builtin()
        if user_dir:
            self._load_dir(user_dir)

    def _load_builtin(self) -> None:
        """Load built-in personas shipped with the package."""
        if _BUILTIN_DIR.exists():
            self._load_dir(_BUILTIN_DIR)

    def _load_dir(self, directory: Path) -> None:
        """Load all .yaml/.yml persona files from a directory."""
        if not directory.exists():
            return
        for path in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
            try:
                persona = ReviewerPersona.from_yaml(path)
                key = path.stem.lower()
                self._personas[key] = persona
                logger.debug("Loaded reviewer persona: %s (%s)", persona.name, key)
            except Exception as e:
                logger.warning("Failed to load persona from %s: %s", path, e)

    def get(self, name: str) -> ReviewerPersona | None:
        """Get a persona by key (filename stem, lowercase)."""
        return self._personas.get(name.lower())

    def list_all(self) -> list[ReviewerPersona]:
        """Return all loaded personas, sorted by type then name."""
        type_order = {"builtin": 0, "journal": 1, "expert": 2, "custom": 3}
        return sorted(
            self._personas.values(),
            key=lambda p: (type_order.get(p.type, 9), p.name),
        )

    def install(self, source_path: Path, target_dir: Path) -> ReviewerPersona:
        """Install a persona file into the user directory."""
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source_path.name
        target.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        persona = ReviewerPersona.from_yaml(target)
        key = target.stem.lower()
        self._personas[key] = persona
        logger.info("Installed reviewer persona: %s → %s", persona.name, target)
        return persona
