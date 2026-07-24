"""The local daily store: 25 years of NSE bhavcopy in Parquet, plus its outcome ledger.

Shape (CONTEXT 6: "Parquet flat files. No database"):

    <root>/daily/<YYYY>/bhavcopy_<YYYY>-<MM>.parquet   one file per calendar month
    <root>/ledger.parquet                              one row per DATE ever attempted

**Prices are integer paise** (CONTEXT 7-E11) and **RAW** -- exactly what NSE published, with
no corporate-action adjustment (CONTEXT 4.1: "Bhavcopy prices are UNADJUSTED"; chunk 3 owns
adjustment, applied pairwise at read time per CONTEXT 3.2).

**Store everything, filter on query** (chunk-2 card). Every row of every published bhavcopy
goes in -- all symbols, all series. Filtering to today's F&O universe on the way IN would
make the stored history depend on the day the store happened to be built, and would silently
throw away the rows chunk 3's corporate-action cross-checks may need. The universe filter is
applied on the way OUT, by the caller passing the symbols it wants.

**The outcome ledger is the calendar** (QUESTIONS.md Q-3, architect's ruling). Every date
attempted is recorded as ``file-present`` / ``confirmed-404`` / ``error``; a date is only
settled by the first two, so an interrupted or unlucky run resumes exactly where it stopped
and never leaves a download error looking like a holiday.

Every write is atomic (:mod:`acumen.atomic_io`): the backfill run takes hours and is meant to
be interruptible, so a Ctrl-C must leave the store either as it was or fully updated.

This module is the STORAGE layer -- it does file I/O and no network, and holds no strategy
logic (CONTEXT 6).

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .atomic_io import atomic_write_with
from .bhavcopy import (
    ALL_OUTCOMES,
    OUTCOME_ERROR,
    OUTCOME_NOT_FOUND,
    OUTCOME_PRESENT,
    DailyRow,
    DateOutcome,
    Download,
    date_range,
)

DAILY_DIRNAME: str = "daily"
LEDGER_FILENAME: str = "ledger.parquet"

#: One Parquet schema, written explicitly rather than inferred -- an inferred schema changes
#: shape when a month happens to have no nulls in a column, and a store whose dtypes drift
#: between months is a store whose reads drift too.
DAILY_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("trade_date", pa.date32(), nullable=False),
        pa.field("symbol", pa.string(), nullable=False),
        pa.field("series", pa.string(), nullable=False),
        pa.field("open_paise", pa.int64(), nullable=False),
        pa.field("high_paise", pa.int64(), nullable=False),
        pa.field("low_paise", pa.int64(), nullable=False),
        pa.field("close_paise", pa.int64(), nullable=False),
        pa.field("volume", pa.int64(), nullable=False),
        pa.field("last_paise", pa.int64()),
        pa.field("prev_close_paise", pa.int64()),
        pa.field("turnover_paise", pa.int64()),
        pa.field("trades", pa.int64()),
        pa.field("isin", pa.string()),
        pa.field("instrument_type", pa.string()),
        pa.field("source_format", pa.string(), nullable=False),
    ]
)

LEDGER_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("trade_date", pa.date32(), nullable=False),
        pa.field("outcome", pa.string(), nullable=False),
        pa.field("source_format", pa.string()),
        pa.field("url", pa.string()),
        pa.field("http_status", pa.int32()),
        pa.field("reason", pa.string()),
        pa.field("row_count", pa.int64()),
        pa.field("attempted_at", pa.timestamp("s")),
    ]
)

_PRICE_COLUMNS: tuple[str, ...] = (
    "open_paise",
    "high_paise",
    "low_paise",
    "close_paise",
    "last_paise",
    "prev_close_paise",
)


class DailyStoreError(RuntimeError):
    """The daily store cannot answer, or cannot safely be written."""


@dataclass(frozen=True)
class DailyStore:
    """A Parquet daily store rooted at ``root``. Cheap to construct; opens files lazily."""

    root: Path

    @classmethod
    def at(cls, root: Path | str) -> DailyStore:
        """Open (or address) the store under ``root``. Nothing is created until a write."""
        return cls(root=Path(root))

    # --- paths ---------------------------------------------------------------------

    @property
    def daily_dir(self) -> Path:
        return self.root / DAILY_DIRNAME

    @property
    def ledger_path(self) -> Path:
        return self.root / LEDGER_FILENAME

    def month_path(self, day: date) -> Path:
        """The Parquet file holding ``day``'s month.

        Monthly rather than daily files on purpose: ~21 dates x ~3,400 symbols is a healthy
        Parquet file, while one file per date would leave chunk 3 and chunk 4 opening 6,000+
        files to read a single symbol's history.
        """
        return self.daily_dir / f"{day.year:04d}" / f"bhavcopy_{day.year:04d}-{day.month:02d}.parquet"

    # --- writing -------------------------------------------------------------------

    def ingest(self, download: Download) -> DateOutcome:
        """Record one date's :class:`~acumen.bhavcopy.Download` -- prices AND outcome.

        Idempotent: re-ingesting a date REPLACES that date's rows rather than appending, so
        running the backfill twice over the same window changes nothing (the chunk-2 card's
        "re-run is idempotent (no dupes)").

        Returns the outcome that was recorded.
        """
        outcome = download.outcome
        if outcome.outcome == OUTCOME_PRESENT:
            if not download.rows:
                raise DailyStoreError(
                    f"{outcome.trade_date.isoformat()} is marked {OUTCOME_PRESENT} but carries "
                    "no rows; refusing to record a present-but-empty day."
                )
            self.write_rows(outcome.trade_date, download.rows)
        elif download.rows:
            raise DailyStoreError(
                f"{outcome.trade_date.isoformat()} is marked {outcome.outcome} but carries "
                f"{len(download.rows)} rows; only {OUTCOME_PRESENT} may carry prices."
            )
        self.record_outcome(outcome)
        return outcome

    def write_rows(self, day: date, rows: Sequence[DailyRow]) -> Path:
        """Replace ``day``'s rows in its month file. Atomic; returns the file written."""
        if not rows:
            raise DailyStoreError(f"No rows to write for {day.isoformat()}.")
        wrong = {row.trade_date for row in rows} - {day}
        if wrong:
            raise DailyStoreError(
                f"write_rows({day.isoformat()}) was given rows dated "
                f"{sorted(d.isoformat() for d in wrong)!r}."
            )

        path = self.month_path(day)
        incoming = _rows_to_table(rows)
        if path.is_file():
            existing = pq.read_table(path, schema=DAILY_SCHEMA)
            keep = existing.filter(pc.not_equal(existing.column("trade_date"), day))
            table = pa.concat_tables([keep, incoming])
        else:
            table = incoming

        table = table.sort_by([("symbol", "ascending"), ("trade_date", "ascending")])
        atomic_write_with(path, lambda temp: pq.write_table(table, temp, compression="zstd"))
        return path

    def record_outcome(self, outcome: DateOutcome) -> Path:
        """Insert or replace one date's ledger row. Atomic; returns the ledger path."""
        ledger = dict(self.outcomes())
        ledger[outcome.trade_date] = outcome
        return self._write_ledger(ledger)

    def record_outcomes(self, outcomes: Iterable[DateOutcome]) -> Path:
        """Insert or replace several ledger rows in ONE atomic write."""
        ledger = dict(self.outcomes())
        for outcome in outcomes:
            ledger[outcome.trade_date] = outcome
        return self._write_ledger(ledger)

    def _write_ledger(self, ledger: Mapping[date, DateOutcome]) -> Path:
        table = _outcomes_to_table([ledger[day] for day in sorted(ledger)])
        atomic_write_with(
            self.ledger_path, lambda temp: pq.write_table(table, temp, compression="zstd")
        )
        return self.ledger_path

    # --- reading -------------------------------------------------------------------

    def daily(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
        *,
        series: str | None = None,
    ) -> pd.DataFrame:
        """RAW daily OHLCV for one symbol over ``[from_date, to_date]``, oldest first.

        Prices are integer paise; no corporate-action adjustment has been applied
        (CONTEXT 4.1/4.2). The frame is empty (with the full column set) when the store holds
        nothing for that symbol in that range -- an empty range is a legitimate answer here,
        unlike an empty universe.

        Args:
            symbol: the ticker, case-insensitive.
            from_date: inclusive start.
            to_date: inclusive end.
            series: keep only this NSE series (e.g. "EQ"). ``None`` keeps every series.

        Raises:
            DailyStoreError: the same symbol appears twice on one date. That means several
                series carry it, and silently returning two rows for one day would corrupt
                every downstream candle sequence -- pass ``series=`` to disambiguate.
        """
        frame = self.frame([symbol], from_date, to_date, series=series)
        duplicated = frame["trade_date"].duplicated(keep=False)
        if bool(duplicated.any()):
            clashes = frame.loc[duplicated, ["trade_date", "series"]]
            raise DailyStoreError(
                f"{symbol.upper()} has more than one row on the same date in the store "
                f"({clashes.to_dict('records')!r}). Pass series= to choose one -- returning "
                "two candles for one day would corrupt the bias pair (CONTEXT 3.2)."
            )
        return frame.reset_index(drop=True)

    def frame(
        self,
        symbols: Iterable[str] | None,
        from_date: date,
        to_date: date,
        *,
        series: str | None = None,
    ) -> pd.DataFrame:
        """RAW daily rows for ``symbols`` (``None`` = every symbol) over a date range.

        This is where the universe filter belongs -- pass the F&O list from
        :mod:`acumen.universe` and only those symbols come back (chunk-2 card: store
        everything, filter on query).
        """
        if to_date < from_date:
            raise DailyStoreError(
                f"Empty range: {to_date.isoformat()} is before {from_date.isoformat()}."
            )
        wanted = None if symbols is None else {str(s).strip().upper() for s in symbols}
        if wanted is not None and not wanted:
            raise DailyStoreError(
                "An EMPTY symbol list was passed. That is almost always a bug upstream "
                "(an unloaded universe); pass symbols=None to mean 'every symbol'."
            )

        tables: list[pa.Table] = []
        for path in self._month_paths(from_date, to_date):
            table = pq.read_table(path, schema=DAILY_SCHEMA)
            mask = pc.and_(
                pc.greater_equal(table.column("trade_date"), from_date),
                pc.less_equal(table.column("trade_date"), to_date),
            )
            if wanted is not None:
                mask = pc.and_(
                    mask, pc.is_in(table.column("symbol"), value_set=pa.array(sorted(wanted)))
                )
            if series is not None:
                mask = pc.and_(mask, pc.equal(table.column("series"), series.strip().upper()))
            filtered = table.filter(mask)
            if filtered.num_rows:
                tables.append(filtered)

        combined = pa.concat_tables(tables) if tables else DAILY_SCHEMA.empty_table()
        combined = combined.sort_by(
            [("trade_date", "ascending"), ("symbol", "ascending"), ("series", "ascending")]
        )
        return _to_pandas(combined)

    def _month_paths(self, from_date: date, to_date: date) -> list[Path]:
        paths: list[Path] = []
        year, month = from_date.year, from_date.month
        while (year, month) <= (to_date.year, to_date.month):
            path = self.month_path(date(year, month, 1))
            if path.is_file():
                paths.append(path)
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return paths

    # --- the outcome ledger --------------------------------------------------------

    def outcomes(self) -> dict[date, DateOutcome]:
        """The whole ledger as ``{date: outcome}``. Empty when nothing has been attempted."""
        path = self.ledger_path
        if not path.is_file():
            return {}
        table = pq.read_table(path, schema=LEDGER_SCHEMA)
        result: dict[date, DateOutcome] = {}
        for record in table.to_pylist():
            stamp = record["attempted_at"]
            result[record["trade_date"]] = DateOutcome(
                trade_date=record["trade_date"],
                outcome=record["outcome"],
                source_format=record["source_format"],
                url=record["url"],
                http_status=record["http_status"],
                reason=record["reason"],
                row_count=record["row_count"],
                attempted_at=stamp if isinstance(stamp, datetime) else None,
            )
        return result

    def coverage(self, from_date: date, to_date: date) -> pd.DataFrame:
        """The outcome ledger over ``[from_date, to_date]``, one row per attempted date.

        This is the Q-3 answer made queryable: ``file-present`` dates are trading days,
        ``confirmed-404`` dates are not, and ``error`` dates are simply not known yet.
        Dates never attempted do not appear at all -- absence is not a 404.
        """
        if to_date < from_date:
            raise DailyStoreError(
                f"Empty range: {to_date.isoformat()} is before {from_date.isoformat()}."
            )
        rows = [
            outcome
            for day, outcome in sorted(self.outcomes().items())
            if from_date <= day <= to_date
        ]
        return _to_pandas(_outcomes_to_table(rows))

    def coverage_summary(self, from_date: date, to_date: date) -> dict[str, int]:
        """Counts by outcome over a range, plus ``attempted`` and ``missing``."""
        frame = self.coverage(from_date, to_date)
        counts = {
            name: int((frame["outcome"] == name).sum())
            for name in (OUTCOME_PRESENT, OUTCOME_NOT_FOUND, OUTCOME_ERROR)
        }
        counts["attempted"] = int(len(frame))
        counts["missing"] = (to_date - from_date).days + 1 - counts["attempted"]
        return counts

    def pending_dates(self, from_date: date, to_date: date) -> tuple[date, ...]:
        """Dates in the range that still need attempting -- the resume list.

        Unattempted dates AND ``error`` dates; a ``file-present`` or ``confirmed-404`` date
        is settled. This is what makes the backfill safe to interrupt: it also means a bad
        network afternoon is retried on the next run instead of hardening into a hole.
        """
        settled = {
            day for day, outcome in self.outcomes().items() if outcome.is_terminal
        }
        return tuple(day for day in date_range(from_date, to_date) if day not in settled)


# --- conversions ------------------------------------------------------------------------


def _rows_to_table(rows: Sequence[DailyRow]) -> pa.Table:
    columns = {name: [] for name in DAILY_SCHEMA.names}  # type: ignore[var-annotated]
    for row in rows:
        for name in DAILY_SCHEMA.names:
            columns[name].append(getattr(row, name))
    return pa.table(columns, schema=DAILY_SCHEMA)


def _outcomes_to_table(outcomes: Sequence[DateOutcome]) -> pa.Table:
    columns: dict[str, list[object]] = {name: [] for name in LEDGER_SCHEMA.names}
    for outcome in outcomes:
        if outcome.outcome not in ALL_OUTCOMES:
            raise DailyStoreError(f"Unknown outcome {outcome.outcome!r}.")
        for name in LEDGER_SCHEMA.names:
            columns[name].append(getattr(outcome, name))
    return pa.table(columns, schema=LEDGER_SCHEMA)


def _to_pandas(table: pa.Table) -> pd.DataFrame:
    """Arrow -> pandas with dtypes that keep paise EXACT.

    Integer columns become pandas' nullable ``Int64`` rather than float64: a nullable int
    column converted the default way becomes float, and a float cannot hold a large turnover
    in paise exactly. Dates stay :class:`datetime.date` objects (naive, CONTEXT 7-E8).
    """
    frame = table.to_pandas(
        types_mapper=lambda arrow_type: pd.Int64Dtype() if pa.types.is_integer(arrow_type) else None,
        date_as_object=True,
    )
    for column in _PRICE_COLUMNS:
        if column in frame.columns:
            frame[column] = frame[column].astype("Int64")
    return frame
