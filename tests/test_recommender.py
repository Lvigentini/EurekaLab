# tests/test_recommender.py
"""Tests for EnsembleRecommender — heuristic suggestions."""
import pytest
from eurekalab.ensemble.recommender import EnsembleRecommender
from eurekalab.ensemble.config import EnsembleConfig
from eurekalab.knowledge_bus.bus import KnowledgeBus


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
