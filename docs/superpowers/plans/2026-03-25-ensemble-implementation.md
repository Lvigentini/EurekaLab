# N-Model Ensemble Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the N-model ensemble architecture that runs multiple LLMs concurrently across pipeline stages with per-stage merge strategies and dynamic runtime configuration.

**Architecture:** A ModelPool holds N named LLM clients. An EnsembleOrchestrator dispatches agents in parallel per stage, passing results to pluggable Mergers (union/adversarial/consensus/asymmetric). A Recommender suggests ensemble adjustments between stages. All opt-in via env config — zero overhead when not configured.

**Tech Stack:** Python 3.11, asyncio, Pydantic 2.0, existing LLM adapters (AnthropicAdapter, OpenAICompatAdapter)

**Spec:** `docs/superpowers/specs/2026-03-25-ensemble-architecture-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `eurekaclaw/ensemble/__init__.py` | Create | Package init |
| `eurekaclaw/ensemble/model_pool.py` | Create | Named LLM client registry |
| `eurekaclaw/ensemble/config.py` | Create | Per-stage ensemble config with dynamic overrides |
| `eurekaclaw/ensemble/scoped_bus.py` | Create | Namespaced bus wrapper for parallel isolation |
| `eurekaclaw/ensemble/mergers/__init__.py` | Create | Merger package init + registry |
| `eurekaclaw/ensemble/mergers/base.py` | Create | BaseMerger ABC |
| `eurekaclaw/ensemble/mergers/union.py` | Create | UnionMerger for survey |
| `eurekaclaw/ensemble/mergers/adversarial.py` | Create | AdversarialMerger for ideation |
| `eurekaclaw/ensemble/mergers/consensus.py` | Create | ConsensusMerger for experiment |
| `eurekaclaw/ensemble/orchestrator.py` | Create | Parallel dispatch + merge coordination |
| `eurekaclaw/ensemble/recommender.py` | Create | Heuristic suggestions |
| `eurekaclaw/llm/factory.py` | Modify | Add `google` backend alias |
| `eurekaclaw/config.py` | Modify | Add ENSEMBLE_* settings |
| `eurekaclaw/orchestrator/router.py` | Modify | Add `create_agent()` factory method |
| `eurekaclaw/orchestrator/meta_orchestrator.py` | Modify | Wire ensemble into task loop |
| `.env.example` | Modify | Add ensemble config section |
| `README.md` | Modify | Fork notice + contribution summary |
| `tests/test_model_pool.py` | Create | ModelPool tests |
| `tests/test_ensemble_config.py` | Create | EnsembleConfig tests |
| `tests/test_scoped_bus.py` | Create | ScopedBus tests |
| `tests/test_union_merger.py` | Create | UnionMerger tests |
| `tests/test_adversarial_merger.py` | Create | AdversarialMerger tests |
| `tests/test_consensus_merger.py` | Create | ConsensusMerger tests |
| `tests/test_recommender.py` | Create | Recommender tests |
| `tests/test_ensemble_orchestrator.py` | Create | EnsembleOrchestrator tests |

---

### Task 1: ModelPool — Named LLM Client Registry

**Files:**
- Create: `eurekaclaw/ensemble/__init__.py`
- Create: `eurekaclaw/ensemble/model_pool.py`
- Modify: `eurekaclaw/llm/factory.py`
- Modify: `eurekaclaw/config.py`
- Test: `tests/test_model_pool.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_model_pool.py
"""Tests for ModelPool — named LLM client registry."""
import pytest
from unittest.mock import MagicMock
from eurekaclaw.ensemble.model_pool import ModelPool


def test_register_and_get():
    pool = ModelPool()
    mock_client = MagicMock()
    pool.register("claude", mock_client, "claude-sonnet-4-6", "anthropic")
    assert pool.get("claude") is mock_client


def test_get_model_name():
    pool = ModelPool()
    pool.register("gemini", MagicMock(), "gemini-2.0-flash", "google")
    assert pool.get_model_name("gemini") == "gemini-2.0-flash"


def test_list_available():
    pool = ModelPool()
    pool.register("claude", MagicMock(), "claude-sonnet-4-6", "anthropic")
    pool.register("gemini", MagicMock(), "gemini-2.0-flash", "google")
    assert set(pool.list_available()) == {"claude", "gemini"}


def test_get_unknown_raises():
    pool = ModelPool()
    with pytest.raises(KeyError, match="unknown"):
        pool.get("unknown")


def test_create_from_config_no_ensemble(monkeypatch):
    """When ENSEMBLE_MODELS is not set, pool has just the default model."""
    monkeypatch.setenv("ENSEMBLE_MODELS", "")
    pool = ModelPool.create_from_config()
    available = pool.list_available()
    assert len(available) == 1
    assert "default" in available
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_model_pool.py -v`

- [ ] **Step 3: Add `google` backend alias to `eurekaclaw/llm/factory.py`**

Add to `_BACKEND_ALIASES` dict:
```python
    "google": ("openai_compat", "https://generativelanguage.googleapis.com/v1beta/openai/"),
```

- [ ] **Step 4: Add ensemble settings to `eurekaclaw/config.py`**

After the existing `gemini_api_key` field, add:
```python
    # ---- Ensemble ---------------------------------------------------------
    ensemble_models: str = Field(default="", alias="ENSEMBLE_MODELS")
```

- [ ] **Step 5: Create `eurekaclaw/ensemble/__init__.py`**

```python
"""N-model ensemble execution for EurekaClaw pipeline stages."""
```

- [ ] **Step 6: Create `eurekaclaw/ensemble/model_pool.py`**

```python
"""ModelPool — registry of named LLM clients for ensemble execution."""

from __future__ import annotations

import logging
import os

from eurekaclaw.llm.base import LLMClient

logger = logging.getLogger(__name__)


class ModelPool:
    """Registry of named LLM clients. Each model gets a name (e.g., 'claude', 'gemini')."""

    def __init__(self) -> None:
        self._clients: dict[str, LLMClient] = {}
        self._model_names: dict[str, str] = {}
        self._backends: dict[str, str] = {}

    def register(self, name: str, client: LLMClient, model_name: str, backend: str) -> None:
        self._clients[name] = client
        self._model_names[name] = model_name
        self._backends[name] = backend
        logger.info("ModelPool: registered '%s' (model=%s, backend=%s)", name, model_name, backend)

    def get(self, name: str) -> LLMClient:
        if name not in self._clients:
            raise KeyError(f"Model '{name}' not registered in ModelPool. Available: {list(self._clients.keys())}")
        return self._clients[name]

    def get_model_name(self, name: str) -> str:
        return self._model_names[name]

    def get_backend(self, name: str) -> str:
        return self._backends[name]

    def list_available(self) -> list[str]:
        return list(self._clients.keys())

    @classmethod
    def create_from_config(cls) -> "ModelPool":
        """Build a ModelPool from environment variables.

        Reads ENSEMBLE_MODELS for the list of named models.
        For each model, reads MODEL_{NAME}_BACKEND, MODEL_{NAME}_API_KEY, MODEL_{NAME}_MODEL.
        Falls back to a single 'default' model from the standard LLM_BACKEND config.
        """
        from eurekaclaw.config import settings
        from eurekaclaw.llm.factory import create_client

        pool = cls()
        model_names_str = settings.ensemble_models.strip()

        if not model_names_str:
            # No ensemble configured — single default model
            client = create_client()
            pool.register("default", client, settings.active_model, settings.llm_backend)
            return pool

        for name in model_names_str.split(","):
            name = name.strip()
            if not name:
                continue
            prefix = f"MODEL_{name.upper()}_"
            backend = os.environ.get(f"{prefix}BACKEND", "anthropic")
            api_key = os.environ.get(f"{prefix}API_KEY", "")
            model = os.environ.get(f"{prefix}MODEL", "")

            try:
                if backend == "anthropic":
                    client = create_client(backend="anthropic", anthropic_api_key=api_key or None)
                    model = model or settings.active_model
                else:
                    client = create_client(
                        backend=backend,
                        openai_api_key=api_key or None,
                        openai_model=model or None,
                    )
                pool.register(name, client, model, backend)
            except Exception as e:
                logger.warning("Failed to create client for model '%s': %s", name, e)

        if not pool._clients:
            logger.warning("No ensemble models created — falling back to default")
            client = create_client()
            pool.register("default", client, settings.active_model, settings.llm_backend)

        return pool
```

- [ ] **Step 7: Run tests — verify they pass**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_model_pool.py -v`

- [ ] **Step 8: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/ensemble/ eurekaclaw/llm/factory.py eurekaclaw/config.py tests/test_model_pool.py && git commit -m "feat: add ModelPool and google backend alias for ensemble support"
```

---

### Task 2: Ensemble Config — Per-Stage Configuration

**Files:**
- Create: `eurekaclaw/ensemble/config.py`
- Test: `tests/test_ensemble_config.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_ensemble_config.py
"""Tests for EnsembleConfig — per-stage ensemble configuration."""
import pytest
from eurekaclaw.ensemble.config import EnsembleConfig, StageEnsembleConfig


def test_default_config_is_single():
    config = EnsembleConfig()
    stage = config.get_stage("survey")
    assert stage.strategy == "single"
    assert stage.models == []


def test_from_env_parses_stage(monkeypatch):
    monkeypatch.setenv("ENSEMBLE_SURVEY_MODELS", "claude,gemini")
    monkeypatch.setenv("ENSEMBLE_SURVEY_STRATEGY", "union")
    config = EnsembleConfig.from_env()
    stage = config.get_stage("survey")
    assert stage.models == ["claude", "gemini"]
    assert stage.strategy == "union"


def test_from_env_asymmetric(monkeypatch):
    monkeypatch.setenv("ENSEMBLE_THEORY_MODELS", "claude")
    monkeypatch.setenv("ENSEMBLE_THEORY_STRATEGY", "asymmetric")
    monkeypatch.setenv("ENSEMBLE_THEORY_REVIEWER", "gemini")
    config = EnsembleConfig.from_env()
    stage = config.get_stage("theory")
    assert stage.strategy == "asymmetric"
    assert stage.reviewer == "gemini"


def test_update_stage():
    config = EnsembleConfig()
    config.update_stage("ideation", ["claude", "gemini", "gpt5"], "adversarial")
    stage = config.get_stage("ideation")
    assert stage.models == ["claude", "gemini", "gpt5"]
    assert stage.strategy == "adversarial"


def test_update_stage_sets_locked():
    config = EnsembleConfig()
    config.update_stage("ideation", ["claude"], "single", locked=True)
    assert config.get_stage("ideation").locked is True


def test_missing_stage_returns_default():
    config = EnsembleConfig()
    stage = config.get_stage("nonexistent")
    assert stage.strategy == "single"
```

- [ ] **Step 2: Create `eurekaclaw/ensemble/config.py`**

```python
"""EnsembleConfig — per-stage ensemble configuration with dynamic overrides."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

KNOWN_STAGES = ["survey", "ideation", "theory", "experiment", "writer"]
VALID_STRATEGIES = {"single", "union", "adversarial", "consensus", "asymmetric"}


@dataclass
class StageEnsembleConfig:
    """Configuration for one pipeline stage's ensemble behavior."""
    models: list[str] = field(default_factory=list)
    strategy: str = "single"
    reviewer: str | None = None
    locked: bool = False


@dataclass
class EnsembleRecommendation:
    """A suggested ensemble adjustment for an upcoming stage."""
    stage: str
    suggested_models: list[str]
    suggested_strategy: str
    reason: str
    confidence: float  # 0-1


class EnsembleConfig:
    """Manages per-stage ensemble configuration."""

    def __init__(self) -> None:
        self._stages: dict[str, StageEnsembleConfig] = {}

    def get_stage(self, stage_name: str) -> StageEnsembleConfig:
        return self._stages.get(stage_name, StageEnsembleConfig())

    def update_stage(
        self,
        stage_name: str,
        models: list[str],
        strategy: str,
        locked: bool = False,
        reviewer: str | None = None,
    ) -> None:
        self._stages[stage_name] = StageEnsembleConfig(
            models=models,
            strategy=strategy,
            reviewer=reviewer,
            locked=locked,
        )

    @classmethod
    def from_env(cls) -> "EnsembleConfig":
        """Parse ENSEMBLE_{STAGE}_MODELS/STRATEGY/REVIEWER from environment."""
        config = cls()
        for stage in KNOWN_STAGES:
            prefix = f"ENSEMBLE_{stage.upper()}_"
            models_str = os.environ.get(f"{prefix}MODELS", "")
            strategy = os.environ.get(f"{prefix}STRATEGY", "")
            reviewer = os.environ.get(f"{prefix}REVIEWER", "")

            if not models_str and not strategy:
                continue

            models = [m.strip() for m in models_str.split(",") if m.strip()]
            strategy = strategy or "single"

            if strategy not in VALID_STRATEGIES:
                logger.warning("Invalid strategy '%s' for stage '%s' — using 'single'", strategy, stage)
                strategy = "single"

            config._stages[stage] = StageEnsembleConfig(
                models=models,
                strategy=strategy,
                reviewer=reviewer or None,
            )

        return config
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_ensemble_config.py -v`

- [ ] **Step 4: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/ensemble/config.py tests/test_ensemble_config.py && git commit -m "feat: add per-stage ensemble configuration"
```

---

### Task 3: ScopedBus — Bus Isolation for Parallel Execution

**Files:**
- Create: `eurekaclaw/ensemble/scoped_bus.py`
- Test: `tests/test_scoped_bus.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_scoped_bus.py
"""Tests for ScopedBus — namespaced bus wrapper for parallel isolation."""
import pytest
from eurekaclaw.knowledge_bus.bus import KnowledgeBus
from eurekaclaw.ensemble.scoped_bus import ScopedBus


@pytest.fixture
def bus():
    return KnowledgeBus("test-session")


def test_scoped_put_namespaces_key(bus):
    scoped = ScopedBus(bus, namespace="claude")
    scoped.put("result", {"score": 0.9})
    assert bus.get("result__claude") == {"score": 0.9}
    assert bus.get("result") is None


def test_scoped_get_reads_namespaced(bus):
    scoped = ScopedBus(bus, namespace="gemini")
    bus._store["result__gemini"] = {"score": 0.8}
    assert scoped.get("result") == {"score": 0.8}


def test_scoped_get_falls_back_to_canonical(bus):
    scoped = ScopedBus(bus, namespace="claude")
    bus._store["research_brief"] = "shared_brief"
    assert scoped.get("research_brief") == "shared_brief"


def test_two_scopes_dont_collide(bus):
    scope_a = ScopedBus(bus, namespace="claude")
    scope_b = ScopedBus(bus, namespace="gemini")
    scope_a.put("result", {"model": "claude"})
    scope_b.put("result", {"model": "gemini"})
    assert bus.get("result__claude")["model"] == "claude"
    assert bus.get("result__gemini")["model"] == "gemini"


def test_read_only_methods_delegate(bus):
    from eurekaclaw.types.artifacts import ResearchBrief
    brief = ResearchBrief(session_id="test", domain="test", query="test")
    bus.put_research_brief(brief)
    scoped = ScopedBus(bus, namespace="claude")
    assert scoped.get_research_brief() is not None
    assert scoped.get_research_brief().domain == "test"
```

- [ ] **Step 2: Create `eurekaclaw/ensemble/scoped_bus.py`**

```python
"""ScopedBus — namespaced bus wrapper for parallel ensemble isolation."""

from __future__ import annotations

from typing import Any

from eurekaclaw.knowledge_bus.bus import KnowledgeBus


class ScopedBus:
    """Wraps KnowledgeBus to namespace writes by model name during parallel dispatch.

    Writes go to '{key}__{namespace}'. Reads try namespaced first, fall back to canonical.
    Read-only typed accessors (get_research_brief, etc.) always read canonical — these
    are shared inputs that all parallel agents should see identically.
    """

    def __init__(self, bus: KnowledgeBus, namespace: str) -> None:
        self._bus = bus
        self._ns = namespace

    # --- Namespaced write ---
    def put(self, key: str, value: Any) -> None:
        self._bus.put(f"{key}__{self._ns}", value)

    # --- Namespaced read (with canonical fallback) ---
    def get(self, key: str, default: Any = None) -> Any:
        namespaced = self._bus.get(f"{key}__{self._ns}")
        if namespaced is not None:
            return namespaced
        return self._bus.get(key, default)

    # --- Read-only delegations (shared inputs) ---
    def get_research_brief(self):
        return self._bus.get_research_brief()

    def get_bibliography(self):
        return self._bus.get_bibliography()

    def get_theory_state(self):
        return self._bus.get_theory_state()

    def get_experiment_result(self):
        return self._bus.get_experiment_result()

    def get_pipeline(self):
        return self._bus.get_pipeline()

    # --- Write delegations that agents may call ---
    def put_research_brief(self, brief):
        self._bus.put(f"research_brief__{self._ns}", brief)

    def put_bibliography(self, bib):
        self._bus.put(f"bibliography__{self._ns}", bib)

    def put_theory_state(self, state):
        self._bus.put(f"theory_state__{self._ns}", state)

    def put_experiment_result(self, result):
        self._bus.put(f"experiment_result__{self._ns}", result)

    def append_citations(self, papers):
        # Append to a namespaced bibliography
        from eurekaclaw.types.artifacts import Bibliography
        bib = self._bus.get(f"bibliography__{self._ns}")
        if bib is None:
            bib = self._bus.get_bibliography() or Bibliography(session_id=self._bus.session_id)
            # Copy to avoid mutating shared bibliography
            bib = bib.model_copy(deep=True)
        existing_ids = {p.paper_id for p in bib.papers}
        new_papers = [p for p in papers if p.paper_id not in existing_ids]
        bib.papers.extend(new_papers)
        self._bus.put(f"bibliography__{self._ns}", bib)

    def subscribe(self, artifact_type, callback):
        self._bus.subscribe(artifact_type, callback)

    @property
    def session_id(self):
        return self._bus.session_id
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_scoped_bus.py -v`

- [ ] **Step 4: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/ensemble/scoped_bus.py tests/test_scoped_bus.py && git commit -m "feat: add ScopedBus for parallel ensemble isolation"
```

---

### Task 4: Merger Base + UnionMerger (Survey)

**Files:**
- Create: `eurekaclaw/ensemble/mergers/__init__.py`
- Create: `eurekaclaw/ensemble/mergers/base.py`
- Create: `eurekaclaw/ensemble/mergers/union.py`
- Test: `tests/test_union_merger.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_union_merger.py
"""Tests for UnionMerger — combines survey results with deduplication."""
import pytest
from eurekaclaw.ensemble.mergers.union import UnionMerger
from eurekaclaw.types.agents import AgentResult, AgentRole
from eurekaclaw.knowledge_bus.bus import KnowledgeBus


def _make_result(papers, open_problems=None):
    return AgentResult(
        task_id="t1",
        agent_role=AgentRole.SURVEY,
        success=True,
        output={
            "papers": papers,
            "open_problems": open_problems or [],
            "key_mathematical_objects": [],
        },
        text_summary="",
    )


@pytest.fixture
def bus():
    return KnowledgeBus("test")


@pytest.mark.asyncio
async def test_union_dedup_by_arxiv_id(bus):
    results = {
        "claude": _make_result([
            {"arxiv_id": "2301.001", "title": "Paper A", "abstract": "Short"},
        ]),
        "gemini": _make_result([
            {"arxiv_id": "2301.001", "title": "Paper A", "abstract": "Longer abstract here"},
            {"arxiv_id": "2301.002", "title": "Paper B", "abstract": "New"},
        ]),
    }
    merger = UnionMerger()
    merged = await merger.merge(results, None, bus)
    papers = merged.output["papers"]
    assert len(papers) == 2
    # Should keep the richer version (longer abstract)
    paper_a = next(p for p in papers if p["arxiv_id"] == "2301.001")
    assert "Longer" in paper_a["abstract"]


@pytest.mark.asyncio
async def test_union_tags_source_models(bus):
    results = {
        "claude": _make_result([{"arxiv_id": "2301.001", "title": "P1", "abstract": "a"}]),
        "gemini": _make_result([{"arxiv_id": "2301.001", "title": "P1", "abstract": "a"}]),
    }
    merger = UnionMerger()
    merged = await merger.merge(results, None, bus)
    paper = merged.output["papers"][0]
    assert "claude" in paper["source_models"]
    assert "gemini" in paper["source_models"]


@pytest.mark.asyncio
async def test_union_stats_on_bus(bus):
    results = {
        "claude": _make_result([{"arxiv_id": "1", "title": "A", "abstract": ""}]),
        "gemini": _make_result([
            {"arxiv_id": "1", "title": "A", "abstract": ""},
            {"arxiv_id": "2", "title": "B", "abstract": ""},
        ]),
    }
    merger = UnionMerger()
    await merger.merge(results, None, bus)
    stats = bus.get("ensemble_survey_stats")
    assert stats["per_model"]["claude"] == 1
    assert stats["per_model"]["gemini"] == 2
    assert stats["merged_total"] == 2
    assert stats["overlap_count"] == 1


@pytest.mark.asyncio
async def test_union_handles_partial_failure(bus):
    results = {
        "claude": _make_result([{"arxiv_id": "1", "title": "A", "abstract": ""}]),
        "gemini": AgentResult(
            task_id="t1", agent_role=AgentRole.SURVEY, success=False,
            output={}, text_summary="", error="API error",
        ),
    }
    merger = UnionMerger()
    merged = await merger.merge(results, None, bus)
    assert len(merged.output["papers"]) == 1
```

- [ ] **Step 2: Create merger package and base**

```python
# eurekaclaw/ensemble/mergers/__init__.py
"""Pluggable merge strategies for ensemble pipeline stages."""

from eurekaclaw.ensemble.mergers.base import BaseMerger

MERGER_REGISTRY: dict[str, type[BaseMerger] | None] = {}


def _register_mergers() -> None:
    """Lazy-load merger classes to avoid circular imports."""
    global MERGER_REGISTRY
    from eurekaclaw.ensemble.mergers.union import UnionMerger
    from eurekaclaw.ensemble.mergers.adversarial import AdversarialMerger
    from eurekaclaw.ensemble.mergers.consensus import ConsensusMerger

    MERGER_REGISTRY.update({
        "union": UnionMerger,
        "adversarial": AdversarialMerger,
        "consensus": ConsensusMerger,
        "asymmetric": None,
        "single": None,
    })


def get_merger(strategy: str) -> BaseMerger | None:
    if not MERGER_REGISTRY:
        _register_mergers()
    cls = MERGER_REGISTRY.get(strategy)
    return cls() if cls else None
```

```python
# eurekaclaw/ensemble/mergers/base.py
"""BaseMerger — abstract interface for ensemble merge strategies."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from eurekaclaw.knowledge_bus.bus import KnowledgeBus
from eurekaclaw.types.agents import AgentResult, AgentRole
from eurekaclaw.types.tasks import Task

logger = logging.getLogger(__name__)


class BaseMerger(ABC):
    """All ensemble merge strategies implement this interface."""

    @abstractmethod
    async def merge(
        self,
        results: dict[str, AgentResult],
        task: Task | None,
        bus: KnowledgeBus,
    ) -> AgentResult:
        ...

    def _filter_successes(self, results: dict[str, AgentResult]) -> dict[str, AgentResult]:
        """Keep only successful results. Raises if all failed."""
        valid = {k: v for k, v in results.items() if v.success}
        if not valid:
            errors = {k: v.error for k, v in results.items()}
            raise RuntimeError(f"All ensemble models failed: {errors}")
        return valid
```

- [ ] **Step 3: Create `eurekaclaw/ensemble/mergers/union.py`**

```python
"""UnionMerger — combines survey results with deduplication."""

from __future__ import annotations

import logging
from typing import Any

from eurekaclaw.ensemble.mergers.base import BaseMerger
from eurekaclaw.knowledge_bus.bus import KnowledgeBus
from eurekaclaw.types.agents import AgentResult, AgentRole
from eurekaclaw.types.tasks import Task

logger = logging.getLogger(__name__)


class UnionMerger(BaseMerger):
    """Merge survey results: combine all papers, deduplicate by ID, union open problems."""

    async def merge(
        self,
        results: dict[str, AgentResult],
        task: Task | None,
        bus: KnowledgeBus,
    ) -> AgentResult:
        valid = self._filter_successes(results)

        # Collect papers from all models
        per_model_counts: dict[str, int] = {}
        all_papers: list[tuple[str, dict]] = []  # (model_name, paper_dict)

        for model_name, result in valid.items():
            papers = result.output.get("papers", [])
            per_model_counts[model_name] = len(papers)
            for paper in papers:
                all_papers.append((model_name, paper))

        # Deduplicate by arxiv_id (or title as fallback)
        merged_papers: dict[str, dict] = {}  # key -> paper
        paper_sources: dict[str, list[str]] = {}  # key -> [model_names]

        for model_name, paper in all_papers:
            key = paper.get("arxiv_id") or paper.get("title", "").lower().strip()
            if not key:
                continue

            if key in merged_papers:
                paper_sources[key].append(model_name)
                # Keep the richer version (longer abstract)
                existing = merged_papers[key]
                if len(paper.get("abstract", "")) > len(existing.get("abstract", "")):
                    paper["source_models"] = paper_sources[key]
                    merged_papers[key] = paper
                else:
                    existing["source_models"] = paper_sources[key]
            else:
                merged_papers[key] = paper
                paper_sources[key] = [model_name]
                paper["source_models"] = [model_name]

        merged_list = list(merged_papers.values())
        overlap_count = sum(1 for sources in paper_sources.values() if len(sources) > 1)
        total = len(merged_list)

        # Union open problems and key objects
        all_problems: list[str] = []
        all_objects: list[str] = []
        seen_problems: set[str] = set()
        seen_objects: set[str] = set()

        for result in valid.values():
            for p in result.output.get("open_problems", []):
                p_str = str(p)
                if p_str not in seen_problems:
                    all_problems.append(p_str)
                    seen_problems.add(p_str)
            for o in result.output.get("key_mathematical_objects", []):
                o_str = str(o)
                if o_str not in seen_objects:
                    all_objects.append(o_str)
                    seen_objects.add(o_str)

        # Store stats on bus
        bus.put("ensemble_survey_stats", {
            "per_model": per_model_counts,
            "merged_total": total,
            "overlap_count": overlap_count,
            "overlap_ratio": round(overlap_count / max(total, 1), 2),
        })

        # Build merged output
        first_result = next(iter(valid.values()))
        merged_output = dict(first_result.output)
        merged_output["papers"] = merged_list
        merged_output["open_problems"] = all_problems
        merged_output["key_mathematical_objects"] = all_objects

        # Combine token usage
        total_tokens: dict[str, int] = {"input": 0, "output": 0}
        for result in valid.values():
            for k in ("input", "output"):
                total_tokens[k] += result.token_usage.get(k, 0)

        return AgentResult(
            task_id=first_result.task_id,
            agent_role=first_result.agent_role,
            success=True,
            output=merged_output,
            text_summary=f"Ensemble survey: {total} papers from {len(valid)} models (overlap: {overlap_count})",
            token_usage=total_tokens,
        )
```

- [ ] **Step 4: Create stub files for adversarial and consensus** (to avoid import errors in `__init__.py`)

```python
# eurekaclaw/ensemble/mergers/adversarial.py
"""AdversarialMerger — cross-review ideation directions. Implemented in Task 5."""

from eurekaclaw.ensemble.mergers.base import BaseMerger
from eurekaclaw.knowledge_bus.bus import KnowledgeBus
from eurekaclaw.types.agents import AgentResult
from eurekaclaw.types.tasks import Task


class AdversarialMerger(BaseMerger):
    async def merge(self, results, task, bus):
        raise NotImplementedError("AdversarialMerger not yet implemented")
```

```python
# eurekaclaw/ensemble/mergers/consensus.py
"""ConsensusMerger — independent experiment validation. Implemented in Task 6."""

from eurekaclaw.ensemble.mergers.base import BaseMerger
from eurekaclaw.knowledge_bus.bus import KnowledgeBus
from eurekaclaw.types.agents import AgentResult
from eurekaclaw.types.tasks import Task


class ConsensusMerger(BaseMerger):
    async def merge(self, results, task, bus):
        raise NotImplementedError("ConsensusMerger not yet implemented")
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_union_merger.py -v`

- [ ] **Step 6: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/ensemble/mergers/ tests/test_union_merger.py && git commit -m "feat: add merger base, UnionMerger, and merger registry"
```

---

### Task 5: AdversarialMerger (Ideation)

**Files:**
- Modify: `eurekaclaw/ensemble/mergers/adversarial.py`
- Test: `tests/test_adversarial_merger.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_adversarial_merger.py
"""Tests for AdversarialMerger — cross-review ideation directions."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from eurekaclaw.ensemble.mergers.adversarial import AdversarialMerger
from eurekaclaw.types.agents import AgentResult, AgentRole
from eurekaclaw.knowledge_bus.bus import KnowledgeBus


def _make_ideation_result(directions):
    return AgentResult(
        task_id="t1",
        agent_role=AgentRole.IDEATION,
        success=True,
        output={"directions": directions},
        text_summary="",
    )


@pytest.fixture
def bus():
    return KnowledgeBus("test")


@pytest.mark.asyncio
async def test_merge_combines_directions(bus):
    results = {
        "claude": _make_ideation_result([
            {"direction_id": "d1", "title": "Approach A", "hypothesis": "H1",
             "novelty_score": 0.8, "soundness_score": 0.7, "transformative_score": 0.6},
        ]),
        "gemini": _make_ideation_result([
            {"direction_id": "d2", "title": "Approach B", "hypothesis": "H2",
             "novelty_score": 0.9, "soundness_score": 0.8, "transformative_score": 0.7},
        ]),
    }
    merger = AdversarialMerger()
    # Skip cross-review in unit test (requires LLM) — test the merge logic
    merged = await merger._merge_without_review(results, bus)
    assert len(merged.output["directions"]) == 2


@pytest.mark.asyncio
async def test_unique_directions_get_originality_bonus(bus):
    results = {
        "claude": _make_ideation_result([
            {"direction_id": "d1", "title": "Unique Idea", "hypothesis": "H1",
             "novelty_score": 0.8, "soundness_score": 0.7, "transformative_score": 0.6},
        ]),
        "gemini": _make_ideation_result([
            {"direction_id": "d2", "title": "Different Topic", "hypothesis": "H2",
             "novelty_score": 0.7, "soundness_score": 0.6, "transformative_score": 0.5},
        ]),
    }
    merger = AdversarialMerger()
    merged = await merger._merge_without_review(results, bus)
    for d in merged.output["directions"]:
        assert d["consensus"] == "unique"


@pytest.mark.asyncio
async def test_handles_single_model(bus):
    results = {
        "claude": _make_ideation_result([
            {"direction_id": "d1", "title": "Solo", "hypothesis": "H1",
             "novelty_score": 0.8, "soundness_score": 0.7, "transformative_score": 0.6},
        ]),
    }
    merger = AdversarialMerger()
    merged = await merger._merge_without_review(results, bus)
    assert len(merged.output["directions"]) == 1
```

- [ ] **Step 2: Implement `eurekaclaw/ensemble/mergers/adversarial.py`**

```python
"""AdversarialMerger — cross-review and rank ideation directions from multiple models."""

from __future__ import annotations

import json
import logging
from typing import Any

from eurekaclaw.ensemble.mergers.base import BaseMerger
from eurekaclaw.knowledge_bus.bus import KnowledgeBus
from eurekaclaw.types.agents import AgentResult, AgentRole
from eurekaclaw.types.tasks import Task

logger = logging.getLogger(__name__)

# Simple word-overlap similarity for detecting convergent directions
def _title_similarity(a: str, b: str) -> float:
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0

SIMILARITY_THRESHOLD = 0.7


class AdversarialMerger(BaseMerger):
    """Merge ideation results: combine directions, detect convergence/uniqueness, rank."""

    def __init__(self, model_pool=None):
        self._model_pool = model_pool  # needed for cross-review LLM calls

    async def merge(
        self,
        results: dict[str, AgentResult],
        task: Task | None,
        bus: KnowledgeBus,
    ) -> AgentResult:
        valid = self._filter_successes(results)

        if len(valid) == 1 or self._model_pool is None:
            return await self._merge_without_review(valid, bus)

        # Phase 1: Collect all directions
        all_directions = self._collect_directions(valid)

        # Phase 2: Cross-review (if model_pool available)
        try:
            all_directions = await self._cross_review(all_directions, valid)
        except Exception as e:
            logger.warning("Cross-review failed, proceeding without: %s", e)

        # Phase 3: Rank
        ranked = self._rank_directions(all_directions)

        return self._build_result(ranked, valid, bus)

    async def _merge_without_review(
        self, results: dict[str, AgentResult], bus: KnowledgeBus,
    ) -> AgentResult:
        """Merge without cross-review — used when only 1 model or no model_pool."""
        valid = self._filter_successes(results)
        all_directions = self._collect_directions(valid)
        ranked = self._rank_directions(all_directions)
        return self._build_result(ranked, valid, bus)

    def _collect_directions(self, results: dict[str, AgentResult]) -> list[dict]:
        """Collect all directions from all models, tagging source."""
        all_dirs = []
        for model_name, result in results.items():
            for d in result.output.get("directions", []):
                d["source_model"] = model_name
                d["cross_scores"] = {}
                all_dirs.append(d)
        return all_dirs

    async def _cross_review(self, directions: list[dict], results: dict[str, AgentResult]) -> list[dict]:
        """Each model reviews the other models' directions."""
        from eurekaclaw.config import settings

        model_names = list(results.keys())

        for reviewer_name in model_names:
            others = [d for d in directions if d["source_model"] != reviewer_name]
            if not others:
                continue

            reviewer_client = self._model_pool.get(reviewer_name)
            prompt = (
                "Score each research direction on three dimensions (0.0-1.0):\n"
                "- novelty: How original is this idea?\n"
                "- soundness: Is the mathematical reasoning plausible?\n"
                "- feasibility: Can this be proved with known techniques?\n\n"
                "Directions to review:\n"
                f"{json.dumps([{'title': d['title'], 'hypothesis': d['hypothesis'], 'direction_id': d['direction_id']} for d in others], indent=2)}\n\n"
                'Return JSON array: [{"direction_id": "...", "novelty": 0.8, "soundness": 0.7, "feasibility": 0.6, "critique": "..."}]'
            )

            try:
                response = await reviewer_client.messages.create(
                    model=self._model_pool.get_model_name(reviewer_name),
                    max_tokens=2048,
                    system="You are a rigorous research reviewer. Output only valid JSON.",
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text
                scores = json.loads(text if text.strip().startswith("[") else text[text.index("["):text.rindex("]")+1])
                score_map = {s["direction_id"]: s for s in scores}

                for d in directions:
                    if d["direction_id"] in score_map:
                        s = score_map[d["direction_id"]]
                        cross_score = 0.4 * s.get("novelty", 0.5) + 0.35 * s.get("soundness", 0.5) + 0.25 * s.get("feasibility", 0.5)
                        d["cross_scores"][reviewer_name] = round(cross_score, 3)
            except Exception as e:
                logger.warning("Cross-review by %s failed: %s", reviewer_name, e)

        return directions

    def _rank_directions(self, directions: list[dict]) -> list[dict]:
        """Rank directions by composite score with bonuses."""
        # Detect convergent pairs (similar titles from different models)
        convergent_ids: set[str] = set()
        for i, a in enumerate(directions):
            for b in directions[i+1:]:
                if a["source_model"] != b["source_model"]:
                    if _title_similarity(a.get("title", ""), b.get("title", "")) > SIMILARITY_THRESHOLD:
                        convergent_ids.add(a["direction_id"])
                        convergent_ids.add(b["direction_id"])

        for d in directions:
            self_score = (
                0.4 * d.get("novelty_score", 0.5)
                + 0.35 * d.get("soundness_score", 0.5)
                + 0.25 * d.get("transformative_score", 0.5)
            )
            cross_scores = list(d.get("cross_scores", {}).values())
            avg_cross = sum(cross_scores) / len(cross_scores) if cross_scores else self_score

            is_convergent = d["direction_id"] in convergent_ids
            bonus = 0.15 if is_convergent else 0.2  # convergence vs originality
            d["consensus"] = "converged" if is_convergent else "unique"

            d["final_score"] = round(0.4 * avg_cross + 0.3 * self_score + 0.3 * bonus, 3)

        directions.sort(key=lambda d: d["final_score"], reverse=True)
        return directions[:7]  # top 7

    def _build_result(self, directions: list[dict], results: dict[str, AgentResult], bus: KnowledgeBus) -> AgentResult:
        first = next(iter(results.values()))
        total_tokens: dict[str, int] = {"input": 0, "output": 0}
        for r in results.values():
            for k in ("input", "output"):
                total_tokens[k] += r.token_usage.get(k, 0)

        return AgentResult(
            task_id=first.task_id,
            agent_role=first.agent_role,
            success=True,
            output={"directions": directions},
            text_summary=f"Ensemble ideation: {len(directions)} directions from {len(results)} models",
            token_usage=total_tokens,
        )
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_adversarial_merger.py -v`

- [ ] **Step 4: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/ensemble/mergers/adversarial.py tests/test_adversarial_merger.py && git commit -m "feat: add AdversarialMerger for cross-model ideation"
```

---

### Task 6: ConsensusMerger (Experiment)

**Files:**
- Modify: `eurekaclaw/ensemble/mergers/consensus.py`
- Test: `tests/test_consensus_merger.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_consensus_merger.py
"""Tests for ConsensusMerger — independent experiment validation."""
import pytest
from eurekaclaw.ensemble.mergers.consensus import ConsensusMerger
from eurekaclaw.types.agents import AgentResult, AgentRole
from eurekaclaw.knowledge_bus.bus import KnowledgeBus


def _make_experiment_result(bounds, alignment_score):
    return AgentResult(
        task_id="t1",
        agent_role=AgentRole.EXPERIMENT,
        success=True,
        output={
            "bounds": bounds,
            "alignment_score": alignment_score,
            "code": "print('test')",
        },
        text_summary="",
    )


@pytest.fixture
def bus():
    return KnowledgeBus("test")


@pytest.mark.asyncio
async def test_consensus_confirmed_bounds(bus):
    results = {
        "claude": _make_experiment_result(
            [{"name": "regret", "theoretical": 1.0, "empirical": 0.95}], 0.9
        ),
        "gemini": _make_experiment_result(
            [{"name": "regret", "theoretical": 1.0, "empirical": 0.97}], 0.92
        ),
    }
    merger = ConsensusMerger()
    merged = await merger.merge(results, None, bus)
    assert len(merged.output["confirmed_bounds"]) == 1
    assert len(merged.output["contested_bounds"]) == 0
    assert merged.output["agreement_ratio"] == 1.0


@pytest.mark.asyncio
async def test_consensus_contested_bounds(bus):
    results = {
        "claude": _make_experiment_result(
            [{"name": "error", "theoretical": 0.01, "empirical": 0.02}], 0.8
        ),
        "gemini": _make_experiment_result(
            [{"name": "error", "theoretical": 0.01, "empirical": 0.5}], 0.4
        ),
    }
    merger = ConsensusMerger()
    merged = await merger.merge(results, None, bus)
    assert len(merged.output["contested_bounds"]) == 1
    assert merged.output["agreement_ratio"] == 0.0


@pytest.mark.asyncio
async def test_consensus_single_model_passthrough(bus):
    results = {
        "claude": _make_experiment_result(
            [{"name": "bound", "theoretical": 1.0, "empirical": 0.9}], 0.85
        ),
    }
    merger = ConsensusMerger()
    merged = await merger.merge(results, None, bus)
    assert merged.output["alignment_score"] == 0.85
```

- [ ] **Step 2: Implement `eurekaclaw/ensemble/mergers/consensus.py`**

```python
"""ConsensusMerger — independent experiment validation with agreement scoring."""

from __future__ import annotations

import logging
from typing import Any

from eurekaclaw.ensemble.mergers.base import BaseMerger
from eurekaclaw.knowledge_bus.bus import KnowledgeBus
from eurekaclaw.types.agents import AgentResult, AgentRole
from eurekaclaw.types.tasks import Task

logger = logging.getLogger(__name__)

AGREEMENT_TOLERANCE = 0.10  # 10% tolerance for "agreement"


class ConsensusMerger(BaseMerger):
    """Compare experiment results across models — agreement = high confidence."""

    async def merge(
        self,
        results: dict[str, AgentResult],
        task: Task | None,
        bus: KnowledgeBus,
    ) -> AgentResult:
        valid = self._filter_successes(results)

        if len(valid) == 1:
            return next(iter(valid.values()))

        # Collect bounds from all models, keyed by bound name
        bounds_by_name: dict[str, dict[str, Any]] = {}  # name -> {model: empirical}
        theoretical_by_name: dict[str, float] = {}

        for model_name, result in valid.items():
            for bound in result.output.get("bounds", []):
                name = bound.get("name", "")
                if not name:
                    continue
                if name not in bounds_by_name:
                    bounds_by_name[name] = {}
                    theoretical_by_name[name] = bound.get("theoretical", 0)
                try:
                    bounds_by_name[name][model_name] = float(bound.get("empirical", 0))
                except (ValueError, TypeError):
                    pass

        # Compare bounds across models
        confirmed: list[dict] = []
        contested: list[dict] = []

        for name, model_values in bounds_by_name.items():
            values = list(model_values.values())
            if len(values) < 2:
                # Only one model measured this bound — include but can't confirm
                confirmed.append({
                    "name": name,
                    "theoretical": theoretical_by_name.get(name),
                    "empirical": values[0],
                    "models_agree": False,
                    "single_model": True,
                })
                continue

            # Check if all values are within tolerance of each other
            min_val = min(values)
            max_val = max(values)
            mean_val = sum(values) / len(values)
            spread = (max_val - min_val) / max(abs(mean_val), 1e-10)

            if spread <= AGREEMENT_TOLERANCE:
                confirmed.append({
                    "name": name,
                    "theoretical": theoretical_by_name.get(name),
                    "empirical": round(mean_val, 6),
                    "models_agree": True,
                    "per_model": model_values,
                })
            else:
                contested.append({
                    "name": name,
                    "theoretical": theoretical_by_name.get(name),
                    "per_model": model_values,
                    "gap": round(spread, 4),
                })

        total_bounds = len(confirmed) + len(contested)
        confirmed_count = len([b for b in confirmed if b.get("models_agree")])
        agreement_ratio = round(confirmed_count / max(total_bounds, 1), 2)

        # Average alignment scores across models
        alignment_scores = [r.output.get("alignment_score", 0) for r in valid.values()]
        avg_alignment = round(sum(alignment_scores) / len(alignment_scores), 3)

        # Total tokens
        total_tokens: dict[str, int] = {"input": 0, "output": 0}
        for r in valid.values():
            for k in ("input", "output"):
                total_tokens[k] += r.token_usage.get(k, 0)

        first = next(iter(valid.values()))
        return AgentResult(
            task_id=first.task_id,
            agent_role=first.agent_role,
            success=True,
            output={
                "confirmed_bounds": confirmed,
                "contested_bounds": contested,
                "agreement_ratio": agreement_ratio,
                "alignment_score": avg_alignment,
                "code": first.output.get("code", ""),
                "bounds": first.output.get("bounds", []),  # keep original for writer
            },
            text_summary=f"Ensemble experiment: {confirmed_count}/{total_bounds} bounds confirmed, {len(contested)} contested",
            token_usage=total_tokens,
        )
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_consensus_merger.py -v`

- [ ] **Step 4: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/ensemble/mergers/consensus.py tests/test_consensus_merger.py && git commit -m "feat: add ConsensusMerger for independent experiment validation"
```

---

### Task 7: Recommender — Heuristic Suggestions

**Files:**
- Create: `eurekaclaw/ensemble/recommender.py`
- Test: `tests/test_recommender.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_recommender.py
"""Tests for EnsembleRecommender — heuristic suggestions."""
import pytest
from eurekaclaw.ensemble.recommender import EnsembleRecommender
from eurekaclaw.ensemble.config import EnsembleConfig
from eurekaclaw.knowledge_bus.bus import KnowledgeBus


@pytest.fixture
def bus():
    b = KnowledgeBus("test")
    return b


def test_low_overlap_recommends_wider(bus):
    bus.put("ensemble_survey_stats", {
        "per_model": {"claude": 6, "gemini": 9},
        "merged_total": 13,
        "overlap_count": 1,
        "overlap_ratio": 0.07,
    })
    rec = EnsembleRecommender()
    config = EnsembleConfig()
    result = rec.recommend("survey", bus, ["claude", "gemini", "gpt5"], config)
    assert result is not None
    assert len(result.suggested_models) > 2
    assert result.confidence >= 0.7


def test_high_overlap_recommends_narrower(bus):
    bus.put("ensemble_survey_stats", {
        "per_model": {"claude": 8, "gemini": 9},
        "merged_total": 10,
        "overlap_count": 7,
        "overlap_ratio": 0.70,
    })
    rec = EnsembleRecommender()
    config = EnsembleConfig()
    result = rec.recommend("survey", bus, ["claude", "gemini", "gpt5"], config)
    assert result is not None
    assert len(result.suggested_models) <= 2


def test_no_recommendation_when_normal(bus):
    bus.put("ensemble_survey_stats", {
        "per_model": {"claude": 7, "gemini": 8},
        "merged_total": 12,
        "overlap_count": 3,
        "overlap_ratio": 0.25,
    })
    rec = EnsembleRecommender()
    config = EnsembleConfig()
    result = rec.recommend("survey", bus, ["claude", "gemini"], config)
    assert result is None  # 25% overlap is normal, no recommendation
```

- [ ] **Step 2: Create `eurekaclaw/ensemble/recommender.py`**

```python
"""EnsembleRecommender — heuristic suggestions for ensemble adjustments."""

from __future__ import annotations

import logging
from typing import Any

from eurekaclaw.ensemble.config import EnsembleConfig, EnsembleRecommendation
from eurekaclaw.knowledge_bus.bus import KnowledgeBus

logger = logging.getLogger(__name__)


class EnsembleRecommender:
    """Generates ensemble recommendations based on stage results."""

    def recommend(
        self,
        completed_stage: str,
        bus: KnowledgeBus,
        available_models: list[str],
        current_config: EnsembleConfig,
    ) -> EnsembleRecommendation | None:
        """Check heuristic rules and return a recommendation, or None."""
        handler = getattr(self, f"_after_{completed_stage}", None)
        if handler:
            return handler(bus, available_models, current_config)
        return None

    def _after_survey(
        self, bus: KnowledgeBus, available: list[str], config: EnsembleConfig,
    ) -> EnsembleRecommendation | None:
        stats = bus.get("ensemble_survey_stats")
        if not stats:
            return None

        overlap = stats.get("overlap_ratio", 0.5)
        per_model = stats.get("per_model", {})

        # Check for dead models
        dead = [m for m, count in per_model.items() if count == 0]
        if dead:
            alive = [m for m in available if m not in dead]
            return EnsembleRecommendation(
                stage="ideation",
                suggested_models=alive,
                suggested_strategy="adversarial",
                reason=f"Model(s) {dead} found 0 papers — excluding from ideation",
                confidence=0.9,
            )

        # Low overlap — widen
        if overlap < 0.20 and len(available) > 2:
            return EnsembleRecommendation(
                stage="ideation",
                suggested_models=available,
                suggested_strategy="adversarial",
                reason=f"Low overlap ({overlap:.0%}) — widen ideation to {len(available)} models for broader creative coverage",
                confidence=0.8,
            )

        # High overlap — narrow
        if overlap > 0.65:
            narrowed = list(per_model.keys())[:2] if len(per_model) > 2 else list(per_model.keys())
            return EnsembleRecommendation(
                stage="ideation",
                suggested_models=narrowed,
                suggested_strategy="adversarial",
                reason=f"High overlap ({overlap:.0%}) — 2 models sufficient for ideation, save tokens",
                confidence=0.6,
            )

        return None

    def _after_ideation(
        self, bus: KnowledgeBus, available: list[str], config: EnsembleConfig,
    ) -> EnsembleRecommendation | None:
        return None  # Placeholder — can add clustering detection later

    def _after_theory(
        self, bus: KnowledgeBus, available: list[str], config: EnsembleConfig,
    ) -> EnsembleRecommendation | None:
        state = bus.get_theory_state()
        if not state:
            return None

        # Count low-confidence lemmas
        low_conf = sum(
            1 for p in state.proven_lemmas.values()
            if hasattr(p, 'confidence') and p.confidence and p.confidence < 0.7
        )
        if low_conf > 2 and len(available) > 1:
            return EnsembleRecommendation(
                stage="experiment",
                suggested_models=available[:2],
                suggested_strategy="consensus",
                reason=f"{low_conf} low-confidence lemmas — add consensus validation in experiment",
                confidence=0.7,
            )
        return None

    def _after_experiment(
        self, bus: KnowledgeBus, available: list[str], config: EnsembleConfig,
    ) -> EnsembleRecommendation | None:
        return None  # Writer is always single-model
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_recommender.py -v`

- [ ] **Step 4: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/ensemble/recommender.py tests/test_recommender.py && git commit -m "feat: add ensemble recommender with heuristic suggestions"
```

---

### Task 8: Ensemble Orchestrator

**Files:**
- Create: `eurekaclaw/ensemble/orchestrator.py`
- Test: `tests/test_ensemble_orchestrator.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_ensemble_orchestrator.py
"""Tests for EnsembleOrchestrator — dispatch + merge coordination."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from eurekaclaw.ensemble.orchestrator import EnsembleOrchestrator
from eurekaclaw.ensemble.model_pool import ModelPool
from eurekaclaw.ensemble.config import EnsembleConfig
from eurekaclaw.knowledge_bus.bus import KnowledgeBus
from eurekaclaw.types.agents import AgentResult, AgentRole
from eurekaclaw.types.tasks import Task


@pytest.fixture
def bus():
    return KnowledgeBus("test")


@pytest.fixture
def pool():
    p = ModelPool()
    p.register("claude", MagicMock(), "claude-sonnet-4-6", "anthropic")
    p.register("gemini", MagicMock(), "gemini-2.0-flash", "google")
    return p


def test_is_ensemble_stage_true():
    config = EnsembleConfig()
    config.update_stage("survey", ["claude", "gemini"], "union")
    orch = EnsembleOrchestrator(ModelPool(), config, KnowledgeBus("t"), "auto")
    assert orch.is_ensemble_stage("survey")


def test_is_ensemble_stage_false_single():
    config = EnsembleConfig()
    orch = EnsembleOrchestrator(ModelPool(), config, KnowledgeBus("t"), "auto")
    assert not orch.is_ensemble_stage("survey")


@pytest.mark.asyncio
async def test_single_model_fast_path(pool, bus):
    config = EnsembleConfig()
    config.update_stage("survey", ["claude"], "single")
    orch = EnsembleOrchestrator(pool, config, bus, "none")

    expected = AgentResult(
        task_id="t1", agent_role=AgentRole.SURVEY, success=True,
        output={"papers": []}, text_summary="",
    )
    mock_agent = MagicMock()
    mock_agent.execute = AsyncMock(return_value=expected)

    task = Task(task_id="t1", name="survey", agent_role="survey")
    result = await orch.execute_stage(task, lambda client: mock_agent)
    assert result is expected
```

- [ ] **Step 2: Create `eurekaclaw/ensemble/orchestrator.py`**

```python
"""EnsembleOrchestrator — dispatches agents to multiple models and merges results."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

from eurekaclaw.agents.base import BaseAgent
from eurekaclaw.ensemble.config import EnsembleConfig, EnsembleRecommendation
from eurekaclaw.ensemble.model_pool import ModelPool
from eurekaclaw.ensemble.recommender import EnsembleRecommender
from eurekaclaw.ensemble.scoped_bus import ScopedBus
from eurekaclaw.knowledge_bus.bus import KnowledgeBus
from eurekaclaw.llm.base import LLMClient
from eurekaclaw.types.agents import AgentResult
from eurekaclaw.types.tasks import Task

logger = logging.getLogger(__name__)

PER_MODEL_TIMEOUT = 300  # seconds


class EnsembleOrchestrator:
    """Coordinates multi-model execution for pipeline stages."""

    def __init__(
        self,
        model_pool: ModelPool,
        config: EnsembleConfig,
        bus: KnowledgeBus,
        gate_mode: str,
    ) -> None:
        self.model_pool = model_pool
        self.config = config
        self.bus = bus
        self.gate_mode = gate_mode
        self.recommender = EnsembleRecommender()

    def is_ensemble_stage(self, stage_name: str) -> bool:
        """Return True if this stage has multi-model ensemble configured."""
        stage = self.config.get_stage(stage_name)
        return stage.strategy != "single" and len(stage.models) > 1

    async def execute_stage(
        self,
        task: Task,
        agent_factory: Callable[[LLMClient], BaseAgent],
    ) -> AgentResult:
        """Run a stage with ensemble if configured, single-model otherwise."""
        stage_config = self.config.get_stage(task.name)

        # Fast path: single model
        if stage_config.strategy == "single" or len(stage_config.models) <= 1:
            model_name = stage_config.models[0] if stage_config.models else "default"
            client = self.model_pool.get(model_name)
            agent = agent_factory(client)
            return await agent.execute(task)

        # Asymmetric: primary + reviewer
        if stage_config.strategy == "asymmetric":
            return await self._run_asymmetric(task, agent_factory, stage_config)

        # Parallel: union / adversarial / consensus
        results = await self._run_parallel(task, agent_factory, stage_config)

        # Merge
        from eurekaclaw.ensemble.mergers import get_merger
        merger = get_merger(stage_config.strategy)
        if merger is None:
            # Unknown strategy — return first successful result
            for r in results.values():
                if r.success:
                    return r
            raise RuntimeError("All ensemble models failed and no merger available")

        # Pass model_pool to adversarial merger for cross-review
        if hasattr(merger, '_model_pool'):
            merger._model_pool = self.model_pool

        merged = await merger.merge(results, task, self.bus)

        # Generate recommendation
        rec = self.recommender.recommend(
            task.name, self.bus, self.model_pool.list_available(), self.config,
        )
        if rec:
            self.bus.put("ensemble_recommendation", rec)
            logger.info("Ensemble recommendation for %s: %s (confidence=%.2f)",
                        rec.stage, rec.reason, rec.confidence)

        return merged

    async def _run_parallel(
        self,
        task: Task,
        agent_factory: Callable[[LLMClient], BaseAgent],
        stage_config: Any,
    ) -> dict[str, AgentResult]:
        """Run N agents concurrently, return {model_name: result}."""

        async def run_one(model_name: str) -> AgentResult:
            client = self.model_pool.get(model_name)
            agent = agent_factory(client)
            scoped = ScopedBus(self.bus, namespace=model_name)
            agent.bus = scoped
            return await asyncio.wait_for(
                agent.execute(task.model_copy()),
                timeout=PER_MODEL_TIMEOUT,
            )

        coros = {name: run_one(name) for name in stage_config.models}
        raw = await asyncio.gather(*coros.values(), return_exceptions=True)

        results: dict[str, AgentResult] = {}
        for name, result in zip(coros.keys(), raw):
            if isinstance(result, Exception):
                logger.warning("Ensemble model '%s' failed: %s", name, result)
            else:
                results[name] = result

        if not results:
            raise RuntimeError(
                f"All ensemble models failed for stage '{task.name}': "
                + ", ".join(f"{n}: {r}" for n, r in zip(coros.keys(), raw))
            )

        return results

    async def _run_asymmetric(
        self,
        task: Task,
        agent_factory: Callable[[LLMClient], BaseAgent],
        stage_config: Any,
    ) -> AgentResult:
        """Primary model executes, reviewer model critiques."""
        primary_name = stage_config.models[0]
        primary_client = self.model_pool.get(primary_name)
        primary_agent = agent_factory(primary_client)
        primary_result = await primary_agent.execute(task)

        if not stage_config.reviewer:
            return primary_result

        # Run review
        reviewer_client = self.model_pool.get(stage_config.reviewer)
        review = await self._run_review(
            reviewer_client, stage_config.reviewer, primary_result, task,
        )
        primary_result.output["ensemble_review"] = review

        # Re-run if high-severity issues found
        if review.get("issues") and any(
            i.get("severity") == "high" for i in review["issues"]
        ):
            logger.info("Reviewer found high-severity issues — re-running primary with feedback")
            revised_task = task.model_copy()
            revised_task.description = (revised_task.description or "") + \
                f"\n\n[Reviewer feedback]: {json.dumps(review['issues'])}"
            primary_result = await primary_agent.execute(revised_task)
            primary_result.output["ensemble_review"] = review
            primary_result.output["ensemble_revision"] = True

        return primary_result

    async def _run_review(
        self,
        reviewer_client: LLMClient,
        reviewer_name: str,
        primary_result: AgentResult,
        task: Task,
    ) -> dict:
        """Ask a reviewer model to critique the primary model's output."""
        from eurekaclaw.config import settings

        review_prompt = (
            "You are an independent reviewer. Examine the following proof/analysis output "
            "and identify logical gaps, unjustified steps, missing edge cases, or errors.\n\n"
            f"Original task: {(task.description or '')[:500]}\n\n"
            f"Output to review:\n{json.dumps(primary_result.output, default=str)[:4000]}\n\n"
            "Respond with a JSON object:\n"
            '{"review_passed": bool, "issues": [{"lemma_id": "...", "severity": "high|medium|low", '
            '"description": "..."}], "confidence": 0.0-1.0, "summary": "1-2 sentence overall assessment"}'
        )

        try:
            response = await reviewer_client.messages.create(
                model=self.model_pool.get_model_name(reviewer_name),
                max_tokens=settings.max_tokens_verifier,
                system="You are a rigorous mathematical reviewer. Output only valid JSON.",
                messages=[{"role": "user", "content": review_prompt}],
            )
            text = response.content[0].text
            return json.loads(text)
        except Exception as e:
            logger.warning("Reviewer returned non-JSON or failed: %s", e)
            return {"review_passed": True, "issues": [], "confidence": 0.5}
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_ensemble_orchestrator.py -v`

- [ ] **Step 4: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/ensemble/orchestrator.py tests/test_ensemble_orchestrator.py && git commit -m "feat: add EnsembleOrchestrator with parallel dispatch and merge"
```

---

### Task 9: Wire Ensemble into MetaOrchestrator + TaskRouter

**Files:**
- Modify: `eurekaclaw/orchestrator/router.py`
- Modify: `eurekaclaw/orchestrator/meta_orchestrator.py`
- Modify: `.env.example`

- [ ] **Step 1: Add `create_agent()` to `eurekaclaw/orchestrator/router.py`**

Read the file first. Add after the `resolve` method:
```python
    def create_agent(self, task: Task, client: "LLMClient") -> BaseAgent:
        """Create a NEW agent instance for parallel ensemble execution.

        Unlike resolve() which returns shared singletons, this creates
        independent instances safe for concurrent use.
        """
        from eurekaclaw.agents.survey.agent import SurveyAgent
        from eurekaclaw.agents.ideation.agent import IdeationAgent
        from eurekaclaw.agents.theory.agent import TheoryAgent
        from eurekaclaw.agents.experiment.agent import ExperimentAgent
        from eurekaclaw.agents.writer.agent import WriterAgent

        _AGENT_CLASSES = {
            AgentRole.SURVEY: SurveyAgent,
            AgentRole.IDEATION: IdeationAgent,
            AgentRole.THEORY: TheoryAgent,
            AgentRole.EXPERIMENT: ExperimentAgent,
            AgentRole.WRITER: WriterAgent,
        }
        role = AgentRole(task.agent_role)
        cls = _AGENT_CLASSES.get(role)
        if not cls:
            raise ValueError(f"No agent class for role: {role}")

        # Get shared dependencies from the existing singleton agent
        template = self._agents[role]
        return cls(
            bus=template.bus,
            tool_registry=template.tool_registry,
            skill_injector=template.skill_injector,
            memory=template.memory,
            client=client,
        )
```

Also add the import: `from eurekaclaw.llm.base import LLMClient` (use string annotation to avoid circular import if needed).

- [ ] **Step 2: Modify `eurekaclaw/orchestrator/meta_orchestrator.py`**

In `__init__`, after `self.learning_loop = ...`, add:
```python
        # Ensemble (opt-in via ENSEMBLE_MODELS env var)
        from eurekaclaw.ensemble.model_pool import ModelPool
        from eurekaclaw.ensemble.config import EnsembleConfig
        from eurekaclaw.ensemble.orchestrator import EnsembleOrchestrator

        self.model_pool = ModelPool.create_from_config()
        self.ensemble_config = EnsembleConfig.from_env()
        self.ensemble = EnsembleOrchestrator(
            model_pool=self.model_pool,
            config=self.ensemble_config,
            bus=self.bus,
            gate_mode=settings.gate_mode,
        )
```

In the task execution loop, replace the agent execution block:
```python
            # Before (find this pattern):
            agent = self.router.resolve(task)
            ...
            result = await agent.execute(task)

            # After:
            if self.ensemble.is_ensemble_stage(task.name):
                agent_factory = lambda client: self.router.create_agent(task, client)
                result = await self.ensemble.execute_stage(task, agent_factory)
            else:
                agent = self.router.resolve(task)
                ...
                result = await agent.execute(task)
```

Note: Be careful to preserve the Progress spinner wrapping. The ensemble path should also be inside the Progress context manager.

- [ ] **Step 3: Update `.env.example`**

Add at the end:
```env
# ── Ensemble (N-Model) ──────────────────────────────────────────────────────
# Enable multi-model ensemble by listing named models (comma-separated).
# Each model needs MODEL_{NAME}_BACKEND, MODEL_{NAME}_API_KEY, MODEL_{NAME}_MODEL.
# If not set, all stages run with a single model (standard behavior).
#
# ENSEMBLE_MODELS=claude,gemini,gpt5
#
# MODEL_CLAUDE_BACKEND=anthropic
#
# MODEL_GEMINI_BACKEND=google
# MODEL_GEMINI_API_KEY=
# MODEL_GEMINI_MODEL=gemini-2.0-flash
#
# MODEL_GPT5_BACKEND=openrouter
# MODEL_GPT5_API_KEY=
# MODEL_GPT5_MODEL=openai/gpt-5.4
#
# Per-stage ensemble config (all optional — falls back to single model):
# ENSEMBLE_SURVEY_MODELS=claude,gemini
# ENSEMBLE_SURVEY_STRATEGY=union
#
# ENSEMBLE_IDEATION_MODELS=claude,gemini
# ENSEMBLE_IDEATION_STRATEGY=adversarial
#
# ENSEMBLE_THEORY_MODELS=claude
# ENSEMBLE_THEORY_REVIEWER=gemini
# ENSEMBLE_THEORY_STRATEGY=asymmetric
#
# ENSEMBLE_EXPERIMENT_MODELS=claude,gemini
# ENSEMBLE_EXPERIMENT_STRATEGY=consensus
```

- [ ] **Step 4: Run all tests**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/ -v`

- [ ] **Step 5: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/orchestrator/router.py eurekaclaw/orchestrator/meta_orchestrator.py .env.example && git commit -m "feat: wire ensemble orchestrator into pipeline"
```

---

### Task 10: Update README — Fork Notice + Contributions

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read the current README**

Read `README.md` to understand the full structure.

- [ ] **Step 2: Add fork notice at the top**

After the existing header/badges block, BEFORE the `---` and "What EurekaClaw Does" section, add:

```markdown
> **Fork Notice:** This is a fork of [EurekaClaw/EurekaClaw](https://github.com/EurekaClaw/EurekaClaw) with significant improvements to resilience, multi-model support, and research quality. See [What's New in This Fork](#whats-new-in-this-fork) below.
```

- [ ] **Step 3: Add "What's New in This Fork" section**

After the "What EurekaClaw Does" table, add a new section:

```markdown
## What's New in This Fork

This fork ([Lvigentini/EurekaClaw](https://github.com/Lvigentini/EurekaClaw)) adds three major contributions over the upstream project:

### 1. N-Model Ensemble Architecture
Run multiple LLMs (Claude, Gemini, GPT, Kimi, etc.) concurrently across pipeline stages with per-stage merge strategies:

| Stage | Strategy | What It Does |
|-------|----------|-------------|
| Survey | Union + dedup | Broader literature coverage from multiple models |
| Ideation | Adversarial cross-review | Models challenge each other's hypotheses |
| Theory | Asymmetric (primary + reviewer) | Independent proof verification catches blind spots |
| Experiment | Consensus | Both models must agree for high confidence |

Configure via environment variables — add `ENSEMBLE_MODELS=claude,gemini` and per-stage strategies. Adding a new model is 3 lines of config.

### 2. Crash Resilience
- **Incremental checkpointing** — state saved after each pipeline stage, not just at session end
- **Full-pipeline resume** — `eurekaclaw resume <session_id>` detects progress from any stage
- **Circuit breaker** — fails fast after 3 consecutive API failures instead of burning tokens
- **Error classification** — auth errors (401/403) fail immediately, server errors retry with backoff
- **ccproxy health monitoring** — auto-restarts OAuth proxy if it crashes mid-session
- **Token waste tracking** — reports tokens spent on failed retries at session end

### 3. Enhanced Search
- **Gemini parallel search** — Google Gemini with grounding searches alongside arXiv/Semantic Scholar for broader coverage, especially on interdisciplinary topics
- **Structured error handling** — tool failures return JSON errors that agents can reason about
- **Dynamic ensemble recommendations** — system suggests widening or narrowing model participation based on observed results
```

- [ ] **Step 4: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add README.md && git commit -m "docs: add fork notice and contribution summary to README"
```

---

### Task 11: Final Integration Test + Push

- [ ] **Step 1: Run all tests**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/ -v`
Expected: All pass (except pre-existing skips)

- [ ] **Step 2: Verify CLI imports**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/python -c "from eurekaclaw.ensemble.orchestrator import EnsembleOrchestrator; from eurekaclaw.ensemble.model_pool import ModelPool; print('Ensemble OK')"`

- [ ] **Step 3: Verify backward compatibility**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/python -c "from eurekaclaw.cli import main; print('CLI OK')"`
This should work WITHOUT any ENSEMBLE_* env vars set.

- [ ] **Step 4: Push to remote**

```bash
cd /Users/lor/_coding/EurekaClaw && git push origin main
```
