"""THE LIVE SCREENER (chunk 13): the same engine, driven by the clock instead of by history.

This is the tool's second half. The backtester answers *"would this have worked"*; the screener
answers *"is it happening now"* -- and it answers it with the code the backtester was reviewed
on, because CONTEXT section 6 makes that the law rather than the goal:

    "One engine, two modes: bias, poc, signals, simulate are pure functions over candles
     (no I/O); the backtester feeds them stored history, the screener feeds them the live
     poll -- same code path, guaranteed no backtest/live drift."

**IT NEVER PLACES AN ORDER.** CONTEXT section 1 R4 and CLAUDE.md rule 4: read-only endpoints
only, no order-placement code anywhere. The screener alerts; the human trades. A tripwire test
(:mod:`tests.test_live_safety`) walks every module in this package and fails the build if an
order endpoint is ever so much as named.

## The morning, in order

1. **Pre-open.** Today's bias for every symbol, from the STORED daily candles (D-1, D-2),
   through :class:`acumen.bias_engine.BiasEngine` -- including Rule 3's 1-minute scan of D-1,
   through the RUN's own gated loader. No new logic exists here: the bias the screener shows at
   09:00 is the bias the backtester would have computed for the same day.
2. **09:15-11:14, collecting.** 1-minute bars accumulate into the recording. Nothing is decided.
3. **11:15, the POC pass.** CONTEXT 3.3 over the 09:15-11:14 window, and CONTEXT 3.4-1's
   reference from the 11:00-11:15 candle's close. The POC is fixed for the rest of the day.
4. **11:30 -> 15:15, the boundary sweeps.** Each just-closed 15-minute candle is evaluated by
   :func:`acumen.signals.evaluate_day` over the day SO FAR, and the alerts are the state changes:
   armed, triggered (with entry / stop / target / qty), exited, squared off.

CONTEXT 4.4's sweep discipline is honoured literally: short retries, then **SKIP the symbol and
re-poll at sweep end**, and a **hard deadline before the next boundary**. A symbol that misses
its window is reported as ``skipped`` and never allowed to stall the queue -- one slow ticker
must not cost the other 209 their 11:30 evaluation.

## Which battery a morning runs (CONTEXT 4.7)

CONTEXT 3.3's POC is computed only when the day's governing battery has PASSED. On a SETTLED day
that battery is CONTEXT 4.6's -- gate 1 (volume reconciliation), gate 2 (integrity) and gate 1P
(price containment) -- and gate 1 and gate 1P both measure the day against **that day's
bhavcopy**, which for TODAY does not exist until after the close.

That was **Q-28**, and it blocked this module's live mode until the architect ruled on
08-Aug-2026. The ruling, now **CONTEXT 4.7**: gates 1 and 1P exist to catch history being
rewritten, and today cannot be rewritten during today, so they are structurally INAPPLICABLE to
same-day data -- a live morning runs the **ORACLE-FREE battery per sweep** (gate 2 with the
Q-21(a) open test, the Q-17 candle-level drops, candle validity), every live alert carries
:data:`LIVE_DISCLOSURE`, and the NEXT pre-open runs the full battery over the recording against
the published bhavcopy and reports the verdict loudly
(:func:`acumen.live_refresh.verify_prior_recording`). The residual is measured, not asserted:
0.5229% of settled symbol-days over the ten-year ledger failed gate 1 alone
(``docs/evidence/chunk13_q28_residual.md``).

**Replay is unchanged.** A past day has its bhavcopy, so the battery is the backtester's own
verdict and the whole pipeline runs end to end -- which is exactly what this chunk's replay
invariant tests, and it tests the same code the live morning runs.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import time as _time
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterable, Mapping, Protocol, Sequence

from . import backtest as bt
from . import signals as sig
from . import simulate as sim
from .aggregate import Bar
from .bias_engine import DailyBias
from .calendar import TradingCalendar
from .instrument_master import InstrumentMaster
from .live_recording import (
    CALENDAR_PUBLISHED,
    FETCH_EMPTY,
    FETCH_ERROR,
    FETCH_OK,
    FETCH_SKIPPED,
    FetchOutcome,
    LiveRecording,
    RecordedAlert,
)
from .live_source import BarSource, merge_bars
from .minute_store import StoredBar
from .signal_engine import (
    POSTURE_LIVE,
    POSTURE_SETTLED,
    DayGates,
    SignalPipeline,
    StockDay,
    oracle_free_battery,
)

# --- the seven states the dashboard shows (DESIGN.md PART II names each one's colour) ---------

PHASE_WAITING: str = "waiting"
PHASE_ARMED: str = "armed"
PHASE_TRIGGERED: str = "triggered"
PHASE_IN_TRADE: str = "in-trade"
PHASE_EXITED: str = "exited"
PHASE_REFUSED: str = "refused"
PHASE_SKIPPED: str = "skipped"

PHASES: tuple[str, ...] = (
    PHASE_TRIGGERED, PHASE_IN_TRADE, PHASE_ARMED, PHASE_WAITING,
    PHASE_EXITED, PHASE_SKIPPED, PHASE_REFUSED,
)

# --- alert kinds ------------------------------------------------------------------------------

ALERT_ARMED: str = "armed"
ALERT_TRIGGER: str = "trigger"
ALERT_EXIT: str = "exit"
ALERT_SQUARE_OFF: str = "square-off"
ALERT_FAILURE: str = "failure"

ALERT_KINDS: frozenset[str] = frozenset(
    {ALERT_ARMED, ALERT_TRIGGER, ALERT_EXIT, ALERT_SQUARE_OFF, ALERT_FAILURE}
)

# --- the clock the sweeps run on (CONTEXT 3.1 / 3.4) ------------------------------------------

#: The POC pass. CONTEXT 3.3: the profile is built after 11:15 from the 09:15-11:14 window,
#: and CONTEXT 3.4-1's reference is the 11:00-11:15 candle's close, which is known at 11:15.
POC_BOUNDARY = "11:15"
#: The last boundary a sweep runs at: the 15:00-15:15 candle's close, where CONTEXT 3.4-5
#: squares off anything still open (R1-Q18).
LAST_BOUNDARY = "15:15"

#: The session's end (CONTEXT 3.1). Used only by :meth:`LiveScreener.close_day`, which polls
#: once more after the last minute so the RECORDING holds the whole day.
SESSION_END: time = time(15, 30)

#: CONTEXT 4.4: short retries, then skip. Two attempts at 0.5s and 1.0s is the ruling's own
#: shape ("0.5s/1s short retries ... never block the queue 31s").
RETRY_BACKOFF_SECONDS: tuple[float, ...] = (0.5, 1.0)


class ScreenerError(RuntimeError):
    """The screener cannot start, or cannot safely continue."""


class BlockedByOpenQuestion(ScreenerError):
    """A class-A spec hole stands between this session and a correct answer. See QUESTIONS.md.

    Nothing raises this today -- Q-28, the hole it was written for, was ruled on 08-Aug-2026 and
    is CONTEXT 4.7. It is KEPT, and kept exported, because the next class-A hole a live session
    walks into needs the same exit: refuse to start, in the question's own words, rather than
    start and produce a number nobody may rely on.
    """


#: CONTEXT 4.7, the architect's own words, carried on **every live alert** and on the dashboard
#: header of any live session -- dry-run included, because a dry-run morning reads the same
#: unverified feed. It is not a caveat about the software; it is a fact about the data: no
#: exchange record exists for today until the evening's bhavcopy is published.
LIVE_DISCLOSURE: str = "live feed, not yet verified against the exchange's end-of-day record"

#: What a live session prints before it starts, so the operator sees the posture he is running
#: under rather than inferring it from a mode flag. CONTEXT 4.7 in the section's own terms.
LIVE_STARTUP_DISCLOSURE: str = (
    "CONTEXT 4.7 -- LIVE MODE. A live trading day has no bhavcopy oracle until evening, so this "
    "session runs the ORACLE-FREE battery per sweep: gate 2 (with the Q-21(a) open test), the "
    "Q-17 candle-level drops, and candle validity. Gates 1 and 1P are structurally INAPPLICABLE "
    "to same-day data -- what they detect is history being rewritten, and today cannot be "
    "rewritten during today. Every alert this session produces carries: '" + LIVE_DISCLOSURE +
    "'. The NEXT pre-open runs the FULL battery over this day's recording against the published "
    "bhavcopy and reports both verdicts, naming loudly any day it alerted on that the oracle "
    "then refuses. Measured residual: 0.5229% of settled symbol-days (2,187/418,275 over the "
    "ten-year ledger) failed gate 1 alone -- the frequency this morning accepts and discloses. "
    "The instrument master is THIS DAY'S OWN dump (QUESTIONS.md Q-29), named and hashed into the "
    "recording. THIS TOOL PLACES NO ORDERS."
)


def boundary_stamps(day: date) -> tuple[datetime, ...]:
    """Every 15-minute boundary the screener sweeps at, 11:15 through 15:15 inclusive.

    CONTEXT 4.4 sweeps *"at each 15-min boundary (11:15...15:00)"* and CONTEXT 3.4-5 squares off
    at 15:15, so the last sweep is the one that can see the 15:00-15:15 candle. The 11:15 sweep
    is the special one: it builds the day's POC (CONTEXT 3.3) and reads the reference.
    """
    first = datetime.combine(day, sig.bar_close_stamp(day, sig.REFERENCE_BAR).time())
    last = sig.bar_close_stamp(day, sig.SQUARE_OFF_BAR)
    stamps = []
    stamp = first
    while stamp <= last:
        stamps.append(stamp)
        stamp += timedelta(minutes=sig.CANDLE_MINUTES)
    return tuple(stamps)


#: How long a live loop sleeps between checks while it waits for the next boundary. Short enough
#: that the sweep starts within a second of the candle closing (CONTEXT 4.4 measures the
#: just-closed candle as arriving ~0.2s after the boundary), long enough not to spin.
BOUNDARY_POLL_SECONDS: float = 1.0


class Clock(Protocol):
    """Wall time, injectable -- so a replay is deterministic and a test is fast."""

    def now(self) -> datetime:
        ...

    def sleep(self, seconds: float) -> None:
        ...


@dataclass
class SystemClock:
    """The real clock. CONTEXT 7-E8: naive IST, which is the operator's own local time."""

    def now(self) -> datetime:
        return datetime.now().replace(microsecond=0)

    def sleep(self, seconds: float) -> None:  # pragma: no cover -- real waiting
        _time.sleep(seconds)


@dataclass
class VirtualClock:
    """A clock the caller drives. Every ``sleep`` advances it; nothing ever waits.

    This is what makes the replay invariant a test rather than a four-hour observation, and it
    is why no engine in this repo is allowed to read a clock of its own (CLAUDE.md code
    standards): a screener that asked the operating system for the time could not be replayed.
    """

    stamp: datetime
    elapsed_seconds: float = 0.0

    def now(self) -> datetime:
        return self.stamp

    def sleep(self, seconds: float) -> None:
        self.elapsed_seconds += seconds
        self.stamp += timedelta(seconds=seconds)

    def set(self, stamp: datetime) -> None:
        self.stamp = stamp


# --- alert delivery ---------------------------------------------------------------------------


class AlertSink(Protocol):
    """Somewhere an alert goes. Chunk 14 adds Telegram by adding a sink, not by editing this."""

    def deliver(self, alert: RecordedAlert) -> None:
        ...


@dataclass
class ScreenAlertSink:
    """The screen. One line per alert, the four numbers he trades on first."""

    out: Callable[[str], None] = print

    def deliver(self, alert: RecordedAlert) -> None:
        self.out(format_alert(alert))


@dataclass
class SoundAlertSink:
    """A sound. The terminal bell by default -- present on every console, needs no package.

    Silent for :data:`ALERT_ARMED`: arming is information, and a bell that goes off thirty times
    a morning is a bell the trader learns to ignore, which would cost him the one that matters.
    """

    out: Callable[[str], None] = print
    loud_kinds: frozenset[str] = frozenset({ALERT_TRIGGER, ALERT_EXIT, ALERT_SQUARE_OFF,
                                            ALERT_FAILURE})
    rings: list[str] = field(default_factory=list)

    def deliver(self, alert: RecordedAlert) -> None:
        if alert.kind not in self.loud_kinds:
            return
        self.rings.append(alert.kind)
        self.out("\a")


@dataclass
class CollectingAlertSink:
    """Keeps every alert. The dashboard's alert log, and what the tests assert against."""

    alerts: list[RecordedAlert] = field(default_factory=list)

    def deliver(self, alert: RecordedAlert) -> None:
        self.alerts.append(alert)


def format_alert(alert: RecordedAlert) -> str:
    """One line, the trader's four numbers first (CONTEXT 4.4's payload list).

    A live alert carries CONTEXT 4.7's disclosure on the same line, after the numbers rather
    than before them: the sentence must not be what he reads first at 11:30, and it must not be
    absent from what he forwards at 11:31.
    """
    line = _format_alert_body(alert)
    disclosure = alert.payload.get("disclosure")
    return f"{line}   [{disclosure}]" if disclosure else line


def _format_alert_body(alert: RecordedAlert) -> str:
    at = alert.at.strftime("%H:%M")
    payload = alert.payload
    if alert.kind == ALERT_TRIGGER:
        return (
            f"[{at}] {alert.symbol} {str(payload.get('side', '')).upper()}  "
            f"entry {_rs(payload.get('entry_paise'))}  "
            f"SL {_rs(payload.get('stop_paise'))}  "
            f"TP {_rs(payload.get('target_paise'))}  "
            f"qty {payload.get('qty')}   "
            f"(POC {_rs(payload.get('poc_paise'))}, bias {payload.get('bias')})"
        )
    if alert.kind == ALERT_ARMED:
        return (
            f"[{at}] {alert.symbol} ARMED  {str(payload.get('side', '')).upper()}  "
            f"POC {_rs(payload.get('poc_paise'))}  "
            f"reference {_rs(payload.get('reference_paise'))}"
        )
    if alert.kind == ALERT_EXIT:
        return (
            f"[{at}] {alert.symbol} EXIT {payload.get('exit_kind')}  "
            f"at {_rs(payload.get('exit_paise'))}"
        )
    if alert.kind == ALERT_SQUARE_OFF:
        return f"[{at}] {alert.symbol} SQUARE-OFF at {_rs(payload.get('exit_paise'))}"
    return f"[{at}] !! {payload.get('detail', 'the screener is not answering')}"


def _rs(paise) -> str:
    if paise is None:
        return "-"
    value = Fraction(paise) / 100
    return f"{float(value):,.2f}"


# --- per-symbol state -------------------------------------------------------------------------


@dataclass(frozen=True)
class SymbolState:
    """One stock's state right now: everything the dashboard shows, and nothing it does not."""

    symbol: str
    phase: str
    detail: str = ""
    bias: str | None = None
    bias_rule: str = ""
    side: str | None = None
    poc_paise: Fraction | None = None
    reference_paise: int | None = None
    entry_paise: int | None = None
    stop_paise: int | None = None
    target_paise: int | None = None
    qty: int | None = None
    exit_kind: str | None = None
    exit_paise: int | None = None
    minute_count: int = 0
    last_stamp: datetime | None = None
    refusal: str | None = None

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "phase": self.phase,
            "detail": self.detail,
            "bias": self.bias,
            "bias_rule": self.bias_rule,
            "side": self.side,
            "poc_paise": None if self.poc_paise is None else str(self.poc_paise),
            "reference_paise": self.reference_paise,
            "entry_paise": self.entry_paise,
            "stop_paise": self.stop_paise,
            "target_paise": self.target_paise,
            "qty": self.qty,
            "exit_kind": self.exit_kind,
            "exit_paise": self.exit_paise,
            "minute_count": self.minute_count,
            "last_stamp": None if self.last_stamp is None else self.last_stamp.isoformat(),
            "refusal": self.refusal,
        }


@dataclass(frozen=True)
class SweepReport:
    """What one boundary sweep did -- and, more usefully, what it failed to do.

    ``skipped`` is CONTEXT 4.4's own outcome and it is a first-class result, not an error: the
    sweep completed, these symbols did not, and both facts reach the operator. ``complete`` is
    False whenever anything was left unfetched at the deadline, which is what raises the
    failure banner.
    """

    boundary: datetime
    started: datetime
    finished: datetime
    fetched: tuple[str, ...]
    skipped: tuple[str, ...]
    failed: tuple[str, ...]
    evaluated: int
    alerts: tuple[RecordedAlert, ...]
    deadline: datetime
    deadline_hit: bool

    @property
    def complete(self) -> bool:
        return not self.skipped and not self.failed

    @property
    def elapsed_seconds(self) -> float:
        return (self.finished - self.started).total_seconds()


# --- the screener -----------------------------------------------------------------------------


@dataclass
class LiveScreener:
    """The morning pipeline, one trading day, one universe.

    Attributes:
        day: the trade date.
        symbols: the universe, in sweep order.
        pipeline: the chunk-7 orchestration -- the SAME object the backtester wires.
        biases: today's bias per symbol, computed pre-open from the stored daily candles.
        gates: the CONTEXT 4.6 battery per symbol for this day, under :data:`POSTURE_SETTLED`.
            A whole-day measurement, so it is computed ONCE and reused at every boundary. EMPTY
            under :data:`POSTURE_LIVE`: CONTEXT 4.7's oracle-free battery is a property of the
            bars in hand and is therefore recomputed per sweep, from the same shared function.
        posture: which battery governs (CONTEXT 4.7). ``settled`` for a replay of a past day,
            ``live`` for today.
        disclosure: the sentence every alert of this session carries. Empty for a replay, whose
            day HAS been verified against the exchange's record.
        source: where the 1-minute bars come from (:mod:`acumen.live_source`).
        recording: the replay contract (:mod:`acumen.live_recording`).
        clock: injectable wall time.
        sinks: where alerts go. Screen and sound at minimum; chunk 14 adds Telegram here.
        risk_per_trade_paise / cost_paise: CONTEXT 3.5, from ``config.yaml`` through the loader.
        deadline_seconds: CONTEXT 4.4's hard sweep deadline. Defaults to one whole 15-minute
            bar minus a minute, so a sweep can never run into the boundary it would report at.
        dry_run: log-only. Alerts are computed, recorded and shown, and the ``dry-run`` marker
            travels on every one of them so a dry-mode alert can never be mistaken for a live
            one in the recording.
    """

    day: date
    symbols: tuple[str, ...]
    pipeline: SignalPipeline
    biases: Mapping[str, DailyBias]
    gates: Mapping[str, DayGates]
    source: BarSource
    recording: LiveRecording
    clock: Clock
    sinks: tuple[AlertSink, ...] = ()
    risk_per_trade_paise: int = 0
    cost_paise: int = 0
    deadline_seconds: int = (sig.CANDLE_MINUTES - 1) * 60
    dry_run: bool = True
    posture: str = POSTURE_SETTLED
    disclosure: str = ""

    # --- mutable session state (persisted to state.json after every sweep) ---
    bars: dict[str, tuple[StoredBar, ...]] = field(default_factory=dict)
    states: dict[str, SymbolState] = field(default_factory=dict)
    alerted: set[tuple[str, str]] = field(default_factory=set)
    banner: str = ""
    sweeps_done: list[str] = field(default_factory=list)

    # --- lifecycle ----------------------------------------------------------------

    def __post_init__(self) -> None:
        for symbol in self.symbols:
            self.states.setdefault(symbol, self._initial_state(symbol))

    def _initial_state(self, symbol: str) -> SymbolState:
        bias = self.biases.get(symbol)
        if bias is None:
            return SymbolState(
                symbol=symbol, phase=PHASE_REFUSED,
                detail="no bias computed for today", refusal="no bias",
            )
        if bias.suppressed or bias.bias is None:
            return SymbolState(
                symbol=symbol, phase=PHASE_REFUSED,
                bias=bias.bias, bias_rule=bias.rule,
                detail=bias.detail, refusal=bias.rule,
            )
        return SymbolState(
            symbol=symbol, phase=PHASE_WAITING, bias=bias.bias, bias_rule=bias.rule,
            side=sig.side_for_bias(bias.bias),
            detail="waiting for the 11:15 profile",
        )

    def run_day(self, *, on_sweep: Callable[[SweepReport], None] | None = None
                ) -> tuple[SweepReport, ...]:
        """Sweep every boundary of the day, in order, then CLOSE the day. One report per sweep."""
        reports = []
        for boundary in boundary_stamps(self.day):
            report = self.sweep(boundary)
            reports.append(report)
            if on_sweep is not None:
                on_sweep(report)
        report = self.close_day()
        reports.append(report)
        if on_sweep is not None:
            on_sweep(report)
        return tuple(reports)

    def close_day(self) -> SweepReport:
        """One last poll after 15:29, so the RECORDING holds the whole session.

        Not a decision boundary -- CONTEXT 3.4's last entry closes at 15:00 and its square-off at
        15:15, and no bar after 15:14 can change either (chunk 8 proved the 15:15-stamped candle
        is never read). This exists for the REPLAY CONTRACT, and it is load-bearing there: gate 1
        reconciles the day's WHOLE folded volume against the bhavcopy, so a recording that
        stopped at 15:14 could never be pushed back through the backtest path at all. The last
        fifteen minutes of the session are evidence even though they are not information.

        The states are recomputed from the completed day and must not move; if one ever does,
        something after 15:14 reached a decision and that is a defect, not a late correction.
        """
        stamp = datetime.combine(self.day, SESSION_END)
        before = dict(self.states)
        report = self.sweep(stamp)
        moved = [
            symbol for symbol, state in self.states.items()
            if symbol in before and before[symbol].phase != state.phase
            and before[symbol].phase != PHASE_SKIPPED
        ]
        if moved:
            self.recording.record_event(
                "post-session-state-change", at=stamp, detail=", ".join(sorted(moved)),
                symbols=sorted(moved),
            )
        return report

    # --- one boundary -------------------------------------------------------------

    def sweep(self, boundary: datetime) -> SweepReport:
        """Poll the universe, evaluate every symbol that answered, alert on the changes.

        The order is CONTEXT 4.4's: poll with short retries, SKIP a symbol that will not answer
        and re-poll it at the end of the sweep, and stop at the hard deadline whatever is left.
        A skipped symbol keeps its previous state and is reported; it is never evaluated on a
        stale day, and it never blocks the queue.
        """
        label = boundary.strftime("%H:%M")
        started = self.clock.now()
        deadline = boundary + timedelta(seconds=self.deadline_seconds)
        self.recording.record_event(
            "sweep-opened", at=started, sweep=label,
            detail=f"{len(self.symbols)} symbols, deadline {deadline.isoformat()}",
        )

        fetched: list[str] = []
        deferred: list[str] = []
        failed: list[str] = []
        deadline_hit = False

        for symbol in self.symbols:
            if self.clock.now() > deadline:
                deadline_hit = True
                deferred.extend(self.symbols[len(fetched) + len(deferred) + len(failed):])
                break
            ok = self._poll(symbol, boundary, label)
            if ok:
                fetched.append(symbol)
            else:
                deferred.append(symbol)

        # CONTEXT 4.4's second pass -- "on failure SKIP the symbol and re-poll at sweep end".
        still: list[str] = []
        for symbol in deferred:
            if self.clock.now() > deadline:
                deadline_hit = True
                still.append(symbol)
                continue
            if self._poll(symbol, boundary, label, attempt=2):
                fetched.append(symbol)
            else:
                still.append(symbol)
        failed = [s for s in still if s in self.bars]
        skipped = [s for s in still if s not in self.bars]

        alerts: list[RecordedAlert] = []
        evaluated = 0
        for symbol in fetched:
            evaluated += 1
            alerts.extend(self._evaluate(symbol, boundary))
        for symbol in still:
            self._mark_skipped(symbol, boundary)
            self.recording.record_fetch(FetchOutcome(
                symbol=symbol, sweep=label, outcome=FETCH_SKIPPED, bars=0,
                at=self.clock.now(),
                detail="missed its data window; kept its previous state (CONTEXT 4.4)",
            ))

        finished = self.clock.now()
        report = SweepReport(
            boundary=boundary, started=started, finished=finished,
            fetched=tuple(fetched), skipped=tuple(skipped), failed=tuple(failed),
            evaluated=evaluated, alerts=tuple(alerts),
            deadline=deadline, deadline_hit=deadline_hit,
        )
        self._settle_banner(report)
        self.sweeps_done.append(label)
        self.recording.record_event(
            "sweep-closed", at=finished, sweep=label,
            fetched=len(fetched), skipped=len(skipped), failed=len(failed),
            evaluated=evaluated, alerts=len(alerts), deadline_hit=deadline_hit,
            detail="complete" if report.complete else "INCOMPLETE",
        )
        self.persist()
        return report

    def _poll(self, symbol: str, boundary: datetime, label: str, *, attempt: int = 1) -> bool:
        """Fetch one symbol with CONTEXT 4.4's short retries. True when the day is in hand."""
        backoff = RETRY_BACKOFF_SECONDS if attempt == 1 else RETRY_BACKOFF_SECONDS[:1]
        last_error = ""
        for tries in range(len(backoff) + 1):
            at = self.clock.now()
            began = at
            try:
                bars = self.source.fetch(symbol, self.day, boundary)
            except Exception as exc:  # a feed failure is normal (CONTEXT 4.3); a crash is not
                last_error = f"{type(exc).__name__}: {exc}"
                self.recording.record_fetch(FetchOutcome(
                    symbol=symbol, sweep=label, outcome=FETCH_ERROR, bars=0,
                    at=at, attempt=attempt, detail=last_error,
                ))
                if tries < len(backoff):
                    self.clock.sleep(backoff[tries])
                    continue
                return False
            # Divided by a unit rather than scaled by a magic 1000 -- which also keeps this
            # module clear of the chunk-8 money tripwire, whose whole value is that it is a
            # LITERAL scan and therefore cannot be reasoned with (REVIEW_9A_2 finding C4).
            elapsed = int((self.clock.now() - began) / timedelta(milliseconds=1))
            merged = merge_bars(self.bars.get(symbol, ()), bars)
            self.bars[symbol] = merged
            self.recording.record_bars(symbol, bars, sweep=label, at=at)
            self.recording.record_fetch(FetchOutcome(
                symbol=symbol, sweep=label,
                outcome=FETCH_OK if bars else FETCH_EMPTY,
                bars=len(bars), at=at, attempt=attempt, elapsed_ms=elapsed,
            ))
            return True
        return False

    # --- evaluation: THE ONE ENGINE -----------------------------------------------

    def _evaluate(self, symbol: str, boundary: datetime) -> list[RecordedAlert]:
        """Run CONTEXT 3.3 + 3.4 over the day so far, through the BACKTESTER'S own pipeline.

        Nothing about the strategy is decided in this method. It calls
        :meth:`acumen.signal_engine.SignalPipeline.evaluate` -- the same call
        :meth:`~acumen.signal_engine.SignalPipeline.stock_day` makes, with the same battery, the
        same POC engine, the same aggregation and the same
        :func:`acumen.signals.evaluate_day` -- and then reads a PHASE off the result. The
        reading is the only live-specific thing here, and it exists because a square-off marked
        on the last bar of a prefix is the engine's honest answer for a day that has ended, not
        an exit that has happened (CONTEXT 3.4-5 squares off at 15:15 and at no other time).
        """
        state = self.states[symbol]
        if state.phase == PHASE_REFUSED and state.refusal and not state.refusal.startswith("gate"):
            return []  # a suppressed or unseeded day never becomes tradeable during the day
        bias = self.biases.get(symbol)
        if bias is None:
            return []
        minutes = self.bars.get(symbol, ())
        if not minutes:
            self.states[symbol] = replace(
                state, phase=PHASE_WAITING, detail="no 1-minute candles yet",
                minute_count=0,
            )
            return []

        stock_day = self.pipeline.evaluate(
            symbol, self.day, bias=bias, minutes=minutes, gates=self._battery(symbol, minutes)
        )
        before = self.states[symbol]
        after = self._state_from(stock_day, boundary, previous=before)
        self.states[symbol] = after
        return self._alerts_for(before, after, stock_day, boundary)

    def _battery(self, symbol: str, minutes: Sequence[StoredBar]) -> DayGates | None:
        """Which battery governs this symbol-day, and for a live morning, over these bars.

        CONTEXT 4.7 is the whole of this method. A REPLAY takes the settled battery computed once
        from the whole stored day (gate 1 folds a whole session's volume against a whole day's
        bhavcopy, so recomputing it on a growing prefix would be wrong at every boundary but the
        last). A LIVE morning has no bhavcopy to fold against, so it runs the ORACLE-FREE battery
        PER SWEEP over the bars actually in hand -- which is legitimate precisely because every
        trigger left in that battery is a property of the bars themselves.

        Neither branch computes anything here: both call functions the backtester's own path
        calls, which is what keeps CONTEXT section 6 a property of the code.
        """
        if self.posture == POSTURE_LIVE:
            return oracle_free_battery(self.day, minutes)
        return self.gates.get(symbol)

    def _state_from(
        self, stock_day: StockDay, boundary: datetime, *, previous: SymbolState
    ) -> SymbolState:
        """A :class:`StockDay` read as one of the seven dashboard states."""
        symbol = stock_day.symbol
        bias = stock_day.bias
        minutes = stock_day.minute_count
        last_stamp = self.bars.get(symbol, ())[-1].stamp if self.bars.get(symbol) else None
        base = dict(
            symbol=symbol,
            bias=None if bias is None else bias.bias,
            bias_rule="" if bias is None else bias.rule,
            side=stock_day.side,
            minute_count=minutes,
            last_stamp=last_stamp,
        )
        if not stock_day.evaluated:
            # Before 11:15 the profile does not exist yet, and CONTEXT 3.3 says so rather than
            # refusing the day: an empty-window or gate-unrun POC before the boundary is the
            # normal morning, not a verdict.
            if boundary < sig.bar_close_stamp(self.day, sig.REFERENCE_BAR):
                return SymbolState(phase=PHASE_WAITING, detail="collecting", **base)
            return SymbolState(
                phase=PHASE_REFUSED, detail=stock_day.reason,
                refusal=stock_day.reason, **base,
            )

        signal = stock_day.signal
        assert signal is not None  # evaluated days always carry one
        poc = stock_day.profile.poc_paise if stock_day.profile is not None else None
        common = dict(base, poc_paise=poc, reference_paise=signal.reference_paise)

        if signal.entry is None:
            phase = PHASE_ARMED if signal.final_state == sig.STATE_ARMED else PHASE_WAITING
            return SymbolState(phase=phase, detail=_state_words(signal), **common)

        entry = signal.entry
        qty = (
            sim.position_size(self.risk_per_trade_paise, entry.risk_paise)
            if self.risk_per_trade_paise else None
        )
        exit_event = signal.exit_event
        exit_kind, exit_paise, phase = None, None, PHASE_IN_TRADE
        if exit_event is not None and exit_event.kind != sig.EXIT_SQUARE_OFF:
            exit_kind = exit_event.kind
            exit_paise = entry.stop_paise if exit_event.kind == sig.EXIT_STOP else entry.target_paise
            phase = PHASE_EXITED
        elif exit_event is not None and self._square_off_bar_closed(boundary):
            exit_kind = exit_event.kind
            exit_paise = self._bar_close(symbol, exit_event.stamp)
            phase = PHASE_EXITED
        elif entry.close_stamp == boundary:
            phase = PHASE_TRIGGERED
        elif previous.phase == PHASE_TRIGGERED and exit_kind is None:
            phase = PHASE_IN_TRADE

        detail = entry.detail if phase in (PHASE_TRIGGERED, PHASE_IN_TRADE) else (
            "" if exit_event is None else exit_event.detail
        )
        return SymbolState(
            phase=phase, detail=detail,
            entry_paise=entry.entry_paise, stop_paise=entry.stop_paise,
            target_paise=entry.target_paise, qty=qty,
            exit_kind=exit_kind, exit_paise=exit_paise, **common,
        )

    def _square_off_bar_closed(self, boundary: datetime) -> bool:
        """Has the 15:00-15:15 candle actually closed? CONTEXT 3.4-5's square-off moment.

        Until it has, an engine answer of ``square-off`` is the engine describing the prefix it
        was handed -- *"nothing after the entry candle yet"* -- not an exit. Reading it as one
        would close the trader's position four hours early, on the screen if not in the market.
        """
        return boundary >= sig.bar_close_stamp(self.day, sig.SQUARE_OFF_BAR)

    def _bar_close(self, symbol: str, stamp: datetime) -> int | None:
        for bar in self._fifteen(symbol):
            if bar.stamp == stamp:
                return int(bar.close_paise)
        return None

    def _fifteen(self, symbol: str) -> tuple[Bar, ...]:
        from .aggregate import aggregate_15min, in_session_bars

        session, _dropped = in_session_bars(self.bars.get(symbol, ()))
        return aggregate_15min(session) if session else ()

    # --- alerts -------------------------------------------------------------------

    def _alerts_for(
        self, before: SymbolState, after: SymbolState, stock_day: StockDay, boundary: datetime
    ) -> list[RecordedAlert]:
        out: list[RecordedAlert] = []
        symbol = after.symbol
        if after.phase == PHASE_ARMED and before.phase != PHASE_ARMED:
            out.append(self._alert(ALERT_ARMED, symbol, boundary, {
                "side": after.side, "poc_paise": _num(after.poc_paise),
                "reference_paise": after.reference_paise, "bias": after.bias,
            }))
        if after.phase == PHASE_TRIGGERED and before.phase != PHASE_TRIGGERED:
            out.append(self._alert(ALERT_TRIGGER, symbol, boundary, {
                # CONTEXT 4.4's payload, verbatim, plus the quantity CONTEXT 3.5 sizes.
                "side": after.side,
                "entry_paise": after.entry_paise,
                "stop_paise": after.stop_paise,
                "target_paise": after.target_paise,
                "poc_paise": _num(after.poc_paise),
                "bias": after.bias,
                "qty": after.qty,
                "risk_paise": (
                    None if after.entry_paise is None or after.stop_paise is None
                    else abs(after.entry_paise - after.stop_paise)
                ),
                "gap_entry": stock_day.signal.entry.gap_entry if stock_day.signal
                and stock_day.signal.entry else None,
            }))
        if after.phase == PHASE_EXITED and before.phase != PHASE_EXITED:
            kind = ALERT_SQUARE_OFF if after.exit_kind == sig.EXIT_SQUARE_OFF else ALERT_EXIT
            out.append(self._alert(kind, symbol, boundary, {
                "exit_kind": after.exit_kind, "exit_paise": after.exit_paise,
                "entry_paise": after.entry_paise, "side": after.side, "qty": after.qty,
            }))
        return [alert for alert in out if self._deliver(alert)]

    def _alert(self, kind: str, symbol: str, at: datetime, payload: dict) -> RecordedAlert:
        body = dict(payload)
        body["dry_run"] = self.dry_run
        if self.disclosure:
            # CONTEXT 4.7: "Every live alert carries: 'live feed, not yet verified against the
            # exchange's end-of-day record.'" On the alert itself, not only on the screen it was
            # read from -- an alert is forwarded, screenshotted and quoted, and the sentence has
            # to travel with it.
            body["disclosure"] = self.disclosure
        return RecordedAlert(kind=kind, symbol=symbol, at=at, payload=body)

    def _deliver(self, alert: RecordedAlert) -> bool:
        """Record and deliver once. Returns False for a duplicate, which is never re-sent."""
        key = (alert.symbol, alert.kind)
        if key in self.alerted:
            return False
        self.alerted.add(key)
        self.recording.record_alert(alert)
        for sink in self.sinks:
            sink.deliver(alert)
        return True

    def _mark_skipped(self, symbol: str, boundary: datetime) -> None:
        state = self.states[symbol]
        if state.phase in (PHASE_REFUSED, PHASE_EXITED):
            return
        self.states[symbol] = replace(
            state, phase=PHASE_SKIPPED,
            detail=f"missed the {boundary.strftime('%H:%M')} window; will be re-polled",
        )

    def _settle_banner(self, report: SweepReport) -> None:
        """The failure banner: raised when a sweep did not complete, cleared when one does.

        This is the safety rail in its visible form. The screener degrades to SILENCE plus a
        banner and never to a wrong alert: the symbols it could not read produce nothing at all,
        and the operator can see that they produced nothing rather than inferring calm.
        """
        if report.complete:
            if self.banner:
                self.recording.record_event(
                    "banner-cleared", at=report.finished, sweep=report.boundary.isoformat(),
                    detail=self.banner,
                )
            self.banner = ""
            return
        parts = []
        if report.skipped:
            parts.append(f"{len(report.skipped)} symbol(s) never answered")
        if report.failed:
            parts.append(f"{len(report.failed)} symbol(s) are stale")
        if report.deadline_hit:
            parts.append("the sweep hit its hard deadline")
        self.banner = (
            f"{report.boundary.strftime('%H:%M')} sweep INCOMPLETE -- " + "; ".join(parts)
            + ". Those stocks are NOT being watched."
        )
        self.recording.record_event(
            "banner-raised", at=report.finished, sweep=report.boundary.isoformat(),
            detail=self.banner,
        )
        self._deliver(self._alert(
            ALERT_FAILURE, "-", report.finished,
            {"detail": self.banner, "sweep": report.boundary.isoformat()},
        ))

    # --- crash-safe resume ---------------------------------------------------------

    def persist(self) -> None:
        """Write the intraday state. Called after every sweep, so a crash costs one boundary."""
        self.recording.write_state({
            "trade_date": self.day.isoformat(),
            "sweeps_done": list(self.sweeps_done),
            "banner": self.banner,
            "dry_run": self.dry_run,
            "alerted": sorted(f"{symbol}|{kind}" for symbol, kind in self.alerted),
            "states": {symbol: state.as_dict() for symbol, state in sorted(self.states.items())},
        })

    def restore(self) -> bool:
        """Reload the intraday state from the recording. True when there was one to reload.

        The BARS are not restored from ``state.json`` -- they are re-read from the recording's
        own candle files, which is the whole reason those files are append-only. A resumed
        screener therefore continues from the same bytes it had, not from a summary of them.
        """
        state = self.recording.read_state()
        if not state:
            return False
        if state.get("trade_date") != self.day.isoformat():
            raise ScreenerError(
                f"the recording at {self.recording.root} holds "
                f"{state.get('trade_date')!r}, not {self.day.isoformat()}"
            )
        self.sweeps_done = list(state.get("sweeps_done", ()))
        self.banner = str(state.get("banner", ""))
        self.alerted = {
            (part.split("|", 1)[0], part.split("|", 1)[1])
            for part in state.get("alerted", ()) if "|" in part
        }
        for symbol in self.symbols:
            self.bars[symbol] = self.recording.bars(symbol, self.day)
        self.recording.record_event(
            "resumed", at=self.clock.now(),
            detail=f"{len(self.sweeps_done)} sweep(s) already done; "
                   f"{sum(1 for s in self.bars.values() if s)} symbol(s) restored from candles",
        )
        return True

    # --- what the dashboard reads --------------------------------------------------

    def by_phase(self) -> dict[str, tuple[SymbolState, ...]]:
        """Every symbol grouped by state, in the dashboard's own reading order."""
        grouped: dict[str, list[SymbolState]] = {phase: [] for phase in PHASES}
        for state in self.states.values():
            grouped.setdefault(state.phase, []).append(state)
        return {
            phase: tuple(sorted(rows, key=lambda row: row.symbol))
            for phase, rows in grouped.items()
        }


def wait_for_boundary(
    clock: Clock, stamp: datetime, *, poll_seconds: float = BOUNDARY_POLL_SECONDS
) -> float:
    """Sleep until ``clock`` reaches ``stamp``. Returns the seconds waited.

    A REPLAY drives a :class:`VirtualClock` and never waits at all; a live morning drives a
    :class:`SystemClock` and must not sweep a boundary before the candle has closed -- the bar
    stamped 11:15 covers ``[11:15, 11:30)`` (CONTEXT 7-E12), so polling for it at 11:29 is
    polling for a candle that does not exist yet. Written as a loop over the injected clock
    rather than as one long sleep so that the wait is itself replayable, which is the same
    discipline every other clock read in this module follows.
    """
    waited = 0.0
    while clock.now() < stamp:
        remaining = (stamp - clock.now()).total_seconds()
        nap = min(poll_seconds, remaining) if remaining > 0 else 0.0
        if nap <= 0:
            break
        clock.sleep(nap)
        waited += nap
    return waited


def _state_words(signal: sig.SignalDay) -> str:
    if signal.final_state == sig.STATE_ARMED:
        return "armed -- waiting for a close across the POC"
    if signal.final_state in (sig.STATE_WAIT_BELOW, sig.STATE_WAIT_ABOVE):
        return f"{signal.final_state}: needs a close on the other side of the POC first"
    if signal.final_state == sig.STATE_SIDE_UNSET:
        return "reference is exactly ON the POC: the first distinct close sets the side"
    return signal.outcome


def _num(value):
    if value is None:
        return None
    return str(value)


# --- construction ------------------------------------------------------------------------------


def full_day_gates(
    pipeline: SignalPipeline, symbols: Iterable[str], day: date
) -> dict[str, DayGates]:
    """The CONTEXT 4.6 battery for ``day``, per symbol, from the STORED whole day.

    This is the backtester's own verdict, computed exactly where the backtester computes it --
    :meth:`acumen.signal_engine.SignalPipeline.gate_day` over the day's whole stored minute day.
    It is a WHOLE-DAY measurement (gate 1 folds the session's total volume against the
    bhavcopy), which is why it is computed once and handed to every boundary rather than
    recomputed on a growing prefix, where it would be wrong at every boundary but the last.

    It is available for a PAST day and not for TODAY. That asymmetry was QUESTIONS.md **Q-28**
    and CONTEXT 4.7 is the ruling on it: a live morning runs
    :func:`acumen.signal_engine.oracle_free_battery` per sweep instead, and this function is not
    called at all for ``mode="live"``.
    """
    out: dict[str, DayGates] = {}
    for symbol in symbols:
        minutes = pipeline.minute_store.minutes(symbol, day)
        if minutes:
            out[symbol] = pipeline.gate_day(symbol, day, minutes)
    return out


def build_live_screener(
    day: date,
    symbols: Sequence[str],
    *,
    source: BarSource,
    recording: LiveRecording,
    clock: Clock,
    mode: str,
    data_dir: Path | None = None,
    cache_dir: Path | None = None,
    seed_from: date | None = None,
    sinks: Sequence[AlertSink] = (),
    dry_run: bool = True,
    allow_network: bool = False,
    calendar: TradingCalendar | None = None,
    calendar_source: str = CALENDAR_PUBLISHED,
    master_file: str | None = None,
) -> LiveScreener:
    """Wire the screener over the local stores. ``mode`` is ``"replay"`` or ``"live"``.

    Everything is taken from the same places the backtester takes it (``config.yaml`` through the
    loader, the local stores) and from nowhere else. The ONE thing that is chosen here rather
    than inherited is the instrument master, and CONTEXT 4.7 is why:

    * ``mode="live"`` takes **THE DAY'S OWN master** (QUESTIONS.md Q-29, architect 08-Aug-2026):
      the replication target is the trader's chart AS OF THAT MORNING, and his chart's tick that
      morning is that morning's dump. It must already be in the cache -- the pre-open refresh
      fetches it (:func:`acumen.live_refresh.refresh_instrument_master`) -- and the morning
      REFUSES to start without it rather than silently falling back to a stale snapshot, because
      the tick sizes the profile row grid, hence the POC, hence every entry, stop and target.
    * ``mode="replay"`` takes **the recording's own pin** when the recording already names one,
      so section 6's no-drift guarantee holds PER DAY: a live day replays under the master it
      ran on, whatever the config pin has since become. With no recording to read, the Q-20 pin
      governs, exactly as it governs the historical ledger.

    ``master_file`` overrides that resolution explicitly (chunk 14's parity harness replaying a
    recording into a fresh directory is the caller that needs it).

    :func:`master_tick_divergence` reports pin-vs-day differences as information every morning;
    it decides nothing, which is the ruling's own instruction.
    """
    if mode not in ("replay", "live"):
        raise ScreenerError(f"mode must be 'replay' or 'live', got {mode!r}.")
    live = mode == "live"
    chosen_master = master_file or _master_for(mode, day=day, recording=recording)

    runner, master_path, _ca = bt.build_runner(
        symbols, day, day, data_dir=data_dir, cache_dir=cache_dir,
        seed_from=seed_from if seed_from is not None else day,
        label="live-screener", allow_network=allow_network,
        master_file=chosen_master,
    )
    wanted = tuple(symbol.strip().upper() for symbol in symbols)
    biases: dict[str, DailyBias] = {}
    for symbol in wanted:
        series, _reason = runner.bias_map(symbol)
        if day in series:
            biases[symbol] = series[day]

    # CONTEXT 4.7: a live morning has no stored day to gate and no oracle to gate it against, so
    # the settled battery is not computed at all and the oracle-free one runs per sweep.
    gates = {} if live else full_day_gates(runner.pipeline, wanted, day)
    recording.open_session(_manifest(
        runner=runner, day=day, symbols=wanted, master_path=master_path,
        mode=mode, dry_run=dry_run,
        calendar=calendar if calendar is not None else runner.calendar,
        calendar_source=calendar_source,
    ))
    recording.write_bias({
        symbol: {
            "bias": bias.bias, "rule": bias.rule, "detail": bias.detail,
            "tradeable": bias.tradeable, "suppressed": bias.suppressed,
            "current_date": None if bias.current_date is None else bias.current_date.isoformat(),
            "previous_date": None if bias.previous_date is None
            else bias.previous_date.isoformat(),
            "tie_case": bias.tie_case,
        }
        for symbol, bias in sorted(biases.items())
    })
    return LiveScreener(
        day=day, symbols=wanted, pipeline=runner.pipeline, biases=biases, gates=gates,
        source=source, recording=recording, clock=clock, sinks=tuple(sinks),
        risk_per_trade_paise=runner.spec.risk_per_trade_paise,
        cost_paise=runner.spec.cost_paise, dry_run=dry_run,
        posture=POSTURE_LIVE if live else POSTURE_SETTLED,
        disclosure=LIVE_DISCLOSURE if live else "",
    )


def day_master_filename(day: date) -> str:
    """The filename of ``day``'s OWN instrument-master dump (CONTEXT 4.7 / QUESTIONS.md Q-29).

    One place, because three modules need to agree on it: the pre-open refresh that fetches it,
    the screener that runs on it, and the verification that replays yesterday under the one
    yesterday recorded. It is the same name :func:`acumen.instrument_master.master_cache_path`
    writes, taken from that function rather than spelled again here.
    """
    from .instrument_master import master_cache_path

    return master_cache_path(".", day).name


def _master_for(mode: str, *, day: date, recording: LiveRecording) -> str | None:
    """Which instrument master governs this session (CONTEXT 4.7). ``None`` means the Q-20 pin.

    Live: the day's own dump, always, and its absence is a refusal rather than a fallback.
    Replay: the recording's own pin when the recording already names one -- which is what makes
    section 6's guarantee hold PER DAY -- and otherwise the config pin, which is the law for
    every historical day.
    """
    if mode == "live":
        return day_master_filename(day)
    if recording.exists():
        recorded = recording.read_manifest().get("master_file")
        if recorded:
            return str(recorded)
    return None


def _manifest(
    *, runner, day: date, symbols: Sequence[str], master_path: Path, mode: str,
    dry_run: bool, calendar: TradingCalendar, calendar_source: str,
) -> dict:
    """Everything the replay needs to know about the machine this day ran on."""
    spec = runner.spec
    return {
        "trade_date": day.isoformat(),
        "mode": mode,
        "dry_run": dry_run,
        "spec_version": bt.SPEC_VERSION,
        "code_sha": spec.code_sha,
        "config_digest": spec.digest(),
        "master_file": master_path.name,
        "master_sha256": spec.master_sha256,
        "row_size": spec.row_size,
        "risk_per_trade_paise": spec.risk_per_trade_paise,
        "cost_paise": spec.cost_paise,
        "factor_digest": spec.factor_digest,
        "symbols": list(symbols),
        "calendar": {
            # The C5 duty: which reading GOVERNED is stated, and the other is recorded beside
            # it as the cross-check rather than left to be guessed from which one is present.
            "governing_source": calendar_source,
            "calendar_source_field": calendar.source,
            "is_trading_day": calendar.is_trading_day(day),
            "is_standard_session": calendar.is_standard_session(day),
            "holidays_in_scope": sorted(
                holiday.isoformat() for holiday in calendar.holidays
                if holiday.year == day.year
            ),
            "excluded_weekend_sessions": [
                stamp.isoformat() for stamp in calendar.weekend_sessions
            ],
            "non_standard_sessions_store_scan": sorted(
                stamp.isoformat() for stamp in runner.non_standard_sessions
            ),
        },
        "boundaries": [stamp.isoformat() for stamp in boundary_stamps(day)],
    }


def master_tick_divergence(
    pinned: InstrumentMaster, other: InstrumentMaster, symbols: Iterable[str]
) -> dict[str, tuple[int, int]]:
    """Symbols whose tick differs between the PINNED master and another dump.

    QUESTIONS.md **Q-29**, measured rather than decided. Q-20 pins one snapshot for the whole
    backtest because the replication target (TradingView) applies the CURRENT tick to the whole
    history; a live morning's "current tick" is TODAY's, which is not necessarily the pin's. The
    tick sizes the profile row grid, hence the POC, hence every entry, stop and target -- so a
    divergence is not cosmetic. This function names the symbols it would touch. What governs is
    the architect's.
    """
    out: dict[str, tuple[int, int]] = {}
    for symbol in symbols:
        ticker = symbol.strip().upper()
        try:
            here = pinned.instrument(ticker).tick_size_paise
            there = other.instrument(ticker).tick_size_paise
        except Exception:
            continue
        if here != there:
            out[ticker] = (here, there)
    return out


__all__ = [
    "ALERT_ARMED",
    "ALERT_EXIT",
    "ALERT_FAILURE",
    "ALERT_KINDS",
    "ALERT_SQUARE_OFF",
    "ALERT_TRIGGER",
    "AlertSink",
    "BlockedByOpenQuestion",
    "Clock",
    "CollectingAlertSink",
    "LIVE_DISCLOSURE",
    "LIVE_STARTUP_DISCLOSURE",
    "LiveScreener",
    "POSTURE_LIVE",
    "POSTURE_SETTLED",
    "PHASES",
    "PHASE_ARMED",
    "PHASE_EXITED",
    "PHASE_IN_TRADE",
    "PHASE_REFUSED",
    "PHASE_SKIPPED",
    "PHASE_TRIGGERED",
    "PHASE_WAITING",
    "RETRY_BACKOFF_SECONDS",
    "ScreenAlertSink",
    "ScreenerError",
    "SoundAlertSink",
    "SweepReport",
    "SymbolState",
    "SystemClock",
    "VirtualClock",
    "boundary_stamps",
    "build_live_screener",
    "day_master_filename",
    "format_alert",
    "full_day_gates",
    "master_tick_divergence",
    "wait_for_boundary",
]
