"""The volume-profile / POC engine: CONTEXT 3.3, as PURE functions (candles in, POC out).

This is TradingView's Fixed Range Volume Profile, reproduced exactly as CONTEXT 3.3 and
CONTEXT 5 spell it. The strategy is frozen (CLAUDE.md rule 2): every step below is written
from the spec's own sentences, in the spec's own order, and nothing "better" is added.

**Window.** The profile is built from the 1-minute candles OPEN-stamped 09:15 through 11:14
inclusive -- "the session up to 11:15; the 15-min candle closing at 11:15 is INCLUDED"
(CONTEXT 3.3, R1-Q11). In 15-minute terms that is the first EIGHT candles of the session, and
that is how :data:`SPEC_WINDOW` is defined here -- as a count of 15-minute candles from the
session open (CONTEXT 7-E12 stamping), not as a hand-typed clock time.

The window is a PARAMETER because QUESTIONS.md **Q-8 is OPEN**: the trader's Round-3 FRVP
screenshot shows a NINE-candle box (Coordinates #1=150, #2=158), which would extend the window
to the 11:29 stamp. Q-8's INTERIM is unchanged from the spec -- the 8-candle window stands and
is the default everywhere -- and Round-3 Q42 will settle it. :data:`ALTERNATE_WINDOW` exists so
the chunk-6 trader gate can print BOTH numbers side by side (the Q-8 record asks for exactly
that); it is **EVIDENCE ONLY** and no engine path selects it.

**Row construction** (CONTEXT 3.3, TradingView's documented math, CONTEXT 5):

* ``top = max(high)``, ``bottom = min(low)`` over the window;
* ``totalTicks = round((top - bottom) / tick)``, floored at 1 so a frozen stock
  (``top == bottom``) still has one single-tick row;
* ``tpr = totalTicks / N`` rounded to a whole number, **minimum 1**, the direction chosen so
  the REALIZED row count lands closest to the requested ``N``;
* rows are stacked from ``bottom`` upward, each ``tpr`` ticks tall, and the LAST row holds the
  remainder (it may be smaller) -- so the realized count can exceed ``N``. TradingView's own
  worked example: 100 ticks, N=30 -> tpr=3 -> 33 rows of 3 + 1 row of 1 = 34 rows (fixture F6).

**Row containment.** Rows are half-open ``[lo, hi)`` EXCEPT the topmost, which INCLUDES
``top``. A zero-range bar (``high == low``) is a point: its FULL volume goes to the single row
containing that price. ``top == bottom`` for the whole window -> one single-tick row.

**Volume spreading = PRORATA** (LOCKED by the 22-Jul-2026 calibration, 5/5 against the
trader's TradingView readings): each 1-minute bar's volume is split across the rows its
``[low, high]`` range overlaps, in proportion to the price overlap, with ``high == low``
treated as a one-tick span. Not "all at close", not "uniform".

**POC** = the MIDPOINT of the row with the maximum TOTAL volume; a tie goes to the
HIGHER-priced row (R1-Q9, side-independent). The midpoint may legally sit OFF the tick grid
(half-paise) -- CONTEXT 3.3 / 7-E11 -- so it is returned as an exact
:class:`~fractions.Fraction` of paise and never rounded.

**Window validity -- the AMENDED completeness rule.** QUESTIONS.md carries the architect's
2026-07-26 ruling (CONTEXT v1.3 will carry it; recorded there verbatim): *"a missing 1-minute
stamp on a day whose gate-1 volume reconciliation PASSES is a NO-TRADE minute, not missing
data ... E4 is redefined the same way: the 09:15-11:14 profile window is valid when the DAY
passes gate-1 (zero-volume minutes contribute zero to the profile, which remains true); E4's
minute-count trigger is retired."* So this module counts NOTHING: a stock-day yields a POC iff
its gate-1 verdict is PASS, and absent stamps inside the window are simply minutes in which
nothing traded. ``tests/test_quality_gates.py`` keeps an ``ast`` probe that fails if any
``src/`` module reintroduces the retired count, and nothing here does.

**Exactness.** Prices are integer paise (CONTEXT 7-E11) and row edges are exact integer paise.
Row volumes are :class:`~fractions.Fraction`, so the profile sums EXACTLY to the window's
volume and the "maximum row" comparison (and therefore the tie rule) is exact -- there is no
float anywhere in the arithmetic and no float equality comparison, which CONTEXT 7-E11 bans.

PURE: no I/O, no network, no clock reads (CONTEXT 6). ``tick_paise`` is supplied by the caller
from the chunk-5A instrument-master loader
(:attr:`acumen.instrument_master.Instrument.tick_size_paise`) -- there is no tick table here
and no default, because CONTEXT 3.3/4.3 say "NEVER hardcode 0.05" and QUESTIONS.md Q-2
measured that hardcoding it mis-prices DIXON by rupees.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction
from typing import Protocol, Sequence

from .calendar import SESSION_CLOSE, SESSION_OPEN

#: One profile-window step, in minutes: the strategy's candle length (CONTEXT 3.4 / 7-E12).
CANDLE_MINUTES: int = 15


_OPEN_MINUTE_OF_DAY: int = SESSION_OPEN.hour * 60 + SESSION_OPEN.minute
_CLOSE_MINUTE_OF_DAY: int = SESSION_CLOSE.hour * 60 + SESSION_CLOSE.minute


def _minutes_after_open(minutes: int) -> time:
    """The clock time ``minutes`` after the 09:15 session open. PURE, and date-free.

    Refuses to run past the 15:30 session close (CONTEXT 7-E2), so no window can silently
    wrap past midnight or reach into a session that does not exist.
    """
    total = _OPEN_MINUTE_OF_DAY + minutes
    if total > _CLOSE_MINUTE_OF_DAY:
        raise PocError(
            f"{minutes} minutes after the {SESSION_OPEN.isoformat()} open runs past the "
            f"{SESSION_CLOSE.isoformat()} session close (CONTEXT 7-E2)."
        )
    hour, minute = divmod(total, 60)
    return time(hour, minute)

#: CONTEXT 3.3 / R1-Q11: candles stamped 09:15..11:14 = the FIRST EIGHT 15-minute candles of
#: the session (the last one is the candle closing at 11:15, which is IN).
SPEC_WINDOW_CANDLES: int = 8

#: QUESTIONS.md Q-8 / Round-3 Q42, EVIDENCE ONLY: the trader's screenshot box read as an
#: inclusive 9-bar count (158 - 150 + 1), i.e. stamps 09:15..11:29. No engine path selects it.
ALTERNATE_WINDOW_CANDLES: int = 9

#: Why a stock-day has no POC (or has one). Carried on the result so chunk 9 can COUNT the
#: exclusions by reason (CONTEXT 7-E3) instead of inferring them from a null.
POC_OK: str = "poc-computed"
NO_POC_GATE_1_FAILED: str = "no-poc-day-fails-gate-1"
NO_POC_GATE_1_UNRUN: str = "no-poc-gate-1-not-run"
NO_POC_EMPTY_WINDOW: str = "no-poc-no-candles-in-window"


class PocError(RuntimeError):
    """The profile inputs are not usable (a caller bug, never a data verdict).

    A day that simply must not be traded is NOT an error -- it comes back as a
    :class:`DayProfile` with ``poc_paise is None`` and a reason (CONTEXT 7-E3 counts it).
    """


class _Bar(Protocol):
    """Structural 1-minute bar: naive-IST open-stamp, integer-paise OHLC, share volume."""

    stamp: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int


# --- the window (CONTEXT 3.3; Q-8 makes it a parameter) --------------------------------


@dataclass(frozen=True)
class ProfileWindow:
    """A profile window, expressed as a count of 15-minute candles from the session open.

    CONTEXT 3.3 states the window as 1-minute stamps 09:15..11:14 and explains it in 15-minute
    terms ("the 15-min candle closing at 11:15 is INCLUDED"). Both are the same statement;
    holding the CANDLE COUNT and deriving the stamps keeps the two descriptions from ever
    drifting apart and keeps the clock times out of the code as literals.
    """

    name: str
    candles: int

    def __post_init__(self) -> None:
        if isinstance(self.candles, bool) or not isinstance(self.candles, int) or self.candles < 1:
            raise PocError(f"a profile window must span >= 1 candle, got {self.candles!r}.")
        _minutes_after_open(CANDLE_MINUTES * self.candles)  # refuses a window past 15:30

    @property
    def first_time(self) -> time:
        """The first 1-minute open-stamp in the window: the session open (CONTEXT 3.3)."""
        return SESSION_OPEN

    @property
    def last_time(self) -> time:
        """The LAST 1-minute open-stamp inside the window (inclusive).

        The window covers ``candles`` 15-minute candles from the open, i.e. the half-open span
        ``[09:15, 09:15 + 15*candles)``; the last open-stamped MINUTE in it is one minute
        earlier than that end (CONTEXT 7-E12). Eight candles -> 11:14; nine -> 11:29.
        """
        return _minutes_after_open(CANDLE_MINUTES * self.candles - 1)

    def contains(self, stamp: datetime) -> bool:
        """Is this 1-minute OPEN-stamp inside the window? PURE.

        Raises:
            PocError: ``stamp`` is tz-aware (CONTEXT 7-E8 keeps everything naive IST).
        """
        if not isinstance(stamp, datetime) or stamp.tzinfo is not None:
            raise PocError(f"1-minute stamps must be naive IST (CONTEXT 7-E8); got {stamp!r}.")
        return self.first_time <= stamp.time() <= self.last_time

    def describe(self) -> str:
        """One line for a report / evidence pack: ``spec-8-candle 09:15..11:14 (8 candles)``."""
        return (
            f"{self.name} {self.first_time.strftime('%H:%M')}..{self.last_time.strftime('%H:%M')} "
            f"({self.candles} candles)"
        )


#: THE window CONTEXT 3.3 specifies, and the default of every function here.
SPEC_WINDOW: ProfileWindow = ProfileWindow(name="spec-8-candle", candles=SPEC_WINDOW_CANDLES)

#: EVIDENCE ONLY (QUESTIONS.md Q-8 / Round-3 Q42). Never a default, never selected by the
#: engine; the chunk-6 gate evidence computes it so both answers exist before Q42 returns.
ALTERNATE_WINDOW: ProfileWindow = ProfileWindow(
    name="evidence-9-candle", candles=ALTERNATE_WINDOW_CANDLES
)


def window_bars(
    bars: Sequence[_Bar], day: date, *, window: ProfileWindow = SPEC_WINDOW
) -> tuple[_Bar, ...]:
    """The ``day``'s 1-minute bars that fall INSIDE ``window``, oldest first. PURE.

    Absent stamps are not an error and are not counted: on a gate-1-passing day they are
    minutes in which nothing traded (the completeness ruling, 2026-07-26).

    Raises:
        PocError: a bar belongs to another date (the minute loader hands one day at a time, so
            a mixed input is a caller bug), a stamp is tz-aware, or two bars share a stamp
            inside the window -- a duplicate would double-count volume, and CONTEXT 4.5 gate 2
            excludes any day carrying one, so reaching here means the gate was bypassed.
    """
    selected: list[_Bar] = []
    seen: set[datetime] = set()
    for bar in bars:
        stamp = bar.stamp
        if not isinstance(stamp, datetime) or stamp.tzinfo is not None:
            raise PocError(f"1-minute stamps must be naive IST (CONTEXT 7-E8); got {stamp!r}.")
        if stamp.date() != day:
            raise PocError(
                f"window_bars was given a bar stamped {stamp.isoformat()} while building "
                f"{day.isoformat()}'s profile; feed one trade date at a time."
            )
        if not window.contains(stamp):
            continue
        if stamp in seen:
            raise PocError(
                f"duplicate 1-minute stamp {stamp.isoformat()} inside the profile window; "
                "CONTEXT 4.5 gate 2 excludes a day with duplicates, so this day should never "
                "have reached the POC engine."
            )
        seen.add(stamp)
        selected.append(bar)
    selected.sort(key=lambda b: b.stamp)
    return tuple(selected)


# --- the row grid (CONTEXT 3.3 / CONTEXT 5, TradingView's documented math) --------------


@dataclass(frozen=True)
class Row:
    """One profile row: ``[lo_paise, hi_paise)`` on the tick grid, ``ticks`` ticks tall.

    ``hi_paise`` is the row's GRID edge, which is what its midpoint is taken from. Allocation
    into the TOPMOST row additionally reaches ``top`` (CONTEXT 3.3's top-inclusive rule) --
    see :meth:`RowGrid.alloc_hi_paise`.
    """

    lo_paise: int
    hi_paise: int
    ticks: int

    @property
    def midpoint_paise(self) -> Fraction:
        """The row's midpoint in paise -- EXACT, and legally half-paise (CONTEXT 3.3/7-E11)."""
        return Fraction(self.lo_paise + self.hi_paise, 2)


@dataclass(frozen=True)
class RowGrid:
    """The full set of rows for one window, bottom row first (CONTEXT 3.3)."""

    rows: tuple[Row, ...]
    bottom_paise: int
    top_paise: int
    tick_paise: int
    ticks_per_row: int
    total_ticks: int
    row_size: int

    def __len__(self) -> int:
        return len(self.rows)

    @property
    def grid_top_paise(self) -> int:
        """The top edge of the topmost row: ``bottom + total_ticks * tick``."""
        return self.rows[-1].hi_paise

    def alloc_hi_paise(self, index: int) -> int:
        """The upper bound used when ALLOCATING volume into row ``index``.

        Identical to the row's grid edge for every row but the topmost, whose bound is
        stretched to ``top`` when ``top`` sits above the grid (only possible when
        ``(top - bottom)`` is not a whole number of ticks -- an off-grid price, which the
        minute store flags rather than silently re-grids). CONTEXT 3.3's "the topmost row
        includes top" is then true in both senses: no traded price falls outside the profile,
        and the rows tile ``[bottom, top]`` exactly, so prorata conserves volume.
        """
        row = self.rows[index]
        if index == len(self.rows) - 1:
            return max(row.hi_paise, self.top_paise)
        return row.hi_paise

    def containing_index(self, price_paise: int) -> int:
        """The index of the row containing ``price_paise`` (CONTEXT 3.3 containment). PURE.

        Rows are half-open ``[lo, hi)``; the topmost row also includes ``top`` (and anything
        above the grid edge, which only the off-grid case can produce).

        Raises:
            PocError: the price is below ``bottom`` or above ``top`` -- it is not a price from
                this window, so no row contains it.
        """
        if price_paise < self.bottom_paise or price_paise > max(self.top_paise, self.grid_top_paise):
            raise PocError(
                f"price {price_paise} paise is outside the profile's "
                f"[{self.bottom_paise}, {max(self.top_paise, self.grid_top_paise)}] range; it is "
                "not a price of this window."
            )
        # Every row but the last is exactly ``ticks_per_row`` ticks tall (the last one holds
        # the remainder), so the index is arithmetic rather than a scan; the tail guard covers
        # the remainder row and the top-inclusive case.
        index = (price_paise - self.bottom_paise) // (self.ticks_per_row * self.tick_paise)
        if index >= len(self.rows):
            return len(self.rows) - 1
        return int(index)


def total_ticks(top_paise: int, bottom_paise: int, tick_paise: int) -> int:
    """``round((top - bottom) / tick)``, floored at 1 (CONTEXT 3.3). PURE.

    The floor is the spec's frozen-stock case: ``top == bottom`` gives 0 ticks, and CONTEXT 3.3
    says such a window "is one single-tick row". Rounding is half-EVEN -- Python's own
    ``round`` and the rounding this repo already uses for exact money
    (:mod:`acumen.minute_unadjust`); on the tick grid the division is exact, so the mode only
    ever decides an off-grid residual.

    Raises:
        PocError: ``tick_paise`` is not a positive whole number of paise, or ``top < bottom``.
    """
    if isinstance(tick_paise, bool) or not isinstance(tick_paise, int) or tick_paise < 1:
        raise PocError(
            f"tick_paise must be a positive whole number of paise (from the instrument master, "
            f"CONTEXT 4.3), got {tick_paise!r}."
        )
    if top_paise < bottom_paise:
        raise PocError(f"top {top_paise} is below bottom {bottom_paise}.")
    exact = Decimal(top_paise - bottom_paise) / Decimal(tick_paise)
    rounded = int(exact.to_integral_value(rounding=ROUND_HALF_EVEN))
    return max(1, rounded)


def ticks_per_row(ticks: int, row_size: int) -> int:
    """``totalTicks / N`` rounded to a whole number, minimum 1 (CONTEXT 3.3). PURE.

    "Direction chosen so the realized row count is closest to requested N": the realized count
    for a candidate ``tpr`` is ``ceil(totalTicks / tpr)`` (full rows plus the remainder row), so
    both candidates are counted and the closer one wins. TradingView's own worked example is
    decided this way and is NOT a tie -- 100 ticks at N=30 gives 34 rows at tpr=3 (4 away) and
    25 rows at tpr=4 (5 away), so tpr=3.

    **An exact tie is CONTEXT 3.3's one silence** -- it does not say which direction wins when
    both are equally close, and the tie is common (measured: 10.7%-20.0% of stored stock-days at
    N=24, with a different POC on every one). It is raised as QUESTIONS.md **Q-13**; the INTERIM
    implemented here keeps the SMALLER ``tpr`` (the finer profile), because that is the direction
    that reproduces all 25 frozen calibration values, six of which sit on a tie. It is not a
    preference and must not be flipped without the architect's answer.

    Raises:
        PocError: ``ticks`` or ``row_size`` is not a positive whole number.
    """
    for label, value in (("ticks", ticks), ("row_size", row_size)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise PocError(f"{label} must be a positive whole number, got {value!r}.")
    lower = max(1, ticks // row_size)
    upper = max(1, -(-ticks // row_size))  # ceil
    if lower == upper:
        return lower
    if abs(_realized_rows(ticks, lower) - row_size) <= abs(_realized_rows(ticks, upper) - row_size):
        return lower
    return upper


def _realized_rows(ticks: int, per_row: int) -> int:
    """How many rows ``per_row`` produces over ``ticks`` -- full rows plus the remainder row."""
    return -(-ticks // per_row)  # ceil


def build_rows(
    top_paise: int, bottom_paise: int, *, row_size: int, tick_paise: int
) -> RowGrid:
    """Build the profile's rows for ``[bottom, top]`` (CONTEXT 3.3, TV's documented math). PURE.

    Rows are stacked from ``bottom`` upward, each ``tpr`` ticks tall, and the LAST row carries
    whatever ticks remain (it may be smaller than ``tpr``), so the realized row count can
    exceed ``row_size`` -- fixture F6 pins TradingView's own example.

    Args:
        top_paise: ``max(high)`` over the window, integer paise.
        bottom_paise: ``min(low)`` over the window, integer paise.
        row_size: N, the Row Size (CONTEXT 3.3; ``config.yaml`` carries the trader's 24).
        tick_paise: the SYMBOL's tick from the instrument master (CONTEXT 4.3) -- never a
            constant, never a default (CONTEXT 3.3: "NEVER hardcode 0.05").
    """
    ticks = total_ticks(top_paise, bottom_paise, tick_paise)
    per_row = ticks_per_row(ticks, row_size)
    rows: list[Row] = []
    filled = 0
    while filled < ticks:
        span = min(per_row, ticks - filled)
        rows.append(
            Row(
                lo_paise=bottom_paise + filled * tick_paise,
                hi_paise=bottom_paise + (filled + span) * tick_paise,
                ticks=span,
            )
        )
        filled += span
    return RowGrid(
        rows=tuple(rows),
        bottom_paise=bottom_paise,
        top_paise=top_paise,
        tick_paise=tick_paise,
        ticks_per_row=per_row,
        total_ticks=ticks,
        row_size=row_size,
    )


# --- prorata spreading + the POC (CONTEXT 3.3) -----------------------------------------


def spread_volume(bars: Sequence[_Bar], grid: RowGrid) -> tuple[Fraction, ...]:
    """Distribute each bar's volume across the rows its range overlaps -- PRORATA. PURE.

    CONTEXT 3.3: "each 1-min bar's volume is distributed across the rows its [low, high] range
    overlaps, proportionally to the price-overlap fraction (``overlap / (high - low)``, with
    ``high == low`` treated as one-tick span)". The zero-range case is spelled out separately
    in the same section -- "a zero-range bar is a point: its full volume goes to the single row
    containing that price" -- and that is what happens here: a point bar's one-tick span lies
    wholly inside its own row, so "prorata over a one-tick span" and "all of it to the
    containing row" are the same allocation.

    Returns one exact :class:`~fractions.Fraction` per row, in row order. The rows tile
    ``[bottom, top]`` and every bar's range is inside it, so the totals sum EXACTLY to the
    window's volume -- an invariant the property test asserts on every fixture day.
    """
    totals = [Fraction(0)] * len(grid.rows)
    for bar in bars:
        volume = int(bar.volume)
        if volume == 0:
            continue  # a tradeless minute contributes nothing (the completeness ruling)
        if volume < 0:
            raise PocError(
                f"bar stamped {bar.stamp.isoformat()} carries a negative volume ({volume}); "
                "CONTEXT 4.5 gate 2 excludes a day with negative values."
            )
        low, high = int(bar.low_paise), int(bar.high_paise)
        if high < low:
            raise PocError(
                f"bar stamped {bar.stamp.isoformat()} has high {high} below low {low}; "
                "CONTEXT 4.5 gate 2 excludes a day with impossible OHLC."
            )
        if high == low:
            totals[grid.containing_index(low)] += volume
            continue
        span = high - low
        for index, row in enumerate(grid.rows):
            overlap = min(high, grid.alloc_hi_paise(index)) - max(low, row.lo_paise)
            if overlap > 0:
                totals[index] += Fraction(volume * overlap, span)
    return tuple(totals)


def poc_row_index(row_volumes: Sequence[Fraction]) -> int:
    """The index of the maximum-volume row; a TIE goes to the HIGHER-priced row (R1-Q9). PURE.

    Rows are ordered bottom-up, so walking upward and keeping the LAST index that is not
    beaten resolves every tie to the higher row -- side-independent, exactly as the trader
    answered (CONTEXT 3.3: "Tie -> the higher-priced row"; the bearish mirror in CONTEXT 3.4
    restates that it has no side condition).

    Raises:
        PocError: there are no rows.
    """
    if not row_volumes:
        raise PocError("a profile with no rows has no POC.")
    best_index = 0
    best = row_volumes[0]
    for index in range(1, len(row_volumes)):
        if row_volumes[index] >= best:  # >= walking upward == "tie goes to the higher row"
            best = row_volumes[index]
            best_index = index
    return best_index


# --- the day-level answer ---------------------------------------------------------------


@dataclass(frozen=True)
class DayProfile:
    """One stock-day's volume profile, or the recorded reason it has no POC.

    ``poc_paise`` is ``None`` exactly when ``reason != POC_OK``; chunk 9 counts the day by its
    reason (CONTEXT 7-E3) instead of guessing from the null.
    """

    day: date
    window: ProfileWindow
    reason: str
    poc_paise: Fraction | None = None
    grid: RowGrid | None = None
    row_volumes: tuple[Fraction, ...] = ()
    poc_row: int | None = None
    bar_count: int = 0
    window_volume: int = 0

    @property
    def has_poc(self) -> bool:
        return self.poc_paise is not None

    @property
    def poc_rupees(self) -> Decimal | None:
        """The POC in rupees, EXACT (a half-paise midpoint renders as e.g. ``815.275``).

        For display and evidence packs only -- every comparison in the engine uses
        ``poc_paise`` at full precision (CONTEXT 3.3: "all comparisons against it use full
        precision, never rounded prices").
        """
        if self.poc_paise is None:
            return None
        return Decimal(self.poc_paise.numerator) / Decimal(self.poc_paise.denominator) / Decimal(100)

    @property
    def zero_volume_profile(self) -> bool:
        """True when the window held bars but NO volume at all -- see :func:`day_profile`."""
        return self.has_poc and self.window_volume == 0


def day_profile(
    bars: Sequence[_Bar],
    day: date,
    *,
    row_size: int,
    tick_paise: int,
    volume_reconciled: bool | None,
    window: ProfileWindow = SPEC_WINDOW,
) -> DayProfile:
    """One stock-day's POC, or the reason there is none (CONTEXT 3.3). PURE.

    The order is the spec's: validity first, then the window slice, then the rows, then the
    prorata spread, then the POC.

    Args:
        bars: that day's stored 1-minute bars (the whole day is fine -- the window is sliced
            here). Absent stamps are no-trade minutes and are neither counted nor an error.
        day: the trade date.
        row_size: N (CONTEXT 3.3; ``config.yaml`` carries the trader-confirmed 24).
        tick_paise: the SYMBOL's tick from the instrument master (CONTEXT 4.3).
        volume_reconciled: the verdict of the battery that GOVERNS this day, and the ONLY
            validity test there is (the completeness ruling of 2026-07-26 retired E4's minute
            count). ``True`` -> the window is valid; ``False`` -> the day is excluded and gets no
            POC; ``None`` (the gate could not be run at all -- no raw daily row) -> also no POC,
            because the ruling's licence is "gate-1 PASSES" and an unrun gate has not passed (the
            same conservative reading the integrity gate takes).

            On a SETTLED day that verdict is gate 1's and nothing about this function has
            changed. On a LIVE day it is CONTEXT 4.7's ORACLE-FREE battery, because gate 1
            reconciles against a bhavcopy that does not exist during the session and gates 1/1P
            are structurally inapplicable to same-day data. The caller decides which battery
            governs and passes its verdict -- :attr:`acumen.signal_engine.DayGates.poc_licence`
            is the one place that choice is made, and this engine stays free of it.
        window: which window to build over. Defaults to the spec's 8-candle window; the
            9-candle :data:`ALTERNATE_WINDOW` exists for the Q-8/Q42 gate evidence only.

    Returns:
        A :class:`DayProfile`. ``poc_paise`` is ``None`` with a reason when the day fails
        gate 1, when gate 1 never ran, or when the window holds no candles at all. That last
        case is NOT a re-introduced count: ``max(high)`` over an empty window does not exist,
        so there is no profile to build -- it is the empty set, not a threshold.

    Note:
        A window that holds bars but ZERO total volume does produce a POC: every row ties at
        zero and CONTEXT 3.3's tie rule ("the higher-priced row") is unconditional, so the
        answer is the topmost row's midpoint. ``DayProfile.zero_volume_profile`` flags it so
        such a day can be counted rather than trusted silently -- recorded for the architect in
        QUESTIONS.md (chunk-6 FINDING).
    """
    if volume_reconciled is not True:
        reason = NO_POC_GATE_1_FAILED if volume_reconciled is False else NO_POC_GATE_1_UNRUN
        return DayProfile(day=day, window=window, reason=reason)

    selected = window_bars(bars, day, window=window)
    if not selected:
        return DayProfile(day=day, window=window, reason=NO_POC_EMPTY_WINDOW)

    grid = build_rows(
        top_paise=max(bar.high_paise for bar in selected),
        bottom_paise=min(bar.low_paise for bar in selected),
        row_size=row_size,
        tick_paise=tick_paise,
    )
    volumes = spread_volume(selected, grid)
    index = poc_row_index(volumes)
    return DayProfile(
        day=day,
        window=window,
        reason=POC_OK,
        poc_paise=grid.rows[index].midpoint_paise,
        grid=grid,
        row_volumes=volumes,
        poc_row=index,
        bar_count=len(selected),
        window_volume=sum(int(bar.volume) for bar in selected),
    )
