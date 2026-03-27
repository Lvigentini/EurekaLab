"""ScopedBus — namespaced bus wrapper for parallel ensemble isolation."""

from __future__ import annotations

from typing import Any

from eurekalab.knowledge_bus.bus import KnowledgeBus


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
        from eurekalab.types.artifacts import Bibliography
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
