"""THE MORNING REFRESH (chunk 13, pre-09:15), and the two rulings that bind it.

Nothing here re-tests a fetch or a parser -- every step drives a reviewed module. What is tested
is the SEQUENCE and the two disciplines the live path is the first unattended consumer of:

* **QUESTIONS.md Q-19** -- a bhavcopy 404 for a file that has not been published yet is recorded
  as a CONFIRMED non-trading day, which shifts ``bias_pair(D)`` for the next trading day too. The
  runbook's answer is "end at the last COMPLETED trading day, never at today". At 08:45 with
  nobody watching, that has to be code.
* **the C5 duty** -- live takes non-standard sessions from the PUBLISHED NSE calendar; the store
  scan stays the backtest cross-check. Both readings are computed and which one GOVERNS is
  stated, not inferred.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from acumen import live_refresh as refresh
from acumen.calendar import TradingCalendar
from acumen.live_recording import CALENDAR_PUBLISHED

#: A small, explicit 2026 holiday list -- enough to make the weekday rule non-trivial.
HOLIDAYS_2026 = (date(2026, 1, 26), date(2026, 3, 4), date(2026, 8, 15))


def published(today: date = date(2026, 8, 7)) -> TradingCalendar:
    return TradingCalendar.from_holidays(HOLIDAYS_2026, covered_years=(today.year,))


def holiday_cache(tmp_path: Path, today: date) -> Path:
    """A day-cache the offline ``fetch_calendar`` will serve without touching the network."""
    from acumen.calendar import cache_path

    path = cache_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "fetched_on": today.isoformat(),
            "payload": {"CM": [
                {"tradingDate": day.strftime("%d-%b-%Y")} for day in HOLIDAYS_2026
            ]},
        }),
        encoding="utf-8",
    )
    return tmp_path


# --- Q-19: the ceiling -------------------------------------------------------------------------


def test_the_topup_ceiling_is_the_last_COMPLETED_trading_day_never_today() -> None:
    """Q-19, the whole finding in one function.

    Strictly before today, ALWAYS -- even when today is a trading day and even after the close,
    because the bhavcopy for a session is published after it and a 404 for a file that has not
    arrived yet is indistinguishable from a 404 for a day that had no session. One day of lag
    costs the screener nothing: CONTEXT 3.2's bias pair is (D-1, D-2) and both are complete.
    """
    calendar = published()
    # a Friday -> the Thursday before it
    assert refresh.last_completed_trading_day(calendar, date(2026, 8, 7)) == date(2026, 8, 6)
    # a Monday -> the FRIDAY before it, skipping the weekend
    assert refresh.last_completed_trading_day(calendar, date(2026, 8, 10)) == date(2026, 8, 7)
    # the day AFTER a holiday -> back past the holiday (15-Aug-2026 is a Saturday holiday, so
    # Monday the 17th pairs back to Friday the 14th)
    assert refresh.last_completed_trading_day(calendar, date(2026, 8, 17)) == date(2026, 8, 14)
    # and it never returns today, on any day of the year this calendar covers
    day = date(2026, 1, 5)
    while day <= date(2026, 12, 20):
        assert refresh.last_completed_trading_day(calendar, day) < day
        day += timedelta(days=1)


def test_the_daily_topup_ENDS_at_that_ceiling_and_the_window_is_reported(tmp_path: Path) -> None:
    """The ceiling, as the argv the backfill actually receives -- not as a claim about it."""
    seen: list[list[str]] = []

    step = refresh.refresh_daily_store(
        store=None, calendar=published(), today=date(2026, 8, 7),
        runner=lambda argv: (seen.append(argv), 0)[1],
    )
    assert step.ok
    assert seen == [["--from", "2026-07-27", "--to", "2026-08-06"]]
    assert step.figures["q19_ceiling"] == "2026-08-06"
    assert "never 2026-08-07" in step.detail, (
        "the report says out loud that it stopped short of today, so an operator reading the "
        "preflight sees the Q-19 discipline rather than having to know about it"
    )


def test_a_topup_that_would_reach_TODAY_is_REFUSED(tmp_path: Path) -> None:
    """The guard is in ``refresh_daily_store`` as well as in the ceiling function.

    Belt and braces on purpose: the ceiling cannot produce a bad window, and the guard is there
    so that a FUTURE caller computing the ceiling some other way cannot either. Q-19 is exactly
    the kind of defect that comes back through a door nobody was watching.
    """
    class TodayCalendar:
        def prev_trading_day(self, day):
            return day  # a wrong calendar, which is the point

    with pytest.raises(refresh.RefreshError, match="Q-19"):
        refresh.refresh_daily_store(
            store=None, calendar=TodayCalendar(), today=date(2026, 8, 7),
            runner=lambda argv: 0,
        )


def test_a_failed_topup_makes_the_whole_refresh_NOT_READY(tmp_path: Path) -> None:
    """There is no partial success: a screener that starts behind a stale store computes
    yesterday's bias for every stock and never says so."""
    good = refresh.RefreshStep(name="a", ok=True, detail="")
    bad = refresh.RefreshStep(name="b", ok=False, detail="the download failed")
    assert refresh.RefreshReport(day=date(2026, 8, 7), steps=(good, good)).ok
    report = refresh.RefreshReport(day=date(2026, 8, 7), steps=(good, bad))
    assert not report.ok
    rendered = report.render()
    assert "NOT READY -- the screener must not start" in rendered
    assert "[FAIL] b" in rendered and "[ok  ] a" in rendered


# --- C5: which calendar governs ------------------------------------------------------------------


def test_the_PUBLISHED_calendar_GOVERNS_and_the_store_scan_is_the_cross_check(
    tmp_path: Path,
) -> None:
    """The C5 duty, executed and stated.

    The published endpoint is the only calendar that can answer for TODAY at all -- a derived
    calendar refuses an incomplete year by construction, which is the division of labour
    ``TradingCalendar.from_daily_store`` documents. So it governs, and the step says which source
    governed rather than leaving a reader to infer it from which one is present.
    """
    today = date(2026, 8, 7)
    calendar, step = refresh.refresh_calendar(
        cache_dir=holiday_cache(tmp_path, today), today=today, allow_network=False
    )
    assert step.ok
    assert step.figures["governing_source"] == CALENDAR_PUBLISHED
    assert "backtest cross-check" in step.figures["cross_check_source"]
    assert calendar.source == "published"
    assert calendar.is_trading_day(today) and calendar.is_standard_session(today)
    assert step.figures["holidays_this_year"] == len(HOLIDAYS_2026)
    assert "published calendar governs" in step.detail


def test_a_store_scan_DISAGREEMENT_is_reported_and_never_resolved_here(tmp_path: Path) -> None:
    """A cross-check that quietly overruled the published calendar would be a second calendar.

    NSE's occasional weekend sessions are exactly where the two readings part company (Q-5
    excludes them; the published weekday rule never saw them). The step counts the disagreement
    and hands it on; deciding it is not a screener's business.
    """
    today = date(2026, 8, 7)

    class DerivedStub:
        """Stands in for the daily store, deriving a calendar that disagrees on one day."""

    def fake_from_range(store, start, end):
        return TradingCalendar(
            holidays=frozenset(HOLIDAYS_2026),
            covered_years=frozenset({2026}),
            # the published calendar calls 2026-08-05 (a Wednesday) a trading day; this one
            # does not -- one disagreement, and it must surface
            trading_days=frozenset({date(2026, 8, 4), date(2026, 8, 6)}),
            covered_days=frozenset({date(2026, 8, 4), date(2026, 8, 5), date(2026, 8, 6)}),
            excluded_weekend_sessions=frozenset({date(2026, 8, 1)}),
            source="derived",
        )

    import acumen.calendar as cal_module

    original = cal_module.TradingCalendar.from_daily_store_range
    cal_module.TradingCalendar.from_daily_store_range = staticmethod(fake_from_range)
    try:
        _calendar, step = refresh.refresh_calendar(
            cache_dir=holiday_cache(tmp_path, today), today=today,
            allow_network=False, daily_store=DerivedStub(),
        )
    finally:
        cal_module.TradingCalendar.from_daily_store_range = original

    assert step.figures["cross_check_disagreements"] == ["2026-08-05"]
    assert step.figures["cross_check_weekend_sessions"] == ["2026-08-01"]
    assert "DISAGREES on 1 day(s)" in step.detail
    assert step.ok, "a disagreement is REPORTED; it is not this job's to resolve"


# --- the CA pull -----------------------------------------------------------------------------------


def test_an_ex_date_ON_todays_bias_pair_is_called_out_by_name() -> None:
    """The card's own reason for the step: *"a split effective TODAY must be known before
    computing bias"*.

    An ordinary stale CA cache costs nothing. A cache that missed today's split is a wrong bias
    on every stock it touches -- so the step does not merely pull, it says which symbols have an
    ex-date on or beside the pair CONTEXT 3.2 is about to read.
    """
    from acumen.corp_actions import CorporateAction

    today = date(2026, 8, 7)
    events = (
        CorporateAction(symbol="AAA", ex_date=date(2026, 8, 7), subject="Bonus 1:2", source="nse"),
        CorporateAction(symbol="BBB", ex_date=date(2026, 8, 6), subject="Split", source="nse"),
        CorporateAction(symbol="CCC", ex_date=date(2026, 7, 30), subject="Dividend", source="nse"),
        CorporateAction(symbol="ZZZ", ex_date=date(2026, 8, 7), subject="Bonus", source="nse"),
    )
    step = refresh.refresh_corporate_actions(
        symbols=("AAA", "BBB", "CCC"), today=today,
        puller=lambda start, end, **kwargs: events,
    )
    assert step.ok
    assert step.figures["events_total"] == 4
    assert step.figures["events_for_universe"] == 3, "ZZZ is not in the universe"
    named = {row["symbol"] for row in step.figures["ex_dates_near_the_bias_pair"]}
    assert named == {"AAA", "BBB"}, "CCC's ex-date is eight days back and does not touch the pair"
    assert "AAA, BBB" in step.detail


# --- the whole job ------------------------------------------------------------------------------------


def test_the_refresh_runs_every_step_and_a_broken_one_does_not_stop_the_rest(
    tmp_path: Path,
) -> None:
    """A pre-open job that abandoned itself at the first failure would tell the operator about
    one problem when there are three. Every step runs; the REPORT is the AND."""
    today = date(2026, 8, 7)

    def exploding(argv):
        raise RuntimeError("the archive is down")

    _cal, universe, report = refresh.morning_refresh(
        today=today, store=None, cache_dir=holiday_cache(tmp_path, today),
        allow_network=False, symbols=("AAA", "BBB"), daily_runner=exploding,
    )
    names = [step.name for step in report.steps]
    assert names == [
        "calendar (published NSE)", "universe (F&O underlyings)",
        "daily store (bhavcopy top-up)", "corporate actions",
    ]
    assert universe == ("AAA", "BBB")
    assert not report.ok
    failed = {step.name: step for step in report.steps if not step.ok}
    assert "daily store (bhavcopy top-up)" in failed
    assert "the archive is down" in failed["daily store (bhavcopy top-up)"].detail
    # The CA step ALSO fails here, and honestly so: this test runs offline with no CA day-cache,
    # so the reviewed chunk-3 fetcher refuses rather than serving an empty event list. That is
    # the property under test -- the job did not abandon itself at the first failure, and the
    # operator is told about both problems in one preflight instead of one per restart.
    assert "corporate actions" in failed
    assert len(report.steps) == 4
    assert "NOT READY" in report.render()
