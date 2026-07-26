# Chunk 6 gate evidence -- the POC under BOTH candidate windows

**Status: PENDING.** This pack exists to answer one question the trader has been asked (Round-3 **Q42**) and nothing else.

## What is being asked

The strategy builds its volume profile from the morning session. The written specification (CONTEXT 3.3, from the trader's earlier answer R1-Q11) says the profile covers the **first eight 15-minute candles** -- 09:15 up to and including the candle that closes at 11:15. The trader's Round-3 screenshot of his TradingView Fixed Range Volume Profile shows the box drawn across what reads as **nine** candles (bar numbers 150 to 158 inclusive), which would extend it to 11:30.

One extra candle can move the POC, and the POC decides every entry that day. So both answers are computed below, side by side, on the days where his own readings exist.

* **8-candle (spec)** = spec-8-candle 09:15..11:14 (8 candles) -- what the engine uses today.
* **9-candle (alternative)** = evidence-9-candle 09:15..11:29 (9 candles) -- computed here as evidence only; no engine path selects it.
* Row Size N = 24 (the trader's own setting, confirmed by his Q32 screenshot).

## The table

| symbol | date | POC, 8-candle | POC, 9-candle | trader's reading | which window matches | source of the minutes |
|---|---|---|---|---|---|---|
| TCS | 2026-07-14 | 2205.25 | 2205.25 | 2205.3 | both (the two windows agree on this day) | frozen poc/data CSV |
| RELIANCE | 2026-07-16 | 1303.6 | 1303.6 | 1303.7 | both (the two windows agree on this day) | frozen poc/data CSV |
| HDFCBANK | 2026-07-14 | 815.275 | 815.275 | 815.3 | both (the two windows agree on this day) | frozen poc/data CSV |
| DIXON | 2026-07-16 | 14263.5 | 14263.5 | 14267 | both (the two windows agree on this day) | frozen poc/data CSV |
| MANAPPURAM | 2026-07-15 | 329.75 | 329.75 | 329.75 | both (the two windows agree on this day) | frozen poc/data CSV |
| ICICIBANK | 2026-07-17 | 1429.15 | 1429.15 | not known yet | no reading yet | local minute store (universe run) |
| BHARTIARTL | 2026-07-17 | 1914.6 | 1914.5 | not known yet | no reading yet | local minute store (universe run) |

**Q42's answer selects the window; nothing is locked until then.**

## What this evidence says today

* **6 of 7 days cannot tell the two windows apart** -- the ninth candle does not move the busiest band, so the POC (and any trade off it) is the same number either way.
* **BHARTIARTL 2026-07-17 DOES separate them**: 1914.6 under the 8-candle window against 1914.5 under the 9-candle one -- 0.1 rupees apart. This is the row to check against his chart.
* No POC reading has been relayed yet for ICICIBANK 2026-07-17, BHARTIARTL 2026-07-17. His Q32 screenshots confirmed his SETTINGS (Rows Layout = Number of Rows, Row Size = 24); what is still needed to close this gate is the POC PRICE he reads off those same charts.

## How to read a row

The POC is the middle price of the busiest price band of the morning. Both columns are computed by the same code from the same 1-minute candles -- the ONLY difference is where the window stops. Where the two columns are equal, that day cannot tell the two windows apart: the busiest band is the same either way, so no trade on that day would have differed.

## Proof that each day's prices are the real prices of that day

A POC computed from corporate-action-rescaled prices would be a plausible-looking wrong number, so each day is checked against the exchange's own daily figures before its POC is quoted: the 1-minute volume must reconcile with the official daily volume (the project's gate 1, band -0.1% to +5.0%), and the day's 1-minute high/low must match the official daily high/low.

| symbol | date | 1-min volume vs daily | gate 1 | 1-min high/low | official daily high/low |
|---|---|---|---|---|---|
| TCS | 2026-07-14 | 9,515,133 vs 9,546,290 (gap 0.326%) | PASS | 2228.00 / 2179.00 | 2228.00 / 2179.00 |
| RELIANCE | 2026-07-16 | 15,543,513 vs 15,631,046 (gap 0.560%) | PASS | 1309.40 / 1291.80 | 1309.40 / 1291.80 |
| HDFCBANK | 2026-07-14 | 25,164,225 vs 25,605,395 (gap 1.723%) | PASS | 818.40 / 807.00 | 818.40 / 807.00 |
| DIXON | 2026-07-16 | 2,248,355 vs 2,267,533 (gap 0.846%) | PASS | 14685.00 / 14101.00 | 14685.00 / 14101.00 |
| MANAPPURAM | 2026-07-15 | 1,335,787 vs 1,372,071 (gap 2.644%) | PASS | 335.80 / 326.65 | 335.80 / 326.65 |
| ICICIBANK | 2026-07-17 | 11,033,892 vs 11,112,550 (gap 0.708%) | PASS | 1455.10 / 1419.70 | 1455.10 / 1419.70 |
| BHARTIARTL | 2026-07-17 | 4,688,536 vs 4,715,613 (gap 0.574%) | PASS | 1925.20 / 1902.70 | 1925.20 / 1902.70 |

## Detail per day

### TCS 2026-07-14

* tick size 0.1 rupees (from the instrument master -- never assumed)
* 8-candle (spec): POC 2205.25 -- 120 traded minutes, range 2179.00..2228.00, 24 rows of 21 tick(s), busiest row #13 of 24
* 9-candle: POC 2205.25 -- 135 traded minutes, range 2179.00..2228.00, 24 rows of 21 tick(s), busiest row #13 of 24

### RELIANCE 2026-07-16

* tick size 0.1 rupees (from the instrument master -- never assumed)
* 8-candle (spec): POC 1303.6 -- 120 traded minutes, range 1295.50..1309.40, 24 rows of 6 tick(s), busiest row #14 of 24
* 9-candle: POC 1303.6 -- 135 traded minutes, range 1295.50..1309.40, 24 rows of 6 tick(s), busiest row #14 of 24

### HDFCBANK 2026-07-14

* tick size 0.05 rupees (from the instrument master -- never assumed)
* 8-candle (spec): POC 815.275 -- 120 traded minutes, range 808.30..818.40, 23 rows of 9 tick(s), busiest row #16 of 23
* 9-candle: POC 815.275 -- 135 traded minutes, range 808.30..818.40, 23 rows of 9 tick(s), busiest row #16 of 23

### DIXON 2026-07-16

* tick size 1 rupees (from the instrument master -- never assumed)
* 8-candle (spec): POC 14263.5 -- 120 traded minutes, range 14101.00..14685.00, 24 rows of 25 tick(s), busiest row #7 of 24
* 9-candle: POC 14263.5 -- 135 traded minutes, range 14101.00..14685.00, 24 rows of 25 tick(s), busiest row #7 of 24

### MANAPPURAM 2026-07-15

* tick size 0.05 rupees (from the instrument master -- never assumed)
* 8-candle (spec): POC 329.75 -- 120 traded minutes, range 329.00..335.80, 23 rows of 6 tick(s), busiest row #3 of 23
* 9-candle: POC 329.75 -- 135 traded minutes, range 329.00..335.80, 23 rows of 6 tick(s), busiest row #3 of 23

### ICICIBANK 2026-07-17

* tick size 0.1 rupees (from the instrument master -- never assumed)
* 8-candle (spec): POC 1429.15 -- 120 traded minutes, range 1419.70..1435.40, 23 rows of 7 tick(s), busiest row #14 of 23
* 9-candle: POC 1429.15 -- 135 traded minutes, range 1419.70..1437.30, 26 rows of 7 tick(s), busiest row #14 of 26

### BHARTIARTL 2026-07-17

* tick size 0.1 rupees (from the instrument master -- never assumed)
* 8-candle (spec): POC 1914.6 -- 120 traded minutes, range 1910.10..1925.20, 26 rows of 6 tick(s), busiest row #8 of 26
* 9-candle: POC 1914.5 -- 135 traded minutes, range 1910.00..1925.20, 26 rows of 6 tick(s), busiest row #8 of 26

## One more thing worth asking while he is at the chart

Separately from the window, CONTEXT 3.3 leaves one rounding case unstated: when the row arithmetic lands exactly between two row heights, the specification does not say which way TradingView goes (QUESTIONS.md **Q-13**). It matters on roughly one stock-day in six to ten, and it does not need a POC reading to settle -- just the NUMBER OF ROWS his profile draws on such a day. If he sends any chart with the rows countable, that answers it. Until then the engine keeps the direction that reproduces all 25 calibration days.

## What is NOT decided here

Nothing in this pack changes the engine. The spec's 8-candle window remains what the code computes, the trader's Row Size 24 remains what the code uses, and the chunk-6 gate stays PENDING until Round-3 Q42 comes back. If Q42 answers "nine", the architect amends CONTEXT 3.3 and the fixtures move with it -- this pack is what makes that a one-line change instead of a re-run.

Generated by: `acumen-poc-evidence --calibration TCS:2026-07-14 --calibration RELIANCE:2026-07-16 --calibration HDFCBANK:2026-07-14 --calibration DIXON:2026-07-16 --calibration MANAPPURAM:2026-07-15 --chart ICICIBANK:2026-07-17 --chart BHARTIARTL:2026-07-17 --reading TCS:2026-07-14=2205.3 --reading RELIANCE:2026-07-16=1303.7 --reading HDFCBANK:2026-07-14=815.3 --reading DIXON:2026-07-16=14267 --reading MANAPPURAM:2026-07-15=329.75`
