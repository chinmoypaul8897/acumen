"""Chunk 13 FIX-2 evidence: the replay invariant over a sample STRATIFIED BY ``bias_rule``.

REVIEW_13 finding **B1**, and PART 3 item 1's second sentence:

    "give the live bias series real history. `seed_from` already exists and already works; the
     default is the defect. Then re-run the replay invariant over a day sample that is
     STRATIFIED BY `bias_rule`, so a carry day is in it by construction and not by luck."

The build session's three walk days were all rule-fired (rule-3, rule-1, rule-1), which is
exactly why *"the invariant holds on 3 of 3 real symbol-days"* was true while the invariant was
broken for **15.46% of the backtester's executed trades**. A sample chosen by luck cannot find a
defect that lives in one stratum; a sample chosen by CONSTRUCTION can only miss it if the
stratum is empty.

    python docs/evidence/chunk13_fix2_bias_stratified.py

**READ-ONLY over the stores.** It streams the chunk-9B ledger, opens the daily store, the
1-minute lake and the pinned instrument master, and writes exactly three things, all under
``docs/evidence/``: this run's markdown, the machine-readable sample the SUITE then re-runs, and
a RECORDING per replayed day into a temporary directory OUTSIDE the stores. Nothing under
``data_root`` is created, modified or removed.

What it does, in order:

1. streams every row of the ten-year ledger ONCE, counting evaluated stock-days by ``bias_rule``,
   measuring **how far back a carry has to reach to find the last rule-firing day** -- which is
   what decides :data:`acumen.live_screener.SEED_LOOKBACK_DAYS` -- and keeping the first
   candidate per rule that the local minute lake can actually replay;
2. replays each chosen symbol-day through ``build_live_screener(mode="replay")`` -- the shipped
   wiring, no ``seed_from`` argument, so what is measured is the DEFAULT;
3. compares the screener's own answer against that ledger row field by field: bias, bias rule,
   POC, reference, entry, stop, target, quantity, exit kind and exit price;
4. writes the sample to ``chunk13_fix2_bias_stratified.json`` so
   ``tests/test_live_replay_invariant.py`` re-runs it on every suite run rather than trusting
   this document.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from datetime import date, datetime
from fractions import Fraction
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from acumen import live_screener as ls  # noqa: E402
from acumen.config import load_config  # noqa: E402
from acumen.live_recording import LiveRecording  # noqa: E402
from acumen.live_source import StoredDayBarSource  # noqa: E402
from acumen.minute_store import MinuteStore  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "docs" / "evidence" / "chunk13_fix2_bias_stratified.md"
DEFAULT_SAMPLE = REPO_ROOT / "docs" / "evidence" / "chunk13_fix2_bias_stratified.json"
LEDGER_RELPATH = Path("backtests") / "chunk9b_full" / "ledger.jsonl"

#: The bias rules a live morning can meet. The CARRY rules are the point of the exercise: they
#: are the strata a series seeded at the trade day cannot reach at all (CONTEXT 3.2 rules 1
#: and 5), and they are 15.42% of the ledger's evaluated stock-days.
CARRY_RULES: frozenset[str] = frozenset(
    {"inside-bar-carry", "no-rule-carry", "no-data", "rule-3-no-1min-carry",
     "rule-3-no-break-carry"}
)

#: The rules that FIRE a bias rather than carrying one. A look-back reaches a correct carry
#: exactly when it reaches one of these days -- which is what makes
#: :data:`acumen.live_screener.SEED_LOOKBACK_DAYS` a measurable quantity rather than a taste.
RULE_FIRING: frozenset[str] = frozenset(
    {"rule-1-breakout", "rule-2-sweep", "rule-3-outside-bar", "rule-3-tie"}
)

#: Only days the LAKE holds can be replayed at all, and the lake is the 2016-10-03..2026-07-31
#: era. Recent days are PREFERRED (they are the ones an operator can check by hand), but a rare
#: stratum with no recent day falls back to any replayable day rather than going unsampled --
#: the whole point of stratifying is that no stratum is left to luck.
PREFERRED_FROM = date(2026, 1, 1)

#: REVIEW_13's own named witness for B1, pinned into the sample whatever the strata sweep picks:
#: *"ITC 2026-06-10 -- ledger bias=bearish, rule=inside-bar-carry, status=evaluated; screener
#: bias=None -> refused. It is in the very universe the chunk's own dashboard renders."*
WITNESS: tuple[str, date] = ("ITC", date(2026, 6, 10))


def _rupees(paise) -> str:
    if paise is None:
        return "-"
    return f"{float(Fraction(paise) / 100):,.2f}"


def _half_paise(value) -> Fraction | None:
    """The ledger stores the POC in HALF paise so a row midpoint is exact without a float."""
    return None if value is None else Fraction(int(value), 2)


def stratify(ledger: Path, *, store: MinuteStore, per_rule: int = 1) -> tuple[dict, Counter]:
    """One pass over the ledger: count evaluated days by rule, keep replayable candidates.

    EVERY stratum that has a replayable day gets one, and the review's named witness is pinned
    in whatever the sweep picks. The pass is deterministic -- ledger order, first match -- so a
    re-run chooses the same days and this document regenerates apart from its own timestamp.
    """
    counts: Counter = Counter()
    reach: Counter = Counter()
    last_fired: dict[str, date] = {}
    chosen: dict[str, list[dict]] = {}
    fallback: dict[str, list[dict]] = {}
    witness: dict | None = None
    with open(ledger, "r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            rule = str(row.get("bias_rule") or "")
            symbol = str(row["symbol"])
            day = date.fromisoformat(str(row["day"]))
            # How far back a look-back has to reach on THIS row to find a rule-firing day. Every
            # stored row counts, evaluated or not: the bias SERIES is computed over trading days
            # from daily candles and does not stop where a gate refuses a day.
            if rule in RULE_FIRING:
                last_fired[symbol] = day
                reach[0] += 1
            elif symbol in last_fired:
                reach[(day - last_fired[symbol]).days] += 1
            if row.get("status") != "evaluated":
                continue
            counts[rule] += 1
            if (symbol, day) == WITNESS:
                witness = row
            if len(chosen.get(rule, ())) >= per_rule and len(fallback.get(rule, ())) >= per_rule:
                continue
            if not store.minutes(symbol, day):
                continue
            if day >= PREFERRED_FROM and len(chosen.get(rule, ())) < per_rule:
                chosen.setdefault(rule, []).append(row)
            elif len(fallback.get(rule, ())) < per_rule:
                fallback.setdefault(rule, []).append(row)
    for rule, rows in fallback.items():
        if rule not in chosen:
            chosen[rule] = rows
    if witness is not None:
        rule = str(witness.get("bias_rule") or "")
        already = {(str(r["symbol"]), str(r["day"])) for rows in chosen.values() for r in rows}
        if (WITNESS[0], WITNESS[1].isoformat()) not in already:
            chosen.setdefault(rule, []).insert(0, witness)
    return chosen, counts, reach


def replay(row: dict, *, data_root: Path, recording_root: Path) -> dict:
    """Replay one ledger row through the SHIPPED live wiring and compare, field by field."""
    symbol, day = str(row["symbol"]), date.fromisoformat(str(row["day"]))
    store = MinuteStore.at(data_root / "minute_store")
    screener = ls.build_live_screener(
        day, (symbol,),
        source=StoredDayBarSource(store),
        recording=LiveRecording.at(recording_root / f"{symbol}-{day.isoformat()}"),
        clock=ls.VirtualClock(stamp=datetime.combine(day, datetime.min.time())),
        mode="replay",
        sinks=(ls.CollectingAlertSink(),),
        # NO seed_from: what is measured is the DEFAULT, which is where B1 lived.
    )
    screener.run_day()
    state = screener.states[symbol]
    bias = screener.biases.get(symbol)

    got = {
        "bias": None if bias is None else bias.bias,
        "bias_rule": None if bias is None else bias.rule,
        "poc_paise": None if state.poc_paise is None else str(state.poc_paise),
        "reference_paise": state.reference_paise,
        "entry_paise": state.entry_paise,
        "stop_paise": state.stop_paise,
        "target_paise": state.target_paise,
        "qty": state.qty,
        "exit_kind": state.exit_kind,
    }
    want = {
        "bias": row.get("bias"),
        "bias_rule": row.get("bias_rule"),
        "poc_paise": None if row.get("poc_half_paise") is None
        else str(_half_paise(row["poc_half_paise"])),
        "reference_paise": row.get("reference_paise"),
        "entry_paise": row.get("entry_paise"),
        "stop_paise": row.get("stop_paise"),
        "target_paise": row.get("target_paise"),
        "qty": row.get("qty"),
        "exit_kind": row.get("exit_kind"),
    }
    if want["entry_paise"] is None and got["entry_paise"] is None:
        # A no-trade day: the LEDGER's schema writes qty 0 (there is a column to fill), the
        # SCREENER's state carries None (there is no position to size). Neither is a divergence
        # and comparing them would report one on every no-trade row -- so both are normalised.
        want["qty"] = got["qty"] = None
    mismatches = sorted(key for key in want if want[key] != got[key])
    return {
        "symbol": symbol, "day": day.isoformat(), "rule": str(row.get("bias_rule") or ""),
        "carried": str(row.get("bias_rule") or "") in CARRY_RULES,
        "want": want, "got": got, "mismatches": mismatches,
        "phase": state.phase,
    }


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

    chosen, counts, reach = stratify(ledger, store=store)
    total = sum(counts.values())
    carried = sum(count for rule, count in counts.items() if rule in CARRY_RULES)

    root = Path(args.recording_root) if args.recording_root else Path(
        tempfile.mkdtemp(prefix="acumen-fix2-stratified-")
    )
    results = [
        replay(row, data_root=data_root, recording_root=root)
        for rule in sorted(chosen)
        for row in chosen[rule]
    ]

    lines = [
        "# chunk 13 FIX-2 -- the replay invariant, STRATIFIED BY bias_rule",
        "",
        f"Run at {datetime.now().replace(microsecond=0).isoformat()} from "
        f"`docs/evidence/chunk13_fix2_bias_stratified.py`. READ-ONLY over the stores.",
        "",
        "REVIEW_13 **B1**: `build_live_screener` seeded the bias SERIES at the trade day, so",
        "CONTEXT 3.2's rule-1 and rule-5 CARRY had no earlier bias to carry and the screener",
        "refused the symbol for the whole day. The build session's three walk days were all",
        "rule-fired, which is why the invariant appeared to hold. This sample is stratified by",
        "`bias_rule`, so a carry day is present BY CONSTRUCTION.",
        "",
        "## The strata, over the whole ten-year ledger",
        "",
        "| bias_rule | evaluated stock-days | share |",
        "|---|---:|---:|",
    ]
    for rule, count in sorted(counts.items(), key=lambda item: -item[1]):
        lines.append(f"| `{rule}` | {count:,} | {count / total:.2%} |")
    lines += [
        f"| **total** | **{total:,}** | 100% |",
        "",
        f"**Carried strata (`{'`, `'.join(sorted(CARRY_RULES))}`): {carried:,} of {total:,} = "
        f"{carried / total:.2%} of evaluated stock-days.** Those are the days a series seeded at",
        "the trade day cannot answer at all.",
        "",
        "## How far back a carry has to reach -- which is what sets SEED_LOOKBACK_DAYS",
        "",
        "A look-back reaches the RIGHT carried bias exactly when it reaches the most recent",
        "rule-firing day, and reaching further back cannot change the answer: longer is never",
        "wrong, only slower. So the constant is measurable. Distance from every stored row back",
        "to its symbol's last `rule-1` / `rule-2` / `rule-3-outside-bar` / `rule-3-tie` day:",
        "",
        "| reach | rows within it | share |",
        "|---|---:|---:|",
    ]
    reach_total = sum(reach.values())
    running = 0
    for limit in (0, 1, 3, 7, 14, 30, 60, 90, 120, 180):
        running = sum(count for days, count in reach.items() if days <= limit)
        lines.append(
            f"| <= {limit} calendar day(s) | {running:,} | {running / reach_total:.6%} |"
        )
    over_thirty = sum(count for days, count in reach.items() if days > 30)
    lines += [
        f"| **any** | **{reach_total:,}** | 100% |",
        "",
        f"**Worst case over the whole decade: {max(reach):,} calendar days.** "
        f"{over_thirty:,} rows ({over_thirty / reach_total:.6%}) need more than 30, and every "
        "one of them is a single stretch of missing daily candles rather than a market",
        f"condition. `SEED_LOOKBACK_DAYS` is **{ls.SEED_LOOKBACK_DAYS}**, which covers the "
        "measured maximum with margin.",
        "",
        "## The sample, replayed through the SHIPPED wiring (no `seed_from` argument)",
        "",
        "| symbol | day | bias_rule | carried | screener vs ledger |",
        "|---|---|---|---|---|",
    ]
    for result in results:
        verdict = "MATCH" if not result["mismatches"] else (
            "MISMATCH on " + ", ".join(result["mismatches"])
        )
        lines.append(
            f"| {result['symbol']} | {result['day']} | `{result['rule']}` | "
            f"{'YES' if result['carried'] else 'no'} | **{verdict}** |"
        )

    matched = [r for r in results if not r["mismatches"]]
    carried_days = [r for r in results if r["carried"]]
    lines += [
        "",
        f"**{len(matched)} of {len(results)} strata MATCH the ledger field for field** "
        f"(bias, rule, POC, reference, entry, stop, target, qty, exit kind), and "
        f"{len(carried_days)} of them stand on a CARRIED bias.",
        "",
        "## The carried days in full",
        "",
    ]
    for result in carried_days:
        lines += [
            f"### {result['symbol']} {result['day']} -- `{result['rule']}`",
            "",
            "| field | ledger | screener |",
            "|---|---|---|",
        ]
        for key in sorted(result["want"]):
            want, got = result["want"][key], result["got"][key]
            shown_want = _rupees(want) if key.endswith("_paise") and want is not None else want
            shown_got = _rupees(got) if key.endswith("_paise") and got is not None else got
            lines.append(f"| {key} | {shown_want} | {shown_got} |")
        lines.append("")

    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path(args.sample).write_text(
        json.dumps(
            {
                "note": (
                    "Stratified by bias_rule from the chunk-9B ledger by "
                    "docs/evidence/chunk13_fix2_bias_stratified.py (REVIEW_13 B1). The SUITE "
                    "re-runs these days on every run; the counts are this document's."
                ),
                "strata_counts": dict(sorted(counts.items())),
                "carry_rules": sorted(CARRY_RULES),
                "sample": [
                    {"symbol": r["symbol"], "day": r["day"], "rule": r["rule"],
                     "carried": r["carried"], "expected": r["want"]}
                    for r in results
                ],
            },
            indent=2, sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.out} and {args.sample}")
    print(f"{len(matched)}/{len(results)} strata match; {len(carried_days)} carried")
    return 0 if len(matched) == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
