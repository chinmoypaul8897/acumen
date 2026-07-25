# Chunk 5A — Gate 3 / OPEN-8 evidence pack

**For the architect.** OPEN-8 asked: *is SmartAPI's historical 1-minute feed raw, or already
corporate-action adjusted?* The chunk-5A card made gate 3 settle it empirically during the TCS
backfill. This pack records the verdict and the numbers behind it.

## VERDICT: **ADJUSTED** — the 1-minute feed is corporate-action back-adjusted (STOP)

SmartAPI returns historical 1-minute candles that have been adjusted for corporate actions that
happened *after* the candle's date. A day before a later split/bonus comes back at
`raw × k` for price and `raw × (1/k)` for volume. This is the same behaviour chunk 4 already
found for the ONE_DAY (daily) feed — now confirmed for ONE_MINUTE too.

Per the chunk-5A card, an ADJUSTED verdict is a **STOP**: recorded here and in QUESTIONS.md
(OPEN-8 resolution + **Q-10**), and **chunk 6 (POC) is blocked** until the architect decides how
the intraday layer obtains the raw same-day prices CONTEXT §7-E11 requires.

## How the verdict was reached (honoring the GATE LESSON)

The GATE LESSON (PROGRESS.md, chunk 4): a cross-source price comparison is only valid
**raw-to-raw with no corporate action in between**. So every comparison below is a **pre-ex
1-minute day vs the SAME day's RAW daily-store price** — the same calendar day, so there is no
event between the two sides. The daily store is known-raw (unadjusted NSE bhavcopy; it *halves*
at a bonus ex-date, exactly what raw prices do).

### Evidence 1 — TCS whole history (the clearest signal)

TCS did a **1:1 bonus in 2018**. If the 1-minute feed were raw, a 2016 TCS candle would equal the
2016 raw bhavcopy. Instead every pre-bonus day comes back at **half the price and double the
volume** — adjusted for the 2018 bonus:

| day (pre-2018-bonus) | 1-min close ÷ raw daily close | 1-min volume ÷ raw daily volume |
|---|---|---|
| 2016-10-03 | **0.5000** | **1.9993** |
| 2016-10-04 | **0.5000** | **1.9991** |
| 2016-12-01 | **0.5000** | **1.9998** |

The **gate-1 volume-reconciliation pass rate by year** is the smoking gun — a raw feed would
reconcile every year; an adjusted feed fails every year before the bonus and passes after it:

| year | gate-1 pass rate | reading |
|---|---|---|
| 2016 | **0 / 62 (0.0%)** | fully back-adjusted (÷2 price, ×2 volume) |
| 2017 | **0 / 248 (0.0%)** | same |
| 2018 | **139 / 246 (56.5%)** | the bonus ex-date (~June 2018) splits the year |
| 2019 | 241 / 245 (98.4%) | post-bonus: adjusted == raw |
| 2020 | 250 / 251 (99.6%) | |
| 2021 | 246 / 247 (99.6%) | |
| 2022 | 248 / 248 (100.0%) | |
| 2023 | 245 / 246 (99.6%) | |
| 2024 | 242 / 249 (97.2%) | |
| 2025 | 247 / 249 (99.2%) | |
| 2026 | 137 / 138 (99.3%) | |

(2019+ is TCS's post-last-CA span, so adjusted == raw and reconciliation passes; the handful of
sub-100% years are the ordinary gate-2 exclusions below, not adjustment.)

### Evidence 2 — the three named events (the formal gate-3 probe)

| event | pre-ex day | 1-min vs raw daily | verdict |
|---|---|---|---|
| **RELIANCE** 1:1 bonus ex 2024-10-28 | 2024-10-25 | ratios high **0.5000**, low **0.5000**, close **0.50011** (= raw × k, k=0.5024 from the raw gap) | **ADJUSTED** |
| KOTHARIPRO bonus ex 2016-01-05 | 2016-01-04 | no 1-minute data (predates the 2016-10 floor) | INDETERMINATE |
| GREENPLY FV split ex 2016-01-06 | 2016-01-05 | no 1-minute data (predates the 2016-10 floor) | INDETERMINATE |

RELIANCE is the one self-contained event with pre-ex 1-minute data, and it is decisive; the two
2016 microcaps predate the one-minute floor (RESULTS.md B) so they can neither confirm nor
contradict. Combined verdict = **ADJUSTED**, consistent with the TCS whole-history cross-check.

## What this means for CONTEXT §7-E11 (raised as Q-10)

CONTEXT §7-E11: *"intraday engines (POC, signals, simulator) run on RAW same-day 1-min prices
(tick grid preserved; PnL in that day's real rupees)."* The feed does not provide that for any
day before a later CA. For a **recent** day (after the symbol's last CA) adjusted == raw — which
is why the F10 calibration days (all 2026) and recent backtests are fine. For an **old** day the
stored prices are half-scaled and the tick grid is broken.

The architect's options (Q-10; **not decided by this session**): (a) un-adjust on ingest using
the chunk-3 CA factor table (`raw = adjusted ÷ product of post-date factors`), which keeps E11
intact; (b) amend E11 to run on adjusted prices (loses real-rupees/tick-grid, needs trader
awareness); (c) restrict the intraday window to each symbol's post-last-CA span; (d) switch to
the Zerodha Kite fallback (CONTEXT §4.3) if it serves raw minutes.

## Safety already in place

Nothing is silently traded on the half-scaled old prices: **gate 1 flags every affected old
symbol-day** (they fail volume reconciliation) and CONTEXT §7-E3 excludes and counts them. The
store holds the feed **as fetched** and labelled; no un-adjustment was applied.

## The rest of the TCS run (context)

- Depth found: first 1-minute date **2016-10-03** (matches RESULTS.md B); 2,430 symbol-days
  2016-10-03..2026-07-25; 129 windows, all present, 0 errors, ~906k candles.
- Gate-2 exclusions: **18** — all genuine non-standard/partial sessions (Diwali Muhurat evening
  sessions, the 2020 COVID circuit-halt days, and today's still-open partial session), not data
  defects. (An earlier run showed 38; the extra 20 were a window-boundary truncation and a
  too-strict gate, both fixed this session — see PROGRESS.)
