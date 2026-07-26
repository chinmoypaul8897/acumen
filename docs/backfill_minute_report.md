# Minute backfill report -- chunk 5B (full-universe 1-minute run)

Generated 2026-07-26T16:04:47 from `C:\Users\chinm\acumen\data\universe_backfill\ledger.json` and the stores. Re-runnable at any time; makes no network call.

Scope: CONTEXT 3.1's F&O stock underlyings (CONTEXT 7-E5 -- TODAY's list, with the survivorship disclosure the report owes), 1-minute candles from `2016-10-01` (CONTEXT 4.3 depth floor) or the symbol's listing, whichever is later, to `2026-07-26`.

## 1. Headline

| Measure | Value |
|---|---|
| Universe symbols | 210 |
| Processed | 56 |
| Settled | 51 |
| Quarantined (gate-1 pass rate < 80%) | 3 |
| map-required-but-unbuildable | 2 |
| Not yet processed | 154 |
| Symbol-days gated (settled symbols) | 113,067 |
| Gate-1 PASS | 111,325 (98.5%) |
| Gate-2 exclusions | 622 |
| Un-provable days (no map era / unknown factor) | 0 |
| **TOTAL coverage** (gate-1-passing days of every symbol-day seen) | **93.6%** |
| Usable symbol-days (gate 1 AND gate 2) | ~110,703 |

**Definition of done (plan.md chunk 5B): >= 95% of symbol-days pass gates.** Measured: **93.6%** of all symbol-days seen pass gate 1, with every failure categorized in section 4.

## 2. Route classification (QUESTIONS.md Q-11 addendum)

| Route | Symbols | Meaning |
|---|---|---|
| `table-path` | 31 | bonus/split-only: our CONTEXT 4.2 factors ARE the vendor's, and gate-1 volume proves the price division |
| `map-required` | 25 | carries a non-share-count event (rights / special dividend / demerger) or something unparsed: ingested only through a measured map with per-day price containment |

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
| BAJAJFINSV | 0 | 0 | 0 | - |
| BANKBARODA | 5 | 3 | 0 | dividend@2024-06-28: absent/ours; dividend@2025-06-06: absent/ours; dividend@2026-06-05: absent/ours |
| BANKINDIA | 5 | 5 | 0 | dividend@2022-07-07: absent/ours; dividend@2023-06-20: absent/ours; dividend@2024-06-18: absent/ours; dividend@2025-06-20: absent/ours; dividend@2026-05-29: absent/ours |
| BDL | 1 | 0 | 0 | - |
| BEL | 3 | 1 | 0 | bonus@2022-09-15: ours/measured |
| BHARTIARTL | 2 | 2 | 0 | rights@2019-04-23: measured/price-factor; rights@2021-09-27: absent/measured |
| BHEL | 2 | 2 | 0 | bonus@2017-09-28: ours/ours; dividend@2019-09-11: absent/ours |
| BLUESTARCO | 1 | 1 | 0 | bonus@2023-06-20: ours/ours |
| BPCL | 13 | 11 | 0 | bonus@2024-06-21: ours/ours; dividend@2018-02-22: absent/ours; dividend@2019-02-21: absent/ours; dividend@2019-08-21: absent/ours; dividend@2020-03-23: absent/ours; dividend@2021-02-17: absent/ours; dividend@2021-09-16: absent/ours; dividend@2023-12-12: absent/ours; dividend@2024-08-09: absent/ours; dividend@2025-11-07: absent/ours; dividend@2026-02-02: absent/ours |
| BRITANNIA | 2 | 2 | 0 | dividend@2020-08-26: absent/ours; split@2018-11-29: ours/ours |
| BSE | 7 | 6 | 0 | bonus@2022-03-21: ours/measured; bonus@2025-05-23: ours/ours; dividend@2018-07-25: absent/ours; dividend@2019-06-27: absent/ours; dividend@2020-07-22: absent/ours; dividend@2022-06-23: absent/ours |
| CAMS | 1 | 1 | 0 | split@2025-12-05: ours/ours |
| CANBK | 7 | 6 | 0 | dividend@2022-06-15: absent/ours; dividend@2023-06-14: absent/ours; dividend@2024-06-14: absent/ours; dividend@2025-06-13: absent/ours; dividend@2026-06-12: absent/ours; split@2024-05-15: ours/ours |
| CDSL | 2 | 2 | 0 | bonus@2024-08-23: ours/ours; dividend@2019-09-06: absent/ours |
| COALINDIA | 15 | 9 | 0 | dividend@2021-03-15: absent/ours; dividend@2021-09-02: absent/ours; dividend@2021-12-06: absent/ours; dividend@2022-02-21: absent/ours; dividend@2022-11-15: absent/ours; dividend@2023-02-08: absent/ours; dividend@2023-11-21: absent/ours; dividend@2024-11-05: absent/ours; dividend@2025-11-04: absent/ours |
| COCHINSHIP | 6 | 2 | 0 | dividend@2022-02-21: absent/ours; split@2024-01-10: ours/ours |
| COLPAL | 0 | 0 | 0 | - |

Per-event factor sources across every committed map, PRICE side -- **ours 18**, **measured 4**, **absent 53**. `ours` = our exact CONTEXT 4.2 factor matched the vendor; `measured` = the vendor used a factor we had to observe; `absent` = the vendor did not apply the event in that era.

VOLUME side -- **ours 65**, **price-factor 5**, **measured 4**, **absent 1**. The Q-12 ruling's candidate order is `ours(share-count) > chosen-price-factor > measured-minimum > absent`: `price-factor` means the event's volume was reconciled by the very factor the PRICE oracle had already pinned to 2 paise per probe day, which is strictly better evidenced than an observed volume ratio the pre-open auction biases upward. `measured` on this side is now the MINIMUM over the price-passing probe days, never the median.

## 3. Depth found, per symbol

| Symbol | Route | Clamp | First 1-min day | Days | Windows p/e/x | Gate-1 | Gate-2 excl | Avg min/day | Status |
|---|---|---|---|---|---|---|---|---|---|
| 360ONE | table-path | 2023-01-23 | 2023-01-23 | 867 | 46/0/0 | 858/867 (99.0%) | 1 | 363.6 | settled |
| ABB | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2414/2429 (99.4%) | 10 | 351.0 | settled |
| ABCAPITAL | table-path | 2017-09-01 | 2017-09-01 | 2202 | 117/0/0 | 2187/2202 (99.3%) | 2 | 372.7 | settled |
| ADANIENSOL | table-path | 2023-08-24 | 2023-08-24 | 723 | 39/0/0 | 721/723 (99.7%) | 1 | 372.9 | settled |
| ADANIENT | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2400/2429 (98.8%) | 2 | 372.7 | settled |
| ADANIGREEN | table-path | 2018-06-18 | 2018-06-18 | 2005 | 106/0/0 | 1990/2005 (99.3%) | 10 | 362.8 | settled |
| ADANIPORTS | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2410/2429 (99.2%) | 2 | 373.2 | settled |
| ADANIPOWER | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2401/2429 (98.8%) | 3 | 372.4 | settled |
| ALKEM | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2415/2429 (99.4%) | 10 | 343.9 | settled |
| AMBER | table-path | 2018-01-30 | 2018-01-30 | 2099 | 111/0/0 | 2082/2099 (99.2%) | 13 | 327.3 | settled |
| AMBUJACEM | map-required | 2016-10-01 | 2016-10-03 | 2428 | 128/1/0 | 2413/2428 (99.4%) | 2 | 373.1 | settled |
| ANGELONE | table-path | 2021-11-11 | 2021-11-11 | 1166 | 62/0/0 | 1163/1166 (99.7%) | 1 | 373.1 | settled |
| APLAPOLLO | map-required | 2016-10-01 | 2016-10-03 | 2431 | 128/1/0 | 2343/2431 (96.4%) | 85 | 314.0 | settled |
| APOLLOHOSP | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2415/2429 (99.4%) | 2 | 371.9 | settled |
| ASHOKLEY | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2414/2429 (99.4%) | 4 | 373.3 | settled |
| ASIANPAINT | table-path | 2016-10-01 | 2016-10-03 | 2430 | 128/1/0 | 2417/2430 (99.5%) | 2 | 373.2 | settled |
| ASTRAL | map-required | 2016-10-01 | 2016-10-03 | 2430 | 128/1/0 | 1331/2430 (54.8%) | 775 | 332.7 | quarantined |
| AUBANK | map-required | 2017-07-10 | 2017-07-10 | 2240 | 118/0/0 | 2235/2240 (99.8%) | 3 | 365.6 | settled |
| AUROPHARMA | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2415/2429 (99.4%) | 2 | 373.2 | settled |
| AXISBANK | table-path | 2016-10-01 | 2016-10-03 | 2428 | 128/1/0 | 2410/2428 (99.3%) | 2 | 373.3 | settled |
| BAJAJ-AUTO | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2415/2429 (99.4%) | 2 | 373.0 | settled |
| BAJAJFINSV | map-required | 2016-10-01 | - | 0 | 0/0/0 | 0/0 (-) | 0 | 0.0 | map-required-but-unbuildable |
| BAJAJHLDNG | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2406/2429 (99.1%) | 20 | 314.9 | settled |
| BAJFINANCE | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2410/2429 (99.2%) | 2 | 373.2 | settled |
| BANDHANBNK | table-path | 2018-03-27 | 2018-03-27 | 2061 | 109/0/0 | 2046/2061 (99.3%) | 3 | 373.1 | settled |
| BANKBARODA | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2416/2429 (99.5%) | 2 | 373.3 | settled |
| BANKINDIA | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2414/2429 (99.4%) | 2 | 372.6 | settled |
| BDL | map-required | 2018-03-23 | 2022-05-19 | 1038 | 55/54/0 | 536/1038 (51.6%) | 6 | 372.9 | quarantined |
| BEL | map-required | 2016-10-01 | 2016-10-03 | 2431 | 128/1/0 | 2173/2431 (89.4%) | 13 | 373.1 | settled |
| BHARATFORG | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2416/2429 (99.5%) | 2 | 372.9 | settled |
| BHARTIARTL | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2402/2429 (98.9%) | 3 | 373.2 | settled |
| BHEL | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2415/2429 (99.4%) | 3 | 373.3 | settled |
| BIOCON | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2416/2429 (99.5%) | 2 | 373.0 | settled |
| BLUESTARCO | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2408/2429 (99.1%) | 17 | 321.0 | settled |
| BOSCHLTD | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2408/2429 (99.1%) | 12 | 357.2 | settled |
| BPCL | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2222/2429 (91.5%) | 4 | 373.3 | settled |
| BRITANNIA | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2411/2429 (99.3%) | 3 | 372.7 | settled |
| BSE | map-required | 2017-02-03 | 2017-02-03 | 2345 | 124/0/0 | 2110/2345 (90.0%) | 108 | 365.1 | settled |
| CAMS | map-required | 2020-10-05 | 2020-10-05 | 1438 | 76/0/0 | 1432/1438 (99.6%) | 1 | 372.2 | settled |
| CANBK | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 1043/2429 (42.9%) | 10 | 373.2 | quarantined |
| CDSL | map-required | 2017-06-30 | 2017-06-30 | 2244 | 119/0/0 | 2228/2244 (99.3%) | 9 | 364.2 | settled |
| CGPOWER | table-path | 2017-03-08 | 2017-03-08 | 2321 | 123/0/0 | 2302/2321 (99.2%) | 5 | 356.2 | settled |
| CHOLAFIN | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2413/2429 (99.3%) | 2 | 368.2 | settled |
| CIPLA | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2414/2429 (99.4%) | 2 | 373.2 | settled |
| COALINDIA | map-required | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2415/2429 (99.4%) | 2 | 373.3 | settled |
| COCHINSHIP | map-required | 2017-08-11 | 2017-08-11 | 2215 | 117/0/0 | 2197/2215 (99.2%) | 10 | 350.0 | settled |
| COFORGE | table-path | 2020-08-20 | 2020-08-20 | 1469 | 78/0/0 | 1463/1469 (99.6%) | 2 | 373.0 | settled |
| COLPAL | map-required | 2016-10-01 | - | 0 | 0/0/0 | 0/0 (-) | 0 | 0.0 | map-required-but-unbuildable |
| CONCOR | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2416/2429 (99.5%) | 3 | 370.8 | settled |
| CROMPTON | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2413/2429 (99.3%) | 4 | 367.4 | settled |
| CUMMINSIND | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2413/2429 (99.3%) | 4 | 368.0 | settled |
| DABUR | table-path | 2016-10-01 | 2016-10-03 | 2429 | 128/1/0 | 2413/2429 (99.3%) | 2 | 372.7 | settled |
| DALBHARAT | table-path | 2019-01-22 | 2019-01-22 | 1857 | 98/0/0 | 1847/1857 (99.5%) | 5 | 350.5 | settled |
| DELHIVERY | table-path | 2022-05-24 | 2022-05-24 | 1035 | 55/0/0 | 1031/1035 (99.6%) | 1 | 370.5 | settled |
| DIVISLAB | table-path | 2016-10-01 | 2016-10-03 | 2428 | 128/1/0 | 2412/2428 (99.3%) | 3 | 372.8 | settled |
| DIXON | table-path | 2017-09-18 | 2017-09-18 | 2192 | 116/0/0 | 1925/2192 (87.8%) | 212 | 343.2 | settled |

### 3a. BEFORE / AFTER the 2026-07-26 rulings (same stored candles, no refetch)

Every row here was gated once under the pre-ruling definitions and then re-gated from the SAME stored candles, so the two columns are a controlled comparison of the rulings themselves: Q-12's volume estimator + candidate set, the CONTEXT 4.5 gate-2 completeness redefinition, and the Q-12-addendum quarantine-recovery reroute. Not one candle was re-downloaded to produce the "after" column.

| Symbol | Route (after) | Gate-1 before | Gate-1 after | Gate-2 excl before | Gate-2 excl after | Status before | Status after |
|---|---|---|---|---|---|---|---|
| 360ONE | table-path | 858/867 (99.0%) | 858/867 (99.0%) | 158 | 1 | settled | settled |
| ABB | map-required | 1632/2429 (67.2%) | 2414/2429 (99.4%) | 828 | 10 | quarantined | settled |
| ABCAPITAL | table-path | 2187/2202 (99.3%) | 2187/2202 (99.3%) | 23 | 2 | settled | settled |
| ADANIENSOL | table-path | 721/723 (99.7%) | 721/723 (99.7%) | 5 | 1 | settled | settled |
| ADANIENT | map-required | 197/2429 (8.1%) | 2400/2429 (98.8%) | 41 | 2 | quarantined | settled |
| ADANIGREEN | table-path | 1990/2005 (99.3%) | 1990/2005 (99.3%) | 316 | 10 | settled | settled |
| ADANIPORTS | table-path | 2410/2429 (99.2%) | 2410/2429 (99.2%) | 16 | 2 | settled | settled |
| ADANIPOWER | table-path | 2401/2429 (98.8%) | 2401/2429 (98.8%) | 39 | 3 | settled | settled |
| ALKEM | table-path | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 852 | 10 | settled | settled |
| AMBER | table-path | 2082/2099 (99.2%) | 2082/2099 (99.2%) | 836 | 13 | settled | settled |
| AMBUJACEM | map-required | 2413/2428 (99.4%) | 2413/2428 (99.4%) | 18 | 2 | settled | settled |
| ANGELONE | table-path | 1163/1166 (99.7%) | 1163/1166 (99.7%) | 6 | 1 | settled | settled |
| APLAPOLLO | map-required | 1892/2431 (77.8%) | 2343/2431 (96.4%) | 989 | 85 | quarantined | settled |
| APOLLOHOSP | table-path | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 84 | 2 | settled | settled |
| ASHOKLEY | map-required | 2416/2429 (99.5%) | 2414/2429 (99.4%) | 16 | 4 | settled | settled |
| ASIANPAINT | table-path | 2417/2430 (99.5%) | 2417/2430 (99.5%) | 16 | 2 | settled | settled |
| ASTRAL | map-required | 1331/2430 (54.8%) | 1331/2430 (54.8%) | 781 | 775 | quarantined | quarantined |
| AUBANK | map-required | 1029/2240 (45.9%) | 2235/2240 (99.8%) | 311 | 3 | quarantined | settled |
| AUROPHARMA | table-path | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 16 | 2 | settled | settled |
| AXISBANK | table-path | 2410/2428 (99.3%) | 2410/2428 (99.3%) | 16 | 2 | settled | settled |
| BAJAJ-AUTO | map-required | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 25 | 2 | settled | settled |
| BAJAJHLDNG | table-path | 2406/2429 (99.1%) | 2406/2429 (99.1%) | 1549 | 20 | settled | settled |
| BAJFINANCE | table-path | 2410/2429 (99.2%) | 2410/2429 (99.2%) | 16 | 2 | settled | settled |
| BANDHANBNK | table-path | 2046/2061 (99.3%) | 2046/2061 (99.3%) | 21 | 3 | settled | settled |
| BANKBARODA | map-required | 2416/2429 (99.5%) | 2416/2429 (99.5%) | 16 | 2 | settled | settled |
| BANKINDIA | map-required | 2414/2429 (99.4%) | 2414/2429 (99.4%) | 33 | 2 | settled | settled |
| BDL | map-required | 536/1038 (51.6%) | 536/1038 (51.6%) | 8 | 6 | quarantined | quarantined |
| BEL | map-required | 955/2431 (39.3%) | 2173/2431 (89.4%) | 25 | 13 | quarantined | settled |
| BHARATFORG | table-path | 2416/2429 (99.5%) | 2416/2429 (99.5%) | 18 | 2 | settled | settled |
| BHARTIARTL | map-required | 2404/2429 (99.0%) | 2402/2429 (98.9%) | 16 | 3 | settled | settled |
| BHEL | map-required | 2416/2429 (99.5%) | 2415/2429 (99.4%) | 16 | 3 | settled | settled |
| BIOCON | table-path | 2416/2429 (99.5%) | 2416/2429 (99.5%) | 24 | 2 | settled | settled |
| BLUESTARCO | map-required | 1276/2429 (52.5%) | 2408/2429 (99.1%) | 1364 | 17 | quarantined | settled |
| BOSCHLTD | table-path | 2408/2429 (99.1%) | 2408/2429 (99.1%) | 855 | 12 | settled | settled |
| BPCL | map-required | 2223/2429 (91.5%) | 2222/2429 (91.5%) | 16 | 4 | settled | settled |
| BRITANNIA | map-required | 2411/2429 (99.3%) | 2411/2429 (99.3%) | 39 | 3 | settled | settled |
| BSE | map-required | 2195/2345 (93.6%) | 2110/2345 (90.0%) | 433 | 108 | settled | settled |
| CAMS | map-required | 1436/1438 (99.9%) | 1432/1438 (99.6%) | 30 | 1 | settled | settled |
| CANBK | map-required | 1043/2429 (42.9%) | 1043/2429 (42.9%) | 16 | 10 | quarantined | quarantined |
| CDSL | map-required | 2228/2244 (99.3%) | 2228/2244 (99.3%) | 360 | 9 | settled | settled |
| CGPOWER | table-path | 2302/2321 (99.2%) | 2302/2321 (99.2%) | 524 | 5 | settled | settled |
| CHOLAFIN | table-path | 2413/2429 (99.3%) | 2413/2429 (99.3%) | 219 | 2 | settled | settled |
| CIPLA | table-path | 2414/2429 (99.4%) | 2414/2429 (99.4%) | 16 | 2 | settled | settled |
| COALINDIA | map-required | 2415/2429 (99.4%) | 2415/2429 (99.4%) | 16 | 2 | settled | settled |
| COCHINSHIP | map-required | 1957/2215 (88.4%) | 2197/2215 (99.2%) | 837 | 10 | settled | settled |
| COFORGE | table-path | 1463/1469 (99.6%) | 1463/1469 (99.6%) | 12 | 2 | settled | settled |
| CONCOR | table-path | 2416/2429 (99.5%) | 2416/2429 (99.5%) | 124 | 3 | settled | settled |
| CROMPTON | table-path | 2413/2429 (99.3%) | 2413/2429 (99.3%) | 297 | 4 | settled | settled |
| CUMMINSIND | table-path | 2413/2429 (99.3%) | 2413/2429 (99.3%) | 274 | 4 | settled | settled |
| DABUR | table-path | 2413/2429 (99.3%) | 2413/2429 (99.3%) | 36 | 2 | settled | settled |
| DALBHARAT | table-path | 1847/1857 (99.5%) | 1847/1857 (99.5%) | 522 | 5 | settled | settled |
| **TOTAL (51)** | | **101,730/113,309 (89.8%)** | **108,867/113,309 (96.1%)** | **13,124** | **1,197** | | |

### 3b. Traded-minute statistics per symbol (the completeness ruling's liquidity numbers)

The architect's completeness ruling: "NO liquidity filter is invented (the trader specified none; per-symbol traded-minutes statistics are reported for his eyes)". These are those statistics. **Nothing in the code consumes them** -- there is no minimum traded minutes, no minimum volume and no symbol drop anywhere. `Liquidity days` counts days INCLUDED while carrying more than 15 tradeless minutes -- days the pre-ruling gate 2 excluded.

| Symbol | Avg min/day | Median min/day | Min min/day | Liquidity days | Liquidity days as % of stored |
|---|---|---|---|---|---|
| 360ONE | 363.6 | 375 | 0 | 384 | 44.3% |
| ABB | 351.0 | 374 | 0 | 1269 | 52.2% |
| ABCAPITAL | 372.7 | 375 | 0 | 376 | 17.1% |
| ADANIENSOL | 372.9 | 375 | 0 | 44 | 6.1% |
| ADANIENT | 372.7 | 375 | 0 | 296 | 12.2% |
| ADANIGREEN | 362.8 | 375 | 0 | 517 | 25.8% |
| ADANIPORTS | 373.2 | 375 | 0 | 48 | 2.0% |
| ADANIPOWER | 372.4 | 375 | 0 | 370 | 15.2% |
| ALKEM | 343.9 | 372 | 0 | 1508 | 62.1% |
| AMBER | 327.3 | 370 | 0 | 1316 | 62.7% |
| AMBUJACEM | 373.1 | 375 | 0 | 196 | 8.1% |
| ANGELONE | 373.1 | 375 | 0 | 147 | 12.6% |
| APLAPOLLO | 314.0 | 374 | 0 | 1159 | 47.7% |
| APOLLOHOSP | 371.9 | 375 | 0 | 361 | 14.9% |
| ASHOKLEY | 373.3 | 375 | 0 | 25 | 1.0% |
| ASIANPAINT | 373.2 | 375 | 0 | 47 | 1.9% |
| ASTRAL | 332.7 | 375 | 0 | 295 | 12.1% |
| AUBANK | 365.6 | 375 | 0 | 593 | 26.5% |
| AUROPHARMA | 373.2 | 375 | 0 | 114 | 4.7% |
| AXISBANK | 373.3 | 375 | 0 | 25 | 1.0% |
| BAJAJ-AUTO | 373.0 | 375 | 0 | 201 | 8.3% |
| BAJAJHLDNG | 314.9 | 339 | 0 | 2070 | 85.2% |
| BAJFINANCE | 373.2 | 375 | 0 | 47 | 1.9% |
| BANDHANBNK | 373.1 | 375 | 0 | 131 | 6.4% |
| BANKBARODA | 373.3 | 375 | 0 | 23 | 0.9% |
| BANKINDIA | 372.6 | 375 | 0 | 455 | 18.7% |
| BDL | 372.9 | 375 | 0 | 107 | 10.3% |
| BEL | 373.1 | 375 | 0 | 79 | 3.2% |
| BHARATFORG | 372.9 | 375 | 0 | 327 | 13.5% |
| BHARTIARTL | 373.2 | 375 | 0 | 51 | 2.1% |
| BHEL | 373.3 | 375 | 0 | 52 | 2.1% |
| BIOCON | 373.0 | 375 | 0 | 204 | 8.4% |
| BLUESTARCO | 321.0 | 351 | 0 | 1849 | 76.1% |
| BOSCHLTD | 357.2 | 367 | 0 | 1922 | 79.1% |
| BPCL | 373.3 | 375 | 0 | 21 | 0.9% |
| BRITANNIA | 372.7 | 375 | 0 | 259 | 10.7% |
| BSE | 365.1 | 375 | 0 | 747 | 31.9% |
| CAMS | 372.2 | 375 | 0 | 308 | 21.4% |
| CANBK | 373.2 | 375 | 0 | 73 | 3.0% |
| CDSL | 364.2 | 375 | 0 | 605 | 27.0% |
| CGPOWER | 356.2 | 375 | 0 | 1095 | 47.2% |
| CHOLAFIN | 368.2 | 375 | 0 | 539 | 22.2% |
| CIPLA | 373.2 | 375 | 0 | 98 | 4.0% |
| COALINDIA | 373.3 | 375 | 0 | 31 | 1.3% |
| COCHINSHIP | 350.0 | 371 | 0 | 1252 | 56.5% |
| COFORGE | 373.0 | 375 | 0 | 112 | 7.6% |
| CONCOR | 370.8 | 375 | 0 | 601 | 24.7% |
| CROMPTON | 367.4 | 375 | 0 | 660 | 27.2% |
| CUMMINSIND | 368.0 | 375 | 0 | 812 | 33.4% |
| DABUR | 372.7 | 375 | 0 | 247 | 10.2% |
| DALBHARAT | 350.5 | 373 | 0 | 1125 | 60.6% |
| DELHIVERY | 370.5 | 375 | 0 | 293 | 28.3% |
| DIVISLAB | 372.8 | 375 | 0 | 277 | 11.4% |
| DIXON | 343.2 | 375 | 0 | 510 | 23.3% |

## 4. Exclusions by reason

| Reason | Symbol-days | Note |
|---|---|---|
| gate-1 (volume reconciliation outside [-0.1%, +5.0%]) | 1,742 | CONTEXT 4.5 gate 1; excluded + counted per CONTEXT 7-E3 |
| gate-2 (candle integrity) | 622 | duplicates, impossible OHLC, negative values, or missing minutes ON A DAY WHERE GATE 1 ALSO FAILS (the completeness ruling) |
| un-provable (no map era / unknown factor in (D, F]) | 0 | the Q-11 surgical clamp -- stored so the day is visible, failed by gate 1 |
| stored days LEFT UNTOUCHED (baseline unidentified) | 2,286 | not an exclusion reason and mostly not damage: the map application declined to correct these days because their stored bars match neither raw nor the map's chain nor a one-too-many division. Declining is the conservative action -- a day that already needed no correction is unaffected, and gate 1 decides either way. The count measures how often the classifier refuses, not how many days are wrong |
| quarantined symbols (whole history) | 5,897 | 3 symbol(s) below the 80% gate-1 floor |

### Gate 2 redefined: completeness is volume reconciliation, not a minute count

The architect's ruling of 2026-07-26 (QUESTIONS.md "CONTEXT 4.5 / 7-E4 AMENDMENT"): **the vendor omits minutes in which nothing traded**, so a missing stamp on a day whose gate-1 volume reconciliation PASSES is a NO-TRADE minute, not missing data -- every traded rupee is already accounted for. Gate 2's exclusion triggers are now exactly four, and the run counts each one separately:

| Gate-2 trigger | Symbol-days | Note |
|---|---|---|
| missing minutes AND gate 1 also failed | 571 | indistinguishable from data loss, so still excluded |
| duplicate stamps | 0 | unchanged trigger |
| impossible OHLC (high<low, close outside range) | 1 | unchanged trigger (CONTEXT 4.5's own two) |
| negative price or volume | 50 | trigger ADDED by the ruling -- and it fired: see below |
| **missing minutes with gate 1 PASSING -> INCLUDED** | **25,798** | recorded as liquidity statistics (section 3b), never an exclusion -- this is the redefinition's whole effect |

Measured before the ruling, on the same stored candles: ABB traded 318/293/325/338 of 375 minutes on four consecutive 2019 days -- 37..82 missing -- while gate 1 reconciled every one of them, and the pre-ruling gate 2 excluded all four. CONTEXT 4.3's PoC measurement of "375/375 candles, zero gaps" was taken on 5 LIQUID symbols in 2026, which is why the minute-count rule looked safe. CONTEXT 7-E4's own minute-count trigger ("missing > 5 of its 120") is retired by the same ruling; chunk 6's POC window is valid when the DAY passes gate 1, and a tradeless minute contributes zero volume to the profile.

### Quarantined symbols

| Symbol | Route | Gate-1 | Rerouted? | Failure pattern | Why |
|---|---|---|---|---|---|
| ASTRAL | map-required | 1331/2430 (54.8%) | yes | clustered-before-ex-date (adjustment problem) | gate-1 pass rate 54.8% is below 80%; skipped, listed, run continues |
| BDL | map-required | 536/1038 (51.6%) | n/a (map path) | clustered-before-ex-date (adjustment problem) | gate-1 pass rate 51.6% is below 80%; skipped, listed, run continues |
| CANBK | map-required | 1043/2429 (42.9%) | n/a (map path) | clustered-before-ex-date (adjustment problem) | gate-1 pass rate 42.9% is below 80%; skipped, listed, run continues |

**Failure-pattern analysis** (the Q-12-addendum ruling: "failures clustered before a CA ex-date (adjustment problem) vs scattered (auction/liquidity shape)"). Every table-path symbol here was first REROUTED through the map path as a second pass -- probes bought it the price oracle the routing rule does not otherwise give a bonus/split-only symbol -- and stayed quarantined anyway.

- **ASTRAL** -- clustered-before-ex-date (adjustment problem). an era fails at 100.0% while the post-last-ex-date era fails at 0.2% -- one wrong factor applied to a whole span, not a market property
  - per-era gate-1 failure rate: < 2019-09-16 729/729 (100.0%); < 2021-03-18 368/375 (98.1%); < 2023-03-14 0/493 (0.0%); >= 2023-03-14 2/833 (0.2%)
- **BDL** -- clustered-before-ex-date (adjustment problem). an era fails at 100.0% while the post-last-ex-date era fails at 0.4% -- one wrong factor applied to a whole span, not a market property
  - per-era gate-1 failure rate: < 2024-05-24 500/500 (100.0%); >= 2024-05-24 2/538 (0.4%)
- **CANBK** -- clustered-before-ex-date (adjustment problem). an era fails at 98.2% while the post-last-ex-date era fails at 0.0% -- one wrong factor applied to a whole span, not a market property
  - per-era gate-1 failure rate: < 2022-06-15 1384/1410 (98.2%); < 2023-06-14 0/247 (0.0%); < 2024-05-15 0/227 (0.0%); < 2024-06-14 0/22 (0.0%); < 2025-06-13 2/247 (0.8%); < 2026-06-12 0/246 (0.0%); >= 2026-06-12 0/30 (0.0%)

### Deferred to the architect: the gate-1 +5.0% ceiling on illiquid names

The Q-12-addendum ruling: "The gate-1 +5.0% ceiling's behavior on illiquid names (auction share of a tiny day can exceed 5%) is EXPLICITLY DEFERRED to the architect's review of the completed run's report -- flag it there with per-symbol evidence; do not tune the band." **The band is untouched** (`[-0.1%, 5.0%]`, byte-identical). This is the evidence, per symbol:

| Symbol | Gate-1 failures | Above +5.0% ceiling | Below -0.1% floor | Median raw daily volume (all days) | Median on the above-ceiling days | Pattern |
|---|---|---|---|---|---|---|
| ASTRAL | 1099 | 369 | 730 | 242,725 | 109,081 | clustered-before-ex-date (adjustment problem) |
| BDL | 502 | 0 | 502 | 977,369 | 0 | clustered-before-ex-date (adjustment problem) |
| CANBK | 1386 | 1290 | 96 | 8,929,560 | 7,202,607 | clustered-before-ex-date (adjustment problem) |

Read it this way: an ABOVE-ceiling failure on a day whose raw daily volume is far below the symbol's own median is the pre-open auction taking more than 5% of a thin day -- a market property, not a data defect. A BELOW-floor failure, or an above-ceiling failure on an ordinary-volume day, is an adjustment problem. No band was moved either way.

### Symbols excluded before ingest

| Symbol | Status | Why |
|---|---|---|
| BAJAJFINSV | map-required-but-unbuildable | map build failed: VendorAdjustmentError: BAJAJFINSV: two price-moving events share an ex-date [datetime.date(2022, 9, 13)]; the map keys eras by ex-date and cannot represent both -- resolve upstream (merge or re-key) before building a map |
| COLPAL | map-required-but-unbuildable | map-required, but no era of its ingest span could be probed (no minute-era trading days); refusing the price-blind factor-table fallback (REVIEW_5A F2) |

## 5. Gate 3 -- adjustment sanity across every share-count ex-date

CONTEXT 4.5 gate 3: on every split/bonus ex-date in the stored span, the ADJUSTED series must show |day-over-day gap| < 20%. Checked on the stored RAW closes with the event's own CONTEXT 4.2 factor applied at the comparison. **36 ex-date(s) checked, 5 failed.**

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
- **Neither ruling widened gate 1's band.** It is still `[-0.1%, 5.0%]`. The +5.0% ceiling's behaviour on illiquid names is DEFERRED to the architect with the per-symbol evidence in section 4.
- **The daily store was verified before the run** (`DailyStore.verify()`, the owed REVIEW_2 F7 check): the oracle is checked before it is trusted.

