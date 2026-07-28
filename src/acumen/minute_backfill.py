"""Resumable single-symbol 1-minute backfill + the quality-gate report (chunk 5A).

This is the operator's front end to the intraday layer -- the intraday twin of
:mod:`acumen.backfill_daily`. It ties together the pieces that do the real work:

* :mod:`acumen.smartapi_client` -- the paced, backing-off, session-refreshing candle fetcher;
* :mod:`acumen.instrument_master` -- symbol -> token and per-symbol tick;
* :mod:`acumen.minute_store` -- the Parquet 1-minute store and its window ledger;
* :mod:`acumen.quality_gates` -- CONTEXT 4.5 gates 1-3;
* :mod:`acumen.aggregate` -- 15-minute bars (CONTEXT 7-E1/E12);
* :mod:`acumen.daily_store` -- the RAW daily volumes gate 1 reconciles against, and the RAW
  daily prices gate 3 (OPEN-8) compares the 1-minute feed to.

CONTEXT 4.3 depth: 1-minute history begins **2016-10** (later for newer listings), so the
per-symbol backfill start clamps to :data:`MINUTE_DATA_FLOOR` -- a window entirely before it
returns empty without a request (RESULTS.md B; the chunk-5A "clamp" golden). The window walk
is 30 calendar days (the ONE_MINUTE request cap), resumable via the window ledger.

It also exposes :func:`minute_loader`, the REAL implementation of the ``MinuteLoader`` interface
chunk 4 defined (:mod:`acumen.bias_engine`): ``(symbol, date) -> 1-minute candles or None``, so
the bias engine's Rule 3 finally reads real data instead of a fixture.

The live run itself is a SCRIPT (``main``), not a test: it makes real SmartAPI pulls behind an
explicit ``--allow-network`` and reads credentials from ``.env`` via the config loader. The
pytest suite stays fully offline (the client and gates are all injectable / pure).

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Callable, Sequence

from . import corp_actions as ca
from . import minute_unadjust as unadj
from . import quality_gates as gates
from . import smartapi_client as sac
from . import vendor_adjustment as va
from .adjustment_route import classify_route, map_covers_route
from .aggregate import aggregate_15min
from .bias import Candle
from .bias_engine import MinuteLoader
from .daily_store import DailyStore, DailyStoreError
from .instrument_master import InstrumentMaster, InstrumentMasterError, load_instrument_master
from .minute_store import (
    MinuteStore,
    StoredBar,
    WINDOW_EMPTY,
    WINDOW_ERROR,
    WINDOW_PRESENT,
    WindowOutcome,
)

#: CONTEXT 4.3 / RESULTS.md B: real 1-minute depth begins October 2016 for established stocks.
#: Per-symbol backfill start = max(this, the symbol's first data); requesting earlier returns
#: empty without error.
MINUTE_DATA_FLOOR: date = date(2016, 10, 1)

#: The ONE_MINUTE fetch window, in calendar days. CONTEXT 4.3 caps the DATE range at 30, but
#: the live PoC (2026-07-25) found SmartAPI ALSO caps the RESPONSE at 8000 candles
#: (:data:`acumen.smartapi_client.ONE_MINUTE_RESPONSE_CAP`) and silently drops the oldest when
#: a window exceeds it. Any 28 consecutive calendar days hold at most 20 weekdays (four whole
#: weeks) -> at most 20 trading days x 375 = 7500 candles, comfortably under 8000 even with a
#: Muhurat session's extra evening candles in the window. So 28 days can never truncate, while
#: 30 does. Fewer than ~22 trading days per request also keeps the request count modest.
ONE_MINUTE_WINDOW_DAYS: int = 28

#: The three self-contained corporate-action events chunk 5A's gate 3 uses to settle OPEN-8
#: (SmartAPI 1-minute: raw or pre-adjusted?). Named in the card. KOTHARIPRO/GREENPLY predate
#: the 1-minute floor, so only RELIANCE (2024) can actually yield a verdict -- the other two are
#: attempted honestly and recorded INDETERMINATE if no pre-ex 1-minute data exists.
@dataclass(frozen=True)
class AdjustmentEvent:
    symbol: str
    ex_date: date
    description: str


OPEN8_EVENTS: tuple[AdjustmentEvent, ...] = (
    AdjustmentEvent("KOTHARIPRO", date(2016, 1, 5), "bonus ex 2016-01-05"),
    AdjustmentEvent("GREENPLY", date(2016, 1, 6), "face-value split ex 2016-01-06"),
    AdjustmentEvent("RELIANCE", date(2024, 10, 28), "1:1 bonus ex 2024-10-28"),
)


# --- the per-symbol factor table used to un-adjust on ingest (Q-10) --------------------


@dataclass(frozen=True)
class SymbolFactors:
    """Everything the ingest path needs to un-adjust one symbol's minutes back to RAW (Q-10).

    Assembled by :func:`build_symbol_factors` from the symbol's CONTEXT 4.2 corporate-action
    history (with cum-closes read from the raw daily store) and its instrument-master tick.
    The empty default (:data:`NO_FACTORS` via ``SymbolFactors.identity``) makes un-adjustment
    the exact identity -- correct for a symbol with no split/bonus/rights in the window, and the
    behaviour the offline tests rely on when they inject bars directly.
    """

    symbol: str
    factors: tuple[ca.Factor, ...] = ()
    suppressions: tuple[ca.Suppression, ...] = ()
    pending_ex_dates: tuple[date, ...] = ()
    tick_paise: int | None = None

    @classmethod
    def identity(cls, symbol: str, *, tick_paise: int | None = None) -> "SymbolFactors":
        return cls(symbol=symbol.strip().upper(), tick_paise=tick_paise)


@dataclass(frozen=True)
class SymbolCorpActions:
    """One symbol's whole chunk-3 corporate-action picture -- factors AND what did not resolve.

    :class:`SymbolFactors` carries only what the un-adjustment arithmetic consumes. The ROUTING
    rule (QUESTIONS.md Q-11 addendum, :mod:`acumen.adjustment_route`) also has to see what did
    NOT resolve -- a pending factor, an unparsed subject -- because those force the map path
    conservatively. This is the fuller view; :meth:`symbol_factors` narrows it back down.
    """

    symbol: str
    factors: tuple[ca.Factor, ...] = ()
    suppressions: tuple[ca.Suppression, ...] = ()
    pending: tuple[ca.PendingFactor, ...] = ()
    pending_rights_ex_dates: tuple[date, ...] = ()
    parse_exceptions: tuple[ca.ParseException, ...] = ()

    def symbol_factors(self, *, tick_paise: int | None = None) -> SymbolFactors:
        return SymbolFactors(
            symbol=self.symbol,
            factors=self.factors,
            suppressions=self.suppressions,
            pending_ex_dates=self.pending_rights_ex_dates,
            tick_paise=tick_paise,
        )


def corp_actions_for_symbol(
    symbol: str,
    actions: Sequence[ca.CorporateAction],
    daily_store: DailyStore,
) -> SymbolCorpActions:
    """Build one symbol's CONTEXT 4.2 factor table from already-fetched raw actions.

    Split out of :func:`build_symbol_factors` so the universe run (chunk 5B) can fetch the NSE
    corporate-action history ONCE for all years and reuse it across ~210 symbols instead of
    re-fetching and re-parsing the whole market per symbol.

    Cum-date closes come from the RAW daily store, so bonus/split/rights/special-dividend
    factors are concrete. Demergers and Q-6-unrecoverable rights come back as suppressions; a
    factor that needs a price we do not hold comes back pending.
    """
    sym = symbol.strip().upper()
    report = ca.parse_actions([a for a in actions if a.symbol == sym])

    def cum_close(lookup_symbol: str, ex_date: date) -> int | None:
        prev = _last_daily_before(daily_store, lookup_symbol, ex_date)
        if prev is None:
            return None
        frame = daily_store.daily(lookup_symbol, prev, prev)
        return None if frame.empty else int(frame.iloc[0]["close_paise"])

    try:
        overrides = ca.load_rights_overrides()
    except ca.CorporateActionError:
        overrides = {}
    table = ca.build_factor_table(report.events, cum_close=cum_close, rights_overrides=overrides)
    pending_rights = tuple(
        sorted({p.event.ex_date for p in table.pending if p.event.kind == ca.KIND_RIGHTS})
    )
    return SymbolCorpActions(
        symbol=sym,
        factors=table.factors,
        suppressions=table.suppressions,
        pending=table.pending,
        pending_rights_ex_dates=pending_rights,
        parse_exceptions=report.exceptions,
    )


def fetch_corp_action_history(
    start: date,
    end: date,
    *,
    allow_network: bool = False,
    cache_dir: Path | None = None,
    today: date | None = None,
) -> tuple[ca.CorporateAction, ...]:
    """The NSE corporate-action rows covering ``[start.year, end.year]``, one year per request.

    Day-cached and opt-in (CONTEXT 4.2): with ``allow_network=False`` this reads only the
    day-cache, so a reviewer with the frozen cache gets a deterministic history and a bare clone
    gets an empty one.
    """
    actions: list[ca.CorporateAction] = []
    for year in range(start.year, end.year + 1):
        actions.extend(
            ca.fetch_nse_corporate_actions(
                date(year, 1, 1),
                date(year, 12, 31),
                allow_network=allow_network,
                cache_dir=cache_dir,
                today=today,
            )
        )
    return tuple(actions)


def build_symbol_factors(
    symbol: str,
    start: date,
    end: date,
    daily_store: DailyStore,
    *,
    allow_network: bool = False,
    cache_dir: Path | None = None,
    today: date | None = None,
    tick_paise: int | None = None,
) -> SymbolFactors:
    """Assemble ``symbol``'s Q-10 un-adjustment factor table over ``[start.year, end.year]``.

    Pulls the NSE corporate-action history one year per request (the day-cached, opt-in fetcher
    -- CONTEXT 4.2), parses it, and builds the CONTEXT 4.2 factor table with cum-date closes
    read from the RAW daily store (so bonus/split/rights/special-dividend factors are all
    concrete). Demergers and Q-6-pending rights come back as suppressions / pending ex-dates:
    the vendor adjusts by factors we do not hold there, so those spans are un-provable (gate 1
    excludes and counts them; a systematic pre-event span moves the clamp).

    Network is opt-in: with ``allow_network=False`` this reads only the day-cache, so a reviewer
    with the frozen cache gets a deterministic table and a bare clone gets an empty one.
    """
    actions = fetch_corp_action_history(
        start, end, allow_network=allow_network, cache_dir=cache_dir, today=today
    )
    view = corp_actions_for_symbol(symbol, actions, daily_store)
    return view.symbol_factors(tick_paise=tick_paise)


# --- clamp + window planning (PURE) ----------------------------------------------------


def clamp_start(requested_start: date, first_data: date | None = None) -> date:
    """The per-symbol backfill start: ``max(MINUTE_DATA_FLOOR, requested, first_data)``. PURE."""
    candidates = [MINUTE_DATA_FLOOR, requested_start]
    if first_data is not None:
        candidates.append(first_data)
    return max(candidates)


def plan_windows(
    requested_start: date, end: date, *, first_data: date | None = None
) -> list[tuple[date, date]]:
    """The 30-day windows to fetch, clamped to the 1-minute floor. PURE.

    A request whose whole range is before :data:`MINUTE_DATA_FLOOR` yields an EMPTY list -- the
    "requesting pre-2016-09 returns empty without error" golden.
    """
    start = clamp_start(requested_start, first_data)
    if end < start:
        return []
    return sac.one_minute_windows(start, end, days=ONE_MINUTE_WINDOW_DAYS)


# --- the resumable backfill ------------------------------------------------------------


@dataclass
class BackfillProgress:
    """Running totals for the operator's progress line."""

    windows_total: int = 0
    windows_done: int = 0
    present: int = 0
    empty: int = 0
    error: int = 0
    candles: int = 0
    unprovable_days: int = 0
    tick_flagged_days: int = 0


@dataclass
class BackfillResult:
    """The outcome of backfilling one symbol."""

    symbol: str
    windows_planned: int
    windows_attempted: int
    ledger_summary: dict[str, int]
    first_stored_date: date | None
    errors: list[tuple[date, date, str]] = field(default_factory=list)
    #: Q-10 un-adjustment diagnostics accumulated across the fetched windows.
    unprovable_days: list[date] = field(default_factory=list)
    tick_flagged_days: list[date] = field(default_factory=list)


def backfill_symbol(
    client: sac.SmartApiClient,
    master: InstrumentMaster,
    store: MinuteStore,
    symbol: str,
    requested_start: date,
    end: date,
    *,
    symbol_factors: SymbolFactors | None = None,
    adjustment_map: "va.AdjustmentMap | None" = None,
    retry_errors: bool = True,
    now: Callable[[], datetime] = datetime.now,
    on_progress: Callable[[BackfillProgress, date, date, str], None] | None = None,
) -> BackfillResult:
    """Download ``symbol``'s 1-minute candles over ``[requested_start, end]``, resumably.

    Walks the clamped 30-day windows, skips windows already settled in the ledger, fetches the
    rest, UN-ADJUSTS each window back to RAW, stores the raw candles and records each window's
    outcome incl. its fetch date. Safe to interrupt and re-run: a settled window is never
    refetched, an ``error`` window is retried next time.

    Un-adjustment path: when an ``adjustment_map`` is given (the Q-11 per-event MEASURED
    reconstruction, :mod:`acumen.vendor_adjustment`), each window is un-adjusted THROUGH the map
    -- the correct path for a symbol whose vendor adjustment is era-inconsistent (a demerger baked
    into some eras but not others). Without one it falls back to the Q-10 factor-table un-adjust
    (``symbol_factors``), which is exact for a symbol with only clean bonus/split factors (e.g.
    TCS). ``symbol_factors`` still supplies the tick for both paths.
    """
    token = master.token(symbol)
    factors = symbol_factors or SymbolFactors.identity(symbol)
    windows = plan_windows(requested_start, end)
    pending = store.pending_windows(symbol, windows, retry_errors=retry_errors)

    progress = BackfillProgress(windows_total=len(pending))
    errors: list[tuple[date, date, str]] = []
    unprovable: list[date] = []
    tick_flagged: list[date] = []

    for window_start, window_end in pending:
        outcome, diag = _fetch_and_store_window(
            client, store, symbol, token, window_start, window_end, factors, now, adjustment_map
        )
        store.record_window(outcome)
        progress.windows_done += 1
        if outcome.outcome == WINDOW_PRESENT:
            progress.present += 1
            progress.candles += outcome.candle_count or 0
            unprovable.extend(diag.unprovable_days)
            tick_flagged.extend(diag.tick_flagged_days)
            progress.unprovable_days = len(unprovable)
            progress.tick_flagged_days = len(tick_flagged)
        elif outcome.outcome == WINDOW_EMPTY:
            progress.empty += 1
        else:
            progress.error += 1
            errors.append((window_start, window_end, outcome.reason or "error"))
        if on_progress is not None:
            on_progress(progress, window_start, window_end, outcome.outcome)

    return BackfillResult(
        symbol=symbol.strip().upper(),
        windows_planned=len(windows),
        windows_attempted=len(pending),
        ledger_summary=store.ledger_summary(symbol),
        first_stored_date=store.first_stored_date(symbol),
        errors=errors,
        unprovable_days=sorted(set(unprovable)),
        tick_flagged_days=sorted(set(tick_flagged)),
    )


def _fetch_and_store_window(
    client: sac.SmartApiClient,
    store: MinuteStore,
    symbol: str,
    token: str,
    window_start: date,
    window_end: date,
    symbol_factors: SymbolFactors,
    now: Callable[[], datetime],
    adjustment_map: "va.AdjustmentMap | None" = None,
) -> tuple[WindowOutcome, unadj.UnadjustResult]:
    sym = symbol.strip().upper()
    when = now()
    fetch_date = when.date()
    from_dt = datetime.combine(window_start, dtime(9, 15))
    to_dt = datetime.combine(window_end, dtime(15, 30))
    empty = unadj.UnadjustResult(raw_bars=(), days=())
    try:
        bars = client.get_candles(token, sac.INTERVAL_ONE_MINUTE, from_dt, to_dt)
    except sac.SmartApiError as exc:
        return (
            WindowOutcome(
                symbol=sym,
                window_start=window_start,
                window_end=window_end,
                outcome=WINDOW_ERROR,
                reason=str(exc),
                attempted_at=when,
                fetch_date=fetch_date,
            ),
            empty,
        )
    if not bars:
        return (
            WindowOutcome(
                symbol=sym,
                window_start=window_start,
                window_end=window_end,
                outcome=WINDOW_EMPTY,
                candle_count=0,
                reason="no candles in window (before listing or suspended)",
                attempted_at=when,
                fetch_date=fetch_date,
            ),
            empty,
        )
    # Un-adjust the fetched (CA-back-adjusted) window back to RAW before it is stored. Q-11 map
    # path when available (per-event MEASURED, era-inconsistency-aware); else the Q-10 factor-table.
    if adjustment_map is not None:
        result = va.unadjust_with_map(
            bars, adjustment_map, symbol=sym, tick_paise=symbol_factors.tick_paise
        )
    else:
        result = unadj.unadjust_bars(
            bars,
            factors=symbol_factors.factors,
            fetch_date=fetch_date,
            symbol=sym,
            tick_paise=symbol_factors.tick_paise,
            suppressions=symbol_factors.suppressions,
            pending_ex_dates=symbol_factors.pending_ex_dates,
        )
    store.write_bars(sym, result.raw_bars)
    dates = sorted({b.stamp.date() for b in result.raw_bars})
    reason = _window_reason(len(bars), result)
    return (
        WindowOutcome(
            symbol=sym,
            window_start=window_start,
            window_end=window_end,
            outcome=WINDOW_PRESENT,
            candle_count=len(result.raw_bars),
            first_date=dates[0],
            last_date=dates[-1],
            reason=reason,
            attempted_at=when,
            fetch_date=fetch_date,
        ),
        result,
    )


def _window_reason(fetched_count: int, result: unadj.UnadjustResult) -> str | None:
    """The ledger ``reason`` for a stored window: the 8000-cap warning + un-adjust diagnostics."""
    parts: list[str] = []
    # Safety net for the 8000-candle response cap: with a 28-day window this cannot fire, but
    # if a future caller widens the window and the server drops the oldest candles, flag it so
    # the truncation is visible in the ledger rather than silent. Gate 2 also excludes the
    # resulting partial first-day, so no truncated day ever reaches the backtest either way.
    if fetched_count >= sac.ONE_MINUTE_RESPONSE_CAP:
        parts.append(
            f"WARNING: {fetched_count} candles >= the {sac.ONE_MINUTE_RESPONSE_CAP} response "
            "cap; the oldest candles may have been dropped -- narrow the window"
        )
    unprovable = result.unprovable_days
    if unprovable:
        parts.append(f"un-provable days (gate-1 will exclude): {len(unprovable)}")
    flagged = result.tick_flagged_days
    if flagged:
        parts.append(f"tick-grid-flagged days (vendor rounding > tol): {len(flagged)}")
    return "; ".join(parts) or None


# --- the REAL chunk-4 minute loader ----------------------------------------------------


def minute_loader(store: MinuteStore) -> MinuteLoader:
    """The production ``MinuteLoader`` (chunk-4 interface) over the 1-minute store.

    ``(symbol, date) -> tuple[Candle, ...] | None``: the day's stored 1-minute candles as
    :class:`acumen.bias.Candle` (integer paise, open-stamped, in time order), or ``None`` when
    the store has no candles for that day -- which is exactly the "no 1-minute data (old dates)"
    case CONTEXT 3.2 / R1-Q6 says the bias engine must carry the last bias through. This finally
    gives Rule 3 real data (chunk-4 shipped the interface with a CSV-fixture stand-in).
    """

    def load(symbol: str, day: date) -> Sequence[Candle] | None:
        bars = store.minutes(symbol, day)
        if not bars:
            return None
        return tuple(
            Candle(
                open=b.open_paise,
                high=b.high_paise,
                low=b.low_paise,
                close=b.close_paise,
                stamp=b.stamp,
                day=b.trade_date,
            )
            for b in bars
        )

    return load


# --- gate reports over the store -------------------------------------------------------


def daily_ohlc_from_minutes(bars: Sequence[StoredBar]) -> dict[str, int]:
    """Fold one day's 1-minute bars into a daily OHLC (integer paise). PURE-ish (no I/O)."""
    ordered = sorted(bars, key=lambda b: b.stamp)
    return {
        "open_paise": ordered[0].open_paise,
        "high_paise": max(b.high_paise for b in ordered),
        "low_paise": min(b.low_paise for b in ordered),
        "close_paise": ordered[-1].close_paise,
    }


def gate1_for_day(
    daily_store: DailyStore, minute_store: MinuteStore, symbol: str, day: date
) -> gates.VolumeGateResult | None:
    """Gate 1 for one symbol-day; ``None`` when the daily store has no row to reconcile against."""
    frame = daily_store.daily(symbol, day, day)
    if frame.empty:
        return None
    daily_volume = int(frame.iloc[0]["volume"])
    minute_volume = sum(int(b.volume) for b in minute_store.minutes(symbol, day))
    return gates.volume_gate(daily_volume, minute_volume)


def gate2_for_day(minute_store: MinuteStore, symbol: str, day: date) -> gates.IntegrityGateResult:
    """Gate 2 for one symbol-day."""
    return gates.integrity_gate(minute_store.minutes(symbol, day), day)


# --- rebuild an already-fetched store to RAW + the Q-10 acceptance (read-only) ----------


def fetch_date_for_day(store: MinuteStore, symbol: str, day: date) -> date | None:
    """The fetch date F of the window covering ``day`` (``fetch_date``, else ``attempted_at``)."""
    for outcome in store.window_outcomes(symbol).values():
        if outcome.window_start <= day <= outcome.window_end and outcome.outcome == WINDOW_PRESENT:
            if outcome.fetch_date is not None:
                return outcome.fetch_date
            if outcome.attempted_at is not None:
                return outcome.attempted_at.date()
    return None


def unadjust_stored_day(
    store: MinuteStore,
    symbol: str,
    day: date,
    symbol_factors: SymbolFactors,
    *,
    fetch_date: date | None = None,
) -> tuple[StoredBar, ...]:
    """Read a stored (as-fetched/adjusted) day and return its RAW bars IN MEMORY (read-only).

    The migration primitive: it does NOT write. ``fetch_date`` defaults to the ledger's recorded
    F for the window covering ``day`` (:func:`fetch_date_for_day`), because ``k_cum`` is
    fetch-dated. Used by :func:`rebuild_symbol_raw` (which then writes) and by the acceptance
    checks (which only read).
    """
    stored = store.minutes(symbol, day)
    if not stored:
        return ()
    fd = fetch_date or fetch_date_for_day(store, symbol, day)
    if fd is None:
        raise DailyStoreError(
            f"{symbol} {day}: no fetch date recorded for the covering window; cannot un-adjust "
            "(k_cum is fetch-dated). Re-pull the window so its fetch date is recorded."
        )
    as_fetched = [
        sac.OneMinuteBar(b.stamp, b.open_paise, b.high_paise, b.low_paise, b.close_paise, b.volume)
        for b in stored
    ]
    result = unadj.unadjust_bars(
        as_fetched,
        factors=symbol_factors.factors,
        fetch_date=fd,
        symbol=symbol,
        tick_paise=symbol_factors.tick_paise,
        suppressions=symbol_factors.suppressions,
        pending_ex_dates=symbol_factors.pending_ex_dates,
    )
    sym = symbol.strip().upper()
    return tuple(
        StoredBar(sym, rb.stamp, rb.open_paise, rb.high_paise, rb.low_paise, rb.close_paise, rb.volume)
        for rb in result.raw_bars
    )


@dataclass
class RebuildResult:
    """The outcome of un-adjusting an already-fetched store to RAW in place."""

    symbol: str
    days_rewritten: int
    identity_days: int
    unadjusted_days: int
    unprovable_days: list[date] = field(default_factory=list)
    tick_flagged_days: list[date] = field(default_factory=list)
    #: Days whose stored bars match NO known baseline (:data:`BASELINE_UNKNOWN`). Left untouched --
    #: no factor is guessed -- and excluded + counted by gate 1 (CONTEXT 7-E3).
    unknown_baseline_days: list[date] = field(default_factory=list)


def rebuild_symbol_raw(
    store: MinuteStore, symbol: str, symbol_factors: SymbolFactors
) -> RebuildResult:
    """Un-adjust an already-fetched (adjusted) store to RAW IN PLACE, day by day (Q-10).

    This is the one-time migration for a store built before Q-10: it reads each stored day,
    un-adjusts it against the factor table using the window's recorded fetch date, and writes
    the raw bars back (per-date replacement -- :meth:`MinuteStore.write_bars`). NOT idempotent
    against re-running on an ALREADY-raw store (it would divide a second time), so it is run once
    and only on an adjusted store; the clean, idempotent alternative is a fresh re-pull through
    the (now un-adjusting) ingest path. The candles are gitignored and reproducible either way.
    """
    sym = symbol.strip().upper()
    # Q-10 ADDENDUM 2: demergers are filtered out here (the 1-minute feed is not
    # demerger-adjusted); only tier-2 unrecoverable rights mark a minute day un-provable.
    supp_dates = unadj.unprovable_suppression_dates(symbol_factors.suppressions)
    pend_dates = sorted(symbol_factors.pending_ex_dates)
    result = RebuildResult(symbol=sym, days_rewritten=0, identity_days=0, unadjusted_days=0)
    for day in store.stored_days(sym):
        fd = fetch_date_for_day(store, sym, day)
        stored = store.minutes(sym, day)
        if not stored or fd is None:
            continue
        k_price = unadj.cumulative_factor(symbol_factors.factors, day, fd, symbol=sym)
        k_shares = unadj.cumulative_factor(
            symbol_factors.factors, day, fd, symbol=sym, kinds=ca.SHARE_COUNT_KINDS
        )
        if unadj._unknown_factor_between(day, fd, supp_dates, pend_dates) is not None:  # noqa: SLF001
            result.unprovable_days.append(day)  # gate-1 excludes it; count regardless of the skip
        if k_price == Decimal(1) and k_shares == Decimal(1):
            # A recent (post-last-CA) day is already RAW as fetched -- no rewrite needed. Skipping
            # it keeps the migration to the handful of days that actually change (and avoids
            # rewriting thousands of identical files, which is also what a flaky Windows
            # os.replace trips over). The write path is idempotent, so this is safe to re-run.
            # BOTH factors must be 1: a special dividend leaves k_shares==1 but k_price<1 (price
            # still needs dividing), so k_price alone would wrongly skip such a day (FIX-2).
            result.identity_days += 1
            continue
        raw = unadjust_stored_day(store, sym, day, symbol_factors, fetch_date=fd)
        store.write_bars(sym, raw)
        result.days_rewritten += 1
        result.unadjusted_days += 1
    return result


#: A stored day counts as "already raw" only if its fold high/low sit within this fraction of the
#: raw daily (0.1% -- absorbs market microstructure, well below the smallest adjustment factor).
#: Used only by :func:`_stored_day_is_raw`, which has NO caller in ``src/`` (REVIEW_5B finding C12).
_RAW_PRICE_REL_TOL: Decimal = Decimal("0.001")

#: Outer bound on how far a fold/raw ratio may sit from a hypothesis and still be recognised as it
#: (:func:`stored_day_baseline`). 2% comfortably absorbs the fold-vs-bhavcopy microstructure
#: difference -- the bhavcopy's high/low can include a pre-open auction or block-window print that
#: never appears in a continuous 1-minute candle -- while staying far inside the gap between the
#: hypotheses for every real factor. Measured live: ASHOKLEY has 37 raw days whose fold high sits
#: 0.1%-0.5% off the bhavcopy high, which a 0.1% test wrongly calls "not raw".
_BASELINE_MATCH_TOL: Decimal = Decimal("0.02")

BASELINE_RAW: str = "raw"                    # stored == raw; nothing to do
BASELINE_AS_FETCHED: str = "as-fetched"      # stored == the vendor's bars; divide by the map's k
BASELINE_OVER_DIVIDED: str = "over-divided"  # stored == raw / k; multiply BACK by k
#: stored == raw / k^2 -- divided by the SAME chain twice. Not hypothetical: the superseded one-way
#: "is this day raw?" rebuild (see :data:`acumen.universe_backfill.REBUILD_DISCIPLINE`) divided a
#: day that was already un-adjusted, and where that happened on a span the vendor had never
#: adjusted at all (a vendor APPLICATION FLOOR, QUESTIONS.md Q-11 addendum 2) the damage compounds:
#: CANBK's pre-2022-05-10 days sit at exactly 25x the raw price and 0.04x the raw volume, i.e.
#: 1/k^2 for its k = 0.2 split. One more well-separated hypothesis repairs them exactly.
BASELINE_OVER_DIVIDED_TWICE: str = "over-divided-twice"
#: stored == raw x (k_target / k_era) -- the store was un-adjusted by the PRE-FLOOR era chain while
#: the vendor had only ever applied the post-floor one. This is the shape a newly-measured vendor
#: APPLICATION FLOOR leaves behind on an already-stored day when the floor drops SOME of the chain
#: rather than all of it (RELIANCE: the 2023 demerger floored at 2022-01-05 leaves the older stored
#: days at 1/0.908 of raw). Correction: multiply BACK by ``k_era / k_target``.
BASELINE_PRE_FLOOR_DIVIDED: str = "pre-floor-divided"
#: stored == raw x (k_era / k_target) -- the vendor DID apply the full era chain to this day while we
#: un-adjusted by the floored one, i.e. the floor does not hold here. Correction: divide by
#: ``k_era / k_target``. Kept as a hypothesis precisely so a wrong floor still lands on raw instead
#: of quietly storing a scaled price.
BASELINE_FLOOR_OVERREACHED: str = "floor-overreached"
#: stored == raw x k_target -- the vendor's OWN bars, still untouched, on a day whose chain a floor
#: has reduced. This is the shape of every day of an era that was un-provable until a floor made it
#: provable (QUESTIONS.md Q-11 addendum 4): nothing ever corrected those days, so they sit at the
#: chain the VENDOR applied, which is no longer the era chain the hypotheses are generated from.
#: Correction: divide by ``k_target``, exactly like :data:`BASELINE_AS_FETCHED`. Without this
#: hypothesis a promoted era classifies UNKNOWN and the floor repairs nothing.
BASELINE_AS_FETCHED_FLOORED: str = "as-fetched-floored"
BASELINE_UNKNOWN: str = "unknown"            # matches no hypothesis; NEVER touched, gate 1 decides


def stored_day_baseline(
    stored: Sequence[StoredBar],
    daily_row,
    k_price: Decimal,
    k_volume: Decimal,
    *,
    k_price_target: Decimal | None = None,
    k_volume_target: Decimal | None = None,
) -> str:
    """Where does a stored symbol-day sit relative to raw? PURE-ish (no I/O).

    A rebuild must not ask "is this day raw?" and divide whenever the answer is no -- that turns any
    day the test misjudges into a day divided twice. It asks instead WHICH of a small set of
    well-separated, known baselines the day is on, and refuses to touch a day that matches none.

    The observable is the price fold ratio ``fold_high / raw_daily_high`` (and the same for the low),
    which is exact -- unlike volume, it carries no auction shortfall. Against a map factor
    ``k_price`` the hypotheses are:

    * ``1``          -> :data:`BASELINE_RAW` -- already un-adjusted; skip it;
    * ``k_price``    -> :data:`BASELINE_AS_FETCHED` -- still the vendor's bars; divide by ``k_price``;
    * ``1/k_price``  -> :data:`BASELINE_OVER_DIVIDED` -- divided one time too many; multiply BACK;
    * ``1/k_price^2``-> :data:`BASELINE_OVER_DIVIDED_TWICE` -- divided twice too many; multiply back
      by ``k_price^2``.

    The last two are not curiosities: they make the rebuild idempotent BY CONSTRUCTION rather than
    by bookkeeping, and they are as well-determined as the first two (for a 1:1 bonus the four
    ratios are 1, 0.5, 2 and 4). ``over-divided`` is also right on a vendor that FORWARD-adjusted a
    day: multiplying by ``k`` lands on raw either way. ``over-divided-twice`` is what the superseded
    one-way rebuild left behind on a span the vendor never adjusted at all.

    When a vendor APPLICATION FLOOR (QUESTIONS.md Q-11 addendum 2) makes the day's own chain
    ``k_target`` differ from its era chain ``k_price``, two further provenances become reachable and
    are named rather than refused:

    * ``k_target / k_price`` -> :data:`BASELINE_PRE_FLOOR_DIVIDED` -- the store was un-adjusted by
      the PRE-floor chain while the vendor had only applied the post-floor one; multiply BACK by
      ``k_price / k_target``;
    * ``k_price / k_target`` -> :data:`BASELINE_FLOOR_OVERREACHED` -- the vendor DID apply the full
      chain here, so the floor does not hold for this day; divide by ``k_price / k_target``. Keeping
      this hypothesis is what stops a wrong floor from quietly storing a scaled price;
    * ``k_target`` -> :data:`BASELINE_AS_FETCHED_FLOORED` -- the vendor's own untouched bars on a
      floored day (every day of an era a floor just made provable); divide by ``k_target``.

    The winner is the nearest hypothesis in RELATIVE terms, and it must sit within
    ``min(2%, half the closest gap between any two hypotheses)`` -- so no two can ever both claim a
    ratio, however close a floored factor happens to sit to 1. Anything else is
    :data:`BASELINE_UNKNOWN`: the day's provenance is lost, no factor is guessed, and gate 1
    excludes and counts it (CONTEXT 7-E3).

    ``k_price == 1`` carries no price information (the hypotheses coincide), so the volume ratio
    ``minute_sum / raw_daily_volume`` decides instead. With every factor 1 there is nothing to do at
    all and the day is :data:`BASELINE_RAW` by definition.
    """
    if k_price != Decimal(1) or (k_price_target is not None and k_price_target != k_price):
        raw_high = int(daily_row["high_paise"])
        raw_low = int(daily_row["low_paise"])
        if raw_high <= 0 or raw_low <= 0:
            return BASELINE_UNKNOWN
        ratios = [
            Decimal(max(b.high_paise for b in stored)) / Decimal(raw_high),
            Decimal(min(b.low_paise for b in stored)) / Decimal(raw_low),
        ]
        verdicts = {_nearest_baseline(ratio, k_price, k_price_target) for ratio in ratios}
        return verdicts.pop() if len(verdicts) == 1 else BASELINE_UNKNOWN
    if k_volume != Decimal(1) or (k_volume_target is not None and k_volume_target != k_volume):
        daily_volume = int(daily_row["volume"])
        if daily_volume <= 0:
            return BASELINE_UNKNOWN
        minute_volume = sum(int(b.volume) for b in stored)
        # Volume moves the OTHER way (raw = stored x k_volume), so as-fetched sits at 1/k_volume.
        return _nearest_baseline(
            Decimal(minute_volume) / Decimal(daily_volume),
            Decimal(1) / k_volume,
            None if k_volume_target is None else Decimal(1) / k_volume_target,
        )
    return BASELINE_RAW


def _nearest_baseline(ratio: Decimal, k: Decimal, k_target: Decimal | None = None) -> str:
    """Which named provenance is ``ratio`` on, else :data:`BASELINE_UNKNOWN`. PURE.

    Hypotheses are ``1`` / ``k`` / ``1/k`` / ``1/k^2``, plus -- when a vendor application floor makes
    the day's own chain ``k_target`` differ from its era chain ``k`` -- ``k_target/k`` and
    ``k/k_target``.

    Distance is RELATIVE (``|ratio/h - 1|``), not absolute: the hypotheses span orders of magnitude
    once ``k`` is small (1, 0.2, 5, 25 for a 5:1 split), and an absolute 2% would be an 8% test at
    0.2 and a 0.08% test at 25. Relative judges every hypothesis on the same footing.

    The tolerance is ``min(2%, half the closest relative gap between any two hypotheses)``, computed
    from the candidate set itself rather than assumed. That is what makes the set SAFE to extend: a
    floored factor sitting close to 1 tightens the tolerance automatically instead of letting two
    hypotheses both claim a ratio.
    """
    if k <= 0 or (k_target is not None and k_target <= 0):
        return BASELINE_UNKNOWN
    candidates = [
        (Decimal(1), BASELINE_RAW),
        (k, BASELINE_AS_FETCHED),
        (Decimal(1) / k, BASELINE_OVER_DIVIDED),
        (Decimal(1) / (k * k), BASELINE_OVER_DIVIDED_TWICE),
    ]
    if k_target is not None and k_target != k:
        candidates.append((k_target / k, BASELINE_PRE_FLOOR_DIVIDED))
        candidates.append((k / k_target, BASELINE_FLOOR_OVERREACHED))
        candidates.append((k_target, BASELINE_AS_FETCHED_FLOORED))
    # A hypothesis that COINCIDES with an earlier one is dropped rather than allowed to shrink the
    # derived tolerance to zero: two names for one ratio are not two hypotheses, and the first name
    # is the older, better-evidenced provenance.
    seen: set[Decimal] = set()
    candidates = [c for c in candidates if not (c[0] in seen or seen.add(c[0]))]
    values = [value for value, _name in candidates]
    gaps = [
        abs(a / b - Decimal(1))
        for i, a in enumerate(values) for b in values[i + 1:]
        if a != b
    ]
    tol = min([_BASELINE_MATCH_TOL, *[gap / Decimal(2) for gap in gaps]])
    distance, verdict = min(
        ((abs(ratio / value - Decimal(1)), name) for value, name in candidates),
        key=lambda item: item[0],
    )
    return verdict if distance <= tol else BASELINE_UNKNOWN


def baseline_correction(
    baseline: str,
    net_price: Decimal,
    net_volume: Decimal,
    target_price: Decimal,
    target_volume: Decimal,
) -> tuple[Decimal, Decimal] | None:
    """The multiple a classified day is currently stored at -- divide by it to reach RAW. PURE.

    One rule, applied to every provenance: a hypothesis NAMES the multiple of raw the stored bars sit
    at, so the repair is to divide by exactly that multiple (and to scale volume by its counterpart).
    That is what makes the rebuild idempotent by construction and what keeps a wrong floor from
    quietly storing a scaled price -- every branch lands on raw, or the day is left alone.

    ``net_*`` is the day's ERA chain (the hypotheses were generated from it) and ``target_*`` the
    day's own floor-reduced chain; on a map with no floors the two are equal and every branch below
    collapses to the pre-floor arithmetic exactly. Returns ``None`` for a baseline that must not be
    touched (:data:`BASELINE_RAW`, :data:`BASELINE_UNKNOWN`).
    """
    one = Decimal(1)
    if baseline == BASELINE_AS_FETCHED:
        return net_price, net_volume
    if baseline == BASELINE_AS_FETCHED_FLOORED:
        # The vendor's own bars on a floored day: what came out is what the vendor put in, which is
        # the day's OWN chain, not the era's.
        return target_price, target_volume
    if baseline == BASELINE_OVER_DIVIDED:
        # Divided one time too many by exactly this chain: multiply back. The ratios 1 / k / 1/k are
        # far enough apart that the classification is a measurement, not a fit.
        return one / net_price, one / net_volume
    if baseline == BASELINE_OVER_DIVIDED_TWICE:
        # Divided by the same chain twice (the superseded one-way rebuild, on a span the vendor had
        # never adjusted at all): the same repair, one power further out.
        return one / (net_price * net_price), one / (net_volume * net_volume)
    if baseline == BASELINE_PRE_FLOOR_DIVIDED:
        # Un-adjusted by the PRE-floor chain while the vendor had only applied the post-floor one:
        # multiply back by the part the floor removed.
        return target_price / net_price, target_volume / net_volume
    if baseline == BASELINE_FLOOR_OVERREACHED:
        # The vendor DID apply the full era chain here, so the floor does not hold for this day.
        return net_price / target_price, net_volume / target_volume
    return None


def _stored_day_is_raw(stored: Sequence[StoredBar], daily_row) -> bool:
    """Is a stored symbol-day ALREADY raw? Checks BOTH price and volume. PURE-ish (no I/O).

    **This function has NO caller in ``src/``** (REVIEW_5B finding C12). It is the ONE-WAY guard the
    FIX-2 map rebuild used before decision B108 replaced it with :func:`stored_day_baseline`, and
    the attribution that survived in B108's recorded text and in two ``src`` comments -- "the Q-10
    factor-table path" -- was never true: that path never called it either. It is kept, tested and
    named honestly rather than deleted, because a one-way "is this raw?" test is a genuinely useful
    predicate and the repo should hold ONE statement of it; what it must never again be is the thing
    that decides whether to DIVIDE a day.

    Volume must reconcile to the raw daily (gate 1), AND the stored fold high/low must match the raw
    daily high/low within :data:`_RAW_PRICE_REL_TOL` (0.1%). The map-backed rebuild uses
    :func:`stored_day_baseline` instead: a tight one-way test is safe when the alternative is "leave
    it alone" and dangerous when the alternative is "divide it", which is what this one used to be
    asked to decide.
    """
    daily_volume = int(daily_row["volume"])
    minute_volume = sum(int(b.volume) for b in stored)
    if not gates.volume_gate(daily_volume, minute_volume).passed:
        return False
    fold_high = max(b.high_paise for b in stored)
    fold_low = min(b.low_paise for b in stored)
    for fold, raw in ((fold_high, int(daily_row["high_paise"])), (fold_low, int(daily_row["low_paise"]))):
        if raw <= 0:
            return False
        if abs(Decimal(fold - raw)) > max(Decimal(2), Decimal(raw) * _RAW_PRICE_REL_TOL):
            return False
    return True


def net_map_factors(
    adjustment_map: "va.AdjustmentMap",
    day: date,
    applied: SymbolFactors | None,
    fetch_date: date | None,
    *,
    hypothesis: bool = False,
) -> tuple[Decimal, Decimal] | None:
    """The factors still to apply to a STORED day so it reaches the map's RAW. PURE.

    Returns ``(net_price, net_volume)`` -- divide the stored price by the first, multiply the stored
    volume by the second -- or ``None`` when the map cannot resolve the day (un-provable).

    With ``applied is None`` the stored bars are the vendor's AS-FETCHED bars, so the net factors are
    simply the map's own ``(k_price, k_volume)``.

    With ``applied`` given, the store was already un-adjusted once by the Q-10 FACTOR-TABLE chain at
    ingest -- the quarantine-recovery case (QUESTIONS.md Q-12 addendum: a table-path symbol rerouted
    through the map). There ``stored = fetched / k_table``, so the raw the map asks for is
    ``fetched / k_map == stored x k_table / k_map``, i.e. divide the STORED value by the NET factor
    ``k_map / k_table``. It is applied as ONE division, not a second full division on top of the
    first: two divisions would round twice and, worse, would divide by ``k_table`` a second time. A
    net factor of exactly 1 means the map agrees with the factor table -- the exact identity, and the
    day is left untouched.

    With ``hypothesis=True`` the map's ERA chain is used instead of the day's floor-reduced chain
    (:meth:`acumen.vendor_adjustment.AdjustmentMap.era_chain_for_day`). That is the set of factors
    that has ever been applied to this day by ANY pass -- ours or the vendor's -- and it is what the
    in-place rebuild must GENERATE its baseline hypotheses from: once a vendor application floor
    drops a day's own chain to 1, a store still holding that day under the PRE-floor chain would
    otherwise be unrecognisable and silently left uncorrected. The correction lands on RAW either
    way; the chain only supplies the candidate ratios.
    """
    factors = (
        adjustment_map.era_chain_for_day(day) if hypothesis
        else adjustment_map.factors_for_day(day)
    )
    if factors is None:
        return None
    k_price, k_volume = factors
    if applied is None or fetch_date is None:
        return k_price, k_volume
    sym = adjustment_map.symbol
    k_table_price = unadj.cumulative_factor(applied.factors, day, fetch_date, symbol=sym)
    k_table_volume = unadj.cumulative_factor(
        applied.factors, day, fetch_date, symbol=sym, kinds=ca.SHARE_COUNT_KINDS
    )
    if k_table_price <= 0 or k_table_volume <= 0:
        return None
    return k_price / k_table_price, k_volume / k_table_volume


def rebuild_symbol_raw_with_map(
    store: MinuteStore,
    daily_store: DailyStore,
    symbol: str,
    adjustment_map: "va.AdjustmentMap",
    *,
    tick_paise: int | None = None,
    applied_factors: SymbolFactors | None = None,
) -> RebuildResult:
    """Bring an already-fetched store to the map's RAW, IN PLACE, by BASELINE CLASSIFICATION.

    Safe to re-run, and safe on a store in any mixed state, because it never asks "is this day raw?"
    and divides whenever the answer is no. It asks WHICH known baseline each day sits on
    (:func:`stored_day_baseline`) and applies the one correction that baseline needs:

    * :data:`BASELINE_RAW` -> nothing (skip; counted in ``identity_days``);
    * :data:`BASELINE_AS_FETCHED` -> divide by the map's ``k_price``, scale volume by ``k_volume``;
    * :data:`BASELINE_OVER_DIVIDED` -> multiply BACK by ``k_price`` (a day a previous pass divided
      one time too many -- this is what makes the rebuild idempotent by construction);
    * :data:`BASELINE_UNKNOWN` -> LEFT ALONE and counted. Its provenance is lost, no factor is
      guessed, and gate 1 excludes and counts it (CONTEXT 7-E3).

    The one-way ``is it raw?`` test this used to use was measured to be wrong in the dangerous
    direction: the bhavcopy's high/low can carry a pre-open-auction or block-window print that no
    continuous 1-minute candle holds, so 37 genuinely-raw ASHOKLEY days sat 0.1%-0.5% off it, were
    called "not raw", and were divided a second time.

    ``applied_factors`` names the factor-table chain the store was ALREADY un-adjusted by at ingest
    (the quarantine-recovery reroute of a table-path symbol -- QUESTIONS.md Q-12 addendum). Given it,
    an as-fetched-relative day is corrected by the NET factor ``k_map / k_table`` in ONE division
    (:func:`net_map_factors`), never a second full division on top of the first.

    A day with no raw daily row cannot be classified at all, so it is left as-is (gate 1 excludes it
    downstream); a day whose era the map cannot resolve is counted un-provable and left as-is.
    """
    sym = symbol.strip().upper()
    result = RebuildResult(symbol=sym, days_rewritten=0, identity_days=0, unadjusted_days=0)
    for day in store.stored_days(sym):
        stored = store.minutes(sym, day)
        if not stored:
            continue
        frame = daily_store.daily(sym, day, day)
        if frame.empty:
            result.identity_days += 1  # no raw daily row to verify against -> leave as-is (safe)
            continue
        fd = fetch_date_for_day(store, sym, day) if applied_factors is not None else None
        target = net_map_factors(adjustment_map, day, applied_factors, fd)
        if target is None:
            result.unprovable_days.append(day)  # unprobed / un-provable era -> gate 1 excludes it
            continue
        # Hypotheses come from the ERA chain, not the day's floor-reduced chain: a day the store
        # still holds under a PRE-floor chain must stay recognisable after a floor drops that chain,
        # or the repair would silently skip exactly the days the floor was measured for. Both chains
        # go to the classifier, which names the floor-specific provenances from their ratio.
        net = net_map_factors(adjustment_map, day, applied_factors, fd, hypothesis=True)
        if net is None:
            result.unprovable_days.append(day)
            continue
        net_price, net_volume = net
        target_price, target_volume = target
        baseline = stored_day_baseline(
            stored, frame.iloc[0], net_price, net_volume,
            k_price_target=target_price, k_volume_target=target_volume,
        )
        if baseline == BASELINE_RAW:
            result.identity_days += 1
            continue
        if baseline == BASELINE_UNKNOWN:
            result.unknown_baseline_days.append(day)
            continue
        correction = baseline_correction(
            baseline, net_price, net_volume, target_price, target_volume
        )
        if correction is None:
            result.unknown_baseline_days.append(day)
            continue
        net_price, net_volume = correction
        if net_price == Decimal(1) and net_volume == Decimal(1):
            # The map agrees with whatever was already applied -- the exact identity. Nothing to do,
            # and nothing rewritten (which is also what makes the reroute cheap and re-runnable).
            result.identity_days += 1
            continue
        raw_bars: list[StoredBar] = []
        tick_flagged = 0
        for b in stored:
            prices = []
            for value in (b.open_paise, b.high_paise, b.low_paise, b.close_paise):
                raw, _snap, off = unadj.unadjust_price_paise(value, net_price, tick_paise=tick_paise)
                prices.append(raw)
                if off > unadj.DEFAULT_TICK_SNAP_TOLERANCE_PAISE:
                    tick_flagged += 1
            raw_bars.append(
                StoredBar(sym, b.stamp, prices[0], prices[1], prices[2], prices[3],
                          unadj.unadjust_volume(b.volume, net_volume))
            )
        store.write_bars(sym, raw_bars)
        if tick_flagged:
            result.tick_flagged_days.append(day)
        result.days_rewritten += 1
        result.unadjusted_days += 1
    return result


@dataclass
class YearGate1:
    """Gate-1 pass tally for one year (the Q-10 acceptance table, evidence 4a)."""

    year: int
    passed: int
    total: int

    @property
    def pct(self) -> float:
        return 100.0 * self.passed / self.total if self.total else 0.0


def gate1_by_year(
    daily_store: DailyStore,
    minute_store: MinuteStore,
    symbol: str,
    *,
    symbol_factors: SymbolFactors | None = None,
) -> list[YearGate1]:
    """Gate-1 pass rate per year over a symbol's stored days (Q-10 acceptance 4a).

    With ``symbol_factors`` given, each day's stored bars are UN-ADJUSTED in memory (read-only)
    before their volume is summed -- so this reports the "after" rate over a store that still
    holds the adjusted feed. With ``None`` it reports the store's volume as-is (the "before"
    rate, or the "after" rate once the store has been rebuilt to raw).
    """
    per_year_pass: dict[int, int] = {}
    per_year_total: dict[int, int] = {}
    for day in minute_store.stored_days(symbol):
        frame = daily_store.daily(symbol, day, day)
        if frame.empty:
            continue
        daily_volume = int(frame.iloc[0]["volume"])
        if symbol_factors is None:
            bars = minute_store.minutes(symbol, day)
        else:
            bars = unadjust_stored_day(minute_store, symbol, day, symbol_factors)
        minute_volume = sum(int(b.volume) for b in bars)
        per_year_total[day.year] = per_year_total.get(day.year, 0) + 1
        if gates.volume_gate(daily_volume, minute_volume).passed:
            per_year_pass[day.year] = per_year_pass.get(day.year, 0) + 1
    return [
        YearGate1(year=y, passed=per_year_pass.get(y, 0), total=per_year_total[y])
        for y in sorted(per_year_total)
    ]


# --- gate 3 / OPEN-8 adjustment probe --------------------------------------------------


@dataclass(frozen=True)
class AdjustmentProbe:
    """The evidence and verdict for one OPEN-8 event (gate 3)."""

    event: AdjustmentEvent
    verdict: str
    pre_ex_day: date | None
    candidate_k: Decimal | None
    minute_ohlc: dict[str, int] | None
    raw_daily_ohlc: dict[str, int] | None
    ratios: dict[str, Decimal]
    detail: str


def _last_daily_before(daily_store: DailyStore, symbol: str, before: date, *, max_back: int = 20) -> date | None:
    """The most recent trading day strictly before ``before`` that has a raw daily row."""
    frame = daily_store.daily(symbol, before - timedelta(days=max_back), before - timedelta(days=1))
    if frame.empty:
        return None
    return max(frame["trade_date"])


def _first_daily_on_or_after(daily_store: DailyStore, symbol: str, since: date, *, max_fwd: int = 20) -> date | None:
    frame = daily_store.daily(symbol, since, since + timedelta(days=max_fwd))
    if frame.empty:
        return None
    return min(frame["trade_date"])


def adjustment_probe(
    client: sac.SmartApiClient,
    master: InstrumentMaster,
    daily_store: DailyStore,
    event: AdjustmentEvent,
) -> AdjustmentProbe:
    """Run gate 3 for one event: is the SmartAPI 1-minute feed RAW or ADJUSTED? (OPEN-8)

    Honors the GATE LESSON (PROGRESS.md chunk-4): compares a PRE-EX day's SmartAPI 1-minute
    prices against the SAME pre-ex day's RAW daily store prices -- a raw-to-raw comparison with
    no corporate action in between -- and against ``raw x k``, where ``k`` is read from the raw
    daily store's own price gap across the ex-date (no external magic number).

    Returns an :class:`AdjustmentProbe`. INDETERMINATE (never an error) when the symbol is not
    in the master, has no pre-ex daily row, or -- the KOTHARIPRO/GREENPLY case -- has no
    pre-ex 1-minute data (their ex-dates predate the 2016-10 floor).
    """
    def indeterminate(detail: str, pre_ex_day: date | None = None, k: Decimal | None = None,
                      minute: dict[str, int] | None = None, raw: dict[str, int] | None = None) -> AdjustmentProbe:
        return AdjustmentProbe(event, gates.VERDICT_INDETERMINATE, pre_ex_day, k, minute, raw, {}, detail)

    try:
        token = master.token(event.symbol)
    except InstrumentMasterError:
        return indeterminate(f"{event.symbol} is not in the current instrument master (delisted?)")

    pre_ex_day = _last_daily_before(daily_store, event.symbol, event.ex_date)
    ex_ref_day = _first_daily_on_or_after(daily_store, event.symbol, event.ex_date)
    if pre_ex_day is None or ex_ref_day is None:
        return indeterminate(f"no raw daily rows around {event.ex_date} for {event.symbol}", pre_ex_day)

    raw_pre = daily_store.daily(event.symbol, pre_ex_day, pre_ex_day).iloc[0]
    raw_ex = daily_store.daily(event.symbol, ex_ref_day, ex_ref_day).iloc[0]
    raw_daily_ohlc = {
        "open_paise": int(raw_pre["open_paise"]),
        "high_paise": int(raw_pre["high_paise"]),
        "low_paise": int(raw_pre["low_paise"]),
        "close_paise": int(raw_pre["close_paise"]),
    }
    # k = the raw price gap across the ex-date, observed in our own RAW store (the effective
    # corporate-action factor; a 1:1 bonus shows ~0.5). Robust because RAW vs ADJUSTED (1.0 vs
    # ~0.5) are far apart relative to any overnight move baked into this ratio.
    candidate_k = Decimal(int(raw_ex["close_paise"])) / Decimal(int(raw_pre["close_paise"]))

    from_dt = datetime.combine(pre_ex_day, dtime(9, 15))
    to_dt = datetime.combine(pre_ex_day, dtime(15, 30))
    try:
        bars = client.get_candles(token, sac.INTERVAL_ONE_MINUTE, from_dt, to_dt)
    except sac.SmartApiError as exc:
        return indeterminate(f"1-minute fetch for {pre_ex_day} failed: {exc}", pre_ex_day, candidate_k, None, raw_daily_ohlc)
    if not bars:
        return indeterminate(
            f"no 1-minute data for {pre_ex_day} (predates the 2016-10 floor?)",
            pre_ex_day, candidate_k, None, raw_daily_ohlc,
        )

    stored = tuple(
        StoredBar(event.symbol, b.stamp, b.open_paise, b.high_paise, b.low_paise, b.close_paise, b.volume)
        for b in bars
    )
    minute_ohlc = daily_ohlc_from_minutes(stored)
    result = gates.adjustment_gate(minute_ohlc, raw_daily_ohlc, candidate_k)
    return AdjustmentProbe(
        event=event,
        verdict=result.verdict,
        pre_ex_day=pre_ex_day,
        candidate_k=candidate_k,
        minute_ohlc=minute_ohlc,
        raw_daily_ohlc=raw_daily_ohlc,
        ratios=result.field_ratios,
        detail=result.detail,
    )


# --- the live-run CLI ------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="acumen-minute-backfill",
        description="Backfill one symbol's 1-minute candles and run the CONTEXT 4.5 gates.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--symbol", default="TCS", help="symbol to backfill (NSE cash equity)")
    parser.add_argument("--from", dest="start", default=MINUTE_DATA_FLOOR.isoformat(), help="start date YYYY-MM-DD")
    parser.add_argument("--to", dest="end", default=None, help="end date YYYY-MM-DD (default: today)")
    parser.add_argument("--store", default=None, help="minute store root (default: <data_dir>/minute_store)")
    parser.add_argument("--daily-store", default=None, help="daily store root (default: <data_dir>/daily_store)")
    parser.add_argument("--cache-dir", default=None, help="instrument-master cache dir (default: config cache_dir)")
    parser.add_argument("--allow-network", action="store_true", help="REQUIRED to fetch anything")
    parser.add_argument("--no-gate3", action="store_true", help="skip the OPEN-8 adjustment probe")
    parser.add_argument("--max-windows", type=int, default=None, help="cap windows this run (debug)")
    parser.add_argument("--rebuild", action="store_true",
                        help="Q-10: un-adjust an already-fetched (adjusted) store to RAW in place, "
                             "then report; makes NO SmartAPI pulls")
    parser.add_argument("--acceptance", action="store_true",
                        help="Q-10 acceptance (read-only): print gate-1 by year BEFORE (as stored) "
                             "and AFTER (un-adjusted in memory); makes NO SmartAPI pulls")
    parser.add_argument("--adjustment-map", default=None,
                        help="path to a persisted Q-11 adjustment map JSON; default: "
                             "<data_dir>/adjustment_maps/<SYMBOL>.json when it exists")
    parser.add_argument("--map-data-dir", default=None,
                        help="data dir holding adjustment_maps/ (default: config data_dir)")
    return parser.parse_args(argv)


def load_adjustment_map_for(
    symbol: str,
    *,
    explicit_path: str | Path | None = None,
    data_dir: Path | None = None,
) -> "va.AdjustmentMap | None":
    """The persisted Q-11 map for ``symbol``, or ``None`` when none exists (REVIEW_5A F1).

    An explicit path MUST exist -- an operator who names a map and gets silently ignored would
    believe the run was map-backed when it was not. The default discovery path is allowed to be
    absent (a bonus/split-only symbol has no map and needs none).
    """
    if explicit_path is not None:
        path = Path(explicit_path)
        if not path.is_file():
            raise va.VendorAdjustmentError(f"--adjustment-map {path} does not exist")
        return va.from_dict(json.loads(path.read_text(encoding="utf-8")))
    path = va.map_path(symbol, data_dir)
    if not path.is_file():
        return None
    return va.load_map(symbol, data_dir)


def _default_root(subdir: str) -> Path:
    from .config import load_config

    return load_config(include_env=False).path("data_dir") / subdir


def run(args: argparse.Namespace) -> int:
    symbol = args.symbol.strip().upper()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end) if args.end else datetime.now().date()
    minute_root = Path(args.store) if args.store else _default_root("minute_store")
    daily_root = Path(args.daily_store) if args.daily_store else _default_root("daily_store")
    minute_store = MinuteStore.at(minute_root)
    daily_store = DailyStore.at(daily_root)

    print(f"symbol       : {symbol}")
    print(f"range        : {start} .. {end}  (clamped to {clamp_start(start)} = 1-min floor)")
    print(f"minute store : {minute_root}")
    print(f"daily store  : {daily_root}")

    # The Q-10 offline modes (rebuild / acceptance) read the already-fetched store and the CA
    # history; they make NO SmartAPI pulls, so they need no login (the master loads from cache
    # for the tick). Building the factor table needs the NSE CA history -- opt-in via --allow-network.
    map_data_dir = Path(args.map_data_dir) if args.map_data_dir else None
    if args.rebuild or args.acceptance:
        master = load_instrument_master(cache_dir=args.cache_dir, allow_network=args.allow_network)
        tick_paise = _tick_paise(master, symbol)
        print(f"  instrument master loaded; {symbol} tick = {master.tick_size(symbol)} "
              f"({tick_paise} paise)")
        actions = fetch_corp_action_history(start, end, allow_network=args.allow_network,
                                            cache_dir=args.cache_dir)
        view = corp_actions_for_symbol(symbol, actions, daily_store)
        sf = view.symbol_factors(tick_paise=tick_paise)
        _print_symbol_factors(sf)
        amap = load_adjustment_map_for(symbol, explicit_path=args.adjustment_map,
                                       data_dir=map_data_dir)
        decision = _print_route(view, clamp_start(start), amap, until=end)
        if args.acceptance:
            _print_acceptance(daily_store, minute_store, symbol, sf)
        if args.rebuild:
            allowed, why_not = map_covers_route(decision, amap is not None)
            if not allowed:
                print(f"\nSTOPPING (routing rule): {why_not}")
                return 2
            if amap is not None:
                _print_rebuild_with_map(minute_store, daily_store, symbol, amap, tick_paise)
            else:
                _print_rebuild(minute_store, symbol, sf)
        return 0

    if not args.allow_network:
        print("STOPPING: --allow-network is required. This script makes live SmartAPI pulls "
              "(CONTEXT 4.3); nothing was fetched. (Use --rebuild / --acceptance for the offline "
              "Q-10 modes.)")
        return 0

    print("logging in to SmartAPI ...")
    credentials = sac.Credentials.from_env()
    client = sac.SmartApiClient(credentials).login()
    print("  login OK")
    master = load_instrument_master(cache_dir=args.cache_dir, allow_network=True)
    tick_paise = _tick_paise(master, symbol)
    print(f"  instrument master loaded ({len(master)} NSE equities); {symbol} token = {master.token(symbol)} "
          f"tick = {master.tick_size(symbol)} ({tick_paise} paise)")

    # Q-10: assemble the symbol's factor table so the ingest path un-adjusts each window to RAW.
    actions = fetch_corp_action_history(start, end, allow_network=True, cache_dir=args.cache_dir)
    view = corp_actions_for_symbol(symbol, actions, daily_store)
    sf = view.symbol_factors(tick_paise=tick_paise)
    _print_symbol_factors(sf)

    # Q-11 addendum (routing): a MAP-REQUIRED symbol is ingested THROUGH its measured adjustment
    # map or not at all -- the factor-table fallback has no price oracle for a non-share-count
    # event, so a wrong price would pass gate-1 volume unseen (REVIEW_5A F1/F2).
    adjustment_map = load_adjustment_map_for(symbol, explicit_path=args.adjustment_map,
                                             data_dir=map_data_dir)
    decision = _print_route(view, clamp_start(start), adjustment_map, until=end)
    allowed, why_not = map_covers_route(decision, adjustment_map is not None)
    if not allowed:
        print(f"\nSTOPPING (routing rule): {why_not}")
        client.logout()
        return 2

    started = time.monotonic()

    def on_progress(p: BackfillProgress, ws: date, we: date, outcome: str) -> None:
        if p.windows_done % 10 == 0 or p.windows_done == p.windows_total:
            elapsed = time.monotonic() - started
            print(f"  {p.windows_done:>4}/{p.windows_total}  {ws}..{we}  "
                  f"present={p.present} empty={p.empty} error={p.error} candles={p.candles} "
                  f"unprovable={p.unprovable_days} tick_flag={p.tick_flagged_days} elapsed={int(elapsed)}s")

    if args.max_windows is not None:
        # Debug cap: only plan the first N windows this run (still resumable).
        planned = plan_windows(start, end)
        pending = minute_store.pending_windows(symbol, planned)
        if pending:
            end = min(end, pending[min(args.max_windows, len(pending)) - 1][1])
            print(f"  (debug) capping this run to {args.max_windows} pending windows -> end {end}")

    path_name = "map" if adjustment_map is not None else "factor-table"
    print(f"\nbackfilling (un-adjusting each window to RAW on ingest, {path_name} path) ...")
    result = backfill_symbol(client, master, minute_store, symbol, start, end,
                             symbol_factors=sf, adjustment_map=adjustment_map,
                             on_progress=on_progress)

    print("\nWINDOW LEDGER " + "-" * 60)
    print(f"  windows planned  : {result.windows_planned}")
    print(f"  windows attempted: {result.windows_attempted}")
    print(f"  ledger totals    : {result.ledger_summary}")
    print(f"  depth found      : first 1-min date = {result.first_stored_date}")
    print(f"  un-provable days : {len(result.unprovable_days)} (excluded + counted by gate 1)")
    print(f"  tick-flag days   : {len(result.tick_flagged_days)} (vendor rounding > 2 paise)")
    if result.errors:
        print(f"  windows in ERROR : {len(result.errors)} (retried next run)")
        for ws, we, reason in result.errors[:10]:
            print(f"      ! {ws}..{we}: {reason[:80]}")

    _print_gate_report(daily_store, minute_store, symbol)

    if not args.no_gate3:
        _print_gate3_report(client, master, daily_store)

    client.logout()
    return 0


def _tick_paise(master: InstrumentMaster, symbol: str) -> int | None:
    """The symbol's tick in integer paise (from the instrument master), or ``None``."""
    try:
        tick = master.tick_size(symbol)
    except InstrumentMasterError:
        return None
    scaled = Decimal(tick) * 100
    return int(scaled) if scaled == scaled.to_integral_value() else None


def _print_symbol_factors(sf: SymbolFactors) -> None:
    print(f"\nQ-10 FACTOR TABLE for {sf.symbol} " + "-" * 40)
    print(f"  factors (k!=1 affect un-adjust): {len(sf.factors)}")
    for f in sf.factors:
        if f.k != Decimal(1):
            # FIX-2: a share-count factor (bonus/split/consolidation) enters BOTH k_price and
            # k_shares; every other kind (special dividend, rights) enters k_price only.
            domain = "price+volume" if f.kind in ca.SHARE_COUNT_KINDS else "price only"
            print(f"      {f.ex_date}  {f.kind:9s} k={f.k}  [{domain}]  ({f.basis})")
    # Q-10 ADDENDUM 2: a demerger no longer marks a MINUTE span un-provable (the 1-minute feed
    # is not demerger-adjusted); only a tier-2 unrecoverable rights does. The demerger's DAILY
    # bias-pair suppression (CONTEXT 3.2) is separate and consumes the full list.
    print(f"  suppressions: {len(sf.suppressions)} "
          f"(demerger -> bias-layer only; tier-2 rights -> un-provable minute span)")
    for s in sf.suppressions:
        minute_effect = ("un-provable minute span" if s.kind != ca.KIND_DEMERGER
                         else "NOT un-provable for minutes (bias-layer suppression only)")
        print(f"      {s.ex_date}  {s.kind}: {s.reason}  [{minute_effect}]")
    if sf.pending_ex_dates:
        print(f"  Q-6-pending rights ex-dates: {list(sf.pending_ex_dates)}")


def _print_route(view: SymbolCorpActions, since: date, amap: "va.AdjustmentMap | None",
                 until: date | None = None):
    """Print (and return) the symbol's Q-11-addendum routing decision."""
    decision = classify_route(
        view.symbol,
        factors=view.factors,
        suppressions=view.suppressions,
        pending=view.pending,
        parse_exceptions=view.parse_exceptions,
        since=since,
        until=until,
    )
    print(f"\nROUTE (Q-11 addendum) for {view.symbol} " + "-" * 36)
    print(f"  route          : {decision.route}")
    for reason in decision.reasons:
        print(f"      forced by  : {reason}")
    if amap is None:
        print("  adjustment map : (none loaded)")
    else:
        provable = sum(1 for era in amap.eras if era.provable)
        print(f"  adjustment map : F={amap.fetch_date}, {provable}/{len(amap.eras)} eras provable")
    return decision


def _print_rebuild_with_map(minute_store: MinuteStore, daily_store: DailyStore, symbol: str,
                            amap: "va.AdjustmentMap", tick_paise: int | None) -> None:
    print("\nQ-11 REBUILD via the adjustment map (idempotent, identity-guarded) " + "-" * 4)
    result = rebuild_symbol_raw_with_map(minute_store, daily_store, symbol, amap,
                                         tick_paise=tick_paise)
    print(f"  days rewritten   : {result.days_rewritten}")
    print(f"  identity days    : {result.identity_days} (already RAW on price AND volume)")
    print(f"  un-provable days : {len(result.unprovable_days)} (gate 1 excludes + counts)")
    print("  store now holds RAW same-day prices (CONTEXT 7-E11).")


def _print_acceptance(daily_store: DailyStore, minute_store: MinuteStore, symbol: str,
                      sf: SymbolFactors) -> None:
    print("\nQ-10 ACCEPTANCE 4a -- gate-1 pass rate by year " + "-" * 20)
    before = gate1_by_year(daily_store, minute_store, symbol)  # as stored (adjusted)
    after = gate1_by_year(daily_store, minute_store, symbol, symbol_factors=sf)  # un-adjusted
    after_by_year = {y.year: y for y in after}
    print(f"  {'year':>6} {'before':>18} {'after (un-adjusted)':>22}")
    for row in before:
        aft = after_by_year.get(row.year)
        aft_txt = f"{aft.passed}/{aft.total} ({aft.pct:.1f}%)" if aft else "-"
        print(f"  {row.year:>6} {f'{row.passed}/{row.total} ({row.pct:.1f}%)':>18} {aft_txt:>22}")


def _print_rebuild(minute_store: MinuteStore, symbol: str, sf: SymbolFactors) -> None:
    print("\nQ-10 REBUILD -- un-adjusting the stored feed to RAW in place " + "-" * 8)
    result = rebuild_symbol_raw(minute_store, symbol, sf)
    print(f"  days rewritten   : {result.days_rewritten}")
    print(f"  identity days    : {result.identity_days} (k_price=k_shares=1, stored unchanged)")
    print(f"  un-adjusted days : {result.unadjusted_days} (k_price!=1, divided back to raw)")
    print(f"  un-provable days : {len(result.unprovable_days)} (gate 1 excludes + counts)")
    print("  store now holds RAW same-day prices (CONTEXT 7-E11).")


def _print_gate_report(daily_store: DailyStore, minute_store: MinuteStore, symbol: str) -> None:
    print("\nGATE 1 (volume) + GATE 2 (integrity) " + "-" * 40)
    days = minute_store.stored_days(symbol)
    if not days:
        print("  no stored days.")
        return
    per_year_pass: dict[int, int] = {}
    per_year_total: dict[int, int] = {}
    gate2_exclusions: list[tuple[date, tuple[str, ...]]] = []
    gate1_missing_daily = 0
    for day in days:
        try:
            g1 = gate1_for_day(daily_store, minute_store, symbol, day)
        except DailyStoreError:
            g1 = None
        if g1 is None:
            gate1_missing_daily += 1
        else:
            per_year_total[day.year] = per_year_total.get(day.year, 0) + 1
            if g1.passed:
                per_year_pass[day.year] = per_year_pass.get(day.year, 0) + 1
        g2 = gate2_for_day(minute_store, symbol, day)
        if not g2.passed:
            gate2_exclusions.append((day, g2.reasons))

    print(f"  stored symbol-days : {len(days)}  ({days[0]} .. {days[-1]})")
    print("  gate-1 pass rate by year (vs raw daily-store volume, band [-0.1%, +5.0%]):")
    for year in sorted(per_year_total):
        passed = per_year_pass.get(year, 0)
        total = per_year_total[year]
        print(f"      {year}: {passed}/{total}  ({100.0 * passed / total:.1f}%)")
    if gate1_missing_daily:
        print(f"  gate-1 skipped     : {gate1_missing_daily} day(s) had no raw daily row to reconcile against")
    print(f"  gate-2 exclusions  : {len(gate2_exclusions)}")
    for day, reasons in gate2_exclusions[:20]:
        print(f"      ! {day}: {'; '.join(reasons)}")


def _print_gate3_report(client: sac.SmartApiClient, master: InstrumentMaster, daily_store: DailyStore) -> None:
    print("\nGATE 3 / OPEN-8 (SmartAPI 1-min: RAW or ADJUSTED?) " + "-" * 25)
    verdicts: list[str] = []
    for event in OPEN8_EVENTS:
        probe = adjustment_probe(client, master, daily_store, event)
        verdicts.append(probe.verdict)
        print(f"  {event.symbol} ({event.description}):  VERDICT = {probe.verdict}")
        if probe.pre_ex_day is not None:
            print(f"      pre-ex day    : {probe.pre_ex_day}   candidate k (raw gap) = "
                  f"{probe.candidate_k if probe.candidate_k is None else round(float(probe.candidate_k), 5)}")
        if probe.minute_ohlc and probe.raw_daily_ohlc:
            print(f"      1-min OHLC    : {probe.minute_ohlc}")
            print(f"      raw daily OHLC: {probe.raw_daily_ohlc}")
            print(f"      ratios        : { {k: round(float(v), 5) for k, v in probe.ratios.items()} }")
        print(f"      {probe.detail}")
    combined = gates.combine_adjustment_verdicts(verdicts)
    print(f"\n  COMBINED OPEN-8 VERDICT: {combined}")
    if combined == gates.VERDICT_ADJUSTED:
        print("  *** STOP: the 1-minute feed is ADJUSTED. Record and halt -- the architect must "
              "amend CONTEXT 7-E11 before chunk 6 consumes minute data (chunk-5A card). ***")


def main(argv: list[str] | None = None) -> int:
    try:
        return run(parse_args(argv))
    except (DailyStoreError, InstrumentMasterError, sac.SmartApiError, ca.CorporateActionError,
            va.VendorAdjustmentError) as exc:
        print(f"\nERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
