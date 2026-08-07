"""The REPLAY CONTRACT (chunk 13): what a live day owes the harness that will check it.

CONTEXT section 6 promises no backtest/live drift. Chunk 14 is the session that has to PROVE it
on a real morning, and it can only prove what the day wrote down. So these tests attack the
recording as an evidence file rather than as a data structure: does it survive a crash, can a
resumed session continue the same bytes, is a vendor revision visible, and can a later reader
say "this is the day I replayed" and be believed.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from acumen.live_recording import (
    FETCH_ERROR,
    FETCH_OK,
    FETCH_SKIPPED,
    FetchOutcome,
    LiveRecording,
    RecordedAlert,
    RecordingError,
)
from acumen.minute_store import StoredBar

DAY = date(2026, 7, 17)


def bar(minute: int, close: int = 200_000, volume: int = 100, symbol: str = "SYNTH") -> StoredBar:
    return StoredBar(
        symbol=symbol,
        stamp=datetime(DAY.year, DAY.month, DAY.day, 9, 15) + timedelta(minutes=minute),
        open_paise=close, high_paise=close, low_paise=close, close_paise=close, volume=volume,
    )


def manifest() -> dict:
    return {
        "trade_date": DAY.isoformat(), "mode": "replay", "spec_version": "v1.9",
        "code_sha": "a" * 40, "config_digest": "b" * 64,
        "master_file": "OpenAPIScripMaster_2026-07-31.json", "master_sha256": "c" * 64,
        "row_size": 24,
    }


def test_a_recording_round_trips_every_bar_it_was_given(tmp_path: Path) -> None:
    """The floor: what went in comes out, as :class:`StoredBar`, ready for the engines.

    The type matters as much as the values. A recording that came back as dicts would need an
    adapter between it and :meth:`acumen.signal_engine.SignalPipeline.gate_day`, and an adapter
    is exactly where backtest/live drift would live.
    """
    rec = LiveRecording.at(tmp_path / "day")
    rec.open_session(manifest())
    rec.record_bars("SYNTH", [bar(0), bar(1), bar(2)], sweep="11:15", at=datetime(2026, 7, 17, 11, 15))

    got = rec.bars("SYNTH", DAY)
    assert [b.stamp.minute for b in got] == [15, 16, 17]
    assert all(isinstance(b, StoredBar) for b in got)
    assert rec.symbols() == ("SYNTH",)


def test_a_re_poll_resolves_to_the_LATEST_answer_and_the_change_is_NOT_silent(
    tmp_path: Path,
) -> None:
    """CONTEXT 4.4 re-polls the whole session at every boundary, so a stamp is served many times.

    Two rules, and the second is the one that matters: the LATEST answer wins (it is what the
    screener acted on), and a stamp whose VALUES moved between polls is reported as a revision.
    A screener that silently took the newer bytes would have made a decision the recording could
    not explain -- which is the one failure a replay contract exists to prevent.
    """
    rec = LiveRecording.at(tmp_path / "day")
    rec.open_session(manifest())
    rec.record_bars("SYNTH", [bar(0, close=200_000)], sweep="11:15", at=datetime(2026, 7, 17, 11, 15))
    rec.record_bars("SYNTH", [bar(0, close=200_000)], sweep="11:30", at=datetime(2026, 7, 17, 11, 30))
    rec.record_bars("SYNTH", [bar(0, close=200_400)], sweep="11:45", at=datetime(2026, 7, 17, 11, 45))

    got = rec.bars("SYNTH", DAY)
    assert len(got) == 1 and got[0].close_paise == 200_400, "the vendor's latest answer wins"

    revisions = rec.revisions("SYNTH")
    assert len(revisions) == 1, "an identical re-poll is not a revision; a changed one is"
    assert revisions[0].first[3] == 200_000 and revisions[0].later[3] == 200_400
    # and the raw sequence survived: three lines, not one
    assert sum(1 for _ in rec.candle_path("SYNTH").read_text().splitlines()) == 3


def test_the_recording_REFUSES_to_resume_under_a_different_machine(tmp_path: Path) -> None:
    """A recording that describes two machines can be replayed against neither.

    The same discipline :meth:`acumen.backtest.BacktestRunner._resume_state` applies to a moved
    code SHA, for the same reason: half a day computed under one instrument master and half
    under another is not a day, it is two.
    """
    rec = LiveRecording.at(tmp_path / "day")
    rec.open_session(manifest())
    rec.open_session(manifest())  # an identical resume is silent

    moved = dict(manifest(), master_sha256="d" * 64)
    with pytest.raises(RecordingError, match="different machine"):
        rec.open_session(moved)

    for field, value in (("code_sha", "z" * 40), ("row_size", 25), ("spec_version", "v1.8")):
        with pytest.raises(RecordingError, match="different machine"):
            rec.open_session(dict(manifest(), **{field: value}))


def test_every_fetch_ATTEMPT_is_recorded_including_the_ones_that_failed(tmp_path: Path) -> None:
    """A sweep that silently shrank is the failure this file exists to make impossible.

    CONTEXT 4.4's skip-and-return means a symbol can be dropped from a sweep by design. The
    design is fine; a drop nobody can count is not. So the error, the skip and the success are
    all rows, and a reader can partition the sweep.
    """
    rec = LiveRecording.at(tmp_path / "day")
    rec.open_session(manifest())
    at = datetime(2026, 7, 17, 11, 30)
    rec.record_fetch(FetchOutcome(symbol="A", sweep="11:30", outcome=FETCH_OK, bars=120, at=at))
    rec.record_fetch(FetchOutcome(symbol="B", sweep="11:30", outcome=FETCH_ERROR, bars=0, at=at,
                                  detail="access denied"))
    rec.record_fetch(FetchOutcome(symbol="B", sweep="11:30", outcome=FETCH_SKIPPED, bars=0, at=at))

    rows = rec.fetches()
    assert [row["outcome"] for row in rows] == [FETCH_OK, FETCH_ERROR, FETCH_SKIPPED]
    assert {row["symbol"] for row in rows} == {"A", "B"}
    with pytest.raises(RecordingError, match="Unknown fetch outcome"):
        rec.record_fetch(FetchOutcome(symbol="A", sweep="11:30", outcome="fine", bars=0, at=at))


def test_an_alert_is_recorded_with_its_WHOLE_payload(tmp_path: Path) -> None:
    """CONTEXT 4.4's payload list is the trader's decision. It is stored whole, not summarised."""
    rec = LiveRecording.at(tmp_path / "day")
    rec.open_session(manifest())
    payload = {"side": "long", "entry_paise": 200_100, "stop_paise": 199_900,
               "target_paise": 200_700, "poc_paise": "200005", "bias": "bullish", "qty": 500}
    rec.record_alert(RecordedAlert(kind="trigger", symbol="SYNTH",
                                   at=datetime(2026, 7, 17, 11, 30), payload=payload))
    got = rec.alerts()
    assert len(got) == 1
    assert got[0]["payload"] == payload, "every field CONTEXT 4.4 names survives the round trip"
    assert got[0]["at"] == "2026-07-17T11:30:00"


def test_the_digest_MOVES_when_any_byte_of_the_recording_moves(tmp_path: Path) -> None:
    """What makes a recording quotable. Chunk 14 will name a digest; it has to mean something."""
    rec = LiveRecording.at(tmp_path / "day")
    rec.open_session(manifest())
    rec.record_bars("SYNTH", [bar(0)], sweep="11:15", at=datetime(2026, 7, 17, 11, 15))
    before = rec.digest()
    assert before == rec.digest(), "and it is stable when nothing moves"

    rec.record_bars("SYNTH", [bar(1)], sweep="11:30", at=datetime(2026, 7, 17, 11, 30))
    assert rec.digest() != before


def test_the_records_are_JSON_one_per_line_with_no_python_in_them(tmp_path: Path) -> None:
    """A replay contract a future reader cannot parse without this package is not a contract.

    Every line is plain JSON with sorted keys, so ``diff`` between two recordings is readable
    and a reader outside this repo needs nothing but a JSON parser.
    """
    rec = LiveRecording.at(tmp_path / "day")
    rec.open_session(manifest())
    rec.record_bars("SYNTH", [bar(0)], sweep="11:15", at=datetime(2026, 7, 17, 11, 15))
    rec.record_event("sweep-opened", at=datetime(2026, 7, 17, 11, 15), detail="1 symbol")

    for path in (rec.candle_path("SYNTH"), rec.events_path):
        for line in path.read_text(encoding="utf-8").splitlines():
            parsed = json.loads(line)
            assert isinstance(parsed, dict)
            assert list(parsed) == sorted(parsed), "keys are sorted, so two recordings diff cleanly"
    assert json.loads(rec.manifest_path.read_text(encoding="utf-8"))["row_size"] == 24


def test_a_tz_aware_stamp_can_never_enter_a_recording(tmp_path: Path) -> None:
    """CONTEXT 7-E8: everything in this repo is naive IST. A recording is not an exception."""
    from datetime import timezone

    rec = LiveRecording.at(tmp_path / "day")
    rec.open_session(manifest())
    aware = StoredBar(
        symbol="SYNTH", stamp=datetime(2026, 7, 17, 9, 15, tzinfo=timezone.utc),
        open_paise=1, high_paise=1, low_paise=1, close_paise=1, volume=1,
    )
    rec.record_bars("SYNTH", [aware], sweep="11:15", at=datetime(2026, 7, 17, 11, 15))
    with pytest.raises(RecordingError, match="tz-aware"):
        rec.bars("SYNTH", DAY)


def test_the_state_file_is_whole_and_atomic_and_the_bars_are_NOT_in_it(tmp_path: Path) -> None:
    """The resume design, asserted: state.json is a summary; the CANDLES are the truth.

    Restoring bars from a summary would mean the resumed screener ran on a different day from
    the one it recorded. The candle files are append-only precisely so the resume can re-read
    them rather than trust a snapshot of them.
    """
    rec = LiveRecording.at(tmp_path / "day")
    rec.open_session(manifest())
    rec.write_state({"trade_date": DAY.isoformat(), "sweeps_done": ["11:15"], "states": {}})
    state = rec.read_state()
    assert state["sweeps_done"] == ["11:15"]
    assert "bars" not in state and "candles" not in state
    rec.write_state({"trade_date": DAY.isoformat(), "sweeps_done": ["11:15", "11:30"],
                     "states": {}})
    assert rec.read_state()["sweeps_done"] == ["11:15", "11:30"], "a rewrite replaces, atomically"


def test_the_inventory_is_what_the_session_report_prints(tmp_path: Path) -> None:
    """The recording can describe itself, so a report does not have to count files by hand."""
    rec = LiveRecording.at(tmp_path / "day")
    rec.open_session(manifest())
    rec.record_bars("SYNTH", [bar(0), bar(1)], sweep="11:15", at=datetime(2026, 7, 17, 11, 15))
    rec.record_alert(RecordedAlert(kind="armed", symbol="SYNTH",
                                   at=datetime(2026, 7, 17, 11, 15), payload={}))
    rec.record_event("sweep-closed", at=datetime(2026, 7, 17, 11, 15))
    rec.write_bias({"SYNTH": {"bias": "bullish"}})

    inv = rec.inventory()
    assert inv["symbols"] == 1 and inv["candle_lines"] == 2
    assert inv["alerts"] == 1 and inv["events"] == 1
    assert inv["has_manifest"] and inv["has_bias"]
    assert len(inv["digest"]) == 64
