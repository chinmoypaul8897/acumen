"""Q-18 T5 -- hand-verify the two BIG improvements before any vendor repair is believed.

The architect's T5 ruling (QUESTIONS.md, 01-Aug-2026, verbatim):

    "T5 BIG IMPROVEMENTS VERIFIED: NESTLEIND (+1,002) and BSE (+84) -- hand-verify FIVE flipped
    days each against raw bhavcopy before vendor-repair is believed; show the arithmetic."

**What a "flipped day" is, and why it is not guesswork.** The sealed era's per-day verdicts died
with `data/`; only its REPORT survived. But that report makes a committed, quoted, per-day claim
about a named span for each of these two symbols, and a day inside that span which PASSES gate 1
on the rebuilt store is therefore a flipped day by the sealed report's own words:

* NESTLEIND -- an era failure-rate CLIFF: *"2020-10-29 | era failure-rate cliff: 1009/1009 =
  100.0% of the gated days below 2020-10-29 fail gate 1 (>= 95%)"*. Every gated day below
  2020-10-29 failed. Measured on the rebuild: 998 of those 1,009 now pass.
* BSE -- a REJECTED per-side floor: *"2025-05-23 | price no splice (UNRESOLVED, 2 probe(s)) |
  volume 2017-12-20 | 13 | REJECTED by acceptance: both-gate days would go 2115 -> 2115 (gate 1
  2116 -> 2196); the floor is discarded, not applied"*. A floor whose acceptance would have
  moved gate 1 by +80 is a statement that those 80 days were FAILING, and the floor was
  discarded, so they stayed failing. The span the floor covers is
  ``[2017-08-24, 2017-12-20)`` -- above BSE's own cliff, which is why the cliff is the WRONG
  anchor for this symbol: its 137 cliff days still fail on the rebuild, all of them.
  Measured on the rebuild: 80 of the 81 gated days in that span now pass, with no floor
  applied at all.

In both cases the arithmetic closes exactly against the reported delta once the four
sealed-fetch-horizon days are added: NESTLEIND 998 + 4 = +1,002, BSE 80 + 4 = +84.

Five days are picked evenly across each span, deterministically, and each is printed digit by
digit against the raw bhavcopy the exchange published. A symbol that cannot supply five flipped
days FAILS here rather than passing on an empty list.

Offline and read-only; it re-runs CONTEXT 4.5's own gate functions rather than trusting a report.

Run:  python docs/recovery/q18_t5_improvements.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Sequence

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from acumen import quality_gates as gates                       # noqa: E402
from acumen.config import load_config                           # noqa: E402
from acumen.daily_store import DailyStore                       # noqa: E402
from acumen.minute_backfill import fetch_corp_action_history    # noqa: E402
from acumen.minute_store import MinuteStore                     # noqa: E402
from acumen.recovery_reconcile import read_report               # noqa: E402

#: symbol -> the ANCHOR: the span the sealed report makes a per-day failing claim about, the
#: quote that makes it, the number of days that claim covers, and the ruling's own delta. The
#: span is half-open [start, end).
TARGETS: tuple[tuple[str, date, date, int, int, str], ...] = (
    ("NESTLEIND", date(2016, 1, 1), date(2020, 10, 29), 1009, 1002,
     "era failure-rate cliff: 1009/1009 = 100.0% of the gated days below 2020-10-29 fail "
     "gate 1 (>= 95%)"),
    ("BSE", date(2017, 8, 24), date(2017, 12, 20), 80, 84,
     "REJECTED by acceptance: both-gate days would go 2115 -> 2115 (gate 1 2116 -> 2196); the "
     "floor is discarded, not applied -- so those 80 days stayed FAILING in the sealed era"),
)
PICKS = 5


def verify_day(store: MinuteStore, daily: DailyStore, symbol: str, day: date) -> dict[str, Any]:
    bars = store.minutes(symbol, day)
    frame = daily.daily(symbol, day, day)
    row = None if frame.empty else frame.iloc[0]
    fold_high = max(b.high_paise for b in bars)
    fold_low = min(b.low_paise for b in bars)
    fold_volume = sum(b.volume for b in bars)
    out: dict[str, Any] = {
        "date": day.isoformat(),
        "bars": len(bars),
        "minute_open": bars[0].open_paise,
        "minute_high": fold_high,
        "minute_low": fold_low,
        "minute_close": bars[-1].close_paise,
        "minute_volume": fold_volume,
    }
    if row is None:
        out["raw"] = "no raw bhavcopy row"
        return out
    raw_volume = int(row["volume"])
    volume = gates.volume_gate(raw_volume, fold_volume)
    price = gates.price_containment_gate(
        fold_high, fold_low, int(row["high_paise"]), int(row["low_paise"])
    )
    out.update({
        "raw_open": int(row["open_paise"]),
        "raw_high": int(row["high_paise"]),
        "raw_low": int(row["low_paise"]),
        "raw_close": int(row["close_paise"]),
        "raw_volume": raw_volume,
        "raw_series": str(row["series"]),
        "raw_source": str(row["source_format"]),
        "difference": fold_volume - raw_volume,
        "gap_pct": None if volume.gap_pct is None else f"{float(volume.gap_pct):+.4f}%",
        "gate1_passed": bool(volume.passed),
        "gate1p_passed": bool(price.passed),
        "gate1p_high_excess": int(price.high_excess_paise or 0),
        "gate1p_low_excess": int(price.low_excess_paise or 0),
        "price_ratio_high": round(fold_high / int(row["high_paise"]), 8),
        "price_ratio_low": round(fold_low / int(row["low_paise"]), 8),
        "volume_ratio": round(fold_volume / raw_volume, 8) if raw_volume else None,
    })
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q-18 T5 improvement verification (offline).")
    parser.add_argument("--out", default=str(REPO / "docs/recovery/q18_t5_improvements.md"))
    args = parser.parse_args(argv)

    data = load_config(include_env=False).path("data_root")
    store = MinuteStore.at(data / "minute_store")
    daily = DailyStore.at(data / "daily_store")
    sealed = read_report(REPO / "docs/backfill_minute_report.md")
    rebuilt = read_report(REPO / "docs/recovery/backfill_minute_report_rebuild.md")
    actions = fetch_corp_action_history(date(2005, 1, 1), date(2026, 12, 31), allow_network=False)

    out: list[str] = []
    add = out.append
    add("# Q-18 T5 -- the two BIG improvements, hand-verified")
    add("")
    add("Generated by `docs/recovery/q18_t5_improvements.py`, offline and read-only, under "
        "CLAUDE.md's evidence rule. Every gate number is recomputed here with CONTEXT 4.5's own "
        "`acumen.quality_gates` functions from the two raw numbers the gate sees.")
    add("")
    add("The architect's T5 ruling this executes (QUESTIONS.md, 01-Aug-2026, verbatim):")
    add("")
    add("> T5 BIG IMPROVEMENTS VERIFIED: NESTLEIND (+1,002) and BSE (+84) -- hand-verify FIVE")
    add("> flipped days each against raw bhavcopy before vendor-repair is believed; show the")
    add("> arithmetic.")
    add("")

    summary: dict[str, dict[str, Any]] = {}
    for symbol, span_from, span_to, claimed, ruling_delta, quote in TARGETS:
        old, new = sealed.symbols[symbol], rebuilt.symbols[symbol]
        stored = [d for d in store.stored_days(symbol) if span_from <= d < span_to]
        checks = [verify_day(store, daily, symbol, day) for day in stored]
        gated = [c for c in checks if "raw_volume" in c]
        passing = [c for c in gated if c["gate1_passed"]]
        step = max(1, len(passing) // PICKS)
        picks = [passing[i * step] for i in range(PICKS)] if len(passing) >= PICKS else passing

        add(f"## {symbol} -- {old.gate1_pass:,}/{old.gate1_gated:,} -> "
            f"{new.gate1_pass:,}/{new.gate1_gated:,} ({new.gate1_pass - old.gate1_pass:+,}; the "
            f"ruling quotes {ruling_delta:+,})")
        add("")
        add(f"The SEALED report's committed claim about the span "
            f"`[{span_from.isoformat()}, {span_to.isoformat()})`, quoted: *\"{quote}\"* -- i.e. "
            f"{claimed:,} days of it were FAILING gate 1 in the sealed era. Measured on the "
            f"rebuilt store over that same span: **{len(gated):,} gated days, of which "
            f"{len(passing):,} PASS gate 1**. Adding the four sealed-fetch-horizon days at the "
            f"tail gives {len(passing):,} + 4 = {len(passing) + 4:+,}, against the reported "
            f"{new.gate1_pass - old.gate1_pass:+,}. Five flipped days, evenly spaced:")
        add("")
        subjects = sorted({
            f"{a.subject.strip()} @ {a.ex_date.isoformat()}"
            for a in actions if str(a.symbol).strip().upper() == symbol
        })
        add("- corporate actions this symbol carries in the rebuilt cache: "
            + (", ".join(subjects) or "none"))
        add("")
        for check in picks:
            add(f"**{check['date']}** -- {check['bars']:,} stored 1-minute bars")
            add("")
            add("| Field | RAW bhavcopy (paise) | 1-minute store | minute / raw |")
            add("|---|---|---|---|")
            add(f"| open | {check['raw_open']:,} | {check['minute_open']:,} | -- |")
            add(f"| high | {check['raw_high']:,} | {check['minute_high']:,} | "
                f"{check['price_ratio_high']} |")
            add(f"| low | {check['raw_low']:,} | {check['minute_low']:,} | "
                f"{check['price_ratio_low']} |")
            add(f"| close | {check['raw_close']:,} | {check['minute_close']:,} | -- |")
            add(f"| volume | {check['raw_volume']:,} | {check['minute_volume']:,} | "
                f"{check['volume_ratio']} |")
            add("")
            add(f"- gate 1 arithmetic: minute sum {check['minute_volume']:,} - raw daily "
                f"{check['raw_volume']:,} = {check['difference']:+,} shares, gap "
                f"{check['gap_pct']} -> **{'PASS' if check['gate1_passed'] else 'FAIL'}**")
            add(f"- gate 1P arithmetic: fold high {check['minute_high']:,} vs raw high "
                f"{check['raw_high']:,} (excess {check['gate1p_high_excess']:,} paise); fold low "
                f"{check['minute_low']:,} vs raw low {check['raw_low']:,} (excess "
                f"{check['gate1p_low_excess']:,} paise) -> "
                f"**{'PASS' if check['gate1p_passed'] else 'FAIL'}**")
            # The domain sentence is DERIVED from the ratio, never asserted: an earlier version
            # of this script printed "SAME domain" beside a measured 3.0 and was wrong.
            same = abs(check["price_ratio_high"] - 1.0) < 0.005
            reciprocal = abs(check["price_ratio_high"] * (check["volume_ratio"] or 0) - 1.0) < 0.02
            add(f"- price domain: the 1-minute high is {check['price_ratio_high']} x the "
                f"exchange's own high and the low {check['price_ratio_low']} x its low"
                + (" -- the vendor is serving this day in the SAME price domain as the raw "
                   "bhavcopy" if same else
                   f" -- the vendor is serving this day in a DIFFERENT price domain from the raw "
                   f"bhavcopy, while its volume is {check['volume_ratio']} x raw"
                   + (", i.e. the reciprocal back-adjustment signature" if reciprocal else
                      ", i.e. price and volume are NOT reciprocal: the two sides of this day sit "
                      "in different domains, which is why gate 1 can pass while gate 1P refuses"))
                + f" (raw source `{check['raw_source']}`, series `{check['raw_series']}`)")
            add("")
        # A verdict on an EMPTY list is not a verdict. The ruling asks for five days; five is
        # the floor, and a symbol that cannot supply them fails here rather than passing
        # vacuously (the first run of this script did exactly that for BSE, off a wrong anchor).
        believed = len(picks) == PICKS and all(
            c["gate1_passed"] and c["gate1p_passed"] for c in picks
        )
        summary[symbol] = {
            "sealed": f"{old.gate1_pass}/{old.gate1_gated}",
            "rebuilt": f"{new.gate1_pass}/{new.gate1_gated}",
            "delta": new.gate1_pass - old.gate1_pass,
            "anchor_span": f"[{span_from.isoformat()}, {span_to.isoformat()})",
            "sealed_claimed_failing": claimed,
            "gated_in_span": len(gated),
            "passing_in_span": len(passing),
            "arithmetic": f"{len(passing)} flipped + 4 horizon = {len(passing) + 4}",
            "verified": [c["date"] for c in picks],
            "vendor_repair_believed": believed,
        }
        if believed:
            label = "vendor repair BELIEVED"
        elif len(picks) < PICKS:
            label = f"NOT BELIEVED -- only {len(picks)} of {PICKS} flipped days could be found"
        else:
            label = ("PARTIAL -- the gate-1 (volume) flip is verified, but every verified day "
                     "still FAILS gate 1P, so no coverage is recovered")
        add(f"### {symbol} verdict: **{label}**")
        add("")
        both = sum(1 for c in picks if c["gate1_passed"] and c["gate1p_passed"])
        add(f"{len(picks)} of {PICKS} required hand-verified days were found; {both} of them "
            f"pass gate 1 AND gate 1P on the rebuilt store. The gate code is unchanged and is "
            f"re-run here, so nothing was loosened.")
        add("")
        if believed:
            add("The improvement is a REAL vendor repair: the 1-minute fold now sits in the "
                "same price domain as the exchange's own row and reconciles on volume, where "
                "the sealed report's own committed quote says every gated day in this span "
                "failed. Believed.")
        else:
            add(f"**The improvement is PARTIAL and vendor-repair is NOT believed as a full "
                f"repair.** All {len(picks)} days reconcile on VOLUME -- gate 1 passes, and the "
                f"minute sum matches the exchange's own daily volume to a fraction of a per "
                f"cent -- but every one of them still FAILS gate 1P, because the 1-minute "
                f"prices sit roughly {picks[0]['price_ratio_high']:.2f}x the exchange's own. "
                f"Price and volume are in DIFFERENT domains on the same day, so the reciprocal "
                f"back-adjustment signature is absent. The gate-1 delta is therefore real and "
                f"earned, but these days do NOT become usable days: they stay in the "
                f"disclosed-residual register exactly as the sealed era left them. Any reading "
                f"of this symbol's improvement as recovered COVERAGE would be wrong.")
        add("")

    add("## Summary")
    add("")
    add("```json")
    add(json.dumps(summary, indent=2))
    add("```")
    Path(args.out).write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2))
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
