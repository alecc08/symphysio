"""Registration is a switch, and the default is open.

An instance behind a public router needs to close its front door; the test
checks the door actually shuts, and shuts without writing anything.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app.main import create_app
from fastapi.testclient import TestClient

from .conftest import EMAIL, PASSWORD, configure


@pytest.fixture()
def closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    configure(tmp_path, monkeypatch, "closed.sqlite", SYPHYSIO_ALLOW_REGISTRATION="0")
    with TestClient(create_app()) as client:
        yield client


def test_registration_is_open_by_default(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 201, response.text


def test_a_closed_instance_refuses_and_says_so(closed: TestClient) -> None:
    response = closed.post("/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 403
    assert "closed" in response.json()["detail"]


def test_closing_registration_does_not_create_the_account(closed: TestClient) -> None:
    closed.post("/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD})
    login = closed.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 401, login.text


def test_a_closed_instance_is_still_rate_limited(closed: TestClient) -> None:
    """The 403 must not be a free oracle for probing which instances are open.

    Every rejected attempt is charged to the limiter (the fixture sets
    attempts=4), so hammering a closed endpoint runs out the same budget as an
    open one.
    """
    codes = [
        closed.post(
            "/api/v1/auth/register", json={"email": f"p{i}@example.com", "password": PASSWORD}
        ).status_code
        for i in range(4)
    ]
    assert set(codes) == {403}, codes
    flood = closed.post(
        "/api/v1/auth/register", json={"email": "more@example.com", "password": PASSWORD}
    )
    assert flood.status_code == 429


def test_rejected_attempts_cost_budget_on_an_open_instance(client: TestClient) -> None:
    """Registration is the endpoint that pays for an Argon2 hash, so it is metered.

    The limiter only counts what the router tells it, and nothing used to charge
    the `register:` key — the check was there and could never trip. Weak-password
    attempts now fill the window (attempts=4 here), and the next request is
    refused before the password is ever hashed.
    """
    weak = [
        client.post(
            "/api/v1/auth/register", json={"email": EMAIL, "password": "short123"}
        ).status_code
        for _ in range(4)
    ]
    assert set(weak) == {422}, weak
    blocked = client.post(
        "/api/v1/auth/register", json={"email": "next@example.com", "password": PASSWORD}
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers

