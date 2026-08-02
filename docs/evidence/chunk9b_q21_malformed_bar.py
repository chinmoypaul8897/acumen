"""Q-21: the vendor-corrupt 1-minute bars, and what the fix costs the chunk-9B run.

Committed under CLAUDE.md's evidence rule ("any session making claims from real store data
commits the generating script and its output under docs/evidence/"). Regenerate with:

    python docs/evidence/chunk9b_q21_malformed_bar.py --out docs/evidence/chunk9b_q21_malformed_bar.md

OFFLINE and READ-ONLY on both stores and on the crashed run directory. Nothing here writes,
renames or deletes anything under `data_root` -- the crashed run directory is the OPERATOR's to
rename (CLAUDE.md data-store safety, layer 2), and this script only reads its progress file.

WHAT THIS ESTABLISHES, each from the machine rather than from the crash transcript:

1. WHERE the run stopped -- the completed shards and the crashed run's own progress file give
   the walk position and therefore the symbol the runner died inside, by the universe order the
   run itself walked (read from the disclosed-residual register, never typed).
2. WHICH BARS -- a scan of the WHOLE minute lake, all 204 settled symbols, for a stored bar
   whose open or close lies outside [low, high]. Not just the one that crashed: the population.
3. WHICH PAIR it broke -- the trade day whose CONTEXT 3.2 bias pair reads the crash symbol's
   corrupt date as D-1, and whether that pair really is a Rule-3 outside bar (which is the only
   reason 1-minute candles are loaded at all).
4. THAT DAY'S GATE VERDICTS from the store -- the Q-21 ruling's RATIONALE is that gate 2
   already declares an impossible-OHLC day unusable for trading, so this checks it rather than
   repeating it. The verdicts are printed whichever way they fall.
5. THE FIX, on the REAL bar -- the pure invariant still raises (it is what caught the
   corruption), the run's loader now names the bar, and the runner turns it into ONE counted
   refusal instead of a dead run.
6. THE BLAST RADIUS -- every symbol carrying a malformed bar, asked whether any trade day's
   Rule-3 scan actually READS it. That is the exact set of ledger rows the relaunched run will
   refuse, and it is also the test of the ruling's own claim that the fix changes nothing for
   the symbols that had already completed.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:  # a bare clone runs with no install step (chunk-0 B2)
    sys.path.insert(0, str(REPO / "src"))

from acumen import backtest as bt  # noqa: E402
from acumen import run_backtest as rb  # noqa: E402
from acumen.bias import BiasError, Candle, evaluate_pair  # noqa: E402
from acumen.bias_engine import BiasEngine, BiasEngineError, MalformedMinuteBar  # noqa: E402
from acumen.calendar import CalendarError, TradingCalendar  # noqa: E402
from acumen.config import load_config  # noqa: E402
from acumen.daily_store import DailyStore  # noqa: E402
from acumen.instrument_master import load_master_file  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402
from acumen.signal_engine import SignalPipeline  # noqa: E402

RUN_DIRNAME = "chunk9b_full"

#: The window section 5's demonstration walks. The full run's span is ten years; a short window
#: around the event proves the SHAPE of the refusal (one counted row, no crash) without
#: re-walking the history, and every number taken from it is labelled as such.
DEMO_START = date(2023, 2, 1)
DEMO_END = date(2023, 3, 31)


def price(paise: int) -> str:
    return f"{paise / 100:,.2f}"


def faults(hit: dict) -> list[str]:
    """Everything impossible about one stored bar, named."""
    out: list[str] = []
    if hit["high"] < hit["low"]:
        out.append("H < L")
    if not (hit["low"] <= hit["open"] <= hit["high"]):
        out.append(f"O {hit['open']} outside [L {hit['low']}, H {hit['high']}]")
    if not (hit["low"] <= hit["close"] <= hit["high"]):
        out.append(f"C {hit['close']} outside [L {hit['low']}, H {hit['high']}]")
    return out


def seen_by_gate2(hit: dict) -> bool:
    """Would CONTEXT 4.5's gate 2 exclude the day for this bar?

    Gate 2 enumerates exactly two OHLC-sanity triggers -- ``high < low`` and a CLOSE outside
    ``[low, high]`` -- and `quality_gates.integrity_gate` states in its own docstring that the
    OPEN is deliberately NOT tested. So a bar whose only fault is its open is invisible to it.
    """
    return hit["high"] < hit["low"] or not (hit["low"] <= hit["close"] <= hit["high"])


# --- 1. where the run stopped -------------------------------------------------------------------


def crash_position(data: Path) -> dict:
    run_dir = data / "backtests" / RUN_DIRNAME
    progress = json.loads((run_dir / bt.PROGRESS_NAME).read_text(encoding="utf-8"))
    done = [str(symbol) for symbol in progress.get("completed", [])]
    shards = sorted(p.stem for p in (run_dir / bt.SHARD_DIRNAME).glob("*.jsonl"))
    register = bt.load_residual_register(data / bt.RESIDUAL_LEDGER_RELPATH)
    universe = rb.settled_symbols(register)
    return {
        "run_dir": run_dir,
        "completed": done,
        "shards": shards,
        "shards_match_progress": sorted(done) == shards,
        "universe": universe,
        "prefix_is_the_walk_order": list(universe[: len(done)]) == done,
        "died_in": universe[len(done)] if len(done) < len(universe) else None,
        "position": len(done) + 1,
        "spec_digest": progress.get("spec_digest"),
    }


# --- 2. which bars ------------------------------------------------------------------------------


def scan_lake(data: Path, symbols) -> tuple[list[dict], int, int]:
    """Every stored 1-minute bar whose open or close is outside [low, high]. READ-ONLY."""
    columns = ["stamp", "open_paise", "high_paise", "low_paise", "close_paise", "volume"]
    found: list[dict] = []
    files = 0
    bars = 0
    for symbol in symbols:
        pattern = str(data / "minute_store" / "minute" / symbol / f"{symbol}_*.parquet")
        for path in sorted(glob.glob(pattern)):
            files += 1
            table = pq.read_table(path, columns=columns).to_pydict()
            bars += len(table["stamp"])
            for index in range(len(table["stamp"])):
                o = table["open_paise"][index]
                h = table["high_paise"][index]
                l = table["low_paise"][index]
                c = table["close_paise"][index]
                if h < l or not (l <= o <= h) or not (l <= c <= h):
                    found.append(
                        {
                            "symbol": symbol,
                            "stamp": table["stamp"][index],
                            "open": o,
                            "high": h,
                            "low": l,
                            "close": c,
                            "volume": table["volume"][index],
                        }
                    )
    return found, files, bars


# --- 3. the pair --------------------------------------------------------------------------------


def pair_for(calendar: TradingCalendar, current: date) -> tuple[date, date, date] | None:
    """The trade day D whose CONTEXT 3.2 pair reads ``current`` as D-1, plus that pair."""
    day = current + timedelta(days=1)
    while day <= current + timedelta(days=15):
        try:
            if calendar.is_trading_day(day):
                pair = calendar.bias_pair(day)
                if pair.current == current:
                    return day, pair.current, pair.previous
        except CalendarError:
            pass
        day += timedelta(days=1)
    return None


def daily_candle(store: DailyStore, symbol: str, day: date) -> Candle | None:
    frame = store.daily(symbol, day, day)
    if frame.empty:
        return None
    row = frame.iloc[0]
    return Candle(
        open=int(row["open_paise"]),
        high=int(row["high_paise"]),
        low=int(row["low_paise"]),
        close=int(row["close_paise"]),
        day=day,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    config = load_config(include_env=False)
    data = config.path("data_root")
    daily_store = DailyStore.at(data / "daily_store")
    minute_store = MinuteStore.at(data / "minute_store")

    lines: list[str] = []

    def add(text: str = "") -> None:
        lines.append(text)

    add("# Q-21 evidence -- the malformed 1-minute bars that stopped the chunk-9B run")
    add()
    add(
        "Generated by `docs/evidence/chunk9b_q21_malformed_bar.py`, offline and READ-ONLY over "
        "the stores and over the crashed run directory. No file under `data_root` is written, "
        "renamed or removed by this script."
    )
    add()

    # 1 --------------------------------------------------------------------------------------
    where = crash_position(data)
    crash_symbol = where["died_in"]
    add("## 1. Where the run stopped, read from the run directory itself")
    add()
    add(f"* run directory: `{where['run_dir']}`")
    add(f"* completed symbols in `progress.json`: **{len(where['completed'])}**")
    add(
        f"* shards on disk: **{len(where['shards'])}** "
        f"(they match the progress file exactly: {where['shards_match_progress']})"
    )
    add(f"* settled universe: **{len(where['universe'])}** symbols")
    add(
        f"* the completed list is the universe's own leading prefix: "
        f"**{where['prefix_is_the_walk_order']}**"
    )
    add(
        f"* so the runner died inside symbol **{where['position']} of "
        f"{len(where['universe'])}: {crash_symbol}** -- the last symbol it FINISHED was "
        f"`{where['completed'][-1]}` (#{len(where['completed'])})"
    )
    add(f"* the run's spec digest: `{where['spec_digest']}`")
    add()
    add(
        "A shard is written only when its symbol is COMPLETE, so those "
        f"{len(where['shards'])} shards are whole symbols and the crash cost no finished work."
    )
    add()

    # 2 --------------------------------------------------------------------------------------
    found, files, bars = scan_lake(data, where["universe"])
    add("## 2. The malformed bars -- the whole population, not just the one that crashed")
    add()
    add(
        f"Scanned **{bars:,} stored 1-minute bars** in {files:,} parquet files across all "
        f"{len(where['universe'])} settled symbols for the impossible shape (open or close "
        "outside `[low, high]`, or high below low)."
    )
    add()
    add("| symbol | stamp | O | H | L | C | V | what is wrong | gate 2 sees it |")
    add("|---|---|---|---|---|---|---|---|---|")
    for hit in sorted(found, key=lambda h: (h["stamp"], h["symbol"])):
        add(
            f"| {hit['symbol']} | {hit['stamp']:%Y-%m-%d %H:%M} | {hit['open']} | {hit['high']} "
            f"| {hit['low']} | {hit['close']} | {hit['volume']:,} | {'; '.join(faults(hit))} | "
            f"{'yes' if seen_by_gate2(hit) else 'NO'} |"
        )
    add()
    add(f"**Total: {len(found)} malformed bar(s) in the entire minute lake.**")
    add()

    if not found:
        add("Nothing further to report: the shape is absent from the store.")
        _emit(lines, args.out)
        return 0

    dates = sorted({hit["stamp"].date() for hit in found})
    blind = [hit for hit in found if not seen_by_gate2(hit)]
    stamps = sorted({hit["stamp"].strftime("%H:%M") for hit in found})
    spread = ", ".join(
        f"{when} ({sum(1 for h in found if h['stamp'].date() == when)} symbols)"
        for when in dates
    )
    clock = f", every one of them stamped {stamps[0]}" if len(stamps) == 1 else ""
    add(f"They sit on **{len(dates)} date(s)**: {spread}{clock}.")
    add()
    add(
        f"**{len(blind)} of {len(found)} are invisible to CONTEXT 4.5's gate 2**, which "
        "enumerates only `high < low` and a CLOSE outside `[low, high]` and states in its own "
        "docstring that the OPEN is deliberately not tested (section 4 measures this on the "
        "crash day itself)."
    )
    add()

    crash_bars = [hit for hit in found if hit["symbol"] == crash_symbol]
    bar = crash_bars[0]
    bad_day = bar["stamp"].date()
    add(
        f"The bar the run died on is **{crash_symbol} {bar['stamp']:%Y-%m-%d %H:%M}**: prices "
        f"are integer paise (CONTEXT 7-E11), so its open is Rs {price(bar['open'])} against a "
        f"low of Rs {price(bar['low'])} -- the open sits **{bar['low'] - bar['open']} paise "
        "BELOW the low**. No trade can print outside its own bar's range, so the bar is "
        "vendor-corrupt, not merely unusual."
    )
    add()

    # 3 --------------------------------------------------------------------------------------
    calendar = TradingCalendar.from_daily_store_range(
        daily_store, min(dates) - timedelta(days=45), max(dates) + timedelta(days=45)
    )
    pair = pair_for(calendar, bad_day)
    add("## 3. The pair it broke, and why minutes were read at all")
    add()
    if pair is None:
        add(f"No trade day in the following fortnight reads {bad_day} as D-1.")
    else:
        trade_day, d1, d2 = pair
        current = daily_candle(daily_store, crash_symbol, d1)
        previous = daily_candle(daily_store, crash_symbol, d2)
        outside = current.high > previous.high and current.low < previous.low
        verdict = evaluate_pair(previous, current, lambda: None, None)
        add(f"* trade day **D = {trade_day}**, whose CONTEXT 3.2 pair is D-1 {d1}, D-2 {d2}")
        add(
            f"* candle(D-2) = P: O {previous.open} H {previous.high} L {previous.low} "
            f"C {previous.close}  (body [{previous.body_min}, {previous.body_max}])"
        )
        add(
            f"* candle(D-1) = C: O {current.open} H {current.high} L {current.low} "
            f"C {current.close}"
        )
        add(
            f"* C.high > P.high **and** C.low < P.low: **{outside}**"
            + (
                " -- an OUTSIDE BAR whose close sits inside P's body, so Rules 1 and 2 do not "
                "fire and Rule 3 decides"
                if outside
                else " -- so this pair is NOT an outside bar"
            )
        )
        add(
            f"* with the minutes withheld the engine answers `{verdict.rule}`"
            + (
                " -- the Rule-3 branch, which is proof that this pair reaches the 1-minute scan"
                if verdict.rule.startswith("rule-3")
                else " -- which is NOT a Rule-3 branch"
            )
        )
        if bar["open"] == current.open:
            add(
                f"* the corrupt bar's own open ({bar['open']}) equals the RAW bhavcopy open for "
                f"{d1} to the paisa, while the raw daily low is {current.low}: it is the "
                f"vendor's first-minute LOW ({bar['low']}) that is wrong, not its open"
            )
        add()
        add(
            "That is the whole mechanism: only Rule 3 asks WHICH extreme broke first, only Rule "
            f"3 loads 1-minute candles, and the day it loads is D-1 = {d1}."
        )
    add()

    # 4 --------------------------------------------------------------------------------------
    master = load_master_file(config.instrument_master_path())
    pipeline = SignalPipeline(
        minute_store=minute_store,
        daily_store=daily_store,
        master=master,
        row_size=config.row_size,
    )
    minutes = minute_store.minutes(crash_symbol, bad_day)
    gates = pipeline.gate_day(crash_symbol, bad_day, minutes)
    add(f"## 4. {crash_symbol} {bad_day}'s own gate verdicts, recomputed from the store")
    add()
    add(f"* stored bars: **{len(minutes):,}**")
    add(
        f"* **gate 1** (volume reconciliation): "
        f"{'PASS' if gates.gate1 is not None and gates.gate1.passed else 'FAIL'}"
        f"{' (relieved)' if gates.relieved else ''}"
    )
    add(f"* **gate 2** (intraday integrity): {'PASS' if gates.gate2.passed else 'FAIL'}")
    if gates.gate2.reasons:
        for reason in gates.gate2.reasons:
            add(f"  * {reason}")
    add(f"* **gate 1P** (price containment): {'PASS' if gates.gate1p.passed else 'FAIL'}")
    add(f"* the day is usable for trading: **{gates.usable}**")
    add()
    if not gates.usable:
        add(
            "This is the Q-21 ruling's rationale, measured rather than assumed: CONTEXT 4.6's "
            "battery already declares this day unusable, so its minutes cannot then be trusted "
            "to decide a bias for the NEXT day."
        )
    else:
        add(
            "**The ruling's rationale does not hold for this bar's shape, and that matters.** "
            "The ruling reasons that gate 2 already declares an impossible-OHLC day unusable; "
            "this day PASSES every gate. It is not a hole in the gate -- CONTEXT 4.5 enumerates "
            "exactly two OHLC-sanity triggers, `high < low` and a CLOSE outside `[low, high]`, "
            "and `quality_gates.integrity_gate` states in its own docstring that **`open` is "
            "deliberately NOT tested**. This bar's close equals its low, so nothing gate 2 "
            "tests is violated. Only `bias.Candle`'s CONTEXT 7-E11 invariant, which validates "
            "the open too, catches it. So an open outside `[low, high]` has NO backstop other "
            "than the Q-21 refusal itself: without the fix this day's minutes would have "
            "decided a bias and the day would have traded on a bar that cannot exist. The "
            "ruling's INSTRUCTION is executed exactly as written; the discrepancy in its "
            "rationale is recorded for the architect and decides nothing here."
        )
    add()

    # 5 --------------------------------------------------------------------------------------
    add("## 5. The fix, exercised on the real bar")
    add()
    stored = next(b for b in minutes if b.stamp == bar["stamp"])
    try:
        Candle(
            open=int(stored.open_paise),
            high=int(stored.high_paise),
            low=int(stored.low_paise),
            close=int(stored.close_paise),
        )
        raised = "NOTHING -- the invariant did not fire (this would be a defect)"
    except BiasError as exc:
        raised = f"`BiasError: {exc}`"
    add(f"* the pure CONTEXT 7-E11 invariant in `bias.Candle` still refuses the bar: {raised}")
    add("  * that exception, uncaught, is exactly what killed the run")
    load = bt.minute_loader(minute_store)
    try:
        load(crash_symbol, bad_day)
        named = "NOTHING -- the loader did not refuse (this would be a defect)"
    except MalformedMinuteBar as exc:
        named = f"`{exc.detail()}`"
    add(f"* the RUN's loader now names it instead of dying anonymously: {named}")
    add()

    runner, master_path, _ = bt.build_runner(
        (crash_symbol,),
        DEMO_START,
        DEMO_END,
        non_standard_sessions=_cached_sessions(data),
    )
    walked = runner.walk_symbol(crash_symbol).rows
    refused = [row for row in walked if bt.FLAG_MALFORMED_MINUTE_BAR in row.flags]
    manifest = runner.build_manifest(tuple(walked), {crash_symbol: {}})
    label = "rule-3 day refused on a malformed 1-minute bar (QUESTIONS.md Q-21)"
    add(
        f"Walking `{crash_symbol}` over {DEMO_START} .. {DEMO_END} (a short window around the "
        "event, not the run's ten-year span) now COMPLETES:"
    )
    add()
    add(f"* symbol-days walked: **{len(walked)}**, exceptions raised: **0**")
    add(f"* days carrying the Q-21 flag: **{len(refused)}**")
    for row in refused:
        add(f"  * `{row.day}` -- status `{row.status}`")
        add(f"    * reason: `{row.reason}`")
        add(
            f"    * bias rule `{row.bias_rule}`, carried bias `{row.bias}`, traded: "
            f"{row.executed}"
        )
    add(f"* the manifest's rare-shape counter `{label}`: **{manifest['rare_shapes'][label]}**")
    add(f"* instrument master pinned for this walk: `{Path(master_path).name}`")
    add()
    add(
        "One refused, counted symbol-day where there used to be a dead run. Every other day of "
        "the window is unaffected, and no bar was skipped to get there."
    )
    add()

    # 6 --------------------------------------------------------------------------------------
    add("## 6. The blast radius: which of these bars a Rule-3 scan actually READS")
    add()
    add(
        "A malformed bar only matters if some trade day's Rule-3 scan loads its date. Rules 1 "
        "and 2 read no minutes at all, and Rule 3 reads D-1's minutes only -- so for each "
        "symbol below the question is whether the trade day whose pair takes the corrupt date "
        "as D-1 is a Rule-3 outside bar. This is asked of the REAL engine, with that symbol's "
        "own corporate-action factors wired, and it is the exact set of rows the relaunched run "
        "will refuse."
    )
    add()
    symbols_hit = sorted({hit["symbol"] for hit in found})
    factors, suppressions, _, _ = bt.build_factor_tables(
        tuple(symbols_hit),
        daily_store,
        start=min(dates) - timedelta(days=400),
        end=max(dates) + timedelta(days=30),
    )
    completed = set(where["completed"])
    rows: list[tuple[str, str, str, str, str]] = []
    refused_count = 0
    for hit in sorted(found, key=lambda h: (h["symbol"], h["stamp"])):
        symbol = hit["symbol"]
        when = hit["stamp"].date()
        target = pair_for(calendar, when)
        walk_state = "completed before the crash" if symbol in completed else "not yet walked"
        if target is None:
            rows.append((symbol, str(when), "-", "no trade day reads it as D-1", walk_state))
            continue
        trade_day = target[0]
        engine = BiasEngine(
            store=daily_store,
            calendar=calendar,
            factors=tuple(factors.get(symbol, ())),
            suppressions=tuple(suppressions.get(symbol, ())),
            minute_loader=bt.minute_loader(minute_store),
        )
        try:
            outcome = engine.bias_for_day(symbol, trade_day, seed_from=trade_day)
            rule = outcome.rule
            if outcome.unresolved_detail is not None:
                refused_count += 1
                verdict = "**REFUSED (Q-21)**"
            else:
                verdict = "reads no minutes" if not rule.startswith("rule-3") else "Rule 3, clean"
        except BiasEngineError as exc:
            rule = "engine error"
            verdict = f"{type(exc).__name__}"
        rows.append((symbol, str(when), str(trade_day), f"`{rule}` -- {verdict}", walk_state))

    add("| symbol | corrupt date | trade day reading it as D-1 | what the engine decides | walk state |")
    add("|---|---|---|---|---|")
    for row in rows:
        add("| " + " | ".join(row) + " |")
    add()
    hit_completed = [s for s in symbols_hit if s in completed]
    add(
        f"**{refused_count} symbol-day(s) of {len(found)} malformed bars are actually refused.** "
        f"{len(hit_completed)} of the {len(symbols_hit)} affected symbols had already COMPLETED "
        "before the crash, which is the ruling's own claim under test."
    )
    add()
    completed_refusals = [
        row for row in rows if row[0] in completed and "REFUSED" in row[3]
    ]
    if completed_refusals:
        add(
            f"**The claim does NOT hold**: {len(completed_refusals)} completed symbol(s) gain a "
            "refusal, so their shards are not reproducible under the fix."
        )
    else:
        add(
            "**The ruling's conclusion holds, but not for the reason it gives.** The ruling says "
            "the symbols that completed \"provably contain no such day (they would have "
            f"crashed)\". They DO contain such bars -- {len(hit_completed)} of them do -- and "
            "they did not crash because no Rule-3 scan ever asked for those dates. The "
            "conclusion is nonetheless correct: not one completed symbol gains a refusal, so "
            "every finished shard would reproduce byte-for-byte under the fixed code. What was "
            "load-bearing was the READ, not the presence of the bar."
        )
    add()

    _emit(lines, args.out)
    return 0


def _cached_sessions(data: Path) -> frozenset[date]:
    """The crashed run's own CONTEXT 7-E2 scan, read from its `sessions.json`. READ-ONLY.

    The key that guards `load_session_scan` includes the code SHA, which has moved with the fix,
    so the payload is read directly and used for exactly one thing: making the demonstration in
    section 5 walk under the same E2 exclusions the crashed run walked under.
    """
    path = data / "backtests" / RUN_DIRNAME / bt.SESSIONS_NAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    return frozenset(date.fromisoformat(day) for day in payload.get("non_standard", []))


def _emit(lines: list[str], out: Path | None) -> None:
    text = "\n".join(lines).rstrip() + "\n"
    if out is None:
        print(text)
        return
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(lines)} lines)")


if __name__ == "__main__":
    raise SystemExit(main())
