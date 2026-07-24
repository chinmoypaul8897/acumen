"""Recovery + durability tests for the 2026-07-25 power-loss incident (REVIEW_2 F6).

A power cut during the operator's 25-year backfill truncated three files that all had valid
names: ``ledger.parquet`` ("magic bytes not found"), the month parquet being written
(``daily/2009/bhavcopy_2009-03.parquet``), and the raw archive CSV for that date (87 KB of
spaces). That is F6 exactly: ``os.replace`` was durable while the data behind it was not.

Two things are proven here:

* **durability** -- every atomic write now ``fsync``s the file's data to disk BEFORE the
  rename, so the incident's "valid name over un-flushed bytes" cannot recur; and
* **recovery** -- a corrupt ledger raises a clear error naming ``--rebuild-ledger`` instead of
  a raw pyarrow traceback, and that command reconstructs the ledger from the surviving monthly
  parquets: present dates come back file-present, everything else returns to pending.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

from acumen import backfill_daily
from acumen.atomic_io import atomic_write_bytes, atomic_write_with
from acumen.bhavcopy import (
    FORMAT_ARCHIVE,
    FORMAT_UDIFF,
    OUTCOME_ERROR,
    OUTCOME_NOT_FOUND,
    OUTCOME_PRESENT,
    DailyRow,
    DateOutcome,
    url_for,
)
from acumen.daily_store import (
    REBUILT_LEDGER_REASON,
    DailyStore,
    DailyStoreError,
)


# --- helpers ---------------------------------------------------------------------------


def _row(day: date, symbol: str = "TCS", *, series: str = "EQ", fmt: str = FORMAT_ARCHIVE) -> DailyRow:
    return DailyRow(
        trade_date=day,
        symbol=symbol,
        series=series,
        open_paise=10000,
        high_paise=11000,
        low_paise=9000,
        close_paise=10500,
        volume=1234,
        source_format=fmt,
    )


def _store_with_two_months(root: Path) -> DailyStore:
    """A store with rows in two months (archive-format Jan-2009, udiff-format Aug-2024)."""
    store = DailyStore.at(root)
    for d in (date(2009, 1, 5), date(2009, 1, 6), date(2009, 1, 7)):
        store.write_rows(d, [_row(d, fmt=FORMAT_ARCHIVE), _row(d, symbol="RELIANCE", fmt=FORMAT_ARCHIVE)])
    for d in (date(2024, 8, 1), date(2024, 8, 2)):
        store.write_rows(d, [_row(d, fmt=FORMAT_UDIFF)])
    return store


# --- 1. durability: fsync before rename (the fix for F6) -------------------------------


def test_atomic_write_with_fsyncs_the_file_before_the_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The F6 fix, asserted via monkeypatch: the writer's bytes reach disk BEFORE os.replace.

    Without this ordering a power cut can leave the rename durable and the data not -- which is
    precisely what corrupted the store on 2026-07-25.
    """
    order: list[str] = []
    real_fsync, real_replace = os.fsync, os.replace

    def spy_fsync(fd: int) -> None:
        order.append("fsync")
        real_fsync(fd)

    def spy_replace(src: object, dst: object) -> None:
        order.append("replace")
        real_replace(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr("acumen.atomic_io.os.fsync", spy_fsync)
    monkeypatch.setattr("acumen.atomic_io.os.replace", spy_replace)

    target = tmp_path / "sub" / "part.parquet"
    atomic_write_with(target, lambda temp: temp.write_bytes(b"payload"))

    assert target.read_bytes() == b"payload"
    assert "fsync" in order, "the temp file's data was never fsynced"
    assert order.index("fsync") < order.index("replace"), "fsync must precede the rename"


def test_atomic_write_bytes_also_fsyncs_before_the_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[str] = []
    real_fsync, real_replace = os.fsync, os.replace
    monkeypatch.setattr("acumen.atomic_io.os.fsync", lambda fd: (order.append("fsync"), real_fsync(fd))[1])
    monkeypatch.setattr(
        "acumen.atomic_io.os.replace",
        lambda src, dst: (order.append("replace"), real_replace(src, dst))[1],
    )
    atomic_write_bytes(tmp_path / "f.bin", b"data")
    assert order.index("fsync") < order.index("replace")


def test_a_failed_fsync_does_not_corrupt_the_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If fsync itself raises, the previous good file must survive and no temp is left."""
    target = tmp_path / "f.parquet"
    atomic_write_bytes(target, b"GOOD-ORIGINAL")

    def _boom(fd: int) -> None:
        raise OSError("disk gone")

    monkeypatch.setattr("acumen.atomic_io.os.fsync", _boom)
    with pytest.raises(OSError, match="disk gone"):
        atomic_write_with(target, lambda temp: temp.write_bytes(b"NEW"))

    assert target.read_bytes() == b"GOOD-ORIGINAL"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["f.parquet"]


# --- 2. startup integrity: a corrupt ledger raises clear guidance ----------------------


def test_a_corrupt_ledger_raises_a_clear_error_naming_rebuild_not_a_pyarrow_traceback(
    tmp_path: Path,
) -> None:
    store = _store_with_two_months(tmp_path / "store")
    store.record_outcomes([DateOutcome(trade_date=date(2009, 1, 5), outcome=OUTCOME_PRESENT)])

    # simulate the power-loss truncation: a valid name over bytes that are not a parquet
    store.ledger_path.write_bytes(b"PAR1 then power died -- not a real footer")

    with pytest.raises(DailyStoreError) as excinfo:
        store.outcomes()
    message = str(excinfo.value)
    assert "--rebuild-ledger" in message
    assert "REVIEW_2 F6" in message or "F6" in message
    assert str(store.root) in message, "the message must name the store to pass to --store"
    # it must NOT be a bare pyarrow error type leaking through
    assert "Traceback" not in message


def test_main_turns_the_corrupt_ledger_into_a_clean_nonzero_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A normal run over a corrupt ledger exits 2 with guidance, never a raw traceback."""
    store = _store_with_two_months(tmp_path / "store")
    store.record_outcomes([DateOutcome(trade_date=date(2009, 1, 5), outcome=OUTCOME_PRESENT)])
    store.ledger_path.write_bytes(b"not a parquet")

    code = backfill_daily.main(
        ["--from", "2009-01-01", "--to", "2009-01-31", "--store", str(store.root), "--allow-network"]
    )
    out = capsys.readouterr().out
    assert code == 2
    assert "--rebuild-ledger" in out


# --- 3. recovery: rebuild the ledger from the surviving monthlies ----------------------


def test_rebuild_marks_present_dates_and_returns_all_others_to_pending(tmp_path: Path) -> None:
    store = _store_with_two_months(tmp_path / "store")
    # a pre-incident ledger that also "knew" a 404 and an error -- knowledge we will lose
    store.record_outcomes(
        [
            DateOutcome(trade_date=date(2009, 1, 5), outcome=OUTCOME_PRESENT),
            DateOutcome(trade_date=date(2009, 1, 8), outcome=OUTCOME_NOT_FOUND),  # a holiday
            DateOutcome(trade_date=date(2009, 1, 9), outcome=OUTCOME_ERROR),
        ]
    )
    store.ledger_path.write_bytes(b"truncated")  # the incident

    summary = store.rebuild_ledger_from_monthlies()

    recovered = store.outcomes()  # reads the freshly-written ledger back
    present = {d for d, o in recovered.items() if o.outcome == OUTCOME_PRESENT}
    assert present == {
        date(2009, 1, 5), date(2009, 1, 6), date(2009, 1, 7),
        date(2024, 8, 1), date(2024, 8, 2),
    }
    # the lost 404 and error are NOT invented back -- they are simply absent (pending again)
    assert date(2009, 1, 8) not in recovered
    assert date(2009, 1, 9) not in recovered
    # pending_dates now re-offers exactly the non-present in-range dates
    pending = store.pending_dates(date(2009, 1, 5), date(2009, 1, 9))
    assert date(2009, 1, 8) in pending and date(2009, 1, 9) in pending
    assert date(2009, 1, 5) not in pending

    # provenance + fidelity of the recovered rows
    jan5 = recovered[date(2009, 1, 5)]
    assert jan5.source_format == FORMAT_ARCHIVE
    assert jan5.url == url_for(date(2009, 1, 5), FORMAT_ARCHIVE)
    assert jan5.row_count == 2  # TCS + RELIANCE
    assert jan5.reason == REBUILT_LEDGER_REASON
    assert recovered[date(2024, 8, 1)].source_format == FORMAT_UDIFF

    assert summary["dates_present"] == 5
    assert summary["by_format"] == {FORMAT_ARCHIVE: 3, FORMAT_UDIFF: 2}
    assert summary["monthlies_unreadable"] == []


def test_rebuild_skips_a_corrupt_month_and_returns_its_dates_to_pending(tmp_path: Path) -> None:
    store = _store_with_two_months(tmp_path / "store")
    corrupt_month = store.month_path(date(2009, 1, 1))
    assert corrupt_month.is_file()
    corrupt_month.write_bytes(b"power died mid-write -- not a parquet")

    summary = store.rebuild_ledger_from_monthlies()

    recovered = store.outcomes()
    # the good (Aug-2024) month is recovered; the corrupt (Jan-2009) one is not
    assert set(recovered) == {date(2024, 8, 1), date(2024, 8, 2)}
    assert date(2009, 1, 5) not in recovered
    assert len(summary["monthlies_unreadable"]) == 1
    assert "2009-01" in summary["monthlies_unreadable"][0]


def test_rebuild_from_a_store_with_a_quarantined_month(tmp_path: Path) -> None:
    """The real recovery flow: the corrupt month is MOVED to quarantine first, then rebuild."""
    store = _store_with_two_months(tmp_path / "store")
    quarantine = store.root / "_quarantine" / "2026-07-25"
    quarantine.mkdir(parents=True)
    month = store.month_path(date(2009, 1, 1))
    month.rename(quarantine / month.name)  # quarantine (move, never delete)
    store.ledger_path.write_bytes(b"truncated")

    store.rebuild_ledger_from_monthlies()

    recovered = store.outcomes()
    assert set(recovered) == {date(2024, 8, 1), date(2024, 8, 2)}
    # the quarantined month's dates are pending again and will re-fetch on resume
    assert date(2009, 1, 5) in store.pending_dates(date(2009, 1, 1), date(2009, 1, 31))
    # and the quarantined file is untouched, not deleted
    assert (quarantine / month.name).is_file()


def test_rebuild_writes_a_ledger_readable_by_the_normal_path(tmp_path: Path) -> None:
    """Recovery must leave a ledger the ordinary run can read -- close the loop."""
    store = _store_with_two_months(tmp_path / "store")
    store.ledger_path.write_bytes(b"corrupt")
    store.rebuild_ledger_from_monthlies()
    # no exception, and coverage/summary work again
    assert store.coverage_summary(date(2009, 1, 1), date(2024, 8, 31))[OUTCOME_PRESENT] == 5


# --- 4. the CLI recovery command -------------------------------------------------------


def test_rebuild_ledger_cli_needs_no_dates_or_network_and_recovers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = _store_with_two_months(tmp_path / "store")
    store.ledger_path.write_bytes(b"truncated by power loss")

    # note: no --from/--to and no --allow-network -- recovery is offline and range-free
    code = backfill_daily.run(
        backfill_daily.parse_args(["--rebuild-ledger", "--store", str(store.root)])
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "REBUILDING the ledger" in out
    assert "dates -> file-present: 5" in out
    assert DailyStore.at(store.root).coverage_summary(
        date(2009, 1, 1), date(2024, 8, 31)
    )[OUTCOME_PRESENT] == 5


def test_rebuild_ledger_cli_reports_a_skipped_corrupt_month(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = _store_with_two_months(tmp_path / "store")
    store.month_path(date(2009, 1, 1)).write_bytes(b"garbage")
    store.ledger_path.write_bytes(b"garbage")

    code = backfill_daily.run(
        backfill_daily.parse_args(["--rebuild-ledger", "--store", str(store.root)])
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "monthlies unreadable : 1" in out
    assert "dates -> file-present: 2" in out  # only the Aug-2024 month survives


def test_a_normal_run_without_dates_asks_for_them_or_rebuild(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = backfill_daily.run(
        backfill_daily.parse_args(["--store", str(tmp_path / "store"), "--allow-network"])
    )
    out = capsys.readouterr().out
    assert code == 2
    assert "--from and --to are required" in out
    assert "--rebuild-ledger" in out
