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

**The starting capital is an ARGUMENT, never a constant.** CONTEXT 3.5's "Capital: INR
1,00,000 (R1-Q21a)" reaches this module from ``config.yaml``'s ``initial_capital`` key through
:meth:`acumen.config.Config.initial_capital_paise`, and every function that needs it REQUIRES
it -- there is no default here to fall back on (REVIEW_9A finding C1).

**ONE presentation basis: NET.** Every metric here is after the CONTEXT 3.5 round-trip cost
and over one population keyed on the sign of NET PnL -- see :data:`E13_BASIS`. The before-costs
totals survive as exactly two fields, for the single labelled line the ruling allows.

**Money is integer paise; every ratio is a Fraction; the two statistics that need a square
root are Decimal.** No float is produced anywhere in this file (CONTEXT 7-E11).

**The two E13 entries the build session STOPPED on are now ruled** (QUESTIONS.md Q-16,
architect 30-Jul-2026). Outliers are Tukey fences on net PnL and the rule travels with the
number -- see :data:`OUTLIER_DEFINITION` and :func:`outliers`. The intra-trade / intrabar
drawdown and run-up are measured on the TRUE portfolio equity path at 15-minute resolution --
:func:`intraday_equity_path`, :func:`path_max_drawdown`, :func:`path_max_run_up` -- and the
worst-case coincidence construction that stood in for them is GONE, with nothing provisional
left in its place. The path's marks are assembled in the I/O layer
(:func:`acumen.backtest.assemble_trade_paths`), because assembling them needs the stored
candles; everything here stays pure.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from typing import Iterable, Mapping, Sequence

from .backtest import LedgerRow, TradePath
from .signals import LONG, SHORT

#: E13's annualization convention, stated by the spec itself: "Sharpe & Sortino on the DAILY
#: equity series, risk-free rate 0, annualized x sqrt(252)".
TRADING_DAYS_PER_YEAR: int = 252

#: CONTEXT 7-E13 lists "outliers" and fixed no definition for it; the architect's Q-16(a)
#: ruling (30-Jul-2026) does. This sentence IS the definition and the ruling requires it to be
#: printed beside the number, so the figure never appears without the rule that produced it.
OUTLIER_DEFINITION: str = (
    "outliers = executed trades whose NET PnL falls outside the Tukey fences "
    "[Q1 - 3/2 x IQR, Q3 + 3/2 x IQR], taken over the net PnL of ALL executed trades; "
    "quartiles by linear interpolation between order statistics (R / numpy type 7), computed "
    "exactly in Fractions; shares are of the net-basis gross profit and gross loss "
    "(QUESTIONS.md Q-16(a), architect 30-Jul-2026)"
)

#: The architect's E13 PRESENTATION BASIS ruling (30-Jul-2026), which every metric in this
#: module obeys and which the report prints beside its tables. One basis, one population.
E13_BASIS: str = (
    "single basis, NET of the CONTEXT 3.5 flat Rs 100/trade round-trip cost, throughout "
    "(TradingView semantics, which is what E13 mimics). ONE population everywhere: a trade is "
    "a winner or a loser by the sign of its NET PnL. Gross profit, gross loss and profit "
    "factor are sums of those same NET figures over those same populations, so winners x avg "
    "profit == gross profit exactly; every average, ratio, largest-win/loss line and "
    "percentage is on NET (percent-of-notional = net / notional; share-of-profit = net / "
    "net-basis gross profit). Before-costs totals appear ONCE, labelled, and nowhere else "
    "(QUESTIONS.md Q-16, architect 30-Jul-2026; closes REVIEW_9A Q1/Q2/Q4)"
)

#: The quartile probabilities the fences are built from, and Tukey's own 1.5 multiplier -- as
#: exact Fractions, because a float multiplier has no place in this codebase (CONTEXT 7-E11).
QUARTILE_LOW: Fraction = Fraction(1, 4)
QUARTILE_HIGH: Fraction = Fraction(3, 4)
TUKEY_MULTIPLIER: Fraction = Fraction(3, 2)

#: The architect's Q-16(b) ruling (30-Jul-2026) RETIRED the worst-case coincidence
#: construction -- it invented co-timing, which is an assumption -- and replaced it with the
#: true portfolio equity path at 15-minute resolution. This sentence is the ruling's own single
#: disclosed limit and is printed beside every figure taken from the path.
INTRADAY_PATH_LIMIT: str = (
    "measured on the TRUE portfolio equity path at 15-minute resolution: every open position "
    "marked to its 15-min candle closes, exit candles at their exit levels, summed across "
    "positions. ONE disclosed limit: intra-candle excursions are not represented -- the "
    "per-trade MFE/MAE figures carry those (QUESTIONS.md Q-16(b), architect 30-Jul-2026)"
)

#: What a metric set says when no path was handed to it. The path cannot be invented here: it
#: is a function of the stored candles, and this module opens no file.
INTRADAY_PATH_NOT_SUPPLIED: str = (
    "15-minute path NOT supplied to this metric set -- it is assembled in the I/O layer by "
    "acumen.backtest.assemble_trade_paths, which is the layer that holds the candles"
)

#: HISTORICAL. What every output said while the trader's Q43 answer was outstanding (same words
#: as the runner's manifest -- one sentence, one meaning). Kept byte-exact because the completed
#: run's manifest and the committed chunk-9A pilot pack both carry it.
CAPITAL_FLAGS_PENDING_NOTE: str = (
    "capital-infeasibility flags NOT computed -- the trader's Q43 answer is pending"
)

#: What every output says now: the trader SUPERSEDED his own Q43 question in Round 4 and the
#: flags are RETIRED (architect, 06-Aug-2026). Same words as the runner's manifest constant.
CAPITAL_FLAGS_RETIRED_NOTE: str = (
    "capital-infeasibility flags RETIRED by the trader (Round 4): he superseded his own Q43 "
    "question, and the config keys stay null, labelled 'retired by trader, Round 4'"
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


# --- CONTEXT 7-E13 "outliers" (the Q-16(a) ruling) --------------------------------------------


@dataclass(frozen=True)
class OutlierTrade:
    """One trade outside the fences: which one, how much, and which tail it fell out of."""

    symbol: str
    day: date
    net_paise: int
    side_of_fence: str  # "above" or "below"


@dataclass(frozen=True)
class Outliers:
    """CONTEXT 7-E13's "outliers" under the architect's Q-16(a) ruling.

    Everything a reader needs to check the number by hand is in here: the two quartiles, the
    IQR, both fences, the population they were taken over, and the trades themselves. The
    ``definition`` travels WITH the record because the ruling requires the rule to be printed
    beside the figure.
    """

    definition: str
    population: int
    q1_paise: Fraction | None
    q3_paise: Fraction | None
    iqr_paise: Fraction | None
    lower_fence_paise: Fraction | None
    upper_fence_paise: Fraction | None
    count: int
    net_paise: int
    above_count: int
    above_net_paise: int
    below_count: int
    below_net_paise: int
    share_of_gross_profit: Fraction | None
    share_of_gross_loss: Fraction | None
    trades: tuple[OutlierTrade, ...]


def quantile(values: Sequence[int], p: Fraction) -> Fraction | None:
    """The ``p``-quantile by linear interpolation between order statistics. PURE, exact.

    This is R's and numpy's default estimator (type 7): with ``n`` sorted observations the
    quantile sits at position ``(n - 1) * p``, interpolated linearly between the two
    neighbouring order statistics. Fractions throughout, so the result is exact and a reviewer
    reproduces it with ``numpy.percentile`` to the digit (decision B195).
    """
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return None
    position = Fraction(n - 1) * p
    lower = position.numerator // position.denominator  # floor; position is never negative
    if lower >= n - 1:
        return Fraction(ordered[-1])
    weight = position - lower
    return Fraction(ordered[lower]) + weight * (ordered[lower + 1] - ordered[lower])


def outliers(rows: Sequence[LedgerRow]) -> Outliers:
    """CONTEXT 7-E13's outliers by Tukey fences on net PnL (Q-16(a) ruling). PURE.

    The population is every EXECUTED trade's net PnL -- the same single NET basis the rest of
    the report uses (the E13 presentation ruling). A trade is an outlier when its net PnL is
    strictly outside ``[Q1 - 3/2 x IQR, Q3 + 3/2 x IQR]``; a trade sitting exactly ON a fence is
    not an outlier, matching every other "exceeds" rule in this codebase.

    The shares are of the net-basis gross profit (for the upper tail) and gross loss (for the
    lower tail) -- each tail against the pot it belongs to, which is the only reading under
    which a share is between 0 and 1.
    """
    trades = executed(rows)
    nets = [row.net_pnl_paise for row in trades]
    empty = Outliers(
        definition=OUTLIER_DEFINITION,
        population=0,
        q1_paise=None,
        q3_paise=None,
        iqr_paise=None,
        lower_fence_paise=None,
        upper_fence_paise=None,
        count=0,
        net_paise=0,
        above_count=0,
        above_net_paise=0,
        below_count=0,
        below_net_paise=0,
        share_of_gross_profit=None,
        share_of_gross_loss=None,
        trades=(),
    )
    if not nets:
        return empty
    q1 = quantile(nets, QUARTILE_LOW)
    q3 = quantile(nets, QUARTILE_HIGH)
    iqr = q3 - q1
    lower_fence = q1 - TUKEY_MULTIPLIER * iqr
    upper_fence = q3 + TUKEY_MULTIPLIER * iqr

    found: list[OutlierTrade] = []
    for row in trades:
        if row.net_pnl_paise > upper_fence:
            found.append(OutlierTrade(row.symbol, row.day, row.net_pnl_paise, "above"))
        elif row.net_pnl_paise < lower_fence:
            found.append(OutlierTrade(row.symbol, row.day, row.net_pnl_paise, "below"))

    above = [item for item in found if item.side_of_fence == "above"]
    below = [item for item in found if item.side_of_fence == "below"]
    above_net = sum(item.net_paise for item in above)
    below_net = sum(item.net_paise for item in below)
    gross_profit, gross_loss = net_basis_totals(trades)
    return Outliers(
        definition=OUTLIER_DEFINITION,
        population=len(nets),
        q1_paise=q1,
        q3_paise=q3,
        iqr_paise=iqr,
        lower_fence_paise=lower_fence,
        upper_fence_paise=upper_fence,
        count=len(found),
        net_paise=above_net + below_net,
        above_count=len(above),
        above_net_paise=above_net,
        below_count=len(below),
        below_net_paise=below_net,
        share_of_gross_profit=(
            None if gross_profit == 0 else Fraction(above_net, gross_profit)
        ),
        share_of_gross_loss=(None if gross_loss == 0 else Fraction(below_net, gross_loss)),
        trades=tuple(found),
    )


def net_basis_totals(trades: Sequence[LedgerRow]) -> tuple[int, int]:
    """``(gross profit, gross loss)`` on the E13 presentation basis: NET sums, NET populations.

    The architect's E13 ruling (30-Jul-2026) fixes ONE basis and ONE population for the whole
    report: a trade is a winner or a loser by the sign of its NET PnL -- after the CONTEXT 3.5
    round-trip cost -- and the profit and loss pots are the sums of those same net figures.
    That is what makes ``winners x avg profit == gross profit`` an identity a reader can check.
    """
    profit = sum(row.net_pnl_paise for row in trades if row.net_pnl_paise > 0)
    loss = sum(row.net_pnl_paise for row in trades if row.net_pnl_paise < 0)
    return (profit, loss)


# --- the daily series and the equity curve --------------------------------------------------


@dataclass(frozen=True)
class DailyPnL:
    """One trading day of the portfolio: what closed that day, and for how much."""

    day: date
    trades: int
    gross_paise: int
    cost_paise: int
    net_paise: int


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
            )
        )
    return tuple(series)


@dataclass(frozen=True)
class EquityPoint:
    """One day of the equity curve: the day's net PnL and the closing equity after it."""

    day: date
    net_paise: int
    equity_paise: int


def equity_curve(
    series: Sequence[DailyPnL], initial_capital_paise: int
) -> tuple[EquityPoint, ...]:
    """``capital + cumulative net PnL`` per day (CONTEXT 3.5). A plain cumulative SUM. PURE.

    The fixed-INR-risk rule means the position size never depends on the running equity, so
    compounding would be a fiction: the curve adds, it does not multiply. This is E13's
    "equity close-to-close" series exactly; what happened INSIDE a day is the 15-minute path's
    subject (:func:`intraday_equity_path`), not this curve's.
    """
    points: list[EquityPoint] = []
    equity = int(initial_capital_paise)
    for day in series:
        equity = equity + day.net_paise
        points.append(
            EquityPoint(day=day.day, net_paise=day.net_paise, equity_paise=equity)
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


def max_drawdown(points: Sequence[EquityPoint]) -> Excursion:
    """The largest peak-to-trough fall of the equity curve. PURE.

    This is E13's "equity close-to-close" form: both the peak and the trough are daily CLOSING
    equity. The intra-trade / intrabar form is measured on the 15-minute path instead -- see
    :func:`path_max_drawdown` -- and not on a band bolted onto this curve.

    The running peak starts at the run's OPENING capital -- the equity before the first day --
    not at the first day's close, because a fall measured from a close that came after the low
    is not a fall anyone lived through. A ``peak_day`` of ``None`` therefore means "the run's
    opening capital", and it counts as the observation before the first day.

    ``duration_days`` counts the observations from the peak to the trough; it is a count of
    daily observations, which is what a daily series can honestly report. ``recovered_on`` is
    the first later day whose closing equity reaches the peak again, or ``None`` if the series
    ends under water -- and that holds when the peak IS the opening capital, which B185 makes a
    normal case for any run that goes down from its first day (REVIEW_9A finding Q3: the level
    to recover is passed in, never looked up by a date no point carries).
    """
    if not points:
        return Excursion(0, None, None, None, 0, None)
    opening = points[0].equity_paise - points[0].net_paise  # the equity before the first day
    peak = opening
    peak_day: date | None = None
    best = Excursion(0, Fraction(0), peak_day, peak_day, 0, None)
    peak_index = -1
    for index, point in enumerate(points):
        fall = peak - point.equity_paise
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
        recovery = _first_recovery(points, best, opening_paise=opening)
        best = Excursion(
            best.amount_paise,
            best.pct,
            best.peak_day,
            best.trough_day,
            best.duration_days,
            recovery,
        )
    return best


def max_run_up(points: Sequence[EquityPoint]) -> Excursion:
    """The largest trough-to-peak rise -- the mirror of :func:`max_drawdown`. PURE.

    Symmetrically, the running trough starts at the opening capital and a ``trough_day`` of
    ``None`` means the run started there. E13 asks for run-ups "in the same forms" as
    drawdowns, so ``recovered_on`` is filled here too: the first day AFTER the peak whose
    closing equity falls back to the trough level, i.e. the day the rise was given back. It was
    structurally always ``None`` before, which is a dead field rather than a meaningfully empty
    one (REVIEW_9A finding Q5).
    """
    if not points:
        return Excursion(0, None, None, None, 0, None)
    opening = points[0].equity_paise - points[0].net_paise  # the equity before the first day
    trough = opening
    trough_day: date | None = None
    trough_index = -1
    best = Excursion(0, Fraction(0), trough_day, trough_day, 0, None)
    for index, point in enumerate(points):
        rise = point.equity_paise - trough
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
    if best.peak_day is not None and best.amount_paise > 0:
        given_back = _first_giveback(points, best, opening_paise=opening)
        best = Excursion(
            best.amount_paise,
            best.pct,
            best.peak_day,
            best.trough_day,
            best.duration_days,
            given_back,
        )
    return best


def _first_giveback(
    points: Sequence[EquityPoint], excursion: Excursion, *, opening_paise: int
) -> date | None:
    """The first day after the peak whose closing equity is back down at the trough level."""
    trough_equity = opening_paise
    for point in points:
        if point.day == excursion.trough_day:
            trough_equity = point.equity_paise
    seen_peak = False
    for point in points:
        if point.day == excursion.peak_day:
            seen_peak = True
            continue
        if seen_peak and point.equity_paise <= trough_equity:
            return point.day
    return None


def _first_recovery(
    points: Sequence[EquityPoint], excursion: Excursion, *, opening_paise: int
) -> date | None:
    """The first day after the trough whose closing equity is back at the peak level. PURE.

    The level is resolved BEFORE the walk: a ``peak_day`` of ``None`` means the opening capital
    (B185), and the old implementation learned the level only from a point whose ``day``
    matched, so in that case no point ever matched and a drawdown that demonstrably recovered
    reported "recovered never" (REVIEW_9A finding Q3).
    """
    peak_equity = opening_paise
    for point in points:
        if point.day == excursion.peak_day:
            peak_equity = point.equity_paise
    seen_trough = False
    for point in points:
        if point.day == excursion.trough_day:
            seen_trough = True
            continue
        if seen_trough and point.equity_paise >= peak_equity:
            return point.day
    return None


# --- the 15-minute portfolio equity path (E13's intra-trade form, Q-16(b) ruling) ------------


@dataclass(frozen=True)
class PathPoint:
    """One observation of the portfolio's equity inside the run, at 15-minute resolution.

    ``stamp`` is the 15-minute candle close the observation was taken at; ``None`` marks the
    day's CLOSING observation, which is there for every walked day -- including days that
    traded nothing, so a drawdown can span them.
    """

    day: date
    stamp: datetime | None
    equity_paise: int
    open_positions: int


@dataclass(frozen=True)
class PathExcursion:
    """A drawdown or run-up measured on the 15-minute path, with the points that made it."""

    amount_paise: int
    pct: Fraction | None
    peak: PathPoint | None
    trough: PathPoint | None
    observations: int
    recovered: PathPoint | None
    note: str = INTRADAY_PATH_LIMIT

    @property
    def is_empty(self) -> bool:
        return self.amount_paise == 0


def mark_pnl_paise(path: TradePath, price_paise: int) -> int:
    """A position's PnL if it were marked at ``price_paise``, NET of its round-trip cost. PURE.

    The cost is charged from the ENTRY mark onward (decision B194): the round trip is committed
    the moment the position opens, and charging it there is what makes the last mark of a trade
    equal its realized net PnL exactly, so the path runs continuously into the closed position
    instead of stepping by Rs 100 at the exit.
    """
    if path.side == SHORT:
        gross = (path.entry_paise - price_paise) * path.qty
    else:
        gross = (price_paise - path.entry_paise) * path.qty
    return gross - path.cost_paise


def path_reconciles(path: TradePath) -> bool:
    """Does the trade's LAST mark reproduce its ledger net PnL exactly? PURE.

    The invariant that makes the path trustworthy: if the exit mark is the exit LEVEL and the
    arithmetic is the simulator's own, then marking the last observation must land on the money
    the ledger recorded. A False here means the assembly and the ledger disagree.
    """
    if not path.marks:
        return path.net_pnl_paise == 0
    return mark_pnl_paise(path, path.marks[-1].price_paise) == path.net_pnl_paise


def _contribution(path: TradePath, stamp: datetime) -> tuple[int, int]:
    """``(PnL contribution, 1 if still open)`` of one trade at one 15-minute stamp. PURE."""
    if stamp < path.marks[0].stamp:
        return (0, 0)
    price = path.marks[0].price_paise
    for mark in path.marks:
        if mark.stamp > stamp:
            break
        price = mark.price_paise
    live = 0 if stamp >= path.marks[-1].stamp else 1
    return (mark_pnl_paise(path, price), live)


def intraday_equity_path(
    series: Sequence[DailyPnL],
    paths: Sequence[TradePath],
    *,
    initial_capital_paise: int,
) -> tuple[PathPoint, ...]:
    """The TRUE portfolio equity path at 15-minute resolution (Q-16(b) ruling). PURE.

    At every 15-minute stamp of a day, every position open at that stamp is marked to its own
    candle close (its exit candle to its exit level) and the marks are SUMMED across positions
    onto the equity the day opened with. A position already closed contributes its realized net;
    one not yet opened contributes nothing. Every walked day also contributes its CLOSING
    observation, so the path spans days that traded nothing and a multi-day drawdown is
    measurable on it.

    Because CONTEXT 3.1 squares everything off at 15:15, no trade straddles a day: each day's
    last observation therefore equals that day's closing equity on the daily curve, which is the
    invariant that ties this path to :func:`equity_curve`.

    The disclosed limit is :data:`INTRADAY_PATH_LIMIT`: a mark is a candle CLOSE, so an
    excursion that happened inside a candle and reversed before it closed is not on this path.
    The per-trade MFE/MAE figures are exactly what carry those.
    """
    by_day: dict[date, list[TradePath]] = {}
    for path in paths:
        by_day.setdefault(path.day, []).append(path)

    points: list[PathPoint] = []
    equity = int(initial_capital_paise)
    for day in series:
        opening = equity
        day_paths = by_day.get(day.day, ())
        stamps = sorted({mark.stamp for path in day_paths for mark in path.marks})
        for stamp in stamps:
            total = 0
            live = 0
            for path in day_paths:
                contribution, open_now = _contribution(path, stamp)
                total += contribution
                live += open_now
            points.append(PathPoint(day.day, stamp, opening + total, live))
        equity = opening + day.net_paise
        points.append(PathPoint(day.day, None, equity, 0))
    return tuple(points)


def path_max_drawdown(
    points: Sequence[PathPoint], *, initial_capital_paise: int
) -> PathExcursion:
    """The largest peak-to-trough fall of the 15-minute path. PURE.

    The running peak is seeded at the run's OPENING capital, exactly as the close-to-close form
    is (decision B185): a ``peak`` of ``None`` means the fall started from the opening capital.
    ``observations`` counts path points from the peak to the trough, and ``recovered`` is the
    first later observation to reach the peak again.
    """
    if not points:
        return PathExcursion(0, None, None, None, 0, None)
    peak = int(initial_capital_paise)
    peak_point: PathPoint | None = None
    peak_index = -1
    best = PathExcursion(0, Fraction(0), None, None, 0, None)
    for index, point in enumerate(points):
        fall = peak - point.equity_paise
        if fall > best.amount_paise:
            best = PathExcursion(
                amount_paise=fall,
                pct=Fraction(fall, peak) if peak != 0 else None,
                peak=peak_point,
                trough=point,
                observations=index - peak_index,
                recovered=None,
            )
        if point.equity_paise > peak:
            peak, peak_point, peak_index = point.equity_paise, point, index
    if best.amount_paise == 0:
        return best
    return _with_recovery(points, best, peak_level=peak_of(best, initial_capital_paise))


def path_max_run_up(
    points: Sequence[PathPoint], *, initial_capital_paise: int
) -> PathExcursion:
    """The largest trough-to-peak rise of the 15-minute path -- the exact mirror. PURE.

    E13 asks for run-ups "in the same forms", so this fills ``recovered`` too: the first later
    observation to fall back to the trough level (REVIEW_9A finding Q5).
    """
    if not points:
        return PathExcursion(0, None, None, None, 0, None)
    trough = int(initial_capital_paise)
    trough_point: PathPoint | None = None
    trough_index = -1
    best = PathExcursion(0, Fraction(0), None, None, 0, None)
    for index, point in enumerate(points):
        rise = point.equity_paise - trough
        if rise > best.amount_paise:
            best = PathExcursion(
                amount_paise=rise,
                pct=Fraction(rise, trough) if trough != 0 else None,
                peak=point,
                trough=trough_point,
                observations=index - trough_index,
                recovered=None,
            )
        if point.equity_paise < trough:
            trough, trough_point, trough_index = point.equity_paise, point, index
    if best.amount_paise == 0:
        return best
    level = (
        initial_capital_paise if best.trough is None else best.trough.equity_paise
    )
    after = _points_after(points, best.peak)
    for point in after:
        if point.equity_paise <= level:
            return PathExcursion(
                best.amount_paise,
                best.pct,
                best.peak,
                best.trough,
                best.observations,
                point,
            )
    return best


def peak_of(excursion: PathExcursion, initial_capital_paise: int) -> int:
    """The equity the drawdown fell FROM -- the opening capital when the peak is ``None``."""
    if excursion.peak is None:
        return int(initial_capital_paise)
    return excursion.peak.equity_paise


def _with_recovery(
    points: Sequence[PathPoint], excursion: PathExcursion, *, peak_level: int
) -> PathExcursion:
    for point in _points_after(points, excursion.trough):
        if point.equity_paise >= peak_level:
            return PathExcursion(
                excursion.amount_paise,
                excursion.pct,
                excursion.peak,
                excursion.trough,
                excursion.observations,
                point,
            )
    return excursion


def _points_after(
    points: Sequence[PathPoint], marker: PathPoint | None
) -> tuple[PathPoint, ...]:
    """Every observation strictly after ``marker`` (all of them when it is ``None``)."""
    if marker is None:
        return tuple(points)
    for index, point in enumerate(points):
        if point is marker or (point.day == marker.day and point.stamp == marker.stamp):
            return tuple(points[index + 1 :])
    return ()  # pragma: no cover -- the marker always comes from `points`


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
    capital could not actually have taken. Which capital figure the flags must use was his to
    say (Q43), and in Round 4 he SUPERSEDED his own question rather than answering it: the flags
    are RETIRED and a per-stock POINTS view (:mod:`acumen.points_view`) is adopted in their place
    (architect, 06-Aug-2026). So with either input ``None`` this computes NOTHING and returns
    :data:`CAPITAL_FLAGS_RETIRED_NOTE` for the report to print verbatim. No default is
    substituted -- flagging a real trade "infeasible" against a guessed figure would put this
    repo's number in place of his -- and the machinery is kept rather than deleted, so a later
    answer would revive it without a rebuild.

    When both are supplied: a trade is beyond CASH when its notional (qty x entry) exceeds the
    capital reference, and beyond MARGIN when it exceeds ``capital_reference x margin_basis``
    (CONTEXT 3.5's "typical-MIS tiers"). Nothing is capped, skipped or resized -- take-all is
    unchanged; the flags are a disclosure, not a constraint.
    """
    if capital_reference_paise is None or margin_basis is None:
        return CapitalFlagReport(
            computed=False,
            note=CAPITAL_FLAGS_RETIRED_NOTE,
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
    initial_capital_paise: int,
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
        total_return=(
            None
            if initial_capital_paise == 0
            else (end_value - initial_capital_paise) / initial_capital_paise
        ),
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
    Sharpe and Sortino are :class:`~decimal.Decimal` because they need a square root. The two
    entries the build session had to leave blank are both computed now, under the architect's
    Q-16 ruling: ``outliers`` carries its own definition, and the ``intraday_*`` excursions are
    measured on the true 15-minute path when one is supplied (:data:`INTRADAY_PATH_LIMIT`) and
    are ``None``, with :data:`INTRADAY_PATH_NOT_SUPPLIED` said out loud, when one is not.
    """

    label: str
    # --- money
    net_pnl_paise: int
    gross_profit_paise: int
    gross_loss_paise: int
    profit_factor: Fraction | None
    commission_paise: int
    #: The ONE place before-cost totals exist. Labelled "before Rs 100/trade costs" wherever
    #: they are printed, and printed exactly once (the E13 presentation ruling).
    before_cost_profit_paise: int
    before_cost_loss_paise: int
    basis: str
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
    outliers: Outliers
    outliers_note: str
    # --- equity
    initial_capital_paise: int
    final_equity_paise: int
    return_on_initial_capital: Fraction | None
    cagr: Decimal | None
    max_drawdown: Excursion
    max_run_up: Excursion
    intraday_max_drawdown: PathExcursion | None
    intraday_max_run_up: PathExcursion | None
    intraday_observations: int
    intraday_note: str
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
    initial_capital_paise: int,
    days: Sequence[date] | None = None,
    paths: Sequence[TradePath] = (),
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
    path_points = (
        intraday_equity_path(series, paths, initial_capital_paise=initial_capital_paise)
        if paths
        else ()
    )
    trades = executed(rows)
    wins = [row for row in trades if row.net_pnl_paise > 0]
    losses = [row for row in trades if row.net_pnl_paise < 0]
    flats = [row for row in trades if row.net_pnl_paise == 0]

    # THE E13 PRESENTATION BASIS (architect, 30-Jul-2026): the profit and loss pots are sums
    # of NET PnL over the NET-sign populations -- the same `wins` and `losses` counted above --
    # so no reader has to reconcile two bases or two memberships. See :data:`E13_BASIS`.
    gross_profit, gross_loss = net_basis_totals(trades)
    net = sum(row.net_pnl_paise for row in trades)
    commission = sum(row.cost_paise for row in trades)
    # The before-costs pair, carried for the single labelled line the ruling permits.
    before_cost_profit = sum(
        row.gross_pnl_paise for row in trades if row.gross_pnl_paise > 0
    )
    before_cost_loss = sum(row.gross_pnl_paise for row in trades if row.gross_pnl_paise < 0)

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
        before_cost_profit_paise=before_cost_profit,
        before_cost_loss_paise=before_cost_loss,
        basis=E13_BASIS,
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
            else Fraction(largest_win.net_pnl_paise, gross_profit)
        ),
        largest_loss_paise=0 if largest_loss is None else largest_loss.net_pnl_paise,
        largest_loss_pct_of_notional=_pct_of_notional(largest_loss),
        largest_loss_pct_of_gross_loss=(
            None
            if largest_loss is None or gross_loss == 0
            else Fraction(largest_loss.net_pnl_paise, gross_loss)
        ),
        outliers=outliers(rows),
        outliers_note=OUTLIER_DEFINITION,
        initial_capital_paise=initial_capital_paise,
        final_equity_paise=final_equity,
        return_on_initial_capital=(
            None
            if initial_capital_paise == 0
            else Fraction(final_equity - initial_capital_paise, initial_capital_paise)
        ),
        cagr=_cagr(initial_capital_paise, final_equity, span),
        max_drawdown=max_drawdown(points),
        max_run_up=max_run_up(points),
        intraday_max_drawdown=(
            None
            if not path_points
            else path_max_drawdown(path_points, initial_capital_paise=initial_capital_paise)
        ),
        intraday_max_run_up=(
            None
            if not path_points
            else path_max_run_up(path_points, initial_capital_paise=initial_capital_paise)
        ),
        intraday_observations=len(path_points),
        intraday_note=INTRADAY_PATH_LIMIT if path_points else INTRADAY_PATH_NOT_SUPPLIED,
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
    rows: Sequence[LedgerRow],
    *,
    initial_capital_paise: int,
    paths: Sequence[TradePath] = (),
) -> dict[str, Metrics]:
    """E13's All / Long / Short column split. PURE.

    A side's subset keeps every walked day, so its daily series has the same index as the
    portfolio's and its Sharpe is annualized over the same sample. Each column's 15-minute path
    is built from that column's own trades, so a side's intraday drawdown is that side's, never
    a slice of the portfolio's.
    """
    index = walked_days(rows)
    return {
        "All": metrics(
            rows,
            label="All",
            initial_capital_paise=initial_capital_paise,
            days=index,
            paths=paths,
        ),
        "Long": metrics(
            for_side(rows, LONG),
            label="Long",
            initial_capital_paise=initial_capital_paise,
            days=index,
            paths=paths_for_side(paths, LONG),
        ),
        "Short": metrics(
            for_side(rows, SHORT),
            label="Short",
            initial_capital_paise=initial_capital_paise,
            days=index,
            paths=paths_for_side(paths, SHORT),
        ),
    }


def paths_for_side(paths: Sequence[TradePath], side: str) -> tuple[TradePath, ...]:
    return tuple(path for path in paths if path.side == side)


def paths_for_symbol(paths: Sequence[TradePath], symbol: str) -> tuple[TradePath, ...]:
    wanted = symbol.strip().upper()
    return tuple(path for path in paths if path.symbol == wanted)


def per_symbol(
    rows: Sequence[LedgerRow],
    *,
    initial_capital_paise: int,
    paths: Sequence[TradePath] = (),
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
            paths=paths_for_symbol(paths, symbol),
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
