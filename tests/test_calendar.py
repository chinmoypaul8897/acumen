"""Chunk-1 calendar tests -- CONTEXT 3.1, 3.2, 4.1, 7-E2/E8/E12.

Everything here runs against ``tests/fixtures/holidays_2026.json``, a verbatim snapshot of
``https://www.nseindia.com/api/holiday-master?type=trading`` fetched once during the chunk-1
build session (2026-07-24). No test opens a socket (see conftest.py).

The 2026 CM holiday list the cases below were hand-computed from:

    15-Jan Thu  Municipal Corporation Election - Maharashtra
    26-Jan Mon  Republic Day
    15-Feb Sun  Mahashivratri
    03-Mar Tue  Holi
    21-Mar Sat  Id-Ul-Fitr (Ramadan Eid)
    26-Mar Thu  Shri Ram Navami
    31-Mar Tue  Shri Mahavir Jayanti
    03-Apr Fri  Good Friday
    14-Apr Tue  Dr. Baba Saheb Ambedkar Jayanti
    01-May Fri  Maharashtra Day
    28-May Thu  Bakri Id
    26-Jun Fri  Muharram
    15-Aug Sat  Independence Day
    14-Sep Mon  Ganesh Chaturthi
    02-Oct Fri  Mahatma Gandhi Jayanti
    20-Oct Tue  Dussehra
    08-Nov Sun  Diwali Laxmi Pujan*
    10-Nov Tue  Diwali-Balipratipada
    24-Nov Tue  Prakash Gurpurb Sri Guru Nanak Dev
    25-Dec Fri  Christmas
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from acumen.calendar import (
    CASH_SEGMENT,
    BiasPair,
    CalendarError,
    TradingCalendar,
    is_session_time,
    load_calendar,
    parse_holidays,
    parse_nse_date,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
HOLIDAY_SNAPSHOT = FIXTURES / "holidays_2026.json"

_WEEKDAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


@pytest.fixture()
def calendar_2026() -> TradingCalendar:
    return load_calendar(HOLIDAY_SNAPSHOT)


@pytest.fixture()
def payload() -> dict:
    return json.loads(HOLIDAY_SNAPSHOT.read_text(encoding="utf-8"))


# --- GOLDEN: 2026 CM holiday count == 20 (CONTEXT 4.1) ---------------------------------


def test_golden_2026_cm_holiday_count_is_20(payload: dict) -> None:
    """CONTEXT 4.1: "Holiday calendar ... fetched live, 2026 = 20 holidays"."""
    holidays = parse_holidays(payload)
    assert len(holidays) == 20


def test_cash_segment_is_the_default(payload: dict) -> None:
    """CONTEXT 4.1 says "use CM" -- reading a different segment must be a deliberate act."""
    assert CASH_SEGMENT == "CM"
    assert parse_holidays(payload) == parse_holidays(payload, segment="CM")


def test_every_holiday_falls_in_2026(calendar_2026: TradingCalendar) -> None:
    assert {day.year for day in calendar_2026.holidays} == {2026}
    assert calendar_2026.covered_years == frozenset({2026})


def test_parsed_dates_agree_with_the_payload_weekday_field(payload: dict) -> None:
    """Proof the DD-MMM-YYYY parser is right: NSE ships the weekday name alongside.

    A day/month transposition or an off-by-one year would break this on most rows.
    """
    for row in payload[CASH_SEGMENT]:
        parsed = parse_nse_date(row["tradingDate"])
        assert _WEEKDAY_NAMES[parsed.weekday()] == row["weekDay"], row


def test_2026_has_245_trading_days(calendar_2026: TradingCalendar) -> None:
    """365 days - 104 weekend days - 16 holidays that do not already fall on a weekend.

    Four of the 20 holidays land on a Saturday or Sunday (15-Feb, 21-Mar, 15-Aug, 08-Nov),
    so they cost no trading day at all.
    """
    day, trading = date(2026, 1, 1), 0
    while day.year == 2026:
        trading += calendar_2026.is_trading_day(day)
        day += timedelta(days=1)
    assert trading == 245
    assert sum(1 for h in calendar_2026.holidays if h.weekday() >= 5) == 4


# --- GOLDEN: is_trading_day ------------------------------------------------------------


@pytest.mark.parametrize(
    "day, expected, why",
    [
        (date(2026, 1, 26), False, "Republic Day (Monday) -- GOLDEN"),
        (date(2026, 1, 25), False, "Sunday -- GOLDEN"),
        (date(2026, 1, 24), False, "Saturday"),
        (date(2026, 1, 27), True, "the Tuesday after Republic Day"),
        (date(2026, 1, 23), True, "ordinary Friday"),
        (date(2026, 2, 15), False, "Mahashivratri, which is itself a Sunday"),
        (date(2026, 2, 16), True, "the Monday after it -- still a normal trading day"),
        (date(2026, 4, 3), False, "Good Friday"),
        (date(2026, 11, 10), False, "Diwali-Balipratipada (Tuesday)"),
        (date(2026, 11, 9), True, "the Monday between the two Diwali holidays"),
        (date(2026, 12, 25), False, "Christmas (Friday)"),
        (date(2026, 1, 1), True, "New Year's Day is NOT an NSE holiday in the 2026 list"),
    ],
)
def test_is_trading_day(
    calendar_2026: TradingCalendar, day: date, expected: bool, why: str
) -> None:
    assert calendar_2026.is_trading_day(day) is expected, why


def test_no_holiday_is_ever_a_trading_day(calendar_2026: TradingCalendar) -> None:
    for holiday in sorted(calendar_2026.holidays):
        assert calendar_2026.is_trading_day(holiday) is False


def test_every_weekend_day_of_2026_is_closed(calendar_2026: TradingCalendar) -> None:
    day = date(2026, 1, 1)
    while day.year == 2026:
        if day.weekday() >= 5:
            assert calendar_2026.is_trading_day(day) is False, day
        day += timedelta(days=1)


# --- GOLDEN: bias_pair (CONTEXT 3.2) ---------------------------------------------------


@pytest.mark.parametrize(
    "day, expected_current, expected_previous, reasoning",
    [
        pytest.param(
            date(2026, 1, 27),
            date(2026, 1, 23),
            date(2026, 1, 22),
            # GOLDEN (card): the trading day after Republic Day. Walking back from Tue 27:
            # Mon 26 is Republic Day, Sun 25 and Sat 24 are the weekend -> Fri 23 is D-1.
            # From Fri 23 the previous trading day is Thu 22 -> D-2. The pair skips the
            # holiday AND the weekend, exactly as CONTEXT 3.1's "previous TRADING day" says.
            "after Republic Day Mon 26-Jan: skips the holiday and the weekend",
            id="republic-day-weekend",
        ),
        pytest.param(
            date(2026, 7, 23),
            date(2026, 7, 22),
            date(2026, 7, 21),
            # Plain midweek control: Thu -> Wed -> Tue, nothing skipped.
            "ordinary midweek day",
            id="plain-midweek",
        ),
        pytest.param(
            date(2026, 7, 20),
            date(2026, 7, 17),
            date(2026, 7, 16),
            # Ordinary weekend: Mon 20 -> Fri 17 (Sun 19/Sat 18 skipped) -> Thu 16.
            "ordinary Monday, weekend skipped",
            id="plain-weekend",
        ),
        pytest.param(
            date(2026, 4, 6),
            date(2026, 4, 2),
            date(2026, 4, 1),
            # Good Friday 03-Apr + weekend: Mon 06 -> Sun 05, Sat 04, Fri 03 (holiday) all
            # skipped -> Thu 02 -> Wed 01. A three-day skip in one step.
            "after Good Friday: holiday adjoins the weekend",
            id="good-friday",
        ),
        pytest.param(
            date(2026, 2, 16),
            date(2026, 2, 13),
            date(2026, 2, 12),
            # Mahashivratri falls on Sun 15-Feb, so it costs NOTHING: Mon 16 -> Fri 13 ->
            # Thu 12, identical to an ordinary weekend. Guards against double-counting a
            # holiday that already lands on a non-trading day.
            "holiday that already falls on a Sunday costs no trading day",
            id="holiday-on-a-sunday",
        ),
        pytest.param(
            date(2026, 11, 11),
            date(2026, 11, 9),
            date(2026, 11, 6),
            # Diwali cluster. From Wed 11: Tue 10 is Balipratipada -> Mon 09 is D-1.
            # From Mon 09: Sun 08 is BOTH Laxmi Pujan and a Sunday, Sat 07 is the weekend
            # -> Fri 06 is D-2. The two legs of the pair skip different obstacles.
            "Diwali: each leg of the pair skips a different obstacle",
            id="diwali-cluster",
        ),
        pytest.param(
            date(2026, 3, 4),
            date(2026, 3, 2),
            date(2026, 2, 27),
            # Holi Tue 03-Mar: Wed 04 -> Mon 02 -> (Sun 01, Sat 28-Feb) -> Fri 27-Feb.
            # Also crosses a month boundary.
            "after Holi, crossing into the previous month",
            id="holi-month-boundary",
        ),
    ],
)
def test_golden_bias_pair(
    calendar_2026: TradingCalendar,
    day: date,
    expected_current: date,
    expected_previous: date,
    reasoning: str,
) -> None:
    """CONTEXT 3.2: to trade on D, current = candle(D-1), previous = candle(D-2)."""
    pair = calendar_2026.bias_pair(day)
    assert pair == BiasPair(current=expected_current, previous=expected_previous), reasoning
    assert pair == (expected_current, expected_previous)  # a plain tuple still unpacks


def test_bias_pair_fields_are_named_in_spec_order(calendar_2026: TradingCalendar) -> None:
    """CONTEXT 3.2's "current" is the LATER candle; swapping them inverts every bias."""
    pair = calendar_2026.bias_pair(date(2026, 1, 27))
    assert pair.current > pair.previous
    assert pair.current == pair[0] and pair.previous == pair[1]


def test_bias_pair_is_two_trading_days_strictly_before_d(calendar_2026: TradingCalendar) -> None:
    """Property over every 2026 trading day whose pair stays inside the covered year."""
    day, checked = date(2026, 1, 5), 0
    while day.year == 2026:
        if calendar_2026.is_trading_day(day):
            current, previous = calendar_2026.bias_pair(day)
            assert previous < current < day
            assert calendar_2026.is_trading_day(current)
            assert calendar_2026.is_trading_day(previous)
            # nothing tradable may hide between the two legs, or between D-1 and D
            assert not any(
                calendar_2026.is_trading_day(previous + timedelta(days=n))
                for n in range(1, (current - previous).days)
            )
            assert not any(
                calendar_2026.is_trading_day(current + timedelta(days=n))
                for n in range(1, (day - current).days)
            )
            checked += 1
        day += timedelta(days=1)
    assert checked > 230


@pytest.mark.parametrize("day", [date(2026, 1, 26), date(2026, 1, 25), date(2026, 4, 3)])
def test_bias_pair_refuses_a_non_trading_day(calendar_2026: TradingCalendar, day: date) -> None:
    """There is no bias for a day the market is shut."""
    with pytest.raises(CalendarError, match="not an NSE trading day"):
        calendar_2026.bias_pair(day)


# --- prev_trading_day ------------------------------------------------------------------


@pytest.mark.parametrize(
    "day, expected",
    [
        (date(2026, 1, 27), date(2026, 1, 23)),  # skips Republic Day + weekend
        (date(2026, 1, 26), date(2026, 1, 23)),  # from the holiday itself
        (date(2026, 1, 25), date(2026, 1, 23)),  # from a Sunday
        (date(2026, 7, 23), date(2026, 7, 22)),  # ordinary
        (date(2026, 11, 11), date(2026, 11, 9)),
    ],
)
def test_prev_trading_day(calendar_2026: TradingCalendar, day: date, expected: date) -> None:
    """The argument need not itself be a trading day (CONTEXT 3.1)."""
    assert calendar_2026.prev_trading_day(day) == expected


def test_prev_trading_day_is_strictly_before_its_argument(
    calendar_2026: TradingCalendar,
) -> None:
    day = date(2026, 6, 1)
    assert calendar_2026.prev_trading_day(day) < day


def test_walk_back_refuses_a_calendar_with_no_trading_days() -> None:
    """A pathological calendar must raise, never spin."""
    every_day = [date(2026, 3, 1) + timedelta(days=n) for n in range(40)]
    calendar = TradingCalendar.from_holidays(every_day)
    with pytest.raises(CalendarError, match="No trading day found"):
        calendar.prev_trading_day(date(2026, 4, 8))


# --- year coverage: the STOP rule made executable (QUESTIONS.md Q-3) -------------------


@pytest.mark.parametrize("day", [date(2025, 12, 31), date(2027, 1, 4), date(2019, 5, 2)])
def test_uncovered_year_raises_instead_of_guessing(
    calendar_2026: TradingCalendar, day: date
) -> None:
    """The endpoint publishes ONE year; an unloaded year must not look holiday-free."""
    with pytest.raises(CalendarError, match="No NSE holiday data loaded"):
        calendar_2026.is_trading_day(day)


def test_bias_pair_refuses_to_cross_out_of_the_covered_year(
    calendar_2026: TradingCalendar,
) -> None:
    """Fri 02-Jan-2026's pair reaches Thu 01-Jan and then 2025, which is not loaded."""
    with pytest.raises(CalendarError, match="No NSE holiday data loaded"):
        calendar_2026.bias_pair(date(2026, 1, 2))


def test_a_multi_year_calendar_answers_across_the_boundary() -> None:
    """With both years loaded the same walk succeeds -- the guard is about DATA, not dates."""
    calendar = TradingCalendar.from_holidays(
        [date(2025, 12, 25), date(2026, 1, 26)], covered_years=[2025, 2026]
    )
    # Fri 02-Jan-2026 -> Thu 01-Jan-2026 -> Wed 31-Dec-2025.
    assert calendar.bias_pair(date(2026, 1, 2)) == (date(2026, 1, 1), date(2025, 12, 31))


def test_covered_years_default_to_the_years_present() -> None:
    calendar = TradingCalendar.from_holidays([date(2026, 1, 26), date(2027, 1, 26)])
    assert calendar.covered_years == frozenset({2026, 2027})


# --- CONTEXT 7-E8: naive IST only ------------------------------------------------------


def test_datetime_is_rejected_where_a_date_is_expected(calendar_2026: TradingCalendar) -> None:
    """Silent truncation of a timestamp to a date is how off-by-one-day bugs start."""
    with pytest.raises(CalendarError, match="Pass .date()"):
        calendar_2026.is_trading_day(datetime(2026, 1, 27, 9, 15))


@pytest.mark.parametrize("value", ["2026-01-27", 20260127, None])
def test_non_date_input_is_rejected(calendar_2026: TradingCalendar, value: object) -> None:
    with pytest.raises(CalendarError):
        calendar_2026.is_trading_day(value)  # type: ignore[arg-type]


def test_tz_aware_timestamps_are_rejected(calendar_2026: TradingCalendar) -> None:
    """The frozen PoC CSVs carry +05:30 stamps; ingest must normalize, not this module."""
    ist = timezone(timedelta(hours=5, minutes=30))
    with pytest.raises(CalendarError, match="naive IST"):
        calendar_2026.is_session_candle(datetime(2026, 1, 27, 9, 15, tzinfo=ist))


# --- CONTEXT 7-E2: the session filter --------------------------------------------------


@pytest.mark.parametrize(
    "stamp, minutes, expected, why",
    [
        (datetime(2026, 1, 27, 9, 15), 1, True, "first 1-min bar of the session"),
        (datetime(2026, 1, 27, 9, 14), 1, False, "one minute before the open"),
        (datetime(2026, 1, 27, 15, 29), 1, True, "375th and last 1-min bar (CONTEXT 4.5)"),
        (datetime(2026, 1, 27, 15, 30), 1, False, "open-stamped at the close = after it"),
        (datetime(2026, 1, 27, 15, 45), 1, False, "post-market"),
        (datetime(2026, 1, 27, 8, 0), 1, False, "pre-open auction"),
        (datetime(2026, 1, 27, 9, 15), 15, True, "first 15-min bar, closes 09:30"),
        (datetime(2026, 1, 27, 15, 15), 15, True, "15-min bar closing exactly at 15:30"),
        (datetime(2026, 1, 27, 15, 16), 15, False, "would close at 15:31, past the bell"),
        (datetime(2026, 1, 27, 11, 0), 15, True, "the 11:00-11:15 reference candle (3.4)"),
        (datetime(2026, 1, 27, 14, 45), 15, True, "the candle closing at 15:00 (E12)"),
    ],
)
def test_is_session_time(stamp: datetime, minutes: int, expected: bool, why: str) -> None:
    """CONTEXT 7-E12: a bar stamped t covers [t, t+minutes); it must fit in 09:15-15:30."""
    assert is_session_time(stamp, minutes=minutes) is expected, why


def test_one_minute_session_admits_exactly_the_375_expected_stamps() -> None:
    """CONTEXT 4.5 gate 2: "expected 375 minutes 09:15-15:29"."""
    day = datetime(2026, 1, 27)
    accepted = [
        day + timedelta(minutes=n) for n in range(24 * 60) if is_session_time(day + timedelta(minutes=n))
    ]
    assert len(accepted) == 375
    assert accepted[0] == datetime(2026, 1, 27, 9, 15)
    assert accepted[-1] == datetime(2026, 1, 27, 15, 29)


def test_session_candle_excludes_a_non_calendar_day(calendar_2026: TradingCalendar) -> None:
    """CONTEXT 7-E2 clause 1: candle data on a date absent from the calendar is excluded.

    This is also the Muhurat rule: NSE lists Diwali Laxmi Pujan as a holiday, so its special
    evening session is excluded by the date, and by the clock as well.
    """
    assert calendar_2026.is_session_candle(datetime(2026, 1, 26, 10, 0)) is False  # holiday
    assert calendar_2026.is_session_candle(datetime(2026, 1, 25, 10, 0)) is False  # Sunday
    assert calendar_2026.is_session_candle(datetime(2026, 11, 8, 18, 30)) is False  # Muhurat
    assert calendar_2026.is_session_candle(datetime(2026, 1, 27, 10, 0)) is True


def test_filter_session_candles_drops_both_kinds_of_outsider(
    calendar_2026: TradingCalendar,
) -> None:
    stamps = [
        datetime(2026, 1, 26, 10, 0),  # holiday -> out
        datetime(2026, 1, 27, 9, 14),  # too early -> out
        datetime(2026, 1, 27, 9, 15),  # keep
        datetime(2026, 1, 27, 15, 29),  # keep
        datetime(2026, 1, 27, 15, 30),  # after the bell -> out
        datetime(2026, 1, 27, 18, 15),  # Muhurat-style evening stamp -> out
    ]
    assert calendar_2026.filter_session_candles(stamps) == (
        datetime(2026, 1, 27, 9, 15),
        datetime(2026, 1, 27, 15, 29),
    )


def test_is_standard_session_matches_is_trading_day(calendar_2026: TradingCalendar) -> None:
    for day in (date(2026, 1, 26), date(2026, 1, 27), date(2026, 11, 8)):
        assert calendar_2026.is_standard_session(day) == calendar_2026.is_trading_day(day)


@pytest.mark.parametrize("minutes", [0, -5, 1.5, True, "15", None])
def test_bad_bar_length_is_rejected(minutes: object) -> None:
    with pytest.raises(CalendarError, match="minutes"):
        is_session_time(datetime(2026, 1, 27, 9, 15), minutes=minutes)  # type: ignore[arg-type]


def test_a_bar_running_past_midnight_is_not_a_session_bar() -> None:
    assert is_session_time(datetime(2026, 1, 27, 23, 55), minutes=15) is False


# --- payload validation ----------------------------------------------------------------


@pytest.mark.parametrize(
    "payload, match",
    [
        ({}, "no 'CM' segment"),
        ({"CM": []}, "is empty"),
        ({"CM": {}}, "no 'CM' segment"),
        ({"CM": ["26-Jan-2026"]}, "expected an object"),
        ({"CM": [{"weekDay": "Monday"}]}, "tradingDate"),
        ({"CM": [{"tradingDate": ""}]}, "tradingDate"),
        ([], "must be a JSON object"),
    ],
)
def test_malformed_holiday_payload_is_rejected(payload: object, match: str) -> None:
    with pytest.raises(CalendarError, match=match):
        parse_holidays(payload)  # type: ignore[arg-type]


def test_absent_segment_error_names_the_segments_that_are_present(payload: dict) -> None:
    with pytest.raises(CalendarError, match=r"segments present: CBM, CD, CM,") as excinfo:
        parse_holidays(payload, segment="NOPE")
    assert "FO" in str(excinfo.value)


@pytest.mark.parametrize(
    "value",
    ["26/01/2026", "26-Xxx-2026", "2026-01-26", "32-Jan-2026", "26-Jan", "", "26-Jan-2026-x"],
)
def test_bad_nse_date_is_rejected(value: str) -> None:
    with pytest.raises(CalendarError):
        parse_nse_date(value)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("26-Jan-2026", date(2026, 1, 26)),
        ("08-Nov-2026", date(2026, 11, 8)),
        ("26-JAN-2026", date(2026, 1, 26)),  # case-insensitive month
        ("1-Mar-2026", date(2026, 3, 1)),  # unpadded day
    ],
)
def test_nse_date_parsing(value: str, expected: date) -> None:
    assert parse_nse_date(value) == expected


def test_duplicate_holidays_are_collapsed() -> None:
    payload = {"CM": [{"tradingDate": "26-Jan-2026"}, {"tradingDate": "26-Jan-2026"}]}
    assert parse_holidays(payload) == (date(2026, 1, 26),)


def test_holidays_come_back_sorted(calendar_2026: TradingCalendar, payload: dict) -> None:
    parsed = parse_holidays(payload)
    assert list(parsed) == sorted(parsed)


def test_empty_calendar_is_refused() -> None:
    with pytest.raises(CalendarError, match="no holidays"):
        TradingCalendar.from_holidays([])


def test_load_calendar_reports_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(CalendarError, match="not found"):
        load_calendar(tmp_path / "absent.json")


def test_load_calendar_reports_a_non_json_file(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("<html>403</html>", encoding="utf-8")
    with pytest.raises(CalendarError, match="Could not read"):
        load_calendar(path)


def test_calendar_is_immutable(calendar_2026: TradingCalendar) -> None:
    """A frozen dataclass over frozensets: nothing downstream can edit the market's days."""
    with pytest.raises(Exception):
        calendar_2026.holidays = frozenset()  # type: ignore[misc]
