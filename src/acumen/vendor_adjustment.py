"""Reconstruct the vendor's per-event minute adjustment by MEASUREMENT (QUESTIONS.md Q-11).

FIX-2/FIX-3 tried to GUESS a single policy for how SmartAPI back-adjusts its historical
1-minute feed (first "not demerger-adjusted", then "demerger-adjusted"). The live RELIANCE
re-runs proved BOTH guesses wrong: the vendor's adjustment stack is **era-inconsistent** --
the 2023-07-20 Jio demerger is baked into 2022/2023-06 pre-ex minute bars (~0.908) but NOT into
2016/2019 ones, and the 2020 rights was scaled in both price AND volume by a vendor factor
(~0.9873/~0.9877) that differs from our CONTEXT 4.2 TERP (0.99061). No fixed rule un-adjusts
RELIANCE correctly.

The architect's Q-11 ruling replaces rule-guessing with per-event MEASUREMENT.

**The observable.** For a fetched day ``D`` (fetch date ``F``),
``R(D) = fetched_price(D) / raw_daily(D)`` is exactly the product of the vendor's actually-applied
price factors for the corporate actions with ex-date in ``(D, F]``. It is measured directly: fold
the fetched 1-minute day into a daily OHLC and ratio its HIGH and LOW (the exact multiples -- the
close carries intraday-vs-official-close noise) against the RAW daily store (chunk 2). Volume has
its own observable ``Rv(D) = raw_daily_vol(D) / fetched_vol(D)`` -- the reciprocal, because a
vendor SCALES reported volume up by ``1/k`` when it scales price down by ``k`` (a 1:1 bonus halves
price and doubles volume), so the pre-ex volume is recovered by MULTIPLYING by ``k``.

**Eras.** Days sharing the same in-window event set ``{E : D < E.ex_date <= F}`` form an ERA; on
every day of an era the cumulative factor is the same, so ``R`` is measured once per era as the
MEDIAN over that era's pre-ex probe days (residuals recorded). This is measurement of an
observable, never free fitting.

**The candidate set + arbitration.** Working BACKWARDS from ``F`` one era at a time, each older era
adds exactly one older event. For PRICE and (independently) for VOLUME, each in-era event's factor
is chosen from ``{ours, measured k-hat, not-applied=1}`` and arbitrated by the raw-daily oracle:

* PRICE -- every probe day's un-adjusted HIGH and LOW must land within
  :data:`DEFAULT_PRICE_CONTAINMENT_PAISE` of the RAW daily high/low.
* VOLUME -- every probe day's un-adjusted volume must reconcile to the RAW daily volume inside
  gate-1's band ``[-0.1%, +5.0%]`` (:func:`acumen.quality_gates.volume_gate`; the -0.1% floor is
  NOT widened -- the ruling is explicit). The band's positive skew absorbs the pre-open
  call-auction volume the daily total counts but continuous 1-min candles do not.

Selection is MIN-COST -- ``ours`` (an exact known factor) is preferred over ``not-applied`` (the
vendor omitted the event) over ``measured`` (the vendor used a factor we had to observe). An
event's source is decided at its NEWEST appearance and carried into older eras; only a no-``ours``
event (a demerger) may FLIP between its measured value and not-applied across eras -- the exact
era-inconsistency the ruling names. At most ONE freshly-solved measured unknown is permitted per
era per pass, so a ``measured`` value is always a single observed scalar, never a curve fit.

**The map.** :class:`AdjustmentMap` is committed per symbol: one :class:`EraResolution` per era,
each carrying its per-event :class:`EventChoice` (kind, ex-date, price/volume factor and source),
the measured cumulative, the containment residual, the gate-1 gap and the probe windows. It is
persisted under ``data/adjustment_maps/<SYMBOL>.json`` (a gitignored store artifact) and printed
into the evidence pack. Deterministic: the same fetched inputs produce the same map.

**Consumption.** :func:`unadjust_with_map` replaces the FIX-3 factor-table un-adjustment: for a day
``D`` it finds the era covering ``D``, forms ``k_price``/``k_volume`` from the chosen per-event
factors and divides/scales with the same :mod:`acumen.minute_unadjust` Decimal + single-half-even +
tick-snap primitives. A day whose era is NOT in the map (an unprobed span) or whose events found no
fitting candidate is UN-PROVABLE -> gate 1 excludes and counts it (CONTEXT 7-E3, surgical clamp);
gate 1 stays the per-day proof.

The MEASUREMENT + arbitration + consumption are all PURE (Decimal, no I/O). Only the thin
``measure_*`` / ``persist_*`` / ``load_map`` wrappers touch the network, the daily store, or disk,
and they are opt-in exactly like every other fetch in this repo.

Prices are integer paise (CONTEXT 7-E11); volume is shares. Source files in this package are
ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, time
from decimal import ROUND_HALF_EVEN, Decimal
from itertools import product
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from .atomic_io import atomic_write_text
from .corp_actions import (
    KIND_BONUS,
    KIND_DIVIDEND,
    KIND_RIGHTS,
    KIND_SPLIT,
    Factor,
    Suppression,
)
from .minute_unadjust import (
    DEFAULT_TICK_SNAP_TOLERANCE_PAISE,
    DayUnadjust,
    UnadjustResult,
    unadjust_price_paise,
    unadjust_volume,
)
from .quality_gates import (
    PRICE_CONTAINMENT_MIN_PAISE,
    PRICE_CONTAINMENT_REL,
    price_containment_gate,
    price_containment_limit,
    volume_gate,
)
from .smartapi_client import INTERVAL_ONE_MINUTE, OneMinuteBar

#: How close an un-adjusted HIGH/LOW must sit to the raw daily value to be "contained". The
#: ruling's "within 2 paise (scaled)": the vendor's cumulative rounding of a multi-factor chain
#: leaves the recovered raw price a hair off, and the measured factor is the median over an era's
#: probe days, so a specific day sits within the per-day spread of that median. Two paise covers
#: it while remaining three orders of magnitude below the ~0.3% rights and ~9% demerger errors a
#: WRONG factor leaves -- so the arbitration choice is never close (a wrong candidate misses by
#: hundreds of paise).
#:
#: SINGLE-SOURCED from :mod:`acumen.quality_gates` (the Q-14 ruling puts the same tolerance in the
#: per-day gate battery, and two copies of one constant is exactly how the two would drift apart).
DEFAULT_PRICE_CONTAINMENT_PAISE: int = PRICE_CONTAINMENT_MIN_PAISE

#: Relative floor for price containment: a day is contained within max(2 paise, this x raw). 0.1%
#: absorbs market microstructure (fold-vs-daily-high divergence, ~0.01%) while staying well below
#: the smallest WRONG-factor residual (the rights ours-vs-vendor gap, ~0.33%) -- so a wrong factor
#: or a bimodal era still fails on the offending day. See :func:`_price_contained`.
#: Also single-sourced from :mod:`acumen.quality_gates` (gate 1P's own tolerance).
_PRICE_CONTAINMENT_REL: Decimal = PRICE_CONTAINMENT_REL

SOURCE_OURS: str = "ours"  # our CONTEXT 4.2 factor -- an exact known multiplier
SOURCE_MEASURED: str = "measured"  # the vendor's factor, measured from the fetched/raw ratio
SOURCE_ABSENT: str = "absent"  # the vendor did not apply this event in this era (factor 1.0)

#: Q-11 ADDENDUM 3 clause (ii) pseudo-kind: a corporate-action subject the CONTEXT 4.2 parser
#: could not classify. It needs no parsing to enter the map -- it participates with candidates
#: ``{measured, absent}`` only (there is no ``ours`` for something unparsed) and is arbitrated by
#: the same oracle as every other event. So an unparsed subject can no longer BLOCK a map: it is
#: measured or absent.
KIND_UNPARSED: str = "unparsed"
#: VOLUME side only (Q-12 ruling clause ii): the factor the PRICE oracle already proved for this
#: same event, reused as a volume candidate. A rights or demerger has no ``ours`` volume factor at
#: all -- the vendor scaled volume by something that is not our TERP -- but its price factor is
#: pinned to 2 paise per probe day, so it is the best-evidenced volume candidate available.
SOURCE_PRICE_FACTOR: str = "price-factor"

#: Q-12 ruling clause (i): the measured VOLUME estimator needs at least this many probe days whose
#: PRICE containment passes. Fewer is not a measurement of a one-directionally contaminated
#: observable, so NO measured-volume candidate is offered at all and the era stands or falls on
#: ``ours`` / the chosen price factor / absent.
MIN_VOLUME_ESTIMATOR_DAYS: int = 3

#: Identity of the volume estimator a persisted map was built with. Stamped into the map JSON so a
#: map written under the SUPERSEDED median estimator (Q-11 as originally ruled) is detectable as
#: stale and rebuilt, rather than silently consumed. Bump this string whenever the estimator or the
#: volume candidate set changes.
MAP_VOLUME_ESTIMATOR: str = "min-over-price-passing-days-v2"

#: Identity of the MAP MODEL a persisted map was built under. A map written before the FIX-3
#: rulings has no compound/unparsed nodes and no floor field at all, so its era keys can differ
#: from the ones this builder would produce -- it must be REBUILT (probe windows only; no stored
#: candle is refetched), never consumed. Bump this whenever the node model or the chain model
#: changes; :func:`map_is_current` makes the rebuild automatic and auditable. v4: the builder is
#: FLOOR-AWARE (Q-11 addendum 4 -- a floored event is forced absent in the eras it does not reach)
#: and probe days are restricted to TRADING sessions (the Q-5 ruling), so a map measured under v3
#: can carry an era whose factor was measured on a weekend session the spec excludes.
MAP_MODEL: str = "floor-aware-build+trading-day-probes-v4"

_ONE: Decimal = Decimal(1)
#: Ratio tolerance for calling a solved/measured value "actually ours" or "actually absent".
#: 5e-4 is far tighter than the smallest real discrepancy (the rights, ~1.3% off ours) yet loose
#: enough to absorb the vendor's per-paise rounding on a large price.
_RATIO_TOL: Decimal = Decimal("0.0005")
#: A measured price/volume factor for anything but a reverse-split must be a discount (<= 1). This
#: rejects the confounded ratio (e.g. a rights "measured" at 1.087 when a demerger-era boundary was
#: crossed) rather than committing an economically impossible multiplier.
_MEASURED_UPPER: Decimal = _ONE + _RATIO_TOL

#: Cost of each source in the PRICE min-cost arbitration: prefer a known exact factor, then a
#: vendor omission, then a measured observation. UNCHANGED by Q-12 (the price observable is
#: symmetric and unbiased, so nothing about the price side moved).
_COST = {SOURCE_OURS: 0, SOURCE_ABSENT: 1, SOURCE_MEASURED: 2}

#: Cost of each source in the VOLUME min-cost arbitration, exactly the Q-12 ruling's order:
#: ``ours(share-count) > chosen-price-factor > measured-minimum > absent``. ``absent`` moved from
#: second to LAST on this side only. It can never demote a share-count event or a cash dividend
#: (both carry a cost-0 volume ``ours``), so the reordering only ever decides an event with NO
#: volume ``ours`` -- a rights, a demerger, a Q-6-pending rights -- which is the ruling's target.
_VOLUME_COST = {SOURCE_OURS: 0, SOURCE_PRICE_FACTOR: 1, SOURCE_MEASURED: 2, SOURCE_ABSENT: 3}


class VendorAdjustmentError(RuntimeError):
    """The adjustment map cannot be built, read, or consumed."""


# --- events feeding the builder --------------------------------------------------------


@dataclass(frozen=True)
class EventComponent:
    """One raw corporate action feeding a map node, before same-ex-date composition. PURE data."""

    kind: str
    our_price_factor: Decimal | None
    is_share_count: bool

    def our_volume_factor(self) -> Decimal | None:
        """This component's clean ``ours`` VOLUME multiplier, or ``None`` when there is none."""
        if self.is_share_count:
            return self.our_price_factor
        if self.kind == KIND_DIVIDEND:
            return _ONE  # a cash dividend moves the price, never the share count
        return None


@dataclass(frozen=True)
class EventSpec:
    """One map NODE: every price-moving corporate action sharing one ex-date, composed.

    ``our_price_factor`` is our CONTEXT 4.2 multiplier, or ``None`` for a demerger / a rights whose
    issue price we could not recover (Q-6 tier 2) / an unparsed subject -- for those the vendor's
    factor is only ever an observation. ``is_share_count`` (a bonus/split/consolidation) means the
    vendor scales VOLUME by the same factor; a special dividend scales price but not volume, so its
    volume ``ours`` is 1.0.

    **Q-11 ADDENDUM 3 clause (i) -- the compound node.** Two corporate actions can share an ex-date
    (BAJAJFINSV: a 1:1 bonus AND a 5->1 face-value split, both ex 2022-09-13), and then only their
    PRODUCT describes the price step. The map keys eras by ex-date and cannot represent two nodes on
    one date, so same-ex-date events COMPOSE into one node: ``k`` is the product, the share-count
    flags combine, and the candidate set is arbitrated against the compound exactly as against a
    single event. ``component_kinds`` keeps the parts visible in the audit row.

    ``our_volume_factor_value`` carries a compound's own volume ``ours`` -- the product over
    components of the share-count factor, 1.0 for a cash dividend, ``None`` for anything whose
    volume scaling we cannot know. ``None`` here means "derive it the single-event way", which is
    what every non-compound node does.
    """

    kind: str
    ex_date: date
    our_price_factor: Decimal | None
    is_share_count: bool
    #: A COMPOUND node's own volume ``ours``; ``None`` -> derive per the single-event rule.
    our_volume_factor_value: Decimal | None = None
    #: The component kinds this node composes (length > 1 only for a compound node).
    component_kinds: tuple[str, ...] = ()

    @property
    def is_compound(self) -> bool:
        return len(self.component_kinds) > 1

    def our_volume_factor(self) -> Decimal | None:
        """The clean ``ours`` VOLUME candidate: the price factor for a share-count event, 1.0 for a
        cash dividend (volume never scales for it), else ``None`` (a rights/demerger/unparsed volume
        factor is only ever measured -- the vendor scaled it by a value that is not our TERP)."""
        if self.our_volume_factor_value is not None:
            return self.our_volume_factor_value
        if self.is_share_count:
            return self.our_price_factor
        if self.kind == KIND_DIVIDEND:
            return _ONE
        return None


def compose_event(ex_date: date, components: Sequence[EventComponent]) -> EventSpec:
    """Compose every event sharing ``ex_date`` into ONE map node (Q-11 addendum 3, clause i). PURE.

    ``k = product`` on both sides, share-count flags combined:

    * **price** -- the product of the components' CONTEXT 4.2 factors, or ``None`` if ANY component
      has none (a demerger, an unrecoverable rights or an unparsed subject makes the whole product
      unknown, and the node then has no ``ours`` at all -- which is exactly right, because we cannot
      claim to know a step we can only observe);
    * **volume** -- the product of the components' volume ``ours`` (the share-count factor, 1.0 for
      a cash dividend), or ``None`` if any component has none. So a bonus + special dividend has a
      price ``ours`` of ``k_bonus x k_div`` and a volume ``ours`` of ``k_bonus`` alone;
    * **share-count** -- the node is share-count only when EVERY component is, so a mixed node never
      claims the clean "volume scales with price" identity.

    A single-component date composes to exactly the node the pre-compound builder produced, so
    nothing about a symbol without same-date events moves.
    """
    if not components:
        raise VendorAdjustmentError(f"no component events to compose at {ex_date}")
    if len(components) == 1:
        one = components[0]
        return EventSpec(
            kind=one.kind,
            ex_date=ex_date,
            our_price_factor=one.our_price_factor,
            is_share_count=one.is_share_count,
            component_kinds=(one.kind,),
        )
    price: Decimal | None = _ONE
    volume: Decimal | None = _ONE
    for component in components:
        if price is not None:
            price = None if component.our_price_factor is None else price * component.our_price_factor
        if volume is not None:
            one_volume = component.our_volume_factor()
            volume = None if one_volume is None else volume * one_volume
    kinds = tuple(component.kind for component in components)
    return EventSpec(
        kind="+".join(sorted(set(kinds))),
        ex_date=ex_date,
        our_price_factor=price,
        is_share_count=all(component.is_share_count for component in components),
        our_volume_factor_value=volume,
        component_kinds=kinds,
    )


def events_from_factor_table(
    factors: Iterable[Factor],
    suppressions: Iterable[Suppression] = (),
    pending_ex_dates: Iterable[date] = (),
    *,
    symbol: str | None = None,
    unparsed_ex_dates: Iterable[date] = (),
) -> tuple[EventSpec, ...]:
    """Build the price-moving map NODES from a chunk-3 factor table. PURE.

    Only events that MOVE a price or volume enter an era key: factors with ``k != 1`` (bonus,
    split, rights, special dividend), plus demergers and unrecoverable/pending rights (which carry
    no factor but the vendor may have adjusted by), plus -- Q-11 addendum 3 clause (ii) -- every
    UNPARSED subject on the symbol. Ordinary dividends (``k == 1``) are dropped: they neither move
    a price nor fragment an era.

    Everything sharing an ex-date is COMPOSED into one node (:func:`compose_event`, clause i), so
    the returned nodes carry DISTINCT ex-dates by construction and the map's ex-date keying is
    always representable.

    Args:
        unparsed_ex_dates: ex-dates of subjects the CONTEXT 4.2 parser could not classify on this
            symbol (``ParseException``). They enter as :data:`KIND_UNPARSED` components with no
            factor, so their candidate list is ``{measured, absent}`` -- never ``ours``. An
            unparsed subject that carries no price move resolves to ``absent`` (cost 1, below
            ``measured``'s 2) and changes no chain; one that does carry a price move is measured
            against the daily oracle like any other. Either way it never blocks the map.
    """
    wanted = None if symbol is None else symbol.strip().upper()
    by_ex: dict[date, list[EventComponent]] = {}
    for f in factors:
        if wanted is not None and f.symbol != wanted:
            continue
        if f.k == _ONE:
            continue
        by_ex.setdefault(f.ex_date, []).append(
            EventComponent(
                kind=f.kind,
                our_price_factor=f.k,
                is_share_count=f.kind in (KIND_BONUS, KIND_SPLIT),
            )
        )
    for s in suppressions:
        if wanted is not None and s.symbol != wanted:
            continue
        by_ex.setdefault(s.ex_date, []).append(
            EventComponent(kind=s.kind, our_price_factor=None, is_share_count=False)
        )
    for ex in pending_ex_dates:
        by_ex.setdefault(ex, []).append(
            EventComponent(kind=KIND_RIGHTS, our_price_factor=None, is_share_count=False)
        )
    for ex in unparsed_ex_dates:
        components = by_ex.setdefault(ex, [])
        # One unparsed component per date is enough: a second unparsed subject on the same day adds
        # no new unknown (the node already carries a single measured-or-absent scalar), and adding
        # it would only duplicate the label in the audit row.
        if not any(c.kind == KIND_UNPARSED for c in components):
            components.append(
                EventComponent(kind=KIND_UNPARSED, our_price_factor=None, is_share_count=False)
            )
    return tuple(compose_event(ex, sorted(components, key=lambda c: c.kind))
                 for ex, components in sorted(by_ex.items()))


# --- probe measurements ----------------------------------------------------------------


@dataclass(frozen=True)
class ProbeDay:
    """One pre-ex probe day: the fetched 1-minute daily-fold vs the RAW daily store. PURE data."""

    day: date
    fetched_high: int
    fetched_low: int
    fetched_close: int
    fetched_volume: int
    raw_high: int
    raw_low: int
    raw_close: int
    raw_volume: int

    def price_ratios(self) -> tuple[Decimal, Decimal]:
        """``fetched / raw`` for HIGH and LOW -- the exact multiples (not the noisy close)."""
        return (
            Decimal(self.fetched_high) / Decimal(self.raw_high),
            Decimal(self.fetched_low) / Decimal(self.raw_low),
        )

    def volume_recovery(self) -> Decimal:
        """``raw / fetched`` volume -- the multiplier that recovers the raw share count."""
        return Decimal(self.raw_volume) / Decimal(self.fetched_volume)


@dataclass(frozen=True)
class EraMeasurement:
    """The measured cumulative ratios for one era, from its pre-ex probe days. PURE data.

    ``ex_dates`` is the era KEY: the sorted ex-dates of the price-moving events in ``(D, F]`` for
    every day of this era. ``price_cumulative`` is the median of the probe days' high/low ratios
    (``fetched/raw``) -- the ruled estimator, unchanged: that observable is the same number every
    day, so the median is unbiased. The spreads record how tight the observation is.

    ``volume_cumulative`` (the median of ``raw/fetched`` volume) is **DIAGNOSTIC ONLY** since the
    Q-12 ruling: the volume observable is one-sidedly contaminated by the pre-open call auction
    (``measured = true / (1 - auction)`` >= ``true``), so its median is biased HIGH and the
    committed estimator is :func:`volume_estimator` -- the MINIMUM over the probe days whose PRICE
    containment passes. The median is kept because the report and the audit want to SEE the bias
    that the ruling corrects; nothing consumes it as a factor.
    """

    ex_dates: tuple[date, ...]
    label: str
    probe_days: tuple[ProbeDay, ...]
    price_cumulative: Decimal
    volume_cumulative: Decimal
    price_spread: Decimal
    volume_spread: Decimal


def measure_era(ex_dates: Sequence[date], label: str, probe_days: Sequence[ProbeDay]) -> EraMeasurement:
    """Fold a set of probe days into one :class:`EraMeasurement`. PURE.

    Degenerate probe days -- a zero (or negative) fetched/raw volume or price -- are DROPPED: a
    halted or vendor-flat-filled day carries no ratio, and ``raw/fetched`` / ``fetched/raw`` would
    divide by zero. If that leaves no usable day the era cannot be measured and this raises (the
    caller marks the era un-provable). The dropped days are still un-adjusted at consumption by the
    era's factor and caught by gate 1 downstream.
    """
    if not probe_days:
        raise VendorAdjustmentError(f"era {label!r} has no probe days to measure")
    usable = [
        p for p in probe_days
        if p.fetched_volume > 0 and p.raw_volume > 0
        and p.fetched_high > 0 and p.fetched_low > 0 and p.raw_high > 0 and p.raw_low > 0
    ]
    if not usable:
        raise VendorAdjustmentError(
            f"era {label!r}: every probe day had a zero/negative volume or price; cannot measure"
        )
    price_ratios: list[Decimal] = []
    for p in usable:
        price_ratios.extend(p.price_ratios())
    vol_ratios = [p.volume_recovery() for p in usable]
    return EraMeasurement(
        ex_dates=tuple(sorted(ex_dates)),
        label=label,
        probe_days=tuple(usable),
        price_cumulative=_median(price_ratios),
        volume_cumulative=_median(vol_ratios),
        price_spread=(max(price_ratios) - min(price_ratios)),
        volume_spread=(max(vol_ratios) - min(vol_ratios)),
    )


def _median(values: Sequence[Decimal]) -> Decimal:
    """The median (average of the two middle values for an even count). Deterministic, exact."""
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal(2)


def price_passing_probe_days(
    era: EraMeasurement, k_price: Decimal, tol_paise: int = DEFAULT_PRICE_CONTAINMENT_PAISE
) -> tuple[ProbeDay, ...]:
    """The era's probe days whose un-adjusted high AND low land inside price containment. PURE.

    The Q-12 ruling restricts the volume estimator to "days whose PRICE containment passes". This
    is that filter, evaluated per day against the era's CHOSEN ``k_price`` -- the same arithmetic
    :func:`_price_contained` applies to the whole era, one day at a time. A day the price oracle
    rejects carries a confounded ratio (a vendor re-adjustment floor inside the era, a corrupt
    fold) and must never be allowed to set the volume floor.
    """
    return tuple(p for p in era.probe_days if _day_price_contained(p, k_price, tol_paise))


def volume_estimator(
    era: EraMeasurement,
    k_price: Decimal,
    *,
    tol_paise: int = DEFAULT_PRICE_CONTAINMENT_PAISE,
    min_days: int = MIN_VOLUME_ESTIMATOR_DAYS,
) -> Decimal | None:
    """The Q-12 measured VOLUME estimator: the MINIMUM of ``raw/fetched`` over price-passing days.

    PURE. Returns ``None`` -- i.e. **no measured-volume candidate exists** -- when fewer than
    ``min_days`` of the era's probe days pass price containment under ``k_price``.

    Why the minimum and not the ruled-for-price median: the 1-minute sum systematically UNDER-counts
    the exchange's daily total, because the pre-open call auction trades in neither the continuous
    session nor a 1-minute candle. So every day's observable is ``true / (1 - auction_share)``,
    which is >= the true factor, never below it -- a one-directional contamination, and exactly the
    asymmetry gate 1's own ``[-0.1%, +5.0%]`` band models. The median therefore lands roughly half
    the probe days BELOW the committed factor, each producing a NEGATIVE gap the un-widened -0.1%
    floor rejects, which marked eras un-provable that a single exact factor reconciles (ABB:
    median 0.8986 vs the true 0.8976). The observable's FLOOR is the unbiased point. It is also
    conservative in the safe direction: an estimator slightly BELOW truth un-adjusts volume slightly
    low, which pushes gate-1 gaps POSITIVE, into the band's wide side.
    """
    if k_price <= 0:
        return None
    days = price_passing_probe_days(era, k_price, tol_paise)
    if len(days) < min_days:
        return None
    return min(p.volume_recovery() for p in days)


# --- the resolved map ------------------------------------------------------------------


@dataclass(frozen=True)
class EventChoice:
    """One event's resolved factor + source, for one era (an audit row)."""

    kind: str
    ex_date: date
    price_factor: Decimal
    price_source: str
    volume_factor: Decimal
    volume_source: str


@dataclass(frozen=True)
class EraResolution:
    """One era's fully-resolved chain plus its oracle diagnostics."""

    label: str
    ex_dates: tuple[date, ...]
    choices: tuple[EventChoice, ...]
    k_price: Decimal
    k_volume: Decimal
    price_containment_paise: int
    volume_gap_pct: Decimal | None
    provable: bool
    probe_days: tuple[date, ...]
    note: str


# --- vendor APPLICATION FLOORS (Q-11 addendum 2) ---------------------------------------

#: The classifier's three verdicts for one probed day, against one event.
FLOOR_IN: str = "event-in"  # the day's fetched bars DO carry this event's adjustment
FLOOR_OUT: str = "event-out"  # they do NOT -- the day sits below the vendor's splice
FLOOR_UNDECIDED: str = "undecided"  # neither hypothesis contains, or both do

#: Probe budget for ONE event's floor search. A binary search over ~2,400 trading days needs
#: ceil(log2(2400)) + 2 endpoint probes = ~13; the ruling's estimate is "~11 probes per event".
#: 16 leaves room for a couple of undecided midpoints without ever becoming an open-ended sweep.
MAX_FLOOR_PROBES: int = 16

#: How many neighbours an UNDECIDED midpoint may step to before the search gives up UNRESOLVED.
#: A damaged single day must not sink a search; a run of them means the floor model does not fit
#: there, and guessing is worse than "un-provable" (CLAUDE.md rule 1).
MAX_UNDECIDED_STEPS: int = 2


@dataclass(frozen=True)
class FloorProbe:
    """One day of a floor binary search: what was asked, and what the daily oracle answered."""

    day: date
    verdict: str
    k_in: Decimal | None = None
    k_out: Decimal | None = None
    #: ``fetched/raw`` for HIGH and LOW on this day -- the observable the verdict was read from.
    ratio_high: Decimal | None = None
    ratio_low: Decimal | None = None


@dataclass(frozen=True)
class EventFloor:
    """One event's measured vendor APPLICATION FLOOR: the splice date its adjustment starts at.

    The architect's Q-11 addendum-2 ruling: the vendor's back-adjustments have per-event
    application floors -- internal splice dates before which the event was never applied to its
    archive. ``floor_date`` is that date, binary-searched with daily-oracle probes; **for days
    strictly before it the event is ABSENT from that day's chain**.

    ``floor_date is None`` with ``resolved`` True means the event is applied on every day of the
    searched span (no splice inside our history) -- the chain is unchanged. ``resolved`` False means
    the search could not pin a boundary; the chain is likewise unchanged, and the days stay whatever
    gate 1 makes of them. Nothing is ever guessed: an unresolved search leaves the map exactly as it
    was, which is the ruling's own "un-provable remains the honest fallback where no floor fits".
    """

    ex_date: date
    floor_date: date | None
    resolved: bool
    probes: tuple[FloorProbe, ...] = ()
    note: str = ""
    #: The event's PRICE factor the probes were classified under -- provenance the Q-11 addendum-4
    #: ruling asks be committed, and what :func:`carry_floors_forward` re-validates a carry against.
    #: ``None`` on a floor measured before FIX-4 (the carry then falls back to the previous map's own
    #: canonical factor, exactly as it did then).
    event_price_factor: Decimal | None = None
    # --- the VOLUME side (QUESTIONS.md Q-14: per-side vendor splices) ----------------------
    #: The Q-14 ruling: "the mechanism is per-side vendor splices -- price and volume applied back
    #: to DIFFERENT dates for the same event. The floor model gains per-side floors (floor_price,
    #: floor_volume per event)". ``floor_date`` above IS the price side (:attr:`floor_price` names
    #: it); this is the volume side, measured by its own run of the same bisection against gate 1's
    #: own band. ``volume_measured`` False means the volume side was never searched -- which is the
    #: state of every floor committed before this ruling -- and then the volume chain follows the
    #: PRICE floor exactly as it did before, so no committed map changes behaviour.
    floor_volume: date | None = None
    volume_resolved: bool = False
    volume_measured: bool = False
    volume_probes: tuple[FloorProbe, ...] = ()
    volume_note: str = ""
    event_volume_factor: Decimal | None = None

    @property
    def floor_price(self) -> date | None:
        """The PRICE-side splice date -- the Q-14 ruling's own name for ``floor_date``. PURE."""
        return self.floor_date

    def applies_on(self, day: date) -> bool:
        """Did the vendor apply this event's PRICE adjustment to a bar stamped ``day``? PURE."""
        if self.floor_date is None:
            return True
        return day >= self.floor_date

    def applies_on_volume(self, day: date) -> bool:
        """Did the vendor apply this event's VOLUME adjustment to a bar stamped ``day``? PURE.

        Falls back to the PRICE side when the volume side was never measured, so a floor committed
        before the Q-14 ruling answers exactly as it did then (one floor, both chains).
        """
        if not self.volume_measured:
            return self.applies_on(day)
        if self.floor_volume is None:
            return True
        return day >= self.floor_volume

    @property
    def absent_throughout(self) -> bool:
        """Is the PRICE floor at or above the ex-date -- absent from EVERY chain we can form? PURE.

        A chain only ever contains events with ``day < ex_date``, so a floor at the ex-date means the
        vendor's back-adjustment never reached one day of our history (Q-11 addendum 4).
        """
        return self.floor_date is not None and self.floor_date >= self.ex_date

    @property
    def per_side(self) -> bool:
        """Do the two sides genuinely differ -- the Q-14 mechanism, measured? PURE."""
        return self.volume_measured and self.floor_volume != self.floor_date


def classify_floor_day(
    probe: ProbeDay, k_in: Decimal, k_out: Decimal, tol_paise: int = DEFAULT_PRICE_CONTAINMENT_PAISE
) -> str:
    """Does ``probe``'s day fit with the event IN the chain, or OUT of it? PURE.

    The ruling's "day fits with event-in vs event-out", read through the same daily oracle the map
    itself is arbitrated by: un-adjust the day's fetched HIGH and LOW by each candidate chain and
    require containment within :data:`DEFAULT_PRICE_CONTAINMENT_PAISE` of the RAW daily high/low.
    Exactly one side containing decides. Both (which happens only when the two chains are the same
    number) or neither is :data:`FLOOR_UNDECIDED` -- an honest "this day answers nothing".

    PRICE alone decides. It is the exact observable -- a wrong chain misses by the factor, hundreds
    of paise -- while the volume ratio carries the pre-open auction shortfall the gate-1 band exists
    to absorb, so adding it could only turn decisive days undecided.
    """
    if k_in <= 0 or k_out <= 0:
        return FLOOR_UNDECIDED
    in_ok = _day_price_contained(probe, k_in, tol_paise)
    out_ok = _day_price_contained(probe, k_out, tol_paise)
    if in_ok and not out_ok:
        return FLOOR_IN
    if out_ok and not in_ok:
        return FLOOR_OUT
    return FLOOR_UNDECIDED


def classify_floor_day_volume(probe: ProbeDay, k_in: Decimal, k_out: Decimal) -> str:
    """The VOLUME-side twin of :func:`classify_floor_day` (QUESTIONS.md Q-14). PURE.

    The Q-14 ruling makes the floors PER SIDE, so the volume splice is measured with the volume
    oracle: un-adjust the day's fetched volume by each candidate chain and require CONTEXT 4.5 gate
    1's own, unwidened band. Exactly one side reconciling decides; both or neither is
    :data:`FLOOR_UNDECIDED`.

    The volume observable carries the pre-open auction shortfall, which is why PRICE alone decides
    the price side. Here it is the only observable there is -- and it is decisive whenever the
    event's volume factor is far enough from 1 to move a day outside a ``[-0.1%, +5.0%]`` band. An
    event whose volume factor is ~1 (a demerger the vendor did not rescale shares for) can never be
    decided on this side, and the search then answers UNDECIDED rather than guessing: that is the
    honest outcome, and it is exactly the blindness finding Q1 measured.
    """
    if k_in <= 0 or k_out <= 0:
        return FLOOR_UNDECIDED
    in_ok = volume_gate(probe.raw_volume, unadjust_volume(probe.fetched_volume, k_in)).passed
    out_ok = volume_gate(probe.raw_volume, unadjust_volume(probe.fetched_volume, k_out)).passed
    if in_ok and not out_ok:
        return FLOOR_IN
    if out_ok and not in_ok:
        return FLOOR_OUT
    return FLOOR_UNDECIDED


# --- the STORE-backed classifier (Q-14; decision B143) ----------------------------------

#: Which side of the per-side floor model a search is measuring.
FLOOR_SIDE_PRICE: str = "price"
FLOOR_SIDE_VOLUME: str = "volume"


@dataclass(frozen=True)
class StoredDay:
    """One STORED symbol-day reduced to the two observables a floor search reads. PURE data.

    The Q-14 ruling's own closing note is that both sides of the check are LOCAL. A probe buys the
    ratio ``fetched/raw``; the store already holds it, because ``stored = fetched / k_applied`` by
    construction of the ingest. So a floor search can be run against the store with no credentialed
    call at all -- see :func:`classify_stored_price_day`.
    """

    day: date
    stored_high: int
    stored_low: int
    stored_volume: int
    raw_high: int
    raw_low: int
    raw_volume: int


def classify_stored_price_day(
    stored: StoredDay,
    event_price_factor: Decimal,
    tol_paise: int = DEFAULT_PRICE_CONTAINMENT_PAISE,
) -> str:
    """Does this STORED day fit with the event IN its price chain, or OUT of it? PURE.

    The arithmetic, stated once (QUESTIONS.md Q-14, decision B143). The store holds
    ``stored = fetched / k_applied``, where ``k_applied`` is the chain the committed map applied to
    the day. Under the hypothesis that the vendor's archive was spliced and the event was NOT
    applied to this day, the vendor's true chain was ``k_applied / k_event``, so the correct raw
    price is ``fetched x k_event / k_applied = stored x k_event``. Therefore:

    * **event-in**  <=> the stored day is already contained in the raw daily interval -- which is
      literally :func:`acumen.quality_gates.price_containment_gate`, gate 1P itself;
    * **event-out** <=> the stored day multiplied BACK by the event's own factor is contained.

    Exactly one containing decides; both (only possible when ``k_event`` is 1, i.e. nothing to
    test) or neither is :data:`FLOOR_UNDECIDED`. Identical oracle, identical tolerance, and no
    candle is fetched: the two hypotheses are two multiplications of numbers already on disk.
    """
    if event_price_factor <= 0 or event_price_factor == _ONE:
        return FLOOR_UNDECIDED
    in_ok = price_containment_gate(
        stored.stored_high, stored.stored_low, stored.raw_high, stored.raw_low,
        min_tol_paise=tol_paise,
    ).passed
    out_ok = price_containment_gate(
        _scale_paise(stored.stored_high, event_price_factor),
        _scale_paise(stored.stored_low, event_price_factor),
        stored.raw_high, stored.raw_low, min_tol_paise=tol_paise,
    ).passed
    if in_ok and not out_ok:
        return FLOOR_IN
    if out_ok and not in_ok:
        return FLOOR_OUT
    return FLOOR_UNDECIDED


def classify_stored_volume_day(stored: StoredDay, event_volume_factor: Decimal) -> str:
    """The VOLUME-side twin of :func:`classify_stored_price_day`. PURE.

    Volume scales the other way (``stored = fetched x k_applied``), so the event-out hypothesis is
    the stored volume DIVIDED by the event's own volume factor. The oracle is CONTEXT 4.5 gate 1's
    unwidened band, exactly as :func:`classify_floor_day_volume` uses it on a probe.
    """
    if event_volume_factor <= 0 or event_volume_factor == _ONE:
        return FLOOR_UNDECIDED
    in_ok = volume_gate(stored.raw_volume, stored.stored_volume).passed
    out_ok = volume_gate(
        stored.raw_volume,
        int((Decimal(stored.stored_volume) / event_volume_factor).quantize(
            _ONE, rounding=ROUND_HALF_EVEN
        )),
    ).passed
    if in_ok and not out_ok:
        return FLOOR_IN
    if out_ok and not in_ok:
        return FLOOR_OUT
    return FLOOR_UNDECIDED


def _scale_paise(paise: int, factor: Decimal) -> int:
    return int((Decimal(paise) * factor).quantize(_ONE, rounding=ROUND_HALF_EVEN))


@dataclass(frozen=True)
class FloorSearch:
    """The outcome of one binary search: the boundary, whether it resolved, and every probe."""

    floor_date: date | None
    resolved: bool
    probes: tuple[FloorProbe, ...]
    note: str


def binary_search_floor(
    days: Sequence[date],
    classify: Callable[[date], FloorProbe],
    *,
    max_probes: int = MAX_FLOOR_PROBES,
    max_undecided_steps: int = MAX_UNDECIDED_STEPS,
    absent_floor_date: date | None = None,
) -> FloorSearch:
    """Binary-search the vendor's application floor over ``days``. PURE control flow.

    ``days`` is the ascending list of candidate trading days (every one strictly before the event's
    ex-date, and every one inside a PROVABLE era so the two hypotheses are exact). ``classify``
    probes ONE day and returns its :class:`FloorProbe`; it is the only thing here that touches the
    network, which is why it is injected -- the search itself is deterministic and offline-testable.

    The model is a single step: below the floor the event is absent, at and above it the event is
    applied. So the search
    (1) probes the NEWEST day -- it must be :data:`FLOOR_IN`, otherwise the event is not applied
        even beside its own ex-date and there is no floor to find (UNRESOLVED, chain untouched);
    (2) probes the OLDEST day -- :data:`FLOOR_IN` means the event is applied throughout and there is
        no splice inside our history (``floor_date=None``, resolved);
    (3) otherwise bisects the OUT/IN boundary, and returns the OLDEST day that is still
        :data:`FLOOR_IN` -- i.e. the first day the vendor's adjustment reaches.

    An :data:`FLOOR_UNDECIDED` day steps to at most ``max_undecided_steps`` neighbours before the
    search abandons UNRESOLVED. Running out of ``max_probes`` also abandons. Neither ever guesses a
    boundary: an unresolved search leaves the map's chain exactly as it was.

    ``absent_floor_date`` (Q-11 addendum 4) admits the one outcome step (1) otherwise discards: a
    floor sitting ABOVE our whole history, where the vendor never applied the event to one day we
    can probe. That is exactly the case the un-provable-era deadlock is made of, so it may not stay
    an abandoned search -- but neither may it be assumed from one probe. Given the date, the search
    probes the newest, the OLDEST and a MIDPOINT day, and resolves the floor AT ``absent_floor_date``
    only when all three answer :data:`FLOOR_OUT`. One ``event-in`` or one ``undecided`` among them
    and it stays UNRESOLVED. Left ``None`` the search behaves exactly as it did before the ruling.
    """
    ordered = sorted(set(days))
    if not ordered:
        return FloorSearch(None, False, (), "no candidate day inside a provable era to probe")

    probes: list[FloorProbe] = []
    seen: dict[int, FloorProbe] = {}

    def look(index: int) -> FloorProbe | None:
        """Probe ``ordered[index]`` once, memoised; ``None`` when the budget is spent."""
        if index in seen:
            return seen[index]
        if len(probes) >= max_probes:
            return None
        probe = classify(ordered[index])
        seen[index] = probe
        probes.append(probe)
        return probe

    def decisive(index: int, low: int, high: int) -> tuple[int, str] | None:
        """``(index, verdict)`` for ``index`` or a near neighbour STRICTLY inside ``(low, high)``.

        Strictly inside is load-bearing, not tidiness: an endpoint's verdict is already the loop's
        invariant, so returning one would move neither bound and the bisection would spin on the
        same midpoint forever without spending a probe. Out of strictly-inside candidates means the
        search abandons UNRESOLVED, which is the honest answer.
        """
        offsets = [0]
        for step in range(1, max_undecided_steps + 1):
            offsets.extend((step, -step))
        for offset in offsets:
            candidate = index + offset
            if not (low < candidate < high):
                continue
            probe = look(candidate)
            if probe is None:
                return None
            if probe.verdict != FLOOR_UNDECIDED:
                return candidate, probe.verdict
        return None

    newest = look(len(ordered) - 1)
    if newest is None or newest.verdict != FLOOR_IN:
        verdict = "budget spent" if newest is None else newest.verdict
        if absent_floor_date is not None and verdict == FLOOR_OUT:
            return _search_absent_throughout(
                ordered, look, probes, absent_floor_date, newest_index=len(ordered) - 1
            )
        return FloorSearch(
            None, False, tuple(probes),
            f"the newest probed day ({ordered[-1].isoformat()}) is {verdict}, not {FLOOR_IN}: the "
            "event is not applied even beside its own ex-date, so there is no floor to find",
        )
    if len(ordered) == 1:
        return FloorSearch(
            None, True, tuple(probes),
            "a single candidate day, and the event is applied on it: no splice inside our history",
        )
    oldest = look(0)
    if oldest is None:
        return FloorSearch(None, False, tuple(probes), "probe budget spent before the oldest day")
    if oldest.verdict == FLOOR_IN:
        return FloorSearch(
            None, True, tuple(probes),
            f"applied on the oldest stored day too ({ordered[0].isoformat()}): no splice inside "
            "our history, the chain is unchanged",
        )
    if oldest.verdict == FLOOR_UNDECIDED:
        return FloorSearch(
            None, False, tuple(probes),
            f"the oldest probed day ({ordered[0].isoformat()}) answers neither hypothesis; no "
            "boundary is guessed",
        )

    low, high = 0, len(ordered) - 1  # invariant: ordered[low] is OUT, ordered[high] is IN
    while high - low > 1:
        found = decisive((low + high) // 2, low, high)
        if found is None:
            return FloorSearch(
                None, False, tuple(probes),
                f"the search stalled between {ordered[low].isoformat()} and "
                f"{ordered[high].isoformat()} (undecided midpoints or probe budget spent); no "
                "boundary is guessed",
            )
        index, verdict = found
        if verdict == FLOOR_IN:
            high = min(high, index)
        else:
            low = max(low, index)
        if high - low <= 1:
            break
    return FloorSearch(
        ordered[high], True, tuple(probes),
        f"vendor application floor {ordered[high].isoformat()}: the event is absent from every "
        f"chain before it ({ordered[low].isoformat()} probed {FLOOR_OUT}) and applied from it on",
    )


def _search_absent_throughout(
    ordered: Sequence[date],
    look: Callable[[int], FloorProbe | None],
    probes: Sequence[FloorProbe],
    absent_floor_date: date,
    *,
    newest_index: int,
) -> FloorSearch:
    """Confirm (or refuse) a floor sitting ABOVE the whole searched span. PURE control flow.

    The newest day already answered :data:`FLOOR_OUT`. Under the step model that alone would put the
    floor above every day here, but one probe is not a measurement of a whole span -- a damaged day
    or a mis-hypothesised chain looks exactly the same. So the OLDEST day and a MIDPOINT are probed
    too, and the floor is resolved AT ``absent_floor_date`` only if all three are ``event-out``.
    """
    checked = [(newest_index, "newest")]
    if len(ordered) > 1:
        checked.append((0, "oldest"))
    if len(ordered) > 2:
        checked.append((len(ordered) // 2, "midpoint"))
    for index, which in checked:
        probe = look(index)
        if probe is None:
            return FloorSearch(
                None, False, tuple(probes),
                f"probe budget spent before the {which} day could confirm the event is absent "
                "throughout; no boundary is guessed",
            )
        if probe.verdict != FLOOR_OUT:
            return FloorSearch(
                None, False, tuple(probes),
                f"the {which} probed day ({ordered[index].isoformat()}) answers {probe.verdict}, "
                f"not {FLOOR_OUT}: the event is not absent throughout and no boundary is inside the "
                "searched span; nothing is guessed",
            )
    span = f"{ordered[0].isoformat()} .. {ordered[-1].isoformat()}"
    return FloorSearch(
        absent_floor_date, True, tuple(probes),
        f"vendor application floor at or above the ex-date {absent_floor_date.isoformat()}: the "
        f"event is absent from every chain in our history ({len(checked)} probed day(s) across "
        f"{span}, all {FLOOR_OUT})",
    )


@dataclass(frozen=True)
class AdjustmentMap:
    """The committed per-symbol adjustment map: one :class:`EraResolution` per probed era."""

    symbol: str
    fetch_date: date
    all_event_ex_dates: tuple[date, ...]
    eras: tuple[EraResolution, ...]
    tick_paise: int | None = None
    #: Which volume estimator built this map (:data:`MAP_VOLUME_ESTIMATOR`). A map read back with a
    #: different value was built under a superseded ruling and must be rebuilt, not consumed --
    #: see :func:`map_is_current`.
    volume_estimator_id: str = MAP_VOLUME_ESTIMATOR
    #: Q-11 addendum 2: the measured per-event vendor application floors. Empty means none were
    #: hunted (or none resolved), and the map then behaves exactly as it did before the ruling.
    floors: tuple[EventFloor, ...] = ()
    #: Which MAP MODEL built this map (:data:`MAP_MODEL`) -- see :func:`map_is_current`.
    map_model_id: str = MAP_MODEL

    def _era_index(self) -> dict[tuple[date, ...], EraResolution]:
        return {era.ex_dates: era for era in self.eras}

    def _floor_index(self) -> dict[date, EventFloor]:
        return {floor.ex_date: floor for floor in self.floors}

    def in_window_ex_dates(self, day: date) -> tuple[date, ...]:
        """The price-moving ex-dates in ``(day, fetch_date]`` -- the era key for ``day``."""
        return tuple(ex for ex in self.all_event_ex_dates if day < ex <= self.fetch_date)

    def era_for_day(self, day: date) -> EraResolution | None:
        """The resolved era covering ``day``, or ``None`` when that era was never probed."""
        return self._era_index().get(self.in_window_ex_dates(day))

    def era_chain_for_day(self, day: date) -> tuple[Decimal, Decimal] | None:
        """The day's era chain with FLOORS IGNORED -- ``(k_price, k_volume)`` as the era committed.

        This is not what the day should be un-adjusted BY (that is :meth:`factors_for_day`); it is
        the set of factors that has ever been applied to the day by any pass, ours or the vendor's.
        The in-place rebuild uses it to GENERATE its baseline hypotheses, so a day the store already
        holds under the pre-floor chain is still recognisable after a floor drops that chain to 1.
        """
        if not self.in_window_ex_dates(day):
            return _ONE, _ONE
        era = self.era_for_day(day)
        if era is None or not era.provable:
            return None
        return era.k_price, era.k_volume

    def event_applies_on(self, ex_date: date, day: date) -> bool:
        """Did the vendor apply the event at ``ex_date`` to a bar stamped ``day``? PURE (PRICE side).

        True unless a RESOLVED floor for that event sits above ``day`` (Q-11 addendum 2). An event
        with no floor, or one whose search did not resolve, is applied as the era resolved it.
        """
        floor = self._floor_index().get(ex_date)
        return True if floor is None else floor.applies_on(day)

    def event_applies_on_volume(self, ex_date: date, day: date) -> bool:
        """The same question for the VOLUME side (QUESTIONS.md Q-14 per-side floors). PURE.

        Identical to :meth:`event_applies_on` for every floor whose volume side was never measured,
        so a map committed before the Q-14 ruling answers exactly as it did then.
        """
        floor = self._floor_index().get(ex_date)
        return True if floor is None else floor.applies_on_volume(day)

    def factors_for_day(self, day: date) -> tuple[Decimal, Decimal] | None:
        """``(k_price, k_volume)`` for ``day``, or ``None`` when the day is un-provable.

        A day with NO price-moving event in ``(day, F]`` (an empty era key -- a recent, post-last-CA
        day) is the EXACT identity ``(1, 1)`` by definition: the vendor applied nothing, so fetched
        == raw. This holds even if no identity era was explicitly probed, so a recent RAW day is
        never wrongly excluded for want of a probe window. Otherwise ``None`` means the day's era was
        not probed or found no fitting candidate -- the day cannot be un-adjusted and gate 1 will
        exclude and count it.

        With FLOORS committed (Q-11 addendum 2) the chain is formed PER EVENT from the era's own
        :class:`EventChoice` rows, dropping every event whose application floor sits above ``day``.
        Without floors the product of those same per-event factors IS the era's ``k_price`` /
        ``k_volume``, so a floorless map answers exactly as it did before the ruling.

        The two sides are dropped INDEPENDENTLY (QUESTIONS.md Q-14): the vendor spliced its archive
        per side, so one event can be absent from a day's PRICE chain while still present in its
        VOLUME chain. That asymmetry is the whole mechanism behind the 1,963 days finding Q1
        measured -- the volume side reconciled, so gate 1 passed, while the price side was off by
        the event's own factor.
        """
        if not self.in_window_ex_dates(day):
            return _ONE, _ONE
        era = self.era_for_day(day)
        if era is None or not era.provable:
            return None
        if not self.floors:
            return era.k_price, era.k_volume
        k_price = _ONE
        k_volume = _ONE
        for choice in era.choices:
            if self.event_applies_on(choice.ex_date, day):
                k_price *= choice.price_factor
            # else: below the vendor's PRICE splice -- ABSENT from this day's price chain
            if self.event_applies_on_volume(choice.ex_date, day):
                k_volume *= choice.volume_factor
        return k_price, k_volume


def with_floors(adjustment_map: AdjustmentMap, floors: Sequence[EventFloor]) -> AdjustmentMap:
    """A copy of ``adjustment_map`` carrying ``floors``. PURE (the map is frozen)."""
    return replace(adjustment_map, floors=tuple(floors))


def carry_floors_forward(
    previous: AdjustmentMap | None, fresh: AdjustmentMap
) -> tuple[AdjustmentMap, tuple[EventFloor, ...]]:
    """Carry an already-measured floor onto a freshly-rebuilt map. PURE.

    Returns ``(map_with_carried_floors, dropped)``.

    A vendor APPLICATION FLOOR is a property of the vendor's ARCHIVE -- the splice date before which
    it never applied an event -- so it does not expire when the map is rebuilt under a newer fetch
    date. Rebuilding without carrying it is a silent regression in the exact artifact the Q-11
    addendum-2 ruling asks be committed ("floor + probe evidence recorded in the map"): the store
    stays correct only until the next fresh fetch, and the audit trail is gone immediately.

    A floor is carried ONLY when the fresh map still resolves its event to the SAME committed price
    factor. That is the assumption the floor's own probes were classified under -- each probe asked
    "does this day fit with this factor in the chain, or out of it?" -- so a changed factor
    invalidates the measurement and the floor is DROPPED rather than reused. Dropped floors are
    returned so the caller can re-open the hunt instead of quietly losing one.

    A floor MEASURED under Q-11 addendum 4 also carries the factor its probes were classified under
    (``event_price_factor``), and the fresh map may legitimately resolve that event to ABSENT
    precisely BECAUSE the floor is in force -- a floor that forces an event out of every era makes
    its canonical factor 1, which the "same factor" test would read as a change and drop, re-opening
    a hunt that would measure the same floor again, forever. So a carry is also kept when the fresh
    map commits nothing for the event (no provable era resolved it) or commits exactly ABSENT: in
    both cases dropping the event from a day's chain is the identity, so the carry cannot alter one
    stored price and the committed evidence survives.

    A floor the FRESH map was already built WITH (the Q-11 addendum-4 rebuild passes its measured
    floors INTO the builder) is kept as it stands and never re-derived from the previous map.
    """
    if previous is None or not previous.floors:
        return fresh, ()
    own = {floor.ex_date for floor in fresh.floors}
    was = canonical_event_factors(previous)
    now = canonical_event_factors(fresh)
    kept: list[EventFloor] = list(fresh.floors)
    dropped: list[EventFloor] = []
    for floor in previous.floors:
        if floor.ex_date in own:
            continue  # the rebuild already carries a fresher measurement for this event
        before, after = was.get(floor.ex_date), now.get(floor.ex_date)
        classified_under = floor.event_price_factor if floor.event_price_factor is not None else (
            None if before is None else before[0]
        )
        if after is None or after[0] == _ONE:
            kept.append(floor)  # nothing committed, or committed absent -- the floor is an identity
        elif classified_under is not None and classified_under == after[0]:
            kept.append(floor)
        else:
            dropped.append(floor)
    return with_floors(fresh, sorted(kept, key=lambda f: f.ex_date)), tuple(dropped)


def canonical_event_factors(
    adjustment_map: AdjustmentMap,
) -> dict[date, tuple[Decimal, Decimal, str, str]]:
    """Each event's committed ``(price, volume, price_source, volume_source)``. PURE.

    Read from the NEWEST provable era in which the event appears -- the same "decided at its newest
    appearance and carried older" discipline the builder itself uses. An event that appears only in
    un-provable eras is absent from the result: nothing about it was ever committed.
    """
    committed: dict[date, tuple[Decimal, Decimal, str, str]] = {}
    for era in sorted(adjustment_map.eras, key=lambda e: (len(e.ex_dates), e.ex_dates)):
        if not era.provable:
            continue
        for choice in era.choices:
            committed.setdefault(
                choice.ex_date,
                (choice.price_factor, choice.volume_factor, choice.price_source, choice.volume_source),
            )
    return committed


def era_hypothesis(
    adjustment_map: AdjustmentMap,
    era: EraResolution,
    events: Mapping[date, EventSpec],
    *,
    target_ex_date: date | None = None,
    committed: Mapping[date, tuple[Decimal, Decimal, str, str]] | None = None,
) -> tuple[EventChoice, ...] | None:
    """The chain an UN-PROVABLE era would carry, for a floor search to test against. PURE.

    Q-11 addendum 4 clause (ii): "the one-fresh-unknown-per-era discipline holds -- a floor being
    measured is that era's fresh unknown; previously committed sources may combine with it." An
    un-provable era committed nothing, so a floor search inside it needs a chain to form its two
    hypotheses from. This builds one WITHOUT fitting anything, and the rule is exactly the ruling's:

    * every event OTHER than the one being floored must carry a PREVIOUSLY COMMITTED source -- the
      factor the newest era that resolved it committed (:func:`canonical_event_factors`, the same
      "decided at its newest appearance and carried older" discipline the builder uses). An era
      holding a second uncommitted event has TWO unknowns, not one, so it returns ``None`` and the
      caller records the refusal. Filling that slot with our own factor would be assuming the vendor
      used it -- a policy guess of exactly the kind measurement replaced (measured live: on IOC the
      vendor applies NO special dividend, so `ours` there would put both hypotheses off by ~3% and
      turn every decisive probe into an `undecided` one);
    * ``target_ex_date`` -- the event whose floor is being measured -- may instead take our exact
      CONTEXT 4.2 factor when nothing committed it. That is not an assumption about the vendor: it
      is the very quantity the two hypotheses test the presence of, and the oracle answers.

    Only the FLOOR is left unknown, and the daily oracle decides it. The volume side is filled in
    the same order so the hypothesis is a complete audit row, but a floor search reads the PRICE
    side alone.
    """
    known = canonical_event_factors(adjustment_map) if committed is None else committed
    choices: list[EventChoice] = []
    for ex_date in era.ex_dates:
        event = events.get(ex_date)
        if ex_date != target_ex_date and ex_date not in known:
            return None  # a second unknown -- refuse rather than guess
        if ex_date in known:
            price, volume, price_source, volume_source = known[ex_date]
            choices.append(
                EventChoice(
                    kind=event.kind if event is not None else KIND_UNPARSED,
                    ex_date=ex_date,
                    price_factor=price,
                    price_source=price_source,
                    volume_factor=volume,
                    volume_source=volume_source,
                )
            )
            continue
        if event is None or event.our_price_factor is None:
            return None
        our_volume = event.our_volume_factor()
        choices.append(
            EventChoice(
                kind=event.kind,
                ex_date=ex_date,
                price_factor=event.our_price_factor,
                price_source=SOURCE_OURS,
                volume_factor=our_volume if our_volume is not None else event.our_price_factor,
                volume_source=SOURCE_OURS if our_volume is not None else SOURCE_PRICE_FACTOR,
            )
        )
    return tuple(choices)


# --- the pure builder ------------------------------------------------------------------


def build_map(
    symbol: str,
    fetch_date: date,
    events: Sequence[EventSpec],
    era_measurements: Sequence[EraMeasurement],
    *,
    tick_paise: int | None = None,
    price_tol_paise: int = DEFAULT_PRICE_CONTAINMENT_PAISE,
    floors: Sequence[EventFloor] = (),
) -> AdjustmentMap:
    """Build the adjustment map from measured eras + the event list. PURE, deterministic.

    Works backwards (eras newest = fewest in-window events, first), carrying each event's decision
    into older eras. The price oracle is 2-paise containment vs the raw daily high/low, the volume
    oracle is gate-1's band (UNWIDENED). An era whose events admit no passing assignment is marked
    ``provable=False`` -- its days are excluded and counted.

    Price and volume stay independently ARBITRATED, but the passes are ORDERED (Q-12 ruling clause
    ii): price resolves first, and each event's chosen price factor is then offered to the volume
    pass as a candidate -- so a rights or demerger, which has no ``ours`` volume factor at all, can
    be reconciled by the factor the price oracle already pinned to 2 paise per probe day. The
    measured volume candidate is :func:`volume_estimator` (the minimum over price-passing days),
    not a median (clause i).

    ``floors`` (Q-11 addendum 4) are already-MEASURED vendor application floors, and they take part
    in the build rather than being layered on afterwards. For an era whose probe days ALL sit below
    an event's floor the event is forced ABSENT -- the vendor demonstrably did not apply it there --
    and it stops counting as a fresh unknown for the probe-gap guard, which is what lets a cascade
    of under-determined older eras unwind. An era whose probe window STRADDLES a floor is marked
    un-provable and says so: its measured cumulative ratio mixes two different chains, so no single
    era factor describes it. Acceptance is otherwise untouched -- a floored era still has to satisfy
    2-paise per-day price containment AND gate-1's unwidened band, exactly like every other era.
    """
    sym = symbol.strip().upper()
    by_ex: dict[date, EventSpec] = {e.ex_date: e for e in events}
    # Two price-moving events sharing an ex-date would collapse in ``by_ex`` and one would silently
    # vanish from the chain. The map keys eras by ex-date and cannot represent both -- refuse (STOP)
    # rather than commit a chain missing an event (CLAUDE.md rule 1).
    if len(by_ex) != len(list(events)):
        seen: set[date] = set()
        dupes = sorted({e.ex_date for e in events if e.ex_date in seen or seen.add(e.ex_date)})
        raise VendorAdjustmentError(
            f"{sym}: two price-moving events share an ex-date {dupes}; the map keys eras by ex-date "
            "and cannot represent both -- resolve upstream (merge or re-key) before building a map"
        )
    all_ex = tuple(sorted(by_ex))
    ordered_eras = sorted(era_measurements, key=lambda m: (len(m.ex_dates), m.ex_dates))
    # A floor resolved on EITHER side is a measurement the arbitration must honour (Q-14 per-side
    # floors): a volume-only splice carries ``resolved=False`` on the price side, and reading only
    # that flag would silently drop it from the build.
    floor_index = {f.ex_date: f for f in floors if f.resolved or f.volume_resolved}

    # --- Phase 1: backward pass -- decide each event's SOURCE per era (the audit labels) -------
    price_canon: dict[date, tuple[str, Decimal]] = {}
    vol_canon: dict[date, tuple[str, Decimal]] = {}
    # decided[era_key][ex] = (price_source, price_factor, volume_source, volume_factor); None era = unprovable
    decided: dict[tuple[date, ...], dict[date, tuple[str, Decimal, str, Decimal]] | None] = {}
    reasons: dict[tuple[date, ...], str] = {}
    for era in ordered_eras:
        win = [by_ex[ex] for ex in era.ex_dates if ex in by_ex]
        # Guard: an era key must name only known events. An unknown ex-date means the caller's
        # event list and its measured eras disagree -- refuse rather than silently mis-key.
        if len(win) != len(era.ex_dates):
            raise VendorAdjustmentError(
                f"{sym} era {era.label!r} names ex-dates not in the event list: "
                f"{sorted(set(era.ex_dates) - set(by_ex))}"
            )
        # Q-11 addendum 4: an event whose MEASURED floor sits above this era's probe days was not
        # applied by the vendor here at all. That is a measurement, not a candidate, so the event is
        # FORCED absent -- and a straddled probe window is refused rather than averaged.
        forced_price, forced_volume, straddled = _floored_events(win, era, floor_index)
        if straddled:
            decided[era.ex_dates] = None
            reasons[era.ex_dates] = (
                "probe window straddles a measured vendor application floor "
                f"({[ex.isoformat() for ex in straddled]}); one era factor cannot describe two "
                "different chains -- probe a window wholly on one side of the floor"
            )
            continue
        # PROBE-GAP guard: working backwards, a consecutively-probed era adds exactly ONE older
        # event. If an era introduces >1 event not already resolved by a newer era, an inter-event
        # era was NOT probed, so the residual cannot be attributed per event (>1 unknown from one
        # observable) -- committing a decomposition would be free fitting, not measurement. Mark the
        # era un-provable (its days are excluded + counted, the ruling's surgical clamp); probing
        # the missing intermediate era rescues it. The gap propagates to older eras by construction.
        # A FORCED-absent event is not an unknown -- its factor was measured by the floor search --
        # so it does not consume the era's one degree of freedom (Q-11 addendum 4 clause ii). Under
        # the Q-14 per-side floors an event only stops being an unknown when BOTH sides were
        # measured absent here; a price-only splice still leaves the volume side to arbitrate.
        settled = set(forced_price) & set(forced_volume)
        new_events = [e for e in win if e.ex_date not in price_canon and e.ex_date not in settled]
        if len(new_events) > 1:
            decided[era.ex_dates] = None
            reasons[era.ex_dates] = (
                f"probe gap: era introduces {len(new_events)} events not covered by a newer era "
                f"({[e.ex_date.isoformat() for e in new_events]}); per-event attribution is "
                "under-determined -- probe each intermediate era to resolve"
            )
            continue
        price = _resolve_pass(
            win, era.price_cumulative, price_canon,
            get_ours=lambda e: e.our_price_factor,
            oracle=lambda k_chain, per: _price_contained(era, k_chain, price_tol_paise),
            forced=forced_price,
        )
        # Q-12 clause (ii): the volume pass sees the price pass's OWN result -- each event's chosen
        # price factor becomes a volume candidate, and the era's chosen price chain is what the
        # estimator's day filter (clause i) is evaluated against. Hence price FIRST, then volume.
        volume = None
        if price is not None:
            chosen_price = {ex: factor for ex, (_src, factor) in price.items()}
            k_price_chosen = _ONE
            for factor in chosen_price.values():
                k_price_chosen *= factor
            volume = _resolve_pass(
                win,
                volume_estimator(era, k_price_chosen, tol_paise=price_tol_paise),
                vol_canon,
                get_ours=lambda e: e.our_volume_factor(),
                oracle=lambda k_chain, per: _volume_reconciled(era, k_chain),
                costs=_VOLUME_COST,
                price_factors=chosen_price,
                forced=forced_volume,
            )
        if price is None or volume is None:
            decided[era.ex_dates] = None
            reasons[era.ex_dates] = "no candidate chain satisfies price containment + gate-1"
            continue
        era_choice: dict[date, tuple[str, Decimal, str, Decimal]] = {}
        for e in win:
            psrc, pval = price[e.ex_date]
            vsrc, vval = volume[e.ex_date]
            era_choice[e.ex_date] = (psrc, pval, vsrc, vval)
            price_canon[e.ex_date] = (psrc, pval)
            vol_canon[e.ex_date] = (vsrc, vval)
        decided[era.ex_dates] = era_choice

    # --- Phase 2: refine each MEASURED event's scalar to the median over ALL its pre-ex probe
    # days (across every era it is measured in), exactly the ruling's "median ratio over pre-ex
    # probe days -- single scalar per event". Dividing out the OTHER events' resolved factors
    # isolates the one event; the median tightens containment without re-labelling anything. ------
    by_key: dict[tuple[date, ...], EraMeasurement] = {e.ex_dates: e for e in ordered_eras}
    price_scalar = _refine_scalars(decided, by_key, by_ex, "price")
    # The VOLUME refinement is filtered by price containment too (Q-12 clause i applies to the
    # estimator wherever it is formed, not only inside one era), so it needs each era's REFINED
    # price chain -- the very chain phase 3 commits and consumes.
    refined_k_price: dict[tuple[date, ...], Decimal] = {}
    for key, choice in decided.items():
        if choice is None:
            continue
        chain = _ONE
        for ex, (psrc, pval, _vsrc, _vval) in choice.items():
            chain *= _factor_for_source(by_ex[ex], psrc, price_scalar.get(ex, pval), price=True)
        refined_k_price[key] = chain
    vol_scalar = _refine_scalars(
        decided, by_key, by_ex, "volume",
        price_chains=refined_k_price, price_tol_paise=price_tol_paise,
    )

    # --- Phase 3: assemble each era with the refined factors + oracle diagnostics --------------
    resolutions: list[EraResolution] = []
    for era in ordered_eras:
        era_choice = decided[era.ex_dates]
        provable = era_choice is not None
        win = [by_ex[ex] for ex in era.ex_dates]
        choices: list[EventChoice] = []
        k_price = _ONE
        k_volume = _ONE
        note = reasons.get(era.ex_dates, "")
        if provable:
            for e in win:
                psrc, _p0, vsrc, _v0 = era_choice[e.ex_date]
                # Fall back to the phase-1 value when no refined scalar exists: the refinement only
                # TIGHTENS an already-arbitrated factor, so a missing refinement must never turn a
                # provable era into a crash.
                pval = _factor_for_source(e, psrc, price_scalar.get(e.ex_date, _p0), price=True)
                if vsrc == SOURCE_PRICE_FACTOR:
                    # Q-12 clause (ii): this event's volume factor IS its committed price factor --
                    # read from ``pval`` above so the two can never drift apart in the audit row.
                    vval = pval
                else:
                    vval = _factor_for_source(e, vsrc, vol_scalar.get(e.ex_date, _v0), price=False)
                choices.append(
                    EventChoice(
                        kind=e.kind, ex_date=e.ex_date,
                        price_factor=pval, price_source=psrc,
                        volume_factor=vval, volume_source=vsrc,
                    )
                )
                k_price *= pval
                k_volume *= vval
            # RE-VALIDATE the FINAL (refined) chain against the oracle -- phase 1 arbitrated on the
            # provisional (carried) factors, and the phase-2 refinement can shift a measured scalar,
            # so provability must be re-proven on exactly the k_price/k_volume that get COMMITTED and
            # consumed. If the refined chain no longer contains or reconciles, the era is un-provable.
            if not (_price_contained(era, k_price, price_tol_paise) and _volume_reconciled(era, k_volume)):
                provable = False
                note = "refined chain fails price containment or gate-1 on re-validation"
        containment = _price_residual_paise(era, k_price) if provable else -1
        gap = _volume_gap_pct(era, k_volume) if provable else None
        resolutions.append(
            EraResolution(
                label=era.label,
                ex_dates=era.ex_dates,
                choices=tuple(choices),
                k_price=k_price,
                k_volume=k_volume,
                price_containment_paise=containment,
                volume_gap_pct=gap,
                provable=provable,
                probe_days=tuple(p.day for p in era.probe_days),
                note=_era_note(era, choices, provable, reason=note),
            )
        )

    resolutions.sort(key=lambda r: (len(r.ex_dates), r.ex_dates))
    return AdjustmentMap(
        symbol=sym,
        fetch_date=fetch_date,
        all_event_ex_dates=all_ex,
        eras=tuple(resolutions),
        tick_paise=tick_paise,
        # The floors the build was arbitrated UNDER are committed with it: a map whose eras were
        # resolved with an event forced absent must carry the evidence for that, or a consumer would
        # read a chain it cannot justify (Q-11 addendum 4 clause iv).
        floors=tuple(floors),
    )


def _floored_events(
    win: Sequence[EventSpec],
    era: EraMeasurement,
    floor_index: Mapping[date, EventFloor],
) -> tuple[dict[date, tuple[str, Decimal]], dict[date, tuple[str, Decimal]], list[date]]:
    """Which of this era's events a MEASURED floor forces ABSENT, per side, and which straddle. PURE.

    Returns ``(forced_price, forced_volume, straddled)``.

    Q-11 addendum 4: a floor is a measured property of the vendor's archive, so where it lies above
    an era's probe days the event is not a candidate to arbitrate -- it is known absent. Where the
    probe window sits astride the floor (some days below, some above) the era's single cumulative
    ratio mixes two chains and no era factor can describe it; the caller marks that era un-provable
    rather than averaging the two.

    Q-14 makes the floors PER SIDE, so the two forced sets are computed separately: the price pass
    is told what the price splice measured and the volume pass what the volume splice measured. A
    straddle on EITHER side refuses the era, because either one alone makes the era's single
    cumulative ratio a mixture.
    """
    forced_price: dict[date, tuple[str, Decimal]] = {}
    forced_volume: dict[date, tuple[str, Decimal]] = {}
    straddled: list[date] = []
    days = [p.day for p in era.probe_days]
    for event in win:
        floor = floor_index.get(event.ex_date)
        if floor is None or not days:
            continue
        applies_price = {floor.applies_on(day) for day in days}
        applies_volume = {floor.applies_on_volume(day) for day in days}
        if applies_price == {False}:
            forced_price[event.ex_date] = (SOURCE_ABSENT, _ONE)
        if applies_volume == {False}:
            forced_volume[event.ex_date] = (SOURCE_ABSENT, _ONE)
        if len(applies_price) > 1 or len(applies_volume) > 1:
            straddled.append(event.ex_date)
    return forced_price, forced_volume, straddled


def _resolve_pass(
    win: Sequence[EventSpec],
    cumulative: Decimal | None,
    canonical: Mapping[date, tuple[str, Decimal]],
    *,
    get_ours,
    oracle,
    costs: Mapping[str, int] = _COST,
    price_factors: Mapping[date, Decimal] | None = None,
    forced: Mapping[date, tuple[str, Decimal]] | None = None,
) -> dict[date, tuple[str, Decimal]] | None:
    """Resolve one era for ONE pass (price or volume). Returns per-event (source, factor) or None.

    Each event gets a small candidate list; a NEW event (not yet in ``canonical``) may be OURS /
    ABSENT / a freshly-SOLVED measured value / -- on the VOLUME pass only -- its own chosen PRICE
    FACTOR; a CARRIED event keeps its canonical source (a no-ours event may also flip to ABSENT --
    the era-inconsistency). At most one freshly-solved measured per assignment (never two unknowns
    from one equation). The min-cost passing assignment wins, costed by ``costs``.

    Args:
        cumulative: the era's measured cumulative observable, or ``None`` when no measured candidate
            may be offered at all (Q-12: fewer than :data:`MIN_VOLUME_ESTIMATOR_DAYS` price-passing
            probe days means the volume observable was not measured, so nothing is SOLVEd).
        costs: :data:`_COST` for price, :data:`_VOLUME_COST` for volume (the Q-12 order).
        price_factors: VOLUME pass only -- each event's already-chosen PRICE factor, offered as the
            :data:`SOURCE_PRICE_FACTOR` candidate. A price factor of exactly 1 is NOT offered: that
            is what ``absent`` means, and relabelling a vendor omission as a measurement would make
            the audit row lie.
        forced: events a MEASURED vendor application floor puts below the vendor's splice for this
            whole era (Q-11 addendum 4). They get exactly ONE option -- the measurement -- so the
            arbitration cannot re-open a question the probes already answered.
    """
    fixed = forced or {}
    option_lists: list[list[tuple[str, object, int]]] = []
    for e in win:
        ours = get_ours(e)
        from_price = None if price_factors is None else price_factors.get(e.ex_date)
        opts: list[tuple[str, object, int]] = []
        if e.ex_date in fixed:
            source, value = fixed[e.ex_date]
            option_lists.append([(source, value, costs.get(source, 0))])
            continue
        if e.ex_date in canonical:
            csrc, cval = canonical[e.ex_date]
            if csrc == SOURCE_OURS:
                opts.append((SOURCE_OURS, ours if ours is not None else cval, costs[SOURCE_OURS]))
            elif csrc == SOURCE_PRICE_FACTOR:
                # Carried: this event's volume TRACKS its price factor, so the value is read from
                # THIS era's price resolution, not from the older era's number. That matters when the
                # price side FLIPPED to absent in this era (the era-inconsistency): the volume must
                # flip with it -- and then the honest label is ABSENT, because a factor of 1 is a
                # vendor omission, not a measurement.
                tracked = cval if from_price is None else from_price
                if tracked == _ONE:
                    opts.append((SOURCE_ABSENT, _ONE, costs[SOURCE_ABSENT]))
                else:
                    opts.append((SOURCE_PRICE_FACTOR, tracked, costs[SOURCE_PRICE_FACTOR]))
            elif csrc == SOURCE_MEASURED:
                # A carried MEASURED event is a SINGLE observed scalar (the ruling's "single
                # scalar per event"): it uses that canonical value, never a fresh re-solve --
                # otherwise a demerger measured ~0.908 where it IS applied could shape-shift to
                # absorb the rights' residual in an era where it is NOT applied. A no-ours event
                # (a demerger) may instead VANISH (the era-inconsistency); a with-ours event
                # (a rights whose vendor factor differs from our TERP) stays measured.
                opts.append((SOURCE_MEASURED, cval, costs[SOURCE_MEASURED]))
                if ours is None:
                    opts.append((SOURCE_ABSENT, _ONE, costs[SOURCE_ABSENT]))
            else:  # carried ABSENT
                opts.append((SOURCE_ABSENT, _ONE, costs[SOURCE_ABSENT]))
        else:
            if ours is not None:
                opts.append((SOURCE_OURS, ours, costs[SOURCE_OURS]))
            if from_price is not None and from_price != _ONE:
                # A chosen price factor of exactly 1 is not offered under this label: that IS what
                # ABSENT means, and relabelling a vendor omission as a measurement would make the
                # audit row lie. ABSENT is already in the list below.
                opts.append((SOURCE_PRICE_FACTOR, from_price, costs[SOURCE_PRICE_FACTOR]))
            opts.append((SOURCE_ABSENT, _ONE, costs[SOURCE_ABSENT]))
            if cumulative is not None:
                opts.append((SOURCE_MEASURED, "SOLVE", costs[SOURCE_MEASURED]))
        option_lists.append(opts)

    best: tuple[int, int, dict[date, tuple[str, Decimal]]] | None = None
    for combo in product(*option_lists):
        if sum(1 for src, val, _ in combo if val == "SOLVE") > 1:
            continue
        known = _ONE
        solve_index = -1
        for i, (src, val, _cost) in enumerate(combo):
            if val == "SOLVE":
                solve_index = i
            else:
                known *= val  # type: ignore[operator]
        assignment: dict[date, tuple[str, Decimal]] = {}
        ok = True
        if solve_index >= 0:
            if known == 0 or cumulative is None:
                continue
            solved = cumulative / known
            e = win[solve_index]
            if not _valid_measured(e, solved):
                continue
            assignment[e.ex_date] = (SOURCE_MEASURED, solved)
        k_chain = _ONE
        for i, (src, val, _cost) in enumerate(combo):
            e = win[i]
            if i == solve_index:
                factor = assignment[e.ex_date][1]
            else:
                factor = val  # type: ignore[assignment]
                assignment[e.ex_date] = (src, factor)
            k_chain *= factor
        if not oracle(k_chain, assignment):
            continue
        cost = sum(c for _s, _v, c in combo)
        measured_count = sum(1 for s, _f in assignment.values() if s == SOURCE_MEASURED)
        key = (cost, measured_count)
        if best is None or key < best[:2]:
            best = (cost, measured_count, assignment)
    return None if best is None else best[2]


def _valid_measured(event: EventSpec, value: Decimal) -> bool:
    """A solved measured factor must be positive, and a discount (<= 1) for anything but a split."""
    if value <= 0:
        return False
    if event.kind == KIND_SPLIT:
        return True  # a consolidation (reverse split) legitimately has k > 1
    return value <= _MEASURED_UPPER


def _refine_scalars(
    decided: Mapping[tuple[date, ...], Mapping[date, tuple[str, Decimal, str, Decimal]] | None],
    by_key: Mapping[tuple[date, ...], EraMeasurement],
    by_ex: Mapping[date, EventSpec],
    which: str,
    *,
    price_chains: Mapping[tuple[date, ...], Decimal] | None = None,
    price_tol_paise: int = DEFAULT_PRICE_CONTAINMENT_PAISE,
) -> dict[date, Decimal]:
    """Refine each MEASURED event's scalar over ALL its pre-ex probe days. PURE.

    An event's pre-ex days span EVERY era in which it is applied (the rights sits in both RELIANCE's
    2016 and 2019 eras). Isolating the one event on a probe day means dividing the day's cumulative
    observable (``fetched/raw`` for price, ``raw/fetched`` for volume) by the OTHER in-era events'
    resolved factors. The result only tightens containment and never changes a source label (that
    was fixed in phase 1). Assumes at most one MEASURED event per era for a given pass (guaranteed
    by the <=1-fresh-solve rule), so the "other" events are always known exactly.

    The two sides use the estimator each was ruled: **price = the MEDIAN** over its days (the
    observable is symmetric), **volume = the MINIMUM over the days whose PRICE containment passes**
    (Q-12 clause i -- the auction contaminates the volume observable in one direction only). The
    volume side therefore needs ``price_chains``: each era's committed ``k_price``, against which
    the per-day containment filter runs. Without it (price pass) no filter applies.

    A measured event with fewer than :data:`MIN_VOLUME_ESTIMATOR_DAYS` qualifying volume days is
    OMITTED from the result -- the caller then keeps the phase-1 solved value, which was itself
    admitted only against a qualifying estimator.
    """
    per_event: dict[date, list[Decimal]] = {}
    for key, choice in decided.items():
        if choice is None:
            continue
        era = by_key[key]
        for ex, (psrc, pval, vsrc, vval) in choice.items():
            src = psrc if which == "price" else vsrc
            if src != SOURCE_MEASURED:
                continue
            others = _ONE
            for other_ex, (ops, opv, ovs, ovv) in choice.items():
                if other_ex == ex:
                    continue
                others *= opv if which == "price" else ovv
            if others == 0:
                continue
            if which == "price":
                for p in era.probe_days:
                    for fetched, raw in ((p.fetched_high, p.raw_high), (p.fetched_low, p.raw_low)):
                        per_event.setdefault(ex, []).append(
                            (Decimal(fetched) / Decimal(raw)) / others
                        )
            else:
                k_price = None if price_chains is None else price_chains.get(key)
                days = (
                    era.probe_days if k_price is None
                    else price_passing_probe_days(era, k_price, price_tol_paise)
                )
                for p in days:
                    per_event.setdefault(ex, []).append(p.volume_recovery() / others)
    if which == "price":
        return {ex: _median(vals) for ex, vals in per_event.items() if vals}
    return {
        ex: min(vals)
        for ex, vals in per_event.items()
        if len(vals) >= MIN_VOLUME_ESTIMATOR_DAYS
    }


def _factor_for_source(
    event: EventSpec, source: str, refined: Decimal | None, *, price: bool
) -> Decimal:
    """The factor to commit for one event given its resolved SOURCE and refined scalar. PURE."""
    if source == SOURCE_PRICE_FACTOR:  # resolved by the caller from the committed price factor
        raise VendorAdjustmentError(
            f"{event.kind}@{event.ex_date}: {SOURCE_PRICE_FACTOR} must be resolved from the "
            "event's committed price factor, not from a refined scalar"
        )
    if source == SOURCE_ABSENT:
        return _ONE
    if source == SOURCE_OURS:
        ours = event.our_price_factor if price else event.our_volume_factor()
        if ours is None:  # defensive: a no-ours event should never be labelled OURS
            raise VendorAdjustmentError(f"{event.kind}@{event.ex_date}: OURS with no ours-factor")
        return ours
    if refined is None:
        raise VendorAdjustmentError(f"{event.kind}@{event.ex_date}: MEASURED with no refined scalar")
    return refined


# --- the oracles (PURE) ----------------------------------------------------------------


def _price_residuals(era: EraMeasurement, k_price: Decimal) -> list[int]:
    """|un-adjusted high/low - raw daily|, one entry per (probe day, {high, low}), in paise."""
    if k_price <= 0:
        return [1 << 30]
    residuals: list[int] = []
    for p in era.probe_days:
        for fetched, raw in ((p.fetched_high, p.raw_high), (p.fetched_low, p.raw_low)):
            un, _snap, _off = unadjust_price_paise(fetched, k_price, tick_paise=None)
            residuals.append(abs(un - raw))
    return residuals


def _price_residual_paise(era: EraMeasurement, k_price: Decimal) -> int:
    """Max |un-adjusted high/low - raw daily| over the era's probe days, in paise (reporting)."""
    return max(_price_residuals(era, k_price), default=0)


def _price_contained(era: EraMeasurement, k_price: Decimal, tol_paise: int) -> bool:
    """EVERY probe day's un-adjusted high/low must land within tolerance of the raw daily. PURE.

    Per-day (not median): a bimodal era -- the vendor's re-adjustment floor falling inside one era
    key so a MINORITY of days carry a different factor -- must be caught, because consumption
    applies ONE factor to the whole era and gate 1 (volume) cannot see a price error. So a single
    day off by an adjustment-sized amount fails the era (it is un-provable -> excluded).

    The tolerance is ``max(tol_paise, raw x`` :data:`_PRICE_CONTAINMENT_REL` ``)`` -- 2 paise, OR
    0.1% of the price, whichever is larger. The relative floor absorbs genuine market microstructure
    (the fold high/low can differ from the official daily high/low by a few paise -- an odd-lot /
    block trade the bhavcopy counts but the continuous 1-min series does not, ~0.01%; the same
    reason gate-1's band skews positive) WITHOUT admitting a wrong factor: the smallest wrong-factor
    residual is the rights ours-vs-vendor gap (~0.33%), three-fold above the 0.1% floor, and every
    other wrong choice (rights not-applied ~1.3%, demerger ~9%, bonus ~50%) is far larger.
    """
    if k_price <= 0:
        return False
    return all(_day_price_contained(p, k_price, tol_paise) for p in era.probe_days)


def _day_price_contained(probe: ProbeDay, k_price: Decimal, tol_paise: int) -> bool:
    """One probe day's containment test -- the per-day unit :func:`_price_contained` quantifies over.

    Split out (not new arithmetic) because the Q-12 volume estimator needs the SAME per-day verdict
    to decide which days may set the volume floor (:func:`price_passing_probe_days`).
    """
    if k_price <= 0:
        return False
    for fetched, raw in ((probe.fetched_high, probe.raw_high), (probe.fetched_low, probe.raw_low)):
        if raw <= 0:
            return False
        un, _snap, _off = unadjust_price_paise(fetched, k_price, tick_paise=None)
        limit = price_containment_limit(raw, tol_paise)
        if abs(Decimal(un - raw)) > limit:
            return False
    return True


def _volume_gap_pct(era: EraMeasurement, k_volume: Decimal) -> Decimal | None:
    """The median per-day gate-1 gap after un-adjusting volume by ``k_volume``."""
    gaps: list[Decimal] = []
    for p in era.probe_days:
        un = unadjust_volume(p.fetched_volume, k_volume)
        result = volume_gate(p.raw_volume, un)
        if result.gap_pct is not None:
            gaps.append(result.gap_pct)
    if not gaps:
        return None
    return _median(gaps)


def _volume_reconciled(era: EraMeasurement, k_volume: Decimal) -> bool:
    """Every probe day's un-adjusted volume must pass gate 1 (the band is NOT widened)."""
    if k_volume <= 0:
        return False
    for p in era.probe_days:
        un = unadjust_volume(p.fetched_volume, k_volume)
        if not volume_gate(p.raw_volume, un).passed:
            return False
    return True


def _era_note(era: EraMeasurement, choices: Sequence[EventChoice], provable: bool, *, reason: str = "") -> str:
    if not provable:
        why = reason or "no candidate chain satisfies price containment + gate-1"
        return (
            f"UN-PROVABLE ({why}) for era {era.label} "
            f"(events {[ex.isoformat() for ex in era.ex_dates]}); excluded + counted"
        )
    if not choices:
        return f"identity era {era.label}: no events in (D, F]; fetched == raw"
    parts = []
    for c in choices:
        parts.append(f"{c.kind}@{c.ex_date.isoformat()} price={c.price_source} vol={c.volume_source}")
    return f"era {era.label}: " + "; ".join(parts)


# --- consumption: un-adjust bars via the map (PURE) ------------------------------------


def unadjust_with_map(
    bars: Sequence[OneMinuteBar],
    adjustment_map: AdjustmentMap,
    *,
    symbol: str,
    tick_paise: int | None = None,
    tol_paise: int = DEFAULT_TICK_SNAP_TOLERANCE_PAISE,
) -> UnadjustResult:
    """Un-adjust fetched bars to RAW using the committed map (Q-11). PURE.

    Groups bars by trade date; for each day it looks up the era covering it and forms
    ``k_price``/``k_volume`` from the chosen per-event factors. A day whose era is missing or
    un-provable is marked ``provable=False`` -- the partial (identity) bars are still emitted so the
    day is visible, but gate 1 will exclude and count it (CONTEXT 7-E3). ``k_price == 1`` is the
    exact identity (a recent day / an unprobed identity era), stored byte-for-byte.
    """
    by_day: dict[date, list[OneMinuteBar]] = {}
    for bar in bars:
        by_day.setdefault(bar.stamp.date(), []).append(bar)

    raw_bars: list[OneMinuteBar] = []
    day_reports: list[DayUnadjust] = []
    for day in sorted(by_day):
        factors = adjustment_map.factors_for_day(day)
        provable = factors is not None
        k_price, k_volume = factors if factors is not None else (_ONE, _ONE)
        era = adjustment_map.era_for_day(day)
        snapped = flagged = off_max = 0
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
                    volume=unadjust_volume(bar.volume, k_volume),
                )
            )
        day_reports.append(
            DayUnadjust(
                day=day,
                fetch_date=adjustment_map.fetch_date,
                k_price=k_price,
                k_shares=k_volume,
                identity=(k_price == _ONE and k_volume == _ONE),
                provable=provable,
                snapped=snapped,
                tick_flagged=flagged,
                off_grid_max_paise=off_max,
                reason=_day_reason(day, era, provable, k_price, k_volume, flagged),
            )
        )
    return UnadjustResult(raw_bars=tuple(raw_bars), days=tuple(day_reports))


def _day_reason(
    day: date, era: EraResolution | None, provable: bool, k_price: Decimal, k_volume: Decimal, flagged: int
) -> str:
    if not provable:
        which = "unprobed era" if era is None else f"un-provable era {era.label}"
        return f"UN-PROVABLE: {which}; gate 1 will exclude and count this day"
    if k_price == _ONE and k_volume == _ONE:
        return "identity (k_price = k_volume = 1): stored exactly as fetched"
    note = f"un-adjusted via map: price / k_price={k_price}, volume x k_volume={k_volume}"
    if flagged:
        note += f"; {flagged} price(s) > tolerance off the tick grid (flagged)"
    return note


# --- persistence (I/O) -----------------------------------------------------------------


def map_path(symbol: str, data_dir: Path | None = None) -> Path:
    """Where a symbol's committed adjustment map lives (``data/`` is gitignored)."""
    base = Path(data_dir) if data_dir is not None else _default_data_dir()
    return base / "adjustment_maps" / f"{symbol.strip().upper()}.json"


def _default_data_dir() -> Path:
    from .config import load_config  # local: building a map must not require a config file

    return load_config(include_env=False).path("data_dir")


def _probe_to_dict(p: FloorProbe) -> dict:
    return {
        "day": p.day.isoformat(),
        "verdict": p.verdict,
        "k_in": None if p.k_in is None else str(p.k_in),
        "k_out": None if p.k_out is None else str(p.k_out),
        "ratio_high": None if p.ratio_high is None else str(p.ratio_high),
        "ratio_low": None if p.ratio_low is None else str(p.ratio_low),
    }


def _probe_from_dict(p: Mapping) -> FloorProbe:
    return FloorProbe(
        day=date.fromisoformat(str(p["day"])),
        verdict=str(p["verdict"]),
        k_in=None if p.get("k_in") is None else Decimal(str(p["k_in"])),
        k_out=None if p.get("k_out") is None else Decimal(str(p["k_out"])),
        ratio_high=None if p.get("ratio_high") is None else Decimal(str(p["ratio_high"])),
        ratio_low=None if p.get("ratio_low") is None else Decimal(str(p["ratio_low"])),
    )


def to_dict(adjustment_map: AdjustmentMap) -> dict:
    """A JSON-ready dict of the map (Decimals as strings, dates as ISO). PURE."""
    return {
        "symbol": adjustment_map.symbol,
        "fetch_date": adjustment_map.fetch_date.isoformat(),
        "tick_paise": adjustment_map.tick_paise,
        "volume_estimator": adjustment_map.volume_estimator_id,
        "map_model": adjustment_map.map_model_id,
        "all_event_ex_dates": [d.isoformat() for d in adjustment_map.all_event_ex_dates],
        "floors": [
            {
                "ex_date": floor.ex_date.isoformat(),
                "floor_date": None if floor.floor_date is None else floor.floor_date.isoformat(),
                "resolved": floor.resolved,
                "absent_throughout": floor.absent_throughout,
                "event_price_factor": (
                    None if floor.event_price_factor is None else str(floor.event_price_factor)
                ),
                "note": floor.note,
                "probes": [_probe_to_dict(p) for p in floor.probes],
                # --- the VOLUME side (QUESTIONS.md Q-14 per-side floors) ---------------------
                "floor_volume": (
                    None if floor.floor_volume is None else floor.floor_volume.isoformat()
                ),
                "volume_resolved": floor.volume_resolved,
                "volume_measured": floor.volume_measured,
                "volume_note": floor.volume_note,
                "event_volume_factor": (
                    None if floor.event_volume_factor is None else str(floor.event_volume_factor)
                ),
                "volume_probes": [_probe_to_dict(p) for p in floor.volume_probes],
            }
            for floor in adjustment_map.floors
        ],
        "eras": [
            {
                "label": era.label,
                "ex_dates": [d.isoformat() for d in era.ex_dates],
                "k_price": str(era.k_price),
                "k_volume": str(era.k_volume),
                "price_containment_paise": era.price_containment_paise,
                "volume_gap_pct": None if era.volume_gap_pct is None else str(era.volume_gap_pct),
                "provable": era.provable,
                "probe_days": [d.isoformat() for d in era.probe_days],
                "note": era.note,
                "choices": [
                    {
                        "kind": c.kind,
                        "ex_date": c.ex_date.isoformat(),
                        "price_factor": str(c.price_factor),
                        "price_source": c.price_source,
                        "volume_factor": str(c.volume_factor),
                        "volume_source": c.volume_source,
                    }
                    for c in era.choices
                ],
            }
            for era in adjustment_map.eras
        ],
    }


def from_dict(payload: Mapping) -> AdjustmentMap:
    """Rebuild an :class:`AdjustmentMap` from :func:`to_dict`'s shape. PURE."""
    try:
        eras = tuple(
            EraResolution(
                label=str(e["label"]),
                ex_dates=tuple(date.fromisoformat(d) for d in e["ex_dates"]),
                choices=tuple(
                    EventChoice(
                        kind=str(c["kind"]),
                        ex_date=date.fromisoformat(c["ex_date"]),
                        price_factor=Decimal(str(c["price_factor"])),
                        price_source=str(c["price_source"]),
                        volume_factor=Decimal(str(c["volume_factor"])),
                        volume_source=str(c["volume_source"]),
                    )
                    for c in e["choices"]
                ),
                k_price=Decimal(str(e["k_price"])),
                k_volume=Decimal(str(e["k_volume"])),
                price_containment_paise=int(e["price_containment_paise"]),
                volume_gap_pct=None if e["volume_gap_pct"] is None else Decimal(str(e["volume_gap_pct"])),
                provable=bool(e["provable"]),
                probe_days=tuple(date.fromisoformat(d) for d in e["probe_days"]),
                note=str(e.get("note", "")),
            )
            for e in payload["eras"]
        )
        floors = tuple(
            EventFloor(
                ex_date=date.fromisoformat(str(f["ex_date"])),
                floor_date=(
                    None if f.get("floor_date") is None else date.fromisoformat(str(f["floor_date"]))
                ),
                resolved=bool(f["resolved"]),
                probes=tuple(_probe_from_dict(p) for p in f.get("probes", ())),
                note=str(f.get("note", "")),
                event_price_factor=(
                    None if f.get("event_price_factor") is None
                    else Decimal(str(f["event_price_factor"]))
                ),
                # Q-14 per-side floors. A map written before the ruling carries none of these keys,
                # so ``volume_measured`` reads False and the volume chain follows the PRICE floor
                # exactly as it did then -- the committed map's behaviour is unchanged.
                floor_volume=(
                    None if f.get("floor_volume") is None
                    else date.fromisoformat(str(f["floor_volume"]))
                ),
                volume_resolved=bool(f.get("volume_resolved", False)),
                volume_measured=bool(f.get("volume_measured", False)),
                volume_probes=tuple(_probe_from_dict(p) for p in f.get("volume_probes", ())),
                volume_note=str(f.get("volume_note", "")),
                event_volume_factor=(
                    None if f.get("event_volume_factor") is None
                    else Decimal(str(f["event_volume_factor"]))
                ),
            )
            for f in payload.get("floors", ())
        )
        return AdjustmentMap(
            symbol=str(payload["symbol"]),
            fetch_date=date.fromisoformat(str(payload["fetch_date"])),
            all_event_ex_dates=tuple(date.fromisoformat(d) for d in payload["all_event_ex_dates"]),
            eras=eras,
            tick_paise=payload.get("tick_paise"),
            # A map written before the Q-12 ruling carries no marker at all -> "" -> stale, which is
            # exactly right: it was built with the superseded median volume estimator.
            volume_estimator_id=str(payload.get("volume_estimator", "")),
            floors=floors,
            # Likewise: a map written before the FIX-3 rulings carries no model marker -> "" ->
            # stale, because its era keys predate compound + unparsed nodes.
            map_model_id=str(payload.get("map_model", "")),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise VendorAdjustmentError(f"cannot read adjustment map: {exc}") from exc


def map_is_current(adjustment_map: AdjustmentMap) -> bool:
    """Was this map built under the CURRENT estimator AND the current map model?

    A ``False`` here is not a corrupt file -- it is a map built under a superseded ruling. It must be
    REBUILT (probe windows only; no stored candle is refetched) rather than consumed, because:

    * a pre-Q-12 map's committed volume factors came from the biased median
      (:data:`MAP_VOLUME_ESTIMATOR`), and its un-provable eras may be provable under the ruled
      estimator;
    * a pre-FIX-3 map's ERA KEYS predate the compound and unparsed nodes
      (:data:`MAP_MODEL`), so it can be keyed on a set of ex-dates this builder no longer produces.
    """
    return (
        adjustment_map.volume_estimator_id == MAP_VOLUME_ESTIMATOR
        and adjustment_map.map_model_id == MAP_MODEL
    )


def persist_map(adjustment_map: AdjustmentMap, data_dir: Path | None = None) -> Path:
    """Write the map to ``data/adjustment_maps/<SYMBOL>.json`` (gitignored) ATOMICALLY.

    REVIEW_5B finding C4: this was the only store write in the repo that bypassed
    :mod:`acumen.atomic_io` -- a plain truncate-then-write, with no temp file, no fsync and no
    rename. The map is the artifact the Q-11 addendum-2 ruling commits a floor's probe evidence to,
    so a torn write loses exactly the provenance the ruling exists to preserve. It now goes through
    the same temp -> fsync -> rename path (with the bounded retry the 2026-07-25 power-loss incident
    hardened) as the parquet stores and the run ledger.
    """
    path = map_path(adjustment_map.symbol, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    return atomic_write_text(path, json.dumps(to_dict(adjustment_map), indent=2))


def load_map(symbol: str, data_dir: Path | None = None) -> AdjustmentMap:
    """Read a committed adjustment map from ``data/``.

    A torn or malformed file raises :class:`VendorAdjustmentError` like every other unreadable map
    (REVIEW_5B finding C4: ``json.JSONDecodeError`` escaped all four guards written for exactly this
    case, so a damaged map aborted the run with a raw traceback instead of the designed rebuild).
    """
    path = map_path(symbol, data_dir)
    if not path.is_file():
        raise VendorAdjustmentError(f"no adjustment map for {symbol} at {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VendorAdjustmentError(
            f"the adjustment map at {path} will not parse ({exc}). It is a MEASURED artifact, not "
            "a cache: rebuilding it re-probes the symbol's eras. Move it aside and re-run the "
            "backfill for this symbol."
        ) from exc
    return from_dict(payload)


# --- live measurement (I/O; opt-in) ----------------------------------------------------


@dataclass(frozen=True)
class WindowSpec:
    """One probe window: a small span of pre-ex days in one era, fetched in a single call."""

    label: str
    start: date
    end: date


def is_measurable_session(day: date) -> bool:
    """May a vendor factor be MEASURED on this session? PURE.

    The Q-5 ruling: "weekend-dated sessions are EXCLUDED from trading days, bias pairs, and
    trading, even when a bhavcopy exists" -- :meth:`acumen.calendar.TradingCalendar.is_trading_day`
    answers False for one. A day that is not a trading day must not be a measurement day either.

    This is enforced at BOTH ends, which is not belt-and-braces: a probe WINDOW is a date RANGE
    (one call for four pre-ex sessions), so dropping the weekend from the chosen days still leaves
    the vendor free to return it inside the range. It is therefore filtered again when the fetched
    bars are folded into an era, and once more per single-day probe.

    Measured live, and this is why it matters: NSE's Saturday 2024-05-18 special session lands
    inside BDL's and INOXWIND's pre-ex probe windows, and the vendor's 1-minute volume for it
    recovers only 0.259 / 0.196 of the raw daily against 0.500 / 0.246 on the real sessions beside
    it. Gate-1 reconciliation must hold on EVERY probe day, so that one session made the only
    correct chain un-provable and cost those two symbols 2,391 stored days. No oracle is widened
    here -- the band, the containment and the candidate sets are untouched; an excluded session
    simply stops being used as evidence.
    """
    return day.weekday() < 5


def fold_bars(bars: Sequence[OneMinuteBar]) -> dict[date, dict[str, int]]:
    """Fold fetched 1-minute bars into per-day daily OHLC + summed volume (integer paise). PURE."""
    by_day: dict[date, list[OneMinuteBar]] = {}
    for b in bars:
        by_day.setdefault(b.stamp.date(), []).append(b)
    out: dict[date, dict[str, int]] = {}
    for day, bs in by_day.items():
        bs.sort(key=lambda x: x.stamp)
        out[day] = {
            "high": max(x.high_paise for x in bs),
            "low": min(x.low_paise for x in bs),
            "close": bs[-1].close_paise,
            "volume": sum(x.volume for x in bs),
            "n": len(bs),
        }
    return out


def measure_symbol_live(
    client,
    daily_store,
    symbol: str,
    token: str,
    events: Sequence[EventSpec],
    windows: Sequence[WindowSpec],
    fetch_date: date,
    *,
    on_window: Callable[[WindowSpec, int], None] | None = None,
) -> list[EraMeasurement]:
    """Fetch the probe windows, fold them, and group into per-era measurements. I/O.

    For each window one credentialed ONE_MINUTE call is made (the client is paced and backs off --
    :mod:`acumen.smartapi_client`). Each fetched day is compared to the RAW daily store; days are
    grouped by their in-window event set (the era key ``{ex : D < ex <= fetch_date}``), so several
    windows can feed the same era (2022-07 and 2023-06 share RELIANCE's demerger era). Empty or
    raw-missing days are skipped (and reported by the caller if it wants).
    """
    all_ex = sorted(e.ex_date for e in events)
    era_days: dict[tuple[date, ...], list[ProbeDay]] = defaultdict(list)
    era_labels: dict[tuple[date, ...], set[str]] = defaultdict(set)
    for w in windows:
        bars = client.get_candles(
            token, INTERVAL_ONE_MINUTE,
            datetime.combine(w.start, time(9, 15)), datetime.combine(w.end, time(15, 30)),
        )
        folds = fold_bars(bars)
        if on_window is not None:
            on_window(w, len(folds))
        for day, m in folds.items():
            if not is_measurable_session(day):
                continue  # Q-5: a weekend-dated session is not a trading day, so not evidence
            frame = daily_store.daily(symbol, day, day)
            if frame.empty:
                continue
            row = frame.iloc[0]
            probe = ProbeDay(
                day=day,
                fetched_high=m["high"], fetched_low=m["low"], fetched_close=m["close"],
                fetched_volume=m["volume"],
                raw_high=int(row["high_paise"]), raw_low=int(row["low_paise"]),
                raw_close=int(row["close_paise"]), raw_volume=int(row["volume"]),
            )
            key = tuple(ex for ex in all_ex if day < ex <= fetch_date)
            era_days[key].append(probe)
            era_labels[key].add(w.label)
    return [
        measure_era(key, "+".join(sorted(era_labels[key])), days)
        for key, days in era_days.items()
    ]


def probe_one_day(client, daily_store, symbol: str, token: str, day: date) -> ProbeDay | None:
    """Fetch ONE day of 1-minute bars, fold it, and pair it with the RAW daily row. I/O.

    The unit of a floor binary search (Q-11 addendum 2): one credentialed ONE_MINUTE call for a
    single session, folded to a daily OHLC and compared against the chunk-2 raw daily store --
    exactly the observable :func:`measure_symbol_live` builds an era from, for one day. Returns
    ``None`` when the vendor served nothing for that day, when the daily store has no row for it,
    or when the day is not a trading session at all (Q-5) -- each of which is a day that answers
    nothing, which the classifier then reports as undecided.
    """
    if not is_measurable_session(day):
        return None
    bars = client.get_candles(
        token,
        INTERVAL_ONE_MINUTE,
        datetime.combine(day, time(9, 15)),
        datetime.combine(day, time(15, 30)),
    )
    folds = fold_bars(bars)
    fold = folds.get(day)
    if fold is None:
        return None
    frame = daily_store.daily(symbol, day, day)
    if frame.empty:
        return None
    row = frame.iloc[0]
    return ProbeDay(
        day=day,
        fetched_high=fold["high"], fetched_low=fold["low"], fetched_close=fold["close"],
        fetched_volume=fold["volume"],
        raw_high=int(row["high_paise"]), raw_low=int(row["low_paise"]),
        raw_close=int(row["close_paise"]), raw_volume=int(row["volume"]),
    )


def era_chain_without(
    era: EraResolution | Sequence[EventChoice],
    day_map: AdjustmentMap,
    day: date,
    *,
    drop_ex_date: date | None,
) -> Decimal:
    """The era's PRICE chain at ``day``, with ``drop_ex_date``'s event removed. PURE.

    Every other event is applied exactly as the era committed it, minus any whose already-measured
    floor sits above ``day`` -- so a second event's floor, once found, is honoured while a third
    event's floor is searched. This is the arithmetic the floor classifier's two hypotheses are
    built from.

    Accepts an :class:`EraResolution` (the committed case) or a bare sequence of
    :class:`EventChoice` (Q-11 addendum 4: an UN-PROVABLE era's :func:`era_hypothesis`, which has no
    committed resolution to read).
    """
    chain = _ONE
    choices = era.choices if isinstance(era, EraResolution) else era
    for choice in choices:
        if choice.ex_date == drop_ex_date:
            continue
        if not day_map.event_applies_on(choice.ex_date, day):
            continue
        chain *= choice.price_factor
    return chain


def search_event_floor_live(
    probe: Callable[[date], ProbeDay | None],
    adjustment_map: AdjustmentMap,
    ex_date: date,
    days: Sequence[date],
    *,
    tol_paise: int = DEFAULT_PRICE_CONTAINMENT_PAISE,
    max_probes: int = MAX_FLOOR_PROBES,
    on_probe: Callable[[FloorProbe], None] | None = None,
    hypotheses: Mapping[tuple[date, ...], tuple[EventChoice, ...]] | None = None,
    allow_absent_throughout: bool = False,
) -> EventFloor:
    """Measure ONE event's vendor application floor (Q-11 addendum 2 / 4). I/O via ``probe``.

    ``days`` are candidate trading days strictly before ``ex_date``. A day inside a PROVABLE era is
    classified against the chain that era actually committed -- so a symbol whose event resolved
    differently in different eras is still tested honestly.

    ``hypotheses`` (Q-11 addendum 4) maps an UN-PROVABLE era's key to the chain
    :func:`era_hypothesis` built for it from previously committed sources; without an entry such a
    day answers nothing, exactly as before the ruling. ``allow_absent_throughout`` passes the
    ex-date to :func:`binary_search_floor` as its ``absent_floor_date``, admitting the "the vendor
    never applied this event to one day of our history" outcome -- which requires three ``event-out``
    probes, not one.
    """
    chains = hypotheses or {}
    event_factor: Decimal | None = None

    def classify(day: date) -> FloorProbe:
        nonlocal event_factor
        era = adjustment_map.era_for_day(day)
        if era is None:
            return FloorProbe(day=day, verdict=FLOOR_UNDECIDED)
        choices = era.choices if era.provable else chains.get(era.ex_dates)
        if not choices:
            return FloorProbe(day=day, verdict=FLOOR_UNDECIDED)
        factor = next((c.price_factor for c in choices if c.ex_date == ex_date), None)
        if factor is None or factor == _ONE:
            # Nothing to test: this era does not carry the event, or carries it as ABSENT (factor
            # 1), in which case "in" and "out" are the same chain and the day answers nothing.
            return FloorProbe(day=day, verdict=FLOOR_UNDECIDED)
        event_factor = factor
        k_out = era_chain_without(choices, adjustment_map, day, drop_ex_date=ex_date)
        k_in = k_out * factor
        measured = probe(day)
        if measured is None:
            return FloorProbe(day=day, verdict=FLOOR_UNDECIDED, k_in=k_in, k_out=k_out)
        high_ratio, low_ratio = measured.price_ratios()
        return FloorProbe(
            day=day,
            verdict=classify_floor_day(measured, k_in, k_out, tol_paise),
            k_in=k_in, k_out=k_out, ratio_high=high_ratio, ratio_low=low_ratio,
        )

    def classify_and_report(day: date) -> FloorProbe:
        result = classify(day)
        if on_probe is not None:
            on_probe(result)
        return result

    search = binary_search_floor(
        days, classify_and_report, max_probes=max_probes,
        absent_floor_date=ex_date if allow_absent_throughout else None,
    )
    return EventFloor(
        ex_date=ex_date,
        floor_date=search.floor_date,
        resolved=search.resolved,
        probes=search.probes,
        note=search.note,
        event_price_factor=event_factor,
    )


def search_event_floor_stored(
    stored: Mapping[date, StoredDay],
    adjustment_map: AdjustmentMap,
    ex_date: date,
    days: Sequence[date],
    *,
    side: str = FLOOR_SIDE_PRICE,
    tol_paise: int = DEFAULT_PRICE_CONTAINMENT_PAISE,
    max_probes: int = MAX_FLOOR_PROBES,
    allow_absent_throughout: bool = False,
) -> tuple[FloorSearch, Decimal | None]:
    """Measure ONE side of ONE event's vendor application floor FROM THE STORE. PURE.

    The Q-14 ruling's "measured by the same bisection under the same guards": this drives the very
    same :func:`binary_search_floor` -- same probe budget, same undecided-step allowance, same
    three-probe ``absent throughout`` rule, same "one event-in or one undecided leaves it
    UNRESOLVED" -- with a classifier that reads the STORE instead of the vendor
    (:func:`classify_stored_price_day` / :func:`classify_stored_volume_day`, decision B143). It
    therefore spends ZERO credentialed calls and is reproducible offline by anyone holding the
    minute store and the daily store.

    ``days`` are candidate trading days strictly before ``ex_date``, each inside a PROVABLE era --
    that is what makes ``k_applied`` known, and the two hypotheses exact. Returns the search and the
    event factor its probes were classified under (committed as the floor's provenance).
    """
    event_factor: Decimal | None = None
    price_side = side == FLOOR_SIDE_PRICE

    def classify(day: date) -> FloorProbe:
        nonlocal event_factor
        era = adjustment_map.era_for_day(day)
        if era is None or not era.provable:
            return FloorProbe(day=day, verdict=FLOOR_UNDECIDED)
        choice = next((c for c in era.choices if c.ex_date == ex_date), None)
        if choice is None:
            return FloorProbe(day=day, verdict=FLOOR_UNDECIDED)
        factor = choice.price_factor if price_side else choice.volume_factor
        if factor == _ONE:
            # The era carries this event as ABSENT already: "in" and "out" are the same chain, so
            # the day answers nothing. Never guessed either way.
            return FloorProbe(day=day, verdict=FLOOR_UNDECIDED)
        day_row = stored.get(day)
        if day_row is None:
            return FloorProbe(day=day, verdict=FLOOR_UNDECIDED)
        event_factor = factor
        applied = adjustment_map.factors_for_day(day)
        k_applied = (applied[0] if price_side else applied[1]) if applied else None
        verdict = (
            classify_stored_price_day(day_row, factor, tol_paise) if price_side
            else classify_stored_volume_day(day_row, factor)
        )
        if price_side:
            ratio_high = Decimal(day_row.stored_high) / Decimal(day_row.raw_high) if day_row.raw_high else None
            ratio_low = Decimal(day_row.stored_low) / Decimal(day_row.raw_low) if day_row.raw_low else None
        else:
            recovery = (
                Decimal(day_row.stored_volume) / Decimal(day_row.raw_volume)
                if day_row.raw_volume else None
            )
            ratio_high = ratio_low = recovery
        return FloorProbe(
            day=day,
            verdict=verdict,
            k_in=k_applied,
            k_out=None if k_applied is None else (
                k_applied / factor if price_side else k_applied / factor
            ),
            ratio_high=ratio_high,
            ratio_low=ratio_low,
        )

    search = binary_search_floor(
        days, classify, max_probes=max_probes,
        absent_floor_date=ex_date if allow_absent_throughout else None,
    )
    return search, event_factor


def build_symbol_map_live(
    client,
    daily_store,
    symbol: str,
    token: str,
    events: Sequence[EventSpec],
    windows: Sequence[WindowSpec],
    fetch_date: date,
    *,
    tick_paise: int | None = None,
    price_tol_paise: int = DEFAULT_PRICE_CONTAINMENT_PAISE,
    on_window: Callable[[WindowSpec, int], None] | None = None,
    floors: Sequence[EventFloor] = (),
) -> AdjustmentMap:
    """Measure the probe windows live and build the map. I/O (the fetch), then PURE (the build)."""
    eras = measure_symbol_live(
        client, daily_store, symbol, token, events, windows, fetch_date, on_window=on_window
    )
    return build_map(
        symbol, fetch_date, events, eras,
        tick_paise=tick_paise, price_tol_paise=price_tol_paise, floors=floors,
    )
