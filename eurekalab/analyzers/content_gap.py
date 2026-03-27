"""ContentGapAnalyzer — identify papers with degraded or missing content."""
from __future__ import annotations

from dataclasses import dataclass, field

from eurekalab.types.artifacts import Bibliography, Paper


@dataclass
class ContentGapReport:
    """Summary of content availability across the bibliography."""
    full_text: list[Paper] = field(default_factory=list)
    abstract_only: list[Paper] = field(default_factory=list)
    metadata_only: list[Paper] = field(default_factory=list)
    missing: list[Paper] = field(default_factory=list)

    @property
    def has_gaps(self) -> bool:
        return bool(self.abstract_only or self.metadata_only or self.missing)

    @property
    def total(self) -> int:
        return len(self.full_text) + len(self.abstract_only) + len(self.metadata_only) + len(self.missing)


class ContentGapAnalyzer:
    """Analyzes bibliography for content completeness."""

    @staticmethod
    def analyze(bib: Bibliography) -> ContentGapReport:
        report = ContentGapReport()
        for paper in bib.papers:
            tier = paper.content_tier
            if tier == "full_text":
                report.full_text.append(paper)
            elif tier == "abstract":
                report.abstract_only.append(paper)
            elif tier == "metadata":
                report.metadata_only.append(paper)
            else:
                report.missing.append(paper)
        return report
