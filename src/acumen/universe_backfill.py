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
#: here on, listed in the report, and excluded from the coverage figure. 80% is the architect's
#: threshold for the run.
QUARANTINE_GATE1_MIN_PASS_RATE: Decimal = Decimal("0.80")

#: More than this FRACTION of the universe quarantined halts the whole run. One bad symbol is
#: an exclusion; a fifth of the universe is a systemic fault (a damaged daily store, a vendor
#: change) that must reach the architect before hours more are spent on it.
HALT_QUARANTINE_FRACTION: Decimal = Decimal("0.10")

#: How many pre-ex trading days to probe per era when building a map. The FIX-4 runbook used
#: 4-5 per window; the measured factor is the MEDIAN over the era's probe days, so a handful is
#: enough to be robust to one odd day while costing one request per era.
PROBE_DAYS_PER_ERA: int = 4

#: A day-of-the-week-agnostic minimum: an era with fewer stored trading days than this cannot
#: be probed usefully, and is reported unprobed rather than measured off one day.
MIN_PROBE_DAYS_PER_ERA: int = 1

DEFAULT_REPORT_PATH: Path = Path("docs") / "backfill_minute_report.md"

#: Identity of the gate DEFINITION a ledger row's numbers were produced under. The architect's
#: completeness ruling (2026-07-26) redefined CONTEXT 4.5 gate 2, so every row written before it
#: carries a different marker and is RE-GATED from the stored candles -- no window refetched. Bump
#: this string whenever a gate's definition changes; it is what makes a re-gate automatic, bounded
#: (a row already on the current definition is skipped) and auditable.
GATE_DEFINITION: str = "gate2-completeness-2026-07-26"

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
REBUILD_DISCIPLINE: str = "baseline-classification-2026-07-26"

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
    """One symbol-day of the RAW daily store, reduced to what the run actually uses."""

    high_paise: int
    low_paise: int
    close_paise: int
    volume: int


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

    _COLUMNS = ["trade_date", "high_paise", "low_paise", "close_paise", "volume"]

    def __init__(self, cache: DailyCache) -> None:
        self._cache = cache

    def daily(self, symbol: str, from_date: date, to_date: date, *, series=None) -> pd.DataFrame:
        sym = symbol.strip().upper()
        rows = [
            {
                "trade_date": day,
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
    """
    windows: list[va.WindowSpec] = []
    unprobeable: list[tuple[date, ...]] = []
    usable = sorted(day for day in trading_days if day >= max(clamp, floor))
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

    def era_rate_summary(self) -> str:
        return "; ".join(self.era_failure_rates)

    @property
    def gate1_rate(self) -> Decimal:
        if not self.gate1_total:
            return Decimal(0)
        return Decimal(self.gate1_pass) / Decimal(self.gate1_total)

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
        self.gate2_excluded = tally.gate2_excluded
        self.gate2_missing = tally.gate2_missing
        self.gate2_duplicates = tally.gate2_duplicates
        self.gate2_ohlc = tally.gate2_ohlc
        self.gate2_negative = tally.gate2_negative
        self.gate2_negative_dates = [d.isoformat() for d in tally.gate2_negative_days[:10]]
        self.liquidity_days = tally.liquidity_days
        self.gate3_checked = tally.gate3_checked
        self.gate3_failed = tally.gate3_failed
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
        if self.map_required_by_recovery:
            self.route = ROUTE_MAP_REQUIRED
            self.route_reasons = [*self.route_reasons, _RECOVERY_REASON]

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
    #: ``(day, gap_pct, raw_daily_volume)`` for every gate-1 FAILING day, and the raw daily volume
    #: of every gated day -- the inputs to :func:`gate1_failure_profile`.
    gate1_failures: list[tuple[date, "Decimal | None", int]] = field(default_factory=list)
    gate1_volumes: list[int] = field(default_factory=list)
    #: the days gate 1 actually ran on (a day with no raw daily row is not one of them).
    gate1_days: list[date] = field(default_factory=list)


def gate_symbol(
    minute_store: MinuteStore, cache: DailyCache, symbol: str, *, since: date | None = None
) -> GateTally:
    """Run CONTEXT 4.5 gates 1 and 2 over every stored symbol-day, a month at a time.

    Gate 1 runs FIRST and its verdict is handed to gate 2, because the completeness ruling
    (2026-07-26) makes gate 1 the completeness oracle: absent minute stamps exclude a day only when
    gate 1 has also failed on it. On a gate-1-passing day the same absent stamps are tradeless
    minutes and are counted as liquidity instead.
    """
    tally = GateTally()
    for day, bars in minute_store.iter_days(symbol, since, None):
        tally.days += 1
        tally.bars_total += len(bars)
        tally.first_day = tally.first_day or day
        tally.last_day = day
        tally.closes[day] = bars[-1].close_paise
        row = cache.day(symbol, day)
        reconciled: bool | None = None
        if row is None:
            tally.gate1_missing_daily += 1
        else:
            tally.gate1_total += 1
            tally.gate1_volumes.append(row.volume)
            tally.gate1_days.append(day)
            result = gates.volume_gate(row.volume, sum(b.volume for b in bars))
            reconciled = result.passed
            if result.passed:
                tally.gate1_pass += 1
            else:
                tally.gate1_failures.append((day, result.gap_pct, row.volume))
        integrity = gates.integrity_gate(bars, day, volume_reconciled=reconciled)
        tally.minutes_per_day.append(integrity.present)
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
    return tally


# --- the quarantine failure-pattern analysis (Q-12 addendum ruling; PURE) -----------------

PATTERN_CLUSTERED: str = "clustered-before-ex-date (adjustment problem)"
PATTERN_SCATTERED: str = "scattered (auction/liquidity shape)"
PATTERN_MIXED: str = "mixed"
PATTERN_NONE: str = "no gate-1 failures"

#: An era whose failure rate is at or above this is "clustered" -- essentially every day of that
#: span fails, which is what a wrong adjustment factor does (it is applied to the whole era).
_CLUSTER_RATE: Decimal = Decimal("0.90")
#: An era below this is not carrying a systematic adjustment error.
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
    """
    if not tally.closes:
        return
    days = sorted(tally.closes)
    for ex_date, (k, kinds) in sorted(share_count_factors_by_ex_date(symbol, factors).items()):
        before = [d for d in days if d < ex_date]
        after = [d for d in days if d >= ex_date]
        if not before or not after:
            continue  # the ex-date sits outside the stored span; nothing to compare
        result = gates.adjustment_continuity_gate(
            ex_date, before[-1], after[0],
            tally.closes[before[-1]], tally.closes[after[0]], k,
        )
        tally.gate3_checked += 1
        if not result.passed:
            tally.gate3_failed += 1
            tally.gate3_failures.append(f"{symbol} {'+'.join(kinds)} ex {ex_date}: {result.reason}")


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
    log: Callable[[str], None] = print,
) -> tuple["va.AdjustmentMap | None", int]:
    """Probe every era of ``symbol``'s ingest span and build + persist its map. Returns
    ``(map, unprobed_era_count)``; ``None`` when no era could be probed at all."""
    events = va.events_from_factor_table(
        view.factors, view.suppressions, view.pending_rights_ex_dates, symbol=symbol
    )
    windows, unprobeable = era_probe_windows(events, cache.days(symbol), clamp, config.end)
    if unprobeable:
        log(f"    {len(unprobeable)} era(s) have no trading day to probe -- older spans stay "
            "un-provable (excluded + counted)")
    if not windows:
        return None, len(unprobeable)
    log(f"    probing {len(windows)} era(s): {[w.label for w in windows]}")
    eras = va.measure_symbol_live(
        client, cached_store, symbol, token, events, windows, config.end
    )
    if not eras:
        return None, len(unprobeable)
    amap = va.build_map(symbol, config.end, events, eras, tick_paise=tick_paise)
    va.persist_map(amap, data_dir=config.map_data_dir)
    return amap, len(unprobeable)


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
            log(f"    map was built under estimator {adjustment_map.volume_estimator_id or '(none)'}"
                f" -> stale under Q-12 ({va.MAP_VOLUME_ESTIMATOR}); rebuilding")
            adjustment_map = None
        if adjustment_map is None or adjustment_map.fetch_date != config.end:
            try:
                adjustment_map, unprobed = build_map_for(
                    client, cached_store, cache, symbol, master.token(symbol), view, clamp,
                    config, tick_paise, log=log,
                )
            except (sac.SmartApiError, va.VendorAdjustmentError, DailyStoreError) as exc:
                record.status = STATUS_MAP_UNBUILDABLE
                record.note = f"map build failed: {type(exc).__name__}: {exc}"
                log(f"    map build FAILED: {exc}")
                return record
            record.map_unprobed_eras = unprobed
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
    _settle(record, tally, view.factors)

    if (
        record.status == STATUS_QUARANTINED
        and record.route == ROUTE_TABLE_PATH
        and not record.reroute_attempted
    ):
        # The Q-12 addendum ruling: a quarantined TABLE-PATH symbol is rerouted through the map path
        # as a second pass, because the routing rule only guarantees a PRICE oracle for a
        # non-share-count event -- so a bonus/split-only symbol whose vendor used a different factor
        # has nothing that can catch it. Probes buy the oracle; no stored candle is refetched.
        reroute_quarantined_to_map(
            client, master, cache, cached_store, record, view, clamp, config, tick_paise, log=log,
        )

    log(f"    windows {record.windows_present}p/{record.windows_empty}e/{record.windows_error}x  "
        f"days={record.depth_days} gate1={record.gate1_pass}/{record.gate1_total} "
        f"({record.gate1_rate:.1%}) gate2_excl={record.gate2_excluded} "
        f"liquidity_days={record.liquidity_days} "
        f"avg_min/day={record.avg_minutes_per_day} -> {record.status}")
    if tally.gate3_failures:
        for failure in tally.gate3_failures:
            log(f"    GATE-3 FAIL: {failure}")
    return record


def _settle(
    record: SymbolRecord, tally: GateTally, factors: Sequence[ca.Factor]
) -> None:
    """Set the terminal status from a fresh tally, and profile the failures if it is quarantined."""
    if record.gate1_total and record.gate1_rate < QUARANTINE_GATE1_MIN_PASS_RATE:
        record.status = STATUS_QUARANTINED
        record.note = (
            f"gate-1 pass rate {record.gate1_rate:.1%} is below "
            f"{QUARANTINE_GATE1_MIN_PASS_RATE:.0%}; skipped, listed, run continues"
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
) -> None:
    """The Q-12-addendum quarantine-recovery second pass. Mutates ``record`` in place.

    Probe the symbol's eras, build + persist a map (so the recovery is auditable), apply it to the
    ALREADY-STORED days by the NET factor ``k_map / k_table`` -- the store was already un-adjusted
    once by the factor table at ingest -- and re-run the gates. If the symbol recovers it settles; if
    it does not, it stays quarantined and carries the ruling's failure-pattern analysis.

    ``reroute_attempted`` is set whatever the outcome, so a resumed run never re-probes it.
    """
    record.reroute_attempted = True
    log(f"    QUARANTINE RECOVERY: rerouting {record.symbol} through the map path (second pass)")
    try:
        adjustment_map, unprobed = build_map_for(
            client, cached_store, cache, record.symbol, master.token(record.symbol),
            view, clamp, config, tick_paise, log=log,
        )
    except (sac.SmartApiError, va.VendorAdjustmentError, DailyStoreError, InstrumentMasterError) as exc:
        record.reroute_note = f"map build failed: {type(exc).__name__}: {exc}"
        log(f"      reroute map build FAILED: {exc} -- stays quarantined on the table-path numbers")
        return
    if adjustment_map is None:
        record.reroute_note = "no era of the ingest span could be probed; nothing to reroute through"
        log(f"      {record.reroute_note}")
        return

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
    before = f"{record.gate1_pass}/{record.gate1_total} ({record.gate1_rate:.1%})"
    record.snapshot_prior()
    record.apply_tally(tally)
    record.unprovable_days = len(applied.unprovable_days)
    record.unknown_baseline_days = len(applied.unknown_baseline_days)
    _settle(record, tally, view.factors)
    record.reroute_note = (
        f"map {record.map_eras_provable}/{record.map_eras} eras provable; "
        f"{applied.days_rewritten} day(s) rewritten, {applied.identity_days} already raw; "
        f"gate 1 {before} -> {record.gate1_pass}/{record.gate1_total} ({record.gate1_rate:.1%})"
    )
    log(f"      {record.reroute_note} -> {record.status}")
    for failure in tally.gate3_failures:
        log(f"      GATE-3 FAIL: {failure}")


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
    if record.status == STATUS_QUARANTINED and record.route == ROUTE_TABLE_PATH and not record.reroute_attempted:
        return "quarantine-recovery pass owed (Q-12 addendum)"
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
    already = ledger.quarantined()
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
        quarantined = ledger.quarantined()
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
    gate1_total = sum(r.gate1_total for r in settled)
    gate2_excluded = sum(r.gate2_excluded for r in settled)
    unprovable = sum(r.unprovable_days for r in settled)
    quarantined_days = sum(r.gate1_total for r in quarantined)
    all_days = gate1_total + quarantined_days
    usable = gate1_pass - gate2_excluded

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
    add(f"| Gate-1 PASS | {gate1_pass:,} ({_pct(gate1_pass, gate1_total)}) |")
    add(f"| Gate-2 exclusions | {gate2_excluded:,} |")
    add(f"| Un-provable days (no map era / unknown factor) | {unprovable:,} |")
    add(f"| **TOTAL coverage** (gate-1-passing days of every symbol-day seen) | "
        f"**{_pct(gate1_pass, all_days)}** |")
    add(f"| Usable symbol-days (gate 1 AND gate 2) | ~{max(usable, 0):,} |")
    add("")
    add(f"**Definition of done (plan.md chunk 5B): >= 95% of symbol-days pass gates.** "
        f"Measured: **{_pct(gate1_pass, all_days)}** of all symbol-days seen pass gate 1, with "
        "every failure categorized in section 4.")
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
    add("| Symbol | Route | Clamp | First 1-min day | Days | Windows p/e/x | Gate-1 | Gate-2 excl | Avg min/day | Status |")
    add("|---|---|---|---|---|---|---|---|---|---|")
    for record in sorted(records, key=lambda r: r.symbol):
        add(f"| {record.symbol} | {record.route} | {record.clamp_start or '-'} | "
            f"{record.first_stored_date or '-'} | {record.depth_days} | "
            f"{record.windows_present}/{record.windows_empty}/{record.windows_error} | "
            f"{record.gate1_pass}/{record.gate1_total} ({_pct(record.gate1_pass, record.gate1_total)}) | "
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
            after_pass += record.gate1_pass
            after_total += record.gate1_total
            before_g2 += max(record.prior_gate2_excluded, 0)
            after_g2 += record.gate2_excluded
            add(f"| {record.symbol} | {record.route} | "
                f"{record.prior_gate1_pass}/{record.prior_gate1_total} "
                f"({_pct(max(record.prior_gate1_pass, 0), max(record.prior_gate1_total, 0))}) | "
                f"{record.gate1_pass}/{record.gate1_total} "
                f"({_pct(record.gate1_pass, record.gate1_total)}) | "
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
    add("| Symbol | Avg min/day | Median min/day | Min min/day | Liquidity days | "
        "Liquidity days as % of stored |")
    add("|---|---|---|---|---|---|")
    for record in sorted(records, key=lambda r: r.symbol):
        if not record.depth_days:
            continue
        add(f"| {record.symbol} | {record.avg_minutes_per_day} | {record.median_minutes_per_day} | "
            f"{record.min_minutes_per_day} | {record.liquidity_days} | "
            f"{_pct(record.liquidity_days, record.depth_days)} |")
    add("")

    add("## 4. Exclusions by reason")
    add("")
    add("| Reason | Symbol-days | Note |")
    add("|---|---|---|")
    add(f"| gate-1 (volume reconciliation outside [-0.1%, +5.0%]) | "
        f"{gate1_total - gate1_pass:,} | CONTEXT 4.5 gate 1; excluded + counted per CONTEXT 7-E3 |")
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
                f"{record.gate1_pass}/{record.gate1_total} "
                f"({_pct(record.gate1_pass, record.gate1_total)}) | {rerouted} | "
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
            add(f"| {record.symbol} | {record.gate1_total - record.gate1_pass} | "
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
    add(f"- **Neither ruling widened gate 1's band.** It is still "
        f"`[{gates.VOLUME_GAP_MIN_PCT}%, {gates.VOLUME_GAP_MAX_PCT}%]`. The +5.0% ceiling's behaviour "
        "on illiquid names is DEFERRED to the architect with the per-symbol evidence in section 4.")
    add("- **The daily store was verified before the run** (`DailyStore.verify()`, the owed "
        "REVIEW_2 F7 check): the oracle is checked before it is trusted.")
    add("")
    return "\n".join(lines) + "\n"


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

    return load_config(include_env=False).path("data_dir") / subdir


def _data_dir() -> Path:
    from .config import load_config

    return load_config(include_env=False).path("data_dir")


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
