"""Tests for the crash-safe write helper (src/acumen/atomic_io.py).

This module exists because of docs/reviews/REVIEW_1.md Finding 2: the chunk-1 day-cache was
written in place, so an interrupted write left a truncated file that even a refetch could not
repair. Chunk 2 writes far more than a small JSON file -- a 25-year parquet store and its
outcome ledger, produced by a job the operator is explicitly told to interrupt -- so the
property being tested here is the one that keeps that store trustworthy: after any failure,
the target is either untouched or complete, and nothing is left lying beside it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from acumen import atomic_io
from acumen.atomic_io import atomic_write_bytes, atomic_write_text, atomic_write_with


def test_bytes_round_trip_and_parents_are_created(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "file.bin"
    assert atomic_write_bytes(target, b"\x00\x01payload") == target
    assert target.read_bytes() == b"\x00\x01payload"


def test_text_round_trips_as_utf8(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    atomic_write_text(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_an_existing_file_is_replaced_whole(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    atomic_write_text(target, "a much longer previous version\n")
    atomic_write_text(target, "short\n")
    assert target.read_text(encoding="utf-8") == "short\n"


def test_no_temp_debris_is_left_behind(tmp_path: Path) -> None:
    atomic_write_text(tmp_path / "file.txt", "content")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["file.txt"]


def test_a_failed_rename_leaves_the_previous_file_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point: a crash during the write must not destroy the good copy."""
    target = tmp_path / "file.txt"
    atomic_write_text(target, "the good version\n")

    def _crash(src: object, dst: object) -> None:
        raise OSError("no space left on device")

    monkeypatch.setattr(os, "replace", _crash)
    with pytest.raises(OSError, match="no space left"):
        atomic_write_text(target, "the doomed version\n")

    assert target.read_text(encoding="utf-8") == "the good version\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["file.txt"]


def test_a_transiently_denied_rename_is_retried_and_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows refuses ``os.replace`` while another process (an antivirus scanner, the search
    indexer) holds an open handle to the TARGET, and it clears in milliseconds. Measured live: the
    chunk-5B quarantine-recovery reroute rewrites ~1,500 month parquets for one symbol in a tight
    loop and one rename in tens of thousands was denied, killing an hours-long run.

    Retrying is safe because the temp file is already complete and fsynced -- only the atomic step
    repeats. The previous contents survive until it lands.
    """
    target = tmp_path / "file.txt"
    atomic_write_text(target, "the good version\n")
    real_replace = os.replace
    calls: list[int] = []

    def _denied_twice(src: object, dst: object) -> None:
        calls.append(1)
        if len(calls) <= 2:
            raise PermissionError(5, "Access is denied")
        real_replace(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "replace", _denied_twice)
    monkeypatch.setattr(atomic_io, "_RENAME_BACKOFF_SECONDS", 0.0)  # no sleeping in tests
    atomic_write_text(target, "the new version\n")

    assert len(calls) == 3, "retried twice, then landed"
    assert target.read_text(encoding="utf-8") == "the new version\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["file.txt"], "no temp debris"


def test_a_persistently_denied_rename_still_raises_and_keeps_the_good_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The retry is bounded. A denial that never clears is a REAL fault (a read-only file, a lost
    ACL) and must reach the caller, not be swallowed after a few attempts."""
    target = tmp_path / "file.txt"
    atomic_write_text(target, "the good version\n")
    calls: list[int] = []

    def _always_denied(src: object, dst: object) -> None:
        calls.append(1)
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(os, "replace", _always_denied)
    monkeypatch.setattr(atomic_io, "_RENAME_BACKOFF_SECONDS", 0.0)
    with pytest.raises(PermissionError):
        atomic_write_text(target, "the doomed version\n")

    assert len(calls) == atomic_io._RENAME_ATTEMPTS
    assert target.read_text(encoding="utf-8") == "the good version\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["file.txt"]


def test_a_keyboard_interrupt_mid_write_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ctrl-C is the interruption the operator is TOLD to use on the backfill run."""
    target = tmp_path / "file.txt"

    def _interrupt(src: object, dst: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "replace", _interrupt)
    with pytest.raises(KeyboardInterrupt):
        atomic_write_text(target, "half a file")

    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_write_with_hands_the_writer_a_temp_path_in_the_target_directory(
    tmp_path: Path,
) -> None:
    """For libraries that insist on writing to a filename themselves (pyarrow)."""
    seen: list[Path] = []

    def _writer(path: Path) -> None:
        seen.append(path)
        path.write_bytes(b"parquet-ish")

    target = tmp_path / "store" / "part.parquet"
    assert atomic_write_with(target, _writer) == target
    assert target.read_bytes() == b"parquet-ish"
    assert seen[0].parent == target.parent, "temp must share the filesystem for os.replace"
    assert seen[0] != target


def test_write_with_discards_the_temp_file_when_the_writer_raises(tmp_path: Path) -> None:
    target = tmp_path / "part.parquet"
    target.write_bytes(b"previous")

    def _writer(path: Path) -> None:
        path.write_bytes(b"half")
        raise ValueError("serialization blew up")

    with pytest.raises(ValueError, match="blew up"):
        atomic_write_with(target, _writer)

    assert target.read_bytes() == b"previous"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["part.parquet"]
