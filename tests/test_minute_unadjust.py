"""Tests for the Q-10 un-adjustment: SmartAPI 1-minute -> RAW on ingest.

Pure-arithmetic goldens (the RELIANCE bonus case hand-computed against the OPEN-8 evidence, a
chained two-event round-once case, the identity case), the tick-snap tolerance on both sides,
the volume direction, the fetch-date the ledger now records, and the un-provable (demerger /
pending-rights) span. Then the ingest-path integration: a backfill that un-adjusts each fetched
window before storing it, the in-place rebuild of an already-fetched store, and gate-1 by year
before vs after. All offline: fakes for the client / master / daily store, a real Parquet store.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from acumen import minute_backfill as mb
from acumen import minute_unadjust as u
from acumen import quality_gates as qg
from acumen.corp_actions import Factor, Suppression, KIND_BONUS, KIND_SPLIT, KIND_DEMERGER
from acumen.minute_store import MinuteStore, WINDOW_PRESENT, WindowOutcome
from acumen.smartapi_client import OneMinuteBar, SmartApiError


# --- k_cum window semantics -----------------------------------------------------------


def _bonus(symbol: str, ex: date, k: Decimal) -> Factor:
    return Factor(symbol=symbol, ex_date=ex, kind=KIND_BONUS, k=k, basis="test")


def test_cumulative_factor_is_the_half_open_D_to_F_window() -> None:
    sym = "TCS"
    # three events: one ON the candle day D (excluded), one strictly inside (included),
    # one ON the fetch date F (included), one after F (excluded).
    factors = [
        _bonus(sym, date(2016, 10, 3), Decimal("0.9")),   # ex == D -> excluded
        _bonus(sym, date(2018, 6, 1), Decimal("0.5")),    # in (D, F] -> included
        _bonus(sym, date(2026, 7, 25), Decimal("0.8")),   # ex == F -> included
        _bonus(sym, date(2026, 8, 1), Decimal("0.7")),    # after F -> excluded
        _bonus("OTHER", date(2019, 1, 1), Decimal("0.3")),  # other symbol -> excluded
    ]
    k = u.cumulative_factor(factors, date(2016, 10, 3), date(2026, 7, 25), symbol=sym)
    assert k == Decimal("0.5") * Decimal("0.8")


def test_cumulative_factor_empty_window_is_identity() -> None:
    factors = [_bonus("TCS", date(2018, 6, 1), Decimal("0.5"))]
    # a day AFTER the only event: empty window -> k_cum == 1 (a recent, raw day)
    assert u.cumulative_factor(factors, date(2020, 1, 1), date(2026, 7, 25), symbol="TCS") == Decimal(1)


def test_cumulative_factor_rejects_fetch_before_day() -> None:
    with pytest.raises(ValueError):
        u.cumulative_factor([], date(2026, 7, 25), date(2016, 1, 1), symbol="TCS")


# --- price goldens --------------------------------------------------------------------


def test_reliance_1to1_bonus_recovers_raw_prices_exactly() -> None:
    """OPEN-8 evidence, RELIANCE pre-ex day 2024-10-25: the fetched 1-minute daily-OHLC divided
    by the EXACT bonus factor k = 1/2 recovers the RAW daily high/low to the paisa (268870 /
    264400). The gate-3 probe's empirical raw-gap was 0.5024, but the ruling un-adjusts with the
    factor TABLE's k, not the gap -- and the factor is exactly 1/2 for a 1:1 bonus."""
    k = Decimal(1) / 2
    raw_high, snapped_h, _ = u.unadjust_price_paise(134435, k, tick_paise=5)
    raw_low, snapped_l, _ = u.unadjust_price_paise(132200, k, tick_paise=5)
    assert (raw_high, raw_low) == (268870, 264400)  # == raw daily high/low from the evidence
    assert snapped_h and snapped_l  # both land exactly on the tick grid


def test_reliance_0p5024_gap_case_hand_computed() -> None:
    """The '0.5024 case' arithmetic pin: dividing the evidence's 1-minute close (132815) by the
    measured raw-gap 0.5024 and rounding once, half-even, is exactly 264361 -- hand-computed
    (132815 / 0.5024 = 264361.46..., rounds to 264361). This pins the Decimal divide + single
    half-even round independently of any tick grid."""
    raw, _, _ = u.unadjust_price_paise(132815, Decimal("0.5024"), tick_paise=None)
    assert raw == 264361


def test_chained_two_events_round_once_not_per_event() -> None:
    """Two factors in (D, F] chain into ONE k_cum and the price is divided ONCE, rounded ONCE
    (CONTEXT 7-E11), matching adjust_pair's discipline in reverse. A=1001 with k1=2/3, k2=0.7 is
    a case where rounding once (2145) differs from rounding after each divide (2146)."""
    sym = "TCS"
    k1 = Decimal(2) / Decimal(3)   # bonus 1:2
    k2 = Decimal(7) / Decimal(10)  # a second event, k=0.7
    factors = [_bonus(sym, date(2019, 1, 1), k1), _bonus(sym, date(2020, 1, 1), k2)]
    k_cum = u.cumulative_factor(factors, date(2016, 10, 3), date(2026, 7, 25), symbol=sym)
    assert k_cum == k1 * k2
    raw, _, _ = u.unadjust_price_paise(1001, k_cum, tick_paise=None)
    assert raw == 2145  # round-once
    # the wrong per-event answer is 2146; prove we are NOT doing that
    from decimal import ROUND_HALF_EVEN
    step1 = int((Decimal(1001) / k1).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
    per_event = int((Decimal(step1) / k2).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
    assert per_event == 2146 != raw


def test_identity_price_returned_exactly_and_not_regridded() -> None:
    """k_cum == 1 (a recent, post-last-CA day): the fetched price is returned EXACTLY, never
    re-gridded against the current tick -- so an already-raw price on a finer historical grid is
    not corrupted."""
    raw, snapped, off = u.unadjust_price_paise(241157, Decimal(1), tick_paise=10)
    assert raw == 241157 and snapped is False and off == 0  # untouched despite being off the 10-grid


# --- volume direction -----------------------------------------------------------------


def test_volume_multiplies_by_k_cum() -> None:
    """The ruling's direction: raw_volume = fetched_volume x k_cum. A 1:1 bonus doubled the
    pre-ex volume, so recovering raw halves it (the OPEN-8 evidence: 1-min vol ~2x raw daily)."""
    assert u.unadjust_volume(1818222, Decimal("0.5")) == 909111
    assert u.unadjust_volume(1000, Decimal(1)) == 1000  # identity leaves volume unchanged


# --- tick-snap on both sides ----------------------------------------------------------


def test_tick_snap_within_tolerance_snaps_to_grid() -> None:
    # k=0.5, adjusted 12061 -> raw 24122; nearest 10-paise tick is 24120 (2 paise off) -> snap.
    raw, snapped, off = u.unadjust_price_paise(12061, Decimal("0.5"), tick_paise=10, tol_paise=2)
    assert (raw, snapped, off) == (24120, True, 2)


def test_tick_snap_beyond_tolerance_flags_and_does_not_snap() -> None:
    # k=0.5, adjusted 12057 -> raw 24114; nearest 10-paise tick is 24110 (4 paise off) -> flag,
    # keep the divided value (do not corrupt it by snapping across > tolerance).
    raw, snapped, off = u.unadjust_price_paise(12057, Decimal("0.5"), tick_paise=10, tol_paise=2)
    assert (raw, snapped, off) == (24114, False, 4)


# --- unadjust_bars: grouping, identity, un-provable ------------------------------------


def _bars(day: date, prices: list[int], vol: int = 1000) -> list[OneMinuteBar]:
    open_dt = datetime.combine(day, time(9, 15))
    return [
        OneMinuteBar(open_dt + timedelta(minutes=i), p, p + 10, p - 10, p, vol)
        for i, p in enumerate(prices)
    ]


def test_unadjust_bars_un_adjusts_old_day_and_leaves_recent_day() -> None:
    sym = "TCS"
    factors = [_bonus(sym, date(2018, 6, 1), Decimal("0.5"))]
    fetch = date(2026, 7, 25)
    old = _bars(date(2016, 10, 3), [120000], vol=2000)   # pre-bonus -> k_cum 0.5
    recent = _bars(date(2020, 1, 2), [200000], vol=2000)  # post-bonus -> identity
    result = u.unadjust_bars(old + recent, factors=factors, fetch_date=fetch, symbol=sym, tick_paise=5)
    by_day = {d.day: d for d in result.days}
    assert by_day[date(2016, 10, 3)].k_cum == Decimal("0.5")
    assert by_day[date(2020, 1, 2)].identity is True
    raw = {b.stamp.date(): b for b in result.raw_bars}
    assert raw[date(2016, 10, 3)].open_paise == 240000  # 120000 / 0.5
    assert raw[date(2016, 10, 3)].volume == 1000        # 2000 * 0.5
    assert raw[date(2020, 1, 2)].open_paise == 200000   # identity: unchanged
    assert raw[date(2020, 1, 2)].volume == 2000


def test_unadjust_bars_marks_a_demerger_span_unprovable() -> None:
    sym = "RELIANCE"
    factors = [_bonus(sym, date(2024, 10, 28), Decimal("0.5"))]  # the bonus we HAVE
    supp = [Suppression(sym, date(2023, 7, 20), KIND_DEMERGER, "Jio demerger: no factor")]
    fetch = date(2026, 7, 25)
    # a 2016 day: the demerger (2023) lies in (D, F] and has NO factor -> un-provable
    old = _bars(date(2016, 11, 1), [100000])
    # a 2024-10-25 day: the demerger is BEFORE it, only the bonus is in (D, F] -> provable
    recent = _bars(date(2024, 10, 25), [268700])
    result = u.unadjust_bars(old + recent, factors=factors, fetch_date=fetch, symbol=sym,
                             suppressions=supp)
    by_day = {d.day: d for d in result.days}
    assert by_day[date(2016, 11, 1)].provable is False   # demerger in window
    assert by_day[date(2024, 10, 25)].provable is True    # only the bonus in window
    assert result.unprovable_days == (date(2016, 11, 1),)


def test_systematic_unprovable_floor_moves_the_clamp() -> None:
    days = [
        u.DayUnadjust(date(2016, 10, 3), date(2026, 7, 25), Decimal("0.5"), False, False, 0, 0, 0, ""),
        u.DayUnadjust(date(2016, 10, 4), date(2026, 7, 25), Decimal("0.5"), False, False, 0, 0, 0, ""),
        u.DayUnadjust(date(2016, 10, 5), date(2026, 7, 25), Decimal("0.5"), False, False, 0, 0, 0, ""),
        u.DayUnadjust(date(2016, 10, 6), date(2026, 7, 25), Decimal("0.5"), False, False, 0, 0, 0, ""),
        u.DayUnadjust(date(2016, 10, 7), date(2026, 7, 25), Decimal("0.5"), False, False, 0, 0, 0, ""),
        u.DayUnadjust(date(2023, 8, 1), date(2026, 7, 25), Decimal("1"), True, True, 0, 0, 0, ""),
    ]
    assert u.systematic_unprovable_floor(days, min_run=5) == date(2023, 8, 1)
    # a lone un-provable day is not systematic -> no clamp move
    assert u.systematic_unprovable_floor(days[:1] + days[5:], min_run=5) is None


# --- the fetch-date the ledger records ------------------------------------------------


def test_window_ledger_round_trips_the_fetch_date(tmp_path: Path) -> None:
    store = MinuteStore.at(tmp_path / "m")
    store.record_window(WindowOutcome(
        symbol="TCS", window_start=date(2016, 10, 1), window_end=date(2016, 10, 28),
        outcome=WINDOW_PRESENT, candle_count=10, attempted_at=datetime(2026, 7, 25, 12, 0),
        fetch_date=date(2026, 7, 25),
    ))
    back = store.window_outcomes("TCS")[date(2016, 10, 1)]
    assert back.fetch_date == date(2026, 7, 25)


def test_ledger_written_before_fetch_date_column_reads_none(tmp_path: Path) -> None:
    """A ledger written by an older build (no fetch_date column) still reads -- fetch_date None."""
    old_schema = pa.schema([
        pa.field("symbol", pa.string(), nullable=False),
        pa.field("window_start", pa.date32(), nullable=False),
        pa.field("window_end", pa.date32(), nullable=False),
        pa.field("outcome", pa.string(), nullable=False),
        pa.field("candle_count", pa.int64()),
        pa.field("first_date", pa.date32()),
        pa.field("last_date", pa.date32()),
        pa.field("reason", pa.string()),
        pa.field("attempted_at", pa.timestamp("s")),
    ])
    store = MinuteStore.at(tmp_path / "m")
    path = store.ledger_path("TCS")
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table({
        "symbol": ["TCS"], "window_start": [date(2016, 10, 1)], "window_end": [date(2016, 10, 28)],
        "outcome": [WINDOW_PRESENT], "candle_count": [10], "first_date": [date(2016, 10, 3)],
        "last_date": [date(2016, 10, 28)], "reason": [None], "attempted_at": [datetime(2026, 7, 25, 12, 0)],
    }, schema=old_schema)
    pq.write_table(table, path)
    back = store.window_outcomes("TCS")[date(2016, 10, 1)]
    assert back.fetch_date is None and back.candle_count == 10


# --- ingest-path integration ----------------------------------------------------------


class FakeClient:
    def __init__(self, replies: list[object]) -> None:
        self._replies = list(replies)
        self.calls: list[tuple] = []

    def get_candles(self, token, interval, from_dt, to_dt, *, exchange="NSE"):  # type: ignore[no-untyped-def]
        self.calls.append((token, interval, from_dt, to_dt))
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return tuple(reply)


class FakeMaster:
    def token(self, symbol: str) -> str:
        return "11536"


_COLS = ["trade_date", "open_paise", "high_paise", "low_paise", "close_paise", "volume"]


class FakeDailyStore:
    def __init__(self, rows: dict[str, list[dict]]) -> None:
        self._rows = rows

    def daily(self, symbol: str, from_date: date, to_date: date, *, series=None) -> pd.DataFrame:
        rows = [r for r in self._rows.get(symbol.upper(), []) if from_date <= r["trade_date"] <= to_date]
        return pd.DataFrame(rows, columns=_COLS)


def test_backfill_unadjusts_on_ingest_and_records_fetch_date(tmp_path: Path) -> None:
    store = MinuteStore.at(tmp_path / "m")
    sf = mb.SymbolFactors(
        symbol="TCS",
        factors=(_bonus("TCS", date(2018, 6, 1), Decimal("0.5")),),
        tick_paise=None,
    )
    day = date(2016, 10, 3)
    # a fetched (ADJUSTED) bar: raw was 240000 price / 1000 vol, back-adjusted x0.5 / x2
    adjusted = [OneMinuteBar(datetime.combine(day, time(9, 15)), 120000, 120100, 119900, 120050, 2000)]
    client = FakeClient([adjusted])
    result = mb.backfill_symbol(client, FakeMaster(), store, "TCS", date(2016, 10, 1),
                                date(2016, 10, 28), symbol_factors=sf,
                                now=lambda: datetime(2026, 7, 25, 12, 0))
    stored = store.minutes("TCS", day)
    assert stored[0].open_paise == 240000   # 120000 / 0.5  (RAW recovered)
    assert stored[0].volume == 1000         # raw_volume = fetched x k_cum = 2000 * 0.5
    # the window ledger recorded the fetch date
    outcome = store.window_outcomes("TCS")[date(2016, 10, 1)]
    assert outcome.fetch_date == date(2026, 7, 25)
    assert result.unprovable_days == []


def test_rebuild_symbol_raw_in_place(tmp_path: Path) -> None:
    """An already-fetched (adjusted) store is un-adjusted to RAW in place using the recorded
    fetch date. A post-bonus (identity) day is counted but SKIPPED -- no needless rewrite."""
    store = MinuteStore.at(tmp_path / "m")
    old = date(2016, 10, 3)      # pre-bonus -> k_cum 0.5 -> rewritten
    recent = date(2020, 1, 2)    # post-bonus -> identity -> skipped, left unchanged
    store.write_bars("TCS", [OneMinuteBar(datetime.combine(old, time(9, 15)), 120000, 120100, 119900, 120050, 2000)])
    store.write_bars("TCS", [OneMinuteBar(datetime.combine(recent, time(9, 15)), 200000, 200100, 199900, 200050, 3000)])
    for ws, we in [(date(2016, 10, 1), date(2016, 10, 28)), (date(2019, 12, 30), date(2020, 1, 26))]:
        store.record_window(WindowOutcome(
            symbol="TCS", window_start=ws, window_end=we, outcome=WINDOW_PRESENT, candle_count=1,
            attempted_at=datetime(2026, 7, 25, 12, 0), fetch_date=date(2026, 7, 25),
        ))
    sf = mb.SymbolFactors("TCS", factors=(_bonus("TCS", date(2018, 6, 1), Decimal("0.5")),), tick_paise=None)
    res = mb.rebuild_symbol_raw(store, "TCS", sf)
    assert res.days_rewritten == 1 and res.unadjusted_days == 1 and res.identity_days == 1
    assert store.minutes("TCS", old)[0].open_paise == 240000     # un-adjusted to RAW (120000 / 0.5)
    assert store.minutes("TCS", recent)[0].open_paise == 200000  # identity: untouched


def test_gate1_by_year_before_fails_after_passes(tmp_path: Path) -> None:
    """The ruling's per-day PROOF: an adjusted 2016 day has ~2x the raw daily volume (gate-1
    fails); un-adjusting halves it back (gate-1 passes)."""
    store = MinuteStore.at(tmp_path / "m")
    day = date(2016, 10, 3)
    raw_daily_vol = 1000
    # fetched(adjusted) 1-min volume ~ 2x raw daily; one bar carrying it all for simplicity
    store.write_bars("TCS", [OneMinuteBar(datetime.combine(day, time(9, 15)), 120000, 120100, 119900, 120050, 2 * raw_daily_vol)])
    store.record_window(WindowOutcome(
        symbol="TCS", window_start=date(2016, 10, 1), window_end=date(2016, 10, 28),
        outcome=WINDOW_PRESENT, candle_count=1, attempted_at=datetime(2026, 7, 25, 12, 0),
        fetch_date=date(2026, 7, 25),
    ))
    daily = FakeDailyStore({"TCS": [{"trade_date": day, "open_paise": 240000, "high_paise": 240200,
                                     "low_paise": 239800, "close_paise": 240100, "volume": raw_daily_vol}]})
    sf = mb.SymbolFactors("TCS", factors=(_bonus("TCS", date(2018, 6, 1), Decimal("0.5")),), tick_paise=None)
    before = {y.year: y for y in mb.gate1_by_year(daily, store, "TCS")}
    after = {y.year: y for y in mb.gate1_by_year(daily, store, "TCS", symbol_factors=sf)}
    assert before[2016].passed == 0 and before[2016].total == 1   # adjusted volume fails gate-1
    assert after[2016].passed == 1 and after[2016].total == 1     # un-adjusted volume reconciles
