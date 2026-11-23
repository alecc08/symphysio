"""Outbound email: one interface, two implementations, no health data ever sent.

`app.state.mailer` is chosen from the environment at startup, so tests use
`OutboxMailer` (an in-memory list, plus `.eml` files under the data dir) and
never reach the network. `ResendMailer` is the production path: a single JSON
POST to Resend, with a strict timeout and at most one retry on 429.

Everything here returns a bool instead of raising: a failed send must never turn
into a failed request. The verification row stays unused, so the user can ask for
the link again.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import httpx

from .ids import new_id
from .settings import Settings

logger = logging.getLogger("symphysio.mail")

RESEND_ENDPOINT = "https://api.resend.com/emails"
CONNECT_TIMEOUT_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 10.0
MAX_ATTEMPTS = 2  # one send, one retry, never a loop


def mask_email(email: str) -> str:
    """`person@example.com` -> `p…n@example.com`: enough to spot a typo, not an address."""
    name, _, domain = email.partition("@")
    if not domain or len(name) < 2:
        return f"{name[:1]}…@{domain}" if domain else "…"
    return f"{name[0]}…{name[-1]}@{domain}"


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    text: str
    html: str


class Mailer(Protocol):
    async def send(self, message: Message) -> bool:
        """Deliver, or return False. Must not raise."""


class NullMailer:
    """Email is not configured: log and move on, the app stays fully usable."""

    backend = "null"

    async def send(self, message: Message) -> bool:
        logger.info("email disabled; dropping %r to %s", message.subject, mask_email(message.to))
        return False


@dataclass
class OutboxMailer:
    """Dev and test: nothing is ever sent.

    Messages go to an in-memory list for assertions, and — when a directory is
    configured — to `<data dir>/outbox/<id>.eml` so a human following a
    confirmation link by hand can read the token out of a file instead of having
    to attach to the process.
    """

    backend = "outbox"
    outbox: list[Message] = field(default_factory=list)
    directory: Path | None = None

    async def send(self, message: Message) -> bool:
        self.outbox.append(message)
        written = ""
        directory = self.directory
        if directory is not None:
            try:
                written = f" -> {self._write(directory, message)}"
            except OSError:
                # a dev convenience failing must not fail the request any more
                # than a real provider failing would
                logger.exception("could not write the outbox message")
        logger.info("outbox: %r -> %s%s", message.subject, mask_email(message.to), written)
        return True

    @staticmethod
    def _write(directory: Path, message: Message) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{new_id()}.eml"
        path.write_text(
            f"Date: {datetime.now(UTC).isoformat(timespec='seconds')}\n"
            f"To: {message.to}\n"
            f"Subject: {message.subject}\n"
            "\n"
            f"{message.text}\n"
            f"\n-- html part --\n{message.html}\n",
            encoding="utf-8",
        )
        return path


class ResendMailer:
    """Production transport. The API key lives in the environment only."""

    backend = "resend"

    def __init__(self, settings: Settings) -> None:
        if settings.resend_api_key is None:  # guarded by build_mailer
            raise ValueError("ResendMailer needs RESEND_API_KEY")
        self._api_key = settings.resend_api_key
        self._from = str(settings.email_from)
        self._reply_to = settings.email_reply_to

    async def send(self, message: Message) -> bool:
        payload: dict[str, object] = {
            "from": self._from,
            "to": [message.to],
            "subject": message.subject,
            "text": message.text,
            "html": message.html,
        }
        if self._reply_to:
            payload["reply_to"] = self._reply_to
        timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                for attempt in range(1, MAX_ATTEMPTS + 1):
                    response = await client.post(
                        RESEND_ENDPOINT,
                        headers={
                            "authorization": f"Bearer {self._api_key}",
                            "content-type": "application/json",
                        },
                        json=payload,
                    )
                    if response.status_code < 300:
                        logger.info("queued %r for %s", message.subject, mask_email(message.to))
                        return True
                    if response.status_code == 429 and attempt < MAX_ATTEMPTS:
                        await asyncio.sleep(_retry_after(response.headers.get("retry-after")))
                        continue
                    logger.warning(
                        "resend rejected %r for %s (HTTP %s)",
                        message.subject,
                        mask_email(message.to),
                        response.status_code,
                    )
                    return False
        except (httpx.HTTPError, ValueError):
            # Never leak the key or the body into the log; the caller keeps the
            # verification row so the user can simply ask again.
            logger.exception("resend send failed for %s", mask_email(message.to))
            return False
        return False


def _retry_after(header_value: str | None) -> float:
    try:
        return min(10.0, max(0.5, float(header_value or "1")))
    except ValueError:
        return 1.0


def build_mailer(settings: Settings) -> Mailer:
    if settings.mail_backend == "outbox":
        return OutboxMailer(directory=settings.data_dir / "outbox")
    if settings.mail_backend == "resend":
        if not settings.email_enabled:
            logger.warning("SYPHYSIO_MAIL_BACKEND=resend but email is unconfigured; using null")
            return NullMailer()
        return ResendMailer(settings)
    return NullMailer()


__all__ = [
    "Mailer",
    "Message",
    "NullMailer",
    "OutboxMailer",
    "ResendMailer",
    "build_mailer",
    "mask_email",
]
