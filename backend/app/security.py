"""Password hashing, opaque cookie sessions and CSRF plumbing.

Sessions are 256-bit opaque tokens; only their SHA-256 digest is stored, so a
database leak never yields a usable credential. Cookies are ``HttpOnly``,
``Secure`` and ``SameSite=Lax`` — tokens are never placed in localStorage.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Any

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Response

from .db import Database
from .i18n import DEFAULT_LOCALE
from .ids import new_id, now_utc
from .settings import Settings

# Argon2id with OWASP-aligned parameters: 64 MiB memory, 3 passes, 4 lanes.
password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)

MAX_PASSWORD_BYTES = 1024  # argon2-cffi rejects oversized inputs; cap early instead.


def hash_password(password: str) -> str:
    return password_hasher.hash(password[:MAX_PASSWORD_BYTES])


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password[:MAX_PASSWORD_BYTES])
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def token_digest(token: str) -> str:
    """SHA-256 hex of the cookie token (what we actually store)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits of entropy


@dataclass(frozen=True)
class Authenticated:
    user: dict[str, Any]
    token: str
    expires_at_utc: int
    renewed: bool


async def create_session(db: Database, user_id: str, settings: Settings) -> tuple[str, int]:
    token = new_token()
    expires_at = now_utc() + settings.session_ttl_seconds
    await db.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at_utc, created_at_utc)"
        " VALUES (?, ?, ?, ?)",
        (token_digest(token), user_id, expires_at, now_utc()),
    )
    return token, expires_at


async def authenticate(db: Database, settings: Settings, token: str | None) -> Authenticated | None:
    """Look up a live session and roll its expiry forward when half elapsed."""
    if not token:
        return None
    digest = token_digest(token)
    row = await db.row(
        "SELECT s.expires_at_utc, u.id, u.email, u.created_at_utc, u.is_verified, u.profile_key,"
        " u.locale, u.timezone"
        " FROM sessions s JOIN users u ON u.id = s.user_id"
        " WHERE s.token_hash = ? AND s.expires_at_utc > ?",
        (digest, now_utc()),
    )
    if row is None:
        return None
    renewed = False
    expires_at = int(row["expires_at_utc"])
    half_life = settings.session_ttl_seconds // 2
    if expires_at - now_utc() < half_life:
        expires_at = now_utc() + settings.session_ttl_seconds
        await db.execute(
            "UPDATE sessions SET expires_at_utc = ? WHERE token_hash = ?",
            (expires_at, digest),
        )
        renewed = True
    user = {
        "id": row["id"],
        "email": row["email"],
        "created_at_utc": row["created_at_utc"],
        "is_verified": bool(row["is_verified"]),
        # The set this account started from. Cheap to carry (the join already
        # touches users) and it is what makes the insights copy say "your
        # postnatal set" instead of guessing from row counts.
        "profile_key": str(row["profile_key"]),
        # Carried for the same reason: every response that says something in
        # words, and every local-day bucket, needs the account's own answers
        # rather than a guess from headers or from the newest row's offset.
        "locale": str(row["locale"]),
        "timezone": row["timezone"],
    }
    return Authenticated(user=user, token=token, expires_at_utc=expires_at, renewed=renewed)


async def revoke_session(db: Database, token: str | None) -> int:
    if not token:
        return 0
    return await db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_digest(token),))


async def revoke_all_sessions(db: Database, user_id: str) -> int:
    return await db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


# -- cookies ---------------------------------------------------------------


def set_session_cookies(
    response: Response, settings: Settings, token: str, expires_at: int
) -> None:
    max_age = max(0, expires_at - now_utc())
    response.set_cookie(
        key=settings.session_cookie,
        value=token,
        max_age=max_age,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    response.set_cookie(
        key=settings.csrf_cookie,
        value=new_token(),
        max_age=max_age,
        path="/",
        httponly=False,  # readable by the SPA for the double-submit header
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    for key, http_only in ((settings.session_cookie, True), (settings.csrf_cookie, False)):
        response.delete_cookie(
            key=key,
            path="/",
            httponly=http_only,
            secure=settings.cookie_secure,
            samesite="lax",
        )


def csrf_matches(header_value: str | None, cookie_value: str | None) -> bool:
    """Double-submit check: ``X-CSRF-Token`` header must equal the CSRF cookie."""
    if not header_value or not cookie_value:
        return False
    return hmac.compare_digest(header_value, cookie_value)


def new_csrf_token() -> str:
    return new_token()


def user_public(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "created_at_utc": user["created_at_utc"],
        "is_verified": bool(user.get("is_verified", True)),
        # Same two answers as everywhere else: a payload that describes the
        # account should not describe it in one language and omit the other.
        "locale": user.get("locale", DEFAULT_LOCALE),
        "timezone": user.get("timezone"),
    }


__all__ = [
    "Authenticated",
    "authenticate",
    "clear_session_cookies",
    "create_session",
    "csrf_matches",
    "hash_password",
    "new_csrf_token",
    "new_id",
    "password_needs_rehash",
    "revoke_all_sessions",
    "revoke_session",
    "set_session_cookies",
    "token_digest",
    "user_public",
    "verify_password",
]
