"""THE LIVE SCREENER (chunk 13): the morning pipeline, the sweep discipline, the states.

The engines under this are all reviewed (chunks 4, 6, 7, 8) and this file deliberately does not
re-test them. What it attacks is everything the live mode ADDS, which is where a live-only bug
could live:

* the boundary grid -- CONTEXT 3.3's POC pass at 11:15, CONTEXT 3.4's last entry at 15:00,
  CONTEXT 3.4-5's square-off at 15:15;
* **the prefix reading** -- the engine, handed a half-finished day, honestly reports a
  square-off marked on the last bar it was given. A live layer that read that as an EXIT would
  close the trader's position four hours early on his screen. This is the single most dangerous
  live-only defect available and it gets its own tests, in both directions;
* CONTEXT 4.4's sweep discipline -- short retries, SKIP and re-poll at sweep end, hard deadline,
  and a skipped symbol that keeps its old state instead of being evaluated on a stale day;
* the alerts -- CONTEXT 4.4's payload, once each, never twice;
* the crash-safe resume;
* the failure banner, which is the visible half of "degrade to silence, never to a wrong alert".

The synthetic world is the chunk-9A one, imported rather than rebuilt: tick 10 paise, Row Size
24, POC 200005, ARMED at 11:15, entry 200100 at 11:30 with stop 199900 and target 200700, target
taken by the candle closing 11:45. Money on it: qty = floor(100000 / 200) = 500.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from acumen import live_screener as ls
from acumen import signals as sig
from acumen.live_recording import LiveRecording
from acumen.live_source import BarSourceError, FlakyBarSource, StoredDayBarSource, merge_bars
from acumen.minute_store import StoredBar
from acumen.signal_engine import SignalPipeline

from test_backtest import (
    RISK_PAISE,
    ROW_SIZE,
    SYMBOL,
    TRADE_DAY,
    standard_world,
)

R_POC = "200005"
ENTRY, STOP, TARGET = 200_100, 199_900, 200_700


# --- the world under test ----------------------------------------------------------------------


def make_screener(
    tmp_path: Path,
    *,
    symbols: tuple[str, ...] = (SYMBOL,),
    source=None,
    dry_run: bool = True,
    deadline_seconds: int = (sig.CANDLE_MINUTES - 1) * 60,
    live: bool = False,
) -> tuple[ls.LiveScreener, ls.CollectingAlertSink, LiveRecording]:
    """The screener over the synthetic day, wired exactly as ``build_live_screener`` wires it.

    The bias is supplied directly rather than walked, because this file is about the LIVE layer;
    the "the bias is the backtester's own" property is proved in
    ``tests/test_live_replay_invariant.py`` against the real stores, where it means something.

    ``live`` wires CONTEXT 4.7's posture: no settled battery at all (there is no bhavcopy for
    today to compute one against), the oracle-free battery per sweep, and the disclosed line on
    every alert -- exactly what ``build_live_screener(mode="live")`` produces.
    """
    from acumen.bias import BULLISH
    from acumen.bias_engine import DailyBias

    minute_store, daily_store, master, _calendar = standard_world(tmp_path, symbols=symbols)
    pipeline = SignalPipeline(
        minute_store=minute_store, daily_store=daily_store, master=master, row_size=ROW_SIZE
    )
    bias = DailyBias(
        trade_date=TRADE_DAY, bias=BULLISH, tradeable=True,
        rule="rule-1-breakout", detail="synthetic bullish day",
    )
    recording = LiveRecording.at(tmp_path / "recording")
    recording.open_session({"trade_date": TRADE_DAY.isoformat(), "code_sha": "a" * 40,
                            "master_sha256": "c" * 64, "row_size": ROW_SIZE})
    sink = ls.CollectingAlertSink()
    screener = ls.LiveScreener(
        day=TRADE_DAY,
        symbols=symbols,
        pipeline=pipeline,
        biases={symbol: bias for symbol in symbols},
        gates={} if live else ls.full_day_gates(pipeline, symbols, TRADE_DAY),
        source=source if source is not None else StoredDayBarSource(minute_store),
        recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(TRADE_DAY, datetime.min.time())),
        sinks=(sink,),
        risk_per_trade_paise=RISK_PAISE,
        deadline_seconds=deadline_seconds,
        dry_run=dry_run,
        posture=ls.POSTURE_LIVE if live else ls.POSTURE_SETTLED,
        disclosure=ls.LIVE_DISCLOSURE if live else "",
    )
    return screener, sink, recording


def run_to(screener: ls.LiveScreener, upto: str) -> list[ls.SweepReport]:
    """Sweep every boundary through ``upto`` (an 'HH:MM' label), driving the virtual clock."""
    reports = []
    for boundary in ls.boundary_stamps(screener.day):
        screener.clock.set(boundary)
        reports.append(screener.sweep(boundary))
        if boundary.strftime("%H:%M") == upto:
            break
    return reports


# --- the boundary grid ---------------------------------------------------------------------------


def test_the_boundaries_are_CONTEXT_3_4s_own_and_there_are_seventeen() -> None:
    """11:15 (the POC pass) through 15:15 (the square-off), every quarter hour.

    Hand-counted from the spec rather than from the code: CONTEXT 3.4-1 reads the reference off
    the 11:00-11:15 candle, so the first boundary a screener can act on is 11:15; CONTEXT 3.4-2's
    last entry candle closes at 15:00; CONTEXT 3.4-5 squares off at 15:15. 11:15 -> 15:15 in
    15-minute steps is 17 stamps.
    """
    stamps = ls.boundary_stamps(date(2026, 7, 17))
    assert len(stamps) == 17
    assert stamps[0] == datetime(2026, 7, 17, 11, 15)
    assert stamps[1] == datetime(2026, 7, 17, 11, 30), "the first ELIGIBLE trigger close"
    assert stamps[-2] == datetime(2026, 7, 17, 15, 0), "the last entry close (R2-Q30)"
    assert stamps[-1] == datetime(2026, 7, 17, 15, 15), "the square-off (R1-Q18)"
    assert all(
        (later - earlier) == timedelta(minutes=15)
        for earlier, later in zip(stamps, stamps[1:])
    )


# --- the morning, end to end ----------------------------------------------------------------------


def test_the_whole_morning_reaches_the_SAME_numbers_the_backtester_does(tmp_path: Path) -> None:
    """The one-engine law on the synthetic day: POC, arming, entry, stop, target, quantity.

    Every figure here is the chunk-7/chunk-8 hand-derivation, not a number this file computed:
    POC 200005 (tick 10, the busiest row [200000, 200010)), ARMED at 11:15 because the
    11:00-11:15 close 200000 is below it, entry 200100 on the candle closing 11:30, stop 199900
    (that candle's own low, CONTEXT 3.4-3 normal branch), target 200700 (3R), qty 500.
    """
    screener, sink, _rec = make_screener(tmp_path)
    screener.run_day()

    state = screener.states[SYMBOL]
    assert state.phase == ls.PHASE_EXITED
    assert str(state.poc_paise) == R_POC
    assert (state.entry_paise, state.stop_paise, state.target_paise) == (ENTRY, STOP, TARGET)
    assert state.qty == 500, "floor(100000 / 200); 501 x 200 would break the budget"
    assert state.exit_kind == sig.EXIT_TARGET and state.exit_paise == TARGET

    kinds = [alert.kind for alert in sink.alerts]
    assert kinds == [ls.ALERT_ARMED, ls.ALERT_TRIGGER, ls.ALERT_EXIT]
    trigger = next(a for a in sink.alerts if a.kind == ls.ALERT_TRIGGER)
    # CONTEXT 4.4's payload list, field for field: symbol, side, entry, SL, TP, POC, bias, time.
    assert trigger.symbol == SYMBOL
    assert trigger.at == datetime.combine(TRADE_DAY, datetime.min.time()).replace(hour=11, minute=30)
    for field in ("side", "entry_paise", "stop_paise", "target_paise", "poc_paise", "bias"):
        assert trigger.payload[field] is not None, f"CONTEXT 4.4 names {field} in the payload"
    assert trigger.payload["qty"] == 500 and trigger.payload["risk_paise"] == 200


def test_the_states_move_waiting_then_armed_then_triggered_then_exited(tmp_path: Path) -> None:
    """The dashboard's own reading, boundary by boundary. Every state is entered exactly once."""
    screener, _sink, _rec = make_screener(tmp_path)
    seen: list[tuple[str, str]] = []
    for boundary in ls.boundary_stamps(TRADE_DAY):
        screener.clock.set(boundary)
        screener.sweep(boundary)
        seen.append((boundary.strftime("%H:%M"), screener.states[SYMBOL].phase))

    assert seen[0] == ("11:15", ls.PHASE_ARMED)
    assert seen[1] == ("11:30", ls.PHASE_TRIGGERED)
    assert seen[2] == ("11:45", ls.PHASE_EXITED), "the target is taken by the 11:45 candle"
    assert {phase for _label, phase in seen[3:]} == {ls.PHASE_EXITED}, "and it stays exited"


# --- the prefix reading: the dangerous live-only case ---------------------------------------------


def test_an_open_position_is_IN_TRADE_and_is_NOT_reported_as_squared_off(tmp_path: Path) -> None:
    """The live-only defect this chunk most needed to avoid, pinned in both directions.

    Handed a prefix, :func:`acumen.signals.evaluate_day` correctly answers ``square-off`` marked
    on the last bar it was given -- that IS the right answer for a day that ended there. The
    live layer must not read it as an exit, because CONTEXT 3.4-5 squares off at 15:15 and at no
    other time. Driven on a day whose position never closes: the target is moved out of reach by
    truncating the world to the entry candle.
    """
    screener, sink, _rec = make_screener(tmp_path)
    # Sweep only up to 11:30 -- the entry candle exists, nothing after it does.
    run_to(screener, "11:30")
    state = screener.states[SYMBOL]
    assert state.phase == ls.PHASE_TRIGGERED
    assert state.exit_kind is None, "no exit has happened; the engine's marker is not one"
    assert not any(alert.kind in (ls.ALERT_EXIT, ls.ALERT_SQUARE_OFF) for alert in sink.alerts)

    # ... and the SAME engine answer at 15:15 IS an exit, because the square-off candle has now
    # closed. The reading is the boundary, not a guess about the shape of the answer.
    assert not screener._square_off_bar_closed(datetime(2026, 7, 17, 15, 0))
    assert screener._square_off_bar_closed(datetime(2026, 7, 17, 15, 15))


def test_a_position_still_open_at_15_15_IS_squared_off_and_alerts(tmp_path: Path) -> None:
    """The other direction: at the square-off boundary, the engine's marker IS the exit.

    Built by removing the candle that takes the target, so the trade runs to the close. The
    exit is priced at the marked candle's CLOSE (CONTEXT 3.4-5 / R1-Q18), which is the chunk-8
    rule and is read off the aggregated bar rather than re-derived here.
    """
    from test_backtest import build_stores, lead_rows, row_for_minutes, synthetic_minutes
    from test_backtest import SEED_A, SEED_B, daily_row, R

    minutes = [m for m in synthetic_minutes(TRADE_DAY) if m.stamp.hour != 11 or m.stamp.minute != 30]
    rows = dict(lead_rows())
    rows.update({
        SEED_A: daily_row(SEED_A, R(1990), R(2000), R(1980), R(1995), 1000),
        SEED_B: daily_row(SEED_B, R(1995), R(2010), R(1990), R(2008), 1000),
        TRADE_DAY: row_for_minutes(TRADE_DAY, minutes),
    })
    stores = build_stores(tmp_path, minute_days={TRADE_DAY: minutes}, daily_rows=rows)
    minute_store, daily_store, master, _cal = stores

    from acumen.bias import BULLISH
    from acumen.bias_engine import DailyBias

    pipeline = SignalPipeline(minute_store=minute_store, daily_store=daily_store,
                              master=master, row_size=ROW_SIZE)
    recording = LiveRecording.at(tmp_path / "rec2")
    recording.open_session({"trade_date": TRADE_DAY.isoformat()})
    sink = ls.CollectingAlertSink()
    screener = ls.LiveScreener(
        day=TRADE_DAY, symbols=(SYMBOL,), pipeline=pipeline,
        biases={SYMBOL: DailyBias(trade_date=TRADE_DAY, bias=BULLISH, tradeable=True,
                                  rule="rule-1-breakout", detail="synthetic")},
        gates=ls.full_day_gates(pipeline, (SYMBOL,), TRADE_DAY),
        source=StoredDayBarSource(minute_store), recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(TRADE_DAY, datetime.min.time())),
        sinks=(sink,), risk_per_trade_paise=RISK_PAISE,
    )
    screener.run_day()

    state = screener.states[SYMBOL]
    assert state.phase == ls.PHASE_EXITED
    assert state.exit_kind == sig.EXIT_SQUARE_OFF
    assert [a.kind for a in sink.alerts][-1] == ls.ALERT_SQUARE_OFF


# --- CONTEXT 4.4's sweep discipline ---------------------------------------------------------------


def test_a_failing_symbol_is_retried_then_SKIPPED_and_never_blocks_the_queue(
    tmp_path: Path,
) -> None:
    """CONTEXT 4.4, literally: short retries (0.5s/1s), then skip, then re-poll at sweep end.

    The failing symbol must not cost the others their evaluation, and it must not be evaluated
    on a day it does not have. It keeps its previous state and is REPORTED -- that is the
    difference between a screener that degrades and one that lies.
    """
    _s, _sink, _rec = make_screener(tmp_path, symbols=("SYNTH", "OTHER"))
    minute_store, daily_store, master, _cal = standard_world(tmp_path / "w2",
                                                             symbols=("SYNTH", "OTHER"))
    source = FlakyBarSource(
        inner=StoredDayBarSource(minute_store), fail_symbols=frozenset({"OTHER"}),
        fail_times=99,
    )
    screener, sink, recording = make_screener(
        tmp_path / "w3", symbols=("SYNTH", "OTHER"), source=source
    )
    report = run_to(screener, "11:15")[0]

    assert "SYNTH" in report.fetched, "the healthy symbol was evaluated"
    assert report.skipped == ("OTHER",), "the failing one is skipped, not raised"
    assert not report.complete
    assert screener.states["OTHER"].phase == ls.PHASE_SKIPPED
    assert screener.states["SYNTH"].phase == ls.PHASE_ARMED

    # every attempt is on the record: 3 first-pass tries (1 + two backoffs), 2 on the re-poll
    errors = [row for row in recording.fetches()
              if row["symbol"] == "OTHER" and row["outcome"] == "error"]
    assert len(errors) == 5, "CONTEXT 4.4's short retries, then the sweep-end re-poll"
    skips = [row for row in recording.fetches() if row["outcome"] == "skipped-deadline"]
    assert [row["symbol"] for row in skips] == ["OTHER"]


def test_a_transient_burst_HEALS_on_the_sweep_end_re_poll(tmp_path: Path) -> None:
    """CONTEXT 4.3: *"transient false 'access denied' bursts are NORMAL -- retry"*.

    A source that fails three times and then answers is exactly that burst. The first pass gives
    up on it (3 tries) and the sweep-end re-poll gets it, so the symbol is evaluated in the SAME
    sweep and never reaches the dashboard as skipped.
    """
    minute_store, _d, _m, _c = standard_world(tmp_path / "w", symbols=("SYNTH",))
    source = FlakyBarSource(
        inner=StoredDayBarSource(minute_store), fail_symbols=frozenset({SYMBOL}), fail_times=3
    )
    screener, _sink, _rec = make_screener(tmp_path / "s", source=source)
    report = run_to(screener, "11:15")[0]
    assert report.fetched == (SYMBOL,) and not report.skipped
    assert report.complete and screener.states[SYMBOL].phase == ls.PHASE_ARMED


def test_the_hard_deadline_stops_a_sweep_and_the_rest_are_SKIPPED_not_dropped(
    tmp_path: Path,
) -> None:
    """CONTEXT 4.4's *"hard sweep deadline before the next boundary"*.

    A sweep that ran past its deadline would report at 11:45 about the 11:30 candle. So it stops,
    and everything it did not reach is skipped and COUNTED -- the queue drains, the boundary is
    kept, and the operator sees a banner rather than a quiet short sweep.
    """
    screener, _sink, _rec = make_screener(
        tmp_path, symbols=("SYNTH", "OTHER"), deadline_seconds=0
    )
    screener.clock.set(datetime(2026, 7, 17, 11, 16))  # already past a zero-second deadline
    report = screener.sweep(datetime(2026, 7, 17, 11, 15))

    assert report.deadline_hit
    assert not report.fetched and set(report.skipped) == {"SYNTH", "OTHER"}
    assert not report.complete
    assert screener.banner and "NOT being watched" in screener.banner


def test_the_failure_banner_is_raised_and_then_CLEARED_by_a_clean_sweep(tmp_path: Path) -> None:
    """Silence has two meanings on this screen and they must never look alike.

    The banner is the safety rail's visible half: raised the moment a sweep is incomplete,
    cleared the moment one is not. A banner that could only be raised would rot into wallpaper.
    """
    minute_store, _d, _m, _c = standard_world(tmp_path / "w", symbols=("SYNTH",))
    source = FlakyBarSource(
        inner=StoredDayBarSource(minute_store), fail_symbols=frozenset({SYMBOL}), fail_times=5
    )
    screener, sink, recording = make_screener(tmp_path / "s", source=source)

    screener.clock.set(datetime(2026, 7, 17, 11, 15))
    screener.sweep(datetime(2026, 7, 17, 11, 15))
    assert screener.banner
    assert [a.kind for a in sink.alerts] == [ls.ALERT_FAILURE]

    screener.clock.set(datetime(2026, 7, 17, 11, 30))
    screener.sweep(datetime(2026, 7, 17, 11, 30))
    assert screener.banner == "", "the source healed; the banner goes"
    kinds = [row["kind"] for row in recording.events()]
    assert "banner-raised" in kinds and "banner-cleared" in kinds


def test_a_skipped_symbol_is_NEVER_evaluated_on_the_day_it_does_not_have(tmp_path: Path) -> None:
    """The safety rail, stated as a property: no data -> no alert, ever.

    "Degrades to SILENCE, never to a wrong alert" is only true if the missing symbol produces
    nothing at all. A screener that fell back to the last day it managed to fetch would produce
    a confident, wrong alert -- the exact failure the rail names.
    """
    minute_store, _d, _m, _c = standard_world(tmp_path / "w", symbols=("SYNTH",))
    source = FlakyBarSource(
        inner=StoredDayBarSource(minute_store), fail_symbols=frozenset({SYMBOL}), fail_times=999
    )
    screener, sink, _rec = make_screener(tmp_path / "s", source=source)
    screener.run_day()

    assert screener.states[SYMBOL].phase == ls.PHASE_SKIPPED
    assert not screener.bars.get(SYMBOL), "no bars were ever accepted"
    assert all(a.kind == ls.ALERT_FAILURE for a in sink.alerts), "no per-symbol alert at all"


# --- alerts ---------------------------------------------------------------------------------------


def test_an_alert_fires_ONCE_however_many_sweeps_re_confirm_it(tmp_path: Path) -> None:
    """Every boundary re-evaluates the whole day, so every boundary re-derives the same entry.

    Without dedup the trader would get the same trigger seventeen times, which is worse than no
    alert: he would learn to dismiss them. The key is (symbol, kind) and it survives a resume.
    """
    screener, sink, _rec = make_screener(tmp_path)
    screener.run_day()
    triggers = [a for a in sink.alerts if a.kind == ls.ALERT_TRIGGER]
    assert len(triggers) == 1
    assert len(sink.alerts) == len(set((a.symbol, a.kind) for a in sink.alerts))


def test_a_dry_run_alert_is_MARKED_as_one_in_the_recording(tmp_path: Path) -> None:
    """plan.md's chunk-13 card ships dry-mode. A dry alert that looked live in the record would
    make the whole recording untrustworthy as evidence about what the trader was told."""
    screener, sink, recording = make_screener(tmp_path, dry_run=True)
    screener.run_day()
    assert all(alert.payload["dry_run"] is True for alert in sink.alerts)
    assert all(row["payload"]["dry_run"] is True for row in recording.alerts())


def test_the_sound_sink_stays_QUIET_for_arming_and_rings_for_a_trigger(tmp_path: Path) -> None:
    """A bell that goes off thirty times a morning is a bell he learns to ignore -- and the one
    it costs him is the one that matters. Arming is information; a trigger is an instruction."""
    rings: list[str] = []
    sound = ls.SoundAlertSink(out=rings.append)
    for kind in (ls.ALERT_ARMED, ls.ALERT_TRIGGER, ls.ALERT_EXIT, ls.ALERT_FAILURE):
        sound.deliver(ls.RecordedAlert(kind=kind, symbol="X", at=datetime(2026, 7, 17, 11, 30),
                                       payload={}))
    assert sound.rings == [ls.ALERT_TRIGGER, ls.ALERT_EXIT, ls.ALERT_FAILURE]


def test_the_alert_line_leads_with_the_four_numbers_he_trades_on(tmp_path: Path) -> None:
    """DESIGN.md PART II: what he needs at 11:30 is entry, SL, TP, qty -- in that order."""
    alert = ls.RecordedAlert(
        kind=ls.ALERT_TRIGGER, symbol="SYNTH", at=datetime(2026, 7, 17, 11, 30),
        payload={"side": "long", "entry_paise": ENTRY, "stop_paise": STOP,
                 "target_paise": TARGET, "qty": 500, "poc_paise": R_POC, "bias": "bullish"},
    )
    line = ls.format_alert(alert)
    assert line.index("entry") < line.index("SL") < line.index("TP") < line.index("qty")
    assert "2,001.00" in line and "1,999.00" in line and "2,007.00" in line
    assert line.startswith("[11:30] SYNTH LONG")


# --- resume ----------------------------------------------------------------------------------------


def test_a_screener_that_DIES_mid_morning_comes_back_where_it_was(tmp_path: Path) -> None:
    """The chunk card's simulated-disconnect test.

    A screener that restarted at 09:15 would re-alert everything it had already sent, which is
    the dedup failure wearing a crash. The bars come back from the CANDLE FILES, not from the
    state summary, so the resumed session continues the same bytes it recorded.
    """
    screener, sink, recording = make_screener(tmp_path)
    run_to(screener, "11:45")
    assert screener.states[SYMBOL].phase == ls.PHASE_EXITED
    fired = [ls.LiveScreener._alert_key(alert) for alert in sink.alerts]
    assert len(fired) == 3

    # ... the process dies. A NEW screener, same recording.
    reborn, sink2, _rec = make_screener(tmp_path)
    assert reborn.restore() is True
    assert reborn.sweeps_done == ["11:15", "11:30", "11:45"]
    assert reborn.alerted == set(fired), (
        "the dedup set round-trips under the re-cut (symbol, kind, identity) key"
    )
    assert len(reborn.bars[SYMBOL]) == len(screener.bars[SYMBOL]), "bars from the candle files"
    # REVIEW_13 B8's compounding half: restore() used to leave every symbol at its pre-open
    # phase, so even a correct resume had forgotten that the day was over.
    assert reborn.states[SYMBOL].phase == ls.PHASE_EXITED, "the STATES come back too"
    assert reborn.states[SYMBOL].entry_paise == ENTRY
    assert reborn.states[SYMBOL].exit_kind == screener.states[SYMBOL].exit_kind
    # ... and so does CONTEXT 3.3's pinned POC, so a restart cannot re-fix the day's POC from a
    # window that is more complete now than it was at 11:15 (REVIEW_13 B3).
    assert reborn.profiles[SYMBOL].poc_paise == screener.profiles[SYMBOL].poc_paise

    for boundary in ls.boundary_stamps(TRADE_DAY)[3:]:
        reborn.clock.set(boundary)
        reborn.sweep(boundary)
    assert sink2.alerts == [], "nothing is re-sent"
    assert reborn.states[SYMBOL].phase == ls.PHASE_EXITED
    assert "resumed" in {row["kind"] for row in recording.events()}


def test_a_resume_REFUSES_a_recording_from_another_day(tmp_path: Path) -> None:
    """A screener that quietly adopted yesterday's state would trade today on yesterday's POC."""
    screener, _sink, recording = make_screener(tmp_path)
    run_to(screener, "11:15")
    recording.write_state(dict(recording.read_state(), trade_date="2026-07-16"))
    reborn, _s2, _r = make_screener(tmp_path)
    with pytest.raises(ls.ScreenerError, match="2026-07-17"):
        reborn.restore()


# --- the bar sources -------------------------------------------------------------------------------


def test_a_poll_at_a_boundary_sees_the_bars_that_have_actually_CLOSED(tmp_path: Path) -> None:
    """CONTEXT 7-E12's boundary, which is where an off-by-one bucket bug would live.

    A bar stamped ``t`` covers ``[t, t+1min)``, so a poll at 11:15 may see 11:14 and must not see
    11:15. Getting this wrong by one bar moves CONTEXT 3.3's profile window, hence the POC, hence
    every entry, stop and target on the day.
    """
    minute_store, _d, _m, _c = standard_world(tmp_path, symbols=("SYNTH",))
    source = StoredDayBarSource(minute_store)
    at_1115 = source.fetch(SYMBOL, TRADE_DAY, datetime(2026, 7, 17, 11, 15))
    assert max(b.stamp for b in at_1115) == datetime(2026, 7, 17, 11, 14)
    at_1130 = source.fetch(SYMBOL, TRADE_DAY, datetime(2026, 7, 17, 11, 30))
    assert max(b.stamp for b in at_1130) == datetime(2026, 7, 17, 11, 29)
    assert len(at_1115) == 120, "exactly CONTEXT 3.3's 09:15..11:14 window"


def test_merging_polls_keeps_the_latest_and_sorts_by_stamp() -> None:
    """One resolution rule, in one place, so the in-memory day and the replayed day agree."""
    def b(minute: int, close: int) -> StoredBar:
        return StoredBar(symbol="X", stamp=datetime(2026, 7, 17, 9, 15) + timedelta(minutes=minute),
                         open_paise=close, high_paise=close, low_paise=close,
                         close_paise=close, volume=1)

    merged = merge_bars([b(1, 100), b(0, 200)], [b(1, 999)])
    assert [bar.stamp.minute for bar in merged] == [15, 16]
    assert merged[1].close_paise == 999


def test_the_flaky_source_raises_a_BarSourceError_and_then_heals() -> None:
    """The simulated disconnect is a shipped object, because the failure it models is spec'd."""
    class Inner:
        def fetch(self, symbol, day, upto):
            return ()

    source = FlakyBarSource(inner=Inner(), fail_symbols=frozenset({"X"}), fail_times=2)
    for _ in range(2):
        with pytest.raises(BarSourceError):
            source.fetch("X", TRADE_DAY, datetime(2026, 7, 17, 11, 15))
    assert source.fetch("X", TRADE_DAY, datetime(2026, 7, 17, 11, 15)) == ()
    assert source.fetch("Y", TRADE_DAY, datetime(2026, 7, 17, 11, 15)) == ()


# --- what the screener refuses ---------------------------------------------------------------------


def test_a_suppressed_or_unseeded_day_is_REFUSED_before_a_single_poll(tmp_path: Path) -> None:
    """CONTEXT 3.2's demerger block and its seeding rule reach the dashboard as `refused`.

    They are not sweep failures and must not look like them: nothing is wrong with the feed, the
    strategy itself says there is no trade in that stock today.
    """
    from acumen.bias_engine import DailyBias

    screener, _sink, _rec = make_screener(tmp_path)
    screener.biases[SYMBOL] = DailyBias(
        trade_date=TRADE_DAY, bias="bullish", tradeable=False, rule="suppressed",
        detail="suppressed: demerger ex-date is D-1 of the pair (CONTEXT 3.2)", suppressed=True,
    )
    screener.states[SYMBOL] = screener._initial_state(SYMBOL)
    assert screener.states[SYMBOL].phase == ls.PHASE_REFUSED
    screener.run_day()
    assert screener.states[SYMBOL].phase == ls.PHASE_REFUSED

    screener.biases[SYMBOL] = DailyBias(
        trade_date=TRADE_DAY, bias=None, tradeable=False, rule="unseeded", detail="not seeded",
    )
    screener.states[SYMBOL] = screener._initial_state(SYMBOL)
    assert screener.states[SYMBOL].phase == ls.PHASE_REFUSED


def test_by_phase_groups_every_symbol_exactly_once(tmp_path: Path) -> None:
    """DESIGN.md PART II: *"a stock never appears twice, never in two states"*."""
    screener, _sink, _rec = make_screener(tmp_path, symbols=("SYNTH", "OTHER"))
    screener.run_day()
    grouped = screener.by_phase()
    flat = [state.symbol for rows in grouped.values() for state in rows]
    assert sorted(flat) == ["OTHER", "SYNTH"]
    assert set(grouped) >= set(ls.PHASES)


# --- closing the day: what the RECORDING owes chunk 14 ------------------------------------------


def test_the_day_is_CLOSED_after_15_29_so_the_recording_can_be_GATED(tmp_path: Path) -> None:
    """The replay contract's load-bearing detail, and it was found by a test rather than by luck.

    CONTEXT 4.5 gate 1 reconciles the day's WHOLE folded 1-minute volume against the bhavcopy. A
    recording that stopped at the last decision boundary would hold 09:15..15:14 and could never
    be pushed back through the backtest path at all -- the gate would refuse it for a shortfall
    the screener itself created. So the day is closed with one final poll after 15:29.

    It is a RECORDING step and not a decision step, and that is asserted: nothing after 15:14 may
    move a state (chunk 8 proved the 15:15-stamped candle is never read), so the close-out is
    evidence, not a late correction.
    """
    screener, _sink, recording = make_screener(tmp_path)
    reports = screener.run_day()

    assert len(reports) == len(ls.boundary_stamps(TRADE_DAY)) + 1, "17 boundaries, then the close"
    assert reports[-1].boundary == datetime.combine(TRADE_DAY, ls.SESSION_END)

    before = screener.states[SYMBOL]
    # the recording holds the WHOLE session, not the prefix the last boundary could see
    stored_last = max(bar.stamp for bar in recording.bars(SYMBOL, TRADE_DAY))
    assert stored_last >= datetime(2026, 7, 17, 11, 30), "the day ran to its own last bar"
    assert screener.bars[SYMBOL] == recording.bars(SYMBOL, TRADE_DAY)

    # and the close-out changed nothing
    assert before.phase == ls.PHASE_EXITED and before.entry_paise == ENTRY
    assert "post-session-state-change" not in {row["kind"] for row in recording.events()}


def test_the_gate_battery_is_computed_ONCE_from_the_whole_day_not_per_boundary(
    tmp_path: Path,
) -> None:
    """Why ``gates`` is handed in rather than recomputed: it is a WHOLE-DAY measurement.

    Gate 1 folds the session's total volume against the bhavcopy's. On a growing prefix that
    fold is short by construction, so a battery recomputed at 11:15 would refuse every symbol on
    every day -- and the refusal would look like a data problem rather than an arithmetic one.
    This is the same fact QUESTIONS.md Q-28 turns on, so it gets its own test.
    """
    screener, _sink, _rec = make_screener(tmp_path)
    whole_day = screener.gates[SYMBOL]
    assert whole_day.usable, "the synthetic day passes the battery"

    prefix = screener.pipeline.gate_day(
        SYMBOL, TRADE_DAY,
        screener.pipeline.minute_store.minutes(SYMBOL, TRADE_DAY)[:60],
    )
    assert not prefix.usable, (
        "half a day of volume cannot reconcile against a whole day's bhavcopy -- which is "
        "exactly why the live path cannot run this battery at all (Q-28)"
    )
    assert prefix.refusal == "gate 1 (volume reconciliation)"
