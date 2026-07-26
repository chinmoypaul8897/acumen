"""Tests for the CONTEXT 4.5 quality gates. PURE.

Gate 1 band edges, gate 2 exclusion rules, and gate 3 (OPEN-8) RAW / ADJUSTED /
INDETERMINATE classification and its consistency reduction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from acumen import quality_gates as qg


# --- Gate 1: volume ------------------------------------------------------------------


def test_gate1_reproduces_the_results_md_gap() -> None:
    # RESULTS.md: TCS 2026-07-14 sum 9,515,133 vs daily 9,546,290 -> +0.326%.
    result = qg.volume_gate(9546290, 9515133)
    assert result.passed
    assert result.gap_pct is not None and round(float(result.gap_pct), 3) == 0.326


@pytest.mark.parametrize(
    "daily,sminute,passed",
    [
        (10000, 9500, True),    # +5.0% exactly -> inside (inclusive upper edge)
        (10000, 9499, False),   # +5.01% -> above band
        (10000, 10010, True),   # -0.1% exactly -> inside (inclusive lower edge)
        (10000, 10011, False),  # -0.11% -> below band
        (10000, 9900, True),    # +1.0% -> comfortably inside
    ],
)
def test_gate1_band_edges_are_inclusive(daily: int, sminute: int, passed: bool) -> None:
    assert qg.volume_gate(daily, sminute).passed is passed


def test_gate1_zero_daily_volume_fails() -> None:
    result = qg.volume_gate(0, 0)
    assert not result.passed and result.gap_pct is None


# --- Gate 2: integrity ---------------------------------------------------------------


@dataclass(frozen=True)
class Bar:
    stamp: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int


def _full_day(day: date) -> list[Bar]:
    open_dt = datetime.combine(day, time(9, 15))
    return [Bar(open_dt + timedelta(minutes=i), 100, 110, 90, 105) for i in range(375)]


DAY = date(2026, 7, 14)


def test_gate2_full_clean_day_passes() -> None:
    result = qg.integrity_gate(_full_day(DAY), DAY)
    assert result.passed and result.present == 375 and result.missing == 0


def test_gate2_15_missing_passes_but_16_excludes() -> None:
    bars = _full_day(DAY)
    assert qg.integrity_gate(bars[:-15], DAY).passed        # 15 missing -> still in
    assert not qg.integrity_gate(bars[:-16], DAY).passed    # 16 missing -> excluded


def test_gate2_duplicate_stamp_excludes() -> None:
    bars = _full_day(DAY)
    bars.append(bars[0])  # a duplicate 09:15
    result = qg.integrity_gate(bars, DAY)
    assert not result.passed and result.duplicates == 1


def test_gate2_high_below_low_excludes() -> None:
    bars = _full_day(DAY)
    bars[10] = Bar(bars[10].stamp, 100, 90, 110, 100)  # high < low
    result = qg.integrity_gate(bars, DAY)
    assert result.ohlc_violations == 1 and not result.passed


def test_gate2_close_outside_range_excludes() -> None:
    bars = _full_day(DAY)
    bars[10] = Bar(bars[10].stamp, 100, 110, 90, 999)  # close above high
    assert not qg.integrity_gate(bars, DAY).passed


def test_gate2_open_outside_range_is_not_a_spec_exclusion() -> None:
    """CONTEXT 4.5 gate-2 enumerates only high<low and close-outside; OPEN out of range is NOT
    a listed criterion, so a clean day with one open-out-of-range bar must PASS (REVIEW finding)."""
    bars = _full_day(DAY)
    bars[10] = Bar(bars[10].stamp, 90, 110, 100, 105)  # open 90 < low 100, but close in range
    result = qg.integrity_gate(bars, DAY)
    assert result.ohlc_violations == 0 and result.passed


def test_gate2_a_single_out_of_session_bar_does_not_exclude_the_day() -> None:
    """CONTEXT 7-E2 drops a stray candle at the CANDLE level; a full clean session day plus one
    stray 09:14 bar keeps the day (only the stray is ignored) -- REVIEW finding."""
    bars = _full_day(DAY)
    bars.append(Bar(datetime.combine(DAY, time(9, 14)), 100, 110, 90, 105))
    result = qg.integrity_gate(bars, DAY)
    assert result.out_of_session == 1 and result.present == 375 and result.passed


def test_gate2_a_muhurat_only_day_still_excludes_via_missing() -> None:
    """A day that is ENTIRELY a non-standard session (evening candles, no 09:15..15:29) still
    excludes: its 375 regular-session minutes are all missing (missing>15 fires)."""
    evening = [Bar(datetime.combine(DAY, time(18, 15)) + timedelta(minutes=i), 100, 110, 90, 105) for i in range(60)]
    result = qg.integrity_gate(evening, DAY)
    assert result.present == 0 and result.missing == 375 and not result.passed


# --- Gate 3: adjustment (OPEN-8) -----------------------------------------------------


def _ohlc(o: int, h: int, l: int, c: int) -> dict[str, int]:
    return {"open_paise": o, "high_paise": h, "low_paise": l, "close_paise": c}


def test_gate3_raw_when_minute_matches_raw_daily() -> None:
    raw = _ohlc(268700, 268870, 264400, 265570)   # RELIANCE 2024-10-25 raw
    minute = _ohlc(268700, 268870, 264400, 265520)  # ~ raw (close differs slightly, still ~1.0)
    result = qg.adjustment_gate(minute, raw, candidate_k=Decimal("0.5024"))
    assert result.verdict == qg.VERDICT_RAW


def test_gate3_adjusted_when_minute_matches_raw_times_k() -> None:
    raw = _ohlc(268700, 268870, 264400, 265570)
    # a back-adjusted feed halves the pre-ex prices (k ~ 0.5 for a 1:1 bonus)
    minute = _ohlc(134350, 134435, 132200, 132785)
    result = qg.adjustment_gate(minute, raw, candidate_k=Decimal("0.5024"))
    assert result.verdict == qg.VERDICT_ADJUSTED


def test_gate3_indeterminate_when_neither() -> None:
    raw = _ohlc(268700, 268870, 264400, 265570)
    minute = _ohlc(200000, 200000, 200000, 200000)  # matches neither 1.0 nor k
    result = qg.adjustment_gate(minute, raw, candidate_k=Decimal("0.5024"))
    assert result.verdict == qg.VERDICT_INDETERMINATE


def test_gate3_combine_requires_consistency() -> None:
    assert qg.combine_adjustment_verdicts([qg.VERDICT_RAW, qg.VERDICT_INDETERMINATE]) == qg.VERDICT_RAW
    assert qg.combine_adjustment_verdicts([qg.VERDICT_ADJUSTED, qg.VERDICT_INDETERMINATE]) == qg.VERDICT_ADJUSTED
    # a contradiction is never averaged away
    assert qg.combine_adjustment_verdicts([qg.VERDICT_RAW, qg.VERDICT_ADJUSTED]) == qg.VERDICT_INDETERMINATE
    # no decisive event at all
    assert qg.combine_adjustment_verdicts([qg.VERDICT_INDETERMINATE]) == qg.VERDICT_INDETERMINATE


# --- chunk-5B: gate 3, continuity form (CONTEXT 4.5 gate 3's literal wording) ----------


def test_a_bonus_disappears_from_the_adjusted_series() -> None:
    """The spec's own example shape: the fake gap must vanish once k is applied."""
    result = qg.adjustment_continuity_gate(
        date(2024, 10, 28), date(2024, 10, 25), date(2024, 10, 28),
        pre_ex_close_paise=265570, ex_close_paise=132800, k=Decimal("0.5"),
    )
    assert result.passed
    assert abs(result.gap) < Decimal("0.01")
    assert result.adjusted_pre_close_paise == 132785


def test_an_unadjusted_split_leaves_the_90_percent_fake_gap_and_fails() -> None:
    """CONTEXT 4.5: 'unadjusted 1:10 split = -90% fake gap must disappear'. With k applied
    WRONGLY (k=1, i.e. no adjustment) the gap survives and the gate must fail."""
    result = qg.adjustment_continuity_gate(
        date(2020, 1, 1), date(2019, 12, 31), date(2020, 1, 1),
        pre_ex_close_paise=100000, ex_close_paise=10000, k=Decimal("1"),
    )
    assert not result.passed
    assert result.gap == Decimal("-0.9")
    assert "never an ordinary market move" in result.reason


def test_the_right_factor_rescues_the_same_split() -> None:
    result = qg.adjustment_continuity_gate(
        date(2020, 1, 1), date(2019, 12, 31), date(2020, 1, 1),
        pre_ex_close_paise=100000, ex_close_paise=10000, k=Decimal("0.1"),
    )
    assert result.passed and result.gap == Decimal(0)


def test_the_threshold_is_strict_at_twenty_percent() -> None:
    exactly = qg.adjustment_continuity_gate(
        date(2020, 1, 1), date(2019, 12, 31), date(2020, 1, 1),
        pre_ex_close_paise=100000, ex_close_paise=120000, k=Decimal("1"),
    )
    assert not exactly.passed, "CONTEXT 4.5 says |gap| < 20%, so exactly 20% is a FAIL"
    inside = qg.adjustment_continuity_gate(
        date(2020, 1, 1), date(2019, 12, 31), date(2020, 1, 1),
        pre_ex_close_paise=100000, ex_close_paise=119000, k=Decimal("1"),
    )
    assert inside.passed


def test_a_non_positive_price_or_factor_raises_rather_than_returning_a_verdict() -> None:
    with pytest.raises(ValueError):
        qg.adjustment_continuity_gate(date(2020, 1, 1), date(2019, 12, 31), date(2020, 1, 1),
                                      0, 100, Decimal("0.5"))
    with pytest.raises(ValueError):
        qg.adjustment_continuity_gate(date(2020, 1, 1), date(2019, 12, 31), date(2020, 1, 1),
                                      100, 100, Decimal("0"))
