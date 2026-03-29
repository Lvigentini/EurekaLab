# EurekaLab

Multi-agent system for theoretical research — proof-heavy, formalism-rich, math-dense domains.

## Quick Reference

- **Version:** 0.6.3
- **Python:** 3.11+
- **Entry:** `eurekalab/cli.py` (Click CLI), `eurekalab/main.py` (EurekaSession)
- **Tests:** `pytest tests/ -v` (331 tests, ~6s)
- **Database:** `~/.eurekalab/eurekalab.db` (SQLite — session metadata + version history)
- **Package:** `pip install -e "."` (or `pip install -e ".[all]"` for all extras — includes zotero, pdf)

## Architecture

### Pipeline
```
survey → ideation → direction_gate → theory → theory_review_gate → experiment → writer
```

Pipeline is defined in `eurekalab/orchestrator/pipelines/default_pipeline.yaml` and executed by `MetaOrchestrator` in `eurekalab/orchestrator/meta_orchestrator.py`.

### Key Components
| Component | Path | Purpose |
|-----------|------|---------|
| KnowledgeBus | `eurekalab/knowledge_bus/bus.py` | Central artifact store, reactive subscriptions |
| MetaOrchestrator | `eurekalab/orchestrator/meta_orchestrator.py` | Pipeline execution, gates, feedback |
| VersionStore | `eurekalab/versioning/store.py` | Git-like session versioning (SQLite backend) |
| SessionDB | `eurekalab/storage/db.py` | SQLite for session metadata + versions |
| IdeationPool | `eurekalab/orchestrator/ideation_pool.py` | Continuous ideation, injected ideas |
| GateController | `eurekalab/orchestrator/gate.py` | Human/auto gates, content status |
| Config | `eurekalab/config.py` | Pydantic Settings, all env vars |
| AnalystAgent | `eurekalab/agents/analyst/agent.py` | Flexible agent for non-proof core work |
| ReviewerAgent | `eurekalab/agents/reviewer/agent.py` | Pluggable persona-driven paper review |

### Data Models
All in `eurekalab/types/artifacts.py` and `eurekalab/types/tasks.py`:
- `Paper` — with content_tier, full_text, local_pdf_path, zotero_item_key
- `Bibliography` — papers + citation_graph
- `ResearchBrief` — session state: directions, selected_direction, draft info
- `TheoryState` — proven_lemmas (dict[str, ProofRecord]), lemma_dag, open_goals
- `InputSpec` — mode (detailed/reference/exploration), draft_path, draft_instruction
- `ResearchOutput` — final artifacts (latex_paper, bibliography_json, etc.)

### Entry Points (CLI)
| Command | What |
|---------|------|
| `prove` | Prove a specific conjecture |
| `explore` | Open exploration of a domain |
| `from-papers` | Start from arXiv IDs |
| `from-bib` | Start from .bib file + local PDFs |
| `from-draft` | Start from a draft paper |
| `from-zotero` | Start from a Zotero collection |
| `inject paper/idea/draft` | Mid-session injection |
| `history/diff/checkout` | Version management |
| `sessions` | List all sessions (from SQLite) |
| `clean` | Remove old sessions |
| `housekeep` | Global maintenance (push papers to Zotero) |
| `push-to-zotero` | Sync session results back to Zotero |
| `library-auth` | Institutional library access |
| `review` | Review a paper with AI reviewer persona |
| `reviewer list/install` | Manage reviewer personas |

## Paper Types

`--paper-type/-t` option on all entry commands selects the output type:

| Type | Pipeline | Default For |
|------|----------|-------------|
| `proof` | survey → ideation → theory → experiment → writer | `prove` |
| `survey` | survey → ideation → analyst → writer | `explore`, `from-bib`, `from-zotero` |
| `review` | survey → ideation → analyst → writer | — |
| `experimental` | survey → ideation → analyst → experiment → writer | — |
| `discussion` | survey → ideation → analyst → writer | — |

## Conventions

- All agents extend `BaseAgent` in `eurekalab/agents/base.py`
- LLM calls go through `eurekalab/llm/base.py` (normalized response types)
- Config uses Pydantic Settings with `alias=ENV_VAR_NAME` pattern
- Tests use `tmp_path` fixtures, mock external APIs, no network calls in unit tests
- Commits follow conventional commits: `feat:`, `fix:`, `chore:`, `docs:`
- Version in both `pyproject.toml` and `eurekalab/__init__.py` — keep in sync

## Important Patterns

- **Circular imports:** `versioning/snapshot.py` ↔ `knowledge_bus/bus.py` — use lazy imports (inside methods, not at module level)
- **proven_lemmas** is `dict[str, ProofRecord]`, NOT a list
- **Content tiers:** Paper.content_tier is one of: full_text, abstract, metadata, missing
- **PDF extraction:** pdfplumber (default) or docling; controlled by `PAPER_READER_PDF_BACKEND`
- **OAuth auth:** ccproxy handles Claude Pro/Max OAuth tokens; configured via `ANTHROPIC_AUTH_MODE=oauth`
- **Version commits:** auto-triggered by `bus.persist_incremental()` — every stage completion creates a version
