"""Chunk-9A evidence: run the pilot through the RUNNER and write the pack. I/O allowed here.

CLAUDE.md's evidence rule (REVIEW_7 finding C3): a session making claims from real store data
commits the GENERATING SCRIPT and its OUTPUT under ``docs/evidence/``. This module is that
generator; ``docs/evidence/chunk9a_pilot.py`` is the launcher and
``docs/evidence/chunk9a_pilot.md`` is its committed output, which must regenerate BYTE-IDENTICAL
from this code over the same stores (REVIEW_8 finding C2 -- no hand edits, ever).

**The four proofs the pack carries.**

1. **Reconciliation.** The chunk-8 window (5 symbols, 2026-05-01..2026-07-24) re-run through
   the chunk-9 runner WITH THE REAL chunk-3 factor table must reproduce the committed chunk-8
   pack to the paisa. The real table must change NOTHING in this window, and the pack proves
   why by listing every corporate action inside it.
2. **A real corporate action, walked by hand.** RELIANCE's 1:1 bonus (ex 2024-10-28) is a
   settled symbol's share-count event inside the minute era. The one bias pair the factor
   touches is walked digit by digit, adjusted and unadjusted, beside the runner's own answer.
   A second walk (HDFCBANK's 2019 face-value split) shows a pair where the adjustment REVERSES
   the bias, and a universe-wide scan measures how often that happens.
3. **Resume and determinism.** A run killed mid-way, resumed, reproduces the uninterrupted
   run's ledger byte for byte.
4. **The portfolio layer**, on the pilot ledger: the equity curve, CONTEXT 7-E13's metrics,
   CONTEXT 3.5's take-all disclosures, and the capital-infeasibility flags NOT computed while
   the trader's Q43 answer is pending.

Read-only and offline apart from the corporate-action day-cache, which is read (never fetched)
by default.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Sequence

from . import backtest as bt
from . import bias as bias_engine
from . import corp_actions as ca
from . import portfolio as pf
from . import signals as sig
from .bias import Candle
from .bias_engine import DailyBias
from .calendar import TradingCalendar
from .config import load_config
from .daily_store import DailyStore
from .minute_backfill import corp_actions_for_symbol, fetch_corp_action_history

#: Pilot (a): the chunk-7 / chunk-8 window, unchanged, so the three packs are line-comparable.
PILOT_SYMBOLS: tuple[str, ...] = ("TCS", "RELIANCE", "HDFCBANK", "ICICIBANK", "BHARTIARTL")
PILOT_START: date = date(2026, 5, 1)
PILOT_END: date = date(2026, 7, 24)

#: The committed chunk-8 pack's own totals (docs/evidence/chunk8_sweep.md). The pilot must
#: reproduce every one of them THROUGH THE RUNNER and with the REAL factor table wired.
CHUNK8_PACK: dict[str, int] = {
    "walked": 290,
    "entered": 146,
    "armed_no_cross": 88,
    "never_armed": 56,
    "executed": 146,
    "shares": 53_750,
    "gross_paise": 1_266_505,
    "cost_paise": 1_460_000,
    "net_paise": -193_495,
    "winners": 45,
    "losers": 101,
    "flat": 0,
    "gross_profit_paise": 10_109_920,
    "gross_loss_paise": -8_843_415,
    "exit_stop": 86,
    "exit_square_off": 36,
    "exit_target": 24,
}

#: Pilot (b1): a settled symbol's 1:1 BONUS inside the minute era, with full minute coverage --
#: and the window also carries NSE's Muhurat session (2024-11-01), a real CONTEXT 7-E2 case.
CROSS_CA_SYMBOL: str = "RELIANCE"
CROSS_CA_EX_DATE: date = date(2024, 10, 28)
CROSS_CA_START: date = date(2024, 10, 20)
CROSS_CA_END: date = date(2024, 11, 8)

#: Pilot (b2): a face-value SPLIT whose adjustment REVERSES the bias of the pair it touches.
FLIP_CA_SYMBOL: str = "HDFCBANK"
FLIP_CA_EX_DATE: date = date(2019, 9, 19)
FLIP_CA_START: date = date(2019, 9, 12)
FLIP_CA_END: date = date(2019, 9, 27)

#: The demerger window: CONTEXT 3.2 suppresses the pair across the ex-date -- counted no-trades.
DEMERGER_SYMBOL: str = "RELIANCE"
DEMERGER_EX_DATE: date = date(2023, 7, 20)
DEMERGER_START: date = date(2023, 7, 17)
DEMERGER_END: date = date(2023, 7, 28)

#: The universe-wide materiality scan: every share-count event on a SETTLED symbol inside the
#: minute era, one affected bias pair each.
SCAN_START: date = date(2016, 10, 1)

DEFAULT_OUT: str = "docs/evidence/chunk9a_pilot.md"
RUN_ROOT: str = "backtests"


class PilotError(RuntimeError):
    """The pilot cannot assemble its inputs from the local stores."""


# --- the bias walk (the digit-by-digit evidence) ----------------------------------------------


@dataclass(frozen=True)
class BiasWalk:
    """One CONTEXT 3.2 pair, walked by hand: raw, adjusted, and the rule each one fires."""

    symbol: str
    trade_day: date
    current_day: date
    previous_day: date
    previous_raw: Candle
    previous_adjusted: Candle
    current: Candle
    factors: tuple[ca.Factor, ...]
    adjusted_bias: str | None
    adjusted_rule: str
    adjusted_detail: str
    unadjusted_bias: str | None
    unadjusted_rule: str
    unadjusted_detail: str
    runner_bias: str | None
    runner_rule: str | None

    @property
    def bias_changed(self) -> bool:
        return self.adjusted_bias != self.unadjusted_bias

    @property
    def rule_changed(self) -> bool:
        return self.adjusted_rule != self.unadjusted_rule


def candle_at(store: DailyStore, symbol: str, day: date) -> Candle:
    frame = store.daily(symbol, day, day)
    if frame.empty:
        raise PilotError(f"{symbol}: no daily row for {day}")
    row = frame.iloc[0]
    return Candle(
        open=int(row["open_paise"]),
        high=int(row["high_paise"]),
        low=int(row["low_paise"]),
        close=int(row["close_paise"]),
        day=day,
    )


def walk_pair(
    store: DailyStore,
    calendar: TradingCalendar,
    symbol: str,
    trade_day: date,
    factors: Sequence[ca.Factor],
    *,
    minute_loader=None,
    carry: str | None = None,
    runner_bias: DailyBias | None = None,
) -> BiasWalk:
    """Evaluate ONE bias pair twice -- with the factor table and without it. PURE-ish (reads).

    Nothing here calls the bias ORCHESTRATION: the pair is assembled from the calendar, the
    adjustment is :func:`acumen.corp_actions.adjust_pair` applied exactly as CONTEXT 3.2 states
    it, and the rule is :func:`acumen.bias.evaluate_pair`. The runner's own answer is carried
    beside it so the pack can show the two agree rather than assert it.
    """
    pair = calendar.bias_pair(trade_day)
    previous_raw = candle_at(store, symbol, pair.previous)
    current = candle_at(store, symbol, pair.current)
    between = ca.factors_between(factors, pair.previous, pair.current, symbol=symbol)
    adjusted = Candle(
        open=ca.adjust_pair(previous_raw.open, between),
        high=ca.adjust_pair(previous_raw.high, between),
        low=ca.adjust_pair(previous_raw.low, between),
        close=ca.adjust_pair(previous_raw.close, between),
        day=previous_raw.day,
    )

    def provider():
        return None if minute_loader is None else minute_loader(symbol, pair.current)

    with_ca = bias_engine.evaluate_pair(adjusted, current, provider, carry)
    without = bias_engine.evaluate_pair(previous_raw, current, provider, carry)
    return BiasWalk(
        symbol=symbol,
        trade_day=trade_day,
        current_day=pair.current,
        previous_day=pair.previous,
        previous_raw=previous_raw,
        previous_adjusted=adjusted,
        current=current,
        factors=tuple(between),
        adjusted_bias=with_ca.bias,
        adjusted_rule=with_ca.rule,
        adjusted_detail=with_ca.detail,
        unadjusted_bias=without.bias,
        unadjusted_rule=without.rule,
        unadjusted_detail=without.detail,
        runner_bias=None if runner_bias is None else runner_bias.bias,
        runner_rule=None if runner_bias is None else runner_bias.rule,
    )


# --- the universe-wide materiality scan --------------------------------------------------------


@dataclass(frozen=True)
class ScanRow:
    symbol: str
    ex_date: date
    kind: str
    k: str
    trade_day: date
    adjusted_bias: str | None
    unadjusted_bias: str | None


@dataclass(frozen=True)
class ScanResult:
    events: int
    pairs: int
    bias_changed: int
    rows: tuple[ScanRow, ...]
    symbols_scanned: int
    end: date


def scan_share_count_events(
    store: DailyStore,
    calendar: TradingCalendar,
    register: dict,
    actions: Sequence[ca.CorporateAction],
    *,
    end: date,
    minute_loader=None,
    progress=None,
) -> ScanResult:
    """How often does the pairwise adjustment CHANGE the bias, on REAL events? Read-only.

    Every bonus / split on a SETTLED symbol with an ex-date inside the minute era touches
    exactly ONE bias pair -- the trade day whose D-1 IS the ex-date (for the next day the pair
    is (ex+1, ex) and the factor's ex-date is no longer strictly after P). That pair is
    evaluated both ways. This is the measurement behind "wire the real table": it says what the
    empty table would have cost, in bias days, over the whole settled universe.
    """
    settled = sorted(
        symbol for symbol, entry in register.items() if entry.status == "settled"
    )
    rows: list[ScanRow] = []
    events = pairs = changed = 0
    for symbol in settled:
        table = corp_actions_for_symbol(symbol, actions, store)
        share_count = [
            factor
            for factor in table.factors
            if factor.kind in (ca.KIND_BONUS, ca.KIND_SPLIT)
            and SCAN_START <= factor.ex_date <= end
            and factor.k != 1
        ]
        if not share_count:
            continue
        if progress is not None:
            progress(f"  scan: {symbol} ({len(share_count)} share-count event(s))")
        for factor in share_count:
            events += 1
            trade_day = _next_trading_day(calendar, factor.ex_date, end)
            if trade_day is None:
                continue
            try:
                pair = calendar.bias_pair(trade_day)
            except Exception:  # noqa: BLE001 -- an unreachable pair is simply not walked
                continue
            if pair.current != factor.ex_date:
                continue
            with_table, without_table = _bias_both_ways(
                store, calendar, symbol, trade_day, table, minute_loader=minute_loader
            )
            if with_table is None or without_table is None:
                continue
            pairs += 1
            if with_table != without_table:
                changed += 1
            rows.append(
                ScanRow(
                    symbol=symbol,
                    ex_date=factor.ex_date,
                    kind=factor.kind,
                    k=_k_text(factor.k),
                    trade_day=trade_day,
                    adjusted_bias=with_table,
                    unadjusted_bias=without_table,
                )
            )
    return ScanResult(
        events=events,
        pairs=pairs,
        bias_changed=changed,
        rows=tuple(rows),
        symbols_scanned=len(settled),
        end=end,
    )


#: How far back the scan seeds each bias carry, so both readings answer with a REAL bias
#: rather than with "no rule fired here". CONTEXT 3.2's carry is path dependent, so the two
#: readings are each given the same run-up and each carries its own answer forward.
SCAN_SEED_DAYS: int = 40


def _bias_both_ways(
    store: DailyStore,
    calendar: TradingCalendar,
    symbol: str,
    trade_day: date,
    table,
    *,
    minute_loader=None,
) -> tuple[str | None, str | None]:
    """``(bias with the real factor table, bias with an empty one)`` for one trade day.

    Both are produced by the ORCHESTRATION, seeded the same number of days back, so each
    reading carries its own bias forward exactly as a run would. Comparing two engine answers
    is the honest measurement; comparing two isolated pairs would count "this pair fires no
    rule" as a change when the run would simply have carried.
    """
    from .bias_engine import BiasEngine

    seed = trade_day - timedelta(days=SCAN_SEED_DAYS)
    with_table = BiasEngine(
        store=store,
        calendar=calendar,
        factors=tuple(table.factors),
        suppressions=tuple(table.suppressions),
        minute_loader=minute_loader,
    )
    without_table = BiasEngine(store=store, calendar=calendar, minute_loader=minute_loader)
    try:
        adjusted = with_table.bias_for_day(symbol, trade_day, seed_from=seed)
        naked = without_table.bias_for_day(symbol, trade_day, seed_from=seed)
    except Exception:  # noqa: BLE001 -- an unreachable pair is simply not counted
        return (None, None)
    return (adjusted.bias, naked.bias)


def _next_trading_day(calendar: TradingCalendar, after: date, end: date) -> date | None:
    day = after + timedelta(days=1)
    while day <= end:
        try:
            if calendar.is_trading_day(day):
                return day
        except Exception:  # noqa: BLE001 -- outside the derived calendar
            return None
        day += timedelta(days=1)
    return None


def _k_text(k: Decimal) -> str:
    """A factor as an exact short string: 0.5, 0.2, or 2/3 printed to 10 places."""
    text = format(k.normalize(), "f")
    return text if len(text) <= 12 else format(k, ".10f")


# --- the pilot runs -----------------------------------------------------------------------------


@dataclass(frozen=True)
class PilotRun:
    """One window driven through the runner, with everything the pack prints about it."""

    label: str
    result: bt.RunResult
    ledger_sha: str
    manifest_sha: str


def run_window(
    symbols: Sequence[str],
    start: date,
    end: date,
    *,
    label: str,
    data_dir: Path | None = None,
    fresh: bool = True,
    progress=None,
    run_name: str | None = None,
) -> tuple[PilotRun, bt.BacktestRunner]:
    """Wire the machine and walk one window, into a fresh run directory under ``<data_root>/``.

    ``run_name`` names the DIRECTORY when it must differ from the label; the label is part of
    the spec, so two runs that are meant to produce identical manifests must share it.
    """
    runner, _master, _ca = bt.build_runner(
        symbols, start, end, data_dir=data_dir, label=label
    )
    config = load_config(include_env=False)
    root = (Path(data_dir) if data_dir is not None else config.path("data_root")) / RUN_ROOT
    run_dir = root / (run_name or label)
    if fresh and run_dir.exists():
        shutil.rmtree(run_dir)
    result = runner.run(run_dir, progress=progress)
    return (
        PilotRun(
            label=label,
            result=result,
            ledger_sha=_sha(result.ledger_path),
            manifest_sha=bt.stable_manifest_digest(result.manifest),
        ),
        runner,
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class ResumeProof:
    """The chunk-9A resume test: kill mid-run, resume, compare bytes."""

    whole_sha: str
    resumed_sha: str
    manifest_whole: str
    manifest_resumed: str
    killed_after: str
    shards_before_resume: tuple[str, ...]
    rows_whole: int
    rows_resumed: int
    duplicate_keys: int

    @property
    def identical(self) -> bool:
        return (
            self.whole_sha == self.resumed_sha
            and self.manifest_whole == self.manifest_resumed
            and self.duplicate_keys == 0
            and self.rows_whole == self.rows_resumed
        )


def resume_proof(
    symbols: Sequence[str],
    start: date,
    end: date,
    *,
    data_dir: Path | None = None,
    kill_after: str,
    progress=None,
) -> ResumeProof:
    """Run the window whole; run it again killing after ``kill_after``; resume; diff the bytes."""

    class _Interrupt(RuntimeError):
        pass

    # BOTH runs carry the SAME label, so they are the same spec and their manifests must come
    # out byte-identical; only the directory differs.
    whole, _ = run_window(
        symbols,
        start,
        end,
        label="chunk9a_resume",
        run_name="chunk9a_resume_whole",
        data_dir=data_dir,
        progress=progress,
    )

    config = load_config(include_env=False)
    root = (Path(data_dir) if data_dir is not None else config.path("data_root")) / RUN_ROOT
    run_dir = root / "chunk9a_resume_killed"
    if run_dir.exists():
        shutil.rmtree(run_dir)

    runner, _master, _ca = bt.build_runner(
        symbols, start, end, data_dir=data_dir, label="chunk9a_resume"
    )

    def kill(symbol: str) -> None:
        if symbol == kill_after:
            raise _Interrupt(symbol)

    try:
        runner.run(run_dir, after_symbol=kill)
    except _Interrupt:
        pass
    else:  # pragma: no cover -- the kill symbol is always in the universe
        raise PilotError("the interrupted run did not stop")
    shards = tuple(
        sorted(path.name for path in (run_dir / bt.SHARD_DIRNAME).glob("*.jsonl"))
    )

    resumed_runner, _master, _ca = bt.build_runner(
        symbols, start, end, data_dir=data_dir, label="chunk9a_resume"
    )
    resumed = resumed_runner.run(run_dir, progress=progress)

    keys = [(row.symbol, row.day) for row in resumed.rows]
    return ResumeProof(
        whole_sha=whole.ledger_sha,
        resumed_sha=_sha(resumed.ledger_path),
        manifest_whole=whole.manifest_sha,
        manifest_resumed=bt.stable_manifest_digest(resumed.manifest),
        killed_after=kill_after,
        shards_before_resume=shards,
        rows_whole=len(whole.result.rows),
        rows_resumed=len(resumed.rows),
        duplicate_keys=len(keys) - len(set(keys)),
    )


# --- reconciliation against the chunk-8 pack ----------------------------------------------------


#: How each reconciled figure is printed in the pack.
RECONCILIATION_LABELS: dict[str, str] = {
    "walked": "Stock-days walked",
    "entered": "Days that entered",
    "armed_no_cross": "Days armed with no qualifying close",
    "never_armed": "Days never armed",
    "executed": "Executed trades",
    "shares": "Shares transacted",
    "gross_paise": "Gross PnL (chunk-8 basis, before Rs 100/trade costs)",
    "cost_paise": "Costs paid",
    "net_paise": "Net PnL",
    "winners": "Winners (net)",
    "losers": "Losers (net)",
    "flat": "Flat (net)",
    "gross_profit_paise": "Gross profit (chunk-8 basis, before Rs 100/trade costs)",
    "gross_loss_paise": "Gross loss (chunk-8 basis, before Rs 100/trade costs)",
    "exit_stop": "Exit: stop-loss-hit",
    "exit_square_off": "Exit: square-off-at-the-15:15-close",
    "exit_target": "Exit: target-hit",
}


def reconciliation(rows: Sequence[bt.LedgerRow]) -> list[tuple[str, int, int, bool]]:
    """(label, chunk-8's number, this run's number, equal) for every figure the pack pins."""
    executed = [row for row in rows if row.executed]
    outcomes = bt.outcome_counts(rows)
    exits = bt.exit_kind_counts(rows)
    measured = {
        "walked": len(rows),
        "entered": outcomes.get(sig.OUTCOME_ENTERED, 0),
        "armed_no_cross": outcomes.get(sig.OUTCOME_ARMED_NO_CROSS, 0),
        "never_armed": outcomes.get(sig.OUTCOME_NEVER_ARMED, 0),
        "executed": len(executed),
        "shares": sum(row.qty for row in executed),
        "gross_paise": sum(row.gross_pnl_paise for row in executed),
        "cost_paise": sum(row.cost_paise for row in executed),
        "net_paise": sum(row.net_pnl_paise for row in executed),
        "winners": sum(1 for row in executed if row.net_pnl_paise > 0),
        "losers": sum(1 for row in executed if row.net_pnl_paise < 0),
        "flat": sum(1 for row in executed if row.net_pnl_paise == 0),
        "gross_profit_paise": sum(
            row.gross_pnl_paise for row in executed if row.gross_pnl_paise > 0
        ),
        "gross_loss_paise": sum(
            row.gross_pnl_paise for row in executed if row.gross_pnl_paise < 0
        ),
        "exit_stop": exits.get(sig.EXIT_STOP, 0),
        "exit_square_off": exits.get(sig.EXIT_SQUARE_OFF, 0),
        "exit_target": exits.get(sig.EXIT_TARGET, 0),
    }
    return [
        (label, CHUNK8_PACK[label], measured[label], CHUNK8_PACK[label] == measured[label])
        for label in CHUNK8_PACK
    ]


def in_window_events(
    runner: bt.BacktestRunner,
) -> list[tuple[str, str, str, str, str]]:
    """Every corporate action inside the pilot window, with the k it produced."""
    rows = []
    for symbol in runner.spec.symbols:
        for factor in runner.factors.get(symbol, ()):
            if runner.spec.seed_date <= factor.ex_date <= runner.spec.end:
                rows.append(
                    (
                        symbol,
                        factor.ex_date.isoformat(),
                        factor.kind,
                        _k_text(factor.k),
                        factor.basis,
                    )
                )
        for supp in runner.suppressions.get(symbol, ()):
            if runner.spec.seed_date <= supp.ex_date <= runner.spec.end:
                rows.append(
                    (symbol, supp.ex_date.isoformat(), supp.kind, "suppressed", supp.reason)
                )
    return sorted(rows)


# --- rendering ---------------------------------------------------------------------------------


def _money(paise) -> str:
    return pf.format_paise(paise)


def _price(paise: int | None) -> str:
    return "-" if paise is None else pf.format_paise(paise)[3:]


def _poc(row: bt.LedgerRow) -> str:
    if row.poc_half_paise is None:
        return "-"
    whole, half = divmod(row.poc_half_paise, 2)
    return _price(whole) + ("5" if half else "")


def _candle_row(label: str, candle: Candle) -> str:
    return (
        f"| {label} | {_price(candle.open)} | {_price(candle.high)} | "
        f"{_price(candle.low)} | {_price(candle.close)} |"
    )


def render_bias_walk(walk: BiasWalk, *, title: str, note: str) -> list[str]:
    """The digit-by-digit table: raw P, the factor, adjusted P, C, and both verdicts."""
    body_max_adj = max(walk.previous_adjusted.open, walk.previous_adjusted.close)
    body_min_adj = min(walk.previous_adjusted.open, walk.previous_adjusted.close)
    body_max_raw = max(walk.previous_raw.open, walk.previous_raw.close)
    body_min_raw = min(walk.previous_raw.open, walk.previous_raw.close)
    lines = [
        f"### {title}",
        "",
        note,
        "",
        f"Trade day **D = {walk.trade_day}**; CONTEXT 3.2's pair is C = candle({walk.current_day}) "
        f"and P = candle({walk.previous_day}).",
        "",
        "| candle | open | high | low | close |",
        "|---|---|---|---|---|",
        _candle_row(f"P raw ({walk.previous_day})", walk.previous_raw),
        _candle_row(f"P in C's scale ({walk.previous_day})", walk.previous_adjusted),
        _candle_row(f"C ({walk.current_day})", walk.current),
        "",
        "**The factors applied to P** (CONTEXT 3.2: events with ex-date strictly after P and on "
        "or before C):",
        "",
    ]
    if walk.factors:
        lines += [
            "| ex-date | kind | k | basis |",
            "|---|---|---|---|",
        ]
        for factor in walk.factors:
            lines.append(
                f"| {factor.ex_date} | {factor.kind} | {_k_text(factor.k)} | {factor.basis} |"
            )
        lines.append("")
        lines.append("Digit by digit, each of P's four prices x k, rounded ONCE half-even to paise:")
        lines.append("")
        lines.append("| price | raw paise | x k | adjusted paise | adjusted rupees |")
        lines.append("|---|---|---|---|---|")
        for name, raw, adjusted in (
            ("open", walk.previous_raw.open, walk.previous_adjusted.open),
            ("high", walk.previous_raw.high, walk.previous_adjusted.high),
            ("low", walk.previous_raw.low, walk.previous_adjusted.low),
            ("close", walk.previous_raw.close, walk.previous_adjusted.close),
        ):
            product = Decimal(raw)
            for factor in walk.factors:
                product *= factor.k
            lines.append(
                f"| {name} | {raw:,} | {product} | {adjusted:,} | {_price(adjusted)} |"
            )
    else:
        lines.append("None -- no corporate action falls in this pair's window.")
    lines += [
        "",
        "**The rule, evaluated on both readings** (CONTEXT 3.2's order: inside bar -> Rule 1 -> "
        "Rule 2 -> Rule 3 -> carry):",
        "",
        "| reading | P.high | P.low | bodyMax | bodyMin | C.high | C.low | C.close | rule | bias |",
        "|---|---|---|---|---|---|---|---|---|---|",
        (
            f"| **adjusted** | {_price(walk.previous_adjusted.high)} | "
            f"{_price(walk.previous_adjusted.low)} | {_price(body_max_adj)} | "
            f"{_price(body_min_adj)} | {_price(walk.current.high)} | {_price(walk.current.low)} | "
            f"{_price(walk.current.close)} | {walk.adjusted_rule} | "
            f"**{walk.adjusted_bias}** |"
        ),
        (
            f"| unadjusted (the defect) | {_price(walk.previous_raw.high)} | "
            f"{_price(walk.previous_raw.low)} | {_price(body_max_raw)} | "
            f"{_price(body_min_raw)} | {_price(walk.current.high)} | {_price(walk.current.low)} | "
            f"{_price(walk.current.close)} | {walk.unadjusted_rule} | "
            f"{walk.unadjusted_bias} |"
        ),
        "",
        f"* adjusted verdict: {walk.adjusted_detail}",
        f"* unadjusted verdict: {walk.unadjusted_detail}",
        f"* the adjustment changes the BIAS: **{'YES' if walk.bias_changed else 'no'}**; "
        f"changes the RULE: **{'YES' if walk.rule_changed else 'no'}**",
        f"* the RUNNER's own answer for {walk.trade_day}: bias **{walk.runner_bias}**, rule "
        f"`{walk.runner_rule}` -- "
        + (
            "identical to the hand walk above"
            if walk.runner_bias == walk.adjusted_bias and walk.runner_rule == walk.adjusted_rule
            else "DIFFERENT from the hand walk -- investigate before reading anything else"
        ),
        "",
    ]
    return lines


def ledger_table(rows: Sequence[bt.LedgerRow]) -> list[str]:
    lines = [
        "| day | status | bias | rule | side | POC | outcome | qty | exit | net |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.day} | {row.status} | {row.bias or '-'} | {row.bias_rule or '-'} | "
            f"{row.side or '-'} | {_poc(row)} | "
            f"{row.outcome or row.reason[:64]} | {row.qty or '-'} | "
            f"{row.exit_kind or '-'} | {_money(row.net_pnl_paise) if row.executed else '-'} |"
        )
    return lines


def metrics_table(label: str, metrics: pf.Metrics) -> list[str]:
    excursion = metrics.max_drawdown
    run_up = metrics.max_run_up
    return [
        f"| Net PnL | {_money(metrics.net_pnl_paise)} |",
        f"| Gross profit (net basis: the winners' net sum) | "
        f"{_money(metrics.gross_profit_paise)} |",
        f"| Gross loss (net basis: the losers' net sum) | "
        f"{_money(metrics.gross_loss_paise)} |",
        f"| Profit factor | {_ratio(metrics.profit_factor)} |",
        f"| Commission paid | {_money(metrics.commission_paise)} |",
        (
            "| Profit / loss BEFORE Rs 100/trade costs | "
            f"{_money(metrics.before_cost_profit_paise)} / "
            f"{_money(metrics.before_cost_loss_paise)} -- the only before-costs figures in "
            "section 7; the three labelled rows of section 3's cross-document reconciliation "
            "are the stated exception; every other number on this page is NET |"
        ),
        f"| Expected payoff (per trade) | {_money(metrics.expected_payoff_paise)} |",
        f"| Total trades / open trades | {metrics.total_trades} / {metrics.open_trades} |",
        (
            f"| Winners / losers / flat (by NET sign) | {metrics.winners} / "
            f"{metrics.losers} / {metrics.flat} |"
        ),
        f"| Percent profitable (net) | {pf.format_pct(metrics.percent_profitable)} |",
        f"| Avg PnL | {_money(metrics.avg_pnl_paise)} |",
        f"| Avg profit | {_money(metrics.avg_profit_paise)} |",
        f"| Avg loss | {_money(metrics.avg_loss_paise)} |",
        f"| Avg profit / avg loss | {_ratio(metrics.avg_profit_over_avg_loss)} |",
        (
            f"| Largest win | {_money(metrics.largest_win_paise)} "
            f"({pf.format_pct(metrics.largest_win_pct_of_notional)} of its own notional, "
            f"{pf.format_pct(metrics.largest_win_pct_of_gross_profit)} of gross profit) "
            "-- all three NET |"
        ),
        (
            f"| Largest loss | {_money(metrics.largest_loss_paise)} "
            f"({pf.format_pct(metrics.largest_loss_pct_of_notional)} of its own notional, "
            f"{pf.format_pct(metrics.largest_loss_pct_of_gross_loss)} of gross loss) "
            "-- all three NET; a loss over a loss is a POSITIVE share |"
        ),
        _outlier_line(metrics.outliers),
        (
            f"| Max drawdown (equity close-to-close) | {_money(excursion.amount_paise)} "
            f"({pf.format_pct(excursion.pct)}), {excursion.peak_day} -> {excursion.trough_day}, "
            f"{excursion.duration_days} observation(s), recovered "
            f"{excursion.recovered_on or 'never in the window'} |"
        ),
        (
            f"| Max run-up (equity close-to-close) | {_money(run_up.amount_paise)} "
            f"({pf.format_pct(run_up.pct)}), {run_up.trough_day or 'opening capital'} -> "
            f"{run_up.peak_day}, {run_up.duration_days} observation(s), given back "
            f"{run_up.recovered_on or 'never in the window'} |"
        ),
        _path_line("Max drawdown", metrics.intraday_max_drawdown, metrics),
        _path_line("Max run-up", metrics.intraday_max_run_up, metrics),
        f"| Return on initial capital | {pf.format_pct(metrics.return_on_initial_capital)} |",
        f"| CAGR | {_decimal_pct(metrics.cagr)} |",
        f"| Sharpe (daily, rf 0, x sqrt 252) | {_decimal(metrics.sharpe)} |",
        f"| Sortino (daily, rf 0, x sqrt 252) | {_decimal(metrics.sortino)} |",
        (
            f"| Avg MFE / avg MAE per trade | {_money(metrics.avg_mfe_paise)} / "
            f"{_money(metrics.avg_mae_paise)} -- **BEFORE COSTS**: an excursion is a PRICE "
            "move against the entry, so neither figure carries the Rs 100 round trip. The "
            "excursions bracket a trade's GROSS PnL, not its net |"
        ),
        (
            f"| Largest MFE / largest MAE | {_money(metrics.largest_mfe_paise)} / "
            f"{_money(metrics.largest_mae_paise)} -- **BEFORE COSTS**, on the same basis as "
            "the row above |"
        ),
        f"| Trading days in the series | {metrics.trading_days} |",
    ]


def _path_stamp(point: pf.PathPoint | None) -> str:
    """A path observation as ``YYYY-MM-DD HH:MM``, or what ``None`` means on that column."""
    if point is None:
        return "opening capital"
    if point.stamp is None:
        return f"{point.day} close"
    return point.stamp.strftime("%Y-%m-%d %H:%M")


def _path_line(label: str, excursion: pf.PathExcursion | None, metrics: pf.Metrics) -> str:
    """The intra-trade form of E13's drawdown/run-up, measured on the 15-minute path.

    Q-16(b) RULED (architect, 30-Jul-2026): the worst-case coincidence construction is retired.
    The ruling's single disclosed limit is printed with the figure, so nothing is implied.

    The two forms are MIRRORS and are described in mirrored words (REVIEW_9A_2 finding Q2). A
    drawdown's `recovered` field is the first later observation back at the peak it fell from;
    a run-up's is the first later observation back at the trough it rose from -- which is a
    GIVEBACK, not a recovery. The close-to-close rows one line above already say it that way,
    so printing "never recovered" on a run-up row described one quantity two ways on adjacent
    lines of the same table.
    """
    if excursion is None:
        return f"| {label} (intra-trade, 15-min path) | NOT COMPUTED -- {metrics.intraday_note} |"
    drawdown = label.startswith("Max drawdown")
    first, second = (
        (excursion.peak, excursion.trough) if drawdown else (excursion.trough, excursion.peak)
    )
    verb = "recovered" if drawdown else "given back"
    resolved = (
        f"{verb} {_path_stamp(excursion.recovered)}"
        if excursion.recovered is not None
        else f"{verb} never in the window"
    )
    return (
        f"| {label} (intra-trade, 15-min path) | {_money(excursion.amount_paise)} "
        f"({pf.format_pct(excursion.pct)}), {_path_stamp(first)} -> {_path_stamp(second)}, "
        f"{excursion.observations} observation(s) of {metrics.intraday_observations}, "
        f"{resolved}. LIMIT: {excursion.note} |"
    )


def _outlier_line(found: pf.Outliers) -> str:
    """E13's "outliers" under the Q-16(a) ruling: count, summed net, shares, and the RULE.

    The ruling requires the definition beside the number, and the fences are printed with it so
    a reader can re-derive the count from the trade list without rerunning anything.

    **ONE FORMAT ON BOTH BRANCHES** (architect's GO ruling, 31-Jul-2026, condition 3, closing
    REVIEW_9A_2 finding Q4). The zero case used to print "NONE of N ... " and omit three of the
    four quantities the ruling names, on the reasoning that three zeros are noise. They are not:
    a reader comparing this run's row against the next run's must see the same four fields in
    the same places, and on a fixed-rupee-risk strategy a zero count is a structural PROPERTY
    (every trade is bounded between -1R and +3R) rather than an empty result. So the branch is
    gone -- count, summed net, and both tails with their fences, amounts and shares are printed
    either way, with zeros printed as zeros.
    """
    return (
        f"| Outliers | **{found.count}** of {found.population} executed trades, summed net "
        f"{_money(found.net_paise)} -- {found.above_count} above "
        f"{_money(found.upper_fence_paise)} "
        f"({_money(found.above_net_paise)}, "
        f"{pf.format_pct(found.share_of_gross_profit)} of gross profit) and "
        f"{found.below_count} below {_money(found.lower_fence_paise)} "
        f"({_money(found.below_net_paise)}, "
        f"{pf.format_pct(found.share_of_gross_loss)} of gross loss). "
        f"Q1 {_money(found.q1_paise)}, Q3 {_money(found.q3_paise)}, "
        f"IQR {_money(found.iqr_paise)}. DEFINITION: {found.definition} |"
    )


def _ratio(value: Fraction | None) -> str:
    if value is None:
        return "-"
    return f"{Decimal(value.numerator) / Decimal(value.denominator):.4f}"


def _decimal(value: Decimal | None, places: str = "0.0001") -> str:
    return "-" if value is None else str(value.quantize(Decimal(places)))


def _decimal_pct(value: Decimal | None) -> str:
    return "-" if value is None else f"{(value * 100).quantize(Decimal('0.01'))}%"


def render_markdown(
    *,
    pilot: PilotRun,
    pilot_runner: bt.BacktestRunner,
    cross: PilotRun,
    cross_walk: BiasWalk,
    flip: PilotRun,
    flip_walk: BiasWalk,
    demerger: PilotRun,
    scan: ScanResult,
    resume: ResumeProof,
    benchmark: pf.Benchmark,
    master_name: str,
    initial_capital_paise: int,
    trade_paths: tuple[bt.TradePath, ...],
    command: str,
) -> str:
    rows = pilot.result.rows
    manifest = pilot.result.manifest
    metrics = pf.metrics(
        rows, initial_capital_paise=initial_capital_paise, paths=trade_paths
    )
    split = pf.side_split(
        rows, initial_capital_paise=initial_capital_paise, paths=trade_paths
    )
    symbols = pf.per_symbol(
        rows, initial_capital_paise=initial_capital_paise, paths=trade_paths
    )
    disclosures = pf.disclosures(rows)
    flags = pf.capital_flags(
        rows,
        capital_reference_paise=pilot_runner.spec.capital_reference_paise,
        margin_basis=None
        if pilot_runner.spec.margin_basis is None
        else Decimal(pilot_runner.spec.margin_basis),
    )

    out: list[str] = []
    add = out.append

    add("# chunk 9A evidence -- the backtest runner, proven on a pilot")
    add("")
    add(
        "Generated by `docs/evidence/chunk9a_pilot.py` (implementation: "
        "`src/acumen/pilot_evidence.py`), committed under CLAUDE.md's evidence rule "
        "(REVIEW_7 finding C3). Regenerate with:"
    )
    add("")
    add(f"    {command}")
    add("")
    add(
        "Every number below is produced by the committed code over the two local Parquet "
        "stores and the corporate-action day-cache. The file is written by the generator and "
        "never edited by hand (REVIEW_8 finding C2)."
    )
    add("")

    add("## 1. What this is, and what it is not")
    add("")
    add(
        "This is the chunk-9A **machine** -- the runner, the run ledger, the manifest and the "
        "portfolio layer -- exercised on a pilot. It is **not** a backtest result: the full "
        "history run and its report are chunk 9B, and they are gated on the trader's Round-4 "
        "answers. Nobody should read a strategy verdict into five symbols over three months."
    )
    add("")
    add("**Disclosures, first**")
    add("")
    add(
        "* **The REAL chunk-3 factor table is wired.** Chunk 8's sweep ran with an EMPTY factor "
        "table, which REVIEW_7 proved correct for that window only. This run builds the full "
        "CONTEXT 4.2 table per symbol from the NSE corporate-action history and applies it "
        "pairwise (CONTEXT 3.2). Section 3 shows it changes nothing in the pilot window, and "
        "section 6 measures what it would have changed over the settled universe."
    )
    add(
        f"* **The disclosed-residual register was read before any per-symbol statistic** "
        f"(`{bt.RESIDUAL_LEDGER_RELPATH}`, CONTEXT 4.6's chunk-9 duty). Carried verbatim into "
        f"every manifest this runner writes: "
        f"\"{manifest['residual_register']['caveat']}\""
    )
    add(
        f"* **{bt.CAPITAL_FLAGS_PENDING_NOTE}.** `capital_reference` and `margin_basis` are "
        "optional config keys and both are null. The machinery is built and tested; it "
        "computes POST-HOC from the ledger, never inside the run, and there is no default "
        "figure anywhere in it."
    )
    add(
        "* **The two CONTEXT 7-E13 metrics the build session STOPPED on are RULED and "
        "computed** (QUESTIONS.md **Q-16**, architect 30-Jul-2026). `outliers` is Tukey fences "
        "on net PnL, printed with its definition beside it. The intra-trade / intrabar "
        "drawdown and run-up are measured on the TRUE portfolio equity path at 15-minute "
        "resolution -- the earlier worst-case coincidence construction is RETIRED, because it "
        "invented co-timing -- with one disclosed limit: intra-candle excursions are not "
        "represented, and the per-trade MFE/MAE figures carry those. Nothing in this pack is "
        "labelled PROVISIONAL."
    )
    add(
        "* **One presentation basis: NET.** Every metric in section 7 is after the CONTEXT 3.5 "
        "Rs 100/trade round trip, over one population keyed on the sign of NET (the E13 "
        "presentation ruling, 30-Jul-2026). The before-costs totals appear on exactly one "
        "labelled line. Section 7a opens with the definitions block that ruling requires."
    )
    add(
        "* **Idealized fills (CONTEXT 7-E9)** and **read-only stores**: no order, no network "
        "beyond the corporate-action day-cache, nothing written to either store."
    )
    add("")

    add("## 2. Inputs")
    add("")
    add("| Input | Value | Source |")
    add("|---|---|---|")
    add(
        f"| Risk per trade | {_money(pilot_runner.spec.risk_per_trade_paise)} = "
        f"{pilot_runner.spec.risk_per_trade_paise:,} paise | `config.yaml` (CONTEXT 3.5) |"
    )
    add(
        f"| Cost per executed round trip | {_money(pilot_runner.spec.cost_paise)} | "
        "`config.yaml` (CONTEXT 3.5, R1-Q23) |"
    )
    add(f"| Row Size N | {pilot_runner.spec.row_size} | `config.yaml` (CONTEXT 3.3) |")
    add(
        f"| Capital (equity curve base) | "
        f"{_money(initial_capital_paise)} | `config.yaml` (CONTEXT 3.5, R1-Q21a) |"
    )
    add("| capital_reference / margin_basis | null / null | trader Q43 PENDING |")
    add(f"| Instrument master | `{master_name}` | newest cached dump (CONTEXT 4.3 ticks) |")
    add(f"| Spec version | {manifest['spec_version']} | CONTEXT.md |")
    add(f"| Factor-table digest | `{pilot_runner.spec.factor_digest[:16]}...` | sha256 |")
    add(f"| Pilot symbols | {', '.join(PILOT_SYMBOLS)} | chunk-7/8 window, unchanged |")
    add(f"| Pilot window | {PILOT_START} .. {PILOT_END} | chunk-7/8 window, unchanged |")
    add("")

    add("## 3. Pilot (a) -- the chunk-8 window, re-run THROUGH THE RUNNER")
    add("")
    add(
        "Same days, same engines, but now driven by `acumen.backtest` end to end and with the "
        "real factor table wired. The committed chunk-8 pack is the oracle; every figure must "
        "match to the paisa."
    )
    add("")
    add("| Figure | chunk-8 pack | chunk-9A runner | match |")
    add("|---|---|---|---|")
    for label, expected, measured, ok in reconciliation(rows):
        shown_expected = (
            _money(expected) if label.endswith("paise") else f"{expected:,}"
        )
        shown_measured = (
            _money(measured) if label.endswith("paise") else f"{measured:,}"
        )
        add(
            f"| {RECONCILIATION_LABELS[label]} | {shown_expected} | {shown_measured} | "
            f"{'YES' if ok else '**NO**'} |"
        )
    add("")
    mismatches = [row for row in reconciliation(rows) if not row[3]]
    add(
        f"**Reconciliation: {len(reconciliation(rows)) - len(mismatches)} of "
        f"{len(reconciliation(rows))} figures identical"
        + ("**." if not mismatches else f", {len(mismatches)} DIVERGENT**.")
    )
    add("")
    add("**Why the real factor table changes nothing HERE.** Every corporate action for these")
    add("five symbols with an ex-date inside the window:")
    add("")
    add("| symbol | ex-date | kind | k | basis |")
    add("|---|---|---|---|---|")
    for row in in_window_events(pilot_runner):
        add("| " + " | ".join(row) + " |")
    add("")
    add(
        "All of them are ORDINARY dividends under CONTEXT 4.2's 2% special-dividend threshold, "
        "so every k = 1 and a pairwise adjustment by them is the identity. That is the same "
        "conclusion REVIEW_7 section 6 reached from the CA cache, reproduced here from the "
        "table the run actually used. (REVIEW_7 quoted the worst as 1.78%; the classification "
        "band printed above is measured against the CUM-date close, which CONTEXT 4.2 "
        "distinguishes from the pre-announcement close the 2% test uses -- two different "
        "reference prices, and both readings are under the threshold.)"
    )
    add("")
    add("**The run's own partition and rare shapes** (from the manifest, counted, never inferred):")
    add("")
    add("| Outcome | Days |")
    add("|---|---|")
    for outcome, count in manifest["outcomes"].items():
        add(f"| {outcome} | {count} |")
    add(f"| **total walked** | **{manifest['totals']['walked']}** |")
    add("")
    add("| Rare shape | Occurrences |")
    add("|---|---|")
    for shape, count in manifest["rare_shapes"].items():
        add(f"| {shape} | {count} |")
    add("")
    add(
        "A zero is a statement about this window, not about the code: it says the window "
        "carries no real-data witness for that branch."
    )
    add("")

    add("## 4. Pilot (b) -- crossing a REAL corporate action")
    add("")
    out.extend(
        render_bias_walk(
            cross_walk,
            title=f"4a. {CROSS_CA_SYMBOL} 1:1 bonus, ex-date {CROSS_CA_EX_DATE}",
            note=(
                f"A settled symbol, a share-count event inside the minute era, full minute "
                f"coverage on both sides. The factor table gives k = 1/2 (CONTEXT 4.2: bonus "
                f"A:B -> B/(A+B) = 1/2). Exactly ONE bias pair in the whole history is touched "
                f"by it -- the trade day whose D-1 IS the ex-date; for the day after, the "
                f"ex-date is P itself and CONTEXT 3.2's window (P, C] no longer contains it."
            ),
        )
    )
    add(f"The runner's ledger over {CROSS_CA_START} .. {CROSS_CA_END}:")
    add("")
    out.extend(ledger_table(cross.result.rows))
    add("")
    add(
        "Note the row for **2024-11-01**: NSE's Muhurat session. Its stored candles are stamped "
        "18:00-18:59, wholly outside 09:15-15:30, so CONTEXT 7-E2's own detection makes it a "
        "NON-STANDARD session. It is refused under E2, counted, and removed from the trading "
        "calendar -- which is why the next trading day's pair reaches back past it."
    )
    add("")
    out.extend(
        render_bias_walk(
            flip_walk,
            title=f"4b. {FLIP_CA_SYMBOL} face-value split, ex-date {FLIP_CA_EX_DATE}",
            note=(
                "The case that matters: here the adjustment REVERSES the bias. Unadjusted, the "
                "split looks like a 50% collapse and Rule 1 fires BEARISH; adjusted, the same "
                "two candles are an ordinary pair. A bearish bias means the engine would have "
                "traded the SHORT side all day."
            ),
        )
    )
    add(f"The runner's ledger over {FLIP_CA_START} .. {FLIP_CA_END}:")
    add("")
    out.extend(ledger_table(flip.result.rows))
    add("")
    add(f"### 4c. The demerger window -- {DEMERGER_SYMBOL}, ex-date {DEMERGER_EX_DATE}")
    add("")
    add(
        "CONTEXT 3.2: a demerger has NO valid factor, so any pair spanning the ex-date is "
        "invalid -- no bias update and no trade on the days where D-1 or D-2 is the ex-date. "
        "Those days are REFUSED and COUNTED, and the engine resumes from the first pair whose "
        "candles both sit strictly after E."
    )
    add("")
    out.extend(ledger_table(demerger.result.rows))
    add("")

    add("## 5. Pilot (c) -- resume and determinism")
    add("")
    add("| Check | Result |")
    add("|---|---|")
    add(f"| Uninterrupted run, ledger sha256 | `{resume.whole_sha}` |")
    add(f"| Killed after symbol | {resume.killed_after} |")
    add(
        f"| Shards on disk at the kill | {', '.join(resume.shards_before_resume)} "
        "(only COMPLETE symbols) |"
    )
    add(f"| Resumed run, ledger sha256 | `{resume.resumed_sha}` |")
    add(
        f"| **Byte-identical** | **{'YES' if resume.whole_sha == resume.resumed_sha else 'NO'}** |"
    )
    add(
        f"| Manifest digest (commit-independent) | `{resume.manifest_whole}` vs "
        f"`{resume.manifest_resumed}` |"
    )
    add(f"| Rows: whole / resumed | {resume.rows_whole} / {resume.rows_resumed} |")
    add(f"| Duplicated (symbol, day) keys | {resume.duplicate_keys} |")
    add(f"| Pilot (a) ledger sha256 | `{pilot.ledger_sha}` |")
    add(f"| Pilot (a) manifest digest | `{pilot.manifest_sha}` |")
    add("")
    add(
        "The ledger holds no clock read of any kind -- the only timestamps in a row are CANDLE "
        "stamps -- which is what lets the same code over the same stores produce the same bytes."
    )
    add("")

    add("## 6. How much the real factor table matters, measured")
    add("")
    add(
        f"Every bonus and face-value split on a SETTLED symbol with an ex-date in the minute era "
        f"({SCAN_START} .. {scan.end}) touches exactly one bias pair -- the trade day whose D-1 "
        f"IS the ex-date. Each of those days was computed TWICE by the bias orchestration, once "
        f"with the real factor table and once with an empty one, each seeded {SCAN_SEED_DAYS} "
        f"calendar days back so both readings carry their own bias forward exactly as a run "
        f"would:"
    )
    add("")
    add("| Measure | Count |")
    add("|---|---|")
    add(f"| Settled symbols scanned | {scan.symbols_scanned} |")
    add(f"| Share-count events in the era | {scan.events} |")
    add(f"| Bias pairs walked (one per event) | {scan.pairs} |")
    add(f"| **Pairs whose BIAS the adjustment changes** | **{scan.bias_changed}** |")
    add("")
    add(
        "Those are days on which an empty factor table would have traded the WRONG SIDE. It is "
        "the measurement behind chunk 9's duty to wire the real table, and it is why the pilot "
        "window's \"nothing changed\" is a statement about the window, not a general one."
    )
    add("")
    add("First 15 changed pairs (oldest first):")
    add("")
    add("| symbol | ex-date | kind | k | affected trade day | adjusted | unadjusted |")
    add("|---|---|---|---|---|---|---|")
    changed = sorted(
        (row for row in scan.rows if row.adjusted_bias != row.unadjusted_bias),
        key=lambda row: (row.ex_date, row.symbol),
    )
    for row in changed[:15]:
        add(
            f"| {row.symbol} | {row.ex_date} | {row.kind} | {row.k} | {row.trade_day} | "
            f"{row.adjusted_bias} | {row.unadjusted_bias} |"
        )
    add("")

    add("## 7. The portfolio layer on the pilot ledger")
    add("")
    add(
        "PURE over the ledger rows: no store, no clock. The equity curve is "
        "`capital + cumulative PnL` -- a plain cumulative SUM, because the fixed-rupee risk "
        "rule never sizes off the running equity (CONTEXT 3.5)."
    )
    add("")
    add("### 7a. CONTEXT 7-E13 metrics (All)")
    add("")
    add("**DEFINITIONS -- read these before the table** (the architect's Q-16 and E13 rulings, "
        "30-Jul-2026; they close REVIEW_9A findings Q1, Q2, Q4, Q6 and Q7):")
    add("")
    add(f"* **Basis and population.** {pf.E13_BASIS}")
    add(
        "* **Drawdown and run-up denominators.** A drawdown's percent is over the RUNNING PEAK "
        "it fell from, a run-up's over the RUNNING TROUGH it rose from -- not over the initial "
        "capital. Both running extremes are SEEDED AT THE OPENING CAPITAL, so a fall on the "
        "very first day is measured from the money that was actually there (decision B185); a "
        "peak or trough shown as \"opening capital\" means exactly that."
    )
    add(
        "* **Drawdown and run-up, two forms.** The close-to-close form walks daily CLOSING "
        f"equity. The intra-trade form walks the 15-minute path: {pf.INTRADAY_PATH_LIMIT}."
    )
    add(f"* **Outliers.** {pf.OUTLIER_DEFINITION}")
    add(
        "* **CAGR span.** The ENDPOINT DIFFERENCE of the walked window in calendar days "
        "(last day minus first day, so an 82-day window spans 81 days), over a 365-day year; "
        "`None` when the final equity is at or below zero, because a negative base has no real "
        "root (decision B187)."
    )
    add(
        "* **Sharpe and Sortino.** E13's own convention: daily equity returns, risk-free rate "
        "0, annualized x sqrt(252); sample standard deviation (n-1) for Sharpe, downside "
        "sum-of-squares over ALL observations for Sortino; `-` when undefined, never 0 "
        "(decision B186)."
    )
    add(
        "* **The one exception to the net basis, stated so it cannot mislead.** Section 3's "
        "reconciliation table compares this run against the COMMITTED chunk-8 pack figure by "
        "figure, and chunk 8 reported on a before-costs basis: its \"Gross PnL\", its \"gross "
        "profit\" and its \"gross loss\" are all totals taken before the Rs 100/trade round "
        "trip. **All THREE of those rows** are labelled with that basis where they appear and "
        "are a cross-document check, not report metrics (REVIEW_9A_2 finding Q1: the earlier "
        "wording named two of them and left the third unlabelled)."
    )
    add("")
    add("| Metric | Value |")
    add("|---|---|")
    out.extend(metrics_table("All", metrics))
    add("")
    add("### 7b. All / Long / Short")
    add("")
    add("| Column | Trades | Net PnL | Winners | Losers | % profitable | Max drawdown |")
    add("|---|---|---|---|---|---|---|")
    for name in ("All", "Long", "Short"):
        column = split[name]
        add(
            f"| {name} | {column.total_trades} | {_money(column.net_pnl_paise)} | "
            f"{column.winners} | {column.losers} | "
            f"{pf.format_pct(column.percent_profitable)} | "
            f"{_money(column.max_drawdown.amount_paise)} |"
        )
    add("")
    add("### 7c. Per symbol")
    add("")
    add("| Symbol | Trades | Net PnL | Winners | Losers | Largest win | Largest loss |")
    add("|---|---|---|---|---|---|---|")
    for symbol in PILOT_SYMBOLS:
        column = symbols[symbol]
        add(
            f"| {symbol} | {column.total_trades} | {_money(column.net_pnl_paise)} | "
            f"{column.winners} | {column.losers} | {_money(column.largest_win_paise)} | "
            f"{_money(column.largest_loss_paise)} |"
        )
    add("")
    add("### 7d. Buy & hold benchmark (CONTEXT 7-E13's own definition)")
    add("")
    add(
        f"Equal-weight portfolio of the traded universe, bought at the first trade date's close "
        f"({benchmark.first_day}) and held to {benchmark.last_day}."
    )
    add("")
    add("| Figure | Value |")
    add("|---|---|")
    add(f"| Start value | {_money(benchmark.start_value_paise)} |")
    add(f"| End value | {_money(benchmark.end_value_paise)} |")
    add(f"| Total return | {pf.format_pct(benchmark.total_return)} |")
    add(f"| Strategy return over the same span | {pf.format_pct(metrics.return_on_initial_capital)} |")
    add(f"| Construction | {benchmark.note} |")
    add("")
    add("### 7e. CONTEXT 3.5 take-all disclosures (Round-3 Q40, option d)")
    add("")
    add("| Disclosure | Value |")
    add("|---|---|")
    add(
        f"| Max concurrent positions | {disclosures.max_concurrent_positions.positions} "
        f"(at {disclosures.max_concurrent_positions.at}) |"
    )
    add(
        f"| Peak simultaneous notional | "
        f"{_money(disclosures.peak_simultaneous_notional.notional_paise)} "
        f"(at {disclosures.peak_simultaneous_notional.at}, "
        f"{disclosures.peak_simultaneous_notional.positions} position(s)) |"
    )
    add(
        f"| Largest single position notional | "
        f"{_money(disclosures.largest_single_notional_paise)} |"
    )
    add(f"| Executed trades | {disclosures.total_executed} |")
    add("")
    add("Distribution of daily trade counts (every walked day, including the empty ones):")
    add("")
    add("| Trades on the day | Number of days |")
    add("|---|---|")
    for count, days in disclosures.daily_trade_counts:
        add(f"| {count} | {days} |")
    add("")
    add("### 7f. Capital-infeasibility flags (Q40-d, second half)")
    add("")
    add(f"**{flags.note}**")
    add("")
    add(
        "The machinery exists and is unit-tested on both branches: with `capital_reference` and "
        "`margin_basis` set, each executed trade whose notional exceeds the cash figure is "
        "flagged `beyond cash`, and each one beyond `capital_reference x margin_basis` is "
        "flagged `beyond margin`, computed POST-HOC from this ledger. Neither key has a "
        "default, and a trade is never capped, skipped or resized -- the flags are a "
        "disclosure, not a constraint. For reference while the answer is pending, the largest "
        f"notional this pilot ever held is {_money(disclosures.largest_single_notional_paise)} "
        f"and the peak simultaneous notional is "
        f"{_money(disclosures.peak_simultaneous_notional.notional_paise)}."
    )
    add("")

    add("## 8. Invariants asserted over this pack")
    add("")
    for line in invariant_report(
        pilot,
        resume,
        benchmark,
        initial_capital_paise=initial_capital_paise,
        trade_paths=trade_paths,
    ):
        add(f"* {line}")
    add("")
    add("## 9. What chunk 9B still owes")
    add("")
    add(
        "* the full-history run over the settled universe, and the report built on it -- gated "
        "on the trader's Round-4 answers (Q43's capital figure for the Q40-d flags, Q44's "
        "confirmation);"
    )
    add(
        "* the capital-infeasibility FLAG VALUES, which cannot be computed before Q43 and are "
        "deliberately absent here;"
    )
    add(
        "* a **DISCRIMINATING CONTEXT 7-E2 witness** (REVIEW_9A finding Q8, recorded here as a "
        "9B duty). This pack's witness -- 2024-11-04's bias pair reaching back past NSE's "
        "Muhurat session to (2024-10-30, 2024-10-31) -- proves the MECHANISM, but both "
        "readings, with and without the E2 removal, land on `inside-bar-carry` and the same "
        "carried bias, so it does not show E2 changing an answer. 9B's pack owes a day where "
        "the removal changes the bias, the rule or the trade;"
    )
    add(
        "* **non-standard sessions from the PUBLISHED calendar on the live path** (REVIEW_9A "
        "finding C5, recorded here as a chunk-9B/13 duty). `scan_non_standard_sessions` "
        "decides a market-wide calendar property by scanning stored candles across the run's "
        "universe and span, which is correct and self-evidencing for a backtest -- but chunk "
        "13 has no future candles to scan, and CONTEXT 6's replay invariant requires the two "
        "paths to agree. The live path must take non-standard sessions from the published NSE "
        "calendar (CONTEXT 4.1) and keep this store scan as the backtest-side cross-check; 9B "
        "should also cache the scan beside its ledger (decision B181). No code change was made "
        "here: the change belongs on the live path, which chunk 13 owns."
    )
    add("")
    return "\n".join(out) + "\n"


def invariant_report(
    pilot: PilotRun,
    resume: ResumeProof,
    benchmark: pf.Benchmark,
    *,
    initial_capital_paise: int,
    trade_paths: tuple[bt.TradePath, ...] = (),
) -> list[str]:
    """Every invariant this pack claims, each recomputed here and printed with its verdict."""
    rows = pilot.result.rows
    manifest = pilot.result.manifest
    executed = [row for row in rows if row.executed]
    lines: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        lines.append(f"{label}: **{'PASS' if ok else 'FAIL'}**{detail}")

    keys = [(row.symbol, row.day) for row in rows]
    check(
        "one ledger row per walked symbol-day, no duplicates",
        len(keys) == len(set(keys)),
        f" ({len(keys)} rows, {len(set(keys))} distinct keys)",
    )
    check(
        "the outcome counts PARTITION the walked days",
        sum(manifest["outcomes"].values()) == len(rows),
    )
    check(
        "every refusal carries exactly one reason and no money",
        all(
            row.reason and row.qty == 0 and row.net_pnl_paise == 0
            for row in rows
            if row.status == bt.STATUS_REFUSED
        ),
    )
    net = sum(row.net_pnl_paise for row in executed)
    points = pf.equity_curve(pf.daily_pnl(rows), initial_capital_paise)
    check(
        "sum of trade PnL == equity curve delta",
        points[-1].equity_paise - initial_capital_paise == net,
        f" ({_money(net)})",
    )
    check(
        "trade count == number of executed ledger rows",
        pf.metrics(rows, initial_capital_paise=initial_capital_paise).total_trades
        == len(executed),
        f" ({len(executed)})",
    )
    check(
        "net == gross - cost on every executed trade",
        all(
            row.net_pnl_paise == row.gross_pnl_paise - row.cost_paise for row in executed
        ),
    )
    check(
        "no non-executed day pays a cost or carries PnL",
        all(
            row.cost_paise == 0 and row.gross_pnl_paise == 0 and row.net_pnl_paise == 0
            for row in rows
            if not row.executed
        ),
    )
    check(
        "qty x per-share risk <= the risk budget on every signalled day",
        all(
            row.qty * (row.per_share_risk_paise or 0) <= pilot.result.spec.risk_per_trade_paise
            for row in rows
            if row.signalled and row.per_share_risk_paise
        ),
    )
    check(
        "the sizing floor is tight ((qty + 1) x risk > budget)",
        all(
            (row.qty + 1) * (row.per_share_risk_paise or 1)
            > pilot.result.spec.risk_per_trade_paise
            for row in rows
            if row.signalled and row.per_share_risk_paise
        ),
    )
    check(
        "every MFE >= 0 and every MAE <= 0 (both BEFORE COSTS -- price excursions)",
        all(
            (row.mfe_paise or 0) >= 0 and (row.mae_paise or 0) <= 0 for row in executed
        ),
    )
    net_inside = sum(
        1
        for row in executed
        if (row.mae_paise or 0) <= row.net_pnl_paise <= (row.mfe_paise or 0)
    )
    check(
        "every executed trade's realized GROSS PnL sits inside [MAE, MFE] -- the BEFORE-COSTS "
        "basis is what makes this an invariant; the NET PnL can sit below MAE by up to the "
        "Rs 100 cost, so it is stated and counted rather than asserted",
        all(
            (row.mae_paise or 0) <= row.gross_pnl_paise <= (row.mfe_paise or 0)
            for row in executed
        ),
        f" (net inside on {net_inside} of {len(executed)})",
    )
    relieved = sum(1 for row in rows if row.gate1_relieved)
    check(
        "every evaluated day passed the whole CONTEXT 4.6 battery, recomputed per day "
        "(gate 1 strictly or by the evidence-gated auction relief, gate 2, gate 1P)",
        all(
            (row.gate1_passed or row.gate1_relieved)
            and row.gate2_passed
            and row.gate1p_passed
            for row in rows
            if row.status == bt.STATUS_EVALUATED
        ),
        f" ({relieved} day(s) passed gate 1 by auction relief, counted separately)",
    )
    check(
        "the run reconciles with the committed chunk-8 pack on every figure",
        all(ok for *_rest, ok in reconciliation(rows)),
    )
    check(
        "an interrupted run resumes byte-identically with zero duplicates",
        resume.identical,
    )
    check(
        # CONTEXT 4.6 (v1.5): the settled-but-partial figures are "quoted from the register's
        # own current figures, which every manifest carries verbatim". So the invariant is
        # INTERNAL CONSISTENCY -- the caveat sentence must be the one this manifest's OWN
        # per-symbol register entries produce. Reconstructing the entries from the manifest
        # keeps the check offline and makes it impossible to satisfy with a frozen string.
        "the manifest's residual caveat quotes its own register entries (CONTEXT 4.6 v1.5)",
        manifest["residual_register"]["caveat"]
        == bt.residual_caveat(
            {
                symbol: bt.ResidualEntry(
                    symbol=entry["symbol"],
                    status=entry["status"],
                    gate1p_pass=entry["gate1p_pass"],
                    gate1p_total=entry["gate1p_total"],
                    gate1p_no_oracle=entry["gate1p_no_oracle"],
                    residual_reason=entry["residual_reason"],
                )
                for symbol, entry in manifest["residual_register"]["per_symbol"].items()
            }
        ),
    )
    check(
        "the capital-infeasibility flags are NOT computed (Q43 pending)",
        manifest["capital_flags"]["computed"] is False,
    )
    check(
        "the benchmark is built from the first trade date's closes",
        benchmark.total_return is not None,
    )
    series = pf.daily_pnl(rows)
    path_points = pf.intraday_equity_path(
        series, trade_paths, initial_capital_paise=initial_capital_paise
    )
    check(
        "every 15-minute path reconciles with the ledger (last mark == realized net PnL)",
        len(trade_paths) == len(executed)
        and all(pf.path_reconciles(path) for path in trade_paths),
        f" ({len(trade_paths)} paths, {sum(len(p.marks) for p in trade_paths):,} marks)",
    )
    closes = {point.day: point.equity_paise for point in path_points if point.stamp is None}
    check(
        "each day's last 15-minute observation equals that day's closing equity",
        closes == {point.day: point.equity_paise for point in points},
        f" ({len(path_points):,} path observations)",
    )
    check(
        "the 15-minute path never rests on a mark outside the session (CONTEXT 3.1)",
        all(
            bt.is_standard_session_stamp(mark.stamp - timedelta(minutes=15))
            for path in trade_paths
            for mark in path.marks
        ),
    )
    return lines


# --- the launcher --------------------------------------------------------------------------------


def build_everything(
    *, data_dir: Path | None = None, progress=None, scan: bool = True
) -> dict:
    """Run every pilot piece and return what the renderer needs."""
    config = load_config(include_env=False)
    data = Path(data_dir) if data_dir is not None else config.path("data_root")
    daily_store = DailyStore.at(data / "daily_store")

    pilot, pilot_runner = run_window(
        PILOT_SYMBOLS,
        PILOT_START,
        PILOT_END,
        label="chunk9a_pilot_a",
        data_dir=data_dir,
        progress=progress,
    )
    cross, cross_runner = run_window(
        (CROSS_CA_SYMBOL,),
        CROSS_CA_START,
        CROSS_CA_END,
        label="chunk9a_pilot_b1",
        data_dir=data_dir,
        progress=progress,
    )
    flip, flip_runner = run_window(
        (FLIP_CA_SYMBOL,),
        FLIP_CA_START,
        FLIP_CA_END,
        label="chunk9a_pilot_b2",
        data_dir=data_dir,
        progress=progress,
    )
    demerger, _demerger_runner = run_window(
        (DEMERGER_SYMBOL,),
        DEMERGER_START,
        DEMERGER_END,
        label="chunk9a_pilot_b3",
        data_dir=data_dir,
        progress=progress,
    )

    cross_walk = _walk_for(cross_runner, CROSS_CA_SYMBOL, CROSS_CA_EX_DATE, cross)
    flip_walk = _walk_for(flip_runner, FLIP_CA_SYMBOL, FLIP_CA_EX_DATE, flip)

    resume = resume_proof(
        PILOT_SYMBOLS,
        PILOT_START,
        PILOT_END,
        data_dir=data_dir,
        kill_after=PILOT_SYMBOLS[1],
        progress=progress,
    )

    if scan:
        actions = fetch_corp_action_history(
            date(2005, 1, 1), PILOT_END, allow_network=False
        )
        register = bt.load_residual_register(data / bt.RESIDUAL_LEDGER_RELPATH)
        calendar = TradingCalendar.from_daily_store_range(
            daily_store, date(2016, 1, 1), PILOT_END
        )
        scan_result = scan_share_count_events(
            daily_store,
            calendar,
            register,
            actions,
            end=PILOT_END,
            minute_loader=pilot_runner.minute_loader,
            progress=progress,
        )
    else:  # pragma: no cover -- the committed pack is always generated with the scan
        scan_result = ScanResult(0, 0, 0, (), 0, PILOT_END)

    executed = [row for row in pilot.result.rows if row.executed]
    first_trade_day = min(row.day for row in executed)
    closes = {
        symbol: _closes(daily_store, symbol, first_trade_day, PILOT_END)
        for symbol in PILOT_SYMBOLS
    }
    benchmark = pf.buy_and_hold(
        closes,
        first_day=first_trade_day,
        last_day=PILOT_END,
        initial_capital_paise=config.initial_capital_paise(),
    )
    trade_paths = bt.assemble_trade_paths(
        pilot.result.rows, bars_for=bt.minute_store_bars(pilot_runner.minute_store)
    )
    master = bt.latest_cached_master(config.path("cache_root"))[1].name
    return {
        "pilot": pilot,
        "pilot_runner": pilot_runner,
        "cross": cross,
        "cross_walk": cross_walk,
        "flip": flip,
        "flip_walk": flip_walk,
        "demerger": demerger,
        "scan": scan_result,
        "resume": resume,
        "benchmark": benchmark,
        "master_name": master,
        "initial_capital_paise": config.initial_capital_paise(),
        "trade_paths": trade_paths,
    }


def _walk_for(
    runner: bt.BacktestRunner, symbol: str, ex_date: date, run: PilotRun
) -> BiasWalk:
    """The hand walk of the ONE pair an ex-date touches, beside the runner's own answer."""
    trade_day = _next_trading_day(runner.calendar, ex_date, runner.spec.end)
    if trade_day is None:  # pragma: no cover -- the windows are chosen to contain it
        raise PilotError(f"{symbol}: no trading day after {ex_date} inside the window")
    biases, failure = runner.bias_map(symbol)
    if failure is not None:  # pragma: no cover
        raise PilotError(f"{symbol}: {failure}")
    previous = biases.get(_previous_trading_day(runner.calendar, trade_day))
    return walk_pair(
        runner.daily_store,
        runner.calendar,
        symbol,
        trade_day,
        runner.factors.get(symbol, ()),
        minute_loader=runner.minute_loader,
        carry=None if previous is None else previous.bias,
        runner_bias=biases.get(trade_day),
    )


def _previous_trading_day(calendar: TradingCalendar, day: date) -> date:
    return calendar.prev_trading_day(day)


def _closes(store: DailyStore, symbol: str, start: date, end: date) -> dict[date, int]:
    frame = store.daily(symbol, start, end)
    return {
        row.trade_date: int(row.close_paise)
        for row in frame.itertuples()
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="chunk-9A pilot evidence pack")
    parser.add_argument("--out", default=DEFAULT_OUT, help="markdown output path")
    parser.add_argument(
        "--no-scan",
        action="store_true",
        help="skip the universe-wide corporate-action materiality scan (the committed pack "
        "is always generated WITH it)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pieces = build_everything(progress=print, scan=not args.no_scan)
    command = "python docs/evidence/chunk9a_pilot.py" + (
        " --no-scan" if args.no_scan else ""
    )
    text = render_markdown(command=command, **pieces)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(text):,} chars)")
    return 0
