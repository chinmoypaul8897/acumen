"""Probes kept by the chunk-2 REVIEW session (docs/reviews/REVIEW_2.md).

These are the review's own tests, not the builder's. They exist because a review that only
re-runs the build's assertions grades the build with its own marking scheme. Four kinds live
here:

1. **Re-attacks on the two REVIEW_1 findings chunk 2 closed** -- the socket-level offline
   guard (F1) and the atomic write path (F2). A closed finding that nothing independently
   re-tests is a finding that can silently re-open.
2. **Independent recomputations.** The cross-source table is rebuilt here from the frozen
   `poc/data` CSVs and the DERIVED bhavcopy fixture with code that imports nothing from
   `acumen`, so the goldens are not graded by the module they test.
3. **Attacks past the fixtures** -- ledger semantics under resume, byte-idempotence over
   three passes and both bhavcopy eras, and the pacing actually observed on the wire.
4. **Two deliberate PINS of defects this review found** (REVIEW_2 Findings 1 and 2). Each is
   written to FAIL LOUDLY when the defect is fixed, and its message names the finding to
   close. A defect no test can see is how a fix silently regresses.

Everything is offline. Where a probe needs a network address it uses 192.0.2.1 (RFC 5737
TEST-NET-1, reserved for documentation and unroutable) or a closed loopback port, so nothing
here can reach a real host even if a guard were missing -- the chunk-1 review had to issue
real traffic to prove F1; proving the fix needs none.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import socket
import sys
import urllib.error
import urllib.request
import warnings
import zipfile
from datetime import date, datetime, time as clock_time, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock

import pytest
import requests

from acumen import bhavcopy, nse_http
from acumen.atomic_io import atomic_write_bytes, atomic_write_with
from acumen.bhavcopy import (
    FORMAT_ARCHIVE,
    FORMAT_UDIFF,
    OUTCOME_ERROR,
    OUTCOME_NOT_FOUND,
    OUTCOME_PRESENT,
    DateOutcome,
    Download,
    parse_bhavcopy,
    url_for,
)
from acumen.calendar import CalendarError, TradingCalendar, load_calendar
from acumen.daily_store import DailyStore, DailyStoreError

from conftest import NETWORK_GUARD_MESSAGE

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"
POC_DATA = REPO / "poc" / "data"
SCRIPT = REPO / "scripts" / "backfill_daily.py"

#: RFC 5737 TEST-NET-1: reserved for documentation, unroutable. Nothing can reach a real
#: host through it, so these probes are safe even if a guard were absent.
UNROUTABLE = "192.0.2.1"

POC_SYMBOLS = ("TCS", "RELIANCE", "HDFCBANK", "DIXON", "MANAPPURAM")
POC_DATES = tuple(date(2026, 7, d) for d in (14, 15, 16, 17, 20))
WINDOW_2026 = (date(2026, 7, 13), date(2026, 7, 24))
NOW = datetime(2026, 7, 24, 21, 0, 0)


# --- helpers ----------------------------------------------------------------------------


def _zip_of(text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("b.csv", text)
    return buffer.getvalue()


class _Response:
    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content


class _Recorder:
    """A stub session that records the fake-clock time of every outbound GET."""

    def __init__(self, answers: dict[str, Any], clock: list[float]) -> None:
        self.answers, self.clock = answers, clock
        self.log: list[tuple[float, str]] = []

    def get(self, url: str, timeout: float | None = None) -> Any:
        self.log.append((round(self.clock[0], 3), url))
        return self.answers.get(url, _Response(404))


def _download_on_a_fake_clock(
    answers: dict[str, Any], day: date, *, min_interval: float, max_attempts: int = 4
) -> tuple[Download, list[tuple[float, str]]]:
    """Run one download with a virtual clock, so the real spacing is observable."""
    clock = [1000.0]
    recorder = _Recorder(answers, clock)

    def advance(seconds: float) -> None:
        clock[0] += seconds

    previous = nse_http._last_request_at[0]
    nse_http._last_request_at[0] = -10_000.0
    try:
        with mock.patch.object(nse_http.time, "monotonic", lambda: clock[0]):
            result = bhavcopy.download_bhavcopy(
                day,
                session=recorder,
                sleep=advance,
                min_interval=min_interval,
                max_attempts=max_attempts,
                now=NOW,
            )
    finally:
        nse_http._last_request_at[0] = previous
    return result, recorder.log


def _gaps(log: list[tuple[float, str]]) -> list[float]:
    return [round(log[i + 1][0] - log[i][0], 3) for i in range(len(log) - 1)]


def _ingest_fixture(store: DailyStore, fixture: str, source_format: str) -> None:
    rows = parse_bhavcopy((FIXTURES / fixture).read_text(encoding="utf-8"), source_format)
    for day in sorted({row.trade_date for row in rows}):
        same_day = tuple(row for row in rows if row.trade_date == day)
        store.ingest(
            Download(
                DateOutcome(
                    trade_date=day,
                    outcome=OUTCOME_PRESENT,
                    source_format=source_format,
                    http_status=200,
                    row_count=len(same_day),
                    attempted_at=NOW,
                ),
                same_day,
            )
        )


@pytest.fixture()
def both_eras(tmp_path: Path) -> DailyStore:
    """A store holding both DERIVED bhavcopy fixtures -- UDiFF 2026 and archive 2018."""
    store = DailyStore.at(tmp_path / "store")
    _ingest_fixture(store, "bhavcopy_udiff_sample.csv", FORMAT_UDIFF)
    _ingest_fixture(store, "bhavcopy_archive_sample.csv", FORMAT_ARCHIVE)
    return store


def _minutes(symbol: str, day: date) -> list[dict[str, Any]]:
    """The frozen SmartAPI minutes, parsed HERE -- no acumen code on this path."""
    path = POC_DATA / f"{symbol}_{day.isoformat()}_1min.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    out = []
    for row in rows:
        stamp = datetime.fromisoformat(row["ts"]).replace(tzinfo=None)
        out.append(
            {
                "t": stamp.time(),
                "o": _exact_paise(row["open"]),
                "h": _exact_paise(row["high"]),
                "l": _exact_paise(row["low"]),
                "c": _exact_paise(row["close"]),
                "v": int(row["volume"]),
            }
        )
    return out


def _exact_paise(text: str) -> int:
    scaled = Decimal(text.strip()) * 100
    assert scaled == scaled.to_integral_value(), f"{text!r} is not a whole number of paise"
    return int(scaled)


def _bhav_rows_parsed_here() -> dict[tuple[str, date, str], dict[str, int]]:
    """The DERIVED UDiFF fixture, parsed with plain csv + Decimal (no acumen import)."""
    out: dict[tuple[str, date, str], dict[str, int]] = {}
    with (FIXTURES / "bhavcopy_udiff_sample.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (
                row["TckrSymb"].strip(),
                date.fromisoformat(row["TradDt"].strip()),
                row["SctySrs"].strip(),
            )
            out[key] = {
                "open": _exact_paise(row["OpnPric"]),
                "high": _exact_paise(row["HghPric"]),
                "low": _exact_paise(row["LwPric"]),
                "close": _exact_paise(row["ClsPric"]),
                "last": _exact_paise(row["LastPric"]),
                "volume": int(row["TtlTradgVol"]),
                "turnover": _exact_paise(row["TtlTrfVal"]),
            }
    return out


def _summary_rows() -> dict[tuple[str, date], dict[str, int]]:
    with (POC_DATA / "volume_poc_summary.csv").open(encoding="utf-8", newline="") as handle:
        return {
            (row["symbol"], date.fromisoformat(row["date"])): {
                "daily_vol": int(float(row["daily_vol"])),
                "sum_1min_vol": int(float(row["sum_1min_vol"])),
            }
            for row in csv.DictReader(handle)
        }


# =========================================================================================
# 1. The socket-level offline guard, re-attacked (REVIEW_1 Finding 1, closed by chunk 2)
# =========================================================================================


def test_the_guard_blocks_a_raw_socket_connect() -> None:
    """The exact attack that walked past the chunk-1 guard, re-run against the new one."""
    with pytest.raises(AssertionError, match=NETWORK_GUARD_MESSAGE):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((UNROUTABLE, 443))


def test_the_guard_blocks_connect_ex_and_create_connection() -> None:
    """connect_ex returns an errno instead of raising, so a guard that misses it is silent."""
    with pytest.raises(AssertionError, match=NETWORK_GUARD_MESSAGE):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex((UNROUTABLE, 443))
    with pytest.raises(AssertionError, match=NETWORK_GUARD_MESSAGE):
        socket.create_connection((UNROUTABLE, 443), timeout=0.1)


def test_the_guard_blocks_urllib() -> None:
    """The second attack that walked past the chunk-1 guard."""
    with pytest.raises(AssertionError, match=NETWORK_GUARD_MESSAGE):
        urllib.request.urlopen(f"http://{UNROUTABLE}/anything", timeout=0.1)


def test_the_guard_blocks_pandas_read_csv_from_a_url() -> None:
    """conftest names this case by name: chunk 2 is the chunk that reads CSVs off the web."""
    import pandas as pd

    with pytest.raises(BaseException) as excinfo:
        pd.read_csv(f"http://{UNROUTABLE}/bhav.csv")
    chain, error = [], excinfo.value
    while error is not None:
        chain.append(str(error))
        error = error.__cause__ or error.__context__
    assert any(NETWORK_GUARD_MESSAGE in text for text in chain), chain


@pytest.mark.parametrize(
    "call",
    [
        lambda: requests.get(f"http://{UNROUTABLE}/x"),
        lambda: requests.post(f"http://{UNROUTABLE}/x"),
        lambda: requests.Session().get(f"http://{UNROUTABLE}/x"),
        lambda: requests.Session().request("GET", f"http://{UNROUTABLE}/x"),
        lambda: nse_http.fetch_json(f"http://{UNROUTABLE}/x", sleep=lambda _s: None),
        lambda: nse_http.fetch_binary(f"http://{UNROUTABLE}/x", sleep=lambda _s: None),
    ],
    ids=["get", "post", "session-get", "session-request", "fetch_json", "fetch_binary"],
)
def test_the_guard_still_trips_on_every_requests_entry_point(call: Any) -> None:
    """The chunk-1 patches are kept on top of the socket block; both layers must hold.

    `fetch_binary` is chunk 2's new one -- the download path must be as sealed as the JSON
    path it was modelled on.
    """
    with pytest.raises(AssertionError, match=NETWORK_GUARD_MESSAGE):
        call()


def test_a_closed_local_port_is_blocked_too_so_the_guard_is_not_host_specific() -> None:
    """The guard must be a rule about connecting, not a blocklist of NSE's hostnames."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()
    with pytest.raises(AssertionError, match=NETWORK_GUARD_MESSAGE):
        socket.create_connection(("127.0.0.1", port), timeout=0.1)


# =========================================================================================
# 2. Atomic writes, crash-tested (REVIEW_1 Finding 2, closed by chunk 2)
# =========================================================================================


@pytest.mark.parametrize(
    "interrupt", [KeyboardInterrupt, SystemExit, MemoryError], ids=["ctrl-c", "sysexit", "oom"]
)
def test_an_interrupted_write_leaves_the_previous_file_and_no_orphan_temp(
    tmp_path: Path, interrupt: type[BaseException]
) -> None:
    """A Ctrl-C mid-write is the scenario atomic_io exists for; the operator is TOLD the
    hours-long backfill is interruptible, so this must hold for BaseException, not just
    Exception."""
    target = tmp_path / "sub" / "store.parquet"
    atomic_write_bytes(target, b"GOOD-ORIGINAL")

    def half_write_then_die(temp: Path) -> None:
        temp.write_bytes(b"HALF-WRITTEN-GARBAGE")
        raise interrupt()

    with pytest.raises(interrupt):
        atomic_write_with(target, half_write_then_die)

    assert target.read_bytes() == b"GOOD-ORIGINAL"
    assert sorted(p.name for p in target.parent.iterdir()) == ["store.parquet"]


def test_an_interrupt_inside_os_replace_itself_still_cleans_up(tmp_path: Path) -> None:
    """The narrowest window there is: the temp file is complete, the rename is not."""
    target = tmp_path / "store.parquet"
    atomic_write_bytes(target, b"GOOD-ORIGINAL")
    with mock.patch("acumen.atomic_io.os.replace", side_effect=KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            atomic_write_bytes(target, b"NEW")
    assert target.read_bytes() == b"GOOD-ORIGINAL"
    assert sorted(p.name for p in target.parent.iterdir()) == ["store.parquet"]


def test_a_damaged_cache_is_repaired_only_by_an_explicit_network_opt_in(
    tmp_path: Path,
) -> None:
    """REVIEW_1 F2's second half: the read path stays loud, and allow_network=True is the
    only way out -- with a warning, so the repair is never silent."""
    cache = tmp_path / "nse" / "holiday.json"
    nse_http.write_cache(cache, {"CM": ["good"]}, url="https://x/y", fetched_on=date(2026, 7, 24))
    whole = cache.read_bytes()
    cache.write_bytes(whole[: len(whole) // 2])

    with pytest.raises(nse_http.NseFetchError, match="unreadable or not valid JSON"):
        nse_http.cached_json("https://x/y", cache, today=date(2026, 7, 24), allow_network=False)

    with mock.patch.object(nse_http, "cached_json_fetch", return_value={"CM": ["repaired"]}):
        with pytest.warns(RuntimeWarning, match="Replacing a damaged day-cache"):
            payload = nse_http.cached_json(
                "https://x/y", cache, today=date(2026, 7, 24), allow_network=True
            )
    assert payload == {"CM": ["repaired"]}
    assert nse_http.read_cache(cache) == (date(2026, 7, 24), {"CM": ["repaired"]})
    assert [p.name for p in cache.parent.iterdir() if p.name.endswith(".tmp")] == []


def test_an_interrupted_ingest_leaves_the_store_consistent_and_the_date_pending(
    tmp_path: Path,
) -> None:
    """The write order is what makes resume safe: PRICES first, LEDGER second.

    A crash between them re-does the date on the next run. The other order would settle a
    date whose rows never landed, and nothing downstream would ever look again.
    """
    store = DailyStore.at(tmp_path / "store")
    rows = parse_bhavcopy(
        (FIXTURES / "bhavcopy_udiff_sample.csv").read_text(encoding="utf-8"), FORMAT_UDIFF
    )
    settled, interrupted = date(2026, 7, 20), date(2026, 7, 17)
    for day in (settled,):
        same = tuple(r for r in rows if r.trade_date == day)
        store.ingest(
            Download(
                DateOutcome(
                    trade_date=day,
                    outcome=OUTCOME_PRESENT,
                    source_format=FORMAT_UDIFF,
                    http_status=200,
                    row_count=len(same),
                    attempted_at=NOW,
                ),
                same,
            )
        )
    before = store.month_path(settled).read_bytes()

    same = tuple(r for r in rows if r.trade_date == interrupted)
    with mock.patch("acumen.daily_store.pq.write_table", side_effect=KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            store.ingest(
                Download(
                    DateOutcome(
                        trade_date=interrupted,
                        outcome=OUTCOME_PRESENT,
                        source_format=FORMAT_UDIFF,
                        http_status=200,
                        row_count=len(same),
                        attempted_at=NOW,
                    ),
                    same,
                )
            )

    assert store.month_path(settled).read_bytes() == before
    assert [p.name for p in store.root.rglob("*") if p.name.endswith(".tmp")] == []
    assert sorted(store.outcomes()) == [settled]
    assert interrupted in store.pending_dates(*WINDOW_2026)

    # The order itself, isolated: if only the ROW write fails, the ledger must still be
    # untouched. Recording the outcome first would settle a date whose prices never landed,
    # and `pending_dates` would never offer it again -- a permanent silent hole.
    with mock.patch.object(
        DailyStore, "write_rows", side_effect=KeyboardInterrupt, autospec=True
    ):
        with pytest.raises(KeyboardInterrupt):
            store.ingest(
                Download(
                    DateOutcome(
                        trade_date=interrupted,
                        outcome=OUTCOME_PRESENT,
                        source_format=FORMAT_UDIFF,
                        http_status=200,
                        row_count=len(same),
                        attempted_at=NOW,
                    ),
                    same,
                )
            )
    assert interrupted not in store.outcomes(), "the ledger settled a date with no rows"
    assert interrupted in store.pending_dates(*WINDOW_2026)


# =========================================================================================
# 3. Ledger semantics under resume (Q-3 safeguard 1)
# =========================================================================================


def test_confirmed_404_requires_both_formats_to_answer_404(tmp_path: Path) -> None:
    """B19, attacked from the other side: if the SECOND format answers, the date is a
    trading day and must never be recorded as absent."""
    day = date(2026, 7, 20)
    archive_text = (FIXTURES / "bhavcopy_archive_sample.csv").read_text(encoding="utf-8")
    lines = archive_text.splitlines()
    relabelled = "\n".join(
        [lines[0]]
        + [ln.replace("01-JAN-2018", "20-JUL-2026") for ln in lines[1:] if ",01-JAN-2018," in ln]
    )
    session = _Recorder(
        {url_for(day, FORMAT_ARCHIVE): _Response(200, _zip_of(relabelled))}, [0.0]
    )
    result = bhavcopy.download_bhavcopy(day, session=session, sleep=lambda _s: None, now=NOW)
    assert result.outcome.outcome == OUTCOME_PRESENT
    assert result.outcome.source_format == FORMAT_ARCHIVE
    assert [url for _t, url in session.log] == [
        url_for(day, FORMAT_UDIFF),
        url_for(day, FORMAT_ARCHIVE),
    ]


@pytest.mark.parametrize("status", [403, 429, 500, 502, 503, 504])
def test_no_retryable_status_can_ever_settle_a_date(tmp_path: Path, status: int) -> None:
    """Every status CONTEXT 4.3 calls transient must end as `error`, never as a holiday."""
    day = date(2026, 7, 20)
    session = _Recorder({url_for(day, FORMAT_UDIFF): _Response(status)}, [0.0])
    result = bhavcopy.download_bhavcopy(
        day, session=session, sleep=lambda _s: None, max_attempts=2, now=NOW
    )
    assert result.outcome.outcome == OUTCOME_ERROR
    assert result.outcome.is_terminal is False

    store = DailyStore.at(tmp_path / f"s{status}")
    store.ingest(result)
    assert day in store.pending_dates(day, day)
    with pytest.raises(CalendarError, match="unsettled"):
        TradingCalendar.from_daily_store_range(store, day, day)


def test_an_error_date_is_re_attempted_and_only_fresh_evidence_settles_it(
    tmp_path: Path,
) -> None:
    """The resume story end to end: error -> retried -> settled by what the SERVER says.

    An error becoming confirmed-404 later is correct only because BOTH formats answered 404
    on the retry; nothing in the store may promote an error on its own.
    """
    store = DailyStore.at(tmp_path / "store")
    day = date(2026, 7, 18)
    store.record_outcome(DateOutcome(trade_date=day, outcome=OUTCOME_ERROR, reason="HTTP 503"))
    assert store.pending_dates(day, day) == (day,)

    session = _Recorder({}, [0.0])  # a real Saturday: everything 404s
    store.ingest(bhavcopy.download_bhavcopy(day, session=session, sleep=lambda _s: None, now=NOW))

    assert store.outcomes()[day].outcome == OUTCOME_NOT_FOUND
    assert len(session.log) == 2, "both formats were asked before the date was settled"
    assert store.pending_dates(day, day) == ()


def test_a_settled_date_is_never_re_fetched_on_resume(tmp_path: Path) -> None:
    store = DailyStore.at(tmp_path / "store")
    store.record_outcomes(
        [
            DateOutcome(trade_date=date(2026, 7, 20), outcome=OUTCOME_PRESENT),
            DateOutcome(trade_date=date(2026, 7, 19), outcome=OUTCOME_NOT_FOUND),
            DateOutcome(trade_date=date(2026, 7, 18), outcome=OUTCOME_ERROR),
        ]
    )
    assert store.pending_dates(date(2026, 7, 18), date(2026, 7, 20)) == (date(2026, 7, 18),)


# =========================================================================================
# 4. Idempotence, over three passes and both eras
# =========================================================================================


def test_three_re_ingest_passes_are_byte_identical_in_both_eras(both_eras: DailyStore) -> None:
    """The card's "re-run is idempotent (no dupes)", taken past "no dupes" to "no new bytes".

    Byte-identity is the stronger claim and the operator-relevant one: a re-run that
    rewrites files would defeat any backup or sync the operator puts around the store.
    """
    def digests() -> dict[str, str]:
        return {
            path.relative_to(both_eras.root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(both_eras.root.rglob("*.parquet"))
        }

    first = digests()
    assert set(first) == {
        "daily/2018/bhavcopy_2018-01.parquet",
        "daily/2026/bhavcopy_2026-07.parquet",
        "ledger.parquet",
    }
    rows_before = len(both_eras.frame(None, date(2000, 1, 1), date(2030, 1, 1)))

    for _ in range(2):
        _ingest_fixture(both_eras, "bhavcopy_udiff_sample.csv", FORMAT_UDIFF)
        _ingest_fixture(both_eras, "bhavcopy_archive_sample.csv", FORMAT_ARCHIVE)
        assert digests() == first

    assert len(both_eras.frame(None, date(2000, 1, 1), date(2030, 1, 1))) == rows_before
    assert [p.name for p in both_eras.root.rglob("*") if p.name.endswith(".tmp")] == []


# =========================================================================================
# 5. The price path: Decimal on text, integer paise, no float anywhere
# =========================================================================================


def test_no_column_that_can_hold_a_price_comes_back_as_a_float(both_eras: DailyStore) -> None:
    """CONTEXT 7-E11. A float64 turnover in paise loses exactness above 2^53."""
    frame = both_eras.frame(None, date(2000, 1, 1), date(2030, 1, 1))
    assert not any("float" in str(dtype) for dtype in frame.dtypes)
    for column in (
        "open_paise",
        "high_paise",
        "low_paise",
        "close_paise",
        "last_paise",
        "prev_close_paise",
        "turnover_paise",
        "volume",
        "trades",
    ):
        assert str(frame[column].dtype) == "Int64", column
    assert isinstance(frame["trade_date"].iloc[0], date)


def test_a_price_a_float_would_corrupt_survives_the_whole_pipe(both_eras: DailyStore) -> None:
    """RECORDS REVIEW_2 FINDING 4: decision B24 is right, but its cited example is not.

    `float("2251.10") * 100` is exactly 225110.0 in IEEE-754 double arithmetic, so the
    example repeated in bhavcopy.py's module docstring, in `_paise`, in a build test and in
    PROGRESS B24 does NOT demonstrate the hazard it is quoted for. The hazard is real
    anyway, and this test uses a case measured from THIS fixture instead: TCS closed at
    2189.20 on 2026-07-15, where a float path silently loses a paisa. Ten of the fixture's
    217 printed values behave this way.
    """
    assert int(float("2251.10") * 100) == 225110, "the quoted example does not round-trip badly"

    row = both_eras.daily("TCS", date(2026, 7, 15), date(2026, 7, 15)).iloc[0]
    assert int(row.close_paise) == 218920, "the exact paise, via Decimal on the CSV text"
    assert int(float("2189.20") * 100) == 218919, "a float path would have lost a paisa here"

    twenty = both_eras.daily("TCS", date(2026, 7, 20), date(2026, 7, 20)).iloc[0]
    assert int(twenty.close_paise) == 225110
    assert int(twenty.turnover_paise) == 497162363920
    assert int(twenty.volume) == 2202693


def test_a_sub_paisa_price_is_refused_rather_than_rounded_in_both_formats() -> None:
    """Refusing is the only honest option: rounding would be a silent price change."""
    udiff = (
        "TradDt,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol\n"
        "2026-07-20,TCS,EQ,100.005,101,99,100,1\n"
    )
    archive = (
        "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,\n"
        "TCS,EQ,100,101,99,99.999,100,100,1,100,01-JAN-2018,\n"
    )
    for text, fmt in ((udiff, FORMAT_UDIFF), (archive, FORMAT_ARCHIVE)):
        with pytest.raises(bhavcopy.BhavcopyError, match="not a whole number of paise"):
            parse_bhavcopy(text, fmt)


# =========================================================================================
# 6. Cross-source, recomputed independently of the acumen parser
# =========================================================================================


def test_cross_source_open_high_low_and_volume_recomputed_without_acumen() -> None:
    """25 symbol-days rebuilt here from the frozen CSVs with plain csv + Decimal.

    The builder's golden asserts the same equalities through `parse_bhavcopy` and the
    Parquet round trip. This one shares no code with it, so agreement means the DATA agrees,
    not that one implementation is self-consistent.
    """
    bhav, summary = _bhav_rows_parsed_here(), _summary_rows()
    checked = 0
    for symbol in POC_SYMBOLS:
        for day in POC_DATES:
            row = bhav[(symbol, day, "EQ")]
            candles = _minutes(symbol, day)
            assert len(candles) == 375, f"{symbol} {day}"
            assert row["open"] == candles[0]["o"], f"{symbol} {day} open"
            assert row["high"] == max(c["h"] for c in candles), f"{symbol} {day} high"
            assert row["low"] == min(c["l"] for c in candles), f"{symbol} {day} low"
            assert row["volume"] == summary[(symbol, day)]["daily_vol"], f"{symbol} {day} vol"
            assert sum(c["v"] for c in candles) == summary[(symbol, day)]["sum_1min_vol"]
            checked += 1
    assert checked == 25


def test_the_daily_close_is_not_the_last_traded_price_but_lastpric_is() -> None:
    """B34's premise, measured -- and the sharper assertion it left on the table.

    Across the 25 frozen symbol-days the bhavcopy `ClsPric` equals the final 1-minute close
    on only ONE, while `LastPric` equals it on all 25. So refusing to compare the daily
    CLOSE to the 1-minute series is right, and the LTP field is the one that IS comparable
    exactly. This pins the frozen fixture, not a universal law about NSE.
    """
    bhav = _bhav_rows_parsed_here()
    last_matches = close_matches = 0
    for symbol in POC_SYMBOLS:
        for day in POC_DATES:
            row = bhav[(symbol, day, "EQ")]
            final_close = _minutes(symbol, day)[-1]["c"]
            last_matches += row["last"] == final_close
            close_matches += row["close"] == final_close
    assert last_matches == 25, "LastPric IS the last traded price of the 1-minute series"
    assert close_matches == 1, "ClsPric is a different quantity and must not be equated"


def test_the_close_lies_inside_the_closing_half_hour_range() -> None:
    """The invariant that follows from NSE's definition (last-30-minute weighted average).

    Recomputed here, and stated as what it is: a VWAP over 15:00-15:29 must sit inside that
    window's traded range. It is asserted only over five liquid symbols -- on an illiquid
    symbol-day with no trades in the last half hour NSE falls back to the last traded price,
    which need not satisfy it. Chunk 5A's gate should not assume this holds universally.
    """
    bhav = _bhav_rows_parsed_here()
    for symbol in POC_SYMBOLS:
        for day in POC_DATES:
            tail = [c for c in _minutes(symbol, day) if c["t"] >= clock_time(15, 0)]
            assert len(tail) == 30, f"{symbol} {day}"
            low, high = min(c["l"] for c in tail), max(c["h"] for c in tail)
            assert low <= bhav[(symbol, day, "EQ")]["close"] <= high, f"{symbol} {day}"


def test_the_tcs_golden_row_matches_results_md_read_from_the_document(
    both_eras: DailyStore,
) -> None:
    """docs/RESULTS.md is the source of the card's golden, so it is READ, not restated."""
    text = (REPO / "docs" / "RESULTS.md").read_text(encoding="utf-8")
    assert "2026-07-20 close 2251.1, vol 2,202,693" in text, "RESULTS.md section A changed"
    row = both_eras.daily("TCS", date(2026, 7, 20), date(2026, 7, 20)).iloc[0]
    assert int(row.close_paise) == _exact_paise("2251.1")
    assert int(row.volume) == 2202693


# =========================================================================================
# 7. The derived calendar (Q-3), recomputed from the ledger fixture
# =========================================================================================


def _ledger_fixture_rows() -> list[DateOutcome]:
    with (FIXTURES / "daily_ledger_window.csv").open(encoding="utf-8", newline="") as handle:
        return [
            DateOutcome(
                trade_date=date.fromisoformat(row["trade_date"]),
                outcome=row["outcome"],
                source_format=row["source_format"] or None,
                http_status=int(row["http_status"]),
            )
            for row in csv.DictReader(handle)
        ]


@pytest.fixture()
def ledgered(tmp_path: Path) -> DailyStore:
    store = DailyStore.at(tmp_path / "ledger_store")
    store.record_outcomes(_ledger_fixture_rows())
    return store


def test_the_derived_days_match_a_second_derivation_written_here(ledgered: DailyStore) -> None:
    """Safeguard 2 with a third opinion: the ledger CSV is walked here directly.

    Both windows, not just the 2026 one the published snapshot can cross-check -- the 2018
    window has no published calendar in the repo, so this is the only independent read of it.
    """
    expected_2026 = [
        date.fromisoformat(row["trade_date"])
        for row in csv.DictReader(
            (FIXTURES / "daily_ledger_window.csv").open(encoding="utf-8", newline="")
        )
        if row["outcome"] == "file-present" and row["trade_date"].startswith("2026")
    ]
    calendar = TradingCalendar.from_daily_store_range(ledgered, *WINDOW_2026)
    got, current = [], WINDOW_2026[0]
    while current <= WINDOW_2026[1]:
        if calendar.is_trading_day(current):
            got.append(current)
        current += timedelta(days=1)
    assert got == expected_2026
    assert got == [date(2026, 7, d) for d in (13, 14, 15, 16, 17, 20, 21, 22, 23, 24)]

    old = TradingCalendar.from_daily_store_range(ledgered, date(2018, 1, 1), date(2018, 1, 15))
    old_days, current = [], date(2018, 1, 1)
    while current <= date(2018, 1, 15):
        if old.is_trading_day(current):
            old_days.append(current)
        current += timedelta(days=1)
    # Independent check on the 2018 half: January 2018 carried no NSE holiday before the 26th,
    # so the derived set must be exactly its weekdays -- a rule the ledger never saw.
    assert old_days == [
        date(2018, 1, d) for d in range(1, 16) if date(2018, 1, d).weekday() < 5
    ]


def test_the_two_calendars_agree_on_every_bias_pair_in_the_window(ledgered: DailyStore) -> None:
    """Not only the three days the builder's golden samples: every trading day whose pair
    stays inside the window."""
    derived = TradingCalendar.from_daily_store_range(ledgered, *WINDOW_2026)
    published = load_calendar(FIXTURES / "holidays_2026.json")
    compared = 0
    for offset in range((WINDOW_2026[1] - WINDOW_2026[0]).days + 1):
        day = WINDOW_2026[0] + timedelta(days=offset)
        if not published.is_trading_day(day):
            continue
        try:
            pair = derived.bias_pair(day)
        except CalendarError:
            continue  # the pair leaves the ingested window; refusing is the correct answer
        assert pair == published.bias_pair(day), day
        compared += 1
    assert compared >= 8, f"only {compared} pairs were actually comparable"


def test_the_derived_calendar_refuses_the_edge_of_its_own_window(ledgered: DailyStore) -> None:
    """The first covered day has no pair inside the evidence, and saying so is the point."""
    derived = TradingCalendar.from_daily_store_range(ledgered, *WINDOW_2026)
    with pytest.raises(CalendarError, match="no evidence for"):
        derived.bias_pair(WINDOW_2026[0])


def test_a_weekend_session_is_surfaced_and_no_longer_moves_the_following_monday(
    tmp_path: Path,
) -> None:
    """Q-5 RULED AND EXECUTED. This probe measured the open question; it now measures the fix.

    The consequence it was written to expose -- a Budget Saturday moving Monday's CONTEXT 3.2
    pair by a whole candle -- is what the architect's ruling removes: the weekend session is
    excluded as a non-standard session (CONTEXT 7-E2), stays surfaced, and Monday pairs to
    Friday/Thursday. The counterpart regression test lives with the calendar's own suite.
    """
    store = DailyStore.at(tmp_path / "store")
    saturday = date(2019, 6, 1)
    rows, current = [], date(2019, 1, 1)
    while current.year == 2019:
        traded = current.weekday() < 5 or current == saturday
        rows.append(
            DateOutcome(
                trade_date=current,
                outcome=OUTCOME_PRESENT if traded else OUTCOME_NOT_FOUND,
            )
        )
        current += timedelta(days=1)
    store.record_outcomes(rows)

    calendar = TradingCalendar.from_daily_store(store, [2019])
    assert calendar.weekend_sessions == (saturday,), "surfaced"
    assert calendar.is_trading_day(saturday) is False, "and excluded"
    assert calendar.excluded_session_counts() == {"weekend-session": 1}, "and counted"
    assert calendar.bias_pair(date(2019, 6, 3)) == (date(2019, 5, 31), date(2019, 5, 30))
    # The pre-ruling behaviour, for the record: this was (2019-06-01, 2019-05-31).
    assert saturday not in calendar.bias_pair(date(2019, 6, 3))


def test_a_published_calendar_is_bit_identical_to_chunk_1(tmp_path: Path) -> None:
    """Chunk 1 is reviewed-PASS. The two new optional fields must not have moved it."""
    published = load_calendar(FIXTURES / "holidays_2026.json")
    assert published.trading_days is None and published.covered_days is None
    assert published.source == "published"
    assert published.weekend_sessions == ()
    assert len([d for d in _all_2026() if published.is_trading_day(d)]) == 245


def _all_2026() -> list[date]:
    days, current = [], date(2026, 1, 1)
    while current.year == 2026:
        days.append(current)
        current += timedelta(days=1)
    return days


# =========================================================================================
# 8. Q-4: the series ambiguity, reproduced on the 2018 data
# =========================================================================================


def test_the_2018_multi_series_ambiguity_is_real_in_both_formats(both_eras: DailyStore) -> None:
    """Q-4's evidence, re-measured from the frozen fixtures rather than taken on trust."""
    frame = both_eras.frame(["NTPC"], date(2018, 1, 1), date(2018, 1, 1))
    assert sorted(frame["series"]) == ["EQ", "N4", "N6", "N7", "NB", "NC"]
    assert sorted(
        both_eras.frame(["JSWSTEEL"], date(2018, 1, 1), date(2018, 1, 1))["series"]
    ) == ["EQ", "P2"]
    assert sorted(
        both_eras.frame(["BIOCON"], date(2026, 7, 14), date(2026, 7, 14))["series"]
    ) == ["BL", "EQ"]


def test_q4_the_ruling_picks_the_equity_row_out_of_six_series(both_eras: DailyStore) -> None:
    """QUESTIONS.md Q-4 EXECUTED, measured on the six-series NTPC case this review found.

    Before the ruling `daily()` refused to choose (correct while the question was open).
    Now it selects the whitelist row and ignores the five debt series, and the explicit
    `series=` escape still answers exactly as it did.
    """
    picked = both_eras.daily("NTPC", date(2018, 1, 1), date(2018, 1, 2))
    assert list(picked["trade_date"]) == [date(2018, 1, 1), date(2018, 1, 2)]
    assert set(picked["series"]) == {"EQ"}

    explicit = both_eras.daily("NTPC", date(2018, 1, 1), date(2018, 1, 2), series="N4")
    assert set(explicit["series"]) == {"N4"}, "the escape hatch is unchanged"

    biocon = both_eras.daily("BIOCON", date(2026, 7, 14), date(2026, 7, 14))
    assert len(biocon) == 1 and biocon.iloc[0].series == "EQ", "the block-deal row is ignored"


def test_q4_a_debt_only_symbol_answers_empty_rather_than_with_a_debenture(
    both_eras: DailyStore,
) -> None:
    """The ruling's most dangerous clause, and the reason a volume rule would have failed.

    IRFC listed debt long before its equity. "No whitelist series -> the equity did not
    exist/trade that day: empty result, not an error." A "largest volume wins" rule would
    have handed chunk 4 a debenture's price series instead.
    """
    frame = both_eras.frame(["IRFC"], date(2018, 1, 1), date(2018, 1, 2))
    if not frame.empty:  # the DERIVED fixture may or may not carry IRFC's rows
        assert set(frame["series"]).isdisjoint({"EQ", "BE", "BZ"})
    daily = both_eras.daily("IRFC", date(2018, 1, 1), date(2018, 1, 2))
    assert daily.empty
    assert list(daily.columns) == list(both_eras.frame(None, date(2018, 1, 1), date(2018, 1, 1)).columns)


def test_the_only_series_choice_in_src_is_the_q4_whitelist() -> None:
    """The ruling licenses ONE choice; `src/` may not grow a second one somewhere else.

    Parsed rather than grepped: a docstring naming "EQ" as an example argument reads the same
    to a grep as a default does. An `ast` walk for the string constants of the whitelist can
    tell them apart, and it pins them to the single constant that cites the ruling.
    """
    import ast

    offenders = []
    for source in sorted((REPO / "src").rglob("*.py")) + sorted((REPO / "scripts").rglob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value in ("EQ", "BE", "BZ"):
                offenders.append(f"{source.relative_to(REPO)}:{node.lineno}")
    files = {entry.rsplit(":", 1)[0].replace("\\", "/") for entry in offenders}
    assert files == {"src/acumen/daily_store.py"}, offenders
    assert len(offenders) == 3, "exactly the three members of INSTRUMENT_SERIES"

    from acumen.daily_store import INSTRUMENT_SERIES

    assert INSTRUMENT_SERIES == ("EQ", "BE", "BZ")


# =========================================================================================
# 9. The backfill script
# =========================================================================================


@pytest.fixture(scope="module")
def backfill() -> ModuleType:
    from acumen import backfill_daily

    return backfill_daily


def test_importing_either_entry_point_runs_nothing(backfill: ModuleType) -> None:
    """CLOSES REVIEW_2 FINDING 12's import-time half.

    An entry point that did work on import could not be tested, and would be a hazard the
    moment anything imported it. Checked structurally on BOTH files: the packaged module
    (`src/acumen/backfill_daily.py`, where the implementation now lives) and the launcher
    (`scripts/backfill_daily.py`) may each hold only a docstring, imports, definitions and
    the `if __name__` guard -- ZERO executed statements. The launcher's `sys.path` insert
    moved inside a function that only `__main__` calls, and only fires when the package is
    genuinely not installed; the console entry point in pyproject.toml is the installed path.
    """
    import ast

    assert backfill.__name__ == "acumen.backfill_daily"
    assert hasattr(backfill, "main") and hasattr(backfill, "run")

    for path in (REPO / "src" / "acumen" / "backfill_daily.py", SCRIPT):
        body = ast.parse(path.read_text(encoding="utf-8")).body
        executed = [
            node
            for node in body
            if not isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.If))
            and not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
        ]
        assert executed == [], (path.name, [ast.dump(n)[:60] for n in executed])
        guards = [node for node in body if isinstance(node, ast.If)]
        assert len(guards) == 1 and "__main__" in ast.unparse(guards[0].test), path.name

    assert "sys.path.insert" not in ast.unparse(
        ast.parse((REPO / "src" / "acumen" / "backfill_daily.py").read_text(encoding="utf-8"))
    )
    assert 'acumen-backfill = "acumen.backfill_daily:main"' in (
        REPO / "pyproject.toml"
    ).read_text(encoding="utf-8")


def test_a_dry_run_opens_no_session_at_all(
    backfill: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """"--dry-run fetches nothing" proved at the session boundary, not only at the socket:
    the run must never even construct the HTTP session."""
    with mock.patch.object(nse_http, "new_session", side_effect=AssertionError("built a session")):
        code = backfill.run(
            backfill.parse_args(
                [
                    "--from", "2026-07-13", "--to", "2026-07-24",
                    "--store", str(tmp_path / "s"),
                    "--allow-network", "--dry-run",
                ]
            )
        )
    assert code == 0
    assert "STOPPING (--dry-run)" in capsys.readouterr().out
    assert not (tmp_path / "s").exists()


def test_without_the_flag_the_run_is_a_dry_run_too(
    backfill: ModuleType, tmp_path: Path
) -> None:
    with mock.patch.object(nse_http, "new_session", side_effect=AssertionError("built a session")):
        assert backfill.run(
            backfill.parse_args(
                ["--from", "2026-07-13", "--to", "2026-07-24", "--store", str(tmp_path / "s")]
            )
        ) == 0


def test_the_default_pacing_is_the_cards_number_and_is_not_silently_overridable(
    backfill: ModuleType,
) -> None:
    args = backfill.parse_args(["--from", "2026-07-13", "--to", "2026-07-13"])
    assert args.min_interval == bhavcopy.MIN_SECONDS_BETWEEN_REQUESTS == 2.0


def test_a_resumed_run_asks_only_for_the_unsettled_dates(
    backfill: ModuleType, tmp_path: Path
) -> None:
    store = DailyStore.at(tmp_path / "store")
    store.record_outcomes(
        [
            DateOutcome(trade_date=date(2026, 7, 13), outcome=OUTCOME_PRESENT),
            DateOutcome(trade_date=date(2026, 7, 14), outcome=OUTCOME_ERROR),
            DateOutcome(trade_date=date(2026, 7, 18), outcome=OUTCOME_NOT_FOUND),
        ]
    )
    assert backfill.resolve_dates(
        store, date(2026, 7, 13), date(2026, 7, 18), retry_errors=True
    ) == [date(2026, 7, d) for d in (14, 15, 16, 17)]
    assert backfill.resolve_dates(
        store, date(2026, 7, 13), date(2026, 7, 18), retry_errors=False
    ) == [date(2026, 7, d) for d in (15, 16, 17)]


# =========================================================================================
# 10. Pacing on the wire, and two PINNED defects (REVIEW_2 Findings 1 and 2)
# =========================================================================================


def test_the_normal_download_path_never_exceeds_one_request_per_two_seconds() -> None:
    """The chunk-2 card's politeness rule, measured on a virtual clock rather than asserted."""
    _result, log = _download_on_a_fake_clock({}, date(2026, 7, 19), min_interval=2.0)
    assert len(log) == 2
    assert all(gap >= 2.0 for gap in _gaps(log)), _gaps(log)


def test_the_cookie_warm_up_honors_the_callers_pacing() -> None:
    """CLOSES REVIEW_2 FINDING 1 (the pin it replaces asserted the wrong 0.5s spacing).

    `_warm_up_cookies` used to call `_throttle(sleep)` without the caller's `min_interval`,
    so on the download path (2.0s) the warm-up landed 0.5s after the request NSE had just
    refused -- a 4x rate spike aimed at a server already saying no. It now threads
    `min_interval` through, so every gap on the wire obeys the card's one-request-per-two-
    seconds rule, including the warm-up.
    """
    answers = {
        nse_http.NSE_HOME_URL: _Response(403),
        url_for(date(2026, 7, 20), FORMAT_UDIFF): _Response(403),
    }
    _result, log = _download_on_a_fake_clock(
        answers, date(2026, 7, 20), min_interval=2.0, max_attempts=2
    )
    assert [url for _t, url in log][1] == nse_http.NSE_HOME_URL
    assert all(gap >= 2.0 for gap in _gaps(log)), _gaps(log)


def test_a_bot_shield_page_behind_http_200_is_retried_on_downloads_too() -> None:
    """CLOSES REVIEW_2 FINDING 2 (the pin it replaces asserted the single-attempt defect).

    `fetch_json` treats an HTTP 200 whose body is unusable as transient and retries it. The
    download path now applies the SAME policy to NSE's bot-shield HTML, so both paths spend
    their full retry budget on the burst CONTEXT 4.3 calls NORMAL instead of one giving up
    immediately. Decision B31's claim -- one loop, so the policy cannot drift between the
    two paths -- is now true of the policy as well as of the loop.
    """
    day = date(2026, 7, 20)
    html = b"<!DOCTYPE html><html>Access Denied</html>"
    binary = _Recorder({url_for(day, FORMAT_UDIFF): _Response(200, html)}, [0.0])
    result = bhavcopy.download_bhavcopy(
        day, session=binary, sleep=lambda _s: None, max_attempts=4, now=NOW
    )
    assert result.outcome.outcome == OUTCOME_ERROR, "still an error once the budget is spent"
    assert len(binary.log) == 4, "and it is spent: four attempts, like the JSON path"

    class _JsonResponse(_Response):
        def json(self) -> Any:
            raise ValueError("not JSON")

    class _JsonRecorder(_Recorder):
        def get(self, url: str, timeout: float | None = None) -> Any:
            self.log.append((0.0, url))
            return _JsonResponse(200, html)

    json_path = _JsonRecorder({}, [0.0])
    with pytest.raises(nse_http.NseFetchError):
        nse_http.fetch_json(
            f"http://{UNROUTABLE}/x", session=json_path, sleep=lambda _s: None, max_attempts=4
        )
    assert len(json_path.log) == 4, "the JSON path retries the identical body four times"


def test_a_real_zip_is_still_accepted_on_the_first_attempt() -> None:
    """The Finding-2 fix must not make a GOOD download retry: only HTML is transient."""
    day = date(2026, 7, 20)
    payload = _zip_of(
        "TradDt,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol\n"
        "2026-07-20,TCS,EQ,2280.10,2283.40,2245.10,2251.10,2202693\n"
    )
    session = _Recorder({url_for(day, FORMAT_UDIFF): _Response(200, payload)}, [0.0])
    result = bhavcopy.download_bhavcopy(
        day, session=session, sleep=lambda _s: None, max_attempts=4, now=NOW
    )
    assert result.outcome.outcome == OUTCOME_PRESENT
    assert len(session.log) == 1


def test_the_raw_csv_archive_is_written_atomically(
    backfill: ModuleType, tmp_path: Path
) -> None:
    """CLOSES the atomic half of REVIEW_2 FINDING 3; RECORDS the half still open.

    Fixed: `--raw-dir` now writes through `acumen.atomic_io`, so a Ctrl-C mid-write cannot
    leave a truncated CSV in the archive the DERIVED fixtures are cut from -- measured here
    by interrupting the write and checking what survives.

    Still true, and still documented rather than fixed (the architect scoped this session to
    the atomic half): the archive is written INSIDE the fetch loop, so a date settled by an
    earlier run is never archived, and adding `--raw-dir` to a later run does not backfill it.
    """
    raw_dir = tmp_path / "raw"
    download = Download(
        DateOutcome(
            trade_date=date(2026, 7, 20),
            outcome=OUTCOME_PRESENT,
            source_format=FORMAT_UDIFF,
            row_count=1,
        ),
        (),
        raw_csv="TradDt,TckrSymb\n2026-07-20,TCS\n",
    )
    backfill._keep_raw(raw_dir, date(2026, 7, 20), download)
    written = raw_dir / f"2026-07-20_{FORMAT_UDIFF}.csv"
    assert written.read_text(encoding="utf-8") == download.raw_csv

    with mock.patch("acumen.atomic_io.os.replace", side_effect=KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt):
            backfill._keep_raw(
                raw_dir, date(2026, 7, 21), Download(download.outcome, (), raw_csv="X")
            )
    assert not (raw_dir / f"2026-07-21_{FORMAT_UDIFF}.csv").exists(), "no truncated file"
    assert sorted(p.name for p in raw_dir.iterdir()) == [written.name], "and no orphan temp"

    source = (REPO / "src" / "acumen" / "backfill_daily.py").read_text(encoding="utf-8")
    assert "atomic_write_text(raw_dir / name" in source
    assert "_keep_raw(raw_dir, day, download)" in source, "still inside the fetch loop"
