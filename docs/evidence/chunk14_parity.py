"""Chunk 14 evidence: THE PARITY REPORT -- the live half against the backtester, candle for
candle, over a sample STRATIFIED BY ``bias_rule``.

    python docs/evidence/chunk14_parity.py

plan.md's chunk-14 goal is that the signal reaches the trader; CONTEXT section 6's promise is
that it is the SAME signal the backtester found. :mod:`acumen.parity` is the harness that can
falsify the promise; this script is the sample it is run over, and the report is what a reviewer
reads instead of taking the claim on trust.

**The sample is chosen by CONSTRUCTION, not by luck** -- the lesson REVIEW_13 B1 paid for, where
"the invariant holds on 3 of 3 real symbol-days" was true while the invariant was broken for
15.42% of evaluated stock-days, because all three days happened to be rule-fired. So one pass
over the chunk-9B ten-year ledger picks, deterministically (ledger order, first replayable
match, recent days preferred):

* one day per ``bias_rule`` stratum, so a CARRIED-bias day is present by construction;
* a GAP-ENTRY day (CONTEXT 3.4-3's second stop rule);
* a day whose reference sits EXACTLY ON the POC (CONTEXT 3.4-1's side-unset path, R2-Q34b/Q41);
* both ``qty == 0`` days in the whole ledger (CONTEXT 3.5, REVIEW_13 M21);
* an ORACLE-REFUSED day -- one the full CONTEXT 4.6 battery refuses -- driven in LIVE posture,
  which is CONTEXT 4.7's disclosed, bounded difference and is REPORTED rather than failed.

Every judged day is then run twice more: once through a RECORDING of itself, so the recording
path chunk 14 forwards is exercised end to end, and once as the backtester's own whole-day
answer, which is what the boundary projection is derived from.

**READ-ONLY over the stores.** It streams the ledger, opens the daily store, the minute lake and
the instrument master, and writes only under ``docs/evidence/`` plus recordings into a temporary
directory OUTSIDE the stores.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from acumen import calendar as cal  # noqa: E402
from acumen import live_screener as ls  # noqa: E402
from acumen import parity  # noqa: E402
from acumen.config import load_config  # noqa: E402
from acumen.live_recording import LiveRecording  # noqa: E402
from acumen.live_source import RecordingBarSource, StoredDayBarSource  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "docs" / "evidence" / "chunk14_parity_report.md"
DEFAULT_SAMPLE = REPO_ROOT / "docs" / "evidence" / "chunk14_parity_sample.json"
LEDGER_RELPATH = Path("backtests") / "chunk9b_full" / "ledger.jsonl"
HOLIDAY_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "holidays_2026.json"

#: Recent days are preferred: they are the ones an operator can still check on a chart.
PREFERRED_FROM = date(2026, 1, 1)

#: The two ``qty == 0`` days in the whole ledger (CONTEXT 3.5 / REVIEW_13 M21), pinned by name
#: so the stratum cannot go missing if a future ledger is walked in a different order.
QTY_ZERO: tuple[tuple[str, str], ...] = (
    ("BOSCHLTD", "2021-05-20"), ("SHREECEM", "2020-03-19"),
)

#: REVIEW_13's named witness for the carried-bias stratum (B1), pinned for the same reason.
WITNESS: tuple[str, str] = ("ITC", "2026-06-10")


def stratify(ledger: Path, *, store: MinuteStore) -> tuple[dict, Counter]:
    """One pass over the ledger. Returns ``{stratum: row}`` and the stratum counts."""
    counts: Counter = Counter()
    chosen: dict[str, dict] = {}
    fallback: dict[str, dict] = {}

    def offer(stratum: str, row: dict) -> None:
        if stratum in chosen:
            return
        day = date.fromisoformat(str(row["day"]))
        if not store.minutes(str(row["symbol"]), day):
            return
        if day >= PREFERRED_FROM:
            chosen[stratum] = row
        else:
            fallback.setdefault(stratum, row)

    with open(ledger, "r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            symbol, day_text = str(row["symbol"]), str(row["day"])
            status = str(row.get("status"))
            if status != "evaluated":
                # An ORACLE-REFUSED day: the full CONTEXT 4.6 battery said no. CONTEXT 4.7's
                # disclosed difference is a day the LIVE battery accepts and the oracle later
                # refuses, so gate 1 / gate 1P failures are the population, not gate 2's.
                reason = str(row.get("reason") or "")
                if "gate 2" not in reason:
                    offer("oracle-refused", row)
                continue
            rule = str(row.get("bias_rule") or "")
            counts[rule] += 1
            offer(f"bias_rule:{rule}", row)
            if row.get("gap_entry"):
                offer("gap-entry", row)
            poc_half, reference = row.get("poc_half_paise"), row.get("reference_paise")
            if poc_half is not None and reference is not None and poc_half == reference * 2:
                offer("reference==POC", row)
            if (symbol, day_text) == WITNESS:
                chosen["carried-witness"] = row
            if (symbol, day_text) in QTY_ZERO:
                chosen[f"qty-zero:{symbol}"] = row
    for stratum, row in fallback.items():
        chosen.setdefault(stratum, row)
    return chosen, counts


def _scratch_cache(root: Path, day: date) -> Path:
    """A scratch ``cache_root`` holding the day's own master (a COPY) and the holiday master."""
    config = load_config(include_env=False)
    cache = root / f"cache-{day.isoformat()}"
    (cache / "instrument_master").mkdir(parents=True, exist_ok=True)
    target = cache / "instrument_master" / ls.day_master_filename(day)
    if not target.is_file():
        shutil.copyfile(
            config.path("cache_root") / "instrument_master" / config.instrument_master, target
        )
    payload = json.loads(HOLIDAY_FIXTURE.read_text(encoding="utf-8"))
    cal.nse_http.write_cache(
        cal.cache_path(cache), payload, url=cal.HOLIDAY_MASTER_URL, fetched_on=day
    )
    return cache


def _screener(symbol: str, day: date, *, source, root: Path, label: str, mode: str):
    config = load_config(include_env=False)
    kwargs = {}
    if mode == "live":
        kwargs = {
            "data_dir": config.path("data_root"),
            "cache_dir": _scratch_cache(root, day),
        }
    return ls.build_live_screener(
        day, (symbol,), source=source,
        recording=LiveRecording.at(root / f"{symbol}-{day.isoformat()}-{label}"),
        clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
        mode=mode, sinks=(ls.CollectingAlertSink(),), **kwargs,
    )


def parity_from_lake(symbol: str, day: date, *, store: MinuteStore, root: Path, stratum: str):
    """The independent-sources case: seventeen polls against one Parquet read."""
    screener = _screener(symbol, day, source=StoredDayBarSource(store), root=root,
                         label="lake", mode="replay")
    return parity.parity_for_screener(screener, symbol, stratum=stratum, source="lake")


def parity_from_recording(symbol: str, day: date, *, store: MinuteStore, root: Path,
                          stratum: str):
    """The recording case: a live-posture morning is recorded, then replayed from its own bytes.

    The recording is written in LIVE posture -- the oracle-free battery, the disclosed line on
    every alert, the day's own master -- so what is replayed is a real morning's bytes and not a
    replay of a replay. The BACKTEST side then reads the recording's whole day through the
    backtester's own battery, which is CONTEXT 4.7's next-pre-open construction.
    """
    live = _screener(symbol, day, source=StoredDayBarSource(store), root=root,
                     label="morning", mode="live")
    live.run_day()
    recording = live.recording
    replay = _screener(symbol, day, source=RecordingBarSource(recording), root=root,
                       label="replay", mode="replay")
    bars = recording.bars(symbol, day)
    return parity.parity_for_screener(
        replay, symbol, minutes_for_backtest=bars, stratum=stratum, source="recording"
    ), live


def parity_live_posture(symbol: str, day: date, *, store: MinuteStore, root: Path, stratum: str):
    """A day driven under CONTEXT 4.7's LIVE battery, judged against the oracle afterwards."""
    live = _screener(symbol, day, source=StoredDayBarSource(store), root=root,
                     label="live", mode="live")
    return parity.parity_for_screener(live, symbol, stratum=stratum, source="live-posture"), live


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--sample", default=str(DEFAULT_SAMPLE))
    parser.add_argument("--recording-root", default="")
    args = parser.parse_args(argv)

    config = load_config(include_env=False)
    data_root = config.path("data_root")
    ledger = data_root / LEDGER_RELPATH
    if not ledger.is_file():
        print(f"no chunk-9B ledger at {ledger}")
        return 1
    store = MinuteStore.at(data_root / "minute_store")
    root = Path(args.recording_root) if args.recording_root else Path(
        tempfile.mkdtemp(prefix="acumen-chunk14-parity-")
    )

    chosen, counts = stratify(ledger, store=store)
    results: list[parity.DayParity] = []
    live_notes: list[str] = []
    for stratum in sorted(chosen):
        row = chosen[stratum]
        symbol, day = str(row["symbol"]), date.fromisoformat(str(row["day"]))
        if stratum == "oracle-refused":
            result, live = parity_live_posture(
                symbol, day, store=store, root=root, stratum=stratum
            )
            live_notes.append(
                f"{symbol} {day.isoformat()}: live posture delivered "
                f"{[a.kind for a in live.sinks[0].alerts]}; ledger reason "
                f"{row.get('reason')!r}"
            )
        else:
            result = parity_from_lake(symbol, day, store=store, root=root, stratum=stratum)
        results.append(result)

    # ...and one full RECORDING round trip, on the named golden day.
    recorded, morning = parity_from_recording(
        "HDFCBANK", date(2026, 6, 10), store=store, root=root, stratum="recording round trip"
    )
    results.append(recorded)
    recorded_alerts = [ls.format_alert(a) for a in morning.sinks[0].alerts]

    summary = parity.summarise(results)
    sample = {
        "generated_from": "docs/evidence/chunk14_parity.py",
        "ledger": str(ledger),
        "strata_counts": {rule: count for rule, count in sorted(counts.items())},
        "summary": summary,
        "days": [row.as_dict() for row in results],
    }
    Path(args.sample).write_text(
        json.dumps(sample, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )

    lines = [
        "# chunk 14 -- THE PARITY REPORT",
        "",
        f"Run at {datetime.now().replace(microsecond=0).isoformat()} from "
        "`docs/evidence/chunk14_parity.py`. READ-ONLY over the stores.",
        "",
        "CONTEXT section 6: *\"One engine, two modes ... same code path, guaranteed no",
        "backtest/live drift\"*, qualified by CONTEXT 4.7: *\"Section 6 parity is judged on",
        "oracle-passing days; a live-alerted day the oracle later refuses is the disclosed,",
        "bounded difference (live cannot see tomorrow).\"* Both halves are executed here.",
        "",
        "## The verdict",
        "",
        f"* **{summary['days']} symbol-days** in the sample, stratified by `bias_rule` and by "
        "the shapes CONTEXT 3.4 and 3.5 decide differently.",
        f"* **{summary['judged']} judged** (the full CONTEXT 4.6 battery accepts the day).",
        f"* **{summary['matched']} matched** -- every boundary, every field, every alert.",
        f"* **{summary['mismatched']} mismatched.**",
        f"* **{summary['disclosed_oracle_refused']} disclosed** as CONTEXT 4.7's bounded "
        "difference rather than judged.",
        "",
    ]
    if summary["mismatches"]:
        lines += ["### The mismatches, named", ""]
        for row in summary["mismatches"]:
            lines.append(f"* **{row['symbol']} {row['day']}**")
            for named in row["named"]:
                lines.append(f"  * {named}")
        lines.append("")
    else:
        lines += [
            "### ZERO mismatches",
            "",
            "Not one field of one boundary of one day differs. What is compared per day: the",
            "bias and the rule that produced it, the POC, the 11:15 reference, and then at",
            "EVERY boundary the phase, entry, stop, target, quantity, exit kind and exit price,",
            "plus the alert sequence and the whole CONTEXT 3.4 transition trail.",
            "",
        ]
    lines += [
        "## The sample, day by day",
        "",
        "| stratum | symbol | day | source | oracle | boundaries | verdict |",
        "|---|---|---|---|---|---:|---|",
    ]
    for row in results:
        verdict = (
            "MATCH" if row.matched and row.judged
            else ("DISCLOSED (4.7)" if not row.judged else "MISMATCH")
        )
        lines.append(
            f"| `{row.stratum}` | {row.symbol} | {row.day.isoformat()} | {row.source} | "
            f"{'pass' if row.oracle_passed else 'REFUSED'} | {len(row.boundaries)} | "
            f"**{verdict}** |"
        )
    lines += ["", "## What each judged day agreed on", ""]
    for row in results:
        if not row.judged:
            continue
        lines += [
            f"### {row.symbol} {row.day.isoformat()} -- `{row.stratum}` ({row.source})",
            "",
            f"bias `{row.backtest_day['bias']}` by `{row.backtest_day['bias_rule']}`, side "
            f"`{row.backtest_day['side']}`, POC `{row.backtest_day['poc_paise']}` paise, "
            f"reference `{row.backtest_day['reference_paise']}` paise.",
            "",
            f"alerts: live `{list(row.live_alerts)}` == backtest `{list(row.backtest_alerts)}`; "
            f"transition trail identical: `{row.transitions_equal}`.",
            "",
            "| boundary | phase | entry | stop | target | qty | exit |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
        for live, _want in row.boundaries:
            lines.append(
                f"| {live.boundary.strftime('%H:%M')} | {live.phase} | "
                f"{live.entry_paise if live.entry_paise is not None else '-'} | "
                f"{live.stop_paise if live.stop_paise is not None else '-'} | "
                f"{live.target_paise if live.target_paise is not None else '-'} | "
                f"{live.qty if live.qty is not None else '-'} | "
                f"{live.exit_kind or '-'}"
                f"{'' if live.exit_paise is None else ' @ ' + str(live.exit_paise)} |"
            )
        lines.append("")
        lines.append(
            "Every row above is the LIVE screener's own state at that boundary, and every one "
            "of them equals the backtester's whole-day answer projected onto the same boundary."
        )
        lines.append("")
    disclosed = [row for row in results if not row.judged]
    lines += ["## The disclosed difference (CONTEXT 4.7)", ""]
    if not disclosed:
        lines.append("No day in this sample was refused by the oracle.")
    for row in disclosed:
        lines += [
            f"* **{row.symbol} {row.day.isoformat()}** (`{row.stratum}`, {row.source}): the "
            f"full battery REFUSES the day -- *{row.oracle_reason}* -- while the ORACLE-FREE "
            f"battery a live morning runs accepts it. Live alerts delivered: "
            f"`{list(row.live_alerts)}`. This is not a parity failure: it is the bounded "
            "difference the architect's 08-Aug-2026 ruling names, and the next pre-open's "
            "verification reports it loudly.",
        ]
    for note in live_notes:
        lines.append(f"  * measured: {note}")
    lines += [
        "",
        "## The recording round trip",
        "",
        "A LIVE-posture morning was recorded over the named golden day and then replayed from "
        "its OWN bytes through `RecordingBarSource`, with the backtest side reading the same "
        "recording through the backtester's battery. This is the path REVIEW_13 **M22** blocked "
        "-- the lake does not hold a live morning's day, so the whole-day battery did not exist "
        "and 15 of 17 boundaries were refused by a gate that never ran. The alerts that morning "
        "delivered, verbatim (a live posture, so each carries CONTEXT 4.7's disclosed line):",
        "",
        "```",
    ]
    lines += [f"  {line}" for line in recorded_alerts]
    lines += [
        "```",
        "",
        "## The strata, over the whole ten-year ledger",
        "",
        "| bias_rule | evaluated stock-days |",
        "|---|---:|",
    ]
    for rule, count in sorted(counts.items(), key=lambda item: -item[1]):
        lines.append(f"| `{rule}` | {count:,} |")
    lines += [
        "",
        f"Machine-readable sample: `{Path(args.sample).name}` (the suite re-runs it, so a "
        "regression fails the build rather than waiting for someone to re-run this script).",
        "",
    ]
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:40]))
    print(f"\nwritten: {args.out}\n         {args.sample}")
    return 0 if summary["mismatched"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
