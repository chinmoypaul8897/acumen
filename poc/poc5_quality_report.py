"""PoC 5 - Data-quality scan of everything poc3 downloaded. Run AFTER poc3. No API calls."""
import csv
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
rows = []
for f in sorted(DATA_DIR.glob("*_1min.csv")):
    df = pd.read_csv(f, parse_dates=["ts"])
    sym, ds = f.stem.rsplit("_1min", 1)[0].rsplit("_", 1)
    n = len(df)
    zero_vol = int((df["volume"] == 0).sum())
    dupes = int(df["ts"].duplicated().sum())
    # expected minutes 09:15..15:29 = 375
    missing = 375 - n
    bad_ohlc = int(((df["high"] < df["low"]) | (df["close"] > df["high"]) | (df["close"] < df["low"])).sum())
    rows.append({"symbol": sym, "date": ds, "candles": n, "missing_minutes": missing,
                 "zero_volume_candles": zero_vol, "duplicate_timestamps": dupes, "impossible_ohlc": bad_ohlc})
    print(f"{sym} {ds}: candles={n} missing={missing} zerovol={zero_vol} dupes={dupes} badohlc={bad_ohlc}")

out = DATA_DIR / "quality_report.csv"
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else ["empty"])
    w.writeheader()
    w.writerows(rows)
print(f"\nSaved: {out}")
