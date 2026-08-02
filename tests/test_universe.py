"""Chunk-1 universe tests -- CONTEXT 3.1 (who we trade) and 4.1 (where the list comes from).

Everything here runs against ``tests/fixtures/universe_snapshot.json``, a verbatim snapshot
of ``https://www.nseindia.com/api/underlying-information`` fetched once during the chunk-1
build session (2026-07-24): 210 underlyings + 5 indexes, matching CONTEXT 4.1's live
verification of 21-Jul-2026. No test opens a socket (see conftest.py).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from acumen import nse_http, universe
from acumen.nse_http import NseFetchError
from acumen.universe import (
    UNDERLYING_INFORMATION_URL,
    UniverseError,
    fetch_universe,
    load_cached_universe,
    load_universe,
    parse_index_symbols,
    parse_universe,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
UNIVERSE_SNAPSHOT = FIXTURES / "universe_snapshot.json"


@pytest.fixture()
def payload() -> dict:
    return json.loads(UNIVERSE_SNAPSHOT.read_text(encoding="utf-8"))


@pytest.fixture()
def symbols() -> tuple[str, ...]:
    return load_universe(UNIVERSE_SNAPSHOT)


def _payload(underlying: list[Any], indexes: list[Any] | None = None) -> dict:
    return {"data": {"IndexList": indexes or [], "UnderlyingList": underlying}}


# --- GOLDEN: membership ----------------------------------------------------------------


@pytest.mark.parametrize("symbol", ["TCS", "RELIANCE"])
def test_golden_symbol_is_in_the_universe(symbols: tuple[str, ...], symbol: str) -> None:
    """The card's golden: TCS and RELIANCE are F&O underlyings."""
    assert symbol in symbols


def test_universe_has_the_210_underlyings_context_4_1_verified(
    symbols: tuple[str, ...],
) -> None:
    """CONTEXT 4.1: "F&O universe (~210 stocks) ... fetched live 21-Jul-2026, 210 stocks"."""
    assert len(symbols) == 210


def test_indexes_are_skipped_entirely(payload: dict, symbols: tuple[str, ...]) -> None:
    """CONTEXT 3.1: "Indexes are NOT traded and need no data ... skip them entirely"."""
    indexes = parse_index_symbols(payload)
    assert len(indexes) == 5
    assert "NIFTY" in indexes
    assert not set(indexes) & set(symbols)
    for index_symbol in indexes:
        assert index_symbol not in symbols


def test_symbols_are_sorted_unique_and_upper_case(symbols: tuple[str, ...]) -> None:
    """Order is a property of the data, not of NSE's serialNumber field."""
    assert list(symbols) == sorted(symbols)
    assert len(set(symbols)) == len(symbols)
    for symbol in symbols:
        assert symbol == symbol.strip().upper() != ""


def test_parse_universe_is_pure(payload: dict) -> None:
    """Same input, same output, and the caller's payload is never mutated."""
    before = json.dumps(payload, sort_keys=True)
    assert parse_universe(payload) == parse_universe(payload)
    assert json.dumps(payload, sort_keys=True) == before


# --- never a silent empty universe -----------------------------------------------------


def test_empty_underlying_list_is_an_error_not_an_empty_universe() -> None:
    """A backtest over zero stocks reports a clean, meaningless zero. Refuse it."""
    with pytest.raises(UniverseError, match="empty"):
        parse_universe(_payload([]))


@pytest.mark.parametrize(
    "payload, match",
    [
        ({}, "no 'data' object"),
        ({"data": []}, "no 'data' object"),
        ({"data": {"IndexList": []}}, "no 'UnderlyingList' array"),
        ({"data": {"UnderlyingList": {}}}, "no 'UnderlyingList' array"),
        ("TCS", "must be a JSON object"),
        (None, "must be a JSON object"),
    ],
)
def test_malformed_universe_payload_is_rejected(payload: object, match: str) -> None:
    with pytest.raises(UniverseError, match=match):
        parse_universe(payload)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "row, match",
    [
        ("TCS", "expected an object"),
        ({"underlying": "Tata Consultancy"}, "no usable 'symbol'"),
        ({"symbol": ""}, "no usable 'symbol'"),
        ({"symbol": "   "}, "no usable 'symbol'"),
        ({"symbol": 42}, "no usable 'symbol'"),
        ({"symbol": None}, "no usable 'symbol'"),
    ],
)
def test_unusable_row_is_rejected(row: object, match: str) -> None:
    """One bad row fails the pull; it never silently shrinks the universe by one stock."""
    with pytest.raises(UniverseError, match=match):
        parse_universe(_payload([{"symbol": "TCS"}, row]))


def test_symbols_are_normalized() -> None:
    assert parse_universe(_payload([{"symbol": " tcs "}, {"symbol": "TCS"}])) == ("TCS",)


def test_error_message_points_at_the_offending_row() -> None:
    with pytest.raises(UniverseError, match=r"UnderlyingList\[2\]"):
        parse_universe(_payload([{"symbol": "A"}, {"symbol": "B"}, {"nope": 1}]))


# --- file loading ----------------------------------------------------------------------


def test_load_universe_reports_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(UniverseError, match="not found"):
        load_universe(tmp_path / "absent.json")


def test_load_universe_reports_a_non_json_file(tmp_path: Path) -> None:
    """NSE answers a bare client with an HTML 403 page -- that must not parse as empty."""
    path = tmp_path / "broken.json"
    path.write_text("<html>Access Denied</html>", encoding="utf-8")
    with pytest.raises(UniverseError, match="Could not read"):
        load_universe(path)


# --- the once-a-day pull (CONTEXT 4.1) -------------------------------------------------


def _write_cache(cache_dir: Path, payload: dict, fetched_on: date) -> Path:
    return nse_http.write_cache(
        universe.cache_path(cache_dir),
        payload,
        url=UNDERLYING_INFORMATION_URL,
        fetched_on=fetched_on,
    )


def test_offline_with_no_cache_raises(tmp_path: Path) -> None:
    """conftest's network guard would fire if this reached out; the flag stops it first."""
    with pytest.raises(NseFetchError, match="no cache file exists"):
        fetch_universe(cache_dir=tmp_path, today=date(2026, 7, 24))


def test_a_cache_written_today_is_served_without_the_network(
    tmp_path: Path, payload: dict
) -> None:
    _write_cache(tmp_path, payload, date(2026, 7, 24))
    assert fetch_universe(cache_dir=tmp_path, today=date(2026, 7, 24)) == load_universe(
        UNIVERSE_SNAPSHOT
    )


def test_a_stale_cache_is_served_offline_and_still_refetched_online(
    tmp_path: Path, payload: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**REPLACES `test_a_stale_cache_is_never_served_silently`, by ARCHITECT'S RULING
    (31-Jul-2026, closing REVIEW_9A_2 finding C3).**

    That test pinned "yesterday's universe may be fine -- but the CALLER has to say so".
    OFFLINE, the caller now says so by being offline: `allow_network=False` means "use exactly
    what is on disk". The explicit stale path is untouched and still the one to use when the AGE
    matters -- `load_cached_universe` hands the date back (tested directly below) -- and the
    once-a-day politeness of CONTEXT 4.1 is untouched too: online, a stale cache is still
    refetched rather than served.
    """
    _write_cache(tmp_path, payload, date(2026, 7, 23))
    assert fetch_universe(cache_dir=tmp_path, today=date(2026, 7, 24)) == load_universe(
        UNIVERSE_SNAPSHOT
    )

    monkeypatch.setattr(
        nse_http, "cached_json_fetch", lambda url, **kwargs: {"data": {"UnderlyingList": []}}
    )
    with pytest.raises(UniverseError):  # the refetched payload is empty -- so it WAS refetched
        fetch_universe(cache_dir=tmp_path, today=date(2026, 7, 24), allow_network=True)


def test_load_cached_universe_returns_the_age_with_the_symbols(
    tmp_path: Path, payload: dict
) -> None:
    """The explicit stale path: staleness is handed back, not hidden."""
    _write_cache(tmp_path, payload, date(2026, 7, 23))
    fetched_on, symbols = load_cached_universe(tmp_path)
    assert fetched_on == date(2026, 7, 23)
    assert len(symbols) == 210


def test_load_cached_universe_reports_an_absent_cache(tmp_path: Path) -> None:
    with pytest.raises(UniverseError, match="No cached universe"):
        load_cached_universe(tmp_path)


def test_at_most_one_live_pull_per_calendar_day(
    tmp_path: Path, payload: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTEXT 4.1: "the JSON endpoints are pulled gently (once/day max)".

    The stub replaces only the live half, so the cache logic under test is the real one.
    """
    calls: list[str] = []

    def _stub(url: str, **kwargs: Any) -> dict:
        calls.append(url)
        return payload

    monkeypatch.setattr(nse_http, "cached_json_fetch", _stub)

    first = fetch_universe(cache_dir=tmp_path, today=date(2026, 7, 24), allow_network=True)
    assert len(calls) == 1
    for _ in range(5):
        again = fetch_universe(cache_dir=tmp_path, today=date(2026, 7, 24), allow_network=True)
        assert again == first
    assert len(calls) == 1, "the same calendar day must never pull twice"

    fetch_universe(cache_dir=tmp_path, today=date(2026, 7, 25), allow_network=True)
    assert len(calls) == 2, "a new calendar day pulls once"
    assert calls == [UNDERLYING_INFORMATION_URL] * 2


def test_a_live_pull_writes_a_cache_the_offline_path_can_read(
    tmp_path: Path, payload: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(nse_http, "cached_json_fetch", lambda url, **kwargs: payload)
    fetch_universe(cache_dir=tmp_path, today=date(2026, 7, 24), allow_network=True)

    cached = universe.cache_path(tmp_path)
    assert cached.is_file()
    envelope = json.loads(cached.read_text(encoding="utf-8"))
    assert envelope["source_url"] == UNDERLYING_INFORMATION_URL
    assert envelope["fetched_on"] == "2026-07-24"
    assert fetch_universe(cache_dir=tmp_path, today=date(2026, 7, 24)) == load_universe(
        UNIVERSE_SNAPSHOT
    )


def test_a_live_pull_of_a_bad_payload_still_refuses_to_invent_a_universe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(nse_http, "cached_json_fetch", lambda url, **kwargs: _payload([]))
    with pytest.raises(UniverseError):
        fetch_universe(cache_dir=tmp_path, today=date(2026, 7, 24), allow_network=True)


def test_cache_lives_under_the_configured_data_root_outside_the_repo() -> None:
    """CLAUDE.md Q-18 layer 1: the day-cache is store state, so it lives OUTSIDE the repo.

    It used to be enough to say "under gitignored data/". The 31-Jul-2026 incident proved it
    is not: every ignore rule was in force and `git worktree remove --force` destroyed the
    tree anyway. The location is now derived from ``paths.data_root``, which the loader
    refuses to let point inside the repository tree.
    """
    from acumen.config import REPO_ROOT, load_config

    data_root = load_config(include_env=False).path("data_root")
    default = universe.cache_path()
    assert default.name == universe.CACHE_FILENAME
    assert default.parent.name == "nse"
    assert default.parent.parent == data_root
    assert not default.resolve().is_relative_to(REPO_ROOT.resolve())
