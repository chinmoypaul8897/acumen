"""Tests for the 1-minute backfill orchestration + the real chunk-4 minute loader (chunk 5A).

Offline: a fake candle client, a fake daily store (real pandas frames), and the real Parquet
minute store. Covers the clamp golden, resumability via the window ledger, the OPEN-8
adjustment probe (RAW / ADJUSTED / INDETERMINATE), and Rule 3 of the bias engine finally
reading real 1-minute data through :func:`acumen.minute_backfill.minute_loader`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from acumen import minute_backfill as mb
from acumen import quality_gates as qg
from acumen import smartapi_client as sac
from acumen.bias import Candle, evaluate_pair, BULLISH, BEARISH
from acumen.instrument_master import InstrumentMaster
from acumen.minute_store import MinuteStore, WINDOW_EMPTY, WINDOW_ERROR, WINDOW_PRESENT
from acumen.smartapi_client import OneMinuteBar, SmartApiError


# --- clamp golden --------------------------------------------------------------------


def test_clamp_start_holds_the_2016_10_floor() -> None:
    assert mb.clamp_start(date(2015, 1, 1)) == mb.MINUTE_DATA_FLOOR
    assert mb.clamp_start(date(2020, 1, 1)) == date(2020, 1, 1)
    assert mb.clamp_start(date(2015, 1, 1), first_data=date(2017, 10, 1)) == date(2017, 10, 1)


def test_requesting_pre_2016_09_returns_empty_without_error() -> None:
    """The chunk-5A clamp golden: a whole range before the floor plans NO windows."""
    assert mb.plan_windows(date(2016, 1, 1), date(2016, 9, 30)) == []
    assert mb.plan_windows(date(2010, 1, 1), date(2015, 12, 31)) == []


def test_plan_windows_clamps_the_start_to_the_floor() -> None:
    windows = mb.plan_windows(date(2016, 1, 1), date(2016, 11, 15))
    assert windows[0][0] == mb.MINUTE_DATA_FLOOR  # started at the floor, not 2016-01-01


def test_plan_windows_use_a_28_day_span_that_cannot_hit_the_8000_cap() -> None:
    """PoC-discovered ONE_MINUTE 8000-candle response cap: a 28-calendar-day window holds at
    most 20 weekdays (four whole weeks) -> <= 7500 candles < 8000, so it can never truncate."""
    windows = mb.plan_windows(date(2020, 1, 1), date(2020, 12, 31))
    for start, end in windows[:-1]:  # the last window is a short remainder
        assert (end - start).days + 1 == mb.ONE_MINUTE_WINDOW_DAYS == 28
    # the theoretical worst case (28 straight weekdays is impossible; 20 is the real max)
    assert 20 * 375 < sac.ONE_MINUTE_RESPONSE_CAP


# --- a fake candle client + a fake daily store ---------------------------------------


def _minutes(day: date, n: int = 3, base: int = 250000) -> list[OneMinuteBar]:
    open_dt = datetime.combine(day, time(9, 15))
    return [OneMinuteBar(open_dt + timedelta(minutes=i), base + i, base + 10 + i, base - 10 + i, base + i, 100 + i) for i in range(n)]


class FakeClient:
    """A scripted get_candles: each call pops the next reply (bars, [] or an exception)."""

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
    def __init__(self, tokens: dict[str, str]) -> None:
        self._tokens = tokens

    def token(self, symbol: str) -> str:
        try:
            return self._tokens[symbol.upper()]
        except KeyError:
            from acumen.instrument_master import InstrumentMasterError

            raise InstrumentMasterError(f"no {symbol}") from None

    def tick_size(self, symbol: str):  # pragma: no cover - not used here
        return Decimal("0.05")

    def __len__(self) -> int:  # pragma: no cover
        return len(self._tokens)


_DAILY_COLUMNS = ["trade_date", "open_paise", "high_paise", "low_paise", "close_paise", "volume"]


class FakeDailyStore:
    """A daily store double whose ``daily()`` returns real pandas frames filtered by range."""

    def __init__(self, rows: dict[str, list[dict]]) -> None:
        self._rows = rows

    def daily(self, symbol: str, from_date: date, to_date: date, *, series=None) -> pd.DataFrame:
        rows = [r for r in self._rows.get(symbol.upper(), []) if from_date <= r["trade_date"] <= to_date]
        return pd.DataFrame(rows, columns=_DAILY_COLUMNS)


# --- resumable backfill --------------------------------------------------------------


def test_backfill_stores_bars_and_records_window_outcomes(tmp_path: Path) -> None:
    store = MinuteStore.at(tmp_path / "m")
    master = FakeMaster({"TCS": "11536"})
    # one 28-day window [2016-10-01, 2016-10-28]: return two days of minutes
    bars = _minutes(date(2016, 10, 3)) + _minutes(date(2016, 10, 4))
    client = FakeClient([bars])
    result = mb.backfill_symbol(client, master, store, "TCS", date(2016, 10, 1), date(2016, 10, 28),
                                now=lambda: datetime(2026, 7, 25, 12, 0))
    assert result.ledger_summary[WINDOW_PRESENT] == 1
    assert store.has_day("TCS", date(2016, 10, 3)) and store.has_day("TCS", date(2016, 10, 4))
    assert result.first_stored_date == date(2016, 10, 3)


def test_empty_window_is_recorded_empty_and_not_refetched(tmp_path: Path) -> None:
    store = MinuteStore.at(tmp_path / "m")
    master = FakeMaster({"DIXON": "21690"})
    client = FakeClient([[]])  # before-listing: no candles
    mb.backfill_symbol(client, master, store, "DIXON", date(2016, 10, 1), date(2016, 10, 28),
                       now=lambda: datetime(2026, 7, 25, 12, 0))
    assert store.ledger_summary("DIXON")[WINDOW_EMPTY] == 1
    # a second run must NOT call the client again (settled empty)
    client2 = FakeClient([])
    mb.backfill_symbol(client2, master, store, "DIXON", date(2016, 10, 1), date(2016, 10, 28),
                       now=lambda: datetime(2026, 7, 25, 12, 0))
    assert client2.calls == []


def test_error_window_is_retried_on_the_next_run(tmp_path: Path) -> None:
    store = MinuteStore.at(tmp_path / "m")
    master = FakeMaster({"TCS": "11536"})
    # run 1: the window errors
    run1 = mb.backfill_symbol(FakeClient([SmartApiError("403 burst")]), master, store, "TCS",
                              date(2016, 10, 1), date(2016, 10, 28), now=lambda: datetime(2026, 7, 25, 12, 0))
    assert run1.ledger_summary[WINDOW_ERROR] == 1
    assert not store.has_day("TCS", date(2016, 10, 3))
    # run 2: the same window is retried and now succeeds
    bars = _minutes(date(2016, 10, 3))
    run2 = mb.backfill_symbol(FakeClient([bars]), master, store, "TCS",
                              date(2016, 10, 1), date(2016, 10, 28), now=lambda: datetime(2026, 7, 25, 12, 0))
    assert run2.windows_attempted == 1 and store.has_day("TCS", date(2016, 10, 3))
    assert store.ledger_summary("TCS")[WINDOW_PRESENT] == 1 and store.ledger_summary("TCS")[WINDOW_ERROR] == 0


def test_settled_windows_are_skipped_on_rerun(tmp_path: Path) -> None:
    store = MinuteStore.at(tmp_path / "m")
    master = FakeMaster({"TCS": "11536"})
    bars = _minutes(date(2016, 10, 3))
    mb.backfill_symbol(FakeClient([bars]), master, store, "TCS", date(2016, 10, 1), date(2016, 10, 28),
                       now=lambda: datetime(2026, 7, 25, 12, 0))
    client2 = FakeClient([])  # nothing scripted -> would IndexError if it fetched
    result = mb.backfill_symbol(client2, master, store, "TCS", date(2016, 10, 1), date(2016, 10, 28),
                                now=lambda: datetime(2026, 7, 25, 12, 0))
    assert client2.calls == [] and result.windows_attempted == 0


# --- gate helpers over the store ------------------------------------------------------


def test_gate1_for_day_reconciles_against_the_daily_store(tmp_path: Path) -> None:
    store = MinuteStore.at(tmp_path / "m")
    day = date(2016, 10, 3)
    bars = _minutes(day, n=5)
    store.write_bars("TCS", bars)
    minute_vol = sum(b.volume for b in bars)
    daily = FakeDailyStore({"TCS": [{"trade_date": day, "open_paise": 1, "high_paise": 1, "low_paise": 1,
                                     "close_paise": 1, "volume": minute_vol}]})
    result = mb.gate1_for_day(daily, store, "TCS", day)
    assert result is not None and result.passed and result.gap_pct == Decimal("0")


def test_gate1_for_day_none_when_no_daily_row(tmp_path: Path) -> None:
    store = MinuteStore.at(tmp_path / "m")
    store.write_bars("TCS", _minutes(date(2016, 10, 3)))
    daily = FakeDailyStore({})
    assert mb.gate1_for_day(daily, store, "TCS", date(2016, 10, 3)) is None


# --- OPEN-8 adjustment probe ----------------------------------------------------------


def _daily_row(day: date, o: int, h: int, l: int, c: int, v: int = 1000) -> dict:
    return {"trade_date": day, "open_paise": o, "high_paise": h, "low_paise": l, "close_paise": c, "volume": v}


def test_adjustment_probe_raw_verdict() -> None:
    # RELIANCE-style 1:1 bonus: pre-ex raw ~ 2655, ex-day raw ~ 1334 (k ~ 0.5). A RAW 1-min
    # feed shows the pre-ex day at ~2655 -> ratio ~ 1.0 -> RAW.
    pre, ex = date(2024, 10, 25), date(2024, 10, 28)
    daily = FakeDailyStore({"RELIANCE": [
        _daily_row(pre, 268700, 268870, 264400, 265570),
        _daily_row(ex, 133700, 135300, 132210, 133435),
    ]})
    minutes = [OneMinuteBar(datetime.combine(pre, time(9, 15)), 268700, 268870, 264400, 265570, 5)]
    client = FakeClient([minutes])
    master = FakeMaster({"RELIANCE": "2885"})
    probe = mb.adjustment_probe(client, master, daily, mb.AdjustmentEvent("RELIANCE", ex, "1:1 bonus"))
    assert probe.verdict == qg.VERDICT_RAW
    assert probe.pre_ex_day == pre


def test_adjustment_probe_adjusted_verdict() -> None:
    pre, ex = date(2024, 10, 25), date(2024, 10, 28)
    daily = FakeDailyStore({"RELIANCE": [
        _daily_row(pre, 268700, 268870, 264400, 265570),
        _daily_row(ex, 133700, 135300, 132210, 133435),
    ]})
    # a back-adjusted feed halves the pre-ex prices
    minutes = [OneMinuteBar(datetime.combine(pre, time(9, 15)), 134350, 134435, 132200, 132785, 5)]
    client = FakeClient([minutes])
    master = FakeMaster({"RELIANCE": "2885"})
    probe = mb.adjustment_probe(client, master, daily, mb.AdjustmentEvent("RELIANCE", ex, "1:1 bonus"))
    assert probe.verdict == qg.VERDICT_ADJUSTED


def test_adjustment_probe_indeterminate_without_minute_data() -> None:
    # KOTHARIPRO/GREENPLY case: no 1-min data before the ex-date (predates the floor).
    pre, ex = date(2016, 1, 4), date(2016, 1, 5)
    daily = FakeDailyStore({"KOTHARIPRO": [
        _daily_row(pre, 10000, 10100, 9900, 10000),
        _daily_row(ex, 6667, 6700, 6600, 6667),
    ]})
    client = FakeClient([[]])  # empty 1-min window
    master = FakeMaster({"KOTHARIPRO": "999"})
    probe = mb.adjustment_probe(client, master, daily, mb.AdjustmentEvent("KOTHARIPRO", ex, "bonus"))
    assert probe.verdict == qg.VERDICT_INDETERMINATE


def test_adjustment_probe_indeterminate_when_symbol_absent_from_master() -> None:
    daily = FakeDailyStore({})
    client = FakeClient([])
    master = FakeMaster({})  # GREENPLY not in the current master
    probe = mb.adjustment_probe(client, master, daily, mb.AdjustmentEvent("GREENPLY", date(2016, 1, 6), "split"))
    assert probe.verdict == qg.VERDICT_INDETERMINATE and client.calls == []


# --- the real chunk-4 minute loader drives Rule 3 -------------------------------------


def _outside_bar_pair() -> tuple[Candle, Candle]:
    """P (previous) and C (current): C is an outside bar closing inside P's body."""
    previous = Candle(open=200000, high=205000, low=200000, close=204000, day=date(2016, 10, 3))
    current = Candle(open=201000, high=206000, low=199000, close=202000, day=date(2016, 10, 4))
    return previous, current


def test_rule3_high_first_is_bullish_via_the_real_loader(tmp_path: Path) -> None:
    store = MinuteStore.at(tmp_path / "m")
    day = date(2016, 10, 4)
    open_dt = datetime.combine(day, time(9, 15))
    # minute 0 breaks P.high (206000 > 205000); minute 1 breaks P.low (199000 < 200000) LATER
    store.write_bars("SYNTH", [
        OneMinuteBar(open_dt, 204000, 206000, 203000, 205000, 10),          # high broken first
        OneMinuteBar(open_dt + timedelta(minutes=1), 200000, 201000, 199000, 200000, 10),  # low later
    ])
    loader = mb.minute_loader(store)
    previous, current = _outside_bar_pair()
    outcome = evaluate_pair(previous, current, lambda: loader("SYNTH", day), last_bias=None)
    assert outcome.bias == BULLISH  # high-first + close inside body -> bullish (CONTEXT 3.2 Rule 3)


def test_rule3_low_first_is_bearish_via_the_real_loader(tmp_path: Path) -> None:
    store = MinuteStore.at(tmp_path / "m")
    day = date(2016, 10, 4)
    open_dt = datetime.combine(day, time(9, 15))
    # minute 0 breaks P.low first; minute 1 breaks P.high later
    store.write_bars("SYNTH", [
        OneMinuteBar(open_dt, 200000, 201000, 199000, 200000, 10),          # low broken first
        OneMinuteBar(open_dt + timedelta(minutes=1), 204000, 206000, 203000, 205000, 10),  # high later
    ])
    loader = mb.minute_loader(store)
    previous, current = _outside_bar_pair()
    outcome = evaluate_pair(previous, current, lambda: loader("SYNTH", day), last_bias=None)
    assert outcome.bias == BEARISH


def test_minute_loader_returns_none_for_a_day_with_no_data(tmp_path: Path) -> None:
    store = MinuteStore.at(tmp_path / "m")
    loader = mb.minute_loader(store)
    assert loader("TCS", date(2016, 10, 3)) is None  # old-date carry fallback (R1-Q6)
