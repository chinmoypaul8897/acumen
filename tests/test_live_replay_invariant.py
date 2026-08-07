"""THE REPLAY INVARIANT (chunk 13's Done-when), against the real stores.

plan.md's chunk-13 card: *"the live pipeline in replay mode over 3 recorded historical days
produces byte-identical signals to the chunk-9 backtester on those days; morning-refresh test on
a recorded day yields the same biases as the backtest path; simulated-disconnect test recovers"*.

CONTEXT section 6 is the law being tested and it is a strong claim -- *"same code path,
guaranteed no backtest/live drift"*. There are two ways to make that claim true and only one of
them is worth anything: write a second implementation and check it agrees, or **have one
implementation**. This chunk took the second, so what these tests really check is that the seam
is where it is claimed to be:
:meth:`acumen.signal_engine.SignalPipeline.evaluate` is the SAME call the backtester's
:meth:`~acumen.signal_engine.SignalPipeline.stock_day` makes, and the live screener does not go
round it.

The heavy three-day walk lives in ``docs/evidence/chunk13_replay_walk.py`` with its committed
output (CLAUDE.md git rules, REVIEW_7 finding C3). What is in the SUITE is the named golden --
**HDFCBANK 2026-06-10**, the real Rule-3 outside-bar day chunk 7 walked candle by candle and
chunk 8 priced -- because a test that only ever ran in an evidence script is a test that stops
being run.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import ast
import inspect
from datetime import date, datetime
from textwrap import dedent
from pathlib import Path

import pytest

from acumen import backtest as bt
from acumen import live_screener as ls
from acumen import signal_engine as se
from acumen import signals as sig
from acumen.config import load_config
from acumen.live_recording import LiveRecording
from acumen.live_source import FlakyBarSource, StoredDayBarSource
from acumen.minute_store import MinuteStore

#: The chunk-7 / chunk-8 named golden, re-derived from the stores by both reviews. Typed here as
#: the pin it is: if the live path moves one of these, this file fails rather than the claim
#: quietly changing.
GOLDEN_SYMBOL = "HDFCBANK"
GOLDEN_DAY = date(2026, 6, 10)
GOLDEN_POC_PAISE = 73_980          # tick 5, totalTicks 182, tpr 8, 23 rows
GOLDEN_REFERENCE_PAISE = 73_820    # the 11:00-11:15 close, BELOW the POC -> ARMED
GOLDEN_ENTRY_PAISE = 74_095
GOLDEN_STOP_PAISE = 73_810         # NOT a gap entry: 738.10 < POC, so the normal branch
GOLDEN_TARGET_PAISE = 74_950
GOLDEN_QTY = 350                   # floor(100000 / 285); 351 x 285 = 100,035 > budget


def _stores_or_skip() -> None:
    config = load_config(include_env=False)
    for relpath in ("minute_store", "daily_store"):
        store_dir = config.path("data_root") / relpath
        if not store_dir.is_dir():
            pytest.skip(f"local {relpath} {store_dir} is absent (the stores are gitignored)")
    if not Path(config.instrument_master_path()).is_file():
        pytest.skip("the pinned instrument master is absent")


def _screener(tmp_path: Path, *, source=None, symbols=(GOLDEN_SYMBOL,)) -> ls.LiveScreener:
    config = load_config(include_env=False)
    data_root = config.path("data_root")
    return ls.build_live_screener(
        GOLDEN_DAY, symbols,
        source=source if source is not None
        else StoredDayBarSource(MinuteStore.at(data_root / "minute_store")),
        recording=LiveRecording.at(tmp_path / "recording"),
        clock=ls.VirtualClock(stamp=datetime.combine(GOLDEN_DAY, datetime.min.time())),
        mode="replay",
        sinks=(ls.CollectingAlertSink(),),
    )


# --- the seam itself, provable without touching a store ------------------------------------------


def test_the_backtester_and_the_screener_call_the_SAME_evaluate() -> None:
    """The one-engine law, pinned at the source, because that is where it is either true or not.

    ``stock_day`` -- the whole backtest's per-day entry point -- loads the minutes and then
    DELEGATES. If a future session re-inlines the pipeline into ``stock_day``, or gives the
    screener its own copy, this goes red immediately rather than four months later on a real
    morning. Everything below this test measures a consequence; this one is the cause.
    """
    body = inspect.getsource(se.SignalPipeline.stock_day)
    assert "self.evaluate(" in body, (
        "stock_day must DELEGATE to evaluate; a second implementation is backtest/live drift"
    )
    live = inspect.getsource(ls.LiveScreener._evaluate)
    assert "self.pipeline.evaluate(" in live
    # the CODE, not the prose: the docstring names the engines it is forbidden to call, which is
    # the point of it, so the docstring is removed before the scan.
    function = ast.parse(dedent(live)).body[0]
    if (function.body and isinstance(function.body[0], ast.Expr)
            and isinstance(function.body[0].value, ast.Constant)):
        function.body = function.body[1:]
    code = ast.unparse(function)
    for engine_call in ("day_profile", "aggregate_15min", "evaluate_day", "gate_day"):
        assert engine_call not in code, (
            f"the live layer calls {engine_call} directly -- it must go through evaluate()"
        )


def test_evaluate_and_stock_day_agree_on_the_synthetic_day(tmp_path: Path) -> None:
    """The delegation, exercised: the two entry points return the SAME object, field for field.

    Deliberately on the synthetic world so it runs everywhere, including a clone with no stores.
    """
    from test_backtest import ROW_SIZE, SYMBOL, TRADE_DAY, standard_world
    from acumen.bias import BULLISH
    from acumen.bias_engine import DailyBias

    minute_store, daily_store, master, _cal = standard_world(tmp_path)
    pipeline = se.SignalPipeline(minute_store=minute_store, daily_store=daily_store,
                                 master=master, row_size=ROW_SIZE)
    bias = DailyBias(trade_date=TRADE_DAY, bias=BULLISH, tradeable=True,
                     rule="rule-1-breakout", detail="synthetic")

    through_store = pipeline.stock_day(SYMBOL, TRADE_DAY, bias=bias)
    minutes = minute_store.minutes(SYMBOL, TRADE_DAY)
    through_minutes = pipeline.evaluate(SYMBOL, TRADE_DAY, bias=bias, minutes=minutes)
    gates = pipeline.gate_day(SYMBOL, TRADE_DAY, minutes)
    with_gates = pipeline.evaluate(SYMBOL, TRADE_DAY, bias=bias, minutes=minutes, gates=gates)

    assert through_store == through_minutes == with_gates


# --- the named golden, from the real stores ------------------------------------------------------


def test_the_LIVE_screener_reproduces_the_chunk_7_and_8_golden_exactly(tmp_path: Path) -> None:
    """HDFCBANK 2026-06-10 through the LIVE pipeline, bar by bar, on a virtual clock.

    Every figure asserted here was derived twice already by sessions that had never seen this
    module: chunk 7 walked the day candle by candle from the raw minute parquet, and REVIEW_8
    re-derived the money with its own 15-minute aggregation. The live screener is handed the day
    a boundary at a time and must land on all of them.
    """
    _stores_or_skip()
    screener = _screener(tmp_path)
    sink = screener.sinks[0]
    screener.run_day()

    state = screener.states[GOLDEN_SYMBOL]
    assert state.poc_paise == GOLDEN_POC_PAISE
    assert state.reference_paise == GOLDEN_REFERENCE_PAISE
    assert state.entry_paise == GOLDEN_ENTRY_PAISE
    assert state.stop_paise == GOLDEN_STOP_PAISE
    assert state.target_paise == GOLDEN_TARGET_PAISE
    assert state.qty == GOLDEN_QTY
    assert state.exit_kind == sig.EXIT_TARGET
    assert state.phase == ls.PHASE_EXITED
    assert state.bias == "bullish" and state.side == sig.LONG

    kinds = [alert.kind for alert in sink.alerts]
    assert kinds == [ls.ALERT_ARMED, ls.ALERT_TRIGGER, ls.ALERT_EXIT]
    trigger = sink.alerts[1]
    assert trigger.at == datetime(2026, 6, 10, 11, 30), "the first eligible trigger close"
    assert sink.alerts[2].at == datetime(2026, 6, 10, 13, 15), (
        "chunk 7's own sentence: the target lands on the 13:15-closing candle"
    )


def test_the_replayed_day_is_IDENTICAL_to_the_backtesters_answer(tmp_path: Path) -> None:
    """The invariant itself: the live day's final :class:`SignalDay` == the backtester's.

    Not "the same numbers" -- the same OBJECT, compared field for field including the whole
    transition trail, because a divergence in a transition note is a divergence in the audit
    trail chunk 12's replay pack is built from.
    """
    _stores_or_skip()
    screener = _screener(tmp_path)
    screener.run_day()

    # the backtester's own answer for the same symbol-day, through stock_day
    backtest_day = screener.pipeline.stock_day(
        GOLDEN_SYMBOL, GOLDEN_DAY, bias=screener.biases[GOLDEN_SYMBOL]
    )
    live_day = screener.pipeline.evaluate(
        GOLDEN_SYMBOL, GOLDEN_DAY, bias=screener.biases[GOLDEN_SYMBOL],
        minutes=screener.bars[GOLDEN_SYMBOL], gates=screener.gates[GOLDEN_SYMBOL],
    )
    assert live_day.signal == backtest_day.signal
    assert live_day.profile.poc_paise == backtest_day.profile.poc_paise
    assert live_day.bars == backtest_day.bars
    assert live_day == backtest_day


def test_the_bars_the_screener_COLLECTED_are_the_bars_the_lake_holds(tmp_path: Path) -> None:
    """Why the invariant holds, rather than that it does.

    CONTEXT 4.4's design is that live bars ARE backtest bars -- same endpoint, no tick-building.
    In replay that is testable to the byte: what the screener accumulated across seventeen
    polls must equal the stored day exactly. If this ever fails, the invariant above is a
    coincidence.
    """
    _stores_or_skip()
    config = load_config(include_env=False)
    store = MinuteStore.at(config.path("data_root") / "minute_store")
    screener = _screener(tmp_path)
    screener.run_day()

    assert screener.bars[GOLDEN_SYMBOL] == store.minutes(GOLDEN_SYMBOL, GOLDEN_DAY)
    # ...and so is the RECORDING's own de-duplicated reading of its candle file
    assert screener.recording.bars(GOLDEN_SYMBOL, GOLDEN_DAY) == store.minutes(
        GOLDEN_SYMBOL, GOLDEN_DAY
    )
    assert screener.recording.revisions(GOLDEN_SYMBOL) == (), "a lake replay revises nothing"


def test_the_screeners_pre_open_bias_is_the_BACKTESTERS_bias(tmp_path: Path) -> None:
    """The card's morning-refresh clause: the same day, the same bias, from the same engine.

    ``build_live_screener`` takes the bias from ``BacktestRunner.bias_map``, which is the run's
    own path-dependent carry through the GATED Rule-3 loader (QUESTIONS.md Q-21(b), Q-22(a)).
    Recomputing it here from the same runner is what proves the screener did not shortcut it --
    including the rule that produced it, which for this day is the real outside-bar Rule 3.
    """
    _stores_or_skip()
    screener = _screener(tmp_path)
    runner, _master, _ca = bt.build_runner(
        (GOLDEN_SYMBOL,), GOLDEN_DAY, GOLDEN_DAY, seed_from=GOLDEN_DAY, label="parity-check"
    )
    series, _reason = runner.bias_map(GOLDEN_SYMBOL)
    assert screener.biases[GOLDEN_SYMBOL] == series[GOLDEN_DAY]
    assert screener.biases[GOLDEN_SYMBOL].bias == "bullish"
    assert screener.biases[GOLDEN_SYMBOL].rule.startswith("rule-3"), (
        "2026-06-10 is the real Rule-3 outside-bar day chunk 7 found; if the rule moved, the "
        "bias engine moved"
    )
    # the recording carries it, so a replay can check the bias the day actually ran on
    assert screener.recording.read_bias()[GOLDEN_SYMBOL]["rule"] == series[GOLDEN_DAY].rule


def test_a_DISCONNECT_mid_morning_recovers_to_the_same_answer(tmp_path: Path) -> None:
    """The card's simulated-disconnect test, on the real day.

    The feed dies for the first three polls of the morning and then heals. CONTEXT 4.3 calls
    that burst NORMAL, so the correct outcome is not a graceful degradation -- it is the SAME
    trade, found late or found on time, and never a different one.
    """
    _stores_or_skip()
    config = load_config(include_env=False)
    inner = StoredDayBarSource(MinuteStore.at(config.path("data_root") / "minute_store"))

    # (a) a burst inside ONE sweep: three failures, healed by the sweep-end re-poll. CONTEXT 4.4's
    # retry policy is doing exactly its job and the boundary is not missed at all.
    healed = _screener(
        tmp_path / "healed",
        source=FlakyBarSource(inner=inner, fail_symbols=frozenset({GOLDEN_SYMBOL}), fail_times=3),
    )
    reports = healed.run_day()
    assert reports[0].complete and reports[0].fetched == (GOLDEN_SYMBOL,)
    assert healed.states[GOLDEN_SYMBOL].entry_paise == GOLDEN_ENTRY_PAISE
    assert [a.kind for a in healed.sinks[0].alerts] == [
        ls.ALERT_ARMED, ls.ALERT_TRIGGER, ls.ALERT_EXIT
    ]

    # (b) a burst that outlives the whole 11:15 sweep. The POC pass is LOST, the banner goes up,
    # and 11:30 recovers. The trade is the same trade -- but the ARMED alert is gone forever,
    # because arming happened during the outage and this screener does not invent it afterwards.
    outage = _screener(
        tmp_path / "outage",
        source=FlakyBarSource(inner=inner, fail_symbols=frozenset({GOLDEN_SYMBOL}), fail_times=6),
    )
    reports = outage.run_day()
    assert not reports[0].complete, "the 11:15 POC pass really did fail"
    assert reports[0].skipped == (GOLDEN_SYMBOL,)
    assert reports[1].complete, "and 11:30 recovered"
    assert outage.states[GOLDEN_SYMBOL].phase == ls.PHASE_EXITED
    assert outage.states[GOLDEN_SYMBOL].entry_paise == GOLDEN_ENTRY_PAISE
    assert outage.states[GOLDEN_SYMBOL].exit_kind == sig.EXIT_TARGET
    assert outage.banner == "", "and the banner cleared once the feed came back"
    kinds = [a.kind for a in outage.sinks[0].alerts]
    assert kinds == [ls.ALERT_FAILURE, ls.ALERT_TRIGGER, ls.ALERT_EXIT], (
        "the trade is identical; the arming alert is honestly absent, not back-filled"
    )
    events = {row["kind"] for row in outage.recording.events()}
    assert "banner-raised" in events and "banner-cleared" in events


def test_a_CRASH_mid_morning_resumes_to_the_same_answer(tmp_path: Path) -> None:
    """Crash-safe intra-day resume on the real day: same trade, no alert sent twice."""
    _stores_or_skip()
    first = _screener(tmp_path)
    for boundary in ls.boundary_stamps(GOLDEN_DAY)[:2]:   # 11:15 and 11:30
        first.clock.set(boundary)
        first.sweep(boundary)
    assert first.states[GOLDEN_SYMBOL].phase == ls.PHASE_TRIGGERED
    already = set(first.alerted)

    reborn = _screener(tmp_path)
    assert reborn.restore() is True
    assert reborn.alerted == already
    sink = reborn.sinks[0]
    for boundary in ls.boundary_stamps(GOLDEN_DAY)[2:]:
        reborn.clock.set(boundary)
        reborn.sweep(boundary)

    assert reborn.states[GOLDEN_SYMBOL].exit_kind == sig.EXIT_TARGET
    assert [alert.kind for alert in sink.alerts] == [ls.ALERT_EXIT], (
        "only the exit is new; the armed and trigger alerts are not re-sent"
    )


def test_the_recording_carries_everything_a_replay_needs(tmp_path: Path) -> None:
    """The replay contract, listed against what chunk 14 will ask for.

    The manifest must pin the MACHINE (spec, code, config, the Q-20 instrument master by name
    AND digest) and the CALENDAR READING with its governing source named -- the C5 duty. Without
    the master pin a replay cannot reproduce a POC; without the calendar reading it cannot
    reproduce which days existed.
    """
    _stores_or_skip()
    screener = _screener(tmp_path)
    screener.run_day()
    manifest = screener.recording.read_manifest()

    for key in ("trade_date", "mode", "spec_version", "code_sha", "config_digest",
                "master_file", "master_sha256", "row_size", "risk_per_trade_paise",
                "cost_paise", "factor_digest", "symbols", "calendar", "boundaries"):
        assert key in manifest, f"the replay contract is missing {key}"
    assert manifest["master_file"].startswith("OpenAPIScripMaster_")
    assert len(manifest["master_sha256"]) == 64
    assert manifest["spec_version"] == bt.SPEC_VERSION

    calendar = manifest["calendar"]
    assert calendar["governing_source"] == "published-nse-holiday-master", (
        "the C5 duty: LIVE takes non-standard sessions from the PUBLISHED calendar"
    )
    assert "non_standard_sessions_store_scan" in calendar, (
        "and the store scan stays, as the backtest cross-check"
    )
    assert calendar["is_standard_session"] is True

    inventory = screener.recording.inventory()
    assert inventory["symbols"] == 1
    assert inventory["candle_lines"] > 300, "seventeen polls of a 375-minute day"
    assert inventory["alerts"] == 3 and inventory["has_bias"] and inventory["has_manifest"]
    assert len(inventory["digest"]) == 64
