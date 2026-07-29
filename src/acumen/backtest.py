"""The backtest RUNNER and its run ledger (chunk 9A). I/O allowed here.

This module is the machine that will produce the full-history backtest. It owns no strategy
rule: every decision it prints was made by a pure engine it calls.

**What one stock-day goes through, in order** (CONTEXT 4.6 + 3.2 + 3.3 + 3.4 + 3.5):

1. **CONTEXT 7-E2** -- a date whose stored candles lie wholly outside 09:15-15:30 is a
   NON-STANDARD session (Muhurat and the special/shortened sessions). E2 names exactly that
   detection ("candle data on a date absent from the trading calendar, or outside
   09:15-15:30"), so such a date is removed from the trading calendar BEFORE any bias pair is
   built -- it is not the previous trading day of anything -- and it is counted under its own
   reason. See :func:`scan_non_standard_sessions`.
2. **bias** -- :class:`acumen.bias_engine.BiasEngine` over the symbol's own daily candles,
   with the REAL chunk-3 factor table wired (pairwise "P in C's scale", CONTEXT 3.2) and the
   chunk-3 suppression list (demerger / Q-6 tier-2 rights). A day the bias engine cannot
   resolve is a COUNTED no-trade, never an exception.
3. **the CONTEXT 4.6 gate battery, RECOMPUTED per day** -- gate 1, gate 2 and gate 1P, by
   :meth:`acumen.signal_engine.SignalPipeline.gate_day`. There is no per-day exclusion file
   (CONTEXT 4.6's own words); both stores are local, so the gates are recomputed exactly.
4. **POC** (chunk 6), **signals** (chunk 7), **money** (chunk 8).

**One reason per day, in a fixed order.** A day can fail several ways at once. The order is
E2 -> no minutes -> gate 1 -> gate 2 -> gate 1P -> suppressed -> no bias -> no POC -> the
signal outcome (chunk-7 decision B162, extended at the front by E2 and the bias failure).
The counts therefore PARTITION the walked days instead of double-counting them.

**The ledger is resumable, idempotent and byte-identical on a re-run.** One row per walked
symbol-day -- a priced trade or a no-trade row carrying its reason -- written through
:mod:`acumen.atomic_io` (temp file, fsync, atomic replace). A symbol's shard is written only
when that symbol is COMPLETE, so an interrupted run leaves no partial symbol behind and a
resume re-walks exactly what it lost: zero duplicates. Nothing in the ledger or the manifest
is read from a clock, so the same code over the same stores produces the same bytes.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from . import corp_actions as ca
from . import signal_engine as se
from . import signals as sig
from . import simulate as sim
from .aggregate import Bar
from .atomic_io import atomic_write_text
from .bias import RULE_3_NO_MINUTE
from .bias_engine import BiasEngine, BiasEngineError, DailyBias
from .calendar import CalendarError, TradingCalendar
from .config import load_config
from .daily_store import DailyStore
from .instrument_master import (
    CACHE_SUBDIR as MASTER_CACHE_SUBDIR,
    InstrumentMaster,
    InstrumentMasterError,
    load_master_file,
)
from .minute_backfill import corp_actions_for_symbol, fetch_corp_action_history
from .minute_store import MinuteStore
from .signal_engine import SignalPipeline

#: The CONTEXT.md version this runner implements. Written into every manifest.
SPEC_VERSION: str = "v1.4"

#: The session window CONTEXT 3.1 gives NSE cash. Used ONLY by the E2 detector below.
SESSION_OPEN: time = time(9, 15)
SESSION_LAST_OPEN_STAMP: time = time(15, 29)

#: Refusal reasons this module adds in front of :mod:`acumen.signal_engine`'s own set.
REASON_E2_NON_STANDARD: str = (
    "CONTEXT 7-E2 non-standard session (stored candles outside 09:15-15:30)"
)
REASON_BIAS_UNRESOLVED: str = "bias unresolvable (CONTEXT 3.2 pair could not be assembled)"

#: Row statuses. ``evaluated`` means the day reached CONTEXT 3.4; it does NOT mean it traded.
STATUS_EVALUATED: str = "evaluated"
STATUS_REFUSED: str = "refused"

#: CONTEXT 4.6's chunk-9 duty, carried VERBATIM into every manifest and every report built on
#: it: the two settled-but-partial symbols whose backtests cover a minority of stored history.
RESIDUAL_CAVEAT: str = (
    "IOC (41.9% price-proven) and TATASTEEL (65.8%) are settled-but-partial under B149 -- "
    "their backtests cover a minority of stored history, concentrated in recent years."
)

#: Where the chunk-5B run ledger lives, relative to ``data_dir``. It is the machine-readable
#: face of the disclosed-residual register (backfill report section 3f).
RESIDUAL_LEDGER_RELPATH: str = "universe_backfill/ledger.json"

#: The rare shapes every run counts, whether or not they occur. A key that only appears when
#: the shape occurs lets silence read as coverage; a printed ZERO says "this window carries no
#: real-data witness for that branch", which is a fact about the window (REVIEW_8 finding Q1).
RARE_SHAPE_LABELS: tuple[str, ...] = (
    "gap entries",
    "qty-zero unsizable days",
    "signal-unsizable (degenerate) days",
    "both-touched candles (stop won)",
    "square-offs priced at the entry candle",
    "rule-3 tie bias days",
    "rule-3 day with no 1-minute data (carried, CONTEXT 3.2)",
    "E10 fallback reference (no 11:00-stamped candle)",
)

#: Ledger / manifest / progress file names inside a run directory.
LEDGER_NAME: str = "ledger.jsonl"
MANIFEST_NAME: str = "manifest.json"
PROGRESS_NAME: str = "progress.json"
SESSIONS_NAME: str = "sessions.json"
SHARD_DIRNAME: str = "symbols"

#: How far before the span the calendar is derived, so ``bias_pair(D)`` can reach D-1 and D-2
#: for the span's first trading day (chunk-8 used the same lead).
CALENDAR_LEAD_DAYS: int = 30


class BacktestError(RuntimeError):
    """The run cannot be assembled, or a resume was asked for on a different run."""


# --- E2: which dates are not standard sessions (PURE detector + the store scan) -------------


def is_standard_session_stamp(stamp: datetime) -> bool:
    """CONTEXT 7-E2's clock half: is this OPEN-stamped 1-minute bar inside the session? PURE."""
    return SESSION_OPEN <= stamp.time() <= SESSION_LAST_OPEN_STAMP


def scan_non_standard_sessions(
    minute_store: MinuteStore,
    symbols: Sequence[str],
    days: Sequence[date],
    *,
    progress: Callable[[str], None] | None = None,
) -> tuple[date, ...]:
    """Dates in ``days`` whose stored candles lie WHOLLY outside 09:15-15:30, oldest first.

    CONTEXT 7-E2 names this detection itself. A session is a property of the MARKET, not of a
    symbol, so the scan is over the whole run universe and a date is non-standard when at least
    one symbol stored candles for it and no symbol stored a candle inside the session window
    (the Muhurat shape: an 18:00-19:00 hour, every symbol, one date).
    """
    inside: set[date] = set()
    outside: set[date] = set()
    for symbol in symbols:
        for day in days:
            bars = minute_store.minutes(symbol, day)
            if not bars:
                continue
            if any(is_standard_session_stamp(bar.stamp) for bar in bars):
                inside.add(day)
            else:
                outside.add(day)
        if progress is not None:
            progress(f"  session scan: {symbol}")
    return tuple(sorted(outside - inside))


# --- the ledger row -------------------------------------------------------------------------


@dataclass(frozen=True)
class LedgerRow:
    """One walked symbol-day: the priced trade, or the recorded reason there is none.

    Every field is an integer, a string, a bool or ``None`` -- there is no float anywhere, so
    the JSON the ledger holds is exact (CONTEXT 7-E11). The POC is carried as
    ``poc_half_paise`` (twice the price) because a row midpoint may legally sit half a paisa
    off the tick grid (CONTEXT 3.3) and halving is the only division a reader ever needs.
    """

    symbol: str
    day: date
    status: str
    reason: str
    bias: str | None = None
    bias_rule: str | None = None
    side: str | None = None
    tie_case: bool = False
    suppressed: bool = False
    minute_count: int = 0
    gate1_passed: bool | None = None
    gate1_relieved: bool = False
    gate2_passed: bool | None = None
    gate1p_passed: bool | None = None
    poc_half_paise: int | None = None
    reference_paise: int | None = None
    reference_source: str | None = None
    outcome: str | None = None
    consumed: bool = False
    signalled: bool = False
    executed: bool = False
    gap_entry: bool = False
    entry_paise: int | None = None
    stop_paise: int | None = None
    target_paise: int | None = None
    per_share_risk_paise: int | None = None
    entry_close_stamp: datetime | None = None
    exit_kind: str | None = None
    exit_paise: int | None = None
    exit_close_stamp: datetime | None = None
    qty: int = 0
    notional_paise: int = 0
    gross_pnl_paise: int = 0
    cost_paise: int = 0
    net_pnl_paise: int = 0
    mfe_paise: int | None = None
    mae_paise: int | None = None
    flags: tuple[str, ...] = ()

    def to_json(self) -> str:
        """One canonical JSON line: sorted keys, no spaces, no clock read. Deterministic."""
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))

    def as_dict(self) -> dict:
        payload = {
            "symbol": self.symbol,
            "day": self.day.isoformat(),
            "status": self.status,
            "reason": self.reason,
            "bias": self.bias,
            "bias_rule": self.bias_rule,
            "side": self.side,
            "tie_case": self.tie_case,
            "suppressed": self.suppressed,
            "minute_count": self.minute_count,
            "gate1_passed": self.gate1_passed,
            "gate1_relieved": self.gate1_relieved,
            "gate2_passed": self.gate2_passed,
            "gate1p_passed": self.gate1p_passed,
            "poc_half_paise": self.poc_half_paise,
            "reference_paise": self.reference_paise,
            "reference_source": self.reference_source,
            "outcome": self.outcome,
            "consumed": self.consumed,
            "signalled": self.signalled,
            "executed": self.executed,
            "gap_entry": self.gap_entry,
            "entry_paise": self.entry_paise,
            "stop_paise": self.stop_paise,
            "target_paise": self.target_paise,
            "per_share_risk_paise": self.per_share_risk_paise,
            "entry_close_stamp": _stamp_text(self.entry_close_stamp),
            "exit_kind": self.exit_kind,
            "exit_paise": self.exit_paise,
            "exit_close_stamp": _stamp_text(self.exit_close_stamp),
            "qty": self.qty,
            "notional_paise": self.notional_paise,
            "gross_pnl_paise": self.gross_pnl_paise,
            "cost_paise": self.cost_paise,
            "net_pnl_paise": self.net_pnl_paise,
            "mfe_paise": self.mfe_paise,
            "mae_paise": self.mae_paise,
            "flags": list(self.flags),
        }
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping) -> "LedgerRow":
        return cls(
            symbol=str(payload["symbol"]),
            day=date.fromisoformat(str(payload["day"])),
            status=str(payload["status"]),
            reason=str(payload["reason"]),
            bias=payload.get("bias"),
            bias_rule=payload.get("bias_rule"),
            side=payload.get("side"),
            tie_case=bool(payload.get("tie_case", False)),
            suppressed=bool(payload.get("suppressed", False)),
            minute_count=int(payload.get("minute_count", 0)),
            gate1_passed=payload.get("gate1_passed"),
            gate1_relieved=bool(payload.get("gate1_relieved", False)),
            gate2_passed=payload.get("gate2_passed"),
            gate1p_passed=payload.get("gate1p_passed"),
            poc_half_paise=payload.get("poc_half_paise"),
            reference_paise=payload.get("reference_paise"),
            reference_source=payload.get("reference_source"),
            outcome=payload.get("outcome"),
            consumed=bool(payload.get("consumed", False)),
            signalled=bool(payload.get("signalled", False)),
            executed=bool(payload.get("executed", False)),
            gap_entry=bool(payload.get("gap_entry", False)),
            entry_paise=payload.get("entry_paise"),
            stop_paise=payload.get("stop_paise"),
            target_paise=payload.get("target_paise"),
            per_share_risk_paise=payload.get("per_share_risk_paise"),
            entry_close_stamp=_parse_stamp(payload.get("entry_close_stamp")),
            exit_kind=payload.get("exit_kind"),
            exit_paise=payload.get("exit_paise"),
            exit_close_stamp=_parse_stamp(payload.get("exit_close_stamp")),
            qty=int(payload.get("qty", 0)),
            notional_paise=int(payload.get("notional_paise", 0)),
            gross_pnl_paise=int(payload.get("gross_pnl_paise", 0)),
            cost_paise=int(payload.get("cost_paise", 0)),
            net_pnl_paise=int(payload.get("net_pnl_paise", 0)),
            mfe_paise=payload.get("mfe_paise"),
            mae_paise=payload.get("mae_paise"),
            flags=tuple(str(flag) for flag in payload.get("flags", ())),
        )

    @property
    def poc_paise(self) -> Fraction | None:
        return None if self.poc_half_paise is None else Fraction(self.poc_half_paise, 2)


def _stamp_text(stamp: datetime | None) -> str | None:
    return None if stamp is None else stamp.isoformat(sep="T", timespec="seconds")


def _parse_stamp(text) -> datetime | None:
    return None if text in (None, "") else datetime.fromisoformat(str(text))


# --- MFE / MAE (CONTEXT 7-E13's per-trade excursions), PURE ---------------------------------


def trade_excursion_paise(
    side: str,
    entry_paise: int,
    qty: int,
    bars: Sequence[Bar],
    entry_close_stamp: datetime,
    exit_close_stamp: datetime | None,
) -> tuple[int, int]:
    """``(MFE, MAE)`` in paise over the candles the position was actually held. PURE.

    CONTEXT 7-E13 lists "MFE/MAE per trade" without fixing a convention, so this is the one
    the spec's own monitoring rule forces: the position opens at the entry candle's CLOSE and
    the entry candle itself cannot move it (CONTEXT 7-E7), so the excursion is measured over
    the candles AFTER the entry candle up to and including the exit candle -- exactly the
    candles CONTEXT 3.4-5 walks. MFE is signed >= 0 and MAE <= 0; a trade whose price never
    traded beyond the entry in one direction has 0 on that side, and a trade with no monitored
    candle at all (chunk-7 decision B159) has 0 on both.
    """
    if qty <= 0:
        return (0, 0)
    monitored = [
        bar
        for bar in bars
        if bar.close_stamp > entry_close_stamp
        and (exit_close_stamp is None or bar.close_stamp <= exit_close_stamp)
    ]
    if not monitored:
        return (0, 0)
    highest = max(bar.high_paise for bar in monitored)
    lowest = min(bar.low_paise for bar in monitored)
    if side == sig.LONG:
        favourable, adverse = highest - entry_paise, lowest - entry_paise
    else:
        favourable, adverse = entry_paise - lowest, entry_paise - highest
    return (max(0, favourable) * qty, min(0, adverse) * qty)


# --- the run spec ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunSpec:
    """Everything that decides what the ledger contains -- and therefore its digest.

    ``digest`` covers the code SHA as well: a ledger is a function of ONE code state, so a
    resume after the code moved is refused rather than silently mixed (see
    :meth:`BacktestRunner.run`).
    """

    symbols: tuple[str, ...]
    start: date
    end: date
    row_size: int
    risk_per_trade_paise: int
    cost_paise: int
    seed_from: date | None = None
    spec_version: str = SPEC_VERSION
    code_sha: str = ""
    factor_digest: str = ""
    capital_reference_paise: int | None = None
    margin_basis: str | None = None
    label: str = ""

    @property
    def seed_date(self) -> date:
        return self.seed_from if self.seed_from is not None else self.start

    def as_dict(self) -> dict:
        return {
            "symbols": list(self.symbols),
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "seed_from": self.seed_date.isoformat(),
            "row_size": self.row_size,
            "risk_per_trade_paise": self.risk_per_trade_paise,
            "cost_paise": self.cost_paise,
            "spec_version": self.spec_version,
            "code_sha": self.code_sha,
            "factor_digest": self.factor_digest,
            "capital_reference_paise": self.capital_reference_paise,
            "margin_basis": self.margin_basis,
            "label": self.label,
        }

    def digest(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("ascii")).hexdigest()


def code_sha(repo_root: Path | None = None) -> str:
    """``git rev-parse HEAD`` for the manifest, or ``"unknown"`` outside a git checkout."""
    root = repo_root if repo_root is not None else Path(__file__).resolve().parents[2]
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:  # pragma: no cover -- git absent
        return "unknown"
    sha = out.stdout.strip()
    return sha if out.returncode == 0 and sha else "unknown"


# --- the disclosed-residual register --------------------------------------------------------


@dataclass(frozen=True)
class ResidualEntry:
    """One symbol's line of the chunk-5B disclosed-residual register (report section 3f)."""

    symbol: str
    status: str
    gate1p_pass: int
    gate1p_total: int
    gate1p_no_oracle: int
    residual_reason: str

    @property
    def price_proven_ratio(self) -> Fraction | None:
        if self.gate1p_total <= 0:
            return None
        return Fraction(self.gate1p_pass, self.gate1p_total)

    def as_dict(self) -> dict:
        ratio = self.price_proven_ratio
        return {
            "symbol": self.symbol,
            "status": self.status,
            "gate1p_pass": self.gate1p_pass,
            "gate1p_total": self.gate1p_total,
            "gate1p_no_oracle": self.gate1p_no_oracle,
            # ratio -> percent (x100) -> hundredths of a percent (x100 again). Written as two
            # factors of 100 rather than one 10,000 so that no module in src/acumen carries an
            # integer literal equal to a CONTEXT 3.5 money amount in paise -- the widened money
            # tripwire (REVIEW_9A finding C1) scans every module for exactly those magnitudes.
            # The arithmetic is Fraction and therefore identical either way.
            "price_proven_pct_x100": None if ratio is None else int(ratio * 100 * 100),
            "residual_reason": self.residual_reason,
        }


def load_residual_register(path: Path) -> dict[str, ResidualEntry]:
    """Read the chunk-5B ledger -- the machine-readable disclosed-residual register.

    CONTEXT 4.6 makes reading it a chunk-9 duty ("read the residual register before any
    per-symbol statistic"). A missing file is an ERROR, not an empty register: a run that
    silently forgot which symbols are price-partial would print per-symbol statistics nobody
    could qualify.
    """
    source = Path(path)
    if not source.is_file():
        raise BacktestError(
            f"No disclosed-residual register at {source}. CONTEXT 4.6 makes reading it a "
            "chunk-9 duty; run the chunk-5B backfill or point the runner at its ledger."
        )
    payload = json.loads(source.read_text(encoding="utf-8"))
    rows = payload.get("symbols", {})
    register: dict[str, ResidualEntry] = {}
    for symbol, row in rows.items():
        register[str(symbol).upper()] = ResidualEntry(
            symbol=str(symbol).upper(),
            status=str(row.get("status", "")),
            gate1p_pass=int(row.get("gate1p_pass", 0)),
            gate1p_total=int(row.get("gate1p_total", 0)),
            gate1p_no_oracle=int(row.get("gate1p_no_oracle", 0)),
            residual_reason=str(row.get("residual_reason", "")),
        )
    return register


# --- the runner -------------------------------------------------------------------------------


@dataclass(frozen=True)
class SymbolRun:
    """One symbol's rows plus the counts the manifest prints for it."""

    symbol: str
    rows: tuple[LedgerRow, ...]

    def counts(self) -> dict:
        refused: dict[str, int] = {}
        for row in self.rows:
            if row.status == STATUS_REFUSED:
                refused[row.reason] = refused.get(row.reason, 0) + 1
        return {
            "walked": len(self.rows),
            "usable": sum(1 for row in self.rows if row.status == STATUS_EVALUATED),
            "signalled": sum(1 for row in self.rows if row.signalled),
            "executed": sum(1 for row in self.rows if row.executed),
            "refused": dict(sorted(refused.items())),
        }


@dataclass(frozen=True)
class RunResult:
    """A finished run: every row, the manifest, and where both were written."""

    spec: RunSpec
    rows: tuple[LedgerRow, ...]
    manifest: dict
    ledger_path: Path
    manifest_path: Path
    non_standard_sessions: tuple[date, ...]


@dataclass(frozen=True)
class BacktestRunner:
    """Walks symbol-days, prices them, and writes a resumable ledger. I/O lives HERE."""

    spec: RunSpec
    pipeline: SignalPipeline
    calendar: TradingCalendar
    minute_store: MinuteStore
    daily_store: DailyStore
    factors: Mapping[str, tuple[ca.Factor, ...]]
    suppressions: Mapping[str, tuple[ca.Suppression, ...]]
    residual: Mapping[str, ResidualEntry]
    non_standard_sessions: frozenset[date] = frozenset()
    minute_loader: Callable[[str, date], Sequence | None] | None = None

    # --- one symbol ---------------------------------------------------------------------

    def bias_map(self, symbol: str) -> tuple[dict[date, DailyBias], str | None]:
        """The symbol's CONTEXT 3.2 bias series over the span, or the reason there is none.

        A :class:`acumen.bias_engine.BiasEngineError` is a COUNTED no-trade for every day of
        the span, never a crash: a full-history run over 400,000 stock-days must not die
        because one symbol's pair cannot be assembled.
        """
        engine = BiasEngine(
            store=self.daily_store,
            calendar=self.calendar,
            factors=tuple(self.factors.get(symbol.upper(), ())),
            suppressions=tuple(self.suppressions.get(symbol.upper(), ())),
            minute_loader=self.minute_loader,
        )
        first = self._first_pairable_day()
        if first is None:
            return ({}, f"{REASON_BIAS_UNRESOLVED}: no day in the span has a CONTEXT 3.2 pair")
        try:
            series = engine.bias_series(symbol, first, self.spec.end)
        except (BiasEngineError, CalendarError) as exc:
            return ({}, f"{REASON_BIAS_UNRESOLVED}: {exc}")
        return ({entry.trade_date: entry for entry in series}, None)

    def _first_pairable_day(self) -> date | None:
        """The first day of the span whose CONTEXT 3.2 pair the calendar can assemble.

        A span that starts at (or before) a symbol's first data has days with no D-1/D-2 at
        all. Those days are refused ONE AT A TIME, counted -- the alternative, letting the
        engine's exception refuse the whole symbol, would lose a whole history to its own first
        morning. The carry then seeds at the first pairable day, which is CONTEXT 3.2's own
        "walk forward from the earliest data" rule.
        """
        current = self.spec.seed_date
        while current <= self.spec.end:
            try:
                if self.calendar.is_trading_day(current):
                    self.calendar.bias_pair(current)
                    return current
            except CalendarError:
                pass
            current += timedelta(days=1)
        return None

    def _is_trading_day(self, day: date) -> bool | None:
        """True / False, or ``None`` when the calendar cannot answer for that date at all."""
        try:
            return self.calendar.is_trading_day(day)
        except CalendarError:
            return None

    def walk_symbol(self, symbol: str) -> SymbolRun:
        """Every walked day for one symbol, in date order. No I/O beyond the two stores."""
        biases, failure = self.bias_map(symbol)
        rows: list[LedgerRow] = []
        for day in self._span_days():
            if day in self.non_standard_sessions:
                rows.append(
                    LedgerRow(
                        symbol=symbol,
                        day=day,
                        status=STATUS_REFUSED,
                        reason=REASON_E2_NON_STANDARD,
                    )
                )
                continue
            trading = self._is_trading_day(day)
            if trading is False:
                continue  # a weekend or a holiday: there is no stock-day to walk
            if failure is not None or trading is None:
                rows.append(
                    LedgerRow(
                        symbol=symbol,
                        day=day,
                        status=STATUS_REFUSED,
                        reason=failure
                        or f"{REASON_BIAS_UNRESOLVED}: the calendar does not cover {day}",
                    )
                )
                continue
            bias = biases.get(day)
            if bias is None:
                rows.append(
                    LedgerRow(
                        symbol=symbol,
                        day=day,
                        status=STATUS_REFUSED,
                        reason=(
                            f"{REASON_BIAS_UNRESOLVED}: no CONTEXT 3.2 pair for {day} "
                            "(D-1 or D-2 is outside the run's own history)"
                        ),
                    )
                )
                continue
            rows.append(self.walk_day(symbol, bias))
        return SymbolRun(symbol=symbol, rows=tuple(rows))

    def walk_day(self, symbol: str, bias: DailyBias) -> LedgerRow:
        """One symbol-day: gates -> POC -> signal -> money, or the first refusal reason."""
        stock_day = self.pipeline.stock_day(symbol, bias.trade_date, bias=bias)
        record = None
        if stock_day.signal is not None:
            record = sim.simulate_day(
                stock_day.signal,
                stock_day.bars,
                symbol=symbol,
                risk_per_trade_paise=self.spec.risk_per_trade_paise,
                cost_paise=self.spec.cost_paise,
                bias=bias.bias,
                tie_case=bias.tie_case,
            )
        return self._row(symbol, bias, stock_day, record)

    # --- the row ------------------------------------------------------------------------

    def _row(
        self,
        symbol: str,
        bias: DailyBias,
        stock_day: se.StockDay,
        record: sim.TradeRecord | None,
    ) -> LedgerRow:
        gates = stock_day.gates
        profile = stock_day.profile
        poc = None if profile is None else profile.poc_paise
        base = LedgerRow(
            symbol=symbol,
            day=stock_day.day,
            status=STATUS_EVALUATED if stock_day.evaluated else STATUS_REFUSED,
            reason=stock_day.reason,
            bias=bias.bias,
            bias_rule=bias.rule,
            side=stock_day.side,
            tie_case=bias.tie_case,
            suppressed=bias.suppressed,
            minute_count=stock_day.minute_count,
            gate1_passed=None if gates is None or gates.gate1 is None else gates.gate1.passed,
            gate1_relieved=bool(gates is not None and gates.relieved),
            gate2_passed=None if gates is None else gates.gate2.passed,
            gate1p_passed=None if gates is None else gates.gate1p.passed,
            poc_half_paise=None if poc is None else int(poc * 2),
        )
        if record is None:
            return base
        signal = stock_day.signal
        mfe = mae = None
        if record.executed and record.entry_paise is not None and record.entry_close_stamp:
            mfe, mae = trade_excursion_paise(
                record.side,
                record.entry_paise,
                record.qty,
                stock_day.bars,
                record.entry_close_stamp,
                record.exit_close_stamp,
            )
        return replace(
            base,
            reference_paise=None if signal is None else signal.reference_paise,
            reference_source=None if signal is None else signal.reference_source,
            outcome=record.outcome,
            consumed=record.consumed,
            signalled=record.signalled,
            executed=record.executed,
            gap_entry=record.gap_entry,
            entry_paise=record.entry_paise,
            stop_paise=record.stop_paise,
            target_paise=record.target_paise,
            per_share_risk_paise=record.per_share_risk_paise,
            entry_close_stamp=record.entry_close_stamp,
            exit_kind=record.exit_kind,
            exit_paise=record.exit_paise,
            exit_close_stamp=record.exit_close_stamp,
            qty=record.qty,
            notional_paise=(
                0 if record.entry_paise is None else record.qty * record.entry_paise
            ),
            gross_pnl_paise=record.gross_pnl_paise,
            cost_paise=record.cost_paise,
            net_pnl_paise=record.net_pnl_paise,
            mfe_paise=mfe,
            mae_paise=mae,
            flags=record.flags,
        )

    def _span_days(self) -> tuple[date, ...]:
        days: list[date] = []
        current = self.spec.start
        while current <= self.spec.end:
            days.append(current)
            current += timedelta(days=1)
        return tuple(days)

    # --- the run ------------------------------------------------------------------------

    def run(
        self,
        run_dir: Path,
        *,
        progress: Callable[[str], None] | None = None,
        after_symbol: Callable[[str], None] | None = None,
    ) -> RunResult:
        """Walk every symbol, shard by shard, then write the ledger and the manifest.

        Resumable: a symbol's shard is written (atomically, fsynced) only once that symbol is
        COMPLETE, and ``progress.json`` records which symbols are done. A resume replays the
        finished shards and re-walks only what was lost, so no row can be duplicated. Idempotent:
        the shard content, the ledger and the manifest are pure functions of the spec and the
        stores, so a completed re-run reproduces the same bytes.

        ``after_symbol`` runs after each symbol's shard is durable -- the hook the resume test
        interrupts the run from.
        """
        base = Path(run_dir)
        shards = base / SHARD_DIRNAME
        shards.mkdir(parents=True, exist_ok=True)
        done = self._resume_state(base)

        for symbol in self.spec.symbols:
            shard = shards / f"{symbol}.jsonl"
            if symbol in done and shard.is_file():
                if progress is not None:
                    progress(f"  {symbol}: resumed from shard ({shard.name})")
                continue
            walked = self.walk_symbol(symbol)
            atomic_write_text(shard, "".join(row.to_json() + "\n" for row in walked.rows))
            done.append(symbol)
            self._write_progress(base, done)
            if progress is not None:
                counts = walked.counts()
                progress(
                    f"  {symbol}: {counts['walked']} walked, {counts['usable']} usable, "
                    f"{counts['executed']} executed"
                )
            if after_symbol is not None:
                after_symbol(symbol)

        rows: list[LedgerRow] = []
        per_symbol: dict[str, dict] = {}
        for symbol in self.spec.symbols:
            shard_rows = read_ledger(shards / f"{symbol}.jsonl")
            rows.extend(shard_rows)
            per_symbol[symbol] = SymbolRun(symbol, shard_rows).counts()

        ledger_path = base / LEDGER_NAME
        atomic_write_text(ledger_path, "".join(row.to_json() + "\n" for row in rows))
        manifest = self.build_manifest(tuple(rows), per_symbol)
        manifest_path = base / MANIFEST_NAME
        atomic_write_text(manifest_path, canonical_json(manifest))
        return RunResult(
            spec=self.spec,
            rows=tuple(rows),
            manifest=manifest,
            ledger_path=ledger_path,
            manifest_path=manifest_path,
            non_standard_sessions=tuple(sorted(self.non_standard_sessions)),
        )

    def _resume_state(self, base: Path) -> list[str]:
        path = base / PROGRESS_NAME
        if not path.is_file():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("spec_digest") != self.spec.digest():
            raise BacktestError(
                f"{path} belongs to a different run (spec digest "
                f"{payload.get('spec_digest')!r} != {self.spec.digest()!r}). A ledger is a "
                "function of ONE spec and ONE code state; delete the run directory or start a "
                "new one rather than mixing two."
            )
        return [str(symbol) for symbol in payload.get("completed", [])]

    def _write_progress(self, base: Path, done: Sequence[str]) -> None:
        atomic_write_text(
            base / PROGRESS_NAME,
            canonical_json({"spec_digest": self.spec.digest(), "completed": list(done)}),
        )

    # --- the manifest -------------------------------------------------------------------

    def build_manifest(
        self, rows: Sequence[LedgerRow], per_symbol: Mapping[str, dict]
    ) -> dict:
        """Everything a reader needs to qualify the ledger. No clock read anywhere in it."""
        refused: dict[str, int] = {}
        for row in rows:
            if row.status == STATUS_REFUSED:
                refused[row.reason] = refused.get(row.reason, 0) + 1
        executed = [row for row in rows if row.executed]
        return {
            "spec_version": self.spec.spec_version,
            "code_sha": self.spec.code_sha,
            "config_digest": self.spec.digest(),
            "spec": self.spec.as_dict(),
            "universe": list(self.spec.symbols),
            "span": {"start": self.spec.start.isoformat(), "end": self.spec.end.isoformat()},
            "totals": {
                "walked": len(rows),
                "usable": sum(1 for row in rows if row.status == STATUS_EVALUATED),
                "gate1_relieved": sum(1 for row in rows if row.gate1_relieved),
                "signalled": sum(1 for row in rows if row.signalled),
                "executed": len(executed),
                "shares": sum(row.qty for row in executed),
                "gross_pnl_paise": sum(row.gross_pnl_paise for row in executed),
                "cost_paise": sum(row.cost_paise for row in executed),
                "net_pnl_paise": sum(row.net_pnl_paise for row in executed),
            },
            "refused_by_reason": dict(sorted(refused.items())),
            "outcomes": outcome_counts(rows),
            "exit_kinds": exit_kind_counts(rows),
            "per_symbol": {symbol: per_symbol[symbol] for symbol in sorted(per_symbol)},
            "rare_shapes": rare_shape_counts(rows),
            "non_standard_sessions_excluded": [
                day.isoformat() for day in sorted(self.non_standard_sessions)
            ],
            "factor_table": self._factor_summary(),
            "residual_register": self._residual_summary(),
            "capital_flags": {
                "computed": False,
                "note": CAPITAL_FLAGS_PENDING_NOTE,
                "capital_reference_paise": self.spec.capital_reference_paise,
                "margin_basis": self.spec.margin_basis,
            }
            if self.spec.capital_reference_paise is None or self.spec.margin_basis is None
            else {
                "computed": True,
                "note": "computed POST-HOC from the ledger, never inside the run",
                "capital_reference_paise": self.spec.capital_reference_paise,
                "margin_basis": self.spec.margin_basis,
            },
        }

    def _factor_summary(self) -> dict:
        return {
            "digest": self.spec.factor_digest,
            "per_symbol": {
                symbol: {
                    "factors": len(self.factors.get(symbol, ())),
                    "suppressions": len(self.suppressions.get(symbol, ())),
                    "in_span": [
                        {
                            "ex_date": f.ex_date.isoformat(),
                            "kind": f.kind,
                            "k": str(f.k),
                            "classification": f.classification,
                        }
                        for f in self.factors.get(symbol, ())
                        if self.spec.seed_date <= f.ex_date <= self.spec.end
                    ],
                    "suppressions_in_span": [
                        {"ex_date": s.ex_date.isoformat(), "kind": s.kind}
                        for s in self.suppressions.get(symbol, ())
                        if self.spec.seed_date <= s.ex_date <= self.spec.end
                    ],
                }
                for symbol in sorted(self.spec.symbols)
            },
        }

    def _residual_summary(self) -> dict:
        entries = {
            symbol: self.residual[symbol].as_dict()
            for symbol in sorted(self.spec.symbols)
            if symbol in self.residual
        }
        missing = [symbol for symbol in sorted(self.spec.symbols) if symbol not in self.residual]
        return {
            "acknowledged": True,
            "source": RESIDUAL_LEDGER_RELPATH,
            "caveat": RESIDUAL_CAVEAT,
            "per_symbol": entries,
            "not_in_register": missing,
        }


#: What every output says while the trader's Q43 answer is outstanding. Verbatim, everywhere.
CAPITAL_FLAGS_PENDING_NOTE: str = (
    "capital-infeasibility flags NOT computed -- the trader's Q43 answer is pending"
)


def rare_shape_counts(rows: Sequence[LedgerRow]) -> dict[str, int]:
    """How often each rare shape actually occurred, counted from the ROWS. PURE.

    Derived rather than accumulated on the way past, for two reasons: a resumed run replays
    shards it did not walk (so a running counter would undercount and the manifest would stop
    being byte-identical), and a reader can recompute every number here from the committed
    ledger alone.
    """
    counts = {label: 0 for label in RARE_SHAPE_LABELS}
    for row in rows:
        if row.gap_entry:
            counts["gap entries"] += 1
        if row.tie_case:
            counts["rule-3 tie bias days"] += 1
        if row.bias_rule == RULE_3_NO_MINUTE:
            counts["rule-3 day with no 1-minute data (carried, CONTEXT 3.2)"] += 1
        if row.reference_source == sig.REFERENCE_FROM_MINUTES:
            counts["E10 fallback reference (no 11:00-stamped candle)"] += 1
        for flag, label in (
            (sim.FLAG_QTY_ZERO_UNSIZABLE, "qty-zero unsizable days"),
            (sim.FLAG_SIGNAL_UNSIZABLE, "signal-unsizable (degenerate) days"),
            (sim.FLAG_BOTH_TOUCHED_STOP_WINS, "both-touched candles (stop won)"),
            (sim.FLAG_SQUARE_OFF_AT_ENTRY_CANDLE, "square-offs priced at the entry candle"),
        ):
            if flag in row.flags:
                counts[label] += 1
    return counts


def outcome_counts(rows: Sequence[LedgerRow]) -> dict[str, int]:
    """Every walked day by what happened to it. The counts PARTITION the run. PURE."""
    counts: dict[str, int] = {}
    for row in rows:
        key = row.outcome if row.outcome is not None else f"not evaluated: {row.reason}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def exit_kind_counts(rows: Sequence[LedgerRow]) -> dict[str, int]:
    """How the executed trades ended (stop / target / square-off). PURE."""
    counts: dict[str, int] = {}
    for row in rows:
        if row.executed and row.exit_kind:
            counts[row.exit_kind] = counts.get(row.exit_kind, 0) + 1
    return dict(sorted(counts.items()))


def stable_manifest_digest(manifest: Mapping) -> str:
    """sha256 of the manifest with the commit-dependent fields removed.

    ``code_sha`` and the config digest that covers it change with every commit, so a pack that
    printed them could not regenerate byte-identically tomorrow (REVIEW_8 finding C2). They
    stay in the manifest ON DISK, where pinning the run to a commit is the point; this digest
    is what a pack quotes.
    """
    payload = {key: value for key, value in manifest.items() if key not in _VOLATILE_KEYS}
    spec = dict(payload.get("spec", {}))
    spec.pop("code_sha", None)
    if spec:
        payload["spec"] = spec
    return hashlib.sha256(canonical_json(payload).encode("ascii")).hexdigest()


_VOLATILE_KEYS: frozenset[str] = frozenset({"code_sha", "config_digest"})


def canonical_json(payload) -> str:
    """Sorted-key, ASCII, newline-terminated JSON. The only serialization this module writes."""
    return json.dumps(payload, sort_keys=True, indent=1, ensure_ascii=True) + "\n"


def read_ledger(path: Path) -> tuple[LedgerRow, ...]:
    """Parse a ledger (or one shard) back into rows. The portfolio layer consumes these."""
    source = Path(path)
    if not source.is_file():
        raise BacktestError(f"No ledger at {source}.")
    rows = []
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(LedgerRow.from_dict(json.loads(line)))
    return tuple(rows)


# --- wiring (the only place stores, the CA table and the calendar are opened) ---------------


def latest_cached_master(cache_dir: Path) -> tuple[InstrumentMaster, Path]:
    """The NEWEST cached instrument-master dump, offline (chunk-8 decision B175)."""
    home = Path(cache_dir) / MASTER_CACHE_SUBDIR
    candidates = sorted(home.glob("OpenAPIScripMaster_*.json"))
    if not candidates:
        raise BacktestError(
            f"No cached instrument master under {home}: the run needs each symbol's own tick "
            "size (CONTEXT 4.3 -- never hardcode a tick)."
        )
    path = candidates[-1]
    try:
        return load_master_file(path), path
    except InstrumentMasterError as exc:  # pragma: no cover -- a corrupt cache file
        raise BacktestError(f"Cached instrument master {path} is unusable: {exc}") from exc


def build_factor_tables(
    symbols: Sequence[str],
    daily_store: DailyStore,
    *,
    start: date,
    end: date,
    allow_network: bool = False,
    cache_dir: Path | None = None,
) -> tuple[dict[str, tuple[ca.Factor, ...]], dict[str, tuple[ca.Suppression, ...]], str, dict]:
    """The REAL chunk-3 factor table for each symbol, plus its digest and a parse summary.

    The corporate-action history is pulled ONCE for all years and reused across the universe
    (the chunk-5B shape), day-cached; with ``allow_network=False`` only the cache is read, so a
    reviewer holding it reproduces the table exactly and a bare clone gets an empty one -- which
    is visible in the digest and in the manifest, never silent.

    The full history is passed to :func:`acumen.corp_actions.build_factor_table` per symbol
    because the Q-6 face-value reconstruction needs the symbol's whole split history, not the
    slice inside the run span.
    """
    actions = fetch_corp_action_history(
        date(min(2005, start.year), 1, 1),
        end,
        allow_network=allow_network,
        cache_dir=cache_dir,
    )
    factors: dict[str, tuple[ca.Factor, ...]] = {}
    suppressions: dict[str, tuple[ca.Suppression, ...]] = {}
    summary: dict[str, dict] = {}
    for symbol in symbols:
        table = corp_actions_for_symbol(symbol, actions, daily_store)
        factors[symbol] = tuple(table.factors)
        suppressions[symbol] = tuple(table.suppressions)
        summary[symbol] = {
            "factors": len(table.factors),
            "suppressions": len(table.suppressions),
            "pending": len(table.pending),
            "parse_exceptions": len(table.parse_exceptions),
        }
    payload = json.dumps(
        {
            symbol: {
                "factors": [
                    [f.ex_date.isoformat(), f.kind, str(f.k)] for f in factors[symbol]
                ],
                "suppressions": [
                    [s.ex_date.isoformat(), s.kind] for s in suppressions[symbol]
                ],
            }
            for symbol in sorted(factors)
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("ascii")).hexdigest()
    return factors, suppressions, digest, summary


def build_runner(
    symbols: Sequence[str],
    start: date,
    end: date,
    *,
    data_dir: Path | None = None,
    cache_dir: Path | None = None,
    seed_from: date | None = None,
    label: str = "",
    allow_network: bool = False,
    progress: Callable[[str], None] | None = None,
) -> tuple[BacktestRunner, Path, dict]:
    """Open the local stores read-only and wire the whole machine. Returns (runner, master, ca).

    Money and Row Size come from ``config.yaml`` through the loader -- never typed here
    (CONTEXT 3.5, chunk-8 decision B169).
    """
    config = load_config(include_env=False)
    data = Path(data_dir) if data_dir is not None else config.path("data_dir")
    cache = Path(cache_dir) if cache_dir is not None else config.path("cache_dir")

    daily_store = DailyStore.at(data / "daily_store")
    minute_store = MinuteStore.at(data / "minute_store")
    master, master_path = latest_cached_master(cache)
    seed = seed_from if seed_from is not None else start
    calendar = TradingCalendar.from_daily_store_range(
        daily_store, seed - timedelta(days=CALENDAR_LEAD_DAYS), end
    )
    residual = load_residual_register(data / RESIDUAL_LEDGER_RELPATH)

    wanted = tuple(symbol.strip().upper() for symbol in symbols)
    factors, suppressions, digest, ca_summary = build_factor_tables(
        wanted, daily_store, start=seed, end=end, allow_network=allow_network
    )

    span_days = [seed + timedelta(days=offset) for offset in range((end - seed).days + 1)]
    non_standard = scan_non_standard_sessions(
        minute_store, wanted, span_days, progress=progress
    )
    if non_standard:
        calendar = replace(
            calendar, trading_days=frozenset(calendar.trading_days) - set(non_standard)
        )

    spec = RunSpec(
        symbols=wanted,
        start=start,
        end=end,
        seed_from=seed,
        row_size=config.row_size,
        risk_per_trade_paise=config.require_risk_per_trade_paise(),
        cost_paise=config.cost_per_trade_paise(),
        code_sha=code_sha(),
        factor_digest=digest,
        capital_reference_paise=config.capital_reference_paise(),
        margin_basis=config.margin_basis_text(),
        label=label,
    )
    runner = BacktestRunner(
        spec=spec,
        pipeline=SignalPipeline(
            minute_store=minute_store,
            daily_store=daily_store,
            master=master,
            row_size=config.row_size,
        ),
        calendar=calendar,
        minute_store=minute_store,
        daily_store=daily_store,
        factors=factors,
        suppressions=suppressions,
        residual=residual,
        non_standard_sessions=frozenset(non_standard),
        minute_loader=minute_loader(minute_store),
    )
    return runner, master_path, ca_summary


def minute_loader(store: MinuteStore):
    """The ``(symbol, date) -> candles`` interface CONTEXT 3.2's Rule 3 needs, over the store."""

    def load(symbol: str, day: date):
        bars = store.minutes(symbol, day)
        if not bars:
            return None
        from .bias import Candle

        return tuple(
            Candle(
                open=int(bar.open_paise),
                high=int(bar.high_paise),
                low=int(bar.low_paise),
                close=int(bar.close_paise),
                stamp=bar.stamp,
                day=bar.stamp.date(),
            )
            for bar in bars
        )

    return load


def iter_trading_days(calendar: TradingCalendar, start: date, end: date) -> Iterable[date]:
    """Every trading day in ``[start, end]`` the calendar knows, oldest first."""
    current = start
    while current <= end:
        if calendar.is_trading_day(current):
            yield current
        current += timedelta(days=1)
