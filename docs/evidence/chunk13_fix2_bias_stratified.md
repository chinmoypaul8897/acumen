# chunk 13 FIX-2 -- the replay invariant, STRATIFIED BY bias_rule

Run at 2026-08-12T21:35:56 from `docs/evidence/chunk13_fix2_bias_stratified.py`. READ-ONLY over the stores.

REVIEW_13 **B1**: `build_live_screener` seeded the bias SERIES at the trade day, so
CONTEXT 3.2's rule-1 and rule-5 CARRY had no earlier bias to carry and the screener
refused the symbol for the whole day. The build session's three walk days were all
rule-fired, which is why the invariant appeared to hold. This sample is stratified by
`bias_rule`, so a carry day is present BY CONSTRUCTION.

## The strata, over the whole ten-year ledger

| bias_rule | evaluated stock-days | share |
|---|---:|---:|
| `rule-1-breakout` | 276,541 | 68.03% |
| `inside-bar-carry` | 62,680 | 15.42% |
| `rule-2-sweep` | 60,527 | 14.89% |
| `rule-3-outside-bar` | 6,664 | 1.64% |
| `rule-3-tie` | 62 | 0.02% |
| `rule-3-no-1min-carry` | 7 | 0.00% |
| `rule-3-no-break-carry` | 5 | 0.00% |
| `no-data` | 2 | 0.00% |
| **total** | **406,488** | 100% |

**Carried strata (`inside-bar-carry`, `no-data`, `no-rule-carry`, `rule-3-no-1min-carry`, `rule-3-no-break-carry`): 62,694 of 406,488 = 15.42% of evaluated stock-days.** Those are the days a series seeded at
the trade day cannot answer at all.

## How far back a carry has to reach -- which is what sets SEED_LOOKBACK_DAYS

A look-back reaches the RIGHT carried bias exactly when it reaches the most recent
rule-firing day, and reaching further back cannot change the answer: longer is never
wrong, only slower. So the constant is measurable. Distance from every stored row back
to its symbol's last `rule-1` / `rule-2` / `rule-3-outside-bar` / `rule-3-tie` day:

| reach | rows within it | share |
|---|---:|---:|
| <= 0 calendar day(s) | 354,745 | 84.226259% |
| <= 1 calendar day(s) | 400,883 | 95.180694% |
| <= 3 calendar day(s) | 417,104 | 99.032008% |
| <= 7 calendar day(s) | 421,107 | 99.982430% |
| <= 14 calendar day(s) | 421,115 | 99.984330% |
| <= 30 calendar day(s) | 421,126 | 99.986941% |
| <= 60 calendar day(s) | 421,145 | 99.991453% |
| <= 90 calendar day(s) | 421,166 | 99.996439% |
| <= 120 calendar day(s) | 421,181 | 100.000000% |
| <= 180 calendar day(s) | 421,181 | 100.000000% |
| **any** | **421,181** | 100% |

**Worst case over the whole decade: 112 calendar days.** 55 rows (0.013059%) need more than 30, and every one of them is a single stretch of missing daily candles rather than a market
condition. `SEED_LOOKBACK_DAYS` is **180**, which covers the measured maximum with margin.

## The sample, replayed through the SHIPPED wiring (no `seed_from` argument)

| symbol | day | bias_rule | carried | screener vs ledger |
|---|---|---|---|---|
| ITC | 2026-06-10 | `inside-bar-carry` | YES | **MATCH** |
| 360ONE | 2026-01-01 | `inside-bar-carry` | YES | **MATCH** |
| FORCEMOT | 2024-02-14 | `no-data` | YES | **MATCH** |
| 360ONE | 2026-01-05 | `rule-1-breakout` | no | **MATCH** |
| 360ONE | 2026-01-06 | `rule-2-sweep` | no | **MATCH** |
| AMBER | 2021-01-27 | `rule-3-no-1min-carry` | YES | **MATCH** |
| ASIANPAINT | 2017-07-11 | `rule-3-no-break-carry` | YES | **MATCH** |
| 360ONE | 2026-04-22 | `rule-3-outside-bar` | no | **MATCH** |
| BDL | 2026-03-04 | `rule-3-tie` | no | **MATCH** |

**9 of 9 strata MATCH the ledger field for field** (bias, rule, POC, reference, entry, stop, target, qty, exit kind), and 5 of them stand on a CARRIED bias.

## The carried days in full

### ITC 2026-06-10 -- `inside-bar-carry`

| field | ledger | screener |
|---|---|---|
| bias | bearish | bearish |
| bias_rule | inside-bar-carry | inside-bar-carry |
| entry_paise | None | None |
| exit_kind | None | None |
| poc_paise | 283.27 | 283.27 |
| qty | None | None |
| reference_paise | 284.40 | 284.40 |
| stop_paise | None | None |
| target_paise | None | None |

### 360ONE 2026-01-01 -- `inside-bar-carry`

| field | ledger | screener |
|---|---|---|
| bias | bullish | bullish |
| bias_rule | inside-bar-carry | inside-bar-carry |
| entry_paise | 1,179.10 | 1,179.10 |
| exit_kind | stop-loss-hit | stop-loss-hit |
| poc_paise | 1,178.75 | 1,178.75 |
| qty | 625 | 625 |
| reference_paise | 1,177.80 | 1,177.80 |
| stop_paise | 1,177.50 | 1,177.50 |
| target_paise | 1,183.90 | 1,183.90 |

### FORCEMOT 2024-02-14 -- `no-data`

| field | ledger | screener |
|---|---|---|
| bias | bearish | bearish |
| bias_rule | no-data | no-data |
| entry_paise | None | None |
| exit_kind | None | None |
| poc_paise | 4,402.50 | 4,402.50 |
| qty | None | None |
| reference_paise | 4,397.00 | 4,397.00 |
| stop_paise | None | None |
| target_paise | None | None |

### AMBER 2021-01-27 -- `rule-3-no-1min-carry`

| field | ledger | screener |
|---|---|---|
| bias | bearish | bearish |
| bias_rule | rule-3-no-1min-carry | rule-3-no-1min-carry |
| entry_paise | None | None |
| exit_kind | None | None |
| poc_paise | 2,533.95 | 2,533.95 |
| qty | None | None |
| reference_paise | 2,532.15 | 2,532.15 |
| stop_paise | None | None |
| target_paise | None | None |

### ASIANPAINT 2017-07-11 -- `rule-3-no-break-carry`

| field | ledger | screener |
|---|---|---|
| bias | bearish | bearish |
| bias_rule | rule-3-no-break-carry | rule-3-no-break-carry |
| entry_paise | None | None |
| exit_kind | None | None |
| poc_paise | 1,125.35 | 1,125.35 |
| qty | None | None |
| reference_paise | 1,131.05 | 1,131.05 |
| stop_paise | None | None |
| target_paise | None | None |

