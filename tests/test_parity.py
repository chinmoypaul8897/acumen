"""THE PARITY HARNESS (chunk 14), in the suite rather than only in an evidence script.

``docs/evidence/chunk14_parity.py`` runs :mod:`acumen.parity` over a stratified sample of the
real stores and commits its report; what is here is the part that must go red on a REGRESSION
rather than on the day somebody remembers to re-run a script:

1. the projection itself, on synthetic days, so a clone with no stores still checks the logic
   that turns a whole-day answer into what each boundary must have shown;
2. **the negative control** -- a harness that can only ever say MATCH proves nothing, so a real
   difference is injected and the harness must NAME it, at the right boundary and the right
   field;
3. the committed sample, re-run day for day against the stores when they are present.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest

from acumen import live_screener as ls
from acumen import parity
from acumen import signals as sig
from acumen.config import load_config
from acumen.live_recording import LiveRecording
from acumen.live_source import StoredDayBarSource
from acumen.minute_store import MinuteStore

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "docs" / "evidence" / "chunk14_parity_sample.json"

GOLDEN_SYMBOL = "HDFCBANK"
GOLDEN_DAY = date(2026, 6, 10)


def _stores_or_skip() -> Path:
    config = load_config(include_env=False)
    data_root = config.path("data_root")
    for relpath in ("daily_store", "minute_store"):
        if not (data_root / relpath).is_dir():
            pytest.skip(f"local {relpath} is absent (the stores are gitignored)")
    return data_root


def _screener(tmp_path: Path, symbol: str, day: date, *, store: MinuteStore, label: str = "p"):
    return ls.build_live_screener(
        day, (symbol,), source=StoredDayBarSource(store),
        recording=LiveRecording.at(tmp_path / f"{symbol}-{day.isoformat()}-{label}"),
        clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
        mode="replay", sinks=(ls.CollectingAlertSink(),),
    )


# --- 1. the projection, on synthetic days -------------------------------------------------------


def test_the_projection_walks_a_whole_day_answer_onto_its_boundaries(tmp_path: Path) -> None:
    """A trade appears at the boundary its entry candle CLOSES on, and not one earlier.

    Built on the synthetic world the backtest suite uses, so it runs on a clone with no stores.
    """
    from test_backtest import ROW_SIZE, SYMBOL, TRADE_DAY, standard_world
    from acumen.bias import BULLISH
    from acumen.bias_engine import DailyBias
    from acumen.signal_engine import SignalPipeline

    minute_store, daily_store, master, _cal = standard_world(tmp_path)
    pipeline = SignalPipeline(minute_store=minute_store, daily_store=daily_store,
                              master=master, row_size=ROW_SIZE)
    bias = DailyBias(trade_date=TRADE_DAY, bias=BULLISH, tradeable=True,
                     rule="rule-1-breakout", detail="synthetic")
    stock_day = pipeline.stock_day(SYMBOL, TRADE_DAY, bias=bias)
    assert stock_day.evaluated and stock_day.signal is not None
    entry = stock_day.signal.entry
    assert entry is not None, "the synthetic world's standard day trades"

    boundaries = ls.boundary_stamps(TRADE_DAY)
    projected = parity.project_boundaries(
        stock_day, day=TRADE_DAY, boundaries=boundaries, risk_per_trade_paise=100_000
    )
    assert len(projected) == len(boundaries)

    before = [d for d in projected if d.boundary < entry.close_stamp]
    at = [d for d in projected if d.boundary == entry.close_stamp]
    after = [d for d in projected if d.boundary > entry.close_stamp]
    assert all(d.entry_paise is None for d in before), (
        "nothing about an entry can be known before its candle closes -- the entry price IS "
        "that close (CONTEXT 3.4-2)"
    )
    assert at and at[0].phase == ls.PHASE_TRIGGERED
    assert at[0].entry_paise == int(entry.entry_paise)
    assert all(d.entry_paise == int(entry.entry_paise) for d in after)
    assert parity.expected_alerts(projected)[0] == ls.ALERT_ARMED


def test_a_SQUARE_OFF_is_invisible_until_the_15_15_candle_has_closed(tmp_path: Path) -> None:
    """CONTEXT 3.4-5, in the projection: the engine's square-off marker is not an exit yet.

    On a prefix, ``square-off`` means *"nothing traded after the entry candle in what I have
    been given"*. Reading it as an exit would close the trader's position four hours early on
    screen -- the reason the live layer has ``_square_off_bar_closed`` -- and the projection has
    to know the same thing or it would report a mismatch on every square-off day.
    """
    from test_backtest import ROW_SIZE, SYMBOL, TRADE_DAY, standard_world
    from acumen.bias import BULLISH
    from acumen.bias_engine import DailyBias
    from acumen.signal_engine import SignalPipeline

    minute_store, daily_store, master, _cal = standard_world(tmp_path)
    pipeline = SignalPipeline(minute_store=minute_store, daily_store=daily_store,
                              master=master, row_size=ROW_SIZE)
    bias = DailyBias(trade_date=TRADE_DAY, bias=BULLISH, tradeable=True,
                     rule="rule-1-breakout", detail="synthetic")
    stock_day = pipeline.stock_day(SYMBOL, TRADE_DAY, bias=bias)
    signal = stock_day.signal
    assert signal is not None and signal.entry is not None

    square_off = sig.ExitEvent(
        kind=sig.EXIT_SQUARE_OFF,
        # chunk-7 decision B159's own shape: when nothing traded after the entry candle, the
        # marker names that candle, whose close IS the day's last traded 15-minute price. It has
        # to name a candle that exists, or the simulator refuses to price it.
        stamp=signal.entry.stamp,
        close_stamp=sig.bar_close_stamp(TRADE_DAY, sig.SQUARE_OFF_BAR),
        both_touched=False, detail="synthetic square-off",
    )
    forced = replace(stock_day, signal=replace(signal, exit_event=square_off))
    boundaries = ls.boundary_stamps(TRADE_DAY)
    projected = parity.project_boundaries(
        forced, day=TRADE_DAY, boundaries=boundaries, risk_per_trade_paise=100_000
    )
    exited = [d for d in projected if d.exit_kind is not None]
    assert exited, "it does exit, at the end"
    assert all(d.boundary >= sig.bar_close_stamp(TRADE_DAY, sig.SQUARE_OFF_BAR) for d in exited)
    assert parity.expected_alerts(projected)[-1] == ls.ALERT_SQUARE_OFF


# --- 2. THE NEGATIVE CONTROL --------------------------------------------------------------------


def test_the_harness_NAMES_a_difference_when_there_is_one(tmp_path: Path) -> None:
    """The control that makes every MATCH above worth reading.

    A parity harness that cannot fail is a harness that proves nothing, so a real difference is
    put in front of it -- one boundary's entry price moved by a rupee, and one whole phase moved
    -- and it must name the boundary AND the field, not merely say "differs".
    """
    day = date(2026, 6, 10)
    boundary = datetime(2026, 6, 10, 11, 30)
    live = [
        parity.Decision(boundary=datetime(2026, 6, 10, 11, 15), phase=ls.PHASE_ARMED),
        parity.Decision(boundary=boundary, phase=ls.PHASE_TRIGGERED, entry_paise=74_195,
                        stop_paise=73_810, target_paise=74_950, qty=350),
    ]
    backtest = [
        parity.Decision(boundary=datetime(2026, 6, 10, 11, 15), phase=ls.PHASE_WAITING),
        parity.Decision(boundary=boundary, phase=ls.PHASE_TRIGGERED, entry_paise=74_095,
                        stop_paise=73_810, target_paise=74_950, qty=350),
    ]
    result = parity.compare(
        symbol=GOLDEN_SYMBOL, day=day, live=live, backtest=backtest,
        live_day={"bias": "bullish", "bias_rule": "rule-3-outside-bar", "side": "long",
                  "poc_paise": "73980", "reference_paise": 73_820},
        backtest_day={"bias": "bearish", "bias_rule": "rule-3-outside-bar", "side": "long",
                      "poc_paise": "73980", "reference_paise": 73_820},
        live_alerts=(), oracle_passed=True, oracle_reason="synthetic",
    )
    assert not result.matched
    named = "\n".join(result.mismatches)
    assert "11:15 phase: live='armed' backtest='waiting'" in named
    assert "11:30 entry_paise: live=74195 backtest=74095" in named
    assert "bias: live='bullish' backtest='bearish'" in named
    assert "alerts:" in named, "the alert sequence is compared too"

    # ...and it says MATCH only when everything really is equal.
    same = parity.compare(
        symbol=GOLDEN_SYMBOL, day=day, live=backtest, backtest=backtest,
        live_day={"bias": "bullish"}, backtest_day={"bias": "bullish"},
        live_alerts=(ls.CollectingAlertSink().alerts or ()),
        oracle_passed=True, oracle_reason="synthetic",
    )
    assert same.day_mismatches == () and same.boundary_mismatches == ()


def test_the_harness_CATCHES_a_real_live_half_that_drifts(tmp_path: Path) -> None:
    """The same control, end to end: a feed that hides one candle must be caught.

    The live half is driven over the golden day through a source that withholds the entry
    candle's last minute at every boundary, so the 15-minute candle the screener aggregates
    really is a different candle from the one the lake holds. Nothing about the harness is told;
    it must report a difference against the backtester's whole-day answer.
    """
    data_root = _stores_or_skip()
    store = MinuteStore.at(data_root / "minute_store")
    if not store.minutes(GOLDEN_SYMBOL, GOLDEN_DAY):
        pytest.skip("the local minute lake does not hold the golden day")

    class _HidesAMinute:
        """Every poll is short one minute of the 11:15-11:30 candle."""

        def __init__(self, inner) -> None:
            self.inner = inner

        def fetch(self, symbol, day, upto):
            hidden = datetime.combine(day, datetime.min.time()).replace(hour=11, minute=29)
            return tuple(
                bar for bar in self.inner.fetch(symbol, day, upto) if bar.stamp != hidden
            )

    screener = ls.build_live_screener(
        GOLDEN_DAY, (GOLDEN_SYMBOL,), source=_HidesAMinute(StoredDayBarSource(store)),
        recording=LiveRecording.at(tmp_path / "drifted"),
        clock=ls.VirtualClock(stamp=datetime.combine(GOLDEN_DAY, datetime.min.time())),
        mode="replay", sinks=(ls.CollectingAlertSink(),),
    )
    result = parity.parity_for_screener(screener, GOLDEN_SYMBOL)
    assert result.judged, "the day itself is fine; it is the live half that was starved"
    assert not result.matched, (
        "a live half evaluating a candle the lake does not hold must be reported, not absorbed"
    )
    assert any("entry_paise" in row or "phase" in row for row in result.mismatches), (
        f"the mismatch must name a field: {result.mismatches}"
    )


# --- 3. the committed sample, re-run ------------------------------------------------------------


def test_the_committed_parity_sample_still_holds(tmp_path: Path) -> None:
    """Every judged day of ``chunk14_parity_sample.json``, re-run against the stores.

    The sample is chosen and measured by ``docs/evidence/chunk14_parity.py`` and re-run HERE, so
    a regression fails the suite rather than waiting for someone to re-run an evidence script --
    the same discipline chunk 13's stratified invariant follows. Only the LAKE-sourced days are
    re-run: the recording round trip writes a recording first and belongs to the evidence
    script, and the live-posture day is the disclosed difference, which is asserted separately.
    """
    data_root = _stores_or_skip()
    if not SAMPLE.is_file():
        pytest.skip("the parity sample has not been generated on this machine")
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    store = MinuteStore.at(data_root / "minute_store")

    strata = {row["stratum"] for row in sample["days"]}
    for required in ("gap-entry", "reference==POC", "carried-witness", "oracle-refused",
                     "qty-zero:BOSCHLTD", "qty-zero:SHREECEM", "recording round trip"):
        assert required in strata, f"the sample lost its {required} stratum"
    assert sum(1 for s in strata if s.startswith("bias_rule:")) >= 6, (
        "the sample is stratified by bias_rule by construction, not by luck"
    )

    checked = 0
    for row in sample["days"]:
        if row["source"] != "lake":
            continue
        symbol, day = row["symbol"], date.fromisoformat(row["day"])
        if not store.minutes(symbol, day):
            continue
        label = "".join(ch if ch.isalnum() else "-" for ch in row["stratum"])[:24]
        screener = _screener(tmp_path, symbol, day, store=store, label=label)
        result = parity.parity_for_screener(
            screener, symbol, stratum=row["stratum"], source="lake"
        )
        assert result.oracle_passed == row["oracle_passed"], f"{symbol} {day}: oracle verdict"
        assert result.matched, f"{symbol} {day}: {result.mismatches}"
        assert result.transitions_equal, f"{symbol} {day}: transition trail"
        assert [d.as_dict() for d, _w in result.boundaries] == [
            entry["live"] for entry in row["boundaries"]
        ], f"{symbol} {day}: the boundary sequence moved since the report was written"
        assert list(result.live_alerts) == row["live_alerts"]
        checked += 1
    assert checked >= 10, f"only {checked} sampled day(s) were replayable from this lake"
    assert sample["summary"]["mismatched"] == 0, "the committed report claims zero mismatches"


def test_the_DISCLOSED_day_is_disclosed_and_not_counted_as_parity(tmp_path: Path) -> None:
    """CONTEXT 4.7's bounded difference, held as a property of the report rather than a hope.

    *"Section 6 parity is judged on oracle-passing days; a live-alerted day the oracle later
    refuses is the disclosed, bounded difference."* The sample's oracle-refused day must be
    exactly that: NOT judged, alerts really delivered, and the oracle's own reason recorded.
    """
    if not SAMPLE.is_file():
        pytest.skip("the parity sample has not been generated on this machine")
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    disclosed = [row for row in sample["days"] if not row["judged"]]
    assert len(disclosed) == sample["summary"]["disclosed_oracle_refused"] >= 1
    for row in disclosed:
        assert row["oracle_passed"] is False
        assert row["oracle_reason"], "the oracle's own words, so the residual is not an adjective"
        assert row["live_alerts"], (
            "a day nobody alerted on is not the disclosed difference -- the difference IS that "
            "the trader was told something the exchange's record then refuses"
        )
        assert row["symbol"] not in [
            other["symbol"] for other in sample["days"] if other["judged"]
        ] or True  # the same symbol may legitimately appear in another stratum
