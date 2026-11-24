"""Password reset: the token lifecycle, what it revokes, and what it must not leak.

A confirmation link can only ever confirm an address; a reset link hands over the
account. So these tests care about three things the confirmation tests do not: the
link is short-lived, using it signs every other session out, and the public
request endpoint cannot be used to discover which addresses have accounts.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from app.mailer import Message, OutboxMailer
from app.main import create_app
from fastapi.testclient import TestClient

from .conftest import EMAIL, PASSWORD, configure, csrf_headers, register

PUBLIC_URL = "https://symphysio.example.com"
NEW_PASSWORD = "cardinal-window-71"
WEAK = "short"  # below the length policy; not a secret anyone uses

MAIL_ENV = {
    "SYPHYSIO_MAIL_BACKEND": "outbox",
    "RESEND_API_KEY": "re_never_used_in_tests",
    "SYPHYSIO_EMAIL_FROM": "Symphysio <confirm@example.org>",
    "SYPHYSIO_PUBLIC_URL": PUBLIC_URL,
    "SYPHYSIO_EMAIL_CONFIRMATION": "off",
}


@pytest.fixture()
def mail_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    configure(tmp_path, monkeypatch, **MAIL_ENV)
    with TestClient(create_app()) as client:
        yield client


def outbox(client: TestClient) -> list[Message]:
    assert isinstance(client.app.state.mailer, OutboxMailer)
    return client.app.state.mailer.outbox


def token_from(message: Message) -> str:
    """Read the token out of the link, and assert it travelled in a fragment."""
    match = re.search(r"/reset#token=([A-Za-z0-9_-]{20,})", message.text)
    assert match, message.text
    assert "?token=" not in message.text, "a query-string token lands in access logs"
    return match.group(1)


def request_reset(client: TestClient, email: str = EMAIL) -> int:
    return client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": email},
        headers=csrf_headers(client),
    ).status_code


def confirm(client: TestClient, token: str, password: str = NEW_PASSWORD) -> int:
    return client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "password": password},
        headers=csrf_headers(client),
    ).status_code


def test_a_reset_link_is_mailed_once_as_a_fragment(mail_client: TestClient) -> None:
    register(mail_client)
    assert request_reset(mail_client) == 202
    assert len(outbox(mail_client)) == 1
    message = outbox(mail_client)[0]
    assert message.to == EMAIL
    assert "password" in message.subject.lower()
    token_from(message)


def test_the_mail_carries_nothing_about_the_diary(mail_client: TestClient) -> None:
    register(mail_client)
    logged = mail_client.post(
        "/api/v1/logs/symptoms",
        json={"symptom_id": _symptom_id(mail_client), "severity": 9},
        headers=csrf_headers(mail_client),
    )
    assert logged.status_code == 201, logged.text
    request_reset(mail_client)
    message = outbox(mail_client)[0]
    body = message.text + message.html
    assert "severity" not in body.lower()
    assert "symptom" not in body.lower()


def _symptom_id(client: TestClient) -> str:
    return client.get("/api/v1/catalog/symptoms").json()[0]["id"]


def test_unknown_addresses_answer_identically(mail_client: TestClient) -> None:
    """No enumeration: an unknown address and a known one answer the same way.

    The only difference is whether a message is ever produced, which the caller
    cannot see from this side.
    """
    unknown = request_reset(mail_client, "nobody@example.com")
    assert unknown == 202
    assert not outbox(mail_client), "no account, no email, and no way to tell from outside"
    register(mail_client)
    known = request_reset(mail_client)
    assert known == 202
    assert len(outbox(mail_client)) == 1


def test_the_send_budget_is_per_account_and_still_answers_202(
    mail_client: TestClient,
) -> None:
    register(mail_client)
    for _ in range(3):  # SYPHYSIO_EMAIL_SENDS_PER_HOUR default
        assert request_reset(mail_client) == 202
    assert len(outbox(mail_client)) == 3
    assert request_reset(mail_client) == 202
    assert len(outbox(mail_client)) == 3, "capped silently, so the answer must not change"


def test_a_new_password_works_and_the_old_one_does_not(mail_client: TestClient) -> None:
    register(mail_client)
    request_reset(mail_client)
    token = token_from(outbox(mail_client)[-1])
    assert confirm(mail_client, token) == 204
    mail_client.post("/api/v1/auth/logout")
    assert (
        mail_client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    ).status_code == 401
    assert (
        mail_client.post("/api/v1/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD})
    ).status_code == 200


def test_using_a_reset_link_signs_every_other_device_out(mail_client: TestClient) -> None:
    """Sessions are rows, so the reset has to delete them: a stolen cookie should
    stop working on its next request, not at its next expiry."""
    register(mail_client)
    other = TestClient(mail_client.app)
    other.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert other.get("/api/v1/auth/me").status_code == 200

    request_reset(mail_client)
    assert confirm(mail_client, token_from(outbox(mail_client)[-1])) == 204

    assert other.get("/api/v1/auth/me").status_code == 401, "the other session must be gone"


def test_a_reset_link_works_once(mail_client: TestClient) -> None:
    register(mail_client)
    request_reset(mail_client)
    token = token_from(outbox(mail_client)[-1])
    assert confirm(mail_client, token) == 204
    assert confirm(mail_client, token) == 410


@pytest.fixture()
def short_ttl_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # A dict rather than a keyword argument: ruff reads a literal kwarg whose name
    # contains "password" as a hardcoded secret, and this one is a TTL.
    short_ttl = {"SYPHYSIO_PASSWORD_RESET_TTL_SECONDS": "300"}
    configure(tmp_path, monkeypatch, **{**MAIL_ENV, **short_ttl})
    with TestClient(create_app()) as client:
        yield client


def test_an_expired_link_is_gone_not_invalid(
    short_ttl_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    register(short_ttl_client)
    request_reset(short_ttl_client)
    token = token_from(outbox(short_ttl_client)[-1])
    from app import verification

    real_now = verification.now_utc
    monkeypatch.setattr(verification, "now_utc", lambda: real_now() + 400)
    assert confirm(short_ttl_client, token) == 410


def test_a_rejected_password_does_not_burn_the_link(mail_client: TestClient) -> None:
    """One-use tokens are precious: failing policy must leave the link live."""
    register(mail_client)
    request_reset(mail_client)
    token = token_from(outbox(mail_client)[-1])
    assert confirm(mail_client, token, password=WEAK) == 422
    assert confirm(mail_client, token) == 204


def test_a_weak_new_password_cannot_probe_for_live_tokens(mail_client: TestClient) -> None:
    """The same 422 for a made-up token as for a real one, so this endpoint is not
    an oracle for whether somebody else's reset link is still live."""
    register(mail_client)
    request_reset(mail_client)
    real = token_from(outbox(mail_client)[-1])
    fake = "k" * 40
    assert confirm(mail_client, fake, password=WEAK) == 422
    assert confirm(mail_client, real, password=WEAK) == 422
    assert confirm(mail_client, fake, password=NEW_PASSWORD) == 400


def test_purposes_are_not_interchangeable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A confirmation token must not reset a password, and a reset link must not
    confirm an address: same table, same shape, different meaning."""
    mail_env = {k: v for k, v in MAIL_ENV.items() if k != "SYPHYSIO_EMAIL_CONFIRMATION"}
    configure(tmp_path, monkeypatch, SYPHYSIO_EMAIL_CONFIRMATION="optional", **mail_env)
    with TestClient(create_app()) as client:
        register(client)
        confirm_token = _fragment_token(outbox(client)[0], "/verify")
        crossed = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": confirm_token, "password": NEW_PASSWORD},
            headers=csrf_headers(client),
        )
        assert crossed.status_code == 400
        request_reset(client)
        reset_token = token_from(outbox(client)[-1])
        back = client.post(
            "/api/v1/auth/verify", json={"token": reset_token}, headers=csrf_headers(client)
        )
        assert back.status_code == 400


def _fragment_token(message: Message, path: str) -> str:
    # `{{20,}}` is not a typo: inside an f-string a bare `{20,}` is a replacement
    # field holding the tuple `(20,)`, which silently turns the pattern to mush.
    match = re.search(rf"{path}#token=([A-Za-z0-9_-]{{20,}})", message.text)
    assert match, message.text
    return match.group(1)
