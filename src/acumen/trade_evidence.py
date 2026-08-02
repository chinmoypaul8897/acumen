"""Chunk-8 evidence: price real stored stock-days and write the pack. I/O allowed here.

CLAUDE.md's git rules (REVIEW_7 finding C3) require that a session making claims from real
store data commits the GENERATING SCRIPT and its OUTPUT under ``docs/evidence/``. This module
is that generator; ``docs/evidence/chunk8_sweep.py`` is the launcher the operator runs and
``docs/evidence/chunk8_sweep.md`` is its committed output.

What it does, and nothing more: it extends the chunk-7 orchestration
(:class:`acumen.signal_engine.SignalPipeline` -- bias -> the CONTEXT 4.6 gate battery -> POC ->
CONTEXT 3.4 signals) with the chunk-8 step, :func:`acumen.simulate.simulate_day`, so every
entered day in the sweep comes out priced. The engines are untouched: this module wires stores
to pure functions and formats the result.

**The money comes from ``config.yaml`` through the loader** -- ``risk_per_trade`` (CONTEXT 3.5,
1000 rupees) and ``cost_per_trade`` (100 rupees, R1-Q23), converted once to exact paise. No
amount is typed into this file.

**Disclosures carried into the pack, so no number in it is read as more than it is:**

* the factor table is EMPTY for this window. REVIEW_7 section 6 verified that against the CA
  cache itself: the only five corporate-action rows for these symbols with ex-dates inside the
  window are ORDINARY dividends, all under CONTEXT 4.2's 2% special-dividend threshold (worst
  1.78%), so every k = 1 and an empty table is exactly right HERE. Chunk 9 must wire the real
  chunk-3 table for a full-history run;
* the run is read-only and offline: it opens the two local parquet stores and the cached
  instrument master, and never a socket;
* the bias series is seeded at the window start (CONTEXT 3.2 seeding), which is what makes the
  first days of the window comparable to chunk 7's own sweep.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Sequence

from . import signals
from . import simulate as sim
from .bias_engine import BiasEngine, DailyBias
from .calendar import TradingCalendar
from .config import load_config
from .daily_store import DailyStore
from .instrument_master import (
    CACHE_SUBDIR as MASTER_CACHE_SUBDIR,
    InstrumentMaster,
    InstrumentMasterError,
    load_master_file,
)
from .minute_store import MinuteStore
from .signal_engine import SignalPipeline, StockDay

#: The five symbols and the window chunk 7 swept. Chunk 8 prices the same days, so the two
#: reports are line-comparable.
SWEEP_SYMBOLS: tuple[str, ...] = ("TCS", "RELIANCE", "HDFCBANK", "ICICIBANK", "BHARTIARTL")
SWEEP_START: date = date(2026, 5, 1)
SWEEP_END: date = date(2026, 7, 24)

#: The named golden of this chunk: the real Rule-3 outside-bar day chunk 7 walked candle by
#: candle and REVIEW_7 re-derived independently from the stores.
GOLDEN_SYMBOL: str = "HDFCBANK"
GOLDEN_DAY: date = date(2026, 6, 10)

#: How far before the window the calendar is derived, so ``bias_pair(D)`` can reach D-1/D-2
#: for the window's first trading day.
CALENDAR_LEAD_DAYS: int = 30

DEFAULT_OUT: str = "docs/evidence/chunk8_sweep.md"

#: The OPEN-stamp time of the square-off candle (CONTEXT 7-E12: the candle stamped 15:00
#: closes at 15:15). DERIVED from the signal engine's own session grid by ordinal rather than
#: typed as a clock literal (chunk-7 decision B154), so the two cannot drift apart.
_SQUARE_OFF_TIME = signals.bar_open_stamp(date.min, signals.SQUARE_OFF_BAR).time()


class EvidenceError(RuntimeError):
    """The evidence run cannot assemble its inputs from the local stores."""


@dataclass(frozen=True)
class SweepContext:
    """Everything one priced day needs: the two stores, the master, the calendar, the money."""

    pipeline: SignalPipeline
    bias_engine: BiasEngine
    risk_per_trade_paise: int
    cost_paise: int
    master_path: Path

    @property
    def row_size(self) -> int:
        return self.pipeline.row_size


@dataclass(frozen=True)
class PricedDay:
    """One stock-day through bias -> gates -> POC -> signal -> MONEY."""

    stock_day: StockDay
    record: sim.TradeRecord | None  # None when the day never reached the signal engine

    @property
    def symbol(self) -> str:
        return self.stock_day.symbol

    @property
    def day(self) -> date:
        return self.stock_day.day

    @property
    def executed(self) -> bool:
        return self.record is not None and self.record.executed


@dataclass(frozen=True)
class SweepResult:
    """Every day the sweep walked, in order, plus the inputs it was run with."""

    days: tuple[PricedDay, ...]
    symbols: tuple[str, ...]
    start: date
    end: date
    risk_per_trade_paise: int
    cost_paise: int
    row_size: int
    master_path: Path

    @property
    def evaluated(self) -> tuple[PricedDay, ...]:
        return tuple(day for day in self.days if day.record is not None)

    @property
    def entered(self) -> tuple[PricedDay, ...]:
        return tuple(
            day for day in self.days if day.record is not None and day.record.signalled
        )

    @property
    def executed(self) -> tuple[PricedDay, ...]:
        return tuple(day for day in self.days if day.executed)


# --- wiring -------------------------------------------------------------------------------


def pinned_cached_master(cache_dir: Path, filename: str) -> tuple[InstrumentMaster, Path]:
    """Load the PINNED instrument master by name, offline. Its PATH is printed in the pack.

    **This replaced a newest-by-filename selector** (the chunk-8 build's own
    ``latest_cached_master``, decision B175, whose docstring reasoned that "the tick sizes it
    reads are per-symbol constants, not a daily quantity"). That premise is now MEASURED FALSE:
    QUESTIONS.md Q-20 found the vendor moving ``tick_size`` in BOTH directions on 11 of the
    sealed 210 within two days. This module computes POCs, and CONTEXT 3.3 sizes the profile row
    grid by the tick, so it reads the same one pinned snapshot the run reads -- the repo has ONE
    tick source, not two that agree until the day they do not.

    ``load_instrument_master`` is still not used here: it serves today's dump or downloads it,
    and an evidence run must never reach the network (CLAUDE.md rule 4).
    """
    path = Path(cache_dir) / MASTER_CACHE_SUBDIR / filename
    if not path.is_file():
        raise EvidenceError(
            f"The pinned instrument master {filename!r} is not at {path}: the sweep needs each "
            "symbol's own tick size (CONTEXT 4.3 -- never hardcode a tick) and QUESTIONS.md "
            "Q-20 pins which dump supplies it (config.yaml `instrument_master`)."
        )
    try:
        return load_master_file(path), path
    except InstrumentMasterError as exc:  # pragma: no cover -- a corrupt cache file
        raise EvidenceError(f"Pinned instrument master {path} is unusable: {exc}") from exc


def build_context(
    *,
    data_dir: Path | None = None,
    cache_dir: Path | None = None,
    start: date = SWEEP_START,
    end: date = SWEEP_END,
) -> SweepContext:
    """Open the local stores read-only and wire the whole pipeline, money included."""
    config = load_config(include_env=False)
    data = Path(data_dir) if data_dir is not None else config.path("data_root")
    cache = Path(cache_dir) if cache_dir is not None else config.path("cache_root")

    daily_store = DailyStore.at(data / "daily_store")
    minute_store = MinuteStore.at(data / "minute_store")
    master, master_path = pinned_cached_master(cache, config.instrument_master)
    calendar = TradingCalendar.from_daily_store_range(
        daily_store, start - timedelta(days=CALENDAR_LEAD_DAYS), end
    )
    return SweepContext(
        pipeline=SignalPipeline(
            minute_store=minute_store,
            daily_store=daily_store,
            master=master,
            row_size=config.row_size,
        ),
        # factors=() and suppressions=(): the EMPTY factor table, disclosed in the pack and
        # verified correct for this window by REVIEW_7 section 6 (five ordinary dividends,
        # all under CONTEXT 4.2's 2% threshold, so every k = 1).
        bias_engine=BiasEngine(
            store=daily_store,
            calendar=calendar,
            minute_loader=_minute_loader(minute_store),
        ),
        risk_per_trade_paise=config.require_risk_per_trade_paise(),
        cost_paise=config.cost_per_trade_paise(),
        master_path=master_path,
    )


def _minute_loader(minute_store: MinuteStore):
    """The (symbol, date) -> 1-minute candles interface CONTEXT 3.2's Rule 3 needs."""

    def load(symbol: str, day: date):
        bars = minute_store.minutes(symbol, day)
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


# --- pricing ------------------------------------------------------------------------------


def price_day(context: SweepContext, symbol: str, bias: DailyBias) -> PricedDay:
    """One stock-day: chunk 7's evaluation, then chunk 8's money on top of it."""
    stock_day = context.pipeline.stock_day(symbol, bias.trade_date, bias=bias)
    if stock_day.signal is None:
        return PricedDay(stock_day=stock_day, record=None)
    record = sim.simulate_day(
        stock_day.signal,
        stock_day.bars,
        symbol=symbol,
        risk_per_trade_paise=context.risk_per_trade_paise,
        cost_paise=context.cost_paise,
        bias=bias.bias,
        tie_case=bias.tie_case,
    )
    return PricedDay(stock_day=stock_day, record=record)


def price_one(
    context: SweepContext, symbol: str, day: date, *, seed_from: date = SWEEP_START
) -> PricedDay:
    """Price a single named day, seeding the bias carry from ``seed_from`` (CONTEXT 3.2)."""
    bias = context.bias_engine.bias_for_day(symbol, day, seed_from=seed_from)
    return price_day(context, symbol, bias)


def run_sweep(
    context: SweepContext,
    *,
    symbols: Sequence[str] = SWEEP_SYMBOLS,
    start: date = SWEEP_START,
    end: date = SWEEP_END,
    progress=None,
) -> SweepResult:
    """Walk every symbol-day in the window, price it, and keep every day -- refusals included."""
    days: list[PricedDay] = []
    for symbol in symbols:
        series = context.bias_engine.bias_series(symbol, start, end)
        for bias in series:
            days.append(price_day(context, symbol, bias))
        if progress is not None:
            progress(f"  {symbol}: {len(series)} stock-days priced")
    return SweepResult(
        days=tuple(days),
        symbols=tuple(symbols),
        start=start,
        end=end,
        risk_per_trade_paise=context.risk_per_trade_paise,
        cost_paise=context.cost_paise,
        row_size=context.row_size,
        master_path=context.master_path,
    )


# --- the pack -----------------------------------------------------------------------------


def outcome_counts(result: SweepResult) -> dict[str, int]:
    """Count every day by what happened to it. The counts PARTITION the sweep."""
    counts: dict[str, int] = {}
    for priced in result.days:
        if priced.record is None:
            key = f"not evaluated: {priced.stock_day.reason}"
        else:
            key = priced.record.outcome
        counts[key] = counts.get(key, 0) + 1
    return counts


def money_totals(result: SweepResult) -> dict[str, int]:
    """Gross, cost and net over the EXECUTED trades, plus the winner/loser split."""
    executed = [priced.record for priced in result.executed if priced.record is not None]
    gross = sum(record.gross_pnl_paise for record in executed)
    cost = sum(record.cost_paise for record in executed)
    net = sum(record.net_pnl_paise for record in executed)
    return {
        "trades": len(executed),
        "gross_paise": gross,
        "cost_paise": cost,
        "net_paise": net,
        "winners": sum(1 for record in executed if record.net_pnl_paise > 0),
        "losers": sum(1 for record in executed if record.net_pnl_paise < 0),
        "flat": sum(1 for record in executed if record.net_pnl_paise == 0),
        "gross_profit_paise": sum(
            record.gross_pnl_paise for record in executed if record.gross_pnl_paise > 0
        ),
        "gross_loss_paise": sum(
            record.gross_pnl_paise for record in executed if record.gross_pnl_paise < 0
        ),
        "shares": sum(record.qty for record in executed),
    }


def shape_counts(result: SweepResult) -> dict[str, int]:
    """How often the rare shapes actually occurred -- so the pack can say when a branch has
    NO real-data witness here rather than let silence read as coverage (REVIEW_7 finding Q3)."""
    records = [priced.record for priced in result.days if priced.record is not None]
    return {
        "gap entries": sum(1 for record in records if record.gap_entry),
        "qty-zero unsizable days": sum(
            1 for record in records if sim.FLAG_QTY_ZERO_UNSIZABLE in record.flags
        ),
        "signal-unsizable (degenerate) days": sum(
            1 for record in records if sim.FLAG_SIGNAL_UNSIZABLE in record.flags
        ),
        "both-touched candles (stop won)": sum(
            1 for record in records if sim.FLAG_BOTH_TOUCHED_STOP_WINS in record.flags
        ),
        "square-offs priced at the entry candle": sum(
            1 for record in records if sim.FLAG_SQUARE_OFF_AT_ENTRY_CANDLE in record.flags
        ),
        "rule-3 tie bias days": sum(1 for record in records if record.tie_case),
    }


def exit_kind_counts(result: SweepResult) -> dict[str, int]:
    counts: dict[str, int] = {}
    for priced in result.executed:
        record = priced.record
        if record is None or record.exit_kind is None:  # pragma: no cover -- executed implies both
            continue
        counts[record.exit_kind] = counts.get(record.exit_kind, 0) + 1
    return counts


def _price(paise: int | None) -> str:
    return "-" if paise is None else sim.format_paise(paise)[3:]  # drop the "Rs " prefix


def _poc_text(value: Fraction | None) -> str:
    """A POC in rupees, exactly -- including the legal half-paisa (CONTEXT 3.3 / 7-E11).

    ``739.80`` for a whole paisa, ``739.805`` for a row midpoint that sits half a paisa off
    the tick grid. Never rounded: the half is printed, not dropped.
    """
    if value is None:
        return "-"
    whole, half = value.numerator // value.denominator, value.denominator == 2
    return _price(whole) + ("5" if half else "")


def render_markdown(result: SweepResult, *, command: str) -> str:
    """The committed evidence pack: per-trade table, totals, and the named golden."""
    lines: list[str] = []
    add = lines.append

    add("# chunk 8 evidence -- the 290-day sweep, PRICED")
    add("")
    add(
        "Generated by `docs/evidence/chunk8_sweep.py` (implementation: "
        "`src/acumen/trade_evidence.py`), committed under CLAUDE.md's evidence rule "
        "(REVIEW_7 finding C3). Regenerate with:"
    )
    add("")
    add(f"    {command}")
    add("")
    add("## 1. What this is, and what it is not")
    add("")
    add(
        "Chunk 7's own sweep walked these same stock-days and reported 146 entered / 88 "
        "armed-with-no-qualifying-close / 56 never-armed, with zero exceptions and zero gate "
        "refusals; REVIEW_7 reproduced that partition independently. This run adds the chunk-8 "
        "step -- CONTEXT 3.5 sizing, exit PRICING and the money -- to every one of those days "
        "and prints the result trade by trade."
    )
    add("")
    add("It is **not** a backtest result. There is no portfolio here, no equity curve, no")
    add("metric and no capital constraint: those are chunks 9 and 10. Five symbols over three")
    add("months is a wiring witness, not a strategy measurement, and nobody should read a")
    add("profit into it.")
    add("")
    add("**Disclosures**")
    add("")
    add(
        "* **Empty factor table.** The bias engine ran with no corporate-action factors. "
        "REVIEW_7 section 6 verified against the CA cache that the only five events for these "
        "symbols with ex-dates in this window are ORDINARY dividends, all under CONTEXT 4.2's "
        "2% special-dividend threshold (worst 1.78%), so every k = 1 and the empty table is "
        "exactly right for THIS window. Chunk 9 must wire the real chunk-3 table."
    )
    add(
        "* **Read-only and offline.** Both parquet stores were opened read-only, the "
        f"instrument master came from the cached dump `{result.master_path.name}` (per-symbol "
        "tick sizes, CONTEXT 4.3 -- never hardcoded), and no socket was opened."
    )
    add(
        "* **Idealized fills (CONTEXT 7-E9).** A target or stop exit fills at the LEVEL, a "
        "square-off at the 15:00-stamped candle's close. No slippage beyond the flat cost."
    )
    add(
        "* **Gate battery recomputed per day** (CONTEXT 4.6, gate 1 + gate 2 + gate 1P), never "
        "looked up."
    )
    add("")
    add("## 2. Inputs")
    add("")
    add("| Input | Value | Source |")
    add("|---|---|---|")
    add(
        f"| Risk per trade | {sim.format_paise(result.risk_per_trade_paise)} = "
        f"{result.risk_per_trade_paise:,} paise | `config.yaml` -> loader (CONTEXT 3.5) |"
    )
    add(
        f"| Cost per executed round trip | {sim.format_paise(result.cost_paise)} = "
        f"{result.cost_paise:,} paise | `config.yaml` -> loader (CONTEXT 3.5, R1-Q23) |"
    )
    add(f"| Row Size N | {result.row_size} | `config.yaml` (CONTEXT 3.3) |")
    add(f"| Symbols | {', '.join(result.symbols)} | chunk-7 sweep, unchanged |")
    add(f"| Window | {result.start.isoformat()} .. {result.end.isoformat()} | chunk-7 sweep |")
    add(f"| Stock-days walked | {len(result.days)} | |")
    add("")

    add("## 3. Day partition")
    add("")
    add("| Outcome | Days |")
    add("|---|---|")
    for key, count in sorted(outcome_counts(result).items(), key=lambda item: -item[1]):
        add(f"| {key} | {count} |")
    add(f"| **total** | **{len(result.days)}** |")
    add("")

    totals = money_totals(result)
    add("## 4. Totals over the executed trades")
    add("")
    add("| Figure | Value |")
    add("|---|---|")
    add(f"| Executed trades | {totals['trades']} |")
    add(f"| Shares transacted | {totals['shares']:,} |")
    add(f"| Gross PnL | {sim.format_paise(totals['gross_paise'])} |")
    add(f"| Costs paid | {sim.format_paise(totals['cost_paise'])} |")
    add(f"| **Net PnL** | **{sim.format_paise(totals['net_paise'])}** |")
    add(f"| Gross profit (winners) | {sim.format_paise(totals['gross_profit_paise'])} |")
    add(f"| Gross loss (losers) | {sim.format_paise(totals['gross_loss_paise'])} |")
    add(
        f"| Winners / losers / flat (net) | {totals['winners']} / {totals['losers']} / "
        f"{totals['flat']} |"
    )
    for kind, count in sorted(exit_kind_counts(result).items()):
        add(f"| Exit: {kind} | {count} |")
    add("")
    add(
        f"Arithmetic check: net = gross - cost, and the cost is exactly "
        f"{sim.format_paise(result.cost_paise)} x {totals['trades']} executed trades = "
        f"{sim.format_paise(totals['cost_paise'])}."
    )
    add("")
    add("Rare shapes, counted rather than assumed -- a zero here means this window carries NO")
    add("real-data witness for that branch, which is a fact about the window, not about the code")
    add("(the branches themselves are covered by hand-computed fixtures in `tests/test_simulate.py`):")
    add("")
    add("| Shape | Days |")
    add("|---|---|")
    for shape, count in shape_counts(result).items():
        add(f"| {shape} | {count} |")
    add("")

    add("## 5. The named golden")
    add("")
    golden = _find_golden(result)
    if golden is None or golden.record is None:
        add(f"*{GOLDEN_SYMBOL} {GOLDEN_DAY.isoformat()} is not in this run's window.*")
    else:
        record = golden.record
        add(
            f"**{GOLDEN_SYMBOL} {GOLDEN_DAY.isoformat()}** -- the real Rule-3 outside-bar day "
            "chunk 7 walked candle by candle and REVIEW_7 re-derived from the stores. Its "
            "money is asserted in the suite (`tests/test_simulate.py`), read from this same "
            "store:"
        )
        add("")
        add(
            f"    POC {_poc_text(record.poc_paise)}"
            f"  entry {_price(record.entry_paise)}  stop {_price(record.stop_paise)}"
            f"  target {_price(record.target_paise)}"
        )
        add(
            f"    per-share risk {_price(record.per_share_risk_paise)}"
            f"  qty floor({result.risk_per_trade_paise:,} / "
            f"{record.per_share_risk_paise:,}) = {record.qty}"
        )
        add(
            f"    {record.exit_kind} at {_price(record.exit_paise)}"
            f"  gross {sim.format_paise(record.gross_pnl_paise)}"
            f"  cost {sim.format_paise(record.cost_paise)}"
            f"  net {sim.format_paise(record.net_pnl_paise)}"
        )
    add("")

    add("## 6. Every priced trade")
    add("")
    add(
        "One row per day that produced an entry signal. Prices in rupees; qty, gross and net "
        "are exact integer paise internally (CONTEXT 7-E11)."
    )
    add("")
    add(
        "| # | Symbol | Date | Side | Entry | Stop | Target | Risk/sh | Qty | Exit kind | "
        "Exit | Gross | Net | Flags |"
    )
    add("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for index, priced in enumerate(result.entered, start=1):
        record = priced.record
        if record is None:  # pragma: no cover -- `entered` selects records that exist
            continue
        flags = ", ".join(record.flags) if record.flags else ""
        if record.gap_entry:
            flags = f"gap, {flags}" if flags else "gap"
        if record.tie_case:
            flags = f"rule-3 tie, {flags}" if flags else "rule-3 tie"
        add(
            f"| {index} | {record.symbol} | {record.day.isoformat()} | {record.side} | "
            f"{_price(record.entry_paise)} | {_price(record.stop_paise)} | "
            f"{_price(record.target_paise)} | {_price(record.per_share_risk_paise)} | "
            f"{record.qty} | {record.exit_kind or '-'} | {_price(record.exit_paise)} | "
            f"{sim.format_paise(record.gross_pnl_paise)} | "
            f"{sim.format_paise(record.net_pnl_paise)} | {flags} |"
        )
    add("")

    add("## 7. Invariants asserted over every priced day")
    add("")
    for line in invariant_report(result):
        add(f"* {line}")
    add("")
    return "\n".join(lines) + "\n"


def _find_golden(result: SweepResult) -> PricedDay | None:
    for priced in result.days:
        if priced.symbol == GOLDEN_SYMBOL and priced.day == GOLDEN_DAY:
            return priced
    return None


def invariant_report(result: SweepResult) -> list[str]:
    """Re-check the CONTEXT 3.5 properties over the whole run and report them as PASS lines."""
    lines: list[str] = []
    entered = result.entered
    risk_budget = result.risk_per_trade_paise

    over_budget = [
        priced
        for priced in entered
        if priced.record is not None
        and priced.record.per_share_risk_paise is not None
        and priced.record.qty * priced.record.per_share_risk_paise > risk_budget
    ]
    lines.append(
        f"`qty x per-share risk <= {sim.format_paise(risk_budget)}` on all "
        f"{len(entered)} signalled days: {'PASS' if not over_budget else 'FAIL'} "
        f"({len(over_budget)} violations)"
    )

    not_tight = [
        priced
        for priced in entered
        if priced.record is not None
        and priced.record.per_share_risk_paise is not None
        and (priced.record.qty + 1) * priced.record.per_share_risk_paise <= risk_budget
    ]
    lines.append(
        f"the floor is tight -- `(qty + 1) x per-share risk > {sim.format_paise(risk_budget)}`: "
        f"{'PASS' if not not_tight else 'FAIL'} ({len(not_tight)} violations)"
    )

    bad_money = [
        priced
        for priced in result.executed
        if priced.record is not None
        and priced.record.net_pnl_paise
        != priced.record.gross_pnl_paise - result.cost_paise
    ]
    lines.append(
        f"`net == gross - {sim.format_paise(result.cost_paise)}` on all "
        f"{len(result.executed)} executed trades: {'PASS' if not bad_money else 'FAIL'} "
        f"({len(bad_money)} violations)"
    )

    bad_target = []
    bad_stop = []
    for priced in result.executed:
        record = priced.record
        if record is None or record.per_share_risk_paise is None:  # pragma: no cover
            continue
        if record.exit_kind == sim.EXIT_TARGET and record.gross_pnl_paise != (
            record.qty * 3 * record.per_share_risk_paise
        ):
            bad_target.append(record)
        if record.exit_kind == sim.EXIT_STOP and record.gross_pnl_paise != (
            -record.qty * record.per_share_risk_paise
        ):
            bad_stop.append(record)
    lines.append(
        "every target exit pays exactly `qty x 3 x per-share risk`: "
        f"{'PASS' if not bad_target else 'FAIL'} ({len(bad_target)} violations)"
    )
    lines.append(
        "every stop exit pays exactly `-qty x per-share risk`: "
        f"{'PASS' if not bad_stop else 'FAIL'} ({len(bad_stop)} violations)"
    )

    unpaid = [
        priced
        for priced in result.days
        if priced.record is not None
        and not priced.record.executed
        and (priced.record.cost_paise, priced.record.gross_pnl_paise) != (0, 0)
    ]
    lines.append(
        f"no non-executed day pays a cost or carries PnL: {'PASS' if not unpaid else 'FAIL'} "
        f"({len(unpaid)} violations)"
    )

    # Every square-off must fill at the CLOSE of the candle its marker names, and on a whole
    # day that candle is the 15:00-stamped one (R1-Q18/E12). Checked against the bars, not
    # against the record's own claim.
    square_offs = [
        priced
        for priced in result.executed
        if priced.record is not None and priced.record.exit_kind == sim.EXIT_SQUARE_OFF
    ]
    mispriced = []
    off_grid = []
    for priced in square_offs:
        record = priced.record
        if record is None:  # pragma: no cover
            continue
        marked = [bar for bar in priced.stock_day.bars if bar.stamp == record.exit_stamp]
        if not marked or int(marked[0].close_paise) != record.exit_paise:
            mispriced.append(record)
        if record.exit_stamp is not None and record.exit_stamp.time() != _SQUARE_OFF_TIME:
            off_grid.append(record)
    lines.append(
        f"every square-off fills at the marked candle's own close: "
        f"{'PASS' if not mispriced else 'FAIL'} ({len(mispriced)} of {len(square_offs)} wrong)"
    )
    lines.append(
        f"every square-off marker is the 15:00-stamped candle (the one closing 15:15): "
        f"{'PASS' if not off_grid else 'FAIL'} ({len(off_grid)} elsewhere)"
    )
    return lines


# --- CLI ----------------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Price the chunk-7 sweep and write the chunk-8 evidence pack.",
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help=f"output path (default: {DEFAULT_OUT})")
    parser.add_argument("--data-dir", default=None, help="data dir (default: config paths.data_root)")
    parser.add_argument("--cache-dir", default=None, help="instrument-master cache dir")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    context = build_context(
        data_dir=Path(args.data_dir) if args.data_dir else None,
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
    )
    print(
        f"pricing {len(SWEEP_SYMBOLS)} symbols {SWEEP_START.isoformat()}.."
        f"{SWEEP_END.isoformat()} at risk {sim.format_paise(context.risk_per_trade_paise)} / "
        f"cost {sim.format_paise(context.cost_paise)} per round trip"
    )
    result = run_sweep(context, progress=print)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_markdown(result, command="python docs/evidence/chunk8_sweep.py"),
        encoding="utf-8",
        newline="\n",
    )
    totals = money_totals(result)
    print(
        f"{len(result.days)} stock-days walked, {len(result.entered)} signalled, "
        f"{totals['trades']} executed; net {sim.format_paise(totals['net_paise'])}"
    )
    for line in invariant_report(result):
        print(f"  {line}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
