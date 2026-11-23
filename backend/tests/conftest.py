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


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("SYPHYSIO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SYPHYSIO_DB_PATH", str(tmp_path / "test.sqlite"))
    monkeypatch.setenv("SYPHYSIO_MIGRATIONS_DIR", str(MIGRATIONS))
    monkeypatch.setenv("SYPHYSIO_STATIC_DIR", str(tmp_path / "no-dist"))
    monkeypatch.setenv("SYPHYSIO_COOKIE_SECURE", "0")
    monkeypatch.setenv("SYPHYSIO_RATE_LIMIT_ATTEMPTS", "4")
    monkeypatch.setenv("SYPHYSIO_RATE_LIMIT_WINDOW", "60")
    # Test-only hashing parameters: production keeps the OWASP-strength defaults.
    monkeypatch.setattr(
        security,
        "password_hasher",
        PasswordHasher(time_cost=1, memory_cost=2_048, parallelism=1, type=security.Type.ID),
    )
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("symphysio_csrf") or ""
    return {"X-CSRF-Token": token}


def register(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> dict:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def catalog_ids(client: TestClient, kind: str = "exercises") -> list[dict]:
    response = client.get(f"/api/v1/catalog/{kind}")
    assert response.status_code == 200, response.text
    return response.json()
