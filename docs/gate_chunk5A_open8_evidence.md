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

---

# FIX-2 (2026-07-25) — volume factor split (k_price / k_shares) + the LIVE 4b RELIANCE probe

Two refinements from the architect's reading of the FIX report. The Q-10 ruling addendum, the
ruling text, and the QUESTIONS.md cross-reference are in **QUESTIONS.md Q-10 ADDENDUM**.

## 1 — Volume factor split (k_price all-factors; k_shares share-count only)

Architect's ruling (verbatim): *"Volume un-adjustment uses k_shares — the product of SHARE-COUNT
event factors only (bonus, split, consolidation) — because vendors scale volume for share-count
changes but not for cash-dividend price adjustments. Price continues to use k_price = all factors.
price_raw = fetched / k_price ; volume_raw = fetched × k_shares."*

- `raw_price  = fetched / k_price ` where `k_price ` = product of ALL factors in `(D, F]`.
- `raw_volume = fetched × k_shares` where `k_shares` = product of `corp_actions.SHARE_COUNT_KINDS`
  factors (bonus, split; a consolidation is a reverse split → `KIND_SPLIT`) in `(D, F]`.

A special dividend back-adjusts the PRICE (so it is in `k_price`) but the vendor never rescales
volume for it (so it is NOT in `k_shares`). Before FIX-2 the single `k_cum` was used for both, so a
special dividend in the window over-corrected volume by its `k`. Now it does not.

| in-window events | k_price (price ÷) | k_shares (volume ×) | changed vs pre-FIX-2? |
|---|---|---|---|
| bonus only (e.g. TCS) | k_bonus | k_bonus | **no** (identical) |
| split only | k_split | k_split | **no** |
| special dividend only | 1−D/P | **1** | yes — volume no longer touched |
| bonus + special dividend | k_bonus·(1−D/P) | **k_bonus** | yes — volume by bonus only |

TCS (bonus-only) and every F10 2026 day (post-CA identity) are therefore **unchanged** — the
acceptance table above (0%/0%/56.5% → 100%/100%/97.2%) and F10 still hold. New tests pin the
special-dividend case (volume by the bonus only, 1000 not the wrong 900; price by both) at the unit
and gate-1 levels; the full suite is **883 / 0** offline. (A rights issue is a share-count change
but the ruling's verbatim list is bonus/split/consolidation and a rights `k` is a TERP blend, so
rights stays OUT of `k_shares` as written — flagged for the architect, decision B81.)

## 2 — 4b RELIANCE probe, executed LIVE (credentialed, polite pacing)

Ran against SmartAPI on 2026-07-25 (fetch date F). Credentials from `.env`, never printed. One
1-minute fetch per window; all comparisons are RAW-to-RAW (a pre-ex 1-min day vs that same day's
raw daily row). RELIANCE factor table built live: **2017-09-07 bonus k=0.5, 2020-05-13 rights
k=0.99061, 2024-10-28 bonus k=0.5; suppression 2023-07-20 Jio demerger; no pending rights.**

### 2a — 2024-10 window (bonus-only, provable) → un-adjusts to raw at 1.000×, gate-1 passes

Pre-ex day **2024-10-25** (only the 2024-10-28 bonus is in `(D, F]`; the demerger and 2020 rights
are *before* it, so `k_price = k_shares = 0.5`):

| | High | Low | Close | Volume |
|---|---|---|---|---|
| raw daily store | 268870 | 264400 | 265570 | 9,298,748 |
| 1-min **as fetched** (÷ raw) | 134435 (0.50000) | 132200 (0.50000) | 132815 | — |
| 1-min **un-adjusted** (÷ raw) | **268870 (1.00000)** | **264400 (1.00000)** | 265630 | 9,247,981 |

`|dH| = |dL| = 0` paise (**within 2**); close 60 paise (0.02%) off — the intraday-vs-official-close
noise. **Gate-1 (volume, via k_shares): gap 0.546% ∈ [−0.1%, +5.0%] → PASS.**

### 2b — 2016 window (the demerger probe) → 1-minute feed is NOT demerger-adjusted

Un-adjusting 2016 days by our table (`k_price = 0.5 × 0.5 × 0.99061 = 0.24765` — both bonuses + the
rights; the demerger is a suppression, not a factor) vs the RAW daily store:

| day | raw H | 1-min fetched H | 1-min un-adj H | R_fetched | R_unadj |
|---|---|---|---|---|---|
| 2016-10-03 | 110795 | 27347 | 110425 | 0.24683 | 0.99666 |
| 2016-10-04 | 110830 | 27356 | 110460 | 0.24683 | 0.99666 |
| 2016-10-05 | 110650 | 27311 | 110280 | 0.24682 | 0.99666 |
| 2016-10-06 | 112625 | 27799 | 112250 | 0.24683 | 0.99667 |
| 2016-10-07 | 112305 | 27720 | 111930 | 0.24683 | 0.99666 |
| 2016-10-10 | 112200 | 27694 | 111826 | 0.24683 | 0.99667 |

median **R_fetched = 0.24683**, median **R_unadj = 0.99666**.

**VERDICT = the SmartAPI 1-MINUTE feed is NOT demerger-adjusted.** A demerger-adjusted feed would
give `R_unadj ≈ 0.908` (the Jio residual); 0.99666 is ~1.000. The vendor's 2016 minute price
(₹273.5) = raw ₹1108 × ¼ (two 1:1 bonuses) × ~0.987 (a rights-ish factor) — **no ×0.908 demerger
term**. So **full RELIANCE minute history is PROVABLE by our bonus/rights table; the surgical clamp
fallback is NOT triggered.**

> **Corollary (important, new):** SmartAPI's ONE_MINUTE and ONE_DAY feeds adjust for DIFFERENT
> event sets. Chunk 4 proved the DAILY feed IS demerger-adjusted (RELIANCE daily 2020-07-13 ratio
> 0.4539 = bonus × demerger). The 1-MINUTE feed carries the bonuses (and a rights) but NOT the
> demerger. A cross-feed assumption ("if the daily is demerger-adjusted the minute is too") would
> have been wrong — hence the probe.

Minor caveat: a **~0.33% price residual** on pre-2020-rights days (`R_unadj 0.99666`, not exactly
1). The vendor's implied rights-equivalent (~0.9873) differs slightly from our CONTEXT 4.2 TERP
factor (0.99061) — a rights-convention or cum-close difference, two orders of magnitude below the
~9% demerger signal. It is within gate-1's volume band; on the ₹0.10 tick grid it tick-flags (a
cosmetic diagnostic, B75), it does not exclude.

### 2c — identity-skip rebuild guard (real data)

A fresh "pre-Q10" temp store was seeded with the as-fetched (adjusted) bars of a pre-bonus day
(2024-10-25, `k_price=0.5`) and a post-bonus day (2024-11-04, `k_price=k_shares=1`), then rebuilt:
`days_rewritten=1`, `identity_days=1`, and the post-bonus day is **byte-for-byte unchanged** — the
identity guard skips it, no unnecessary rewrite. The operator's real `data/minute_store` (TCS only)
was NOT touched; the probe used a throwaway scratchpad store.

### Architect follow-up flagged (before chunk 5B)

The Q-10 ruling conditioned the un-provable/clamp fallback on "pre-demerger spans **if the vendor
demerger-adjusts**". 2b settles that = NO. But the code still treats the demerger *suppression* as
an unknown-factor event that marks a 2016–2023 RELIANCE minute day UN-PROVABLE (gate-1 excludes;
the clamp could move to post-2023), which would now falsely drop ~7 years of provable data. Not
changed this session (Class-A, out of FIX-2 scope) — see QUESTIONS.md Q-10 ADDENDUM for the exact
ask. The demerger's bias-pair suppression in the daily/bias engine (CONTEXT 3.2) is separate and
stays.

---

# FIX-3 (2026-07-25) — demergers excluded from minute un-provability (Q-10 ADDENDUM 2), and a
# STOP: the 2016-only "not demerger-adjusted" premise does NOT generalise (Q-11)

The architect ruled (Q-10 ADDENDUM 2, verbatim in QUESTIONS.md) that, because FIX-2's 2016 probe
showed the 1-minute feed is not demerger-adjusted, demergers are EXCLUDED from the minute
un-adjustment chains and must NOT mark minute spans un-provable; gate-1 remains the per-day proof;
the daily bias-engine demerger suppression (CONTEXT 3.2) is separate and stays.

## Code change (done, gate-1-safe)

A demerger is a `Suppression(kind=KIND_DEMERGER)` and was **never** a `Factor`, so it was already
absent from `k_price`/`k_shares`. The one behaviour changed: a new PURE helper
`minute_unadjust.unprovable_suppression_dates()` returns only suppression ex-dates whose
`kind != KIND_DEMERGER` (i.e. Q-6 tier-2 unrecoverable rights). `unadjust_bars` and
`minute_backfill.rebuild_symbol_raw` both route through it, so a demerger ex-date in `(D, F]` no
longer marks a minute day un-provable; tier-2 rights and Q-6-pending rights still do. The
bias-engine demerger suppression (`bias_engine._bias_for`) is untouched. A test pins both halves:
`tests/test_minute_unadjust.py::test_demerger_provable_for_minutes_but_still_suppressed_for_bias`.

## LIVE RE-RUN through the fixed path (credentialed SmartAPI, polite, 2026-07-25) — the STOP

Raw-to-raw (a pre-ex 1-min day vs that same day's RAW daily row). RELIANCE factor table (live,
offline from the day-cache): 2017-09-07 bonus k=0.5, 2020-05-13 rights k=0.99061, 2024-10-28 bonus
k=0.5; suppression 2023-07-20 Jio demerger; no pending rights. Fetch date F = 2026-07-25.

**Provability (the FIX-3 change): every tested day comes out `provable=True`, `unprovable_days=[]`.**
The code change works exactly as ruled — a demerger in `(D, F]` no longer marks the day un-provable.

**But gate-1 does NOT pass, and a new contradiction appears.** un-adj/raw is the un-adjusted 1-min
daily-fold high over the raw daily high:

| window | in (D, F] | k_price | un-adj/raw price | gate-1 (k_shares) | gate-1 (k_price) | demerger baked in? |
|---|---|---|---|---|---|---|
| 2016-10 | 2017 bonus, 2020 rights, [demerger], 2024 bonus | 0.24765 | ~0.99666 | FAIL ~-1.24% | FAIL ~-0.29% | **NO** |
| 2019-07 | 2020 rights, [demerger], 2024 bonus | 0.49530 | ~0.99666 | FAIL ~-1.24% | FAIL ~-0.29% | **NO** |
| 2022-07 | [demerger], 2024 bonus | 0.50000 | **~0.90787** | **FAIL ~-10.14%** | **FAIL ~-10.14%** | **YES** |
| 2023-06 (pre-ex) | [demerger], 2024 bonus | 0.50000 | **~0.90786** | **FAIL ~-10.14%** | **FAIL ~-10.14%** | **YES** |
| 2023-09 (post-ex) | 2024 bonus only | 0.50000 | **1.00000** | **PASS +0.00%** | **PASS +0.00%** | n/a (clean) |

Reading the table:

- **2016 / 2019 (pre-2020-rights):** the ~0.33% price residual is the RIGHTS convention (vendor
  rights-equivalent vs our CONTEXT 4.2 TERP — decision B81), NOT the demerger. Via `k_shares` the
  volume over-corrects (~-1.24%) because the vendor scales pre-ex volume by its full price factor
  (rights included) while `k_shares` excludes the rights; even via `k_price` the gap (~-0.29%) is
  just past gate-1's -0.1% floor, so the day fails.
- **2022 / 2023-06 (post-rights, pre-demerger):** the un-adjusted price is exactly `raw × 0.908`
  — the Jio demerger factor is STILL IN the 1-minute feed for this era. Un-adjusting by the bonus
  only (per the ruling) leaves that ~9% error; gate-1 volume catches it at ~-10.1% and excludes it.
- **2023-09 (post-demerger):** the demerger is behind these days (not in `(D, F]`), only the 2024
  bonus is, and un-adjustment recovers RAW to the paisa (ratio 1.00000, gate-1 +0.00%) — the clean
  bonus-only case, unaffected by FIX-3.

**Conclusion (STOP, Q-11).** The vendor's 1-minute demerger adjustment is **inconsistent across its
own history**: absent for 2016 (FIX-2's measurement, reproduced: ratio 0.99666), present for
2022–2023 (ratio 0.908). FIX-2's generalisation ("the 1-minute feed is not demerger-adjusted") was
based on the 2016 window alone and does not hold. The FIX-3 code change is correct-per-ruling and
gate-1-SAFE (every affected day is excluded, nothing silently traded), but it rescues NO RELIANCE
minute data — every day it makes "provable" fails gate-1 (demerger residual on 2020–2023, rights
residual on 2016–2019). The correct un-adjustment for 2020–2023 RELIANCE minutes would INCLUDE the
demerger factor (opposite of the ruling), while 2016 must EXCLUDE it. The architect must decide the
demerger-symbol minute treatment (Q-11) before chunk 5B backfills RELIANCE-like symbols. The
demerger's daily bias-pair suppression (CONTEXT 3.2) is unaffected and stays.
