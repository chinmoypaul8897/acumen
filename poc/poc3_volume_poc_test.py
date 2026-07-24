"""PoC 3 - The decisive test: volume quality + POC computation (3 spreading methods)."""
import argparse
import csv
from datetime import date, time as dtime, timedelta

from common import login, find_equity, fetch_candles, candles_to_df, DATA_DIR

P = argparse.ArgumentParser()
P.add_argument("--rows", type=int, default=24, help="Row Size (Number of Rows) - trader's TV setting")
P.add_argument("--days", type=int, default=5, help="how many recent weekdays to test")
P.add_argument("--symbols", default="TCS,RELIANCE,HDFCBANK,DIXON,MANAPPURAM")
args = P.parse_args()


def tv_rows(top, bottom, n_rows, tick):
    """TradingView's documented row construction. Returns list of (row_low, row_high)."""
    total_ticks = max(1, round((top - bottom) / tick))
    raw = total_ticks / n_rows
    floor_t, ceil_t = max(1, int(raw)), max(1, int(raw) + (0 if raw == int(raw) else 1))

    def count_rows(tpr):
        full = total_ticks // tpr
        rem = total_ticks - full * tpr
        extra = (rem + tpr - 1) // tpr if rem else 0
        return full + extra

    tpr = floor_t if abs(count_rows(floor_t) - n_rows) <= abs(count_rows(ceil_t) - n_rows) else ceil_t
    rows, t = [], 0
    while t < total_ticks:
        span = min(tpr, total_ticks - t)
        rows.append((bottom + t * tick, bottom + (t + span) * tick))
        t += span
    return rows


def build_profile(df, n_rows, tick, method):
    top, bottom = df["high"].max(), df["low"].min()
    rows = tv_rows(top, bottom, n_rows, tick)
    vol = [0.0] * len(rows)
    for _, bar in df.iterrows():
        lo, hi, v = bar["low"], bar["high"], float(bar["volume"])
        if v == 0:
            continue
        touched = [i for i, (rl, rh) in enumerate(rows) if hi >= rl and lo < rh] or [0]
        if method == "close":
            c = bar["close"]
            idx = next((i for i, (rl, rh) in enumerate(rows) if rl <= c < rh), len(rows) - 1)
            vol[idx] += v
        elif method == "uniform":
            for i in touched:
                vol[i] += v / len(touched)
        elif method == "prorata":
            span = max(hi - lo, tick)
            for i in touched:
                rl, rh = rows[i]
                overlap = max(0.0, min(hi, rh) - max(lo, rl))
                vol[i] += v * (overlap / span)
    return [((rl + rh) / 2, vl) for (rl, rh), vl in zip(rows, vol)]


def poc_of(profile):
    return max(profile, key=lambda x: x[1])[0]


api = login()
symbols = [s.strip().upper() for s in args.symbols.split(",")]
days, d = [], date.today() - timedelta(days=1)
while len(days) < args.days:
    if d.weekday() < 5:
        days.append(d)
    d -= timedelta(days=1)

summary = []
for sym in symbols:
    token, tick = find_equity(sym)
    print(f"\n=== {sym} (tick Rs {tick}) ===")
    for day in days:
        ds = day.strftime("%Y-%m-%d")
        raw = fetch_candles(api, token, "ONE_MINUTE", f"{ds} 09:15", f"{ds} 15:30")
        if not raw:
            print(f"  {ds}: no data (holiday?)")
            continue
        df = candles_to_df(raw)
        df.to_csv(DATA_DIR / f"{sym}_{ds}_1min.csv", index=False)

        daily = fetch_candles(api, token, "ONE_DAY", f"{ds} 00:00", f"{ds} 15:30")
        day_vol = float(daily[0][5]) if daily else 0
        min_sum = float(df["volume"].sum())
        diff_pct = 100 * (day_vol - min_sum) / day_vol if day_vol else float("nan")

        win = df[(df["ts"].dt.time >= dtime(9, 15)) & (df["ts"].dt.time <= dtime(11, 14))]
        if win.empty:
            print(f"  {ds}: no morning window data")
            continue
        pocs = {m: poc_of(build_profile(win, args.rows, tick, m)) for m in ("close", "uniform", "prorata")}
        print(f"  {ds}: 1min-sum={min_sum:,.0f}  daily={day_vol:,.0f}  gap={diff_pct:+.2f}%  "
              f"POC close={pocs['close']:.2f} uniform={pocs['uniform']:.2f} prorata={pocs['prorata']:.2f}")
        summary.append({"symbol": sym, "date": ds, "rows": args.rows, "sum_1min_vol": min_sum,
                        "daily_vol": day_vol, "gap_pct": round(diff_pct, 3),
                        "poc_close": pocs["close"], "poc_uniform": pocs["uniform"],
                        "poc_prorata": pocs["prorata"]})

out = DATA_DIR / "volume_poc_summary.csv"
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(summary[0].keys()) if summary else ["empty"])
    w.writeheader()
    w.writerows(summary)
print(f"\nSaved: {out}")
