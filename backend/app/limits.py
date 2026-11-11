"""Admission control, a small answer cache and client identification for the API.

The free model tiers are the scarcest resource: one burst of requests (or one person spoofing headers) can use up the
quota for everyone. So the app (1) identifies clients without trusting spoofable headers, (2) caps how many
model-backed requests run at once and per minute across ALL clients, and (3) remembers answers to repeated questions.
When a request is not admitted it is answered from the law text without a model (Pipeline.ask_degraded), not refused.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from typing import Optional

from .schemas import AskResponse


def client_ip(forwarded_for: str, peer: str, trusted_hops: int) -> str:
    """The address to rate-limit on. X-Forwarded-For is client-controlled except for the entries our own proxies add,
    so it is only used when TRUSTED_PROXY_HOPS says how many proxies are in front of the app, and then the entry that
    the outermost trusted proxy appended is taken (index -hops). Anything the client prepended is ignored."""
    if trusted_hops > 0:
        parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
        if len(parts) >= trusted_hops:
            return parts[-trusted_hops]
    return peer or "unknown"


class Admission:
    """At most `max_inflight` model-backed requests at once and `global_rpm` per minute, for everyone together."""

    def __init__(self, max_inflight: int, global_rpm: int):
        self._sem = threading.BoundedSemaphore(max(1, max_inflight))
        self._global_rpm = global_rpm
        self._times: deque[float] = deque()
        self._lock = threading.Lock()

    def enter(self) -> bool:
        now = time.monotonic()
        with self._lock:
            while self._times and now - self._times[0] > 60:
                self._times.popleft()
            if self._global_rpm > 0 and len(self._times) >= self._global_rpm:
                return False
            if not self._sem.acquire(blocking=False):
                return False
            self._times.append(now)
            return True

    def leave(self) -> None:
        self._sem.release()


class AnswerCache:
    """LRU with a time limit for answers to repeated questions.

    Only status "answered" is stored: those passed citation validation. "not_found" and "out_of_scope" can be a model's
    one-off misjudgement (a rate-limited fallback model once answered "not found" to a question that is answered fine a
    minute later), and caching one would repeat the mistake for everyone for the whole TTL. Danger and degraded
    (no-model) answers are never stored either."""

    CACHEABLE = ("answered",)

    def __init__(self, ttl_s: float, max_size: int):
        self._ttl = ttl_s
        self._max = max_size
        self._data: OrderedDict[str, tuple[float, AskResponse]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[AskResponse]:
        if self._ttl <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            stored_at, res = item
            if now - stored_at > self._ttl:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return res.model_copy(deep=True)

    def put(self, key: str, res: AskResponse) -> None:
        if self._ttl <= 0 or res.status not in self.CACHEABLE:
            return
        with self._lock:
            self._data[key] = (time.monotonic(), res.model_copy(deep=True))
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def __len__(self) -> int:
        return len(self._data)
