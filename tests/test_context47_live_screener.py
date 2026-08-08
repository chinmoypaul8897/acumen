"""CONTEXT 4.7 at the SCREENER level: the live posture, the disclosure, the per-sweep battery.

``tests/test_context47_oracle_free_battery.py`` attacks the battery itself. This file attacks
what the live screener does with it, on the synthetic day whose every figure
``tests/test_live_screener.py`` already pins -- POC 200005, entry 200100, stop 199900, target
200700, qty 500 -- so a number that moves here is a number that moved because of the ruling.

The three claims:

1. a live morning reaches the SAME numbers a settled replay reaches (the ruling changed the
   validity test, not the strategy -- CLAUDE.md rule 2);
2. every live alert carries the disclosed line, and a replay carries none;
3. the battery is recomputed PER SWEEP under the live posture and handed out ONCE under the
   settled one -- which is what lets a corrupt bar refuse the day the moment it arrives.

ASCII-only, like every other source file in this repo (chunk-0 B7).
"""

from __future__ import annotations

from datetime import datetime
from fractions import Fraction
from pathlib import Path

from acumen import live_screener as ls
from acumen.live_source import FlakyBarSource, StoredDayBarSource
from acumen.minute_store import StoredBar
from acumen.signal_engine import SignalPipeline

from test_backtest import ROW_SIZE, SYMBOL, TRADE_DAY, standard_world
from test_live_screener import ENTRY, R_POC, STOP, TARGET, make_screener


def _bullish():
    from acumen.bias import BULLISH
    from acumen.bias_engine import DailyBias

    return DailyBias(
        trade_date=TRADE_DAY, bias=BULLISH, tradeable=True,
        rule="rule-1-breakout", detail="synthetic bullish day",
    )


# --- 1. the numbers do not move -----------------------------------------------------------------


def test_a_LIVE_morning_reaches_the_SAME_numbers_the_backtester_does(tmp_path: Path) -> None:
    """The point of the whole ruling, on the day this suite already knows every figure of.

    Under CONTEXT 4.7 a live morning runs the oracle-free battery and nothing else about the
    engine changes -- so the POC, the arming, the entry, the stop, the target and the quantity
    land on the SAME numbers the settled replay lands on. If a single one moved, the ruling would
    have changed the strategy rather than the validity test, which is the one thing it is not
    allowed to do.
    """
    settled, _s_sink, _s_rec = make_screener(tmp_path / "settled")
    live, live_sink, _l_rec = make_screener(tmp_path / "live", live=True)
    settled.run_day()
    live.run_day()

    here, there = settled.states[SYMBOL], live.states[SYMBOL]
    assert here.poc_paise == there.poc_paise == Fraction(R_POC)
    for state in (here, there):
        assert (state.entry_paise, state.stop_paise, state.target_paise, state.qty) == (
            ENTRY, STOP, TARGET, 500
        )
    assert here.phase == there.phase == ls.PHASE_EXITED
    assert [alert.kind for alert in live_sink.alerts] == [
        ls.ALERT_ARMED, ls.ALERT_TRIGGER, ls.ALERT_EXIT
    ]


# --- 2. the disclosed line ----------------------------------------------------------------------


def test_EVERY_LIVE_ALERT_carries_the_disclosed_line(tmp_path: Path) -> None:
    """CONTEXT 4.7, verbatim: *"Every live alert carries: 'live feed, not yet verified ...'"*

    On the alert OBJECT and in its rendered line, because an alert is forwarded, screenshotted
    and quoted -- the sentence has to travel with it rather than stay on the screen it was read
    from. Asserted over every alert of the morning, not over a sample.
    """
    screener, sink, recording = make_screener(tmp_path, live=True)
    screener.run_day()

    assert sink.alerts, "the live morning really did alert"
    for alert in sink.alerts:
        assert alert.payload["disclosure"] == ls.LIVE_DISCLOSURE
        line = ls.format_alert(alert)
        assert ls.LIVE_DISCLOSURE in line
        assert line.index(ls.LIVE_DISCLOSURE) > 20, (
            "after the numbers he trades on at 11:30, never in front of them"
        )
    recorded = recording.alerts()
    assert recorded and all(
        row["payload"]["disclosure"] == ls.LIVE_DISCLOSURE for row in recorded
    ), "and it survives into the recording, which is what chunk 14 and his own log read"


def test_a_REPLAYED_day_carries_NO_disclosure_because_its_bhavcopy_exists(
    tmp_path: Path,
) -> None:
    """The other direction, which a careless edit would get wrong.

    A sentence that appears on every alert ever produced is a sentence nobody reads on the
    morning that needs it. A replayed day HAS been verified against the exchange's record -- the
    settled battery is the backtester's own verdict on it -- so the line would simply be false.
    """
    screener, sink, _rec = make_screener(tmp_path)
    screener.run_day()
    assert sink.alerts
    for alert in sink.alerts:
        assert "disclosure" not in alert.payload
        assert ls.LIVE_DISCLOSURE not in ls.format_alert(alert)


def test_the_FAILURE_BANNER_alert_carries_it_too(tmp_path: Path) -> None:
    """The banner is an alert like any other, and it is the one most likely to be forwarded.

    "Those stocks are NOT being watched" plus an unverified feed is a different sentence from
    "those stocks are NOT being watched" alone, and he is entitled to both facts at once.
    """
    screener, sink, _rec = make_screener(tmp_path, live=True)
    screener.source = FlakyBarSource(
        inner=screener.source, fail_symbols=frozenset({SYMBOL}), fail_times=99
    )
    screener.sweep(datetime.combine(TRADE_DAY, datetime.min.time()).replace(hour=11, minute=15))

    failures = [alert for alert in sink.alerts if alert.kind == ls.ALERT_FAILURE]
    assert failures, "the sweep really did fail"
    assert failures[0].payload["disclosure"] == ls.LIVE_DISCLOSURE
    assert "NOT being watched" in failures[0].payload["detail"]


# --- 3. per sweep, and what that buys ------------------------------------------------------------


def test_the_LIVE_battery_is_recomputed_PER_SWEEP_and_the_settled_one_is_not(
    tmp_path: Path,
) -> None:
    """CONTEXT 4.7's *"per sweep"*, and CONTEXT 4.6's *"once"*, both asserted at the seam.

    The asymmetry is not a preference. Gate 1 is a whole-day fold against a whole-day total, so
    recomputing it on a growing prefix is WRONG at every boundary but the last; every trigger
    left in the oracle-free battery is a property of the bars in hand, so recomputing it per
    sweep is the only reading that can see a corrupt bar the moment it arrives.
    """
    live, _sink, _rec = make_screener(tmp_path / "live", live=True)
    assert live.gates == {}, "a live morning has no settled battery to hand out"

    seen: list[int] = []
    real = ls.oracle_free_battery

    def counting(day, minutes):
        seen.append(len(minutes))
        return real(day, minutes)

    ls.oracle_free_battery = counting
    try:
        live.run_day()
    finally:
        ls.oracle_free_battery = real

    assert len(seen) >= 17, "one battery per sweep, not one for the day"
    assert seen == sorted(seen), "and each one sees at least as many bars as the last"
    assert seen[0] < seen[-1]

    settled, _s, _r = make_screener(tmp_path / "settled")
    assert set(settled.gates) == {SYMBOL}
    assert settled._battery(SYMBOL, ()) is settled.gates[SYMBOL], (
        "the settled posture hands out the SAME object at every boundary"
    )


def test_a_CORRUPT_BAR_refuses_the_LIVE_day_and_produces_no_signal(tmp_path: Path) -> None:
    """Why "per sweep" is a safety property and not only an arithmetic one.

    The Q-21(a) open test is inside the live battery, and a live morning is the one place where
    nothing downstream would catch a corrupt bar -- there is no end-of-day battery in front of
    the trader at 11:30. So the day is refused, the screener degrades to silence with a stated
    reason, and no POC is built on a bar that cannot exist.
    """
    minute_store, daily_store, master, _cal = standard_world(tmp_path)
    pipeline = SignalPipeline(
        minute_store=minute_store, daily_store=daily_store, master=master, row_size=ROW_SIZE
    )
    good = minute_store.minutes(SYMBOL, TRADE_DAY)
    poisoned = tuple(
        candle if index != 5 else StoredBar(
            symbol=candle.symbol, stamp=candle.stamp,
            open_paise=candle.high_paise + 5_000,  # an open ABOVE the high: impossible
            high_paise=candle.high_paise, low_paise=candle.low_paise,
            close_paise=candle.close_paise, volume=candle.volume,
        )
        for index, candle in enumerate(good)
    )

    clean = pipeline.evaluate(
        SYMBOL, TRADE_DAY, bias=_bullish(), minutes=good,
        gates=ls.oracle_free_battery(TRADE_DAY, good),
    )
    assert clean.evaluated and clean.profile.poc_paise == Fraction(R_POC)

    refused = pipeline.evaluate(
        SYMBOL, TRADE_DAY, bias=_bullish(), minutes=poisoned,
        gates=ls.oracle_free_battery(TRADE_DAY, poisoned),
    )
    assert not refused.evaluated
    assert refused.reason == "gate 2 (candle integrity)"
    assert refused.signal is None and refused.profile is None


def test_the_live_screener_still_goes_through_the_ONE_ENGINE(tmp_path: Path) -> None:
    """The chunk's own law, re-asserted against the new branch.

    ``_battery`` is a new fork in the live layer and a fork is where a second implementation
    grows. The source-level guard in ``tests/test_live_replay_invariant.py`` forbids the live
    layer from calling the engines directly; what is checked here is the consequence -- the live
    posture's answer is the SAME object ``pipeline.evaluate`` produces for the same bars and the
    same battery.
    """
    screener, _sink, _rec = make_screener(tmp_path, live=True)
    screener.run_day()
    bars = screener.bars[SYMBOL]

    independent = screener.pipeline.evaluate(
        SYMBOL, TRADE_DAY, bias=screener.biases[SYMBOL], minutes=bars,
        gates=ls.oracle_free_battery(TRADE_DAY, bars),
    )
    through_the_screener = screener.pipeline.evaluate(
        SYMBOL, TRADE_DAY, bias=screener.biases[SYMBOL], minutes=bars,
        gates=screener._battery(SYMBOL, bars),
    )
    assert independent == through_the_screener
    assert independent.evaluated and independent.signal is not None


def test_the_bars_a_LIVE_morning_collected_are_the_bars_it_recorded(tmp_path: Path) -> None:
    """The replay contract holds under the live posture too, which is what makes 4.7's next
    pre-open possible at all: the verification re-gates the RECORDING, so the recording has to
    be the morning's own bytes.
    """
    screener, _sink, recording = make_screener(tmp_path, live=True)
    screener.run_day()
    assert screener.bars[SYMBOL] == recording.bars(SYMBOL, TRADE_DAY)
    assert recording.revisions(SYMBOL) == ()
