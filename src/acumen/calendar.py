"""NSE trading calendar: trading days, bias pairs, and the E2 session filter.

Spec:

* CONTEXT 3.1 -- "Days: NSE trading days only (holiday calendar 4.1). 'Previous day' always
  means previous TRADING day. Non-standard sessions (Muhurat etc.) are excluded."
* CONTEXT 3.2 -- "to trade on day D, take candle(D-1) as current and candle(D-2) as
  previous (both trading days)". That is :meth:`TradingCalendar.bias_pair`.
* CONTEXT 4.1 -- holiday source: the per-segment holiday-master JSON; use the **CM** (cash)
  segment. 2026 = 20 holidays.
* CONTEXT 7-E2 -- "Non-standard sessions (Muhurat, special/shortened sessions) are excluded.
  Detection: candle data on a date absent from the trading calendar, or outside 09:15-15:30
  -> excluded." Both clauses live in :meth:`TradingCalendar.is_session_candle`.
* CONTEXT 7-E8 -- everything is naive IST. Tz-aware input is rejected, not silently
  converted (the PoC's frozen CSVs carry +05:30 stamps; the ingest layer must normalize).
* CONTEXT 7-E12 -- bars are OPEN-stamped: the 09:15 bar covers 09:15:00-09:15:59, and a
  15-minute bar stamped 15:15 is the one closing at 15:30.

A calendar only ever answers for the years its holiday data actually covers. Asking about
any other year raises instead of returning a plausible-looking answer: the endpoint publishes
one year at a time, and treating an unloaded year as "no holidays" would silently invent
about a dozen trading days per year (QUESTIONS.md Q-3).

Everything below the parse boundary is pure: no I/O, no network, no clock reads inside the
calendar itself -- the fetch half is at the bottom of the module and is opt-in.

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, NamedTuple

import requests

from . import nse_http

#: CONTEXT 4.1 -- per-segment holiday JSON; the cash market segment is the one we trade.
HOLIDAY_MASTER_URL: str = "https://www.nseindia.com/api/holiday-master?type=trading"

#: Cash market. CONTEXT 4.1 says explicitly: "use CM".
CASH_SEGMENT: str = "CM"

CACHE_FILENAME: str = "holiday_master_trading.json"

#: CONTEXT 3.1 -- NSE cash session, 09:15-15:30 IST. These are SPEC constants, not tunables:
#: the exchange session is law, so it must not be movable from a config file.
SESSION_OPEN: time = time(9, 15)
SESSION_CLOSE: time = time(15, 30)

#: Saturday, Sunday. NSE cash trades Monday-Friday minus the holiday list.
_WEEKEND: frozenset[int] = frozenset({5, 6})

#: NSE stamps dates as "26-Jan-2026". Parsed with an explicit map rather than
#: ``strptime("%d-%b-%Y")``: %b is LOCALE-dependent and would fail on a non-English machine.
_MONTHS: dict[str, int] = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

#: Guard against an unbounded walk on a pathological calendar. NSE's longest real gap is a
#: few days; 30 is far beyond anything legitimate and turns a hang into an error.
_MAX_WALK_BACK_DAYS: int = 30


class CalendarError(RuntimeError):
    """The trading calendar cannot answer the question asked of it."""


class BiasPair(NamedTuple):
    """The two daily candles that decide day D's bias (CONTEXT 3.2).

    ``current`` is candle(D-1) and ``previous`` is candle(D-2) -- named, because the spec's
    "current" is the LATER of the two and swapping them silently inverts every bias.
    """

    current: date
    previous: date


def parse_holidays(
    payload: Mapping[str, Any], *, segment: str = CASH_SEGMENT
) -> tuple[date, ...]:
    """Extract one segment's holiday dates from a ``holiday-master`` payload.

    PURE: no I/O, no network, no clock.

    Args:
        payload: the decoded endpoint JSON -- ``{"CM": [{"tradingDate": "26-Jan-2026", ...}]}``.
        segment: which market segment to read; CONTEXT 4.1 says CM.

    Returns:
        The holiday dates, de-duplicated and sorted.

    Raises:
        CalendarError: the payload has the wrong shape, the segment is absent or empty, or
            a date does not parse. An empty holiday list is never returned -- it would make
            every weekday look tradable.
    """
    if not isinstance(payload, Mapping):
        raise CalendarError(
            f"Holiday payload must be a JSON object, got {type(payload).__name__}."
        )
    rows = payload.get(segment)
    if not isinstance(rows, list):
        raise CalendarError(
            f"Holiday payload has no {segment!r} segment "
            f"(segments present: {', '.join(sorted(map(str, payload))) or '<none>'})."
        )
    if not rows:
        raise CalendarError(
            f"Holiday segment {segment!r} is empty. Refusing to build a calendar with no "
            "holidays: every weekday would look like a trading day."
        )

    holidays: set[date] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise CalendarError(f"{segment}[{index}] is {type(row).__name__}, expected an object.")
        raw = row.get("tradingDate")
        if not isinstance(raw, str) or not raw.strip():
            raise CalendarError(f"{segment}[{index}] has no usable 'tradingDate' value.")
        holidays.add(parse_nse_date(raw.strip()))
    return tuple(sorted(holidays))


def parse_nse_date(value: str) -> date:
    """Parse NSE's ``DD-MMM-YYYY`` date form, locale-independently.

    Raises:
        CalendarError: the string is not a valid NSE date.
    """
    parts = value.split("-")
    if len(parts) != 3:
        raise CalendarError(f"Unparseable NSE date {value!r}; expected DD-MMM-YYYY.")
    day_text, month_text, year_text = parts
    month = _MONTHS.get(month_text.strip().upper())
    if month is None:
        raise CalendarError(f"Unknown month {month_text!r} in NSE date {value!r}.")
    try:
        return date(int(year_text), month, int(day_text))
    except ValueError as exc:
        raise CalendarError(f"Unparseable NSE date {value!r}: {exc}") from exc


def is_session_time(stamp: datetime, *, minutes: int = 1) -> bool:
    """Does an OPEN-stamped bar of ``minutes`` fall inside the 09:15-15:30 session?

    PURE, and calendar-free: this is only the clock half of CONTEXT 7-E2. A bar stamped
    ``t`` covers ``[t, t + minutes)`` (E12), so it is inside the session when
    ``t >= 09:15`` AND ``t + minutes <= 15:30``. For 1-minute bars that admits 09:15..15:29
    -- exactly the 375 stamps CONTEXT 4.5 gate 2 expects. For 15-minute bars it admits
    09:15..15:15, and 15:15 is the bar closing at 15:30.

    Raises:
        CalendarError: ``stamp`` is tz-aware (CONTEXT 7-E8) or ``minutes`` is not positive.
    """
    _require_naive_datetime(stamp)
    if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 1:
        raise CalendarError(f"minutes must be a positive whole number, got {minutes!r}.")
    end = stamp + timedelta(minutes=minutes)
    if end.date() != stamp.date():  # a bar that runs past midnight is not a session bar
        return False
    return stamp.time() >= SESSION_OPEN and end.time() <= SESSION_CLOSE


@dataclass(frozen=True)
class TradingCalendar:
    """NSE trading days for the years its holiday data covers. Immutable and pure.

    Attributes:
        holidays: the exchange holidays (weekends are separate and implicit).
        covered_years: the years this calendar may answer for. Any other year raises.
    """

    holidays: frozenset[date]
    covered_years: frozenset[int]

    # --- construction -------------------------------------------------------------

    @classmethod
    def from_holidays(
        cls,
        holidays: Iterable[date],
        *,
        covered_years: Iterable[int] | None = None,
    ) -> TradingCalendar:
        """Build from an explicit holiday list.

        Args:
            holidays: exchange holidays.
            covered_years: years this calendar may answer for. Defaults to the years the
                holidays themselves fall in -- the honest reading of "one year per pull".
        """
        frozen = frozenset(_require_plain_date(day, "holiday") for day in holidays)
        if not frozen:
            raise CalendarError("Refusing to build a calendar with no holidays.")
        if covered_years is None:
            years = frozenset(day.year for day in frozen)
        else:
            years = frozenset(int(year) for year in covered_years)
            if not years:
                raise CalendarError("covered_years was given but is empty; omit it to derive it.")
        return cls(holidays=frozen, covered_years=years)

    @classmethod
    def from_payload(
        cls, payload: Mapping[str, Any], *, segment: str = CASH_SEGMENT
    ) -> TradingCalendar:
        """Build straight from a ``holiday-master`` payload. PURE."""
        return cls.from_holidays(parse_holidays(payload, segment=segment))

    # --- trading days -------------------------------------------------------------

    def is_trading_day(self, day: date) -> bool:
        """Is ``day`` an NSE cash trading day? Weekends and holidays are not.

        Raises:
            CalendarError: ``day`` is a datetime, is tz-aware, or falls in a year this
                calendar does not cover.
        """
        checked = _require_plain_date(day)
        self._require_covered(checked)
        return checked.weekday() not in _WEEKEND and checked not in self.holidays

    def is_standard_session(self, day: date) -> bool:
        """CONTEXT 7-E2: is ``day`` a standard session?

        A date absent from the trading calendar is non-standard, which covers Muhurat (NSE
        lists it as a holiday, with its special session outside 09:15-15:30) and every other
        special session. Kept separate from :meth:`is_trading_day` because they answer
        different questions even where the predicate coincides.
        """
        return self.is_trading_day(day)

    def prev_trading_day(self, day: date) -> date:
        """The last trading day STRICTLY before ``day``.

        ``day`` itself need not be a trading day. CONTEXT 3.1: "'Previous day' always means
        previous TRADING day."

        Raises:
            CalendarError: the walk leaves the covered years, or finds no trading day
                within 30 calendar days (a pathological calendar).
        """
        checked = _require_plain_date(day)
        candidate = checked - timedelta(days=1)
        for _ in range(_MAX_WALK_BACK_DAYS):
            if self.is_trading_day(candidate):
                return candidate
            candidate -= timedelta(days=1)
        raise CalendarError(
            f"No trading day found in the {_MAX_WALK_BACK_DAYS} calendar days before "
            f"{checked.isoformat()}; the loaded holiday data cannot be right."
        )

    def bias_pair(self, day: date) -> BiasPair:
        """The (D-1, D-2) TRADING days whose candles decide ``day``'s bias (CONTEXT 3.2).

        Both are trading days, so the pair skips weekends and holidays alike. Returns a
        named pair: ``current`` = candle(D-1), ``previous`` = candle(D-2).

        Raises:
            CalendarError: ``day`` is not a trading day (there is no bias for a day the
                market is shut), or the pair leaves the covered years.
        """
        checked = _require_plain_date(day)
        if not self.is_trading_day(checked):
            raise CalendarError(
                f"{checked.isoformat()} is not an NSE trading day, so it has no bias pair "
                "(CONTEXT 3.2 computes a bias for a day the stock can be traded on)."
            )
        current = self.prev_trading_day(checked)
        return BiasPair(current=current, previous=self.prev_trading_day(current))

    # --- CONTEXT 7-E2 session filter ----------------------------------------------

    def is_session_candle(self, stamp: datetime, *, minutes: int = 1) -> bool:
        """CONTEXT 7-E2, both clauses: is this OPEN-stamped bar part of a standard session?

        Excluded when the date is absent from the trading calendar, or when the bar does not
        fit inside 09:15-15:30 (see :func:`is_session_time`).

        Raises:
            CalendarError: ``stamp`` is not a naive datetime, ``minutes`` is not positive,
                or the date falls outside the covered years.
        """
        _require_naive_datetime(stamp)
        if not self.is_standard_session(stamp.date()):
            return False
        return is_session_time(stamp, minutes=minutes)

    def filter_session_candles(
        self, stamps: Iterable[datetime], *, minutes: int = 1
    ) -> tuple[datetime, ...]:
        """Keep only the stamps :meth:`is_session_candle` accepts, in the order given."""
        return tuple(stamp for stamp in stamps if self.is_session_candle(stamp, minutes=minutes))

    # --- internals ----------------------------------------------------------------

    def _require_covered(self, day: date) -> None:
        if day.year not in self.covered_years:
            years = ", ".join(str(y) for y in sorted(self.covered_years))
            raise CalendarError(
                f"No NSE holiday data loaded for {day.year} (loaded: {years}). Refusing to "
                "answer: an uncovered year would silently look holiday-free, inventing "
                "about a dozen trading days. See QUESTIONS.md Q-3."
            )


# --- fetch half (I/O; opt-in) ------------------------------------------------------


def load_calendar(path: Path, *, segment: str = CASH_SEGMENT) -> TradingCalendar:
    """Build a calendar from a saved RAW endpoint payload (e.g. the frozen test snapshot).

    Raises:
        CalendarError: the file is missing, is not JSON, or fails :func:`parse_holidays`.
    """
    source = Path(path)
    if not source.is_file():
        raise CalendarError(f"Holiday snapshot not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CalendarError(f"Could not read holiday snapshot {source}: {exc}") from exc
    return TradingCalendar.from_payload(payload, segment=segment)


def cache_path(cache_dir: Path | None = None) -> Path:
    """Return the day-cache path for the holiday endpoint."""
    base = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    return base / CACHE_FILENAME


def default_cache_dir() -> Path:
    """``<data_dir>/nse`` from config.yaml. ``data/`` is gitignored (CLAUDE.md git rules)."""
    from .config import load_config  # local import: parsing must not require a config file

    return load_config(include_env=False).path("data_dir") / "nse"


def fetch_calendar(
    *,
    cache_dir: Path | None = None,
    today: date | None = None,
    allow_network: bool = False,
    session: requests.Session | None = None,
    segment: str = CASH_SEGMENT,
    sleep: Callable[[float], None] | None = None,
) -> TradingCalendar:
    """Return the trading calendar, pulling it live at most once per calendar day.

    Args:
        cache_dir: where the day-cache lives; defaults to :func:`default_cache_dir`.
        today: the IST calendar date; defaults to the system date.
        allow_network: explicit opt-in to a live pull. While False, a missing or stale
            cache raises instead of reaching out -- this is what keeps pytest offline.
        session: an existing :class:`requests.Session`.
        segment: market segment; CONTEXT 4.1 says CM.
        sleep: injected for tests.

    Raises:
        NseFetchError: offline with no cache for today, or the live pull failed.
        CalendarError: the payload parsed but is not a usable calendar.
    """
    kwargs: dict[str, Any] = {}
    if sleep is not None:
        kwargs["sleep"] = sleep
    payload = nse_http.cached_json(
        HOLIDAY_MASTER_URL,
        cache_path(cache_dir),
        today=today if today is not None else date.today(),
        allow_network=allow_network,
        session=session,
        **kwargs,
    )
    return TradingCalendar.from_payload(payload, segment=segment)


def load_cached_calendar(
    cache_dir: Path | None = None, *, segment: str = CASH_SEGMENT
) -> tuple[date, TradingCalendar]:
    """Return ``(fetched_on, calendar)`` from the day-cache at ANY age.

    Staleness is handed back to the caller rather than hidden.

    Raises:
        CalendarError: no cache file exists.
        NseFetchError: the cache file is damaged.
    """
    path = cache_path(cache_dir)
    cached = nse_http.read_cache(path)
    if cached is None:
        raise CalendarError(
            f"No cached holiday calendar at {path}. Run fetch_calendar(allow_network=True) once."
        )
    fetched_on, payload = cached
    return fetched_on, TradingCalendar.from_payload(payload, segment=segment)


def _require_plain_date(value: Any, what: str = "date") -> date:
    """Accept a naive ``date``; reject ``datetime`` and anything else (CONTEXT 7-E8)."""
    if isinstance(value, datetime):
        raise CalendarError(
            f"Expected a plain {what}, got a datetime ({value!r}). Pass .date() explicitly "
            "so the truncation is visible in the caller."
        )
    if not isinstance(value, date):
        raise CalendarError(f"Expected a {what}, got {type(value).__name__}.")
    return value


def _require_naive_datetime(value: Any) -> datetime:
    """Accept a naive IST ``datetime``; reject tz-aware ones (CONTEXT 7-E8)."""
    if not isinstance(value, datetime):
        raise CalendarError(f"Expected a datetime, got {type(value).__name__}.")
    if value.tzinfo is not None:
        raise CalendarError(
            f"Timestamps must be naive IST (CONTEXT 7-E8); got a tz-aware value ({value!r}). "
            "Normalize on ingest -- do not attach or convert a timezone here."
        )
    return value
