"""Q-21(b): what the "battery-failing D-1" refusal costs the chunk-9B run, measured.

Committed under CLAUDE.md's evidence rule ("any session making claims from real store data
commits the generating script and its output under docs/evidence/"). Regenerate with:

    python docs/evidence/chunk9b_q21b_blast_radius.py --out docs/evidence/chunk9b_q21b_blast_radius.md

OFFLINE and READ-ONLY on both stores and on the crashed run directory. Nothing here writes,
renames or deletes anything under `data_root`.

THE QUESTION, exactly as the architect's Q-21(b) ruling poses it: a day's minutes may serve a
Rule-3 first-break scan ONLY if that day passes the CONTEXT 4.5/4.6 gate battery. So: across all
204 settled symbols over the run's own span, how many trade days does that refuse?

HOW IT IS ASKED, so that the number is the RUN's number and not a re-implementation's:

1. THE SPAN AND THE UNIVERSE come from `run_backtest.preflight` -- the same measurement the run
   itself takes, never typed here.
2. THE CALENDAR is derived exactly as `backtest.build_runner` derives it, including the CONTEXT
   7-E2 non-standard sessions removed from it. That scan is O(symbols x span days) minute reads,
   which is why the run caches it; this script REUSES the crashed run's cached `sessions.json`
   payload rather than re-scanning, and says so in its output.
3. WHICH DAYS REACH THE RULE-3 SCAN is decided by the REAL pure engine. Each candidate pair is
   put through `bias.evaluate_pair` with a probe provider that records whether it was called and
   returns nothing: `evaluate_pair` calls the provider ONLY in the Rule-3 branch (CONTEXT 3.2 --
   only Rule 3 asks which extreme broke first), so "the probe was called" IS "this day consumes
   D-1's minutes". Suppressed pairs are skipped exactly as `BiasEngine._bias_for` skips them,
   and the previous candle is brought into the current candle's scale by the same chunk-3
   pairwise adjustment the engine applies. Nothing here re-implements a rule.
   The carry is NOT threaded: whether the provider is called depends only on (P, C), never on
   the carried bias, so a per-symbol walk would return the same set of days at 2,400x the cost.
4. THE VERDICT for each such D-1 is `SignalPipeline.gate_day(...).refusal_detail` -- the same
   battery, from the same pipeline class, that the runner puts in front of the load.

WHAT ELSE IT ANSWERS, because both are load-bearing for the relaunch:

* whether any of the 103 symbols the crashed run COMPLETED gains a refusal (if one does, its
  shard would no longer reproduce and the crashed run's shards stop being a cross-check);
* whether the committed chunk-9A pilot pack's window moves (its 290/146/88/56 reconciliation is
  pinned by tests and quoted in three reviews).

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:  # a bare clone runs with no install step (chunk-0 B2)
    sys.path.insert(0, str(REPO / "src"))

from acumen import backtest as bt  # noqa: E402
from acumen import corp_actions as ca  # noqa: E402
from acumen import pilot_evidence as pe  # noqa: E402
from acumen import run_backtest as rb  # noqa: E402
from acumen import signal_engine as se  # noqa: E402
from acumen.bias import BiasError, Candle, evaluate_pair  # noqa: E402
from acumen.calendar import CalendarError, TradingCalendar  # noqa: E402
from acumen.config import load_config  # noqa: E402
from acumen.daily_store import DailyStore  # noqa: E402
from acumen.instrument_master import load_master_file  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402
from acumen.signal_engine import SignalPipeline  # noqa: E402

RUN_DIRNAME = "chunk9b_full"

#: The gate labels, in the battery's own order, so every table below sorts the same way.
GATE_ORDER: tuple[str, ...] = (
    se.NOT_EVALUATED_GATE1,
    se.NOT_EVALUATED_GATE2,
    se.NOT_EVALUATED_GATE1P,
)


class Probe:
    """A Rule-3 minute provider that answers NOTHING and remembers that it was asked."""

    def __init__(self) -> None:
        self.called = False

    def __call__(self):
        self.called = True
        return None


def cached_sessions(data: Path) -> tuple[frozenset[date], str]:
    """The crashed run's own CONTEXT 7-E2 scan, read from its `sessions.json`. READ-ONLY."""
    path = data / "backtests" / RUN_DIRNAME / bt.SESSIONS_NAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    days = frozenset(date.fromisoformat(day) for day in payload.get("non_standard", []))
    return days, str(payload.get("code_sha", "unknown"))


def completed_symbols(data: Path) -> list[str]:
    """The symbols the crashed run FINISHED, from its own progress file. READ-ONLY."""
    path = data / "backtests" / RUN_DIRNAME / bt.PROGRESS_NAME
    if not path.is_file():
        return []
    return [str(s) for s in json.loads(path.read_text(encoding="utf-8")).get("completed", [])]


def candles_by_date(store: DailyStore, symbol: str, first: date, last: date) -> dict[date, Candle]:
    """One symbol's whole daily history over the window, read ONCE. Q-4 equity series on read."""
    frame = store.daily(symbol, first, last)
    out: dict[date, Candle] = {}
    for row in frame.itertuples(index=False):
        try:
            out[row.trade_date] = Candle(
                open=int(row.open_paise),
                high=int(row.high_paise),
                low=int(row.low_paise),
                close=int(row.close_paise),
                day=row.trade_date,
            )
        except BiasError:
            continue  # a malformed DAILY candle is a different question (none in this store)
    return out


def adjust_previous(previous: Candle, current: Candle, factors, symbol: str) -> Candle:
    """`BiasEngine._adjust_previous`, applied here so the pair is compared in ONE scale."""
    between = ca.factors_between(factors, previous.day, current.day, symbol=symbol)
    if not between:
        return previous
    return Candle(
        open=ca.adjust_pair(previous.open, between),
        high=ca.adjust_pair(previous.high, between),
        low=ca.adjust_pair(previous.low, between),
        close=ca.adjust_pair(previous.close, between),
        day=previous.day,
    )


def rule3_scan_days(
    symbol: str,
    *,
    calendar: TradingCalendar,
    candles: dict[date, Candle],
    factors,
    suppressions,
    start: date,
    end: date,
) -> list[tuple[date, date]]:
    """Every ``(trade day D, D-1)`` in the span whose pair reaches CONTEXT 3.2's Rule-3 scan."""
    suppressed = {s.ex_date for s in suppressions if s.symbol == symbol.upper()}
    found: list[tuple[date, date]] = []
    day = start
    while day <= end:
        try:
            if not calendar.is_trading_day(day):
                day += timedelta(days=1)
                continue
            pair = calendar.bias_pair(day)
        except CalendarError:
            day += timedelta(days=1)
            continue
        current, previous = candles.get(pair.current), candles.get(pair.previous)
        if (
            current is not None
            and previous is not None
            and pair.current not in suppressed
            and pair.previous not in suppressed
        ):
            probe = Probe()
            evaluate_pair(adjust_previous(previous, current, factors, symbol), current, probe, None)
            if probe.called:
                found.append((day, pair.current))
        day += timedelta(days=1)
    return found


def battery_refusal(
    pipeline: SignalPipeline, minute_store: MinuteStore, symbol: str, day: date
) -> tuple[str, str] | None:
    """The CONTEXT 4.6 battery for one stored day, or ``None`` when it passes (or has no bars).

    A day with NO stored minutes is not gated and not refused -- it is CONTEXT 3.2 / R1-Q6's
    documented missing-1-minute carry, which the gated loader leaves exactly as it was.
    """
    bars = minute_store.minutes(symbol, day)
    if not bars:
        return None
    return pipeline.gate_day(symbol, day, bars).refusal_detail


def short(reason: str, width: int = 110) -> str:
    """A gate's own reason, trimmed for a table cell (the full text is in the ledger row)."""
    flat = " ".join(reason.split())
    return flat if len(flat) <= width else flat[: width - 3] + "..."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--symbols", default=None, help="comma-separated subset (a smoke run of this script)"
    )
    args = parser.parse_args()

    config = load_config(include_env=False)
    data = config.path("data_root")
    daily_store = DailyStore.at(data / "daily_store")
    minute_store = MinuteStore.at(data / "minute_store")

    report = rb.preflight()
    universe = list(report.symbols)
    start, end = report.start, report.end
    if args.symbols:
        universe = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    master = load_master_file(config.instrument_master_path())
    pipeline = SignalPipeline(
        minute_store=minute_store,
        daily_store=daily_store,
        master=master,
        row_size=config.row_size,
    )
    non_standard, scan_sha = cached_sessions(data)
    calendar = TradingCalendar.from_daily_store_range(
        daily_store, start - timedelta(days=bt.CALENDAR_LEAD_DAYS), end
    )
    from dataclasses import replace as _replace

    calendar = _replace(
        calendar, trading_days=frozenset(calendar.trading_days) - set(non_standard)
    )
    factors, suppressions, factor_digest, _ = bt.build_factor_tables(
        tuple(universe), daily_store, start=start, end=end
    )
    done = set(completed_symbols(data))

    lines: list[str] = []

    def add(text: str = "") -> None:
        lines.append(text)

    scan_total = 0
    refused: list[tuple[str, date, date, str, str]] = []  # symbol, D, D-1, gate, reason
    no_minutes = 0
    symbols_with_scan = 0
    for symbol in universe:
        candles = candles_by_date(
            daily_store, symbol, start - timedelta(days=bt.CALENDAR_LEAD_DAYS), end
        )
        days = rule3_scan_days(
            symbol,
            calendar=calendar,
            candles=candles,
            factors=tuple(factors.get(symbol, ())),
            suppressions=tuple(suppressions.get(symbol, ())),
            start=start,
            end=end,
        )
        scan_total += len(days)
        symbols_with_scan += 1 if days else 0
        for trade_day, d1 in days:
            if not minute_store.minutes(symbol, d1):
                no_minutes += 1
                continue
            verdict = battery_refusal(pipeline, minute_store, symbol, d1)
            if verdict is not None:
                refused.append((symbol, trade_day, d1, verdict[0], verdict[1]))

    # --- the report ---------------------------------------------------------------------------
    add("# Q-21(b) evidence -- what the battery-gated Rule-3 scan costs the chunk-9B run")
    add()
    add(
        "Generated by `docs/evidence/chunk9b_q21b_blast_radius.py`, offline and READ-ONLY over "
        "the stores and over the crashed run directory. No file under `data_root` is written, "
        "renamed or removed by this script."
    )
    add()
    add("## 1. What was asked, and of what")
    add()
    add(f"* span, measured by the run's own preflight: **{start} -> {end}**")
    add(f"* universe: **{len(universe)}** settled symbol(s)")
    add(
        f"* CONTEXT 7-E2 non-standard sessions removed from the calendar: "
        f"**{len(non_standard)}** ({', '.join(day.isoformat() for day in sorted(non_standard))})"
    )
    add(
        f"  * REUSED from the crashed run's cached `sessions.json` (scanned under code SHA "
        f"`{scan_sha[:12]}`), not re-scanned: the scan is O(symbols x span days) minute reads, "
        "which is why the run caches it, and no code in this fix touches the E2 detector."
    )
    add(f"* corporate-action factor digest for this universe: `{factor_digest}`")
    add(f"* instrument master, pinned (Q-20): `{Path(config.instrument_master_path()).name}`")
    add()
    add(
        "**Rule-3 scan days** below means what the ruling means: a trade day whose CONTEXT 3.2 "
        "pair reaches Rule 3 and therefore CONSUMES D-1's 1-minute candles. It is decided by "
        "`bias.evaluate_pair` itself, with a probe provider recording whether it was called -- "
        "the pure engine calls that provider in the Rule-3 branch and nowhere else."
    )
    add()

    # --- 2 ------------------------------------------------------------------------------------
    add("## 2. The blast radius")
    add()
    add("| measure | count |")
    add("|---|---|")
    add(f"| trade days whose pair reaches the Rule-3 1-minute scan | **{scan_total:,}** |")
    add(f"| ...of those, D-1 has NO stored minutes (CONTEXT 3.2 / R1-Q6 carry, unchanged) | {no_minutes:,} |")
    add(f"| ...of those, D-1 has minutes and PASSES the battery (scan proceeds) | {scan_total - no_minutes - len(refused):,} |")
    add(f"| **...of those, D-1 has minutes and FAILS the battery -> REFUSED (Q-21(b))** | **{len(refused):,}** |")
    add(f"| symbols carrying at least one such refusal | **{len({r[0] for r in refused}):,}** of {len(universe)} |")
    add()
    share = (len(refused) / scan_total * 100) if scan_total else 0.0
    add(
        f"So the ruling refuses **{len(refused):,} symbol-day(s)** of the "
        f"{scan_total:,} that reach the Rule-3 scan ({share:.2f}% of them), across "
        f"{len({r[0] for r in refused}):,} symbol(s). Every one of them was, before this fix, a "
        "bias decided by minutes the gate battery had already judged unusable for trading."
    )
    add()

    if refused:
        by_gate = Counter(row[3] for row in refused)
        add("### by which gate refused D-1")
        add()
        add("| gate | refused trade days |")
        add("|---|---|")
        for gate in GATE_ORDER:
            if by_gate.get(gate):
                add(f"| {gate} | {by_gate[gate]:,} |")
        add()

        by_era = Counter(row[2].year for row in refused)
        add("### by era (the YEAR of the refused D-1)")
        add()
        add("| year | refused trade days | symbols |")
        add("|---|---|---|")
        for year in sorted(by_era):
            syms = {row[0] for row in refused if row[2].year == year}
            add(f"| {year} | {by_era[year]:,} | {len(syms):,} |")
        add()

        by_symbol = Counter(row[0] for row in refused)
        add("### by symbol")
        add()
        add("| symbol | refused trade days | eras (years of D-1) | completed before the crash |")
        add("|---|---|---|---|")
        for symbol in sorted(by_symbol):
            years = sorted({row[2].year for row in refused if row[0] == symbol})
            add(
                f"| {symbol} | {by_symbol[symbol]:,} | "
                f"{', '.join(str(y) for y in years)} | "
                f"{'yes' if symbol in done else 'no'} |"
            )
        add()

    # --- 3 ------------------------------------------------------------------------------------
    add("## 3. Every refused symbol-day, with the gate's own words")
    add()
    if not refused:
        add("There are none: no Rule-3 scan in the whole span asks for a battery-failing D-1.")
    else:
        add("| symbol | trade day D | D-1 (the refused evidence) | gate | the gate's own reason |")
        add("|---|---|---|---|---|")
        for symbol, trade_day, d1, gate, reason in sorted(refused, key=lambda r: (r[0], r[1])):
            add(f"| {symbol} | {trade_day} | {d1} | {gate} | {short(reason)} |")
    add()

    # --- 4 ------------------------------------------------------------------------------------
    add("## 4. Does any COMPLETED symbol gain a refusal?")
    add()
    hit_done = sorted({row[0] for row in refused if row[0] in done})
    add(
        f"The crashed run finished **{len(done)}** symbols before it died; their shards are on "
        "disk and are the relaunch's cross-check."
    )
    add()
    if not hit_done:
        add(
            "**None of them gains a refusal.** Every finished shard would reproduce "
            "byte-for-byte under this fix, exactly as it does under the Q-21 fix -- so the "
            "crashed run's 103 shards remain a valid cross-check for the relaunched ledger over "
            "those symbols."
        )
    else:
        add(
            f"**{len(hit_done)} completed symbol(s) DO gain a refusal** -- "
            f"{', '.join(hit_done)} -- so their crashed-run shards are NOT reproducible under "
            "this fix and must not be used as a row-for-row cross-check for those symbols. The "
            "relaunch re-walks every symbol from scratch in any case (the spec digest covers the "
            "code SHA, which this fix moved), so no ledger mixes the two states."
        )
    add()

    # --- 5 ------------------------------------------------------------------------------------
    add("## 5. Does the committed chunk-9A pilot pack move?")
    add()
    add(
        f"The pilot is {', '.join(pe.PILOT_SYMBOLS)} over {pe.PILOT_START} .. {pe.PILOT_END}; its "
        "290 / 146 / 88 / 56 reconciliation is pinned by tests and quoted in three reviews, so a "
        "refusal inside that window would move a published number."
    )
    add()
    pilot_hits = [
        row
        for row in refused
        if row[0] in pe.PILOT_SYMBOLS and pe.PILOT_START <= row[1] <= pe.PILOT_END
    ]
    if not pilot_hits:
        add(
            "**No refusal falls inside the pilot window.** The committed pack's figures are "
            "unaffected by this fix (it gains one zero-valued rare-shape key on a fresh run, "
            "which is the same disclosed staleness decision B249 recorded for Q-21's label)."
        )
    else:
        add("**The pilot window IS touched** -- these rows would move:")
        add()
        for symbol, trade_day, d1, gate, reason in pilot_hits:
            add(f"* {symbol} {trade_day} (D-1 {d1}) -- {gate}")
    add()

    _emit(lines, args.out)
    return 0


def _emit(lines: list[str], out: Path | None) -> None:
    text = "\n".join(lines).rstrip() + "\n"
    if out is None:
        print(text)
        return
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(lines)} lines)")


if __name__ == "__main__":
    raise SystemExit(main())
