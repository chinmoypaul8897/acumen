# Minute backfill report -- chunk 5B (full-universe 1-minute run)

Generated 2026-08-01T05:37:07 from `C:\Users\chinm\acumen\data\universe_backfill\ledger.json` and the stores. Re-runnable at any time; makes no network call.

Scope: CONTEXT 3.1's F&O stock underlyings (CONTEXT 7-E5 -- TODAY's list, with the survivorship disclosure the report owes), 1-minute candles from `2016-10-01` (CONTEXT 4.3 depth floor) or the symbol's listing, whichever is later, to `2026-07-31`.

## 1. Headline

| Measure | Value |
|---|---|
| Universe symbols | 208 |
| Processed | 208 |
| Settled | 202 |
| Quarantined (gate-1 pass rate < 80%) | 6 |
| Not yet processed | 0 |
| Symbol-days gated (settled symbols) | 417,985 |
| Gate-1 PASS (strict band) | 411,271 (98.4%) |
| Gate-1 AUCTION-RELIEF pass (Q-12 addendum 2) | 411 (0.1%) |
| Gate-1 EFFECTIVE pass (strict + relief) | 411,682 (98.5%) |
| Gate-1P PASS (per-day price containment, Q-14) | 409,112 (97.8% of 418,187 stored days) |
| Gate-1P failures with NO raw daily row (Q-14 closes REVIEW_5B Q4) | 208 |
| Gate-2 exclusions | 1,072 |
| Un-provable days (no map era / unknown factor) | 19,872 |
| Vendor application floors resolved (Q-11 addendum 2, Q-14 per-side) | 19 over 228 probe(s) -- the Q-14 pass's probes are STORE reads, not credentialed calls (section 3f) |
| Gate 1 AND gate 2 (overlap-aware) | 411,507 |
| **USABLE symbol-days (gate 1 AND gate 2 AND gate 1P)** | **406,154** |
| **TOTAL coverage** (usable days of every stored symbol-day) | **93.9%** |
| Coverage on gate 1 alone, gated denominator (the pre-Q-14 headline) | 95.2% |
| Coverage on gate 1 alone, STRICT band (no relief) | 95.1% |

**Definition of done (plan.md chunk 5B): >= 95% of symbol-days pass gates.** The architect's Q-14 ruling of 2026-07-28 put GATE 1P in the battery permanently, so "pass gates" now means gate 1 AND gate 2 AND gate 1P, and the honest denominator is every stored symbol-day (a day with no raw daily row is a gate-1P FAILURE, not an absence -- that is what closes REVIEW_5B's finding Q4). Measured: **406,154 of 432,512 = 93.9%**.

> **DoD VERDICT: NOT MET** -- 406,154 of 432,512 stored symbol-days pass gate 1, gate 2 AND gate 1P; 4,733 more passing symbol-days would be needed to reach 95%. Every remaining failure is disclosed in section 4 and in the residual register of section 5.

### 1a. Coverage under every defensible reading (REVIEW_5B section 7, recomputed)

The review tabulated six readings of this chunk's coverage and showed that the only one under which the DoD appeared to miss was the report's OWN arithmetic error (its finding Q3). All six are recomputed here from the same ledger, with the error fixed, and the post-Q-14 reading added as G -- which is the one the verdict above uses.

| Reading | Numerator | Denominator | Coverage | DoD |
|---|---|---|---|---|
| A gate 1 only, gated denominator (the pre-Q-14 headline) | 411,682 | 432,304 | 95.2297% | MET |
| B gate 1 strict, no auction relief | 411,271 | 432,304 | 95.1347% | MET |
| C gate 1 AND gate 2, OVERLAP-AWARE | 411,507 | 432,304 | 95.1893% | MET |
| D gate 1 AND gate 2, the naive subtraction (WRONG -- finding Q3) | 410,610 | 432,304 | 94.9818% | **NOT MET** |
| E gate 1 only, denominator = every stored day | 411,682 | 432,512 | 95.1839% | MET |
| F gate 1 AND gate 2 overlap-aware, stored-day denominator | 411,507 | 432,512 | 95.1435% | MET |
| **G gate 1 AND gate 2 AND GATE 1P, stored-day denominator** | 406,154 | 432,512 | 93.9058% | **NOT MET** |

Reading **D is arithmetically wrong** and is printed only so the correction is visible: it subtracts all 1,072 gate-2 exclusions from the gate-1-passing count, but a gate-2 missing-minutes exclusion can only fire on a day where gate 1 ALSO failed (the completeness ruling), so those days were never in that numerator. Reading C counts the intersection PER DAY instead, and the difference is 897 symbol-days. Reading G is the DoD reading from the Q-14 ruling onward.

## 2. Route classification (QUESTIONS.md Q-11 addendum)

| Route | Symbols | Meaning |
|---|---|---|
| `table-path` | 110 | bonus/split-only: our CONTEXT 4.2 factors ARE the vendor's, and gate-1 volume proves the price division |
| `map-required` | 98 | carries a non-share-count event (rights / special dividend / demerger) or something unparsed: ingested only through a measured map with per-day price containment |

### Map inventory

| Symbol | Eras probed | Provable | Unprobed | Events (kind @ ex-date: price/volume source) |
|---|---|---|---|---|
| ABB | 1 | 1 | 0 | demerger@2019-12-20: measured/price-factor |
| ADANIENT | 3 | 3 | 0 | demerger@2018-04-05: measured/price-factor; demerger@2018-09-06: absent/absent; demerger@2018-09-06: measured/price-factor; rights@2025-11-17: ours/price-factor |
| AMBUJACEM | 2 | 2 | 0 | dividend@2020-11-05: absent/ours; dividend@2022-03-30: absent/ours |
| APLAPOLLO | 2 | 2 | 0 | bonus@2021-09-16: ours/ours; split@2020-12-15: ours/ours |
| ASHOKLEY | 3 | 3 | 0 | bonus@2025-07-16: ours/ours; dividend@2019-07-23: absent/ours; dividend@2024-04-03: absent/ours |
| ASTRAL | 3 | 3 | 0 | bonus@2019-09-16: ours/ours; bonus@2021-03-18: ours/ours; bonus@2023-03-14: absent/absent; bonus@2023-03-14: ours/ours |
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
| CANBK | 7 | 7 | 0 | dividend@2022-06-15: absent/ours; dividend@2023-06-14: absent/ours; dividend@2024-06-14: absent/ours; dividend@2025-06-13: absent/ours; dividend@2026-06-12: absent/ours; rights@2017-02-17: measured/price-factor; split@2024-05-15: absent/absent; split@2024-05-15: ours/ours |
| CDSL | 2 | 2 | 0 | bonus@2024-08-23: ours/ours; dividend@2019-09-06: absent/ours |
| COALINDIA | 15 | 15 | 0 | dividend@2017-03-14: absent/ours; dividend@2018-03-16: absent/ours; dividend@2018-12-28: absent/ours; dividend@2019-03-22: absent/ours; dividend@2020-03-19: absent/ours; dividend@2020-11-19: absent/ours; dividend@2021-03-15: absent/ours; dividend@2021-09-02: absent/ours; dividend@2021-12-06: absent/ours; dividend@2022-02-21: absent/ours; dividend@2022-11-15: absent/ours; dividend@2023-02-08: absent/ours; dividend@2023-11-21: absent/ours; dividend@2024-11-05: absent/ours; dividend@2025-11-04: absent/ours |
| COCHINSHIP | 6 | 6 | 0 | dividend@2018-08-06: absent/ours; dividend@2019-08-05: absent/ours; dividend@2020-09-21: absent/ours; dividend@2021-01-13: absent/ours; dividend@2022-02-21: absent/ours; split@2024-01-10: absent/absent; split@2024-01-10: ours/ours |
| COLPAL | 2 | 2 | 0 | unparsed@2017-12-18: absent/measured; unparsed@2019-04-05: absent/measured |
| DIXON | 1 | 1 | 0 | split@2021-03-18: ours/ours |
| GAIL | 12 | 10 | 0 | bonus@2019-07-09: ours/ours; bonus@2022-09-06: ours/ours; dividend@2020-02-17: absent/ours; dividend@2021-12-30: absent/ours; dividend@2022-03-21: absent/ours; dividend@2023-03-21: absent/ours; dividend@2024-02-06: absent/ours; dividend@2025-02-07: absent/ours; dividend@2026-02-05: absent/ours; unparsed@2019-08-08: absent/measured |
| GODFRYPHLP | 5 | 5 | 0 | bonus@2025-09-16: ours/ours; dividend@2020-03-17: absent/ours; dividend@2021-07-28: absent/ours; dividend@2022-08-11: absent/ours; dividend@2023-08-11: absent/ours |
| GRASIM | 3 | 3 | 0 | demerger@2017-07-19: measured/price-factor; rights@2024-01-10: ours/price-factor; split@2016-10-06: ours/ours |
| HAL | 3 | 3 | 0 | dividend@2019-03-28: absent/ours; dividend@2020-03-23: absent/ours; split@2023-09-28: absent/absent; split@2023-09-28: ours/ours |
| HCLTECH | 2 | 2 | 0 | bonus@2019-12-05: ours/ours; unparsed@2018-08-02: absent/measured |
| HDFCAMC | 4 | 4 | 0 | bonus@2025-11-26: ours/ours; dividend@2022-06-09: absent/ours; dividend@2023-06-09: absent/ours; dividend@2026-06-05: absent/ours |
| HDFCBANK | 2 | 2 | 0 | bonus@2025-08-26: ours/ours; split@2019-09-19: ours/ours |
| HEROMOTOCO | 5 | 5 | 0 | dividend@2020-02-17: absent/ours; dividend@2022-02-21: absent/ours; dividend@2023-02-17: absent/ours; dividend@2024-02-21: absent/ours; dividend@2025-02-12: absent/ours |
| HINDPETRO | 12 | 8 | 0 | bonus@2024-06-21: ours/ours; dividend@2019-02-14: absent/ours; dividend@2019-06-06: absent/absent; dividend@2020-07-02: absent/ours; dividend@2021-07-08: absent/ours; dividend@2022-08-22: absent/ours; dividend@2024-02-07: absent/ours; dividend@2024-08-09: absent/ours; dividend@2025-08-14: absent/ours |
| HINDUNILVR | 1 | 1 | 0 | demerger@2025-12-05: absent/absent |
| HINDZINC | 11 | 1 | 0 | dividend@2024-08-28: absent/ours |
| IDEA | 1 | 1 | 0 | rights@2019-03-29: measured/price-factor |
| IEX | 2 | 1 | 0 | bonus@2021-12-03: absent/absent; split@2018-10-19: ours/ours |
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
| NESTLEIND | 3 | 3 | 0 | bonus@2025-08-08: ours/ours; split@2024-01-05: absent/absent; split@2024-01-05: ours/ours; unparsed@2020-10-29: absent/measured |
| NHPC | 8 | 8 | 0 | dividend@2017-01-19: absent/ours; dividend@2018-02-20: absent/ours; dividend@2019-09-12: absent/ours; dividend@2020-02-17: absent/ours; dividend@2021-02-22: absent/ours; dividend@2022-02-22: absent/ours; dividend@2023-02-17: absent/ours; unparsed@2019-02-18: absent/measured |
| NMDC | 14 | 12 | 0 | bonus@2024-12-27: ours/ours; demerger@2022-10-27: measured/measured; dividend@2019-03-22: absent/ours; dividend@2020-02-18: absent/ours; dividend@2021-03-22: absent/ours; dividend@2021-12-14: absent/ours; dividend@2022-02-17: absent/ours; dividend@2023-02-24: absent/ours; dividend@2023-08-31: absent/ours; dividend@2024-02-27: absent/ours; dividend@2025-03-21: absent/ours; dividend@2026-02-13: absent/ours |
| NTPC | 8 | 7 | 0 | bonus@2019-03-19: ours/ours; dividend@2019-08-13: absent/ours; dividend@2020-08-13: absent/ours; dividend@2021-02-11: absent/ours; dividend@2021-09-08: absent/ours; dividend@2022-02-03: absent/ours; dividend@2023-02-03: absent/ours |
| NYKAA | 1 | 1 | 0 | bonus@2022-11-10: ours/measured |
| OFSS | 9 | 9 | 0 | dividend@2017-04-19: absent/ours; dividend@2018-08-06: absent/ours; dividend@2020-05-19: absent/ours; dividend@2021-05-17: absent/ours; dividend@2022-05-13: absent/ours; dividend@2023-05-09: absent/ours; dividend@2024-05-07: absent/ours; dividend@2025-05-08: absent/ours; dividend@2026-05-07: absent/ours |
| OIL | 12 | 8 | 0 | bonus@2024-07-02: ours/ours; dividend@2019-02-21: absent/ours; dividend@2020-02-20: absent/ours; dividend@2021-02-23: absent/ours; dividend@2022-02-22: absent/ours; dividend@2022-09-15: absent/ours; dividend@2022-11-21: absent/ours; dividend@2023-02-22: absent/ours |
| ONGC | 11 | 11 | 0 | bonus@2016-12-15: ours/ours; dividend@2019-02-28: absent/ours; dividend@2020-03-23: absent/ours; dividend@2021-11-22: absent/ours; dividend@2022-08-18: absent/ours; dividend@2022-11-21: absent/ours; dividend@2023-02-24: absent/ours; dividend@2023-11-21: absent/ours; dividend@2024-11-19: absent/ours; dividend@2025-11-14: absent/ours; dividend@2026-02-18: absent/ours |
| PERSISTENT | 1 | 1 | 0 | split@2024-03-28: ours/ours |
| PETRONET | 10 | 2 | 0 | dividend@2024-11-08: absent/ours; dividend@2025-11-14: absent/ours |
| PFC | 9 | 9 | 0 | bonus@2023-09-21: absent/absent; bonus@2023-09-21: ours/ours; dividend@2017-03-30: absent/ours; dividend@2017-11-10: absent/ours; dividend@2020-02-28: absent/ours; dividend@2021-03-19: absent/ours; dividend@2022-02-25: absent/ours; dividend@2022-11-24: absent/ours; dividend@2023-02-24: absent/ours; dividend@2023-06-16: absent/ours |
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
| ULTRACEMCO | 1 | 0 | 0 | - |
| UNIONBANK | 5 | 3 | 0 | dividend@2024-07-19: absent/ours; dividend@2025-07-25: absent/ours; dividend@2026-07-03: absent/ours |
| UPL | 2 | 1 | 0 | rights@2024-11-26: ours/price-factor |
| VBL | 5 | 3 | 0 | bonus@2022-06-06: ours/ours; split@2023-06-15: ours/ours; split@2024-09-12: ours/ours |
| VEDL | 19 | 17 | 0 | demerger@2026-04-30: measured/price-factor; dividend@2017-04-11: absent/ours; dividend@2018-03-20: absent/ours; dividend@2018-11-06: absent/absent; dividend@2020-03-05: absent/ours; dividend@2020-10-28: absent/ours; dividend@2021-09-08: absent/ours; dividend@2021-12-17: absent/ours; dividend@2022-05-06: absent/ours; dividend@2022-07-26: absent/ours; dividend@2022-11-29: absent/ours; dividend@2023-02-03: absent/ours; dividend@2023-04-06: absent/ours; dividend@2023-05-30: absent/ours; dividend@2023-12-27: absent/absent; dividend@2024-05-24: absent/ours; dividend@2024-09-10: absent/ours; dividend@2025-08-26: absent/ours; unparsed@2022-03-09: absent/measured |
| WIPRO | 4 | 4 | 0 | bonus@2017-06-13: ours/ours; bonus@2019-03-06: ours/ours; bonus@2024-12-03: ours/ours; dividend@2026-01-27: absent/ours |

Per-event factor sources across every committed map, PRICE side -- **ours 73**, **measured 15**, **absent 282**. `ours` = our exact CONTEXT 4.2 factor matched the vendor; `measured` = the vendor used a factor we had to observe; `absent` = the vendor did not apply the event in that era.

VOLUME side -- **ours 309**, **price-factor 18**, **measured 28**, **absent 15**. The Q-12 ruling's candidate order is `ours(share-count) > chosen-price-factor > measured-minimum > absent`: `price-factor` means the event's volume was reconciled by the very factor the PRICE oracle had already pinned to 2 paise per probe day, which is strictly better evidenced than an observed volume ratio the pre-open auction biases upward. `measured` on this side is now the MINIMUM over the price-passing probe days, never the median.

## 3. Depth found, per symbol

| Symbol | Route | Clamp | First 1-min day | Days | Windows p/e/x | Gate-1 (strict) | Relief | Gate-1 (effective) | Floors | Gate-2 excl | Avg min/day | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 360ONE | table-path | 2023-01-23 | 2023-01-23 | 872 | 46/0/0 | 862/871 (99.0%) | 3 | 865/871 (99.3%) | - | 1 | 363.7 | settled |
| ABB | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2418/2433 (99.4%) | 2 | 2420/2433 (99.5%) | - | 9 | 351.0 | settled |
| ABCAPITAL | table-path | 2017-09-01 | 2017-09-01 | 2207 | 117/0/0 | 2191/2206 (99.3%) | 0 | 2191/2206 (99.3%) | - | 2 | 372.7 | settled |
| ADANIENSOL | table-path | 2023-08-24 | 2023-08-24 | 728 | 39/0/0 | 725/727 (99.7%) | 1 | 726/727 (99.9%) | - | 1 | 372.9 | settled |
| ADANIENT | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2404/2433 (98.8%) | 13 | 2417/2433 (99.3%) | - | 2 | 372.7 | settled |
| ADANIGREEN | table-path | 2018-06-18 | 2018-06-18 | 2010 | 106/0/0 | 1994/2009 (99.3%) | 2 | 1996/2009 (99.4%) | - | 9 | 362.8 | settled |
| ADANIPORTS | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2414/2433 (99.2%) | 1 | 2415/2433 (99.3%) | - | 2 | 373.3 | settled |
| ADANIPOWER | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2405/2433 (98.8%) | 8 | 2413/2433 (99.2%) | - | 2 | 372.4 | settled |
| ALKEM | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2419/2433 (99.4%) | 0 | 2419/2433 (99.4%) | - | 10 | 343.9 | settled |
| AMBER | table-path | 2018-01-30 | 2018-01-30 | 2104 | 111/0/0 | 2086/2103 (99.2%) | 1 | 2087/2103 (99.2%) | - | 12 | 327.4 | settled |
| AMBUJACEM | map-required | 2016-10-01 | 2016-10-03 | 2433 | 129/0/0 | 2417/2432 (99.4%) | 1 | 2418/2432 (99.4%) | - | 2 | 373.1 | settled |
| ANGELONE | table-path | 2021-11-11 | 2021-11-11 | 1171 | 62/0/0 | 1167/1170 (99.7%) | 0 | 1167/1170 (99.7%) | - | 1 | 373.1 | settled |
| APLAPOLLO | map-required | 2016-10-01 | 2016-10-03 | 2436 | 129/0/0 | 1896/2435 (77.9%) | 0 | 1896/2435 (77.9%) | 0 | 524 | 314.1 | quarantined |
| APOLLOHOSP | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2419/2433 (99.4%) | 1 | 2420/2433 (99.5%) | - | 2 | 372.0 | settled |
| ASHOKLEY | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2420/2433 (99.5%) | 0 | 2420/2433 (99.5%) | - | 2 | 373.3 | settled |
| ASIANPAINT | table-path | 2016-10-01 | 2016-10-03 | 2435 | 129/0/0 | 2421/2434 (99.5%) | 1 | 2422/2434 (99.5%) | - | 2 | 373.3 | settled |
| ASTRAL | map-required | 2016-10-01 | 2016-10-03 | 2435 | 129/0/0 | 1702/2434 (69.9%) | 1 | 1703/2434 (70.0%) | 1 | 636 | 332.8 | quarantined |
| AUBANK | map-required | 2017-07-10 | 2017-07-10 | 2245 | 119/0/0 | 2239/2244 (99.8%) | 0 | 2239/2244 (99.8%) | 0 | 2 | 365.6 | settled |
| AUROPHARMA | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2419/2433 (99.4%) | 0 | 2419/2433 (99.4%) | - | 2 | 373.2 | settled |
| AXISBANK | table-path | 2016-10-01 | 2016-10-03 | 2433 | 129/0/0 | 2414/2432 (99.3%) | 3 | 2417/2432 (99.4%) | - | 2 | 373.3 | settled |
| BAJAJ-AUTO | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2419/2433 (99.4%) | 0 | 2419/2433 (99.4%) | - | 2 | 373.0 | settled |
| BAJAJFINSV | map-required | 2016-10-01 | 2016-10-03 | 2436 | 129/0/0 | 2421/2435 (99.4%) | 0 | 2421/2435 (99.4%) | 0 | 2 | 372.4 | settled |
| BAJAJHLDNG | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2410/2433 (99.1%) | 1 | 2411/2433 (99.1%) | - | 19 | 315.0 | settled |
| BAJFINANCE | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2414/2433 (99.2%) | 2 | 2416/2433 (99.3%) | - | 2 | 373.2 | settled |
| BANDHANBNK | table-path | 2018-03-27 | 2018-03-27 | 2066 | 109/0/0 | 2050/2065 (99.3%) | 2 | 2052/2065 (99.4%) | - | 3 | 373.1 | settled |
| BANKBARODA | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2420/2433 (99.5%) | 0 | 2420/2433 (99.5%) | - | 2 | 373.3 | settled |
| BANKINDIA | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2418/2433 (99.4%) | 1 | 2419/2433 (99.4%) | - | 2 | 372.6 | settled |
| BDL | map-required | 2018-03-23 | 2022-05-19 | 1043 | 56/54/0 | 1039/1042 (99.7%) | 0 | 1039/1042 (99.7%) | - | 1 | 372.9 | settled |
| BEL | map-required | 2016-10-01 | 2016-10-03 | 2436 | 129/0/0 | 2177/2435 (89.4%) | 0 | 2177/2435 (89.4%) | 0 | 13 | 373.1 | settled |
| BHARATFORG | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2420/2433 (99.5%) | 0 | 2420/2433 (99.5%) | - | 2 | 372.9 | settled |
| BHARTIARTL | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2408/2433 (99.0%) | 8 | 2416/2433 (99.3%) | - | 2 | 373.2 | settled |
| BHEL | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2420/2433 (99.5%) | 0 | 2420/2433 (99.5%) | - | 2 | 373.3 | settled |
| BIOCON | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2420/2433 (99.5%) | 0 | 2420/2433 (99.5%) | - | 2 | 373.0 | settled |
| BLUESTARCO | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2413/2433 (99.2%) | 1 | 2414/2433 (99.2%) | 1 | 16 | 321.1 | settled |
| BOSCHLTD | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2412/2433 (99.1%) | 0 | 2412/2433 (99.1%) | - | 12 | 357.2 | settled |
| BPCL | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2227/2433 (91.5%) | 0 | 2227/2433 (91.5%) | 0 | 4 | 373.3 | settled |
| BRITANNIA | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2415/2433 (99.3%) | 3 | 2418/2433 (99.4%) | - | 3 | 372.7 | settled |
| BSE | map-required | 2017-02-03 | 2017-02-03 | 2350 | 124/0/0 | 2199/2349 (93.6%) | 0 | 2199/2349 (93.6%) | 0 | 54 | 365.1 | settled |
| CAMS | map-required | 2020-10-05 | 2020-10-05 | 1443 | 76/0/0 | 1440/1442 (99.9%) | 0 | 1440/1442 (99.9%) | - | 1 | 372.2 | settled |
| CANBK | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2418/2433 (99.4%) | 0 | 2418/2433 (99.4%) | 1 | 2 | 373.2 | settled |
| CDSL | map-required | 2017-06-30 | 2017-06-30 | 2249 | 119/0/0 | 2232/2248 (99.3%) | 2 | 2234/2248 (99.4%) | - | 9 | 364.3 | settled |
| CGPOWER | table-path | 2017-03-08 | 2017-03-08 | 2326 | 123/0/0 | 2306/2325 (99.2%) | 4 | 2310/2325 (99.4%) | - | 3 | 356.2 | settled |
| CHOLAFIN | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 2 | 2419/2433 (99.4%) | - | 2 | 368.3 | settled |
| CIPLA | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2418/2433 (99.4%) | 2 | 2420/2433 (99.5%) | - | 2 | 373.2 | settled |
| COALINDIA | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2419/2433 (99.4%) | 1 | 2420/2433 (99.5%) | - | 2 | 373.3 | settled |
| COCHINSHIP | map-required | 2017-08-11 | 2017-08-11 | 2220 | 118/0/0 | 2201/2219 (99.2%) | 1 | 2202/2219 (99.2%) | 1 | 10 | 350.0 | settled |
| COFORGE | table-path | 2020-08-20 | 2020-08-20 | 1474 | 78/0/0 | 1467/1473 (99.6%) | 1 | 1468/1473 (99.7%) | - | 2 | 373.0 | settled |
| COLPAL | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 1 | 2418/2433 (99.4%) | - | 3 | 370.4 | settled |
| CONCOR | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2420/2433 (99.5%) | 1 | 2421/2433 (99.5%) | - | 3 | 370.9 | settled |
| CROMPTON | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 2 | 2419/2433 (99.4%) | - | 4 | 367.4 | settled |
| CUMMINSIND | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 2 | 2419/2433 (99.4%) | - | 4 | 368.0 | settled |
| DABUR | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 3 | 2420/2433 (99.5%) | - | 2 | 372.7 | settled |
| DALBHARAT | table-path | 2019-01-22 | 2019-01-22 | 1862 | 99/0/0 | 1851/1861 (99.5%) | 0 | 1851/1861 (99.5%) | - | 5 | 350.6 | settled |
| DELHIVERY | table-path | 2022-05-24 | 2022-05-24 | 1040 | 55/0/0 | 1035/1039 (99.6%) | 0 | 1035/1039 (99.6%) | - | 1 | 370.5 | settled |
| DIVISLAB | table-path | 2016-10-01 | 2016-10-03 | 2433 | 129/0/0 | 2416/2432 (99.3%) | 0 | 2416/2432 (99.3%) | - | 3 | 372.8 | settled |
| DIXON | map-required | 2017-09-18 | 2017-09-18 | 2197 | 116/0/0 | 2173/2196 (99.0%) | 0 | 2173/2196 (99.0%) | 1 | 18 | 343.3 | settled |
| DLF | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2410/2433 (99.1%) | 7 | 2417/2433 (99.3%) | - | 2 | 373.3 | settled |
| DMART | table-path | 2017-03-21 | 2017-03-21 | 2318 | 123/0/0 | 2300/2317 (99.3%) | 2 | 2302/2317 (99.4%) | - | 3 | 373.2 | settled |
| DRREDDY | table-path | 2016-10-01 | 2016-10-03 | 2435 | 129/0/0 | 2422/2434 (99.5%) | 0 | 2422/2434 (99.5%) | - | 2 | 373.2 | settled |
| EICHERMOT | table-path | 2016-10-01 | 2016-10-03 | 2433 | 129/0/0 | 2413/2432 (99.2%) | 3 | 2416/2432 (99.3%) | - | 5 | 373.0 | settled |
| ETERNAL | table-path | 2025-04-09 | 2025-04-09 | 324 | 18/0/0 | 323/323 (100.0%) | 0 | 323/323 (100.0%) | - | 0 | 374.0 | settled |
| FEDERALBNK | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2419/2433 (99.4%) | 1 | 2420/2433 (99.5%) | - | 2 | 373.2 | settled |
| FORCEMOT | table-path | 2019-08-19 | 2019-08-19 | 1647 | 88/3/0 | 1618/1646 (98.3%) | 8 | 1626/1646 (98.8%) | - | 17 | 317.7 | settled |
| FORTIS | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2414/2433 (99.2%) | 3 | 2417/2433 (99.3%) | - | 11 | 362.9 | settled |
| GAIL | map-required | 2016-10-01 | 2016-10-03 | 2436 | 129/0/0 | 1994/2435 (81.9%) | 0 | 1994/2435 (81.9%) | 0 | 3 | 373.2 | settled |
| GLENMARK | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2418/2433 (99.4%) | 2 | 2420/2433 (99.5%) | - | 3 | 372.1 | settled |
| GMRAIRPORT | table-path | 2024-12-11 | 2024-12-11 | 406 | 22/0/0 | 404/405 (99.8%) | 0 | 404/405 (99.8%) | - | 0 | 374.2 | settled |
| GODFRYPHLP | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 1 | 2418/2433 (99.4%) | - | 14 | 327.7 | settled |
| GODREJCP | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2414/2433 (99.2%) | 2 | 2416/2433 (99.3%) | - | 3 | 372.5 | settled |
| GODREJPROP | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2415/2433 (99.3%) | 1 | 2416/2433 (99.3%) | - | 11 | 358.3 | settled |
| GRASIM | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 1 | 2418/2433 (99.4%) | 0 | 3 | 373.0 | settled |
| GVT&D | table-path | 2024-11-05 | 2024-11-05 | 430 | 23/0/0 | 418/429 (97.4%) | 3 | 421/429 (98.1%) | - | 4 | 373.1 | settled |
| HAL | map-required | 2018-03-28 | 2018-03-28 | 2065 | 109/0/0 | 2051/2064 (99.4%) | 1 | 2052/2064 (99.4%) | 1 | 10 | 341.5 | settled |
| HAVELLS | table-path | 2016-10-01 | 2016-10-03 | 2435 | 129/0/0 | 2419/2434 (99.4%) | 0 | 2419/2434 (99.4%) | - | 3 | 373.0 | settled |
| HCLTECH | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2416/2433 (99.3%) | 1 | 2417/2433 (99.3%) | - | 4 | 373.2 | settled |
| HDFCAMC | map-required | 2018-08-06 | 2018-08-06 | 1974 | 105/0/0 | 1961/1973 (99.4%) | 0 | 1961/1973 (99.4%) | - | 2 | 372.7 | settled |
| HDFCBANK | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2334/2433 (95.9%) | 43 | 2377/2433 (97.7%) | 0 | 3 | 373.2 | settled |
| HDFCLIFE | table-path | 2017-11-17 | 2017-11-17 | 2154 | 114/0/0 | 2136/2153 (99.2%) | 3 | 2139/2153 (99.3%) | - | 2 | 373.3 | settled |
| HEROMOTOCO | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 1 | 2418/2433 (99.4%) | - | 4 | 373.2 | settled |
| HINDALCO | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2416/2433 (99.3%) | 0 | 2416/2433 (99.3%) | - | 4 | 373.2 | settled |
| HINDPETRO | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 1999/2433 (82.2%) | 0 | 1999/2433 (82.2%) | 1 | 5 | 373.2 | settled |
| HINDUNILVR | map-required | 2016-10-01 | 2016-10-03 | 2435 | 129/0/0 | 2420/2434 (99.4%) | 0 | 2420/2434 (99.4%) | - | 3 | 373.2 | settled |
| HINDZINC | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 1 | 2418/2433 (99.4%) | - | 5 | 370.8 | settled |
| HYUNDAI | table-path | 2024-10-22 | 2024-10-22 | 440 | 24/0/0 | 437/439 (99.5%) | 1 | 438/439 (99.8%) | - | 1 | 373.4 | settled |
| ICICIBANK | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2399/2433 (98.6%) | 10 | 2409/2433 (99.0%) | - | 5 | 373.2 | settled |
| ICICIGI | table-path | 2017-09-27 | 2017-09-27 | 2188 | 116/0/0 | 2170/2187 (99.2%) | 1 | 2171/2187 (99.3%) | - | 4 | 370.2 | settled |
| ICICIPRULI | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2416/2433 (99.3%) | 2 | 2418/2433 (99.4%) | - | 3 | 372.7 | settled |
| IDEA | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2410/2433 (99.1%) | 3 | 2413/2433 (99.2%) | - | 5 | 372.9 | settled |
| IDFCFIRSTB | table-path | 2019-01-16 | 2019-01-16 | 1867 | 99/0/0 | 1860/1866 (99.7%) | 0 | 1860/1866 (99.7%) | - | 1 | 373.4 | settled |
| IEX | map-required | 2017-10-23 | 2017-10-23 | 2174 | 115/0/0 | 1152/2173 (53.0%) | 1 | 1153/2173 (53.1%) | 1 | 577 | 337.6 | quarantined |
| INDHOTEL | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2418/2433 (99.4%) | 2 | 2420/2433 (99.5%) | - | 5 | 363.8 | settled |
| INDIANB | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2418/2433 (99.4%) | 0 | 2418/2433 (99.4%) | - | 2 | 370.5 | settled |
| INDIGO | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2412/2433 (99.1%) | 2 | 2414/2433 (99.2%) | - | 2 | 371.1 | settled |
| INDUSINDBK | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2416/2433 (99.3%) | 2 | 2418/2433 (99.4%) | - | 3 | 373.2 | settled |
| INDUSTOWER | map-required | 2020-12-18 | 2020-12-18 | 1391 | 74/0/0 | 1388/1390 (99.9%) | 0 | 1388/1390 (99.9%) | - | 1 | 373.3 | settled |
| INFY | map-required | 2016-10-01 | 2016-10-03 | 2435 | 129/0/0 | 2414/2434 (99.2%) | 3 | 2417/2434 (99.3%) | - | 4 | 373.2 | settled |
| INOXWIND | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2408/2433 (99.0%) | 6 | 2414/2433 (99.2%) | 1 | 16 | 300.3 | settled |
| IOC | map-required | 2016-10-01 | 2016-10-03 | 2436 | 129/0/0 | 2066/2435 (84.8%) | 0 | 2066/2435 (84.8%) | 0 | 4 | 373.2 | settled |
| IREDA | table-path | 2023-11-29 | 2023-11-29 | 663 | 35/0/0 | 647/662 (97.7%) | 6 | 653/662 (98.6%) | - | 1 | 373.2 | settled |
| IRFC | map-required | 2021-01-29 | 2021-01-29 | 1363 | 72/0/0 | 1360/1362 (99.9%) | 0 | 1360/1362 (99.9%) | - | 2 | 373.5 | settled |
| ITC | map-required | 2016-10-01 | 2016-10-03 | 2433 | 129/0/0 | 2415/2432 (99.3%) | 1 | 2416/2432 (99.3%) | - | 4 | 373.2 | settled |
| JINDALSTEL | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 0 | 2417/2433 (99.3%) | - | 3 | 373.2 | settled |
| JIOFIN | table-path | 2023-08-21 | 2023-08-21 | 728 | 39/0/0 | 721/727 (99.2%) | 2 | 723/727 (99.4%) | - | 2 | 373.4 | settled |
| JSWENERGY | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2410/2433 (99.1%) | 5 | 2415/2433 (99.3%) | - | 11 | 362.6 | settled |
| JSWSTEEL | map-required | 2016-10-01 | 2016-10-03 | 2435 | 129/0/0 | 2421/2434 (99.5%) | 0 | 2421/2434 (99.5%) | - | 3 | 373.2 | settled |
| JUBLFOOD | map-required | 2016-10-01 | 2016-10-03 | 2436 | 129/0/0 | 2097/2435 (86.1%) | 1 | 2098/2435 (86.2%) | 1 | 17 | 372.8 | settled |
| KALYANKJIL | table-path | 2021-03-26 | 2021-03-26 | 1324 | 70/0/0 | 1320/1323 (99.8%) | 0 | 1320/1323 (99.8%) | - | 1 | 370.7 | settled |
| KAYNES | table-path | 2022-11-22 | 2022-11-22 | 916 | 49/0/0 | 912/915 (99.7%) | 1 | 913/915 (99.8%) | - | 2 | 369.6 | settled |
| KEI | table-path | 2016-10-01 | 2016-10-03 | 2433 | 129/0/0 | 2413/2432 (99.2%) | 4 | 2417/2432 (99.4%) | - | 10 | 354.2 | settled |
| KFINTECH | table-path | 2022-12-29 | 2022-12-29 | 889 | 47/0/0 | 882/888 (99.3%) | 0 | 882/888 (99.3%) | - | 1 | 365.0 | settled |
| KOTAKBANK | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2414/2433 (99.2%) | 3 | 2417/2433 (99.3%) | - | 2 | 373.3 | settled |
| KPITTECH | table-path | 2019-04-22 | 2019-04-22 | 1803 | 95/0/0 | 1798/1802 (99.8%) | 1 | 1799/1802 (99.8%) | - | 1 | 358.4 | settled |
| LAURUSLABS | table-path | 2016-12-19 | 2016-12-19 | 2381 | 126/0/0 | 2362/2380 (99.2%) | 4 | 2366/2380 (99.4%) | - | 12 | 329.8 | settled |
| LICHSGFIN | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2420/2433 (99.5%) | 0 | 2420/2433 (99.5%) | - | 2 | 373.0 | settled |
| LICI | map-required | 2022-05-17 | 2022-05-17 | 1045 | 55/0/0 | 1043/1044 (99.9%) | 0 | 1043/1044 (99.9%) | - | 1 | 373.2 | settled |
| LODHA | map-required | 2021-04-19 | 2021-04-19 | 1312 | 69/0/0 | 1280/1311 (97.6%) | 2 | 1282/1311 (97.8%) | 0 | 6 | 367.7 | settled |
| LT | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2419/2433 (99.4%) | 0 | 2419/2433 (99.4%) | - | 2 | 373.3 | settled |
| LTF | table-path | 2024-04-23 | 2024-04-23 | 565 | 30/0/0 | 563/564 (99.8%) | 0 | 563/564 (99.8%) | - | 0 | 373.4 | settled |
| LTM | table-path | 2026-02-27 | 2026-02-27 | 103 | 6/0/0 | 102/102 (100.0%) | 0 | 102/102 (100.0%) | - | 0 | 374.9 | settled |
| LUPIN | table-path | 2016-10-01 | 2016-10-03 | 2433 | 129/0/0 | 2417/2432 (99.4%) | 1 | 2418/2432 (99.4%) | - | 2 | 373.1 | settled |
| M&M | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2414/2433 (99.2%) | 4 | 2418/2433 (99.4%) | - | 2 | 373.3 | settled |
| MANAPPURAM | table-path | 2016-10-01 | 2016-10-03 | 2435 | 129/0/0 | 2417/2434 (99.3%) | 5 | 2422/2434 (99.5%) | - | 2 | 372.8 | settled |
| MANKIND | table-path | 2023-05-09 | 2023-05-09 | 803 | 43/0/0 | 794/802 (99.0%) | 0 | 794/802 (99.0%) | - | 3 | 372.3 | settled |
| MARICO | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2421/2433 (99.5%) | 0 | 2421/2433 (99.5%) | - | 2 | 372.3 | settled |
| MARUTI | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2419/2433 (99.4%) | 0 | 2419/2433 (99.4%) | - | 3 | 373.3 | settled |
| MAXHEALTH | table-path | 2020-08-21 | 2020-08-21 | 1473 | 78/0/0 | 1465/1472 (99.5%) | 2 | 1467/1472 (99.7%) | - | 2 | 369.3 | settled |
| MAZDOCK | map-required | 2020-10-12 | 2020-10-12 | 1438 | 76/0/0 | 1434/1437 (99.8%) | 0 | 1434/1437 (99.8%) | - | 2 | 367.2 | settled |
| MCX | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 2 | 2419/2433 (99.4%) | - | 4 | 370.2 | settled |
| MFSL | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 2 | 2419/2433 (99.4%) | - | 3 | 368.9 | settled |
| MOTHERSON | map-required | 2022-06-09 | 2022-06-09 | 1028 | 55/0/0 | 1024/1027 (99.7%) | 0 | 1024/1027 (99.7%) | - | 2 | 373.3 | settled |
| MOTILALOFS | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2410/2433 (99.1%) | 3 | 2413/2433 (99.2%) | 1 | 13 | 339.2 | settled |
| MPHASIS | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 1 | 2418/2433 (99.4%) | - | 2 | 359.9 | settled |
| MUTHOOTFIN | map-required | 2016-10-01 | 2016-10-03 | 2433 | 129/0/0 | 2416/2432 (99.3%) | 1 | 2417/2432 (99.4%) | - | 3 | 370.3 | settled |
| NAM-INDIA | map-required | 2020-01-23 | 2020-01-23 | 1617 | 86/0/0 | 1614/1616 (99.9%) | 0 | 1614/1616 (99.9%) | - | 1 | 369.4 | settled |
| NATIONALUM | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2418/2433 (99.4%) | 1 | 2419/2433 (99.4%) | - | 2 | 371.6 | settled |
| NAUKRI | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2414/2433 (99.2%) | 3 | 2417/2433 (99.3%) | - | 10 | 349.3 | settled |
| NBCC | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2416/2433 (99.3%) | 3 | 2419/2433 (99.4%) | - | 3 | 372.6 | settled |
| NESTLEIND | map-required | 2016-10-01 | 2016-10-03 | 2435 | 129/0/0 | 2393/2434 (98.3%) | 0 | 2393/2434 (98.3%) | 1 | 4 | 367.1 | settled |
| NHPC | map-required | 2016-10-01 | 2016-10-03 | 2433 | 129/0/0 | 2415/2432 (99.3%) | 4 | 2419/2432 (99.5%) | - | 6 | 368.3 | settled |
| NMDC | map-required | 2016-10-01 | 2016-10-03 | 2436 | 129/0/0 | 2053/2435 (84.3%) | 4 | 2057/2435 (84.5%) | 0 | 6 | 372.8 | settled |
| NTPC | map-required | 2016-10-01 | 2016-10-03 | 2433 | 129/0/0 | 1844/2432 (75.8%) | 1 | 1845/2432 (75.9%) | 1 | 5 | 373.2 | quarantined |
| NYKAA | map-required | 2021-11-10 | 2021-11-10 | 1172 | 62/0/0 | 1166/1171 (99.6%) | 3 | 1169/1171 (99.8%) | - | 2 | 373.4 | settled |
| OBEROIRLTY | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2398/2433 (98.6%) | 17 | 2415/2433 (99.3%) | - | 6 | 358.7 | settled |
| OFSS | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2416/2433 (99.3%) | 1 | 2417/2433 (99.3%) | - | 12 | 340.3 | settled |
| OIL | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2052/2433 (84.3%) | 0 | 2052/2433 (84.3%) | 0 | 129 | 368.1 | settled |
| ONGC | map-required | 2016-10-01 | 2016-10-03 | 2436 | 129/0/0 | 2423/2435 (99.5%) | 0 | 2423/2435 (99.5%) | - | 1 | 373.3 | settled |
| PAGEIND | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2406/2433 (98.9%) | 1 | 2407/2433 (98.9%) | - | 11 | 358.6 | settled |
| PATANJALI | table-path | 2022-07-13 | 2022-07-13 | 858 | 47/6/0 | 838/857 (97.8%) | 7 | 845/857 (98.6%) | - | 4 | 368.0 | settled |
| PAYTM | table-path | 2021-11-18 | 2021-11-18 | 1166 | 62/0/0 | 1144/1165 (98.2%) | 9 | 1153/1165 (99.0%) | - | 1 | 373.4 | settled |
| PERSISTENT | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2415/2433 (99.3%) | 0 | 2415/2433 (99.3%) | 1 | 6 | 355.9 | settled |
| PETRONET | map-required | 2016-10-01 | 2016-10-03 | 2436 | 129/0/0 | 2236/2435 (91.8%) | 2 | 2238/2435 (91.9%) | 0 | 2 | 373.0 | settled |
| PFC | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2420/2433 (99.5%) | 0 | 2420/2433 (99.5%) | 1 | 2 | 373.2 | settled |
| PGEL | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2364/2433 (97.2%) | 18 | 2382/2433 (97.9%) | 0 | 49 | 231.6 | settled |
| PHOENIXLTD | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2411/2433 (99.1%) | 2 | 2413/2433 (99.2%) | - | 13 | 324.5 | settled |
| PIDILITIND | table-path | 2016-10-01 | 2016-10-03 | 2436 | 129/0/0 | 2419/2435 (99.3%) | 2 | 2421/2435 (99.4%) | - | 2 | 372.3 | settled |
| PIIND | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 1 | 2418/2433 (99.4%) | - | 10 | 354.6 | settled |
| PNB | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2419/2433 (99.4%) | 1 | 2420/2433 (99.5%) | - | 2 | 373.3 | settled |
| PNBHOUSING | map-required | 2016-11-07 | 2016-11-07 | 2413 | 127/0/0 | 2393/2412 (99.2%) | 3 | 2396/2412 (99.3%) | 1 | 6 | 356.7 | settled |
| POLICYBZR | table-path | 2021-11-15 | 2021-11-15 | 1168 | 62/0/0 | 1162/1167 (99.6%) | 1 | 1163/1167 (99.7%) | - | 1 | 373.3 | settled |
| POLYCAB | table-path | 2019-04-16 | 2019-04-16 | 1803 | 96/0/0 | 1793/1802 (99.5%) | 2 | 1795/1802 (99.6%) | - | 1 | 369.8 | settled |
| POWERGRID | map-required | 2016-10-01 | 2016-10-03 | 2435 | 129/0/0 | 2391/2434 (98.2%) | 4 | 2395/2434 (98.4%) | 0 | 2 | 373.3 | settled |
| POWERINDIA | table-path | 2020-03-30 | 2020-03-30 | 1571 | 83/0/0 | 1558/1570 (99.2%) | 2 | 1560/1570 (99.4%) | - | 10 | 323.4 | settled |
| PREMIERENE | table-path | 2024-09-03 | 2024-09-03 | 474 | 25/0/0 | 470/473 (99.4%) | 3 | 473/473 (100.0%) | - | 0 | 373.5 | settled |
| PRESTIGE | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2419/2433 (99.4%) | 0 | 2419/2433 (99.4%) | - | 10 | 348.7 | settled |
| RADICO | table-path | 2016-10-01 | 2016-10-03 | 2433 | 129/0/0 | 2418/2432 (99.4%) | 0 | 2418/2432 (99.4%) | - | 2 | 362.0 | settled |
| RBLBANK | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2418/2433 (99.4%) | 1 | 2419/2433 (99.4%) | - | 2 | 373.1 | settled |
| RECLTD | map-required | 2016-10-01 | 2016-10-03 | 2436 | 129/0/0 | 2420/2435 (99.4%) | 0 | 2420/2435 (99.4%) | 0 | 5 | 373.1 | settled |
| RELIANCE | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2408/2433 (99.0%) | 4 | 2412/2433 (99.1%) | 1 | 3 | 373.2 | settled |
| RVNL | map-required | 2019-04-11 | 2019-04-11 | 1808 | 96/0/0 | 1802/1807 (99.7%) | 0 | 1802/1807 (99.7%) | - | 2 | 372.9 | settled |
| SAIL | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2404/2433 (98.8%) | 12 | 2416/2433 (99.3%) | - | 4 | 373.1 | settled |
| SBICARD | table-path | 2020-03-16 | 2020-03-16 | 1581 | 84/0/0 | 1574/1580 (99.6%) | 2 | 1576/1580 (99.7%) | - | 1 | 373.3 | settled |
| SBILIFE | table-path | 2017-10-03 | 2017-10-03 | 2185 | 116/0/0 | 2169/2184 (99.3%) | 0 | 2169/2184 (99.3%) | - | 6 | 371.5 | settled |
| SBIN | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2420/2433 (99.5%) | 0 | 2420/2433 (99.5%) | - | 2 | 373.3 | settled |
| SHREECEM | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2402/2433 (98.7%) | 0 | 2402/2433 (98.7%) | - | 16 | 357.0 | settled |
| SHRIRAMFIN | table-path | 2022-12-20 | 2022-12-20 | 896 | 48/0/0 | 892/895 (99.7%) | 1 | 893/895 (99.8%) | - | 1 | 373.2 | settled |
| SIEMENS | map-required | 2016-10-01 | 2016-10-03 | 2433 | 129/0/0 | 2419/2432 (99.5%) | 0 | 2419/2432 (99.5%) | - | 3 | 368.7 | settled |
| SOLARINDS | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2413/2433 (99.2%) | 5 | 2418/2433 (99.4%) | - | 13 | 265.4 | settled |
| SONACOMS | table-path | 2021-06-24 | 2021-06-24 | 1266 | 67/0/0 | 1263/1265 (99.8%) | 0 | 1263/1265 (99.8%) | - | 1 | 373.2 | settled |
| SRF | map-required | 2016-10-01 | 2016-10-03 | 2436 | 129/0/0 | 2422/2435 (99.5%) | 1 | 2423/2435 (99.5%) | 0 | 4 | 368.0 | settled |
| SUNPHARMA | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 2 | 2419/2433 (99.4%) | - | 2 | 373.3 | settled |
| SUPREMEIND | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2415/2433 (99.3%) | 0 | 2415/2433 (99.3%) | - | 13 | 332.2 | settled |
| SUZLON | map-required | 2016-10-01 | 2016-10-03 | 2433 | 129/0/0 | 2381/2432 (97.9%) | 15 | 2396/2432 (98.5%) | - | 4 | 372.1 | settled |
| SWIGGY | table-path | 2024-11-13 | 2024-11-13 | 424 | 23/0/0 | 422/423 (99.8%) | 1 | 423/423 (100.0%) | - | 0 | 374.2 | settled |
| TATACONSUM | map-required | 2020-02-27 | 2020-02-27 | 1592 | 84/0/0 | 1586/1591 (99.7%) | 2 | 1588/1591 (99.8%) | - | 2 | 373.2 | settled |
| TATAELXSI | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2419/2433 (99.4%) | 0 | 2419/2433 (99.4%) | - | 3 | 372.3 | settled |
| TATAPOWER | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2406/2433 (98.9%) | 13 | 2419/2433 (99.4%) | - | 3 | 373.0 | settled |
| TATASTEEL | map-required | 2016-10-01 | 2016-10-03 | 2436 | 129/0/0 | 2091/2435 (85.9%) | 0 | 2091/2435 (85.9%) | 0 | 6 | 373.3 | settled |
| TCS | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2409/2433 (99.0%) | 4 | 2413/2433 (99.2%) | - | 3 | 373.3 | settled |
| TECHM | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2421/2433 (99.5%) | 0 | 2421/2433 (99.5%) | - | 2 | 373.3 | settled |
| TIINDIA | table-path | 2017-11-02 | 2017-11-02 | 2165 | 115/0/0 | 2141/2164 (98.9%) | 5 | 2146/2164 (99.2%) | - | 13 | 316.1 | settled |
| TITAN | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2418/2433 (99.4%) | 0 | 2418/2433 (99.4%) | - | 2 | 373.2 | settled |
| TMPV | table-path | 2025-10-24 | 2025-10-24 | 190 | 11/0/0 | 189/189 (100.0%) | 0 | 189/189 (100.0%) | - | 0 | 375.0 | settled |
| TORNTPHARM | map-required | 2016-10-01 | 2016-10-03 | 2436 | 129/0/0 | 2429/2435 (99.8%) | 1 | 2430/2435 (99.8%) | 0 | 3 | 365.1 | settled |
| TRENT | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2416/2433 (99.3%) | 1 | 2417/2433 (99.3%) | - | 13 | 339.6 | settled |
| TVSMOTOR | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2418/2433 (99.4%) | 0 | 2418/2433 (99.4%) | - | 3 | 372.6 | settled |
| ULTRACEMCO | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2418/2433 (99.4%) | 2 | 2420/2433 (99.5%) | - | 2 | 373.1 | settled |
| UNIONBANK | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2420/2433 (99.5%) | 0 | 2420/2433 (99.5%) | - | 2 | 373.0 | settled |
| UNITDSPR | table-path | 2024-06-07 | 2024-06-07 | 533 | 29/0/0 | 531/532 (99.8%) | 0 | 531/532 (99.8%) | - | 0 | 373.7 | settled |
| UNOMINDA | table-path | 2022-08-05 | 2022-08-05 | 987 | 53/0/0 | 981/986 (99.5%) | 0 | 981/986 (99.5%) | - | 3 | 371.9 | settled |
| UPL | map-required | 2016-10-01 | 2016-10-03 | 2435 | 129/0/0 | 1754/2434 (72.1%) | 0 | 1754/2434 (72.1%) | 0 | 680 | 373.2 | quarantined |
| VBL | map-required | 2016-11-08 | 2016-11-08 | 2412 | 127/0/0 | 1274/2411 (52.8%) | 0 | 1274/2411 (52.8%) | 0 | 749 | 336.7 | quarantined |
| VEDL | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2123/2433 (87.3%) | 0 | 2123/2433 (87.3%) | 2 | 5 | 373.2 | settled |
| VMM | table-path | 2024-12-18 | 2024-12-18 | 401 | 22/0/0 | 398/400 (99.5%) | 0 | 398/400 (99.5%) | - | 1 | 374.1 | settled |
| VOLTAS | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2419/2433 (99.4%) | 0 | 2419/2433 (99.4%) | - | 3 | 372.9 | settled |
| WAAREEENER | table-path | 2024-10-28 | 2024-10-28 | 436 | 23/0/0 | 434/435 (99.8%) | 0 | 434/435 (99.8%) | - | 1 | 373.5 | settled |
| WIPRO | map-required | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2419/2433 (99.4%) | 0 | 2419/2433 (99.4%) | - | 3 | 373.2 | settled |
| YESBANK | table-path | 2016-10-01 | 2016-10-03 | 2434 | 129/0/0 | 2417/2433 (99.3%) | 0 | 2417/2433 (99.3%) | - | 3 | 373.3 | settled |
| ZYDUSLIFE | table-path | 2022-03-07 | 2022-03-07 | 1091 | 58/0/0 | 1087/1090 (99.7%) | 1 | 1088/1090 (99.8%) | - | 2 | 373.5 | settled |

### 3a. BEFORE / AFTER the 2026-07-26 rulings (same stored candles, no refetch)

Every row here was gated once under the pre-ruling definitions and then re-gated from the SAME stored candles, so the two columns are a controlled comparison of the rulings themselves: Q-12's volume estimator + candidate set, the CONTEXT 4.5 gate-2 completeness redefinition, and the Q-12-addendum quarantine-recovery reroute. Not one candle was re-downloaded to produce the "after" column.

| Symbol | Route (after) | Gate-1 before | Gate-1 after | Gate-2 excl before | Gate-2 excl after | Status before | Status after |
|---|---|---|---|---|---|---|---|
| APLAPOLLO | map-required | 1896/2435 (77.9%) | 1896/2435 (77.9%) | 524 | 524 | quarantined | quarantined |
| ASTRAL | map-required | 1335/2434 (54.8%) | 1703/2434 (70.0%) | 775 | 636 | quarantined | quarantined |
| AUBANK | map-required | 1033/2244 (46.0%) | 2239/2244 (99.8%) | 303 | 2 | quarantined | settled |
| BEL | map-required | 959/2435 (39.4%) | 2177/2435 (89.4%) | 20 | 13 | quarantined | settled |
| BLUESTARCO | map-required | 1280/2433 (52.6%) | 2414/2433 (99.2%) | 924 | 16 | quarantined | settled |
| CANBK | map-required | 1047/2433 (43.0%) | 2418/2433 (99.4%) | 10 | 2 | quarantined | settled |
| COCHINSHIP | map-required | 1961/2219 (88.4%) | 2202/2219 (99.2%) | 147 | 10 | settled | settled |
| DIXON | map-required | 1929/2196 (87.8%) | 2173/2196 (99.0%) | 212 | 18 | settled | settled |
| HAL | map-required | 1679/2064 (81.3%) | 2052/2064 (99.4%) | 76 | 10 | settled | settled |
| HDFCBANK | map-required | 2334/2433 (95.9%) | 2377/2433 (97.7%) | 3 | 3 | settled | settled |
| HINDPETRO | map-required | 1770/2433 (72.7%) | 1999/2433 (82.2%) | 5 | 5 | quarantined | settled |
| IEX | map-required | 1152/2173 (53.0%) | 1153/2173 (53.1%) | 577 | 577 | quarantined | quarantined |
| INOXWIND | map-required | 1037/2433 (42.6%) | 2414/2433 (99.2%) | 1239 | 16 | quarantined | settled |
| JUBLFOOD | map-required | 1058/2435 (43.4%) | 2098/2435 (86.2%) | 24 | 17 | quarantined | settled |
| LODHA | map-required | 1280/1311 (97.6%) | 1282/1311 (97.8%) | 6 | 6 | settled | settled |
| MOTHERSON | map-required | 945/1027 (92.0%) | 1024/1027 (99.7%) | 2 | 2 | settled | settled |
| MOTILALOFS | map-required | 1028/2433 (42.3%) | 2413/2433 (99.2%) | 865 | 13 | quarantined | settled |
| NESTLEIND | map-required | 1133/2434 (46.5%) | 2393/2434 (98.3%) | 249 | 4 | quarantined | settled |
| NTPC | map-required | 1844/2432 (75.8%) | 1845/2432 (75.9%) | 5 | 5 | quarantined | quarantined |
| NYKAA | map-required | 919/1171 (78.5%) | 1169/1171 (99.8%) | 3 | 2 | quarantined | settled |
| PERSISTENT | map-required | 1088/2433 (44.7%) | 2415/2433 (99.3%) | 573 | 6 | quarantined | settled |
| PFC | map-required | 2299/2433 (94.5%) | 2420/2433 (99.5%) | 2 | 2 | settled | settled |
| PGEL | map-required | 2364/2433 (97.2%) | 2382/2433 (97.9%) | 49 | 49 | settled | settled |
| PNBHOUSING | map-required | 1666/2412 (69.1%) | 2396/2412 (99.3%) | 304 | 6 | quarantined | settled |
| RELIANCE | map-required | 2000/2433 (82.2%) | 2412/2433 (99.1%) | 5 | 3 | settled | settled |
| TORNTPHARM | map-required | 1011/2435 (41.5%) | 2430/2435 (99.8%) | 372 | 3 | quarantined | settled |
| VBL | map-required | 1274/2411 (52.8%) | 1274/2411 (52.8%) | 749 | 749 | quarantined | quarantined |
| VEDL | map-required | 642/2433 (26.4%) | 2123/2433 (87.3%) | 15 | 5 | quarantined | settled |
| **TOTAL (28)** | | **39,963/63,031 (63.4%)** | **57,293/63,031 (90.9%)** | **8,038** | **2,704** | | |

### 3b. Traded-minute statistics per symbol (the completeness ruling's liquidity numbers)

The architect's completeness ruling: "NO liquidity filter is invented (the trader specified none; per-symbol traded-minutes statistics are reported for his eyes)". These are those statistics. **Nothing in the code consumes them** -- there is no minimum traded minutes, no minimum volume and no symbol drop anywhere. `Liquidity days` counts days INCLUDED while carrying more than 15 tradeless minutes -- days the pre-ruling gate 2 excluded.

REVIEW_5B finding C15: the first column is STORED BARS per day (every bar the vendor served for the day, including any stamped outside the session) while the median and minimum are IN-SESSION traded minutes, so the two differ by ~0.2 min/day. Both are named for what they are rather than averaged into one number.

| Symbol | Avg stored bars/day | Median traded min/day | Min traded min/day | Liquidity days | Liquidity days as % of stored |
|---|---|---|---|---|---|
| 360ONE | 363.7 | 375 | 0 | 384 | 44.0% |
| ABB | 351.0 | 374 | 0 | 1270 | 52.2% |
| ABCAPITAL | 372.7 | 375 | 0 | 376 | 17.0% |
| ADANIENSOL | 372.9 | 375 | 0 | 44 | 6.0% |
| ADANIENT | 372.7 | 375 | 0 | 296 | 12.2% |
| ADANIGREEN | 362.8 | 375 | 0 | 518 | 25.8% |
| ADANIPORTS | 373.3 | 375 | 0 | 48 | 2.0% |
| ADANIPOWER | 372.4 | 375 | 0 | 371 | 15.2% |
| ALKEM | 343.9 | 372 | 0 | 1511 | 62.1% |
| AMBER | 327.4 | 370 | 0 | 1319 | 62.7% |
| AMBUJACEM | 373.1 | 375 | 0 | 196 | 8.1% |
| ANGELONE | 373.1 | 375 | 0 | 147 | 12.6% |
| APLAPOLLO | 314.1 | 374 | 0 | 721 | 29.6% |
| APOLLOHOSP | 372.0 | 375 | 0 | 361 | 14.8% |
| ASHOKLEY | 373.3 | 375 | 0 | 27 | 1.1% |
| ASIANPAINT | 373.3 | 375 | 0 | 47 | 1.9% |
| ASTRAL | 332.8 | 375 | 0 | 434 | 17.8% |
| AUBANK | 365.6 | 375 | 0 | 594 | 26.5% |
| AUROPHARMA | 373.2 | 375 | 0 | 114 | 4.7% |
| AXISBANK | 373.3 | 375 | 0 | 25 | 1.0% |
| BAJAJ-AUTO | 373.0 | 375 | 0 | 201 | 8.3% |
| BAJAJFINSV | 372.4 | 375 | 0 | 282 | 11.6% |
| BAJAJHLDNG | 315.0 | 340 | 0 | 2076 | 85.3% |
| BAJFINANCE | 373.2 | 375 | 0 | 47 | 1.9% |
| BANDHANBNK | 373.1 | 375 | 0 | 131 | 6.3% |
| BANKBARODA | 373.3 | 375 | 0 | 23 | 0.9% |
| BANKINDIA | 372.6 | 375 | 0 | 455 | 18.7% |
| BDL | 372.9 | 375 | 0 | 113 | 10.8% |
| BEL | 373.1 | 375 | 0 | 79 | 3.2% |
| BHARATFORG | 372.9 | 375 | 0 | 328 | 13.5% |
| BHARTIARTL | 373.2 | 375 | 0 | 52 | 2.1% |
| BHEL | 373.3 | 375 | 0 | 53 | 2.2% |
| BIOCON | 373.0 | 375 | 0 | 204 | 8.4% |
| BLUESTARCO | 321.1 | 352 | 0 | 1855 | 76.2% |
| BOSCHLTD | 357.2 | 367 | 0 | 1925 | 79.1% |
| BPCL | 373.3 | 375 | 0 | 21 | 0.9% |
| BRITANNIA | 372.7 | 375 | 0 | 260 | 10.7% |
| BSE | 365.1 | 375 | 0 | 801 | 34.1% |
| CAMS | 372.2 | 375 | 0 | 309 | 21.4% |
| CANBK | 373.2 | 375 | 0 | 81 | 3.3% |
| CDSL | 364.3 | 375 | 0 | 605 | 26.9% |
| CGPOWER | 356.2 | 375 | 0 | 1097 | 47.2% |
| CHOLAFIN | 368.3 | 375 | 0 | 539 | 22.1% |
| CIPLA | 373.2 | 375 | 0 | 98 | 4.0% |
| COALINDIA | 373.3 | 375 | 0 | 31 | 1.3% |
| COCHINSHIP | 350.0 | 371 | 0 | 1252 | 56.4% |
| COFORGE | 373.0 | 375 | 0 | 112 | 7.6% |
| COLPAL | 370.4 | 375 | 0 | 762 | 31.3% |
| CONCOR | 370.9 | 375 | 0 | 601 | 24.7% |
| CROMPTON | 367.4 | 375 | 0 | 661 | 27.2% |
| CUMMINSIND | 368.0 | 375 | 0 | 812 | 33.4% |
| DABUR | 372.7 | 375 | 0 | 248 | 10.2% |
| DALBHARAT | 350.6 | 373 | 0 | 1126 | 60.5% |
| DELHIVERY | 370.5 | 375 | 0 | 293 | 28.2% |
| DIVISLAB | 372.8 | 375 | 0 | 277 | 11.4% |
| DIXON | 343.3 | 375 | 0 | 704 | 32.0% |
| DLF | 373.3 | 375 | 0 | 43 | 1.8% |
| DMART | 373.2 | 375 | 0 | 202 | 8.7% |
| DRREDDY | 373.2 | 375 | 0 | 115 | 4.7% |
| EICHERMOT | 373.0 | 375 | 0 | 170 | 7.0% |
| ETERNAL | 374.0 | 375 | 60 | 1 | 0.3% |
| FEDERALBNK | 373.2 | 375 | 0 | 44 | 1.8% |
| FORCEMOT | 317.7 | 332 | 0 | 1364 | 82.8% |
| FORTIS | 362.9 | 375 | 0 | 986 | 40.5% |
| GAIL | 373.2 | 375 | 0 | 33 | 1.4% |
| GLENMARK | 372.1 | 375 | 0 | 660 | 27.1% |
| GMRAIRPORT | 374.2 | 375 | 60 | 17 | 4.2% |
| GODFRYPHLP | 327.7 | 345 | 0 | 1981 | 81.4% |
| GODREJCP | 372.5 | 375 | 0 | 341 | 14.0% |
| GODREJPROP | 358.3 | 375 | 0 | 973 | 40.0% |
| GRASIM | 373.0 | 375 | 0 | 163 | 6.7% |
| GVT&D | 373.1 | 375 | 60 | 35 | 8.1% |
| HAL | 341.5 | 375 | 0 | 711 | 34.4% |
| HAVELLS | 373.0 | 375 | 0 | 261 | 10.7% |
| HCLTECH | 373.2 | 375 | 0 | 35 | 1.4% |
| HDFCAMC | 372.7 | 375 | 0 | 280 | 14.2% |
| HDFCBANK | 373.2 | 375 | 0 | 35 | 1.4% |
| HDFCLIFE | 373.3 | 375 | 0 | 85 | 3.9% |
| HEROMOTOCO | 373.2 | 375 | 0 | 83 | 3.4% |
| HINDALCO | 373.2 | 375 | 0 | 23 | 0.9% |
| HINDPETRO | 373.2 | 375 | 0 | 29 | 1.2% |
| HINDUNILVR | 373.2 | 375 | 0 | 33 | 1.4% |
| HINDZINC | 370.8 | 375 | 0 | 833 | 34.2% |
| HYUNDAI | 373.4 | 375 | 0 | 11 | 2.5% |
| ICICIBANK | 373.2 | 375 | 0 | 21 | 0.9% |
| ICICIGI | 370.2 | 375 | 0 | 483 | 22.1% |
| ICICIPRULI | 372.7 | 375 | 0 | 362 | 14.9% |
| IDEA | 372.9 | 375 | 0 | 69 | 2.8% |
| IDFCFIRSTB | 373.4 | 375 | 0 | 24 | 1.3% |
| IEX | 337.6 | 375 | 0 | 125 | 5.7% |
| INDHOTEL | 363.8 | 375 | 0 | 816 | 33.5% |
| INDIANB | 370.5 | 375 | 0 | 862 | 35.4% |
| INDIGO | 371.1 | 375 | 0 | 403 | 16.6% |
| INDUSINDBK | 373.2 | 375 | 0 | 39 | 1.6% |
| INDUSTOWER | 373.3 | 375 | 0 | 89 | 6.4% |
| INFY | 373.2 | 375 | 0 | 19 | 0.8% |
| INOXWIND | 300.3 | 329 | 0 | 1730 | 71.1% |
| IOC | 373.2 | 375 | 0 | 19 | 0.8% |
| IREDA | 373.2 | 375 | 0 | 4 | 0.6% |
| IRFC | 373.5 | 375 | 0 | 16 | 1.2% |
| ITC | 373.2 | 375 | 0 | 22 | 0.9% |
| JINDALSTEL | 373.2 | 375 | 0 | 106 | 4.4% |
| JIOFIN | 373.4 | 375 | 0 | 3 | 0.4% |
| JSWENERGY | 362.6 | 375 | 0 | 1108 | 45.5% |
| JSWSTEEL | 373.2 | 375 | 0 | 66 | 2.7% |
| JUBLFOOD | 372.8 | 375 | 0 | 179 | 7.3% |
| KALYANKJIL | 370.7 | 375 | 0 | 278 | 21.0% |
| KAYNES | 369.6 | 375 | 0 | 222 | 24.2% |
| KEI | 354.2 | 373 | 0 | 1383 | 56.8% |
| KFINTECH | 365.0 | 375 | 0 | 315 | 35.4% |
| KOTAKBANK | 373.3 | 375 | 0 | 43 | 1.8% |
| KPITTECH | 358.4 | 375 | 0 | 475 | 26.3% |
| LAURUSLABS | 329.8 | 375 | 0 | 951 | 39.9% |
| LICHSGFIN | 373.0 | 375 | 0 | 265 | 10.9% |
| LICI | 373.2 | 375 | 0 | 10 | 1.0% |
| LODHA | 367.7 | 375 | 0 | 416 | 31.7% |
| LT | 373.3 | 375 | 0 | 24 | 1.0% |
| LTF | 373.4 | 375 | 0 | 7 | 1.2% |
| LTM | 374.9 | 375 | 373 | 7 | 6.8% |
| LUPIN | 373.1 | 375 | 0 | 141 | 5.8% |
| M&M | 373.3 | 375 | 0 | 39 | 1.6% |
| MANAPPURAM | 372.8 | 375 | 0 | 325 | 13.3% |
| MANKIND | 372.3 | 375 | 0 | 180 | 22.4% |
| MARICO | 372.3 | 375 | 0 | 308 | 12.7% |
| MARUTI | 373.3 | 375 | 0 | 24 | 1.0% |
| MAXHEALTH | 369.3 | 375 | 0 | 281 | 19.1% |
| MAZDOCK | 367.2 | 375 | 0 | 405 | 28.2% |
| MCX | 370.2 | 375 | 0 | 928 | 38.1% |
| MFSL | 368.9 | 375 | 0 | 851 | 35.0% |
| MOTHERSON | 373.3 | 375 | 0 | 4 | 0.4% |
| MOTILALOFS | 339.2 | 365 | 0 | 1592 | 65.4% |
| MPHASIS | 359.9 | 375 | 0 | 832 | 34.2% |
| MUTHOOTFIN | 370.3 | 375 | 0 | 594 | 24.4% |
| NAM-INDIA | 369.4 | 375 | 0 | 647 | 40.0% |
| NATIONALUM | 371.6 | 375 | 0 | 413 | 17.0% |
| NAUKRI | 349.3 | 375 | 0 | 741 | 30.4% |
| NBCC | 372.6 | 375 | 0 | 390 | 16.0% |
| NESTLEIND | 367.1 | 375 | 0 | 629 | 25.8% |
| NHPC | 368.3 | 375 | 0 | 880 | 36.2% |
| NMDC | 372.8 | 375 | 0 | 329 | 13.5% |
| NTPC | 373.2 | 375 | 0 | 72 | 3.0% |
| NYKAA | 373.4 | 375 | 0 | 24 | 2.0% |
| OBEROIRLTY | 358.7 | 374 | 0 | 1282 | 52.7% |
| OFSS | 340.3 | 367 | 0 | 1647 | 67.7% |
| OIL | 368.1 | 375 | 0 | 973 | 40.0% |
| ONGC | 373.3 | 375 | 0 | 23 | 0.9% |
| PAGEIND | 358.6 | 371 | 0 | 1669 | 68.6% |
| PATANJALI | 368.0 | 374 | 0 | 523 | 61.0% |
| PAYTM | 373.4 | 375 | 0 | 14 | 1.2% |
| PERSISTENT | 355.9 | 375 | 0 | 948 | 38.9% |
| PETRONET | 373.0 | 375 | 0 | 300 | 12.3% |
| PFC | 373.2 | 375 | 0 | 171 | 7.0% |
| PGEL | 231.6 | 220 | 0 | 1869 | 76.8% |
| PHOENIXLTD | 324.5 | 369 | 0 | 1515 | 62.2% |
| PIDILITIND | 372.3 | 375 | 0 | 358 | 14.7% |
| PIIND | 354.6 | 375 | 0 | 1132 | 46.5% |
| PNB | 373.3 | 375 | 0 | 26 | 1.1% |
| PNBHOUSING | 356.7 | 372 | 0 | 1442 | 59.8% |
| POLICYBZR | 373.3 | 375 | 0 | 114 | 9.8% |
| POLYCAB | 369.8 | 375 | 0 | 353 | 19.6% |
| POWERGRID | 373.3 | 375 | 0 | 58 | 2.4% |
| POWERINDIA | 323.4 | 356 | 0 | 1080 | 68.7% |
| PREMIERENE | 373.5 | 375 | 0 | 27 | 5.7% |
| PRESTIGE | 348.7 | 373 | 0 | 1409 | 57.9% |
| RADICO | 362.0 | 374 | 0 | 1362 | 56.0% |
| RBLBANK | 373.1 | 375 | 0 | 162 | 6.7% |
| RECLTD | 373.1 | 375 | 0 | 584 | 24.0% |
| RELIANCE | 373.2 | 375 | 0 | 24 | 1.0% |
| RVNL | 372.9 | 375 | 0 | 217 | 12.0% |
| SAIL | 373.1 | 375 | 0 | 175 | 7.2% |
| SBICARD | 373.3 | 375 | 0 | 43 | 2.7% |
| SBILIFE | 371.5 | 375 | 0 | 254 | 11.6% |
| SBIN | 373.3 | 375 | 0 | 25 | 1.0% |
| SHREECEM | 357.0 | 371 | 0 | 1640 | 67.4% |
| SHRIRAMFIN | 373.2 | 375 | 0 | 36 | 4.0% |
| SIEMENS | 368.7 | 375 | 0 | 1014 | 41.7% |
| SOLARINDS | 265.4 | 311 | 0 | 1794 | 73.7% |
| SONACOMS | 373.2 | 375 | 0 | 57 | 4.5% |
| SRF | 368.0 | 375 | 0 | 787 | 32.3% |
| SUNPHARMA | 373.3 | 375 | 0 | 24 | 1.0% |
| SUPREMEIND | 332.2 | 365 | 0 | 1717 | 70.5% |
| SUZLON | 372.1 | 375 | 0 | 401 | 16.5% |
| SWIGGY | 374.2 | 375 | 60 | 2 | 0.5% |
| TATACONSUM | 373.2 | 375 | 0 | 20 | 1.3% |
| TATAELXSI | 372.3 | 375 | 0 | 558 | 22.9% |
| TATAPOWER | 373.0 | 375 | 0 | 227 | 9.3% |
| TATASTEEL | 373.3 | 375 | 0 | 506 | 20.8% |
| TCS | 373.3 | 375 | 0 | 30 | 1.2% |
| TECHM | 373.3 | 375 | 0 | 43 | 1.8% |
| TIINDIA | 316.1 | 369 | 0 | 1393 | 64.3% |
| TITAN | 373.2 | 375 | 0 | 73 | 3.0% |
| TMPV | 375.0 | 375 | 375 | 0 | 0.0% |
| TORNTPHARM | 365.1 | 375 | 0 | 1163 | 47.7% |
| TRENT | 339.6 | 375 | 0 | 1069 | 43.9% |
| TVSMOTOR | 372.6 | 375 | 0 | 427 | 17.5% |
| ULTRACEMCO | 373.1 | 375 | 0 | 122 | 5.0% |
| UNIONBANK | 373.0 | 375 | 0 | 264 | 10.8% |
| UNITDSPR | 373.7 | 375 | 0 | 34 | 6.4% |
| UNOMINDA | 371.9 | 375 | 0 | 233 | 23.6% |
| UPL | 373.2 | 375 | 0 | 432 | 17.7% |
| VBL | 336.7 | 375 | 0 | 278 | 11.5% |
| VEDL | 373.2 | 375 | 0 | 23 | 0.9% |
| VMM | 374.1 | 375 | 60 | 1 | 0.2% |
| VOLTAS | 372.9 | 375 | 0 | 292 | 12.0% |
| WAAREEENER | 373.5 | 375 | 0 | 2 | 0.5% |
| WIPRO | 373.2 | 375 | 0 | 64 | 2.6% |
| YESBANK | 373.3 | 375 | 0 | 25 | 1.0% |
| ZYDUSLIFE | 373.5 | 375 | 0 | 69 | 6.3% |

### 3c. Vendor APPLICATION FLOORS (QUESTIONS.md Q-11 addendum 2)

The architect's ruling: "the vendor's back-adjustments have per-event APPLICATION FLOORS -- internal splice dates before which the event was never applied to its archive ... for days < F_e the event is ABSENT from that day's chain". Each floor below was BINARY-SEARCHED, not fitted: the search asks the daily oracle, one probed session at a time, whether that day's fetched bars fit the era's chain WITH the event or WITHOUT it, and bisects the boundary. Price containment decides -- and the tolerance is `max(2 paise, 0.100% of the raw price)`, NOT a flat 2 paise (REVIEW_5B finding Q2: every 5B document said "the same 2-paise containment" while the code has carried the relative floor since chunk 5A, decision B92 -- on a Rs 1,000 stock the effective tolerance is 100 paise, and the IOC cascade's "0.3 paise past the band" is only intelligible against it). A day that answers neither hypothesis is `undecided` and an undecided run abandons the search UNRESOLVED rather than guessing. Budget 16 probes per event, and the Q-14 pass spends none at all -- it reads the store (section 3f).

Hunt scope is the ruling's own: every QUARANTINED symbol and every settled symbol below gate-1 98%, plus (Q-11 addendum 4) every symbol carrying a GATE-3 failure, because a symbol can sit above the line while one ex-date of its history is in the wrong price domain -- a correctness question, not a coverage one. Within a symbol an event is searched only when its pre-ex provable-era span actually fails systematically (>= 10% of its days), or -- inside an un-provable era -- only when the signature gate admits it (section 3e). There is no floor to find where nothing fails, and every skip is recorded with its reason.

| Symbol | Gate-1 before the floor pass | Gate-1 after | Floors resolved | Probes | Note |
|---|---|---|---|---|---|
| APLAPOLLO | unchanged | 1896/2435 (77.9%) | 0 | 3 | 3 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| ASTRAL | 1336/2434 (54.9%) | 1703/2434 (70.0%) | 1 | 13 | 1 floor(s) resolved over 13 probe(s); 1 era(s) promoted to provable; 368 day(s) rewritten, 1338 already raw; gate 1 1336/2434 (54.9%) -> 1703/2434 (70.0%) |
| AUBANK | unchanged | 2239/2244 (99.8%) | 0 | 0 | 0 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| BAJAJFINSV | unchanged | 2421/2435 (99.4%) | 0 | 0 | 0 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| BEL | unchanged | 2177/2435 (89.4%) | 0 | 1 | 1 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| BLUESTARCO | 1280/2433 (52.6%) | 2414/2433 (99.2%) | 1 | 13 | 1 floor(s) resolved over 13 probe(s); 1161 day(s) rewritten, 1273 already raw; gate 1 1280/2433 (52.6%) -> 2414/2433 (99.2%) |
| BPCL | unchanged | 2227/2433 (91.5%) | 0 | 2 | 2 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| BSE | unchanged | 2199/2349 (93.6%) | 0 | 1 | 1 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| CANBK | 1047/2433 (43.0%) | 2418/2433 (99.4%) | 1 | 15 | 1 floor(s) resolved over 15 probe(s); 1 era(s) promoted to provable; 1383 day(s) rewritten, 1050 already raw; gate 1 1047/2433 (43.0%) -> 2418/2433 (99.4%) |
| COCHINSHIP | 1962/2219 (88.4%) | 2202/2219 (99.2%) | 1 | 12 | 1 floor(s) resolved over 12 probe(s); 4 era(s) promoted to provable; 240 day(s) rewritten, 1980 already raw; gate 1 1962/2219 (88.4%) -> 2202/2219 (99.2%) |
| DIXON | 1929/2196 (87.8%) | 2173/2196 (99.0%) | 1 | 12 | 1 floor(s) resolved over 12 probe(s); 257 day(s) rewritten, 1939 already raw; gate 1 1929/2196 (87.8%) -> 2173/2196 (99.0%) |
| GAIL | unchanged | 1994/2435 (81.9%) | 0 | 3 | 3 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| GRASIM | unchanged | 2418/2433 (99.4%) | 0 | 0 | 0 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| HAL | 1680/2064 (81.4%) | 2052/2064 (99.4%) | 1 | 12 | 1 floor(s) resolved over 12 probe(s); 2 era(s) promoted to provable; 373 day(s) rewritten, 1692 already raw; gate 1 1680/2064 (81.4%) -> 2052/2064 (99.4%) |
| HDFCBANK | unchanged | 2377/2433 (97.7%) | 0 | 0 | 0 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| HINDPETRO | 1770/2433 (72.7%) | 1999/2433 (82.2%) | 1 | 5 | 1 floor(s) resolved over 5 probe(s); 1 era(s) promoted to provable; 238 day(s) rewritten, 1772 already raw; gate 1 1770/2433 (72.7%) -> 1999/2433 (82.2%) |
| IEX | 1153/2173 (53.1%) | 1153/2173 (53.1%) | 1 | 14 | 1 floor(s) resolved over 14 probe(s); 1 era(s) promoted to provable; 0 day(s) rewritten, 1155 already raw; gate 1 1153/2173 (53.1%) -> 1153/2173 (53.1%) |
| INOXWIND | 1039/2433 (42.7%) | 2414/2433 (99.2%) | 1 | 14 | 1 floor(s) resolved over 14 probe(s); 1389 day(s) rewritten, 1043 already raw; gate 1 1039/2433 (42.7%) -> 2414/2433 (99.2%) |
| IOC | unchanged | 2066/2435 (84.8%) | 0 | 0 | 0 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| JUBLFOOD | 2098/2435 (86.2%) | 2098/2435 (86.2%) | 1 | 13 | 1 floor(s) resolved over 13 probe(s); 323 day(s) rewritten, 2113 already raw; gate 1 2098/2435 (86.2%) -> 2098/2435 (86.2%) |
| LODHA | unchanged | 1282/1311 (97.8%) | 0 | 0 | 0 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| MOTILALOFS | 1029/2433 (42.3%) | 2413/2433 (99.2%) | 1 | 13 | 1 floor(s) resolved over 13 probe(s); 1401 day(s) rewritten, 1032 already raw; gate 1 1029/2433 (42.3%) -> 2413/2433 (99.2%) |
| NESTLEIND | 1133/2434 (46.5%) | 2393/2434 (98.3%) | 1 | 14 | 1 floor(s) resolved over 14 probe(s); 1 era(s) promoted to provable; 1299 day(s) rewritten, 1136 already raw; gate 1 1133/2434 (46.5%) -> 2393/2434 (98.3%) |
| NMDC | unchanged | 2057/2435 (84.5%) | 0 | 1 | 1 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| NTPC | 1845/2432 (75.9%) | 1845/2432 (75.9%) | 1 | 3 | 1 floor(s) resolved over 3 probe(s); 0 day(s) rewritten, 1851 already raw; gate 1 1845/2432 (75.9%) -> 1845/2432 (75.9%) |
| OIL | unchanged | 2052/2433 (84.3%) | 0 | 2 | 2 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| PERSISTENT | 1088/2433 (44.7%) | 2415/2433 (99.3%) | 1 | 13 | 1 floor(s) resolved over 13 probe(s); 1354 day(s) rewritten, 1080 already raw; gate 1 1088/2433 (44.7%) -> 2415/2433 (99.3%) |
| PETRONET | unchanged | 2238/2435 (91.9%) | 0 | 0 | 0 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| PFC | 2299/2433 (94.5%) | 2420/2433 (99.5%) | 1 | 12 | 1 floor(s) resolved over 12 probe(s); 4 era(s) promoted to provable; 121 day(s) rewritten, 2313 already raw; gate 1 2299/2433 (94.5%) -> 2420/2433 (99.5%) |
| PGEL | unchanged | 2382/2433 (97.9%) | 0 | 0 | 0 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| PNBHOUSING | 1669/2412 (69.2%) | 2396/2412 (99.3%) | 1 | 13 | 1 floor(s) resolved over 13 probe(s); 739 day(s) rewritten, 1674 already raw; gate 1 1669/2412 (69.2%) -> 2396/2412 (99.3%) |
| POWERGRID | unchanged | 2395/2434 (98.4%) | 0 | 0 | 0 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| RECLTD | unchanged | 2420/2435 (99.4%) | 0 | 0 | 0 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| RELIANCE | 2004/2433 (82.4%) | 2412/2433 (99.1%) | 1 | 14 | 1 floor(s) resolved over 14 probe(s); 411 day(s) rewritten, 2022 already raw; gate 1 2004/2433 (82.4%) -> 2412/2433 (99.1%) |
| SRF | unchanged | 2423/2435 (99.5%) | 0 | 0 | 0 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| TATASTEEL | unchanged | 2091/2435 (85.9%) | 0 | 0 | 0 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| TORNTPHARM | unchanged | 2430/2435 (99.8%) | 0 | 0 | 0 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| UPL | unchanged | 1754/2434 (72.1%) | 0 | 1 | 1 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| VBL | unchanged | 1274/2411 (52.8%) | 0 | 1 | 1 probe(s) spent; this pass measured no new vendor application floor, so the map's chain is unchanged; no event carries a vendor application floor inside our history |
| VEDL | 642/2433 (26.4%) | 2123/2433 (87.3%) | 2 | 8 | 2 floor(s) resolved over 8 probe(s); 13 era(s) promoted to provable; 1489 day(s) rewritten, 644 already raw; gate 1 642/2433 (26.4%) -> 2123/2433 (87.3%) |

Per-event findings (every event the hunt looked at, including the ones it declined to search and why):

- **APLAPOLLO**
  - 2021-09-16 -> no splice (UNRESOLVED, 2 probe(s)): the oldest probed day (2016-10-03) answers neither hypothesis; no boundary is guessed
  - 2020-12-15 -> no splice (UNRESOLVED, 2 probe(s)): the oldest probed day (2016-10-03) answers neither hypothesis; no boundary is guessed
- **ASTRAL**
  - 2023-03-14 -> 2021-03-08 (resolved, 11 probe(s)): vendor application floor 2021-03-08: the event is absent from every chain before it (2021-03-05 probed event-out) and applied from it on
  - 2021-03-18 -> era pre-2019-09-16: no hypothesis -- ['2019-09-16'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-18 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too (2019-09-16): no splice inside our history, the chain is unchanged
  - 2019-09-16 -> no splice (UNRESOLVED, 2 probe(s)): the oldest probed day (2016-10-03) answers neither hypothesis; no boundary is guessed [admitted by era failure-rate cliff: 729/729 = 100.0% of the gated days below 2019-09-16 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 729 of the 729 stored days below 2019-09-16 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind]
  - [round 2] 2019-09-16 -> no splice (UNRESOLVED, 2 probe(s)): the oldest probed day (2016-10-03) answers neither hypothesis; no boundary is guessed
- **AUBANK**
  - 2022-06-09 -> not searched: its pre-ex span reconciles (2/1215 = 0.2% of days fail gate 1, below the 10% systematic-failure threshold)
- **BAJAJFINSV**
  - 2022-09-13 -> era pre-2017-07-06: no hypothesis -- ['2017-07-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-09-13 -> not searched: its pre-ex span reconciles (11/1282 = 0.9% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2017-07-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
- **BEL**
  - 2022-09-15 -> era pre-2017-09-28: no hypothesis -- ['2017-09-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-09-15 -> era pre-2017-03-16: no hypothesis -- ['2017-03-16', '2017-09-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-09-15 -> not searched: its pre-ex span reconciles (11/1226 = 0.9% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2017-09-28 -> era pre-2017-03-16: no hypothesis -- ['2017-03-16'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-09-28 -> no splice (UNRESOLVED, 1 probe(s)): the newest probed day (2017-09-27) is undecided, not event-in: the event is not applied even beside its own ex-date, so there is no floor to find [admitted by era failure-rate cliff: 134/134 = 100.0% of the gated days below 2017-09-28 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 134 of the 134 stored days below 2017-09-28 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind]
  - 2017-03-16 -> era pre-2017-09-28: no hypothesis -- ['2017-09-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-16 -> era pre-2017-03-16: no hypothesis -- ['2017-09-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-16 -> not searched: no day of a provable era carries this event with a factor to drop
- **BLUESTARCO**
  - 2023-06-20 -> 2021-06-15 (resolved, 13 probe(s)): vendor application floor 2021-06-15: the event is absent from every chain before it (2021-06-14 probed event-out) and applied from it on
- **BPCL**
  - 2026-02-02 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2025-11-07 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-08-09 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-06-21 -> not searched: its pre-ex span reconciles (12/1710 = 0.7% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2023-12-12 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-09-16 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-02-17 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-03-23 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-08-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-02-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2018-02-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2017-07-13 -> era pre-2017-02-28: no hypothesis -- ['2017-02-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-07-13 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too (2017-02-28): no splice inside our history, the chain is unchanged [admitted by era failure-rate cliff: 92/92 = 100.0% of the gated days below 2017-07-13 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 92 of the 92 stored days below 2017-07-13 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind]
  - 2017-02-28 -> era pre-2017-07-13: no hypothesis -- ['2017-07-13'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-28 -> era pre-2017-02-28: no hypothesis -- ['2017-07-13'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-28 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2016-07-13 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
- **BSE**
  - 2025-05-23 -> not searched: its pre-ex span reconciles (12/1909 = 0.6% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2022-06-23 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-03-21 -> not searched: its pre-ex span reconciles (11/1127 = 1.0% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2020-07-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-06-27 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2018-07-25 -> era pre-2017-08-24: no hypothesis -- ['2017-08-24'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-07-25 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2017-08-24 -> no splice (UNRESOLVED, 1 probe(s)): the newest probed day (2017-08-23) is undecided, not event-in: the event is not applied even beside its own ex-date, so there is no floor to find [admitted by era failure-rate cliff: 137/137 = 100.0% of the gated days below 2017-08-24 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 137 of the 137 stored days below 2017-08-24 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind]
- **CANBK**
  - 2026-06-12 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2025-06-13 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-06-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-05-15 -> 2022-05-10 (resolved, 13 probe(s)): vendor application floor 2022-05-10: the event is absent from every chain before it (2022-05-09 probed event-out) and applied from it on
  - 2023-06-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-06-15 -> era pre-2017-02-17: no hypothesis -- ['2017-02-17'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-15 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2017-02-17 -> era pre-2017-02-17: no hypothesis -- ['2017-02-17'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-02-17 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2026-06-12 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2025-06-13 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2024-06-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2023-06-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2022-06-15 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2017-02-17 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too (2016-10-03): no splice inside our history, the chain is unchanged
- **COCHINSHIP**
  - 2024-01-10 -> 2022-01-04 (resolved, 12 probe(s)): vendor application floor 2022-01-04: the event is absent from every chain before it (2022-01-03 probed event-out) and applied from it on
  - 2022-02-21 -> era pre-2021-01-13: no hypothesis -- ['2021-01-13'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-21 -> era pre-2020-09-21: no hypothesis -- ['2020-09-21', '2021-01-13'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-21 -> era pre-2019-08-05: no hypothesis -- ['2019-08-05', '2020-09-21', '2021-01-13'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-21 -> era pre-2018-08-06: no hypothesis -- ['2018-08-06', '2019-08-05', '2020-09-21', '2021-01-13'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-21 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2021-01-13 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-09-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-08-05 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2018-08-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2022-02-21 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2021-01-13 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2020-09-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2019-08-05 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2018-08-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
- **DIXON**
  - 2021-03-18 -> 2018-10-01 (resolved, 12 probe(s)): vendor application floor 2018-10-01: the event is absent from every chain before it (2018-09-28 probed event-out) and applied from it on
- **GAIL**
  - 2026-02-05 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2025-02-07 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-02-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-03-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-09-06 -> not searched: its pre-ex span reconciles (72/1097 = 6.6% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2022-03-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-12-30 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-02-17 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-08-08 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-07-09 -> era pre-2018-03-27: no hypothesis -- ['2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-07-09 -> era pre-2017-03-09: no hypothesis -- ['2017-03-09', '2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-07-09 -> no splice (UNRESOLVED, 2 probe(s)): the oldest probed day (2018-03-27) answers neither hypothesis; no boundary is guessed
  - 2018-03-27 -> era pre-2017-03-09: no hypothesis -- ['2017-03-09'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-27 -> no splice (UNRESOLVED, 1 probe(s)): the newest probed day (2018-03-26) is undecided, not event-in: the event is not applied even beside its own ex-date, so there is no floor to find [admitted by era failure-rate cliff: 260/260 = 100.0% of the gated days below 2018-03-27 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 260 of the 260 stored days below 2018-03-27 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind]
  - 2017-03-09 -> era pre-2018-03-27: no hypothesis -- ['2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-09 -> era pre-2017-03-09: no hypothesis -- ['2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-03-09 -> not searched: no day of a provable era carries this event with a factor to drop
- **GRASIM**
  - 2024-01-10 -> not searched: its pre-ex span reconciles (14/1795 = 0.8% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2017-07-19 -> not searched: its pre-ex span reconciles (1/196 = 0.5% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2016-10-06 -> not searched: its pre-ex span reconciles (0/3 = 0.0% of days fail gate 1, below the 10% systematic-failure threshold)
- **HAL**
  - 2023-09-28 -> era pre-2020-03-23: no hypothesis -- ['2020-03-23'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-09-28 -> era pre-2019-03-28: no hypothesis -- ['2019-03-28', '2020-03-23'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-09-28 -> 2021-09-24 (resolved, 12 probe(s)): vendor application floor 2021-09-24: the event is absent from every chain before it (2021-09-23 probed event-out) and applied from it on
  - 2020-03-23 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-03-28 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2020-03-23 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2019-03-28 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
- **HDFCBANK**
  - 2025-08-26 -> not searched: its pre-ex span reconciles (56/2195 = 2.6% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2019-09-19 -> not searched: its pre-ex span reconciles (12/731 = 1.6% of days fail gate 1, below the 10% systematic-failure threshold)
- **HINDPETRO**
  - 2025-08-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-08-09 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-06-21 -> not searched: its pre-ex span reconciles (1/1242 = 0.1% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2024-02-07 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-08-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-07-08 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-07-02 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-06-06 -> era pre-2019-02-14: no hypothesis -- ['2019-02-14'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-06-06 -> era pre-2018-02-28: no hypothesis -- ['2018-02-28', '2019-02-14'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-06-06 -> era pre-2017-07-11: no hypothesis -- ['2017-07-11', '2018-02-28', '2019-02-14'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-06-06 -> era pre-2017-03-01: no hypothesis -- ['2017-03-01', '2017-07-11', '2018-02-28', '2019-02-14'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-06-06 -> 2019-06-06 (resolved, 3 probe(s)): vendor application floor at or above the ex-date 2019-06-06: the event is absent from every chain in our history (3 probed day(s) across 2019-02-14 .. 2019-06-04, all event-out) [admitted by era failure-rate cliff: 73/73 = 100.0% of the gated days below 2019-06-06 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 73 of the 73 stored days below 2019-06-06 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind]
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
  - 2021-12-03 -> 2019-10-01 (resolved, 12 probe(s)): vendor application floor 2019-10-01: the event is absent from every chain before it (2019-09-30 probed event-out) and applied from it on [admitted by era failure-rate cliff: 773/773 = 100.0% of the gated days below 2021-12-03 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 233 of the 773 stored days below 2021-12-03 fail gate 1P as a contiguous block (>= 95%) while the 540 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind]
  - 2018-10-19 -> era pre-2021-12-03: no hypothesis -- ['2021-12-03'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-10-19 -> era pre-2018-10-19: no hypothesis -- ['2021-12-03'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-10-19 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2018-10-19 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too (2017-10-23): no splice inside our history, the chain is unchanged
- **INOXWIND**
  - 2025-07-29 -> no splice (UNRESOLVED, 2 probe(s)): the oldest probed day (2016-10-03) answers neither hypothesis; no boundary is guessed
  - 2024-05-24 -> 2022-05-19 (resolved, 13 probe(s)): vendor application floor 2022-05-19: the event is absent from every chain before it (2022-05-18 probed event-out) and applied from it on
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
  - 2022-02-09 -> era pre-2023-11-10: no hypothesis -- ['2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-09 -> era pre-2023-07-28: no hypothesis -- ['2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-09 -> era pre-2022-08-11: no hypothesis -- ['2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-09 -> era pre-2022-06-30: no hypothesis -- ['2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-09 -> era pre-2022-02-09: no hypothesis -- ['2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-09 -> era pre-2021-11-11: no hypothesis -- ['2021-11-11', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-09 -> era pre-2021-03-23: no hypothesis -- ['2021-03-23', '2021-11-11', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-09 -> era pre-2021-02-09: no hypothesis -- ['2021-02-09', '2021-03-23', '2021-11-11', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-09 -> era pre-2020-03-23: no hypothesis -- ['2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-09 -> era pre-2018-12-21: no hypothesis -- ['2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-09 -> era pre-2018-03-15: no hypothesis -- ['2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-09 -> era pre-2018-02-08: no hypothesis -- ['2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-09 -> era pre-2017-02-09: no hypothesis -- ['2017-02-09', '2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-09 -> era pre-2016-10-18: no hypothesis -- ['2016-10-18', '2017-02-09', '2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2021-11-11', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-09 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2021-11-11 -> era pre-2023-11-10: no hypothesis -- ['2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-11-11 -> era pre-2023-07-28: no hypothesis -- ['2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-11-11 -> era pre-2022-08-11: no hypothesis -- ['2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-11-11 -> era pre-2022-06-30: no hypothesis -- ['2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-11-11 -> era pre-2022-02-09: no hypothesis -- ['2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-11-11 -> era pre-2021-11-11: no hypothesis -- ['2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-11-11 -> era pre-2021-03-23: no hypothesis -- ['2021-03-23', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-11-11 -> era pre-2021-02-09: no hypothesis -- ['2021-02-09', '2021-03-23', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-11-11 -> era pre-2020-03-23: no hypothesis -- ['2020-03-23', '2021-02-09', '2021-03-23', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-11-11 -> era pre-2018-12-21: no hypothesis -- ['2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-11-11 -> era pre-2018-03-15: no hypothesis -- ['2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-11-11 -> era pre-2018-02-08: no hypothesis -- ['2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-11-11 -> era pre-2017-02-09: no hypothesis -- ['2017-02-09', '2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-11-11 -> era pre-2016-10-18: no hypothesis -- ['2016-10-18', '2017-02-09', '2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-03-23', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-11-11 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2021-03-23 -> era pre-2023-11-10: no hypothesis -- ['2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-23 -> era pre-2023-07-28: no hypothesis -- ['2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-23 -> era pre-2022-08-11: no hypothesis -- ['2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-23 -> era pre-2022-06-30: no hypothesis -- ['2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-23 -> era pre-2022-02-09: no hypothesis -- ['2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-23 -> era pre-2021-11-11: no hypothesis -- ['2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-23 -> era pre-2021-03-23: no hypothesis -- ['2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-23 -> era pre-2021-02-09: no hypothesis -- ['2021-02-09', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-23 -> era pre-2020-03-23: no hypothesis -- ['2020-03-23', '2021-02-09', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-23 -> era pre-2018-12-21: no hypothesis -- ['2018-12-21', '2020-03-23', '2021-02-09', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-23 -> era pre-2018-03-15: no hypothesis -- ['2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-23 -> era pre-2018-02-08: no hypothesis -- ['2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-23 -> era pre-2017-02-09: no hypothesis -- ['2017-02-09', '2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-23 -> era pre-2016-10-18: no hypothesis -- ['2016-10-18', '2017-02-09', '2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-02-09', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-03-23 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2021-02-09 -> era pre-2023-11-10: no hypothesis -- ['2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-02-09 -> era pre-2023-07-28: no hypothesis -- ['2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-02-09 -> era pre-2022-08-11: no hypothesis -- ['2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-02-09 -> era pre-2022-06-30: no hypothesis -- ['2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-02-09 -> era pre-2022-02-09: no hypothesis -- ['2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-02-09 -> era pre-2021-11-11: no hypothesis -- ['2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-02-09 -> era pre-2021-03-23: no hypothesis -- ['2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-02-09 -> era pre-2021-02-09: no hypothesis -- ['2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-02-09 -> era pre-2020-03-23: no hypothesis -- ['2020-03-23', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-02-09 -> era pre-2018-12-21: no hypothesis -- ['2018-12-21', '2020-03-23', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-02-09 -> era pre-2018-03-15: no hypothesis -- ['2018-03-15', '2018-12-21', '2020-03-23', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-02-09 -> era pre-2018-02-08: no hypothesis -- ['2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-02-09 -> era pre-2017-02-09: no hypothesis -- ['2017-02-09', '2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-02-09 -> era pre-2016-10-18: no hypothesis -- ['2016-10-18', '2017-02-09', '2018-02-08', '2018-03-15', '2018-12-21', '2020-03-23', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-02-09 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2020-03-23 -> era pre-2023-11-10: no hypothesis -- ['2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-23 -> era pre-2023-07-28: no hypothesis -- ['2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-23 -> era pre-2022-08-11: no hypothesis -- ['2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-23 -> era pre-2022-06-30: no hypothesis -- ['2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-23 -> era pre-2022-02-09: no hypothesis -- ['2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-23 -> era pre-2021-11-11: no hypothesis -- ['2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-23 -> era pre-2021-03-23: no hypothesis -- ['2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-23 -> era pre-2021-02-09: no hypothesis -- ['2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-23 -> era pre-2020-03-23: no hypothesis -- ['2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-23 -> era pre-2018-12-21: no hypothesis -- ['2018-12-21', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-23 -> era pre-2018-03-15: no hypothesis -- ['2018-03-15', '2018-12-21', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-23 -> era pre-2018-02-08: no hypothesis -- ['2018-02-08', '2018-03-15', '2018-12-21', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-23 -> era pre-2017-02-09: no hypothesis -- ['2017-02-09', '2018-02-08', '2018-03-15', '2018-12-21', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-23 -> era pre-2016-10-18: no hypothesis -- ['2016-10-18', '2017-02-09', '2018-02-08', '2018-03-15', '2018-12-21', '2021-02-09', '2021-03-23', '2021-11-11', '2022-02-09', '2022-06-30', '2022-08-11', '2023-07-28', '2023-11-10'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-23 -> not searched: no day of a provable era carries this event with a factor to drop
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
- **MOTILALOFS**
  - 2024-06-10 -> 2022-06-03 (resolved, 13 probe(s)): vendor application floor 2022-06-03: the event is absent from every chain before it (2022-06-02 probed event-out) and applied from it on
- **NESTLEIND**
  - 2025-08-08 -> no splice (UNRESOLVED, 2 probe(s)): the oldest probed day (2020-10-29) answers neither hypothesis; no boundary is guessed
  - 2024-01-05 -> era pre-2020-10-29: no hypothesis -- ['2020-10-29'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2024-01-05 -> 2021-12-31 (resolved, 12 probe(s)): vendor application floor 2021-12-31: the event is absent from every chain before it (2021-12-30 probed event-out) and applied from it on
  - 2020-10-29 -> era pre-2020-10-29: no hypothesis -- ['2020-10-29'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-29 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2025-08-08 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too (2016-10-03): no splice inside our history, the chain is unchanged
  - [round 2] 2020-10-29 -> not searched: no day of a provable era carries this event with a factor to drop
- **NMDC**
  - 2026-02-13 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2025-03-21 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2024-12-27 -> not searched: its pre-ex span reconciles (9/1666 = 0.5% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2024-02-27 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-08-31 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-02-24 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-10-27 -> not searched: its pre-ex span reconciles (8/1132 = 0.7% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2022-02-17 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-12-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-03-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-02-18 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-03-22 -> era pre-2018-03-27: no hypothesis -- ['2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-03-22 -> era pre-2017-03-16: no hypothesis -- ['2017-03-16', '2018-03-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2019-03-22 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2018-03-27 -> era pre-2017-03-16: no hypothesis -- ['2017-03-16'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-27 -> no splice (UNRESOLVED, 1 probe(s)): the newest probed day (2018-03-26) is undecided, not event-in: the event is not applied even beside its own ex-date, so there is no floor to find [admitted by era failure-rate cliff: 256/256 = 100.0% of the gated days below 2018-03-27 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 256 of the 256 stored days below 2018-03-27 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind]
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
  - 2019-02-06 -> 2019-02-06 (resolved, 3 probe(s)): vendor application floor at or above the ex-date 2019-02-06: the event is absent from every chain in our history (3 probed day(s) across 2016-10-03 .. 2019-02-05, all event-out) [admitted by era failure-rate cliff: 582/582 = 100.0% of the gated days below 2019-02-06 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 582 of the 582 stored days below 2019-02-06 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind]
- **OIL**
  - 2024-07-02 -> not searched: its pre-ex span reconciles (12/1542 = 0.8% of days fail gate 1, below the 10% systematic-failure threshold)
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
  - 2018-03-27 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too (2018-02-21): no splice inside our history, the chain is unchanged [admitted by era failure-rate cliff: 23/23 = 100.0% of the gated days below 2018-03-27 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 23 of the 23 stored days below 2018-03-27 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind]
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
- **PERSISTENT**
  - 2024-03-28 -> 2022-03-24 (resolved, 13 probe(s)): vendor application floor 2022-03-24: the event is absent from every chain before it (2022-03-23 probed event-out) and applied from it on
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
- **PFC**
  - 2023-09-21 -> 2021-09-16 (resolved, 12 probe(s)): vendor application floor 2021-09-16: the event is absent from every chain before it (2021-09-15 probed event-out) and applied from it on
  - 2023-06-16 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-02-24 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-11-24 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-02-25 -> era pre-2021-03-19: no hypothesis -- ['2021-03-19'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-25 -> era pre-2020-02-28: no hypothesis -- ['2020-02-28', '2021-03-19'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-25 -> era pre-2017-11-10: no hypothesis -- ['2017-11-10', '2020-02-28', '2021-03-19'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-25 -> era pre-2017-03-30: no hypothesis -- ['2017-03-30', '2017-11-10', '2020-02-28', '2021-03-19'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-02-25 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2021-03-19 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-02-28 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2017-11-10 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2017-03-30 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2016-08-26 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2016-02-16 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2023-06-16 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2023-02-24 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2022-11-24 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2022-02-25 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2021-03-19 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2020-02-28 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2017-11-10 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2017-03-30 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2016-08-26 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2016-02-16 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
- **PGEL**
  - 2024-07-10 -> not searched: its pre-ex span reconciles (50/1915 = 2.6% of days fail gate 1, below the 10% systematic-failure threshold)
- **PNBHOUSING**
  - 2023-04-05 -> 2019-11-05 (resolved, 13 probe(s)): vendor application floor 2019-11-05: the event is absent from every chain before it (2019-11-04 probed event-out) and applied from it on
- **POWERGRID**
  - 2023-09-12 -> not searched: its pre-ex span reconciles (38/1716 = 2.2% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2023-02-08 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-11-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-02-16 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-12-22 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2021-07-29 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2020-12-17 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-09-02 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-03-16 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-03-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
- **RECLTD**
  - 2023-07-14 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-02-09 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-11-07 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-08-17 -> not searched: its pre-ex span reconciles (0/434 = 0.0% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2022-07-12 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-02-15 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2021-03-18 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-11-13 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2020-02-11 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2019-03-11 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2018-02-15 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2017-02-27 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2016-09-28 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2016-08-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2016-02-17 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
- **RELIANCE**
  - 2024-10-28 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too (2016-10-03): no splice inside our history, the chain is unchanged
  - 2023-07-20 -> 2022-01-05 (resolved, 12 probe(s)): vendor application floor 2022-01-05: the event is absent from every chain before it (2022-01-04 probed event-out) and applied from it on
  - 2020-05-13 -> not searched: its pre-ex span reconciles (11/887 = 1.2% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2017-09-07 -> not searched: its pre-ex span reconciles (0/230 = 0.0% of days fail gate 1, below the 10% systematic-failure threshold)
- **SRF**
  - 2021-10-13 -> era pre-2017-08-16: no hypothesis -- ['2017-08-16'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-10-13 -> not searched: its pre-ex span reconciles (10/1027 = 1.0% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2017-08-16 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
- **TATASTEEL**
  - 2026-06-12 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2025-06-06 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2023-06-22 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - 2022-07-28 -> era pre-2022-06-15: no hypothesis -- ['2022-06-15'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-28 -> era pre-2021-06-17: no hypothesis -- ['2021-06-17', '2022-06-15'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-28 -> era pre-2020-08-06: no hypothesis -- ['2020-08-06', '2021-06-17', '2022-06-15'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-28 -> era pre-2019-07-04: no hypothesis -- ['2019-07-04', '2020-08-06', '2021-06-17', '2022-06-15'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-28 -> era pre-2018-01-31: no hypothesis -- ['2018-01-31', '2019-07-04', '2020-08-06', '2021-06-17', '2022-06-15'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-28 -> not searched: its pre-ex span reconciles (0/31 = 0.0% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2022-06-15 -> era pre-2022-07-28: no hypothesis -- ['2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-15 -> era pre-2022-06-15: no hypothesis -- ['2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-15 -> era pre-2021-06-17: no hypothesis -- ['2021-06-17', '2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-15 -> era pre-2020-08-06: no hypothesis -- ['2020-08-06', '2021-06-17', '2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-15 -> era pre-2019-07-04: no hypothesis -- ['2019-07-04', '2020-08-06', '2021-06-17', '2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-15 -> era pre-2018-01-31: no hypothesis -- ['2018-01-31', '2019-07-04', '2020-08-06', '2021-06-17', '2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-06-15 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2021-06-17 -> era pre-2022-07-28: no hypothesis -- ['2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-06-17 -> era pre-2022-06-15: no hypothesis -- ['2022-06-15', '2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-06-17 -> era pre-2021-06-17: no hypothesis -- ['2022-06-15', '2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-06-17 -> era pre-2020-08-06: no hypothesis -- ['2020-08-06', '2022-06-15', '2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-06-17 -> era pre-2019-07-04: no hypothesis -- ['2019-07-04', '2020-08-06', '2022-06-15', '2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-06-17 -> era pre-2018-01-31: no hypothesis -- ['2018-01-31', '2019-07-04', '2020-08-06', '2022-06-15', '2022-07-28'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-06-17 -> not searched: no day of a provable era carries this event with a factor to drop
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
- **TORNTPHARM**
  - 2022-07-08 -> not searched: its pre-ex span reconciles (2/1425 = 0.1% of days fail gate 1, below the 10% systematic-failure threshold)
- **UPL**
  - 2024-11-26 -> not searched: its pre-ex span reconciles (1/1332 = 0.1% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2019-07-02 -> no splice (UNRESOLVED, 1 probe(s)): the newest probed day (2019-07-01) is undecided, not event-in: the event is not applied even beside its own ex-date, so there is no floor to find [admitted by gate-3 raw-gap-near-zero: |raw gap| 8.62% is nearer 0 than the event's own step 33.33% (k=0.6666666666666666666666666667), adjusted gap 62.94% -- both closes are already in the same price domain AND era failure-rate cliff: 679/679 = 100.0% of the gated days below 2019-07-02 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 679 of the 679 stored days below 2019-07-02 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind]
- **VBL**
  - 2024-09-12 -> not searched: its pre-ex span reconciles (1/805 = 0.1% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2023-06-15 -> not searched: its pre-ex span reconciles (0/500 = 0.0% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2022-06-06 -> not searched: its pre-ex span reconciles (0/245 = 0.0% of days fail gate 1, below the 10% systematic-failure threshold)
  - 2021-06-10 -> era pre-2019-07-25: no hypothesis -- ['2019-07-25'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-06-10 -> no splice (UNRESOLVED, 1 probe(s)): the newest probed day (2021-06-09) is undecided, not event-in: the event is not applied even beside its own ex-date, so there is no floor to find [admitted by era failure-rate cliff: 464/464 = 100.0% of the gated days below 2021-06-10 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 464 of the 464 stored days below 2021-06-10 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind]
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
  - 2023-12-27 -> 2023-12-27 (resolved, 3 probe(s)): vendor application floor at or above the ex-date 2023-12-27: the event is absent from every chain in our history (3 probed day(s) across 2023-05-30 .. 2023-12-26, all event-out) [admitted by era failure-rate cliff: 144/144 = 100.0% of the gated days below 2023-12-27 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 144 of the 144 stored days below 2023-12-27 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind]
  - 2023-05-30 -> era pre-2023-12-27: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> era pre-2023-05-30: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> era pre-2023-04-06: no hypothesis -- ['2023-04-06', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> era pre-2023-02-03: no hypothesis -- ['2023-02-03', '2023-04-06', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> era pre-2022-11-29: no hypothesis -- ['2022-11-29', '2023-02-03', '2023-04-06', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> era pre-2022-07-26: no hypothesis -- ['2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> era pre-2022-05-06: no hypothesis -- ['2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> era pre-2022-03-09: no hypothesis -- ['2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> era pre-2021-12-17: no hypothesis -- ['2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> era pre-2021-09-08: no hypothesis -- ['2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> era pre-2020-10-28: no hypothesis -- ['2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> era pre-2020-03-05: no hypothesis -- ['2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-05-30 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2023-04-06 -> era pre-2023-12-27: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> era pre-2023-05-30: no hypothesis -- ['2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> era pre-2023-04-06: no hypothesis -- ['2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> era pre-2023-02-03: no hypothesis -- ['2023-02-03', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> era pre-2022-11-29: no hypothesis -- ['2022-11-29', '2023-02-03', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> era pre-2022-07-26: no hypothesis -- ['2022-07-26', '2022-11-29', '2023-02-03', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> era pre-2022-05-06: no hypothesis -- ['2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> era pre-2022-03-09: no hypothesis -- ['2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> era pre-2021-12-17: no hypothesis -- ['2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> era pre-2021-09-08: no hypothesis -- ['2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> era pre-2020-10-28: no hypothesis -- ['2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> era pre-2020-03-05: no hypothesis -- ['2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-04-06 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2023-02-03 -> era pre-2023-12-27: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> era pre-2023-05-30: no hypothesis -- ['2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> era pre-2023-04-06: no hypothesis -- ['2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> era pre-2023-02-03: no hypothesis -- ['2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> era pre-2022-11-29: no hypothesis -- ['2022-11-29', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> era pre-2022-07-26: no hypothesis -- ['2022-07-26', '2022-11-29', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> era pre-2022-05-06: no hypothesis -- ['2022-05-06', '2022-07-26', '2022-11-29', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> era pre-2022-03-09: no hypothesis -- ['2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> era pre-2021-12-17: no hypothesis -- ['2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> era pre-2021-09-08: no hypothesis -- ['2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> era pre-2020-10-28: no hypothesis -- ['2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> era pre-2020-03-05: no hypothesis -- ['2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2023-02-03 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2022-11-29 -> era pre-2023-12-27: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> era pre-2023-05-30: no hypothesis -- ['2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> era pre-2023-04-06: no hypothesis -- ['2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> era pre-2023-02-03: no hypothesis -- ['2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> era pre-2022-11-29: no hypothesis -- ['2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> era pre-2022-07-26: no hypothesis -- ['2022-07-26', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> era pre-2022-05-06: no hypothesis -- ['2022-05-06', '2022-07-26', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> era pre-2022-03-09: no hypothesis -- ['2022-03-09', '2022-05-06', '2022-07-26', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> era pre-2021-12-17: no hypothesis -- ['2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> era pre-2021-09-08: no hypothesis -- ['2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> era pre-2020-10-28: no hypothesis -- ['2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> era pre-2020-03-05: no hypothesis -- ['2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-11-29 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2022-07-26 -> era pre-2023-12-27: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> era pre-2023-05-30: no hypothesis -- ['2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> era pre-2023-04-06: no hypothesis -- ['2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> era pre-2023-02-03: no hypothesis -- ['2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> era pre-2022-11-29: no hypothesis -- ['2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> era pre-2022-07-26: no hypothesis -- ['2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> era pre-2022-05-06: no hypothesis -- ['2022-05-06', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> era pre-2022-03-09: no hypothesis -- ['2022-03-09', '2022-05-06', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> era pre-2021-12-17: no hypothesis -- ['2021-12-17', '2022-03-09', '2022-05-06', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> era pre-2021-09-08: no hypothesis -- ['2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> era pre-2020-10-28: no hypothesis -- ['2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> era pre-2020-03-05: no hypothesis -- ['2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-07-26 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2022-05-06 -> era pre-2023-12-27: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> era pre-2023-05-30: no hypothesis -- ['2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> era pre-2023-04-06: no hypothesis -- ['2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> era pre-2023-02-03: no hypothesis -- ['2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> era pre-2022-11-29: no hypothesis -- ['2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> era pre-2022-07-26: no hypothesis -- ['2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> era pre-2022-05-06: no hypothesis -- ['2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> era pre-2022-03-09: no hypothesis -- ['2022-03-09', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> era pre-2021-12-17: no hypothesis -- ['2021-12-17', '2022-03-09', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> era pre-2021-09-08: no hypothesis -- ['2021-09-08', '2021-12-17', '2022-03-09', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> era pre-2020-10-28: no hypothesis -- ['2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> era pre-2020-03-05: no hypothesis -- ['2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-05-06 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2022-03-09 -> era pre-2023-12-27: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> era pre-2023-05-30: no hypothesis -- ['2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> era pre-2023-04-06: no hypothesis -- ['2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> era pre-2023-02-03: no hypothesis -- ['2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> era pre-2022-11-29: no hypothesis -- ['2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> era pre-2022-07-26: no hypothesis -- ['2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> era pre-2022-05-06: no hypothesis -- ['2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> era pre-2022-03-09: no hypothesis -- ['2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> era pre-2021-12-17: no hypothesis -- ['2021-12-17', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> era pre-2021-09-08: no hypothesis -- ['2021-09-08', '2021-12-17', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> era pre-2020-10-28: no hypothesis -- ['2020-10-28', '2021-09-08', '2021-12-17', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> era pre-2020-03-05: no hypothesis -- ['2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2022-03-09 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2021-12-17 -> era pre-2023-12-27: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> era pre-2023-05-30: no hypothesis -- ['2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> era pre-2023-04-06: no hypothesis -- ['2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> era pre-2023-02-03: no hypothesis -- ['2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> era pre-2022-11-29: no hypothesis -- ['2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> era pre-2022-07-26: no hypothesis -- ['2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> era pre-2022-05-06: no hypothesis -- ['2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> era pre-2022-03-09: no hypothesis -- ['2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> era pre-2021-12-17: no hypothesis -- ['2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> era pre-2021-09-08: no hypothesis -- ['2021-09-08', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> era pre-2020-10-28: no hypothesis -- ['2020-10-28', '2021-09-08', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> era pre-2020-03-05: no hypothesis -- ['2020-03-05', '2020-10-28', '2021-09-08', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-12-17 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2021-09-08 -> era pre-2023-12-27: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> era pre-2023-05-30: no hypothesis -- ['2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> era pre-2023-04-06: no hypothesis -- ['2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> era pre-2023-02-03: no hypothesis -- ['2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> era pre-2022-11-29: no hypothesis -- ['2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> era pre-2022-07-26: no hypothesis -- ['2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> era pre-2022-05-06: no hypothesis -- ['2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> era pre-2022-03-09: no hypothesis -- ['2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> era pre-2021-12-17: no hypothesis -- ['2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> era pre-2021-09-08: no hypothesis -- ['2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> era pre-2020-10-28: no hypothesis -- ['2020-10-28', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> era pre-2020-03-05: no hypothesis -- ['2020-03-05', '2020-10-28', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06', '2020-03-05', '2020-10-28', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2021-09-08 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2020-10-28 -> era pre-2023-12-27: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> era pre-2023-05-30: no hypothesis -- ['2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> era pre-2023-04-06: no hypothesis -- ['2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> era pre-2023-02-03: no hypothesis -- ['2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> era pre-2022-11-29: no hypothesis -- ['2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> era pre-2022-07-26: no hypothesis -- ['2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> era pre-2022-05-06: no hypothesis -- ['2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> era pre-2022-03-09: no hypothesis -- ['2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> era pre-2021-12-17: no hypothesis -- ['2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> era pre-2021-09-08: no hypothesis -- ['2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> era pre-2020-10-28: no hypothesis -- ['2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> era pre-2020-03-05: no hypothesis -- ['2020-03-05', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06', '2020-03-05', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06', '2020-03-05', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06', '2020-03-05', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-10-28 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2020-03-05 -> era pre-2023-12-27: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> era pre-2023-05-30: no hypothesis -- ['2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> era pre-2023-04-06: no hypothesis -- ['2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> era pre-2023-02-03: no hypothesis -- ['2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> era pre-2022-11-29: no hypothesis -- ['2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> era pre-2022-07-26: no hypothesis -- ['2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> era pre-2022-05-06: no hypothesis -- ['2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> era pre-2022-03-09: no hypothesis -- ['2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> era pre-2021-12-17: no hypothesis -- ['2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> era pre-2021-09-08: no hypothesis -- ['2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> era pre-2020-10-28: no hypothesis -- ['2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> era pre-2020-03-05: no hypothesis -- ['2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2020-03-05 -> not searched: no day of a provable era carries this event with a factor to drop
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
  - 2018-03-20 -> era pre-2023-12-27: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> era pre-2023-05-30: no hypothesis -- ['2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> era pre-2023-04-06: no hypothesis -- ['2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> era pre-2023-02-03: no hypothesis -- ['2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> era pre-2022-11-29: no hypothesis -- ['2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> era pre-2022-07-26: no hypothesis -- ['2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> era pre-2022-05-06: no hypothesis -- ['2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> era pre-2022-03-09: no hypothesis -- ['2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> era pre-2021-12-17: no hypothesis -- ['2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> era pre-2021-09-08: no hypothesis -- ['2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> era pre-2020-10-28: no hypothesis -- ['2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> era pre-2020-03-05: no hypothesis -- ['2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> era pre-2018-03-20: no hypothesis -- ['2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2018-03-20 -> not searched: no day of a provable era carries this event with a factor to drop
  - 2017-04-11 -> era pre-2023-12-27: no hypothesis -- ['2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> era pre-2023-05-30: no hypothesis -- ['2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> era pre-2023-04-06: no hypothesis -- ['2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> era pre-2023-02-03: no hypothesis -- ['2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> era pre-2022-11-29: no hypothesis -- ['2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> era pre-2022-07-26: no hypothesis -- ['2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> era pre-2022-05-06: no hypothesis -- ['2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> era pre-2022-03-09: no hypothesis -- ['2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> era pre-2021-12-17: no hypothesis -- ['2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> era pre-2021-09-08: no hypothesis -- ['2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> era pre-2020-10-28: no hypothesis -- ['2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> era pre-2020-03-05: no hypothesis -- ['2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> era pre-2017-04-11: no hypothesis -- ['2018-03-20', '2018-11-06', '2020-03-05', '2020-10-28', '2021-09-08', '2021-12-17', '2022-03-09', '2022-05-06', '2022-07-26', '2022-11-29', '2023-02-03', '2023-04-06', '2023-05-30', '2023-12-27'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - 2017-04-11 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2026-04-30 -> no splice (resolved, 2 probe(s)): applied on the oldest stored day too (2018-11-06): no splice inside our history, the chain is unchanged
  - [round 2] 2025-08-26 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2024-09-10 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2024-05-24 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 2] 2023-05-30 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2023-05-30 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2023-05-30 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2023-05-30 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2023-04-06 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2023-04-06 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2023-04-06 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2023-04-06 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2023-02-03 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2023-02-03 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2023-02-03 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2023-02-03 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2022-11-29 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2022-11-29 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2022-11-29 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2022-11-29 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2022-07-26 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2022-07-26 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2022-07-26 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2022-07-26 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2022-05-06 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2022-05-06 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2022-05-06 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2022-05-06 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2022-03-09 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2022-03-09 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2022-03-09 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2022-03-09 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2021-12-17 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2021-12-17 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2021-12-17 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2021-12-17 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2021-09-08 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2021-09-08 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2021-09-08 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2021-09-08 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2020-10-28 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2020-10-28 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2020-10-28 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2020-10-28 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2020-03-05 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2020-03-05 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2020-03-05 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2020-03-05 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2018-11-06 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2018-11-06 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-03-20'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2018-11-06 -> 2018-11-06 (resolved, 3 probe(s)): vendor application floor at or above the ex-date 2018-11-06: the event is absent from every chain in our history (3 probed day(s) across 2018-03-20 .. 2018-11-05, all event-out) [admitted by era failure-rate cliff: 156/156 = 100.0% of the gated days below 2018-11-06 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 156 of the 156 stored days below 2018-11-06 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind]
  - [round 2] 2018-03-20 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2018-03-20 -> era pre-2018-03-20: no hypothesis -- ['2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2018-03-20 -> era pre-2017-04-11: no hypothesis -- ['2017-04-11', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2018-03-20 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 2] 2017-04-11 -> era pre-2018-11-06: no hypothesis -- ['2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2017-04-11 -> era pre-2018-03-20: no hypothesis -- ['2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2017-04-11 -> era pre-2017-04-11: no hypothesis -- ['2018-03-20', '2018-11-06'] carry no committed source, so the era holds more than one unknown; nothing honest to test a floor against
  - [round 2] 2017-04-11 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 3] 2025-08-26 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2024-09-10 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2024-05-24 -> not searched: no day of a provable era carries this event with a factor to drop; and no signature admits an un-provable era's days (Q-11 addendum 4 clause i)
  - [round 3] 2023-05-30 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 3] 2023-04-06 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 3] 2023-02-03 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 3] 2022-11-29 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 3] 2022-07-26 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 3] 2022-05-06 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 3] 2022-03-09 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 3] 2021-12-17 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 3] 2021-09-08 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 3] 2020-10-28 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 3] 2020-03-05 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 3] 2018-03-20 -> not searched: no day of a provable era carries this event with a factor to drop
  - [round 3] 2017-04-11 -> not searched: no day of a provable era carries this event with a factor to drop

### 3d. AUCTION RELIEF -- the deferred +5.0% ceiling, answered (QUESTIONS.md Q-12 addendum 2)

The architect's ruling: **"the ceiling stays"**. `VOLUME_GAP_MIN_PCT` and `VOLUME_GAP_MAX_PCT` are byte-identical (`[-0.1%, 5.0%]`) and `volume_gate` is untouched. A gate-1 failure ABOVE the ceiling is separately examined and relieved **IFF ALL FOUR** hold: (a) the failure is above the ceiling, never below the floor; (b) the stored 1-min HIGH equals the raw daily HIGH and the 1-min LOW the raw daily LOW, EXACTLY; (c) the first stamp's open equals the raw daily open, exactly; (d) the shortfall is <= 20.0%. Data LOSS clips extremes; a day with intact extremes, a matching opening print and only volume short is a thin day whose pre-open auction exceeds 5% -- a market property.

**414 symbol-day(s) relieved** across 123 symbol(s), out of 432,304 gated days on ALL processed symbols. Of those, **411** land on SETTLED symbols (417,985 gated days) and are the only ones the coverage headline counts; the remaining 3 sit on QUARANTINED symbols, whose whole history is excluded anyway. REVIEW_5B finding C9: the two populations are now named apart instead of an all-symbol numerator being printed over a settled-only denominator. Relieved days are counted SEPARATELY everywhere in this report -- the strict gate-1 numerator is never overwritten.

| Symbol | Gate-1 strict | Auction-relief pass | Effective | Median shortfall | Relieved days also carrying tradeless minutes | Status |
|---|---|---|---|---|---|---|
| HDFCBANK | 2334/2433 (95.9%) | 43 | 2377/2433 (97.7%) | 6.40% | 1 | settled |
| PGEL | 2364/2433 (97.2%) | 18 | 2382/2433 (97.9%) | 8.62% | 17 | settled |
| OBEROIRLTY | 2398/2433 (98.6%) | 17 | 2415/2433 (99.3%) | 7.40% | 4 | settled |
| SUZLON | 2381/2432 (97.9%) | 15 | 2396/2432 (98.5%) | 7.22% | 0 | settled |
| ADANIENT | 2404/2433 (98.8%) | 13 | 2417/2433 (99.3%) | 6.61% | 0 | settled |
| TATAPOWER | 2406/2433 (98.9%) | 13 | 2419/2433 (99.4%) | 7.11% | 0 | settled |
| SAIL | 2404/2433 (98.8%) | 12 | 2416/2433 (99.3%) | 8.50% | 0 | settled |
| ICICIBANK | 2399/2433 (98.6%) | 10 | 2409/2433 (99.0%) | 5.90% | 1 | settled |
| PAYTM | 1144/1165 (98.2%) | 9 | 1153/1165 (99.0%) | 12.26% | 0 | settled |
| ADANIPOWER | 2405/2433 (98.8%) | 8 | 2413/2433 (99.2%) | 6.45% | 1 | settled |
| BHARTIARTL | 2408/2433 (99.0%) | 8 | 2416/2433 (99.3%) | 5.88% | 0 | settled |
| FORCEMOT | 1618/1646 (98.3%) | 8 | 1626/1646 (98.8%) | 8.16% | 8 | settled |
| DLF | 2410/2433 (99.1%) | 7 | 2417/2433 (99.3%) | 5.73% | 0 | settled |
| PATANJALI | 838/857 (97.8%) | 7 | 845/857 (98.6%) | 6.89% | 0 | settled |
| INOXWIND | 2408/2433 (99.0%) | 6 | 2414/2433 (99.2%) | 9.02% | 4 | settled |
| IREDA | 647/662 (97.7%) | 6 | 653/662 (98.6%) | 11.40% | 0 | settled |
| JSWENERGY | 2410/2433 (99.1%) | 5 | 2415/2433 (99.3%) | 8.70% | 2 | settled |
| MANAPPURAM | 2417/2434 (99.3%) | 5 | 2422/2434 (99.5%) | 6.27% | 0 | settled |
| SOLARINDS | 2413/2433 (99.2%) | 5 | 2418/2433 (99.4%) | 8.29% | 4 | settled |
| TIINDIA | 2141/2164 (98.9%) | 5 | 2146/2164 (99.2%) | 6.73% | 5 | settled |
| CGPOWER | 2306/2325 (99.2%) | 4 | 2310/2325 (99.4%) | 7.22% | 2 | settled |
| KEI | 2413/2432 (99.2%) | 4 | 2417/2432 (99.4%) | 9.15% | 0 | settled |
| LAURUSLABS | 2362/2380 (99.2%) | 4 | 2366/2380 (99.4%) | 6.74% | 2 | settled |
| M&M | 2414/2433 (99.2%) | 4 | 2418/2433 (99.4%) | 6.55% | 0 | settled |
| NHPC | 2415/2432 (99.3%) | 4 | 2419/2432 (99.5%) | 6.67% | 0 | settled |
| NMDC | 2053/2435 (84.3%) | 4 | 2057/2435 (84.5%) | 13.16% | 0 | settled |
| POWERGRID | 2391/2434 (98.2%) | 4 | 2395/2434 (98.4%) | 7.36% | 0 | settled |
| RELIANCE | 2408/2433 (99.0%) | 4 | 2412/2433 (99.1%) | 6.70% | 0 | settled |
| TCS | 2409/2433 (99.0%) | 4 | 2413/2433 (99.2%) | 11.84% | 0 | settled |
| 360ONE | 862/871 (99.0%) | 3 | 865/871 (99.3%) | 8.08% | 0 | settled |
| AXISBANK | 2414/2432 (99.3%) | 3 | 2417/2432 (99.4%) | 5.19% | 0 | settled |
| BRITANNIA | 2415/2433 (99.3%) | 3 | 2418/2433 (99.4%) | 7.74% | 0 | settled |
| DABUR | 2417/2433 (99.3%) | 3 | 2420/2433 (99.5%) | 12.00% | 0 | settled |
| EICHERMOT | 2413/2432 (99.2%) | 3 | 2416/2432 (99.3%) | 5.82% | 0 | settled |
| FORTIS | 2414/2433 (99.2%) | 3 | 2417/2433 (99.3%) | 7.33% | 1 | settled |
| GVT&D | 418/429 (97.4%) | 3 | 421/429 (98.1%) | 7.49% | 1 | settled |
| HDFCLIFE | 2136/2153 (99.2%) | 3 | 2139/2153 (99.3%) | 5.32% | 0 | settled |
| IDEA | 2410/2433 (99.1%) | 3 | 2413/2433 (99.2%) | 9.93% | 0 | settled |
| INFY | 2414/2434 (99.2%) | 3 | 2417/2434 (99.3%) | 5.47% | 0 | settled |
| KOTAKBANK | 2414/2433 (99.2%) | 3 | 2417/2433 (99.3%) | 6.62% | 0 | settled |
| MOTILALOFS | 2410/2433 (99.1%) | 3 | 2413/2433 (99.2%) | 10.96% | 0 | settled |
| NAUKRI | 2414/2433 (99.2%) | 3 | 2417/2433 (99.3%) | 11.58% | 2 | settled |
| NBCC | 2416/2433 (99.3%) | 3 | 2419/2433 (99.4%) | 9.75% | 0 | settled |
| NYKAA | 1166/1171 (99.6%) | 3 | 1169/1171 (99.8%) | 6.26% | 0 | settled |
| PNBHOUSING | 2393/2412 (99.2%) | 3 | 2396/2412 (99.3%) | 6.52% | 1 | settled |
| PREMIERENE | 470/473 (99.4%) | 3 | 473/473 (100.0%) | 6.97% | 1 | settled |
| ABB | 2418/2433 (99.4%) | 2 | 2420/2433 (99.5%) | 6.09% | 1 | settled |
| ADANIGREEN | 1994/2009 (99.3%) | 2 | 1996/2009 (99.4%) | 5.99% | 1 | settled |
| BAJFINANCE | 2414/2433 (99.2%) | 2 | 2416/2433 (99.3%) | 11.27% | 0 | settled |
| BANDHANBNK | 2050/2065 (99.3%) | 2 | 2052/2065 (99.4%) | 5.30% | 0 | settled |
| CDSL | 2232/2248 (99.3%) | 2 | 2234/2248 (99.4%) | 11.99% | 0 | settled |
| CHOLAFIN | 2417/2433 (99.3%) | 2 | 2419/2433 (99.4%) | 5.78% | 0 | settled |
| CIPLA | 2418/2433 (99.4%) | 2 | 2420/2433 (99.5%) | 8.96% | 0 | settled |
| CROMPTON | 2417/2433 (99.3%) | 2 | 2419/2433 (99.4%) | 7.46% | 0 | settled |
| CUMMINSIND | 2417/2433 (99.3%) | 2 | 2419/2433 (99.4%) | 15.57% | 0 | settled |
| DMART | 2300/2317 (99.3%) | 2 | 2302/2317 (99.4%) | 14.88% | 0 | settled |
| GLENMARK | 2418/2433 (99.4%) | 2 | 2420/2433 (99.5%) | 6.82% | 0 | settled |
| GODREJCP | 2414/2433 (99.2%) | 2 | 2416/2433 (99.3%) | 10.97% | 0 | settled |
| ICICIPRULI | 2416/2433 (99.3%) | 2 | 2418/2433 (99.4%) | 9.58% | 0 | settled |
| INDHOTEL | 2418/2433 (99.4%) | 2 | 2420/2433 (99.5%) | 12.97% | 0 | settled |
| INDIGO | 2412/2433 (99.1%) | 2 | 2414/2433 (99.2%) | 7.57% | 0 | settled |
| INDUSINDBK | 2416/2433 (99.3%) | 2 | 2418/2433 (99.4%) | 7.17% | 0 | settled |
| JIOFIN | 721/727 (99.2%) | 2 | 723/727 (99.4%) | 12.35% | 0 | settled |
| LODHA | 1280/1311 (97.6%) | 2 | 1282/1311 (97.8%) | 7.72% | 1 | settled |
| MAXHEALTH | 1465/1472 (99.5%) | 2 | 1467/1472 (99.7%) | 6.11% | 0 | settled |
| MCX | 2417/2433 (99.3%) | 2 | 2419/2433 (99.4%) | 5.59% | 0 | settled |
| MFSL | 2417/2433 (99.3%) | 2 | 2419/2433 (99.4%) | 8.33% | 1 | settled |
| PETRONET | 2236/2435 (91.8%) | 2 | 2238/2435 (91.9%) | 6.80% | 0 | settled |
| PHOENIXLTD | 2411/2433 (99.1%) | 2 | 2413/2433 (99.2%) | 15.24% | 2 | settled |
| PIDILITIND | 2419/2435 (99.3%) | 2 | 2421/2435 (99.4%) | 6.01% | 0 | settled |
| POLYCAB | 1793/1802 (99.5%) | 2 | 1795/1802 (99.6%) | 5.30% | 0 | settled |
| POWERINDIA | 1558/1570 (99.2%) | 2 | 1560/1570 (99.4%) | 7.77% | 2 | settled |
| SBICARD | 1574/1580 (99.6%) | 2 | 1576/1580 (99.7%) | 10.65% | 0 | settled |
| SUNPHARMA | 2417/2433 (99.3%) | 2 | 2419/2433 (99.4%) | 6.08% | 0 | settled |
| TATACONSUM | 1586/1591 (99.7%) | 2 | 1588/1591 (99.8%) | 12.09% | 0 | settled |
| ULTRACEMCO | 2418/2433 (99.4%) | 2 | 2420/2433 (99.5%) | 10.32% | 0 | settled |
| ADANIENSOL | 725/727 (99.7%) | 1 | 726/727 (99.9%) | 7.07% | 0 | settled |
| ADANIPORTS | 2414/2433 (99.2%) | 1 | 2415/2433 (99.3%) | 5.02% | 0 | settled |
| AMBER | 2086/2103 (99.2%) | 1 | 2087/2103 (99.2%) | 5.77% | 1 | settled |
| AMBUJACEM | 2417/2432 (99.4%) | 1 | 2418/2432 (99.4%) | 6.89% | 0 | settled |
| APOLLOHOSP | 2419/2433 (99.4%) | 1 | 2420/2433 (99.5%) | 7.71% | 0 | settled |
| ASIANPAINT | 2421/2434 (99.5%) | 1 | 2422/2434 (99.5%) | 6.16% | 0 | settled |
| ASTRAL | 1702/2434 (69.9%) | 1 | 1703/2434 (70.0%) | 14.26% | 0 | quarantined |
| BAJAJHLDNG | 2410/2433 (99.1%) | 1 | 2411/2433 (99.1%) | 9.93% | 1 | settled |
| BANKINDIA | 2418/2433 (99.4%) | 1 | 2419/2433 (99.4%) | 6.39% | 0 | settled |
| BLUESTARCO | 2413/2433 (99.2%) | 1 | 2414/2433 (99.2%) | 5.96% | 1 | settled |
| COALINDIA | 2419/2433 (99.4%) | 1 | 2420/2433 (99.5%) | 6.98% | 0 | settled |
| COCHINSHIP | 2201/2219 (99.2%) | 1 | 2202/2219 (99.2%) | 12.72% | 0 | settled |
| COFORGE | 1467/1473 (99.6%) | 1 | 1468/1473 (99.7%) | 6.35% | 0 | settled |
| COLPAL | 2417/2433 (99.3%) | 1 | 2418/2433 (99.4%) | 17.48% | 0 | settled |
| CONCOR | 2420/2433 (99.5%) | 1 | 2421/2433 (99.5%) | 19.07% | 0 | settled |
| FEDERALBNK | 2419/2433 (99.4%) | 1 | 2420/2433 (99.5%) | 8.10% | 0 | settled |
| GODFRYPHLP | 2417/2433 (99.3%) | 1 | 2418/2433 (99.4%) | 6.24% | 0 | settled |
| GODREJPROP | 2415/2433 (99.3%) | 1 | 2416/2433 (99.3%) | 5.58% | 0 | settled |
| GRASIM | 2417/2433 (99.3%) | 1 | 2418/2433 (99.4%) | 11.71% | 0 | settled |
| HAL | 2051/2064 (99.4%) | 1 | 2052/2064 (99.4%) | 8.22% | 1 | settled |
| HCLTECH | 2416/2433 (99.3%) | 1 | 2417/2433 (99.3%) | 6.91% | 0 | settled |
| HEROMOTOCO | 2417/2433 (99.3%) | 1 | 2418/2433 (99.4%) | 13.14% | 0 | settled |
| HINDZINC | 2417/2433 (99.3%) | 1 | 2418/2433 (99.4%) | 5.95% | 0 | settled |
| HYUNDAI | 437/439 (99.5%) | 1 | 438/439 (99.8%) | 15.33% | 1 | settled |
| ICICIGI | 2170/2187 (99.2%) | 1 | 2171/2187 (99.3%) | 8.75% | 0 | settled |
| IEX | 1152/2173 (53.0%) | 1 | 1153/2173 (53.1%) | 7.41% | 0 | quarantined |
| ITC | 2415/2432 (99.3%) | 1 | 2416/2432 (99.3%) | 5.00% | 0 | settled |
| JUBLFOOD | 2097/2435 (86.1%) | 1 | 2098/2435 (86.2%) | 14.40% | 0 | settled |
| KAYNES | 912/915 (99.7%) | 1 | 913/915 (99.8%) | 14.54% | 0 | settled |
| KPITTECH | 1798/1802 (99.8%) | 1 | 1799/1802 (99.8%) | 6.45% | 1 | settled |
| LUPIN | 2417/2432 (99.4%) | 1 | 2418/2432 (99.4%) | 7.88% | 0 | settled |
| MPHASIS | 2417/2433 (99.3%) | 1 | 2418/2433 (99.4%) | 8.56% | 0 | settled |
| MUTHOOTFIN | 2416/2432 (99.3%) | 1 | 2417/2432 (99.4%) | 15.46% | 1 | settled |
| NATIONALUM | 2418/2433 (99.4%) | 1 | 2419/2433 (99.4%) | 5.48% | 0 | settled |
| NTPC | 1844/2432 (75.8%) | 1 | 1845/2432 (75.9%) | 5.62% | 1 | quarantined |
| OFSS | 2416/2433 (99.3%) | 1 | 2417/2433 (99.3%) | 5.27% | 0 | settled |
| PAGEIND | 2406/2433 (98.9%) | 1 | 2407/2433 (98.9%) | 10.91% | 1 | settled |
| PIIND | 2417/2433 (99.3%) | 1 | 2418/2433 (99.4%) | 5.19% | 1 | settled |
| PNB | 2419/2433 (99.4%) | 1 | 2420/2433 (99.5%) | 5.95% | 0 | settled |
| POLICYBZR | 1162/1167 (99.6%) | 1 | 1163/1167 (99.7%) | 6.67% | 0 | settled |
| RBLBANK | 2418/2433 (99.4%) | 1 | 2419/2433 (99.4%) | 5.81% | 0 | settled |
| SHRIRAMFIN | 892/895 (99.7%) | 1 | 893/895 (99.8%) | 9.40% | 0 | settled |
| SRF | 2422/2435 (99.5%) | 1 | 2423/2435 (99.5%) | 5.30% | 0 | settled |
| SWIGGY | 422/423 (99.8%) | 1 | 423/423 (100.0%) | 15.11% | 1 | settled |
| TORNTPHARM | 2429/2435 (99.8%) | 1 | 2430/2435 (99.8%) | 13.46% | 0 | settled |
| TRENT | 2416/2433 (99.3%) | 1 | 2417/2433 (99.3%) | 5.69% | 1 | settled |
| ZYDUSLIFE | 1087/1090 (99.7%) | 1 | 1088/1090 (99.8%) | 5.30% | 0 | settled |

**Decision B122, recorded not assumed.** The completeness ruling excludes a day for missing minutes only "ON A DAY WHERE GATE-1 ALSO FAILS". A relieved day's gate-1 verdict is *pass (by relief)*, so it is handed to gate 2 as reconciled. The relief's own conditions (b) and (c) are the direct evidence that nothing was lost -- exactly the hypothesis the missing-minutes trigger exists to catch -- and the thin days relief targets are precisely the days that carry tradeless minutes, so the other reading would cancel the relief it had just granted. The last column above measures how often it mattered: 77 of 414 relieved days also carried more than 15 tradeless minutes.

### 3e. Floors in UN-PROVABLE eras -- the FINAL data ruling (QUESTIONS.md Q-11 addendum 4)

The architect's ruling: "an un-provable era is a conclusion under the floor-less model; where the floor itself caused unprovability, the hunt was locked out of exactly the eras needing it." Floor hypotheses may now be tested inside un-provable eras under four guards: (i) hunting is SIGNATURE-GATED, never blanket; (ii) the one-fresh-unknown-per-era discipline holds -- the floor is the fresh unknown and previously committed sources combine with it; (iii) acceptance is unchanged -- the era stands only if it becomes provable under normal per-day price containment and gate-1 re-gating; (iv) full provenance in the map.

**Clause (i) -- what the signature gate admitted.** An event qualifies only by the gate-3 raw-gap-near-zero signature (the measured raw gap is strictly nearer 0 than the healthy `k - 1`) or by an era failure-rate cliff (>= 95% of the gated days below the ex-date fail gate 1, over at least 20 days). Everything else keeps exactly its pre-ruling domain.

**Every floor this run MEASURED** -- event, the splice date the bisection returned, and what it cost. A floor AT the ex-date means the vendor never applied that event to one day of our history; a floor inside the span means it applied it from that date on.

| Symbol | Event ex-date | Measured floor | Probes | What the search found |
|---|---|---|---|---|
| ASTRAL | 2023-03-14 | 2021-03-08 | 11 | vendor application floor 2021-03-08: the event is absent from every chain before it (2021-03-05 probed event-out) and applied from it on |
| BLUESTARCO | 2023-06-20 | 2021-06-15 | 13 | vendor application floor 2021-06-15: the event is absent from every chain before it (2021-06-14 probed event-out) and applied from it on |
| CANBK | 2024-05-15 | 2022-05-10 | 13 | vendor application floor 2022-05-10: the event is absent from every chain before it (2022-05-09 probed event-out) and applied from it on |
| COCHINSHIP | 2024-01-10 | 2022-01-04 | 12 | vendor application floor 2022-01-04: the event is absent from every chain before it (2022-01-03 probed event-out) and applied from it on |
| DIXON | 2021-03-18 | 2018-10-01 | 12 | vendor application floor 2018-10-01: the event is absent from every chain before it (2018-09-28 probed event-out) and applied from it on |
| HAL | 2023-09-28 | 2021-09-24 | 12 | vendor application floor 2021-09-24: the event is absent from every chain before it (2021-09-23 probed event-out) and applied from it on |
| HINDPETRO | 2019-06-06 | 2019-06-06 | 3 | vendor application floor at or above the ex-date 2019-06-06: the event is absent from every chain in our history (3 probed day(s) across 2019-02-14 .. 2019-06-04, all event-out) |
| IEX | 2021-12-03 | 2019-10-01 | 12 | vendor application floor 2019-10-01: the event is absent from every chain before it (2019-09-30 probed event-out) and applied from it on |
| INOXWIND | 2024-05-24 | 2022-05-19 | 13 | vendor application floor 2022-05-19: the event is absent from every chain before it (2022-05-18 probed event-out) and applied from it on |
| JUBLFOOD | 2022-04-19 | 2018-01-18 | 12 | vendor application floor 2018-01-18: the event is absent from every chain before it (2018-01-17 probed event-out) and applied from it on |
| MOTILALOFS | 2024-06-10 | 2022-06-03 | 13 | vendor application floor 2022-06-03: the event is absent from every chain before it (2022-06-02 probed event-out) and applied from it on |
| NESTLEIND | 2024-01-05 | 2021-12-31 | 12 | vendor application floor 2021-12-31: the event is absent from every chain before it (2021-12-30 probed event-out) and applied from it on |
| NTPC | 2019-02-06 | 2019-02-06 | 3 | vendor application floor at or above the ex-date 2019-02-06: the event is absent from every chain in our history (3 probed day(s) across 2016-10-03 .. 2019-02-05, all event-out) |
| PERSISTENT | 2024-03-28 | 2022-03-24 | 13 | vendor application floor 2022-03-24: the event is absent from every chain before it (2022-03-23 probed event-out) and applied from it on |
| PFC | 2023-09-21 | 2021-09-16 | 12 | vendor application floor 2021-09-16: the event is absent from every chain before it (2021-09-15 probed event-out) and applied from it on |
| PNBHOUSING | 2023-04-05 | 2019-11-05 | 13 | vendor application floor 2019-11-05: the event is absent from every chain before it (2019-11-04 probed event-out) and applied from it on |
| RELIANCE | 2023-07-20 | 2022-01-05 | 12 | vendor application floor 2022-01-05: the event is absent from every chain before it (2022-01-04 probed event-out) and applied from it on |
| VEDL | 2023-12-27 | 2023-12-27 | 3 | vendor application floor at or above the ex-date 2023-12-27: the event is absent from every chain in our history (3 probed day(s) across 2023-05-30 .. 2023-12-26, all event-out) |
| VEDL | 2018-11-06 | 2018-11-06 | 3 | vendor application floor at or above the ex-date 2018-11-06: the event is absent from every chain in our history (3 probed day(s) across 2018-03-20 .. 2018-11-05, all event-out) |

**Every event the gate ADMITTED into an un-provable era**, with the measurement that admitted it. An event absent from this table was never hunted there, however badly its span fails -- that is the ruling's "never blanket".

| Symbol | Event | Admitting signature |
|---|---|---|
| APLAPOLLO | 2020-12-15 | gate-1P failure cluster: the oldest 536 of the 1041 stored days below 2020-12-15 fail gate 1P as a contiguous block (>= 95%) while the 505 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| ASTRAL | 2019-09-16 | era failure-rate cliff: 729/729 = 100.0% of the gated days below 2019-09-16 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 729 of the 729 stored days below 2019-09-16 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| ASTRAL | 2021-03-18 | era failure-rate cliff: 368/375 = 98.1% of the gated days below 2021-03-18 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 368 of the 375 stored days below 2021-03-18 fail gate 1P as a contiguous block (>= 95%) while the 7 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| AUBANK | 2022-06-09 | gate-1P failure cluster: the oldest 192 of the 1217 stored days below 2022-06-09 fail gate 1P as a contiguous block (>= 95%) while the 1025 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| BAJAJFINSV | 2022-09-13 | gate-1P failure cluster: the oldest 785 of the 1285 stored days below 2022-09-13 fail gate 1P as a contiguous block (>= 95%) while the 500 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| BEL | 2017-03-16 | era failure-rate cliff: 112/112 = 100.0% of the gated days below 2017-03-16 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 112 of the 112 stored days below 2017-03-16 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| BEL | 2017-09-28 | era failure-rate cliff: 134/134 = 100.0% of the gated days below 2017-09-28 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 134 of the 134 stored days below 2017-09-28 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| BEL | 2022-09-15 | gate-1P failure cluster: the oldest 729 of the 1229 stored days below 2022-09-15 fail gate 1P as a contiguous block (>= 95%) while the 500 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| BLUESTARCO | 2023-06-20 | gate-1P failure cluster: the oldest 1161 of the 1661 stored days below 2023-06-20 fail gate 1P as a contiguous block (>= 95%) while the 500 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| BPCL | 2017-02-28 | era failure-rate cliff: 101/101 = 100.0% of the gated days below 2017-02-28 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 101 of the 101 stored days below 2017-02-28 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| BPCL | 2017-07-13 | era failure-rate cliff: 92/92 = 100.0% of the gated days below 2017-07-13 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 92 of the 92 stored days below 2017-07-13 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| BSE | 2017-08-24 | era failure-rate cliff: 137/137 = 100.0% of the gated days below 2017-08-24 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 137 of the 137 stored days below 2017-08-24 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| BSE | 2018-07-25 | gate-1P failure cluster: the oldest 81 of the 229 stored days below 2018-07-25 fail gate 1P as a contiguous block (>= 95%) while the 148 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| CANBK | 2017-02-17 | era failure-rate cliff: 95/95 = 100.0% of the gated days below 2017-02-17 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 95 of the 95 stored days below 2017-02-17 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| CANBK | 2022-06-15 | era failure-rate cliff: 1289/1315 = 98.0% of the gated days below 2022-06-15 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 1289 of the 1315 stored days below 2022-06-15 fail gate 1P as a contiguous block (>= 95%) while the 26 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| COCHINSHIP | 2022-02-21 | gate-1P failure cluster: the oldest 240 of the 273 stored days below 2022-02-21 fail gate 1P as a contiguous block (>= 95%) while the 33 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| DIXON | 2021-03-18 | gate-1P failure cluster: the oldest 257 of the 866 stored days below 2021-03-18 fail gate 1P as a contiguous block (>= 95%) while the 609 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| GAIL | 2017-03-09 | gate-3 raw-gap-near-zero: \|raw gap\| 2.52% is nearer 0 than the event's own step 25.00% (k=0.75), adjusted gap 29.97% -- both closes are already in the same price domain AND era failure-rate cliff: 108/108 = 100.0% of the gated days below 2017-03-09 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 108 of the 108 stored days below 2017-03-09 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| GAIL | 2018-03-27 | era failure-rate cliff: 260/260 = 100.0% of the gated days below 2018-03-27 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 260 of the 260 stored days below 2018-03-27 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| GAIL | 2019-07-09 | gate-1P failure cluster: the oldest 64 of the 316 stored days below 2019-07-09 fail gate 1P as a contiguous block (>= 95%) while the 252 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| GRASIM | 2024-01-10 | gate-1P failure cluster: the oldest 1103 of the 1603 stored days below 2024-01-10 fail gate 1P as a contiguous block (>= 95%) while the 500 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| HAL | 2023-09-28 | gate-1P failure cluster: the oldest 373 of the 872 stored days below 2023-09-28 fail gate 1P as a contiguous block (>= 95%) while the 499 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| HINDPETRO | 2017-03-01 | era failure-rate cliff: 102/102 = 100.0% of the gated days below 2017-03-01 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 102 of the 102 stored days below 2017-03-01 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| HINDPETRO | 2017-07-11 | gate-3 raw-gap-near-zero: \|raw gap\| 0.35% is nearer 0 than the event's own step 33.33% (k=0.6666666666666666666666666667), adjusted gap 49.47% -- both closes are already in the same price domain AND era failure-rate cliff: 89/89 = 100.0% of the gated days below 2017-07-11 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 89 of the 89 stored days below 2017-07-11 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| HINDPETRO | 2018-02-28 | era failure-rate cliff: 159/159 = 100.0% of the gated days below 2018-02-28 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 159 of the 159 stored days below 2018-02-28 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| HINDPETRO | 2019-02-14 | era failure-rate cliff: 238/238 = 100.0% of the gated days below 2019-02-14 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 238 of the 238 stored days below 2019-02-14 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| HINDPETRO | 2019-06-06 | era failure-rate cliff: 73/73 = 100.0% of the gated days below 2019-06-06 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 73 of the 73 stored days below 2019-06-06 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| IEX | 2018-10-19 | era failure-rate cliff: 246/246 = 100.0% of the gated days below 2018-10-19 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 246 of the 246 stored days below 2018-10-19 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| IEX | 2021-12-03 | era failure-rate cliff: 773/773 = 100.0% of the gated days below 2021-12-03 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 233 of the 773 stored days below 2021-12-03 fail gate 1P as a contiguous block (>= 95%) while the 540 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| INOXWIND | 2024-05-24 | gate-1P failure cluster: the oldest 1391 of the 1891 stored days below 2024-05-24 fail gate 1P as a contiguous block (>= 95%) while the 500 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| IOC | 2016-10-18 | gate-3 raw-gap-near-zero: \|raw gap\| 0.17% is nearer 0 than the event's own step 50.00% (k=0.5), adjusted gap 100.34% -- both closes are already in the same price domain |
| IOC | 2017-02-09 | era failure-rate cliff: 80/80 = 100.0% of the gated days below 2017-02-09 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 80 of the 80 stored days below 2017-02-09 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| IOC | 2018-02-08 | era failure-rate cliff: 248/248 = 100.0% of the gated days below 2018-02-08 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 248 of the 248 stored days below 2018-02-08 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| IOC | 2018-03-15 | gate-3 raw-gap-near-zero: \|raw gap\| 2.77% is nearer 0 than the event's own step 50.00% (k=0.5), adjusted gap 94.45% -- both closes are already in the same price domain AND era failure-rate cliff: 23/23 = 100.0% of the gated days below 2018-03-15 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 23 of the 23 stored days below 2018-03-15 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| IOC | 2020-03-23 | gate-1P failure cluster: the oldest 308 of the 308 stored days below 2020-03-23 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| IOC | 2021-02-09 | gate-1P failure cluster: the oldest 221 of the 221 stored days below 2021-02-09 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| IOC | 2021-03-23 | gate-1P failure cluster: the oldest 29 of the 29 stored days below 2021-03-23 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| IOC | 2021-11-11 | gate-1P failure cluster: the oldest 157 of the 157 stored days below 2021-11-11 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| IOC | 2022-02-09 | gate-1P failure cluster: the oldest 62 of the 62 stored days below 2022-02-09 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| IOC | 2022-06-30 | gate-3 raw-gap-near-zero: \|raw gap\| 1.43% is nearer 0 than the event's own step 33.33% (k=0.6666666666666666666666666667), adjusted gap 52.15% -- both closes are already in the same price domain AND gate-1P failure cluster: the oldest 96 of the 96 stored days below 2022-06-30 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| JUBLFOOD | 2018-06-21 | gate-1P failure cluster: the oldest 323 of the 427 stored days below 2018-06-21 fail gate 1P as a contiguous block (>= 95%) while the 104 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| LODHA | 2023-05-31 | gate-1P failure cluster: the oldest 25 of the 525 stored days below 2023-05-31 fail gate 1P as a contiguous block (>= 95%) while the 500 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| MOTILALOFS | 2024-06-10 | gate-1P failure cluster: the oldest 1402 of the 1902 stored days below 2024-06-10 fail gate 1P as a contiguous block (>= 95%) while the 500 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| NESTLEIND | 2020-10-29 | era failure-rate cliff: 1009/1009 = 100.0% of the gated days below 2020-10-29 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 1009 of the 1009 stored days below 2020-10-29 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| NESTLEIND | 2024-01-05 | gate-1P failure cluster: the oldest 290 of the 789 stored days below 2024-01-05 fail gate 1P as a contiguous block (>= 95%) while the 499 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| NMDC | 2017-03-16 | era failure-rate cliff: 112/112 = 100.0% of the gated days below 2017-03-16 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 112 of the 112 stored days below 2017-03-16 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| NMDC | 2018-03-27 | era failure-rate cliff: 256/256 = 100.0% of the gated days below 2018-03-27 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 256 of the 256 stored days below 2018-03-27 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| NMDC | 2019-03-22 | gate-1P failure cluster: the oldest 135 of the 244 stored days below 2019-03-22 fail gate 1P as a contiguous block (>= 95%) while the 109 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| NTPC | 2019-02-06 | era failure-rate cliff: 582/582 = 100.0% of the gated days below 2019-02-06 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 582 of the 582 stored days below 2019-02-06 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| OIL | 2017-01-12 | gate-3 raw-gap-near-zero: \|raw gap\| 4.63% is nearer 0 than the event's own step 25.00% (k=0.75), adjusted gap 27.16% -- both closes are already in the same price domain AND era failure-rate cliff: 70/70 = 100.0% of the gated days below 2017-01-12 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 70 of the 70 stored days below 2017-01-12 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| OIL | 2017-02-13 | era failure-rate cliff: 21/21 = 100.0% of the gated days below 2017-02-13 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 21 of the 21 stored days below 2017-02-13 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| OIL | 2018-02-21 | era failure-rate cliff: 254/254 = 100.0% of the gated days below 2018-02-21 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 254 of the 254 stored days below 2018-02-21 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| OIL | 2018-03-27 | era failure-rate cliff: 23/23 = 100.0% of the gated days below 2018-03-27 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 23 of the 23 stored days below 2018-03-27 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| PERSISTENT | 2024-03-28 | gate-1P failure cluster: the oldest 1354 of the 1854 stored days below 2024-03-28 fail gate 1P as a contiguous block (>= 95%) while the 500 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| PETRONET | 2017-07-03 | gate-3 raw-gap-near-zero: \|raw gap\| 0.87% is nearer 0 than the event's own step 50.00% (k=0.5), adjusted gap 98.26% -- both closes are already in the same price domain AND era failure-rate cliff: 185/185 = 100.0% of the gated days below 2017-07-03 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 185 of the 185 stored days below 2017-07-03 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| PFC | 2022-02-25 | gate-1P failure cluster: the oldest 121 of the 233 stored days below 2022-02-25 fail gate 1P as a contiguous block (>= 95%) while the 112 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| PNBHOUSING | 2023-04-05 | gate-1P failure cluster: the oldest 739 of the 1589 stored days below 2023-04-05 fail gate 1P as a contiguous block (>= 95%) while the 850 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| POWERGRID | 2021-07-29 | gate-3 raw-gap-near-zero: \|raw gap\| 2.15% is nearer 0 than the event's own step 25.00% (k=0.75), adjusted gap 30.47% -- both closes are already in the same price domain |
| POWERGRID | 2021-12-22 | gate-1P failure cluster: the oldest 27 of the 99 stored days below 2021-12-22 fail gate 1P as a contiguous block (>= 95%) while the 72 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| RELIANCE | 2023-07-20 | gate-1P failure cluster: the oldest 411 of the 792 stored days below 2023-07-20 fail gate 1P as a contiguous block (>= 95%) while the 381 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| SRF | 2021-10-13 | gate-1P failure cluster: the oldest 103 of the 1030 stored days below 2021-10-13 fail gate 1P as a contiguous block (>= 95%) while the 927 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| TATASTEEL | 2018-01-31 | era failure-rate cliff: 331/331 = 100.0% of the gated days below 2018-01-31 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 331 of the 331 stored days below 2018-01-31 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| TATASTEEL | 2021-06-17 | gate-1P failure cluster: the oldest 215 of the 215 stored days below 2021-06-17 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| TATASTEEL | 2022-06-15 | gate-1P failure cluster: the oldest 247 of the 247 stored days below 2022-06-15 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| TATASTEEL | 2022-07-28 | gate-1P failure cluster: the oldest 29 of the 31 stored days below 2022-07-28 fail gate 1P as a contiguous block (>= 95%) while the 2 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| TORNTPHARM | 2022-07-08 | gate-1P failure cluster: the oldest 379 of the 1429 stored days below 2022-07-08 fail gate 1P as a contiguous block (>= 95%) while the 1050 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| UPL | 2019-07-02 | gate-3 raw-gap-near-zero: \|raw gap\| 8.62% is nearer 0 than the event's own step 33.33% (k=0.6666666666666666666666666667), adjusted gap 62.94% -- both closes are already in the same price domain AND era failure-rate cliff: 679/679 = 100.0% of the gated days below 2019-07-02 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 679 of the 679 stored days below 2019-07-02 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VBL | 2019-07-25 | era failure-rate cliff: 672/672 = 100.0% of the gated days below 2019-07-25 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 672 of the 672 stored days below 2019-07-25 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VBL | 2021-06-10 | era failure-rate cliff: 464/464 = 100.0% of the gated days below 2021-06-10 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 464 of the 464 stored days below 2021-06-10 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2017-04-11 | era failure-rate cliff: 129/129 = 100.0% of the gated days below 2017-04-11 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 129 of the 129 stored days below 2017-04-11 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2018-03-20 | era failure-rate cliff: 234/234 = 100.0% of the gated days below 2018-03-20 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 234 of the 234 stored days below 2018-03-20 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2018-11-06 | era failure-rate cliff: 156/156 = 100.0% of the gated days below 2018-11-06 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 156 of the 156 stored days below 2018-11-06 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2020-03-05 | era failure-rate cliff: 328/328 = 100.0% of the gated days below 2020-03-05 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 328 of the 328 stored days below 2020-03-05 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2020-10-28 | era failure-rate cliff: 161/161 = 100.0% of the gated days below 2020-10-28 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 161 of the 161 stored days below 2020-10-28 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2021-09-08 | era failure-rate cliff: 212/212 = 100.0% of the gated days below 2021-09-08 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 212 of the 212 stored days below 2021-09-08 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2021-12-17 | era failure-rate cliff: 68/68 = 100.0% of the gated days below 2021-12-17 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 68 of the 68 stored days below 2021-12-17 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2022-03-09 | era failure-rate cliff: 56/56 = 100.0% of the gated days below 2022-03-09 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 56 of the 56 stored days below 2022-03-09 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2022-05-06 | era failure-rate cliff: 38/38 = 100.0% of the gated days below 2022-05-06 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 38 of the 38 stored days below 2022-05-06 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2022-07-26 | era failure-rate cliff: 57/57 = 100.0% of the gated days below 2022-07-26 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 57 of the 57 stored days below 2022-07-26 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2022-11-29 | era failure-rate cliff: 84/84 = 100.0% of the gated days below 2022-11-29 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 84 of the 84 stored days below 2022-11-29 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2023-02-03 | era failure-rate cliff: 47/47 = 100.0% of the gated days below 2023-02-03 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 47 of the 47 stored days below 2023-02-03 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2023-04-06 | era failure-rate cliff: 41/41 = 100.0% of the gated days below 2023-04-06 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 41 of the 41 stored days below 2023-04-06 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2023-05-30 | era failure-rate cliff: 35/35 = 100.0% of the gated days below 2023-05-30 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 35 of the 35 stored days below 2023-05-30 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |
| VEDL | 2023-12-27 | era failure-rate cliff: 144/144 = 100.0% of the gated days below 2023-12-27 fail gate 1 (>= 95%) AND gate-1P failure cluster: the oldest 144 of the 144 stored days below 2023-12-27 fail gate 1P as a contiguous block (>= 95%) while the 0 above them are clean -- a STEP, which is what a per-side vendor splice leaves behind |

**Clause (iii) -- acceptance, era by era.** A measured floor is handed back to the MAP BUILDER, not layered onto the committed map: every era it touches must satisfy the same 2-paise per-day price containment and the same unwidened gate-1 band as any other era. An era that does is PROMOTED to provable; one that does not stays un-provable and its days stay excluded + counted.

| Symbol | Eras provable before | after | Promoted | Gate-1 before | Gate-1 after |
|---|---|---|---|---|---|
| APLAPOLLO | 2 | 2 | 0 | unchanged | 1896/2435 (77.9%) |
| ASTRAL | 2 | 3 | 1 | 1336/2434 (54.9%) | 1703/2434 (70.0%) |
| AUBANK | 1 | 1 | 0 | unchanged | 2239/2244 (99.8%) |
| BAJAJFINSV | 1 | 1 | 0 | unchanged | 2421/2435 (99.4%) |
| BEL | 1 | 1 | 0 | unchanged | 2177/2435 (89.4%) |
| BLUESTARCO | 1 | 1 | 0 | 1280/2433 (52.6%) | 2414/2433 (99.2%) |
| BPCL | 11 | 11 | 0 | unchanged | 2227/2433 (91.5%) |
| BSE | 6 | 6 | 0 | unchanged | 2199/2349 (93.6%) |
| CANBK | 6 | 7 | 1 | 1047/2433 (43.0%) | 2418/2433 (99.4%) |
| COCHINSHIP | 2 | 6 | 4 | 1962/2219 (88.4%) | 2202/2219 (99.2%) |
| DIXON | 1 | 1 | 0 | 1929/2196 (87.8%) | 2173/2196 (99.0%) |
| GAIL | 10 | 10 | 0 | unchanged | 1994/2435 (81.9%) |
| GRASIM | 3 | 3 | 0 | unchanged | 2418/2433 (99.4%) |
| HAL | 1 | 3 | 2 | 1680/2064 (81.4%) | 2052/2064 (99.4%) |
| HDFCBANK | 2 | 2 | 0 | unchanged | 2377/2433 (97.7%) |
| HINDPETRO | 7 | 8 | 1 | 1770/2433 (72.7%) | 1999/2433 (82.2%) |
| IEX | 0 | 1 | 1 | 1153/2173 (53.1%) | 1153/2173 (53.1%) |
| INOXWIND | 2 | 2 | 0 | 1039/2433 (42.7%) | 2414/2433 (99.2%) |
| IOC | 3 | 3 | 0 | unchanged | 2066/2435 (84.8%) |
| JUBLFOOD | 2 | 2 | 0 | 2098/2435 (86.2%) | 2098/2435 (86.2%) |
| LODHA | 1 | 1 | 0 | unchanged | 1282/1311 (97.8%) |
| MOTILALOFS | 1 | 1 | 0 | 1029/2433 (42.3%) | 2413/2433 (99.2%) |
| NESTLEIND | 2 | 3 | 1 | 1133/2434 (46.5%) | 2393/2434 (98.3%) |
| NMDC | 12 | 12 | 0 | unchanged | 2057/2435 (84.5%) |
| NTPC | 7 | 7 | 0 | 1845/2432 (75.9%) | 1845/2432 (75.9%) |
| OIL | 8 | 8 | 0 | unchanged | 2052/2433 (84.3%) |
| PERSISTENT | 1 | 1 | 0 | 1088/2433 (44.7%) | 2415/2433 (99.3%) |
| PETRONET | 2 | 2 | 0 | unchanged | 2238/2435 (91.9%) |
| PFC | 5 | 9 | 4 | 2299/2433 (94.5%) | 2420/2433 (99.5%) |
| PGEL | 1 | 1 | 0 | unchanged | 2382/2433 (97.9%) |
| PNBHOUSING | 1 | 1 | 0 | 1669/2412 (69.2%) | 2396/2412 (99.3%) |
| POWERGRID | 10 | 10 | 0 | unchanged | 2395/2434 (98.4%) |
| RECLTD | 7 | 7 | 0 | unchanged | 2420/2435 (99.4%) |
| RELIANCE | 4 | 4 | 0 | 2004/2433 (82.4%) | 2412/2433 (99.1%) |
| SRF | 1 | 1 | 0 | unchanged | 2423/2435 (99.5%) |
| TATASTEEL | 3 | 3 | 0 | unchanged | 2091/2435 (85.9%) |
| TORNTPHARM | 1 | 1 | 0 | unchanged | 2430/2435 (99.8%) |
| UPL | 1 | 1 | 0 | unchanged | 1754/2434 (72.1%) |
| VBL | 3 | 3 | 0 | unchanged | 1274/2411 (52.8%) |
| VEDL | 4 | 17 | 13 | 642/2433 (26.4%) | 2123/2433 (87.3%) |

### 3f. GATE 1P and the bounded PRICE-RECOVERY pass (QUESTIONS.md Q-14)

The architect's ruling of 2026-07-28: "gate 1 proves volume; nothing proved price per day ... Therefore GATE 1P joins CONTEXT 4.5's battery permanently: for every stored symbol-day, the un-adjusted 1-minute fold interval [low, high] must sit INSIDE the raw bhavcopy interval [daily_low, daily_high] with tolerance max(2 paise, 0.1% of the raw price) per side; a day with no raw daily row cannot be price-proven and FAILS. A day failing 1P is EXCLUDED and COUNTED under its own reason."

The mechanism the ruling names is a PER-SIDE vendor splice -- price and volume applied back to different dates for the same event -- so the floor model gained `floor_price` and `floor_volume` per event, each measured by the SAME bisection under the SAME guards. The hunt is signature-gated by gate-1P failure CLUSTERS: a contiguous block of price failures at the old end of an era's span, at least 20 days long, failing at >= 95% with a clean remainder above it -- the shape a step leaves, and nothing else.

**No candle was fetched for this pass.** The observable a probe buys is `fetched / raw`, and the store holds it exactly: the ingest wrote `stored = fetched / k_applied`, so `event-in` is "the stored day is contained in raw" (gate 1P itself) and `event-out` is "the stored day multiplied BACK by the event's own factor is contained". Identical oracle, identical tolerance, zero credentialed calls, reproducible offline by anyone holding the two stores (decision B143).

No symbol carried enough price-unproven days for a cluster signature to be possible, so the pass entered none. The register below is the whole gate-1P residue.

| Symbol | Gate-1P before | Gate-1P after | Events admitted | Floors accepted | Days rewritten | Outcome |
|---|---|---|---|---|---|---|

**The DISCLOSED-RESIDUAL register for gate 1P.** The ruling freezes the data era after this one pass: "anything still flagged is a disclosed residual, not chased." Every symbol below still carries price-unproven days; they are EXCLUDED and COUNTED under gate 1P's own reason, and this table is what chunk 9 carries forward.

| Symbol | Days failing gate 1P | above / below / no-oracle | Worst excess (paise) | Status | Why it is residual |
|---|---|---|---|---|---|
| IOC | 1,412 | 1 / 1410 / 1 | 47,823 | settled | the failing days sit inside UN-PROVABLE eras (1,761 un-provable stored days, 3/17 eras provable). An un-provable era commits no chain, so there is no factor for a floor to drop and no floor could change one stored price -- the Q-11 addendum-2 ruling's own fallback: un-provable remains the honest answer |
| VBL | 1,137 | 1136 / 0 / 1 | 265,509 | quarantined | the failing days sit inside UN-PROVABLE eras (1,136 un-provable stored days, 3/5 eras provable). An un-provable era commits no chain, so there is no factor for a floor to drop and no floor could change one stored price -- the Q-11 addendum-2 ruling's own fallback: un-provable remains the honest answer |
| GRASIM | 1,105 | 1103 / 1 / 1 | 563 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| BEL | 978 | 975 / 2 / 1 | 324,847 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| TATASTEEL | 832 | 0 / 831 / 1 | 134,107 | settled | the failing days sit inside UN-PROVABLE eras (1,443 un-provable stored days, 3/9 eras provable). An un-provable era commits no chain, so there is no factor for a floor to drop and no floor could change one stored price -- the Q-11 addendum-2 ruling's own fallback: un-provable remains the honest answer |
| BAJAJFINSV | 788 | 785 / 2 / 1 | 8,954,005 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| ASTRAL | 731 | 729 / 1 / 1 | 92,810 | quarantined | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| UPL | 682 | 0 / 681 / 1 | 36,570 | quarantined | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| NTPC | 583 | 0 / 582 / 1 | 3,023 | quarantined | the failing days sit inside UN-PROVABLE eras (582 un-provable stored days, 7/8 eras provable). An un-provable era commits no chain, so there is no factor for a floor to drop and no floor could change one stored price -- the Q-11 addendum-2 ruling's own fallback: un-provable remains the honest answer |
| APLAPOLLO | 537 | 536 / 0 / 1 | 2,317,242 | quarantined | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| NMDC | 507 | 137 / 369 / 1 | 10,537 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| IEX | 481 | 480 / 0 / 1 | 355,822 | quarantined | the failing days sit inside UN-PROVABLE eras (773 un-provable stored days, 1/2 eras provable). An un-provable era commits no chain, so there is no factor for a floor to drop and no floor could change one stored price -- the Q-11 addendum-2 ruling's own fallback: un-provable remains the honest answer |
| GAIL | 434 | 64 / 369 / 1 | 37,329 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| HINDPETRO | 428 | 1 / 426 / 1 | 31,742 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| TORNTPHARM | 380 | 379 / 0 / 1 | 169,730 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| OIL | 370 | 1 / 368 / 1 | 31,908 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| VEDL | 304 | 0 / 303 / 1 | 18,993 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| BSE | 220 | 81 / 138 / 1 | 207,693 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| BPCL | 197 | 0 / 196 / 1 | 49,725 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| AUBANK | 195 | 192 / 2 / 1 | 74,035 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| PETRONET | 187 | 0 / 186 / 1 | 22,260 | settled | the failing days sit inside UN-PROVABLE eras (1,761 un-provable stored days, 2/10 eras provable). An un-provable era commits no chain, so there is no factor for a floor to drop and no floor could change one stored price -- the Q-11 addendum-2 ruling's own fallback: un-provable remains the honest answer |
| SRF | 105 | 103 / 1 / 1 | 808,597 | settled | the failing days sit inside UN-PROVABLE eras (216 un-provable stored days, 1/2 eras provable). An un-provable era commits no chain, so there is no factor for a floor to drop and no floor could change one stored price -- the Q-11 addendum-2 ruling's own fallback: un-provable remains the honest answer |
| PGEL | 80 | 77 / 2 / 1 | 670 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| RECLTD | 68 | 1 / 66 / 1 | 2,818 | settled | the failing days sit inside UN-PROVABLE eras (1,020 un-provable stored days, 7/12 eras provable). An un-provable era commits no chain, so there is no factor for a floor to drop and no floor could change one stored price -- the Q-11 addendum-2 ruling's own fallback: un-provable remains the honest answer |
| POWERGRID | 28 | 27 / 0 / 1 | 6,236 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| LODHA | 26 | 25 / 0 / 1 | 75,734 | settled | no event showed a gate-1P failure CLUSTER -- the failures are not a contiguous step, so no vendor application floor explains them and none was hunted ("never blanket") |
| **182 further symbol(s)**, aggregated | **431** | | | settled / quarantined | fewer than 20 price-unproven days each -- below a cluster's minimum length, so no vendor application floor could be measured for them and none was hunted. 182 of these days have no raw daily row at all |

Read the register this way: an **above** failure means the stored 1-minute high sits ABOVE the exchange's own daily high, which is impossible on raw prices and means the day is stored too HIGH; a **below** failure means the fold low sits below the daily low, i.e. the day is stored too LOW; **no-oracle** means the day has no bhavcopy row at all and cannot be price-proven either way (the ruling's own words). The worst excess is how far past the tolerated bound the worse side sits, in paise -- a few paise is microstructure, a few thousand is a wrong price scale.

## 4. Exclusions by reason

| Reason | Symbol-days | Note |
|---|---|---|
| gate-1 (volume reconciliation outside [-0.1%, +5.0%], UNRELIEVED) | 6,303 | CONTEXT 4.5 gate 1; excluded + counted per CONTEXT 7-E3. 411 further above-ceiling failures were relieved as a thin day's auction share (section 3d) and are NOT excluded |
| **gate-1P (per-day PRICE containment, QUESTIONS.md Q-14)** | **9,075** | the stored 1-minute fold does not sit inside the raw bhavcopy high/low within max(2 paise, 0.1%). Its own reason, never folded into gate 1's count. Of these, 208 have no raw daily row at all and cannot be price-proven (the ruling's own words; REVIEW_5B finding Q4) |
| gate-2 (candle integrity) | 1,072 | duplicates, impossible OHLC, negative values, or missing minutes ON A DAY WHERE GATE 1 ALSO FAILS (the completeness ruling) |
| un-provable (no map era / unknown factor in (D, F]) | 19,872 | the Q-11 surgical clamp -- stored so the day is visible, failed by gate 1 |
| stored days LEFT UNTOUCHED (baseline unidentified) | 998 | not an exclusion reason and mostly not damage: the map application declined to correct these days because their stored bars match neither raw nor the map's chain nor a one-too-many division. Declining is the conservative action -- a day that already needed no correction is unaffected, and gate 1 decides either way. The count measures how often the classifier refuses, not how many days are wrong |
| quarantined symbols (whole history) | 14,319 | 6 symbol(s) below the 80% gate-1 floor |

**The unknown-baseline days, re-classified against the ENRICHED hypothesis set (Q-11 addendum 4).** The set is now `1 / k_era / 1/k_era / 1/k_era^2` plus, wherever a measured floor makes the day's own chain differ from its era chain, `k_target/k_era` (pre-floor-divided), `k_era/k_target` (floor-overreached) and `k_target` itself (as-fetched-floored -- the vendor's own untouched bars on a floored day, which is what every day of a newly PROMOTED era looks like). Of the 998 days still unidentified, **980 also fail gate 1** -- those are the only ones that cost coverage. The remainder reconcile exactly as they stand, which is why declining to touch them is the conservative action and not a loss. A day is never corrected by a guessed factor: the tolerance is derived from the candidate set itself (half the closest relative gap, capped at 2%), so extending the set can never let two hypotheses claim one ratio.

### Gate 2 redefined: completeness is volume reconciliation, not a minute count

The architect's ruling of 2026-07-26 (QUESTIONS.md "CONTEXT 4.5 / 7-E4 AMENDMENT"): **the vendor omits minutes in which nothing traded**, so a missing stamp on a day whose gate-1 volume reconciliation PASSES is a NO-TRADE minute, not missing data -- every traded rupee is already accounted for. Gate 2's exclusion triggers are now exactly four, and the run counts each one separately:

| Gate-2 trigger | Symbol-days | Note |
|---|---|---|
| missing minutes AND gate 1 also failed | 895 | indistinguishable from data loss, so still excluded |
| duplicate stamps | 0 | unchanged trigger |
| impossible OHLC (high<low, close outside range) | 1 | unchanged trigger (CONTEXT 4.5's own two) |
| negative price or volume | 180 | trigger ADDED by the ruling -- and it fired: see below |
| **missing minutes with gate 1 PASSING -> INCLUDED** | **90,991** | recorded as liquidity statistics (section 3b), never an exclusion -- this is the redefinition's whole effect |

**The NEGATIVE-values trigger the ruling added found a real defect on its first run.** Every one of its exclusions lands on 4 date(s) -- `2023-05-03`, `2023-05-04`, `2023-08-21`, `2024-03-02` -- across essentially EVERY symbol processed, not on scattered per-symbol accidents. The vendor serves 1-minute bars with negative VOLUME for those dates (measured: ABB -6,060 and -2 shares, AXISBANK -99,379 and -1, CIPLA -43,534, all stamped 11:15 onwards). `2024-03-02` is a SATURDAY -- one of NSE's disaster-recovery special live sessions. Such a date is already excluded from trading days, bias pairs and trading by QUESTIONS.md Q-5, so nothing was ever going to trade it; what is new is that the day's candles are now excluded EXPLICITLY and counted, instead of passing gate 2 on a minute count and relying on the calendar alone. Before this ruling a negative share count was not a gate-2 trigger at all.

Measured before the ruling, on the same stored candles: ABB traded 318/293/325/338 of 375 minutes on four consecutive 2019 days -- 37..82 missing -- while gate 1 reconciled every one of them, and the pre-ruling gate 2 excluded all four. CONTEXT 4.3's PoC measurement of "375/375 candles, zero gaps" was taken on 5 LIQUID symbols in 2026, which is why the minute-count rule looked safe. CONTEXT 7-E4's own minute-count trigger ("missing > 5 of its 120") is retired by the same ruling; chunk 6's POC window is valid when the DAY passes gate 1, and a tradeless minute contributes zero volume to the profile.

### Quarantined symbols

| Symbol | Route | Gate-1 | Rerouted? | Failure pattern | Why |
|---|---|---|---|---|---|
| APLAPOLLO | map-required | 1896/2435 (77.9%) | yes | mixed | gate-1 pass rate 77.9% is below 80%; skipped, listed, run continues |
| ASTRAL | map-required | 1703/2434 (70.0%) | yes | clustered-before-ex-date (adjustment problem) | gate-1 pass rate 70.0% (strict 69.9% + 1 relieved) is below 80%; skipped, listed, run continues |
| IEX | map-required | 1153/2173 (53.1%) | yes | clustered-before-ex-date (adjustment problem) | gate-1 pass rate 53.1% (strict 53.0% + 1 relieved) is below 80%; skipped, listed, run continues |
| NTPC | map-required | 1845/2432 (75.9%) | n/a (map path) | clustered-before-ex-date (adjustment problem) | gate-1 pass rate 75.9% (strict 75.8% + 1 relieved) is below 80%; skipped, listed, run continues |
| UPL | map-required | 1754/2434 (72.1%) | n/a (map path) | clustered-before-ex-date (adjustment problem) | gate-1 pass rate 72.1% is below 80%; skipped, listed, run continues |
| VBL | map-required | 1274/2411 (52.8%) | yes | clustered-before-ex-date (adjustment problem) | gate-1 pass rate 52.8% is below 80%; skipped, listed, run continues |

**Failure-pattern analysis** (the Q-12-addendum ruling: "failures clustered before a CA ex-date (adjustment problem) vs scattered (auction/liquidity shape)"). Every table-path symbol here was first REROUTED through the map path as a second pass -- probes bought it the price oracle the routing rule does not otherwise give a bonus/split-only symbol -- and stayed quarantined anyway.

- **APLAPOLLO** -- mixed. worst era failure rate 51.7%, post-last-ex-date era 0.0%; 534 above the ceiling / 5 below the floor -- neither pattern is clean
  - reroute: map 2/2 eras provable; 0 day(s) rewritten, 2436 already raw; gate 1 1896/2435 (77.9%) -> 1896/2435 (77.9%)
  - per-era gate-1 failure rate: < 2020-12-15 538/1041 (51.7%); < 2021-09-16 1/186 (0.5%); >= 2021-09-16 0/1208 (0.0%)
- **ASTRAL** -- clustered-before-ex-date (adjustment problem). an era fails at 100.0% while the post-last-ex-date era fails at 0.1% -- one wrong factor applied to a whole span, not a market property
  - reroute: map 2/3 eras provable; 0 day(s) rewritten, 1706 already raw; gate 1 1336/2434 (54.9%) -> 1336/2434 (54.9%)
  - per-era gate-1 failure rate: < 2019-09-16 729/729 (100.0%); < 2021-03-18 1/375 (0.3%); < 2023-03-14 0/493 (0.0%); >= 2023-03-14 1/837 (0.1%)
- **IEX** -- clustered-before-ex-date (adjustment problem). an era fails at 100.0% while the post-last-ex-date era fails at 0.1% -- one wrong factor applied to a whole span, not a market property
  - reroute: map 0/2 eras provable; 0 day(s) rewritten, 1155 already raw; gate 1 1153/2173 (53.1%) -> 1153/2173 (53.1%)
  - per-era gate-1 failure rate: < 2018-10-19 246/246 (100.0%); < 2021-12-03 773/773 (100.0%); >= 2021-12-03 1/1154 (0.1%)
- **NTPC** -- clustered-before-ex-date (adjustment problem). an era fails at 100.0% while the post-last-ex-date era fails at 0.1% -- one wrong factor applied to a whole span, not a market property
  - per-era gate-1 failure rate: < 2019-02-06 582/582 (100.0%); < 2019-03-19 2/28 (7.1%); < 2019-08-13 1/98 (1.0%); < 2020-08-13 0/247 (0.0%); < 2021-02-11 1/123 (0.8%); < 2021-09-08 0/141 (0.0%); < 2022-02-03 0/101 (0.0%); < 2023-02-03 0/249 (0.0%); >= 2023-02-03 1/863 (0.1%)
- **UPL** -- clustered-before-ex-date (adjustment problem). an era fails at 100.0% while the post-last-ex-date era fails at 0.0% -- one wrong factor applied to a whole span, not a market property
  - per-era gate-1 failure rate: < 2019-07-02 679/679 (100.0%); < 2024-11-26 1/1339 (0.1%); >= 2024-11-26 0/416 (0.0%)
- **VBL** -- clustered-before-ex-date (adjustment problem). an era fails at 100.0% while the post-last-ex-date era fails at 0.0% -- one wrong factor applied to a whole span, not a market property
  - reroute: map 3/5 eras provable; 0 day(s) rewritten, 1276 already raw; gate 1 1274/2411 (52.8%) -> 1274/2411 (52.8%)
  - per-era gate-1 failure rate: < 2019-07-25 672/672 (100.0%); < 2021-06-10 464/464 (100.0%); < 2022-06-06 0/245 (0.0%); < 2023-06-15 0/255 (0.0%); < 2024-09-12 1/309 (0.3%); >= 2024-09-12 0/466 (0.0%)

### Deferred to the architect: the gate-1 +5.0% ceiling on illiquid names

The Q-12-addendum ruling: "The gate-1 +5.0% ceiling's behavior on illiquid names (auction share of a tiny day can exceed 5%) is EXPLICITLY DEFERRED to the architect's review of the completed run's report -- flag it there with per-symbol evidence; do not tune the band." **The band is untouched** (`[-0.1%, 5.0%]`, byte-identical). This is the evidence, per symbol:

| Symbol | Gate-1 failures | Above +5.0% ceiling | Below -0.1% floor | Median raw daily volume (all days) | Median on the above-ceiling days | Pattern |
|---|---|---|---|---|---|---|
| APLAPOLLO | 539 | 534 | 5 | 237,197 | 13,621 | mixed |
| ASTRAL | 731 | 719 | 12 | 242,756 | 35,388 | clustered-before-ex-date (adjustment problem) |
| IEX | 1020 | 1019 | 1 | 3,543,960 | 292,260 | clustered-before-ex-date (adjustment problem) |
| NTPC | 587 | 0 | 587 | 10,501,134 | 0 | clustered-before-ex-date (adjustment problem) |
| UPL | 680 | 0 | 680 | 2,140,521 | 0 | clustered-before-ex-date (adjustment problem) |
| VBL | 1137 | 1136 | 1 | 499,470 | 114,174 | clustered-before-ex-date (adjustment problem) |

Read it this way: an ABOVE-ceiling failure on a day whose raw daily volume is far below the symbol's own median is the pre-open auction taking more than 5% of a thin day -- a market property, not a data defect. A BELOW-floor failure, or an above-ceiling failure on an ordinary-volume day, is an adjustment problem. No band was moved either way.

## 5. Gate 3 -- adjustment sanity across every share-count ex-date

CONTEXT 4.5 gate 3: on every split/bonus ex-date in the stored span, the ADJUSTED series must show |day-over-day gap| < 20%. Checked on the stored RAW closes with the event's own CONTEXT 4.2 factor applied at the comparison. **117 ex-date(s) checked, 15 failed.**

Every failure, with its numbers. `raw gap` is the two stored closes with NO factor applied; `adjusted gap` is CONTEXT 4.5's own test (the pre-ex close scaled by `k`). Read together they name the defect: a raw gap near `k - 1` with an adjusted gap near zero is a healthy event, while a raw gap near ZERO with a large adjusted gap means the two closes are ALREADY in the same price domain -- i.e. the pre-ex side was never un-adjusted for the event, which is the exact signature of a vendor APPLICATION FLOOR (section 3c) sitting above the pre-ex day.

| Symbol | Event(s) | Ex-date | k | Pre-ex day | Ex day | Raw gap | Adjusted gap | Classification |
|---|---|---|---|---|---|---|---|---|
| ASTRAL | bonus | 2019-09-16 | 0.8 | 2019-09-13 | 2019-09-16 | -37.68% | -22.10% | hunted; a floor was measured for another event of this symbol but not for this one -- residual |
| BPCL | bonus | 2017-07-13 | 0.6666666666666666666666666667 | 2017-07-12 | 2017-07-13 | 101.21% | 201.81% | hunted, no floor needed; residual |
| COCHINSHIP | split | 2024-01-10 | 0.5 | 2024-01-09 | 2024-01-10 | -40.00% | 20.00% | pre-floor span, floor MEASURED for this event -- this row is the post-fix recheck |
| GAIL | bonus | 2017-03-09 | 0.75 | 2017-03-08 | 2017-03-09 | -2.52% | 29.97% | unresolved-floor span -- hunted, no floor fitted; residual |
| GAIL | bonus | 2018-03-27 | 0.75 | 2018-03-26 | 2018-03-27 | 201.98% | 302.63% | hunted, no floor needed; residual |
| HINDPETRO | bonus | 2017-07-11 | 0.6666666666666666666666666667 | 2017-07-10 | 2017-07-11 | -0.35% | 49.47% | hunted; a floor was measured for another event of this symbol but not for this one -- residual |
| IOC | bonus | 2016-10-18 | 0.5 | 2016-10-17 | 2016-10-18 | 0.17% | 100.34% | unresolved-floor span -- hunted, no floor fitted; residual |
| IOC | bonus | 2018-03-15 | 0.5 | 2018-03-14 | 2018-03-15 | -2.77% | 94.45% | unresolved-floor span -- hunted, no floor fitted; residual |
| IOC | bonus | 2022-06-30 | 0.6666666666666666666666666667 | 2022-06-29 | 2022-06-30 | 1.43% | 52.15% | unresolved-floor span -- hunted, no floor fitted; residual |
| OIL | bonus | 2017-01-12 | 0.75 | 2017-01-11 | 2017-01-12 | -4.63% | 27.16% | unresolved-floor span -- hunted, no floor fitted; residual |
| OIL | bonus | 2018-03-27 | 0.6666666666666666666666666667 | 2018-03-26 | 2018-03-27 | 42.44% | 113.67% | hunted, no floor needed; residual |
| PETRONET | bonus | 2017-07-03 | 0.5 | 2017-06-30 | 2017-07-03 | -0.87% | 98.26% | unresolved-floor span -- hunted, no floor fitted; residual |
| POWERGRID | bonus | 2021-07-29 | 0.75 | 2021-07-28 | 2021-07-29 | -2.15% | 30.47% | unresolved-floor span -- hunted, no floor fitted; residual |
| UPL | bonus | 2019-07-02 | 0.6666666666666666666666666667 | 2019-07-01 | 2019-07-02 | 8.62% | 62.94% | unresolved-floor span -- hunted, no floor fitted; residual |
| VBL | bonus | 2021-06-10 | 0.6666666666666666666666666667 | 2021-06-09 | 2021-06-10 | -65.70% | -48.56% | hunted, no floor needed; residual |

### The DISCLOSED RESIDUAL register (QUESTIONS.md Q-11 addendum 4)

The final ruling closes the data era: "residuals after this pass are disclosed, not chased." This is that register -- every gate-3 failure that survived the signature-gated hunt, with the numbers, the symbol's coverage cost, and why the hunt did not resolve it. Chunk 9's report carries this table forward.

| Symbol | Ex-date | k | Raw gap | Adjusted gap | Signature? | Symbol-days failing gate 1 | Why it is residual |
|---|---|---|---|---|---|---|---|
| ASTRAL | 2019-09-16 | 0.8 | -37.68% | -22.10% | no -- raw gap -37.68% is nearer the healthy k-1 than 0, so the raw-gap-near-zero signature does not admit it | 731 | hunted; a floor was measured for another event of this symbol but not for this one -- residual |
| BPCL | 2017-07-13 | 0.6666666666666666666666666667 | 101.21% | 201.81% | no -- raw gap 101.21% is nearer the healthy k-1 than 0, so the raw-gap-near-zero signature does not admit it | 206 | hunted, no floor needed; residual |
| COCHINSHIP | 2024-01-10 | 0.5 | -40.00% | 20.00% | no -- raw gap -40.00% is nearer the healthy k-1 than 0, so the raw-gap-near-zero signature does not admit it | 17 | pre-floor span, floor MEASURED for this event -- this row is the post-fix recheck |
| GAIL | 2017-03-09 | 0.75 | -2.52% | 29.97% | gate-3 raw-gap-near-zero: \|raw gap\| 2.52% is nearer 0 than the event's own step 25.00% (k=0.75), adjusted gap 29.97% -- both closes are already in the same price domain | 441 | unresolved-floor span -- hunted, no floor fitted; residual |
| GAIL | 2018-03-27 | 0.75 | 201.98% | 302.63% | no -- raw gap 201.98% is nearer the healthy k-1 than 0, so the raw-gap-near-zero signature does not admit it | 441 | hunted, no floor needed; residual |
| HINDPETRO | 2017-07-11 | 0.6666666666666666666666666667 | -0.35% | 49.47% | gate-3 raw-gap-near-zero: \|raw gap\| 0.35% is nearer 0 than the event's own step 33.33% (k=0.6666666666666666666666666667), adjusted gap 49.47% -- both closes are already in the same price domain | 434 | hunted; a floor was measured for another event of this symbol but not for this one -- residual |
| IOC | 2016-10-18 | 0.5 | 0.17% | 100.34% | gate-3 raw-gap-near-zero: \|raw gap\| 0.17% is nearer 0 than the event's own step 50.00% (k=0.5), adjusted gap 100.34% -- both closes are already in the same price domain | 369 | unresolved-floor span -- hunted, no floor fitted; residual |
| IOC | 2018-03-15 | 0.5 | -2.77% | 94.45% | gate-3 raw-gap-near-zero: \|raw gap\| 2.77% is nearer 0 than the event's own step 50.00% (k=0.5), adjusted gap 94.45% -- both closes are already in the same price domain | 369 | unresolved-floor span -- hunted, no floor fitted; residual |
| IOC | 2022-06-30 | 0.6666666666666666666666666667 | 1.43% | 52.15% | gate-3 raw-gap-near-zero: \|raw gap\| 1.43% is nearer 0 than the event's own step 33.33% (k=0.6666666666666666666666666667), adjusted gap 52.15% -- both closes are already in the same price domain | 369 | unresolved-floor span -- hunted, no floor fitted; residual |
| OIL | 2017-01-12 | 0.75 | -4.63% | 27.16% | gate-3 raw-gap-near-zero: \|raw gap\| 4.63% is nearer 0 than the event's own step 25.00% (k=0.75), adjusted gap 27.16% -- both closes are already in the same price domain | 381 | unresolved-floor span -- hunted, no floor fitted; residual |
| OIL | 2018-03-27 | 0.6666666666666666666666666667 | 42.44% | 113.67% | no -- raw gap 42.44% is nearer the healthy k-1 than 0, so the raw-gap-near-zero signature does not admit it | 381 | hunted, no floor needed; residual |
| PETRONET | 2017-07-03 | 0.5 | -0.87% | 98.26% | gate-3 raw-gap-near-zero: \|raw gap\| 0.87% is nearer 0 than the event's own step 50.00% (k=0.5), adjusted gap 98.26% -- both closes are already in the same price domain | 197 | unresolved-floor span -- hunted, no floor fitted; residual |
| POWERGRID | 2021-07-29 | 0.75 | -2.15% | 30.47% | gate-3 raw-gap-near-zero: \|raw gap\| 2.15% is nearer 0 than the event's own step 25.00% (k=0.75), adjusted gap 30.47% -- both closes are already in the same price domain | 39 | unresolved-floor span -- hunted, no floor fitted; residual |
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

