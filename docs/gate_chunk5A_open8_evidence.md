# Chunk 5A — Gate 3 / OPEN-8 evidence pack

**For the architect.** OPEN-8 asked: *is SmartAPI's historical 1-minute feed raw, or already
corporate-action adjusted?* The chunk-5A card made gate 3 settle it empirically during the TCS
backfill. This pack records the verdict and the numbers behind it.

> **UPDATE (2026-07-25, chunk-5A-fix): OPEN-8 stays ADJUSTED (the finding); Q-10 is RESOLVED
> and EXECUTED (the remedy).** The architect ruled option (a): un-adjust on ingest back to RAW
> using the chunk-3 factor table; the minute store now holds RAW ONLY and CONTEXT §7-E11 stands
> unchanged. The ruling, the code, and the before/after acceptance numbers are in the **Q-10
> REMEDY** section at the bottom of this pack. Chunk 6 (POC) is UNBLOCKED.

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

---

# Q-10 REMEDY — un-adjust on ingest back to RAW (RESOLVED, executed 2026-07-25)

OPEN-8 = ADJUSTED contradicted CONTEXT §7-E11 ("intraday engines run on RAW same-day 1-min
prices; tick grid preserved; PnL in that day's real rupees"): the vendor gives, for a candle on
day D fetched on date F, `raw × k_cum` where `k_cum` is the product of the CA factors of events
with ex-date in `(D, F]`. **Q-10** asked how the intraday layer obtains the raw same-day prices.

## The ruling (verbatim in QUESTIONS.md Q-10)

> "ARCHITECT'S RULING (option a, with surgical fallback): SmartAPI 1-min candles are UN-ADJUSTED
> ON INGEST back to RAW using the chunk-3 factor table: for a candle on day D fetched on date F,
> k_cum = product of factors of events with ex-date in (D, F]; raw_price = fetched_price / k_cum ;
> raw_volume = fetched_volume × k_cum. The minute store holds RAW ONLY — CONTEXT §7-E11 stands
> unchanged. Gate-1 (volume reconciliation vs raw bhavcopy) is hereby the per-day PROOF of factor
> correctness. Symbol-day spans where un-adjustment is unprovable ... and gate-1 fails → excluded +
> counted, and if a whole pre-event span fails systematically, that symbol's minute clamp moves to
> post-event (surgical restriction, disclosed). ... Ingest ledger must record the FETCH DATE per
> window (k_cum is fetch-dated); future top-ups un-adjust with a refreshed CA table."

## The key identity: un-adjust = the inverse of chunk-3's pairwise adjust

`k_cum = product of factors with ex-date in (D, F]` is **exactly**
`corp_actions.factors_between(factors, D, F)` — the same half-open `(previous, current]` window
the bias engine already *adjusts with*. So no new factor logic exists: `minute_unadjust` divides
prices (and multiplies volume) by the same chunk-3 table the bias engine multiplies by. Decimal
throughout, one half-even rounding to paise at the end (CONTEXT §7-E11). `k_cum == 1` (a recent,
post-last-CA day) is the **exact identity** — the fetched candle is stored byte-for-byte.

## Acceptance evidence (TCS, real data — the store rebuilt in place)

TCS's factor table over 2016-10..2026-07 has exactly **one** price-moving factor: the
**2018-05-31 Bonus 1:1 → k = 0.5** (fetched live from NSE, cum with a Rs 29 dividend; the bonus
takes parse precedence). No demergers, no pending rights → **every TCS day is provable**, so no
day is excluded on un-adjustment grounds and the clamp does not move.

### 4a — gate-1 pass rate by year, BEFORE (as fetched = adjusted) vs AFTER (un-adjusted)

| year | before (adjusted, as stored) | after (un-adjusted to RAW) |
|---|---|---|
| 2016 | **0 / 62 (0.0%)** | **62 / 62 (100.0%)** |
| 2017 | **0 / 248 (0.0%)** | **248 / 248 (100.0%)** |
| 2018 | **139 / 246 (56.5%)** | **239 / 246 (97.2%)** |
| 2019 | 241 / 245 (98.4%) | 241 / 245 (98.4%) |
| 2020 | 250 / 251 (99.6%) | 250 / 251 (99.6%) |
| 2021 | 246 / 247 (99.6%) | 246 / 247 (99.6%) |
| 2022 | 248 / 248 (100.0%) | 248 / 248 (100.0%) |
| 2023 | 245 / 246 (99.6%) | 245 / 246 (99.6%) |
| 2024 | 242 / 249 (97.2%) | 242 / 249 (97.2%) |
| 2025 | 247 / 249 (99.2%) | 247 / 249 (99.2%) |
| 2026 | 137 / 138 (99.3%) | 137 / 138 (99.3%) |

The three back-adjusted years **rise to the normal band** (0%/0%/56.5% → 100%/100%/97.2%),
matching 2019+. **No year fails.** 2019+ is byte-for-byte identical because those days are
post-bonus (k_cum = 1, identity) — un-adjustment does not touch them. The residual sub-100%
(2018's 7, 2019's 4, 2024's 7, etc.) is the **same before and after**: the ordinary gate-2
exclusions (Diwali Muhurat evenings, the 2020 COVID circuit-halt days, today's open partial
session), not adjustment.

### 4c — pre-2018-bonus TCS 1-minute vs raw bhavcopy (containment, not close equality)

Un-adjusted 1-minute daily-fold high/low vs the RAW daily store, 5 sampled pre-bonus days
(the last-30-min caveat respected: containment + gate-1 volume, not close equality):

| day | un-adj 1-min H/L (paise) | raw daily H/L (paise) | contained | gate-1 |
|---|---|---|---|---|
| 2016-10-03 | 245766 / 240110 | 245765 / 240110 | yes | PASS (gap 0.036%) |
| 2016-10-04 | 242506 / 239800 | 242505 / 239800 | yes | PASS (gap 0.045%) |
| 2016-12-01 | 229000 / 225406 | 229000 / 225405 | yes | PASS (gap 0.009%) |
| 2017-06-01 | 256400 / 253000 | 256400 / 253000 | yes | PASS (gap 0.031%) |
| 2018-05-30 | 353300 / 348250 | 353300 / 348250 | yes | PASS (gap 0.119%) |

The un-adjusted 1-minute extremes sit inside the raw daily range to within **1 paise** (the
vendor's own rounding of `raw × 0.5`, recovered by `÷ 0.5`). Continuity across the ex-date is
visible in the store: 2018-05-30 (last cum) first-minute open **₹3509.06**, 2018-06-01 (first
ex) **₹1754.00** — the raw ~half, exactly as a raw series behaves across a 1:1 bonus (the daily
bhavcopy halves the same way). Tick-note: the current instrument-master tick for TCS is ₹0.10,
but pre-2024 TCS traded on a ₹0.05 grid, so the tick-snap **flags** (never mis-snaps) a share of
old days — a disclosed cosmetic diagnostic, not a data defect (gate-1 is the correctness proof,
and it passes 100%).

### 4d — F10 is untouched (identity)

Every F10 day is in 2026, after TCS's last CA, so its factor window `(D, F]` is empty, `k_cum =
1`, and un-adjustment is the **exact identity** — asserted directly in
`tests/test_f10_volume_gate.py::test_f10_days_unadjust_to_the_exact_identity` (the un-adjuster,
run with a 2018 bonus + a 2023 demerger in the table and a 2026 fetch date, returns the F10 bars
byte-for-byte). F10's 25-day volume-gate golden still passes unchanged.

### 4b — RELIANCE spot windows (requires a live SmartAPI re-pull — operator action)

RELIANCE's 1-minute data is not in the local store (only TCS was backfilled), so 4b needs a
fresh, credentialed SmartAPI pull, which this session did **not** run. Two things are already
settled without it, and one is a genuine empirical question the re-pull answers:

- **The RELIANCE un-adjustment math is proven** against the real OPEN-8 evidence numbers in
  `tests/test_minute_unadjust.py::test_reliance_1to1_bonus_recovers_raw_prices_exactly`: the
  fetched 2024-10-25 pre-ex 1-minute high/low (134435 / 132200) divided by the exact bonus
  factor **k = 1/2** recovers the raw daily high/low **268870 / 264400 to the paisa**.
- **The 2024-10 window is provable** (ratio 1.000x expected): the RELIANCE 1:1 bonus (ex
  2024-10-28) is the only factor in `(2024-10-25, F]` — the Jio demerger (ex 2023-07-20) is
  *before* the window, so it does not enter k_cum. Command:
  `acumen-minute-backfill --symbol RELIANCE --from 2024-10-20 --to 2024-10-27 --allow-network`
  then the same with `--acceptance`.
- **The 2016 window is the demerger probe.** A 2016 RELIANCE day fetched in 2026 has the Jio
  demerger in `(D, F]`, and the demerger has NO factor (a Suppression). The daily feed is known
  to be demerger-adjusted (chunk-4: RELIANCE daily 2020-07-13 ratio 0.4539 = bonus × demerger).
  If the **1-minute** feed is demerger-adjusted too, un-adjusting by the bonus alone leaves a
  ~0.908 residual → gate-1 fails → the day is **un-provable, excluded and counted, and
  RELIANCE's minute clamp moves to post-2023-demerger** (the ruling's surgical fallback, already
  coded: `minute_unadjust.systematic_unprovable_floor`). If the 1-minute feed is *not*
  demerger-adjusted, the 2016 window reconciles to 1.000x. **Which one holds is exactly what the
  2016 re-pull settles** — an open empirical question the OPEN-8 probe never reached (its
  RELIANCE 1-min day was post-demerger). Either outcome is handled correctly by the code; the
  operator's re-pull records which, and the clamp/disclosure follow automatically.

## The store is now RAW

The existing TCS minute store was rebuilt in place (`minute_backfill.rebuild_symbol_raw`): the
pre-2018-bonus days were divided back by k_cum = 0.5, the post-bonus days are identity and were
left untouched. The persisted store now reads raw same-day prices everywhere (gate-1 by year on
the *persisted* store equals the "after" column above), satisfying CONTEXT §7-E11 without any
change to E11. The window ledger gained a `fetch_date` column (k_cum is fetch-dated); existing
rows fall back to `attempted_at` and new pulls record it explicitly. (One Windows `os.replace`
hiccup during the rebuild stopped it on an identity month, a no-op; the fix skips identity days
so the migration only rewrites the days that actually change.)
