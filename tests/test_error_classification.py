"""Tests for LLM error classification."""
import pytest
from eurekalab.llm.errors import ErrorClass, classify_error


def test_rate_limit_429():
    exc = Exception("Error code: 429 - rate limit exceeded")
    assert classify_error(exc) == ErrorClass.RATE_LIMIT


def test_rate_limit_keyword():
    exc = Exception("You have exceeded your rate_limit")
    assert classify_error(exc) == ErrorClass.RATE_LIMIT


def test_auth_401():
    exc = Exception("Error code: 401 - Unauthorized")
    assert classify_error(exc) == ErrorClass.AUTH


def test_auth_403():
    exc = Exception("Error code: 403 - Forbidden")
    assert classify_error(exc) == ErrorClass.AUTH


def test_server_500():
    exc = Exception("Error code: 500 - An internal server error occurred")
    assert classify_error(exc) == ErrorClass.SERVER


def test_server_502():
    exc = Exception("Error code: 502 - Bad Gateway")
    assert classify_error(exc) == ErrorClass.SERVER


def test_server_503():
    exc = Exception("service unavailable")
    assert classify_error(exc) == ErrorClass.SERVER


def test_server_overloaded():
    exc = Exception("overloaded_error: Anthropic is overloaded")
    assert classify_error(exc) == ErrorClass.SERVER


def test_timeout():
    exc = Exception("Request timed out after 30s")
    assert classify_error(exc) == ErrorClass.TIMEOUT


def test_client_error():
    exc = Exception("Error code: 400 - Invalid request")
    assert classify_error(exc) == ErrorClass.CLIENT


def test_unknown():
    exc = Exception("Something completely unexpected")
    assert classify_error(exc) == ErrorClass.UNKNOWN


def test_retryable_classes():
    assert ErrorClass.RATE_LIMIT.is_retryable
    assert ErrorClass.SERVER.is_retryable
    assert ErrorClass.TIMEOUT.is_retryable
    assert not ErrorClass.AUTH.is_retryable
    assert not ErrorClass.CLIENT.is_retryable
    assert not ErrorClass.UNKNOWN.is_retryable
