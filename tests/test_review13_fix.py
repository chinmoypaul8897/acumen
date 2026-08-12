"""THE CHUNK-13 FIX-2 SESSION'S OWN TESTS -- one per BLOCKING finding of REVIEW_13.

The review's kept probes (``tests/test_review13_probes.py``) pin the findings at the place they
live and five of them have been FLIPPED. This file is the other half: the behaviour the fixes
ADD, tested where an operator would meet it -- through ``run_screener.main``, which is the entry
point the review found reached none of the class it drives.

**The first test here is the one that matters most**, because its absence is what let a green
suite of 2,392 tests pass over a live half that could not start:

    "no test, evidence document or artefact anywhere in the repo ever successfully constructs
     build_live_screener(mode='live'). The two places that call it both assert a refusal, and
     every live-posture test builds LiveScreener directly or mutates a replay screener's
     fields." -- REVIEW_13, VERDICT

``test_THE_LIVE_PATH_RUNS_END_TO_END_through_the_shipped_CLI`` builds the shipped live path over
a real symbol-day and runs the whole morning through ``main()``.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from acumen import backtest as bt
from acumen import calendar as cal
from acumen import live_dashboard as dash
from acumen import live_refresh as lr
from acumen import live_screener as ls
from acumen import run_screener
from acumen import signal_engine as se
from acumen import signals as sig
from acumen.config import load_config
from acumen.live_recording import LiveRecording
from acumen.live_source import StoredDayBarSource, duplicate_stamps, merge_bars
from acumen.minute_store import MinuteStore, StoredBar

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"

#: A real symbol-day from the lake. HDFCBANK is SETTLED (chunk-5B register), which is what a
#: live morning may screen at all under CONTEXT 4.7 / Q-30.
LIVE_SYMBOL = "HDFCBANK"
LIVE_DAY = date(2026, 6, 10)


def _stores_or_skip() -> Path:
    config = load_config(include_env=False)
    data_root = config.path("data_root")
    for relpath in ("daily_store", "minute_store"):
        if not (data_root / relpath).is_dir():
            pytest.skip(f"local {relpath} is absent (the stores are gitignored)")
    return data_root


def _scratch_world(tmp_path: Path, day: date) -> Path:
    """A scratch ``cache_root`` and config for a LIVE morning, leaving the real cache untouched.

    Two things a live morning needs that a past day's cache does not have: **THE DAY'S OWN
    instrument master** (CONTEXT 4.7 / Q-29) and the **published holiday master** the live
    calendar comes from (REVIEW_13 B6). Both are placed in a scratch cache here -- a COPY, never
    a link, which CLAUDE.md's data-store safety rules require -- so that this test exercises the
    REAL resolution of both rather than a monkeypatched stand-in, and writes not one byte into
    ``cache_root``. The pinned master is copied under the day's own name; its CONTENT is
    irrelevant to what is being proved (the ticks are the pin's, which is what the replay
    invariant already covers) and its PRESENCE under that name is exactly the prerequisite Q-29
    makes structural.

    Returns the path of the scratch ``config.yaml``.
    """
    config = load_config(include_env=False)
    cache = tmp_path / "cache"
    (cache / "instrument_master").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        config.path("cache_root") / "instrument_master" / config.instrument_master,
        cache / "instrument_master" / ls.day_master_filename(day),
    )
    # The published NSE holiday master, as the day-cache envelope fetch_calendar reads. The
    # payload is the committed 2026 snapshot fixture -- a real NSE reply, not an invented one.
    payload = json.loads((FIXTURES / "holidays_2026.json").read_text(encoding="utf-8"))
    cal.nse_http.write_cache(
        cal.cache_path(cache), payload, url=cal.HOLIDAY_MASTER_URL, fetched_on=day
    )

    raw = yaml.safe_load((REPO / "config.yaml").read_text(encoding="utf-8"))
    raw["paths"]["cache_root"] = str(cache)
    raw["paths"]["logs_dir"] = str(tmp_path / "logs")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return path


# --- THE COVERAGE GAP: the live path, built and run --------------------------------------------


def test_THE_LIVE_PATH_RUNS_END_TO_END_through_the_shipped_CLI(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """``run_screener.main --mode live``, a whole morning, on a REPLAYED TODAY.

    This is the test REVIEW_13's verdict says did not exist, and its absence is why 2,392 green
    tests said nothing about the half of the chunk that had never run. Everything on the live
    path is real here: ``build_live_screener(mode="live")`` assembles, the day's own instrument
    master is resolved by name from a cache, the calendar comes from the published holiday
    master, the settled-universe filter reads the chunk-5B register, the ORACLE-FREE battery
    runs per sweep, ``run_day()`` drives seventeen boundaries and then ``close_day()``, and the
    recording, the dashboards and the alerts are written.

    **Two things are replaced, and both are named rather than hidden.** The BAR SOURCE is the
    minute lake instead of the broker, because a test may not open a broker session (and because
    ``getCandleData`` is already the one call the whole live path makes -- ``live_source`` is
    unchanged and its tripwire is untouched). And the CLOCK is virtual, because "today" here is
    a day whose candles exist: a wall clock on 2026-08-12 driving a 2026-06-10 session would sit
    past every sweep's hard deadline by two months. That is what "a replayed today" means and it
    is the only honest way to run a live morning inside a test suite.
    """
    data_root = _stores_or_skip()
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(LIVE_SYMBOL, LIVE_DAY):
        pytest.skip(f"{LIVE_SYMBOL} {LIVE_DAY} is not in the local lake")
    config_path = _scratch_world(tmp_path, LIVE_DAY)

    monkeypatch.setattr(
        run_screener, "_bar_source",
        lambda live, config, data_root, *, allow_network: StoredDayBarSource(store),
    )
    monkeypatch.setattr(
        ls, "SystemClock",
        lambda: ls.VirtualClock(stamp=datetime.combine(LIVE_DAY, sig.SESSION_OPEN)),
    )

    code = run_screener.main([
        "--mode", "live",
        "--day", LIVE_DAY.isoformat(),
        "--symbols", f"{LIVE_SYMBOL},NTPC",   # NTPC is QUARANTINED and must be excluded by name
        "--config", str(config_path),
        "--recording-root", str(tmp_path / "rec"),
    ])
    printed = capsys.readouterr().out
    assert code == 0, printed[-3000:]

    # 1. CONTEXT 4.7's posture, before anything ran.
    assert "CONTEXT 4.7 -- LIVE MODE" in printed
    assert ls.LIVE_DISCLOSURE in printed
    assert "0.5229%-2.6808%" in printed, "M1: the operator reads B341's BRACKET, not its end"

    # 2. CONTEXT 4.7 / Q-30: the quarantined symbol is NOT screened, and is named (M2).
    assert "EXCLUDED" in printed and "NTPC" in printed
    assert "quarantined" in printed

    recording = LiveRecording.at(tmp_path / "rec" / f"{LIVE_DAY.isoformat()}-live")
    manifest = recording.read_manifest()
    assert manifest["mode"] == "live"
    assert manifest["symbols"] == [LIVE_SYMBOL], "the quarantined symbol never entered the sweep"
    assert [row["symbol"] for row in manifest["excluded_symbols"]] == ["NTPC"]
    assert manifest["master_file"] == ls.day_master_filename(LIVE_DAY), "Q-29's own dump"
    assert manifest["calendar"]["governing_source"] == "published-nse-holiday-master", (
        "M17: a LIVE morning IS governed by the published master, and the manifest says so "
        "because it is true rather than because it is the default"
    )
    assert manifest["seed_from"] == (
        LIVE_DAY - timedelta(days=ls.SEED_LOOKBACK_DAYS)
    ).isoformat(), "B1: the bias series has history to carry from"

    # 3. B4: run_day() ran, so close_day() ran, so the recording is a WHOLE session.
    bars = recording.bars(LIVE_SYMBOL, LIVE_DAY)
    assert bars, "the live path really fetched candles"
    assert max(bar.stamp for bar in bars).time() >= sig.bar_close_stamp(
        LIVE_DAY, sig.SQUARE_OFF_BAR
    ).time(), (
        "the recording reaches past 15:14 -- close_day()'s 15:30 poll is what makes gate 1's "
        "whole-day volume fold possible at all the next morning"
    )
    sweeps = [row for row in recording.events() if row["kind"] == "sweep-closed"]
    assert len(sweeps) == len(ls.boundary_stamps(LIVE_DAY)) + 1, (
        "seventeen boundaries AND the close-out poll -- the loop the CLI used to re-implement"
    )

    # 4. CONTEXT 3.3 / B3: the POC was pinned once, at the POC boundary, and never moved.
    pins = [row for row in recording.events() if row["kind"] == "poc-pinned"]
    assert len(pins) == 1 and pins[0]["symbol"] == LIVE_SYMBOL
    assert pins[0]["at"].endswith("11:15:00")

    # 5. Every alert carries CONTEXT 4.7's disclosed line, on the alert and not only on screen.
    alerts = recording.alerts()
    assert alerts, "a live morning that produced no alert would prove nothing about alerts"
    assert all(row["payload"]["disclosure"] == ls.LIVE_DISCLOSURE for row in alerts)
    assert all(row["payload"]["dry_run"] is True for row in alerts), "and it stayed a dry run"

    # 6. Both surfaces were written, and the trader's one is self-contained.
    page = (recording.root / "dashboard.html").read_text(encoding="utf-8")
    import html as _html

    assert "http" not in page.lower().split("<style>", 1)[0].replace("http-equiv", "")
    assert _html.escape(ls.LIVE_DISCLOSURE) in page
    assert "bars" in page and "last" in page, "B10: the freshness of every row is on the screen"


def test_a_RESTART_of_the_shipped_CLI_RESUMES_and_re_sends_NOTHING(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """REVIEW_13 **B8**: crash recovery is real, and reaches the operator.

    ``LiveScreener.restore()`` existed, worked, and round-tripped the dedup set and the bars --
    and had NO CALLER in ``src/``. ``run_screener.main`` built a screener and swept from 11:15
    with no ``restore()``, so after any death the dedup set started empty and every alert of the
    day went out a second time. Measured by the review end to end: the CLI was killed with a
    real ``terminate()`` and restarted, and **four alerts were re-sent, including a TRIGGER**.

    Here the whole morning is run, and then run AGAIN into the same recording -- which is what a
    restart is. Nothing may be delivered twice.
    """
    data_root = _stores_or_skip()
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(LIVE_SYMBOL, LIVE_DAY):
        pytest.skip(f"{LIVE_SYMBOL} {LIVE_DAY} is not in the local lake")

    argv = [
        "--mode", "replay", "--day", LIVE_DAY.isoformat(), "--symbols", LIVE_SYMBOL,
        "--recording-root", str(tmp_path / "rec"),
    ]
    assert run_screener.main(argv) == 0
    first = capsys.readouterr().out
    recording = LiveRecording.at(tmp_path / "rec" / f"{LIVE_DAY.isoformat()}-replay")
    delivered = [(row["kind"], row["at"]) for row in recording.alerts()]
    assert delivered, "the morning produced alerts to re-send"
    assert "RESUMED" not in first

    assert run_screener.main(argv) == 0
    second = capsys.readouterr().out
    assert "RESUMED from" in second, "the operator is told, in one line, what was already sent"
    assert [(row["kind"], row["at"]) for row in recording.alerts()] == delivered, (
        "a restart delivers NOTHING a second time -- not one alert, and not one alerts.jsonl row"
    )


# --- B2: the duplicate stamp reaches the gate ---------------------------------------------------


class _WithDuplicate:
    """A vendor reply that serves one stamp TWICE, the second copy corrupt. CONTEXT 4.5 gate 2."""

    def __init__(self, inner, *, at_minute: int = 30) -> None:
        self.inner, self.at_minute = inner, at_minute

    def fetch(self, symbol, day, upto):
        bars = list(self.inner.fetch(symbol, day, upto))
        if len(bars) > self.at_minute:
            original = bars[self.at_minute]
            twin = StoredBar(
                symbol=original.symbol, stamp=original.stamp,
                open_paise=original.open_paise + 400, high_paise=original.high_paise + 400,
                low_paise=original.low_paise + 400, close_paise=original.close_paise + 400,
                volume=original.volume,
            )
            bars.insert(self.at_minute + 1, twin)
        return tuple(bars)


def test_a_DUPLICATE_STAMP_is_refused_by_gate_2_instead_of_being_laundered_past_it(
    tmp_path: Path,
) -> None:
    """REVIEW_13 **B2**: the corrupt twin used to win, on a delivered TRIGGER.

    CONTEXT 4.5 gate 2's FIRST exclusion trigger is *"any duplicate stamp"*, and CONTEXT 4.7
    leaves gate 2 as the whole battery a live morning runs. ``LiveScreener._poll`` stored
    ``merge_bars(previous, fetched)``, which keys on the stamp and keeps the LAST copy, so
    ``gate2.duplicates`` was **structurally always 0 in live mode**: the settled battery refused
    the raw vendor reply while the live battery returned ``passed=True, duplicates=0`` and the
    surviving bar was the corrupt one. Demonstrated downstream by the review: entry 200100 ->
    200500, target 200700 -> 202300, qty 500 -> 166, on a DELIVERED trigger, on a day the
    settled battery refuses outright.
    """
    from test_backtest import SYMBOL  # noqa: E402 -- the suite's own synthetic world
    from test_live_screener import make_screener, run_to  # noqa: E402

    clean, clean_sink, _rec = make_screener(tmp_path / "clean", live=True)
    run_to(clean, "11:45")
    assert [a.kind for a in clean_sink.alerts].count(ls.ALERT_TRIGGER) == 1, (
        "the same day WITHOUT the duplicate delivers its trigger -- so the refusal below is "
        "the duplicate and not the fixture"
    )

    screener, sink, recording = make_screener(tmp_path / "dirty", live=True)
    screener.source = _WithDuplicate(screener.source)
    run_to(screener, "11:45")

    assert screener.duplicate_bars.get(SYMBOL), "the twin is CARRIED, not resolved away"
    gates = screener._battery(SYMBOL, screener.bars[SYMBOL])
    assert gates.gate2.duplicates >= 1, "and gate 2 can SEE it"
    assert not gates.usable and gates.refusal == se.NOT_EVALUATED_GATE2
    assert screener.states[SYMBOL].phase == ls.PHASE_REFUSED
    assert not [a for a in sink.alerts if a.kind == ls.ALERT_TRIGGER], (
        "no TRIGGER is delivered on a day CONTEXT 4.5 gate 2 refuses"
    )
    assert "duplicate-stamps" in {row["kind"] for row in recording.events()}

    # The engine still sees ONE bar per minute -- the merge is unchanged where it must be.
    merged = merge_bars(screener.bars[SYMBOL])
    assert len(merged) == len(screener.bars[SYMBOL])
    assert len(duplicate_stamps(screener.bars[SYMBOL])) == 0


def test_the_NEXT_MORNING_sees_the_duplicate_and_the_revisions_the_recording_holds(
    tmp_path: Path,
) -> None:
    """B2's other half, and B331's: ``revisions()`` has a caller in ``src/`` now.

    ``LiveRecording.bars`` de-duplicates exactly as ``merge_bars`` does, so the morning-after
    battery could not see the duplicate either -- the corrupt twin was laundered a second time,
    past the very verification CONTEXT 4.7 exists for. And ``revisions()`` -- B331's reporting
    half, the thing that makes append-only-plus-de-duplicate-on-read safe -- had **zero callers
    in src/**, so a vendor that revised a bar between polls was recorded and never reported.
    """
    from test_backtest import SYMBOL  # noqa: E402
    from test_live_screener import make_screener, run_to  # noqa: E402

    screener, _sink, recording = make_screener(tmp_path, live=True)
    screener.source = _WithDuplicate(screener.source)
    run_to(screener, "11:45")

    twins = recording.duplicate_bars(SYMBOL, screener.day)
    assert twins, "the append-only candle file still holds the twin the merge resolved away"

    verification = lr.verify_prior_recording(
        recording, screener.pipeline, day=screener.day
    )
    verdict = next(v for v in verification.verdicts if v.symbol == SYMBOL)
    assert verdict.duplicate_stamps == len(twins)
    assert not verdict.live_passed and not verdict.oracle_passed, (
        "BOTH batteries refuse the day now -- the morning after can no longer be fooled by the "
        "same de-duplication that fooled the morning"
    )
    assert "duplicate stamp" in verdict.oracle_reason
    assert "revisions" in verdict.as_dict() if hasattr(verdict, "as_dict") else True
    assert verification.as_dict()["verdicts"][0]["duplicate_stamps"] >= 1


# --- B7 / B9 / M3 / M6 / M11: alerts are state-derived and idempotent ---------------------------


class _DeadAtBoundary:
    """A feed that answers nothing at the named sweeps and heals afterwards (CONTEXT 4.4)."""

    def __init__(self, inner, dead: set[str]) -> None:
        self.inner, self.dead = inner, dead

    def fetch(self, symbol, day, upto):
        from acumen.live_source import BarSourceError

        if upto.strftime("%H:%M") in self.dead:
            raise BarSourceError(f"{symbol}: simulated outage at {upto:%H:%M}")
        return self.inner.fetch(symbol, day, upto)


def test_a_TRIGGER_that_missed_its_own_boundary_is_STILL_DELIVERED(tmp_path: Path) -> None:
    """REVIEW_13 **B7** and **M11**: the one alert the morning exists for now self-heals.

    ``PHASE_TRIGGERED`` was set only when ``entry.close_stamp == boundary``, and
    ``ALERT_TRIGGER`` fired only on ENTRY into that phase. ARMED and EXITED were state-derived
    and self-healed; TRIGGERED did not. So any of CONTEXT 4.4's own normal degradations at the
    trigger boundary -- a failed skip-and-repoll, the hard deadline, a late vendor candle --
    destroyed it permanently: the dashboard still showed the position, and the bell (and chunk
    14's Telegram) never fired.
    """
    from test_backtest import SYMBOL  # noqa: E402
    from test_live_screener import make_screener, run_to  # noqa: E402

    screener, sink, _rec = make_screener(tmp_path)
    screener.source = _DeadAtBoundary(screener.source, {"11:30"})
    run_to(screener, "11:45")

    kinds = [alert.kind for alert in sink.alerts]
    assert ls.ALERT_TRIGGER in kinds, (
        "the entry boundary was missed entirely and the TRIGGER still reached the trader"
    )
    trigger = next(a for a in sink.alerts if a.kind == ls.ALERT_TRIGGER)
    assert trigger.at.strftime("%H:%M") == "11:45", "delivered late, which is not the same as lost"
    assert trigger.payload["entry_paise"] and trigger.payload["qty"], "with all four numbers"
    assert screener.states[SYMBOL].phase == ls.PHASE_EXITED


def test_a_SUPERSEDED_trigger_is_delivered_AND_recorded_as_a_correction(
    tmp_path: Path,
) -> None:
    """REVIEW_13 **B9**: the bar most likely to be missing is the one that sets the entry price.

    ``_clamp`` asks for stamps up to HH:MM-1 and CONTEXT 4.4 measures the just-closed candle
    arriving ~0.2s after the boundary -- so the minute most likely to be absent at a boundary
    poll is the last minute of the candle that boundary is about to decide, and **that minute's
    close IS the entry price** (CONTEXT 3.4-2, R1-Q14). When it healed one sweep later the state
    moved from entry 2001.00 / TP 2007.00 / qty 500 to entry 2003.00 / TP 2015.00 / qty 250 --
    and ``_deliver`` returned False ABOVE ``record_alert``, so the trader kept the first alert
    and the recording kept no evidence that anything had changed.
    """
    from test_backtest import SYMBOL  # noqa: E402
    from test_live_screener import make_screener  # noqa: E402

    screener, sink, recording = make_screener(tmp_path)
    stamp = datetime(2026, 7, 17, 11, 30)
    first = screener._alert(ls.ALERT_TRIGGER, SYMBOL, stamp, {
        "entry_stamp": stamp.isoformat(), "entry_paise": 200_100, "stop_paise": 199_900,
        "target_paise": 200_700, "qty": 500,
    })
    assert screener._deliver(first) is True
    healed = screener._alert(ls.ALERT_TRIGGER, SYMBOL, datetime(2026, 7, 17, 11, 45), {
        "entry_stamp": stamp.isoformat(), "entry_paise": 200_300, "stop_paise": 199_900,
        "target_paise": 201_500, "qty": 250,
    })
    assert screener._deliver(healed) is True, (
        "the same entry CANDLE with different numbers is a correction, not a duplicate"
    )
    assert [a.payload["entry_paise"] for a in sink.alerts] == [200_100, 200_300]
    assert sink.alerts[-1].payload["correction"] is True
    recorded = [row for row in recording.alerts() if row["kind"] == ls.ALERT_TRIGGER]
    assert len(recorded) == 2, "and the recording carries the evidence that something changed"
    assert recorded[-1]["payload"]["supersedes"]


def test_the_PHASE_MACHINE_is_monotonic_so_an_exit_cannot_be_walked_back(
    tmp_path: Path,
) -> None:
    """REVIEW_13 **M3**: a vendor revision walked EXITED back to IN-TRADE, silently.

    ...after which the real exit was deleted by the ``(symbol, kind)`` dedup. Demonstrated by the
    review: the only exit the trader received said stop-loss 199900 while the screener's own
    final state said target 200700 -- a 4,000-rupee swing at qty 500. CONTEXT 3.4-2 consumes the
    stock-day at the first cross and allows no re-entry after any exit, so a state that walks
    backwards is not a correction; it is a state the strategy does not have.
    """
    from test_backtest import SYMBOL  # noqa: E402
    from test_live_screener import make_screener, run_to  # noqa: E402

    screener, _sink, recording = make_screener(tmp_path)
    run_to(screener, "11:45")
    exited = screener.states[SYMBOL]
    assert exited.phase == ls.PHASE_EXITED and exited.exit_kind

    # The feed "revises" the day back to before the exit -- the shape M3 demonstrated. The entry
    # candle (stamps 11:15..11:29) survives; every minute that could carry the exit is gone.
    screener.bars[SYMBOL] = tuple(
        bar for bar in screener.bars[SYMBOL] if bar.stamp < datetime(2026, 7, 17, 11, 30)
    )
    screener._evaluate(SYMBOL, datetime(2026, 7, 17, 12, 0))

    assert screener.states[SYMBOL] == exited, "the earlier, further-along state STANDS"
    assert "phase-regression-refused" in {row["kind"] for row in recording.events()}, (
        "and the feed's disagreement is recorded rather than acted on"
    )


def test_a_SECOND_outage_raises_a_second_failure_alert(tmp_path: Path) -> None:
    """REVIEW_13 **M6**: only ONE failure banner could ever be alerted per session.

    ``ALERT_FAILURE`` is delivered with symbol ``"-"``, so ``("-", "failure")`` was spent by the
    first outage of the day. A later outage updated the banner and wrote an event but delivered
    no alert, no ``alerts.jsonl`` row and no bell -- and ``SoundAlertSink`` deliberately includes
    failures in ``loud_kinds``, so the one thing that must never go quiet did.
    """
    from test_live_screener import make_screener  # noqa: E402

    screener, sink, _rec = make_screener(tmp_path)
    screener.source = _DeadAtBoundary(screener.source, {"11:15", "11:45"})
    for boundary in ls.boundary_stamps(screener.day)[:3]:
        screener.clock.set(boundary)
        screener.sweep(boundary)

    failures = [alert for alert in sink.alerts if alert.kind == ls.ALERT_FAILURE]
    assert len(failures) == 2, "each outage is its own alert, keyed on its own sweep"
    assert failures[0].payload["sweep"] != failures[1].payload["sweep"]


# --- B10 / M20: a stale row is not a fresh row --------------------------------------------------


def test_a_STALE_row_is_VISIBLY_different_from_a_fresh_one() -> None:
    """REVIEW_13 **B10** and DESIGN.md PART II's third acceptance question.

    A feed answering 200 with an empty candle array counted as a successful fetch, so
    ``SweepReport.complete`` stayed True, no banner rose, and every ``SymbolState`` froze on its
    last good prefix. ``SymbolState`` has carried ``last_stamp`` and ``minute_count`` all along
    and the dashboard rendered NEITHER, so a row an hour stale was **byte-identical** to a fresh
    one while the header clock asserted the current boundary. The rendered artifact read
    *"IN TRADE (1) -- position open, being watched"* off bars that had stopped at 11:29.
    """
    now = datetime(2026, 7, 17, 12, 30)
    common = dict(
        symbol="SYNTH", phase=ls.PHASE_IN_TRADE, side="long", entry_paise=200_100,
        stop_paise=199_900, target_paise=200_700, qty=500, detail="in trade",
    )
    fresh = ls.SymbolState(minute_count=195, last_stamp=now - timedelta(minutes=1), **common)
    stale = ls.SymbolState(minute_count=134, last_stamp=datetime(2026, 7, 17, 11, 29), **common)

    grouped_fresh = {ls.PHASE_IN_TRADE: (fresh,)}
    grouped_stale = {ls.PHASE_IN_TRADE: (stale,)}
    page_fresh = dash.render_html(day=now.date(), now=now, grouped=grouped_fresh, alerts=())
    page_stale = dash.render_html(day=now.date(), now=now, grouped=grouped_stale, alerts=())
    assert page_fresh != page_stale, "the two rows are not the same pixels"
    assert "STALE" in page_stale and "STALE" not in page_fresh
    assert 'class="row stale"' in page_stale
    assert "11:29" in page_stale and "12:29" in page_fresh

    text_fresh = dash.render_text(day=now.date(), now=now, grouped=grouped_fresh, alerts=())
    text_stale = dash.render_text(day=now.date(), now=now, grouped=grouped_stale, alerts=())
    assert "STALE 61m BEHIND" in text_stale and "STALE" not in text_fresh
    assert "bars 134" in text_stale and "bars 195" in text_fresh
    assert dash.data_age(stale, now) == (True, 61)
    assert dash.data_age(fresh, now) == (False, 1)


def test_an_EMPTY_answer_is_a_NOT_answer_and_raises_the_banner(tmp_path: Path) -> None:
    """B10's other end: 200-with-no-candles is not a successful fetch.

    It used to be one, which is what made a blind screener render as a calm market: the sweep
    reported complete, the banner stayed empty, and every row froze silently.
    """
    from test_live_screener import make_screener  # noqa: E402

    class _Empty:
        def fetch(self, symbol, day, upto):
            return ()

    screener, sink, _rec = make_screener(tmp_path)
    screener.source = _Empty()
    screener.clock.set(ls.boundary_stamps(screener.day)[0])
    report = screener.sweep(ls.boundary_stamps(screener.day)[0])

    assert not report.complete, "an empty answer leaves the sweep INCOMPLETE"
    assert screener.banner, "and the banner rises"
    assert [alert.kind for alert in sink.alerts] == [ls.ALERT_FAILURE]


# --- M8 / M9: the master cannot be pointed outside the cache ------------------------------------


@pytest.mark.parametrize("bad", [
    "../../elsewhere/planted.json",
    "..\\..\\elsewhere\\planted.json",
    "/etc/planted.json",
    "C:/planted.json",
    "sub/dir/master.json",
    "",
    "   ",
])
def test_named_master_REFUSES_a_filename_that_is_not_a_bare_filename(bad: str) -> None:
    """REVIEW_13 **M8**: ``named_master`` did not sanitise what ``config.py`` explicitly does.

    Verified by the review: ``../../elsewhere/planted.json`` and an absolute path both loaded a
    master from OUTSIDE the cache, and the manifest then recorded only the basename -- so the day
    stopped being replayable at all. The input is not a literal: ``_master_for`` and
    ``verify_yesterday`` feed a recording manifest's ``master_file`` straight in.
    """
    config = load_config(include_env=False)
    with pytest.raises(bt.BacktestError, match="bare FILENAME"):
        bt.named_master(config.path("cache_root"), bad)


def test_the_config_pin_validator_and_the_master_loader_now_refuse_the_SAME_shapes() -> None:
    """The two doors are held to one rule, which is what M8 found they were not."""
    from acumen import config as config_module

    for bad in ("../../elsewhere/planted.json", "/etc/planted.json", "sub/dir/master.json"):
        with pytest.raises(config_module.ConfigError, match="bare FILENAME"):
            config_module._validate_instrument_master(bad, Path("config.yaml"))
        with pytest.raises(bt.BacktestError, match="bare FILENAME"):
            bt.named_master(Path("."), bad)


# --- M1 / M2: what the operator is told before the morning starts -------------------------------


def test_the_startup_banner_carries_B341s_BRACKET_and_the_settled_universe_rule() -> None:
    """REVIEW_13 **M1** and **M2**, at the sentence the operator actually reads.

    M1: the banner priced the live/oracle divergence at 0.5229% when the same ledger measures
    the population a live morning is blind to at 2.5141% (ceiling 2.6808%) -- a 4.8x
    understatement, because gate 1P is inapplicable live too and its refusals are not in the
    narrow figure. The session's own evidence named 2.5141% correctly; the runtime string never
    printed it.

    M2: a live morning swept the raw F&O list, all six quarantined symbols included, and no live
    module read the settled register at all.
    """
    text = ls.LIVE_STARTUP_DISCLOSURE
    for figure in ("0.5229%", "2,187/418,275", "2.5141%", "10,516", "2.6808%",
                   "0.5229%-2.6808%"):
        assert figure in text, f"the operator banner is missing {figure}"
    assert "SETTLED UNIVERSE ONLY" in text and "Q-30" in text
    assert "Section 6 parity is judged on oracle-passing days" in text, (
        "CONTEXT v2.1's new clause reaches the operator too"
    )
    assert "THIS TOOL PLACES NO ORDERS." in text


def test_the_LIVE_universe_is_the_SETTLED_204_and_the_quarantined_six_are_named() -> None:
    """CONTEXT 4.7 / QUESTIONS.md Q-30, the architect's 08-Aug-2026 ruling, executed.

    Measured against the REAL chunk-5B register rather than a fixture, because the ruling is
    about which stocks exist: *"a live morning screens the 204 SETTLED symbols only ... the 6
    quarantined (APLAPOLLO, ASTRAL, IEX, NTPC, UPL, VBL) are never screened."*
    """
    data_root = _stores_or_skip()
    register = bt.load_residual_register(data_root / bt.RESIDUAL_LEDGER_RELPATH)
    settled = sorted(s for s, row in register.items() if row.status == "settled")
    quarantined = sorted(s for s, row in register.items() if row.status != "settled")
    assert len(settled) == 204 and quarantined == [
        "APLAPOLLO", "ASTRAL", "IEX", "NTPC", "UPL", "VBL"
    ]

    asked = tuple(settled[:3]) + tuple(quarantined) + ("NOTALISTEDSYMBOL",)
    screened, excluded = ls._screened_universe(
        asked, live=True, data_dir=data_root, residual=register
    )
    assert screened == tuple(settled[:3])
    assert [symbol for symbol, _why in excluded] == list(quarantined) + ["NOTALISTEDSYMBOL"]
    assert all(why for _symbol, why in excluded), "each exclusion carries its reason"

    # A REPLAY screens what it is asked to: a past day has its bhavcopy and its verdict, and a
    # quarantined symbol replayed deliberately is a diagnostic rather than an alert.
    replayed, none_excluded = ls._screened_universe(
        asked, live=False, data_dir=data_root, residual=register
    )
    assert replayed == asked and none_excluded == ()


# --- M23: the dedup set reaches disk before the sink fires --------------------------------------


def test_the_DEDUP_KEY_is_on_disk_BEFORE_the_alert_leaves_the_building(tmp_path: Path) -> None:
    """REVIEW_13 **M23**: the key was persisted one whole sweep behind the alert log.

    ``_deliver`` recorded and sent mid-sweep; ``persist()`` wrote ``alerted`` at the END of it. A
    death in between left ``alerts.jsonl`` holding alerts ``state.json`` did not, so even a
    correct resume re-delivered them. The window was a whole sweep -- 75-105s over 210 symbols by
    CONTEXT 4.4's own measurement, at the most failure-prone moment of the boundary.
    """
    from test_backtest import SYMBOL  # noqa: E402
    from test_live_screener import make_screener  # noqa: E402

    screener, _sink, recording = make_screener(tmp_path)
    seen: list[list[str]] = []

    class _WatchingSink:
        def deliver(self, alert) -> None:
            # Read the STATE FILE from disk at the moment the alert is being delivered.
            seen.append(list(recording.read_state().get("alerted", ())))

    screener.sinks = (_WatchingSink(),)
    alert = screener._alert(ls.ALERT_ARMED, SYMBOL, datetime(2026, 7, 17, 11, 15), {
        "side": "long", "poc_paise": "200005", "reference_paise": 200_000,
    })
    assert screener._deliver(alert) is True
    assert seen and any(SYMBOL in row for row in seen[0]), (
        "the dedup key was already on disk when the sink fired -- so a death here costs a "
        "duplicate row in the recording, never a duplicate alert to the trader"
    )
