"""Tests for IdeationPool and InjectedIdea models."""
import pytest
from datetime import datetime
from eurekaclaw.types.artifacts import ResearchBrief, ResearchDirection
from eurekaclaw.orchestrator.ideation_pool import IdeationPool, InjectedIdea


@pytest.fixture
def pool() -> IdeationPool:
    return IdeationPool()


@pytest.fixture
def direction() -> ResearchDirection:
    return ResearchDirection(
        title="Optimal Bounds",
        hypothesis="The regret is O(sqrt(dT))",
        approach_sketch="Use concentration inequalities",
    )


def test_pool_starts_empty(pool):
    assert len(pool.directions) == 0
    assert pool.selected_direction is None
    assert pool.version == 0


def test_add_direction(pool, direction):
    pool.add_direction(direction, source="ideation:initial")
    assert len(pool.directions) == 1
    assert pool.idea_sources[direction.title] == "ideation:initial"


def test_inject_idea(pool):
    pool.inject_idea("What about spectral methods?", source="user")
    assert len(pool.injected_ideas) == 1
    assert pool.injected_ideas[0].text == "What about spectral methods?"
    assert pool.injected_ideas[0].incorporated is False


def test_inject_idea_increments_version(pool):
    pool.inject_idea("idea 1", source="user")
    assert pool.version == 1
    pool.inject_idea("idea 2", source="user")
    assert pool.version == 2


def test_add_insight(pool):
    pool.add_insight("Lemma L3 failed — assumption too strong")
    assert len(pool.emerged_insights) == 1


def test_discard_direction(pool, direction):
    pool.add_direction(direction, source="test")
    pool.discard_direction(direction.title, reason="Superseded by stronger result")
    assert len(pool.discarded) == 1
    assert pool.discarded[0][0] == "Optimal Bounds"


def test_unincorporated_ideas(pool):
    pool.inject_idea("idea 1", source="user")
    pool.inject_idea("idea 2", source="user")
    pool.injected_ideas[0].incorporated = True
    unincorp = pool.unincorporated_ideas
    assert len(unincorp) == 1
    assert unincorp[0].text == "idea 2"


def test_has_new_input_false_when_empty(pool):
    assert pool.has_new_input is False


def test_has_new_input_true_with_ideas(pool):
    pool.inject_idea("new idea", source="user")
    assert pool.has_new_input is True


def test_has_new_input_true_with_insights(pool):
    pool.add_insight("new insight")
    assert pool.has_new_input is True
