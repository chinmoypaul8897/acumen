"""CONTEXT 4.7's ORACLE-FREE battery (the Q-28 ruling, 08-Aug-2026).

This is the file that has to be right, because it is where the live mode's whole licence lives.
The ruling, verbatim in QUESTIONS.md: *"gates 1/1P exist to catch history being rewritten, and
today cannot be rewritten during today -- so a LIVE morning runs the ORACLE-FREE battery per
sweep (gate 2 incl. the Q-21(a) open test, Q-17 candle-level drops, candle validity)"*.

Two claims are load-bearing and each is attacked from both sides:

1. **The live battery accepts what it must accept.** A session in progress is missing most of
   its 375 minutes by construction, and the settled battery refuses exactly that shape -- which
   is what left a live morning with no POC for any symbol on any day and became Q-28. The one
   trigger set aside is the missing-minutes one, and it is set aside because it was never
   oracle-free: CONTEXT 4.5 fires it only *"on a day where gate 1 ALSO fails"*.
2. **The live battery still refuses what it must refuse.** Everything the ruling names stays:
   the Q-21(a) open test that 47 corrupt bars once walked past, duplicates, negative values.
   A live morning is not a morning with the gates turned off.

And the property that keeps the BACKTEST from moving at all: on a settled day the POC's licence
is gate 1's verdict, unchanged and identical, which is asserted rather than reasoned about.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from acumen import quality_gates as qg
from acumen import signal_engine as se
from acumen.minute_store import StoredBar

DAY = date(2026, 7, 17)


def bar(
    minute: int, *, o: int = 1000, h: int = 1010, low: int = 990, c: int = 1005, v: int = 100,
    symbol: str = "SYNTH",
) -> StoredBar:
    return StoredBar(
        symbol=symbol,
        stamp=datetime.combine(DAY, datetime.min.time()).replace(hour=9, minute=15)
        + timedelta(minutes=minute),
        open_paise=o, high_paise=h, low_paise=low, close_paise=c, volume=v,
    )


def session_prefix(count: int) -> tuple[StoredBar, ...]:
    """The first ``count`` minutes of the session -- what a live sweep actually holds."""
    return tuple(bar(index) for index in range(count))


# --- 1. what the live battery IS ----------------------------------------------------------------


def test_the_live_battery_runs_gate_2_and_names_gates_1_and_1P_as_UNRUN_not_failed() -> None:
    """The distinction the whole ruling turns on, in the object itself.

    ``None`` is not ``False`` here and the difference is the ruling: a settled day whose gate 1
    could not run is a day that failed to prove itself, and a live day whose gate 1 cannot run is
    a day that cannot yet be asked. Storing the second as a failure is precisely what refused
    every live symbol on every day before 08-Aug-2026.
    """
    gates = se.oracle_free_battery(DAY, session_prefix(120))

    assert gates.posture == se.POSTURE_LIVE
    assert gates.gate1 is None and gates.gate1p is None
    assert gates.volume_reconciled is None
    assert gates.relieved is False
    assert gates.gate2.passed
    assert gates.usable, "an intact live window is usable under CONTEXT 4.7"
    assert gates.refusal is None


def test_a_LIVE_PREFIX_is_accepted_where_the_SETTLED_battery_refuses_it(tmp_path: Path) -> None:
    """Q-28's own measurement, and its answer, side by side on the same bars.

    The settled battery over a 60-minute prefix is refused by gate 1 -- a fold of part of a
    session cannot reconcile against a whole session's published volume, at any hour before the
    close. That fact has not changed and this test still asserts it. What CONTEXT 4.7 changes is
    which battery a live morning runs over those same bars.
    """
    from test_backtest import ROW_SIZE, SYMBOL, TRADE_DAY, standard_world

    minute_store, daily_store, master, _cal = standard_world(tmp_path)
    pipeline = se.SignalPipeline(
        minute_store=minute_store, daily_store=daily_store, master=master, row_size=ROW_SIZE
    )
    prefix = minute_store.minutes(SYMBOL, TRADE_DAY)[:60]

    settled = pipeline.gate_day(SYMBOL, TRADE_DAY, prefix)
    assert not settled.usable
    assert settled.refusal == se.NOT_EVALUATED_GATE1, (
        "the Q-28 fact, unchanged: half a day of volume cannot reconcile a whole day's bhavcopy"
    )

    live = se.oracle_free_battery(TRADE_DAY, prefix)
    assert live.usable, "and CONTEXT 4.7 is what a live morning runs instead"
    assert live.refusal is None


def test_the_missing_minutes_trigger_does_not_fire_and_the_count_is_STILL_STATED() -> None:
    """Set aside, not swept away: an accepted window says how much of itself is absent.

    A live battery that accepted 120 of 375 minutes in silence would read exactly like a battery
    that had checked completeness and been satisfied. The trigger cannot fire (it is itself
    gate-1-derived, so it was never oracle-free), and the count reaches the operator anyway.
    """
    live = qg.integrity_gate(
        session_prefix(120), DAY, volume_reconciled=None, completeness_measurable=False
    )
    assert live.passed and not live.missing_excluded
    assert live.missing == 375 - 120
    assert "255 of 375" in live.liquidity_note
    assert "NOT MEASURABLE" in live.liquidity_note and "CONTEXT 4.7" in live.liquidity_note

    # ...and the settled reading of the same bars is unchanged, which is the control.
    settled = qg.integrity_gate(session_prefix(120), DAY, volume_reconciled=None)
    assert not settled.passed and settled.missing_excluded


def test_the_default_is_the_SETTLED_reading_so_no_stored_day_moves() -> None:
    """The parameter's default is the backtest's behaviour, byte for byte.

    Every existing caller passes no ``completeness_measurable`` at all. If the default were the
    live reading, 435,641 stored symbol-days would silently change verdict -- so the default is
    asserted here rather than assumed from where it is written.
    """
    for reconciled in (True, False, None):
        assert (
            qg.integrity_gate(session_prefix(120), DAY, volume_reconciled=reconciled)
            == qg.integrity_gate(
                session_prefix(120), DAY, volume_reconciled=reconciled,
                completeness_measurable=True,
            )
        )


# --- 2. what the live battery still REFUSES -----------------------------------------------------


def test_the_Q21a_OPEN_TEST_still_bites_on_a_live_window() -> None:
    """The enumeration the architect COMPLETED on 03-Aug-2026 is inside the live battery.

    47 vendor-corrupt bars once walked past the close-only list and one of them killed the
    chunk-9B run. A live morning is the one place nobody would notice, because there is no
    end-of-day battery in front of it -- so the open clause is exercised here explicitly.
    """
    bars = list(session_prefix(30))
    bars[7] = bar(7, o=2000, h=1010, low=990, c=1005)  # open ABOVE the high: impossible
    gates = se.oracle_free_battery(DAY, tuple(bars))

    assert not gates.usable
    assert gates.refusal == se.NOT_EVALUATED_GATE2
    assert gates.gate2.ohlc_violations == 1
    assert "open or close out of range" in gates.refusal_detail[1]


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda bars: bars + [bars[3]], "duplicate"),
        (lambda bars: bars[:5] + [bar(5, v=-1)] + bars[6:], "NEGATIVE"),
        (lambda bars: bars[:9] + [bar(9, h=100, low=900)] + bars[10:], "OHLC-sanity"),
    ],
    ids=["duplicate-stamp", "negative-volume", "high-below-low"],
)
def test_candle_validity_is_the_whole_of_gate_2s_own_enumeration(mutate, expected) -> None:
    """"Candle validity" is not a new test invented for live -- it is gate 2's own list.

    Each of the ruling's three remaining triggers is driven separately, so a future edit that
    quietly narrows the live battery to one of them turns this red.
    """
    gates = se.oracle_free_battery(DAY, tuple(mutate(list(session_prefix(20)))))
    assert not gates.usable
    assert expected in "; ".join(gates.gate2.reasons)


def test_a_Q17_STRAY_BAR_is_counted_and_never_kills_the_live_day() -> None:
    """Q-17 IS LAW and it is a CANDLE-level drop, in live exactly as in the lake.

    A pre-open or post-close stray is dropped where every consumer drops it and counted where
    every consumer counts it. Reading it as a day-killer would blank the screen for a stock whose
    only problem is a vendor timestamp.
    """
    stray = StoredBar(
        symbol="SYNTH", stamp=datetime(2026, 7, 17, 9, 7),  # before 09:15
        open_paise=1000, high_paise=1010, low_paise=990, close_paise=1005, volume=5,
    )
    gates = se.oracle_free_battery(DAY, (stray,) + session_prefix(30))
    assert gates.usable, "a stray candle is dropped, not a day-level refusal (CONTEXT 7-E2)"
    assert gates.gate2.out_of_session == 1, "and it is COUNTED, never silent"


# --- 3. the property that keeps the BACKTEST still -----------------------------------------------


def test_on_a_SETTLED_day_the_POC_licence_IS_gate_1s_verdict_unchanged() -> None:
    """The identity the whole change rests on, asserted over every settled shape.

    ``signal_engine.evaluate`` now hands ``poc_licence`` to the POC engine where it used to hand
    ``volume_reconciled``. If those two ever differ on a settled day, the ten-year ledger moves.
    They cannot, and here is the proof rather than the argument.
    """
    integrity = qg.integrity_gate(session_prefix(375), DAY, volume_reconciled=True)
    containment = qg.price_containment_gate(1010, 990, 1010, 990)
    for reconciled in (True, False, None):
        gates = se.DayGates(
            gate1=None if reconciled is None else qg.volume_gate(1000, 1000),
            relieved=False,
            volume_reconciled=reconciled,
            gate2=integrity,
            gate1p=containment,
        )
        assert gates.posture == se.POSTURE_SETTLED, "the default posture is the settled one"
        assert gates.poc_licence is gates.volume_reconciled


def test_a_SETTLED_DayGates_with_no_gate_1P_verdict_is_a_CONSTRUCTION_ERROR() -> None:
    """The invariant that makes ``gate1p`` safe to type as optional.

    Optional means "CONTEXT 4.7's live posture leaves it unrun" and nothing else. A settled day
    without a gate-1P verdict is not a day that passed price containment -- it is a bug, and it
    says so instead of reading as a pass.
    """
    gates = se.DayGates(
        gate1=None, relieved=False, volume_reconciled=None,
        gate2=qg.integrity_gate(session_prefix(375), DAY, volume_reconciled=True),
        gate1p=None,
    )
    with pytest.raises(ValueError, match="must carry a gate-1P verdict"):
        _ = gates.refusal
    assert not gates.usable


def test_the_live_battery_is_the_SHARED_function_and_not_a_copy_of_it() -> None:
    """CONTEXT 4.7 says "the same battery, minus the gates that cannot run" -- so it must BE it.

    A live battery that re-implemented duplicate detection, or the OHLC clauses, or the Q-17
    count, would drift from the backtest's the first time either was fixed. This is checked at
    the source: the function's whole body is one call to :func:`quality_gates.integrity_gate` and
    one :class:`DayGates` construction.
    """
    import ast
    import inspect
    from textwrap import dedent

    tree = ast.parse(dedent(inspect.getsource(se.oracle_free_battery)))
    calls = {
        node.func.id if isinstance(node.func, ast.Name) else
        (node.func.attr if isinstance(node.func, ast.Attribute) else "")
        for node in ast.walk(tree) if isinstance(node, ast.Call)
    }
    assert calls == {"integrity_gate", "DayGates"}, (
        f"the live battery must delegate, not re-implement; it calls {sorted(calls)}"
    )
