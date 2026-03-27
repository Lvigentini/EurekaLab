"""Tests for circuit breaker and retry logic in LLMClient."""
import time
import pytest
from eurekalab.llm.base import CircuitBreaker


@pytest.fixture
def breaker():
    return CircuitBreaker(failure_threshold=3, reset_timeout=2.0)


def test_breaker_starts_closed(breaker):
    assert not breaker.is_open


def test_breaker_opens_after_threshold(breaker):
    for _ in range(3):
        breaker.record_failure()
    assert breaker.is_open


def test_breaker_resets_after_timeout(breaker):
    for _ in range(3):
        breaker.record_failure()
    assert breaker.is_open
    breaker._opened_at = time.monotonic() - 3.0
    assert not breaker.is_open


def test_breaker_resets_on_success(breaker):
    breaker.record_failure()
    breaker.record_failure()
    assert not breaker.is_open
    breaker.record_success()
    assert breaker._failure_count == 0


def test_breaker_raises_when_open(breaker):
    for _ in range(3):
        breaker.record_failure()
    with pytest.raises(RuntimeError, match="Circuit breaker is open"):
        breaker.check()
