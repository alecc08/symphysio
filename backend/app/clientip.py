"""Who the server believes made this request.

That question is the whole of the auth rate limiter's value: a limiter keyed on
something the caller controls is not a limiter. `X-Forwarded-For` is a header like
any other, so the rule here is the one uvicorn and Traefik also follow — believe
the header only when the *socket peer* is a proxy you configured.

Measured against the published image before this existed: with the limiter set to
one attempt, a failed login from a peer, then a second attempt carrying
`X-Forwarded-For: 9.9.9.9`, answered `401`. Rotating the header per request bought
an unlimited login budget — on an instance whose port the LAN can reach.
"""

from __future__ import annotations

import ipaddress
from functools import lru_cache

from fastapi import Request


@lru_cache(maxsize=8)
def networks(trusted: tuple[str, ...]) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """Parse the proxy list once per distinct value.

    `get_settings()` validates these on the way in, so anything unparseable here
    means a Settings built by hand in a test.
    """
    return tuple(ipaddress.ip_network(entry, strict=False) for entry in trusted)


def is_trusted(address: str, trusted: tuple[str, ...]) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:  # "testclient", an empty value, junk
        return False
    return any(ip in network for network in networks(trusted))


def resolve_client_ip(peer: str, forwarded_for: str, trusted: tuple[str, ...]) -> str:
    """The address to key per-client limits on. Pure, so it can be tested directly.

    - Empty `trusted`: the socket peer, always. Correct for `uv run uvicorn` on a
      laptop, and for anything bound directly to a network.
    - Peer is one of the configured proxies: the right-most entry of
      `X-Forwarded-For` that is not itself a proxy of ours — the visitor, because
      each of our proxies appends the address it actually saw, and anything
      further left is whatever the client typed.
    - Peer is not one of them: the socket peer, and the header is ignored. This is
      the case that closes the forged-header path.
    """
    if not trusted or not is_trusted(peer, trusted):
        return peer
    chain = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    for hop in reversed(chain):
        if not is_trusted(hop, trusted):
            return hop
    return chain[0] if chain else peer


def client_ip(request: Request) -> str:
    """`resolve_client_ip` for a live request, using this app's settings."""
    settings = request.app.state.settings
    return resolve_client_ip(
        request.client.host if request.client else "unknown",
        request.headers.get("x-forwarded-for", ""),
        settings.trusted_proxies,
    )
