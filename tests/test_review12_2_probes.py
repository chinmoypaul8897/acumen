"""REVIEW_12_2 reviewer probes -- the chunk-12 ROUND-4 EXECUTION re-review.

Probes the builder did not write, kept in the repo per `personas/quant_reviewer.md` step 4 and
`personas/code_reviewer.md` step 4. Two CLOSE a coverage gap the execution session recorded
honestly and left open (B306); one asserts, as a PROPERTY over a swept grid, the constraint the
trader's own Round-4 words put on the gap stop; and one PINS a finding, so the fix the architect
may order turns it red rather than passing silently (the repo's established discipline --
REVIEW_9A/9B/12 probes that pinned a defect and were later FLIPPED).

Offline: the artefact probe reads two committed files in the repository and no store.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import json
import re
from datetime import date
from fractions import Fraction
from pathlib import Path

import pytest

from acumen import signals as sig
from acumen import simulate as sim
from acumen.aggregate import Bar

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / "docs/validation/trader_pack.md"
COMPANION = REPO / "docs/validation/trader_pack.json"
CONTEXT = REPO / "CONTEXT.md"

DAY = date(2026, 7, 20)
RISK_PAISE = 100_000      # CONTEXT 3.5, Round-3 Q29
COST_PAISE = 10_000       # CONTEXT 3.5, R1-Q23


def R(rupees: float) -> int:
    return int(round(rupees * 100))


def POC(rupees: float) -> Fraction:
    return Fraction(R(rupees))


def bar(ordinal: int, o: float, h: float, l: float, c: float) -> Bar:
    return Bar(stamp=sig.bar_open_stamp(DAY, ordinal), open_paise=R(o), high_paise=R(h),
               low_paise=R(l), close_paise=R(c), volume=1_000)


# The SAME candles chunk 7 built and chunk 12 re-designated -- copied here so this file asserts
# against CONTEXT 3.4/3.5 directly and does not inherit another module's fixtures.
F1_BARS = (
    bar(8, 2028, 2029, 2024, 2025),
    bar(9, 2033, 2038, 2032, 2037),
    bar(10, 2037, 2041, 2035, 2040),
    bar(11, 2040, 2055, 2039, 2053),
)
F2_BARS = (
    bar(8, 2030, 2036, 2029, 2034),
    bar(9, 2034, 2039, 2033, 2038),
    bar(10, 2038, 2038, 2026, 2027),
    bar(11, 2033, 2038, 2032, 2037),
    bar(12, 2037, 2043, 2036, 2042),
    bar(13, 2042, 2056, 2041, 2054),
)


def priced(bars, *, side: str, poc: Fraction) -> sim.TradeRecord:
    signal = sig.evaluate_day(bars, day=DAY, side=side, poc_paise=poc)
    return sim.simulate_day(signal, bars, symbol="TCS", risk_per_trade_paise=RISK_PAISE,
                            cost_paise=COST_PAISE)


# --- 1 & 2. CLOSE the gap B306 recorded: CONTEXT 8's F1/F2 had no PnL-level golden ---------------


def test_f1_the_round_4_golden_has_a_hand_computed_PnL_of_its_own() -> None:
    """**B306's open gap, closed.** CONTEXT v1.8 section 8 re-parametrized F1 to the GAP day at
    POC 2030, and the execution session -- correctly, under a ruling that forbade re-measuring
    anything -- left that parametrization asserted only at SIGNAL level. So the fixture the
    trader's own Round-4 answer now defines had no money attached to it anywhere.

    A REVIEW session is the right place to compute one: the persona's own step 4 is to write the
    tests the builder did not, and nothing here re-measures a value the builder published.
    HAND-COMPUTED from CONTEXT 3.5 BEFORE running the code:

    * entry 2037, gap stop = the previous 15-minute candle's close **2025**, per-share risk
      **12.00 rupees = 1,200 paise**;
    * ``qty = floor(100,000 / 1,200)`` = **83**. Check the floor is tight: 83 x 1,200 = 99,600
      <= 100,000 and 84 x 1,200 = 100,800 > 100,000;
    * neither 2025 nor the target 2073 is touched after the entry candle (E7), and no candle
      trades after 12:00, so the day SQUARES OFF at the last candle's close **2053**;
    * gross = 83 x (205,300 - 203,700) = 83 x 1,600 = **132,800 paise = +Rs 1,328.00**;
    * net = 132,800 - 10,000 = **122,800 paise = +Rs 1,228.00**.

    Note this is NOT a 3R payout: a square-off pays what the day gave, not a multiple of R.
    """
    record = priced(F1_BARS, side=sig.LONG, poc=POC(2030))

    assert record.gap_entry
    assert (record.entry_paise, record.stop_paise, record.target_paise) == (
        R(2037), R(2025), R(2073),
    )
    assert record.per_share_risk_paise == R(12) and record.qty == 83
    assert record.qty * record.per_share_risk_paise <= RISK_PAISE
    assert (record.qty + 1) * record.per_share_risk_paise > RISK_PAISE
    assert record.exit_kind == sig.EXIT_SQUARE_OFF and record.exit_paise == R(2053)
    assert record.gross_pnl_paise == R(1_328)
    assert record.net_pnl_paise == R(1_228)


def test_f2_the_round_4_golden_has_a_hand_computed_PnL_of_its_own() -> None:
    """**B306's open gap, closed on the Entry-2 path.** HAND-COMPUTED from CONTEXT 3.5:

    * WAIT-BELOW at 2034 -> the 2038 close consumes nothing -> 2027 arms -> 2037 triggers;
    * entry 2037, gap stop = the previous candle's close **2027**, per-share risk
      **10.00 rupees = 1,000 paise**;
    * ``qty = floor(100,000 / 1,000)`` = **100**, and the floor is exact here (100 x 1,000 =
      100,000, so nothing is left over at all);
    * neither 2027 nor the target 2067 is touched after the entry candle, so the day SQUARES
      OFF at the last candle's close **2054**;
    * gross = 100 x (205,400 - 203,700) = 100 x 1,700 = **170,000 paise = +Rs 1,700.00**;
    * net = 170,000 - 10,000 = **160,000 paise = +Rs 1,600.00**.
    """
    record = priced(F2_BARS, side=sig.LONG, poc=POC(2030))

    assert record.gap_entry
    assert (record.entry_paise, record.stop_paise, record.target_paise) == (
        R(2037), R(2027), R(2067),
    )
    assert record.per_share_risk_paise == R(10) and record.qty == 100
    assert record.qty * record.per_share_risk_paise <= RISK_PAISE
    assert (record.qty + 1) * record.per_share_risk_paise > RISK_PAISE
    assert record.exit_kind == sig.EXIT_SQUARE_OFF and record.exit_paise == R(2054)
    assert record.gross_pnl_paise == R(1_700)
    assert record.net_pnl_paise == R(1_600)


# --- 3. The trader's OWN Round-4 constraint, as a swept PROPERTY ----------------------------------


@pytest.mark.parametrize("poc_rupees", [2020 + n * 0.25 for n in range(0, 49)])
def test_a_gap_stop_is_never_beyond_the_poc_on_either_side(poc_rupees: float) -> None:
    """**The constraint the trader wrote in his own Round-4 diagram, swept.**

    His recorded words (QUESTIONS.md, ROUND-4 RECEIPTS) put the stop *"at or below the origin/
    bottom of the Gap Up (i.e., at or below 2030)"* -- a ZONE, not a value. CONTEXT 3.4 picks
    one member of that zone (the previous 15-minute candle's close, from his earlier R2-Q33),
    and the two agree only because of a structural fact worth asserting rather than trusting:

    on a bullish day a close STRICTLY above the POC is itself the trigger, so the candle before
    the entry candle can only have closed at or BELOW the POC -- and the mirror holds short.

    Swept over 49 POCs a quarter-rupee apart, on both sides, so the property is asserted where
    the fixtures do not look. Only the days that actually produce a GAP entry are examined; the
    rest are skipped, and at least one gap is required so the sweep cannot pass vacuously.
    """
    seen_gap = 0
    for bars, side in ((F1_BARS, sig.LONG), (F2_BARS, sig.LONG),
                       (F1_BARS, sig.SHORT), (F2_BARS, sig.SHORT)):
        result = sig.evaluate_day(bars, day=DAY, side=side, poc_paise=POC(poc_rupees))
        entry = result.entry
        if entry is None or not entry.gap_entry:
            continue
        seen_gap += 1
        assert entry.stop_source == sig.STOP_FROM_PREVIOUS_CLOSE
        poc = POC(poc_rupees)
        if side == sig.LONG:
            assert entry.stop_paise <= poc, "a long gap stop above the POC is unreachable"
        else:
            assert entry.stop_paise >= poc, "a short gap stop below the POC is unreachable"
        assert entry.risk_paise > 0
    if abs(poc_rupees - 2030) < 1e-9:
        assert seen_gap >= 2, "the sweep must reach the gap branch at the fixtures' own POC"


# --- 4. PINS a finding: the bias-table reconciliation the page invites the trader to check --------


def test_the_bias_tables_stated_arithmetic_does_NOT_close() -> None:
    """REVIEW_12_2 finding Q1, PINNED.

    Page 5's reconciliation paragraph says, of the bias-rule table: *"Those rows add up to
    493,680, and here is the rest of the arithmetic so you can check it"*, then names three of
    its own rows as *not judged*, and then says *"And 87,192 MORE had a bias but were refused
    afterwards on a data check"*.

    Followed literally -- which is exactly what the reader is invited to do -- that is

        493,680  -  74,081 (the three 'not judged' rows)  -  87,192  =  332,407

    and the page states the answer is 406,488. The error is 74,081, precisely the not-judged
    population, subtracted twice: the 87,192 is `ruled - usable`, which CONTAINS the three
    not-judged rows rather than standing beside them, and 74,081 of those 87,192 days did not
    have a bias at all. The figure that genuinely *"had a bias but was refused afterwards"* is
    **13,111**.

    This probe reproduces the arithmetic from the COMMITTED companion, so it is the trader's own
    document being checked and not a re-run. When the sentence is corrected it turns red.
    """
    figures = json.loads(COMPANION.read_text(encoding="utf-8"))["figures"]
    counts, limits = figures["counts"], figures["limits"]
    ruled = counts["bias_rules_total"]
    usable = limits["usable"]

    # the three rows the page itself calls "not judged", read off the page's OWN table rather
    # than mapped through rule keys (two different rules carry the same count of 30, so a
    # count-keyed lookup silently picks the wrong row)
    rows = _table_rows()
    assert len(rows) == len(counts["bias_rules"]) == 10, "every rule has a printed row"
    assert sum(count for _, count in rows) == ruled
    not_judged_rows = [(words, count) for words, count in rows if "not judged" in words]
    assert len(not_judged_rows) == 3, "the page's own sentence says three rows say 'not judged'"
    not_judged = sum(count for _, count in not_judged_rows)
    assert not_judged == 74_081, "the three not-judged rows, read off the committed table"
    assert counts["bias_rules_ruled_then_refused"] == ruled - usable == 87_192

    # the page's own three-step arithmetic, followed literally
    assert ruled - not_judged - (ruled - usable) != usable, (
        "if this ever passes, the reconciliation has been fixed and this probe must flip"
    )
    assert usable - (ruled - not_judged - (ruled - usable)) == not_judged, (
        "and the error is exactly the not-judged population, counted twice"
    )

    page = PACK.read_text(encoding="utf-8")
    assert f"{ruled - usable:,} more had a bias but were refused afterwards" in page, (
        "the defective sentence is the one shipped to the trader"
    )
    assert f"{ruled - usable - not_judged:,}" not in page, (
        "and the figure that is actually true of 'had a bias, then refused' is on no page"
    )


def _table_rows() -> list[tuple[str, int]]:
    """The bias-rule table as the trader reads it: (the page's own words, the printed count)."""
    page = PACK.read_text(encoding="utf-8")
    section = page.split("What the machine found on each stock-day it looked at", 1)[1]
    section = section.split("**Those rows add up to", 1)[0]
    return [(words, int(printed.replace(",", "")))
            for words, printed in re.findall(r"^\|\s*(.+?)\s*\|\s*([\d,]+)\s*\|\s*$",
                                             section, re.M)]
