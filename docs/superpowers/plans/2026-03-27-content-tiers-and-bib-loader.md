# Content Tiers & Bibliography Loader (Phases 1+2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add content awareness to papers (full_text/abstract/metadata/missing tiers), interactive gap-filling that prompts the user for missing papers, and a `.bib` + local PDF entry point so users can start from their existing research.

**Architecture:** Extend the `Paper` model with `content_tier`, `local_pdf_path`, `full_text`, `user_notes`, and `source` fields. Add a `ContentGapAnalyzer` that reports content status after survey and prompts the user to fill gaps. Add a `BibLoader` that parses `.bib` files via `bibtexparser` (already a dependency, not yet used) and matches local PDFs. Add a `from-bib` CLI command. Survey gains a "gap-fill" mode when bibliography is pre-populated.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, bibtexparser (already in deps), pdfplumber (already installed), Click, Rich

---

## File Structure

```
eurekalab/types/artifacts.py          # Modify: extend Paper model with content fields
eurekalab/analyzers/                   # New directory
  __init__.py
  content_gap.py                        # ContentGapAnalyzer + interactive prompt
  bib_loader.py                         # Parse .bib files + match local PDFs
eurekalab/orchestrator/gate.py         # Modify: add content status report after survey
eurekalab/cli.py                       # Modify: add from-bib command
eurekalab/agents/survey/agent.py       # Modify: gap-fill survey mode

tests/test_content_tier.py              # Paper content tier + gap analysis
tests/test_bib_loader.py               # .bib parsing + PDF matching
```

---

### Task 1: Extend Paper Model with Content Fields

**Files:**
- Modify: `eurekalab/types/artifacts.py` (Paper class, lines 16-27)
- Test: `tests/test_content_tier.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_content_tier.py
"""Tests for Paper content tier tracking."""
import pytest
from eurekalab.types.artifacts import Paper


def test_paper_default_content_tier():
    p = Paper(paper_id="p1", title="Test", authors=["A"])
    assert p.content_tier == "metadata"


def test_paper_content_tier_full_text():
    p = Paper(paper_id="p1", title="Test", authors=["A"],
              content_tier="full_text", full_text="some content")
    assert p.content_tier == "full_text"
    assert p.full_text == "some content"


def test_paper_local_pdf_path():
    p = Paper(paper_id="p1", title="Test", authors=["A"],
              local_pdf_path="/tmp/paper.pdf")
    assert p.local_pdf_path == "/tmp/paper.pdf"


def test_paper_source_default():
    p = Paper(paper_id="p1", title="Test", authors=["A"])
    assert p.source == "search"


def test_paper_source_zotero():
    p = Paper(paper_id="p1", title="Test", authors=["A"], source="zotero")
    assert p.source == "zotero"


def test_paper_user_notes():
    p = Paper(paper_id="p1", title="Test", authors=["A"],
              user_notes="Important theorem in section 3")
    assert p.user_notes == "Important theorem in section 3"


def test_paper_backward_compatible():
    """Existing code that creates Paper without new fields must still work."""
    p = Paper(
        paper_id="old-paper",
        title="Old Style",
        authors=["B"],
        year=2024,
        abstract="An abstract",
        venue="NeurIPS",
        arxiv_id="2401.12345",
        relevance_score=0.8,
    )
    assert p.content_tier == "metadata"
    assert p.full_text is None
    assert p.local_pdf_path is None
    assert p.source == "search"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_tier.py -v`
Expected: FAIL — `Paper` has no `content_tier` field

- [ ] **Step 3: Add new fields to Paper model**

In `eurekalab/types/artifacts.py`, add these fields to the `Paper` class after the existing `relevance_score` field:

```python
    # Content tracking (Phase 1)
    content_tier: Literal["full_text", "abstract", "metadata", "missing"] = "metadata"
    local_pdf_path: str | None = None
    full_text: str | None = None
    user_notes: str = ""
    source: str = "search"  # "search", "zotero", "user_provided", "bib_import", "draft"
```

Also add `Literal` to the imports from `typing` if not already present.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_content_tier.py tests/unit/test_types.py -v`
Expected: All PASS (new tests + existing type tests for backward compat)

- [ ] **Step 5: Commit**

```bash
git add eurekalab/types/artifacts.py tests/test_content_tier.py
git commit -m "feat: add content_tier and source fields to Paper model"
```

---

### Task 2: ContentGapAnalyzer

**Files:**
- Create: `eurekalab/analyzers/__init__.py`
- Create: `eurekalab/analyzers/content_gap.py`
- Test: `tests/test_content_tier.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_content_tier.py`:

```python
from eurekalab.types.artifacts import Bibliography
from eurekalab.analyzers.content_gap import ContentGapAnalyzer, ContentGapReport


def test_gap_report_categorizes_tiers():
    papers = [
        Paper(paper_id="p1", title="Full", authors=[], content_tier="full_text"),
        Paper(paper_id="p2", title="Abstract", authors=[], content_tier="abstract"),
        Paper(paper_id="p3", title="Meta", authors=[], content_tier="metadata"),
        Paper(paper_id="p4", title="Missing", authors=[], content_tier="missing"),
    ]
    bib = Bibliography(session_id="test", papers=papers)
    report = ContentGapAnalyzer.analyze(bib)
    assert len(report.full_text) == 1
    assert len(report.abstract_only) == 1
    assert len(report.metadata_only) == 1
    assert len(report.missing) == 1


def test_gap_report_empty_bibliography():
    bib = Bibliography(session_id="test", papers=[])
    report = ContentGapAnalyzer.analyze(bib)
    assert len(report.full_text) == 0
    assert len(report.abstract_only) == 0


def test_gap_report_all_full_text():
    papers = [
        Paper(paper_id="p1", title="A", authors=[], content_tier="full_text"),
        Paper(paper_id="p2", title="B", authors=[], content_tier="full_text"),
    ]
    bib = Bibliography(session_id="test", papers=papers)
    report = ContentGapAnalyzer.analyze(bib)
    assert report.has_gaps is False


def test_gap_report_has_gaps():
    papers = [
        Paper(paper_id="p1", title="A", authors=[], content_tier="full_text"),
        Paper(paper_id="p2", title="B", authors=[], content_tier="abstract"),
    ]
    bib = Bibliography(session_id="test", papers=papers)
    report = ContentGapAnalyzer.analyze(bib)
    assert report.has_gaps is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_tier.py::test_gap_report_categorizes_tiers -v`
Expected: FAIL — `No module named 'eurekalab.analyzers'`

- [ ] **Step 3: Implement ContentGapAnalyzer**

```python
# eurekalab/analyzers/__init__.py
"""Analyzers for content gaps, draft papers, and bibliography loading."""
```

```python
# eurekalab/analyzers/content_gap.py
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_content_tier.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add eurekalab/analyzers/ tests/test_content_tier.py
git commit -m "feat: add ContentGapAnalyzer for tracking paper content completeness"
```

---

### Task 3: BibLoader — Parse .bib Files

**Files:**
- Create: `eurekalab/analyzers/bib_loader.py`
- Create: `tests/test_bib_loader.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_bib_loader.py
"""Tests for BibLoader — .bib file parsing and PDF matching."""
import pytest
from pathlib import Path
from eurekalab.analyzers.bib_loader import BibLoader
from eurekalab.types.artifacts import Paper


SAMPLE_BIB = """\
@article{smith2024,
  title = {Optimal Bounds for Contextual Bandits},
  author = {Smith, John and Doe, Jane},
  year = {2024},
  journal = {arXiv preprint arXiv:2401.12345},
}

@inproceedings{jones2023,
  title = {Concentration Inequalities for RL},
  author = {Jones, Alice},
  year = {2023},
  booktitle = {NeurIPS},
}

@misc{noauthor2022,
  title = {A Survey of Methods},
  year = {2022},
}
"""


@pytest.fixture
def bib_file(tmp_path) -> Path:
    path = tmp_path / "references.bib"
    path.write_text(SAMPLE_BIB)
    return path


def test_load_parses_all_entries(bib_file):
    papers = BibLoader.load_bib(bib_file)
    assert len(papers) == 3


def test_load_extracts_title(bib_file):
    papers = BibLoader.load_bib(bib_file)
    titles = {p.title for p in papers}
    assert "Optimal Bounds for Contextual Bandits" in titles


def test_load_extracts_authors(bib_file):
    papers = BibLoader.load_bib(bib_file)
    smith = next(p for p in papers if "Smith" in p.title or "Optimal" in p.title)
    assert len(smith.authors) == 2
    assert any("Smith" in a for a in smith.authors)


def test_load_extracts_year(bib_file):
    papers = BibLoader.load_bib(bib_file)
    smith = next(p for p in papers if "Optimal" in p.title)
    assert smith.year == 2024


def test_load_extracts_arxiv_id(bib_file):
    papers = BibLoader.load_bib(bib_file)
    smith = next(p for p in papers if "Optimal" in p.title)
    assert smith.arxiv_id == "2401.12345"


def test_load_sets_source_bib_import(bib_file):
    papers = BibLoader.load_bib(bib_file)
    assert all(p.source == "bib_import" for p in papers)


def test_load_sets_content_tier_metadata(bib_file):
    papers = BibLoader.load_bib(bib_file)
    assert all(p.content_tier == "metadata" for p in papers)


def test_load_handles_missing_author(bib_file):
    papers = BibLoader.load_bib(bib_file)
    noauth = next(p for p in papers if "Survey" in p.title)
    assert noauth.authors == [] or noauth.authors == [""]


def test_match_pdfs(bib_file, tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "2401.12345.pdf").write_bytes(b"%PDF-fake")
    papers = BibLoader.load_bib(bib_file)
    matched = BibLoader.match_pdfs(papers, pdf_dir)
    smith = next(p for p in matched if "Optimal" in p.title)
    assert smith.local_pdf_path is not None
    assert smith.content_tier == "metadata"  # not yet extracted, just matched


def test_match_pdfs_no_match(bib_file, tmp_path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    papers = BibLoader.load_bib(bib_file)
    matched = BibLoader.match_pdfs(papers, pdf_dir)
    assert all(p.local_pdf_path is None for p in matched)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bib_loader.py -v`
Expected: FAIL — `No module named 'eurekalab.analyzers.bib_loader'`

- [ ] **Step 3: Implement BibLoader**

```python
# eurekalab/analyzers/bib_loader.py
"""BibLoader — parse .bib files into Paper objects and match local PDFs."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import bibtexparser

from eurekalab.types.artifacts import Paper

logger = logging.getLogger(__name__)


def _extract_arxiv_id(entry: dict) -> str | None:
    """Try to extract an arXiv ID from various bib fields."""
    for field in ("journal", "eprint", "url", "note", "doi"):
        val = entry.get(field, "")
        m = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", val)
        if m:
            return m.group(1)
    return None


def _parse_authors(raw: str) -> list[str]:
    """Parse BibTeX author string ('Last, First and Last2, First2') into list."""
    if not raw:
        return []
    parts = [a.strip() for a in raw.split(" and ") if a.strip()]
    return parts


class BibLoader:
    """Parse .bib files into Paper objects and match local PDFs."""

    @staticmethod
    def load_bib(bib_path: Path) -> list[Paper]:
        """Parse a .bib file and return a list of Paper objects."""
        text = bib_path.read_text(encoding="utf-8")
        bib_db = bibtexparser.parse(text)

        papers: list[Paper] = []
        for entry in bib_db.entries:
            fields = {f.key: f.value for f in entry.fields}
            title = fields.get("title", "").strip("{}")
            authors_raw = fields.get("author", "")
            year_str = fields.get("year", "")
            venue = fields.get("booktitle", "") or fields.get("journal", "")
            arxiv_id = _extract_arxiv_id(fields)
            url = fields.get("url", "") or fields.get("doi", "")

            year = None
            if year_str:
                try:
                    year = int(year_str.strip())
                except ValueError:
                    pass

            paper_id = arxiv_id or entry.key or title[:30]

            papers.append(Paper(
                paper_id=paper_id,
                title=title,
                authors=_parse_authors(authors_raw),
                year=year,
                venue=venue.strip("{}"),
                arxiv_id=arxiv_id,
                url=url,
                source="bib_import",
                content_tier="metadata",
            ))

        logger.info("BibLoader: parsed %d entries from %s", len(papers), bib_path)
        return papers

    @staticmethod
    def match_pdfs(papers: list[Paper], pdf_dir: Path) -> list[Paper]:
        """Match papers to local PDF files by arxiv_id or paper_id.

        Checks for files named: {arxiv_id}.pdf, {paper_id}.pdf, or
        any PDF containing the arxiv_id in its filename.
        """
        if not pdf_dir.exists():
            return papers

        pdf_files = {f.stem.lower(): f for f in pdf_dir.glob("*.pdf")}

        for paper in papers:
            candidates = []
            if paper.arxiv_id:
                candidates.append(paper.arxiv_id.lower())
                # Also try without version suffix
                base = re.sub(r"v\d+$", "", paper.arxiv_id.lower())
                candidates.append(base)
            candidates.append(paper.paper_id.lower())

            for cand in candidates:
                if cand in pdf_files:
                    paper.local_pdf_path = str(pdf_files[cand])
                    break
            else:
                # Fuzzy: check if any PDF filename contains the arxiv_id
                if paper.arxiv_id:
                    for stem, path in pdf_files.items():
                        if paper.arxiv_id.lower() in stem:
                            paper.local_pdf_path = str(path)
                            break

        matched = sum(1 for p in papers if p.local_pdf_path)
        logger.info("BibLoader: matched %d/%d papers to local PDFs", matched, len(papers))
        return papers
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_bib_loader.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add eurekalab/analyzers/bib_loader.py tests/test_bib_loader.py
git commit -m "feat: add BibLoader for parsing .bib files and matching local PDFs"
```

---

### Task 4: Interactive Content Gap Report in Gate

**Files:**
- Modify: `eurekalab/orchestrator/gate.py`

- [ ] **Step 1: Add content gap report method to GateController**

After the existing `_print_survey_summary` method, add:

```python
def print_content_status(self) -> str | None:
    """Show content availability report after survey and prompt for missing papers.

    Returns the user's response (path to PDFs, 'skip', or None).
    """
    if not self.bus:
        return None
    bib = self.bus.get_bibliography()
    if not bib or not bib.papers:
        return None

    from eurekalab.analyzers.content_gap import ContentGapAnalyzer
    report = ContentGapAnalyzer.analyze(bib)

    lines = [
        f"[bold]Full text available:[/bold] {len(report.full_text)} papers",
        f"[bold]Abstract only:[/bold]      {len(report.abstract_only)} papers",
        f"[bold]Metadata only:[/bold]      {len(report.metadata_only)} papers",
    ]
    if report.missing:
        lines.append(f"[bold red]Missing:[/bold red]             {len(report.missing)} papers")

    border = "green" if not report.has_gaps else "yellow"
    console.print(Panel("\n".join(lines),
                        title="[cyan]Content Status[/cyan]",
                        border_style=border))

    if not report.has_gaps:
        return None

    # Show top degraded papers
    degraded = report.abstract_only + report.metadata_only
    if degraded:
        console.print("\n[yellow]Papers with limited content:[/yellow]")
        for p in degraded[:5]:
            tier_label = "[dim]abstract[/dim]" if p.content_tier == "abstract" else "[red]metadata only[/red]"
            arxiv_hint = f" (arXiv: {p.arxiv_id})" if p.arxiv_id else ""
            console.print(f"  {tier_label} {p.title[:70]}{arxiv_hint}")
        if len(degraded) > 5:
            console.print(f"  [dim]… and {len(degraded) - 5} more[/dim]")

    try:
        action = Prompt.ask(
            "\n[bold]Content gaps detected.[/bold] Options:\n"
            "  [cyan]path[/cyan]  — provide a directory of PDFs to match\n"
            "  [cyan]skip[/cyan]  — proceed with what we have\n"
            "  [cyan]Enter[/cyan] — skip",
            default="skip",
        )
    except (KeyboardInterrupt, EOFError):
        return None

    return action.strip() if action.strip().lower() != "skip" else None
```

- [ ] **Step 2: Wire into MetaOrchestrator after survey stage**

In `eurekalab/orchestrator/meta_orchestrator.py`, find the block after survey completion (around line 230):
```python
if task.name == "survey":
    await self._handle_empty_survey_fallback(pipeline)
```

Add after it:
```python
                if task.name == "survey":
                    self._handle_content_gaps()
```

And add the helper method to MetaOrchestrator:
```python
def _handle_content_gaps(self) -> None:
    """Show content status and optionally match local PDFs."""
    response = self.gate.print_content_status()
    if response and response != "skip":
        from pathlib import Path
        pdf_dir = Path(response).expanduser()
        if pdf_dir.is_dir():
            from eurekalab.analyzers.bib_loader import BibLoader
            bib = self.bus.get_bibliography()
            if bib:
                BibLoader.match_pdfs(bib.papers, pdf_dir)
                # Extract text from matched PDFs
                self._extract_matched_pdfs(bib)
                self.bus.put_bibliography(bib)
                matched = sum(1 for p in bib.papers if p.local_pdf_path)
                console.print(f"[green]Matched {matched} papers to local PDFs.[/green]")
        else:
            console.print(f"[red]Directory not found: {pdf_dir}[/red]")

def _extract_matched_pdfs(self, bib: "Bibliography") -> None:
    """Extract text from matched local PDFs using pdfplumber."""
    for paper in bib.papers:
        if paper.local_pdf_path and paper.content_tier != "full_text":
            try:
                import pdfplumber
                with pdfplumber.open(paper.local_pdf_path) as pdf:
                    pages = [page.extract_text() or "" for page in pdf.pages]
                    paper.full_text = "\n\n".join(pages)
                    paper.content_tier = "full_text"
            except Exception as e:
                logger.warning("PDF extraction failed for '%s': %s", paper.title, e)
```

- [ ] **Step 3: Run existing tests to confirm no regressions**

Run: `pytest tests/ -v --tb=short -x`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add eurekalab/orchestrator/gate.py eurekalab/orchestrator/meta_orchestrator.py
git commit -m "feat: add interactive content gap report after survey"
```

---

### Task 5: Update SurveyAgent Content Tier Assignment

**Files:**
- Modify: `eurekalab/agents/survey/agent.py` (lines 139-154, Paper creation)

- [ ] **Step 1: Set content_tier based on what's available in survey results**

In the Paper creation loop in `survey/agent.py`, after the existing fields, add logic to set `content_tier`:

Find the Paper creation (around line 139-154) and add `content_tier` assignment:

```python
# After creating the paper object, set content_tier based on available data
content_tier = "metadata"
if p.get("abstract", ""):
    content_tier = "abstract"
# full_text would only be set if PDF extraction happened later
```

Add `content_tier=content_tier` to the Paper constructor call.

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v --tb=short -x`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add eurekalab/agents/survey/agent.py
git commit -m "feat: set content_tier on papers during survey based on available data"
```

---

### Task 6: `from-bib` CLI Command

**Files:**
- Modify: `eurekalab/cli.py`

- [ ] **Step 1: Add the from-bib command**

Add after the `from-papers` command:

```python
@main.command("from-bib")
@click.argument("bib_file", type=click.Path(exists=True))
@click.option("--pdfs", "-p", default=None, type=click.Path(exists=True),
              help="Directory containing local PDF files to match")
@click.option("--domain", "-d", required=True, help="Research domain")
@click.option("--query", "-q", default="", help="Specific research question")
@click.option("--mode", default="skills_only", type=click.Choice(["skills_only", "rl", "madmax"]))
@click.option("--gate", default="none", type=click.Choice(["human", "auto", "none"]))
@click.option("--output", "-o", default="./results", help="Output directory")
def from_bib(bib_file: str, pdfs: str | None, domain: str, query: str, mode: str, gate: str, output: str) -> None:
    """Start research from a .bib file and optional local PDFs.

    Example: eurekalab from-bib refs.bib --pdfs ./papers/ --domain "ML theory"
    """
    from pathlib import Path
    from eurekalab.analyzers.bib_loader import BibLoader
    from eurekalab.types.artifacts import Bibliography

    # Parse .bib file
    papers = BibLoader.load_bib(Path(bib_file))
    if not papers:
        console.print("[red]No papers found in .bib file.[/red]")
        sys.exit(1)

    console.print(f"[green]Loaded {len(papers)} papers from {bib_file}[/green]")

    # Match local PDFs if directory provided
    if pdfs:
        pdf_dir = Path(pdfs)
        papers = BibLoader.match_pdfs(papers, pdf_dir)
        matched = sum(1 for p in papers if p.local_pdf_path)
        console.print(f"[green]Matched {matched}/{len(papers)} papers to local PDFs[/green]")

        # Extract text from matched PDFs
        for paper in papers:
            if paper.local_pdf_path:
                try:
                    import pdfplumber
                    with pdfplumber.open(paper.local_pdf_path) as pdf:
                        pages = [page.extract_text() or "" for page in pdf.pages]
                        paper.full_text = "\n\n".join(pages)
                        paper.content_tier = "full_text"
                except Exception as e:
                    console.print(f"[yellow]PDF extraction failed for '{paper.title[:50]}': {e}[/yellow]")

    if not query:
        n = len(papers)
        query = (
            f"You have been provided with {n} papers from the user's bibliography in {domain}. "
            f"These papers are already loaded — do NOT search for them again. "
            f"Instead, identify gaps in coverage: what related work is missing? "
            f"What recent advances are not represented? What foundational work should be added? "
            f"Search for papers that complement this existing collection."
        )

    # Extract paper IDs for the survey agent to recognize as pre-loaded
    paper_ids = [p.paper_id for p in papers if p.paper_id]

    _run_session(
        mode="reference",
        query=query,
        domain=domain,
        paper_ids=paper_ids,
        learn_mode=mode,
        gate=gate,
        output_dir=output,
        _preloaded_papers=papers,
    )
```

- [ ] **Step 2: Modify `_run_session` to accept preloaded papers**

Add `_preloaded_papers: list | None = None` parameter to `_run_session`. Before `session.run(spec)`, if `_preloaded_papers` is provided, pre-populate the bibliography on the bus:

```python
if _preloaded_papers:
    from eurekalab.types.artifacts import Bibliography
    bib = Bibliography(session_id=session.session_id, papers=_preloaded_papers)
    session.bus.put_bibliography(bib)
```

- [ ] **Step 3: Verify the command registers**

Run: `.venv/bin/python -m eurekalab.cli --help`
Expected: `from-bib` appears in command list

- [ ] **Step 4: Run all tests**

Run: `pytest tests/ -v --tb=short -x`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add eurekalab/cli.py
git commit -m "feat: add from-bib CLI command for starting from .bib files"
```

---

### Task 7: Version Bump and Push

- [ ] **Step 1: Bump version to 0.2.1**

In `pyproject.toml`: change `version = "0.2.0"` to `version = "0.2.1"`
In `eurekalab/__init__.py`: change `__version__ = "0.2.0"` to `__version__ = "0.2.1"`

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 3: Commit and push**

```bash
git add eurekalab/__init__.py pyproject.toml
git commit -m "feat: content tiers, gap analysis, and from-bib entry point (Phases 1+2)

- Paper model extended with content_tier, full_text, local_pdf_path, source
- ContentGapAnalyzer reports content availability after survey
- Interactive gap-filling prompts user for PDF directory
- BibLoader parses .bib files via bibtexparser, matches local PDFs
- from-bib CLI command: start research from existing bibliography
- Bump to v0.2.1"
git push
```
