"""Quality gates for ingested 1-minute data (CONTEXT 4.5). PURE.

CONTEXT 4.5 defines three gates that decide whether a symbol-day of 1-minute candles may be
trusted by the backtest. This module is the pure arithmetic of all three; the backfill
(:mod:`acumen.minute_backfill`) supplies the numbers and records the verdicts, and chunk 9
excludes a flagged day and counts it (CONTEXT 7-E3).

* **Gate 1 -- volume reconciliation.** ``gap% = (bhavcopy_daily_vol - sum(1-min vol)) /
  bhavcopy_daily_vol``. Acceptance band **-0.1% .. +5.0%** (the PoC observed +0.02%..+3.6%,
  the small positive shortfall being the pre-open call-auction volume the exchange counts in
  the daily total but not in continuous-session 1-min candles). Outside the band -> flag,
  exclude, log. The daily figure is the RAW daily store (chunk 2) bhavcopy volume.
  **AUCTION RELIEF** (the architect's ruling of 2026-07-26, QUESTIONS.md Q-12 addendum 2): the
  ceiling STAYS and the band is untouched, but an ABOVE-ceiling failure whose day carries intact
  extremes (1-min high/low == the raw daily high/low exactly), a matching opening print and a
  shortfall <= 20% is a thin day whose pre-open auction exceeds 5% -- a market property, not data
  loss. Such a day is an ``auction-relief pass``, counted SEPARATELY and disclosed
  (:func:`auction_relief`). Below-floor failures are NEVER relieved.
* **Gate 1P -- per-day PRICE containment** (the architect's ruling of 2026-07-28, QUESTIONS.md
  Q-14; CONTEXT v1.3 will carry it, effective now by that record). Gate 1 proves a day's VOLUME
  and the Q-11 oracle proves an ERA's price over its probe days; 1,963 stored symbol-days fell
  between the two at 0.1x-5x the traded price and passed the whole battery (REVIEW_5B finding
  Q1). Gate 1P closes that: **the stored day's 1-minute fold interval ``[low, high]`` must sit
  INSIDE the raw bhavcopy interval ``[daily_low, daily_high]``**, within
  ``max(2 paise, 0.1% x raw)`` per side (:func:`price_containment_gate`). It is a CONTAINMENT and
  not an equality on purpose: the exchange's daily high is the maximum of every trade, including
  auction and block prints the continuous 1-minute series never held, so a fold high BELOW the
  daily high is ordinary while one ABOVE it is impossible. A day with no raw daily row cannot be
  price-proven and FAILS. A failing day is EXCLUDED and COUNTED under its own reason
  (:data:`REASON_GATE1P`), never folded into gate 1's count.
* **Gate 2 -- candle integrity** (REDEFINED by the architect's completeness ruling, 2026-07-26 --
  QUESTIONS.md "CONTEXT 4.5 / 7-E4 AMENDMENT"; CONTEXT v1.3 will carry it). Completeness is
  measured by gate 1, not by a minute count: **the vendor omits minutes in which nothing traded**,
  so a missing stamp on a day whose gate-1 volume reconciliation PASSES is a NO-TRADE minute and
  every traded rupee is already accounted for. The exclusion triggers are exactly four: any
  duplicate stamp; impossible OHLC (``high < low`` or a CLOSE outside ``[low, high]`` -- CONTEXT
  4.5's own two, ``open`` is not among them); any NEGATIVE price or volume; and missing minutes
  ``> 15`` **on a day where gate 1 ALSO fails** (there, missing stamps are indistinguishable from
  data loss). Missing minutes alone, with gate 1 passing, are recorded as LIQUIDITY STATISTICS and
  never exclude. An out-of-session bar is dropped at the candle level (CONTEXT 7-E2), not counted
  as a day-exclusion trigger. NO liquidity filter exists anywhere -- the trader specified none.
* **CONTEXT 7-E4 (chunk 6's POC window) is redefined the same way and its minute-count trigger is
  RETIRED.** The 09:15-11:14 profile window is valid when the DAY passes gate 1; zero-volume
  minutes contribute zero volume to the profile, which remains arithmetically true. Nothing in
  ``src/`` implements the retired "missing > 5 of its 120" count, and
  ``tests/test_quality_gates.py`` keeps an ``ast`` probe that fails if a later chunk reintroduces
  it.
* **Gate 3 -- adjustment sanity (RESOLVES OPEN-8).** On a known split/bonus ex-date, compare
  SmartAPI 1-minute prices from BEFORE the ex-date against the RAW daily store for the same
  pre-ex day. The GATE LESSON (PROGRESS.md chunk-4): a cross-source price comparison is only
  valid RAW-to-RAW with no intervening corporate action -- so we compare a pre-ex 1-min day
  against that same pre-ex raw daily day (no event between them), and against raw x k. If the
  1-min matches raw -> the 1-min feed is RAW; if it matches raw x k -> it is ADJUSTED. The
  verdict must be consistent across the three named events; ADJUSTED means the intraday price
  domain (CONTEXT 7-E11) is wrong and the architect must amend it before chunk 6 consumes
  minute data.

Volume is shares (never paise); prices are integer paise (CONTEXT 7-E11).

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable, Sequence

from .calendar import SESSION_OPEN, is_session_time

# --- Gate 1: volume reconciliation -----------------------------------------------------

#: CONTEXT 4.5 gate 1 acceptance band on gap%, inclusive at both ends.
VOLUME_GAP_MIN_PCT: Decimal = Decimal("-0.1")
VOLUME_GAP_MAX_PCT: Decimal = Decimal("5.0")


@dataclass(frozen=True)
class VolumeGateResult:
    """Gate-1 outcome for one symbol-day."""

    daily_volume: int
    minute_volume_sum: int
    gap_pct: Decimal | None  # None when the daily volume is zero (undefined ratio)
    passed: bool
    reason: str


def volume_gate(daily_volume: int, minute_volume_sum: int) -> VolumeGateResult:
    """CONTEXT 4.5 gate 1: does the 1-minute volume reconcile to the daily total? PURE.

    ``gap% = (daily - sum) / daily * 100``; pass when ``-0.1 <= gap% <= 5.0``. A zero daily
    volume makes the ratio undefined and is a FAIL (a genuinely zero-volume trading day is a
    damaged figure, not a clean reconciliation).

    The gap is computed with :class:`~decimal.Decimal` so the band comparison is exact and the
    stored gap% does not drift with float error.
    """
    if daily_volume < 0 or minute_volume_sum < 0:
        raise ValueError("volumes must be non-negative")
    if daily_volume == 0:
        return VolumeGateResult(
            daily_volume=daily_volume,
            minute_volume_sum=minute_volume_sum,
            gap_pct=None,
            passed=False,
            reason="daily volume is zero; the reconciliation ratio is undefined",
        )
    gap = (Decimal(daily_volume - minute_volume_sum) / Decimal(daily_volume)) * Decimal(100)
    passed = VOLUME_GAP_MIN_PCT <= gap <= VOLUME_GAP_MAX_PCT
    if passed:
        reason = f"gap {gap:.3f}% within [{VOLUME_GAP_MIN_PCT}, {VOLUME_GAP_MAX_PCT}]"
    else:
        side = "below" if gap < VOLUME_GAP_MIN_PCT else "above"
        reason = f"gap {gap:.3f}% is {side} the band [{VOLUME_GAP_MIN_PCT}, {VOLUME_GAP_MAX_PCT}]"
    return VolumeGateResult(
        daily_volume=daily_volume,
        minute_volume_sum=minute_volume_sum,
        gap_pct=gap,
        passed=passed,
        reason=reason,
    )


# --- Gate 1 relief: the auction share of a thin day (Q-12 addendum 2) -------------------

#: The architect's auction-relief ruling (2026-07-26) condition (d): a sanity cap on how large a
#: shortfall may be and still be called "the pre-open auction on a thin day". Beyond this the day
#: is not relieved whatever else holds.
AUCTION_RELIEF_MAX_SHORTFALL_PCT: Decimal = Decimal("20.0")


@dataclass(frozen=True)
class AuctionReliefResult:
    """Whether a gate-1 ABOVE-CEILING failure is relieved as a thin day's auction share.

    ``conditions`` names each of the ruling's four tests and whether it held, in the ruling's own
    order, so a refusal always says which condition refused it. ``relieved`` is True only when ALL
    four hold -- the ruling's "IFF ALL hold".
    """

    relieved: bool
    conditions: tuple[tuple[str, bool], ...]
    reason: str


def auction_relief(
    gate1: VolumeGateResult,
    *,
    minute_open_paise: int,
    minute_high_paise: int,
    minute_low_paise: int,
    raw_open_paise: int,
    raw_high_paise: int,
    raw_low_paise: int,
    max_shortfall_pct: Decimal = AUCTION_RELIEF_MAX_SHORTFALL_PCT,
) -> AuctionReliefResult:
    """CONTEXT 4.5 gate 1 AUCTION RELIEF (QUESTIONS.md Q-12 addendum 2). PURE.

    The architect's ruling of 2026-07-26, verbatim in QUESTIONS.md: **the ceiling stays**. A gate-1
    failure ABOVE the ceiling may be relieved if and only if all four hold:

    (a) the FLOOR side is not triggered -- the gap is above ``+5.0%``, never below ``-0.1%``. A
        below-floor failure means the 1-minute sum EXCEEDS the exchange's own daily total, which is
        the signature of an un-recovered vendor volume adjustment, not of a thin market;
    (b) the stored day's 1-minute HIGH equals the RAW daily HIGH and its 1-minute LOW equals the RAW
        daily LOW, **exactly** -- no tolerance. The ruling's whole rationale is that data LOSS clips
        extremes with overwhelming probability, so intact extremes are the evidence;
    (c) the FIRST stamp's OPEN equals the RAW daily OPEN, exactly. A lost opening minute is the one
        loss that need not move either extreme, so the open is tested separately;
    (d) the shortfall is at most ``max_shortfall_pct`` -- a sanity cap.

    A relieved day is an **auction-relief pass**, counted SEPARATELY from a gate-1 pass and
    disclosed; ``gate1.passed`` itself is untouched, and so are
    :data:`VOLUME_GAP_MIN_PCT` / :data:`VOLUME_GAP_MAX_PCT`. Nothing here widens the band: relief is
    a second, strictly-evidenced verdict layered on a failure, and it can only ever be reached by a
    day that already failed above the ceiling.

    Args:
        gate1: the day's :func:`volume_gate` result (a PASSING one is never relieved -- there is
            nothing to relieve, and the caller must not double-count it).
    """
    above_ceiling = (
        not gate1.passed and gate1.gap_pct is not None and gate1.gap_pct > VOLUME_GAP_MAX_PCT
    )
    extremes_intact = (
        minute_high_paise == raw_high_paise
        and minute_low_paise == raw_low_paise
        and raw_high_paise > 0
        and raw_low_paise > 0
    )
    open_matches = minute_open_paise == raw_open_paise and raw_open_paise > 0
    within_cap = gate1.gap_pct is not None and gate1.gap_pct <= max_shortfall_pct
    conditions = (
        ("(a) failed ABOVE the +5.0% ceiling, floor side not triggered", above_ceiling),
        ("(b) 1-min HIGH == raw daily HIGH and 1-min LOW == raw daily LOW exactly", extremes_intact),
        ("(c) first stamp's open == raw daily open exactly", open_matches),
        (f"(d) shortfall <= {max_shortfall_pct}%", within_cap),
    )
    failed = [name for name, held in conditions if not held]
    if failed:
        return AuctionReliefResult(
            relieved=False,
            conditions=conditions,
            reason="not relieved: " + "; ".join(failed),
        )
    return AuctionReliefResult(
        relieved=True,
        conditions=conditions,
        reason=(
            f"auction-relief pass: volume short by {gate1.gap_pct:.3f}% while the day's extremes "
            "and opening print match the exchange's own daily record exactly -- a thin day whose "
            "pre-open call auction exceeds 5% of its volume, not data loss"
        ),
    )


# --- Gate 1P: per-day PRICE containment (QUESTIONS.md Q-14) -----------------------------

#: Gate 1P's absolute tolerance floor, in paise. The Q-11 ruling's "within 2 paise (scaled)": the
#: vendor's cumulative rounding of a multi-factor chain leaves a recovered raw price a hair off.
#: This is the SINGLE definition of that constant -- :mod:`acumen.vendor_adjustment` imports it, so
#: the era oracle and the per-day gate can never drift apart.
PRICE_CONTAINMENT_MIN_PAISE: int = 2

#: Gate 1P's RELATIVE tolerance floor: a price is contained within ``max(2 paise, this x raw)``.
#: 0.1% absorbs market microstructure (the 1-minute fold high/low can differ from the official
#: daily high/low by a few paise -- an odd-lot or block print the bhavcopy counts and the continuous
#: series does not) while staying far below the smallest WRONG-factor residual (the rights
#: ours-vs-vendor gap, ~0.33%); every other wrong chain (rights not-applied ~1.3%, demerger ~9%,
#: bonus ~50%, a 5:1 split 400%) is orders of magnitude larger.
PRICE_CONTAINMENT_REL: Decimal = Decimal("0.001")

#: The exclusion reason a gate-1P failure is counted under (CONTEXT 7-E3: excluded AND counted).
#: Distinct from gate 1's, per the Q-14 ruling -- a price failure is never folded into the volume
#: count, and the two numerators are printed side by side everywhere.
REASON_GATE1P: str = "gate-1P (per-day price containment)"

#: Why a day failed gate 1P, so the run can count the two causes apart.
GATE1P_NO_ORACLE: str = "no-raw-daily-row"
GATE1P_ABOVE: str = "fold-high-above-daily-high"
GATE1P_BELOW: str = "fold-low-below-daily-low"


def price_containment_limit(
    raw_paise: int, min_paise: int = PRICE_CONTAINMENT_MIN_PAISE
) -> Decimal:
    """``max(min_paise, PRICE_CONTAINMENT_REL x raw)`` -- gate 1P's per-side tolerance. PURE.

    One definition, used by the per-day gate here AND by the era oracle in
    :mod:`acumen.vendor_adjustment` (which imports it), so the two can never drift.
    """
    return max(Decimal(min_paise), Decimal(raw_paise) * PRICE_CONTAINMENT_REL)


@dataclass(frozen=True)
class PriceContainmentResult:
    """Gate-1P outcome for one stored symbol-day.

    ``high_excess_paise`` is how far the fold HIGH sits ABOVE the tolerated daily high (0 when
    inside), ``low_excess_paise`` how far the fold LOW sits BELOW the tolerated daily low. Both are
    ``None`` when the day had no raw daily row to test against -- which is itself a FAIL.
    """

    minute_high_paise: int
    minute_low_paise: int
    raw_high_paise: int | None
    raw_low_paise: int | None
    high_excess_paise: Decimal | None
    low_excess_paise: Decimal | None
    passed: bool
    reason: str
    #: :data:`GATE1P_NO_ORACLE` / :data:`GATE1P_ABOVE` / :data:`GATE1P_BELOW`, or "" on a pass.
    cause: str = ""


def price_containment_gate(
    minute_high_paise: int,
    minute_low_paise: int,
    raw_high_paise: int | None,
    raw_low_paise: int | None,
    *,
    min_tol_paise: int = PRICE_CONTAINMENT_MIN_PAISE,
) -> PriceContainmentResult:
    """CONTEXT 4.5 gate 1P (QUESTIONS.md Q-14): is this stored day's PRICE proven? PURE.

    The architect's ruling of 2026-07-28, verbatim in QUESTIONS.md: "for every stored symbol-day,
    the un-adjusted 1-minute fold interval ``[low, high]`` must sit INSIDE the raw bhavcopy interval
    ``[daily_low, daily_high]`` with tolerance ``max(2 paise, 0.1% of the raw price)`` per side; a
    day with no raw daily row cannot be price-proven and FAILS."

    **Containment, not equality.** The exchange's daily high is the maximum over every trade of the
    session, including the pre-open auction and block prints the continuous 1-minute series never
    carries; the daily low is the minimum over the same set. So a fold interval strictly INSIDE the
    daily interval is ordinary market microstructure, while a fold high ABOVE the daily high (or a
    fold low BELOW the daily low) is impossible on raw prices and means the day is on the wrong
    price scale. A wrong scale moves BOTH ends the same way, so one of them always escapes:
    ``0.1x`` drops the fold low below the daily low, ``5x`` lifts the fold high above the daily
    high, and neither can hide inside the interval.

    Args:
        minute_high_paise: max HIGH over the day's stored 1-minute bars.
        minute_low_paise: min LOW over the same bars.
        raw_high_paise: the RAW bhavcopy daily high, or ``None`` when the day has no daily row.
        raw_low_paise: the RAW bhavcopy daily low, or ``None``.
        min_tol_paise: the absolute floor of the per-side tolerance.

    A day that fails is EXCLUDED and COUNTED under :data:`REASON_GATE1P` (CONTEXT 7-E3).
    """
    if raw_high_paise is None or raw_low_paise is None:
        return PriceContainmentResult(
            minute_high_paise=minute_high_paise,
            minute_low_paise=minute_low_paise,
            raw_high_paise=raw_high_paise,
            raw_low_paise=raw_low_paise,
            high_excess_paise=None,
            low_excess_paise=None,
            passed=False,
            reason=(
                "no raw daily row for this day, so the stored prices can be compared with nothing "
                "-- the day is not price-proven (Q-14 ruling)"
            ),
            cause=GATE1P_NO_ORACLE,
        )
    if raw_high_paise <= 0 or raw_low_paise <= 0:
        return PriceContainmentResult(
            minute_high_paise=minute_high_paise,
            minute_low_paise=minute_low_paise,
            raw_high_paise=raw_high_paise,
            raw_low_paise=raw_low_paise,
            high_excess_paise=None,
            low_excess_paise=None,
            passed=False,
            reason="the raw daily high/low is not positive; there is no interval to contain",
            cause=GATE1P_NO_ORACLE,
        )
    high_limit = price_containment_limit(raw_high_paise, min_tol_paise)
    low_limit = price_containment_limit(raw_low_paise, min_tol_paise)
    high_excess = Decimal(minute_high_paise - raw_high_paise) - high_limit
    low_excess = Decimal(raw_low_paise - minute_low_paise) - low_limit
    high_excess = max(high_excess, Decimal(0))
    low_excess = max(low_excess, Decimal(0))
    if high_excess == 0 and low_excess == 0:
        return PriceContainmentResult(
            minute_high_paise=minute_high_paise,
            minute_low_paise=minute_low_paise,
            raw_high_paise=raw_high_paise,
            raw_low_paise=raw_low_paise,
            high_excess_paise=high_excess,
            low_excess_paise=low_excess,
            passed=True,
            reason=(
                f"fold [{minute_low_paise}, {minute_high_paise}] sits inside the raw daily "
                f"[{raw_low_paise}, {raw_high_paise}] within "
                f"max({min_tol_paise} paise, {PRICE_CONTAINMENT_REL * 100}%)"
            ),
        )
    cause = GATE1P_ABOVE if high_excess > 0 else GATE1P_BELOW
    sides = []
    if high_excess > 0:
        sides.append(
            f"fold HIGH {minute_high_paise} is {high_excess} paise past the tolerated daily high "
            f"({raw_high_paise} + {high_limit})"
        )
    if low_excess > 0:
        sides.append(
            f"fold LOW {minute_low_paise} is {low_excess} paise past the tolerated daily low "
            f"({raw_low_paise} - {low_limit})"
        )
    return PriceContainmentResult(
        minute_high_paise=minute_high_paise,
        minute_low_paise=minute_low_paise,
        raw_high_paise=raw_high_paise,
        raw_low_paise=raw_low_paise,
        high_excess_paise=high_excess,
        low_excess_paise=low_excess,
        passed=False,
        reason="not price-proven: " + "; ".join(sides),
        cause=cause,
    )


# --- Gate 2: candle integrity ----------------------------------------------------------

#: CONTEXT 4.5 gate 2: the full session is 375 one-minute candles, 09:15..15:29.
EXPECTED_SESSION_MINUTES: int = 375

#: CONTEXT 4.5 gate 2: more than this many missing minutes in the day is a data-loss trigger --
#: but ONLY on a day where gate 1 also fails (the completeness ruling, 2026-07-26). On a
#: gate-1-passing day the same missing minutes are tradeless minutes and are counted as liquidity.
MAX_MISSING_MINUTES: int = 15


@dataclass(frozen=True)
class IntegrityGateResult:
    """Gate-2 outcome for one symbol-day.

    ``missing`` is always the raw count of absent session stamps -- it is a LIQUIDITY statistic on
    a gate-1-passing day and an exclusion trigger only when ``missing_excluded`` is True (the
    completeness ruling). ``liquidity_note`` names the tradeless-minute case explicitly so an
    INCLUDED day with 60 absent stamps never reads as a silent pass.
    """

    present: int
    missing: int
    duplicates: int
    out_of_session: int
    ohlc_violations: int
    passed: bool
    reasons: tuple[str, ...]
    negative_values: int = 0
    #: True when this day was excluded FOR its missing minutes (i.e. gate 1 did not pass too).
    missing_excluded: bool = False
    #: Non-empty when missing minutes were recorded as liquidity rather than treated as damage.
    liquidity_note: str = ""


def session_minutes(day: date) -> tuple[datetime, ...]:
    """The 375 expected 1-minute open-stamps for ``day``: 09:15..15:29. PURE."""
    open_dt = datetime.combine(day, SESSION_OPEN)
    return tuple(open_dt + timedelta(minutes=i) for i in range(EXPECTED_SESSION_MINUTES))


def integrity_gate(
    bars: Sequence["_Bar"], day: date, *, volume_reconciled: bool | None = None
) -> IntegrityGateResult:
    """CONTEXT 4.5 gate 2, as REDEFINED by the completeness ruling (2026-07-26). PURE.

    Args:
        bars: the day's 1-minute bars (each with ``stamp`` naive IST and integer-paise OHLC).
        day: the trade date the bars must all belong to.
        volume_reconciled: this day's GATE-1 verdict. ``True`` = gate 1 passed, so absent stamps
            are tradeless minutes (the vendor omits them) and every traded rupee is accounted for
            -- they are recorded as liquidity and do NOT exclude. ``False`` = gate 1 failed, so
            absent stamps are indistinguishable from data loss and ``missing > 15`` excludes.
            ``None`` = gate 1 could not be run at all (no raw daily row for the day); the ruling's
            licence is "gate-1 PASSES", and an unrun gate has not passed, so ``None`` keeps the
            conservative pre-amendment behaviour and ``missing > 15`` excludes.

    A day is EXCLUDED (``passed == False``) on exactly the ruling's four triggers: any duplicate
    stamp; impossible OHLC (``high < low`` or a CLOSE outside ``[low, high]`` -- the two CONTEXT
    4.5 enumerates; ``open`` is deliberately NOT tested); any NEGATIVE price or volume; and
    ``missing > 15`` when gate 1 did not pass. Bars stamped outside the 09:15..15:29 session are
    counted (``out_of_session``, for the report) but do NOT by themselves exclude the day: CONTEXT
    7-E2 excludes an out-of-session candle at the CANDLE level (drop the stray bar), not at the day
    level. A day that is ENTIRELY a non-standard session (e.g. a Muhurat evening) has all 375
    regular-session minutes absent AND cannot reconcile its volume, so gate 1 fails and the
    missing-minutes trigger still fires -- the redefinition does not let one through.

    Every failure that fired is named in ``reasons``; a day INCLUDED with absent stamps names that
    in ``liquidity_note`` rather than passing silently.
    """
    reasons: list[str] = []
    expected = set(session_minutes(day))

    seen: set[datetime] = set()
    duplicates = 0
    out_of_session = 0
    ohlc_violations = 0
    negative_values = 0
    present_in_session: set[datetime] = set()

    for bar in bars:
        stamp = bar.stamp
        if stamp.date() != day or not is_session_time(stamp, minutes=1):
            out_of_session += 1  # CONTEXT 7-E2: a stray candle is dropped, not a day-killer
            continue
        if stamp in seen:
            duplicates += 1
        seen.add(stamp)
        present_in_session.add(stamp)
        if not (bar.low_paise <= bar.high_paise and bar.low_paise <= bar.close_paise <= bar.high_paise):
            ohlc_violations += 1  # CONTEXT 4.5 gate-2: high<low or close-outside-[low,high] ONLY
        # The ruling's third trigger: a negative price or share count is IMPOSSIBLE, not merely
        # improbable. Volume is included -- a negative share count is as impossible as a negative
        # price and would poison gate 1's own sum. ``open`` IS tested here: the OHLC-sanity trigger
        # deliberately omits it (CONTEXT 4.5 does not list it), but "negative values" names no
        # field, and a negative open is impossible on any reading.
        if min(bar.open_paise, bar.high_paise, bar.low_paise, bar.close_paise, bar.volume) < 0:
            negative_values += 1

    present = len(present_in_session)
    missing = len(expected - present_in_session)

    liquidity_note = ""
    missing_excluded = False
    if missing > MAX_MISSING_MINUTES:
        if volume_reconciled is True:
            # The completeness ruling: gate 1 PASSED, so the absent stamps are no-trade minutes.
            liquidity_note = (
                f"{missing} of {EXPECTED_SESSION_MINUTES} session minutes carry no trade "
                f"({present} traded); gate 1 reconciles the day's volume, so these are NO-TRADE "
                "minutes, not missing data -- recorded as liquidity, not an exclusion"
            )
        else:
            missing_excluded = True
            why = (
                "gate 1 ALSO fails on this day, so the absent stamps are indistinguishable from "
                "data loss"
                if volume_reconciled is False
                else "gate 1 could not be run for this day (no raw daily row), so completeness is "
                "unproven"
            )
            reasons.append(
                f"{missing} missing minutes (> {MAX_MISSING_MINUTES}) and {why}; day excluded"
            )
    elif missing:
        liquidity_note = f"{missing} of {EXPECTED_SESSION_MINUTES} session minutes carry no trade"
    if duplicates:
        reasons.append(f"{duplicates} duplicate stamp(s)")
    if ohlc_violations:
        reasons.append(f"{ohlc_violations} OHLC-sanity violation(s) (high<low or close out of range)")
    if negative_values:
        reasons.append(f"{negative_values} bar(s) carry a NEGATIVE price or volume (impossible)")

    passed = not reasons
    return IntegrityGateResult(
        present=present,
        missing=missing,
        duplicates=duplicates,
        out_of_session=out_of_session,
        ohlc_violations=ohlc_violations,
        passed=passed,
        reasons=tuple(reasons),
        negative_values=negative_values,
        missing_excluded=missing_excluded,
        liquidity_note=liquidity_note,
    )


# --- Gate 3: adjustment sanity (OPEN-8) -------------------------------------------------

VERDICT_RAW: str = "RAW"
VERDICT_ADJUSTED: str = "ADJUSTED"
VERDICT_INDETERMINATE: str = "INDETERMINATE"

#: How close a ratio must sit to 1.0 (raw) or k (adjusted) to be called a match. 2% is far
#: inside the gap between the two hypotheses for every named event (RELIANCE 1:1 -> k=0.5;
#: KOTHARIPRO 1:2 -> k=2/3; GREENPLY FV split), and comfortably beyond the ~0.5% by which an
#: intraday close can differ from the official daily close (a last-30-min VWAP).
ADJUSTMENT_MATCH_TOL: Decimal = Decimal("0.02")


@dataclass(frozen=True)
class AdjustmentGateResult:
    """Gate-3 outcome for one corporate-action event (OPEN-8)."""

    verdict: str
    field_ratios: dict[str, Decimal]  # minute / raw-daily, per OHLC field compared
    candidate_k: Decimal
    detail: str


def _ratio(minute_paise: int, raw_daily_paise: int) -> Decimal:
    return Decimal(minute_paise) / Decimal(raw_daily_paise)


def adjustment_gate(
    minute_day_ohlc: dict[str, int],
    raw_daily_ohlc: dict[str, int],
    candidate_k: Decimal,
    *,
    fields: Sequence[str] = ("high_paise", "low_paise", "close_paise"),
    tol: Decimal = ADJUSTMENT_MATCH_TOL,
) -> AdjustmentGateResult:
    """CONTEXT 4.5 gate 3 / OPEN-8: is the SmartAPI 1-minute feed RAW or ADJUSTED? PURE.

    Compares a pre-ex day's SmartAPI-1-minute-derived daily OHLC against the RAW daily store's
    OHLC for the SAME pre-ex day (a clean raw-to-raw comparison, honoring the GATE LESSON --
    there is no corporate action BETWEEN a day and itself). For each compared field the ratio
    ``minute / raw_daily`` is computed:

    * every ratio within ``tol`` of **1.0** -> :data:`VERDICT_RAW` (the 1-min feed is raw);
    * every ratio within ``tol`` of **candidate_k** -> :data:`VERDICT_ADJUSTED` (the feed is
      back-adjusted for the event, so a pre-ex price shows as ``raw x k``);
    * anything else (mixed or matching neither) -> :data:`VERDICT_INDETERMINATE`.

    ``candidate_k`` is the corporate-action factor for the event (e.g. 0.5 for a 1:1 bonus).

    Raises:
        ValueError: a compared field is missing from either OHLC dict, or a raw price is <= 0.
    """
    ratios: dict[str, Decimal] = {}
    for field in fields:
        if field not in minute_day_ohlc or field not in raw_daily_ohlc:
            raise ValueError(f"field {field!r} missing from the OHLC being compared")
        raw = raw_daily_ohlc[field]
        if raw <= 0:
            raise ValueError(f"raw daily {field} must be positive, got {raw}")
        ratios[field] = _ratio(minute_day_ohlc[field], raw)

    all_raw = all(abs(r - Decimal(1)) <= tol for r in ratios.values())
    all_adjusted = all(abs(r - candidate_k) <= tol for r in ratios.values())

    if all_raw and not all_adjusted:
        verdict = VERDICT_RAW
        detail = "every compared price matches the raw daily store (ratio ~ 1.0)"
    elif all_adjusted and not all_raw:
        verdict = VERDICT_ADJUSTED
        detail = f"every compared price matches raw x k (ratio ~ {candidate_k})"
    else:
        verdict = VERDICT_INDETERMINATE
        detail = (
            "prices match neither raw (1.0) nor raw x k "
            f"({candidate_k}) within {tol}; ratios={ {k: str(v) for k, v in ratios.items()} }"
        )
    return AdjustmentGateResult(
        verdict=verdict, field_ratios=ratios, candidate_k=candidate_k, detail=detail
    )


# --- Gate 3, continuity form: "the adjusted series shows no fake gap" -------------------

#: CONTEXT 4.5 gate 3, literally: "on every split/bonus ex-date in history, adjusted series
#: must show |day-over-day gap| < 20% (unadjusted 1:10 split = -90% fake gap must disappear)".
ADJUSTMENT_CONTINUITY_MAX_GAP: Decimal = Decimal("0.20")


@dataclass(frozen=True)
class ContinuityGateResult:
    """Gate-3 (continuity form) outcome for one corporate-action ex-date on one symbol."""

    ex_date: date
    pre_ex_day: date
    ex_day: date
    adjusted_pre_close_paise: int
    ex_close_paise: int
    gap: Decimal
    passed: bool
    reason: str


def adjustment_continuity_gate(
    ex_date: date,
    pre_ex_day: date,
    ex_day: date,
    pre_ex_close_paise: int,
    ex_close_paise: int,
    k: Decimal,
    *,
    max_gap: Decimal = ADJUSTMENT_CONTINUITY_MAX_GAP,
) -> ContinuityGateResult:
    """CONTEXT 4.5 gate 3 across ONE ex-date, on the stored RAW series. PURE.

    The spec's wording is about the ADJUSTED series: a 1:10 split leaves a -90% fake gap in
    unadjusted prices, and applying the CONTEXT 4.2 factor must make it disappear. Our minute
    store deliberately holds RAW same-day prices (CONTEXT 7-E11, QUESTIONS.md Q-10), so the
    adjustment is applied HERE, at the comparison: the pre-ex close is brought into the post-ex
    scale by the event's own factor ``k`` -- exactly :func:`acumen.corp_actions.adjust_pair` --
    and the surviving day-over-day move must be an ordinary market move, ``|gap| < 20%``.

    A FAIL means one of three things, all worth stopping on: our ``k`` is wrong, the store is
    not actually raw across that date, or the event itself was mis-parsed. It never means "the
    market moved", because no ordinary session moves a liquid F&O underlying 20% overnight --
    and a mis-scaled series misses by the factor (50% for a 1:1 bonus, 80% for a 5:1 split).

    Args:
        ex_date: the corporate action's ex-date.
        pre_ex_day: the last stored trading day strictly before ``ex_date``.
        ex_day: the first stored trading day on or after ``ex_date``.
        pre_ex_close_paise: the RAW close on ``pre_ex_day``.
        ex_close_paise: the RAW close on ``ex_day``.
        k: the CONTEXT 4.2 pre-ex multiplier for this event.
        max_gap: the acceptance threshold as a fraction (0.20 = 20%).

    Raises:
        ValueError: a non-positive price or factor -- there is no ratio to test.
    """
    if pre_ex_close_paise <= 0 or ex_close_paise <= 0:
        raise ValueError("closes must be positive to compare a day-over-day gap")
    if k <= 0:
        raise ValueError("the adjustment factor must be positive")
    adjusted = Decimal(pre_ex_close_paise) * k
    gap = (Decimal(ex_close_paise) - adjusted) / adjusted
    passed = abs(gap) < max_gap
    pct = gap * Decimal(100)
    if passed:
        reason = f"adjusted day-over-day gap {pct:.2f}% (< {max_gap * 100}%)"
    else:
        reason = (
            f"adjusted day-over-day gap {pct:.2f}% exceeds {max_gap * 100}% across {ex_date} "
            f"({pre_ex_day} -> {ex_day}, k={k}): a wrong factor, a non-raw store, or a "
            "mis-parsed event -- never an ordinary market move"
        )
    return ContinuityGateResult(
        ex_date=ex_date,
        pre_ex_day=pre_ex_day,
        ex_day=ex_day,
        adjusted_pre_close_paise=int(adjusted.to_integral_value()),
        ex_close_paise=ex_close_paise,
        gap=gap,
        passed=passed,
        reason=reason,
    )


def combine_adjustment_verdicts(verdicts: Iterable[str]) -> str:
    """Reduce per-event gate-3 verdicts to one, requiring consistency (OPEN-8).

    Ignores :data:`VERDICT_INDETERMINATE` events (e.g. those with no pre-ex 1-min data). If the
    decisive events disagree (some RAW, some ADJUSTED) the result is
    :data:`VERDICT_INDETERMINATE` -- a contradiction the operator must resolve, never averaged
    away. No decisive event at all is also INDETERMINATE.
    """
    decided = {v for v in verdicts if v in (VERDICT_RAW, VERDICT_ADJUSTED)}
    if decided == {VERDICT_RAW}:
        return VERDICT_RAW
    if decided == {VERDICT_ADJUSTED}:
        return VERDICT_ADJUSTED
    return VERDICT_INDETERMINATE


class _Bar:  # pragma: no cover - typing aid only (structural)
    """Structural stand-in: naive ``stamp``, integer-paise OHLC, and an integer share ``volume``."""

    stamp: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int
