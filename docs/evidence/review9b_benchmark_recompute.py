"""REVIEW_9B_REPORT: CONTEXT 7-E13's buy&hold benchmark, both readings, re-derived.

Written by the chunk-9B REPORT REVIEW session (06-Aug-2026), after the architect's Q-23 ruling
made the SHARE-COUNT-ADJUSTED construction THE benchmark. It imports nothing from `src/acumen`:
the bhavcopy parquet is read with pandas, the equal-weight construction is re-implemented from
E13's own words, and the share-count factors are read from the run manifest's own factor table.

    python docs/evidence/review9b_benchmark_recompute.py

Read-only over the stores. Writes exactly one markdown file inside the repo.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA_ROOT = Path("C:/Users/chinm/acumen-data")
RUN_DIR = DATA_ROOT / "backtests" / "chunk9b_full"
DAILY = DATA_ROOT / "daily_store" / "daily"
OUT = REPO / "docs" / "evidence" / "review9b_benchmark_recompute.md"

CAPITAL_PAISE = 10_000_000
FIRST_DAY = date(2016, 10, 3)
LAST_DAY = date(2026, 7, 30)
INSTRUMENT_SERIES = ("EQ", "BE", "BZ")


def money(paise) -> str:
    """Round-half-up to the paisa, then print. A Fraction is rounded, never truncated."""
    value = Fraction(paise)
    q, r = divmod(abs(value.numerator), value.denominator)
    if r * 2 >= value.denominator:
        q += 1
    sign = "-" if value < 0 else ""
    whole, frac = divmod(q, 100)
    return f"{sign}Rs {whole:,}.{frac:02d}"


def pct(value: Fraction, places: int = 2) -> str:
    scaled = value * 100 * (10**places)
    q, r = divmod(abs(scaled.numerator), scaled.denominator)
    if r * 2 >= scaled.denominator:
        q += 1
    text = f"{q:0{places + 1}d}"
    body = f"{int(text[:-places]):,}.{text[-places:]}"
    return ("-" if scaled.numerator < 0 else "") + body + "%"


def month_frame(day: date) -> pd.DataFrame:
    path = DAILY / f"{day.year:04d}" / f"bhavcopy_{day.year:04d}-{day.month:02d}.parquet"
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_parquet(path, columns=["symbol", "series", "trade_date", "close_paise"])


def main() -> int:
    manifest = json.loads((RUN_DIR / "manifest.json").read_bytes().decode("utf-8"))
    symbols = sorted(manifest["universe"])
    per_symbol = manifest["factor_table"]["per_symbol"]

    # --- the two closes each symbol needs -------------------------------------------------
    first = month_frame(FIRST_DAY)
    first = first[
        (first["trade_date"] == FIRST_DAY) & (first["series"].isin(INSTRUMENT_SERIES))
    ]
    first_close = {
        str(r.symbol): int(r.close_paise) for r in first.itertuples() if str(r.symbol) in set(symbols)
    }

    last_close: dict[str, tuple[date, int]] = {}
    probe = LAST_DAY
    seen: set[str] = set()
    while len(seen) < len(symbols) and probe >= FIRST_DAY:
        frame = month_frame(probe)
        if not frame.empty:
            frame = frame[
                (frame["trade_date"] <= LAST_DAY)
                & (frame["trade_date"] >= FIRST_DAY)
                & (frame["series"].isin(INSTRUMENT_SERIES))
                & (frame["symbol"].isin(symbols))
            ]
            for symbol, group in frame.groupby("symbol"):
                symbol = str(symbol)
                if symbol in seen:
                    continue
                row = group.sort_values("trade_date").iloc[-1]
                last_close[symbol] = (row["trade_date"], int(row["close_paise"]))
                seen.add(symbol)
        probe = probe.replace(day=1) - timedelta(days=1)
        if probe < date(2016, 1, 1):
            break

    usable = sorted(s for s in symbols if s in first_close and s in last_close)
    skipped = sorted(set(symbols) - set(usable))

    # --- the factors -----------------------------------------------------------------------
    # THREE tallies, because the generator's single tally mixes two different animals: a bonus,
    # split or rights issue changes a HOLDER'S SHARE COUNT, while a special dividend does not --
    # it is a cash payment the price drops by. The generator applies both.
    SHARE_COUNT_KINDS = ("bonus", "split", "rights")
    factors: dict[str, Fraction] = {}
    share_only: dict[str, Fraction] = {}
    applied: dict[str, int] = {}
    applied_share: dict[str, int] = {}
    applied_div: dict[str, int] = {}
    for symbol in symbols:
        factor = Fraction(1)
        share_factor = Fraction(1)
        count = share_count = div_count = 0
        for entry in per_symbol.get(symbol, {}).get("in_span", ()):
            ex = date.fromisoformat(entry["ex_date"])
            k = Fraction(entry["k"])
            if FIRST_DAY < ex <= LAST_DAY and k != 1:
                factor *= k
                count += 1
                if entry.get("kind") in SHARE_COUNT_KINDS:
                    share_factor *= k
                    share_count += 1
                else:
                    div_count += 1
        factors[symbol] = factor
        share_only[symbol] = share_factor
        applied[symbol] = count
        applied_share[symbol] = share_count
        applied_div[symbol] = div_count

    slice_paise = Fraction(CAPITAL_PAISE, len(usable))
    raw_end = Fraction(0)
    adj_end = Fraction(0)
    share_end = Fraction(0)
    biggest: list[tuple[Fraction, str]] = []
    for symbol in usable:
        fc = first_close[symbol]
        lc = last_close[symbol][1]
        raw_end += slice_paise * Fraction(lc, fc)
        adj_first = int(Fraction(fc) * factors[symbol])
        adj_end += slice_paise * Fraction(lc, adj_first)
        share_first = int(Fraction(fc) * share_only[symbol])
        share_end += slice_paise * Fraction(lc, share_first)
        biggest.append((Fraction(lc, adj_first), symbol))
    raw_return = (raw_end - CAPITAL_PAISE) / CAPITAL_PAISE
    adj_return = (adj_end - CAPITAL_PAISE) / CAPITAL_PAISE
    share_return = (share_end - CAPITAL_PAISE) / CAPITAL_PAISE

    lines: list[str] = []
    add = lines.append
    add("# REVIEW_9B_REPORT -- the buy&hold benchmark, both readings re-derived")
    add("")
    add("Generated by `docs/evidence/review9b_benchmark_recompute.py`, which imports NOTHING")
    add("from `src/acumen`. CONTEXT 7-E13's construction re-implemented from its own words:")
    add("*equal-weight portfolio of the traded universe, bought at first trade date's close,")
    add("held to period end*; capital split equally, fractional units, no rebalancing.")
    add("")
    add("## Population")
    add("")
    add(f"* universe on the manifest: **{len(symbols)}**")
    add(f"* symbols with a close on the first trade date {FIRST_DAY} (IN the benchmark): "
        f"**{len(usable)}** (report: 134)")
    add(f"* excluded, no close on that date: **{len(skipped)}** (report names 70)")
    add(f"* symbols carrying at least one share-count factor in "
        f"({FIRST_DAY}, {LAST_DAY}]: **{sum(1 for s in symbols if applied[s])}** "
        f"(report: 115)")
    add(f"* share-count factors applied in total: **{sum(applied.values())}** (report: 433)")
    add(f"* of those, on symbols actually IN the benchmark: "
        f"**{sum(applied[s] for s in usable)}** across "
        f"**{sum(1 for s in usable if applied[s])}** symbols")
    add("")
    add("## The two readings")
    add("")
    add("| Reading | Start value | End value | Total return | Report |")
    add("|---|---:|---:|---:|---:|")
    add(f"| RAW closes, exactly as stored | {money(CAPITAL_PAISE)} | {money(raw_end)} | "
        f"{pct(raw_return)} | 298.92% |")
    add(f"| Share-count ADJUSTED (THE benchmark, Q-23 ruling) | {money(CAPITAL_PAISE)} | "
        f"{money(adj_end)} | {pct(adj_return)} | 491.90% |")
    add("")
    add("The strategy, over the same window: -Rs 16,736,018.20, -16836.02%.")
    add("")
    add("## What is actually inside the 433 'share-count factors'")
    add("")
    add("The generator counts every non-unit factor in the table as a share-count factor. They "
        "are not all share-count events. A bonus, split or rights issue multiplies a HOLDER'S "
        "UNITS; a special dividend does not -- it is cash, and the price drops by it.")
    add("")
    kind_counts: dict[str, int] = {}
    for symbol in symbols:
        for entry in per_symbol.get(symbol, {}).get("in_span", ()):
            ex = date.fromisoformat(entry["ex_date"])
            if FIRST_DAY < ex <= LAST_DAY and Fraction(entry["k"]) != 1:
                key = f"{entry.get('kind')} / {entry.get('classification') or '-'}"
                kind_counts[key] = kind_counts.get(key, 0) + 1
    add("| Event kind | Non-unit factors in span |")
    add("|---|---:|")
    for key in sorted(kind_counts, key=lambda k: (-kind_counts[k], k)):
        add(f"| {key} | {kind_counts[key]} |")
    add(f"| **total** | **{sum(kind_counts.values())}** |")
    add("")
    add(f"* genuine SHARE-COUNT events (bonus / split / rights): "
        f"**{sum(applied_share.values())}** across "
        f"**{sum(1 for s in symbols if applied_share[s])}** symbols")
    add(f"* special-DIVIDEND price factors: **{sum(applied_div.values())}** across "
        f"**{sum(1 for s in symbols if applied_div[s])}** symbols")
    add("")
    add("| Reading | End value | Total return |")
    add("|---|---:|---:|")
    add(f"| RAW | {money(raw_end)} | {pct(raw_return)} |")
    add(f"| SHARE-COUNT events ONLY (bonus/split/rights) | {money(share_end)} | "
        f"{pct(share_return)} |")
    add(f"| As GENERATED and now ruled THE benchmark (share-count events AND the 308 special "
        f"dividends) | {money(adj_end)} | {pct(adj_return)} |")
    add("")
    add(f"* the special dividends move the ruled benchmark by "
        f"**{pct(adj_return - share_return)}** of the opening capital "
        f"({money(adj_end - share_end)}), i.e. they are "
        f"{pct((adj_return - share_return) / adj_return)} of the published figure")
    add("")
    add("## Why the adjusted reading is the larger one, per symbol")
    add("")
    add("A holder's UNITS multiply through every bonus and split, so dividing the first close "
        "by the pending factors is the same as multiplying the units by their reciprocal. The "
        "ten largest adjusted multiples:")
    add("")
    add("| Symbol | first close | factors | adjusted first close | last close | "
        "raw multiple | adjusted multiple |")
    add("|---|---:|---:|---:|---:|---:|---:|")
    for mult, symbol in sorted(biggest, reverse=True)[:10]:
        fc = first_close[symbol]
        lc = last_close[symbol][1]
        adj_first = int(Fraction(fc) * factors[symbol])
        add(f"| {symbol} | {money(fc)} | {applied[symbol]} (k={factors[symbol]}) | "
            f"{money(adj_first)} | {money(lc)} | "
            f"{float(Fraction(lc, fc)):.3f}x | {float(mult):.3f}x |")
    add("")
    add("## The falsification the ruling names")
    add("")
    add("Symbols whose RAW close-to-close ratio reads them as DOWN over ten years while the "
        "share count they actually held says otherwise:")
    add("")
    add("| Symbol | raw multiple | adjusted multiple | factors |")
    add("|---|---:|---:|---:|")
    falsified = [
        (symbol, Fraction(last_close[symbol][1], first_close[symbol]), mult, applied[symbol])
        for mult, symbol in biggest
        if Fraction(last_close[symbol][1], first_close[symbol]) < 1 <= mult
    ]
    for symbol, rawm, adjm, count in sorted(falsified, key=lambda t: t[1])[:12]:
        add(f"| {symbol} | {float(rawm):.3f}x | {float(adjm):.3f}x | {count} |")
    add("")
    add(f"* symbols the RAW reading calls a loss but the adjusted reading calls a gain: "
        f"**{len(falsified)}**")
    add("")
    add("## Dividends")
    add("")
    ordinary = sum(
        1
        for symbol in symbols
        for entry in per_symbol.get(symbol, {}).get("in_span", ())
        if entry.get("kind") == "dividend" and Fraction(entry["k"]) == 1
    )
    dividend_factored = sorted(
        (symbol, entry["ex_date"], entry["k"])
        for symbol in symbols
        for entry in per_symbol.get(symbol, {}).get("in_span", ())
        if entry.get("kind") == "dividend" and Fraction(entry["k"]) != 1
        and FIRST_DAY < date.fromisoformat(entry["ex_date"]) <= LAST_DAY
    )
    add(f"* in-span dividend events carrying `k = 1` (CONTEXT 4.2's 2% threshold, so NOT "
        f"adjusted on either side): **{ordinary:,}**")
    add(f"* in-span dividend events carrying a factor (special dividends above the threshold, "
        f"applied on the ADJUSTED side only -- the asymmetry Q-23 named and the ruling "
        f"accepted): **{len(dividend_factored)}**")
    for symbol, ex, k in dividend_factored[:15]:
        add(f"  * {symbol} {ex} k={k}")
    add("")
    OUT.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
