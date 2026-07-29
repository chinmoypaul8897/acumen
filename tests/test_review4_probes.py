"""REVIEW_4 reviewer probes (chunk 4, bias engine) -- kept per persona process step 4.

These close the coverage gaps the REVIEW_4 mutation matrix found in the pure engine and pin the
one orchestration boundary the build left unpinned. NONE is a code defect: HEAD is correct on
every one of them (verified by the review). Each test is written straight from CONTEXT 3.2 so a
"smarter" edit to the operators breaks it on purpose.

1-6. Six Rule-3 / tie / first-break BOUNDARY cases the build's comfortable-margin tests never
     exercise. Each was proven to PASS on HEAD and FAIL on its boundary-flip mutant (M13-M18 in
     the REVIEW_4 matrix): the R3/tie close guards at C.close == bodyMin / == bodyMax, and the
     strict-break definition (a 1-minute high == P.high, or low == P.low, is a TOUCH, not a
     break -- CONTEXT 3.2: "1-min candle's high > P.high (resp. low < P.low)").
7.   The precedence guard and RULE_CARRY are unreachable -- pinned over a dense deterministic
     grid (the build's property test covers RULE_CARRY randomly; the guard had no test at all).
8.   Demerger AND Q-6 tier-2 rights suppression RESUME at E+3 (the build pins blocking at E+1
     but not the resume boundary).

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from acumen import corp_actions as ca
from acumen.bhavcopy import (
    FORMAT_ARCHIVE,
    OUTCOME_NOT_FOUND,
    OUTCOME_PRESENT,
    DailyRow,
    DateOutcome,
)
from acumen.bias import (
    BEARISH,
    BULLISH,
    RULE_3,
    RULE_3_TIE,
    RULE_CARRY,
    RULE_INSIDE,
    RULE_1,
    RULE_2,
    RULE_PRECEDENCE_GUARD,
    Candle,
    evaluate_pair,
)
from acumen.bias_engine import BiasEngine
from acumen.calendar import TradingCalendar
from acumen.daily_store import DailyStore


def R(rupees: float) -> int:
    return int(round(rupees * 100))


def candle(o: float, h: float, l: float, c: float) -> Candle:
    return Candle(R(o), R(h), R(l), R(c))


# The standard previous candle: bodyMin 2010, bodyMax 2040, P.high 2050, P.low 2000.
P = candle(2010, 2050, 2000, 2040)


# --- 1-2. Rule-3 close guards exactly on the body edge (M13/M14) ----------------------------


def test_r3_high_first_close_exactly_on_body_min_is_bullish() -> None:
    """CONTEXT 3.2: P.high broken first AND C.close >= bodyMin -> BULLISH. At C.close == bodyMin
    the inclusive '>=' must still fire bullish (kills mutant M13: '>=' -> '>')."""
    C = candle(2005, 2060, 1990, 2010)  # outside bar, C.close == bodyMin (2010)
    minutes = [candle(2015, 2055, 2005, 2050), candle(2050, 2052, 1990, 1995)]  # high first
    result = evaluate_pair(P, C, lambda: minutes, last_bias=BEARISH)
    assert result.bias == BULLISH and result.rule == RULE_3


def test_r3_low_first_close_exactly_on_body_max_is_bearish() -> None:
    """Mirror of M13: P.low broken first AND C.close <= bodyMax -> BEARISH at C.close == bodyMax
    (kills mutant M14: '<=' -> '<')."""
    C = candle(2035, 2060, 1990, 2040)  # outside bar, C.close == bodyMax (2040)
    minutes = [candle(2008, 2012, 1990, 1995), candle(1995, 2060, 1994, 2055)]  # low first
    result = evaluate_pair(P, C, lambda: minutes, last_bias=BULLISH)
    assert result.bias == BEARISH and result.rule == RULE_3


# --- 3-4. tie close guards exactly on the body edge (M15/M16) --------------------------------
#
# CONTRACT MOVED BY ARCHITECT RULING, 2026-07-29 (CONTEXT 3.2 (v1.3); trader Round-3 Q38/Q39;
# QUESTIONS.md ROUND-3 FINAL RECEIPTS R3F-b). When this file was written, OPEN-4 was open and the
# tie predicate keyed off the decisive minute's COLOUR: red -> bullish, green -> bearish (an
# assumed mirror), doji -> carry. The trader has now REJECTED that mirror: the colour is
# irrelevant and the tie resolves on the DAILY close against the body, with bullish precedence.
# Both probes below are re-pinned to the ruling and NEITHER is weakened -- each still asserts a
# boundary-equal close (== bodyMin, == bodyMax) with a same-minute double break, which is what
# M15/M16 mutate; the SECOND one's expected bias flips from BEARISH to BULLISH because the rule
# it was written against no longer exists.


def test_r3_tie_close_exactly_on_body_min_is_bullish_red_minute() -> None:
    """Same-minute double break, C.close == bodyMin -> BULLISH (kills M15: '>=' -> '>').

    The decisive minute here is RED, which the trader's original Q31 answer already called
    bullish -- so this case's ANSWER is unchanged by Round-3 Q38/Q39; only its rule tag moved
    (RULE_3_TIE_RED -> RULE_3_TIE, since there is nothing left for a colour to key)."""
    C = candle(2005, 2060, 1990, 2010)
    minutes = [candle(2020, 2055, 1990, 1995)]  # both extremes in one minute, red (close<open)
    result = evaluate_pair(P, C, lambda: minutes, last_bias=BEARISH)
    assert result.bias == BULLISH and result.rule == RULE_3_TIE and result.tie_case


def test_r3_tie_close_exactly_on_body_max_is_bullish_even_on_a_green_minute() -> None:
    """Same-minute double break, GREEN 1-min, C.close == bodyMax 2040 -> **BULLISH**.

    HAND-COMPUTED against CONTEXT 3.2 (v1.3): bodyMin 2010, bodyMax 2040, C.close 2040. The tie
    rule is "C.close >= bodyMin -> BULLISH", and 2040 >= 2010, so bullish precedence takes it --
    the green mirror that made this BEARISH was overturned by the trader (Round-3 Q38).

    This still kills M15 at the OTHER end of the body (a '>=' -> '>' mutant leaves 2040 bullish,
    so M15's kill lives in the test above); M16 ('<=' -> '<' on the bodyMax guard) now sits in
    the branch CONTEXT itself calls unreachable, and is killed by
    ``test_bias.py::test_the_tie_bearish_branch_is_written_as_the_spec_writes_it``, which calls
    the predicate directly."""
    C = candle(2035, 2060, 1990, 2040)
    minutes = [candle(2005, 2055, 1990, 2050)]  # both extremes in one minute, green (close>open)
    result = evaluate_pair(P, C, lambda: minutes, last_bias=BULLISH)
    assert result.bias == BULLISH and result.rule == RULE_3_TIE and result.tie_case


# --- 5-6. the first break is STRICT: a touch of P's extreme is not a break (M17/M18) --------


def test_first_break_high_is_strict_a_touch_of_p_high_is_not_a_break() -> None:
    """CONTEXT 3.2: broken == 1-min high > P.high (strict). A first minute whose high EXACTLY
    equals P.high only TOUCHES it; here that same minute breaks the low, so the low broke first
    -> BEARISH. The mutant '>' -> '>=' would call the first minute a same-minute tie and, being
    red, flip it BULLISH (kills M17)."""
    C = candle(2005, 2060, 1990, 2020)  # outside bar, close inside body
    minutes = [candle(2020, 2050, 1990, 1995), candle(1995, 2060, 1994, 2055)]  # min1 high==2050
    result = evaluate_pair(P, C, lambda: minutes, last_bias=BULLISH)
    assert result.bias == BEARISH and result.rule == RULE_3


def test_first_break_low_is_strict_a_touch_of_p_low_is_not_a_break() -> None:
    """Mirror of M17: a first minute whose low EXACTLY equals P.low only touches it; here it
    breaks the high, so the high broke first -> BULLISH. The mutant '<' -> '<=' would call it a
    tie and, being green, flip it BEARISH (kills M18)."""
    C = candle(2005, 2060, 1990, 2020)
    minutes = [candle(2020, 2060, 2000, 2055), candle(2055, 2056, 1990, 1995)]  # min1 low==2000
    result = evaluate_pair(P, C, lambda: minutes, last_bias=BEARISH)
    assert result.bias == BULLISH and result.rule == RULE_3


# --- 7. the precedence guard and RULE_CARRY are unreachable (dense deterministic grid) -------


def test_precedence_guard_and_rule_carry_are_unreachable_over_a_dense_grid() -> None:
    """CONTEXT 3.2's bullish-precedence guard fires only if a bullish AND bearish condition
    ever co-hold (R1 needs close>bodyMax AND close<bodyMin; R2 needs C.high<=P.high AND
    C.high>P.high) -- both contradictions. And RULE_CARRY (item 5) cannot be reached by a
    non-outside bar. A single tie-ish minute lets every outside bar resolve. Neither is ever
    reached; if one were, an operator would be wrong."""
    Pg = Candle(210, 250, 200, 240)  # bmin 210 bmax 240 high 250 low 200 (paise, small scale)
    guard_hits = 0
    carry_nonoutside = 0
    tested = 0
    for lo in range(180, 251):
        for hi in range(lo, 291):
            for o in {lo, hi, (lo + hi) // 2, 210, 240}:
                for c in {lo, hi, (lo + hi) // 2, 210, 240, 205, 245}:
                    if not (lo <= o <= hi and lo <= c <= hi):
                        continue
                    tested += 1
                    C = Candle(o, hi, lo, c)
                    minutes = [Candle(o, max(hi, 300), min(lo, 150), c)]
                    result = evaluate_pair(Pg, C, lambda: minutes, last_bias=BULLISH)
                    if result.rule == RULE_PRECEDENCE_GUARD:
                        guard_hits += 1
                    if result.rule == RULE_CARRY and not (hi > Pg.high and lo < Pg.low):
                        carry_nonoutside += 1
    assert tested > 100000, "the grid must actually be dense"
    assert guard_hits == 0, "the bullish-precedence guard must be unreachable"
    assert carry_nonoutside == 0, "RULE_CARRY must be unreachable for a non-outside bar"


# --- 8. suppression RESUMES at E+3 (demerger AND Q-6 tier-2 rights, same code path) ----------


def _row(day: date, o: int, h: int, l: int, c: int, symbol: str = "ACME") -> DailyRow:
    return DailyRow(
        trade_date=day, symbol=symbol, series="EQ",
        open_paise=o, high_paise=h, low_paise=l, close_paise=c,
        volume=1000, source_format=FORMAT_ARCHIVE,
    )


def _store_from_candles(root, symbol, candles):
    store = DailyStore.at(root)
    for day, (o, h, l, c) in sorted(candles.items()):
        store.write_rows(day, [_row(day, o, h, l, c, symbol)])
    first, last = min(candles), max(candles)
    outcomes = []
    d = first
    while d <= last:
        if d in candles:
            outcomes.append(DateOutcome(d, OUTCOME_PRESENT, source_format=FORMAT_ARCHIVE,
                                        http_status=200, row_count=1))
        else:
            outcomes.append(DateOutcome(d, OUTCOME_NOT_FOUND, http_status=404))
        d += timedelta(days=1)
    store.record_outcomes(outcomes)
    calendar = TradingCalendar.from_daily_store_range(store, first, last)
    return store, calendar


@pytest.mark.parametrize("kind", [ca.KIND_DEMERGER, ca.KIND_RIGHTS])
def test_suppression_blocks_e1_e2_and_resumes_at_e3(tmp_path, kind) -> None:
    """CONTEXT 3.2: a bias pair spanning a suppression ex-date E is invalid on the two days
    where D-1==E or D-2==E; the normal engine RESUMES from the first pair strictly after E
    (day E+3, pair (E+2, E+1)), carrying the pre-event bias. Demerger and Q-6 tier-2 rights
    (JMCPROJECT-style, no recoverable price) must be consumed identically."""
    # six explicit TRADING days (Mon-Fri then the next Mon; the weekend between Fri and Mon is
    # confirmed-404 in the store, so bias_pair(Mon) correctly skips it).
    d = [date(2024, 3, 4), date(2024, 3, 5), date(2024, 3, 6),
         date(2024, 3, 7), date(2024, 3, 8), date(2024, 3, 11)]
    candles = {
        d[0]: (10000, 11000, 9000, 10500),    # Mon  P0
        d[1]: (10450, 12000, 10400, 11800),   # Tue  breakout of Mon -> seeds bullish on Wed
        d[2]: (11800, 12500, 11700, 12100),   # Wed  E (the suppression ex-date)
        d[3]: (12100, 12300, 11000, 11100),   # Thu  pair (Wed, Tue): D-1 == E -> suppressed
        d[4]: (11100, 11200, 11050, 11150),   # Fri  pair (Thu, Wed): D-2 == E -> suppressed
        d[5]: (11150, 11190, 11060, 11120),   # Mon  pair (Fri, Thu): E+3 resume; Fri inside Thu
    }
    store, calendar = _store_from_candles(tmp_path, "ACME", candles)
    supp = (ca.Suppression("ACME", d[2], kind, f"{kind} test"),)
    engine = BiasEngine(store=store, calendar=calendar, suppressions=supp)
    series = {b.trade_date: b for b in engine.bias_series("ACME", d[2], d[5])}

    assert series[d[2]].bias == BULLISH  # seeded on Tue's breakout, before the ex-date
    assert series[d[3]].suppressed and series[d[3]].rule == "suppressed" and not series[d[3]].tradeable
    assert series[d[4]].suppressed and series[d[4]].rule == "suppressed"
    # E+3 resumes: NOT suppressed, engine runs normally, and it carries the pre-event bias.
    resumed = series[d[5]]
    assert not resumed.suppressed
    assert resumed.rule == RULE_INSIDE  # Fri is inside Thu -> carry
    assert resumed.bias == BULLISH  # the pre-event bias, preserved across the two blocked days
