"""Q-18 T3 -- REGRESSION FORENSICS for the four symbols the rebuild made WORSE.

The architect's T3 ruling (QUESTIONS.md, 01-Aug-2026, verbatim):

    "T3 REGRESSION FORENSICS (APLAPOLLO -467, GAIL -60, POWERGRID -23, LODHA -21): for each --
    (a) failing dates listed by era and by gate; (b) rebuilt adjustment-map events and floors
    diffed against every sealed-era review quote available; (c) correlate with the CA-cache
    delta (41,351 -> 41,371: name the new rows for these symbols); (d) hand-verify THREE failing
    days per symbol against raw bhavcopy, digit by digit. Outcome per symbol: a measured,
    era-keyed explanation (class vendor-snapshot-drift -- days honestly refused by the gates,
    disclosed) or ESCALATE to the architect with the evidence. No third option."

This script produces (a)-(d) by MEASUREMENT. It is offline and read-only: it re-runs CONTEXT
4.5's own gate battery (``acumen.universe_backfill.gate_symbol``, the reviewed code that wrote
the report's numbers) over the rebuilt store, reads the SEALED era's quotes out of the COMMITTED
``docs/backfill_minute_report.md``, and reads the corporate-action day-cache offline.

It writes two files:

* ``docs/recovery/q18_t3_forensics.md``   -- the evidence, for the architect to read;
* ``docs/recovery/q18_t3_forensics.json`` -- the per-symbol verdicts the reconciliation consumes.
  ``src/acumen/recovery_reconcile.py`` reads ONLY this file for the ``vendor-snapshot-drift``
  class, so a symbol is reclassified by evidence on disk or not at all.

Run:  python docs/recovery/q18_t3_forensics.py

ERRATUM (05-Aug-2026, chunk-9B REPORT session, closing REVIEW_9B_PRESEAL finding Q3)
------------------------------------------------------------------------------------
The triage session's own summary of this pack said each regression's 1-minute fold "sits at an
EXACT corporate-action factor from the raw bhavcopy". **"EXACT" overstates two of the six
hand-verified days and is withdrawn.** POWERGRID 2021-07-29 really is 4/3 on the high; 2021-08-16
measures 1.333424 and 2021-09-06 measures 1.333428. That is not drift and not a defect: a day's
fold extremes are the max/min of per-minute prices ALREADY rounded to the paisa, so exact equality
with a rational factor cannot be expected of them and was never what the verdict rested on. What
the verdict rests on is the RECIPROCAL price x volume signature, which this pack prints per day
and which holds tightly (0.999794 .. 0.999979 across the three POWERGRID days, 0.984 .. 0.999 on
APLAPOLLO's larger factors). **No verdict, class or number in this pack or in
`q18_reconciliation.md` moves**; the correction is to the WORD. The claim never appeared in the
generated `.md` or `.json` -- it was made in the session narrative (STATUS.md's superseded
2026-08-02 triage entry), which now carries the same erratum. This docstring is not emitted into
either output file, so the pack still regenerates byte-identically.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from acumen import quality_gates as gates                       # noqa: E402
from acumen.config import load_config                           # noqa: E402
from acumen.daily_store import DailyStore                       # noqa: E402
from acumen.minute_backfill import fetch_corp_action_history    # noqa: E402
from acumen.minute_store import MinuteStore                     # noqa: E402
from acumen.recovery_reconcile import (MEASURE_PASSING, MEASURE_STATUS,  # noqa: E402
                                       VERDICT_DRIFT, VERDICT_ESCALATE, read_report)
from acumen.universe_backfill import build_daily_cache, gate_symbol  # noqa: E402

#: The four regressions the ruling names, with the delta it quotes. Measured against these.
TARGETS: tuple[tuple[str, int], ...] = (
    ("APLAPOLLO", -467),
    ("GAIL", -60),
    ("POWERGRID", -23),
    ("LODHA", -21),
)

#: The day-cache the destroyed era held was fetched on this date (QUESTIONS.md Q-18 incident
#: table: "data/nse/ca/ ... fetched_on 2026-07-29"). Rows with an ex-date after it are rows the
#: sealed era's cache could not have carried in its forward window.
SEALED_CA_FETCHED_ON: date = date(2026, 7, 29)
SEALED_CA_ROWS: int = 41_351

#: A failing block this long or longer, ending at an era boundary, is a STEP rather than noise.
MIN_BLOCK: int = 10
#: How near an ex-date a block's edge must land to count as "abutting" it, in calendar days.
ABUT_DAYS: int = 7

#: THE DRIFT TEST, stated before the data is looked at so the verdict cannot be fitted to it.
#: A symbol earns `vendor-snapshot-drift` only if EVERY clause holds; otherwise it ESCALATES.
DRIFT_TEST = (
    "1. three failing days were hand-verified (the ruling's own count); "
    "2. every one of them carries a raw bhavcopy row that is internally SOUND "
    "(low <= open/close <= high, volume > 0), so the gate had a valid oracle to refuse against; "
    "3. every one of them genuinely fails at least one gate by a measurable margin; "
    "4. the failures form a CONTIGUOUS block of stored days at least as long as the regression "
    f"itself and at least {MIN_BLOCK} days long -- a step, not scatter; "
    "5. that block starts the symbol's stored history or abuts one of its own corporate-action "
    f"ex-dates (within {ABUT_DAYS} calendar days) -- i.e. it is ERA-KEYED; "
    "6. at least one hand-verified day shows the reciprocal price/volume signature of a "
    "corporate-action back-adjustment (price / k, volume * k), which is the OPEN-8 fingerprint "
    "of the vendor serving that era in a different domain."
)


def _fmt(day: date | None) -> str:
    return day.isoformat() if day else "--"


def era_bounds(ex_dates: Sequence[date], first: date, last: date) -> list[tuple[date, date, str]]:
    """The symbol's own eras: half-open spans cut at its corporate-action ex-dates."""
    cuts = sorted({d for d in ex_dates if first <= d <= last})
    spans: list[tuple[date, date, str]] = []
    start = first
    for cut in cuts:
        spans.append((start, cut - timedelta(days=1), f"< {cut.isoformat()}"))
        start = cut
    spans.append((start, last, f">= {cuts[-1].isoformat()}" if cuts else "whole history"))
    return [(a, b, label) for a, b, label in spans if a <= b]


def contiguous_blocks(days: Sequence[date], failing: Iterable[date]) -> list[tuple[int, int]]:
    """Maximal runs of failing days, as (start index, end index) into the stored-day list."""
    index = {day: i for i, day in enumerate(days)}
    marks = sorted(index[d] for d in failing if d in index)
    blocks: list[tuple[int, int]] = []
    for position in marks:
        if blocks and position == blocks[-1][1] + 1:
            blocks[-1] = (blocks[-1][0], position)
        else:
            blocks.append((position, position))
    return blocks


def sealed_quotes(text: str, symbol: str) -> list[str]:
    """Every committed SEALED-report line that names this symbol -- the era's own words."""
    pattern = re.compile(r"(^\|\s*" + re.escape(symbol) + r"\s*\|)|(\b" + re.escape(symbol)
                         + r"\b.{0,6}(fail|era|floor|quarant|residual|cluster))")
    return [line.strip() for line in text.splitlines() if pattern.search(line)]


def hand_verify(store: MinuteStore, daily: DailyStore, symbol: str, day: date,
                fold: tuple[int, int, int]) -> dict[str, Any]:
    """One failing day, digit by digit: the raw bhavcopy row against the 1-minute fold."""
    frame = daily.daily(symbol, day, day)
    row = None if frame.empty else frame.iloc[0]
    bars = store.minutes(symbol, day)
    fold_high, fold_low, fold_volume = fold
    out: dict[str, Any] = {
        "date": day.isoformat(),
        "minute_bars": len(bars),
        "minute_open_paise": bars[0].open_paise if bars else None,
        "minute_high_paise": fold_high,
        "minute_low_paise": fold_low,
        "minute_close_paise": bars[-1].close_paise if bars else None,
        "minute_volume": fold_volume,
    }
    if row is None:
        out["raw"] = "NO RAW BHAVCOPY ROW -- gate 1 cannot run and gate 1P fails with no oracle"
        return out
    out.update({
        "raw_series": str(row["series"]),
        "raw_open_paise": int(row["open_paise"]),
        "raw_high_paise": int(row["high_paise"]),
        "raw_low_paise": int(row["low_paise"]),
        "raw_close_paise": int(row["close_paise"]),
        "raw_volume": int(row["volume"]),
        "raw_source": str(row["source_format"]),
    })
    # Is the exchange's own row internally sound? If it is not, the gate is not the suspect.
    out["raw_row_sound"] = bool(
        int(row["low_paise"]) <= int(row["open_paise"]) <= int(row["high_paise"])
        and int(row["low_paise"]) <= int(row["close_paise"]) <= int(row["high_paise"])
        and int(row["volume"]) > 0
    )
    # The gate arithmetic, recomputed here from the same two numbers the gate saw.
    volume = gates.volume_gate(int(row["volume"]), fold_volume)
    price = gates.price_containment_gate(
        fold_high, fold_low, int(row["high_paise"]), int(row["low_paise"])
    )
    out["gate1_gap_pct"] = None if volume.gap_pct is None else f"{float(volume.gap_pct):+.4f}%"
    out["gate1_passed"] = volume.passed
    out["gate1p_passed"] = price.passed
    out["gate1p_cause"] = price.cause
    out["gate1p_high_excess_paise"] = int(price.high_excess_paise or 0)
    out["gate1p_low_excess_paise"] = int(price.low_excess_paise or 0)
    # The price/volume DOMAIN test: a back-adjusted snapshot divides price by k and multiplies
    # volume by k, so the two ratios are reciprocal. That is the OPEN-8 signature, measured.
    price_ratio = fold_high / int(row["high_paise"]) if int(row["high_paise"]) else None
    volume_ratio = fold_volume / int(row["volume"]) if int(row["volume"]) else None
    out["price_ratio_minute_over_raw"] = None if price_ratio is None else round(price_ratio, 6)
    out["volume_ratio_minute_over_raw"] = None if volume_ratio is None else round(volume_ratio, 6)
    if price_ratio and volume_ratio:
        out["reciprocal_product"] = round(price_ratio * volume_ratio, 6)
        out["domain_signature"] = (
            "PRICE-DOMAIN mismatch with the reciprocal volume signature of a corporate-action "
            "back-adjustment (price / k, volume * k)"
            if abs(price_ratio * volume_ratio - 1.0) < 0.02 and abs(price_ratio - 1.0) > 0.02
            else "no reciprocal signature"
        )
    return out


def measure(symbol: str, expected_delta: int, store: MinuteStore, daily: DailyStore,
            cache: Any, register: dict, sealed_text: str, sealed_facts, rebuilt_facts,
            actions: Sequence[Any]) -> dict[str, Any]:
    tally = gate_symbol(store, cache, symbol)
    stored = sorted(tally.folds)
    entry = register[symbol]
    ex_dates = sorted({date.fromisoformat(e["ex_date"]) for e in entry.get("map_events", ())})

    gate1_failing = sorted(day for day, _gap, _volume in tally.gate1_failures)
    gate1p_failing = sorted(day for day, _cause in tally.gate1p_failures)
    causes = dict(tally.gate1p_failures)

    old = sealed_facts.symbols[symbol]
    new = rebuilt_facts.symbols[symbol]
    measured_delta = new.gate1_pass - old.gate1_pass

    spans = era_bounds(ex_dates, stored[0], stored[-1]) if stored else []
    eras = []
    for start, end, label in spans:
        span_days = [d for d in stored if start <= d <= end]
        gated = [d for d in tally.gate1_days if start <= d <= end]
        eras.append({
            "era": label,
            "from": _fmt(start),
            "to": _fmt(end),
            "stored": len(span_days),
            "gate1_gated": len(gated),
            "gate1_failing": sum(1 for d in gate1_failing if start <= d <= end),
            "gate1p_failing": sum(1 for d in gate1p_failing if start <= d <= end),
            "gate1p_above": sum(1 for d in gate1p_failing
                                if start <= d <= end and causes[d] == gates.GATE1P_ABOVE),
            "gate1p_below": sum(1 for d in gate1p_failing
                                if start <= d <= end and causes[d] == gates.GATE1P_BELOW),
            "gate1p_no_oracle": sum(1 for d in gate1p_failing
                                    if start <= d <= end and causes[d] == gates.GATE1P_NO_ORACLE),
        })

    union = sorted(set(gate1_failing) | set(gate1p_failing))
    blocks = contiguous_blocks(stored, union)
    ranked = sorted(blocks, key=lambda b: b[1] - b[0], reverse=True)
    def abuts(first: date, last: date) -> bool:
        """An ex-date inside the block, or within ABUT_DAYS after its last failing day.

        The second shape is the one an adjustment error leaves behind: every day BEFORE the
        ex-date sits in the wrong price domain and the days from the ex-date on are clean.
        """
        return any(first <= d <= last + timedelta(days=ABUT_DAYS) for d in ex_dates)

    block_rows = [
        {
            "from": _fmt(stored[a]), "to": _fmt(stored[b]), "length": b - a + 1,
            "starts_history": a == 0,
            "abuts_ex_date": abuts(stored[a], stored[b]),
        }
        for a, b in ranked[:6]
    ]
    biggest = ranked[0] if ranked else None
    biggest_len = (biggest[1] - biggest[0] + 1) if biggest else 0

    # (d) three failing days, chosen deterministically from the largest block.
    picks: list[date] = []
    if biggest:
        a, b = biggest
        picks = [stored[a], stored[(a + b) // 2], stored[b]]
    elif union:
        picks = union[:3]
    hands = [hand_verify(store, daily, symbol, day, tally.folds[day]) for day in picks]

    # (c) the corporate-action cache, this symbol's rows.
    rows = [a for a in actions if str(a.symbol).strip().upper() == symbol]
    fresh = [a for a in rows if a.ex_date > SEALED_CA_FETCHED_ON]

    # The measured drift test, exactly as DRIFT_TEST states it above. Rule-based, so the verdict
    # is not a matter of taste and cannot be fitted to what the numbers turned out to be.
    sound = [h for h in hands if h.get("raw_row_sound")]
    refused = [h for h in hands
               if h.get("gate1_passed") is False or h.get("gate1p_passed") is False]
    domain = [h for h in hands if str(h.get("domain_signature", "")).startswith("PRICE-DOMAIN")]
    era_keyed = bool(block_rows) and (block_rows[0]["starts_history"]
                                      or block_rows[0]["abuts_ex_date"])
    clauses = {
        "1. three days hand-verified": len(hands) == 3,
        "2. every raw bhavcopy row internally sound": bool(hands) and len(sound) == len(hands),
        "3. every hand-verified day really fails a gate": bool(hands)
        and len(refused) == len(hands),
        "4. one contiguous block >= the regression and >= "
        f"{MIN_BLOCK} days": biggest_len >= abs(measured_delta) and biggest_len >= MIN_BLOCK,
        "5. that block is ERA-KEYED": era_keyed,
        "6. the back-adjustment domain signature is present": len(domain) >= 1,
    }
    drift = all(clauses.values())

    return {
        "symbol": symbol,
        "ruling_delta": expected_delta,
        "measured_delta": measured_delta,
        "sealed": f"{old.gate1_pass:,}/{old.gate1_gated:,}",
        "rebuilt": f"{new.gate1_pass:,}/{new.gate1_gated:,}",
        "sealed_days": old.days,
        "rebuilt_days": new.days,
        "sealed_status": old.status,
        "rebuilt_status": new.status,
        "status_moved": old.status != new.status,
        "stored_first": _fmt(stored[0] if stored else None),
        "stored_last": _fmt(stored[-1] if stored else None),
        "gate1_gated": tally.gate1_total,
        "gate1_pass_strict": tally.gate1_pass,
        "gate1_relieved": tally.gate1_relieved,
        "gate1_effective": tally.gate1_effective_pass,
        "gate1_failing": len(gate1_failing),
        "gate1p_total": tally.gate1p_total,
        "gate1p_pass": tally.gate1p_pass,
        "gate1p_above": tally.gate1p_above,
        "gate1p_below": tally.gate1p_below,
        "gate1p_no_oracle": tally.gate1p_no_oracle,
        "gate1p_worst_excess": tally.gate1p_worst_excess,
        "gate2_excluded": tally.gate2_excluded,
        "eras": eras,
        "blocks": block_rows,
        "biggest_block": biggest_len,
        "hands": hands,
        "rebuilt_map_events": sorted({f"{e['kind']}@{e['ex_date']}: "
                                      f"{e['price_source']}/{e['volume_source']}"
                                      for e in entry.get("map_events", ())}),
        "rebuilt_floor_signatures": entry.get("floor_signatures", []),
        "rebuilt_floor_findings": entry.get("floor_findings", []),
        "rebuilt_floor_note": entry.get("floor_note", ""),
        "rebuilt_floors_resolved": entry.get("floors_resolved", 0),
        "rebuilt_era_failure_rates": entry.get("era_failure_rates", []),
        "rebuilt_failure_pattern": entry.get("failure_pattern", ""),
        "rebuilt_failure_detail": entry.get("failure_detail", ""),
        "sealed_quotes": sealed_quotes(sealed_text, symbol),
        "ca_rows": len(rows),
        "ca_new_rows": [f"{a.subject.strip()} @ {a.ex_date.isoformat()}" for a in fresh],
        "drift_test": drift,
        "drift_clauses": clauses,
    }


def render(findings: Sequence[dict], verdicts: dict[str, str], ca_rows: int) -> str:
    out: list[str] = []
    add = out.append
    add("# Q-18 T3 -- REGRESSION FORENSICS")
    add("")
    add("Generated by `docs/recovery/q18_t3_forensics.py`, offline and read-only, under "
        "CLAUDE.md's evidence rule.")
    add("The gate numbers below are not copied from any report: CONTEXT 4.5's own battery")
    add("(`acumen.universe_backfill.gate_symbol`) was re-run here over the rebuilt store.")
    add("")
    add("The architect's T3 ruling this executes (QUESTIONS.md, 01-Aug-2026, verbatim):")
    add("")
    add("> for each -- (a) failing dates listed by era and by gate; (b) rebuilt adjustment-map")
    add("> events and floors diffed against every sealed-era review quote available; (c)")
    add("> correlate with the CA-cache delta (41,351 -> 41,371: name the new rows for these")
    add("> symbols); (d) hand-verify THREE failing days per symbol against raw bhavcopy, digit")
    add("> by digit. Outcome per symbol: a measured, era-keyed explanation (class")
    add("> vendor-snapshot-drift -- days honestly refused by the gates, disclosed) or ESCALATE")
    add("> to the architect with the evidence. No third option.")
    add("")
    add("## 0. Verdicts")
    add("")
    add("| Symbol | Ruling delta | MEASURED delta | Rebuilt gate-1 | Verdict |")
    add("|---|---|---|---|---|")
    for item in findings:
        add(f"| {item['symbol']} | {item['ruling_delta']:+,} | {item['measured_delta']:+,} | "
            f"{item['rebuilt']} | **{verdicts[item['symbol']]}** |")
    add("")
    add("The DRIFT TEST every verdict above was decided by, stated before the data was read:")
    add("")
    for clause in DRIFT_TEST.split("; "):
        add(f"- {clause.strip().rstrip('.')}")
    add("")
    add("| Symbol | " + " | ".join(f"clause {i}" for i in range(1, 7)) + " |")
    add("|---|" + "---|" * 6)
    for item in findings:
        add(f"| {item['symbol']} | "
            + " | ".join("PASS" if v else "**FAIL**"
                         for v in item["drift_clauses"].values()) + " |")
    add("")
    add(f"The rebuilt corporate-action day-cache holds **{ca_rows:,}** rows against the sealed "
        f"era's **{SEALED_CA_ROWS:,}** (+{ca_rows - SEALED_CA_ROWS}). The sealed cache itself "
        "was destroyed with the rest of `data/` (Q-18 incident), so a row-level diff of the two "
        "caches is impossible and is NOT claimed here. What IS available and is used instead: "
        "the SEALED report's own committed map inventory, which records every corporate action "
        "that era actually applied per symbol, and the rebuilt cache's rows whose ex-date falls "
        f"after the sealed cache's `fetched_on` of {SEALED_CA_FETCHED_ON.isoformat()}.")
    add("")

    for item in findings:
        symbol = item["symbol"]
        add(f"## {symbol} -- {item['sealed']} -> {item['rebuilt']} "
            f"({item['measured_delta']:+,})")
        add("")
        add(f"Stored {item['stored_first']} .. {item['stored_last']}; sealed report days "
            f"{item['sealed_days']:,}, rebuilt {item['rebuilt_days']:,}. Re-measured here: "
            f"gate 1 gated {item['gate1_gated']:,}, strict pass {item['gate1_pass_strict']:,}, "
            f"auction relief {item['gate1_relieved']:,}, EFFECTIVE "
            f"{item['gate1_effective']:,}; gate 1P {item['gate1p_pass']:,}/"
            f"{item['gate1p_total']:,} (above {item['gate1p_above']:,}, below "
            f"{item['gate1p_below']:,}, no-oracle {item['gate1p_no_oracle']:,}, worst excess "
            f"{item['gate1p_worst_excess']:,} paise); gate 2 excluded "
            f"{item['gate2_excluded']:,}.")
        add("")
        add("### (a) Failing dates by ERA and by GATE")
        add("")
        add("| Era | From | To | Stored | Gate-1 gated | Gate-1 FAIL | Gate-1P FAIL | 1P above "
            "| 1P below | 1P no-oracle |")
        add("|---|---|---|---|---|---|---|---|---|---|")
        for era in item["eras"]:
            add(f"| `{era['era']}` | {era['from']} | {era['to']} | {era['stored']:,} | "
                f"{era['gate1_gated']:,} | {era['gate1_failing']:,} | "
                f"{era['gate1p_failing']:,} | {era['gate1p_above']:,} | "
                f"{era['gate1p_below']:,} | {era['gate1p_no_oracle']:,} |")
        add("")
        add("Contiguous blocks of failing stored days (longest first) -- a STEP, not scatter, "
            "is what a differently-adjusted vendor snapshot leaves behind:")
        add("")
        add("| From | To | Length | Starts the stored history | Abuts an ex-date |")
        add("|---|---|---|---|---|")
        for block in item["blocks"]:
            add(f"| {block['from']} | {block['to']} | {block['length']:,} | "
                f"{'YES' if block['starts_history'] else 'no'} | "
                f"{'YES' if block['abuts_ex_date'] else 'no'} |")
        add("")
        add("### (b) Rebuilt map events and floors, against the SEALED era's own quotes")
        add("")
        add(f"- rebuilt map events: {', '.join(item['rebuilt_map_events']) or 'none'}")
        add(f"- rebuilt floors resolved: {item['rebuilt_floors_resolved']}")
        add(f"- rebuilt floor note: {item['rebuilt_floor_note'] or '--'}")
        add(f"- rebuilt failure pattern: {item['rebuilt_failure_pattern']} -- "
            f"{item['rebuilt_failure_detail']}")
        add(f"- rebuilt era failure rates: {'; '.join(item['rebuilt_era_failure_rates']) or '--'}")
        for line in item["rebuilt_floor_signatures"]:
            add(f"- rebuilt floor signature: {line}")
        for line in item["rebuilt_floor_findings"]:
            add(f"- rebuilt floor finding: {line}")
        add("")
        add("Every line the COMMITTED sealed report carries for this symbol (the sealed-era "
            "quotes the ruling asks this to be diffed against):")
        add("")
        for line in item["sealed_quotes"]:
            add(f"- `{line}`")
        add("")
        add("### (c) Corporate-action cache correlation")
        add("")
        add(f"- rows for {symbol} in the rebuilt cache: **{item['ca_rows']}**")
        add(f"- of those, ex-date AFTER the sealed cache's fetch date "
            f"({SEALED_CA_FETCHED_ON.isoformat()}): "
            f"{', '.join(item['ca_new_rows']) if item['ca_new_rows'] else '**none**'}")
        add("")
        add("### (d) THREE failing days, hand-verified against the raw bhavcopy")
        add("")
        for hand in item["hands"]:
            add(f"**{hand['date']}**")
            add("")
            if "raw_open_paise" not in hand:
                add(f"- {hand['raw']}")
                add("")
                continue
            add("| Field | RAW bhavcopy (paise) | 1-minute store | ratio minute/raw |")
            add("|---|---|---|---|")
            add(f"| open | {hand['raw_open_paise']:,} | {hand['minute_open_paise']:,} | -- |")
            add(f"| high | {hand['raw_high_paise']:,} | {hand['minute_high_paise']:,} | "
                f"{hand['price_ratio_minute_over_raw']} |")
            add(f"| low | {hand['raw_low_paise']:,} | {hand['minute_low_paise']:,} | -- |")
            add(f"| close | {hand['raw_close_paise']:,} | {hand['minute_close_paise']:,} | -- |")
            add(f"| volume | {hand['raw_volume']:,} | {hand['minute_volume']:,} | "
                f"{hand['volume_ratio_minute_over_raw']} |")
            add("")
            add(f"- raw row: series `{hand['raw_series']}`, source `{hand['raw_source']}`, "
                f"internally sound (low <= open/close <= high, volume > 0): "
                f"**{'YES' if hand['raw_row_sound'] else 'NO'}**")
            add(f"- {hand['minute_bars']:,} stored 1-minute bars that day")
            add(f"- gate 1 (volume reconciliation): gap {hand['gate1_gap_pct']} -> "
                f"{'PASS' if hand['gate1_passed'] else 'FAIL'}")
            add(f"- gate 1P (price containment): {'PASS' if hand['gate1p_passed'] else 'FAIL'}"
                f", cause `{hand['gate1p_cause']}`, high excess "
                f"{hand['gate1p_high_excess_paise']:,} paise, low excess "
                f"{hand['gate1p_low_excess_paise']:,} paise")
            add(f"- price x volume ratio product = {hand.get('reciprocal_product')} -> "
                f"{hand.get('domain_signature')}")
            add("")
        add(f"### Verdict: **{verdicts[symbol]}**")
        add("")
        add("")
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q-18 T3 regression forensics (offline).")
    parser.add_argument("--out", default=str(REPO / "docs/recovery/q18_t3_forensics.md"))
    parser.add_argument("--json", default=str(REPO / "docs/recovery/q18_t3_forensics.json"))
    args = parser.parse_args(argv)

    data = load_config(include_env=False).path("data_root")
    store = MinuteStore.at(data / "minute_store")
    daily = DailyStore.at(data / "daily_store")
    register = json.loads((data / "universe_backfill" / "ledger.json").read_text("utf-8"))["symbols"]
    sealed_text = (REPO / "docs/backfill_minute_report.md").read_text(encoding="utf-8")
    sealed_facts = read_report(REPO / "docs/backfill_minute_report.md")
    rebuilt_facts = read_report(REPO / "docs/recovery/backfill_minute_report_rebuild.md")

    symbols = [s for s, _ in TARGETS]
    print(f"reading the raw daily store for {symbols} ...", flush=True)
    cache = build_daily_cache(daily, symbols, date(2015, 1, 1), date(2026, 12, 31))
    print(f"  cached {sum(len(v) for v in cache.by_symbol.values()):,} symbol-days", flush=True)
    actions = fetch_corp_action_history(date(2005, 1, 1), date(2026, 12, 31), allow_network=False)
    print(f"  {len(actions):,} corporate-action rows (offline)", flush=True)

    findings = []
    for symbol, delta in TARGETS:
        print(f"re-gating {symbol} over its whole stored history ...", flush=True)
        findings.append(measure(symbol, delta, store, daily, cache, register, sealed_text,
                                sealed_facts, rebuilt_facts, actions))
        item = findings[-1]
        print(f"  {symbol}: measured {item['measured_delta']:+,}, biggest failing block "
              f"{item['biggest_block']:,} days, drift test "
              f"{'PASS' if item['drift_test'] else 'FAIL'}", flush=True)

    verdicts = {
        item["symbol"]: (VERDICT_DRIFT if item["drift_test"] else VERDICT_ESCALATE)
        for item in findings
    }
    payload = {
        "generated_by": "docs/recovery/q18_t3_forensics.py",
        "ruling": "QUESTIONS.md, ARCHITECT'S TRIAGE RULINGS (01-Aug-2026), T3",
        "ca_rows_rebuilt": len(actions),
        "ca_rows_sealed": SEALED_CA_ROWS,
        "symbols": {
            item["symbol"]: {
                "verdict": verdicts[item["symbol"]],
                # A quarantine follows MECHANICALLY from the gate-1 pass rate crossing 80%, so
                # a symbol whose status moved has its status divergence named too -- otherwise
                # the reconciliation would explain the cause and leave the consequence dangling.
                "measures": ([MEASURE_PASSING] + ([MEASURE_STATUS] if item["status_moved"] else [])
                             if verdicts[item["symbol"]] == VERDICT_DRIFT else []),
                "summary": (
                    f"{item['sealed']} -> {item['rebuilt']} ({item['measured_delta']:+,}); the "
                    f"failures form a contiguous block of {item['biggest_block']:,} stored days "
                    f"({item['blocks'][0]['from']}..{item['blocks'][0]['to']}) keyed to this "
                    f"symbol's own eras, every hand-verified day carries a SOUND raw bhavcopy "
                    f"row, and the 1-minute fold sits in a different price domain with the "
                    f"reciprocal volume signature of a corporate-action back-adjustment"
                ) if verdicts[item["symbol"]] == VERDICT_DRIFT else (
                    f"{item['sealed']} -> {item['rebuilt']} ({item['measured_delta']:+,}); the "
                    f"forensics could not produce a measured, era-keyed explanation"
                ),
            }
            for item in findings
        },
    }
    Path(args.json).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8",
                               newline="\n")
    Path(args.out).write_text(render(findings, verdicts, len(actions)) + "\n", encoding="utf-8",
                              newline="\n")
    print(f"\nwrote {args.out}\nwrote {args.json}")
    for symbol, verdict in verdicts.items():
        print(f"  {symbol}: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
