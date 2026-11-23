"""Email confirmation: token lifecycle, sending, limits and the opt-in hard gate.

Nothing here reaches the network: ``SYPHYSIO_MAIL_BACKEND=outbox`` swaps in an
in-memory mailer, and ``ResendMailer`` is exercised against a stubbed transport.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from app import mailer as mailer_module
from app import security, verification
from app.mailer import Message, OutboxMailer, ResendMailer
from app.main import create_app
from app.security import token_digest
from app.settings import Settings
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from .conftest import MIGRATIONS, PASSWORD, csrf_headers

PUBLIC_URL = "https://symphysio.example.com"
MAIL_EMAIL = "newest@example.com"

BASE_ENV = {
    "SYPHYSIO_COOKIE_SECURE": "0",
    "SYPHYSIO_MIGRATIONS_DIR": str(MIGRATIONS),
    "SYPHYSIO_RATE_LIMIT_ATTEMPTS": "4",
    "SYPHYSIO_RATE_LIMIT_WINDOW": "60",
}
MAIL_ENV = {
    "SYPHYSIO_MAIL_BACKEND": "outbox",
    "RESEND_API_KEY": "re_never_used_in_tests",
    "SYPHYSIO_EMAIL_FROM": "Symphysio <confirm@example.org>",
    "SYPHYSIO_PUBLIC_URL": PUBLIC_URL,
}


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_name: str, **extra: str) -> None:
    for key, value in {
        **BASE_ENV,
        "SYPHYSIO_DATA_DIR": str(tmp_path),
        "SYPHYSIO_DB_PATH": str(tmp_path / db_name),
        "SYPHYSIO_STATIC_DIR": str(tmp_path / "no-dist"),
        **MAIL_ENV,
        **extra,
    }.items():
        monkeypatch.setenv(key, value)
    # Test-only hashing parameters: production keeps the OWASP-strength defaults.
    monkeypatch.setattr(
        security,
        "password_hasher",
        PasswordHasher(time_cost=1, memory_cost=2_048, parallelism=1, type=security.Type.ID),
    )


@pytest.fixture()
def mail_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A client with email enabled, delivered to an in-memory outbox."""
    _configure(tmp_path, monkeypatch, "mail.sqlite")
    with TestClient(create_app()) as client:
        yield client


def outbox(client: TestClient) -> list[Message]:
    assert isinstance(client.app.state.mailer, OutboxMailer), "expected the outbox transport"
    return client.app.state.mailer.outbox


def register_by_mail(client: TestClient, email: str = MAIL_EMAIL) -> dict:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return response.json()


def token_from(message: Message) -> str:
    marker = f"{PUBLIC_URL}/verify?token="
    start = message.text.index(marker) + len(marker)
    return message.text[start:].splitlines()[0].strip()


# -- sending ---------------------------------------------------------------


def test_register_sends_exactly_one_link(mail_client: TestClient) -> None:
    body = register_by_mail(mail_client)
    assert body["user"]["is_verified"] is False
    messages = outbox(mail_client)
    assert len(messages) == 1
    assert messages[0].to == MAIL_EMAIL
    assert messages[0].subject == "Confirm your Symphysio account"
    assert f"{PUBLIC_URL}/verify?token=" in messages[0].text


def test_the_outbox_backend_also_writes_a_readable_file(
    mail_client: TestClient, tmp_path: Path
) -> None:
    """The dev flow in DEPLOYING.md reads the link out of this file."""
    register_by_mail(mail_client)
    token = token_from(outbox(mail_client)[0])
    files = list((tmp_path / "outbox").glob("*.eml"))
    assert len(files) == 1
    written = files[0].read_text(encoding="utf-8")
    assert f"{PUBLIC_URL}/verify?token={token}" in written
    assert written.startswith("Date:") and "Subject: Confirm your Symphysio account" in written


def test_the_email_carries_no_health_vocabulary(mail_client: TestClient) -> None:
    register_by_mail(mail_client)
    message = outbox(mail_client)[0]
    joined = (message.text + message.html).lower()
    for word in ("symptom", "severity", "pelvic", "exercise", "leak", "streak"):
        assert word not in joined


def test_only_the_token_digest_is_stored(mail_client: TestClient, tmp_path: Path) -> None:
    register_by_mail(mail_client)
    token = token_from(outbox(mail_client)[0])
    conn = sqlite3.connect(tmp_path / "mail.sqlite")
    try:
        rows = conn.execute("SELECT purpose, token_hash FROM email_verifications").fetchall()
    finally:
        conn.close()
    assert rows == [("confirm_email", token_digest(token))]
    assert token not in (tmp_path / "mail.sqlite").read_bytes().decode("latin-1")


def test_the_link_host_comes_from_config_not_the_request(mail_client: TestClient) -> None:
    response = mail_client.post(
        "/api/v1/auth/register",
        json={"email": "hosty@example.com", "password": PASSWORD},
        headers={"Host": "evil.example"},
    )
    assert response.status_code == 201
    text = outbox(mail_client)[-1].text
    assert f"{PUBLIC_URL}/verify?token=" in text
    assert "evil.example" not in text


# -- consuming -------------------------------------------------------------


def test_verify_marks_the_account_and_is_single_use(mail_client: TestClient) -> None:
    register_by_mail(mail_client)
    token = token_from(outbox(mail_client)[0])

    assert (
        mail_client.post(
            "/api/v1/auth/verify", json={"token": token}, headers=csrf_headers(mail_client)
        )
    ).status_code == 204
    me = mail_client.get("/api/v1/auth/me", headers=csrf_headers(mail_client))
    assert me.json()["user"]["is_verified"] is True

    again = mail_client.post(
        "/api/v1/auth/verify", json={"token": token}, headers=csrf_headers(mail_client)
    )
    assert again.status_code == 410


def test_unknown_token_is_rejected(mail_client: TestClient) -> None:
    register_by_mail(mail_client)
    response = mail_client.post(
        "/api/v1/auth/verify", json={"token": "z" * 43}, headers=csrf_headers(mail_client)
    )
    assert response.status_code == 400


def test_expired_token_is_gone(mail_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    register_by_mail(mail_client)
    token = token_from(outbox(mail_client)[0])
    real_clock = verification.now_utc
    monkeypatch.setattr(verification, "now_utc", lambda: real_clock() + 90_000)
    assert (
        mail_client.post(
            "/api/v1/auth/verify", json={"token": token}, headers=csrf_headers(mail_client)
        )
    ).status_code == 410


def test_resend_invalidates_the_previous_link(mail_client: TestClient) -> None:
    register_by_mail(mail_client)
    first = token_from(outbox(mail_client)[0])
    response = mail_client.post(
        "/api/v1/auth/verify/resend", json={}, headers=csrf_headers(mail_client)
    )
    assert response.status_code == 202
    assert len(outbox(mail_client)) == 2

    stale = mail_client.post(
        "/api/v1/auth/verify", json={"token": first}, headers=csrf_headers(mail_client)
    )
    assert stale.status_code == 410  # superseded links expire immediately
    assert "expired" in stale.json()["detail"]
    second = token_from(outbox(mail_client)[1])
    assert (
        mail_client.post(
            "/api/v1/auth/verify", json={"token": second}, headers=csrf_headers(mail_client)
        )
    ).status_code == 204


def test_five_wrong_guesses_trip_the_ip_limit(mail_client: TestClient) -> None:
    register_by_mail(mail_client)
    token = token_from(outbox(mail_client)[0])
    forged = token[:39] + "AAAA"
    for _ in range(4):  # SYPHYSIO_RATE_LIMIT_ATTEMPTS=4 in this fixture
        response = mail_client.post(
            "/api/v1/auth/verify", json={"token": forged}, headers=csrf_headers(mail_client)
        )
        assert response.status_code == 400
    blocked = mail_client.post(
        "/api/v1/auth/verify", json={"token": token}, headers=csrf_headers(mail_client)
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("retry-after")


def test_send_cap_per_account(mail_client: TestClient) -> None:
    register_by_mail(mail_client)
    headers = csrf_headers(mail_client)
    # One send at signup plus two more, then capped (SYPHYSIO_EMAIL_SENDS_PER_HOUR=3).
    for _ in range(2):
        assert (
            mail_client.post("/api/v1/auth/verify/resend", json={}, headers=headers).status_code
            == 202
        )
    capped = mail_client.post("/api/v1/auth/verify/resend", json={}, headers=headers)
    assert capped.status_code == 429
    assert capped.headers.get("retry-after") == "3600"
    assert len(outbox(mail_client)) == 3


def test_a_verified_account_cannot_ask_for_another_link(mail_client: TestClient) -> None:
    register_by_mail(mail_client)
    token = token_from(outbox(mail_client)[0])
    mail_client.post(
        "/api/v1/auth/verify", json={"token": token}, headers=csrf_headers(mail_client)
    )
    response = mail_client.post(
        "/api/v1/auth/verify/resend", json={}, headers=csrf_headers(mail_client)
    )
    assert response.status_code == 409


def test_verify_needs_csrf_when_a_session_exists(mail_client: TestClient) -> None:
    register_by_mail(mail_client)
    token = token_from(outbox(mail_client)[0])
    response = mail_client.post(
        "/api/v1/auth/verify", json={"token": token}, headers={"X-CSRF-Token": "wrong"}
    )
    assert response.status_code == 403


def test_verify_is_allowed_without_any_session(mail_client: TestClient) -> None:
    """The link is usually opened in a browser that has never logged in."""
    register_by_mail(mail_client)
    token = token_from(outbox(mail_client)[0])
    anonymous = TestClient(mail_client.app)  # same app, no cookies at all
    assert anonymous.post("/api/v1/auth/verify", json={"token": token}).status_code == 204


# -- failure modes ---------------------------------------------------------


def test_registration_survives_a_failed_send(
    mail_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing(self: OutboxMailer, message: Message) -> bool:
        return False

    original_send = OutboxMailer.send
    monkeypatch.setattr(OutboxMailer, "send", failing)
    assert register_by_mail(mail_client)["user"]["is_verified"] is False
    assert outbox(mail_client) == []
    monkeypatch.setattr(OutboxMailer, "send", original_send)

    # The row still exists, so the user can simply ask again.
    response = mail_client.post(
        "/api/v1/auth/verify/resend", json={}, headers=csrf_headers(mail_client)
    )
    assert response.status_code == 202
    assert len(outbox(mail_client)) == 1


def _mailer_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "data_dir": Path("."),
        "database_path": Path("unused.sqlite"),
        "migrations_dir": Path("."),
        "static_dir": Path("."),
        "cookie_secure": True,
        "session_ttl_seconds": 3600,
        "max_body_bytes": 1024,
        "rate_limit_enabled": True,
        "rate_limit_attempts": 5,
        "rate_limit_window_seconds": 60,
        "rate_limit_lockout_seconds": 60,
        "mail_backend": "resend",
        "resend_api_key": "re_test",
        "email_from": "Symphysio <confirm@example.org>",
        "email_reply_to": None,
        "public_url": PUBLIC_URL,
        "email_verification_ttl_seconds": 86_400,
        "email_sends_per_hour": 3,
        "require_email_verification": False,
    }
    return Settings(**{**base, **overrides})  # type: ignore[arg-type]


async def test_resend_transport_retries_429_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[str] = []

    class StubClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> StubClient:
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def post(self, url: str, **kwargs: object) -> mailer_module.httpx.Response:
            attempts.append(url)
            request = mailer_module.httpx.Request("POST", url)
            if len(attempts) == 1:
                return mailer_module.httpx.Response(
                    429, headers={"retry-after": "0"}, request=request
                )
            return mailer_module.httpx.Response(200, request=request)

    monkeypatch.setattr(mailer_module.httpx, "AsyncClient", StubClient)
    mailer = ResendMailer(_mailer_settings())
    sent = await mailer.send(Message(to="a@b.co", subject="s", text="t", html="<p>t</p>"))
    assert sent is True
    assert len(attempts) == 2


async def test_resend_transport_gives_up_without_raising(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class ExplodingClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise mailer_module.httpx.ConnectTimeout("no route")

    monkeypatch.setattr(mailer_module.httpx, "AsyncClient", ExplodingClient)
    sent = await ResendMailer(_mailer_settings()).send(
        Message(to="person@example.com", subject="s", text="t", html="<p>t</p>")
    )
    assert sent is False
    assert "person@example.com" not in caplog.text  # addresses are logged masked
    assert "p…n@example.com" in caplog.text


def test_no_key_never_builds_a_resend_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("SYPHYSIO_MAIL_BACKEND", "resend")
    assert mailer_module.build_mailer(_mailer_settings(resend_api_key=None)).backend == "null"


# -- the opt-in hard gate --------------------------------------------------


def test_hard_mode_blocks_login_until_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(tmp_path, monkeypatch, "hard.sqlite", SYPHYSIO_REQUIRE_EMAIL_VERIFICATION="1")
    with TestClient(create_app()) as client:
        body = register_by_mail(client)
        assert body["user"]["is_verified"] is False
        assert client.cookies.get("symphysio_session") is None  # no session yet

        blocked = client.post(
            "/api/v1/auth/login", json={"email": MAIL_EMAIL, "password": PASSWORD}
        )
        assert blocked.status_code == 403
        token = token_from(outbox(client)[-1])  # login queued a fresh link

        assert client.post("/api/v1/auth/verify", json={"token": token}).status_code == 204
        ok = client.post("/api/v1/auth/login", json={"email": MAIL_EMAIL, "password": PASSWORD})
        assert ok.status_code == 200
        assert ok.json()["user"]["is_verified"] is True


def test_hard_mode_without_email_refuses_to_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(
        tmp_path,
        monkeypatch,
        "none.sqlite",
        SYPHYSIO_REQUIRE_EMAIL_VERIFICATION="1",
        RESEND_API_KEY="",
        SYPHYSIO_EMAIL_FROM="",
        SYPHYSIO_PUBLIC_URL="",
    )
    with pytest.raises(RuntimeError, match="email is not configured"), TestClient(create_app()):
        pass


def test_unconfigured_email_leaves_the_account_plain_usable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A LAN install with no outbound mail must not nag or block anyone."""
    _configure(
        tmp_path,
        monkeypatch,
        "lan.sqlite",
        RESEND_API_KEY="",
        SYPHYSIO_EMAIL_FROM="",
        SYPHYSIO_PUBLIC_URL="",
        SYPHYSIO_MAIL_BACKEND="null",
    )
    with TestClient(create_app()) as client:
        body = register_by_mail(client)
        assert body["user"]["is_verified"] is True
        assert client.cookies.get("symphysio_session") is not None
        response = client.post(
            "/api/v1/auth/verify/resend", json={}, headers=csrf_headers(client)
        )
        assert response.status_code == 409
