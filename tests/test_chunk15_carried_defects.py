"""CHUNK 15, PART A: the defects REVIEW_14 and REVIEW_14B left standing, each with its test.

One section per carried finding, named after the finding so a later reader can walk the reviews
and the suite side by side:

* **R1** (MAJOR, REVIEW_14B PART 4) -- ``_poll``'s guard stopped before the merge-and-record
  block, so three of seven malformed one-minute shapes still ended the morning. The architect's
  15-Aug-2026 note calls that an under-prescription rather than a regression and assigns the
  completion here. All seven shapes are driven through ``run_day``; so is the reachable cause,
  a per-symbol candle file that cannot be written at 11:30.
* **M4** (REVIEW_13, upgraded by REVIEW_14 H8) -- ``close_day``'s 15:30 poll was an ordinary
  sweep, so a feed that healed after the close published a full TRIGGER to the screen, the bell
  and the phone. Both halves are proved: no NEW trade is created from post-15:29 bars, and the
  post-session poll annunciates nothing.
* **M13 / M14** (REVIEW_14) -- the morning-after verified ``prev_trading_day`` only, and within
  that day ``live_recordings[-1]`` only. Proved on two stacked unverified days.
* **M25** (REVIEW_13) -- ``_fifteen``'s function-local aggregation import. The tripwire that
  makes the hoist worth doing lives in ``tests/test_live_replay_invariant.py``; what is here is
  the behavioural half.
* **L1-L4** (REVIEW_14B) -- the four LOW notes.

Every test drives the shipped path. The ones that need stores build a COPY (never a link --
CLAUDE.md data-store safety) through ``test_review14_fix.build_scratch_world``, so no byte under
the real ``data_root`` or ``cache_root`` can move.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from acumen import live_refresh as refresh
from acumen import live_screener as ls
from acumen import telegram_sink as tg
from acumen.calendar import TradingCalendar
from acumen.config import load_config
from acumen.live_recording import (
    FETCH_UNREADABLE,
    LiveRecording,
    RecordedAlert,
)
from acumen.minute_store import MinuteStore, StoredBar

from test_review14_fix import (  # the reviewed scratch-world builder, not a second copy of it
    DAY,
    SYMBOL,
    _bias,
    _pipeline,
    build_scratch_world,
    _stores_or_skip,
)

REPO = Path(__file__).resolve().parents[1]

#: Ten REAL F&O names, so the day's instrument master can price all ten. One real session fanned
#: out under ten names is what makes the nine healthy symbols genuinely evaluable, which is the
#: only way "one symbol did not cost the morning" can be measured rather than asserted.
FANOUT: tuple[str, ...] = (
    "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS",
    "RELIANCE", "AXISBANK", "ITC", "LT", "WIPRO",
)
POISONED: str = "ITC"


@pytest.fixture(scope="module")
def world(tmp_path_factory) -> Path:
    """One copied world per module run -- ~65 MB, and every test here only reads it."""
    _stores_or_skip()
    return build_scratch_world(tmp_path_factory.mktemp("chunk15-world"))


def _real_day(world: Path) -> tuple[StoredBar, ...]:
    config = load_config(world, include_env=False)
    store = MinuteStore.at(config.path("data_root") / "minute_store")
    bars = tuple(store.minutes(SYMBOL, DAY))
    if not bars:
        pytest.skip("the local minute lake does not hold the probe day")
    return bars


def _screener(world: Path, root: Path, source, *, symbols=FANOUT, sinks=None):
    """A LIVE-posture screener over ``symbols``, wired exactly as ``build_live_screener`` wires
    one, with the pipeline and bias pinned so the probe measures the SWEEP and nothing else."""
    config = load_config(world, include_env=False)
    sink = ls.CollectingAlertSink()
    recording = LiveRecording.at(root)
    screener = ls.LiveScreener(
        day=DAY, symbols=tuple(symbols),
        pipeline=_pipeline(config),
        biases={symbol: _bias(config, DAY) for symbol in symbols},
        gates={}, source=source, recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        sinks=(sink,) if sinks is None else tuple(sinks),
        risk_per_trade_paise=100_000, cost_paise=10_000,
        posture=ls.POSTURE_LIVE, dry_run=True,
    )
    recording.open_session(
        {"trade_date": DAY.isoformat(), "mode": "live", "symbols": list(symbols)}
    )
    return screener, sink, recording


# --- R1: the guard covers the WHOLE per-symbol body ---------------------------------------------

#: REVIEW_14B's own census, re-derived here as executable shapes. ``channel`` is where the shape
#: is CONTAINED now: ``gates`` (no exception at all -- CONTEXT 4.5 refuses the day), ``evaluate``
#: (M19's guard, closed by chunk 14), ``intake`` (R1's guard, closed here). The three ``intake``
#: rows are the three the re-review measured ESCAPING ``run_day`` entirely.
MALFORMED: tuple[tuple[str, str], ...] = (
    ("next-day stray stamp", "evaluate"),
    ("high below low", "gates"),
    ("negative volume", "gates"),
    ("sub-minute stamp", "gates"),
    ("tz-aware stamp", "intake"),
    ("close_paise is None", "intake"),
    ("volume is None", "intake"),
)


def _poison(shape: str, bar: StoredBar) -> StoredBar:
    """One malformed 1-minute bar, in REVIEW_14B's own seven shapes."""
    if shape == "next-day stray stamp":
        return replace(bar, stamp=bar.stamp - timedelta(days=1))
    if shape == "high below low":
        return replace(bar, high_paise=bar.low_paise - 1)
    if shape == "negative volume":
        return replace(bar, volume=-1)
    if shape == "sub-minute stamp":
        return replace(bar, stamp=bar.stamp + timedelta(seconds=30))
    if shape == "tz-aware stamp":
        return replace(bar, stamp=bar.stamp.replace(tzinfo=timezone(timedelta(hours=5,
                                                                             minutes=30))))
    if shape == "close_paise is None":
        return replace(bar, close_paise=None)  # type: ignore[arg-type]
    if shape == "volume is None":
        return replace(bar, volume=None)  # type: ignore[arg-type]
    raise AssertionError(shape)


@pytest.mark.parametrize("shape,channel", MALFORMED, ids=[row[0] for row in MALFORMED])
def test_R1_every_malformed_shape_in_the_census_is_CONTAINED(
    world: Path, tmp_path: Path, shape: str, channel: str
) -> None:
    """REVIEW_14B **R1**: all seven shapes, one symbol of ten, driven through ``run_day``.

    Measured by that re-review on the reviewed tip: four were contained (one by M19's new
    evaluation guard, three by the gates raising nothing at all) and **three escaped ``run_day``
    entirely** -- a tz-AWARE stamp raising ``TypeError`` in ``merge_bars``, and
    ``close_paise=None`` or ``volume=None`` raising ``TypeError`` in ``record_bars``. An escape
    is not one lost symbol: it is 0 of 18 sweeps, no dashboard, no banner, and a restart that
    resumes into the same raise.

    The property asserted for all seven is the same one CONTEXT 4.4 states for a symbol that will
    not answer -- the morning finishes, the other nine are evaluated at every boundary, and the
    poisoned one is either refused by the gates or NAMED as unevaluated. Never an escape.
    """
    real = _real_day(world)
    poison = _poison(shape, real[0])

    class _Fanout:
        def fetch(self, symbol: str, day: date, upto: datetime):
            bars = tuple(bar for bar in real if bar.stamp <= upto)
            if symbol == POISONED and bars:
                return (poison,) + bars
            return bars

    screener, sink, recording = _screener(world, tmp_path / "rec", _Fanout())
    reports = screener.run_day()          # <- the escape, if there is one, happens here

    # 1. THE MORNING SURVIVED -- every boundary, including close_day's 15:30 poll.
    assert len(reports) == 18 and len(screener.sweeps_done) == 18

    # 2. The other nine are evaluated at every one of the eighteen sweeps.
    healthy = [symbol for symbol in FANOUT if symbol != POISONED]
    for report in reports:
        assert set(report.unevaluated) <= {POISONED}, report.boundary
        assert report.evaluated >= len(healthy), report.boundary
    for symbol in healthy:
        assert screener.states[symbol].phase != ls.PHASE_SKIPPED, symbol

    # 3. The poisoned symbol is contained through the channel the census names, and only that one.
    events = recording.events()
    intake = [row for row in events if row["kind"] == ls.EVENT_INTAKE_FAILED]
    evaluation = [row for row in events if row["kind"] == ls.EVENT_EVALUATION_FAILED]
    if channel == "intake":
        assert intake, "R1's guard did not fire -- this is one of the three that used to escape"
        assert all(row["symbol"] == POISONED for row in intake)
        assert "could not be taken in" in intake[0]["detail"]
        assert POISONED in screener.banner and "NOT being watched" in screener.banner
        assert not evaluation, "it never reached the evaluation, so it must not say it did"
        unreadable = [
            row for row in recording.fetches() if row["outcome"] == FETCH_UNREADABLE
        ]
        assert unreadable and unreadable[0]["symbol"] == POISONED, (
            "an unreadable reply is its own outcome, not an `error` hidden in the feed's noise"
        )
    elif channel == "evaluate":
        assert evaluation and not intake
        assert POISONED in screener.banner
    else:
        assert not intake and not evaluation, (
            "the gates refuse this shape without raising, exactly as the census measured"
        )
        assert all(report.unevaluated == () for report in reports)


def test_R1_a_record_bars_IO_failure_at_1130_loses_ONE_BOUNDARY_not_the_morning(
    world: Path, tmp_path: Path
) -> None:
    """R1's reachable cause, in its own words: *"a locked or unwritable candle file for one
    symbol at 11:30 on a Windows laptop, which would take the whole morning down"*.

    Chosen over the malformed-bar shapes because those are out of reach of the shipped vendor
    source (``smartapi_client.parse_candles`` drops the tzinfo and refuses a non-paise price from
    INSIDE the call the old guard already wrapped) and this one is not: it needs no vendor
    misbehaviour at all, only an antivirus scanner holding one file open for a second.

    It is TRANSIENT here on purpose. The morning must not merely survive: the symbol must come
    back at 11:45 under its own steam, which is what tells a one-boundary loss apart from a
    permanent one.
    """
    real = _real_day(world)

    class _Fanout:
        def fetch(self, symbol: str, day: date, upto: datetime):
            return tuple(bar for bar in real if bar.stamp <= upto)

    class _LockedAt1130(LiveRecording):
        """One symbol's candle file cannot be written, at one boundary, once."""

        def __init__(self, root: Path) -> None:
            super().__init__(root=Path(root))
            self.blocked = 0

        def record_bars(self, symbol, bars, *, sweep, at):
            if symbol == POISONED and sweep == "11:30":
                self.blocked += 1
                raise OSError(13, "the candle file is locked by another process")
            return super().record_bars(symbol, bars, sweep=sweep, at=at)

    config = load_config(world, include_env=False)
    recording = _LockedAt1130(tmp_path / "rec-locked")
    sink = ls.CollectingAlertSink()
    screener = ls.LiveScreener(
        day=DAY, symbols=FANOUT, pipeline=_pipeline(config),
        biases={symbol: _bias(config, DAY) for symbol in FANOUT},
        gates={}, source=_Fanout(), recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        sinks=(sink,), risk_per_trade_paise=100_000, cost_paise=10_000,
        posture=ls.POSTURE_LIVE, dry_run=True,
    )
    recording.open_session(
        {"trade_date": DAY.isoformat(), "mode": "live", "symbols": list(FANOUT)}
    )

    seen: list[tuple[str, tuple[str, ...], str]] = []
    reports = screener.run_day(on_sweep=lambda report: seen.append((
        report.boundary.strftime("%H:%M"), report.unevaluated,
        screener.states[POISONED].phase,
    )))

    assert len(reports) == 18, "the morning finished"
    by_sweep = {label: (unevaluated, phase) for label, unevaluated, phase in seen}

    # 1. ONE boundary lost, and it is the one whose file could not be written.
    assert by_sweep["11:30"][0] == (POISONED,)
    assert by_sweep["11:30"][1] == ls.PHASE_SKIPPED
    assert [label for label, unevaluated, _phase in seen if unevaluated] == ["11:30"], (
        "every other boundary is complete for every symbol"
    )

    # 2. ...and the symbol comes BACK on its own at the next boundary.
    assert by_sweep["11:45"][0] == ()
    assert by_sweep["11:45"][1] != ls.PHASE_SKIPPED

    # 3. The failure was not retried inside the boundary: the bars are already in hand, and a
    #    second identical intake would re-record the whole prefix under one sweep label -- which
    #    `LiveRecording.duplicate_bars` hands to gate 2 as twins.
    assert recording.blocked == 1, f"the intake was retried {recording.blocked} time(s)"
    assert recording.duplicate_bars(POISONED, DAY) == (), (
        "a fix that made tomorrow's verification refuse the day would be worse than the defect"
    )

    # 4. It is on disk, by name, with the boundary and the exception on it.
    intake = [row for row in recording.events() if row["kind"] == ls.EVENT_INTAKE_FAILED]
    assert len(intake) == 1
    assert intake[0]["symbol"] == POISONED and intake[0]["sweep"] == "11:30"
    # `OSError(13, ...)` IS a PermissionError -- the exception's own class, recorded, rather than
    # the base one the test happened to construct.
    assert intake[0]["error"] == "PermissionError"
    assert "locked by another process" in intake[0]["detail"]

    # 5. And the nine healthy symbols never noticed.
    assert all(report.evaluated >= len(FANOUT) - 1 for report in reports)


def test_R1_the_intake_records_are_BEST_EFFORT_when_the_recording_is_what_failed(
    world: Path, tmp_path: Path
) -> None:
    """The branch's own reachable cause is the recording, so its reporting cannot depend on it.

    A recording whose ``record_bars`` AND whose ``record_fetch``/``record_event`` all fail is the
    unwritable-directory case. Losing the line that describes the failure is not a reason to lose
    the morning: the banner still names the symbol and the state still says it is not watched.
    """
    real = _real_day(world)

    class _Fanout:
        def fetch(self, symbol: str, day: date, upto: datetime):
            return tuple(bar for bar in real if bar.stamp <= upto)

    class _Unwritable(LiveRecording):
        def record_bars(self, symbol, bars, *, sweep, at):
            if symbol == POISONED:
                raise OSError(13, "read-only file system")
            return super().record_bars(symbol, bars, sweep=sweep, at=at)

        def record_fetch(self, outcome):
            if outcome.symbol == POISONED and outcome.outcome == FETCH_UNREADABLE:
                raise OSError(13, "read-only file system")
            return super().record_fetch(outcome)

        def record_event(self, kind, *, at, detail="", **fields):
            if kind == ls.EVENT_INTAKE_FAILED:
                raise OSError(13, "read-only file system")
            return super().record_event(kind, at=at, detail=detail, **fields)

    config = load_config(world, include_env=False)
    recording = _Unwritable(root=tmp_path / "rec-unwritable")
    screener = ls.LiveScreener(
        day=DAY, symbols=FANOUT, pipeline=_pipeline(config),
        biases={symbol: _bias(config, DAY) for symbol in FANOUT},
        gates={}, source=_Fanout(), recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        sinks=(ls.CollectingAlertSink(),),
        risk_per_trade_paise=100_000, cost_paise=10_000,
        posture=ls.POSTURE_LIVE, dry_run=True,
    )
    recording.open_session(
        {"trade_date": DAY.isoformat(), "mode": "live", "symbols": list(FANOUT)}
    )
    reports = screener.run_day()

    assert len(reports) == 18
    assert all(report.unevaluated == (POISONED,) for report in reports)
    assert POISONED in screener.banner and "NOT being watched" in screener.banner
    assert screener.states[POISONED].phase == ls.PHASE_SKIPPED
    assert not [row for row in recording.events() if row["kind"] == ls.EVENT_INTAKE_FAILED], (
        "the recording really did refuse its own failure line, which is the case under test"
    )


# --- M4: nothing is announced after the close ---------------------------------------------------


def test_M4_no_NEW_trade_is_created_from_post_1529_bars(world: Path, tmp_path: Path) -> None:
    """M4's first half, and the reason it is a disclosure defect and not a strategy one.

    The decision a full day produces must be BYTE-IDENTICAL with and without bars stamped after
    15:29 -- ``aggregate.in_session_bars`` drops them at the candle level (CONTEXT 7-E2 / Q-17),
    so nothing after the session can reach an entry, a stop, a target or a quantity.
    """
    real = _real_day(world)
    last = real[-1].stamp
    strays = tuple(
        replace(real[0], stamp=datetime.combine(DAY, datetime.min.time()).replace(
            hour=15, minute=minute
        ), close_paise=real[0].close_paise + 10_000)
        for minute in (30, 40, 55)
    )
    assert all(stray.stamp > last for stray in strays)

    class _Clean:
        def fetch(self, symbol: str, day: date, upto: datetime):
            return tuple(bar for bar in real if bar.stamp <= upto)

    class _WithStrays:
        def fetch(self, symbol: str, day: date, upto: datetime):
            return tuple(bar for bar in real if bar.stamp <= upto) + strays

    clean, _sink, _rec = _screener(world, tmp_path / "clean", _Clean(), symbols=(SYMBOL,))
    dirty, _sink2, _rec2 = _screener(world, tmp_path / "dirty", _WithStrays(), symbols=(SYMBOL,))
    clean.run_day()
    dirty.run_day()

    a, b = clean.states[SYMBOL], dirty.states[SYMBOL]
    for field_name in ("phase", "side", "entry_paise", "stop_paise", "target_paise", "qty",
                       "exit_paise", "exit_kind", "refusal"):
        assert getattr(a, field_name) == getattr(b, field_name), field_name


def test_M4_the_post_session_poll_ANNUNCIATES_NOTHING(world: Path, tmp_path: Path) -> None:
    """M4's second half -- REVIEW_14 H8's own construction, with the phone attached.

    Measured by that review: 15:15 leaves the symbol short of its entry because the feed is
    starved, the 15:30 poll finally serves the whole session, and the screener publishes a full
    TRIGGER -- entry, stop, target, quantity -- to the screen, the bell and Telegram, half an
    hour after CONTEXT 3.4's last actionable moment.

    What must happen now: the state still moves (the recording must hold the whole session, which
    is what ``close_day`` is FOR), the move is still recorded, and NO sink receives anything.
    """
    real = _real_day(world)
    # Frozen at the POC boundary: the profile is fixed and the day ARMS, and not one 15-minute
    # candle after 11:15 ever arrives, so no cross can be consumed and 15:15 finds the symbol
    # still armed with nothing to square off. Then the whole session lands at 15:30. That is
    # REVIEW_14 H8's construction exactly -- "a feed that heals after 15:29 publishes, for the
    # first time, a trigger with all four numbers".
    frozen_at = datetime.combine(DAY, datetime.min.time()).replace(hour=11, minute=15)

    class _StarvedUntilTheClose:
        def fetch(self, symbol: str, day: date, upto: datetime):
            ceiling = upto if upto.time() >= ls.SESSION_END else frozen_at
            return tuple(bar for bar in real if bar.stamp <= min(upto, ceiling))

    sent: list[str] = []
    telegram = tg.TelegramSink(live=True, send=sent.append, out=lambda line: None)
    screener, sink, recording = _screener(
        world, tmp_path / "rec-m4", _StarvedUntilTheClose(),
        symbols=(SYMBOL,), sinks=(ls.CollectingAlertSink(), telegram),
    )
    collecting = screener.sinks[0]
    before_close: dict = {}

    def after(report):
        if report.boundary.strftime("%H:%M") == ls.LAST_BOUNDARY:
            before_close["state"] = screener.states[SYMBOL]
            before_close["alerts"] = len(collecting.alerts)

    screener.run_day(on_sweep=after)
    assert before_close["state"].phase == ls.PHASE_ARMED, (
        "the starved morning must reach 15:15 ARMED, which is H8's own setup"
    )

    withheld = [
        row for row in recording.events() if row["kind"] == ls.EVENT_POST_SESSION_ALERT
    ]
    assert withheld, (
        "this probe needs the post-session poll to actually produce an alert; the feed model "
        "starves the session and heals at 15:30, which is REVIEW_14 H8's own construction"
    )

    # 1. NOTHING left the tool after the close -- not the screen, not the bell, not the phone.
    assert len(collecting.alerts) == before_close["alerts"], (
        "a sink received an alert from the post-session poll"
    )
    assert not [text for text in sent if "15:30" in text], sent

    # 2. ...and it is not silence: the alert is on disk, whole, with the reason it was withheld.
    assert withheld[0]["symbol"] == SYMBOL
    assert "delivered to NO sink" in withheld[0]["detail"]
    assert withheld[0]["payload"], "the payload the trader would have received, recorded in full"
    assert any(
        row["alert_kind"] == ls.ALERT_TRIGGER for row in withheld
    ), "the withheld alert really is a full TRIGGER, which is what H8 measured reaching the phone"
    trigger = [row for row in withheld if row["alert_kind"] == ls.ALERT_TRIGGER][0]
    for number in ("entry_paise", "stop_paise", "target_paise", "qty"):
        assert trigger["payload"][number] is not None, number

    # 3. The state still moved and close_day still recorded that it did -- the recording holds
    #    the whole 375-minute session, which is the thing close_day exists for.
    assert screener.states[SYMBOL].phase != before_close["state"].phase
    moved = [row for row in recording.events() if row["kind"] == "post-session-state-change"]
    assert moved and SYMBOL in moved[0]["detail"]

    # 4. The end-of-day summary cannot leak it either: it reads alerts.jsonl, and a withheld
    #    alert is an EVENT, never an alert.
    from acumen.run_screener import recorded_alerts

    assert not [
        alert for alert in recorded_alerts(recording)
        if alert.at.strftime("%H:%M") == "15:30"
    ]


def test_M4_an_ordinary_day_is_UNTOUCHED_by_the_post_session_flag(
    world: Path, tmp_path: Path
) -> None:
    """The risk the flag creates, refused: a normal morning must deliver exactly what it did.

    On an ordinary day nothing moves at 15:30 -- the states are recomputed from the completed day
    and the dedup key of every alert is already spent -- so the flag must be invisible. Measured
    by comparing a full replay's delivered alerts against the recording's own alert log.
    """
    real = _real_day(world)

    class _Whole:
        def fetch(self, symbol: str, day: date, upto: datetime):
            return tuple(bar for bar in real if bar.stamp <= upto)

    screener, sink, recording = _screener(
        world, tmp_path / "rec-normal", _Whole(), symbols=(SYMBOL,)
    )
    screener.run_day()

    assert sink.alerts, "the day really produced alerts"
    assert not [
        row for row in recording.events() if row["kind"] == ls.EVENT_POST_SESSION_ALERT
    ], "nothing was withheld on a day where nothing moved after the close"
    assert len(recording.alerts()) == len(sink.alerts), (
        "every alert that was recorded was also delivered, and vice versa"
    )


# --- M13 / M14: the morning-after verifies the whole backlog -------------------------------------


def _plant_recording(
    root: Path, *, day: date, label: str, mode: str = "live", verified: bool = False
) -> LiveRecording:
    """A minimal recording on disk: manifest, one candle file, one alert. No stores needed."""
    recording = LiveRecording.at(root / f"{day.isoformat()}-{label}")
    recording.open_session({
        "trade_date": day.isoformat(), "mode": mode, "symbols": [SYMBOL],
        "master_file": "OpenAPIScripMaster_1999-01-01.json", "row_size": 24,
    })
    recording.record_bars(
        SYMBOL,
        (StoredBar(symbol=SYMBOL, stamp=datetime.combine(day, datetime.min.time()).replace(
            hour=9, minute=15), open_paise=100, high_paise=101, low_paise=99,
            close_paise=100, volume=10),),
        sweep="11:15", at=datetime.combine(day, datetime.min.time()),
    )
    recording.record_alert(RecordedAlert(
        kind=ls.ALERT_ARMED, symbol=SYMBOL,
        at=datetime.combine(day, datetime.min.time()).replace(hour=11, minute=15),
        payload={"side": "long"},
    ))
    if verified:
        recording.write_verification({"trade_date": day.isoformat(), "verdicts": []})
    return recording


def test_M13_M14_the_scan_finds_EVERY_unverified_recording_on_TWO_STACKED_DAYS(
    tmp_path: Path
) -> None:
    """REVIEW_14 **M13** and **M14** together, on the shape they were found in.

    Two live days nobody verified, the newer one holding TWO recordings because ``open_session``
    told the operator to start a second when the code sha moved mid-day. The old job would have
    produced ONE verdict, about ONE of the three, and reported READY.

    The scan is asserted on directly here because it is the whole of the fix; the step that
    drives it is asserted below.
    """
    root = tmp_path / "live"
    monday, tuesday, wednesday = date(2026, 8, 10), date(2026, 8, 11), date(2026, 8, 12)
    _plant_recording(root, day=monday, label="live")
    _plant_recording(root, day=tuesday, label="live")
    _plant_recording(root, day=tuesday, label="live-2")
    already = _plant_recording(root, day=date(2026, 8, 7), label="live", verified=True)
    _plant_recording(root, day=monday, label="replay", mode="replay")
    _plant_recording(root, day=wednesday, label="live")   # today: no oracle yet

    pending, unreadable = refresh.unverified_recordings(root, before=wednesday)

    assert unreadable == ()
    assert [p.root.name for p in pending] == [
        "2026-08-10-live", "2026-08-11-live", "2026-08-11-live-2",
    ], "both days, both of Tuesday's recordings, oldest first -- M13 and M14 in one list"
    assert already.root.name not in [p.root.name for p in pending], "a verdict empties the queue"

    # ...and each of the three filters is load-bearing, checked one at a time.
    assert [p.root.name for p in refresh.unverified_recordings(root, before=tuesday)[0]] == [
        "2026-08-10-live"
    ], "a day that is not yet past has no oracle and is not judged"
    already.verification_path.unlink()
    assert "2026-08-07-live" in [
        p.root.name for p in refresh.unverified_recordings(root, before=wednesday)[0]
    ], "and a verdict removed puts its day back on the queue"


def test_M13_an_unreadable_recording_is_REPORTED_and_never_silently_skipped(
    tmp_path: Path
) -> None:
    """A recording silently absent from the queue reads as one that passed -- M15's shape."""
    root = tmp_path / "live"
    good = _plant_recording(root, day=date(2026, 8, 10), label="live")
    broken = _plant_recording(root, day=date(2026, 8, 11), label="live")
    broken.manifest_path.write_text("{not json", encoding="utf-8")

    pending, unreadable = refresh.unverified_recordings(root, before=date(2026, 8, 12))
    assert [p.root.name for p in pending] == [good.root.root.name if False else "2026-08-10-live"]
    assert len(unreadable) == 1 and unreadable[0][0].name == "2026-08-11-live"


def test_M13_M14_the_STEP_verifies_the_whole_backlog_and_shouts_about_each_day(
    tmp_path: Path
) -> None:
    """The step, driven -- and what it does when a recording cannot be judged.

    Every recording here names a master that does not exist, so none can be judged. What is
    proved is the DISCIPLINE: all three are named, none is dropped from the queue, and the step
    fails only because one of them is the prior trading day's -- the one CONTEXT 4.7 names.
    """
    root = tmp_path / "live"
    monday, tuesday, wednesday = date(2026, 8, 10), date(2026, 8, 11), date(2026, 8, 12)
    for day, label in ((monday, "live"), (tuesday, "live"), (tuesday, "live-2")):
        _plant_recording(root, day=day, label=label)

    calendar = TradingCalendar.from_holidays((date(2026, 8, 15),), covered_years=(2026,))
    verifications, step = refresh.verify_prior_recordings(
        today=wednesday, calendar=calendar, data_root=tmp_path / "stores",
        cache_dir=tmp_path / "cache", recording_root=root,
    )

    assert verifications == ()
    assert not step.ok, "one of them IS the prior trading day's, so the morning stops"
    assert len(step.figures["not_judged"]) == 3, "all three named, none dropped"
    for name in ("2026-08-10-live", "2026-08-11-live", "2026-08-11-live-2"):
        assert name in step.detail, name
    assert step.figures["pending"] == 3
    for day, label in ((monday, "live"), (tuesday, "live"), (tuesday, "live-2")):
        assert not LiveRecording.at(
            root / f"{day.isoformat()}-{label}"
        ).read_verification(), "an unjudged day stays unjudged, and therefore stays queued"


def test_M13_an_OLD_unjudgeable_recording_does_NOT_hold_the_morning_hostage(
    tmp_path: Path
) -> None:
    """The other edge of widening the scan, and the reason the two tiers exist.

    A three-week-old recording nobody can re-judge must not stop today's bell for ever: CONTEXT
    4.7 requires the verdict to be reported loudly, not to gate the next session. So it is named,
    it stays on the queue, and the step stays green -- while the same failure on the PRIOR
    TRADING DAY's recording, which is the one 4.7 names, still stops the morning (proved above).
    """
    root = tmp_path / "live"
    _plant_recording(root, day=date(2026, 7, 20), label="live")   # three weeks back

    calendar = TradingCalendar.from_holidays((date(2026, 8, 15),), covered_years=(2026,))
    verifications, step = refresh.verify_prior_recordings(
        today=date(2026, 8, 12), calendar=calendar, data_root=tmp_path / "stores",
        cache_dir=tmp_path / "cache", recording_root=root,
    )
    assert verifications == ()
    assert step.ok, "an old artifact nobody can re-judge is not a reason to lose a morning"
    assert "NOT JUDGED and still queued" in step.detail
    assert "2026-07-20-live" in step.detail


def test_M13_the_refresh_REPORT_shouts_about_every_day_of_the_backlog() -> None:
    """The operator reads the pre-open report and often nothing else, so it carries all of them.

    ``render`` used to consult one verification. A three-day catch-up that shouted only about the
    newest would bury exactly the days nobody has looked at.
    """
    def _verification(day: date) -> refresh.MorningVerification:
        return refresh.MorningVerification(
            day=day, recording_root=f"/live/{day.isoformat()}",
            verdicts=(refresh.SymbolVerdict(
                symbol=SYMBOL, live_passed=True, live_reason="ok",
                oracle_passed=False, oracle_reason="gate 1: volume gap",
                verified=True, alerted=("armed",), minutes=375,
            ),),
        )

    report = refresh.RefreshReport(
        day=date(2026, 8, 12),
        steps=(refresh.RefreshStep(name="calendar (published NSE)", ok=True, detail="fine"),),
        verifications=tuple(_verification(day) for day in (
            date(2026, 8, 10), date(2026, 8, 11)
        )),
    )
    text = report.render()
    assert text.count("THE EXCHANGE'S RECORD REFUSES") == 2, "one loud line per day, not one"
    assert "2026-08-10" in text and "2026-08-11" in text
    assert text.index("READY") < text.index("2026-08-10")
    assert report.verification is not None and report.verification.day == date(2026, 8, 11), (
        "the single-day surfaces read the NEWEST, and it is derived rather than stored"
    )


# --- M25: the aggregation import is at module top -----------------------------------------------


def test_M25_the_live_layer_imports_its_aggregation_at_MODULE_level() -> None:
    """REVIEW_13 **M25**, the behavioural half (the tripwire is in the replay-invariant module).

    A local import in a language with module-level ones reads as a circular-import workaround,
    and here it hid a real fact: the live layer calls the aggregator directly, on the evaluation
    path, at every square-off. There was never a cycle to work around -- ``aggregate`` imports
    only ``calendar`` -- and this is that, measured rather than argued.
    """
    import ast
    import inspect

    assert ls.aggregate_15min is not None and ls.in_session_bars is not None
    body = inspect.getsource(ls.LiveScreener._fifteen)
    tree = ast.parse(__import__("textwrap").dedent(body))
    assert not [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ], "_fifteen imports nothing of its own any more"

    from acumen import aggregate

    assert not [
        line for line in Path(aggregate.__file__).read_text(encoding="utf-8").splitlines()
        if line.startswith("from .") and "live_screener" in line
    ], "there was never a cycle to work around"


# --- L1 - L4: the four LOW notes REVIEW_14B recorded --------------------------------------------


def test_L1_a_RESUMED_summary_says_which_number_is_about_what() -> None:
    """**L1**: the alert list is the day's and the counters are this process's.

    Each is right about its own subject and after a resume they read as a contradiction -- "1
    symbol(s) alerted ... telegram: 0 sent". Counting deliveries this process did not make would
    be worse; one line saying which is which is the whole remedy.
    """
    alerts = (RecordedAlert(
        kind=ls.ALERT_TRIGGER, symbol=SYMBOL, at=datetime(2026, 6, 10, 11, 30),
        payload={"side": "long", "entry_paise": 74_095, "mode": ls.POSTURE_LIVE},
    ),)
    resumed = tg.TelegramSink(live=True, send=lambda text: None, out=lambda line: None)
    message = resumed.end_of_day_message(alerts, day=DAY)
    assert "1 symbol(s) alerted" in message and "0 sent" in message
    assert tg.SUMMARY_SUBJECTS in message

    # ...and a morning that really did deliver its own alerts does NOT carry the line.
    ordinary = tg.TelegramSink(live=True, send=lambda text: None, out=lambda line: None)
    ordinary.deliver(alerts[0])
    assert tg.SUMMARY_SUBJECTS not in ordinary.end_of_day_message(alerts, day=DAY)
    assert tg.SUMMARY_SUBJECTS not in ordinary.end_of_day_message((), day=DAY)


def test_L2_a_payload_with_NO_MODE_is_not_read_as_a_live_morning() -> None:
    """**L2**: ``live`` is the only posture that carries no marker, so silence claimed the most.

    An alert recorded before B411 existed and replayed later arrived on a phone looking exactly
    like today's. Backwards compatibility is kept -- the message still goes and the trade date
    still travels -- and the ambiguity is stated instead of resolved in the flattering direction.
    """
    def _payload(**extra):
        body = {"side": "long", "entry_paise": 74_095, "dry_run": False}
        body.update(extra)
        return body

    assert tg.posture_markers(_payload()) == (tg.UNSTAMPED_MARKER,)
    assert tg.posture_markers(_payload(mode=ls.POSTURE_LIVE)) == ()
    assert tg.posture_markers(_payload(mode=ls.POSTURE_SETTLED)) == (tg.REPLAY_MARKER,)
    assert tg.posture_markers(_payload(dry_run=True)) == (
        tg.DRY_RUN_MARKER, tg.UNSTAMPED_MARKER
    )
    # ...and the SUMMARY of unstamped alerts carries it too, the same way it carries REPLAY.
    sink = tg.TelegramSink(live=True, send=lambda text: None, out=lambda line: None)
    summary = sink.end_of_day_message((RecordedAlert(
        kind=ls.ALERT_ARMED, symbol=SYMBOL, at=datetime(2026, 6, 10, 11, 15),
        payload=_payload(),
    ),), day=DAY)
    assert tg.UNSTAMPED_MARKER in summary


def test_L3_a_freshness_stamp_without_a_NUMBER_vouches_for_nothing() -> None:
    """**L3**: rule 3 needed the age to be an ``int``, so ``stale`` without it slipped all three.

    Unreachable from ``_alert``, which sets the pair together -- and a predicate that is only
    correct because of what its one caller happens to do is the shape this repo keeps being
    bitten by. Measured on the whole neighbourhood, so the fix is not a special case for ``None``.
    """
    def _alert(**payload) -> RecordedAlert:
        return RecordedAlert(kind=ls.ALERT_TRIGGER, symbol=SYMBOL,
                             at=datetime(2026, 6, 10, 11, 30), payload=payload)

    for age in (None, "1", 1.0, True, [1]):
        reason = ls.unvouched_price(_alert(entry_paise=100, stale=False,
                                           data_behind_minutes=age))
        assert reason is not None and "no NUMBER" in reason, age
    assert ls.unvouched_price(_alert(entry_paise=100, stale=False)) is not None

    # The honest shapes still pass, and the three earlier rules are unmoved.
    assert ls.unvouched_price(
        _alert(entry_paise=100, stale=False, data_behind_minutes=1)
    ) is None
    assert ls.unvouched_price(_alert(
        entry_paise=100, stale=True, data_behind_minutes=226,
        alert_states=[ls.MARKER_STALE],
    )) is None
    assert "no freshness stamp" in (ls.unvouched_price(_alert(entry_paise=100)) or "")
    assert ls.unvouched_price(_alert(detail="the screener is not answering")) is None


def test_L4_the_BLIND_branch_catches_the_absent_cache_and_NOT_a_bug(tmp_path: Path) -> None:
    """**L4**: B407's ``except Exception`` read a programming error as "no cached window".

    A real defect wearing the costume of a known, disclosed, harmless condition is the worst
    shape a report can have. The three that mean *"there is nothing on disk to read"* are caught
    and disclosed; anything else propagates and is reported by ``morning_refresh``'s own per-step
    guard as what it is.
    """
    from acumen import corp_actions as ca
    from acumen import nse_http

    data, cache = tmp_path / "data", tmp_path / "cache"
    today = date(2026, 8, 14)

    for error in (
        nse_http.NseFetchError("no cache on disk"),
        ca.CorporateActionError("the cached payload is not parseable"),
        OSError(13, "permission denied"),
    ):
        def raising(start, end, **kwargs):
            raise error

        step = refresh.refresh_corporate_actions(
            symbols=(SYMBOL,), today=today, allow_network=True, cache_dir=cache,
            puller=raising, data_root=data, cache_root=cache,
        )
        assert step.ok and "THIS REPORT IS BLIND" in step.detail, type(error).__name__
        assert type(error).__name__ in step.figures["unreadable"]

    def buggy(start, end, **kwargs):
        raise TypeError("puller() got an unexpected keyword argument 'today'")

    with pytest.raises(TypeError):
        refresh.refresh_corporate_actions(
            symbols=(SYMBOL,), today=today, allow_network=True, cache_dir=cache,
            puller=buggy, data_root=data, cache_root=cache,
        )
    assert refresh.NO_CACHED_WINDOW == (
        nse_http.NseFetchError, ca.CorporateActionError, OSError
    )
