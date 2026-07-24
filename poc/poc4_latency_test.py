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
