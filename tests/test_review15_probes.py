"""REVIEW_15's own probes -- the attacks this review built, kept in the repo.

Nothing here re-asserts what ``tests/test_chunk15_carried_defects.py`` already pins. Every test
in this file exists because the review asked a question the build's own suite does not ask:

* **R1 / B416** -- the widened guard is judged on the two places a wider guard can buy a WORSE
  defect than it closes. A retry inside it is shown to hand CONTEXT 4.5 gate 2 the whole reply as
  twins (``duplicate_bars`` keys on ``(sweep, stamp)``, so a second ``record_bars`` under one
  label duplicates EVERY stamp), and the no-retry choice is shown to lose no data: the next
  boundary re-fetches and the recording ends the day holding exactly what a clean run holds.
* **R1 / B417** -- the ordering claim is driven rather than read. A reply carrying twins is failed
  at the ``record_event`` call that now precedes the one non-idempotent statement, and the twins
  are counted ONCE over the whole day. Under the pre-fix ordering the same day counts them twice.
* **R1, an EIGHTH shape** -- REVIEW_14B's census is the builder's own list, so this review brought
  a malformed bar and a recording failure of its OWN shape (a ``date`` where a ``datetime``
  belongs; a reviewer-defined exception class from ``record_fetch``, which is a different
  statement from the build's ``record_bars`` probe).
* **M4** -- the risk of a suppression is what it suppresses by accident. A normal day is measured
  for DELIVERY, not for silence, and the end-of-day summary is built from the recording and
  searched for the withheld payload.
* **M13 / M14 / B420** -- the "unjudged, and not yesterday" reading is attacked at its edge: a
  prior-trading-day recording that cannot say WHICH day it is.
* **the readiness gate** -- the credential hunt is run through the REAL
  :func:`acumen.telegram_sink.post_message` with a transport that raises carrying the token, and
  the gate's no-write claim is fingerprinted over both roots rather than asserted.

Store-safe: the probes that need real bars build a COPY through the reviewed
``test_review14_fix.build_scratch_world`` (CLAUDE.md data-store safety); the rest are store-free
and run on a bare clone.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from acumen import dry_run_readiness as gate
from acumen import live_refresh as refresh
from acumen import live_screener as ls
from acumen import telegram_sink as tg
from acumen.calendar import TradingCalendar
from acumen.config import load_config
from acumen.live_recording import FETCH_UNREADABLE, LiveRecording, RecordedAlert
from acumen.minute_store import MinuteStore, StoredBar

from test_review14_fix import (  # the reviewed scratch-world builder, not a second copy of it
    DAY,
    SYMBOL,
    _bias,
    _pipeline,
    _stores_or_skip,
    build_scratch_world,
)

REPO = Path(__file__).resolve().parents[1]

FANOUT: tuple[str, ...] = (
    "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS",
    "RELIANCE", "AXISBANK", "ITC", "LT", "WIPRO",
)
POISONED: str = "ITC"
BOUNDARY: str = "11:30"


class ReviewerDiskFull(RuntimeError):
    """This review's OWN failure class -- deliberately not the build's ``OSError``/``PermissionError``."""


@pytest.fixture(scope="module")
def world(tmp_path_factory) -> Path:
    _stores_or_skip()
    return build_scratch_world(tmp_path_factory.mktemp("review15-world"))


def _real_day(world: Path) -> tuple[StoredBar, ...]:
    config = load_config(world, include_env=False)
    bars = tuple(MinuteStore.at(config.path("data_root") / "minute_store").minutes(SYMBOL, DAY))
    if not bars:
        pytest.skip("the local minute lake does not hold the probe day")
    return bars


def _screener(world: Path, root: Path, source, *, symbols=FANOUT, sinks=None, recording=None):
    config = load_config(world, include_env=False)
    sink = ls.CollectingAlertSink()
    tape = recording if recording is not None else LiveRecording.at(root)
    screener = ls.LiveScreener(
        day=DAY, symbols=tuple(symbols), pipeline=_pipeline(config),
        biases={symbol: _bias(config, DAY) for symbol in symbols},
        gates={}, source=source, recording=tape,
        clock=ls.VirtualClock(stamp=datetime.combine(DAY, datetime.min.time())),
        sinks=(sink,) if sinks is None else tuple(sinks),
        risk_per_trade_paise=100_000, cost_paise=10_000,
        posture=ls.POSTURE_LIVE, dry_run=True,
    )
    tape.open_session(
        {"trade_date": DAY.isoformat(), "mode": "live", "symbols": list(symbols)}
    )
    return screener, screener.sinks[0], tape


class _Fanout:
    """One real session served under every name, truncated at the boundary asked for."""

    def __init__(self, bars: tuple[StoredBar, ...], poisoned: StoredBar | None = None) -> None:
        self.bars, self.poisoned = bars, poisoned

    def fetch(self, symbol, day, upto):
        served = tuple(bar for bar in self.bars if bar.stamp <= upto)
        if self.poisoned is not None and symbol == POISONED and served:
            return (self.poisoned,) + served
        return served


# --- R1 / B416: the no-retry decision, and what a retry would have cost --------------------------


def test_R1_B416_a_RETRY_inside_the_guard_would_hand_gate_2_the_whole_reply_as_TWINS(
    world: Path, tmp_path: Path
) -> None:
    """B416's premise, PROVED rather than argued -- and it is exact.

    ``LiveRecording.duplicate_bars`` -- the method whose answer CONTEXT 4.5 gate 2 excludes a day
    for -- keys on ``(sweep, stamp)``. So a second ``record_bars`` for the same reply under the
    SAME sweep label does not duplicate one bar: it duplicates every stamp in the reply. That is
    what a retry after a post-answer failure would do, and it is why ``_poll`` returns
    ``POLL_UNREADABLE`` instead of looping. A fix that made tomorrow's verification refuse the day
    would indeed be worse than the defect it closed.
    """
    real = _real_day(world)
    screener, _sink, recording = _screener(
        world, tmp_path / "twins", _Fanout(real), symbols=(SYMBOL,)
    )
    boundary = datetime.combine(DAY, datetime.min.time()).replace(hour=11, minute=30)

    assert screener._poll(SYMBOL, boundary, BOUNDARY) == ls.POLL_OK
    served = len(recording.bars(SYMBOL, DAY))
    assert served > 100, "the probe needs a real reply to be worth anything"
    assert recording.duplicate_bars(SYMBOL, DAY) == (), "a single intake creates no twins"

    # The retry the guard deliberately does NOT do.
    assert screener._poll(SYMBOL, boundary, BOUNDARY) == ls.POLL_OK
    twins = recording.duplicate_bars(SYMBOL, DAY)
    assert len(twins) == served, (
        "a retry under one sweep label duplicates the WHOLE reply, not one bar -- "
        f"{len(twins)} twins from a {served}-bar prefix"
    )

    # ...and the same reply arriving under the NEXT boundary's label is the design's own
    # whole-session re-pull, which is not a duplicate. The distinction B416 rests on is real.
    later = boundary + timedelta(minutes=15)
    assert screener._poll(SYMBOL, later, "11:45") == ls.POLL_OK
    assert len(recording.duplicate_bars(SYMBOL, DAY)) == served, "a later sweep adds no twins"


def test_R1_B416_the_no_retry_choice_loses_NO_DATA_over_the_morning(
    world: Path, tmp_path: Path
) -> None:
    """One boundary is lost; nothing else is. The recording ends the day byte-complete.

    The other half of B416: not retrying is only defensible if the data comes back. It does --
    ``SmartApiBarSource`` re-pulls the whole session every boundary, so the next sweep carries
    every stamp the failed one carried. Measured against a clean run of the same day.
    """
    real = _real_day(world)

    class FailsOnceAt1130(LiveRecording):
        def __init__(self, root: Path) -> None:
            super().__init__(root=Path(root))
            self.blocked = 0

        def record_bars(self, symbol, bars, *, sweep, at):
            if symbol == SYMBOL and sweep == BOUNDARY:
                self.blocked += 1
                raise ReviewerDiskFull("the reviewer's own failure, at the reviewer's own site")
            return super().record_bars(symbol, bars, sweep=sweep, at=at)

    hurt = FailsOnceAt1130(tmp_path / "hurt")
    screener, _s, _r = _screener(
        world, tmp_path / "hurt", _Fanout(real), symbols=(SYMBOL,), recording=hurt
    )
    screener.run_day()

    clean_screener, _s2, clean = _screener(
        world, tmp_path / "clean", _Fanout(real), symbols=(SYMBOL,)
    )
    clean_screener.run_day()

    assert hurt.blocked == 1, "one attempt, no retry -- the guard did not loop on the same bytes"
    assert {bar.stamp for bar in hurt.bars(SYMBOL, DAY)} == {
        bar.stamp for bar in clean.bars(SYMBOL, DAY)
    }, "the boundary was lost; the DATA was not"
    assert hurt.duplicate_bars(SYMBOL, DAY) == (), "and recovering it created no twins"
    assert clean_screener.states[SYMBOL].phase == screener.states[SYMBOL].phase, (
        "one lost intake did not move where the day ended up"
    )


# --- R1 / B417: the one non-idempotent statement is last ----------------------------------------


def _twinned(real: tuple[StoredBar, ...]) -> tuple[StoredBar, ...]:
    """A reply that serves its first stamp twice -- CONTEXT 4.5 gate 2's own trigger."""
    return (real[0],) + real


def test_R1_B417_a_crash_BETWEEN_statements_leaves_no_half_written_twin_count(
    world: Path, tmp_path: Path
) -> None:
    """The ordering claim, driven. A raise at the statement BEFORE the accumulation must not
    leave the accumulation half-applied, because the symbol is re-polled at the next boundary and
    the same twins arrive again.

    ``record_event`` (the duplicate-stamps line) is now the last thing that can raise before
    ``self.duplicate_bars[symbol] += twins``. Fail it at 11:30 and the day must still count each
    twin exactly ONCE. Under the pre-fix ordering -- accumulate, THEN record the event -- this
    same day counts them twice, because 11:30 accumulated before it died and 11:45 accumulated
    again.
    """
    real = _real_day(world)
    twinned = _twinned(real)

    class EventFailsAt1130(LiveRecording):
        def __init__(self, root: Path) -> None:
            super().__init__(root=Path(root))
            self.blocked = 0

        def record_event(self, kind, **fields):
            if kind == "duplicate-stamps" and fields.get("sweep") == BOUNDARY:
                self.blocked += 1
                raise ReviewerDiskFull("the twins line could not be written")
            return super().record_event(kind, **fields)

    tape = EventFailsAt1130(tmp_path / "b417")

    class Twins:
        def fetch(self, symbol, day, upto):
            served = tuple(bar for bar in twinned if bar.stamp <= upto)
            return (served[0],) + served if served else served

    screener, _s, _r = _screener(
        world, tmp_path / "b417", Twins(), symbols=(SYMBOL,), recording=tape
    )
    sweeps = len(screener.run_day())

    control_screener, _s2, _r2 = _screener(
        world, tmp_path / "b417-control", Twins(), symbols=(SYMBOL,)
    )
    control_screener.run_day()

    assert tape.blocked == 1, "the probe must really have failed that one statement"
    hurt = screener.duplicate_bars.get(SYMBOL, ())
    control = control_screener.duplicate_bars.get(SYMBOL, ())
    per_reply = len(control) // sweeps
    assert per_reply and len(control) == per_reply * sweeps, (
        f"the control must accumulate one reply's twins per sweep: {len(control)} over {sweeps}"
    )
    assert len(hurt) == len(control) - per_reply, (
        "the boundary that died at record_event must have contributed ZERO twins, not its own "
        f"share: {len(hurt)} vs a control of {len(control)} over {sweeps} sweeps"
    )
    assert len(hurt) != len(control), (
        "under the PRE-FIX ordering -- accumulate, then record the event -- the failed boundary "
        "accumulates before it dies and these two are equal; that is the defect B417 closes"
    )
    assert screener.states[SYMBOL].phase, "and the morning still finished"


def test_R1_B417_the_non_idempotent_statement_is_STRUCTURALLY_last(world: Path) -> None:
    """Read off the shipped AST, so a later edit that reorders it fails here and not in a market.

    B417 is a claim about statement ORDER, and an ordering that is only true today is not a
    property. The accumulation must be the final statement of ``_poll``'s guarded block.
    """
    tree = ast.parse(Path(ls.__file__).read_text(encoding="utf-8"))
    poll = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_poll"
    )
    tries = [node for node in ast.walk(poll) if isinstance(node, ast.Try)]
    assert len(tries) == 1, "one guard, covering the whole per-symbol body"
    body = tries[0].body
    accumulations = [
        index for index, stmt in enumerate(body)
        if "self.duplicate_bars[symbol]" in ast.unparse(stmt)
    ]
    assert accumulations, "the twin accumulation must live inside the guard"
    innermost = ast.unparse(body[-1])
    assert "self.duplicate_bars[symbol]" in innermost, (
        "the one non-idempotent statement is not the last one in the guarded block: "
        f"the block ends with {innermost.splitlines()[0]!r}"
    )
    tail = ast.unparse(body[-1]).splitlines()[-1]
    assert "self.duplicate_bars[symbol] = self.duplicate_bars.get" in tail, tail


# --- R1: an EIGHTH shape, and a failure site the build's own probe does not use ------------------


def test_R1_an_EIGHTH_malformed_shape_of_the_REVIEWERS_own_is_CONTAINED(
    world: Path, tmp_path: Path
) -> None:
    """REVIEW_14B's seven are the builder's list. This is not on it.

    A ``date`` where a ``datetime`` belongs: it survives the fetch, it is not any of the seven,
    and it dies inside ``merge_bars`` comparing a date to a datetime. The guard must contain it
    for the same reason it contains the other three -- because the guard covers the block, not a
    list of known shapes.
    """
    real = _real_day(world)
    eighth = replace(real[0], stamp=real[0].stamp.date())  # type: ignore[arg-type]

    screener, _sink, recording = _screener(
        world, tmp_path / "eighth", _Fanout(real, poisoned=eighth)
    )
    reports = screener.run_day()

    assert len(reports) == 18, "the morning completed"
    kinds = {row["kind"] for row in recording.events()}
    assert ls.EVENT_INTAKE_FAILED in kinds, "contained by the intake guard, by name"
    assert screener.states[POISONED].phase == ls.PHASE_SKIPPED
    healthy = [symbol for symbol in FANOUT if symbol != POISONED]
    assert all(screener.states[symbol].phase != ls.PHASE_SKIPPED for symbol in healthy), (
        "the other nine swept normally"
    )
    outcomes = {
        row["outcome"] for row in recording.fetches() if row["symbol"] == POISONED
    }
    assert FETCH_UNREADABLE in outcomes, "and the reply is on disk as unreadable, not as an error"


def test_R1_a_reviewer_defined_exception_from_record_fetch_is_ALSO_contained(
    world: Path, tmp_path: Path
) -> None:
    """A different statement and a different exception class from the build's own probe.

    The build failed ``record_bars`` with ``OSError``. This fails ``record_fetch`` -- the next
    statement -- with a class defined in this file, which nothing in ``src/`` has ever seen. It
    also drives B418 to its worst case: the machinery that must write the failure line is the
    machinery that just failed, so both best-effort recordings are refused too.
    """
    real = _real_day(world)

    class FetchLineFails(LiveRecording):
        def __init__(self, root: Path) -> None:
            super().__init__(root=Path(root))
            self.blocked = 0

        def record_fetch(self, outcome):
            if outcome.symbol == POISONED and outcome.sweep == BOUNDARY:
                self.blocked += 1
                raise ReviewerDiskFull("no outcome line can be written for this symbol")
            return super().record_fetch(outcome)

    tape = FetchLineFails(tmp_path / "myshape")
    screener, _sink, _r = _screener(
        world, tmp_path / "myshape", _Fanout(real), recording=tape
    )
    seen: dict[str, str] = {}
    reports = screener.run_day(on_sweep=lambda report: seen.setdefault(
        report.boundary.strftime("%H:%M"), screener.states[POISONED].phase
    ))

    assert len(reports) == 18, "the morning completed"
    assert tape.blocked == 2, (
        "once inside the guard and once when _intake_failed tried to describe it -- B418's "
        "own worst case"
    )
    assert seen[BOUNDARY] == ls.PHASE_SKIPPED, "skipped at ITS OWN boundary, by name"
    assert "could not be taken in" in screener.states[POISONED].detail or (
        screener.states[POISONED].phase != ls.PHASE_SKIPPED
    ), "and re-polled at the next boundary like any other symbol"
    at_1130 = [report for report in reports if report.boundary.strftime("%H:%M") == BOUNDARY]
    assert at_1130 and POISONED in at_1130[0].unevaluated, "and the banner names it"
    events = [
        row for row in tape.events()
        if row["kind"] == ls.EVENT_INTAKE_FAILED and row.get("sweep") == BOUNDARY
    ]
    assert events, "the event line survived even though the outcome line could not be written"


# --- M4: what did NOT stop being announced ------------------------------------------------------


def test_M4_a_NORMAL_days_alerts_ALL_still_reach_the_transport(
    world: Path, tmp_path: Path
) -> None:
    """The risk of a suppression is what it suppresses by accident. Measured for DELIVERY.

    Every alert this day produces is checked to have reached the Telegram transport, and the
    withheld-event log is checked to be EMPTY -- the flag is set only inside ``close_day``, so an
    ordinary boundary cannot be caught by it.
    """
    real = _real_day(world)
    sent: list[str] = []
    telegram = tg.TelegramSink(live=True, send=sent.append, out=lambda line: None)
    screener, collecting, recording = _screener(
        world, tmp_path / "normal", _Fanout(real), symbols=(SYMBOL,),
        sinks=(ls.CollectingAlertSink(), telegram),
    )
    screener.run_day()

    delivered = [alert.kind for alert in collecting.alerts]
    assert delivered, "the probe day must actually produce alerts or it measures nothing"
    assert len(sent) == len(delivered), "every alert reached the phone transport"
    recorded = [row["kind"] for row in recording.alerts()]
    assert sorted(recorded) == sorted(delivered), (
        "and the recording and the transport agree about the day"
    )
    withheld = [
        row for row in recording.events() if row["kind"] == ls.EVENT_POST_SESSION_ALERT
    ]
    assert withheld == [], "nothing of an ordinary day was withheld"
    assert screener.post_session is False, "the flag is not left set"


def test_M4_the_END_OF_DAY_SUMMARY_cannot_see_a_WITHHELD_alert(
    world: Path, tmp_path: Path
) -> None:
    """B419's load-bearing half: the summary reads the RECORDING (REVIEW_14 H2).

    So an alert withheld at 15:30 must not be written as an alert. If it were, it would reach the
    phone by the back door -- inside the one message that is sent unconditionally at the close.
    """
    real = _real_day(world)
    frozen = datetime.combine(DAY, datetime.min.time()).replace(hour=11, minute=15)

    class Starved:
        def fetch(self, symbol, day, upto):
            ceiling = upto if upto.time() >= ls.SESSION_END else frozen
            return tuple(bar for bar in real if bar.stamp <= min(upto, ceiling))

    sent: list[str] = []
    telegram = tg.TelegramSink(live=True, send=sent.append, out=lambda line: None)
    screener, _collecting, recording = _screener(
        world, tmp_path / "withheld", Starved(), symbols=(SYMBOL,),
        sinks=(ls.CollectingAlertSink(), telegram),
    )
    screener.run_day()

    withheld = [
        row for row in recording.events() if row["kind"] == ls.EVENT_POST_SESSION_ALERT
    ]
    assert withheld, "the probe needs the post-session poll to have produced something"
    assert not any(
        _parse(row["at"]).strftime("%H:%M") == "15:30" for row in recording.alerts()
    ), "a withheld alert was written into alerts.jsonl after all"

    summary = telegram.end_of_day_message(
        day=DAY, alerts=tuple(
            RecordedAlert(
                kind=row["kind"], symbol=row["symbol"], at=_parse(row["at"]),
                payload=row.get("payload") or {},
            ) for row in recording.alerts()
        ),
    )
    for row in withheld:
        payload = row.get("payload") or {}
        for key in ("entry_paise", "stop_paise", "target_paise", "qty"):
            value = payload.get(key)
            if value:
                assert str(value) not in summary, (
                    f"the withheld alert's {key} reached the end-of-day summary"
                )
    assert not any(" 15:30]" in text for text in sent), "and nothing 15:30-stamped was sent"


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(str(stamp))


# --- M13 / M14 / B420: the blocking rule, at its edge --------------------------------------------


def _plant(root: Path, day: date, label: str, *, mode: str = "live", verified: bool = False):
    recording = LiveRecording.at(root / f"{day.isoformat()}-{label}")
    recording.open_session({
        "trade_date": day.isoformat(), "mode": mode, "symbols": [SYMBOL],
        "master_file": "OpenAPIScripMaster_1999-01-01.json", "row_size": 24,
    })
    if verified:
        recording.write_verification({"trade_date": day.isoformat(), "verdicts": []})
    return recording


def _run_step(root: Path, scratch: Path, today: date, calendar: TradingCalendar):
    return refresh.verify_prior_recordings(
        today=today, calendar=calendar, data_root=scratch / "stores",
        cache_dir=scratch / "cache", recording_root=root,
    )


def test_B420_an_unjudgeable_recording_OF_THE_PRIOR_TRADING_DAY_blocks_the_morning(
    tmp_path: Path
) -> None:
    """The rule B420 states, at the boundary it states it on -- and across a weekend.

    ``today`` is a Monday, so the prior TRADING day is the Friday, not Sunday. A recording that
    cannot be judged must block when it is the Friday's and must not when it is the Thursday's.
    """
    root = tmp_path / "live"
    friday, thursday = date(2026, 8, 14), date(2026, 8, 13)
    monday = date(2026, 8, 17)
    calendar = TradingCalendar.from_holidays((date(2026, 1, 26),), covered_years=(2026,))
    assert calendar.prev_trading_day(monday) == friday

    _plant(root, friday, "live")
    _, step = _run_step(root, tmp_path, monday, calendar)
    assert step.ok is False, "the prior TRADING day's unjudgeable recording stops the morning"
    assert "NOT JUDGED and still queued" in step.detail

    for path in root.iterdir():
        for child in sorted(path.rglob("*"), reverse=True):
            child.unlink() if child.is_file() else child.rmdir()
        path.rmdir()

    _plant(root, thursday, "live")
    _, older = _run_step(root, tmp_path, monday, calendar)
    assert older.ok is True, "an older one is shouted about and does not hold the bell hostage"
    assert "NOT JUDGED and still queued" in older.detail, "...but it is still named, loudly"


def test_B420_a_prior_day_recording_that_cannot_SAY_which_day_it_is_does_NOT_block(
    tmp_path: Path
) -> None:
    """REVIEW_15 finding: the stated rule and the implemented rule part company here.

    ``unverified_recordings`` reports an unreadable manifest, and the blocking test then asks
    ``recording_day(...) == prior`` -- which for that very recording returns ``None``, because
    the manifest is what could not be read. So the ONE recording whose day is unknowable is
    treated as "not yesterday's" and the morning is READY.

    Pinned as the measured behaviour, not as the intended one. It is a corner (the manifest is
    written once, atomically, at ``open_session``), it is always NAMED and always left queued, and
    nothing about the day's decisions changes -- which is why this review records it and does not
    fail on it.
    """
    root = tmp_path / "live"
    friday, monday = date(2026, 8, 14), date(2026, 8, 17)
    calendar = TradingCalendar.from_holidays((date(2026, 1, 26),), covered_years=(2026,))
    recording = _plant(root, friday, "live")
    (recording.root / "manifest.json").write_text("{ this is not json", encoding="utf-8")

    pending, unreadable = refresh.unverified_recordings(root, before=monday)
    assert pending == (), "it cannot be judged"
    assert len(unreadable) == 1 and "manifest" in unreadable[0][1].lower() or unreadable
    assert refresh.recording_day(recording) is None, "and it cannot say which day it is"

    _, step = _run_step(root, tmp_path, monday, calendar)
    assert step.ok is True, (
        "MEASURED: an unreadable manifest on the prior trading day's own recording does not "
        "block -- because nothing can prove it IS the prior trading day's"
    )
    assert str(recording.root) in step.detail, "it is still named, and still queued"
    assert step.figures["not_judged"], "and reachable as data, not only as a sentence"


def test_B420_a_recording_with_NO_manifest_at_all_is_invisible_to_the_queue(
    tmp_path: Path
) -> None:
    """The other edge of the same rule, recorded for the same reason.

    ``unverified_recordings`` skips a directory with no ``manifest.json`` -- not into the
    unreadable list, but silently. Its own docstring says a recording absent from this list reads
    as one that passed (M15's shape). Pre-existing (the chunk-13 code had the same filter) and
    narrow: without a manifest there is no ``mode``, no ``trade_date`` and no ``master_file``, so
    there is nothing to verify it under. Recorded, not failed.
    """
    root = tmp_path / "live"
    orphan = root / "2026-08-14-live"
    (orphan / "candles").mkdir(parents=True)
    (orphan / "candles" / "HDFCBANK.jsonl").write_text("", encoding="utf-8")

    pending, unreadable = refresh.unverified_recordings(root, before=date(2026, 8, 17))
    assert pending == () and unreadable == (), "MEASURED: silently invisible, in both lists"


def test_B420_TODAYs_own_and_a_FUTURE_recording_are_never_judged(tmp_path: Path) -> None:
    """``before=today`` is a strict inequality, and it has to be: today's recording is being
    written as this runs and today has no oracle until the evening."""
    root = tmp_path / "live"
    today = date(2026, 8, 17)
    _plant(root, today, "live")
    _plant(root, today + timedelta(days=1), "live")
    _plant(root, today - timedelta(days=1), "replay", mode="replay")
    _plant(root, today - timedelta(days=2), "live", verified=True)

    pending, unreadable = refresh.unverified_recordings(root, before=today)
    assert pending == (), "today's own, tomorrow's, a replay and a judged day are all excluded"
    assert unreadable == ()


# --- the readiness gate: the credential hunt, and the no-write claim -----------------------------


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """The operator's real ``.env`` must never decide a probe's answer, in either direction."""
    monkeypatch.setattr("acumen.config.load_env", lambda *args, **kwargs: None)
    for name in (tg.ENV_BOT_TOKEN, tg.ENV_CHAT_ID):
        monkeypatch.delenv(name, raising=False)


PLANTED_TOKEN: str = "8123456789:AAF_reviewer_planted_token_do_not_print_me_0123"
PLANTED_CHAT: str = "-1002233445566"


def _gate_world(root: Path) -> Path:
    from acumen import calendar as cal

    # The build's own register writer, imported rather than re-implemented: a probe that builds
    # its own idea of the ledger measures its own idea of the ledger.
    from test_dry_run_readiness import _register, _write_register

    data, cache = root / "data", root / "cache"
    _write_register(data, _register(gate.SETTLED_UNIVERSE_SIZE))

    master = cache / "instrument_master" / ls.day_master_filename(DAY)
    master.parent.mkdir(parents=True, exist_ok=True)
    master.write_text("[]", encoding="utf-8")
    payload = json.loads(
        (REPO / "tests" / "fixtures" / "holidays_2026.json").read_text(encoding="utf-8")
    )
    cal.nse_http.write_cache(
        cal.cache_path(cache), payload, url=cal.HOLIDAY_MASTER_URL, fetched_on=DAY
    )
    text = (REPO / "config.yaml").read_text(encoding="utf-8")
    for key, value in (("data_root", data), ("cache_root", cache)):
        text = "\n".join(
            f"  {key}: {value.as_posix()}" if line.strip().startswith(f"{key}:") else line
            for line in text.splitlines()
        )
    config_path = root / "config.yaml"
    config_path.write_text(text + "\n", encoding="utf-8")
    return config_path


def _every_byte(report) -> str:
    """Every string this report can put in front of a human OR keep as data."""
    return "\n".join((
        report.render(),
        json.dumps([check.figures for check in report.checks], default=str),
        json.dumps([check.detail for check in report.checks], default=str),
        repr(report),
        "\n".join(report.refusals),
    ))


def test_the_GATE_leaks_no_credential_even_when_the_REAL_SEND_PATH_raises_carrying_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hunt the build's own probe does not run: through the REAL ``post_message``.

    ``requests`` is made to raise an exception whose text carries the whole request URL, token and
    all -- which is exactly the shape a real transport failure has. ``post_message`` drops the
    cause and reports only the exception TYPE, so the gate's refusal names a class and not a
    secret. Every byte of every outcome is searched, not just the rendered page.
    """
    monkeypatch.setenv(tg.ENV_BOT_TOKEN, PLANTED_TOKEN)
    monkeypatch.setenv(tg.ENV_CHAT_ID, PLANTED_CHAT)
    monkeypatch.setattr("acumen.config.load_env", lambda *args, **kwargs: None)
    config_path = _gate_world(tmp_path)

    class Boom(Exception):
        pass

    class FakeRequests:
        @staticmethod
        def post(url, **kwargs):
            raise Boom(
                f"HTTPSConnectionPool: Max retries exceeded with url: {url} "
                f"(payload chat_id={kwargs.get('data', {}).get('chat_id')})"
            )

    monkeypatch.setitem(__import__("sys").modules, "requests", FakeRequests)

    report = gate.assess(
        day=DAY, config=load_config(config_path, include_env=False),
        tripwire_runner=lambda argv, cwd: (0, "14 passed in 19.14s\n"),
        send_test_message=True,          # the real tg.post_message, deliberately not stubbed
    )
    everything = _every_byte(report)
    assert not report.ready, "the send failed, so the gate must refuse"
    for secret in (
        PLANTED_TOKEN, PLANTED_CHAT, PLANTED_TOKEN.split(":")[1], PLANTED_CHAT.lstrip("-"),
        "api.telegram.org",
    ):
        assert secret not in everything, f"{secret[:12]}... reached the readiness report"
    assert "Boom" in everything, "the failure is still named -- by TYPE, which is the safe half"


def test_the_GATE_writes_NOTHING_under_either_root_fingerprinted_not_asserted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLAUDE.md's rule about tests that certify a no-write property: drive the ACTUAL path and
    fingerprint EVERY affected root (REVIEW_14 Q3, the M1/M6 pattern).

    So this runs the whole gate -- including a REAL pytest subprocess over the real tripwire
    suite -- and fingerprints both roots byte by byte on either side of it.
    """
    monkeypatch.setenv(tg.ENV_BOT_TOKEN, PLANTED_TOKEN)
    monkeypatch.setenv(tg.ENV_CHAT_ID, PLANTED_CHAT)
    monkeypatch.setattr("acumen.config.load_env", lambda *args, **kwargs: None)
    config_path = _gate_world(tmp_path)
    settings = load_config(config_path, include_env=False)
    roots = (settings.path("data_root"), settings.path("cache_root"))

    def fingerprint() -> dict[str, str]:
        marks = {}
        for root in roots:
            digest = hashlib.sha256()
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                stat = path.stat()
                digest.update(
                    f"{path.relative_to(root).as_posix()}|{stat.st_size}|"
                    f"{stat.st_mtime_ns}|".encode("utf-8")
                )
                digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("utf-8"))
            marks[str(root)] = digest.hexdigest()
        return marks

    before = fingerprint()
    report = gate.assess(
        day=DAY, config=settings, send_test_message=True, transport=lambda text: None,
    )
    after = fingerprint()

    assert before == after, "the readiness gate moved a byte inside a store root"
    assert [check.name for check in report.checks] == list(gate.CHECKS)
    tripwires = next(c for c in report.checks if c.name == gate.CHECK_TRIPWIRES)
    assert tripwires.figures.get("ran") is True and tripwires.ok, (
        f"the real tripwire suite must have RUN and passed: {tripwires.detail}"
    )


def test_the_GATE_refuses_a_tripwire_suite_it_could_not_RUN_and_one_that_TIMED_OUT(
    tmp_path: Path
) -> None:
    """An exit code that never happened certifies nothing. Both non-answers are refusals."""
    def exploding(argv, cwd):
        raise ReviewerDiskFull("pytest could not be started on this machine")

    could_not_run = gate.check_tripwires(runner=exploding)
    assert not could_not_run.ok and could_not_run.figures["ran"] is False
    assert "could not be RUN" in could_not_run.detail

    absent = gate.check_tripwires(repo_root=tmp_path)
    assert not absent.ok and "is not at" in absent.detail

    red = gate.check_tripwires(runner=lambda argv, cwd: (1, "1 failed, 13 passed"))
    assert not red.ok and "FAILED (exit 1)" in red.detail

    green = gate.check_tripwires(runner=lambda argv, cwd: (0, "14 passed in 1.00s"))
    assert green.ok and "GREEN" in green.detail


def test_the_GATE_report_is_NOT_READY_when_a_check_is_simply_ABSENT(tmp_path: Path) -> None:
    """The property that matters more than any single check. A report carrying six of seven must
    never read READY, and the missing one must be named."""
    passing = tuple(
        gate.ReadinessCheck(name=name, ok=True, detail="stubbed")
        for name in gate.CHECKS
    )
    assert gate.ReadinessReport(day=DAY, checks=passing).ready

    for dropped in gate.CHECKS:
        short = gate.ReadinessReport(
            day=DAY, checks=tuple(c for c in passing if c.name != dropped)
        )
        assert not short.ready, f"a report without {dropped!r} claimed READY"
        assert any("NOT CHECKED" in refusal and dropped in refusal
                   for refusal in short.refusals), dropped
        assert gate.NOT_READY_LINE in short.render()

    scrambled = gate.ReadinessReport(day=DAY, checks=tuple(reversed(passing)))
    assert not scrambled.ready, "and a report that reorders them is not the certified seven"


# --- the runbook, read as the operator ----------------------------------------------------------


def test_the_RUNBOOK_names_exactly_ONE_command_that_can_ring_the_phone_with_an_ALERT(
) -> None:
    """Directed check: one command, and only one, rings the phone -- and it is labelled.

    Two commands in the runbook cause a message to leave the machine, and they are different
    things: ``--send-test-message`` sends ONE labelled test message from the readiness gate, and
    ``--live-alerts`` is the only one that can put a SIGNAL on the trader's phone. Both are
    labelled as what they are, and no other command in the document can send anything.
    """
    text = (REPO / "docs" / "morning_runbook.md").read_text(encoding="utf-8")
    commands = [
        line.strip() for line in text.splitlines()
        if line.strip().startswith("python ")
    ]
    assert commands, "the runbook must actually print commands"
    alerting = [line for line in commands if "--live-alerts" in line]
    messaging = [line for line in commands if "--send-test-message" in line]
    assert len(alerting) == 1, f"more than one command can ring the phone: {alerting}"
    assert len(messaging) == 1, f"more than one command sends a test message: {messaging}"
    assert not (set(alerting) & set(messaging)), "and they are not the same command"

    index = text.index(alerting[0])
    preamble = text[max(0, index - 400):index]
    assert "--live-alerts" in preamble and (
        "separate, deliberate act" in preamble or "ONLY when the trader wants" in preamble
    ), "the alerting command is not labelled as the deliberate act it is"
    assert "opt-in" in text[:text.index(messaging[0])], "the test message is not labelled opt-in"


def test_the_RUNBOOK_and_the_GATE_agree_on_the_SEVEN_CHECK_NAMES_verbatim() -> None:
    """A runbook that paraphrases a constant is a runbook that goes stale silently."""
    text = (REPO / "docs" / "morning_runbook.md").read_text(encoding="utf-8")
    for name in gate.CHECKS:
        assert f"`{name}`" in text, f"the runbook does not quote the check {name!r} verbatim"
    assert gate.READY_LINE in text

    # REVIEW_15 finding, PINNED as measured rather than asserted away: the gate's own refusal
    # line is the one sentence of it the runbook paraphrases ("it REFUSES and names what is
    # missing") instead of quoting. The similar-looking line the document DOES quote --
    # "NOT READY -- the screener must not start" -- belongs to the morning REFRESH, not to the
    # gate, and section 11 tabulates it as such. Nothing is wrong on the page; one string simply
    # is not pinned to its constant, which is how a paraphrase later drifts. Flip this when the
    # runbook quotes it.
    assert gate.NOT_READY_LINE not in text, (
        "the runbook now quotes the gate's refusal line verbatim -- flip this pin: "
        "change `not in` to `in` and delete this comment"
    )
    assert "NOT READY -- the screener must not start" in text, (
        "the REFRESH's refusal, which the runbook does quote, is still quoted"
    )
    assert gate.TEST_MESSAGE_HEADING in text
    assert refresh.VERIFY_STEP in text
    assert ls.EVENT_POST_SESSION_ALERT in text
    # Compared with whitespace normalised: the runbook wraps its prose, and a line break is not
    # a paraphrase. Every other character must be the constant's own.
    flat = " ".join(text.split())
    assert " ".join(tg.SUMMARY_SUBJECTS.split()).strip("()") in flat, (
        "the runbook paraphrases L1's summary-subjects line instead of quoting it"
    )
    # The marker is quoted by its OPENING, elided with "..." in the markers table -- which is the
    # honest way to tabulate a two-line sentence. The opening is the part a phone shows first.
    assert tg.UNSTAMPED_MARKER.split(" -- ")[0] in flat
    assert tg.DRY_RUN_MARKER in text and tg.REPLAY_MARKER in text, (
        "the two markers that fit on one line ARE quoted whole"
    )
    for quarantined in gate.QUARANTINED:
        assert quarantined in text


def test_the_SEVEN_CHECKS_each_driven_to_BOTH_a_pass_and_a_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole gate, both ways, in one matrix -- the review's own directed check.

    A gate is worth exactly the refusals it makes, so each of the seven is shown answering yes on
    a world where it should and no on a world where it should not, and the refusal is checked to
    NAME its own check. Driven through ``assess`` -- the function the CLI calls -- rather than
    through the seven functions one at a time, so the wiring is measured too.
    """
    monkeypatch.setenv(tg.ENV_BOT_TOKEN, PLANTED_TOKEN)
    monkeypatch.setenv(tg.ENV_CHAT_ID, PLANTED_CHAT)
    monkeypatch.setattr("acumen.config.load_env", lambda *args, **kwargs: None)
    config_path = _gate_world(tmp_path)
    settings = load_config(config_path, include_env=False)
    green = dict(
        day=DAY, config=settings, send_test_message=True, transport=lambda text: None,
        tripwire_runner=lambda argv, cwd: (0, "14 passed in 19.14s\n"),
    )

    passing = gate.assess(**green)
    assert passing.ready, f"the all-green world must certify: {passing.refusals}"
    assert gate.READY_LINE in passing.render() and not passing.refusals

    def refuse(name: str, **broken) -> None:
        report = gate.assess(**{**green, **broken})
        assert not report.ready, f"{name} was broken and the gate still said READY"
        assert [c.name for c in report.checks] == list(gate.CHECKS), (
            f"{name}'s failure hid another check"
        )
        bad = [c for c in report.checks if not c.ok]
        assert [c.name for c in bad] == [name], (
            f"{name} should be the only refusal; got {[c.name for c in bad]}"
        )
        assert any(refusal.startswith(name) for refusal in report.refusals)
        assert gate.NOT_READY_LINE in report.render()

    monkeypatch.delenv(tg.ENV_BOT_TOKEN, raising=False)
    refuse(gate.CHECK_CREDENTIALS)
    monkeypatch.setenv(tg.ENV_BOT_TOKEN, PLANTED_TOKEN)

    master = settings.path("cache_root") / "instrument_master" / ls.day_master_filename(DAY)
    master.rename(master.with_suffix(".hidden"))
    refuse(gate.CHECK_MASTER)
    master.with_suffix(".hidden").rename(master)

    from acumen import calendar as cal

    holiday_cache = cal.cache_path(settings.path("cache_root"))
    kept = holiday_cache.read_bytes()
    holiday_cache.unlink()
    refuse(gate.CHECK_CALENDAR)
    holiday_cache.write_bytes(kept)

    from acumen import backtest as bt
    from test_dry_run_readiness import _register, _write_register

    register = settings.path("data_root") / bt.RESIDUAL_LEDGER_RELPATH
    saved = register.read_text(encoding="utf-8")
    _write_register(settings.path("data_root"), _register(gate.SETTLED_UNIVERSE_SIZE + 1))
    refuse(gate.CHECK_UNIVERSE)   # a universe that quietly grew back is the M2 shape
    register.write_text(saved, encoding="utf-8")

    # The fence answers about the roots the JOB runs under (B406), so it PASSES here: this
    # world's ca cache sits under this world's data_root. Its refusal is driven through the
    # gate's own aggregation, restored by hand rather than by undo() -- undo() would also
    # unwind the autouse .env neutraliser and the planted keys.
    original_fence = gate.check_fence
    assert original_fence(
        data_root=settings.path("data_root"), cache_root=settings.path("cache_root")
    ).ok, "a cache under the job's own roots is fenced -- that is the pass"
    monkeypatch.setattr(
        gate, "check_fence",
        lambda **kw: gate.ReadinessCheck(
            name=gate.CHECK_FENCE, ok=False,
            detail="NOT fenced for data_root: a --refresh --allow-network morning would WRITE",
        ),
    )
    refuse(gate.CHECK_FENCE)
    monkeypatch.setattr(gate, "check_fence", original_fence)

    refuse(gate.CHECK_TRIPWIRES, tripwire_runner=lambda argv, cwd: (1, "1 failed"))
    refuse(gate.CHECK_TEST_MESSAGE, send_test_message=False)

    def explodes(text: str) -> None:
        raise ReviewerDiskFull("the chat could not be reached")

    refuse(gate.CHECK_TEST_MESSAGE, transport=explodes)


# --- the handover, read as the trader ------------------------------------------------------------


def test_the_HANDOVERS_THREE_PATHS_are_NOT_the_PACKS_three_as_it_claims() -> None:
    """REVIEW_15 finding, PINNED as measured. The attribution is wrong; one path is invented.

    ``docs/handover.md`` section 4 opens *"The validation pack (chunk 12) put three paths in
    front of you"* and lists **Stop here / The complete tool, used as a screener / Automation**.
    The pack's own section is headed **"Three ways forward"** and its three are **Retire it /
    Change it / Take it live knowing the arithmetic**.

    * *Take it live* -> *the complete tool used as a screener* -- the CHOSEN one, correctly named
      and correctly described. Nothing about the delivered path is wrong.
    * *Retire it* -> *Stop here* -- the same option in the trader's own terms.
    * **``Change it`` is DROPPED**, and **``Automation`` is put in its place** -- and automation
      was never a pack option. It is plan.md section 8's v2 backlog item, which the handover's
      own paragraph goes on to say ("listed in the plan's own backlog beside slippage modelling
      and a point-in-time universe"), so the document contradicts its own sentence one line
      later.

    The build's ``tests/test_handover.py`` names this property
    (``test_the_THREE_PATHS_are_the_packs_own_three...``) and checks the HANDOVER's own three
    headings without ever opening the pack -- a test that asserts its own document, which is the
    REVIEW_14 B2 shape. This probe opens the pack.
    """
    handover = (REPO / "docs" / "handover.md").read_text(encoding="utf-8")
    pack = (REPO / "docs" / "validation" / "trader_pack.md").read_text(encoding="utf-8")

    assert "### Three ways forward" in pack, "the pack's own section, by its own heading"
    forward = pack.split("### Three ways forward", 1)[1].split("\n## ", 1)[0]
    for offered in ("**Retire it.**", "**Change it.**", "**Take it live knowing the arithmetic.**"):
        assert offered in forward, f"the pack offers {offered}"

    assert "The validation pack (chunk 12) put three paths in front of you" in handover

    # The one that IS right, and it is the one that matters most: the delivered path.
    assert "2. **The complete tool, used as a screener.**" in handover
    assert "This is the path being delivered." in handover
    assert "the screener that watches the market and alerts you when a signal fires" in forward

    # ...and the two that are not.
    assert "Change it" not in handover, (
        "the handover now carries the pack's second option -- flip this pin: the finding is fixed"
    )
    assert "3. **Automation.**" in handover
    assert "Automation" not in forward, (
        "automation is not one of the pack's three; it is plan.md section 8's v2 backlog item"
    )
    plan = (REPO / "plan.md").read_text(encoding="utf-8")
    assert "auto-execution discussion" in plan, "which is where it really comes from"

    # The half of the paragraph that is CORRECT and load-bearing must not be lost in a fix.
    flat = " ".join(handover.split())
    assert "explicitly *not* built" in flat and "v2 conversation" in flat


def test_the_HANDOVER_holds_its_TRADER_FACING_discipline() -> None:
    """The rest of the directed read, which the document passes cleanly.

    No-order sentence in the first third; the honest bracket, not its flattering end; success
    defined as alerts-match rather than PnL; and not one command, flag or module path anywhere in
    a document written for somebody who will never open a terminal.
    """
    text = (REPO / "docs" / "handover.md").read_text(encoding="utf-8")
    lines = text.splitlines()

    no_order = next(
        index for index, line in enumerate(lines)
        if "It has never placed an order and it cannot place one" in line
    )
    assert no_order < len(lines) // 3, (
        f"the no-order sentence is at line {no_order} of {len(lines)} -- not in the first third"
    )

    assert "between 0.52% and 2.68%" in text
    assert "That is the honest range, not the flattering end of it." in text
    assert "**Success is not a profit number.**" in text
    assert "you accept it." in text

    import re

    for pattern in (r"--[a-z][a-z-]+", r"python ", r"acumen\.[a-z_]+", r"\bsrc/", r"\.py\b"):
        found = re.findall(pattern, text)
        assert not found, f"a terminal-shaped string reached the trader's document: {found[:3]}"
