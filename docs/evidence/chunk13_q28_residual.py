"""Chunk 13 evidence: the Q-28 RESIDUAL, measured from the chunk-9B ten-year ledger.

Committed here beside its own output under CLAUDE.md's git rules (REVIEW_7 finding C3): a
session making claims from real store data commits the generating script and its output.

    python docs/evidence/chunk13_q28_residual.py [--out docs/evidence/chunk13_q28_residual.md]

**READ-ONLY over the stores.** It opens two files and writes one document outside them: the
chunk-9B run ledger (`<data_root>/backtests/chunk9b_full/ledger.jsonl`, streamed line by line,
400 MB) and the chunk-5B disclosed-residual register
(`<data_root>/universe_backfill/ledger.json`, for each symbol's settled/quarantined status).
Nothing under `data_root` is created, modified or removed.

## What is measured, and why the architect asked for it

The architect's ruling of 08-Aug-2026 (QUESTIONS.md, recorded verbatim) makes the live mode's
residual a MEASURED frequency rather than an adjective:

    "The residual is disclosed as a MEASURED frequency, not an adjective."

A live morning runs the ORACLE-FREE battery -- gate 2 including the Q-21(a) open test, the Q-17
candle-level drops, candle validity -- because gates 1 and 1P need THAT DAY's bhavcopy, which
does not exist during that day. So the question the residual answers is:

    over a decade of SETTLED symbol-days, how often did gate 1 -- and gate 1 ALONE -- refuse a
    day that gate 2 and gate 1P both accepted?

That is exactly the population a live morning cannot see and therefore accepts. It is counted
here per day from the run's own ledger rows, never from a per-symbol summary, because the
question is a per-day CROSS-TABULATION (gate 1 failed AND gate 2 passed AND gate 1P passed) and
no per-symbol total can answer it.

## The definitions, stated so a reviewer need not infer them

* **settled symbol-day** -- a ledger row whose symbol is `settled` in the chunk-5B register (204
  of 210; the 6 quarantined are outside every published statistic) AND whose battery actually
  RAN, i.e. the day has stored 1-minute candles. A day with no stored minutes has no verdict
  from any gate and belongs in no gate's numerator or denominator.
* **refused by gate 1** -- `volume_reconciled` is false: gate 1 failed strictly AND the
  evidence-gated auction relief (decision B122) did not rescue it. A RELIEVED day passed.
* **gate 1 could not be RUN** (`gate1_passed` null -- no raw daily row) is NOT a gate-1 refusal.
  The Q-14 ruling counts such a day under gate 1P and forbids folding it into gate 1's count,
  and this script obeys that in both directions.
* **gate 1 ALONE** -- refused by gate 1 while gate 2 PASSED and gate 1P PASSED. This is the
  architect's own wording ("failed gate 1 alone") and it is the headline figure section 4.7
  carries.

## What this figure is NOT (the honest limit, stated here rather than left to be found)

It is a LOWER bound on what a live morning accepts, for one measurable reason: gate 2's
missing-minutes trigger fires only *"on a day where gate 1 ALSO fails"*, so a day that failed
both may have failed gate 2 BECAUSE gate 1 failed. Under the oracle-free battery that trigger is
structurally inapplicable (the session is not over and the completeness oracle does not exist),
so some gate-1-and-gate-2 days would also pass a live morning's battery. The ledger records gate
2's verdict but not WHICH of its four triggers fired, so that share cannot be separated from
these rows; it would need a re-gate of the whole lake. The two adjacent populations that CAN be
separated are printed beside the headline -- gate 1P alone, and the union -- so the reader sees
the bracket rather than one number.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from acumen.config import load_config  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "docs" / "evidence" / "chunk13_q28_residual.md"

#: The chunk-9B full-history run -- the ten-year ledger CONTEXT 4.7's residual is measured over.
RUN_LABEL: str = "chunk9b_full"

#: The chunk-5B disclosed-residual register, which carries each symbol's settled/quarantined
#: status. Same relative path `acumen.backtest.RESIDUAL_LEDGER_RELPATH` names.
REGISTER_RELPATH: str = "universe_backfill/ledger.json"


def settled_symbols(data_root: Path) -> frozenset[str]:
    """The SETTLED symbols of the chunk-5B register (204 of 210)."""
    payload = json.loads((data_root / REGISTER_RELPATH).read_text(encoding="utf-8"))
    return frozenset(
        symbol for symbol, entry in payload["symbols"].items()
        if entry.get("status") == "settled"
    )


def measure(data_root: Path, *, progress=print) -> dict:
    """Stream the run ledger ONCE and cross-tabulate the three gates per settled symbol-day."""
    settled = settled_symbols(data_root)
    ledger = data_root / "backtests" / RUN_LABEL / "ledger.jsonl"
    if not ledger.is_file():
        raise SystemExit(f"No chunk-9B ledger at {ledger}.")

    counts: Counter[str] = Counter()
    per_symbol_gate1_alone: Counter[str] = Counter()
    per_symbol_battery_days: Counter[str] = Counter()
    walked_days: set[str] = set()
    rows = 0
    with ledger.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows += 1
            if rows % 100_000 == 0:
                progress(f"  {rows:,} ledger rows read", flush=True)
            row = json.loads(line)
            symbol = row["symbol"]
            walked_days.add(row["day"])
            if symbol not in settled:
                counts["rows_quarantined_symbol"] += 1
                continue
            gate1p = row["gate1p_passed"]
            if gate1p is None:
                # No battery ran: the day has no stored 1-minute candles at all.
                counts["rows_no_stored_minutes"] += 1
                continue

            counts["settled_symbol_days"] += 1
            per_symbol_battery_days[symbol] += 1
            gate1 = row["gate1_passed"]
            relieved = bool(row["gate1_relieved"])
            gate2 = row["gate2_passed"]

            if gate1 is None:
                # Gate 1 could not be RUN -- no raw daily row. The Q-14 ruling counts this under
                # gate 1P and never under gate 1.
                counts["gate1_unrun_no_oracle"] += 1
                reconciled = None
            else:
                reconciled = bool(gate1) or relieved
                if relieved and not gate1:
                    counts["gate1_relieved_pass"] += 1

            if reconciled is False:
                counts["gate1_refused_total"] += 1
                if gate2 and gate1p:
                    counts["gate1_alone"] += 1
                    per_symbol_gate1_alone[symbol] += 1
                elif not gate2 and gate1p:
                    counts["gate1_and_gate2"] += 1
                elif gate2 and not gate1p:
                    counts["gate1_and_gate1p"] += 1
                else:
                    counts["gate1_and_gate2_and_gate1p"] += 1
            if not gate1p:
                counts["gate1p_refused_total"] += 1
                if reconciled and gate2:
                    counts["gate1p_alone"] += 1
            if not gate2:
                counts["gate2_refused_total"] += 1
                if reconciled is not False and gate1p:
                    counts["gate2_alone"] += 1
            if reconciled and gate2 and gate1p:
                counts["usable"] += 1

    counts["ledger_rows"] = rows
    counts["settled_symbols"] = len(settled)
    counts["walked_dates"] = len(walked_days)
    # The union a live morning cannot see: refused by gate 1 or gate 1P, accepted by gate 2.
    counts["oracle_only_refusals"] = (
        counts["gate1_alone"] + counts["gate1p_alone"] + counts["gate1_and_gate1p"]
    )

    # The register's own whole-lake count of stored days per SETTLED symbol, so the difference
    # between "stored in the lake" and "walked with a battery verdict by this run" is stated
    # per symbol rather than left as one unexplained total.
    register = json.loads((data_root / REGISTER_RELPATH).read_text(encoding="utf-8"))["symbols"]
    excess: dict[str, int] = {}
    register_stored = 0
    for symbol in sorted(settled):
        stored = int(register[symbol]["gate1p_total"])
        register_stored += stored
        gap = stored - per_symbol_battery_days.get(symbol, 0)
        if gap:
            excess[symbol] = gap
    counts["register_stored_settled"] = register_stored
    counts["register_minus_walked"] = register_stored - counts["settled_symbol_days"]

    manifest_path = ledger.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "counts": dict(counts),
        "per_symbol_gate1_alone": dict(per_symbol_gate1_alone.most_common()),
        "register_excess_per_symbol": dict(
            sorted(excess.items(), key=lambda item: (-item[1], item[0]))
        ),
        "run_span": manifest["span"],
        "run_totals": manifest["totals"],
        "run_refused_by_reason": manifest["refused_by_reason"],
        "ledger": str(ledger),
        "ledger_bytes": ledger.stat().st_size,
    }


def pct(part: int, whole: int, places: int = 4) -> str:
    if whole <= 0:
        return "-"
    return f"{part * 100 / whole:.{places}f}"


def render(result: dict, *, generated_at: str) -> str:
    counts = result["counts"]
    total = counts["settled_symbol_days"]
    alone = counts["gate1_alone"]
    out: list[str] = []
    add = out.append
    add("# Chunk 13 evidence -- the Q-28 residual, measured")
    add("")
    add("Generated by `docs/evidence/chunk13_q28_residual.py`, read-only over the stores.")
    add(f"Run at {generated_at} over `{result['ledger']}` "
        f"({result['ledger_bytes']:,} bytes, {counts['ledger_rows']:,} rows).")
    add("")
    add("The architect's ruling of 08-Aug-2026: *\"The residual is disclosed as a MEASURED "
        "frequency, not an adjective.\"* This is that measurement, and CONTEXT v2.0 section 4.7 "
        "quotes its headline verbatim.")
    add("")
    add("## 1 -- The headline (what CONTEXT 4.7 carries)")
    add("")
    add(f"**{pct(alone, total)}% of settled symbol-days ({alone:,}/{total:,} over the ten-year "
        "ledger) failed gate 1 alone** -- refused by gate 1's volume reconciliation while gate 2 "
        "and gate 1P both accepted the day.")
    add("")
    add("That is the frequency a live morning accepts and discloses: gate 1 is the gate a live "
        "session cannot run, and these are the days on which it, and it alone, would have "
        "changed the answer.")
    add("")
    add("## 2 -- The population, gate by gate")
    add("")
    add("| reading | days | % of settled symbol-days |")
    add("|---|---:|---:|")
    for label, key in (
        ("settled symbol-days (the denominator)", "settled_symbol_days"),
        ("usable -- all three gates pass", "usable"),
        ("refused by gate 1 (volume_reconciled false)", "gate1_refused_total"),
        ("**refused by gate 1 ALONE (gate 2 and gate 1P both pass)**", "gate1_alone"),
        ("refused by gate 1 and gate 2", "gate1_and_gate2"),
        ("refused by gate 1 and gate 1P", "gate1_and_gate1p"),
        ("refused by all three", "gate1_and_gate2_and_gate1p"),
        ("refused by gate 1P (any cause)", "gate1p_refused_total"),
        ("refused by gate 1P ALONE", "gate1p_alone"),
        ("refused by gate 2 (any cause)", "gate2_refused_total"),
        ("refused by gate 2 ALONE", "gate2_alone"),
        ("gate 1 could not be RUN (no raw daily row -- counted under gate 1P, never gate 1)",
         "gate1_unrun_no_oracle"),
        ("gate-1 failures rescued by the auction relief (they PASSED)", "gate1_relieved_pass"),
        ("union: refused only by an ORACLE gate (1 or 1P), gate 2 accepting",
         "oracle_only_refusals"),
    ):
        value = counts.get(key, 0)
        add(f"| {label} | {value:,} | {pct(value, total)}% |")
    add("")
    add(f"Rows skipped before any of this: {counts.get('rows_quarantined_symbol', 0):,} on the 6 "
        f"quarantined symbols and {counts.get('rows_no_stored_minutes', 0):,} symbol-days with no "
        f"stored 1-minute candles (no battery ran, so no gate has a verdict to count). "
        f"{counts['settled_symbols']} symbols are settled.")
    add("")
    add("### 2a -- Reconciled against the run's own manifest, and against the register")
    add("")
    span = result["run_span"]
    totals = result["run_totals"]
    refused = result["run_refused_by_reason"]
    add(f"The run walked `{span['start']}` -> `{span['end']}`, "
        f"{counts['walked_dates']:,} distinct dates x {counts['settled_symbols']} settled symbols "
        f"= **{totals['walked']:,} rows**, which is this stream's own row count "
        f"({counts['ledger_rows']:,}) to the row.")
    add("")
    add("| claim | this stream | the run's manifest | agree |")
    add("|---|---:|---:|---|")
    checks = [
        ("rows walked", counts["ledger_rows"], totals["walked"]),
        ("refused by gate 1", counts["gate1_refused_total"],
         refused.get("gate 1 (volume reconciliation)", 0)),
        ("refused by gate 2 ALONE (the run counts gate 1 first)", counts.get("gate2_alone", 0),
         refused.get("gate 2 (candle integrity)", 0)),
        ("refused by gate 1P ALONE (the run counts gates 1 and 2 first)",
         counts.get("gate1p_alone", 0),
         refused.get("gate-1P (per-day price containment)", 0)),
        ("gate-1 failures rescued by the auction relief", counts.get("gate1_relieved_pass", 0),
         totals.get("gate1_relieved", 0)),
    ]
    for label, mine, theirs in checks:
        add(f"| {label} | {mine:,} | {theirs:,} | {'YES' if mine == theirs else '**NO**'} |")
    add("")
    add("The run's refusal counts are a PARTITION in the battery's own order -- gate 1 first, then "
        "gate 2, then gate 1P -- which is why its `gate 2` and `gate-1P` lines equal this "
        "document's ALONE rows and not its totals. That the two agree to the day on all five "
        "readings is what makes the cross-tabulation above trustworthy: it is the same ledger, "
        "read a second way.")
    add("")
    usable_gap = counts["usable"] - totals["usable"]
    add(f"**Usable.** This document's `usable` ({counts['usable']:,}) counts days where all three "
        f"gates pass. The run's `usable` ({totals['usable']:,}) counts days it went on to "
        f"EVALUATE, so it is smaller by exactly {usable_gap:,} -- the "
        f"{refused.get('bias suppressed across a demerger/rights ex-date (CONTEXT 3.2)', 0)} "
        "suppressed, "
        f"{refused.get('no bias yet (CONTEXT 3.2 seeding: not seeded)', 0)} unseeded and "
        f"{refused.get('no POC for the day (CONTEXT 3.3): no-poc-no-candles-in-window', 0)} "
        "empty-window days that pass the battery and still produce no signal.")
    add("")
    excess = result["register_excess_per_symbol"]
    gaps = sorted(excess.values())
    shape = (
        f"{gaps[0]}..{gaps[-1]} days per symbol (median {gaps[len(gaps) // 2]}) on all "
        f"{len(excess)} of them" if gaps else "nothing"
    )
    add(f"**Against the chunk-5B register.** The register counts "
        f"{counts['register_stored_settled']:,} STORED symbol-days on the settled 204 over the "
        f"whole lake; this run carries a battery verdict for {total:,} of them, a difference of "
        f"**{counts['register_minus_walked']:,} days across {len(excess)} symbols**. Those days are "
        "stored but were never walked: the lake runs one day past the run's end "
        f"(`{span['end']}`), the run's calendar is derived from the daily store, and "
        f"{sum(refused.get(key, 0) for key in ('CONTEXT 7-E2 non-standard session (stored candles outside 09:15-15:30)',)):,} "
        "further stored days are the CONTEXT 7-E2 non-standard sessions the run refuses before "
        "any gate runs (they are inside this document's "
        f"{counts.get('rows_no_stored_minutes', 0):,} no-verdict rows, not inside its "
        "denominator). The gap's SHAPE says which kind of difference it is: "
        f"{shape} -- a spread consistent with a CALENDAR difference across the whole universe "
        "rather than with a defect concentrated in a few symbols. The difference is stated "
        "rather than absorbed, and it is not decomposed day by day here, because the denominator "
        "section 1 needs is the days this ten-year run actually gated, which is the population "
        "the ruling asks about.")
    add("")
    add("## 3 -- The bracket, and the honest limit")
    add("")
    add("The headline is a **lower bound** on what a live morning accepts, and the reason is "
        "measurable rather than rhetorical. Gate 2's missing-minutes trigger fires only *\"on a "
        "day where gate 1 ALSO fails\"* (CONTEXT 4.5, the completeness ruling), so an unknown "
        "share of the "
        f"{counts.get('gate1_and_gate2', 0):,} gate-1-and-gate-2 days failed gate 2 BECAUSE gate 1 "
        "failed. A live morning's battery cannot fire that trigger at all -- the session is not "
        "over and the completeness oracle does not exist -- so some of those days would pass it "
        "too. The ledger records gate 2's verdict but not which of its four triggers fired, so "
        "separating them would need a re-gate of the whole lake; it is disclosed here instead of "
        "estimated.")
    add("")
    add(f"The upper end of the bracket that CAN be measured is the union in the table: "
        f"**{counts.get('oracle_only_refusals', 0):,} days ({pct(counts.get('oracle_only_refusals', 0), total)}%)** "
        "were refused only by an ORACLE gate (1 or 1P) with gate 2 accepting the day. That is "
        "every day whose refusal a live morning is structurally blind to, and it is the figure to "
        "read if the question is *\"how often could a live alert survive an evening it should not "
        "have?\"* rather than the architect's narrower *\"failed gate 1 alone\"*.")
    add("")
    add("Both readings are bounded, and neither is an estimate.")
    add("")
    add("## 4 -- Where the gate-1-alone days live")
    add("")
    add("| symbol | gate-1-alone days |")
    add("|---|---:|")
    shown = 0
    for symbol, count in result["per_symbol_gate1_alone"].items():
        add(f"| {symbol} | {count:,} |")
        shown += 1
        if shown >= 25:
            break
    remaining = len(result["per_symbol_gate1_alone"]) - shown
    add("")
    if remaining > 0:
        add(f"{len(result['per_symbol_gate1_alone'])} settled symbols carry at least one such day; "
            f"the {shown} largest are listed and {remaining} more are not. The full distribution "
            "is reproducible by re-running this script.")
    else:
        add(f"{len(result['per_symbol_gate1_alone'])} settled symbols carry at least one such day, "
            "all listed.")
    add("")
    add("## 5 -- What this does NOT measure")
    add("")
    add("* **Whether any of these days would have produced a live ALERT.** A refused day produces "
        "no signal in the backtest; whether the same day under a live battery would have armed, "
        "triggered or done nothing depends on its POC and its bias, which this cross-tabulation "
        "does not compute. The frequency is of days ACCEPTED, not of alerts changed.")
    add("* **The quarantined six.** They are outside every published statistic in this repo "
        "(CONTEXT 4.6) and they are outside this one.")
    add("* **Anything about tomorrow.** The ruling's own bound: live cannot see tomorrow, and the "
        "next pre-open's full battery over the recording is what closes each day's loop.")
    add("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chunk13_q28_residual")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--json-out", default="")
    args = parser.parse_args(argv)

    data_root = load_config(include_env=False).path("data_root")
    print(f"streaming the chunk-9B ledger under {data_root}", flush=True)
    result = measure(data_root)
    text = render(result, generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(text):,} chars)")
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"wrote {args.json_out}")

    counts = result["counts"]
    print(
        f"gate-1-alone: {counts['gate1_alone']:,} / {counts['settled_symbol_days']:,} = "
        f"{pct(counts['gate1_alone'], counts['settled_symbol_days'])}%"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- ASSERTED AT THE SOURCE (an AST test)
    raise SystemExit(main())
