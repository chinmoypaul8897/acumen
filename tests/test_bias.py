"""The pure bias engine (CONTEXT 3.2): evaluate_pair and its boundary operators.

Everything here is offline and synthetic -- the BOUNDARY-EQUAL cases the F9 real-day goldens
deliberately avoid (close == bodyMax, an inside-bar touch on the extreme, a sweep whose close
sits exactly on the body edge) live here, as CONTEXT 3.2 says they behave. F5 (the trader's
Q31 worked tie example, CONTEXT 8) is here too, with its synthetic 1-minute data.

The strategy is frozen (CLAUDE.md rule 2): these tests are written straight from CONTEXT 3.2's
operators, so a "smarter" change to the engine breaks them on purpose.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from acumen.bias import (
    BEARISH,
    BULLISH,
    RULE_1,
    RULE_2,
    RULE_3,
    RULE_3_NO_MINUTE,
    RULE_3_TIE_DOJI,
    RULE_3_TIE_GREEN,
    RULE_3_TIE_RED,
    RULE_INSIDE,
    RULE_CARRY,
    BiasError,
    Candle,
    evaluate_pair,
)
from acumen.bias_engine import csv_minute_loader

MINUTE_DIR = Path(__file__).resolve().parent / "fixtures" / "minute"


def R(rupees: float) -> int:
    """Rupees -> integer paise (test helper)."""
    return int(round(rupees * 100))


def candle(o: float, h: float, l: float, c: float) -> Candle:
    return Candle(R(o), R(h), R(l), R(c))


# The standard previous candle used across the boundary tests: bodyMin 2010, bodyMax 2040,
# P.high 2050, P.low 2000.
P = candle(2010, 2050, 2000, 2040)


# --- inside bar (inclusive operators) ------------------------------------------------------


def test_inside_bar_carries_the_last_bias() -> None:
    result = evaluate_pair(P, candle(2020, 2045, 2010, 2030), last_bias=BEARISH)
    assert result.bias == BEARISH and result.rule == RULE_INSIDE and result.carried


def test_inside_bar_touching_both_extremes_is_still_inside() -> None:
    """CONTEXT 3.2: touching an extreme counts as inside (operators are <= and >=)."""
    touch = candle(2025, 2050, 2000, 2030)  # C.high == P.high, C.low == P.low
    result = evaluate_pair(P, touch, last_bias=BULLISH)
    assert result.bias == BULLISH and result.rule == RULE_INSIDE


def test_an_inside_bar_carries_even_when_its_close_is_beyond_the_body() -> None:
    """Inside is checked FIRST, so it wins over a would-be Rule 1: C.close 2045 > bodyMax 2040
    but the bar is inside P's range, so the bias is carried, not flipped."""
    inside_high_close = candle(2043, 2048, 2010, 2045)  # within [2000, 2050], close > bodyMax
    result = evaluate_pair(P, inside_high_close, last_bias=BEARISH)
    assert result.bias == BEARISH and result.rule == RULE_INSIDE


def test_unseeded_inside_bar_carries_none() -> None:
    result = evaluate_pair(P, candle(2020, 2045, 2010, 2030), last_bias=None)
    assert result.bias is None and result.carried


# --- Rule 1: breakout on close, STRICT -----------------------------------------------------


def test_rule_1_bullish_close_strictly_above_body_max() -> None:
    result = evaluate_pair(P, candle(2045, 2060, 2040, 2055), last_bias=None)
    assert result.bias == BULLISH and result.rule == RULE_1


def test_rule_1_bearish_close_strictly_below_body_min() -> None:
    result = evaluate_pair(P, candle(2015, 2020, 1995, 2005), last_bias=None)
    assert result.bias == BEARISH and result.rule == RULE_1


def test_rule_1_is_strict_close_equal_to_body_max_does_not_fire() -> None:
    """C.close == bodyMax exactly is NOT a Rule-1 breakout (strict >). Here it is a high-sweep,
    so Rule 2 (bearish) takes it instead -- exercising the boundary the F9 reals avoid."""
    on_edge = candle(2035, 2055, 2005, 2040)  # high>P.high, low>=P.low, close==bodyMax
    result = evaluate_pair(P, on_edge, last_bias=None)
    assert result.rule == RULE_2 and result.bias == BEARISH


def test_an_outside_bar_closing_beyond_the_body_is_decided_by_rule_1() -> None:
    """CONTEXT 3.2 precedence note: an outside bar whose close lands beyond the body is decided
    by Rule 1, NOT by the Rule-3 first-break test. No minute data is even consulted."""
    outside_high_close = candle(2030, 2060, 1990, 2055)  # outside bar, close 2055 > bodyMax
    called = []
    result = evaluate_pair(
        P, outside_high_close, minute_loader=lambda: called.append(1) or [], last_bias=None
    )
    assert result.bias == BULLISH and result.rule == RULE_1
    assert called == [], "Rule 1 decided; the 1-minute loader must not be consulted"

    outside_low_close = candle(2015, 2060, 1990, 2005)  # outside bar, close 2005 < bodyMin
    result = evaluate_pair(P, outside_low_close, minute_loader=lambda: [], last_bias=None)
    assert result.bias == BEARISH and result.rule == RULE_1


# --- Rule 2: simple sweep, EXACT mixed operators -------------------------------------------


def test_rule_2_bullish_low_sweep() -> None:
    result = evaluate_pair(P, candle(2020, 2049, 1995, 2030), last_bias=None)
    assert result.bias == BULLISH and result.rule == RULE_2


def test_rule_2_bullish_boundary_high_equal_and_close_equal_body_min() -> None:
    """C.high == P.high (allowed, <=) and C.close == bodyMin (allowed, >=) still fires bullish."""
    result = evaluate_pair(P, candle(2015, 2050, 1995, 2010), last_bias=None)
    assert result.bias == BULLISH and result.rule == RULE_2


def test_rule_2_bearish_high_sweep() -> None:
    result = evaluate_pair(P, candle(2030, 2055, 2001, 2020), last_bias=None)
    assert result.bias == BEARISH and result.rule == RULE_2


def test_rule_2_bearish_boundary_low_equal_and_close_equal_body_max() -> None:
    result = evaluate_pair(P, candle(2035, 2055, 2000, 2040), last_bias=None)
    assert result.bias == BEARISH and result.rule == RULE_2


# --- Rule 3: double sweep (outside bar), close INSIDE the body ------------------------------


def _outside_close_inside() -> Candle:
    return candle(2005, 2060, 1990, 2020)  # outside bar, close 2020 inside [2010, 2040]


def test_rule_3_high_broken_first_is_bullish() -> None:
    minutes = [candle(2015, 2055, 2005, 2050), candle(2050, 2052, 1990, 1995)]
    result = evaluate_pair(P, _outside_close_inside(), lambda: minutes, last_bias=None)
    assert result.bias == BULLISH and result.rule == RULE_3


def test_rule_3_low_broken_first_is_bearish() -> None:
    minutes = [candle(2008, 2012, 1990, 1995), candle(1995, 2060, 1994, 2055)]
    result = evaluate_pair(P, _outside_close_inside(), lambda: minutes, last_bias=None)
    assert result.bias == BEARISH and result.rule == RULE_3


def test_rule_3_missing_one_minute_data_carries_last_bias() -> None:
    """Old dates with no 1-minute data: carry (R1-Q6, documented fallback)."""
    result = evaluate_pair(P, _outside_close_inside(), lambda: None, last_bias=BULLISH)
    assert result.bias == BULLISH and result.rule == RULE_3_NO_MINUTE and result.carried
    # no loader at all behaves the same way
    result2 = evaluate_pair(P, _outside_close_inside(), None, last_bias=BEARISH)
    assert result2.bias == BEARISH and result2.rule == RULE_3_NO_MINUTE


# --- the tie predicate (CONTEXT 3.2 + OPEN-4) ----------------------------------------------


def test_f5_rule_3_tie_red_is_bullish() -> None:
    """F5 (CONTEXT 8, the trader's Q31 worked example): P O2010 H2050 L2000 C2040; a
    same-minute double break whose 1-minute candle closes RED; C.close 2020 -> BULLISH.

    The 1-minute data is the frozen synthetic fixture SYNTH_2099-01-06 (clearly not real:
    far-future date, SYNTH symbol). The trader answered this exact case Bullish."""
    loader = csv_minute_loader(MINUTE_DIR)
    C = candle(2005, 2060, 1990, 2020)  # outside bar, C.close 2020 (CONTEXT 8 F5)
    result = evaluate_pair(P, C, lambda: loader("SYNTH", date(2099, 1, 6)), last_bias=BEARISH)
    assert result.bias == BULLISH and result.rule == RULE_3_TIE_RED


def test_rule_3_tie_green_is_bearish_open4_mirror() -> None:
    """OPEN-4: the green mirror -- assumed by symmetry, flagged for the trader to confirm."""
    minutes = [candle(2005, 2055, 1995, 2050)]  # same-minute double break, green (close>open)
    result = evaluate_pair(P, _outside_close_inside(), lambda: minutes, last_bias=BULLISH)
    assert result.bias == BEARISH and result.rule == RULE_3_TIE_GREEN and result.open4


def test_rule_3_tie_doji_carries_and_is_open4() -> None:
    """OPEN-4: a doji tie (1-minute close == open) is no decision -> carry + log."""
    minutes = [candle(2010, 2055, 1995, 2010)]  # same-minute double break, doji (close==open)
    result = evaluate_pair(P, _outside_close_inside(), lambda: minutes, last_bias=BULLISH)
    assert result.bias == BULLISH and result.rule == RULE_3_TIE_DOJI
    assert result.carried and result.open4 and result.log is not None


# --- carry, seeding, validation ------------------------------------------------------------


def test_the_non_rule3_rules_are_exhaustive_rule_carry_never_fires() -> None:
    """A property CONTEXT 3.2's operators guarantee: every candle that is not an outside bar
    is decided by inside / Rule 1 / Rule 2. RULE_CARRY (the "no rule fires" catch-all) is a
    safety net that cannot actually be reached for a single-sweep bar -- because after Rule 1
    the close is inside the body, so a high-sweep always fires Rule 2 bearish and a low-sweep
    always fires Rule 2 bullish. We prove it over a spread of random valid non-outside bars."""
    import random

    rng = random.Random(20260725)
    for _ in range(5000):
        # a random valid daily candle in a band overlapping P, then reject outside bars
        lo = rng.randint(199000, 203000)
        hi = lo + rng.randint(1, 6000)
        o = rng.randint(lo, hi)
        c = rng.randint(lo, hi)
        C = Candle(o, hi, lo, c)
        if C.high > P.high and C.low < P.low:
            continue  # outside bar -> Rule 3, needs minute data; excluded from this property
        result = evaluate_pair(P, C, last_bias=BULLISH)
        assert result.rule in (RULE_INSIDE, RULE_1, RULE_2), (
            f"RULE_CARRY should be unreachable, got {result.rule} on "
            f"O{o} H{hi} L{lo} C{c}"
        )
    assert RULE_CARRY == "no-rule-carry"  # the catch-all is defined (spec item 5), just unreached


def test_candle_rejects_non_integer_and_impossible_ohlc() -> None:
    with pytest.raises(BiasError, match="integer paise"):
        Candle(2000.0, 2050, 2000, 2040)  # type: ignore[arg-type]
    with pytest.raises(BiasError, match="high .* < low"):
        Candle(2000, 1990, 2000, 1995)
    with pytest.raises(BiasError, match="within"):
        Candle(2000, 2050, 2010, 2060)  # close 2060 > high 2050
