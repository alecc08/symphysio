"""The address the auth limiter keys on.

The HTTP tests are the point: they replay what worked against the published image
— rotate `X-Forwarded-For` per request and the per-IP budget never runs out. The
unit tests cover the chain rule, which one live request cannot exercise.
"""

from __future__ import annotations

import pytest
from app.clientip import resolve_client_ip
from app.main import create_app
from app.settings import get_settings
from fastapi.testclient import TestClient

from .conftest import configure

TRAEFIK = "172.17.0.2"


def test_with_no_configured_proxy_the_peer_wins_and_the_header_is_ignored() -> None:
    assert resolve_client_ip("203.0.113.9", "9.9.9.9", ()) == "203.0.113.9"


def test_a_header_from_somebody_else_is_not_believed() -> None:
    assert resolve_client_ip("192.168.1.50", "9.9.9.9", ("172.16.0.0/12",)) == "192.168.1.50"


def test_behind_the_proxy_the_visitor_is_taken() -> None:
    assert resolve_client_ip(TRAEFIK, "136.124.33.3", ("172.16.0.0/12",)) == "136.124.33.3"


def test_the_rightmost_untrusted_hop_is_the_one_our_proxy_appended() -> None:
    # A chain a client wrote, then appended to by our own proxy: the entry nearest
    # us is the one our proxy wrote, so that is the one to believe.
    chain = f"1.2.3.4, 5.6.7.8, {TRAEFIK}"
    assert resolve_client_ip(TRAEFIK, chain, ("172.17.0.0/16",)) == "5.6.7.8"


def test_junk_in_the_chain_is_skipped_not_believed() -> None:
    assert resolve_client_ip(TRAEFIK, "unknown, 8.8.8.8", ("172.17.0.0/16",)) == "8.8.8.8"
    assert resolve_client_ip("testclient", "8.8.8.8", ("172.17.0.0/16",)) == "testclient"


def test_a_bad_proxy_list_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYPHYSIO_TRUSTED_PROXIES", "172.16.0.0/12, definitely-not-a-cidr")
    with pytest.raises(ValueError, match="SYPHYSIO_TRUSTED_PROXIES"):
        get_settings()


def test_the_proxy_list_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYPHYSIO_TRUSTED_PROXIES", "172.16.0.0/12, 10.0.0.5")
    assert get_settings().trusted_proxies == ("172.16.0.0/12", "10.0.0.5/32")


# -- over HTTP ------------------------------------------------------------

def _login(client: TestClient, forwarded_for: str | None = None) -> int:
    """One failed login. The email follows the address under test, so the per-email
    limiter cannot be what makes these assertions pass."""
    who = (forwarded_for or "peer").replace(".", "_")
    headers = {"X-Forwarded-For": forwarded_for} if forwarded_for else {}
    body = {"email": f"{who}@example.com", "password": "not-a-real-passphrase-1"}
    return client.post("/api/v1/auth/login", json=body, headers=headers).status_code


def test_rotating_the_header_does_not_buy_a_fresh_budget(client: TestClient) -> None:
    """The regression: every attempt is charged to the peer, header or not.

    `client` (conftest) sets attempts=4 and no proxy list, and TestClient's peer
    is not an IP — so the header is never believed.
    """
    codes = [_login(client, f"9.9.9.{n}") for n in range(1, 5)]
    assert codes == [401, 401, 401, 401]  # each charged to the same peer bucket
    assert _login(client, "9.9.9.99") == 429


def test_behind_a_configured_proxy_each_visitor_gets_own_budget(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """And the proxy path still works: the visitor is the key, not Traefik's IP.

    Without this, one noisy visitor would lock out every other visitor on the box.
    """
    configure(
        tmp_path,
        monkeypatch,
        "proxied.sqlite",
        SYPHYSIO_TRUSTED_PROXIES="172.17.0.0/16",
        SYPHYSIO_RATE_LIMIT_ATTEMPTS="1",
    )
    with TestClient(create_app(), client=(TRAEFIK, 4321)) as client:
        assert _login(client, "198.51.100.7") == 401
        assert _login(client, "203.0.113.5") == 401  # a different visitor, fresh budget
        assert _login(client, "198.51.100.7") == 429  # this visitor is out
        assert _login(client) == 401  # no header: the peer (our proxy) has its own bucket
