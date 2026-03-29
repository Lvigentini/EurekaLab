"""Tests for reviewer persona loading and registry."""
import pytest
from pathlib import Path
from eurekalab.agents.reviewer.persona import ReviewerPersona
from eurekalab.agents.reviewer.registry import ReviewerRegistry


SAMPLE_PERSONA = """\
name: "Test Reviewer"
type: expert
icon: "🧪"
description: "A test reviewer persona"
author: "Test"
version: "1.0"
expertise: "Testing"
focus_areas:
  - "Unit tests"
  - "Integration tests"
scoring_dimensions:
  - clarity
  - rigor
scoring_scale: "1-5"
recommendation_options:
  - "Fail"
  - "Pass"
review_prompt: |
  You are a test reviewer. Review the paper for test coverage.
"""


@pytest.fixture
def persona_file(tmp_path) -> Path:
    p = tmp_path / "test_reviewer.yaml"
    p.write_text(SAMPLE_PERSONA)
    return p


def test_load_persona_from_yaml(persona_file):
    persona = ReviewerPersona.from_yaml(persona_file)
    assert persona.name == "Test Reviewer"
    assert persona.type == "expert"
    assert persona.icon == "🧪"
    assert "test reviewer" in persona.review_prompt.lower()


def test_persona_scoring_dimensions(persona_file):
    persona = ReviewerPersona.from_yaml(persona_file)
    assert persona.scoring_dimensions == ["clarity", "rigor"]
    assert persona.scoring_scale == "1-5"


def test_persona_expert_fields(persona_file):
    persona = ReviewerPersona.from_yaml(persona_file)
    assert persona.expertise == "Testing"
    assert "Unit tests" in persona.focus_areas


def test_persona_to_dict(persona_file):
    persona = ReviewerPersona.from_yaml(persona_file)
    d = persona.to_dict()
    assert d["name"] == "Test Reviewer"
    assert d["type"] == "expert"
    assert isinstance(d["scoring_dimensions"], list)


def test_registry_loads_builtin():
    registry = ReviewerRegistry()
    personas = registry.list_all()
    names = {p.name for p in personas}
    assert "Adversarial" in names
    assert "Rigorous" in names
    assert "Constructive" in names


def test_registry_get_by_name():
    registry = ReviewerRegistry()
    adv = registry.get("adversarial")
    assert adv is not None
    assert adv.name == "Adversarial"
    assert adv.type == "builtin"
    assert "weakness" in adv.review_prompt.lower()


def test_registry_loads_user_dir(tmp_path):
    user_dir = tmp_path / "reviewers"
    user_dir.mkdir()
    (user_dir / "custom.yaml").write_text(SAMPLE_PERSONA)
    registry = ReviewerRegistry(user_dir=user_dir)
    custom = registry.get("custom")
    assert custom is not None
    assert custom.name == "Test Reviewer"


def test_registry_user_dir_overrides_builtin(tmp_path):
    user_dir = tmp_path / "reviewers"
    user_dir.mkdir()
    # Create a custom "adversarial" that overrides the built-in
    custom = SAMPLE_PERSONA.replace("Test Reviewer", "Custom Adversarial")
    (user_dir / "adversarial.yaml").write_text(custom)
    registry = ReviewerRegistry(user_dir=user_dir)
    adv = registry.get("adversarial")
    assert adv is not None
    assert adv.name == "Custom Adversarial"


def test_registry_install(tmp_path):
    source = tmp_path / "source" / "new_reviewer.yaml"
    source.parent.mkdir()
    source.write_text(SAMPLE_PERSONA)
    target_dir = tmp_path / "reviewers"
    registry = ReviewerRegistry()
    persona = registry.install(source, target_dir)
    assert persona.name == "Test Reviewer"
    assert (target_dir / "new_reviewer.yaml").exists()
    assert registry.get("new_reviewer") is not None


def test_registry_list_sorted_by_type():
    registry = ReviewerRegistry()
    personas = registry.list_all()
    # All builtins should come first
    types = [p.type for p in personas]
    builtin_indices = [i for i, t in enumerate(types) if t == "builtin"]
    other_indices = [i for i, t in enumerate(types) if t != "builtin"]
    if builtin_indices and other_indices:
        assert max(builtin_indices) < min(other_indices)
