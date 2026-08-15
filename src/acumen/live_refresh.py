"""THE MORNING REFRESH (chunk 13, pre-09:15): make the stored world current before the bell.

plan.md's chunk-13 card: *"morning refresh job (pre-09:15): ingest yesterday's bhavcopy into the
daily store, incremental CA pull (a split effective TODAY must be known before computing bias),
universe + holiday refresh (gentle, cached), compute & persist today's bias for every symbol"*.

Every step is an existing, reviewed module driven in order. Nothing here re-implements a fetch,
a parser or a store; the refresh's whole job is SEQUENCE, and its whole risk is a step that
half-succeeds and is reported as done. So each step returns a :class:`RefreshStep` naming what it
did, and :meth:`RefreshReport.ok` is the AND of all of them -- a screener that starts on a stale
daily store would compute yesterday's bias and never say so.

## CONTEXT 4.7, executed here (the Q-28 and Q-29 rulings, 08-Aug-2026)

Two of this job's steps exist because of that section, and neither is optional:

* **the day's own instrument master** (Q-29). *"A live morning uses THE DAY'S OWN instrument
  master, fetched pre-open, named+hashed into the recording"* -- so the fetch is a pre-open STEP
  with its filename and sha256 in the report, and a morning whose master did not arrive is NOT
  READY. The Q-20 pin still governs the historical ledger and the divergence between the two is
  REPORTED every morning as information, exactly as the ruling instructs;
* **yesterday's verdict** (Q-28). *"The NEXT pre-open runs the FULL battery on yesterday's
  recording against the published bhavcopy and reports the verdict, loudly naming any
  live-alerted day the oracle refuses."* That is :func:`verify_prior_recording`, and it runs
  AFTER the bhavcopy top-up in this job's order for the obvious reason: the oracle it needs is
  the file the step before it fetched.

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
from .live_recording import CALENDAR_PUBLISHED, CALENDAR_STORE_SCAN, LiveRecording
from .signal_engine import DayGates, SignalPipeline, oracle_free_battery

#: How far back a top-up looks when the store's own last day cannot be trusted to be recent.
DEFAULT_LOOKBACK_DAYS: int = 10

#: What a calendar-dependent step reports when the calendar step itself failed. NOT RUN is a
#: third outcome beside ok and FAIL, and it is stated rather than left to be inferred from a
#: missing line -- a step that is silently absent reads as a step that passed (REVIEW_14 M15's
#: shape, refused here before it can be made).
NOT_RUN_WITHOUT_A_CALENDAR: str = (
    "NOT RUN: the published calendar step above failed, and {what}"
)


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
    """The whole pre-open job. ``ok`` is the AND of every step -- there is no partial success.

    ``verification`` is CONTEXT 4.7's verdict on YESTERDAY, when there was a live yesterday to
    verify. It rides on the report rather than only in a step's ``detail`` because the dashboard
    shows it as its own section, and because a live-alerted day the oracle refuses must be
    reachable as data and not only as a sentence.
    """

    day: date
    steps: tuple[RefreshStep, ...]
    verification: "MorningVerification | None" = None

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
        if self.verification is not None and (
            self.verification.refused_after_alert
            or self.verification.alerted_but_unverified
        ):
            # The one thing in this report that must not be read past. CONTEXT 4.7's "named
            # loudly", in the only register a text report has. REVIEW_14 M15: a live-alerted
            # symbol-day that could not be judged AT ALL is loud too -- quieter than a refusal
            # and louder than silence, because the operator has to know what was not checked.
            lines.append("")
            lines.append("!! " + self.verification.headline)
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
    # REVIEW_14, found by driving the shipped `--refresh` end to end for B3's CLI test: the
    # backfill was invoked with no `--store`, so it resolved `default_store_root()` -- the
    # data_root of whatever config.yaml the PROCESS loaded -- and topped up THAT store however
    # the caller had been pointed. A session running against a scratch copy would have written
    # into the real one, which is precisely the write CLAUDE.md's new rule forbids and precisely
    # the shape of B1 one directory over. The store this job was HANDED is the store it tops up.
    argv = [
        "--from", start.isoformat(), "--to", ceiling.isoformat(),
        *([] if store is None else ["--store", str(Path(store.root))]),
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
                 "exit_code": code, "q19_ceiling": ceiling.isoformat(),
                 "store": None if store is None else str(Path(store.root))},
    )


def refresh_corporate_actions(
    *, symbols: Sequence[str], today: date, allow_network: bool = False,
    cache_dir: Path | None = None,
    puller: Callable[..., Sequence] | None = None,
    data_root: Path | None = None,
    cache_root: Path | None = None,
) -> RefreshStep:
    """Incremental CA pull, so a factor effective TODAY is known before any bias is computed.

    The card's own reason: *"a split effective TODAY must be known before computing bias"*. The
    fetch is the reviewed chunk-3 engine (``corp_actions.fetch_nse_corporate_actions``, itself
    day-cached and gently paced per CONTEXT 4.1). What this step ADDS is the report a screener
    needs at 08:45: **whether any ex-date lands on today or on either day of the bias pair**,
    because that is the case where a stale cache silently changes a bias rather than merely
    aging. An ordinary stale cache costs nothing; a cache that missed today's split is a wrong
    bias on every stock it touches.

    **THE FENCE IS ASKED HERE** (REVIEW_14 **B1**, closing REVIEW_13B Q3 where it was left
    open). :func:`acumen.backtest.fence_ca_cache` was built, works on every machine layout, and
    was never called on this path: the pull took ``allow_network`` straight from the CLI flag and
    the cache directory straight from ``--config``'s ``cache_root``, so a real
    ``--refresh --allow-network`` morning CREATED ``<cache_root>/ca/`` and accreted one
    ``nse_ca_<D-10>_<D>.json`` into the snapshot-protected tree every morning thereafter. The
    defect REVIEW_13B pinned was one module away from the fence built to stop it. The fence now
    stands between this step's flag and the fetch, judged against **the roots this job is
    actually running under** rather than against whatever ``config.yaml`` a process happened to
    load -- which is what makes a scratch-copy run fenced by its own scratch roots and a real
    morning fenced by the real ones.

    A fenced pull is a **downgrade to the cache, never a refusal**: the day-cache is read at any
    age (the 31-Jul-2026 offline ruling) and the morning goes on. When the fence has downgraded
    the pull and there is no cached window on disk to read, this step is ``ok`` and says so
    LOUDLY in its own detail: the report it produces is advisory -- the factor tables every bias
    really descends from come from :func:`acumen.backtest.build_factor_tables`, fenced
    identically, reading the cache the backtester has always read -- and a read-only law is not a
    reason to tell the operator his morning is broken. An operator who asked for OFFLINE and has
    no cache still gets the failure he asked about, unchanged.
    """
    from . import backtest as bt

    window_start = today - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    if puller is None:
        from . import corp_actions as ca

        puller = ca.fetch_nse_corporate_actions
    resolved, network, fence_reason = bt.fence_ca_cache(
        cache_dir=cache_dir, allow_network=allow_network,
        data_root=data_root, cache_root=cache_root,
    )
    fenced = bool(allow_network) and not network
    try:
        events = puller(
            window_start, today, allow_network=network, cache_dir=resolved, today=today
        )
    except Exception as exc:
        if not fenced:
            raise
        return RefreshStep(
            name="corporate actions", ok=True,
            detail=(
                f"{fence_reason}. NO cached window for "
                f"{window_start.isoformat()}..{today.isoformat()} is on disk at "
                f"{ca_cache_display(resolved)}, so THIS REPORT IS BLIND: an ex-date effective "
                f"today would not be named below ({type(exc).__name__}). The factor tables the "
                "bias descends from are unaffected -- they are built from the corporate-action "
                "cache the backtester reads, under the same fence"
            ),
            figures={
                "fenced": True, "fence_reason": fence_reason, "cache_dir": str(resolved),
                "events_total": None, "events_for_universe": None,
                "ex_dates_near_the_bias_pair": None,
                "window_start": window_start.isoformat(),
                "window_end": today.isoformat(),
                "unreadable": f"{type(exc).__name__}: {exc}",
            },
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
    if fenced:
        # Disclosed where the operator is already reading. The events above came off the
        # day-cache at whatever age it has, and that is a different sentence from "pulled".
        detail += f" [read from the day-cache, NOT refreshed -- {fence_reason}]"
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
            "fenced": fenced,
            "fence_reason": fence_reason,
            "cache_dir": str(resolved),
        },
    )


def ca_cache_display(cache_dir: Path) -> str:
    """The corporate-action day-cache directory, as the report names it. No I/O."""
    from . import corp_actions as ca

    return str(ca.cache_path(Path(cache_dir), "").parent)


def refresh_instrument_master(
    *, today: date, cache_dir: Path | None = None, allow_network: bool = False,
    pin: str | None = None,
    symbols: Sequence[str] = (),
) -> RefreshStep:
    """Fetch TODAY'S OWN instrument master and name it -- CONTEXT 4.7 / QUESTIONS.md Q-29.

    The architect's ruling of 08-Aug-2026: *"a live morning uses THE DAY'S OWN instrument master,
    fetched pre-open, named+hashed into the recording -- the replication target is the trader's
    chart AS OF THAT MORNING"*. The tick sizes CONTEXT 3.3's profile row grid, hence the POC,
    hence every entry, stop and target, so this file is a prerequisite of the morning rather than
    a convenience: without it the step is NOT ok and :attr:`RefreshReport.ok` is False.

    It also runs the ruling's second instruction -- *"the divergence detector reports pin-vs-day
    differences every morning as information"*. The symbols whose tick moved between the Q-20 pin
    and today's dump are NAMED in the report and in ``figures``, and nothing is refused for it:
    today's dump governs today, the pin governs the ledger, and the operator sees the difference
    instead of discovering it in a POC.
    """
    from . import backtest as bt
    from . import instrument_master as im
    from . import live_screener as ls
    from .config import load_config

    config = load_config(include_env=False)
    cache = Path(cache_dir) if cache_dir is not None else config.path("cache_root")
    wanted_name = im.master_cache_path(".", today).name
    try:
        master = im.load_instrument_master(
            cache_dir=cache, today=today, allow_network=allow_network
        )
    except Exception as exc:
        return RefreshStep(
            name="instrument master (TODAY's dump)", ok=False,
            detail=(
                f"{wanted_name} is not available: {type(exc).__name__}: {exc}. CONTEXT 4.7 runs "
                "a live morning on THE DAY'S OWN master; a stale snapshot is not a substitute, "
                "because the vendor's tick moves between dumps and it sizes the POC."
            ),
            figures={"master_file": wanted_name, "fetched": False},
        )
    path = im.master_cache_path(cache, today)
    digest = bt.file_sha256(path)

    divergence: dict[str, tuple[int, int]] = {}
    pin_name = pin if pin is not None else config.instrument_master
    pin_note = ""
    try:
        pinned, _pin_path, _pin_sha = bt.pinned_master(cache, pin_name)
    except Exception as exc:  # the pin is the LEDGER's law, not this morning's -- never fatal
        pin_note = f"pin {pin_name} unreadable ({type(exc).__name__}); no divergence computed"
    else:
        divergence = ls.master_tick_divergence(pinned, master, symbols or ())
    detail = f"{wanted_name} ({len(master):,} instruments), sha256 {digest[:12]}..."
    if divergence:
        named = ", ".join(
            f"{symbol} {pin_tick}->{day_tick}"
            for symbol, (pin_tick, day_tick) in sorted(divergence.items())
        )
        detail += (
            f"; TICK DIVERGENCE vs the Q-20 pin on {len(divergence)} symbol(s): {named} "
            "(reported as information -- today's dump governs today, the pin governs the ledger)"
        )
    elif pin_note:
        detail += f"; {pin_note}"
    elif symbols:
        detail += f"; no tick divergence vs the Q-20 pin over {len(symbols)} symbol(s)"
    return RefreshStep(
        name="instrument master (TODAY's dump)", ok=True, detail=detail,
        figures={
            "master_file": wanted_name,
            "master_sha256": digest,
            "instruments": len(master),
            "fetched": True,
            "pin": pin_name,
            "tick_divergence_vs_pin": {
                symbol: {"pin_paise": pin_tick, "day_paise": day_tick}
                for symbol, (pin_tick, day_tick) in sorted(divergence.items())
            },
        },
    )


# --- CONTEXT 4.7: the next morning's verdict on the last one -----------------------------------

#: The row mark for a symbol-day nothing could judge. Distinct from ``oracle-refused`` on purpose
#: (REVIEW_14 M15/M16): one says the exchange's record disagrees with this tool, the other says
#: the exchange's record is not there to ask.
NOT_VERIFIED_MARK: str = "NOT-VERIFIED"

#: Why a symbol could not be judged: its candles are not in the recording (M15).
NO_CANDLES_RECORDED: str = (
    "this symbol ALERTED but the recording holds no candle file for it, so neither battery "
    "could be run -- nothing about this symbol-day has been verified"
)

#: Why a symbol could not be judged: the oracle itself is absent (M16).
NO_ORACLE_ROW: str = "THE ORACLE HAS NOT SPOKEN"


def oracle_spoke(gates: DayGates) -> bool:
    """Did the exchange's record ANSWER for this symbol-day at all? (REVIEW_14 M16.)

    A gate-1P failure whose cause is :data:`acumen.quality_gates.GATE1P_NO_ORACLE` means the
    published bhavcopy has no row for the day -- *"the stored prices can be compared with
    nothing"*. That is the oracle being silent, and a silent oracle refuses nothing. Every other
    failure is a real disagreement between this tool's data and the exchange's, which is what
    CONTEXT 4.7's loud sentence is for.
    """
    from . import quality_gates as qg

    gate1p = gates.gate1p
    if gate1p is not None and not gate1p.passed and gate1p.cause == qg.GATE1P_NO_ORACLE:
        return False
    return True


def _blind_sentence(blind: Sequence["SymbolVerdict"]) -> str:
    names = ", ".join(verdict.symbol for verdict in blind)
    return (
        f"{len(blind)} LIVE-ALERTED symbol-day(s) could NOT be judged -- {names}. "
        "Their alerts are NOT withdrawn and NOT confirmed: the end-of-day battery was never "
        "able to run on them, and a verification that did not happen must not read as one "
        "that passed."
    )


@dataclass(frozen=True)
class SymbolVerdict:
    """One symbol of a verified day: what the live battery said, and what the oracle says now."""

    symbol: str
    live_passed: bool
    live_reason: str
    oracle_passed: bool
    oracle_reason: str
    alerted: tuple[str, ...]
    minutes: int
    #: Could this symbol be judged AT ALL? False when the recording holds no candle file for it
    #: (REVIEW_14 **M15**) or when the published bhavcopy has no row for the day, so gate 1P
    #: fails with :data:`acumen.quality_gates.GATE1P_NO_ORACLE` (**M16**). Both are "the oracle
    #: has not spoken", which is a different sentence from "the oracle REFUSES" and must never be
    #: rendered as one: the first withdraws nothing, the second withdraws a real alert.
    verified: bool = True
    #: Stamps ONE reply served twice -- CONTEXT 4.5 gate 2's first exclusion trigger, which both
    #: batteries below are handed so they can act on it (REVIEW_13 B2).
    duplicate_stamps: int = 0
    #: Stamps the vendor served twice with DIFFERENT values across polls. B331's reporting half,
    #: which had ZERO callers in ``src/`` until this finding gave it one: a revision is a real
    #: event about the feed and the morning after is where it has to be visible.
    revisions: int = 0

    @property
    def refused_after_alert(self) -> bool:
        """The LOUD case: this symbol produced live alerts and the oracle REFUSES its day.

        REVIEW_14 **M16**: an unjudgeable symbol is not a refused one. An absent bhavcopy row
        fails gate 1P by :data:`~acumen.quality_gates.GATE1P_NO_ORACLE` -- *"no raw daily row for
        this day, so the stored prices can be compared with nothing"* -- which is the exchange
        having said NOTHING, and over five dry-run days it withdrew real, correct alerts in a
        headline that must never be ignored. Withdrawing an alert the record has not refused
        trains the trader to ignore the one line that exists to stop him trading.
        """
        return bool(self.alerted) and self.verified and not self.oracle_passed

    @property
    def alerted_but_unverified(self) -> bool:
        """This symbol ALERTED and could not be judged at all (REVIEW_14 M15 / M16).

        Not a pass, not a refusal, and above all not absent: a symbol dropped from the verdict
        list is counted nowhere, which is how ``0 alerted`` came to be printed over a recording
        holding three alerts.
        """
        return bool(self.alerted) and not self.verified


@dataclass(frozen=True)
class MorningVerification:
    """CONTEXT 4.7's next-pre-open verdict over one prior recording.

    ``ok`` is deliberately NOT "everything passed": a day the oracle refuses is a fact about the
    market's data, not a failure of this job, and a refresh that reported NOT READY every time a
    stock had a bad print would train the operator to ignore it. What must never be quiet is
    :attr:`refused_after_alert` -- a day this tool ALERTED on that the exchange's own record then
    refuses -- and that is what the report says loudly and what the dashboard shows in the
    banner's own colour.
    """

    day: date
    recording_root: str
    verdicts: tuple[SymbolVerdict, ...]
    oracle_available: bool = True
    note: str = ""

    @property
    def alerted(self) -> tuple[SymbolVerdict, ...]:
        return tuple(verdict for verdict in self.verdicts if verdict.alerted)

    @property
    def refused_after_alert(self) -> tuple[SymbolVerdict, ...]:
        return tuple(verdict for verdict in self.verdicts if verdict.refused_after_alert)

    @property
    def alerted_but_unverified(self) -> tuple[SymbolVerdict, ...]:
        """Symbols that alerted and could not be judged -- REVIEW_14 M15 and M16, counted."""
        return tuple(verdict for verdict in self.verdicts if verdict.alerted_but_unverified)

    @property
    def unverified(self) -> tuple[SymbolVerdict, ...]:
        return tuple(verdict for verdict in self.verdicts if not verdict.verified)

    @property
    def oracle_passed(self) -> tuple[SymbolVerdict, ...]:
        return tuple(verdict for verdict in self.verdicts if verdict.oracle_passed)

    @property
    def headline(self) -> str:
        if not self.oracle_available:
            return f"{self.day.isoformat()}: NOT VERIFIED -- {self.note}"
        bad = self.refused_after_alert
        blind = self.alerted_but_unverified
        if bad:
            names = ", ".join(verdict.symbol for verdict in bad)
            head = (
                f"{self.day.isoformat()}: THE EXCHANGE'S RECORD REFUSES {len(bad)} "
                f"LIVE-ALERTED SYMBOL-DAY(S) -- {names}. Those alerts were produced on data the "
                "end-of-day battery does not accept; treat them as withdrawn."
            )
            return head + ("" if not blind else " " + _blind_sentence(blind))
        if blind:
            # REVIEW_14 **M15**: this is the case that used to print "0/0 ... 0 alerted, 0
            # alerted-then-refused" over a morning holding three alerts, and the dry-run week's
            # debrief read it as "yesterday checked out". It is NOT a pass and it is NOT a
            # refusal -- nothing has been verified, and the sentence has to say so first.
            return f"{self.day.isoformat()}: NOT VERIFIED -- " + _blind_sentence(blind)
        return (
            f"{self.day.isoformat()}: verified against the published bhavcopy -- "
            f"{len(self.oracle_passed)}/{len(self.verdicts)} symbol-day(s) pass the FULL battery, "
            f"{len(self.alerted)} alerted, 0 alerted-then-refused"
            + (
                "." if not self.unverified else
                f"; {len(self.unverified)} symbol-day(s) could not be judged at all "
                "(the oracle has not spoken for them), none of which alerted."
            )
        )

    def as_dict(self) -> dict:
        return {
            "trade_date": self.day.isoformat(),
            "recording_root": self.recording_root,
            "oracle_available": self.oracle_available,
            "note": self.note,
            "headline": self.headline,
            "refused_after_alert": [v.symbol for v in self.refused_after_alert],
            "alerted_but_unverified": [v.symbol for v in self.alerted_but_unverified],
            "unverified": [v.symbol for v in self.unverified],
            "verdicts": [
                {
                    "symbol": v.symbol,
                    "live_passed": v.live_passed,
                    "live_reason": v.live_reason,
                    "oracle_passed": v.oracle_passed,
                    "oracle_reason": v.oracle_reason,
                    "verified": v.verified,
                    "alerted": list(v.alerted),
                    "minutes": v.minutes,
                    "duplicate_stamps": v.duplicate_stamps,
                    "revisions": v.revisions,
                }
                for v in sorted(self.verdicts, key=lambda v: v.symbol)
            ],
        }

    def render(self) -> str:
        lines = [
            f"YESTERDAY VERIFIED  {self.day.isoformat()}   (CONTEXT 4.7)",
            "=" * 72,
            self.headline,
            "-" * 72,
        ]
        for verdict in sorted(self.verdicts, key=lambda v: v.symbol):
            mark = "REFUSED-AFTER-ALERT" if verdict.refused_after_alert else (
                NOT_VERIFIED_MARK if not verdict.verified else
                "oracle-pass" if verdict.oracle_passed else "oracle-refused"
            )
            lines.append(
                f"  {verdict.symbol:<14} live={'pass' if verdict.live_passed else 'refused'}  "
                f"{mark:<20} alerts={','.join(verdict.alerted) or '-'}"
            )
            if not verdict.oracle_passed or not verdict.verified:
                lines.append(f"      {verdict.oracle_reason}")
        lines.append("=" * 72)
        return "\n".join(lines) + "\n"


def verify_prior_recording(
    recording: LiveRecording,
    pipeline: SignalPipeline,
    *,
    day: date,
) -> MorningVerification:
    """Run the FULL battery over a prior LIVE recording, against the now-published bhavcopy.

    CONTEXT 4.7, executed: *"The next pre-open runs the FULL battery on the prior recording
    against the published bhavcopy and reports both verdicts; a live-alerted day the oracle
    refuses is named loudly."*

    The bars are the recording's own -- the bytes the morning actually decided on, not a fresh
    pull that might have been repaired since -- and they go through
    :meth:`acumen.signal_engine.SignalPipeline.gate_day`, which is the backtester's battery with
    nothing added. The LIVE verdict is recomputed the same way, from
    :func:`acumen.signal_engine.oracle_free_battery` over the same bars, so the two columns of
    the report are two batteries over one set of bytes rather than one battery and a memory.

    ``pipeline`` must be wired to the TOPPED-UP daily store (this job's previous step) and to the
    master the RECORDING names -- a day is re-judged under the ticks it ran on, which is the
    other half of the Q-29 ruling.
    """
    verdicts: list[SymbolVerdict] = []
    alerts_by_symbol: dict[str, list[str]] = {}
    for row in recording.alerts():
        alerts_by_symbol.setdefault(str(row.get("symbol", "")), []).append(str(row.get("kind")))

    judged_symbols = set(recording.symbols()) | set(alerts_by_symbol)
    for symbol in sorted(judged_symbols):
        bars = recording.bars(symbol, day)
        if not bars:
            # REVIEW_14 **M15**: this used to `continue`, so a symbol that ALERTED and whose
            # candle file is absent left the verdict list entirely -- and the headline then
            # asserted it had alerted zero times ("0/0 symbol-day(s) pass the FULL battery, 0
            # alerted, 0 alerted-then-refused") over an `alerts.jsonl` holding three alerts. A
            # false GREEN over a morning nothing verified is worse than no verification at all,
            # because the dry-run week's debrief reads it as "yesterday checked out".
            verdicts.append(SymbolVerdict(
                symbol=symbol, live_passed=False,
                live_reason=NO_CANDLES_RECORDED,
                oracle_passed=False, oracle_reason=NO_CANDLES_RECORDED,
                verified=False,
                alerted=tuple(sorted(set(alerts_by_symbol.get(symbol, ())))),
                minutes=0,
            ))
            continue
        # REVIEW_13 B2. `recording.bars()` de-duplicates a re-polled stamp exactly as the
        # screener's `merge_bars` does, and it must -- the engines need one bar per minute. But
        # running the BATTERY over the de-duplicated day meant the morning after could not see
        # the duplicate either, so a corrupt twin that had already won a live TRIGGER was
        # laundered a second time, past the very verification CONTEXT 4.7 exists for. Both
        # columns are now computed over the bars PLUS the twins, so gate 2 reaches its own
        # verdict on CONTEXT 4.5's first exclusion trigger.
        twins = recording.duplicate_bars(symbol, day)
        revisions = recording.revisions(symbol)
        judged = tuple(bars) + twins
        live_gates = oracle_free_battery(day, judged)
        oracle_gates: DayGates = pipeline.gate_day(symbol, day, judged)
        note = ""
        if twins:
            note = (
                f" [{len(twins)} duplicate stamp(s) in a single reply -- CONTEXT 4.5 gate 2's "
                "first exclusion trigger]"
            )
        if revisions:
            note += (
                f" [{len(revisions)} stamp(s) the vendor RE-SERVED with different values; the "
                "screener acted on the later one]"
            )
        # REVIEW_14 **M16**: gate 1P fails with GATE1P_NO_ORACLE when the published bhavcopy has
        # no row for this symbol-day -- which is the exchange having said NOTHING, not the
        # exchange refusing. Rendering the two the same way loudly withdrew real, correct alerts
        # over five dry-run days, and `oracle_available` plus the NOT-VERIFIED branch that exist
        # for exactly this case were dead code. The oracle is asked whether it SPOKE first.
        spoke = oracle_spoke(oracle_gates)
        verdicts.append(SymbolVerdict(
            symbol=symbol,
            live_passed=live_gates.usable,
            live_reason=(live_gates.refusal or "the oracle-free battery accepts this day") + note,
            oracle_passed=oracle_gates.usable,
            oracle_reason=(
                (
                    oracle_gates.refusal_detail[1] if oracle_gates.refusal_detail is not None
                    else "the FULL battery accepts this day"
                ) if spoke else
                f"{NO_ORACLE_ROW} -- the published bhavcopy has no row for this symbol-day, so "
                "nothing has been verified either way"
            ) + note,
            verified=spoke,
            alerted=tuple(sorted(set(alerts_by_symbol.get(symbol, ())))),
            minutes=len(bars),
            duplicate_stamps=len(twins),
            revisions=len(revisions),
        ))
    return MorningVerification(
        day=day, recording_root=str(recording.root), verdicts=tuple(verdicts),
    )


def verify_yesterday(
    *,
    today: date,
    calendar: cal.TradingCalendar,
    data_root: Path,
    cache_dir: Path | None = None,
    recording_root: Path | None = None,
) -> tuple[MorningVerification | None, RefreshStep]:
    """Find yesterday's LIVE recording and verify it. CONTEXT 4.7's next-pre-open duty.

    Absence is not failure and says so: on the first live morning, or after a replay-only day,
    there is no prior LIVE recording and the step reports that in one line. What IS reported
    loudly -- in the step's own ``detail``, so it reaches an operator who reads nothing else --
    is a live-alerted symbol-day the oracle refuses.
    """
    from . import backtest as bt
    from .config import load_config
    from .daily_store import DailyStore
    from .minute_store import MinuteStore

    prior = calendar.prev_trading_day(today)
    root = Path(recording_root) if recording_root is not None else Path(data_root) / "live"
    candidates = [
        LiveRecording.at(path) for path in sorted(root.glob(f"{prior.isoformat()}*"))
        if (path / "manifest.json").is_file()
    ] if root.is_dir() else []
    live_recordings = [
        rec for rec in candidates if rec.read_manifest().get("mode") == "live"
    ]
    if not live_recordings:
        return None, RefreshStep(
            name="verify yesterday (CONTEXT 4.7)", ok=True,
            detail=(
                f"no LIVE recording for {prior.isoformat()} under {root} -- nothing to verify "
                "(a replay needs no verification: its day already had a bhavcopy)"
            ),
            figures={"prior_day": prior.isoformat(), "verified": False},
        )

    recording = live_recordings[-1]
    manifest = recording.read_manifest()
    config = load_config(include_env=False)
    cache = Path(cache_dir) if cache_dir is not None else config.path("cache_root")
    try:
        master, _path, _sha = bt.named_master(cache, str(manifest["master_file"]))
    except Exception as exc:
        return None, RefreshStep(
            name="verify yesterday (CONTEXT 4.7)", ok=False,
            detail=(
                f"{recording.root} names master {manifest.get('master_file')!r}, which cannot be "
                f"loaded: {type(exc).__name__}: {exc}. A day is re-judged under the ticks it ran "
                "on (Q-29), so it is not re-judged under another."
            ),
            figures={"prior_day": prior.isoformat(), "verified": False},
        )

    pipeline = SignalPipeline(
        minute_store=MinuteStore.at(Path(data_root) / "minute_store"),
        daily_store=DailyStore.at(Path(data_root) / "daily_store"),
        master=master,
        row_size=int(manifest.get("row_size") or config.row_size),
    )
    verification = verify_prior_recording(recording, pipeline, day=prior)
    recording.write_verification(verification.as_dict())
    bad = verification.refused_after_alert
    return verification, RefreshStep(
        name="verify yesterday (CONTEXT 4.7)", ok=True,
        detail=verification.headline,
        figures={
            "prior_day": prior.isoformat(),
            "verified": True,
            "recording": str(recording.root),
            "symbols": len(verification.verdicts),
            "oracle_pass": len(verification.oracle_passed),
            "alerted": len(verification.alerted),
            "refused_after_alert": [verdict.symbol for verdict in bad],
            "alerted_but_unverified": [
                verdict.symbol for verdict in verification.alerted_but_unverified
            ],
            "unverified": [verdict.symbol for verdict in verification.unverified],
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
    verify_prior: bool = True,
    recording_root: Path | None = None,
) -> tuple[cal.TradingCalendar | None, tuple[str, ...], RefreshReport]:
    """Run every pre-open step in order and report each one. Returns what the screener needs.

    The calendar is ``None`` only when the published master could not be read at all, which is
    the one case :attr:`RefreshReport.ok` is guaranteed False for -- so no caller ever reaches a
    ``None`` calendar past its own readiness check.

    The bias itself is NOT computed here -- :func:`acumen.live_screener.build_live_screener`
    computes it through the backtester's own runner, which is the only way to be sure the
    screener's 09:00 bias and the backtester's bias for the same day are the same number rather
    than two implementations that agree today.

    ``verify_prior`` runs CONTEXT 4.7's next-pre-open verification of yesterday's LIVE recording.
    It is on by default because the ruling makes it a duty rather than an option; it is a
    parameter at all so that a test can drive the job without a recordings tree beside it.
    """
    steps: list[RefreshStep] = []
    calendar: cal.TradingCalendar | None
    try:
        calendar, step = refresh_calendar(
            cache_dir=cache_dir, today=today, allow_network=allow_network, daily_store=store
        )
    except Exception as exc:
        # REVIEW_14, found while building B1's certifying test: this was the ONE step with no
        # guard, so a published holiday master that could not be read -- an offline morning with
        # no day-cache, a refused endpoint at 08:45 -- left `main` with a traceback from four
        # layers down instead of REVIEW_12C C2's one sentence and exit 1. Every step still runs
        # that CAN run; the two that need a calendar say why they did not, which is the same
        # discipline the rest of this job already had ("the job did not abandon itself at the
        # first failure, and the operator is told about both problems in one preflight").
        calendar = None
        step = RefreshStep(
            name="calendar (published NSE)", ok=False,
            detail=(
                f"{type(exc).__name__}: {exc}. The PUBLISHED master governs a live morning "
                "(QUESTIONS.md C5) and the store-derived calendar cannot answer for today by "
                "construction, so there is no fallback"
            ),
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

    if calendar is None:
        steps.append(RefreshStep(
            name="daily store (bhavcopy top-up)", ok=False,
            detail=NOT_RUN_WITHOUT_A_CALENDAR.format(
                what="the Q-19 ceiling is the last COMPLETED trading day, which only a calendar "
                     "can name"
            ),
        ))
    else:
        try:
            steps.append(refresh_daily_store(
                store, calendar, today=today, allow_network=allow_network, runner=daily_runner
            ))
        except Exception as exc:
            steps.append(RefreshStep(
                name="daily store (bhavcopy top-up)", ok=False,
                detail=f"{type(exc).__name__}: {exc}",
            ))

    try:
        # REVIEW_14 B1: the fence is judged against the roots THIS job runs under -- the store
        # the caller handed in and the cache directory it was given -- so a scratch-copy run is
        # fenced by its own roots and a real morning by the real ones.
        steps.append(refresh_corporate_actions(
            symbols=universe, today=today, allow_network=allow_network, cache_dir=cache_dir,
            data_root=data_root_for(store), cache_root=cache_dir,
        ))
    except Exception as exc:
        steps.append(RefreshStep(
            name="corporate actions", ok=False, detail=f"{type(exc).__name__}: {exc}"
        ))

    # CONTEXT 4.7 / Q-29. AFTER the universe (it names the symbols the divergence is reported
    # over) and before anything that needs a tick.
    try:
        steps.append(refresh_instrument_master(
            today=today, cache_dir=cache_dir, allow_network=allow_network, symbols=universe,
        ))
    except Exception as exc:
        steps.append(RefreshStep(
            name="instrument master (TODAY's dump)", ok=False,
            detail=f"{type(exc).__name__}: {exc}",
        ))

    # CONTEXT 4.7 / Q-28. AFTER the bhavcopy top-up: the oracle it verifies against is the file
    # that step just fetched.
    verification: MorningVerification | None = None
    if verify_prior and calendar is None:
        steps.append(RefreshStep(
            name="verify yesterday (CONTEXT 4.7)", ok=False,
            detail=NOT_RUN_WITHOUT_A_CALENDAR.format(
                what="which day 'yesterday' was is a calendar question"
            ),
        ))
    elif verify_prior:
        try:
            verification, step = verify_yesterday(
                today=today, calendar=calendar, data_root=data_root_for(store),
                cache_dir=cache_dir, recording_root=recording_root,
            )
            steps.append(step)
        except Exception as exc:
            steps.append(RefreshStep(
                name="verify yesterday (CONTEXT 4.7)", ok=False,
                detail=f"{type(exc).__name__}: {exc}",
            ))

    return calendar, universe, RefreshReport(
        day=today, steps=tuple(steps), verification=verification
    )


def data_root_for(store: DailyStore) -> Path:
    """The ``data_root`` a daily store lives under -- ``<data_root>/daily_store``'s parent.

    Derived from the store the caller already handed in rather than re-read from config, so a
    test (or an operator pointing at a copy) cannot end up verifying yesterday out of one tree
    while topping up another.
    """
    return Path(store.root).parent


__all__ = [
    "DEFAULT_LOOKBACK_DAYS",
    "NOT_RUN_WITHOUT_A_CALENDAR",
    "NOT_VERIFIED_MARK",
    "NO_CANDLES_RECORDED",
    "NO_ORACLE_ROW",
    "MorningVerification",
    "ca_cache_display",
    "oracle_spoke",
    "RefreshError",
    "RefreshReport",
    "RefreshStep",
    "SymbolVerdict",
    "data_root_for",
    "last_completed_trading_day",
    "morning_refresh",
    "refresh_calendar",
    "refresh_corporate_actions",
    "refresh_daily_store",
    "refresh_instrument_master",
    "refresh_universe",
    "verify_prior_recording",
    "verify_yesterday",
]
