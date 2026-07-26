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

    @property
    def gate1_rate(self) -> Decimal:
        if not self.gate1_total:
            return Decimal(0)
        return Decimal(self.gate1_pass) / Decimal(self.gate1_total)

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


def gate_symbol(
    minute_store: MinuteStore, cache: DailyCache, symbol: str, *, since: date | None = None
) -> GateTally:
    """Run CONTEXT 4.5 gates 1 and 2 over every stored symbol-day, a month at a time."""
    tally = GateTally()
    for day, bars in minute_store.iter_days(symbol, since, None):
        tally.days += 1
        tally.bars_total += len(bars)
        tally.first_day = tally.first_day or day
        tally.last_day = day
        tally.closes[day] = bars[-1].close_paise
        row = cache.day(symbol, day)
        if row is None:
            tally.gate1_missing_daily += 1
        else:
            tally.gate1_total += 1
            if gates.volume_gate(row.volume, sum(b.volume for b in bars)).passed:
                tally.gate1_pass += 1
        if not gates.integrity_gate(bars, day).passed:
            tally.gate2_excluded += 1
    return tally


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
) -> SymbolRecord:
    """Route, map, ingest and gate ONE symbol. Every failure lands in the record, never a crash."""
    record, view, decision, tick_paise = plan_symbol(
        symbol, master, cache, actions, cached_store, config
    )
    if view is None or decision is None:
        log(f"  {symbol}: {record.status} -- {record.note}")
        return record

    clamp = date.fromisoformat(record.clamp_start or config.start.isoformat())
    log(f"  {symbol}: route={record.route} clamp={clamp}"
        + (f" ({len(record.route_reasons)} forcing event(s))" if record.route_reasons else ""))

    adjustment_map: "va.AdjustmentMap | None" = None
    if decision.map_required:
        try:
            adjustment_map = mb.load_adjustment_map_for(symbol, data_dir=config.map_data_dir)
        except va.VendorAdjustmentError:
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
    record.depth_days = tally.days
    record.avg_minutes_per_day = round(tally.bars_total / tally.days, 1) if tally.days else 0.0
    record.gate1_pass = tally.gate1_pass
    record.gate1_total = tally.gate1_total
    record.gate2_excluded = tally.gate2_excluded
    record.gate3_checked = tally.gate3_checked
    record.gate3_failed = tally.gate3_failed

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
    log(f"    windows {record.windows_present}p/{record.windows_empty}e/{record.windows_error}x  "
        f"days={record.depth_days} gate1={record.gate1_pass}/{record.gate1_total} "
        f"({record.gate1_rate:.1%}) gate2_excl={record.gate2_excluded} "
        f"avg_min/day={record.avg_minutes_per_day} -> {record.status}")
    if tally.gate3_failures:
        for failure in tally.gate3_failures:
            log(f"    GATE-3 FAIL: {failure}")
    return record


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
    todo = [s for s in symbols if not (s in ledger.records and ledger.records[s].is_terminal)]
    terminal = len(symbols) - len(todo)
    if config.max_symbols is not None:
        todo = todo[: config.max_symbols]
    log(f"universe: {len(symbols)} symbols; {terminal} already terminal; {len(todo)} to process "
        f"this run (quarantine ceiling {ceiling})")

    started = time.monotonic()
    for index, symbol in enumerate(todo, start=1):
        elapsed = int(time.monotonic() - started)
        log(f"[{index}/{len(todo)}] {symbol}  (elapsed {elapsed}s)")
        try:
            record = process_symbol(
                client, master, cache, cached_store, actions, symbol, config, log=log
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
        add(f"Per-event factor sources across every committed map -- "
            f"**ours {sources.get(va.SOURCE_OURS, 0)}**, "
            f"**measured {sources.get(va.SOURCE_MEASURED, 0)}**, "
            f"**absent {sources.get(va.SOURCE_ABSENT, 0)}** (price side). `ours` = our exact "
            "CONTEXT 4.2 factor matched the vendor; `measured` = the vendor used a factor we "
            "had to observe; `absent` = the vendor did not apply the event in that era.")
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

    add("## 4. Exclusions by reason")
    add("")
    add("| Reason | Symbol-days | Note |")
    add("|---|---|---|")
    add(f"| gate-1 (volume reconciliation outside [-0.1%, +5.0%]) | "
        f"{gate1_total - gate1_pass:,} | CONTEXT 4.5 gate 1; excluded + counted per CONTEXT 7-E3 |")
    add(f"| gate-2 (candle integrity) | {gate2_excluded:,} | missing > 15 minutes, duplicate "
        "stamps, or OHLC violations |")
    add(f"| un-provable (no map era / unknown factor in (D, F]) | {unprovable:,} | the Q-11 "
        "surgical clamp -- stored so the day is visible, failed by gate 1 |")
    add(f"| quarantined symbols (whole history) | {quarantined_days:,} | "
        f"{len(quarantined)} symbol(s) below the {QUARANTINE_GATE1_MIN_PASS_RATE:.0%} gate-1 floor |")
    add("")
    thin = [r for r in records if r.depth_days and r.gate2_excluded / r.depth_days > 0.10]
    add("### Gate 2 and liquidity -- read this before reading the coverage number")
    add("")
    add("CONTEXT 4.5 gate 2 excludes a day missing more than 15 of the 375 session minutes, and "
        "the vendor OMITS minutes in which nothing traded. For a liquid symbol in a recent year "
        "that is 375/375 and gate 2 never fires (the CONTEXT 4.3 PoC measured exactly that on 25 "
        "symbol-days). For a less liquid F&O underlying in an older year the true traded-minute "
        "count is well under 375, so gate 2 excludes the day -- correctly, per the spec as "
        "written, but for a LIQUIDITY reason rather than a data-quality one.")
    add("")
    if thin:
        add(f"**{len(thin)} symbol(s) lose more than 10% of their stored days to gate 2.** Their "
            "average traded minutes per day is in the table above; the lower it is, the more of "
            "the symbol's old history gate 2 removes.")
    add("")
    if quarantined:
        add("### Quarantined symbols")
        add("")
        add("| Symbol | Route | Gate-1 | Why |")
        add("|---|---|---|---|")
        for record in sorted(quarantined, key=lambda r: r.symbol):
            add(f"| {record.symbol} | {record.route} | "
                f"{record.gate1_pass}/{record.gate1_total} "
                f"({_pct(record.gate1_pass, record.gate1_total)}) | {record.note} |")
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


def _source_counts(records: Sequence[SymbolRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        for event in _dedupe_events(record.map_events):
            counts[event.price_source] = counts.get(event.price_source, 0) + 1
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
