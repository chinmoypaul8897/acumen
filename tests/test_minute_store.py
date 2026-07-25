"""Tests for the 1-minute Parquet store and its window ledger (chunk 5A).

Round-trip, per-date replacement across the 30-day window seam (idempotent, no clobber), the
resumable window ledger, and the naive-IST guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest

from acumen.minute_store import (
    MinuteStore,
    MinuteStoreError,
    WINDOW_EMPTY,
    WINDOW_ERROR,
    WINDOW_PRESENT,
    WindowOutcome,
)


@dataclass(frozen=True)
class Bar:
    stamp: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int


def day_bars(day: date, n: int = 3, base: int = 10000) -> list[Bar]:
    open_dt = datetime.combine(day, time(9, 15))
    return [Bar(open_dt + timedelta(minutes=i), base + i, base + 10 + i, base - 10 + i, base + i, 100 + i) for i in range(n)]


@pytest.fixture
def store(tmp_path: Path) -> MinuteStore:
    return MinuteStore.at(tmp_path / "minute_store")


# --- round-trip ----------------------------------------------------------------------


def test_write_and_read_round_trip(store: MinuteStore) -> None:
    bars = day_bars(date(2016, 10, 3), n=5)
    store.write_bars("TCS", bars)
    got = store.minutes("TCS", date(2016, 10, 3))
    assert len(got) == 5
    assert [b.open_paise for b in got] == [b.open_paise for b in bars]
    assert got[0].symbol == "TCS" and got[0].trade_date == date(2016, 10, 3)


def test_month_path_keys_by_symbol_and_month(store: MinuteStore) -> None:
    path = store.month_path("tcs", date(2016, 10, 3))
    assert path.name == "TCS_2016-10.parquet" and path.parent.name == "TCS"


def test_empty_day_reads_empty(store: MinuteStore) -> None:
    assert store.minutes("TCS", date(2016, 10, 3)) == ()


# --- idempotency + the window seam ---------------------------------------------------


def test_rewriting_a_day_replaces_not_appends(store: MinuteStore) -> None:
    store.write_bars("TCS", day_bars(date(2016, 10, 3), n=5))
    store.write_bars("TCS", day_bars(date(2016, 10, 3), n=5))  # same day again
    assert len(store.minutes("TCS", date(2016, 10, 3))) == 5  # no dupes (chunk-2 idempotency)


def test_adjacent_windows_sharing_a_month_do_not_clobber(store: MinuteStore) -> None:
    """A 30-day window seam can put two windows into one month; a write replaces only its
    own DATES, never a neighbour window's rows (daily_store.write_rows' rule)."""
    # window 1 ends 2016-11-01; window 2 starts 2016-11-02 -- both touch November.
    store.write_bars("TCS", day_bars(date(2016, 11, 1), n=3))
    store.write_bars("TCS", day_bars(date(2016, 11, 2), n=3))
    assert len(store.minutes("TCS", date(2016, 11, 1))) == 3  # window 1's Nov-1 survives
    assert len(store.minutes("TCS", date(2016, 11, 2))) == 3


def test_bars_spanning_two_months_write_both(store: MinuteStore) -> None:
    bars = day_bars(date(2016, 10, 31), n=2) + day_bars(date(2016, 11, 1), n=2)
    store.write_bars("TCS", bars)
    assert store.has_day("TCS", date(2016, 10, 31)) and store.has_day("TCS", date(2016, 11, 1))
    assert store.month_path("TCS", date(2016, 10, 1)).is_file()
    assert store.month_path("TCS", date(2016, 11, 1)).is_file()


def test_minutes_range_spans_months(store: MinuteStore) -> None:
    store.write_bars("TCS", day_bars(date(2016, 10, 31), n=2) + day_bars(date(2016, 11, 1), n=2))
    got = store.minutes_range("TCS", date(2016, 10, 1), date(2016, 11, 30))
    assert len(got) == 4 and got == tuple(sorted(got, key=lambda b: b.stamp))


def test_first_stored_date_and_stored_days(store: MinuteStore) -> None:
    store.write_bars("TCS", day_bars(date(2016, 11, 1), n=1))
    store.write_bars("TCS", day_bars(date(2016, 10, 3), n=1))
    assert store.first_stored_date("TCS") == date(2016, 10, 3)
    assert store.stored_days("TCS") == (date(2016, 10, 3), date(2016, 11, 1))
    assert store.first_stored_date("NOPE") is None


# --- guards --------------------------------------------------------------------------


def test_tz_aware_stamp_is_rejected(store: MinuteStore) -> None:
    aware = Bar(datetime(2016, 10, 3, 9, 15, tzinfo=timezone.utc), 1, 1, 1, 1, 1)
    with pytest.raises(MinuteStoreError, match="naive IST"):
        store.write_bars("TCS", [aware])


# --- the window ledger ----------------------------------------------------------------


def test_window_ledger_records_and_reads_back(store: MinuteStore) -> None:
    outcome = WindowOutcome("TCS", date(2016, 10, 1), date(2016, 10, 30), WINDOW_PRESENT,
                            candle_count=375, first_date=date(2016, 10, 3), last_date=date(2016, 10, 28))
    store.record_window(outcome)
    ledger = store.window_outcomes("TCS")
    assert ledger[date(2016, 10, 1)].outcome == WINDOW_PRESENT
    assert ledger[date(2016, 10, 1)].candle_count == 375


def test_pending_windows_skips_settled_and_retries_errors(store: MinuteStore) -> None:
    windows = [
        (date(2016, 10, 1), date(2016, 10, 30)),
        (date(2016, 10, 31), date(2016, 11, 29)),
        (date(2016, 11, 30), date(2016, 12, 29)),
    ]
    store.record_window(WindowOutcome("TCS", *windows[0], WINDOW_PRESENT, candle_count=100))
    store.record_window(WindowOutcome("TCS", *windows[1], WINDOW_ERROR, reason="403 burst"))
    # window[2] never attempted
    pending = store.pending_windows("TCS", windows)
    assert pending == [windows[1], windows[2]]  # present settled; error retried; unattempted pending

    # with retry_errors False, the error window is left alone
    assert store.pending_windows("TCS", windows, retry_errors=False) == [windows[2]]


def test_a_window_extended_by_a_later_run_is_re_fetched(store: MinuteStore) -> None:
    """The `--to today` incremental hazard (REVIEW finding): a settled window whose stored end
    is SHORTER than the now-requested end must be pending again, not silently skipped."""
    start = date(2016, 10, 31)
    # run 1 settled this window covering only up to 2016-11-20 (an unaligned --to)
    store.record_window(WindowOutcome("TCS", start, date(2016, 11, 20), WINDOW_PRESENT, candle_count=100))
    # run 2 plans the same window_start but a later end 2016-11-29
    pending = store.pending_windows("TCS", [(start, date(2016, 11, 29))])
    assert pending == [(start, date(2016, 11, 29))]  # re-fetched: the 11-21..11-29 tail is NOT lost
    # once stored covering the full end, it is settled
    store.record_window(WindowOutcome("TCS", start, date(2016, 11, 29), WINDOW_PRESENT, candle_count=200))
    assert store.pending_windows("TCS", [(start, date(2016, 11, 29))]) == []
    # and a window re-planned with the SAME end is still skipped (no needless refetch)
    assert store.pending_windows("TCS", [(start, date(2016, 11, 25))]) == []


def test_empty_window_is_terminal(store: MinuteStore) -> None:
    windows = [(date(2016, 1, 1), date(2016, 1, 30))]
    store.record_window(WindowOutcome("TCS", *windows[0], WINDOW_EMPTY, candle_count=0))
    assert store.pending_windows("TCS", windows) == []  # before-listing empty never re-fetched


def test_ledger_summary_counts_by_outcome(store: MinuteStore) -> None:
    store.record_window(WindowOutcome("TCS", date(2016, 10, 1), date(2016, 10, 30), WINDOW_PRESENT))
    store.record_window(WindowOutcome("TCS", date(2016, 10, 31), date(2016, 11, 29), WINDOW_EMPTY))
    summary = store.ledger_summary("TCS")
    assert summary == {WINDOW_PRESENT: 1, WINDOW_EMPTY: 1, WINDOW_ERROR: 0, "windows": 2}


def test_unknown_outcome_is_rejected() -> None:
    with pytest.raises(MinuteStoreError, match="Unknown window outcome"):
        WindowOutcome("TCS", date(2016, 10, 1), date(2016, 10, 30), "banana")
