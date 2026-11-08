from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque
from threading import Lock


class FixedWindowRateLimiter:
    """Small in-memory limiter for a single API process.

    Production deployment should replace this with a shared store such as Redis.
    """

    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window_seconds:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


def resolve_api_key_owner(api_key: str | None, configured_keys: tuple[tuple[str, str], ...]) -> str | None:
    """Return a configured owner only when a key matches in constant time."""
    if not api_key:
        return None
    for configured_key, owner_id in configured_keys:
        if hmac.compare_digest(api_key, configured_key):
            return owner_id
    return None
