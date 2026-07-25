"""The REAL 2020-07-13 data-quirk round-trip, over the frozen DERIVED fixtures (chunk-4 prep).

Offline: the DERIVED cut of NSE's actual malformed archive bhavcopy
(``tests/fixtures/quirk_2020-07-13_archive_cut.csv``, TIMESTAMP ``13-Jul-20``) plus the two
verbatim SmartAPI ONE_DAY responses. Proves end to end that:

* normal validation refuses the file (its rows parse to 0020-07-13);
* the curated quirk corrects it to 2020-07-13 and the prices survive untouched;
* the corrected TCS close equals SmartAPI ONE_DAY to the paisa -- TCS had no intervening
  corporate action, so raw == adjusted (the adjustment-free verification leg);
* the corrected RELIANCE close does NOT match SmartAPI ONE_DAY, and it is meant not to:
  SmartAPI ONE_DAY is corporate-action back-adjusted (OPEN-8 evidence, QUESTIONS.md), while
  the bhavcopy is raw. The gap is the known artifact, not a defect;
* a full download -> ingest -> read-back through a stubbed session reproduces the store row.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from acumen import data_quirks
from acumen.bhavcopy import (
    FORMAT_ARCHIVE,
    OUTCOME_PRESENT,
    download_bhavcopy,
    parse_bhavcopy,
    url_for,
)
from acumen.daily_store import DailyStore

FIX = Path(__file__).resolve().parent / "fixtures"
DAY = date(2020, 7, 13)
NOW = datetime(2026, 7, 25, 9, 0, 0)
WITHIN = 0.05  # percent -- the addendum's cross-check tolerance


def _cut() -> str:
    return (FIX / "quirk_2020-07-13_archive_cut.csv").read_text(encoding="utf-8")


def _smartapi_close(symbol: str) -> float:
    payload = json.loads((FIX / f"smartapi_oneday_{symbol}_2020-07-13.json").read_text("utf-8"))
    return float(payload["data"][0][4])


def _corrected_rows():
    rows = parse_bhavcopy(_cut(), FORMAT_ARCHIVE)
    assert {r.trade_date for r in rows} == {date(20, 7, 13)}, "the cut parses to the malformed year"
    result = data_quirks.correct_rows(DAY, FORMAT_ARCHIVE, rows)
    assert result is not None
    corrected, _reason = result
    return {r.symbol: r for r in corrected}


def test_tcs_corrected_close_matches_smartapi_to_the_paisa() -> None:
    """The adjustment-free leg: TCS has no intervening CA, so raw == SmartAPI ONE_DAY."""
    tcs = _corrected_rows()["TCS"]
    assert tcs.trade_date == DAY
    bhav_rupees = tcs.close_paise / 100.0
    smart = _smartapi_close("TCS")
    diff_pct = abs(bhav_rupees - smart) / smart * 100.0
    assert diff_pct < WITHIN, f"TCS {bhav_rupees} vs SmartAPI {smart} = {diff_pct:.4f}%"
    assert tcs.close_paise == 222000


def test_reliance_raw_differs_from_smartapi_by_the_known_adjustment() -> None:
    """RELIANCE differs because SmartAPI ONE_DAY is CA-back-adjusted (OPEN-8 evidence).

    Raw 1935.00 / SmartAPI 878.36 ~= 0.454, consistent with the 1:1 bonus (0.5) times the
    RELIANCE->Jio demerger (~0.908). The raw close is the genuine one (it chained to the store
    neighbours when it was ingested); this test PINS that the two feeds are NOT comparable
    raw-to-adjusted for a symbol with intervening corporate actions.
    """
    reliance = _corrected_rows()["RELIANCE"]
    assert reliance.close_paise == 193500, "the genuine raw close, 1935.00"
    raw = reliance.close_paise / 100.0
    smart = _smartapi_close("RELIANCE")
    ratio = smart / raw
    assert ratio < 0.6, "SmartAPI is deeply below raw -- it is back-adjusted, not raw"
    assert 0.44 < ratio < 0.47, "ratio ~ 0.454 = 1:1 bonus x Jio demerger"


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

    def get(self, url: str, timeout: float | None = None) -> Any:
        return self.answers.get(url, _Response(404))


def test_download_ingest_readback_roundtrip(tmp_path) -> None:
    """The whole pipe, offline: a stubbed session serves the malformed cut as a ZIP; the
    downloader quirk-corrects it; the store ingests it; daily() reads the corrected closes."""
    url = url_for(DAY, FORMAT_ARCHIVE)
    session = _StubSession({url: _Response(200, _zip_of("cm13JUL2020bhav.csv", _cut()))})

    download = download_bhavcopy(DAY, session=session, sleep=lambda _s: None, now=NOW)
    assert download.outcome.outcome == OUTCOME_PRESENT
    assert download.outcome.reason and "0020" in download.outcome.reason

    store = DailyStore.at(tmp_path)
    store.ingest(download)
    assert int(store.daily("TCS", DAY, DAY).iloc[0]["close_paise"]) == 222000
    assert int(store.daily("RELIANCE", DAY, DAY).iloc[0]["close_paise"]) == 193500
    # the ledger records the date as file-present, carrying the quirk provenance
    outcome = store.outcomes()[DAY]
    assert outcome.outcome == OUTCOME_PRESENT and "quirk" in (outcome.reason or "").lower()
