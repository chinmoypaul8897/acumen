"""The portfolio layer: PURE functions over the run ledger (chunk 9A).

Nothing here opens a file, reads a clock or touches a store. It takes the rows chunk 9's
runner wrote (:class:`acumen.backtest.LedgerRow`) and produces the portfolio quantities
CONTEXT 3.5 and CONTEXT 7-E13 name -- and nothing that is not named there.

**Take-all portfolio semantics (CONTEXT 3.5, Round-3 Q40 option d, TRADER-FINAL).** Every
signal is taken, on every stock, concurrently, each sized by the fixed-INR-risk rule, with NO
capital or concurrency constraint. There is one equity curve, ``capital + cumulative PnL``,
and because the risk per trade is a fixed rupee amount the curve is a plain cumulative SUM --
no compounding, no position scaling. The disclosures the trader's own answer demands are
computed beside it: max concurrent positions, peak simultaneous notional, and the full
distribution of daily concurrent-trade counts.

**Capital-infeasibility flags (the same answer's second half).** They are computed POST-HOC
from the ledger and only when the config supplies BOTH ``capital_reference`` and
``margin_basis``. While either is null -- which is the state until the trader answers Q43 --
:func:`capital_flags` computes nothing and returns the pending note verbatim, which every
output then prints. There is no default figure anywhere in this module.

**Money is integer paise; every ratio is a Fraction; the two statistics that need a square
root are Decimal.** No float is produced anywhere in this file (CONTEXT 7-E11).

**Two E13 metrics are BLOCKED on the architect, not computed silently** -- see
:data:`OUTLIERS_NOT_COMPUTED` and :data:`INTRA_TRADE_PROVISIONAL` and QUESTIONS.md Q-16.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from typing import Iterable, Mapping, Sequence

from .backtest import LedgerRow
from .signals import LONG, SHORT

#: CONTEXT 3.5: "Capital: INR 1,00,000 (R1-Q21a)" -- the base of the equity curve and the
#: denominator of "return on initial capital". It is NOT the Q40-d flag figure (that one is
#: the trader's pending Q43 answer, and it is config-supplied or absent).
DEFAULT_INITIAL_CAPITAL_PAISE: int = 10_000_000

#: E13's annualization convention, stated by the spec itself: "Sharpe & Sortino on the DAILY
#: equity series, risk-free rate 0, annualized x sqrt(252)".
TRADING_DAYS_PER_YEAR: int = 252

#: CONTEXT 7-E13 lists "outliers" among the report metrics and fixes NO definition for it --
#: no threshold, no rule, no reference. Under CLAUDE.md rule 1 this module does not invent one.
OUTLIERS_NOT_COMPUTED: str = (
    "outliers NOT computed -- CONTEXT 7-E13 names the metric but fixes no definition "
    "(no threshold, no rule); QUESTIONS.md Q-16(a) is pending with the architect"
)

#: The intra-trade / intrabar drawdown and run-up E13 asks for need an intraday equity PATH,
#: and a take-all portfolio of concurrent intraday trades does not have an observable one: the
#: ledger holds each trade's MFE and MAE but not WHEN inside the day each occurred. The
#: construction below is the honest WORST/BEST case (every same-day excursion assumed to
#: coincide), it is labelled provisional everywhere it is printed, and the convention is with
#: the architect as QUESTIONS.md Q-16(b).
INTRA_TRADE_PROVISIONAL: str = (
    "PROVISIONAL construction -- the intraday equity path of concurrent trades is not "
    "observable from the ledger; this assumes every same-day excursion coincides (worst case "
    "for the drawdown, best case for the run-up). QUESTIONS.md Q-16(b) is pending"
)

#: What every output says while the trader's Q43 answer is outstanding (same words as the
#: runner's manifest -- one sentence, one meaning).
CAPITAL_FLAGS_PENDING_NOTE: str = (
    "capital-infeasibility flags NOT computed -- the trader's Q43 answer is pending"
)


# --- selection ------------------------------------------------------------------------------


def executed(rows: Sequence[LedgerRow]) -> tuple[LedgerRow, ...]:
    """The rows that actually opened a position (``qty > 0``), in ledger order."""
    return tuple(row for row in rows if row.executed)


def for_side(rows: Sequence[LedgerRow], side: str) -> tuple[LedgerRow, ...]:
    return tuple(row for row in rows if row.side == side)


def for_symbol(rows: Sequence[LedgerRow], symbol: str) -> tuple[LedgerRow, ...]:
    wanted = symbol.strip().upper()
    return tuple(row for row in rows if row.symbol == wanted)


def walked_days(rows: Sequence[LedgerRow]) -> tuple[date, ...]:
    """Every distinct day the run walked, oldest first -- the daily series' own index.

    The series covers days that traded nothing too: a flat day is a real observation for a
    daily Sharpe, and dropping it would silently annualize a different sample.
    """
    return tuple(sorted({row.day for row in rows}))


# --- the daily series and the equity curve --------------------------------------------------


@dataclass(frozen=True)
class DailyPnL:
    """One trading day of the portfolio: what closed that day, and for how much."""

    day: date
    trades: int
    gross_paise: int
    cost_paise: int
    net_paise: int
    mfe_paise: int
    mae_paise: int


def daily_pnl(
    rows: Sequence[LedgerRow], *, days: Sequence[date] | None = None
) -> tuple[DailyPnL, ...]:
    """Net PnL per day over EVERY walked day, oldest first. PURE.

    Every trade opens and closes inside its own day (CONTEXT 3.1 squares off at 15:15), so
    "trade-close order" and date order are the same ordering and no trade can straddle a day.

    ``days`` overrides the index -- E13's Long and Short columns are computed over the SAME
    trading days as the All column, so their daily series are the same length and their Sharpe
    ratios are annualized over the same sample.
    """
    index = tuple(days) if days is not None else walked_days(rows)
    by_day: dict[date, list[LedgerRow]] = {day: [] for day in index}
    for row in executed(rows):
        by_day.setdefault(row.day, []).append(row)
    series = []
    for day in sorted(by_day):
        day_rows = by_day[day]
        series.append(
            DailyPnL(
                day=day,
                trades=len(day_rows),
                gross_paise=sum(row.gross_pnl_paise for row in day_rows),
                cost_paise=sum(row.cost_paise for row in day_rows),
                net_paise=sum(row.net_pnl_paise for row in day_rows),
                mfe_paise=sum(row.mfe_paise or 0 for row in day_rows),
                mae_paise=sum(row.mae_paise or 0 for row in day_rows),
            )
        )
    return tuple(series)


@dataclass(frozen=True)
class EquityPoint:
    """One day of the equity curve, plus the PROVISIONAL intraday band (Q-16(b))."""

    day: date
    net_paise: int
    equity_paise: int
    low_equity_paise: int
    high_equity_paise: int


def equity_curve(
    series: Sequence[DailyPnL], initial_capital_paise: int = DEFAULT_INITIAL_CAPITAL_PAISE
) -> tuple[EquityPoint, ...]:
    """``capital + cumulative net PnL`` per day (CONTEXT 3.5). A plain cumulative SUM. PURE.

    The fixed-INR-risk rule means the position size never depends on the running equity, so
    compounding would be a fiction: the curve adds, it does not multiply. The low/high band on
    each point is the provisional intraday envelope described in
    :data:`INTRA_TRADE_PROVISIONAL` -- the day's costs are charged in both, because a trade
    that opened has paid its round trip whichever way the price went.
    """
    points: list[EquityPoint] = []
    equity = int(initial_capital_paise)
    for day in series:
        opening = equity
        equity = equity + day.net_paise
        points.append(
            EquityPoint(
                day=day.day,
                net_paise=day.net_paise,
                equity_paise=equity,
                low_equity_paise=min(equity, opening + day.mae_paise - day.cost_paise),
                high_equity_paise=max(equity, opening + day.mfe_paise - day.cost_paise),
            )
        )
    return tuple(points)


# --- drawdown / run-up ------------------------------------------------------------------------


@dataclass(frozen=True)
class Excursion:
    """A max drawdown or max run-up: its size, its dates and how long it took."""

    amount_paise: int
    pct: Fraction | None
    peak_day: date | None
    trough_day: date | None
    duration_days: int
    recovered_on: date | None

    @property
    def is_empty(self) -> bool:
        return self.amount_paise == 0


def max_drawdown(points: Sequence[EquityPoint], *, intrabar: bool = False) -> Excursion:
    """The largest peak-to-trough fall of the equity curve. PURE.

    ``intrabar=False`` is E13's "equity close-to-close" form: both the peak and the trough are
    daily CLOSING equity. ``intrabar=True`` is the provisional intra-trade form -- the peak is
    still a closing equity (a peak that never closed is not an equity anyone held) and the
    trough is the day's provisional LOW (:data:`INTRA_TRADE_PROVISIONAL`).

    The running peak starts at the run's OPENING capital -- the equity before the first day --
    not at the first day's close, because a fall measured from a close that came after the low
    is not a fall anyone lived through. A ``peak_day`` of ``None`` therefore means "the run's
    opening capital", and it counts as the observation before the first day.

    ``duration_days`` counts the observations from the peak to the trough; it is a count of
    daily observations, which is what a daily series can honestly report. ``recovered_on`` is
    the first later day whose closing equity reaches the peak again, or ``None`` if the series
    ends under water.
    """
    if not points:
        return Excursion(0, None, None, None, 0, None)
    peak = points[0].equity_paise - points[0].net_paise  # the opening capital
    peak_day: date | None = None
    best = Excursion(0, Fraction(0), peak_day, peak_day, 0, None)
    peak_index = -1
    for index, point in enumerate(points):
        low = point.low_equity_paise if intrabar else point.equity_paise
        fall = peak - low
        if fall > best.amount_paise:
            best = Excursion(
                amount_paise=fall,
                pct=Fraction(fall, peak) if peak != 0 else None,
                peak_day=peak_day,
                trough_day=point.day,
                duration_days=index - peak_index,
                recovered_on=None,
            )
        if point.equity_paise > peak:
            peak = point.equity_paise
            peak_day = point.day
            peak_index = index
    if best.trough_day is not None and best.amount_paise > 0:
        recovery = _first_recovery(points, best)
        best = Excursion(
            best.amount_paise,
            best.pct,
            best.peak_day,
            best.trough_day,
            best.duration_days,
            recovery,
        )
    return best


def max_run_up(points: Sequence[EquityPoint], *, intrabar: bool = False) -> Excursion:
    """The largest trough-to-peak rise -- the mirror of :func:`max_drawdown`. PURE.

    Symmetrically, the running trough starts at the opening capital and a ``trough_day`` of
    ``None`` means the run started there.
    """
    if not points:
        return Excursion(0, None, None, None, 0, None)
    trough = points[0].equity_paise - points[0].net_paise  # the opening capital
    trough_day: date | None = None
    trough_index = -1
    best = Excursion(0, Fraction(0), trough_day, trough_day, 0, None)
    for index, point in enumerate(points):
        high = point.high_equity_paise if intrabar else point.equity_paise
        rise = high - trough
        if rise > best.amount_paise:
            best = Excursion(
                amount_paise=rise,
                pct=Fraction(rise, trough) if trough != 0 else None,
                peak_day=point.day,
                trough_day=trough_day,
                duration_days=index - trough_index,
                recovered_on=None,
            )
        if point.equity_paise < trough:
            trough = point.equity_paise
            trough_day = point.day
            trough_index = index
    return best


def _first_recovery(points: Sequence[EquityPoint], excursion: Excursion) -> date | None:
    seen_trough = False
    peak_equity = None
    for point in points:
        if point.day == excursion.peak_day:
            peak_equity = point.equity_paise
        if point.day == excursion.trough_day:
            seen_trough = True
            continue
        if seen_trough and peak_equity is not None and point.equity_paise >= peak_equity:
            return point.day
    return None


# --- risk-adjusted return (E13's own conventions) --------------------------------------------


def daily_returns(points: Sequence[EquityPoint]) -> tuple[Fraction, ...]:
    """Simple daily returns of the equity curve, exactly (Fractions, never floats). PURE."""
    returns: list[Fraction] = []
    for previous, current in zip(points, points[1:]):
        if previous.equity_paise == 0:
            continue
        returns.append(
            Fraction(current.equity_paise - previous.equity_paise, previous.equity_paise)
        )
    return tuple(returns)


def sharpe(points: Sequence[EquityPoint]) -> Decimal | None:
    """E13's Sharpe: daily equity returns, risk-free 0, annualized x sqrt(252). PURE.

    The dispersion is the SAMPLE standard deviation (n-1). Returns ``None`` when there are
    fewer than two returns or the sample is perfectly flat -- an undefined ratio is reported as
    undefined, never as zero.
    """
    returns = daily_returns(points)
    if len(returns) < 2:
        return None
    mean = sum(returns, Fraction(0)) / len(returns)
    variance = sum(((r - mean) ** 2 for r in returns), Fraction(0)) / (len(returns) - 1)
    if variance == 0:
        return None
    return _annualize(mean, variance)


def sortino(points: Sequence[EquityPoint]) -> Decimal | None:
    """E13's Sortino: the same, with only the NEGATIVE returns in the denominator. PURE.

    Downside deviation is measured against a target of zero (the risk-free rate E13 fixes),
    averaged over ALL observations -- the standard construction, so a strategy with few losing
    days is not flattered by a smaller denominator sample.
    """
    returns = daily_returns(points)
    if len(returns) < 2:
        return None
    mean = sum(returns, Fraction(0)) / len(returns)
    downside = sum(((r ** 2) for r in returns if r < 0), Fraction(0)) / len(returns)
    if downside == 0:
        return None
    return _annualize(mean, downside)


def _annualize(mean: Fraction, variance: Fraction) -> Decimal:
    deviation = _decimal(variance).sqrt()
    if deviation == 0:  # pragma: no cover -- guarded by the callers
        return Decimal(0)
    root = Decimal(TRADING_DAYS_PER_YEAR).sqrt()
    return (_decimal(mean) / deviation) * root


def _decimal(value: Fraction) -> Decimal:
    return Decimal(value.numerator) / Decimal(value.denominator)


# --- the take-all disclosures (CONTEXT 3.5 / Q40-d) -------------------------------------------


@dataclass(frozen=True)
class ConcurrencyPeak:
    """When the portfolio held the most at once, and how much that was."""

    positions: int
    notional_paise: int
    at: datetime | None
    symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class Disclosures:
    """Everything CONTEXT 3.5's take-all answer requires the report to disclose."""

    max_concurrent_positions: ConcurrencyPeak
    peak_simultaneous_notional: ConcurrencyPeak
    daily_trade_counts: tuple[tuple[int, int], ...]  # (trades on a day, how many such days)
    max_daily_trades: int
    total_executed: int
    largest_single_notional_paise: int


def disclosures(rows: Sequence[LedgerRow]) -> Disclosures:
    """Max concurrency, peak simultaneous notional and the daily-count distribution. PURE.

    The sweep opens a position at its entry candle's CLOSE and closes it at its exit candle's
    close (CONTEXT 3.4: the entry price IS a close, and the exit is priced at a level or a
    close on its own candle). At an instant where one trade opens and another closes, the OPEN
    is processed first -- the pessimistic reading, and the only one that cannot understate what
    the trader's capital would have had to carry.
    """
    trades = executed(rows)
    events: list[tuple[datetime, int, int, str]] = []
    for row in trades:
        if row.entry_close_stamp is None:
            continue
        exit_stamp = row.exit_close_stamp or row.entry_close_stamp
        events.append((row.entry_close_stamp, 0, row.notional_paise, row.symbol))
        events.append((exit_stamp, 1, -row.notional_paise, row.symbol))
    events.sort(key=lambda event: (event[0], event[1]))

    live: dict[str, int] = {}
    positions = notional = 0
    best_positions = ConcurrencyPeak(0, 0, None)
    best_notional = ConcurrencyPeak(0, 0, None)
    for stamp, kind, delta, symbol in events:
        if kind == 0:
            positions += 1
            live[symbol] = live.get(symbol, 0) + 1
        else:
            positions -= 1
            live[symbol] = live.get(symbol, 0) - 1
            if live[symbol] <= 0:
                live.pop(symbol, None)
        notional += delta
        if kind != 0:
            continue
        snapshot = tuple(sorted(live))
        if positions > best_positions.positions:
            best_positions = ConcurrencyPeak(positions, notional, stamp, snapshot)
        if notional > best_notional.notional_paise:
            best_notional = ConcurrencyPeak(positions, notional, stamp, snapshot)

    counts: dict[int, int] = {}
    for day in daily_pnl(rows):
        counts[day.trades] = counts.get(day.trades, 0) + 1
    return Disclosures(
        max_concurrent_positions=best_positions,
        peak_simultaneous_notional=best_notional,
        daily_trade_counts=tuple(sorted(counts.items())),
        max_daily_trades=max(counts) if counts else 0,
        total_executed=len(trades),
        largest_single_notional_paise=max((row.notional_paise for row in trades), default=0),
    )


# --- the capital-infeasibility flags (Q40-d second half; BLOCKED on Q43) ----------------------


@dataclass(frozen=True)
class TradeFlag:
    """One trade the trader's capital could not have taken, and by how much."""

    symbol: str
    day: date
    notional_paise: int
    over_by_paise: int
    tier: str


@dataclass(frozen=True)
class CapitalFlagReport:
    """The Q40-d flags -- or the recorded reason there are none yet."""

    computed: bool
    note: str
    capital_reference_paise: int | None = None
    margin_basis: Decimal | None = None
    beyond_cash: tuple[TradeFlag, ...] = ()
    beyond_margin: tuple[TradeFlag, ...] = ()

    @property
    def flagged_trades(self) -> int:
        return len({(flag.symbol, flag.day) for flag in self.beyond_cash + self.beyond_margin})


def capital_flags(
    rows: Sequence[LedgerRow],
    *,
    capital_reference_paise: int | None,
    margin_basis: Decimal | None,
) -> CapitalFlagReport:
    """CONTEXT 3.5's per-trade capital-infeasibility flags, computed POST-HOC. PURE.

    The trader answered Q40 with option (d): take every signal, and DISCLOSE the trades his
    capital could not actually have taken. Which capital figure the flags must use is his to
    say (Q43) and it has not arrived, so with either input ``None`` this computes NOTHING and
    returns :data:`CAPITAL_FLAGS_PENDING_NOTE` for the report to print verbatim. No default is
    substituted -- flagging a real trade "infeasible" against a guessed figure would put this
    repo's number in place of his.

    When both are supplied: a trade is beyond CASH when its notional (qty x entry) exceeds the
    capital reference, and beyond MARGIN when it exceeds ``capital_reference x margin_basis``
    (CONTEXT 3.5's "typical-MIS tiers"). Nothing is capped, skipped or resized -- take-all is
    unchanged; the flags are a disclosure, not a constraint.
    """
    if capital_reference_paise is None or margin_basis is None:
        return CapitalFlagReport(
            computed=False,
            note=CAPITAL_FLAGS_PENDING_NOTE,
            capital_reference_paise=capital_reference_paise,
            margin_basis=margin_basis,
        )
    margin_limit = int(Decimal(capital_reference_paise) * margin_basis)
    cash: list[TradeFlag] = []
    margin: list[TradeFlag] = []
    for row in executed(rows):
        if row.notional_paise > capital_reference_paise:
            cash.append(
                TradeFlag(
                    row.symbol,
                    row.day,
                    row.notional_paise,
                    row.notional_paise - capital_reference_paise,
                    "cash",
                )
            )
        if row.notional_paise > margin_limit:
            margin.append(
                TradeFlag(
                    row.symbol,
                    row.day,
                    row.notional_paise,
                    row.notional_paise - margin_limit,
                    "margin",
                )
            )
    return CapitalFlagReport(
        computed=True,
        note=(
            "computed POST-HOC from the ledger (CONTEXT 3.5 / Q40-d); take-all is unchanged "
            "and no trade was capped, skipped or resized"
        ),
        capital_reference_paise=capital_reference_paise,
        margin_basis=margin_basis,
        beyond_cash=tuple(cash),
        beyond_margin=tuple(margin),
    )


# --- the buy & hold benchmark (E13's own definition) ------------------------------------------


@dataclass(frozen=True)
class Benchmark:
    """E13's benchmark: equal-weight, bought at the first trade date's close, held to the end."""

    first_day: date
    last_day: date
    symbols: tuple[str, ...]
    start_value_paise: int
    end_value_paise: Fraction
    total_return: Fraction | None
    note: str


def buy_and_hold(
    closes: Mapping[str, Mapping[date, int]],
    *,
    first_day: date,
    last_day: date,
    initial_capital_paise: int = DEFAULT_INITIAL_CAPITAL_PAISE,
) -> Benchmark:
    """CONTEXT 7-E13's buy&hold benchmark, exactly as E13 defines it. PURE.

    "equal-weight portfolio of the traded universe, bought at first trade date's close, held to
    period end". Capital is split equally across the symbols and the units bought are exact
    Fractions -- fractional units, because rounding to whole shares would silently make the
    benchmark depend on each stock's price level, which is not what "equal-weight" means. A
    symbol with no close on the first day is EXCLUDED from the benchmark and named in the note
    rather than back-filled.
    """
    usable = tuple(
        sorted(symbol for symbol in closes if closes[symbol].get(first_day) is not None)
    )
    skipped = tuple(sorted(set(closes) - set(usable)))
    if not usable:
        return Benchmark(
            first_day,
            last_day,
            (),
            initial_capital_paise,
            Fraction(initial_capital_paise),
            None,
            "no symbol has a close on the first trade date; benchmark not computed",
        )
    slice_paise = Fraction(initial_capital_paise, len(usable))
    end_value = Fraction(0)
    for symbol in usable:
        first_close = closes[symbol][first_day]
        last_close = _last_close_on_or_before(closes[symbol], last_day)
        end_value += slice_paise * Fraction(last_close, first_close)
    note = "equal-weight, fractional units, no rebalancing (CONTEXT 7-E13)"
    if skipped:
        note += "; excluded (no close on the first trade date): " + ", ".join(skipped)
    return Benchmark(
        first_day=first_day,
        last_day=last_day,
        symbols=usable,
        start_value_paise=initial_capital_paise,
        end_value_paise=end_value,
        total_return=(end_value - initial_capital_paise) / initial_capital_paise,
        note=note,
    )


def _last_close_on_or_before(series: Mapping[date, int], day: date) -> int:
    candidates = [stamp for stamp in series if stamp <= day]
    if not candidates:  # pragma: no cover -- callers pass a series starting at first_day
        raise ValueError("no close on or before the benchmark end date")
    return series[max(candidates)]


# --- the E13 metric set -----------------------------------------------------------------------


@dataclass(frozen=True)
class Metrics:
    """CONTEXT 7-E13's authoritative list, computed over one set of ledger rows.

    Every money field is integer paise; every ratio is an exact :class:`~fractions.Fraction`;
    Sharpe and Sortino are :class:`~decimal.Decimal` because they need a square root. Two
    entries are deliberately NOT numbers -- ``outliers`` and the two ``intra_*`` excursions --
    see :data:`OUTLIERS_NOT_COMPUTED` and :data:`INTRA_TRADE_PROVISIONAL`.
    """

    label: str
    # --- money
    net_pnl_paise: int
    gross_profit_paise: int
    gross_loss_paise: int
    profit_factor: Fraction | None
    commission_paise: int
    expected_payoff_paise: Fraction | None
    # --- counts
    total_trades: int
    open_trades: int
    winners: int
    losers: int
    flat: int
    percent_profitable: Fraction | None
    # --- averages and extremes
    avg_pnl_paise: Fraction | None
    avg_profit_paise: Fraction | None
    avg_loss_paise: Fraction | None
    avg_profit_over_avg_loss: Fraction | None
    largest_win_paise: int
    largest_win_pct_of_notional: Fraction | None
    largest_win_pct_of_gross_profit: Fraction | None
    largest_loss_paise: int
    largest_loss_pct_of_notional: Fraction | None
    largest_loss_pct_of_gross_loss: Fraction | None
    outliers: None
    outliers_note: str
    # --- equity
    initial_capital_paise: int
    final_equity_paise: int
    return_on_initial_capital: Fraction
    cagr: Decimal | None
    max_drawdown: Excursion
    max_run_up: Excursion
    intra_trade_max_drawdown: Excursion
    intra_trade_max_run_up: Excursion
    intra_trade_note: str
    sharpe: Decimal | None
    sortino: Decimal | None
    # --- excursions
    avg_mfe_paise: Fraction | None
    avg_mae_paise: Fraction | None
    largest_mfe_paise: int
    largest_mae_paise: int
    # --- context
    first_day: date | None
    last_day: date | None
    trading_days: int


def metrics(
    rows: Sequence[LedgerRow],
    *,
    label: str = "All",
    initial_capital_paise: int = DEFAULT_INITIAL_CAPITAL_PAISE,
    days: Sequence[date] | None = None,
) -> Metrics:
    """The whole E13 list over ``rows``. PURE.

    Pass every walked row (refusals included): the daily series is built over the days the run
    WALKED, so a day that traded nothing is a flat observation rather than a missing one.
    Filter with :func:`for_side` / :func:`for_symbol` for E13's All/Long/Short split and the
    per-symbol table -- each subset keeps its own equity curve, so its drawdown is that
    subset's own, not a slice of the portfolio's.
    """
    index = tuple(days) if days is not None else walked_days(rows)
    series = daily_pnl(rows, days=index)
    points = equity_curve(series, initial_capital_paise)
    trades = executed(rows)
    wins = [row for row in trades if row.net_pnl_paise > 0]
    losses = [row for row in trades if row.net_pnl_paise < 0]
    flats = [row for row in trades if row.net_pnl_paise == 0]

    gross_profit = sum(row.gross_pnl_paise for row in trades if row.gross_pnl_paise > 0)
    gross_loss = sum(row.gross_pnl_paise for row in trades if row.gross_pnl_paise < 0)
    net = sum(row.net_pnl_paise for row in trades)
    commission = sum(row.cost_paise for row in trades)

    largest_win = max((row for row in trades), key=lambda r: r.net_pnl_paise, default=None)
    largest_loss = min((row for row in trades), key=lambda r: r.net_pnl_paise, default=None)
    if largest_win is not None and largest_win.net_pnl_paise <= 0:
        largest_win = None
    if largest_loss is not None and largest_loss.net_pnl_paise >= 0:
        largest_loss = None

    final_equity = points[-1].equity_paise if points else initial_capital_paise
    span = tuple(point.day for point in points)
    return Metrics(
        label=label,
        net_pnl_paise=net,
        gross_profit_paise=gross_profit,
        gross_loss_paise=gross_loss,
        profit_factor=(
            Fraction(gross_profit, -gross_loss) if gross_loss < 0 else None
        ),
        commission_paise=commission,
        expected_payoff_paise=_ratio(net, len(trades)),
        total_trades=len(trades),
        open_trades=0,
        winners=len(wins),
        losers=len(losses),
        flat=len(flats),
        percent_profitable=_ratio(len(wins), len(trades)),
        avg_pnl_paise=_ratio(net, len(trades)),
        avg_profit_paise=_ratio(sum(row.net_pnl_paise for row in wins), len(wins)),
        avg_loss_paise=_ratio(sum(row.net_pnl_paise for row in losses), len(losses)),
        avg_profit_over_avg_loss=_avg_ratio(wins, losses),
        largest_win_paise=0 if largest_win is None else largest_win.net_pnl_paise,
        largest_win_pct_of_notional=_pct_of_notional(largest_win),
        largest_win_pct_of_gross_profit=(
            None
            if largest_win is None or gross_profit == 0
            else Fraction(largest_win.gross_pnl_paise, gross_profit)
        ),
        largest_loss_paise=0 if largest_loss is None else largest_loss.net_pnl_paise,
        largest_loss_pct_of_notional=_pct_of_notional(largest_loss),
        largest_loss_pct_of_gross_loss=(
            None
            if largest_loss is None or gross_loss == 0
            else Fraction(largest_loss.gross_pnl_paise, gross_loss)
        ),
        outliers=None,
        outliers_note=OUTLIERS_NOT_COMPUTED,
        initial_capital_paise=initial_capital_paise,
        final_equity_paise=final_equity,
        return_on_initial_capital=Fraction(
            final_equity - initial_capital_paise, initial_capital_paise
        ),
        cagr=_cagr(initial_capital_paise, final_equity, span),
        max_drawdown=max_drawdown(points),
        max_run_up=max_run_up(points),
        intra_trade_max_drawdown=max_drawdown(points, intrabar=True),
        intra_trade_max_run_up=max_run_up(points, intrabar=True),
        intra_trade_note=INTRA_TRADE_PROVISIONAL,
        sharpe=sharpe(points),
        sortino=sortino(points),
        avg_mfe_paise=_ratio(sum(row.mfe_paise or 0 for row in trades), len(trades)),
        avg_mae_paise=_ratio(sum(row.mae_paise or 0 for row in trades), len(trades)),
        largest_mfe_paise=max((row.mfe_paise or 0 for row in trades), default=0),
        largest_mae_paise=min((row.mae_paise or 0 for row in trades), default=0),
        first_day=span[0] if span else None,
        last_day=span[-1] if span else None,
        trading_days=len(span),
    )


def side_split(
    rows: Sequence[LedgerRow], *, initial_capital_paise: int = DEFAULT_INITIAL_CAPITAL_PAISE
) -> dict[str, Metrics]:
    """E13's All / Long / Short column split. PURE.

    A side's subset keeps every walked day, so its daily series has the same index as the
    portfolio's and its Sharpe is annualized over the same sample.
    """
    index = walked_days(rows)
    return {
        "All": metrics(
            rows, label="All", initial_capital_paise=initial_capital_paise, days=index
        ),
        "Long": metrics(
            for_side(rows, LONG),
            label="Long",
            initial_capital_paise=initial_capital_paise,
            days=index,
        ),
        "Short": metrics(
            for_side(rows, SHORT),
            label="Short",
            initial_capital_paise=initial_capital_paise,
            days=index,
        ),
    }


def per_symbol(
    rows: Sequence[LedgerRow], *, initial_capital_paise: int = DEFAULT_INITIAL_CAPITAL_PAISE
) -> dict[str, Metrics]:
    """E13's per-symbol breakdown table. PURE."""
    symbols = sorted({row.symbol for row in rows})
    index = walked_days(rows)
    return {
        symbol: metrics(
            for_symbol(rows, symbol),
            label=symbol,
            initial_capital_paise=initial_capital_paise,
            days=index,
        )
        for symbol in symbols
    }


def _ratio(total: int, count: int) -> Fraction | None:
    return None if count == 0 else Fraction(total, count)


def _avg_ratio(
    wins: Sequence[LedgerRow], losses: Sequence[LedgerRow]
) -> Fraction | None:
    if not wins or not losses:
        return None
    average_win = Fraction(sum(row.net_pnl_paise for row in wins), len(wins))
    average_loss = Fraction(sum(row.net_pnl_paise for row in losses), len(losses))
    if average_loss == 0:  # pragma: no cover -- a loss set cannot average zero
        return None
    return average_win / -average_loss


def _pct_of_notional(row: LedgerRow | None) -> Fraction | None:
    """A trade's return on its OWN position value -- the only percent a single trade has."""
    if row is None or row.notional_paise == 0:
        return None
    return Fraction(row.net_pnl_paise, row.notional_paise)


def _cagr(initial_paise: int, final_paise: int, days: Sequence[date]) -> Decimal | None:
    """Compound annual growth of the equity curve over the WALKED calendar span.

    ``None`` when the span is shorter than a day or the equity ended at or below zero -- a
    negative base has no real root, and reporting one would be inventing a number.
    """
    if len(days) < 2 or final_paise <= 0 or initial_paise <= 0:
        return None
    span_days = (days[-1] - days[0]).days
    if span_days <= 0:
        return None
    growth = Decimal(final_paise) / Decimal(initial_paise)
    years = Decimal(span_days) / Decimal(365)
    return growth ** (Decimal(1) / years) - Decimal(1)


def format_paise(paise: int | Fraction | None) -> str:
    """``Rs 1,234.56`` from integer paise, for the packs. A Fraction is rounded to 2dp.

    No float on the way: an exact paise count divides by 100 in Decimal, and a Fraction (an
    average, say) becomes a Decimal through its own numerator and denominator.
    """
    if paise is None:
        return "-"
    if isinstance(paise, Fraction):
        rupees = Decimal(paise.numerator) / Decimal(paise.denominator) / Decimal(100)
    else:
        rupees = Decimal(int(paise)) / Decimal(100)
    value = rupees.quantize(Decimal("0.01"))
    sign = "-" if value < 0 else ""
    value = abs(value)
    whole = int(value)
    hundredths = int((value - whole) * 100)
    return f"{sign}Rs {whole:,}.{hundredths:02d}"


def format_pct(value: Fraction | Decimal | None, places: int = 2) -> str:
    """A ratio as a percentage string, or ``-``. Exact rounding, no float."""
    if value is None:
        return "-"
    if isinstance(value, Fraction):
        scaled = Decimal(value.numerator) / Decimal(value.denominator)
    else:
        scaled = value
    quantum = Decimal(1).scaleb(-places)
    return f"{(scaled * 100).quantize(quantum)}%"


def iter_flags(report: CapitalFlagReport) -> Iterable[TradeFlag]:
    return tuple(report.beyond_cash) + tuple(report.beyond_margin)
