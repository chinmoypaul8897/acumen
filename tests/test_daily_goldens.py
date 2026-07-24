"""Chunk-2 GOLDENS -- the card's done-criteria, reproducible offline.

Five, in the card's own words:

1. the TCS 2026-07-20 row matches `docs/RESULTS.md` (close 2251.10, volume 2,202,693);
2. cross-source: bhavcopy OHLCV vs the frozen SmartAPI data in `poc/data/` for recent dates;
3. re-ingest is idempotent (tests/test_daily_store.py owns that one);
4. derived-vs-published trading days over the ingested 2026 window (QUESTIONS.md Q-3
   safeguard 2);
5. the outcome ledger shows `confirmed-404` for 2026-07-19 (Sunday) and `file-present` for
   2026-07-20.

Everything here also RAN LIVE this session against the real ingest -- the numbers below were
measured there first and are reproduced here from the frozen fixtures, so a reviewer can
re-run them from a clean clone with the network unplugged.

**On the cross-source check.** `poc/data` holds SmartAPI 1-minute candles plus
`volume_poc_summary.csv`, whose `daily_vol` column is a SmartAPI `ONE_DAY` volume
(docs/RESULTS.md section G). So the two sources are compared where they are genuinely
comparable, and no tolerance is invented anywhere:

* volume: bhavcopy `TtlTradgVol` vs SmartAPI `ONE_DAY` volume -- both are the exchange's own
  daily total, so EXACT equality is asserted (25/25);
* open/high/low: vs the 1-minute aggregate -- EXACT equality holds on all 25 symbol-days;
* close: NOT compared to the last 1-minute close. NSE's daily close is the last-30-minute
  weighted average, not the last trade (TCS 2026-07-20: 2251.10 vs an LTP of 2251.00, and
  the bhavcopy carries BOTH -- `ClsPric` and `LastPric`). What IS asserted is the invariant
  that follows from that definition: the close lies inside the 15:00-15:29 price range;
* the 1-minute sum vs the daily total is checked against CONTEXT 4.5 gate 1's band
  [-0.1%, +5.0%] -- a spec number, not one of ours.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from acumen.bhavcopy import (
    FORMAT_UDIFF,
    OUTCOME_NOT_FOUND,
    OUTCOME_PRESENT,
    DateOutcome,
    Download,
    parse_bhavcopy,
)
from acumen.calendar import TradingCalendar, load_calendar
from acumen.daily_store import DailyStore

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"
POC_DATA = REPO / "poc" / "data"

WINDOW_START, WINDOW_END = date(2026, 7, 13), date(2026, 7, 24)

#: The five symbol-days per symbol that poc/data froze (CONTEXT 8 F7/F10 inputs).
POC_DATES = [date(2026, 7, d) for d in (14, 15, 16, 17, 20)]
POC_SYMBOLS = ("TCS", "RELIANCE", "HDFCBANK", "DIXON", "MANAPPURAM")

#: CONTEXT 4.5 gate 1 -- the spec's own acceptance band for (daily - sum of 1-min) / daily.
GATE_1_BAND = (Decimal("-0.001"), Decimal("0.05"))


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory) -> DailyStore:
    """A store built from the DERIVED bhavcopy fixture plus the frozen outcome ledger."""
    built = DailyStore.at(tmp_path_factory.mktemp("golden_store"))
    rows = parse_bhavcopy(
        (FIXTURES / "bhavcopy_udiff_sample.csv").read_text(encoding="utf-8"), FORMAT_UDIFF
    )
    for day in sorted({row.trade_date for row in rows}):
        same_day = tuple(row for row in rows if row.trade_date == day)
        built.ingest(
            Download(
                DateOutcome(
                    trade_date=day,
                    outcome=OUTCOME_PRESENT,
                    source_format=FORMAT_UDIFF,
                    http_status=200,
                    row_count=len(same_day),
                    attempted_at=datetime(2026, 7, 24, 21, 0, 0),
                ),
                same_day,
            )
        )
    built.record_outcomes(_frozen_ledger())
    return built


def _frozen_ledger() -> list[DateOutcome]:
    with (FIXTURES / "daily_ledger_window.csv").open(encoding="utf-8", newline="") as handle:
        return [
            DateOutcome(
                trade_date=date.fromisoformat(row["trade_date"]),
                outcome=row["outcome"],
                source_format=row["source_format"] or None,
                http_status=int(row["http_status"]),
            )
            for row in csv.DictReader(handle)
        ]


def _minute_candles(symbol: str, day: date) -> list[dict[str, object]]:
    """The frozen SmartAPI 1-minute file, as naive-IST stamps and exact Decimal prices.

    The CSVs carry '+05:30' stamps (REVIEW_0 Finding 7); normalising them is the ingest
    layer's job, so it is done explicitly here rather than assumed away.
    """
    path = POC_DATA / f"{symbol}_{day.isoformat()}_1min.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    candles = []
    for row in rows:
        stamp = datetime.fromisoformat(row["ts"])
        candles.append(
            {
                "time": stamp.replace(tzinfo=None).time(),
                "open": Decimal(row["open"]),
                "high": Decimal(row["high"]),
                "low": Decimal(row["low"]),
                "close": Decimal(row["close"]),
                "volume": int(row["volume"]),
            }
        )
    assert len(candles) == 375, "CONTEXT 4.5 gate 2: 375 minutes 09:15-15:29"
    return candles


def _summary_rows() -> dict[tuple[str, date], dict[str, int]]:
    with (POC_DATA / "volume_poc_summary.csv").open(encoding="utf-8", newline="") as handle:
        return {
            (row["symbol"], date.fromisoformat(row["date"])): {
                "daily_vol": int(float(row["daily_vol"])),
                "sum_1min_vol": int(float(row["sum_1min_vol"])),
            }
            for row in csv.DictReader(handle)
        }


def _paise(value: Decimal) -> int:
    scaled = value * 100
    assert scaled == scaled.to_integral_value(), f"{value} is not a whole number of paise"
    return int(scaled)


# --- GOLDEN 1 ---------------------------------------------------------------------------


def test_golden_the_tcs_row_matches_results_md(store: DailyStore) -> None:
    """docs/RESULTS.md section A: TCS 2026-07-20 close 2251.1, volume 2,202,693.

    That value was produced by a DIFFERENT vendor (SmartAPI ONE_DAY) on 2026-07-21, before
    this store existed. Two independent readings of the same exchange day agreeing to the
    paisa is the whole point of the check.
    """
    row = store.daily("TCS", date(2026, 7, 20), date(2026, 7, 20)).iloc[0]
    assert int(row.close_paise) == 225110
    assert int(row.volume) == 2202693


# --- GOLDEN 2 ---------------------------------------------------------------------------


@pytest.mark.parametrize("symbol", POC_SYMBOLS)
@pytest.mark.parametrize("day", POC_DATES)
def test_golden_cross_source_volume_is_exact(store: DailyStore, symbol: str, day: date) -> None:
    """bhavcopy TtlTradgVol vs the frozen SmartAPI ONE_DAY volume: both are THE exchange
    total for the day, so they must agree exactly -- 25/25 do."""
    row = store.daily(symbol, day, day).iloc[0]
    assert int(row.volume) == _summary_rows()[(symbol, day)]["daily_vol"]


@pytest.mark.parametrize("symbol", POC_SYMBOLS)
@pytest.mark.parametrize("day", POC_DATES)
def test_golden_cross_source_open_high_low_are_exact(
    store: DailyStore, symbol: str, day: date
) -> None:
    """bhavcopy O/H/L vs the 1-minute aggregate. Exact on all 25 symbol-days -- so no
    tolerance is invented; if a future ingest drifts by one paisa, this fails."""
    row = store.daily(symbol, day, day).iloc[0]
    candles = _minute_candles(symbol, day)
    assert int(row.open_paise) == _paise(candles[0]["open"])  # type: ignore[arg-type]
    assert int(row.high_paise) == _paise(max(c["high"] for c in candles))  # type: ignore[type-var]
    assert int(row.low_paise) == _paise(min(c["low"] for c in candles))  # type: ignore[type-var]


@pytest.mark.parametrize("symbol", POC_SYMBOLS)
@pytest.mark.parametrize("day", POC_DATES)
def test_golden_the_daily_close_sits_inside_the_closing_half_hour(
    store: DailyStore, symbol: str, day: date
) -> None:
    """NSE's daily close is the last-30-minute weighted average, not the last trade.

    So it is NOT equal to the final 1-minute close (TCS 2026-07-20: 2251.10 vs 2251.00) and
    asserting equality would be wrong. What must hold is that it lies within the range
    actually traded in that half hour -- and the bhavcopy's own LastPric field carries the
    LTP separately, which is what the 1-minute series ends on.
    """
    row = store.daily(symbol, day, day).iloc[0]
    tail = [c for c in _minute_candles(symbol, day) if c["time"] >= time(15, 0)]
    assert len(tail) == 30
    low = _paise(min(c["low"] for c in tail))  # type: ignore[type-var]
    high = _paise(max(c["high"] for c in tail))  # type: ignore[type-var]
    assert low <= int(row.close_paise) <= high


def test_golden_the_one_minute_shortfall_stays_inside_context_4_5_gate_1() -> None:
    """The same 25 symbol-days re-checked against the SPEC's band, using the bhavcopy total
    this chunk now supplies -- which is exactly the input CONTEXT 4.5 gate 1 will consume
    in chunk 5A. All 25 land in [+0.02%, +3.6%], comfortably inside [-0.1%, +5.0%]."""
    summary = _summary_rows()
    lower, upper = GATE_1_BAND
    for symbol in POC_SYMBOLS:
        for day in POC_DATES:
            values = summary[(symbol, day)]
            gap = (
                Decimal(values["daily_vol"] - values["sum_1min_vol"]) / Decimal(values["daily_vol"])
            )
            assert lower <= gap <= upper, f"{symbol} {day}: gap {gap}"


# --- GOLDEN 4 (Q-3 safeguard 2) ---------------------------------------------------------


def test_golden_derived_trading_days_equal_the_published_ones_over_the_window(
    store: DailyStore,
) -> None:
    """QUESTIONS.md Q-3, safeguard 2, verbatim: "the derived calendar's 2026 trading days
    must exactly equal the published holidays_2026.json snapshot's implied trading days over
    the ingested range".

    The two calendars share NOTHING: one is built from 12 HTTP outcomes recorded while
    downloading files, the other from a JSON holiday list pulled from a different endpoint.
    """
    derived = TradingCalendar.from_daily_store_range(store, WINDOW_START, WINDOW_END)
    published = load_calendar(FIXTURES / "holidays_2026.json")

    derived_days, published_days, current = [], [], WINDOW_START
    while current <= WINDOW_END:
        if derived.is_trading_day(current):
            derived_days.append(current)
        if published.is_trading_day(current):
            published_days.append(current)
        current += timedelta(days=1)

    assert derived_days == published_days
    assert derived_days == [date(2026, 7, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 24)]
    assert derived.weekend_sessions == (), "no special session in this window"


def test_golden_the_two_calendars_agree_on_the_bias_pair(store: DailyStore) -> None:
    """The consequence that actually matters: CONTEXT 3.2's (D-1, D-2) across a weekend."""
    derived = TradingCalendar.from_daily_store_range(store, WINDOW_START, WINDOW_END)
    published = load_calendar(FIXTURES / "holidays_2026.json")
    for day in (date(2026, 7, 20), date(2026, 7, 21), date(2026, 7, 24)):
        assert derived.bias_pair(day) == published.bias_pair(day)


# --- GOLDEN 5 ---------------------------------------------------------------------------


def test_golden_the_ledger_shows_the_cards_two_named_dates(store: DailyStore) -> None:
    """"outcome ledger shows confirmed-404 for 2026-07-19 (Sunday) and file-present for
    2026-07-20" -- the card, word for word."""
    ledger = store.outcomes()
    assert ledger[date(2026, 7, 19)].outcome == OUTCOME_NOT_FOUND
    assert ledger[date(2026, 7, 19)].http_status == 404
    assert ledger[date(2026, 7, 20)].outcome == OUTCOME_PRESENT
    assert ledger[date(2026, 7, 20)].source_format == FORMAT_UDIFF


def test_golden_the_ingested_window_is_fully_settled(store: DailyStore) -> None:
    """Both bounded windows: every date attempted, none left in error."""
    for start, end, present, absent in (
        (WINDOW_START, WINDOW_END, 10, 2),
        (date(2018, 1, 1), date(2018, 1, 15), 11, 4),
    ):
        summary = store.coverage_summary(start, end)
        assert summary[OUTCOME_PRESENT] == present
        assert summary[OUTCOME_NOT_FOUND] == absent
        assert summary["error"] == 0
        assert summary["missing"] == 0
