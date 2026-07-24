"""Chunk-2 tests for the DERIVED trading calendar -- QUESTIONS.md Q-3 executed.

The architect's ruling, in full: "historical trading days are DERIVED from the daily store --
a date with a bhavcopy IS a trading day. Safeguards: (1) the downloader records every date's
outcome as file-present / confirmed-404 / error; ONLY a confirmed-404 counts as a
non-trading day -- a download error is NEVER treated as a holiday; (2) the derived calendar's
2026 trading days must exactly equal the published holidays_2026.json snapshot's implied
trading days over the ingested range (test); (3) the published endpoint remains authoritative
for current/future dates (live screener); the derived calendar serves the backtest past."

Safeguard 2 is the golden in tests/test_daily_goldens.py. This module tests the machinery:
what the derived calendar answers, and -- far more important -- what it REFUSES to answer.
The failure being guarded against is silent: a calendar that quietly calls a failed download
a holiday shifts every bias pair spanning it (CONTEXT 3.2) and the backtest still prints a
number.

Offline: the ledger comes from the DERIVED fixture in tests/fixtures/PROVENANCE.md.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from acumen.bhavcopy import OUTCOME_ERROR, OUTCOME_NOT_FOUND, OUTCOME_PRESENT, DateOutcome
from acumen.calendar import CalendarError, TradingCalendar
from acumen.daily_store import DailyStore

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LEDGER_FIXTURE = FIXTURES / "daily_ledger_window.csv"

WINDOW_2026 = (date(2026, 7, 13), date(2026, 7, 24))
WINDOW_2018 = (date(2018, 1, 1), date(2018, 1, 15))


def ledger_rows() -> list[DateOutcome]:
    """The frozen ledger of this session's two bounded-window ingests."""
    with LEDGER_FIXTURE.open(encoding="utf-8", newline="") as handle:
        return [
            DateOutcome(
                trade_date=date.fromisoformat(row["trade_date"]),
                outcome=row["outcome"],
                source_format=row["source_format"] or None,
                http_status=int(row["http_status"]),
                attempted_at=datetime(2026, 7, 24, 21, 0, 0),
            )
            for row in csv.DictReader(handle)
        ]


@pytest.fixture()
def ingested(tmp_path: Path) -> DailyStore:
    """A store whose LEDGER is the real one, with no price rows -- the calendar needs none."""
    store = DailyStore.at(tmp_path / "store")
    store.record_outcomes(ledger_rows())
    return store


def _trading_days(calendar: TradingCalendar, start: date, end: date) -> list[date]:
    days, current = [], start
    while current <= end:
        if calendar.is_trading_day(current):
            days.append(current)
        current += timedelta(days=1)
    return days


# --- what it answers --------------------------------------------------------------------


def test_a_date_with_a_bhavcopy_is_a_trading_day(ingested: DailyStore) -> None:
    """The ruling, verbatim, in one assertion."""
    calendar = TradingCalendar.from_daily_store_range(ingested, *WINDOW_2026)
    assert calendar.is_trading_day(date(2026, 7, 20)) is True
    assert calendar.is_trading_day(date(2026, 7, 19)) is False, "Sunday, confirmed-404"
    assert calendar.source == "derived"


def test_the_derived_calendar_spans_both_bhavcopy_eras(ingested: DailyStore) -> None:
    """The 2018 window came from the old archive format, the 2026 one from UDiFF."""
    old = TradingCalendar.from_daily_store_range(ingested, *WINDOW_2018)
    assert _trading_days(old, *WINDOW_2018) == [
        date(2018, 1, d) for d in (1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 15)
    ]


def test_bias_pairs_work_on_a_derived_calendar(ingested: DailyStore) -> None:
    """CONTEXT 3.2 is what this calendar exists for: (D-1, D-2) as TRADING days.

    2026-07-20 is a Monday, so its pair must skip the weekend the ledger marked 404.
    """
    calendar = TradingCalendar.from_daily_store_range(ingested, *WINDOW_2026)
    assert calendar.bias_pair(date(2026, 7, 20)) == (date(2026, 7, 17), date(2026, 7, 16))
    assert calendar.prev_trading_day(date(2026, 7, 20)) == date(2026, 7, 17)


def test_the_e2_session_filter_works_on_a_derived_calendar(ingested: DailyStore) -> None:
    """CONTEXT 7-E2's first clause is "a date absent from the trading calendar"."""
    calendar = TradingCalendar.from_daily_store_range(ingested, *WINDOW_2026)
    assert calendar.is_session_candle(datetime(2026, 7, 20, 9, 15)) is True
    assert calendar.is_session_candle(datetime(2026, 7, 19, 9, 15)) is False


def test_holidays_are_the_weekday_404s_only(ingested: DailyStore) -> None:
    """A weekend 404 is not a holiday, it is a weekend. The July window has neither."""
    calendar = TradingCalendar.from_daily_store_range(ingested, *WINDOW_2026)
    assert calendar.holidays == frozenset()
    assert calendar.weekend_sessions == ()


# --- what it refuses to answer ----------------------------------------------------------


def test_a_date_the_store_never_ingested_is_unknown_not_a_holiday(
    ingested: DailyStore,
) -> None:
    """The heart of safeguard 1. 2026-03-05 is a perfectly good trading day; this calendar
    simply has no evidence about it, and must say so rather than answer False."""
    calendar = TradingCalendar.from_daily_store_range(ingested, *WINDOW_2026)
    with pytest.raises(CalendarError, match="no evidence for 2026-03-05"):
        calendar.is_trading_day(date(2026, 3, 5))


def test_an_error_in_the_ledger_blocks_the_calendar_entirely(tmp_path: Path) -> None:
    """Safeguard 1, stated as loudly as it can be: a download error is NEVER a holiday.

    The alternative -- deriving a calendar around the error -- would delete 2026-07-16 from
    history, and every bias pair spanning it would silently use the wrong two candles.
    """
    store = DailyStore.at(tmp_path)
    rows = [
        row
        for row in ledger_rows()
        if WINDOW_2026[0] <= row.trade_date <= WINDOW_2026[1]
        and row.trade_date != date(2026, 7, 16)
    ]
    rows.append(
        DateOutcome(
            trade_date=date(2026, 7, 16), outcome=OUTCOME_ERROR, reason="HTTP 503 burst"
        )
    )
    store.record_outcomes(rows)

    with pytest.raises(CalendarError, match="1 unsettled"):
        TradingCalendar.from_daily_store_range(store, *WINDOW_2026)


def test_a_gap_in_the_ledger_blocks_the_calendar(tmp_path: Path) -> None:
    """An interrupted backfill must not become a calendar full of invented holidays."""
    store = DailyStore.at(tmp_path)
    store.record_outcomes(
        [
            row
            for row in ledger_rows()
            if WINDOW_2026[0] <= row.trade_date <= WINDOW_2026[1]
            and row.trade_date != date(2026, 7, 15)
        ]
    )
    with pytest.raises(CalendarError, match="never attempted"):
        TradingCalendar.from_daily_store_range(store, *WINDOW_2026)


def test_a_partial_year_cannot_masquerade_as_a_whole_one(ingested: DailyStore) -> None:
    """Safeguard 3 in code: the CURRENT year can never be complete, so the whole-year
    constructor refuses it and the published endpoint stays authoritative for today."""
    with pytest.raises(CalendarError, match="never attempted"):
        TradingCalendar.from_daily_store(ingested, [2026])


def test_a_ledger_with_no_file_present_date_is_a_damaged_store_not_a_closed_market(
    tmp_path: Path,
) -> None:
    store = DailyStore.at(tmp_path)
    store.record_outcomes(
        [
            DateOutcome(trade_date=date(2026, 7, 13) + timedelta(days=n), outcome=OUTCOME_NOT_FOUND)
            for n in range(5)
        ]
    )
    with pytest.raises(CalendarError, match="no file-present date"):
        TradingCalendar.from_daily_store_range(store, date(2026, 7, 13), date(2026, 7, 17))


def test_from_daily_store_needs_at_least_one_year(ingested: DailyStore) -> None:
    with pytest.raises(CalendarError, match="at least one year"):
        TradingCalendar.from_daily_store(ingested, [])


def test_a_backwards_range_is_refused(ingested: DailyStore) -> None:
    with pytest.raises(CalendarError, match="Empty range"):
        TradingCalendar.from_daily_store_range(ingested, date(2026, 7, 24), date(2026, 7, 13))


# --- whole years, and the weekend-session case (QUESTIONS.md Q-4) -----------------------


def _whole_year_ledger(year: int, *, present: set[date]) -> list[DateOutcome]:
    rows, current = [], date(year, 1, 1)
    while current.year == year:
        rows.append(
            DateOutcome(
                trade_date=current,
                outcome=OUTCOME_PRESENT if current in present else OUTCOME_NOT_FOUND,
            )
        )
        current += timedelta(days=1)
    return rows


def test_a_complete_year_derives_cleanly(tmp_path: Path) -> None:
    """The production path: a finished year, every date settled."""
    weekdays = set()
    current = date(2019, 1, 1)
    while current.year == 2019:
        if current.weekday() < 5 and current != date(2019, 8, 15):
            weekdays.add(current)
        current += timedelta(days=1)

    store = DailyStore.at(tmp_path)
    store.record_outcomes(_whole_year_ledger(2019, present=weekdays))

    calendar = TradingCalendar.from_daily_store(store, [2019])
    assert calendar.covered_years == frozenset({2019})
    assert calendar.holidays == frozenset({date(2019, 8, 15)})
    assert calendar.is_trading_day(date(2019, 8, 15)) is False
    assert calendar.is_trading_day(date(2019, 8, 14)) is True
    assert len(_trading_days(calendar, date(2019, 1, 1), date(2019, 12, 31))) == len(weekdays)


def test_a_saturday_session_is_represented_honestly(tmp_path: Path) -> None:
    """NSE does hold weekend sessions (budget Saturdays, DR live sessions), and the ruling
    says a date with a bhavcopy IS a trading day -- so the derived calendar cannot use the
    weekday rule. It must answer from evidence, and it must make the case VISIBLE.

    Whether CONTEXT 7-E2 should additionally exclude such a day from trading is QUESTIONS.md
    Q-4, unanswered: this test pins the representation, not that decision.
    """
    saturday = date(2019, 6, 1)
    weekdays = {saturday}
    current = date(2019, 1, 1)
    while current.year == 2019:
        if current.weekday() < 5:
            weekdays.add(current)
        current += timedelta(days=1)

    store = DailyStore.at(tmp_path)
    store.record_outcomes(_whole_year_ledger(2019, present=weekdays))

    calendar = TradingCalendar.from_daily_store(store, [2019])
    assert calendar.is_trading_day(saturday) is True
    assert calendar.weekend_sessions == (saturday,)
    assert calendar.prev_trading_day(date(2019, 6, 3)) == saturday, "the pair must include it"


def test_a_published_calendar_reports_no_weekend_sessions() -> None:
    """The property is meaningful only for a derived calendar; it must not lie for the other."""
    published = TradingCalendar.from_holidays([date(2026, 1, 26)])
    assert published.weekend_sessions == ()
    assert published.source == "published"


def test_the_published_calendar_is_unchanged_by_all_of_this() -> None:
    """Chunk 1 is reviewed-PASS; its behaviour must be byte-for-byte the same."""
    published = TradingCalendar.from_holidays([date(2026, 1, 26)])
    assert published.trading_days is None and published.covered_days is None
    assert published.is_trading_day(date(2026, 1, 26)) is False
    assert published.is_trading_day(date(2026, 1, 27)) is True
    assert published.is_trading_day(date(2026, 1, 25)) is False, "Sunday"
