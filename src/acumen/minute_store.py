"""The local 1-minute store: SmartAPI intraday candles in Parquet, plus a window ledger.

The intraday twin of :mod:`acumen.daily_store`, and it borrows that module's every hard-won
lesson (CONTEXT 6: "Parquet flat files. No database"):

    <root>/minute/<SYMBOL>/<SYMBOL>_<YYYY>-<MM>.parquet   one file per symbol per month
    <root>/ledger/<SYMBOL>.parquet                        one row per WINDOW ever attempted

**Prices are integer paise** (CONTEXT 7-E11). The store holds the SmartAPI feed AS FETCHED.
CONTEXT 7-E11 wants the intraday engines to run on RAW same-day prices, but the chunk-5A
gate-3 run RESOLVED OPEN-8 to **ADJUSTED**: SmartAPI's 1-minute historical feed is
corporate-action back-adjusted (a pre-CA day comes back at raw x k, e.g. 0.5 across a 1:1
bonus; QUESTIONS.md OPEN-8 / Q-10). So for a RECENT day (after the symbol's last CA) the stored
prices are raw, but for an OLD day before an intervening CA they are NOT the rupees that traded
that day. Recovering raw same-day prices (or amending E11) is an OPEN architect decision (Q-10),
and chunk 6 is BLOCKED on it; gate 1 already FLAGS the affected old days (they fail volume
reconciliation) so none is silently traded. This module does not un-adjust -- it stores what the
API returns, faithfully and labelled.

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
from typing import Iterable, Mapping, Sequence

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
            table = pq.read_table(path, schema=WINDOW_LEDGER_SCHEMA)
        except Exception as exc:  # a truncated ledger: report, do not surface a raw traceback
            raise MinuteStoreError(
                f"The window ledger at {path} exists but cannot be read "
                f"({type(exc).__name__}: {exc}). Delete it to force those windows to re-resolve "
                "(the candles themselves are safe in the month parquets)."
            ) from exc
        result: dict[date, WindowOutcome] = {}
        for record in table.to_pylist():
            stamp = record["attempted_at"]
            result[record["window_start"]] = WindowOutcome(
                symbol=record["symbol"],
                window_start=record["window_start"],
                window_end=record["window_end"],
                outcome=record["outcome"],
                candle_count=record["candle_count"],
                first_date=record["first_date"],
                last_date=record["last_date"],
                reason=record["reason"],
                attempted_at=stamp if isinstance(stamp, datetime) else None,
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
