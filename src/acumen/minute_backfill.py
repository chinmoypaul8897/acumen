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
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Callable, Sequence

from . import quality_gates as gates
from . import smartapi_client as sac
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


@dataclass
class BackfillResult:
    """The outcome of backfilling one symbol."""

    symbol: str
    windows_planned: int
    windows_attempted: int
    ledger_summary: dict[str, int]
    first_stored_date: date | None
    errors: list[tuple[date, date, str]] = field(default_factory=list)


def backfill_symbol(
    client: sac.SmartApiClient,
    master: InstrumentMaster,
    store: MinuteStore,
    symbol: str,
    requested_start: date,
    end: date,
    *,
    retry_errors: bool = True,
    now: Callable[[], datetime] = datetime.now,
    on_progress: Callable[[BackfillProgress, date, date, str], None] | None = None,
) -> BackfillResult:
    """Download ``symbol``'s 1-minute candles over ``[requested_start, end]``, resumably.

    Walks the clamped 30-day windows, skips windows already settled in the ledger, fetches the
    rest, stores the candles and records each window's outcome. Safe to interrupt and re-run:
    a settled window is never refetched, an ``error`` window is retried next time.
    """
    token = master.token(symbol)
    windows = plan_windows(requested_start, end)
    pending = store.pending_windows(symbol, windows, retry_errors=retry_errors)

    progress = BackfillProgress(windows_total=len(pending))
    errors: list[tuple[date, date, str]] = []

    for window_start, window_end in pending:
        outcome = _fetch_and_store_window(client, store, symbol, token, window_start, window_end, now)
        store.record_window(outcome)
        progress.windows_done += 1
        if outcome.outcome == WINDOW_PRESENT:
            progress.present += 1
            progress.candles += outcome.candle_count or 0
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
    )


def _fetch_and_store_window(
    client: sac.SmartApiClient,
    store: MinuteStore,
    symbol: str,
    token: str,
    window_start: date,
    window_end: date,
    now: Callable[[], datetime],
) -> WindowOutcome:
    from_dt = datetime.combine(window_start, dtime(9, 15))
    to_dt = datetime.combine(window_end, dtime(15, 30))
    try:
        bars = client.get_candles(token, sac.INTERVAL_ONE_MINUTE, from_dt, to_dt)
    except sac.SmartApiError as exc:
        return WindowOutcome(
            symbol=symbol.strip().upper(),
            window_start=window_start,
            window_end=window_end,
            outcome=WINDOW_ERROR,
            reason=str(exc),
            attempted_at=now(),
        )
    if not bars:
        return WindowOutcome(
            symbol=symbol.strip().upper(),
            window_start=window_start,
            window_end=window_end,
            outcome=WINDOW_EMPTY,
            candle_count=0,
            reason="no candles in window (before listing or suspended)",
            attempted_at=now(),
        )
    store.write_bars(symbol, bars)
    dates = sorted({b.stamp.date() for b in bars})
    # Safety net for the 8000-candle response cap: with a 28-day window this cannot fire, but
    # if a future caller widens the window and the server drops the oldest candles, flag it so
    # the truncation is visible in the ledger rather than silent. Gate 2 also excludes the
    # resulting partial first-day, so no truncated day ever reaches the backtest either way.
    reason = None
    if len(bars) >= sac.ONE_MINUTE_RESPONSE_CAP:
        reason = (
            f"WARNING: {len(bars)} candles >= the {sac.ONE_MINUTE_RESPONSE_CAP} response cap; "
            "the oldest candles may have been dropped -- narrow the window"
        )
    return WindowOutcome(
        symbol=symbol.strip().upper(),
        window_start=window_start,
        window_end=window_end,
        outcome=WINDOW_PRESENT,
        candle_count=len(bars),
        first_date=dates[0],
        last_date=dates[-1],
        reason=reason,
        attempted_at=now(),
    )


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
    return parser.parse_args(argv)


def _default_root(subdir: str) -> Path:
    from .config import load_config

    return load_config(include_env=False).path("data_dir") / subdir


def run(args: argparse.Namespace) -> int:
    if not args.allow_network:
        print("STOPPING: --allow-network is required. This script makes live SmartAPI pulls "
              "(CONTEXT 4.3); nothing was fetched.")
        return 0

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
    print("logging in to SmartAPI ...")

    credentials = sac.Credentials.from_env()
    client = sac.SmartApiClient(credentials).login()
    print("  login OK")
    master = load_instrument_master(cache_dir=args.cache_dir, allow_network=True)
    print(f"  instrument master loaded ({len(master)} NSE equities); {symbol} token = {master.token(symbol)} "
          f"tick = {master.tick_size(symbol)}")

    started = time.monotonic()

    def on_progress(p: BackfillProgress, ws: date, we: date, outcome: str) -> None:
        if p.windows_done % 10 == 0 or p.windows_done == p.windows_total:
            elapsed = time.monotonic() - started
            print(f"  {p.windows_done:>4}/{p.windows_total}  {ws}..{we}  "
                  f"present={p.present} empty={p.empty} error={p.error} candles={p.candles} "
                  f"elapsed={int(elapsed)}s")

    if args.max_windows is not None:
        # Debug cap: only plan the first N windows this run (still resumable).
        planned = plan_windows(start, end)
        pending = minute_store.pending_windows(symbol, planned)
        if pending:
            end = min(end, pending[min(args.max_windows, len(pending)) - 1][1])
            print(f"  (debug) capping this run to {args.max_windows} pending windows -> end {end}")

    print("\nbackfilling ...")
    result = backfill_symbol(client, master, minute_store, symbol, start, end, on_progress=on_progress)

    print("\nWINDOW LEDGER " + "-" * 60)
    print(f"  windows planned  : {result.windows_planned}")
    print(f"  windows attempted: {result.windows_attempted}")
    print(f"  ledger totals    : {result.ledger_summary}")
    print(f"  depth found      : first 1-min date = {result.first_stored_date}")
    if result.errors:
        print(f"  windows in ERROR : {len(result.errors)} (retried next run)")
        for ws, we, reason in result.errors[:10]:
            print(f"      ! {ws}..{we}: {reason[:80]}")

    _print_gate_report(daily_store, minute_store, symbol)

    if not args.no_gate3:
        _print_gate3_report(client, master, daily_store)

    client.logout()
    return 0


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
    except (DailyStoreError, InstrumentMasterError, sac.SmartApiError) as exc:
        print(f"\nERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
