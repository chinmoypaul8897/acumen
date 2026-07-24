"""Chunk-2 tests for the bhavcopy downloader and parser (CONTEXT 4.1).

Two things decide whether 25 years of history can be trusted, and both are tested here far
harder than the happy path:

1. **Paise are exact.** Prices come off the CSV text through :class:`~decimal.Decimal`, never
   through a float. A value that is not a whole number of paise is refused rather than
   rounded (CONTEXT 7-E11).
2. **The three outcomes are never confused.** ``file-present`` / ``confirmed-404`` / ``error``
   is the ledger the derived trading calendar is built from (QUESTIONS.md Q-3). A fetch that
   FAILED must never be recorded as "NSE published nothing", because that is how a bad
   network afternoon silently deletes trading days and shifts every bias pair that spans them.

Every test is offline. The parse fixtures are real lines lifted out of real bhavcopy files
(tests/fixtures/PROVENANCE.md); the download tests answer from a stub session, and
tests/conftest.py fails any test that opens a socket.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from acumen import bhavcopy
from acumen.bhavcopy import (
    FORMAT_ARCHIVE,
    FORMAT_UDIFF,
    OUTCOME_ERROR,
    OUTCOME_NOT_FOUND,
    OUTCOME_PRESENT,
    BhavcopyError,
    DateOutcome,
    candidate_formats,
    date_range,
    download_bhavcopy,
    extract_csv,
    format_for,
    parse_bhavcopy,
    url_for,
)
from acumen.nse_http import NseFetchError, NseNotFoundError

FIXTURES = Path(__file__).resolve().parent / "fixtures"
UDIFF_SAMPLE = FIXTURES / "bhavcopy_udiff_sample.csv"
ARCHIVE_SAMPLE = FIXTURES / "bhavcopy_archive_sample.csv"

NOW = datetime(2026, 7, 24, 21, 0, 0)


@pytest.fixture()
def udiff_text() -> str:
    return UDIFF_SAMPLE.read_text(encoding="utf-8")


@pytest.fixture()
def archive_text() -> str:
    return ARCHIVE_SAMPLE.read_text(encoding="utf-8")


def _zip_of(name: str, text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, text)
    return buffer.getvalue()


class _Response:
    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content


class _StubSession:
    """Answers per-URL, so the two candidate formats can be scripted independently."""

    def __init__(self, answers: dict[str, Any]) -> None:
        self.answers = answers
        self.urls: list[str] = []

    def get(self, url: str, timeout: float | None = None) -> Any:
        self.urls.append(url)
        result = self.answers.get(url, _Response(404))
        if isinstance(result, Exception):
            raise result
        return result


def _no_sleep(_seconds: float) -> None:
    return None


# --- URLs and the era boundary ----------------------------------------------------------


@pytest.mark.parametrize(
    "day, expected",
    [
        (date(2000, 1, 3), FORMAT_ARCHIVE),
        (date(2018, 1, 1), FORMAT_ARCHIVE),
        (date(2024, 6, 30), FORMAT_ARCHIVE),
        (date(2024, 7, 1), FORMAT_UDIFF),
        (date(2026, 7, 20), FORMAT_UDIFF),
    ],
)
def test_the_era_boundary_follows_context_4_1(day: date, expected: str) -> None:
    """CONTEXT 4.1: UDiFF "since Jul-2024", the archive format before it."""
    assert format_for(day) == expected


def test_both_formats_are_tried_before_a_date_is_called_a_non_trading_day() -> None:
    """CONTEXT 4.1 states the cutover only to the MONTH.

    So a `confirmed-404` is only allowed to mean "neither published file exists". Without
    this, a wrong cutover date would turn a run of real trading days into holidays.
    """
    assert candidate_formats(date(2026, 7, 20)) == (FORMAT_UDIFF, FORMAT_ARCHIVE)
    assert candidate_formats(date(2018, 1, 1)) == (FORMAT_ARCHIVE, FORMAT_UDIFF)


def test_the_published_urls_are_built_exactly_as_context_4_1_documents() -> None:
    assert url_for(date(2026, 7, 20), FORMAT_UDIFF) == (
        "https://nsearchives.nseindia.com/content/cm/"
        "BhavCopy_NSE_CM_0_0_0_20260720_F_0000.csv.zip"
    )
    assert url_for(date(2018, 1, 1), FORMAT_ARCHIVE) == (
        "https://nsearchives.nseindia.com/content/historical/EQUITIES/2018/JAN/"
        "cm01JAN2018bhav.csv.zip"
    )
    # Zero-padded day in the FILE name, even though the CSV inside stamps "3-JAN-2000".
    assert url_for(date(2000, 1, 3), FORMAT_ARCHIVE).endswith("2000/JAN/cm03JAN2000bhav.csv.zip")


def test_an_unknown_format_name_is_refused() -> None:
    with pytest.raises(BhavcopyError, match="Unknown bhavcopy format"):
        url_for(date(2026, 7, 20), "parquet")


# --- parsing: UDiFF ---------------------------------------------------------------------


def test_the_udiff_golden_row_matches_results_md(udiff_text: str) -> None:
    """The chunk-2 card's golden: TCS 2026-07-20 close 2251.10, volume 2,202,693.

    Independently verified in docs/RESULTS.md section A against a SmartAPI ONE_DAY candle,
    which is a different vendor reading the same exchange.
    """
    rows = parse_bhavcopy(udiff_text, FORMAT_UDIFF)
    tcs = [r for r in rows if r.symbol == "TCS" and r.trade_date == date(2026, 7, 20)]
    assert len(tcs) == 1
    row = tcs[0]
    assert row.close_paise == 225110, "2251.10 rupees, exactly, as integer paise"
    assert row.volume == 2202693
    assert (row.open_paise, row.high_paise, row.low_paise) == (228010, 228340, 224510)
    assert row.series == "EQ"
    assert row.isin == "INE467B01029"
    assert row.instrument_type == "STK"
    assert row.source_format == FORMAT_UDIFF
    assert row.last_paise == 225100, "LastPric is the LTP and differs from the closing price"
    assert row.turnover_paise == 497162363920


def test_udiff_keeps_every_series_including_the_ones_we_do_not_trade(udiff_text: str) -> None:
    """Store everything, filter on query (chunk-2 card). BIOCON traded EQ and BL that day."""
    rows = parse_bhavcopy(udiff_text, FORMAT_UDIFF)
    biocon = {r.series for r in rows if r.symbol == "BIOCON" and r.trade_date == date(2026, 7, 14)}
    assert biocon == {"EQ", "BL"}


def test_the_parser_is_date_agnostic(udiff_text: str) -> None:
    """A file carries one date; the PARSER must not assume it, or a multi-date fixture
    (and any future combined file) could not be read. The DOWNLOADER enforces the date."""
    dates = {row.trade_date for row in parse_bhavcopy(udiff_text, FORMAT_UDIFF)}
    assert dates == {date(2026, 7, d) for d in (14, 15, 16, 17, 20)}


# --- parsing: the old archive format ----------------------------------------------------


def test_the_archive_format_parses_with_its_own_column_names(archive_text: str) -> None:
    rows = parse_bhavcopy(archive_text, FORMAT_ARCHIVE)
    tcs = [r for r in rows if r.symbol == "TCS" and r.trade_date == date(2018, 1, 1)]
    assert len(tcs) == 1
    row = tcs[0]
    assert (row.open_paise, row.high_paise, row.low_paise, row.close_paise) == (
        268230,
        269480,
        263500,
        264560,
    )
    assert row.volume == 675880
    assert row.series == "EQ"
    assert row.source_format == FORMAT_ARCHIVE
    assert row.instrument_type is None, "the old format has no instrument-type column"


def test_a_price_without_decimals_is_still_exact_paise(archive_text: str) -> None:
    """The old files print "2635" for 2635.00 -- 263500 paise, not 2635."""
    rows = parse_bhavcopy(archive_text, FORMAT_ARCHIVE)
    tcs = next(r for r in rows if r.symbol == "TCS" and r.trade_date == date(2018, 1, 1))
    assert tcs.low_paise == 263500


def test_the_2000_era_header_without_totaltrades_or_isin_still_parses() -> None:
    """Verified live against cm03JAN2000bhav.csv on 2026-07-24: the header stops at
    TIMESTAMP, and the day is unpadded ("3-JAN-2000"). Both must parse, or the operator's
    2000-onwards backfill dies on its first date."""
    text = (
        "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,\n"
        "21STCENMGM,EQ,20,24.6,20,24.55,24.6,19.65,54000,1271385,3-JAN-2000,\n"
    )
    rows = parse_bhavcopy(text, FORMAT_ARCHIVE)
    assert len(rows) == 1
    assert rows[0].trade_date == date(2000, 1, 3)
    assert rows[0].open_paise == 2000
    assert rows[0].close_paise == 2455
    assert rows[0].trades is None and rows[0].isin is None


# --- parsing: refusals ------------------------------------------------------------------


def test_a_missing_required_column_is_refused() -> None:
    with pytest.raises(BhavcopyError, match="missing column"):
        parse_bhavcopy("SYMBOL,SERIES,OPEN\nTCS,EQ,10\n", FORMAT_ARCHIVE)


def test_a_price_that_is_not_a_whole_number_of_paise_is_refused() -> None:
    """CONTEXT 7-E11 makes paise the price domain. Rounding here would be a price change."""
    text = (
        "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,\n"
        "TCS,EQ,100.005,101,99,100,100,100,1,100,01-JAN-2018,\n"
    )
    with pytest.raises(BhavcopyError, match="not a whole number of paise"):
        parse_bhavcopy(text, FORMAT_ARCHIVE)


def test_the_paise_conversion_does_not_go_through_a_float() -> None:
    """int(float("2189.20") * 100) == 218919, so a float path would lose a real paisa.

    2189.20 is TCS's own close on 2026-07-15 in this repo's UDiFF fixture (REVIEW_2 Finding
    4 replaced the original 2251.10 example, which round-trips through a float perfectly and
    therefore demonstrated nothing).
    """
    assert int(float("2189.20") * 100) == 218919, "the float path is short by a paisa"
    text = (
        "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,\n"
        "TCS,EQ,2189.20,2189.20,2189.20,2189.20,2189.20,2189.20,1,2189.20,01-JAN-2018,\n"
    )
    row = parse_bhavcopy(text, FORMAT_ARCHIVE)[0]
    assert row.close_paise == 218920
    assert isinstance(row.close_paise, int)


def test_a_non_numeric_price_is_refused() -> None:
    text = (
        "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,\n"
        "TCS,EQ,-,101,99,100,100,100,1,100,01-JAN-2018,\n"
    )
    with pytest.raises(BhavcopyError, match="not a number"):
        parse_bhavcopy(text, FORMAT_ARCHIVE)


def test_an_empty_file_is_an_error_not_an_empty_day() -> None:
    with pytest.raises(BhavcopyError, match="zero rows"):
        parse_bhavcopy(
            "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,\n",
            FORMAT_ARCHIVE,
        )


def test_html_behind_a_200_is_not_mistaken_for_a_zip() -> None:
    """NSE serves an HTML page for a blocked file; treating it as an empty day would be fatal."""
    with pytest.raises(BhavcopyError, match="not a ZIP"):
        extract_csv(b"<!DOCTYPE html><html>Access Denied</html>")


def test_a_zip_without_exactly_one_csv_is_refused() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a.csv", "x")
        archive.writestr("b.csv", "y")
    with pytest.raises(BhavcopyError, match="exactly one CSV"):
        extract_csv(buffer.getvalue())


# --- the download outcome (QUESTIONS.md Q-3 ledger) --------------------------------------


def test_a_present_file_is_recorded_as_file_present(udiff_text: str) -> None:
    day = date(2026, 7, 20)
    url = url_for(day, FORMAT_UDIFF)
    only_20 = "\n".join(
        [udiff_text.splitlines()[0]]
        + [line for line in udiff_text.splitlines()[1:] if line.startswith("2026-07-20,")]
    )
    session = _StubSession({url: _Response(200, _zip_of("b.csv", only_20))})

    result = download_bhavcopy(day, session=session, sleep=_no_sleep, now=NOW)
    assert result.outcome.outcome == OUTCOME_PRESENT
    assert result.outcome.source_format == FORMAT_UDIFF
    assert result.outcome.row_count == len(result.rows) == 6
    assert result.outcome.http_status == 200
    assert result.raw_csv == only_20, "the SOURCE text is carried, not a re-serialisation"
    assert session.urls == [url], "a present file costs exactly one request"


def test_a_404_from_both_formats_is_confirmed_404() -> None:
    """The card's named case: 2026-07-19 is a Sunday and NSE publishes nothing."""
    day = date(2026, 7, 19)
    session = _StubSession({})  # everything 404s

    result = download_bhavcopy(day, session=session, sleep=_no_sleep, now=NOW)
    assert result.outcome.outcome == OUTCOME_NOT_FOUND
    assert result.outcome.http_status == 404
    assert result.rows == ()
    assert session.urls == [
        url_for(day, FORMAT_UDIFF),
        url_for(day, FORMAT_ARCHIVE),
    ], "both formats must be asked before a date may be called a non-trading day"


def test_the_other_format_rescues_a_date_near_the_era_boundary(archive_text: str) -> None:
    """If CONTEXT 4.1's month-granular cutover is off by a few days, the file is still found
    -- and the outcome records WHICH format actually answered."""
    day = date(2024, 7, 2)  # our boundary says UDiFF; pretend NSE still published the old one
    lines = archive_text.splitlines()
    rows = "\n".join(
        [lines[0]]
        + [line.replace("01-JAN-2018", "02-JUL-2024") for line in lines[1:] if ",01-JAN-2018," in line]
    )
    session = _StubSession({url_for(day, FORMAT_ARCHIVE): _Response(200, _zip_of("b.csv", rows))})

    result = download_bhavcopy(day, session=session, sleep=_no_sleep, now=NOW)
    assert result.outcome.outcome == OUTCOME_PRESENT
    assert result.outcome.source_format == FORMAT_ARCHIVE
    assert len(session.urls) == 2


def test_a_failed_fetch_is_an_error_and_never_a_holiday() -> None:
    """QUESTIONS.md Q-3 safeguard 1, the single most important rule in this module.

    A 403 burst that outlives its retries means the date is UNKNOWN. Recording it as
    confirmed-404 would delete a trading day from the derived calendar for good.
    """
    day = date(2026, 7, 20)
    session = _StubSession({url_for(day, FORMAT_UDIFF): _Response(503)})

    result = download_bhavcopy(day, session=session, sleep=_no_sleep, max_attempts=2, now=NOW)
    assert result.outcome.outcome == OUTCOME_ERROR
    assert result.outcome.outcome != OUTCOME_NOT_FOUND
    assert "503" in (result.outcome.reason or "")
    assert result.outcome.is_terminal is False, "an error must be retried, never settled"


def test_an_error_on_the_second_format_does_not_become_a_404() -> None:
    """The subtle version: format one legitimately 404s, format two errors. Still UNKNOWN."""
    day = date(2018, 1, 1)
    session = _StubSession({url_for(day, FORMAT_UDIFF): _Response(500)})

    result = download_bhavcopy(day, session=session, sleep=_no_sleep, max_attempts=1, now=NOW)
    assert result.outcome.outcome == OUTCOME_ERROR


def test_a_bot_shield_page_is_retried_and_then_recorded_as_an_error() -> None:
    """NSE serves its shield as HTML behind an HTTP 200.

    Since REVIEW_2 Finding 2 that is treated exactly as the JSON path treats an undecodable
    200: transient, retried to the end of the budget (CONTEXT 4.3 -- access-denied bursts are
    NORMAL). When the budget runs out the date is an `error`, never a missing day.
    """
    day = date(2026, 7, 20)
    session = _StubSession({url_for(day, FORMAT_UDIFF): _Response(200, b"<html>nope</html>")})

    result = download_bhavcopy(day, session=session, sleep=_no_sleep, now=NOW)
    assert result.outcome.outcome == OUTCOME_ERROR
    assert "HTML page" in (result.outcome.reason or "")
    assert "after 4 attempts" in (result.outcome.reason or "")


def test_a_corrupt_body_that_is_not_html_is_an_error_not_a_missing_day() -> None:
    """A truncated or garbled ZIP is a damaged download, and it fails fast rather than
    burning the retry budget -- only the shield's HTML page is treated as transient."""
    day = date(2026, 7, 20)
    session = _StubSession({url_for(day, FORMAT_UDIFF): _Response(200, b"PK\x03\x04garbage")})

    result = download_bhavcopy(day, session=session, sleep=_no_sleep, now=NOW)
    assert result.outcome.outcome == OUTCOME_ERROR
    assert "not a ZIP" in (result.outcome.reason or "")


def test_a_file_that_is_not_the_requested_date_is_refused(udiff_text: str) -> None:
    """NSE serving yesterday's file under today's URL would poison the store AND, through
    the ledger, the calendar."""
    day = date(2026, 7, 21)
    session = _StubSession(
        {url_for(day, FORMAT_UDIFF): _Response(200, _zip_of("b.csv", udiff_text))}
    )

    result = download_bhavcopy(day, session=session, sleep=_no_sleep, now=NOW)
    assert result.outcome.outcome == OUTCOME_ERROR
    assert "not the date it was requested for" in (result.outcome.reason or "")


def test_a_transient_burst_is_retried_before_it_becomes_an_error(udiff_text: str) -> None:
    """CONTEXT 4.3 / CLAUDE.md: transient bursts are NORMAL -- retry, never treat the first
    failure as an answer."""

    day = date(2026, 7, 20)
    only_20 = "\n".join(
        [udiff_text.splitlines()[0]]
        + [line for line in udiff_text.splitlines()[1:] if line.startswith("2026-07-20,")]
    )
    url = url_for(day, FORMAT_UDIFF)
    replies = [_Response(403), _Response(403), _Response(200, _zip_of("b.csv", only_20))]

    class _Flaky(_StubSession):
        def get(self, target: str, timeout: float | None = None) -> Any:
            self.urls.append(target)
            if target == bhavcopy.nse_http.NSE_HOME_URL:
                return _Response(403)
            return replies.pop(0)

    session = _Flaky({})
    result = download_bhavcopy(day, session=session, sleep=_no_sleep, now=NOW)
    assert result.outcome.outcome == OUTCOME_PRESENT
    assert session.urls.count(url) == 3


def test_the_ledger_timestamp_must_be_naive_ist() -> None:
    from datetime import timedelta, timezone

    aware = datetime(2026, 7, 24, 21, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    with pytest.raises(BhavcopyError, match="naive IST"):
        download_bhavcopy(date(2026, 7, 20), session=_StubSession({}), now=aware)


def test_404_is_a_distinct_exception_from_a_failure() -> None:
    """The type-level version of the same rule, at the fetch layer."""
    assert issubclass(NseNotFoundError, NseFetchError)


# --- small helpers ----------------------------------------------------------------------


def test_the_date_range_includes_weekends() -> None:
    """Deliberate: the Q-3 ruling derives trading days from what NSE published, and NSE does
    hold occasional weekend sessions. Skipping Saturdays would replace evidence with a rule."""
    days = list(date_range(date(2026, 7, 17), date(2026, 7, 20)))
    assert days == [date(2026, 7, d) for d in (17, 18, 19, 20)]


def test_a_backwards_range_is_refused() -> None:
    with pytest.raises(BhavcopyError, match="Empty range"):
        list(date_range(date(2026, 7, 20), date(2026, 7, 17)))


def test_an_unknown_outcome_name_cannot_be_constructed() -> None:
    with pytest.raises(BhavcopyError, match="Unknown outcome"):
        DateOutcome(trade_date=date(2026, 7, 20), outcome="probably-a-holiday")


def test_summarise_counts_every_kind() -> None:
    outcomes = [
        DateOutcome(trade_date=date(2026, 7, 20), outcome=OUTCOME_PRESENT),
        DateOutcome(trade_date=date(2026, 7, 19), outcome=OUTCOME_NOT_FOUND),
        DateOutcome(trade_date=date(2026, 7, 18), outcome=OUTCOME_NOT_FOUND),
        DateOutcome(trade_date=date(2026, 7, 17), outcome=OUTCOME_ERROR),
    ]
    assert bhavcopy.summarise(outcomes) == {
        OUTCOME_PRESENT: 1,
        OUTCOME_NOT_FOUND: 2,
        OUTCOME_ERROR: 1,
        "attempted": 4,
    }
