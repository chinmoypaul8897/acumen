# chunk 14 -- TELEGRAM, on a real morning

Run at 2026-08-14T05:16:33 from `docs/evidence/chunk14_telegram.py`. READ-ONLY over the stores. **No network and no credential**: the transport is a list, `.env` is never opened, and the only environment names that appear anywhere below are the two KEY NAMES.

The morning is HDFCBANK 2026-06-10 in LIVE posture -- the day chunk 7 walked candle by candle and chunk 8 priced, driven through the shipped screener with the Telegram sink attached to the sink tuple and nothing else changed.

## 1. What lands on the trader's phone

3 messages, verbatim:

```
--- message 1 ------------------------------------------------------------
[11:15] HDFCBANK ARMED  LONG  POC 739.80  reference 738.20
(live feed, not yet verified against the exchange's end-of-day record)
--- message 2 ------------------------------------------------------------
[11:30] HDFCBANK LONG  entry 740.95  SL 738.10  TP 749.50  qty 350   (POC 739.80, bias bullish)
(live feed, not yet verified against the exchange's end-of-day record)
--- message 3 ------------------------------------------------------------
[13:15] HDFCBANK EXIT target-hit  at 749.50
(live feed, not yet verified against the exchange's end-of-day record)
```

Every one carries CONTEXT 4.7's disclosed line, on its own line so a phone cannot wrap it out of sight. The numbers are CONTEXT 4.4's payload -- symbol, side, entry, SL, TP, POC, bias, timestamp -- plus the quantity CONTEXT 3.5 sizes.

## 2. The Q1 case: a frozen feed

The same day, with a vendor that keeps answering 200 with a prefix that never grows. The screener squares off at 15:15 on a price computed from bars that stopped at 11:29, and **the message says so**:

```
--- message 1 ------------------------------------------------------------
[11:15] HDFCBANK ARMED  LONG  POC 739.80  reference 738.20
(live feed, not yet verified against the exchange's end-of-day record)
--- message 2 ------------------------------------------------------------
[11:30] HDFCBANK LONG  entry 740.95  SL 738.10  TP 749.50  qty 350   (POC 739.80, bias bullish)
(live feed, not yet verified against the exchange's end-of-day record)
--- message 3 ------------------------------------------------------------
[15:15] HDFCBANK SQUARE-OFF at 740.95
!! STALE 226m BEHIND -- this price stands on a window the screener cannot vouch for
(live feed, not yet verified against the exchange's end-of-day record)
```

## 3. A send failure degrades to silence plus a VISIBLE failure

The transport raises on every alert of the morning. Nothing crashes, the sweep is not interrupted, and the operator's screen carries one line per failed alert:

```
!! TELEGRAM SEND FAILED (the alert is on this screen and in the recording): HDFCBANK armed (TelegramError)
!! TELEGRAM SEND FAILED (the alert is on this screen and in the recording): HDFCBANK trigger (TelegramError)
!! TELEGRAM SEND FAILED (the alert is on this screen and in the recording): HDFCBANK exit (TelegramError)
```

Then the transport heals: **3 message(s) delivered** on the next pass over the same alerts, and **3 still** after a third pass -- a failed send is retried by the next re-derivation, and a successful one is never sent twice.

## 4. An alert whose price cannot be vouched for is NOT forwarded

```
!! TELEGRAM REFUSED an alert whose price the screener cannot vouch for: HDFCBANK trigger: the payload names a price and carries no freshness stamp, so nothing on it says how old the window behind that price is
```

## 5. The order-endpoint tripwire, over the new module

`tests/test_live_safety.py`'s scan over 179 Python files, including `src/acumen/telegram_sink.py`: **0 offender(s)**.

The sink talks to exactly one host, `api.telegram.org`, through exactly one call, and the repository holds no order-placement code for it to reach even if it wanted to.

## 6. A DRY-RUN morning says so, on the message

Everything above is the `--live-alerts` shape. Without that flag the screener stays in dry run, the sink sends nothing at all, and if a message is built anyway it carries the marker -- so a forwarded screenshot of a dry-run alert can never be read as a live one:

```
[11:30] HDFCBANK LONG  entry 740.95  SL 738.10  TP 749.50  qty 350   (POC 739.80, bias bullish)
[DRY RUN -- log only, nothing was sent to anyone else]
(live feed, not yet verified against the exchange's end-of-day record)
```
