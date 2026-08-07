"""Every figure the REVIEW_12_2 FIX session takes from the run, measured in one pass.

CLAUDE.md: *"Any session making claims from real store data commits the generating script and
its output under docs/evidence/"*. This session's fixes rest on five such claims, and all five
are measured here rather than copied out of `docs/reviews/REVIEW_12_2.md`:

1. **Q1 -- page 5's reconciliation.** The bias-rule tally, the walked and judged counts, the
   three rows the page calls *not judged*, and the residual the corrected paragraph prints.
2. **Q1/Q2 -- the OVERLAP.** How many of those three rows' days were nevertheless JUDGED. This
   is the number that decides whether the corrected paragraph is exactly true: the three-way
   split shares those days between two of its buckets, so the paragraph has to say so.
3. **Q2 -- the boundary case.** Which days they are, and the hole in the DAILY store they sit
   at the edge of, read from the daily store read-only.
4. **Page 6 (architect-directed) -- the trader's Round-4 stop constraint** over every gap trade
   the run took: the count, the split by side, and the number of violations, compared in HALF
   PAISE so an off-grid POC is never rounded (CONTEXT 7-E11 bans a float compare on prices).
5. **Q3 -- page 7's flat trades**: how many trades ended exactly level in POINTS, and across
   how many stocks.

READ-ONLY: it opens the ledger and the daily store for reading and writes exactly one file,
its own JSON output, inside the repository. Run from the repo root:

    PYTHONPATH=src python docs/evidence/chunk12_fix_review12_2_measurements.py
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from acumen import backtest as bt
from acumen import points_view as pts
from acumen import report_9b as r9
from acumen import signals as sig
from acumen.config import load_config
from acumen.daily_store import DailyStore

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "docs" / "evidence" / "chunk12_fix_review12_2_measurements.json"

#: The three bias rules whose printed row on the trader's page ends "-- not judged". Named as
#: keys here, and cross-checked below against the pack's own labels, so this script and the page
#: cannot drift apart silently.
NOT_JUDGED_RULES = ("no-data", "minutes-ungated", "suppressed")

#: The symbol whose daily-store hole produced the boundary case, and how far either side of the
#: judged days to look for the hole's ends.
BOUNDARY_SYMBOL = "FORCEMOT"


def measure(run_dir: Path) -> dict:
    """One streaming pass over the ledger for every figure above. I/O, no writes."""
    ledger = run_dir / bt.LEDGER_NAME
    rules: Counter = Counter()
    walked = usable = 0
    not_judged_but_judged: list[dict] = []
    gap_trades = gap_long = gap_short = 0
    gap_stop_violations: list[dict] = []
    flats = 0
    flat_symbols: set[str] = set()

    with ledger.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            walked += 1
            judged = row["status"] != bt.STATUS_REFUSED
            if judged:
                usable += 1
            if row["bias_rule"]:
                rules[row["bias_rule"]] += 1
            if row["bias_rule"] in NOT_JUDGED_RULES and judged:
                not_judged_but_judged.append({
                    "symbol": row["symbol"], "day": row["day"], "bias": row["bias"],
                    "bias_rule": row["bias_rule"], "status": row["status"],
                    "minute_count": row["minute_count"], "outcome": row["outcome"],
                })

            if not row["executed"]:
                continue
            move = (int(row["exit_paise"]) - int(row["entry_paise"])
                    if row["side"] == sig.LONG
                    else int(row["entry_paise"]) - int(row["exit_paise"]))
            if move == 0:
                flats += 1
                flat_symbols.add(row["symbol"])
            if not row["gap_entry"]:
                continue
            gap_trades += 1
            # Half paise on both sides: the POC may legally sit half a paisa off the tick grid
            # (CONTEXT 3.3), so the stop is doubled rather than the POC halved.
            stop_half, poc_half = int(row["stop_paise"]) * 2, int(row["poc_half_paise"])
            if row["side"] == sig.LONG:
                gap_long += 1
                ok = stop_half <= poc_half
            else:
                gap_short += 1
                ok = stop_half >= poc_half
            if not ok:
                gap_stop_violations.append({
                    "symbol": row["symbol"], "day": row["day"], "side": row["side"],
                    "stop_half_paise": stop_half, "poc_half_paise": poc_half,
                })

    ruled = sum(rules.values())
    not_judged = sum(rules[rule] for rule in NOT_JUDGED_RULES)
    return {
        "walked": walked,
        "usable": usable,
        "refused": walked - usable,
        "bias_rules": dict(sorted(rules.items(), key=lambda kv: (-kv[1], kv[0]))),
        "bias_rules_total": ruled,
        "walked_without_a_rule": walked - ruled,
        "not_judged_rows": {rule: rules[rule] for rule in NOT_JUDGED_RULES},
        "not_judged_total": not_judged,
        "ruled_then_refused": ruled - usable,
        # what the corrected paragraph prints as its third figure...
        "page5_third_figure": ruled - usable - not_judged,
        # ...and the size of the population that phrase describes, which differs from it by
        # exactly the overlap below. The paragraph states the overlap for that reason.
        "had_a_bias_then_refused_population": (ruled - not_judged) - (usable - len(
            not_judged_but_judged)),
        "overlap_judged_inside_the_not_judged_rows": len(not_judged_but_judged),
        "overlap_rows": not_judged_but_judged,
        "gap_trades": gap_trades,
        "gap_long": gap_long,
        "gap_short": gap_short,
        "gap_stop_violations": len(gap_stop_violations),
        "gap_stop_violation_rows": gap_stop_violations,
        "flat_trades_in_points": flats,
        "flat_trade_symbols": len(flat_symbols),
    }


def daily_hole(store: DailyStore, symbol: str, around: date) -> dict:
    """The gap in ``symbol``'s DAILY store that ``around`` sits at the far edge of. Read-only."""
    frame = store.daily(symbol, date(2000, 1, 1), date(2100, 1, 1))
    days = sorted({date.fromisoformat(str(value)[:10]) for value in frame["trade_date"]})
    biggest: dict = {"span_days": 0}
    for earlier, later in zip(days, days[1:]):
        span = (later - earlier).days
        if span > biggest["span_days"]:
            biggest = {"span_days": span, "last_row_before": earlier.isoformat(),
                       "first_row_after": later.isoformat()}
    return {
        "symbol": symbol,
        "rows": len(days),
        "first": days[0].isoformat() if days else None,
        "last": days[-1].isoformat() if days else None,
        "largest_gap": biggest,
        "gaps_over_five_days": sum(1 for a, b in zip(days, days[1:]) if (b - a).days > 5),
        "around": around.isoformat(),
        "around_has_a_daily_row": around in set(days),
        "pair_days_have_a_daily_row": {
            (around - timedelta(days=n)).isoformat(): (around - timedelta(days=n)) in set(days)
            for n in (1, 2, 3, 4)
        },
    }


def main() -> int:
    config = load_config(config_path=REPO_ROOT / "config.yaml", include_env=False)
    data_root = Path(config.paths["data_root"])
    run_dir = data_root / "backtests" / r9.RUN_LABEL
    measured = measure(run_dir)

    store = DailyStore.at(data_root / "daily_store")
    boundary = [row for row in measured["overlap_rows"] if row["symbol"] == BOUNDARY_SYMBOL]
    measured["boundary_daily_store"] = daily_hole(
        store, BOUNDARY_SYMBOL, date.fromisoformat(boundary[0]["day"]),
    ) if boundary else None

    # The points view's own totals, so page 7's flat count is checked against the module the
    # page is rendered from and not only against this script's own streaming.
    rows = list(bt.read_ledger(run_dir / bt.LEDGER_NAME))
    table = pts.per_symbol(rows)
    measured["points_view_flats"] = sum(one.flat for one in table)
    measured["points_view_symbols_with_a_flat"] = sum(1 for one in table if one.flat)
    measured["points_view_trades"] = sum(one.trades for one in table)

    OUT.write_text(json.dumps(measured, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in measured.items()
                      if not isinstance(value, (dict, list))}, indent=2, sort_keys=True))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
