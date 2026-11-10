"""Small process-local sliding-window limits for single-instance deployments.

The project has no PostgreSQL rate-limit table, and the API must not require
Redis. These limits intentionally reset on restart and are not shared across
multiple workers; callers should not present them as distributed guarantees.
"""

import math
import threading
import time
from collections import deque

_HITS: dict[str, deque[float]] = {}
_LOCK = threading.Lock()
_MAX_KEYS = 10_000


def check_rate_limit(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Record a hit and return ``(allowed, retry_after_seconds)``."""
    now = time.monotonic()
    cutoff = now - window_seconds
    with _LOCK:
        hits = _HITS.setdefault(key, deque())
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= limit:
            return False, max(1, math.ceil(window_seconds - (now - hits[0])))
        hits.append(now)

        if len(_HITS) > _MAX_KEYS:
            for existing_key, existing_hits in list(_HITS.items()):
                while existing_hits and existing_hits[0] <= cutoff:
                    existing_hits.popleft()
                if not existing_hits:
                    _HITS.pop(existing_key, None)
            while len(_HITS) > _MAX_KEYS:
                _HITS.pop(next(iter(_HITS)))
    return True, 0


def reset_rate_limits() -> None:
    """Clear volatile state; intended for deterministic unit tests."""
    with _LOCK:
        _HITS.clear()
