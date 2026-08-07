"""THE MORNING REFRESH (chunk 13, pre-09:15): make the stored world current before the bell.

plan.md's chunk-13 card: *"morning refresh job (pre-09:15): ingest yesterday's bhavcopy into the
daily store, incremental CA pull (a split effective TODAY must be known before computing bias),
universe + holiday refresh (gentle, cached), compute & persist today's bias for every symbol"*.

Every step is an existing, reviewed module driven in order. Nothing here re-implements a fetch,
a parser or a store; the refresh's whole job is SEQUENCE, and its whole risk is a step that
half-succeeds and is reported as done. So each step returns a :class:`RefreshStep` naming what it
did, and :meth:`RefreshReport.ok` is the AND of all of them -- a screener that starts on a stale
daily store would compute yesterday's bias and never say so.

## The Q-19 guard, applied

**QUESTIONS.md Q-19 is OPEN, and its measured workaround binds this job.** A bhavcopy 404 for a
date whose file is *not published yet* is indistinguishable, in the ledger, from a 404 for a date
that *had no session* -- so ingesting "up to today" during or shortly after the session silently
records TODAY as a holiday, which shifts ``bias_pair(D)`` for the NEXT trading day too. The
operator rule written into ``docs/recovery/q18_runbook.md`` step 1 is *"end at the last COMPLETED
trading day, never at today"*, and this job is the first piece of code that has to obey it
unattended, at 08:45, with no operator watching.

So :func:`last_completed_trading_day` is where the top-up stops, it is derived rather than
assumed, and :func:`refresh_daily_store` REFUSES a window that reaches today or later. The
architect's ruling on Q-19 -- operator discipline (a), a structural refusal in the downloader
(b), or a publication-lag config value (c) -- is still owed; this job takes option (a)'s
discipline and makes it non-optional for the live path, deciding nothing about the downloader.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Sequence

from . import backfill_daily as daily_backfill
from . import calendar as cal
from . import universe as uni
from .daily_store import DailyStore
from .live_recording import CALENDAR_PUBLISHED, CALENDAR_STORE_SCAN

#: How far back a top-up looks when the store's own last day cannot be trusted to be recent.
DEFAULT_LOOKBACK_DAYS: int = 10


class RefreshError(RuntimeError):
    """The morning refresh cannot complete, and the screener must not start behind it."""


@dataclass(frozen=True)
class RefreshStep:
    """One step of the refresh: what it was, whether it worked, and what it actually did."""

    name: str
    ok: bool
    detail: str
    figures: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RefreshReport:
    """The whole pre-open job. ``ok`` is the AND of every step -- there is no partial success."""

    day: date
    steps: tuple[RefreshStep, ...]

    @property
    def ok(self) -> bool:
        return all(step.ok for step in self.steps)

    def render(self) -> str:
        lines = [f"MORNING REFRESH  {self.day.isoformat()}", "=" * 72]
        for step in self.steps:
            mark = "ok  " if step.ok else "FAIL"
            lines.append(f"[{mark}] {step.name:<28} {step.detail}")
        lines.append("=" * 72)
        lines.append("READY" if self.ok else "NOT READY -- the screener must not start")
        return "\n".join(lines) + "\n"


def last_completed_trading_day(calendar: cal.TradingCalendar, today: date) -> date:
    """The last trading day STRICTLY before ``today`` -- the Q-19 ceiling for any top-up.

    Strictly before, always, even when today is a trading day and the market has closed: the
    bhavcopy for a session is published after it, and a 404 for a file that merely has not
    arrived yet is the phantom holiday Q-19 measured. One day of lag costs the screener nothing
    (CONTEXT 3.2's bias pair is (D-1, D-2), both already complete) and it is the only reading
    that cannot invent a holiday.
    """
    return calendar.prev_trading_day(today)


def refresh_calendar(
    *, cache_dir: Path | None = None, today: date, allow_network: bool = False,
    daily_store: DailyStore | None = None,
) -> tuple[cal.TradingCalendar, RefreshStep]:
    """Pull the PUBLISHED NSE holiday calendar (gently, day-cached) -- and cross-check it.

    **This is the C5 duty executed** (QUESTIONS.md, recorded by the chunk-9A fix session and
    carried on the chunk-13 card): *"chunk 13 takes non-standard sessions from the published NSE
    calendar; the store scan stays the backtest cross-check."*

    So the PUBLISHED calendar governs -- it is the only one that can answer for today and
    tomorrow at all (a derived calendar refuses an incomplete year by construction, which is the
    division of labour :meth:`acumen.calendar.TradingCalendar.from_daily_store` documents). The
    store-derived reading is computed beside it where the daily store can support it, and the two
    are compared over the days they share. A disagreement is REPORTED, never resolved here.
    """
    calendar = cal.fetch_calendar(
        cache_dir=cache_dir, today=today, allow_network=allow_network
    )
    figures: dict = {
        "governing_source": CALENDAR_PUBLISHED,
        "cross_check_source": CALENDAR_STORE_SCAN,
        "holidays_this_year": sum(1 for day in calendar.holidays if day.year == today.year),
        "today_is_trading_day": calendar.is_trading_day(today),
        "today_is_standard_session": calendar.is_standard_session(today),
    }
    disagreements: list[str] = []
    if daily_store is not None:
        try:
            derived = cal.TradingCalendar.from_daily_store_range(
                daily_store, date(today.year, 1, 1), today - timedelta(days=1)
            )
        except Exception as exc:  # a partial store is normal in January; not a failure
            figures["cross_check"] = f"unavailable: {type(exc).__name__}: {exc}"
        else:
            covered = derived.covered_days or frozenset()
            for day in sorted(covered):
                if day.year != today.year:
                    continue
                try:
                    published = calendar.is_trading_day(day)
                except cal.CalendarError:
                    continue
                if published != derived.is_trading_day(day):
                    disagreements.append(day.isoformat())
            figures["cross_check_days"] = len(covered)
            figures["cross_check_disagreements"] = disagreements
            figures["cross_check_weekend_sessions"] = [
                stamp.isoformat() for stamp in derived.weekend_sessions
            ]
    detail = (
        f"published calendar governs ({figures['holidays_this_year']} holidays in "
        f"{today.year}); today is "
        + ("a standard session" if figures["today_is_standard_session"] else "NOT a session")
    )
    if disagreements:
        detail += f"; store-scan cross-check DISAGREES on {len(disagreements)} day(s)"
    return calendar, RefreshStep(name="calendar (published NSE)", ok=True,
                                 detail=detail, figures=figures)


def refresh_universe(
    *, cache_dir: Path | None = None, today: date, allow_network: bool = False
) -> tuple[tuple[str, ...], RefreshStep]:
    """The F&O universe, at most one pull per calendar day (CONTEXT 4.1's own ToU sentence)."""
    symbols = uni.fetch_universe(
        cache_dir=cache_dir, today=today, allow_network=allow_network
    )
    fetched_on, _cached = uni.load_cached_universe(cache_dir)
    age = (today - fetched_on).days
    return symbols, RefreshStep(
        name="universe (F&O underlyings)", ok=bool(symbols),
        detail=f"{len(symbols)} symbols, cache fetched {fetched_on.isoformat()} ({age}d old)",
        figures={"symbols": len(symbols), "fetched_on": fetched_on.isoformat(), "age_days": age},
    )


def refresh_daily_store(
    store: DailyStore,
    calendar: cal.TradingCalendar,
    *,
    today: date,
    allow_network: bool = False,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    runner: Callable[[list[str]], int] | None = None,
) -> RefreshStep:
    """Top the daily store up to the LAST COMPLETED TRADING DAY. Never to today (Q-19).

    Raises:
        RefreshError: the computed window would reach today or later. That cannot happen from
            :func:`last_completed_trading_day`, and the guard is here so that it also cannot
            happen from a future caller that computes the ceiling some other way.
    """
    ceiling = last_completed_trading_day(calendar, today)
    if ceiling >= today:
        raise RefreshError(
            f"Refusing to ingest up to {ceiling.isoformat()} on {today.isoformat()}: "
            "QUESTIONS.md Q-19 measured that a 404 for an unpublished bhavcopy is recorded as "
            "a CONFIRMED non-trading day, which shifts the CONTEXT 3.2 bias pair for the next "
            "trading day. A top-up ends at the last COMPLETED trading day."
        )
    start = ceiling - timedelta(days=max(1, lookback_days))
    argv = [
        "--from", start.isoformat(), "--to", ceiling.isoformat(),
        *(["--allow-network"] if allow_network else []),
    ]
    code = (runner or daily_backfill.main)(argv)
    return RefreshStep(
        name="daily store (bhavcopy top-up)", ok=code == 0,
        detail=(
            f"{start.isoformat()} -> {ceiling.isoformat()} (Q-19 ceiling: the last COMPLETED "
            f"trading day, never {today.isoformat()})"
        ),
        figures={"from": start.isoformat(), "to": ceiling.isoformat(),
                 "exit_code": code, "q19_ceiling": ceiling.isoformat()},
    )


def refresh_corporate_actions(
    *, symbols: Sequence[str], today: date, allow_network: bool = False,
    cache_dir: Path | None = None,
    puller: Callable[..., Sequence] | None = None,
) -> RefreshStep:
    """Incremental CA pull, so a factor effective TODAY is known before any bias is computed.

    The card's own reason: *"a split effective TODAY must be known before computing bias"*. The
    fetch is the reviewed chunk-3 engine (``corp_actions.fetch_nse_corporate_actions``, itself
    day-cached and gently paced per CONTEXT 4.1). What this step ADDS is the report a screener
    needs at 08:45: **whether any ex-date lands on today or on either day of the bias pair**,
    because that is the case where a stale cache silently changes a bias rather than merely
    aging. An ordinary stale cache costs nothing; a cache that missed today's split is a wrong
    bias on every stock it touches.
    """
    window_start = today - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    if puller is None:
        from . import corp_actions as ca

        puller = ca.fetch_nse_corporate_actions
    events = puller(
        window_start, today, allow_network=allow_network, cache_dir=cache_dir, today=today
    )
    wanted = {symbol.strip().upper() for symbol in symbols}
    in_window = [
        event for event in events
        if getattr(event, "symbol", "").strip().upper() in wanted
    ] if wanted else list(events)
    on_the_pair = [
        event for event in in_window
        if getattr(event, "ex_date", None) is not None
        and today - timedelta(days=4) <= event.ex_date <= today
    ]
    detail = (
        f"{len(in_window)} event(s) for the universe in "
        f"{window_start.isoformat()}..{today.isoformat()}"
    )
    if on_the_pair:
        names = ", ".join(sorted({event.symbol for event in on_the_pair}))
        detail += f"; {len(on_the_pair)} ex-date(s) ON or beside today's bias pair: {names}"
    return RefreshStep(
        name="corporate actions", ok=True, detail=detail,
        figures={
            "events_total": len(events),
            "events_for_universe": len(in_window),
            "ex_dates_near_the_bias_pair": [
                {"symbol": event.symbol, "ex_date": event.ex_date.isoformat(),
                 "subject": getattr(event, "subject", "")}
                for event in on_the_pair
            ],
            "window_start": window_start.isoformat(),
            "window_end": today.isoformat(),
        },
    )


def morning_refresh(
    *,
    today: date,
    store: DailyStore,
    cache_dir: Path | None = None,
    allow_network: bool = False,
    symbols: Sequence[str] | None = None,
    daily_runner: Callable[[list[str]], int] | None = None,
) -> tuple[cal.TradingCalendar, tuple[str, ...], RefreshReport]:
    """Run every pre-open step in order and report each one. Returns what the screener needs.

    The bias itself is NOT computed here -- :func:`acumen.live_screener.build_live_screener`
    computes it through the backtester's own runner, which is the only way to be sure the
    screener's 09:00 bias and the backtester's bias for the same day are the same number rather
    than two implementations that agree today.
    """
    steps: list[RefreshStep] = []
    calendar, step = refresh_calendar(
        cache_dir=cache_dir, today=today, allow_network=allow_network, daily_store=store
    )
    steps.append(step)

    if symbols is None:
        try:
            universe, step = refresh_universe(
                cache_dir=cache_dir, today=today, allow_network=allow_network
            )
        except Exception as exc:
            universe, step = (), RefreshStep(
                name="universe (F&O underlyings)", ok=False,
                detail=f"{type(exc).__name__}: {exc}",
            )
        steps.append(step)
    else:
        universe = tuple(symbol.strip().upper() for symbol in symbols)
        steps.append(RefreshStep(
            name="universe (F&O underlyings)", ok=True,
            detail=f"{len(universe)} symbol(s) supplied by the operator, no pull",
            figures={"symbols": len(universe)},
        ))

    try:
        steps.append(refresh_daily_store(
            store, calendar, today=today, allow_network=allow_network, runner=daily_runner
        ))
    except Exception as exc:
        steps.append(RefreshStep(
            name="daily store (bhavcopy top-up)", ok=False, detail=f"{type(exc).__name__}: {exc}"
        ))

    try:
        steps.append(refresh_corporate_actions(
            symbols=universe, today=today, allow_network=allow_network, cache_dir=cache_dir
        ))
    except Exception as exc:
        steps.append(RefreshStep(
            name="corporate actions", ok=False, detail=f"{type(exc).__name__}: {exc}"
        ))

    return calendar, universe, RefreshReport(day=today, steps=tuple(steps))


__all__ = [
    "DEFAULT_LOOKBACK_DAYS",
    "RefreshError",
    "RefreshReport",
    "RefreshStep",
    "last_completed_trading_day",
    "morning_refresh",
    "refresh_calendar",
    "refresh_corporate_actions",
    "refresh_daily_store",
    "refresh_universe",
]
