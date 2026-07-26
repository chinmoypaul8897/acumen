"""Chunk-5B tests for ``DailyStore.verify()`` -- the owed REVIEW_2 F7 consistency check.

REVIEW_2 Finding 7: "nothing ever cross-checks the ledger against the rows it claims exist ...
a month file lost to a disk error, a bad sync or a manual ``rm`` leaves a store that reports a
trading day with no candles, and ``TradingCalendar.from_daily_store`` would still build happily
from the ledger alone. *Suggested:* a ``DailyStore.verify(from, to)`` that reports ledger rows
with no data, run once before chunk 9's full backtest."

Chunk 5B runs it BEFORE the universe minute backfill, because the daily store is the ORACLE
that both the Q-11 vendor-adjustment maps and CONTEXT 4.5 gate 1 are measured against. These
tests build the exact damage the finding describes and prove the check sees it.

All offline: synthetic in-memory rows written to a tmp store.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from acumen.bhavcopy import (
    FORMAT_UDIFF,
    OUTCOME_NOT_FOUND,
    OUTCOME_PRESENT,
    DailyRow,
    DateOutcome,
    Download,
)
from acumen.daily_store import (
    MIN_ROWS_PER_DATE,
    ROW_COUNT_FLOOR_FROM,
    VERIFY_LEDGER_WITHOUT_ROWS,
    VERIFY_NON_STANDARD_SESSION_ROWS,
    VERIFY_ROW_COUNT_BELOW_FLOOR,
    VERIFY_ROWS_WITHOUT_LEDGER,
    VERIFY_UNREADABLE_MONTH,
    DailyStore,
    DailyStoreError,
)

NOW = datetime(2026, 7, 26, 9, 0, 0)


def _row(day: date, symbol: str) -> DailyRow:
    return DailyRow(
        trade_date=day,
        symbol=symbol,
        series="EQ",
        open_paise=10000,
        high_paise=10100,
        low_paise=9900,
        close_paise=10050,
        volume=1000,
        last_paise=10050,
        prev_close_paise=10000,
        turnover_paise=10050000,
        trades=10,
        isin=None,
        instrument_type=None,
        source_format=FORMAT_UDIFF,
    )


def _present(day: date, count: int) -> Download:
    rows = tuple(_row(day, f"SYM{i:04d}") for i in range(count))
    return Download(
        DateOutcome(
            trade_date=day,
            outcome=OUTCOME_PRESENT,
            source_format=FORMAT_UDIFF,
            url=f"https://example.invalid/{day.isoformat()}",
            http_status=200,
            row_count=count,
            attempted_at=NOW,
        ),
        rows,
    )


def _store(tmp_path: Path, days: dict[date, int]) -> DailyStore:
    store = DailyStore.at(tmp_path / "daily_store")
    for day, count in sorted(days.items()):
        store.ingest(_present(day, count))
    return store


FULL = MIN_ROWS_PER_DATE + 20
MON = date(2026, 3, 2)
TUE = date(2026, 3, 3)
WED = date(2026, 3, 4)


def test_a_healthy_store_verifies_clean(tmp_path: Path) -> None:
    store = _store(tmp_path, {MON: FULL, TUE: FULL, WED: FULL})
    result = store.verify()
    assert result.ok
    assert result.anomalies == ()
    assert result.notes == ()
    assert result.ledger_present_dates == 3
    assert result.dates_with_rows == 3
    assert result.rows_total == 3 * FULL
    assert result.from_date == MON and result.to_date == WED


def test_the_f7_failure_mode_a_vanished_month_file_is_caught(tmp_path: Path) -> None:
    """The finding's own scenario: the ledger claims file-present, the rows are gone."""
    store = _store(tmp_path, {MON: FULL, TUE: FULL})
    store.month_path(MON).unlink()  # a disk error / a bad sync / a manual rm

    result = store.verify()

    assert not result.ok
    kinds = [a.kind for a in result.anomalies]
    assert kinds == [VERIFY_LEDGER_WITHOUT_ROWS, VERIFY_LEDGER_WITHOUT_ROWS]
    assert {a.trade_date for a in result.anomalies} == {MON, TUE}
    # And the ledger is unchanged -- it still claims both dates, which is exactly the drift.
    assert len(store.outcomes()) == 2


def test_a_truncated_day_is_caught_by_the_row_count_floor(tmp_path: Path) -> None:
    store = _store(tmp_path, {MON: FULL, TUE: 12})

    result = store.verify()

    assert not result.ok
    assert [a.kind for a in result.anomalies] == [VERIFY_ROW_COUNT_BELOW_FLOOR]
    assert result.anomalies[0].trade_date == TUE
    assert "12 rows" in result.anomalies[0].detail


def test_the_row_count_floor_does_not_fire_before_its_start_date(tmp_path: Path) -> None:
    """Early-2000s archive bhavcopies are genuinely small; the floor starts at 2011."""
    old = date(2004, 6, 1)
    assert old < ROW_COUNT_FLOOR_FROM
    store = _store(tmp_path, {old: 40})
    assert store.verify().ok


def test_a_weekend_session_under_the_floor_is_a_NOTE_not_an_anomaly(tmp_path: Path) -> None:
    """The real 2012-11-11 case: a Sunday gold-ETF-only session, 14 rows.

    QUESTIONS.md Q-5 (ruled, executed chunk 3) already excludes weekend-dated sessions from
    trading days, so such a date is by that ruling not a full-market day. It must still be
    REPORTED -- silence would hide a genuine partial write on some other weekend date.
    """
    sunday = date(2012, 11, 11)
    assert sunday.weekday() == 6
    store = _store(tmp_path, {sunday: 14})

    result = store.verify()

    assert result.ok, "a Q-5-excluded weekend session must not block a run"
    assert result.anomalies == ()
    assert [n.kind for n in result.notes] == [VERIFY_NON_STANDARD_SESSION_ROWS]
    assert result.notes[0].trade_date == sunday
    assert "Sunday" in result.notes[0].detail
    assert result.by_kind() == {VERIFY_NON_STANDARD_SESSION_ROWS: 1}


def test_a_weekday_session_under_the_floor_stays_an_anomaly(tmp_path: Path) -> None:
    """Nothing in the spec separates a weekday special session from a truncated write."""
    store = _store(tmp_path, {WED: 14})
    result = store.verify()
    assert not result.ok
    assert [a.kind for a in result.anomalies] == [VERIFY_ROW_COUNT_BELOW_FLOOR]


def test_rows_without_a_ledger_row_are_reported(tmp_path: Path) -> None:
    """The reverse drift: the ledger IS the derived trading calendar (Q-3), so a missing
    file-present row means a real trading day is absent from the calendar."""
    store = _store(tmp_path, {MON: FULL, TUE: FULL})
    ledger = store.outcomes()
    del ledger[TUE]
    store._write_ledger(ledger)  # noqa: SLF001 -- simulating a lossy ledger rebuild

    result = store.verify(MON, WED)

    assert not result.ok
    assert [a.kind for a in result.anomalies] == [VERIFY_ROWS_WITHOUT_LEDGER]
    assert result.anomalies[0].trade_date == TUE


def test_a_confirmed_404_needs_no_rows(tmp_path: Path) -> None:
    store = _store(tmp_path, {MON: FULL})
    store.record_outcome(
        DateOutcome(trade_date=TUE, outcome=OUTCOME_NOT_FOUND, http_status=404, attempted_at=NOW)
    )
    result = store.verify()
    assert result.ok
    assert result.ledger_present_dates == 1


def test_an_unreadable_month_is_reported_and_the_check_keeps_going(tmp_path: Path) -> None:
    """The power-loss signature (REVIEW_2 F6): a valid name over data that never landed."""
    store = _store(tmp_path, {MON: FULL, date(2026, 4, 1): FULL})
    store.month_path(MON).write_bytes(b"not a parquet file at all")

    result = store.verify()

    kinds = [a.kind for a in result.anomalies]
    assert VERIFY_UNREADABLE_MONTH in kinds
    # The March dates are now unverifiable, so they also show as ledger-without-rows -- and the
    # April month was still read, proving the check did not abort on the bad file.
    assert VERIFY_LEDGER_WITHOUT_ROWS in kinds
    assert result.months_read == 1
    assert result.dates_with_rows == 1


def test_verify_refuses_to_guess_a_range_on_an_empty_ledger(tmp_path: Path) -> None:
    store = DailyStore.at(tmp_path / "empty")
    with pytest.raises(DailyStoreError, match="no date range"):
        store.verify()


def test_verify_honors_an_explicit_range(tmp_path: Path) -> None:
    store = _store(tmp_path, {MON: FULL, TUE: 12})
    assert store.verify(MON, MON).ok, "the damaged date is outside the requested range"
    assert not store.verify(MON, TUE).ok


def test_verify_rejects_a_backwards_range(tmp_path: Path) -> None:
    store = _store(tmp_path, {MON: FULL})
    with pytest.raises(DailyStoreError, match="Empty range"):
        store.verify(WED, MON)
