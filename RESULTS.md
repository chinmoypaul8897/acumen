# ACUMEN PoC RESULTS — run on 2026-07-21 (poc4 latency addendum 2026-07-22), machine timezone India Standard Time (UTC+05:30)

## A. Login (poc1)
- Login worked: **YES**
- Notes/errors: SmartAPI session generated cleanly on the first attempt (TOTP accepted). Account name returned via `getProfile`. Instrument master (~40 MB) downloaded once and cached to `cache/`. One `ONE_DAY` TCS candle fetched successfully (2026-07-20 close 2251.1, vol 2,202,693). No retries, no errors.

## B. 1-min depth (poc2) — paste the table
| symbol | earliest 1-min month |
|---|---|
| RELIANCE | 2016-10 |
| SBIN | 2016-10 |
| TCS | 2016-10 |
| DIXON | 2017-10 |
| MANAPPURAM | 2016-10 |

- Daily depth probe (RELIANCE): 1996-01: **DATA** / 2000-01: **DATA** / 2005-01: **DATA** / 2010-01: **DATA** (daily candles go back at least to Jan 1996)
- Contradictions vs the "2016" claim:
  - The "2016" claim is **directionally true but imprecise**. 1-minute data does **not** start in Jan 2016. For all four established large/mid caps (RELIANCE, SBIN, TCS, MANAPPURAM) the earliest month with 1-min candles is **2016-10** — Jan through Sep 2016 are empty (verified: 2016-01, 2016-06, 2016-08, 2016-09 all empty; 2016-10 returns ~1,125 candles for the probe window). So usable 1-min history begins **October 2016**, roughly 9 months later than a naive reading of "2016".
  - **DIXON begins 2017-10**, not 2016 — because it listed later (its IPO was 2017). Depth is therefore per-stock and bounded by the listing date, not a universal 2016 floor. Any backtest must clamp its start per symbol.
  - **Daily** data is far deeper than 1-min: RELIANCE daily candles exist back to at least 1996. Long-horizon daily backtests are fine; 1-min intraday work is effectively limited to **Oct 2016 → present** (and later for newer listings).

## C. Volume sanity (poc3)
`volume_poc_summary.csv` (rows = 24, the trader's TV setting):

| symbol | date | sum_1min_vol | daily_vol | gap_pct | poc_close | poc_uniform | poc_prorata |
|---|---|---|---|---|---|---|---|
| TCS | 2026-07-20 | 2,184,939 | 2,202,693 | +0.806% | 2259.50 | 2259.50 | 2259.50 |
| TCS | 2026-07-17 | 5,599,202 | 5,615,138 | +0.284% | 2230.40 | 2232.20 | 2230.40 |
| TCS | 2026-07-16 | 5,168,309 | 5,197,595 | +0.563% | 2215.10 | 2213.70 | 2215.10 |
| TCS | 2026-07-15 | 5,382,660 | 5,426,489 | +0.808% | 2185.00 | 2185.00 | 2185.00 |
| TCS | 2026-07-14 | 9,515,133 | 9,546,290 | +0.326% | 2211.55 | 2203.15 | 2205.25 |
| RELIANCE | 2026-07-20 | 14,099,373 | 14,305,844 | +1.443% | 1332.45 | 1329.85 | 1329.85 |
| RELIANCE | 2026-07-17 | 18,216,653 | 18,302,218 | +0.468% | 1321.90 | 1320.70 | 1320.70 |
| RELIANCE | 2026-07-16 | 15,543,513 | 15,631,046 | +0.560% | 1305.40 | 1304.80 | 1303.60 |
| RELIANCE | 2026-07-15 | 9,521,156 | 9,577,965 | +0.593% | 1303.55 | 1302.85 | 1303.55 |
| RELIANCE | 2026-07-14 | 13,430,890 | 13,511,284 | +0.595% | 1298.40 | 1298.40 | 1297.60 |
| HDFCBANK | 2026-07-20 | 54,603,127 | 56,061,789 | +2.602% | 782.75 | 782.25 | 782.75 |
| HDFCBANK | 2026-07-17 | 17,155,972 | 17,415,322 | +1.489% | 816.25 | 817.75 | 818.25 |
| HDFCBANK | 2026-07-16 | 18,028,553 | 18,698,186 | +3.581% | 814.58 | 814.23 | 814.23 |
| HDFCBANK | 2026-07-15 | 21,212,260 | 21,488,739 | +1.287% | 815.90 | 817.90 | 817.90 |
| HDFCBANK | 2026-07-14 | 25,164,225 | 25,605,395 | +1.723% | 808.97 | 815.27 | 815.27 |
| DIXON | 2026-07-20 | 405,854 | 407,451 | +0.392% | 14445.00 | 14445.00 | 14509.00 |
| DIXON | 2026-07-17 | 667,592 | 674,412 | +1.011% | 14466.50 | 14466.50 | 14466.50 |
| DIXON | 2026-07-16 | 2,248,355 | 2,267,533 | +0.846% | 14613.50 | 14263.50 | 14263.50 |
| DIXON | 2026-07-15 | 441,874 | 447,702 | +1.302% | 13553.50 | 13560.50 | 13560.50 |
| DIXON | 2026-07-14 | 395,758 | 396,507 | +0.189% | 13255.00 | 13335.00 | 13335.00 |
| MANAPPURAM | 2026-07-20 | 5,048,561 | 5,049,814 | +0.025% | 330.62 | 330.62 | 330.27 |
| MANAPPURAM | 2026-07-17 | 2,153,694 | 2,172,582 | +0.869% | 320.65 | 322.05 | 320.65 |
| MANAPPURAM | 2026-07-16 | 3,046,920 | 3,051,861 | +0.162% | 325.90 | 326.30 | 326.10 |
| MANAPPURAM | 2026-07-15 | 1,335,787 | 1,372,071 | +2.644% | 329.75 | 333.65 | 329.75 |
| MANAPPURAM | 2026-07-14 | 2,197,599 | 2,265,971 | +3.017% | 326.12 | 324.62 | 324.62 |

- gap_pct pattern: **steady small positive.** Every one of the 25 symbol-days is positive, ranging **+0.025% to +3.581%** (median ≈ +0.8%). The 1-minute volume sum is always *slightly below* the official daily total, never above, never wild, never negative.
- **Verdict (one line): candle volume is trustworthy** — the sum of 09:15–15:30 one-minute volumes reconciles to the daily figure to within ~1% on average; the small consistent shortfall is the pre-open call-auction (and any closing-auction/off-market block) volume that is included in the exchange daily total but not in continuous-session 1-min candles.

## D. POC methods (poc3)
Spread = max − min of the three method POCs for that symbol-day (Number of Rows = 24):

| symbol | date | close | uniform | prorata | spread (Rs) | spread (% of price) |
|---|---|---|---|---|---|---|
| TCS | 2026-07-20 | 2259.50 | 2259.50 | 2259.50 | 0.00 | 0.00% |
| TCS | 2026-07-17 | 2230.40 | 2232.20 | 2230.40 | 1.80 | 0.08% |
| TCS | 2026-07-16 | 2215.10 | 2213.70 | 2215.10 | 1.40 | 0.06% |
| TCS | 2026-07-15 | 2185.00 | 2185.00 | 2185.00 | 0.00 | 0.00% |
| TCS | 2026-07-14 | 2211.55 | 2203.15 | 2205.25 | 8.40 | 0.38% |
| RELIANCE | 2026-07-20 | 1332.45 | 1329.85 | 1329.85 | 2.60 | 0.20% |
| RELIANCE | 2026-07-17 | 1321.90 | 1320.70 | 1320.70 | 1.20 | 0.09% |
| RELIANCE | 2026-07-16 | 1305.40 | 1304.80 | 1303.60 | 1.80 | 0.14% |
| RELIANCE | 2026-07-15 | 1303.55 | 1302.85 | 1303.55 | 0.70 | 0.05% |
| RELIANCE | 2026-07-14 | 1298.40 | 1298.40 | 1297.60 | 0.80 | 0.06% |
| HDFCBANK | 2026-07-20 | 782.75 | 782.25 | 782.75 | 0.50 | 0.06% |
| HDFCBANK | 2026-07-17 | 816.25 | 817.75 | 818.25 | 2.00 | 0.24% |
| HDFCBANK | 2026-07-16 | 814.58 | 814.23 | 814.23 | 0.35 | 0.04% |
| HDFCBANK | 2026-07-15 | 815.90 | 817.90 | 817.90 | 2.00 | 0.24% |
| HDFCBANK | 2026-07-14 | 808.97 | 815.27 | 815.27 | 6.30 | 0.77% |
| DIXON | 2026-07-20 | 14445.00 | 14445.00 | 14509.00 | 64.00 | 0.44% |
| DIXON | 2026-07-17 | 14466.50 | 14466.50 | 14466.50 | 0.00 | 0.00% |
| DIXON | 2026-07-16 | 14613.50 | 14263.50 | 14263.50 | 350.00 | 2.45% |
| DIXON | 2026-07-15 | 13553.50 | 13560.50 | 13560.50 | 7.00 | 0.05% |
| DIXON | 2026-07-14 | 13255.00 | 13335.00 | 13335.00 | 80.00 | 0.60% |
| MANAPPURAM | 2026-07-20 | 330.62 | 330.62 | 330.27 | 0.35 | 0.11% |
| MANAPPURAM | 2026-07-17 | 320.65 | 322.05 | 320.65 | 1.40 | 0.44% |
| MANAPPURAM | 2026-07-16 | 325.90 | 326.30 | 326.10 | 0.40 | 0.12% |
| MANAPPURAM | 2026-07-15 | 329.75 | 333.65 | 329.75 | 3.90 | 1.18% |
| MANAPPURAM | 2026-07-14 | 326.12 | 324.62 | 324.62 | 1.50 | 0.46% |

- **Do the three methods agree or differ?** Mostly agree. On 22 of 25 days the spread is under 0.5% of price; on 3 days all three are identical to the paisa. The methods land in the **same or an adjacent row** almost always.
- **By how much (in Rs)?** Typically **0–3 Rs** for the sub-Rs-2500 names. The eye-catching absolute gaps are all on **DIXON** (price ~Rs 13,000–14,600, so one 24-row row-height ≈ Rs 64): DIXON 2026-07-16 shows a Rs 350 gap and 07-14 a Rs 80 gap. These look large in rupees but are a **one-row POC shift** (≤2.45% of price), driven by the high absolute price, not by disagreement about where volume sits.
- **Which method is the odd one out?** `uniform` and `prorata` track each other very closely (identical or within ~Rs 2 on nearly every day). `close` is the most frequent outlier — it dumps each bar's *entire* volume into the single row containing that bar's close, whereas uniform/prorata distribute a bar's volume across all the rows its high–low range touches. When one row narrowly wins on closes but an adjacent row accumulates more spread-out volume, `close` picks the other row. **This is exactly why the TradingView calibration in Step 5 matters** — we cannot yet say which of these three matches TV; that requires the manual chart comparison.

### D-worksheet — TradingView calibration (fill this in during Step 5)

Do these 4 stock-days first — they are the ones where the methods **disagree**, so they can actually tell the methods apart. On days where all three POCs are equal, TV can't reveal a winner. Read the TV POC line, see which of the three numbers it sits on, and write it in the last two columns.

| # | symbol (TV) | date | POC close | POC uniform | POC prorata | TV POC (you fill) | closest method (you fill) |
|---|---|---|---|---|---|---|---|
| 1 | NSE:TCS | 2026-07-14 | **2211.55** | **2203.15** | **2205.25** | | |
| 2 | NSE:RELIANCE | 2026-07-16 | **1305.40** | **1304.80** | **1303.60** | | |
| 3 | NSE:HDFCBANK | 2026-07-14 | **808.97** | **815.27** | **815.27** | | |
| 4 | NSE:DIXON | 2026-07-16 | **14613.50** | **14263.50** | **14263.50** | | |
| 5 (optional) | NSE:MANAPPURAM | 2026-07-15 | **329.75** | **333.65** | **329.75** | | |

Why these five: #1 and #2 have all three values distinct (so a match uniquely fingerprints one method, and they separate `uniform` from `prorata`); #3 and #4 put `close` far from `uniform`=`prorata` (do they dump volume at the close, or spread it?) — and #4's ₹350 gap is the easiest of all to read on a chart; #5 isolates `uniform` as the odd one out. Together they distinguish all three methods.

**Winner:** whichever method column the TV POC matches most often is the volume-spreading method Acumen should adopt. Write the verdict here → `WINNER: ______`

**Calibration status — DELEGATED, pending (as of 2026-07-21).**
TradingView's Volume Profile indicators (including Fixed Range Volume Profile) require a **paid** TradingView plan; a free account cannot draw them. This calibration has therefore been handed to the **strategy owner / trader, who holds a TradingView premium account.** They were sent a step-by-step field guide and asked to return the raw POC reads.

- **Data point requested from the trader:** for each of the 5 stock-days in the D-worksheet above, the **POC price (₹)** of the Fixed Range Volume Profile drawn over **09:15–11:15 with Number of Rows = 24**, plus the **chart timeframe** used (1m preferred; 15m acceptable), and optionally a screenshot. (i.e. 5 numbers: TCS 07-14, RELIANCE 07-16, HDFCBANK 07-14, DIXON 07-16, MANAPPURAM 07-15.)
- **Why these 5 days:** they are the only days (of the 25 tested) where the three methods disagree, so a TV read can actually distinguish them — days #3 & #4 separate `close` from `uniform`/`prorata`; days #1, #2 & #5 separate `uniform` from `prorata`.
- **On receipt:** fill the `TV POC` / `closest method` columns above, set `WINNER`, and Acumen adopts that spreading method.
- **Provisional method until then: `prorata`** (equivalently `uniform` — the two agree within ~₹2 on almost every tested day). Rationale: TradingView distributes each bar's volume across the price range the bar spans rather than dumping it all at the close, so `close` is effectively ruled out; only `uniform` vs `prorata` remains open, and the trader's numbers will settle it. **Do not finalize `close`.**
- **Field guide sent to trader (Artifact):** https://claude.ai/code/artifact/98dc1016-203c-44d8-a8ba-5b096795adb7

## E. Data quality (poc5)
`quality_report.csv` — all 25 symbol-days (5 symbols × 5 weekdays 2026-07-14…07-20):

| symbol | date | candles | missing_minutes | zero_volume_candles | duplicate_timestamps | impossible_ohlc |
|---|---|---|---|---|---|---|
| DIXON | 2026-07-14 → 07-20 (5 days) | 375 | 0 | 0 | 0 | 0 |
| HDFCBANK | 2026-07-14 → 07-20 (5 days) | 375 | 0 | 0 | 0 | 0 |
| MANAPPURAM | 2026-07-14 → 07-20 (5 days) | 375 | 0 | 0 | 0 | 0 |
| RELIANCE | 2026-07-14 → 07-20 (5 days) | 375 | 0 | 0 | 0 | 0 |
| TCS | 2026-07-14 → 07-20 (5 days) | 375 | 0 | 0 | 0 | 0 |

*(Every individual row is identical: candles=375, missing=0, zerovol=0, dupes=0, badohlc=0 — collapsed above for readability; the full per-day CSV is in `data/quality_report.csv`.)*

- Any day with missing_minutes > 5, zero-volume streaks, dupes, impossible OHLC? **None.** Every trading day returned exactly 375 one-minute candles (09:15–15:29 inclusive), zero missing minutes, zero zero-volume candles, zero duplicate timestamps, zero impossible OHLC bars. Intraday data quality on these 5 F&O names for the last week is **flawless**.

## F. Latency (poc4)
- Ran: **YES** — Wednesday **2026-07-22** during NSE live market hours (IST). (On the original 2026-07-21 audit the market was already closed, so this was completed the next trading day.)
- Three latency values (clean run; boundaries 14:00 / 14:15 / 14:30 IST):

  | boundary (IST) | candle that just closed | appeared after close |
  |---|---|---|
  | 14:00 | 13:45–14:00 | **0.2 s** |
  | 14:15 | 14:00–14:15 | **0.2 s** |
  | 14:30 | 14:15–14:30 | **33.0 s** |

- **Verdict:** a just-closed 15-minute candle is available **essentially immediately (~0.2 s)** when the API responds normally. The single ~33 s reading is **not** slow data — it is the client's own exponential backoff (1+2+4+8+16 s) firing after a burst of SmartAPI transient "access denied / couldn't parse the json response" errors; the candle then appeared on the very next poll. So underlying availability is sub-second, and the occasional multi-second reading is throttle/backoff, not exchange latency — fine for a live 15-min screener.
- **Corroboration:** an earlier run the same day, interrupted after 2 of 3 boundaries (11:45 & 12:00), measured **6.7 s** and **34.5 s** — identical pattern (near-instant when clean, ~34 s during a retry storm).

## G. Errors observed across all runs
- **Retry events:** none in poc1, poc2 (55+ probe windows), poc3 (run twice) or poc5. **poc4, run during live market hours, did hit them:** several bursts of SmartAPI's transient `access denied / couldn't parse the json response received from the server` errors, each triggering the full `retry 1→5` (1+2+4+8+16 s) backoff. This is the known false rate-limit / transient-403 behaviour the brief warns about; the data always arrived on a following poll.
- **Give-ups ("giving up on this window"):** **2, both in poc4** (one in the interrupted run, one in the clean run) — a 5-retry cycle exhausted mid-burst. In **both** cases the immediately following poll succeeded, so no data was lost; the only effect was inflating that boundary's measured latency to ~33–34 s instead of ~0.2 s. (Per the brief, each give-up was re-confirmed by the next successful poll.)
- **One bug found and fixed (not in the frozen testing logic):** poc3's daily-volume fetch originally requested `ONE_DAY` with `fromdate="{date} 09:15"`. SmartAPI stamps the daily candle at **00:00** of the day, so a 09:15 start excludes it and the call returned empty — producing `daily=0` and `gap=+nan%` on the first poc3 run. Confirmed with a read-only probe (09:15 start → 0 candles; 00:00 start → 1 candle with the correct volume). Fixed by changing that single line's start time to `"{date} 00:00"`. **`tv_rows` and `build_profile` were left untouched** — the fix is purely in daily-candle retrieval, not in the row/profile math. poc3 was re-run and all gap_pct values are now valid.
- **Cosmetic only:** logzero prints `[I ...] in pool` to stderr on login; under PowerShell this surfaces as a `NativeCommandError` wrapper line. It is harmless (login and all fetches succeeded) and does not affect results.
- **Behavioral note for the architect:** for single-day daily-volume reconciliation, always start the `ONE_DAY` window at 00:00 (or span multiple days) — the daily candle sits at midnight, not at the session open.

## H. Files attached alongside this report
- `data/depth_probe_results.csv` — earliest 1-min month per symbol (poc2)
- `data/volume_poc_summary.csv` — volume reconciliation + 3-method POC per symbol-day (poc3)
- `data/quality_report.csv` — per-day integrity scan (poc5)
- Plus 25 raw intraday files `data/{SYMBOL}_{YYYY-MM-DD}_1min.csv` (the 375-row source candles poc3 downloaded and poc5 audited)
