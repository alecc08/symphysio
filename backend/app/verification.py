"""Single-use, expiring tokens for email confirmation (and later password resets).

Mirror image of the session design in `security.py`: the caller gets a 256-bit
random token, the database only ever sees ``sha256(token)``.

Because the row is found *by* digest, a wrong guess never touches any row at all —
so there is no per-token guess budget to burn. Guessing is stopped by the IP rate
limiter in the router, and the send budget here is enforced per account against
the database so it survives a restart.
"""

from __future__ import annotations

from enum import StrEnum

from .db import Database
from .ids import new_id, now_utc
from .security import new_token, token_digest

CONFIRM_EMAIL = "confirm_email"
PASSWORD_RESET = "password_reset"  # a purpose tag, not a secret  # noqa: S105
MAX_TOKEN_CHARS = 512


class VerifyOutcome(StrEnum):
    OK = "ok"
    INVALID = "invalid"  # unknown token or wrong purpose
    EXPIRED = "expired"
    USED = "used"


async def create_verification(
    db: Database, user_id: str, purpose: str, ttl_seconds: int
) -> str:
    """Issue a fresh token, superseding any outstanding one for the same purpose.

    Resending therefore cannot leave two live links in two inboxes. The old row is
    expired rather than deleted, so it still counts against the per-hour budget.
    """
    await db.execute(
        "UPDATE email_verifications SET expires_at_utc = ?"
        " WHERE user_id = ? AND purpose = ? AND used_at_utc IS NULL",
        (now_utc(), user_id, purpose),
    )
    token = new_token()
    created = now_utc()
    await db.execute(
        "INSERT INTO email_verifications"
        " (id, user_id, token_hash, purpose, created_at_utc, expires_at_utc)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (new_id(), user_id, token_digest(token), purpose, created, created + ttl_seconds),
    )
    return token


async def consume_verification(db: Database, token: str, purpose: str) -> VerifyOutcome:
    """Validate and consume a token. Successful use is recorded, never reused."""
    if not token or len(token) > MAX_TOKEN_CHARS:
        return VerifyOutcome.INVALID
    row = await db.row(
        "SELECT id, user_id, expires_at_utc, used_at_utc FROM email_verifications"
        " WHERE token_hash = ? AND purpose = ?",
        (token_digest(token), purpose),
    )
    if row is None:
        return VerifyOutcome.INVALID
    if row["used_at_utc"] is not None:
        return VerifyOutcome.USED
    if int(row["expires_at_utc"]) <= now_utc():
        return VerifyOutcome.EXPIRED

    await db.execute(
        "UPDATE email_verifications SET used_at_utc = ? WHERE id = ?", (now_utc(), row["id"])
    )
    if purpose == CONFIRM_EMAIL:
        await db.execute(
            "UPDATE users SET is_verified = 1, verified_at_utc = ? WHERE id = ?",
            (now_utc(), row["user_id"]),
        )
    return VerifyOutcome.OK


async def count_recent_sends(
    db: Database, user_id: str, window_seconds: int, purpose: str = CONFIRM_EMAIL
) -> int:
    """Links issued recently for this account, for the per-hour send budget."""
    value = await db.value(
        "SELECT COUNT(*) FROM email_verifications"
        " WHERE user_id = ? AND purpose = ? AND created_at_utc > ?",
        (user_id, purpose, now_utc() - window_seconds),
    )
    return int(value or 0)


async def verification_owner(db: Database, token: str, purpose: str) -> str | None:
    """The account a live, unused token belongs to, or None.

    Used by the password-reset flow, which has to check the new password against
    the account's address and therefore needs the address before the token is
    consumed. It is a lookup by digest, so it reveals nothing about whether a
    guess was close.
    """
    if not token or len(token) > MAX_TOKEN_CHARS:
        return None
    row = await db.row(
        "SELECT user_id FROM email_verifications"
        " WHERE token_hash = ? AND purpose = ? AND used_at_utc IS NULL AND expires_at_utc > ?",
        (token_digest(token), purpose, now_utc()),
    )
    return None if row is None else str(row["user_id"])


async def has_pending_verification(db: Database, user_id: str) -> bool:
    """True while a live, unused confirmation link exists for this account."""
    value = await db.value(
        "SELECT COUNT(*) FROM email_verifications"
        " WHERE user_id = ? AND purpose = ? AND used_at_utc IS NULL AND expires_at_utc > ?",
        (user_id, CONFIRM_EMAIL, now_utc()),
    )
    return bool(value)


async def prune_verifications(db: Database) -> int:
    """Drop dead rows at startup; nothing here is worth keeping once unusable."""
    return await db.execute(
        "DELETE FROM email_verifications"
        " WHERE used_at_utc IS NOT NULL OR expires_at_utc < ?",
        (now_utc(),),
    )


__all__ = [
    "CONFIRM_EMAIL",
    "MAX_TOKEN_CHARS",
    "PASSWORD_RESET",
    "VerifyOutcome",
    "consume_verification",
    "count_recent_sends",
    "create_verification",
    "has_pending_verification",
    "prune_verifications",
    "verification_owner",
]
