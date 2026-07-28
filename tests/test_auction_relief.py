"""Gate-1 AUCTION RELIEF -- the deferred +5.0% ceiling, answered (QUESTIONS.md Q-12 addendum 2).

All OFFLINE and pure. The architect's ruling relieves a gate-1 failure ABOVE the ceiling **IFF
ALL** of four conditions hold, so the tests that matter are the ones that flip exactly ONE
condition at a time and prove the relief is refused -- that is what "each condition is
individually necessary" means, and it is the only way to show that no single clause is decorative.

The other half of the ruling is what did NOT change: the ceiling stays, the floor is untouched,
``volume_gate`` is untouched, and a below-floor failure is never relieved. Those are pinned here
too, by reading the constants themselves rather than by re-deriving them.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from acumen import quality_gates as qg


#: A thin day: the exchange counted 1,000,000 shares, the continuous 1-minute series 900,000.
#: gap% = 10.0 -- above the +5.0% ceiling, inside the 20% sanity cap.
_DAILY_VOLUME = 1_000_000
_MINUTE_VOLUME = 900_000

_RAW_OPEN, _RAW_HIGH, _RAW_LOW = 45_000, 46_250, 44_100


def _relief(**overrides):
    """The canonical relievable day, with named fields overridable one at a time."""
    fields = {
        "minute_open_paise": _RAW_OPEN,
        "minute_high_paise": _RAW_HIGH,
        "minute_low_paise": _RAW_LOW,
        "raw_open_paise": _RAW_OPEN,
        "raw_high_paise": _RAW_HIGH,
        "raw_low_paise": _RAW_LOW,
    }
    daily = overrides.pop("daily_volume", _DAILY_VOLUME)
    minute = overrides.pop("minute_volume", _MINUTE_VOLUME)
    fields.update(overrides)
    return qg.auction_relief(qg.volume_gate(daily, minute), **fields)


# --- the band itself did not move -------------------------------------------------------


def test_the_ruling_did_not_widen_the_band_in_either_direction() -> None:
    """"The ceiling stays" -- and so does the floor. Read the constants, do not re-derive them."""
    assert qg.VOLUME_GAP_MIN_PCT == Decimal("-0.1")
    assert qg.VOLUME_GAP_MAX_PCT == Decimal("5.0")
    assert qg.AUCTION_RELIEF_MAX_SHORTFALL_PCT == Decimal("20.0")


def test_relief_never_touches_the_gate1_verdict_itself() -> None:
    """A relieved day still FAILED gate 1. Relief is a second verdict, never a widening."""
    gate1 = qg.volume_gate(_DAILY_VOLUME, _MINUTE_VOLUME)
    assert not gate1.passed and gate1.gap_pct == Decimal(10)
    assert _relief().relieved is True
    # the gate-1 result object is unchanged by having been examined
    assert not gate1.passed


def test_a_passing_day_is_never_relieved_so_it_cannot_be_double_counted() -> None:
    passing = qg.volume_gate(1_000_000, 990_000)  # gap 1.0%, inside the band
    assert passing.passed
    result = _relief(daily_volume=1_000_000, minute_volume=990_000)
    assert not result.relieved, "a passing day has nothing to relieve; counting it twice is a bug"


# --- the canonical relievable day -------------------------------------------------------


def test_the_thin_day_with_intact_extremes_and_a_matching_open_is_relieved() -> None:
    result = _relief()
    assert result.relieved
    assert all(held for _name, held in result.conditions)
    assert "auction-relief pass" in result.reason


# --- each condition, flipped alone, refuses the relief -----------------------------------


def test_condition_a_a_below_floor_failure_is_never_relieved() -> None:
    """The minute sum EXCEEDS the daily total -- an un-recovered vendor volume factor, not a thin
    market. The ruling is explicit: "below-floor failures are never relieved"."""
    result = _relief(daily_volume=1_000_000, minute_volume=1_100_000)  # gap -10%
    assert not result.relieved
    assert "(a)" in result.reason
    assert result.conditions[0] == (result.conditions[0][0], False)


def test_condition_b_a_clipped_high_refuses_the_relief() -> None:
    """One paisa off the daily high is enough: the ruling's rationale is that data LOSS clips
    extremes, so the test carries NO tolerance."""
    result = _relief(minute_high_paise=_RAW_HIGH - 1)
    assert not result.relieved
    assert "(b)" in result.reason and "(a)" not in result.reason


def test_condition_b_a_clipped_low_refuses_the_relief() -> None:
    result = _relief(minute_low_paise=_RAW_LOW + 1)
    assert not result.relieved
    assert "(b)" in result.reason


def test_condition_c_a_missing_opening_print_refuses_the_relief() -> None:
    """A lost opening minute is the one loss that need not move either extreme, which is exactly
    why the ruling tests the open separately from the high and the low."""
    result = _relief(minute_open_paise=_RAW_OPEN + 25)
    assert not result.relieved
    assert "(c)" in result.reason
    # ... and conditions (a), (b) and (d) all still held, so (c) alone decided it
    held = dict(result.conditions)
    assert sum(1 for value in held.values() if not value) == 1


def test_condition_d_a_shortfall_beyond_the_sanity_cap_refuses_the_relief() -> None:
    """25% short with perfect extremes is beyond anything a pre-open auction explains."""
    result = _relief(daily_volume=1_000_000, minute_volume=750_000)  # gap 25%
    assert not result.relieved
    assert "(d)" in result.reason


def test_the_cap_is_inclusive_at_exactly_twenty_percent() -> None:
    """"shortfall <= 20%" -- the boundary itself is relieved, matching the ruling's own operator."""
    result = _relief(daily_volume=1_000_000, minute_volume=800_000)  # gap exactly 20.0%
    assert result.relieved


def test_a_relievable_gap_just_above_the_ceiling_is_relieved_and_just_below_is_not_examined() -> None:
    inside = qg.volume_gate(1_000_000, 950_000)  # gap exactly 5.0% -- inside the band
    assert inside.passed, "the ceiling is inclusive; this day never reaches relief at all"
    just_above = _relief(daily_volume=1_000_000, minute_volume=949_000)  # gap 5.1%
    assert just_above.relieved


# --- degenerate inputs -------------------------------------------------------------------


def test_a_zero_raw_high_or_open_refuses_the_relief_rather_than_matching_on_zero() -> None:
    """A damaged daily row must not satisfy "equals exactly" by both sides being zero."""
    assert not _relief(minute_high_paise=0, raw_high_paise=0).relieved
    assert not _relief(minute_open_paise=0, raw_open_paise=0).relieved


def test_a_zero_daily_volume_day_has_no_gap_and_is_not_relieved() -> None:
    gate1 = qg.volume_gate(0, 5_000)
    assert gate1.gap_pct is None and not gate1.passed
    result = qg.auction_relief(
        gate1,
        minute_open_paise=_RAW_OPEN, minute_high_paise=_RAW_HIGH, minute_low_paise=_RAW_LOW,
        raw_open_paise=_RAW_OPEN, raw_high_paise=_RAW_HIGH, raw_low_paise=_RAW_LOW,
    )
    assert not result.relieved


@pytest.mark.parametrize("index", range(4))
def test_every_condition_is_named_in_the_result_so_a_refusal_always_says_which(index: int) -> None:
    result = _relief()
    name, held = result.conditions[index]
    assert held and name.startswith(f"({'abcd'[index]})")
