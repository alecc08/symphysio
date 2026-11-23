"""UUIDv7 identifiers (time-ordered, safe for SQLite TEXT primary keys).

Python 3.14 ships :func:`uuid.uuid7`; on 3.12/3.13 we build the same layout by
hand so primary keys stay clustered and index-friendly everywhere.
"""

from __future__ import annotations

import secrets
import time
import uuid

_native_uuid7 = getattr(uuid, "uuid7", None)


def _uuid7_fallback() -> str:
    timestamp_ms = time.time_ns() // 1_000_000
    rand_a = int.from_bytes(secrets.token_bytes(2), "big") & 0x0FFF
    rand_b = int.from_bytes(secrets.token_bytes(8), "big") & ((1 << 62) - 1)
    value = (timestamp_ms & ((1 << 48) - 1)) << 80 | 0x7000 | rand_a << 64 | 0b10 << 62 | rand_b
    return str(uuid.UUID(int=value))


def new_id() -> str:
    """Return a new UUIDv7 string."""
    if _native_uuid7 is not None:
        return str(_native_uuid7())
    return _uuid7_fallback()


def now_utc() -> int:
    """Unix epoch seconds (UTC)."""
    return int(time.time())
