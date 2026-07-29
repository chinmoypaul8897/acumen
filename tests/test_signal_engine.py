"""The chunk-7 orchestration (`acumen.signal_engine`): bias -> gates -> POC -> signal.

The pure engine is tested in `test_signals.py`; this file tests the WIRING, which is where a
backtest silently goes wrong: the wrong tick, the wrong window, a gate that is not recomputed,
a POC that is rounded on its way across a module boundary, or a day that is evaluated when the
data says it must not be.

Everything runs against REAL store objects (a Parquet minute store and a Parquet daily store in
`tmp_path`), not mocks, because the thing under test is precisely how the stores are read.

**The synthetic day**, used by nearly every test below and hand-derivable end to end:

* tick 10 paise, Row Size 24 (CONTEXT 3.3);
* the profile window (09:15..11:14) holds 120 one-minute bars -- 119 point bars at exactly
  Rs 2000.00 and one wider first minute running Rs 1999.50..Rs 2000.50. So `bottom` = 199950
  paise, `top` = 200050, `totalTicks` = 10, and since 10 ticks over 24 requested rows floors
  `tpr` to 1, the profile is **10 rows of one tick**. Every point bar lands in the row
  `[200000, 200010)`, which is therefore the busiest, and its midpoint is the **POC =
  200005 paise = Rs 2000.05**;
* the 11:00-11:15 candle is made of point bars, so the **reference closes at 200000**, below
  the POC -> **ARMED**;
* the candle closing 11:30 runs 199900..200120 and closes **200100**, strictly above the POC ->
  **TRIGGER**. Its low 199900 is below the POC, so this is a normal entry: **stop 199900**,
  **risk 200 paise**, **target 200100 + 3 x 200 = 200700**;
* the candle closing 11:45 reaches 200800 >= 200700 -> **target hit**.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from fractions import Fraction
from pathlib import Path

import pytest

from acumen import poc as poc_engine
from acumen import quality_gates as gates
from acumen import signal_engine as se
from acumen import signals as sig
from acumen.aggregate import aggregate_15min
from acumen.bhavcopy import DailyRow
from acumen.bias import BEARISH, BULLISH
from acumen.bias_engine import DailyBias
from acumen.daily_store import DailyStore
from acumen.instrument_master import InstrumentMaster
from acumen.minute_store import MinuteStore

SYMBOL = "SYNTH"
DAY = date(2026, 7, 20)
TICK_PAISE = 10
ROW_SIZE = 24

#: The POC the synthetic window produces -- hand-derived in the module docstring and asserted
#: against the POC engine itself in `test_the_poc_is_the_poc_engines_own_answer`.
EXPECTED_POC = Fraction(200_005)


@dataclass(frozen=True)
class Minute:
    """One 1-minute bar, in the shape `MinuteStore.write_bars` accepts."""

    stamp: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int


def R(rupees: float) -> int:
    return int(round(rupees * 100))


def at(t: time, day: date = DAY) -> datetime:
    return datetime.combine(day, t)


def synthetic_minutes(day: date = DAY) -> list[Minute]:
    """The day described in the module docstring."""
    minutes: list[Minute] = []
    window_open = at(time(9, 15), day)
    for i in range(120):  # 09:15..11:14 -- the CONTEXT 3.3 profile window
        stamp = window_open + timedelta(minutes=i)
        if i == 0:
            minutes.append(Minute(stamp, R(2000.00), R(2000.50), R(1999.50), R(2000.00), 10))
        else:
            minutes.append(Minute(stamp, R(2000.00), R(2000.00), R(2000.00), R(2000.00), 100))
    # the candle closing 11:30: opens 2000.00, dips to 1999.00, closes 2001.00 -> TRIGGER
    minutes += [
        Minute(at(time(11, 15), day), R(2000.00), R(2000.50), R(1999.00), R(1999.50), 200),
        Minute(at(time(11, 16), day), R(1999.50), R(2001.20), R(1999.50), R(2001.00), 300),
        Minute(at(time(11, 29), day), R(2001.00), R(2001.00), R(2001.00), R(2001.00), 50),
    ]
    # the candle closing 11:45 reaches 2008.00 -> the target
    minutes.append(Minute(at(time(11, 30), day), R(2001.00), R(2008.00), R(2001.00), R(2007.50), 400))
    return minutes


def daily_row_for(minutes: list[Minute], day: date = DAY, **override) -> DailyRow:
    """The RAW bhavcopy row that reconciles with ``minutes`` exactly (gate 1 gap 0.000%) and
    contains their price fold exactly (gate 1P at zero excess on both sides)."""
    fields = dict(
        trade_date=day,
        symbol=SYMBOL,
        series="EQ",
        open_paise=minutes[0].open_paise,
        high_paise=max(m.high_paise for m in minutes),
        low_paise=min(m.low_paise for m in minutes),
        close_paise=minutes[-1].close_paise,
        volume=sum(m.volume for m in minutes),
    )
    fields.update(override)
    return DailyRow(**fields)


def build(
    tmp_path: Path,
    minutes: list[Minute] | None,
    row: DailyRow | None,
    *,
    tick_paise: int = TICK_PAISE,
) -> se.SignalPipeline:
    minute_store = MinuteStore.at(tmp_path / "minute_store")
    daily_store = DailyStore.at(tmp_path / "daily_store")
    if minutes:
        minute_store.write_bars(SYMBOL, minutes)
    if row is not None:
        daily_store.write_rows(row.trade_date, [row])
    master = InstrumentMaster.from_rows(
        [
            {
                "exch_seg": "NSE",
                "symbol": f"{SYMBOL}-EQ",
                "token": "99999",
                "tick_size": f"{tick_paise}.000000",
                "name": SYMBOL,
                "lotsize": "1",
            }
        ]
    )
    return se.SignalPipeline(
        minute_store=minute_store, daily_store=daily_store, master=master, row_size=ROW_SIZE
    )


def bullish(day: date = DAY) -> DailyBias:
    return DailyBias(trade_date=day, bias=BULLISH, tradeable=True, rule="rule-1-breakout", detail="")


def happy(tmp_path: Path) -> se.StockDay:
    minutes = synthetic_minutes()
    pipeline = build(tmp_path, minutes, daily_row_for(minutes))
    return pipeline.stock_day(SYMBOL, DAY, bias=bullish())


# ==============================================================================================
# The happy path, end to end
# ==============================================================================================


def test_a_clean_day_runs_bias_gates_poc_and_the_signal_end_to_end(tmp_path: Path) -> None:
    """The whole chunk-7 wiring on one stock-day, with every number hand-derived in the module
    docstring: POC 200005 -> reference 200000 ARMS -> the 11:30 close 200100 TRIGGERS -> stop
    199900 (the entry candle's own low, which is below the POC, so no gap) -> risk 200 ->
    target 200700 -> the 11:45 candle reaches 200800 and takes it.
    """
    result = happy(tmp_path)

    assert result.evaluated and result.reason == se.EVALUATED
    assert result.side == sig.LONG
    assert result.profile is not None and result.profile.poc_paise == EXPECTED_POC

    signal = result.signal
    assert signal is not None
    assert signal.reference_paise == 200_000
    assert signal.reference_source == sig.REFERENCE_FROM_CANDLE
    assert signal.initial_state == sig.STATE_ARMED
    assert signal.outcome == sig.OUTCOME_ENTERED and signal.consumed

    entry = signal.entry
    assert entry is not None
    assert entry.close_stamp == at(time(11, 30))
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (200_100, 199_900, 200_700)
    assert entry.risk_paise == 200 and not entry.gap_entry
    assert signal.exit_event is not None and signal.exit_event.kind == sig.EXIT_TARGET
    assert signal.exit_event.close_stamp == at(time(11, 45))
    assert result.traded


def test_the_poc_is_the_poc_engines_own_answer_and_is_never_rounded(tmp_path: Path) -> None:
    """The POC crosses two module boundaries (poc -> pipeline -> signals) and must arrive
    unchanged and EXACT. Recomputed here straight from the same minutes with the chunk-6 engine.
    """
    minutes = synthetic_minutes()
    pipeline = build(tmp_path, minutes, daily_row_for(minutes))
    result = pipeline.stock_day(SYMBOL, DAY, bias=bullish())

    independent = poc_engine.day_profile(
        pipeline.minute_store.minutes(SYMBOL, DAY),
        DAY,
        row_size=ROW_SIZE,
        tick_paise=TICK_PAISE,
        volume_reconciled=True,
    )
    assert independent.poc_paise == EXPECTED_POC
    assert result.signal is not None
    assert result.signal.poc_paise == independent.poc_paise
    assert isinstance(result.signal.poc_paise, Fraction)


def test_the_tick_comes_from_the_instrument_master_and_changes_the_poc(tmp_path: Path) -> None:
    """CONTEXT 3.3/4.3: the tick is per SYMBOL, from the instrument master, never hardcoded.
    The proof that the pipeline really reads it: the same minutes at a 50-paise tick build a
    different grid and a different POC.

    HAND-DERIVED at tick 50: the range 199950..200050 is 100 paise = 2 ticks, so `tpr` floors to
    1 and there are 2 rows -- [199950, 200000) and [200000, 200050]. The point bars at 200000
    land in the upper row, whose midpoint is 200025 = Rs 2000.25.
    """
    minutes = synthetic_minutes()
    pipeline = build(tmp_path, minutes, daily_row_for(minutes), tick_paise=50)
    result = pipeline.stock_day(SYMBOL, DAY, bias=bullish())

    assert result.profile is not None
    assert result.profile.poc_paise == Fraction(200_025)
    assert result.profile.poc_paise != EXPECTED_POC


def test_the_15_minute_bars_are_the_aggregators_own_output(tmp_path: Path) -> None:
    """CONTEXT 7-E1: 15-minute bars are AGGREGATED from the stored minutes, never fetched. The
    bars the signal engine saw must be exactly what `aggregate_15min` produces from the store.
    """
    minutes = synthetic_minutes()
    pipeline = build(tmp_path, minutes, daily_row_for(minutes))
    result = pipeline.stock_day(SYMBOL, DAY, bias=bullish())

    expected = aggregate_15min(pipeline.minute_store.minutes(SYMBOL, DAY))
    assert result.bars == expected
    # ...and E12's stamping is what it is: the 11:15-stamped bar CLOSES at 11:30.
    stamps = {bar.stamp.time() for bar in result.bars}
    assert time(11, 0) in stamps and time(11, 15) in stamps


def test_a_bearish_day_takes_the_short_side_only(tmp_path: Path) -> None:
    """CONTEXT 3.4: the bias picks the side and nothing else does.

    HAND-DERIVED on the SAME candles as the long case. A bearish bias mirrors every comparison:
    the reference 200000 is BELOW the POC 200005, which on a short day is WAIT-ABOVE (not
    ARMED); the 11:30 close 200100 is above the POC, which on a short day ARMS rather than
    triggers; and no later candle ever closes below the POC, so the day ends ARMED with no
    qualifying cross and nothing consumed. The identical candles that produce a long entry
    produce no short at all.
    """
    minutes = synthetic_minutes()
    pipeline = build(tmp_path, minutes, daily_row_for(minutes))
    result = pipeline.stock_day(
        SYMBOL,
        DAY,
        bias=DailyBias(trade_date=DAY, bias=BEARISH, tradeable=True, rule="rule-1-breakout", detail=""),
    )

    assert result.side == sig.SHORT
    assert result.signal is not None
    assert result.signal.initial_state == sig.STATE_WAIT_ABOVE
    assert result.signal.transitions[0].state_after == sig.STATE_ARMED  # the mirror: above ARMS
    assert result.signal.final_state == sig.STATE_ARMED
    assert result.signal.outcome == sig.OUTCOME_ARMED_NO_CROSS
    assert not result.signal.consumed and not result.traded


# ==============================================================================================
# The CONTEXT 4.6 gate battery -- recomputed per day, and each refusal counted apart
# ==============================================================================================


def test_a_clean_day_passes_all_three_gates(tmp_path: Path) -> None:
    result = happy(tmp_path)
    day_gates = result.gates
    assert day_gates is not None and day_gates.usable and day_gates.refusal is None
    assert day_gates.gate1 is not None and day_gates.gate1.passed and day_gates.gate1.gap_pct == 0
    assert day_gates.gate2.passed
    assert day_gates.gate1p.passed
    assert not day_gates.relieved


def test_a_gate_1_volume_failure_stops_the_day_before_any_signal(tmp_path: Path) -> None:
    """CONTEXT 4.5 gate 1 / 7-E3. The bhavcopy says 20,000 shares traded and the minutes account
    for 12,860 -- a 35.7% shortfall, far outside the [-0.1%, +5.0%] band and past the auction
    relief branch's 20% sanity cap, so the day is excluded and NOT evaluated.
    """
    minutes = synthetic_minutes()
    pipeline = build(tmp_path, minutes, daily_row_for(minutes, volume=20_000))
    result = pipeline.stock_day(SYMBOL, DAY, bias=bullish())

    assert not result.evaluated and result.reason == se.NOT_EVALUATED_GATE1
    assert result.signal is None and result.profile is None
    assert result.gates is not None and not result.gates.usable
    assert result.gates.gate1 is not None and not result.gates.gate1.passed
    assert not result.gates.relieved


def test_a_gate_1p_price_failure_stops_the_day_before_any_signal(tmp_path: Path) -> None:
    """CONTEXT 4.6 / QUESTIONS.md Q-14 -- the reason this gate exists at all.

    The volume reconciles perfectly (gap 0.000%), so gate 1 passes and gate 2 passes with it.
    But the exchange's own daily high for the day is Rs 2000.00 while the stored minutes reach
    Rs 2008.00 -- impossible on raw prices, and the exact shape (a day whose 1-minute prices sit
    on the wrong scale while its volume reconciles) that passed the pre-Q-14 battery. Gate 1P
    catches it and the day is excluded under its OWN reason, never folded into gate 1's.
    """
    minutes = synthetic_minutes()
    pipeline = build(tmp_path, minutes, daily_row_for(minutes, high_paise=R(2000.00)))
    result = pipeline.stock_day(SYMBOL, DAY, bias=bullish())

    assert not result.evaluated and result.reason == se.NOT_EVALUATED_GATE1P
    assert result.reason == gates.REASON_GATE1P
    assert result.signal is None
    day_gates = result.gates
    assert day_gates is not None
    assert day_gates.gate1 is not None and day_gates.gate1.passed  # volume was fine
    assert day_gates.gate2.passed
    assert not day_gates.gate1p.passed
    assert day_gates.gate1p.cause == gates.GATE1P_ABOVE


def test_a_day_with_no_raw_daily_row_fails_gate_1p_and_not_gate_1(tmp_path: Path) -> None:
    """The Q-14 ruling in as many words: "a day with no raw daily row cannot be price-proven and
    FAILS". Gate 1 did not FAIL on such a day -- it could not RUN -- so counting it under gate 1
    would be exactly the folding the ruling forbids.
    """
    minutes = synthetic_minutes()
    pipeline = build(tmp_path, minutes, None)
    result = pipeline.stock_day(SYMBOL, DAY, bias=bullish())

    assert not result.evaluated and result.reason == se.NOT_EVALUATED_GATE1P
    day_gates = result.gates
    assert day_gates is not None
    assert day_gates.gate1 is None and day_gates.volume_reconciled is None
    assert not day_gates.gate1p.passed and day_gates.gate1p.cause == gates.GATE1P_NO_ORACLE


def test_a_gate_2_integrity_failure_stops_the_day_before_any_signal(tmp_path: Path) -> None:
    """CONTEXT 4.5 gate 2: any duplicate stamp excludes the day, whatever gate 1 says.

    The duplicate carries ZERO volume on purpose, so the day still reconciles perfectly and
    gate 1 passes -- which isolates gate 2 as the only refusal.
    """
    minutes = synthetic_minutes()
    row = daily_row_for(minutes)
    duplicate = Minute(at(time(11, 16)), R(1999.50), R(2001.20), R(1999.50), R(2001.00), 0)
    pipeline = build(tmp_path, minutes + [duplicate], row)
    result = pipeline.stock_day(SYMBOL, DAY, bias=bullish())

    assert not result.evaluated and result.reason == se.NOT_EVALUATED_GATE2
    day_gates = result.gates
    assert day_gates is not None
    assert day_gates.gate1 is not None and day_gates.gate1.passed
    assert not day_gates.gate2.passed and day_gates.gate2.duplicates == 1


def test_the_gate_battery_is_recomputed_from_the_stores_not_looked_up(tmp_path: Path) -> None:
    """CONTEXT 4.6's chunk-9 duty, which chunk 7 is the first to carry: "recompute gate 1P per
    day (pure function, both stores local -- there is no per-day exclusion file)".

    The proof is behavioural: nothing but the two stores is ever consulted, so CHANGING the raw
    daily row -- and nothing else -- flips the verdict on an unchanged minute store.
    """
    minutes = synthetic_minutes()
    pipeline = build(tmp_path, minutes, daily_row_for(minutes))
    assert pipeline.stock_day(SYMBOL, DAY, bias=bullish()).evaluated

    pipeline.daily_store.write_rows(DAY, [daily_row_for(minutes, low_paise=R(2005.00))])
    again = pipeline.stock_day(SYMBOL, DAY, bias=bullish())
    assert not again.evaluated and again.reason == se.NOT_EVALUATED_GATE1P
    assert again.gates is not None and again.gates.gate1p.cause == gates.GATE1P_BELOW


def test_a_thin_days_auction_shortfall_is_relieved_and_the_day_still_trades(tmp_path: Path) -> None:
    """The auction-relief branch (QUESTIONS.md Q-12 addendum 2, decision B122) is part of the
    battery and the pipeline must carry it, or a legitimate thin day is silently dropped.

    The bhavcopy counts 14,000 shares against the minutes' 12,860 -- an 8.1% shortfall, above
    the +5.0% ceiling -- but the day's extremes and its opening print match the exchange's own
    record EXACTLY, which is the ruling's evidence that nothing was lost. The day is relieved,
    gate 2 is handed `volume_reconciled=True` with it, and the signal is evaluated.
    """
    minutes = synthetic_minutes()
    pipeline = build(tmp_path, minutes, daily_row_for(minutes, volume=14_000))
    result = pipeline.stock_day(SYMBOL, DAY, bias=bullish())

    day_gates = result.gates
    assert day_gates is not None
    assert day_gates.gate1 is not None and not day_gates.gate1.passed  # the strict band is not widened
    assert day_gates.relieved and day_gates.volume_reconciled is True
    assert result.evaluated and result.traded


# ==============================================================================================
# The bias gate, and the POC gate
# ==============================================================================================


def test_a_suppressed_day_is_never_evaluated(tmp_path: Path) -> None:
    """CONTEXT 3.2: across a demerger (or a Q-6 tier-2 rights) ex-date there is no bias update
    AND no trade in that stock that day."""
    minutes = synthetic_minutes()
    pipeline = build(tmp_path, minutes, daily_row_for(minutes))
    result = pipeline.stock_day(
        SYMBOL,
        DAY,
        bias=DailyBias(
            trade_date=DAY, bias=BULLISH, tradeable=False, rule="suppressed", detail="",
            suppressed=True, suppression_reason="demerger",
        ),
    )

    assert not result.evaluated and result.reason == se.NOT_EVALUATED_SUPPRESSED
    assert result.signal is None and result.side is None


def test_an_unseeded_day_is_never_evaluated(tmp_path: Path) -> None:
    """CONTEXT 3.2 seeding: before any rule has fired there is no bias and no trading."""
    minutes = synthetic_minutes()
    pipeline = build(tmp_path, minutes, daily_row_for(minutes))
    result = pipeline.stock_day(
        SYMBOL, DAY,
        bias=DailyBias(trade_date=DAY, bias=None, tradeable=False, rule="no-data", detail=""),
    )

    assert not result.evaluated and result.reason == se.NOT_EVALUATED_NO_BIAS
    assert result.signal is None


def test_a_day_with_no_poc_is_never_evaluated(tmp_path: Path) -> None:
    """CONTEXT 3.3 / 7-E4: no POC -> no trading that stock-day. Here nothing traded before
    11:15 at all, so the profile window is empty and has no top or bottom to build rows from.
    """
    minutes = [m for m in synthetic_minutes() if m.stamp.time() >= time(11, 15)]
    pipeline = build(tmp_path, minutes, daily_row_for(minutes))
    result = pipeline.stock_day(SYMBOL, DAY, bias=bullish())

    assert not result.evaluated
    assert result.reason.startswith(se.NOT_EVALUATED_NO_POC)
    assert poc_engine.NO_POC_EMPTY_WINDOW in result.reason
    assert result.profile is not None and result.profile.poc_paise is None
    assert result.signal is None


def test_a_day_the_store_never_ingested_is_recorded_as_such(tmp_path: Path) -> None:
    pipeline = build(tmp_path, None, None)
    result = pipeline.stock_day(SYMBOL, DAY, bias=bullish())

    assert not result.evaluated and result.reason == se.NOT_EVALUATED_NO_MINUTES
    assert result.gates is None and result.signal is None


def test_every_refusal_has_its_own_reason_so_the_counts_partition_the_days(tmp_path: Path) -> None:
    """CONTEXT 7-E3 asks for excluded days to be COUNTED. That only works if a day carries
    exactly one reason and the reasons are distinct strings, so chunk 9's tally cannot
    double-count a day that fails two ways at once.
    """
    reasons = {
        se.NOT_EVALUATED_NO_MINUTES,
        se.NOT_EVALUATED_GATE1,
        se.NOT_EVALUATED_GATE2,
        se.NOT_EVALUATED_GATE1P,
        se.NOT_EVALUATED_NO_BIAS,
        se.NOT_EVALUATED_SUPPRESSED,
        se.NOT_EVALUATED_NO_POC,
        se.EVALUATED,
    }
    assert len(reasons) == 8

    # a day that fails gate 1 AND has no bias reports the GATE, in the battery's own order
    minutes = synthetic_minutes()
    pipeline = build(tmp_path, minutes, daily_row_for(minutes, volume=20_000))
    both = pipeline.stock_day(
        SYMBOL, DAY,
        bias=DailyBias(trade_date=DAY, bias=None, tradeable=False, rule="no-data", detail=""),
    )
    assert both.reason == se.NOT_EVALUATED_GATE1


# ==============================================================================================
# Purity of the boundary: the orchestration may do I/O, the engines may not
# ==============================================================================================


def test_the_orchestration_never_writes_to_either_store(tmp_path: Path) -> None:
    """chunk 7 READS the lake; the backfill owns writing it. Structural, in the same shape as
    decision B120's guard on the chunk-6 evidence generator."""
    import inspect

    source = inspect.getsource(se)
    for forbidden in ("write_bars", "write_rows", "record_window", "record_outcome", "ingest("):
        assert forbidden not in source, f"{forbidden} must not appear in signal_engine.py"


def test_the_pure_engines_are_not_reached_through_any_io_in_signals(tmp_path: Path) -> None:
    """CONTEXT 6 keeps `signals` pure and puts the I/O here. The import direction proves it:
    `signal_engine` imports `signals`, and `signals` imports nothing that touches a store."""
    import inspect

    assert "import" in inspect.getsource(se)
    signal_source = inspect.getsource(sig)
    for io_module in ("minute_store", "daily_store", "instrument_master", "smartapi_client"):
        assert io_module not in signal_source
