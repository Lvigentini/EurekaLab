"""Tests for ModelPool — named LLM client registry."""
import pytest
from unittest.mock import MagicMock
from eurekalab.ensemble.model_pool import ModelPool


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
