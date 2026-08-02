"""Q-19: a bhavcopy 404 seals as a non-trading day ONLY once the date is old enough.

CONTEXT 4.6 (v1.5), the architect's ruling made law:

    "Q-19 IS LAW: a confirmed-404 bhavcopy may be SEALED as a non-trading day only when the
    date is more than 7 calendar days in the past; younger 404s record as PENDING and are
    retried."

This closes the one door QUESTIONS.md Q-3's safeguard 1 left open. Q-3 protects the ledger
from an ERROR becoming a holiday. Q-19 is the other shape entirely: nothing failed, the
server answered 404 in BOTH published formats, and the answer was simply EARLY -- the file
was not published yet. The chunk-2 double-format check cannot see it (both formats agree)
and it is not an error (nothing failed), so before this guard nothing in the pipeline caught
it.

It was MEASURED, not imagined. The Q-18 runbook smoke ran the ordinary chunk-2 command at
10:21 IST on Friday 2026-07-31 with the market open, and recorded **2026-07-31 itself** as
``confirmed-404`` -- a normal trading day sealed into the ledger as a phantom holiday. Under
Q-3 that is a settled answer meaning "not a trading day", and CONTEXT 3.2's ``bias_pair(D)``
is defined on TRADING days, so one phantom holiday shifts the (D-1, D-2) pair for the next
session too. The failure is silent and it lands on the most recent day in the store -- the
one the live screener and every fresh backtest reach first.

Until v1.5 the only protection was an operator rule in the Q-18 runbook ("--to is the last
COMPLETED trading day, never today"). The belt stays; these tests are the structure.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from acumen import bhavcopy
from acumen.bhavcopy import (
    FORMAT_ARCHIVE,
    FORMAT_UDIFF,
    MIN_SEAL_AGE_DAYS,
    OUTCOME_ERROR,
    OUTCOME_NOT_FOUND,
    OUTCOME_PENDING,
    OUTCOME_PRESENT,
    DateOutcome,
    download_bhavcopy,
    seals_as_non_trading_day,
    url_for,
)
from acumen.calendar import CalendarError, TradingCalendar
from acumen.daily_store import DailyStore

#: The Q-19 incident's own clock: Friday 2026-07-31, 10:21 IST, market open.
SMOKE_RUN = datetime(2026, 7, 31, 10, 21, 0)


class _Response:
    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content


class _AllMissing:
    """Answers 404 to everything -- the shape a not-yet-published date really has."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def get(self, url: str, timeout: float | None = None) -> Any:
        self.urls.append(url)
        return _Response(404)


class _Failing:
    """Answers 503 to everything -- a bad network afternoon, NOT a missing file."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def get(self, url: str, timeout: float | None = None) -> Any:
        self.urls.append(url)
        return _Response(503)


def _no_sleep(_seconds: float) -> None:
    return None


def _fetch(day: date, *, now: datetime, session: Any | None = None) -> bhavcopy.Download:
    return download_bhavcopy(
        day, session=session if session is not None else _AllMissing(),
        sleep=_no_sleep, max_attempts=1, now=now,
    )


# --- the predicate, on its own ----------------------------------------------------------


def test_the_seal_horizon_is_the_context_4_6_value() -> None:
    """The number is SPEC, cited where it is defined -- not a knob and not a magic literal."""
    assert MIN_SEAL_AGE_DAYS == 7


@pytest.mark.parametrize(
    "age, seals",
    [
        (-1, False),  # the future: NSE cannot have published it
        (0, False),   # today, market open -- the measured Q-19 incident
        (1, False),
        (6, False),   # the architect's named case: day 6 STAYS PENDING
        (7, False),   # the boundary: "MORE THAN 7 days in the past", so 7 is not enough
        (8, True),    # the architect's named case: day 8 SEALS
        (30, True),
        (4000, True),
    ],
)
def test_only_a_404_older_than_the_horizon_seals(age: int, seals: bool) -> None:
    run_date = date(2026, 7, 31)
    assert seals_as_non_trading_day(run_date - timedelta(days=age), run_date) is seals


# --- the download path ------------------------------------------------------------------


def test_a_404_six_days_old_stays_pending_and_is_never_confirmed() -> None:
    """Day 6, the architect's own case. It is not a holiday and it is not settled."""
    run_date = date(2026, 7, 31)
    day = run_date - timedelta(days=6)
    session = _AllMissing()

    result = _fetch(day, now=datetime.combine(run_date, datetime.min.time()), session=session)

    assert result.outcome.outcome == OUTCOME_PENDING
    assert result.outcome.outcome != OUTCOME_NOT_FOUND
    assert result.outcome.is_terminal is False, "a pending date must come back for another ask"
    assert result.outcome.http_status == 404, "what the server said is still recorded honestly"
    assert result.rows == ()
    assert "Q-19" in (result.outcome.reason or "")
    assert session.urls == [url_for(day, FORMAT_UDIFF), url_for(day, FORMAT_ARCHIVE)], (
        "both formats are still asked -- the guard changes the VERDICT, not the evidence"
    )


def test_a_404_eight_days_old_seals_as_a_non_trading_day() -> None:
    """Day 8, the architect's other case: past the horizon, the 404 is final."""
    run_date = date(2026, 7, 31)
    day = run_date - timedelta(days=8)

    result = _fetch(day, now=datetime.combine(run_date, datetime.min.time()))

    assert result.outcome.outcome == OUTCOME_NOT_FOUND
    assert result.outcome.is_terminal is True
    assert result.outcome.reason == "no published bhavcopy in either format"


def test_the_horizon_is_read_from_the_run_clock_not_from_the_wall_clock() -> None:
    """The same date is pending or sealed depending only on WHEN it was asked."""
    day = date(2026, 7, 24)
    assert _fetch(day, now=datetime(2026, 7, 28, 9, 0)).outcome.outcome == OUTCOME_PENDING
    assert _fetch(day, now=datetime(2026, 8, 5, 9, 0)).outcome.outcome == OUTCOME_NOT_FOUND


@pytest.mark.parametrize("age", [0, 3, 6, 7, 8, 40])
def test_an_error_is_never_a_holiday_and_never_pending_either(age: int) -> None:
    """QUESTIONS.md Q-3 safeguard 1 SURVIVES the new guard, at every age.

    An error and a young 404 are both retried, but they are not the same fact and the ledger
    must not blur them: one means "we could not ask", the other means "we asked too early".
    Blurring them would let a bad network afternoon masquerade as a publication lag.
    """
    run_date = date(2026, 7, 31)
    day = run_date - timedelta(days=age)

    result = _fetch(
        day, now=datetime.combine(run_date, datetime.min.time()), session=_Failing()
    )

    assert result.outcome.outcome == OUTCOME_ERROR
    assert result.outcome.outcome not in (OUTCOME_NOT_FOUND, OUTCOME_PENDING)
    assert result.outcome.is_terminal is False
    assert "503" in (result.outcome.reason or "")


def test_a_present_file_is_unaffected_by_the_horizon(tmp_path: Path) -> None:
    """The guard touches exactly one branch. A published file settles at any age."""
    import io
    import zipfile

    day = date(2026, 7, 31)
    csv = (
        "TradDt,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol\n"
        "2026-07-31,TCS,EQ,3000.00,3010.00,2990.00,3005.00,123456\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("b.csv", csv)

    class _Published(_AllMissing):
        def get(self, url: str, timeout: float | None = None) -> Any:
            self.urls.append(url)
            if url == url_for(day, FORMAT_UDIFF):
                return _Response(200, buffer.getvalue())
            return _Response(404)

    result = _fetch(day, now=SMOKE_RUN, session=_Published())
    assert result.outcome.outcome == OUTCOME_PRESENT
    assert result.outcome.is_terminal is True


# --- the measured incident, reproduced ---------------------------------------------------


def _july_2026_window() -> tuple[list[date], list[date]]:
    """The Q-19 record's own window: 2026-07-01..07-31, 22 completed trading days + 9 others."""
    days = [date(2026, 7, 1) + timedelta(days=n) for n in range(31)]
    weekends = [day for day in days if day.weekday() >= 5]
    traded = [day for day in days if day.weekday() < 5 and day != date(2026, 7, 31)]
    assert len(weekends) == 8 and len(traded) == 22, "the window this item measured"
    return traded, weekends + [date(2026, 7, 31)]


def test_the_2026_07_31_phantom_holiday_cannot_recur(tmp_path: Path) -> None:
    """The exact shape QUESTIONS.md Q-19 measured, run against the guard.

    The record: `--from 2026-07-01 --to 2026-07-31 --allow-network` at 10:21 IST on Friday
    2026-07-31 gave 22 file-present, 9 confirmed-404, 0 error -- and the 9 included
    **2026-07-31 itself**, a normal Friday whose session was in progress.

    With the guard, the same run cannot produce that row. The 31st, and the two weekend dates
    inside the seven-day window with it, come back PENDING; only the six weekend dates old
    enough to be final are sealed.
    """
    store = DailyStore.at(tmp_path / "store")
    traded, missing = _july_2026_window()
    store.record_outcomes(
        [DateOutcome(trade_date=day, outcome=OUTCOME_PRESENT, row_count=1) for day in traded]
    )
    for day in missing:
        store.ingest(_fetch(day, now=SMOKE_RUN))

    ledger = store.outcomes()
    assert ledger[date(2026, 7, 31)].outcome == OUTCOME_PENDING
    assert ledger[date(2026, 7, 31)].outcome != OUTCOME_NOT_FOUND, "the phantom holiday"

    summary = store.coverage_summary(date(2026, 7, 1), date(2026, 7, 31))
    assert summary[OUTCOME_PRESENT] == 22
    assert summary[OUTCOME_ERROR] == 0
    assert summary[OUTCOME_NOT_FOUND] == 6, "only the weekends past the seven-day horizon"
    assert summary[OUTCOME_PENDING] == 3, "2026-07-25, 07-26 and 07-31"

    assert store.pending_dates(date(2026, 7, 1), date(2026, 7, 31)) == (
        date(2026, 7, 25),
        date(2026, 7, 26),
        date(2026, 7, 31),
    ), "every unsealed date comes back on the next run, for free"


def test_a_pending_date_refuses_a_calendar_rather_than_becoming_a_holiday(
    tmp_path: Path,
) -> None:
    """The consequence that matters: CONTEXT 3.2's bias pair can never be built over it.

    A phantom holiday is dangerous precisely because it is SILENT -- the calendar builds
    happily and every pair spanning the date is one candle out. A pending date is unsettled,
    so the loader refuses outright (the same posture Q-3's safeguard 1 takes for an error).
    """
    store = DailyStore.at(tmp_path / "store")
    traded, missing = _july_2026_window()
    store.record_outcomes(
        [DateOutcome(trade_date=day, outcome=OUTCOME_PRESENT, row_count=1) for day in traded]
    )
    for day in missing:
        store.ingest(_fetch(day, now=SMOKE_RUN))

    with pytest.raises(CalendarError) as excinfo:
        TradingCalendar.from_daily_store_range(store, date(2026, 7, 1), date(2026, 7, 31))
    message = str(excinfo.value)
    assert "unsettled" in message
    assert "2026-07-31=pending" in message
    assert "Q-19" in message


def test_the_deferred_day_is_recovered_by_the_next_run_not_lost(tmp_path: Path) -> None:
    """The guard DEFERS a verdict; it never drops a date.

    Re-run a week later: the two weekend dates now seal, the 31st comes back with its real
    published file, and the calendar builds -- with 2026-07-31 a TRADING day, which is what
    it always was.
    """
    store = DailyStore.at(tmp_path / "store")
    traded, missing = _july_2026_window()
    store.record_outcomes(
        [DateOutcome(trade_date=day, outcome=OUTCOME_PRESENT, row_count=1) for day in traded]
    )
    for day in missing:
        store.ingest(_fetch(day, now=SMOKE_RUN))

    # The next run, 2026-08-08. NSE published the 31st hours after the smoke; the two young
    # weekend dates are now past the horizon and answer 404 for the last time.
    later = datetime(2026, 8, 8, 20, 0, 0)
    for day in store.pending_dates(date(2026, 7, 1), date(2026, 7, 31)):
        if day == date(2026, 7, 31):
            store.record_outcome(
                DateOutcome(trade_date=day, outcome=OUTCOME_PRESENT, row_count=1)
            )
        else:
            store.ingest(_fetch(day, now=later))

    assert store.pending_dates(date(2026, 7, 1), date(2026, 7, 31)) == ()
    calendar = TradingCalendar.from_daily_store_range(
        store, date(2026, 7, 1), date(2026, 7, 31)
    )
    assert calendar.is_trading_day(date(2026, 7, 31)) is True
    assert calendar.is_trading_day(date(2026, 7, 26)) is False, "a Sunday, sealed on the retry"
    assert calendar.bias_pair(date(2026, 7, 31)) == (date(2026, 7, 30), date(2026, 7, 29))
