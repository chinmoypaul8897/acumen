"""The backtest RUNNER and its run ledger (chunk 9A). I/O allowed here.

This module is the machine that will produce the full-history backtest. It owns no strategy
rule: every decision it prints was made by a pure engine it calls.

**What one stock-day goes through, in order** (CONTEXT 4.6 + 3.2 + 3.3 + 3.4 + 3.5):

1. **CONTEXT 7-E2** -- a date whose stored candles lie wholly outside 09:15-15:30 is a
   NON-STANDARD session (Muhurat and the special/shortened sessions). E2 names exactly that
   detection ("candle data on a date absent from the trading calendar, or outside
   09:15-15:30"), so such a date is removed from the trading calendar BEFORE any bias pair is
   built -- it is not the previous trading day of anything -- and it is counted under its own
   reason. See :func:`scan_non_standard_sessions`.
2. **bias** -- :class:`acumen.bias_engine.BiasEngine` over the symbol's own daily candles,
   with the REAL chunk-3 factor table wired (pairwise "P in C's scale", CONTEXT 3.2) and the
   chunk-3 suppression list (demerger / Q-6 tier-2 rights). A day the bias engine cannot
   resolve is a COUNTED no-trade, never an exception.
3. **the CONTEXT 4.6 gate battery, RECOMPUTED per day** -- gate 1, gate 2 and gate 1P, by
   :meth:`acumen.signal_engine.SignalPipeline.gate_day`. There is no per-day exclusion file
   (CONTEXT 4.6's own words); both stores are local, so the gates are recomputed exactly.
4. **POC** (chunk 6), **signals** (chunk 7), **money** (chunk 8).

**One reason per day, in a fixed order.** A day can fail several ways at once. The order,
written out in full and in the order the code actually executes it (REVIEW_9A finding C4 --
the earlier version left one of its own reasons out of the chain and only mentioned it in a
parenthesis):

    CONTEXT 7-E2 non-standard session
      -> BIAS UNRESOLVABLE (:data:`REASON_BIAS_UNRESOLVED`: the calendar cannot answer for the
         date, the symbol's whole bias series could not be assembled, this particular day has
         no CONTEXT 3.2 pair inside the run's own history, or -- QUESTIONS.md Q-21 -- its
         Rule-3 minute scan met a vendor-corrupt bar on D-1, or -- Q-21(b) -- its Rule-3 scan
         asked for a D-1 that does not pass the CONTEXT 4.5/4.6 gate battery)
      -> no minutes -> gate 1 -> gate 2 -> gate 1P -> suppressed -> no bias yet (seeding)
      -> no POC -> the signal outcome

**A day's gates now gate BOTH of its jobs** (QUESTIONS.md Q-21(b), architect 03-Aug-2026).
Step 3 below has always decided whether a day may be TRADED. It now also decides whether that
day's minutes may serve the NEXT day's Rule-3 first-break scan: :func:`gated_minute_loader`
puts the same battery in front of the Rule-3 load, so a D-1 in a wrong price domain can no
longer hand the scan minutes measured on one scale to compare against daily thresholds on
another.

**And the CONTEXT 7-E2 / Q-17 drop binds that scan too** (QUESTIONS.md Q-22(a), architect
03-Aug-2026): *"Q-17's candle-level drop binds EVERY consumer of stored minute bars, the Rule-3
first-break scan included."* :func:`candles_for` filters through
:func:`acumen.aggregate.in_session_bars` before it builds a candle, so a stray stamp cannot vote
on which of P's extremes broke FIRST; the drop is counted through :class:`Rule3SessionDrops`
onto the trade day's row under the same :data:`FLAG_OUT_OF_SESSION_DROPPED` the trading path
uses. The GATES still see the whole stored day, which is the other half of the same law.

The first TWO are decided by :meth:`BacktestRunner.walk_symbol` -- it emits
:data:`REASON_E2_NON_STANDARD` and :data:`REASON_BIAS_UNRESOLVED` and nothing else. Every
reason from "no minutes" onward, that one included, is :mod:`acumen.signal_engine`'s own order
(chunk-7 decision B162); this module owns no "no minutes" reason at all. The counts therefore
PARTITION the walked days instead of double-counting them.

**The ledger is resumable, idempotent and byte-identical on a re-run.** One row per walked
symbol-day -- a priced trade or a no-trade row carrying its reason -- written through
:mod:`acumen.atomic_io` (temp file, fsync, atomic replace). A symbol's shard is written only
when that symbol is COMPLETE, so an interrupted run leaves no partial symbol behind and a
resume re-walks exactly what it lost: zero duplicates. Nothing in the ledger or the manifest
is read from a clock, so the same code over the same stores produces the same bytes.

**The tick input is PINNED, recorded and resume-checked** (QUESTIONS.md Q-20, architect
02-Aug-2026). CONTEXT 3.3 sizes the volume-profile row grid by each symbol's tick and CONTEXT
4.3 makes the instrument master a DAILY LIVE DUMP whose ticks move -- in both directions -- from
one pull to the next. So the run reads ONE pinned snapshot, named in ``config.yaml``, resolved by
:func:`pinned_master`; its filename and sha256 sit on :class:`RunSpec` and therefore inside the
spec digest, so the manifest can be traced back to the ticks that shaped its POCs and a resume
under any other master REFUSES exactly as a resume after a moved code SHA does.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from . import corp_actions as ca
from . import signal_engine as se
from . import signals as sig
from . import simulate as sim
from .aggregate import Bar, aggregate_15min, in_session_bars
from .atomic_io import atomic_write_text
from .bias import RULE_3_NO_MINUTE, BiasError, Candle
from .bias_engine import (
    RULE_MINUTES_MALFORMED,
    RULE_MINUTES_UNGATED,
    BiasEngine,
    BiasEngineError,
    DailyBias,
    MalformedMinuteBar,
    UngatedMinuteDay,
    UnusableMinuteEvidence,
)
from .calendar import CalendarError, TradingCalendar
from .config import load_config
from .daily_store import DailyStore
from .instrument_master import (
    CACHE_SUBDIR as MASTER_CACHE_SUBDIR,
    InstrumentMaster,
    InstrumentMasterError,
    load_master_file,
)
from .minute_backfill import corp_actions_for_symbol, fetch_corp_action_history
from .minute_store import MinuteStore
from .signal_engine import SignalPipeline

#: The CONTEXT.md version this runner implements. Written into every manifest, so a
#: ledger always names the law it was produced under. Moved to v1.5 on 02-Aug-2026 with
#: the Q-18 re-seal (CONTEXT 4.6 rewritten; Q-17 and Q-19 made law), and to v1.6 on
#: 03-Aug-2026 with the Q-21(a) completion of gate 2's impossible-OHLC enumeration (the
#: OPEN test), which changes which stored days are usable and therefore which rows a run
#: may walk -- so a ledger written under it must not be readable as a v1.5 ledger. Moved
#: again to v1.7 the same day with the Q-22 rulings: CONTEXT 4.6's Q-17 drop now binds the
#: Rule-3 first-break scan, which changes which BARS decide a bias and therefore what a
#: ledger row can say -- measured at 21 re-answered Rule-3 days across the span. The bump is
#: compelled by this constant's own contract ("a ledger always names the law it was produced
#: under"), exactly as the v1.6 bump was. Moved to v1.8 on 06-Aug-2026 with the trader's Round-4
#: answers: CONTEXT 3.4 is UNCHANGED (his Q44 answer confirms the rule this engine implements),
#: so this bump changes no walked row and the completed run's v1.7 manifest stays exactly as
#: true as it was -- the constant tracks the spec's version because a ledger names the law it
#: was produced under, and section 8's F1/F2 example and section 10 are what moved.
SPEC_VERSION: str = "v1.8"

#: What the manifest's ``instrument_master`` block says about itself, so a reader who has never
#: seen QUESTIONS.md Q-20 still knows why a filename is pinned rather than resolved. Verbatim on
#: every manifest; it names the ruling, not a session's reasoning.
MASTER_PIN_NOTE: str = (
    "ONE PINNED master snapshot governs the whole backtest (QUESTIONS.md Q-20, architect "
    "02-Aug-2026). CONTEXT 3.3 sizes the profile row grid by each symbol's tick and CONTEXT 4.3 "
    "makes the master a daily live dump whose ticks move in both directions; the replication "
    "target is the trader's TradingView chart, which applies the CURRENT tick to the entire "
    "history. Latest-by-filename selection is retired from the run path; a resume under any "
    "other master refuses."
)

#: The session window CONTEXT 3.1 gives NSE cash. Used ONLY by the E2 detector below.
SESSION_OPEN: time = time(9, 15)
SESSION_LAST_OPEN_STAMP: time = time(15, 29)

#: Refusal reasons this module adds in front of :mod:`acumen.signal_engine`'s own set.
REASON_E2_NON_STANDARD: str = (
    "CONTEXT 7-E2 non-standard session (stored candles outside 09:15-15:30)"
)
REASON_BIAS_UNRESOLVED: str = "bias unresolvable (CONTEXT 3.2 pair could not be assembled)"

#: Row statuses. ``evaluated`` means the day reached CONTEXT 3.4; it does NOT mean it traded.
STATUS_EVALUATED: str = "evaluated"
STATUS_REFUSED: str = "refused"

#: The settled-but-partial symbols CONTEXT 4.6 names under B149. The SYMBOLS are spec (the
#: section names them outright); their FIGURES are not, and are never typed here.
SETTLED_BUT_PARTIAL: tuple[str, ...] = ("IOC", "TATASTEEL")


def residual_caveat(register: Mapping[str, ResidualEntry]) -> str:
    """CONTEXT 4.6's chunk-9 caveat, quoted from the REGISTER'S OWN CURRENT FIGURES.

    CONTEXT 4.6 (v1.5) is explicit about where the numbers come from: *"settled-but-partial
    symbols (IOC, TATASTEEL -- B149) are quoted from the register's own current figures, which
    every manifest carries verbatim."* Before v1.5 this was a frozen string carrying the
    pre-Q-18 era's percentages; after the re-seal those percentages describe a store that no
    longer exists. The rebuilt register puts IOC at 1,024/2,436 -- **42.0%**, not the 41.9%
    the frozen sentence claimed -- so the old constant was not merely stale, it was wrong, and
    it was wrong on the manifest, which is the qualification record of a money-bearing ledger.

    Percentages are computed in :class:`~fractions.Fraction` and rounded half-even to one
    decimal, so no float ever touches a figure that goes into a manifest (CONTEXT 7-E11).

    Args:
        register: the disclosed-residual register, as loaded by
            :func:`load_residual_register`.

    Returns:
        The caveat sentence. A symbol the register does not carry is named as absent rather
        than silently dropped -- a caveat that quietly loses one of its two subjects would
        read as an all-clear.
    """
    parts: list[str] = []
    for symbol in SETTLED_BUT_PARTIAL:
        entry = register.get(symbol)
        if entry is None:
            parts.append(f"{symbol} (ABSENT from the register)")
            continue
        ratio = entry.price_proven_ratio
        if ratio is None:
            parts.append(f"{symbol} (no gate-1P denominator in the register)")
            continue
        tenths = round(ratio * 100 * 10)  # Fraction -> exact, half-even, tenths of a percent
        parts.append(f"{symbol} ({tenths // 10}.{tenths % 10}% price-proven)")
    return (
        f"{' and '.join(parts)} are settled-but-partial under B149 -- their backtests cover "
        "only part of stored history, concentrated in recent years."
    )

#: Where the chunk-5B run ledger lives, relative to ``data_root``. It is the machine-readable
#: face of the disclosed-residual register (backfill report section 3f).
RESIDUAL_LEDGER_RELPATH: str = "universe_backfill/ledger.json"

#: The rare shapes every run counts, whether or not they occur. A key that only appears when
#: the shape occurs lets silence read as coverage; a printed ZERO says "this window carries no
#: real-data witness for that branch", which is a fact about the window (REVIEW_8 finding Q1).
RARE_SHAPE_LABELS: tuple[str, ...] = (
    "gap entries",
    "qty-zero unsizable days",
    "signal-unsizable (degenerate) days",
    "both-touched candles (stop won)",
    "square-offs priced at the entry candle",
    "rule-3 tie bias days",
    "rule-3 day with no 1-minute data (carried, CONTEXT 3.2)",
    "E10 fallback reference (no 11:00-stamped candle)",
    "rule-3 day refused on a malformed 1-minute bar (QUESTIONS.md Q-21)",
    "rule-3 day refused on a battery-failing D-1 (QUESTIONS.md Q-21(b))",
    # Q-17 is the most frequent rare shape in the lake (3,100 symbol-days) and was the only
    # flag with no counter beside it, while eight rarer shapes carried zero-valued ones
    # (REVIEW_9B_FIXES R9). It counts DAYS whose row carries the flag, from either consumer.
    "day with out-of-session 1-minute bar(s) dropped (CONTEXT 7-E2 / Q-17)",
)

#: Ledger / manifest / progress file names inside a run directory.
LEDGER_NAME: str = "ledger.jsonl"
MANIFEST_NAME: str = "manifest.json"
PROGRESS_NAME: str = "progress.json"
SESSIONS_NAME: str = "sessions.json"
SHARD_DIRNAME: str = "symbols"

#: How far before the span the calendar is derived, so ``bias_pair(D)`` can reach D-1 and D-2
#: for the span's first trading day (chunk-8 used the same lead).
CALENDAR_LEAD_DAYS: int = 30


class BacktestError(RuntimeError):
    """The run cannot be assembled, or a resume was asked for on a different run."""


# --- E2: which dates are not standard sessions (PURE detector + the store scan) -------------


def is_standard_session_stamp(stamp: datetime) -> bool:
    """CONTEXT 7-E2's clock half: is this OPEN-stamped 1-minute bar inside the session? PURE."""
    return SESSION_OPEN <= stamp.time() <= SESSION_LAST_OPEN_STAMP


def scan_non_standard_sessions(
    minute_store: MinuteStore,
    symbols: Sequence[str],
    days: Sequence[date],
    *,
    progress: Callable[[str], None] | None = None,
) -> tuple[date, ...]:
    """Dates in ``days`` whose stored candles lie WHOLLY outside 09:15-15:30, oldest first.

    CONTEXT 7-E2 names this detection itself. A session is a property of the MARKET, not of a
    symbol, so the scan is over the whole run universe and a date is non-standard when at least
    one symbol stored candles for it and no symbol stored a candle inside the session window
    (the Muhurat shape: an 18:00-19:00 hour, every symbol, one date).
    """
    inside: set[date] = set()
    outside: set[date] = set()
    for symbol in symbols:
        for day in days:
            bars = minute_store.minutes(symbol, day)
            if not bars:
                continue
            if any(is_standard_session_stamp(bar.stamp) for bar in bars):
                inside.add(day)
            else:
                outside.add(day)
        if progress is not None:
            progress(f"  session scan: {symbol}")
    return tuple(sorted(outside - inside))


# --- the ledger row -------------------------------------------------------------------------


@dataclass(frozen=True)
class LedgerRow:
    """One walked symbol-day: the priced trade, or the recorded reason there is none.

    Every field is an integer, a string, a bool or ``None`` -- there is no float anywhere, so
    the JSON the ledger holds is exact (CONTEXT 7-E11). The POC is carried as
    ``poc_half_paise`` (twice the price) because a row midpoint may legally sit half a paisa
    off the tick grid (CONTEXT 3.3) and halving is the only division a reader ever needs.
    """

    symbol: str
    day: date
    status: str
    reason: str
    #: The SPECIFICS behind ``reason``, when a reason has any: the offending bar and its OHLCV,
    #: or the refusing gate and that gate's own words. It exists so ``reason`` can stay a STABLE
    #: KEY -- the manifest's ``refused_by_reason`` and :meth:`SymbolRun.counts` group on it, and
    #: a reason string that embedded a symbol, a date and a bar made every such row its own
    #: singleton key (REVIEW_9B_FIXES R9: ~210 of them on a full-history run, against a
    #: pre-arc shape that aggregated). ``None`` on every other row, and SERIALIZED ONLY WHEN
    #: SET, so a row that has no detail writes exactly the bytes it always did and no committed
    #: ledger digest moves.
    detail: str | None = None
    bias: str | None = None
    bias_rule: str | None = None
    side: str | None = None
    tie_case: bool = False
    suppressed: bool = False
    minute_count: int = 0
    gate1_passed: bool | None = None
    gate1_relieved: bool = False
    gate2_passed: bool | None = None
    gate1p_passed: bool | None = None
    poc_half_paise: int | None = None
    reference_paise: int | None = None
    reference_source: str | None = None
    outcome: str | None = None
    consumed: bool = False
    signalled: bool = False
    executed: bool = False
    gap_entry: bool = False
    entry_paise: int | None = None
    stop_paise: int | None = None
    target_paise: int | None = None
    per_share_risk_paise: int | None = None
    entry_close_stamp: datetime | None = None
    exit_kind: str | None = None
    exit_paise: int | None = None
    exit_close_stamp: datetime | None = None
    qty: int = 0
    notional_paise: int = 0
    gross_pnl_paise: int = 0
    cost_paise: int = 0
    net_pnl_paise: int = 0
    mfe_paise: int | None = None
    mae_paise: int | None = None
    flags: tuple[str, ...] = ()

    def to_json(self) -> str:
        """One canonical JSON line: sorted keys, no spaces, no clock read. Deterministic."""
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))

    def as_dict(self) -> dict:
        payload = {
            "symbol": self.symbol,
            "day": self.day.isoformat(),
            "status": self.status,
            "reason": self.reason,
            "bias": self.bias,
            "bias_rule": self.bias_rule,
            "side": self.side,
            "tie_case": self.tie_case,
            "suppressed": self.suppressed,
            "minute_count": self.minute_count,
            "gate1_passed": self.gate1_passed,
            "gate1_relieved": self.gate1_relieved,
            "gate2_passed": self.gate2_passed,
            "gate1p_passed": self.gate1p_passed,
            "poc_half_paise": self.poc_half_paise,
            "reference_paise": self.reference_paise,
            "reference_source": self.reference_source,
            "outcome": self.outcome,
            "consumed": self.consumed,
            "signalled": self.signalled,
            "executed": self.executed,
            "gap_entry": self.gap_entry,
            "entry_paise": self.entry_paise,
            "stop_paise": self.stop_paise,
            "target_paise": self.target_paise,
            "per_share_risk_paise": self.per_share_risk_paise,
            "entry_close_stamp": _stamp_text(self.entry_close_stamp),
            "exit_kind": self.exit_kind,
            "exit_paise": self.exit_paise,
            "exit_close_stamp": _stamp_text(self.exit_close_stamp),
            "qty": self.qty,
            "notional_paise": self.notional_paise,
            "gross_pnl_paise": self.gross_pnl_paise,
            "cost_paise": self.cost_paise,
            "net_pnl_paise": self.net_pnl_paise,
            "mfe_paise": self.mfe_paise,
            "mae_paise": self.mae_paise,
            "flags": list(self.flags),
        }
        if self.detail is not None:
            # Present only when there IS a detail: an always-written `"detail":null` would move
            # every ordinary row's bytes, and with them the chunk-9A pilot ledger's published
            # sha256, for rows that have nothing to say.
            payload["detail"] = self.detail
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping) -> "LedgerRow":
        return cls(
            symbol=str(payload["symbol"]),
            day=date.fromisoformat(str(payload["day"])),
            status=str(payload["status"]),
            reason=str(payload["reason"]),
            detail=payload.get("detail"),
            bias=payload.get("bias"),
            bias_rule=payload.get("bias_rule"),
            side=payload.get("side"),
            tie_case=bool(payload.get("tie_case", False)),
            suppressed=bool(payload.get("suppressed", False)),
            minute_count=int(payload.get("minute_count", 0)),
            gate1_passed=payload.get("gate1_passed"),
            gate1_relieved=bool(payload.get("gate1_relieved", False)),
            gate2_passed=payload.get("gate2_passed"),
            gate1p_passed=payload.get("gate1p_passed"),
            poc_half_paise=payload.get("poc_half_paise"),
            reference_paise=payload.get("reference_paise"),
            reference_source=payload.get("reference_source"),
            outcome=payload.get("outcome"),
            consumed=bool(payload.get("consumed", False)),
            signalled=bool(payload.get("signalled", False)),
            executed=bool(payload.get("executed", False)),
            gap_entry=bool(payload.get("gap_entry", False)),
            entry_paise=payload.get("entry_paise"),
            stop_paise=payload.get("stop_paise"),
            target_paise=payload.get("target_paise"),
            per_share_risk_paise=payload.get("per_share_risk_paise"),
            entry_close_stamp=_parse_stamp(payload.get("entry_close_stamp")),
            exit_kind=payload.get("exit_kind"),
            exit_paise=payload.get("exit_paise"),
            exit_close_stamp=_parse_stamp(payload.get("exit_close_stamp")),
            qty=int(payload.get("qty", 0)),
            notional_paise=int(payload.get("notional_paise", 0)),
            gross_pnl_paise=int(payload.get("gross_pnl_paise", 0)),
            cost_paise=int(payload.get("cost_paise", 0)),
            net_pnl_paise=int(payload.get("net_pnl_paise", 0)),
            mfe_paise=payload.get("mfe_paise"),
            mae_paise=payload.get("mae_paise"),
            flags=tuple(str(flag) for flag in payload.get("flags", ())),
        )

    @property
    def poc_paise(self) -> Fraction | None:
        return None if self.poc_half_paise is None else Fraction(self.poc_half_paise, 2)


def _stamp_text(stamp: datetime | None) -> str | None:
    return None if stamp is None else stamp.isoformat(sep="T", timespec="seconds")


def _parse_stamp(text) -> datetime | None:
    return None if text in (None, "") else datetime.fromisoformat(str(text))


# --- MFE / MAE (CONTEXT 7-E13's per-trade excursions), PURE ---------------------------------


def trade_excursion_paise(
    side: str,
    entry_paise: int,
    qty: int,
    bars: Sequence[Bar],
    entry_close_stamp: datetime,
    exit_close_stamp: datetime | None,
) -> tuple[int, int]:
    """``(MFE, MAE)`` in paise over the candles the position was actually held. PURE.

    CONTEXT 7-E13 lists "MFE/MAE per trade" without fixing a convention, so this is the one
    the spec's own monitoring rule forces: the position opens at the entry candle's CLOSE and
    the entry candle itself cannot move it (CONTEXT 7-E7), so the excursion is measured over
    the candles AFTER the entry candle up to and including the exit candle -- exactly the
    candles CONTEXT 3.4-5 walks. MFE is signed >= 0 and MAE <= 0; a trade whose price never
    traded beyond the entry in one direction has 0 on that side, and a trade with no monitored
    candle at all (chunk-7 decision B159) has 0 on both.
    """
    if qty <= 0:
        return (0, 0)
    monitored = [
        bar
        for bar in bars
        if bar.close_stamp > entry_close_stamp
        and (exit_close_stamp is None or bar.close_stamp <= exit_close_stamp)
    ]
    if not monitored:
        return (0, 0)
    highest = max(bar.high_paise for bar in monitored)
    lowest = min(bar.low_paise for bar in monitored)
    if side == sig.LONG:
        favourable, adverse = highest - entry_paise, lowest - entry_paise
    else:
        favourable, adverse = entry_paise - lowest, entry_paise - highest
    return (max(0, favourable) * qty, min(0, adverse) * qty)


# --- the 15-minute portfolio path (Q-16(b)): ASSEMBLY here, the METRIC in portfolio.py -------


@dataclass(frozen=True)
class TradeMark:
    """One 15-minute observation of an open position: when, and at what price it was marked."""

    stamp: datetime
    price_paise: int


@dataclass(frozen=True)
class TradePath:
    """One executed trade's marks, from its entry candle's close to its exit.

    This is the raw material of the architect's Q-16(b) ruling: "every open position marked to
    its 15-min candle closes (exit candles at their exit levels), summed across positions". The
    summation and the drawdown live in :mod:`acumen.portfolio`, which is pure; the marks are
    assembled HERE because assembling them needs the stored candles.
    """

    symbol: str
    day: date
    side: str
    qty: int
    entry_paise: int
    cost_paise: int
    net_pnl_paise: int
    marks: tuple[TradeMark, ...]


def minute_store_bars(store: MinuteStore) -> Callable[[str, date], tuple[Bar, ...]]:
    """A ``bars_for(symbol, day)`` over the stored minutes, aggregated per CONTEXT 7-E1/E12.

    The same aggregation the signal engine ran -- INCLUDING its CONTEXT 7-E2 candle-level drop
    of an out-of-session stamp -- so a mark is taken from the very candle the strategy saw, and
    there is no second source of 15-minute bars anywhere in this repo. Filtering here rather
    than only in the engine is what keeps that true: a day whose vendor feed carries a pre-open
    print would otherwise aggregate differently on this path (or raise), and the 15-minute
    equity path would stop reconciling with the ledger it is built from.
    """

    def bars_for(symbol: str, day: date) -> tuple[Bar, ...]:  # noqa: D401 -- see the wrapper
        session, _dropped = in_session_bars(store.minutes(symbol, day))
        return aggregate_15min(session) if session else ()

    return bars_for


def assemble_trade_paths(
    rows: Sequence[LedgerRow],
    *,
    bars_for: Callable[[str, date], Sequence[Bar]],
) -> tuple[TradePath, ...]:
    """Mark every executed trade at each 15-minute candle close it was held. I/O via ``bars_for``.

    The marks run from the ENTRY candle's close (where the position opened at that candle's
    close, CONTEXT 3.4) through the EXIT candle's close stamp, and the last mark carries the
    trade's EXIT LEVEL rather than that candle's close -- a target or a stop fills at its level
    even when the candle ran past it (CONTEXT 3.4-5), so marking the exit candle at its close
    would report an excursion the trade never had.

    A missing candle cannot invent a mark: the entry and exit observations are supplied from
    the ledger's own prices when the aggregation has no bar on those stamps, and nothing between
    them is interpolated.
    """
    paths: list[TradePath] = []
    for row in rows:
        if not row.executed or row.entry_paise is None or row.entry_close_stamp is None:
            continue
        entry_stamp = row.entry_close_stamp
        exit_stamp = row.exit_close_stamp or entry_stamp
        exit_paise = row.exit_paise if row.exit_paise is not None else row.entry_paise
        marks: list[TradeMark] = []
        for bar in bars_for(row.symbol, row.day):
            if bar.close_stamp < entry_stamp or bar.close_stamp > exit_stamp:
                continue
            marks.append(TradeMark(bar.close_stamp, int(bar.close_paise)))
        marks.sort(key=lambda mark: mark.stamp)
        if not marks or marks[0].stamp != entry_stamp:
            marks.insert(0, TradeMark(entry_stamp, row.entry_paise))
        if marks[-1].stamp == exit_stamp:
            marks[-1] = TradeMark(exit_stamp, exit_paise)  # the LEVEL, not the candle's close
        else:
            marks.append(TradeMark(exit_stamp, exit_paise))
        paths.append(
            TradePath(
                symbol=row.symbol,
                day=row.day,
                side=row.side or sig.LONG,
                qty=row.qty,
                entry_paise=row.entry_paise,
                cost_paise=row.cost_paise,
                net_pnl_paise=row.net_pnl_paise,
                marks=tuple(marks),
            )
        )
    return tuple(paths)


# --- the run spec ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunSpec:
    """Everything that decides what the ledger contains -- and therefore its digest.

    ``digest`` covers the code SHA as well: a ledger is a function of ONE code state, so a
    resume after the code moved is refused rather than silently mixed (see
    :meth:`BacktestRunner.run`).
    """

    symbols: tuple[str, ...]
    start: date
    end: date
    row_size: int
    risk_per_trade_paise: int
    cost_paise: int
    seed_from: date | None = None
    spec_version: str = SPEC_VERSION
    code_sha: str = ""
    factor_digest: str = ""
    #: The Q-20 PIN: which instrument-master dump supplied every symbol's tick, by filename AND
    #: content digest. Both are inside :meth:`as_dict`, therefore inside :meth:`digest`, so a
    #: resume under a different master refuses exactly as a resume after a moved code SHA does.
    master_file: str = ""
    master_sha256: str = ""
    capital_reference_paise: int | None = None
    margin_basis: str | None = None
    label: str = ""

    @property
    def seed_date(self) -> date:
        return self.seed_from if self.seed_from is not None else self.start

    def as_dict(self) -> dict:
        return {
            "symbols": list(self.symbols),
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "seed_from": self.seed_date.isoformat(),
            "row_size": self.row_size,
            "risk_per_trade_paise": self.risk_per_trade_paise,
            "cost_paise": self.cost_paise,
            "spec_version": self.spec_version,
            "code_sha": self.code_sha,
            "factor_digest": self.factor_digest,
            "master_file": self.master_file,
            "master_sha256": self.master_sha256,
            "capital_reference_paise": self.capital_reference_paise,
            "margin_basis": self.margin_basis,
            "label": self.label,
        }

    def digest(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("ascii")).hexdigest()


def code_sha(repo_root: Path | None = None) -> str:
    """``git rev-parse HEAD`` for the manifest, or ``"unknown"`` outside a git checkout."""
    root = repo_root if repo_root is not None else Path(__file__).resolve().parents[2]
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:  # pragma: no cover -- git absent
        return "unknown"
    sha = out.stdout.strip()
    return sha if out.returncode == 0 and sha else "unknown"


# --- the disclosed-residual register --------------------------------------------------------


@dataclass(frozen=True)
class ResidualEntry:
    """One symbol's line of the chunk-5B disclosed-residual register (report section 3f)."""

    symbol: str
    status: str
    gate1p_pass: int
    gate1p_total: int
    gate1p_no_oracle: int
    residual_reason: str
    #: Days that pass gate 1 AND gate 2 AND gate 1P -- the chunk-5B ledger's own ``usable_pass``.
    #: Carried so the ALL-THREE-GATES coverage figure can be COMPUTED from the register a reader
    #: already has in hand rather than typed beside the narrower gate-1P one (REVIEW_9B_FINAL
    #: finding C2). Defaulted, so every existing positional construction is unchanged.
    usable_pass: int = 0

    @property
    def price_proven_ratio(self) -> Fraction | None:
        if self.gate1p_total <= 0:
            return None
        return Fraction(self.gate1p_pass, self.gate1p_total)

    def as_dict(self) -> dict:
        ratio = self.price_proven_ratio
        return {
            "symbol": self.symbol,
            "status": self.status,
            "gate1p_pass": self.gate1p_pass,
            "gate1p_total": self.gate1p_total,
            "gate1p_no_oracle": self.gate1p_no_oracle,
            # ratio -> percent (x100) -> hundredths of a percent (x100 again). Written as two
            # factors of 100 rather than one 10,000 so that no module in src/acumen carries an
            # integer literal equal to a CONTEXT 3.5 money amount in paise -- the widened money
            # tripwire (REVIEW_9A finding C1) scans every module for exactly those magnitudes.
            # The arithmetic is Fraction and therefore identical either way.
            "price_proven_pct_x100": None if ratio is None else int(ratio * 100 * 100),
            "residual_reason": self.residual_reason,
        }


def load_residual_register(path: Path) -> dict[str, ResidualEntry]:
    """Read the chunk-5B ledger -- the machine-readable disclosed-residual register.

    CONTEXT 4.6 makes reading it a chunk-9 duty ("read the residual register before any
    per-symbol statistic"). A missing file is an ERROR, not an empty register: a run that
    silently forgot which symbols are price-partial would print per-symbol statistics nobody
    could qualify.
    """
    source = Path(path)
    if not source.is_file():
        raise BacktestError(
            f"No disclosed-residual register at {source}. CONTEXT 4.6 makes reading it a "
            "chunk-9 duty; run the chunk-5B backfill or point the runner at its ledger."
        )
    payload = json.loads(source.read_text(encoding="utf-8"))
    rows = payload.get("symbols", {})
    register: dict[str, ResidualEntry] = {}
    for symbol, row in rows.items():
        register[str(symbol).upper()] = ResidualEntry(
            symbol=str(symbol).upper(),
            status=str(row.get("status", "")),
            gate1p_pass=int(row.get("gate1p_pass", 0)),
            gate1p_total=int(row.get("gate1p_total", 0)),
            gate1p_no_oracle=int(row.get("gate1p_no_oracle", 0)),
            residual_reason=str(row.get("residual_reason", "")),
            usable_pass=int(row.get("usable_pass", 0)),
        )
    return register


# --- the Rule-3 scan's out-of-session drops (QUESTIONS.md Q-22(a)) --------------------------


@dataclass
class Rule3SessionDrops:
    """How many out-of-session 1-minute bars each Rule-3 first-break scan dropped.

    CONTEXT 4.6 makes Q-17 law: a stray stamp is dropped at the CANDLE level, *"flagged and
    counted, never silently"*. The trading path counts its own drop on the day's own row
    (:attr:`acumen.signal_engine.StockDay.out_of_session_dropped`). The Rule-3 scan reads
    **D-1's** minutes, so the only ledger row that exists for ITS drop is the TRADE DAY's -- and
    the count has to travel from the loader, which is where the dropping happens and the only
    place that still holds the raw bars, to the runner, which writes the row. This class is that
    channel and nothing more: one integer per ``(symbol, D-1)``, recorded only when a stray was
    actually dropped.

    It is per-RUN and in memory. Nothing is persisted -- CONTEXT 4.6 says outright that there is
    no per-day exclusion file -- and it is not an input to any decision: the drop itself is a
    pure function of the stored bars, so a resumed run that re-walks a symbol records exactly
    what the first walk recorded, and a shard replayed from disk keeps the flag it was written
    with. :func:`build_runner` creates ONE and hands it to both the loader and the runner.
    """

    counts: dict[tuple[str, date], int] = field(default_factory=dict)

    def record(self, symbol: str, day: date, dropped: int) -> None:
        """Remember that ``dropped`` stray bars were dropped from ``(symbol, day)``'s scan."""
        if dropped:
            self.counts[(symbol.upper(), day)] = dropped

    def dropped(self, symbol: str, day: date) -> int:
        """How many were dropped from that day's scan; ``0`` if none were, or none was asked."""
        return self.counts.get((symbol.upper(), day), 0)


# --- the runner -------------------------------------------------------------------------------


@dataclass(frozen=True)
class SymbolRun:
    """One symbol's rows plus the counts the manifest prints for it."""

    symbol: str
    rows: tuple[LedgerRow, ...]

    def counts(self) -> dict:
        refused: dict[str, int] = {}
        for row in self.rows:
            if row.status == STATUS_REFUSED:
                refused[row.reason] = refused.get(row.reason, 0) + 1
        return {
            "walked": len(self.rows),
            "usable": sum(1 for row in self.rows if row.status == STATUS_EVALUATED),
            "signalled": sum(1 for row in self.rows if row.signalled),
            "executed": sum(1 for row in self.rows if row.executed),
            "refused": dict(sorted(refused.items())),
        }


@dataclass(frozen=True)
class RunResult:
    """A finished run: every row, the manifest, and where both were written."""

    spec: RunSpec
    rows: tuple[LedgerRow, ...]
    manifest: dict
    ledger_path: Path
    manifest_path: Path
    non_standard_sessions: tuple[date, ...]


@dataclass(frozen=True)
class BacktestRunner:
    """Walks symbol-days, prices them, and writes a resumable ledger. I/O lives HERE."""

    spec: RunSpec
    pipeline: SignalPipeline
    calendar: TradingCalendar
    minute_store: MinuteStore
    daily_store: DailyStore
    factors: Mapping[str, tuple[ca.Factor, ...]]
    suppressions: Mapping[str, tuple[ca.Suppression, ...]]
    residual: Mapping[str, ResidualEntry]
    non_standard_sessions: frozenset[date] = frozenset()
    minute_loader: Callable[[str, date], Sequence | None] | None = None
    #: Where :func:`gated_minute_loader` records the CONTEXT 7-E2 / Q-17 strays it dropped from
    #: a Rule-3 scan, so the trade day's row can carry the drop under the flag the trading path
    #: already uses (QUESTIONS.md Q-22(a)). :func:`build_runner` shares ONE instance between the
    #: loader and this runner; a runner wired with a loader that records nowhere simply sees no
    #: scan drops, which is the honest answer for a loader that does not report them.
    session_drops: Rule3SessionDrops = field(default_factory=Rule3SessionDrops)
    #: Sentences the RUN wants stamped on its own manifest, verbatim and in order. Empty for
    #: every chunk-9A artefact, so no committed manifest or manifest digest moves; chunk 9B's
    #: run CLI fills it with the architect's GO-ruling disclosures (31-Jul-2026).
    disclosures: tuple[str, ...] = ()

    # --- one symbol ---------------------------------------------------------------------

    def bias_map(self, symbol: str) -> tuple[dict[date, DailyBias], str | None]:
        """The symbol's CONTEXT 3.2 bias series over the span, or the reason there is none.

        A :class:`acumen.bias_engine.BiasEngineError` is a COUNTED no-trade for every day of
        the span, never a crash: a full-history run over 400,000 stock-days must not die
        because one symbol's pair cannot be assembled.
        """
        engine = BiasEngine(
            store=self.daily_store,
            calendar=self.calendar,
            factors=tuple(self.factors.get(symbol.upper(), ())),
            suppressions=tuple(self.suppressions.get(symbol.upper(), ())),
            minute_loader=self.minute_loader,
        )
        first = self._first_pairable_day()
        if first is None:
            return ({}, f"{REASON_BIAS_UNRESOLVED}: no day in the span has a CONTEXT 3.2 pair")
        try:
            series = engine.bias_series(symbol, first, self.spec.end)
        except (BiasEngineError, CalendarError) as exc:
            return ({}, f"{REASON_BIAS_UNRESOLVED}: {exc}")
        return ({entry.trade_date: entry for entry in series}, None)

    def _first_pairable_day(self) -> date | None:
        """The first day of the span whose CONTEXT 3.2 pair the calendar can assemble.

        A span that starts at (or before) a symbol's first data has days with no D-1/D-2 at
        all. Those days are refused ONE AT A TIME, counted -- the alternative, letting the
        engine's exception refuse the whole symbol, would lose a whole history to its own first
        morning. The carry then seeds at the first pairable day, which is CONTEXT 3.2's own
        "walk forward from the earliest data" rule.
        """
        current = self.spec.seed_date
        while current <= self.spec.end:
            try:
                if self.calendar.is_trading_day(current):
                    self.calendar.bias_pair(current)
                    return current
            except CalendarError:
                pass
            current += timedelta(days=1)
        return None

    def _is_trading_day(self, day: date) -> bool | None:
        """True / False, or ``None`` when the calendar cannot answer for that date at all."""
        try:
            return self.calendar.is_trading_day(day)
        except CalendarError:
            return None

    def walk_symbol(self, symbol: str) -> SymbolRun:
        """Every walked day for one symbol, in date order. No I/O beyond the two stores."""
        biases, failure = self.bias_map(symbol)
        rows: list[LedgerRow] = []
        for day in self._span_days():
            if day in self.non_standard_sessions:
                rows.append(
                    LedgerRow(
                        symbol=symbol,
                        day=day,
                        status=STATUS_REFUSED,
                        reason=REASON_E2_NON_STANDARD,
                    )
                )
                continue
            trading = self._is_trading_day(day)
            if trading is False:
                continue  # a weekend or a holiday: there is no stock-day to walk
            if failure is not None or trading is None:
                rows.append(
                    LedgerRow(
                        symbol=symbol,
                        day=day,
                        status=STATUS_REFUSED,
                        reason=failure
                        or f"{REASON_BIAS_UNRESOLVED}: the calendar does not cover {day}",
                    )
                )
                continue
            bias = biases.get(day)
            if bias is not None and bias.unresolved_detail is not None:
                # QUESTIONS.md Q-21's THIRD REASON_BIAS_UNRESOLVED case (the Rule-3 scan met a
                # vendor-corrupt 1-minute bar on D-1) and Q-21(b)'s FOURTH (D-1 does not pass
                # the CONTEXT 4.5/4.6 gate battery). Both refuse the DAY the same way, and the
                # row carries the flag the manifest's rare-shape counter is derived from. The
                # carried bias is printed unchanged (the day did not move it) but the day is
                # REFUSED, so nothing trades on evidence that cannot be used.
                #
                # The REASON is the case, and the case alone: it is a grouping key, and both of
                # these details name a symbol, a date and a bar or a gate, which would make
                # every such row its own singleton in `refused_by_reason` (REVIEW_9B_FIXES R9).
                # The specifics go to `detail`, which is written only on rows that have one.
                rows.append(
                    LedgerRow(
                        symbol=symbol,
                        day=day,
                        status=STATUS_REFUSED,
                        reason=f"{REASON_BIAS_UNRESOLVED}: {bias.rule}",
                        detail=bias.unresolved_detail,
                        bias=bias.bias,
                        bias_rule=bias.rule,
                        flags=(unresolved_flag(bias.rule),),
                    )
                )
                continue
            if bias is None:
                rows.append(
                    LedgerRow(
                        symbol=symbol,
                        day=day,
                        status=STATUS_REFUSED,
                        reason=(
                            f"{REASON_BIAS_UNRESOLVED}: no CONTEXT 3.2 pair for {day} "
                            "(D-1 or D-2 is outside the run's own history)"
                        ),
                    )
                )
                continue
            rows.append(self.walk_day(symbol, bias))
        return SymbolRun(symbol=symbol, rows=tuple(rows))

    def walk_day(self, symbol: str, bias: DailyBias) -> LedgerRow:
        """One symbol-day: gates -> POC -> signal -> money, or the first refusal reason."""
        stock_day = self.pipeline.stock_day(symbol, bias.trade_date, bias=bias)
        record = None
        if stock_day.signal is not None:
            record = sim.simulate_day(
                stock_day.signal,
                stock_day.bars,
                symbol=symbol,
                risk_per_trade_paise=self.spec.risk_per_trade_paise,
                cost_paise=self.spec.cost_paise,
                bias=bias.bias,
                tie_case=bias.tie_case,
            )
        return self._row(symbol, bias, stock_day, record)

    # --- the row ------------------------------------------------------------------------

    def _row(
        self,
        symbol: str,
        bias: DailyBias,
        stock_day: se.StockDay,
        record: sim.TradeRecord | None,
    ) -> LedgerRow:
        gates = stock_day.gates
        profile = stock_day.profile
        poc = None if profile is None else profile.poc_paise
        base = LedgerRow(
            symbol=symbol,
            day=stock_day.day,
            status=STATUS_EVALUATED if stock_day.evaluated else STATUS_REFUSED,
            reason=stock_day.reason,
            bias=bias.bias,
            bias_rule=bias.rule,
            side=stock_day.side,
            tie_case=bias.tie_case,
            suppressed=bias.suppressed,
            minute_count=stock_day.minute_count,
            gate1_passed=None if gates is None or gates.gate1 is None else gates.gate1.passed,
            gate1_relieved=bool(gates is not None and gates.relieved),
            gate2_passed=None if gates is None else gates.gate2.passed,
            gate1p_passed=None if gates is None else gates.gate1p.passed,
            poc_half_paise=None if poc is None else int(poc * 2),
            flags=self._session_drop_flags(symbol, bias, stock_day),
        )
        if record is None:
            return base
        signal = stock_day.signal
        mfe = mae = None
        if record.executed and record.entry_paise is not None and record.entry_close_stamp:
            mfe, mae = trade_excursion_paise(
                record.side,
                record.entry_paise,
                record.qty,
                stock_day.bars,
                record.entry_close_stamp,
                record.exit_close_stamp,
            )
        return replace(
            base,
            reference_paise=None if signal is None else signal.reference_paise,
            reference_source=None if signal is None else signal.reference_source,
            outcome=record.outcome,
            consumed=record.consumed,
            signalled=record.signalled,
            executed=record.executed,
            gap_entry=record.gap_entry,
            entry_paise=record.entry_paise,
            stop_paise=record.stop_paise,
            target_paise=record.target_paise,
            per_share_risk_paise=record.per_share_risk_paise,
            entry_close_stamp=record.entry_close_stamp,
            exit_kind=record.exit_kind,
            exit_paise=record.exit_paise,
            exit_close_stamp=record.exit_close_stamp,
            qty=record.qty,
            notional_paise=(
                0 if record.entry_paise is None else record.qty * record.entry_paise
            ),
            gross_pnl_paise=record.gross_pnl_paise,
            cost_paise=record.cost_paise,
            net_pnl_paise=record.net_pnl_paise,
            mfe_paise=mfe,
            mae_paise=mae,
            flags=base.flags + record.flags,
        )

    def _session_drop_flags(
        self, symbol: str, bias: DailyBias, stock_day: se.StockDay
    ) -> tuple[str, ...]:
        """CONTEXT 7-E2 / Q-17's flag, set once whichever consumer dropped the stray.

        Two consumers of stored 1-minute bars can drop an out-of-session stamp for one walked
        day, and after QUESTIONS.md Q-22(a) the ledger records BOTH under the flag Q-17 already
        had: the day's OWN 15-minute feed and POC window (``stock_day.out_of_session_dropped``),
        and the Rule-3 first-break scan of its **D-1** (:class:`Rule3SessionDrops`). A day where
        both fired carries the flag ONCE, so the manifest's counter counts DAYS, not events --
        and a reader can still recompute it from the committed ledger alone.
        """
        scan_dropped = (
            bias.current_date is not None
            and self.session_drops.dropped(symbol, bias.current_date) > 0
        )
        if stock_day.out_of_session_dropped or scan_dropped:
            return (FLAG_OUT_OF_SESSION_DROPPED,)
        return ()

    def _span_days(self) -> tuple[date, ...]:
        days: list[date] = []
        current = self.spec.start
        while current <= self.spec.end:
            days.append(current)
            current += timedelta(days=1)
        return tuple(days)

    # --- the run ------------------------------------------------------------------------

    def run(
        self,
        run_dir: Path,
        *,
        progress: Callable[[str], None] | None = None,
        after_symbol: Callable[[str], None] | None = None,
    ) -> RunResult:
        """Walk every symbol, shard by shard, then write the ledger and the manifest.

        Resumable: a symbol's shard is written (atomically, fsynced) only once that symbol is
        COMPLETE, and ``progress.json`` records which symbols are done. A resume replays the
        finished shards and re-walks only what was lost, so no row can be duplicated. Idempotent:
        the shard content, the ledger and the manifest are pure functions of the spec and the
        stores, so a completed re-run reproduces the same bytes.

        ``after_symbol`` runs after each symbol's shard is durable -- the hook the resume test
        interrupts the run from.
        """
        base = Path(run_dir)
        shards = base / SHARD_DIRNAME
        shards.mkdir(parents=True, exist_ok=True)
        done = self._resume_state(base)

        for symbol in self.spec.symbols:
            shard = shards / f"{symbol}.jsonl"
            if symbol in done and shard.is_file():
                if progress is not None:
                    progress(f"  {symbol}: resumed from shard ({shard.name})")
                continue
            walked = self.walk_symbol(symbol)
            atomic_write_text(shard, "".join(row.to_json() + "\n" for row in walked.rows))
            done.append(symbol)
            self._write_progress(base, done)
            if progress is not None:
                counts = walked.counts()
                progress(
                    f"  {symbol}: {counts['walked']} walked, {counts['usable']} usable, "
                    f"{counts['executed']} executed"
                )
            if after_symbol is not None:
                after_symbol(symbol)

        rows: list[LedgerRow] = []
        per_symbol: dict[str, dict] = {}
        for symbol in self.spec.symbols:
            shard_rows = read_ledger(shards / f"{symbol}.jsonl")
            rows.extend(shard_rows)
            per_symbol[symbol] = SymbolRun(symbol, shard_rows).counts()

        ledger_path = base / LEDGER_NAME
        atomic_write_text(ledger_path, "".join(row.to_json() + "\n" for row in rows))
        manifest = self.build_manifest(tuple(rows), per_symbol)
        manifest_path = base / MANIFEST_NAME
        atomic_write_text(manifest_path, canonical_json(manifest))
        return RunResult(
            spec=self.spec,
            rows=tuple(rows),
            manifest=manifest,
            ledger_path=ledger_path,
            manifest_path=manifest_path,
            non_standard_sessions=tuple(sorted(self.non_standard_sessions)),
        )

    def _resume_state(self, base: Path) -> list[str]:
        path = base / PROGRESS_NAME
        if not path.is_file():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("spec_digest") != self.spec.digest():
            raise BacktestError(
                f"{path} belongs to a different run (spec digest "
                f"{payload.get('spec_digest')!r} != {self.spec.digest()!r}). A ledger is a "
                "function of ONE spec and ONE code state; delete the run directory or start a "
                "new one rather than mixing two."
            )
        return [str(symbol) for symbol in payload.get("completed", [])]

    def _write_progress(self, base: Path, done: Sequence[str]) -> None:
        atomic_write_text(
            base / PROGRESS_NAME,
            canonical_json({"spec_digest": self.spec.digest(), "completed": list(done)}),
        )

    # --- the manifest -------------------------------------------------------------------

    def build_manifest(
        self, rows: Sequence[LedgerRow], per_symbol: Mapping[str, dict]
    ) -> dict:
        """Everything a reader needs to qualify the ledger. No clock read anywhere in it."""
        refused: dict[str, int] = {}
        for row in rows:
            if row.status == STATUS_REFUSED:
                refused[row.reason] = refused.get(row.reason, 0) + 1
        executed = [row for row in rows if row.executed]
        stamped = (
            {"disclosures": list(self.disclosures)} if self.disclosures else {}
        )
        return {
            **stamped,
            "spec_version": self.spec.spec_version,
            "code_sha": self.spec.code_sha,
            "config_digest": self.spec.digest(),
            "spec": self.spec.as_dict(),
            # QUESTIONS.md Q-20 (architect, 02-Aug-2026): "the run manifest records the pin by
            # filename AND sha256". Its own complaint was that a finished ledger could not be
            # traced back to the ticks that shaped its POCs; this block is that traceability.
            "instrument_master": {
                "pinned_file": self.spec.master_file,
                "sha256": self.spec.master_sha256,
                "note": MASTER_PIN_NOTE,
            },
            "universe": list(self.spec.symbols),
            "span": {"start": self.spec.start.isoformat(), "end": self.spec.end.isoformat()},
            "totals": {
                "walked": len(rows),
                "usable": sum(1 for row in rows if row.status == STATUS_EVALUATED),
                "gate1_relieved": sum(1 for row in rows if row.gate1_relieved),
                "signalled": sum(1 for row in rows if row.signalled),
                "executed": len(executed),
                "shares": sum(row.qty for row in executed),
                "gross_pnl_paise": sum(row.gross_pnl_paise for row in executed),
                "cost_paise": sum(row.cost_paise for row in executed),
                "net_pnl_paise": sum(row.net_pnl_paise for row in executed),
            },
            "refused_by_reason": dict(sorted(refused.items())),
            "outcomes": outcome_counts(rows),
            "exit_kinds": exit_kind_counts(rows),
            "per_symbol": {symbol: per_symbol[symbol] for symbol in sorted(per_symbol)},
            "rare_shapes": rare_shape_counts(rows),
            "non_standard_sessions_excluded": [
                day.isoformat() for day in sorted(self.non_standard_sessions)
            ],
            "factor_table": self._factor_summary(),
            "residual_register": self._residual_summary(),
            "capital_flags": {
                "computed": False,
                "note": CAPITAL_FLAGS_RETIRED_NOTE,
                "capital_reference_paise": self.spec.capital_reference_paise,
                "margin_basis": self.spec.margin_basis,
            }
            if self.spec.capital_reference_paise is None or self.spec.margin_basis is None
            else {
                "computed": True,
                "note": "computed POST-HOC from the ledger, never inside the run",
                "capital_reference_paise": self.spec.capital_reference_paise,
                "margin_basis": self.spec.margin_basis,
            },
        }

    def _factor_summary(self) -> dict:
        return {
            "digest": self.spec.factor_digest,
            "per_symbol": {
                symbol: {
                    "factors": len(self.factors.get(symbol, ())),
                    "suppressions": len(self.suppressions.get(symbol, ())),
                    "in_span": [
                        {
                            "ex_date": f.ex_date.isoformat(),
                            "kind": f.kind,
                            "k": str(f.k),
                            "classification": f.classification,
                        }
                        for f in self.factors.get(symbol, ())
                        if self.spec.seed_date <= f.ex_date <= self.spec.end
                    ],
                    "suppressions_in_span": [
                        {"ex_date": s.ex_date.isoformat(), "kind": s.kind}
                        for s in self.suppressions.get(symbol, ())
                        if self.spec.seed_date <= s.ex_date <= self.spec.end
                    ],
                }
                for symbol in sorted(self.spec.symbols)
            },
        }

    def _residual_summary(self) -> dict:
        entries = {
            symbol: self.residual[symbol].as_dict()
            for symbol in sorted(self.spec.symbols)
            if symbol in self.residual
        }
        missing = [symbol for symbol in sorted(self.spec.symbols) if symbol not in self.residual]
        return {
            "acknowledged": True,
            "source": RESIDUAL_LEDGER_RELPATH,
            "caveat": residual_caveat(self.residual),
            # The register entries the CAVEAT ITSELF quotes -- CONTEXT 4.6 (v1.5) requires its
            # figures to be "quoted from the register's own current figures", so a reader must
            # be able to recompute the sentence from the manifest alone. They are carried in
            # their own block rather than folded into `per_symbol`, because `per_symbol` is the
            # UNIVERSE THIS RUN WALKED and IOC/TATASTEEL are usually not in it: a pilot over
            # five symbols would otherwise look as though it had walked seven.
            "caveat_basis": {
                symbol: self.residual[symbol].as_dict()
                for symbol in SETTLED_BUT_PARTIAL
                if symbol in self.residual
            },
            "per_symbol": entries,
            "not_in_register": missing,
        }


#: Set on a ledger row whose day carried a 1-minute stamp outside 09:15..15:29 that was DROPPED
#: before the engines ran (CONTEXT 7-E2 at the candle level -- gate 2's own reading, chunk 5B).
#: Carried as a FLAG rather than as a new column so a day without one writes the same bytes it
#: always did: the chunk-9A pilot ledger's published sha256 does not move (REVIEW_9A section 7).
#:
#: Since QUESTIONS.md **Q-22(a)** (architect, 03-Aug-2026) it covers BOTH consumers of a walked
#: day's stored minutes -- the day's own 15-minute feed and POC window, and the Rule-3
#: first-break scan of its D-1 -- because the ruling makes the drop bind every consumer and this
#: is the row on which a Rule-3 drop can be recorded at all. It is set at most once per row
#: (:meth:`BacktestRunner._session_drop_flags`), so its manifest counter counts DAYS.
FLAG_OUT_OF_SESSION_DROPPED: str = "out-of-session 1-minute bar(s) dropped (CONTEXT 7-E2)"

#: Set on the refused ledger row of a trade day whose Rule-3 scan met a vendor-corrupt bar on
#: D-1 (QUESTIONS.md Q-21). Like the flag above it is a FLAG rather than a new column, so a day
#: without one writes exactly the bytes it always did; the manifest's rare-shape counter is
#: DERIVED from it, which is what keeps a resumed run's count identical to a fresh one's.
FLAG_MALFORMED_MINUTE_BAR: str = (
    "rule-3 minute scan met a malformed 1-minute bar (QUESTIONS.md Q-21)"
)

#: Set on the refused ledger row of a trade day whose Rule-3 scan asked for a D-1 that does NOT
#: pass the CONTEXT 4.5/4.6 gate battery (QUESTIONS.md Q-21(b)). Same carrier as the flag above,
#: for the same two reasons: a day without one writes exactly the bytes it always did, and the
#: manifest's counter is DERIVED from the flag rather than accumulated during the walk.
FLAG_UNGATED_MINUTE_DAY: str = (
    "rule-3 minute scan met a D-1 that fails the CONTEXT 4.5/4.6 gate battery "
    "(QUESTIONS.md Q-21(b))"
)

#: Which flag (and therefore which rare-shape counter) an UNRESOLVED bias day carries, keyed by
#: the rule :mod:`acumen.bias_engine` gave it. One mapping rather than a branch per case, so a
#: fifth case cannot be added to the engine and silently reach the ledger unflagged and uncounted.
UNRESOLVED_FLAG_BY_RULE: Mapping[str, str] = {
    RULE_MINUTES_MALFORMED: FLAG_MALFORMED_MINUTE_BAR,
    RULE_MINUTES_UNGATED: FLAG_UNGATED_MINUTE_DAY,
}


def unusable_evidence_rules() -> tuple[str, ...]:
    """Every rule tag an :class:`~acumen.bias_engine.UnusableMinuteEvidence` can put on a day.

    Discovered from the class tree rather than listed, so the answer cannot go stale: a fifth
    case is a new subclass, and a new subclass is what this walks. Sorted, so the guard below
    and the tests that read it are deterministic.
    """
    found: set[str] = set()
    stack = list(UnusableMinuteEvidence.__subclasses__())
    while stack:
        cls = stack.pop()
        stack.extend(cls.__subclasses__())
        if cls.rule:
            found.add(cls.rule)
    return tuple(sorted(found))


def unresolved_flag(rule: str) -> str:
    """The ledger flag for an unresolvable-bias ``rule`` -- or a NAMED refusal, never a KeyError.

    ``walk_symbol`` used to index :data:`UNRESOLVED_FLAG_BY_RULE` directly, so a fifth
    unusable-evidence case reaching the ledger without an entry would have raised ``KeyError``
    mid-run and killed the walk -- worse than the crash the Q-21 ruling was written to remove
    (REVIEW_9B_FIXES R9). The real defence is the import-time guard below, which makes that gap
    impossible to ship; this is the belt behind it, and it says what is missing.
    """
    flag = UNRESOLVED_FLAG_BY_RULE.get(rule)
    if flag is None:
        raise BacktestError(
            f"No ledger flag for the unresolvable-bias rule {rule!r}. Every "
            "UnusableMinuteEvidence case must carry one, because the manifest's rare-shape "
            "counters are DERIVED from the row flags -- an unflagged refusal would be counted "
            "nowhere. Add it to UNRESOLVED_FLAG_BY_RULE and give it a RARE_SHAPE_LABELS entry."
        )
    return flag


def _unflagged_unusable_rules() -> tuple[str, ...]:
    """Unusable-evidence rules with no entry in :data:`UNRESOLVED_FLAG_BY_RULE`. Empty = sound."""
    return tuple(
        rule for rule in unusable_evidence_rules() if rule not in UNRESOLVED_FLAG_BY_RULE
    )


# The guard fires at IMPORT, which means at collection time for the whole test suite and before
# the first symbol of a ten-hour run -- not on the one day in the span that happens to hit the
# new case (REVIEW_9B_FIXES R9). A missing flag is a build-time error, deliberately loud.
_UNFLAGGED_RULES = _unflagged_unusable_rules()
if _UNFLAGGED_RULES:  # pragma: no cover -- the tripwire's failure mode, asserted by test
    raise BacktestError(
        "acumen.bias_engine defines unusable-evidence rule(s) with no ledger flag: "
        f"{', '.join(_UNFLAGGED_RULES)}. Every case must be flagged AND counted (QUESTIONS.md "
        "Q-21 / Q-21(b)); add each to UNRESOLVED_FLAG_BY_RULE and to RARE_SHAPE_LABELS."
    )


#: HISTORICAL. What every output said while the trader's Q43 answer was outstanding, kept
#: byte-exact because the completed run's manifest and the committed chunk-9A pilot pack both
#: carry this sentence and a quotation of either must stay verbatim (the architect's
#: quotation-fidelity ruling, 06-Aug-2026). Nothing NEW says it -- see
#: :data:`CAPITAL_FLAGS_RETIRED_NOTE`.
CAPITAL_FLAGS_PENDING_NOTE: str = (
    "capital-infeasibility flags NOT computed -- the trader's Q43 answer is pending"
)

#: What every output says now. The trader SUPERSEDED his own Q43 question in Round 4 (architect,
#: 06-Aug-2026): the capital-infeasibility flags are RETIRED and a per-stock POINTS view is
#: adopted in their place. The two config keys stay null, so the machinery still computes
#: nothing -- what changes is that no reader is told an answer is on its way.
CAPITAL_FLAGS_RETIRED_NOTE: str = (
    "capital-infeasibility flags RETIRED by the trader (Round 4): he superseded his own Q43 "
    "question, and the config keys stay null, labelled 'retired by trader, Round 4'"
)


def rare_shape_counts(rows: Sequence[LedgerRow]) -> dict[str, int]:
    """How often each rare shape actually occurred, counted from the ROWS. PURE.

    Derived rather than accumulated on the way past, for two reasons: a resumed run replays
    shards it did not walk (so a running counter would undercount and the manifest would stop
    being byte-identical), and a reader can recompute every number here from the committed
    ledger alone.
    """
    counts = {label: 0 for label in RARE_SHAPE_LABELS}
    for row in rows:
        if row.gap_entry:
            counts["gap entries"] += 1
        if row.tie_case:
            counts["rule-3 tie bias days"] += 1
        if row.bias_rule == RULE_3_NO_MINUTE:
            counts["rule-3 day with no 1-minute data (carried, CONTEXT 3.2)"] += 1
        if row.reference_source == sig.REFERENCE_FROM_MINUTES:
            counts["E10 fallback reference (no 11:00-stamped candle)"] += 1
        for flag, label in (
            (
                FLAG_MALFORMED_MINUTE_BAR,
                "rule-3 day refused on a malformed 1-minute bar (QUESTIONS.md Q-21)",
            ),
            (
                FLAG_UNGATED_MINUTE_DAY,
                "rule-3 day refused on a battery-failing D-1 (QUESTIONS.md Q-21(b))",
            ),
            (sim.FLAG_QTY_ZERO_UNSIZABLE, "qty-zero unsizable days"),
            (sim.FLAG_SIGNAL_UNSIZABLE, "signal-unsizable (degenerate) days"),
            (sim.FLAG_BOTH_TOUCHED_STOP_WINS, "both-touched candles (stop won)"),
            (sim.FLAG_SQUARE_OFF_AT_ENTRY_CANDLE, "square-offs priced at the entry candle"),
            (
                FLAG_OUT_OF_SESSION_DROPPED,
                "day with out-of-session 1-minute bar(s) dropped (CONTEXT 7-E2 / Q-17)",
            ),
        ):
            if flag in row.flags:
                counts[label] += 1
    return counts


def outcome_counts(rows: Sequence[LedgerRow]) -> dict[str, int]:
    """Every walked day by what happened to it. The counts PARTITION the run. PURE."""
    counts: dict[str, int] = {}
    for row in rows:
        key = row.outcome if row.outcome is not None else f"not evaluated: {row.reason}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def exit_kind_counts(rows: Sequence[LedgerRow]) -> dict[str, int]:
    """How the executed trades ended (stop / target / square-off). PURE."""
    counts: dict[str, int] = {}
    for row in rows:
        if row.executed and row.exit_kind:
            counts[row.exit_kind] = counts.get(row.exit_kind, 0) + 1
    return dict(sorted(counts.items()))


def stable_manifest_digest(manifest: Mapping) -> str:
    """sha256 of the manifest with the commit-dependent fields removed.

    ``code_sha`` and the config digest that covers it change with every commit, so a pack that
    printed them could not regenerate byte-identically tomorrow (REVIEW_8 finding C2). They
    stay in the manifest ON DISK, where pinning the run to a commit is the point; this digest
    is what a pack quotes.
    """
    payload = {key: value for key, value in manifest.items() if key not in _VOLATILE_KEYS}
    spec = dict(payload.get("spec", {}))
    spec.pop("code_sha", None)
    if spec:
        payload["spec"] = spec
    return hashlib.sha256(canonical_json(payload).encode("ascii")).hexdigest()


_VOLATILE_KEYS: frozenset[str] = frozenset({"code_sha", "config_digest"})


def canonical_json(payload) -> str:
    """Sorted-key, ASCII, newline-terminated JSON. The only serialization this module writes."""
    return json.dumps(payload, sort_keys=True, indent=1, ensure_ascii=True) + "\n"


def read_ledger(path: Path) -> tuple[LedgerRow, ...]:
    """Parse a ledger (or one shard) back into rows. The portfolio layer consumes these."""
    source = Path(path)
    if not source.is_file():
        raise BacktestError(f"No ledger at {source}.")
    rows = []
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(LedgerRow.from_dict(json.loads(line)))
    return tuple(rows)


# --- wiring (the only place stores, the CA table and the calendar are opened) ---------------


def pinned_master(cache_dir: Path, filename: str) -> tuple[InstrumentMaster, Path, str]:
    """Load the ONE PINNED instrument master by name, offline. Returns (master, path, sha256).

    **This replaced ``latest_cached_master``, which selected the newest dump by filename.**
    QUESTIONS.md Q-20 (architect, 02-Aug-2026): the vendor's ``tick_size`` is not stable between
    daily dumps -- two snapshots two days apart disagree for 11 of the sealed 210, in BOTH
    directions -- and CONTEXT 3.3 sizes the profile row grid by that tick, so "newest wins"
    silently decided every POC on those symbols and made a re-run non-reproducible. One pinned
    snapshot governs the whole backtest; the spec target is the trader's TradingView chart, which
    applies the CURRENT tick to the entire history.

    The sha256 is returned with the path because the manifest records the pin by BOTH (a
    filename can be overwritten in place; a digest cannot), and because both fields enter
    :class:`RunSpec`, hence the spec digest, hence the resume check -- so a resume under any
    other master REFUSES exactly as a resume after a moved code SHA does.
    """
    path = Path(cache_dir) / MASTER_CACHE_SUBDIR / filename
    if not path.is_file():
        raise BacktestError(
            f"The pinned instrument master {filename!r} is not at {path}. The run needs each "
            "symbol's own tick size (CONTEXT 4.3 -- never hardcode a tick) and QUESTIONS.md "
            "Q-20 pins WHICH dump supplies it; config.yaml's `instrument_master` names the pin. "
            "Fetch that dump or correct the pin -- do NOT substitute another snapshot, because "
            "the vendor's tick moves between dumps."
        )
    try:
        master = load_master_file(path)
    except InstrumentMasterError as exc:  # pragma: no cover -- a corrupt cache file
        raise BacktestError(f"Pinned instrument master {path} is unusable: {exc}") from exc
    return master, path, file_sha256(path)


def file_sha256(path: Path) -> str:
    """Streaming sha256 of a file. The master is ~34 MB, so it is never slurped whole."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_factor_tables(
    symbols: Sequence[str],
    daily_store: DailyStore,
    *,
    start: date,
    end: date,
    allow_network: bool = False,
    cache_dir: Path | None = None,
) -> tuple[dict[str, tuple[ca.Factor, ...]], dict[str, tuple[ca.Suppression, ...]], str, dict]:
    """The REAL chunk-3 factor table for each symbol, plus its digest and a parse summary.

    The corporate-action history is pulled ONCE for all years and reused across the universe
    (the chunk-5B shape), day-cached; with ``allow_network=False`` only the cache is read, at
    ANY age (architect, 31-Jul-2026 -- offline means "use exactly what is on disk"), so a
    reviewer holding it reproduces the table exactly on any later day. A bare clone with no
    cache RAISES rather than running on an empty table: an empty factor table is not visibly
    different from a market with no corporate actions, and CONTEXT 3.2's pairwise adjustment
    would then be silently wrong on every pre-event pair.

    The full history is passed to :func:`acumen.corp_actions.build_factor_table` per symbol
    because the Q-6 face-value reconstruction needs the symbol's whole split history, not the
    slice inside the run span.
    """
    actions = fetch_corp_action_history(
        date(min(2005, start.year), 1, 1),
        end,
        allow_network=allow_network,
        cache_dir=cache_dir,
    )
    factors: dict[str, tuple[ca.Factor, ...]] = {}
    suppressions: dict[str, tuple[ca.Suppression, ...]] = {}
    summary: dict[str, dict] = {}
    for symbol in symbols:
        table = corp_actions_for_symbol(symbol, actions, daily_store)
        factors[symbol] = tuple(table.factors)
        suppressions[symbol] = tuple(table.suppressions)
        summary[symbol] = {
            "factors": len(table.factors),
            "suppressions": len(table.suppressions),
            "pending": len(table.pending),
            "parse_exceptions": len(table.parse_exceptions),
        }
    payload = json.dumps(
        {
            symbol: {
                "factors": [
                    [f.ex_date.isoformat(), f.kind, str(f.k)] for f in factors[symbol]
                ],
                "suppressions": [
                    [s.ex_date.isoformat(), s.kind] for s in suppressions[symbol]
                ],
            }
            for symbol in sorted(factors)
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("ascii")).hexdigest()
    return factors, suppressions, digest, summary


def build_runner(
    symbols: Sequence[str],
    start: date,
    end: date,
    *,
    data_dir: Path | None = None,
    cache_dir: Path | None = None,
    seed_from: date | None = None,
    label: str = "",
    allow_network: bool = False,
    progress: Callable[[str], None] | None = None,
    non_standard_sessions: frozenset[date] | None = None,
    disclosures: tuple[str, ...] = (),
    master_path: Path | None = None,
) -> tuple[BacktestRunner, Path, dict]:
    """Open the local stores read-only and wire the whole machine. Returns (runner, master, ca).

    Money, Row Size and the PINNED instrument master all come from ``config.yaml`` through the
    loader -- never typed here (CONTEXT 3.5, chunk-8 decision B169; QUESTIONS.md Q-20).

    ``master_path`` names the instrument master explicitly, which is what the run path does:
    the preflight resolves the Q-20 pin, prints its digest, and hands the same file to the run.
    ``None`` falls back to the CONFIGURED PIN -- never to "the newest dump on disk", which is
    the selection the Q-20 ruling retired.

    ``non_standard_sessions`` lets a caller supply a CONTEXT 7-E2 scan it already holds instead
    of re-running it. The scan is O(symbols x span days) reads of the minute store -- the same
    order as the walk itself -- so a full-history run that re-scanned on every resume would pay
    for the whole universe again before writing its first new row (decision B181, recorded as a
    9B duty in the chunk-9A pack). ``None`` means "scan now", which is what every chunk-9A
    caller does and what keeps their artefacts byte-identical.

    ``disclosures`` are stamped verbatim onto the run's own manifest and onto nothing else.
    """
    config = load_config(include_env=False)
    data = Path(data_dir) if data_dir is not None else config.path("data_root")
    cache = Path(cache_dir) if cache_dir is not None else config.path("cache_root")

    daily_store = DailyStore.at(data / "daily_store")
    minute_store = MinuteStore.at(data / "minute_store")
    if master_path is not None and Path(master_path).name != config.instrument_master:
        # The ruling is "ONE PINNED master snapshot governs the whole backtest", so an explicit
        # path is a CONFIRMATION of the pin, never an override of it. Without this, threading
        # the path through would have re-opened by argument exactly the door the config closed.
        raise BacktestError(
            f"{Path(master_path).name} is not the pinned instrument master "
            f"({config.instrument_master}). QUESTIONS.md Q-20 pins ONE snapshot for the whole "
            "backtest; change the pin in config.yaml -- which is an architect spec change, and "
            "which makes every in-flight run refuse to resume -- rather than passing another "
            "file here."
        )
    master, master_path, master_sha = pinned_master(cache, config.instrument_master)
    seed = seed_from if seed_from is not None else start
    calendar = TradingCalendar.from_daily_store_range(
        daily_store, seed - timedelta(days=CALENDAR_LEAD_DAYS), end
    )
    residual = load_residual_register(data / RESIDUAL_LEDGER_RELPATH)

    wanted = tuple(symbol.strip().upper() for symbol in symbols)
    factors, suppressions, digest, ca_summary = build_factor_tables(
        wanted, daily_store, start=seed, end=end, allow_network=allow_network
    )

    if non_standard_sessions is None:
        span_days = [seed + timedelta(days=offset) for offset in range((end - seed).days + 1)]
        non_standard = scan_non_standard_sessions(
            minute_store, wanted, span_days, progress=progress
        )
    else:
        non_standard = tuple(sorted(non_standard_sessions))
    if non_standard:
        calendar = replace(
            calendar, trading_days=frozenset(calendar.trading_days) - set(non_standard)
        )

    spec = RunSpec(
        symbols=wanted,
        start=start,
        end=end,
        seed_from=seed,
        row_size=config.row_size,
        risk_per_trade_paise=config.require_risk_per_trade_paise(),
        cost_paise=config.cost_per_trade_paise(),
        code_sha=code_sha(),
        factor_digest=digest,
        master_file=master_path.name,
        master_sha256=master_sha,
        capital_reference_paise=config.capital_reference_paise(),
        margin_basis=config.margin_basis_text(),
        label=label,
    )
    pipeline = SignalPipeline(
        minute_store=minute_store,
        daily_store=daily_store,
        master=master,
        row_size=config.row_size,
    )
    # QUESTIONS.md Q-22(a): ONE drop ledger, shared between the loader that does the dropping
    # and the runner that writes the row. Two instances would mean a counted drop nobody printed.
    session_drops = Rule3SessionDrops()
    runner = BacktestRunner(
        spec=spec,
        pipeline=pipeline,
        calendar=calendar,
        minute_store=minute_store,
        daily_store=daily_store,
        factors=factors,
        suppressions=suppressions,
        residual=residual,
        non_standard_sessions=frozenset(non_standard),
        # QUESTIONS.md Q-21(b): the RUN reads D-1's minutes through the GATED loader -- the
        # same pipeline that gates the day being traded also gates the day being used as
        # evidence, so one battery answers both questions and they can never disagree.
        minute_loader=gated_minute_loader(minute_store, pipeline, drops=session_drops),
        session_drops=session_drops,
        disclosures=tuple(disclosures),
    )
    return runner, master_path, ca_summary


def gated_minute_loader(
    store: MinuteStore, pipeline: SignalPipeline, *, drops: Rule3SessionDrops | None = None
):
    """The RUN's Rule-3 minute loader, with the CONTEXT 4.5/4.6 battery IN FRONT of it.

    **QUESTIONS.md Q-21(b)** (architect, 03-Aug-2026): *"a day's minutes may serve a Rule-3
    first-break scan ONLY if that day passes the CONTEXT 4.5/4.6 gate battery ... a
    battery-failing D-1 makes the bias UNRESOLVABLE: fourth counted case (minutes-ungated)."*
    Until that ruling, a day's gate verdicts gated only its own TRADING: the bias engine read
    D-1's minutes straight from the store, consulting no gate, so a D-1 in a wrong-price-domain
    era could hand a Rule-3 scan minutes on one price scale to compare against P's levels on
    another -- and the winner of that comparison then decided a real trade.

    The order is the ruling's own: the BATTERY FIRST, before a single :class:`acumen.bias.Candle`
    is built. A day that fails a gate is refused as ``minutes-ungated`` even if it also carries a
    malformed bar (JIOFIN 2023-08-21 is exactly that day), because the gate is the ruling's
    precondition rather than a second opinion about the bar.

    The verdict is computed ONCE per ``(symbol, day)`` and reused -- the ruling's "computes (or
    reuses)". It is a memo and never a persisted exclusion file: CONTEXT 4.6 says outright that
    there is no per-day exclusion file, and the battery is recomputed from the two local stores
    exactly as :meth:`acumen.signal_engine.SignalPipeline.stock_day` recomputes it for the day
    being traded. Only the two-string verdict is held, never the day's bars.

    A day with NO stored minutes is NOT gated and NOT refused: it is CONTEXT 3.2's documented
    missing-1-minute carry (R1-Q6), which is a spec branch and not a data verdict, and the
    battery cannot be run on a day with no bars at all.

    **The battery sees the WHOLE stored day; the SCAN sees only the session** (QUESTIONS.md
    Q-22(a)). ``gate_day`` is handed the unfiltered bars because CONTEXT 4.6's Q-17 law says
    outright that *"gates still see the whole stored day for volume"* -- NSE's daily volume
    includes the pre-open auction, which is what gate 1 reconciles against -- and only then does
    :func:`candles_for` drop the strays. ``drops`` is where that drop is recorded so the trade
    day's ledger row can carry it; ``None`` records nowhere, which is what an evidence script
    asking a one-off question wants.
    """
    refusals: dict[tuple[str, date], tuple[str, str] | None] = {}

    def gated(symbol: str, day: date):
        bars = store.minutes(symbol, day)
        if not bars:
            return None  # CONTEXT 3.2 / R1-Q6: the documented carry, not a gate verdict
        key = (symbol.upper(), day)
        if key not in refusals:
            refusals[key] = pipeline.gate_day(symbol, day, bars).refusal_detail
        refusal = refusals[key]
        if refusal is not None:
            raise UngatedMinuteDay(
                symbol=symbol, day=day, gate=refusal[0], gate_reason=refusal[1]
            )
        candles, dropped = candles_for(symbol, day, bars)
        if drops is not None:
            drops.record(symbol, day, dropped)
        return candles

    return gated


def minute_loader(store: MinuteStore, *, drops: Rule3SessionDrops | None = None):
    """The ``(symbol, date) -> candles`` interface CONTEXT 3.2's Rule 3 needs, over the store.

    **A vendor-corrupt bar is refused HERE** (QUESTIONS.md Q-21, architect 03-Aug-2026). A raw
    1-minute bar whose open or close lies outside ``[low, high]`` is impossible, and
    :class:`acumen.bias.Candle` -- the pure engine's own invariant -- says so by raising. This
    is the narrowest place that still holds the RAW bar, so it is the only place that can name
    the offending stamp and its OHLCV; the exception is re-raised as
    :class:`~acumen.bias_engine.MalformedMinuteBar`, which the bias engine turns into a refused
    DAY under :data:`REASON_BIAS_UNRESOLVED`.

    The bar is never dropped and the scan is never continued without it: Rule 3 decides on
    which extreme broke FIRST, so a scan minus one corrupt bar could reverse the bias.

    **This loader does NOT gate the day.** The RUN path uses :func:`gated_minute_loader`, which
    puts the CONTEXT 4.5/4.6 battery in front of this one (QUESTIONS.md Q-21(b)); the bare
    loader is what the evidence scripts and the unit tests exercise when the question is the
    BAR rather than the day. It DOES drop out-of-session stamps, because that is
    :func:`candles_for`'s job and Q-22(a) binds every consumer, not every gated consumer.
    """

    def load(symbol: str, day: date):
        bars = store.minutes(symbol, day)
        if not bars:
            return None
        candles, dropped = candles_for(symbol, day, bars)
        if drops is not None:
            drops.record(symbol, day, dropped)
        return candles

    return load


def candles_for(symbol: str, day: date, bars: Sequence) -> tuple[tuple[Candle, ...], int]:
    """Stored 1-minute bars -> ``(bias.Candle objects, how many strays were dropped)``.

    The one place on the run path that turns stored bars into candles, so it is the one place
    a vendor-corrupt bar can be NAMED (QUESTIONS.md Q-21). Both loaders above call it, which is
    what keeps the gated and ungated paths building identical candles from identical bytes.

    **The CONTEXT 7-E2 / Q-17 drop happens HERE, before a single candle is built**
    (QUESTIONS.md **Q-22(a)**, architect 03-Aug-2026): *"Q-17's candle-level drop binds EVERY
    consumer of stored minute bars, the Rule-3 first-break scan included ... where the only
    break lives in stray bars the scan finds NO break and the day carries -- the engine's
    existing honest answer, no invention."* Until that ruling this function built a candle for
    every stored bar, so a stamp outside 09:15..15:29 could decide which of P's extremes broke
    FIRST and therefore the day's bias and the day's trade direction (CONTEXT 3.4) -- measured
    on the real store, a 15:44 print on the 2021-02-24 outage day flipped GODREJCP and
    LAURUSLABS (REVIEW_9B_FIXES R1).

    The count is RETURNED rather than swallowed for the reason
    :func:`acumen.aggregate.in_session_bars` gives: a caller that dropped candles silently would
    hide vendor damage, and Q-17 requires the drop to be flagged and counted. The callers pass
    it to a :class:`Rule3SessionDrops`, which is what puts it on the trade day's ledger row.

    Dropping first also means a malformed bar OUTSIDE the session is never built and therefore
    never named: it is a stray, and a stray is dropped. Q-21's third case survives for
    in-session bars only -- where the completed gate 2 (Q-21(a)) already refuses the day on the
    gated path -- which is exactly what the ruling's option (a) predicted.
    """
    session, dropped = in_session_bars(bars)
    candles: list[Candle] = []
    for bar in session:
        try:
            candles.append(
                Candle(
                    open=int(bar.open_paise),
                    high=int(bar.high_paise),
                    low=int(bar.low_paise),
                    close=int(bar.close_paise),
                    stamp=bar.stamp,
                    day=bar.stamp.date(),
                )
            )
        except BiasError as exc:
            raise MalformedMinuteBar(
                symbol=symbol,
                day=day,
                stamp=bar.stamp,
                open_paise=int(bar.open_paise),
                high_paise=int(bar.high_paise),
                low_paise=int(bar.low_paise),
                close_paise=int(bar.close_paise),
                volume=int(bar.volume),
            ) from exc
    return tuple(candles), dropped


def iter_trading_days(calendar: TradingCalendar, start: date, end: date) -> Iterable[date]:
    """Every trading day in ``[start, end]`` the calendar knows, oldest first."""
    current = start
    while current <= end:
        if calendar.is_trading_day(current):
            yield current
        current += timedelta(days=1)
