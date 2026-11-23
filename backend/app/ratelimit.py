"""In-process sliding-window rate limiting for the auth endpoints.

Deliberately dependency-free and per-process: v1 is documented as a single
uvicorn worker (see docs/DEPLOYING.md). If you ever scale out, swap this for a
shared store rather than running several workers behind a load balancer.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

_MAX_KEYS = 10_000  # memory guard: forget stale keys beyond this


@dataclass
class _Bucket:
    failures: deque[float] = field(default_factory=deque)
    locked_until: float = 0.0


class RateLimiter:
    def __init__(self, attempts: int, window_seconds: int, lockout_seconds: int) -> None:
        self.attempts = max(1, attempts)
        self.window = max(1, window_seconds)
        self.lockout = max(1, lockout_seconds)
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> int:
        """Seconds until ``key`` may try again (0 when the attempt is allowed)."""
        now = time.monotonic()
        with self._lock:
            self._evict_stale(now)
            bucket = self._buckets.get(key)
            if bucket is None:
                return 0
            if bucket.locked_until > now:
                return int(bucket.locked_until - now) + 1
            self._trim(bucket, now)
            if len(bucket.failures) >= self.attempts:
                bucket.locked_until = now + self.lockout
                return self.lockout
            return 0

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._evict_stale(now)
            bucket = self._buckets.setdefault(key, _Bucket())
            self._trim(bucket, now)
            bucket.failures.append(now)

    def record_success(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    def _trim(self, bucket: _Bucket, now: float) -> None:
        cutoff = now - self.window
        while bucket.failures and bucket.failures[0] < cutoff:
            bucket.failures.popleft()

    def _evict_stale(self, now: float) -> None:
        if len(self._buckets) <= _MAX_KEYS:
            return
        cutoff = now - self.window
        stale = [
            key
            for key, bucket in self._buckets.items()
            if bucket.locked_until <= now and (not bucket.failures or bucket.failures[-1] < cutoff)
        ]
        for key in stale:
            self._buckets.pop(key, None)
