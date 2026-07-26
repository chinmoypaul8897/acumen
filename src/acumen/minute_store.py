"""The local 1-minute store: SmartAPI intraday candles in Parquet, plus a window ledger.

The intraday twin of :mod:`acumen.daily_store`, and it borrows that module's every hard-won
lesson (CONTEXT 6: "Parquet flat files. No database"):

    <root>/minute/<SYMBOL>/<SYMBOL>_<YYYY>-<MM>.parquet   one file per symbol per month
    <root>/ledger/<SYMBOL>.parquet                        one row per WINDOW ever attempted

**Prices are integer paise** (CONTEXT 7-E11). The store holds **RAW same-day prices** -- the
rupees that actually traded that day, on that day's tick grid, exactly as CONTEXT 7-E11
requires. The SmartAPI 1-minute feed is corporate-action back-adjusted (OPEN-8 resolved
ADJUSTED: a pre-CA day comes back at raw x k, e.g. 0.5 across a 1:1 bonus), so the ingest path
UN-ADJUSTS every window back to raw before it is stored here, using the chunk-3 factor table
(QUESTIONS.md Q-10 ruling; :mod:`acumen.minute_unadjust`). A RECENT day (after the symbol's
last CA) has an empty factor window, so its un-adjustment is the exact identity and the fetched
prices are stored unchanged; an OLD day before an intervening CA is divided back by ``k_cum``.
The window ledger records the FETCH DATE per window, because ``k_cum`` is fetch-dated (a future
top-up un-adjusts with a refreshed CA table). A day whose CA in ``(D, F]`` has no factor (a
demerger, a Q-6-pending rights) is un-provable: it is stored but gate 1 fails it, so it is
excluded and counted (CONTEXT 7-E3) rather than silently traded on a half-scaled price.

**Stamps are naive IST, open-stamped** (CONTEXT 7-E8/E12): the +05:30 the API sends is
normalized away on ingest (in :mod:`acumen.smartapi_client`), so nothing stored here carries
a timezone.

**The window ledger is the resume list** (the Q-3 discipline, applied to 30-day minute
windows): every window attempted is recorded ``present`` / ``empty`` / ``error``; only the
first two settle it, so an interrupted or unlucky backfill resumes exactly where it stopped
and a transient failure is retried, never frozen into a hole. ``empty`` is terminal on
purpose -- a window entirely before a stock's listing has no candles and never will
(RESULTS.md B: 1-min depth begins 2016-10, later for newer listings).

Every write is atomic (:mod:`acumen.atomic_io`, fsync-before-replace): the backfill runs for
minutes per symbol and is meant to be Ctrl-C-able, so an interrupt leaves the store either as
it was or fully updated -- the same guarantee the 2026-07-25 power-loss incident hardened for
the daily side.

Per-date replacement (not per-window) keeps ingestion idempotent AND safe across the 30-day
window seams: two adjacent windows can each touch one calendar month, so a write replaces only
the DATES it carries and never deletes a neighbour window's rows -- exactly
:meth:`acumen.daily_store.DailyStore.write_rows`' rule.

This module is STORAGE -- file I/O, no network, no strategy logic (CONTEXT 6).

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .atomic_io import atomic_write_with

MINUTE_DIRNAME: str = "minute"
LEDGER_DIRNAME: str = "ledger"

#: Window outcomes, spelled once and persisted (part of the store's contract).
WINDOW_PRESENT: str = "present"   # candles were stored for this window
WINDOW_EMPTY: str = "empty"       # the window genuinely holds no candles (before listing)
WINDOW_ERROR: str = "error"       # the fetch failed; retry on the next run

TERMINAL_WINDOW_OUTCOMES: frozenset[str] = frozenset({WINDOW_PRESENT, WINDOW_EMPTY})
ALL_WINDOW_OUTCOMES: frozenset[str] = frozenset({WINDOW_PRESENT, WINDOW_EMPTY, WINDOW_ERROR})

#: Explicit schema (never inferred -- an inferred schema drifts when a month has no nulls).
MINUTE_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("symbol", pa.string(), nullable=False),
        pa.field("trade_date", pa.date32(), nullable=False),
        pa.field("stamp", pa.timestamp("us"), nullable=False),  # naive IST, open-stamped
        pa.field("open_paise", pa.int64(), nullable=False),
        pa.field("high_paise", pa.int64(), nullable=False),
        pa.field("low_paise", pa.int64(), nullable=False),
        pa.field("close_paise", pa.int64(), nullable=False),
        pa.field("volume", pa.int64(), nullable=False),
    ]
)

WINDOW_LEDGER_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("symbol", pa.string(), nullable=False),
        pa.field("window_start", pa.date32(), nullable=False),
        pa.field("window_end", pa.date32(), nullable=False),
        pa.field("outcome", pa.string(), nullable=False),
        pa.field("candle_count", pa.int64()),
        pa.field("first_date", pa.date32()),
        pa.field("last_date", pa.date32()),
        pa.field("reason", pa.string()),
        pa.field("attempted_at", pa.timestamp("s")),
        # QUESTIONS.md Q-10: k_cum is fetch-dated, so the FETCH DATE of each window is recorded
        # explicitly (not merely implied by attempted_at) -- a future top-up un-adjusts the
        # extended tail with a refreshed CA table keyed on this date. Nullable so a ledger
        # written before this column (or by --rebuild-ledger, which cannot know it) still reads.
        pa.field("fetch_date", pa.date32()),
    ]
)


class MinuteStoreError(RuntimeError):
    """The minute store cannot answer, or cannot safely be written."""


@dataclass(frozen=True)
class StoredBar:
    """One stored 1-minute candle. Integer paise, naive-IST open-stamp (CONTEXT 7-E8/E11/E12).

    Structurally compatible with the pure aggregator (:mod:`acumen.aggregate`) and the quality
    gates (:mod:`acumen.quality_gates`), so a stored bar flows into both with no adapter.
    """

    symbol: str
    stamp: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int

    @property
    def trade_date(self) -> date:
        return self.stamp.date()


@dataclass(frozen=True)
class WindowOutcome:
    """What happened when we asked SmartAPI for one 30-day window of a symbol (ledger row)."""

    symbol: str
    window_start: date
    window_end: date
    outcome: str
    candle_count: int | None = None
    first_date: date | None = None
    last_date: date | None = None
    reason: str | None = None
    attempted_at: datetime | None = None
    fetch_date: date | None = None  # F: the date this window was fetched (k_cum is fetch-dated)

    def __post_init__(self) -> None:
        if self.outcome not in ALL_WINDOW_OUTCOMES:
            raise MinuteStoreError(
                f"Unknown window outcome {self.outcome!r}; known: "
                f"{', '.join(sorted(ALL_WINDOW_OUTCOMES))}."
            )

    @property
    def is_terminal(self) -> bool:
        return self.outcome in TERMINAL_WINDOW_OUTCOMES


@dataclass(frozen=True)
class MinuteStore:
    """A Parquet 1-minute store rooted at ``root``. Cheap to construct; opens files lazily."""

    root: Path

    @classmethod
    def at(cls, root: Path | str) -> MinuteStore:
        return cls(root=Path(root))

    # --- paths ---------------------------------------------------------------------

    @property
    def minute_dir(self) -> Path:
        return self.root / MINUTE_DIRNAME

    @property
    def ledger_dir(self) -> Path:
        return self.root / LEDGER_DIRNAME

    def month_path(self, symbol: str, day: date) -> Path:
        sym = symbol.strip().upper()
        return self.minute_dir / sym / f"{sym}_{day.year:04d}-{day.month:02d}.parquet"

    def ledger_path(self, symbol: str) -> Path:
        return self.ledger_dir / f"{symbol.strip().upper()}.parquet"

    # --- writing -------------------------------------------------------------------

    def write_bars(self, symbol: str, bars: Sequence["_BarLike"]) -> list[Path]:
        """Store ``bars`` for ``symbol``, replacing by DATE within each month. Atomic.

        Bars may span more than one month (a 30-day window does); each affected month file has
        exactly the incoming DATES replaced and every other date kept, so adjacent windows that
        share a month do not clobber each other and a re-run is idempotent. Returns the month
        files written.
        """
        sym = symbol.strip().upper()
        by_month: dict[tuple[int, int], list[_BarLike]] = {}
        for bar in bars:
            _require_naive(bar.stamp)
            key = (bar.stamp.year, bar.stamp.month)
            by_month.setdefault(key, []).append(bar)

        written: list[Path] = []
        for (year, month), month_bars in sorted(by_month.items()):
            path = self.month_path(sym, date(year, month, 1))
            incoming = _bars_to_table(sym, month_bars)
            incoming_dates = pa.array(sorted({b.stamp.date() for b in month_bars}), type=pa.date32())
            if path.is_file():
                existing = pq.read_table(path, schema=MINUTE_SCHEMA)
                keep = existing.filter(pc.invert(pc.is_in(existing.column("trade_date"), value_set=incoming_dates)))
                table = pa.concat_tables([keep, incoming])
            else:
                table = incoming
            table = table.sort_by([("stamp", "ascending")])
            atomic_write_with(path, lambda temp, t=table: pq.write_table(t, temp, compression="zstd"))
            written.append(path)
        return written

    def record_window(self, outcome: WindowOutcome) -> Path:
        """Insert or replace one window's ledger row for its symbol. Atomic."""
        ledger = self.window_outcomes(outcome.symbol)
        ledger[outcome.window_start] = outcome
        return self._write_ledger(outcome.symbol, ledger)

    def _write_ledger(self, symbol: str, ledger: Mapping[date, WindowOutcome]) -> Path:
        rows = [ledger[start] for start in sorted(ledger)]
        table = _windows_to_table(rows)
        path = self.ledger_path(symbol)
        atomic_write_with(path, lambda temp: pq.write_table(table, temp, compression="zstd"))
        return path

    # --- reading -------------------------------------------------------------------

    def minutes(self, symbol: str, day: date) -> tuple[StoredBar, ...]:
        """One day's stored 1-minute candles for ``symbol``, oldest first (empty if none)."""
        path = self.month_path(symbol, day)
        if not path.is_file():
            return ()
        table = pq.read_table(path, schema=MINUTE_SCHEMA)
        table = table.filter(pc.equal(table.column("trade_date"), day)).sort_by([("stamp", "ascending")])
        return _table_to_bars(table)

    def minutes_range(self, symbol: str, from_date: date, to_date: date) -> tuple[StoredBar, ...]:
        """Stored 1-minute candles for ``symbol`` over ``[from_date, to_date]``, oldest first."""
        if to_date < from_date:
            raise MinuteStoreError(f"Empty range: {to_date.isoformat()} before {from_date.isoformat()}.")
        bars: list[StoredBar] = []
        for path in self._month_paths(symbol, from_date, to_date):
            table = pq.read_table(path, schema=MINUTE_SCHEMA)
            mask = pc.and_(
                pc.greater_equal(table.column("trade_date"), from_date),
                pc.less_equal(table.column("trade_date"), to_date),
            )
            bars.extend(_table_to_bars(table.filter(mask)))
        bars.sort(key=lambda b: b.stamp)
        return tuple(bars)

    def iter_days(
        self, symbol: str, from_date: date | None = None, to_date: date | None = None
    ) -> Iterator[tuple[date, tuple[StoredBar, ...]]]:
        """Yield ``(day, bars)`` for every stored day in range, oldest first, a MONTH at a time.

        The scan the universe run (chunk 5B) gates on. :meth:`minutes` opens (and filters) the
        month file once PER DAY, which is ~2,400 opens per symbol over the full history, and
        :meth:`minutes_range` materialises every bar of every day at once (~900k objects for a
        decade). This walks one month file at a time and groups its rows by date, so the peak
        cost is one month (~7,500 bars) no matter how long the history is, and a caller that
        aggregates per day never holds two months at once.
        """
        sym = symbol.strip().upper()
        directory = self.minute_dir / sym
        if not directory.is_dir():
            return
        for path in sorted(directory.glob("*.parquet")):
            table = pq.read_table(path, schema=MINUTE_SCHEMA)
            if from_date is not None:
                table = table.filter(pc.greater_equal(table.column("trade_date"), from_date))
            if to_date is not None:
                table = table.filter(pc.less_equal(table.column("trade_date"), to_date))
            if not table.num_rows:
                continue
            by_day: dict[date, list[StoredBar]] = {}
            for bar in _table_to_bars(table.sort_by([("stamp", "ascending")])):
                by_day.setdefault(bar.trade_date, []).append(bar)
            for day in sorted(by_day):
                yield day, tuple(by_day[day])

    def has_day(self, symbol: str, day: date) -> bool:
        return bool(self.minutes(symbol, day))

    def stored_days(self, symbol: str) -> tuple[date, ...]:
        """Every date this symbol has at least one stored candle for, oldest first."""
        days: set[date] = set()
        for path in sorted(self.minute_dir.joinpath(symbol.strip().upper()).glob("*.parquet")) \
                if self.minute_dir.joinpath(symbol.strip().upper()).is_dir() else []:
            table = pq.read_table(path, columns=["trade_date"])
            days.update(table.column("trade_date").to_pylist())
        return tuple(sorted(days))

    def first_stored_date(self, symbol: str) -> date | None:
        """The earliest date with stored candles -- the symbol's discovered 1-min depth."""
        days = self.stored_days(symbol)
        return days[0] if days else None

    def _month_paths(self, symbol: str, from_date: date, to_date: date) -> list[Path]:
        sym = symbol.strip().upper()
        paths: list[Path] = []
        year, month = from_date.year, from_date.month
        while (year, month) <= (to_date.year, to_date.month):
            path = self.month_path(sym, date(year, month, 1))
            if path.is_file():
                paths.append(path)
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return paths

    # --- the window ledger ---------------------------------------------------------

    def window_outcomes(self, symbol: str) -> dict[date, WindowOutcome]:
        """The whole window ledger for ``symbol`` as ``{window_start: outcome}``."""
        path = self.ledger_path(symbol)
        if not path.is_file():
            return {}
        try:
            # Read the file's own schema (not forced to WINDOW_LEDGER_SCHEMA): a ledger written
            # before the fetch_date column simply lacks that key below, read as None -- the
            # write path always emits the full schema, so no NEW ledger drifts.
            table = pq.read_table(path)
        except Exception as exc:  # a truncated ledger: report, do not surface a raw traceback
            raise MinuteStoreError(
                f"The window ledger at {path} exists but cannot be read "
                f"({type(exc).__name__}: {exc}). Delete it to force those windows to re-resolve "
                "(the candles themselves are safe in the month parquets)."
            ) from exc
        result: dict[date, WindowOutcome] = {}
        for record in table.to_pylist():
            stamp = record.get("attempted_at")
            fetch = record.get("fetch_date")
            result[record["window_start"]] = WindowOutcome(
                symbol=record["symbol"],
                window_start=record["window_start"],
                window_end=record["window_end"],
                outcome=record["outcome"],
                candle_count=record.get("candle_count"),
                first_date=record.get("first_date"),
                last_date=record.get("last_date"),
                reason=record.get("reason"),
                attempted_at=stamp if isinstance(stamp, datetime) else None,
                fetch_date=fetch if isinstance(fetch, date) else None,
            )
        return result

    def pending_windows(
        self, symbol: str, windows: Iterable[tuple[date, date]], *, retry_errors: bool = True
    ) -> list[tuple[date, date]]:
        """Which of ``windows`` still need attempting -- the resume list.

        A window is SETTLED (skipped) only when the ledger holds a terminal (``present`` /
        ``empty``) row for its ``window_start`` that already covered AT LEAST as far as the
        window now asks -- ``stored.window_end >= end``. It is PENDING when:

        * never attempted, or
        * its last outcome was ``error`` (retried unless ``retry_errors`` is False), or
        * a terminal row exists but stored a SHORTER end than now requested.

        That last case is the ``--to today`` incremental hazard: the final window's ``end``
        tracks the requested end, so it grows day to day while its ``window_start`` stays fixed.
        Keying settlement on the start alone would skip the same last window forever and never
        fetch the newly-requested tail days (a silent hole). Comparing against the stored end
        closes it: the window is refetched, and :meth:`write_bars` replaces the already-stored
        dates and appends the new ones idempotently.
        """
        ledger = self.window_outcomes(symbol)
        pending: list[tuple[date, date]] = []
        for start, end in windows:
            outcome = ledger.get(start)
            if outcome is None:
                pending.append((start, end))
            elif not outcome.is_terminal:
                if retry_errors:
                    pending.append((start, end))
            elif outcome.window_end < end:
                pending.append((start, end))  # a later run extended --to past the stored end
        return pending

    def ledger_summary(self, symbol: str) -> dict[str, int]:
        """Counts by window outcome for ``symbol`` (the backfill run summary)."""
        counts = {name: 0 for name in (WINDOW_PRESENT, WINDOW_EMPTY, WINDOW_ERROR)}
        for outcome in self.window_outcomes(symbol).values():
            counts[outcome.outcome] += 1
        counts["windows"] = sum(counts.values())
        return counts


# --- conversions ----------------------------------------------------------------------


def _bars_to_table(symbol: str, bars: Sequence["_BarLike"]) -> pa.Table:
    columns: dict[str, list[object]] = {name: [] for name in MINUTE_SCHEMA.names}
    for bar in bars:
        columns["symbol"].append(symbol)
        columns["trade_date"].append(bar.stamp.date())
        columns["stamp"].append(bar.stamp)
        columns["open_paise"].append(int(bar.open_paise))
        columns["high_paise"].append(int(bar.high_paise))
        columns["low_paise"].append(int(bar.low_paise))
        columns["close_paise"].append(int(bar.close_paise))
        columns["volume"].append(int(bar.volume))
    return pa.table(columns, schema=MINUTE_SCHEMA)


def _table_to_bars(table: pa.Table) -> tuple[StoredBar, ...]:
    rows = table.to_pylist()
    return tuple(
        StoredBar(
            symbol=row["symbol"],
            stamp=row["stamp"],
            open_paise=row["open_paise"],
            high_paise=row["high_paise"],
            low_paise=row["low_paise"],
            close_paise=row["close_paise"],
            volume=row["volume"],
        )
        for row in rows
    )


def _windows_to_table(outcomes: Sequence[WindowOutcome]) -> pa.Table:
    columns: dict[str, list[object]] = {name: [] for name in WINDOW_LEDGER_SCHEMA.names}
    for outcome in outcomes:
        columns["symbol"].append(outcome.symbol)
        columns["window_start"].append(outcome.window_start)
        columns["window_end"].append(outcome.window_end)
        columns["outcome"].append(outcome.outcome)
        columns["candle_count"].append(outcome.candle_count)
        columns["first_date"].append(outcome.first_date)
        columns["last_date"].append(outcome.last_date)
        columns["reason"].append(outcome.reason)
        columns["attempted_at"].append(outcome.attempted_at)
        columns["fetch_date"].append(outcome.fetch_date)
    return pa.table(columns, schema=WINDOW_LEDGER_SCHEMA)


def _require_naive(stamp: datetime) -> None:
    if not isinstance(stamp, datetime) or stamp.tzinfo is not None:
        raise MinuteStoreError(
            f"1-minute stamps must be naive IST (CONTEXT 7-E8); got {stamp!r}. Normalize the "
            "+05:30 on ingest (acumen.smartapi_client.parse_candles does this)."
        )


class _BarLike:  # pragma: no cover - typing aid only (structural)
    stamp: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int
