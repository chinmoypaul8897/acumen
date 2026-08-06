"""REVIEW_9B_REPORT: the 15-minute portfolio equity path, re-assembled from the raw minute lake.

Written by the chunk-9B REPORT REVIEW session (06-Aug-2026). Companion to
`review9b_report_recompute.py`, which does the close-to-close half.

**It imports nothing from `src/acumen`.** The 1-minute parquet is read with pandas and
aggregated to 15-minute candles HERE, from CONTEXT 7-E1/E12/E2 as written: session stamps are
09:15..15:29 (a stray is dropped at the CANDLE level, Q-17), a 15-minute bar covers the fifteen
open-stamps `[T, T+15)` and CLOSES at `T+15`, and its close is the last 1-minute close inside it.
Every open position is then marked at each candle close it was held through, the exit candle at
its EXIT LEVEL (a stop or target fills at its level even when the candle ran past it), the flat
Rs 100 charged from the ENTRY mark, and the marks summed across positions onto the equity the day
opened with -- the architect's Q-16(b) construction, re-implemented rather than re-run.

Read-only over the stores. Writes exactly one markdown file inside the repo.

    python docs/evidence/review9b_path_recompute.py

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from fractions import Fraction
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
DATA_ROOT = Path("C:/Users/chinm/acumen-data")
RUN_DIR = DATA_ROOT / "backtests" / "chunk9b_full"
MINUTES = DATA_ROOT / "minute_store" / "minute"
OUT = REPO / "docs" / "evidence" / "review9b_path_recompute.md"

CAPITAL_PAISE = 10_000_000
SESSION_OPEN = time(9, 15)
SESSION_LAST_MINUTE = time(15, 29)


def money(paise: int) -> str:
    sign = "-" if paise < 0 else ""
    whole, frac = divmod(abs(int(paise)), 100)
    return f"{sign}Rs {whole:,}.{frac:02d}"


def pct(value: Fraction | None, places: int = 2) -> str:
    if value is None or value <= 0:
        return "n/a -- base at or below zero"
    scaled = value * 100 * (10**places)
    q, r = divmod(scaled.numerator, scaled.denominator)
    if r * 2 >= scaled.denominator:
        q += 1
    text = f"{q:0{places + 1}d}"
    return f"{int(text[:-places]):,}.{text[-places:]}%"


def fifteen_min_closes(frame: pd.DataFrame) -> dict[date, list[tuple[int, int]]]:
    """One symbol's stored minutes -> ``{day: [(close-stamp minute-of-day, close paise), ...]}``.

    CONTEXT 7-E2 first (drop a stray stamp at the CANDLE level), then CONTEXT 7-E12's grid: the
    bar covering open-stamps [T, T+15) CLOSES at T+15, and its close is the last 1-minute close
    inside it.
    """
    stamps = frame["stamp"]
    minute_of_day = stamps.dt.hour * 60 + stamps.dt.minute
    open_minute = SESSION_OPEN.hour * 60 + SESSION_OPEN.minute
    last_minute = SESSION_LAST_MINUTE.hour * 60 + SESSION_LAST_MINUTE.minute
    keep = (minute_of_day >= open_minute) & (minute_of_day <= last_minute)
    frame = frame.loc[keep]
    minute_of_day = minute_of_day.loc[keep]
    bucket = (minute_of_day - open_minute) // 15
    close_minute = open_minute + 15 * (bucket + 1)
    work = pd.DataFrame(
        {
            "day": stamps.loc[keep].dt.date,
            "close_minute": close_minute.astype("int64"),
            "minute_of_day": minute_of_day.astype("int64"),
            "close_paise": frame["close_paise"].astype("int64").to_numpy(),
        }
    )
    work = work.sort_values(["day", "close_minute", "minute_of_day"], kind="mergesort")
    last = work.groupby(["day", "close_minute"], sort=True)["close_paise"].last()
    out: dict[date, list[tuple[int, int]]] = defaultdict(list)
    for (day, close_minute), close_paise in last.items():
        out[day].append((int(close_minute), int(close_paise)))
    return out


def stamp_text(day: date, minute_of_day: int | None) -> str:
    if minute_of_day is None:
        return f"{day.isoformat()} (day close)"
    return (datetime.combine(day, time()) + timedelta(minutes=minute_of_day)).isoformat(
        sep=" ", timespec="minutes"
    )


def main() -> int:
    executed: dict[str, list[dict]] = defaultdict(list)
    walked_days: set[date] = set()
    daily_net: dict[date, int] = defaultdict(int)
    with (RUN_DIR / "ledger.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            r = json.loads(line)
            walked_days.add(date.fromisoformat(r["day"]))
            if r["executed"]:
                executed[r["symbol"]].append(r)
                daily_net[date.fromisoformat(r["day"])] += r["net_pnl_paise"]
    day_index = sorted(walked_days)
    total_trades = sum(len(v) for v in executed.values())
    print(f"{total_trades:,} executed trades over {len(executed)} symbols", file=sys.stderr)

    # --- assemble every trade's marks ---------------------------------------------------------
    by_day: dict[date, list[dict]] = defaultdict(list)
    marks_total = 0
    reconciling = 0
    entry_mark_is_cost = 0
    outside_session = 0
    for index, symbol in enumerate(sorted(executed), start=1):
        rows = executed[symbol]
        months = sorted({r["day"][:7] for r in rows})
        frames = []
        for month in months:
            path = MINUTES / symbol / f"{symbol}_{month}.parquet"
            if path.is_file():
                frames.append(pd.read_parquet(path, columns=["stamp", "close_paise"]))
        closes = fifteen_min_closes(pd.concat(frames)) if frames else {}
        for r in rows:
            day = date.fromisoformat(r["day"])
            entry_stamp = datetime.fromisoformat(r["entry_close_stamp"])
            entry_m = entry_stamp.hour * 60 + entry_stamp.minute
            exit_stamp = datetime.fromisoformat(r["exit_close_stamp"] or r["entry_close_stamp"])
            exit_m = exit_stamp.hour * 60 + exit_stamp.minute
            exit_paise = r["exit_paise"] if r["exit_paise"] is not None else r["entry_paise"]
            marks = [
                (m, p) for m, p in closes.get(day, ()) if entry_m <= m <= exit_m
            ]
            if not marks or marks[0][0] != entry_m:
                marks.insert(0, (entry_m, r["entry_paise"]))
            if marks[-1][0] == exit_m:
                marks[-1] = (exit_m, exit_paise)
            else:
                marks.append((exit_m, exit_paise))
            sign = -1 if r["side"] == "short" else 1
            trade = dict(
                sign=sign, qty=r["qty"], entry=r["entry_paise"], cost=r["cost_paise"],
                net=r["net_pnl_paise"], marks=marks, symbol=symbol, day=day,
            )
            marks_total += len(marks)
            last_price = marks[-1][1]
            if sign * (last_price - r["entry_paise"]) * r["qty"] - r["cost_paise"] == r["net_pnl_paise"]:
                reconciling += 1
            if sign * (marks[0][1] - r["entry_paise"]) * r["qty"] - r["cost_paise"] == -r["cost_paise"]:
                entry_mark_is_cost += 1
            if marks[0][0] < 9 * 60 + 30 or marks[-1][0] > 15 * 60 + 30:
                outside_session += 1
            by_day[day].append(trade)
        if index % 20 == 0 or index == len(executed):
            print(f"  {index}/{len(executed)} symbols, {marks_total:,} marks", file=sys.stderr)

    # --- the portfolio path ----------------------------------------------------------------
    points: list[tuple[date, int | None, int, int]] = []
    equity = CAPITAL_PAISE
    for day in day_index:
        opening = equity
        trades = by_day.get(day, ())
        stamps = sorted({m for t in trades for m, _p in t["marks"]})
        for stamp in stamps:
            total = 0
            live = 0
            for t in trades:
                if stamp < t["marks"][0][0]:
                    continue
                price = t["marks"][0][1]
                for m, p in t["marks"]:
                    if m > stamp:
                        break
                    price = p
                total += t["sign"] * (price - t["entry"]) * t["qty"] - t["cost"]
                if stamp < t["marks"][-1][0]:
                    live += 1
            points.append((day, stamp, opening + total, live))
        equity = opening + daily_net.get(day, 0)
        points.append((day, None, equity, 0))

    # --- excursions ---------------------------------------------------------------------------
    peak = CAPITAL_PAISE
    peak_i = -1
    best = (0, None, None, 0)
    for i, (_d, _s, eq, _l) in enumerate(points):
        fall = peak - eq
        if fall > best[0]:
            best = (fall, peak_i, i, peak)
        if eq > peak:
            peak, peak_i = eq, i
    dd_amount, dd_peak_i, dd_trough_i, dd_peak_equity = best
    dd_recovered = None
    for j in range(dd_trough_i + 1, len(points)):
        if points[j][2] >= dd_peak_equity:
            dd_recovered = j
            break

    trough = CAPITAL_PAISE
    trough_i = -1
    bestr = (0, None, None, 0)
    for i, (_d, _s, eq, _l) in enumerate(points):
        rise = eq - trough
        if rise > bestr[0]:
            bestr = (rise, trough_i, i, trough)
        if eq < trough:
            trough, trough_i = eq, i
    ru_amount, ru_trough_i, ru_peak_i, ru_trough_equity = bestr
    ru_given_back = None
    for j in range(ru_peak_i + 1, len(points)):
        if points[j][2] <= ru_trough_equity:
            ru_given_back = j
            break

    def point_text(i: int | None) -> str:
        if i is None:
            return "the run's opening capital"
        day, stamp, _eq, _l = points[i]
        return stamp_text(day, stamp)

    # --- the day-close identity --------------------------------------------------------------
    closes_match = 0
    equity_walk = CAPITAL_PAISE
    for day in day_index:
        equity_walk += daily_net.get(day, 0)
        last = [p for p in points if p[0] == day and p[1] is None]
        if last and last[0][2] == equity_walk:
            closes_match += 1

    lines: list[str] = []
    add = lines.append
    add("# REVIEW_9B_REPORT -- the 15-minute portfolio path, re-assembled")
    add("")
    add("Generated by `docs/evidence/review9b_path_recompute.py`, which imports NOTHING from")
    add("`src/acumen`: the 1-minute parquet is read with pandas and aggregated to 15-minute")
    add("candles here, from CONTEXT 7-E1/E2/E12 as written.")
    add("")
    add("## The assembly")
    add("")
    add(f"* executed trades: **{total_trades:,}**")
    add(f"* 15-minute marks assembled: **{marks_total:,}** (report: 1,101,029)")
    add(f"* paths whose LAST mark reproduces the ledger's net PnL exactly: "
        f"**{reconciling:,} of {total_trades:,}** (report: 188,345 of 188,345)")
    add(f"* paths whose FIRST mark is exactly -Rs 100.00 (the cost charged at entry, B194): "
        f"**{entry_mark_is_cost:,} of {total_trades:,}**")
    add(f"* paths with a mark outside 09:30..15:30 (the valid 15-minute close grid): "
        f"**{outside_session}**")
    add(f"* path observations: **{len(points):,}** (report: 40,981)")
    add(f"* of which day-close observations: **{sum(1 for p in points if p[1] is None):,}** "
        f"(one per walked day: {len(day_index):,})")
    add(f"* days whose LAST path observation equals that day's closing equity on the daily "
        f"curve: **{closes_match:,} of {len(day_index):,}**")
    add(f"* final path observation: **{money(points[-1][2])}**")
    add("")
    add("## Max drawdown on the path")
    add("")
    add(f"**{money(dd_amount)} "
        f"({pct(Fraction(dd_amount, dd_peak_equity) if dd_peak_equity > 0 else None)}), "
        f"{point_text(dd_peak_i)} -> {point_text(dd_trough_i)}, "
        f"{dd_trough_i - (dd_peak_i if dd_peak_i is not None else -1):,} observation(s) of "
        f"{len(points):,}, recovered "
        f"{point_text(dd_recovered) if dd_recovered is not None else 'never inside the span'}.**")
    add("")
    add("Report: Rs 16,864,934.22 (13174.01%), 2016-10-07 11:45 -> 2026-07-30 15:00, 40,909 "
        "observation(s) of 40,981, recovered never inside the span.")
    add("")
    add(f"* the peak equity the fall is measured from: **{money(dd_peak_equity)}**")
    add(f"* observations at or above that peak AFTER the trough: "
        f"**{sum(1 for p in points[dd_trough_i + 1:] if p[2] >= dd_peak_equity)}** -- never "
        f"recovered")
    add(f"* the trough is the LAST observation of the run: "
        f"**{dd_trough_i == len(points) - 1 or points[dd_trough_i][0] == day_index[-1]}** "
        f"(index {dd_trough_i:,} of {len(points) - 1:,})")
    add(f"* the path drawdown EXCEEDS the close-to-close one, as it must (it sees falls the "
        f"15:15 close does not): {money(dd_amount)} vs Rs 16,852,007.80 -- "
        f"**{dd_amount > 1685200780}**")
    add("")
    add("## Max run-up on the path")
    add("")
    add(f"**{money(ru_amount)} "
        f"({pct(Fraction(ru_amount, ru_trough_equity) if ru_trough_equity > 0 else None)}), "
        f"{point_text(ru_trough_i)} -> {point_text(ru_peak_i)}, "
        f"{ru_peak_i - (ru_trough_i if ru_trough_i is not None else -1):,} observation(s) of "
        f"{len(points):,}, given back "
        f"{point_text(ru_given_back) if ru_given_back is not None else 'never inside the span'}.**")
    add("")
    add("Report: Rs 424,810.90 (% n/a), 2024-11-05 13:30 -> 2025-01-14 12:30, 795 "
        "observation(s) of 40,981, given back 2025-02-24 13:00.")
    add("")
    add(f"* the trough equity the rise is measured from: **{money(ru_trough_equity)}** -- at or "
        f"below zero: **{ru_trough_equity <= 0}**, so the percentage is refused")
    add(f"* printed trough-first (the order it happened): trough index {ru_trough_i:,} < peak "
        f"index {ru_peak_i:,}: **{ru_trough_i < ru_peak_i}**")
    add("")
    add("## Concurrency, from the same marks")
    add("")
    peak_live = max(p[3] for p in points)
    first_peak = next(p for p in points if p[3] == peak_live)
    add(f"* maximum positions open at one 15-minute observation: **{peak_live}**, first at "
        f"**{stamp_text(first_peak[0], first_peak[1])}** (report: 90, first reached "
        f"2026-05-07 12:45)")
    add("")
    OUT.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
