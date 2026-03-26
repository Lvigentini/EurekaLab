"""DraftAnalyzer — extract structured information from draft papers."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DraftAnalysis:
    """Structured extraction from a draft paper."""
    title: str = ""
    abstract: str = ""
    full_text: str = ""
    citation_keys: list[str] = field(default_factory=list)
    claims: list[str] = field(default_factory=list)  # theorems, lemmas, conjectures
    sections: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)  # TODOs, empty sections


class DraftAnalyzer:
    """Extract structure from draft papers (LaTeX, Markdown, PDF)."""

    @staticmethod
    def analyze(path: Path) -> DraftAnalysis:
        suffix = path.suffix.lower()
        text = DraftAnalyzer._read_text(path, suffix)
        if not text:
            return DraftAnalysis()

        if suffix == ".tex":
            return DraftAnalyzer._analyze_latex(text)
        elif suffix in (".md", ".markdown"):
            return DraftAnalyzer._analyze_markdown(text)
        else:
            # PDF or unknown — treat as plain text
            return DraftAnalyzer._analyze_plain(text)

    @staticmethod
    def _read_text(path: Path, suffix: str) -> str:
        if suffix == ".pdf":
            try:
                import pdfplumber
                with pdfplumber.open(str(path)) as pdf:
                    pages = [page.extract_text() or "" for page in pdf.pages]
                    return "\n\n".join(pages)
            except Exception as e:
                logger.warning("DraftAnalyzer: PDF read failed for %s: %s", path, e)
                return ""
        else:
            try:
                return path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning("DraftAnalyzer: file read failed for %s: %s", path, e)
                return ""

    @staticmethod
    def _analyze_latex(text: str) -> DraftAnalysis:
        analysis = DraftAnalysis(full_text=text)

        # Title
        m = re.search(r"\\title\{(.+?)\}", text, re.DOTALL)
        if m:
            analysis.title = re.sub(r"\s+", " ", m.group(1)).strip()

        # Abstract
        m = re.search(r"\\begin\{abstract\}(.+?)\\end\{abstract\}", text, re.DOTALL)
        if m:
            analysis.abstract = m.group(1).strip()

        # Citations
        cites = re.findall(r"\\cite\{([^}]+)\}", text)
        keys: list[str] = []
        for cite_group in cites:
            keys.extend(k.strip() for k in cite_group.split(","))
        analysis.citation_keys = sorted(set(keys))

        # Claims (theorems, lemmas, etc.)
        claim_envs = re.findall(
            r"\\begin\{(theorem|lemma|corollary|proposition|conjecture|claim)\}"
            r"(?:\[([^\]]*)\])?"
            r"(.+?)"
            r"\\end\{\1\}",
            text, re.DOTALL,
        )
        for env_type, label, content in claim_envs:
            prefix = f"{env_type.capitalize()}"
            if label:
                prefix += f" ({label})"
            analysis.claims.append(f"{prefix}: {content.strip()[:200]}")

        # Sections
        sections = re.findall(r"\\section\{(.+?)\}", text)
        analysis.sections = [s.strip() for s in sections]

        # Gaps — TODOs, empty sections, comments
        todos = re.findall(r"\\todo\{(.+?)\}", text)
        comment_todos = re.findall(r"%\s*TODO[:\s]*(.+)", text, re.IGNORECASE)
        for t in todos + comment_todos:
            analysis.gaps.append(t.strip())

        return analysis

    @staticmethod
    def _analyze_markdown(text: str) -> DraftAnalysis:
        analysis = DraftAnalysis(full_text=text)

        # Title — first # heading
        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if m:
            analysis.title = m.group(1).strip()

        # Abstract — content under ## Abstract heading
        m = re.search(r"##\s+Abstract\s*\n(.+?)(?=\n##|\Z)", text, re.DOTALL | re.IGNORECASE)
        if m:
            analysis.abstract = m.group(1).strip()

        # Citations — [@key] or @key patterns
        cites = re.findall(r"@(\w+)", text)
        # Filter out common false positives
        analysis.citation_keys = sorted(set(
            c for c in cites if len(c) > 2 and not c.startswith("_")
        ))

        # Claims — **Theorem/Lemma N.**
        claims = re.findall(
            r"\*\*(Theorem|Lemma|Corollary|Proposition|Conjecture)\s*\d*\.?\*\*\s*(.+?)(?=\n\n|\n\*\*|\Z)",
            text, re.DOTALL | re.IGNORECASE,
        )
        for claim_type, content in claims:
            analysis.claims.append(f"{claim_type}: {content.strip()[:200]}")

        # Sections
        sections = re.findall(r"^##\s+(.+)$", text, re.MULTILINE)
        analysis.sections = [s.strip() for s in sections]

        # Gaps
        todos = re.findall(r"TODO[:\s]*(.+)", text, re.IGNORECASE)
        for t in todos:
            analysis.gaps.append(t.strip())

        return analysis

    @staticmethod
    def _analyze_plain(text: str) -> DraftAnalysis:
        """Fallback for plain text or PDF-extracted content."""
        analysis = DraftAnalysis(full_text=text)
        # Try to extract title from first non-empty line
        for line in text.split("\n"):
            line = line.strip()
            if line and len(line) > 10:
                analysis.title = line[:200]
                break
        return analysis
