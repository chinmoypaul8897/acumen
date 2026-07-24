"""PoC 2 - How far back does 1-minute data REALLY go, per stock?"""
import csv

from common import login, find_equity, fetch_candles, DATA_DIR

SYMBOLS = ["RELIANCE", "SBIN", "TCS", "DIXON", "MANAPPURAM"]  # large caps + mid + smaller
PROBE_MONTHS = ["2016-01", "2016-06", "2016-10", "2017-01", "2018-01", "2019-01",
                "2020-01", "2021-01", "2021-12", "2022-06", "2023-01"]


def month_has_data(api, token, ym):
    y, m = ym.split("-")
    data = fetch_candles(api, token, "ONE_MINUTE", f"{y}-{m}-08 09:15", f"{y}-{m}-16 15:30")
    return len(data) > 0, len(data)


def months_between(a, b):
    ay, am = map(int, a.split("-"))
    by, bm = map(int, b.split("-"))
    out, y, m = [], ay, am
    while (y, m) <= (by, bm):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


api = login()
results = []
for sym in SYMBOLS:
    token, _ = find_equity(sym)
    print(f"\n=== {sym} (token {token}) ===")
    status = {}
    for ym in PROBE_MONTHS:
        ok, n = month_has_data(api, token, ym)
        status[ym] = ok
        print(f"  {ym}: {'DATA (' + str(n) + ' candles)' if ok else 'empty'}")
    earliest = None
    firsts = [ym for ym in PROBE_MONTHS if status[ym]]
    if firsts:
        first_ok = firsts[0]
        prev_empty = None
        for ym in PROBE_MONTHS:
            if ym == first_ok:
                break
            if not status[ym]:
                prev_empty = ym
        earliest = first_ok
        if prev_empty:
            gap = months_between(prev_empty, first_ok)[1:-1]
            lo, hi = 0, len(gap) - 1
            while lo <= hi:
                mid = (lo + hi) // 2
                ok, _ = month_has_data(api, token, gap[mid])
                print(f"  narrow {gap[mid]}: {'DATA' if ok else 'empty'}")
                if ok:
                    earliest, hi = gap[mid], mid - 1
                else:
                    lo = mid + 1
    print(f"  --> earliest month with 1-min data: {earliest or 'NONE FOUND'}")
    results.append({"symbol": sym, "earliest_1min_month": earliest or "NONE"})

token, _ = find_equity("RELIANCE")
print("\n=== RELIANCE daily-candle depth probe ===")
for ym in ["1996-01", "2000-01", "2005-01", "2010-01"]:
    y, m = ym.split("-")
    data = fetch_candles(api, token, "ONE_DAY", f"{y}-{m}-01 09:15", f"{y}-{m}-28 15:30")
    print(f"  {ym}: {'DATA' if data else 'empty'}")

out = DATA_DIR / "depth_probe_results.csv"
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["symbol", "earliest_1min_month"])
    w.writeheader()
    w.writerows(results)
print(f"\nSaved: {out}")
