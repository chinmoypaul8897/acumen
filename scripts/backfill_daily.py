"""Operator-run backfill of the daily bhavcopy store (chunk 2; CONTEXT 4.1).

Downloads one date at a time, paced at one request per two seconds, and records EVERY date's
outcome in the store's ledger -- ``file-present`` / ``confirmed-404`` / ``error``. It is
resumable: a settled date is never fetched twice, and an ``error`` date is retried on the
next run. Ctrl-C at any moment is safe (every write is atomic), and re-running over the same
window changes nothing.

Typical operator run (25 years; expect hours of wall clock, minutes of attention):

    python scripts/backfill_daily.py --from 2000-01-01 --to 2026-07-24 --allow-network

Useful flags:

    --store data/daily_store   where the Parquet store lives (default: config paths.data_dir)
    --raw-dir data/raw_bhav    also keep each date's extracted CSV, for audit / fixtures
    --retry-errors             re-attempt dates whose last outcome was an error (default on)
    --dry-run                  list what WOULD be fetched, touch nothing

Nothing happens without ``--allow-network``: reaching the internet is opt-in everywhere in
this repo, which is what keeps the test suite honest.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from acumen import bhavcopy, nse_http  # noqa: E402
from acumen.daily_store import DailyStore  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
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
    from acumen.config import load_config

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
        _print_summary(store, start, end)
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
        _print_summary(store, start, end)
        return 130

    print()
    _print_summary(store, start, end)
    return 0


def _keep_raw(raw_dir: Path, day: date, download: bhavcopy.Download) -> None:
    """Archive the date's CSV exactly as NSE published it (verbatim, no re-serialisation)."""
    if download.raw_csv is None:
        return
    raw_dir.mkdir(parents=True, exist_ok=True)
    name = f"{day.isoformat()}_{download.outcome.source_format}.csv"
    (raw_dir / name).write_text(download.raw_csv, encoding="utf-8", newline="")


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


def _print_summary(store: DailyStore, start: date, end: date) -> None:
    summary = store.coverage_summary(start, end)
    print("LEDGER SUMMARY " + "-" * 60)
    print(f"  range          : {start} .. {end}")
    print(f"  attempted      : {summary['attempted']}")
    print(f"  file-present   : {summary[bhavcopy.OUTCOME_PRESENT]}")
    print(f"  confirmed-404  : {summary[bhavcopy.OUTCOME_NOT_FOUND]}")
    print(f"  error          : {summary[bhavcopy.OUTCOME_ERROR]}")
    print(f"  never attempted: {summary['missing']}")
    if summary[bhavcopy.OUTCOME_ERROR] or summary["missing"]:
        print(
            "  NOTE: errors and un-attempted dates are NOT holidays (QUESTIONS.md Q-3 "
            "safeguard 1). Re-run this command to settle them before deriving a calendar."
        )


def _hms(seconds: float) -> str:
    seconds = int(max(0.0, seconds))
    return f"{seconds // 3600:d}h{(seconds % 3600) // 60:02d}m{seconds % 60:02d}s"


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
