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
