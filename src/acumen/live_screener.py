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
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterable, Mapping, Protocol, Sequence

from . import backtest as bt
from . import signals as sig
from . import simulate as sim
from .aggregate import Bar, aggregate_15min, in_session_bars
from .bias_engine import DailyBias
from .calendar import TradingCalendar
from .instrument_master import InstrumentMaster
from .live_recording import (
    CALENDAR_PUBLISHED,
    CALENDAR_STORE_SCAN,
    FETCH_EMPTY,
    FETCH_ERROR,
    FETCH_OK,
    FETCH_SKIPPED,
    FETCH_UNREADABLE,
    FetchOutcome,
    LiveRecording,
    RecordedAlert,
)
from .live_source import BarSource, duplicate_stamps, merge_bars
from .minute_store import StoredBar
from .poc import POC_OK, SPEC_WINDOW, DayProfile, ProfileWindow
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

#: How far through its day a symbol has got. **The phase machine is MONOTONIC** (REVIEW_13 M3):
#: a re-evaluation may only move a symbol FORWARD along this ladder, never back. CONTEXT 3.4-2
#: is the reason -- *"the first qualifying cross CONSUMES the stock-day ... no later entry that
#: day ... no re-entry after any exit"* -- so a vendor revision that walks an EXITED symbol back
#: to IN-TRADE is not a correction, it is a state the strategy does not have. Demonstrated
#: before the fix: the only exit the trader received said stop-loss 199900 while the screener's
#: own final state said target 200700, a 4,000-rupee swing at qty 500.
#:
#: ``skipped`` and ``refused`` are OFF the ladder and carry no rank: the first is a sweep
#: outcome (the symbol keeps its real state underneath) and the second is a verdict about the
#: day, both of which are handled explicitly where they arise.
PHASE_RANK: Mapping[str, int] = {
    PHASE_WAITING: 0,
    PHASE_ARMED: 1,
    PHASE_TRIGGERED: 2,
    PHASE_IN_TRADE: 2,
    PHASE_EXITED: 3,
}

#: CONTEXT 3.3 + the architect's 08-Aug-2026 ruling on REVIEW_13 B3: *"the POC is fixed at 11:15
#: and immutable for the day; a window missing its late minutes is a completeness failure --
#: flag 'POC provisional / incomplete window' and never silently re-fix."* This is that flag, in
#: the ruling's own words, and it travels on the state, on both dashboards and on every alert
#: the symbol produces.
POC_PROVISIONAL: str = "POC provisional / incomplete window"

# --- the STATES an alert carries besides its numbers (REVIEW_13B Q1) ---------------------------

#: The alert stands on a window the screener cannot vouch for: its last 1-minute candle is
#: further behind this boundary than :data:`STALE_AFTER_MINUTES` allows. REVIEW_13B **Q1**
#: measured what its absence cost -- a feed answering 200 with a prefix that never grew left
#: every sweep "complete", so no banner rose, and the trader received
#: ``[15:15] HDFCBANK SQUARE-OFF at 740.95`` computed off bars that stopped at 11:29 on a day
#: whose real answer was target-hit at 749.50. The dashboard ROW was marked; the ALERT, which is
#: the surface the bell rings on and the surface chunk 14 forwards, carried nothing.
MARKER_STALE: str = "stale"
#: The alert's numbers descend from a POC pinned over an INCOMPLETE window (B357 / the
#: architect's B3 ruling). A first-class alert state, on the payload, for every kind.
MARKER_POC_PROVISIONAL: str = "poc-provisional"

#: The two above, in the order an alert line prints them. A payload's ``alert_states`` is a
#: subset of this tuple, so a reader (or a Telegram message) never meets a state nobody named.
ALERT_STATES: tuple[str, ...] = (MARKER_STALE, MARKER_POC_PROVISIONAL)

#: How far behind the boundary a state's last 1-minute bar may be before it is STALE.
#:
#: A poll at boundary ``T`` may legally have seen stamps up to ``T - 1min`` (CONTEXT 7-E12, and
#: :func:`acumen.live_source._clamp`), so a fresh state's last stamp IS ``T - 1min``. One minute
#: of tolerance, because one minute is the honest width of the clamp and not a judgment about
#: liveness. It lives HERE, beside the alert machinery, because the same predicate now decides
#: the dashboard's row marker and the alert's own -- one implementation of one sentence, which
#: is the discipline REVIEW_13 M10 set for :func:`rupees` after two of them disagreed on screen.
STALE_AFTER_MINUTES: int = 1

#: The price fields an alert can carry. If any of them is present, the alert is making a claim
#: about a PRICE and must therefore state the age of the data behind it -- which is what
#: :func:`unvouched_price` checks before a sink is allowed to forward it.
PRICE_FIELDS: tuple[str, ...] = (
    "entry_paise", "stop_paise", "target_paise", "exit_paise", "poc_paise", "reference_paise",
)

#: How a dedup key is flattened into ``state.json``. A vertical bar cannot occur in a symbol, a
#: kind or any identity component (they are stamps, integers and engine words), so the round
#: trip is exact -- and a resume that misread its own dedup set would re-send the morning.
_ALERT_KEY_SEP: str = "|"

# --- alert kinds ------------------------------------------------------------------------------

ALERT_ARMED: str = "armed"
ALERT_TRIGGER: str = "trigger"
ALERT_EXIT: str = "exit"
ALERT_SQUARE_OFF: str = "square-off"
ALERT_FAILURE: str = "failure"

ALERT_KINDS: frozenset[str] = frozenset(
    {ALERT_ARMED, ALERT_TRIGGER, ALERT_EXIT, ALERT_SQUARE_OFF, ALERT_FAILURE}
)

#: One symbol's evaluation raised and the sweep continued without it (REVIEW_14 M19). Recorded
#: per symbol per boundary, because a feed that poisons one stock at 11:15 and heals at 11:30 is
#: a different morning from one that poisons it all day.
EVENT_EVALUATION_FAILED: str = "evaluation-failed"

#: One sink raised while an alert was being delivered to it (REVIEW_14 M19, second surface). The
#: alert is already recorded and already on every other sink; this names the one that missed it.
EVENT_SINK_FAILED: str = "sink-failed"

#: An alert the POST-SESSION poll would have delivered, RECORDED instead of sent (**M4**).
#:
#: REVIEW_13 M4, upgraded in consequence by chunk 14 and measured again by REVIEW_14 H8:
#: :meth:`LiveScreener.close_day`'s 15:30 poll was an ordinary sweep, so a feed that healed after
#: 15:29 published, for the first time, a full TRIGGER with all four numbers to the screen, the
#: bell and -- once chunk 14 attached a phone to that sink tuple -- Telegram. Measured message:
#: ``[15:30] SYNTH LONG entry 2,001.00 SL 1,999.00 TP 2,007.00 qty 500``, thirty minutes after
#: the last moment CONTEXT 3.4 lets anyone act on it.
EVENT_POST_SESSION_ALERT: str = "post-session-alert-withheld"

#: One symbol's reply ARRIVED and could not be taken in (REVIEW_14B **R1**). Recorded per symbol
#: per boundary, exactly like :data:`EVENT_EVALUATION_FAILED` and for the same reason -- and kept
#: a DIFFERENT word from it, because "the evaluation raised" would be a lie about a symbol whose
#: bars never reached the evaluation at all.
EVENT_INTAKE_FAILED: str = "intake-failed"

#: What one poll of one symbol came to. **Three outcomes, not two** (REVIEW_14B **R1**).
#:
#: The bool this replaced could say "I have the day" and "I do not", and the whole of R1 lives in
#: the case it could not say: the feed ANSWERED and this tool could not take the answer in. The
#: two failures need different handling -- one is retried and re-polled at sweep end (CONTEXT 4.3
#: calls a transient burst normal), the other must not be, because part of the intake has already
#: been applied and a second identical reply would re-record the whole prefix under one sweep
#: label, which is precisely what
#: :meth:`acumen.live_recording.LiveRecording.duplicate_bars` reports to gate 2 as twins.
POLL_OK: str = "ok"
POLL_NO_ANSWER: str = "no-answer"
POLL_UNREADABLE: str = "unreadable"

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

    Raised by :func:`build_live_screener` for every entry in
    :data:`LIVE_BLOCKING_QUESTIONS`, which is EMPTY today because every class-A question a live
    morning has met so far has been ruled on (Q-28 and Q-29 on 08-Aug-2026, Q-30 with
    REVIEW_13). The exit is kept, and kept exercised by a test that registers a question and
    watches the mode refuse, because the next class-A hole a live session walks into needs it:
    refuse to start, in the question's own words, rather than start and produce a number nobody
    may rely on.
    """


#: The class-A questions that BLOCK a live morning, as ``(id, the question's own words)``.
#:
#: **This tuple is the STOP rule in executable form** (REVIEW_13 M24). Until 08-Aug-2026 that
#: rule lived as a hard-coded refusal carrying Q-28's text, and a test asserted it; the ruling
#: retired the refusal, its successor asserted a different refusal entirely, and the STOP
#: property was lost with it -- nothing went red if a future session unblocked a live mode
#: without a ruling, and :class:`BlockedByOpenQuestion` became a branch no test had ever taken.
#: Registering the block here restores the property AND generalises it: a session that meets a
#: class-A hole on the live path adds one row, and the mode refuses in the question's own words
#: until the architect rules.
#:
#: EMPTY today. Q-28 and Q-29 are CONTEXT 4.7; Q-30 is the architect's 08-Aug-2026 ruling on
#: REVIEW_13 and is executed by the settled-universe filter in :func:`build_live_screener`;
#: Q-31 is a CONTEXT edit and never blocked anything.
LIVE_BLOCKING_QUESTIONS: tuple[tuple[str, str], ...] = ()

#: CONTEXT 3.5's own outcome for a day whose per-share risk exceeds the whole trade risk:
#: *"qty == 0 -> no trade, consumed + logged"*. REVIEW_13 **M21**: the live path alerted it as a
#: TRIGGER with ``qty 0`` on the line, which is a trade the strategy does not have -- the
#: backtester writes :data:`acumen.simulate.FLAG_QTY_ZERO_UNSIZABLE`, no fill, no cost and no
#: PnL for exactly these days. Measured population over the chunk-9B ten-year ledger: **2
#: stock-days of 495,312** -- BOSCHLTD 2021-05-20 (per-share risk Rs 1,019.70) and SHREECEM
#: 2020-03-19 (Rs 1,173.30). Rare, reachable, and a spec deviation on the live path.
REFUSAL_QTY_ZERO: str = "qty 0 -- no trade, consumed (CONTEXT 3.5)"

#: The refusal a REPLAY gives for a symbol-day nothing can gate (REVIEW_13 **M22**).
#:
#: CONTEXT 4.6's battery is a WHOLE-DAY measurement -- gate 1 folds a session's total volume
#: against the day's bhavcopy -- so it is computed once and handed to every boundary. When no
#: whole day can be found (the minute lake does not hold the day and the session's own source
#: cannot serve one), the battery does not exist, and the pipeline's ``gates=None`` door means
#: "compute it here", which on a GROWING PREFIX is not a stricter reading but a WRONG one: it
#: folds a partial session against a whole-day total and refuses by gate 1. Re-measured by
#: REVIEW_13B at **15 of 17 boundaries refused**, on a day where nothing was wrong. A refusal
#: has to be the screener's own, by name, so that a parity result can never be an artefact of
#: both sides refusing for reasons neither of them stated.
REFUSAL_NO_BATTERY: str = (
    "no whole-day battery for this symbol-day: the lake does not hold it and the session's "
    "source could not serve a whole session, so CONTEXT 4.6's gates cannot be measured "
    "(gating a growing prefix against a whole-day oracle would refuse a sound day)"
)

#: The refusal a live morning gives when THE DAY'S OWN instrument master is not in the cache.
#: A module constant so a test can assert the contract by EQUALITY rather than by three
#: substrings (REVIEW_13 M24), and so the sentence cannot drift from the ruling it executes.
MASTER_MISSING_REFUSAL: str = (
    "a LIVE morning runs on THE DAY'S OWN instrument master (CONTEXT 4.7 / QUESTIONS.md Q-29), "
    "fetched pre-open. The tick sizes CONTEXT 3.3's profile row grid, hence the POC, hence every "
    "entry, stop and target -- so the day's dump is a prerequisite of the morning, not something "
    "to substitute around"
)

#: The launcher :func:`_require_day_master`'s refusal names for the pre-open refresh, relative to
#: the repository root. It is a LAUNCHER and not a module path on purpose (REVIEW_15B **R1**, and
#: REVIEW_15 **C1**, REVIEW_14 **B3**, **B429** before it): the operator's tree has no editable
#: install, so ``python -m acumen.run_screener`` -- which is what this refusal used to print --
#: answers ``No module named 'acumen'`` in a hand-typed shell. ``pyproject.toml``'s
#: ``pythonpath = ["src"]`` is PYTEST's and not a subprocess's, which is exactly how that form
#: stayed invisible to a green suite. This is the refusal a LIVE MORNING raises at 09:00, so its
#: remedy is the one that can least afford not to run. The master's launcher is
#: :data:`acumen.backtest.MASTER_LAUNCHER`, named once there and read here.
SCREENER_LAUNCHER: str = "scripts/run_screener.py"


#: CONTEXT 4.7, the architect's own words, carried on **every live alert** and on the dashboard
#: header of any live session -- dry-run included, because a dry-run morning reads the same
#: unverified feed. It is not a caveat about the software; it is a fact about the data: no
#: exchange record exists for today until the evening's bhavcopy is published.
LIVE_DISCLOSURE: str = "live feed, not yet verified against the exchange's end-of-day record"

#: The measured price of the live posture, as a BRACKET rather than as its narrow end.
#:
#: REVIEW_13 **M1**: the runtime banner printed 0.5229% -- the days refused by gate 1 ALONE --
#: while the same ledger measures the population a live morning is blind to at 2.5141%, because
#: gate 1P is inapplicable live too (CONTEXT 4.7's own preceding sentence says so) and its
#: refusals are not in the narrow figure. B341's evidence
#: (``docs/evidence/chunk13_q28_residual.md``) states both ends and its own ceiling; what the
#: operator reads now states them too. Every figure here is quoted from that document, which
#: this chunk's review re-derived independently from the 400 MB chunk-9B ledger.
LIVE_RESIDUAL_BRACKET: str = (
    "Measured residual, as a BRACKET rather than a single number (B341, re-derived by "
    "REVIEW_13): 0.5229% of settled symbol-days (2,187/418,275 over the ten-year ledger) failed "
    "gate 1 alone; 2.5141% (10,516 days) failed an ORACLE-ONLY gate -- gate 1 or gate 1P, both "
    "inapplicable this morning; and the measurable ceiling, counting the 697 days whose gate-2 "
    "trigger the ledger does not name, is 2.6808%. So the frequency this morning accepts and "
    "discloses is 0.5229%-2.6808%, not 0.5229%."
)

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
    "then refuses. " + LIVE_RESIDUAL_BRACKET + " Section 6 parity is judged on oracle-passing "
    "days; a live-alerted day the oracle later refuses is that disclosed, bounded difference. "
    "This morning screens the SETTLED UNIVERSE ONLY (CONTEXT 4.7 / QUESTIONS.md Q-30, architect "
    "08-Aug-2026): the symbols CONTEXT 4.6 quarantined are NOT screened and are named below, "
    "because the screener alerts on what the backtester validated. The instrument master is "
    "THIS DAY'S OWN dump (QUESTIONS.md Q-29), named and hashed into the recording. "
    "THIS TOOL PLACES NO ORDERS."
)

#: How far back the live bias SERIES is seeded. REVIEW_13 **B1**.
#:
#: CONTEXT 3.2 rule 1 (*"Inside bar ... bias unchanged (carry last known bias)"*) and rule 5
#: (*"No rule fires -> carry last known bias"*) both need an EARLIER bias to carry, and a series
#: seeded at the trade day itself has none: the engine correctly answers "not seeded" -- a state
#: 3.2's Seeding paragraph reserves for HISTORY START -- and the screener refused the symbol for
#: the whole day. Measured over the chunk-9B ten-year ledger: **62,692 of 406,488 evaluated
#: stock-days (15.42%) and 29,121 of 188,345 executed trades (15.46%)** stand on a carried bias,
#: every one of them invisible to the live half, silently.
#:
#: **The value is MEASURED, not chosen.** CONTEXT 3.2's model is one series from history start,
#: which the backtester really does walk and a live morning cannot: seeding 204 symbols from
#: 2016 before the bell is not a pre-open job. So the live series takes a LOOK-BACK, and the
#: only question is how long it has to be to reach the last day a RULE fired -- because once it
#: does, the carry resolves to the same bias the full series carries, and reaching further back
#: cannot change it. Longer is never wrong, only slower.
#:
#: Streamed over all 495,312 rows of the chunk-9B ten-year ledger
#: (``docs/evidence/chunk13_fix2_bias_stratified.md``), the distance from a day back to the most
#: recent rule-firing day is: 84.23% zero (a rule fired that day), 99.03% within 3 calendar days,
#: 99.98% within 7, and **112 days at the very worst** -- one stretch, FORCEMOT's missing daily
#: candles of Dec-2023..Feb-2024, where 55 rows (0.013%) exceed 30 days. 180 days therefore
#: covers the whole measured decade with ~60% headroom.
#:
#: Its price is real and is stated rather than hidden: the pre-open build costs ~13.5s per
#: symbol at 180 days against ~4.1s at 30 (measured on the operator's machine over 20 symbols),
#: so a 204-symbol universe is roughly 46 minutes of pre-open work instead of 14. That is
#: affordable exactly because it is PRE-open: the first sweep is at 11:15 and nothing waits on
#: it. It buys the 15.42% of evaluated stock-days that stand on a carried bias -- 62,680 of
#: 406,488, and 29,121 of 188,345 executed trades -- which is what REVIEW_13 B1 measured the
#: live half was losing silently.
SEED_LOOKBACK_DAYS: int = 180


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

    **REVIEW_13B Q1**: the alert's own STATES print between the numbers and the disclosure, and
    they print BEFORE it deliberately -- the disclosure is a standing condition of every live
    morning, while a staleness or provisional-POC marker is a fact about THIS alert, and the
    thing that is true only today must not be read as part of the sentence that is true daily.
    """
    line = _format_alert_body(alert)
    for note in alert_state_notes(alert.payload):
        line = f"{line}   [{note}]"
    disclosure = alert.payload.get("disclosure")
    return f"{line}   [{disclosure}]" if disclosure else line


def alert_state_notes(payload: Mapping) -> tuple[str, ...]:
    """The human sentence for each state on this alert, in :data:`ALERT_STATES` order.

    Read off the payload rather than recomputed, so what the terminal prints, what the HTML
    dashboard shows and what chunk 14 forwards to Telegram are the same three sentences from
    the same source -- and so a recording replayed months later still says what it said.
    """
    states = set(payload.get("alert_states") or ())
    notes: list[str] = []
    for marker in ALERT_STATES:
        if marker not in states:
            continue
        if marker == MARKER_STALE:
            notes.append(str(payload.get("stale_note") or MARKER_STALE))
        else:
            notes.append(str(payload.get("poc_note") or POC_PROVISIONAL))
    return tuple(notes)


def stale_note(behind_minutes: int) -> str:
    """The staleness marker's own words. One place, so every surface says the same thing."""
    return (
        f"STALE {behind_minutes}m BEHIND -- this price stands on a window the screener cannot "
        "vouch for"
    )


def unvouched_price(alert: RecordedAlert) -> str | None:
    """Why this alert's price may NOT be forwarded, or ``None`` when it may.

    **The chunk-14 rule, in executable form:** *no alert forwarded to Telegram may carry a price
    the screener cannot vouch for.* An alert vouches for its price by carrying the AGE of the
    data behind it -- ``stale`` plus ``data_behind_minutes`` -- and, when that age is beyond the
    clamp, by carrying the marker that says so. So there are exactly two ways to fail:

    1. the alert names a price and carries no freshness stamp at all, which is the shape
       REVIEW_13B Q1 found (the row was marked, the payload was not);
    2. it is stale and the marker did not travel with it; or
    3. **the stamp contradicts itself** -- it says FRESH while its own recorded age is past the
       clamp (REVIEW_14 **H4**). A missing stamp was caught here from the first day; a false one
       was not, and a false one is worse, because it is the shape that survives a reviewer's eye.
       The predicate does not need a clock to catch it: the two numbers are both on the payload
       and they have to agree -- and BOTH have to be there. REVIEW_14B **L3**: rule 3 needed the
       age to be an ``int`` to fire, so a payload carrying ``stale`` with no
       ``data_behind_minutes`` slipped all three rules and forwarded a price whose age nothing
       stated. Unreachable from :meth:`LiveScreener._alert`, which sets the pair together -- and
       a predicate that is only correct because of what its one caller happens to do is a
       predicate this repo has been bitten by before.

    A sink calls this before it sends. Deliberately a function of the PAYLOAD alone: the sink
    holds no clock, no bars and no state, so what it can check is exactly what a later reader of
    the recording can check.
    """
    payload = alert.payload
    if not any(payload.get(field) is not None for field in PRICE_FIELDS):
        return None
    if "stale" not in payload:
        return (
            f"{alert.symbol} {alert.kind}: the payload names a price and carries no freshness "
            "stamp, so nothing on it says how old the window behind that price is"
        )
    if payload.get("stale") and MARKER_STALE not in set(payload.get("alert_states") or ()):
        return (
            f"{alert.symbol} {alert.kind}: the window behind this price is "
            f"{payload.get('data_behind_minutes')} minute(s) behind the boundary and the alert "
            "carries no staleness marker"
        )
    behind = payload.get("data_behind_minutes")
    if not isinstance(behind, int) or isinstance(behind, bool):
        # **L3.** A freshness stamp is the pair, not the flag: an age that is absent, null or
        # anything but a whole number of minutes means nothing on this payload says how old the
        # window behind the price is -- which is rule 1's own failure, arriving by a second door.
        return (
            f"{alert.symbol} {alert.kind}: the payload names a price and stamps it "
            f"stale={payload.get('stale')!r} with no NUMBER for how far behind the boundary its "
            f"window is (data_behind_minutes={behind!r}), so the stamp vouches for nothing"
        )
    if not payload.get("stale") and behind > STALE_AFTER_MINUTES:
        return (
            f"{alert.symbol} {alert.kind}: the payload stamps this price FRESH while its own "
            f"recorded age is {behind} minute(s) behind the boundary -- a stamp that contradicts "
            "itself vouches for nothing"
        )
    return None


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


def rupees(paise) -> str:
    """Integer (or exact Fraction) paise as rupees -- and a HALF-paise POC as it really is.

    CONTEXT 3.3 lets a POC sit on half a paisa (it is a row MIDPOINT) and CONTEXT 7-E11 says
    every comparison against it runs at full precision, integer paise internally, and NO float
    anywhere. Two decimal places are right for money and wrong for a row midpoint: they would
    move the POC by half a paisa on the one line whose purpose is that the trader can check it
    against his own chart. So a value that is a whole number of paise prints in two places and
    one that is not prints in three -- the same rule ``trader_pack._Emit.poc`` applies to the
    validation pack, for the same reason.

    **One implementation, because there were two** (REVIEW_13 M10). The dashboard rendered a
    half-paise POC exactly (148.695) while the ALERT line -- the line the alert log shows, the
    terminal prints and chunk 14 forwards -- converted through a binary float and printed
    148.69. Four real 2026-06-10 POCs all moved, and the direction was IEEE-754's rather than a
    stated rule. :func:`acumen.live_dashboard.rupees` is now this function.

    Exact throughout: :class:`~fractions.Fraction` and :class:`~decimal.Decimal`, never a float.
    """
    if paise is None:
        return "-"
    value = Fraction(paise)
    if value.denominator == 1:
        exact = (Decimal(value.numerator) / Decimal(100)).quantize(Decimal("0.01"))
        return f"{exact:,.2f}"
    exact = (
        Decimal(value.numerator) / Decimal(value.denominator) / Decimal(100)
    ).quantize(Decimal("0.001"))
    return f"{exact:,.3f}"


#: The alert line's own name for it. Kept so the formatter reads as it always did.
_rs = rupees


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
    #: CONTEXT 3.3 / B3: the 09:15-11:14 window was SHORT of its 120 expected minutes at the
    #: moment the POC was pinned. The POC is not re-fixed for it -- it is disclosed.
    poc_provisional: bool = False
    #: How many of the window's 120 expected minutes were missing when the POC was pinned.
    poc_missing_minutes: int = 0

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
            "poc_provisional": self.poc_provisional,
            "poc_missing_minutes": self.poc_missing_minutes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping) -> "SymbolState":
        """Rebuild a state written by :meth:`as_dict`. The other half of a crash-safe resume.

        REVIEW_13 **B8**: ``restore()`` round-tripped the dedup set and the bars and then left
        every symbol at its pre-open phase, because nothing ever read back what ``persist()``
        wrote. A resumed screener that has forgotten a symbol is IN TRADE is a screener that
        will re-alert its entry and can miss its exit.
        """
        stamp = payload.get("last_stamp")
        poc = payload.get("poc_paise")
        return cls(
            symbol=str(payload["symbol"]),
            phase=str(payload.get("phase", PHASE_WAITING)),
            detail=str(payload.get("detail", "")),
            bias=payload.get("bias"),
            bias_rule=str(payload.get("bias_rule", "")),
            side=payload.get("side"),
            poc_paise=None if poc is None else Fraction(str(poc)),
            reference_paise=payload.get("reference_paise"),
            entry_paise=payload.get("entry_paise"),
            stop_paise=payload.get("stop_paise"),
            target_paise=payload.get("target_paise"),
            qty=payload.get("qty"),
            exit_kind=payload.get("exit_kind"),
            exit_paise=payload.get("exit_paise"),
            minute_count=int(payload.get("minute_count", 0) or 0),
            last_stamp=None if not stamp else datetime.fromisoformat(str(stamp)),
            refusal=payload.get("refusal"),
            poc_provisional=bool(payload.get("poc_provisional", False)),
            poc_missing_minutes=int(payload.get("poc_missing_minutes", 0) or 0),
        )


def data_age(state: SymbolState, now: datetime) -> tuple[bool, int]:
    """``(is this state STALE, how many minutes behind ``now`` its last bar is)``.

    REVIEW_13 B10 / M20 raised it for the dashboard ROW; REVIEW_13B **Q1** is that the ALERT
    needed the same answer and there was no shared place to ask it. This is that place -- the
    dashboard imports this function, exactly as it imports :func:`rupees`, so a row and the
    alert beside it can never disagree about whether the same window is stale.

    **REVIEW_14 H4.** A ``refused`` state used to short-circuit to ``(False, 0)`` -- the reading
    being that its data is not what the reader is asked to act on. That is true of a refused row
    on the dashboard and FALSE of the one alert kind that names prices out of a refused state:
    the *"the battery now REFUSES this day while a position is open"* FAILURE alert, which
    carries entry, stop, target and qty precisely so the trader can manage a position this tool
    has stopped watching. Measured by the review: a feed frozen at 11:29 produced, at 15:00, such
    an alert stamped ``stale=False, data_behind_minutes=0`` over a true gap of **211 minutes** --
    and :func:`unvouched_price` accepted it, because a missing stamp is caught by the predicate
    and a FALSE one was not.

    So the age is now measured for every state, always. It is a MEASUREMENT and never a verdict:
    what a surface does with it stays that surface's own choice, and the dashboard's refused rows
    are rendered from the same numbers they always were.
    """
    if state.last_stamp is None:
        return (state.minute_count == 0, 0)
    behind = int((now - state.last_stamp).total_seconds() // 60)
    return (behind > STALE_AFTER_MINUTES, max(0, behind))


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
    #: Symbols whose data ARRIVED and whose evaluation then raised (REVIEW_14 M19). A third
    #: outcome beside fetched and skipped, and a first-class one: the sweep completed, these
    #: symbols did not, and the banner names them because a symbol that vanishes from the watch
    #: list without being named is indistinguishable from a symbol with nothing to say.
    unevaluated: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.skipped and not self.failed and not self.unevaluated

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
    #: Symbols the session is NOT screening, and why -- CONTEXT 4.7 / Q-30's quarantined six on
    #: a live morning. Carried so the exclusion is NAMED at startup rather than inferred from a
    #: count that is six short (REVIEW_13 M2).
    excluded: tuple[tuple[str, str], ...] = ()
    #: Why THIS master governs, decided from the file that was actually resolved rather than
    #: from the mode flag (REVIEW_13 M9).
    master_reason: str = ""

    # --- mutable session state (persisted to state.json after every sweep) ---
    bars: dict[str, tuple[StoredBar, ...]] = field(default_factory=dict)
    states: dict[str, SymbolState] = field(default_factory=dict)
    #: The alerts already DELIVERED, keyed by ``(symbol, kind, identity)`` -- see
    #: :meth:`_alert_key`. The third element is what REVIEW_13 B334/B9 showed ``(symbol, kind)``
    #: was missing: the identity of the state being alerted about.
    alerted: set[tuple[str, str, str]] = field(default_factory=set)
    banner: str = ""
    #: True ONLY while :meth:`close_day`'s post-session poll runs (**M4**). CONTEXT 3.4's last
    #: entry closes at 15:00 and its square-off at 15:15, so nothing after 15:29 is actionable --
    #: and an alert nobody can act on, arriving after the market has closed, is worse than no
    #: alert. While this is set every alert is still computed, still deduped and still WRITTEN --
    #: as :data:`EVENT_POST_SESSION_ALERT`, with its whole payload -- and no sink is fired. No
    #: new trade is created from post-15:29 bars either way (``in_session_bars`` drops them, and
    #: the parity harness proves the decision is unchanged), so this is annunciation and not
    #: strategy: the recording says everything it said before, and the phone stays quiet.
    post_session: bool = False
    sweeps_done: list[str] = field(default_factory=list)
    #: CONTEXT 3.3's POC, PINNED at 11:15 and immutable for the day (REVIEW_13 B3).
    profiles: dict[str, DayProfile] = field(default_factory=dict)
    #: Bars a single vendor reply served under a stamp it had already served in that same reply.
    #: Kept so CONTEXT 4.5 gate 2 can SEE them (REVIEW_13 B2) -- ``merge_bars`` resolves a
    #: re-polled stamp for the ENGINE, and resolving it before the gate is what laundered a
    #: corrupt twin past the one gate CONTEXT 4.7 leaves standing.
    duplicate_bars: dict[str, tuple[StoredBar, ...]] = field(default_factory=dict)

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

    def run_day(
        self,
        *,
        on_sweep: Callable[[SweepReport], None] | None = None,
        before_sweep: Callable[[datetime], None] | None = None,
    ) -> tuple[SweepReport, ...]:
        """Sweep every boundary of the day, in order, then CLOSE the day. One report per sweep.

        **This is the loop, and it is the only loop** (REVIEW_13 B4 + B8). ``run_screener.main``
        used to re-implement it, which is how ``run_day``, ``close_day`` and ``restore`` all came
        to have no caller anywhere in ``src/``: the class was crash-safe, closed its recording
        and resumed correctly, and the only entry point an operator had reached none of it.

        ``before_sweep`` is called with each boundary BEFORE it is swept, and it is what lets one
        loop serve both modes without either of them owning a second copy of it: a live morning
        passes a function that WAITS for the wall clock to reach the boundary (the candle has to
        close before it can be polled for -- CONTEXT 7-E12), a replay passes one that sets the
        virtual clock and returns at once. It is called for :meth:`close_day`'s 15:30 poll too,
        because that poll waits exactly like the others.
        """
        reports = []
        for boundary in boundary_stamps(self.day):
            if before_sweep is not None:
                before_sweep(boundary)
            report = self.sweep(boundary)
            reports.append(report)
            if on_sweep is not None:
                on_sweep(report)
        report = self.close_day(before_sweep=before_sweep)
        reports.append(report)
        if on_sweep is not None:
            on_sweep(report)
        return tuple(reports)

    def close_day(
        self, *, before_sweep: Callable[[datetime], None] | None = None
    ) -> SweepReport:
        """One last poll after 15:29, so the RECORDING holds the whole session.

        Not a decision boundary -- CONTEXT 3.4's last entry closes at 15:00 and its square-off at
        15:15, and no bar after 15:14 can change either (chunk 8 proved the 15:15-stamped candle
        is never read). This exists for the REPLAY CONTRACT, and it is load-bearing there: gate 1
        reconciles the day's WHOLE folded volume against the bhavcopy, so a recording that
        stopped at 15:14 could never be pushed back through the backtest path at all. The last
        fifteen minutes of the session are evidence even though they are not information.

        The states are recomputed from the completed day and must not move; if one ever does,
        something after 15:14 reached a decision and that is a defect, not a late correction.

        **This poll ANNUNCIATES NOTHING** (REVIEW_13 **M4**, re-measured as REVIEW_14 H8). It was
        an ordinary sweep, so on a feed that healed after 15:29 it published a full TRIGGER --
        entry, stop, target, quantity -- to the screen, the bell and, once chunk 14 attached a
        phone to that sink tuple, Telegram, half an hour after the last moment CONTEXT 3.4 lets
        anyone act on it. :attr:`post_session` is the flag REVIEW_14's remedy asked for: every
        alert this poll warrants is still computed, deduped and written into the recording as
        :data:`EVENT_POST_SESSION_ALERT` with its whole payload, and no sink is fired. The
        operator still sees the moved state -- the dashboard and the closing terminal render both
        read :meth:`by_phase`, and the banner is still set -- so nothing is hidden; it is only
        not ANNOUNCED as though it were tradeable.
        """
        stamp = datetime.combine(self.day, SESSION_END)
        if before_sweep is not None:
            before_sweep(stamp)
        before = dict(self.states)
        self.post_session = True
        try:
            report = self.sweep(stamp)
        finally:
            self.post_session = False
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
        #: Symbols whose reply ARRIVED and could not be taken in (REVIEW_14B **R1**). They are
        #: NOT re-polled: see :meth:`_poll` for why a second identical reply is worse than none.
        unreadable: list[str] = []
        deadline_hit = False

        for index, symbol in enumerate(self.symbols):
            if self.clock.now() > deadline:
                deadline_hit = True
                deferred.extend(self.symbols[index:])
                break
            outcome = self._poll(symbol, boundary, label)
            if outcome == POLL_OK:
                fetched.append(symbol)
            elif outcome == POLL_UNREADABLE:
                unreadable.append(symbol)
            else:
                deferred.append(symbol)

        # CONTEXT 4.4's second pass -- "on failure SKIP the symbol and re-poll at sweep end".
        # It re-polls the symbols that did not ANSWER, and only those.
        still: list[str] = []
        for symbol in deferred:
            if self.clock.now() > deadline:
                deadline_hit = True
                still.append(symbol)
                continue
            outcome = self._poll(symbol, boundary, label, attempt=2)
            if outcome == POLL_OK:
                fetched.append(symbol)
            elif outcome == POLL_UNREADABLE:
                unreadable.append(symbol)
            else:
                still.append(symbol)
        failed = [s for s in still if s in self.bars]
        skipped = [s for s in still if s not in self.bars]

        alerts: list[RecordedAlert] = []
        evaluated = 0
        # A symbol whose reply could not be taken in never reaches the evaluation, so it is
        # unevaluated in exactly the sense M19's symbols are -- and the banner NAMES it for
        # exactly the same reason (REVIEW_14B R1).
        unevaluated: list[str] = list(unreadable)
        for symbol in fetched:
            try:
                alerts.extend(self._evaluate(symbol, boundary))
            except Exception as exc:
                # REVIEW_14 PART 4, **M19** -- the finding that disqualified the dry-run week.
                # A vendor reply carrying an in-session candle stamped on the PREVIOUS trading
                # day raised `PocError` at the first boundary, and the exception escaped
                # `run_screener.main` entirely: 0 of 18 sweeps, no dashboard, no banner, six
                # symbols never evaluated all day, and a restart resumed into the same raise.
                # One symbol lost the morning. CONTEXT 4.4's discipline for a symbol that will
                # not answer -- "SKIP the symbol and re-poll" -- is already implemented on the
                # FETCH side above; this is the same discipline on the EVALUATION side, and it
                # is deliberately as narrow as that one: the symbol keeps its previous state,
                # the reason is recorded per symbol per boundary, the banner NAMES it, and the
                # other 203 symbols finish their sweep.
                unevaluated.append(symbol)
                self._evaluation_failed(symbol, boundary, exc)
                continue
            evaluated += 1
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
            unevaluated=tuple(unevaluated),
        )
        self._settle_banner(report)
        self.sweeps_done.append(label)
        self.recording.record_event(
            "sweep-closed", at=finished, sweep=label,
            fetched=len(fetched), skipped=len(skipped), failed=len(failed),
            evaluated=evaluated, alerts=len(alerts), deadline_hit=deadline_hit,
            unevaluated=len(unevaluated),
            detail="complete" if report.complete else "INCOMPLETE",
        )
        self.persist()
        return report

    def _poll(self, symbol: str, boundary: datetime, label: str, *, attempt: int = 1) -> str:
        """Fetch one symbol and TAKE ITS REPLY IN. CONTEXT 4.4's short retries, then skip.

        Returns :data:`POLL_OK`, :data:`POLL_NO_ANSWER` or :data:`POLL_UNREADABLE`.

        **The guard covers the WHOLE per-symbol body** -- REVIEW_14B **R1**, and the architect's
        15-Aug-2026 note, which calls the narrower shape an under-prescription rather than a
        regression: REVIEW_14's remedy for M19 named the ``_evaluate`` call and the sink loop,
        chunk 14 implemented exactly that, and CONTEXT 4.4's skip-and-continue property is wider
        than the prescription was. The ``try`` used to wrap ``self.source.fetch(...)`` and
        nothing else, so the four statements after it -- ``merge_bars``, ``duplicate_stamps``,
        ``record_bars`` and ``record_fetch`` -- stood outside every guard in this module, and a
        bar that survived the fetch and died in that block ended the sweep, the morning, and
        (because :meth:`restore` resumes into the same bytes) the restart too. Measured by that
        re-review over seven malformed one-minute shapes, three escaped ``run_day`` entirely: a
        tz-AWARE stamp (``TypeError`` in ``merge_bars``), and ``close_paise=None`` or
        ``volume=None`` (``TypeError`` in ``record_bars``). The reachable case is not exotic --
        one locked or unwritable candle file at 11:30 on a laptop took the universe down with it.

        **A failure before the reply is retried; a failure after it is not,** and both halves are
        deliberate:

        * before -- the feed did not answer, which CONTEXT 4.3 calls normal, and a short retry is
          the ruling's own remedy;
        * after -- the same bytes will fail the same way 0.5s later, and part of this block has
          already been applied, so re-running it would double what succeeded and re-record the
          whole prefix under ONE sweep label, which is exactly the shape
          :meth:`acumen.live_recording.LiveRecording.duplicate_bars` hands to gate 2 as twins. A
          fix that made tomorrow's verification refuse the day would be worse than the defect.

        Either way the symbol keeps its previous state, is named in the banner, and is re-polled
        at the NEXT boundary like any other. One symbol loses one boundary; nobody loses the
        morning.
        """
        backoff = RETRY_BACKOFF_SECONDS if attempt == 1 else RETRY_BACKOFF_SECONDS[:1]
        last_error = ""
        for tries in range(len(backoff) + 1):
            at = self.clock.now()
            began = at
            answered = False
            try:
                bars = self.source.fetch(symbol, self.day, boundary)
                answered = True
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
                # CONTEXT 4.5 gate 2's first trigger, kept VISIBLE to it (REVIEW_13 B2). The
                # merge above resolves a re-polled stamp for the engine, which needs one bar per
                # minute; the twins it resolved away are carried here so the battery can refuse
                # the day. The ACCUMULATION is the last statement of the block on purpose: it is
                # the one step here that is not idempotent, so nothing that can raise may follow
                # it (R1's guard makes that reachable, where before it was unreachable by being
                # fatal).
                twins = duplicate_stamps(bars)
                if twins:
                    self.recording.record_event(
                        "duplicate-stamps", at=at, sweep=label, symbol=symbol,
                        count=len(twins),
                        detail=(
                            f"{len(twins)} stamp(s) served twice in one reply "
                            f"({', '.join(bar.stamp.strftime('%H:%M') for bar in twins[:5])}); "
                            "CONTEXT 4.5 gate 2 excludes a day carrying one"
                        ),
                    )
                    self.duplicate_bars[symbol] = self.duplicate_bars.get(symbol, ()) + twins
            except Exception as exc:  # a feed failure is normal (CONTEXT 4.3); a crash is not
                last_error = f"{type(exc).__name__}: {exc}"
                if answered:
                    self._intake_failed(
                        symbol, boundary, label, at=at, attempt=attempt, exc=exc
                    )
                    return POLL_UNREADABLE
                self.recording.record_fetch(FetchOutcome(
                    symbol=symbol, sweep=label, outcome=FETCH_ERROR, bars=0,
                    at=at, attempt=attempt, detail=last_error,
                ))
                if tries < len(backoff):
                    self.clock.sleep(backoff[tries])
                    continue
                return POLL_NO_ANSWER
            if not bars:
                # REVIEW_13 B10: an EMPTY answer is a not-answer, not a successful fetch. A feed
                # replying 200 with an empty candle array used to count as complete, so no
                # banner rose, every symbol froze on its last good prefix, and a blind screener
                # rendered as a calm morning. It is recorded (above) and then treated exactly as
                # a failure is: retried, deferred to the sweep's second pass, and reported.
                last_error = "the feed answered with NO candles"
                if tries < len(backoff):
                    self.clock.sleep(backoff[tries])
                    continue
                return POLL_NO_ANSWER
            return POLL_OK
        return POLL_NO_ANSWER

    def _intake_failed(
        self, symbol: str, boundary: datetime, label: str, *,
        at: datetime, attempt: int, exc: Exception,
    ) -> None:
        """The reply ARRIVED and could not be taken in. Record it BY NAME, and mark it (**R1**).

        The twin of :meth:`_evaluation_failed`, one step earlier in the same per-symbol body and
        with the same discipline -- the symbol keeps its previous state, the reason is on disk
        per symbol per boundary, the banner NAMES it, and the rest of the universe finishes its
        sweep. It is a separate word from ``evaluation-failed`` because these bars never reached
        the evaluation, and a separate word from *"missed its data window"* because they arrived.

        **Both recordings are best-effort, and that is the point.** The reachable cause of this
        branch is the recording itself failing -- a locked or unwritable candle file at 11:30 --
        so the line that describes the failure is written by the machinery that just failed.
        Losing that line is not a reason to lose the morning: the banner still names the symbol
        on the operator's screen, and the state still says it is not being watched.
        """
        reason = f"{type(exc).__name__}: {exc}"
        state = self.states[symbol]
        if state.phase not in (PHASE_REFUSED, PHASE_EXITED):
            self.states[symbol] = replace(
                state, phase=PHASE_SKIPPED,
                detail=(
                    f"the {label} reply could not be taken in ({type(exc).__name__}); kept its "
                    "previous state and NOT being watched"
                ),
            )
        try:
            self.recording.record_fetch(FetchOutcome(
                symbol=symbol, sweep=label, outcome=FETCH_UNREADABLE, bars=0,
                at=at, attempt=attempt, detail=reason,
            ))
        except Exception:  # the recording is the most likely thing to have failed here
            pass
        try:
            self.recording.record_event(
                EVENT_INTAKE_FAILED, at=boundary, symbol=symbol, sweep=label,
                error=type(exc).__name__,
                detail=(
                    f"{symbol}: the {label} reply ARRIVED and could not be taken in -- {reason}. "
                    "The symbol keeps its previous state and is SKIPPED for this boundary "
                    "(CONTEXT 4.4); the rest of the sweep continues and it is re-polled at the "
                    "next boundary."
                ),
            )
        except Exception:  # pragma: no cover -- same reason, stated once above
            pass

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

        gates = self._battery(symbol, minutes)
        if gates is None:
            # REVIEW_13 M22. `gates=None` reaches `evaluate` as "compute it here", which on a
            # growing prefix measures a partial session against a whole-day oracle and refuses
            # by gate 1 at every boundary but the last. The screener refuses in its OWN words
            # instead, once, so the reason is the true one and a parity harness can tell a
            # refusal apart from an agreement.
            return self._refuse_without_battery(symbol, boundary, minutes)
        stock_day = self.pipeline.evaluate(
            symbol, self.day, bias=bias, minutes=minutes, gates=gates,
            profile=self._profile(symbol, minutes, boundary, gates),
        )
        before = self.states[symbol]
        after = self._state_from(stock_day, boundary, previous=before)
        self.states[symbol] = after
        return self._alerts_for(after, stock_day, boundary)

    def _refuse_without_battery(
        self, symbol: str, boundary: datetime, minutes: Sequence[StoredBar]
    ) -> list[RecordedAlert]:
        """No whole-day battery exists for this symbol-day: refuse it BY NAME (REVIEW_13 M22).

        Recorded once, on the boundary that first meets it, so a replay of a day the lake does
        not hold reads as one refusal with a stated cause instead of fifteen gate-1 failures
        that were never really gate 1's verdict.
        """
        previous = self.states[symbol]
        bias = self.biases.get(symbol)
        if previous.refusal != REFUSAL_NO_BATTERY:
            self.recording.record_event(
                "battery-unavailable", at=boundary, symbol=symbol,
                minutes=len(minutes), detail=f"{symbol}: {REFUSAL_NO_BATTERY}",
            )
        self.states[symbol] = SymbolState(
            symbol=symbol, phase=PHASE_REFUSED,
            bias=None if bias is None else bias.bias,
            bias_rule="" if bias is None else bias.rule,
            detail=REFUSAL_NO_BATTERY, refusal=REFUSAL_NO_BATTERY,
            minute_count=len(minutes),
            last_stamp=minutes[-1].stamp if minutes else None,
        )
        return []

    def _profile(
        self,
        symbol: str,
        minutes: Sequence[StoredBar],
        boundary: datetime,
        gates: DayGates | None,
    ) -> DayProfile | None:
        """CONTEXT 3.3's POC for this symbol -- computed ONCE, at 11:15, immutable thereafter.

        The architect's ruling of 08-Aug-2026 on REVIEW_13 **B3**: *"the POC is fixed at 11:15
        and immutable for the day; a window missing its late minutes is a completeness failure --
        flag 'POC provisional / incomplete window' and never silently re-fix."* CONTEXT 3.3's
        own last line says the same thing and the live layer did not implement it: the profile
        was rebuilt from the bars in hand at every boundary, and :class:`SmartApiBarSource`
        deliberately re-pulls the whole session each sweep, so the day's POC moved under alerts
        that had already been delivered. Measured on the real lake over 290 symbol-days: it
        moves on 2.76% of them if only the 11:14 bar is late -- the EXPECTED case, since that
        bar closes at 11:15:00.0 and CONTEXT 4.4 measures it arriving ~0.2s later -- on 14.48%
        if the last five minutes are, and on **53 real symbol-days a 1-5-minute-late window
        flipped the 11:15 arming decision, in both directions**.

        Pinned on the FIRST evaluation at or after 11:15 rather than at the 11:15 stamp alone,
        because a symbol whose 11:15 poll was skipped must still get a POC; the window it is
        built over is CONTEXT 3.3's 09:15-11:14 either way, whenever it is computed.

        ``None`` before the POC boundary, which means "let the engine answer for the prefix it
        was given" -- and before 11:15 that answer is *collecting*, not a verdict.
        """
        if boundary < sig.bar_close_stamp(self.day, sig.REFERENCE_BAR):
            return None
        pinned = self.profiles.get(symbol)
        if pinned is not None:
            return pinned
        licence = None if gates is None else gates.poc_licence
        profile = self.pipeline.profile_day(symbol, self.day, minutes, licence=licence)
        if profile.poc_paise is None:
            # No POC to pin yet -- a refused day, or a window with no candles at all. Nothing is
            # cached, so a symbol whose data arrives late still gets its one honest pass.
            return profile
        self.profiles[symbol] = profile
        missing = profile.missing_window_minutes
        self.recording.record_event(
            "poc-pinned", at=boundary, symbol=symbol,
            poc_paise=str(profile.poc_paise),
            window_minutes=profile.bar_count,
            missing_minutes=missing,
            detail=(
                f"CONTEXT 3.3: POC fixed for the day at {boundary.strftime('%H:%M')}"
                + (f" -- {POC_PROVISIONAL}: {missing} of "
                   f"{profile.window.expected_minutes} window minute(s) absent" if missing else "")
            ),
        )
        return profile

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

        **The live branch is handed the duplicate stamps too** (REVIEW_13 B2). ``merge_bars``
        resolves a re-polled stamp so the ENGINE sees one bar per minute, which it must; running
        the GATE over the merged day meant CONTEXT 4.5's first exclusion trigger could never
        fire, so a vendor reply carrying two rows under one stamp passed a battery that the
        settled battery refuses outright, and the surviving bar was the corrupt twin.
        """
        if self.posture == POSTURE_LIVE:
            twins = self.duplicate_bars.get(symbol, ())
            return oracle_free_battery(self.day, tuple(minutes) + twins)
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
            if PHASE_RANK.get(previous.phase, 0) >= PHASE_RANK[PHASE_TRIGGERED]:
                # REVIEW_13 M5, which B2's fix makes reachable rather than theoretical: a
                # duplicate stamp arriving at 12:00 now refuses the day, correctly -- and the
                # symbol had an OPEN POSITION. Its four numbers must not simply leave the state:
                # the trader is in that trade. The refusal is carried WITH them, and
                # `_alerts_for` turns it into a loud failure alert rather than a silent
                # disappearance from the watch list.
                return replace(
                    previous, phase=PHASE_REFUSED, refusal=stock_day.reason,
                    detail=(
                        f"the battery now REFUSES this day while a position is open: "
                        f"{stock_day.reason}"
                    ),
                    minute_count=minutes, last_stamp=last_stamp,
                )
            return SymbolState(
                phase=PHASE_REFUSED, detail=stock_day.reason,
                refusal=stock_day.reason, **base,
            )

        signal = stock_day.signal
        assert signal is not None  # evaluated days always carry one
        profile = stock_day.profile
        poc = profile.poc_paise if profile is not None else None
        missing = 0 if profile is None else profile.missing_window_minutes
        common = dict(
            base, poc_paise=poc, reference_paise=signal.reference_paise,
            poc_provisional=bool(missing), poc_missing_minutes=missing,
        )

        if signal.entry is None:
            phase = PHASE_ARMED if signal.final_state == sig.STATE_ARMED else PHASE_WAITING
            return self._monotonic(
                SymbolState(phase=phase, detail=_state_words(signal), **common), previous
            )

        entry = signal.entry
        qty = (
            sim.position_size(self.risk_per_trade_paise, entry.risk_paise)
            if self.risk_per_trade_paise else None
        )
        if qty == 0:
            return self._consumed_unsizable(entry, common, previous=previous, boundary=boundary)
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
        return self._monotonic(SymbolState(
            phase=phase, detail=detail,
            entry_paise=entry.entry_paise, stop_paise=entry.stop_paise,
            target_paise=entry.target_paise, qty=qty,
            exit_kind=exit_kind, exit_paise=exit_paise, **common,
        ), previous)

    def _consumed_unsizable(
        self, entry, common: dict, *, previous: SymbolState, boundary: datetime
    ) -> SymbolState:
        """CONTEXT 3.5's ``qty == 0``: **no trade, consumed + logged** (REVIEW_13 **M21**).

        The cross was real, so the stock-day is CONSUMED (CONTEXT 3.4-2) and nothing later can
        trade it -- but a single share would already risk more than the trader's whole per-trade
        budget, so nothing is bought and there is no position to alert, to watch or to square
        off. The backtester has always said exactly this: ``simulate._unsizable_record`` keeps
        the entry, stop and target for the replay pack, writes ``qty 0``, NO fill price, no cost
        and no PnL, and flags the row ``qty_zero_unsizable``. The live path instead delivered a
        TRIGGER with ``qty 0`` printed on it -- a trade the strategy does not have.

        The four numbers stay READABLE, in the detail line, because the trader can legitimately
        ask why his screen went quiet on a stock that crossed; they do not stay in the entry
        FIELDS, because those are what the alert machinery reads as "there is a position here".
        Refused rather than exited: the day is over for this symbol and
        :meth:`_evaluate`'s own guard keeps it that way for the rest of the session.

        **It returns through :meth:`_monotonic`** (REVIEW_14 **H3**). The M21 fix returned this
        state DIRECTLY, which made it the only transition in the screener that could walk
        BACKWARDS along :data:`PHASE_RANK`. Measured on BOSCHLTD 2021-05-20 with two ordinary
        late candles -- CONTEXT 4.4's normal case, no vendor revision: at 13:30 ``qty == 1`` and
        the trader was sent a TRIGGER with all four numbers; at 13:45 the late bars landed,
        ``qty`` went to 0, and the state became a numberless ``refused`` row with **no alert, no
        ALERT_FAILURE and no phase-regression record**. The position was unmanaged and 15:15
        would not have squared it off -- verbatim the sentence :meth:`_alerts_for` exists to
        shout for REVIEW_13 M5. CONTEXT 3.4-2 consumes the stock-day at the first cross, so a
        re-evaluation that unwinds a DELIVERED trade is a state this strategy does not have: the
        earlier state stands and the disagreement is recorded.
        """
        risk = int(entry.risk_paise)
        detail = (
            f"NO TRADE, day consumed: per-share risk {rupees(risk)} exceeds the whole trade "
            f"risk {rupees(self.risk_per_trade_paise)}, so floor(risk / per-share risk) = 0 "
            f"shares (CONTEXT 3.5). The cross at {rupees(int(entry.entry_paise))} "
            f"(stop {rupees(int(entry.stop_paise))}, target "
            f"{rupees(int(entry.target_paise))}) still CONSUMED the stock-day (CONTEXT 3.4-2)"
        )
        if previous.refusal != REFUSAL_QTY_ZERO:
            # "consumed + LOGGED", in the recording rather than only on a screen nobody kept.
            self.recording.record_event(
                "qty-zero-unsizable", at=boundary, symbol=common["symbol"],
                entry_paise=int(entry.entry_paise), stop_paise=int(entry.stop_paise),
                target_paise=int(entry.target_paise), per_share_risk_paise=risk,
                risk_per_trade_paise=self.risk_per_trade_paise, detail=detail,
            )
        return self._monotonic(
            SymbolState(
                phase=PHASE_REFUSED, detail=detail, refusal=REFUSAL_QTY_ZERO, qty=0, **common
            ),
            previous,
        )

    def _monotonic(self, after: SymbolState, previous: SymbolState) -> SymbolState:
        """Refuse a state that walks BACKWARDS along :data:`PHASE_RANK` (REVIEW_13 M3).

        CONTEXT 3.4-2: *"the first qualifying cross CONSUMES the stock-day ... no re-entry after
        any exit."* A vendor revision that turns an EXITED symbol back into IN-TRADE, or a
        TRIGGERED one back into ARMED, is not a correction -- it is a state this strategy does
        not have, and the alert machinery downstream then had to deal with it (the demonstrated
        cost: the only exit the trader received said stop-loss while the screener's own final
        state said target).

        The regression is REFUSED and RECORDED, never absorbed: the earlier, further-along state
        stands, and the recording carries the event so the morning after can see that the feed
        contradicted itself.

        The rank is read from the state's CONTENT (:func:`_reached_rank`) rather than from its
        phase LABEL, because ``skipped`` is a sweep outcome laid over a real state: a symbol
        that is in trade and missed one poll shows ``skipped`` while still carrying its entry,
        and reading the label alone would let the ladder be reset by a single missed fetch.
        """
        was, now = _reached_rank(previous), _reached_rank(after)
        if now >= was:
            return after
        self.recording.record_event(
            "phase-regression-refused", at=self.clock.now(), symbol=after.symbol,
            was=previous.phase, proposed=after.phase,
            detail=(
                f"{after.symbol}: the re-evaluation reads {after.phase!r} after {previous.phase!r}. "
                "CONTEXT 3.4-2 consumes the stock-day at the first cross and allows no re-entry "
                "after an exit, so the earlier state stands and the feed's disagreement is "
                "recorded rather than acted on."
            ),
        )
        return previous

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
        """The day's 15-minute bars, for READING one candle's close. Never for a decision.

        **REVIEW_13 M25.** The import used to be function-local, and there was no reason for it
        to be -- ``aggregate`` imports nothing from this package, and this module already imported
        ``Bar`` from it at the top. A local import in a language with module-level ones reads as
        a circular-import workaround, and here it hid a real fact: the live layer DOES call the
        aggregator directly, on the evaluation path, at every square-off. It is at the top now,
        where the forbidden-direct-call tripwire in ``tests/test_live_replay_invariant.py`` can
        see it -- and that tripwire is widened to the whole module, so what is allowed here and
        what is not is pinned rather than asserted.

        What is allowed: the CANDLE MATHS. ``in_session_bars`` and ``aggregate_15min`` are pure
        functions over bars and are the SAME two the backtester's pipeline uses, so calling them
        here cannot make the two halves disagree -- it is the one-engine law being kept, not
        broken. What is forbidden, and what the tripwire refuses: ``day_profile``, ``gate_day``
        and ``evaluate_day``, the three that DECIDE. Every decision on this path goes through
        :meth:`acumen.signal_engine.SignalPipeline.evaluate`, which is the backtester's own call.
        """
        session, _dropped = in_session_bars(self.bars.get(symbol, ()))
        return aggregate_15min(session) if session else ()

    # --- alerts -------------------------------------------------------------------

    def _alerts_for(
        self, after: SymbolState, stock_day: StockDay, boundary: datetime
    ) -> list[RecordedAlert]:
        """The alerts THIS STATE warrants -- derived from the state, never from the transition.

        **REVIEW_13 B7 / B9 / M3 / M6 / M11.** The old rule fired on a transition INTO a phase,
        and the TRIGGERED phase is only ever entered on the one boundary where
        ``entry.close_stamp == boundary``. So any of CONTEXT 4.4's own normal degradations at
        that boundary -- a failed skip-and-repoll, the hard deadline, a late vendor candle --
        destroyed the one alert the morning exists to deliver, permanently and silently: the
        dashboard still showed the position and the bell never rang. ARMED and EXITED
        self-healed; TRIGGERED, the one with the four numbers on it, did not.

        Stating the alerts as a function of the CURRENT state makes every one of them
        self-healing: whatever was missed at 11:30 is derived again at 11:45, and the dedup key
        below is what stops the same answer being sent twice. A feed that dies across an entry
        boundary and heals now produces the alert it owes instead of a position the trader was
        never told about (M11).
        """
        out: list[RecordedAlert] = []
        symbol = after.symbol
        entry = stock_day.signal.entry if stock_day.signal is not None else None

        if after.phase == PHASE_REFUSED and after.entry_paise is not None:
            # M5: the battery refused the day while a position is open. Loud, by name.
            out.append(self._alert(ALERT_FAILURE, symbol, boundary, {
                "detail": (
                    f"{symbol}: {after.detail}. It is NOT being watched and 15:15 will not "
                    "square it off -- the position is unmanaged by this tool."
                ),
                "refusal": after.refusal, "entry_paise": after.entry_paise,
                "stop_paise": after.stop_paise, "target_paise": after.target_paise,
                "qty": after.qty, "side": after.side,
            }))
        elif after.phase == PHASE_ARMED:
            out.append(self._alert(ALERT_ARMED, symbol, boundary, {
                "side": after.side, "poc_paise": _num(after.poc_paise),
                "reference_paise": after.reference_paise, "bias": after.bias,
            }))
        elif after.entry_paise is not None:
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
                "entry_stamp": None if entry is None else entry.close_stamp.isoformat(),
                "gap_entry": None if entry is None else entry.gap_entry,
            }))
        if after.phase == PHASE_EXITED:
            kind = ALERT_SQUARE_OFF if after.exit_kind == sig.EXIT_SQUARE_OFF else ALERT_EXIT
            out.append(self._alert(kind, symbol, boundary, {
                "exit_kind": after.exit_kind, "exit_paise": after.exit_paise,
                "entry_paise": after.entry_paise, "side": after.side, "qty": after.qty,
            }))
        return [alert for alert in out if self._deliver(alert)]

    def _alert(self, kind: str, symbol: str, at: datetime, payload: dict) -> RecordedAlert:
        """Build the alert this state warrants, WITH the states that qualify its numbers.

        **REVIEW_13B Q1, and the architect's chunk-14 instruction with it.** An alert is the
        surface the bell rings on, the surface that gets forwarded, and the only surface a
        trader reads at 11:31 -- so everything that qualifies its numbers has to be ON it and
        not merely beside it on a screen. Three things travel here:

        * CONTEXT 4.7's disclosure, unchanged;
        * the AGE of the window behind the price -- ``bars``, ``last_bar_stamp``,
          ``data_behind_minutes`` and ``stale`` -- on every alert, always, so that
          :func:`unvouched_price` can tell "fresh" from "nobody said" rather than having to
          assume;
        * the STATES, :data:`ALERT_STATES`, as first-class payload data: ``stale`` beyond the
          clamp (Q1) and B357's ``POC provisional / incomplete window`` (the architect's B3
          ruling, whose own words are *"on the state, on both dashboards and on every alert the
          symbol produces"* -- it used to reach ARMED and TRIGGER only, which left the exit
          alert of a provisional-POC day carrying a stop and a target derived from that POC with
          nothing on it to say so).
        """
        body = dict(payload)
        body["dry_run"] = self.dry_run
        # REVIEW_14 H1: the POSTURE travels on the alert, exactly as `dry_run` does and for the
        # same reason. A recording says which mode it was made in; a single alert forwarded to a
        # phone said only "11:30", and a replayed 2020 trade was then indistinguishable from
        # today's. `posture` is `live` or `settled` -- the screener's own word for it, not a
        # second flag that could disagree with the one the battery is chosen by.
        body["mode"] = self.posture
        if self.disclosure:
            # CONTEXT 4.7: "Every live alert carries: 'live feed, not yet verified against the
            # exchange's end-of-day record.'" On the alert itself, not only on the screen it was
            # read from -- an alert is forwarded, screenshotted and quoted, and the sentence has
            # to travel with it.
            body["disclosure"] = self.disclosure
        state = self.states.get(symbol)
        states: list[str] = []
        if state is not None:
            stale, behind = data_age(state, at)
            body["bars"] = state.minute_count
            body["last_bar_stamp"] = (
                None if state.last_stamp is None else state.last_stamp.isoformat()
            )
            body["data_behind_minutes"] = behind
            body["stale"] = stale
            if stale:
                states.append(MARKER_STALE)
                body["stale_note"] = stale_note(behind)
            if state.poc_provisional:
                states.append(MARKER_POC_PROVISIONAL)
                body["poc_note"] = POC_PROVISIONAL
                body["poc_missing_minutes"] = state.poc_missing_minutes
        if states:
            body["alert_states"] = [marker for marker in ALERT_STATES if marker in states]
        return RecordedAlert(kind=kind, symbol=symbol, at=at, payload=body)

    @staticmethod
    def _alert_key(alert: RecordedAlert) -> tuple[str, str, str]:
        """``(symbol, kind, identity)`` -- the dedup key, re-cut (REVIEW_13 B334 / B9 / M6).

        ``(symbol, kind)`` was right for the case CONTEXT 4.4 worries about -- the same trigger
        re-derived at seventeen boundaries must be sent once -- and wrong for every case where
        the tool has since changed its mind. It swallowed a corrected ARMED alert, the second
        failure banner of the day, the real exit after a phase walked backwards, and a TRIGGER
        whose entry price had moved. **The third element is the identity of the STATE being
        alerted about**, anchored on the entry stamp for a trigger and on the four numbers that
        stamp decides, so that:

        * the same answer re-derived at every later boundary is ONE alert, as before;
        * a DIFFERENT answer -- the entry that healed one sweep later from 2001.00/TP 2007.00/qty
          500 to 2003.00/TP 2015.00/qty 250 -- is a second, delivered alert marked as a
          correction, not silence;
        * a second outage alerts (the failure key carries its own sweep), where
          ``("-", "failure")`` was spent by the first one for the whole session.
        """
        payload = alert.payload
        if alert.kind == ALERT_TRIGGER:
            identity = "|".join(str(payload.get(name)) for name in (
                "entry_stamp", "entry_paise", "stop_paise", "target_paise", "qty",
            ))
        elif alert.kind == ALERT_ARMED:
            identity = "|".join(str(payload.get(name)) for name in (
                "side", "poc_paise", "reference_paise",
            ))
        elif alert.kind in (ALERT_EXIT, ALERT_SQUARE_OFF):
            identity = "|".join(str(payload.get(name)) for name in (
                "exit_kind", "exit_paise", "qty",
            ))
        else:
            identity = str(payload.get("sweep") or payload.get("detail", ""))
        return (alert.symbol, alert.kind, identity)

    def _deliver(self, alert: RecordedAlert) -> bool:
        """Record and deliver an alert the state warrants. False when it says nothing new.

        Three things happen here in a fixed order, and the order is the fix (REVIEW_13 B9, M23):

        1. an alert whose identity has already been delivered is a byte-identical re-derivation
           of the same answer, and is neither recorded nor sent -- that is the property CONTEXT
           4.4's "no duplicate alerts" asks for, and the ONLY thing suppressed here;
        2. an alert that SUPERSEDES an earlier one of the same kind is marked as a correction,
           carrying what it replaces, and is **recorded before it is delivered** -- the old code
           returned False above ``record_alert``, so a superseded trigger left no trace anywhere
           and the recording could not show that anything had changed;
        3. the dedup set reaches DISK before any sink fires. It used to be persisted at the end
           of the sweep while the sinks fired in the middle of it, so a death in between left
           ``alerts.jsonl`` holding alerts ``state.json`` did not, and even a correct resume
           re-delivered them. The window was a whole sweep -- 75-105s over 210 symbols by
           CONTEXT 4.4's own measurement, at the most failure-prone moment of the boundary.
        """
        key = self._alert_key(alert)
        if key in self.alerted:
            return False
        if self.post_session:
            # **M4.** After 15:29 nothing is tradeable (CONTEXT 3.4-2's last entry is 15:00 and
            # 3.4-5's square-off is 15:15), so an alert produced by the post-session poll is
            # information about the recording and not a signal. It is written whole -- the
            # payload the trader would have received, so the morning-after can see exactly what
            # was withheld and why -- and no sink is fired. Checked AFTER the dedup test above,
            # so a trigger already delivered at 13:30 and re-derived at 15:30 stays silent
            # rather than generating a withheld-alert line for an alert that really did go.
            self.recording.record_event(
                EVENT_POST_SESSION_ALERT, at=alert.at, symbol=alert.symbol,
                alert_kind=alert.kind, payload=dict(alert.payload),
                detail=(
                    f"{alert.symbol} {alert.kind}: the post-session poll produced this alert "
                    f"at {alert.at.strftime('%H:%M')}, after CONTEXT 3.4's last actionable "
                    "moment (15:15 square-off). It is recorded in full and was delivered to NO "
                    "sink -- not the screen, not the bell, not the phone."
                ),
            )
            return False
        superseded = [
            prior for prior in self.alerted
            if prior[0] == alert.symbol and prior[1] == alert.kind
        ]
        if superseded:
            alert = RecordedAlert(
                kind=alert.kind, symbol=alert.symbol, at=alert.at,
                payload=dict(
                    alert.payload,
                    correction=True,
                    supersedes=sorted(prior[2] for prior in superseded),
                ),
            )
        self.recording.record_alert(alert)
        self.alerted.add(key)
        self.persist()
        for sink in self.sinks:
            try:
                sink.deliver(alert)
            except Exception as exc:
                # REVIEW_14 M19's second surface. `TelegramSink.deliver` never raises by design
                # -- that is rule 3 of its own module doc -- and chunk 14 still made this the
                # fourth participant in a bare loop, the only one doing network I/O. An
                # exception here ends the SWEEP, so one sink costs the other 203 symbols their
                # boundary. The alert is already recorded and already dedup-keyed on disk above,
                # so a sink that dies loses exactly its own delivery.
                self.recording.record_event(
                    EVENT_SINK_FAILED, at=alert.at, symbol=alert.symbol,
                    sink=type(sink).__name__, error=type(exc).__name__,
                    detail=(
                        f"{type(sink).__name__} raised {type(exc).__name__}: {exc} on "
                        f"{alert.symbol} {alert.kind}. The alert is recorded and on every other "
                        "sink; only this one did not receive it."
                    ),
                )
        return True

    def _evaluation_failed(self, symbol: str, boundary: datetime, exc: Exception) -> None:
        """One symbol's evaluation raised. Record it BY NAME, and mark it (REVIEW_14 M19).

        Recorded per symbol per boundary rather than once per day, because a feed that poisons
        one symbol at 11:15 and heals at 11:30 is a different morning from one that poisons it
        all day, and the morning-after cannot tell them apart from a single line.

        The symbol is marked SKIPPED -- the same phase a symbol that never answered gets, since
        the consequence is identical (it keeps its previous state and is not being watched) --
        but with its OWN detail: *"missed its data window"* would be a lie about a symbol whose
        data arrived and could not be read.
        """
        state = self.states[symbol]
        if state.phase not in (PHASE_REFUSED, PHASE_EXITED):
            self.states[symbol] = replace(
                state, phase=PHASE_SKIPPED,
                detail=(
                    f"the {boundary.strftime('%H:%M')} evaluation raised "
                    f"{type(exc).__name__}; kept its previous state and NOT being watched"
                ),
            )
        self.recording.record_event(
            EVENT_EVALUATION_FAILED, at=boundary, symbol=symbol,
            sweep=boundary.strftime("%H:%M"), error=type(exc).__name__,
            detail=(
                f"{symbol}: the evaluation raised {type(exc).__name__}: {exc}. The symbol keeps "
                "its previous state and is SKIPPED for this boundary (CONTEXT 4.4); the rest of "
                "the sweep continues."
            ),
        )

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
        if report.unevaluated:
            # NAMED, not counted (REVIEW_14 M19): an evaluation that raises is a defect in the
            # data or in this tool, not a quiet feed, and the operator has to know WHICH stock
            # stopped being watched in order to manage it by hand.
            parts.append(
                f"{len(report.unevaluated)} symbol(s) could NOT be evaluated: "
                + ", ".join(sorted(report.unevaluated))
            )
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
        """Write the intraday state. Called after every sweep AND before every alert is sent."""
        self.recording.write_state({
            "trade_date": self.day.isoformat(),
            "sweeps_done": list(self.sweeps_done),
            "banner": self.banner,
            "dry_run": self.dry_run,
            "alerted": sorted(
                _ALERT_KEY_SEP.join(part) for part in self.alerted
            ),
            "states": {symbol: state.as_dict() for symbol, state in sorted(self.states.items())},
            # CONTEXT 3.3's POC survives the crash it was pinned before. A resume that re-pinned
            # from a now-complete window would move the day's POC across a restart, which is the
            # very thing B3 exists to stop -- and a restart is exactly when the window IS more
            # complete than it was at 11:15.
            "profiles": {
                symbol: {
                    "poc_paise": str(profile.poc_paise),
                    "bar_count": profile.bar_count,
                    "window_volume": profile.window_volume,
                    "window_candles": profile.window.candles,
                    "window_name": profile.window.name,
                }
                for symbol, profile in sorted(self.profiles.items())
            },
        })

    def restore(self) -> bool:
        """Reload the intraday state from the recording. True when there was one to reload.

        The BARS are not restored from ``state.json`` -- they are re-read from the recording's
        own candle files, which is the whole reason those files are append-only. A resumed
        screener therefore continues from the same bytes it had, not from a summary of them.

        **Everything else is restored too, which it was not** (REVIEW_13 B8): the per-symbol
        states, so a resumed screener has not forgotten that a symbol is IN TRADE; the pinned
        POCs, so CONTEXT 3.3's fixed POC survives a restart; and the duplicate stamps the
        recording witnessed, so a day gate 2 refused before the crash stays refused after it.
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
            tuple(part.split(_ALERT_KEY_SEP, 2))  # type: ignore[misc]
            for part in state.get("alerted", ())
            if part.count(_ALERT_KEY_SEP) >= 2
        }
        for symbol, payload in (state.get("states") or {}).items():
            if symbol in self.states:
                self.states[symbol] = SymbolState.from_dict(payload)
        for symbol, payload in (state.get("profiles") or {}).items():
            self.profiles[symbol] = DayProfile(
                day=self.day,
                window=ProfileWindow(
                    name=str(payload.get("window_name", SPEC_WINDOW.name)),
                    candles=int(payload.get("window_candles", SPEC_WINDOW.candles)),
                ),
                reason=POC_OK,
                poc_paise=Fraction(str(payload["poc_paise"])),
                bar_count=int(payload.get("bar_count", 0)),
                window_volume=int(payload.get("window_volume", 0)),
            )
        for symbol in self.symbols:
            self.bars[symbol] = self.recording.bars(symbol, self.day)
            twins = self.recording.duplicate_bars(symbol, self.day)
            if twins:
                self.duplicate_bars[symbol] = twins
        self.recording.record_event(
            "resumed", at=self.clock.now(),
            detail=f"{len(self.sweeps_done)} sweep(s) already done; "
                   f"{sum(1 for s in self.bars.values() if s)} symbol(s) restored from candles; "
                   f"{len(self.profiles)} pinned POC(s); "
                   f"{len(self.alerted)} alert(s) already delivered",
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


def _reached_rank(state: SymbolState) -> int:
    """How far along :data:`PHASE_RANK` this state has actually got, read from its CONTENT.

    An exit price means the day is over; an entry price means the stock-day is CONSUMED
    (CONTEXT 3.4-2) whatever the sweep is currently able to fetch; ``armed`` is a live reading
    of the state machine. Content rather than label, so a ``skipped`` sweep -- which keeps every
    other field and only relabels the phase -- cannot reset the ladder.

    **CONTEXT 3.5's ``qty == 0`` day stands exactly where an ARMED day stands** (REVIEW_14 H3).
    The ladder measures how far a POSITION got, and on an unsizable cross nothing was bought:
    the day is consumed and terminal, but there is no position, so it is not further along than
    a day still waiting for one. That places the transition ARMED -> consumed FORWARD (which is
    what CONTEXT 3.5 asks for) and TRIGGERED -> consumed BACKWARD, which is the hole H3 found: a
    delivered ``qty 1`` alert walked into a numberless ``refused`` row, with no alert, no
    ALERT_FAILURE and no regression record, leaving a position 15:15 would not square off.
    """
    if state.exit_kind is not None:
        return PHASE_RANK[PHASE_EXITED]
    if state.entry_paise is not None:
        return PHASE_RANK[PHASE_TRIGGERED]
    if state.refusal == REFUSAL_QTY_ZERO:
        return PHASE_RANK[PHASE_ARMED]
    if state.phase == PHASE_ARMED:
        return PHASE_RANK[PHASE_ARMED]
    return PHASE_RANK[PHASE_WAITING]


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


def whole_day_from_source(source: BarSource, symbol: str, day: date) -> tuple[StoredBar, ...]:
    """Every 1-minute bar ``source`` can serve for ``day`` -- the whole session, in one ask.

    A replay source (the minute lake, or a recording) answers a poll stamped after the close
    with the complete day, which is precisely what CONTEXT 4.6's battery needs. Never called on
    a live morning: :func:`full_day_gates` is not called there at all (CONTEXT 4.7).

    A source that replays a RECORDING hands back its duplicate stamps too. ``recording.bars``
    de-duplicates a re-polled stamp because the engines need one bar per minute; the battery
    must see the twins or it cannot refuse them, which is REVIEW_13 **B2** exactly.
    """
    bars = tuple(source.fetch(symbol, day, datetime.combine(day, SESSION_END)))
    origin = getattr(source, "recording", None)
    if bars and origin is not None:
        bars = bars + tuple(origin.duplicate_bars(symbol, day))
    return bars


def full_day_gates(
    pipeline: SignalPipeline,
    symbols: Iterable[str],
    day: date,
    *,
    source: BarSource | None = None,
) -> dict[str, DayGates]:
    """The CONTEXT 4.6 battery for ``day``, per symbol, from the WHOLE day.

    This is the backtester's own verdict, computed exactly where the backtester computes it --
    :meth:`acumen.signal_engine.SignalPipeline.gate_day` over a whole minute day. It is a
    WHOLE-DAY measurement (gate 1 folds the session's total volume against the bhavcopy), which
    is why it is computed once and handed to every boundary rather than recomputed on a growing
    prefix, where it would be wrong at every boundary but the last.

    It is available for a PAST day and not for TODAY. That asymmetry was QUESTIONS.md **Q-28**
    and CONTEXT 4.7 is the ruling on it: a live morning runs
    :func:`acumen.signal_engine.oracle_free_battery` per sweep instead, and this function is not
    called at all for ``mode="live"``.

    **The stored lake is not the only whole day there is** (REVIEW_13 **M22**). A recording of a
    live morning holds a session the lake will not hold until that night's backfill, and
    replaying it was the first thing chunk 14's parity harness had to do. With no battery the
    screener handed ``gates=None`` down to the pipeline, which computed one per boundary over a
    GROWING PREFIX and refused 15 of 17 boundaries by gate 1 -- a parity that agreed because
    both sides had refused. So when the lake cannot answer, the battery is measured over the
    whole day the SESSION'S OWN SOURCE can serve, against the published bhavcopy: which is
    CONTEXT 4.7's own next-pre-open construction (:func:`acumen.live_refresh.verify_prior_
    recording`), applied one step earlier. The duplicate stamps of a recording are folded in
    with it, for the reason REVIEW_13 B2 gives -- a battery that cannot see a twin cannot refuse
    it.
    """
    out: dict[str, DayGates] = {}
    for symbol in symbols:
        minutes: tuple[StoredBar, ...] = tuple(pipeline.minute_store.minutes(symbol, day))
        if not minutes and source is not None:
            try:
                minutes = whole_day_from_source(source, symbol, day)
            except Exception:
                # A source that cannot answer here is not an error: ``--preflight-only`` runs on
                # a source that REFUSES to be used at all, and a bar source is allowed to fail
                # (CONTEXT 4.3 calls a transient failure normal). The symbol simply has no
                # whole-day battery, which :meth:`LiveScreener._evaluate` then refuses BY NAME
                # rather than by gating a prefix (REVIEW_13 M22).
                minutes = ()
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
    calendar_source: str | None = None,
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
    if live and LIVE_BLOCKING_QUESTIONS:
        raise BlockedByOpenQuestion(
            "A class-A question stands between this morning and an answer anyone may rely on, "
            "so the screener refuses to start rather than produce one (CLAUDE.md rule 1):\n\n"
            + "\n\n".join(f"{name}: {text}" for name, text in LIVE_BLOCKING_QUESTIONS)
        )
    chosen_master, master_reason = _master_for(
        mode, day=day, recording=recording, master_file=master_file or None
    )
    if live:
        # The CHEAPEST prerequisite, checked first and by name. Q-29 makes the day's own dump
        # structural, and an operator whose pre-open fetch did not land should read THAT rather
        # than whichever of the morning's other inputs happens to be resolved next.
        _require_day_master(chosen_master, cache_dir=cache_dir)
    seed = seed_from if seed_from is not None else day - timedelta(days=SEED_LOOKBACK_DAYS)
    if (live and calendar is None) or (
        calendar is not None and calendar.trading_days is None
    ):
        # REVIEW_13 B6: the derived calendar cannot answer for TODAY and never will be able to.
        #
        # REVIEW_14 **B3**, the second clause. A PUBLISHED holiday master carries no explicit
        # trading-day set -- it is a list of holidays and a weekday rule -- and
        # `backtest.build_runner` refuses exactly that (there is nothing for CONTEXT 7-E2's
        # non-standard sessions to be subtracted from). `--refresh` ALWAYS supplies one, because
        # REVIEW_13 M17 made the refresh's own cross-checked calendar the calendar the session
        # runs and records; so the documented 08:45 command reached the refusal and the operator
        # read "the screener cannot start" AFTER the pre-open had already touched the stores.
        # The published master is now COMPOSED here -- the C5 division of labour, published for
        # today and the store's own scan for the history behind it -- instead of being handed on
        # raw. The composition is the same function `_live_calendar` builds from, so a supplied
        # master and a fetched one produce the same calendar.
        calendar = _live_calendar(
            day=day, first_day=seed - timedelta(days=bt.CALENDAR_LEAD_DAYS),
            data_dir=data_dir, cache_dir=cache_dir, allow_network=allow_network,
            published=calendar,
        )
        calendar_source = CALENDAR_PUBLISHED

    try:
        runner, master_path, _ca = bt.build_runner(
            symbols, day, day, data_dir=data_dir, cache_dir=cache_dir,
            seed_from=seed,
            label="live-screener", allow_network=allow_network,
            master_file=chosen_master, calendar=calendar,
        )
    except bt.BacktestError as exc:
        # REVIEW_13 M24: the module's error contract does not leak. A caller that catches
        # ScreenerError catches every way this function refuses, including the day's-own-master
        # prerequisite -- which is the refusal the STOP-rule test now asserts by equality.
        if chosen_master is not None and "instrument master" in str(exc):
            raise ScreenerError(f"{MASTER_MISSING_REFUSAL}. {exc}") from exc
        raise ScreenerError(str(exc)) from exc

    supplied = tuple(symbol.strip().upper() for symbol in symbols)
    wanted, excluded = _screened_universe(
        supplied, live=live, data_dir=data_dir, residual=runner.residual
    )
    if live and not wanted:
        raise ScreenerError(
            "no SETTLED symbol left to screen. CONTEXT 4.7 (QUESTIONS.md Q-30, architect "
            "08-Aug-2026) screens the settled universe only, and every symbol asked for is "
            "quarantined or absent from the chunk-5B disclosed-residual register: "
            + ", ".join(f"{symbol} ({why})" for symbol, why in excluded)
        )
    biases: dict[str, DailyBias] = {}
    for symbol in wanted:
        series, _reason = runner.bias_map(symbol)
        if day in series:
            biases[symbol] = series[day]

    # CONTEXT 4.7: a live morning has no stored day to gate and no oracle to gate it against, so
    # the settled battery is not computed at all and the oracle-free one runs per sweep. A
    # REPLAY takes it from the lake, and -- REVIEW_13 M22 -- from the session's own source for a
    # day the lake does not hold yet, which is every recording of a live morning.
    gates = {} if live else full_day_gates(runner.pipeline, wanted, day, source=source)
    governing_calendar = calendar if calendar is not None else runner.calendar
    recording.open_session(_manifest(
        runner=runner, day=day, symbols=wanted, master_path=master_path,
        mode=mode, dry_run=dry_run,
        calendar=governing_calendar,
        # REVIEW_13 M17/F2: the source is what ACTUALLY governed, never a parameter default. A
        # replay is judged by the store-derived calendar the backtester itself uses, and saying
        # "published" beside a `calendar_source_field` of "derived" was the manifest
        # contradicting itself in one block.
        calendar_source=(
            calendar_source if calendar_source is not None
            else (CALENDAR_PUBLISHED if live else CALENDAR_STORE_SCAN)
        ),
        excluded=excluded,
        master_reason=master_reason,
        seed_from=seed,
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
        excluded=excluded,
        master_reason=master_reason,
    )


def _require_day_master(filename: str | None, *, cache_dir: Path | None) -> Path:
    """THE DAY'S OWN dump must be on disk before a live morning goes any further (Q-29).

    Checked here rather than only inside :func:`acumen.backtest.named_master` so that the
    refusal is the SCREENER's own -- :data:`MASTER_MISSING_REFUSAL`, asserted by equality in the
    safety suite -- and so that it comes first, before the calendar, the factor tables or the
    32 MB the loader would otherwise read. The file is not opened here; ``build_runner`` still
    loads and hashes it, which is what puts its sha256 in the recording.

    **Both remedies name a command that runs on the operator's own tree (REVIEW_15B R1).** They
    used to read ``python -m acumen.run_screener --mode live ...`` and ``python -m
    acumen.instrument_master --allow-network``, which need an editable install this machine does
    not have and so answer ``No module named 'acumen'`` at 09:00, on the morning's own refusal --
    REVIEW_14 **B3**'s defect, at the latest possible moment to discover it.
    :data:`SCREENER_LAUNCHER` and :data:`acumen.backtest.MASTER_LAUNCHER` are what a bare clone
    really runs, and the flags are unchanged: each launcher forwards to the same ``main``.
    """
    from .config import MASTER_CACHE_SUBDIR, load_config

    assert filename is not None  # a live mode always resolves to the day's own dump
    cache = Path(cache_dir) if cache_dir is not None else load_config(
        include_env=False
    ).path("cache_root")
    path = cache / MASTER_CACHE_SUBDIR / filename
    if not path.is_file():
        raise ScreenerError(
            f"{MASTER_MISSING_REFUSAL}. It is not at {path}. Run the pre-open refresh "
            f"(`python {SCREENER_LAUNCHER} --mode live --day <today> --refresh "
            "--allow-network`), or fetch the dump directly "
            f"(`python {bt.MASTER_LAUNCHER} --allow-network`)."
        )
    return path


def _live_calendar(
    *, day: date, first_day: date, data_dir: Path | None, cache_dir: Path | None,
    allow_network: bool, published: TradingCalendar | None = None,
) -> TradingCalendar:
    """The calendar a live morning runs on -- the PUBLISHED master, over the store's history.

    REVIEW_13 **B6**: ``build_runner`` derived its calendar from the daily store, which refuses
    any range holding a date it has never attempted (Q-3 safeguard 1). On a live morning that
    date is TODAY, whose bhavcopy cannot exist during today, and Q-19's guard stops the pre-open
    top-up strictly before it -- so the mode failed to start on every real morning, exit 1.
    Reproduced by this chunk's review against the real stores; the same command for a day the
    store covers started perfectly, which isolated the cause exactly.

    The holiday master is DAY-CACHED (CONTEXT 4.1's own courtesy rule), so an offline morning
    runs on the file the pre-open refresh already pulled and nothing reaches out here.

    ``published`` is the master the caller ALREADY holds -- the one ``morning_refresh`` fetched
    and cross-checked against the store scan an instant earlier (REVIEW_13 M17's C5 duty). It is
    composed rather than re-fetched, so the calendar the session runs is byte-for-byte the one
    the preflight reported on, and the endpoint is not asked twice in one morning (CONTEXT 4.1).
    """
    from . import calendar as cal
    from .config import load_config
    from .daily_store import DailyStore

    config = load_config(include_env=False)
    data = Path(data_dir) if data_dir is not None else config.path("data_root")
    cache = Path(cache_dir) if cache_dir is not None else config.path("cache_root")
    try:
        published = published if published is not None else cal.fetch_calendar(
            cache_dir=cache, today=day, allow_network=allow_network
        )
    except Exception as exc:
        raise ScreenerError(
            f"a LIVE morning takes its calendar from the PUBLISHED NSE holiday master (CONTEXT "
            f"4.7 / QUESTIONS.md C5) and it is not available: {type(exc).__name__}: {exc}. The "
            "store-derived calendar cannot answer for today by construction, so there is no "
            "fallback -- run the pre-open refresh with --allow-network."
        ) from exc
    try:
        return cal.live_trading_calendar(
            published, store=DailyStore.at(data / "daily_store"),
            first_day=first_day, day=day,
        )
    except Exception as exc:
        raise ScreenerError(
            f"the live calendar cannot be built for {day.isoformat()}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def _screened_universe(
    symbols: Sequence[str], *, live: bool, data_dir: Path | None, residual: Mapping
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """Which symbols a session screens, and which it refuses to -- CONTEXT 4.7 / Q-30.

    The architect's 08-Aug-2026 ruling on REVIEW_13, option (a): *"a live morning screens the
    204 SETTLED symbols only -- the screener alerts on what the backtester validated; the 6
    quarantined (APLAPOLLO, ASTRAL, IEX, NTPC, UPL, VBL) are never screened and the startup
    banner names them excluded."*

    REVIEW_13 **M2** measured what the alternative cost: a live morning swept the raw F&O list,
    all six quarantined symbols included, and no live module read the settled register at all.
    The backtester walked ZERO of their days -- 0 rows of 495,312 -- while their own gate-1
    refusal rate is 22.1%-47.2% (32.8% pooled) against a disclosed 0.5229%. The sentence on
    every live alert was calibrated to a population that excluded exactly the symbols most
    likely to break it.

    The register is the chunk-5B disclosed-residual ledger, which CONTEXT 4.6 already makes a
    chunk-9 duty to read; ``runner.residual`` is the copy ``build_runner`` has already loaded,
    so this decides nothing on its own and reads no second source of truth. A symbol with NO row
    at all is excluded too, and named: it is a symbol the backtester never walked, which is the
    ruling's own test.

    A REPLAY screens whatever it is asked to. A past day has its bhavcopy and its verdict; a
    quarantined symbol replayed deliberately is a diagnostic, not an alert anybody trades on.
    """
    supplied = tuple(dict.fromkeys(symbol.strip().upper() for symbol in symbols))
    if not live:
        return supplied, ()
    del data_dir  # the register travels on the runner; there is no second lookup
    screened: list[str] = []
    excluded: list[tuple[str, str]] = []
    for symbol in supplied:
        entry = residual.get(symbol)
        if entry is None:
            excluded.append((symbol, "not in the chunk-5B register: the backtester never walked it"))
        elif str(entry.status).strip().lower() != "settled":
            why = entry.residual_reason.strip() or (
                f"gate 1P proves {entry.gate1p_pass:,} of {entry.gate1p_total:,} stored days; "
                "the chunk-9B run walked none of them"
            )
            excluded.append((symbol, f"{entry.status} (CONTEXT 4.6) -- {why}"))
        else:
            screened.append(symbol)
    return tuple(screened), tuple(excluded)


def day_master_filename(day: date) -> str:
    """The filename of ``day``'s OWN instrument-master dump (CONTEXT 4.7 / QUESTIONS.md Q-29).

    One place, because three modules need to agree on it: the pre-open refresh that fetches it,
    the screener that runs on it, and the verification that replays yesterday under the one
    yesterday recorded. It is the same name :func:`acumen.instrument_master.master_cache_path`
    writes, taken from that function rather than spelled again here.
    """
    from .instrument_master import master_cache_path

    return master_cache_path(".", day).name


def _master_for(
    mode: str, *, day: date, recording: LiveRecording, master_file: str | None = None
) -> tuple[str | None, str]:
    """Which instrument master governs, and WHY. ``None`` means the Q-20 pin (CONTEXT 4.7).

    Live: the day's own dump, always, and its absence is a refusal rather than a fallback.
    Replay: the recording's own pin when the recording already names one -- which is what makes
    section 6's guarantee hold PER DAY -- and otherwise the config pin, which is the law for
    every historical day.

    **``master_file`` is FENCED to the two cases CONTEXT 4.7 licenses** (REVIEW_13 **M9**). It
    used to short-circuit this resolution entirely -- ``master_file or _master_for(...)`` -- for
    ``mode="live"`` too, so a live session could run on the Q-20 pin while the preflight, which
    derived its provenance line from the MODE rather than from the FILE, printed "THIS DAY'S OWN
    dump". B344's refusal had an unguarded bypass straight through it. A live caller may now
    name only the day's own dump; anything else is refused by name.

    The REASON is returned beside the filename for the same finding's other half: the sentence
    the operator reads is now derived from the file that was actually resolved.
    """
    if mode == "live":
        wanted = day_master_filename(day)
        if master_file is not None and master_file != wanted:
            raise ScreenerError(
                f"a LIVE morning may run only on THE DAY'S OWN instrument master "
                f"({wanted}); {master_file!r} was named instead. CONTEXT 4.7 / QUESTIONS.md "
                "Q-29 licenses master_file for exactly two things -- this morning's own "
                "pre-open dump, and the master a live RECORDING was made under when that "
                "recording is replayed -- and the Q-20 pin governs the historical ledger, "
                "never a live session."
            )
        return wanted, (
            "THIS DAY'S OWN dump (CONTEXT 4.7 / Q-29 -- the trader's chart as of this morning)"
        )
    if master_file is not None:
        return master_file, (
            f"{master_file}, named explicitly by the replay's caller (CONTEXT 4.7: the master "
            "a recording was made under)"
        )
    if recording.exists():
        recorded = recording.read_manifest().get("master_file")
        if recorded:
            return str(recorded), (
                f"{recorded}, the RECORDING'S OWN pin -- a day is replayed under the ticks it "
                "ran on (CONTEXT 4.7 / Q-29), so section 6 holds per day"
            )
    return None, "the Q-20 config pin, which is the law for every historical day"


def _manifest(
    *, runner, day: date, symbols: Sequence[str], master_path: Path, mode: str,
    dry_run: bool, calendar: TradingCalendar, calendar_source: str,
    excluded: Sequence[tuple[str, str]] = (), master_reason: str = "",
    seed_from: date | None = None,
) -> dict:
    """Everything the replay needs to know about the machine this day ran on."""
    spec = runner.spec
    return {
        "trade_date": day.isoformat(),
        "mode": mode,
        "dry_run": dry_run,
        "spec_version": bt.SPEC_VERSION,
        # CONTEXT 4.7 / Q-30: which symbols were NOT screened, and why. A universe six short
        # with no record of which six is a universe nobody can check (REVIEW_13 M2).
        "excluded_symbols": [
            {"symbol": symbol, "reason": reason} for symbol, reason in excluded
        ],
        "master_reason": master_reason,
        # CONTEXT 3.2's carry needs history to carry FROM (REVIEW_13 B1). Recorded so a replay
        # can prove which bias series the morning ran on.
        "seed_from": None if seed_from is None else seed_from.isoformat(),
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
    "ALERT_STATES",
    "LIVE_BLOCKING_QUESTIONS",
    "LIVE_RESIDUAL_BRACKET",
    "MARKER_POC_PROVISIONAL",
    "MARKER_STALE",
    "MASTER_MISSING_REFUSAL",
    "PHASE_RANK",
    "POC_PROVISIONAL",
    "PRICE_FIELDS",
    "REFUSAL_NO_BATTERY",
    "REFUSAL_QTY_ZERO",
    "SCREENER_LAUNCHER",
    "SEED_LOOKBACK_DAYS",
    "STALE_AFTER_MINUTES",
    "ALERT_ARMED",
    "ALERT_EXIT",
    "ALERT_FAILURE",
    "ALERT_KINDS",
    "EVENT_EVALUATION_FAILED",
    "EVENT_INTAKE_FAILED",
    "EVENT_POST_SESSION_ALERT",
    "EVENT_SINK_FAILED",
    "POLL_NO_ANSWER",
    "POLL_OK",
    "POLL_UNREADABLE",
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
    "alert_state_notes",
    "boundary_stamps",
    "build_live_screener",
    "data_age",
    "day_master_filename",
    "format_alert",
    "full_day_gates",
    "master_tick_divergence",
    "rupees",
    "stale_note",
    "unvouched_price",
    "wait_for_boundary",
    "whole_day_from_source",
]
