"""Signature-agnostic tripwire: what does the RUN's own loader hand the Rule-3 scan?

Runs unchanged in both checkouts (6b6baaa and bb2ad60): it never unpacks candles_for's return,
it asks the RUN's gated loader for D-1's candles and looks at their STAMPS and at the verdict.
READ-ONLY over <data_root>.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None:  # bare-clone bootstrap, like every other launcher (REVIEW_2 F12)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import datetime as dt
import sys

from acumen import backtest as bt
from acumen.bias import Candle, evaluate_pair
from acumen.config import load_config
from acumen.daily_store import DailyStore
from acumen.minute_store import MinuteStore
from acumen.signal_engine import SignalPipeline

config = load_config(include_env=False)
DATA = config.path("data_root")
minute_store = MinuteStore(DATA / "minute_store")
daily_store = DailyStore(DATA / "daily_store")
pipeline = SignalPipeline(minute_store, daily_store, None, config.row_size)

D1, D2 = dt.date(2021, 2, 24), dt.date(2021, 2, 23)
loader = bt.gated_minute_loader(minute_store, pipeline)

bad = 0
for symbol in ("GODREJCP", "LAURUSLABS"):
    bars = minute_store.minutes(symbol, D1)
    strays = [b for b in bars if not (dt.time(9, 15) <= b.stamp.time() <= dt.time(15, 29))]
    candles = loader(symbol, D1)
    out = [c for c in candles if not (dt.time(9, 15) <= c.stamp.time() <= dt.time(15, 29))]

    previous = daily_store.daily(symbol, D2, D2).iloc[0]
    current = daily_store.daily(symbol, D1, D1).iloc[0]
    pair = [
        Candle(
            open=int(row["open_paise"]), high=int(row["high_paise"]),
            low=int(row["low_paise"]), close=int(row["close_paise"]), day=day,
        )
        for row, day in ((previous, D2), (current, D1))
    ]
    verdict = evaluate_pair(*pair, lambda: tuple(candles), "bearish")

    ok = not out
    bad += 0 if ok else 1
    print(
        f"{symbol}: stored {len(bars)} bars, {len(strays)} out-of-session; "
        f"loader handed the scan {len(candles)} candles of which {len(out)} are out-of-session "
        f"-> rule {verdict.rule!r} bias {verdict.bias!r}   [{'DROPPED' if ok else 'CONSUMED'}]"
    )

print(f"\nVERDICT: {'GREEN (Q-17 obeyed)' if bad == 0 else 'RED (strays consumed)'}")
sys.exit(0 if bad == 0 else 1)
