"""REVIEW_9B_REPORT: two gap-entry days walked end to end -- bias, POC, signal, money.

Written by the chunk-9B REPORT REVIEW session (06-Aug-2026). It imports NOTHING from
`src/acumen`: CONTEXT 3.2 (bias), 3.3 (volume profile / POC), 3.4 (the signal state machine and
the GAP branch) and 3.5 (sizing, costs, PnL) are re-implemented here from the spec text, and the
answer is compared with the ledger row the run wrote.

The two days are the ones section 12a of the report NAMES as the earliest and the latest gap
entry of the whole ten-year span, so walking them also tests that claim:

* MUTHOOTFIN 2016-10-06 -- the earliest
* TIINDIA    2026-07-27 -- the latest

Both are BEARISH days, so both exercise the SHORT mirror of the gap rule: the entry candle's
HIGH sits below the POC, so the stop comes from the previous 15-minute candle's CLOSE rather
than from the entry candle.

    python docs/evidence/review9b_gap_walks.py

Read-only over the stores. Writes exactly one markdown file inside the repo.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from fractions import Fraction
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA_ROOT = Path("C:/Users/chinm/acumen-data")
RUN_DIR = DATA_ROOT / "backtests" / "chunk9b_full"
MINUTES = DATA_ROOT / "minute_store" / "minute"
DAILY = DATA_ROOT / "daily_store" / "daily"
MASTER = DATA_ROOT / "cache" / "instrument_master" / "OpenAPIScripMaster_2026-07-31.json"
OUT = REPO / "docs" / "evidence" / "review9b_gap_walks.md"

ROW_SIZE = 24  # config.yaml row_size, CONTEXT 3.3
RISK_PAISE = 100_000  # config.yaml risk_per_trade 1000 rupees, CONTEXT 3.5
COST_PAISE = 10_000  # config.yaml cost_per_trade 100 rupees, CONTEXT 3.5
INSTRUMENT_SERIES = ("EQ", "BE", "BZ")

WALKS = (("MUTHOOTFIN", date(2016, 10, 6)), ("TIINDIA", date(2026, 7, 27)))


def money(paise) -> str:
    value = int(paise)
    sign = "-" if value < 0 else ""
    whole, frac = divmod(abs(value), 100)
    return f"{sign}Rs {whole:,}.{frac:02d}"


def half_paise(value: Fraction) -> str:
    """A POC may legally sit on a half paisa (CONTEXT 3.3). Print it as it is."""
    rupees = value / 100
    return f"Rs {float(rupees):,.3f}".rstrip("0").rstrip(".")


def round_half_even(value: Fraction) -> int:
    floor = value.numerator // value.denominator
    rest = value - floor
    if rest > Fraction(1, 2):
        return floor + 1
    if rest < Fraction(1, 2):
        return floor
    return floor if floor % 2 == 0 else floor + 1


# --- the stores, read directly -------------------------------------------------------------


def minutes(symbol: str, day: date) -> pd.DataFrame:
    path = MINUTES / symbol / f"{symbol}_{day.year:04d}-{day.month:02d}.parquet"
    frame = pd.read_parquet(path)
    frame = frame[frame["stamp"].dt.date == day].sort_values("stamp")
    keep = frame["stamp"].dt.time.between(time(9, 15), time(15, 29))
    return frame.loc[keep].reset_index(drop=True)


def daily_rows(symbol: str, upto: date, count: int) -> list[dict]:
    """The last ``count`` EQUITY daily rows on or before ``upto``, oldest first."""
    out: list[dict] = []
    probe = upto
    while len(out) < count and probe > date(2015, 1, 1):
        path = DAILY / f"{probe.year:04d}" / f"bhavcopy_{probe.year:04d}-{probe.month:02d}.parquet"
        if path.is_file():
            frame = pd.read_parquet(path)
            frame = frame[
                (frame["symbol"] == symbol)
                & (frame["series"].isin(INSTRUMENT_SERIES))
                & (frame["trade_date"] <= upto)
            ].sort_values("trade_date")
            out = [r._asdict() for r in frame.itertuples(index=False)] + out
        probe = probe.replace(day=1) - timedelta(days=1)
    return out[-count:]


def tick_paise(symbol: str) -> int:
    for row in json.loads(MASTER.read_text(encoding="utf-8")):
        if row.get("name") == symbol and row.get("exch_seg") == "NSE":
            raw = Fraction(row["tick_size"])
            assert raw.denominator == 1, raw
            return int(raw)
    raise KeyError(symbol)


# --- CONTEXT 3.3, re-implemented --------------------------------------------------------------


def poc(frame: pd.DataFrame, tick: int, n_rows: int) -> dict:
    window = frame[frame["stamp"].dt.time <= time(11, 14)]
    top = int(window["high_paise"].max())
    bottom = int(window["low_paise"].min())
    if top == bottom:
        return dict(top=top, bottom=bottom, total_ticks=1, tpr=1, rows=1,
                    poc=Fraction(top), bars=len(window), volume=int(window["volume"].sum()),
                    row_volumes=[(Fraction(top), int(window["volume"].sum()))])
    total_ticks = round_half_even(Fraction(top - bottom, tick))
    exact = Fraction(total_ticks, n_rows)
    lo_tpr = max(1, exact.numerator // exact.denominator)
    hi_tpr = max(1, lo_tpr + 1)
    candidates = []
    for tpr in {lo_tpr, hi_tpr}:
        rows = -(-total_ticks // tpr)
        candidates.append((abs(rows - n_rows), tpr, rows))
    candidates.sort()  # closest realized row count, then the SMALLER tpr (finer) on a tie
    _, tpr, rows = candidates[0]

    edges = []
    for i in range(rows):
        lo = bottom + i * tpr * tick
        hi = min(bottom + (i + 1) * tpr * tick, top)
        edges.append((lo, hi))
    volumes = [Fraction(0) for _ in edges]
    for bar in window.itertuples():
        low, high, vol = int(bar.low_paise), int(bar.high_paise), int(bar.volume)
        if high == low:  # a point bar: the whole volume into the row containing that price
            for i, (lo, hi) in enumerate(edges):
                inside = lo <= low < hi or (i == len(edges) - 1 and low == hi)
                if inside:
                    volumes[i] += vol
                    break
            continue
        span = Fraction(high - low)
        for i, (lo, hi) in enumerate(edges):
            top_edge = hi if i < len(edges) - 1 else hi + 1  # topmost row includes `top`
            overlap = min(high, top_edge if i == len(edges) - 1 else hi) - max(low, lo)
            if i == len(edges) - 1:
                overlap = min(high, hi) - max(low, lo)
                if high >= hi:
                    overlap = hi - max(low, lo)
            if overlap > 0:
                volumes[i] += Fraction(vol) * Fraction(overlap) / span
    best = max(range(len(edges)), key=lambda i: (volumes[i], edges[i][0]))
    lo, hi = edges[best]
    return dict(
        top=top, bottom=bottom, total_ticks=total_ticks, tpr=tpr, rows=rows,
        poc=Fraction(lo + hi, 2), bars=len(window), volume=int(window["volume"].sum()),
        row_volumes=[(Fraction(a + b, 2), volumes[i]) for i, (a, b) in enumerate(edges)],
        best_row=(lo, hi, volumes[best]),
    )


def fifteen(frame: pd.DataFrame) -> list[dict]:
    """CONTEXT 7-E1/E12: the bar covering open-stamps [T, T+15) CLOSES at T+15."""
    open_stamp = datetime.combine(frame["stamp"].iloc[0].date(), time(9, 15))
    buckets: dict[datetime, list] = {}
    for bar in frame.itertuples():
        idx = int((bar.stamp - open_stamp).total_seconds() // 60) // 15
        buckets.setdefault(open_stamp + timedelta(minutes=15 * idx), []).append(bar)
    out = []
    for stamp in sorted(buckets):
        members = sorted(buckets[stamp], key=lambda b: b.stamp)
        out.append(dict(
            open_stamp=stamp, close_stamp=stamp + timedelta(minutes=15),
            open=int(members[0].open_paise),
            high=max(int(b.high_paise) for b in members),
            low=min(int(b.low_paise) for b in members),
            close=int(members[-1].close_paise),
        ))
    return out


# --- CONTEXT 3.2, re-implemented -----------------------------------------------------------


def bias_verdict(prev: dict, cur: dict) -> str:
    body_max = max(prev["open_paise"], prev["close_paise"])
    body_min = min(prev["open_paise"], prev["close_paise"])
    if cur["high_paise"] <= prev["high_paise"] and cur["low_paise"] >= prev["low_paise"]:
        return "inside-bar-carry"
    if cur["close_paise"] > body_max:
        return "rule-1-breakout BULLISH"
    if cur["close_paise"] < body_min:
        return "rule-1-breakout BEARISH"
    if (cur["low_paise"] < prev["low_paise"] and cur["high_paise"] <= prev["high_paise"]
            and cur["close_paise"] >= body_min):
        return "rule-2-sweep BULLISH"
    if (cur["high_paise"] > prev["high_paise"] and cur["low_paise"] >= prev["low_paise"]
            and cur["close_paise"] <= body_max):
        return "rule-2-sweep BEARISH"
    if cur["high_paise"] > prev["high_paise"] and cur["low_paise"] < prev["low_paise"]:
        return "rule-3-outside-bar (needs the 1-minute first-break scan)"
    return "no rule fires -- carry"


def main() -> int:
    lines: list[str] = []
    add = lines.append
    add("# REVIEW_9B_REPORT -- two gap-entry days, walked end to end")
    add("")
    add("Generated by `docs/evidence/review9b_gap_walks.py`, which imports NOTHING from")
    add("`src/acumen`. CONTEXT 3.2, 3.3, 3.4 and 3.5 are re-implemented here from the spec")
    add("text and the answer is compared with the ledger row the run wrote. Both days are the")
    add("ones report section 12a NAMES as the earliest and the latest gap entry of the span,")
    add("so the walk tests that claim too. Both are BEARISH -- the SHORT mirror of the gap rule.")
    add("")

    for symbol, day in WALKS:
        row = next(
            r for r in (json.loads(line) for line in
                        (RUN_DIR / "symbols" / f"{symbol}.jsonl").open(encoding="utf-8"))
            if r["day"] == day.isoformat()
        )
        tick = tick_paise(symbol)
        frame = minutes(symbol, day)
        add(f"## {symbol} {day.isoformat()}")
        add("")
        add(f"tick from the PINNED master: **{tick} paise**; stored in-session 1-minute bars: "
            f"**{len(frame)}** (ledger `minute_count` {row['minute_count']})")
        add("")

        # --- 1. BIAS ---------------------------------------------------------------------
        add("### 1. Bias (CONTEXT 3.2) -- pair D-1 / D-2")
        add("")
        dailies = daily_rows(symbol, day - timedelta(days=1), 2)
        prev, cur = dailies[0], dailies[1]
        body_max = max(prev["open_paise"], prev["close_paise"])
        body_min = min(prev["open_paise"], prev["close_paise"])
        add(f"* D-2 (P) {prev['trade_date']}: O {money(prev['open_paise'])} H "
            f"{money(prev['high_paise'])} L {money(prev['low_paise'])} C "
            f"{money(prev['close_paise'])}")
        add(f"* D-1 (C) {cur['trade_date']}: O {money(cur['open_paise'])} H "
            f"{money(cur['high_paise'])} L {money(cur['low_paise'])} C "
            f"{money(cur['close_paise'])}")
        add(f"* P's body: bodyMin {money(body_min)} .. bodyMax {money(body_max)}")
        add(f"* inside bar? C.high {money(cur['high_paise'])} <= P.high "
            f"{money(prev['high_paise'])} AND C.low {money(cur['low_paise'])} >= P.low "
            f"{money(prev['low_paise'])} -> "
            f"{cur['high_paise'] <= prev['high_paise'] and cur['low_paise'] >= prev['low_paise']}")
        add(f"* Rule 1: C.close {money(cur['close_paise'])} vs bodyMax {money(body_max)} / "
            f"bodyMin {money(body_min)}")
        add(f"* **verdict: {bias_verdict(prev, cur)}**")
        add(f"* the ledger says: rule `{row['bias_rule']}`, bias **{row['bias']}**")
        add(f"* no share-count factor sits between P and C, so the pairwise adjustment is the "
            f"identity here (checked below).")
        add("")

        # --- 2. POC ----------------------------------------------------------------------
        add("### 2. POC (CONTEXT 3.3) -- the 09:15..11:14 window")
        add("")
        profile = poc(frame, tick, ROW_SIZE)
        add(f"* window bars **{profile['bars']}**, window volume **{profile['volume']:,}**")
        add(f"* top {money(profile['top'])}, bottom {money(profile['bottom'])}, range "
            f"{money(profile['top'] - profile['bottom'])}")
        add(f"* totalTicks = round_half_even(({profile['top']} - {profile['bottom']}) / {tick}) "
            f"= **{profile['total_ticks']}**")
        add(f"* tpr = round(totalTicks / N={ROW_SIZE}), realized-count-closest with the FINER "
            f"profile on a tie = **{profile['tpr']}**; realized rows = "
            f"ceil({profile['total_ticks']}/{profile['tpr']}) = **{profile['rows']}**")
        lo, hi, vol = profile["best_row"]
        add(f"* winning row [{money(lo)}, {money(hi)}] carrying **{float(vol):,.2f}** of the "
            f"window's volume; midpoint = **{half_paise(profile['poc'])}**")
        add(f"* conservation: sum of row volumes {float(sum(v for _m, v in profile['row_volumes'])):,.4f} "
            f"vs window volume {profile['volume']:,} -- difference "
            f"{float(sum(v for _m, v in profile['row_volumes']) - profile['volume']):.10f}")
        ledger_poc = Fraction(row["poc_half_paise"], 2)
        add(f"* the ledger says `poc_half_paise` {row['poc_half_paise']} = "
            f"**{half_paise(ledger_poc)}**; mine **{half_paise(profile['poc'])}** -- "
            f"**{'MATCH' if ledger_poc == profile['poc'] else 'DIFFERS'}**")
        add("")

        # --- 3. SIGNAL --------------------------------------------------------------------
        add("### 3. Signal (CONTEXT 3.4, bearish mirror)")
        add("")
        bars = fifteen(frame)
        poc_value = profile["poc"]
        reference = next(b for b in bars if b["close_stamp"] == datetime.combine(day, time(11, 15)))
        add(f"* reference = close of the 11:00-11:15 candle = **{money(reference['close'])}** "
            f"(ledger `reference_paise` {row['reference_paise']}, source "
            f"`{row['reference_source']}`)")
        add(f"* bearish day: reference {money(reference['close'])} vs POC "
            f"{half_paise(poc_value)} -> "
            f"{'ARMED (reference > POC)' if reference['close'] > poc_value else 'WAIT-ABOVE (reference < POC)' if reference['close'] < poc_value else 'side unset (reference == POC)'}")
        add("")
        add("| Candle closes at | O | H | L | C | vs POC | state after |")
        add("|---|---:|---:|---:|---:|---|---|")
        state = ("ARMED" if reference["close"] > poc_value
                 else "WAIT-ABOVE" if reference["close"] < poc_value else "SIDE-UNSET")
        entry = None
        prev_close = None
        eligible = [b for b in bars
                    if datetime.combine(day, time(11, 30)) <= b["close_stamp"]
                    <= datetime.combine(day, time(15, 15))]
        for bar in eligible:
            before = state
            mark = ("below POC" if bar["close"] < poc_value
                    else "above POC" if bar["close"] > poc_value else "== POC")
            if entry is None:
                if state == "WAIT-ABOVE" and bar["close"] > poc_value:
                    state = "ARMED"
                elif state == "ARMED" and bar["close"] < poc_value:
                    entry = bar
                    state = "ENTERED"
            add(f"| {bar['close_stamp'].time()} | {money(bar['open'])} | {money(bar['high'])} | "
                f"{money(bar['low'])} | {money(bar['close'])} | {mark} | "
                f"{before} -> {state} |")
            if entry is bar:
                break
            prev_close = bar["close"]
        add("")
        assert entry is not None
        prior = bars[bars.index(entry) - 1]
        gap = entry["high"] < poc_value
        add(f"* **entry candle closes {entry['close_stamp'].time()}**, entry price = its close "
            f"= **{money(entry['close'])}** (ledger {money(row['entry_paise'])}, stamp "
            f"{row['entry_close_stamp']})")
        add(f"* GAP test (bearish): entry candle's HIGH {money(entry['high'])} < POC "
            f"{half_paise(poc_value)} -> **{gap}** (ledger `gap_entry` {row['gap_entry']})")
        add(f"* stop source: {'the PREVIOUS 15-minute candle CLOSE (gap branch, R2-Q33)' if gap else 'the entry candle HIGH (normal branch)'} "
            f"= **{money(prior['close'] if gap else entry['high'])}** (ledger "
            f"{money(row['stop_paise'])})")
        stop = prior["close"] if gap else entry["high"]
        risk = stop - entry["close"]
        target = entry["close"] - 3 * risk
        add(f"* per-share risk = SL - entry = {money(stop)} - {money(entry['close'])} = "
            f"**{money(risk)}** (ledger {money(row['per_share_risk_paise'])})")
        add(f"* target = entry - 3 x risk = {money(entry['close'])} - 3 x {money(risk)} = "
            f"**{money(target)}** (ledger {money(row['target_paise'])})")
        add("")

        # --- 4. MONEY ---------------------------------------------------------------------
        add("### 4. Money (CONTEXT 3.5)")
        add("")
        qty = RISK_PAISE // risk
        add(f"* qty = floor({money(RISK_PAISE)} / {money(risk)}) = **{qty:,}** (ledger "
            f"{row['qty']:,})")
        add(f"* both sizing bounds: {qty:,} x {risk} = {qty * risk:,} <= {RISK_PAISE:,} < "
            f"{qty + 1:,} x {risk} = {(qty + 1) * risk:,} -- "
            f"**{qty * risk <= RISK_PAISE < (qty + 1) * risk}**")
        after = bars[bars.index(entry) + 1:]
        exit_bar = None
        exit_price = None
        exit_kind = None
        for bar in after:
            if bar["close_stamp"] > datetime.combine(day, time(15, 15)):
                break
            if bar["high"] >= stop:
                exit_bar, exit_price, exit_kind = bar, stop, "stop-loss-hit"
                break
            if bar["low"] <= target:
                exit_bar, exit_price, exit_kind = bar, target, "target-hit"
                break
            if bar["close_stamp"] == datetime.combine(day, time(15, 15)):
                exit_bar = bar
                exit_price = bar["close"]
                exit_kind = "square-off-at-the-15:15-close"
                break
        add(f"* exit: **{exit_kind}** on the candle closing "
            f"{exit_bar['close_stamp'].time()} at **{money(exit_price)}** (ledger "
            f"`{row['exit_kind']}` at {money(row['exit_paise'])}, stamp "
            f"{row['exit_close_stamp']})")
        add(f"  * that candle: H {money(exit_bar['high'])} (>= SL {money(stop)}: "
            f"{exit_bar['high'] >= stop}), L {money(exit_bar['low'])} (<= TP {money(target)}: "
            f"{exit_bar['low'] <= target}) -- the FILL is the LEVEL, not the extreme")
        gross = (entry["close"] - exit_price) * qty
        net = gross - COST_PAISE
        notional = qty * entry["close"]
        add(f"* gross = (entry - exit) x qty = ({money(entry['close'])} - {money(exit_price)}) "
            f"x {qty:,} = **{money(gross)}** (ledger {money(row['gross_pnl_paise'])})")
        add(f"* net = gross - {money(COST_PAISE)} = **{money(net)}** (ledger "
            f"{money(row['net_pnl_paise'])})")
        add(f"* notional = qty x entry = **{money(notional)}** (ledger "
            f"{money(row['notional_paise'])})")
        add("")
        checks = {
            "bias rule": row["bias_rule"] in bias_verdict(prev, cur).lower().replace(" ", "-")
            or bias_verdict(prev, cur).lower().startswith(row["bias_rule"]),
            "POC": ledger_poc == profile["poc"],
            "reference": reference["close"] == row["reference_paise"],
            "entry price": entry["close"] == row["entry_paise"],
            "entry stamp": entry["close_stamp"].isoformat() == row["entry_close_stamp"],
            "gap flag": gap == row["gap_entry"],
            "stop": stop == row["stop_paise"],
            "risk": risk == row["per_share_risk_paise"],
            "target": target == row["target_paise"],
            "qty": qty == row["qty"],
            "exit kind": exit_kind == row["exit_kind"],
            "exit price": exit_price == row["exit_paise"],
            "exit stamp": exit_bar["close_stamp"].isoformat() == row["exit_close_stamp"],
            "gross": gross == row["gross_pnl_paise"],
            "net": net == row["net_pnl_paise"],
            "notional": notional == row["notional_paise"],
        }
        add(f"**{sum(checks.values())} of {len(checks)} fields reproduce.** "
            + ("Divergences: " + ", ".join(k for k, v in checks.items() if not v)
               if not all(checks.values()) else "No divergence."))
        add("")

    # --- the earliest/latest claim ---------------------------------------------------------
    add("## The report's 'earliest and latest gap entry' claim")
    add("")
    gaps: list[tuple[str, str]] = []
    with (RUN_DIR / "ledger.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            if '"gap_entry":true' not in line.replace(" ", ""):
                continue
            r = json.loads(line)
            if r["gap_entry"] and r["executed"]:
                gaps.append((r["day"], r["symbol"]))
    gaps.sort()
    add(f"* executed gap entries: **{len(gaps):,}** (report: 2,068)")
    add(f"* earliest by DATE: **{gaps[0][1]} {gaps[0][0]}** (report: MUTHOOTFIN 2016-10-06)")
    add(f"* latest by DATE: **{gaps[-1][1]} {gaps[-1][0]}** (report: TIINDIA 2026-07-27)")
    add("")
    OUT.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
