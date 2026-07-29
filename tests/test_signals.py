"""The pure signal engine (CONTEXT 3.4): the state machine, both sides, every boundary.

CONTEXT 8's F1-F4 live here at SIGNAL level (entry / stop / target as exact integer paise);
chunk 8 asserts the same four again at PnL level. Everything else here is a synthetic day built
to isolate ONE sentence of CONTEXT 3.4, with the expected numbers HAND-COMPUTED in the
docstring so a reader can check the test without running it.

Every long fixture has a full SHORT mirror. CONTEXT 3.4 writes the bearish machine out
explicitly ("Bearish-day mirror, explicit") precisely so it is not hand-derived, so the mirrors
are asserted, never inferred.

**Q-15 is RESOLVED -- option (a), architect, 29-Jul-2026 -- and it touched F1 and F2 only.**
The conflict was between CONTEXT 8's F1/F2 numbers (`POC 2030, entry 2037, SL 2032 (risk 5),
TP 2052`) and CONTEXT 3.4's gap predicate "entry candle's low > POC": the only candle that
yields SL 2032 from the NORMAL rule has low 2032, which is above 2030, so 3.4 routed it to the
gap branch and a different stop. The ruling moves F1/F2's ILLUSTRATIVE POC to 2032 (CONTEXT
v1.4 8) and leaves 3.4 untouched -- every number the trader stated survives, and no rule of his
changes. So each of F1 and F2 is evaluated on ONE set of candles at TWO POCs, with the two
designated differently:

* **the GOLDEN is the ruled POC 2032** -- CONTEXT 8's entry/SL/TP reproduce to the paisa on the
  NORMAL branch, because the entry candle's low TOUCHES the POC and `low > POC` is FALSE. This
  is the boundary the fixture now teaches;
* **the superseded POC 2030 is kept as a recorded MEASUREMENT** of the gap branch on the same
  candles (prior-close stop, risk >= 7) -- not a golden, and no longer a claim about CONTEXT 8.

F4 remains the single gap witness. See QUESTIONS.md Q-15.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from fractions import Fraction

import pytest

from acumen import poc as poc_engine
from acumen import signals as sig
from acumen.aggregate import Bar

#: An ordinary Monday. Nothing in the pure engine reads the calendar; the date only stamps bars.
DAY = date(2026, 7, 20)


def R(rupees: float) -> int:
    """Rupees -> integer paise (CONTEXT 7-E11)."""
    return int(round(rupees * 100))


def POC(rupees: float) -> Fraction:
    """A POC in paise as the exact Fraction the POC engine hands over (CONTEXT 3.3)."""
    return Fraction(R(rupees))


def bar(ordinal: int, o: float, h: float, l: float, c: float, *, day: date = DAY) -> Bar:
    """The ``ordinal``-th 15-minute candle of ``day`` (1-based; the 8th closes at 11:15)."""
    return Bar(
        stamp=sig.bar_open_stamp(day, ordinal),
        open_paise=R(o),
        high_paise=R(h),
        low_paise=R(l),
        close_paise=R(c),
        volume=1_000,
    )


class Minute:
    """A 1-minute bar, for the E10 reference fallback only (it reads stamp + close)."""

    def __init__(self, at: time, close: float, day: date = DAY) -> None:
        self.stamp = datetime.combine(day, at)
        self.close_paise = R(close)


def closes_at(result: sig.SignalDay, ordinal: int) -> bool:
    """Did the entry land on the candle CLOSING at ``ordinal``'s close time?"""
    assert result.entry is not None
    return result.entry.close_stamp == sig.bar_close_stamp(result.day, ordinal)


# ==============================================================================================
# The session grid (CONTEXT 7-E12) and the reference candle's identity
# ==============================================================================================


def test_the_session_grid_ordinals_land_on_the_times_context_3_4_names() -> None:
    """CONTEXT 3.4 names four clock times; every one is DERIVED here from a bar ordinal."""
    assert sig.bar_close_stamp(DAY, sig.REFERENCE_BAR).time() == time(11, 15)
    assert sig.bar_close_stamp(DAY, sig.FIRST_TRIGGER_BAR).time() == time(11, 30)
    assert sig.bar_close_stamp(DAY, sig.LAST_TRIGGER_BAR).time() == time(15, 0)
    assert sig.bar_close_stamp(DAY, sig.SQUARE_OFF_BAR).time() == time(15, 15)
    assert sig.bar_close_stamp(DAY, sig.BARS_PER_SESSION).time() == time(15, 30)
    assert sig.bar_open_stamp(DAY, 1).time() == time(9, 15)


def test_the_reference_candle_is_the_profile_windows_last_candle() -> None:
    """Not a coincidence, and not allowed to drift: CONTEXT 3.3's window is the eight candles
    09:15..11:15 (Q42-confirmed) and CONTEXT 3.4's reference is "the CLOSE of the 11:00-11:15
    candle" -- the same candle. Both modules derive it from the same ordinal, so a change to
    one without the other fails here.
    """
    assert sig.REFERENCE_BAR == poc_engine.SPEC_WINDOW_CANDLES == poc_engine.SPEC_WINDOW.candles
    assert sig.reference_cutoff_stamp(DAY).time() == poc_engine.SPEC_WINDOW.last_time == time(11, 14)


def test_the_bias_decides_the_side_and_an_unseeded_day_has_none() -> None:
    """CONTEXT 3.4: bullish day -> longs only, bearish day -> shorts only (R1-Q24)."""
    from acumen.bias import BEARISH, BULLISH

    assert sig.side_for_bias(BULLISH) == sig.LONG
    assert sig.side_for_bias(BEARISH) == sig.SHORT
    assert sig.side_for_bias(None) is None
    with pytest.raises(sig.SignalError):
        sig.side_for_bias("sideways")


# ==============================================================================================
# F1 -- CONTEXT 8: TCS bullish Entry-1. POC 2032, entry 2037, SL 2032 (risk 5), TP 2052.
# ==============================================================================================
#
# ONE set of candles, TWO POCs: the ruled 2032 (the GOLDEN) and the superseded 2030 (a recorded
# MEASUREMENT of the gap branch) -- see the module docstring and QUESTIONS.md Q-15.
#
#   ord  8 (closes 11:15)  O 2028  H 2029  L 2024  C 2025   <- the reference candle
#   ord  9 (closes 11:30)  O 2033  H 2038  L 2032  C 2037   <- closes above the POC: TRIGGER
#   ord 10 (closes 11:45)  O 2037  H 2041  L 2035  C 2040
#   ord 11 (closes 12:00)  O 2040  H 2055  L 2039  C 2053

F1_BARS = (
    bar(8, 2028, 2029, 2024, 2025),
    bar(9, 2033, 2038, 2032, 2037),
    bar(10, 2037, 2041, 2035, 2040),
    bar(11, 2040, 2055, 2039, 2053),
)


def test_f1_golden_context_8_entry_sl_tp_to_the_paisa_at_the_ruled_poc_2032() -> None:
    """**THE F1 GOLDEN at signal level: CONTEXT 8's entry/SL/TP to the paisa.**

    HAND-COMPUTED at POC 2032 -- the POC CONTEXT v1.4 8 pins for F1, per the Q-15 ruling
    (option (a), 29-Jul-2026: the illustrative POC moves, CONTEXT 3.4 is untouched). It is the
    boundary POC: CONTEXT 3.4's strict "low > POC" gap predicate does NOT fire on this candle
    because its low TOUCHES the POC exactly:

    * reference = the 11:15 close 2025 < POC 2032 -> ARMED (CONTEXT 3.4-1);
    * the candle closing 11:30 closes 2037, strictly above 2032, while ARMED -> TRIGGER;
      **entry = 2037** (R1-Q14, the candle's close);
    * its low is 2032, which is NOT above the POC 2032, so this is a NORMAL entry ->
      **SL = the entry candle's low = 2032**, exactly, no buffer (R1-Q15). **Risk 5.**
    * **TP = 2037 + 3 x 5 = 2052** (CONTEXT 3.4-4).
    * exit: monitoring starts the NEXT candle (E7). 11:45 candle: low 2035 > 2032 and high
      2041 < 2052 -> nothing. 12:00 candle: high 2055 >= 2052 -> TARGET hit.
    """
    result = sig.evaluate_day(F1_BARS, day=DAY, side=sig.LONG, poc_paise=POC(2032))

    assert result.initial_state == sig.STATE_ARMED
    assert result.reference_paise == R(2025)
    assert result.reference_source == sig.REFERENCE_FROM_CANDLE
    assert result.outcome == sig.OUTCOME_ENTERED and result.consumed
    entry = result.entry
    assert entry is not None
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(2037), R(2032), R(2052))
    assert entry.risk_paise == R(5) and not entry.gap_entry
    assert entry.stop_source == sig.STOP_FROM_ENTRY_CANDLE
    assert closes_at(result, 9)
    assert result.exit_event is not None and result.exit_event.kind == sig.EXIT_TARGET
    assert result.exit_event.close_stamp == sig.bar_close_stamp(DAY, 11)


def test_measurement_f1_candles_at_the_superseded_poc_2030_take_the_gap_branch() -> None:
    """**A MEASUREMENT, not a golden: F1's candles at the superseded illustrative POC 2030.**

    The Q-15 ruling moved F1's POC to 2032, so 2030 is no longer CONTEXT 8's F1 and this test
    claims nothing about that fixture. What it still measures is worth keeping: what CONTEXT
    3.4's gap branch -- unchanged by the ruling -- does to these same candles when the POC sits
    below the entry candle's low. HAND-COMPUTED, values unchanged from the build session:

    * reference 2025 < POC 2030 -> ARMED; the 11:30 close 2037 > 2030 -> TRIGGER, entry 2037;
    * the entry candle's low is 2032, which IS above the POC 2030, so 3.4's gap predicate
      fires: **SL = the previous 15-minute candle's close = 2025**, risk 12,
      **TP = 2037 + 36 = 2073**;
    * exit: neither 2025 nor 2073 is touched by 12:00, and no candle trades after it, so the
      day squares off at the last traded candle's close (R1-Q18).

    The two properties Q-15's arithmetic rests on are asserted as properties, not just as these
    numbers: the gap stop is a PRIOR CLOSE and it can never be above the POC (while ARMED every
    close is at or below it), so on a day whose entry is 2037 the gap risk is at least 7 -- never
    CONTEXT 8's 5. That is why the fixture's own POC had to be the thing that moved.
    """
    result = sig.evaluate_day(F1_BARS, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    assert result.initial_state == sig.STATE_ARMED
    assert result.outcome == sig.OUTCOME_ENTERED and result.consumed
    entry = result.entry
    assert entry is not None
    assert entry.entry_paise == R(2037) and closes_at(result, 9)
    assert entry.gap_entry and entry.stop_source == sig.STOP_FROM_PREVIOUS_CLOSE
    assert (entry.stop_paise, entry.risk_paise, entry.target_paise) == (R(2025), R(12), R(2073))
    assert entry.stop_paise <= R(2030) and entry.risk_paise >= R(7)
    assert result.exit_event is not None and result.exit_event.kind == sig.EXIT_SQUARE_OFF


# ==============================================================================================
# F2 -- CONTEXT 8: TCS bullish Entry-2. WAIT-BELOW, close below at 2027 arms, re-cross 2037.
# ==============================================================================================
#
#   ord  8 (closes 11:15)  O 2030  H 2036  L 2029  C 2034  <- reference ABOVE the POC
#   ord  9 (closes 11:30)  O 2034  H 2039  L 2033  C 2038  <- a cross ABOVE while WAIT-BELOW
#   ord 10 (closes 11:45)  O 2038  H 2038  L 2026  C 2027  <- the close below that ARMS
#   ord 11 (closes 12:00)  O 2033  H 2038  L 2032  C 2037  <- the re-cross: TRIGGER
#   ord 12 (closes 12:15)  O 2037  H 2043  L 2036  C 2042
#   ord 13 (closes 12:30)  O 2042  H 2056  L 2041  C 2054

F2_BARS = (
    bar(8, 2030, 2036, 2029, 2034),
    bar(9, 2034, 2039, 2033, 2038),
    bar(10, 2038, 2038, 2026, 2027),
    bar(11, 2033, 2038, 2032, 2037),
    bar(12, 2037, 2043, 2036, 2042),
    bar(13, 2042, 2056, 2041, 2054),
)


def test_f2_golden_context_8_entry_sl_tp_to_the_paisa_at_the_ruled_poc_2032() -> None:
    """**THE F2 GOLDEN at signal level: CONTEXT 8's entry/SL/TP to the paisa** (POC 2032, the
    POC CONTEXT v1.4 8 pins for F2 per the Q-15 ruling, option (a), 29-Jul-2026).

    HAND-COMPUTED, and it walks the whole Entry-2 path CONTEXT 8 describes:

    * reference = the 11:15 close 2034 > POC 2032 -> **WAIT-BELOW** (CONTEXT 8 F2's "initial
      state WAIT-BELOW");
    * 11:30 closes 2038, above the POC -- but the day is still WAIT-BELOW, so it is NOT a cross
      and consumes NOTHING (CONTEXT 3.4-2, R1-Q19b);
    * 11:45 closes **2027**, strictly below 2032 -> ARMED (CONTEXT 8 F2's "close below at 2027
      arms");
    * 12:00 closes **2037**, strictly above while ARMED -> TRIGGER, **entry 2037**;
    * its low 2032 is not above the POC 2032 -> normal stop = **2032**, **risk 5**,
      **TP = 2037 + 15 = 2052**;
    * exit: 12:15 low 2036 > 2032, high 2043 < 2052 -> nothing; 12:30 high 2056 >= 2052 -> TARGET.
    """
    result = sig.evaluate_day(F2_BARS, day=DAY, side=sig.LONG, poc_paise=POC(2032))

    assert result.initial_state == sig.STATE_WAIT_BELOW
    assert result.reference_paise == R(2034)
    # the 11:30 cross while waiting changed nothing at all
    first = result.transitions[0]
    assert first.close_stamp == sig.bar_close_stamp(DAY, 9)
    assert first.state_before == first.state_after == sig.STATE_WAIT_BELOW
    assert "nothing consumed" in first.note
    # the 11:45 close arms
    assert result.transitions[1].state_after == sig.STATE_ARMED
    assert result.transitions[1].close_paise == R(2027)

    entry = result.entry
    assert entry is not None and closes_at(result, 11)
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(2037), R(2032), R(2052))
    assert entry.risk_paise == R(5) and not entry.gap_entry
    assert result.exit_event is not None and result.exit_event.kind == sig.EXIT_TARGET
    assert result.exit_event.close_stamp == sig.bar_close_stamp(DAY, 13)


def test_measurement_f2_candles_at_the_superseded_poc_2030_take_the_gap_branch() -> None:
    """**A MEASUREMENT, not a golden**: F2's candles at the superseded illustrative POC 2030 --
    the same gap-branch measurement as its F1 counterpart, on the Entry-2 path.

    HAND-COMPUTED under CONTEXT 3.4, which the Q-15 ruling left untouched; values unchanged from
    the build session. The state walk is identical to the golden's (2034 > 2030 -> WAIT-BELOW;
    2038 above while waiting consumes nothing; 2027 < 2030 arms; 2037 > 2030 triggers at entry
    2037), but the entry candle's low 2032 is above the POC 2030, so the gap branch takes
    **SL = the previous candle's close = 2027**, risk 10, **TP = 2037 + 30 = 2067**. Exit:
    nothing touches 2027 or 2067, so the day squares off.

    The same two properties are asserted here: the stop is a prior close at or below the POC, so
    the risk is at least 7 -- the arming path cannot produce CONTEXT 8's 5 on this branch.
    """
    result = sig.evaluate_day(F2_BARS, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    assert result.initial_state == sig.STATE_WAIT_BELOW
    entry = result.entry
    assert entry is not None and closes_at(result, 11)
    assert entry.entry_paise == R(2037) and entry.gap_entry
    assert entry.stop_source == sig.STOP_FROM_PREVIOUS_CLOSE
    assert (entry.stop_paise, entry.risk_paise, entry.target_paise) == (R(2027), R(10), R(2067))
    assert entry.stop_paise <= R(2030) and entry.risk_paise >= R(7)
    assert result.exit_event is not None and result.exit_event.kind == sig.EXIT_SQUARE_OFF


# ==============================================================================================
# F3 -- CONTEXT 8: TCS bearish Entry-1. entry 1980, SL 1988 (candle HIGH, risk 8), TP 1956.
# ==============================================================================================


def test_f3_bearish_entry_1_reproduces_context_8_exactly() -> None:
    """**F3 at signal level** (CONTEXT 8 + the R1-Q1/Q2 corrections), HAND-COMPUTED at POC 1985.

    CONTEXT 8 pins no POC for F3, so the day is built at 1985 -- above the entry close 1980 (so
    the close is strictly below the POC and triggers) and below the entry candle's high 1988 (so
    the candle DID trade at/above the POC and the bearish gap rule does not fire).

    * bearish day -> SHORT only (CONTEXT 3.4, R1-Q24);
    * reference = the 11:15 close 1990 > POC 1985 -> **ARMED** (the bearish mirror: above arms);
    * the candle closing 11:30 closes **1980**, strictly BELOW the POC while ARMED -> TRIGGER,
      **entry 1980**;
    * its high 1988 is not below the POC -> normal stop = the entry candle's **HIGH = 1988**
      (R1-Q2), **risk 8**;
    * **TP = 1980 - 3 x 8 = 1956** -- the PDF's "2004" was a confirmed typo (R1-Q1);
    * exit: 11:45 high 1984 < 1988 and low 1975 > 1956 -> nothing; 12:00 low 1954 <= 1956 ->
      TARGET hit.
    """
    bars = (
        bar(8, 1992, 1994, 1988, 1990),
        bar(9, 1987, 1988, 1979, 1980),
        bar(10, 1980, 1984, 1975, 1977),
        bar(11, 1977, 1979, 1954, 1958),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.SHORT, poc_paise=POC(1985))

    assert result.initial_state == sig.STATE_ARMED and result.reference_paise == R(1990)
    entry = result.entry
    assert entry is not None and closes_at(result, 9)
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(1980), R(1988), R(1956))
    assert entry.risk_paise == R(8) and not entry.gap_entry
    assert entry.stop_source == sig.STOP_FROM_ENTRY_CANDLE_SHORT
    assert result.exit_event is not None and result.exit_event.kind == sig.EXIT_TARGET
    assert result.exit_event.close_stamp == sig.bar_close_stamp(DAY, 11)


# ==============================================================================================
# F4 -- CONTEXT 8: gap entry. prior close 2028 -> gap candle low 2034, close 2042 -> SL 2028.
# ==============================================================================================


def test_f4_gap_entry_takes_the_previous_candles_close_and_reproduces_context_8() -> None:
    """**F4 at signal level** (R2-Q33's worked numbers), HAND-COMPUTED at POC 2030.

    The POC must sit above the prior close 2028 (so the day can be ARMED there) and below the
    gap candle's low 2034 (so the gap predicate fires); 2030 is the TCS example's own POC.

    * reference = the 11:15 close 2029 < POC 2030 -> ARMED;
    * 11:30 closes **2028**, below the POC -- while ARMED that is not a trigger, and it is the
      "prior close" R2-Q33 names;
    * 11:45 opens 2035 and never trades at or below the POC (**low 2034 > 2030**) and closes
      **2042** -> TRIGGER, **entry 2042**, and it is a **GAP entry**;
    * so the stop is the last traded price before the jump = **the previous candle's close,
      2028** (R2-Q33 option b), **risk 14**;
    * **TP = 2042 + 3 x 14 = 2084**;
    * exit: 12:00 touches neither; 12:15 high 2086 >= 2084 -> TARGET hit.
    """
    bars = (
        bar(8, 2031, 2032, 2027, 2029),
        bar(9, 2029, 2030, 2026, 2028),
        bar(10, 2035, 2044, 2034, 2042),
        bar(11, 2042, 2050, 2040, 2048),
        bar(12, 2048, 2086, 2047, 2085),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    entry = result.entry
    assert entry is not None and closes_at(result, 10)
    assert entry.gap_entry and entry.stop_source == sig.STOP_FROM_PREVIOUS_CLOSE
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(2042), R(2028), R(2084))
    assert entry.risk_paise == R(14)
    assert result.exit_event is not None and result.exit_event.kind == sig.EXIT_TARGET
    assert result.exit_event.close_stamp == sig.bar_close_stamp(DAY, 12)


def test_the_bearish_gap_mirror_takes_the_previous_close_too() -> None:
    """The SHORT mirror of F4, from CONTEXT 3.4's own mirror paragraph ("Gap entry = entry
    candle's high < POC (never traded at/above it) -> SL = previous 15-min candle's close").

    HAND-COMPUTED at POC 1985: reference 1990 > 1985 -> ARMED; 11:30 closes 1987, above the POC
    and therefore not a trigger on a short day -- it is the prior close; 11:45 never trades at or
    above the POC (**high 1981 < 1985**) and closes **1973** -> TRIGGER, gap entry, stop = the
    previous close **1987**, **risk 14**, **TP = 1973 - 42 = 1931**; 12:15's low 1929 <= 1931 ->
    TARGET.
    """
    bars = (
        bar(8, 1988, 1992, 1986, 1990),
        bar(9, 1990, 1991, 1986, 1987),
        bar(10, 1980, 1981, 1971, 1973),
        bar(11, 1973, 1975, 1965, 1968),
        bar(12, 1968, 1970, 1929, 1932),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.SHORT, poc_paise=POC(1985))

    entry = result.entry
    assert entry is not None and closes_at(result, 10)
    assert entry.gap_entry and entry.stop_source == sig.STOP_FROM_PREVIOUS_CLOSE
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(1973), R(1987), R(1931))
    assert entry.risk_paise == R(14)
    assert result.exit_event is not None and result.exit_event.kind == sig.EXIT_TARGET


# ==============================================================================================
# EDGE: a close exactly ON the POC while ARMED (CONTEXT 3.4-2, R2-Q34c)
# ==============================================================================================


def test_a_close_exactly_on_the_poc_while_armed_is_not_a_trigger_and_consumes_nothing() -> None:
    """CONTEXT 3.4-2: "A close == POC while ARMED: not a trigger, state stays ARMED, nothing is
    consumed."

    HAND-COMPUTED at POC 2030: reference 2025 arms the day; the 11:30 candle closes EXACTLY
    2030 -- not strictly above -- so there is no trigger, the state is still ARMED afterwards,
    the day is not consumed, and the 11:45 close 2028 leaves it armed too. No cross ever comes,
    so the day ends armed with nothing consumed.
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2026, 2032, 2025, 2030),
        bar(10, 2030, 2031, 2027, 2028),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    at_poc = result.transitions[0]
    assert at_poc.side_of_poc == sig.AT_POC
    assert at_poc.state_before == at_poc.state_after == sig.STATE_ARMED
    assert result.final_state == sig.STATE_ARMED
    assert result.outcome == sig.OUTCOME_ARMED_NO_CROSS
    assert not result.consumed and result.entry is None


def test_a_later_cross_still_trades_after_a_close_exactly_on_the_poc() -> None:
    """The behavioural half of the same sentence: because the ==POC candle consumed nothing,
    the NEXT close strictly above the POC is still the day's first qualifying cross.

    HAND-COMPUTED at POC 2030: 11:30 closes exactly 2030 (nothing); 11:45 closes 2035 ->
    TRIGGER, entry 2035, low 2029 is not above the POC so the stop is that low, risk 6,
    TP = 2035 + 18 = 2053.
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2026, 2032, 2025, 2030),
        bar(10, 2030, 2036, 2029, 2035),
        bar(11, 2035, 2038, 2033, 2036),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    entry = result.entry
    assert entry is not None and closes_at(result, 10)
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(2035), R(2029), R(2053))


def test_the_short_mirror_a_close_exactly_on_the_poc_while_armed_is_not_a_trigger() -> None:
    """The SHORT mirror: on a bearish day the trigger is a close strictly BELOW the POC, so a
    close exactly ON it is not a trigger either and consumes nothing.

    HAND-COMPUTED at POC 1985: reference 1990 > 1985 arms; 11:30 closes exactly 1985 -> nothing;
    11:45 closes 1980, strictly below, while still ARMED -> TRIGGER, entry 1980, stop = the
    candle's high 1986, risk 6, TP = 1980 - 18 = 1962.
    """
    bars = (
        bar(8, 1992, 1994, 1988, 1990),
        bar(9, 1988, 1990, 1984, 1985),
        bar(10, 1985, 1986, 1979, 1980),
        bar(11, 1980, 1983, 1978, 1979),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.SHORT, poc_paise=POC(1985))

    assert result.transitions[0].side_of_poc == sig.AT_POC
    assert result.transitions[0].state_after == sig.STATE_ARMED
    entry = result.entry
    assert entry is not None and closes_at(result, 10)
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(1980), R(1986), R(1962))


# ==============================================================================================
# EDGE: the WAIT rule -- reference == POC (trader Q34b + Round-3 Q41 option A)
# ==============================================================================================
#
# QUESTIONS.md ROUND-3 FINAL RECEIPTS R3F-d. This SUPERSEDES the plan.md chunk-7 card's
# "OPEN-3 day (logged, no trade)" fixture: the card predates the ruling, and building its
# fixture literally would re-implement an interim the trader has now answered. The card's
# no-trade day is therefore built INVERTED -- these days TRADE -- exactly as decision B121
# handled the E4 amendment in chunk 6.


def test_the_wait_rule_a_first_distinct_close_above_only_sets_the_side() -> None:
    """CONTEXT 3.4-1: reference == POC -> no side yet; the first 15-minute candle to close
    strictly above or below SETS the side "and ONLY sets it (it is never itself the entry --
    Q41 option A)". First distinct close ABOVE -> WAIT-BELOW, the Entry-2 path.

    HAND-COMPUTED at POC 2030 on a bullish day:

    * reference = the 11:15 close **2030 == POC** -> side-unset;
    * 11:30 closes **2033**, the first distinct close: it sets the side and puts the day in
      WAIT-BELOW. **It is not the entry** even though it closed above the POC on a long day;
    * 11:45 dips to close **2026**, strictly below -> ARMED;
    * 12:00 re-crosses to close **2035** -> TRIGGER, entry 2035, low 2029 is not above the POC
      so the stop is that low, risk 6, TP = 2035 + 18 = 2053.
    """
    bars = (
        bar(8, 2029, 2032, 2028, 2030),
        bar(9, 2030, 2034, 2029, 2033),
        bar(10, 2033, 2033, 2025, 2026),
        bar(11, 2027, 2036, 2029, 2035),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    assert result.initial_state == sig.STATE_SIDE_UNSET
    setter = result.transitions[0]
    assert setter.close_stamp == sig.bar_close_stamp(DAY, 9) and setter.close_paise == R(2033)
    assert setter.state_before == sig.STATE_SIDE_UNSET
    assert setter.state_after == sig.STATE_WAIT_BELOW
    assert "never itself the entry" in setter.note
    assert result.transitions[1].state_after == sig.STATE_ARMED

    entry = result.entry
    assert entry is not None and closes_at(result, 11)
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(2035), R(2029), R(2053))


def test_the_wait_rule_a_first_distinct_close_below_arms_the_day_directly() -> None:
    """The other branch of the same sentence: "First distinct close below -> ARMED."

    HAND-COMPUTED at POC 2030 on a bullish day: reference 2030 == POC -> side-unset; 11:30
    closes **2026**, the first distinct close, strictly below -> ARMED **directly** (and it is
    not an entry either -- it closed below the POC); 11:45 closes **2035** -> TRIGGER, entry
    2035, stop = its low 2029, risk 6, TP 2053.
    """
    bars = (
        bar(8, 2029, 2032, 2028, 2030),
        bar(9, 2030, 2031, 2025, 2026),
        bar(10, 2027, 2036, 2029, 2035),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    assert result.initial_state == sig.STATE_SIDE_UNSET
    assert result.transitions[0].state_after == sig.STATE_ARMED
    entry = result.entry
    assert entry is not None and closes_at(result, 10)
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(2035), R(2029), R(2053))


def test_the_wait_rule_short_mirror_a_first_distinct_close_below_only_sets_the_side() -> None:
    """The SHORT mirror of the Entry-2 branch: on a bearish day the trigger side is BELOW, so
    the first distinct close BELOW sets the side and puts the day in **WAIT-ABOVE**.

    HAND-COMPUTED at POC 1985: reference 1985 == POC -> side-unset; 11:30 closes **1982**, the
    first distinct close, and it only sets the side (WAIT-ABOVE) -- not an entry; 11:45 closes
    **1989**, strictly above -> ARMED; 12:00 closes **1979** -> TRIGGER, entry 1979, stop = its
    high 1986, risk 7, TP = 1979 - 21 = 1958.
    """
    bars = (
        bar(8, 1984, 1987, 1983, 1985),
        bar(9, 1985, 1986, 1981, 1982),
        bar(10, 1982, 1990, 1981, 1989),
        bar(11, 1985, 1986, 1978, 1979),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.SHORT, poc_paise=POC(1985))

    assert result.initial_state == sig.STATE_SIDE_UNSET
    setter = result.transitions[0]
    assert setter.state_after == sig.STATE_WAIT_ABOVE and "never itself the entry" in setter.note
    assert result.transitions[1].state_after == sig.STATE_ARMED
    entry = result.entry
    assert entry is not None and closes_at(result, 11)
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(1979), R(1986), R(1958))


def test_the_wait_rule_short_mirror_a_first_distinct_close_above_arms_directly() -> None:
    """The SHORT mirror of the direct-arm branch.

    HAND-COMPUTED at POC 1985: reference 1985 == POC -> side-unset; 11:30 closes **1989**,
    strictly above -> ARMED directly; 11:45 closes **1979** -> TRIGGER, entry 1979, stop = its
    high 1986, risk 7, TP 1958.
    """
    bars = (
        bar(8, 1984, 1987, 1983, 1985),
        bar(9, 1985, 1990, 1984, 1989),
        bar(10, 1985, 1986, 1978, 1979),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.SHORT, poc_paise=POC(1985))

    assert result.initial_state == sig.STATE_SIDE_UNSET
    assert result.transitions[0].state_after == sig.STATE_ARMED
    entry = result.entry
    assert entry is not None and closes_at(result, 10)
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(1979), R(1986), R(1958))


def test_the_wait_rule_never_resolves_when_no_close_is_ever_distinct() -> None:
    """If no candle ever closes strictly off the POC, no side is ever set: no trade, and --
    crucially -- nothing is consumed, because no cross ever happened."""
    bars = (
        bar(8, 2029, 2032, 2028, 2030),
        bar(9, 2030, 2033, 2027, 2030),
        bar(10, 2030, 2031, 2029, 2030),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    assert result.final_state == sig.STATE_SIDE_UNSET
    assert result.outcome == sig.OUTCOME_SIDE_NEVER_SET
    assert not result.consumed and result.entry is None


# ==============================================================================================
# EDGE: crosses during WAIT consume nothing (CONTEXT 3.4-2, R1-Q19b)
# ==============================================================================================


def test_crosses_above_the_poc_during_wait_below_consume_nothing_and_the_day_never_arms() -> None:
    """CONTEXT 3.4-2: "Closes above POC while still WAIT-BELOW do NOT count or consume anything
    -- 'first cross' is counted from the ARMED state only."

    HAND-COMPUTED at POC 2030: reference 2036 > 2030 -> WAIT-BELOW. Three later candles close
    2038, 2041 and 2030 -- two above the POC and one exactly ON it. None arms the day (only a
    close STRICTLY below arms), none is a trigger, and none consumes the day. The day ends
    WAIT-BELOW, never armed, NOT consumed -- so on a real run this stock-day is still available
    to nothing at all, which is the point: consumption is what blocks a re-entry, and there was
    no entry to block.
    """
    bars = (
        bar(8, 2032, 2038, 2031, 2036),
        bar(9, 2036, 2040, 2035, 2038),
        bar(10, 2038, 2043, 2037, 2041),
        bar(11, 2041, 2042, 2029, 2030),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    assert result.initial_state == sig.STATE_WAIT_BELOW
    assert [t.state_after for t in result.transitions] == [sig.STATE_WAIT_BELOW] * 3
    assert result.outcome == sig.OUTCOME_NEVER_ARMED
    assert not result.consumed and result.entry is None
    assert "nothing consumed" in result.transitions[0].note


def test_the_short_mirror_crosses_below_the_poc_during_wait_above_consume_nothing() -> None:
    """The SHORT mirror: on a bearish day in WAIT-ABOVE, closes BELOW the POC count for nothing.

    HAND-COMPUTED at POC 1985: reference 1979 < 1985 -> WAIT-ABOVE; later closes 1977, 1974 and
    exactly 1985 never arm the day (only a close strictly ABOVE arms), so it ends never-armed
    and unconsumed.
    """
    bars = (
        bar(8, 1983, 1984, 1978, 1979),
        bar(9, 1979, 1980, 1976, 1977),
        bar(10, 1977, 1978, 1973, 1974),
        bar(11, 1974, 1986, 1973, 1985),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.SHORT, poc_paise=POC(1985))

    assert result.initial_state == sig.STATE_WAIT_ABOVE
    assert result.outcome == sig.OUTCOME_NEVER_ARMED
    assert not result.consumed and result.entry is None


# ==============================================================================================
# EDGE: an unsizable cross CONSUMES the stock-day (CONTEXT 3.4-2/3)
# ==============================================================================================


def test_an_unsizable_cross_consumes_the_day_and_is_logged() -> None:
    """CONTEXT 3.4-2: "The first qualifying cross CONSUMES the stock-day even if the trade is
    unsizable (entry == SL or qty rounds to 0): no later entry that day; logged as a skipped
    signal." CONTEXT 3.4-3: "Degenerate entry == SL -> no trade (cannot size) -- log to run
    report."

    At SIGNAL level the reachable half is `entry == SL`; `qty == 0` needs the rupee risk and is
    chunk 8's. Reaching `entry == SL` at all takes the one shape where the stop is not bounded
    by the state machine (see the property test below): a GAP entry whose reference candle is
    MISSING, so the "previous 15-minute candle" is older than the reference and its close is
    unconstrained.

    HAND-COMPUTED at POC 2030: no candle trades 11:00-11:15, so E10 supplies the reference from
    the last 1-minute close at or before 11:14 -- **2025 at 10:59**, which is below the POC, so
    the day is ARMED. The 11:30 candle never trades at or below the POC (**low 2036 > 2030**) and
    closes **2037** -> TRIGGER and a GAP entry, so the stop is the previous 15-minute candle's
    close -- the 10:45 candle's **2037**. Entry 2037 == stop 2037: risk 0, unsizable. The day is
    CONSUMED, there is no entry, and the reason is logged.

    The later candle closing 2045 proves the consumption is real: it would have been a perfectly
    good cross, and it is not evaluated.
    """
    bars = (
        bar(7, 2030, 2038, 2029, 2037),
        bar(9, 2038, 2040, 2036, 2037),
        bar(10, 2037, 2046, 2036, 2045),
    )
    minutes = (Minute(time(10, 59), 2025),)
    result = sig.evaluate_day(
        bars, day=DAY, side=sig.LONG, poc_paise=POC(2030), minute_bars=minutes
    )

    assert result.reference_source == sig.REFERENCE_FROM_MINUTES
    assert result.reference_paise == R(2025) and result.initial_state == sig.STATE_ARMED
    assert result.outcome == sig.OUTCOME_UNSIZABLE
    assert result.consumed and result.entry is None and result.exit_event is None
    assert result.log is not None and "CONSUMED" in result.log
    # the trigger IS in the trail, and nothing after it was evaluated
    assert result.transitions[-1].close_stamp == sig.bar_close_stamp(DAY, 9)


def test_the_short_mirror_an_unsizable_gap_cross_consumes_the_day() -> None:
    """The SHORT mirror of the same shape.

    HAND-COMPUTED at POC 1985: the 11:00-11:15 candle is missing, E10 takes the 10:59 one-minute
    close **1990** (above the POC -> ARMED on a bearish day); the 11:30 candle never trades at or
    above the POC (**high 1974 < 1985**) and closes **1973** -> gap entry, stop = the 10:45
    candle's close **1973** == entry -> risk 0, unsizable, day CONSUMED.
    """
    bars = (
        bar(7, 1980, 1981, 1972, 1973),
        bar(9, 1972, 1974, 1970, 1973),
        bar(10, 1973, 1975, 1960, 1962),
    )
    minutes = (Minute(time(10, 59), 1990),)
    result = sig.evaluate_day(
        bars, day=DAY, side=sig.SHORT, poc_paise=POC(1985), minute_bars=minutes
    )

    assert result.initial_state == sig.STATE_ARMED
    assert result.outcome == sig.OUTCOME_UNSIZABLE and result.consumed
    assert result.entry is None


def test_on_an_ordinary_day_the_risk_is_always_strictly_positive() -> None:
    """The property behind the fixture above, and the arithmetic QUESTIONS.md Q-15 rests on.

    While a day is ARMED every close sits at or below the POC (a close strictly above IS the
    trigger, so none can precede it), and the arming close is strictly below it. So on a long
    day whose reference candle is present, the stop -- the entry candle's low when it traded at
    or below the POC, otherwise the previous candle's close -- is always at or below the POC,
    while the entry close is always strictly above it. Risk is therefore >= 1 paisa, and
    `entry == SL` is UNREACHABLE. Swept over a deterministic grid of both shapes.
    """
    poc = POC(2030)
    for low in (2020, 2025, 2029, 2030, 2031, 2034):  # below, on, and above the POC
        for close in (2031, 2035, 2042):
            if close < low:
                continue
            bars = (
                bar(8, 2028, 2029, 2024, 2025),  # reference below the POC -> ARMED
                bar(9, 2029, 2030, 2026, 2028),  # a close below the POC while ARMED
                bar(10, low, max(close, low), low, close),
            )
            result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=poc)
            assert result.entry is not None, (low, close)
            assert result.entry.risk_paise > 0, (low, close, result.entry)
            assert result.entry.entry_paise > result.entry.stop_paise


# ==============================================================================================
# EDGE: a day with no qualifying cross at all (CONTEXT 3.4-6)
# ==============================================================================================


def test_a_no_cross_day_trades_nothing_and_consumes_nothing() -> None:
    """CONTEXT 3.4-6: "price never gives a qualifying close across POC -> no entry that day".

    HAND-COMPUTED at POC 2030: reference 2025 arms the day, and every later close (2026, 2028,
    2029) is below the POC. Armed all day, no cross, nothing consumed.
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2025, 2029, 2024, 2026),
        bar(10, 2026, 2029, 2025, 2028),
        bar(23, 2028, 2030, 2027, 2029),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    assert result.final_state == sig.STATE_ARMED
    assert result.outcome == sig.OUTCOME_ARMED_NO_CROSS
    assert not result.consumed and result.entry is None and result.exit_event is None


def test_the_short_mirror_of_a_no_cross_day() -> None:
    """HAND-COMPUTED at POC 1985: reference 1990 arms the bearish day; every later close (1989,
    1987, 1985) is at or above the POC, so no close is ever strictly below it. No trade."""
    bars = (
        bar(8, 1992, 1994, 1988, 1990),
        bar(9, 1990, 1993, 1988, 1989),
        bar(10, 1989, 1991, 1986, 1987),
        bar(23, 1987, 1988, 1984, 1985),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.SHORT, poc_paise=POC(1985))

    assert result.outcome == sig.OUTCOME_ARMED_NO_CROSS
    assert not result.consumed and result.entry is None


# ==============================================================================================
# EDGE: the trading window ends at the 15:00 close (R2-Q30)
# ==============================================================================================


def test_a_signal_on_the_candle_closing_at_15_00_is_valid() -> None:
    """CONTEXT 3.1/3.4-2: entries run "up to and including the 15-min candle that closes at
    15:00". The 23rd candle of the session is that candle.

    HAND-COMPUTED at POC 2030: reference 2025 arms; the candle closing **15:00** closes 2035 ->
    TRIGGER, entry 2035, stop = its low 2029, risk 6, TP 2053. The candle closing 15:15 then
    touches neither, so the day squares off at ITS close (R1-Q18).
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(23, 2029, 2036, 2029, 2035),
        bar(24, 2035, 2037, 2033, 2034),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    entry = result.entry
    assert entry is not None
    assert entry.close_stamp == datetime.combine(DAY, time(15, 0))
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(2035), R(2029), R(2053))
    assert result.exit_event is not None and result.exit_event.kind == sig.EXIT_SQUARE_OFF
    assert result.exit_event.close_stamp == datetime.combine(DAY, time(15, 15))


def test_a_cross_on_the_candle_closing_at_15_15_or_later_can_never_be_a_signal() -> None:
    """The other side of R2-Q30: the candle closing at 15:15 is the SQUARE-OFF candle and the
    one closing at 15:30 is past the session's trading window entirely. Neither may open a
    trade, however cleanly it crosses.

    HAND-COMPUTED at POC 2030: reference 2025 arms the day and NOTHING closes above the POC in
    the window; the two candles that do close above it (2038 at 15:15 and 2044 at 15:30) are
    both outside it. The day ends ARMED with no trade and nothing consumed.
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(23, 2025, 2029, 2024, 2028),
        bar(24, 2028, 2039, 2027, 2038),
        bar(25, 2038, 2045, 2037, 2044),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    assert result.outcome == sig.OUTCOME_ARMED_NO_CROSS
    assert result.entry is None and not result.consumed
    # only the 15:00-closing candle was ever evaluated
    assert [t.close_stamp.time() for t in result.transitions] == [time(15, 0)]


def test_the_short_mirror_of_the_15_00_last_entry_boundary() -> None:
    """HAND-COMPUTED at POC 1985: reference 1990 arms the bearish day; the candle closing 15:00
    closes 1980 -> TRIGGER, entry 1980, stop = its high 1986, risk 6, TP = 1980 - 18 = 1962; the
    15:15 candle touches neither, so the day squares off there. A cross on the 15:15 candle
    would have been ignored -- proven by the long case above, and by the fact that this entry
    is the LAST transition in the trail."""
    bars = (
        bar(8, 1992, 1994, 1988, 1990),
        bar(23, 1986, 1986, 1979, 1980),
        bar(24, 1980, 1983, 1978, 1979),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.SHORT, poc_paise=POC(1985))

    entry = result.entry
    assert entry is not None and entry.close_stamp == datetime.combine(DAY, time(15, 0))
    assert (entry.entry_paise, entry.stop_paise, entry.target_paise) == (R(1980), R(1986), R(1962))
    assert result.exit_event is not None and result.exit_event.kind == sig.EXIT_SQUARE_OFF


# ==============================================================================================
# EXITS (CONTEXT 3.4-5 + 7-E7)
# ==============================================================================================


def test_the_entry_candle_can_never_trigger_its_own_stop() -> None:
    """CONTEXT 7-E7: "Entry candle itself cannot trigger SL/TP (position starts at its close);
    monitoring starts next candle."

    This is not a corner case: on a NORMAL long entry the stop IS the entry candle's own low, so
    without E7 every single trade would stop out on the candle it opened. HAND-COMPUTED at POC
    2030: entry 2037 on the 11:30 candle with stop = its low 2032; the NEXT candle's low is 2031,
    which is below the stop, so the stop is hit THERE -- one candle later, not on the entry.
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2033, 2038, 2032, 2037),
        bar(10, 2036, 2037, 2031, 2032),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2032))

    entry = result.entry
    assert entry is not None and entry.stop_paise == R(2032)
    exit_event = result.exit_event
    assert exit_event is not None and exit_event.kind == sig.EXIT_STOP
    assert exit_event.stamp != entry.stamp
    assert exit_event.close_stamp == sig.bar_close_stamp(DAY, 10)


def test_when_one_candle_touches_both_the_stop_wins() -> None:
    """CONTEXT 3.4-5, R1-Q20: "Both touched in the same candle -> SL wins."

    HAND-COMPUTED at POC 2032: entry 2037, stop 2032, risk 5, TP 2052. The next candle runs
    2031..2055 -- it touches the stop (2031 <= 2032) AND the target (2055 >= 2052). The stop
    wins, and the ambiguity is RECORDED (``both_touched``) so the report can disclose how often
    the backtest resolved a candle pessimistically.
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2033, 2038, 2032, 2037),
        bar(10, 2037, 2055, 2031, 2050),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2032))

    exit_event = result.exit_event
    assert exit_event is not None
    assert exit_event.kind == sig.EXIT_STOP and exit_event.both_touched
    assert "the stop wins" in exit_event.detail


def test_the_short_mirror_when_one_candle_touches_both_the_stop_wins() -> None:
    """The SHORT mirror: stop above, target below, and a candle spanning both pays the stop.

    HAND-COMPUTED at POC 1985: entry 1980, stop = the entry candle's high 1988, risk 8, TP 1956.
    The next candle runs 1950..1990: it touches the stop (1990 >= 1988) and the target
    (1950 <= 1956). The stop wins.
    """
    bars = (
        bar(8, 1992, 1994, 1988, 1990),
        bar(9, 1987, 1988, 1979, 1980),
        bar(10, 1980, 1990, 1950, 1955),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.SHORT, poc_paise=POC(1985))

    exit_event = result.exit_event
    assert exit_event is not None
    assert exit_event.kind == sig.EXIT_STOP and exit_event.both_touched


def test_an_untouched_trade_squares_off_at_the_15_15_candles_close() -> None:
    """CONTEXT 3.4-5, R1-Q18: "Neither by 15:15 -> square off at the 15:00-15:15 candle's
    close." The marker names that candle; chunk 8 prices it.

    HAND-COMPUTED at POC 2032: entry 2037 at 11:30 with stop 2032 and TP 2052; the 11:45 candle
    and the 15:00-15:15 candle both stay strictly inside 2032..2052, so the exit is the
    square-off marker on the candle CLOSING at 15:15.
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2033, 2038, 2032, 2037),
        bar(10, 2037, 2040, 2034, 2039),
        bar(24, 2039, 2044, 2035, 2041),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2032))

    exit_event = result.exit_event
    assert exit_event is not None and exit_event.kind == sig.EXIT_SQUARE_OFF
    assert exit_event.close_stamp == datetime.combine(DAY, time(15, 15))
    assert not exit_event.both_touched


def test_the_square_off_never_looks_at_the_candle_closing_at_15_30() -> None:
    """The 25th candle closes at 15:30 -- after the square-off. It can neither exit a trade nor
    move the square-off marker.

    HAND-COMPUTED at POC 2032: entry 2037, stop 2032, TP 2052. The 15:00-15:15 candle stays
    inside the band, so the day squares off there. The 15:15-15:30 candle then trades down to
    2020 -- straight through the stop -- and is IGNORED.
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2033, 2038, 2032, 2037),
        bar(24, 2037, 2044, 2035, 2041),
        bar(25, 2041, 2042, 2020, 2021),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2032))

    exit_event = result.exit_event
    assert exit_event is not None and exit_event.kind == sig.EXIT_SQUARE_OFF
    assert exit_event.close_stamp == datetime.combine(DAY, time(15, 15))


def test_a_target_hit_beats_a_later_stop_because_the_walk_stops_at_the_first_exit() -> None:
    """One trade, one exit: the first candle that touches either level ends it.

    HAND-COMPUTED at POC 2032: entry 2037, stop 2032, TP 2052; the 11:45 candle reaches 2053 ->
    TARGET; the 12:00 candle then collapses to 2010, which is never looked at.
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2033, 2038, 2032, 2037),
        bar(10, 2037, 2053, 2036, 2050),
        bar(11, 2050, 2051, 2010, 2012),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2032))

    assert result.exit_event is not None
    assert result.exit_event.kind == sig.EXIT_TARGET
    assert result.exit_event.close_stamp == sig.bar_close_stamp(DAY, 10)


def test_one_trade_per_stock_day_no_re_entry_after_the_first_cross() -> None:
    """CONTEXT 3.4-2, R1-Q16: max one trade per stock per day, no re-entry after any exit.

    HAND-COMPUTED at POC 2032: the 11:30 candle triggers at 2037 and the 11:45 candle stops it
    out at 2032. The 12:00 candle then closes 2045 -- a textbook cross -- and produces nothing:
    the walk ended at the first qualifying cross, so it is not even in the transition trail.
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2033, 2038, 2032, 2037),
        bar(10, 2036, 2037, 2031, 2033),
        bar(11, 2033, 2046, 2032, 2045),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2032))

    assert result.exit_event is not None and result.exit_event.kind == sig.EXIT_STOP
    assert [t.close_stamp for t in result.transitions] == [sig.bar_close_stamp(DAY, 9)]


def test_a_trade_with_no_candle_after_it_squares_off_at_its_own_close() -> None:
    """The degenerate tail: the entry lands on the 15:00 close and NOTHING trades in the last
    quarter-hour, so the day's last traded 15-minute close is the entry candle's own. The
    square-off is marked there rather than invented -- chunk 8 then prices a flat trade.
    """
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(23, 2029, 2036, 2029, 2035),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    entry, exit_event = result.entry, result.exit_event
    assert entry is not None and exit_event is not None
    assert exit_event.kind == sig.EXIT_SQUARE_OFF and exit_event.stamp == entry.stamp
    assert "the entry candle's own close" in exit_event.detail


# ==============================================================================================
# The reference: E10's fallback, and the no-reference day
# ==============================================================================================


def test_e10_falls_back_to_the_last_one_minute_close_at_or_before_11_14() -> None:
    """CONTEXT 7-E10: "Missing 11:00-11:15 reference candle on an otherwise valid day ->
    reference = last available 1-min close <= 11:14."

    HAND-COMPUTED at POC 2030: no candle trades 11:00-11:15. Three 1-minute closes are on offer
    -- 10:58 at 2040, 11:14 at 2025 and 11:20 at 2010. The LAST one at or before 11:14 is the
    11:14 close 2025, which is below the POC, so the day is ARMED (the 11:20 close is after the
    cutoff and must not be read; had it been, the reference would still be below the POC, so the
    assertion is on the VALUE, not on the state).
    """
    bars = (
        bar(9, 2029, 2036, 2028, 2035),
        bar(10, 2035, 2038, 2033, 2036),
    )
    minutes = (
        Minute(time(10, 58), 2040),
        Minute(time(11, 14), 2025),
        Minute(time(11, 20), 2010),
    )
    result = sig.evaluate_day(
        bars, day=DAY, side=sig.LONG, poc_paise=POC(2030), minute_bars=minutes
    )

    assert result.reference_source == sig.REFERENCE_FROM_MINUTES
    assert result.reference_paise == R(2025)
    assert result.initial_state == sig.STATE_ARMED
    assert result.entry is not None and closes_at(result, 9)


def test_the_reference_candle_wins_whenever_it_exists() -> None:
    """The fallback is a FALLBACK: with the 11:00-11:15 candle present, the 1-minute bars are
    never consulted, even when they would give a different answer (here 2040 vs 2025)."""
    bars = (
        bar(8, 2028, 2029, 2024, 2025),
        bar(9, 2029, 2036, 2028, 2035),
    )
    minutes = (Minute(time(11, 14), 2040),)
    result = sig.evaluate_day(
        bars, day=DAY, side=sig.LONG, poc_paise=POC(2030), minute_bars=minutes
    )

    assert result.reference_source == sig.REFERENCE_FROM_CANDLE
    assert result.reference_paise == R(2025)


def test_no_reference_at_all_means_no_trade() -> None:
    """CONTEXT 7-E10's second half: "none -> no trade". Nothing traded before 11:15 at all, so
    there is no reference and the day is not evaluated -- and nothing is consumed.
    """
    bars = (bar(9, 2029, 2036, 2028, 2035), bar(10, 2035, 2040, 2034, 2039))
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=POC(2030))

    assert result.reference_paise is None
    assert result.reference_source == sig.REFERENCE_NONE
    assert result.initial_state == sig.STATE_NO_REFERENCE
    assert result.outcome == sig.OUTCOME_NO_REFERENCE
    assert not result.consumed and result.entry is None
    assert result.log is not None


def test_a_one_minute_close_after_the_cutoff_is_not_a_reference() -> None:
    """The cutoff is inclusive at 11:14 and nothing later counts: with only an 11:15 one-minute
    close on offer (the first minute of the NEXT candle), the day has no reference."""
    bars = (bar(9, 2029, 2036, 2028, 2035),)
    minutes = (Minute(time(11, 15), 2025),)
    result = sig.evaluate_day(
        bars, day=DAY, side=sig.LONG, poc_paise=POC(2030), minute_bars=minutes
    )

    assert result.reference_paise is None and result.outcome == sig.OUTCOME_NO_REFERENCE


def test_an_empty_day_is_recorded_as_such() -> None:
    """No 15-minute candles at all: its own outcome, so chunk 9 counts it apart from a day that
    merely had no reference."""
    result = sig.evaluate_day((), day=DAY, side=sig.LONG, poc_paise=POC(2030))
    assert result.outcome == sig.OUTCOME_NO_BARS and not result.consumed


# ==============================================================================================
# The POC is exact: half a paisa, never rounded (CONTEXT 3.3 / 7-E11)
# ==============================================================================================


def test_a_half_paise_poc_is_compared_at_full_precision_and_never_rounded() -> None:
    """CONTEXT 3.3: "POC value is a row MIDPOINT -- it may legally sit off the tick grid
    (half-tick values); all comparisons against it use full precision, never rounded prices."

    The POC here is 203050.5 paise (Rs 2030.505), exactly half a paisa above Rs 2030.50.
    HAND-COMPUTED: a close of 203050 paise (Rs 2030.50) is BELOW it -- it would be equal to a
    rounded-down POC and above a rounded-up one -- and a close of 203051 (Rs 2030.51) is above
    it. The reference 203050 therefore ARMS the day and the 203051 close TRIGGERS it, with the
    stop at the entry candle's low 203049 and risk 2 paise.
    """
    poc = Fraction(406101, 2)  # 203050.5 paise
    assert poc.denominator == 2 and poc != int(poc)
    bars = (
        Bar(
            stamp=sig.bar_open_stamp(DAY, 8),
            open_paise=203048, high_paise=203050, low_paise=203047, close_paise=203050,
            volume=1_000,
        ),
        Bar(
            stamp=sig.bar_open_stamp(DAY, 9),
            open_paise=203050, high_paise=203052, low_paise=203049, close_paise=203051,
            volume=1_000,
        ),
    )
    result = sig.evaluate_day(bars, day=DAY, side=sig.LONG, poc_paise=poc)

    assert result.initial_state == sig.STATE_ARMED
    entry = result.entry
    assert entry is not None
    assert (entry.entry_paise, entry.stop_paise, entry.risk_paise) == (203051, 203049, 2)
    assert entry.target_paise == 203051 + 3 * 2
    assert not entry.gap_entry  # low 203049 < POC 203050.5, so the candle DID trade below it


def test_no_close_can_ever_sit_exactly_on_a_half_paise_poc() -> None:
    """A consequence worth pinning: prices are whole paise and a half-paise POC is not, so on
    such a day the ==POC branches (which neither arm, nor trigger, nor set a side) are simply
    unreachable. Every close is strictly one side or the other."""
    poc = Fraction(406101, 2)
    for close in range(203048, 203054):
        assert sig.poc_side(close, poc) in (sig.ABOVE_POC, sig.BELOW_POC)


def test_a_float_poc_is_refused_outright() -> None:
    """CONTEXT 7-E11 bans float equality on prices. A float POC would make every comparison in
    the engine a float comparison, so it is refused at the door rather than silently accepted."""
    with pytest.raises(sig.SignalError, match="Fraction"):
        sig.evaluate_day(F1_BARS, day=DAY, side=sig.LONG, poc_paise=2030.0)  # type: ignore[arg-type]


# ==============================================================================================
# Input validation -- a bad stock-day is a caller bug, never a silent verdict
# ==============================================================================================


def test_a_bar_from_another_day_is_refused() -> None:
    other = bar(9, 2029, 2036, 2028, 2035, day=date(2026, 7, 21))
    with pytest.raises(sig.SignalError, match="ONE trade date"):
        sig.evaluate_day((other,), day=DAY, side=sig.LONG, poc_paise=POC(2030))


def test_an_off_grid_15_minute_stamp_is_refused() -> None:
    """CONTEXT 7-E12: valid 15-minute open-stamps are 09:15, 09:30, ... 15:15. The aggregator
    never produces anything else, so one here means the caller assembled the bars by hand."""
    stray = Bar(
        stamp=datetime.combine(DAY, time(11, 20)),
        open_paise=R(2030), high_paise=R(2036), low_paise=R(2028), close_paise=R(2035),
        volume=1_000,
    )
    with pytest.raises(sig.SignalError, match="off the 09:15 session grid"):
        sig.evaluate_day((stray,), day=DAY, side=sig.LONG, poc_paise=POC(2030))


def test_duplicate_15_minute_stamps_are_refused() -> None:
    twice = (bar(9, 2029, 2036, 2028, 2035), bar(9, 2029, 2036, 2028, 2031))
    with pytest.raises(sig.SignalError, match="duplicate"):
        sig.evaluate_day(twice, day=DAY, side=sig.LONG, poc_paise=POC(2030))


def test_an_unknown_side_is_refused() -> None:
    with pytest.raises(sig.SignalError, match="side must be"):
        sig.evaluate_day(F1_BARS, day=DAY, side="flat", poc_paise=POC(2030))


def test_bars_need_not_arrive_sorted() -> None:
    """The store and the aggregator both hand over sorted bars, but the engine sorts anyway --
    an out-of-order input must not silently change which candle is 'previous'."""
    shuffled = tuple(reversed(F1_BARS))
    assert sig.evaluate_day(
        shuffled, day=DAY, side=sig.LONG, poc_paise=POC(2032)
    ) == sig.evaluate_day(F1_BARS, day=DAY, side=sig.LONG, poc_paise=POC(2032))


# ==============================================================================================
# Purity (CONTEXT 6)
# ==============================================================================================


def test_the_signal_engine_is_pure() -> None:
    """CONTEXT 6: the engines are pure functions over candles. No I/O, no network, no clock
    read, and -- CONTEXT 7-E11 -- no float anywhere in the arithmetic."""
    import ast
    import inspect

    source = inspect.getsource(sig)
    tree = ast.parse(source)

    imported = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported <= {"__future__", "dataclasses", "datetime", "fractions", "typing", "bias", "calendar", ""}, imported

    # The import whitelist above already makes network access impossible (no requests, no
    # urllib, no socket). These are the calls that would smuggle in a clock read or a file
    # handle through a module that IS allowed.
    banned = {"now", "today", "utcnow", "fromtimestamp", "read_text", "write_text", "open"}
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    } | {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not (called & banned), sorted(called & banned)

    floats = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, float)
    ]
    assert not floats, "no float literal may appear in the signal engine (CONTEXT 7-E11)"
