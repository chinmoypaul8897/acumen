"""The screener's operator entry point (chunk 13).

    python -m acumen.run_screener --mode replay --day 2026-06-10 --symbols HDFCBANK
    python -m acumen.run_screener --mode live                       # refuses -- see Q-28

Two modes, one pipeline:

* ``replay`` -- a past day, served bar by bar from the minute lake as if the clock were running,
  on a VIRTUAL clock so it finishes in seconds. This is the mode the chunk's replay invariant
  runs in, and it is a real exercise of the live screener rather than of a stand-in.
* ``live`` -- today. **Blocked on QUESTIONS.md Q-28** and it says so, with the question's own
  text, rather than starting and producing a number nobody may rely on.

The preflight prints everything a later reader would need to reproduce the session: the pinned
instrument master and its digest, the calendar reading and which source governed it (the C5
duty), the boundaries, the gate battery's availability, and the recording it will write. It
prints no credential and reads none (CLAUDE.md rule 4 -- and there is no order endpoint anywhere
on this path, which :mod:`tests.test_live_safety` proves by AST).

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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    day = date.fromisoformat(args.day)
    config = load_config(Path(args.config), include_env=False)
    data_root = config.path("data_root")

    symbols = tuple(
        part.strip().upper() for part in args.symbols.split(",") if part.strip()
    )

    if args.refresh:
        calendar, universe, report = morning_refresh(
            today=day,
            store=DailyStore.at(data_root / "daily_store"),
            cache_dir=config.path("cache_root"),
            allow_network=args.allow_network,
            symbols=symbols or None,
        )
        print(report.render(), flush=True)
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
    clock = ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time()))
    screen = ls.ScreenAlertSink()
    sound = ls.SoundAlertSink()
    collected = ls.CollectingAlertSink()

    try:
        screener = ls.build_live_screener(
            day, symbols,
            source=StoredDayBarSource(MinuteStore.at(data_root / "minute_store")),
            recording=recording, clock=clock, mode=args.mode,
            sinks=(screen, sound, collected),
            dry_run=not args.live_alerts,
            allow_network=args.allow_network,
        )
    except ls.BlockedByOpenQuestion as exc:
        print("THE LIVE MODE IS BLOCKED, and this is not a bug:")
        print("")
        print(str(exc))
        return 1

    for line in _preflight_lines(screener, recording, args.mode):
        print(line, flush=True)
    if args.preflight_only:
        return 0
    print("", flush=True)

    def after(report: ls.SweepReport) -> None:
        clock.set(report.boundary)
        dash.write_dashboard(
            recording.root, day=day, now=report.boundary,
            grouped=screener.by_phase(), alerts=tuple(collected.alerts),
            banner=screener.banner, dry_run=screener.dry_run,
        )

    for boundary in ls.boundary_stamps(day):
        clock.set(boundary)
        after(screener.sweep(boundary))

    print("")
    print(dash.render_text(
        day=day, now=ls.boundary_stamps(day)[-1], grouped=screener.by_phase(),
        alerts=tuple(collected.alerts), banner=screener.banner, dry_run=screener.dry_run,
    ))
    print(f"recording: {recording.root}")
    print(f"dashboard: {recording.root / 'dashboard.html'}")
    return 0


def _preflight_lines(screener: ls.LiveScreener, recording: LiveRecording, mode: str) -> list[str]:
    manifest = recording.read_manifest()
    calendar = manifest.get("calendar", {})
    gated = len(screener.gates)
    lines = [
        "=" * 78,
        f"ACUMEN SCREENER PREFLIGHT   {screener.day.isoformat()}   mode={mode}",
        "=" * 78,
        f"spec                 {manifest.get('spec_version')}   code {manifest.get('code_sha')}",
        f"instrument master    {manifest.get('master_file')}",
        f"                     sha256 {manifest.get('master_sha256')}",
        f"row size             {manifest.get('row_size')}",
        f"risk / cost (paise)  {manifest.get('risk_per_trade_paise')} / "
        f"{manifest.get('cost_paise')}",
        f"symbols              {len(screener.symbols)}",
        f"biases resolved      {len(screener.biases)}",
        f"gate battery         {gated} symbol-day(s) measured from the STORED whole day "
        f"(the backtester's own verdict)",
        f"calendar             {calendar.get('governing_source')} governs; "
        f"trading day = {calendar.get('is_trading_day')}, "
        f"standard session = {calendar.get('is_standard_session')}",
        f"                     store-scan cross-check found "
        f"{len(calendar.get('non_standard_sessions_store_scan', []))} non-standard session(s)",
        f"boundaries           {len(manifest.get('boundaries', []))} "
        f"({ls.POC_BOUNDARY} POC pass, last {ls.LAST_BOUNDARY})",
        f"alerts               {'DRY RUN (log only)' if screener.dry_run else 'LIVE'}",
        f"recording            {recording.root}",
        "=" * 78,
    ]
    return lines


if __name__ == "__main__":  # pragma: no cover -- ASSERTED AT THE SOURCE (an AST test)
    raise SystemExit(main())
