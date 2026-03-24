"""Abstract LLMClient — identical call surface to anthropic.AsyncAnthropic.messages."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Any

from eurekaclaw.llm.errors import ErrorClass, classify_error
from eurekaclaw.llm.types import NormalizedMessage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global token counter
# ---------------------------------------------------------------------------
_GLOBAL_TOKENS: dict[str, int] = {"input": 0, "output": 0}
_WASTED_TOKENS: dict[str, int] = {"input": 0, "output": 0}


def get_global_tokens() -> dict[str, int]:
    return dict(_GLOBAL_TOKENS)


def get_wasted_tokens() -> dict[str, int]:
    return dict(_WASTED_TOKENS)


def reset_global_tokens() -> None:
    _GLOBAL_TOKENS["input"] = 0
    _GLOBAL_TOKENS["output"] = 0
    _WASTED_TOKENS["input"] = 0
    _WASTED_TOKENS["output"] = 0


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Simple circuit breaker — fails fast after consecutive failures."""

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 60.0) -> None:
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._failure_count = 0
        self._opened_at: float = 0.0

    @property
    def is_open(self) -> bool:
        if self._failure_count >= self._failure_threshold:
            if time.monotonic() - self._opened_at > self._reset_timeout:
                self._failure_count = 0
                return False
            return True
        return False

    def check(self) -> None:
        if self.is_open:
            raise RuntimeError(
                f"Circuit breaker is open — {self._failure_count} consecutive failures "
                f"in the last {self._reset_timeout}s. Waiting for reset."
            )

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._opened_at = time.monotonic()
            logger.warning(
                "Circuit breaker OPEN after %d consecutive failures",
                self._failure_count,
            )

    def record_success(self) -> None:
        self._failure_count = 0


_circuit_breaker = CircuitBreaker(failure_threshold=3, reset_timeout=60.0)


class _MessagesNamespace:
    """Provides the `client.messages.create(...)` call surface."""

    def __init__(self, owner: "LLMClient") -> None:
        self._owner = owner

    async def create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> NormalizedMessage:
        from eurekaclaw.config import settings

        attempts = max(1, settings.llm_retry_attempts)
        wait_min = settings.llm_retry_wait_min
        wait_max = settings.llm_retry_wait_max

        last_exc: Exception = RuntimeError("unreachable")
        for attempt in range(attempts):
            _circuit_breaker.check()

            try:
                response = await self._owner._create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=messages,
                    system=system,
                    tools=tools,
                    **kwargs,
                )
                if not response.content:
                    raise ValueError("LLM returned empty content list")
                _GLOBAL_TOKENS["input"] += response.usage.input_tokens
                _GLOBAL_TOKENS["output"] += response.usage.output_tokens
                _circuit_breaker.record_success()
                return response
            except Exception as exc:
                last_exc = exc
                error_class = classify_error(exc)

                if not error_class.is_retryable:
                    logger.error(
                        "LLM call failed (non-retryable %s): %s",
                        error_class.value, exc,
                    )
                    _circuit_breaker.record_failure()
                    raise

                if attempt == attempts - 1:
                    _circuit_breaker.record_failure()
                    raise

                base_wait = min(wait_min * (2 ** attempt), wait_max)
                if error_class == ErrorClass.RATE_LIMIT:
                    jitter = random.uniform(0, base_wait * 0.3)
                    wait = base_wait + jitter
                else:
                    wait = base_wait

                logger.warning(
                    "LLM call failed (%s, attempt %d/%d, retrying in %.1fs): %s",
                    error_class.value, attempt + 1, attempts, wait, exc,
                )
                await asyncio.sleep(wait)

        raise last_exc


class LLMClient(ABC):
    """Unified LLM client. All backends expose `.messages.create(...)`."""

    def __init__(self) -> None:
        self.messages = _MessagesNamespace(self)

    @abstractmethod
    async def _create(
        self,
        *,
        model: str,
        max_tokens: int,
        messages: list[dict[str, Any]],
        system: str = "",
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> NormalizedMessage:
        ...
