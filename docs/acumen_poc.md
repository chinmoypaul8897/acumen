# ACUMEN PoC — Handoff Brief for Claude Code

**You are Claude Code, running locally in this folder.** This file is your complete instruction set. Execute it top to bottom.

## Context (read first)

This is a data-audit PoC for "Acumen Intelligence" — a backtester + live screener for an intraday strategy on NSE F&O stocks. Before building, we must verify 4 things about Angel One's free SmartAPI using the owner's own API key:

1. Does the key/login work?
2. How far back does 1-minute equity data REALLY go? (docs claim 2016 — unproven)
3. Is candle volume trustworthy? (sum of 1-min volumes vs daily volume, per day)
4. What POC (Point of Control of a 9:15–11:15 volume profile) do three different volume-spreading methods produce? (TradingView doesn't document its method — we calibrate later against real TV charts)

**Hard rules for you:**
- READ-ONLY. Only `getCandleData`, `getProfile`, login and the public instrument master. NEVER call any order/GTT/funds endpoint. No order code may exist in this folder.
- NEVER print, echo, log, or paste the contents of `.env`. Never commit it. If the user pastes credentials into chat by mistake, tell them to rotate the key.
- Respect rate limits: the code already throttles to ~2 req/s with backoff. Do not "speed it up".
- If something fails, debug it, but do not change the testing logic (row math is verified against TradingView's documented example — leave `tv_rows` and `build_profile` semantics untouched).
- Final deliverable: a filled `RESULTS.md` (template at the bottom) + the CSVs in `data/`.

## Step 1 — Create the project files

Create each file below with exactly this content.

### File: `.gitignore`

```
.env
cache/
data/
__pycache__/
```

### File: `requirements.txt`

```
smartapi-python>=1.4.8
pyotp>=2.9.0
python-dotenv>=1.0.0
pandas>=2.0.0
requests>=2.31.0
websocket-client>=1.6.0
logzero>=1.7.0
```

### File: `.env` (create with these placeholder lines, then STOP and ask the user to fill it)

```
SMARTAPI_KEY=
SMARTAPI_CLIENT_CODE=
SMARTAPI_PIN=
SMARTAPI_TOTP_SECRET=
```

### File: `common.py`

```python
"""ACUMEN PoC - shared helpers: login, instrument lookup, rate-limited candle fetch."""
import json
import os
import time
from pathlib import Path

import pandas as pd
import pyotp
import requests
from dotenv import load_dotenv

SCRIP_MASTER_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
CACHE_DIR = Path(__file__).parent / "cache"
DATA_DIR = Path(__file__).parent / "data"
CACHE_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# --- global throttle: SmartAPI historical limit is 3 req/s; we stay at ~2/s to be polite ---
_MIN_GAP = 0.5
_last_call = [0.0]


def _throttle():
    wait = _MIN_GAP - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()


def login():
    """Log in to SmartAPI using .env credentials. Returns a SmartConnect object."""
    load_dotenv(Path(__file__).parent / ".env")
    key = os.getenv("SMARTAPI_KEY")
    client = os.getenv("SMARTAPI_CLIENT_CODE")
    pin = os.getenv("SMARTAPI_PIN")
    totp_secret = os.getenv("SMARTAPI_TOTP_SECRET")
    if not all([key, client, pin, totp_secret]):
        raise SystemExit("ERROR: .env is missing values. Fill all 4 lines.")

    from SmartApi import SmartConnect  # imported here so pip errors are clearer

    api = SmartConnect(api_key=key)
    totp = pyotp.TOTP(totp_secret.replace(" ", "")).now()
    resp = api.generateSession(client, pin, totp)
    if not resp or not resp.get("status"):
        raise SystemExit(f"LOGIN FAILED: {resp}")
    return api


def get_scrip_master():
    """Download (once) and cache the full instrument list."""
    cache_file = CACHE_DIR / "scrip_master.json"
    if cache_file.exists() and cache_file.stat().st_size > 1000:
        return json.loads(cache_file.read_text(encoding="utf-8"))
    print("Downloading instrument master (~40 MB, one time)...")
    r = requests.get(SCRIP_MASTER_URL, timeout=120)
    r.raise_for_status()
    cache_file.write_text(r.text, encoding="utf-8")
    return r.json()


def find_equity(symbol):
    """Return (token, tick_size_in_rupees) for an NSE cash equity like 'RELIANCE'."""
    target = f"{symbol.upper()}-EQ"
    for row in get_scrip_master():
        if row.get("exch_seg") == "NSE" and row.get("symbol") == target:
            tick = float(row.get("tick_size", "5"))
            tick = tick / 100.0 if tick >= 1 else tick  # master stores paise
            return row["token"], tick
    raise SystemExit(f"Symbol {target} not found in instrument master.")


def fetch_candles(api, token, interval, fromdate, todate, max_retries=5):
    """Rate-limited getCandleData with backoff. Returns list of [ts,o,h,l,c,v] (may be empty)."""
    params = {
        "exchange": "NSE",
        "symboltoken": str(token),
        "interval": interval,
        "fromdate": fromdate,  # "YYYY-MM-DD HH:MM"
        "todate": todate,
    }
    for attempt in range(max_retries):
        _throttle()
        try:
            resp = api.getCandleData(params)
            if resp and resp.get("status") and resp.get("data") is not None:
                return resp["data"]
            if resp and resp.get("status") and resp.get("data") is None:
                return []  # successful call, genuinely no candles in this window
            msg = str(resp.get("message", "") if resp else "no response").lower()
            if resp is not None and resp.get("data") is None and ("no data" in msg or resp.get("errorcode") == "AB1004"):
                return []
        except Exception as e:  # network hiccup / 403 burst
            msg = str(e).lower()
        sleep_s = 2 ** attempt
        print(f"    retry {attempt + 1}/{max_retries} in {sleep_s}s ({msg[:80]})")
        time.sleep(sleep_s)
    print("    WARNING: giving up on this window (treated as EMPTY - rerun to confirm).")
    return []


def candles_to_df(raw):
    if not raw:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"])
    return df
```

### File: `poc1_login_test.py`

```python
"""PoC 1 - Does the key work? Logs in, prints your profile, fetches one candle."""
from common import login, find_equity, fetch_candles

api = login()
prof = api.getProfile(api.refresh_token) if hasattr(api, "refresh_token") else None
try:
    name = prof["data"]["name"] if prof and prof.get("data") else "(profile fetch skipped)"
except Exception:
    name = "(profile fetch skipped)"
print(f"LOGIN OK. Account: {name}")

token, tick = find_equity("TCS")
print(f"TCS token={token}, tick size=Rs {tick}")

data = fetch_candles(api, token, "ONE_DAY", "2026-07-13 09:15", "2026-07-20 15:30")
print(f"Fetched {len(data)} daily candles for TCS last week. Sample: {data[-1] if data else 'EMPTY'}")
print("\nPOC 1 PASSED - key, TOTP and data access all work." if data else "\nPOC 1 PROBLEM - login worked but no data returned.")
```

### File: `poc2_depth_probe.py`

```python
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
```

### File: `poc3_volume_poc_test.py`

```python
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

        daily = fetch_candles(api, token, "ONE_DAY", f"{ds} 09:15", f"{ds} 15:30")
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
```

### File: `poc4_latency_test.py`

```python
"""PoC 4 - How fast does a just-closed 15-min candle appear? MARKET HOURS ONLY (Mon-Fri 9:30-15:15 IST)."""
import time
from datetime import datetime, timedelta

from common import login, find_equity, fetch_candles

api = login()
token, _ = find_equity("TCS")
print("Waiting for 15-min boundaries (this script is a stopwatch by nature)...")

for _ in range(3):
    now = datetime.now()
    nxt = (now + timedelta(minutes=15 - now.minute % 15)).replace(second=0, microsecond=0)
    print(f"\nNext boundary: {nxt.strftime('%H:%M')} (waiting {(nxt - now).total_seconds():.0f}s)")
    time.sleep(max(0, (nxt - now).total_seconds()))

    target_open = (nxt - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M")
    ds = nxt.strftime("%Y-%m-%d")
    t0, latency = time.time(), None
    while time.time() - t0 < 60:
        raw = fetch_candles(api, token, "FIFTEEN_MINUTE", f"{ds} 09:15", f"{ds} 15:30")
        stamps = [r[0][:16].replace("T", " ") for r in raw]
        if target_open in stamps:
            latency = time.time() - t0
            break
        time.sleep(1)
    print(f"Candle opening {target_open} appeared {latency:.1f}s after close." if latency
          else "Candle did NOT appear within 60s.")
print("\nDone.")
```

### File: `poc5_quality_report.py`

```python
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
```

## Step 2 — Environment

1. Verify Python 3.10+ exists (`python --version`). If missing, tell the user to install from python.org with "Add to PATH".
2. `pip install -r requirements.txt`
3. Check `.env` is filled (all 4 values non-empty). If not, STOP and ask the user to fill it. Do not read the values aloud.

## Step 3 — Run sequence

| Order | Command | When | Expected time |
|---|---|---|---|
| 1 | `python poc1_login_test.py` | any time | 10 s |
| 2 | `python poc2_depth_probe.py` | any time | 3–6 min |
| 3 | `python poc3_volume_poc_test.py` | best after 15:30 IST | ~2 min |
| 4 | `python poc5_quality_report.py` | right after poc3 | 5 s |
| 5 | `python poc4_latency_test.py` | ONLY Mon–Fri 09:30–15:15 IST; skip otherwise and note it | ~35 min |

Notes: `retry x/5` lines are normal (SmartAPI throws false rate-limit errors; backoff handles them). A window that says "giving up" should be re-run once before being reported as empty. If login fails with TOTP error, re-check the TOTP secret has no spaces.

## Step 4 — Fill RESULTS.md

Create `RESULTS.md` with the template below, filled from the actual outputs. This file goes back to the architect (the other Claude session). Do not include any credential material in it.

```markdown
# ACUMEN PoC RESULTS — run on <date>, machine timezone <tz>

## A. Login (poc1)
- Login worked: YES/NO
- Notes/errors:

## B. 1-min depth (poc2) — paste the table
| symbol | earliest 1-min month |
|---|---|
- Daily depth probe (RELIANCE): 1996-01: ? / 2000-01: ? / 2005-01: ? / 2010-01: ?
- Contradictions vs the "2016" claim:

## C. Volume sanity (poc3)
- Paste volume_poc_summary.csv as a table
- gap_pct pattern: steady small positive / wild / negative? Verdict in one line:

## D. POC methods (poc3)
- For each symbol-day: do the three methods agree or differ? By how much (in Rs)?

## E. Data quality (poc5)
- Paste quality_report.csv as a table
- Any day with missing_minutes > 5, zero-volume streaks, dupes, impossible OHLC?

## F. Latency (poc4)
- Ran: YES/NO (if market was closed, say so)
- Three latency values:

## G. Errors observed across all runs
- How many retry events, any give-ups, anything strange:

## H. Files attached alongside this report
- data/depth_probe_results.csv, data/volume_poc_summary.csv, data/quality_report.csv
```

## Step 5 — Manual step for the human (not for Claude Code)

The TradingView comparison cannot be automated here: open TradingView → each tested stock → 15-min chart → draw **Fixed Range Volume Profile** from 09:15 to 11:15 on 3–4 tested dates → write the TV POC values into RESULTS.md section D next to the three computed methods. Whichever method matches TV wins.

**End of brief. Execute Step 1 now.**

