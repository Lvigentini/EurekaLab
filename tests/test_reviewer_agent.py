"""Tests for ReviewerAgent."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from eurekalab.agents.reviewer.agent import ReviewerAgent, ReviewResult, ReviewComment


MOCK_REVIEW_JSON = json.dumps({
    "summary": "This paper proposes a new bandit algorithm.",
    "strengths": ["Clear motivation", "Strong experimental setup"],
    "comments": [
        {"severity": "major", "section": "Section 3", "comment": "Missing baseline comparison", "suggestion": "Add UCB1 baseline"},
        {"severity": "minor", "section": "Abstract", "comment": "Abstract too long", "suggestion": "Reduce to 200 words"},
        {"severity": "suggestion", "section": "Section 5", "comment": "Could add ablation", "suggestion": "Test without feature X"},
    ],
    "scores": {"novelty": 7, "rigor": 6, "clarity": 8},
    "recommendation": "Major Revision",
    "questions": ["What happens with non-stationary rewards?"],
    "missing_references": ["Thompson 1933"],
})


@pytest.fixture
def mock_client():
    client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock(text=MOCK_REVIEW_JSON)]
    client.messages.create = AsyncMock(return_value=response)
    return client


@pytest.fixture
def agent(mock_client):
    a = ReviewerAgent(client=mock_client)
    return a


def test_list_personas(agent):
    personas = agent.list_personas()
    names = {p.name for p in personas}
    assert "Adversarial" in names
    assert "Rigorous" in names
    assert "Constructive" in names


def test_get_persona(agent):
    p = agent.get_persona("adversarial")
    assert p is not None
    assert p.icon == "🔴"


@pytest.mark.asyncio
async def test_review_returns_structured_result(agent):
    result = await agent.review("This is a test paper about bandits.", persona_name="rigorous")
    assert isinstance(result, ReviewResult)
    assert result.persona_name == "Rigorous"
    assert result.major_count == 1
    assert result.minor_count == 1
    assert result.suggestion_count == 1


@pytest.mark.asyncio
async def test_review_parses_scores(agent):
    result = await agent.review("Test paper.", persona_name="rigorous")
    assert result.scores.get("novelty") == 7
    assert result.scores.get("rigor") == 6


@pytest.mark.asyncio
async def test_review_parses_recommendation(agent):
    result = await agent.review("Test paper.", persona_name="rigorous")
    assert result.recommendation == "Major Revision"


@pytest.mark.asyncio
async def test_review_with_custom_instructions(agent, mock_client):
    await agent.review("Test paper.", persona_name="rigorous", custom_instructions="Focus on statistical methods")
    call_args = mock_client.messages.create.call_args
    system = call_args.kwargs.get("system", "")
    assert "statistical methods" in system.lower()


@pytest.mark.asyncio
async def test_review_with_previous_comments(agent, mock_client):
    prev = [{"severity": "major", "comment": "Missing baseline", "resolved": False}]
    await agent.review("Revised paper.", persona_name="rigorous", previous_comments=prev)
    call_args = mock_client.messages.create.call_args
    system = call_args.kwargs.get("system", "")
    assert "re-review" in system.lower()


@pytest.mark.asyncio
async def test_review_unknown_persona(agent):
    with pytest.raises(ValueError, match="not found"):
        await agent.review("Test.", persona_name="nonexistent")


def test_review_result_to_dict(agent):
    result = ReviewResult(
        persona_name="Test",
        persona_icon="🧪",
        summary="Good paper",
        comments=[ReviewComment(severity="major", comment="Fix this")],
        scores={"rigor": 8},
        recommendation="Accept",
    )
    d = result.to_dict()
    assert d["persona_name"] == "Test"
    assert d["major_count"] == 1
    assert len(d["comments"]) == 1


def test_review_comment_resolution():
    c = ReviewComment(severity="major", comment="Issue", resolved=False)
    assert not c.resolved
    c.resolved = True
    c.user_response = "Fixed in revision"
    assert c.resolved
