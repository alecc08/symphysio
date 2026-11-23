"""Auth: registration, login, sessions, cookies, CSRF, rate limiting."""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import EMAIL, PASSWORD, csrf_headers, register


def test_register_sets_session_and_seeds_catalog(client: TestClient) -> None:
    body = register(client)
    assert body["user"]["email"] == EMAIL
    cookie = client.cookies.get("symphysio_session")
    assert cookie and len(cookie) >= 32
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["id"] == body["user"]["id"]
    assert len(client.get("/api/v1/catalog/exercises").json()) == 10


def test_session_cookie_flags(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD})
    raw = response.headers.get_list("set-cookie")
    session = next(c for c in raw if c.startswith("symphysio_session="))
    assert "HttpOnly" in session
    assert "samesite=lax" in session.lower()
    assert "Path=/" in session
    csrf = next(c for c in raw if c.startswith("symphysio_csrf="))
    assert "HttpOnly" not in csrf  # the SPA must read it


def test_only_email_and_password_accepted(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "is_admin": True},
    )
    assert response.status_code == 422


def test_password_policy(client: TestClient) -> None:
    short = client.post("/api/v1/auth/register", json={"email": EMAIL, "password": "short123"})
    assert short.status_code == 422
    breached = client.post(
        "/api/v1/auth/register", json={"email": EMAIL, "password": "password1234"}
    )
    assert breached.status_code == 422
    assert "breached" in breached.json()["detail"]
    with_email = client.post(
        "/api/v1/auth/register", json={"email": EMAIL, "password": "example-com-9999"}
    )
    assert with_email.status_code == 422


def test_duplicate_email_conflicts(client: TestClient) -> None:
    register(client)
    again = client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert again.status_code == 409


def test_login_and_logout(client: TestClient) -> None:
    register(client)
    assert client.post("/api/v1/auth/logout", headers=csrf_headers(client)).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    logged_in = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert logged_in.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200


def test_login_rejects_wrong_password(client: TestClient) -> None:
    register(client)
    assert client.post("/api/v1/auth/logout", headers=csrf_headers(client)).status_code == 204
    bad = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "wrong-password-1"})
    assert bad.status_code == 401
    assert "incorrect" in bad.json()["detail"]


def test_login_rate_limited_per_account(client: TestClient) -> None:
    register(client)
    assert client.post("/api/v1/auth/logout", headers=csrf_headers(client)).status_code == 204
    statuses = [
        client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": "nope-nope-nope"}
        ).status_code
        for _ in range(6)
    ]
    assert statuses[:4] == [401, 401, 401, 401]
    assert statuses[4] == 429
    good = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert good.status_code == 429  # lockout covers the correct password too


def test_write_requires_csrf_header(client: TestClient) -> None:
    register(client)
    definitions = client.get("/api/v1/catalog/symptoms").json()
    payload = {"symptom_id": definitions[0]["id"], "severity": 4}
    without = client.post("/api/v1/logs/symptoms", json=payload)
    assert without.status_code == 403
    with_header = client.post("/api/v1/logs/symptoms", json=payload, headers=csrf_headers(client))
    assert with_header.status_code == 201


def test_unknown_email_and_wrong_password_are_indistinguishable(client: TestClient) -> None:
    register(client)
    wrong = client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": "wrong-password-99"}
    )
    missing = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "wrong-password-99"},
    )
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()
