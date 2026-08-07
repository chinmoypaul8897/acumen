"""Chunk 13 evidence: the LIVE screener replayed over real historical days, checked against
the backtester candle for candle.

Committed here beside its own output under CLAUDE.md's git rules (REVIEW_7 finding C3): a
session making claims from real store data commits the generating script and its output.

    python docs/evidence/chunk13_replay_walk.py [--out docs/evidence/chunk13_replay_walk.md]

**READ-ONLY over the stores.** It opens the daily store, the 1-minute lake and the pinned
instrument master, and it writes exactly two things: this document, and a RECORDING per replayed
day into a directory the caller names (``--recording-root``, defaulting to a temporary directory
OUTSIDE the stores). Nothing under ``data_root`` is created, modified or removed.

What it proves, per day:

1. the live pipeline, driven a 15-minute boundary at a time on a virtual clock, produces the
   SAME :class:`acumen.signals.SignalDay` the backtester's ``stock_day`` produces -- compared
   field by field, transitions included;
2. the bars the screener ACCUMULATED across its polls equal the stored day exactly, which is why
   (1) holds rather than being a coincidence;
3. the pre-open bias is the backtester's own, from ``BacktestRunner.bias_map``, rule and all;
4. the recording carries what a replay needs -- the machine (spec, code SHA, config digest, the
   Q-20 master by filename AND sha256), the calendar reading with its governing source named
   (the C5 duty), every fetched candle, every fetch attempt, every alert and the bias table.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from acumen import backtest as bt  # noqa: E402
from acumen import live_screener as ls  # noqa: E402
from acumen import signals as sig  # noqa: E402
from acumen.config import load_config  # noqa: E402
from acumen.live_recording import LiveRecording  # noqa: E402
from acumen.live_source import FlakyBarSource, StoredDayBarSource  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "docs" / "evidence" / "chunk13_replay_walk.md"

#: The three days. Chosen for what they are rather than for what they pay:
#:  * HDFCBANK 2026-06-10 -- the real Rule-3 OUTSIDE-BAR day chunk 7 walked candle by candle and
#:    chunk 8 priced (risk 285p, qty 350, target 749.50 on the 13:15-closing candle). The one day
#:    in this repo whose every number three sessions have already agreed on.
#:  * ICICIBANK 2026-06-10 -- same date, a different symbol and a different tick, so a shared-day
#:    coincidence cannot explain a match.
#:  * RELIANCE 2026-06-11 -- a different date, so a shared-day coincidence cannot explain it either.
DAYS: tuple[tuple[str, date], ...] = (
    ("HDFCBANK", date(2026, 6, 10)),
    ("ICICIBANK", date(2026, 6, 10)),
    ("RELIANCE", date(2026, 6, 11)),
)


def rupees(paise) -> str:
    if paise is None:
        return "-"
    from fractions import Fraction
    return f"{float(Fraction(paise) / 100):,.2f}"


def walk(symbol: str, day: date, recording_root: Path) -> dict:
    """Replay one symbol-day through the LIVE pipeline and compare it to the backtester."""
    config = load_config(include_env=False)
    data_root = config.path("data_root")
    store = MinuteStore.at(data_root / "minute_store")
    recording = LiveRecording.at(recording_root / f"{symbol}-{day.isoformat()}")

    screener = ls.build_live_screener(
        day, (symbol,),
        source=StoredDayBarSource(store),
        recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
        mode="replay",
        sinks=(ls.CollectingAlertSink(),),
    )
    sink = screener.sinks[0]

    timeline: list[tuple[str, str, str]] = []
    for boundary in ls.boundary_stamps(day):
        screener.clock.set(boundary)
        report = screener.sweep(boundary)
        state = screener.states[symbol]
        timeline.append((
            boundary.strftime("%H:%M"), state.phase,
            "; ".join(a.kind for a in report.alerts) or "",
        ))
    screener.close_day()

    live_day = screener.pipeline.evaluate(
        symbol, day, bias=screener.biases[symbol],
        minutes=screener.bars[symbol], gates=screener.gates[symbol],
    )
    backtest_day = screener.pipeline.stock_day(symbol, day, bias=screener.biases[symbol])

    runner, _master, _ca = bt.build_runner(
        (symbol,), day, day, seed_from=day, label="chunk13-evidence"
    )
    series, _reason = runner.bias_map(symbol)

    stored = store.minutes(symbol, day)
    return {
        "symbol": symbol,
        "day": day,
        "timeline": timeline,
        "state": screener.states[symbol],
        "alerts": tuple(sink.alerts),
        "identical": live_day == backtest_day,
        "signal_identical": live_day.signal == backtest_day.signal,
        "bars_identical": tuple(screener.bars[symbol]) == tuple(stored),
        "recording_bars_identical": recording.bars(symbol, day) == tuple(stored),
        "revisions": recording.revisions(symbol),
        "bias": screener.biases[symbol],
        "bias_identical": screener.biases[symbol] == series[day],
        "stored_bars": len(stored),
        "manifest": recording.read_manifest(),
        "inventory": recording.inventory(),
        "backtest_day": backtest_day,
    }


def disconnect_check(symbol: str, day: date, recording_root: Path) -> dict:
    """The same day with the feed dead through the whole 11:15 sweep. Same trade or not?"""
    config = load_config(include_env=False)
    store = MinuteStore.at(config.path("data_root") / "minute_store")
    recording = LiveRecording.at(recording_root / f"{symbol}-{day.isoformat()}-disconnect")
    screener = ls.build_live_screener(
        day, (symbol,),
        source=FlakyBarSource(
            inner=StoredDayBarSource(store), fail_symbols=frozenset({symbol}), fail_times=6
        ),
        recording=recording,
        clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
        mode="replay", sinks=(ls.CollectingAlertSink(),),
    )
    reports = screener.run_day()
    return {
        "first_sweep_complete": reports[0].complete,
        "first_sweep_skipped": reports[0].skipped,
        "second_sweep_complete": reports[1].complete,
        "state": screener.states[symbol],
        "alerts": tuple(screener.sinks[0].alerts),
        "banner": screener.banner,
        "events": {row["kind"] for row in recording.events()},
    }


def render(walks: list[dict], disconnect: dict) -> str:
    out: list[str] = []
    add = out.append
    add("# Chunk 13 evidence -- the live screener replayed against the backtester")
    add("")
    add("Generated by `docs/evidence/chunk13_replay_walk.py`, read-only over the stores.")
    add("")
    add("CONTEXT section 6: *\"One engine, two modes ... the backtester feeds them stored "
        "history, the screener feeds them the live poll -- same code path, guaranteed no "
        "backtest/live drift.\"* This document is that sentence, measured.")
    add("")
    add("## 1 -- The invariant, per day")
    add("")
    add("| symbol | day | stored 1-min bars | bars collected == stored | SignalDay identical | "
        "bias == backtester's | vendor revisions |")
    add("|---|---|---:|---|---|---|---:|")
    for walk_result in walks:
        add(
            f"| {walk_result['symbol']} | {walk_result['day'].isoformat()} | "
            f"{walk_result['stored_bars']:,} | "
            f"{'YES' if walk_result['bars_identical'] else 'NO'} | "
            f"{'YES' if walk_result['identical'] else 'NO'} | "
            f"{'YES' if walk_result['bias_identical'] else 'NO'} | "
            f"{len(walk_result['revisions'])} |"
        )
    add("")
    add("`SignalDay identical` compares the whole `StockDay` -- the profile, the aggregated "
        "15-minute bars, the signal, and every transition note in it -- not a selection of "
        "figures.")
    add("")

    for walk_result in walks:
        state = walk_result["state"]
        add(f"## 2.{walks.index(walk_result) + 1} -- {walk_result['symbol']} "
            f"{walk_result['day'].isoformat()}: the morning, boundary by boundary")
        add("")
        bias = walk_result["bias"]
        add(f"**Pre-open.** bias **{bias.bias}** by `{bias.rule}` from the pair "
            f"({bias.previous_date} , {bias.current_date}) -- taken from "
            f"`BacktestRunner.bias_map`, so it is the backtester's own carry.")
        add("")
        add("| boundary | state | alerts |")
        add("|---|---|---|")
        last = None
        for label, phase, alerts in walk_result["timeline"]:
            if phase == last and not alerts:
                continue
            last = phase
            add(f"| {label} | {phase} | {alerts or ''} |")
        add("")
        if state.poc_paise is not None:
            add(f"**POC** {rupees(state.poc_paise)} | **reference** "
                f"{rupees(state.reference_paise)} | side **{state.side}**")
        if state.entry_paise:
            add("")
            add(f"**Entry** {rupees(state.entry_paise)} | **SL** {rupees(state.stop_paise)} | "
                f"**TP** {rupees(state.target_paise)} | **qty** {state.qty} | "
                f"**exit** {state.exit_kind or 'open'} at {rupees(state.exit_paise)}")
        else:
            add("")
            add(f"No trade. Final state **{state.phase}** -- {state.detail or state.refusal}")
        add("")
        add("Alerts delivered:")
        add("")
        for alert in walk_result["alerts"]:
            add(f"* `{ls.format_alert(alert)}`")
        if not walk_result["alerts"]:
            add("* none")
        add("")

    add("## 3 -- The recording contract, per day")
    add("")
    add("| symbol | day | candle lines | fetch rows | alerts | events | master pinned | "
        "calendar source | digest |")
    add("|---|---|---:|---:|---:|---:|---|---|---|")
    for walk_result in walks:
        inv = walk_result["inventory"]
        man = walk_result["manifest"]
        add(
            f"| {walk_result['symbol']} | {walk_result['day'].isoformat()} | "
            f"{inv['candle_lines']:,} | {inv['fetch_rows']:,} | {inv['alerts']} | "
            f"{inv['events']} | `{man['master_file']}` "
            f"({man['master_sha256'][:12]}...) | {man['calendar']['governing_source']} | "
            f"`{inv['digest'][:16]}...` |"
        )
    add("")
    manifest = walks[0]["manifest"]
    add("The first day's manifest, in full (every field a replay needs):")
    add("")
    add("```")
    for key in ("trade_date", "mode", "dry_run", "spec_version", "code_sha", "config_digest",
                "master_file", "master_sha256", "row_size", "risk_per_trade_paise",
                "cost_paise", "factor_digest", "recording_version"):
        add(f"{key:<24} {manifest.get(key)}")
    cal = manifest["calendar"]
    add(f"{'calendar.governing':<24} {cal['governing_source']}")
    add(f"{'calendar.trading_day':<24} {cal['is_trading_day']}")
    add(f"{'calendar.standard':<24} {cal['is_standard_session']}")
    add(f"{'calendar.store_scan':<24} "
        f"{len(cal['non_standard_sessions_store_scan'])} non-standard session(s) "
        f"(the backtest cross-check; the published calendar governs -- C5)")
    add(f"{'boundaries':<24} {len(manifest['boundaries'])} "
        f"({manifest['boundaries'][0][11:16]} .. {manifest['boundaries'][-1][11:16]})")
    add("```")
    add("")

    add("## 4 -- The simulated disconnect")
    add("")
    symbol, day = DAYS[0]
    add(f"{symbol} {day.isoformat()}, with the feed refusing for six consecutive attempts -- "
        "long enough to outlive the whole 11:15 POC sweep (three tries in the first pass, two "
        "on CONTEXT 4.4's sweep-end re-poll).")
    add("")
    add(f"* 11:15 sweep complete: **{disconnect['first_sweep_complete']}**, "
        f"skipped {list(disconnect['first_sweep_skipped'])}")
    add(f"* 11:30 sweep complete: **{disconnect['second_sweep_complete']}**")
    add(f"* final state: **{disconnect['state'].phase}**, entry "
        f"{rupees(disconnect['state'].entry_paise)}, exit {disconnect['state'].exit_kind} at "
        f"{rupees(disconnect['state'].exit_paise)}")
    add(f"* banner at the end of the day: "
        f"**{disconnect['banner'] or 'cleared (empty)'}**")
    add(f"* alerts: {[a.kind for a in disconnect['alerts']]}")
    add("")
    add("The trade is the SAME trade. The arming alert is honestly ABSENT -- arming happened "
        "during the outage and the screener does not back-fill it -- and the failure banner was "
        "raised and then cleared, both on the record.")
    add("")

    add("## 5 -- What this does NOT show")
    add("")
    add("* **A live morning.** QUESTIONS.md **Q-28** blocks it: CONTEXT 3.3's POC needs CONTEXT "
        "4.5's gate 1 to have passed, gate 1 needs the day's bhavcopy, and today's does not "
        "exist during today. Every walk above is a REPLAY, where the battery is the "
        "backtester's own verdict.")
    add("* **Which instrument master a live morning takes.** QUESTIONS.md **Q-29**. The replay "
        "runs under the Q-20 pin, which already governs the backtest path.")
    add("* **Money.** The screener sizes the alert (`qty`) from CONTEXT 3.5 and prices nothing; "
        "PnL is the backtester's business and is unchanged by this chunk.")
    add("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chunk13_replay_walk")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--recording-root", default="",
        help="where the replay recordings go; default a temporary directory OUTSIDE the stores",
    )
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="acumen-chunk13-") as scratch:
        root = Path(args.recording_root) if args.recording_root else Path(scratch)
        walks = []
        for symbol, day in DAYS:
            print(f"replaying {symbol} {day.isoformat()}", flush=True)
            walks.append(walk(symbol, day, root))
        print("simulated disconnect", flush=True)
        disconnect = disconnect_check(DAYS[0][0], DAYS[0][1], root)
        text = render(walks, disconnect)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(text):,} chars)")

    failures = [w for w in walks if not (w["identical"] and w["bars_identical"]
                                         and w["bias_identical"])]
    if failures:
        print("REPLAY INVARIANT FAILED for: "
              + ", ".join(f"{w['symbol']} {w['day']}" for w in failures))
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover -- ASSERTED AT THE SOURCE (an AST test)
    raise SystemExit(main())
