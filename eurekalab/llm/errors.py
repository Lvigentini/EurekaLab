"""LLM error classification — distinguishes auth, rate-limit, server, timeout, and client errors."""

from __future__ import annotations

import enum
import re


class ErrorClass(enum.Enum):
    """Categories of LLM call failures with different retry strategies."""
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    SERVER = "server"
    TIMEOUT = "timeout"
    CLIENT = "client"
    UNKNOWN = "unknown"

    @property
    def is_retryable(self) -> bool:
        return self in (ErrorClass.RATE_LIMIT, ErrorClass.SERVER, ErrorClass.TIMEOUT)


_PATTERNS: list[tuple[re.Pattern, ErrorClass]] = [
    (re.compile(r"(401|unauthorized)", re.IGNORECASE), ErrorClass.AUTH),
    (re.compile(r"(403|forbidden)", re.IGNORECASE), ErrorClass.AUTH),
    (re.compile(r"(429|rate.?limit)", re.IGNORECASE), ErrorClass.RATE_LIMIT),
    (re.compile(r"(overloaded|529)", re.IGNORECASE), ErrorClass.SERVER),
    (re.compile(r"(500|502|503|service.unavailable)", re.IGNORECASE), ErrorClass.SERVER),
    (re.compile(r"(timeout|timed.out)", re.IGNORECASE), ErrorClass.TIMEOUT),
    (re.compile(r"(400|422|invalid.request|bad.request)", re.IGNORECASE), ErrorClass.CLIENT),
]


def classify_error(exc: Exception) -> ErrorClass:
    """Classify an LLM exception into an ErrorClass for retry decisions."""
    msg = str(exc)
    for pattern, error_class in _PATTERNS:
        if pattern.search(msg):
            return error_class
    return ErrorClass.UNKNOWN
