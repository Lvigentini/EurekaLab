# Version Store (Phase 0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add git-like version history to research sessions so every state change is tracked, diffable, and reversible — enabling safe backtracking and iterative refinement.

**Architecture:** A `VersionStore` writes numbered JSON snapshots of the full `KnowledgeBus` state after every stage completion and user injection. Each version records a trigger (what caused it), the full serialized bus state, and a human-readable change summary. The existing `persist_incremental()` call sites in `MetaOrchestrator` become version commits, and the `_stage_progress.json` is subsumed by the version log. New CLI commands (`history`, `diff`, `checkout`) expose the version history to the user.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, existing KnowledgeBus serialization

---

## File Structure

```
eurekalab/versioning/
  __init__.py              # Public API: VersionStore, ResearchVersion
  store.py                 # VersionStore: commit, checkout, diff, log, head
  snapshot.py              # BusSnapshot: serialize/deserialize full bus state
  diff.py                  # Diff logic: compare two snapshots, produce human-readable changes

tests/
  test_version_snapshot.py # BusSnapshot round-trip serialization
  test_version_store.py    # VersionStore commit/checkout/log/head
  test_version_diff.py     # Diff between versions
  test_version_integration.py  # Integration with KnowledgeBus.persist_incremental

eurekalab/knowledge_bus/bus.py       # Modify: wire version commits into persist_incremental
eurekalab/orchestrator/meta_orchestrator.py  # Modify: pass trigger strings to persist_incremental
eurekalab/cli.py                     # Modify: add history, diff, checkout commands
```

---

### Task 1: BusSnapshot — Serialize/Deserialize Bus State

**Files:**
- Create: `eurekalab/versioning/__init__.py`
- Create: `eurekalab/versioning/snapshot.py`
- Test: `tests/test_version_snapshot.py`

- [ ] **Step 1: Write the failing test for snapshot round-trip**

```python
# tests/test_version_snapshot.py
"""Tests for BusSnapshot serialization."""
import json
import pytest
from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.types.artifacts import ResearchBrief, Bibliography, Paper, TheoryState
from eurekalab.versioning.snapshot import BusSnapshot


@pytest.fixture
def populated_bus() -> KnowledgeBus:
    bus = KnowledgeBus("test-snap-001")
    bus.put_research_brief(ResearchBrief(
        session_id="test-snap-001",
        input_mode="exploration",
        domain="ML theory",
        query="test query",
    ))
    bus.put_bibliography(Bibliography(
        session_id="test-snap-001",
        papers=[Paper(paper_id="p1", title="Paper One", authors=["A"])],
    ))
    bus.put("custom_key", {"foo": "bar"})
    return bus


def test_snapshot_captures_all_artifacts(populated_bus):
    snap = BusSnapshot.from_bus(populated_bus)
    assert "research_brief" in snap.artifacts
    assert "bibliography" in snap.artifacts
    assert "custom_key" in snap.artifacts


def test_snapshot_round_trip_json(populated_bus):
    snap = BusSnapshot.from_bus(populated_bus)
    json_str = snap.to_json()
    restored = BusSnapshot.from_json(json_str)
    assert restored.artifacts.keys() == snap.artifacts.keys()
    assert restored.session_id == snap.session_id


def test_snapshot_restore_to_bus(populated_bus):
    snap = BusSnapshot.from_bus(populated_bus)
    new_bus = snap.to_bus()
    brief = new_bus.get_research_brief()
    assert brief is not None
    assert brief.domain == "ML theory"
    bib = new_bus.get_bibliography()
    assert bib is not None
    assert len(bib.papers) == 1


def test_snapshot_preserves_custom_keys(populated_bus):
    snap = BusSnapshot.from_bus(populated_bus)
    new_bus = snap.to_bus()
    # Custom keys are restored as raw dicts
    assert new_bus.get("custom_key") == {"foo": "bar"}


def test_snapshot_handles_empty_bus():
    bus = KnowledgeBus("empty-session")
    snap = BusSnapshot.from_bus(bus)
    assert snap.artifacts == {}
    restored = snap.to_bus()
    assert restored.get_research_brief() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_version_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eurekalab.versioning'`

- [ ] **Step 3: Implement BusSnapshot**

```python
# eurekalab/versioning/__init__.py
"""Version management for EurekaLab research sessions."""
from eurekalab.versioning.snapshot import BusSnapshot
from eurekalab.versioning.store import VersionStore, ResearchVersion

__all__ = ["BusSnapshot", "VersionStore", "ResearchVersion"]
```

```python
# eurekalab/versioning/snapshot.py
"""BusSnapshot — serialize/deserialize full KnowledgeBus state.

NOTE: This module uses lazy imports for KnowledgeBus to avoid circular
imports (bus.py imports versioning, versioning imports bus.py).
"""
from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from eurekalab.knowledge_bus.bus import KnowledgeBus


def _model_map() -> dict[str, type]:
    """Lazy-load the model map to avoid import-time circular deps."""
    from eurekalab.types.artifacts import (
        Bibliography,
        ExperimentResult,
        ResearchBrief,
        TheoryState,
    )
    from eurekalab.types.tasks import TaskPipeline
    return {
        "research_brief": ResearchBrief,
        "theory_state": TheoryState,
        "experiment_result": ExperimentResult,
        "bibliography": Bibliography,
        "pipeline": TaskPipeline,
    }


class BusSnapshot:
    """A serializable snapshot of the full KnowledgeBus state."""

    def __init__(self, session_id: str, artifacts: dict[str, Any]) -> None:
        self.session_id = session_id
        self.artifacts = artifacts  # key → serialized JSON string per artifact

    @classmethod
    def from_bus(cls, bus: KnowledgeBus) -> BusSnapshot:
        artifacts: dict[str, str] = {}
        for key, value in bus._store.items():
            if hasattr(value, "model_dump_json"):
                artifacts[key] = value.model_dump_json()
            else:
                artifacts[key] = json.dumps(value, default=str)
        return cls(session_id=bus.session_id, artifacts=artifacts)

    def to_bus(self) -> KnowledgeBus:
        from eurekalab.knowledge_bus.bus import KnowledgeBus
        bus = KnowledgeBus(self.session_id)
        models = _model_map()
        for key, raw_json in self.artifacts.items():
            model_cls = models.get(key)
            if model_cls is not None:
                bus._store[key] = model_cls.model_validate_json(raw_json)
            else:
                bus._store[key] = json.loads(raw_json)
        return bus

    def to_json(self) -> str:
        return json.dumps({
            "session_id": self.session_id,
            "artifacts": self.artifacts,
        })

    @classmethod
    def from_json(cls, raw: str) -> BusSnapshot:
        data = json.loads(raw)
        return cls(
            session_id=data["session_id"],
            artifacts=data["artifacts"],
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_version_snapshot.py -v`
Expected: All 5 PASS

- [ ] **Step 5: Commit**

```bash
git add eurekalab/versioning/ tests/test_version_snapshot.py
git commit -m "feat(versioning): add BusSnapshot for serializing full bus state"
```

---

### Task 2: VersionStore — Commit, Log, Head

**Files:**
- Create: `eurekalab/versioning/store.py`
- Test: `tests/test_version_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_version_store.py
"""Tests for VersionStore: commit, log, head, checkout."""
import pytest
from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.types.artifacts import ResearchBrief
from eurekalab.versioning.store import VersionStore, ResearchVersion


@pytest.fixture
def store(tmp_path) -> VersionStore:
    return VersionStore("test-vs-001", tmp_path / "runs" / "test-vs-001")


@pytest.fixture
def bus_v1() -> KnowledgeBus:
    bus = KnowledgeBus("test-vs-001")
    bus.put_research_brief(ResearchBrief(
        session_id="test-vs-001",
        input_mode="exploration",
        domain="ML theory",
        query="initial query",
    ))
    return bus


@pytest.fixture
def bus_v2() -> KnowledgeBus:
    bus = KnowledgeBus("test-vs-001")
    bus.put_research_brief(ResearchBrief(
        session_id="test-vs-001",
        input_mode="exploration",
        domain="ML theory",
        query="revised query",
    ))
    return bus


def test_commit_creates_version(store, bus_v1):
    v = store.commit(bus_v1, trigger="stage:survey:completed")
    assert v.version_number == 1
    assert v.trigger == "stage:survey:completed"


def test_commit_increments_version_number(store, bus_v1, bus_v2):
    v1 = store.commit(bus_v1, trigger="stage:survey:completed")
    v2 = store.commit(bus_v2, trigger="stage:ideation:completed")
    assert v1.version_number == 1
    assert v2.version_number == 2


def test_head_returns_latest(store, bus_v1, bus_v2):
    store.commit(bus_v1, trigger="stage:survey:completed")
    store.commit(bus_v2, trigger="stage:ideation:completed")
    head = store.head
    assert head is not None
    assert head.version_number == 2


def test_head_none_when_empty(store):
    assert store.head is None


def test_log_returns_all_versions(store, bus_v1, bus_v2):
    store.commit(bus_v1, trigger="stage:survey:completed")
    store.commit(bus_v2, trigger="stage:ideation:completed")
    versions = store.log()
    assert len(versions) == 2
    assert versions[0].version_number == 1
    assert versions[1].version_number == 2


def test_commit_writes_to_disk(store, bus_v1):
    store.commit(bus_v1, trigger="test")
    files = list(store._versions_dir.glob("v*.json"))
    assert len(files) == 1


def test_log_survives_reload(store, bus_v1, bus_v2, tmp_path):
    store.commit(bus_v1, trigger="stage:survey:completed")
    store.commit(bus_v2, trigger="stage:ideation:completed")
    # Reload from disk
    store2 = VersionStore("test-vs-001", tmp_path / "runs" / "test-vs-001")
    versions = store2.log()
    assert len(versions) == 2
    assert store2.head.version_number == 2


def test_commit_records_completed_stages(store, bus_v1, bus_v2):
    store.commit(bus_v1, trigger="stage:survey:completed",
                 completed_stages=["survey"])
    store.commit(bus_v2, trigger="stage:ideation:completed",
                 completed_stages=["survey", "ideation"])
    assert store.head.completed_stages == ["survey", "ideation"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_version_store.py -v`
Expected: FAIL — `ImportError: cannot import name 'VersionStore'`

- [ ] **Step 3: Implement VersionStore and ResearchVersion**

```python
# eurekalab/versioning/store.py
"""VersionStore — git-like version management for research sessions."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.versioning.snapshot import BusSnapshot

logger = logging.getLogger(__name__)


class ResearchVersion(BaseModel):
    """A single point-in-time snapshot of the research state."""
    version_number: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trigger: str                          # e.g. "stage:survey:completed"
    completed_stages: list[str] = Field(default_factory=list)
    snapshot_json: str = ""               # serialized BusSnapshot
    changes: list[str] = Field(default_factory=list)  # human-readable


class VersionStore:
    """Manages version history for a research session."""

    def __init__(self, session_id: str, session_dir: Path) -> None:
        self.session_id = session_id
        self._session_dir = session_dir
        self._versions_dir = session_dir / "versions"
        self._versions: list[ResearchVersion] = []
        self._load_existing()

    def _load_existing(self) -> None:
        if not self._versions_dir.exists():
            return
        files = sorted(self._versions_dir.glob("v*.json"))
        for f in files:
            try:
                v = ResearchVersion.model_validate_json(f.read_text())
                self._versions.append(v)
            except Exception as e:
                logger.warning("Failed to load version file %s: %s", f, e)

    def commit(
        self,
        bus: KnowledgeBus,
        trigger: str,
        completed_stages: list[str] | None = None,
        changes: list[str] | None = None,
    ) -> ResearchVersion:
        snap = BusSnapshot.from_bus(bus)
        version_number = len(self._versions) + 1

        version = ResearchVersion(
            version_number=version_number,
            trigger=trigger,
            completed_stages=completed_stages or [],
            snapshot_json=snap.to_json(),
            changes=changes or [],
        )
        self._versions.append(version)
        self._write_version(version)
        logger.info("Version v%03d committed: %s", version_number, trigger)
        return version

    def _write_version(self, v: ResearchVersion) -> None:
        self._versions_dir.mkdir(parents=True, exist_ok=True)
        path = self._versions_dir / f"v{v.version_number:03d}.json"
        path.write_text(v.model_dump_json(indent=2), encoding="utf-8")

    @property
    def head(self) -> ResearchVersion | None:
        return self._versions[-1] if self._versions else None

    def log(self) -> list[ResearchVersion]:
        return list(self._versions)

    def get(self, version_number: int) -> ResearchVersion | None:
        for v in self._versions:
            if v.version_number == version_number:
                return v
        return None

    def checkout(self, version_number: int) -> KnowledgeBus:
        v = self.get(version_number)
        if v is None:
            raise ValueError(f"Version {version_number} not found")
        snap = BusSnapshot.from_json(v.snapshot_json)
        return snap.to_bus()
```

- [ ] **Step 4: Update `__init__.py` import** (already has the import from step 1, confirm it resolves)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_version_store.py -v`
Expected: All 9 PASS

- [ ] **Step 6: Commit**

```bash
git add eurekalab/versioning/store.py tests/test_version_store.py
git commit -m "feat(versioning): add VersionStore with commit, log, head, checkout"
```

---

### Task 3: Version Diff

**Files:**
- Create: `eurekalab/versioning/diff.py`
- Test: `tests/test_version_diff.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_version_diff.py
"""Tests for version diff logic."""
import pytest
from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.types.artifacts import (
    Bibliography, Paper, ProofRecord, ResearchBrief, TheoryState,
)
from eurekalab.versioning.diff import diff_versions
from eurekalab.versioning.store import VersionStore


@pytest.fixture
def store(tmp_path) -> VersionStore:
    return VersionStore("test-diff-001", tmp_path / "runs" / "test-diff-001")


def _make_bus(domain="ML theory", papers=None, proven=None) -> KnowledgeBus:
    bus = KnowledgeBus("test-diff-001")
    bus.put_research_brief(ResearchBrief(
        session_id="test-diff-001",
        input_mode="exploration",
        domain=domain,
        query="test",
    ))
    if papers:
        bus.put_bibliography(Bibliography(
            session_id="test-diff-001",
            papers=[Paper(paper_id=pid, title=t, authors=[]) for pid, t in papers],
        ))
    if proven is not None:
        state = TheoryState(
            session_id="test-diff-001",
            theorem_id="thm-001",
            informal_statement="test",
            status="in_progress",
        )
        # proven_lemmas is dict[str, ProofRecord]
        for lid, stmt in proven:
            state.proven_lemmas[lid] = ProofRecord(
                lemma_id=lid, proof_text=stmt,
            )
        bus.put_theory_state(state)
    return bus


def test_diff_detects_added_papers(store):
    bus1 = _make_bus(papers=[("p1", "Paper One")])
    bus2 = _make_bus(papers=[("p1", "Paper One"), ("p2", "Paper Two")])
    v1 = store.commit(bus1, trigger="v1")
    v2 = store.commit(bus2, trigger="v2")
    changes = diff_versions(store, v1.version_number, v2.version_number)
    assert any("Paper Two" in c or "p2" in c for c in changes)


def test_diff_detects_proven_lemma(store):
    bus1 = _make_bus(proven=[])
    bus2 = _make_bus(proven=[("L1", "Concentration bound")])
    v1 = store.commit(bus1, trigger="v1")
    v2 = store.commit(bus2, trigger="v2")
    changes = diff_versions(store, v1.version_number, v2.version_number)
    assert any("L1" in c or "lemma" in c.lower() for c in changes)


def test_diff_detects_domain_change(store):
    bus1 = _make_bus(domain="ML theory")
    bus2 = _make_bus(domain="Information theory")
    v1 = store.commit(bus1, trigger="v1")
    v2 = store.commit(bus2, trigger="v2")
    changes = diff_versions(store, v1.version_number, v2.version_number)
    assert any("domain" in c.lower() or "Information theory" in c for c in changes)


def test_diff_identical_versions(store):
    bus = _make_bus()
    v1 = store.commit(bus, trigger="v1")
    v2 = store.commit(bus, trigger="v2")
    changes = diff_versions(store, v1.version_number, v2.version_number)
    assert len(changes) == 0 or all("no changes" in c.lower() for c in changes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_version_diff.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eurekalab.versioning.diff'`

- [ ] **Step 3: Implement diff logic**

```python
# eurekalab/versioning/diff.py
"""Diff logic — compare two version snapshots and produce human-readable changes."""
from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from eurekalab.versioning.snapshot import BusSnapshot

if TYPE_CHECKING:
    from eurekalab.versioning.store import VersionStore


def diff_versions(store: VersionStore, v1_num: int, v2_num: int) -> list[str]:
    """Compare two versions and return a list of human-readable change descriptions."""
    ver1 = store.get(v1_num)
    ver2 = store.get(v2_num)
    if ver1 is None or ver2 is None:
        raise ValueError(f"Version not found: v{v1_num} or v{v2_num}")

    snap1 = BusSnapshot.from_json(ver1.snapshot_json)
    snap2 = BusSnapshot.from_json(ver2.snapshot_json)
    return _diff_snapshots(snap1, snap2)


def _diff_snapshots(old: BusSnapshot, new: BusSnapshot) -> list[str]:
    changes: list[str] = []

    all_keys = set(old.artifacts.keys()) | set(new.artifacts.keys())
    for key in sorted(all_keys):
        old_raw = old.artifacts.get(key)
        new_raw = new.artifacts.get(key)

        if old_raw is None and new_raw is not None:
            changes.append(f"Added: {key}")
            continue
        if old_raw is not None and new_raw is None:
            changes.append(f"Removed: {key}")
            continue
        if old_raw == new_raw:
            continue

        # Key exists in both but changed — produce key-specific diff
        old_data = json.loads(old_raw)
        new_data = json.loads(new_raw)
        key_changes = _diff_artifact(key, old_data, new_data)
        changes.extend(key_changes)

    return changes


def _diff_artifact(key: str, old: Any, new: Any) -> list[str]:
    """Produce human-readable diffs for known artifact types."""
    if key == "bibliography":
        return _diff_bibliography(old, new)
    if key == "research_brief":
        return _diff_brief(old, new)
    if key == "theory_state":
        return _diff_theory(old, new)
    # Generic fallback
    if old != new:
        return [f"Modified: {key}"]
    return []


def _diff_bibliography(old: dict, new: dict) -> list[str]:
    changes: list[str] = []
    old_ids = {p["paper_id"] for p in old.get("papers", [])}
    new_papers = new.get("papers", [])
    new_ids = {p["paper_id"] for p in new_papers}
    added = new_ids - old_ids
    removed = old_ids - new_ids
    if added:
        titles = {p["paper_id"]: p.get("title", "?") for p in new_papers}
        for pid in sorted(added):
            changes.append(f"Bibliography: +paper '{titles.get(pid, pid)}' ({pid})")
    if removed:
        changes.append(f"Bibliography: -{len(removed)} paper(s) removed")
    return changes


def _diff_brief(old: dict, new: dict) -> list[str]:
    changes: list[str] = []
    for field in ("domain", "query", "conjecture"):
        ov = old.get(field, "")
        nv = new.get(field, "")
        if ov != nv and nv:
            changes.append(f"Brief: {field} changed to '{nv}'")

    old_dirs = {d.get("title", "") for d in old.get("directions", [])}
    new_dirs = {d.get("title", "") for d in new.get("directions", [])}
    for title in sorted(new_dirs - old_dirs):
        if title:
            changes.append(f"Brief: +direction '{title}'")
    for title in sorted(old_dirs - new_dirs):
        if title:
            changes.append(f"Brief: -direction '{title}'")

    old_ideas = set(old.get("injected_ideas", []))
    new_ideas = set(new.get("injected_ideas", []))
    for idea in sorted(new_ideas - old_ideas):
        changes.append(f"Brief: +injected idea '{idea[:60]}'")
    return changes


def _diff_theory(old: dict, new: dict) -> list[str]:
    changes: list[str] = []
    # proven_lemmas is dict[str, ProofRecord] — keys are lemma IDs
    old_proven = set(old.get("proven_lemmas", {}).keys())
    new_proven_dict = new.get("proven_lemmas", {})
    new_proven = set(new_proven_dict.keys())
    added = new_proven - old_proven
    if added:
        for lid in sorted(added):
            record = new_proven_dict.get(lid, {})
            proof_text = record.get("proof_text", "")[:60]
            changes.append(f"Theory: +proven lemma {lid} '{proof_text}'")

    old_status = old.get("status", "")
    new_status = new.get("status", "")
    if old_status != new_status:
        changes.append(f"Theory: status {old_status} -> {new_status}")
    return changes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_version_diff.py -v`
Expected: All 4 PASS

- [ ] **Step 5: Commit**

```bash
git add eurekalab/versioning/diff.py tests/test_version_diff.py
git commit -m "feat(versioning): add diff logic for comparing version snapshots"
```

---

### Task 4: Wire VersionStore into KnowledgeBus

**Files:**
- Modify: `eurekalab/knowledge_bus/bus.py` (lines 147-175 — `persist_incremental`)
- Test: `tests/test_version_integration.py`

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_version_integration.py
"""Integration tests — VersionStore wired into KnowledgeBus."""
import json
import pytest
from eurekalab.knowledge_bus.bus import KnowledgeBus
from eurekalab.types.artifacts import ResearchBrief, Bibliography, Paper
from eurekalab.versioning.store import VersionStore


@pytest.fixture
def bus(tmp_path) -> KnowledgeBus:
    b = KnowledgeBus("test-int-001")
    b._session_dir = tmp_path / "runs" / "test-int-001"
    return b


def test_persist_incremental_creates_version(bus):
    bus.put_research_brief(ResearchBrief(
        session_id="test-int-001",
        input_mode="exploration",
        domain="test",
        query="test",
    ))
    bus.persist_incremental(completed_stage="survey")
    assert bus.version_store is not None
    assert bus.version_store.head is not None
    assert bus.version_store.head.trigger == "stage:survey:completed"


def test_multiple_stages_create_multiple_versions(bus):
    bus.put_research_brief(ResearchBrief(
        session_id="test-int-001",
        input_mode="exploration",
        domain="test",
        query="test",
    ))
    bus.persist_incremental(completed_stage="survey")
    bus.persist_incremental(completed_stage="ideation")
    versions = bus.version_store.log()
    assert len(versions) == 2


def test_version_store_still_writes_stage_progress(bus):
    bus.persist_incremental(completed_stage="survey")
    marker = bus._session_dir / "_stage_progress.json"
    assert marker.exists()
    data = json.loads(marker.read_text())
    assert "survey" in data["completed_stages"]


def test_failed_stage_recorded_in_version(bus):
    bus.persist_incremental(completed_stage="survey_FAILED")
    head = bus.version_store.head
    assert head is not None
    assert "FAILED" in head.trigger


def test_version_store_loaded_on_bus_load(bus, tmp_path):
    bus.put_research_brief(ResearchBrief(
        session_id="test-int-001",
        input_mode="exploration",
        domain="test",
        query="test",
    ))
    bus.persist_incremental(completed_stage="survey")

    # Reload bus from disk
    restored = KnowledgeBus.load("test-int-001", tmp_path / "runs" / "test-int-001")
    assert restored.version_store is not None
    assert len(restored.version_store.log()) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_version_integration.py -v`
Expected: FAIL — `AttributeError: 'KnowledgeBus' object has no attribute 'version_store'`

- [ ] **Step 3: Modify KnowledgeBus to wire in VersionStore**

In `eurekalab/knowledge_bus/bus.py`, make these changes:

**Add `version_store` property to `__init__`:**
After `self._completed_stages: list[str] = []` add:
```python
self.version_store = None  # VersionStore, lazy-initialized (avoids circular import)
```

**NOTE on circular imports:** Do NOT add a top-level import of `VersionStore` in `bus.py`.
`snapshot.py` imports `KnowledgeBus`, so a top-level import from `versioning` in `bus.py`
would create a circular import. All `VersionStore` usage must be lazy-imported inside methods.

**Modify `persist_incremental` to commit a version:**
After the existing stage progress write, add version commit logic:
```python
# Version store: auto-commit on every incremental persist
if self._session_dir is not None:
    from eurekalab.versioning.store import VersionStore  # lazy to avoid circular import
    if self.version_store is None:
        self.version_store = VersionStore(self.session_id, self._session_dir)
    trigger = f"stage:{completed_stage}:completed" if completed_stage else "persist"
    if completed_stage and "_FAILED" in completed_stage:
        trigger = f"stage:{completed_stage}"
    self.version_store.commit(
        self,
        trigger=trigger,
        completed_stages=list(self._completed_stages),
    )
```

**Modify `load` classmethod to restore VersionStore and set _session_dir:**
After the model_map restoration loop, add:
```python
bus._session_dir = session_dir  # fix: was missing, needed for subsequent persist_incremental calls
from eurekalab.versioning.store import VersionStore  # lazy to avoid circular import
bus.version_store = VersionStore(session_id, session_dir)
```

- [ ] **Step 4: Run ALL version tests to verify nothing broke**

Run: `pytest tests/test_version_snapshot.py tests/test_version_store.py tests/test_version_diff.py tests/test_version_integration.py tests/test_incremental_persist.py -v`
Expected: All PASS (including old incremental persist tests — backward compatible)

- [ ] **Step 5: Commit**

```bash
git add eurekalab/knowledge_bus/bus.py tests/test_version_integration.py
git commit -m "feat(versioning): wire VersionStore into KnowledgeBus.persist_incremental"
```

---

### Task 5: CLI Commands — history, diff, checkout

**Files:**
- Modify: `eurekalab/cli.py`
- No automated tests for CLI commands (they use console I/O) — manual verification steps provided

- [ ] **Step 1: Add `history` command to cli.py**

Add after the `resume` command:

```python
@main.command()
@click.argument("session_id")
def history(session_id: str) -> None:
    """Show version history for a session.

    Example: eurekalab history abc12345-...
    """
    from datetime import datetime, timezone
    from rich.table import Table
    from eurekalab.versioning.store import VersionStore

    session_dir = settings.runs_dir / session_id
    if not session_dir.exists():
        console.print(f"[red]Session not found: {session_dir}[/red]")
        sys.exit(1)

    store = VersionStore(session_id, session_dir)
    versions = store.log()
    if not versions:
        console.print("[yellow]No versions found for this session.[/yellow]")
        return

    table = Table(title=f"Version History — {session_id[:8]}")
    table.add_column("Version", style="cyan", width=8)
    table.add_column("Time", style="dim", width=20)
    table.add_column("Trigger", style="green")
    table.add_column("Stages", style="yellow")

    now = datetime.now(timezone.utc)
    for v in reversed(versions):
        age = now - v.timestamp
        if age.total_seconds() < 3600:
            time_str = f"{int(age.total_seconds() / 60)}m ago"
        elif age.total_seconds() < 86400:
            time_str = f"{int(age.total_seconds() / 3600)}h ago"
        else:
            time_str = v.timestamp.strftime("%Y-%m-%d %H:%M")

        head_marker = " *" if v == store.head else ""
        table.add_row(
            f"v{v.version_number:03d}{head_marker}",
            time_str,
            v.trigger,
            ", ".join(v.completed_stages[-3:]) if v.completed_stages else "—",
        )

    console.print(table)
```

- [ ] **Step 2: Add `diff` command**

```python
@main.command("diff")
@click.argument("session_id")
@click.argument("v1", type=int)
@click.argument("v2", type=int)
def version_diff(session_id: str, v1: int, v2: int) -> None:
    """Show changes between two versions.

    Example: eurekalab diff abc12345-... 1 3
    """
    from eurekalab.versioning.store import VersionStore
    from eurekalab.versioning.diff import diff_versions

    session_dir = settings.runs_dir / session_id
    if not session_dir.exists():
        console.print(f"[red]Session not found: {session_dir}[/red]")
        sys.exit(1)

    store = VersionStore(session_id, session_dir)
    try:
        changes = diff_versions(store, v1, v2)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    if not changes:
        console.print(f"[dim]No changes between v{v1:03d} and v{v2:03d}[/dim]")
        return

    console.print(f"\n[bold]Changes v{v1:03d} → v{v2:03d}:[/bold]")
    for change in changes:
        if change.startswith("+") or "+paper" in change or "+proven" in change or "+direction" in change:
            console.print(f"  [green]{change}[/green]")
        elif change.startswith("-") or "removed" in change.lower():
            console.print(f"  [red]{change}[/red]")
        else:
            console.print(f"  [yellow]{change}[/yellow]")
```

- [ ] **Step 3: Add `checkout` command**

```python
@main.command()
@click.argument("session_id")
@click.argument("version_number", type=int)
def checkout(session_id: str, version_number: int) -> None:
    """Restore session state to a specific version.

    Example: eurekalab checkout abc12345-... 3
    """
    from eurekalab.versioning.store import VersionStore

    session_dir = settings.runs_dir / session_id
    if not session_dir.exists():
        console.print(f"[red]Session not found: {session_dir}[/red]")
        sys.exit(1)

    store = VersionStore(session_id, session_dir)
    target = store.get(version_number)
    if target is None:
        console.print(f"[red]Version {version_number} not found.[/red]")
        sys.exit(1)

    from rich.prompt import Confirm
    console.print(f"\n[bold]Checkout v{version_number:03d}[/bold]: {target.trigger}")
    console.print(f"  Stages: {', '.join(target.completed_stages) or '(none)'}")
    if not Confirm.ask("Restore this version? (current HEAD will be preserved as a version)", default=True):
        return

    # Restore bus from the target version
    bus = store.checkout(version_number)

    # Commit the checkout itself as a new version (so HEAD is never lost)
    store.commit(
        bus,
        trigger=f"checkout:v{version_number:03d}",
        completed_stages=target.completed_stages,
        changes=[f"Restored state from v{version_number:03d}"],
    )

    # Write restored state to session dir (overwrite current artifacts)
    bus._session_dir = session_dir
    bus.persist(session_dir)

    head = store.head
    console.print(f"\n[green]Restored to v{version_number:03d}. New HEAD is v{head.version_number:03d}.[/green]")
    console.print(f"  Completed stages: {', '.join(target.completed_stages) or '(none)'}")
    console.print(f"  Resume with: [bold]eurekalab resume {session_id}[/bold]")
```

- [ ] **Step 4: Verify CLI commands register**

Run: `python -m eurekalab.cli --help`
Expected: `history`, `diff`, `checkout` appear in the command list

- [ ] **Step 5: Commit**

```bash
git add eurekalab/cli.py
git commit -m "feat(versioning): add history, diff, checkout CLI commands"
```

---

### Task 6: Enrich MetaOrchestrator Trigger Strings

**Files:**
- Modify: `eurekalab/orchestrator/meta_orchestrator.py` (lines 233-236)

Currently `persist_incremental` is called with just the stage name. We should pass richer trigger context so the version log is informative.

- [ ] **Step 1: Update the persist_incremental call in MetaOrchestrator**

In `meta_orchestrator.py`, find the line (currently ~236):
```python
stage_label = task.name if (result and not result.failed) else f"{task.name}_FAILED"
self.bus.persist_incremental(completed_stage=stage_label)
```

This already works — `persist_incremental` now auto-generates the trigger string `stage:<name>:completed` in the bus. No code change needed here, but verify the trigger format is correct.

- [ ] **Step 2: Run the full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests PASS, all new version tests PASS

- [ ] **Step 3: Commit (if any changes were needed)**

```bash
git add -A
git commit -m "chore(versioning): verify trigger strings in MetaOrchestrator"
```

---

### Task 7: Version Bump and Final Push

- [ ] **Step 1: Bump version to 0.2.0**

In `pyproject.toml`: change `version = "0.1.1"` to `version = "0.2.0"`
In `eurekalab/__init__.py`: change `__version__ = "0.1.1"` to `__version__ = "0.2.0"`

- [ ] **Step 2: Run full test suite one final time**

Run: `pytest tests/ -v --tb=short`
Expected: ALL PASS

- [ ] **Step 3: Commit and push**

```bash
git add eurekalab/__init__.py pyproject.toml
git commit -m "feat(versioning): add git-like version history for research sessions

Phase 0 of the non-linear pipeline redesign:
- BusSnapshot: serialize/deserialize full bus state
- VersionStore: commit, checkout, diff, log, head
- Auto-commit on every stage completion via persist_incremental
- CLI commands: history, diff, checkout
- Bump to v0.2.0"
git push
```
