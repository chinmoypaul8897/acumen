# Minute backfill report -- chunk 5B (full-universe 1-minute run)

Generated 2026-07-28T17:43:52 from `C:\Users\chinm\acumen\data\universe_backfill\ledger.json` and the stores. Re-runnable at any time; makes no network call.

Scope: CONTEXT 3.1's F&O stock underlyings (CONTEXT 7-E5 -- TODAY's list, with the survivorship disclosure the report owes), 1-minute candles from `2016-10-01` (CONTEXT 4.3 depth floor) or the symbol's listing, whichever is later, to `2026-07-27`.

## 1. Headline

| Measure | Value |
|---|---|
| Universe symbols | 210 |
| Processed | 210 |
| Settled | 204 |
| Quarantined (gate-1 pass rate < 80%) | 6 |
| Not yet processed | 0 |
| Symbol-days gated (settled symbols) | 420,297 |
| Gate-1 PASS (strict band) | 413,482 (98.4%) |
| Gate-1 AUCTION-RELIEF pass (Q-12 addendum 2) | 432 (0.1%) |
| Gate-1 EFFECTIVE pass (strict + relief) | 413,914 (98.5%) |
| Gate-2 exclusions | 1,191 |
| Un-provable days (no map era / unknown factor) | 300 |
| Vendor application floors resolved (Q-11 addendum 2) | 10 over 108 probe(s) |
| **TOTAL coverage** (gate-1-passing days of every symbol-day seen) | **95.2%** |
| TOTAL coverage, STRICT band only (no relief) | 95.1% |
| Usable symbol-days (gate 1 AND gate 2) | ~412,723 |

**Definition of done (plan.md chunk 5B): >= 95% of symbol-days pass gates.** Measured: **95.2%** of all symbol-days seen pass gate 1, with every failure categorized in section 4. Without the auction relief the same store measures 95.1%; the two numbers are printed side by side everywhere in this report, and the relief count is never folded into the strict one.

> **DoD VERDICT: MET** -- 413,914 of 434,591 symbol-days pass, at or above the 95% line.

## 2. Route classification (QUESTIONS.md Q-11 addendum)

| Route | Symbols | Meaning |
|---|---|---|
| `table-path` | 113 | bonus/split-only: our CONTEXT 4.2 factors ARE the vendor's, and gate-1 volume proves the price division |
| `map-required` | 97 | carries a non-share-count event (rights / special dividend / demerger) or something unparsed: ingested only through a measured map with per-day price containment |

### Map inventory

| Symbol | Eras probed | Provable | Unprobed | Events (kind @ ex-date: price/volume source) |
|---|---|---|---|---|
| ABB | 1 | 1 | 0 | demerger@2019-12-20: measured/price-factor |
| ADANIENT | 3 | 3 | 0 | demerger@2018-04-05: measured/price-factor; demerger@2018-09-06: absent/absent; demerger@2018-09-06: measured/price-factor; rights@2025-11-17: ours/price-factor |
| AMBUJACEM | 2 | 2 | 0 | dividend@2020-11-05: absent/ours; dividend@2022-03-30: absent/ours |
| APLAPOLLO | 2 | 2 | 0 | bonus@2021-09-16: ours/ours; split@2020-12-15: ours/ours |
| ASHOKLEY | 3 | 3 | 0 | bonus@2025-07-16: ours/ours; dividend@2019-07-23: absent/ours; dividend@2024-04-03: absent/ours |
| ASTRAL | 3 | 2 | 0 | bonus@2021-03-18: ours/ours; bonus@2023-03-14: ours/ours |
| AUBANK | 1 | 1 | 0 | bonus@2022-06-09: ours/measured |
| BAJAJ-AUTO | 7 | 7 | 0 | dividend@2018-07-05: absent/ours; dividend@2019-07-11: absent/ours; dividend@2020-03-03: absent/ours; dividend@2021-07-08: absent/ours; dividend@2022-06-30: absent/ours; dividend@2023-06-30: absent/ours; dividend@2025-06-20: absent/ours |
| BAJAJFINSV | 2 | 1 | 0 | bonus+split@2022-09-13: ours/measured |
| BANKBARODA | 5 | 3 | 0 | dividend@2024-06-28: absent/ours; dividend@2025-06-06: absent/ours; dividend@2026-06-05: absent/ours |
| BANKINDIA | 5 | 5 | 0 | dividend@2022-07-07: absent/ours; dividend@2023-06-20: absent/ours; dividend@2024-06-18: absent/ours; dividend@2025-06-20: absent/ours; dividend@2026-05-29: absent/ours |
| BDL | 1 | 1 | 0 | split@2024-05-24: ours/ours |
| BEL | 3 | 1 | 0 | bonus@2022-09-15: ours/measured |
| BHARTIARTL | 2 | 2 | 0 | rights@2019-04-23: measured/price-factor; rights@2021-09-27: absent/measured |
| BHEL | 2 | 2 | 0 | bonus@2017-09-28: ours/ours; dividend@2019-09-11: absent/ours |
| BLUESTARCO | 1 | 1 | 0 | bonus@2023-06-20: ours/ours |
| BPCL | 13 | 11 | 0 | bonus@2024-06-21: ours/ours; dividend@2018-02-22: absent/ours; dividend@2019-02-21: absent/ours; dividend@2019-08-21: absent/ours; dividend@2020-03-23: absent/ours; dividend@2021-02-17: absent/ours; dividend@2021-09-16: absent/ours; dividend@2023-12-12: absent/ours; dividend@2024-08-09: absent/ours; dividend@2025-11-07: absent/ours; dividend@2026-02-02: absent/ours |
| BRITANNIA | 4 | 4 | 0 | dividend@2020-08-26: absent/ours; split@2018-11-29: ours/ours; unparsed@2019-08-22: absent/measured; unparsed@2021-05-25: absent/measured |
| BSE | 7 | 6 | 0 | bonus@2022-03-21: ours/measured; bonus@2025-05-23: ours/ours; dividend@2018-07-25: absent/ours; dividend@2019-06-27: absent/ours; dividend@2020-07-22: absent/ours; dividend@2022-06-23: absent/ours |
| CAMS | 2 | 2 | 0 | split@2025-12-05: ours/ours; unparsed@2021-02-17: absent/measured |
| CANBK | 7 | 6 | 0 | dividend@2022-06-15: absent/ours; dividend@2023-06-14: absent/ours; dividend@2024-06-14: absent/ours; dividend@2025-06-13: absent/ours; dividend@2026-06-12: absent/ours; split@2024-05-15: ours/ours |
| CDSL | 2 | 2 | 0 | bonus@2024-08-23: ours/ours; dividend@2019-09-06: absent/ours |
| COALINDIA | 15 | 15 | 0 | dividend@2017-03-14: absent/ours; dividend@2018-03-16: absent/ours; dividend@2018-12-28: absent/ours; dividend@2019-03-22: absent/ours; dividend@2020-03-19: absent/ours; dividend@2020-11-19: absent/ours; dividend@2021-03-15: absent/ours; dividend@2021-09-02: absent/ours; dividend@2021-12-06: absent/ours; dividend@2022-02-21: absent/ours; dividend@2022-11-15: absent/ours; dividend@2023-02-08: absent/ours; dividend@2023-11-21: absent/ours; dividend@2024-11-05: absent/ours; dividend@2025-11-04: absent/ours |
| COCHINSHIP | 6 | 2 | 0 | dividend@2022-02-21: absent/ours; split@2024-01-10: ours/ours |
| COLPAL | 2 | 2 | 0 | unparsed@2017-12-18: absent/measured; unparsed@2019-04-05: absent/measured |
| DIXON | 1 | 1 | 0 | split@2021-03-18: ours/ours |
| GAIL | 12 | 10 | 0 | bonus@2019-07-09: ours/ours; bonus@2022-09-06: ours/ours; dividend@2020-02-17: absent/ours; dividend@2021-12-30: absent/ours; dividend@2022-03-21: absent/ours; dividend@2023-03-21: absent/ours; dividend@2024-02-06: absent/ours; dividend@2025-02-07: absent/ours; dividend@2026-02-05: absent/ours; unparsed@2019-08-08: absent/measured |
| GODFRYPHLP | 5 | 5 | 0 | bonus@2025-09-16: ours/ours; dividend@2020-03-17: absent/ours; dividend@2021-07-28: absent/ours; dividend@2022-08-11: absent/ours; dividend@2023-08-11: absent/ours |
| GRASIM | 3 | 3 | 0 | demerger@2017-07-19: measured/price-factor; rights@2024-01-10: ours/price-factor; split@2016-10-06: ours/ours |
| HAL | 3 | 1 | 0 | split@2023-09-28: ours/ours |
| HCLTECH | 2 | 2 | 0 | bonus@2019-12-05: ours/ours; unparsed@2018-08-02: absent/measured |
| HDFCAMC | 4 | 4 | 0 | bonus@2025-11-26: ours/ours; dividend@2022-06-09: absent/ours; dividend@2023-06-09: absent/ours; dividend@2026-06-05: absent/ours |
| HDFCBANK | 2 | 2 | 0 | bonus@2025-08-26: ours/ours; split@2019-09-19: ours/ours |
| HEROMOTOCO | 5 | 5 | 0 | dividend@2020-02-17: absent/ours; dividend@2022-02-21: absent/ours; dividend@2023-02-17: absent/ours; dividend@2024-02-21: absent/ours; dividend@2025-02-12: absent/ours |
| HINDPETRO | 12 | 7 | 0 | bonus@2024-06-21: ours/ours; dividend@2020-07-02: absent/ours; dividend@2021-07-08: absent/ours; dividend@2022-08-22: absent/ours; dividend@2024-02-07: absent/ours; dividend@2024-08-09: absent/ours; dividend@2025-08-14: absent/ours |
| HINDUNILVR | 1 | 1 | 0 | demerger@2025-12-05: absent/absent |
| HINDZINC | 11 | 1 | 0 | dividend@2024-08-28: absent/ours |
| IDEA | 1 | 1 | 0 | rights@2019-03-29: measured/price-factor |
| IEX | 2 | 0 | 0 | - |
| INDHOTEL | 2 | 2 | 0 | rights@2017-10-04: measured/price-factor; rights@2021-11-11: absent/measured |
| INDIANB | 5 | 5 | 0 | dividend@2022-06-14: absent/ours; dividend@2023-06-12: absent/ours; dividend@2024-06-07: absent/ours; dividend@2025-06-10: absent/ours; dividend@2026-06-10: absent/ours |
| INDIGO | 1 | 1 | 0 | dividend@2017-08-18: absent/ours |
| INDUSTOWER | 2 | 2 | 0 | dividend@2021-02-08: absent/ours; dividend@2022-05-13: absent/ours |
| INFY | 3 | 3 | 0 | bonus@2018-09-04: ours/ours; dividend@2018-06-14: absent/ours; dividend@2026-06-10: absent/ours |
| INOXWIND | 2 | 2 | 0 | bonus@2024-05-24: ours/ours; rights@2025-07-29: ours/price-factor |
| IOC | 17 | 3 | 0 | dividend@2024-07-12: absent/ours; dividend@2025-08-08: absent/ours; dividend@2025-12-18: absent/ours |
| IRFC | 4 | 4 | 0 | dividend@2021-02-17: absent/ours; dividend@2021-11-10: absent/ours; dividend@2022-09-15: absent/ours; dividend@2022-11-17: absent/ours |
| ITC | 9 | 9 | 0 | demerger@2025-01-06: absent/absent; dividend@2020-07-06: absent/ours; dividend@2021-02-22: absent/ours; dividend@2021-06-10: absent/ours; dividend@2022-02-14: absent/ours; dividend@2022-05-26: absent/ours; dividend@2023-05-30: absent/ours; dividend@2026-02-04: absent/ours; dividend@2026-05-27: absent/ours |
| JSWENERGY | 1 | 1 | 0 | dividend@2020-08-04: absent/ours |
| JSWSTEEL | 2 | 2 | 0 | dividend@2022-07-04: absent/ours; unparsed@2017-01-04: measured/price-factor |
| JUBLFOOD | 2 | 2 | 0 | bonus@2018-06-21: ours/measured; split@2022-04-19: ours/measured |
| LICHSGFIN | 3 | 3 | 0 | dividend@2020-09-17: absent/ours; dividend@2021-09-16: absent/ours; dividend@2023-08-18: absent/ours |
| LICI | 2 | 2 | 0 | bonus@2026-05-29: ours/ours; dividend@2026-06-25: absent/ours |
| LODHA | 1 | 1 | 0 | bonus@2023-05-31: ours/ours |
| MAZDOCK | 3 | 3 | 0 | dividend@2021-02-22: absent/ours; dividend@2022-01-06: absent/ours; split@2024-12-27: ours/ours |
| MCX | 2 | 2 | 0 | dividend@2019-09-12: absent/ours; split@2026-01-02: ours/ours |
| MOTHERSON | 2 | 2 | 0 | bonus@2022-10-03: ours/measured; bonus@2025-07-18: ours/ours |
| MOTILALOFS | 1 | 1 | 0 | bonus@2024-06-10: ours/ours |
| MPHASIS | 9 | 2 | 0 | dividend@2024-07-10: absent/ours; dividend@2026-07-08: absent/ours |
| MUTHOOTFIN | 3 | 3 | 0 | dividend@2018-02-15: absent/ours; dividend@2020-03-23: absent/ours; dividend@2023-04-18: absent/ours |
| NAM-INDIA | 2 | 0 | 0 | - |
| NATIONALUM | 10 | 10 | 0 | dividend@2017-03-09: absent/ours; dividend@2018-02-16: absent/ours; dividend@2019-03-11: absent/ours; dividend@2019-09-11: absent/ours; dividend@2020-02-18: absent/ours; dividend@2021-03-22: absent/ours; dividend@2021-11-24: absent/ours; dividend@2022-02-17: absent/ours; dividend@2023-03-21: absent/ours; dividend@2025-02-14: absent/ours |
| NBCC | 4 | 4 | 0 | bonus@2017-02-17: ours/ours; bonus@2024-10-07: ours/ours; split@2018-04-25: ours/ours; unparsed@2020-11-26: absent/measured |
| NESTLEIND | 3 | 2 | 0 | bonus@2025-08-08: ours/ours; split@2024-01-05: ours/ours |
| NHPC | 8 | 8 | 0 | dividend@2017-01-19: absent/ours; dividend@2018-02-20: absent/ours; dividend@2019-09-12: absent/ours; dividend@2020-02-17: absent/ours; dividend@2021-02-22: absent/ours; dividend@2022-02-22: absent/ours; dividend@2023-02-17: absent/ours; unparsed@2019-02-18: absent/measured |
| NMDC | 14 | 12 | 0 | bonus@2024-12-27: ours/ours; demerger@2022-10-27: measured/measured; dividend@2019-03-22: absent/ours; dividend@2020-02-18: absent/ours; dividend@2021-03-22: absent/ours; dividend@2021-12-14: absent/ours; dividend@2022-02-17: absent/ours; dividend@2023-02-24: absent/ours; dividend@2023-08-31: absent/ours; dividend@2024-02-27: absent/ours; dividend@2025-03-21: absent/ours; dividend@2026-02-13: absent/ours |
| NTPC | 8 | 7 | 0 | bonus@2019-03-19: ours/ours; dividend@2019-08-13: absent/ours; dividend@2020-08-13: absent/ours; dividend@2021-02-11: absent/ours; dividend@2021-09-08: absent/ours; dividend@2022-02-03: absent/ours; dividend@2023-02-03: absent/ours |
| NYKAA | 1 | 1 | 0 | bonus@2022-11-10: ours/measured |
| OFSS | 9 | 9 | 0 | dividend@2017-04-19: absent/ours; dividend@2018-08-06: absent/ours; dividend@2020-05-19: absent/ours; dividend@2021-05-17: absent/ours; dividend@2022-05-13: absent/ours; dividend@2023-05-09: absent/ours; dividend@2024-05-07: absent/ours; dividend@2025-05-08: absent/ours; dividend@2026-05-07: absent/ours |
| OIL | 12 | 8 | 0 | bonus@2024-07-02: ours/ours; dividend@2019-02-21: absent/ours; dividend@2020-02-20: absent/ours; dividend@2021-02-23: absent/ours; dividend@2022-02-22: absent/ours; dividend@2022-09-15: absent/ours; dividend@2022-11-21: absent/ours; dividend@2023-02-22: absent/ours |
| ONGC | 11 | 11 | 0 | bonus@2016-12-15: ours/ours; dividend@2019-02-28: absent/ours; dividend@2020-03-23: absent/ours; dividend@2021-11-22: absent/ours; dividend@2022-08-18: absent/ours; dividend@2022-11-21: absent/ours; dividend@2023-02-24: absent/ours; dividend@2023-11-21: absent/ours; dividend@2024-11-19: absent/ours; dividend@2025-11-14: absent/ours; dividend@2026-02-18: absent/ours |
| PERSISTENT | 1 | 1 | 0 | split@2024-03-28: ours/ours |
| PETRONET | 10 | 2 | 0 | dividend@2024-11-08: absent/ours; dividend@2025-11-14: absent/ours |
| PFC | 9 | 5 | 0 | bonus@2023-09-21: ours/ours; dividend@2022-02-25: absent/ours; dividend@2022-11-24: absent/ours; dividend@2023-02-24: absent/ours; dividend@2023-06-16: absent/ours |
| PGEL | 1 | 1 | 0 | split@2024-07-10: ours/ours |
| PNB | 3 | 3 | 0 | dividend@2022-06-22: absent/ours; dividend@2025-06-20: absent/ours; dividend@2026-06-12: absent/ours |
| PNBHOUSING | 1 | 1 | 0 | rights@2023-04-05: measured/price-factor |
| POWERGRID | 10 | 10 | 0 | bonus@2021-07-29: absent/measured; bonus@2023-09-12: ours/ours; dividend@2019-03-14: absent/ours; dividend@2020-03-16: absent/ours; dividend@2020-09-02: absent/ours; dividend@2020-12-17: absent/ours; dividend@2021-12-22: absent/ours; dividend@2022-02-16: absent/ours; dividend@2022-11-14: absent/ours; dividend@2023-02-08: absent/ours |
| RECLTD | 12 | 7 | 0 | bonus@2022-08-17: ours/measured; dividend@2021-03-18: absent/ours; dividend@2022-02-15: absent/ours; dividend@2022-07-12: absent/ours; dividend@2022-11-07: absent/ours; dividend@2023-02-09: absent/ours; dividend@2023-07-14: absent/ours |
| RELIANCE | 4 | 4 | 0 | bonus@2017-09-07: ours/ours; bonus@2024-10-28: ours/ours; demerger@2023-07-20: absent/absent; demerger@2023-07-20: measured/price-factor; rights@2020-05-13: measured/price-factor |
| RVNL | 4 | 4 | 0 | dividend@2020-12-08: absent/ours; dividend@2021-04-08: absent/ours; dividend@2022-03-24: absent/ours; dividend@2023-04-06: absent/ours |
| SAIL | 3 | 3 | 0 | dividend@2021-11-09: absent/ours; dividend@2022-03-28: absent/ours; dividend@2022-07-28: absent/ours |
| SIEMENS | 1 | 1 | 0 | demerger@2025-04-07: measured/price-factor |
| SRF | 2 | 1 | 0 | bonus@2021-10-13: ours/measured |
| SUZLON | 1 | 1 | 0 | rights@2022-10-03: absent/measured |
| TATACONSUM | 1 | 0 | 0 | - |
| TATAPOWER | 1 | 1 | 0 | dividend@2020-07-14: absent/ours |
| TATASTEEL | 9 | 3 | 0 | dividend@2023-06-22: absent/ours; dividend@2025-06-06: absent/ours; dividend@2026-06-12: absent/ours |
| TCS | 2 | 2 | 0 | bonus@2018-05-31: ours/ours; unparsed@2018-10-23: absent/measured |
| TECHM | 6 | 6 | 0 | dividend@2017-07-27: absent/ours; dividend@2018-07-26: absent/ours; dividend@2019-07-25: absent/ours; dividend@2022-07-21: absent/ours; dividend@2023-07-21: absent/ours; dividend@2026-07-03: absent/ours |
| TORNTPHARM | 1 | 1 | 0 | bonus@2022-07-08: ours/measured |
| TVSMOTOR | 1 | 1 | 0 | demerger@2025-08-25: absent/absent |
| UNIONBANK | 5 | 3 | 0 | dividend@2024-07-19: absent/ours; dividend@2025-07-25: absent/ours; dividend@2026-07-03: absent/ours |
| UPL | 2 | 1 | 0 | rights@2024-11-26: ours/price-factor |
| VBL | 5 | 3 | 0 | bonus@2022-06-06: ours/ours; split@2023-06-15: ours/ours; split@2024-09-12: ours/ours |
| VEDL | 19 | 17 | 0 | demerger@2026-04-30: measured/price-factor; dividend@2017-04-11: absent/ours; dividend@2018-03-20: absent/ours; dividend@2018-11-06: absent/absent; dividend@2020-03-05: absent/ours; dividend@2020-10-28: absent/ours; dividend@2021-09-08: absent/ours; dividend@2021-12-17: absent/ours; dividend@2022-05-06: absent/ours; dividend@2022-07-26: absent/ours; dividend@2022-11-29: absent/ours; dividend@2023-02-03: absent/ours; dividend@2023-04-06: absent/ours; dividend@2023-05-30: absent/ours; dividend@2023-12-27: absent/absent; dividend@2024-05-24: absent/ours; dividend@2024-09-10: absent/ours; dividend@2025-08-26: absent/ours; unparsed@2022-03-09: absent/measured |
| WIPRO | 4 | 4 | 0 | bonus@2017-06-13: ours/ours; bonus@2019-03-06: ours/ours; bonus@2024-12-03: ours/ours; dividend@2026-01-27: absent/ours |

Per-event factor sources across every committed map, PRICE side -- **ours 71**, **measured 14**, **absent 262**. `ours` = our exact CONTEXT 4.2 factor matched the vendor; `measured` = the vendor used a factor we had to observe; `absent` = the vendor did not apply the event in that era.

VOLUME side -- **ours 296**, **price-factor 17**, **measured 27**, **absent 7**. The Q-12 ruling's candidate order is `ours(share-count) > chosen-price-factor > measured-minimum > absent`: `price-factor` means the event's volume was reconciled by the very factor the PRICE oracle had already pinned to 2 paise per probe day, which is strictly better evidenced than an observed volume ratio the pre-open auction biases upward. `measured` on this side is now the MINIMUM over the price-passing probe days, never the median.

## 3. Depth found, per symbol

| Symbol | Route | Clamp | First 1-min day | Days | Windows p/e/x | Gate-1 (strict) | Relief | Gate-1 (effective) | Floors | Gate-2 excl | Avg min/day | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 360ONE | table-path | 2023-01-23 | 2023-01-23 | 867 | 46/0/0 | 858/867 (99.0%) | 3 | 861/867 (99.3%) | - | 1 | 363.6 | settled |
| ABB | map-required | 2016-10-01 | 2016-10-03 | 2431 | 129/0/0 | 2414/2429 (99.4%) | 2 | 2416/2429 (99.5%) | - | 10 | 350.9 | settled |
| ABCAPITAL | table-path | 2017-09-01 | 2017-09-01 | 2202 | 117/0/0 | 2187/2202 (99.3%) | 0 | 2187/2202 (99.3%) | - | 2 | 372.7 | settled |
| ADANIENSOL | table-path | 2023-08-24 | 2023-08-24 | 723 | 39/0/0 | 721/723 (99.7%) | 1 | 722/723 (99.9%) | - | 1 | 372.9 | settled |
| ADANIENT | map-required | 2016-10-01 | 2016-10-03 | 2431 | 129/0/0 | 2400/2429 (98.8%) | 13 | 2413/2429 (99.3%) | - | 3 | 372.6 | settled |
| ADANIGREEN | table-path | 2018-06-18 | 2018-06-18 | 2005 | 106/0/0 | 1990/2005 (99.3%) | 2 | 1992/2005 (99.4%) | - | 9 | 362.8 | settled |
| ADANIPORTS | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2410/2429 (99.2%) | 1 | 2411/2429 (99.3%) | - | 2 | 373.2 | settled |
| ADANIPOWER | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2401/2429 (98.8%) | 8 | 2409/2429 (99.2%) | - | 2 | 372.4 | settled |
| ALKEM | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2415/2429 (99.4%) | 0 | 2415/2429 (99.4%) | - | 10 | 343.9 | settled |
| AMBER | table-path | 2018-01-30 | 2018-01-30 | 2099 | 111/0/0 | 2082/2099 (99.2%) | 1 | 2083/2099 (99.2%) | - | 12 | 327.3 | settled |
| AMBUJACEM | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2428 (99.4%) | 1 | 2414/2428 (99.4%) | - | 3 | 373.0 | settled |
| ANGELONE | table-path | 2021-11-11 | 2021-11-11 | 1166 | 62/0/0 | 1163/1166 (99.7%) | 0 | 1163/1166 (99.7%) | - | 1 | 373.1 | settled |
| APLAPOLLO | map-required | 2016-10-01 | 2016-10-03 | 2433 | 129/0/0 | 2343/2431 (96.4%) | 20 | 2363/2431 (97.2%) | 0 | 67 | 313.9 | settled |
| APOLLOHOSP | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2415/2429 (99.4%) | 1 | 2416/2429 (99.5%) | - | 2 | 371.9 | settled |
| ASHOKLEY | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2415/2429 (99.4%) | 0 | 2415/2429 (99.4%) | - | 3 | 373.3 | settled |
| ASIANPAINT | table-path | 2016-10-01 | 2016-10-03 | 2430 | 128/1/0 | 2417/2430 (99.5%) | 1 | 2418/2430 (99.5%) | - | 2 | 373.2 | settled |
| ASTRAL | map-required | 2016-10-01 | 2016-10-03 | 2430 | 128/1/0 | 1698/2430 (69.9%) | 1 | 1699/2430 (69.9%) | 0 | 636 | 332.7 | quarantined |
| AUBANK | map-required | 2017-07-10 | 2017-07-10 | 2241 | 119/0/0 | 2235/2240 (99.8%) | 0 | 2235/2240 (99.8%) | - | 3 | 365.6 | settled |
| AUROPHARMA | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2415/2429 (99.4%) | 0 | 2415/2429 (99.4%) | - | 2 | 373.2 | settled |
| AXISBANK | table-path | 2016-10-01 | 2016-10-03 | 2428 | 128/1/0 | 2410/2428 (99.3%) | 3 | 2413/2428 (99.4%) | - | 2 | 373.3 | settled |
| BAJAJ-AUTO | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2415/2429 (99.4%) | 0 | 2415/2429 (99.4%) | - | 2 | 373.0 | settled |
| BAJAJFINSV | map-required | 2016-10-01 | 2016-10-03 | 2431 | 128/1/0 | 2417/2431 (99.4%) | 0 | 2417/2431 (99.4%) | - | 2 | 372.4 | settled |
| BAJAJHLDNG | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2406/2429 (99.1%) | 1 | 2407/2429 (99.1%) | - | 19 | 314.9 | settled |
| BAJFINANCE | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2410/2429 (99.2%) | 2 | 2412/2429 (99.3%) | - | 2 | 373.2 | settled |
| BANDHANBNK | table-path | 2018-03-27 | 2018-03-27 | 2061 | 109/0/0 | 2046/2061 (99.3%) | 2 | 2048/2061 (99.4%) | - | 3 | 373.1 | settled |
| BANKBARODA | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2416/2429 (99.5%) | 0 | 2416/2429 (99.5%) | - | 2 | 373.3 | settled |
| BANKINDIA | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2414/2429 (99.4%) | 1 | 2415/2429 (99.4%) | - | 2 | 372.6 | settled |
| BDL | map-required | 2018-03-23 | 2022-05-19 | 1038 | 55/54/0 | 1035/1038 (99.7%) | 0 | 1035/1038 (99.7%) | - | 1 | 372.9 | settled |
| BEL | map-required | 2016-10-01 | 2016-10-03 | 2431 | 128/1/0 | 2173/2431 (89.4%) | 0 | 2173/2431 (89.4%) | 0 | 13 | 373.1 | settled |
| BHARATFORG | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2416/2429 (99.5%) | 0 | 2416/2429 (99.5%) | - | 2 | 372.9 | settled |
| BHARTIARTL | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2402/2429 (98.9%) | 8 | 2410/2429 (99.2%) | - | 3 | 373.2 | settled |
| BHEL | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2415/2429 (99.4%) | 0 | 2415/2429 (99.4%) | - | 3 | 373.3 | settled |
| BIOCON | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2416/2429 (99.5%) | 0 | 2416/2429 (99.5%) | - | 2 | 373.0 | settled |
| BLUESTARCO | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2409/2429 (99.2%) | 1 | 2410/2429 (99.2%) | - | 16 | 321.0 | settled |
| BOSCHLTD | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2408/2429 (99.1%) | 0 | 2408/2429 (99.1%) | - | 12 | 357.2 | settled |
| BPCL | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2223/2429 (91.5%) | 0 | 2223/2429 (91.5%) | 0 | 4 | 373.3 | settled |
| BRITANNIA | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2411/2429 (99.3%) | 3 | 2414/2429 (99.4%) | - | 3 | 372.7 | settled |
| BSE | map-required | 2017-02-03 | 2017-02-03 | 2345 | 124/0/0 | 2115/2345 (90.2%) | 0 | 2115/2345 (90.2%) | 0 | 106 | 365.1 | settled |
| CAMS | map-required | 2020-10-05 | 2020-10-05 | 1438 | 76/0/0 | 1436/1438 (99.9%) | 0 | 1436/1438 (99.9%) | - | 1 | 372.2 | settled |
| CANBK | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2414/2429 (99.4%) | 0 | 2414/2429 (99.4%) | - | 2 | 373.2 | settled |
| CDSL | map-required | 2017-06-30 | 2017-06-30 | 2244 | 119/0/0 | 2228/2244 (99.3%) | 2 | 2230/2244 (99.4%) | - | 9 | 364.2 | settled |
| CGPOWER | table-path | 2017-03-08 | 2017-03-08 | 2321 | 123/0/0 | 2302/2321 (99.2%) | 4 | 2306/2321 (99.4%) | - | 3 | 356.2 | settled |
| CHOLAFIN | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 2 | 2415/2429 (99.4%) | - | 2 | 368.2 | settled |
| CIPLA | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2414/2429 (99.4%) | 2 | 2416/2429 (99.5%) | - | 2 | 373.2 | settled |
| COALINDIA | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2415/2429 (99.4%) | 1 | 2416/2429 (99.5%) | - | 2 | 373.3 | settled |
| COCHINSHIP | map-required | 2017-08-11 | 2017-08-11 | 2216 | 117/0/0 | 2197/2215 (99.2%) | 1 | 2198/2215 (99.2%) | 0 | 10 | 350.0 | settled |
| COFORGE | table-path | 2020-08-20 | 2020-08-20 | 1470 | 78/0/0 | 1463/1469 (99.6%) | 1 | 1464/1469 (99.7%) | - | 2 | 373.0 | settled |
| COLPAL | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 1 | 2414/2429 (99.4%) | - | 3 | 370.4 | settled |
| CONCOR | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2416/2429 (99.5%) | 1 | 2417/2429 (99.5%) | - | 3 | 370.9 | settled |
| CROMPTON | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 2 | 2415/2429 (99.4%) | - | 4 | 367.4 | settled |
| CUMMINSIND | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 2 | 2415/2429 (99.4%) | - | 4 | 368.0 | settled |
| DABUR | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 3 | 2416/2429 (99.5%) | - | 2 | 372.7 | settled |
| DALBHARAT | table-path | 2019-01-22 | 2019-01-22 | 1858 | 98/0/0 | 1847/1857 (99.5%) | 0 | 1847/1857 (99.5%) | - | 5 | 350.6 | settled |
| DELHIVERY | table-path | 2022-05-24 | 2022-05-24 | 1036 | 55/0/0 | 1031/1035 (99.6%) | 0 | 1031/1035 (99.6%) | - | 1 | 370.5 | settled |
| DIVISLAB | table-path | 2016-10-01 | 2016-10-03 | 2429 | 129/0/0 | 2412/2428 (99.3%) | 0 | 2412/2428 (99.3%) | - | 3 | 372.8 | settled |
| DIXON | map-required | 2017-09-18 | 2017-09-18 | 2193 | 116/0/0 | 2169/2192 (99.0%) | 0 | 2169/2192 (99.0%) | 1 | 18 | 343.2 | settled |
| DLF | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2406/2429 (99.1%) | 7 | 2413/2429 (99.3%) | - | 2 | 373.3 | settled |
| DMART | table-path | 2017-03-21 | 2017-03-21 | 2314 | 122/0/0 | 2296/2313 (99.3%) | 2 | 2298/2313 (99.4%) | - | 3 | 373.2 | settled |
| DRREDDY | table-path | 2016-10-01 | 2016-10-03 | 2431 | 129/0/0 | 2418/2430 (99.5%) | 0 | 2418/2430 (99.5%) | - | 2 | 373.2 | settled |
| EICHERMOT | table-path | 2016-10-01 | 2016-10-03 | 2429 | 129/0/0 | 2409/2428 (99.2%) | 3 | 2412/2428 (99.3%) | - | 5 | 373.0 | settled |
| ETERNAL | table-path | 2025-04-09 | 2025-04-09 | 320 | 17/0/0 | 319/319 (100.0%) | 0 | 319/319 (100.0%) | - | 0 | 374.0 | settled |
| EXIDEIND | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2415/2429 (99.4%) | 0 | 2415/2429 (99.4%) | - | 3 | 372.8 | settled |
| FEDERALBNK | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2415/2429 (99.4%) | 1 | 2416/2429 (99.5%) | - | 2 | 373.2 | settled |
| FORCEMOT | table-path | 2019-08-19 | 2019-08-19 | 1643 | 88/3/0 | 1614/1642 (98.3%) | 8 | 1622/1642 (98.8%) | - | 17 | 317.6 | settled |
| FORTIS | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2410/2429 (99.2%) | 3 | 2413/2429 (99.3%) | - | 11 | 362.9 | settled |
| GAIL | map-required | 2016-10-01 | 2016-10-03 | 2432 | 129/0/0 | 1990/2431 (81.9%) | 0 | 1990/2431 (81.9%) | 0 | 3 | 373.2 | settled |
| GLENMARK | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2414/2429 (99.4%) | 2 | 2416/2429 (99.5%) | - | 3 | 372.1 | settled |
| GMRAIRPORT | table-path | 2024-12-11 | 2024-12-11 | 402 | 22/0/0 | 400/401 (99.8%) | 0 | 400/401 (99.8%) | - | 0 | 374.2 | settled |
| GODFRYPHLP | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 1 | 2414/2429 (99.4%) | - | 14 | 327.7 | settled |
| GODREJCP | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2410/2429 (99.2%) | 2 | 2412/2429 (99.3%) | - | 3 | 372.5 | settled |
| GODREJPROP | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2411/2429 (99.3%) | 1 | 2412/2429 (99.3%) | - | 11 | 358.2 | settled |
| GRASIM | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 2 | 2415/2429 (99.4%) | - | 3 | 373.0 | settled |
| GVT&D | table-path | 2024-11-05 | 2024-11-05 | 426 | 23/0/0 | 414/425 (97.4%) | 3 | 417/425 (98.1%) | - | 4 | 373.1 | settled |
| HAL | map-required | 2018-03-28 | 2018-03-28 | 2061 | 109/0/0 | 2047/2060 (99.4%) | 1 | 2048/2060 (99.4%) | - | 10 | 341.4 | settled |
| HAVELLS | table-path | 2016-10-01 | 2016-10-03 | 2431 | 129/0/0 | 2415/2430 (99.4%) | 0 | 2415/2430 (99.4%) | - | 3 | 373.0 | settled |
| HCLTECH | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2412/2429 (99.3%) | 1 | 2413/2429 (99.3%) | - | 4 | 373.2 | settled |
| HDFCAMC | map-required | 2018-08-06 | 2018-08-06 | 1970 | 105/0/0 | 1957/1969 (99.4%) | 0 | 1957/1969 (99.4%) | - | 2 | 372.7 | settled |
| HDFCBANK | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2330/2429 (95.9%) | 43 | 2373/2429 (97.7%) | 0 | 3 | 373.2 | settled |
| HDFCLIFE | table-path | 2017-11-17 | 2017-11-17 | 2150 | 114/0/0 | 2132/2149 (99.2%) | 3 | 2135/2149 (99.3%) | - | 2 | 373.3 | settled |
| HEROMOTOCO | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 1 | 2414/2429 (99.4%) | - | 4 | 373.2 | settled |
| HINDALCO | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2412/2429 (99.3%) | 0 | 2412/2429 (99.3%) | - | 4 | 373.2 | settled |
| HINDPETRO | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 1995/2429 (82.1%) | 0 | 1995/2429 (82.1%) | 1 | 5 | 373.2 | settled |
| HINDUNILVR | map-required | 2016-10-01 | 2016-10-03 | 2431 | 129/0/0 | 2416/2430 (99.4%) | 0 | 2416/2430 (99.4%) | - | 3 | 373.2 | settled |
| HINDZINC | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 1 | 2414/2429 (99.4%) | - | 5 | 370.8 | settled |
| HYUNDAI | table-path | 2024-10-22 | 2024-10-22 | 436 | 23/0/0 | 433/435 (99.5%) | 1 | 434/435 (99.8%) | - | 1 | 373.4 | settled |
| ICICIBANK | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2396/2429 (98.6%) | 9 | 2405/2429 (99.0%) | - | 5 | 373.2 | settled |
| ICICIGI | table-path | 2017-09-27 | 2017-09-27 | 2184 | 116/0/0 | 2166/2183 (99.2%) | 1 | 2167/2183 (99.3%) | - | 4 | 370.2 | settled |
| ICICIPRULI | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2412/2429 (99.3%) | 2 | 2414/2429 (99.4%) | - | 3 | 372.7 | settled |
| IDEA | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2406/2429 (99.1%) | 3 | 2409/2429 (99.2%) | - | 5 | 372.9 | settled |
| IDFCFIRSTB | table-path | 2019-01-16 | 2019-01-16 | 1863 | 99/0/0 | 1856/1862 (99.7%) | 0 | 1856/1862 (99.7%) | - | 1 | 373.4 | settled |
| IEX | map-required | 2017-10-23 | 2017-10-23 | 2170 | 115/0/0 | 1148/2169 (52.9%) | 1 | 1149/2169 (53.0%) | 1 | 577 | 337.5 | quarantined |
| INDHOTEL | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2414/2429 (99.4%) | 2 | 2416/2429 (99.5%) | - | 5 | 363.8 | settled |
| INDIANB | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2414/2429 (99.4%) | 0 | 2414/2429 (99.4%) | - | 2 | 370.5 | settled |
| INDIGO | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2408/2429 (99.1%) | 2 | 2410/2429 (99.2%) | - | 2 | 371.1 | settled |
| INDUSINDBK | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2412/2429 (99.3%) | 2 | 2414/2429 (99.4%) | - | 3 | 373.2 | settled |
| INDUSTOWER | map-required | 2020-12-18 | 2020-12-18 | 1387 | 74/0/0 | 1384/1386 (99.9%) | 0 | 1384/1386 (99.9%) | - | 1 | 373.3 | settled |
| INFY | map-required | 2016-10-01 | 2016-10-03 | 2431 | 129/0/0 | 2410/2430 (99.2%) | 3 | 2413/2430 (99.3%) | - | 4 | 373.2 | settled |
| INOXWIND | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2405/2429 (99.0%) | 5 | 2410/2429 (99.2%) | 1 | 16 | 300.2 | settled |
| IOC | map-required | 2016-10-01 | 2016-10-03 | 2432 | 129/0/0 | 2062/2431 (84.8%) | 0 | 2062/2431 (84.8%) | 0 | 4 | 373.2 | settled |
| IREDA | table-path | 2023-11-29 | 2023-11-29 | 659 | 35/0/0 | 643/658 (97.7%) | 6 | 649/658 (98.6%) | - | 1 | 373.2 | settled |
| IRFC | map-required | 2021-01-29 | 2021-01-29 | 1359 | 72/0/0 | 1356/1358 (99.9%) | 0 | 1356/1358 (99.9%) | - | 2 | 373.5 | settled |
| ITC | map-required | 2016-10-01 | 2016-10-03 | 2429 | 129/0/0 | 2411/2428 (99.3%) | 1 | 2412/2428 (99.3%) | - | 4 | 373.2 | settled |
| JINDALSTEL | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 0 | 2413/2429 (99.3%) | - | 3 | 373.2 | settled |
| JIOFIN | table-path | 2023-08-21 | 2023-08-21 | 724 | 39/0/0 | 717/723 (99.2%) | 2 | 719/723 (99.4%) | - | 2 | 373.4 | settled |
| JSWENERGY | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2406/2429 (99.1%) | 5 | 2411/2429 (99.3%) | - | 11 | 362.6 | settled |
| JSWSTEEL | map-required | 2016-10-01 | 2016-10-03 | 2431 | 129/0/0 | 2417/2430 (99.5%) | 0 | 2417/2430 (99.5%) | - | 3 | 373.2 | settled |
| JUBLFOOD | map-required | 2016-10-01 | 2016-10-03 | 2432 | 129/0/0 | 2093/2431 (86.1%) | 1 | 2094/2431 (86.1%) | 1 | 17 | 372.8 | settled |
| KALYANKJIL | table-path | 2021-03-26 | 2021-03-26 | 1320 | 70/0/0 | 1316/1319 (99.8%) | 0 | 1316/1319 (99.8%) | - | 1 | 370.7 | settled |
| KAYNES | table-path | 2022-11-22 | 2022-11-22 | 912 | 48/0/0 | 908/911 (99.7%) | 1 | 909/911 (99.8%) | - | 2 | 369.6 | settled |
| KEI | table-path | 2016-10-01 | 2016-10-03 | 2429 | 129/0/0 | 2409/2428 (99.2%) | 4 | 2413/2428 (99.4%) | - | 10 | 354.1 | settled |
| KFINTECH | table-path | 2022-12-29 | 2022-12-29 | 885 | 47/0/0 | 878/884 (99.3%) | 0 | 878/884 (99.3%) | - | 1 | 365.0 | settled |
| KOTAKBANK | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2410/2429 (99.2%) | 3 | 2413/2429 (99.3%) | - | 2 | 373.3 | settled |
| KPITTECH | table-path | 2019-04-22 | 2019-04-22 | 1799 | 95/0/0 | 1794/1798 (99.8%) | 1 | 1795/1798 (99.8%) | - | 1 | 358.3 | settled |
| LAURUSLABS | table-path | 2016-12-19 | 2016-12-19 | 2377 | 126/0/0 | 2358/2376 (99.2%) | 4 | 2362/2376 (99.4%) | - | 12 | 329.7 | settled |
| LICHSGFIN | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2416/2429 (99.5%) | 0 | 2416/2429 (99.5%) | - | 2 | 373.0 | settled |
| LICI | map-required | 2022-05-17 | 2022-05-17 | 1041 | 55/0/0 | 1039/1040 (99.9%) | 0 | 1039/1040 (99.9%) | - | 1 | 373.2 | settled |
| LODHA | map-required | 2021-04-19 | 2021-04-19 | 1308 | 69/0/0 | 1301/1307 (99.5%) | 2 | 1303/1307 (99.7%) | 0 | 1 | 367.7 | settled |
| LT | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2415/2429 (99.4%) | 0 | 2415/2429 (99.4%) | - | 2 | 373.3 | settled |
| LTF | table-path | 2024-04-23 | 2024-04-23 | 561 | 30/0/0 | 559/560 (99.8%) | 0 | 559/560 (99.8%) | - | 0 | 373.4 | settled |
| LTM | table-path | 2026-02-27 | 2026-02-27 | 99 | 6/0/0 | 98/98 (100.0%) | 0 | 98/98 (100.0%) | - | 0 | 374.9 | settled |
| LUPIN | table-path | 2016-10-01 | 2016-10-03 | 2429 | 129/0/0 | 2413/2428 (99.4%) | 1 | 2414/2428 (99.4%) | - | 2 | 373.1 | settled |
| M&M | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2410/2429 (99.2%) | 4 | 2414/2429 (99.4%) | - | 2 | 373.2 | settled |
| MANAPPURAM | table-path | 2016-10-01 | 2016-10-03 | 2431 | 129/0/0 | 2413/2430 (99.3%) | 5 | 2418/2430 (99.5%) | - | 2 | 372.8 | settled |
| MANKIND | table-path | 2023-05-09 | 2023-05-09 | 799 | 42/0/0 | 790/798 (99.0%) | 0 | 790/798 (99.0%) | - | 3 | 372.2 | settled |
| MARICO | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2417/2429 (99.5%) | 0 | 2417/2429 (99.5%) | - | 2 | 372.3 | settled |
| MARUTI | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2415/2429 (99.4%) | 0 | 2415/2429 (99.4%) | - | 3 | 373.3 | settled |
| MAXHEALTH | table-path | 2020-08-21 | 2020-08-21 | 1469 | 78/0/0 | 1461/1468 (99.5%) | 2 | 1463/1468 (99.7%) | - | 2 | 369.2 | settled |
| MAZDOCK | map-required | 2020-10-12 | 2020-10-12 | 1434 | 76/0/0 | 1430/1433 (99.8%) | 0 | 1430/1433 (99.8%) | - | 2 | 367.2 | settled |
| MCX | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 2 | 2415/2429 (99.4%) | - | 4 | 370.2 | settled |
| MFSL | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 2 | 2415/2429 (99.4%) | - | 3 | 368.9 | settled |
| MOTHERSON | map-required | 2022-06-09 | 2022-06-09 | 1024 | 54/0/0 | 1020/1023 (99.7%) | 0 | 1020/1023 (99.7%) | - | 2 | 373.3 | settled |
| MOTILALOFS | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2406/2429 (99.1%) | 3 | 2409/2429 (99.2%) | - | 13 | 339.2 | settled |
| MPHASIS | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 1 | 2414/2429 (99.4%) | - | 2 | 359.9 | settled |
| MUTHOOTFIN | map-required | 2016-10-01 | 2016-10-03 | 2429 | 129/0/0 | 2412/2428 (99.3%) | 1 | 2413/2428 (99.4%) | - | 3 | 370.3 | settled |
| NAM-INDIA | map-required | 2020-01-23 | 2020-01-23 | 1613 | 85/0/0 | 1610/1612 (99.9%) | 0 | 1610/1612 (99.9%) | - | 1 | 369.4 | settled |
| NATIONALUM | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2414/2429 (99.4%) | 1 | 2415/2429 (99.4%) | - | 2 | 371.6 | settled |
| NAUKRI | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2410/2429 (99.2%) | 3 | 2413/2429 (99.3%) | - | 10 | 349.3 | settled |
| NBCC | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2412/2429 (99.3%) | 3 | 2415/2429 (99.4%) | - | 3 | 372.6 | settled |
| NESTLEIND | map-required | 2016-10-01 | 2016-10-03 | 2431 | 129/0/0 | 1391/2430 (57.2%) | 0 | 1391/2430 (57.2%) | 0 | 247 | 367.1 | quarantined |
| NHPC | map-required | 2016-10-01 | 2016-10-03 | 2429 | 129/0/0 | 2410/2428 (99.3%) | 5 | 2415/2428 (99.5%) | - | 6 | 368.3 | settled |
| NMDC | map-required | 2016-10-01 | 2016-10-03 | 2432 | 129/0/0 | 2049/2431 (84.3%) | 4 | 2053/2431 (84.5%) | 0 | 6 | 372.8 | settled |
| NTPC | map-required | 2016-10-01 | 2016-10-03 | 2429 | 129/0/0 | 1840/2428 (75.8%) | 1 | 1841/2428 (75.8%) | 1 | 5 | 373.2 | quarantined |
| NUVAMA | table-path | 2023-09-26 | 2023-10-11 | 691 | 37/0/0 | 679/690 (98.4%) | 1 | 680/690 (98.6%) | - | 1 | 364.2 | settled |
| NYKAA | map-required | 2021-11-10 | 2021-11-10 | 1168 | 62/0/0 | 1163/1167 (99.7%) | 3 | 1166/1167 (99.9%) | - | 1 | 373.4 | settled |
| OBEROIRLTY | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2394/2429 (98.6%) | 17 | 2411/2429 (99.3%) | - | 6 | 358.6 | settled |
| OFSS | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2412/2429 (99.3%) | 1 | 2413/2429 (99.3%) | - | 12 | 340.3 | settled |
| OIL | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2048/2429 (84.3%) | 0 | 2048/2429 (84.3%) | 0 | 129 | 368.1 | settled |
| ONGC | map-required | 2016-10-01 | 2016-10-03 | 2432 | 129/0/0 | 2419/2431 (99.5%) | 0 | 2419/2431 (99.5%) | - | 1 | 373.3 | settled |
| PAGEIND | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2402/2429 (98.9%) | 1 | 2403/2429 (98.9%) | - | 11 | 358.6 | settled |
| PATANJALI | table-path | 2022-07-13 | 2022-07-13 | 854 | 47/6/0 | 834/853 (97.8%) | 7 | 841/853 (98.6%) | - | 4 | 367.9 | settled |
| PAYTM | table-path | 2021-11-18 | 2021-11-18 | 1162 | 62/0/0 | 1140/1161 (98.2%) | 9 | 1149/1161 (99.0%) | - | 1 | 373.4 | settled |
| PERSISTENT | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2411/2429 (99.3%) | 0 | 2411/2429 (99.3%) | - | 6 | 355.9 | settled |
| PETRONET | map-required | 2016-10-01 | 2016-10-03 | 2432 | 129/0/0 | 2232/2431 (91.8%) | 2 | 2234/2431 (91.9%) | 0 | 2 | 373.0 | settled |
| PFC | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2416/2429 (99.5%) | 0 | 2416/2429 (99.5%) | - | 2 | 373.2 | settled |
| PGEL | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2360/2429 (97.2%) | 18 | 2378/2429 (97.9%) | 0 | 49 | 231.3 | settled |
| PHOENIXLTD | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2407/2429 (99.1%) | 2 | 2409/2429 (99.2%) | - | 13 | 324.4 | settled |
| PIDILITIND | table-path | 2016-10-01 | 2016-10-03 | 2432 | 129/0/0 | 2415/2431 (99.3%) | 2 | 2417/2431 (99.4%) | - | 2 | 372.3 | settled |
| PIIND | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 1 | 2414/2429 (99.4%) | - | 10 | 354.6 | settled |
| PNB | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2415/2429 (99.4%) | 1 | 2416/2429 (99.5%) | - | 2 | 373.3 | settled |
| PNBHOUSING | map-required | 2016-11-07 | 2016-11-07 | 2409 | 127/0/0 | 2389/2408 (99.2%) | 3 | 2392/2408 (99.3%) | - | 6 | 356.7 | settled |
| POLICYBZR | table-path | 2021-11-15 | 2021-11-15 | 1164 | 62/0/0 | 1158/1163 (99.6%) | 1 | 1159/1163 (99.7%) | - | 1 | 373.3 | settled |
| POLYCAB | table-path | 2019-04-16 | 2019-04-16 | 1799 | 95/0/0 | 1789/1798 (99.5%) | 2 | 1791/1798 (99.6%) | - | 1 | 369.7 | settled |
| POWERGRID | map-required | 2016-10-01 | 2016-10-03 | 2431 | 129/0/0 | 2414/2430 (99.3%) | 4 | 2418/2430 (99.5%) | - | 2 | 373.3 | settled |
| POWERINDIA | table-path | 2020-03-30 | 2020-03-30 | 1567 | 83/0/0 | 1554/1566 (99.2%) | 2 | 1556/1566 (99.4%) | - | 10 | 323.3 | settled |
| PREMIERENE | table-path | 2024-09-03 | 2024-09-03 | 470 | 25/0/0 | 466/469 (99.4%) | 3 | 469/469 (100.0%) | - | 0 | 373.5 | settled |
| PRESTIGE | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2415/2429 (99.4%) | 0 | 2415/2429 (99.4%) | - | 10 | 348.7 | settled |
| RADICO | table-path | 2016-10-01 | 2016-10-03 | 2429 | 129/0/0 | 2414/2428 (99.4%) | 0 | 2414/2428 (99.4%) | - | 2 | 362.0 | settled |
| RBLBANK | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2414/2429 (99.4%) | 1 | 2415/2429 (99.4%) | - | 2 | 373.1 | settled |
| RECLTD | map-required | 2016-10-01 | 2016-10-03 | 2432 | 129/0/0 | 2416/2431 (99.4%) | 0 | 2416/2431 (99.4%) | - | 5 | 373.1 | settled |
| RELIANCE | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2404/2429 (99.0%) | 4 | 2408/2429 (99.1%) | 1 | 3 | 373.2 | settled |
| RVNL | map-required | 2019-04-11 | 2019-04-11 | 1804 | 96/0/0 | 1798/1803 (99.7%) | 0 | 1798/1803 (99.7%) | - | 2 | 372.9 | settled |
| SAIL | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2400/2429 (98.8%) | 12 | 2412/2429 (99.3%) | - | 4 | 373.1 | settled |
| SBICARD | table-path | 2020-03-16 | 2020-03-16 | 1577 | 84/0/0 | 1570/1576 (99.6%) | 2 | 1572/1576 (99.7%) | - | 1 | 373.3 | settled |
| SBILIFE | table-path | 2017-10-03 | 2017-10-03 | 2181 | 115/0/0 | 2165/2180 (99.3%) | 0 | 2165/2180 (99.3%) | - | 6 | 371.5 | settled |
| SBIN | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2416/2429 (99.5%) | 0 | 2416/2429 (99.5%) | - | 2 | 373.3 | settled |
| SHREECEM | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2399/2429 (98.8%) | 0 | 2399/2429 (98.8%) | - | 14 | 357.0 | settled |
| SHRIRAMFIN | table-path | 2022-12-20 | 2022-12-20 | 892 | 47/0/0 | 888/891 (99.7%) | 1 | 889/891 (99.8%) | - | 1 | 373.2 | settled |
| SIEMENS | map-required | 2016-10-01 | 2016-10-03 | 2429 | 129/0/0 | 2415/2428 (99.5%) | 0 | 2415/2428 (99.5%) | - | 3 | 368.7 | settled |
| SOLARINDS | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2409/2429 (99.2%) | 5 | 2414/2429 (99.4%) | - | 13 | 265.3 | settled |
| SONACOMS | table-path | 2021-06-24 | 2021-06-24 | 1262 | 67/0/0 | 1259/1261 (99.8%) | 0 | 1259/1261 (99.8%) | - | 1 | 373.2 | settled |
| SRF | map-required | 2016-10-01 | 2016-10-03 | 2432 | 129/0/0 | 2418/2431 (99.5%) | 1 | 2419/2431 (99.5%) | - | 4 | 368.0 | settled |
| SUNPHARMA | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 2 | 2415/2429 (99.4%) | - | 2 | 373.3 | settled |
| SUPREMEIND | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2411/2429 (99.3%) | 0 | 2411/2429 (99.3%) | - | 13 | 332.2 | settled |
| SUZLON | map-required | 2016-10-01 | 2016-10-03 | 2429 | 129/0/0 | 2377/2428 (97.9%) | 15 | 2392/2428 (98.5%) | - | 4 | 372.1 | settled |
| SWIGGY | table-path | 2024-11-13 | 2024-11-13 | 420 | 23/0/0 | 418/419 (99.8%) | 1 | 419/419 (100.0%) | - | 0 | 374.1 | settled |
| TATACONSUM | map-required | 2020-02-27 | 2020-02-27 | 1588 | 84/0/0 | 1582/1587 (99.7%) | 2 | 1584/1587 (99.8%) | - | 2 | 373.2 | settled |
| TATAELXSI | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2415/2429 (99.4%) | 0 | 2415/2429 (99.4%) | - | 3 | 372.3 | settled |
| TATAPOWER | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2402/2429 (98.9%) | 13 | 2415/2429 (99.4%) | - | 3 | 373.0 | settled |
| TATASTEEL | map-required | 2016-10-01 | 2016-10-03 | 2432 | 129/0/0 | 2087/2431 (85.8%) | 0 | 2087/2431 (85.8%) | 0 | 6 | 373.3 | settled |
| TCS | map-required | 2016-10-01 | 2016-10-03 | 2431 | 129/0/0 | 2405/2429 (99.0%) | 4 | 2409/2429 (99.2%) | - | 4 | 373.1 | settled |
| TECHM | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2417/2429 (99.5%) | 0 | 2417/2429 (99.5%) | - | 2 | 373.3 | settled |
| TIINDIA | table-path | 2017-11-02 | 2017-11-02 | 2161 | 114/0/0 | 2137/2160 (98.9%) | 5 | 2142/2160 (99.2%) | - | 13 | 316.0 | settled |
| TITAN | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2414/2429 (99.4%) | 0 | 2414/2429 (99.4%) | - | 2 | 373.2 | settled |
| TMPV | table-path | 2025-10-24 | 2025-10-24 | 186 | 10/0/0 | 185/185 (100.0%) | 0 | 185/185 (100.0%) | - | 0 | 375.0 | settled |
| TORNTPHARM | map-required | 2016-10-01 | 2016-10-03 | 2432 | 129/0/0 | 2425/2431 (99.8%) | 1 | 2426/2431 (99.8%) | - | 3 | 365.1 | settled |
| TRENT | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2412/2429 (99.3%) | 1 | 2413/2429 (99.3%) | - | 13 | 339.6 | settled |
| TVSMOTOR | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2414/2429 (99.4%) | 0 | 2414/2429 (99.4%) | - | 3 | 372.6 | settled |
| ULTRACEMCO | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2414/2429 (99.4%) | 2 | 2416/2429 (99.5%) | - | 2 | 373.1 | settled |
| UNIONBANK | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2416/2429 (99.5%) | 0 | 2416/2429 (99.5%) | - | 2 | 373.0 | settled |
| UNITDSPR | table-path | 2024-06-07 | 2024-06-07 | 529 | 28/0/0 | 527/528 (99.8%) | 0 | 527/528 (99.8%) | - | 0 | 373.7 | settled |
| UNOMINDA | table-path | 2022-08-05 | 2022-08-05 | 983 | 52/0/0 | 977/982 (99.5%) | 0 | 977/982 (99.5%) | - | 3 | 371.9 | settled |
| UPL | map-required | 2016-10-01 | 2016-10-03 | 2431 | 129/0/0 | 1750/2430 (72.0%) | 0 | 1750/2430 (72.0%) | 0 | 680 | 373.2 | quarantined |
| VBL | map-required | 2016-11-08 | 2016-11-08 | 2408 | 127/0/0 | 1270/2407 (52.8%) | 0 | 1270/2407 (52.8%) | 0 | 749 | 336.6 | quarantined |
| VEDL | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2119/2429 (87.2%) | 0 | 2119/2429 (87.2%) | 2 | 5 | 373.2 | settled |
| VMM | table-path | 2024-12-18 | 2024-12-18 | 397 | 21/0/0 | 394/396 (99.5%) | 0 | 394/396 (99.5%) | - | 1 | 374.1 | settled |
| VOLTAS | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2415/2429 (99.4%) | 0 | 2415/2429 (99.4%) | - | 3 | 372.9 | settled |
| WAAREEENER | table-path | 2024-10-28 | 2024-10-28 | 432 | 23/0/0 | 430/431 (99.8%) | 0 | 430/431 (99.8%) | - | 1 | 373.4 | settled |
| WIPRO | map-required | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2415/2429 (99.4%) | 0 | 2415/2429 (99.4%) | - | 3 | 373.2 | settled |
| YESBANK | table-path | 2016-10-01 | 2016-10-03 | 2430 | 129/0/0 | 2413/2429 (99.3%) | 0 | 2413/2429 (99.3%) | - | 3 | 373.3 | settled |
| ZYDUSLIFE | table-path | 2022-03-07 | 2022-03-07 | 1087 | 58/0/0 | 1083/1086 (99.7%) | 1 | 1084/1086 (99.8%) | - | 2 | 373.5 | settled |

### 3a. BEFORE / AFTER the 2026-07-26 rulings (same stored candles, no refetch)

Every row here was gated once under the pre-ruling definitions and then re-gated from the SAME stored candles, so the two columns are a controlled comparison of the rulings themselves: Q-12's volume estimator + candidate set, the CONTEXT 4.5 gate-2 completeness redefinition, and the Q-12-addendum quarantine-recovery reroute. Not one candle was re-downloaded to produce the "after" column.

| Symbol | Route (after) | Gate-1 before | Gate-1 after | Gate-2 excl before | Gate-2 excl after | Status before | Status after |
|---|---|---|---|---|---|---|---|
| 360ONE | table-path | 858/867 (99.0%) | 861/867 (99.3%) | 158 | 1 | settled | settled |
| ABB | map-required | 1632/2429 (67.2%) | 2416/2429 (99.5%) | 828 | 10 | quarantined | settled |
| ABCAPITAL | table-path | 2187/2202 (99.3%) | 2187/2202 (99.3%) | 23 | 2 | settled | settled |
| ADANIENSOL | table-path | 721/723 (99.7%) | 722/723 (99.9%) | 5 | 1 | settled | settled |
| ADANIENT | map-required | 197/2429 (8.1%) | 2413/2429 (99.3%) | 41 | 3 | quarantined | settled |
| ADANIGREEN | table-path | 1990/2005 (99.3%) | 1992/2005 (99.4%) | 316 | 9 | settled | settled |
| ADANIPORTS | table-path | 2410/2429 (99.2%) | 2411/2429 (99.3%) | 16 | 2 | settled | settled |
| ADANIPOWER | table-path | 2401/2429 (98.8%) | 2409/2429 (99.2%) | 39 | 2 | settled | settled |
| ALKEM | table-path | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 852 | 10 | settled | settled |
| AMBER | table-path | 2082/2099 (99.2%) | 2083/2099 (99.2%) | 836 | 12 | settled | settled |
| AMBUJACEM | map-required | 2413/2428 (99.4%) | 2414/2428 (99.4%) | 18 | 3 | settled | settled |
| ANGELONE | table-path | 1163/1166 (99.7%) | 1163/1166 (99.7%) | 6 | 1 | settled | settled |
| APLAPOLLO | map-required | 1892/2431 (77.8%) | 2363/2431 (97.2%) | 989 | 67 | quarantined | settled |
| APOLLOHOSP | table-path | 2415/2429 (99.4%) | 2416/2429 (99.5%) | 84 | 2 | settled | settled |
| ASHOKLEY | map-required | 2416/2429 (99.5%) | 2415/2429 (99.4%) | 16 | 3 | settled | settled |
| ASIANPAINT | table-path | 2417/2430 (99.5%) | 2418/2430 (99.5%) | 16 | 2 | settled | settled |
| ASTRAL | map-required | 1331/2430 (54.8%) | 1699/2430 (69.9%) | 781 | 636 | quarantined | quarantined |
| AUBANK | map-required | 1029/2240 (45.9%) | 2235/2240 (99.8%) | 311 | 3 | quarantined | settled |
| AUROPHARMA | table-path | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 16 | 2 | settled | settled |
| AXISBANK | table-path | 2410/2428 (99.3%) | 2413/2428 (99.4%) | 16 | 2 | settled | settled |
| BAJAJ-AUTO | map-required | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 25 | 2 | settled | settled |
| BAJAJFINSV | map-required | 2417/2431 (99.4%) | 2417/2431 (99.4%) | 2 | 2 | settled | settled |
| BAJAJHLDNG | table-path | 2406/2429 (99.1%) | 2407/2429 (99.1%) | 1549 | 19 | settled | settled |
| BAJFINANCE | table-path | 2410/2429 (99.2%) | 2412/2429 (99.3%) | 16 | 2 | settled | settled |
| BANDHANBNK | table-path | 2046/2061 (99.3%) | 2048/2061 (99.4%) | 21 | 3 | settled | settled |
| BANKBARODA | map-required | 2416/2429 (99.5%) | 2416/2429 (99.5%) | 16 | 2 | settled | settled |
| BANKINDIA | map-required | 2414/2429 (99.4%) | 2415/2429 (99.4%) | 33 | 2 | settled | settled |
| BDL | map-required | 536/1038 (51.6%) | 1035/1038 (99.7%) | 8 | 1 | quarantined | settled |
| BEL | map-required | 955/2431 (39.3%) | 2173/2431 (89.4%) | 25 | 13 | quarantined | settled |
| BHARATFORG | table-path | 2416/2429 (99.5%) | 2416/2429 (99.5%) | 18 | 2 | settled | settled |
| BHARTIARTL | map-required | 2404/2429 (99.0%) | 2410/2429 (99.2%) | 16 | 3 | settled | settled |
| BHEL | map-required | 2416/2429 (99.5%) | 2415/2429 (99.4%) | 16 | 3 | settled | settled |
| BIOCON | table-path | 2416/2429 (99.5%) | 2416/2429 (99.5%) | 24 | 2 | settled | settled |
| BLUESTARCO | map-required | 1276/2429 (52.5%) | 2410/2429 (99.2%) | 1364 | 16 | quarantined | settled |
| BOSCHLTD | table-path | 2408/2429 (99.1%) | 2408/2429 (99.1%) | 855 | 12 | settled | settled |
| BPCL | map-required | 2223/2429 (91.5%) | 2223/2429 (91.5%) | 16 | 4 | settled | settled |
| BRITANNIA | map-required | 2411/2429 (99.3%) | 2414/2429 (99.4%) | 39 | 3 | settled | settled |
| BSE | map-required | 2195/2345 (93.6%) | 2115/2345 (90.2%) | 433 | 106 | settled | settled |
| CAMS | map-required | 1436/1438 (99.9%) | 1436/1438 (99.9%) | 30 | 1 | settled | settled |
| CANBK | map-required | 1043/2429 (42.9%) | 2414/2429 (99.4%) | 16 | 2 | quarantined | settled |
| CDSL | map-required | 2228/2244 (99.3%) | 2230/2244 (99.4%) | 360 | 9 | settled | settled |
| CGPOWER | table-path | 2302/2321 (99.2%) | 2306/2321 (99.4%) | 524 | 3 | settled | settled |
| CHOLAFIN | table-path | 2413/2429 (99.3%) | 2415/2429 (99.4%) | 219 | 2 | settled | settled |
| CIPLA | table-path | 2414/2429 (99.4%) | 2416/2429 (99.5%) | 16 | 2 | settled | settled |
| COALINDIA | map-required | 2415/2429 (99.4%) | 2416/2429 (99.5%) | 16 | 2 | settled | settled |
| COCHINSHIP | map-required | 1957/2215 (88.4%) | 2198/2215 (99.2%) | 837 | 10 | settled | settled |
| COFORGE | table-path | 1463/1469 (99.6%) | 1464/1469 (99.7%) | 12 | 2 | settled | settled |
| COLPAL | map-required | 2413/2429 (99.3%) | 2414/2429 (99.4%) | 3 | 3 | settled | settled |
| CONCOR | table-path | 2416/2429 (99.5%) | 2417/2429 (99.5%) | 124 | 3 | settled | settled |
| CROMPTON | table-path | 2413/2429 (99.3%) | 2415/2429 (99.4%) | 297 | 4 | settled | settled |
| CUMMINSIND | table-path | 2413/2429 (99.3%) | 2415/2429 (99.4%) | 274 | 4 | settled | settled |
| DABUR | table-path | 2413/2429 (99.3%) | 2416/2429 (99.5%) | 36 | 2 | settled | settled |
| DALBHARAT | table-path | 1847/1857 (99.5%) | 1847/1857 (99.5%) | 522 | 5 | settled | settled |
| DELHIVERY | table-path | 1031/1035 (99.6%) | 1031/1035 (99.6%) | 1 | 1 | settled | settled |
| DIVISLAB | table-path | 2412/2428 (99.3%) | 2412/2428 (99.3%) | 3 | 3 | settled | settled |
| DIXON | map-required | 1925/2192 (87.8%) | 2169/2192 (99.0%) | 212 | 18 | settled | settled |
| DLF | table-path | 2406/2429 (99.1%) | 2413/2429 (99.3%) | 2 | 2 | settled | settled |
| DMART | table-path | 2296/2313 (99.3%) | 2298/2313 (99.4%) | 3 | 3 | settled | settled |
| DRREDDY | table-path | 2418/2430 (99.5%) | 2418/2430 (99.5%) | 2 | 2 | settled | settled |
| EICHERMOT | table-path | 2409/2428 (99.2%) | 2412/2428 (99.3%) | 5 | 5 | settled | settled |
| ETERNAL | table-path | 319/319 (100.0%) | 319/319 (100.0%) | 0 | 0 | settled | settled |
| EXIDEIND | table-path | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 3 | 3 | settled | settled |
| FEDERALBNK | table-path | 2415/2429 (99.4%) | 2416/2429 (99.5%) | 2 | 2 | settled | settled |
| FORCEMOT | table-path | 1614/1642 (98.3%) | 1622/1642 (98.8%) | 25 | 17 | settled | settled |
| FORTIS | table-path | 2410/2429 (99.2%) | 2413/2429 (99.3%) | 12 | 11 | settled | settled |
| GAIL | map-required | 1990/2431 (81.9%) | 1990/2431 (81.9%) | 3 | 3 | settled | settled |
| GLENMARK | table-path | 2414/2429 (99.4%) | 2416/2429 (99.5%) | 3 | 3 | settled | settled |
| GMRAIRPORT | table-path | 400/401 (99.8%) | 400/401 (99.8%) | 0 | 0 | settled | settled |
| GODFRYPHLP | map-required | 2413/2429 (99.3%) | 2414/2429 (99.4%) | 14 | 14 | settled | settled |
| GODREJCP | table-path | 2410/2429 (99.2%) | 2412/2429 (99.3%) | 3 | 3 | settled | settled |
| GODREJPROP | table-path | 2411/2429 (99.3%) | 2412/2429 (99.3%) | 11 | 11 | settled | settled |
| GRASIM | map-required | 2413/2429 (99.3%) | 2415/2429 (99.4%) | 3 | 3 | settled | settled |
| GVT&D | table-path | 414/425 (97.4%) | 417/425 (98.1%) | 5 | 4 | settled | settled |
| HAL | map-required | 1675/2060 (81.3%) | 2048/2060 (99.4%) | 77 | 10 | settled | settled |
| HAVELLS | table-path | 2415/2430 (99.4%) | 2415/2430 (99.4%) | 3 | 3 | settled | settled |
| HCLTECH | map-required | 2412/2429 (99.3%) | 2413/2429 (99.3%) | 4 | 4 | settled | settled |
| HDFCAMC | map-required | 1957/1969 (99.4%) | 1957/1969 (99.4%) | 2 | 2 | settled | settled |
| HDFCBANK | map-required | 2330/2429 (95.9%) | 2373/2429 (97.7%) | 4 | 3 | settled | settled |
| HDFCLIFE | table-path | 2132/2149 (99.2%) | 2135/2149 (99.3%) | 2 | 2 | settled | settled |
| HEROMOTOCO | map-required | 2413/2429 (99.3%) | 2414/2429 (99.4%) | 4 | 4 | settled | settled |
| HINDALCO | table-path | 2412/2429 (99.3%) | 2412/2429 (99.3%) | 4 | 4 | settled | settled |
| HINDPETRO | map-required | 1766/2429 (72.7%) | 1995/2429 (82.1%) | 5 | 5 | quarantined | settled |
| HINDUNILVR | map-required | 2416/2430 (99.4%) | 2416/2430 (99.4%) | 3 | 3 | settled | settled |
| HINDZINC | map-required | 2413/2429 (99.3%) | 2414/2429 (99.4%) | 5 | 5 | settled | settled |
| HYUNDAI | table-path | 433/435 (99.5%) | 434/435 (99.8%) | 2 | 1 | settled | settled |
| ICICIBANK | table-path | 2396/2429 (98.6%) | 2405/2429 (99.0%) | 6 | 5 | settled | settled |
| ICICIGI | table-path | 2166/2183 (99.2%) | 2167/2183 (99.3%) | 4 | 4 | settled | settled |
| ICICIPRULI | table-path | 2412/2429 (99.3%) | 2414/2429 (99.4%) | 3 | 3 | settled | settled |
| IDEA | map-required | 2406/2429 (99.1%) | 2409/2429 (99.2%) | 5 | 5 | settled | settled |
| IDFCFIRSTB | table-path | 1856/1862 (99.7%) | 1856/1862 (99.7%) | 1 | 1 | settled | settled |
| IEX | map-required | 1148/2169 (52.9%) | 1149/2169 (53.0%) | 577 | 577 | quarantined | quarantined |
| INDHOTEL | map-required | 2414/2429 (99.4%) | 2416/2429 (99.5%) | 5 | 5 | settled | settled |
| INDIANB | map-required | 2414/2429 (99.4%) | 2414/2429 (99.4%) | 2 | 2 | settled | settled |
| INDIGO | map-required | 2408/2429 (99.1%) | 2410/2429 (99.2%) | 2 | 2 | settled | settled |
| INDUSINDBK | table-path | 2412/2429 (99.3%) | 2414/2429 (99.4%) | 3 | 3 | settled | settled |
| INDUSTOWER | map-required | 1384/1386 (99.9%) | 1384/1386 (99.9%) | 1 | 1 | settled | settled |
| INFY | map-required | 2410/2430 (99.2%) | 2413/2430 (99.3%) | 4 | 4 | settled | settled |
| INOXWIND | map-required | 586/2429 (24.1%) | 2410/2429 (99.2%) | 1445 | 16 | quarantined | settled |
| IOC | map-required | 2062/2431 (84.8%) | 2062/2431 (84.8%) | 4 | 4 | settled | settled |
| IREDA | table-path | 643/658 (97.7%) | 649/658 (98.6%) | 1 | 1 | settled | settled |
| IRFC | map-required | 1356/1358 (99.9%) | 1356/1358 (99.9%) | 2 | 2 | settled | settled |
| ITC | map-required | 2411/2428 (99.3%) | 2412/2428 (99.3%) | 4 | 4 | settled | settled |
| JINDALSTEL | table-path | 2413/2429 (99.3%) | 2413/2429 (99.3%) | 3 | 3 | settled | settled |
| JIOFIN | table-path | 717/723 (99.2%) | 719/723 (99.4%) | 2 | 2 | settled | settled |
| JSWENERGY | map-required | 2406/2429 (99.1%) | 2411/2429 (99.3%) | 13 | 11 | settled | settled |
| JSWSTEEL | map-required | 2353/2430 (96.8%) | 2417/2430 (99.5%) | 4 | 3 | settled | settled |
| JUBLFOOD | map-required | 1054/2431 (43.4%) | 2094/2431 (86.1%) | 24 | 17 | quarantined | settled |
| KALYANKJIL | table-path | 1316/1319 (99.8%) | 1316/1319 (99.8%) | 1 | 1 | settled | settled |
| KAYNES | table-path | 908/911 (99.7%) | 909/911 (99.8%) | 2 | 2 | settled | settled |
| KEI | table-path | 2409/2428 (99.2%) | 2413/2428 (99.4%) | 10 | 10 | settled | settled |
| KFINTECH | table-path | 878/884 (99.3%) | 878/884 (99.3%) | 1 | 1 | settled | settled |
| KOTAKBANK | table-path | 2410/2429 (99.2%) | 2413/2429 (99.3%) | 2 | 2 | settled | settled |
| KPITTECH | table-path | 1794/1798 (99.8%) | 1795/1798 (99.8%) | 2 | 1 | settled | settled |
| LAURUSLABS | table-path | 2358/2376 (99.2%) | 2362/2376 (99.4%) | 14 | 12 | settled | settled |
| LICHSGFIN | map-required | 2416/2429 (99.5%) | 2416/2429 (99.5%) | 2 | 2 | settled | settled |
| LICI | map-required | 1039/1040 (99.9%) | 1039/1040 (99.9%) | 1 | 1 | settled | settled |
| LODHA | map-required | 1276/1307 (97.6%) | 1303/1307 (99.7%) | 7 | 1 | settled | settled |
| LT | table-path | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 2 | 2 | settled | settled |
| LTF | table-path | 559/560 (99.8%) | 559/560 (99.8%) | 0 | 0 | settled | settled |
| LTM | table-path | 98/98 (100.0%) | 98/98 (100.0%) | 0 | 0 | settled | settled |
| LUPIN | table-path | 2413/2428 (99.4%) | 2414/2428 (99.4%) | 2 | 2 | settled | settled |
| M&M | table-path | 2410/2429 (99.2%) | 2414/2429 (99.4%) | 2 | 2 | settled | settled |
| MANAPPURAM | table-path | 2413/2430 (99.3%) | 2418/2430 (99.5%) | 2 | 2 | settled | settled |
| MANKIND | table-path | 790/798 (99.0%) | 790/798 (99.0%) | 3 | 3 | settled | settled |
| MARICO | table-path | 2417/2429 (99.5%) | 2417/2429 (99.5%) | 2 | 2 | settled | settled |
| MARUTI | table-path | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 3 | 3 | settled | settled |
| MAXHEALTH | table-path | 1461/1468 (99.5%) | 1463/1468 (99.7%) | 2 | 2 | settled | settled |
| MAZDOCK | map-required | 1430/1433 (99.8%) | 1430/1433 (99.8%) | 2 | 2 | settled | settled |
| MCX | map-required | 2413/2429 (99.3%) | 2415/2429 (99.4%) | 4 | 4 | settled | settled |
| MFSL | table-path | 2413/2429 (99.3%) | 2415/2429 (99.4%) | 4 | 3 | settled | settled |
| MOTHERSON | map-required | 941/1023 (92.0%) | 1020/1023 (99.7%) | 2 | 2 | settled | settled |
| MOTILALOFS | map-required | 1024/2429 (42.2%) | 2409/2429 (99.2%) | 865 | 13 | quarantined | settled |
| MPHASIS | map-required | 2413/2429 (99.3%) | 2414/2429 (99.4%) | 2 | 2 | settled | settled |
| MUTHOOTFIN | map-required | 2412/2428 (99.3%) | 2413/2428 (99.4%) | 4 | 3 | settled | settled |
| NAM-INDIA | map-required | 1610/1612 (99.9%) | 1610/1612 (99.9%) | 1 | 1 | settled | settled |
| NATIONALUM | map-required | 2414/2429 (99.4%) | 2415/2429 (99.4%) | 2 | 2 | settled | settled |
| NAUKRI | table-path | 2410/2429 (99.2%) | 2413/2429 (99.3%) | 12 | 10 | settled | settled |
| NBCC | map-required | 2412/2429 (99.3%) | 2415/2429 (99.4%) | 3 | 3 | settled | settled |
| NESTLEIND | map-required | 1129/2430 (46.5%) | 1391/2430 (57.2%) | 249 | 247 | quarantined | quarantined |
| NHPC | map-required | 2410/2428 (99.3%) | 2415/2428 (99.5%) | 6 | 6 | settled | settled |
| NMDC | map-required | 2049/2431 (84.3%) | 2053/2431 (84.5%) | 6 | 6 | settled | settled |
| NTPC | map-required | 1840/2428 (75.8%) | 1841/2428 (75.8%) | 5 | 5 | quarantined | quarantined |
| NUVAMA | table-path | 679/690 (98.4%) | 680/690 (98.6%) | 1 | 1 | settled | settled |
| NYKAA | map-required | 915/1167 (78.4%) | 1166/1167 (99.9%) | 3 | 1 | quarantined | settled |
| OBEROIRLTY | table-path | 2394/2429 (98.6%) | 2411/2429 (99.3%) | 10 | 6 | settled | settled |
| OFSS | map-required | 2412/2429 (99.3%) | 2413/2429 (99.3%) | 12 | 12 | settled | settled |
| OIL | map-required | 2048/2429 (84.3%) | 2048/2429 (84.3%) | 129 | 129 | settled | settled |
| ONGC | map-required | 2419/2431 (99.5%) | 2419/2431 (99.5%) | 1 | 1 | settled | settled |
| PAGEIND | table-path | 2402/2429 (98.9%) | 2403/2429 (98.9%) | 11 | 11 | settled | settled |
| PATANJALI | table-path | 834/853 (97.8%) | 841/853 (98.6%) | 4 | 4 | settled | settled |
| PAYTM | table-path | 1140/1161 (98.2%) | 1149/1161 (99.0%) | 1 | 1 | settled | settled |
| PERSISTENT | map-required | 1084/2429 (44.6%) | 2411/2429 (99.3%) | 573 | 6 | quarantined | settled |
| PETRONET | map-required | 2232/2431 (91.8%) | 2234/2431 (91.9%) | 2 | 2 | settled | settled |
| PFC | map-required | 2295/2429 (94.5%) | 2416/2429 (99.5%) | 2 | 2 | settled | settled |
| PGEL | map-required | 2360/2429 (97.2%) | 2378/2429 (97.9%) | 66 | 49 | settled | settled |
| PHOENIXLTD | table-path | 2407/2429 (99.1%) | 2409/2429 (99.2%) | 15 | 13 | settled | settled |
| PIDILITIND | table-path | 2415/2431 (99.3%) | 2417/2431 (99.4%) | 2 | 2 | settled | settled |
| PIIND | table-path | 2413/2429 (99.3%) | 2414/2429 (99.4%) | 11 | 10 | settled | settled |
| PNB | map-required | 2415/2429 (99.4%) | 2416/2429 (99.5%) | 2 | 2 | settled | settled |
| PNBHOUSING | map-required | 1662/2408 (69.0%) | 2392/2408 (99.3%) | 304 | 6 | quarantined | settled |
| POLICYBZR | table-path | 1158/1163 (99.6%) | 1159/1163 (99.7%) | 1 | 1 | settled | settled |
| POLYCAB | table-path | 1789/1798 (99.5%) | 1791/1798 (99.6%) | 1 | 1 | settled | settled |
| POWERGRID | map-required | 2387/2430 (98.2%) | 2418/2430 (99.5%) | 2 | 2 | settled | settled |
| POWERINDIA | table-path | 1554/1566 (99.2%) | 1556/1566 (99.4%) | 12 | 10 | settled | settled |
| PREMIERENE | table-path | 466/469 (99.4%) | 469/469 (100.0%) | 1 | 0 | settled | settled |
| PRESTIGE | table-path | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 10 | 10 | settled | settled |
| RADICO | table-path | 2414/2428 (99.4%) | 2414/2428 (99.4%) | 2 | 2 | settled | settled |
| RBLBANK | table-path | 2414/2429 (99.4%) | 2415/2429 (99.4%) | 2 | 2 | settled | settled |
| RECLTD | map-required | 2416/2431 (99.4%) | 2416/2431 (99.4%) | 5 | 5 | settled | settled |
| RELIANCE | map-required | 1996/2429 (82.2%) | 2408/2429 (99.1%) | 5 | 3 | settled | settled |
| RVNL | map-required | 1798/1803 (99.7%) | 1798/1803 (99.7%) | 2 | 2 | settled | settled |
| SAIL | map-required | 2400/2429 (98.8%) | 2412/2429 (99.3%) | 4 | 4 | settled | settled |
| SBICARD | table-path | 1570/1576 (99.6%) | 1572/1576 (99.7%) | 1 | 1 | settled | settled |
| SBILIFE | table-path | 2165/2180 (99.3%) | 2165/2180 (99.3%) | 6 | 6 | settled | settled |
| SBIN | table-path | 2416/2429 (99.5%) | 2416/2429 (99.5%) | 2 | 2 | settled | settled |
| SHREECEM | table-path | 2399/2429 (98.8%) | 2399/2429 (98.8%) | 14 | 14 | settled | settled |
| SHRIRAMFIN | table-path | 888/891 (99.7%) | 889/891 (99.8%) | 1 | 1 | settled | settled |
| SIEMENS | map-required | 2415/2428 (99.5%) | 2415/2428 (99.5%) | 3 | 3 | settled | settled |
| SOLARINDS | table-path | 2409/2429 (99.2%) | 2414/2429 (99.4%) | 17 | 13 | settled | settled |
| SONACOMS | table-path | 1259/1261 (99.8%) | 1259/1261 (99.8%) | 1 | 1 | settled | settled |
| SRF | map-required | 2418/2431 (99.5%) | 2419/2431 (99.5%) | 4 | 4 | settled | settled |
| SUNPHARMA | table-path | 2413/2429 (99.3%) | 2415/2429 (99.4%) | 2 | 2 | settled | settled |
| SUPREMEIND | table-path | 2411/2429 (99.3%) | 2411/2429 (99.3%) | 13 | 13 | settled | settled |
| SUZLON | map-required | 2300/2351 (97.8%) | 2392/2428 (98.5%) | 4 | 4 | settled | settled |
| SWIGGY | table-path | 418/419 (99.8%) | 419/419 (100.0%) | 1 | 0 | settled | settled |
| TATACONSUM | map-required | 1582/1587 (99.7%) | 1584/1587 (99.8%) | 2 | 2 | settled | settled |
| TATAELXSI | table-path | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 3 | 3 | settled | settled |
| TATAPOWER | map-required | 2402/2429 (98.9%) | 2415/2429 (99.4%) | 3 | 3 | settled | settled |
| TATASTEEL | map-required | 2087/2431 (85.8%) | 2087/2431 (85.8%) | 6 | 6 | settled | settled |
| TCS | map-required | 2405/2429 (99.0%) | 2409/2429 (99.2%) | 4 | 4 | settled | settled |
| TECHM | map-required | 2417/2429 (99.5%) | 2417/2429 (99.5%) | 2 | 2 | settled | settled |
| TIINDIA | table-path | 2137/2160 (98.9%) | 2142/2160 (99.2%) | 18 | 13 | settled | settled |
| TITAN | table-path | 2414/2429 (99.4%) | 2414/2429 (99.4%) | 2 | 2 | settled | settled |
| TMPV | table-path | 185/185 (100.0%) | 185/185 (100.0%) | 0 | 0 | settled | settled |
| TORNTPHARM | map-required | 1007/2431 (41.4%) | 2426/2431 (99.8%) | 372 | 3 | quarantined | settled |
| TRENT | table-path | 2412/2429 (99.3%) | 2413/2429 (99.3%) | 14 | 13 | settled | settled |
| TVSMOTOR | map-required | 2414/2429 (99.4%) | 2414/2429 (99.4%) | 3 | 3 | settled | settled |
| ULTRACEMCO | table-path | 2414/2429 (99.4%) | 2416/2429 (99.5%) | 2 | 2 | settled | settled |
| UNIONBANK | map-required | 2416/2429 (99.5%) | 2416/2429 (99.5%) | 2 | 2 | settled | settled |
| UNITDSPR | table-path | 527/528 (99.8%) | 527/528 (99.8%) | 0 | 0 | settled | settled |
| UNOMINDA | table-path | 977/982 (99.5%) | 977/982 (99.5%) | 3 | 3 | settled | settled |
| UPL | map-required | 1750/2430 (72.0%) | 1750/2430 (72.0%) | 680 | 680 | quarantined | quarantined |
| VBL | map-required | 1270/2407 (52.8%) | 1270/2407 (52.8%) | 749 | 749 | quarantined | quarantined |
| VEDL | map-required | 638/2429 (26.3%) | 2119/2429 (87.2%) | 15 | 5 | quarantined | settled |
| VMM | table-path | 394/396 (99.5%) | 394/396 (99.5%) | 1 | 1 | settled | settled |
| VOLTAS | table-path | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 3 | 3 | settled | settled |
| WAAREEENER | table-path | 430/431 (99.8%) | 430/431 (99.8%) | 1 | 1 | settled | settled |
| WIPRO | map-required | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 3 | 3 | settled | settled |
| YESBANK | table-path | 2413/2429 (99.3%) | 2413/2429 (99.3%) | 3 | 3 | settled | settled |
| ZYDUSLIFE | table-path | 1083/1086 (99.7%) | 1084/1086 (99.8%) | 2 | 2 | settled | settled |
| **TOTAL (210)** | | **401,844/434,514 (92.5%)** | **423,014/434,591 (97.3%)** | **20,056** | **4,085** | | |

### 3b. Traded-minute statistics per symbol (the completeness ruling's liquidity numbers)

The architect's completeness ruling: "NO liquidity filter is invented (the trader specified none; per-symbol traded-minutes statistics are reported for his eyes)". These are those statistics. **Nothing in the code consumes them** -- there is no minimum traded minutes, no minimum volume and no symbol drop anywhere. `Liquidity days` counts days INCLUDED while carrying more than 15 tradeless minutes -- days the pre-ruling gate 2 excluded.

| Symbol | Avg min/day | Median min/day | Min min/day | Liquidity days | Liquidity days as % of stored |
|---|---|---|---|---|---|
| 360ONE | 363.6 | 375 | 0 | 384 | 44.3% |
| ABB | 350.9 | 374 | 0 | 1270 | 52.2% |
| ABCAPITAL | 372.7 | 375 | 0 | 376 | 17.1% |
| ADANIENSOL | 372.9 | 375 | 0 | 44 | 6.1% |
| ADANIENT | 372.6 | 375 | 0 | 296 | 12.2% |
| ADANIGREEN | 362.8 | 375 | 0 | 518 | 25.8% |
| ADANIPORTS | 373.2 | 375 | 0 | 48 | 2.0% |
| ADANIPOWER | 372.4 | 375 | 0 | 371 | 15.3% |
| ALKEM | 343.9 | 372 | 0 | 1508 | 62.1% |
| AMBER | 327.3 | 370 | 0 | 1317 | 62.7% |
| AMBUJACEM | 373.0 | 375 | 0 | 196 | 8.1% |
| ANGELONE | 373.1 | 375 | 0 | 147 | 12.6% |
| APLAPOLLO | 313.9 | 374 | 0 | 1178 | 48.4% |
| APOLLOHOSP | 371.9 | 375 | 0 | 361 | 14.9% |
| ASHOKLEY | 373.3 | 375 | 0 | 26 | 1.1% |
| ASIANPAINT | 373.2 | 375 | 0 | 47 | 1.9% |
| ASTRAL | 332.7 | 375 | 0 | 434 | 17.9% |
| AUBANK | 365.6 | 375 | 0 | 593 | 26.5% |
| AUROPHARMA | 373.2 | 375 | 0 | 114 | 4.7% |
| AXISBANK | 373.3 | 375 | 0 | 25 | 1.0% |
| BAJAJ-AUTO | 373.0 | 375 | 0 | 201 | 8.3% |
| BAJAJFINSV | 372.4 | 375 | 0 | 282 | 11.6% |
| BAJAJHLDNG | 314.9 | 339 | 0 | 2071 | 85.3% |
| BAJFINANCE | 373.2 | 375 | 0 | 47 | 1.9% |
| BANDHANBNK | 373.1 | 375 | 0 | 131 | 6.4% |
| BANKBARODA | 373.3 | 375 | 0 | 23 | 0.9% |
| BANKINDIA | 372.6 | 375 | 0 | 455 | 18.7% |
| BDL | 372.9 | 375 | 0 | 112 | 10.8% |
| BEL | 373.1 | 375 | 0 | 79 | 3.2% |
| BHARATFORG | 372.9 | 375 | 0 | 327 | 13.5% |
| BHARTIARTL | 373.2 | 375 | 0 | 51 | 2.1% |
| BHEL | 373.3 | 375 | 0 | 52 | 2.1% |
| BIOCON | 373.0 | 375 | 0 | 204 | 8.4% |
| BLUESTARCO | 321.0 | 351 | 0 | 1850 | 76.2% |
| BOSCHLTD | 357.2 | 367 | 0 | 1922 | 79.1% |
| BPCL | 373.3 | 375 | 0 | 21 | 0.9% |
| BRITANNIA | 372.7 | 375 | 0 | 259 | 10.7% |
| BSE | 365.1 | 375 | 0 | 749 | 31.9% |
| CAMS | 372.2 | 375 | 0 | 308 | 21.4% |
| CANBK | 373.2 | 375 | 0 | 81 | 3.3% |
| CDSL | 364.2 | 375 | 0 | 605 | 27.0% |
| CGPOWER | 356.2 | 375 | 0 | 1097 | 47.3% |
| CHOLAFIN | 368.2 | 375 | 0 | 539 | 22.2% |
| CIPLA | 373.2 | 375 | 0 | 98 | 4.0% |
| COALINDIA | 373.3 | 375 | 0 | 31 | 1.3% |
| COCHINSHIP | 350.0 | 371 | 0 | 1252 | 56.5% |
| COFORGE | 373.0 | 375 | 0 | 112 | 7.6% |
| COLPAL | 370.4 | 375 | 0 | 762 | 31.4% |
| CONCOR | 370.9 | 375 | 0 | 601 | 24.7% |
| CROMPTON | 367.4 | 375 | 0 | 660 | 27.2% |
| CUMMINSIND | 368.0 | 375 | 0 | 812 | 33.4% |
| DABUR | 372.7 | 375 | 0 | 248 | 10.2% |
| DALBHARAT | 350.6 | 373 | 0 | 1125 | 60.5% |
| DELHIVERY | 370.5 | 375 | 0 | 293 | 28.3% |
| DIVISLAB | 372.8 | 375 | 0 | 277 | 11.4% |
| DIXON | 343.2 | 375 | 0 | 704 | 32.1% |
| DLF | 373.3 | 375 | 0 | 43 | 1.8% |
| DMART | 373.2 | 375 | 0 | 202 | 8.7% |
| DRREDDY | 373.2 | 375 | 0 | 115 | 4.7% |
| EICHERMOT | 373.0 | 375 | 0 | 170 | 7.0% |
| ETERNAL | 374.0 | 375 | 60 | 1 | 0.3% |
| EXIDEIND | 372.8 | 375 | 0 | 348 | 14.3% |
| FEDERALBNK | 373.2 | 375 | 0 | 44 | 1.8% |
| FORCEMOT | 317.6 | 332 | 0 | 1363 | 83.0% |
| FORTIS | 362.9 | 375 | 0 | 984 | 40.5% |
| GAIL | 373.2 | 375 | 0 | 33 | 1.4% |
| GLENMARK | 372.1 | 375 | 0 | 657 | 27.0% |
| GMRAIRPORT | 374.2 | 375 | 60 | 17 | 4.2% |
| GODFRYPHLP | 327.7 | 345 | 0 | 1981 | 81.5% |
| GODREJCP | 372.5 | 375 | 0 | 339 | 14.0% |
| GODREJPROP | 358.2 | 375 | 0 | 973 | 40.0% |
| GRASIM | 373.0 | 375 | 0 | 163 | 6.7% |
| GVT&D | 373.1 | 375 | 60 | 35 | 8.2% |
| HAL | 341.4 | 375 | 0 | 711 | 34.5% |
| HAVELLS | 373.0 | 375 | 0 | 261 | 10.7% |
| HCLTECH | 373.2 | 375 | 0 | 35 | 1.4% |
| HDFCAMC | 372.7 | 375 | 0 | 280 | 14.2% |
| HDFCBANK | 373.2 | 375 | 0 | 35 | 1.4% |
| HDFCLIFE | 373.3 | 375 | 0 | 85 | 4.0% |
| HEROMOTOCO | 373.2 | 375 | 0 | 83 | 3.4% |
| HINDALCO | 373.2 | 375 | 0 | 23 | 0.9% |
| HINDPETRO | 373.2 | 375 | 0 | 29 | 1.2% |
| HINDUNILVR | 373.2 | 375 | 0 | 33 | 1.4% |
| HINDZINC | 370.8 | 375 | 0 | 833 | 34.3% |
| HYUNDAI | 373.4 | 375 | 0 | 11 | 2.5% |
| ICICIBANK | 373.2 | 375 | 0 | 21 | 0.9% |
| ICICIGI | 370.2 | 375 | 0 | 482 | 22.1% |
| ICICIPRULI | 372.7 | 375 | 0 | 360 | 14.8% |
| IDEA | 372.9 | 375 | 0 | 69 | 2.8% |
| IDFCFIRSTB | 373.4 | 375 | 0 | 24 | 1.3% |
| IEX | 337.5 | 375 | 0 | 125 | 5.8% |
| INDHOTEL | 363.8 | 375 | 0 | 816 | 33.6% |
| INDIANB | 370.5 | 375 | 0 | 862 | 35.5% |
| INDIGO | 371.1 | 375 | 0 | 403 | 16.6% |
| INDUSINDBK | 373.2 | 375 | 0 | 39 | 1.6% |
| INDUSTOWER | 373.3 | 375 | 0 | 89 | 6.4% |
| INFY | 373.2 | 375 | 0 | 19 | 0.8% |
| INOXWIND | 300.2 | 329 | 0 | 1730 | 71.2% |
| IOC | 373.2 | 375 | 0 | 19 | 0.8% |
| IREDA | 373.2 | 375 | 0 | 4 | 0.6% |
| IRFC | 373.5 | 375 | 0 | 16 | 1.2% |
| ITC | 373.2 | 375 | 0 | 22 | 0.9% |
| JINDALSTEL | 373.2 | 375 | 0 | 106 | 4.4% |
| JIOFIN | 373.4 | 375 | 0 | 3 | 0.4% |
| JSWENERGY | 362.6 | 375 | 0 | 1108 | 45.6% |
| JSWSTEEL | 373.2 | 375 | 0 | 66 | 2.7% |
| JUBLFOOD | 372.8 | 375 | 0 | 179 | 7.4% |
| KALYANKJIL | 370.7 | 375 | 0 | 278 | 21.1% |
| KAYNES | 369.6 | 375 | 0 | 222 | 24.3% |
| KEI | 354.1 | 373 | 0 | 1383 | 56.9% |
| KFINTECH | 365.0 | 375 | 0 | 314 | 35.5% |
| KOTAKBANK | 373.3 | 375 | 0 | 43 | 1.8% |
| KPITTECH | 358.3 | 375 | 0 | 475 | 26.4% |
| LAURUSLABS | 329.7 | 375 | 0 | 951 | 40.0% |
| LICHSGFIN | 373.0 | 375 | 0 | 263 | 10.8% |
| LICI | 373.2 | 375 | 0 | 10 | 1.0% |
| LODHA | 367.7 | 375 | 0 | 421 | 32.2% |
| LT | 373.3 | 375 | 0 | 24 | 1.0% |
| LTF | 373.4 | 375 | 0 | 7 | 1.2% |
| LTM | 374.9 | 375 | 373 | 7 | 7.1% |
| LUPIN | 373.1 | 375 | 0 | 141 | 5.8% |
| M&M | 373.2 | 375 | 0 | 39 | 1.6% |
| MANAPPURAM | 372.8 | 375 | 0 | 325 | 13.4% |
| MANKIND | 372.2 | 375 | 0 | 178 | 22.3% |
| MARICO | 372.3 | 375 | 0 | 308 | 12.7% |
| MARUTI | 373.3 | 375 | 0 | 24 | 1.0% |
| MAXHEALTH | 369.2 | 375 | 0 | 281 | 19.1% |
| MAZDOCK | 367.2 | 375 | 0 | 405 | 28.2% |
| MCX | 370.2 | 375 | 0 | 928 | 38.2% |
| MFSL | 368.9 | 375 | 0 | 851 | 35.0% |
| MOTHERSON | 373.3 | 375 | 0 | 4 | 0.4% |
| MOTILALOFS | 339.2 | 365 | 0 | 1592 | 65.5% |
| MPHASIS | 359.9 | 375 | 0 | 832 | 34.2% |
| MUTHOOTFIN | 370.3 | 375 | 0 | 594 | 24.5% |
| NAM-INDIA | 369.4 | 375 | 0 | 646 | 40.0% |
| NATIONALUM | 371.6 | 375 | 0 | 413 | 17.0% |
| NAUKRI | 349.3 | 375 | 0 | 741 | 30.5% |
| NBCC | 372.6 | 375 | 0 | 390 | 16.0% |
| NESTLEIND | 367.1 | 375 | 0 | 386 | 15.9% |
| NHPC | 368.3 | 375 | 0 | 880 | 36.2% |
| NMDC | 372.8 | 375 | 0 | 329 | 13.5% |
| NTPC | 373.2 | 375 | 0 | 72 | 3.0% |
| NUVAMA | 364.2 | 373 | 0 | 428 | 61.9% |
| NYKAA | 373.4 | 375 | 0 | 25 | 2.1% |
| OBEROIRLTY | 358.6 | 374 | 0 | 1281 | 52.7% |
| OFSS | 340.3 | 367 | 0 | 1647 | 67.8% |
| OIL | 368.1 | 375 | 0 | 971 | 40.0% |
| ONGC | 373.3 | 375 | 0 | 23 | 0.9% |
| PAGEIND | 358.6 | 371 | 0 | 1665 | 68.5% |
| PATANJALI | 367.9 | 374 | 0 | 522 | 61.1% |
| PAYTM | 373.4 | 375 | 0 | 14 | 1.2% |
| PERSISTENT | 355.9 | 375 | 0 | 948 | 39.0% |
| PETRONET | 373.0 | 375 | 0 | 300 | 12.3% |
| PFC | 373.2 | 375 | 0 | 171 | 7.0% |
| PGEL | 231.3 | 219 | 0 | 1868 | 76.9% |
| PHOENIXLTD | 324.4 | 369 | 0 | 1514 | 62.3% |
| PIDILITIND | 372.3 | 375 | 0 | 358 | 14.7% |
| PIIND | 354.6 | 375 | 0 | 1128 | 46.4% |
| PNB | 373.3 | 375 | 0 | 26 | 1.1% |
| PNBHOUSING | 356.7 | 372 | 0 | 1441 | 59.8% |
| POLICYBZR | 373.3 | 375 | 0 | 114 | 9.8% |
| POLYCAB | 369.7 | 375 | 0 | 353 | 19.6% |
| POWERGRID | 373.3 | 375 | 0 | 58 | 2.4% |
| POWERINDIA | 323.3 | 355 | 0 | 1080 | 68.9% |
| PREMIERENE | 373.5 | 375 | 0 | 26 | 5.5% |
| PRESTIGE | 348.7 | 373 | 0 | 1408 | 57.9% |
| RADICO | 362.0 | 374 | 0 | 1362 | 56.1% |
| RBLBANK | 373.1 | 375 | 0 | 162 | 6.7% |
| RECLTD | 373.1 | 375 | 0 | 584 | 24.0% |
| RELIANCE | 373.2 | 375 | 0 | 24 | 1.0% |
| RVNL | 372.9 | 375 | 0 | 217 | 12.0% |
| SAIL | 373.1 | 375 | 0 | 175 | 7.2% |
| SBICARD | 373.3 | 375 | 0 | 43 | 2.7% |
| SBILIFE | 371.5 | 375 | 0 | 254 | 11.6% |
| SBIN | 373.3 | 375 | 0 | 25 | 1.0% |
| SHREECEM | 357.0 | 371 | 0 | 1638 | 67.4% |
| SHRIRAMFIN | 373.2 | 375 | 0 | 36 | 4.0% |
| SIEMENS | 368.7 | 375 | 0 | 1013 | 41.7% |
| SOLARINDS | 265.3 | 310 | 0 | 1794 | 73.8% |
| SONACOMS | 373.2 | 375 | 0 | 57 | 4.5% |
| SRF | 368.0 | 375 | 0 | 786 | 32.3% |
| SUNPHARMA | 373.3 | 375 | 0 | 24 | 1.0% |
| SUPREMEIND | 332.2 | 365 | 0 | 1717 | 70.7% |
| SUZLON | 372.1 | 375 | 0 | 401 | 16.5% |
| SWIGGY | 374.1 | 375 | 60 | 2 | 0.5% |
| TATACONSUM | 373.2 | 375 | 0 | 20 | 1.3% |
| TATAELXSI | 372.3 | 375 | 0 | 558 | 23.0% |
| TATAPOWER | 373.0 | 375 | 0 | 227 | 9.3% |
| TATASTEEL | 373.3 | 375 | 0 | 506 | 20.8% |
| TCS | 373.1 | 375 | 0 | 30 | 1.2% |
| TECHM | 373.3 | 375 | 0 | 43 | 1.8% |
| TIINDIA | 316.0 | 368 | 0 | 1392 | 64.4% |
| TITAN | 373.2 | 375 | 0 | 73 | 3.0% |
| TMPV | 375.0 | 375 | 375 | 0 | 0.0% |
| TORNTPHARM | 365.1 | 375 | 0 | 1163 | 47.8% |
| TRENT | 339.6 | 375 | 0 | 1069 | 44.0% |
| TVSMOTOR | 372.6 | 375 | 0 | 427 | 17.6% |
| ULTRACEMCO | 373.1 | 375 | 0 | 122 | 5.0% |
| UNIONBANK | 373.0 | 375 | 0 | 264 | 10.9% |
| UNITDSPR | 373.7 | 375 | 0 | 34 | 6.4% |
| UNOMINDA | 371.9 | 375 | 0 | 233 | 23.7% |
| UPL | 373.2 | 375 | 0 | 432 | 17.8% |
| VBL | 336.6 | 375 | 0 | 278 | 11.5% |
| VEDL | 373.2 | 375 | 0 | 23 | 0.9% |
| VMM | 374.1 | 375 | 60 | 1 | 0.3% |
| VOLTAS | 372.9 | 375 | 0 | 289 | 11.9% |
| WAAREEENER | 373.4 | 375 | 0 | 2 | 0.5% |
| WIPRO | 373.2 | 375 | 0 | 64 | 2.6% |
| YESBANK | 373.3 | 375 | 0 | 25 | 1.0% |
| ZYDUSLIFE | 373.5 | 375 | 0 | 69 | 6.3% |

### 3c. Vendor APPLICATION FLOORS (QUESTIONS.md Q-11 addendum 2)

The architect's ruling: "the vendor's back-adjustments have per-event APPLICATION FLOORS -- internal splice dates before which the event was never applied to its archive ... for days < F_e the event is ABSENT from that day's chain". Each floor below was BINARY-SEARCHED, not fitted: the search asks the daily oracle, one probed session at a time, whether that day's fetched bars fit the era's chain WITH the event or WITHOUT it, and bisects the boundary. Price containment (2 paise vs the RAW daily high/low) decides; a day that answers neither is `undecided` and an undecided run abandons the search UNRESOLVED rather than guessing. Budget 16 probes per event.

Hunt scope is the ruling's own: every QUARANTINED symbol and every settled symbol below gate-1 98%, plus (Q-11 addendum 4) every symbol carrying a GATE-3 failure, because a symbol can sit above the line while one ex-date of its history is in the wrong price domain -- a correctness question, not a coverage one. Within a symbol an event is searched only when its pre-ex provable-era span actually fails systematically (>= 10% of its days), or -- inside an un-provable era -- only when the signature gate admits it (section 3e). There is no floor to find where nothing fails, and every skip is recorded with its reason.

| Symbol | Gate-1 before the floor pass | Gate-1 after | Floors resolved | Probes | Note |
|---|---|---|---|---|---|
| APLAPOLLO | unchanged | 2363/2431 (97.2%) | 0 | 0 | 0 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| ASTRAL | 1332/2430 (54.8%) | 1699/2430 (69.9%) | 0 | 2 | 2 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| BEL | unchanged | 2173/2431 (89.4%) | 0 | 1 | 1 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| BPCL | unchanged | 2223/2429 (91.5%) | 0 | 2 | 2 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| BSE | unchanged | 2115/2345 (90.2%) | 0 | 1 | 1 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| COCHINSHIP | unchanged | 2198/2215 (99.2%) | 0 | 0 | 0 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| DIXON | 1925/2192 (87.8%) | 2169/2192 (99.0%) | 1 | 11 | 1 floor(s) resolved over 11 probe(s); 257 day(s) rewritten, 1934 already raw; gate 1 1925/2192 (87.8%) -> 2169/2192 (99.0%) |
| GAIL | unchanged | 1990/2431 (81.9%) | 0 | 3 | 3 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| HDFCBANK | unchanged | 2373/2429 (97.7%) | 0 | 0 | 0 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| HINDPETRO | 1766/2429 (72.7%) | 1995/2429 (82.1%) | 1 | 5 | 1 floor(s) resolved over 5 probe(s); 1 era(s) promoted to provable; 238 day(s) rewritten, 1768 already raw; gate 1 1766/2429 (72.7%) -> 1995/2429 (82.1%) |
| IEX | 1149/2169 (53.0%) | 1149/2169 (53.0%) | 1 | 13 | 1 floor(s) resolved over 13 probe(s); 1 era(s) promoted to provable; 0 day(s) rewritten, 1151 already raw; gate 1 1149/2169 (53.0%) -> 1149/2169 (53.0%) |
| INOXWIND | 588/2429 (24.2%) | 2410/2429 (99.2%) | 1 | 13 | 1 floor(s) resolved over 13 probe(s); 0 day(s) rewritten, 539 already raw; gate 1 588/2429 (24.2%) -> 588/2429 (24.2%) |
| IOC | unchanged | 2062/2431 (84.8%) | 0 | 0 | 0 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| JUBLFOOD | 2094/2431 (86.1%) | 2094/2431 (86.1%) | 1 | 13 | 1 floor(s) resolved over 13 probe(s); 0 day(s) rewritten, 2432 already raw; gate 1 2094/2431 (86.1%) -> 2094/2431 (86.1%) |
| LODHA | unchanged | 1303/1307 (99.7%) | 0 | 0 | 0 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| NESTLEIND | 1129/2430 (46.5%) | 1391/2430 (57.2%) | 0 | 0 | 0 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| NMDC | unchanged | 2053/2431 (84.5%) | 0 | 1 | 1 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| NTPC | 1841/2428 (75.8%) | 1841/2428 (75.8%) | 1 | 3 | 1 floor(s) resolved over 3 probe(s); 0 day(s) rewritten, 1847 already raw; gate 1 1841/2428 (75.8%) -> 1841/2428 (75.8%) |
| OIL | unchanged | 2048/2429 (84.3%) | 0 | 2 | 2 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| PETRONET | unchanged | 2234/2431 (91.9%) | 0 | 0 | 0 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| PGEL | unchanged | 2378/2429 (97.9%) | 0 | 0 | 0 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| RELIANCE | 2000/2429 (82.3%) | 2408/2429 (99.1%) | 1 | 13 | 1 floor(s) resolved over 13 probe(s); 0 day(s) rewritten, 2017 already raw; gate 1 2000/2429 (82.3%) -> 2000/2429 (82.3%) |
| TATASTEEL | unchanged | 2087/2431 (85.8%) | 0 | 0 | 0 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| UPL | unchanged | 1750/2430 (72.0%) | 0 | 1 | 1 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| VBL | unchanged | 1270/2407 (52.8%) | 0 | 1 | 1 probe(s) spent; no event carries a vendor application floor inside our history, so the map's chain is unchanged |
| VEDL | 2119/2429 (87.2%) | 2119/2429 (87.2%) | 2 | 6 | 2 floor(s) resolved over 6 probe(s); 13 era(s) promoted to provable; 0 day(s) rewritten, 2129 already raw; gate 1 2119/2429 (87.2%) -> 2119/2429 (87.2%) |

Per-event findings (every event the hunt looked at, including the ones it declined to search and why):

- **APLAPOLLO**
  - 2021-09-16 -> not searched: its pre-ex span reconciles (68/1227 = 5.5% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2020-12-15 -> not searched: its pre-ex span reconciles (67/1041 = 6.4% of days fail gate 1, below the 10% systematic-failure threshold)
- **ASTRAL**
  - 2023-03-14 -> not searched: its pre-ex span reconciles (1/868 = 0.1% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2021-03-18 -> not searched: its pre-ex span reconciles (1/375 = 0.3% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2019-09-16 -> no splice (UNRESOLVED, 2 probe(s)): the oldest probed day (2016-10-03) answers neither hypothesis; no boundary is guessed [admitted by era failure-rate cliff: 729/729 = 100.0% of the gated days below 2019-09-16 fail gate 1 (>= 95%)]
- **BEL**
  - 2022-09-15 -> not searched: its pre-ex span reconciles (11/1229 = 0.9% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2017-09-28 -> era pre-2017-03-16: no hypothesis -- ['2017-03-16'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-09-28 -> no splice (UNRESOLVED, 1 probe(s)): the newest probed day (2017-09-27) is undecided, not event-in: the event is not applied even beside its own ex-date, so there is no floor to find [admitted by era failure-rate cliff: 134/134 = 100.0% of the gated days below 2017-09-28 fail gate 1 (>= 95%)]
  - 2017-03-16 -> era pre-2017-09-28: no hypothesis -- ['2017-09-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-16 -> era pre-2017-03-16: no hypothesis -- ['2017-09-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-16 -> not searched: no day of a provable era carries this event with a factor to drop
- **BPCL**
  - 2026-02-02 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2025-11-07 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-08-09 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-06-21 -> not searched: its pre-ex span reconciles (12/1717 = 0.7% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2023-12-12 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-09-16 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-02-17 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-03-23 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-08-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-02-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2018-02-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2017-07-13 -> era pre-2017-02-28: no hypothesis -- ['2017-02-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-13 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too (2017-02-28): no splice inside our history, the chain is unchanged [admitted by era failure-rate cliff: 92/92 = 100.0% of the gated days below 2017-07-13 fail gate 1 (>= 95%)]
  - 2017-02-28 -> era pre-2017-07-13: no hypothesis -- ['2017-07-13'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-28 -> era pre-2017-02-28: no hypothesis -- ['2017-07-13'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-28 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2016-07-13 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
- **BSE**
  - 2025-05-23 -> not searched: its pre-ex span reconciles (92/1917 = 4.8% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2022-06-23 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-03-21 -> not searched: its pre-ex span reconciles (91/1130 = 8.1% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2020-07-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-06-27 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2018-07-25 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2017-08-24 -> no splice (UNRESOLVED, 1 probe(s)): the newest probed day (2017-08-23) is undecided, not event-in: the event is not applied even beside its own ex-date, so there is no floor to find [admitted by era failure-rate cliff: 137/137 = 100.0% of the gated days below 2017-08-24 fail gate 1 (>= 95%)]
- **COCHINSHIP**
  - 2024-01-10 -> not searched: its pre-ex span reconciles (0/740 = 0.0% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2022-02-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-01-13 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-09-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-08-05 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2018-08-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
- **DIXON**
  - 2021-03-18 -> 2018-10-01 (resolved, 11 probe(s)): vendor application floor 2018-10-01: the event is absent from every chain before it (2018-09-28 probed event-out) and applied from it on
- **GAIL**
  - 2026-02-05 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2025-02-07 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-02-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-03-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-09-06 -> not searched: its pre-ex span reconciles (72/1100 = 6.5% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2022-03-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-12-30 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-02-17 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-08-08 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-07-09 -> no splice (UNRESOLVED, 2 probe(s)): the oldest probed day (2018-03-27) answers neither hypothesis; no boundary is guessed
  - 2018-03-27 -> era pre-2017-03-09: no hypothesis -- ['2017-03-09'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-27 -> no splice (UNRESOLVED, 1 probe(s)): the newest probed day (2018-03-26) is undecided, not event-in: the event is not applied even beside its own ex-date, so there is no floor to find [admitted by era failure-rate cliff: 260/260 = 100.0% of the gated days below 2018-03-27 fail gate 1 (>= 95%)]
  - 2017-03-09 -> era pre-2018-03-27: no hypothesis -- ['2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-09 -> era pre-2017-03-09: no hypothesis -- ['2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-09 -> not searched: no day of a provable era carries this event with a factor to drop
- **HDFCBANK**
  - 2025-08-26 -> not searched: its pre-ex span reconciles (56/2204 = 2.5% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2019-09-19 -> not searched: its pre-ex span reconciles (12/732 = 1.6% of days fail gate 1, below the 10% systematic-failure threshold)
- **HINDPETRO**
  - 2025-08-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-08-09 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-06-21 -> not searched: its pre-ex span reconciles (1/1249 = 0.1% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2024-02-07 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-08-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-07-08 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-07-02 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-06-06 -> era pre-2019-02-14: no hypothesis -- ['2019-02-14'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-06-06 -> era pre-2018-02-28: no hypothesis -- ['2018-02-28', '2019-02-14'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-06-06 -> era pre-2017-07-11: no hypothesis -- ['2017-07-11', '2018-02-28', '2019-02-14'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-06-06 -> era pre-2017-03-01: no hypothesis -- ['2017-03-01', '2017-07-11', '2018-02-28', '2019-02-14'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-06-06 -> 2019-06-06 (resolved, 3 probe(s)): vendor application floor at or above the ex-date 2019-06-06: the event is absent from every chain in our history (3 probed day(s) across 2019-02-14 .. 2019-06-04, all event-out) [admitted by era failure-rate cliff: 73/73 = 100.0% of the gated days below 2019-06-06 fail gate 1 (>= 95%)]
  - 2019-02-14 -> era pre-2019-06-06: no hypothesis -- ['2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-02-14 -> era pre-2019-02-14: no hypothesis -- ['2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-02-14 -> era pre-2018-02-28: no hypothesis -- ['2018-02-28', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-02-14 -> era pre-2017-07-11: no hypothesis -- ['2017-07-11', '2018-02-28', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-02-14 -> era pre-2017-03-01: no hypothesis -- ['2017-03-01', '2017-07-11', '2018-02-28', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-02-14 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2018-02-28 -> era pre-2019-06-06: no hypothesis -- ['2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-28 -> era pre-2019-02-14: no hypothesis -- ['2019-02-14', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-28 -> era pre-2018-02-28: no hypothesis -- ['2019-02-14', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-28 -> era pre-2017-07-11: no hypothesis -- ['2017-07-11', '2019-02-14', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-28 -> era pre-2017-03-01: no hypothesis -- ['2017-03-01', '2017-07-11', '2019-02-14', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-28 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2017-07-11 -> era pre-2019-06-06: no hypothesis -- ['2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-11 -> era pre-2019-02-14: no hypothesis -- ['2019-02-14', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-11 -> era pre-2018-02-28: no hypothesis -- ['2018-02-28', '2019-02-14', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-11 -> era pre-2017-07-11: no hypothesis -- ['2018-02-28', '2019-02-14', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-11 -> era pre-2017-03-01: no hypothesis -- ['2017-03-01', '2018-02-28', '2019-02-14', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-11 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2017-03-01 -> era pre-2019-06-06: no hypothesis -- ['2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-01 -> era pre-2019-02-14: no hypothesis -- ['2019-02-14', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-01 -> era pre-2018-02-28: no hypothesis -- ['2018-02-28', '2019-02-14', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-01 -> era pre-2017-07-11: no hypothesis -- ['2017-07-11', '2018-02-28', '2019-02-14', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-01 -> era pre-2017-03-01: no hypothesis -- ['2017-07-11', '2018-02-28', '2019-02-14', '2019-06-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-01 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2016-09-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2025-08-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2024-08-09 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2024-06-21 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too (2018-02-28): no splice inside our history, the chain is unchanged
  - [round 2] 2024-02-07 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2022-08-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2021-07-08 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2020-07-02 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2019-02-14 -> era pre-2018-02-28: no hypothesis -- ['2018-02-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2019-02-14 -> era pre-2017-07-11: no hypothesis -- ['2017-07-11', '2018-02-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2019-02-14 -> era pre-2017-03-01: no hypothesis -- ['2017-03-01', '2017-07-11', '2018-02-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2019-02-14 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2018-02-28 -> era pre-2018-02-28: no hypothesis -- ['2018-02-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2018-02-28 -> era pre-2017-07-11: no hypothesis -- ['2017-07-11'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2018-02-28 -> era pre-2017-03-01: no hypothesis -- ['2017-03-01', '2017-07-11'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2018-02-28 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2017-07-11 -> era pre-2018-02-28: no hypothesis -- ['2018-02-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2017-07-11 -> era pre-2017-07-11: no hypothesis -- ['2018-02-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2017-07-11 -> era pre-2017-03-01: no hypothesis -- ['2017-03-01', '2018-02-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2017-07-11 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2017-03-01 -> era pre-2018-02-28: no hypothesis -- ['2018-02-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2017-03-01 -> era pre-2017-07-11: no hypothesis -- ['2017-07-11', '2018-02-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2017-03-01 -> era pre-2017-03-01: no hypothesis -- ['2017-07-11', '2018-02-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2017-03-01 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2016-09-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
- **IEX**
  - 2021-12-03 -> era pre-2018-10-19: no hypothesis -- ['2018-10-19'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-03 -> 2019-10-01 (resolved, 11 probe(s)): vendor application floor 2019-10-01: the event is absent from every chain before it (2019-09-30 probed event-out) and applied from it on [admitted by era failure-rate cliff: 773/773 = 100.0% of the gated days below 2021-12-03 fail gate 1 (>= 95%)]
  - 2018-10-19 -> era pre-2021-12-03: no hypothesis -- ['2021-12-03'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-10-19 -> era pre-2018-10-19: no hypothesis -- ['2021-12-03'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-10-19 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2018-10-19 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too (2017-10-23): no splice inside our history, the chain is unchanged
- **INOXWIND**
  - 2025-07-29 -> not searched: its pre-ex span reconciles (2/294 = 0.7% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2024-05-24 -> 2022-05-19 (resolved, 13 probe(s)): vendor application floor 2022-05-19: the event is absent from every chain before it (2022-05-18 probed event-out) and applied from it on [admitted by gate-3 raw-gap-near-zero: |raw gap| 10.98% is nearer 0 than the event's own step 75.00% (k=0.25), adjusted gap 343.91% -- both closes are already in the same price domain AND era failure-rate cliff: 1839/1891 = 97.3% of the gated days below 2024-05-24 fail gate 1 (>= 95%)]
- **IOC**
  - 2025-12-18 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2025-08-08 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-07-12 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-11-10 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-07-28 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-08-11 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-06-30 -> era pre-2023-11-10: no hypothesis -- ['2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-30 -> era pre-2023-07-28: no hypothesis -- ['2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-30 -> era pre-2022-08-11: no hypothesis -- ['2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-30 -> era pre-2022-06-30: no hypothesis -- ['2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-30 -> era pre-2022-02-09: no hypothesis -- ['2022-02-09', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-30 -> era pre-2021-11-11: no hypothesis -- ['2021-11-11', '2022-02-09', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-30 -> era pre-2021-03-23: no hypothesis -- ['2021-03-23', '2021-11-11', '2022-02-09', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-30 -> era pre-2021-02-09: no hypothesis -- ['2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-30 -> era pre-2020-03-23: no hypothesis -- ['2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-30 -> era pre-2018-12-21: no hypothesis -- ['2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-30 -> era pre-2018-03-15: no hypothesis -- ['2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-30 -> era pre-2018-02-08: no hypothesis -- ['2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-30 -> era pre-2017-02-09: no hypothesis -- ['2017-02-09', '2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-30 -> era pre-2016-10-18: no hypothesis -- ['2016-10-18', '2017-02-09', '2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-30 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2022-02-09 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-11-11 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-03-23 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-02-09 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-03-23 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2018-12-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2018-03-15 -> era pre-2023-11-10: no hypothesis -- ['2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-15 -> era pre-2023-07-28: no hypothesis -- ['2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-15 -> era pre-2022-08-11: no hypothesis -- ['2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-15 -> era pre-2022-06-30: no hypothesis -- ['2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-15 -> era pre-2022-02-09: no hypothesis -- ['2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-15 -> era pre-2021-11-11: no hypothesis -- ['2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-15 -> era pre-2021-03-23: no hypothesis -- ['2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-15 -> era pre-2021-02-09: no hypothesis -- ['2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-15 -> era pre-2020-03-23: no hypothesis -- ['2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-15 -> era pre-2018-12-21: no hypothesis -- ['2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-15 -> era pre-2018-03-15: no hypothesis -- ['2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-15 -> era pre-2018-02-08: no hypothesis -- ['2018-02-08', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-15 -> era pre-2017-02-09: no hypothesis -- ['2017-02-09', '2018-02-08', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-15 -> era pre-2016-10-18: no hypothesis -- ['2016-10-18', '2017-02-09', '2018-02-08', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-15 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2018-02-08 -> era pre-2023-11-10: no hypothesis -- ['2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-08 -> era pre-2023-07-28: no hypothesis -- ['2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-08 -> era pre-2022-08-11: no hypothesis -- ['2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-08 -> era pre-2022-06-30: no hypothesis -- ['2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-08 -> era pre-2022-02-09: no hypothesis -- ['2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-08 -> era pre-2021-11-11: no hypothesis -- ['2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-08 -> era pre-2021-03-23: no hypothesis -- ['2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-08 -> era pre-2021-02-09: no hypothesis -- ['2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-08 -> era pre-2020-03-23: no hypothesis -- ['2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-08 -> era pre-2018-12-21: no hypothesis -- ['2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-08 -> era pre-2018-03-15: no hypothesis -- ['2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-08 -> era pre-2018-02-08: no hypothesis -- ['2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-08 -> era pre-2017-02-09: no hypothesis -- ['2017-02-09', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-08 -> era pre-2016-10-18: no hypothesis -- ['2016-10-18', '2017-02-09', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-08 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2017-02-09 -> era pre-2023-11-10: no hypothesis -- ['2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-09 -> era pre-2023-07-28: no hypothesis -- ['2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-09 -> era pre-2022-08-11: no hypothesis -- ['2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-09 -> era pre-2022-06-30: no hypothesis -- ['2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-09 -> era pre-2022-02-09: no hypothesis -- ['2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-09 -> era pre-2021-11-11: no hypothesis -- ['2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-09 -> era pre-2021-03-23: no hypothesis -- ['2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-09 -> era pre-2021-02-09: no hypothesis -- ['2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-09 -> era pre-2020-03-23: no hypothesis -- ['2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-09 -> era pre-2018-12-21: no hypothesis -- ['2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-09 -> era pre-2018-03-15: no hypothesis -- ['2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-09 -> era pre-2018-02-08: no hypothesis -- ['2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-09 -> era pre-2017-02-09: no hypothesis -- ['2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-09 -> era pre-2016-10-18: no hypothesis -- ['2016-10-18', '2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-09 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2016-10-18 -> era pre-2023-11-10: no hypothesis -- ['2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2016-10-18 -> era pre-2023-07-28: no hypothesis -- ['2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2016-10-18 -> era pre-2022-08-11: no hypothesis -- ['2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2016-10-18 -> era pre-2022-06-30: no hypothesis -- ['2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2016-10-18 -> era pre-2022-02-09: no hypothesis -- ['2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2016-10-18 -> era pre-2021-11-11: no hypothesis -- ['2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2016-10-18 -> era pre-2021-03-23: no hypothesis -- ['2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2016-10-18 -> era pre-2021-02-09: no hypothesis -- ['2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2016-10-18 -> era pre-2020-03-23: no hypothesis -- ['2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2016-10-18 -> era pre-2018-12-21: no hypothesis -- ['2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2016-10-18 -> era pre-2018-03-15: no hypothesis -- ['2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2016-10-18 -> era pre-2018-02-08: no hypothesis -- ['2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2016-10-18 -> era pre-2017-02-09: no hypothesis -- ['2017-02-09', '2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2016-10-18 -> era pre-2016-10-18: no hypothesis -- ['2017-02-09', '2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2016-10-18 -> not searched: no day of a provable era carries this event with a factor to drop
- **JUBLFOOD**
  - 2022-04-19 -> 2018-01-18 (resolved, 12 probe(s)): vendor application floor 2018-01-18: the event is absent from every chain before it (2018-01-17 probed event-out) and applied from it on
  - 2018-06-21 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too (2016-10-03): no splice inside our history, the chain is unchanged
- **LODHA**
  - 2023-05-31 -> not searched: its pre-ex span reconciles (25/525 = 4.8% of days fail gate 1, below the 10% systematic-failure threshold)
- **NESTLEIND**
  - 2025-08-08 -> not searched: its pre-ex span reconciles (30/1185 = 2.5% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2024-01-05 -> not searched: its pre-ex span reconciles (29/789 = 3.7% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2020-10-29 -> era pre-2020-10-29: no hypothesis -- ['2020-10-29'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-29 -> not searched: no day of a provable era carries this event with a factor to drop
- **NMDC**
  - 2026-02-13 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2025-03-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-12-27 -> not searched: its pre-ex span reconciles (9/1673 = 0.5% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2024-02-27 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-08-31 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-02-24 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-10-27 -> not searched: its pre-ex span reconciles (8/1135 = 0.7% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2022-02-17 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-12-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-03-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-02-18 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-03-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2018-03-27 -> era pre-2017-03-16: no hypothesis -- ['2017-03-16'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-27 -> no splice (UNRESOLVED, 1 probe(s)): the newest probed day (2018-03-26) is undecided, not event-in: the event is not applied even beside its own ex-date, so there is no floor to find [admitted by era failure-rate cliff: 256/256 = 100.0% of the gated days below 2018-03-27 fail gate 1 (>= 95%)]
  - 2017-03-16 -> era pre-2018-03-27: no hypothesis -- ['2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-16 -> era pre-2017-03-16: no hypothesis -- ['2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-16 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2016-02-24 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
- **NTPC**
  - 2023-02-03 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-02-03 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-09-08 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-02-11 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-08-13 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-08-13 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-03-19 -> not searched: its pre-ex span reconciles (2/28 = 7.1% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2019-02-06 -> 2019-02-06 (resolved, 3 probe(s)): vendor application floor at or above the ex-date 2019-02-06: the event is absent from every chain in our history (3 probed day(s) across 2016-10-03 .. 2019-02-05, all event-out) [admitted by era failure-rate cliff: 582/582 = 100.0% of the gated days below 2019-02-06 fail gate 1 (>= 95%)]
- **OIL**
  - 2024-07-02 -> not searched: its pre-ex span reconciles (12/1549 = 0.8% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2023-02-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-11-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-09-15 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-02-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-02-23 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-02-20 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-02-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2018-03-27 -> era pre-2018-02-21: no hypothesis -- ['2018-02-21'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-27 -> era pre-2017-02-13: no hypothesis -- ['2017-02-13', '2018-02-21'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-27 -> era pre-2017-01-12: no hypothesis -- ['2017-01-12', '2017-02-13', '2018-02-21'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-27 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too (2018-02-21): no splice inside our history, the chain is unchanged [admitted by era failure-rate cliff: 23/23 = 100.0% of the gated days below 2018-03-27 fail gate 1 (>= 95%)]
  - 2018-02-21 -> era pre-2018-03-27: no hypothesis -- ['2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-21 -> era pre-2018-02-21: no hypothesis -- ['2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-21 -> era pre-2017-02-13: no hypothesis -- ['2017-02-13', '2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-21 -> era pre-2017-01-12: no hypothesis -- ['2017-01-12', '2017-02-13', '2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-02-21 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2017-02-13 -> era pre-2018-03-27: no hypothesis -- ['2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-13 -> era pre-2018-02-21: no hypothesis -- ['2018-02-21', '2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-13 -> era pre-2017-02-13: no hypothesis -- ['2018-02-21', '2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-13 -> era pre-2017-01-12: no hypothesis -- ['2017-01-12', '2018-02-21', '2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-13 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2017-01-12 -> era pre-2018-03-27: no hypothesis -- ['2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-01-12 -> era pre-2018-02-21: no hypothesis -- ['2018-02-21', '2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-01-12 -> era pre-2017-02-13: no hypothesis -- ['2017-02-13', '2018-02-21', '2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-01-12 -> era pre-2017-01-12: no hypothesis -- ['2017-02-13', '2018-02-21', '2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-01-12 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2016-09-15 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2016-01-19 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
- **PETRONET**
  - 2025-11-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-11-08 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-11-10 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-11-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-07-04 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-11-17 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-11-23 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-07-15 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2018-11-15 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2017-07-03 -> era pre-2023-11-10: no hypothesis -- ['2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-03 -> era pre-2022-11-21: no hypothesis -- ['2022-11-21', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-03 -> era pre-2022-07-04: no hypothesis -- ['2022-07-04', '2022-11-21', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-03 -> era pre-2021-11-17: no hypothesis -- ['2021-11-17', '2022-07-04', '2022-11-21', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-03 -> era pre-2020-11-23: no hypothesis -- ['2020-11-23', '2021-11-17', '2022-07-04', '2022-11-21', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-03 -> era pre-2020-07-15: no hypothesis -- ['2020-07-15', '2020-11-23', '2021-11-17', '2022-07-04', '2022-11-21', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-03 -> era pre-2018-11-15: no hypothesis -- ['2018-11-15', '2020-07-15', '2020-11-23', '2021-11-17', '2022-07-04', '2022-11-21', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-03 -> era pre-2017-07-03: no hypothesis -- ['2018-11-15', '2020-07-15', '2020-11-23', '2021-11-17', '2022-07-04', '2022-11-21', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-03 -> not searched: no day of a provable era carries this event with a factor to drop
- **PGEL**
  - 2024-07-10 -> not searched: its pre-ex span reconciles (50/1923 = 2.6% of days fail gate 1, below the 10% systematic-failure threshold)
- **RELIANCE**
  - 2024-10-28 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too (2016-10-03): no splice inside our history, the chain is unchanged
  - 2023-07-20 -> 2022-01-05 (resolved, 11 probe(s)): vendor application floor 2022-01-05: the event is absent from every chain before it (2022-01-04 probed event-out) and applied from it on
  - 2020-05-13 -> not searched: its pre-ex span reconciles (11/890 = 1.2% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2017-09-07 -> not searched: its pre-ex span reconciles (0/231 = 0.0% of days fail gate 1, below the 10% systematic-failure threshold)
- **TATASTEEL**
  - 2026-06-12 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2025-06-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-06-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-07-28 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-06-15 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-06-17 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-08-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-07-04 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2018-01-31 -> era pre-2022-07-28: no hypothesis -- ['2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-01-31 -> era pre-2022-06-15: no hypothesis -- ['2022-06-15', '2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-01-31 -> era pre-2021-06-17: no hypothesis -- ['2021-06-17', '2022-06-15', '2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-01-31 -> era pre-2020-08-06: no hypothesis -- ['2020-08-06', '2021-06-17', '2022-06-15', '2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-01-31 -> era pre-2019-07-04: no hypothesis -- ['2019-07-04', '2020-08-06', '2021-06-17', '2022-06-15', '2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-01-31 -> era pre-2018-01-31: no hypothesis -- ['2019-07-04', '2020-08-06', '2021-06-17', '2022-06-15', '2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-01-31 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2016-07-28 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
- **UPL**
  - 2024-11-26 -> not searched: its pre-ex span reconciles (1/1339 = 0.1% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2019-07-02 -> no splice (UNRESOLVED, 1 probe(s)): the newest probed day (2019-07-01) is undecided, not event-in: the event is not applied even beside its own ex-date, so there is no floor to find [admitted by gate-3 raw-gap-near-zero: |raw gap| 8.62% is nearer 0 than the event's own step 33.33% (k=0.6666666666666666666666666667), adjusted gap 62.94% -- both closes are already in the same price domain AND era failure-rate cliff: 679/679 = 100.0% of the gated days below 2019-07-02 fail gate 1 (>= 95%)]
- **VBL**
  - 2024-09-12 -> not searched: its pre-ex span reconciles (1/809 = 0.1% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2023-06-15 -> not searched: its pre-ex span reconciles (0/500 = 0.0% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2022-06-06 -> not searched: its pre-ex span reconciles (0/245 = 0.0% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2021-06-10 -> era pre-2019-07-25: no hypothesis -- ['2019-07-25'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-06-10 -> no splice (UNRESOLVED, 1 probe(s)): the newest probed day (2021-06-09) is undecided, not event-in: the event is not applied even beside its own ex-date, so there is no floor to find [admitted by era failure-rate cliff: 464/464 = 100.0% of the gated days below 2021-06-10 fail gate 1 (>= 95%)]
  - 2019-07-25 -> era pre-2021-06-10: no hypothesis -- ['2021-06-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-07-25 -> era pre-2019-07-25: no hypothesis -- ['2021-06-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-07-25 -> not searched: no day of a provable era carries this event with a factor to drop
- **VEDL**
  - 2026-04-30 -> not searched: its pre-ex span reconciles (1/575 = 0.2% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2025-08-26 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-09-10 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-05-24 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-12-27 -> era pre-2023-05-30: no hypothesis -- ['2023-05-30'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-12-27 -> era pre-2023-04-06: no hypothesis -- ['2023-04-06', '2023-05-30'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-12-27 -> era pre-2023-02-03: no hypothesis -- ['2023-02-03', '2023-04-06', '2023-05-30'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-12-27 -> era pre-2022-11-29: no hypothesis -- ['2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-12-27 -> era pre-2022-07-26: no hypothesis -- ['2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-12-27 -> era pre-2022-05-06: no hypothesis -- ['2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-12-27 -> era pre-2022-03-09: no hypothesis -- ['2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-12-27 -> era pre-2021-12-17: no hypothesis -- ['2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-12-27 -> era pre-2021-09-08: no hypothesis -- ['2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-12-27 -> era pre-2020-10-28: no hypothesis -- ['2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-12-27 -> era pre-2020-03-05: no hypothesis -- ['2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-12-27 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-12-27 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-12-27 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-12-27 -> 2023-12-27 (resolved, 3 probe(s)): vendor application floor at or above the ex-date 2023-12-27: the event is absent from every chain in our history (3 probed day(s) across 2023-05-30 .. 2023-12-26, all event-out) [admitted by era failure-rate cliff: 144/144 = 100.0% of the gated days below 2023-12-27 fail gate 1 (>= 95%)]
  - 2023-05-30 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-04-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-02-03 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-11-29 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-07-26 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-05-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-03-09 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-12-17 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-09-08 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-10-28 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-03-05 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2018-11-06 -> era pre-2023-12-27: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> era pre-2023-05-30: no hypothesis -- ['2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> era pre-2023-04-06: no hypothesis -- ['2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> era pre-2023-02-03: no hypothesis -- ['2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> era pre-2022-11-29: no hypothesis -- ['2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> era pre-2022-07-26: no hypothesis -- ['2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> era pre-2022-05-06: no hypothesis -- ['2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> era pre-2022-03-09: no hypothesis -- ['2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> era pre-2021-12-17: no hypothesis -- ['2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> era pre-2021-09-08: no hypothesis -- ['2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> era pre-2020-10-28: no hypothesis -- ['2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> era pre-2020-03-05: no hypothesis -- ['2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> era pre-2018-11-06: no hypothesis -- ['2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-11-06 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2018-03-20 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2017-04-11 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2026-04-30 -> not searched: its pre-ex span reconciles (8/1699 = 0.5% of days fail gate 1, below the 10% systematic-failure threshold)
  - [round 2] 2025-08-26 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2024-09-10 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2024-05-24 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2023-05-30 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2023-04-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2023-02-03 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2022-11-29 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2022-07-26 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2022-05-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2022-03-09 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2021-12-17 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2021-09-08 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2020-10-28 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2020-03-05 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2018-11-06 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2018-11-06 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2018-11-06 -> 2018-11-06 (resolved, 3 probe(s)): vendor application floor at or above the ex-date 2018-11-06: the event is absent from every chain in our history (3 probed day(s) across 2018-03-20 .. 2018-11-05, all event-out) [admitted by era failure-rate cliff: 156/156 = 100.0% of the gated days below 2018-11-06 fail gate 1 (>= 95%)]
  - [round 2] 2018-03-20 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2017-04-11 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2026-04-30 -> not searched: its pre-ex span reconciles (10/2061 = 0.5% of days fail gate 1, below the 10% systematic-failure threshold)
  - [round 3] 2025-08-26 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2024-09-10 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2024-05-24 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2023-05-30 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2023-04-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2023-02-03 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2022-11-29 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2022-07-26 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2022-05-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2022-03-09 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2021-12-17 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2021-09-08 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2020-10-28 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2020-03-05 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2018-03-20 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2017-04-11 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)

### 3d. AUCTION RELIEF -- the deferred +5.0% ceiling, answered (QUESTIONS.md Q-12 addendum 2)

The architect's ruling: **"the ceiling stays"**. `VOLUME_GAP_MIN_PCT` and `VOLUME_GAP_MAX_PCT` are byte-identical (`[-0.1%, 5.0%]`) and `volume_gate` is untouched. A gate-1 failure ABOVE the ceiling is separately examined and relieved **IFF ALL FOUR** hold: (a) the failure is above the ceiling, never below the floor; (b) the stored 1-min HIGH equals the raw daily HIGH and the 1-min LOW the raw daily LOW, EXACTLY; (c) the first stamp's open equals the raw daily open, exactly; (d) the shortfall is <= 20.0%. Data LOSS clips extremes; a day with intact extremes, a matching opening print and only volume short is a thin day whose pre-open auction exceeds 5% -- a market property.

**435 symbol-day(s) relieved** across 125 symbol(s), out of 420,297 gated days on settled symbols. Relieved days are counted SEPARATELY everywhere in this report -- the strict gate-1 numerator is never overwritten.

| Symbol | Gate-1 strict | Auction-relief pass | Effective | Median shortfall | Relieved days also carrying tradeless minutes | Status |
|---|---|---|---|---|---|---|
| HDFCBANK | 2330/2429 (95.9%) | 43 | 2373/2429 (97.7%) | 6.40% | 1 | settled |
| APLAPOLLO | 2343/2431 (96.4%) | 20 | 2363/2431 (97.2%) | 6.15% | 19 | settled |
| PGEL | 2360/2429 (97.2%) | 18 | 2378/2429 (97.9%) | 8.62% | 17 | settled |
| OBEROIRLTY | 2394/2429 (98.6%) | 17 | 2411/2429 (99.3%) | 7.40% | 4 | settled |
| SUZLON | 2377/2428 (97.9%) | 15 | 2392/2428 (98.5%) | 7.22% | 0 | settled |
| ADANIENT | 2400/2429 (98.8%) | 13 | 2413/2429 (99.3%) | 6.61% | 0 | settled |
| TATAPOWER | 2402/2429 (98.9%) | 13 | 2415/2429 (99.4%) | 7.11% | 0 | settled |
| SAIL | 2400/2429 (98.8%) | 12 | 2412/2429 (99.3%) | 8.50% | 0 | settled |
| ICICIBANK | 2396/2429 (98.6%) | 9 | 2405/2429 (99.0%) | 5.97% | 1 | settled |
| PAYTM | 1140/1161 (98.2%) | 9 | 1149/1161 (99.0%) | 12.26% | 0 | settled |
| ADANIPOWER | 2401/2429 (98.8%) | 8 | 2409/2429 (99.2%) | 6.45% | 1 | settled |
| BHARTIARTL | 2402/2429 (98.9%) | 8 | 2410/2429 (99.2%) | 5.88% | 0 | settled |
| FORCEMOT | 1614/1642 (98.3%) | 8 | 1622/1642 (98.8%) | 8.16% | 8 | settled |
| DLF | 2406/2429 (99.1%) | 7 | 2413/2429 (99.3%) | 5.73% | 0 | settled |
| PATANJALI | 834/853 (97.8%) | 7 | 841/853 (98.6%) | 6.89% | 0 | settled |
| IREDA | 643/658 (97.7%) | 6 | 649/658 (98.6%) | 11.40% | 0 | settled |
| INOXWIND | 2405/2429 (99.0%) | 5 | 2410/2429 (99.2%) | 9.53% | 3 | settled |
| JSWENERGY | 2406/2429 (99.1%) | 5 | 2411/2429 (99.3%) | 8.70% | 2 | settled |
| MANAPPURAM | 2413/2430 (99.3%) | 5 | 2418/2430 (99.5%) | 6.27% | 0 | settled |
| NHPC | 2410/2428 (99.3%) | 5 | 2415/2428 (99.5%) | 5.87% | 0 | settled |
| SOLARINDS | 2409/2429 (99.2%) | 5 | 2414/2429 (99.4%) | 8.29% | 4 | settled |
| TIINDIA | 2137/2160 (98.9%) | 5 | 2142/2160 (99.2%) | 6.73% | 5 | settled |
| CGPOWER | 2302/2321 (99.2%) | 4 | 2306/2321 (99.4%) | 7.22% | 2 | settled |
| KEI | 2409/2428 (99.2%) | 4 | 2413/2428 (99.4%) | 9.15% | 0 | settled |
| LAURUSLABS | 2358/2376 (99.2%) | 4 | 2362/2376 (99.4%) | 6.74% | 2 | settled |
| M&M | 2410/2429 (99.2%) | 4 | 2414/2429 (99.4%) | 6.55% | 0 | settled |
| NMDC | 2049/2431 (84.3%) | 4 | 2053/2431 (84.5%) | 13.16% | 0 | settled |
| POWERGRID | 2414/2430 (99.3%) | 4 | 2418/2430 (99.5%) | 7.36% | 0 | settled |
| RELIANCE | 2404/2429 (99.0%) | 4 | 2408/2429 (99.1%) | 6.70% | 0 | settled |
| TCS | 2405/2429 (99.0%) | 4 | 2409/2429 (99.2%) | 11.84% | 0 | settled |
| 360ONE | 858/867 (99.0%) | 3 | 861/867 (99.3%) | 8.08% | 0 | settled |
| AXISBANK | 2410/2428 (99.3%) | 3 | 2413/2428 (99.4%) | 5.19% | 0 | settled |
| BRITANNIA | 2411/2429 (99.3%) | 3 | 2414/2429 (99.4%) | 7.74% | 0 | settled |
| DABUR | 2413/2429 (99.3%) | 3 | 2416/2429 (99.5%) | 12.00% | 0 | settled |
| EICHERMOT | 2409/2428 (99.2%) | 3 | 2412/2428 (99.3%) | 5.82% | 0 | settled |
| FORTIS | 2410/2429 (99.2%) | 3 | 2413/2429 (99.3%) | 7.33% | 1 | settled |
| GVT&D | 414/425 (97.4%) | 3 | 417/425 (98.1%) | 7.49% | 1 | settled |
| HDFCLIFE | 2132/2149 (99.2%) | 3 | 2135/2149 (99.3%) | 5.32% | 0 | settled |
| IDEA | 2406/2429 (99.1%) | 3 | 2409/2429 (99.2%) | 9.93% | 0 | settled |
| INFY | 2410/2430 (99.2%) | 3 | 2413/2430 (99.3%) | 5.47% | 0 | settled |
| KOTAKBANK | 2410/2429 (99.2%) | 3 | 2413/2429 (99.3%) | 6.62% | 0 | settled |
| MOTILALOFS | 2406/2429 (99.1%) | 3 | 2409/2429 (99.2%) | 10.96% | 0 | settled |
| NAUKRI | 2410/2429 (99.2%) | 3 | 2413/2429 (99.3%) | 11.58% | 2 | settled |
| NBCC | 2412/2429 (99.3%) | 3 | 2415/2429 (99.4%) | 9.75% | 0 | settled |
| NYKAA | 1163/1167 (99.7%) | 3 | 1166/1167 (99.9%) | 6.26% | 0 | settled |
| PNBHOUSING | 2389/2408 (99.2%) | 3 | 2392/2408 (99.3%) | 6.52% | 1 | settled |
| PREMIERENE | 466/469 (99.4%) | 3 | 469/469 (100.0%) | 6.97% | 1 | settled |
| ABB | 2414/2429 (99.4%) | 2 | 2416/2429 (99.5%) | 6.09% | 1 | settled |
| ADANIGREEN | 1990/2005 (99.3%) | 2 | 1992/2005 (99.4%) | 5.99% | 1 | settled |
| BAJFINANCE | 2410/2429 (99.2%) | 2 | 2412/2429 (99.3%) | 11.27% | 0 | settled |
| BANDHANBNK | 2046/2061 (99.3%) | 2 | 2048/2061 (99.4%) | 5.30% | 0 | settled |
| CDSL | 2228/2244 (99.3%) | 2 | 2230/2244 (99.4%) | 11.99% | 0 | settled |
| CHOLAFIN | 2413/2429 (99.3%) | 2 | 2415/2429 (99.4%) | 5.78% | 0 | settled |
| CIPLA | 2414/2429 (99.4%) | 2 | 2416/2429 (99.5%) | 8.96% | 0 | settled |
| CROMPTON | 2413/2429 (99.3%) | 2 | 2415/2429 (99.4%) | 7.46% | 0 | settled |
| CUMMINSIND | 2413/2429 (99.3%) | 2 | 2415/2429 (99.4%) | 15.57% | 0 | settled |
| DMART | 2296/2313 (99.3%) | 2 | 2298/2313 (99.4%) | 14.88% | 0 | settled |
| GLENMARK | 2414/2429 (99.4%) | 2 | 2416/2429 (99.5%) | 6.82% | 0 | settled |
| GODREJCP | 2410/2429 (99.2%) | 2 | 2412/2429 (99.3%) | 10.97% | 0 | settled |
| GRASIM | 2413/2429 (99.3%) | 2 | 2415/2429 (99.4%) | 9.99% | 0 | settled |
| ICICIPRULI | 2412/2429 (99.3%) | 2 | 2414/2429 (99.4%) | 9.58% | 0 | settled |
| INDHOTEL | 2414/2429 (99.4%) | 2 | 2416/2429 (99.5%) | 12.97% | 0 | settled |
| INDIGO | 2408/2429 (99.1%) | 2 | 2410/2429 (99.2%) | 7.57% | 0 | settled |
| INDUSINDBK | 2412/2429 (99.3%) | 2 | 2414/2429 (99.4%) | 7.17% | 0 | settled |
| JIOFIN | 717/723 (99.2%) | 2 | 719/723 (99.4%) | 12.35% | 0 | settled |
| LODHA | 1301/1307 (99.5%) | 2 | 1303/1307 (99.7%) | 7.72% | 1 | settled |
| MAXHEALTH | 1461/1468 (99.5%) | 2 | 1463/1468 (99.7%) | 6.11% | 0 | settled |
| MCX | 2413/2429 (99.3%) | 2 | 2415/2429 (99.4%) | 5.59% | 0 | settled |
| MFSL | 2413/2429 (99.3%) | 2 | 2415/2429 (99.4%) | 8.33% | 1 | settled |
| PETRONET | 2232/2431 (91.8%) | 2 | 2234/2431 (91.9%) | 6.80% | 0 | settled |
| PHOENIXLTD | 2407/2429 (99.1%) | 2 | 2409/2429 (99.2%) | 15.24% | 2 | settled |
| PIDILITIND | 2415/2431 (99.3%) | 2 | 2417/2431 (99.4%) | 6.01% | 0 | settled |
| POLYCAB | 1789/1798 (99.5%) | 2 | 1791/1798 (99.6%) | 5.30% | 0 | settled |
| POWERINDIA | 1554/1566 (99.2%) | 2 | 1556/1566 (99.4%) | 7.77% | 2 | settled |
| SBICARD | 1570/1576 (99.6%) | 2 | 1572/1576 (99.7%) | 10.65% | 0 | settled |
| SUNPHARMA | 2413/2429 (99.3%) | 2 | 2415/2429 (99.4%) | 6.08% | 0 | settled |
| TATACONSUM | 1582/1587 (99.7%) | 2 | 1584/1587 (99.8%) | 12.09% | 0 | settled |
| ULTRACEMCO | 2414/2429 (99.4%) | 2 | 2416/2429 (99.5%) | 10.32% | 0 | settled |
| ADANIENSOL | 721/723 (99.7%) | 1 | 722/723 (99.9%) | 7.07% | 0 | settled |
| ADANIPORTS | 2410/2429 (99.2%) | 1 | 2411/2429 (99.3%) | 5.02% | 0 | settled |
| AMBER | 2082/2099 (99.2%) | 1 | 2083/2099 (99.2%) | 5.77% | 1 | settled |
| AMBUJACEM | 2413/2428 (99.4%) | 1 | 2414/2428 (99.4%) | 6.89% | 0 | settled |
| APOLLOHOSP | 2415/2429 (99.4%) | 1 | 2416/2429 (99.5%) | 7.71% | 0 | settled |
| ASIANPAINT | 2417/2430 (99.5%) | 1 | 2418/2430 (99.5%) | 6.16% | 0 | settled |
| ASTRAL | 1698/2430 (69.9%) | 1 | 1699/2430 (69.9%) | 14.26% | 0 | quarantined |
| BAJAJHLDNG | 2406/2429 (99.1%) | 1 | 2407/2429 (99.1%) | 9.93% | 1 | settled |
| BANKINDIA | 2414/2429 (99.4%) | 1 | 2415/2429 (99.4%) | 6.39% | 0 | settled |
| BLUESTARCO | 2409/2429 (99.2%) | 1 | 2410/2429 (99.2%) | 5.96% | 1 | settled |
| COALINDIA | 2415/2429 (99.4%) | 1 | 2416/2429 (99.5%) | 6.98% | 0 | settled |
| COCHINSHIP | 2197/2215 (99.2%) | 1 | 2198/2215 (99.2%) | 12.72% | 0 | settled |
| COFORGE | 1463/1469 (99.6%) | 1 | 1464/1469 (99.7%) | 6.35% | 0 | settled |
| COLPAL | 2413/2429 (99.3%) | 1 | 2414/2429 (99.4%) | 17.48% | 0 | settled |
| CONCOR | 2416/2429 (99.5%) | 1 | 2417/2429 (99.5%) | 19.07% | 0 | settled |
| FEDERALBNK | 2415/2429 (99.4%) | 1 | 2416/2429 (99.5%) | 8.10% | 0 | settled |
| GODFRYPHLP | 2413/2429 (99.3%) | 1 | 2414/2429 (99.4%) | 6.24% | 0 | settled |
| GODREJPROP | 2411/2429 (99.3%) | 1 | 2412/2429 (99.3%) | 5.58% | 0 | settled |
| HAL | 2047/2060 (99.4%) | 1 | 2048/2060 (99.4%) | 8.22% | 1 | settled |
| HCLTECH | 2412/2429 (99.3%) | 1 | 2413/2429 (99.3%) | 6.95% | 0 | settled |
| HEROMOTOCO | 2413/2429 (99.3%) | 1 | 2414/2429 (99.4%) | 13.14% | 0 | settled |
| HINDZINC | 2413/2429 (99.3%) | 1 | 2414/2429 (99.4%) | 5.95% | 0 | settled |
| HYUNDAI | 433/435 (99.5%) | 1 | 434/435 (99.8%) | 15.33% | 1 | settled |
| ICICIGI | 2166/2183 (99.2%) | 1 | 2167/2183 (99.3%) | 8.75% | 0 | settled |
| IEX | 1148/2169 (52.9%) | 1 | 1149/2169 (53.0%) | 7.41% | 0 | quarantined |
| ITC | 2411/2428 (99.3%) | 1 | 2412/2428 (99.3%) | 5.00% | 0 | settled |
| JUBLFOOD | 2093/2431 (86.1%) | 1 | 2094/2431 (86.1%) | 14.40% | 0 | settled |
| KAYNES | 908/911 (99.7%) | 1 | 909/911 (99.8%) | 14.54% | 0 | settled |
| KPITTECH | 1794/1798 (99.8%) | 1 | 1795/1798 (99.8%) | 6.45% | 1 | settled |
| LUPIN | 2413/2428 (99.4%) | 1 | 2414/2428 (99.4%) | 7.88% | 0 | settled |
| MPHASIS | 2413/2429 (99.3%) | 1 | 2414/2429 (99.4%) | 8.56% | 0 | settled |
| MUTHOOTFIN | 2412/2428 (99.3%) | 1 | 2413/2428 (99.4%) | 15.46% | 1 | settled |
| NATIONALUM | 2414/2429 (99.4%) | 1 | 2415/2429 (99.4%) | 5.48% | 0 | settled |
| NTPC | 1840/2428 (75.8%) | 1 | 1841/2428 (75.8%) | 5.62% | 1 | quarantined |
| NUVAMA | 679/690 (98.4%) | 1 | 680/690 (98.6%) | 5.68% | 0 | settled |
| OFSS | 2412/2429 (99.3%) | 1 | 2413/2429 (99.3%) | 5.27% | 0 | settled |
| PAGEIND | 2402/2429 (98.9%) | 1 | 2403/2429 (98.9%) | 10.91% | 1 | settled |
| PIIND | 2413/2429 (99.3%) | 1 | 2414/2429 (99.4%) | 5.19% | 1 | settled |
| PNB | 2415/2429 (99.4%) | 1 | 2416/2429 (99.5%) | 5.95% | 0 | settled |
| POLICYBZR | 1158/1163 (99.6%) | 1 | 1159/1163 (99.7%) | 6.67% | 0 | settled |
| RBLBANK | 2414/2429 (99.4%) | 1 | 2415/2429 (99.4%) | 5.81% | 0 | settled |
| SHRIRAMFIN | 888/891 (99.7%) | 1 | 889/891 (99.8%) | 9.40% | 0 | settled |
| SRF | 2418/2431 (99.5%) | 1 | 2419/2431 (99.5%) | 5.30% | 0 | settled |
| SWIGGY | 418/419 (99.8%) | 1 | 419/419 (100.0%) | 15.11% | 1 | settled |
| TORNTPHARM | 2425/2431 (99.8%) | 1 | 2426/2431 (99.8%) | 13.46% | 0 | settled |
| TRENT | 2412/2429 (99.3%) | 1 | 2413/2429 (99.3%) | 5.69% | 1 | settled |
| ZYDUSLIFE | 1083/1086 (99.7%) | 1 | 1084/1086 (99.8%) | 5.30% | 0 | settled |

**Decision B122, recorded not assumed.** The completeness ruling excludes a day for missing minutes only "ON A DAY WHERE GATE-1 ALSO FAILS". A relieved day's gate-1 verdict is *pass (by relief)*, so it is handed to gate 2 as reconciled. The relief's own conditions (b) and (c) are the direct evidence that nothing was lost -- exactly the hypothesis the missing-minutes trigger exists to catch -- and the thin days relief targets are precisely the days that carry tradeless minutes, so the other reading would cancel the relief it had just granted. The last column above measures how often it mattered: 95 of 435 relieved days also carried more than 15 tradeless minutes.

### 3e. Floors in UN-PROVABLE eras -- the FINAL data ruling (QUESTIONS.md Q-11 addendum 4)

The architect's ruling: "an un-provable era is a conclusion under the floor-less model; where the floor itself caused unprovability, the hunt was locked out of exactly the eras needing it." Floor hypotheses may now be tested inside un-provable eras under four guards: (i) hunting is SIGNATURE-GATED, never blanket; (ii) the one-fresh-unknown-per-era discipline holds -- the floor is the fresh unknown and previously committed sources combine with it; (iii) acceptance is unchanged -- the era stands only if it becomes provable under normal per-day price containment and gate-1 re-gating; (iv) full provenance in the map.

**Clause (i) -- what the signature gate admitted.** An event qualifies only by the gate-3 raw-gap-near-zero signature (the measured raw gap is strictly nearer 0 than the healthy `k - 1`) or by an era failure-rate cliff (>= 95% of the gated days below the ex-date fail gate 1, over at least 20 days). Everything else keeps exactly its pre-ruling domain.

**Every floor this run MEASURED** -- event, the splice date the bisection returned, and what it cost. A floor AT the ex-date means the vendor never applied that event to one day of our history; a floor inside the span means it applied it from that date on.

| Symbol | Event ex-date | Measured floor | Probes | What the search found |
|---|---|---|---|---|
| DIXON | 2021-03-18 | 2018-10-01 | 11 | vendor application floor 2018-10-01: the event is absent from every chain before it (2018-09-28 probed event-out) and applied from it on |
| HINDPETRO | 2019-06-06 | 2019-06-06 | 3 | vendor application floor at or above the ex-date 2019-06-06: the event is absent from every chain in our history (3 probed day(s) across 2019-02-14 .. 2019-06-04, all event-out) |
| IEX | 2021-12-03 | 2019-10-01 | 11 | vendor application floor 2019-10-01: the event is absent from every chain before it (2019-09-30 probed event-out) and applied from it on |
| INOXWIND | 2024-05-24 | 2022-05-19 | 13 | vendor application floor 2022-05-19: the event is absent from every chain before it (2022-05-18 probed event-out) and applied from it on |
| JUBLFOOD | 2022-04-19 | 2018-01-18 | 12 | vendor application floor 2018-01-18: the event is absent from every chain before it (2018-01-17 probed event-out) and applied from it on |
| NTPC | 2019-02-06 | 2019-02-06 | 3 | vendor application floor at or above the ex-date 2019-02-06: the event is absent from every chain in our history (3 probed day(s) across 2016-10-03 .. 2019-02-05, all event-out) |
| RELIANCE | 2023-07-20 | 2022-01-05 | 11 | vendor application floor 2022-01-05: the event is absent from every chain before it (2022-01-04 probed event-out) and applied from it on |
| VEDL | 2023-12-27 | 2023-12-27 | 3 | vendor application floor at or above the ex-date 2023-12-27: the event is absent from every chain in our history (3 probed day(s) across 2023-05-30 .. 2023-12-26, all event-out) |
| VEDL | 2018-11-06 | 2018-11-06 | 3 | vendor application floor at or above the ex-date 2018-11-06: the event is absent from every chain in our history (3 probed day(s) across 2018-03-20 .. 2018-11-05, all event-out) |

**Every event the gate ADMITTED into an un-provable era**, with the measurement that admitted it. An event absent from this table was never hunted there, however badly its span fails -- that is the ruling's "never blanket".

| Symbol | Event | Admitting signature |
|---|---|---|
| ASTRAL | 2019-09-16 | era failure-rate cliff: 729/729 = 100.0% of the gated days below 2019-09-16 fail gate 1 (>= 95%) |
| BEL | 2017-03-16 | gate-3 raw-gap-near-zero: \|raw gap\| 5.22% is nearer 0 than the event's own step 90.00% (k=0.1), adjusted gap 952.21% -- both closes are already in the same price domain AND era failure-rate cliff: 112/112 = 100.0% of the gated days below 2017-03-16 fail gate 1 (>= 95%) |
| BEL | 2017-09-28 | era failure-rate cliff: 134/134 = 100.0% of the gated days below 2017-09-28 fail gate 1 (>= 95%) |
| BPCL | 2017-02-28 | era failure-rate cliff: 101/101 = 100.0% of the gated days below 2017-02-28 fail gate 1 (>= 95%) |
| BPCL | 2017-07-13 | era failure-rate cliff: 92/92 = 100.0% of the gated days below 2017-07-13 fail gate 1 (>= 95%) |
| BSE | 2017-08-24 | era failure-rate cliff: 137/137 = 100.0% of the gated days below 2017-08-24 fail gate 1 (>= 95%) |
| GAIL | 2017-03-09 | gate-3 raw-gap-near-zero: \|raw gap\| 2.52% is nearer 0 than the event's own step 25.00% (k=0.75), adjusted gap 29.97% -- both closes are already in the same price domain AND era failure-rate cliff: 108/108 = 100.0% of the gated days below 2017-03-09 fail gate 1 (>= 95%) |
| GAIL | 2018-03-27 | era failure-rate cliff: 260/260 = 100.0% of the gated days below 2018-03-27 fail gate 1 (>= 95%) |
| HINDPETRO | 2017-03-01 | era failure-rate cliff: 102/102 = 100.0% of the gated days below 2017-03-01 fail gate 1 (>= 95%) |
| HINDPETRO | 2017-07-11 | gate-3 raw-gap-near-zero: \|raw gap\| 0.35% is nearer 0 than the event's own step 33.33% (k=0.6666666666666666666666666667), adjusted gap 49.47% -- both closes are already in the same price domain AND era failure-rate cliff: 89/89 = 100.0% of the gated days below 2017-07-11 fail gate 1 (>= 95%) |
| HINDPETRO | 2018-02-28 | era failure-rate cliff: 159/159 = 100.0% of the gated days below 2018-02-28 fail gate 1 (>= 95%) |
| HINDPETRO | 2019-02-14 | era failure-rate cliff: 238/238 = 100.0% of the gated days below 2019-02-14 fail gate 1 (>= 95%) |
| HINDPETRO | 2019-06-06 | era failure-rate cliff: 73/73 = 100.0% of the gated days below 2019-06-06 fail gate 1 (>= 95%) |
| IEX | 2018-10-19 | era failure-rate cliff: 246/246 = 100.0% of the gated days below 2018-10-19 fail gate 1 (>= 95%) |
| IEX | 2021-12-03 | era failure-rate cliff: 773/773 = 100.0% of the gated days below 2021-12-03 fail gate 1 (>= 95%) |
| INOXWIND | 2024-05-24 | gate-3 raw-gap-near-zero: \|raw gap\| 10.98% is nearer 0 than the event's own step 75.00% (k=0.25), adjusted gap 343.91% -- both closes are already in the same price domain AND era failure-rate cliff: 1839/1891 = 97.3% of the gated days below 2024-05-24 fail gate 1 (>= 95%) |
| IOC | 2016-10-18 | gate-3 raw-gap-near-zero: \|raw gap\| 0.17% is nearer 0 than the event's own step 50.00% (k=0.5), adjusted gap 100.34% -- both closes are already in the same price domain |
| IOC | 2017-02-09 | era failure-rate cliff: 80/80 = 100.0% of the gated days below 2017-02-09 fail gate 1 (>= 95%) |
| IOC | 2018-02-08 | era failure-rate cliff: 248/248 = 100.0% of the gated days below 2018-02-08 fail gate 1 (>= 95%) |
| IOC | 2018-03-15 | gate-3 raw-gap-near-zero: \|raw gap\| 2.77% is nearer 0 than the event's own step 50.00% (k=0.5), adjusted gap 94.45% -- both closes are already in the same price domain AND era failure-rate cliff: 23/23 = 100.0% of the gated days below 2018-03-15 fail gate 1 (>= 95%) |
| IOC | 2022-06-30 | gate-3 raw-gap-near-zero: \|raw gap\| 1.43% is nearer 0 than the event's own step 33.33% (k=0.6666666666666666666666666667), adjusted gap 52.15% -- both closes are already in the same price domain |
| NESTLEIND | 2020-10-29 | era failure-rate cliff: 1009/1009 = 100.0% of the gated days below 2020-10-29 fail gate 1 (>= 95%) |
| NMDC | 2017-03-16 | era failure-rate cliff: 112/112 = 100.0% of the gated days below 2017-03-16 fail gate 1 (>= 95%) |
| NMDC | 2018-03-27 | era failure-rate cliff: 256/256 = 100.0% of the gated days below 2018-03-27 fail gate 1 (>= 95%) |
| NTPC | 2019-02-06 | era failure-rate cliff: 582/582 = 100.0% of the gated days below 2019-02-06 fail gate 1 (>= 95%) |
| OIL | 2017-01-12 | gate-3 raw-gap-near-zero: \|raw gap\| 4.63% is nearer 0 than the event's own step 25.00% (k=0.75), adjusted gap 27.16% -- both closes are already in the same price domain AND era failure-rate cliff: 70/70 = 100.0% of the gated days below 2017-01-12 fail gate 1 (>= 95%) |
| OIL | 2017-02-13 | era failure-rate cliff: 21/21 = 100.0% of the gated days below 2017-02-13 fail gate 1 (>= 95%) |
| OIL | 2018-02-21 | era failure-rate cliff: 254/254 = 100.0% of the gated days below 2018-02-21 fail gate 1 (>= 95%) |
| OIL | 2018-03-27 | era failure-rate cliff: 23/23 = 100.0% of the gated days below 2018-03-27 fail gate 1 (>= 95%) |
| PETRONET | 2017-07-03 | gate-3 raw-gap-near-zero: \|raw gap\| 0.87% is nearer 0 than the event's own step 50.00% (k=0.5), adjusted gap 98.26% -- both closes are already in the same price domain AND era failure-rate cliff: 185/185 = 100.0% of the gated days below 2017-07-03 fail gate 1 (>= 95%) |
| TATASTEEL | 2018-01-31 | era failure-rate cliff: 331/331 = 100.0% of the gated days below 2018-01-31 fail gate 1 (>= 95%) |
| UPL | 2019-07-02 | gate-3 raw-gap-near-zero: \|raw gap\| 8.62% is nearer 0 than the event's own step 33.33% (k=0.6666666666666666666666666667), adjusted gap 62.94% -- both closes are already in the same price domain AND era failure-rate cliff: 679/679 = 100.0% of the gated days below 2019-07-02 fail gate 1 (>= 95%) |
| VBL | 2019-07-25 | era failure-rate cliff: 672/672 = 100.0% of the gated days below 2019-07-25 fail gate 1 (>= 95%) |
| VBL | 2021-06-10 | era failure-rate cliff: 464/464 = 100.0% of the gated days below 2021-06-10 fail gate 1 (>= 95%) |
| VEDL | 2018-11-06 | era failure-rate cliff: 156/156 = 100.0% of the gated days below 2018-11-06 fail gate 1 (>= 95%) |
| VEDL | 2023-12-27 | era failure-rate cliff: 144/144 = 100.0% of the gated days below 2023-12-27 fail gate 1 (>= 95%) |

**Clause (iii) -- acceptance, era by era.** A measured floor is handed back to the MAP BUILDER, not layered onto the committed map: every era it touches must satisfy the same 2-paise per-day price containment and the same unwidened gate-1 band as any other era. An era that does is PROMOTED to provable; one that does not stays un-provable and its days stay excluded + counted.

| Symbol | Eras provable before | after | Promoted | Gate-1 before | Gate-1 after |
|---|---|---|---|---|---|
| APLAPOLLO | 2 | 2 | 0 | unchanged | 2363/2431 (97.2%) |
| ASTRAL | 2 | 2 | 0 | 1332/2430 (54.8%) | 1699/2430 (69.9%) |
| BEL | 1 | 1 | 0 | unchanged | 2173/2431 (89.4%) |
| BPCL | 11 | 11 | 0 | unchanged | 2223/2429 (91.5%) |
| BSE | 6 | 6 | 0 | unchanged | 2115/2345 (90.2%) |
| COCHINSHIP | 2 | 2 | 0 | unchanged | 2198/2215 (99.2%) |
| GAIL | 10 | 10 | 0 | unchanged | 1990/2431 (81.9%) |
| HDFCBANK | 2 | 2 | 0 | unchanged | 2373/2429 (97.7%) |
| HINDPETRO | 7 | 7 | 1 | 1766/2429 (72.7%) | 1995/2429 (82.1%) |
| IEX | 0 | 0 | 1 | 1149/2169 (53.0%) | 1149/2169 (53.0%) |
| INOXWIND | 1 | 2 | 0 | 588/2429 (24.2%) | 2410/2429 (99.2%) |
| IOC | 3 | 3 | 0 | unchanged | 2062/2431 (84.8%) |
| JUBLFOOD | 2 | 2 | 0 | 2094/2431 (86.1%) | 2094/2431 (86.1%) |
| NESTLEIND | 2 | 2 | 0 | 1129/2430 (46.5%) | 1391/2430 (57.2%) |
| NMDC | 12 | 12 | 0 | unchanged | 2053/2431 (84.5%) |
| NTPC | 7 | 7 | 0 | 1841/2428 (75.8%) | 1841/2428 (75.8%) |
| OIL | 8 | 8 | 0 | unchanged | 2048/2429 (84.3%) |
| PETRONET | 2 | 2 | 0 | unchanged | 2234/2431 (91.9%) |
| PGEL | 1 | 1 | 0 | unchanged | 2378/2429 (97.9%) |
| TATASTEEL | 3 | 3 | 0 | unchanged | 2087/2431 (85.8%) |
| UPL | 1 | 1 | 0 | unchanged | 1750/2430 (72.0%) |
| VBL | 3 | 3 | 0 | unchanged | 1270/2407 (52.8%) |
| VEDL | 4 | 17 | 13 | 2119/2429 (87.2%) | 2119/2429 (87.2%) |

## 4. Exclusions by reason

| Reason | Symbol-days | Note |
|---|---|---|
| gate-1 (volume reconciliation outside [-0.1%, +5.0%], UNRELIEVED) | 6,383 | CONTEXT 4.5 gate 1; excluded + counted per CONTEXT 7-E3. 432 further above-ceiling failures were relieved as a thin day's auction share (section 3d) and are NOT excluded |
| gate-2 (candle integrity) | 1,191 | duplicates, impossible OHLC, negative values, or missing minutes ON A DAY WHERE GATE 1 ALSO FAILS (the completeness ruling) |
| un-provable (no map era / unknown factor in (D, F]) | 300 | the Q-11 surgical clamp -- stored so the day is visible, failed by gate 1 |
| stored days LEFT UNTOUCHED (baseline unidentified) | 4,526 | not an exclusion reason and mostly not damage: the map application declined to correct these days because their stored bars match neither raw nor the map's chain nor a one-too-many division. Declining is the conservative action -- a day that already needed no correction is unaffected, and gate 1 decides either way. The count measures how often the classifier refuses, not how many days are wrong |
| quarantined symbols (whole history) | 14,294 | 6 symbol(s) below the 80% gate-1 floor |

**The unknown-baseline days, re-classified against the ENRICHED hypothesis set (Q-11 addendum 4).** The set is now `1 / k_era / 1/k_era / 1/k_era^2` plus, wherever a measured floor makes the day's own chain differ from its era chain, `k_target/k_era` (pre-floor-divided), `k_era/k_target` (floor-overreached) and `k_target` itself (as-fetched-floored -- the vendor's own untouched bars on a floored day, which is what every day of a newly PROMOTED era looks like). Of the 4,526 days still unidentified, **257 also fail gate 1** -- those are the only ones that cost coverage. The remainder reconcile exactly as they stand, which is why declining to touch them is the conservative action and not a loss. A day is never corrected by a guessed factor: the tolerance is derived from the candidate set itself (half the closest relative gap, capped at 2%), so extending the set can never let two hypotheses claim one ratio.

### Gate 2 redefined: completeness is volume reconciliation, not a minute count

The architect's ruling of 2026-07-26 (QUESTIONS.md "CONTEXT 4.5 / 7-E4 AMENDMENT"): **the vendor omits minutes in which nothing traded**, so a missing stamp on a day whose gate-1 volume reconciliation PASSES is a NO-TRADE minute, not missing data -- every traded rupee is already accounted for. Gate 2's exclusion triggers are now exactly four, and the run counts each one separately:

| Gate-2 trigger | Symbol-days | Note |
|---|---|---|
| missing minutes AND gate 1 also failed | 1,012 | indistinguishable from data loss, so still excluded |
| duplicate stamps | 0 | unchanged trigger |
| impossible OHLC (high<low, close outside range) | 2 | unchanged trigger (CONTEXT 4.5's own two) |
| negative price or volume | 181 | trigger ADDED by the ruling -- and it fired: see below |
| **missing minutes with gate 1 PASSING -> INCLUDED** | **92,200** | recorded as liquidity statistics (section 3b), never an exclusion -- this is the redefinition's whole effect |

**The NEGATIVE-values trigger the ruling added found a real defect on its first run.** Every one of its exclusions lands on 4 date(s) -- `2023-05-03`, `2023-05-04`, `2023-08-21`, `2024-03-02` -- across essentially EVERY symbol processed, not on scattered per-symbol accidents. The vendor serves 1-minute bars with negative VOLUME for those dates (measured: ABB -6,060 and -2 shares, AXISBANK -99,379 and -1, CIPLA -43,534, all stamped 11:15 onwards). `2024-03-02` is a SATURDAY -- one of NSE's disaster-recovery special live sessions. Such a date is already excluded from trading days, bias pairs and trading by QUESTIONS.md Q-5, so nothing was ever going to trade it; what is new is that the day's candles are now excluded EXPLICITLY and counted, instead of passing gate 2 on a minute count and relying on the calendar alone. Before this ruling a negative share count was not a gate-2 trigger at all.

Measured before the ruling, on the same stored candles: ABB traded 318/293/325/338 of 375 minutes on four consecutive 2019 days -- 37..82 missing -- while gate 1 reconciled every one of them, and the pre-ruling gate 2 excluded all four. CONTEXT 4.3's PoC measurement of "375/375 candles, zero gaps" was taken on 5 LIQUID symbols in 2026, which is why the minute-count rule looked safe. CONTEXT 7-E4's own minute-count trigger ("missing > 5 of its 120") is retired by the same ruling; chunk 6's POC window is valid when the DAY passes gate 1, and a tradeless minute contributes zero volume to the profile.

### Quarantined symbols

| Symbol | Route | Gate-1 | Rerouted? | Failure pattern | Why |
|---|---|---|---|---|---|
| ASTRAL | map-required | 1699/2430 (69.9%) | yes | clustered-before-ex-date (adjustment problem) | gate-1 pass rate 69.9% (strict 69.9% + 1 relieved) is below 80%; skipped, listed, run continues |
| IEX | map-required | 1149/2169 (53.0%) | yes | clustered-before-ex-date (adjustment problem) | gate-1 pass rate 53.0% (strict 52.9% + 1 relieved) is below 80%; skipped, listed, run continues |
| NESTLEIND | map-required | 1391/2430 (57.2%) | n/a (map path) | mixed | gate-1 pass rate 57.2% is below 80%; skipped, listed, run continues |
| NTPC | map-required | 1841/2428 (75.8%) | n/a (map path) | clustered-before-ex-date (adjustment problem) | gate-1 pass rate 75.8% (strict 75.8% + 1 relieved) is below 80%; skipped, listed, run continues |
| UPL | map-required | 1750/2430 (72.0%) | n/a (map path) | clustered-before-ex-date (adjustment problem) | gate-1 pass rate 72.0% is below 80%; skipped, listed, run continues |
| VBL | map-required | 1270/2407 (52.8%) | yes | clustered-before-ex-date (adjustment problem) | gate-1 pass rate 52.8% is below 80%; skipped, listed, run continues |

**Failure-pattern analysis** (the Q-12-addendum ruling: "failures clustered before a CA ex-date (adjustment problem) vs scattered (auction/liquidity shape)"). Every table-path symbol here was first REROUTED through the map path as a second pass -- probes bought it the price oracle the routing rule does not otherwise give a bonus/split-only symbol -- and stayed quarantined anyway.

- **ASTRAL** -- clustered-before-ex-date (adjustment problem). an era fails at 100.0% while the post-last-ex-date era fails at 0.1% -- one wrong factor applied to a whole span, not a market property
  - per-era gate-1 failure rate: < 2019-09-16 729/729 (100.0%); < 2021-03-18 1/375 (0.3%); < 2023-03-14 0/493 (0.0%); >= 2023-03-14 1/833 (0.1%)
- **IEX** -- clustered-before-ex-date (adjustment problem). an era fails at 100.0% while the post-last-ex-date era fails at 0.1% -- one wrong factor applied to a whole span, not a market property
  - per-era gate-1 failure rate: < 2018-10-19 246/246 (100.0%); < 2021-12-03 773/773 (100.0%); >= 2021-12-03 1/1150 (0.1%)
- **NESTLEIND** -- mixed. worst era failure rate 57.7%, post-last-ex-date era 0.0%; 1010 above the ceiling / 29 below the floor -- neither pattern is clean
  - per-era gate-1 failure rate: < 2024-01-05 1038/1798 (57.7%); < 2025-08-08 1/396 (0.3%); >= 2025-08-08 0/236 (0.0%)
- **NTPC** -- clustered-before-ex-date (adjustment problem). an era fails at 100.0% while the post-last-ex-date era fails at 0.1% -- one wrong factor applied to a whole span, not a market property
  - per-era gate-1 failure rate: < 2019-02-06 582/582 (100.0%); < 2019-03-19 2/28 (7.1%); < 2019-08-13 1/98 (1.0%); < 2020-08-13 0/247 (0.0%); < 2021-02-11 1/123 (0.8%); < 2021-09-08 0/141 (0.0%); < 2022-02-03 0/101 (0.0%); < 2023-02-03 0/249 (0.0%); >= 2023-02-03 1/859 (0.1%)
- **UPL** -- clustered-before-ex-date (adjustment problem). an era fails at 100.0% while the post-last-ex-date era fails at 0.0% -- one wrong factor applied to a whole span, not a market property
  - per-era gate-1 failure rate: < 2019-07-02 679/679 (100.0%); < 2024-11-26 1/1339 (0.1%); >= 2024-11-26 0/412 (0.0%)
- **VBL** -- clustered-before-ex-date (adjustment problem). an era fails at 100.0% while the post-last-ex-date era fails at 0.0% -- one wrong factor applied to a whole span, not a market property
  - per-era gate-1 failure rate: < 2019-07-25 672/672 (100.0%); < 2021-06-10 464/464 (100.0%); < 2022-06-06 0/245 (0.0%); < 2023-06-15 0/255 (0.0%); < 2024-09-12 1/309 (0.3%); >= 2024-09-12 0/462 (0.0%)

### Deferred to the architect: the gate-1 +5.0% ceiling on illiquid names

The Q-12-addendum ruling: "The gate-1 +5.0% ceiling's behavior on illiquid names (auction share of a tiny day can exceed 5%) is EXPLICITLY DEFERRED to the architect's review of the completed run's report -- flag it there with per-symbol evidence; do not tune the band." **The band is untouched** (`[-0.1%, 5.0%]`, byte-identical). This is the evidence, per symbol:

| Symbol | Gate-1 failures | Above +5.0% ceiling | Below -0.1% floor | Median raw daily volume (all days) | Median on the above-ceiling days | Pattern |
|---|---|---|---|---|---|---|
| ASTRAL | 731 | 0 | 731 | 242,725 | 0 | clustered-before-ex-date (adjustment problem) |
| IEX | 1020 | 1019 | 1 | 3,533,577 | 292,260 | clustered-before-ex-date (adjustment problem) |
| NESTLEIND | 1039 | 1010 | 29 | 79,007 | 60,014 | mixed |
| NTPC | 587 | 0 | 587 | 10,501,134 | 0 | clustered-before-ex-date (adjustment problem) |
| UPL | 680 | 0 | 680 | 2,143,270 | 0 | clustered-before-ex-date (adjustment problem) |
| VBL | 1137 | 1136 | 1 | 498,288 | 114,174 | clustered-before-ex-date (adjustment problem) |

Read it this way: an ABOVE-ceiling failure on a day whose raw daily volume is far below the symbol's own median is the pre-open auction taking more than 5% of a thin day -- a market property, not a data defect. A BELOW-floor failure, or an above-ceiling failure on an ordinary-volume day, is an adjustment problem. No band was moved either way.

## 5. Gate 3 -- adjustment sanity across every share-count ex-date

CONTEXT 4.5 gate 3: on every split/bonus ex-date in the stored span, the ADJUSTED series must show |day-over-day gap| < 20%. Checked on the stored RAW closes with the event's own CONTEXT 4.2 factor applied at the comparison. **118 ex-date(s) checked, 15 failed.**

Every failure, with its numbers. `raw gap` is the two stored closes with NO factor applied; `adjusted gap` is CONTEXT 4.5's own test (the pre-ex close scaled by `k`). Read together they name the defect: a raw gap near `k - 1` with an adjusted gap near zero is a healthy event, while a raw gap near ZERO with a large adjusted gap means the two closes are ALREADY in the same price domain -- i.e. the pre-ex side was never un-adjusted for the event, which is the exact signature of a vendor APPLICATION FLOOR (section 3c) sitting above the pre-ex day.

| Symbol | Event(s) | Ex-date | k | Pre-ex day | Ex day | Raw gap | Adjusted gap | Classification |
|---|---|---|---|---|---|---|---|---|
| ASTRAL | bonus | 2019-09-16 | 0.8 | 2019-09-13 | 2019-09-16 | 38.49% | 73.11% | hunted, no floor needed; residual |
| BEL | split | 2017-03-16 | 0.1 | 2017-03-15 | 2017-03-16 | 5.22% | 952.21% | unresolved-floor span -- hunted, no floor fitted; residual |
| BPCL | bonus | 2017-07-13 | 0.6666666666666666666666666667 | 2017-07-12 | 2017-07-13 | 101.21% | 201.81% | hunted, no floor needed; residual |
| COCHINSHIP | split | 2024-01-10 | 0.5 | 2024-01-09 | 2024-01-10 | -40.00% | 20.00% | hunted, no floor needed; residual |
| GAIL | bonus | 2017-03-09 | 0.75 | 2017-03-08 | 2017-03-09 | -2.52% | 29.97% | unresolved-floor span -- hunted, no floor fitted; residual |
| GAIL | bonus | 2018-03-27 | 0.75 | 2018-03-26 | 2018-03-27 | 201.98% | 302.63% | hunted, no floor needed; residual |
| HINDPETRO | bonus | 2017-07-11 | 0.6666666666666666666666666667 | 2017-07-10 | 2017-07-11 | -0.35% | 49.47% | hunted; a floor was measured for another event of this symbol but not for this one -- residual |
| IOC | bonus | 2016-10-18 | 0.5 | 2016-10-17 | 2016-10-18 | 0.17% | 100.34% | unresolved-floor span -- hunted, no floor fitted; residual |
| IOC | bonus | 2018-03-15 | 0.5 | 2018-03-14 | 2018-03-15 | -2.77% | 94.45% | unresolved-floor span -- hunted, no floor fitted; residual |
| IOC | bonus | 2022-06-30 | 0.6666666666666666666666666667 | 2022-06-29 | 2022-06-30 | 1.43% | 52.15% | unresolved-floor span -- hunted, no floor fitted; residual |
| OIL | bonus | 2017-01-12 | 0.75 | 2017-01-11 | 2017-01-12 | -4.63% | 27.16% | unresolved-floor span -- hunted, no floor fitted; residual |
| OIL | bonus | 2018-03-27 | 0.6666666666666666666666666667 | 2018-03-26 | 2018-03-27 | 42.44% | 113.67% | hunted, no floor needed; residual |
| PETRONET | bonus | 2017-07-03 | 0.5 | 2017-06-30 | 2017-07-03 | -0.87% | 98.26% | unresolved-floor span -- hunted, no floor fitted; residual |
| UPL | bonus | 2019-07-02 | 0.6666666666666666666666666667 | 2019-07-01 | 2019-07-02 | 8.62% | 62.94% | unresolved-floor span -- hunted, no floor fitted; residual |
| VBL | bonus | 2021-06-10 | 0.6666666666666666666666666667 | 2021-06-09 | 2021-06-10 | -65.70% | -48.56% | hunted, no floor needed; residual |

### The DISCLOSED RESIDUAL register (QUESTIONS.md Q-11 addendum 4)

The final ruling closes the data era: "residuals after this pass are disclosed, not chased." This is that register -- every gate-3 failure that survived the signature-gated hunt, with the numbers, the symbol's coverage cost, and why the hunt did not resolve it. Chunk 9's report carries this table forward.

| Symbol | Ex-date | k | Raw gap | Adjusted gap | Signature? | Symbol-days failing gate 1 | Why it is residual |
|---|---|---|---|---|---|---|---|
| ASTRAL | 2019-09-16 | 0.8 | 38.49% | 73.11% | no -- raw gap 38.49% is nearer the healthy k-1 than 0, so the raw-gap-near-zero signature does not admit it | 731 | hunted, no floor needed; residual |
| BEL | 2017-03-16 | 0.1 | 5.22% | 952.21% | gate-3 raw-gap-near-zero: \|raw gap\| 5.22% is nearer 0 than the event's own step 90.00% (k=0.1), adjusted gap 952.21% -- both closes are already in the same price domain | 258 | unresolved-floor span -- hunted, no floor fitted; residual |
| BPCL | 2017-07-13 | 0.6666666666666666666666666667 | 101.21% | 201.81% | no -- raw gap 101.21% is nearer the healthy k-1 than 0, so the raw-gap-near-zero signature does not admit it | 206 | hunted, no floor needed; residual |
| COCHINSHIP | 2024-01-10 | 0.5 | -40.00% | 20.00% | no -- raw gap -40.00% is nearer the healthy k-1 than 0, so the raw-gap-near-zero signature does not admit it | 17 | hunted, no floor needed; residual |
| GAIL | 2017-03-09 | 0.75 | -2.52% | 29.97% | gate-3 raw-gap-near-zero: \|raw gap\| 2.52% is nearer 0 than the event's own step 25.00% (k=0.75), adjusted gap 29.97% -- both closes are already in the same price domain | 441 | unresolved-floor span -- hunted, no floor fitted; residual |
| GAIL | 2018-03-27 | 0.75 | 201.98% | 302.63% | no -- raw gap 201.98% is nearer the healthy k-1 than 0, so the raw-gap-near-zero signature does not admit it | 441 | hunted, no floor needed; residual |
| HINDPETRO | 2017-07-11 | 0.6666666666666666666666666667 | -0.35% | 49.47% | gate-3 raw-gap-near-zero: \|raw gap\| 0.35% is nearer 0 than the event's own step 33.33% (k=0.6666666666666666666666666667), adjusted gap 49.47% -- both closes are already in the same price domain | 434 | hunted; a floor was measured for another event of this symbol but not for this one -- residual |
| IOC | 2016-10-18 | 0.5 | 0.17% | 100.34% | gate-3 raw-gap-near-zero: \|raw gap\| 0.17% is nearer 0 than the event's own step 50.00% (k=0.5), adjusted gap 100.34% -- both closes are already in the same price domain | 369 | unresolved-floor span -- hunted, no floor fitted; residual |
| IOC | 2018-03-15 | 0.5 | -2.77% | 94.45% | gate-3 raw-gap-near-zero: \|raw gap\| 2.77% is nearer 0 than the event's own step 50.00% (k=0.5), adjusted gap 94.45% -- both closes are already in the same price domain | 369 | unresolved-floor span -- hunted, no floor fitted; residual |
| IOC | 2022-06-30 | 0.6666666666666666666666666667 | 1.43% | 52.15% | gate-3 raw-gap-near-zero: \|raw gap\| 1.43% is nearer 0 than the event's own step 33.33% (k=0.6666666666666666666666666667), adjusted gap 52.15% -- both closes are already in the same price domain | 369 | unresolved-floor span -- hunted, no floor fitted; residual |
| OIL | 2017-01-12 | 0.75 | -4.63% | 27.16% | gate-3 raw-gap-near-zero: \|raw gap\| 4.63% is nearer 0 than the event's own step 25.00% (k=0.75), adjusted gap 27.16% -- both closes are already in the same price domain | 381 | unresolved-floor span -- hunted, no floor fitted; residual |
| OIL | 2018-03-27 | 0.6666666666666666666666666667 | 42.44% | 113.67% | no -- raw gap 42.44% is nearer the healthy k-1 than 0, so the raw-gap-near-zero signature does not admit it | 381 | hunted, no floor needed; residual |
| PETRONET | 2017-07-03 | 0.5 | -0.87% | 98.26% | gate-3 raw-gap-near-zero: \|raw gap\| 0.87% is nearer 0 than the event's own step 50.00% (k=0.5), adjusted gap 98.26% -- both closes are already in the same price domain | 197 | unresolved-floor span -- hunted, no floor fitted; residual |
| UPL | 2019-07-02 | 0.6666666666666666666666666667 | 8.62% | 62.94% | gate-3 raw-gap-near-zero: \|raw gap\| 8.62% is nearer 0 than the event's own step 33.33% (k=0.6666666666666666666666666667), adjusted gap 62.94% -- both closes are already in the same price domain | 680 | unresolved-floor span -- hunted, no floor fitted; residual |
| VBL | 2021-06-10 | 0.6666666666666666666666666667 | -65.70% | -48.56% | no -- raw gap -65.70% is nearer the healthy k-1 than 0, so the raw-gap-near-zero signature does not admit it | 1,137 | hunted, no floor needed; residual |

**Classification key.** `pre-floor span` -- the pre-ex close sits below a vendor application floor this run MEASURED for that very event, so the two closes were never in the same price domain and the gate-3 comparison there was meaningless before the fix; the row above is the POST-fix recheck. `unresolved-floor span` -- the symbol was hunted but no floor resolved for this event, so the comparison stands and the failure is residual. `not hunted` -- the symbol reconciles above the hunt line, so the failure is residual and carries its own numbers. **No failure is waived**: every row is printed with its gap either way.

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
- **The measured VOLUME factor is a MINIMUM, not a median (QUESTIONS.md Q-12).** The 1-minute sum systematically under-counts the exchange's daily total by the pre-open call auction, so the volume observable is `true / (1 - auction_share)` -- contaminated in one direction only. Its FLOOR is therefore the unbiased point, taken across the probe days whose PRICE containment passes, minimum 3 such days, else no measured-volume candidate is offered at all. The estimator is also conservative in the safe direction: too low a factor pushes gate-1 gaps POSITIVE, into the band's wide side.
- **Completeness is gate 1, not a minute count (CONTEXT 4.5/7-E4 amendment).** A missing 1-minute stamp on a gate-1-passing day is a no-trade minute; see section 3b for the per-symbol traded-minute statistics and section 4 for the trigger counts. **No liquidity filter exists anywhere in the code** -- the trader specified none.
- **NO ruling has widened gate 1's band.** It is still `[-0.1%, 5.0%]`, byte-identical, and `volume_gate` is untouched. The +5.0% ceiling question the Q-12 addendum DEFERRED is now answered by the AUCTION-RELIEF ruling (section 3d): the ceiling stays, and an above-ceiling failure with intact extremes, a matching opening print and a shortfall <= 20.0% is separately counted as an `auction-relief pass`. Below-floor failures are never relieved.
- **Vendor APPLICATION FLOORS (Q-11 addendum 2).** The vendor's archive is spliced: for some events its back-adjustment never reached the older bars. Each floor in section 3c was BINARY-SEARCHED against the daily oracle (does this day fit with the event in the chain or out of it?), never fitted, and is committed to the symbol's map with every probe day and verdict. Below a measured floor the event is ABSENT from that day's chain. An unresolved search changes nothing -- un-provable stays the honest fallback.
- **Compound and unparsed map nodes (Q-11 addendum 3).** Events sharing an ex-date compose into ONE node (k = product, share-count flags combined), so a symbol carrying a bonus and a face-value split on the same day is representable at last; and an UNPARSED subject enters the map with candidates {measured, absent} instead of forcing the map path and then contributing no era to probe. Both are why BAJAJFINSV and COLPAL have minute data in this report for the first time.
- **The daily store was verified before the run** (`DailyStore.verify()`, the owed REVIEW_2 F7 check): the oracle is checked before it is trusted.

