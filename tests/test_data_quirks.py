"""The curated data-quirk mechanism (chunk-4 prep addendum; src/acumen/data_quirks.py).

Two layers:

* the MECHANISM, tested here against a SYNTHETIC malformed archive CSV -- it corrects only a
  file broken in exactly the documented way, is consulted only after normal validation fails,
  and never emits a still-wrong date;
* the REAL 2020-07-13 round-trip, in ``test_data_quirks_roundtrip.py``, which uses the frozen
  DERIVED cut of NSE's actual malformed file and the frozen SmartAPI ONE_DAY closes.

Everything here is offline (the conftest guard fails any test that opens a socket).

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from typing import Any

import pytest

from acumen import data_quirks
from acumen.bhavcopy import (
    FORMAT_ARCHIVE,
    OUTCOME_ERROR,
    OUTCOME_PRESENT,
    download_bhavcopy,
    parse_bhavcopy,
    url_for,
)
from acumen.data_quirks import ArchiveYearQuirk, DataQuirkError, correct_rows

NOW = datetime(2026, 7, 25, 9, 0, 0)
REAL = date(2020, 7, 13)

# A synthetic archive-format bhavcopy carrying the documented malformation: the TIMESTAMP
# column reads 13-JUL-0020 (year 0020) instead of 13-JUL-2020. Two rows are enough.
_HEADER = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN"


def _archive_csv(timestamp: str, *, second_timestamp: str | None = None) -> str:
    rows = [
        _HEADER,
        f"TCS,EQ,2200.00,2230.00,2180.00,2210.00,2210.00,2195.00,1000000,2210000000.00,{timestamp},50000,INE467B01029",
        "RELIANCE,EQ,1900.00,1930.00,1880.00,1910.00,1910.00,1895.00,2000000,3820000000.00,"
        f"{second_timestamp or timestamp},80000,INE002A01018",
    ]
    return "\r\n".join(rows) + "\r\n"


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


# --- the pure correction ------------------------------------------------------------------


def test_correct_rows_fixes_the_documented_year_malformation() -> None:
    rows = parse_bhavcopy(_archive_csv("13-JUL-0020"), FORMAT_ARCHIVE)
    assert {r.trade_date for r in rows} == {date(20, 7, 13)}, "parses to the malformed year"

    result = correct_rows(REAL, FORMAT_ARCHIVE, rows)
    assert result is not None
    corrected, reason = result
    assert {r.trade_date for r in corrected} == {REAL}
    assert "0020" in reason and "2020" in reason
    # prices are UNTOUCHED -- only the date is corrected
    tcs = [r for r in corrected if r.symbol == "TCS"][0]
    assert tcs.close_paise == 221000 and tcs.open_paise == 220000


def test_correct_rows_refuses_a_file_broken_a_different_way() -> None:
    """A correction applies ONLY when every row carries EXACTLY the documented malformation."""
    # a different wrong year (0021) is not the documented pattern -> stays an error
    other_year = parse_bhavcopy(_archive_csv("13-JUL-0021"), FORMAT_ARCHIVE)
    assert correct_rows(REAL, FORMAT_ARCHIVE, other_year) is None
    # a MIXED file (one malformed row, one correct row) -> not exactly {malformed_date}
    mixed = parse_bhavcopy(
        _archive_csv("13-JUL-0020", second_timestamp="13-JUL-2020"), FORMAT_ARCHIVE
    )
    assert correct_rows(REAL, FORMAT_ARCHIVE, mixed) is None


def test_correct_rows_returns_none_when_there_is_no_quirk_for_the_date() -> None:
    rows = parse_bhavcopy(_archive_csv("14-JUL-0020"), FORMAT_ARCHIVE)
    assert correct_rows(date(2019, 1, 1), FORMAT_ARCHIVE, rows) is None


def test_a_quirk_that_would_change_nothing_is_refused() -> None:
    with pytest.raises(DataQuirkError, match="changes nothing|wrong_year"):
        ArchiveYearQuirk(
            trade_date=REAL, source_format=FORMAT_ARCHIVE, wrong_year=2020, reason="noop"
        )


# --- the downloader hook ------------------------------------------------------------------


def test_download_consults_the_quirk_only_after_validation_and_ingests_present() -> None:
    """The malformed real-date file: normal validation refuses it, the quirk rescues it."""
    url = url_for(REAL, FORMAT_ARCHIVE)
    payload = _zip_of("cm13JUL2020bhav.csv", _archive_csv("13-JUL-0020"))
    session = _StubSession({url: _Response(200, payload)})

    result = download_bhavcopy(REAL, session=session, sleep=_no_sleep, now=NOW)
    assert result.outcome.outcome == OUTCOME_PRESENT
    assert result.outcome.reason and "0020" in result.outcome.reason
    assert {r.trade_date for r in result.rows} == {REAL}
    # the raw archived text is the SOURCE, still malformed -- evidence, not a re-serialisation
    assert "13-JUL-0020" in (result.raw_csv or "")


def test_download_leaves_an_undocumented_malformation_as_error() -> None:
    """A different malformation is never silently corrected -- the store stays honest."""
    url = url_for(REAL, FORMAT_ARCHIVE)
    payload = _zip_of("cm13JUL2020bhav.csv", _archive_csv("13-JUL-0021"))
    session = _StubSession({url: _Response(200, payload)})

    result = download_bhavcopy(REAL, session=session, sleep=_no_sleep, now=NOW)
    assert result.outcome.outcome == OUTCOME_ERROR
    assert result.rows == ()
    assert "0020-07-13" not in (result.outcome.reason or "")  # the error names the FILE'S date
