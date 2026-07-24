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
