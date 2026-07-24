"""Tests for the operator-facing backfill script (scripts/backfill_daily.py).

The script is the only part of chunk 2 a human drives, and the human in question will start
a run that takes hours and may Ctrl-C it. Two behaviours therefore have to be right before
anything else:

* **it cannot touch the network by accident** -- no ``--allow-network``, no requests, and
  that is asserted here rather than trusted (the same opt-in discipline as chunk-1 B2);
* **it resumes correctly** -- a settled date is never re-fetched, and an ``error`` date IS,
  because an error means "unknown", not "no file" (QUESTIONS.md Q-3 safeguard 1).

Since REVIEW_2 Finding 12 the implementation is a real module inside the package
(:mod:`acumen.backfill_daily`) and ``scripts/backfill_daily.py`` is a thin launcher, so these
tests import it normally instead of loading a file by path.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

from acumen import backfill_daily
from acumen.bhavcopy import OUTCOME_ERROR, OUTCOME_NOT_FOUND, OUTCOME_PRESENT, DateOutcome
from acumen.daily_store import DailyStore

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backfill_daily.py"


@pytest.fixture(scope="module")
def backfill() -> ModuleType:
    return backfill_daily


def _store_with(tmp_path: Path, outcomes: dict[date, str]) -> DailyStore:
    store = DailyStore.at(tmp_path / "store")
    store.record_outcomes(
        [DateOutcome(trade_date=day, outcome=name) for day, name in outcomes.items()]
    )
    return store


def test_the_script_exists_and_parses_the_documented_arguments(backfill: ModuleType) -> None:
    args = backfill.parse_args(
        ["--from", "2000-01-01", "--to", "2026-07-24", "--store", "data/x", "--allow-network"]
    )
    assert (args.start, args.end, args.store, args.allow_network) == (
        "2000-01-01",
        "2026-07-24",
        "data/x",
        True,
    )
    assert args.min_interval == 2.0, "the card's politeness rule is the DEFAULT, not a flag"


def test_nothing_is_fetched_without_the_network_flag(
    backfill: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """conftest.py would fail this test at the socket if the script tried anyway."""
    exit_code = backfill.run(
        backfill.parse_args(
            ["--from", "2026-07-13", "--to", "2026-07-24", "--store", str(tmp_path / "s")]
        )
    )
    assert exit_code == 0
    assert "no --allow-network" in capsys.readouterr().out
    assert not (tmp_path / "s").exists(), "a refused run must not create the store either"


def test_a_dry_run_lists_the_pending_dates_and_writes_nothing(
    backfill: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = backfill.run(
        backfill.parse_args(
            [
                "--from", "2026-07-13", "--to", "2026-07-15",
                "--store", str(tmp_path / "s"),
                "--allow-network", "--dry-run",
            ]
        )
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "to attempt   : 3" in out
    assert "2026-07-13, 2026-07-14, 2026-07-15" in out
    assert not (tmp_path / "s").exists()


def test_resume_skips_settled_dates_and_retries_errors(
    backfill: ModuleType, tmp_path: Path
) -> None:
    """The resume rule in one assertion: present and 404 are done, error is not."""
    store = _store_with(
        tmp_path,
        {
            date(2026, 7, 13): OUTCOME_PRESENT,
            date(2026, 7, 14): OUTCOME_ERROR,
            date(2026, 7, 18): OUTCOME_NOT_FOUND,
        },
    )
    pending = backfill.resolve_dates(
        store, date(2026, 7, 13), date(2026, 7, 18), retry_errors=True
    )
    assert pending == [date(2026, 7, d) for d in (14, 15, 16, 17)]


def test_no_retry_errors_leaves_the_error_date_alone(
    backfill: ModuleType, tmp_path: Path
) -> None:
    """The escape hatch for an operator who knows a date is permanently broken."""
    store = _store_with(tmp_path, {date(2026, 7, 14): OUTCOME_ERROR})
    pending = backfill.resolve_dates(
        store, date(2026, 7, 13), date(2026, 7, 15), retry_errors=False
    )
    assert pending == [date(2026, 7, 13), date(2026, 7, 15)]


def test_a_fully_settled_range_does_no_work(
    backfill: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = _store_with(
        tmp_path,
        {
            date(2026, 7, 13): OUTCOME_PRESENT,
            date(2026, 7, 14): OUTCOME_PRESENT,
        },
    )
    exit_code = backfill.run(
        backfill.parse_args(
            [
                "--from", "2026-07-13", "--to", "2026-07-14",
                "--store", str(store.root),
                "--allow-network",
            ]
        )
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Nothing to do" in out
    assert "file-present   : 2" in out


def test_the_summary_warns_that_errors_are_not_holidays(
    backfill: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """QUESTIONS.md Q-3 safeguard 1, said out loud to the operator who will read this."""
    store = _store_with(
        tmp_path,
        {date(2026, 7, 13): OUTCOME_PRESENT, date(2026, 7, 14): OUTCOME_ERROR},
    )
    backfill._print_summary(store, date(2026, 7, 13), date(2026, 7, 14))
    out = capsys.readouterr().out
    assert "error          : 1" in out
    assert "NOT holidays" in out


def test_the_summary_counts_weekend_sessions_as_exclusions(
    backfill: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """QUESTIONS.md Q-5: "the backtest report counts these exclusions" -- so the run that
    ingests one has to say so, or the operator never learns the day was dropped."""
    saturday = date(2019, 6, 1)
    assert saturday.weekday() == 5
    store = _store_with(
        tmp_path, {date(2019, 5, 31): OUTCOME_PRESENT, saturday: OUTCOME_PRESENT}
    )
    backfill._print_summary(store, date(2019, 5, 31), saturday)
    out = capsys.readouterr().out
    assert "weekend session: 1" in out
    assert "EXCLUDED" in out and "Q-5" in out


def test_the_summary_surfaces_unknown_series_for_universe_symbols(
    backfill: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """QUESTIONS.md Q-4's last clause: unknown series are REPORTED, with what carries them.

    The symbol list is passed in explicitly -- a printer that quietly loaded the cached F&O
    universe would make this section depend on the operator's machine.
    """
    from acumen.bhavcopy import FORMAT_UDIFF, Download, parse_bhavcopy

    fixture = (
        Path(__file__).resolve().parent / "fixtures" / "series_edge_cases_synthetic.csv"
    ).read_text(encoding="utf-8")
    rows = parse_bhavcopy(fixture, FORMAT_UDIFF)
    store = DailyStore.at(tmp_path / "store")
    for day in sorted({row.trade_date for row in rows}):
        same_day = tuple(row for row in rows if row.trade_date == day)
        store.ingest(
            Download(
                DateOutcome(
                    trade_date=day,
                    outcome=OUTCOME_PRESENT,
                    source_format=FORMAT_UDIFF,
                    row_count=len(same_day),
                ),
                same_day,
            )
        )

    backfill._print_summary(
        store, date(2026, 7, 14), date(2026, 7, 15), symbols=["ODDSERIES", "DEBTONLY"]
    )
    out = capsys.readouterr().out
    assert "unknown series : 1" in out
    assert "ODDSERIES" in out and "Q1" in out

    backfill._print_summary(store, date(2026, 7, 14), date(2026, 7, 15))
    assert "not checked (no cached F&O universe" in capsys.readouterr().out


def test_the_launcher_forwards_to_the_packaged_module_and_runs_nothing_on_import() -> None:
    """REVIEW_2 Finding 12: scripts/ holds a launcher now, not the implementation."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "from acumen.backfill_daily import main" in source
    assert "def run(" not in source and "def parse_args(" not in source
    assert source.count("sys.path.insert") == 1, "only the un-installed fallback remains"
    assert "def _load_main" in source
    body_before_guard = source.split('if __name__ == "__main__":')[0]
    assert "sys.path.insert" in body_before_guard.split("def _load_main")[1], (
        "the insert must live INSIDE the function, not at module level"
    )
