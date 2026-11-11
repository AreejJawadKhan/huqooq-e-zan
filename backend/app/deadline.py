"""A per-request time budget. Without one, a single /api/ask could hold a server thread for minutes: two model calls,
each up to 60 s, a retry after a 429, then a second provider. Every outgoing model call now takes its timeout from
the time that is left, retries are skipped when there is no time for them, and the next provider is not tried when
the budget is spent. The endpoint then answers from the law text alone (Pipeline.ask_degraded) instead of hanging.
"""
from __future__ import annotations

import contextlib
import contextvars
import time
from typing import Optional

MIN_CALL_BUDGET_S = 2.0  # do not start a model call with less time than this left
MAX_CALL_S = 45.0  # one call never waits longer than this, whatever the budget

_DEADLINE: contextvars.ContextVar[Optional[float]] = contextvars.ContextVar("huqooq_deadline", default=None)


@contextlib.contextmanager
def request_deadline(seconds: float):
    token = _DEADLINE.set(time.monotonic() + seconds)
    try:
        yield
    finally:
        _DEADLINE.reset(token)


def time_left() -> Optional[float]:
    """Seconds left in the current request's budget, or None when no budget is set (tests, scripts)."""
    d = _DEADLINE.get()
    return None if d is None else d - time.monotonic()
