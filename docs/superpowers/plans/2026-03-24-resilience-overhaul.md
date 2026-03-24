# EurekaClaw Resilience Overhaul

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make EurekaClaw crash-resilient: fix auth monitoring, eliminate double retries, add per-stage checkpointing, and surface errors instead of swallowing them.

**Architecture:** Three layers of fixes: (1) LLM call reliability — single retry layer with error classification and ccproxy health monitoring, (2) Pipeline durability — incremental bus persistence after each stage with full-pipeline resume support, (3) Error transparency — replace silent `pass` blocks with logged warnings and structured error returns.

**Tech Stack:** Python 3.11, asyncio, Pydantic 2.0, anthropic SDK, tenacity (to be removed from agent layer)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `eurekaclaw/llm/errors.py` | **Create** | Error classification enum + classifier function |
| `eurekaclaw/llm/base.py` | Modify | Add error classification to retry, add 500 to retryable, add circuit breaker |
| `eurekaclaw/agents/base.py` | Modify | Remove tenacity double-retry, add token waste tracking |
| `eurekaclaw/ccproxy_manager.py` | Modify | Add health monitor, auto-restart on crash |
| `eurekaclaw/knowledge_bus/bus.py` | Modify | Add `persist_incremental()` method |
| `eurekaclaw/orchestrator/meta_orchestrator.py` | Modify | Call `bus.persist_incremental()` after each stage, stop pipeline on critical failure |
| `eurekaclaw/orchestrator/session_checkpoint.py` | **Create** | Full-pipeline checkpoint (which stage completed, bus state) |
| `eurekaclaw/cli.py` | Modify | Add `resume` that works for all stages, not just theory |
| `eurekaclaw/agents/survey/agent.py` | Modify | Log JSON parse failures instead of silent pass |
| `eurekaclaw/tools/registry.py` | Modify | Return structured JSON errors |
| `tests/test_error_classification.py` | **Create** | Tests for error classifier |
| `tests/test_circuit_breaker.py` | **Create** | Tests for circuit breaker |
| `tests/test_session_checkpoint.py` | **Create** | Tests for full-pipeline checkpoint |
| `tests/test_incremental_persist.py` | **Create** | Tests for incremental bus persistence |
| `tests/test_retry_single_layer.py` | **Create** | Tests confirming no double retry |

---

### Task 1: Error Classification

**Files:**
- Create: `eurekaclaw/llm/errors.py`
- Test: `tests/test_error_classification.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_error_classification.py
"""Tests for LLM error classification."""
import pytest
from eurekaclaw.llm.errors import ErrorClass, classify_error


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_error_classification.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'eurekaclaw.llm.errors'`

- [ ] **Step 3: Write the implementation**

```python
# eurekaclaw/llm/errors.py
"""LLM error classification — distinguishes auth, rate-limit, server, timeout, and client errors."""

from __future__ import annotations

import enum
import re


class ErrorClass(enum.Enum):
    """Categories of LLM call failures with different retry strategies."""
    RATE_LIMIT = "rate_limit"   # 429, rate limit keywords — retry with backoff + jitter
    AUTH = "auth"               # 401, 403 — do NOT retry, fail immediately
    SERVER = "server"           # 500, 502, 503, 529, overloaded — retry with backoff
    TIMEOUT = "timeout"         # timeout, timed out — retry once or twice
    CLIENT = "client"           # 400, 422 — do NOT retry, bad request
    UNKNOWN = "unknown"         # anything else — do NOT retry by default

    @property
    def is_retryable(self) -> bool:
        return self in (ErrorClass.RATE_LIMIT, ErrorClass.SERVER, ErrorClass.TIMEOUT)


# Order matters: check specific patterns before generic ones.
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_error_classification.py -v`
Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/llm/errors.py tests/test_error_classification.py
git commit -m "feat: add LLM error classification for retry decisions"
```

---

### Task 2: Fix LLM Retry with Error Classification + Circuit Breaker

**Files:**
- Modify: `eurekaclaw/llm/base.py`
- Test: `tests/test_circuit_breaker.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_circuit_breaker.py
"""Tests for circuit breaker and retry logic in LLMClient."""
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch
from eurekaclaw.llm.base import CircuitBreaker


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
    # Simulate time passing
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_circuit_breaker.py -v`
Expected: FAIL with `ImportError: cannot import name 'CircuitBreaker'`

- [ ] **Step 3: Rewrite `eurekaclaw/llm/base.py`**

Replace the full file with:

```python
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
    """Return a snapshot copy of cumulative token usage across all LLM calls."""
    return dict(_GLOBAL_TOKENS)


def get_wasted_tokens() -> dict[str, int]:
    """Return tokens spent on calls that ultimately failed."""
    return dict(_WASTED_TOKENS)


def reset_global_tokens() -> None:
    """Reset the global counter. Call at the start of each top-level session."""
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
            # Check if reset timeout has elapsed
            if time.monotonic() - self._opened_at > self._reset_timeout:
                self._failure_count = 0
                return False
            return True
        return False

    def check(self) -> None:
        """Raise if the circuit is open."""
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


# Shared circuit breaker instance
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
            # Check circuit breaker before each attempt
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
                # Accumulate into the global counter
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

                # Exponential backoff with jitter for rate limits
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

        raise last_exc  # unreachable but satisfies type checker


class LLMClient(ABC):
    """Unified LLM client.  All backends expose `.messages.create(...)`.

    Usage (identical to the raw Anthropic client):
        response = await client.messages.create(
            model="...", max_tokens=4096, system="...", messages=[...], tools=[...]
        )
        text = response.content[0].text
    """

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_circuit_breaker.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/llm/base.py tests/test_circuit_breaker.py
git commit -m "feat: add circuit breaker and error-classified retry to LLM client"
```

---

### Task 3: Remove Double Retry from BaseAgent

**Files:**
- Modify: `eurekaclaw/agents/base.py`
- Test: `tests/test_retry_single_layer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_retry_single_layer.py
"""Verify BaseAgent._call_model does NOT wrap retries (single layer only)."""
import ast
import inspect
import textwrap


def test_no_tenacity_in_call_model():
    """BaseAgent._call_model must not use tenacity — retry is in LLMClient only."""
    from eurekaclaw.agents.base import BaseAgent
    source = inspect.getsource(BaseAgent._call_model)
    assert "AsyncRetrying" not in source, "_call_model still uses tenacity double-retry"
    assert "Retrying" not in source, "_call_model still uses tenacity double-retry"


def test_no_tenacity_import():
    """The agents.base module should not import tenacity at all."""
    import eurekaclaw.agents.base as mod
    source = inspect.getsource(mod)
    # Allow comments mentioning tenacity, but no actual import
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                names = [node.module or ""]
            for name in names:
                assert "tenacity" not in name, f"tenacity still imported: {name}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_retry_single_layer.py -v`
Expected: FAIL — tenacity is still imported and used in `_call_model`

- [ ] **Step 3: Modify `eurekaclaw/agents/base.py`**

Remove the tenacity import (lines 9-10):
```python
# DELETE these lines:
from tenacity import stop_after_attempt, wait_exponential, Retrying
from tenacity.asyncio import AsyncRetrying
```

Replace `_call_model` method (lines 274-305) with:
```python
    async def _call_model(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
    ) -> NormalizedMessage:
        """Call the LLM. Retry logic lives in LLMClient — no double-wrapping here."""
        from eurekaclaw.config import settings
        _max_tokens = max_tokens if max_tokens is not None else settings.max_tokens_agent
        try:
            return await self.client.messages.create(
                model=settings.active_model,
                max_tokens=_max_tokens,
                system=system,
                messages=messages,
                tools=tools or None,
            )
        except Exception as e:
            logger.error(
                "LLM call failed (model=%s): %s: %s",
                settings.active_model, type(e).__name__, e,
            )
            raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_retry_single_layer.py -v`
Expected: Both tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/agents/base.py tests/test_retry_single_layer.py
git commit -m "fix: remove tenacity double-retry from BaseAgent — single retry layer in LLMClient"
```

---

### Task 4: Add ccproxy Health Monitoring + Auto-Restart

**Files:**
- Modify: `eurekaclaw/ccproxy_manager.py`

- [ ] **Step 1: Add `CcproxyMonitor` class after `stop_ccproxy`**

```python
class CcproxyMonitor:
    """Background monitor that checks ccproxy health and restarts on crash."""

    def __init__(self, port: int, check_interval: float = 30.0) -> None:
        self._port = port
        self._check_interval = check_interval
        self._proc: subprocess.Popen | None = None
        self._task: asyncio.Task | None = None
        self._restart_count = 0
        self._max_restarts = 5

    def start(self, proc: subprocess.Popen | None) -> None:
        """Begin monitoring. Call after ensure_ccproxy()."""
        self._proc = proc
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._monitor_loop())
        except RuntimeError:
            # No running loop — skip async monitoring (e.g. in tests)
            pass

    async def _monitor_loop(self) -> None:
        """Periodically check ccproxy health, restart if dead."""
        import asyncio
        while True:
            await asyncio.sleep(self._check_interval)
            if not is_ccproxy_running(self._port):
                if self._restart_count >= self._max_restarts:
                    logger.error(
                        "ccproxy has crashed %d times — giving up on auto-restart",
                        self._restart_count,
                    )
                    break
                logger.warning("ccproxy is down — attempting restart (%d/%d)",
                               self._restart_count + 1, self._max_restarts)
                try:
                    self._proc = start_ccproxy(self._port)
                    setup_ccproxy_env(self._port)
                    self._restart_count += 1
                    logger.info("ccproxy restarted successfully on port %d", self._port)
                except Exception as e:
                    logger.error("ccproxy restart failed: %s", e)
                    self._restart_count += 1

    def stop(self) -> None:
        """Cancel the monitor and stop ccproxy."""
        if self._task and not self._task.done():
            self._task.cancel()
        stop_ccproxy(self._proc)
```

- [ ] **Step 2: Update `maybe_start_ccproxy` to return a monitor**

Add to end of `maybe_start_ccproxy()`, before `return proc`:
```python
    # Start health monitor
    monitor = CcproxyMonitor(port)
    monitor.start(proc)
    return proc, monitor
```

Update return type annotation to `tuple[subprocess.Popen | None, CcproxyMonitor | None]`.

Note: cli.py callers need updating to unpack the tuple. The monitor's `stop()` replaces `stop_ccproxy(proc)` in atexit.

- [ ] **Step 3: Run existing tests**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/ -v -x --timeout=30 2>&1 | head -40`

- [ ] **Step 4: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/ccproxy_manager.py
git commit -m "feat: add ccproxy health monitor with auto-restart on crash"
```

---

### Task 5: Incremental Bus Persistence

**Files:**
- Modify: `eurekaclaw/knowledge_bus/bus.py`
- Test: `tests/test_incremental_persist.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_incremental_persist.py
"""Tests for incremental bus persistence."""
import json
import pytest
from pathlib import Path
from eurekaclaw.knowledge_bus.bus import KnowledgeBus


@pytest.fixture
def bus(tmp_path):
    b = KnowledgeBus("test-session-123")
    b._session_dir = tmp_path / "sessions" / "test-session-123"
    return b


def test_persist_incremental_creates_dir(bus):
    bus.put("test_key", {"hello": "world"})
    bus.persist_incremental()
    assert bus._session_dir.exists()


def test_persist_incremental_writes_artifacts(bus):
    bus.put("test_key", {"hello": "world"})
    bus.persist_incremental()
    path = bus._session_dir / "test_key.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["hello"] == "world"


def test_persist_incremental_writes_stage_marker(bus):
    bus.persist_incremental(completed_stage="survey")
    marker = bus._session_dir / "_stage_progress.json"
    assert marker.exists()
    data = json.loads(marker.read_text())
    assert "survey" in data["completed_stages"]


def test_persist_incremental_accumulates_stages(bus):
    bus.persist_incremental(completed_stage="survey")
    bus.persist_incremental(completed_stage="ideation")
    marker = bus._session_dir / "_stage_progress.json"
    data = json.loads(marker.read_text())
    assert data["completed_stages"] == ["survey", "ideation"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_incremental_persist.py -v`
Expected: FAIL — `persist_incremental` doesn't exist

- [ ] **Step 3: Implement `persist_incremental` in `bus.py`**

Add `_session_dir` to `__init__`:
```python
def __init__(self, session_id: str) -> None:
    self.session_id = session_id
    self._store: dict[str, Any] = {}
    self._subscribers: dict[str, list[Callable]] = defaultdict(list)
    self._session_dir: Path | None = None
    self._completed_stages: list[str] = []
```

Add method after `persist()`:
```python
def persist_incremental(self, completed_stage: str | None = None) -> None:
    """Write current bus state to disk incrementally.

    Called after each pipeline stage to ensure partial work survives crashes.
    """
    if self._session_dir is None:
        from eurekaclaw.config import settings
        self._session_dir = settings.runs_dir / self.session_id

    self._session_dir.mkdir(parents=True, exist_ok=True)

    # Write all current artifacts
    for key, value in self._store.items():
        path = self._session_dir / f"{key}.json"
        if hasattr(value, "model_dump_json"):
            path.write_text(value.model_dump_json(indent=2), encoding="utf-8")
        else:
            path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")

    # Track stage progress
    if completed_stage and completed_stage not in self._completed_stages:
        self._completed_stages.append(completed_stage)

    marker = self._session_dir / "_stage_progress.json"
    marker.write_text(json.dumps({
        "session_id": self.session_id,
        "completed_stages": self._completed_stages,
    }, indent=2), encoding="utf-8")

    logger.debug("Incremental persist: %d artifacts, stages=%s",
                 len(self._store), self._completed_stages)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_incremental_persist.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/knowledge_bus/bus.py tests/test_incremental_persist.py
git commit -m "feat: add incremental bus persistence after each stage"
```

---

### Task 6: Wire Incremental Persistence into MetaOrchestrator

**Files:**
- Modify: `eurekaclaw/orchestrator/meta_orchestrator.py`

- [ ] **Step 1: Add `bus.persist_incremental()` after each completed task**

In `meta_orchestrator.py`, after the success block (after line 208 `self.bus.put_pipeline(pipeline)`), add:
```python
            # Persist state after each stage so crashes don't lose work
            if result and not result.failed:
                self.bus.persist_incremental(completed_stage=task.name)
```

Also, at session start (after line 112 `self.bus.put_pipeline(pipeline)`), set the session dir:
```python
        self.bus._session_dir = settings.runs_dir / brief.session_id
```

- [ ] **Step 2: Stop pipeline on critical failures**

In the failure block (around line 189), after max retries exhausted, add:
```python
                    if result.failed:
                        task.mark_failed(result.error)
                        # Persist partial state before potentially stopping
                        self.bus.persist_incremental(completed_stage=f"{task.name}_FAILED")
                        # If survey or ideation fails, don't run downstream
                        if task.name in ("survey", "ideation"):
                            console.print(f"[red]Critical stage '{task.name}' failed — stopping pipeline.[/red]")
                            console.print(f"[yellow]Partial results saved to {settings.runs_dir / brief.session_id}[/yellow]")
                            break
```

- [ ] **Step 3: Run existing tests**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/ -v -x --timeout=30 2>&1 | head -40`

- [ ] **Step 4: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/orchestrator/meta_orchestrator.py
git commit -m "feat: wire incremental persistence into pipeline, stop on critical failures"
```

---

### Task 7: Full-Pipeline Session Checkpoint + Resume

**Files:**
- Create: `eurekaclaw/orchestrator/session_checkpoint.py`
- Modify: `eurekaclaw/cli.py`
- Test: `tests/test_session_checkpoint.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_session_checkpoint.py
"""Tests for full-pipeline session checkpoint."""
import json
import pytest
from pathlib import Path
from eurekaclaw.orchestrator.session_checkpoint import SessionCheckpoint


@pytest.fixture
def cp(tmp_path, monkeypatch):
    monkeypatch.setattr("eurekaclaw.config.settings.eurekaclaw_dir", tmp_path)
    return SessionCheckpoint("test-session-456")


def test_detect_last_stage_from_marker(cp, tmp_path):
    runs_dir = tmp_path / "runs" / "test-session-456"
    runs_dir.mkdir(parents=True)
    marker = runs_dir / "_stage_progress.json"
    marker.write_text(json.dumps({
        "session_id": "test-session-456",
        "completed_stages": ["survey", "ideation"],
    }))
    last, stages = cp.detect_progress()
    assert last == "ideation"
    assert stages == ["survey", "ideation"]


def test_detect_no_progress(cp):
    last, stages = cp.detect_progress()
    assert last is None
    assert stages == []


def test_next_stage_after_survey(cp):
    assert cp.next_stage_after("survey") == "ideation"


def test_next_stage_after_ideation(cp):
    assert cp.next_stage_after("ideation") == "theory"


def test_next_stage_after_last(cp):
    assert cp.next_stage_after("writer") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_session_checkpoint.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Write the implementation**

```python
# eurekaclaw/orchestrator/session_checkpoint.py
"""Full-pipeline session checkpoint — detects progress and enables resume from any stage."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from eurekaclaw.config import settings

logger = logging.getLogger(__name__)

# Pipeline stage order — must match default_pipeline.yaml
STAGE_ORDER = [
    "survey",
    "ideation",
    "direction_selection_gate",
    "theory",
    "theory_review_gate",
    "experiment",
    "writer",
]


class SessionCheckpoint:
    """Manages full-pipeline progress detection and resume logic."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._runs_dir = settings.runs_dir / session_id

    def detect_progress(self) -> tuple[str | None, list[str]]:
        """Detect how far a session got before it stopped.

        Returns:
            (last_completed_stage, list_of_completed_stages)
        """
        marker = self._runs_dir / "_stage_progress.json"
        if not marker.exists():
            return None, []

        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
            stages = data.get("completed_stages", [])
            last = stages[-1] if stages else None
            return last, stages
        except (json.JSONDecodeError, KeyError):
            return None, []

    def next_stage_after(self, stage_name: str) -> str | None:
        """Return the stage that should run after the given stage."""
        try:
            idx = STAGE_ORDER.index(stage_name)
            if idx + 1 < len(STAGE_ORDER):
                return STAGE_ORDER[idx + 1]
        except ValueError:
            pass
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/test_session_checkpoint.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Update `eurekaclaw/cli.py` resume command**

Find the existing `resume` command and add a fallback when theory checkpoint doesn't exist:

After the existing "No checkpoint found" error, add:
```python
    # Fallback: check for pipeline-level checkpoint
    from eurekaclaw.orchestrator.session_checkpoint import SessionCheckpoint
    scp = SessionCheckpoint(session_id)
    last_stage, completed = scp.detect_progress()

    if last_stage:
        next_stage = scp.next_stage_after(last_stage)
        console.print(f"[green]Found pipeline checkpoint: completed stages = {completed}[/green]")
        if next_stage:
            console.print(f"[blue]Resuming from stage: {next_stage}[/blue]")
            # Load bus from persisted state and re-run pipeline from next_stage
            from eurekaclaw.knowledge_bus.bus import KnowledgeBus
            bus = KnowledgeBus.load(session_id, settings.runs_dir / session_id)
            # ... continue pipeline from next_stage
        else:
            console.print("[green]Session was fully complete.[/green]")
        return

    console.print(f"\n[red]No checkpoint found for session '{session_id}'.[/red]")
    console.print(f"Expected location: {cp.checkpoint_path}")
```

- [ ] **Step 6: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/orchestrator/session_checkpoint.py tests/test_session_checkpoint.py eurekaclaw/cli.py
git commit -m "feat: add full-pipeline session checkpoint with resume from any stage"
```

---

### Task 8: Fix Silent JSON Parse Failures in Survey Agent

**Files:**
- Modify: `eurekaclaw/agents/survey/agent.py`

- [ ] **Step 1: Replace silent `pass` blocks in `_parse_survey_output`**

Replace lines 168-192 of `survey/agent.py` with:
```python
    def _parse_survey_output(self, text: str) -> dict:
        """Try to extract JSON from the agent's text output."""
        # Try ```json block first
        if "```json" in text:
            try:
                start = text.index("```json") + 7
                end = text.index("```", start)
                return json.loads(text[start:end].strip())
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Failed to parse ```json block: %s", e)

        # Try raw JSON object
        if "{" in text and "}" in text:
            try:
                start = text.index("{")
                end = text.rindex("}") + 1
                return json.loads(text[start:end])
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Failed to parse raw JSON from survey output: %s", e)

        # Fallback: return empty structure with warning
        logger.warning(
            "Survey output contained no parseable JSON — returning empty structure. "
            "Output preview: %s",
            text[:200],
        )
        return {
            "papers": [],
            "open_problems": [],
            "key_mathematical_objects": [],
            "research_frontier": text[:1000],
            "insights": [],
        }
```

- [ ] **Step 2: Run existing tests**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/ -v -x --timeout=30 2>&1 | head -40`

- [ ] **Step 3: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/agents/survey/agent.py
git commit -m "fix: log survey JSON parse failures instead of silently swallowing"
```

---

### Task 9: Structured Tool Error Returns

**Files:**
- Modify: `eurekaclaw/tools/registry.py`

- [ ] **Step 1: Replace error string with structured JSON in `call()`**

Replace lines 38-46 of `tools/registry.py` with:
```python
    async def call(self, name: str, inputs: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"error": True, "type": "unknown_tool", "message": f"Unknown tool '{name}'"})
        try:
            return await tool.call(**inputs)
        except Exception as e:
            logger.exception("Tool %s failed", name)
            return json.dumps({
                "error": True,
                "type": type(e).__name__,
                "message": str(e),
                "tool": name,
            })
```

Add `import json` at top of file.

- [ ] **Step 2: Run existing tests**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/ -v -x --timeout=30 2>&1 | head -40`

- [ ] **Step 3: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/tools/registry.py
git commit -m "fix: return structured JSON errors from tool registry instead of plain strings"
```

---

### Task 10: Token Waste Tracking

**Files:**
- Modify: `eurekaclaw/llm/base.py` (already has `_WASTED_TOKENS` from Task 2)
- Modify: `eurekaclaw/orchestrator/meta_orchestrator.py`

- [ ] **Step 1: Log token waste at session end**

In `meta_orchestrator.py`, in the `run()` method, before the final output section (around line 214), add:
```python
        from eurekaclaw.llm.base import get_global_tokens, get_wasted_tokens
        total = get_global_tokens()
        wasted = get_wasted_tokens()
        console.print(f"\n[dim]Token usage — input: {total['input']:,}, output: {total['output']:,}[/dim]")
        if wasted['input'] > 0 or wasted['output'] > 0:
            console.print(f"[dim]Tokens wasted on failed retries — input: {wasted['input']:,}, output: {wasted['output']:,}[/dim]")
```

- [ ] **Step 2: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/orchestrator/meta_orchestrator.py
git commit -m "feat: log token usage and waste at session end"
```

---

### Task 11: Gemini Parallel Search Tool

**Files:**
- Create: `eurekaclaw/tools/gemini_search.py`
- Modify: `eurekaclaw/config.py`
- Modify: `eurekaclaw/tools/registry.py`
- Modify: `eurekaclaw/agents/survey/agent.py`

- [ ] **Step 1: Add Gemini config to `eurekaclaw/config.py`**

Add after the `s2_api_key` field (line 53):
```python
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
```

- [ ] **Step 2: Create the Gemini search tool**

```python
# eurekaclaw/tools/gemini_search.py
"""Gemini-powered web + academic search — runs in parallel with arXiv/S2 for broader coverage."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from eurekaclaw.config import settings
from eurekaclaw.tools.base import BaseTool

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


class GeminiSearchTool(BaseTool):
    name = "gemini_search"
    description = (
        "Use Google Gemini with grounding to search the web for academic papers, "
        "recent research, and supplementary material. Provides broader coverage "
        "than arXiv alone — especially for interdisciplinary topics, non-arXiv venues, "
        "and very recent work. Returns structured results with titles, snippets, and URLs."
    )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Research-focused search query. Be specific and academic.",
                },
                "focus": {
                    "type": "string",
                    "enum": ["papers", "definitions", "recent_advances", "open_problems"],
                    "default": "papers",
                    "description": "What kind of results to prioritize.",
                },
            },
            "required": ["query"],
        }

    async def call(self, query: str, focus: str = "papers") -> str:
        if not settings.gemini_api_key:
            return json.dumps({"error": "GEMINI_API_KEY not configured."})

        focus_instructions = {
            "papers": "Find academic papers, their authors, publication venues, and key results.",
            "definitions": "Find formal mathematical definitions and key theorems related to the query.",
            "recent_advances": "Find the most recent research advances and breakthroughs.",
            "open_problems": "Find open problems, conjectures, and unsolved questions.",
        }

        prompt = (
            f"You are an academic research assistant. Search for: {query}\n\n"
            f"Focus: {focus_instructions.get(focus, focus_instructions['papers'])}\n\n"
            "Return a JSON array of results. Each result should have:\n"
            '- "title": paper/resource title\n'
            '- "authors": list of author names (if available)\n'
            '- "year": publication year (if available)\n'
            '- "url": source URL\n'
            '- "snippet": 1-2 sentence summary of the key finding\n'
            '- "venue": publication venue (if available)\n'
            "Return 5-10 results. Output ONLY the JSON array, no other text."
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{GEMINI_API_URL}?key={settings.gemini_api_key}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "tools": [{"google_search": {}}],
                        "generationConfig": {
                            "temperature": 0.1,
                            "maxOutputTokens": 4096,
                        },
                    },
                )
                r.raise_for_status()
                data = r.json()

            # Extract text from Gemini response
            candidates = data.get("candidates", [])
            if not candidates:
                return json.dumps({"error": "No response from Gemini"})

            text = ""
            for part in candidates[0].get("content", {}).get("parts", []):
                if "text" in part:
                    text += part["text"]

            # Also extract grounding metadata if available
            grounding = candidates[0].get("groundingMetadata", {})
            search_results = grounding.get("searchEntryPoint", {})
            web_results = grounding.get("groundingChunks", [])

            # Try to parse the LLM's JSON output
            results = self._parse_results(text)

            # Supplement with grounding chunks if LLM output was sparse
            if len(results) < 3 and web_results:
                for chunk in web_results[:5]:
                    web = chunk.get("web", {})
                    if web:
                        results.append({
                            "title": web.get("title", ""),
                            "url": web.get("uri", ""),
                            "snippet": web.get("title", ""),
                        })

            return json.dumps(results[:10], indent=2)
        except httpx.HTTPStatusError as e:
            logger.warning("Gemini search API error %d: %s", e.response.status_code, e.response.text[:200])
            return json.dumps({"error": f"Gemini API error: {e.response.status_code}"})
        except Exception as e:
            logger.exception("Gemini search failed")
            return json.dumps({"error": str(e)})

    def _parse_results(self, text: str) -> list[dict]:
        """Extract JSON array from Gemini's text output."""
        # Try direct JSON parse
        text = text.strip()
        if text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # Try ```json block
        if "```json" in text:
            try:
                start = text.index("```json") + 7
                end = text.index("```", start)
                return json.loads(text[start:end].strip())
            except (json.JSONDecodeError, ValueError):
                pass

        # Try finding [ ... ]
        if "[" in text and "]" in text:
            try:
                start = text.index("[")
                end = text.rindex("]") + 1
                return json.loads(text[start:end])
            except (json.JSONDecodeError, ValueError):
                pass

        logger.warning("Could not parse Gemini search results as JSON")
        return []
```

- [ ] **Step 3: Register the tool in `eurekaclaw/tools/registry.py`**

Add to imports in `build_default_registry()`:
```python
    from eurekaclaw.tools.gemini_search import GeminiSearchTool
```

Add to the tool list:
```python
        GeminiSearchTool(),
```

- [ ] **Step 4: Add `gemini_search` to SurveyAgent's tool list**

In `eurekaclaw/agents/survey/agent.py`, update `get_tool_names()`:
```python
    def get_tool_names(self) -> list[str]:
        tools = ["arxiv_search", "semantic_scholar_search", "web_search", "citation_manager"]
        from eurekaclaw.config import settings
        if settings.gemini_api_key:
            tools.append("gemini_search")
        return tools
```

Update the system prompt to mention the Gemini tool when available:
```python
    def _role_system_prompt(self, task: Task) -> str:
        from eurekaclaw.config import settings
        gemini_hint = ""
        if settings.gemini_api_key:
            gemini_hint = (
                "\nYou also have gemini_search for broader web + academic search. "
                "Run it IN PARALLEL with arXiv searches (use both tools in the same turn) "
                "to maximize coverage — especially for interdisciplinary topics.\n"
            )
        return f"""\
You are the Survey Agent of EurekaClaw. Your job: fast, focused literature search.

Do 2-3 targeted arXiv searches, then synthesize. Be concise.
{gemini_hint}
Output a JSON object with keys:
- papers: top 5-8 most relevant papers (title, authors, year, arxiv_id, abstract 1 sentence)
- open_problems: 3-5 open questions from the literature
- key_mathematical_objects: core definitions/theorems (bullet list)
- research_frontier: 2-3 sentences on active directions
- insights: 2-3 key takeaways
"""
```

- [ ] **Step 5: Add `GEMINI_API_KEY` to `.env.example`**

Add after the `S2_API_KEY` line:
```
# Google Gemini (optional — parallel search for broader coverage)
GEMINI_API_KEY=
```

- [ ] **Step 6: Commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add eurekaclaw/tools/gemini_search.py eurekaclaw/config.py eurekaclaw/tools/registry.py eurekaclaw/agents/survey/agent.py .env.example
git commit -m "feat: add Gemini parallel search tool for broader academic coverage"
```

---

### Task 12: Final Integration Test

- [ ] **Step 1: Run all tests**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/pytest tests/ -v --timeout=30`
Expected: All tests PASS

- [ ] **Step 2: Verify imports work end-to-end**

Run: `cd /Users/lor/_coding/EurekaClaw && .venv/bin/python -c "from eurekaclaw.cli import main; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Final commit**

```bash
cd /Users/lor/_coding/EurekaClaw && git add -A
git commit -m "chore: resilience overhaul complete — error classification, circuit breaker, incremental checkpoints, structured errors"
```
