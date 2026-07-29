"""The trade simulator: CONTEXT 3.5, as PURE functions (a SignalDay in, a TradeRecord out).

Chunk 7 decided WHAT happened on a stock-day -- whether a cross qualified, at what price the
entry was, where the stop and the target sit, and WHICH candle ends the trade and why. This
module turns that into money, and it is deliberately the only place in the repo where a share
count or a rupee figure is computed.

**The three jobs, and nothing else.**

1. **Sizing (CONTEXT 3.5).** ``qty = floor(risk_per_trade / (entry - SL))``, shorts
   ``floor(risk_per_trade / (SL - entry))`` -- exact integer division of paise by paise. The
   risk amount is NOT known here: it is handed in by the caller, which reads it from
   ``config.yaml`` through :meth:`acumen.config.Config.require_risk_per_trade_paise`. A
   hardcoded 100000 in this module would be a defect even though it is today's right number.
   ``qty == 0`` -- the per-share risk exceeds the whole trade risk, which is real on a
   high-priced stock with a wide entry candle -- is a recorded NO-TRADE: zero cost, zero PnL,
   the day still CONSUMED (CONTEXT 3.4-2: the first qualifying cross consumes the stock-day
   "even if the trade is unsizable"), and COUNTED. Such a day is never dropped.

2. **Exit pricing (CONTEXT 3.4-5).** Chunk 7 marks the exit as an EVENT; this module prices
   it, and it prices it at the LEVEL, never at the candle's own extreme:

   * target hit -> exactly the target level;
   * stop hit -> exactly the stop level;
   * both touched in one candle -> the stop level (R1-Q20: the stop wins). That decision was
     already made upstream -- ``ExitEvent.kind`` is the stop -- so this module prices it, it
     does not re-decide it;
   * square-off -> the CLOSE of the candle the marker names, which is the 15:00-stamped
     candle (the one closing 15:15, R1-Q18/E12). Shorts mirror all four exactly.

3. **Money (CONTEXT 3.5).** ``gross = qty x (exit - entry)`` on a long and
   ``qty x (entry - exit)`` on a short; ``net = gross - cost``; the cost is the flat
   round-trip charge (R1-Q23, from config) and it is charged ONCE per EXECUTED trade. A day
   that executed nothing pays nothing -- there is no round trip to charge.

**What this module must never do.** It never re-runs the state machine, never re-decides an
exit, never re-prices a level chunk 7 computed, never caps or scales a position by capital,
and never drops a day. Portfolio aggregation, the equity curve, the metrics and the Q40-d
capital-infeasibility flags are chunk 9 and chunk 10.

PURE (CONTEXT 6): no I/O, no network, no clock read, no float. Every price and every rupee
figure is an integer number of paise (CONTEXT 7-E11), so a PnL sum over 400,000 stock-days is
exact -- the arithmetic here is all ``+``, ``-``, ``*`` and floor division; there is no true
division anywhere in the file and no float can be produced.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from fractions import Fraction
from typing import Protocol, Sequence

from .signals import (
    EXIT_SQUARE_OFF,
    EXIT_STOP,
    EXIT_TARGET,
    LONG,
    SHORT,
    Entry,
    ExitEvent,
    SignalDay,
)

#: Flags on a :class:`TradeRecord`. They name the shapes a later chunk has to be able to
#: COUNT -- CONTEXT 3.5's report has to disclose them, and a count is only honest if the day
#: it counts was kept.
#:
#: The per-share risk is larger than the whole trade risk, so the floor sizes zero shares.
#: Nothing is bought, nothing is paid, and the day is still consumed (CONTEXT 3.4-2).
FLAG_QTY_ZERO_UNSIZABLE: str = "qty_zero_unsizable"
#: The signal engine itself refused the cross as unsizable (CONTEXT 3.4-3's degenerate
#: ``entry == SL``, i.e. a risk of zero or less). The day is consumed with no entry at all.
FLAG_SIGNAL_UNSIZABLE: str = "signal_unsizable_consumed"
#: No entry object at all on the day: either no qualifying cross, or the refusal above.
FLAG_NO_ENTRY: str = "no_entry"
#: The exit candle touched the stop AND the target; the stop won (R1-Q20). The report has to
#: disclose how often an ambiguous candle was resolved in the pessimistic direction.
FLAG_BOTH_TOUCHED_STOP_WINS: str = "both_touched_stop_wins"
#: The square-off marker names the ENTRY candle, because no 15-minute candle traded after it
#: -- so the day's last traded 15-minute price IS the entry close (chunk-7 decision B159).
#: A flat trade, flagged because it is a data shape, not a strategy outcome.
FLAG_SQUARE_OFF_AT_ENTRY_CANDLE: str = "square_off_at_the_entry_candle"


class SimulateError(ValueError):
    """The inputs handed to the simulator are not a priceable stock-day."""


class _Bar(Protocol):
    """Anything with the 15-minute bar fields the square-off price is read from."""

    stamp: datetime
    close_paise: int


@dataclass(frozen=True)
class TradeRecord:
    """One stock-day priced: the trade and its money, or the recorded reason there is none.

    Exactly one record exists per evaluated stock-day -- including the days that traded
    nothing -- so chunk 9 counts records rather than inferring a day's fate from a null.

    All money is integer paise (CONTEXT 7-E11). ``gross_pnl_paise``, ``cost_paise`` and
    ``net_pnl_paise`` are zero on every record that did not execute, and
    ``net == gross - cost`` always holds by construction.

    The provenance fields (``bias``, ``poc_paise``, ``gap_entry``, ``tie_case``, ``consumed``,
    ``outcome``, the stamps) travel with the money because chunk 12's replay pack has to
    explain a rupee figure in plain English on the trader's own chart.
    """

    symbol: str
    day: date
    side: str

    # --- the trade, as chunk 7 computed it (None on a day with no entry at all) ---
    entry_paise: int | None
    stop_paise: int | None
    target_paise: int | None
    per_share_risk_paise: int | None
    entry_stamp: datetime | None
    entry_close_stamp: datetime | None

    # --- the exit, as this module prices it ---
    exit_kind: str | None
    exit_paise: int | None
    exit_stamp: datetime | None
    exit_close_stamp: datetime | None

    # --- the money (CONTEXT 3.5) ---
    qty: int
    gross_pnl_paise: int
    cost_paise: int
    net_pnl_paise: int
    risk_per_trade_paise: int

    # --- provenance, straight from the SignalDay and its inputs ---
    outcome: str
    consumed: bool
    gap_entry: bool
    tie_case: bool
    bias: str | None
    poc_paise: Fraction | None
    reference_paise: int | None
    flags: tuple[str, ...]
    detail: str

    @property
    def executed(self) -> bool:
        """Did a position actually open? Only an executed trade pays the round-trip cost."""
        return self.qty > 0

    @property
    def signalled(self) -> bool:
        """Did the day produce an entry signal, sizable or not?"""
        return self.entry_paise is not None


# --- sizing (CONTEXT 3.5) ----------------------------------------------------------------


def position_size(risk_per_trade_paise: int, per_share_risk_paise: int) -> int:
    """``floor(risk_per_trade / per_share_risk)`` in exact integer paise. PURE.

    CONTEXT 3.5: "Sizing: fixed INR risk per trade ... ``qty = floor(1000 / (entry - SL))``
    (shorts: ``SL - entry``)". Both arguments are paise, so this is Python's floor division on
    two ints -- there is no float, no rounding mode and no tick assumption anywhere in it.

    The result satisfies two properties that the tests assert on every fixture and over a
    swept grid, because together they ARE the definition of the floor:

    * ``qty * per_share_risk <= risk_per_trade`` -- the trade never risks more than the
      trader's fixed amount, on any day, ever;
    * ``(qty + 1) * per_share_risk > risk_per_trade`` -- and it is never smaller than it has
      to be. At ``qty == 0`` this second property is exactly the unsizable condition: one
      single share would already risk more than the whole trade budget.

    Raises:
        SimulateError: either amount is not a positive whole number of paise. A per-share
            risk of zero or less never reaches here (chunk 7 refuses the day as unsizable
            first, CONTEXT 3.4-3) and would be a division by zero or a negative share count.
    """
    _require_positive_int(risk_per_trade_paise, "risk_per_trade_paise")
    _require_positive_int(per_share_risk_paise, "per_share_risk_paise")
    return risk_per_trade_paise // per_share_risk_paise


# --- exit pricing (CONTEXT 3.4-5) ---------------------------------------------------------


def exit_price_paise(entry: Entry, exit_event: ExitEvent, bars: Sequence[_Bar]) -> int:
    """The price the marked exit fills at, in paise. PURE.

    CONTEXT 3.4-5, priced literally:

    * :data:`~acumen.signals.EXIT_TARGET` -> ``entry.target_paise``, the target LEVEL. The
      candle's high may have run far past it (CONTEXT 7-E9: fills are idealized, disclosed);
    * :data:`~acumen.signals.EXIT_STOP` -> ``entry.stop_paise``, the stop LEVEL -- including
      when the candle touched both levels, because R1-Q20's "the stop wins" was already
      applied upstream when the event was marked;
    * :data:`~acumen.signals.EXIT_SQUARE_OFF` -> the CLOSE of the candle the marker names
      (R1-Q18: "square off at the 15:00-15:15 candle's close"). Normally that is the
      15:00-stamped candle; when nothing traded after the entry candle the marker names the
      entry candle itself, whose close IS the day's last traded 15-minute price (chunk-7
      decision B159, approved by REVIEW_7).

    Raises:
        SimulateError: the event kind is not one of the three, or a square-off names a candle
            that is not in ``bars``.
    """
    if exit_event.kind == EXIT_TARGET:
        return int(entry.target_paise)
    if exit_event.kind == EXIT_STOP:
        return int(entry.stop_paise)
    if exit_event.kind == EXIT_SQUARE_OFF:
        for bar in bars:
            if bar.stamp == exit_event.stamp:
                return int(bar.close_paise)
        raise SimulateError(
            f"square-off marks the {exit_event.stamp} candle but it is not among the "
            "15-minute bars handed to the simulator -- the marker names a candle that traded."
        )
    raise SimulateError(f"unknown exit kind {exit_event.kind!r}.")


# --- money (CONTEXT 3.5) ------------------------------------------------------------------


def gross_pnl_paise(side: str, qty: int, entry_paise: int, exit_paise: int) -> int:
    """``qty x (exit - entry)`` long, ``qty x (entry - exit)`` short, in paise. PURE.

    CONTEXT 3.5: "PnL per trade: ``(exit - entry) x qty - 100`` (long; mirrored short)". The
    sign discipline is the whole point of the mirror: a short that exits BELOW its entry made
    money.
    """
    if side == LONG:
        return qty * (exit_paise - entry_paise)
    if side == SHORT:
        return qty * (entry_paise - exit_paise)
    raise SimulateError(f"side must be {LONG!r} or {SHORT!r}, got {side!r}.")


def net_pnl_paise(gross_paise: int, cost_paise: int) -> int:
    """``gross - cost``. The cost is the caller's; this never invents one. PURE."""
    return gross_paise - cost_paise


# --- the simulator ------------------------------------------------------------------------


def simulate_day(
    signal: SignalDay,
    bars: Sequence[_Bar] = (),
    *,
    symbol: str,
    risk_per_trade_paise: int,
    cost_paise: int,
    bias: str | None = None,
    tie_case: bool = False,
) -> TradeRecord:
    """Price one evaluated stock-day (CONTEXT 3.5). PURE.

    Args:
        signal: the day's :class:`~acumen.signals.SignalDay` from chunk 7 -- entered,
            consumed-unsizable, or one of the no-cross outcomes. Every one of them yields a
            record.
        bars: that day's 15-minute candles, the same sequence chunk 7 evaluated. Only a
            square-off reads them (for the marked candle's close); a target or stop exit
            prices off the levels alone.
        symbol: the ticker, carried onto the record.
        risk_per_trade_paise: CONTEXT 3.5's fixed rupee risk, in paise, from
            ``config.yaml`` via the loader. Never defaulted here.
        cost_paise: CONTEXT 3.5's flat round-trip cost, in paise, from ``config.yaml`` via the
            loader. Charged once per EXECUTED trade, never on a no-trade day.
        bias: the day's bias (CONTEXT 3.2), carried for the replay pack.
        tie_case: this day's bias came from the Rule-3 TIE (``DailyBias.tie_case``) -- the
            rare hand-checkable shape plan.md's chunk-12 card wants listed.

    Returns:
        Exactly one :class:`TradeRecord`, whether or not money changed hands.

    Raises:
        SimulateError: the money inputs are not positive whole paise, the side is unknown,
            an entered day carries no exit event, or a square-off names a candle not in
            ``bars``.
    """
    _require_positive_int(risk_per_trade_paise, "risk_per_trade_paise")
    _require_non_negative_int(cost_paise, "cost_paise")
    if signal.side not in (LONG, SHORT):
        raise SimulateError(f"side must be {LONG!r} or {SHORT!r}, got {signal.side!r}.")

    common = dict(
        symbol=symbol,
        day=signal.day,
        side=signal.side,
        risk_per_trade_paise=risk_per_trade_paise,
        outcome=signal.outcome,
        consumed=signal.consumed,
        tie_case=tie_case,
        bias=bias,
        poc_paise=signal.poc_paise,
        reference_paise=signal.reference_paise,
    )

    entry = signal.entry
    if entry is None:
        return _no_entry_record(signal, common)

    exit_event = signal.exit_event
    if exit_event is None:
        raise SimulateError(
            f"{symbol} {signal.day}: an entered day must carry an exit event (CONTEXT 3.4-5 "
            "always ends the trade -- stop, target or the 15:15 square-off)."
        )
    per_share_risk = int(entry.risk_paise)
    if per_share_risk <= 0:
        raise SimulateError(
            f"{symbol} {signal.day}: per-share risk {per_share_risk} paise cannot be sized; "
            "chunk 7 refuses a degenerate entry before it builds an Entry (CONTEXT 3.4-3)."
        )

    qty = position_size(risk_per_trade_paise, per_share_risk)
    if qty == 0:
        return _unsizable_record(signal, entry, exit_event, per_share_risk, common)

    fill = exit_price_paise(entry, exit_event, bars)
    gross = gross_pnl_paise(signal.side, qty, int(entry.entry_paise), fill)
    net = net_pnl_paise(gross, cost_paise)

    flags: list[str] = []
    if exit_event.both_touched:
        flags.append(FLAG_BOTH_TOUCHED_STOP_WINS)
    if exit_event.kind == EXIT_SQUARE_OFF and exit_event.stamp == entry.stamp:
        flags.append(FLAG_SQUARE_OFF_AT_ENTRY_CANDLE)

    return TradeRecord(
        entry_paise=int(entry.entry_paise),
        stop_paise=int(entry.stop_paise),
        target_paise=int(entry.target_paise),
        per_share_risk_paise=per_share_risk,
        entry_stamp=entry.stamp,
        entry_close_stamp=entry.close_stamp,
        exit_kind=exit_event.kind,
        exit_paise=fill,
        exit_stamp=exit_event.stamp,
        exit_close_stamp=exit_event.close_stamp,
        qty=qty,
        gross_pnl_paise=gross,
        cost_paise=cost_paise,
        net_pnl_paise=net,
        gap_entry=entry.gap_entry,
        flags=tuple(flags),
        detail=(
            f"{signal.side} {qty} x {format_paise(int(entry.entry_paise))} -> "
            f"{format_paise(fill)} ({exit_event.kind}); per-share risk "
            f"{format_paise(per_share_risk)}, gross {format_paise(gross)}, cost "
            f"{format_paise(cost_paise)}, net {format_paise(net)}"
        ),
        **common,
    )


def _no_entry_record(signal: SignalDay, common: dict) -> TradeRecord:
    """A day with no entry at all: no cross, or a cross chunk 7 refused as degenerate.

    Both are recorded, never dropped. ``consumed`` distinguishes them -- CONTEXT 3.4-2's
    refused cross consumed the stock-day, a day that never crossed did not.
    """
    flags = [FLAG_NO_ENTRY]
    if signal.consumed:
        flags.append(FLAG_SIGNAL_UNSIZABLE)
        detail = (
            "no trade: the first qualifying cross could not be sized (CONTEXT 3.4-3) and "
            "CONSUMED the stock-day (CONTEXT 3.4-2) -- no cost, no PnL"
        )
    else:
        detail = f"no trade: {signal.outcome} -- nothing consumed, no cost, no PnL"
    return TradeRecord(
        entry_paise=None,
        stop_paise=None,
        target_paise=None,
        per_share_risk_paise=None,
        entry_stamp=None,
        entry_close_stamp=None,
        exit_kind=None,
        exit_paise=None,
        exit_stamp=None,
        exit_close_stamp=None,
        qty=0,
        gross_pnl_paise=0,
        cost_paise=0,
        net_pnl_paise=0,
        gap_entry=False,
        flags=tuple(flags),
        detail=detail,
        **common,
    )


def _unsizable_record(
    signal: SignalDay,
    entry: Entry,
    exit_event: ExitEvent,
    per_share_risk: int,
    common: dict,
) -> TradeRecord:
    """``qty == 0``: the per-share risk exceeds the whole trade risk. CONTEXT 3.5.

    The signal was real and the day is CONSUMED (CONTEXT 3.4-2), so the record keeps the
    entry, the stop, the target and the exit KIND for the replay pack -- but there is no fill
    price, because nothing was ever bought or sold, and therefore no cost and no PnL. Writing
    a counterfactual fill here would let a later chunk sum a trade that never existed.
    """
    return TradeRecord(
        entry_paise=int(entry.entry_paise),
        stop_paise=int(entry.stop_paise),
        target_paise=int(entry.target_paise),
        per_share_risk_paise=per_share_risk,
        entry_stamp=entry.stamp,
        entry_close_stamp=entry.close_stamp,
        exit_kind=exit_event.kind,
        exit_paise=None,
        exit_stamp=exit_event.stamp,
        exit_close_stamp=exit_event.close_stamp,
        qty=0,
        gross_pnl_paise=0,
        cost_paise=0,
        net_pnl_paise=0,
        gap_entry=entry.gap_entry,
        flags=(FLAG_QTY_ZERO_UNSIZABLE,),
        detail=(
            f"no trade: per-share risk {format_paise(per_share_risk)} exceeds the whole "
            f"trade risk {format_paise(common['risk_per_trade_paise'])}, so "
            "floor(risk / per-share risk) = 0 shares (CONTEXT 3.5). The cross still CONSUMED "
            "the stock-day (CONTEXT 3.4-2); no cost, no PnL"
        ),
        **common,
    )


# --- presentation (PURE: integer arithmetic only, no float, no rounding) -------------------


def format_paise(paise: int) -> str:
    """Integer paise -> a plain rupee string, e.g. ``299250`` -> ``Rs 2,992.50``. PURE.

    Written with ``//`` and ``%`` rather than a division, so no float touches a money figure
    on its way to a report the trader reads (CONTEXT 7-E11). ASCII "Rs" rather than the rupee
    sign: the operator's console is cp1252 (see src/acumen/config.py).
    """
    sign = "-" if paise < 0 else ""
    magnitude = -paise if paise < 0 else paise
    rupees, remainder = magnitude // 100, magnitude % 100
    return f"{sign}Rs {rupees:,}.{remainder:02d}"


def _require_positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SimulateError(f"{name} must be a whole number of paise, got {value!r}.")
    if value <= 0:
        raise SimulateError(f"{name} must be > 0 paise, got {value}.")


def _require_non_negative_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SimulateError(f"{name} must be a whole number of paise, got {value!r}.")
    if value < 0:
        raise SimulateError(f"{name} must be >= 0 paise, got {value}.")
