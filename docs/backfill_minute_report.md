# Minute backfill report -- chunk 5B (full-universe 1-minute run)

Generated 2026-07-26T13:28:56 from `C:\Users\chinm\acumen\data\universe_backfill\ledger.json` and the stores. Re-runnable at any time; makes no network call.

Scope: CONTEXT 3.1's F&O stock underlyings (CONTEXT 7-E5 -- TODAY's list, with the survivorship disclosure the report owes), 1-minute candles from `2016-10-01` (CONTEXT 4.3 depth floor) or the symbol's listing, whichever is later, to `2026-07-26`.

## 1. Headline

| Measure | Value |
|---|---|
| Universe symbols | 210 |
| Processed | 2 |
| Settled | 1 |
| Quarantined (gate-1 pass rate < 80%) | 1 |
| Not yet processed | 208 |
| Symbol-days gated (settled symbols) | 867 |
| Gate-1 PASS | 858 (99.0%) |
| Gate-2 exclusions | 158 |
| Un-provable days (no map era / unknown factor) | 0 |
| **TOTAL coverage** (gate-1-passing days of every symbol-day seen) | **26.0%** |
| Usable symbol-days (gate 1 AND gate 2) | ~700 |

**Definition of done (plan.md chunk 5B): >= 95% of symbol-days pass gates.** Measured: **26.0%** of all symbol-days seen pass gate 1, with every failure categorized in section 4.

## 2. Route classification (QUESTIONS.md Q-11 addendum)

| Route | Symbols | Meaning |
|---|---|---|
| `table-path` | 1 | bonus/split-only: our CONTEXT 4.2 factors ARE the vendor's, and gate-1 volume proves the price division |
| `map-required` | 1 | carries a non-share-count event (rights / special dividend / demerger) or something unparsed: ingested only through a measured map with per-day price containment |

### Map inventory

| Symbol | Eras probed | Provable | Unprobed | Events (kind @ ex-date: price/volume source) |
|---|---|---|---|---|
| ABB | 1 | 0 | 0 | - |

Per-event factor sources across every committed map -- **ours 0**, **measured 0**, **absent 0** (price side). `ours` = our exact CONTEXT 4.2 factor matched the vendor; `measured` = the vendor used a factor we had to observe; `absent` = the vendor did not apply the event in that era.

## 3. Depth found, per symbol

| Symbol | Route | Clamp | First 1-min day | Days | Windows p/e/x | Gate-1 | Gate-2 excl | Status |
|---|---|---|---|---|---|---|---|---|
| 360ONE | table-path | 2023-01-23 | 2023-01-23 | 867 | 46/0/0 | 858/867 (99.0%) | 158 | settled |
| ABB | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 1632/2429 (67.2%) | 828 | quarantined |

## 4. Exclusions by reason

| Reason | Symbol-days | Note |
|---|---|---|
| gate-1 (volume reconciliation outside [-0.1%, +5.0%]) | 9 | CONTEXT 4.5 gate 1; excluded + counted per CONTEXT 7-E3 |
| gate-2 (candle integrity) | 158 | missing > 15 minutes, duplicate stamps, or OHLC violations |
| un-provable (no map era / unknown factor in (D, F]) | 0 | the Q-11 surgical clamp -- stored so the day is visible, failed by gate 1 |
| quarantined symbols (whole history) | 2,429 | 1 symbol(s) below the 80% gate-1 floor |

### Quarantined symbols

| Symbol | Route | Gate-1 | Why |
|---|---|---|---|
| ABB | map-required | 1632/2429 (67.2%) | gate-1 pass rate 67.2% is below 80%; skipped, listed, run continues |

## 5. Gate 3 -- adjustment sanity across every share-count ex-date

CONTEXT 4.5 gate 3: on every split/bonus ex-date in the stored span, the ADJUSTED series must show |day-over-day gap| < 20%. Checked on the stored RAW closes with the event's own CONTEXT 4.2 factor applied at the comparison. **2 ex-date(s) checked, 2 failed.**

## 6. Unknown series on F&O-universe symbols (QUESTIONS.md Q-4)

The Q-4 ruling: "Unknown series encountered on F&O-universe symbols must be surfaced in the backfill/coverage report." They are reported here and are still never chosen by `DailyStore.daily()`.

| Symbol | Series | Rows | First | Last |
|---|---|---|---|---|
| ABB | AE | 1 | 2000-03-21 | 2000-03-21 |
| ADANIPOWER | T0 | 1 | 2025-10-29 | 2025-10-29 |
| AMBUJACEM | T0 | 3 | 2024-03-28 | 2025-04-04 |
| ASHOKLEY | AE | 4 | 2000-03-07 | 2000-03-15 |
| ASHOKLEY | BT | 1 | 2014-06-02 | 2014-06-02 |
| ASHOKLEY | T0 | 5 | 2024-03-28 | 2025-10-30 |
| AXISBANK | IL | 82 | 2013-09-04 | 2015-06-03 |
| BANKBARODA | IL | 122 | 2005-07-13 | 2015-07-13 |
| BANKBARODA | T0 | 4 | 2024-03-28 | 2025-04-25 |
| BANKINDIA | IL | 23 | 2009-11-03 | 2010-06-28 |
| BANKINDIA | T0 | 2 | 2025-10-24 | 2025-11-10 |
| BHARATFORG | W1 | 39 | 2005-02-09 | 2005-09-22 |
| BHARATFORG | W2 | 68 | 2010-05-21 | 2013-02-25 |
| BHARTIARTL | IL | 143 | 2006-06-22 | 2007-10-09 |
| BHEL | AE | 19 | 2000-02-01 | 2000-05-29 |
| BHEL | IL | 3 | 2005-12-01 | 2006-05-25 |
| BHEL | T0 | 6 | 2025-07-17 | 2025-11-04 |
| BPCL | T0 | 1 | 2025-05-15 | 2025-05-15 |
| BRITANNIA | AE | 1 | 2000-12-04 | 2000-12-04 |
| CANBK | IL | 17 | 2006-05-31 | 2008-02-13 |
| CIPLA | AE | 10 | 2000-01-12 | 2001-01-24 |
| COALINDIA | T0 | 1 | 2025-10-30 | 2025-10-30 |
| CONCOR | IL | 19 | 2013-11-25 | 2014-12-19 |
| DABUR | AE | 1 | 2000-03-21 | 2000-03-21 |
| DIVISLAB | T0 | 1 | 2024-03-28 | 2024-03-28 |
| DRREDDY | AE | 4 | 2000-01-11 | 2000-07-04 |
| FEDERALBNK | IL | 5 | 2013-12-18 | 2014-03-18 |
| FORTIS | IL | 1 | 2017-06-28 | 2017-06-28 |
| FORTIS | W1 | 128 | 2009-11-04 | 2010-05-13 |
| GAIL | AE | 1 | 2000-02-22 | 2000-02-22 |
| GAIL | T0 | 6 | 2025-07-24 | 2025-11-13 |
| GMRAIRPORT | T0 | 1 | 2025-11-20 | 2025-11-20 |
| GRASIM | AE | 3 | 2000-01-18 | 2000-05-17 |
| GRASIM | IL | 173 | 2005-09-28 | 2016-04-20 |
| HCLTECH | AE | 3 | 2000-10-17 | 2001-01-24 |
| HCLTECH | BT | 1 | 2016-08-22 | 2016-08-22 |
| HDFCBANK | AE | 1 | 2000-07-11 | 2000-07-11 |
| HDFCBANK | IL | 325 | 2013-12-19 | 2018-06-27 |
| HDFCBANK | T0 | 1 | 2025-10-30 | 2025-10-30 |
| HDFCBANK | W3 | 18 | 2023-07-17 | 2023-08-09 |
| HINDALCO | T0 | 2 | 2024-03-28 | 2025-05-19 |
| HINDPETRO | AE | 2 | 2000-02-02 | 2000-03-01 |
| HINDPETRO | IL | 3 | 2005-09-16 | 2006-01-23 |
| HYUNDAI | T0 | 8 | 2025-07-22 | 2025-10-31 |
| ICICIBANK | AE | 1 | 2000-04-26 | 2000-04-26 |
| ICICIBANK | E1 | 21 | 2004-04-22 | 2004-05-21 |
| ICICIBANK | E2 | 66 | 2007-08-14 | 2007-11-15 |
| ICICIBANK | IL | 100 | 2004-05-31 | 2007-08-21 |
| IDEA | T0 | 46 | 2025-07-22 | 2026-03-05 |
| IDFCFIRSTB | T0 | 1 | 2025-08-06 | 2025-08-06 |
| IEX | IL | 1 | 2018-06-06 | 2018-06-06 |
| INDHOTEL | AE | 1 | 2000-06-14 | 2000-06-14 |
| INDHOTEL | D1 | 357 | 2014-09-04 | 2016-02-16 |
| INDHOTEL | W1 | 107 | 2008-07-01 | 2009-08-25 |
| INDUSINDBK | IL | 119 | 2011-01-11 | 2015-08-28 |
| INFY | T0 | 2 | 2025-10-20 | 2025-10-23 |
| IOC | AE | 2 | 2000-01-19 | 2000-03-22 |
| IOC | T0 | 1 | 2025-08-06 | 2025-08-06 |
| ITC | AE | 77 | 2000-01-03 | 2000-12-20 |
| JIOFIN | T0 | 1 | 2025-11-20 | 2025-11-20 |
| JSWSTEEL | W1 | 27 | 2005-09-16 | 2005-10-25 |
| JUBLFOOD | IL | 5 | 2014-01-24 | 2014-04-02 |
| KOTAKBANK | IL | 37 | 2014-07-03 | 2016-03-02 |
| LICHSGFIN | T0 | 1 | 2024-03-28 | 2024-03-28 |
| LUPIN | IL | 35 | 2013-11-21 | 2015-01-23 |
| M&M | IL | 1 | 2004-03-26 | 2004-03-26 |
| MANAPPURAM | T0 | 1 | 2025-09-29 | 2025-09-29 |
| MARUTI | IL | 144 | 2010-01-06 | 2015-09-11 |
| MCX | IL | 5 | 2014-08-20 | 2015-12-23 |
| MOTHERSON | T0 | 2 | 2024-03-28 | 2024-07-01 |
| NATIONALUM | T0 | 1 | 2025-09-30 | 2025-09-30 |
| NAUKRI | IL | 1 | 2008-01-17 | 2008-01-17 |
| NBCC | T0 | 1 | 2025-04-30 | 2025-04-30 |
| NESTLEIND | T0 | 1 | 2024-03-28 | 2024-03-28 |
| NHPC | T0 | 1 | 2026-03-23 | 2026-03-23 |
| NMDC | T0 | 8 | 2024-03-28 | 2025-10-30 |
| NTPC | T0 | 4 | 2025-08-06 | 2025-11-14 |
| OIL | T0 | 1 | 2025-08-06 | 2025-08-06 |
| ONGC | T0 | 5 | 2024-03-28 | 2025-12-05 |
| PERSISTENT | IL | 2 | 2014-08-20 | 2014-08-27 |
| PETRONET | IL | 1 | 2015-10-08 | 2015-10-08 |
| PETRONET | T0 | 2 | 2025-01-28 | 2025-01-29 |
| PNB | IL | 181 | 2005-05-04 | 2016-05-26 |
| PNB | T0 | 7 | 2025-09-19 | 2025-10-31 |
| POWERGRID | IL | 32 | 2014-12-02 | 2015-10-21 |
| PRESTIGE | IL | 1 | 2015-10-28 | 2015-10-28 |
| RECLTD | IL | 19 | 2010-07-08 | 2010-09-30 |
| RELIANCE | AE | 112 | 2000-01-03 | 2001-06-06 |
| RELIANCE | T0 | 3 | 2025-07-25 | 2026-04-23 |
| SAIL | AE | 7 | 2000-02-15 | 2001-02-06 |
| SBIN | AE | 66 | 2000-01-03 | 2001-02-21 |
| SBIN | IL | 216 | 2005-02-07 | 2009-02-27 |
| SBIN | T0 | 33 | 2024-03-28 | 2025-10-31 |
| SHRIRAMFIN | YH | 98 | 2022-12-21 | 2023-06-23 |
| SHRIRAMFIN | YI | 277 | 2022-12-20 | 2024-05-03 |
| SHRIRAMFIN | YK | 87 | 2022-12-22 | 2023-06-23 |
| SHRIRAMFIN | YL | 215 | 2022-12-20 | 2024-05-02 |
| SHRIRAMFIN | YN | 113 | 2022-12-20 | 2023-06-23 |
| SHRIRAMFIN | YO | 133 | 2022-12-20 | 2023-10-09 |
| SHRIRAMFIN | YP | 153 | 2023-01-02 | 2024-05-03 |
| SHRIRAMFIN | YR | 131 | 2022-12-20 | 2023-10-12 |
| SHRIRAMFIN | YS | 117 | 2022-12-20 | 2024-04-18 |
| SHRIRAMFIN | YU | 84 | 2022-12-21 | 2023-10-12 |
| SHRIRAMFIN | YV | 198 | 2022-12-20 | 2024-01-18 |
| SHRIRAMFIN | YW | 131 | 2023-02-03 | 2024-05-03 |
| SHRIRAMFIN | YY | 137 | 2022-12-21 | 2024-01-18 |
| SHRIRAMFIN | YZ | 124 | 2022-12-23 | 2024-04-30 |
| SHRIRAMFIN | Z2 | 136 | 2022-12-21 | 2024-01-20 |
| SHRIRAMFIN | Z3 | 18 | 2022-12-26 | 2023-02-02 |
| SHRIRAMFIN | Z4 | 136 | 2023-01-04 | 2024-05-03 |
| SHRIRAMFIN | Z5 | 94 | 2022-12-20 | 2024-05-02 |
| SHRIRAMFIN | Z7 | 15 | 2022-12-26 | 2023-02-02 |
| SHRIRAMFIN | Z8 | 112 | 2022-12-23 | 2024-05-03 |
| SHRIRAMFIN | Z9 | 72 | 2023-01-03 | 2024-04-30 |
| SHRIRAMFIN | ZA | 16 | 2023-01-02 | 2023-02-02 |
| SHRIRAMFIN | ZB | 64 | 2022-12-21 | 2024-05-03 |
| SHRIRAMFIN | ZC | 88 | 2022-12-21 | 2024-05-03 |
| SHRIRAMFIN | ZD | 10 | 2022-12-21 | 2023-01-11 |
| SHRIRAMFIN | ZE | 98 | 2022-12-27 | 2024-04-24 |
| SHRIRAMFIN | ZF | 132 | 2022-12-26 | 2024-05-03 |
| SHRIRAMFIN | ZG | 6 | 2022-12-27 | 2023-01-11 |
| SHRIRAMFIN | ZH | 123 | 2022-12-21 | 2024-04-30 |
| SHRIRAMFIN | ZI | 40 | 2022-12-20 | 2024-03-18 |
| SHRIRAMFIN | ZJ | 5 | 2022-12-22 | 2023-01-04 |
| SHRIRAMFIN | ZK | 64 | 2022-12-21 | 2024-05-03 |
| SUNPHARMA | AE | 2 | 2000-06-20 | 2000-10-24 |
| SUZLON | T0 | 1 | 2025-10-27 | 2025-10-27 |
| TATAELXSI | AE | 5 | 2000-03-06 | 2000-07-05 |
| TATAPOWER | AE | 1 | 2000-07-11 | 2000-07-11 |
| TATASTEEL | E1 | 590 | 2018-03-19 | 2020-08-07 |
| TATASTEEL | IL | 122 | 2006-03-07 | 2008-10-03 |
| TATASTEEL | Q1 | 378 | 2008-01-24 | 2009-08-12 |
| TATASTEEL | T0 | 11 | 2025-07-11 | 2025-12-23 |
| TITAN | IL | 33 | 2013-11-21 | 2015-08-20 |
| TRENT | IL | 2 | 2017-02-16 | 2017-06-05 |
| TRENT | Q1 | 210 | 2010-09-02 | 2011-08-19 |
| TRENT | Q2 | 390 | 2010-09-02 | 2012-08-21 |
| TRENT | T0 | 1 | 2024-03-28 | 2024-03-28 |
| TRENT | W1 | 397 | 2005-07-18 | 2009-12-17 |
| UNIONBANK | IL | 78 | 2006-02-13 | 2011-09-16 |
| UNIONBANK | T0 | 1 | 2024-03-28 | 2024-03-28 |
| UPL | IL | 3 | 2014-09-11 | 2014-10-07 |
| UPL | Q1 | 223 | 2016-11-16 | 2018-02-06 |
| UPL | Q2 | 36 | 2016-11-18 | 2018-02-06 |
| VEDL | T0 | 6 | 2024-04-02 | 2025-10-16 |
| VOLTAS | AE | 1 | 2000-01-18 | 2000-01-18 |
| WIPRO | AE | 122 | 2000-01-18 | 2001-06-05 |
| WIPRO | T0 | 11 | 2025-07-01 | 2025-10-23 |
| YESBANK | IL | 27 | 2013-03-07 | 2014-11-11 |
| YESBANK | T0 | 15 | 2025-05-29 | 2026-04-02 |

## 7. Disclosures

- **Survivorship (CONTEXT 7-E5).** This run backfills TODAY's F&O list. Symbols that left the F&O universe during the backtest window are not in it, and symbols that joined recently carry their whole history. Point-in-time membership is OPEN-5.
- **Price domain (CONTEXT 7-E11, QUESTIONS.md Q-10/Q-11).** The minute store holds RAW same-day prices. The vendor feed is corporate-action back-adjusted, so every window is un-adjusted on ingest -- by our factor table for a bonus/split-only symbol, and by a MEASURED per-event map for every symbol carrying a non-share-count event.
- **Gate 1 is the per-day proof (Q-10 ruling).** A day whose un-adjustment cannot be proven against the raw daily volume is excluded and counted (CONTEXT 7-E3), never silently traded.
- **The daily store was verified before the run** (`DailyStore.verify()`, the owed REVIEW_2 F7 check): the oracle is checked before it is trusted.

