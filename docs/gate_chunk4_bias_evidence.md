# Chunk 4 — Bias engine · TRADER GATE evidence pack

**For the trader (via Paul). Please check this against your own TCS chart.**

This is the daily **bias** rule — the first thing the tool computes each day, before any trade.
We built it to match your rules exactly. Below are **15 real TCS days**. For each one we show
the two candles the bias is read from and the bias the tool produced. Every price is in rupees,
straight off the daily chart. You should be able to eyeball each row in a few seconds.

## How to read each row

To decide the bias **for a trading day**, the tool looks at the **two previous trading days**:

- **Previous candle** = the day-before-yesterday candle (we call it P).
- **Current candle** = yesterday's candle (we call it C).
- It then applies your rules **in order**: inside bar → Rule 1 (close breakout) → Rule 2
  (sweep) → Rule 3 (outside bar) → otherwise keep the last bias.

"Body" means the open-to-close range of the **previous** candle (P). These are all **plain
market days — no splits, bonuses or special dividends** in this window, so the numbers here are
exactly what your chart shows (nothing is adjusted).

## The 15 real TCS days

| Bias is for | Previous candle P (O/H/L/C) | Current candle C (O/H/L/C) | Which rule fired | Bias |
|---|---|---|---|---|
| 2025-07-01 | 2025-06-27 O3,455.00 H3,466.40 L3,431.00 C3,441.10 | 2025-06-30 O3,439.90 H3,464.90 L3,430.00 C3,462.00 | Rule 1 (close broke **above** the previous body) | **BULLISH** |
| 2025-07-02 | 2025-06-30 O3,439.90 H3,464.90 L3,430.00 C3,462.00 | 2025-07-01 O3,455.00 H3,485.00 L3,413.50 C3,429.70 | Rule 1 (close broke **below** the previous body) | **BEARISH** |
| 2025-07-03 | 2025-07-01 O3,455.00 H3,485.00 L3,413.50 C3,429.70 | 2025-07-02 O3,487.20 H3,489.90 L3,420.00 C3,423.30 | Rule 1 (close below the previous body) | **BEARISH** |
| 2025-07-04 | 2025-07-02 O3,487.20 H3,489.90 L3,420.00 C3,423.30 | 2025-07-03 O3,430.00 H3,435.30 L3,397.60 C3,400.80 | Rule 1 (close below the previous body) | **BEARISH** |
| 2025-07-07 | 2025-07-03 O3,430.00 H3,435.30 L3,397.60 C3,400.80 | 2025-07-04 O3,408.00 H3,427.00 L3,390.10 C3,419.80 | Rule 2 (swept the **low**, closed back inside) | **BULLISH** |
| 2025-07-08 | 2025-07-04 O3,408.00 H3,427.00 L3,390.10 C3,419.80 | 2025-07-07 O3,418.30 H3,426.10 L3,408.40 C3,411.70 | Inside bar (stayed inside P → **keep** the bias) | **BULLISH** |
| 2025-07-09 | 2025-07-07 O3,418.30 H3,426.10 L3,408.40 C3,411.70 | 2025-07-08 O3,405.00 H3,425.00 L3,393.40 C3,406.20 | Rule 1 (close below the previous body) | **BEARISH** |
| 2025-07-10 | 2025-07-08 O3,405.00 H3,425.00 L3,393.40 C3,406.20 | 2025-07-09 O3,410.00 H3,414.00 L3,367.00 C3,383.80 | Rule 1 (close below the previous body) | **BEARISH** |
| 2025-07-11 | 2025-07-09 O3,410.00 H3,414.00 L3,367.00 C3,383.80 | 2025-07-10 O3,380.00 H3,399.00 L3,356.00 C3,382.00 | Rule 1 (close below the previous body) | **BEARISH** |
| 2025-07-14 | 2025-07-10 O3,380.00 H3,399.00 L3,356.00 C3,382.00 | 2025-07-11 O3,299.90 H3,335.00 L3,261.10 C3,266.00 | Rule 1 (close below the previous body) | **BEARISH** |
| 2025-07-15 | 2025-07-11 O3,299.90 H3,335.00 L3,261.10 C3,266.00 | 2025-07-14 O3,266.00 H3,272.00 L3,200.00 C3,222.70 | Rule 1 (close below the previous body) | **BEARISH** |
| 2025-07-16 | 2025-07-14 O3,266.00 H3,272.00 L3,200.00 C3,222.70 | 2025-07-15 O3,206.00 H3,259.40 L3,206.00 C3,252.30 | Inside bar (stayed inside P → **keep** the bias) | **BEARISH** |
| 2025-07-17 | 2025-07-15 O3,206.00 H3,259.40 L3,206.00 C3,252.30 | 2025-07-16 O3,227.00 H3,244.90 L3,220.60 C3,233.10 | Inside bar (stayed inside P → **keep** the bias) | **BEARISH** |
| 2025-07-18 | 2025-07-16 O3,227.00 H3,244.90 L3,220.60 C3,233.10 | 2025-07-17 O3,224.10 H3,242.00 L3,204.10 C3,209.20 | Rule 1 (close below the previous body) | **BEARISH** |
| 2025-08-11 | 2025-08-07 O3,016.00 H3,051.60 L3,010.90 C3,047.00 | 2025-08-08 O3,048.10 H3,059.80 L3,025.00 C3,036.40 | Rule 2 (swept the **high**, closed back inside) | **BEARISH** |

### A couple of worked examples, in words

- **2025-07-01 → BULLISH.** The two candles read are 27-Jun (previous, P) and 30-Jun
  (current, C). P's body ran from 3,441.10 to 3,455.00. C closed at **3,462.00**, which is
  **above** P's body top (3,455.00). A close above the body = a breakout up = **bullish**. This
  is also the first day the tool produced a bias (the "seed" day).
- **2025-07-08 → stays BULLISH.** Yesterday's candle (07-Jul: high 3,426.10, low 3,408.40) sat
  **entirely inside** the previous day (04-Jul: high 3,427.00, low 3,390.10). An inside day
  tells us nothing new, so the bias is **kept** — it stays bullish from 07-Jul.
- **2025-08-11 → BEARISH.** Yesterday's candle (08-Aug) poked **above** the previous high
  (3,051.60 → 3,059.80) but then closed back **inside** the body at 3,036.40. A failed push up
  = **bearish** (Rule 2).

## Two things we are ASSUMING — please confirm (OPEN-4)

Your worked example (Q31) covered the **outside-bar tie** where the 1-minute candle closes
**red near its bottom** — you answered **Bullish**, and we built exactly that. Two related
cases you did not spell out, which we filled in by symmetry and flagged for you:

1. **Green-tie mirror.** If an outside bar's decisive 1-minute candle closes **green** (up)
   instead of red, we make the bias **BEARISH** — the exact mirror of your red-tie answer.
   **Please confirm this mirror is what you'd do.**
2. **Doji tie.** If that 1-minute candle closes **exactly at its open** (a doji — no red, no
   green), we make **no new decision and keep the previous bias**, and we log the day.
   **Please confirm keeping the last bias is right for a doji.**

(These outside-bar/tie cases need 1-minute data to verify on real days; that verification is
scheduled for a later step. The 15 days above are all decided from the daily candles alone.)

## The ask

**Please reply `CONFIRMED`, or tell us which row looks wrong** (and what you'd have called it).
That's all we need to lock the bias engine.
