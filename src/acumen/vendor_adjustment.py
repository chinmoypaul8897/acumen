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
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import ROUND_HALF_EVEN, Decimal
from itertools import product
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

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
from .quality_gates import volume_gate
from .smartapi_client import INTERVAL_ONE_MINUTE, OneMinuteBar

#: How close an un-adjusted HIGH/LOW must sit to the raw daily value to be "contained". The
#: ruling's "within 2 paise (scaled)": the vendor's cumulative rounding of a multi-factor chain
#: leaves the recovered raw price a hair off, and the measured factor is the median over an era's
#: probe days, so a specific day sits within the per-day spread of that median. Two paise covers
#: it while remaining three orders of magnitude below the ~0.3% rights and ~9% demerger errors a
#: WRONG factor leaves -- so the arbitration choice is never close (a wrong candidate misses by
#: hundreds of paise).
DEFAULT_PRICE_CONTAINMENT_PAISE: int = 2

#: Relative floor for price containment: a day is contained within max(2 paise, this x raw). 0.1%
#: absorbs market microstructure (fold-vs-daily-high divergence, ~0.01%) while staying well below
#: the smallest WRONG-factor residual (the rights ours-vs-vendor gap, ~0.33%) -- so a wrong factor
#: or a bimodal era still fails on the offending day. See :func:`_price_contained`.
_PRICE_CONTAINMENT_REL: Decimal = Decimal("0.001")

SOURCE_OURS: str = "ours"  # our CONTEXT 4.2 factor -- an exact known multiplier
SOURCE_MEASURED: str = "measured"  # the vendor's factor, measured from the fetched/raw ratio
SOURCE_ABSENT: str = "absent"  # the vendor did not apply this event in this era (factor 1.0)
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
class EventSpec:
    """One price-moving corporate action, with what we know about it (our factor, its kind).

    ``our_price_factor`` is our CONTEXT 4.2 multiplier, or ``None`` for a demerger / a rights whose
    issue price we could not recover (Q-6 tier 2) -- for those the vendor's factor is only ever an
    observation. ``is_share_count`` (a bonus/split/consolidation) means the vendor scales VOLUME by
    the same factor; a special dividend scales price but not volume, so its volume ``ours`` is 1.0.
    """

    kind: str
    ex_date: date
    our_price_factor: Decimal | None
    is_share_count: bool

    def our_volume_factor(self) -> Decimal | None:
        """The clean ``ours`` VOLUME candidate: the price factor for a share-count event, 1.0 for a
        cash dividend (volume never scales for it), else ``None`` (a rights/demerger volume factor is
        only ever measured -- the vendor scaled it by a value that differs from our TERP)."""
        if self.is_share_count:
            return self.our_price_factor
        if self.kind == KIND_DIVIDEND:
            return _ONE
        return None


def events_from_factor_table(
    factors: Iterable[Factor],
    suppressions: Iterable[Suppression] = (),
    pending_ex_dates: Iterable[date] = (),
    *,
    symbol: str | None = None,
) -> tuple[EventSpec, ...]:
    """Build the price-moving :class:`EventSpec` list from a chunk-3 factor table. PURE.

    Only events that MOVE a price or volume enter an era key: factors with ``k != 1`` (bonus,
    split, rights, special dividend), plus demergers and unrecoverable/pending rights (which carry
    no factor but the vendor may have adjusted by). Ordinary dividends (``k == 1``) are dropped --
    they neither move a price nor fragment an era.
    """
    wanted = None if symbol is None else symbol.strip().upper()
    specs: list[EventSpec] = []
    for f in factors:
        if wanted is not None and f.symbol != wanted:
            continue
        if f.k == _ONE:
            continue
        specs.append(
            EventSpec(
                kind=f.kind,
                ex_date=f.ex_date,
                our_price_factor=f.k,
                is_share_count=f.kind in (KIND_BONUS, KIND_SPLIT),
            )
        )
    for s in suppressions:
        if wanted is not None and s.symbol != wanted:
            continue
        specs.append(
            EventSpec(kind=s.kind, ex_date=s.ex_date, our_price_factor=None, is_share_count=False)
        )
    for ex in pending_ex_dates:
        specs.append(EventSpec(kind=KIND_RIGHTS, ex_date=ex, our_price_factor=None, is_share_count=False))
    specs.sort(key=lambda e: (e.ex_date, e.kind))
    return tuple(specs)


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

    def _era_index(self) -> dict[tuple[date, ...], EraResolution]:
        return {era.ex_dates: era for era in self.eras}

    def in_window_ex_dates(self, day: date) -> tuple[date, ...]:
        """The price-moving ex-dates in ``(day, fetch_date]`` -- the era key for ``day``."""
        return tuple(ex for ex in self.all_event_ex_dates if day < ex <= self.fetch_date)

    def era_for_day(self, day: date) -> EraResolution | None:
        """The resolved era covering ``day``, or ``None`` when that era was never probed."""
        return self._era_index().get(self.in_window_ex_dates(day))

    def factors_for_day(self, day: date) -> tuple[Decimal, Decimal] | None:
        """``(k_price, k_volume)`` for ``day``, or ``None`` when the day is un-provable.

        A day with NO price-moving event in ``(day, F]`` (an empty era key -- a recent, post-last-CA
        day) is the EXACT identity ``(1, 1)`` by definition: the vendor applied nothing, so fetched
        == raw. This holds even if no identity era was explicitly probed, so a recent RAW day is
        never wrongly excluded for want of a probe window. Otherwise ``None`` means the day's era was
        not probed or found no fitting candidate -- the day cannot be un-adjusted and gate 1 will
        exclude and count it.
        """
        if not self.in_window_ex_dates(day):
            return _ONE, _ONE
        era = self.era_for_day(day)
        if era is None or not era.provable:
            return None
        return era.k_price, era.k_volume


# --- the pure builder ------------------------------------------------------------------


def build_map(
    symbol: str,
    fetch_date: date,
    events: Sequence[EventSpec],
    era_measurements: Sequence[EraMeasurement],
    *,
    tick_paise: int | None = None,
    price_tol_paise: int = DEFAULT_PRICE_CONTAINMENT_PAISE,
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
        # PROBE-GAP guard: working backwards, a consecutively-probed era adds exactly ONE older
        # event. If an era introduces >1 event not already resolved by a newer era, an inter-event
        # era was NOT probed, so the residual cannot be attributed per event (>1 unknown from one
        # observable) -- committing a decomposition would be free fitting, not measurement. Mark the
        # era un-provable (its days are excluded + counted, the ruling's surgical clamp); probing
        # the missing intermediate era rescues it. The gap propagates to older eras by construction.
        new_events = [e for e in win if e.ex_date not in price_canon]
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
    )


def _resolve_pass(
    win: Sequence[EventSpec],
    cumulative: Decimal | None,
    canonical: Mapping[date, tuple[str, Decimal]],
    *,
    get_ours,
    oracle,
    costs: Mapping[str, int] = _COST,
    price_factors: Mapping[date, Decimal] | None = None,
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
    """
    option_lists: list[list[tuple[str, object, int]]] = []
    for e in win:
        ours = get_ours(e)
        from_price = None if price_factors is None else price_factors.get(e.ex_date)
        opts: list[tuple[str, object, int]] = []
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
        limit = max(Decimal(tol_paise), Decimal(raw) * _PRICE_CONTAINMENT_REL)
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


def to_dict(adjustment_map: AdjustmentMap) -> dict:
    """A JSON-ready dict of the map (Decimals as strings, dates as ISO). PURE."""
    return {
        "symbol": adjustment_map.symbol,
        "fetch_date": adjustment_map.fetch_date.isoformat(),
        "tick_paise": adjustment_map.tick_paise,
        "volume_estimator": adjustment_map.volume_estimator_id,
        "all_event_ex_dates": [d.isoformat() for d in adjustment_map.all_event_ex_dates],
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
        return AdjustmentMap(
            symbol=str(payload["symbol"]),
            fetch_date=date.fromisoformat(str(payload["fetch_date"])),
            all_event_ex_dates=tuple(date.fromisoformat(d) for d in payload["all_event_ex_dates"]),
            eras=eras,
            tick_paise=payload.get("tick_paise"),
            # A map written before the Q-12 ruling carries no marker at all -> "" -> stale, which is
            # exactly right: it was built with the superseded median volume estimator.
            volume_estimator_id=str(payload.get("volume_estimator", "")),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise VendorAdjustmentError(f"cannot read adjustment map: {exc}") from exc


def map_is_current(adjustment_map: AdjustmentMap) -> bool:
    """Was this map built with the CURRENT volume estimator (:data:`MAP_VOLUME_ESTIMATOR`)?

    A ``False`` here is not a corrupt file -- it is a map built under a superseded ruling. It must be
    REBUILT (probe windows only; no stored candle is refetched) rather than consumed, because its
    committed volume factors came from the biased median and its un-provable eras may be provable
    under the ruled estimator.
    """
    return adjustment_map.volume_estimator_id == MAP_VOLUME_ESTIMATOR


def persist_map(adjustment_map: AdjustmentMap, data_dir: Path | None = None) -> Path:
    """Write the map to ``data/adjustment_maps/<SYMBOL>.json`` (gitignored). Returns the path."""
    path = map_path(adjustment_map.symbol, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_dict(adjustment_map), indent=2), encoding="utf-8")
    return path


def load_map(symbol: str, data_dir: Path | None = None) -> AdjustmentMap:
    """Read a committed adjustment map from ``data/``."""
    path = map_path(symbol, data_dir)
    if not path.is_file():
        raise VendorAdjustmentError(f"no adjustment map for {symbol} at {path}")
    return from_dict(json.loads(path.read_text(encoding="utf-8")))


# --- live measurement (I/O; opt-in) ----------------------------------------------------


@dataclass(frozen=True)
class WindowSpec:
    """One probe window: a small span of pre-ex days in one era, fetched in a single call."""

    label: str
    start: date
    end: date


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
) -> AdjustmentMap:
    """Measure the probe windows live and build the map. I/O (the fetch), then PURE (the build)."""
    eras = measure_symbol_live(
        client, daily_store, symbol, token, events, windows, fetch_date, on_window=on_window
    )
    return build_map(symbol, fetch_date, events, eras, tick_paise=tick_paise, price_tol_paise=price_tol_paise)
