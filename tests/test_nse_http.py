"""Chunk-1 tests for the gentle NSE fetch layer (CONTEXT 4.1, CLAUDE.md network rules).

The behaviour that matters here is not "can it download" -- it is what happens when NSE
misbehaves. CONTEXT 4.3 states that transient "access denied" bursts are NORMAL, and CLAUDE.md
turns that into a rule: retry, never treat the first failure as empty. A universe that comes
back empty because of one 403 would look exactly like a market where nothing trades.

No test opens a socket: :func:`acumen.nse_http.fetch_json` takes the session as an argument,
so a stub answers instead (conftest.py fails any test that reaches the real network).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import requests

from acumen import nse_http
from acumen.nse_http import (
    DEFAULT_USER_AGENT,
    NseFetchError,
    cached_json,
    fetch_json,
    new_session,
    read_cache,
    write_cache,
)

URL = "https://www.nseindia.com/api/underlying-information"


class _Response:
    def __init__(self, status_code: int, body: Any = None, text: str | None = None) -> None:
        self.status_code = status_code
        self._body = body
        self._text = text

    def json(self) -> Any:
        if self._text is not None:
            raise ValueError("not JSON")
        return self._body


class _StubSession:
    """Answers a scripted sequence of API responses.

    The cookie warm-up hits a different URL and is scripted separately, mirroring reality:
    NSE's home page answers this client 403 while the API endpoints answer 200.
    """

    def __init__(self, *responses: Any, home: Any = None) -> None:
        self.responses = list(responses)
        self.home = home if home is not None else _Response(403)
        self.urls: list[str] = []

    def get(self, url: str, timeout: float | None = None) -> Any:
        self.urls.append(url)
        result: Any
        if url == nse_http.NSE_HOME_URL:
            result = self.home
        elif self.responses:
            result = self.responses.pop(0)
        else:
            raise AssertionError(f"unscripted request to {url}")
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture()
def naps() -> list[float]:
    return []


@pytest.fixture()
def sleep(naps: list[float]):
    return naps.append


# --- retry policy ----------------------------------------------------------------------


def test_a_transient_403_burst_is_retried_not_reported_as_empty(sleep, naps) -> None:
    """CONTEXT 4.3: 403 bursts are NORMAL. CLAUDE.md: never treat the first failure as empty."""
    session = _StubSession(
        _Response(403),
        _Response(403),
        _Response(200, {"data": {"UnderlyingList": [{"symbol": "TCS"}]}}),
    )
    payload = fetch_json(URL, session=session, sleep=sleep)
    assert payload == {"data": {"UnderlyingList": [{"symbol": "TCS"}]}}
    assert session.urls.count(URL) == 3


def test_backoff_between_attempts_is_exponential(sleep, naps) -> None:
    session = _StubSession(_Response(500), _Response(500), _Response(200, {"ok": True}))
    fetch_json(URL, session=session, sleep=sleep)
    assert [nap for nap in naps if nap >= 1.0] == [1.0, 2.0]


def test_an_exhausted_retry_budget_raises(sleep) -> None:
    session = _StubSession(*[_Response(403)] * 4)
    with pytest.raises(NseFetchError, match="after 4 attempts"):
        fetch_json(URL, session=session, sleep=sleep)


def test_a_network_exception_is_retried_then_raised(sleep) -> None:
    session = _StubSession(
        requests.ConnectionError("reset"),
        _Response(200, {"ok": True}),
    )
    assert fetch_json(URL, session=session, sleep=sleep) == {"ok": True}


def test_a_non_transient_status_fails_immediately(sleep) -> None:
    """A 404 will not fix itself; hammering the endpoint would just be rude."""
    session = _StubSession(_Response(404))
    with pytest.raises(NseFetchError, match="HTTP 404"):
        fetch_json(URL, session=session, sleep=sleep)
    assert len(session.urls) == 1


def test_an_html_body_behind_http_200_is_not_accepted_as_data(sleep) -> None:
    """NSE's bot-shield answers 200 with an HTML page; json() fails, so retry, then raise."""
    session = _StubSession(*[_Response(200, text="<html>Access Denied</html>")] * 4)
    with pytest.raises(NseFetchError, match="not JSON"):
        fetch_json(URL, session=session, sleep=sleep)


def test_the_error_never_claims_an_empty_result(sleep) -> None:
    session = _StubSession(*[_Response(503)] * 4)
    with pytest.raises(NseFetchError) as excinfo:
        fetch_json(URL, session=session, sleep=sleep)
    assert "not an empty result" in str(excinfo.value)


def test_a_403_triggers_at_most_one_cookie_warm_up(sleep) -> None:
    """Warming up twice tells us nothing new and doubles our footprint on a daily pull."""
    session = _StubSession(_Response(403), _Response(403), _Response(200, {"ok": True}))
    fetch_json(URL, session=session, sleep=sleep)
    assert session.urls.count(nse_http.NSE_HOME_URL) == 1


def test_no_warm_up_happens_when_nothing_is_refused(sleep) -> None:
    session = _StubSession(_Response(500), _Response(200, {"ok": True}))
    fetch_json(URL, session=session, sleep=sleep)
    assert nse_http.NSE_HOME_URL not in session.urls


def test_a_failing_warm_up_does_not_abort_the_real_request(sleep) -> None:
    """The home page itself answers 403 to this client while the API answers 200."""
    session = _StubSession(
        _Response(403),
        _Response(200, {"ok": True}),
        home=requests.ConnectionError("warm-up failed"),
    )
    assert fetch_json(URL, session=session, sleep=sleep) == {"ok": True}


def test_zero_attempts_is_rejected(sleep) -> None:
    with pytest.raises(NseFetchError, match="max_attempts"):
        fetch_json(URL, session=_StubSession(), max_attempts=0, sleep=sleep)


def test_the_session_carries_a_browser_like_user_agent() -> None:
    """NSE answers a bare client with HTTP 403 (CONTEXT 4.1: the pull is one page a day)."""
    headers = new_session().headers
    assert headers["User-Agent"] == DEFAULT_USER_AGENT
    assert "Mozilla" in headers["User-Agent"]
    assert headers["Referer"] == nse_http.NSE_HOME_URL


def test_the_throttle_stays_at_or_below_two_requests_per_second() -> None:
    assert nse_http.MIN_SECONDS_BETWEEN_REQUESTS >= 0.5


# --- the day cache ---------------------------------------------------------------------


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    path = write_cache(
        tmp_path / "nested" / "cache.json", {"a": 1}, url=URL, fetched_on=date(2026, 7, 24)
    )
    assert path.is_file()
    assert read_cache(path) == (date(2026, 7, 24), {"a": 1})


def test_read_cache_returns_none_when_absent(tmp_path: Path) -> None:
    assert read_cache(tmp_path / "absent.json") is None


@pytest.mark.parametrize(
    "body, match",
    [
        ("not json at all", "not valid JSON"),
        ('{"payload": {}}', "not an acumen day-cache envelope"),
        ('{"fetched_on": "2026-07-24"}', "not an acumen day-cache envelope"),
        ('["a", "b"]', "not an acumen day-cache envelope"),
        ('{"fetched_on": "24-Jul-2026", "payload": {}}', "malformed fetched_on"),
    ],
)
def test_a_damaged_cache_is_reported_not_ignored(tmp_path: Path, body: str, match: str) -> None:
    """Treating a damaged cache as "nothing cached" would hide it forever (CLAUDE.md rule 1)."""
    path = tmp_path / "cache.json"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(NseFetchError, match=match):
        read_cache(path)


def test_cached_json_serves_todays_cache_without_the_network(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    write_cache(path, {"a": 1}, url=URL, fetched_on=date(2026, 7, 24))
    assert cached_json(URL, path, today=date(2026, 7, 24), allow_network=False) == {"a": 1}


def test_cached_json_refuses_to_reach_out_without_the_flag(tmp_path: Path) -> None:
    with pytest.raises(NseFetchError, match="allow_network is False"):
        cached_json(URL, tmp_path / "cache.json", today=date(2026, 7, 24), allow_network=False)


def test_cached_json_names_the_stale_date(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    write_cache(path, {"a": 1}, url=URL, fetched_on=date(2026, 7, 1))
    with pytest.raises(NseFetchError, match="the cache is from 2026-07-01"):
        cached_json(URL, path, today=date(2026, 7, 24), allow_network=False)


def test_cached_json_refreshes_a_stale_cache_when_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "cache.json"
    write_cache(path, {"day": "old"}, url=URL, fetched_on=date(2026, 7, 1))
    monkeypatch.setattr(nse_http, "cached_json_fetch", lambda url, **kwargs: {"day": "new"})

    assert cached_json(URL, path, today=date(2026, 7, 24), allow_network=True) == {"day": "new"}
    envelope = json.loads(path.read_text(encoding="utf-8"))
    assert envelope["fetched_on"] == "2026-07-24"
    assert envelope["payload"] == {"day": "new"}
