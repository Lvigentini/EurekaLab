# Zotero Integration, Flexible Entry Points & Non-Linear Research — Design Plan v2

**Status:** Draft / Discussion
**Date:** 2026-03-26
**Version:** 0.1.1

---

## 1. The Problem With the Current Pipeline

EurekaLab's pipeline is a **linear waterfall**:

```
survey → ideation → direction_gate → theory → review → experiment → writer
```

This model fails real research in three fundamental ways:

### 1.1 The Content Access Problem

The survey stage searches arXiv and Semantic Scholar, finds citations, and builds a bibliography. But **finding a citation is not the same as having the paper**. The current pipeline:

- Finds a paper title and abstract via API
- Attempts to fetch the PDF from arXiv (often fails: paywalled, not on arXiv, rate-limited)
- Falls back to abstract-only extraction (loses 90%+ of the actual content)
- Proceeds as if this thin signal is sufficient

Meanwhile, the researcher using EurekaLab likely has **institutional access** — they can download any paper via their university library, Sci-Hub, or direct author contact. They use Zotero's browser connector to save papers with full PDFs as a matter of routine.

**The fix is not better automated downloading. The fix is leveraging what the user already has, and prompting them to get what's missing.**

### 1.2 The Ideation Rigidity Problem

The current pipeline treats ideation as a **single event** — one pass that produces 5 directions, then you pick one and move on. Real research doesn't work this way:

- You read a paper and it sparks a new idea → that idea should feed back into ideation
- You prove a lemma and realize the approach generalizes → the direction should evolve
- You find a counterexample and need to pivot → backtrack to ideation with new constraints
- A colleague suggests a connection to another field → inject that into the mix

Ideation is a **continuous, snowballing process** that runs alongside every other stage. The current architecture makes it a gate you pass through once.

### 1.3 The Forward-Only Problem

Once a stage completes, its output is frozen. There is no mechanism to:

- Add a paper to the bibliography after survey is done
- Revise a research direction after theory has started
- Incorporate new ideas that emerge during proving
- Roll back to an earlier state when an approach fails

This makes the tool brittle: any mistake or missing input in early stages propagates uncorrected through the entire pipeline.

---

## 2. Design Principles for the Redesign

### P1: The user's library is the ground truth, not automated search

Automated search supplements the user's collection. It doesn't replace it. When the system identifies a gap ("you should cite Smith et al. 2024"), the correct response is to **ask the user to obtain it** (via Zotero + institutional access), not to silently proceed with an abstract-only placeholder.

### P2: Ideation is continuous, not a stage

Every interaction with a paper, every proven lemma, every failed attempt, every user insight should be able to feed back into the ideation pool. The "ideation stage" becomes the initial seeding; the ideation *process* runs throughout.

### P3: Every state change is versioned

Like git, every modification to the research state (new paper added, direction revised, lemma proven, idea injected) creates a new version. The user can inspect the history, compare versions, and roll back to any point. This makes backtracking safe — you never lose work.

### P4: The pipeline is re-entrant, not linear

Any stage can be re-entered at any time with new inputs. Re-entry triggers a **delta run** — the stage receives both its previous output and the new inputs, and produces a merged result. The user sees what changed.

### P5: Prompt the user, don't silently degrade

When the system can't access a paper, can't resolve a citation, or hits a dead end in proving — **stop and ask**. A 30-second human intervention (downloading a PDF, clarifying an approach) is worth more than hours of the system working with incomplete information.

---

## 3. Zotero as the Research Backbone

### 3.1 Why Zotero Changes Everything

Zotero is not just a metadata store. It's the researcher's **knowledge management system**:

| What Zotero has | What EurekaLab currently does | The gap |
|---|---|---|
| Full PDFs (via institutional access) | Tries to fetch from arXiv (often fails) | Massive content loss |
| User annotations & highlights | Ignores them | Loses the user's existing analysis |
| User notes per paper | Ignores them | Loses domain expertise |
| Tags & collections (curated) | Auto-generates relevance scores | Less accurate than human curation |
| Citation graph (via plugins) | Builds its own from API data | Duplicated effort |
| Browser connector (one-click save) | Automated PDF download | User's institutional access >> API access |

### 3.2 Bidirectional Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       ZOTERO LIBRARY                         │
│                                                              │
│  Collections ── Items ── PDFs ── Notes ── Tags               │
│       │           │        │        │        │               │
│       │     annotations  highlights  user    curated         │
│       │                             analysis  groups         │
└───────┬──────────────────────────────────────┬───────────────┘
        │ INGEST                               │ ENRICH
        ▼                                      ▲
┌──────────────────────────────────────────────────────────────┐
│                       ZoteroAdapter                           │
│                                                               │
│  Ingest:                          Enrich:                     │
│   import_collection(id)            push_discovered_papers()   │
│   import_item(key)                 push_proof_notes()         │
│   watch_collection(id, callback)   push_session_tags()        │
│   request_paper(title, doi)        push_final_paper()         │
│     → prompts user to add via      create_session_collection()│
│       browser connector                                       │
│                                                               │
│  Content extraction:                                          │
│   extract_pdf_text(item) → pdfplumber                         │
│   extract_annotations(item) → user highlights                 │
│   extract_notes(item) → user notes as context                 │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 The "Request Paper" Flow

When EurekaLab identifies a paper it needs but doesn't have:

```
1. System identifies: "Smith et al. 2024 is cited 12 times in your
   bibliography but you don't have it"

2. System prompts:
   ┌─────────────────────────────────────────────────────────┐
   │  📄 Missing paper: "Optimal Bounds for Contextual       │
   │     Bandits with Linear Payoffs" (Smith et al., 2024)   │
   │                                                          │
   │  DOI: 10.1234/example                                    │
   │  Why needed: Cited by 3 of your papers; contains         │
   │  Theorem 4.2 (regret bound) which is directly relevant   │
   │  to your proof approach.                                  │
   │                                                          │
   │  [1] I'll add it to Zotero now (wait for me)             │
   │  [2] Skip this paper                                      │
   │  [3] I have it locally (provide path)                     │
   └─────────────────────────────────────────────────────────┘

3. If user chooses [1]:
   - User opens DOI link, downloads via institutional access
   - Saves to Zotero via browser connector
   - EurekaLab detects the new item (via polling or manual "done" signal)
   - Extracts full text and continues

4. If user chooses [3]:
   - User provides path to PDF
   - EurekaLab extracts text via pdfplumber
   - Optionally pushes to Zotero for future reference
```

### 3.4 Connection Method

**pyzotero (Web API)** as the primary interface:
- Works with synced libraries (Zotero cloud)
- Official, stable, well-documented
- Handles auth via API key
- Can read items, collections, attachments, notes, tags
- Can write items, notes, tags, collections
- Can access file storage (PDFs) for cloud-synced libraries

**Local file access** as optimization for PDFs:
- Zotero stores PDFs locally at a known path (`~/Zotero/storage/<key>/`)
- When local Zotero is detected, read PDFs directly from disk (faster than API download)
- Use pyzotero for metadata, local filesystem for content

**Configuration:**
```
ZOTERO_ENABLED=true
ZOTERO_API_KEY=...
ZOTERO_LIBRARY_ID=...
ZOTERO_LIBRARY_TYPE=user|group
ZOTERO_LOCAL_DATA_DIR=~/Zotero    # optional, for direct PDF access
ZOTERO_SYNC_BACK=true             # push discoveries back to Zotero
```

---

## 4. Versioned Research State (The Git Model)

### 4.1 Why Versioning is Non-Negotiable

Backtracking without versioning means overwriting previous work. The user proves 5 lemmas, then backtracks to revise the direction — those 5 lemmas are gone. Even with snapshots, managing "which snapshot had what" becomes manual and error-prone.

The solution: **every state change creates a version**, and the full history is preserved.

### 4.2 Version Store Design

```python
class ResearchVersion:
    """A single point-in-time snapshot of the full research state."""
    version_id: str                    # auto-incremented or UUID
    parent_version_id: str | None      # for branching
    timestamp: datetime
    trigger: str                       # what caused this version
                                       # e.g. "stage:survey:completed",
                                       #      "inject:paper:2403.12345",
                                       #      "inject:idea:spectral_methods",
                                       #      "backtrack:ideation:user_requested"

    # Full state at this version
    research_brief: ResearchBrief
    bibliography: Bibliography
    theory_state: TheoryState | None
    experiment_result: ExperimentResult | None
    pipeline_progress: list[str]       # completed stage names

    # Delta from parent (for display)
    changes: list[str]                 # human-readable change descriptions


class VersionStore:
    """Git-like version history for a research session."""

    def commit(self, state: BusSnapshot, trigger: str) -> ResearchVersion:
        """Create a new version from current bus state."""

    def checkout(self, version_id: str) -> BusSnapshot:
        """Restore bus state to a specific version."""

    def diff(self, v1: str, v2: str) -> list[str]:
        """Show what changed between two versions."""

    def log(self) -> list[ResearchVersion]:
        """Show version history (like git log)."""

    def branch(self, from_version: str, name: str) -> str:
        """Create a named branch from a version."""

    @property
    def head(self) -> ResearchVersion:
        """Current version."""
```

### 4.3 What Triggers a New Version

| Event | Trigger string | What's captured |
|---|---|---|
| Survey completes | `stage:survey:completed` | Bibliography, ResearchBrief updates |
| Ideation completes | `stage:ideation:completed` | New directions on brief |
| Direction selected | `direction:selected:<title>` | selected_direction set |
| Lemma proven | `theory:lemma:proven:<id>` | TheoryState update |
| User injects paper | `inject:paper:<id>` | Bibliography addition |
| User injects idea | `inject:idea:<summary>` | Brief.injected_ideas update |
| User injects draft | `inject:draft:<filename>` | Brief + Bibliography update |
| User backtracks | `backtrack:<stage>` | Checkout of earlier version + re-run |
| Stage re-run | `rerun:<stage>:v<N>` | Merged output |
| Zotero sync | `zotero:sync:<collection>` | Bibliography additions |
| User provides missing paper | `user:paper:provided:<id>` | Paper content populated |

### 4.4 Storage

Versions are stored as JSON files in the session directory:

```
~/.eurekalab/runs/<session-id>/
  versions/
    v001_stage_survey_completed.json
    v002_stage_ideation_completed.json
    v003_direction_selected.json
    v004_inject_paper_2403.12345.json
    v005_rerun_ideation_v2.json
    v006_theory_lemma_proven_L1.json
    ...
  _version_head.json    # pointer to current version
  _version_log.json     # ordered list of versions with metadata
```

Each version file contains the full state (not just the delta). This makes checkout instant at the cost of some disk space. For a typical session with 20-30 versions, this is ~5-10MB total.

### 4.5 CLI Commands for Version Management

```bash
# Show version history
eurekalab history <session-id>
  v006  2h ago   theory:lemma:proven:L1      "Proved concentration inequality lemma"
  v005  3h ago   rerun:ideation:v2           "Re-ran ideation with 3 new papers"
  v004  3h ago   inject:paper:2403.12345     "Added Smith et al. 2024"
  v003  4h ago   direction:selected          "Selected: Optimal regret bounds..."
  v002  4h ago   stage:ideation:completed    "5 directions generated"
  v001  5h ago   stage:survey:completed      "Found 23 papers"

# Show what changed between versions
eurekalab diff <session-id> v002 v005
  Bibliography: +3 papers (Smith 2024, Jones 2023, Lee 2024)
  Directions: +2 new, 1 revised, 4 unchanged
  Selected direction: unchanged

# Roll back to a specific version
eurekalab checkout <session-id> v003
  Restored state to v003 (direction:selected)
  Current pipeline: survey ✓, ideation ✓, direction_gate ✓
  Next stage: theory

# Continue from current version
eurekalab resume <session-id>
```

---

## 5. Non-Linear Pipeline: Re-Entrant Stages and Continuous Ideation

### 5.1 Replacing the Waterfall

The current linear pipeline is replaced by a **state machine** where stages can be re-entered:

```
                    ┌──────────────────────────────┐
                    │                              │
                    ▼                              │
              ┌──────────┐    inject paper    ┌────┴─────┐
     ┌───────►│  SURVEY   │◄─────────────────│  USER     │
     │        │ (gap-fill)│   inject idea     │  INPUT    │
     │        └─────┬─────┘   inject draft    │  (anytime)│
     │              │         request paper    └────┬─────┘
     │              ▼                               │
     │        ┌──────────┐                          │
     │   ┌───►│ IDEATION  │◄────────────────────────┘
     │   │    │ (evolving)│
     │   │    └─────┬─────┘
     │   │          │
     │   │          ▼
     │   │    ┌──────────┐
     │   │    │DIRECTION  │──── user picks / revises
     │   │    │  GATE     │
     │   │    └─────┬─────┘
     │   │          │
     │   │          ▼
     │   │    ┌──────────┐     new insight
     │   └────│  THEORY   │────────────────┐
     │        │  (prove)  │                │
     │        └─────┬─────┘                │
     │              │                      │
     │              ▼                      ▼
     │        ┌──────────┐          ┌──────────┐
     │        │  REVIEW   │         │ IDEATION  │ (re-entry
     │        │  GATE     │         │ EXPANSION │  with new
     │        └─────┬─────┘         └───────────┘  context)
     │              │
     │              ▼
     │        ┌──────────┐
     │        │  WRITER   │
     │        └─────┬─────┘
     │              │
     │              ▼
     └────── (backtrack if needed)
```

### 5.2 Ideation as a Living Document

Instead of a single ideation pass, the `ResearchBrief.directions` becomes a **versioned, evolving document**:

```python
class IdeationPool:
    """Continuously evolving pool of research directions and ideas."""

    directions: list[ResearchDirection]      # scored, ranked directions
    selected_direction: ResearchDirection     # current active direction

    # The snowball
    injected_ideas: list[InjectedIdea]       # user-provided ideas
    emerged_insights: list[str]              # insights from theory/proving
    discarded_directions: list[tuple[ResearchDirection, str]]  # direction + why discarded

    # Provenance
    idea_sources: dict[str, str]             # idea_id → source
                                             # "survey:paper:2403.12345"
                                             # "user:injection:2026-03-26T14:30"
                                             # "theory:lemma_failure:L3"
                                             # "draft:section:3.2"


class InjectedIdea:
    """An idea injected by the user at any point in the process."""
    text: str
    injected_at: datetime
    injected_during_stage: str               # which stage was running
    source: str                              # "user", "draft", "paper:id"
    incorporated: bool = False               # has ideation processed this?
```

### 5.3 Stage Re-Entry Protocol

When a stage is re-entered (e.g., ideation re-runs after a paper injection):

1. **Version the current state** (automatic commit)
2. **Load the previous stage output** as context
3. **Provide the new inputs** (injected papers, ideas, insights)
4. **Run a delta prompt** — not "generate directions from scratch" but "given your previous directions AND this new information, revise/extend/add directions"
5. **Present the diff to the user** — "2 new directions, 1 revised, 1 removed (with explanation)"
6. **User confirms** the merged result
7. **Version the new state** (new commit)

Example delta prompt for ideation re-entry:

```
You previously generated these research directions:
{previous_directions}

Since then, the following new inputs have been added:
- New papers: {new_papers_with_abstracts}
- User ideas: {injected_ideas}
- Insights from theory work: {emerged_insights}

Revise the direction pool:
1. Keep directions that are still valid (with updated justification if needed)
2. Add new directions suggested by the new inputs
3. Flag any previous directions that are now superseded or invalidated
4. For each change, explain why

Output the full revised direction list with change annotations.
```

### 5.4 Theory-to-Ideation Feedback Loop

The theory stage often produces insights that should feed back into ideation:

- **Failed proof attempt:** "Lemma L3 failed because the assumption X is too strong" → ideation should know this constraint
- **Unexpected generalization:** "The bound actually holds for a broader class" → ideation should consider the generalized direction
- **Missing tool:** "We need a concentration inequality that doesn't exist in the literature" → survey should search for it, ideation should consider alternative approaches
- **Counterexample found:** "The conjecture is false for d > 5" → ideation must pivot

These are captured as `emerged_insights` on the `IdeationPool` and trigger a re-entry into ideation when significant enough.

**Significance threshold:** Not every lemma proof should trigger re-ideation. Use heuristics:
- Failed proof of a key lemma (not a sub-lemma) → trigger
- Generalization that changes the scope of the result → trigger
- Minor technical difficulties → log but don't trigger
- User explicitly requests re-ideation → always trigger

---

## 6. Draft Paper Integration (Detailed)

### 6.1 What a Draft Tells Us

A draft paper is not a single signal — it's a **rich, multi-layered input**:

| Layer | What it contains | How EurekaLab uses it |
|---|---|---|
| **Metadata** | Title, abstract, authors | Domain detection, query seeding |
| **References** | \cite{} keys, bibliography | Seed the bibliography (if user has PDFs) |
| **Claims** | Theorems, lemmas, conjectures | Theory stage: verify, strengthen, prove |
| **Structure** | Sections, outline, TODOs | Writer stage: preserve structure, fill gaps |
| **Direction** | The overall research question | One input to ideation (not the only one) |
| **Gaps** | Empty sections, \todo{}, TBD | Guide where EurekaLab should focus effort |
| **Voice** | Writing style, notation choices | Writer stage: match the user's style |

### 6.2 Draft Injection Modes

The user's intent varies. The draft could be:

**a) "My work-in-progress — help me finish it"**
- Strong direction signal (don't override, but expand around it)
- Claims need proving
- Gaps need filling
- Survey should find what's missing

**b) "A related paper I'm reading — use its ideas"**
- Not the user's direction, but relevant context
- Extract techniques and results as `known_results`
- Feed into ideation as inspiration, not as anchor

**c) "My previous paper — extend this work"**
- Direction should build on (not repeat) the draft
- Known results are established baselines
- Survey should find what's happened since

**d) "A competing paper — differentiate from this"**
- Ideation should explicitly contrast with this approach
- Theory should find where it falls short
- Writer should position against it

Rather than explicit `--intent` flags, **let the LLM infer intent** from a brief user prompt:

```bash
eurekalab from-draft paper.tex "This is my WIP. Help me strengthen the theory section."
eurekalab from-draft competing.pdf "This is a competing approach. Find its weaknesses."
eurekalab from-draft previous.tex "Extend this to the non-stationary setting."
```

The free-text instruction becomes `ResearchBrief.additional_context` and guides all downstream stages.

### 6.3 Draft Analysis Pipeline

```
Input: draft file (LaTeX / Markdown / PDF) + user instruction
                    │
                    ▼
        ┌─────────────────────┐
        │   Text Extraction    │  pdfplumber (PDF) or raw read (tex/md)
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │   LLM Analysis       │  "Extract from this draft:
        │                      │   - stated claims (theorems, lemmas)
        │                      │   - cited references (with keys)
        │                      │   - research direction
        │                      │   - structural gaps / TODOs
        │                      │   - key notation"
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │   Reference          │  Map \cite{} keys to real papers:
        │   Resolution         │  - Match against Zotero library
        │                      │  - Search arXiv/S2 for unmatched
        │                      │  - Prompt user for unfound papers
        └──────────┬──────────┘
                   │
                   ▼
        Injected into KnowledgeBus:
          - Bibliography (from resolved references)
          - ResearchBrief.draft_summary
          - ResearchBrief.draft_claims
          - ResearchBrief.additional_context (user instruction)
          - IdeationPool seed (draft direction as one input)
```

---

## 7. The "Request Missing Content" System

### 7.1 Content Availability Tiers

Every paper in the bibliography should have a content tier:

```python
class ContentTier(str, Enum):
    FULL_TEXT = "full_text"        # PDF extracted, full content available
    ABSTRACT_ONLY = "abstract"     # Only abstract available
    METADATA_ONLY = "metadata"     # Title + authors, no abstract
    MISSING = "missing"            # Referenced but not found
```

### 7.2 Content Gap Analysis

After survey (or at any point), the system identifies content gaps:

```python
class ContentGapReport:
    """Analysis of what content is available vs. needed."""

    full_text_papers: list[Paper]       # ready to use
    abstract_only_papers: list[Paper]   # degraded — could prompt user
    missing_papers: list[str]           # cited but not found

    # Prioritized list of papers the user should obtain
    recommended_acquisitions: list[PaperRequest]


class PaperRequest:
    """A paper the system recommends the user obtain."""
    title: str
    doi: str | None
    arxiv_id: str | None
    reason: str                    # why this paper matters
    cited_by: list[str]            # which papers in bibliography cite it
    priority: str                  # "critical", "important", "nice-to-have"
```

### 7.3 Interactive Gap-Filling

```
┌────────────────────────────────────────────────────────────────┐
│  📚 Content Status Report                                      │
│                                                                 │
│  Full text available: 18 papers                                 │
│  Abstract only:        5 papers                                 │
│  Missing:              2 papers                                 │
│                                                                 │
│  ⚠ Recommended acquisitions (sorted by priority):               │
│                                                                 │
│  1. [CRITICAL] "Optimal Regret in Linear Bandits" (Smith 2024)  │
│     DOI: 10.1234/example                                        │
│     Why: Contains Theorem 4.2 used by 3 of your papers          │
│                                                                 │
│  2. [IMPORTANT] "Concentration via Entropy" (Lee 2023)          │
│     arXiv: 2312.09876                                           │
│     Why: Key technique for your proof approach                   │
│                                                                 │
│  Actions:                                                        │
│  [a] I'll add these to Zotero now (pause and wait)               │
│  [s] Skip missing papers (proceed with what we have)             │
│  [p] Provide PDF paths manually                                  │
│  [1-2] Address specific paper                                    │
└────────────────────────────────────────────────────────────────┘
```

The system pauses for the user, doesn't silently degrade.

---

## 8. Proposed Architecture (Revised)

### 8.1 New Components

```
eurekalab/
  integrations/
    zotero/
      __init__.py
      adapter.py           # ZoteroAdapter: pyzotero wrapper
      mapper.py            # Zotero Item ↔ Paper mapping
      local_storage.py     # Direct filesystem access for PDFs
      sync.py              # Bidirectional sync logic
  analyzers/
    draft_analyzer.py      # Parse draft papers (LaTeX/MD/PDF → structured)
    bib_loader.py          # Parse .bib files into Bibliography
    content_gap.py         # Identify missing content, prioritize acquisitions
  versioning/
    version_store.py       # Git-like version management
    snapshot.py            # Bus state serialization/deserialization
    diff.py                # Version comparison and change display
  orchestrator/
    state_machine.py       # Non-linear pipeline execution
    reentry.py             # Delta-run logic for stage re-entry
    ideation_pool.py       # Continuous ideation management
    content_request.py     # Interactive "request missing paper" flow
```

### 8.2 Extended Data Models

```python
# Paper additions
class Paper(BaseModel):
    # ... existing fields ...
    content_tier: ContentTier = ContentTier.METADATA_ONLY
    zotero_item_key: str | None = None
    local_pdf_path: str | None = None
    full_text: str | None = None
    user_notes: str = ""
    user_annotations: str = ""
    source: str = "search"        # "search", "zotero", "user_provided", "draft"

# InputSpec additions
class InputSpec(BaseModel):
    # ... existing fields ...
    zotero_collection_id: str | None = None
    draft_path: str | None = None
    draft_instruction: str = ""    # free-text: "This is my WIP...",
                                   # "Extend this...", etc.
    references_path: str | None = None
    pdf_dir: str | None = None     # directory of local PDFs

# IdeationPool (new)
class IdeationPool(BaseModel):
    directions: list[ResearchDirection] = []
    selected_direction: ResearchDirection | None = None
    injected_ideas: list[InjectedIdea] = []
    emerged_insights: list[str] = []
    discarded: list[tuple[str, str]] = []   # (direction_title, reason)
    version: int = 0

# ResearchBrief additions
class ResearchBrief(BaseModel):
    # ... existing fields ...
    draft_summary: str = ""
    draft_claims: list[str] = []
    ideation_pool: IdeationPool = IdeationPool()
```

### 8.3 New CLI Commands

```bash
# ──── Entry points ────

# From Zotero collection (PDFs already downloaded)
eurekalab from-zotero <collection-id> --domain "ML theory"

# From .bib file + local PDF directory
eurekalab from-bib references.bib --pdfs ./papers/ --domain "ML theory"

# From draft paper (with intent instruction)
eurekalab from-draft paper.tex "This is my WIP, strengthen the theory"

# From draft + Zotero (draft's \cite{} resolved against Zotero library)
eurekalab from-draft paper.tex --zotero-collection <id> "Extend this work"

# ──── Mid-session injection ────

# Inject a paper (from Zotero, arXiv, or local path)
eurekalab inject <session-id> paper 2403.12345
eurekalab inject <session-id> paper ./smith2024.pdf
eurekalab inject <session-id> paper --zotero-key ABC123

# Inject an idea
eurekalab inject <session-id> idea "What if we use spectral methods instead?"

# Inject a draft
eurekalab inject <session-id> draft paper.tex "Consider these results too"

# ──── Version management ────

# Show session history
eurekalab history <session-id>

# Show diff between versions
eurekalab diff <session-id> v3 v7

# Roll back to a version
eurekalab checkout <session-id> v3

# Resume from current HEAD
eurekalab resume <session-id>

# ──── Zotero sync ────

# Push results back to Zotero
eurekalab push-to-zotero <session-id> --collection "EurekaLab Results"

# Sync: pull new items from Zotero collection since last sync
eurekalab sync-zotero <session-id> <collection-id>
```

---

## 9. Implementation Phases (Revised)

### Phase 0: Version Store (Foundation)
**Must come first — everything else depends on it.**
- `VersionStore`: create, checkout, diff, log, branch
- `BusSnapshot`: serialize/deserialize full bus state
- Auto-commit after every stage completion
- `eurekalab history`, `eurekalab diff`, `eurekalab checkout`
- Integrate with existing `persist_incremental()` — versions replace raw stage progress tracking
- **Scope:** ~500 lines

### Phase 1: Content Tier Tracking + "Request Paper" Flow
- Add `content_tier` to Paper model
- `ContentGapAnalyzer`: after survey, identify papers with degraded content
- Interactive prompt: present gap report, let user choose action
- Accept PDF path from user, extract text, upgrade content tier
- **Scope:** ~400 lines

### Phase 2: Bibliography Injection (.bib + Local PDFs)
- `BibLoader`: parse `.bib` → `Bibliography` (bibtexparser already a dependency)
- Local PDF matching by filename, arXiv ID, or DOI
- `from-bib` CLI command
- Survey runs in "gap-fill" mode when bibliography is pre-populated
- **Scope:** ~350 lines

### Phase 3: Zotero Read Integration
- `ZoteroAdapter` using pyzotero
- Import collection → Bibliography with full text from local PDFs
- Import user notes and annotations as paper context
- `from-zotero` CLI command
- **Scope:** ~500 lines + pyzotero dependency

### Phase 4: Draft Paper Analysis
- `DraftAnalyzer`: text extraction + LLM-based structural analysis
- Reference resolution (against Zotero library or search APIs)
- `from-draft` CLI command
- Draft context flows into all pipeline stages
- **Scope:** ~450 lines

### Phase 5: Non-Linear Pipeline + Continuous Ideation
**The architectural shift — re-entrant stages.**
- `IdeationPool`: evolving direction management
- Stage re-entry protocol with delta prompts
- `inject` CLI command (paper, idea, draft)
- Theory-to-ideation feedback loop
- User-triggered backtrack with version safety
- **Scope:** ~800 lines (largest phase — touches orchestrator core)

### Phase 6: Zotero Write-Back
- Push discovered papers to Zotero collection
- Push proof notes as child notes on relevant papers
- Push final paper as Zotero item with PDF
- Session tagging (`eurekalab:session:<id>`)
- `push-to-zotero`, `sync-zotero` CLI commands
- **Scope:** ~350 lines

---

## 10. Open Questions

1. **Version storage format:** Full state per version (simple, ~200KB each) vs. delta-based (compact, complex)? Recommendation: full state — disk is cheap, simplicity is valuable.

2. **Zotero polling vs. manual signal:** When user says "I'll add it to Zotero now", do we poll Zotero for the new item, or does the user press Enter when done? Recommendation: user presses Enter, then we fetch.

3. **Ideation re-entry threshold:** What level of change triggers automatic re-ideation vs. just logging? Recommendation: always log, only trigger on user request or key-lemma failure.

4. **Branch support in Phase 0 or defer?** Branching is powerful but adds complexity to checkout/resume. Recommendation: implement linear history in Phase 0, add branching in Phase 5 when non-linear pipeline lands.

5. **Zotero group libraries:** Support shared research groups from the start, or user-only first? Recommendation: user-only first, group support is a config flag away with pyzotero.
