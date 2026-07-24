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
