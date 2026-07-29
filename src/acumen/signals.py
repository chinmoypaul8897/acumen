"""The signal engine: CONTEXT 3.4, as PURE functions (candles + POC in, signal events out).

This is the trader's intraday state machine, implemented EXACTLY as CONTEXT 3.4 spells it and
in the order it spells it. The strategy is frozen (CLAUDE.md rule 2); a deviation here is a
defect even if it looks smarter, so every operator is written character-for-character from the
spec, the bearish mirror is taken from CONTEXT 3.4's own explicit mirror paragraph rather than
hand-derived, and nothing that the spec does not say appears in a predicate.

**One stock-day at a time.** Direction comes from the day's bias (CONTEXT 3.4: bullish day ->
longs only, bearish day -> shorts only); candle COLOUR is irrelevant everywhere -- only closes
matter (R1-Q12). The POC comes from :mod:`acumen.poc` as an exact
:class:`~fractions.Fraction` of paise, which may legally sit half a paisa off the tick grid
(CONTEXT 3.3 / 7-E11): it is compared at FULL PRECISION here and NEVER rounded.

**The state machine (bullish day; bearish is the exact mirror CONTEXT 3.4 writes out).**

1. **Reference** = the CLOSE of the 11:00-11:15 candle -- by CONTEXT 7-E12's stamping, the bar
   OPEN-stamped 11:00, which is the LAST candle of the CONTEXT 3.3 profile window. Missing on
   an otherwise valid day -> the last available 1-minute close at or before the 11:14 stamp
   (E10); none available -> no trade.

   * reference < POC -> **ARMED**
   * reference > POC -> **WAIT-BELOW** (a later close STRICTLY below POC arms it; == POC does
     not arm)
   * reference == POC -> **no side yet**: wait, and the first 15-minute candle that closes
     strictly above or strictly below the POC SETS the side and only sets it -- it is never
     itself the entry (trader Q34b + Round-3 Q41 option A). First distinct close below ->
     ARMED; first distinct close above -> WAIT-BELOW (the Entry-2 path).

2. **Trigger** = the first candle closing at 11:30 or later, up to and including the close at
   15:00, that closes STRICTLY above the POC **while the state is ARMED**. Entry = that
   candle's close (R1-Q14).

   * a close == POC while ARMED is NOT a trigger: the state stays ARMED and nothing is
     consumed (CONTEXT 3.4-2, R2-Q34c);
   * closes above the POC while still WAIT-BELOW do not count and consume nothing -- "first
     cross" is counted from the ARMED state only;
   * the first qualifying cross CONSUMES the stock-day even if the trade turns out unsizable.
     One trade per stock-day, no re-entry (R1-Q16).

3. **Stop** = the entry candle's LOW, exactly, no buffer (R1-Q15). **Gap entry** -- the entry
   candle's low is above the POC, i.e. it opened beyond the POC and never traded at or below
   it (R1-Q13b) -- takes the previous 15-minute candle's CLOSE instead (R2-Q33 option b).
   `entry == stop` cannot be sized -> no trade, day consumed, logged.

4. **Target** = entry + 3 x (entry - stop).

5. **Exit events**, from the candle AFTER the entry candle (CONTEXT 7-E7: the entry price IS
   that candle's close, so the entry candle itself cannot trigger anything): low <= stop ->
   stop hit; high >= target -> target hit; BOTH in one candle -> the stop wins (R1-Q20);
   neither by the candle closing at 15:15 -> square off at that candle's close (R1-Q18).
   This module only MARKS the exit; chunk 8's simulator prices it and does the money.

PURE: no I/O, no network, no clock reads, no float anywhere. Prices are integer paise
(CONTEXT 7-E11) and the POC is an exact Fraction, so every comparison here is exact and none of
them is a float equality. Every session stamp is DERIVED from the 09:15 session grid and a bar
ORDINAL rather than typed as a clock literal, so the reference candle and the profile window
cannot drift apart (the reference is the profile window's last candle, by construction).

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from fractions import Fraction
from typing import Protocol, Sequence

from .bias import BEARISH, BULLISH
from .calendar import SESSION_OPEN

# --- the session grid, by ORDINAL (CONTEXT 7-E12; no clock literals in this module) ---------

#: Minutes per strategy candle. CONTEXT 3.4 works on 15-minute candles.
CANDLE_MINUTES: int = 15

#: 09:15..15:15 open-stamps, i.e. the candles closing 09:30..15:30.
BARS_PER_SESSION: int = 25

#: The REFERENCE candle (CONTEXT 3.4-1): the 8th candle of the session closes at 11:15. It is
#: also the LAST candle of the CONTEXT 3.3 profile window -- the same 8 candles, which is why
#: this is an ordinal and not a typed-in time (Q42 confirmed the 8-candle window).
REFERENCE_BAR: int = 8

#: The first candle ELIGIBLE to trigger: the 9th closes at 11:30 (CONTEXT 3.4-2, "the
#: 11:15-11:30 candle is the first eligible").
FIRST_TRIGGER_BAR: int = 9

#: The LAST candle eligible to trigger: the 23rd closes at 15:00 (R2-Q30).
LAST_TRIGGER_BAR: int = 23

#: The SQUARE-OFF candle: the 24th closes at 15:15 (R1-Q17/Q18). It can exit a position but can
#: never open one, and the 25th candle (closing 15:30) is never looked at at all.
SQUARE_OFF_BAR: int = 24

# --- vocabulary ------------------------------------------------------------------------------

#: Trade direction, from the day's bias (CONTEXT 3.4: bullish -> longs only, bearish -> shorts).
LONG: str = "long"
SHORT: str = "short"

#: States. WAIT-BELOW is the bullish day's wait; WAIT-ABOVE is its bearish mirror (CONTEXT 3.4).
STATE_ARMED: str = "armed"
STATE_WAIT_BELOW: str = "wait-below"
STATE_WAIT_ABOVE: str = "wait-above"
#: reference == POC: no side yet (trader Q34b + Round-3 Q41-A). Resolved by the first distinct
#: close, which SETS the side and is never itself the entry.
STATE_SIDE_UNSET: str = "side-unset"
#: No reference could be resolved at all (E10's "none available -> no trade").
STATE_NO_REFERENCE: str = "no-reference"

#: How the reference was obtained -- printed in the evidence pack so no number is unattributed.
REFERENCE_FROM_CANDLE: str = "close of the 11:00-11:15 candle"
REFERENCE_FROM_MINUTES: str = "E10 fallback: last 1-minute close at or before the 11:14 stamp"
REFERENCE_NONE: str = "none available"

#: Day outcomes. Exactly one is set on every :class:`SignalDay`.
OUTCOME_ENTERED: str = "entered"
OUTCOME_NO_BARS: str = "no-trade-no-15-minute-candles"
OUTCOME_NO_REFERENCE: str = "no-trade-no-reference-available"
OUTCOME_SIDE_NEVER_SET: str = "no-trade-side-never-set"
OUTCOME_NEVER_ARMED: str = "no-trade-never-armed"
OUTCOME_ARMED_NO_CROSS: str = "no-trade-armed-but-no-qualifying-close"
#: A qualifying cross happened and CONSUMED the day, but the trade cannot be sized.
OUTCOME_UNSIZABLE: str = "consumed-unsizable"

#: Where the stop came from (CONTEXT 3.4-3).
STOP_FROM_ENTRY_CANDLE: str = "entry candle low"
STOP_FROM_ENTRY_CANDLE_SHORT: str = "entry candle high"
STOP_FROM_PREVIOUS_CLOSE: str = "previous 15-minute candle close (gap entry)"

#: Exit event kinds. The simulator (chunk 8) prices these; nothing here computes money.
EXIT_STOP: str = "stop-loss-hit"
EXIT_TARGET: str = "target-hit"
EXIT_SQUARE_OFF: str = "square-off-at-the-15:15-close"

#: CONTEXT 3.4-4: target = entry +/- 3 x risk.
TARGET_RISK_MULTIPLE: int = 3

#: Where a close sits relative to the POC. The three-way answer, because CONTEXT 3.4 treats
#: "exactly on the POC" as its own case everywhere (it neither arms, nor triggers, nor sets a
#: side) and a two-way predicate would silently fold it into one of the others.
ABOVE_POC: str = "above"
BELOW_POC: str = "below"
AT_POC: str = "at"


class SignalError(ValueError):
    """The inputs handed to the signal engine are not a usable stock-day."""


class _Bar(Protocol):
    """Anything with the 15-minute bar fields -- so this pure module imports no I/O type."""

    stamp: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int


class _MinuteBar(Protocol):
    """Anything with the 1-minute fields the E10 reference fallback needs."""

    stamp: datetime
    close_paise: int


# --- grid helpers (PURE) ---------------------------------------------------------------------


def bar_open_stamp(day: date, ordinal: int) -> datetime:
    """The OPEN-stamp of the ``ordinal``-th 15-minute candle of ``day`` (1-based). PURE.

    Ordinal 1 opens at 09:15 and closes at 09:30; ordinal 25 opens at 15:15 and closes at
    15:30 (CONTEXT 7-E12). Deriving every stamp from the session open means no time in this
    module is typed in twice.
    """
    if not isinstance(ordinal, int) or isinstance(ordinal, bool):
        raise SignalError(f"bar ordinal must be a whole number, got {ordinal!r}.")
    if not 1 <= ordinal <= BARS_PER_SESSION:
        raise SignalError(
            f"bar ordinal {ordinal} is outside the session's {BARS_PER_SESSION} candles."
        )
    return datetime.combine(day, SESSION_OPEN) + timedelta(
        minutes=CANDLE_MINUTES * (ordinal - 1)
    )


def bar_close_stamp(day: date, ordinal: int) -> datetime:
    """When the ``ordinal``-th 15-minute candle of ``day`` CLOSES (CONTEXT 7-E12). PURE."""
    return bar_open_stamp(day, ordinal) + timedelta(minutes=CANDLE_MINUTES)


def reference_cutoff_stamp(day: date) -> datetime:
    """The last 1-minute OPEN-stamp E10's fallback may read: the 11:14 stamp. PURE.

    E10 says "the last available 1-min close <= 11:14". Derived, not typed: the reference
    candle closes at 11:15 and a 1-minute bar stamped 11:14 is the last one that closes then.
    """
    return bar_close_stamp(day, REFERENCE_BAR) - timedelta(minutes=1)


def poc_side(close_paise: int, poc_paise: Fraction) -> str:
    """Where a close sits relative to the POC: :data:`ABOVE_POC` / :data:`BELOW_POC` /
    :data:`AT_POC`. PURE, exact -- integer paise against an exact Fraction, never a float."""
    if close_paise > poc_paise:
        return ABOVE_POC
    if close_paise < poc_paise:
        return BELOW_POC
    return AT_POC


def side_for_bias(bias: str | None) -> str | None:
    """CONTEXT 3.4: a bullish day trades LONG only, a bearish day SHORT only. PURE.

    ``None`` in (an unseeded or suppressed day) gives ``None`` out -- there is no trade to take
    and the caller must not evaluate a signal at all.
    """
    if bias == BULLISH:
        return LONG
    if bias == BEARISH:
        return SHORT
    if bias is None:
        return None
    raise SignalError(f"unknown bias {bias!r}; expected {BULLISH!r}, {BEARISH!r} or None.")


# --- results ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Transition:
    """One evaluated candle: what the state was, what it became, and why.

    The audit trail chunk 12's plain-English replay pack is built from. Every candle in the
    trigger window produces exactly one of these, including the ones that change nothing.
    """

    stamp: datetime  # the candle's OPEN-stamp
    close_stamp: datetime
    close_paise: int
    side_of_poc: str
    state_before: str
    state_after: str
    note: str


@dataclass(frozen=True)
class Entry:
    """The trade the day's first qualifying cross opened (CONTEXT 3.4-2/3/4).

    All prices are integer paise. ``risk_paise`` is ``entry - stop`` on a long and
    ``stop - entry`` on a short, so it is the positive distance chunk 8 divides the rupee risk
    by; it is > 0 by construction (a zero or negative one is refused as unsizable before an
    :class:`Entry` is ever built).
    """

    stamp: datetime  # the entry candle's OPEN-stamp
    close_stamp: datetime
    entry_paise: int
    stop_paise: int
    target_paise: int
    risk_paise: int
    gap_entry: bool
    stop_source: str
    detail: str


@dataclass(frozen=True)
class ExitEvent:
    """WHICH candle ends the trade and WHY -- the simulator (chunk 8) prices it.

    ``both_touched`` records the R1-Q20 case: the candle touched the stop AND the target, and
    the stop wins. It is kept rather than folded away because the report has to disclose how
    often the backtest resolved an ambiguous candle in the pessimistic direction.
    """

    kind: str
    stamp: datetime  # the OPEN-stamp of the candle that ends the trade
    close_stamp: datetime
    both_touched: bool
    detail: str


@dataclass(frozen=True)
class SignalDay:
    """One stock-day's signal evaluation: the trade, or the recorded reason there is none.

    ``consumed`` is CONTEXT 3.4-2's "the first qualifying cross CONSUMES the stock-day even if
    the trade is unsizable" -- True for an entry AND for a cross that could not be sized, False
    for every no-cross day. Chunk 9 counts a day by its ``outcome``, never by guessing from a
    null.
    """

    day: date
    side: str
    poc_paise: Fraction
    reference_paise: int | None
    reference_source: str
    initial_state: str
    final_state: str
    outcome: str
    consumed: bool
    entry: Entry | None = None
    exit_event: ExitEvent | None = None
    transitions: tuple[Transition, ...] = ()
    log: str | None = None

    @property
    def traded(self) -> bool:
        return self.entry is not None


# --- the engine --------------------------------------------------------------------------------


def evaluate_day(
    bars: Sequence[_Bar],
    *,
    day: date,
    side: str,
    poc_paise: Fraction,
    minute_bars: Sequence[_MinuteBar] = (),
) -> SignalDay:
    """CONTEXT 3.4 over one stock-day. PURE.

    Args:
        bars: that day's 15-minute candles, from the chunk-5A aggregator over the minute store
            (CONTEXT 7-E1/E12). The WHOLE day is expected -- the windows are sliced here. Bars
            need not be sorted. An absent grid stamp is a no-trade quarter-hour, not an error
            (the completeness ruling of 2026-07-26).
        day: the trade date.
        side: :data:`LONG` or :data:`SHORT`, from the day's bias (:func:`side_for_bias`). The
            caller must not evaluate a day with no bias at all.
        poc_paise: the day's POC in paise as an exact ``Fraction`` (``poc.DayProfile.poc_paise``).
            It may legally be half a paisa; it is compared at full precision and never rounded.
        minute_bars: that day's 1-minute bars, used ONLY by E10's reference fallback and only
            when the 11:00-stamped candle is absent.

    Returns:
        A :class:`SignalDay`. It always carries a state, an outcome and the full transition
        trail; ``entry``/``exit_event`` are set only when a trade opened.

    Raises:
        SignalError: the inputs are not one stock-day of grid-aligned bars, the side is not a
            side, or the POC is a float (CONTEXT 7-E11 bans float comparisons on prices).
    """
    if side not in (LONG, SHORT):
        raise SignalError(f"side must be {LONG!r} or {SHORT!r}, got {side!r}.")
    poc = _require_exact_poc(poc_paise)
    ordered = _validated_bars(bars, day)

    by_stamp = {bar.stamp: bar for bar in ordered}
    reference, reference_source = _reference(by_stamp, minute_bars, day)
    if reference is None:
        return SignalDay(
            day=day,
            side=side,
            poc_paise=poc,
            reference_paise=None,
            reference_source=REFERENCE_NONE,
            initial_state=STATE_NO_REFERENCE,
            final_state=STATE_NO_REFERENCE,
            outcome=OUTCOME_NO_BARS if not ordered else OUTCOME_NO_REFERENCE,
            consumed=False,
            log=(
                f"{day}: no 11:00-11:15 candle and no 1-minute close at or before "
                f"{reference_cutoff_stamp(day).time()} -- no trade (CONTEXT 7-E10)"
            ),
        )

    state = _initial_state(reference, poc, side)
    return _walk(
        ordered=ordered,
        day=day,
        side=side,
        poc=poc,
        reference=reference,
        reference_source=reference_source,
        initial_state=state,
    )


# --- reference resolution (CONTEXT 3.4-1 + 7-E10) ---------------------------------------------


def _reference(
    by_stamp: dict[datetime, _Bar], minute_bars: Sequence[_MinuteBar], day: date
) -> tuple[int | None, str]:
    """The reference close and where it came from (CONTEXT 3.4-1; E10 fallback)."""
    candle = by_stamp.get(bar_open_stamp(day, REFERENCE_BAR))
    if candle is not None:
        return int(candle.close_paise), REFERENCE_FROM_CANDLE

    # E10: "Reference candle missing but window valid -> use the last available 1-min close
    # <= 11:14 as reference; none available -> no trade." The window's validity is the
    # caller's business (a day with no POC never reaches this engine at all).
    cutoff = reference_cutoff_stamp(day)
    eligible = [
        bar
        for bar in minute_bars
        if bar.stamp.date() == day and bar.stamp <= cutoff
    ]
    if not eligible:
        return None, REFERENCE_NONE
    last = max(eligible, key=lambda bar: bar.stamp)
    return int(last.close_paise), REFERENCE_FROM_MINUTES


def _initial_state(reference: int, poc: Fraction, side: str) -> str:
    """CONTEXT 3.4-1, and its explicit bearish mirror.

    Bullish: reference < POC -> ARMED; > POC -> WAIT-BELOW; == POC -> no side yet.
    Bearish: reference > POC -> ARMED; < POC -> WAIT-ABOVE; == POC -> no side yet (the mirror
    is 1:1, and the == POC rule names no side at all).
    """
    where = poc_side(reference, poc)
    if where == AT_POC:
        return STATE_SIDE_UNSET
    if side == LONG:
        return STATE_ARMED if where == BELOW_POC else STATE_WAIT_BELOW
    return STATE_ARMED if where == ABOVE_POC else STATE_WAIT_ABOVE


# --- the walk (CONTEXT 3.4-2) ------------------------------------------------------------------


def _walk(
    *,
    ordered: tuple[_Bar, ...],
    day: date,
    side: str,
    poc: Fraction,
    reference: int,
    reference_source: str,
    initial_state: str,
) -> SignalDay:
    first_open = bar_open_stamp(day, FIRST_TRIGGER_BAR)
    last_open = bar_open_stamp(day, LAST_TRIGGER_BAR)
    trigger_side = ABOVE_POC if side == LONG else BELOW_POC
    arming_side = BELOW_POC if side == LONG else ABOVE_POC
    waiting = STATE_WAIT_BELOW if side == LONG else STATE_WAIT_ABOVE

    state = initial_state
    transitions: list[Transition] = []
    triggered: _Bar | None = None

    for bar in ordered:
        if bar.stamp < first_open or bar.stamp > last_open:
            continue
        close = int(bar.close_paise)
        where = poc_side(close, poc)
        before = state

        if state == STATE_SIDE_UNSET:
            # Round-3 Q41 option A: the first distinct close SETS the side and ONLY sets it --
            # it is never itself the entry. A close ON the POC is not distinct and decides
            # nothing.
            if where == arming_side:
                state = STATE_ARMED
                note = (
                    f"first distinct close is {where} the POC: it SETS the side and arms the "
                    "day -- it is never itself the entry (Round-3 Q41-A)"
                )
            elif where == trigger_side:
                state = waiting
                note = (
                    f"first distinct close is {where} the POC: it SETS the side only and puts "
                    f"the day in {waiting} -- the Entry-2 path, never itself the entry "
                    "(Round-3 Q41-A)"
                )
            else:
                note = "close is exactly ON the POC: not a distinct close, no side set"
        elif state == waiting:
            # CONTEXT 3.4-1: "need a later 15-min close STRICTLY below POC first (== POC does
            # not arm)". A close on the trigger side while waiting counts for NOTHING and
            # consumes NOTHING (CONTEXT 3.4-2, R1-Q19b).
            if where == arming_side:
                state = STATE_ARMED
                note = f"close strictly {where} the POC arms the day"
            elif where == trigger_side:
                note = (
                    f"close {where} the POC while still {waiting}: NOT a cross, nothing "
                    "counted and nothing consumed (CONTEXT 3.4-2)"
                )
            else:
                note = "close is exactly ON the POC: does not arm (CONTEXT 3.4-1)"
        else:  # ARMED
            if where == trigger_side:
                triggered = bar
                note = f"close strictly {where} the POC while ARMED: TRIGGER"
            elif where == AT_POC:
                note = (
                    "close is exactly ON the POC while ARMED: not a trigger, the state stays "
                    "ARMED and nothing is consumed (CONTEXT 3.4-2, R2-Q34c)"
                )
            else:
                note = f"close {where} the POC while ARMED: not a trigger on this side"

        transitions.append(
            Transition(
                stamp=bar.stamp,
                close_stamp=bar.stamp + timedelta(minutes=CANDLE_MINUTES),
                close_paise=close,
                side_of_poc=where,
                state_before=before,
                state_after=state,
                note=note,
            )
        )
        if triggered is not None:
            # One trade per stock-day, no re-entry (R1-Q16): the walk stops at the first
            # qualifying cross and nothing after it is evaluated as a signal.
            break

    common = dict(
        day=day,
        side=side,
        poc_paise=poc,
        reference_paise=reference,
        reference_source=reference_source,
        initial_state=initial_state,
        final_state=state,
        transitions=tuple(transitions),
    )
    if triggered is None:
        return SignalDay(outcome=_no_cross_outcome(state, waiting), consumed=False, **common)
    return _open_trade(triggered=triggered, ordered=ordered, day=day, side=side, poc=poc, common=common)


def _no_cross_outcome(state: str, waiting: str) -> str:
    """CONTEXT 3.4-6's no-trade conditions, named apart so chunk 9 can count them apart."""
    if state == STATE_SIDE_UNSET:
        return OUTCOME_SIDE_NEVER_SET
    if state == waiting:
        return OUTCOME_NEVER_ARMED
    return OUTCOME_ARMED_NO_CROSS


# --- the trade (CONTEXT 3.4-3/4/5) -------------------------------------------------------------


def _open_trade(
    *,
    triggered: _Bar,
    ordered: tuple[_Bar, ...],
    day: date,
    side: str,
    poc: Fraction,
    common: dict,
) -> SignalDay:
    entry_price = int(triggered.close_paise)
    previous = _previous_bar(ordered, triggered.stamp)
    stop, gap, source, why = _stop(triggered, previous, side, poc)

    if stop is None:
        # A gap entry whose day holds no earlier 15-minute candle at all has no "last traded
        # price before the jump" to take. It is unreachable on a whole day (the reference rule
        # already requires a traded minute at or before 11:14, which buckets into an earlier
        # candle), and it is NOT decided silently: the cross happened, so the day is consumed
        # and the reason is recorded.
        return SignalDay(
            outcome=OUTCOME_UNSIZABLE,
            consumed=True,
            log=(
                f"{day}: gap entry at {triggered.stamp.time()} with no preceding 15-minute "
                "candle to take the previous close from -- consumed, no trade"
            ),
            **common,
        )

    risk = entry_price - stop if side == LONG else stop - entry_price
    if risk <= 0:
        # CONTEXT 3.4-3: "Degenerate entry == SL -> no trade (cannot size) -- log to run
        # report", and the day is still CONSUMED (3.4-2: "even if the trade is unsizable").
        # `risk < 0` is the same defect one step further (the sizing divisor would be
        # negative); it is only reachable on an E10-fallback gap day, and it is refused under
        # the same sentence rather than sized.
        return SignalDay(
            outcome=OUTCOME_UNSIZABLE,
            consumed=True,
            log=(
                f"{day}: cross at {triggered.stamp.time()} gives entry {entry_price} and stop "
                f"{stop} ({source}) -- risk {risk} paise cannot be sized; day CONSUMED, no "
                "trade (CONTEXT 3.4-2/3)"
            ),
            **common,
        )

    target = (
        entry_price + TARGET_RISK_MULTIPLE * risk
        if side == LONG
        else entry_price - TARGET_RISK_MULTIPLE * risk
    )
    entry = Entry(
        stamp=triggered.stamp,
        close_stamp=triggered.stamp + timedelta(minutes=CANDLE_MINUTES),
        entry_paise=entry_price,
        stop_paise=stop,
        target_paise=target,
        risk_paise=risk,
        gap_entry=gap,
        stop_source=source,
        detail=(
            f"{side} entry at the close {entry_price}; stop {stop} ({why}); risk {risk}; "
            f"target {entry_price} {'+' if side == LONG else '-'} "
            f"{TARGET_RISK_MULTIPLE} x {risk} = {target}"
        ),
    )
    return SignalDay(
        outcome=OUTCOME_ENTERED,
        consumed=True,
        entry=entry,
        exit_event=_exit_event(ordered, entry, side, day),
        **common,
    )


def _previous_bar(ordered: tuple[_Bar, ...], stamp: datetime) -> _Bar | None:
    """The 15-minute candle immediately before ``stamp`` -- the last one that actually traded.

    CONTEXT 3.4-3 calls the gap stop "the last traded price before the jump = the previous
    15-min candle's close", so when a grid stamp holds no candle (a quarter-hour in which
    nothing traded) the one before it IS the last traded price.
    """
    earlier = [bar for bar in ordered if bar.stamp < stamp]
    return earlier[-1] if earlier else None


def _stop(
    triggered: _Bar, previous: _Bar | None, side: str, poc: Fraction
) -> tuple[int | None, bool, str, str]:
    """CONTEXT 3.4-3: the stop, whether it is a gap entry, and the two strings that explain it.

    Long: gap when the entry candle's LOW is above the POC ("it opened beyond POC and never
    traded at/below it"). Short mirror, from CONTEXT 3.4's own mirror paragraph: gap when the
    entry candle's HIGH is below the POC.
    """
    if side == LONG:
        gap = int(triggered.low_paise) > poc
        if not gap:
            return int(triggered.low_paise), False, STOP_FROM_ENTRY_CANDLE, (
                f"entry candle low {int(triggered.low_paise)}, exactly, no buffer"
            )
    else:
        gap = int(triggered.high_paise) < poc
        if not gap:
            return int(triggered.high_paise), False, STOP_FROM_ENTRY_CANDLE_SHORT, (
                f"entry candle high {int(triggered.high_paise)}, exactly, no buffer"
            )
    if previous is None:
        return None, True, STOP_FROM_PREVIOUS_CLOSE, "no preceding 15-minute candle"
    return (
        int(previous.close_paise),
        True,
        STOP_FROM_PREVIOUS_CLOSE,
        (
            f"GAP entry -- the candle never traded "
            f"{'at or below' if side == LONG else 'at or above'} the POC, so the stop is the "
            f"last traded price before the jump: the {previous.stamp.time()} candle's close "
            f"{int(previous.close_paise)}"
        ),
    )


# --- exit events (CONTEXT 3.4-5 + 7-E7) ---------------------------------------------------------


def _exit_event(ordered: tuple[_Bar, ...], entry: Entry, side: str, day: date) -> ExitEvent:
    """Which candle ends the trade and why. CONTEXT 3.4-5; the simulator prices it.

    Monitoring starts the candle AFTER the entry candle (CONTEXT 7-E7: the entry price IS the
    entry candle's close, so that candle cannot trigger its own stop -- which, on a normal
    entry, is its own low) and runs to the candle closing at 15:15. Within a candle the stop
    wins over the target (R1-Q20).
    """
    square_off_open = bar_open_stamp(day, SQUARE_OFF_BAR)
    watched = [
        bar for bar in ordered if entry.stamp < bar.stamp <= square_off_open
    ]
    for bar in watched:
        hit_stop = (
            int(bar.low_paise) <= entry.stop_paise
            if side == LONG
            else int(bar.high_paise) >= entry.stop_paise
        )
        hit_target = (
            int(bar.high_paise) >= entry.target_paise
            if side == LONG
            else int(bar.low_paise) <= entry.target_paise
        )
        if hit_stop:
            return ExitEvent(
                kind=EXIT_STOP,
                stamp=bar.stamp,
                close_stamp=bar.stamp + timedelta(minutes=CANDLE_MINUTES),
                both_touched=hit_target,
                detail=(
                    f"stop {entry.stop_paise} touched by the {bar.stamp.time()} candle"
                    + (
                        f" -- which ALSO touched the target {entry.target_paise}; the stop "
                        "wins (R1-Q20)"
                        if hit_target
                        else ""
                    )
                ),
            )
        if hit_target:
            return ExitEvent(
                kind=EXIT_TARGET,
                stamp=bar.stamp,
                close_stamp=bar.stamp + timedelta(minutes=CANDLE_MINUTES),
                both_touched=False,
                detail=f"target {entry.target_paise} touched by the {bar.stamp.time()} candle",
            )

    if watched:
        marker = watched[-1]
        detail = (
            f"neither the stop {entry.stop_paise} nor the target {entry.target_paise} was "
            f"touched by 15:15: square off at the {marker.stamp.time()} candle's close "
            "(R1-Q18)"
        )
    else:
        # Nothing traded after the entry candle, so the day's last traded 15-minute close IS
        # the entry candle's own close. Marked on that candle so chunk 8 prices the square-off
        # at the last real trade rather than inventing one.
        marker = _bar_at(ordered, entry.stamp)
        detail = (
            "no 15-minute candle traded after the entry candle, so the last traded price of "
            "the day is the entry candle's own close: square off there (R1-Q18)"
        )
    return ExitEvent(
        kind=EXIT_SQUARE_OFF,
        stamp=marker.stamp,
        close_stamp=marker.stamp + timedelta(minutes=CANDLE_MINUTES),
        both_touched=False,
        detail=detail,
    )


def _bar_at(ordered: tuple[_Bar, ...], stamp: datetime) -> _Bar:
    for bar in ordered:
        if bar.stamp == stamp:
            return bar
    raise SignalError(f"no 15-minute candle at {stamp} -- the entry candle must exist.")


# --- validation --------------------------------------------------------------------------------


def _require_exact_poc(poc_paise: Fraction) -> Fraction:
    """CONTEXT 3.3/7-E11: the POC is exact and may be half a paisa. A float would make every
    comparison in this module a float comparison, which E11 bans outright."""
    if isinstance(poc_paise, float):
        raise SignalError(
            "poc_paise must be an exact Fraction of paise (CONTEXT 3.3: a row midpoint may sit "
            "off the tick grid and 'all comparisons against it use full precision'); a float "
            "would make every comparison here a float comparison, which CONTEXT 7-E11 bans."
        )
    if isinstance(poc_paise, bool) or not isinstance(poc_paise, (int, Fraction)):
        raise SignalError(f"poc_paise must be a Fraction or int of paise, got {poc_paise!r}.")
    return Fraction(poc_paise)


def _validated_bars(bars: Sequence[_Bar], day: date) -> tuple[_Bar, ...]:
    """One day of grid-aligned, duplicate-free 15-minute bars, oldest first."""
    ordered = sorted(bars, key=lambda bar: bar.stamp)
    seen: set[datetime] = set()
    grid = {bar_open_stamp(day, n) for n in range(1, BARS_PER_SESSION + 1)}
    for bar in ordered:
        stamp = bar.stamp
        if not isinstance(stamp, datetime) or stamp.tzinfo is not None:
            raise SignalError(f"15-minute stamp must be naive IST (CONTEXT 7-E8); got {stamp!r}.")
        if stamp.date() != day:
            raise SignalError(
                f"evaluate_day takes ONE trade date at a time: {day} was asked for but a bar "
                f"is stamped {stamp.isoformat()}."
            )
        if stamp not in grid:
            raise SignalError(
                f"15-minute stamp {stamp.isoformat()} is off the 09:15 session grid "
                "(CONTEXT 7-E12); the aggregator never produces one."
            )
        if stamp in seen:
            raise SignalError(
                f"duplicate 15-minute stamp {stamp.isoformat()}; the integrity gate "
                "(CONTEXT 4.5 gate 2) rejects a day with duplicates."
            )
        seen.add(stamp)
    return tuple(ordered)
