"""Pluggable merge strategies for ensemble pipeline stages."""

from eurekalab.ensemble.mergers.base import BaseMerger

MERGER_REGISTRY: dict[str, type[BaseMerger] | None] = {}


def _register_mergers() -> None:
    """Lazy-load merger classes to avoid circular imports."""
    global MERGER_REGISTRY
    from eurekalab.ensemble.mergers.union import UnionMerger
    from eurekalab.ensemble.mergers.adversarial import AdversarialMerger
    from eurekalab.ensemble.mergers.consensus import ConsensusMerger

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
