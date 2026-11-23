"""Hardening: security headers, session storage, body caps, unauthenticated surface."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from .conftest import EMAIL, PASSWORD, csrf_headers, register


def test_security_headers_on_api_and_app(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    csp = response.headers["content-security-policy"]
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp
    assert response.headers["cache-control"] == "no-store"


def test_health_is_public_and_docs_are_closed(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404


def test_sessions_store_only_token_hashes(client: TestClient, tmp_path: Path) -> None:
    register(client)
    token = client.cookies["symphysio_session"]
    db = sqlite3.connect(tmp_path / "test.sqlite")
    rows = db.execute("SELECT token_hash FROM sessions").fetchall()
    stored = [row[0] for row in rows]
    assert stored and all(len(value) == 64 for value in stored)
    assert token not in stored
    assert hashlib.sha256(token.encode()).hexdigest() in stored
    passwords = db.execute("SELECT password_hash FROM users").fetchone()[0]
    assert passwords.startswith("$argon2id$")
    assert PASSWORD not in passwords


def test_oversized_bodies_are_rejected(client: TestClient) -> None:
    register(client)
    payload = b'{"symptom_id": "' + b"x" * 400_000 + b'"}'
    response = client.post(
        "/api/v1/logs/symptoms", content=payload, headers={"content-type": "application/json"}
    )
    assert response.status_code == 413


def test_no_auth_means_no_data(client: TestClient) -> None:
    register(client)
    client.post("/api/v1/auth/logout", headers=csrf_headers(client))
    for path in (
        "/api/v1/timeline",
        "/api/v1/catalog/exercises",
        "/api/v1/analytics/summary",
        "/api/v1/export/csv",
    ):
        assert client.get(path).status_code == 401


def test_logout_everywhere_revokes_all_sessions(client: TestClient) -> None:
    register(client)
    other = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert other.status_code == 200
    first_cookie = dict(client.cookies)
    response = client.post("/api/v1/auth/logout-all", headers=csrf_headers(client))
    assert response.status_code == 204
    client.cookies.clear()
    client.cookies.update(first_cookie)
    assert client.get("/api/v1/auth/me").status_code == 401
