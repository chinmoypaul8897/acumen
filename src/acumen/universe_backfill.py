"""The full-universe 1-minute backfill run (chunk 5B): ~210 F&O symbols, 2016-10 -> today.

Chunk 5A proved one symbol end to end. This is the same machinery pointed at CONTEXT 3.1's
whole universe, plus the four things a multi-hour unattended run needs and a single-symbol
script does not: a ROUTE per symbol, a MAP built before its ingest, a per-symbol outcome
LEDGER that survives a Ctrl-C, and a QUARANTINE that keeps one bad symbol from poisoning the
run's verdict.

**The order of operations is the point.**

1. **Verify the oracle first.** The RAW daily store is what the vendor-adjustment maps are
   measured against (QUESTIONS.md Q-11) and what gate 1 reconciles to (CONTEXT 4.5). It is
   verified (:meth:`acumen.daily_store.DailyStore.verify`, the owed REVIEW_2 F7 check) BEFORE a
   single candle is fetched; any anomaly halts the run.
2. **Route every symbol** (QUESTIONS.md Q-11 addendum, :mod:`acumen.adjustment_route`). A
   symbol carrying any non-share-count event is MAP-REQUIRED and may not fall back to the
   price-blind factor table (REVIEW_5A F2).
3. **Build a MAP-REQUIRED symbol's map BEFORE its ingest.** Every ERA the ingest will cover is
   probed -- an unprobed era has no factors, so its days are un-provable and gate 1 excludes
   them. The eras are derived from the symbol's own event list (:func:`era_probe_windows`), so
   the operator does not hand-pick probe windows for 210 symbols the way the FIX-4 runbook did
   for one.
4. **Ingest** through the chosen path, then run the CONTEXT 4.5 gates over every stored
   symbol-day and every corporate-action ex-date in the span.
5. **Quarantine** a symbol whose gate-1 pass rate is under
   :data:`QUARANTINE_GATE1_MIN_PASS_RATE`; **halt** the whole run if more than
   :data:`HALT_QUARANTINE_FRACTION` of the universe ends up there, because that is a systemic
   fault (a bad daily store, a vendor change) and not 210 individual accidents.

**Interrupt-safety.** Every window is settled in the minute store's own ledger as it lands
(chunk 5A), and this run's per-symbol ledger is rewritten atomically after every symbol. The
same command resumes: settled windows are never refetched and terminal symbols are skipped.

**Politeness.** One :class:`acumen.smartapi_client.SmartApiClient` is shared by the whole run,
so its 0.5 s throttle and backoff ladder are GLOBAL by construction -- probes and ingest
windows queue behind the same clock (CONTEXT 4.3).

The report (:func:`write_report`) is re-runnable at any time and makes no network call.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

import pandas as pd

from . import corp_actions as ca
from . import minute_backfill as mb
from . import quality_gates as gates
from . import smartapi_client as sac
from . import universe as universe_module
from . import vendor_adjustment as va
from .adjustment_route import ROUTE_MAP_REQUIRED, ROUTE_TABLE_PATH, RouteDecision, classify_route
from .atomic_io import atomic_write_text
from .daily_store import INSTRUMENT_SERIES, DailyStore, DailyStoreError
from .instrument_master import InstrumentMaster, InstrumentMasterError, load_instrument_master
from .minute_store import MinuteStore

#: A symbol whose CONTEXT 4.5 gate-1 pass rate falls below this is QUARANTINED: skipped from
#: here on, listed in the report, and excluded from the coverage figure.
#:
#: **80% is a CLASS-B choice of this repo's, not a ruling** (REVIEW_5B finding C16: the previous
#: comment attributed it to "the architect" with no ruling or card behind it -- recorded now as
#: decision B144). Neither CONTEXT nor plan.md names a quarantine threshold; the chunk-5B card asks
#: only that ">= 95% of symbol-days pass gates" and that "failures [be] categorized". 80% is a
#: judgement about where a symbol stops being a set of bad days and becomes a bad symbol, chosen so
#: that a symbol contributing more failures than passes to the headline is investigated rather than
#: averaged in. Nothing downstream depends on the exact number: a quarantined symbol's days are
#: excluded and counted either way, so moving it moves which BUCKET days sit in, never whether a
#: wrong price reaches the backtest.
QUARANTINE_GATE1_MIN_PASS_RATE: Decimal = Decimal("0.80")

#: More than this FRACTION of the universe quarantined halts the whole run. One bad symbol is
#: an exclusion; a fifth of the universe is a systemic fault (a damaged daily store, a vendor
#: change) that must reach the architect before hours more are spent on it.
HALT_QUARANTINE_FRACTION: Decimal = Decimal("0.10")

#: QUESTIONS.md Q-11 addendum 2 (vendor application floors): "Floors are hunted ONLY where failure
#: is systematic: every quarantined symbol and every settled symbol with gate-1 < 98%." This is
#: that 98%. A symbol at or above it has no systematic failure for a floor to explain, and is not
#: probed. Reading it as the EFFECTIVE gate-1 rate (auction relief included) is deliberate: a
#: PNBHOUSING-shaped symbol whose failures are relieved as a market property does not have an
#: adjustment problem, and spending 11 probes per event hunting one would be measuring noise.
FLOOR_HUNT_GATE1_MAX_RATE: Decimal = Decimal("0.98")

#: Within a hunted symbol, an EVENT is only searched when this fraction of the days in its pre-ex
#: provable-era span actually FAIL gate 1. The ruling scopes the hunt to systematic failure, and a
#: span that already reconciles has no floor to find -- searching it would spend ~11 credentialed
#: probes to confirm "applied throughout". Every skip is recorded with its reason.
FLOOR_HUNT_MIN_FAILURE_RATE: Decimal = Decimal("0.10")

#: How many pre-ex trading days to probe per era when building a map. The FIX-4 runbook used
#: 4-5 per window; the measured factor is the MEDIAN over the era's probe days, so a handful is
#: enough to be robust to one odd day while costing one request per era.
PROBE_DAYS_PER_ERA: int = 4

#: A day-of-the-week-agnostic minimum: an era with fewer stored trading days than this cannot
#: be probed usefully, and is reported unprobed rather than measured off one day.
MIN_PROBE_DAYS_PER_ERA: int = 1

DEFAULT_REPORT_PATH: Path = Path("docs") / "backfill_minute_report.md"

#: The frozen 210-symbol universe CONTEXT 4.6's E5 clarification makes a rebuild use ("a REBUILD
#: uses the sealed universe list ... today's F&O list applies only to a deliberate,
#: architect-signed universe refresh"). Named here because the staleness banner has to hand the
#: operator a command that is RIGHT: without it the universe resolves from the cached F&O
#: endpoint, which holds 208, and EXIDEIND and NUVAMA -- exactly the pair the Q-18 T4 pass added
#: on the sealed 210 -- would never be re-gated (REVIEW_9B_FIXES R4).
SEALED_UNIVERSE_SNAPSHOT: str = "docs/recovery/sealed_universe_210.json"

#: Identity of the gate DEFINITION a ledger row's numbers were produced under. The architect's
#: completeness ruling (2026-07-26) redefined CONTEXT 4.5 gate 2, so every row written before it
#: carries a different marker and is RE-GATED from the stored candles -- no window refetched. Bump
#: this string whenever a gate's definition changes; it is what makes a re-gate automatic, bounded
#: (a row already on the current definition is skipped) and auditable.
#:
#: The architect's Q-21(a) ruling (2026-08-03, CONTEXT v1.6) COMPLETED gate 2's impossible-OHLC
#: enumeration with the OPEN test, so the marker moves again and every ledger row written under the
#: close-only enumeration is stale BY DEFINITION rather than by anyone's memory. The re-gate that
#: clears it reads stored candles and fetches nothing; the FIX-3 session did not run it, because a
#: re-gate WRITES the ledger and that session was forbidden every store write. The cost of the
#: ruling is measured instead, day by day, in docs/evidence/chunk9b_q21a_gate2_completion.md, and
#: CONTEXT v1.6 4.6 carries the post-completion coverage.
GATE_DEFINITION: str = (
    "gate1p-price-containment+gate2-completeness+auction-relief-2026-07-28"
    "+gate2-open-test-2026-08-03"
)

#: The route reason a quarantine-recovery reroute stamps on a symbol (Q-12 addendum ruling).
_RECOVERY_REASON: str = "quarantine-recovery (Q-12 addendum ruling)"

#: Identity of the discipline the map was applied to an already-stored day under. The first FIX-2
#: pass used a one-way "is this day raw?" test, which is wrong in the dangerous direction: a
#: genuinely-raw day whose 1-minute fold sits a few tenths of a percent off the bhavcopy high/low
#: (a pre-open-auction or block-window print the continuous series never held) was called "not raw"
#: and divided a SECOND time -- measured on 37 ASHOKLEY days. It is now a three-hypothesis baseline
#: classification (:func:`acumen.minute_backfill.stored_day_baseline`), which both prevents that and
#: REPAIRS a doubly-divided day by multiplying it back. A row stamped with anything else is
#: re-processed so the repair reaches it; bump this whenever that discipline changes.
REBUILD_DISCIPLINE: str = "baseline-classification+as-fetched-floored-2026-07-28"

#: QUESTIONS.md Q-11 addendum 4 (floors in un-provable eras): the SIGNATURE GATE's second
#: signature -- "an era failure-rate cliff (>=95% failing) at an event boundary". Measured on the
#: gated days of the span immediately BELOW an event's ex-date.
FLOOR_HUNT_ERA_CLIFF_RATE: Decimal = Decimal("0.95")

#: ... over at least this many gated days. A cliff is a property of a SPAN; a handful of days at
#: 100% is a coincidence, and admitting one would turn the signature gate into a blanket hunt --
#: which is exactly what the ruling forbids. 20 sessions is about a trading month.
MIN_CLIFF_DAYS: int = 20

#: The two admitting signatures, recorded per event so the report can say WHY a hunt was allowed
#: into an un-provable era (Q-11 addendum 4 clause i).
SIGNATURE_GATE3: str = "gate-3 raw-gap-near-zero"
SIGNATURE_CLIFF: str = "era failure-rate cliff"
#: QUESTIONS.md Q-14: the THIRD admitting signature -- "hunts SIGNATURE-GATED by gate-1P failure
#: clusters at era/event boundaries". Same two constants as the volume cliff
#: (:data:`FLOOR_HUNT_ERA_CLIFF_RATE` over :data:`MIN_CLIFF_DAYS`), read off the PRICE gate.
SIGNATURE_GATE1P: str = "gate-1P failure cluster"

#: Identity of the FLOOR-HUNT discipline a ledger row's floors were measured under. The Q-11
#: addendum-4 ruling widened the hunt from provable eras only (decision B123) to signature-gated
#: hypotheses inside UN-PROVABLE eras, so a row hunted under the older discipline has not been
#: asked the new question. Bumping this re-opens the hunt for in-scope symbols only -- a symbol
#: above the hunt line is not re-probed, because the ruling changed what may be hunted, not who.
FLOOR_DISCIPLINE: str = "per-side-floors+gate1p-cluster-signature-2026-07-28"

#: What a row whose floors were measured BEFORE the discipline marker existed carries instead of a
#: blank (REVIEW_5B finding C10: CANBK, DIXON, LODHA and RELIANCE were hunted under FIX-3 and their
#: rows recorded no discipline at all, so the marker no longer said what the measurement ran under).
#: It is deliberately NOT equal to :data:`FLOOR_DISCIPLINE`, so an in-scope symbol still re-opens.
LEGACY_FLOOR_DISCIPLINE: str = "(unmarked: hunted under the FIX-3 provable-era discipline, B123)"

#: Per-symbol terminal states in this run's ledger.
STATUS_SETTLED: str = "settled"
STATUS_QUARANTINED: str = "quarantined"
STATUS_NO_TOKEN: str = "no-instrument-token"
STATUS_NO_DAILY_HISTORY: str = "no-daily-equity-history"
STATUS_MAP_UNBUILDABLE: str = "map-required-but-unbuildable"
STATUS_PENDING: str = "pending"

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {STATUS_SETTLED, STATUS_QUARANTINED, STATUS_NO_TOKEN, STATUS_NO_DAILY_HISTORY}
)

_ONE: Decimal = Decimal(1)


class UniverseBackfillError(RuntimeError):
    """The universe run cannot start, or must stop."""


class RunHalted(UniverseBackfillError):
    """The run stopped itself and must reach the architect (the quarantine ceiling)."""


# --- the daily oracle, read ONCE for the whole universe --------------------------------


@dataclass(frozen=True)
class DailyDay:
    """One symbol-day of the RAW daily store, reduced to what the run actually uses.

    ``open_paise`` is carried for the auction-relief ruling's condition (c) -- "first stamp's open
    == raw daily open exactly" (QUESTIONS.md Q-12 addendum 2).
    """

    high_paise: int
    low_paise: int
    close_paise: int
    volume: int
    open_paise: int = 0


@dataclass(frozen=True)
class DailyCache:
    """Every universe symbol's RAW daily rows, read from the store in ONE pass.

    Gate 1 needs a daily volume per symbol-day, the map probes need daily high/low/volume per
    probe day, and the CA factor table needs a cum-date close per event. Answering those from
    :meth:`acumen.daily_store.DailyStore.daily` would reopen the same monthly Parquet files
    tens of thousands of times across 210 symbols; the store is read once here instead.

    The Q-4 instrument selection is applied exactly as the store applies it: keep the whitelist
    series :data:`acumen.daily_store.INSTRUMENT_SERIES`, and RAISE if one symbol-date carries
    two of them (the ruling's own safety net -- ranking them would corrupt a bias pair).
    """

    by_symbol: Mapping[str, Mapping[date, DailyDay]]

    def days(self, symbol: str) -> tuple[date, ...]:
        return tuple(sorted(self.by_symbol.get(symbol.strip().upper(), {})))

    def first_date(self, symbol: str) -> date | None:
        days = self.days(symbol)
        return days[0] if days else None

    def day(self, symbol: str, when: date) -> DailyDay | None:
        return self.by_symbol.get(symbol.strip().upper(), {}).get(when)

    def last_before(self, symbol: str, when: date) -> date | None:
        earlier = [d for d in self.days(symbol) if d < when]
        return earlier[-1] if earlier else None

    def first_on_or_after(self, symbol: str, when: date) -> date | None:
        later = [d for d in self.days(symbol) if d >= when]
        return later[0] if later else None


def build_daily_cache(
    daily_store: DailyStore, symbols: Sequence[str], from_date: date, to_date: date
) -> DailyCache:
    """Read every universe symbol's RAW daily rows in one pass and index them by symbol-day."""
    frame = daily_store.frame(symbols, from_date, to_date)
    by_symbol: dict[str, dict[date, DailyDay]] = {}
    if frame.empty:
        return DailyCache(by_symbol=by_symbol)
    chosen = frame.loc[frame["series"].isin(INSTRUMENT_SERIES)]
    clashing = chosen.duplicated(subset=["symbol", "trade_date"], keep=False)
    if bool(clashing.any()):
        clashes = chosen.loc[clashing, ["symbol", "trade_date", "series"]]
        raise DailyStoreError(
            "QUESTIONS.md Q-4: a symbol-date carries more than one WHITELIST series "
            f"({clashes.head(10).to_dict('records')!r}). The ruling requires a loud failure "
            "rather than a ranking -- two equity rows for one day would corrupt the bias pair "
            "(CONTEXT 3.2). Resolve upstream before backfilling minutes against this store."
        )
    for row in chosen.itertuples(index=False):
        by_symbol.setdefault(row.symbol, {})[row.trade_date] = DailyDay(
            high_paise=int(row.high_paise),
            low_paise=int(row.low_paise),
            close_paise=int(row.close_paise),
            volume=int(row.volume),
            open_paise=int(row.open_paise),
        )
    return DailyCache(by_symbol=by_symbol)


class CachedDailyStore:
    """A :class:`DailyStore`-shaped read-only adapter over a :class:`DailyCache`.

    Chunk-5A code (``corp_actions_for_symbol``, ``vendor_adjustment.measure_symbol_live``) asks
    a daily store for one symbol-day at a time. Handing it this instead of the real store keeps
    those code paths byte-identical while turning tens of thousands of Parquet reads into dict
    lookups. It answers with the same column names and the same "empty frame is a legitimate
    answer" contract.
    """

    _COLUMNS = ["trade_date", "open_paise", "high_paise", "low_paise", "close_paise", "volume"]

    def __init__(self, cache: DailyCache) -> None:
        self._cache = cache

    def daily(self, symbol: str, from_date: date, to_date: date, *, series=None) -> pd.DataFrame:
        sym = symbol.strip().upper()
        rows = [
            {
                "trade_date": day,
                "open_paise": value.open_paise,
                "high_paise": value.high_paise,
                "low_paise": value.low_paise,
                "close_paise": value.close_paise,
                "volume": value.volume,
            }
            for day, value in sorted(self._cache.by_symbol.get(sym, {}).items())
            if from_date <= day <= to_date
        ]
        return pd.DataFrame(rows, columns=self._COLUMNS)


# --- era probing (PURE) ----------------------------------------------------------------


#: The Q-5 ruling reaching the MEASUREMENT days -- one definition, used when the probe days are
#: CHOSEN here and again when the fetched bars are folded into an era (a probe window is a date
#: range, so the vendor can return an excluded session inside one).
is_measurable_session = va.is_measurable_session


def era_intervals(
    ex_dates: Sequence[date], clamp: date, end: date
) -> list[tuple[tuple[date, ...], date, date]]:
    """The ``(era_key, interval_start, interval_end)`` triples the ingest span covers. PURE.

    A day ``D``'s era key is ``{ex : D < ex <= F}`` (:meth:`acumen.vendor_adjustment.
    AdjustmentMap.in_window_ex_dates`). Sorting the in-scope ex-dates ``x1 < ... < xn`` cuts
    ``[clamp, end]`` into ``n + 1`` half-open intervals whose keys shrink by exactly one event
    each: ``[clamp, x1)`` carries all n, ``[x_i, x_{i+1})`` carries the ones after ``x_i``, and
    ``[x_n, end]`` carries none (the identity era -- fetched == raw, no probe needed).

    "Exactly one event per step" is what the map builder's probe-gap guard requires: it can
    solve at most one fresh unknown per era, so an era that jumps two events is un-provable.
    Only the non-identity intervals are returned, newest first, because the builder works
    backwards from ``F``.
    """
    in_scope = sorted({ex for ex in ex_dates if clamp < ex <= end})
    intervals: list[tuple[tuple[date, ...], date, date]] = []
    lows = [clamp] + in_scope
    for index, low in enumerate(lows[:-1] if in_scope else []):
        high = in_scope[index] - timedelta(days=1)
        key = tuple(in_scope[index:])
        intervals.append((key, low, high))
    intervals.sort(key=lambda item: len(item[0]))
    return intervals


def era_probe_windows(
    events: Sequence[va.EventSpec],
    trading_days: Sequence[date],
    clamp: date,
    end: date,
    *,
    per_era: int = PROBE_DAYS_PER_ERA,
    floor: date = mb.MINUTE_DATA_FLOOR,
) -> tuple[list[va.WindowSpec], list[tuple[date, ...]]]:
    """Probe windows covering every non-identity era of the ingest span. PURE.

    Returns ``(windows, unprobeable_era_keys)``. For each era it takes the LAST ``per_era``
    trading days inside the era's interval -- the days just before the next ex-date, i.e. the
    ruling's "pre-ex probe days", where the measured ratio is cleanest -- and asks for them in
    one window. An era with no trading day at or after the 1-minute floor cannot be probed; it
    is reported, and by the probe-gap guard every OLDER era becomes un-provable too, so those
    spans are excluded and counted rather than guessed (the disclosed surgical clamp).

    A weekend-dated session is never probed (:func:`is_measurable_session`): the Q-5 ruling makes
    it not a trading day at all, so measuring an era's factor on one measures a session the spec
    excludes.
    """
    windows: list[va.WindowSpec] = []
    unprobeable: list[tuple[date, ...]] = []
    usable = sorted(
        day for day in trading_days if day >= max(clamp, floor) and is_measurable_session(day)
    )
    for key, low, high in era_intervals([e.ex_date for e in events], clamp, end):
        inside = [day for day in usable if low <= day <= high]
        if len(inside) < MIN_PROBE_DAYS_PER_ERA:
            unprobeable.append(key)
            continue
        picked = inside[-per_era:]
        windows.append(va.WindowSpec(label=_era_label(key), start=picked[0], end=picked[-1]))
    return windows, unprobeable


def _era_label(key: Sequence[date]) -> str:
    return "pre-" + key[0].isoformat() if key else "identity"


# --- the per-symbol ledger -------------------------------------------------------------


@dataclass
class MapEvent:
    """One committed map row, flattened for the ledger and the report."""

    kind: str
    ex_date: str
    price_source: str
    volume_source: str


@dataclass
class SymbolRecord:
    """Everything this run learned about one symbol. Persisted; survives a Ctrl-C."""

    symbol: str
    status: str = STATUS_PENDING
    route: str = ROUTE_TABLE_PATH
    route_reasons: list[str] = field(default_factory=list)
    clamp_start: str | None = None
    first_stored_date: str | None = None
    depth_days: int = 0
    windows_planned: int = 0
    windows_present: int = 0
    windows_empty: int = 0
    windows_error: int = 0
    gate1_pass: int = 0
    gate1_total: int = 0
    #: Auction-relief passes (Q-12 addendum 2): above-ceiling failures with intact extremes and a
    #: matching opening print. Counted SEPARATELY from ``gate1_pass``, never folded into it.
    gate1_relieved: int = 0
    gate1_relieved_with_missing: int = 0
    gate1_relieved_median_gap: str = ""
    # --- gate 1P: per-day PRICE containment (QUESTIONS.md Q-14) ---------------------------
    #: Every stored day is gated by 1P, so ``gate1p_total`` is the stored-day count and a day with
    #: no raw daily row is a FAILURE (``gate1p_no_oracle``), not an absence.
    gate1p_pass: int = 0
    gate1p_total: int = 0
    gate1p_no_oracle: int = 0
    gate1p_above: int = 0
    gate1p_below: int = 0
    gate1p_worst_excess: int = 0
    #: A bounded sample of failing dates, so the report can name them without carrying thousands.
    gate1p_failure_dates: list[str] = field(default_factory=list)
    #: The gate-1P numbers immediately BEFORE the Q-14 recovery pass, so its effect is auditable.
    pre_recovery_gate1p_pass: int = -1
    pre_recovery_gate1p_total: int = -1
    # --- the Q-14 bounded recovery pass, recorded on the row so the report needs no re-run -----
    recovery_admitted: list[str] = field(default_factory=list)
    recovery_events: list[str] = field(default_factory=list)
    recovery_accepted: int = 0
    recovery_before_both: int = -1
    recovery_after_both: int = -1
    recovery_days_rewritten: int = 0
    recovery_note: str = ""
    #: Why this symbol's remaining gate-1P failures are DISCLOSED RESIDUALS -- the register chunk 9
    #: carries forward. Written by the recovery pass whether or not it recovered anything.
    residual_reason: str = ""
    # --- overlap-aware intersections (REVIEW_5B finding Q3) --------------------------------
    gate1_and_gate2_pass: int = 0
    usable_pass: int = 0
    gate2_excluded: int = 0
    gate3_checked: int = 0
    gate3_failed: int = 0
    #: Mean 1-minute candles per stored day. CONTEXT 4.5 gate 2 excludes a day missing more than
    #: 15 of the 375 session minutes, and the vendor OMITS minutes with no trade -- so this
    #: number is what decides how much of a less liquid symbol's history survives gate 2.
    avg_minutes_per_day: float = 0.0
    unprovable_days: int = 0
    map_eras: int = 0
    map_eras_provable: int = 0
    map_unprobed_eras: int = 0
    map_events: list[MapEvent] = field(default_factory=list)
    note: str = ""
    updated_at: str = ""
    # --- gate-2 trigger breakdown + liquidity statistics (completeness ruling) ------------
    gate2_missing: int = 0
    gate2_duplicates: int = 0
    gate2_ohlc: int = 0
    gate2_negative: int = 0
    #: The dates that tripped the NEGATIVE-values trigger, so the report can name them.
    gate2_negative_dates: list[str] = field(default_factory=list)
    liquidity_days: int = 0
    median_minutes_per_day: int = 0
    min_minutes_per_day: int = 0
    #: Which gate definition produced the numbers above. A record stamped with anything else is
    #: RE-GATED from the store (no refetch) on the next run -- see :data:`GATE_DEFINITION`.
    gate_definition: str = ""
    #: Which map-application discipline produced this row (:data:`REBUILD_DISCIPLINE`).
    rebuild_discipline: str = ""
    #: Stored days whose bars matched no known baseline -- left untouched, excluded by gate 1.
    unknown_baseline_days: int = 0
    # --- the before/after snapshot, so a re-gate is auditable rather than merely different -----
    prior_status: str = ""
    prior_gate1_pass: int = -1
    prior_gate1_total: int = -1
    prior_gate2_excluded: int = -1
    # --- quarantine recovery (Q-12 addendum ruling) ---------------------------------------
    #: True once the table-path -> map second pass has been ATTEMPTED, so a resumed run never
    #: re-probes a symbol it has already rerouted.
    reroute_attempted: bool = False
    #: True once the reroute succeeded in building a map. The routing CLASSIFIER would still call
    #: this symbol table-path (its CA history is unchanged), so the recovery decision has to be
    #: STICKY -- otherwise a re-processing run would drop it back onto the price-blind cheap path
    #: that quarantined it in the first place.
    map_required_by_recovery: bool = False
    reroute_note: str = ""
    failure_pattern: str = ""
    failure_detail: str = ""
    gate1_above_ceiling: int = 0
    gate1_below_floor: int = 0
    median_daily_volume: int = 0
    median_daily_volume_above_ceiling: int = 0
    #: Rendered "span: failing/total (rate)" strings, one per inter-ex-date span.
    era_failure_rates: list[str] = field(default_factory=list)
    # --- vendor application floors (Q-11 addendum 2) --------------------------------------
    #: True once the floor hunt has been ATTEMPTED, so a resumed run never re-probes a symbol.
    floors_hunted: bool = False
    #: Rendered "kind@ex-date -> floor | note" strings, one per event the hunt looked at.
    floor_findings: list[str] = field(default_factory=list)
    floors_resolved: int = 0
    #: The ex-dates a floor was RESOLVED for. Kept as well as counted so a map that lost its floors
    #: can be repaired by re-measuring exactly those events -- the post-repair gate-1 failure rate
    #: cannot tell you an event has a floor, because the repair is why the failures are gone.
    floor_ex_dates: list[str] = field(default_factory=list)
    floor_probes_spent: int = 0
    floor_note: str = ""
    #: The gate-1 numbers immediately BEFORE the floor pass, so its effect is auditable alone.
    pre_floor_gate1_pass: int = -1
    pre_floor_gate1_total: int = -1
    # --- floors in UN-PROVABLE eras (Q-11 addendum 4) --------------------------------------
    #: Which floor-hunt discipline measured this row's floors (:data:`FLOOR_DISCIPLINE`).
    floor_discipline: str = ""
    #: Rendered "ex-date: signature" strings -- why each event was ADMITTED into an un-provable
    #: era's hunt. An empty list on a hunted symbol means no event showed either signature.
    floor_signatures: list[str] = field(default_factory=list)
    #: Provable-era counts either side of the floor pass, so a PROMOTION is visible as a number.
    pre_floor_eras_provable: int = -1
    eras_promoted: int = 0
    #: Unknown-baseline days that ALSO fail gate 1 -- the only ones that cost coverage. The rest are
    #: days the classifier declined to touch that reconcile anyway (the conservative refusal).
    unknown_baseline_failing: int = 0
    # --- gate 3, kept per failure so the report can print the numbers ---------------------
    gate3_failure_rows: list[str] = field(default_factory=list)

    def era_rate_summary(self) -> str:
        return "; ".join(self.era_failure_rates)

    @property
    def gate1_effective_pass(self) -> int:
        """Strict passes PLUS auction-relief passes -- what coverage and quarantine measure on."""
        return self.gate1_pass + self.gate1_relieved

    @property
    def gate1_rate(self) -> Decimal:
        """The EFFECTIVE gate-1 rate: strict passes plus auction-relief passes, over gated days.

        The auction-relief ruling calls a relieved day a pass ("counted SEPARATELY
        ('auction-relief pass')"), so the coverage and quarantine decisions read this. The strict
        numerator is never overwritten -- :attr:`gate1_strict_rate` and ``gate1_relieved`` are both
        printed beside it in the report.
        """
        if not self.gate1_total:
            return Decimal(0)
        return Decimal(self.gate1_effective_pass) / Decimal(self.gate1_total)

    @property
    def gate1_strict_rate(self) -> Decimal:
        if not self.gate1_total:
            return Decimal(0)
        return Decimal(self.gate1_pass) / Decimal(self.gate1_total)

    @property
    def gate1p_rate(self) -> Decimal:
        """The per-day PRICE gate's pass rate over EVERY stored day (QUESTIONS.md Q-14)."""
        if not self.gate1p_total:
            return Decimal(0)
        return Decimal(self.gate1p_pass) / Decimal(self.gate1p_total)

    @property
    def gate1p_failed(self) -> int:
        return max(0, self.gate1p_total - self.gate1p_pass)

    @property
    def prior_gate1_rate(self) -> Decimal | None:
        if self.prior_gate1_total is None or self.prior_gate1_total <= 0:
            return None
        return Decimal(self.prior_gate1_pass) / Decimal(self.prior_gate1_total)

    def snapshot_prior(self) -> None:
        """Freeze the CURRENT gate numbers as the "before" of a re-gate, once per record.

        Called before the gates are re-run under a new definition. It never overwrites an existing
        snapshot: the "before" that matters is the state the architect last saw, not the state of the
        previous intermediate pass.
        """
        if self.prior_gate1_total >= 0:
            return
        self.prior_status = self.status
        self.prior_gate1_pass = self.gate1_pass
        self.prior_gate1_total = self.gate1_total
        self.prior_gate2_excluded = self.gate2_excluded

    def apply_tally(self, tally: "GateTally") -> None:
        """Copy a :class:`GateTally` onto this record (used by the ingest and the re-gate alike)."""
        self.depth_days = tally.days
        self.avg_minutes_per_day = round(tally.bars_total / tally.days, 1) if tally.days else 0.0
        self.median_minutes_per_day = _median_int(tally.minutes_per_day)
        self.min_minutes_per_day = min(tally.minutes_per_day) if tally.minutes_per_day else 0
        self.gate1_pass = tally.gate1_pass
        self.gate1_total = tally.gate1_total
        self.gate1_relieved = tally.gate1_relieved
        self.gate1_relieved_with_missing = tally.gate1_relieved_with_missing
        self.gate1_relieved_median_gap = (
            f"{_median_decimal(tally.gate1_relieved_gaps):.2f}%" if tally.gate1_relieved_gaps else ""
        )
        self.gate1p_pass = tally.gate1p_pass
        self.gate1p_total = tally.gate1p_total
        self.gate1p_no_oracle = tally.gate1p_no_oracle
        self.gate1p_above = tally.gate1p_above
        self.gate1p_below = tally.gate1p_below
        self.gate1p_worst_excess = tally.gate1p_worst_excess
        self.gate1p_failure_dates = [d.isoformat() for d, _cause in tally.gate1p_failures[:10]]
        self.gate1_and_gate2_pass = tally.gate1_and_gate2_pass
        self.usable_pass = tally.usable_pass
        self.gate2_excluded = tally.gate2_excluded
        self.gate2_missing = tally.gate2_missing
        self.gate2_duplicates = tally.gate2_duplicates
        self.gate2_ohlc = tally.gate2_ohlc
        self.gate2_negative = tally.gate2_negative
        self.gate2_negative_dates = [d.isoformat() for d in tally.gate2_negative_days[:10]]
        self.liquidity_days = tally.liquidity_days
        self.gate3_checked = tally.gate3_checked
        self.gate3_failed = tally.gate3_failed
        self.gate3_failure_rows = list(tally.gate3_failures)
        self.gate_definition = GATE_DEFINITION
        self.rebuild_discipline = REBUILD_DISCIPLINE

    def carry_prior_from(self, previous: "SymbolRecord | None") -> None:
        """Seed a fresh record from the ledger row it replaces, so a re-run stays auditable.

        Two things must survive: the BEFORE numbers (the state the architect last saw -- the oldest
        snapshot wins, never an intermediate pass) and ``reroute_attempted`` (a symbol that has
        already had its quarantine-recovery probe must never be re-probed on a resume).
        """
        if previous is None:
            return
        if previous.prior_gate1_total >= 0:
            self.prior_status = previous.prior_status
            self.prior_gate1_pass = previous.prior_gate1_pass
            self.prior_gate1_total = previous.prior_gate1_total
            self.prior_gate2_excluded = previous.prior_gate2_excluded
        elif previous.gate1_total:
            self.prior_status = previous.status
            self.prior_gate1_pass = previous.gate1_pass
            self.prior_gate1_total = previous.gate1_total
            self.prior_gate2_excluded = previous.gate2_excluded
        self.reroute_attempted = previous.reroute_attempted
        self.map_required_by_recovery = previous.map_required_by_recovery
        # A floor hunt is one-shot too: ~11 credentialed probes per event must not be re-spent on a
        # resume. The findings ride along so the report keeps them after a plain re-gate.
        self.floors_hunted = previous.floors_hunted
        self.floor_findings = list(previous.floor_findings)
        self.floors_resolved = previous.floors_resolved
        self.floor_ex_dates = list(previous.floor_ex_dates)
        self.floor_probes_spent = previous.floor_probes_spent
        self.floor_note = previous.floor_note
        self.pre_floor_gate1_pass = previous.pre_floor_gate1_pass
        self.pre_floor_gate1_total = previous.pre_floor_gate1_total
        self.floor_discipline = previous.floor_discipline
        self.floor_signatures = list(previous.floor_signatures)
        self.pre_floor_eras_provable = previous.pre_floor_eras_provable
        self.eras_promoted = previous.eras_promoted
        if self.map_required_by_recovery:
            self.route = ROUTE_MAP_REQUIRED
            self.route_reasons = [*self.route_reasons, _RECOVERY_REASON]

    def claim_floors_from_map(self, adjustment_map: "va.AdjustmentMap") -> None:
        """Re-derive this row's floor CLAIMS from the map that carries their evidence.

        REVIEW_5B finding Q5: :func:`run_floor_pass` ASSIGNED ``floors_resolved`` and
        ``floor_ex_dates`` from the floors THIS pass measured, so a floor measured in an earlier
        pass and carried forward onto a rebuilt map was erased from the ledger's counters -- ASTRAL
        and NESTLEIND each held a resolved floor, in force in their committed maps, while their
        ledger rows read ``floors_resolved = 0`` and the report printed "no event carries a vendor
        application floor". Overwriting ``floor_ex_dates`` also discarded the forced-override handle
        decision B138 exists to preserve.

        Reading the claims back off the MAP fixes it by construction: the map is the artifact the
        Q-11 addendum-2 ruling commits a floor to, so a row can only ever claim what the map can
        show, and it always claims everything the map holds. A floor resolved on EITHER side counts
        (Q-14 per-side floors): a volume-only splice is as much a measured floor as a price one.
        """
        in_force = sorted({
            floor.ex_date.isoformat()
            for floor in adjustment_map.floors
            if (floor.resolved and floor.floor_date is not None)
            or (floor.volume_resolved and floor.floor_volume is not None)
        })
        self.floor_ex_dates = in_force
        self.floors_resolved = len(in_force)

    def apply_profile(self, profile: "Gate1FailureProfile") -> None:
        self.failure_pattern = profile.verdict
        self.failure_detail = profile.detail
        self.gate1_above_ceiling = profile.above_ceiling
        self.gate1_below_floor = profile.below_floor
        self.median_daily_volume = profile.median_volume_all
        self.median_daily_volume_above_ceiling = profile.median_volume_above_ceiling
        self.era_failure_rates = [
            f"{label} {failing}/{total} ({_pct(failing, total)})"
            for label, failing, total in profile.era_rates
        ]

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def to_dict(self) -> dict:
        payload = dict(self.__dict__)
        payload["map_events"] = [dict(e.__dict__) for e in self.map_events]
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping) -> "SymbolRecord":
        data = dict(payload)
        data["map_events"] = [MapEvent(**e) for e in data.get("map_events", [])]
        data["route_reasons"] = list(data.get("route_reasons", []))
        known = {f for f in cls.__dataclass_fields__}  # tolerate a ledger from an older run
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class RunLedger:
    """The run's per-symbol outcome ledger, persisted atomically after every symbol."""

    path: Path
    started: str = ""
    records: dict[str, SymbolRecord] = field(default_factory=dict)
    halted: str = ""

    @classmethod
    def load(cls, path: Path) -> "RunLedger":
        path = Path(path)
        if not path.is_file():
            return cls(path=path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise UniverseBackfillError(
                f"The run ledger at {path} exists but will not parse ({exc}). It is a derived "
                "index -- the minute store's own window ledger is what makes the run resumable "
                "-- so it is safe to move it aside and let this run rebuild it."
            ) from exc
        return cls(
            path=path,
            started=str(payload.get("started", "")),
            halted=str(payload.get("halted", "")),
            records={
                symbol: SymbolRecord.from_dict(record)
                for symbol, record in payload.get("symbols", {}).items()
            },
        )

    def save(self) -> Path:
        payload = {
            "started": self.started,
            "halted": self.halted,
            "symbols": {s: r.to_dict() for s, r in sorted(self.records.items())},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return atomic_write_text(self.path, json.dumps(payload, indent=2, default=str))

    def record(self, record: SymbolRecord) -> None:
        record.updated_at = datetime.now().isoformat(timespec="seconds")
        self.records[record.symbol] = record
        self.save()

    def quarantined(self) -> list[str]:
        return sorted(s for s, r in self.records.items() if r.status == STATUS_QUARANTINED)


# --- gates over a settled symbol --------------------------------------------------------


@dataclass
class GateTally:
    """The CONTEXT 4.5 gate outcome for one symbol's whole stored history."""

    gate1_pass: int = 0
    gate1_total: int = 0
    gate1_missing_daily: int = 0
    gate2_excluded: int = 0
    gate3_checked: int = 0
    gate3_failed: int = 0
    gate3_failures: list[str] = field(default_factory=list)
    days: int = 0
    bars_total: int = 0
    first_day: date | None = None
    last_day: date | None = None
    closes: dict = field(default_factory=dict)
    # --- gate-2 trigger breakdown (the completeness ruling, 2026-07-26) ------------------
    #: days excluded for missing minutes -- which now requires gate 1 to have failed too.
    gate2_missing: int = 0
    gate2_duplicates: int = 0
    gate2_ohlc: int = 0
    gate2_negative: int = 0
    #: The dates that tripped the NEGATIVE-values trigger. Kept, not just counted: the live run
    #: found them all landing on ONE date across the whole universe, which is a vendor-feed fact the
    #: architect should see rather than a per-symbol accident.
    gate2_negative_days: list[date] = field(default_factory=list)
    #: The ruling's liquidity statistics: days INCLUDED while carrying tradeless minutes, and the
    #: traded-minute distribution. Reported for the trader's eyes; nothing consumes them, and no
    #: liquidity filter exists anywhere.
    liquidity_days: int = 0
    minutes_per_day: list[int] = field(default_factory=list)
    #: ``(day, gap_pct, raw_daily_volume)`` for every UNRELIEVED gate-1 failing day, and the raw
    #: daily volume of every gated day -- the inputs to :func:`gate1_failure_profile`.
    gate1_failures: list[tuple[date, "Decimal | None", int]] = field(default_factory=list)
    gate1_volumes: list[int] = field(default_factory=list)
    #: the days gate 1 actually ran on (a day with no raw daily row is not one of them).
    gate1_days: list[date] = field(default_factory=list)
    # --- auction relief (Q-12 addendum 2) -------------------------------------------------
    #: Days that FAILED gate 1 above the +5.0% ceiling and were relieved as a thin day's auction
    #: share. Counted SEPARATELY from ``gate1_pass``, exactly as the ruling requires.
    gate1_relieved: int = 0
    gate1_relieved_days: list[date] = field(default_factory=list)
    #: Of those, how many ALSO carried more than 15 tradeless minutes -- the size of decision B122
    #: (a relieved day is handed to gate 2 as "gate 1 passed").
    gate1_relieved_with_missing: int = 0
    #: Median shortfall (gap%) over the relieved days, for the report.
    gate1_relieved_gaps: list["Decimal"] = field(default_factory=list)
    # --- gate 1P: per-day PRICE containment (QUESTIONS.md Q-14) ---------------------------
    #: Gate 1P runs on EVERY stored day, so its denominator is ``days`` and not ``gate1_total``:
    #: the ruling makes "no raw daily row" a FAILURE rather than an absence, which is what closes
    #: REVIEW_5B's finding Q4 (178 stored days that were in neither numerator nor denominator).
    gate1p_pass: int = 0
    gate1p_total: int = 0
    gate1p_no_oracle: int = 0
    gate1p_above: int = 0
    gate1p_below: int = 0
    #: ``(day, cause)`` per failing day -- the input to the gate-1P cluster signature.
    gate1p_failures: list[tuple[date, str]] = field(default_factory=list)
    #: The worst per-side excess seen, in paise, for the report.
    gate1p_worst_excess: int = 0
    #: ``day -> (fold high, fold low, minute volume sum)`` for every stored day, kept so the Q-14
    #: recovery pass can measure its floors from the SAME read rather than walking the parquet store
    #: a second time. It is the two observables a floor search needs and nothing else.
    folds: dict[date, tuple[int, int, int]] = field(default_factory=dict)
    # --- OVERLAP-AWARE intersections (REVIEW_5B finding Q3) --------------------------------
    #: Days passing gate 1 (effective) AND gate 2, counted per day rather than by subtracting two
    #: totals. The subtraction was wrong by >= 1,012 days because a gate-2 missing-minutes
    #: exclusion can only fire on a day gate 1 already failed.
    gate1_and_gate2_pass: int = 0
    #: Days passing gate 1 (effective) AND gate 2 AND gate 1P -- the USABLE count chunk 9 consumes.
    usable_pass: int = 0

    @property
    def gate1_effective_pass(self) -> int:
        """Strict gate-1 passes PLUS auction-relief passes -- what coverage is measured on."""
        return self.gate1_pass + self.gate1_relieved


def gate_symbol(
    minute_store: MinuteStore, cache: DailyCache, symbol: str, *, since: date | None = None
) -> GateTally:
    """Run CONTEXT 4.5 gates 1 and 2 over every stored symbol-day, a month at a time.

    Gate 1 runs FIRST and its verdict is handed to gate 2, because the completeness ruling
    (2026-07-26) makes gate 1 the completeness oracle: absent minute stamps exclude a day only when
    gate 1 has also failed on it. On a gate-1-passing day the same absent stamps are tradeless
    minutes and are counted as liquidity instead.

    A gate-1 failure ABOVE the +5.0% ceiling is then offered to :func:`acumen.quality_gates.
    auction_relief` (QUESTIONS.md Q-12 addendum 2). The band is untouched -- ``gate1_pass`` stays
    the STRICT count and a relieved day lands in ``gate1_relieved``, its own field. Decision B122:
    a relieved day is handed to gate 2 as ``volume_reconciled=True``, because the relief conditions
    (extremes and opening print matching the exchange's own daily record, exactly) are direct
    evidence that nothing was lost -- which is the very hypothesis the gate-2 missing-minutes
    trigger exists to catch. ``gate1_relieved_with_missing`` measures how often that mattered.

    GATE 1P (QUESTIONS.md Q-14) runs beside gate 1 on EVERY stored day, from the same fold: the
    1-minute high/low the relief conditions already compute, against the same raw daily row. A day
    with no raw daily row FAILS it (the ruling's own words), which is why its denominator is every
    stored day rather than the gated ones. Its failures are counted under their own reason and
    never folded into gate 1's numerator.

    The intersections are counted PER DAY (``gate1_and_gate2_pass``, ``usable_pass``) rather than
    derived by subtracting two totals -- REVIEW_5B finding Q3: the subtraction understated the
    both-gates figure by at least 1,012 days, because a gate-2 missing-minutes exclusion can only
    fire on a day gate 1 already failed.
    """
    tally = GateTally()
    for day, bars in minute_store.iter_days(symbol, since, None):
        tally.days += 1
        tally.bars_total += len(bars)
        tally.first_day = tally.first_day or day
        tally.last_day = day
        tally.closes[day] = bars[-1].close_paise
        row = cache.day(symbol, day)
        fold_high = max(b.high_paise for b in bars)
        fold_low = min(b.low_paise for b in bars)
        tally.folds[day] = (fold_high, fold_low, sum(b.volume for b in bars))
        price = gates.price_containment_gate(
            fold_high, fold_low,
            None if row is None else row.high_paise,
            None if row is None else row.low_paise,
        )
        tally.gate1p_total += 1
        if price.passed:
            tally.gate1p_pass += 1
        else:
            tally.gate1p_failures.append((day, price.cause))
            if price.cause == gates.GATE1P_NO_ORACLE:
                tally.gate1p_no_oracle += 1
            elif price.cause == gates.GATE1P_ABOVE:
                tally.gate1p_above += 1
            else:
                tally.gate1p_below += 1
            worst = max(price.high_excess_paise or 0, price.low_excess_paise or 0)
            tally.gate1p_worst_excess = max(tally.gate1p_worst_excess, int(worst))
        reconciled: bool | None = None
        relieved = False
        if row is None:
            tally.gate1_missing_daily += 1
        else:
            tally.gate1_total += 1
            tally.gate1_volumes.append(row.volume)
            tally.gate1_days.append(day)
            result = gates.volume_gate(row.volume, tally.folds[day][2])
            if result.passed:
                tally.gate1_pass += 1
            else:
                relief = gates.auction_relief(
                    result,
                    minute_open_paise=bars[0].open_paise,
                    minute_high_paise=fold_high,
                    minute_low_paise=fold_low,
                    raw_open_paise=row.open_paise,
                    raw_high_paise=row.high_paise,
                    raw_low_paise=row.low_paise,
                )
                relieved = relief.relieved
                if relieved:
                    tally.gate1_relieved += 1
                    tally.gate1_relieved_days.append(day)
                    if result.gap_pct is not None:
                        tally.gate1_relieved_gaps.append(result.gap_pct)
                else:
                    tally.gate1_failures.append((day, result.gap_pct, row.volume))
            reconciled = result.passed or relieved
        integrity = gates.integrity_gate(bars, day, volume_reconciled=reconciled)
        tally.minutes_per_day.append(integrity.present)
        if relieved and integrity.missing > gates.MAX_MISSING_MINUTES:
            tally.gate1_relieved_with_missing += 1
        if integrity.liquidity_note and integrity.passed:
            tally.liquidity_days += 1
        if not integrity.passed:
            tally.gate2_excluded += 1
            if integrity.missing_excluded:
                tally.gate2_missing += 1
            if integrity.duplicates:
                tally.gate2_duplicates += 1
            if integrity.ohlc_violations:
                tally.gate2_ohlc += 1
            if integrity.negative_values:
                tally.gate2_negative += 1
                tally.gate2_negative_days.append(day)
        # The overlap-aware intersections, counted per day (finding Q3).
        if reconciled is True and integrity.passed:
            tally.gate1_and_gate2_pass += 1
            if price.passed:
                tally.usable_pass += 1
    return tally


# --- the quarantine failure-pattern analysis (Q-12 addendum ruling; PURE) -----------------

PATTERN_CLUSTERED: str = "clustered-before-ex-date (adjustment problem)"
PATTERN_SCATTERED: str = "scattered (auction/liquidity shape)"
#: A THIRD bucket the ruling did not ask for -- Class-B, decision B145 (REVIEW_5B finding C16).
#: The ruling names two patterns; forcing a symbol that matches neither into one of them would be
#: the report asserting a diagnosis it does not have, so "mixed" says so instead. Report-only.
PATTERN_MIXED: str = "mixed"
PATTERN_NONE: str = "no gate-1 failures"

#: An era whose failure rate is at or above this is "clustered" -- essentially every day of that
#: span fails, which is what a wrong adjustment factor does (it is applied to the whole era).
#: **CLASS-B, recorded as decision B145** (REVIEW_5B finding C16). The Q-12-addendum ruling asks for
#: a verdict of "clustered before a CA ex-date (adjustment problem) vs scattered (auction/liquidity
#: shape)" and names no numbers, so these two are this repo's reading of its own words. They are
#: REPORT-ONLY: nothing in the run consumes the verdict, and no day's inclusion depends on it.
_CLUSTER_RATE: Decimal = Decimal("0.90")
#: An era below this is not carrying a systematic adjustment error. Class-B, decision B145.
_SCATTER_RATE: Decimal = Decimal("0.50")


@dataclass
class Gate1FailureProfile:
    """Why a symbol still fails gate 1 after the map pass -- the ruling's failure-pattern analysis.

    The two hypotheses the architect named are separable from the data we already hold:

    * an **adjustment problem** applies ONE wrong factor to a whole era, so the failures CLUSTER --
      nearly every day before some CA ex-date fails and the days after it pass;
    * an **auction/liquidity shape** fails a day when the pre-open auction is a large fraction of a
      thin day's volume, so the failures SCATTER across eras, land ABOVE the +5.0% ceiling, and sit
      on days whose raw daily volume is far below the symbol's own median.

    ``above_ceiling`` / ``below_floor`` and the volume medians are the per-symbol evidence the ruling
    asks be flagged for the DEFERRED +5.0%-ceiling decision. No band is tuned here.
    """

    verdict: str = PATTERN_NONE
    failures: int = 0
    gated_days: int = 0
    above_ceiling: int = 0
    below_floor: int = 0
    undefined_gap: int = 0
    median_volume_all: int = 0
    median_volume_failing: int = 0
    median_volume_above_ceiling: int = 0
    #: ``(era label, failing, total)`` per inter-ex-date span, newest span last.
    era_rates: list[tuple[str, int, int]] = field(default_factory=list)
    detail: str = ""


def _median_int(values: Sequence[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) // 2


def _median_decimal(values: Sequence[Decimal]) -> Decimal:
    if not values:
        return Decimal(0)
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal(2)


def gate1_failure_profile(tally: GateTally, ex_dates: Sequence[date]) -> Gate1FailureProfile:
    """Classify a symbol's gate-1 failures as an adjustment problem or a liquidity shape. PURE."""
    profile = Gate1FailureProfile(failures=len(tally.gate1_failures), gated_days=tally.gate1_total)
    profile.median_volume_all = _median_int(tally.gate1_volumes)
    if not tally.gate1_failures:
        profile.detail = "no gate-1 failure to explain"
        return profile

    above_volumes: list[int] = []
    for _day, gap, volume in tally.gate1_failures:
        if gap is None:
            profile.undefined_gap += 1
        elif gap > gates.VOLUME_GAP_MAX_PCT:
            profile.above_ceiling += 1
            above_volumes.append(volume)
        else:
            profile.below_floor += 1
    profile.median_volume_failing = _median_int([v for _d, _g, v in tally.gate1_failures])
    profile.median_volume_above_ceiling = _median_int(above_volumes)

    failing_days = {day for day, _gap, _vol in tally.gate1_failures}
    gated_days = sorted(tally.gate1_days)
    bounds = sorted({ex for ex in ex_dates})
    edges = [*bounds, date.max]
    low = date.min
    rates: list[tuple[str, int, int]] = []
    for edge in edges:
        span = [d for d in gated_days if low <= d < edge]
        if span:
            label = f"< {edge.isoformat()}" if edge is not date.max else f">= {low.isoformat()}"
            rates.append((label, sum(1 for d in span if d in failing_days), len(span)))
        low = edge
    profile.era_rates = rates

    worst = max((Decimal(f) / Decimal(t) for _l, f, t in rates), default=Decimal(0))
    newest = rates[-1] if rates else None
    newest_rate = Decimal(newest[1]) / Decimal(newest[2]) if newest else Decimal(0)
    if len(rates) > 1 and worst >= _CLUSTER_RATE and newest_rate <= (_ONE - _CLUSTER_RATE):
        profile.verdict = PATTERN_CLUSTERED
        profile.detail = (
            "an era fails at "
            f"{worst:.1%} while the post-last-ex-date era fails at {newest_rate:.1%} -- one wrong "
            "factor applied to a whole span, not a market property"
        )
    elif worst < _SCATTER_RATE:
        profile.verdict = PATTERN_SCATTERED
        profile.detail = (
            f"no era fails above {worst:.1%}; {profile.above_ceiling} of {profile.failures} "
            "failures are ABOVE the +5.0% ceiling, median raw daily volume on those days "
            f"{profile.median_volume_above_ceiling:,} vs the symbol's median "
            f"{profile.median_volume_all:,} -- the auction share of a thin day, not an adjustment"
        )
    else:
        profile.verdict = PATTERN_MIXED
        profile.detail = (
            f"worst era failure rate {worst:.1%}, post-last-ex-date era {newest_rate:.1%}; "
            f"{profile.above_ceiling} above the ceiling / {profile.below_floor} below the floor -- "
            "neither pattern is clean"
        )
    return profile


def share_count_factors_by_ex_date(
    symbol: str, factors: Sequence[ca.Factor]
) -> dict[date, tuple[Decimal, tuple[str, ...]]]:
    """Group a symbol's share-count factors by ex-date, MULTIPLYING same-day events. PURE.

    Two corporate actions can land on the same ex-date, and then only their PRODUCT describes
    the price step. 360ONE is the measured case: a 1:1 bonus (k = 0.5) AND a face-value split
    2 -> 1 (k = 0.5) both ex 2023-03-02, so the raw price falls to a QUARTER overnight. Testing
    either factor alone reports a 50% "failure" on a series that is perfectly continuous --
    which is exactly what this function exists to prevent. CONTEXT 4.2's own instruction is to
    "chain multiple events".
    """
    wanted = symbol.strip().upper()
    grouped: dict[date, tuple[Decimal, tuple[str, ...]]] = {}
    for factor in factors:
        if factor.symbol != wanted or factor.kind not in ca.SHARE_COUNT_KINDS or factor.k == _ONE:
            continue
        product, kinds = grouped.get(factor.ex_date, (_ONE, ()))
        grouped[factor.ex_date] = (product * factor.k, kinds + (factor.kind,))
    return grouped


def gate3_over_events(
    tally: GateTally, symbol: str, factors: Sequence[ca.Factor]
) -> None:
    """CONTEXT 4.5 gate 3 over every share-count ex-date inside the stored span.

    The spec's own scope: "on every split/bonus ex-date in history, adjusted series must show
    |day-over-day gap| < 20%". Applied to the stored RAW closes with the ex-date's CHAINED
    factor brought in at the comparison (:func:`acumen.quality_gates.
    adjustment_continuity_gate`). Mutates the tally in place so a symbol's whole gate picture
    lives in one object.

    A FAILURE is recorded as a pipe-delimited row carrying the NUMBERS the architect is owed as
    well as the diagnostic sentence:
    ``symbol|events|ex_date|k|pre_ex_day|ex_day|raw_gap%|adjusted_gap%|reason``. The RAW gap
    is the same two stored closes with NO factor applied; the ADJUSTED gap is CONTEXT 4.5's own
    test. Both together are what makes a failure diagnosable -- a raw gap near ``k - 1`` with an
    adjusted gap near zero is a healthy event, while a raw gap near ZERO with a large adjusted gap
    means the two closes are already in the SAME price domain, i.e. the pre-ex side was never
    un-adjusted for the event. That is exactly the shape a vendor application floor leaves behind.
    """
    if not tally.closes:
        return
    days = sorted(tally.closes)
    for ex_date, (k, kinds) in sorted(share_count_factors_by_ex_date(symbol, factors).items()):
        before = [d for d in days if d < ex_date]
        after = [d for d in days if d >= ex_date]
        if not before or not after:
            continue  # the ex-date sits outside the stored span; nothing to compare
        pre_day, ex_day = before[-1], after[0]
        pre_close, ex_close = tally.closes[pre_day], tally.closes[ex_day]
        result = gates.adjustment_continuity_gate(
            ex_date, pre_day, ex_day, pre_close, ex_close, k,
        )
        tally.gate3_checked += 1
        if not result.passed:
            tally.gate3_failed += 1
            raw_gap = (Decimal(ex_close - pre_close) / Decimal(pre_close)) * Decimal(100)
            tally.gate3_failures.append("|".join((
                symbol, "+".join(kinds), ex_date.isoformat(), str(k),
                pre_day.isoformat(), ex_day.isoformat(),
                f"{raw_gap:.2f}", f"{result.gap * Decimal(100):.2f}", result.reason,
            )))


# --- the SIGNATURE GATE (Q-11 addendum 4 clause i; PURE) ----------------------------------


def same_price_domain(raw_gap: Decimal, k: Decimal) -> bool:
    """Are the two closes of a gate-3 failure already in the SAME price domain? PURE.

    The Q-11 addendum-4 nearest-hypothesis predicate, written ONCE (REVIEW_5B finding C13: it lived
    both in the tested signature gate and, inline, in the untested report classifier, so the two
    could drift). A healthy event predicts a raw gap of size ``|k - 1|``; a pre-ex side that was
    never un-adjusted predicts a raw gap of size 0; the event qualifies when the measured magnitude
    is nearer 0 than the event's own step -- ``|raw_gap| < |k - 1| / 2``.
    """
    step = abs(k - _ONE)
    return step > 0 and abs(raw_gap) < step / Decimal(2)


def gate3_signature_events(gate3_failure_rows: Sequence[str]) -> dict[date, str]:
    """Ex-dates whose gate-3 failure shows the RAW-GAP-NEAR-ZERO signature. PURE.

    The ruling admits an event into an un-provable era's floor hunt when "it shows the
    raw-gap-near-zero gate-3 signature". The rows already carry both numbers
    (``symbol|events|ex_date|k|pre|ex|raw_gap%|adjusted_gap%|reason``), so the test is a
    NEAREST-HYPOTHESIS one rather than an invented threshold -- there are exactly two models for a
    gate-3 failure's raw gap and the measurement picks one:

    * a HEALTHY event predicts a raw gap of size ``|k - 1|`` (the price step the event itself makes);
    * a pre-ex side that was never un-adjusted predicts a raw gap of size 0 (both closes already in
      the same price domain), which is what a vendor application floor above the pre-ex day leaves.

    The event qualifies when the SIZE of the measured raw gap is nearer 0 than the size of the
    event's own step -- ``|raw_gap| < |k - 1| / 2``. Magnitudes, not signed values: a raw gap of
    +38% against a step of -20% is not "the same price domain" by any reading, and a signed nearest
    test would admit it. Scale-free by construction, so a 5:1 split and a 5% special dividend are
    judged on the same footing rather than against an invented percentage.

    On the FIX-3 residual table this admits exactly the ELEVEN rows the architect named (raw gaps
    -4.63%..+10.98% against HALF-steps of 12.5%..45%) and rejects the six that are a different
    defect: ASTRAL +38.49% (k = 0.8, so a 20% step and a 10% half-step), BPCL +101.21%, GAIL 2018
    +201.98%, OIL 2018 +42.44%, VBL -65.70% and COCHINSHIP -40.00% (k = 0.5, so a 50% step and a
    25% half-step -- and its raw gap is nearly that healthy -50%). REVIEW_5B finding C14: the
    figures quoted here are HALF-steps, which the previous wording mislabelled as steps; the
    arithmetic below was and is right.
    """
    admitted: dict[date, str] = {}
    for row in gate3_failure_rows:
        parts = row.split("|")
        if len(parts) < 8:
            continue
        try:
            ex_date = date.fromisoformat(parts[2])
            k = Decimal(parts[3])
            raw_gap = Decimal(parts[6]) / Decimal(100)
            adjusted_gap = Decimal(parts[7]) / Decimal(100)
        except (ValueError, ArithmeticError):
            continue
        step = abs(k - _ONE)
        if same_price_domain(raw_gap, k):
            admitted[ex_date] = (
                f"{SIGNATURE_GATE3}: |raw gap| {abs(raw_gap) * 100:.2f}% is nearer 0 than the "
                f"event's own step {step * 100:.2f}% (k={k}), adjusted gap "
                f"{adjusted_gap * 100:.2f}% -- both closes are already in the same price domain"
            )
    return admitted


def era_cliff_events(
    tally: GateTally,
    ex_dates: Sequence[date],
    *,
    min_rate: Decimal = FLOOR_HUNT_ERA_CLIFF_RATE,
    min_days: int = MIN_CLIFF_DAYS,
) -> dict[date, str]:
    """Ex-dates whose immediately-below span fails gate 1 at ``min_rate`` or more. PURE.

    The ruling's second signature: "an era failure-rate cliff (>=95% failing) at an event boundary".
    The span measured is the gated days from the previous event's ex-date up to (not including) this
    one -- the days whose chain that event is the newest member of. ``min_days`` keeps a week-long
    bucket from manufacturing a cliff out of a handful of days.
    """
    failing = {day for day, _gap, _volume in tally.gate1_failures}
    gated = sorted(tally.gate1_days)
    bounds = sorted({ex for ex in ex_dates})
    admitted: dict[date, str] = {}
    low = date.min
    for ex_date in bounds:
        span = [d for d in gated if low <= d < ex_date]
        low = ex_date
        if len(span) < min_days:
            continue
        failures = sum(1 for d in span if d in failing)
        rate = Decimal(failures) / Decimal(len(span))
        if rate >= min_rate:
            admitted[ex_date] = (
                f"{SIGNATURE_CLIFF}: {failures}/{len(span)} = {rate:.1%} of the gated days below "
                f"{ex_date.isoformat()} fail gate 1 (>= {min_rate:.0%})"
            )
    return admitted


def cluster_prefix(
    span: Sequence[date],
    failing: set[date],
    *,
    min_rate: Decimal = FLOOR_HUNT_ERA_CLIFF_RATE,
    min_days: int = MIN_CLIFF_DAYS,
) -> int | None:
    """The length of the OLD-END BLOCK of ``span`` that fails, or ``None`` if there is no block. PURE.

    A vendor application floor is a STEP: every day below the splice carries one chain and every day
    above it carries another. Read through a gate that fails exactly one of the two, that is a
    contiguous block of failures anchored at the OLD end of the span and a clean remainder above it.
    This measures precisely that shape and refuses everything else:

    * the longest old-end prefix ENDING ON A FAILING DAY and failing at ``min_rate`` or more, and
      at least ``min_days`` long -- so a handful of scattered failures can never be called a splice,
      and a block is not allowed to swallow the clean days just above it (at a 95% rate a 30-day
      block would otherwise "extend" to 31 and mis-state where the step is);
    * with the REMAINDER above it failing at no more than ``1 - min_rate`` -- so a span that fails
      everywhere in patches is not a step either.

    A block covering the WHOLE span (empty remainder) is the shape :func:`era_cliff_events` already
    admits, so the two signatures agree where they overlap rather than contradicting each other.
    """
    best: int | None = None
    fails = 0
    for index, day in enumerate(span, start=1):
        if day not in failing:
            continue
        fails += 1
        if index >= min_days and Decimal(fails) / Decimal(index) >= min_rate:
            best = index
    if best is None:
        return None
    remainder = span[best:]
    if remainder:
        rem_fail = sum(1 for d in remainder if d in failing)
        if Decimal(rem_fail) / Decimal(len(remainder)) > (_ONE - min_rate):
            return None
    return best


def gate1p_cluster_events(
    tally: GateTally,
    ex_dates: Sequence[date],
    *,
    min_rate: Decimal = FLOOR_HUNT_ERA_CLIFF_RATE,
    min_days: int = MIN_CLIFF_DAYS,
) -> dict[date, str]:
    """Ex-dates whose immediately-below span carries a GATE-1P failure CLUSTER. PURE.

    QUESTIONS.md Q-14's third admitting signature: "hunts SIGNATURE-GATED by gate-1P failure
    clusters at era/event boundaries". Same two constants as :func:`era_cliff_events` -- the same
    rate over the same minimum span -- read off the PRICE gate instead of the volume one, and
    measured as a STEP (:func:`cluster_prefix`) rather than as a whole-span rate, because a splice
    sitting INSIDE an era leaves exactly a block and not a uniform failure.

    That is the shape the defect actually has: NMDC's era ``pre-2019-03-22`` fails gate 1P on its
    oldest 133 sessions at 1.4173x the traded price and reconciles perfectly above them. A whole-span
    rate reads that as 55% and admits nothing; the block reads it as the step it is.

    Days with NO raw daily row are excluded from both numerator and denominator: they fail gate 1P
    for want of an oracle, which says nothing about the vendor's archive and would otherwise
    manufacture a cluster out of a data hole.
    """
    failing = {
        day for day, cause in tally.gate1p_failures if cause != gates.GATE1P_NO_ORACLE
    }
    no_oracle = {day for day, cause in tally.gate1p_failures if cause == gates.GATE1P_NO_ORACLE}
    gated = sorted(day for day in tally.closes if day not in no_oracle)
    bounds = sorted({ex for ex in ex_dates})
    admitted: dict[date, str] = {}
    low = date.min
    for ex_date in bounds:
        span = [d for d in gated if low <= d < ex_date]
        low = ex_date
        block = cluster_prefix(span, failing, min_rate=min_rate, min_days=min_days)
        if block is None:
            continue
        admitted[ex_date] = (
            f"{SIGNATURE_GATE1P}: the oldest {block} of the {len(span)} stored days below "
            f"{ex_date.isoformat()} fail gate 1P as a contiguous block (>= {min_rate:.0%}) while "
            f"the {len(span) - block} above them are clean -- a STEP, which is what a per-side "
            "vendor splice leaves behind"
        )
    return admitted


def gate1p_recovery_events(
    tally: GateTally, adjustment_map: "va.AdjustmentMap"
) -> dict[date, str]:
    """The events the Q-14 recovery pass may hunt a per-side floor for, with the reason. PURE.

    A gate-1P cluster is a property of an ERA -- it says "a splice sits inside this span" -- while a
    floor belongs to an EVENT. The bridge is the era's own committed chain: the events that could
    possibly have been spliced here are exactly the ones the era applies with a factor that is not
    already 1 (an event committed ABSENT has nothing to drop, so no floor for it could change one
    stored price). Every such event is admitted, and the BISECTION decides which of them actually
    carries a splice -- a wrong candidate simply fails to resolve, and the acceptance test discards
    anything that does not pay for itself.

    That keeps the ruling's "never blanket" honest at the level it can be honest at: no era without
    a measured cluster is entered at all, and inside one the candidate list is the era's own chain
    rather than every event in the symbol's history.
    """
    clusters = gate1p_cluster_events(tally, adjustment_map.all_event_ex_dates)
    admitted: dict[date, str] = {}
    for boundary, why in clusters.items():
        era = next((e for e in adjustment_map.eras if e.ex_dates and e.ex_dates[0] == boundary), None)
        if era is None or not era.provable:
            # An UN-PROVABLE era commits no chain, so there is no factor to drop and no floor can
            # change one stored price. The ruling's own fallback stands: un-provable remains
            # un-provable, and the flagged days are disclosed residuals excluded by gate 1P.
            continue
        for choice in era.choices:
            if choice.price_factor == _ONE and choice.volume_factor == _ONE:
                continue
            admitted.setdefault(choice.ex_date, f"{why} [era {era.label}]")
    return admitted


def signature_gated_events(
    tally: GateTally, ex_dates: Sequence[date], gate3_failure_rows: Sequence[str]
) -> dict[date, str]:
    """Every event admitted into an UN-PROVABLE era's floor hunt, with its reason. PURE.

    Q-11 addendum 4 clause (i): "hunting is SIGNATURE-GATED, never blanket". This is the whole gate;
    an event absent from the result is never hunted inside an un-provable era, however badly that
    era fails. Every signature that fires is reported, because the report should show all the
    evidence the hunt acted on.

    Q-14 adds the third: a GATE-1P failure cluster (:func:`gate1p_cluster_events`).
    """
    gate3 = gate3_signature_events(gate3_failure_rows)
    cliff = era_cliff_events(tally, ex_dates)
    price = gate1p_cluster_events(tally, ex_dates)
    admitted: dict[date, str] = {}
    for ex_date in sorted({*gate3, *cliff, *price}):
        reasons = [
            r for r in (gate3.get(ex_date), cliff.get(ex_date), price.get(ex_date)) if r
        ]
        admitted[ex_date] = " AND ".join(reasons)
    return admitted


# --- the run ----------------------------------------------------------------------------


@dataclass
class RunConfig:
    """Everything the run needs that is not a live connection."""

    minute_store: MinuteStore
    daily_store: DailyStore
    ledger_path: Path
    map_data_dir: Path
    end: date
    start: date = mb.MINUTE_DATA_FLOOR
    max_symbols: int | None = None
    skip_verify: bool = False
    report_path: Path = DEFAULT_REPORT_PATH


def verify_the_oracle(
    daily_store: DailyStore, *, log: Callable[[str], None] = print, **verify_kwargs
) -> None:
    """Run the REVIEW_2 F7 check on the daily store and REFUSE to continue on any anomaly."""
    log("verifying the daily store (the oracle both the maps and gate 1 lean on) ...")
    result = daily_store.verify(**verify_kwargs)
    log(f"  range {result.from_date} .. {result.to_date}; {result.months_read} month files; "
        f"{result.ledger_present_dates} file-present dates; {result.rows_total:,} rows")
    for note in result.notes:
        log(f"  note      : {note}")
    if not result.ok:
        for anomaly in result.anomalies[:50]:
            log(f"  ANOMALY   : {anomaly}")
        raise UniverseBackfillError(
            f"the daily store has {len(result.anomalies)} anomaly/anomalies (see above). The "
            "minute run is NOT started: the daily store is the oracle every adjustment map is "
            "measured against and every gate-1 volume is reconciled to, so a hole in it would "
            "silently become a hole in the minute layer. Report to the architect."
        )
    log("  daily store VERIFIED clean.")


def resolve_universe(
    *, cache_dir: Path | None = None, allow_network: bool = False, snapshot: Path | None = None
) -> tuple[str, ...]:
    """Today's F&O universe (CONTEXT 3.1/4.1, E5) from a snapshot, the day-cache, or live."""
    if snapshot is not None:
        return universe_module.load_universe(snapshot)
    if allow_network:
        return universe_module.fetch_universe(cache_dir=cache_dir, allow_network=True)
    _fetched_on, symbols = universe_module.load_cached_universe(cache_dir)
    return symbols


def plan_symbol(
    symbol: str,
    master: InstrumentMaster,
    cache: DailyCache,
    actions: Sequence[ca.CorporateAction],
    cached_store: CachedDailyStore,
    config: RunConfig,
) -> tuple[SymbolRecord, mb.SymbolCorpActions | None, RouteDecision | None, int | None]:
    """Resolve token, listing clamp, corporate actions and route for one symbol. No network."""
    record = SymbolRecord(symbol=symbol)
    try:
        master.token(symbol)
    except InstrumentMasterError:
        record.status = STATUS_NO_TOKEN
        record.note = "not in the NSE cash instrument master (delisted, renamed, or not -EQ)"
        return record, None, None, None

    first_daily = cache.first_date(symbol)
    if first_daily is None:
        record.status = STATUS_NO_DAILY_HISTORY
        record.note = (
            "no EQ/BE/BZ rows in the raw daily store over the window, so gate 1 has nothing to "
            "reconcile against (Q-4: a symbol's history starts at its first equity row)"
        )
        return record, None, None, None

    clamp = mb.clamp_start(config.start, first_daily)
    record.clamp_start = clamp.isoformat()
    view = mb.corp_actions_for_symbol(symbol, actions, cached_store)
    decision = classify_route(
        symbol,
        factors=view.factors,
        suppressions=view.suppressions,
        pending=view.pending,
        parse_exceptions=view.parse_exceptions,
        since=clamp,
        until=config.end,   # F: the un-adjustment window is (D, F]; a future ex-date is in none
    )
    record.route = decision.route
    record.route_reasons = list(decision.reasons)
    return record, view, decision, mb._tick_paise(master, symbol)  # noqa: SLF001


def unparsed_ex_dates(view: mb.SymbolCorpActions, symbol: str) -> tuple[date, ...]:
    """The ex-dates of subjects on ``symbol`` the CONTEXT 4.2 parser could not classify. PURE.

    These are exactly the ``ParseException``s the Q-11 routing rule already treats as
    map-forcing. Under the Q-11 addendum-3 clause (ii) they become map NODES as well, with
    candidates ``{measured, absent}`` -- so an unparsed subject no longer forces a symbol onto the
    map path and then contributes nothing for the map to be built FROM.
    """
    wanted = symbol.strip().upper()
    return tuple(sorted({
        exception.action.ex_date
        for exception in view.parse_exceptions
        if exception.action.symbol == wanted
    }))


def build_map_for(
    client,
    cached_store: CachedDailyStore,
    cache: DailyCache,
    symbol: str,
    token: str,
    view: mb.SymbolCorpActions,
    clamp: date,
    config: RunConfig,
    tick_paise: int | None,
    *,
    floors: Sequence["va.EventFloor"] = (),
    log: Callable[[str], None] = print,
) -> tuple["va.AdjustmentMap | None", int, int]:
    """Probe every era of ``symbol``'s ingest span and build + persist its map.

    Returns ``(map, unprobed_era_count, floors_dropped)``; the map is ``None`` when no era could be
    probed at all.

    Already-measured vendor APPLICATION FLOORS are CARRIED onto the rebuilt map
    (:func:`acumen.vendor_adjustment.carry_floors_forward`). A rebuild happens whenever the map's
    fetch date moves -- which is every calendar day -- and a floor is a property of the vendor's
    archive, not of when we last looked at it. Rebuilding without carrying would drop the committed
    probe evidence the Q-11 addendum-2 ruling requires, and would leave the next fresh fetch of
    those days dividing by a chain the vendor never applied. A floor whose event no longer resolves
    to the same factor is DROPPED and counted, so the caller can re-open the hunt.

    ``floors`` are floors measured by THIS run's hunt, handed to the builder so the arbitration
    happens WITH them in force (Q-11 addendum 4 clause iii): a floored event is absent from the eras
    it does not reach, stops consuming the probe-gap guard's one degree of freedom, and the era then
    stands or falls on the same oracle as every other era. That is how a promotion is earned.

    When the caller passes NONE, the previously committed map's own resolved floors are used
    instead (REVIEW_5B finding C5): the steady-state rebuild paths called this with no floors, so a
    rebuild re-arbitrated a floor-PROMOTED era from scratch -- ``carry_floors_forward`` re-attached
    the evidence afterwards but never re-decided ``era.provable``, and CANBK's committed map ended
    up marking un-provable an era whose stored days measure price-contained and in-band. A floor is
    a measured property of the vendor's archive; a rebuild must arbitrate WITH it, not around it.
    """
    try:
        previous = mb.load_adjustment_map_for(symbol, data_dir=config.map_data_dir)
    except va.VendorAdjustmentError:
        previous = None
    if not floors and previous is not None:
        floors = [f for f in previous.floors if f.resolved or f.volume_resolved]
        if floors:
            log(f"    rebuilding WITH {len(floors)} already-measured floor(s) in force "
                "(finding C5): the arbitration sees the splice, not just its evidence")
    events = va.events_from_factor_table(
        view.factors, view.suppressions, view.pending_rights_ex_dates, symbol=symbol,
        # Q-11 addendum 3 clause (ii): an UNPARSED subject needs no parsing to enter the map. It
        # was already forcing this symbol onto the map path (the routing rule's conservative
        # clause) while contributing NO era key -- which is what left COLPAL with a map-required
        # route and zero probeable eras. It now participates with {measured, absent}.
        unparsed_ex_dates=unparsed_ex_dates(view, symbol),
    )
    windows, unprobeable = era_probe_windows(events, cache.days(symbol), clamp, config.end)
    if unprobeable:
        log(f"    {len(unprobeable)} era(s) have no trading day to probe -- older spans stay "
            "un-provable (excluded + counted)")
    if not windows:
        return None, len(unprobeable), 0
    log(f"    probing {len(windows)} era(s): {[w.label for w in windows]}")
    eras = va.measure_symbol_live(
        client, cached_store, symbol, token, events, windows, config.end
    )
    if not eras:
        return None, len(unprobeable), 0
    amap = va.build_map(symbol, config.end, events, eras, tick_paise=tick_paise, floors=floors)
    amap, dropped = va.carry_floors_forward(previous, amap)
    if amap.floors:
        log(f"    carried {len(amap.floors)} already-measured floor(s) onto the rebuilt map: "
            + ", ".join(
                f"{f.ex_date}->{f.floor_date}" for f in amap.floors if f.floor_date
            ))
    for floor in dropped:
        log(f"    DROPPED floor {floor.ex_date}->{floor.floor_date}: its event no longer resolves "
            "to the factor the probes were classified under; the hunt re-opens")
    va.persist_map(amap, data_dir=config.map_data_dir)
    return amap, len(unprobeable), len(dropped)


def process_symbol(
    client,
    master: InstrumentMaster,
    cache: DailyCache,
    cached_store: CachedDailyStore,
    actions: Sequence[ca.CorporateAction],
    symbol: str,
    config: RunConfig,
    *,
    log: Callable[[str], None] = print,
    previous: SymbolRecord | None = None,
) -> SymbolRecord:
    """Route, map, ingest and gate ONE symbol. Every failure lands in the record, never a crash."""
    record, view, decision, tick_paise = plan_symbol(
        symbol, master, cache, actions, cached_store, config
    )
    record.carry_prior_from(previous)
    if previous is not None and previous.gate1_total:
        record.snapshot_prior()  # this pass may move the numbers; freeze what came before it
    if view is None or decision is None:
        log(f"  {symbol}: {record.status} -- {record.note}")
        return record

    clamp = date.fromisoformat(record.clamp_start or config.start.isoformat())
    log(f"  {symbol}: route={record.route} clamp={clamp}"
        + (f" ({len(record.route_reasons)} forcing event(s))" if record.route_reasons else ""))

    adjustment_map: "va.AdjustmentMap | None" = None
    # The classifier reads the CA table, which does not know a quarantine recovery ever happened --
    # so the recovery decision is carried on the ledger row and ORs in here (Q-12 addendum).
    map_required = decision.map_required or record.map_required_by_recovery
    if map_required:
        try:
            adjustment_map = mb.load_adjustment_map_for(symbol, data_dir=config.map_data_dir)
        except va.VendorAdjustmentError:
            adjustment_map = None
        if adjustment_map is not None and not va.map_is_current(adjustment_map):
            # Built under the SUPERSEDED median volume estimator (Q-12). Its committed volume factors
            # came from a biased estimator and its un-provable eras may be provable under the ruled
            # one, so it is rebuilt from probe windows -- never consumed.
            log("    map is STALE -- estimator "
                f"{adjustment_map.volume_estimator_id or '(none)'} vs {va.MAP_VOLUME_ESTIMATOR}, "
                f"model {adjustment_map.map_model_id or '(none)'} vs {va.MAP_MODEL}; rebuilding")
            adjustment_map = None
        if adjustment_map is None or adjustment_map.fetch_date != config.end:
            try:
                adjustment_map, unprobed, dropped = build_map_for(
                    client, cached_store, cache, symbol, master.token(symbol), view, clamp,
                    config, tick_paise, log=log,
                )
            except (sac.SmartApiError, va.VendorAdjustmentError, DailyStoreError) as exc:
                record.status = STATUS_MAP_UNBUILDABLE
                record.note = f"map build failed: {type(exc).__name__}: {exc}"
                log(f"    map build FAILED: {exc}")
                return record
            record.map_unprobed_eras = unprobed
            if dropped:
                # A floor that could not be carried is a floor we no longer hold evidence for.
                # Re-open the hunt rather than leave the record claiming a measurement it lost.
                record.floors_hunted = False
        if adjustment_map is None:
            record.status = STATUS_MAP_UNBUILDABLE
            record.note = (
                "map-required, but no era of its ingest span could be probed (no minute-era "
                "trading days); refusing the price-blind factor-table fallback (REVIEW_5A F2)"
            )
            log(f"    {record.note}")
            return record
        record.map_eras = len(adjustment_map.eras)
        record.map_eras_provable = sum(1 for era in adjustment_map.eras if era.provable)
        record.map_events = [
            MapEvent(kind=c.kind, ex_date=c.ex_date.isoformat(),
                     price_source=c.price_source, volume_source=c.volume_source)
            for era in adjustment_map.eras for c in era.choices
        ]
        log(f"    map: {record.map_eras_provable}/{record.map_eras} eras provable")
        if record.floors_hunted and record.floors_resolved and not adjustment_map.floors:
            # Self-healing invariant: the record may only CLAIM a measured floor while the map still
            # CARRIES its evidence. A map rebuilt before floors were carried forward loses it, and a
            # sticky `floors_hunted` would then keep the hunt permanently closed over a claim nothing
            # backs. Re-open it; the re-hunt costs ~11 probes and restores the committed artifact.
            # ``floor_ex_dates`` is deliberately NOT cleared -- it is what tells the re-hunt which
            # events to re-measure regardless of the failure-rate scope gate, because a repaired
            # span no longer LOOKS like it needs a floor. That is the whole trap.
            log(f"    {record.floors_resolved} floor(s) claimed but the map carries none "
                "(rebuilt before the carry-forward) -- re-opening the hunt for "
                f"{record.floor_ex_dates or 'every in-scope event'}")
            record.floors_hunted = False
            record.floors_resolved = 0

    symbol_factors = view.symbol_factors(tick_paise=tick_paise)
    if adjustment_map is not None:
        # Windows already PRESENT in the store are not refetched, so a freshly-built (or rebuilt)
        # map would otherwise never reach the days it was built for. Applying it here re-un-adjusts
        # the stored history in place; the identity guard makes it a no-op for a store that already
        # agrees with the map, so this is safe to run on every pass and costs no network.
        applied = mb.rebuild_symbol_raw_with_map(
            config.minute_store, cached_store, symbol, adjustment_map, tick_paise=tick_paise,
        )
        record.unknown_baseline_days = len(applied.unknown_baseline_days)
        if applied.days_rewritten or applied.unknown_baseline_days:
            log(f"    applied the map to {applied.days_rewritten} already-stored day(s) "
                f"({applied.identity_days} already raw, {len(applied.unprovable_days)} un-provable, "
                f"{len(applied.unknown_baseline_days)} unknown baseline -- left untouched)")

    result = mb.backfill_symbol(
        client, master, config.minute_store, symbol, clamp, config.end,
        symbol_factors=symbol_factors, adjustment_map=adjustment_map,
    )
    summary = result.ledger_summary
    record.windows_planned = result.windows_planned
    record.windows_present = summary.get("present", 0)
    record.windows_empty = summary.get("empty", 0)
    record.windows_error = summary.get("error", 0)
    record.first_stored_date = (
        result.first_stored_date.isoformat() if result.first_stored_date else None
    )
    record.unprovable_days = len(result.unprovable_days)

    tally = gate_symbol(config.minute_store, cache, symbol, since=clamp)
    gate3_over_events(tally, symbol, view.factors)
    record.apply_tally(tally)
    if adjustment_map is not None:
        # Of the days the baseline classifier declined to touch, how many actually COST anything --
        # i.e. also fail gate 1. The rest reconcile as they stand, which is why declining is the
        # conservative action rather than a loss (Q-11 addendum 4's re-classification duty).
        record.unknown_baseline_failing = len(
            set(applied.unknown_baseline_days) & {d for d, _g, _v in tally.gate1_failures}
        )
    _settle(record, tally, view.factors)

    if reroute_owed(record):
        # The Q-12 addendum ruling, widened by the Q-11 addendum-2 floor ruling's own scope
        # ("... DIXON incl. table-path re-routes, MOTHERSON, ... HDFCBANK"): a TABLE-PATH symbol
        # that is quarantined OR sits below the 98% floor-hunt line is rerouted through the map
        # path as a second pass, because the routing rule only guarantees a PRICE oracle for a
        # non-share-count event -- so a bonus/split-only symbol whose vendor used a different
        # factor, or spliced its archive, has nothing that can catch it. Probes buy the oracle;
        # no stored candle is refetched. A floor search NEEDS that oracle, so this runs first.
        tally = reroute_quarantined_to_map(
            client, master, cache, cached_store, record, view, clamp, config, tick_paise, log=log,
        ) or tally

    if floor_hunt_owed(record):
        run_floor_pass(
            client, master, cache, cached_store, record, view, clamp, config, tick_paise, tally,
            log=log,
        )

    log(f"    windows {record.windows_present}p/{record.windows_empty}e/{record.windows_error}x  "
        f"days={record.depth_days} gate1={record.gate1_pass}/{record.gate1_total} "
        f"(+{record.gate1_relieved} relieved -> {record.gate1_rate:.1%}) "
        f"gate2_excl={record.gate2_excluded} "
        f"liquidity_days={record.liquidity_days} "
        f"avg_min/day={record.avg_minutes_per_day} -> {record.status}")
    for failure in record.gate3_failure_rows:
        log(f"    GATE-3 FAIL: {failure}")
    return record


def reroute_owed(record: SymbolRecord) -> bool:
    """Does this TABLE-PATH symbol owe a map-path second pass? PURE.

    The Q-12 addendum ruled the reroute for a QUARANTINED table-path symbol. The Q-11 addendum-2
    floor ruling names table-path symbols that are merely BELOW 98% (DIXON, MOTHERSON, HDFCBANK)
    among the symbols whose floors must be hunted -- and a floor search is arbitrated by the map's
    price oracle, which a table-path symbol does not have. So the same second pass now also fires
    at the floor-hunt line. It stays one-shot: ``reroute_attempted`` is sticky.
    """
    if record.route != ROUTE_TABLE_PATH or record.reroute_attempted:
        return False
    if not record.gate1_total:
        return False
    return (
        record.status == STATUS_QUARANTINED
        or record.gate1_rate < FLOOR_HUNT_GATE1_MAX_RATE
    )


def _settle(
    record: SymbolRecord, tally: GateTally, factors: Sequence[ca.Factor]
) -> None:
    """Set the terminal status from a fresh tally, and profile the failures if it is quarantined.

    The rate is the EFFECTIVE one -- strict gate-1 passes plus auction-relief passes -- because the
    relief ruling counts a relieved day as a pass. The strict numerator stays visible in the record
    and in the report; nothing is folded away.
    """
    if record.gate1_total and record.gate1_rate < QUARANTINE_GATE1_MIN_PASS_RATE:
        record.status = STATUS_QUARANTINED
        relief = f" (strict {record.gate1_strict_rate:.1%} + {record.gate1_relieved} relieved)"
        record.note = (
            f"gate-1 pass rate {record.gate1_rate:.1%}{relief if record.gate1_relieved else ''} is "
            f"below {QUARANTINE_GATE1_MIN_PASS_RATE:.0%}; skipped, listed, run continues"
        )
    else:
        record.status = STATUS_SETTLED
        if record.windows_error:
            record.note = f"{record.windows_error} window(s) in error -- retried on the next run"
    ex_dates = [f.ex_date for f in factors if f.symbol == record.symbol and f.k != _ONE]
    record.apply_profile(gate1_failure_profile(tally, ex_dates))


def reroute_quarantined_to_map(
    client,
    master: InstrumentMaster,
    cache: DailyCache,
    cached_store: CachedDailyStore,
    record: SymbolRecord,
    view: mb.SymbolCorpActions,
    clamp: date,
    config: RunConfig,
    tick_paise: int | None,
    *,
    log: Callable[[str], None] = print,
) -> "GateTally | None":
    """The Q-12-addendum recovery second pass. Mutates ``record`` in place; returns the new tally.

    Probe the symbol's eras, build + persist a map (so the recovery is auditable), apply it to the
    ALREADY-STORED days by the NET factor ``k_map / k_table`` -- the store was already un-adjusted
    once by the factor table at ingest -- and re-run the gates. If the symbol recovers it settles; if
    it does not, it stays quarantined and carries the ruling's failure-pattern analysis.

    It now also fires for a table-path symbol merely BELOW the 98% floor-hunt line
    (:func:`reroute_owed`), because the floor search that follows is arbitrated by the map's price
    oracle and a table-path symbol has none. The returned tally is what that search reads its
    failing days from, so the two passes see the same store.

    ``reroute_attempted`` is set whatever the outcome, so a resumed run never re-probes it.
    """
    record.reroute_attempted = True
    log(f"    MAP RECOVERY: rerouting {record.symbol} through the map path (second pass; "
        f"gate 1 {record.gate1_rate:.1%}, status {record.status})")
    try:
        adjustment_map, unprobed, dropped = build_map_for(
            client, cached_store, cache, record.symbol, master.token(record.symbol),
            view, clamp, config, tick_paise, log=log,
        )
    except (sac.SmartApiError, va.VendorAdjustmentError, DailyStoreError, InstrumentMasterError) as exc:
        record.reroute_note = f"map build failed: {type(exc).__name__}: {exc}"
        log(f"      reroute map build FAILED: {exc} -- stays on the table-path numbers")
        return None
    if dropped:
        record.floors_hunted = False
    if adjustment_map is None:
        record.reroute_note = "no era of the ingest span could be probed; nothing to reroute through"
        log(f"      {record.reroute_note}")
        return None

    record.route = ROUTE_MAP_REQUIRED
    record.map_required_by_recovery = True
    record.route_reasons = [*record.route_reasons, _RECOVERY_REASON]
    record.map_unprobed_eras = unprobed
    record.map_eras = len(adjustment_map.eras)
    record.map_eras_provable = sum(1 for era in adjustment_map.eras if era.provable)
    record.map_events = [
        MapEvent(kind=c.kind, ex_date=c.ex_date.isoformat(),
                 price_source=c.price_source, volume_source=c.volume_source)
        for era in adjustment_map.eras for c in era.choices
    ]
    applied = mb.rebuild_symbol_raw_with_map(
        config.minute_store, cached_store, record.symbol, adjustment_map,
        tick_paise=tick_paise,
        applied_factors=view.symbol_factors(tick_paise=tick_paise),
    )
    tally = gate_symbol(config.minute_store, cache, record.symbol, since=clamp)
    gate3_over_events(tally, record.symbol, view.factors)
    before = f"{record.gate1_effective_pass}/{record.gate1_total} ({record.gate1_rate:.1%})"
    record.snapshot_prior()
    record.apply_tally(tally)
    record.unprovable_days = len(applied.unprovable_days)
    record.unknown_baseline_days = len(applied.unknown_baseline_days)
    _settle(record, tally, view.factors)
    record.reroute_note = (
        f"map {record.map_eras_provable}/{record.map_eras} eras provable; "
        f"{applied.days_rewritten} day(s) rewritten, {applied.identity_days} already raw; "
        f"gate 1 {before} -> {record.gate1_effective_pass}/{record.gate1_total} "
        f"({record.gate1_rate:.1%})"
    )
    log(f"      {record.reroute_note} -> {record.status}")
    for failure in tally.gate3_failures:
        log(f"      GATE-3 FAIL: {failure}")
    return tally


# --- the vendor application-floor hunt (Q-11 addendum 2) ---------------------------------


def floor_hunt_in_scope(record: SymbolRecord) -> bool:
    """Is this symbol inside the ruling's hunt SCOPE at all? PURE.

    "Floors are hunted ONLY where failure is systematic: every quarantined symbol and every settled
    symbol with gate-1 < 98%." A symbol with no gated day at all has no failure to explain. A symbol
    carrying a GATE-3 failure is in scope too (Q-11 addendum 4): the raw-gap-near-zero signature is
    read off exactly those rows, and a symbol can sit above the 98% line while one ex-date of its
    history is in the wrong price domain -- which is a correctness question, not a coverage one.

    Q-14 widens the scope the same way and for the same reason: a symbol below
    :data:`FLOOR_HUNT_GATE1_MAX_RATE` on GATE 1P is in scope whatever its volume rate says. That is
    the whole finding -- SRF sits at 99.5% on gate 1 and stores 216 days at five times the traded
    price -- so a scope that reads only the volume gate would never look at it.
    """
    if not record.gate1_total and not record.gate1p_total:
        return False
    if record.status == STATUS_QUARANTINED or record.gate3_failed:
        return True
    if record.gate1p_total and record.gate1p_rate < FLOOR_HUNT_GATE1_MAX_RATE:
        return True
    return bool(record.gate1_total) and record.gate1_rate < FLOOR_HUNT_GATE1_MAX_RATE


def floor_hunt_owed(record: SymbolRecord) -> bool:
    """Is this symbol in scope, and does it owe a hunt under the CURRENT discipline? PURE.

    A hunt is one-shot per discipline: ``floors_hunted`` stops a resumed run re-spending ~11 probes
    per event on a settled answer, and :data:`FLOOR_DISCIPLINE` re-opens it exactly once when the
    architect widens what may be hunted (Q-11 addendum 4 -- signature-gated hypotheses inside
    un-provable eras, a question the FIX-3 hunt never asked).
    """
    if not floor_hunt_in_scope(record):
        return False
    return not record.floors_hunted or record.floor_discipline != FLOOR_DISCIPLINE


def era_hypotheses_for(
    adjustment_map: "va.AdjustmentMap",
    events: Sequence["va.EventSpec"],
    target_ex_date: date | None = None,
) -> tuple[dict[tuple[date, ...], tuple["va.EventChoice", ...]], list[str]]:
    """A hypothesised chain for every UN-PROVABLE era the map holds. PURE.

    Q-11 addendum 4 clause (ii). Returns ``(hypotheses, refusals)``: the chains
    :func:`acumen.vendor_adjustment.era_hypothesis` could build from previously committed sources
    (plus, for ``target_ex_date`` alone, our own CONTEXT 4.2 factor), and a recorded reason for
    every era it could not. An era holding a SECOND uncommitted event has two unknowns and is
    refused -- the honest outcome, and the one that keeps a floor search a measurement.
    """
    by_ex = {e.ex_date: e for e in events}
    committed = va.canonical_event_factors(adjustment_map)
    hypotheses: dict[tuple[date, ...], tuple["va.EventChoice", ...]] = {}
    refusals: list[str] = []
    for era in adjustment_map.eras:
        if era.provable:
            continue
        choices = va.era_hypothesis(
            adjustment_map, era, by_ex, target_ex_date=target_ex_date, committed=committed
        )
        if choices is None:
            missing = [
                ex.isoformat() for ex in era.ex_dates
                if ex not in committed and ex != target_ex_date
            ] or [
                ex.isoformat() for ex in era.ex_dates
                if ex not in committed and (ex not in by_ex or by_ex[ex].our_price_factor is None)
            ]
            refusals.append(
                f"era {era.label}: no hypothesis -- {missing} carry no committed source, so the era "
                "holds more than one unknown; nothing honest to test a floor against"
            )
            continue
        hypotheses[era.ex_dates] = choices
    return hypotheses, refusals


def floor_candidate_days(
    adjustment_map: "va.AdjustmentMap",
    days: Sequence[date],
    ex_date: date,
    hypotheses: Mapping[tuple[date, ...], tuple["va.EventChoice", ...]] | None = None,
) -> list[date]:
    """The trading days a floor search for ``ex_date`` may probe. PURE.

    Strictly before the ex-date, and only days whose era carries the event with a factor to drop.
    A PROVABLE era supplies that factor from its committed chain. An UN-PROVABLE era supplies it
    from ``hypotheses`` -- the Q-11 addendum-4 ruling's own widening, and the ONLY way its days
    enter the domain: without an entry the era is skipped exactly as decision B123 skipped it.
    """
    chains = hypotheses or {}
    inside: list[date] = []
    for day in days:
        if day >= ex_date or not is_measurable_session(day):
            continue
        era = adjustment_map.era_for_day(day)
        if era is None:
            continue
        choices = era.choices if era.provable else chains.get(era.ex_dates)
        if not choices:
            continue
        if any(c.ex_date == ex_date and c.price_factor != _ONE for c in choices):
            inside.append(day)
    return sorted(inside)


def hunt_symbol_floors(
    client,
    cached_store: CachedDailyStore,
    symbol: str,
    token: str,
    adjustment_map: "va.AdjustmentMap",
    tally: GateTally,
    *,
    force_ex_dates: frozenset[date] = frozenset(),
    events: Sequence["va.EventSpec"] = (),
    signatures: Mapping[date, str] | None = None,
    skip_ex_dates: frozenset[date] = frozenset(),
    probe_cache: dict[date, "va.ProbeDay | None"] | None = None,
    log: Callable[[str], None] = print,
) -> tuple[list["va.EventFloor"], list[str], int]:
    """Binary-search a vendor application floor for each systematically-failing event. I/O (probes).

    Returns ``(floors, findings, probes_spent)``. Events are searched NEWEST-first, so by the time
    an older event is searched every newer event's floor is already known and is honoured inside
    the chain the classifier tests against -- the searches compose instead of confounding.

    One probe is one credentialed ONE_MINUTE call for a single session, memoised across events, so
    a day two searches both want costs one request. ``~11 probes per event`` is the ruling's own
    estimate and :data:`acumen.vendor_adjustment.MAX_FLOOR_PROBES` is the hard cap.

    ``force_ex_dates`` bypasses the :data:`FLOOR_HUNT_MIN_FAILURE_RATE` scope gate for events a
    previous pass already resolved a floor for. That gate reads the STORE's gate-1 failures to
    decide whether an event is worth ~11 probes -- which is right the first time and exactly wrong
    afterwards, because a span repaired BY a floor no longer fails. Without this, a map that lost
    its floors could never get them back: the repair would hide its own justification.

    ``events`` + ``signatures`` are the Q-11 addendum-4 widening, and they work together: an
    un-provable era's days enter the search domain ONLY for an event the signature gate admitted
    (clause i), and only where a hypothesis chain could be built for that era FROM PREVIOUSLY
    COMMITTED SOURCES plus the event being floored (clause ii -- rebuilt per target event, because
    the second-unknown test depends on which event is the target). An event with neither keeps
    exactly its FIX-3 domain -- the provable-era days -- so a non-qualifying event is never hunted
    anywhere it was not hunted before.

    ``skip_ex_dates`` are events already floored by an earlier ROUND of this symbol's hunt, and
    ``probe_cache`` is shared across rounds so a day probed once is never paid for twice.
    """
    failing = {day for day, _gap, _volume in tally.gate1_failures}
    gated = sorted(tally.gate1_days)
    admitted = dict(signatures or {})
    cache: dict[date, "va.ProbeDay | None"] = probe_cache if probe_cache is not None else {}
    spent = 0

    def probe(day: date) -> "va.ProbeDay | None":
        nonlocal spent
        if day not in cache:
            cache[day] = va.probe_one_day(client, cached_store, symbol, token, day)
            spent += 1
        return cache[day]

    floors: list["va.EventFloor"] = []
    findings: list[str] = []
    current = adjustment_map
    for ex_date in sorted(adjustment_map.all_event_ex_dates, reverse=True):
        if ex_date > adjustment_map.fetch_date or ex_date in skip_ex_dates:
            continue
        # A floor a PREVIOUS pass already measured for this event is its own admission: the repair
        # it made is exactly what erases the failure signature that admitted it, so requiring the
        # signature again would make a re-measurement impossible after the first success (the same
        # trap decision B125 caught on the failure-rate gate, one level up).
        signature = admitted.get(ex_date) or (
            "previously measured floor, re-measured (its own repair erased the signature)"
            if ex_date in force_ex_dates else None
        )
        # Clause (i): un-provable-era days are in the domain ONLY for a signature-admitted event.
        # Clause (ii): and only where THIS target leaves the era exactly one unknown.
        era_chains: dict[tuple[date, ...], tuple["va.EventChoice", ...]] = {}
        if signature:
            era_chains, era_refusals = era_hypotheses_for(current, events, ex_date)
            for refusal in era_refusals:
                findings.append(f"{ex_date.isoformat()} -> {refusal}")
        days = floor_candidate_days(current, gated, ex_date, era_chains)
        provable_days = floor_candidate_days(current, gated, ex_date)
        unprovable_days = len(days) - len(provable_days)
        if not days:
            findings.append(
                f"{ex_date.isoformat()} -> not searched: no day of a provable era carries this "
                "event with a factor to drop"
                + ("" if signature else "; and no signature admits an un-provable era's days "
                   "(Q-11 addendum 4 clause i)")
            )
            continue
        failures = sum(1 for day in days if day in failing)
        rate = Decimal(failures) / Decimal(len(days))
        if rate < FLOOR_HUNT_MIN_FAILURE_RATE and ex_date not in force_ex_dates:
            findings.append(
                f"{ex_date.isoformat()} -> not searched: its pre-ex span reconciles "
                f"({failures}/{len(days)} = {rate:.1%} of days fail gate 1, below the "
                f"{FLOOR_HUNT_MIN_FAILURE_RATE:.0%} systematic-failure threshold)"
            )
            continue
        if rate < FLOOR_HUNT_MIN_FAILURE_RATE:
            log(f"      re-measuring {ex_date} despite a reconciling span "
                f"({failures}/{len(days)} = {rate:.1%} fail): a previous pass resolved a floor "
                "here, and the repair is why the span no longer fails")
        log(f"      floor search {ex_date} over {len(days)} day(s) "
            f"({failures} failing, {rate:.1%})"
            + (f"  [+{unprovable_days} un-provable-era day(s): {signature}]"
               if unprovable_days else ""))
        floor = va.search_event_floor_live(
            probe, current, ex_date, days,
            hypotheses=era_chains,
            # The "absent from every chain in our history" outcome is only reachable, and only
            # meaningful, where the search may look inside un-provable eras -- it is the shape of
            # the deadlock the ruling exists to break.
            allow_absent_throughout=bool(signature),
        )
        floors.append(floor)
        current = va.with_floors(current, floors)
        findings.append(
            f"{ex_date.isoformat()} -> "
            + (floor.floor_date.isoformat() if floor.floor_date else "no splice")
            + f" ({'resolved' if floor.resolved else 'UNRESOLVED'}, "
            f"{len(floor.probes)} probe(s)): {floor.note}"
            + (f" [admitted by {signature}]" if signature and unprovable_days else "")
        )
        log(f"        {findings[-1]}")
    return floors, findings, spent


#: How many times a symbol's hunt may compose with its own results before it stops. Each round's
#: PROMOTED eras become the next round's committed sources (Q-11 addendum 4 clause ii), so an older
#: era that held two unknowns can hold one after a newer era resolves -- which is exactly how a
#: cascade of "under-determined" eras unwinds. Bounded and deterministic: a round that resolves no
#: new floor, or promotes no era, is the last.
MAX_FLOOR_HUNT_ROUNDS: int = 3


def _hunt_rounds(
    client,
    master: InstrumentMaster,
    cached_store: CachedDailyStore,
    cache: DailyCache,
    record: SymbolRecord,
    view: mb.SymbolCorpActions,
    clamp: date,
    config: RunConfig,
    tick_paise: int | None,
    adjustment_map: "va.AdjustmentMap",
    tally: GateTally,
    events: Sequence["va.EventSpec"],
    signatures: Mapping[date, str],
    forced: frozenset[date],
    *,
    log: Callable[[str], None] = print,
) -> tuple[list["va.EventFloor"], list[str], int, "va.AdjustmentMap | None"]:
    """Hunt, rebuild with what was found, hunt again on what that unlocked. Returns the union.

    The composition the ruling's clause (ii) implies: a floor measured in a newer era makes that
    era's events committed sources, which can leave an OLDER era with exactly one unknown where it
    had two. Rounds are capped at :data:`MAX_FLOOR_HUNT_ROUNDS` and stop as soon as a round adds no
    floor, so the cost stays a handful of probe days. The probe cache is shared across rounds, so
    a day is fetched at most once for the whole symbol.
    """
    all_floors: list["va.EventFloor"] = []
    all_findings: list[str] = []
    probe_cache: dict[date, "va.ProbeDay | None"] = {}
    current = adjustment_map
    rebuilt_with: frozenset[date] = frozenset()
    latest: "va.AdjustmentMap | None" = None
    spent = 0
    for round_index in range(1, MAX_FLOOR_HUNT_ROUNDS + 1):
        floors, findings, round_spent = hunt_symbol_floors(
            client, cached_store, record.symbol, master.token(record.symbol),
            current, tally, force_ex_dates=forced, events=events, signatures=signatures,
            skip_ex_dates=frozenset(f.ex_date for f in all_floors if f.resolved),
            probe_cache=probe_cache, log=log,
        )
        spent += round_spent
        all_findings.extend(
            f if round_index == 1 else f"[round {round_index}] {f}" for f in findings
        )
        fresh = [f for f in floors if f.resolved and f.floor_date is not None]
        all_floors.extend(floors)
        if not fresh or round_index == MAX_FLOOR_HUNT_ROUNDS:
            break
        # Re-arbitrate with the floors in force. Only a PROMOTION can unlock another round, so a
        # rebuild that promotes nothing ends the composition instead of paying for another pass.
        before = sum(1 for era in current.eras if era.provable)
        rebuilt, _unprobed, _dropped = build_map_for(
            client, cached_store, cache, record.symbol, master.token(record.symbol),
            view, clamp, config, tick_paise,
            floors=[f for f in all_floors if f.resolved], log=log,
        )
        if rebuilt is None:
            break
        after = sum(1 for era in rebuilt.eras if era.provable)
        log(f"      round {round_index}: {after - before} era(s) promoted "
            f"({before} -> {after} provable)")
        current = rebuilt
        rebuilt_with = frozenset(f.ex_date for f in all_floors if f.resolved)
        latest = rebuilt
        if after <= before:
            break
    # Only hand the map back if it was built with EVERY floor now in hand; a later round that found
    # one more floor leaves it stale, and a stale map must be re-measured, not reused.
    if latest is not None and rebuilt_with != frozenset(
        f.ex_date for f in all_floors if f.resolved
    ):
        latest = None
    return all_floors, all_findings, spent, latest


def run_floor_pass(
    client,
    master: InstrumentMaster,
    cache: DailyCache,
    cached_store: CachedDailyStore,
    record: SymbolRecord,
    view: mb.SymbolCorpActions,
    clamp: date,
    config: RunConfig,
    tick_paise: int | None,
    tally: GateTally,
    *,
    log: Callable[[str], None] = print,
) -> None:
    """Hunt floors, commit them to the map, re-apply to the STORE and re-gate. Mutates ``record``.

    No stored candle is refetched: the only network calls are the binary search's own probe days.

    ``floors_hunted`` is set for every outcome the symbol itself determines -- a resolved floor, no
    floor, an unprobeable event -- so a resumed run never re-spends ~11 probes on a settled answer.
    It is deliberately NOT set when the hunt dies on a :class:`~acumen.smartapi_client.SmartApiError`:
    CONTEXT 4.3 states that transient "access denied" bursts are NORMAL and must be retried, never
    read as an answer, and a sticky flag would turn one rate-limit burst into a permanently
    unmeasured floor.
    """
    try:
        adjustment_map = mb.load_adjustment_map_for(record.symbol, data_dir=config.map_data_dir)
    except va.VendorAdjustmentError:
        adjustment_map = None
    if adjustment_map is None:
        # No price oracle to arbitrate "event-in vs event-out" against, so there is nothing to
        # search. The symbol keeps its numbers; the reason is recorded rather than silently skipped.
        record.floors_hunted = True
        record.floor_discipline = FLOOR_DISCIPLINE
        record.floor_note = "no adjustment map on disk to hunt floors against"
        log(f"    floor hunt skipped for {record.symbol}: {record.floor_note}")
        return
    log(f"    FLOOR HUNT: {record.symbol} at gate-1 {record.gate1_rate:.1%} "
        f"(< {FLOOR_HUNT_GATE1_MAX_RATE:.0%} or quarantined)")
    forced = frozenset(date.fromisoformat(d) for d in record.floor_ex_dates)
    # Q-11 addendum 4: which events may be hunted INSIDE an un-provable era, and what chain their
    # two hypotheses are formed from. Both are recorded on the row so the report can show the
    # evidence the hunt acted on -- and an empty signature set means the widening changed nothing
    # for this symbol, which is itself a finding.
    events = va.events_from_factor_table(
        view.factors, view.suppressions, view.pending_rights_ex_dates, symbol=record.symbol,
        unparsed_ex_dates=unparsed_ex_dates(view, record.symbol),
    )
    signatures = signature_gated_events(
        tally,
        [e.ex_date for e in events],
        record.gate3_failure_rows,
    )
    record.floor_signatures = [f"{ex.isoformat()}: {why}" for ex, why in sorted(signatures.items())]
    record.pre_floor_eras_provable = record.map_eras_provable
    for line in record.floor_signatures:
        log(f"      SIGNATURE {line}")
    try:
        floors, findings, spent, already_rebuilt = _hunt_rounds(
            client, master, cached_store, cache, record, view, clamp, config, tick_paise,
            adjustment_map, tally, events, signatures, forced, log=log,
        )
    except sac.SmartApiError as exc:
        # CONTEXT 4.3: a transient "access denied" burst is NORMAL and is retried, never treated as
        # an answer. Leave the hunt OPEN so the next run re-measures instead of committing silence.
        record.floor_note = (
            f"floor hunt interrupted by a transient vendor error, RETRIED on the next run: {exc}"
        )
        log(f"      floor hunt interrupted: {exc} -- the map is left exactly as it was; the hunt "
            "stays OPEN and the next run retries it (CONTEXT 4.3)")
        return
    except (va.VendorAdjustmentError, DailyStoreError, InstrumentMasterError) as exc:
        record.floors_hunted = True  # deterministic: retrying would fail identically forever
        record.floor_discipline = FLOOR_DISCIPLINE
        record.floor_note = f"floor hunt failed: {type(exc).__name__}: {exc}"
        log(f"      floor hunt FAILED: {exc} -- the map is left exactly as it was")
        return

    record.floors_hunted = True
    record.floor_discipline = FLOOR_DISCIPLINE
    record.floor_findings = findings
    record.floor_probes_spent = spent
    resolved = [f for f in floors if f.resolved and f.floor_date is not None]
    # REVIEW_5B finding Q5: the claims come off the MAP, which is where the ruling commits a floor's
    # evidence, so a floor measured by an EARLIER pass and carried forward onto the rebuilt map is
    # still claimed instead of being erased by this pass's own (possibly empty) result.
    record.claim_floors_from_map(adjustment_map)
    if not resolved:
        record.floor_note = (
            f"{spent} probe(s) spent; this pass measured no new vendor application floor, so the "
            "map's chain is unchanged"
            + (
                f" ({record.floors_resolved} floor(s) measured by an earlier pass remain in force "
                f"in the committed map: {', '.join(record.floor_ex_dates)})"
                if record.floors_resolved else
                "; no event carries a vendor application floor inside our history"
            )
        )
        log(f"      {record.floor_note}")
        return

    # ACCEPTANCE (Q-11 addendum 4 clause iii) -- the measured floors go back through the MAP BUILDER
    # rather than being layered onto the committed map by hand, so every era they touch has to
    # satisfy the same oracle as every other era: 2-paise per-day price containment plus gate-1's
    # unwidened band. An era that does becomes provable (a PROMOTION, counted below); one that does
    # not stays un-provable, and its days stay excluded + counted. Probe windows are the only
    # download; no stored candle is refetched.
    promoted_from = sum(1 for era in adjustment_map.eras if era.provable)
    rebuilt = already_rebuilt  # a hunt round may already hold the map built with every floor
    try:
        if rebuilt is None:
            rebuilt, unprobed, dropped = build_map_for(
                client, cached_store, cache, record.symbol, master.token(record.symbol),
                view, clamp, config, tick_paise, floors=floors, log=log,
            )
            record.map_unprobed_eras = unprobed
    except (sac.SmartApiError, va.VendorAdjustmentError, DailyStoreError,
            InstrumentMasterError) as exc:
        log(f"      floor-aware rebuild FAILED ({type(exc).__name__}: {exc}); committing the "
            "floors onto the existing map instead -- the chain drop still applies, no era is "
            "promoted")
    if rebuilt is not None:
        adjustment_map = rebuilt
        record.map_eras = len(adjustment_map.eras)
        record.map_eras_provable = sum(1 for era in adjustment_map.eras if era.provable)
        record.map_events = [
            MapEvent(kind=c.kind, ex_date=c.ex_date.isoformat(),
                     price_source=c.price_source, volume_source=c.volume_source)
            for era in adjustment_map.eras for c in era.choices
        ]
        record.eras_promoted = max(0, record.map_eras_provable - promoted_from)
        log(f"      floor-aware rebuild: {record.map_eras_provable}/{record.map_eras} eras "
            f"provable (was {promoted_from}) -> {record.eras_promoted} era(s) PROMOTED")
    else:
        adjustment_map = va.with_floors(adjustment_map, floors)
        va.persist_map(adjustment_map, data_dir=config.map_data_dir)
    # Re-derive the claims from the map that was actually COMMITTED (finding Q5): a rebuild carries
    # older floors forward, so the row's claim is the union and never just this pass's own result.
    record.claim_floors_from_map(adjustment_map)
    applied = mb.rebuild_symbol_raw_with_map(
        config.minute_store, cached_store, record.symbol, adjustment_map, tick_paise=tick_paise,
    )
    before = f"{record.gate1_effective_pass}/{record.gate1_total} ({record.gate1_rate:.1%})"
    record.pre_floor_gate1_pass = record.gate1_effective_pass
    record.pre_floor_gate1_total = record.gate1_total
    new_tally = gate_symbol(config.minute_store, cache, record.symbol, since=clamp)
    gate3_over_events(new_tally, record.symbol, view.factors)
    record.snapshot_prior()
    record.apply_tally(new_tally)
    record.unknown_baseline_days = len(applied.unknown_baseline_days)
    record.unknown_baseline_failing = len(
        set(applied.unknown_baseline_days) & {d for d, _g, _v in new_tally.gate1_failures}
    )
    record.unprovable_days = len(applied.unprovable_days)
    _settle(record, new_tally, view.factors)
    record.floor_note = (
        f"{len(resolved)} floor(s) resolved over {spent} probe(s); "
        + (f"{record.eras_promoted} era(s) promoted to provable; " if record.eras_promoted else "")
        + f"{applied.days_rewritten} day(s) rewritten, {applied.identity_days} already raw; "
        f"gate 1 {before} -> {record.gate1_effective_pass}/{record.gate1_total} "
        f"({record.gate1_rate:.1%})"
    )
    log(f"      {record.floor_note} -> {record.status}")


# --- the OFFLINE re-gate + Q-14 recovery pass (no network at all) ------------------------


def daily_rows_for(cache: DailyCache, symbol: str) -> dict[date, tuple[int, int, int, int]]:
    """``day -> (raw_high, raw_low, raw_open, raw_volume)`` for one symbol. PURE."""
    return {
        day: (row.high_paise, row.low_paise, row.open_paise, row.volume)
        for day, row in cache.by_symbol.get(symbol.strip().upper(), {}).items()
    }


def regate_universe(
    config: RunConfig,
    symbols: Sequence[str],
    cache: DailyCache,
    actions: Sequence[ca.CorporateAction],
    *,
    recover: bool = False,
    log: Callable[[str], None] = print,
) -> tuple[RunLedger, list["pr.SymbolRecovery"]]:
    """Re-gate every stored symbol from the store, OFFLINE, and optionally run the Q-14 recovery.

    No network call of any kind: the gates read the minute store and the raw daily store, and the
    Q-14 recovery pass measures its per-side floors from the same two stores (decision B143). This
    is the "re-gate" arm of the Q-14 ruling's wiring -- gate 1P joins the battery everywhere gate 1
    runs, and every ledger row is brought onto the current :data:`GATE_DEFINITION` from candles that
    are already on disk.

    With ``recover=True`` the bounded recovery pass runs FIRST for each symbol (so the re-gate that
    follows measures the repaired store), exactly once, and its per-symbol result is returned for
    the report. The ruling licenses ONE such pass; after it the data era is FROZEN.
    """
    from . import price_recovery as pr  # local: keeps the module import graph acyclic

    ledger = RunLedger.load(config.ledger_path)
    cached_store = CachedDailyStore(cache)
    recoveries: list[pr.SymbolRecovery] = []
    for index, symbol in enumerate(symbols, start=1):
        record = ledger.records.get(symbol)
        if record is None or record.status in (STATUS_NO_TOKEN, STATUS_NO_DAILY_HISTORY):
            continue
        if record.floors_hunted and not record.floor_discipline:
            # Finding C10: name the discipline the measurement actually ran under instead of a blank.
            record.floor_discipline = LEGACY_FLOOR_DISCIPLINE
        view = mb.corp_actions_for_symbol(symbol, actions, cached_store)
        clamp = _clamp_of(record, config)
        tally = gate_symbol(config.minute_store, cache, symbol, since=clamp)
        # A gate-1P CLUSTER is at least MIN_CLIFF_DAYS failing days by definition, so a symbol with
        # fewer cannot show one and the pass would only spend a store walk to conclude nothing. The
        # skip is a consequence of the signature, not a second threshold.
        if recover and (tally.gate1p_total - tally.gate1p_pass) >= MIN_CLIFF_DAYS:
            recovery = _recover_one(
                config, cache, cached_store, record, symbol, tally, log=log
            )
            if recovery is not None:
                recoveries.append(recovery)
                if recovery.applied:
                    # Re-gate the REPAIRED store, so the ledger row is the post-recovery truth.
                    tally = gate_symbol(config.minute_store, cache, symbol, since=clamp)
        gate3_over_events(tally, symbol, view.factors)
        record.snapshot_prior()
        record.apply_tally(tally)
        # Findings Q6 and Q5: the un-provable-day count and the floor claims both come off the MAP,
        # which is the authority for them, on EVERY re-gate rather than only on a measuring pass.
        sync_row_from_map(config, symbol, record, tally)
        _settle(record, tally, view.factors)
        ledger.record(record)
        log(f"[{index}/{len(symbols)}] {symbol}: gate1 {record.gate1_effective_pass}/"
            f"{record.gate1_total} ({record.gate1_rate:.1%})  gate1P {record.gate1p_pass}/"
            f"{record.gate1p_total} ({record.gate1p_rate:.1%})  usable {record.usable_pass} "
            f"-> {record.status}")
    ledger.save()
    return ledger, recoveries


def sync_row_from_map(config: RunConfig, symbol: str, record: SymbolRecord, tally: GateTally) -> None:
    """Re-derive from the committed MAP the two row fields the map is the authority for.

    Both are REVIEW_5B findings and both have the same shape -- a number the ledger carried that the
    map could not back, or could back and the ledger did not claim:

    * ``unprovable_days`` (finding Q6) -- measured against the STORED days, not carried over from a
      fetch pass that stored nothing on a resumed run;
    * the floor CLAIMS (finding Q5) -- every floor the map carries is claimed, including one
      measured by an earlier pass and merely carried forward, which is what ASTRAL and NESTLEIND
      lost.

    Doing both here means EVERY re-gate keeps the row and the map in agreement, not only the passes
    that happen to measure something.
    """
    try:
        adjustment_map = mb.load_adjustment_map_for(symbol, data_dir=config.map_data_dir)
    except va.VendorAdjustmentError:
        return
    if adjustment_map is None:
        return
    record.unprovable_days = sum(
        1 for day in tally.closes if adjustment_map.factors_for_day(day) is None
    )
    record.claim_floors_from_map(adjustment_map)


def count_unprovable_days(config: RunConfig, symbol: str, tally: GateTally) -> int:
    """How many STORED days of ``symbol`` sit in an era the map cannot resolve. Read-only.

    REVIEW_5B finding Q6: ``record.unprovable_days`` was overwritten with the FETCH pass's count
    (``universe_backfill.py:1396`` and again at :1549), which is empty on a resumed store -- so the
    ledger carried 300 for VEDL and 0 for every other symbol, including 29 symbols that demonstrably
    hold un-provable eras (HINDZINC has 10 of 11 eras un-provable and recorded 0). The report's
    "Un-provable days (no map era / unknown factor)" line was therefore not the quantity it named.

    This is that quantity, measured where it lives: a stored day whose committed map answers
    ``None`` for its chain. A table-path symbol has no map and no un-provable days by construction.
    """
    try:
        adjustment_map = mb.load_adjustment_map_for(symbol, data_dir=config.map_data_dir)
    except va.VendorAdjustmentError:
        return 0
    if adjustment_map is None:
        return 0
    return sum(1 for day in tally.closes if adjustment_map.factors_for_day(day) is None)


def _clamp_of(record: SymbolRecord, config: RunConfig) -> date:
    try:
        return date.fromisoformat(record.clamp_start or config.start.isoformat())
    except ValueError:
        return config.start


def _recover_one(
    config: RunConfig,
    cache: DailyCache,
    cached_store: CachedDailyStore,
    record: SymbolRecord,
    symbol: str,
    tally: GateTally,
    *,
    log: Callable[[str], None] = print,
) -> "pr.SymbolRecovery | None":
    """One symbol's Q-14 recovery: signature, per-side floors, acceptance, apply. Offline."""
    from . import price_recovery as pr

    try:
        adjustment_map = mb.load_adjustment_map_for(symbol, data_dir=config.map_data_dir)
    except va.VendorAdjustmentError:
        adjustment_map = None
    if adjustment_map is None:
        # A TABLE-PATH symbol has no map, so there is no committed chain to drop an event from and
        # no floor can change one stored price. Its flagged days are disclosed residuals, recorded
        # as such rather than silently skipped.
        record.residual_reason = (
            f"{tally.gate1p_total - tally.gate1p_pass} day(s) fail gate 1P on a symbol with no "
            "committed adjustment map (table path), so no vendor application floor can be measured "
            "or applied; excluded + counted"
        )
        return None
    signatures = gate1p_recovery_events(tally, adjustment_map)
    log(f"  {symbol}: gate 1P {tally.gate1p_pass}/{tally.gate1p_total}; "
        f"{len(signatures)} event(s) admitted by the gate-1P cluster signature")
    recovery = pr.recover_symbol(
        config.minute_store, cached_store, daily_rows_for(cache, symbol), symbol,
        adjustment_map, signatures,
        data_dir=config.map_data_dir,
        tick_paise=adjustment_map.tick_paise,
        folds=tally.folds,   # the gate pass already read the store; do not walk it twice
        log=log,
    )
    record.pre_recovery_gate1p_pass = tally.gate1p_pass
    record.pre_recovery_gate1p_total = tally.gate1p_total
    record.floor_discipline = FLOOR_DISCIPLINE
    record.recovery_admitted = list(recovery.admitted)
    record.recovery_accepted = recovery.accepted_floors
    record.recovery_before_both = recovery.before.both
    record.recovery_after_both = recovery.after.both
    record.recovery_days_rewritten = recovery.days_rewritten
    record.recovery_note = recovery.note
    record.residual_reason = recovery.residual_reason or _residual_reason(record, recovery)
    record.recovery_events = [
        f"{e.ex_date.isoformat()} | price "
        + (e.price_floor.isoformat() if e.price_floor else "-")
        + f" ({'resolved' if e.price_resolved else 'unresolved'}, {e.price_probes}p) | volume "
        + (e.volume_floor.isoformat() if e.volume_floor else "-")
        + f" ({'resolved' if e.volume_resolved else 'unresolved'}, {e.volume_probes}p) | "
        + e.verdict
        for e in recovery.events
    ]
    if recovery.events:
        record.floors_hunted = True
        record.floor_probes_spent += sum(
            e.price_probes + e.volume_probes for e in recovery.events
        )
        record.floor_findings = [
            *record.floor_findings,
            *[
                f"[Q-14] {e.ex_date.isoformat()} -> price "
                + (e.price_floor.isoformat() if e.price_floor else "no splice")
                + f" ({'resolved' if e.price_resolved else 'UNRESOLVED'}, {e.price_probes} "
                "probe(s)) | volume "
                + (e.volume_floor.isoformat() if e.volume_floor else "no splice")
                + f" ({'resolved' if e.volume_resolved else 'UNRESOLVED'}, {e.volume_probes} "
                f"probe(s)): {e.verdict}"
                for e in recovery.events
            ],
        ]
    if recovery.applied:
        # The claims come off the MAP, never off this pass's own findings (finding Q5).
        try:
            record.claim_floors_from_map(
                mb.load_adjustment_map_for(symbol, data_dir=config.map_data_dir)
            )
        except va.VendorAdjustmentError:
            pass
    return recovery


def _residual_reason(record: SymbolRecord, recovery: "pr.SymbolRecovery") -> str:
    """Why this symbol's remaining gate-1P failures are DISCLOSED, in the run's own words. PURE.

    The Q-14 ruling freezes the data era after one pass, so every symbol still carrying flagged days
    owes the register a reason rather than a silence. Each branch below is a measurement the pass
    actually made, not a guess.
    """
    left = recovery.after.days - recovery.after.gate1p
    if not left:
        return ""
    if not recovery.admitted:
        return (
            f"{left} day(s) fail gate 1P and no event showed a gate-1P failure CLUSTER: the "
            "failures are scattered rather than a step, so no vendor application floor explains "
            "them and none was hunted (the ruling's \"never blanket\")"
        )
    if not recovery.accepted_floors:
        return (
            f"{left} day(s) fail gate 1P; {len(recovery.admitted)} event(s) were admitted and "
            "searched, but no per-side floor both resolved and improved the per-day gates, so "
            "nothing was committed and the days stay excluded + counted"
        )
    return (
        f"{left} day(s) still fail gate 1P after {recovery.accepted_floors} accepted per-side "
        "floor(s); the residue is not a step this model can express"
    )


def needs_reprocessing(record: SymbolRecord, config: RunConfig) -> str | None:
    """Why an ALREADY-TERMINAL ledger row must be processed again, or ``None``. No network.

    A resumed run normally skips a terminal symbol. Three things un-skip it, all of them rulings
    landing on a store that is already fetched -- so re-processing costs local reads plus, at most, a
    handful of probe windows, and never a re-download of stored candles:

    1. **the gate definition moved** (:data:`GATE_DEFINITION`) -- the completeness ruling redefined
       CONTEXT 4.5 gate 2, so the row's exclusion counts describe a rule that no longer exists;
    2. **the adjustment map is stale** -- built under the superseded median volume estimator (Q-12),
       or keyed to an older fetch date;
    3. **a quarantine-recovery pass is owed** -- a quarantined table-path symbol that has not yet
       been rerouted through the map (Q-12 addendum).

    All three are self-clearing: once the pass has run, the row is stamped with the current markers
    and this returns ``None``, so the next resume skips it again.
    """
    if record.status in (STATUS_NO_TOKEN, STATUS_NO_DAILY_HISTORY):
        return None  # nothing stored, nothing to re-gate
    if record.gate_definition != GATE_DEFINITION:
        return f"gate definition {record.gate_definition or '(pre-ruling)'} -> {GATE_DEFINITION}"
    if record.rebuild_discipline != REBUILD_DISCIPLINE:
        return (
            f"map-application discipline {record.rebuild_discipline or '(one-way raw test)'} -> "
            f"{REBUILD_DISCIPLINE}"
        )
    if record.route == ROUTE_MAP_REQUIRED:
        try:
            amap = mb.load_adjustment_map_for(record.symbol, data_dir=config.map_data_dir)
        except va.VendorAdjustmentError:
            amap = None
        if amap is None:
            return "map-required but no readable adjustment map is on disk"
        if not va.map_is_current(amap):
            return f"adjustment map built under a superseded estimator ({amap.volume_estimator_id or 'none'})"
        if amap.fetch_date != config.end:
            return f"adjustment map keyed to fetch date {amap.fetch_date}, run end is {config.end}"
        if record.floors_resolved and not amap.floors:
            # The record may only CLAIM a measured vendor application floor while the map still
            # CARRIES its probe evidence (the Q-11 addendum-2 ruling commits the floor TO the map).
            # A map rebuilt before floors were carried forward loses it, and `floors_hunted` is
            # sticky -- so without this the claim would outlive its evidence forever and the next
            # fresh fetch of those days would divide by a chain the vendor never applied.
            return (
                f"record claims {record.floors_resolved} vendor application floor(s) but the "
                "adjustment map carries none -- the hunt must re-open"
            )
    if reroute_owed(record):
        return "map-path recovery pass owed (Q-12 addendum / Q-11 addendum-2 hunt scope)"
    if floor_hunt_owed(record):
        if record.floors_hunted and record.floor_discipline != FLOOR_DISCIPLINE:
            return (
                f"floor-hunt discipline {record.floor_discipline or '(provable eras only, B123)'} "
                f"-> {FLOOR_DISCIPLINE}"
            )
        return "vendor application-floor hunt owed (Q-11 addendum 2)"
    return None


def run_universe(
    client,
    master: InstrumentMaster,
    symbols: Sequence[str],
    actions: Sequence[ca.CorporateAction],
    cache: DailyCache,
    config: RunConfig,
    *,
    log: Callable[[str], None] = print,
) -> RunLedger:
    """Process the whole universe, resumably. Raises :class:`RunHalted` at the quarantine ceiling."""
    ledger = RunLedger.load(config.ledger_path)
    if not ledger.started:
        ledger.started = datetime.now().isoformat(timespec="seconds")
    ledger.halted = ""
    cached_store = CachedDailyStore(cache)
    ceiling = int(HALT_QUARANTINE_FRACTION * Decimal(len(symbols)))
    # Count only the quarantined symbols THIS run is responsible for. The ceiling is a fraction of
    # the symbols being processed, so measuring it against the whole ledger makes any `--symbols`
    # subset unstartable the moment anything anywhere is quarantined -- the operator's own
    # single-symbol diagnostic path, refused for a reason that has nothing to do with the symbol.
    # For a full-universe run this is exactly the previous behaviour (the subset IS the universe).
    in_scope = {s.strip().upper() for s in symbols}
    already = [s for s in ledger.quarantined() if s in in_scope]
    if len(already) > ceiling:
        # Check BEFORE fetching anything: a resumed run must not spend another symbol's worth of
        # requests only to halt again on the same systemic fault.
        ledger.halted = (
            f"{len(already)} symbols were ALREADY quarantined (> "
            f"{HALT_QUARANTINE_FRACTION:.0%} of {len(symbols)}) when this run started"
        )
        ledger.save()
        raise RunHalted(
            f"{ledger.halted}. Quarantined: {', '.join(already)}. Nothing was fetched. The "
            "architect must rule before the run continues -- this is a systemic fault, not "
            "individual accidents."
        )
    # A terminal row is normally skipped -- unless a ruling has moved under it (the completeness
    # gate-2 redefinition, a Q-12-stale map, an owed quarantine-recovery pass). Those symbols are
    # RE-PROCESSED through the identical path: `backfill_symbol` skips every window already present,
    # so the store is re-gated and re-un-adjusted without one candle being re-downloaded.
    reprocess: dict[str, str] = {}
    todo: list[str] = []
    for symbol in symbols:
        record = ledger.records.get(symbol)
        if record is None or not record.is_terminal:
            todo.append(symbol)
            continue
        why = needs_reprocessing(record, config)
        if why is not None:
            reprocess[symbol] = why
            todo.append(symbol)
    terminal = len(symbols) - len(todo)
    if config.max_symbols is not None:
        todo = todo[: config.max_symbols]
    log(f"universe: {len(symbols)} symbols; {terminal} already terminal and current; {len(todo)} to "
        f"process this run (quarantine ceiling {ceiling})")
    if reprocess:
        log(f"  RE-PROCESSING {len(reprocess)} settled/quarantined symbol(s) -- rulings moved under "
            "them; no stored window is refetched:")
        for symbol, why in sorted(reprocess.items()):
            log(f"    {symbol}: {why}")

    started = time.monotonic()
    for index, symbol in enumerate(todo, start=1):
        elapsed = int(time.monotonic() - started)
        log(f"[{index}/{len(todo)}] {symbol}  (elapsed {elapsed}s)"
            + ("  [re-process]" if symbol in reprocess else ""))
        try:
            record = process_symbol(
                client, master, cache, cached_store, actions, symbol, config, log=log,
                previous=ledger.records.get(symbol),
            )
        except KeyboardInterrupt:
            ledger.save()
            log("\ninterrupted -- ledger saved; the same command resumes at window granularity")
            raise
        ledger.record(record)
        # Same scoping as the pre-flight check above (decision B131): the ceiling is a fraction of
        # THIS run's symbols, so a `--symbols` subset is judged on its own outcomes. Counting the
        # whole ledger here made a subset run abort after its first symbol on quarantines that had
        # nothing to do with it -- while a full-universe run is unaffected either way.
        quarantined = [s for s in ledger.quarantined() if s in in_scope]
        if len(quarantined) > ceiling:
            ledger.halted = (
                f"{len(quarantined)} symbols quarantined (> {HALT_QUARANTINE_FRACTION:.0%} of "
                f"{len(symbols)}); run halted for the architect"
            )
            ledger.save()
            raise RunHalted(
                f"{ledger.halted}. Quarantined: {', '.join(quarantined)}. This is a systemic "
                "fault, not 210 individual accidents -- a damaged daily store, a vendor "
                "adjustment change, or a wrong routing decision. Nothing further was fetched."
            )
    ledger.save()
    return ledger


# --- the unknown-series sweep (QUESTIONS.md Q-4 duty) ------------------------------------


def unknown_series_sweep(
    daily_store: DailyStore,
    symbols: Sequence[str],
    from_date: date,
    to_date: date,
    *,
    log: Callable[[str], None] = lambda _message: None,
) -> pd.DataFrame:
    """Q-4's last clause: unknown series encountered on F&O-universe symbols, surfaced.

    "Unknown series encountered on F&O-universe symbols must be surfaced in the
    backfill/coverage report." Chunk 3 built the classifier and the query; chunk 5B is the
    first session that holds the cached universe AND the full daily store, so it is the first
    that can actually run the sweep. Nothing here decides anything -- an unknown series is
    reported and still ignored by :meth:`acumen.daily_store.DailyStore.daily`.

    Swept a YEAR AT A TIME and re-aggregated: one 26-year query over 210 symbols would
    materialise millions of rows at once for a report that only needs counts and bounds.
    """
    parts: list[pd.DataFrame] = []
    for year in range(from_date.year, to_date.year + 1):
        low = max(from_date, date(year, 1, 1))
        high = min(to_date, date(year, 12, 31))
        if high < low:
            continue
        found = daily_store.unknown_series(symbols, low, high)
        if not found.empty:
            log(f"  {year}: {len(found)} unknown series row(s)")
            parts.append(found)
    if not parts:
        return daily_store.unknown_series(symbols, to_date, to_date).iloc[0:0]
    combined = pd.concat(parts, ignore_index=True)
    grouped = (
        combined.groupby(["symbol", "series", "kind"], as_index=False)
        .agg(rows=("rows", "sum"), first_date=("first_date", "min"), last_date=("last_date", "max"))
    )
    return grouped[["symbol", "series", "kind", "rows", "first_date", "last_date"]].sort_values(
        ["symbol", "series"]
    ).reset_index(drop=True)


# --- the report --------------------------------------------------------------------------


def _pct(numerator: int, denominator: int) -> str:
    return "-" if not denominator else f"{100.0 * numerator / denominator:.1f}%"


def _cell(text: str) -> str:
    """Make ``text`` safe inside a markdown table cell. PURE.

    A pipe is the column separator, and the signature strings legitimately contain one -- the
    gate-3 reason quotes ``|raw gap|``. Unescaped, that silently splits the row into extra columns
    and the evidence is misread rather than missing, which is worse.
    """
    return text.replace("|", "\\|").replace("\n", " ").strip()


def build_report(
    ledger: RunLedger,
    symbols: Sequence[str],
    unknown_series: pd.DataFrame,
    *,
    generated_at: datetime,
    config: RunConfig,
) -> str:
    """Render ``docs/backfill_minute_report.md``. PURE (given the ledger and the sweep)."""
    records = [ledger.records[s] for s in symbols if s in ledger.records]
    settled = [r for r in records if r.status == STATUS_SETTLED]
    quarantined = [r for r in records if r.status == STATUS_QUARANTINED]
    unprocessed = [s for s in symbols if s not in ledger.records]
    by_route: dict[str, int] = {}
    for record in records:
        by_route[record.route] = by_route.get(record.route, 0) + 1

    gate1_pass = sum(r.gate1_pass for r in settled)
    gate1_relieved = sum(r.gate1_relieved for r in settled)
    gate1_effective = gate1_pass + gate1_relieved
    gate1_total = sum(r.gate1_total for r in settled)
    gate2_excluded = sum(r.gate2_excluded for r in settled)
    unprovable = sum(r.unprovable_days for r in settled)
    quarantined_days = sum(r.gate1_total for r in quarantined)
    all_days = gate1_total + quarantined_days
    # --- gate 1P + the OVERLAP-AWARE intersections (QUESTIONS.md Q-14; REVIEW_5B finding Q3) -----
    gate1p_pass = sum(r.gate1p_pass for r in settled)
    gate1p_total = sum(r.gate1p_total for r in settled)
    gate1p_no_oracle = sum(r.gate1p_no_oracle for r in records)
    both_gates = sum(r.gate1_and_gate2_pass for r in settled)
    usable = sum(r.usable_pass for r in settled)
    stored_all = sum(r.gate1p_total for r in records)
    #: The figure REVIEW_5B finding Q3 caught: `gate1_effective - gate2_excluded` double-counts
    #: every gate-2 exclusion that lands on a day gate 1 already failed. Kept ONLY so the report can
    #: show the wrong arithmetic beside the right one -- it is never the headline.
    naive_usable = gate1_effective - gate2_excluded

    lines: list[str] = []
    add = lines.append
    add("# Minute backfill report -- chunk 5B (full-universe 1-minute run)")
    add("")
    add(f"Generated {generated_at.isoformat(timespec='seconds')} from "
        f"`{config.ledger_path}` and the stores. Re-runnable at any time; makes no network call.")
    add("")
    add("Scope: CONTEXT 3.1's F&O stock underlyings (CONTEXT 7-E5 -- TODAY's list, with the "
        "survivorship disclosure the report owes), 1-minute candles from "
        f"`{config.start.isoformat()}` (CONTEXT 4.3 depth floor) or the symbol's listing, "
        f"whichever is later, to `{config.end.isoformat()}`.")
    add("")

    add("## 1. Headline")
    add("")
    add("| Measure | Value |")
    add("|---|---|")
    add(f"| Universe symbols | {len(symbols)} |")
    add(f"| Processed | {len(records)} |")
    add(f"| Settled | {len(settled)} |")
    add(f"| Quarantined (gate-1 pass rate < "
        f"{QUARANTINE_GATE1_MIN_PASS_RATE:.0%}) | {len(quarantined)} |")
    for status in sorted({r.status for r in records} - {STATUS_SETTLED, STATUS_QUARANTINED}):
        add(f"| {status} | {sum(1 for r in records if r.status == status)} |")
    add(f"| Not yet processed | {len(unprocessed)} |")
    add(f"| Symbol-days gated (settled symbols) | {gate1_total:,} |")
    add(f"| Gate-1 PASS (strict band) | {gate1_pass:,} ({_pct(gate1_pass, gate1_total)}) |")
    add(f"| Gate-1 AUCTION-RELIEF pass (Q-12 addendum 2) | {gate1_relieved:,} "
        f"({_pct(gate1_relieved, gate1_total)}) |")
    add(f"| Gate-1 EFFECTIVE pass (strict + relief) | {gate1_effective:,} "
        f"({_pct(gate1_effective, gate1_total)}) |")
    add(f"| Gate-1P PASS (per-day price containment, Q-14) | {gate1p_pass:,} "
        f"({_pct(gate1p_pass, gate1p_total)} of {gate1p_total:,} stored days) |")
    add(f"| Gate-1P failures with NO raw daily row (Q-14 closes REVIEW_5B Q4) | {gate1p_no_oracle:,} |")
    add(f"| Gate-2 exclusions | {gate2_excluded:,} |")
    add(f"| Un-provable days (no map era / unknown factor) | {unprovable:,} |")
    add(f"| Vendor application floors resolved (Q-11 addendum 2, Q-14 per-side) | "
        f"{sum(r.floors_resolved for r in records):,} over "
        f"{sum(r.floor_probes_spent for r in records):,} probe(s) -- the Q-14 pass's probes are "
        "STORE reads, not credentialed calls (section 3f) |")
    add(f"| Gate 1 AND gate 2 (overlap-aware) | {both_gates:,} |")
    add(f"| **USABLE symbol-days (gate 1 AND gate 2 AND gate 1P)** | **{usable:,}** |")
    add(f"| **TOTAL coverage** (usable days of every stored symbol-day) | "
        f"**{_pct(usable, stored_all)}** |")
    add(f"| Coverage on gate 1 alone, gated denominator (the pre-Q-14 headline) | "
        f"{_pct(gate1_effective, all_days)} |")
    add(f"| Coverage on gate 1 alone, STRICT band (no relief) | {_pct(gate1_pass, all_days)} |")
    add("")
    add("**Definition of done (plan.md chunk 5B): >= 95% of symbol-days pass gates.** The "
        "architect's Q-14 ruling of 2026-07-28 put GATE 1P in the battery permanently, so \"pass "
        "gates\" now means gate 1 AND gate 2 AND gate 1P, and the honest denominator is every "
        "stored symbol-day (a day with no raw daily row is a gate-1P FAILURE, not an absence -- "
        "that is what closes REVIEW_5B's finding Q4). Measured: "
        f"**{usable:,} of {stored_all:,} = {_pct(usable, stored_all)}**.")
    add("")
    stale = [r for r in records if r.depth_days and r.gate_definition != GATE_DEFINITION]
    if stale:
        # The DIRECTION is stated for the bump that is actually in force, and it is not a
        # constant: this banner was written for the Q-14 gate-1P bump, where a stale row was
        # missing a gate entirely and the coverage really was UNDERSTATED, and it went on
        # claiming that after the Q-21(a) bump, where the opposite is true (REVIEW_9B_FIXES R4).
        # Whoever next moves GATE_DEFINITION re-reads this sentence with it.
        add(f"> **{len(stale)} ledger row(s) have NOT been re-gated under `{GATE_DEFINITION}`** "
            f"({', '.join(sorted(r.symbol for r in stale)[:12])}"
            f"{' ...' if len(stale) > 12 else ''}), so their numbers were produced under a "
            "SUPERSEDED gate definition. The bump now in force COMPLETED gate 2's "
            "impossible-OHLC enumeration with the open test (Q-21(a), CONTEXT v1.6), which can "
            "only turn passing days into failures and moves no gate-1P number at all -- so for "
            "these rows the coverage above is **OVERSTATED**, not understated. Clear it with "
            "the re-gate below (offline, refetches nothing) before reading the verdict as "
            "final:")
        add("")
        add("```")
        add(f"acumen-universe-backfill --regate --universe-snapshot {SEALED_UNIVERSE_SNAPSHOT} \\")
        add("    --report-path <a scratch path, NOT the committed report>")
        add("```")
        add("")
        add("> Both flags are mandatory, and the bare command is a trap this repo has already "
            "measured (REVIEW_9B_FIXES R4). Without `--universe-snapshot` the universe resolves "
            "from the cached F&O endpoint, which holds **208** symbols against the register's "
            "sealed **210** -- EXIDEIND and NUVAMA would keep the stale marker forever and the "
            "regenerated aggregates would be neither the pre- nor the post-completion truth "
            "(CONTEXT 4.6's E5 clarification: a rebuild uses the sealed snapshot). Without "
            "`--report-path` it overwrites `docs/backfill_minute_report.md`, the committed "
            "sealed baseline -- the one flag `docs/recovery/q18_runbook.md` says you must not "
            "omit, *including on `--regate` re-runs*.")
        add("")
    met = stored_all > 0 and Decimal(usable) / Decimal(stored_all) >= Decimal("0.95")
    shortfall = max(0, -(-(stored_all * 95) // 100) - usable)
    add(f"> **DoD VERDICT: {'MET' if met else 'NOT MET'}** -- "
        + (f"{usable:,} of {stored_all:,} stored symbol-days pass gate 1, gate 2 AND gate 1P, at "
           "or above the 95% line."
           if met else
           f"{usable:,} of {stored_all:,} stored symbol-days pass gate 1, gate 2 AND gate 1P; "
           f"{shortfall:,} more passing symbol-days would be needed to reach 95%. Every remaining "
           f"failure is disclosed in section 4 and in the residual register of section 5."))
    add("")
    add("### 1a. Coverage under every defensible reading (REVIEW_5B section 7, recomputed)")
    add("")
    add("The review tabulated six readings of this chunk's coverage and showed that the only one "
        "under which the DoD appeared to miss was the report's OWN arithmetic error (its finding "
        "Q3). All six are recomputed here from the same ledger, with the error fixed, and the "
        "post-Q-14 reading added as G -- which is the one the verdict above uses.")
    add("")
    add("| Reading | Numerator | Denominator | Coverage | DoD |")
    add("|---|---|---|---|---|")
    readings = [
        ("A gate 1 only, gated denominator (the pre-Q-14 headline)", gate1_effective, all_days),
        ("B gate 1 strict, no auction relief", gate1_pass, all_days),
        ("C gate 1 AND gate 2, OVERLAP-AWARE", both_gates, all_days),
        ("D gate 1 AND gate 2, the naive subtraction (WRONG -- finding Q3)", naive_usable, all_days),
        ("E gate 1 only, denominator = every stored day", gate1_effective, stored_all),
        ("F gate 1 AND gate 2 overlap-aware, stored-day denominator", both_gates, stored_all),
        ("**G gate 1 AND gate 2 AND GATE 1P, stored-day denominator**", usable, stored_all),
    ]
    for label, num, den in readings:
        ok = den > 0 and Decimal(num) / Decimal(den) >= Decimal("0.95")
        add(f"| {label} | {num:,} | {den:,} | "
            f"{(100 * Decimal(num) / Decimal(den)):.4f}% | {'MET' if ok else '**NOT MET**'} |")
    add("")
    add(f"Reading **D is arithmetically wrong** and is printed only so the correction is visible: "
        f"it subtracts all {gate2_excluded:,} gate-2 exclusions from the gate-1-passing count, but "
        "a gate-2 missing-minutes exclusion can only fire on a day where gate 1 ALSO failed (the "
        "completeness ruling), so those days were never in that numerator. Reading C counts the "
        f"intersection PER DAY instead, and the difference is {both_gates - naive_usable:,} "
        "symbol-days. Reading G is the DoD reading from the Q-14 ruling onward.")
    if ledger.halted:
        add("")
        add(f"> **RUN HALTED.** {ledger.halted}")
    add("")

    add("## 2. Route classification (QUESTIONS.md Q-11 addendum)")
    add("")
    add("| Route | Symbols | Meaning |")
    add("|---|---|---|")
    add(f"| `{ROUTE_TABLE_PATH}` | {by_route.get(ROUTE_TABLE_PATH, 0)} | bonus/split-only: our "
        "CONTEXT 4.2 factors ARE the vendor's, and gate-1 volume proves the price division |")
    add(f"| `{ROUTE_MAP_REQUIRED}` | {by_route.get(ROUTE_MAP_REQUIRED, 0)} | carries a "
        "non-share-count event (rights / special dividend / demerger) or something unparsed: "
        "ingested only through a measured map with per-day price containment |")
    add("")
    map_required = [r for r in records if r.route == ROUTE_MAP_REQUIRED]
    if map_required:
        add("### Map inventory")
        add("")
        add("| Symbol | Eras probed | Provable | Unprobed | Events (kind @ ex-date: price/volume source) |")
        add("|---|---|---|---|---|")
        for record in sorted(map_required, key=lambda r: r.symbol):
            events = "; ".join(
                f"{e.kind}@{e.ex_date}: {e.price_source}/{e.volume_source}"
                for e in _dedupe_events(record.map_events)
            ) or "-"
            add(f"| {record.symbol} | {record.map_eras} | {record.map_eras_provable} | "
                f"{record.map_unprobed_eras} | {events} |")
        add("")
        sources = _source_counts(map_required)
        vol_sources = _source_counts(map_required, price=False)
        add(f"Per-event factor sources across every committed map, PRICE side -- "
            f"**ours {sources.get(va.SOURCE_OURS, 0)}**, "
            f"**measured {sources.get(va.SOURCE_MEASURED, 0)}**, "
            f"**absent {sources.get(va.SOURCE_ABSENT, 0)}**. `ours` = our exact "
            "CONTEXT 4.2 factor matched the vendor; `measured` = the vendor used a factor we "
            "had to observe; `absent` = the vendor did not apply the event in that era.")
        add("")
        add(f"VOLUME side -- **ours {vol_sources.get(va.SOURCE_OURS, 0)}**, "
            f"**price-factor {vol_sources.get(va.SOURCE_PRICE_FACTOR, 0)}**, "
            f"**measured {vol_sources.get(va.SOURCE_MEASURED, 0)}**, "
            f"**absent {vol_sources.get(va.SOURCE_ABSENT, 0)}**. The Q-12 ruling's candidate order "
            "is `ours(share-count) > chosen-price-factor > measured-minimum > absent`: "
            "`price-factor` means the event's volume was reconciled by the very factor the PRICE "
            "oracle had already pinned to 2 paise per probe day, which is strictly better evidenced "
            "than an observed volume ratio the pre-open auction biases upward. `measured` on this "
            "side is now the MINIMUM over the price-passing probe days, never the median.")
        add("")

    add("## 3. Depth found, per symbol")
    add("")
    add("| Symbol | Route | Clamp | First 1-min day | Days | Windows p/e/x | Gate-1 (strict) | "
        "Relief | Gate-1 (effective) | Floors | Gate-2 excl | Avg min/day | Status |")
    add("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for record in sorted(records, key=lambda r: r.symbol):
        floors = (
            f"{record.floors_resolved}" if record.floors_hunted else "-"
        )
        add(f"| {record.symbol} | {record.route} | {record.clamp_start or '-'} | "
            f"{record.first_stored_date or '-'} | {record.depth_days} | "
            f"{record.windows_present}/{record.windows_empty}/{record.windows_error} | "
            f"{record.gate1_pass}/{record.gate1_total} ({_pct(record.gate1_pass, record.gate1_total)}) | "
            f"{record.gate1_relieved} | "
            f"{record.gate1_effective_pass}/{record.gate1_total} "
            f"({_pct(record.gate1_effective_pass, record.gate1_total)}) | {floors} | "
            f"{record.gate2_excluded} | {record.avg_minutes_per_day} | {record.status} |")
    add("")

    moved = [r for r in records if r.prior_gate1_total >= 0]
    if moved:
        add("### 3a. BEFORE / AFTER the 2026-07-26 rulings (same stored candles, no refetch)")
        add("")
        add("Every row here was gated once under the pre-ruling definitions and then re-gated from "
            "the SAME stored candles, so the two columns are a controlled comparison of the rulings "
            "themselves: Q-12's volume estimator + candidate set, the CONTEXT 4.5 gate-2 "
            "completeness redefinition, and the Q-12-addendum quarantine-recovery reroute. Not one "
            "candle was re-downloaded to produce the "
            "\"after\" column.")
        add("")
        add("| Symbol | Route (after) | Gate-1 before | Gate-1 after | Gate-2 excl before | "
            "Gate-2 excl after | Status before | Status after |")
        add("|---|---|---|---|---|---|---|---|")
        before_pass = before_total = after_pass = after_total = 0
        before_g2 = after_g2 = 0
        for record in sorted(moved, key=lambda r: r.symbol):
            before_pass += max(record.prior_gate1_pass, 0)
            before_total += max(record.prior_gate1_total, 0)
            after_pass += record.gate1_effective_pass
            after_total += record.gate1_total
            before_g2 += max(record.prior_gate2_excluded, 0)
            after_g2 += record.gate2_excluded
            add(f"| {record.symbol} | {record.route} | "
                f"{record.prior_gate1_pass}/{record.prior_gate1_total} "
                f"({_pct(max(record.prior_gate1_pass, 0), max(record.prior_gate1_total, 0))}) | "
                f"{record.gate1_effective_pass}/{record.gate1_total} "
                f"({_pct(record.gate1_effective_pass, record.gate1_total)}) | "
                f"{max(record.prior_gate2_excluded, 0)} | {record.gate2_excluded} | "
                f"{record.prior_status or '-'} | {record.status} |")
        add(f"| **TOTAL ({len(moved)})** | | **{before_pass:,}/{before_total:,} "
            f"({_pct(before_pass, before_total)})** | **{after_pass:,}/{after_total:,} "
            f"({_pct(after_pass, after_total)})** | **{before_g2:,}** | **{after_g2:,}** | | |")
        add("")

    add("### 3b. Traded-minute statistics per symbol (the completeness ruling's liquidity numbers)")
    add("")
    add("The architect's completeness ruling: \"NO liquidity filter is invented (the trader "
        "specified none; per-symbol traded-minutes statistics are reported for his eyes)\". These "
        "are those statistics. **Nothing in the code consumes them** -- there is no minimum traded "
        "minutes, no minimum volume and no symbol drop anywhere. `Liquidity days` counts days "
        "INCLUDED while carrying more than "
        f"{gates.MAX_MISSING_MINUTES} tradeless minutes -- days the pre-ruling gate 2 excluded.")
    add("")
    add("REVIEW_5B finding C15: the first column is STORED BARS per day (every bar the vendor "
        "served for the day, including any stamped outside the session) while the median and "
        "minimum are IN-SESSION traded minutes, so the two differ by ~0.2 min/day. Both are named "
        "for what they are rather than averaged into one number.")
    add("")
    add("| Symbol | Avg stored bars/day | Median traded min/day | Min traded min/day | "
        "Liquidity days | Liquidity days as % of stored |")
    add("|---|---|---|---|---|---|")
    for record in sorted(records, key=lambda r: r.symbol):
        if not record.depth_days:
            continue
        add(f"| {record.symbol} | {record.avg_minutes_per_day} | {record.median_minutes_per_day} | "
            f"{record.min_minutes_per_day} | {record.liquidity_days} | "
            f"{_pct(record.liquidity_days, record.depth_days)} |")
    add("")

    _add_floor_section(add, records)
    _add_relief_section(add, records, gate1_total, sum(r.gate1_total for r in records))
    _add_unprovable_floor_section(add, [r for r in records if r.floors_hunted])
    _add_price_recovery_section(add, records)

    add("## 4. Exclusions by reason")
    add("")
    add("| Reason | Symbol-days | Note |")
    add("|---|---|---|")
    add(f"| gate-1 (volume reconciliation outside [-0.1%, +5.0%], UNRELIEVED) | "
        f"{gate1_total - gate1_effective:,} | CONTEXT 4.5 gate 1; excluded + counted per CONTEXT "
        f"7-E3. {gate1_relieved:,} further above-ceiling failures were relieved as a thin day's "
        "auction share (section 3d) and are NOT excluded |")
    add(f"| **gate-1P (per-day PRICE containment, QUESTIONS.md Q-14)** | "
        f"**{gate1p_total - gate1p_pass:,}** | the stored 1-minute fold does not sit inside the raw "
        "bhavcopy high/low within max(2 paise, 0.1%). Its own reason, never folded into gate 1's "
        f"count. Of these, {gate1p_no_oracle:,} have no raw daily row at all and cannot be "
        "price-proven (the ruling's own words; REVIEW_5B finding Q4) |")
    add(f"| gate-2 (candle integrity) | {gate2_excluded:,} | duplicates, impossible OHLC, negative "
        "values, or missing minutes ON A DAY WHERE GATE 1 ALSO FAILS (the completeness ruling) |")
    add(f"| un-provable (no map era / unknown factor in (D, F]) | {unprovable:,} | the Q-11 "
        "surgical clamp -- stored so the day is visible, failed by gate 1 |")
    add(f"| stored days LEFT UNTOUCHED (baseline unidentified) | "
        f"{sum(r.unknown_baseline_days for r in records):,} | not an exclusion reason and mostly not "
        "damage: the map application declined to correct these days because their stored bars match "
        "neither raw nor the map's chain nor a one-too-many division. Declining is the conservative "
        "action -- a day that already needed no correction is unaffected, and gate 1 decides either "
        "way. The count measures how often the classifier refuses, not how many days are wrong |")
    add(f"| quarantined symbols (whole history) | {quarantined_days:,} | "
        f"{len(quarantined)} symbol(s) below the {QUARANTINE_GATE1_MIN_PASS_RATE:.0%} gate-1 floor |")
    add("")
    unknown_days = sum(r.unknown_baseline_days for r in records)
    unknown_failing = sum(r.unknown_baseline_failing for r in records)
    add("**The unknown-baseline days, re-classified against the ENRICHED hypothesis set (Q-11 "
        "addendum 4).** The set is now `1 / k_era / 1/k_era / 1/k_era^2` plus, wherever a measured "
        "floor makes the day's own chain differ from its era chain, `k_target/k_era` "
        "(pre-floor-divided), `k_era/k_target` (floor-overreached) and `k_target` itself "
        "(as-fetched-floored -- the vendor's own untouched bars on a floored day, which is what "
        f"every day of a newly PROMOTED era looks like). Of the {unknown_days:,} days still "
        f"unidentified, **{unknown_failing:,} also fail gate 1** -- those are the only ones that "
        "cost coverage. The remainder reconcile exactly as they stand, which is why declining to "
        "touch them is the conservative action and not a loss. A day is never corrected by a "
        "guessed factor: the tolerance is derived from the candidate set itself (half the closest "
        "relative gap, capped at 2%), so extending the set can never let two hypotheses claim one "
        "ratio.")
    add("")
    add("### Gate 2 redefined: completeness is volume reconciliation, not a minute count")
    add("")
    add("The architect's ruling of 2026-07-26 (QUESTIONS.md \"CONTEXT 4.5 / 7-E4 AMENDMENT\"): "
        "**the vendor omits minutes in which nothing traded**, so a missing stamp on a day whose "
        "gate-1 volume reconciliation PASSES is a NO-TRADE minute, not missing data -- every traded "
        "rupee is already accounted for. Gate 2's exclusion triggers are now exactly four, and the "
        "run counts each one separately:")
    add("")
    add("| Gate-2 trigger | Symbol-days | Note |")
    add("|---|---|---|")
    add(f"| missing minutes AND gate 1 also failed | {sum(r.gate2_missing for r in settled):,} | "
        "indistinguishable from data loss, so still excluded |")
    add(f"| duplicate stamps | {sum(r.gate2_duplicates for r in settled):,} | unchanged trigger |")
    add(f"| impossible OHLC (high<low, close outside range) | "
        f"{sum(r.gate2_ohlc for r in settled):,} | unchanged trigger (CONTEXT 4.5's own two) |")
    negative_dates = sorted({d for r in records for d in r.gate2_negative_dates})
    add(f"| negative price or volume | {sum(r.gate2_negative for r in settled):,} | trigger ADDED "
        "by the ruling -- and it fired: see below |")
    add(f"| **missing minutes with gate 1 PASSING -> INCLUDED** | "
        f"**{sum(r.liquidity_days for r in settled):,}** | recorded as liquidity statistics "
        "(section 3b), never an exclusion -- this is the redefinition's whole effect |")
    add("")
    if negative_dates:
        add(f"**The NEGATIVE-values trigger the ruling added found a real defect on its first run.** "
            f"Every one of its exclusions lands on {len(negative_dates)} date(s) -- "
            f"`{'`, `'.join(negative_dates)}` -- across essentially EVERY symbol processed, not on "
            "scattered per-symbol accidents. The vendor serves 1-minute bars with negative VOLUME "
            "for those dates (measured: ABB -6,060 and -2 shares, AXISBANK -99,379 and -1, CIPLA "
            "-43,534, all stamped 11:15 onwards). `2024-03-02` is a SATURDAY -- one of NSE's "
            "disaster-recovery special live sessions. Such a date is already excluded from trading "
            "days, bias pairs and trading by QUESTIONS.md Q-5, so nothing was ever going to trade "
            "it; what is new is that the day's candles are now excluded EXPLICITLY and counted, "
            "instead of passing gate 2 on a minute count and relying on the calendar alone. Before "
            "this ruling a negative share count was not a gate-2 trigger at all.")
        add("")
    add("Measured before the ruling, on the same stored candles: ABB traded 318/293/325/338 of 375 "
        "minutes on four consecutive 2019 days -- 37..82 missing -- while gate 1 reconciled every "
        "one of them, and the pre-ruling gate 2 excluded all four. CONTEXT 4.3's PoC measurement of "
        "\"375/375 candles, zero gaps\" was taken on 5 LIQUID symbols in 2026, which is why the "
        "minute-count rule looked safe. CONTEXT 7-E4's own minute-count trigger (\"missing > 5 of "
        "its 120\") is retired by the same ruling; chunk 6's POC window is valid when the DAY passes "
        "gate 1, and a tradeless minute contributes zero volume to the profile.")
    add("")
    if quarantined:
        add("### Quarantined symbols")
        add("")
        add("| Symbol | Route | Gate-1 | Rerouted? | Failure pattern | Why |")
        add("|---|---|---|---|---|---|")
        for record in sorted(quarantined, key=lambda r: r.symbol):
            rerouted = "yes" if record.reroute_attempted else "n/a (map path)"
            add(f"| {record.symbol} | {record.route} | "
                f"{record.gate1_effective_pass}/{record.gate1_total} "
                f"({_pct(record.gate1_effective_pass, record.gate1_total)}) | {rerouted} | "
                f"{record.failure_pattern or '-'} | {record.note} |")
        add("")
        add("**Failure-pattern analysis** (the Q-12-addendum ruling: \"failures clustered before a "
            "CA ex-date (adjustment problem) vs scattered (auction/liquidity shape)\"). Every "
            "table-path symbol here was first REROUTED through the map path as a second pass -- "
            "probes bought it the price oracle the routing rule does not otherwise give a "
            "bonus/split-only symbol -- and stayed quarantined anyway.")
        add("")
        for record in sorted(quarantined, key=lambda r: r.symbol):
            add(f"- **{record.symbol}** -- {record.failure_pattern or 'unclassified'}. "
                f"{record.failure_detail or ''}")
            if record.reroute_note:
                add(f"  - reroute: {record.reroute_note}")
            if record.era_rate_summary():
                add(f"  - per-era gate-1 failure rate: {record.era_rate_summary()}")
        add("")
        add("### Deferred to the architect: the gate-1 +5.0% ceiling on illiquid names")
        add("")
        add("The Q-12-addendum ruling: \"The gate-1 +5.0% ceiling's behavior on illiquid names "
            "(auction share of a tiny day can exceed 5%) is EXPLICITLY DEFERRED to the architect's "
            "review of the completed run's report -- flag it there with per-symbol evidence; do not "
            "tune the band.\" **The band is untouched** "
            f"(`[{gates.VOLUME_GAP_MIN_PCT}%, {gates.VOLUME_GAP_MAX_PCT}%]`, byte-identical). This "
            "is the evidence, per symbol:")
        add("")
        add("| Symbol | Gate-1 failures | Above +5.0% ceiling | Below -0.1% floor | "
            "Median raw daily volume (all days) | Median on the above-ceiling days | Pattern |")
        add("|---|---|---|---|---|---|---|")
        for record in sorted(quarantined, key=lambda r: r.symbol):
            add(f"| {record.symbol} | {record.gate1_total - record.gate1_effective_pass} | "
                f"{record.gate1_above_ceiling} | {record.gate1_below_floor} | "
                f"{record.median_daily_volume:,} | "
                f"{record.median_daily_volume_above_ceiling:,} | "
                f"{record.failure_pattern or '-'} |")
        add("")
        add("Read it this way: an ABOVE-ceiling failure on a day whose raw daily volume is far below "
            "the symbol's own median is the pre-open auction taking more than 5% of a thin day -- a "
            "market property, not a data defect. A BELOW-floor failure, or an above-ceiling failure "
            "on an ordinary-volume day, is an adjustment problem. No band was moved either way.")
        add("")
    other = [r for r in records if r.status not in (STATUS_SETTLED, STATUS_QUARANTINED)]
    if other:
        add("### Symbols excluded before ingest")
        add("")
        add("| Symbol | Status | Why |")
        add("|---|---|---|")
        for record in sorted(other, key=lambda r: r.symbol):
            add(f"| {record.symbol} | {record.status} | {record.note} |")
        add("")

    gate3_checked = sum(r.gate3_checked for r in records)
    gate3_failed = sum(r.gate3_failed for r in records)
    add("## 5. Gate 3 -- adjustment sanity across every share-count ex-date")
    add("")
    add(f"CONTEXT 4.5 gate 3: on every split/bonus ex-date in the stored span, the ADJUSTED "
        f"series must show |day-over-day gap| < 20%. Checked on the stored RAW closes with the "
        f"event's own CONTEXT 4.2 factor applied at the comparison. **{gate3_checked} ex-date(s) "
        f"checked, {gate3_failed} failed.**")
    add("")
    failures = [
        row.split("|")[:8] for record in sorted(records, key=lambda r: r.symbol)
        for row in record.gate3_failure_rows
        if len(row.split("|")) >= 8
    ]
    if failures:
        add("Every failure, with its numbers. `raw gap` is the two stored closes with NO factor "
            "applied; `adjusted gap` is CONTEXT 4.5's own test (the pre-ex close scaled by `k`). "
            "Read together they name the defect: a raw gap near `k - 1` with an adjusted gap near "
            "zero is a healthy event, while a raw gap near ZERO with a large adjusted gap means "
            "the two closes are ALREADY in the same price domain -- i.e. the pre-ex side was never "
            "un-adjusted for the event, which is the exact signature of a vendor APPLICATION FLOOR "
            "(section 3c) sitting above the pre-ex day.")
        add("")
        add("| Symbol | Event(s) | Ex-date | k | Pre-ex day | Ex day | Raw gap | Adjusted gap | "
            "Classification |")
        add("|---|---|---|---|---|---|---|---|---|")
        by_symbol = {r.symbol: r for r in records}
        for symbol, kinds, ex_date, k, pre_day, ex_day, raw_gap, adj_gap in failures:
            add(f"| {symbol} | {kinds} | {ex_date} | {k} | {pre_day} | {ex_day} | {raw_gap}% | "
                f"{adj_gap}% | {_gate3_classification(by_symbol.get(symbol), raw_gap, k, ex_date)} |")
        add("")
    if failures:
        add("### The DISCLOSED RESIDUAL register (QUESTIONS.md Q-11 addendum 4)")
        add("")
        add("The final ruling closes the data era: \"residuals after this pass are disclosed, not "
            "chased.\" This is that register -- every gate-3 failure that survived the "
            "signature-gated hunt, with the numbers, the symbol's coverage cost, and why the hunt "
            "did not resolve it. Chunk 9's report carries this table forward.")
        add("")
        add("| Symbol | Ex-date | k | Raw gap | Adjusted gap | Signature? | Symbol-days failing "
            "gate 1 | Why it is residual |")
        add("|---|---|---|---|---|---|---|---|")
        for symbol, _kinds, ex_date, k, _pre, _ex, raw_gap, adj_gap in failures:
            record = by_symbol.get(symbol)
            # The signature is re-derived from the ROW rather than read only off the ledger, so the
            # register says what the gate would say about this failure whether or not the symbol was
            # in the hunt scope this run.
            row = "|".join((symbol, _kinds, ex_date, k, _pre, _ex, raw_gap, adj_gap))
            derived = gate3_signature_events([row])
            signature = derived.get(date.fromisoformat(ex_date))
            if signature is None:
                signature = (
                    f"no -- raw gap {raw_gap}% is nearer the healthy k-1 than 0, so the "
                    "raw-gap-near-zero signature does not admit it"
                )
            elif record is not None and not any(
                line.startswith(ex_date) for line in record.floor_signatures
            ):
                signature += " (admitted; the hunt still found no fitting floor)"
            failing = (
                record.gate1_total - record.gate1_effective_pass if record is not None else 0
            )
            add(f"| {symbol} | {ex_date} | {k} | {raw_gap}% | {adj_gap}% | {_cell(signature)} | "
                f"{failing:,} | {_cell(_gate3_classification(record, raw_gap, k, ex_date))} |")
        add("")
    add("**Classification key.** `pre-floor span` -- the pre-ex close sits below a vendor "
        "application floor this run MEASURED for that very event, so the two closes were never in "
        "the same price domain and the gate-3 comparison there was meaningless before the fix; the "
        "row above is the POST-fix recheck. `unresolved-floor span` -- the symbol was hunted but no "
        "floor resolved for this event, so the comparison stands and the failure is residual. "
        "`not hunted` -- the symbol reconciles above the hunt line, so the failure is residual and "
        "carries its own numbers. **No failure is waived**: every row is printed with its gap "
        "either way.")
    add("")

    add("## 6. Unknown series on F&O-universe symbols (QUESTIONS.md Q-4)")
    add("")
    if unknown_series is None or unknown_series.empty:
        add("None. Every series carried by a universe symbol classifies as the instrument "
            "(`EQ`/`BE`/`BZ`) or as one of the families the Q-4 ruling names as never-the-"
            "instrument (`N*` debt, `P*` partly-paid, `BL` block).")
    else:
        add("The Q-4 ruling: \"Unknown series encountered on F&O-universe symbols must be "
            "surfaced in the backfill/coverage report.\" They are reported here and are still "
            "never chosen by `DailyStore.daily()`.")
        add("")
        add("| Symbol | Series | Rows | First | Last |")
        add("|---|---|---|---|---|")
        for row in unknown_series.itertuples(index=False):
            add(f"| {row.symbol} | {row.series} | {row.rows} | {row.first_date} | {row.last_date} |")
    add("")

    add("## 7. Disclosures")
    add("")
    add("- **Survivorship (CONTEXT 7-E5).** This run backfills TODAY's F&O list. Symbols that "
        "left the F&O universe during the backtest window are not in it, and symbols that "
        "joined recently carry their whole history. Point-in-time membership is OPEN-5.")
    add("- **Price domain (CONTEXT 7-E11, QUESTIONS.md Q-10/Q-11).** The minute store holds RAW "
        "same-day prices. The vendor feed is corporate-action back-adjusted, so every window is "
        "un-adjusted on ingest -- by our factor table for a bonus/split-only symbol, and by a "
        "MEASURED per-event map for every symbol carrying a non-share-count event.")
    add("- **Gate 1 is the per-day proof (Q-10 ruling).** A day whose un-adjustment cannot be "
        "proven against the raw daily volume is excluded and counted (CONTEXT 7-E3), never "
        "silently traded.")
    add("- **The measured VOLUME factor is a MINIMUM, not a median (QUESTIONS.md Q-12).** The "
        "1-minute sum systematically under-counts the exchange's daily total by the pre-open call "
        "auction, so the volume observable is `true / (1 - auction_share)` -- contaminated in one "
        "direction only. Its FLOOR is therefore the unbiased point, taken across the probe days "
        f"whose PRICE containment passes, minimum {va.MIN_VOLUME_ESTIMATOR_DAYS} such days, else no "
        "measured-volume candidate is offered at all. The estimator is also conservative in the safe "
        "direction: too low a factor pushes gate-1 gaps POSITIVE, into the band's wide side.")
    add("- **Completeness is gate 1, not a minute count (CONTEXT 4.5/7-E4 amendment).** A missing "
        "1-minute stamp on a gate-1-passing day is a no-trade minute; see section 3b for the "
        "per-symbol traded-minute statistics and section 4 for the trigger counts. **No liquidity "
        "filter exists anywhere in the code** -- the trader specified none.")
    add(f"- **NO ruling has widened gate 1's band.** It is still "
        f"`[{gates.VOLUME_GAP_MIN_PCT}%, {gates.VOLUME_GAP_MAX_PCT}%]`, byte-identical, and "
        "`volume_gate` is untouched. The +5.0% ceiling question the Q-12 addendum DEFERRED is now "
        "answered by the AUCTION-RELIEF ruling (section 3d): the ceiling stays, and an "
        "above-ceiling failure with intact extremes, a matching opening print and a shortfall "
        f"<= {gates.AUCTION_RELIEF_MAX_SHORTFALL_PCT}% is separately counted as an "
        "`auction-relief pass`. Below-floor failures are never relieved.")
    add("- **Vendor APPLICATION FLOORS (Q-11 addendum 2).** The vendor's archive is spliced: for "
        "some events its back-adjustment never reached the older bars. Each floor in section 3c "
        "was BINARY-SEARCHED against the daily oracle (does this day fit with the event in the "
        "chain or out of it?), never fitted, and is committed to the symbol's map with every probe "
        "day and verdict. Below a measured floor the event is ABSENT from that day's chain. An "
        "unresolved search changes nothing -- un-provable stays the honest fallback.")
    add("- **Compound and unparsed map nodes (Q-11 addendum 3).** Events sharing an ex-date compose "
        "into ONE node (k = product, share-count flags combined), so a symbol carrying a bonus and "
        "a face-value split on the same day is representable at last; and an UNPARSED subject "
        "enters the map with candidates {measured, absent} instead of forcing the map path and "
        "then contributing no era to probe. Both are why BAJAJFINSV and COLPAL have minute data in "
        "this report for the first time.")
    add("- **The daily store was verified before the run** (`DailyStore.verify()`, the owed "
        "REVIEW_2 F7 check): the oracle is checked before it is trusted.")
    add("")
    return "\n".join(lines) + "\n"


def _gate3_classification(
    record: SymbolRecord | None, raw_gap: str, k: str, ex_date: str = ""
) -> str:
    """Classify one gate-3 failure against this run's floor findings. PURE.

    A gate-3 comparison is only meaningful when the two closes are in the SAME price domain. A raw
    gap near zero on an event whose ``k`` is far from 1 means they are not -- the pre-ex close was
    never un-adjusted for the event, which is what a vendor application floor above the pre-ex day
    leaves behind. The classification says whether a floor was MEASURED for that symbol (so the row
    is the post-fix recheck), searched-but-unresolved, or never hunted.
    """
    try:
        gap = Decimal(raw_gap) / Decimal(100)
        factor = Decimal(k)
    except (ArithmeticError, ValueError):
        return "unclassified"
    same_domain = same_price_domain(gap, factor)  # ONE predicate, shared with the signature gate
    if record is None or not record.floors_hunted:
        return (
            "not hunted -- residual, and the raw gap says the closes are in the SAME price domain"
            if same_domain else "not hunted -- residual"
        )
    if ex_date and ex_date in record.floor_ex_dates:
        # THIS event's own floor was measured, so the row is the post-fix recheck. A floor measured
        # for a DIFFERENT event of the same symbol says nothing about this comparison, and claiming
        # it would be the report flattering itself.
        return "pre-floor span, floor MEASURED for this event -- this row is the post-fix recheck"
    if record.floors_resolved:
        return (
            "hunted; a floor was measured for another event of this symbol but not for this one -- "
            "residual"
        )
    return (
        "unresolved-floor span -- hunted, no floor fitted; residual"
        if same_domain else "hunted, no floor needed; residual"
    )


def _add_floor_section(add: Callable[[str], None], records: Sequence[SymbolRecord]) -> None:
    """Section 3c: the vendor application floors this run measured (Q-11 addendum 2)."""
    hunted = [r for r in records if r.floors_hunted]
    if not hunted:
        return
    add("### 3c. Vendor APPLICATION FLOORS (QUESTIONS.md Q-11 addendum 2)")
    add("")
    add("The architect's ruling: \"the vendor's back-adjustments have per-event APPLICATION "
        "FLOORS -- internal splice dates before which the event was never applied to its archive "
        "... for days < F_e the event is ABSENT from that day's chain\". Each floor below was "
        "BINARY-SEARCHED, not fitted: the search asks the daily oracle, one probed session at a "
        "time, whether that day's fetched bars fit the era's chain WITH the event or WITHOUT it, "
        "and bisects the boundary. Price containment decides -- and the tolerance is "
        f"`max({gates.PRICE_CONTAINMENT_MIN_PAISE} paise, "
        f"{gates.PRICE_CONTAINMENT_REL * 100}% of the raw price)`, NOT a flat 2 paise (REVIEW_5B "
        "finding Q2: every 5B document said \"the same 2-paise containment\" while the code has "
        "carried the relative floor since chunk 5A, decision B92 -- on a Rs 1,000 stock the "
        "effective tolerance is 100 paise, and the IOC cascade's \"0.3 paise past the band\" is "
        "only intelligible against it). A day that answers neither hypothesis is `undecided` and an "
        f"undecided run abandons the search UNRESOLVED rather than guessing. Budget "
        f"{va.MAX_FLOOR_PROBES} probes per event, and the Q-14 pass spends none at all -- it reads "
        "the store (section 3f).")
    add("")
    add("Hunt scope is the ruling's own: every QUARANTINED symbol and every settled symbol below "
        f"gate-1 {FLOOR_HUNT_GATE1_MAX_RATE:.0%}, plus (Q-11 addendum 4) every symbol carrying a "
        "GATE-3 failure, because a symbol can sit above the line while one ex-date of its history "
        "is in the wrong price domain -- a correctness question, not a coverage one. Within a "
        "symbol an event is searched only when its pre-ex provable-era span actually fails "
        f"systematically (>= {FLOOR_HUNT_MIN_FAILURE_RATE:.0%} of its days), or -- inside an "
        "un-provable era -- only when the signature gate admits it (section 3e). There is no floor "
        "to find where nothing fails, and every skip is recorded with its reason.")
    add("")
    add("| Symbol | Gate-1 before the floor pass | Gate-1 after | Floors resolved | Probes | Note |")
    add("|---|---|---|---|---|---|")
    for record in sorted(hunted, key=lambda r: r.symbol):
        before = (
            f"{record.pre_floor_gate1_pass}/{record.pre_floor_gate1_total} "
            f"({_pct(max(record.pre_floor_gate1_pass, 0), max(record.pre_floor_gate1_total, 0))})"
            if record.pre_floor_gate1_total >= 0 else "unchanged"
        )
        add(f"| {record.symbol} | {before} | {record.gate1_effective_pass}/{record.gate1_total} "
            f"({_pct(record.gate1_effective_pass, record.gate1_total)}) | "
            f"{record.floors_resolved} | {record.floor_probes_spent} | "
            f"{record.floor_note or '-'} |")
    add("")
    add("Per-event findings (every event the hunt looked at, including the ones it declined to "
        "search and why):")
    add("")
    for record in sorted(hunted, key=lambda r: r.symbol):
        if not record.floor_findings:
            continue
        add(f"- **{record.symbol}**")
        for finding in record.floor_findings:
            add(f"  - {finding}")
    add("")


def _parse_floor_findings(findings: Sequence[str]) -> list[tuple[str, str, str, str]]:
    """``(ex_date, floor_date, probes, note)`` for each RESOLVED floor in a row's findings. PURE.

    The findings are the hunt's own audit lines (``<ex> -> <floor> (resolved, N probe(s)): why``);
    reading them back is what lets the report print one floors table without re-opening the maps.
    Anything that is not a resolved floor with a date -- a skip, an UNRESOLVED search, a "no splice"
    -- is not a measured floor and is left to the per-event findings list below.
    """
    rows: list[tuple[str, str, str, str]] = []
    for finding in findings:
        head, sep, tail = finding.partition(" -> ")
        if not sep or "(resolved," not in tail:
            continue
        floor_date, _, rest = tail.partition(" (resolved,")
        if floor_date.strip() in ("", "no splice"):
            continue
        probes, _, note = rest.partition("): ")
        rows.append((
            head.strip().lstrip("[").split("] ")[-1],
            floor_date.strip(),
            probes.replace("probe(s)", "").strip(),
            note.split(" [admitted by")[0].strip(),
        ))
    return rows


def _add_unprovable_floor_section(
    add: Callable[[str], None], hunted: Sequence[SymbolRecord]
) -> None:
    """Section 3e: the FIX-4 widening -- floors hunted INSIDE un-provable eras (Q-11 addendum 4)."""
    add("### 3e. Floors in UN-PROVABLE eras -- the FINAL data ruling (QUESTIONS.md Q-11 addendum 4)")
    add("")
    add("The architect's ruling: \"an un-provable era is a conclusion under the floor-less model; "
        "where the floor itself caused unprovability, the hunt was locked out of exactly the eras "
        "needing it.\" Floor hypotheses may now be tested inside un-provable eras under four "
        "guards: (i) hunting is SIGNATURE-GATED, never blanket; (ii) the one-fresh-unknown-per-era "
        "discipline holds -- the floor is the fresh unknown and previously committed sources "
        "combine with it; (iii) acceptance is unchanged -- the era stands only if it becomes "
        "provable under normal per-day price containment and gate-1 re-gating; (iv) full "
        "provenance in the map.")
    add("")
    add("**Clause (i) -- what the signature gate admitted.** An event qualifies only by the "
        "gate-3 raw-gap-near-zero signature (the measured raw gap is strictly nearer 0 than the "
        "healthy `k - 1`) or by an era failure-rate cliff (>= "
        f"{FLOOR_HUNT_ERA_CLIFF_RATE:.0%} of the gated days below the ex-date fail gate 1, over at "
        f"least {MIN_CLIFF_DAYS} days). Everything else keeps exactly its pre-ruling domain.")
    add("")
    measured = [
        (record, parsed)
        for record in sorted(hunted, key=lambda r: r.symbol)
        for parsed in (_parse_floor_findings(record.floor_findings),)
        if parsed
    ]
    if measured:
        add("**Every floor this run MEASURED** -- event, the splice date the bisection returned, and"
            " what it cost. A floor AT the ex-date means the vendor never applied that event to one "
            "day of our history; a floor inside the span means it applied it from that date on.")
        add("")
        add("| Symbol | Event ex-date | Measured floor | Probes | What the search found |")
        add("|---|---|---|---|---|")
        for record, rows in measured:
            for ex_date, floor_date, probes, note in rows:
                add(f"| {record.symbol} | {ex_date} | {floor_date} | {probes} | {note} |")
        add("")
    admitted = [r for r in hunted if r.floor_signatures]
    if admitted:
        add("**Every event the gate ADMITTED into an un-provable era**, with the measurement that "
            "admitted it. An event absent from this table was never hunted there, however badly "
            "its span fails -- that is the ruling's \"never blanket\".")
        add("")
    if not admitted:
        add("No event in the hunt scope showed either signature, so the widening changed nothing "
            "this run -- which is itself the gate working: no era was entered on a hunch.")
        add("")
        return
    add("| Symbol | Event | Admitting signature |")
    add("|---|---|---|")
    for record in sorted(admitted, key=lambda r: r.symbol):
        for line in record.floor_signatures:
            ex_date, _, why = line.partition(": ")
            add(f"| {record.symbol} | {ex_date} | {_cell(why)} |")
    add("")
    promoted = [r for r in hunted if r.eras_promoted or r.pre_floor_eras_provable >= 0]
    if promoted:
        add("**Clause (iii) -- acceptance, era by era.** A measured floor is handed back to the MAP "
            "BUILDER, not layered onto the committed map: every era it touches must satisfy the same "
            "2-paise per-day price containment and the same unwidened gate-1 band as any other era. "
            "An era that does is PROMOTED to provable; one that does not stays un-provable and its "
            "days stay excluded + counted.")
        add("")
        add("| Symbol | Eras provable before | after | Promoted | Gate-1 before | Gate-1 after |")
        add("|---|---|---|---|---|---|")
        for record in sorted(promoted, key=lambda r: r.symbol):
            before_rate = (
                f"{record.pre_floor_gate1_pass}/{record.pre_floor_gate1_total} "
                f"({_pct(max(record.pre_floor_gate1_pass, 0), max(record.pre_floor_gate1_total, 0))})"
                if record.pre_floor_gate1_total >= 0 else "unchanged"
            )
            add(f"| {record.symbol} | "
                f"{record.pre_floor_eras_provable if record.pre_floor_eras_provable >= 0 else '-'} | "
                f"{record.map_eras_provable} | {record.eras_promoted} | {before_rate} | "
                f"{record.gate1_effective_pass}/{record.gate1_total} "
                f"({_pct(record.gate1_effective_pass, record.gate1_total)}) |")
        add("")


def residual_verdict(record: SymbolRecord) -> str:
    """Why THIS symbol's remaining gate-1P failures are disclosed rather than repaired. PURE.

    Derived from the row alone, so the register says the same thing whenever it is regenerated.
    The branches are ordered by how much the run actually learned, and each states a fact the row
    carries rather than a guess:

    1. a floor was ACCEPTED -- the residue is what the step model could not reach;
    2. events were ADMITTED and searched but nothing both resolved and paid for itself;
    3. the failing days sit inside UN-PROVABLE eras -- the ruling's own fallback, and the reason
       no signature could admit anything: an un-provable era commits no chain, so there is no
       factor for a floor to drop and no floor could change one stored price;
    4. the symbol has no committed map at all (table path), same conclusion for a different reason;
    5. otherwise the failures are genuinely not a step, and "never blanket" means they are not hunted.
    """
    failing = record.gate1p_total - record.gate1p_pass
    if record.recovery_accepted:
        return (
            f"{failing:,} day(s) still fail after {record.recovery_accepted} accepted per-side "
            "floor(s) -- the residue is not a step the floor model can express"
        )
    if record.recovery_admitted:
        return (
            f"{len(record.recovery_admitted)} event(s) admitted and searched; no per-side floor "
            "both resolved and improved the per-day gates, so nothing was committed"
        )
    if record.unprovable_days >= failing - record.gate1p_no_oracle and failing > record.gate1p_no_oracle:
        return (
            f"the failing days sit inside UN-PROVABLE eras ({record.unprovable_days:,} un-provable "
            f"stored days, {record.map_eras_provable}/{record.map_eras} eras provable). An "
            "un-provable era commits no chain, so there is no factor for a floor to drop and no "
            "floor could change one stored price -- the Q-11 addendum-2 ruling's own fallback: "
            "un-provable remains the honest answer"
        )
    if record.route == ROUTE_TABLE_PATH:
        return (
            "no committed adjustment map (table path), so no vendor application floor can be "
            "measured or applied; excluded + counted"
        )
    return (
        "no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so "
        "no vendor application floor explains them and none was hunted (\"never blanket\")"
    )


def _add_price_recovery_section(
    add: Callable[[str], None], records: Sequence[SymbolRecord]
) -> None:
    """Section 3f: the Q-14 bounded PRICE-RECOVERY pass, and the register it froze."""
    #: Only the symbols the pass actually ENTERED -- a symbol whose gate-1P failures number fewer
    #: than a cluster's minimum length cannot show the signature at all, so listing all 200 of them
    #: here would bury the ones that matter. They are counted in the residual register below.
    touched = [r for r in records if r.recovery_before_both >= 0]
    add("### 3f. GATE 1P and the bounded PRICE-RECOVERY pass (QUESTIONS.md Q-14)")
    add("")
    add("The architect's ruling of 2026-07-28: \"gate 1 proves volume; nothing proved price per "
        "day ... Therefore GATE 1P joins CONTEXT 4.5's battery permanently: for every stored "
        "symbol-day, the un-adjusted 1-minute fold interval [low, high] must sit INSIDE the raw "
        "bhavcopy interval [daily_low, daily_high] with tolerance max(2 paise, 0.1% of the raw "
        "price) per side; a day with no raw daily row cannot be price-proven and FAILS. A day "
        "failing 1P is EXCLUDED and COUNTED under its own reason.\"")
    add("")
    add("The mechanism the ruling names is a PER-SIDE vendor splice -- price and volume applied "
        "back to different dates for the same event -- so the floor model gained `floor_price` and "
        "`floor_volume` per event, each measured by the SAME bisection under the SAME guards. The "
        "hunt is signature-gated by gate-1P failure CLUSTERS: a contiguous block of price failures "
        f"at the old end of an era's span, at least {MIN_CLIFF_DAYS} days long, failing at "
        f">= {FLOOR_HUNT_ERA_CLIFF_RATE:.0%} with a clean remainder above it -- the shape a step "
        "leaves, and nothing else.")
    add("")
    add("**No candle was fetched for this pass.** The observable a probe buys is `fetched / raw`, "
        "and the store holds it exactly: the ingest wrote `stored = fetched / k_applied`, so "
        "`event-in` is \"the stored day is contained in raw\" (gate 1P itself) and `event-out` is "
        "\"the stored day multiplied BACK by the event's own factor is contained\". Identical "
        "oracle, identical tolerance, zero credentialed calls, reproducible offline by anyone "
        "holding the two stores (decision B143).")
    add("")
    if not touched and all(r.gate1p_pass == r.gate1p_total for r in records):
        add("No stored symbol-day fails gate 1P; the pass had nothing to recover.")
        add("")
        return
    if not touched:
        add("No symbol carried enough price-unproven days for a cluster signature to be possible, "
            "so the pass entered none. The register below is the whole gate-1P residue.")
        add("")
    add("| Symbol | Gate-1P before | Gate-1P after | Events admitted | Floors accepted | "
        "Days rewritten | Outcome |")
    add("|---|---|---|---|---|---|---|")
    for record in sorted(touched, key=lambda r: (-(r.gate1p_total - r.gate1p_pass), r.symbol)):
        before = (
            f"{record.pre_recovery_gate1p_pass}/{record.pre_recovery_gate1p_total} "
            f"({_pct(max(record.pre_recovery_gate1p_pass, 0), max(record.pre_recovery_gate1p_total, 0))})"
            if record.pre_recovery_gate1p_total >= 0 else "unchanged"
        )
        add(f"| {record.symbol} | {before} | {record.gate1p_pass}/{record.gate1p_total} "
            f"({_pct(record.gate1p_pass, record.gate1p_total)}) | "
            f"{len(record.recovery_admitted)} | {record.recovery_accepted} | "
            f"{record.recovery_days_rewritten} | {_cell(record.recovery_note or '-')} |")
    add("")
    measured = [r for r in records if r.recovery_events]
    if measured:
        add("**Every per-side floor the pass MEASURED**, accepted or not. A floor is accepted only "
            "when the dry run says the store would end with MORE days passing BOTH per-day gates "
            "and no fewer passing gate 1 -- the ruling's own acceptance. A rejected measurement is "
            "printed here and discarded; it is never written to the store.")
        add("")
        add("| Symbol | Event ex-date | PRICE floor (probes) | VOLUME floor (probes) | Verdict |")
        add("|---|---|---|---|---|")
        for record in sorted(measured, key=lambda r: r.symbol):
            for line in record.recovery_events:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 4:
                    continue
                ex_date, price, volume, verdict = parts[0], parts[1], parts[2], parts[3]
                add(f"| {record.symbol} | {ex_date} | {_cell(price)} | {_cell(volume)} | "
                    f"{_cell(verdict)} |")
        add("")
    residual = [r for r in records if r.gate1p_pass < r.gate1p_total]
    material = [r for r in residual if (r.gate1p_total - r.gate1p_pass) >= MIN_CLIFF_DAYS]
    scattered = [r for r in residual if r not in material]
    add("**The DISCLOSED-RESIDUAL register for gate 1P.** The ruling freezes the data era after "
        "this one pass: \"anything still flagged is a disclosed residual, not chased.\" Every "
        "symbol below still carries price-unproven days; they are EXCLUDED and COUNTED under "
        "gate 1P's own reason, and this table is what chunk 9 carries forward.")
    add("")
    add("| Symbol | Days failing gate 1P | above / below / no-oracle | Worst excess (paise) | "
        "Status | Why it is residual |")
    add("|---|---|---|---|---|---|")
    for record in sorted(material, key=lambda r: -(r.gate1p_total - r.gate1p_pass)):
        add(f"| {record.symbol} | {record.gate1p_total - record.gate1p_pass:,} | "
            f"{record.gate1p_above} / {record.gate1p_below} / {record.gate1p_no_oracle} | "
            f"{record.gate1p_worst_excess:,} | {record.status} | "
            f"{_cell(residual_verdict(record))} |")
    if scattered:
        days = sum(r.gate1p_total - r.gate1p_pass for r in scattered)
        oracle = sum(r.gate1p_no_oracle for r in scattered)
        add(f"| **{len(scattered)} further symbol(s)**, aggregated | **{days:,}** | | | settled / "
            f"quarantined | fewer than {MIN_CLIFF_DAYS} price-unproven days each -- below a "
            "cluster's minimum length, so no vendor application floor could be measured for them "
            f"and none was hunted. {oracle:,} of these days have no raw daily row at all |")
    add("")
    add(f"Read the register this way: an **above** failure means the stored 1-minute high sits "
        "ABOVE the exchange's own daily high, which is impossible on raw prices and means the day "
        "is stored too HIGH; a **below** failure means the fold low sits below the daily low, i.e. "
        "the day is stored too LOW; **no-oracle** means the day has no bhavcopy row at all and "
        "cannot be price-proven either way (the ruling's own words). The worst excess is how far "
        "past the tolerated bound the worse side sits, in paise -- a few paise is microstructure, a "
        "few thousand is a wrong price scale.")
    add("")


def _add_relief_section(
    add: Callable[[str], None],
    records: Sequence[SymbolRecord],
    gated_days: int,
    all_gated_days: int,
) -> None:
    """Section 3d: the auction relief the deferred-ceiling ruling granted (Q-12 addendum 2)."""
    relieved = [r for r in records if r.gate1_relieved]
    total_relieved = sum(r.gate1_relieved for r in records)
    add("### 3d. AUCTION RELIEF -- the deferred +5.0% ceiling, answered (QUESTIONS.md Q-12 addendum 2)")
    add("")
    add("The architect's ruling: **\"the ceiling stays\"**. `VOLUME_GAP_MIN_PCT` and "
        f"`VOLUME_GAP_MAX_PCT` are byte-identical (`[{gates.VOLUME_GAP_MIN_PCT}%, "
        f"{gates.VOLUME_GAP_MAX_PCT}%]`) and `volume_gate` is untouched. A gate-1 failure ABOVE "
        "the ceiling is separately examined and relieved **IFF ALL FOUR** hold: (a) the failure is "
        "above the ceiling, never below the floor; (b) the stored 1-min HIGH equals the raw daily "
        "HIGH and the 1-min LOW the raw daily LOW, EXACTLY; (c) the first stamp's open equals the "
        f"raw daily open, exactly; (d) the shortfall is <= "
        f"{gates.AUCTION_RELIEF_MAX_SHORTFALL_PCT}%. Data LOSS clips extremes; a day with intact "
        "extremes, a matching opening print and only volume short is a thin day whose pre-open "
        "auction exceeds 5% -- a market property.")
    add("")
    settled_relieved = sum(
        r.gate1_relieved for r in records if r.status == STATUS_SETTLED
    )
    add(f"**{total_relieved:,} symbol-day(s) relieved** across {len(relieved)} symbol(s), out of "
        f"{all_gated_days:,} gated days on ALL processed symbols. Of those, "
        f"**{settled_relieved:,}** land on SETTLED symbols ({gated_days:,} gated days) and are the "
        f"only ones the coverage headline counts; the remaining "
        f"{total_relieved - settled_relieved:,} sit on QUARANTINED symbols, whose whole history is "
        "excluded anyway. REVIEW_5B finding C9: the two populations are now named apart instead of "
        "an all-symbol numerator being printed over a settled-only denominator. Relieved days are "
        "counted SEPARATELY everywhere in this report -- the strict gate-1 numerator is never "
        "overwritten.")
    add("")
    if relieved:
        add("| Symbol | Gate-1 strict | Auction-relief pass | Effective | Median shortfall | "
            "Relieved days also carrying tradeless minutes | Status |")
        add("|---|---|---|---|---|---|---|")
        for record in sorted(relieved, key=lambda r: -r.gate1_relieved):
            add(f"| {record.symbol} | {record.gate1_pass}/{record.gate1_total} "
                f"({_pct(record.gate1_pass, record.gate1_total)}) | {record.gate1_relieved} | "
                f"{record.gate1_effective_pass}/{record.gate1_total} "
                f"({_pct(record.gate1_effective_pass, record.gate1_total)}) | "
                f"{record.gate1_relieved_median_gap or '-'} | "
                f"{record.gate1_relieved_with_missing} | {record.status} |")
        add("")
    add("**Decision B122, recorded not assumed.** The completeness ruling excludes a day for "
        "missing minutes only \"ON A DAY WHERE GATE-1 ALSO FAILS\". A relieved day's gate-1 "
        "verdict is *pass (by relief)*, so it is handed to gate 2 as reconciled. The relief's own "
        "conditions (b) and (c) are the direct evidence that nothing was lost -- exactly the "
        "hypothesis the missing-minutes trigger exists to catch -- and the thin days relief "
        "targets are precisely the days that carry tradeless minutes, so the other reading would "
        "cancel the relief it had just granted. The last column above measures how often it "
        f"mattered: {sum(r.gate1_relieved_with_missing for r in records):,} of {total_relieved:,} "
        "relieved days also carried more than "
        f"{gates.MAX_MISSING_MINUTES} tradeless minutes.")
    add("")


def _dedupe_events(events: Sequence[MapEvent]) -> list[MapEvent]:
    """One row per (kind, ex-date, sources) -- an event repeats across the eras it appears in."""
    seen: dict[tuple[str, str, str, str], MapEvent] = {}
    for event in events:
        seen.setdefault((event.kind, event.ex_date, event.price_source, event.volume_source), event)
    return [seen[key] for key in sorted(seen)]


def _source_counts(records: Sequence[SymbolRecord], *, price: bool = True) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        for event in _dedupe_events(record.map_events):
            source = event.price_source if price else event.volume_source
            counts[source] = counts.get(source, 0) + 1
    return counts


def write_report(
    ledger: RunLedger,
    symbols: Sequence[str],
    unknown_series: pd.DataFrame,
    config: RunConfig,
    *,
    generated_at: datetime | None = None,
) -> Path:
    """Render and atomically write the report."""
    text = build_report(
        ledger, symbols, unknown_series,
        generated_at=generated_at or datetime.now(), config=config,
    )
    config.report_path.parent.mkdir(parents=True, exist_ok=True)
    return atomic_write_text(config.report_path, text)


# --- the operator CLI --------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="acumen-universe-backfill",
        description=(
            "Backfill 1-minute candles for the whole F&O universe (chunk 5B). Resumable: the "
            "same command picks up where an interrupt left off, at window granularity."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--from", dest="start", default=mb.MINUTE_DATA_FLOOR.isoformat(),
                        help="earliest date to request (clamped per symbol to its listing)")
    parser.add_argument("--to", dest="end", default=None, help="end date (default: today)")
    parser.add_argument("--store", default=None, help="minute store root")
    parser.add_argument("--daily-store", default=None, help="daily store root")
    parser.add_argument("--data-dir", default=None, help="data dir (maps + run ledger)")
    parser.add_argument("--cache-dir", default=None, help="instrument-master / NSE cache dir")
    parser.add_argument("--universe-snapshot", default=None,
                        help="use a frozen universe JSON instead of the endpoint")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--allow-network", action="store_true", help="REQUIRED to fetch anything")
    parser.add_argument("--report-only", action="store_true",
                        help="regenerate the report from the ledger and the stores; no network")
    parser.add_argument("--regate", action="store_true",
                        help="re-run the CONTEXT 4.5 gates (1, 1P, 2, 3) over the STORED candles "
                             "and rewrite the ledger; no network, nothing refetched")
    parser.add_argument("--recover-prices", action="store_true",
                        help="the Q-14 bounded recovery pass: measure per-side vendor application "
                             "floors from the store, accept what passes BOTH per-day gates, then "
                             "re-gate. Implies --regate; no network. Licensed to run ONCE")
    parser.add_argument("--verify-only", action="store_true",
                        help="run the daily-store verification and stop")
    parser.add_argument("--skip-verify", action="store_true",
                        help="skip the daily-store verification (only after it has passed once)")
    parser.add_argument("--max-symbols", type=int, default=None,
                        help="process at most N pending symbols this run (staged runs / debug)")
    parser.add_argument("--symbols", default=None,
                        help="comma-separated subset of the universe to process")
    return parser.parse_args(argv)


def _default_root(subdir: str) -> Path:
    from .config import load_config

    return load_config(include_env=False).path("data_root") / subdir


def _data_dir() -> Path:
    from .config import load_config

    return load_config(include_env=False).path("data_root")


def run(args: argparse.Namespace) -> int:
    end = date.fromisoformat(args.end) if args.end else datetime.now().date()
    start = date.fromisoformat(args.start)
    data_dir = Path(args.data_dir) if args.data_dir else _data_dir()
    minute_root = Path(args.store) if args.store else _default_root("minute_store")
    daily_root = Path(args.daily_store) if args.daily_store else _default_root("daily_store")
    daily_store = DailyStore.at(daily_root)
    config = RunConfig(
        minute_store=MinuteStore.at(minute_root),
        daily_store=daily_store,
        ledger_path=data_dir / "universe_backfill" / "ledger.json",
        map_data_dir=data_dir,
        end=end,
        start=start,
        max_symbols=args.max_symbols,
        skip_verify=args.skip_verify,
        report_path=Path(args.report_path),
    )

    print(f"range        : {start} .. {end}")
    print(f"minute store : {minute_root}")
    print(f"daily store  : {daily_root}")
    print(f"run ledger   : {config.ledger_path}")
    print(f"report       : {config.report_path}")

    if args.verify_only:
        verify_the_oracle(daily_store)
        return 0

    snapshot = Path(args.universe_snapshot) if args.universe_snapshot else None
    symbols = list(resolve_universe(
        cache_dir=args.cache_dir,
        allow_network=args.allow_network and not args.report_only,
        snapshot=snapshot,
    ))
    if args.symbols:
        wanted = {s.strip().upper() for s in args.symbols.split(",") if s.strip()}
        symbols = [s for s in symbols if s in wanted]
    print(f"universe     : {len(symbols)} symbols")

    if args.report_only:
        ledger = RunLedger.load(config.ledger_path)
        print("sweeping the daily store for unknown series on universe symbols (Q-4) ...")
        unknown = unknown_series_sweep(daily_store, symbols, date(2000, 1, 1), end, log=print)
        path = write_report(ledger, symbols, unknown, config)
        print(f"report written -> {path}")
        return 0

    if args.regate or args.recover_prices:
        # The Q-14 wiring's OFFLINE arm: gate 1P joins the battery everywhere gate 1 runs, and the
        # bounded recovery pass measures its per-side floors from the same two stores. No network
        # call of any kind is made here -- not a candle, not a corporate action, not a login.
        print("reading the raw daily store for the whole universe (one pass) ...")
        cache = build_daily_cache(
            daily_store, symbols, min(start, mb.MINUTE_DATA_FLOOR) - timedelta(days=400), end
        )
        print(f"  cached {sum(len(v) for v in cache.by_symbol.values()):,} symbol-days "
              f"for {len(cache.by_symbol)} symbols")
        print("reading the CACHED NSE corporate-action history (offline) ...")
        actions = mb.fetch_corp_action_history(
            date(start.year, 1, 1), end, allow_network=False, cache_dir=args.cache_dir
        )
        print(f"  {len(actions):,} corporate-action rows {start.year}..{end.year}")
        ledger, recoveries = regate_universe(
            config, symbols, cache, actions, recover=args.recover_prices,
        )
        if recoveries:
            accepted = sum(r.accepted_floors for r in recoveries)
            print(f"\nQ-14 recovery: {len(recoveries)} symbol(s) hunted, {accepted} per-side "
                  f"floor(s) accepted, "
                  f"{sum(r.days_rewritten for r in recoveries):,} stored day(s) rewritten")
        print("\nsweeping the daily store for unknown series on universe symbols (Q-4) ...")
        unknown = unknown_series_sweep(daily_store, symbols, date(2000, 1, 1), end, log=print)
        path = write_report(ledger, symbols, unknown, config)
        print(f"report written -> {path}")
        return 0

    if not config.skip_verify:
        verify_the_oracle(daily_store)

    if not args.allow_network:
        print("STOPPING: --allow-network is required. This run makes live SmartAPI and NSE "
              "pulls (CONTEXT 4.3); nothing was fetched. Use --report-only for the offline "
              "report, or --verify-only for the daily-store check.")
        return 0

    print("reading the raw daily store for the whole universe (one pass) ...")
    cache = build_daily_cache(daily_store, symbols, min(start, mb.MINUTE_DATA_FLOOR) - timedelta(days=400), end)
    print(f"  cached {sum(len(v) for v in cache.by_symbol.values()):,} symbol-days "
          f"for {len(cache.by_symbol)} symbols")

    print("reading the NSE corporate-action history (one pass, day-cached) ...")
    actions = mb.fetch_corp_action_history(
        date(start.year, 1, 1), end, allow_network=True, cache_dir=args.cache_dir
    )
    print(f"  {len(actions):,} corporate-action rows {start.year}..{end.year}")

    master = load_instrument_master(cache_dir=args.cache_dir, allow_network=True)
    print(f"  instrument master loaded ({len(master)} NSE equities)")

    print("logging in to SmartAPI ...")
    client = sac.SmartApiClient(sac.Credentials.from_env()).login()
    print("  login OK\n")

    halted: RunHalted | None = None
    try:
        ledger = run_universe(client, master, symbols, actions, cache, config)
    except RunHalted as exc:
        halted = exc
        ledger = RunLedger.load(config.ledger_path)
    except KeyboardInterrupt:
        ledger = RunLedger.load(config.ledger_path)
        print("\ninterrupted; writing the report from what has settled so far ...")
    finally:
        client.logout()

    print("\nsweeping the daily store for unknown series on universe symbols (Q-4) ...")
    unknown = unknown_series_sweep(daily_store, symbols, date(2000, 1, 1), end, log=print)
    path = write_report(ledger, symbols, unknown, config)
    print(f"report written -> {path}")

    if halted is not None:
        print(f"\n*** RUN HALTED: {halted} ***")
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(parse_args(argv))
    except KeyboardInterrupt:
        print("\ninterrupted -- rerun the same command to resume")
        return 130
    except (UniverseBackfillError, DailyStoreError, InstrumentMasterError, sac.SmartApiError,
            ca.CorporateActionError, va.VendorAdjustmentError,
            universe_module.UniverseError) as exc:
        print(f"\nERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
