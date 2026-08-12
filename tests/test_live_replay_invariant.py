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
import json
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


def test_the_invariant_holds_on_a_sample_STRATIFIED_BY_BIAS_RULE(tmp_path: Path) -> None:
    """REVIEW_13 **B1**, and PART 3 item 1's second half, in the suite rather than in a script.

    *"Then re-run the replay invariant over a day sample that is STRATIFIED BY ``bias_rule``, so
    a carry day is in it by construction and not by luck."*

    The build session's three walk days were all rule-fired (rule-3, rule-1, rule-1). That is
    exactly why *"the invariant holds on 3 of 3 real symbol-days"* was true while the invariant
    was broken for **62,692 of 406,488 evaluated stock-days (15.42%) and 29,121 of 188,345
    executed trades (15.46%)** -- every one of them a day whose bias is CARRIED, which is the
    one stratum a series seeded at the trade day cannot reach.

    The sample is chosen and measured by ``docs/evidence/chunk13_fix2_bias_stratified.py``
    (committed with its output under CLAUDE.md's git rules) and re-run HERE, so a regression
    fails the suite rather than waiting for someone to re-run an evidence script. Only the
    CARRIED strata are re-run in the suite -- they are the property under test, and the rule-fired
    strata are what the named golden above already covers day by day.
    """
    _stores_or_skip()
    sample_path = Path(__file__).resolve().parents[1] / "docs" / "evidence" / (
        "chunk13_fix2_bias_stratified.json"
    )
    if not sample_path.is_file():
        pytest.skip("the stratified sample has not been generated on this machine")
    sample = json.loads(sample_path.read_text(encoding="utf-8"))

    carried = [row for row in sample["sample"] if row["carried"]]
    assert carried, "a stratified sample with no carried day proves nothing"
    assert any(
        row["symbol"] == "ITC" and row["day"] == "2026-06-10" for row in carried
    ), "REVIEW_13's own named witness for B1 is in the sample"

    config = load_config(include_env=False)
    store = MinuteStore.at(config.path("data_root") / "minute_store")
    checked = 0
    for row in carried:
        symbol, day = row["symbol"], date.fromisoformat(row["day"])
        if not store.minutes(symbol, day):
            continue
        screener = ls.build_live_screener(
            day, (symbol,), source=StoredDayBarSource(store),
            recording=LiveRecording.at(tmp_path / f"{symbol}-{day.isoformat()}"),
            clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
            mode="replay", sinks=(ls.CollectingAlertSink(),),
            # NO seed_from: what is under test is the DEFAULT, which is where B1 lived.
        )
        screener.run_day()
        state = screener.states[symbol]
        bias = screener.biases.get(symbol)
        want = row["expected"]
        assert bias is not None, f"{symbol} {day}: the carried bias is resolved at all"
        assert (bias.bias, bias.rule) == (want["bias"], want["bias_rule"]), (
            f"{symbol} {day}: the SHIPPED wiring reaches the ledger's own carried bias"
        )
        assert (
            None if state.poc_paise is None else str(state.poc_paise)
        ) == want["poc_paise"]
        for field in ("reference_paise", "entry_paise", "stop_paise", "target_paise",
                      "exit_kind"):
            assert getattr(state, field) == want[field], f"{symbol} {day}: {field}"
        if want["entry_paise"] is not None:
            assert state.qty == want["qty"], f"{symbol} {day}: qty"
        checked += 1
    assert checked >= 2, f"only {checked} carried day(s) were replayable from this lake"


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
    # REVIEW_13 M17/F2. The C5 duty is "chunk 13 takes non-standard sessions from the PUBLISHED
    # NSE calendar; the store scan stays the backtest cross-check" -- and this is a REPLAY,
    # which the store-derived calendar governs, exactly as it governs the backtester. The
    # manifest used to stamp "published-nse-holiday-master" on every recording ever written
    # (the parameter default) beside a `calendar_source_field` of "derived" in the same block:
    # the two halves of the pair contradicted each other, and the preflight printed the false
    # half. What is asserted now is that the recording names the calendar that ACTUALLY
    # governed, and the live half of the same rule is asserted in test_live_safety.py.
    assert calendar["governing_source"] == "daily-store-scan (backtest cross-check)", (
        "a REPLAY is governed by the store-derived calendar, and says so"
    )
    assert calendar["calendar_source_field"] == "derived", (
        "the claim and the reading agree, which is what M17 found they did not"
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


# --- CONTEXT 4.7 / Q-29: a recording replays under ITS OWN master --------------------------------


def _second_master_or_skip() -> tuple[str, str]:
    """A cached dump that is NOT the config pin, with its digest. Skips if the cache has one."""
    from acumen import backtest as bt
    from acumen.instrument_master import cached_masters

    config = load_config(include_env=False)
    others = [
        path for path in cached_masters(config.path("cache_root"))
        if path.name != config.instrument_master
    ]
    if not others:
        pytest.skip("the cache holds only the pinned master; this test needs a second dump")
    return others[-1].name, bt.file_sha256(others[-1])


def test_a_RECORDING_replays_under_the_master_IT_NAMES_not_under_the_config_pin(
    tmp_path: Path,
) -> None:
    """QUESTIONS.md Q-29, the architect's option (b), made structural.

    *"replay consumes the recording's own pin, so section 6 holds per day"*. This is the one
    property that makes a live day reproducible AT ALL once the pin moves: the vendor's tick is
    not stable between dumps -- Q-20 measured 11 of the sealed 210 disagreeing across two
    snapshots two days apart -- and the tick sizes the row grid, hence the POC, hence every entry,
    stop and target. A replay that silently took today's pin would answer a different question
    from the morning it claims to reproduce, and both answers would look like clean POCs.

    The recording here names the cache's OTHER dump. Nothing about the day changes; what must
    change is which file the pipeline was built from.
    """
    _stores_or_skip()
    other_name, other_sha = _second_master_or_skip()
    config = load_config(include_env=False)
    assert other_name != config.instrument_master

    recording = LiveRecording.at(tmp_path / "recorded-under-another-master")
    recording.open_session({
        "trade_date": GOLDEN_DAY.isoformat(),
        "mode": "live",
        "master_file": other_name,
        "master_sha256": other_sha,
    })

    # The resolution itself, asserted directly -- so this test fails on its OWN claim if the
    # rule is ever reverted, rather than on some downstream refusal (REVIEW_12_2 finding C5).
    chosen, why = ls._master_for("replay", day=GOLDEN_DAY, recording=recording)
    assert chosen == other_name
    assert "RECORDING'S OWN pin" in why, (
        "and the reason the operator reads is derived from the FILE, not from the mode "
        "(REVIEW_13 M9)"
    )
    live_master, live_why = ls._master_for("live", day=GOLDEN_DAY, recording=recording)
    assert live_master == ls.day_master_filename(GOLDEN_DAY), (
        "and a LIVE morning takes its OWN day's dump"
    )
    assert "THIS DAY'S OWN dump" in live_why

    # REVIEW_13 M9: `master_file` is FENCED. A live caller may name only the day's own dump --
    # the bypass that let a live session run on the Q-20 pin while the preflight printed "THIS
    # DAY'S OWN dump" is closed at the resolution rather than by convention.
    with pytest.raises(ls.ScreenerError, match="may run only on THE DAY'S OWN"):
        ls._master_for("live", day=GOLDEN_DAY, recording=recording, master_file=other_name)

    screener = ls.build_live_screener(
        GOLDEN_DAY, (GOLDEN_SYMBOL,),
        source=StoredDayBarSource(MinuteStore.at(config.path("data_root") / "minute_store")),
        recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(GOLDEN_DAY, datetime.min.time())),
        mode="replay",
        sinks=(ls.CollectingAlertSink(),),
    )

    manifest = screener.recording.read_manifest()
    assert manifest["master_file"] == other_name, "the recording's own pin, not the config's"
    assert manifest["master_sha256"] == other_sha
    # ...and the PIPELINE really was built from that file, which is the part that moves a POC
    from acumen.instrument_master import load_master_file

    home = config.path("cache_root") / "instrument_master"
    recorded_master = load_master_file(home / other_name)
    pinned_master = load_master_file(home / config.instrument_master)
    if len(recorded_master) == len(pinned_master):  # pragma: no cover -- cache-dependent
        pytest.skip(
            "the two cached dumps hold the same number of instruments, so this assertion "
            "could not tell them apart"
        )
    assert (
        screener.pipeline.master.instrument(GOLDEN_SYMBOL).tick_size_paise
        == recorded_master.instrument(GOLDEN_SYMBOL).tick_size_paise
    )
    assert len(screener.pipeline.master) == len(recorded_master) != len(pinned_master), (
        "the pipeline was built from the RECORDING's dump, and the two dumps are "
        "distinguishable -- which is what makes this assertion mean anything"
    )


def test_a_FRESH_replay_with_no_recording_still_takes_the_Q20_PIN(tmp_path: Path) -> None:
    """The other half of the same resolution, and the one that governs the historical ledger.

    With nothing recorded to inherit, a replay is a backtest of a past day and Q-20's pin is its
    law -- unchanged by CONTEXT 4.7, which says so in its own last clause.
    """
    _stores_or_skip()
    config = load_config(include_env=False)
    screener = _screener(tmp_path)
    assert screener.recording.read_manifest()["master_file"] == config.instrument_master


def test_the_BACKTEST_still_REFUSES_any_master_but_the_pin() -> None:
    """CONTEXT 4.7 opened ONE door and it is not this one.

    *"the Q-20 pin remains law for the historical ledger"*. ``build_runner``'s ``master_path``
    argument still confirms the pin and refuses anything else, and passing both doors at once is
    itself an error -- so a future caller cannot reach the live door by accident while believing
    it is confirming the pin.
    """
    from acumen import backtest as bt

    config = load_config(include_env=False)
    with pytest.raises(bt.BacktestError, match="is not the pinned instrument master"):
        bt.build_runner(
            (GOLDEN_SYMBOL,), GOLDEN_DAY, GOLDEN_DAY, seed_from=GOLDEN_DAY,
            master_path=Path("OpenAPIScripMaster_1999-01-01.json"),
        )
    with pytest.raises(bt.BacktestError, match="never both"):
        bt.build_runner(
            (GOLDEN_SYMBOL,), GOLDEN_DAY, GOLDEN_DAY, seed_from=GOLDEN_DAY,
            master_path=Path(config.instrument_master),
            master_file=config.instrument_master,
        )
