"""Suite-wide guards.

The chunk-1 and chunk-2 cards both require the tests to run OFFLINE: every assertion is made
against the frozen snapshots in ``tests/fixtures/`` and ``poc/data/``, and live fetching sits
behind an explicit ``allow_network=True`` flag that pytest never sets.

That is easy to claim and easy to break, so it is enforced here rather than trusted.

**The guard is network-shaped, not library-shaped** (docs/reviews/REVIEW_1.md Finding 1,
closed by chunk 2). It blocks at the SOCKET, so it does not matter which client a future
chunk reaches for -- ``requests``, ``urllib``, ``pandas.read_csv(url)``, ``httpx``, a raw
socket: none of them can open an outbound connection from inside a test. The earlier version
patched ``requests.Session`` only, and the chunk-1 review proved a raw socket and ``urllib``
walked straight past it to the live NSE site.

The ``requests``-level patches are KEPT on top of the socket block: they fire earlier and
name the URL, which makes an accidental live call obvious instead of a puzzling connect
error. Chunk 2 downloads bhavcopy ZIPs from a second host, so the surface only grows from
here -- without this, a refactor that flipped a default to ``allow_network=True`` would still
look green while hammering NSE on every commit (CONTEXT 4.1 limits those endpoints to one
pull per day; the bhavcopy archive is paced at one request per two seconds).
"""

from __future__ import annotations

import socket
from typing import Any

import pytest
import requests

#: Every guard raises with this phrase in it, so a test can match on one string.
NETWORK_GUARD_MESSAGE: str = "A test tried to reach the network"

_EXPLANATION: str = (
    "Tests must run against the frozen snapshots in tests/fixtures/ and poc/data/; live "
    "pulls are opt-in via allow_network=True and are never exercised by pytest (CONTEXT 4.1: "
    "the JSON endpoints are pulled at most once a day; the bhavcopy archive is paced)."
)


def _refuse(target: Any) -> Any:
    raise AssertionError(f"{NETWORK_GUARD_MESSAGE} ({target}). {_EXPLANATION}")


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every outbound connection raise, for the duration of each test."""

    def _forbidden_request(self: requests.Session, *args: Any, **kwargs: Any) -> Any:
        return _refuse(args[1] if len(args) > 1 else kwargs.get("url", "<unknown url>"))

    def _forbidden_connect(self: socket.socket, address: Any, *args: Any, **kwargs: Any) -> Any:
        return _refuse(_describe(address))

    def _forbidden_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
        return _refuse(_describe(address))

    monkeypatch.setattr(requests.Session, "request", _forbidden_request, raising=True)
    monkeypatch.setattr(requests.Session, "get", _forbidden_request, raising=True)
    monkeypatch.setattr(socket.socket, "connect", _forbidden_connect, raising=True)
    monkeypatch.setattr(socket.socket, "connect_ex", _forbidden_connect, raising=True)
    monkeypatch.setattr(socket, "create_connection", _forbidden_create_connection, raising=True)


def _describe(address: Any) -> str:
    """Render a socket address for the failure message without assuming its shape."""
    if isinstance(address, tuple) and len(address) >= 2:
        return f"{address[0]}:{address[1]}"
    return str(address)
