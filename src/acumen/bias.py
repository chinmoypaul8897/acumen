"""The daily bias engine: CONTEXT 3.2, as PURE functions (candles in, bias out).

This is the trader's daily bias rule, implemented EXACTLY as CONTEXT 3.2 spells it and in the
order it spells it. The strategy is frozen (CLAUDE.md rule 2); a deviation here is a defect
even if it looks smarter, so every operator is written character-for-character from the spec
and the evaluation order is the spec's order.

**Which candles.** To decide day D's bias, ``current`` = candle(D-1) and ``previous`` =
candle(D-2), both trading days (CONTEXT 3.2). The result is frozen before D's open.

**Definitions** (from the previous candle P): ``bodyMax = max(P.open, P.close)``,
``bodyMin = min(P.open, P.close)``.

**Evaluation order** (the FIRST rule that fires decides):

1. **Inside bar** -- ``C.high <= P.high AND C.low >= P.low`` -> carry last bias. Operators are
   INCLUSIVE: touching an extreme still counts as inside.
2. **Rule 1 -- breakout on close** (STRICT) -- ``C.close > bodyMax`` -> bullish,
   ``C.close < bodyMin`` -> bearish. Because rules run in order, an outside bar whose close
   lands BEYOND the body is decided HERE, not by Rule 3 (CONTEXT 3.2's precedence note).
3. **Rule 2 -- simple sweep** (EXACT mixed operators) -- bullish if
   ``C.low < P.low AND C.high <= P.high AND C.close >= bodyMin``; bearish if
   ``C.high > P.high AND C.low >= P.low AND C.close <= bodyMax``.
4. **Rule 3 -- double sweep (outside bar)** -- when ``C.high > P.high AND C.low < P.low`` and
   the close is INSIDE the body. Day C's 1-minute data decides which extreme broke FIRST:
   P.high first -> bullish, P.low first -> bearish. **Tie** (both break in the SAME 1-min
   candle m): ``m.close < m.open`` (red) -> low swept later -> BULLISH; ``m.close > m.open``
   (green) -> high swept later -> BEARISH (assumed mirror, OPEN-4); ``m.close == m.open``
   (doji) -> carry and log (OPEN-4).
5. **No rule fires** -> carry. If a bullish and a bearish condition ever both hold (should be
   impossible), bullish takes precedence and the event is logged.

**Missing 1-minute data on a Rule-3 day** (old dates) -> carry last bias (documented
fallback, R1-Q6).

PURE: no I/O, no network, no clock reads. The 1-minute data for Rule 3 arrives through an
INJECTED ``minute_loader`` -- the orchestration layer (:mod:`acumen.bias_engine`) binds the
real one; tests inject fixtures. Prices are integer paise (CONTEXT 7-E11); the previous
candle is already brought into the current candle's scale by the caller (pairwise adjustment,
CONTEXT 3.2 / 7-E11), so this module only ever compares numbers -- no float equality anywhere.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, Sequence

#: The two bias values. ``None`` is a third state: "not seeded yet" (CONTEXT 3.2 seeding --
#: before any rule has fired there is no bias and no trading).
BULLISH: str = "bullish"
BEARISH: str = "bearish"

# --- rule tags (carried on the result for the evidence pack and logs) ----------------------
RULE_INSIDE: str = "inside-bar-carry"
RULE_1: str = "rule-1-breakout"
RULE_2: str = "rule-2-sweep"
RULE_3: str = "rule-3-outside-bar"
RULE_3_TIE_RED: str = "rule-3-tie-red-bullish"
RULE_3_TIE_GREEN: str = "rule-3-tie-green-bearish"  # OPEN-4 mirror
RULE_3_TIE_DOJI: str = "rule-3-tie-doji-carry"  # OPEN-4
RULE_3_NO_MINUTE: str = "rule-3-no-1min-carry"  # documented fallback (R1-Q6)
RULE_3_NO_BREAK: str = "rule-3-no-break-carry"
RULE_CARRY: str = "no-rule-carry"
RULE_PRECEDENCE_GUARD: str = "bullish-precedence-guard"

# first-break sides
_HIGH_FIRST: str = "high-first"
_LOW_FIRST: str = "low-first"
_TIE: str = "tie"


class BiasError(ValueError):
    """A candle handed to the bias engine is not a usable candle."""


@dataclass(frozen=True)
class Candle:
    """One OHLC candle in integer paise (CONTEXT 7-E11). Daily or 1-minute.

    ``stamp`` is optional and only meaningful for 1-minute candles (the Rule-3 scan reads them
    in the order given, so the stamp is documentation, not the sort key). A daily candle
    carries its trade ``day`` so the orchestration can adjust and label it; the pure engine
    never reads it.
    """

    open: int
    high: int
    low: int
    close: int
    day: date | None = None
    stamp: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("open", "high", "low", "close"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise BiasError(
                    f"Candle.{name} must be integer paise (CONTEXT 7-E11), got "
                    f"{type(value).__name__} {value!r}."
                )
        if self.high < self.low:
            raise BiasError(f"Candle high {self.high} < low {self.low}.")
        if not (self.low <= self.open <= self.high and self.low <= self.close <= self.high):
            raise BiasError(
                f"Candle open/close must lie within [low, high]: "
                f"O{self.open} H{self.high} L{self.low} C{self.close}."
            )

    @property
    def body_max(self) -> int:
        return max(self.open, self.close)

    @property
    def body_min(self) -> int:
        return min(self.open, self.close)


#: The Rule-3 minute provider handed to :func:`evaluate_pair`: it returns day C's 1-minute
#: candles in time order, or ``None`` when there is no 1-minute data for that day (old dates).
#: It is a zero-argument callable so :func:`evaluate_pair` stays pure and calls it ONLY on a
#: Rule-3 day. The orchestration binds the real (symbol, date) loader into it.
MinuteProvider = Callable[[], Sequence[Candle] | None]


@dataclass(frozen=True)
class BiasResult:
    """The bias decision for one pair, plus why -- for the evidence pack and the logs."""

    bias: str | None
    rule: str
    detail: str
    carried: bool = False
    open4: bool = False  # touched an OPEN-4 branch (green tie mirror / doji)
    log: str | None = None


def evaluate_pair(
    previous: Candle,
    current: Candle,
    minute_loader: MinuteProvider | None = None,
    last_bias: str | None = None,
) -> BiasResult:
    """Decide the bias for the day whose pair is (``previous``, ``current``). PURE.

    Args:
        previous: candle(D-2), ALREADY brought into ``current``'s price scale by the caller
            (pairwise CA adjustment, CONTEXT 3.2 / 7-E11).
        current: candle(D-1), raw same-day prices.
        minute_loader: a zero-arg provider of ``current``'s day 1-minute candles, used ONLY if
            Rule 3 fires. ``None`` (or a provider returning ``None``) on a Rule-3 day triggers
            the documented missing-1-minute fallback (carry last bias).
        last_bias: the bias carried from the previous trading day (``None`` if not seeded yet).

    Returns:
        A :class:`BiasResult`. ``bias`` is :data:`BULLISH`, :data:`BEARISH`, or ``None`` (still
        unseeded when a carry carries ``None``).
    """
    P, C = previous, current
    if not isinstance(P, Candle) or not isinstance(C, Candle):
        raise BiasError("evaluate_pair takes two Candle objects (previous, current).")
    bmax, bmin = P.body_max, P.body_min

    # 1. INSIDE BAR (inclusive operators). Carry, even if the close is beyond the body: the
    #    spec checks this FIRST, so an inside bar is never re-decided by a later rule.
    if C.high <= P.high and C.low >= P.low:
        return _carry(
            last_bias,
            RULE_INSIDE,
            f"inside bar: C.high {C.high} <= P.high {P.high} and C.low {C.low} >= P.low {P.low}",
        )

    # 2. RULE 1 -- breakout on close, STRICT. Decides an outside bar closing beyond the body
    #    too (CONTEXT 3.2 precedence note), because the rules co-evaluate in order.
    r1_bull = C.close > bmax
    r1_bear = C.close < bmin
    if r1_bull and r1_bear:  # impossible: bmin <= bmax
        return _precedence_guard(RULE_1, C, bmin, bmax)
    if r1_bull:
        return BiasResult(BULLISH, RULE_1, f"Rule 1: C.close {C.close} > bodyMax {bmax}")
    if r1_bear:
        return BiasResult(BEARISH, RULE_1, f"Rule 1: C.close {C.close} < bodyMin {bmin}")

    # 3. RULE 2 -- simple sweep, EXACT mixed operators.
    r2_bull = C.low < P.low and C.high <= P.high and C.close >= bmin
    r2_bear = C.high > P.high and C.low >= P.low and C.close <= bmax
    if r2_bull and r2_bear:  # impossible with these operators
        return _precedence_guard(RULE_2, C, bmin, bmax)
    if r2_bull:
        return BiasResult(
            BULLISH,
            RULE_2,
            f"Rule 2 bullish: C.low {C.low} < P.low {P.low}, C.high {C.high} <= P.high "
            f"{P.high}, C.close {C.close} >= bodyMin {bmin}",
        )
    if r2_bear:
        return BiasResult(
            BEARISH,
            RULE_2,
            f"Rule 2 bearish: C.high {C.high} > P.high {P.high}, C.low {C.low} >= P.low "
            f"{P.low}, C.close {C.close} <= bodyMax {bmax}",
        )

    # 4. RULE 3 -- double sweep (outside bar), close INSIDE the body (Rule 1 already took the
    #    close-beyond-body cases). Which extreme broke FIRST is a 1-minute question.
    if C.high > P.high and C.low < P.low:
        return _rule_3(P, C, bmin, bmax, minute_loader, last_bias)

    # 5. no rule fired -> carry
    return _carry(last_bias, RULE_CARRY, "no rule fired: neither a breakout, sweep nor outside bar")


def _rule_3(
    P: Candle,
    C: Candle,
    bmin: int,
    bmax: int,
    minute_loader: MinuteProvider | None,
    last_bias: str | None,
) -> BiasResult:
    minutes = minute_loader() if minute_loader is not None else None
    if not minutes:
        # Missing 1-minute data on a Rule-3 day (old dates): carry (R1-Q6, documented).
        return _carry(
            last_bias,
            RULE_3_NO_MINUTE,
            "Rule 3 (outside bar) but no 1-minute data for day C; carry last bias "
            "(documented fallback, R1-Q6)",
            log=f"R3 day with no 1-min data -> carried {last_bias!r}",
        )

    found = _first_break(minutes, P.high, P.low)
    if found is None:
        # An outside bar at the daily level whose minutes broke NEITHER extreme is a data
        # contradiction (the day's high/low come from those minutes). Carry and log rather
        # than invent a direction.
        return _carry(
            last_bias,
            RULE_3_NO_BREAK,
            "Rule 3: no 1-minute candle broke either extreme (daily/1-min mismatch); carry",
            log="R3 day but no 1-min break found -> carried",
        )

    side, minute = found
    if side == _HIGH_FIRST:
        # P.high first AND C.close >= bodyMin -> bullish. The close condition is guaranteed
        # here (Rule 1 already removed close < bodyMin), asserted for spec-faithfulness.
        if C.close >= bmin:
            return BiasResult(
                BULLISH, RULE_3,
                f"Rule 3: P.high {P.high} broken first (1-min high {minute.high}); "
                f"C.close {C.close} >= bodyMin {bmin} -> bullish",
            )
        return _carry(last_bias, RULE_3, "Rule 3: P.high first but C.close < bodyMin; carry")
    if side == _LOW_FIRST:
        if C.close <= bmax:
            return BiasResult(
                BEARISH, RULE_3,
                f"Rule 3: P.low {P.low} broken first (1-min low {minute.low}); "
                f"C.close {C.close} <= bodyMax {bmax} -> bearish",
            )
        return _carry(last_bias, RULE_3, "Rule 3: P.low first but C.close > bodyMax; carry")

    return _rule_3_tie(minute, C, bmin, bmax, last_bias)


def _rule_3_tie(minute: Candle, C: Candle, bmin: int, bmax: int, last_bias: str | None) -> BiasResult:
    """Both extremes broke in the SAME 1-minute candle (CONTEXT 3.2 tie predicate).

    The codeable operator is close-vs-open on that 1-minute candle (the trader's worked
    example, R2-Q31, is the authority):

    * red (``close < open``): the low was swept LATER, so the high effectively broke first ->
      bullish (his answer);
    * green (``close > open``): mirror -> bearish (OPEN-4, assumed by symmetry);
    * doji (``close == open``): no decision -> carry and log (OPEN-4).
    """
    if minute.close < minute.open:  # red
        if C.close >= bmin:
            return BiasResult(
                BULLISH, RULE_3_TIE_RED,
                f"Rule 3 tie: same-minute double break, 1-min RED (close {minute.close} < open "
                f"{minute.open}) -> low swept later -> bullish; C.close {C.close} >= bodyMin {bmin}",
            )
        return _carry(last_bias, RULE_3_TIE_RED, "Rule 3 tie red but C.close < bodyMin; carry")
    if minute.close > minute.open:  # green -- OPEN-4 mirror
        if C.close <= bmax:
            return BiasResult(
                BEARISH, RULE_3_TIE_GREEN,
                f"Rule 3 tie: same-minute double break, 1-min GREEN (close {minute.close} > open "
                f"{minute.open}) -> high swept later -> bearish [OPEN-4]; C.close {C.close} <= "
                f"bodyMax {bmax}",
                open4=True,
            )
        return _carry(last_bias, RULE_3_TIE_GREEN, "Rule 3 tie green but C.close > bodyMax; carry", open4=True)
    # doji -- OPEN-4: no decision, carry and log
    return _carry(
        last_bias,
        RULE_3_TIE_DOJI,
        f"Rule 3 tie: same-minute double break, 1-min DOJI (close == open == {minute.open}) -> "
        "no decision -> carry last bias [OPEN-4]",
        open4=True,
        log=f"R3 tie doji -> carried {last_bias!r}",
    )


def _first_break(
    minutes: Sequence[Candle], previous_high: int, previous_low: int
) -> tuple[str, Candle] | None:
    """The first 1-minute candle (in time order) to break an extreme, and which side.

    "Broken" is CONTEXT 3.2's definition: 1-min high > P.high (resp. 1-min low < P.low). The
    first minute to break EITHER decides; a minute that breaks BOTH is the tie case.
    """
    for minute in minutes:
        broke_high = minute.high > previous_high
        broke_low = minute.low < previous_low
        if broke_high and broke_low:
            return _TIE, minute
        if broke_high:
            return _HIGH_FIRST, minute
        if broke_low:
            return _LOW_FIRST, minute
    return None


def _carry(
    last_bias: str | None, rule: str, detail: str, *, open4: bool = False, log: str | None = None
) -> BiasResult:
    return BiasResult(bias=last_bias, rule=rule, detail=detail, carried=True, open4=open4, log=log)


def _precedence_guard(rule: str, C: Candle, bmin: int, bmax: int) -> BiasResult:
    """CONTEXT 3.2: if a bullish and a bearish condition ever both hold (impossible), bullish
    takes precedence -- and we LOG it, because it firing means an operator is wrong."""
    return BiasResult(
        BULLISH,
        RULE_PRECEDENCE_GUARD,
        f"{rule}: a bullish AND a bearish condition both evaluated true on C "
        f"(O{C.open} H{C.high} L{C.low} C{C.close}, bodyMin {bmin} bodyMax {bmax}). This should "
        "be impossible; bullish takes precedence (CONTEXT 3.2). LOGGED for investigation.",
        log="bullish-precedence guard fired -- investigate: a bull and bear condition co-held",
    )
