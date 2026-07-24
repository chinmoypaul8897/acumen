"""Operator-run backfill of the daily bhavcopy store (chunk 2; CONTEXT 4.1).

Downloads one date at a time, paced at one request per two seconds, and records EVERY date's
outcome in the store's ledger -- ``file-present`` / ``confirmed-404`` / ``error``. It is
resumable: a settled date is never fetched twice, and an ``error`` date is retried on the
next run. Ctrl-C at any moment is safe (every write is atomic), and re-running over the same
window changes nothing.

Typical operator run (25 years; expect hours of wall clock, minutes of attention):

    python scripts/backfill_daily.py --from 2000-01-01 --to 2026-07-24 --allow-network

Equivalent entry points, in order of preference:

    acumen-backfill --from 2000-01-01 --to 2026-07-24 --allow-network   (after an install)
    python -m acumen.backfill_daily --from ... --allow-network
    python scripts/backfill_daily.py --from ... --allow-network         (thin launcher)

Useful flags:

    --store data/daily_store   where the Parquet store lives (default: config paths.data_dir)
    --raw-dir data/raw_bhav    also keep each date's extracted CSV, for audit / fixtures
    --retry-errors             re-attempt dates whose last outcome was an error (default on)
    --dry-run                  list what WOULD be fetched, touch nothing

Nothing happens without ``--allow-network``: reaching the internet is opt-in everywhere in
this repo, which is what keeps the test suite honest.

This module lives inside the package rather than under ``scripts/`` so that no entry point
has to mutate ``sys.path`` at import time (REVIEW_2 Finding 12). It still holds no strategy
logic: it is the operator's front end to :mod:`acumen.bhavcopy` and :mod:`acumen.daily_store`.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import time
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

from . import bhavcopy, nse_http, universe
from .atomic_io import atomic_write_text
from .daily_store import SERIES_UNKNOWN, DailyStore


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="acumen-backfill",
        description="Backfill the daily bhavcopy store (CONTEXT 4.1).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--from", dest="start", required=True, help="first date, YYYY-MM-DD")
    parser.add_argument("--to", dest="end", required=True, help="last date, YYYY-MM-DD")
    parser.add_argument("--store", default=None, help="store root (default: <data_dir>/daily_store)")
    parser.add_argument("--raw-dir", default=None, help="also keep each date's extracted CSV")
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="REQUIRED to fetch anything; without it this is a dry run",
    )
    parser.add_argument("--dry-run", action="store_true", help="list pending dates and stop")
    parser.add_argument(
        "--no-retry-errors",
        action="store_true",
        help="skip dates whose last outcome was an error instead of retrying them",
    )
    parser.add_argument(
        "--progress-every", type=int, default=10, help="print a progress line every N dates"
    )
    parser.add_argument(
        "--min-interval",
        type=float,
        default=bhavcopy.MIN_SECONDS_BETWEEN_REQUESTS,
        help="minimum seconds between requests (politeness; do not lower without reason)",
    )
    return parser.parse_args(argv)


def default_store_root() -> Path:
    from .config import load_config

    return load_config(include_env=False).path("data_dir") / "daily_store"


def resolve_dates(store: DailyStore, start: date, end: date, *, retry_errors: bool) -> list[date]:
    """The dates this run should attempt, oldest first."""
    if retry_errors:
        return list(store.pending_dates(start, end))
    known = store.outcomes()
    return [day for day in bhavcopy.date_range(start, end) if day not in known]


def run(args: argparse.Namespace) -> int:
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    root = Path(args.store) if args.store else default_store_root()
    store = DailyStore.at(root)
    raw_dir = Path(args.raw_dir) if args.raw_dir else None

    pending = resolve_dates(store, start, end, retry_errors=not args.no_retry_errors)
    total_days = (end - start).days + 1
    print(f"store        : {root}")
    print(f"range        : {start} .. {end}  ({total_days} calendar dates)")
    print(f"already done : {total_days - len(pending)}")
    print(f"to attempt   : {len(pending)}")
    if not args.allow_network or args.dry_run:
        why = "--dry-run" if args.dry_run else "no --allow-network"
        print(f"\nSTOPPING ({why}). Nothing was fetched and nothing was written.")
        if pending:
            preview = ", ".join(day.isoformat() for day in pending[:10])
            print(f"first pending: {preview}{' ...' if len(pending) > 10 else ''}")
        return 0
    if not pending:
        print("\nNothing to do -- every date in the range is already settled.")
        _print_summary(store, start, end, symbols=cached_universe_symbols())
        return 0

    session = nse_http.new_session()
    started = time.monotonic()
    counts = {bhavcopy.OUTCOME_PRESENT: 0, bhavcopy.OUTCOME_NOT_FOUND: 0, bhavcopy.OUTCOME_ERROR: 0}
    print(f"\npacing       : 1 request / {args.min_interval:g}s\nstarted      : {datetime.now():%Y-%m-%d %H:%M:%S}\n")

    try:
        for index, day in enumerate(pending, start=1):
            download = bhavcopy.download_bhavcopy(
                day, session=session, min_interval=args.min_interval
            )
            store.ingest(download)
            counts[download.outcome.outcome] += 1
            if raw_dir is not None and download.outcome.outcome == bhavcopy.OUTCOME_PRESENT:
                _keep_raw(raw_dir, day, download)
            if download.outcome.outcome == bhavcopy.OUTCOME_ERROR:
                print(f"  ! {day}  error: {download.outcome.reason}")
            if index % max(1, args.progress_every) == 0 or index == len(pending):
                _print_progress(index, len(pending), day, counts, started)
    except KeyboardInterrupt:
        print("\nInterrupted. The store is consistent -- re-run the same command to resume.")
        _print_summary(store, start, end, symbols=cached_universe_symbols())
        return 130

    print()
    _print_summary(store, start, end, symbols=cached_universe_symbols())
    return 0


def _keep_raw(raw_dir: Path, day: date, download: bhavcopy.Download) -> None:
    """Archive the date's CSV exactly as NSE published it (verbatim, no re-serialisation).

    Written through :mod:`acumen.atomic_io` (REVIEW_2 Finding 3): a Ctrl-C mid-write must not
    leave a truncated CSV in the archive the DERIVED fixtures are cut from. Note the
    remaining limitation, unchanged: the archive is only written for dates THIS run fetched,
    so a date settled by an earlier run is not backfilled by adding ``--raw-dir`` later.
    """
    if download.raw_csv is None:
        return
    name = f"{day.isoformat()}_{download.outcome.source_format}.csv"
    atomic_write_text(raw_dir / name, download.raw_csv)


def _print_progress(
    index: int, total: int, day: date, counts: dict[str, int], started: float
) -> None:
    elapsed = time.monotonic() - started
    rate = elapsed / index if index else 0.0
    remaining = (total - index) * rate
    print(
        f"  {index:>6}/{total}  {day}  "
        f"present={counts[bhavcopy.OUTCOME_PRESENT]} "
        f"404={counts[bhavcopy.OUTCOME_NOT_FOUND]} "
        f"error={counts[bhavcopy.OUTCOME_ERROR]}  "
        f"elapsed={_hms(elapsed)} eta={_hms(remaining)}"
    )


def _print_summary(
    store: DailyStore, start: date, end: date, *, symbols: Sequence[str] | None = None
) -> None:
    summary = store.coverage_summary(start, end)
    print("LEDGER SUMMARY " + "-" * 60)
    print(f"  range          : {start} .. {end}")
    print(f"  attempted      : {summary['attempted']}")
    print(f"  file-present   : {summary[bhavcopy.OUTCOME_PRESENT]}")
    print(f"  confirmed-404  : {summary[bhavcopy.OUTCOME_NOT_FOUND]}")
    print(f"  error          : {summary[bhavcopy.OUTCOME_ERROR]}")
    print(f"  never attempted: {summary['missing']}")
    print(f"  weekend session: {summary['weekend_session']}  (EXCLUDED, QUESTIONS.md Q-5)")
    if summary[bhavcopy.OUTCOME_ERROR] or summary["missing"]:
        print(
            "  NOTE: errors and un-attempted dates are NOT holidays (QUESTIONS.md Q-3 "
            "safeguard 1). Re-run this command to settle them before deriving a calendar."
        )
    _print_series_report(store, start, end, symbols)


def cached_universe_symbols() -> tuple[str, ...] | None:
    """The cached F&O list, or ``None`` when there is none. Never fetches, never raises."""
    try:
        _fetched_on, symbols = universe.load_cached_universe()
    except Exception:  # UniverseError, NseFetchError, ConfigError: all mean "no list here"
        return None
    return symbols


def _print_series_report(
    store: DailyStore, start: date, end: date, symbols: Sequence[str] | None
) -> None:
    """Surface UNKNOWN series carried by F&O-universe symbols (QUESTIONS.md Q-4 ruling).

    The ruling's last clause: "Unknown series encountered on F&O-universe symbols must be
    surfaced in the backfill/coverage report." An unknown series is never chosen by
    :meth:`acumen.daily_store.DailyStore.daily` -- it is reported so the architect can rule
    on it. The symbol list is passed IN rather than loaded here, so that a printer does no
    hidden I/O and the section is deterministic in tests.
    """
    if symbols is None:
        print("  unknown series : not checked (no cached F&O universe; QUESTIONS.md Q-4)")
        return
    try:
        unknown = store.unknown_series(symbols, start, end)
    except Exception as exc:  # a store that cannot be read must not kill the run summary
        print(f"  unknown series : not checked ({type(exc).__name__}: {exc})")
        return

    if unknown.empty:
        print(f"  unknown series : 0  (over {len(symbols)} F&O symbols, QUESTIONS.md Q-4)")
        return
    print(f"  unknown series : {len(unknown)}  (QUESTIONS.md Q-4: reported, never traded)")
    for row in unknown.itertuples():
        print(
            f"      {row.symbol:<14} {row.series:<4} {row.rows:>6} row(s)  "
            f"{row.first_date} .. {row.last_date}  [{SERIES_UNKNOWN}]"
        )


def _hms(seconds: float) -> str:
    seconds = int(max(0.0, seconds))
    return f"{seconds // 3600:d}h{(seconds % 3600) // 60:02d}m{seconds % 60:02d}s"


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
