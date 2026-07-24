"""Suite-wide guards.

The chunk-1 card requires the tests to run OFFLINE: every assertion is made against the
frozen snapshots in ``tests/fixtures/``, and live fetching sits behind an explicit
``allow_network=True`` flag that pytest never sets.

That is easy to claim and easy to break, so it is enforced here rather than trusted: any
outbound HTTP call made during a test fails the test that made it. Without this, a future
refactor that flipped a default to ``allow_network=True`` would still look green -- while
quietly hammering an NSE endpoint CONTEXT 4.1 limits to one pull per day, on every commit.
"""

from __future__ import annotations

from typing import Any

import pytest
import requests


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every real HTTP request raise, for the duration of each test."""

    def _forbidden(self: requests.Session, *args: Any, **kwargs: Any) -> Any:
        target = args[1] if len(args) > 1 else kwargs.get("url", "<unknown url>")
        raise AssertionError(
            f"A test tried to reach the network ({target}). Tests must run against the "
            "frozen snapshots in tests/fixtures/; live pulls are opt-in via "
            "allow_network=True and are never exercised by pytest (CONTEXT 4.1: these "
            "endpoints are pulled at most once a day)."
        )

    monkeypatch.setattr(requests.Session, "request", _forbidden, raising=True)
    monkeypatch.setattr(requests.Session, "get", _forbidden, raising=True)
