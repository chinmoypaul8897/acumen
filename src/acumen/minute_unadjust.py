"""Un-adjust SmartAPI 1-minute candles back to RAW on ingest (QUESTIONS.md Q-10). PURE.

OPEN-8 resolved ADJUSTED: SmartAPI's historical 1-minute feed is corporate-action
back-adjusted, so a candle on day ``D`` fetched on date ``F`` comes back at ``raw x k`` for
price, where the factors are the CONTEXT 4.2 factors of every event with ex-date in ``(D, F]``.
CONTEXT 7-E11 wants the intraday engines to run on RAW same-day prices; the architect's Q-10
ruling (option a, with a surgical fallback) is therefore to **un-adjust on ingest** and keep the
minute store RAW ONLY -- E11 stands unchanged.

The ruling's arithmetic, with the FIX-2 volume refinement, is what this module computes
(Decimal, one half-even rounding to paise/shares at the end):

    k_price    = product of ALL factors with ex-date in (D, F]            (bonus/split/rights/special-div)
    k_shares   = product of SHARE-COUNT factors with ex-date in (D, F]    (bonus/split/consolidation only)
    raw_price  = fetched_price  / k_price
    raw_volume = fetched_volume x k_shares

The two differ because a vendor rescales reported VOLUME only when the SHARE COUNT changes (a
bonus, a split, a consolidation), NOT for a cash-dividend PRICE adjustment: a special dividend
back-adjusts the pre-ex price (so it is in ``k_price``) but leaves the traded share count and
hence the volume untouched (so it is NOT in ``k_shares`` --
:data:`acumen.corp_actions.SHARE_COUNT_KINDS`). PRICE still uses every factor. For a symbol
whose only in-window factor is a bonus/split (e.g. TCS), ``k_price == k_shares`` and the volume
result is unchanged from the pre-FIX-2 behaviour -- the refinement only stops a special dividend
from spuriously over-correcting volume.

Each factor product is exactly a :func:`acumen.corp_actions.factors_between` window (the same
half-open ``(previous, current]`` the bias engine adjusts *with*), so the chunk-3 factor table
is the same one this un-adjusts *against* -- no new factor logic, only a kind filter for
``k_shares``. A recent day (after the symbol's last CA) has an empty factor window, so both
``k_price == 1`` and ``k_shares == 1`` and un-adjustment is the exact identity (the F10 2026
days, and every post-last-CA backtest window, are untouched).

Two guards ride along, both per the ruling:

* **Tick-snap.** A RAW price is a whole multiple of the symbol's tick; the vendor's rounding
  of ``raw x k`` to paise leaves the recovered ``raw = adjusted / k_price`` up to ~1 paise off
  that grid. So an un-adjusted price within :data:`DEFAULT_TICK_SNAP_TOLERANCE_PAISE` of the
  nearest tick is SNAPPED onto it (E11: "tick grid preserved"); one further off is left as the
  divided value and the day is FLAGGED and counted (vendor rounding beyond tolerance). The snap
  runs only when the price was actually divided (``k_price != 1``): an identity day is stored
  byte-for-byte as fetched, never re-gridded against a possibly-coarser *current* tick.
* **Provability.** Where an event in ``(D, F]`` is one the vendor adjusted the MINUTE feed by
  but for which we hold NO factor -- a Q-6 tier-2 unrecoverable rights (a Suppression) or a
  Q-6-pending rights -- day ``D`` cannot be un-adjusted. It is marked UN-PROVABLE: the partial
  un-adjustment is still applied, but gate 1 (volume reconciliation vs the raw bhavcopy) will
  fail it, so it is excluded and counted (CONTEXT 7-E3), and a systematically-failing pre-event
  span moves the symbol's minute clamp to post-event (:func:`systematic_unprovable_floor` --
  the ruling's surgical fallback).

  A **demerger** is the exception, per the Q-10 ADDENDUM 2 ruling: FIX-2's live RELIANCE probe
  proved the 1-MINUTE feed is NOT demerger-adjusted (unlike the ONE_DAY feed), so a demerger
  ex-date in ``(D, F]`` does NOT mark a minute day un-provable -- the pre-demerger span is
  un-adjusted by the symbol's OTHER events (bonus/split/rights) only and proved by gate 1 like
  any other span. Demergers never had a factor, so they were already absent from ``k_price`` and
  ``k_shares``; this only stops them marking the span un-provable (see
  :func:`unprovable_suppression_dates`). The demerger's DAILY bias-pair suppression (CONTEXT 3.2,
  :mod:`acumen.bias_engine`) is a SEPARATE rule and is unchanged.

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

from .corp_actions import (
    Factor,
    KIND_DEMERGER,
    SHARE_COUNT_KINDS,
    Suppression,
    factors_between,
)
from .smartapi_client import OneMinuteBar

#: The vendor rounds ``raw x k`` to paise, so the recovered ``raw = adjusted / k_price`` can sit
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
    k_price: Decimal  # product of ALL factors in (D, F]; divides the price
    k_shares: Decimal  # product of SHARE-COUNT factors in (D, F]; multiplies the volume (FIX-2)
    identity: bool  # k_price == k_shares == 1 -> stored exactly as fetched (a recent day)
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
    factors: Iterable[Factor],
    day: date,
    fetch_date: date,
    *,
    symbol: str | None = None,
    kinds: frozenset[str] | None = None,
) -> Decimal:
    """Product of ``factor.k`` for events with ex-date in ``(D, F]``. PURE.

    Exactly the window of :func:`acumen.corp_actions.factors_between` (half-open on the left),
    so a candle on ``day`` is un-adjusted against precisely the events the vendor back-adjusted
    it *by*. An empty window returns :data:`Decimal(1)` -- the identity, correct for a recent
    (post-last-CA) day where fetched already equals raw. ``ordinary`` dividends and buybacks
    carry ``k = 1`` in the factor table, so they drop out of the product harmlessly.

    ``kinds`` (FIX-2): when given, only factors whose ``.kind`` is in the set are multiplied.
    ``None`` (the default) multiplies EVERY factor -> ``k_price`` (used to divide the price).
    Passing :data:`acumen.corp_actions.SHARE_COUNT_KINDS` gives ``k_shares`` (bonus/split/
    consolidation only), which multiplies the volume: the vendor scales volume only for a
    share-count change, never for a cash-dividend price adjustment.
    """
    if fetch_date < day:
        raise ValueError(
            f"fetch_date {fetch_date} is before the candle day {day}: a candle cannot be "
            "fetched before it exists."
        )
    k = _ONE
    for factor in factors_between(factors, day, fetch_date, symbol=symbol):
        if kinds is None or factor.kind in kinds:
            k *= factor.k
    return k


def unadjust_price_paise(
    adjusted_paise: int,
    k_price: Decimal,
    *,
    tick_paise: int | None = None,
    tol_paise: int = DEFAULT_TICK_SNAP_TOLERANCE_PAISE,
) -> tuple[int, bool, int]:
    """One price: ``raw = adjusted / k_price`` (Decimal, one half-even round), tick-snap. PURE.

    ``k_price`` is the product of ALL factors in ``(D, F]`` (bonus/split/rights/special-div):
    the price is back-adjusted by every corporate action, so recovering it divides by all of
    them. Returns ``(raw_paise, snapped, off_paise)``:

    * ``k_price == 1`` -> the exact identity: ``adjusted`` returned unchanged, NOT re-gridded
      (a recent day is already raw and on the real tick grid; snapping it against a possibly
      coarser *current* tick could only corrupt it).
    * otherwise ``raw = round_half_even(adjusted / k_price)``. If a ``tick_paise`` grid is given
      and ``raw`` is within ``tol_paise`` of the nearest tick multiple -> snap onto it
      (``snapped = True``); if it is further off -> leave ``raw`` as computed and report the
      distance (the caller flags and counts the day). ``off_paise`` is the pre-snap distance.
    """
    if k_price <= 0:
        raise ValueError(f"k_price must be positive, got {k_price}")
    if k_price == _ONE:
        return adjusted_paise, False, 0
    raw = int((Decimal(adjusted_paise) / k_price).quantize(_ONE, rounding=ROUND_HALF_EVEN))
    if not tick_paise or tick_paise <= 0:
        return raw, False, 0
    nearest = _nearest_tick(raw, tick_paise)
    off = abs(raw - nearest)
    if off <= tol_paise:
        return nearest, True, off
    return raw, False, off


def unadjust_volume(adjusted_volume: int, k_shares: Decimal) -> int:
    """One volume: ``raw = adjusted x k_shares`` (Decimal, one half-even round to shares). PURE.

    ``k_shares`` (FIX-2) is the product of only the SHARE-COUNT factors in ``(D, F]`` --
    bonus/split/consolidation (:data:`acumen.corp_actions.SHARE_COUNT_KINDS`). The vendor
    rescales reported volume by ``1/k`` when the share count changes (a 1:1 bonus doubles a
    pre-ex volume), so recovering the raw share count multiplies BACK by ``k_shares``. A cash
    dividend (special or ordinary) is NOT a share-count change, so it never enters ``k_shares``
    -- that is the whole point of the split from ``k_price``. ``k_shares == 1`` (recent day, or
    a window whose only factors are dividends/buybacks) returns the volume unchanged.
    """
    if k_shares <= 0:
        raise ValueError(f"k_shares must be positive, got {k_shares}")
    if k_shares == _ONE:
        return adjusted_volume
    return int((Decimal(adjusted_volume) * k_shares).quantize(_ONE, rounding=ROUND_HALF_EVEN))


def _nearest_tick(paise: int, tick_paise: int) -> int:
    """The nearest whole multiple of ``tick_paise`` to ``paise`` (half-even on the tie). PURE."""
    steps = (Decimal(paise) / Decimal(tick_paise)).quantize(_ONE, rounding=ROUND_HALF_EVEN)
    return int(steps) * tick_paise


def unprovable_suppression_dates(suppressions: Iterable[Suppression]) -> list[date]:
    """The suppression ex-dates that make a MINUTE day un-provable, sorted. PURE.

    Q-10 ADDENDUM 2: a **demerger** suppression is EXCLUDED. FIX-2's live RELIANCE probe proved
    the vendor's 1-MINUTE feed is NOT demerger-adjusted (median un-adjusted ratio ~1.000, not the
    ~0.908 a demerger-adjusted feed would show), so a pre-demerger minute span is un-adjusted by
    the symbol's other events only and proved by gate 1 -- the demerger must not mark it
    un-provable. A Q-6 tier-2 unrecoverable rights suppression (``kind == KIND_RIGHTS``) is KEPT:
    the minute feed IS rights-adjusted (FIX-2 2b), but its factor is unknown, so those days
    genuinely cannot be un-adjusted. The demerger's DAILY bias-pair suppression (CONTEXT 3.2) is a
    SEPARATE rule and consumes the full suppression list unchanged (:mod:`acumen.bias_engine`).
    """
    return sorted({s.ex_date for s in suppressions if s.kind != KIND_DEMERGER})


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

    Groups the bars by trade date, computes ``k_price(D, F)`` and ``k_shares(D, F)`` per day
    (all of a day's bars share them), and rebuilds each
    :class:`~acumen.smartapi_client.OneMinuteBar` with raw prices (``/ k_price``, tick-snapped)
    and raw volume (``x k_shares`` -- FIX-2: share-count factors only). A day whose ``(D, F]``
    window contains an un-provable rights event -- a Q-6 tier-2 unrecoverable rights Suppression
    or a Q-6-pending rights -- is marked UN-PROVABLE (``provable=False``): the partial
    un-adjustment is still applied so the day is stored and visible, but gate 1 will fail it and
    it is excluded and counted. A **demerger** Suppression does NOT mark the day un-provable
    (Q-10 ADDENDUM 2: the 1-minute feed is not demerger-adjusted --
    :func:`unprovable_suppression_dates`).

    Args:
        bars: the fetched (adjusted) bars, any span; may cross several trade dates.
        factors: the symbol's CONTEXT 4.2 factor table (bonus/split/rights/special-dividend;
            ordinary/buyback carry k=1 and drop out).
        fetch_date: F -- the date the window was fetched (k_cum is fetch-dated; the ledger
            records it so a future top-up un-adjusts with a refreshed CA table).
        symbol: the ticker (factors are filtered to it).
        tick_paise: the symbol's tick in paise (from the instrument master); enables tick-snap.
        suppressions: the symbol's suppression list (demergers + Q-6 tier-2 rights). Only the
            tier-2 rights mark a day un-provable; demergers are filtered out
            (:func:`unprovable_suppression_dates`, Q-10 ADDENDUM 2). The full list is still
            consumed unchanged by the daily bias engine's separate CONTEXT 3.2 suppression.
        pending_ex_dates: rights ex-dates whose issue price is still pending (Q-6) -- also
            unknown-factor, also un-provable.
    """
    sym = symbol.strip().upper()
    supp_dates = unprovable_suppression_dates(suppressions)
    pend_dates = sorted(set(pending_ex_dates))

    by_day: dict[date, list[OneMinuteBar]] = {}
    for bar in bars:
        by_day.setdefault(bar.stamp.date(), []).append(bar)

    raw_bars: list[OneMinuteBar] = []
    day_reports: list[DayUnadjust] = []
    for day in sorted(by_day):
        k_price = cumulative_factor(factors, day, fetch_date, symbol=sym)
        k_shares = cumulative_factor(
            factors, day, fetch_date, symbol=sym, kinds=SHARE_COUNT_KINDS
        )
        unknown = _unknown_factor_between(day, fetch_date, supp_dates, pend_dates)
        snapped = 0
        flagged = 0
        off_max = 0
        for bar in by_day[day]:
            new_prices = []
            for value in (bar.open_paise, bar.high_paise, bar.low_paise, bar.close_paise):
                raw, did_snap, off = unadjust_price_paise(
                    value, k_price, tick_paise=tick_paise, tol_paise=tol_paise
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
                    volume=unadjust_volume(bar.volume, k_shares),
                )
            )
        day_reports.append(
            DayUnadjust(
                day=day,
                fetch_date=fetch_date,
                k_price=k_price,
                k_shares=k_shares,
                identity=(k_price == _ONE and k_shares == _ONE),
                provable=(unknown is None),
                snapped=snapped,
                tick_flagged=flagged,
                off_grid_max_paise=off_max,
                reason=_day_reason(k_price, k_shares, unknown, flagged),
            )
        )
    return UnadjustResult(raw_bars=tuple(raw_bars), days=tuple(day_reports))


def _unknown_factor_between(
    day: date, fetch_date: date, supp_dates: Sequence[date], pend_dates: Sequence[date]
) -> str | None:
    """A one-line reason if an unknown-factor event lies in ``(D, F]``, else ``None``. PURE.

    ``supp_dates`` must already have demergers filtered out (:func:`unprovable_suppression_dates`,
    Q-10 ADDENDUM 2), so the only suppression reaching here is a Q-6 tier-2 unrecoverable rights.
    """
    hits = [d for d in supp_dates if day < d <= fetch_date]
    if hits:
        return f"suppression (tier-2 unrecoverable rights) ex {hits[0]} in (D, F]"
    hits = [d for d in pend_dates if day < d <= fetch_date]
    if hits:
        return f"Q-6-pending rights ex {hits[0]} in (D, F] (issue price unknown)"
    return None


def _day_reason(k_price: Decimal, k_shares: Decimal, unknown: str | None, flagged: int) -> str:
    if unknown is not None:
        return f"UN-PROVABLE: {unknown}; gate 1 will exclude and count this day"
    if k_price == _ONE and k_shares == _ONE:
        return "identity (k_price = k_shares = 1): stored exactly as fetched"
    note = f"un-adjusted: price / k_price={k_price}, volume x k_shares={k_shares}"
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
