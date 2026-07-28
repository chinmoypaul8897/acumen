"""The Q-14 bounded PRICE-RECOVERY pass: per-side vendor application floors, measured offline.

The architect's ruling of 2026-07-28 (QUESTIONS.md Q-14), after REVIEW_5B's finding Q1 measured
1,963 stored symbol-days sitting at 0.1x-5x the traded price and passing the whole gate battery:

    "the mechanism is per-side vendor splices -- price and volume applied back to DIFFERENT dates
    for the same event. The floor model gains per-side floors (floor_price, floor_volume per
    event), measured by the same bisection under the same guards, hunts SIGNATURE-GATED by gate-1P
    failure clusters at era/event boundaries. ONE bounded recovery pass is licensed for the flagged
    days; acceptance = the era's days pass BOTH per-day gates; after this pass the data era FREEZES
    -- anything still flagged is a disclosed residual, not chased."

**Nothing here touches the network** (decision B143). The observable a probe buys is the ratio
``fetched / raw``, and the store already holds it exactly: the ingest wrote
``stored = fetched / k_applied``, so "does this day carry the event?" is answered by two
multiplications of numbers already on disk (:func:`acumen.vendor_adjustment.classify_stored_price_day`).
The ruling's own closing note is that both sides of the check are LOCAL, and this is that note taken
literally -- the pass spends zero credentialed calls and is reproducible offline by anyone holding
the minute store and the daily store.

**The guards are the ones already in force**, not new ones:

* the SEARCH is :func:`acumen.vendor_adjustment.binary_search_floor`, byte-identical -- the same
  probe budget, the same undecided-step allowance, the same three-probe "absent throughout" rule,
  the same "one event-in or one undecided leaves it UNRESOLVED";
* the ADMISSION is the signature gate (:func:`acumen.universe_backfill.signature_gated_events`),
  which Q-14 extends with the gate-1P failure cluster and nothing else;
* the ACCEPTANCE is the ruling's own -- the affected days must pass BOTH per-day gates afterwards.
  It is evaluated as a DRY RUN first (:func:`predict_counts`, pure arithmetic on the same stored
  numbers), so a floor that does not earn its keep is never written to the store at all.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Callable, Mapping, Sequence

from . import minute_backfill as mb
from . import quality_gates as gates
from . import vendor_adjustment as va

_ONE: Decimal = Decimal(1)


@dataclass(frozen=True)
class DayCounts:
    """How many stored days pass each per-day gate, and how many pass both."""

    days: int = 0
    gate1: int = 0
    gate1p: int = 0
    both: int = 0

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"gate1 {self.gate1}/{self.days}, gate1P {self.gate1p}/{self.days}, both {self.both}"


@dataclass
class EventRecovery:
    """One event's per-side floor measurement (QUESTIONS.md Q-14)."""

    ex_date: date
    signature: str
    price_floor: date | None = None
    price_resolved: bool = False
    price_probes: int = 0
    price_note: str = ""
    volume_floor: date | None = None
    volume_resolved: bool = False
    volume_probes: int = 0
    volume_note: str = ""
    accepted: bool = False
    verdict: str = ""

    @property
    def per_side(self) -> bool:
        return self.volume_resolved and self.volume_floor != self.price_floor


@dataclass
class SymbolRecovery:
    """What the bounded recovery pass did to one symbol, and what it cost or bought."""

    symbol: str
    before: DayCounts = field(default_factory=DayCounts)
    after: DayCounts = field(default_factory=DayCounts)
    admitted: list[str] = field(default_factory=list)
    events: list[EventRecovery] = field(default_factory=list)
    accepted_floors: int = 0
    days_rewritten: int = 0
    applied: bool = False
    note: str = ""
    residual_reason: str = ""


# --- reading the store (I/O, read-only) --------------------------------------------------


def stored_days(
    minute_store,
    daily_rows: Mapping[date, tuple[int, int, int, int]],
    symbol: str,
    *,
    since: date | None = None,
    folds: Mapping[date, tuple[int, int, int]] | None = None,
) -> dict[date, va.StoredDay]:
    """Fold every stored symbol-day into the two observables a floor search reads. Read-only I/O.

    ``daily_rows`` maps a trade date to ``(raw_high, raw_low, raw_open, raw_volume)`` from the RAW
    daily store. A day with no raw row is skipped here: it cannot be price-proven at all (gate 1P
    fails it under :data:`acumen.quality_gates.GATE1P_NO_ORACLE`), and it can prove nothing about
    the vendor's archive either.

    ``folds`` are ``day -> (high, low, volume)`` summaries the caller already computed (the gate
    pass keeps them on its tally), and giving them turns this into pure arithmetic with NO store
    read at all -- which is the difference between one walk of a symbol's parquet and two.
    """
    out: dict[date, va.StoredDay] = {}
    source = (
        folds.items() if folds is not None
        else (
            (day, (max(b.high_paise for b in bars), min(b.low_paise for b in bars),
                   sum(b.volume for b in bars)))
            for day, bars in minute_store.iter_days(symbol, since, None) if bars
        )
    )
    for day, (high, low, volume) in source:
        row = daily_rows.get(day)
        if row is None:
            continue
        out[day] = va.StoredDay(
            day=day, stored_high=high, stored_low=low, stored_volume=volume,
            raw_high=row[0], raw_low=row[1], raw_volume=row[3],
        )
    return out


# --- the dry run (PURE) ------------------------------------------------------------------


def rescaled(
    day: va.StoredDay, before: tuple[Decimal, Decimal] | None, after: tuple[Decimal, Decimal] | None
) -> va.StoredDay:
    """What the stored day WOULD hold once the map moved from ``before`` to ``after``. PURE.

    ``stored = fetched / k_price`` and ``stored_volume = fetched_volume x k_volume``, so moving the
    committed chain rescales the store by ``k_before / k_after`` on the price side and by
    ``k_after / k_before`` on the volume side. An un-provable era commits nothing and its days are
    stored exactly as fetched, which is the ``before is None`` case: ``k_before`` is then the
    identity by definition.
    """
    kb_price, kb_volume = before if before is not None else (_ONE, _ONE)
    if after is None:
        return day  # the day becomes un-provable: nothing is rewritten, gate 1 excludes it
    ka_price, ka_volume = after
    if kb_price == ka_price and kb_volume == ka_volume:
        return day
    price_ratio = kb_price / ka_price
    volume_ratio = ka_volume / kb_volume
    return va.StoredDay(
        day=day.day,
        stored_high=va._scale_paise(day.stored_high, price_ratio),      # noqa: SLF001
        stored_low=va._scale_paise(day.stored_low, price_ratio),        # noqa: SLF001
        stored_volume=va._scale_paise(day.stored_volume, volume_ratio), # noqa: SLF001
        raw_high=day.raw_high,
        raw_low=day.raw_low,
        raw_volume=day.raw_volume,
    )


def judge_day(day: va.StoredDay) -> tuple[bool, bool]:
    """``(gate 1 effective, gate 1P)`` for one stored day. PURE.

    Gate 1 is CONTEXT 4.5's own volume reconciliation; a failure above the ceiling is offered the
    auction relief exactly as the runner offers it -- except for condition (c), the opening print,
    which a day FOLD does not carry, so it is passed trivially here. That makes this predictor
    slightly LOOSER on relief than the runner, and it is stated rather than hidden. It cannot change
    a decision: acceptance compares two predictions computed the identical way, so a bias present in
    both cancels, and the authoritative numbers always come from the real re-gate that follows.
    """
    result = gates.volume_gate(day.raw_volume, day.stored_volume)
    ok1 = result.passed
    if not ok1:
        relief = gates.auction_relief(
            result,
            minute_open_paise=day.raw_high,   # (c) is not testable from a fold; see the docstring
            minute_high_paise=day.stored_high,
            minute_low_paise=day.stored_low,
            raw_open_paise=day.raw_high,
            raw_high_paise=day.raw_high,
            raw_low_paise=day.raw_low,
        )
        ok1 = relief.relieved
    ok1p = gates.price_containment_gate(
        day.stored_high, day.stored_low, day.raw_high, day.raw_low
    ).passed
    return ok1, ok1p


def predict_counts(
    stored: Mapping[date, va.StoredDay],
    before: "va.AdjustmentMap",
    after: "va.AdjustmentMap",
) -> DayCounts:
    """The per-day gate counts the store WOULD show under ``after``. PURE.

    This is the ruling's acceptance test, run before anything is written: "acceptance = the era's
    days pass BOTH per-day gates". Same arithmetic the real re-gate performs, on the same numbers,
    so a floor that would not pay for itself never reaches the store.
    """
    counts = DayCounts()
    g1 = g1p = both = 0
    for day, row in stored.items():
        moved = rescaled(row, before.factors_for_day(day), after.factors_for_day(day))
        ok1, ok1p = judge_day(moved)
        g1 += ok1
        g1p += ok1p
        both += ok1 and ok1p
    return DayCounts(days=len(stored), gate1=g1, gate1p=g1p, both=both)


# --- the search domain (PURE) ------------------------------------------------------------


def candidate_days(
    adjustment_map: "va.AdjustmentMap",
    days: Sequence[date],
    ex_date: date,
    *,
    side: str = va.FLOOR_SIDE_PRICE,
) -> list[date]:
    """The stored days a per-side floor search for ``ex_date`` may probe. PURE.

    Strictly before the ex-date, a measurable session (the Q-5 ruling), inside a PROVABLE era -- so
    the chain the store was written under is known and the two hypotheses are exact -- and carrying
    this event with a factor on the side being searched that is not already 1 (an event committed
    ABSENT has nothing to drop, so its days answer nothing).
    """
    out: list[date] = []
    for day in days:
        if day >= ex_date or not va.is_measurable_session(day):
            continue
        era = adjustment_map.era_for_day(day)
        if era is None or not era.provable:
            continue
        for choice in era.choices:
            if choice.ex_date != ex_date:
                continue
            factor = (
                choice.price_factor if side == va.FLOOR_SIDE_PRICE else choice.volume_factor
            )
            if factor != _ONE:
                out.append(day)
            break
    return sorted(out)


# --- the pass ----------------------------------------------------------------------------


def measure_event_floor(
    adjustment_map: "va.AdjustmentMap",
    stored: Mapping[date, va.StoredDay],
    ex_date: date,
    signature: str,
) -> tuple["va.EventFloor | None", EventRecovery]:
    """Measure BOTH sides of one event's vendor application floor from the store. PURE.

    Each side is its own run of the same bisection with its own oracle -- price containment for the
    price side, gate 1's unwidened band for the volume side. A side whose search does not resolve
    simply carries no floor, and the chain on that side is left exactly as the era committed it.
    """
    days = sorted(stored)
    record = EventRecovery(ex_date=ex_date, signature=signature)

    price_days = candidate_days(adjustment_map, days, ex_date, side=va.FLOOR_SIDE_PRICE)
    price_search, price_factor = va.search_event_floor_stored(
        stored, adjustment_map, ex_date, price_days,
        side=va.FLOOR_SIDE_PRICE, allow_absent_throughout=True,
    )
    record.price_floor = price_search.floor_date
    record.price_resolved = price_search.resolved
    record.price_probes = len(price_search.probes)
    record.price_note = price_search.note

    volume_days = candidate_days(adjustment_map, days, ex_date, side=va.FLOOR_SIDE_VOLUME)
    volume_search, volume_factor = va.search_event_floor_stored(
        stored, adjustment_map, ex_date, volume_days,
        side=va.FLOOR_SIDE_VOLUME, allow_absent_throughout=True,
    )
    record.volume_floor = volume_search.floor_date
    record.volume_resolved = volume_search.resolved
    record.volume_probes = len(volume_search.probes)
    record.volume_note = volume_search.note

    if not (price_search.resolved and price_search.floor_date is not None) and not (
        volume_search.resolved and volume_search.floor_date is not None
    ):
        record.verdict = "no splice on either side"
        return None, record

    floor = va.EventFloor(
        ex_date=ex_date,
        floor_date=price_search.floor_date if price_search.resolved else None,
        resolved=price_search.resolved and price_search.floor_date is not None,
        probes=price_search.probes,
        note=price_search.note,
        event_price_factor=price_factor,
        floor_volume=volume_search.floor_date if volume_search.resolved else None,
        volume_resolved=volume_search.resolved and volume_search.floor_date is not None,
        volume_measured=volume_search.resolved,
        volume_probes=volume_search.probes,
        volume_note=volume_search.note,
        event_volume_factor=volume_factor,
    )
    return floor, record


def _merged(
    adjustment_map: "va.AdjustmentMap", fresh: Sequence["va.EventFloor"]
) -> list["va.EventFloor"]:
    """This pass's floors PLUS every floor the map already carried, keyed by event. PURE.

    :func:`acumen.vendor_adjustment.with_floors` REPLACES the tuple, so committing a fresh floor
    without merging would silently drop the FIX-3/FIX-4 floors the map already holds -- exactly the
    class of loss REVIEW_5B finding Q5 caught one level up, in the ledger's claims. The fresh
    measurement wins for an event both hold, because it was measured against the store as it stands.
    """
    by_event = {floor.ex_date: floor for floor in adjustment_map.floors}
    by_event.update({floor.ex_date: floor for floor in fresh})
    return [by_event[ex] for ex in sorted(by_event)]


def recover_symbol(
    minute_store,
    daily_store,
    daily_rows: Mapping[date, tuple[int, int, int, int]],
    symbol: str,
    adjustment_map: "va.AdjustmentMap",
    signatures: Mapping[date, str],
    *,
    data_dir,
    tick_paise: int | None = None,
    apply: bool = True,
    folds: Mapping[date, tuple[int, int, int]] | None = None,
    log: Callable[[str], None] = print,
) -> SymbolRecovery:
    """Hunt per-side floors for one symbol, accept what pays, apply it. The bounded recovery pass.

    Floors are measured NEWEST event first and accepted GREEDILY, one at a time: a floor is kept
    only when the dry run says the store would end with MORE days passing both per-day gates and no
    fewer passing gate 1. That is the ruling's acceptance, and doing it incrementally means one
    unhelpful floor cannot drag a helpful one down with it. A rejected floor is recorded with its
    measurement and discarded -- never written, never half-applied.
    """
    result = SymbolRecovery(symbol=symbol)
    stored = stored_days(minute_store, daily_rows, symbol, folds=folds)
    if not stored:
        result.note = "nothing stored"
        return result
    result.before = predict_counts(stored, adjustment_map, adjustment_map)
    result.admitted = [f"{ex.isoformat()}: {why}" for ex, why in sorted(signatures.items())]
    if not signatures:
        result.after = result.before
        result.note = "no event admitted by the gate-1P cluster signature; nothing hunted"
        return result

    kept: list[va.EventFloor] = []
    best = result.before
    for ex_date in sorted(signatures, reverse=True):
        # Each event is measured against the map the STORE was written under -- the original -- and
        # never against a map carrying a floor this pass has accepted but not yet applied. The
        # classifier's whole arithmetic is "stored = fetched / k_applied", so measuring against a
        # chain the store does not hold would compare two different domains.
        floor, record = measure_event_floor(adjustment_map, stored, ex_date, signatures[ex_date])
        result.events.append(record)
        if floor is None:
            log(f"      {ex_date}: {record.verdict} -- price: {record.price_note}")
            continue
        trial = va.with_floors(adjustment_map, _merged(adjustment_map, [*kept, floor]))
        counts = predict_counts(stored, adjustment_map, trial)
        if counts.both > best.both and counts.gate1 >= best.gate1:
            kept.append(floor)
            best = counts
            record.accepted = True
            record.verdict = (
                f"ACCEPTED: both-gate days {result.before.both} -> {counts.both} "
                f"(gate 1P {result.before.gate1p} -> {counts.gate1p})"
            )
        else:
            record.verdict = (
                f"REJECTED by acceptance: both-gate days would go {best.both} -> {counts.both} "
                f"(gate 1 {best.gate1} -> {counts.gate1}); the floor is discarded, not applied"
            )
        log(f"      {ex_date}: price floor {record.price_floor} "
            f"({'resolved' if record.price_resolved else 'UNRESOLVED'}, {record.price_probes} probe(s)); "
            f"volume floor {record.volume_floor} "
            f"({'resolved' if record.volume_resolved else 'UNRESOLVED'}, {record.volume_probes} probe(s))"
            f" -> {record.verdict}")

    result.accepted_floors = len(kept)
    result.after = best
    if not kept:
        result.note = (
            f"{len(result.events)} event(s) measured, none accepted; the map is untouched and the "
            "flagged days stay excluded by gate 1P as disclosed residuals"
        )
        return result

    if not apply:
        result.note = f"{len(kept)} floor(s) accepted (dry run; nothing written)"
        return result

    committed = va.with_floors(adjustment_map, _merged(adjustment_map, kept))
    va.persist_map(committed, data_dir=data_dir)
    applied = mb.rebuild_symbol_raw_with_map(
        minute_store, daily_store, symbol, committed, tick_paise=tick_paise
    )
    result.days_rewritten = applied.days_rewritten
    result.applied = True
    result.note = (
        f"{len(kept)} per-side floor(s) committed; {applied.days_rewritten} stored day(s) "
        f"rewritten, {applied.identity_days} already correct"
    )
    return result
