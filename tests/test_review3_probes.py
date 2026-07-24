"""REVIEW_3 reviewer probes -- chunk 3 (corporate-action engine).

Written by the fresh REVIEW session (personas/quant_reviewer.md + code_reviewer.md, plan.md
review type QC). These are the tests the build's suite left as GAPS, kept per the persona
process step 4 ("write tests the builder didn't think of; keep the good ones"). No file under
review was modified.

The one that matters: `adjust_pair`'s "round the chain ONCE, at the end" (decision B46) had a
unit test whose chain values (0.5, 0.2) produce EXACT integer intermediates, so a regression
to round-PER-event would have passed it unnoticed -- the surviving mutant in this review's
mutation run. The first test below closes that gap with a chain whose intermediates are
inexact, where round-once and round-per-event genuinely disagree.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from acumen import corp_actions as ca
from acumen.corp_actions import Factor, adjust_pair, factors_between


def _f(k: str, ex: date = date(2020, 1, 2), kind: str = "bonus") -> Factor:
    return Factor(symbol="Z", ex_date=ex, kind=kind, k=Decimal(k), basis="test")


def test_adjust_pair_rounds_the_chain_once_on_an_inexact_chain() -> None:
    """B46 tripwire the build's own test misses.

    A KOTHARIPRO-style bonus 1:2 (k = 2/3) chained with a face-value split 10 -> 4 (k = 0.4):
    at price 10003 paise the exact product is 2667.4666..., which rounds to 2667; rounding
    after the FIRST factor (10003 * 2/3 = 6668.67 -> 6669) and again after the second
    (6669 * 0.4 = 2667.6 -> 2668) gives 2668. `adjust_pair` must produce the round-ONCE
    answer, 2667. The build's chain (0.5, 0.2) can never show this because both steps are
    exact.
    """
    bonus = _f("0.6666666666666666666666666667", date(2020, 1, 2))
    split = Factor(symbol="Z", ex_date=date(2020, 1, 3), kind="split",
                   k=Decimal(2) / Decimal(5), basis="test")
    chain = factors_between([bonus, split], date(2020, 1, 1), date(2020, 1, 6))
    assert len(chain) == 2

    # round-once, computed here from the exact product
    once = int((Decimal(10003) * bonus.k * split.k).quantize(Decimal(1),
                                                              rounding=ROUND_HALF_EVEN))
    per_event = int(
        (Decimal(int((Decimal(10003) * bonus.k).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)))
         * split.k).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
    )
    assert once == 2667 and per_event == 2668, "the case must actually distinguish the two"
    assert adjust_pair(10003, chain) == once == 2667


def test_adjust_pair_round_once_matches_a_hand_scan_of_realistic_prices() -> None:
    """Over a range of realistic paise, `adjust_pair` equals round-ONCE on every price, and
    the two rules genuinely diverge somewhere in that range (so this is not a vacuous test)."""
    k1, k2 = Decimal(2) / Decimal(3), Decimal(2) / Decimal(5)
    f1 = _f(str(k1), date(2020, 1, 2))
    f2 = Factor(symbol="Z", ex_date=date(2020, 1, 3), kind="split", k=k2, basis="test")
    chain = factors_between([f1, f2], date(2020, 1, 1), date(2020, 1, 6))
    divergences = 0
    for price in range(10_000, 12_000):
        once = int((Decimal(price) * k1 * k2).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
        per = int((Decimal(int((Decimal(price) * k1).quantize(Decimal(1),
                   rounding=ROUND_HALF_EVEN))) * k2).quantize(Decimal(1),
                   rounding=ROUND_HALF_EVEN))
        assert adjust_pair(price, chain) == once
        divergences += once != per
    assert divergences > 0, "the range must contain a case where per-event rounding differs"


def test_adjust_pair_is_half_even_not_half_up_on_a_tie() -> None:
    """B46's second half. 1 paise * 0.5 = 0.5 is an exact tie: half-EVEN rounds to 0,
    half-up would give 1. The build tests 5 and 7; this pins the 0-direction tie that only
    half-even gets right, and the cumulative unbiasedness the decision claims."""
    half = _f("0.5")
    assert adjust_pair(1, [half]) == 0     # 0.5 -> 0 (even), half-up would be 1
    assert adjust_pair(3, [half]) == 2     # 1.5 -> 2 (even)
    assert adjust_pair(25, [half]) == 12   # 12.5 -> 12 (even), half-up would be 13
    # cumulative bias over odd paise is zero for half-even (it would be +0.5/tie for half-up)
    exact_minus_rounded = sum(
        adjust_pair(p, [half]) - Decimal(p) * Decimal("0.5") for p in range(1, 1000, 2)
    )
    assert exact_minus_rounded == 0


def test_a_debt_series_row_can_never_attach_a_factor_to_a_real_equity() -> None:
    """Directed check 8, as a kept regression. TATASTEEL is a real F&O equity; a corporate
    action published under a DEBENTURE series (N2) for the same symbol must be dropped before
    parsing, so it can never scale the equity's price history. Only the EQ event survives."""
    rows = [
        ca.CorporateAction(symbol="TATASTEEL", ex_date=date(2023, 7, 10),
                           subject="Bonus 1:1", source=ca.SOURCE_NSE, series="N2"),
        ca.CorporateAction(symbol="TATASTEEL", ex_date=date(2023, 7, 12),
                           subject="Face Value Split From Rs 10 To Rs 2",
                           source=ca.SOURCE_NSE, series="EQ"),
    ]
    report = ca.parse_actions(rows)  # instrument_series_only=True by default
    assert [e.action.series for e in report.events] == ["EQ"]
    assert [a.series for a in report.ignored_series] == ["N2"]
    table = ca.build_factor_table(report.events)
    assert [(f.kind, str(f.k)) for f in table.factors] == [("split", "0.2")]
    assert all(f.kind != ca.KIND_BONUS for f in table.factors)


def test_the_indian_bonus_convention_holds_for_a_range_of_ratios() -> None:
    """CONTEXT 4.2: bonus A:B -> k = B/(A+B), NEVER the US B/A. Pin several ratios so a flip
    to any US-style form is caught here, not only at the KOTHARIPRO/RELIANCE goldens."""
    cases = {
        (1, 1): Decimal(1) / Decimal(2),
        (1, 2): Decimal(2) / Decimal(3),
        (2, 1): Decimal(1) / Decimal(3),
        (3, 5): Decimal(5) / Decimal(8),
        (1, 4): Decimal(4) / Decimal(5),
    }
    for (new, held), want in cases.items():
        event = ca.ParsedEvent(
            action=ca.CorporateAction("X", date(2020, 1, 1), f"Bonus {new}:{held}",
                                      ca.SOURCE_NSE, series="EQ"),
            kind=ca.KIND_BONUS, ratio_new=new, ratio_held=held)
        assert ca.factor_for(event).k == want, f"bonus {new}:{held}"
        # the US convention B/A would give a different number for every non-1:1 ratio
        if new != held:
            assert ca.factor_for(event).k != Decimal(held) / Decimal(new)


def test_pairwise_adjustment_is_the_law_even_where_a_full_series_would_round_differently() -> None:
    """CONTEXT 3.2 DEFINES the bias comparison pairwise (P into C's scale). It also remarks
    this is "equivalent to comparing on a fully adjusted series" -- true in exact arithmetic,
    but once BOTH candles are rounded into a common later scale the two can differ by a
    paise-tie. This test documents that the engine implements the pairwise definition (the
    law), so a downstream chunk must never substitute a fully-adjusted series and expect
    byte-identical comparisons. Values are the first knife-edge case this review found."""
    k_between = ca.rights_factor(cum_close_paise=10710, issue_price_paise=6500,
                                 ratio_new=17, ratio_held=74)  # 0.92656...
    k_after = Decimal(1) - Decimal(2750) / Decimal(91300)      # a later special dividend
    between = Factor(symbol="Z", ex_date=date(2020, 1, 3), kind="rights", k=k_between, basis="")
    after = Factor(symbol="Z", ex_date=date(2020, 2, 1), kind="dividend", k=k_after, basis="")

    p, c = 3544735, 3284430
    p_pair = adjust_pair(p, [between])           # pairwise: P into C's scale, C untouched
    pairwise_c_le_p = c <= p_pair
    p_full = adjust_pair(p, [between, after])     # both into the Feb scale
    c_full = adjust_pair(c, [after])
    full_c_le_p = c_full <= p_full

    # the two rules disagree here -- exactly the case a downstream author must not assume away
    assert pairwise_c_le_p is False and full_c_le_p is True
    # what the engine computes is the pairwise (spec-defined) comparison
    assert (c <= adjust_pair(p, factors_between([between, after], date(2020, 1, 2),
                                                date(2020, 1, 3)))) is pairwise_c_le_p
