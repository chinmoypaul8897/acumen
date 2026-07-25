"""Un-adjust SmartAPI 1-minute candles back to RAW on ingest (QUESTIONS.md Q-10). PURE.

OPEN-8 resolved ADJUSTED: SmartAPI's historical 1-minute feed is corporate-action
back-adjusted, so a candle on day ``D`` fetched on date ``F`` comes back at
``raw x k_cum``, where ``k_cum`` is the product of the CONTEXT 4.2 factors of every event
with ex-date in ``(D, F]``. CONTEXT 7-E11 wants the intraday engines to run on RAW same-day
prices; the architect's Q-10 ruling (option a, with a surgical fallback) is therefore to
**un-adjust on ingest** and keep the minute store RAW ONLY -- E11 stands unchanged.

The ruling's arithmetic, verbatim, is what this module computes (Decimal, one half-even
rounding to paise at the end):

    k_cum      = product of factors of events with ex-date in (D, F]
    raw_price  = fetched_price / k_cum
    raw_volume = fetched_volume x k_cum

``k_cum`` is exactly :func:`acumen.corp_actions.factors_between` (its window is the same
half-open ``(previous, current]``), so the chunk-3 factor table -- the one the bias engine
already adjusts *with* -- is the same one this un-adjusts *against*. A recent day (after the
symbol's last CA) has an empty factor window, so ``k_cum == 1`` and un-adjustment is the exact
identity (the F10 2026 days, and every post-last-CA backtest window, are untouched).

Two guards ride along, both per the ruling:

* **Tick-snap.** A RAW price is a whole multiple of the symbol's tick; the vendor's rounding
  of ``raw x k`` to paise leaves the recovered ``raw = adjusted / k_cum`` up to ~1 paise off
  that grid. So an un-adjusted price within :data:`DEFAULT_TICK_SNAP_TOLERANCE_PAISE` of the
  nearest tick is SNAPPED onto it (E11: "tick grid preserved"); one further off is left as the
  divided value and the day is FLAGGED and counted (vendor rounding beyond tolerance). The snap
  runs only when un-adjustment actually happened (``k_cum != 1``): an identity day is stored
  byte-for-byte as fetched, never re-gridded against a possibly-coarser *current* tick.
* **Provability.** Where an event in ``(D, F]`` has NO factor -- a demerger (a Suppression) or a
  Q-6-pending rights -- the vendor adjusted by a factor we do not hold, so day ``D`` cannot be
  un-adjusted. It is marked UN-PROVABLE: the partial un-adjustment is still applied, but gate 1
  (volume reconciliation vs the raw bhavcopy) will fail it, so it is excluded and counted
  (CONTEXT 7-E3), and a systematically-failing pre-event span moves the symbol's minute clamp
  to post-event (:func:`systematic_unprovable_floor` -- the ruling's surgical fallback).

Gate 1 is, by the ruling, "the per-day PROOF of factor correctness": if the factor table is
right the un-adjusted 1-minute volume reconciles to the raw daily volume; if it is wrong or
incomplete the day fails and is dropped, never silently traded.

Prices are integer paise (CONTEXT 7-E11); volume is shares. This module is PURE arithmetic --
no I/O, no clock, no network (CONTEXT 6). The ingest orchestration that feeds it the fetched
bars, the fetch date and the tick lives in :mod:`acumen.minute_backfill`.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Iterable, Sequence

from .corp_actions import Factor, Suppression, factors_between
from .smartapi_client import OneMinuteBar

#: The vendor rounds ``raw x k`` to paise, so the recovered ``raw = adjusted / k_cum`` can sit
#: a hair off the tick grid. Within this many paise of the nearest tick -> snap onto it; further
#: -> leave it and flag the day. Two paise covers the worst case (a 0.5-paise vendor rounding
#: divided by the smallest real k ~ 0.5 => ~1 paise) with margin.
DEFAULT_TICK_SNAP_TOLERANCE_PAISE: int = 2

_ONE: Decimal = Decimal(1)


@dataclass(frozen=True)
class DayUnadjust:
    """Per-day diagnostics for one un-adjusted symbol-day (for the ledger / gate report)."""

    day: date
    fetch_date: date
    k_cum: Decimal
    identity: bool  # k_cum == 1 -> stored exactly as fetched (a post-last-CA / recent day)
    provable: bool  # no unknown-factor event (demerger / pending rights) in (D, F]
    snapped: int  # prices snapped onto the tick grid (within tolerance)
    tick_flagged: int  # prices left off-grid (> tolerance): vendor rounding beyond tolerance
    off_grid_max_paise: int  # the largest off-grid distance seen on the day
    reason: str


@dataclass(frozen=True)
class UnadjustResult:
    """The RAW bars plus the per-day diagnostics of un-adjusting one symbol's fetched window."""

    raw_bars: tuple[OneMinuteBar, ...]
    days: tuple[DayUnadjust, ...]

    @property
    def unprovable_days(self) -> tuple[date, ...]:
        return tuple(d.day for d in self.days if not d.provable)

    @property
    def tick_flagged_days(self) -> tuple[date, ...]:
        return tuple(d.day for d in self.days if d.tick_flagged)


def cumulative_factor(
    factors: Iterable[Factor], day: date, fetch_date: date, *, symbol: str | None = None
) -> Decimal:
    """``k_cum(D, F)`` = product of ``factor.k`` for events with ex-date in ``(D, F]``. PURE.

    Exactly the window of :func:`acumen.corp_actions.factors_between` (half-open on the left),
    so a candle on ``day`` is un-adjusted against precisely the events the vendor back-adjusted
    it *by*. An empty window returns :data:`Decimal(1)` -- the identity, correct for a recent
    (post-last-CA) day where fetched already equals raw. ``ordinary`` dividends and buybacks
    carry ``k = 1`` in the factor table, so they drop out of the product harmlessly.
    """
    if fetch_date < day:
        raise ValueError(
            f"fetch_date {fetch_date} is before the candle day {day}: a candle cannot be "
            "fetched before it exists."
        )
    k = _ONE
    for factor in factors_between(factors, day, fetch_date, symbol=symbol):
        k *= factor.k
    return k


def unadjust_price_paise(
    adjusted_paise: int,
    k_cum: Decimal,
    *,
    tick_paise: int | None = None,
    tol_paise: int = DEFAULT_TICK_SNAP_TOLERANCE_PAISE,
) -> tuple[int, bool, int]:
    """One price: ``raw = adjusted / k_cum`` (Decimal, one half-even round), then tick-snap. PURE.

    Returns ``(raw_paise, snapped, off_paise)``:

    * ``k_cum == 1`` -> the exact identity: ``adjusted`` returned unchanged, NOT re-gridded
      (a recent day is already raw and on the real tick grid; snapping it against a possibly
      coarser *current* tick could only corrupt it).
    * otherwise ``raw = round_half_even(adjusted / k_cum)``. If a ``tick_paise`` grid is given
      and ``raw`` is within ``tol_paise`` of the nearest tick multiple -> snap onto it
      (``snapped = True``); if it is further off -> leave ``raw`` as computed and report the
      distance (the caller flags and counts the day). ``off_paise`` is the pre-snap distance.
    """
    if k_cum <= 0:
        raise ValueError(f"k_cum must be positive, got {k_cum}")
    if k_cum == _ONE:
        return adjusted_paise, False, 0
    raw = int((Decimal(adjusted_paise) / k_cum).quantize(_ONE, rounding=ROUND_HALF_EVEN))
    if not tick_paise or tick_paise <= 0:
        return raw, False, 0
    nearest = _nearest_tick(raw, tick_paise)
    off = abs(raw - nearest)
    if off <= tol_paise:
        return nearest, True, off
    return raw, False, off


def unadjust_volume(adjusted_volume: int, k_cum: Decimal) -> int:
    """One volume: ``raw = adjusted x k_cum`` (Decimal, one half-even round to shares). PURE.

    The ruling's direction, exactly: a bonus/split back-adjustment scales volume by ``1/k`` (a
    1:1 bonus doubles a pre-ex volume), so recovering the raw share count multiplies BACK by
    ``k_cum``. ``k_cum == 1`` (recent day, or a window of only ordinary dividends/buybacks)
    returns the volume unchanged.
    """
    if k_cum <= 0:
        raise ValueError(f"k_cum must be positive, got {k_cum}")
    if k_cum == _ONE:
        return adjusted_volume
    return int((Decimal(adjusted_volume) * k_cum).quantize(_ONE, rounding=ROUND_HALF_EVEN))


def _nearest_tick(paise: int, tick_paise: int) -> int:
    """The nearest whole multiple of ``tick_paise`` to ``paise`` (half-even on the tie). PURE."""
    steps = (Decimal(paise) / Decimal(tick_paise)).quantize(_ONE, rounding=ROUND_HALF_EVEN)
    return int(steps) * tick_paise


def unadjust_bars(
    bars: Sequence[OneMinuteBar],
    *,
    factors: Iterable[Factor],
    fetch_date: date,
    symbol: str,
    tick_paise: int | None = None,
    tol_paise: int = DEFAULT_TICK_SNAP_TOLERANCE_PAISE,
    suppressions: Iterable[Suppression] = (),
    pending_ex_dates: Iterable[date] = (),
) -> UnadjustResult:
    """Un-adjust a fetched window of bars to RAW, per the Q-10 ruling. PURE.

    Groups the bars by trade date, computes one ``k_cum(D, F)`` per day (all of a day's bars
    share it), and rebuilds each :class:`~acumen.smartapi_client.OneMinuteBar` with raw prices
    (``/ k_cum``, tick-snapped) and raw volume (``x k_cum``). A day whose ``(D, F]`` window
    contains an event with NO factor -- a demerger Suppression or a Q-6-pending rights -- is
    marked UN-PROVABLE (``provable=False``): the partial un-adjustment is still applied so the
    day is stored and visible, but gate 1 will fail it and it is excluded and counted.

    Args:
        bars: the fetched (adjusted) bars, any span; may cross several trade dates.
        factors: the symbol's CONTEXT 4.2 factor table (bonus/split/rights/special-dividend;
            ordinary/buyback carry k=1 and drop out).
        fetch_date: F -- the date the window was fetched (k_cum is fetch-dated; the ledger
            records it so a future top-up un-adjusts with a refreshed CA table).
        symbol: the ticker (factors are filtered to it).
        tick_paise: the symbol's tick in paise (from the instrument master); enables tick-snap.
        suppressions: demerger + Q-6 tier-2 rights ex-dates (unknown factor -> un-provable).
        pending_ex_dates: rights ex-dates whose issue price is still pending (Q-6) -- also
            unknown-factor, also un-provable.
    """
    sym = symbol.strip().upper()
    supp_dates = sorted({s.ex_date for s in suppressions})
    pend_dates = sorted(set(pending_ex_dates))

    by_day: dict[date, list[OneMinuteBar]] = {}
    for bar in bars:
        by_day.setdefault(bar.stamp.date(), []).append(bar)

    raw_bars: list[OneMinuteBar] = []
    day_reports: list[DayUnadjust] = []
    for day in sorted(by_day):
        k_cum = cumulative_factor(factors, day, fetch_date, symbol=sym)
        unknown = _unknown_factor_between(day, fetch_date, supp_dates, pend_dates)
        snapped = 0
        flagged = 0
        off_max = 0
        for bar in by_day[day]:
            new_prices = []
            for value in (bar.open_paise, bar.high_paise, bar.low_paise, bar.close_paise):
                raw, did_snap, off = unadjust_price_paise(
                    value, k_cum, tick_paise=tick_paise, tol_paise=tol_paise
                )
                new_prices.append(raw)
                if did_snap:
                    snapped += 1
                elif off > tol_paise:
                    flagged += 1
                off_max = max(off_max, off)
            raw_bars.append(
                OneMinuteBar(
                    stamp=bar.stamp,
                    open_paise=new_prices[0],
                    high_paise=new_prices[1],
                    low_paise=new_prices[2],
                    close_paise=new_prices[3],
                    volume=unadjust_volume(bar.volume, k_cum),
                )
            )
        day_reports.append(
            DayUnadjust(
                day=day,
                fetch_date=fetch_date,
                k_cum=k_cum,
                identity=(k_cum == _ONE),
                provable=(unknown is None),
                snapped=snapped,
                tick_flagged=flagged,
                off_grid_max_paise=off_max,
                reason=_day_reason(k_cum, unknown, flagged),
            )
        )
    return UnadjustResult(raw_bars=tuple(raw_bars), days=tuple(day_reports))


def _unknown_factor_between(
    day: date, fetch_date: date, supp_dates: Sequence[date], pend_dates: Sequence[date]
) -> str | None:
    """A one-line reason if an unknown-factor event lies in ``(D, F]``, else ``None``. PURE."""
    hits = [d for d in supp_dates if day < d <= fetch_date]
    if hits:
        return f"suppression (demerger / tier-2 rights) ex {hits[0]} in (D, F]"
    hits = [d for d in pend_dates if day < d <= fetch_date]
    if hits:
        return f"Q-6-pending rights ex {hits[0]} in (D, F] (issue price unknown)"
    return None


def _day_reason(k_cum: Decimal, unknown: str | None, flagged: int) -> str:
    if unknown is not None:
        return f"UN-PROVABLE: {unknown}; gate 1 will exclude and count this day"
    if k_cum == _ONE:
        return "identity (k_cum = 1): stored exactly as fetched"
    note = f"un-adjusted by k_cum = {k_cum}"
    if flagged:
        note += f"; {flagged} price(s) > tolerance off the tick grid (flagged)"
    return note


def systematic_unprovable_floor(
    days: Iterable[DayUnadjust], *, min_run: int = 5
) -> date | None:
    """The ruling's surgical fallback: a new minute-clamp floor when a WHOLE pre-event span
    fails un-adjustment systematically. PURE.

    Returns the earliest provable day's date when the un-provable days form a contiguous
    *leading* block of at least ``min_run`` days (a pre-demerger span the vendor
    demerger-adjusts, which we cannot un-adjust). ``None`` when nothing is systematically
    un-provable (the normal case -- e.g. TCS, whose only factor is a bonus we hold). The
    caller discloses the restriction; the excluded days are still counted.
    """
    ordered = sorted(days, key=lambda d: d.day)
    leading_unprovable = 0
    for report in ordered:
        if report.provable:
            break
        leading_unprovable += 1
    if leading_unprovable < min_run:
        return None
    provable = [d.day for d in ordered if d.provable]
    return provable[0] if provable else None
