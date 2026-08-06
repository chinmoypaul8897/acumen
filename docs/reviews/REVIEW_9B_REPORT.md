# REVIEW_9B_REPORT — QC of the chunk-9B BACKTEST REPORT

**Session:** 2026-08-06 · fresh session · BOTH personas (`personas/quant_reviewer.md`,
`personas/code_reviewer.md`) · directed span `41f3e3e..796c39d`.

**Subject:** `docs/reports/chunk9b_backtest_report.md` (880 lines) and its generator
`src/acumen/report_9b.py`, over the completed ten-year run ledger
`<data_root>/backtests/chunk9b_full` — headline **net −Rs 16,836,018.20 on 188,345 trades**.

**Stance.** The brief's instruction was to assume every number is wrong until recomputed. Every
headline figure in this report has therefore been re-derived **importing nothing from
`src/acumen`** — including CONTEXT 3.2, 3.3, 3.4 and 3.5 re-implemented from the spec text for two
hand-walked trading days, and the 15-minute portfolio path re-assembled from the raw 1-minute
parquet with this session's own aggregation. Five evidence packs are committed with this review:

| Pack | What it re-derives |
|---|---|
| `docs/evidence/review9b_report_recompute.{py,md}` | the headline, the eleven year rows, the Long/Short split, close-to-close drawdown and run-up, the 32 manifest checks, the pilot 290, the crashed 145, Tukey on all three columns, R10's pricing, MFE/MAE, the take-all disclosures, all 204 per-symbol rows |
| `docs/evidence/review9b_path_recompute.{py,md}` | the 15-minute portfolio equity path: 1,101,029 marks re-assembled from the lake, its drawdown and run-up |
| `docs/evidence/review9b_benchmark_recompute.{py,md}` | CONTEXT 7-E13's benchmark in both price domains, and what is actually inside the 433 factors |
| `docs/evidence/review9b_gap_walks.{py,md}` | MUTHOOTFIN 2016-10-06 and TIINDIA 2026-07-27 walked bias → POC → signal → money, digit by digit |
| `docs/evidence/review9b_register_and_symbols.{py,md}` | the disclosed-residual register against section 9's coverage column and the B149 caveat |

---

## 0. Two things about the span, recorded before anything else

**(a) The directed span is NARROWER than the unreviewed arc.** The last reviewed tag is
`chunk9b-relaunch-pass` = `c34c088`. Eight commits sit between it and HEAD; the brief names the
last four. The first four — `5afab98`, `d224563`, `de584ac`, `41f3e3e` — are reviewed by nobody,
and two of them touch `src/acumen` (`universe_backfill.py` +18/−1, `trade_evidence.py` 1 line)
and two test files. They are audited here as a supplement (finding **C3**); nothing in them is
wrong, but the gap is recorded rather than left for a later session to discover.

**(b) The run's code SHA is `c34c0880…` = the tag.** The report re-assembles 15-minute paths at
HEAD over a ledger written under that SHA, so every engine module was compared blob-to-blob
against it: `bias`, `poc`, `signals`, `simulate`, `aggregate`, `backtest`, `portfolio`,
`bias_engine`, `quality_gates`, `minute_store`, `daily_store`, `instrument_master`, `config` —
**13 of 13 IDENTICAL**. The report is reading and re-deriving under exactly the code that wrote
the ledger.

---

## VERDICT

**PASS**, with **one owed edit that the architect's own ruling creates** and **one disclosure
that must ride with it**. Neither is a defect in a number: every figure on the page reproduces.

* **15 findings, none blocking**: quant — 3 MEDIUM, 4 LOW, 2 INFO; code — 2 MEDIUM, 3 LOW,
  1 INFO. Not one of them is a wrong number.
* **A 10-mutant matrix over the generator: the shipped suite catches 3.** Four of the five
  corrections commit `4eba3bf` ships — including the Sharpe/Sortino refusal it headlines, and
  the CALL SITE of the walked-day index fix — can be reverted with all 2,140 tests green.
  All seven survivors are closed by kept probes, each verified RED on its own mutant.
* **THE HEADLINE IS TRUE.** −Rs 16,836,018.20 on 188,345 trades, PF 0.8708, win rate 31.53%,
  avg win Rs 1,911.49, avg loss −Rs 1,011.09, expectancy −Rs 89.39, largest pair
  +Rs 2,900.00 / −Rs 1,100.00, all eleven year rows and the Long/Short split — **every one
  reproduced to the paisa** from the raw ledger by arithmetic that shares no line of code with
  the generator.
* **The 15-minute path reproduces to the paisa and to the observation**, from candles this
  session aggregated itself.
* **Reconciliation 32 of 32, pilot 290 of 290 field-for-field, crashed run 145 of 145 attributed,
  zero unexplained** — all three re-derived.
* Suite **2140 passed / 0 failed / 0 skipped** from clean; **2151** with this review's 11 kept
  probes. No test weakened, deleted or skipped; no fixture byte moved; no secrets; no AI
  attribution; `HEAD == origin/main` at entry; **zero store writes**.

---

## PART 0 — the architect's Q-23 ruling, RECORDED and CHECKED

Recorded verbatim in `QUESTIONS.md` under Q-23, whose heading is moved from **OPEN — STOP** to
**RULED 06-Aug-2026**:

> "ARCHITECT'S RULING (06-Aug-2026), Q-23: the buy&hold benchmark is the SHARE-COUNT-ADJUSTED
> construction (491.90% as generated) — buy-and-hold holds UNITS, which multiply through
> bonuses/splits; fixed-unit raw closes falsify wealth at every event. Dividends excluded and
> stated. Both figures remain printed; the adjusted one is THE benchmark. Architect."

### Does the generator publish exactly that? **No — and that is THE ONE OPEN EDIT.**

Verified by reading the generator, not the output. `src/acumen/report_9b.py` still carries
`BENCHMARK_STOP` (the Q-23 STOP paragraph), still titles section 10
*"Buy & hold — BOTH readings, and neither published"*, still writes *"This report does not decide
it"*, and decision **B275** still records *"NEITHER is published"*. Section 13's closing line
still says *"the benchmark's price domain (Q-23 open, both readings shown)"*.

What the ruling requires and the report already does: **both figures are printed** (RAW 298.92%,
adjusted 491.90%, side by side with the strategy's own −16836.02%). What is missing is the
**label**. Owed to the generator, not to the file: retitle section 10, mark the adjusted row as
THE benchmark, replace the STOP quote with the ruling, re-point B275, and fix section 13's line.
**No number moves.**

### Is 491.90% right? **Yes, re-derived independently.**

`docs/evidence/review9b_benchmark_recompute.{py,md}` re-implements E13's construction from its
own words and reads the bhavcopy parquet directly:

| Reading | End value (mine) | Return (mine) | Report |
|---|---:|---:|---:|
| RAW closes as stored | Rs 398,922.17 | **298.92%** | 298.92% |
| Share-count ADJUSTED | Rs 591,899.89 | **491.90%** | 491.90% |

134 of 204 symbols carry a close on 2016-10-03 and are IN; 70 are excluded and named. The
construction is also the RIGHT one for a held portfolio — dividing the first close by the pending
factors is arithmetically identical to multiplying the holder's units by their reciprocal — and
the falsification the ruling names is measurable: **25 of the 134 symbols are read as a LOSS by
the raw reading while the units actually held say a gain** (NESTLEIND 0.230× raw vs 4.593×
adjusted; BEL 0.302× vs 9.979×; IOC 0.232× vs 2.435×).

### The one thing the ruling's words and the generated number do not agree about (finding Q2)

*"Dividends excluded and stated."* The 491.90% as generated does not exclude every dividend. The
433 factors section 10 calls *"share-count factors"* decompose, from the run's own factor table:

| Event kind | Non-unit factors in span |
|---|---:|
| **dividend / special** | **308** |
| bonus | 77 |
| split | 35 |
| rights | 13 |
| **total** | **433** |

Only **125** are share-count events. A special dividend does not multiply a holder's units.
Measured: share-count events alone give **Rs 566,668.64 = 466.67%**; the 308 special dividends
carry it to **491.90%** — **+25.23 percentage points, 5.13% of the published benchmark**.

Q-23 disclosed this asymmetry when it was raised (*"that asymmetry is the architect's to accept
or reject with the rest"*), and the ruling's *"as generated"* clause reads as accepting it, so
**this session treats 491.90% as the ruled figure and changes nothing**. What is owed is the
*"and stated"* half: section 10 currently says *"Both readings are PRICE returns. Ordinary
dividends carry k = 1 … and are not added back on either side"* — true of ORDINARY dividends,
not true of the 308 special ones. If the architect meant share-count events only, the figure is
**466.67%** and one line of `benchmark_pair` changes. Recorded under Q-23, decided by nobody here.

---

## DIRECTED CHECK 1 — THE HEADLINE, recomputed from the raw ledger

Importing nothing from `src/acumen`; all arithmetic in integer paise and exact Fractions.
Full table in `docs/evidence/review9b_report_recompute.md` §1.

| Figure | Recomputed | The report | |
|---|---:|---:|---|
| **Net PnL** | **−Rs 16,836,018.20** | −Rs 16,836,018.20 | OK |
| Gross profit (net basis) | Rs 113,514,085.92 | Rs 113,514,085.92 | OK |
| Gross loss (net basis) | −Rs 130,350,104.12 | −Rs 130,350,104.12 | OK |
| Profit factor | 0.8708 | 0.8708 | OK |
| Trades | 188,345 | 188,345 | OK |
| Winners / losers / flat | 59,385 / 128,920 / 40 | 59,385 / 128,920 / 40 | OK |
| Win rate | 31.53% | 31.53% | OK |
| Avg profit | Rs 1,911.49 | Rs 1,911.49 | OK |
| Avg loss | −Rs 1,011.09 | −Rs 1,011.09 | OK |
| Avg profit / avg loss | 1.8905 | 1.8905 | OK |
| Expected payoff per trade | −Rs 89.39 | −Rs 89.39 | OK |
| Largest win / largest loss | Rs 2,900.00 / −Rs 1,100.00 | same | OK |
| Commission paid | Rs 18,834,500.00 | Rs 18,834,500.00 | OK |
| Shares | 256,816,544 | 256,816,544 | OK |

**The decomposition, as arithmetic.**
net + 188,345 × Rs 100.00 = −Rs 16,836,018.20 + Rs 18,834,500.00 = **Rs 1,998,481.80**, which is
the ledger's own before-costs gross to the paisa. Costs recounted = Rs 18,834,500.00 = 188,345 ×
Rs 100.00. **Every executed row carries a cost of exactly Rs 100.00** and **every executed row's
net == gross − cost** — both checked on all 188,345 rows, zero exceptions.

**The break-even win rate, beside the actual.**

```
W = avg win   Rs 1,911.49
L = avg loss  Rs 1,011.09  (magnitude)
break-even p* = L / (W + L) = 1,011.09 / 2,922.58 = 34.60%
ACTUAL p      = 31.53%
shortfall     = 3.07 pp  ->  ~5,774 winners the strategy did not have
```

That is the whole story of the −₹16.8m in one line: a 1.89:1 payoff needs 34.60% to break even
and the strategy hit 31.53%.

**Long / Short.** Long −Rs 13,248,749.37 (89,345 trades, PF 0.7908) + Short −Rs 3,587,268.83
(99,000 trades, PF 0.9465) = **−Rs 16,836,018.20** exactly; trades 89,345 + 99,000 = 188,345
exactly; only `long` and `short` appear as sides. `winners × avg profit == gross profit` verified
**exactly, in Fractions, on all three columns** — the identity the E13 basis ruling buys.

**The eleven year rows** all reproduce (trades, win rate, net, PF, avg trade, in-year drawdown,
gap entries), the eleven changes **sum to the run's net exactly**, and **11 of 11 are negative**.

**All 204 per-symbol rows of section 9 recomputed cell by cell — 1,632 cells, 0 disagreements**,
and the per-symbol nets sum to the run's net. 28 of 204 symbols are net positive.

---

## DIRECTED CHECK 2 — DRAWDOWNS, and the refusals

**Close-to-close, recomputed over the walked-day index (2,428 observations):**

> **Rs 16,852,007.80 (14,528.90%), 2016-10-06 → 2026-07-30, 2,424 daily observation(s),
> recovered never inside the span.** — identical to the report, field for field.

The denominator is the highest closing equity, Rs 115,989.60 on 2016-10-06. **Never recovered,
proved directly**: the number of later observations at or above that peak is **0**, and the
trough IS the last observation of the run.

Run-up close-to-close: **Rs 407,255.90, 2024-11-08 → 2025-01-13, 43 observations, given back
2025-02-24** — identical. Its base equity is −Rs 13,936,895.00, so the percentage is refused,
correctly, and it is printed **trough-first**, in the order it happened.

**The 15-minute path, RE-ASSEMBLED from the raw lake** (`review9b_path_recompute`): 1-minute
parquet read with pandas, out-of-session stamps dropped at the candle level, 15-minute bars built
from CONTEXT 7-E12's grid by this session's own code, every open position marked at each candle
close it was held through, exit candles at their EXIT LEVELS, cost charged at the entry mark.

| | Mine | Report |
|---|---:|---:|
| marks assembled | **1,101,029** | 1,101,029 |
| paths whose last mark reproduces the ledger net | **188,345 / 188,345** | 188,345 / 188,345 |
| paths whose FIRST mark is exactly −Rs 100.00 | **188,345 / 188,345** | (B194's rule) |
| marks outside the 09:30..15:30 close grid | **0** | — |
| path observations | **40,981** | 40,981 |
| days whose last path point == that day's closing equity | **2,428 / 2,428** | (the tying invariant) |
| **max drawdown** | **Rs 16,864,934.22 (13,174.01%)** | Rs 16,864,934.22 (13174.01%) |
| from → to | **2016-10-07 11:45 → 2026-07-30 15:00** | same |
| observations | **40,909 of 40,981** | same |
| recovered | **never** (0 later points at or above Rs 128,016.70) | never |
| **max run-up** | **Rs 424,810.90**, 2024-11-05 13:30 → 2025-01-14 12:30, 795 obs, given back 2025-02-24 13:00 | identical |

The path drawdown **exceeds** the close-to-close one, as it must — it sees falls the 15:15 close
does not.

**The negative-equity REFUSALS fire for the stated reason, and nothing sign-pathological prints.**
Measured: **2,390 of 2,428** daily observations sit at or below zero equity, the first on
**2016-11-30**; **2,389 of 2,428** daily-return divisions therefore have a NEGATIVE denominator.
All three columns cross zero. Built from those returns, an annualized Sharpe prints
**+0.5882** by this session's own arithmetic — a *positive* Sharpe for a strategy that ended at
−Rs 16,736,018.20. (The session recorded +0.5833; the small difference is an estimator detail
between two implementations of the same broken quantity, and it is not a published figure.) The
report prints `n/a` with its reason on Sharpe **and** Sortino, on **all three columns**, and
CAGR prints `undefined` on all three. Every excursion percentage whose base is at or below zero
prints the reason instead of a number — checked on all eleven year rows and both run-up rows.
**No sign-pathological number appears anywhere on the page.**

---

## DIRECTED CHECK 3 — the three reconciliations, re-verified

**The 32 manifest checks: 32 of 32 agree**, recounted from all 495,312 rows by this session's own
streamer — including the partition four ways (usable + refused == walked; the 9 reasons sum to
88,824; the outcomes sum to the walk; 204 × 2,428 == walked), 0 duplicate keys, and **all eleven
rare-shape counters recounted independently**, the three zeros included.

**The pilot window: 290 rows on each side, key sets identical, 290 identical FIELD FOR FIELD, 0
differing.** Pilot ledger sha256 `c3363f6f17757ebc…c1e318` — the digest three reviews published.
Its totals recomputed here: 146 executed, 53,750 shares, gross Rs 12,665.05, costs Rs 14,600.00,
net −Rs 1,934.95.

**The crashed run: 103 shards, 250,084 rows compared, 145 differ (0.0580%), 0 unexplained.**
Re-derived with this session's own classifier:

| Cause | Mine | Report |
|---|---:|---:|
| A. Q-21(b) minutes-ungated | 105 | 105 |
| B. Q-21(a) gate-2 open test | 18 | 18 |
| C. Q-22(a) out-of-session stamp dropped | 9 | 9 |
| D. downstream carried bias | 13 | 13 |
| **total** | **145** | 145 |

**The four-class split re-derived by hand on a SAMPLE OF 20** (every 7th differing row, so not
one symbol's head): each row's two versions printed side by side and the class read off the
fields themselves — 15 A, 4 C, 1 B, and every one agrees with the classifier. The A rows all show
the same shape (`rule-3-outside-bar` + a gate refusal *before* → `minutes-ungated` + the Q-21(b)
flag *after*); the C rows show the flag appearing where it was absent; the single B row shows
`evaluated` → `gate 2 (candle integrity)`.

**The 59 byte-identical shards, as arithmetic.** Shards with at least one differing row: **44**.
Shards touched by cause A: **27** — exactly FIX-2's prediction that Q-21(b) alone would cost 27
of the 103 their identity, leaving **76**. Shards touched but NOT by A: 44 − 27 = **17**. And
76 − 17 = **59**, which is both the number of shards with no differing row and — checked
independently, by hashing the files — the number that are **byte-for-byte identical**.

---

## DIRECTED CHECK 4 — the witnesses

### Two gap-entry days, hand-walked end to end (`review9b_gap_walks`)

Both are the days section 12a NAMES as the earliest and the latest gap entry of the span, so the
walk tests that claim too. Both are BEARISH — the SHORT mirror of the gap rule.

**MUTHOOTFIN 2016-10-06** — tick 10 paise from the PINNED master; 355 in-session 1-minute bars.

* **Bias**: D-2 2016-10-04 O 352.00 H 354.00 L 345.10 C 349.55; D-1 2016-10-05 O 350.00 H 352.75
  L 344.20 C 345.70. Body 349.55–352.00. Not an inside bar. C.close 345.70 < bodyMin 349.55 →
  **Rule 1 BEARISH**. Ledger: `rule-1-breakout`, bearish. ✔
* **POC**: window 118 bars, 85,792 shares; top 348.00, bottom 341.25; totalTicks =
  round_half_even(675/10) = **68**; tpr **3**; rows ceil(68/3) = **23**; winning row
  [343.35, 343.65] with 16,971.64 of the volume → POC **Rs 343.50**. **Volume conservation exact
  to 0.0000000000.** Ledger `poc_half_paise` 68700 = Rs 343.50. ✔
* **Signal**: reference (11:00–11:15 close) Rs 343.60 > POC → **ARMED**. The 11:15–11:30 candle
  closes Rs 342.90 < POC → **trigger**, entry Rs 342.90 at 11:30. Its HIGH Rs 343.30 < POC
  343.50 → **GAP**, so SL = the previous 15-minute candle's close **Rs 343.60**. risk **Rs 0.70**;
  TP = 342.90 − 3×0.70 = **Rs 340.80**. ✔
* **Money**: qty = floor(1000/0.70) = **1,428**, with both bounds tight (1,428×70 = 99,960 ≤
  100,000 < 1,429×70 = 100,030). Exit **stop-loss-hit** on the 12:15 candle at the **LEVEL**
  Rs 343.60 (that candle's high was Rs 344.70 — the fill is the level, not the extreme). gross
  −Rs 999.60, net **−Rs 1,099.60**, notional Rs 489,661.20. ✔

**TIINDIA 2026-07-27** — tick 10 paise; 375 bars.

* **Bias**: Rule 1 BEARISH (C.close 2,767.00 < bodyMin 2,824.50). ✔
* **POC**: 120 bars, 132,143 shares; top 2,865.00, bottom 2,754.60; totalTicks **1,104**; tpr
  **46**; rows **24**; winning row [2,846.60, 2,851.20] → POC **Rs 2,848.90**; conservation
  exact. ✔
* **Signal**: reference Rs 2,843.40 < POC → **WAIT-ABOVE**. 11:30 closes 2,854.10 above → ARMED;
  three more ARMED candles; 12:30 closes 2,842.10 below → entry. Its HIGH **Rs 2,848.80 < POC
  Rs 2,848.90 — the gap predicate turns on TEN PAISE** → SL = prior close **Rs 2,850.80**, risk
  **Rs 8.70**, TP **Rs 2,816.00**. ✔
* **Money**: qty **114** (99,180 ≤ 100,000 < 100,050); stop-loss-hit at the level Rs 2,850.80 on
  the 13:00 candle; gross −Rs 991.80, net **−Rs 1,091.80**, notional Rs 323,999.40. ✔

**16 of 16 fields reproduce on each day. No divergence.** And section 12a's claim holds: 2,068
executed gap entries, earliest MUTHOOTFIN 2016-10-06, latest TIINDIA 2026-07-27, by DATE.

### The two qty-zero days' per-share risks

| Symbol | Day | per-share risk | floor(Rs 1,000 / risk) |
|---|---|---:|---:|
| BOSCHLTD | 2021-05-20 | Rs 1,019.70 | **0** |
| SHREECEM | 2020-03-19 | Rs 1,173.30 | **0** |

Both floor to zero; both rows carry qty 0 and cost 0; **neither invents a fill price**
(`exit_paise` null); both are **signalled, consumed and NOT executed** — CONTEXT 3.5's
"consumed + logged", exactly.

### The five Q-17 dates, against the ledger's own flags

| Date | Flagged rows (mine) | Report |
|---|---:|---:|
| 2017-04-28 | 123 | 123 |
| 2018-11-05 | 0 | 0 |
| 2019-10-25 | 55 | 55 |
| 2020-12-08 | 1 | 1 |
| 2021-02-24 | 148 | 148 |

Total flagged rows **889** across 445 dates; the five market-wide dates account for 327 of them.
The by-rule split reproduces exactly (rule-1-breakout 553, inside-bar-carry 181, rule-2-sweep 133,
rule-3-outside-bar 20, rule-3-no-break-carry 2).

### The five Rule-3 no-break carries

ASIANPAINT / BHARATFORG / ICICIPRULI on 2017-07-11 (unflagged) and GODREJCP / LAURUSLABS on
2021-02-25 (**flagged — the two Q-22(a) days**), all five carrying **bearish**. Count 5, flagged
2 — exactly as section 12e says, and exactly what FIX-4's measurement predicted at full scale.

### Also verified

2,068 gap entries worth −Rs 149,895.83 net on 621 winners (30.03%), exits 1,332 / 397 / 339;
22 demerger refusals across 10 symbols against 30 rows carrying the `suppressed` mark, difference
**8** — section 12d's "counted once, under the reason that reached them first"; the two
side-never-set days (ADANIGREEN 2018-10-16 and 2019-12-26); max concurrent positions **90** at
2026-05-07 12:45; peak simultaneous notional **Rs 42,148,077.61** at 2023-10-31 13:00 across 39
positions = **421.4808×** capital; largest single-trade notional Rs 27,408,000.00; 151 trades in
the biggest day; 13 zero-trade days; the distribution totalling 2,428.

---

## DIRECTED CHECK 5 — the three defects reading the report found

| # | The defect | The fix | Its pinning test | Verdict |
|---|---|---|---|---|
| 1 | `pf.side_split` derives its index from the rows given → the E13 columns annualized over the 2,415 days that TRADED, dropping 13 flat days | `_side_split_over_walked_days`, the run's true index passed explicitly | `test_the_E13_columns_are_indexed_on_EVERY_WALKED_DAY_not_only_trading_days` | **fix correct, test DISCRIMINATING** |
| 2 | Sharpe printed **+0.5833** for a strategy that lost 168× its capital; excursion percentages divided by a negative base | `RATIO_CROSSES_ZERO` on Sharpe/Sortino where the column crosses zero; `_excursion_pct` refuses a non-positive base | `test_a_percentage_is_REFUSED_when_its_base_equity_is_not_positive` | **fix correct; test covers only HALF the fix** (finding C1) |
| 3 | Run-ups printed peak → trough; section 12f asserted three zero counters while printing 30 for one | `rising=True` on both run-up rows; the zero list computed from `run.rare_shapes` | `test_a_run_up_is_printed_TROUGH_first_because_that_is_the_order_it_happened` | **fixes correct; the 12f half is pinned by NOTHING** (finding C2) |

**Defect 1's test is the strongest form available**: it does not merely assert the right answer,
it *demonstrates the defect* — it calls the shipped `pf.side_split` on the same rows and asserts
it loses the flat day (`naive["All"].trading_days == 3 < 4`) while the money is unchanged. The
report's own figure confirms the fix at scale: **Trading days in the series = 2,428** on all three
columns, which is the walked index, not the 2,415 that traded.

**Defect 2's fix is right and load-bearing**, and this session reproduced the disease
independently (§ check 2 above). But the test exercises `_excursion_pct` only. See the mutation
matrix below: the Sharpe and Sortino branches survive.

**Defect 3's run-up half is pinned in both directions** (a run-up prints trough-first, a drawdown
prints peak-first, in one test). The 12f half — and the section-12c "N of the five appear at
ZERO" sentence, and the gap earliest/latest-by-DATE fix that rode in the same commit — are not
pinned by anything.

### Mutation matrix over `src/acumen/report_9b.py`

Ten mutants, each REINTRODUCING one of the corrections. A mutant is CAUGHT only if a test goes
red; a mutant that survives the fast subset was re-run against the **whole 2,140-test suite**
before being called SURVIVED. The file was restored and its sha256 re-verified after every one.

| # | Mutant — what it reintroduces | Shipped suite (2,140) | Caught by |
|---|---|---|---|
| M1 | defect 1's **CALL SITE**: `build_everything` calls `pf.side_split(run.executed, …)` again | **SURVIVED** (2140 passed) | kept probe |
| M2 | defect 2a: print **Sharpe** unconditionally | **SURVIVED** (2140 passed) | kept probe |
| M3 | defect 2a′: print **Sortino** unconditionally | **SURVIVED** (2140 passed) | kept probe |
| M4 | defect 2b: print a percentage of a non-positive base | CAUGHT | shipped test |
| M5 | defect 3a: run-up printed peak-first (close-to-close) | CAUGHT | shipped test |
| M6 | defect 3a′: run-up printed peak-first (**15-minute path**) | **SURVIVED** (2149 passed) | kept probe |
| M7 | defect 3b: assert THREE zero counters instead of computing them | survived the shipped suite | kept probe |
| M8 | section 12c's "N of the five appear at ZERO" asserted, not computed | survived the shipped suite | kept probe |
| M9 | gap earliest/latest by ledger order instead of by DATE | survived the shipped suite | kept probe |
| M10 | `_rare_shape_recount` echoes the manifest instead of recounting (B277) | CAUGHT | shipped test |

**3 of 10 caught by the shipped suite.** Every survivor was re-run against the **whole** suite,
not a subset. M7/M8/M9 show "1 failed, 2148 passed" because this review's probe file was already
in the tree by the time they ran — they are caught by the probes, not by the build's tests.
`src/acumen/report_9b.py` was restored and its sha256 re-verified after every mutant
(`bc98245fa7e66d36…f62cb`, equal before and after), and after the whole matrix `git status` on
`src/` is clean.

**The most surprising survivor is M1**, and it is worth stating plainly. The shipped test
`test_the_E13_columns_are_indexed_on_EVERY_WALKED_DAY_not_only_trading_days` is excellent — it
demonstrates the defect rather than describing it — but it calls `_side_split_over_walked_days`
**directly**. Nothing asserts that `build_everything` calls it. So the helper can stay perfect
and stop being used, the report goes back to annualizing over 2,415 days instead of 2,428, and
all 2,140 tests stay green. Defect 1 is pinned at the helper, not at the fix.

Each of the four survivors and each of the three prose-fix mutants is now RED against a kept
probe, verified one by one (9 mutants → 9 red, engine restored byte-identically each time).

---

## DIRECTED CHECK 6 — the disclosures

| Item | Claimed | Found |
|---|---|---|
| Q43 "capital-infeasibility flags NOT computed…" | verbatim, ×3 | **3 verbatim occurrences** (§1, §2's disclosure list, §11's blockquote); no flag value anywhere |
| Q44 stamp "PENDING TRADER CONFIRMATION OF Q44 (gap-rule example, POC 2032)" | verbatim | **2 verbatim occurrences** (§1, §2) |
| all five manifest disclosures | verbatim | **5 of 5 present verbatim**, including the Q-21(b) blast-radius paragraph and the span-clamp paragraph, character for character |
| B149 caveat | verbatim from the register's own current figures | **present verbatim**; and all **204** per-symbol `price-proven` percentages recomputed from `<data_root>/universe_backfill/ledger.json` — **0 disagreements** in 204 rows, status included |
| Q-21(b) concentration | 210 days / 59 symbols / six carrying 47.14% | **210 / 59 / 47.14%**, and the six named symbols' counts (33/16/15/14/11/10) all reproduce from the ledger's own flags |
| coverage 409,205 = 93.9317% | CONTEXT 4.6 v1.6 | **reproduces EXACTLY** from the register's own `usable_pass` summed over the 204 settled symbols (409,205) over the whole lake's 435,641 stored days |
| definitions block | above the tables, per the E13 presentation ruling | **present, §4, above every table**; ten definitions incl. basis, population, curve, both drawdown forms, outliers, Sharpe/Sortino, CAGR, MFE/MAE, notional, rupees |

**R10's pricing traced back to the crashed shards**, by re-deriving it from the shards themselves:

| Class | Differing rows in the 103 shards | Traded before, not after | Their net | Traded on BOTH, differently |
|---|---:|---:|---:|---:|
| Q-21(b) minutes-ungated | 105 | **13** | **−Rs 7,358.35** | 0 |
| Q-21(a) gate 2 | 18 | **7** | **−Rs 3,698.60** | 0 |
| Q-22(a) out-of-session | 9 | 0 | — | 3 |
| downstream carried bias | 13 | 0 | — | **2** |

Both published figures land exactly, and section 11b's closing claim — *"13 rows differ for no
reason other than a carried bias … and 2 of those traded on BOTH runs and traded DIFFERENTLY"* —
lands exactly too. The seven classes with no counterfactual print `none`; none is extrapolated.

---

## DIRECTED CHECK 7 — byte-reproducibility

The committed report was regenerated **to a scratch path**, from HEAD, over the same run
directory and the same read-only stores:

```
python -c "from acumen.report_9b import main; main(['--out', '<scratch>/regen_1.md'])"

diff <scratch>/regen_1.md docs/reports/chunk9b_backtest_report.md
    -> EMPTY

sha256  98c45129a8215d2a4e78a389dfa54db4ceccfabb458e5c3ee21a7fcd116b7487  <scratch>/regen_1.md
sha256  98c45129a8215d2a4e78a389dfa54db4ceccfabb458e5c3ee21a7fcd116b7487  docs/reports/chunk9b_backtest_report.md
        77,799 bytes on both
```

**BYTE-IDENTICAL. Diff empty.** REVIEW_8 finding C2's rule is satisfied by an independent
regeneration, and the digest matches the one PROGRESS.md and STATUS.md publish
(`98c45129a8215d2a…`). The run's own artefacts were re-read, never written: after the
regeneration the ledger, manifest, `progress.json` and all 204 shards still carry their
pre-session mtimes (20:25 on 2026-08-05), and a `find -newermt` sweep of the whole `data_root`
returns **nothing**.

One operational note, not a finding: on this box the regeneration took **about four hours**
against the session's stated ~90 minutes, because it ran alongside this review's own store-heavy
probes. The stage that costs the time is the 15-minute path assembly, which opens a month file
per trade-day for all 188,345 trades. The session's own docstring already discloses that a
bulk month-at-a-time reader was built, measured at 2.4× SLOWER, and rejected — this session
independently read every month ONCE (the bulk shape) and assembled the identical 1,101,029 marks
in about twenty minutes, which suggests the measurement was made on a warm OS cache. Nothing
depends on it; the number in the handover is a floor, not a duration.

---

## DIRECTED CHECK 8 — B271 … B281

| # | Decision | Judgment |
|---|---|---|
| **B271** | stream the 306,967 non-executed rows past, keep the executed rows plus the walked-day index | **APPROVED.** Verified by construction: every E13 figure is a function of the executed rows and that index, and this session's own streamer — which keeps nothing either — reproduces all 32 manifest checks and every headline figure. |
| **B272** | one `pf.metrics` per calendar year, seeded at that year's OWN opening equity | **APPROVED.** Re-implemented independently: the eleven rows reproduce and the eleven changes sum to the run's net exactly. The seeding is what makes 2016's 208.28% meaningful and every later year's percentage correctly refused. |
| **B273** | the daily trade-count distribution indexed on WALKED days, not on `pf.disclosures`' trade-days view | **APPROVED.** The distribution totals 2,428 = the walked index, and the 13 zero-trade days are IN it. CONTEXT 3.5 asks for the distribution of daily counts; a sat-out day is one of them. The reviewed pure module was not bent for a report's convenience. |
| **B274** | the per-symbol table carries no 15-minute path and says so | **APPROVED.** E13 asks for the intra-trade form at portfolio level; 204 per-symbol paths would multiply an already 40,981-observation assembly by 204 for a figure the spec never asks for. The refusal is printed, not silent. |
| **B275** | both benchmark readings computed, NEITHER published | **APPROVED as of its date — now SUPERSEDED by the architect's Q-23 ruling (06-Aug-2026).** The decision was right under the STOP rule and the measurement it produced is what let the architect rule with numbers in hand. It must be re-pointed with the publication edit. |
| **B276** | price refusals ONLY where a counterfactual exists; the rest print "none" | **APPROVED**, with finding Q6: the priced rows print the class's FULL day count beside a trade count measured over only the days the crashed run walked. |
| **B277** | `_rare_shape_recount` RAISES on a label it has no independent recount for | **APPROVED and mutation-verified** — a reconciliation that defaults to the thing it is checking is not one, and the mutant that makes it echo the manifest is CAUGHT. |
| **B278** | `REGATE_LAUNCHER` as a constant so banner, runbook and test cannot drift | **APPROVED**, but recorded under finding C3: the commit that carries it (`5afab98`) is OUTSIDE the directed span and is reviewed by nobody. |
| **B279** | `_side_split_over_walked_days` instead of `pf.side_split` | **APPROVED.** The strongest of the eleven: the defect is real, the fix is minimal (same function, one more argument), and the test demonstrates the defect rather than describing it. |
| **B280** | refuse a percentage on a non-positive base, and Sharpe/Sortino on a column that crosses zero | **APPROVED — the single most important judgment on this page.** Independently reproduced: 2,389 of 2,428 daily returns divide by a negative denominator and a naive Sharpe prints **+0.5882**. Finding C1 attaches to its TEST coverage, not to the decision. |
| **B281** | the two duplicate B-ID ranges disambiguated rather than renumbered | **APPROVED-WITH-NOTE.** The convention is right (plan.md is architect-only, PROGRESS.md is append-only) and is recorded. This session's own scan could NOT mechanically confirm the "only two genuine collisions" claim: `PROGRESS.md`'s 49 entries do not format `decisions:` uniformly and only 11 of them expose B-IDs to a line scan. What IS verified: **B271–B281 each appear exactly once in the whole file**, so this span introduces no new collision, and every repeat the scan did find is a review or fix entry JUDGING an earlier decision — the exact pattern B281 describes. |

---

## DIRECTED CHECK 9 — standard sweep

| Item | Result |
|---|---|
| Suite from clean | **2140 passed / 0 failed / 0 skipped** in 380s — the claim reproduced exactly. **2151 passed / 0 / 0** with this review's 11 kept probes. |
| Fixtures | `git diff 41f3e3e..796c39d -- tests/fixtures/ poc/data/` is **EMPTY**. Frozen. F9 untouched. |
| Tests weakened / deleted / skipped | **NONE.** Test-function names diffed base→HEAD: **0 removed, 25 added**, all in the new `tests/test_report_9b.py`; no other test file changed in the span at all. 0 skips, 0 xfails. |
| Engine modules | 13 of 13 blob-identical to the run's own code SHA `c34c088` (see §0(b)). |
| Purity | `report_9b.py` performs I/O by design and is not an engine module. It contains **no clock read** (`datetime.now`/`date.today`/`time.time`/`perf_counter`: none) — which is what makes byte-reproducibility possible at all. |
| Money constants | the config tripwire walks **every** module in `src/acumen` and is green; §2's money rows are computed from the run's own spec block. Finding C4 records the prose sites it structurally cannot see. |
| Commit hygiene | messages are what+why with `chunk9B:` prefixes; **all four src/tests-touching commits since the tag carry `(unreviewed)`**; the four that do not touch src/ or tests/ are correctly exempt. |
| AI attribution | **none** — commit messages and every changed file scanned. |
| Secrets | `.env` present, gitignored, never in a diff; no credential name in any changed file or in this review's evidence packs. |
| SHA chain | `HEAD == origin/main` at session entry (`796c39d`). Single branch `main`. No force-push. |
| Store writes | **NONE.** Everything this session ran is read-only over `<data_root>`; the one regeneration went to the scratchpad. Verified: the run directory's `ledger.jsonl`, `manifest.json` and all 204 shards have their pre-session mtimes, and the ledger's sha256 is still `c70a72b097879914…a4d134`. |

---

## FINDINGS

### Quant

**Q1 · MEDIUM · section 6a's closing paragraph is refuted by its own Long column.**
The paragraph reads *"a fixed-R strategy bounds its own trades … so before costs every trade
lands in a narrow band and the fences sit outside it."* On the **Long** column they do not.
Long's Q3 is Rs 440.00 and its IQR Rs 1,539.60, so the upper fence is **Rs 2,749.40** — below the
Rs 2,900.00 maximum win — and **13,243 long trades are outliers, worth Rs 38,311,425.93 = 76.48%
of Long's gross profit.** The block prints that number correctly two paragraphs above; the prose
then generalises across all three columns and is false on one of them. Reproduced exactly by this
session's own type-7 quantiles in Fractions (All 0, Long 13,243, Short 0). *Related:* the
STATUS.md and PROGRESS.md headline *"TUKEY: 0 outliers of 188,345"* is true of the **All** column
only and carries no such qualifier in the chunk state ledger.
**Fix (owed, one sentence):** qualify the sentence to the column it holds for, and say why the
Long column is the one where the fence bites.

**Q2 · MEDIUM · 308 of the benchmark's "433 share-count factors" are special DIVIDENDS.**
Full treatment in PART 0 above. The ruled figure stands; the *"and stated"* half of the ruling
does not yet exist on the page. Measured cost of the ambiguity: **+25.23 pp of 491.90%**.

**Q3 · MEDIUM · section 5 names a PARTIAL year as the best year, without the caveat section 8
carries.** *"Best year | 2016: −Rs 225,598.97"*. 2016 carries **61** walked days (the minute era
opens 2016-10-03) against a full year's ~246. Among the **nine FULL years** the least negative is
**2018 at −Rs 1,178,849.98** — 5.2× larger. Section 8 says *"2016 is a partial year … neither is
annualized and neither should be read as one"*; section 5, which is the section a reader reads
first, does not. The "Worst year 2023" row is unaffected (2023 is a full year).

**Q4 · LOW · one word, two different quantities.** Section 1 says *"The data era is 93.9317%
price-proven"* and glosses it as days *whose 1-minute prices cannot be reconciled against the
exchange's own bhavcopy* — which is gate 1P. It is not: 93.9317% is the ALL-THREE-GATES figure,
with a settled-only numerator (409,205) over a whole-lake denominator (435,641), exactly as
CONTEXT 4.6 v1.6 defines it. Section 9 then defines `price-proven` as **gate 1P alone**, per
symbol. On gate 1P alone the settled universe is **97.8444%** proven. No number is wrong, the
direction is the conservative one, and the spec figure is quoted correctly in section 11b — but a
reader who averages section 9's column (mostly 99.8–99.96%) will never arrive at section 1's
headline.

**Q5 · LOW · "Largest win, % of its own notional" is arbitrary under ties.**
**5,383** executed trades tie at exactly Rs 2,900.00 (Long 2,205, Short 3,178) and **20,939** tie
at exactly −Rs 1,100.00 — a fixed-R strategy manufactures ties by construction. Which of them
supplies the notional is decided by the ledger's row order, not by anything on the page: the tied
winners' notionals run **Rs 35,700.00 to Rs 14,800,000.00**, so the printed percentage could have
been anything from **0.02% to 8.12%** instead of the 0.29% shown. The same applies to the largest
loss row. The rupee figures are exact; the two percentage rows are not well-defined.

**Q6 · LOW · the priced refusal rows put a full-population count beside a partial-population
measurement.** Section 11b's two priced rows print **210** days (minutes-ungated) and **47**
(gate 2) beside **13** and **7** trades. The trade counts are measured over only the days the
crashed run actually walked — **105** and **18** — because only 103 of 204 shards survive. The
evidence column says the shards *"walked these days"* without saying it walked half of them. A
reader computes 13/210; the measured base is 13/105.

**Q7 · LOW · two concurrency conventions, one printed, neither stated.** Section 11's
*"Max concurrent positions **90**"* comes from `pf.disclosures`, whose sweep processes an OPEN
before a CLOSE at the same stamp — a position closing at T is still counted as open at T. Both
reproduce here: on that convention **90 at 2026-05-07 12:45** exactly; on the 15-minute path's own
convention (a position is closed at its exit mark) the maximum is **77, at 2026-03-20 12:30**. The
choice is defensible and is documented in the code's docstring as the pessimistic reading — but
the definitions block, which defines ten other things, does not define this one, and the report
prints one number without saying which of the two it is.

**Q8 · INFO · the B149 caveat and the table two paragraphs below print the same quantity at two
precisions.** The caveat says TATASTEEL *"65.8% price-proven"*; the section-9 row says
**65.85%**, and round-half-up of the row's own figure is 65.9%, not 65.8%. The caveat's figures
are truncations (`price_proven_pct_x100` 6584 for 65.845…%) while the table rounds. Both are
correct renderings of 1,604/2,436; neither is wrong; they simply disagree at the first decimal on
one symbol. **Pre-existing** — the caveat is generated by the runner and quoted verbatim by rule,
so this is not this span's doing.

**Q9 · INFO · one cross-reference does not hold.** Section 1: *"Over 188,345 trades that is
Rs 18,834,500.00, and it is the difference between the two headline figures in section 5."*
Section 5 carries **one** PnL figure (−Rs 16,836,018.20); the before-costs figure it is the
difference from (Rs 1,998,481.80) is in section **6**, which section 5's own closing line
correctly says. The arithmetic is right; the pointer is not.

### Code

**C1 · MEDIUM · three of the five corrections in `4eba3bf` can be reverted with all 2,140 tests
green — including the one the commit message headlines.** The commit says *"each is now pinned
by one"*. Measured, that is true of two of them.

* **M1 — defect 1's call site.** `test_the_E13_columns_are_indexed_on_EVERY_WALKED_DAY…` calls
  `_side_split_over_walked_days` directly and proves the helper right. Nothing asserts that
  `build_everything` calls it. Putting `pf.side_split(run.executed, …)` back reintroduces the
  exact 2,415-vs-2,428 defect and the suite stays green: the helper remains correct and stops
  being used.
* **M2 / M3 — the Sharpe and Sortino refusal**, i.e. the limb that produced **+0.5833 for a
  strategy that lost 168× its capital**. The shipped test covers `_excursion_pct` only; the
  `crosses_zero → RATIO_CROSSES_ZERO` branches are untested on both rows.
* **M6 — the 15-minute path's run-up order.** `_path_excursion` has its own `rising` branch and
  its own mutant; the one shipped run-up test drives `_excursion` only.

**CLOSED by four kept probes**, each verified RED on its own mutant and green at HEAD.

**C2 · MEDIUM · the corrections the commit describes as "computed from the data rather than
asserted" are pinned by nothing.** Mutants **M7** (hardcode three zero counters — the literal
defect the message describes), **M8** (section 12c's "N of the five appear at ZERO" asserted
again) and **M9** (gap earliest/latest by ledger order instead of by DATE) all survive the
build's own suite; in this matrix they show as caught only because this review's probes were
already in the tree. **CLOSED by three kept probes**, mutation-verified.

**C3 · LOW · four commits since the last reviewed tag sit outside the directed span and are
reviewed by nobody.** `chunk9b-relaunch-pass` = `c34c088`; the brief's span starts at `41f3e3e`,
leaving `5afab98`, `d224563`, `de584ac` and `41f3e3e` unreviewed. Audited here as a supplement and
**nothing in them is wrong**: `5afab98` adds `REGATE_LAUNCHER` (B278) with its test and corrects
the runbook; `d224563` closes REVIEW_9B_FIX4 F3/F5 with a one-line `trade_evidence` docstring fix
and two errata; `de584ac` regenerates the chunk-9A pilot pack in place under the named write
sanction — **verified: the pack's diff is the spec-version label, three new zero-valued
rare-shape rows and two manifest digests, and the ledger sha256 is unchanged at `c3363f6f…`, so
no number moved**; `41f3e3e` appends the run receipt to QUESTIONS.md. Recorded so the next
session's span starts at the tag, not at the middle.

**C4 · LOW · eight prose sites type the CONTEXT 3.5 money magnitudes as text.**
`report_9b.py` computes section 2's Risk/Cost/Capital rows from the run's own spec block — and
then writes *"Rs 100.00"*, *"Rs 1,000.00"* and *"Rs 1,00,000"* as string literals at lines 1157,
1164, 1363, 1426, 1737, 1745, 1862 and 1869, including inside the qty-zero table's own "why"
column. If `config.yaml`'s risk or cost moved, the table would move and the prose would not, and
the AST tripwire would stay green — which is exactly the evasion the tripwire's own docstring
warns about. **CLOSED by a kept probe** that ties those literals to the configured amounts, so a
config change turns the suite red instead of turning the report into a quiet lie.

**C6 · LOW · three more section-12 sentences still ASSERT a count the ledger could supply — the
same defect class the commit says it fixed, in the same section.** Defect 3's stated remedy is
*"both now computed from the data rather than asserted"*, and 12f's zero list and 12c's tail
sentence genuinely are. Three sentences beside them were not converted and still hardcode this
run's answers:

* §12b — *"In ten years and **188,347** signalled days it happened **twice**"*, above a table
  that IS driven by `w.qty_zero`;
* §12e — *"**Two** days in the whole span are that case, and the run carries **three** more"*,
  above a table that IS driven by `w.no_break_carry`;
* §12e's closing paragraph, which names GODREJCP and LAURUSLABS as literals.

On THIS run all three are correct — verified: signalled 188,347, qty-zero 2, carries 5 of which
2 flagged. No number on the page is wrong. But a re-run with one more qty-zero day would print a
false sentence directly above a true table, which is exactly the failure section 12f was fixed
for. **CLOSED by a kept probe** that pins the literals, so converting them is a deliberate act
and a re-run that moves the counts cannot ship silently.

**C5 · INFO · commit `4eba3bf` says "three defects" and ships five corrections.**
Besides the three it names, it widens `largest_win/loss_pct_of_gross_*` from 2 to 5 decimal
places (the figures printed 0.00% before) and changes the gap first/last witnesses from ledger
order to DATE order. Both are improvements and both are visible in the diff; neither is in the
message. History should say what it did.

---

## KEPT PROBES

`tests/test_review9b_report_probes.py` — **11 tests**. Suite **2140 → 2151 passed / 0 failed /
0 skipped**. No existing test, no `src/` file, no fixture and no evidence artefact was modified.

| Probe | Closes | Mutant it is RED against |
|---|---|---|
| `test_sharpe_and_sortino_are_REFUSED_on_a_column_whose_equity_crosses_zero` | C1 | M2, M3 |
| `test_sharpe_and_sortino_still_PRINT_when_the_equity_never_crosses_zero` | C1 (the control — a refusal that fired unconditionally would be its own defect) | — |
| `test_build_everything_uses_the_walked_day_split_and_NOT_the_convenience_wrapper` | C1 | M1 |
| `test_a_run_up_on_the_15_MINUTE_PATH_is_printed_TROUGH_first_too` | C1 | M6 |
| `test_section_12f_COMPUTES_which_counters_are_zero_rather_than_asserting_a_number` | C2 | M7 |
| `test_section_12c_COMPUTES_how_many_of_the_five_Q17_dates_this_run_flagged` | C2 | M8 |
| `test_section_12a_names_the_gap_witnesses_by_DATE_not_by_the_ledger_s_row_order` | C2 | M9 |
| `test_the_money_magnitudes_typed_into_the_report_s_PROSE_match_the_configured_amounts` | C4 | M12 (a stray magnitude in the prose) |
| `test_three_section_12_sentences_still_ASSERT_counts_the_ledger_could_supply` | C6 | M11 (converting one of them silently) |
| `test_the_benchmark_s_share_count_factor_TALLY_also_counts_special_dividends` | Q2 | — (documents the mixing as arithmetic: 1/2 × 24/25, so the dividend factor is inside the published multiple) |
| `test_the_tukey_fences_do_NOT_always_sit_outside_a_fixed_R_band` | Q1 | — (reproduces the Long column's failure on the smallest population that shows it) |

**Nine mutants, nine red.** Each was applied to `src/acumen/report_9b.py`, the probe file run,
the file restored and its sha256 re-verified — `bc98245fa7e66d36…f62cb`, equal every time, and
`git status` on `src/` clean afterwards. The two probes with no mutant are documentation probes:
they turn findings Q1 and Q2 into arithmetic a future session inherits rather than prose it can
skim.

---

## WHAT IS OWED

1. **Publish the Q-23 ruling in the generator** (PART 0). Retitle section 10, label the adjusted
   row THE benchmark, replace `BENCHMARK_STOP` with the ruling, re-point **B275**, fix section
   13's *"Q-23 open"* line. No number moves.
2. **State what is inside the benchmark** (Q2): 125 share-count events and 308 special dividends,
   and the +25.23 pp the latter carry. If the architect meant share-count events only, the figure
   is 466.67% and one line changes — an architect call, recorded under Q-23, not taken here.
3. Six presentational corrections: Q1 (the 6a sentence), Q3 (the partial-year caveat in section
   5), Q4 (the word `price-proven`), Q5 (say the largest-win percentage is one of many ties),
   Q6 (the priced rows' measured base), Q7 (define the concurrency convention).
4. **Q43 and Q44 remain OPEN with the trader**, and both stamps ride on every output verbatim.
5. The next review's span should start at the **tag**, not inside the arc (C3).

---

*Reviewer's note: this review changed no source file, no test, no fixture and no store. It added
five evidence packs, one probe file, this document, the Q-23 ruling record in QUESTIONS.md, and
the STATUS/PROGRESS lines every session owes.*
