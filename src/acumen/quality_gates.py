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
* **Gate 2 -- candle integrity.** Expect 375 minutes 09:15..15:29. **Missing > 15 -> exclude.**
  Any duplicate stamp, ``high < low``, or a CLOSE outside ``[low, high]`` -> exclude (exactly
  the criteria CONTEXT 4.5 enumerates -- ``open`` is not among them). An out-of-session bar is
  dropped at the candle level (CONTEXT 7-E2), not counted as a day-exclusion trigger.
  (Milder window-level damage that this gate PASSES is caught by CONTEXT 7-E4 in chunk 6.)
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


# --- Gate 2: candle integrity ----------------------------------------------------------

#: CONTEXT 4.5 gate 2: the full session is 375 one-minute candles, 09:15..15:29.
EXPECTED_SESSION_MINUTES: int = 375

#: CONTEXT 4.5 gate 2: more than this many missing minutes in the day -> exclude.
MAX_MISSING_MINUTES: int = 15


@dataclass(frozen=True)
class IntegrityGateResult:
    """Gate-2 outcome for one symbol-day."""

    present: int
    missing: int
    duplicates: int
    out_of_session: int
    ohlc_violations: int
    passed: bool
    reasons: tuple[str, ...]


def session_minutes(day: date) -> tuple[datetime, ...]:
    """The 375 expected 1-minute open-stamps for ``day``: 09:15..15:29. PURE."""
    open_dt = datetime.combine(day, SESSION_OPEN)
    return tuple(open_dt + timedelta(minutes=i) for i in range(EXPECTED_SESSION_MINUTES))


def integrity_gate(bars: Sequence["_Bar"], day: date) -> IntegrityGateResult:
    """CONTEXT 4.5 gate 2: 375 stamps, no dupes, OHLC sane; missing > 15 -> exclude. PURE.

    Args:
        bars: the day's 1-minute bars (each with ``stamp`` naive IST and integer-paise OHLC).
        day: the trade date the bars must all belong to.

    A day is EXCLUDED (``passed == False``) on exactly CONTEXT 4.5 gate-2's criteria: more
    than 15 missing minutes, OR any duplicate stamp, OR any OHLC violation (``high < low`` or a
    CLOSE outside ``[low, high]`` -- the two the spec enumerates; ``open`` is deliberately NOT
    tested, as CONTEXT 4.5 does not list it). Bars stamped outside the 09:15..15:29 session are
    counted (``out_of_session``, for the report) but do NOT by themselves exclude the day:
    CONTEXT 7-E2 excludes an out-of-session candle at the CANDLE level (drop the stray bar), not
    at the day level. A day that is ENTIRELY a non-standard session (e.g. Muhurat evening) still
    excludes -- its 375 regular-session minutes are all missing, so the missing>15 rule fires.
    Every failure that fired is named in ``reasons``.
    """
    reasons: list[str] = []
    expected = set(session_minutes(day))

    seen: set[datetime] = set()
    duplicates = 0
    out_of_session = 0
    ohlc_violations = 0
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

    present = len(present_in_session)
    missing = len(expected - present_in_session)

    if missing > MAX_MISSING_MINUTES:
        reasons.append(f"{missing} missing minutes (> {MAX_MISSING_MINUTES}); day excluded")
    if duplicates:
        reasons.append(f"{duplicates} duplicate stamp(s)")
    if ohlc_violations:
        reasons.append(f"{ohlc_violations} OHLC-sanity violation(s) (high<low or close out of range)")

    passed = not reasons
    return IntegrityGateResult(
        present=present,
        missing=missing,
        duplicates=duplicates,
        out_of_session=out_of_session,
        ohlc_violations=ohlc_violations,
        passed=passed,
        reasons=tuple(reasons),
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
    """Structural stand-in: anything with naive ``stamp`` and integer-paise OHLC fields."""

    stamp: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
