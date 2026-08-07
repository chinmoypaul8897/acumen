"""The per-stock POINTS view -- what the trader asked for in Round 4, in place of Q43.

He superseded his own capital question ("which figure should decide whether a trade was
affordable?") and asked instead to see the stocks in POINTS: the per-share move each trade made,
signed by side. The architect adopted it on 06-Aug-2026 (QUESTIONS.md, ROUND-4 RECEIPTS) with two
conditions that this module and its renderers carry:

* it is computed **POST-HOC from the completed ledger** -- no re-run, no new strategy behaviour,
  and nothing here can change a trade;
* it is **size-independent** by construction (``points = exit - entry`` per share, signed by
  side), so a ranking built on it does not quietly rank position sizes -- and because it ignores
  size, it also ignores the flat rupee cost, which is why every page that prints it must print
  the cost line beside it.

**A point is one rupee of price on ONE share.** At one share the CONTEXT 3.5 round-trip cost is
100 points; at 350 shares it is under a third of a point. The view says so on the page rather
than leaving a reader to discover it.

The third condition is a caveat rather than a computation and lives in the renderers: 204 ranked
stocks throw up "good" ones by chance alone, so no ranking produced here may be printed without
the multiple-comparisons sentence beside it (:data:`MULTIPLE_COMPARISONS_CAVEAT`).

PURE, like `bias`, `poc`, `signals` and `simulate`: integer paise in, exact `Fraction` averages
out, no I/O, no network, no clock read. Source files in this package are ASCII-only on purpose
(see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from fractions import Fraction
from typing import Mapping, Sequence

from . import signals as sig

#: Where the full per-symbol table is published, beside the technical report. Named here so the
#: report, the validation pack and the generator all point at one path.
COMPANION_PATH: str = "docs/reports/points_by_symbol.md"

#: How many rows each end of the ranking shows on the trader's page. The full table is always
#: published too, so the cut is a courtesy to the reader and never a filter on the evidence.
SHOWN_EACH_END: int = 20

#: The conventional false-positive rate a ranking of independent tests carries -- one in twenty.
#: Written as a Fraction because the count it produces is printed on a page and nothing on a page
#: in this repo may come from a float.
FALSE_POSITIVE_RATE: Fraction = Fraction(1, 20)

#: The caveat the architect made MANDATORY on any per-stock ranking (Round 4). A TEMPLATE, not a
#: sentence with numbers typed into it: both figures are computed from the ranking actually
#: printed, so a table of a different size cannot inherit this one's arithmetic. Printed in full
#: sentences beside the table -- never as a footnote marker.
MULTIPLE_COMPARISONS_CAVEAT: str = (
    "{symbols} stocks ranked: even a no-edge system shows about {by_chance} 'good' ones by "
    "chance, at the conventional one-in-twenty rate. Treat the top entries as candidates for "
    "forward checking, never as proof."
)


def by_chance(symbols: int) -> int:
    """How many of ``symbols`` independent no-edge tests look good anyway. PURE."""
    return int(symbols * FALSE_POSITIVE_RATE)


class PointsError(Exception):
    """A row that claims to be a trade but cannot supply a per-share move."""


@dataclass(frozen=True)
class SymbolPoints:
    """One stock's whole record, in points. Every field is exact: paise, counts, Fractions."""

    symbol: str
    trades: int
    winners: int
    losers: int
    flat: int
    #: The sum of the signed per-share moves, in paise. NOT money: multiply by a size to get
    #: money, which is exactly what this view refuses to do for you.
    points_paise: int
    #: The deepest fall in the CUMULATIVE points curve, walked in time order from a peak seeded
    #: at zero, so a stock whose first trade loses shows that loss.
    max_drawdown_paise: int
    best_paise: int
    best_day: date | None
    worst_paise: int
    worst_day: date | None

    @property
    def win_rate(self) -> Fraction | None:
        """Winners over ALL trades -- one denominator, flat trades included (E13 basis)."""
        if not self.trades:
            return None
        return Fraction(self.winners, self.trades)

    @property
    def avg_points_paise(self) -> Fraction | None:
        if not self.trades:
            return None
        return Fraction(self.points_paise, self.trades)


@dataclass(frozen=True)
class PointsTotals:
    """The whole run, in the same units -- so the ranking's parts add up to something."""

    symbols: int
    trades: int
    winners: int
    #: Trades that ended EXACTLY level in points, and the stocks that have at least one. They
    #: are inside :attr:`trades` -- the win rate's denominator is every trade (E13) -- and are
    #: in neither the winners nor the losers, so a page that prints the rate has to name them
    #: or leave a reader with a population in no stated category (REVIEW_12_2 finding Q3, the
    #: same correction REVIEW_12 Q5 required of page 1).
    flat: int
    symbols_with_a_flat: int
    points_paise: int
    best: SymbolPoints | None
    worst: SymbolPoints | None

    @property
    def win_rate(self) -> Fraction | None:
        if not self.trades:
            return None
        return Fraction(self.winners, self.trades)

    @property
    def avg_points_paise(self) -> Fraction | None:
        if not self.trades:
            return None
        return Fraction(self.points_paise, self.trades)


def points_paise(row) -> int:
    """One trade's per-share move in paise, signed by side. PURE.

    Long: ``exit - entry``. Short: ``entry - exit`` (CONTEXT 3.4's mirror). The row's quantity,
    notional, gross and net are not read at all -- that independence IS the view.
    """
    entry, exit_ = row.entry_paise, row.exit_paise
    if entry is None or exit_ is None:
        raise PointsError(
            f"{row.symbol} {row.day}: an executed row with no "
            f"{'entry' if entry is None else 'exit'} price cannot produce points"
        )
    return int(exit_) - int(entry) if row.side == sig.LONG else int(entry) - int(exit_)


def _walk(moves: Sequence[int]) -> int:
    """The deepest fall in the cumulative curve, peak seeded at zero. PURE."""
    running = 0
    peak = 0
    deepest = 0
    for move in moves:
        running += move
        peak = max(peak, running)
        deepest = max(deepest, peak - running)
    return deepest


def _ordered(rows: Sequence) -> list:
    """Trades in the order they happened -- the only order a drawdown may be walked in."""
    return sorted(rows, key=lambda row: (row.day, row.entry_close_stamp or row.day, row.symbol))


def per_symbol(rows: Sequence) -> tuple[SymbolPoints, ...]:
    """Every stock that traded, in points, biggest points first. PURE.

    ``rows`` is any sequence of ledger rows (the run's own :class:`acumen.backtest.LedgerRow`);
    the ones that did not execute contribute nothing, exactly as they contribute no money. An
    executed row that carries no price is a data fault and is RAISED, never treated as zero.
    """
    by_symbol: dict[str, list] = {}
    for row in rows:
        if getattr(row, "executed", False):
            by_symbol.setdefault(row.symbol, []).append(row)

    out: list[SymbolPoints] = []
    for symbol in sorted(by_symbol):
        trades = _ordered(by_symbol[symbol])
        moves = [points_paise(row) for row in trades]
        best_index = max(range(len(moves)), key=lambda i: (moves[i], -i))
        worst_index = min(range(len(moves)), key=lambda i: (moves[i], i))
        out.append(SymbolPoints(
            symbol=symbol,
            trades=len(moves),
            winners=sum(1 for move in moves if move > 0),
            losers=sum(1 for move in moves if move < 0),
            flat=sum(1 for move in moves if move == 0),
            points_paise=sum(moves),
            max_drawdown_paise=_walk(moves),
            best_paise=moves[best_index],
            best_day=trades[best_index].day,
            worst_paise=moves[worst_index],
            worst_day=trades[worst_index].day,
        ))
    return tuple(sorted(out, key=lambda one: (-one.points_paise, one.symbol)))


def totals(table: Sequence[SymbolPoints]) -> PointsTotals:
    """The ranking's own totals, so its parts can be checked against the whole. PURE."""
    return PointsTotals(
        symbols=len(table),
        trades=sum(one.trades for one in table),
        winners=sum(one.winners for one in table),
        flat=sum(one.flat for one in table),
        symbols_with_a_flat=sum(1 for one in table if one.flat),
        points_paise=sum(one.points_paise for one in table),
        best=table[0] if table else None,
        worst=table[-1] if table else None,
    )


def ends(table: Sequence[SymbolPoints], *, each_end: int = SHOWN_EACH_END
         ) -> tuple[tuple[SymbolPoints, ...], tuple[SymbolPoints, ...]]:
    """The top and bottom slices of the ranking, never overlapping. PURE.

    With fewer stocks than two full slices the two halves would print the same rows twice, which
    reads as a longer list than the evidence is; the split is exact instead.
    """
    if len(table) <= each_end + each_end:
        middle = len(table) // 2
        return tuple(table[:middle]), tuple(table[middle:])
    return tuple(table[:each_end]), tuple(table[-each_end:])


def cost_in_points_paise(cost_paise: int, *, shares: int) -> Fraction:
    """What the flat round-trip cost is worth in POINTS at a given size. PURE.

    The cost is a rupee amount per trade; a point is a rupee of price on one share. So the cost
    in points is the cost divided by the number of shares -- 100 points at one share, and a
    hundredth of that at a hundred shares. This is the arithmetic behind the honesty line every
    page carrying this view must print.
    """
    if shares <= 0:
        raise PointsError("a trade in no shares has no per-share cost")
    return Fraction(int(cost_paise), int(shares))


def format_points(paise: int | Fraction | None, *, signed: bool = True) -> str:
    """Paise of PRICE, as a signed decimal to two places. No currency: these are points.

    Exact on the way, like :func:`acumen.portfolio.format_paise`: an integer divides in Decimal
    and a Fraction goes through its own numerator and denominator. Positives carry a leading plus
    so a ranking cannot be misread at a glance; ONLY AN EXACT ZERO carries neither sign; thousands
    are grouped. ``signed=False`` is for a MAGNITUDE -- a cost, a drawdown -- where a leading plus
    would read as a gain. Every worked example lives in ``tests/test_points_view.py``,
    hand-computed, which is also why no figure is spelled out here (the pack's no-typed-money
    tripwire scans this module).

    REVIEW_12_2 finding C7: the sign used to be read off the QUANTIZED value, so a stock whose
    average move is smaller than half a paisa printed an unsigned zero in a column whose whole
    convention is that a sign is always there -- seven rows of the 204-row companion did, beside
    a signed and non-zero *Points* figure. The sign is now taken from the value HANDED IN, so a
    move too small to survive rounding still shows the direction it went: the magnitude rounds
    away, the sign does not. Nothing else moves -- an exact zero still prints unsigned, and
    every figure that does not round to nothing is unchanged.
    """
    if paise is None:
        return "-"
    if isinstance(paise, Fraction):
        value = Decimal(paise.numerator) / Decimal(paise.denominator) / Decimal(100)
    else:
        value = Decimal(int(paise)) / Decimal(100)
    negative = value < 0
    positive = value > 0
    value = value.quantize(Decimal("0.01"))
    sign = "-" if negative else ("+" if positive and signed else "")
    value = abs(value)
    whole = int(value)
    hundredths = int((value - whole) * 100)
    return f"{sign}{whole:,}.{hundredths:02d}"


def as_payload(table: Sequence[SymbolPoints]) -> list[Mapping]:
    """The whole table as plain data for the JSON companion -- every stock, no cut. PURE."""
    return [
        {
            "symbol": one.symbol,
            "trades": one.trades,
            "winners": one.winners,
            "losers": one.losers,
            "flat": one.flat,
            "win_rate": str(one.win_rate),
            "points_paise": one.points_paise,
            "avg_points_paise": str(one.avg_points_paise),
            "max_drawdown_points_paise": one.max_drawdown_paise,
            "best_trade_points_paise": one.best_paise,
            "best_trade_day": one.best_day.isoformat() if one.best_day else None,
            "worst_trade_points_paise": one.worst_paise,
            "worst_trade_day": one.worst_day.isoformat() if one.worst_day else None,
        }
        for one in table
    ]


__all__ = [
    "COMPANION_PATH",
    "FALSE_POSITIVE_RATE",
    "MULTIPLE_COMPARISONS_CAVEAT",
    "by_chance",
    "PointsError",
    "PointsTotals",
    "SHOWN_EACH_END",
    "SymbolPoints",
    "as_payload",
    "cost_in_points_paise",
    "ends",
    "format_points",
    "per_symbol",
    "points_paise",
    "totals",
]
