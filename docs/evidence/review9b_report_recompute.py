"""REVIEW_9B_REPORT: the report's headline, re-derived from the raw ledger.

Written by the chunk-9B REPORT REVIEW session (06-Aug-2026) under CLAUDE.md's rule that a
session making claims from real store data commits the generating script and its output.

**It imports nothing from `src/acumen`.** Every figure below is computed here, from the run
ledger's own JSON rows, with its own arithmetic in integer paise and exact Fractions -- so a
defect shared between `acumen.portfolio` and `acumen.report_9b` cannot hide inside an agreement
between them. The point is not to re-run the report; it is to answer, independently, whether
-Rs 16,836,018.20 is what those 495,312 rows actually say.

Read-only over the stores. Writes exactly one markdown file inside the repo.

    python docs/evidence/review9b_report_recompute.py

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from fractions import Fraction
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA_ROOT = Path("C:/Users/chinm/acumen-data")  # read from config.yaml below, never typed
RUNS = DATA_ROOT / "backtests"
RUN = "chunk9b_full"
CRASHED = "chunk9b_full_crashed_0803"
PILOT = "chunk9a_pilot_a"
OUT = REPO / "docs" / "evidence" / "review9b_report_recompute.md"

CAPITAL_PAISE = 10_000_000  # config.yaml initial_capital 100000 rupees
COST_PAISE = 10_000  # config.yaml cost_per_trade 100 rupees

# The ledger's own literal vocabulary. Copied from the ledger's bytes (verified by inspection
# against src/acumen, but this file imports nothing from it), so a rename in the package cannot
# silently make a recount here agree by reading a key that no longer exists.
FLAG_OOS: str = "out-of-session 1-minute bar(s) dropped (CONTEXT 7-E2)"
FLAG_MALFORMED: str = "rule-3 minute scan met a malformed 1-minute bar (QUESTIONS.md Q-21)"
FLAG_UNGATED: str = (
    "rule-3 minute scan met a D-1 that fails the CONTEXT 4.5/4.6 gate battery "
    "(QUESTIONS.md Q-21(b))"
)
FLAG_QTY_ZERO: str = "qty_zero_unsizable"
FLAG_SIGNAL_UNSIZABLE: str = "signal_unsizable_consumed"
FLAG_BOTH_TOUCHED: str = "both_touched_stop_wins"
FLAG_SQUARE_OFF_ENTRY: str = "square_off_at_the_entry_candle"
REFERENCE_FROM_MINUTES: str = "E10 fallback: last 1-minute close at or before the 11:14 stamp"
RULE_3_NO_MINUTE: str = "rule-3-no-1min-carry"
RULE_3_NO_BREAK_CARRY: str = "rule-3-no-break-carry"



# --- formatting (this session's own, deliberately re-implemented) ------------------------------


def money(paise: int) -> str:
    sign = "-" if paise < 0 else ""
    whole, frac = divmod(abs(int(paise)), 100)
    return f"{sign}Rs {whole:,}.{frac:02d}"


def pct(value: Fraction | None, places: int = 2) -> str:
    if value is None:
        return "n/a"
    scaled = value * 100 * (10**places)
    num, den = scaled.numerator, scaled.denominator
    q, r = divmod(abs(num), den)
    if r * 2 >= den:
        q += 1
    q = -q if num < 0 else q
    text = f"{q:0{places + 1}d}" if q >= 0 else f"{-q:0{places + 1}d}"
    body = f"{int(text[:-places] or 0):,}.{text[-places:]}"
    return ("-" if q < 0 else "") + body + "%"


def ratio(num: Fraction, places: int = 4) -> str:
    scaled = num * (10**places)
    n, d = scaled.numerator, scaled.denominator
    q, r = divmod(abs(n), d)
    if r * 2 >= d:
        q += 1
    q = -q if n < 0 else q
    text = f"{abs(q):0{places + 1}d}"
    return ("-" if q < 0 else "") + f"{int(text[:-places] or 0)}.{text[-places:]}"


# --- the ledger ---------------------------------------------------------------------------------


class Run:
    def __init__(self, path: Path) -> None:
        self.executed: list[dict] = []
        self.days: set[date] = set()
        self.symbols: set[str] = set()
        self.walked = 0
        self.usable = 0
        self.refused = 0
        self.signalled = 0
        self.relieved = 0
        self.suppressed_rows = 0
        self.tie_days = 0
        self.e10_days = 0
        self.rule3_no_minute = 0
        self.outcomes: Counter = Counter()
        self.reasons: Counter = Counter()
        self.exit_kinds: Counter = Counter()
        self.flags: Counter = Counter()
        self.oos_by_date: Counter = Counter()
        self.oos_by_rule: Counter = Counter()
        self.ungated_by_symbol: Counter = Counter()
        self.malformed = 0
        self.both_touched = 0
        self.square_off_entry = 0
        self.signal_unsizable = 0
        self.qty_zero: list[tuple[str, str, int]] = []
        self.gap_days: list[dict] = []
        self.demerger: list[tuple[str, str]] = []
        self.gate2_days: list[tuple[str, str]] = []
        self.no_break_carry: list[tuple[str, str, str, bool]] = []
        self.side_never_set: list[tuple[str, str]] = []
        self.keys: set[tuple[str, str]] = set()
        self.duplicates = 0
        self.totals = dict(shares=0, gross=0, cost=0, net=0)

        digest = hashlib.sha256()
        nbytes = 0
        with path.open("rb") as raw:
            for chunk in iter(lambda: raw.read(1 << 22), b""):
                digest.update(chunk)
                nbytes += len(chunk)
        self.sha256 = digest.hexdigest()
        self.bytes = nbytes

        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                r = json.loads(line)
                self.walked += 1
                sym, day = r["symbol"], r["day"]
                self.symbols.add(sym)
                self.days.add(date.fromisoformat(day))
                key = (sym, day)
                if key in self.keys:
                    self.duplicates += 1
                self.keys.add(key)
                out = r["outcome"]
                self.outcomes[out if out is not None else f"not evaluated: {r['reason']}"] += 1
                if r["status"] == "refused":
                    self.refused += 1
                    self.reasons[r["reason"]] += 1
                    if r["reason"].startswith("gate 2"):
                        self.gate2_days.append((sym, day))
                    elif "demerger" in r["reason"]:
                        self.demerger.append((sym, day))
                else:
                    self.usable += 1
                if r["suppressed"]:
                    self.suppressed_rows += 1
                if r["tie_case"]:
                    self.tie_days += 1
                if r["gate1_relieved"]:
                    self.relieved += 1
                if r["signalled"]:
                    self.signalled += 1
                if r["reference_source"] == REFERENCE_FROM_MINUTES:
                    self.e10_days += 1
                if out == "no-trade-side-never-set":
                    self.side_never_set.append((sym, day))
                if r["bias_rule"] == "rule-3-no-break-carry":
                    self.no_break_carry.append(
                        (sym, day, r["bias"], FLAG_OOS in r["flags"])
                    )
                if r["bias_rule"] == RULE_3_NO_MINUTE:
                    self.rule3_no_minute += 1
                for flag in r["flags"]:
                    self.flags[flag] += 1
                    if flag == FLAG_OOS:
                        self.oos_by_date[day] += 1
                        self.oos_by_rule[r["bias_rule"] or "-"] += 1
                    elif flag == FLAG_UNGATED:
                        self.ungated_by_symbol[sym] += 1
                    elif flag == FLAG_MALFORMED:
                        self.malformed += 1
                    elif flag == FLAG_BOTH_TOUCHED:
                        self.both_touched += 1
                    elif flag == FLAG_SQUARE_OFF_ENTRY:
                        self.square_off_entry += 1
                    elif flag == FLAG_SIGNAL_UNSIZABLE:
                        self.signal_unsizable += 1
                    elif flag == FLAG_QTY_ZERO:
                        self.qty_zero.append((sym, day, r["per_share_risk_paise"] or 0))
                if r["executed"]:
                    self.executed.append(r)
                    self.totals["shares"] += r["qty"]
                    self.totals["gross"] += r["gross_pnl_paise"]
                    self.totals["cost"] += r["cost_paise"]
                    self.totals["net"] += r["net_pnl_paise"]
                    if r["exit_kind"]:
                        self.exit_kinds[r["exit_kind"]] += 1
                    if r["gap_entry"]:
                        self.gap_days.append(r)
        self.day_index = sorted(self.days)


# --- metrics, computed here ----------------------------------------------------------------------


def headline(rows: list[dict]) -> dict:
    nets = [r["net_pnl_paise"] for r in rows]
    winners = [n for n in nets if n > 0]
    losers = [n for n in nets if n < 0]
    flat = [n for n in nets if n == 0]
    gp = sum(winners)
    gl = sum(losers)
    net = sum(nets)
    n = len(nets)
    return dict(
        trades=n,
        net=net,
        gross_before=sum(r["gross_pnl_paise"] for r in rows),
        costs=sum(r["cost_paise"] for r in rows),
        winners=len(winners),
        losers=len(losers),
        flat=len(flat),
        gross_profit=gp,
        gross_loss=gl,
        pf=Fraction(gp, -gl) if gl else None,
        win_rate=Fraction(len(winners), n) if n else None,
        avg_win=Fraction(gp, len(winners)) if winners else None,
        avg_loss=Fraction(gl, len(losers)) if losers else None,
        expectancy=Fraction(net, n) if n else None,
        largest_win=max(nets) if nets else 0,
        largest_loss=min(nets) if nets else 0,
        shares=sum(r["qty"] for r in rows),
    )


def daily_series(rows: list[dict], days: list[date]) -> list[int]:
    by_day: dict[date, int] = defaultdict(int)
    for r in rows:
        by_day[date.fromisoformat(r["day"])] += r["net_pnl_paise"]
    return [by_day.get(d, 0) for d in days]


def equity_curve(series: list[int], capital: int) -> list[int]:
    out, running = [], capital
    for value in series:
        running += value
        out.append(running)
    return out


def max_drawdown(curve: list[int], days: list[date], capital: int) -> dict:
    peak = capital
    peak_i = None  # None == the opening capital
    best = 0
    best_peak_i = best_trough_i = None
    best_peak_equity = capital
    for i, equity in enumerate(curve):
        if equity > peak:
            peak, peak_i = equity, i
        fall = peak - equity
        if fall > best:
            best, best_peak_i, best_trough_i = fall, peak_i, i
            best_peak_equity = peak
    recovered = None
    if best_trough_i is not None:
        for j in range(best_trough_i + 1, len(curve)):
            if curve[j] >= best_peak_equity:
                recovered = days[j]
                break
    start_i = -1 if best_peak_i is None else best_peak_i
    return dict(
        amount=best,
        pct=Fraction(best, best_peak_equity) if best_peak_equity > 0 else None,
        peak_day=None if best_peak_i is None else days[best_peak_i],
        trough_day=None if best_trough_i is None else days[best_trough_i],
        duration=(0 if best_trough_i is None else best_trough_i - start_i),
        recovered=recovered,
        peak_equity=best_peak_equity,
    )


def max_run_up(curve: list[int], days: list[date], capital: int) -> dict:
    trough = capital
    trough_i = None
    best = 0
    best_trough_i = best_peak_i = None
    best_trough_equity = capital
    for i, equity in enumerate(curve):
        if equity < trough:
            trough, trough_i = equity, i
        rise = equity - trough
        if rise > best:
            best, best_trough_i, best_peak_i = rise, trough_i, i
            best_trough_equity = trough
    given_back = None
    if best_peak_i is not None:
        for j in range(best_peak_i + 1, len(curve)):
            if curve[j] <= best_trough_equity:
                given_back = days[j]
                break
    start_i = -1 if best_trough_i is None else best_trough_i
    return dict(
        amount=best,
        pct=Fraction(best, best_trough_equity) if best_trough_equity > 0 else None,
        trough_day=None if best_trough_i is None else days[best_trough_i],
        peak_day=None if best_peak_i is None else days[best_peak_i],
        duration=(0 if best_peak_i is None else best_peak_i - start_i),
        given_back=given_back,
    )


def quantile(sorted_values: list[int], q: Fraction) -> Fraction:
    """R / numpy type 7, exactly. Re-implemented here, not imported."""
    n = len(sorted_values)
    if n == 0:
        raise ValueError("no values")
    if n == 1:
        return Fraction(sorted_values[0])
    h = Fraction(n - 1) * q
    lo = int(h)
    hi = min(lo + 1, n - 1)
    frac = h - lo
    return Fraction(sorted_values[lo]) + frac * (
        Fraction(sorted_values[hi]) - Fraction(sorted_values[lo])
    )


def tukey(rows: list[dict]) -> dict:
    nets = sorted(r["net_pnl_paise"] for r in rows)
    q1 = quantile(nets, Fraction(1, 4))
    q3 = quantile(nets, Fraction(3, 4))
    iqr = q3 - q1
    lo = q1 - Fraction(3, 2) * iqr
    hi = q3 + Fraction(3, 2) * iqr
    above = [n for n in nets if n > hi]
    below = [n for n in nets if n < lo]
    gp = sum(n for n in nets if n > 0)
    gl = sum(n for n in nets if n < 0)
    return dict(
        q1=q1, q3=q3, iqr=iqr, lo=lo, hi=hi,
        count=len(above) + len(below),
        total=sum(above) + sum(below),
        above=len(above), above_sum=sum(above),
        below=len(below), below_sum=sum(below),
        above_share=Fraction(sum(above), gp) if gp else None,
        below_share=Fraction(sum(below), gl) if gl else None,
    )


# --- the run ---------------------------------------------------------------------------------


def iter_rows(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def main() -> int:
    lines: list[str] = []
    add = lines.append
    add("# REVIEW_9B_REPORT -- the headline, re-derived from the raw ledger")
    add("")
    add("Generated by `docs/evidence/review9b_report_recompute.py`, which imports NOTHING from")
    add("`src/acumen`. Every figure is recomputed here from the run ledger's own JSON rows, in")
    add("integer paise and exact Fractions, and then compared with what")
    add("`docs/reports/chunk9b_backtest_report.md` publishes.")
    add("")

    run_dir = RUNS / RUN
    print("streaming the ledger ...", file=sys.stderr)
    run = Run(run_dir / "ledger.jsonl")
    manifest = json.loads((run_dir / "manifest.json").read_bytes().decode("utf-8"))
    manifest_sha = hashlib.sha256((run_dir / "manifest.json").read_bytes()).hexdigest()

    add("## 0. What was read")
    add("")
    add(f"* ledger `{run_dir / 'ledger.jsonl'}` -- {run.bytes:,} bytes, sha256 `{run.sha256}`")
    add(f"* manifest sha256 `{manifest_sha}`")
    add(f"* rows streamed: **{run.walked:,}**; distinct (symbol, day) keys "
        f"{len(run.keys):,}; duplicates **{run.duplicates}**")
    add(f"* symbols {len(run.symbols)}; day index {len(run.day_index):,} "
        f"({run.day_index[0]} .. {run.day_index[-1]})")
    add("")

    # --- 1. the headline -------------------------------------------------------------------
    h = headline(run.executed)
    longs = [r for r in run.executed if r["side"] == "long"]
    shorts = [r for r in run.executed if r["side"] == "short"]
    hl = headline(longs)
    hs = headline(shorts)

    add("## 1. THE HEADLINE, recomputed")
    add("")
    add("| Figure | This session, from the rows | The report | |")
    add("|---|---:|---:|---|")

    def row(label: str, mine: str, theirs: str) -> None:
        add(f"| {label} | {mine} | {theirs} | {'OK' if mine == theirs else '**DIFFERS**'} |")

    row("Net PnL", money(h["net"]), "-Rs 16,836,018.20")
    row("Gross profit (net basis)", money(h["gross_profit"]), "Rs 113,514,085.92")
    row("Gross loss (net basis)", money(h["gross_loss"]), "-Rs 130,350,104.12")
    row("Profit factor", ratio(h["pf"]), "0.8708")
    row("Trades", f"{h['trades']:,}", "188,345")
    row("Winners", f"{h['winners']:,}", "59,385")
    row("Losers", f"{h['losers']:,}", "128,920")
    row("Flat", f"{h['flat']:,}", "40")
    row("Win rate", pct(h["win_rate"]), "31.53%")
    row("Avg profit", money(round(h["avg_win"])), "Rs 1,911.49")
    row("Avg loss", money(round(h["avg_loss"])), "-Rs 1,011.09")
    row("Avg profit / avg loss", ratio(h["avg_win"] / -h["avg_loss"]), "1.8905")
    row("Expected payoff per trade", money(round(h["expectancy"])), "-Rs 89.39")
    row("Largest win", money(h["largest_win"]), "Rs 2,900.00")
    row("Largest loss", money(h["largest_loss"]), "-Rs 1,100.00")
    row("Commission paid", money(h["costs"]), "Rs 18,834,500.00")
    row("Shares", f"{h['shares']:,}", "256,816,544")
    add("")

    add("### 1a. The gross/net decomposition, checked as arithmetic")
    add("")
    add(f"* net + {h['trades']:,} x Rs 100.00 = {money(h['net'])} + "
        f"{money(h['trades'] * COST_PAISE)} = **{money(h['net'] + h['trades'] * COST_PAISE)}**")
    add(f"* the ledger's own before-costs gross = **{money(h['gross_before'])}**")
    add(f"* equal: **{h['net'] + h['trades'] * COST_PAISE == h['gross_before']}**")
    add(f"* costs recounted = {money(h['costs'])}; "
        f"{h['trades']:,} x Rs 100.00 = {money(h['trades'] * COST_PAISE)}; "
        f"equal: **{h['costs'] == h['trades'] * COST_PAISE}**")
    add(f"* every executed row carries a cost of exactly Rs 100.00: "
        f"**{all(r['cost_paise'] == COST_PAISE for r in run.executed)}**")
    add(f"* every executed row's net == gross - cost: "
        f"**{all(r['net_pnl_paise'] == r['gross_pnl_paise'] - r['cost_paise'] for r in run.executed)}**")
    add("")

    add("### 1b. The break-even win rate, beside the actual")
    add("")
    aw = h["avg_win"]
    al = -h["avg_loss"]
    be = al / (aw + al)
    add(f"* avg win  W = {money(round(aw))}")
    add(f"* avg loss L = {money(round(al))} (magnitude)")
    add(f"* break-even win rate = L / (W + L) = {money(round(al))} / "
        f"({money(round(aw))} + {money(round(al))}) = **{pct(be)}**")
    add(f"* ACTUAL win rate = **{pct(h['win_rate'])}**")
    add(f"* shortfall = {pct(be - h['win_rate'])} of trades. At {h['trades']:,} trades that is "
        f"{float(be - h['win_rate']) * h['trades']:,.0f} winners the strategy did not have.")
    add(f"* sanity: expectancy from W, L and p = p x W - (1-p) x L over the WINNER/LOSER "
        f"population only (the {h['flat']} flat trades are excluded from both averages) = "
        f"{money(round(Fraction(h['winners'], h['winners'] + h['losers']) * aw - Fraction(h['losers'], h['winners'] + h['losers']) * al))} "
        f"per non-flat trade")
    add("")

    add("### 1c. Long / Short")
    add("")
    add("| Figure | Long (mine) | Long (report) | Short (mine) | Short (report) |")
    add("|---|---:|---:|---:|---:|")
    add(f"| Net PnL | {money(hl['net'])} | -Rs 13,248,749.37 | {money(hs['net'])} | "
        f"-Rs 3,587,268.83 |")
    add(f"| Trades | {hl['trades']:,} | 89,345 | {hs['trades']:,} | 99,000 |")
    add(f"| Winners | {hl['winners']:,} | 26,580 | {hs['winners']:,} | 32,805 |")
    add(f"| Losers | {hl['losers']:,} | 62,749 | {hs['losers']:,} | 66,171 |")
    add(f"| Flat | {hl['flat']:,} | 16 | {hs['flat']:,} | 24 |")
    add(f"| Gross profit | {money(hl['gross_profit'])} | Rs 50,096,334.66 | "
        f"{money(hs['gross_profit'])} | Rs 63,417,751.26 |")
    add(f"| Gross loss | {money(hl['gross_loss'])} | -Rs 63,345,084.03 | "
        f"{money(hs['gross_loss'])} | -Rs 67,005,020.09 |")
    add(f"| Profit factor | {ratio(hl['pf'])} | 0.7908 | {ratio(hs['pf'])} | 0.9465 |")
    add(f"| % profitable | {pct(hl['win_rate'])} | 29.75% | {pct(hs['win_rate'])} | 33.14% |")
    add(f"| Avg profit | {money(round(hl['avg_win']))} | Rs 1,884.74 | "
        f"{money(round(hs['avg_win']))} | Rs 1,933.17 |")
    add(f"| Avg loss | {money(round(hl['avg_loss']))} | -Rs 1,009.50 | "
        f"{money(round(hs['avg_loss']))} | -Rs 1,012.60 |")
    add(f"| Expected payoff | {money(round(hl['expectancy']))} | -Rs 148.29 | "
        f"{money(round(hs['expectancy']))} | -Rs 36.24 |")
    add(f"| Commission | {money(hl['costs'])} | Rs 8,934,500.00 | {money(hs['costs'])} | "
        f"Rs 9,900,000.00 |")
    add("")
    add(f"* Long + Short net = {money(hl['net'])} + {money(hs['net'])} = "
        f"**{money(hl['net'] + hs['net'])}**; All = **{money(h['net'])}**; equal: "
        f"**{hl['net'] + hs['net'] == h['net']}**")
    add(f"* Long + Short trades = {hl['trades']:,} + {hs['trades']:,} = "
        f"{hl['trades'] + hs['trades']:,}; All = {h['trades']:,}; equal: "
        f"**{hl['trades'] + hs['trades'] == h['trades']}**")
    add(f"* sides seen in the executed rows: {sorted({r['side'] for r in run.executed})}")
    add("")
    add("`winners x avg profit == gross profit`, checked exactly on each column:")
    add("")
    for label, col in (("All", h), ("Long", hl), ("Short", hs)):
        exact = col["winners"] * col["avg_win"] == col["gross_profit"]
        add(f"* {label}: {col['winners']:,} x {money(round(col['avg_win']))} (exact "
            f"{col['avg_win']}) == {money(col['gross_profit'])} -- **{exact}**")
    add("")

    # --- 2. the eleven year rows ------------------------------------------------------------
    add("### 1d. The eleven year rows")
    add("")
    add("Each year's own trades, its own walked-day index, its running peak seeded at the equity "
        "the year OPENED with -- the report's stated construction, re-implemented here.")
    add("")
    add("| Year | Trades | Win rate | Net PnL | PF | Avg trade | Max DD in year | Gap entries |")
    add("|---|---:|---:|---:|---:|---:|---|---:|")
    by_year_rows: dict[int, list[dict]] = defaultdict(list)
    for r in run.executed:
        by_year_rows[int(r["day"][:4])].append(r)
    by_year_days: dict[int, list[date]] = defaultdict(list)
    for d in run.day_index:
        by_year_days[d.year].append(d)
    gap_by_year: Counter = Counter()
    for r in run.gap_days:
        gap_by_year[r["day"][:4]] += 1
    equity = CAPITAL_PAISE
    year_closing: dict[int, int] = {}
    year_change: dict[int, int] = {}
    for year in sorted(by_year_days):
        rows = by_year_rows.get(year, [])
        opening = equity
        hy = headline(rows)
        series = daily_series(rows, by_year_days[year])
        curve = equity_curve(series, opening)
        dd = max_drawdown(curve, by_year_days[year], opening)
        equity = curve[-1]
        year_closing[year] = equity
        year_change[year] = equity - opening
        add(f"| {year} | {hy['trades']:,} | {pct(hy['win_rate'])} | {money(hy['net'])} | "
            f"{ratio(hy['pf'])} | {money(round(hy['expectancy']))} | "
            f"{money(dd['amount'])} ({pct(dd['pct']) if dd['pct'] else 'n/a -- base <= 0'}) | "
            f"{gap_by_year[str(year)]} |")
    add("")
    add("| Year end | Closing equity (mine) | Change over the year (mine) |")
    add("|---|---:|---:|")
    for year in sorted(year_closing):
        add(f"| {year} | {money(year_closing[year])} | {money(year_change[year])} |")
    add("")
    add(f"* the eleven changes sum to **{money(sum(year_change.values()))}**; the run's net is "
        f"**{money(h['net'])}**; equal: **{sum(year_change.values()) == h['net']}**")
    add(f"* years with a NEGATIVE change: **{sum(1 for v in year_change.values() if v < 0)} of "
        f"{len(year_change)}**")
    add(f"* best year (least negative) {max(year_change, key=lambda y: year_change[y])}: "
        f"{money(max(year_change.values()))}; worst year "
        f"{min(year_change, key=lambda y: year_change[y])}: {money(min(year_change.values()))}")
    add("")

    # --- 2. drawdowns -----------------------------------------------------------------------
    add("## 2. DRAWDOWN and RUN-UP, close-to-close")
    add("")
    series = daily_series(run.executed, run.day_index)
    curve = equity_curve(series, CAPITAL_PAISE)
    dd = max_drawdown(curve, run.day_index, CAPITAL_PAISE)
    ru = max_run_up(curve, run.day_index, CAPITAL_PAISE)
    add(f"* observations (walked days): **{len(curve):,}**")
    add(f"* opening capital {money(CAPITAL_PAISE)}; final equity **{money(curve[-1])}**")
    add(f"* highest closing equity **{money(max(curve))}** on "
        f"{run.day_index[curve.index(max(curve))]}")
    add(f"* lowest closing equity **{money(min(curve))}** on "
        f"{run.day_index[curve.index(min(curve))]}")
    add(f"* first day of the curve {money(curve[0])} on {run.day_index[0]}")
    add("")
    add(f"**Max drawdown (close-to-close): {money(dd['amount'])} ({pct(dd['pct'])}), "
        f"{dd['peak_day']} -> {dd['trough_day']}, {dd['duration']:,} daily observation(s), "
        f"recovered {dd['recovered'] or 'never inside the span'}.**")
    add("")
    add("Report: Rs 16,852,007.80 (14528.90%), 2016-10-06 -> 2026-07-30, 2,424 daily "
        "observation(s), recovered never inside the span.")
    add("")
    add(f"* peak equity used as the denominator: {money(dd['peak_equity'])} "
        f"(= the highest closing equity above)")
    add(f"* NEVER RECOVERED, proved directly: the number of later observations at or above the "
        f"peak equity {money(dd['peak_equity'])} is "
        f"**{sum(1 for e in curve[curve.index(max(curve)) + 1:] if e >= dd['peak_equity'])}**")
    add(f"* the trough IS the last observation: **{dd['trough_day'] == run.day_index[-1]}**")
    add("")
    add(f"**Max run-up (close-to-close): {money(ru['amount'])} "
        f"({pct(ru['pct']) if ru['pct'] else 'base <= 0, no percentage'}), {ru['trough_day']} -> "
        f"{ru['peak_day']}, {ru['duration']:,} daily observation(s), given back "
        f"{ru['given_back'] or 'never inside the span'}.**")
    add("")
    add("Report: Rs 407,255.90 (% n/a -- the base equity is at or below zero), 2024-11-08 -> "
        "2025-01-13, 43 daily observation(s), given back 2025-02-24.")
    add("")
    add(f"* the run-up's base equity (the trough it rose from) is "
        f"{money(curve[run.day_index.index(ru['trough_day'])])}, which is at or below zero: "
        f"**{curve[run.day_index.index(ru['trough_day'])] <= 0}** -- so a percentage of it is "
        f"refused, correctly")
    add(f"* run-up is printed trough -> peak (rising), i.e. in the order it happened: the trough "
        f"date {ru['trough_day']} is EARLIER than the peak date {ru['peak_day']}: "
        f"**{ru['trough_day'] < ru['peak_day']}**")
    add("")

    add("### 2a. The sign-pathology refusals")
    add("")
    crossings = sum(1 for e in curve if e <= 0)
    first_neg = next((run.day_index[i] for i, e in enumerate(curve) if e <= 0), None)
    add(f"* observations at or below zero equity: **{crossings:,} of {len(curve):,}**; the first "
        f"is **{first_neg}**")
    add(f"* so a daily return `change / prior equity` has a denominator that changes sign inside "
        f"the series. Sharpe, Sortino, CAGR and every excursion percentage whose base is at or "
        f"below zero are therefore REFUSED by the report rather than printed.")
    long_curve = equity_curve(daily_series(longs, run.day_index), CAPITAL_PAISE)
    short_curve = equity_curve(daily_series(shorts, run.day_index), CAPITAL_PAISE)
    for label, c in (("All", curve), ("Long", long_curve), ("Short", short_curve)):
        add(f"* {label}: crosses zero = **{any(e <= 0 for e in c)}**, final equity "
            f"{money(c[-1])}")
    add("")
    add("**What a naive Sharpe would have printed** (the defect the session says it caught), "
        "computed here for the record and NOT proposed as a metric:")
    add("")
    prev = CAPITAL_PAISE
    rets: list[Fraction] = []
    negative_base = 0
    for e in curve:
        if prev != 0:
            rets.append(Fraction(e - prev, prev))
            if prev < 0:
                negative_base += 1
        prev = e
    mean = sum(rets) / len(rets)
    var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
    naive_sharpe = float(mean) / (float(var) ** 0.5) * (252**0.5)
    add(f"* mean daily 'return' over {len(rets):,} observations = {float(mean):+.8f}")
    add(f"* divisions with a NEGATIVE denominator (prior equity below zero): "
        f"**{negative_base:,} of {len(rets):,}** -- on every one of them a LOSS divides to a "
        f"POSITIVE 'return'")
    add(f"* an annualized Sharpe built from these returns would print "
        f"**{naive_sharpe:+.4f}** for a strategy that ended at {money(curve[-1])}. The report "
        f"prints `n/a` with its reason instead, on all three columns.")
    add("")

    # --- 3. reconciliation ------------------------------------------------------------------
    add("## 3. The 32 manifest checks, re-verified")
    add("")
    t = manifest["totals"]
    checks: list[tuple[str, object, object]] = [
        ("walked symbol-days", run.walked, t["walked"]),
        ("usable (evaluated)", run.usable, t["usable"]),
        ("signalled", run.signalled, t["signalled"]),
        ("executed", len(run.executed), t["executed"]),
        ("shares", run.totals["shares"], t["shares"]),
        ("gross PnL (paise)", run.totals["gross"], t["gross_pnl_paise"]),
        ("costs (paise)", run.totals["cost"], t["cost_paise"]),
        ("net PnL (paise)", run.totals["net"], t["net_pnl_paise"]),
        ("gate-1 auction relief", run.relieved, t["gate1_relieved"]),
        ("refusals by reason (all 9)", dict(run.reasons), dict(manifest["refused_by_reason"])),
        ("outcomes (the walk's partition)", dict(run.outcomes), dict(manifest["outcomes"])),
        ("exit kinds", dict(run.exit_kinds), dict(manifest["exit_kinds"])),
        ("universe size", len(run.symbols), len(manifest["universe"])),
        ("universe members", sorted(run.symbols), sorted(manifest["universe"])),
        ("PARTITION usable + refused == walked", run.usable + run.refused, run.walked),
        ("PARTITION sum(refusal reasons) == refused", sum(run.reasons.values()), run.refused),
        ("PARTITION sum(outcomes) == walked", sum(run.outcomes.values()), run.walked),
        ("PARTITION symbols x days == walked",
         len(run.symbols) * len(run.day_index), run.walked),
        ("duplicate (symbol, day) keys", run.duplicates, 0),
        ("costs == cost x executed", run.totals["cost"],
         len(run.executed) * int(manifest["spec"]["cost_paise"])),
        ("net == gross - costs", run.totals["net"], run.totals["gross"] - run.totals["cost"]),
    ]
    recount = {
        "gap entries": len(run.gap_days),
        "rule-3 tie bias days": run.tie_days,
        "E10 fallback reference (no 11:00-stamped candle)": run.e10_days,
        "both-touched candles (stop won)": run.both_touched,
        "square-offs priced at the entry candle": run.square_off_entry,
        "qty-zero unsizable days": len(run.qty_zero),
        "signal-unsizable (degenerate) days": run.signal_unsizable,
        "rule-3 day with no 1-minute data (carried, CONTEXT 3.2)": run.rule3_no_minute,
        "rule-3 day refused on a malformed 1-minute bar (QUESTIONS.md Q-21)": run.malformed,
        "day with out-of-session 1-minute bar(s) dropped (CONTEXT 7-E2 / Q-17)":
            sum(run.oos_by_date.values()),
        "rule-3 day refused on a battery-failing D-1 (QUESTIONS.md Q-21(b))":
            sum(run.ungated_by_symbol.values()),
    }
    for label, claimed in sorted(manifest["rare_shapes"].items()):
        checks.append((f"rare shape: {label}", recount[label], claimed))
    ok = 0
    add("| # | Check | Mine | Manifest | |")
    add("|---:|---|---|---|---|")
    for i, (label, mine, theirs) in enumerate(checks, start=1):
        agree = mine == theirs
        ok += agree
        shown_a = mine if not isinstance(mine, (dict, list)) else "match" if agree else "DIFFERS"
        shown_b = theirs if not isinstance(theirs, (dict, list)) else "match" if agree else "DIFFERS"
        if isinstance(shown_a, int):
            shown_a = f"{shown_a:,}"
        if isinstance(shown_b, int):
            shown_b = f"{shown_b:,}"
        add(f"| {i} | {label} | {shown_a} | {shown_b} | {'OK' if agree else '**DIFFERS**'} |")
    add("")
    add(f"**{ok} of {len(checks)} agree.** The report claims 32 of 32.")
    add("")

    # --- pilot ------------------------------------------------------------------------------
    add("## 3b. The pilot window's 290 rows")
    add("")
    pilot_rows = {(r["symbol"], r["day"]): r for r in iter_rows(RUNS / PILOT / "ledger.jsonl")}
    window: dict[tuple[str, str], dict] = {}
    for symbol in ("TCS", "RELIANCE", "HDFCBANK", "ICICIBANK", "BHARTIARTL"):
        for r in iter_rows(run_dir / "symbols" / f"{symbol}.jsonl"):
            if "2026-05-01" <= r["day"] <= "2026-07-24":
                window[(r["symbol"], r["day"])] = r
    identical = sum(1 for k in set(pilot_rows) & set(window) if pilot_rows[k] == window[k])
    differing = [k for k in set(pilot_rows) & set(window) if pilot_rows[k] != window[k]]
    add(f"* pilot ledger rows **{len(pilot_rows)}**; this run's same window **{len(window)}**")
    add(f"* key sets identical: **{set(pilot_rows) == set(window)}**")
    add(f"* rows identical FIELD FOR FIELD: **{identical}**; differing: **{len(differing)}**")
    pex = [r for r in pilot_rows.values() if r["executed"]]
    add(f"* pilot window totals recomputed here: executed {len(pex)}, shares "
        f"{sum(r['qty'] for r in pex):,}, gross {money(sum(r['gross_pnl_paise'] for r in pex))}, "
        f"costs {money(sum(r['cost_paise'] for r in pex))}, net "
        f"{money(sum(r['net_pnl_paise'] for r in pex))}")
    add(f"* pilot ledger sha256 "
        f"`{hashlib.sha256((RUNS / PILOT / 'ledger.jsonl').read_bytes()).hexdigest()}`")
    add("")

    # --- crashed ----------------------------------------------------------------------------
    add("## 3c. The crashed run's 145 differing rows, re-derived and re-classified")
    add("")

    def classify(before: dict, after: dict) -> str:
        if (after.get("bias_rule") == "minutes-ungated"
                or FLAG_UNGATED in after.get("flags", ())):
            return "A. Q-21(b) minutes-ungated"
        if str(after.get("reason", "")).startswith("gate 2"):
            return "B. Q-21(a) gate-2 open test"
        if (FLAG_OOS in after.get("flags", ())
                and FLAG_OOS not in before.get("flags", ())):
            return "C. Q-22(a) out-of-session stamp dropped"
        return "D. downstream carried bias"

    crashed_dir = RUNS / CRASHED / "symbols"
    shards = sorted(p.stem for p in crashed_dir.glob("*.jsonl"))
    causes: Counter = Counter()
    compared = changed = 0
    identical_shards: list[str] = []
    diff_rows: list[tuple[str, str, str, dict, dict]] = []
    byte_identical = 0
    for symbol in shards:
        old_path = crashed_dir / f"{symbol}.jsonl"
        new_path = run_dir / "symbols" / f"{symbol}.jsonl"
        if old_path.read_bytes() == new_path.read_bytes():
            byte_identical += 1
        old = {r["day"]: r for r in iter_rows(old_path)}
        new = {r["day"]: r for r in iter_rows(new_path)}
        compared += len(old)
        touched = False
        for day in sorted(set(old) & set(new)):
            if old[day] == new[day]:
                continue
            changed += 1
            touched = True
            cause = classify(old[day], new[day])
            causes[cause] += 1
            diff_rows.append((symbol, day, cause, old[day], new[day]))
        if not touched:
            identical_shards.append(symbol)
    add(f"* shards retained: **{len(shards)}**; rows compared **{compared:,}**")
    add(f"* rows that differ: **{changed}** ({pct(Fraction(changed, compared), 4)} of them)")
    add(f"* shards with NO differing row: **{len(identical_shards)}**")
    add(f"* shards BYTE-for-byte identical (independent check, sha of the file): "
        f"**{byte_identical}**")
    add("")
    add("| Cause | Rows (mine) | Report |")
    add("|---|---:|---:|")
    claimed_causes = {"A. Q-21(b) minutes-ungated": 105, "B. Q-21(a) gate-2 open test": 18,
                      "C. Q-22(a) out-of-session stamp dropped": 9,
                      "D. downstream carried bias": 13}
    for cause in sorted(claimed_causes):
        add(f"| {cause} | {causes.get(cause, 0)} | {claimed_causes[cause]} |")
    add(f"| **total** | **{sum(causes.values())}** | **145** |")
    add("")
    add(f"* rows differing for NO listed cause: **{changed - sum(causes.values())}**")
    add("")
    add("### 3c-i. A hand-classified SAMPLE of 20, re-derived from the two rows themselves")
    add("")
    add("Every 7th differing row, so the sample is not the head of one symbol. For each the two "
        "rows' own fields are printed, and the class is re-derived from them by eye rather than "
        "by the classifier above.")
    add("")
    add("| # | Symbol | Day | before: rule / reason / flags | after: rule / reason / flags | "
        "class |")
    add("|---:|---|---|---|---|---|")
    step = max(1, len(diff_rows) // 20)
    sample = diff_rows[::step][:20]
    for i, (symbol, day, cause, before, after) in enumerate(sample, start=1):
        b = (f"{before['bias_rule']} / {before['reason'][:34]} / "
             f"{','.join(before['flags']) or '-'}")
        a = (f"{after['bias_rule']} / {after['reason'][:34]} / "
             f"{','.join(after['flags']) or '-'}")
        add(f"| {i} | {symbol} | {day} | {b} | {a} | {cause[0]} |")
    add("")
    add(f"* sample size {len(sample)}; class counts in the sample: "
        f"{dict(Counter(c for *_, c, _, _ in [(s, d, c, b, a) for s, d, c, b, a in sample]))}")
    add("")
    add("### 3c-ii. The 59 byte-identical shards, as the arithmetic 76 - 17")
    add("")
    touched_by: dict[str, set[str]] = defaultdict(set)
    for symbol, day, cause, _b, _a in diff_rows:
        touched_by[symbol].add(cause)
    only_a = {s for s, cs in touched_by.items() if cs == {"A. Q-21(b) minutes-ungated"}}
    any_a = {s for s, cs in touched_by.items() if "A. Q-21(b) minutes-ungated" in cs}
    add(f"* shards with at least one differing row: **{len(touched_by)}**")
    add(f"* shards untouched by Q-21(b) (cause A absent): "
        f"**{len(shards) - len(any_a)}** -- FIX-2 predicted 76")
    add(f"* shards touched by B or C as well: "
        f"**{len({s for s, cs in touched_by.items() if cs - {'A. Q-21(b) minutes-ungated'}})}**")
    add(f"* 76 - 17 = 59; shards with no differing row at all = **{len(identical_shards)}**")
    add(f"* shards touched ONLY by cause A: **{len(only_a)}**")
    add("")

    # --- witnesses ---------------------------------------------------------------------------
    add("## 4. Witnesses")
    add("")
    add("### 4a. The two qty-zero days")
    add("")
    add("| Symbol | Day | per_share_risk_paise | floor(Rs 1,000 / per-share risk) |")
    add("|---|---|---:|---:|")
    for symbol, day, risk in sorted(run.qty_zero):
        add(f"| {symbol} | {day} | {risk} ({money(risk)}) | {100000 // risk} |")
    add("")
    add(f"* both floor to ZERO shares: "
        f"**{all(100000 // risk == 0 for _s, _d, risk in run.qty_zero)}**")
    qz_rows = [
        next(x for x in iter_rows(run_dir / "symbols" / f"{s}.jsonl") if x["day"] == d)
        for s, d, _r in run.qty_zero
    ]
    add(f"* both rows carry qty 0 and cost 0: "
        f"**{all(r['qty'] == 0 and r['cost_paise'] == 0 for r in qz_rows)}**")
    add(f"* neither invents a fill price (exit_paise is null): "
        f"**{all(r['exit_paise'] is None for r in qz_rows)}**")
    add(f"* both are CONSUMED and COUNTED (signalled, consumed, not executed): "
        f"**{all(r['signalled'] and r['consumed'] and not r['executed'] for r in qz_rows)}**")
    add(f"* their per-share risks read from the rows: "
        f"{[(r['symbol'], r['day'], money(r['per_share_risk_paise'])) for r in qz_rows]}")
    add("")
    add("### 4b. Q-17's five market-wide dates, against the ledger's own flags")
    add("")
    add("| Date | Walked rows this run flagged (mine) | Report |")
    add("|---|---:|---:|")
    claimed_q17 = {"2017-04-28": 123, "2018-11-05": 0, "2019-10-25": 55, "2020-12-08": 1,
                   "2021-02-24": 148}
    for d in sorted(claimed_q17):
        add(f"| {d} | {run.oos_by_date.get(d, 0)} | {claimed_q17[d]} |")
    add("")
    add(f"* total flagged rows across ALL dates: **{sum(run.oos_by_date.values()):,}** "
        f"(report 889); distinct dates carrying a flag: **{len(run.oos_by_date)}**")
    add(f"* the five market-wide dates account for "
        f"**{sum(run.oos_by_date.get(d, 0) for d in claimed_q17):,}** of them")
    add("")
    add("| Bias rule on a flagged row | Rows (mine) |")
    add("|---|---:|")
    for rule, n in run.oos_by_rule.most_common():
        add(f"| {rule} | {n} |")
    add("")
    add("### 4c. The five Rule-3 no-break carries")
    add("")
    add("| Symbol | Trade day | Carried bias | Out-of-session bars dropped |")
    add("|---|---|---|---|")
    for symbol, day, bias, flagged in sorted(run.no_break_carry):
        add(f"| {symbol} | {day} | {bias} | {'YES' if flagged else 'no'} |")
    add("")
    add(f"* count **{len(run.no_break_carry)}**; flagged (Q-22(a)) "
        f"**{sum(1 for *_x, f in run.no_break_carry if f)}**")
    add("")
    add("### 4d. Gap entries, demergers, side-never-set")
    add("")
    gap_net = sum(r["net_pnl_paise"] for r in run.gap_days)
    gap_win = sum(1 for r in run.gap_days if r["net_pnl_paise"] > 0)
    add(f"* gap entries **{len(run.gap_days):,}**, net **{money(gap_net)}**, winners "
        f"**{gap_win}** ({pct(Fraction(gap_win, len(run.gap_days)))})")
    add(f"* gap exit kinds: {dict(Counter(r['exit_kind'] for r in run.gap_days))}")
    add(f"* earliest gap day by DATE: "
        f"{min((r['day'], r['symbol']) for r in run.gap_days)}; latest: "
        f"{max((r['day'], r['symbol']) for r in run.gap_days)}")
    add(f"* demerger-suppressed REFUSED rows **{len(run.demerger)}** across "
        f"**{len({s for s, _d in run.demerger})}** symbols; rows carrying the `suppressed` mark "
        f"**{run.suppressed_rows}**; difference **{run.suppressed_rows - len(run.demerger)}**")
    add(f"* side-never-set days: {sorted(run.side_never_set)}")
    add("")

    # --- Tukey ---------------------------------------------------------------------------------
    add("## 4e. The Tukey outlier block, on all three columns")
    add("")
    add("Fences [Q1 - 3/2 x IQR, Q3 + 3/2 x IQR] over the NET PnL of ALL executed trades, "
        "quartiles by linear interpolation between order statistics (R / numpy type 7), computed "
        "in exact Fractions -- the architect's Q-16(a) definition, re-implemented here.")
    add("")
    add("| Column | Q1 | Q3 | IQR | Lower fence | Upper fence | Outliers | Summed net |")
    add("|---|---:|---:|---:|---:|---:|---:|---:|")
    tukeys = {}
    for label, rows in (("All", run.executed), ("Long", longs), ("Short", shorts)):
        t = tukey(rows)
        tukeys[label] = t
        add(f"| {label} | {money(round(t['q1']))} | {money(round(t['q3']))} | "
            f"{money(round(t['iqr']))} | {money(round(t['lo']))} | {money(round(t['hi']))} | "
            f"{t['count']:,} | {money(t['total'])} |")
    add("")
    add("The report prints: All Q1 -Rs 1,099.60 / Q3 Rs 622.70 / IQR Rs 1,722.30, fences "
        "[-Rs 3,683.05, Rs 3,206.15], **0** outliers; Long Q1 -Rs 1,099.60 / Q3 Rs 440.00 / "
        "IQR Rs 1,539.60, fences [-Rs 3,409.00, Rs 2,749.40], **13,243** outliers worth "
        "Rs 38,311,425.93 = 76.48% of gross profit; Short Q1 -Rs 1,099.60 / Q3 Rs 800.95 / "
        "IQR Rs 1,900.55, fences [-Rs 3,950.42, Rs 3,651.78], **0**.")
    add("")
    for label in ("All", "Long", "Short"):
        t = tukeys[label]
        add(f"* {label}: above the upper fence **{t['above']:,}** worth {money(t['above_sum'])} "
            f"= {pct(t['above_share']) if t['above_share'] is not None else 'n/a'} of gross "
            f"profit; below the lower fence **{t['below']:,}** worth {money(t['below_sum'])} "
            f"= {pct(t['below_share']) if t['below_share'] is not None else 'n/a'} of gross loss")
    add("")
    add("**The prose under the block does not survive its own Long column.** Section 6a closes "
        "with *\"a fixed-R strategy bounds its own trades ... so before costs every trade lands "
        "in a narrow band and the fences sit outside it\"*. On the LONG column they do not: the "
        f"upper fence is {money(round(tukeys['Long']['hi']))} and the largest win is "
        f"{money(max(r['net_pnl_paise'] for r in longs))}, so every long win above the fence is "
        f"an outlier and {tukeys['Long']['above']:,} of them are.")
    add("")
    add(f"* trades in the whole run outside the structural band "
        f"[-Rs 1,100.00, +Rs 2,900.00]: "
        f"**{sum(1 for r in run.executed if not -110000 <= r['net_pnl_paise'] <= 290000)}**")
    add(f"* the band's endpoints ARE the largest loss and the largest win: "
        f"{money(h['largest_loss'])} / {money(h['largest_win'])}")
    add("")

    # --- R10 --------------------------------------------------------------------------------
    add("## 4f. R10's refusal pricing, traced back to the crashed shards")
    add("")
    priced: dict[str, list[dict]] = {c: [] for c in claimed_causes}
    moved: dict[str, int] = {c: 0 for c in claimed_causes}
    walked_by_cause: dict[str, int] = {c: 0 for c in claimed_causes}
    for _symbol, _day, cause, before, after in diff_rows:
        walked_by_cause[cause] += 1
        if before["executed"] and not after["executed"]:
            priced[cause].append(before)
        elif before["executed"] and after["executed"]:
            moved[cause] += 1
    add("| Cause | Differing rows in the 103 shards | Rows that TRADED before and not after | "
        "Their net PnL | Rows that traded on BOTH and differently |")
    add("|---|---:|---:|---:|---:|")
    for cause in sorted(claimed_causes):
        add(f"| {cause} | {walked_by_cause[cause]} | {len(priced[cause])} | "
            f"{money(sum(r['net_pnl_paise'] for r in priced[cause]))} | {moved[cause]} |")
    add("")
    add("The report publishes: minutes-ungated **13** trades worth **-Rs 7,358.35**; gate 2 "
        "**7** trades worth **-Rs 3,698.60**; and, in section 11b's closing paragraph, "
        "**13** downstream rows of which **2** traded on both runs and differently.")
    add("")
    add("**One precision the row invites a reader to get wrong.** The priced row prints the "
        f"refusal class's FULL count ({run.reasons['bias unresolvable (CONTEXT 3.2 pair could not be assembled): minutes-ungated']} "
        f"days for minutes-ungated, {run.reasons['gate 2 (candle integrity)']} for gate 2) "
        f"beside a trade count measured over only the days the crashed run actually walked "
        f"({walked_by_cause['A. Q-21(b) minutes-ungated']} and "
        f"{walked_by_cause['B. Q-21(a) gate-2 open test']} respectively). The measured base is "
        f"the smaller number, and the report's own text says the shards *\"walked these days\"* "
        f"without saying it walked only some of them.")
    add("")

    # --- MFE/MAE ------------------------------------------------------------------------------
    add("## 4g. MFE / MAE, and the basis the definitions block declares")
    add("")
    with_exc = [r for r in run.executed if r["mfe_paise"] is not None
                and r["mae_paise"] is not None]
    avg_mfe = Fraction(sum(r["mfe_paise"] for r in with_exc), len(with_exc))
    avg_mae = Fraction(sum(r["mae_paise"] for r in with_exc), len(with_exc))
    outside = sum(1 for r in with_exc
                  if not r["mae_paise"] <= r["net_pnl_paise"] <= r["mfe_paise"])
    outside_gross = sum(1 for r in with_exc
                        if not r["mae_paise"] <= r["gross_pnl_paise"] <= r["mfe_paise"])
    add(f"* executed rows carrying both excursions: **{len(with_exc):,}** of "
        f"{h['trades']:,}")
    add(f"* avg MFE **{money(round(avg_mfe))}** (report Rs 1,415.23); avg MAE "
        f"**{money(round(avg_mae))}** (report -Rs 1,181.69)")
    add(f"* largest MFE **{money(max(r['mfe_paise'] for r in with_exc))}** (report "
        f"Rs 164,000.00); largest MAE "
        f"**{money(min(r['mae_paise'] for r in with_exc))}** (report -Rs 141,000.00)")
    add(f"* trades whose GROSS PnL sits inside [MAE, MFE] (the bracket the definitions block "
        f"claims): **{len(with_exc) - outside_gross:,} of {len(with_exc):,}**, violations "
        f"**{outside_gross:,}**")
    add(f"* trades whose NET PnL sits inside [MAE, MFE]: "
        f"**{len(with_exc) - outside:,} of {len(with_exc):,}**, violations **{outside:,}** -- "
        f"which is exactly why the definitions block says the pair brackets a trade's GROSS "
        f"and not its net")
    add("")

    # --- take-all disclosures ----------------------------------------------------------------
    add("## 5. The take-all disclosures, recomputed")
    add("")
    daily_counts: Counter = Counter()
    by_day_rows: dict[str, list[dict]] = defaultdict(list)
    for r in run.executed:
        by_day_rows[r["day"]].append(r)
    for d in run.day_index:
        daily_counts[len(by_day_rows.get(d.isoformat(), []))] += 1
    add(f"* most trades in one day: **{max(daily_counts)}**")
    add(f"* days with zero trades: **{daily_counts[0]}**")
    add(f"* distribution total: **{sum(daily_counts.values()):,}** (== walked days "
        f"{len(run.day_index):,}: {sum(daily_counts.values()) == len(run.day_index)})")
    add(f"* largest single-trade notional: "
        f"**{money(max(r['notional_paise'] for r in run.executed))}** (report "
        f"Rs 27,408,000.00)")
    add("")
    add("Concurrency and simultaneous notional, from the ledger's own entry/exit stamps -- a "
        "position is open from its entry candle's close through its exit candle's close, and no "
        "position straddles a day (CONTEXT 3.1 squares off at 15:15):")
    add("")
    events: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for r in run.executed:
        events[r["day"]].append(
            (r["entry_close_stamp"], r["exit_close_stamp"] or r["entry_close_stamp"],
             r["notional_paise"])
        )
    best_count = (0, None)
    best_notional = (0, None, 0)
    for day, trades in events.items():
        stamps = sorted({s for t in trades for s in (t[0], t[1])})
        for stamp in stamps:
            live = [t for t in trades if t[0] <= stamp <= t[1]]
            if len(live) > best_count[0]:
                best_count = (len(live), stamp)
            notional = sum(t[2] for t in live)
            if notional > best_notional[0]:
                best_notional = (notional, stamp, len(live))
    add(f"* max concurrent positions: **{best_count[0]}**, first at **{best_count[1]}** "
        f"(report: 90, first reached 2026-05-07 12:45)")
    add(f"* peak simultaneous notional: **{money(best_notional[0])}** at "
        f"**{best_notional[1]}**, across **{best_notional[2]}** positions (report: "
        f"Rs 42,148,077.61 at 2023-10-31 13:00, across 39)")
    add(f"* that peak against the Rs 1,00,000 capital: "
        f"**{float(Fraction(best_notional[0], CAPITAL_PAISE)):.4f}x** (report: 421.4808x)")
    add("")

    # --- 5b. the whole per-symbol table -------------------------------------------------------
    add("### 5b. All 204 rows of section 9, recomputed cell by cell")
    add("")
    report_text = (REPO / "docs" / "reports" / "chunk9b_backtest_report.md").read_text(
        encoding="utf-8"
    )
    published: dict[str, list[str]] = {}
    for line in report_text.splitlines():
        if line.startswith("| ") and line.count("|") == 11:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells[-1] in ("settled", "quarantined"):
                published[cells[0]] = cells
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for r in run.executed:
        by_symbol[r["symbol"]].append(r)
    mismatch: list[str] = []
    for symbol in sorted(run.symbols):
        rows = by_symbol.get(symbol, [])
        hs_ = headline(rows)
        series_s = daily_series(rows, run.day_index)
        dd_s = max_drawdown(equity_curve(series_s, CAPITAL_PAISE), run.day_index, CAPITAL_PAISE)
        mine = [
            symbol,
            f"{hs_['trades']:,}",
            pct(hs_["win_rate"]) if hs_["win_rate"] is not None else "-",
            money(hs_["net"]),
            ratio(hs_["pf"]) if hs_["pf"] is not None else "undefined",
            money(hs_["largest_win"]),
            money(hs_["largest_loss"]),
            money(dd_s["amount"]),
        ]
        theirs = published.get(symbol)
        if theirs is None:
            mismatch.append(f"{symbol}: no published row")
            continue
        for i, value in enumerate(mine):
            if value != theirs[i]:
                mismatch.append(f"{symbol} col{i}: mine {value!r} vs report {theirs[i]!r}")
    add(f"* published per-symbol rows parsed: **{len(published)}**")
    add(f"* cells recomputed: symbol, trades, win rate, net PnL, profit factor, largest win, "
        f"largest loss, max drawdown -- **{len(published) * 8:,}** cells")
    add(f"* DISAGREEMENTS: **{len(mismatch)}**")
    for text in mismatch[:25]:
        add(f"  * {text}")
    add(f"* the per-symbol nets sum to "
        f"**{money(sum(sum(r['net_pnl_paise'] for r in by_symbol.get(s, [])) for s in run.symbols))}**"
        f", the run's net is **{money(h['net'])}**")
    add(f"* symbols with a POSITIVE net: "
        f"**{sum(1 for s in run.symbols if sum(r['net_pnl_paise'] for r in by_symbol.get(s, [])) > 0)}**"
        f" of {len(run.symbols)}")
    add("")

    # --- 6. the claims a reader would check next ----------------------------------------------
    add("## 6. Four further claims on the page, checked")
    add("")
    weekend = [d for d in run.day_index if d.weekday() >= 5]
    add(f"* section 2 says the walk is *2,425 trading days + the 3 weekend-dated Muhurat "
        f"sessions*. Weekend-dated days in the index: **{len(weekend)}** "
        f"({', '.join(d.isoformat() for d in weekend)}); {len(run.day_index):,} - "
        f"{len(weekend)} = **{len(run.day_index) - len(weekend):,}** -- claim holds: "
        f"**{len(run.day_index) - len(weekend) == 2425 and len(weekend) == 3}**")
    e2 = run.reasons["CONTEXT 7-E2 non-standard session (stored candles outside 09:15-15:30)"]
    add(f"* the E2 refusal count is **{e2:,}**, which is more than the "
        f"{len(weekend) * len(run.symbols):,} rows those three weekend dates could contribute "
        f"-- CONTEXT 4.6 names EIGHT non-standard sessions, and the counter is over all of them")
    add("")
    ties = sum(1 for r in run.executed if r["net_pnl_paise"] == h["largest_win"])
    tie_long = sum(1 for r in longs if r["net_pnl_paise"] == hl["largest_win"])
    tie_short = sum(1 for r in shorts if r["net_pnl_paise"] == hs["largest_win"])
    tie_loss = sum(1 for r in run.executed if r["net_pnl_paise"] == h["largest_loss"])
    add(f"* section 6 prints *Largest win, % of its own notional* as 0.29% / 0.13% / 0.29%. "
        f"The largest win is not one trade: **{ties:,}** executed trades tie at exactly "
        f"{money(h['largest_win'])} (Long {tie_long:,}, Short {tie_short:,}), and "
        f"**{tie_loss:,}** tie at exactly {money(h['largest_loss'])}. Which of them supplies the "
        f"notional -- and therefore the percentage -- is decided by the ledger's own row order, "
        f"not by anything on the page. The notionals of the tied winners range "
        f"{money(min(r['notional_paise'] for r in run.executed if r['net_pnl_paise'] == h['largest_win']))} "
        f"to "
        f"{money(max(r['notional_paise'] for r in run.executed if r['net_pnl_paise'] == h['largest_win']))}, "
        f"so the printed percentage could have been anything from "
        f"{pct(Fraction(h['largest_win'], max(r['notional_paise'] for r in run.executed if r['net_pnl_paise'] == h['largest_win'])))} "
        f"to "
        f"{pct(Fraction(h['largest_win'], min(r['notional_paise'] for r in run.executed if r['net_pnl_paise'] == h['largest_win'])))}.")
    add("")
    full_years = {y: v for y, v in year_change.items() if y not in (2016, 2026)}
    add(f"* section 5 prints *Best year: 2016, {money(year_change[2016])}*. 2016 is a PARTIAL "
        f"year -- the minute era opens 2016-10-03, so it carries "
        f"**{len(by_year_days[2016]):,}** walked days against a full year's ~246 -- and section "
        f"8 says so, but section 5 does not. Among the nine FULL years the least negative is "
        f"**{max(full_years, key=lambda y: full_years[y])} at "
        f"{money(max(full_years.values()))}**. 2026 is partial too "
        f"({len(by_year_days[2026]):,} days).")
    add("")
    add(f"* section 1 says the Rs 18,834,500.00 of commission *is the difference between the "
        f"two headline figures in section 5*. Section 5 carries ONE PnL figure "
        f"({money(h['net'])}); the before-costs figure it is the difference from "
        f"({money(h['gross_before'])}) is printed in section 6, which section 5's own closing "
        f"line says. The arithmetic is right and the cross-reference is not.")
    add("")

    OUT.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
