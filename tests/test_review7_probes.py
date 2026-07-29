"""REVIEW_7 reviewer probes -- the chunk-7 QC review's kept adversarial tests.

Written by the REVIEW session, not the builder. Each one exists because a MUTANT of the shipped
engine survived the build's own suite: the behaviour below is what CONTEXT.md states and what
nothing in `tests/test_signals.py` / `tests/test_signal_engine.py` pinned.

Every expected value is HAND-COMPUTED in the docstring from CONTEXT 3.4, independently of the
engine, so a reader can check the number without running the code.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from fractions import Fraction
from pathlib import Path

from acumen import quality_gates as gates
from acumen import signal_engine as se
from acumen import signals as sig
from acumen.aggregate import Bar
from acumen.bhavcopy import DailyRow
from acumen.bias import BULLISH
from acumen.bias_engine import DailyBias
from acumen.daily_store import DailyStore
from acumen.instrument_master import InstrumentMaster
from acumen.minute_store import MinuteStore

DAY = date(2026, 7, 20)


def R(rupees: float) -> int:
    return int(round(rupees * 100))


def POC(rupees: float) -> Fraction:
    return Fraction(R(rupees))


def bar(ordinal: int, o: float, h: float, l: float, c: float) -> Bar:
    return Bar(
        stamp=sig.bar_open_stamp(DAY, ordinal),
        open_paise=R(o), high_paise=R(h), low_paise=R(l), close_paise=R(c),
        volume=1_000,
    )


# ==============================================================================================
# 1. The gap boundary's SHORT MIRROR -- the Q-15-taught case, on the bearish side
# ==============================================================================================


def test_a_short_entry_candle_whose_high_touches_the_poc_is_NOT_a_gap() -> None:
    """CONTEXT 3.4 mirror paragraph: "Gap entry = entry candle's high < POC (never traded
    at/above it)". STRICTLY below. A candle whose high TOUCHES the POC did trade at the POC, so
    it is a NORMAL entry and the stop is that candle's own HIGH.

    This is the exact mirror of the boundary CONTEXT v1.4 8 says F1/F2 now teach on the long
    side (low == POC -> NORMAL). The long side is pinned by the F1/F2 goldens; the short side was
    pinned by nothing, and a `<` -> `<=` mutation of the mirror predicate survived the build's
    whole suite.

    HAND-COMPUTED at POC 1985 on a bearish day:

    * reference = the 11:15 close 1990 > 1985 -> ARMED (the bearish mirror: above arms);
    * the candle closing 11:30 closes 1978, strictly below the POC while ARMED -> TRIGGER,
      entry 1978;
    * its high is **1985**, which is NOT strictly below the POC 1985, so the gap rule does NOT
      fire -> **normal stop = the entry candle's HIGH = 1985**, risk 7,
      **TP = 1978 - 3 x 7 = 1957**;
    * exit: the 11:45 candle's low 1955 <= 1957 -> TARGET (its high 1980 never reaches 1985).

    Under the inclusive mutant the stop would instead be the previous candle's close 1990
    (risk 12, TP 1942) -- a different trade in size, stop and target.
    """
    bars = (
        bar(8, 1992, 1994, 1988, 1990),
        bar(9, 1984, 1985, 1975, 1978),
        bar(10, 1978, 1980, 1955, 1957),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.SHORT, poc_paise=POC(1985))

    entry = result.entry
    assert entry is not None
    assert not entry.gap_entry
    assert entry.stop_source == sig.STOP_FROM_ENTRY_CANDLE_SHORT
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(1978), R(1985), R(1957))
    assert entry.risk_paise == R(7)
    assert result.exit_event is not None and result.exit_event.kind == sig.EXIT_TARGET


# ==============================================================================================
# 2. Exit touches are INCLUSIVE on both levels and both sides (CONTEXT 3.4-5)
# ==============================================================================================


def test_a_candle_whose_low_exactly_equals_the_stop_exits_at_the_stop() -> None:
    """CONTEXT 3.4-5: "candle low <= SL -> exit at SL". The operator is inclusive: a candle that
    exactly TOUCHES the stop is a stop-out, not a survivor. Nothing in the build's suite put a
    low exactly on the stop, so the strict mutant survived.

    HAND-COMPUTED at POC 2032: reference 2025 arms; the 11:30 candle closes 2037 -> entry 2037,
    low 2032 touches the POC so this is a NORMAL entry, stop 2032, risk 5, TP 2052. The 11:45
    candle's low is **exactly 2032** and its high 2040 is short of the target -> STOP.
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2033, 2038, 2032, 2037),
        bar(10, 2037, 2040, 2032, 2035),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2032))

    assert result.entry is not None and result.entry.stop_paise == R(2032)
    assert result.exit_event is not None
    assert result.exit_event.kind == sig.EXIT_STOP and not result.exit_event.both_touched
    assert result.exit_event.close_stamp == sig.bar_close_stamp(DAY, 10)


def test_a_candle_whose_high_exactly_equals_the_target_exits_at_the_target() -> None:
    """CONTEXT 3.4-5: "candle high >= TP -> exit at TP", inclusive.

    HAND-COMPUTED at POC 2032: entry 2037, stop 2032, risk 5, TP 2052. The 11:45 candle's high is
    **exactly 2052** and its low 2035 never reaches the stop -> TARGET.
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2033, 2038, 2032, 2037),
        bar(10, 2037, 2052, 2035, 2050),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2032))

    assert result.entry is not None and result.entry.target_paise == R(2052)
    assert result.exit_event is not None and result.exit_event.kind == sig.EXIT_TARGET


def test_the_short_mirror_an_exact_touch_of_the_stop_and_of_the_target() -> None:
    """Both inclusive operators on the bearish side (CONTEXT 3.4-5 mirrored: high >= SL,
    low <= TP).

    HAND-COMPUTED at POC 1985: reference 1990 arms; the 11:30 candle closes 1980 -> entry 1980,
    high 1988 is not below the POC so the stop is that high 1988, risk 8, TP = 1980 - 24 = 1956.

    * stop case: the 11:45 candle's high is **exactly 1988** (low 1975, nowhere near 1956) -> STOP;
    * target case: on the same entry, a 11:45 candle whose low is **exactly 1956** (high 1984,
      short of the stop) -> TARGET.
    """
    head = (bar(8, 1992, 1994, 1988, 1990), bar(9, 1987, 1988, 1979, 1980))

    stop_day = sig.evaluate_day(
        head + (bar(10, 1980, 1988, 1975, 1978),), day=DAY, side=sig.SHORT, poc_paise=POC(1985)
    )
    assert stop_day.entry is not None and stop_day.entry.stop_paise == R(1988)
    assert stop_day.exit_event is not None and stop_day.exit_event.kind == sig.EXIT_STOP
    assert not stop_day.exit_event.both_touched

    target_day = sig.evaluate_day(
        head + (bar(10, 1980, 1984, 1956, 1958),), day=DAY, side=sig.SHORT, poc_paise=POC(1985)
    )
    assert target_day.entry is not None and target_day.entry.target_paise == R(1956)
    assert target_day.exit_event is not None and target_day.exit_event.kind == sig.EXIT_TARGET


# ==============================================================================================
# 3. The gap stop is the last candle that TRADED, not the previous grid stamp (decision B160)
# ==============================================================================================


def test_the_gap_stop_skips_a_tradeless_quarter_hour_to_the_last_traded_close() -> None:
    """CONTEXT 3.4-3 calls the gap stop "the last traded price before the jump = the previous
    15-min candle's close". Under the completeness ruling an ABSENT grid stamp is a quarter-hour
    in which nothing traded, so the last traded price is the candle before it -- decision B160,
    which the build recorded but pinned only inside an unsizable-day fixture.

    HAND-COMPUTED at POC 2030 on a bullish day:

    * reference = the 11:15 close 2029 < 2030 -> ARMED;
    * NOTHING trades 11:15-11:30, so that grid stamp holds no candle at all;
    * the candle closing 11:45 opens 2035 and never trades at or below the POC (low 2034 > 2030)
      and closes 2042 -> TRIGGER, entry 2042, **GAP** entry;
    * the last traded 15-minute close before the jump is therefore the **11:00-11:15 candle's
      2029**, not a value invented for the empty stamp -> stop 2029, risk 13,
      **TP = 2042 + 39 = 2081**;
    * exit: the 12:00 candle touches neither -> square off.
    """
    bars = (
        bar(8, 2031, 2032, 2027, 2029),
        bar(10, 2035, 2044, 2034, 2042),
        bar(11, 2042, 2050, 2040, 2048),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    entry = result.entry
    assert entry is not None and entry.gap_entry
    assert entry.stop_source == sig.STOP_FROM_PREVIOUS_CLOSE
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(2042), R(2029), R(2081))
    assert entry.risk_paise == R(13)
    assert result.exit_event is not None and result.exit_event.kind == sig.EXIT_SQUARE_OFF


# ==============================================================================================
# 4. CONTEXT 4.6: ALL THREE gates are required for "usable"
# ==============================================================================================

SYMBOL = "SYNTH"
TICK_PAISE = 10


def _minutes(day: date = DAY) -> list:
    """The chunk-7 test day: a 120-bar profile window plus a trigger candle. Shape only -- this
    probe cares about the gate battery, not the signal."""
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Minute:
        stamp: datetime
        open_paise: int
        high_paise: int
        low_paise: int
        close_paise: int
        volume: int

    out = []
    start = datetime.combine(day, time(9, 15))
    for i in range(120):
        stamp = start + timedelta(minutes=i)
        if i == 0:
            out.append(Minute(stamp, R(2000.00), R(2000.50), R(1999.50), R(2000.00), 10))
        else:
            out.append(Minute(stamp, R(2000.00), R(2000.00), R(2000.00), R(2000.00), 100))
    # one minute AFTER the profile window whose high is far above anything the exchange printed
    out.append(Minute(datetime.combine(day, time(11, 16)), R(1999.50), R(2010.00), R(1999.50), R(2001.00), 300))
    return out


def test_a_day_that_fails_only_gate_1p_is_not_usable(tmp_path: Path) -> None:
    """CONTEXT 4.6: "Gate battery (per symbol-day, ALL THREE required for 'usable')".

    `DayGates.usable` is the property that states that sentence. The build's suite asserts it
    True on a clean day and False on a gate-1 failure, but never on a day whose ONLY failure is
    gate 1P -- so deleting `gate1p.passed` from the conjunction survived the whole suite. Here
    the volume reconciles exactly and the integrity gate passes, and the raw bhavcopy high is
    below the stored fold's high, so gate 1P is the only refusal.
    """
    minutes = _minutes()
    minute_store = MinuteStore.at(tmp_path / "minute_store")
    minute_store.write_bars(SYMBOL, minutes)
    daily_store = DailyStore.at(tmp_path / "daily_store")
    daily_store.write_rows(
        DAY,
        [
            DailyRow(
                trade_date=DAY, symbol=SYMBOL, series="EQ",
                open_paise=minutes[0].open_paise,
                high_paise=R(2000.50),  # the exchange never printed 2010.00 -> gate 1P fails
                low_paise=min(m.low_paise for m in minutes),
                close_paise=minutes[-1].close_paise,
                volume=sum(m.volume for m in minutes),
            )
        ],
    )
    pipeline = se.SignalPipeline(
        minute_store=minute_store,
        daily_store=daily_store,
        master=InstrumentMaster.from_rows(
            [{"symbol": f"{SYMBOL}-EQ", "token": "1", "exch_seg": "NSE", "tick_size": str(TICK_PAISE * 100)}]
        ),
        row_size=24,
    )
    result = pipeline.stock_day(
        SYMBOL, DAY,
        bias=DailyBias(trade_date=DAY, bias=BULLISH, tradeable=True, rule="rule-1-breakout", detail=""),
    )

    day_gates = result.gates
    assert day_gates is not None
    assert day_gates.gate1 is not None and day_gates.gate1.passed  # volume reconciles
    assert day_gates.gate2.passed                                   # integrity is clean
    assert not day_gates.gate1p.passed and day_gates.gate1p.cause == gates.GATE1P_ABOVE
    assert not day_gates.usable, "CONTEXT 4.6 requires ALL THREE gates for a usable day"
    assert day_gates.refusal == se.NOT_EVALUATED_GATE1P
    assert not result.evaluated
