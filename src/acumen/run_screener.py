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
  EXPLICIT ``--mode live``, it prints section 4.7's disclosure before it starts, and it stays in
  DRY RUN unless ``--live-alerts`` is also passed -- three separate deliberate acts between an
  operator and a live morning.

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
from .live_recording import LiveRecording
from .live_refresh import morning_refresh
from .live_source import StoredDayBarSource
from .minute_store import MinuteStore


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
    parser.add_argument("--no-wait", action="store_true",
                        help="live mode: sweep every boundary immediately instead of waiting for "
                             "the clock. For a same-day catch-up after a late start, never for a "
                             "morning that has not happened")
    return parser.parse_args(argv)


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
        del calendar

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

    try:
        screener = ls.build_live_screener(
            day, symbols,
            # A PREFLIGHT opens no broker session. It exists to be run before the bell, by an
            # operator checking what the morning would do, and a check that logs in is a check
            # nobody runs twice.
            source=PreflightOnlySource() if args.preflight_only
            else _bar_source(live, config, data_root, allow_network=args.allow_network),
            recording=recording, clock=clock, mode=args.mode,
            sinks=(screen, sound, collected),
            dry_run=not args.live_alerts,
            allow_network=args.allow_network,
            # --config governs the whole session, not only what this module reads: the stores
            # and the instrument-master cache come from the file the operator named.
            data_dir=data_root,
            cache_dir=config.path("cache_root"),
        )
    except ls.BlockedByOpenQuestion as exc:  # pragma: no cover -- nothing raises it today
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

    for line in _preflight_lines(screener, recording, args.mode):
        print(line, flush=True)
    if args.preflight_only:
        return 0
    print("", flush=True)

    def after(report: ls.SweepReport) -> None:
        if not live:
            clock.set(report.boundary)
        dash.write_dashboard(
            recording.root, day=day, now=report.boundary,
            grouped=screener.by_phase(), alerts=tuple(collected.alerts),
            banner=screener.banner, dry_run=screener.dry_run,
            disclosure=screener.disclosure, verification=verification,
        )

    for boundary in ls.boundary_stamps(day):
        if live:
            if not args.no_wait:
                ls.wait_for_boundary(clock, boundary)
        else:
            clock.set(boundary)
        after(screener.sweep(boundary))

    print("")
    print(dash.render_text(
        day=day, now=ls.boundary_stamps(day)[-1], grouped=screener.by_phase(),
        alerts=tuple(collected.alerts), banner=screener.banner, dry_run=screener.dry_run,
        disclosure=screener.disclosure, verification=verification,
    ))
    print(f"recording: {recording.root}")
    print(f"dashboard: {recording.root / 'dashboard.html'}")
    return 0


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


def _preflight_lines(screener: ls.LiveScreener, recording: LiveRecording, mode: str) -> list[str]:
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
    why_master = (
        "THIS DAY'S OWN dump (CONTEXT 4.7 / Q-29 -- the trader's chart as of this morning)"
        if live else "the recording's own pin, or the Q-20 config pin (CONTEXT 4.7)"
    )
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
        f"symbols              {len(screener.symbols)}",
        f"biases resolved      {len(screener.biases)}",
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
        "=" * 78,
    ]
    return lines


if __name__ == "__main__":  # pragma: no cover -- ASSERTED AT THE SOURCE (an AST test)
    raise SystemExit(main())
