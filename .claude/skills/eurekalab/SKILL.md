---
name: eurekalab
description: EurekaLab project context — architecture, pipeline, CLI commands, data models, and development patterns. Use when working on any EurekaLab code.
user-invocable: true
---

# EurekaLab Development Context

## What This Is
EurekaLab is a multi-agent AI research system that goes from a question to a publishable result. It crawls literature, generates hypotheses, proves theorems, runs experiments, and writes LaTeX papers.

## Pipeline (7 stages)
```
survey → ideation → direction_gate → theory → theory_review_gate → experiment → writer
```

The pipeline is **non-linear** — stages can be re-entered via the `inject` commands, and every state change is versioned (git-like history with checkout/diff/rollback).

## Core Architecture

### Central Hub: KnowledgeBus (`eurekalab/knowledge_bus/bus.py`)
All artifacts flow through the bus. Key types stored:
- `research_brief` → ResearchBrief (directions, selected_direction, domain, query)
- `bibliography` → Bibliography (papers with content_tier, citation_graph)
- `theory_state` → TheoryState (proven_lemmas as dict[str, ProofRecord], lemma_dag)
- `ideation_pool` → IdeationPool (continuous ideation, injected ideas, emerged insights)
- `pipeline` → TaskPipeline

### Version Store (`eurekalab/versioning/`)
Every `persist_incremental()` auto-commits a version. Users can:
- `eurekalab history <session>` — view timeline
- `eurekalab diff <session> v1 v2` — compare versions
- `eurekalab checkout <session> v3` — rollback (preserves HEAD as new version)

### Paper Model (`eurekalab/types/artifacts.py`)
```python
class Paper(BaseModel):
    paper_id: str
    title: str
    authors: list[str]
    year: int | None = None
    abstract: str = ""
    content_tier: Literal["full_text", "abstract", "metadata", "missing"] = "metadata"
    local_pdf_path: str | None = None
    full_text: str | None = None
    user_notes: str = ""
    source: str = "search"  # search, zotero, user_provided, bib_import, draft
    zotero_item_key: str | None = None
    # ... plus venue, arxiv_id, citation_count, relevance_score, url
```

### IdeationPool (`eurekalab/orchestrator/ideation_pool.py`)
Continuous ideation — not a one-shot stage. Collects:
- `directions` — scored research directions
- `injected_ideas` — user-provided ideas (via `inject idea`)
- `emerged_insights` — feedback from theory failures
- Ideas are injected into theory prompts before each run

## CLI Commands (20+)

### Research Entry Points
```bash
eurekalab prove "conjecture" --domain "ML theory"
eurekalab explore "domain topic"
eurekalab from-papers 2401.12345 --domain "ML theory"
eurekalab from-bib refs.bib --pdfs ./papers/ --domain "ML theory"
eurekalab from-draft paper.tex "Strengthen the theory" --domain "ML theory"
eurekalab from-zotero COLLECTION_ID --domain "ML theory"
```

### Mid-Session Injection (pause first with Ctrl+C)
```bash
eurekalab inject paper SESSION_ID 2401.12345
eurekalab inject idea SESSION_ID "What if we use spectral methods?"
eurekalab inject draft SESSION_ID paper.tex "Consider these results"
```

### Version Management
```bash
eurekalab history SESSION_ID
eurekalab diff SESSION_ID 1 3
eurekalab checkout SESSION_ID 2
eurekalab resume SESSION_ID
```

### Zotero Integration
```bash
# Requires: ZOTERO_API_KEY + ZOTERO_LIBRARY_ID env vars
eurekalab from-zotero COLLECTION_ID --domain "ML theory"
eurekalab push-to-zotero SESSION_ID --collection "Results"
```

## Key Directories
```
eurekalab/
  agents/           # BaseAgent subclasses (survey, ideation, theory, experiment, writer)
  analyzers/        # BibLoader, DraftAnalyzer, ContentGapAnalyzer
  integrations/     # Zotero adapter (pyzotero)
  knowledge_bus/    # Central artifact bus
  llm/              # LLM client abstraction (anthropic, openai-compat)
  orchestrator/     # MetaOrchestrator, pipeline, gates, ideation pool
  tools/            # arXiv, Semantic Scholar, citation manager, etc.
  types/            # Pydantic models (artifacts.py, tasks.py)
  versioning/       # BusSnapshot, VersionStore, diff
  config.py         # Pydantic Settings (all env vars)
  cli.py            # Click CLI (all commands)
  main.py           # EurekaSession, save_artifacts
```

## Development Patterns

### Testing
```bash
pytest tests/ -v           # full suite (177 tests, ~6s)
pytest tests/unit/ -v      # unit only (no API calls)
pytest tests/test_X.py -v  # specific file
```

### Circular Import Prevention
`versioning/snapshot.py` ↔ `knowledge_bus/bus.py` — always use lazy imports:
```python
# In bus.py — NEVER top-level import of versioning
def persist_incremental(self, ...):
    from eurekalab.versioning.store import VersionStore  # lazy
```

### Adding a New CLI Command
1. Add Click decorator + function in `cli.py`
2. Follow existing patterns (read settings, validate, call `_run_session` or bus directly)
3. For new entry points: use `_preloaded_papers` param on `_run_session`

### Config Pattern
```python
# In config.py
my_setting: str = Field(default="value", alias="MY_SETTING")
# User sets via: MY_SETTING=value in .env or environment
```

## Optional Dependencies
```
pip install -e ".[pdf]"         # pdfplumber for PDF extraction
pip install -e ".[pdf-docling]" # docling (ML-powered, heavier)
pip install -e ".[zotero]"      # pyzotero for Zotero integration
pip install -e ".[oauth]"       # ccproxy for Claude Pro/Max OAuth
pip install -e ".[all]"         # everything
```
