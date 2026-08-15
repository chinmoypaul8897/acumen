"""THE PARITY HARNESS (chunk 14): the live half and the backtester, candle for candle.

CONTEXT section 6 makes one claim and this module is the only thing in the repository that can
falsify it:

    "One engine, two modes: bias, poc, signals, simulate are pure functions over candles
     (no I/O); the backtester feeds them stored history, the screener feeds them the live
     poll -- same code path, guaranteed no backtest/live drift."

Chunk 13 built the seam that makes the claim structurally true (one ``evaluate``, called by
both) and tested that the seam is where it says it is. What it did not have is a harness that
takes a MORNING -- a recording, or a replayed day -- and asks the backtester the same question
one candle at a time. That is this module, and it exists because "same function" and "same
answer" are not the same sentence: the live half pins its POC at 11:15, reads a growing prefix,
refuses a phase regression, and decides at 15:15 what the backtester decides at once. Each of
those is a place a real difference could live.

## What is compared

For one symbol-day, two sequences of decisions:

* the LIVE sequence -- the shipped :class:`acumen.live_screener.LiveScreener` driven boundary by
  boundary, its own :class:`~acumen.live_screener.SymbolState` read after every sweep, and the
  alerts it actually delivered;
* the BACKTEST sequence -- :meth:`acumen.signal_engine.SignalPipeline.evaluate` over the WHOLE
  day at once (which is what the backtester does), priced by :mod:`acumen.simulate`, and then
  PROJECTED onto the same boundaries by :func:`project_boundaries`.

The projection is deliberately a **second reading** of the same answer, written here rather than
imported from the live layer. A harness that asked the live code what the live code did would
agree with itself on any day; this one re-derives, from the whole-day signal's own transition
trail, what a correct live morning must have shown at 11:15, 11:30, ... 15:15 -- and names the
field when the two disagree. The trail is CONTEXT 3.4's own audit record
(:class:`acumen.signals.Transition`, one per evaluated candle), so "every transition" is
compared literally rather than by proxy.

## What is judged, and what is disclosed instead

CONTEXT 4.7, the architect's 08-Aug-2026 ruling, in the law's own words: *"Section 6 parity is
judged on oracle-passing days; a live-alerted day the oracle later refuses is the disclosed,
bounded difference (live cannot see tomorrow)."* So every day carries its ORACLE verdict -- the
full CONTEXT 4.6 battery over the whole day, which is exactly what the next pre-open runs
(:func:`acumen.live_refresh.verify_prior_recording`) -- and a day the oracle refuses is REPORTED
with its reason and is not counted as a mismatch. It is not skipped either: a live morning that
alerted on a day the exchange's record then refuses is the residual CONTEXT 4.7 discloses, and
the report names it.

## Two sources, one comparison

* a **recording** (:class:`acumen.live_source.RecordingBarSource`) -- the bytes a morning really
  consumed. The backtest side is then the same bytes through the backtester's own battery and
  engine, which is the morning-after verification one step further on;
* the **minute lake** (:class:`acumen.live_source.StoredDayBarSource`) -- any historical day,
  where the two sides are genuinely independent: the live half accumulates the day through
  seventeen polls, the backtest half reads it once from Parquet.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from fractions import Fraction
from typing import Callable, Mapping, Sequence

from . import live_screener as ls
from . import signals as sig
from . import simulate as sim
from .bias_engine import DailyBias
from .live_recording import RecordedAlert
from .live_source import BarSource
from .minute_store import StoredBar
from .signal_engine import POSTURE_LIVE, SignalPipeline, StockDay, oracle_free_battery

#: The decision fields compared at every boundary. Order is the order a mismatch is reported in,
#: and it is the order CONTEXT 3.4 decides them: what state the day is in, then the four numbers
#: the trader trades on, then how it ended.
BOUNDARY_FIELDS: tuple[str, ...] = (
    "phase", "entry_paise", "stop_paise", "target_paise", "qty", "exit_kind", "exit_paise",
)

#: The day-level fields compared once. ``bias`` and ``bias_rule`` are CONTEXT 3.2's answer,
#: ``poc_paise`` is 3.3's, ``reference_paise`` is 3.4-1's -- the three inputs every later number
#: descends from, so a difference here explains every difference below it.
DAY_FIELDS: tuple[str, ...] = ("bias", "bias_rule", "side", "poc_paise", "reference_paise")


@dataclass(frozen=True)
class Decision:
    """One boundary's decision, in the vocabulary both sides can be read into."""

    boundary: datetime
    phase: str
    entry_paise: int | None = None
    stop_paise: int | None = None
    target_paise: int | None = None
    qty: int | None = None
    exit_kind: str | None = None
    exit_paise: int | None = None

    def as_dict(self) -> dict:
        payload = {"boundary": self.boundary.strftime("%H:%M")}
        payload.update({name: getattr(self, name) for name in BOUNDARY_FIELDS})
        return payload


@dataclass(frozen=True)
class DayParity:
    """One symbol-day's verdict: matched, mismatched by name, or oracle-refused."""

    symbol: str
    day: date
    #: The CONTEXT 4.6 battery's verdict over the whole day -- CONTEXT 4.7's "oracle".
    oracle_passed: bool
    oracle_reason: str
    #: Which bias_rule stratum this day belongs to, for the stratified report.
    stratum: str = ""
    #: How the live half was driven: ``lake`` or ``recording``.
    source: str = "lake"
    day_mismatches: tuple[str, ...] = ()
    boundary_mismatches: tuple[str, ...] = ()
    alert_mismatch: str = ""
    transitions_equal: bool = True
    boundaries: tuple[tuple[Decision, Decision], ...] = ()
    live_alerts: tuple[str, ...] = ()
    backtest_alerts: tuple[str, ...] = ()
    live_day: dict = field(default_factory=dict)
    backtest_day: dict = field(default_factory=dict)
    note: str = ""

    @property
    def mismatches(self) -> tuple[str, ...]:
        out = list(self.day_mismatches) + list(self.boundary_mismatches)
        if self.alert_mismatch:
            out.append(self.alert_mismatch)
        if not self.transitions_equal:
            out.append("transition trail: the live day's trail differs from the backtester's")
        return tuple(out)

    @property
    def judged(self) -> bool:
        """CONTEXT 4.7: parity is JUDGED on oracle-passing days and disclosed on the others."""
        return self.oracle_passed

    @property
    def matched(self) -> bool:
        return not self.mismatches

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "day": self.day.isoformat(),
            "stratum": self.stratum,
            "source": self.source,
            "oracle_passed": self.oracle_passed,
            "oracle_reason": self.oracle_reason,
            "judged": self.judged,
            "matched": self.matched,
            "mismatches": list(self.mismatches),
            "transitions_equal": self.transitions_equal,
            "live_alerts": list(self.live_alerts),
            "backtest_alerts": list(self.backtest_alerts),
            "day_fields": {"live": self.live_day, "backtest": self.backtest_day},
            "boundaries": [
                {"live": live.as_dict(), "backtest": want.as_dict()}
                for live, want in self.boundaries
            ],
            "note": self.note,
        }


# --- reading the LIVE half ---------------------------------------------------------------------


def live_decision(state: ls.SymbolState, boundary: datetime) -> Decision:
    """One :class:`~acumen.live_screener.SymbolState`, as a :class:`Decision`.

    A transcription, not a judgment: every field is read off the state the shipped screener
    published at that boundary. ``skipped`` is normalised away because it is a sweep OUTCOME
    laid over a real state (the screener's own rule -- see ``_reached_rank``), and the backtest
    side has no way to know that a poll failed; a skipped boundary keeps its numbers and is
    compared on them.
    """
    phase = state.phase
    if phase == ls.PHASE_SKIPPED:
        phase = _phase_from_numbers(state)
    return Decision(
        boundary=boundary,
        phase=phase,
        entry_paise=state.entry_paise,
        stop_paise=state.stop_paise,
        target_paise=state.target_paise,
        qty=state.qty,
        exit_kind=state.exit_kind,
        exit_paise=state.exit_paise,
    )


def _phase_from_numbers(state: ls.SymbolState) -> str:
    if state.exit_kind is not None:
        return ls.PHASE_EXITED
    if state.entry_paise is not None:
        return ls.PHASE_IN_TRADE
    return ls.PHASE_WAITING


def run_live(
    screener: ls.LiveScreener, symbol: str
) -> tuple[tuple[Decision, ...], tuple[RecordedAlert, ...], StockDay | None]:
    """Drive the shipped screener over a whole day and capture what it decided, boundary by
    boundary.

    Nothing is reached into: the day runs through :meth:`~acumen.live_screener.LiveScreener.
    run_day`, which is the same call ``run_screener`` makes, and the state is read after each
    sweep through the same ``on_sweep`` hook the dashboard uses.

    The alerts are filtered to THIS SYMBOL (REVIEW_14 PART 3): the sink is shared by the whole
    screener, so a screener holding more than one symbol used to hand every symbol's comparison
    the whole morning's alert list and false-mismatch all of them.
    """
    captured: list[Decision] = []

    def after(report: ls.SweepReport) -> None:
        captured.append(live_decision(screener.states[symbol], report.boundary))

    def before(boundary: datetime) -> None:
        clock = screener.clock
        setter = getattr(clock, "set", None)
        if setter is not None:
            setter(boundary)

    screener.run_day(on_sweep=after, before_sweep=before)
    sinks = [s for s in screener.sinks if isinstance(s, ls.CollectingAlertSink)]
    alerts = tuple(
        alert for alert in (sinks[0].alerts if sinks else ()) if alert.symbol == symbol
    )
    # The live half's OWN final answer over everything it collected -- the object whose
    # transition trail is compared against the backtester's.
    bias = screener.biases.get(symbol)
    minutes = screener.bars.get(symbol, ())
    final: StockDay | None = None
    if bias is not None and minutes:
        gates = screener.gates.get(symbol)
        if gates is None and screener.posture == POSTURE_LIVE:
            # REVIEW_14 **H5**: `build_live_screener` sets `gates = {} if live else
            # full_day_gates(...)`, because CONTEXT 4.7 gives a live morning no settled battery
            # at all -- so this branch never ran in live posture, `final` stayed None, and
            # `trails_equal` was structurally False for EVERY day the backtester has a signal.
            # Measured on 8 oracle-passing live-posture days: judged 8, matched 0, mismatched 8,
            # each with exactly one named mismatch -- the trail line -- while the live half's own
            # trail is byte-identical. It fails SAFE (it invents a mismatch and cannot hide one),
            # which is why the review rated it HIGH; but a harness that cannot judge the posture
            # the tool actually runs in judges nothing that matters. The battery used here is the
            # one the live half used at every sweep -- `LiveScreener._battery`'s own live branch,
            # over the bars in hand plus the duplicate stamps CONTEXT 4.5 gate 2 must see.
            gates = oracle_free_battery(
                screener.day, tuple(minutes) + screener.duplicate_bars.get(symbol, ())
            )
        if gates is not None:
            final = screener.pipeline.evaluate(
                symbol, screener.day, bias=bias, minutes=minutes, gates=gates,
                profile=screener.profiles.get(symbol),
            )
    return tuple(captured), alerts, final


# --- reading the BACKTEST half -----------------------------------------------------------------


def project_boundaries(
    stock_day: StockDay,
    *,
    day: date,
    boundaries: Sequence[datetime],
    risk_per_trade_paise: int,
) -> tuple[Decision, ...]:
    """What a correct live morning MUST have shown at each boundary, from the whole-day answer.

    This is the harness's second reading and the reason it can find anything. The backtester
    answers the day at once; a live morning meets the same day one candle at a time. So the
    whole-day :class:`~acumen.signals.SignalDay` is walked forward here:

    * the state at boundary ``T`` is the ``state_after`` of the last transition whose candle has
      CLOSED by ``T`` -- CONTEXT 3.4's own trail, not a re-derivation of the rules;
    * an entry is visible from the boundary its candle closes on, and only then (CONTEXT 3.4-2:
      entry price IS that candle's close, so nothing about it can be known earlier);
    * ``qty`` is :func:`acumen.simulate.position_size`, and a ``qty == 0`` day is CONTEXT 3.5's
      *"no trade, consumed + logged"* -- the backtester writes no fill for it, so the projection
      shows the day consumed and refused rather than in a trade (REVIEW_13 M21);
    * a stop or target exit is visible from the boundary its candle closes on; a SQUARE-OFF is
      visible only from 15:15, because before the 15:00-15:15 candle has closed the engine's
      ``square-off`` marker is a description of a prefix that has run out of candles and not an
      exit that has happened;
    * the exit PRICE is the simulator's own (:func:`acumen.simulate.exit_price_paise`), so the
      comparison runs through the backtest money layer rather than around it.
    """
    if not stock_day.evaluated or stock_day.signal is None:
        return tuple(
            Decision(boundary=stamp, phase=ls.PHASE_REFUSED) for stamp in boundaries
        )
    signal = stock_day.signal
    entry = signal.entry
    exit_event = signal.exit_event
    qty = (
        sim.position_size(risk_per_trade_paise, int(entry.risk_paise))
        if entry is not None and risk_per_trade_paise else None
    )
    fill = (
        sim.exit_price_paise(entry, exit_event, stock_day.bars)
        if entry is not None and exit_event is not None and qty else None
    )
    square_off_close = sig.bar_close_stamp(day, sig.SQUARE_OFF_BAR)
    reference_close = sig.bar_close_stamp(day, sig.REFERENCE_BAR)

    out: list[Decision] = []
    for stamp in boundaries:
        if stamp < reference_close:
            out.append(Decision(boundary=stamp, phase=ls.PHASE_WAITING))
            continue
        seen = [t for t in signal.transitions if t.close_stamp <= stamp]
        state = seen[-1].state_after if seen else signal.initial_state
        entered = entry is not None and entry.close_stamp <= stamp
        if entered and qty == 0:
            # CONTEXT 3.5's own outcome: the cross consumed the day and nothing was bought.
            out.append(Decision(boundary=stamp, phase=ls.PHASE_REFUSED, qty=0))
            continue
        exited = (
            entered and exit_event is not None and exit_event.close_stamp <= stamp
            and (exit_event.kind != sig.EXIT_SQUARE_OFF or stamp >= square_off_close)
        )
        if exited:
            phase = ls.PHASE_EXITED
        elif entered and entry.close_stamp == stamp:
            phase = ls.PHASE_TRIGGERED
        elif entered:
            phase = ls.PHASE_IN_TRADE
        elif state == sig.STATE_ARMED:
            phase = ls.PHASE_ARMED
        else:
            phase = ls.PHASE_WAITING
        out.append(Decision(
            boundary=stamp,
            phase=phase,
            entry_paise=int(entry.entry_paise) if entered else None,
            stop_paise=int(entry.stop_paise) if entered else None,
            target_paise=int(entry.target_paise) if entered else None,
            qty=qty if entered else None,
            exit_kind=exit_event.kind if exited else None,
            exit_paise=fill if exited else None,
        ))
    return tuple(out)


def expected_alerts(decisions: Sequence[Decision]) -> tuple[str, ...]:
    """The alert KINDS a correct morning delivers for a projected sequence, in order.

    Derived from the projection rather than from the screener: an alert exists where the
    decision the trader must act on first appears. Arming, the trigger, and the exit -- which is
    a square-off when the day ran out of candles and an exit otherwise. Nothing is emitted for a
    consumed-but-unsizable day (CONTEXT 3.5: no trade), which is REVIEW_13 M21 stated from the
    other side.
    """
    kinds: list[str] = []
    for decision in decisions:
        if decision.phase == ls.PHASE_ARMED and ls.ALERT_ARMED not in kinds:
            kinds.append(ls.ALERT_ARMED)
        if decision.entry_paise is not None and ls.ALERT_TRIGGER not in kinds:
            kinds.append(ls.ALERT_TRIGGER)
        if decision.exit_kind is not None:
            kind = (
                ls.ALERT_SQUARE_OFF if decision.exit_kind == sig.EXIT_SQUARE_OFF
                else ls.ALERT_EXIT
            )
            if kind not in kinds:
                kinds.append(kind)
    return tuple(kinds)


def _day_fields(
    bias: DailyBias | None, side: str | None, poc: Fraction | None, reference: int | None
) -> dict:
    return {
        "bias": None if bias is None else bias.bias,
        "bias_rule": None if bias is None else bias.rule,
        "side": side,
        "poc_paise": None if poc is None else str(poc),
        "reference_paise": reference,
    }


def compare(
    *,
    symbol: str,
    day: date,
    live: Sequence[Decision],
    backtest: Sequence[Decision],
    live_day: dict,
    backtest_day: dict,
    live_alerts: Sequence[RecordedAlert],
    oracle_passed: bool,
    oracle_reason: str,
    transitions_equal: bool = True,
    stratum: str = "",
    source: str = "lake",
    note: str = "",
) -> DayParity:
    """Two sequences in, one named verdict out. Every mismatch carries its boundary and field."""
    day_mismatches = [
        f"{name}: live={live_day.get(name)!r} backtest={backtest_day.get(name)!r}"
        for name in DAY_FIELDS
        if live_day.get(name) != backtest_day.get(name)
    ]
    boundary_mismatches: list[str] = []
    if len(live) != len(backtest):
        boundary_mismatches.append(
            f"boundary count: live={len(live)} backtest={len(backtest)}"
        )
    for got, want in zip(live, backtest):
        for name in BOUNDARY_FIELDS:
            if getattr(got, name) != getattr(want, name):
                boundary_mismatches.append(
                    f"{got.boundary.strftime('%H:%M')} {name}: "
                    f"live={getattr(got, name)!r} backtest={getattr(want, name)!r}"
                )
    delivered = tuple(alert.kind for alert in live_alerts)
    wanted = expected_alerts(backtest)
    alert_mismatch = (
        "" if delivered == wanted
        else f"alerts: live={list(delivered)} backtest={list(wanted)}"
    )
    return DayParity(
        symbol=symbol, day=day, oracle_passed=oracle_passed, oracle_reason=oracle_reason,
        stratum=stratum, source=source,
        day_mismatches=tuple(day_mismatches),
        boundary_mismatches=tuple(boundary_mismatches),
        alert_mismatch=alert_mismatch,
        transitions_equal=transitions_equal,
        boundaries=tuple(zip(live, backtest)),
        live_alerts=delivered,
        backtest_alerts=wanted,
        live_day=live_day,
        backtest_day=backtest_day,
        note=note,
    )


def parity_for_screener(
    screener: ls.LiveScreener,
    symbol: str,
    *,
    minutes_for_backtest: Sequence[StoredBar] | None = None,
    stratum: str = "",
    source: str = "lake",
) -> DayParity:
    """The whole comparison for one symbol-day, from a screener that has NOT yet been run.

    ``minutes_for_backtest`` is the whole day the BACKTEST side reads. ``None`` means the minute
    lake, which is the independent-sources case; a recording replay passes the recording's own
    bars, which is CONTEXT 4.7's morning-after construction.
    """
    day = screener.day
    bias = screener.biases.get(symbol)
    live_decisions, alerts, live_final = run_live(screener, symbol)

    minutes = (
        tuple(minutes_for_backtest) if minutes_for_backtest is not None
        else tuple(screener.pipeline.minute_store.minutes(symbol, day))
    )
    gates = screener.gates.get(symbol)
    if bias is None or not minutes:
        return DayParity(
            symbol=symbol, day=day, oracle_passed=False, stratum=stratum, source=source,
            oracle_reason=(
                "no bias for this symbol-day" if bias is None
                else "no whole day for the backtest side to read"
            ),
            note="not judged: the backtest side has nothing to answer with",
        )
    if gates is None:
        gates = screener.pipeline.gate_day(symbol, day, minutes)
    stock_day = screener.pipeline.evaluate(
        symbol, day, bias=bias, minutes=minutes, gates=gates
    )
    boundaries = tuple(decision.boundary for decision in live_decisions)
    projected = project_boundaries(
        stock_day, day=day, boundaries=boundaries,
        risk_per_trade_paise=screener.risk_per_trade_paise,
    )
    state = screener.states[symbol]
    signal = stock_day.signal
    profile = stock_day.profile
    live_fields = _day_fields(
        screener.biases.get(symbol), state.side, state.poc_paise, state.reference_paise
    )
    backtest_fields = _day_fields(
        stock_day.bias, stock_day.side,
        None if profile is None else profile.poc_paise,
        None if signal is None else signal.reference_paise,
    )
    trails_equal = (
        live_final is not None and live_final.signal is not None and signal is not None
        and live_final.signal.transitions == signal.transitions
    ) or (signal is None and live_final is None)
    return compare(
        symbol=symbol, day=day,
        live=live_decisions, backtest=projected,
        live_day=live_fields, backtest_day=backtest_fields,
        live_alerts=alerts,
        oracle_passed=bool(gates.usable),
        oracle_reason=(
            gates.refusal_detail[1] if gates.refusal_detail is not None
            else "the FULL CONTEXT 4.6 battery accepts this day"
        ),
        transitions_equal=trails_equal,
        stratum=stratum, source=source,
    )


def summarise(results: Sequence[DayParity]) -> dict:
    """The report's own headline: judged, matched, disclosed, and every mismatch by name."""
    judged = [row for row in results if row.judged]
    disclosed = [row for row in results if not row.judged]
    return {
        "days": len(results),
        "judged": len(judged),
        "matched": len([row for row in judged if row.matched]),
        "mismatched": len([row for row in judged if not row.matched]),
        "disclosed_oracle_refused": len(disclosed),
        "mismatches": [
            {"symbol": row.symbol, "day": row.day.isoformat(), "named": list(row.mismatches)}
            for row in judged if not row.matched
        ],
        "disclosed": [
            {"symbol": row.symbol, "day": row.day.isoformat(),
             "reason": row.oracle_reason, "live_alerts": list(row.live_alerts)}
            for row in disclosed
        ],
    }


__all__ = [
    "BOUNDARY_FIELDS",
    "DAY_FIELDS",
    "DayParity",
    "Decision",
    "compare",
    "expected_alerts",
    "live_decision",
    "parity_for_screener",
    "project_boundaries",
    "run_live",
    "summarise",
]
