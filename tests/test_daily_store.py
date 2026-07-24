"""Chunk-2 tests for the Parquet daily store (CONTEXT 4.1, 6, 7-E11).

The properties under test are the ones the next six chunks will lean on without thinking
about them:

* **RAW integer paise, unchanged by a round trip.** A price that survives the CSV exactly and
  then loses a paisa in Parquet is no better than one that never parsed (CONTEXT 7-E11).
* **Idempotent ingestion.** The backfill is meant to be interrupted and re-run; a second pass
  over the same window must change nothing and must never duplicate a symbol-day.
* **Store everything, filter on query.** Every series NSE published is kept; the F&O universe
  filter is applied by the CALLER, on read.
* **The store never guesses.** Two rows for one symbol-day raise instead of silently
  returning a doubled candle sequence; an empty symbol list raises instead of quietly meaning
  "everything"; a date the store never attempted is absent from the ledger, not a 404.

All offline: rows come from the DERIVED fixtures described in tests/fixtures/PROVENANCE.md.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from acumen.bhavcopy import (
    FORMAT_ARCHIVE,
    FORMAT_UDIFF,
    OUTCOME_ERROR,
    OUTCOME_NOT_FOUND,
    OUTCOME_PRESENT,
    DailyRow,
    DateOutcome,
    Download,
    parse_bhavcopy,
)
from acumen.daily_store import DAILY_SCHEMA, DailyStore, DailyStoreError

FIXTURES = Path(__file__).resolve().parent / "fixtures"
NOW = datetime(2026, 7, 24, 21, 0, 0)


def _rows(fixture: str, source_format: str) -> tuple[DailyRow, ...]:
    return parse_bhavcopy((FIXTURES / fixture).read_text(encoding="utf-8"), source_format)


def _download(day: date, rows: tuple[DailyRow, ...], source_format: str) -> Download:
    same_day = tuple(row for row in rows if row.trade_date == day)
    return Download(
        DateOutcome(
            trade_date=day,
            outcome=OUTCOME_PRESENT,
            source_format=source_format,
            url=f"https://example.invalid/{day.isoformat()}",
            http_status=200,
            row_count=len(same_day),
            attempted_at=NOW,
        ),
        same_day,
    )


def _absent(day: date) -> Download:
    return Download(
        DateOutcome(
            trade_date=day,
            outcome=OUTCOME_NOT_FOUND,
            http_status=404,
            reason="no published bhavcopy in either format",
            attempted_at=NOW,
        )
    )


@pytest.fixture()
def store(tmp_path: Path) -> DailyStore:
    """A store holding the five UDiFF dates plus the two 2026 weekend 404s."""
    built = DailyStore.at(tmp_path / "daily_store")
    udiff = _rows("bhavcopy_udiff_sample.csv", FORMAT_UDIFF)
    for day in sorted({row.trade_date for row in udiff}):
        built.ingest(_download(day, udiff, FORMAT_UDIFF))
    for day in (date(2026, 7, 18), date(2026, 7, 19)):
        built.ingest(_absent(day))
    return built


# --- round trip -------------------------------------------------------------------------


def test_prices_survive_the_round_trip_as_exact_paise(store: DailyStore) -> None:
    """The card's golden, read back out of Parquet: TCS 2026-07-20, close 2251.10."""
    frame = store.daily("TCS", date(2026, 7, 20), date(2026, 7, 20))
    assert len(frame) == 1
    row = frame.iloc[0]
    assert int(row.close_paise) == 225110
    assert int(row.volume) == 2202693
    assert int(row.turnover_paise) == 497162363920, "a large paise value must not become a float"


def test_the_symbol_lookup_is_case_insensitive(store: DailyStore) -> None:
    assert len(store.daily("tcs", date(2026, 7, 14), date(2026, 7, 20))) == 5


def test_rows_come_back_oldest_first(store: DailyStore) -> None:
    """CONTEXT 3.2 walks candles in time order; an unsorted frame would silently mis-pair."""
    frame = store.daily("TCS", date(2026, 7, 1), date(2026, 7, 31))
    assert list(frame["trade_date"]) == [date(2026, 7, d) for d in (14, 15, 16, 17, 20)]


def test_a_range_with_no_data_returns_an_empty_frame_with_the_full_schema(
    store: DailyStore,
) -> None:
    """Unlike an empty universe, an empty date range is a legitimate answer -- but the
    columns must still be there, or every caller needs a special case."""
    frame = store.daily("TCS", date(2019, 1, 1), date(2019, 1, 31))
    assert frame.empty
    assert list(frame.columns) == list(DAILY_SCHEMA.names)


def test_reads_span_month_and_year_boundaries(tmp_path: Path) -> None:
    built = DailyStore.at(tmp_path)
    for fixture, fmt in (
        ("bhavcopy_udiff_sample.csv", FORMAT_UDIFF),
        ("bhavcopy_archive_sample.csv", FORMAT_ARCHIVE),
    ):
        rows = _rows(fixture, fmt)
        for day in sorted({row.trade_date for row in rows}):
            built.ingest(_download(day, rows, fmt))

    frame = built.daily("TCS", date(2018, 1, 1), date(2026, 12, 31))
    assert list(frame["trade_date"]) == [
        date(2018, 1, 1),
        date(2018, 1, 2),
        *[date(2026, 7, d) for d in (14, 15, 16, 17, 20)],
    ]
    assert set(frame["source_format"]) == {FORMAT_ARCHIVE, FORMAT_UDIFF}


# --- idempotency ------------------------------------------------------------------------


def test_re_ingesting_a_date_replaces_it_and_never_duplicates(store: DailyStore) -> None:
    """The card: "re-run is idempotent (no dupes)"."""
    udiff = _rows("bhavcopy_udiff_sample.csv", FORMAT_UDIFF)
    before = store.frame(None, date(2026, 7, 1), date(2026, 7, 31))
    path = store.month_path(date(2026, 7, 20))
    bytes_before = path.read_bytes()

    for _ in range(2):
        for day in sorted({row.trade_date for row in udiff}):
            store.ingest(_download(day, udiff, FORMAT_UDIFF))

    after = store.frame(None, date(2026, 7, 1), date(2026, 7, 31))
    assert len(after) == len(before) == 31
    assert after.equals(before)
    assert path.read_bytes() == bytes_before, "a no-op re-ingest must not even rewrite bytes"


def test_a_corrected_file_replaces_the_old_rows_rather_than_adding_to_them(
    store: DailyStore,
) -> None:
    """If NSE republishes a date, the store must hold the NEW rows only."""
    corrected = DailyRow(
        trade_date=date(2026, 7, 20),
        symbol="TCS",
        series="EQ",
        open_paise=1,
        high_paise=2,
        low_paise=1,
        close_paise=2,
        volume=3,
        source_format=FORMAT_UDIFF,
    )
    store.ingest(
        Download(
            DateOutcome(
                trade_date=date(2026, 7, 20),
                outcome=OUTCOME_PRESENT,
                source_format=FORMAT_UDIFF,
                http_status=200,
                row_count=1,
                attempted_at=NOW,
            ),
            (corrected,),
        )
    )
    same_day = store.frame(None, date(2026, 7, 20), date(2026, 7, 20))
    assert len(same_day) == 1
    assert int(same_day.iloc[0].close_paise) == 2
    # ...and the neighbouring dates in the same month file are untouched.
    assert len(store.frame(None, date(2026, 7, 17), date(2026, 7, 17))) == 6


def test_the_ledger_keeps_one_row_per_date(store: DailyStore) -> None:
    store.ingest(_absent(date(2026, 7, 19)))
    coverage = store.coverage(date(2026, 7, 13), date(2026, 7, 24))
    assert list(coverage["trade_date"]).count(date(2026, 7, 19)) == 1


# --- store everything, filter on query ---------------------------------------------------


def test_every_series_is_stored_not_just_the_tradable_one(store: DailyStore) -> None:
    frame = store.frame(["BIOCON"], date(2026, 7, 14), date(2026, 7, 14))
    assert sorted(frame["series"]) == ["BL", "EQ"]


def test_the_universe_filter_is_applied_on_read(store: DailyStore) -> None:
    universe = ["TCS", "RELIANCE"]
    frame = store.frame(universe, date(2026, 7, 14), date(2026, 7, 20))
    assert set(frame["symbol"]) == {"TCS", "RELIANCE"}
    assert len(frame) == 10


def test_a_series_filter_disambiguates(store: DailyStore) -> None:
    frame = store.daily("BIOCON", date(2026, 7, 14), date(2026, 7, 14), series="EQ")
    assert len(frame) == 1
    assert frame.iloc[0].series == "EQ"


def test_the_block_deal_row_is_ignored_and_the_equity_row_is_returned(
    store: DailyStore,
) -> None:
    """Real data: NSE published BIOCON twice on 2026-07-14 (EQ and the block-deal series BL).

    Returning both would hand chunk 4 two candles for one day and silently corrupt the bias
    pair. QUESTIONS.md Q-4 is now RULED: the instrument is the equity series, so `daily()`
    keeps the EQ row and ignores BL -- which stays in the store, queryable by `frame()`.
    """
    frame = store.daily("BIOCON", date(2026, 7, 14), date(2026, 7, 14))
    assert len(frame) == 1
    assert frame.iloc[0].series == "EQ"
    assert sorted(store.frame(["BIOCON"], date(2026, 7, 14), date(2026, 7, 14))["series"]) == [
        "BL",
        "EQ",
    ]


def test_two_whitelist_series_on_one_symbol_day_raise_loudly(store: DailyStore) -> None:
    """The Q-4 ruling's safety net: "Two whitelist series on one symbol-date -> raise loudly".

    No real bhavcopy in this repo carries the case -- a symbol trades as EQ or as BE/BZ, not
    both -- so it is built here from a synthetic frame. If it ever happens for real, the
    whitelist itself is wrong and a silent ranking would hide that.
    """
    rows = [
        DailyRow(
            trade_date=date(2026, 7, 14),
            symbol="ACME",
            series=series,
            open_paise=1000,
            high_paise=1100,
            low_paise=900,
            close_paise=1050,
            volume=10,
        )
        for series in ("EQ", "BE")
    ]
    store.write_rows(date(2026, 7, 14), rows)
    with pytest.raises(DailyStoreError, match="more than one WHITELIST series"):
        store.daily("ACME", date(2026, 7, 14), date(2026, 7, 14))


def test_an_empty_symbol_list_raises_rather_than_meaning_everything(store: DailyStore) -> None:
    """An unloaded universe is the likely cause, and a silent "everything" would hide it."""
    with pytest.raises(DailyStoreError, match="EMPTY symbol list"):
        store.frame([], date(2026, 7, 14), date(2026, 7, 20))


def test_a_backwards_range_is_refused(store: DailyStore) -> None:
    with pytest.raises(DailyStoreError, match="Empty range"):
        store.daily("TCS", date(2026, 7, 20), date(2026, 7, 14))
    with pytest.raises(DailyStoreError, match="Empty range"):
        store.coverage(date(2026, 7, 20), date(2026, 7, 14))


# --- the outcome ledger -----------------------------------------------------------------


def test_the_ledger_records_the_cards_two_named_cases(store: DailyStore) -> None:
    """Chunk-2 card golden: 2026-07-19 (Sunday) confirmed-404, 2026-07-20 file-present."""
    ledger = store.outcomes()
    assert ledger[date(2026, 7, 19)].outcome == OUTCOME_NOT_FOUND
    assert ledger[date(2026, 7, 19)].http_status == 404
    assert ledger[date(2026, 7, 20)].outcome == OUTCOME_PRESENT
    assert ledger[date(2026, 7, 20)].row_count == 6


def test_coverage_summary_counts_and_names_what_is_missing(store: DailyStore) -> None:
    summary = store.coverage_summary(date(2026, 7, 13), date(2026, 7, 24))
    assert summary[OUTCOME_PRESENT] == 5
    assert summary[OUTCOME_NOT_FOUND] == 2
    assert summary[OUTCOME_ERROR] == 0
    assert summary["attempted"] == 7
    assert summary["missing"] == 5, "12 dates in the range, 7 attempted"


def test_a_date_never_attempted_is_absent_from_the_ledger(store: DailyStore) -> None:
    """Absence is NOT a 404. QUESTIONS.md Q-3 safeguard 1 depends on the distinction."""
    assert date(2026, 7, 13) not in store.outcomes()
    coverage = store.coverage(date(2026, 7, 13), date(2026, 7, 13))
    assert coverage.empty


def test_pending_dates_is_the_resume_list_and_retries_errors(store: DailyStore) -> None:
    store.record_outcome(
        DateOutcome(
            trade_date=date(2026, 7, 13),
            outcome=OUTCOME_ERROR,
            reason="HTTP 503",
            attempted_at=NOW,
        )
    )
    pending = store.pending_dates(date(2026, 7, 13), date(2026, 7, 24))
    assert date(2026, 7, 13) in pending, "an error date is NOT settled -- retry it"
    assert date(2026, 7, 20) not in pending, "a file-present date is settled"
    assert date(2026, 7, 19) not in pending, "a confirmed-404 date is settled"
    assert pending == (
        date(2026, 7, 13),
        *[date(2026, 7, d) for d in (21, 22, 23, 24)],
    )


def test_an_error_outcome_may_not_carry_prices() -> None:
    with pytest.raises(DailyStoreError, match="only file-present may carry prices"):
        DailyStore.at(Path("unused")).ingest(
            Download(
                DateOutcome(trade_date=date(2026, 7, 20), outcome=OUTCOME_ERROR, reason="x"),
                (
                    DailyRow(
                        trade_date=date(2026, 7, 20),
                        symbol="TCS",
                        series="EQ",
                        open_paise=1,
                        high_paise=1,
                        low_paise=1,
                        close_paise=1,
                        volume=1,
                    ),
                ),
            )
        )


def test_a_present_outcome_with_no_rows_is_refused(tmp_path: Path) -> None:
    with pytest.raises(DailyStoreError, match="carries no rows"):
        DailyStore.at(tmp_path).ingest(
            Download(
                DateOutcome(
                    trade_date=date(2026, 7, 20), outcome=OUTCOME_PRESENT, row_count=0
                )
            )
        )


def test_rows_dated_differently_from_the_date_being_written_are_refused(
    tmp_path: Path,
) -> None:
    rows = _rows("bhavcopy_udiff_sample.csv", FORMAT_UDIFF)
    with pytest.raises(DailyStoreError, match="was given rows dated"):
        DailyStore.at(tmp_path).write_rows(date(2026, 7, 20), rows)


# --- files on disk ----------------------------------------------------------------------


def test_the_layout_is_one_parquet_file_per_month(store: DailyStore) -> None:
    path = store.month_path(date(2026, 7, 20))
    assert path.is_file()
    assert path.name == "bhavcopy_2026-07.parquet"
    assert path.parent.name == "2026"
    assert store.month_path(date(2026, 7, 1)) == path


def test_the_written_schema_is_explicit_and_stable(store: DailyStore) -> None:
    """An inferred schema changes shape when a month happens to have no nulls."""
    written = pq.read_schema(store.month_path(date(2026, 7, 20)))
    assert written.names == list(DAILY_SCHEMA.names)
    for field in DAILY_SCHEMA:
        assert written.field(field.name).type == field.type


def test_writes_leave_no_temp_debris(store: DailyStore) -> None:
    """Atomic writes create a temp file beside the target; none may survive."""
    leftovers = [p.name for p in store.root.rglob("*") if p.name.endswith(".tmp")]
    assert leftovers == []
