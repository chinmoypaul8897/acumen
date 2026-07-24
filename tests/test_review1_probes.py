"""Reviewer-added probes -- chunk-1 REVIEW session (docs/reviews/REVIEW_1.md).

These are the holes the chunk-1 build left, plus the boundaries the architect asked this
review to prove rather than assume. Nothing under review was modified; every assertion here
runs offline against the frozen snapshots.

Four groups:

1. **What the offline guard actually covers** (REVIEW_1 Finding 1). Decision B2 claims
   ``tests/conftest.py`` "FAILS any test making a real HTTP request". It patches
   ``requests.Session`` only, so a raw socket or ``urllib`` call reaches NSE from inside a
   test. That was demonstrated during the review. These tests pin the real boundary.
2. **CONTEXT 7-E2/E12 bar containment** at every boundary stamp, including the 15-minute
   15:00 stamp the build did not cover.
3. **CONTEXT 7-E8 naive-IST enforcement** across the WHOLE public surface, not the two
   entry points the build tested.
4. **The (D-1, D-2) bias pair recomputed independently** -- a second implementation built
   straight from the frozen JSON, so the goldens are not graded by the code they test.
"""

from __future__ import annotations

import json
import socket
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import requests

from acumen import nse_http, universe
from acumen.calendar import (
    CalendarError,
    TradingCalendar,
    is_session_time,
    load_calendar,
)
from acumen.nse_http import NseFetchError

FIXTURES = Path(__file__).resolve().parent / "fixtures"
HOLIDAY_SNAPSHOT = FIXTURES / "holidays_2026.json"

_GUARD_MESSAGE = "tried to reach the network"


@pytest.fixture()
def calendar_2026() -> TradingCalendar:
    return load_calendar(HOLIDAY_SNAPSHOT)


# --- 1. the offline guard: what it really covers ---------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda: requests.Session().get("https://www.nseindia.com/"), id="session-get"),
        pytest.param(
            lambda: requests.Session().request("GET", "https://www.nseindia.com/"),
            id="session-request",
        ),
        pytest.param(
            lambda: requests.Session().post("https://www.nseindia.com/", json={}),
            id="session-post",
        ),
        pytest.param(lambda: requests.get("https://www.nseindia.com/"), id="module-level-get"),
        pytest.param(lambda: requests.post("https://www.nseindia.com/"), id="module-level-post"),
    ],
)
def test_the_guard_trips_on_every_requests_entry_point(call) -> None:
    """conftest patches `get` and `request`; `post` is covered because it delegates."""
    with pytest.raises(AssertionError, match=_GUARD_MESSAGE):
        call()


def test_the_guard_trips_through_the_real_fetch_layer() -> None:
    """The path that matters: nse_http's own client, with no stub session in the way."""
    with pytest.raises(AssertionError, match=_GUARD_MESSAGE):
        nse_http.fetch_json(
            universe.UNDERLYING_INFORMATION_URL, max_attempts=1, sleep=lambda _seconds: None
        )


def test_the_guard_does_not_cover_raw_sockets() -> None:
    """REVIEW_1 Finding 1, pinned: the guard is `requests`-shaped, not network-shaped.

    Proven here without sending a byte anywhere: a socket to a CLOSED local port is refused
    by the OS, and the refusal is an OSError -- NOT the guard's AssertionError. During the
    review the same call to a real NSE address CONNECTED, and a `urllib` request reached the
    live site, from inside a test.

    If a later session widens the guard to cover sockets, this test fails. That is the
    intended signal: delete it, and close Finding 1 in docs/reviews/REVIEW_1.md.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    closed_port = probe.getsockname()[1]
    probe.close()

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(2)
    try:
        with pytest.raises(OSError) as excinfo:
            client.connect(("127.0.0.1", closed_port))
    finally:
        client.close()
    assert not isinstance(excinfo.value, AssertionError), (
        "socket access is now intercepted by the conftest guard -- REVIEW_1 Finding 1 is "
        "fixed; delete this test and close the finding."
    )


# --- 2. CONTEXT 7-E2 / 7-E12: bar containment at every boundary -------------------------


@pytest.mark.parametrize(
    "hour, minute, minutes, expected, why",
    [
        # 1-minute bars: the admitted band is exactly 09:15..15:29 (CONTEXT 4.5 gate 2).
        (9, 14, 1, False, "one minute before the open"),
        (9, 15, 1, True, "first stamp of the session"),
        (15, 29, 1, True, "375th stamp; covers 15:29:00-15:29:59"),
        (15, 30, 1, False, "would run to 15:31 -- past the bell"),
        # 15-minute bars: the admitted band is exactly 09:15..15:15.
        (9, 15, 15, True, "first 15-min bar, closes 09:30"),
        (14, 45, 15, True, "the bar CLOSING at 15:00 -- last entry candle (CONTEXT 3.4)"),
        (15, 0, 15, True, "the 15:00-15:15 square-off bar (CONTEXT 3.4-5)"),
        (15, 15, 15, True, "the bar closing exactly at 15:30"),
        (15, 16, 15, False, "would close at 15:31"),
        (9, 14, 15, False, "starts before the open"),
    ],
)
def test_bar_containment_at_every_boundary_stamp(
    hour: int, minute: int, minutes: int, expected: bool, why: str
) -> None:
    """E12: a bar stamped t covers [t, t+minutes); E2 requires it inside 09:15-15:30."""
    stamp = datetime(2026, 1, 27, hour, minute)
    assert is_session_time(stamp, minutes=minutes) is expected, why


def test_the_admitted_bands_are_exactly_the_expected_stamp_sets() -> None:
    """Enumerate the whole day rather than sampling: 375 one-minute, 25 aligned 15-minute."""
    midnight = datetime(2026, 1, 27)
    all_stamps = [midnight + timedelta(minutes=n) for n in range(24 * 60)]

    one_min = [s for s in all_stamps if is_session_time(s, minutes=1)]
    assert len(one_min) == 375
    assert (one_min[0].time(), one_min[-1].time()) == (
        datetime(2026, 1, 27, 9, 15).time(),
        datetime(2026, 1, 27, 15, 29).time(),
    )

    grid = [s for s in all_stamps if (s.hour * 60 + s.minute - 9 * 60 - 15) % 15 == 0]
    fifteen = [s for s in grid if is_session_time(s, minutes=15)]
    assert len(fifteen) == 25, "09:15..15:15 inclusive on the E12 grid"
    assert (fifteen[0].time(), fifteen[-1].time()) == (
        datetime(2026, 1, 27, 9, 15).time(),
        datetime(2026, 1, 27, 15, 15).time(),
    )


def test_containment_does_not_check_grid_alignment() -> None:
    """REVIEW_1 Finding 4: E2 is a containment rule, so an off-grid 15-min stamp passes.

    Not a chunk-1 defect -- E2 says nothing about alignment -- but chunk 5A's aggregator
    must not treat this filter as proof that a bar sits on the E12 grid.
    """
    assert is_session_time(datetime(2026, 1, 27, 9, 20), minutes=15) is True


# --- 3. CONTEXT 7-E8: naive IST across the WHOLE surface --------------------------------


def _ist(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone(timedelta(hours=5, minutes=30)))


def test_every_date_taking_method_rejects_a_datetime(calendar_2026: TradingCalendar) -> None:
    """Silent truncation of a timestamp to a date is how off-by-one-day bugs start (B8)."""
    stamp = datetime(2026, 1, 27, 9, 15)
    for method in (
        calendar_2026.is_trading_day,
        calendar_2026.is_standard_session,
        calendar_2026.prev_trading_day,
        calendar_2026.bias_pair,
    ):
        with pytest.raises(CalendarError, match="Pass .date()"):
            method(stamp)  # type: ignore[arg-type]


def test_every_date_taking_method_rejects_a_tz_aware_value(
    calendar_2026: TradingCalendar,
) -> None:
    """A tz-aware datetime is caught by the datetime guard before it can be truncated."""
    aware = _ist(2026, 1, 27, 9, 15)
    for method in (
        calendar_2026.is_trading_day,
        calendar_2026.is_standard_session,
        calendar_2026.prev_trading_day,
        calendar_2026.bias_pair,
    ):
        with pytest.raises(CalendarError):
            method(aware)  # type: ignore[arg-type]


def test_every_stamp_taking_function_rejects_a_tz_aware_value(
    calendar_2026: TradingCalendar,
) -> None:
    """CONTEXT 7-E8; the frozen PoC CSVs carry +05:30, so this is a live risk for chunk 5A."""
    aware = _ist(2026, 1, 27, 10, 0)
    with pytest.raises(CalendarError, match="naive IST"):
        is_session_time(aware)
    with pytest.raises(CalendarError, match="naive IST"):
        calendar_2026.is_session_candle(aware)
    with pytest.raises(CalendarError, match="naive IST"):
        calendar_2026.filter_session_candles([aware])


def test_a_tz_aware_holiday_cannot_be_built_into_a_calendar() -> None:
    with pytest.raises(CalendarError):
        TradingCalendar.from_holidays([_ist(2026, 1, 26)])  # type: ignore[list-item]


def test_prev_trading_day_answers_for_a_date_in_an_uncovered_year(
    calendar_2026: TradingCalendar,
) -> None:
    """REVIEW_1 Finding 3, pinned: the coverage guard is on the ANSWER, not the QUESTION.

    `is_trading_day(2027-01-01)` raises, but `prev_trading_day(2027-01-01)` answers, because
    every day it inspects happens to be inside 2026. The answer is correct; the asymmetry is
    the finding. `bias_pair` is NOT exposed -- it checks the argument first.
    """
    with pytest.raises(CalendarError, match="No NSE holiday data loaded"):
        calendar_2026.is_trading_day(date(2027, 1, 1))

    assert calendar_2026.prev_trading_day(date(2027, 1, 1)) == date(2026, 12, 31)

    with pytest.raises(CalendarError, match="No NSE holiday data loaded"):
        calendar_2026.bias_pair(date(2027, 1, 1))


# --- 4. the bias pair, recomputed independently -----------------------------------------


def _trading_days_from_the_raw_snapshot() -> set[date]:
    """Rebuild 2026's trading days from the frozen JSON without touching acumen.calendar.

    Deliberately a second implementation: the month name is resolved from the `weekDay`
    field NSE ships beside each date (a transposed or mis-parsed date fails the cross-check),
    so this does not inherit any bug in the module under test.
    """
    payload = json.loads(HOLIDAY_SNAPSHOT.read_text(encoding="utf-8"))
    names = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    months = "jan feb mar apr may jun jul aug sep oct nov dec".split()

    holidays: set[date] = set()
    for row in payload["CM"]:
        day_text, month_text, year_text = row["tradingDate"].split("-")
        parsed = date(int(year_text), months.index(month_text.lower()) + 1, int(day_text))
        assert names[parsed.weekday()] == row["weekDay"], row
        holidays.add(parsed)
    assert len(holidays) == 20, "CONTEXT 4.1 golden: 2026 = 20 CM holidays"

    trading, day = set(), date(2026, 1, 1)
    while day.year == 2026:
        if day.weekday() < 5 and day not in holidays:
            trading.add(day)
        day += timedelta(days=1)
    return trading


def _independent_bias_pair(day: date) -> tuple[date, date]:
    """CONTEXT 3.2 by hand: current = candle(D-1), previous = candle(D-2), both TRADING."""
    trading = _trading_days_from_the_raw_snapshot()

    def back(from_day: date) -> date:
        candidate = from_day - timedelta(days=1)
        while candidate not in trading:
            candidate -= timedelta(days=1)
        return candidate

    current = back(day)
    return current, back(current)


@pytest.mark.parametrize(
    "day, current, previous, why",
    [
        (date(2026, 1, 27), date(2026, 1, 23), date(2026, 1, 22), "Republic Day + weekend"),
        (date(2026, 7, 23), date(2026, 7, 22), date(2026, 7, 21), "plain midweek control"),
        (date(2026, 7, 20), date(2026, 7, 17), date(2026, 7, 16), "ordinary Monday"),
        (date(2026, 4, 6), date(2026, 4, 2), date(2026, 4, 1), "Good Friday + weekend"),
        (date(2026, 2, 16), date(2026, 2, 13), date(2026, 2, 12), "holiday already on a Sunday"),
        (date(2026, 11, 11), date(2026, 11, 9), date(2026, 11, 6), "Diwali cluster"),
        (date(2026, 3, 4), date(2026, 3, 2), date(2026, 2, 27), "Holi, crossing a month"),
    ],
)
def test_the_seven_goldens_survive_an_independent_recomputation(
    calendar_2026: TradingCalendar, day: date, current: date, previous: date, why: str
) -> None:
    """The builder's goldens, recomputed from the raw JSON by a separate implementation."""
    assert _independent_bias_pair(day) == (current, previous), why
    assert calendar_2026.bias_pair(day) == (current, previous), why


def test_the_two_implementations_agree_on_every_trading_day_of_2026(
    calendar_2026: TradingCalendar,
) -> None:
    """Not seven cases -- all 243 pairs that stay inside the covered year."""
    trading = _trading_days_from_the_raw_snapshot()
    assert len(trading) == 245, "365 - 104 weekend days - 16 weekday holidays"

    checked = 0
    for day in sorted(trading):
        if day < date(2026, 1, 6):
            continue  # its pair reaches 2025, which the snapshot does not cover
        assert calendar_2026.bias_pair(day) == _independent_bias_pair(day), day
        checked += 1
    assert checked >= 240


def test_no_holiday_or_weekend_ever_appears_in_a_pair(calendar_2026: TradingCalendar) -> None:
    """The failure this guards is silent: a bias computed from a candle that does not exist."""
    holidays = {h for h in calendar_2026.holidays}
    for day in sorted(_trading_days_from_the_raw_snapshot()):
        if day < date(2026, 1, 6):
            continue
        for leg in calendar_2026.bias_pair(day):
            assert leg.weekday() < 5, f"{leg} is a weekend day"
            assert leg not in holidays, f"{leg} is an NSE holiday"


# --- 5. day-cache failure behaviour (code_reviewer checklist 2 and 3) -------------------


def _write_envelope(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_a_half_written_cache_cannot_be_repaired_by_refetching(tmp_path: Path) -> None:
    """REVIEW_1 Finding 2, pinned: `write_cache` writes in place, so a crash mid-write
    leaves a truncated file -- and `cached_json` reads the cache BEFORE it considers the
    network, so even `allow_network=True` cannot heal it. The operator must delete the file.

    Loud, not silent, which is why this is a finding and not a failure. If a later session
    makes the write atomic (temp + rename) or lets a refetch overwrite a damaged file, the
    second half of this test starts failing -- update it and close the finding.
    """
    path = universe.cache_path(tmp_path)
    envelope = json.dumps({"source_url": "u", "fetched_on": "2026-07-24", "payload": {}})
    _write_envelope(path, envelope[: len(envelope) // 2])

    with pytest.raises(NseFetchError, match="not valid JSON"):
        universe.fetch_universe(cache_dir=tmp_path, today=date(2026, 7, 24))

    with pytest.raises(NseFetchError, match="not valid JSON"):
        universe.fetch_universe(
            cache_dir=tmp_path, today=date(2026, 7, 24), allow_network=True
        )


def test_a_failed_live_pull_never_clobbers_a_good_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Yesterday's good data must survive today's outage -- the cache is written only after
    a successful fetch, so `load_cached_universe` can still hand back the stale copy."""
    payload = json.loads((FIXTURES / "universe_snapshot.json").read_text(encoding="utf-8"))
    nse_http.write_cache(
        universe.cache_path(tmp_path),
        payload,
        url=universe.UNDERLYING_INFORMATION_URL,
        fetched_on=date(2026, 7, 24),
    )

    def _down(url: str, **kwargs: Any) -> Any:
        raise NseFetchError("NSE is down")

    monkeypatch.setattr(nse_http, "cached_json_fetch", _down)
    with pytest.raises(NseFetchError, match="NSE is down"):
        universe.fetch_universe(cache_dir=tmp_path, today=date(2026, 7, 25), allow_network=True)

    fetched_on, symbols = universe.load_cached_universe(tmp_path)
    assert fetched_on == date(2026, 7, 24)
    assert len(symbols) == 210


def test_refetching_the_same_day_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Checklist 3: repeating an ingestion must not duplicate or drift anything."""
    payload = json.loads((FIXTURES / "universe_snapshot.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(nse_http, "cached_json_fetch", lambda url, **kwargs: payload)

    first = universe.fetch_universe(
        cache_dir=tmp_path, today=date(2026, 7, 24), allow_network=True
    )
    bytes_after_first = universe.cache_path(tmp_path).read_bytes()
    second = universe.fetch_universe(
        cache_dir=tmp_path, today=date(2026, 7, 24), allow_network=True
    )
    assert first == second
    assert universe.cache_path(tmp_path).read_bytes() == bytes_after_first
