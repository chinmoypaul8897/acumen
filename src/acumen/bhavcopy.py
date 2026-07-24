"""NSE daily bhavcopy: both published formats, parsed to one row shape (CONTEXT 4.1).

CONTEXT 4.1 names exactly two sources for daily OHLCV, and this module reads both:

* **UDiFF** (the current format, since Jul-2024) --
  ``.../content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip``, columns ``TckrSymb``,
  ``OpnPric``, ``HghPric``, ``LwPric``, ``ClsPric``, ``TtlTradgVol``;
* **the old archive format** (verified back to 2000) --
  ``.../content/historical/EQUITIES/YYYY/MMM/cmDDMMMYYYYbhav.csv.zip``, columns ``SYMBOL``,
  ``OPEN``, ``HIGH``, ``LOW``, ``CLOSE``, ``TOTTRDQTY``.

Two things here decide whether the rest of the project can trust its own history.

**Prices are integer paise.** CLAUDE.md and CONTEXT 7-E11 make paise the internal price
domain, and the conversion goes through :class:`~decimal.Decimal` from the CSV TEXT, never
through a float: ``float("2251.10") * 100`` is 225109.99999999997, and rounding that is a
guess. A price that is not a whole number of paise is an error, not a rounding opportunity.

**Every date gets an OUTCOME, and the three outcomes are never confused** (QUESTIONS.md Q-3,
the architect's ruling and its safeguard 1):

* ``file-present``  -- NSE published a bhavcopy for that date. It is a trading day.
* ``confirmed-404`` -- the server answered 404 for EVERY candidate URL. NSE published no
  file, so it is a non-trading day.
* ``error``         -- anything else (timeout, 403 burst that outlived its retries, a
  corrupt ZIP). The date is simply UNKNOWN and must be retried later.

An ``error`` is NEVER downgraded to ``confirmed-404``. That single rule is what stops a bad
network afternoon from silently deleting trading days out of the derived calendar, and from
there shifting every bias pair that spans them (CONTEXT 3.2).

Politeness: downloads are paced at one request per :data:`MIN_SECONDS_BETWEEN_REQUESTS`
seconds (the chunk-2 card's "<= 1 req/2s"), sharing :mod:`acumen.nse_http`'s process-wide
throttle so a JSON pull cannot slip in beside a download. The files themselves are published
for download and NSE's ToU sanctions taking them (CONTEXT 4.1); nothing is redistributed.

The parse half is PURE (bytes in, rows out). Only :func:`download_bhavcopy` touches the
network, and only :func:`fetch_day` reads the clock.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

import requests

from . import nse_http
from .calendar import parse_nse_date

#: CONTEXT 4.1 -- the archive host that publishes both bhavcopy formats.
ARCHIVE_HOST: str = "https://nsearchives.nseindia.com"

UDIFF_URL_TEMPLATE: str = (
    ARCHIVE_HOST + "/content/cm/BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip"
)
ARCHIVE_URL_TEMPLATE: str = (
    ARCHIVE_HOST + "/content/historical/EQUITIES/{year}/{month}/cm{day}{month}{year}bhav.csv.zip"
)

#: CONTEXT 4.1: "Current UDiFF (since Jul-2024)". Dates from this day on are fetched as
#: UDiFF, earlier ones from the old archive. The boundary is not a guess to be trusted
#: blindly -- see :func:`candidate_formats`, which tries the OTHER format before a date is
#: allowed to be called a non-trading day.
UDIFF_FIRST_DATE: date = date(2024, 7, 1)

FORMAT_UDIFF: str = "udiff"
FORMAT_ARCHIVE: str = "archive"

#: The three outcomes of the Q-3 ledger, spelled exactly as the architect's ruling spells
#: them. They are persisted, so they are part of the store's contract.
OUTCOME_PRESENT: str = "file-present"
OUTCOME_NOT_FOUND: str = "confirmed-404"
OUTCOME_ERROR: str = "error"

TERMINAL_OUTCOMES: frozenset[str] = frozenset({OUTCOME_PRESENT, OUTCOME_NOT_FOUND})
ALL_OUTCOMES: frozenset[str] = frozenset({OUTCOME_PRESENT, OUTCOME_NOT_FOUND, OUTCOME_ERROR})

#: Chunk-2 card: "polite pacing (<= 1 req/2s)". Slower than the 2/s CONTEXT 4.3 allows for
#: the SmartAPI, because these are file downloads from an archive nobody is paying us to run.
MIN_SECONDS_BETWEEN_REQUESTS: float = 2.0

#: NSE writes month names in the archive path in upper case: .../2018/JAN/cm01JAN2018bhav...
_MONTH_NAMES: tuple[str, ...] = (
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
)

#: UDiFF columns we read. The file carries 34; the rest are derivative-only or reserved.
_UDIFF_REQUIRED: tuple[str, ...] = (
    "TradDt",
    "TckrSymb",
    "SctySrs",
    "OpnPric",
    "HghPric",
    "LwPric",
    "ClsPric",
    "TtlTradgVol",
)

#: Old-format columns we read. TOTALTRADES and ISIN are absent from the earliest files
#: (verified: the Jan-2000 header stops at TIMESTAMP), so they are optional everywhere.
_ARCHIVE_REQUIRED: tuple[str, ...] = (
    "SYMBOL",
    "SERIES",
    "OPEN",
    "HIGH",
    "LOW",
    "CLOSE",
    "TOTTRDQTY",
    "TIMESTAMP",
)


class BhavcopyError(RuntimeError):
    """A bhavcopy could not be read, or is not the file it claims to be."""


@dataclass(frozen=True)
class DailyRow:
    """One symbol's RAW daily record, exactly as NSE published it.

    Prices are INTEGER PAISE (CONTEXT 7-E11); ``volume`` is shares and ``turnover_paise``
    is the traded value in paise. Nothing here is corporate-action adjusted -- CONTEXT 4.1
    says bhavcopy prices are UNADJUSTED, and chunk 3 owns the adjustment.
    """

    trade_date: date
    symbol: str
    series: str
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int
    last_paise: int | None = None
    prev_close_paise: int | None = None
    turnover_paise: int | None = None
    trades: int | None = None
    isin: str | None = None
    instrument_type: str | None = None
    source_format: str = FORMAT_UDIFF


@dataclass(frozen=True)
class DateOutcome:
    """What happened when we asked NSE for one date's bhavcopy (Q-3 ledger row)."""

    trade_date: date
    outcome: str
    source_format: str | None = None
    url: str | None = None
    http_status: int | None = None
    reason: str | None = None
    row_count: int | None = None
    attempted_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.outcome not in ALL_OUTCOMES:
            raise BhavcopyError(
                f"Unknown outcome {self.outcome!r}; the ledger only knows "
                f"{', '.join(sorted(ALL_OUTCOMES))}."
            )

    @property
    def is_terminal(self) -> bool:
        """Has this date been settled? An ``error`` has NOT -- it must be retried."""
        return self.outcome in TERMINAL_OUTCOMES


# --- URLs ------------------------------------------------------------------------------


def format_for(day: date) -> str:
    """Which published format covers ``day`` (CONTEXT 4.1: UDiFF since Jul-2024)."""
    return FORMAT_UDIFF if day >= UDIFF_FIRST_DATE else FORMAT_ARCHIVE


def candidate_formats(day: date) -> tuple[str, ...]:
    """The formats to try for ``day``, in order: the era's format, then the other one.

    The second attempt costs one extra request and only ever happens on a date that has
    already answered 404 -- but it is what makes ``confirmed-404`` mean "NEITHER published
    file exists". Without it, a wrong cutover date (CONTEXT 4.1 states the boundary only to
    the month) would turn a run of real trading days into holidays, silently, and the
    derived calendar (Q-3) would carry that error into every bias pair spanning them.
    """
    primary = format_for(day)
    other = FORMAT_ARCHIVE if primary == FORMAT_UDIFF else FORMAT_UDIFF
    return (primary, other)


def url_for(day: date, source_format: str) -> str:
    """The published URL of ``day``'s bhavcopy in ``source_format``."""
    if source_format == FORMAT_UDIFF:
        return UDIFF_URL_TEMPLATE.format(yyyymmdd=day.strftime("%Y%m%d"))
    if source_format == FORMAT_ARCHIVE:
        return ARCHIVE_URL_TEMPLATE.format(
            year=f"{day.year:04d}", month=_MONTH_NAMES[day.month - 1], day=f"{day.day:02d}"
        )
    raise BhavcopyError(
        f"Unknown bhavcopy format {source_format!r}; expected "
        f"{FORMAT_UDIFF!r} or {FORMAT_ARCHIVE!r}."
    )


# --- parsing (PURE) ---------------------------------------------------------------------


def extract_csv(payload: bytes) -> str:
    """Return the single CSV inside a bhavcopy ZIP. PURE.

    Raises:
        BhavcopyError: the bytes are not a ZIP, or do not hold exactly one CSV.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(names) != 1:
                raise BhavcopyError(
                    f"Expected exactly one CSV inside the bhavcopy ZIP, found {names!r}."
                )
            return archive.read(names[0]).decode("utf-8")
    except zipfile.BadZipFile as exc:
        head = payload[:16]
        raise BhavcopyError(
            f"Downloaded {len(payload)} bytes that are not a ZIP (starts with {head!r}). "
            "NSE serves an HTML page for a missing or blocked file -- this is an ERROR, not "
            "an empty day."
        ) from exc
    except UnicodeDecodeError as exc:
        raise BhavcopyError(f"The bhavcopy CSV is not valid UTF-8: {exc}") from exc


def parse_bhavcopy(text: str, source_format: str) -> tuple[DailyRow, ...]:
    """Parse a bhavcopy CSV into :class:`DailyRow` records. PURE.

    Every row is kept -- every symbol and every series NSE published that day. CONTEXT 4.1
    calls the bhavcopy the daily OHLCV source and names no filter, and the chunk-2 card is
    explicit: store everything, filter on query. Restricting the store to today's F&O
    universe would also make the store's own history depend on when it was built.

    Args:
        text: the decoded CSV.
        source_format: :data:`FORMAT_UDIFF` or :data:`FORMAT_ARCHIVE`.

    Raises:
        BhavcopyError: a required column is missing, a value will not parse, or the file has
            no data rows. An empty bhavcopy is never returned as an empty result.
    """
    if source_format == FORMAT_UDIFF:
        required, build = _UDIFF_REQUIRED, _udiff_row
    elif source_format == FORMAT_ARCHIVE:
        required, build = _ARCHIVE_REQUIRED, _archive_row
    else:
        raise BhavcopyError(f"Unknown bhavcopy format {source_format!r}.")

    reader = csv.DictReader(io.StringIO(text))
    header = [name.strip() for name in (reader.fieldnames or [])]
    missing = [name for name in required if name not in header]
    if missing:
        raise BhavcopyError(
            f"{source_format} bhavcopy is missing column(s) {', '.join(missing)}. "
            f"Columns present: {', '.join(header) or '<none>'}."
        )

    rows = tuple(build(_strip_keys(raw), index) for index, raw in enumerate(reader, start=2))
    if not rows:
        raise BhavcopyError(
            f"{source_format} bhavcopy parsed to zero rows. A published bhavcopy always "
            "carries the day's trades; an empty one is a damaged download, not a quiet day."
        )
    return rows


def _strip_keys(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Trim header whitespace and drop the unnamed column both formats end their rows with."""
    return {
        str(key).strip(): value for key, value in raw.items() if key is not None and str(key).strip()
    }


def _udiff_row(raw: Mapping[str, Any], line: int) -> DailyRow:
    return DailyRow(
        trade_date=_iso_date(raw.get("TradDt"), line),
        symbol=_text(raw.get("TckrSymb"), "TckrSymb", line).upper(),
        series=_text(raw.get("SctySrs"), "SctySrs", line).upper(),
        open_paise=_paise(raw.get("OpnPric"), "OpnPric", line),
        high_paise=_paise(raw.get("HghPric"), "HghPric", line),
        low_paise=_paise(raw.get("LwPric"), "LwPric", line),
        close_paise=_paise(raw.get("ClsPric"), "ClsPric", line),
        volume=_whole(raw.get("TtlTradgVol"), "TtlTradgVol", line),
        last_paise=_optional_paise(raw.get("LastPric"), "LastPric", line),
        prev_close_paise=_optional_paise(raw.get("PrvsClsgPric"), "PrvsClsgPric", line),
        turnover_paise=_optional_paise(raw.get("TtlTrfVal"), "TtlTrfVal", line),
        trades=_optional_whole(raw.get("TtlNbOfTxsExctd"), "TtlNbOfTxsExctd", line),
        isin=_optional_text(raw.get("ISIN")),
        instrument_type=_optional_text(raw.get("FinInstrmTp")),
        source_format=FORMAT_UDIFF,
    )


def _archive_row(raw: Mapping[str, Any], line: int) -> DailyRow:
    return DailyRow(
        trade_date=_nse_date(raw.get("TIMESTAMP"), line),
        symbol=_text(raw.get("SYMBOL"), "SYMBOL", line).upper(),
        series=_text(raw.get("SERIES"), "SERIES", line).upper(),
        open_paise=_paise(raw.get("OPEN"), "OPEN", line),
        high_paise=_paise(raw.get("HIGH"), "HIGH", line),
        low_paise=_paise(raw.get("LOW"), "LOW", line),
        close_paise=_paise(raw.get("CLOSE"), "CLOSE", line),
        volume=_whole(raw.get("TOTTRDQTY"), "TOTTRDQTY", line),
        last_paise=_optional_paise(raw.get("LAST"), "LAST", line),
        prev_close_paise=_optional_paise(raw.get("PREVCLOSE"), "PREVCLOSE", line),
        turnover_paise=_optional_paise(raw.get("TOTTRDVAL"), "TOTTRDVAL", line),
        trades=_optional_whole(raw.get("TOTALTRADES"), "TOTALTRADES", line),
        isin=_optional_text(raw.get("ISIN")),
        instrument_type=None,  # the old format carries no instrument-type column
        source_format=FORMAT_ARCHIVE,
    )


def _text(value: Any, field: str, line: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BhavcopyError(f"Line {line}: {field} is empty or missing.")
    return value.strip()


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _paise(value: Any, field: str, line: int) -> int:
    """Convert a printed rupee amount to integer paise EXACTLY (CONTEXT 7-E11).

    Via Decimal on the text, never via float: ``float("2251.10") * 100`` is
    225109.99999999997, and a price that needed rounding would be a silent price change.
    """
    text = _text(value, field, line)
    try:
        scaled = Decimal(text) * 100
    except InvalidOperation as exc:
        raise BhavcopyError(f"Line {line}: {field}={text!r} is not a number.") from exc
    if scaled != scaled.to_integral_value():
        raise BhavcopyError(
            f"Line {line}: {field}={text!r} is not a whole number of paise. Prices are "
            "integer paise internally (CONTEXT 7-E11) and this one cannot be represented."
        )
    return int(scaled)


def _optional_paise(value: Any, field: str, line: int) -> int | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return _paise(value, field, line)


def _whole(value: Any, field: str, line: int) -> int:
    text = _text(value, field, line)
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise BhavcopyError(f"Line {line}: {field}={text!r} is not a number.") from exc
    if number != number.to_integral_value():
        raise BhavcopyError(f"Line {line}: {field}={text!r} must be a whole number.")
    return int(number)


def _optional_whole(value: Any, field: str, line: int) -> int | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return _whole(value, field, line)


def _iso_date(value: Any, line: int) -> date:
    text = _text(value, "TradDt", line)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise BhavcopyError(f"Line {line}: TradDt={text!r} is not an ISO date.") from exc


def _nse_date(value: Any, line: int) -> date:
    """The old format stamps ``01-JAN-2018`` -- and ``3-JAN-2000``, unpadded, in 2000."""
    text = _text(value, "TIMESTAMP", line)
    try:
        return parse_nse_date(text)
    except Exception as exc:  # CalendarError, re-labelled with the CSV line
        raise BhavcopyError(f"Line {line}: TIMESTAMP={text!r} is not an NSE date.") from exc


# --- download (I/O) ---------------------------------------------------------------------


@dataclass(frozen=True)
class Download:
    """The result of asking NSE for one date: an outcome plus whatever rows came back.

    ``raw_csv`` is the file's own text, kept so the operator can archive the SOURCE rather
    than a re-serialisation of it -- a fixture or an audit trail is only evidence if it is
    what NSE actually published (chunk-1 B16, applied to files).
    """

    outcome: DateOutcome
    rows: tuple[DailyRow, ...] = ()
    raw_csv: str | None = None


def download_bhavcopy(
    day: date,
    *,
    session: requests.Session | None = None,
    timeout: float = nse_http.DEFAULT_TIMEOUT,
    max_attempts: int = nse_http.DEFAULT_MAX_ATTEMPTS,
    sleep: Callable[[float], None] | None = None,
    min_interval: float = MIN_SECONDS_BETWEEN_REQUESTS,
    now: datetime | None = None,
) -> Download:
    """Fetch, unzip and parse one date's bhavcopy, classifying the result (Q-3 ledger).

    Tries the era's format first and the other one only if the first answers 404, so a
    ``confirmed-404`` means no published file exists in EITHER format.

    Args:
        day: the trading date to ask for.
        session: an existing :class:`requests.Session` (a fresh one is built when omitted).
        timeout: per-request timeout.
        max_attempts: attempts per URL, including the first.
        sleep: injected for tests; the throttle and backoff call it.
        min_interval: seconds between outbound requests (default: the card's 1 per 2s).
        now: the ledger timestamp; defaults to the machine clock (naive IST, CONTEXT 7-E8).

    Returns:
        A :class:`Download`. It NEVER raises for a missing or broken day -- that is what the
        outcome is for; the caller records it and moves on. It does raise for a programming
        error such as an unknown format name.
    """
    stamped = now if now is not None else datetime.now()
    if stamped.tzinfo is not None:
        raise BhavcopyError(
            "Ledger timestamps must be naive IST (CONTEXT 7-E8); got a tz-aware value."
        )
    kwargs: dict[str, Any] = {} if sleep is None else {"sleep": sleep}
    http = session if session is not None else nse_http.new_session()

    last_url: str | None = None
    for source_format in candidate_formats(day):
        url = last_url = url_for(day, source_format)
        try:
            payload = nse_http.fetch_binary(
                url,
                session=http,
                timeout=timeout,
                max_attempts=max_attempts,
                min_interval=min_interval,
                **kwargs,
            )
        except nse_http.NseNotFoundError:
            continue  # this format has no file; try the other before concluding anything
        except nse_http.NseFetchError as exc:
            return Download(
                DateOutcome(
                    trade_date=day,
                    outcome=OUTCOME_ERROR,
                    source_format=source_format,
                    url=url,
                    reason=str(exc),
                    attempted_at=stamped,
                )
            )

        try:
            text = extract_csv(payload)
            rows = parse_bhavcopy(text, source_format)
            _require_single_date(rows, day, source_format)
        except BhavcopyError as exc:
            return Download(
                DateOutcome(
                    trade_date=day,
                    outcome=OUTCOME_ERROR,
                    source_format=source_format,
                    url=url,
                    http_status=200,
                    reason=str(exc),
                    attempted_at=stamped,
                )
            )

        return Download(
            DateOutcome(
                trade_date=day,
                outcome=OUTCOME_PRESENT,
                source_format=source_format,
                url=url,
                http_status=200,
                row_count=len(rows),
                attempted_at=stamped,
            ),
            rows,
            raw_csv=text,
        )

    return Download(
        DateOutcome(
            trade_date=day,
            outcome=OUTCOME_NOT_FOUND,
            source_format=None,
            url=last_url,
            http_status=404,
            reason="no published bhavcopy in either format",
            attempted_at=stamped,
        )
    )


def _require_single_date(rows: Sequence[DailyRow], day: date, source_format: str) -> None:
    """A downloaded file must be the date we asked for, and only that date.

    NSE serving yesterday's file under today's URL would poison the store and, through the
    Q-3 ledger, the calendar too. (The parser itself stays date-agnostic so a test fixture
    may legitimately hold rows from several days.)
    """
    dates = {row.trade_date for row in rows}
    if dates != {day}:
        raise BhavcopyError(
            f"The {source_format} bhavcopy fetched for {day.isoformat()} carries "
            f"{sorted(d.isoformat() for d in dates)!r}. Refusing to store a file that is not "
            "the date it was requested for."
        )


def date_range(start: date, end: date) -> Iterator[date]:
    """Every calendar date from ``start`` to ``end`` inclusive.

    Weekends included, deliberately: the Q-3 ruling derives trading days from what NSE
    actually published, and NSE does hold occasional weekend sessions. Skipping Saturdays
    would replace the evidence with an assumption.
    """
    if end < start:
        raise BhavcopyError(f"Empty range: {end.isoformat()} is before {start.isoformat()}.")
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def summarise(outcomes: Iterable[DateOutcome]) -> dict[str, int]:
    """Count outcomes by kind, for the operator's run summary."""
    counts = {name: 0 for name in (OUTCOME_PRESENT, OUTCOME_NOT_FOUND, OUTCOME_ERROR)}
    for outcome in outcomes:
        counts[outcome.outcome] += 1
    counts["attempted"] = sum(counts.values())
    return counts
