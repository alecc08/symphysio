"""Runtime configuration, read from environment variables only.

No secrets are hard-coded; the app refuses to run in "secure" mode over plain
HTTP unless the operator opts in explicitly (see `cookie_secure`).
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    mail_backend: str
    resend_api_key: str | None
    email_from: str | None
    email_reply_to: str | None
    public_url: str | None
    email_verification_ttl_seconds: int
    email_sends_per_hour: int
    password_reset_ttl_seconds: int
    email_confirmation: str  # "off" | "optional" | "required"
    allow_registration: bool = True  # keyword default: see get_settings
    trusted_proxies: tuple[str, ...] = ()  # CIDRs of *your* proxy, never a client
    # The zone for accounts that never chose one. Empty or unset means UTC, which
    # is what the app did before this setting existed. One server usually has one
    # country, so a deployment can say "the people on this host are in Montreal"
    # without any account having to find the setting.
    default_timezone: str = "UTC"  # keyword default: see get_settings

    @property
    def session_cookie(self) -> str:
        return "symphysio_session"

    @property
    def csrf_cookie(self) -> str:
        return "symphysio_csrf"

    @property
    def email_enabled(self) -> bool:
        """Email is only usable with a key, a sender and an absolute link host."""
        return bool(self.resend_api_key and self.email_from and self.public_url)

    @property
    def confirmation_enabled(self) -> bool:
        """Whether the confirm-your-email flow runs at all.

        Two ways to be off, and they mean the same thing to the user: the admin
        turned it off, or there is no mail transport to send a link with. Both
        leave accounts born confirmed and no banner in the UI.
        """
        return self.email_confirmation != "off" and self.email_enabled

    @property
    def require_email_verification(self) -> bool:
        """Hard gate: an unconfirmed account may not use its session."""
        return self.email_confirmation == "required"


def _env_url(name: str) -> str | None:
    raw = os.environ.get(name, "").strip().rstrip("/")
    if not raw:
        return None
    if not raw.startswith(("http://", "https://")):
        raise ValueError(f"{name} must be an absolute http(s) URL, got {raw!r}")
    return raw


_EMAIL_MODES = ("off", "optional", "required")


def _env_cidrs(name: str) -> tuple[str, ...]:
    """Parse a comma-separated list of CIDRs/IPs, and refuse a typo out loud.

    A proxy list that silently drops one entry is worse than a crash: the
    limiter would go back to keying on the socket peer (or, if the bad entry was
    a client range, start believing a header again), and nothing would say so.
    """
    raw = os.environ.get(name, "")
    entries = [entry.strip() for entry in raw.replace(",", " ").split() if entry.strip()]
    parsed: list[str] = []
    for entry in entries:
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError as error:
            raise ValueError(
                f"{name} contains {entry!r}, which is not an IP or CIDR ({error})"
            ) from error
        parsed.append(str(network))
    return tuple(parsed)


def _email_confirmation_mode() -> str:
    """How hard the admin wants people to confirm their address.

    - ``off``      — the app never sends a confirmation link and never nags.
    - ``optional`` — a link is sent and a banner reminds; an unconfirmed account
      still works. This is the default.
    - ``required`` — an unconfirmed account cannot use its session. Needs a mail
      transport: ``main.lifespan`` refuses to start without one.
    """
    mode = os.environ.get("SYMPHYSIO_EMAIL_CONFIRMATION", "").strip().lower() or "optional"
    if mode not in _EMAIL_MODES:
        expected = "|".join(_EMAIL_MODES)
        raise ValueError(f"unknown SYMPHYSIO_EMAIL_CONFIRMATION={mode!r}, expected {expected}")
    return mode


def _env_timezone() -> str:
    """An instance-wide default zone, refused out loud if it is not a zone.

    A typo here does not crash anything: it just means every account that never
    picked a zone silently gets UTC, which is the bug the setting exists to fix.
    So it is validated at startup, like ``_env_cidrs`` validates the proxy list.
    """
    raw = os.environ.get("SYMPHYSIO_DEFAULT_TIMEZONE", "").strip()
    if not raw:
        return "UTC"
    try:
        ZoneInfo(raw)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError(
            f"SYMPHYSIO_DEFAULT_TIMEZONE={raw!r} is not an IANA time zone name "
            f"(for example 'America/Toronto'): {error}"
        ) from error
    return raw


#: The namespace was misspelled `SYPHYSIO_*` up to 0.2.0 and the rename has no
#: alias, on purpose — but a silent mismatch is the dangerous direction. With the
#: old names still in the environment, `SYMPHYSIO_DATA_DIR` reads as unset and the
#: app happily opens a **fresh empty database** at its default path while the real
#: one sits unmounted at /data; `SYMPHYSIO_TRUSTED_PROXIES` reads as unset and the
#: login limiter goes back to keying on the proxy (one shared budget);
#: `SYMPHYSIO_ALLOW_REGISTRATION` reads as unset and the door defaults open. So
#: the old spelling is refused out loud instead of being ignored.
_OLD_PREFIX = "SYPHYSIO_"


def _reject_old_prefix() -> None:
    stale = sorted(name for name in os.environ if name.startswith(_OLD_PREFIX))
    if not stale:
        return
    renamed = ", ".join(f"SYMPHYSIO_{name.removeprefix(_OLD_PREFIX)}" for name in stale)
    raise ValueError(
        f"{', '.join(stale)} uses the pre-0.3.0 spelling and is now ignored. "
        f"Rename it to {renamed} before starting: an unset SYMPHYSIO_DATA_DIR "
        "would open a new empty database, an unset SYMPHYSIO_TRUSTED_PROXIES "
        "would give every visitor one rate-limit budget, and an unset "
        "SYMPHYSIO_ALLOW_REGISTRATION would open sign-up."
    )


def get_settings() -> Settings:
    _reject_old_prefix()
    backend_dir = Path(__file__).resolve().parent.parent
    data_dir = Path(os.environ.get("SYMPHYSIO_DATA_DIR", backend_dir / "data")).expanduser()
    static_dir = Path(
        os.environ.get("SYMPHYSIO_STATIC_DIR", backend_dir.parent / "frontend" / "dist")
    ).expanduser()
    ttl_days = _env_int("SYMPHYSIO_SESSION_TTL_DAYS", 30)
    resend_api_key = os.environ.get("RESEND_API_KEY", "").strip() or None
    email_from = os.environ.get("SYMPHYSIO_EMAIL_FROM", "").strip() or None
    public_url = _env_url("SYMPHYSIO_PUBLIC_URL")
    # Explicit wins; otherwise the backend follows whatever the keys allow. Tests
    # force "outbox" so no test can reach the network.
    mail_backend = (
        os.environ.get("SYMPHYSIO_MAIL_BACKEND", "").strip().lower()
        or ("resend" if (resend_api_key and email_from and public_url) else "null")
    )
    if mail_backend not in {"resend", "outbox", "null"}:
        raise ValueError(f"unknown SYMPHYSIO_MAIL_BACKEND={mail_backend!r}")
    return Settings(
        data_dir=data_dir,
        database_path=Path(os.environ.get("SYMPHYSIO_DB_PATH", data_dir / "symphysio.sqlite")),
        migrations_dir=Path(os.environ.get("SYMPHYSIO_MIGRATIONS_DIR", backend_dir / "migrations")),
        static_dir=static_dir,
        # Secure cookies are the default; only flip this for local plain-HTTP dev.
        cookie_secure=_env_bool("SYMPHYSIO_COOKIE_SECURE", True),
        session_ttl_seconds=max(3600, ttl_days * 86_400),
        max_body_bytes=_env_int("SYMPHYSIO_MAX_BODY_BYTES", 262_144),
        rate_limit_enabled=_env_bool("SYMPHYSIO_RATE_LIMIT", True),
        rate_limit_attempts=_env_int("SYMPHYSIO_RATE_LIMIT_ATTEMPTS", 10),
        rate_limit_window_seconds=_env_int("SYMPHYSIO_RATE_LIMIT_WINDOW", 900),
        rate_limit_lockout_seconds=_env_int("SYMPHYSIO_RATE_LIMIT_LOCKOUT", 900),
        mail_backend=mail_backend,
        resend_api_key=resend_api_key,
        email_from=email_from,
        email_reply_to=os.environ.get("SYMPHYSIO_EMAIL_REPLY_TO", "").strip() or None,
        public_url=public_url,
        email_verification_ttl_seconds=max(300, _env_int("SYMPHYSIO_EMAIL_TTL_SECONDS", 86_400)),
        email_sends_per_hour=max(1, _env_int("SYMPHYSIO_EMAIL_SENDS_PER_HOUR", 3)),
        # Reset links are short-lived by design: they hand over the ability to set
        # a new password, and unlike a confirmation link there is no "you can keep
        # using the app meanwhile" to fall back on if one leaks.
        password_reset_ttl_seconds=max(300, _env_int("SYMPHYSIO_PASSWORD_RESET_TTL_SECONDS", 1800)),
        email_confirmation=_email_confirmation_mode(),
        # Open by default: the first account has to come from somewhere. A
        # instance that is reachable from the internet should close this once
        # its own accounts exist - see docs/DEPLOYING.md.
        allow_registration=_env_bool("SYMPHYSIO_ALLOW_REGISTRATION", True),
        # The addresses of *your* reverse proxy. Empty (the default) means "no
        # proxy": X-Forwarded-For is ignored entirely and the limiter keys on the
        # socket peer. Set this to the network your proxy actually connects from -
        # behind Traefik that peer is the traefik container, so leaving this empty
        # makes every visitor share one budget, and setting it too wide makes the
        # header believable again.
        trusted_proxies=_env_cidrs("SYMPHYSIO_TRUSTED_PROXIES"),
        default_timezone=_env_timezone(),
    )
