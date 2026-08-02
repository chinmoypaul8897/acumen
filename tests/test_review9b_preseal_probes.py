"""REVIEW_9B_PRESEAL -- the re-seal reviewer's kept probes (02-Aug-2026).

Written while reviewing `6b0436d..f4c019a` (the 9B-prep + Q-18 arc) against both personas.
Every test here closes a hole the review's own attacks found, or PINS a property the review
proved by argument and would otherwise leave unpinned. Nothing here weakens or replaces an
existing test.

WHAT EACH GROUP IS FOR

1. **The Q-17 candle-level drop -- the two mutation survivors.** The reviewer's 10-mutant
   matrix over `in_session_bars` and its four consumption points caught 8. The two survivors
   (compute the PROFILE on the unfiltered day; hand the SIGNAL engine the unfiltered minute
   bars) are EQUIVALENT rather than untested defects, and the proofs are structural, not
   empirical -- so they are pinned here as properties. If either premise ever moves (the POC
   window opening before 09:15, or E10's fallback gaining a lower bound), these fail and the
   equivalence argument has to be made again.

2. **The Q-19 seal guard -- the boundary as a property, not as cases.** The build pins eight
   named ages; this sweeps every age from a year in the future to a year in the past and
   asserts the partition itself: a 404 is EITHER pending OR sealed, never both and never
   neither, and the switch happens at exactly one place.

3. **The Q-20 pin -- what the name-only guard actually protects.** `build_runner` compares
   `Path(master_path).name` against the configured pin. That is safe only because the path it
   was handed is then DISCARDED and the master is re-resolved under the cache; pinned here so
   the guard cannot quietly become the thing that decides which file is read.

4. **The v1.5 residual caveat -- the manifest's `caveat_basis` is genuinely checkable.** B239
   added the field so the "caveat quotes its own register" invariant can pass on a run smaller
   than the universe. This asserts the round trip on register figures shaped like the real
   ones, including the half-even rounding that made 41.9% -> 42.0% a correction rather than a
   restatement.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from acumen import backtest as bt
from acumen import poc as poc_engine
from acumen import signal_engine as se
from acumen import signals as sig
from acumen.aggregate import aggregate_15min, in_session_bars
from acumen.bhavcopy import (
    MIN_SEAL_AGE_DAYS,
    OUTCOME_NOT_FOUND,
    OUTCOME_PENDING,
    seals_as_non_trading_day,
)
from acumen.config import load_config

from tests.test_signal_engine import (
    DAY,
    ROW_SIZE,
    SYMBOL,
    TICK_PAISE,
    Minute,
    R,
    at,
    bullish,
    build,
    daily_row_for,
    synthetic_minutes,
)

# ==============================================================================================
# 1. The Q-17 candle-level drop -- the two EQUIVALENT mutants, pinned as properties
# ==============================================================================================


def _strays(day: date = DAY) -> list[Minute]:
    """One pre-open stray and one post-close stray -- the two shapes Q-17 measured.

    09:14 is RELIANCE 2017-04-28, the bar that killed the pre-fix smoke run; 15:32 is the
    2018-11-05 shape. Both carry real-looking prices and volume, because a stray the engine
    could dismiss on its numbers would not be a test of the FILTER.
    """
    return [
        Minute(at(time(9, 14), day), R(2100.00), R(2100.00), R(2100.00), R(2100.00), 25_015),
        Minute(at(time(15, 32), day), R(1900.00), R(1900.00), R(1900.00), R(1900.00), 4_242),
    ]


def test_filtering_before_the_profile_cannot_change_it_because_the_window_opens_at_0915() -> None:
    """**Mutation survivor M4, proved EQUIVALENT.**

    Handing `day_profile` the UNFILTERED day survives every test in the suite, and it must:
    CONTEXT 3.3's window is the stamps 09:15..11:14, and `is_session_time` admits exactly
    09:15..15:29 for a 1-minute bar. An out-of-session stamp is therefore either BELOW the
    window's open or ABOVE its close, and can never fall inside it -- so the pre-filter is
    value-neutral for the profile by construction, not by coincidence.

    Asserted rather than argued, on prices far outside the synthetic day's range: a stray at
    Rs 2,100 would raise `top` and a stray at Rs 1,900 would lower `bottom`, either of which
    re-sizes the whole row grid and moves the POC.
    """
    clean = synthetic_minutes()
    dirty = sorted(clean + _strays(), key=lambda bar: bar.stamp)
    session, dropped = in_session_bars(dirty)
    assert dropped == 2

    kwargs = dict(row_size=ROW_SIZE, tick_paise=TICK_PAISE, volume_reconciled=True)
    filtered = poc_engine.day_profile(session, DAY, **kwargs)
    unfiltered = poc_engine.day_profile(dirty, DAY, **kwargs)

    assert filtered.poc_paise == unfiltered.poc_paise
    assert (filtered.grid.top_paise, filtered.grid.bottom_paise) == (
        unfiltered.grid.top_paise,
        unfiltered.grid.bottom_paise,
    )
    assert filtered.grid.total_ticks == unfiltered.grid.total_ticks
    assert len(filtered.grid) == len(unfiltered.grid)
    # ...and the profile really is the CLEAN day's, not merely self-consistent
    assert filtered.poc_paise == poc_engine.day_profile(clean, DAY, **kwargs).poc_paise


def test_e10s_fallback_can_never_reach_a_pre_open_stray_while_a_profile_exists() -> None:
    """**Mutation survivor M6, proved EQUIVALENT.**

    E10's reference fallback takes the LAST 1-minute close at or before 11:14. An
    out-of-session stamp at or before 11:14 must be earlier than 09:15, so it can only be the
    last such bar on a day with NO in-session bar before 11:15 -- and such a day has an empty
    CONTEXT 3.3 window, gets no POC, and never reaches the signal engine at all.

    Both halves are asserted: with the window populated the fallback ignores the stray, and
    with the window emptied the profile refuses the day before any reference is resolved.
    """
    day = DAY
    stray = _strays(day)[0]  # 09:14
    assert stray.stamp.time() < time(9, 15)

    # (a) the window is populated -> the fallback resolves to an IN-SESSION bar
    minutes = sorted(synthetic_minutes(day) + [stray], key=lambda bar: bar.stamp)
    session, dropped = in_session_bars(minutes)
    assert dropped == 1
    bars = aggregate_15min(session)
    without_reference_candle = tuple(
        bar for bar in bars if bar.stamp != sig.bar_open_stamp(day, sig.REFERENCE_BAR)
    )
    assert len(without_reference_candle) == len(bars) - 1  # the E10 branch is really taken

    unfiltered = sig.evaluate_day(
        without_reference_candle,
        day=day,
        side=sig.LONG,
        poc_paise=poc_engine.day_profile(
            session, day, row_size=ROW_SIZE, tick_paise=TICK_PAISE, volume_reconciled=True
        ).poc_paise,
        minute_bars=minutes,          # <-- the MUTANT's argument
    )
    filtered = sig.evaluate_day(
        without_reference_candle,
        day=day,
        side=sig.LONG,
        poc_paise=poc_engine.day_profile(
            session, day, row_size=ROW_SIZE, tick_paise=TICK_PAISE, volume_reconciled=True
        ).poc_paise,
        minute_bars=session,          # <-- what the code does
    )
    assert unfiltered.reference_source == filtered.reference_source == sig.REFERENCE_FROM_MINUTES
    assert unfiltered.reference_paise == filtered.reference_paise
    assert unfiltered.reference_paise != stray.close_paise

    # (b) empty the window and the day never reaches the engine: no POC, no reference
    only_stray_before_1115 = [stray] + [
        bar for bar in synthetic_minutes(day) if bar.stamp.time() >= time(11, 15)
    ]
    kept, _ = in_session_bars(only_stray_before_1115)
    profile = poc_engine.day_profile(
        kept, day, row_size=ROW_SIZE, tick_paise=TICK_PAISE, volume_reconciled=True
    )
    assert profile.poc_paise is None


def test_a_stray_bar_changes_nothing_but_the_flag_and_the_gates_still_see_it(
    tmp_path: Path,
) -> None:
    """The whole pipeline on a day with BOTH stray shapes, against the same day without them.

    The ruling has three clauses and this asserts all three at once: dropped at the CANDLE
    level (the day is still evaluated and every number is the clean day's), counted (the count
    reaches `StockDay.out_of_session_dropped`), and *gates continue to see the whole stored day
    for volume* -- which is why the raw daily row here reconciles against the strays INCLUDED.
    """
    clean = synthetic_minutes()
    dirty = sorted(clean + _strays(), key=lambda bar: bar.stamp)

    clean_day = build(tmp_path / "clean", clean, daily_row_for(clean)).stock_day(
        SYMBOL, DAY, bias=bullish()
    )
    # the bhavcopy row is built over the WHOLE stored day, strays included -- chunk-5B semantics
    dirty_day = build(tmp_path / "dirty", dirty, daily_row_for(dirty)).stock_day(
        SYMBOL, DAY, bias=bullish()
    )

    assert clean_day.out_of_session_dropped == 0
    assert dirty_day.out_of_session_dropped == 2      # counted, never silent
    assert dirty_day.evaluated and dirty_day.reason == se.EVALUATED   # flagged, NOT fatal

    assert dirty_day.profile.poc_paise == clean_day.profile.poc_paise
    assert dirty_day.bars == clean_day.bars
    assert dirty_day.signal.outcome == clean_day.signal.outcome
    assert dirty_day.signal.entry == clean_day.signal.entry
    assert dirty_day.signal.exit_event == clean_day.signal.exit_event

    # the gates were handed the UNFILTERED day: the stored minute count includes both strays,
    # and gate 1 reconciles against a daily volume that includes them too.
    assert dirty_day.minute_count == clean_day.minute_count + 2
    assert dirty_day.gates.volume_reconciled is True and dirty_day.gates.usable
    assert dirty_day.gates.gate2.out_of_session == 2


# ==============================================================================================
# 2. The Q-19 seal guard -- the partition, swept
# ==============================================================================================


@pytest.mark.parametrize("age", list(range(-365, 366, 7)) + [-1, 0, 6, 7, 8, 9])
def test_a_404_is_either_pending_or_sealed_and_the_switch_is_at_exactly_one_age(
    age: int,
) -> None:
    """CONTEXT 4.6 (v1.5) / Q-19 as a PARTITION rather than as a list of cases.

    A 404 whose date is more than :data:`MIN_SEAL_AGE_DAYS` calendar days old is final;
    anything younger -- including the future -- is deferred. Never both, never neither, and
    the boundary sits between age 7 and age 8 for every date in a two-year window, including
    across weekends, month ends and the leap day.
    """
    run_date = date(2026, 7, 31)
    day = run_date - timedelta(days=age)
    seals = seals_as_non_trading_day(day, run_date)
    assert seals is (age > MIN_SEAL_AGE_DAYS)
    # the two outcomes really are the two branches, and they are distinct constants
    assert OUTCOME_PENDING != OUTCOME_NOT_FOUND


def test_the_boundary_is_the_same_across_a_leap_day_and_a_year_end() -> None:
    """Calendar arithmetic, not weekday arithmetic (decision B228) -- proved on the two dates
    where a hand-rolled day count is most likely to be one out."""
    for run_date in (date(2028, 3, 3), date(2027, 1, 5)):
        assert seals_as_non_trading_day(run_date - timedelta(days=7), run_date) is False
        assert seals_as_non_trading_day(run_date - timedelta(days=8), run_date) is True


# ==============================================================================================
# 3. The Q-20 pin -- the name-only guard is safe only because the path is discarded
# ==============================================================================================


def test_the_pin_is_resolved_under_the_cache_and_a_same_named_file_elsewhere_is_ignored(
    tmp_path: Path,
) -> None:
    """`build_runner`'s guard compares only `Path(master_path).name`. That is correct ONLY
    because the argument is then thrown away and the master is re-resolved under the cache --
    otherwise a file with the pinned NAME sitting anywhere on disk would be read.

    Pinned at the resolver, where the property lives: two files with the SAME pinned name and
    DIFFERENT ticks, and `pinned_master` reads the one under the cache it was given.
    """
    import json

    pin = load_config(include_env=False).instrument_master

    def write(root: Path, tick: str) -> Path:
        home = root / "instrument_master"
        home.mkdir(parents=True, exist_ok=True)
        path = home / pin
        path.write_text(
            json.dumps(
                [
                    {
                        "exch_seg": "NSE",
                        "symbol": "PINTEST-EQ",
                        "token": "1",
                        "tick_size": tick,
                        "name": "PINTEST",
                        "lotsize": "1",
                    }
                ]
            ),
            encoding="utf-8",
        )
        return path

    real = write(tmp_path / "cache", "5.000000")
    write(tmp_path / "impostor", "100.000000")

    master, path, _digest = bt.pinned_master(tmp_path / "cache", pin)
    assert path == real
    assert master.by_symbol["PINTEST"].tick_size_paise == 5


# ==============================================================================================
# 4. CONTEXT 4.6 (v1.5) -- the manifest's caveat is recomputable from its own basis
# ==============================================================================================


def test_the_caveat_is_recomputable_from_the_basis_the_manifest_carries() -> None:
    """B239 + B232, asserted end to end on register figures shaped like the real ones.

    IOC's rebuilt entry is 1,024 / 2,436 -- 42.036%, which rounds half-even to **42.0%**, not
    to the 41.9% the frozen string carried. TATASTEEL's is 1,604 / 2,436 = 65.845% -> 65.8%.
    The point of the field is that a reader holding only the manifest can redo this; the point
    of this test is that the redo really does reproduce the sentence.
    """
    basis = {
        "IOC": bt.ResidualEntry("IOC", "settled", 1_024, 2_436, 1, ""),
        "TATASTEEL": bt.ResidualEntry("TATASTEEL", "settled", 1_604, 2_436, 1, ""),
    }
    caveat = bt.residual_caveat(basis)
    assert "IOC (42.0% price-proven)" in caveat
    assert "TATASTEEL (65.8% price-proven)" in caveat
    assert "41.9%" not in caveat

    # a register that LOSES one of the two subjects says so rather than reading as an all-clear
    partial = bt.residual_caveat({"IOC": basis["IOC"]})
    assert "TATASTEEL (ABSENT from the register)" in partial
