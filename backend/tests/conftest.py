"""Shared pytest fixtures: an isolated DB per test and a fast Argon2 hasher."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app import security
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"

EMAIL = "person@example.com"
PASSWORD = "sunlit-origami-42"  # 17 chars, not on any blocklist


def configure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db: str = "test.sqlite",
    **env: str,
) -> None:
    """Point the next TestClient at its own database, with fast hashing.

    Keyword extras override any default, which is how a test asks for a different
    policy (closed registration, email confirmation modes) without rebuilding the
    whole environment.
    """
    defaults = {
        "SYMPHYSIO_DATA_DIR": str(tmp_path),
        "SYMPHYSIO_DB_PATH": str(tmp_path / db),
        "SYMPHYSIO_MIGRATIONS_DIR": str(MIGRATIONS),
        "SYMPHYSIO_STATIC_DIR": str(tmp_path / "no-dist"),
        "SYMPHYSIO_COOKIE_SECURE": "0",
        "SYMPHYSIO_RATE_LIMIT_ATTEMPTS": "4",
        "SYMPHYSIO_RATE_LIMIT_WINDOW": "60",
    }
    for key, value in {**defaults, **env}.items():
        monkeypatch.setenv(key, value)
    # Test-only hashing parameters: production keeps the OWASP-strength defaults.
    monkeypatch.setattr(
        security,
        "password_hasher",
        PasswordHasher(time_cost=1, memory_cost=2_048, parallelism=1, type=security.Type.ID),
    )


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    configure(tmp_path, monkeypatch)
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("symphysio_csrf") or ""
    return {"X-CSRF-Token": token}


def register(
    client: TestClient,
    email: str = EMAIL,
    password: str = PASSWORD,
    locale: str | None = None,
    timezone: str | None = None,
) -> dict:
    """Create an account. `locale`/`timezone` are the sign-up choices; `locale` also
    sets `Accept-Language`, which is what an unauthenticated request is judged by."""
    body: dict[str, object] = {"email": email, "password": password}
    if locale is not None:
        body["locale"] = locale
    if timezone is not None:
        body["timezone"] = timezone
    headers = {"Accept-Language": locale} if locale else {}
    response = client.post("/api/v1/auth/register", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def catalog_ids(client: TestClient, kind: str = "exercises") -> list[dict]:
    response = client.get(f"/api/v1/catalog/{kind}")
    assert response.status_code == 200, response.text
    return response.json()
