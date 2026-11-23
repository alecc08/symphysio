"""Runtime configuration, read from environment variables only.

No secrets are hard-coded; the app refuses to run in "secure" mode over plain
HTTP unless the operator opts in explicitly (see `cookie_secure`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_TRUTHY = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in _TRUTHY


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of process configuration."""

    data_dir: Path
    database_path: Path
    migrations_dir: Path
    static_dir: Path
    cookie_secure: bool
    session_ttl_seconds: int
    max_body_bytes: int
    rate_limit_enabled: bool
    rate_limit_attempts: int
    rate_limit_window_seconds: int
    rate_limit_lockout_seconds: int

    @property
    def session_cookie(self) -> str:
        return "symphysio_session"

    @property
    def csrf_cookie(self) -> str:
        return "symphysio_csrf"


def get_settings() -> Settings:
    backend_dir = Path(__file__).resolve().parent.parent
    data_dir = Path(os.environ.get("SYPHYSIO_DATA_DIR", backend_dir / "data")).expanduser()
    static_dir = Path(
        os.environ.get("SYPHYSIO_STATIC_DIR", backend_dir.parent / "frontend" / "dist")
    ).expanduser()
    ttl_days = _env_int("SYPHYSIO_SESSION_TTL_DAYS", 30)
    return Settings(
        data_dir=data_dir,
        database_path=Path(os.environ.get("SYPHYSIO_DB_PATH", data_dir / "symphysio.sqlite")),
        migrations_dir=Path(os.environ.get("SYPHYSIO_MIGRATIONS_DIR", backend_dir / "migrations")),
        static_dir=static_dir,
        # Secure cookies are the default; only flip this for local plain-HTTP dev.
        cookie_secure=_env_bool("SYPHYSIO_COOKIE_SECURE", True),
        session_ttl_seconds=max(3600, ttl_days * 86_400),
        max_body_bytes=_env_int("SYPHYSIO_MAX_BODY_BYTES", 262_144),
        rate_limit_enabled=_env_bool("SYPHYSIO_RATE_LIMIT", True),
        rate_limit_attempts=_env_int("SYPHYSIO_RATE_LIMIT_ATTEMPTS", 10),
        rate_limit_window_seconds=_env_int("SYPHYSIO_RATE_LIMIT_WINDOW", 900),
        rate_limit_lockout_seconds=_env_int("SYPHYSIO_RATE_LIMIT_LOCKOUT", 900),
    )
