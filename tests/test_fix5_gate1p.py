"""GATE 1P -- the per-day PRICE gate (QUESTIONS.md Q-14, the architect's ruling of 2026-07-28).

The defect the ruling closes (REVIEW_5B finding Q1): CONTEXT 4.5's gate 1 proves a day's VOLUME and
the Q-11 oracle proves an ERA's price over its probe days, so 1,963 stored symbol-days sat between
the two at 0.1x-5x the traded price and passed the whole battery. Gate 1P is the per-day price
proof, and these tests are the shapes the review measured, reduced to their arithmetic:

* the TATASTEEL 2020-07-28 shape (stored at 0.1x the traded price) FAILS;
* the SRF shape (stored at 5x) FAILS;
* a legitimate AUCTION-PRINT day -- daily high above every 1-minute high -- PASSES, because the
  gate is a CONTAINMENT and not an equality;
* a day with no raw daily row FAILS (the ruling's own words; it closes REVIEW_5B Q4's 178 days);
* the tolerance boundary holds exactly, on BOTH sides.

All PURE and offline: the gate takes four integers.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from acumen import quality_gates as qg
from acumen import vendor_adjustment as va


# --- the two review shapes --------------------------------------------------------------


def test_the_tatasteel_2020_07_28_shape_at_a_tenth_of_the_price_fails() -> None:
    # REVIEW_5B Q1: stored 1-minute high Rs 36.00 against a bhavcopy high of Rs 360.00, on a day
    # whose gate-1 volume gap was +0.071% -- i.e. the volume gate passed it.
    result = qg.price_containment_gate(
        minute_high_paise=3600, minute_low_paise=3410,
        raw_high_paise=36000, raw_low_paise=34100,
    )
    assert not result.passed
    assert result.cause == qg.GATE1P_BELOW  # a 0.1x day drops out through the LOW side
    assert "fold LOW" in result.reason
    assert result.low_excess_paise is not None and result.low_excess_paise > 30000


def test_the_srf_shape_at_five_times_the_price_fails() -> None:
    # REVIEW_5B Q1: SRF 2016-10-03 stored high Rs 9,625.00 vs bhavcopy Rs 1,925.00, gap -0.002%.
    result = qg.price_containment_gate(
        minute_high_paise=962500, minute_low_paise=940000,
        raw_high_paise=192500, raw_low_paise=188000,
    )
    assert not result.passed
    assert result.cause == qg.GATE1P_ABOVE  # a 5x day escapes through the HIGH side
    assert "fold HIGH" in result.reason


@pytest.mark.parametrize(
    "factor,expected_cause",
    [
        ("0.667", qg.GATE1P_BELOW),   # IOC, 1,042 days
        ("1.417", qg.GATE1P_ABOVE),   # NMDC, 134 days
        ("0.750", qg.GATE1P_BELOW),   # RECLTD, 65 days
        ("2.000", qg.GATE1P_ABOVE),   # APLAPOLLO, 3 days
    ],
)
def test_every_off_scale_factor_the_review_measured_is_caught(factor: str, expected_cause: str) -> None:
    """A wrong scale moves BOTH ends the same way, so one of them always escapes the interval."""
    raw_high, raw_low = 17415, 16800
    k = Decimal(factor)
    result = qg.price_containment_gate(
        minute_high_paise=int(Decimal(raw_high) * k),
        minute_low_paise=int(Decimal(raw_low) * k),
        raw_high_paise=raw_high, raw_low_paise=raw_low,
    )
    assert not result.passed
    assert result.cause == expected_cause


# --- containment, not equality ----------------------------------------------------------


def test_a_legitimate_auction_print_day_passes() -> None:
    """The daily high is ABOVE every 1-minute high and the daily low BELOW every 1-minute low.

    That is the ordinary shape of a day carrying a pre-open auction or block print: the exchange
    counts it in the daily extremes and the continuous 1-minute series never held it. The gate must
    pass such a day -- which is exactly why it is a CONTAINMENT and not a two-sided equality (the
    auction-relief ruling's condition (b) is the equality, and it is a different question).
    """
    result = qg.price_containment_gate(
        minute_high_paise=153000, minute_low_paise=152800,
        raw_high_paise=153725, raw_low_paise=152580,
    )
    assert result.passed
    assert result.high_excess_paise == 0 and result.low_excess_paise == 0


def test_a_fold_equal_to_the_daily_extremes_passes() -> None:
    result = qg.price_containment_gate(153725, 152580, 153725, 152580)
    assert result.passed


# --- the no-oracle-row case (the ruling closes REVIEW_5B Q4 with it) --------------------


@pytest.mark.parametrize("high,low", [(None, 152580), (153725, None), (None, None)])
def test_a_day_with_no_raw_daily_row_fails_and_says_why(high, low) -> None:
    result = qg.price_containment_gate(153000, 152800, high, low)
    assert not result.passed
    assert result.cause == qg.GATE1P_NO_ORACLE
    assert "no raw daily row" in result.reason
    assert result.high_excess_paise is None and result.low_excess_paise is None


def test_a_non_positive_raw_row_cannot_price_prove_a_day() -> None:
    assert not qg.price_containment_gate(100, 90, 0, 0).passed
    assert qg.price_containment_gate(100, 90, 0, 0).cause == qg.GATE1P_NO_ORACLE


# --- the tolerance, both sides ----------------------------------------------------------


def test_the_relative_tolerance_boundary_holds_on_the_high_side() -> None:
    # raw high 100000 paise (Rs 1,000) -> tolerance max(2, 0.1% x 100000) = 100 paise.
    assert qg.price_containment_limit(100000) == Decimal(100)
    assert qg.price_containment_gate(100100, 99000, 100000, 99000).passed        # exactly at it
    assert not qg.price_containment_gate(100101, 99000, 100000, 99000).passed    # one paise past
    assert qg.price_containment_gate(100101, 99000, 100000, 99000).cause == qg.GATE1P_ABOVE


def test_the_relative_tolerance_boundary_holds_on_the_low_side() -> None:
    assert qg.price_containment_limit(99000) == Decimal(99)
    assert qg.price_containment_gate(100000, 98901, 100000, 99000).passed
    assert not qg.price_containment_gate(100000, 98900, 100000, 99000).passed
    assert qg.price_containment_gate(100000, 98900, 100000, 99000).cause == qg.GATE1P_BELOW


def test_the_absolute_two_paise_floor_governs_a_cheap_stock() -> None:
    # raw 1000 paise (Rs 10) -> 0.1% is 1 paise, so the 2-paise floor is what applies.
    assert qg.price_containment_limit(1000) == Decimal(2)
    assert qg.price_containment_gate(1002, 950, 1000, 950).passed
    assert not qg.price_containment_gate(1003, 950, 1000, 950).passed


# --- the constants are single-sourced (finding C13's class: one predicate, one definition) ---


def test_gate1p_and_the_era_oracle_share_one_tolerance_definition() -> None:
    assert va.DEFAULT_PRICE_CONTAINMENT_PAISE is qg.PRICE_CONTAINMENT_MIN_PAISE
    assert va._PRICE_CONTAINMENT_REL is qg.PRICE_CONTAINMENT_REL  # noqa: SLF001
    assert qg.PRICE_CONTAINMENT_MIN_PAISE == 2
    assert qg.PRICE_CONTAINMENT_REL == Decimal("0.001")


def test_the_gate1_volume_band_is_untouched_by_the_q14_ruling() -> None:
    """Gate 1P is an ADDITION to the battery, never a relaxation of the band beside it."""
    assert qg.VOLUME_GAP_MIN_PCT == Decimal("-0.1")
    assert qg.VOLUME_GAP_MAX_PCT == Decimal("5.0")


def test_the_gate1p_exclusion_reason_is_its_own() -> None:
    assert "gate-1P" in qg.REASON_GATE1P
    assert qg.REASON_GATE1P != "gate-1"
