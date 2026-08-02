"""The chunk-9B FULL-HISTORY RUN: preflight, the operator's runner, progress and ETA.

Chunk 9A built the machine and proved it on a pilot. This module is what the OPERATOR points
at the whole data era, in their own terminal, for hours. It owns no strategy rule and no
metric: it decides WHAT to run over (the universe and the span), refuses to start when the
inputs are not what they must be, and then drives :class:`acumen.backtest.BacktestRunner`.

**PREFLIGHT FIRST, ALWAYS.** Ten checks, every one measured from the machine the run will use
-- `config.yaml`'s money keys, the Q40-d flag keys still null, both stores, the
disclosed-residual register, the settled universe, the corporate-action day-cache served
offline, the PINNED instrument master and its digest, the minute era taken FROM THE STORES
(never a typed date), and the trading calendar. **If any check fails the run command is not
emitted and the run does not start.** A backtest that begins on a half-open store produces a
ledger nobody can qualify, and the failure would surface hours later as a refusal count nobody
can explain.

**THE UNIVERSE IS THE 204 SETTLED SYMBOLS** of CONTEXT 4.6, read from the disclosed-residual
register rather than from the F&O list: the 6 quarantined symbols (ASTRAL, IEX, NESTLEIND,
NTPC, UPL, VBL) have no usable minute era, and CONTEXT 4.6 makes reading the register before
any per-symbol statistic a chunk-9 duty.

**THE SPAN IS THE MINUTE ERA, MEASURED.** The first and last stored 1-minute day across those
204 symbols, read from the parquet month files themselves. CONTEXT 4.3's "from 2016-10 for
established stocks" is a fact about the vendor, not a constant this repo may type.

**RESUMABLE, BY CONSTRUCTION.** Ctrl-C at any moment and re-run the same command: the runner
writes a symbol's shard only when that symbol is COMPLETE, so a resume re-walks only the symbol
that was in flight and never duplicates a row. The CONTEXT 7-E2 session scan is cached beside
the ledger (decision B181, recorded as a 9B duty in the chunk-9A pack), because that scan costs
the same order as the walk itself and a resume that re-scanned the universe would pay for the
whole run again before writing its first new row.

**THE TICK INPUT IS PINNED** (QUESTIONS.md Q-20, architect 02-Aug-2026). `config.yaml` names ONE
instrument-master snapshot; the preflight resolves it, prints its sha256, and hands that exact
file to the run, which records both on the manifest. Latest-by-filename selection is retired
from this path -- the vendor moved the tick on 11 walked symbols in both directions within two
days, and CONTEXT 3.3 sizes the profile row grid by it.

**TWO THINGS WILL REFUSE A RESUME, DELIBERATELY: a moved HEAD and a moved MASTER.** The run
spec's digest covers the code SHA and the pin's filename+sha256, so committing (or checking out)
anything while a run is in flight -- or re-pointing the pin -- makes the resume a different run
and it stops rather than mixing two code states, or two tick regimes, into one ledger. Finish
the run, then commit.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Sequence

import pyarrow.parquet as pq

from . import backtest as bt
from .atomic_io import atomic_write_text
from .calendar import CalendarError, TradingCalendar
from .config import ConfigError, load_config
from .daily_store import DailyStore
from .minute_backfill import fetch_corp_action_history
from .minute_store import MinuteStore
from .nse_http import NseFetchError

#: The chunk-5B status that makes a symbol eligible for the run (CONTEXT 4.6).
SETTLED: str = "settled"

#: Where a full-history run lands, under ``<data_root>/backtests/``. One directory, standard
#: names. ``data_root`` lives OUTSIDE the repository tree (CLAUDE.md Q-18 layer 1), so a run's
#: artifacts are out of every git command's reach as well.
DEFAULT_LABEL: str = "chunk9b_full"

#: The earliest year NSE's corporate-action API answers for (CONTEXT 4.2, verified).
CA_FIRST_YEAR: int = 2005

#: The architect's GO RULING (31-Jul-2026), condition (2), VERBATIM. Stamped on the manifest of
#: every run this module drives, so a ledger can never be read as trader-confirmed.
Q44_PENDING_STAMP: str = "PENDING TRADER CONFIRMATION OF Q44 (gap-rule example, POC 2032)"

#: The same ruling's escalation and retention rule, carried with the stamp so the manifest says
#: what happens if the confirmation contradicts CONTEXT 3.4 rather than leaving it to memory.
Q44_ESCALATION: str = (
    "if the trader's Q44 answer surprises, that is a CONTEXT 3.4 change -> spec version bump "
    "-> full re-run; this ledger is then SUPERSEDED, retained and labelled, never deleted "
    "(architect's GO ruling, 31-Jul-2026)"
)


class PreflightError(RuntimeError):
    """A preflight check could not even be attempted -- distinct from a check that FAILED."""


@dataclass(frozen=True)
class StoreStamp:
    """One store root's LAST-CHANGED time -- CLAUDE.md's Q-18 layer 3, made printable.

    The layer says the operator keeps TWO snapshot generations and never overwrites the
    previous until the new one is verified, "and the preflight prints the stores' last-changed
    timestamps so the operator can confirm the snapshot is newer". This is that measurement:
    the newest modification time anywhere under the root, so a file rewritten deep inside a
    symbol directory still moves the number the operator compares against.

    It is deliberately NOT a check and NOT a disclosure. It cannot fail a preflight (a stale
    snapshot is the operator's call, not the runner's), and it never reaches the run manifest,
    which must stay byte-identical across runs and therefore carries no clock read.
    """

    name: str
    root: Path
    exists: bool
    last_changed: datetime | None
    entries: int

    def line(self, width: int) -> str:
        if not self.exists:
            return f"{self.name.ljust(width)} : {self.root}  MISSING"
        stamp = (
            self.last_changed.strftime("%Y-%m-%d %H:%M:%S")
            if self.last_changed is not None
            else "unknown"
        )
        return (
            f"{self.name.ljust(width)} : {self.root}  last changed {stamp}  "
            f"({self.entries:,} entries)"
        )


def store_last_changed(name: str, root: Path) -> StoreStamp:
    """Walk ``root`` and return its newest modification time and entry count.

    Both stores are written through :mod:`acumen.atomic_io` (write-temp-then-replace), so a
    changed byte anywhere shows up as a changed mtime on a real file; the walk takes the max
    over files AND directories so a pure add/remove is caught too. Unreadable entries are
    skipped rather than raised on: this is an operator convenience, and it must never be the
    thing that stops a run.
    """
    root = Path(root)
    if not root.exists():
        return StoreStamp(name=name, root=root, exists=False, last_changed=None, entries=0)
    newest = 0.0
    entries = 0
    for parent, dirnames, filenames in os.walk(root):
        here = Path(parent)
        for entry in (here, *(here / n for n in dirnames), *(here / n for n in filenames)):
            try:
                newest = max(newest, entry.stat().st_mtime)
            except OSError:  # a vanished or locked entry is not worth a failed preflight
                continue
        entries += len(dirnames) + len(filenames)
    return StoreStamp(
        name=name,
        root=root,
        exists=True,
        last_changed=datetime.fromtimestamp(newest) if newest else None,
        entries=entries,
    )


@dataclass(frozen=True)
class Check:
    """One preflight verdict: what was checked, whether it holds, and what was measured."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class Preflight:
    """Every check, plus the universe and span the run would use if they all pass.

    ``notes`` are DISCLOSED CONDITIONS: measured facts about the inputs that are not failures
    and must not be silent either. They are printed above the verdict and carried into the run
    manifest, so nobody reads the ledger's span without knowing why it is the span it is.
    """

    checks: tuple[Check, ...]
    symbols: tuple[str, ...]
    start: date | None
    end: date | None
    #: Both are ``None`` on exactly one branch: ``config.yaml`` did not load, so the store
    #: roots are UNKNOWN. Nothing invents ``data/`` there -- CLAUDE.md's Q-18 layer 1 puts the
    #: stores outside the repo and config.yaml is the only thing that says where. That branch
    #: is always NO-GO, and the renderer reads neither field unless the verdict is GO.
    data_dir: Path | None
    run_dir: Path | None
    notes: tuple[str, ...] = ()
    #: CLAUDE.md Q-18 layer 3. Printed, never checked, never carried into the manifest.
    store_stamps: tuple[StoreStamp, ...] = ()
    #: The Q-20 PIN the run will read, resolved by check 7, plus its content digest. ``None``
    #: when that check FAILED (or was never reached), which is always a NO-GO -- the run path
    #: takes the master from here and never re-selects one.
    master_path: Path | None = None
    master_sha256: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(check.ok for check in self.checks)

    @property
    def failures(self) -> tuple[Check, ...]:
        return tuple(check for check in self.checks if not check.ok)


# --- the universe and the era (both MEASURED, neither typed) ----------------------------------


def settled_symbols(register: dict[str, bt.ResidualEntry]) -> tuple[str, ...]:
    """The CONTEXT 4.6 settled universe, alphabetical. Quarantined symbols are excluded."""
    return tuple(
        sorted(symbol for symbol, entry in register.items() if entry.status == SETTLED)
    )


def _month_files(store: MinuteStore, symbol: str) -> list[Path]:
    home = store.minute_dir / symbol.strip().upper()
    if not home.is_dir():
        return []
    return sorted(home.glob(f"{symbol.strip().upper()}_*.parquet"))


def _month_extremes(path: Path) -> tuple[date, date] | None:
    """(first, last) stored trade date inside ONE month file, or ``None`` when it is empty."""
    days = pq.read_table(path, columns=["trade_date"]).column("trade_date").to_pylist()
    days = [day for day in days if day is not None]
    return (min(days), max(days)) if days else None


def symbol_era(store: MinuteStore, symbol: str) -> tuple[date, date] | None:
    """One symbol's first and last stored 1-minute day, or ``None`` when it has none.

    Reads only the EXTREME month files (walking inward past any empty one) rather than every
    month: the era of 204 symbols is a preflight question and must not cost a full store scan.
    """
    files = _month_files(store, symbol)
    first = last = None
    for path in files:
        extremes = _month_extremes(path)
        if extremes is not None:
            first = extremes[0]
            break
    for path in reversed(files):
        extremes = _month_extremes(path)
        if extremes is not None:
            last = extremes[1]
            break
    if first is None or last is None:
        return None
    return first, last


def era_span(store: MinuteStore, symbols: Sequence[str]) -> tuple[date | None, date | None, int]:
    """The FULL minute era across ``symbols``: earliest first day, latest last day, and how
    many symbols actually carry stored candles. Measured from the store, never typed."""
    firsts: list[date] = []
    lasts: list[date] = []
    for symbol in symbols:
        era = symbol_era(store, symbol)
        if era is None:
            continue
        firsts.append(era[0])
        lasts.append(era[1])
    if not firsts:
        return None, None, 0
    return min(firsts), max(lasts), len(firsts)


# --- the CONTEXT 7-E2 session scan, cached beside the ledger (decision B181) -------------------


def _session_cache_key(symbols: Sequence[str], start: date, end: date, code_sha: str) -> str:
    payload = json.dumps(
        {
            "symbols": list(symbols),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "code_sha": code_sha,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def load_session_scan(
    run_dir: Path, symbols: Sequence[str], start: date, end: date, code_sha: str
) -> frozenset[date] | None:
    """The cached CONTEXT 7-E2 scan for exactly this universe, span and code state, or ``None``.

    A cache whose key does not match is IGNORED rather than trusted: the scan is a function of
    the universe, the span and the E2 predicate, and serving one built for a different set would
    silently exclude (or admit) trading days.
    """
    path = Path(run_dir) / bt.SESSIONS_NAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if payload.get("key") != _session_cache_key(symbols, start, end, code_sha):
        return None
    return frozenset(date.fromisoformat(day) for day in payload.get("non_standard", []))


def save_session_scan(
    run_dir: Path,
    symbols: Sequence[str],
    start: date,
    end: date,
    code_sha: str,
    non_standard: frozenset[date],
) -> Path:
    """Persist the scan beside the ledger, atomically. No clock is read into it."""
    return atomic_write_text(
        Path(run_dir) / bt.SESSIONS_NAME,
        bt.canonical_json(
            {
                "key": _session_cache_key(symbols, start, end, code_sha),
                "symbols": list(symbols),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "code_sha": code_sha,
                "non_standard": [day.isoformat() for day in sorted(non_standard)],
            }
        ),
    )


# --- preflight ---------------------------------------------------------------------------------


def preflight(
    *,
    data_dir: Path | None = None,
    cache_dir: Path | None = None,
    label: str = DEFAULT_LABEL,
    symbols_override: Sequence[str] | None = None,
) -> Preflight:
    """Run every gate the full-history run depends on and report each one's measurement.

    Nothing here writes, fetches or decides: it opens what the run will open, in the order the
    run will open it, and says what it found. ``symbols_override`` is for the smoke run -- the
    universe check still measures the full settled list and then reports the subset.
    """
    checks: list[Check] = []
    universe: tuple[str, ...] = ()
    start = end = None

    # 1. config.yaml -- the three money keys present, the two flag keys still null.
    try:
        config = load_config(include_env=False)
        risk = config.require_risk_per_trade_paise()
        cost = config.cost_per_trade_paise()
        capital = config.initial_capital_paise()
        reference = config.capital_reference_paise()
        basis = config.margin_basis_text()
    except ConfigError as exc:
        return Preflight(
            checks=(Check("config.yaml complete", False, str(exc)),),
            symbols=(),
            start=None,
            end=None,
            data_dir=Path(data_dir) if data_dir is not None else None,
            run_dir=(Path(data_dir) / "backtests" / label) if data_dir is not None else None,
        )

    checks.append(
        Check(
            "config.yaml complete (CONTEXT 3.5 money)",
            risk > 0 and cost > 0 and capital > 0,
            f"risk_per_trade {risk:,} paise, cost_per_trade {cost:,} paise, "
            f"initial_capital {capital:,} paise",
        )
    )
    checks.append(
        Check(
            "Q40-d flag keys still NULL -> flags-pending path confirmed",
            reference is None and basis is None,
            f"capital_reference={reference!r}, margin_basis={basis!r}; every output will carry "
            f'"{bt.CAPITAL_FLAGS_PENDING_NOTE}"',
        )
    )

    data = Path(data_dir) if data_dir is not None else config.path("data_root")
    cache = Path(cache_dir) if cache_dir is not None else config.path("cache_root")
    run_dir = data / "backtests" / label
    # CLAUDE.md Q-18 layer 3: measured here, printed by the renderer, checked by nobody.
    stamps = (store_last_changed("data_root", data), store_last_changed("cache_root", cache))

    # 2. the daily store (the gate-1 / gate-1P raw oracle).
    daily_store = DailyStore.at(data / "daily_store")
    daily_files = (
        len(list((data / "daily_store" / "daily").glob("**/*.parquet")))
        if (data / "daily_store" / "daily").is_dir()
        else 0
    )
    checks.append(
        Check(
            "daily store reachable (raw bhavcopy oracle)",
            daily_files > 0,
            f"{daily_files:,} parquet file(s) under {data / 'daily_store'}",
        )
    )

    # 3. the minute store (the engines' own prices).
    minute_store = MinuteStore.at(data / "minute_store")
    minute_symbols = (
        sorted(p.name for p in minute_store.minute_dir.iterdir() if p.is_dir())
        if minute_store.minute_dir.is_dir()
        else []
    )
    checks.append(
        Check(
            "minute store reachable (1-minute RAW prices)",
            len(minute_symbols) > 0,
            f"{len(minute_symbols)} symbol director(ies) under {minute_store.minute_dir}",
        )
    )

    # 4. the disclosed-residual register (CONTEXT 4.6's chunk-9 duty).
    register: dict[str, bt.ResidualEntry] = {}
    try:
        register = bt.load_residual_register(data / bt.RESIDUAL_LEDGER_RELPATH)
        register_ok, register_detail = True, (
            f"{len(register)} symbol(s) from {bt.RESIDUAL_LEDGER_RELPATH}; caveat carried "
            f'verbatim: "{bt.residual_caveat(register)}"'
        )
    except bt.BacktestError as exc:
        register_ok, register_detail = False, str(exc)
    checks.append(Check("disclosed-residual register loads", register_ok, register_detail))

    # 5. the universe: the settled symbols, and every one of them present in the minute store.
    universe = settled_symbols(register)
    quarantined = tuple(
        sorted(symbol for symbol, entry in register.items() if entry.status != SETTLED)
    )
    missing = tuple(symbol for symbol in universe if symbol not in set(minute_symbols))
    checks.append(
        Check(
            "universe = the settled symbols, all present in the store",
            bool(universe) and not missing,
            f"{len(universe)} settled, {len(quarantined)} quarantined "
            f"({', '.join(quarantined) or 'none'})"
            + (f"; MISSING from the minute store: {', '.join(missing)}" if missing else ""),
        )
    )

    # 6. the corporate-action day-cache, SERVED OFFLINE (the 31-Jul-2026 ruling in action).
    era_first, era_last, with_data = era_span(minute_store, universe)
    ca_years = (CA_FIRST_YEAR, (era_last or date.today()).year)
    try:
        actions = fetch_corp_action_history(
            date(ca_years[0], 1, 1), date(ca_years[1], 12, 31),
            allow_network=False, cache_dir=cache_dir,
        )
        ca_ok = len(actions) > 0
        ca_detail = (
            f"{len(actions):,} corporate actions parsed from the day-cache for "
            f"{ca_years[0]}..{ca_years[1]}, offline, at any age"
        )
    except NseFetchError as exc:
        ca_ok, ca_detail = False, str(exc)
    checks.append(
        Check(f"CA day-cache {ca_years[0]}..{ca_years[1]} present and served offline",
              ca_ok, ca_detail)
    )

    # 7. the PINNED instrument master (per-symbol tick; CONTEXT 4.3 forbids hardcoding it, and
    #    QUESTIONS.md Q-20 pins WHICH dump supplies it -- the vendor's tick is not stable).
    master_path = None
    master_sha = None
    try:
        master, master_path, master_sha = bt.pinned_master(cache, config.instrument_master)
        master_ok = True
        master_detail = (
            f"PINNED {master_path.name} ({len(master.by_symbol):,} NSE -EQ instruments), "
            f"sha256 {master_sha}"
        )
    except Exception as exc:  # noqa: BLE001 -- any failure here is a refusal, not a crash
        master_ok, master_detail = False, f"{type(exc).__name__}: {exc}"
    checks.append(
        Check("instrument master PINNED (Q-20) and its digest taken", master_ok, master_detail)
    )

    # 8. the span: the FULL minute era, measured from the stores -- and clamped to the RAW
    #    DAILY ORACLE, which CONTEXT 4.6 records as lagging (the frozen "next-data-work" item
    #    C2, "bhavcopy ingest to clear the 178-day store-lag no-oracle failures").
    notes: list[str] = []
    oracle_end = _daily_ledger_end(daily_store, era_first, era_last)
    start, end = era_first, era_last
    if era_first is not None and era_last is not None and oracle_end is not None:
        end = min(era_last, oracle_end)
    span_ok = (
        era_first is not None
        and end is not None
        and with_data == len(universe)
        and end >= era_first
    )
    checks.append(
        Check(
            "span = the full minute era, taken from the stores",
            span_ok,
            (
                f"minute era {era_first} -> {era_last} measured over {with_data} of "
                f"{len(universe)} settled symbols; raw daily oracle settled through "
                f"{oracle_end}; SPAN WALKED = {start} -> {end} "
                f"({(end - start).days + 1:,} calendar days)"
            )
            if span_ok
            else "no stored 1-minute candles found for the settled universe",
        )
    )
    if span_ok and end < era_last:
        beyond = _trading_days_between(daily_store, end, era_last)
        notes.append(
            f"SPAN CLAMPED TO THE RAW DAILY ORACLE. The minute store carries candles through "
            f"{era_last}, but the bhavcopy ledger is settled only through {oracle_end}, so "
            f"{(era_last - end).days} further calendar day(s) -- "
            f"{', '.join(day.isoformat() for day in beyond) or 'none'} by weekday -- are "
            f"OUTSIDE the walked span. This is CONTEXT 4.6's disclosed store lag (the frozen "
            f"next-data-work item: 'bhavcopy ingest to clear the store-lag no-oracle "
            f"failures'), not damage. Those days could not have traded in any case: gate 1P "
            f"FAILS a day with no raw daily row, and the trading calendar REFUSES to derive "
            f"over dates the bhavcopy ledger never attempted (QUESTIONS.md Q-3 safeguard 1). "
            f"Extending the span is a bhavcopy top-up (network, chunk-2 work), after which "
            f"this preflight moves the end date by itself."
        )

    # 9. the calendar, over the span the run will walk (plus CONTEXT 3.2's D-1/D-2 lead).
    calendar_ok, calendar_detail = False, "not attempted (no span)"
    if start is not None and end is not None:
        try:
            calendar = TradingCalendar.from_daily_store_range(
                daily_store, start - timedelta(days=bt.CALENDAR_LEAD_DAYS), end
            )
            trading_days = sum(
                1 for day in bt.iter_trading_days(calendar, start, end)
            )
            calendar_ok = trading_days > 0
            calendar_detail = (
                f"{len(calendar.trading_days):,} trading day(s) derived, {trading_days:,} "
                f"inside the span, {bt.CALENDAR_LEAD_DAYS}-day lead for CONTEXT 3.2's pair"
            )
        except CalendarError as exc:
            calendar_detail = str(exc)
    checks.append(Check("trading calendar loaded over the span", calendar_ok, calendar_detail))

    if symbols_override:
        universe = tuple(symbol.strip().upper() for symbol in symbols_override)

    return Preflight(
        checks=tuple(checks),
        symbols=universe,
        start=start,
        end=end,
        data_dir=data,
        run_dir=run_dir,
        notes=tuple(notes),
        store_stamps=stamps,
        master_path=master_path,
        master_sha256=master_sha,
    )


def _daily_ledger_end(store: DailyStore, first: date | None, last: date | None) -> date | None:
    """The last date the raw bhavcopy ledger has SETTLED -- the daily oracle's own horizon.

    Read from the ledger rather than from the parquet rows: a confirmed-404 (a holiday) is a
    settled answer with no row, and it still bounds the calendar the run walks.
    """
    if first is None or last is None:
        return None
    frame = store.coverage(first, last)
    if frame.empty:
        return None
    stamp = max(frame["trade_date"])
    return stamp if isinstance(stamp, date) else stamp.date()


def _trading_days_between(store: DailyStore, after: date, through: date) -> tuple[date, ...]:
    """The weekday dates in ``(after, through]``. Named in the clamp note so the operator sees
    exactly which sessions the daily oracle cannot yet qualify -- weekends are not sessions."""
    days: list[date] = []
    current = after + timedelta(days=1)
    while current <= through:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return tuple(days)


def render_preflight(report: Preflight, *, label: str, command: str | None) -> list[str]:
    """The operator-facing preflight print-out, one line per check plus the verdict."""
    lines = ["CHUNK 9B PREFLIGHT", "=" * 78]
    width = max(len(check.name) for check in report.checks)
    for index, check in enumerate(report.checks, start=1):
        mark = "PASS" if check.ok else "FAIL"
        lines.append(f"{index}. [{mark}] {check.name.ljust(width)}  {check.detail}")
    lines.append("=" * 78)
    if report.notes:
        lines.append("DISCLOSED CONDITIONS (measured, not failures -- and not silent):")
        for note in report.notes:
            lines.append(f"  * {note}")
        lines.append("=" * 78)
    if report.store_stamps:
        stamp_width = max(len(stamp.name) for stamp in report.store_stamps)
        lines.append(
            "STORE FRESHNESS (CLAUDE.md Q-18 layer 3 -- the stores live OUTSIDE this repo):"
        )
        for stamp in report.store_stamps:
            lines.append(f"  {stamp.line(stamp_width)}")
        lines.append(
            "  A snapshot covers these stores only if it is NEWER than every line above. "
            "Keep TWO generations; never overwrite the previous one until the new one is "
            "verified. Snapshotting is the OPERATOR's, never a session's."
        )
        lines.append("=" * 78)
    if report.ok:
        lines.append(
            f"VERDICT: GO -- {len(report.checks)} of {len(report.checks)} checks pass."
        )
        lines.append(f"  universe : {len(report.symbols)} symbol(s)")
        lines.append(f"  span     : {report.start} -> {report.end}")
        lines.append(f"  run dir  : {report.run_dir}")
        if report.master_path is not None:
            lines.append(f"  tick pin : {report.master_path.name} (Q-20)")
            lines.append(f"             sha256 {report.master_sha256}")
        lines.append("")
        lines.append("THE RUN COMMAND (paste this; safe to Ctrl-C and re-run):")
        lines.append("")
        lines.append(f"    {command}")
        lines.append("")
        lines.append(
            "  progress: one line per symbol, with elapsed / rate / ETA, on stdout. "
            "Redirect it to a file to keep a log."
        )
        lines.append(
            f"  finished: the last line reads 'RUN COMPLETE' and "
            f"{report.run_dir / bt.LEDGER_NAME} and {report.run_dir / bt.MANIFEST_NAME} exist."
        )
        lines.append(
            "  do NOT commit or check out anything while it runs: the run spec's digest covers "
            "the code SHA, so a moved HEAD makes a resume refuse rather than mix two code "
            "states into one ledger."
        )
    else:
        failed = ", ".join(check.name for check in report.failures)
        lines.append(f"VERDICT: NO-GO -- {len(report.failures)} check(s) FAILED: {failed}.")
        lines.append(
            "  The run command is NOT emitted. Fix the inputs above and re-run the preflight; "
            f"a ledger built on a half-open store cannot be qualified by anyone (label {label})."
        )
    return lines


# --- progress + ETA -----------------------------------------------------------------------------


class ProgressReporter:
    """Prints the runner's own per-symbol line, then an elapsed / rate / ETA line.

    :meth:`acumen.backtest.BacktestRunner.run` calls ``progress`` exactly once per symbol -- for
    a resumed shard as well as for a freshly walked one -- and calls ``after_symbol`` only for
    the ones it actually walked. So the COUNT comes from the progress calls (that is genuine
    remaining work) and the RATE comes from the freshly walked ones (a resumed shard is free and
    would flatter the estimate).
    """

    def __init__(
        self,
        total: int,
        *,
        out: Callable[[str], None] = print,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.total = total
        self._out = out
        self._clock = clock
        self._now = now if now is not None else datetime.now
        self._started = clock()
        self.seen = 0
        self.walked = 0
        self._walk_started: float | None = None
        self._walk_seconds = 0.0

    def __call__(self, message: str) -> None:
        self.seen += 1
        self._out(message.rstrip())
        self._out(self._eta_line())
        self._walk_started = self._clock()

    def after_symbol(self, _symbol: str) -> None:
        if self._walk_started is not None:
            self._walk_seconds += max(0.0, self._clock() - self._walk_started)
        self.walked += 1

    def _eta_line(self) -> str:
        elapsed = self._clock() - self._started
        left = max(0, self.total - self.seen)
        pct = (self.seen / self.total * 100) if self.total else 100.0
        head = (
            f"    [{self.seen}/{self.total}] {pct:5.1f}% | elapsed {_hms(elapsed)}"
        )
        if self.walked == 0 or self._walk_seconds <= 0:
            return f"{head} | rate -- | ETA -- (no symbol walked yet)"
        per_symbol = self._walk_seconds / self.walked
        remaining = per_symbol * left
        finish = self._now() + timedelta(seconds=remaining)
        return (
            f"{head} | {per_symbol:,.1f}s/symbol | ETA {_hms(remaining)} "
            f"(~{finish:%Y-%m-%d %H:%M})"
        )


def _hms(seconds: float) -> str:
    total = int(round(max(0.0, seconds)))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:d}:{minutes:02d}:{secs:02d}"


# --- the run ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RunOutcome:
    """What the operator (and the 9B REPORT session) needs after the run returns."""

    result: bt.RunResult
    run_dir: Path
    seconds: float
    symbols: int
    days: int
    sessions_cached: bool


def execute(
    *,
    symbols: Sequence[str],
    start: date,
    end: date,
    run_dir: Path,
    label: str,
    data_dir: Path | None = None,
    cache_dir: Path | None = None,
    disclosures: tuple[str, ...] = (),
    master_path: Path | None = None,
    out: Callable[[str], None] = print,
    clock: Callable[[], float] = time.monotonic,
) -> RunOutcome:
    """Wire the runner (reusing a cached E2 scan when there is one) and walk the whole span.

    ``master_path`` is the Q-20 pin the PREFLIGHT already resolved and printed. It is threaded
    through rather than re-resolved so that the file the operator was shown is provably the file
    the run reads; ``None`` falls through to the configured pin, never to "newest on disk".
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    wanted = tuple(symbol.strip().upper() for symbol in symbols)
    sha = bt.code_sha()
    wiring_started = clock()

    cached = load_session_scan(run_dir, wanted, start, end, sha)
    if cached is None:
        out("scanning for CONTEXT 7-E2 non-standard sessions (once per run; cached below)...")
    runner, resolved_master, ca_summary = bt.build_runner(
        wanted,
        start,
        end,
        data_dir=data_dir,
        cache_dir=cache_dir,
        label=label,
        progress=None if cached is not None else lambda line: out(line.rstrip()),
        non_standard_sessions=cached,
        disclosures=disclosures,
        master_path=master_path,
    )
    if master_path is not None and Path(resolved_master) != Path(master_path):
        # Unreachable by construction, and checked anyway: the whole point of threading the pin
        # is that the operator's printed digest belongs to the file the run actually read.
        raise PreflightError(
            f"the run wired {resolved_master} but the preflight pinned {master_path}"
        )
    if cached is None:
        save_session_scan(run_dir, wanted, start, end, sha, runner.non_standard_sessions)

    out(
        f"instrument master: PINNED {runner.spec.master_file} "
        f"(sha256 {runner.spec.master_sha256}; QUESTIONS.md Q-20)"
    )
    out(
        f"corporate-action tables built for {len(ca_summary)} symbol(s); "
        f"CONTEXT 7-E2 non-standard sessions excluded: "
        f"{len(runner.non_standard_sessions)}"
        + (" (from cache)" if cached is not None else " (scanned, cached)")
    )
    out(
        f"wiring complete in {_hms(clock() - wiring_started)} "
        "(session scan + corporate-action tables + calendar)"
    )
    for sentence in disclosures:
        out(f"DISCLOSURE: {sentence}")
    out("-" * 78)

    reporter = ProgressReporter(len(wanted), out=out, clock=clock)
    started = clock()
    result = runner.run(run_dir, progress=reporter, after_symbol=reporter.after_symbol)
    seconds = clock() - started

    out("-" * 78)
    totals = result.manifest["totals"]
    dropped = sum(
        1 for row in result.rows if bt.FLAG_OUT_OF_SESSION_DROPPED in row.flags
    )
    out(
        f"RUN COMPLETE: {totals['walked']:,} symbol-days walked, {totals['usable']:,} usable, "
        f"{totals['executed']:,} trades, in {_hms(seconds)} "
        f"({totals['walked'] / seconds if seconds else 0:,.1f} days/s)"
    )
    out(
        f"  refused by reason: "
        + "; ".join(
            f"{count:,} {reason}"
            for reason, count in sorted(
                result.manifest["refused_by_reason"].items(), key=lambda kv: -kv[1]
            )
        )
    )
    out(
        f"  CONTEXT 7-E2 candle-level drops: {dropped:,} symbol-day(s) carried an "
        f"out-of-session 1-minute stamp (flagged on the row; QUESTIONS.md Q-17)"
    )
    out(f"  ledger  : {result.ledger_path}")
    out(f"  manifest: {result.manifest_path}")
    return RunOutcome(
        result=result,
        run_dir=run_dir,
        seconds=seconds,
        symbols=len(wanted),
        days=totals["walked"],
        sessions_cached=cached is not None,
    )


# --- the CLI ------------------------------------------------------------------------------------


def run_command(label: str, symbols: Sequence[str] | None = None) -> str:
    """The exact one-liner the operator pastes. Kept in ONE place so it cannot drift.

    The launcher path (`python scripts/run_backtest.py`) rather than `-m`, because it is the
    one that works from a bare clone with no install step (chunk-0 B2) -- the same choice every
    other operator command in this repo makes.
    """
    parts = ["python scripts/run_backtest.py"]
    if label != DEFAULT_LABEL:
        parts.append(f"--label {label}")
    if symbols:
        parts.append("--symbols " + ",".join(symbols))
    return " ".join(parts)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="acumen.run_backtest",
        description="chunk 9B: the full-history backtest run (preflight, then walk).",
    )
    parser.add_argument(
        "--label",
        default=DEFAULT_LABEL,
        help=f"run directory name under <data_root>/backtests/ (default: {DEFAULT_LABEL})",
    )
    parser.add_argument(
        "--symbols",
        default=None,
        help="comma-separated subset (the SMOKE path); omit for the full settled universe",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="run the checks, print the run command if they all pass, and stop",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    subset = (
        tuple(part.strip().upper() for part in args.symbols.split(",") if part.strip())
        if args.symbols
        else None
    )
    report = preflight(label=args.label, symbols_override=subset)
    command = run_command(args.label, subset)
    for line in render_preflight(report, label=args.label, command=command):
        print(line, flush=True)
    if not report.ok:
        return 1
    if args.preflight_only:
        return 0

    print("", flush=True)
    execute(
        symbols=report.symbols,
        start=report.start,
        end=report.end,
        run_dir=report.run_dir,
        label=args.label,
        # The architect's GO-ruling disclosures first (they are RULED text), then whatever the
        # preflight measured about these inputs -- so the manifest says both what it is not
        # allowed to claim and why its span is the span it is.
        disclosures=(
            bt.CAPITAL_FLAGS_PENDING_NOTE,
            Q44_PENDING_STAMP,
            Q44_ESCALATION,
            *report.notes,
        ),
        master_path=report.master_path,
        out=lambda line: print(line, flush=True),
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- the operator's entry point
    raise SystemExit(main())
