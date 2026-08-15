"""The screener's operator entry point (chunk 13).

    python -m acumen.run_screener --mode replay --day 2026-06-10 --symbols HDFCBANK
    python -m acumen.run_screener --mode live --day 2026-08-10 --refresh --allow-network

Two modes, one pipeline:

* ``replay`` -- **the default**. A past day, served bar by bar from the minute lake as if the
  clock were running, on a VIRTUAL clock so it finishes in seconds. This is the mode the chunk's
  replay invariant runs in, and it is a real exercise of the live screener rather than of a
  stand-in. A replayed LIVE recording runs under the master that recording names (CONTEXT 4.7).
* ``live`` -- today. Unblocked by the architect's 08-Aug-2026 ruling and governed by **CONTEXT
  4.7**: the ORACLE-FREE battery per sweep, the disclosed line on every alert, the day's own
  instrument master, and the next pre-open's full-battery verdict on this day. It takes an
  EXPLICIT ``--mode live``, it prints section 4.7's disclosure before it starts, it attaches the
  phone only under ``--telegram``, and it stays in DRY RUN unless ``--live-alerts`` is also
  passed -- three separate deliberate acts between an operator and a message on somebody's
  phone, all three of them in :func:`telegram_is_live` (REVIEW_14 H1).

The preflight prints everything a later reader would need to reproduce the session: the
instrument master and its digest with the reason THAT master governs, the calendar reading and
which source governed it (the C5 duty), the boundaries, the battery posture, and the recording
it will write. It prints no credential and reads none (CLAUDE.md rule 4 -- and there is no order
endpoint anywhere on this path, which :mod:`tests.test_live_safety` proves by AST).

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

from . import live_dashboard as dash
from . import live_screener as ls
from .config import load_config
from .daily_store import DailyStore
from .live_recording import CALENDAR_PUBLISHED, LiveRecording, RecordedAlert
from .live_refresh import morning_refresh
from .live_source import StoredDayBarSource
from .minute_store import MinuteStore
from .telegram_sink import SUMMARY_EVENT, TelegramSink, credentials_present


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="acumen.run_screener", description="Acumen live screener (chunk 13)"
    )
    parser.add_argument("--mode", choices=("replay", "live"), default="replay")
    parser.add_argument("--day", required=True, help="trade date, YYYY-MM-DD")
    parser.add_argument("--symbols", default="", help="comma-separated; default = the universe")
    parser.add_argument("--label", default="", help="recording label suffix")
    parser.add_argument(
        "--recording-root", default="",
        help="where recordings are written; default <data_root>/live. Point it elsewhere to "
             "keep an exploratory run entirely outside the stores (CLAUDE.md data-store safety)",
    )
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--allow-network", action="store_true",
                        help="permit the pre-open refresh to pull (gently, day-cached)")
    parser.add_argument("--refresh", action="store_true",
                        help="run the pre-open morning refresh first")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--live-alerts", action="store_true",
                        help="turn OFF dry-run; alerts are marked live in the recording")
    parser.add_argument("--telegram", action="store_true",
                        help="attach the Telegram sink (chunk 14). It SENDS only when "
                             "--live-alerts is passed as well; on its own it logs what it "
                             "would have sent. Needs TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID "
                             "in .env, which are never printed, logged or committed")
    parser.add_argument("--no-wait", action="store_true",
                        help="live mode: sweep every boundary immediately instead of waiting for "
                             "the clock. For a same-day catch-up after a late start, never for a "
                             "morning that has not happened")
    return parser.parse_args(argv)


def telegram_is_live(args: argparse.Namespace) -> bool:
    """May a message reach the trader's phone this session? **REVIEW_14 H1, in one place.**

    THREE deliberate acts, all required and all named here so no reader has to assemble them
    from a boolean expression at a call site:

    * ``--mode live`` -- the session is about TODAY. This is the term that was MISSING: the gate
      was ``bool(args.live_alerts and args.telegram)``, the mode defaults to ``replay``, and the
      review put two real messages on the transport with ``--day 2020-03-19 --telegram
      --live-alerts``. The first of them named a price, a stop, a target and a quantity, with
      nothing on it about 2020;
    * ``--telegram`` -- the sink is attached at all;
    * ``--live-alerts`` -- dry run is OFF.

    A session failing any one of them still computes, shows, records and logs every alert. What
    it does not do is send.
    """
    return bool(args.mode == "live" and args.telegram and args.live_alerts)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    day = date.fromisoformat(args.day)
    config = load_config(Path(args.config), include_env=False)
    data_root = config.path("data_root")
    live = args.mode == "live"

    if live:
        # CONTEXT 4.7's disclosure, BEFORE anything runs. An operator who reads only the first
        # screen of a live morning has still read the posture he is running under.
        print("=" * 78)
        print(ls.LIVE_STARTUP_DISCLOSURE)
        print("=" * 78)
        print("", flush=True)

    symbols = tuple(
        part.strip().upper() for part in args.symbols.split(",") if part.strip()
    )

    verification = None
    published_calendar = None
    if args.refresh:
        calendar, universe, report = morning_refresh(
            today=day,
            store=DailyStore.at(data_root / "daily_store"),
            cache_dir=config.path("cache_root"),
            allow_network=args.allow_network,
            symbols=symbols or None,
            recording_root=Path(args.recording_root) if args.recording_root else None,
        )
        print(report.render(), flush=True)
        verification = report.verification
        if not report.ok:
            return 1
        symbols = symbols or universe
        # REVIEW_13 M17: the C5 duty is EXECUTED in refresh_calendar and used to be thrown away
        # one line later (`del calendar`), so every recording ever written stamped
        # "published-nse-holiday-master" beside readings taken from the derived store scan. The
        # calendar the refresh cross-checked is the calendar the session runs and records.
        #
        # REVIEW_14 **B3**: what is handed on is the PUBLISHED master, which carries no explicit
        # trading-day set -- and `backtest.build_runner` refuses exactly that, so this line used
        # to end the operator's 08:45 command with "the screener cannot start" AFTER the refresh
        # had run. `build_live_screener` now COMPOSES it through `calendar.live_trading_calendar`
        # (published for today, the store's own scan for the history behind it) instead of
        # passing it on raw, so the calendar this session records is still the one the refresh
        # cross-checked and it is one the runner accepts.
        published_calendar = calendar

    if not symbols:
        print("no symbols: pass --symbols, or --refresh to take the F&O universe")
        return 1

    recording = LiveRecording.for_day(
        Path(args.recording_root).parent if args.recording_root else data_root,
        day, label=args.label or args.mode,
    ) if not args.recording_root else LiveRecording.at(
        Path(args.recording_root) / f"{day.isoformat()}-{args.label or args.mode}"
    )
    # A live morning runs on the wall clock (and WAITS for each candle to close); a replay runs
    # on a virtual one and finishes in seconds. Nothing else about the two paths differs here.
    clock: ls.Clock = (
        ls.SystemClock() if live
        else ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time()))
    )
    screen = ls.ScreenAlertSink()
    sound = ls.SoundAlertSink()
    collected = ls.CollectingAlertSink()
    # CHUNK 14: Telegram attaches by BEING a sink (the protocol chunk 13 reserved for it) and by
    # nothing else -- no line of the screener changed to make this work. It sends only under all
    # THREE acts (REVIEW_14 H1); a dry-run or replayed morning logs the message and sends nothing.
    telegram = TelegramSink(live=telegram_is_live(args))
    sinks: tuple[ls.AlertSink, ...] = (screen, sound, collected)
    if args.telegram:
        sinks = sinks + (telegram,)

    try:
        screener = ls.build_live_screener(
            day, symbols,
            # A PREFLIGHT opens no broker session. It exists to be run before the bell, by an
            # operator checking what the morning would do, and a check that logs in is a check
            # nobody runs twice.
            source=PreflightOnlySource() if args.preflight_only
            else _bar_source(live, config, data_root, allow_network=args.allow_network),
            recording=recording, clock=clock, mode=args.mode,
            sinks=sinks,
            dry_run=not args.live_alerts,
            allow_network=args.allow_network,
            # --config governs the whole session, not only what this module reads: the stores
            # and the instrument-master cache come from the file the operator named.
            data_dir=data_root,
            cache_dir=config.path("cache_root"),
            # REVIEW_13 M17 / F2: whichever calendar this session really ran on, named.
            calendar=published_calendar,
            calendar_source=None if published_calendar is None else CALENDAR_PUBLISHED,
        )
    except ls.BlockedByOpenQuestion as exc:
        # The STOP rule, at the operator's screen. Empty today (ls.LIVE_BLOCKING_QUESTIONS), and
        # kept reachable because the next class-A hole a live session meets needs this exit.
        print("THE SCREENER IS BLOCKED, and this is not a bug:")
        print("")
        print(str(exc))
        return 1
    except Exception as exc:
        # REVIEW_12C finding C2's standard, applied to the newest runnable path: a missing
        # master, an absent store or a refused login reaches the operator as one sentence and
        # exit 1, never as a traceback from four layers down.
        print(f"the screener cannot start: {type(exc).__name__}: {exc}")
        return 1

    for line in _preflight_lines(
        screener, recording, args.mode, telegram=args.telegram,
        data_root=data_root, cache_root=config.path("cache_root"),
        allow_network=args.allow_network,
    ):
        print(line, flush=True)
    if args.preflight_only:
        return 0
    print("", flush=True)

    # REVIEW_13 B8: crash-safe resume, through the shipped entry point. `restore()` existed,
    # worked and round-tripped the dedup set -- and had no caller in src/, so after any death
    # the set started empty and every alert of the day went out a second time, TRIGGER included
    # (measured: a real terminate() and restart re-sent four alerts). plan.md's chunk-13 card
    # requires "state persistence (crash-safe resume intra-day)"; this is the line that
    # delivers it to the operator rather than to the class.
    if screener.restore():
        print(
            f"RESUMED from {recording.root}: {len(screener.sweeps_done)} sweep(s) already done, "
            f"{len(screener.alerted)} alert(s) already delivered and NOT re-sent.",
            flush=True,
        )

    def after(report: ls.SweepReport) -> None:
        dash.write_dashboard(
            recording.root, day=day, now=report.boundary,
            grouped=screener.by_phase(), alerts=tuple(collected.alerts),
            banner=screener.banner, dry_run=screener.dry_run,
            disclosure=screener.disclosure, verification=verification,
        )

    def before(boundary: datetime) -> None:
        """Reach the boundary. A live morning WAITS for the candle; a replay just moves."""
        if not live:
            clock.set(boundary)
        elif not args.no_wait:
            ls.wait_for_boundary(clock, boundary)

    # REVIEW_13 B4 + B8: the CLI CALLS the loop instead of re-implementing it. run_day() sweeps
    # every boundary AND calls close_day(), whose 15:30 poll is what makes the recording a whole
    # 375-minute session -- without it every real recording stopped at 15:14 and CONTEXT 4.7's
    # next-morning verification flipped 22.05% of oracle-passing days to REFUSED, so its loud
    # banner would have fired on roughly one alerted day in five.
    reports = screener.run_day(on_sweep=after, before_sweep=before)

    if live:
        # The session token dies at midnight either way; ending it here means a leaked or
        # logged token is not still valid for the rest of the trading day (REVIEW_13 B5).
        _logout(screener.source)

    print("")
    print(dash.render_text(
        day=day, now=reports[-1].boundary, grouped=screener.by_phase(),
        alerts=tuple(collected.alerts), banner=screener.banner, dry_run=screener.dry_run,
        disclosure=screener.disclosure, verification=verification,
    ))
    if args.telegram:
        # A silent phone must never be ambiguous: this line says whether that silence was
        # "nothing fired", "the sends failed" or "an alert was refused as unvouched".
        print(telegram.summary())
        # ...and the same line now also LEAVES the terminal. The architect's 14-Aug-2026 ruling:
        # "the END-OF-DAY SUMMARY is a card line item and lands in chunk 14 -- routed to the
        # phone via the sink at close, not only the terminal." run_day() has returned, so
        # close_day()'s 15:30 poll is done and the day is whole; this is the last thing the
        # morning does.
        _end_of_day_summary(
            telegram, recording, day=day, disclosure=screener.disclosure,
        )
    print(f"recording: {recording.root}")
    print(f"dashboard: {recording.root / 'dashboard.html'}")
    return 0


def _end_of_day_summary(
    telegram: TelegramSink,
    recording: LiveRecording,
    *,
    day: date,
    disclosure: str = "",
) -> bool:
    """The morning's ONE summary message to the phone, at the close. Never raises.

    plan.md's chunk-14 card lists *"end-of-day summary message"*; the architect's 14-Aug-2026
    ruling says it goes to the phone through the sink and not only to this terminal. Everything
    about HOW it is sent belongs to the sink (the ``--live-alerts`` gate, the dry-run labelling,
    the degrade-to-silence, the credential rule). What belongs HERE is the one thing a sink
    cannot hold: **the memory that it already went**.

    A resumed morning re-runs the whole day into the same recording -- that is what
    :meth:`~acumen.live_screener.LiveScreener.restore` is for -- so without a mark on disk the
    trader would get a second summary for the same day. The mark is the recording's own event
    log, written only AFTER a real send and read before the next attempt, which is the same
    discipline REVIEW_13 M23 set for the alert dedup set. A send that FAILED writes nothing, so
    a restart still owes the trader his summary.

    **The alerts are the RECORDING's, not this process's** (REVIEW_14 **H2**). The summary used
    to be built from the sink that collected what this process delivered -- and a resumed morning
    delivers nothing, because ``restore()`` correctly re-reads a dedup set that already holds the
    day's alerts. So the one summary of a crashed-and-resumed morning said *"no alerts today --
    the screener ran the whole session and nothing fired"* while ``alerts.jsonl`` in the same
    recording held armed 11:15, trigger 11:30 and exit 11:45. That defeats B402's stated purpose
    exactly: the message exists so a silent phone is never ambiguous between "no signal" and
    "the tool has stopped", and on the one morning where the ambiguity is real it asserted the
    wrong one. ``recording.alerts()`` holds the WHOLE day however many processes produced it,
    which is the only list that can be right after a resume.
    """
    try:
        already = any(row.get("kind") == SUMMARY_EVENT for row in recording.events())
    except Exception:  # a recording too damaged to read is not a reason to skip the summary
        already = False
    if already:
        print(
            "telegram: the end-of-day summary already went out for this recording -- not re-sent"
        )
        return False
    alerts = recorded_alerts(recording)
    if not telegram.send_end_of_day(alerts, day=day, disclosure=disclosure):
        return False
    recording.record_event(
        SUMMARY_EVENT, at=datetime.combine(day, ls.SESSION_END),
        detail=f"{len({alert.symbol for alert in alerts})} symbol(s), {len(alerts)} alert(s)",
    )
    return True


def recorded_alerts(recording: LiveRecording) -> tuple[RecordedAlert, ...]:
    """Every alert in ``alerts.jsonl``, as the objects the sink already knows how to read.

    The whole day, whatever number of processes produced it -- which is the property REVIEW_14
    H2 turns on. A row too damaged to parse is skipped rather than allowed to cost the trader
    his summary; the recording is append-only JSONL and a truncated last line is the ordinary
    shape of a kill.
    """
    out: list[RecordedAlert] = []
    try:
        rows = recording.alerts()
    except Exception:
        return ()
    for row in rows:
        try:
            out.append(RecordedAlert(
                kind=str(row["kind"]), symbol=str(row["symbol"]),
                at=datetime.fromisoformat(str(row["at"])),
                payload=dict(row.get("payload") or {}),
            ))
        except Exception:  # pragma: no cover -- a half-written row is not worth a lost summary
            continue
    return tuple(out)


def _logout(source) -> None:
    """End the broker session if this one opened it. Best-effort, never fatal.

    A read-only session that is simply abandoned stays valid until midnight. REVIEW_13 B5
    measured the API key and bearer token being written to ``logs/`` on this machine; the guard
    that stops the writing is in :mod:`acumen.smartapi_client`, and this is the other half --
    the token a leak might have carried is dead by the time the operator reads the log.
    """
    client = getattr(source, "client", None)
    if client is None:
        return
    try:
        client.logout()
    except Exception:  # pragma: no cover -- a logout that fails changes nothing
        pass


def _bar_source(live: bool, config, data_root: Path, *, allow_network: bool):
    """Where a session's 1-minute bars come from. CONTEXT 4.4: the same endpoint, both modes.

    A replay reads the minute lake; a live morning reads ``getCandleData`` through the reviewed
    chunk-5A client -- the ONE broker method this repo is allowed to call, and the one
    :mod:`tests.test_live_safety` proves by AST is the only one it names.
    """
    if not live:
        return StoredDayBarSource(MinuteStore.at(data_root / "minute_store"))
    from .instrument_master import load_instrument_master
    from .live_source import SmartApiBarSource
    from .smartapi_client import Credentials, SmartApiClient

    if not allow_network:
        raise ScreenerStartError(
            "a LIVE morning reads the vendor's candle endpoint, so it needs --allow-network. "
            "Without it nothing is fetched and nothing is faked."
        )
    client = SmartApiClient(credentials=Credentials.from_env()).login()
    return SmartApiBarSource(
        client=client,
        master=load_instrument_master(cache_dir=config.path("cache_root")),
    )


class ScreenerStartError(RuntimeError):
    """The operator asked for a session this machine cannot start. Reported, never a traceback."""


class PreflightOnlySource:
    """A bar source that refuses to be used. What ``--preflight-only`` runs on.

    It is a real object rather than ``None`` so that the preflight exercises the same wiring the
    morning will -- the runner, the master, the bias map, the recording's manifest -- and stops
    exactly at the point where data would be fetched.
    """

    def fetch(self, symbol: str, day, upto):  # pragma: no cover -- ASSERTED BY NOT BEING CALLED
        from .live_source import BarSourceError

        raise BarSourceError(
            "this is a preflight; no candle is fetched and no broker session is opened"
        )


def _ca_note(data_root: Path, cache_root: Path, *, allow_network: bool) -> str:
    """What happened to the corporate-action cache this session, in the fence's own words.

    REVIEW_14 B1's neighbour, found while closing it: the fence was asked WITHOUT the roots this
    session is running under, so it fell back to whatever ``config.yaml`` the process loaded and
    printed *"refresh permitted: ... is outside the stores"* on a ``--config``-scoped run whose
    pull the same fence had just refused. The preflight now asks the question the run asked.
    """
    from . import backtest as bt

    _resolved, _refreshed, reason = bt.fence_ca_cache(
        cache_dir=data_root / bt.CA_CACHE_SUBDIR, allow_network=allow_network,
        data_root=data_root, cache_root=cache_root,
    )
    return reason


def _preflight_lines(
    screener: ls.LiveScreener,
    recording: LiveRecording,
    mode: str,
    *,
    telegram: bool = False,
    data_root: Path | None = None,
    cache_root: Path | None = None,
    allow_network: bool = False,
) -> list[str]:
    manifest = recording.read_manifest()
    calendar = manifest.get("calendar", {})
    gated = len(screener.gates)
    live = mode == "live"
    battery = (
        f"ORACLE-FREE, per sweep (CONTEXT 4.7): gate 2 with the Q-21(a) open test, the Q-17 "
        f"candle-level drops, candle validity. Gates 1 and 1P are structurally inapplicable to "
        f"same-day data"
        if live else
        f"CONTEXT 4.6's FULL battery: {gated} symbol-day(s) measured from the STORED whole day "
        f"(the backtester's own verdict)"
    )
    # REVIEW_13 M9: the provenance line is derived from the FILE that was actually resolved,
    # not from the mode flag. It used to say "THIS DAY'S OWN dump" whenever the mode was live,
    # including when `master_file` had walked around the resolution entirely.
    why_master = screener.master_reason or manifest.get("master_reason") or "unrecorded"
    lines = [
        "=" * 78,
        f"ACUMEN SCREENER PREFLIGHT   {screener.day.isoformat()}   mode={mode}",
        "=" * 78,
        f"spec                 {manifest.get('spec_version')}   code {manifest.get('code_sha')}",
        f"instrument master    {manifest.get('master_file')}",
        f"                     sha256 {manifest.get('master_sha256')}",
        f"                     {why_master}",
        f"row size             {manifest.get('row_size')}",
        f"risk / cost (paise)  {manifest.get('risk_per_trade_paise')} / "
        f"{manifest.get('cost_paise')}",
        f"symbols              {len(screener.symbols)} screened",
        f"biases resolved      {len(screener.biases)}",
        f"bias series seeded   {manifest.get('seed_from')} "
        f"(CONTEXT 3.2's carry needs history to carry from)",
        f"gate battery         {battery}",
        f"calendar             {calendar.get('governing_source')} governs; "
        f"trading day = {calendar.get('is_trading_day')}, "
        f"standard session = {calendar.get('is_standard_session')}",
        f"                     store-scan cross-check found "
        f"{len(calendar.get('non_standard_sessions_store_scan', []))} non-standard session(s)",
        f"boundaries           {len(manifest.get('boundaries', []))} "
        f"({ls.POC_BOUNDARY} POC pass, last {ls.LAST_BOUNDARY})",
        f"alerts               {'DRY RUN (log only)' if screener.dry_run else 'LIVE'}"
        + (f"   [{screener.disclosure}]" if screener.disclosure else ""),
        f"recording            {recording.root}",
        # REVIEW_13B Q3's other half: "nothing discloses it -- not the preflight, not the
        # manifest, not the recording". `fence_ca_cache` is pure and decides nothing here; it
        # is asked the same question `build_runner` asked it, so the operator reads what really
        # happened to the corporate-action cache rather than inferring it from a flag.
        "corporate actions    " + _ca_note(
            data_root if data_root is not None else load_config(include_env=False).path(
                "data_root"
            ),
            cache_root if cache_root is not None else load_config(include_env=False).path(
                "cache_root"
            ),
            allow_network=allow_network,
        ),
    ]
    if telegram:
        # Whether the two keys EXIST, never what they are (CLAUDE.md rule 4). An operator whose
        # .env is short one key must learn it at 08:50 and not at 11:30.
        ready = credentials_present()
        lines.append(
            "telegram             "
            + ("SENDING" if not screener.dry_run else "attached, DRY RUN (nothing is sent)")
            + f"   credentials in .env: {'both present' if ready else 'MISSING'}"
        )
    if screener.excluded:
        # CONTEXT 4.7 / QUESTIONS.md Q-30, the architect's 08-Aug-2026 ruling: the quarantined
        # symbols are never screened AND the startup banner names them excluded. A universe six
        # short with nothing on screen to say which six is REVIEW_13 M2.
        lines.append(
            f"EXCLUDED             {len(screener.excluded)} symbol(s) NOT screened -- the "
            "screener alerts on what the backtester validated (CONTEXT 4.7 / Q-30):"
        )
        for symbol, reason in screener.excluded:
            lines.append(f"                     {symbol:<14} {reason}")
    lines.append("=" * 78)
    return lines


if __name__ == "__main__":  # pragma: no cover -- ASSERTED AT THE SOURCE (an AST test)
    raise SystemExit(main())
