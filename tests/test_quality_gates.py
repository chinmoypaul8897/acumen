"""Tests for the CONTEXT 4.5 quality gates. PURE.

Gate 1 band edges, gate 2 exclusion rules (as REDEFINED by the architect's completeness ruling,
2026-07-26 -- QUESTIONS.md "CONTEXT 4.5 / 7-E4 AMENDMENT"), and gate 3 (OPEN-8) RAW / ADJUSTED /
INDETERMINATE classification and its consistency reduction.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from acumen import quality_gates as qg

_SRC = Path(qg.__file__).parent


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
    #: Gate 2's NEGATIVE-VALUES trigger (the completeness ruling) inspects volume too -- a negative
    #: share count is as impossible as a negative price and would poison gate 1's own sum.
    volume: int = 1000


def _full_day(day: date) -> list[Bar]:
    open_dt = datetime.combine(day, time(9, 15))
    return [Bar(open_dt + timedelta(minutes=i), 100, 110, 90, 105) for i in range(375)]


DAY = date(2026, 7, 14)


def test_gate2_full_clean_day_passes() -> None:
    result = qg.integrity_gate(_full_day(DAY), DAY)
    assert result.passed and result.present == 375 and result.missing == 0


def test_gate2_15_missing_passes_but_16_excludes_when_gate1_also_fails() -> None:
    """The completeness ruling keeps CONTEXT 4.5's 15-minute threshold, but only as a DATA-LOSS
    trigger -- i.e. on a day where gate 1 ALSO fails, where absent stamps are indistinguishable
    from lost candles."""
    bars = _full_day(DAY)
    assert qg.integrity_gate(bars[:-15], DAY, volume_reconciled=False).passed        # 15 -> in
    assert not qg.integrity_gate(bars[:-16], DAY, volume_reconciled=False).passed    # 16 -> out


def test_gate2_missing_minutes_with_gate1_passing_are_liquidity_not_an_exclusion() -> None:
    """The ruling's headline: the vendor OMITS minutes in which nothing traded, so on a day whose
    gate-1 volume reconciliation PASSES every traded rupee is already accounted for and the absent
    stamps are NO-TRADE minutes. The day is INCLUDED and the count becomes a liquidity statistic.

    The measured case this is drawn from: ABB in 2019 traded 318/293/325/338 of 375 minutes on four
    consecutive days -- 37..82 missing -- while gate 1 reconciled every one of them.
    """
    bars = _full_day(DAY)
    result = qg.integrity_gate(bars[:293], DAY, volume_reconciled=True)  # 82 tradeless minutes
    assert result.passed
    assert result.present == 293 and result.missing == 82
    assert result.missing_excluded is False
    assert result.reasons == ()
    assert "NO-TRADE" in result.liquidity_note and "82" in result.liquidity_note


def test_gate2_missing_minutes_with_an_UNRUN_gate1_still_excludes_conservatively() -> None:
    """``volume_reconciled=None`` means gate 1 could not be run at all (no raw daily row for the
    day). The ruling's licence is "gate-1 PASSES"; an unrun gate has not passed, so the
    pre-amendment behaviour stands and the day is excluded."""
    bars = _full_day(DAY)
    result = qg.integrity_gate(bars[:293], DAY, volume_reconciled=None)
    assert not result.passed and result.missing_excluded is True
    assert "could not be run" in result.reasons[0]


def test_gate2_duplicates_and_impossible_ohlc_still_exclude_on_a_gate1_passing_day() -> None:
    """The redefinition narrows ONE trigger (missing minutes). The others are untouched: a
    duplicate stamp and an impossible OHLC exclude the day even when gate 1 reconciles it."""
    dupes = _full_day(DAY)
    dupes.append(dupes[0])
    assert not qg.integrity_gate(dupes, DAY, volume_reconciled=True).passed

    broken = _full_day(DAY)
    broken[10] = Bar(broken[10].stamp, 100, 90, 110, 100)  # high < low
    assert not qg.integrity_gate(broken, DAY, volume_reconciled=True).passed


@pytest.mark.parametrize(
    "bad,label",
    [
        (Bar(datetime.combine(DAY, time(9, 25)), 100, 110, -90, 105), "negative low"),
        (Bar(datetime.combine(DAY, time(9, 25)), -100, 110, 90, 105), "negative open"),
        (Bar(datetime.combine(DAY, time(9, 25)), 100, 110, 90, 105, -1), "negative volume"),
    ],
)
def test_gate2_negative_values_exclude_the_day(bad: Bar, label: str) -> None:
    """The completeness ruling ADDS "negative values" as an exclusion trigger. A negative price or
    share count is impossible, not merely improbable, so it excludes even on a gate-1-passing day.
    Note the negative OPEN: the OHLC-sanity trigger deliberately omits ``open`` (CONTEXT 4.5 does
    not list it), but "negative values" names no field."""
    bars = _full_day(DAY)
    bars[10] = bad
    result = qg.integrity_gate(bars, DAY, volume_reconciled=True)
    assert result.negative_values == 1, label
    assert not result.passed, label
    assert any("NEGATIVE" in r for r in result.reasons), label


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
    excludes: its 375 regular-session minutes are all missing (missing>15 fires).

    The completeness redefinition does NOT let this one through. Such a day cannot reconcile its
    volume against the bhavcopy -- the whole regular session is absent -- so gate 1 fails (or cannot
    run) and the missing-minutes trigger still fires. Both non-passing verdicts are pinned here.
    """
    evening = [Bar(datetime.combine(DAY, time(18, 15)) + timedelta(minutes=i), 100, 110, 90, 105) for i in range(60)]
    for verdict in (False, None):
        result = qg.integrity_gate(evening, DAY, volume_reconciled=verdict)
        assert result.present == 0 and result.missing == 375 and not result.passed
        assert result.missing_excluded is True


def test_the_gate1_band_is_not_widened_by_either_2026_07_26_ruling() -> None:
    """Both rulings this session executes say the band stays put: Q-12's "the -0.1% floor is NOT
    widened", and the completeness ruling leans on gate 1 as the completeness oracle rather than
    relaxing it. Pinned as literals so a future "just widen it a little" is a failing test."""
    assert qg.VOLUME_GAP_MIN_PCT == Decimal("-0.1")
    assert qg.VOLUME_GAP_MAX_PCT == Decimal("5.0")
    assert qg.MAX_MISSING_MINUTES == 15
    assert qg.EXPECTED_SESSION_MINUTES == 375


def _src_modules() -> list[tuple[str, ast.Module]]:
    return [
        (path.name, ast.parse(path.read_text(encoding="utf-8")))
        for path in sorted(_SRC.glob("*.py"))
    ]


def test_e4_minute_count_trigger_is_retired_nothing_in_src_counts_window_minutes() -> None:
    """CONTEXT 7-E4's "missing > 5 of its 120" trigger is RETIRED by the completeness ruling: the
    09:15-11:14 profile window is valid when the DAY passes gate 1.

    E4 was never implemented (chunk 6 owns the POC window), so this probe exists to stop chunk 6
    building the retired rule by accident. It fails if any ``src/`` module compares anything against
    the 120-minute window length, or names a constant that counts window/profile minutes.
    """
    for name, tree in _src_modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                operands = [node.left, *node.comparators]
                for operand in operands:
                    assert not (
                        isinstance(operand, ast.Constant) and operand.value == 120
                    ), f"{name}: a comparison against the retired E4 120-minute window count"
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                upper = node.id.upper()
                assert not (
                    ("WINDOW" in upper or "PROFILE" in upper)
                    and ("MISSING" in upper or "MINUTES" in upper)
                ), f"{name}: {node.id} looks like a retired E4 window-minute-count trigger"


def test_the_missing_minutes_trigger_is_guarded_by_the_gate1_verdict_in_code() -> None:
    """An ``ast`` probe on the ruling itself: inside :func:`integrity_gate`, the branch that fires on
    ``missing > MAX_MISSING_MINUTES`` must consult ``volume_reconciled``. Deleting the guard -- the
    one way to silently restore the pre-amendment behaviour while every other test still passes --
    fails here."""
    tree = ast.parse(Path(qg.__file__).read_text(encoding="utf-8"))
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "integrity_gate"
    )
    guarded = [
        node for node in ast.walk(fn)
        if isinstance(node, ast.If)
        and any(
            isinstance(c, ast.Name) and c.id == "MAX_MISSING_MINUTES"
            for c in ast.walk(node.test)
        )
        and any(
            isinstance(c, ast.Name) and c.id == "volume_reconciled"
            for c in ast.walk(node)
        )
    ]
    assert guarded, "the missing-minutes trigger no longer consults the gate-1 verdict"


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
