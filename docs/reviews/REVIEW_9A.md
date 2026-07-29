# REVIEW_9A — chunk 9A · the backtest runner, run ledger and portfolio layer

**Type:** QC — BOTH personas (`personas/quant_reviewer.md` + `personas/code_reviewer.md`), fresh session.
**Span:** `dfa3ff8..998ac1d` — the plan amendment (b3fb34c), the build (6285c21), the evidence pack (60d2482), the ledger commit (998ac1d).
**Suite:** **1689 passed / 0 failed** from a genuinely clean state (`.pytest_cache` + every `__pycache__` deleted first) — 1675 build + 14 kept reviewer probes. The build's own 1675/0 was reproduced first.

## VERDICT: **PASS**

with 14 findings (2 MEDIUM + 4 LOW + 4 INFO quant; 1 MEDIUM + 2 LOW + 3 INFO code, one numbering shared) and **six conditions carried to chunk 9B**, listed in section 12. No CONTEXT.md deviation was found. Every strategy rule in the span was reimplemented by the reviewer from the spec text and reproduced to the digit.

---

## 0. A MATERIAL DISCREPANCY BETWEEN THE BRIEF AND THE REPO — read this first

The architect's directed check 6 reads:

> "Q-16 EXECUTION: Tukey fences recomputed by hand on the pilot ledger; the 15-min path fixture recomputed by hand INCLUDING the overlap construction; PROVISIONAL absent everywhere; the retired construction gone from output."

**None of that exists in this span.** The review was executed against the repository as it actually stands, and the finding is reported rather than worked around:

| The brief presumes | The repo actually contains | How verified |
|---|---|---|
| Tukey / IQR fences computing `outliers` | **No fence, IQR, quartile or percentile code anywhere in `src/` or `tests/`** | grep over the whole tree; the only hits are unrelated ("finding Q1", "overlap-aware intersections" from REVIEW_5B) |
| A 15-min intraday equity PATH with an overlap construction | **Absent.** The only construction is the coinciding-excursion worst case | `src/acumen/portfolio.py:57-67`, `equity_curve` L183-184 |
| `PROVISIONAL` absent everywhere | **PROVISIONAL is PRESENT — 12 occurrences**, 2 of them in the committed pack | grep |
| The retired construction gone from output | It is not retired; it is the **only** construction | pack lines 309-310 |

`git log`, `git reflog`, `git branch -a` and `git stash list` all confirm the span is four commits and that **no Q-16 fix session ever ran**. Q-16 is still `class A · OPEN · STOP` in QUESTIONS.md, exactly as the build session raised it.

**This is not a defect of the build.** The builder hit an undefined convention in CONTEXT 7-E13 and invoked CLAUDE.md rule 1 rather than inventing one — which is the constitutionally correct behaviour. What section 6 below verifies is therefore *that the STOP was honoured correctly*, not that a ruling was executed. **If the architect has issued a Q-16 ruling, it has not reached this repository and a fix session is still owed.**

---

## 1. Reconciliation — the pilot re-run through the runner (directed check 1)

The reviewer re-ran the pilot generator to a scratch path and recounted every figure **from the ledger JSONL directly**, comparing against the **committed chunk-8 pack**, not against the chunk-9A pack's own claims.

**17 of 17 figures identical.** 290 walked · 146 entered / 88 armed-no-close / 56 never-armed · 146 executed · 53,750 shares · gross Rs 12,665.05 · costs Rs 14,600.00 · net −Rs 1,934.95 · 45 / 101 / 0 winners/losers/flat · gross profit Rs 101,099.20 · gross loss −Rs 88,434.15 · 86 stop / 36 square-off / 24 target.

**The real-vs-empty factor-table equality, verified by the reviewer against the CA cache itself** (not against the pack): parsing `data/nse/ca/nse_ca_2026-*.json` directly and computing each dividend against its own cum-date close from the raw bhavcopy gives **exactly five in-window events for the five pilot symbols, all ordinary dividends, none reaching CONTEXT 4.2's 2% threshold** — TCS 1.3378% and 0.5453%, RELIANCE 0.4602%, HDFCBANK 1.6270%, BHARTIARTL 1.2429% — and **zero share-count events**. Every k = 1, so the real table and an empty one are identical on this window. The pack's five percentages match the reviewer's to 4 dp.

**Pack regeneration:** regenerated to a scratch path and diffed — **byte-identical** to the committed file (`sha256 3e56f26c…` both). REVIEW_8 finding C2's rule is obeyed from the start.

**The pack's own section-8 invariants, re-derived independently from the ledger:** all 12 checked PASS, including `net == gross − cost` on all 146, both sizing bounds tight on all 146, `MFE ≥ 0 ≥ MAE`, realized gross inside `[MAE, MFE]` with **0 violations**, `notional == qty × entry`, target exactly 3R on every signalled day, every evaluated day passing the full CONTEXT 4.6 battery, and **no float in any ledger row**.

## 2. The cross-CA walks, recomputed digit by digit (directed check 2)

Recomputed from `data/daily_store/daily/**/bhavcopy_*.parquet` with the reviewer's own CONTEXT 3.2 arithmetic, importing nothing from `src/acumen`.

**2a. RELIANCE 1:1 bonus, ex 2024-10-28** — k = B/(A+B) = **1/2** (Indian convention; the US convention would give 1/2 here by coincidence of a 1:1, so the discriminating cases are in section 3). Pair for D = 2024-10-29 is P = 2024-10-25, C = 2024-10-28.

| price | raw paise | × 1/2 | half-even | pack |
|---|---|---|---|---|
| open | 268,700 | 134350 | 134,350 | 1,343.50 ✓ |
| high | 268,870 | 134435 | 134,435 | 1,344.35 ✓ |
| low | 264,400 | 132200 | 132,200 | 1,322.00 ✓ |
| close | 265,570 | 132785 | 132,785 | 1,327.85 ✓ |

Adjusted → **Rule 2 bearish**; unadjusted → Rule 1 bearish. **The ten-paise test is confirmed exactly**: Rule 2's `C.low >= P.low` holds at 132,210 vs 132,200 — a margin of **10 paise**. Reviewer sensitivity sweep: at −10 paise it still passes; at **−11 paise the day becomes an outside bar and falls through to Rule 3**. The pack's claim is precise.

**2b. HDFCBANK face-value split, ex 2019-09-19** — k = B/A = 1/2. The two half-paise roundings are the interesting part and both reproduce: high 222,415 × ½ = 111,207.5 → half-even **111,208**; close 218,775 × ½ = 109,387.5 → half-even **109,388**. Adjusted → **Rule 2 BULLISH**; unadjusted → Rule 1 BEARISH. **The adjustment reverses the bias** — confirmed. An empty table would have traded the short side all day.

**2c. Demerger suppression, RELIANCE ex 2023-07-20** — the ledger shows 2023-07-21 and 2023-07-24 `refused / suppressed`, then a clean resume at 2023-07-25 whose pair (2023-07-21, 2023-07-24) sits strictly after E. That is CONTEXT 3.2's "D−1 == E or D−2 == E" blocked, resuming at E+3, exactly.

**2d. Muhurat E2 removal, 2024-11-01** — verified at source: the daily store **does** carry a bhavcopy row for 2024-11-01 (so a calendar built from it would call the date a trading day), and RELIANCE's stored minutes for that date are **60 candles stamped 18:00–18:59**, wholly outside 09:15–15:30. CONTEXT 7-E2's own detection clause applies literally. **2024-11-04's pair does reach back past it**: with the removal the pair is (2024-10-30, 2024-10-31); without it, (2024-10-31, 2024-11-01). Confirmed — see finding **Q8** for the honest limit of this witness.

### The 47, audited

The reviewer **re-ran the whole scan independently**, reimplementing the CONTEXT 3.2 walk, the pairwise adjustment, the Rule-3 first-break minute scan, the v1.4 tie rule and the 40-day carry seeding from the spec text (only the chunk-3 factor table, the chunk-1 calendar and the stores were imported — those are the scan's *inputs*).

| Measure | Pack | **Reviewer** |
|---|---|---|
| Settled symbols scanned | 204 | **204** |
| Share-count events in the era | 112 | **112** |
| Bias pairs walked | 107 | **107** |
| **Pairs whose BIAS changes** | **47** | **47** |

The pack's "first 15 changed" table matches the reviewer's row for row on all seven columns.

**Four changed pairs hand-walked** (chosen for k-diversity, including a non-terminating fraction):

| symbol | ex-date | k | basis | adjusted | unadjusted |
|---|---|---|---|---|---|
| GRASIM | 2016-10-04 → 10-06 | 1/5 | FV split 10→2 | Rule 1 **bullish** (close 100,920 > bodyMax 98,346) | Rule 1 bearish |
| BEL | 2017-03-15 → 03-16 | 1/10 | FV split 10→1 | Rule 1 **bullish** | Rule 1 bearish |
| CONCOR | 2017-04-03 → 04-05 | **4/5** | bonus 1:4 → B/(A+B) | Rule 2 **bullish** | Rule 1 bearish |
| ICICIBANK | 2017-06-19 → 06-20 | **10/11** | bonus 1:10 → B/(A+B) | Rule 1 **bullish** (close 29,245 > bodyMax 29,145) | Rule 1 bearish |

CONCOR and ICICIBANK are the ones that matter for the persona's checklist item 5: **the Indian bonus convention is correct** — 1:4 gives 4/5 and 1:10 gives 10/11, not the US 1/5 and 1/11. ICICIBANK also exercises the non-terminating case (318,000/11 = 28,909.09… → half-even 28,909) and its adjusted verdict is decided by 100 paise, so the rounding is load-bearing and correct.

**B191 confirmed:** both readings go through `BiasEngine.bias_for_day(..., seed_from = trade_day − 40 days)` (`pilot_evidence.py:319,340`). The reviewer's independent scan used the same 40-day carry seeding and landed on 47; comparing isolated pairs instead does inflate the count, as B191 records.

## 3. The CA pull (directed check 3)

- **Row count verified: 41,351.** The cache holds 23 files; **22 of them are the year-per-request history 2005–2026 and total exactly 41,351 rows**. The 23rd is a stray `nse_ca_2024-10-01_2024-10-31.json` month probe (76 rows) that the year loop (`fetch_corp_action_history`, `range(start.year, end.year+1)`) never reads. That accounts for the 41,427 a naive `ls`-and-sum gives — see finding **C6**.
- **Day-cached:** every file carries `fetched_on: 2026-07-29`, a single day. One year per request, the public `corporates-corporateActions` endpoint, no credential in any file.
- **Plausible against the chunk-3 era:** 829 rows in 2005 rising monotonically to ~2,700 in 2024; mean 1,880/yr against CONTEXT 4.2's own "~2k rows/yr". The monthly shape of 2024 tracks 2023 closely. RELIANCE's `28-Oct-2024 Bonus 1:1` is present and parses.
- **Not committed:** `data/` is gitignored; `git ls-files data/` is empty.
- **Nothing else in the span touched the network.** The three new modules (`backtest.py`, `portfolio.py`, `pilot_evidence.py`) contain **no network primitive at all** — no `requests`, `urllib`, `http`, `socket`. `allow_network` defaults to `False` at every level (`backtest.py:1032,1093`) and the pack's scan passes it explicitly (`pilot_evidence.py:1413`). The decisive proof: the reviewer's regeneration ran against the frozen cache and reproduced the pack **byte-identically**, so the pack is a pure function of the local stores plus that cache.
- The throttle itself lives in the chunk-3 `corp_actions` fetcher, unchanged in this span and already reviewed-PASS.

## 4. Determinism and resume (directed check 4)

Reproduced by the reviewer at **kill points the builder never used** (the pack kills after RELIANCE, symbol 2 of 5):

| Probe | Shards at the kill | Resumed ledger sha256 | Identical | Dup keys |
|---|---|---|---|---|
| Uninterrupted | — | `c3363f6f1775…c1e318` | baseline | 0 |
| Killed after **HDFCBANK** (3 of 5) | TCS, RELIANCE, HDFCBANK | `c3363f6f1775…c1e318` | **YES** | 0 |
| Killed after **ICICIBANK** (4 of 5) | + ICICIBANK | `c3363f6f1775…c1e318` | **YES** | 0 |
| **Double interruption** (kill after TCS → resume → kill after ICICIBANK → resume) | TCS, then 4 | `c3363f6f1775…c1e318` | **YES** | 0 |

The reviewer's sha equals the sha the committed pack publishes. All four stable manifest digests are identical to each other. **B178 is proved in the direction that matters**: only COMPLETE symbols leave shards, so the resume re-walks exactly what it lost.

**Moved-SHA refusal:** mutating `RunSpec.code_sha` and resuming raises `BacktestError` naming both digests. **B180 holds.**

**No clock leak:** today's date appears in neither the ledger bytes nor the manifest; all 243 distinct entry/exit stamps are inside session hours; `ast` finds **zero** `now()` / `today()` / `utcnow()` / `monotonic` calls in `backtest.py` or `portfolio.py`. **B179 holds.**

**Pack regeneration byte-identical** — see section 1.

## 5. E13 basis consistency — the directed finding hunt (directed check 5)

The architect's arithmetic is right in substance. The exact figures: **45 × avg profit = Rs 96,489.60** (the architect's 96,489.45 used the pack's *displayed* Rs 2,144.21; the unrounded average is Rs 2,144.2133…). Gross profit is **Rs 101,099.20**. The gap is **Rs 4,609.60**, and the reviewer decomposed it exactly, from the ledger:

```
gross profit 101,099.20
  = 45 × avg profit          96,489.60   (the NET average over the NET-winner set)
  + 45 × Rs 100 commission    4,500.00   <-- BASIS mismatch: avg profit is NET, gross profit is GROSS
  + 4 rows' gross               109.60   <-- MEMBERSHIP mismatch: gross-positive, net-negative
  =                         101,099.20   EXACT
```

The four membership rows, named: HDFCBANK 2026-07-01 (gross +50.00, net −50.00) · ICICIBANK 2026-05-22 (+22.70 / −77.30) · ICICIBANK 2026-06-02 (+14.70 / −85.30) · BHARTIARTL 2026-05-27 (+22.20 / −77.80).

**Every averaged and ratio metric was recomputed by the reviewer from the ledger and every one reproduces exactly.** The arithmetic is not in question; the *disclosure of basis* is. Established basis, metric by metric:

| Metric | Basis of the NUMBER | Population it is taken over | Printed beside it? |
|---|---|---|---|
| Gross profit / gross loss | **GROSS** | rows by **gross** sign (49 / 97) | no |
| Profit factor 1.1432 | **GROSS** | as above | no |
| Winners / losers / flat 45/101/0 | — | rows by **net** sign | no |
| % profitable 30.82% | **NET** | net-winners / all (45/146) | no |
| Avg PnL, expected payoff −Rs 13.25 | **NET** | all trades | no |
| Avg profit Rs 2,144.21 | **NET** | **net**-winners | no |
| Avg loss −Rs 974.50 | **NET** | **net**-losers | no |
| Avg profit / avg loss 2.2003 | **NET** | both | no |
| Largest win Rs 2,900.00 | **NET** | argmax net | no |
| …"0.58% of its notional" | **NET** / notional | — | no |
| …"2.97% of gross profit" | **GROSS** / gross profit | — | no |
| Commission Rs 14,600.00 | — | all executed | n/a |

Because the cost is a flat Rs 100 on **all 146** executed rows (verified: the `cost_paise` distribution is `{10000: 146}`), `argmax(net) == argmax(gross)`, so the "largest win" row itself is unambiguous — but the three numbers printed about it are not (finding **Q4**).

→ Findings **Q1** and **Q2**. The architect's rule ("any mixed basis must be printed beside its number or it is a finding") is met on the finding side, not on the printing side.

**The other four directed sub-items, all recomputed by the reviewer and all exact:**

- **B185 drawdown-% denominators.** Max DD Rs 12,761.75 = **11.68%**, and the denominator is the **running peak equity (Rs 109,286.00)**, not the initial capital; max run-up Rs 16,422.00 = **17.68%** over the **running trough**. Both reproduce to the digit, with the running extreme seeded at the opening capital exactly as B185 records. Correct and standard — but unstated (finding **Q7**), and it hides a real defect (finding **Q3**).
- **B186 Sharpe / Sortino.** Sharpe **−0.3809** (sample sd, n−1, over 57 daily returns, × √252) and Sortino **−0.5903** (downside sum-of-squares of negative returns averaged over **all** n) both reproduce exactly under the reviewer's own Decimal arithmetic.
- **B187 CAGR span.** −8.43% reproduces. The span is the **endpoint difference**: 2026-05-04 → 2026-07-24 = **81 calendar days** over an 82-day window, `/365`. A defensible convention, unstated (finding **Q6**).
- **B188 buy & hold.** End value **Rs 98,403.99**, total return **−1.60%**, reproduced symbol by symbol from the raw bhavcopy. Units are genuinely fractional (10.946308 / 25.660765 / 15.738118 / 13.669606 / 8.226052); all five symbols have a close on 2026-05-04 so nothing was excluded.

**Take-all disclosures** also re-derived exactly: max concurrent **4** at 2026-05-05 13:15, peak simultaneous notional **Rs 2,276,677.55** at 2026-05-07 12:15 (3 positions), largest single **Rs 1,609,500.00**, distribution `{0:2, 1:7, 2:22, 3:15, 4:10, 5:2}` — which sums to 58 days and 146 trades, i.e. it partitions.

## 6. Q-16 — verification of what is actually there (directed check 6)

Read section 0 first. Against the repository as it stands:

- **(a) `outliers` is genuinely NOT computed and no count is ever printed.** `Metrics.outliers` is `None`; `outliers_note` carries the reason; the pack prints the sentence and no number. Reviewer grep over the pack: three mentions of "outlier", **zero counts**. `tests/test_portfolio.py::test_the_outliers_metric_is_blocked_on_the_architect_not_invented` pins it. **The STOP is correctly executed.**
- **(b) The PROVISIONAL construction recomputed by hand.** The reviewer rebuilt the band from the ledger — `low = opening + ΣMAE − Σcost`, `high = opening + ΣMFE − Σcost`, min/max'd against the close — and reproduced **both** figures exactly: intra-trade max drawdown **Rs 18,844.65** (2026-06-12 → 2026-07-20) and intra-trade max run-up **Rs 17,956.90**. The construction is the stated coinciding worst/best case and the MFE/MAE it consumes are **position-scaled**, which the reviewer proved separately (`trade_excursion_paise` multiplies by `qty`; kept probe). Against the close-to-close Rs 12,761.75 that is a **+47.7%** difference, which is why Q-16(b) is the architect's to rule.
- **PROVISIONAL labelling.** Present on both figures in the pack and on the two `Excursion` fields. **But the constant's own construction sentence never reaches the pack** — a reader sees the word and not what it assumes (finding **C3**).

## 7. Purity and floats (directed check 7)

AST sweep of both modules:

| | `portfolio.py` | `backtest.py` |
|---|---|---|
| float literals | **0** | **0** |
| `float()` / `round()` calls | **0 / 0** | **0 / 0** |
| clock reads | **0** | **0** |
| floor division | 0 | 0 |
| true division `/` | 15 — **all** Fraction/Fraction, Fraction/int, or Decimal/Decimal | 11 — **all** `pathlib.Path` joins |
| imports | stdlib + `.backtest` + `.signals` — **no I/O module at all** | stores, `atomic_io`, `subprocess` (git SHA) — I/O is allowed here |

**Sharpe and Sortino are display-layer only.** They are `Decimal`, produced by `_annualize`, and surface only as `Metrics.sharpe` / `Metrics.sortino`; no paise field is computed from either, and no Decimal or Fraction is ever written into a `LedgerRow` (independently confirmed: **no ledger row carries a float**). `portfolio.py` is genuinely pure — it opens no file, reads no clock, touches no store.

**Zero-division:** every ratio in the module guards — `_ratio` on count, `profit_factor` on gross loss, `_pct_of_notional` on notional, `_avg_ratio` on the average loss, `max_drawdown`/`max_run_up` on the peak/trough, `sharpe`/`sortino` on variance and n, `_cagr` on span and sign. **Two do not** (finding **C2**).

**I/O containment in `backtest.py`** is correct: all writes go through `atomic_write_text` (temp → fsync → atomic replace), the shard is published only on symbol completion, and `read_ledger` / `load_residual_register` are the only readers. A missing residual register is a hard error, not an empty dict.

## 8. Findings

### Quant

**Q1 · MEDIUM · CONTEXT 7-E13 — gross and net bases are mixed in one unlabelled table.**
`gross profit`, `gross loss` and `profit factor` are gross-basis; `avg PnL`, `avg profit`, `avg loss`, `avg profit/avg loss`, `expected payoff`, `largest win`, `largest loss` and `% profitable` are net-basis. The pack's section 7a prints them adjacent with no basis column and no note. A reader who multiplies 45 × Rs 2,144.21 gets Rs 96,489.45 and cannot reconcile it with Rs 101,099.20. **Profit factor 1.1432 reads "profitable" directly above Net PnL −Rs 1,934.95** — the two are consistent only once you know one is gross and the other net. *No number is wrong; the basis is undisclosed.* Closed by kept probes `test_the_gross_profit_population_is_not_the_winner_population` and `test_winners_times_avg_profit_does_not_equal_gross_profit`.

**Q2 · MEDIUM · CONTEXT 7-E13 — the winner set and the gross-profit set are different populations.**
`winners`/`losers`/`percent_profitable` count by the sign of **net**; `gross_profit`/`gross_loss` sum by the sign of **gross**. On the pilot **49 trades made money gross and 45 made money net**: four trades are inside "Gross profit Rs 101,099.20" and simultaneously counted among the "101 losers". The gross-basis rate (**33.56%**) is never printed beside the net-basis 30.82%. This is a distinct defect from Q1 — Q1 is the *basis* of the number, Q2 is the *membership* of the set — and the two together account for the Rs 4,609.60 exactly.

**Q3 · MEDIUM · CONTEXT 7-E13 ("max drawdown … with durations") — the recovery date is silently lost whenever the drawdown's peak is the opening capital.**
`_first_recovery` (`portfolio.py:293-304`) learns the peak equity only from a point whose `day == excursion.peak_day`. B185 deliberately makes `peak_day is None` mean "the run's opening capital" — the normal case for any run that goes down from its first day — and then no point ever matches, `peak_equity` stays `None`, and the function returns `None`. The report then says **"recovered never"** for a drawdown that demonstrably recovered. Reviewer witness: equity −5,000 / −3,000 / +9,000 / +1,000 recovers above the opening capital on day 3, and `recovered_on` comes back `None`. **Not exercised by the pilot** (its peak is a real day, 2026-06-12, so the pack's "recovered never in the window" is correct there) — but chunk 9B's full-history run starts at a seed and a first-day drawdown is entirely ordinary. Pinned by kept probe `test_a_drawdown_whose_peak_is_the_opening_capital_loses_its_recovery_date` (green today; **flip it when fixed**) with `test_a_drawdown_from_a_real_peak_names_the_day_it_recovered` as the control.

**Q4 · LOW · one line, two bases, and a sign that flips.**
"Largest win Rs 2,900.00 (0.58% of its notional, 2.97% of gross profit)": the amount and the first percent are **net**, the second uses that trade's **gross** (Rs 3,000.00). On the loss line, "−Rs 1,100.00 (−0.21% of its notional, **1.13%** of gross loss)" — the notional share is negative and the gross-loss share is positive, because a loss divided by a loss is positive. Defensible per B189, unexplained in the output. Closed by kept probe `test_the_largest_win_line_mixes_a_net_number_with_a_gross_share`.

**Q5 · LOW · `max_run_up.recovered_on` is structurally always `None`.**
`max_drawdown` computes it; `max_run_up` never does, on any input. E13 asks for run-ups in the "same forms". The field is dead rather than meaningfully empty, and a reader cannot tell the difference. Pinned by kept probe.

**Q6 · INFO · CAGR span convention unstated.** 81 calendar days for an 82-day window (endpoint difference), `/365`. Recorded in B187, not printed beside the −8.43%.

**Q7 · INFO · drawdown/run-up percentage denominators unstated.** The running peak (Rs 109,286.00) and running trough respectively, not the initial capital. Correct, standard, and invisible to the reader.

**Q8 · INFO · the pilot's E2 witness proves the mechanism but is not a discriminating day.**
2024-11-04's pair genuinely reaches back past the Muhurat to (2024-10-30, 2024-10-31) — verified. But **both** readings (with and without the E2 removal) yield `inside-bar-carry` and the same carried bullish bias, so this day does not demonstrate that E2 *changes an answer*. E2's real bite in the pilot is the Muhurat day itself, which has no 09:15–11:14 window at all and would otherwise be walked. Worth a discriminating witness in 9B's pack.

### Code

**C1 · MEDIUM · a CONTEXT 3.5 money amount is hardcoded in an engine-pure module.**
`portfolio.py:44` — `DEFAULT_INITIAL_CAPITAL_PAISE: int = 10_000_000` — is CONTEXT 3.5's trader-specified "Capital: ₹1,00,000 (R1-Q21a)", typed into `src/` with **no config key**. It is the default on five public functions (`equity_curve`, `buy_and_hold`, `metrics`, `side_split`, `per_symbol`) and is what the evidence pack actually uses (`pilot_evidence.py:824, 913, 1264`). It is the base of the equity curve and the denominator of return-on-initial-capital, CAGR and the benchmark — four E13 numbers.

This contradicts CLAUDE.md's code standard ("no … magic numbers — config and instrument master only"), config.yaml's own stated rationale ("a money constant hidden in an engine module is invisible to the operator and to the architect's spec sync"), and the treatment its two siblings received one chunk earlier — `risk_per_trade` and `cost_per_trade` are both config-loaded with a tripwire. **STATUS.md's chunk-8 line, "no CONTEXT 3.5 money amount hardcoded anywhere in src/acumen", is no longer true.** Nothing caught it because that tripwire (`test_simulate.py:862`) scans `inspect.getsource(sim)` only.

*Why this is a finding and not the verdict:* the value is correct, it is a named constant carrying its own spec citation rather than a buried literal, it is an overridable default, and it cannot move a trade, a fill or any paise field — only presentation denominators. Both personas list "hardcoded spec constant" under FAIL, so this was the closest call in the review; it is carried as a **blocking condition on 9B** (section 12) rather than a FAIL of 9A, and the architect should overrule if that reading is wrong.

**C2 · LOW · the only two unguarded divisions left in the module.**
`return_on_initial_capital` (`portfolio.py:753-755`) and the benchmark's `total_return` (`:602`) divide by `initial_capital_paise` with no guard; a zero raises `ZeroDivisionError` where every other ratio in the file returns `None`. Not reachable through the runner. Pinned by kept probe, with `test_every_other_ratio_returns_none_instead_of_dividing_by_zero` as the contrast that makes it a finding rather than a style note.

**C3 · LOW · the PROVISIONAL construction never reaches the output.**
`INTRA_TRADE_PROVISIONAL` states the assumption ("every same-day excursion coincides") but the pack prints only the word "PROVISIONAL" in two row labels. `outliers_note` is printed in full; its sibling is not. Q-16 says the construction is "explicitly stated" — it is, in QUESTIONS.md and in the source, not beside the number. Given the figure is 47.7% above the close-to-close drawdown, the assumption belongs next to it.

**C4 · INFO · the documented refusal order omits one of its own reasons.**
`backtest.py:23-26` lists "E2 → no minutes → gate 1 → gate 2 → gate 1P → suppressed → no bias → no POC" and then says, parenthetically, "extended at the front by E2 **and the bias failure**". `REASON_BIAS_UNRESOLVED` is not in the explicit chain, and it executes at position 2 — right after E2 and **before** "no minutes" and the gates (`walk_symbol`, L612-636). The parenthetical is accurate and the chain is incomplete; a reader reconciling `refused_by_reason` against the stated order could mis-attribute.

**C5 · INFO · E2 detection is store-derived, which chunk 13 must not inherit.**
`scan_non_standard_sessions` decides a market-wide calendar property by scanning stored candles across the run's universe and span. Correct and self-evidencing for a backtest, but the live path (chunk 13) has no future candles to scan, and CONTEXT §6's replay invariant requires the two paths to agree. 9B/13 should take non-standard sessions from the published NSE calendar and treat the scan as the backtest-side check. B181's own note already asks 9B to cache the scan; this is the sharper version of the same point.

**C6 · INFO · a stray CA cache file makes the row count read wrong.**
`data/nse/ca/` holds 23 files; the 22 year-files total exactly the claimed 41,351, but a leftover `nse_ca_2024-10-01_2024-10-31.json` month probe (76 rows) sits beside them and is never consumed by the year loop. Harmless — it cannot enter any factor table — but a reviewer summing the directory gets 41,427 and has to reconstruct why.

## 9. Class-B decisions judged (B178–B192)

| # | Verdict | Note |
|---|---|---|
| B178 | **APPROVED** | Shard-on-completion. Proved by the reviewer at three kill points plus a double interruption; duplicate-freedom is structural, not de-duplicated. |
| B179 | **APPROVED** | No clock in rows or manifest; `code_sha`/`config_digest` on disk but out of `stable_manifest_digest`. Verified by AST and by byte-identical regeneration after commits moved. |
| B180 | **APPROVED** | Moved-SHA resume refused; reviewer reproduced the refusal. The inconvenience is correct. |
| B181 | **APPROVED** with **C5** | E2 executed literally from CONTEXT's own detection clause; the market-wide reading is right. The live-path caveat is C5, the pilot's non-discriminating witness is Q8. |
| B182 | **APPROVED** | `capital_reference` as rupees, `margin_basis` as a multiple. Both null, no default anywhere — verified structurally (`capital_flags` contains **no integer literal at all**) and behaviourally on both branches plus the half-answered branch. Riding the shape question with Q43 is correct; nothing depends on it. |
| B183 | **APPROVED** | MFE/MAE over the held candles only, `> entry_stamp` through `<= exit_stamp`, signed, **qty-scaled**. Reviewer verified the scaling, the short mirror and the B159 no-monitored-candle case; realized gross sits inside `[MAE, MFE]` on all 146 rows. Computing it in the runner keeps `portfolio.py` pure — correct placement. |
| B184 | **APPROVED** | Every walked day in the daily series; Long/Short/per-symbol share the All index (`side_split`, `per_symbol` pass `days=index`). Right for an annualized daily Sharpe. |
| B185 | **APPROVED** *in principle*, but it **creates Q3** | Seeding the running extreme at the opening capital is the honest choice and reproduces exactly. But it makes `peak_day is None` a normal case, and `_first_recovery` cannot handle that case. The decision is right; the code does not fully implement it. |
| B186 | **APPROVED** | Sample sd (n−1); downside over all n; `None` never 0 for an undefined ratio. Both reproduce to the digit. Refusing to print 0 for undefined is exactly right for a report. |
| B187 | **APPROVED** with **Q6** | 365-day year over the walked span; `None` on non-positive final equity. Convention sound, disclosure missing. |
| B188 | **APPROVED** | Fractional units (reviewer confirmed none is whole); no-close symbols excluded and named. Rounding to whole shares really would make "equal weight" price-dependent. |
| B189 | **APPROVED** with **Q4** | Return-on-own-notional and share-of-gross are each the right choice; printing them in one parenthesis on two bases is the finding. |
| B190 | **APPROVED** | One day refused, not a symbol. Verified: 492 damaged IOC/TATASTEEL symbol-days walked with **zero** unhandled exceptions. Losing a symbol's history to its first morning would be the worse failure. |
| B191 | **APPROVED** | Run-level comparison seeded 40 days back. The reviewer's **independent** reimplementation with the same seeding reproduced 204/112/107/**47**. |
| B192 | **APPROVED** | Rare shapes and the outcome partition derived from rows at manifest time, not accumulated. This is precisely what makes a resumed run's manifest byte-identical, and it lets a reader recompute every count from the committed ledger. |

**All 15 approved**; B185's implementation gap is carried as Q3.

## 10. Standard sweep

| Check | Result |
|---|---|
| Full suite from clean | **1689 / 0** (1675 build + 14 reviewer probes); build's 1675/0 reproduced first; **no skips, no xfails** |
| Fixtures frozen | `git diff chunk8-pass..HEAD -- tests/fixtures poc` is **EMPTY** |
| F9 | untouched (inside the empty fixture diff) |
| CONTEXT.md | **untouched** in the span |
| Engine modules under prior review | `bias`, `poc`, `signals`, `simulate`, `signal_engine`, `bias_engine`, `corp_actions`, `aggregate`, `atomic_io`, `minute_backfill` — **all untouched** |
| Test weakening | **none** — `tests/` is **1,793 insertions, 0 deletions**; `test_config.py` 31→38 defs, 27→36 asserts, nothing removed |
| Commit hygiene | 4 commits, imperative subject + blank line + what/why body citing chunk and spec section; both src/tests-touching commits carry **`(unreviewed)`**, both doc-only commits correctly do not (REVIEW_7 C1) |
| Evidence rule | generator + output committed together (REVIEW_7 C3); regenerates byte-identically (REVIEW_8 C2) |
| AI attribution | **none** — the only "CLAUDE" strings are `CLAUDE.md`, the constitution filename, which the git rules explicitly permit |
| Secrets | no `.env` in the diff; no credential assignment added; the CA cache carries a public URL and no auth |
| Order-placement code | **none** |
| SHA chain | `dfa3ff8 → b3fb34c → 6285c21 → 60d2482 → 998ac1d`, linear, single branch, `origin/main == main` at review start |
| Capital-flag machinery, both branches | null/null → not computed + verbatim note; half-answered → still not computed; both set → flags on both tiers, exact-at-reference **not** flagged, no trade capped or resized. **No default figure anywhere** — `capital_flags` holds zero integer literals |
| Manifest | spec v1.4, `code_sha` == HEAD, residual register acknowledged, **CONTEXT 4.6's IOC/TATASTEEL caveat byte-identical to CONTEXT.md's own text**, all 8 rare-shape keys present at zero, `not_in_register` empty |
| PROGRESS entry | all 9 template fields present (plan.md §6) |
| Refusal partition (adversarial, real damaged data) | IOC + TATASTEEL 2018: 492 walked, 492 distinct keys, 4 reasons summing to 492, `usable + refused == walked`, outcome counts partition, **75 rows fail two gates and every one carries exactly one reason**, no refused row carries money, zero exceptions |

## 11. Reviewer probes kept

`tests/test_review9a_probes.py` — 14 tests, all green, nothing existing modified:

- 3 pin the **E13 basis** facts (population split, the exact Rs 4,500 + Rs 40 decomposition on a purpose-built fixture, the mixed-basis largest-win line) — Q1, Q2, Q4.
- 3 pin **defects** so a fix must be deliberate: the lost recovery date (Q3, with its control), the dead run-up recovery field (Q5), the unguarded capital division (C2, with its contrast).
- 3 cover **MFE/MAE**: position scaling (load-bearing for the Q-16(b) band), the short mirror, and the B159 no-monitored-candle case — none of which the build exercised on the short side.
- 2 cover the **partition** property and the **no-hidden-capital-figure** structural assertion on `capital_flags`.
- 1 pins that the **two blocked E13 entries never come back as numbers** while Q-16 is open.

## 12. Conditions carried to chunk 9B

9B is already blocked on Q43/Q44, so none of these blocks anything today. All six must be closed **before any report prints a number**:

1. **C1** — move the capital figure to `config.yaml` with a loader accessor, and extend the chunk-8 money tripwire to cover `portfolio.py` (and every module, not one).
2. **Q1 + Q2** — print the basis and the population beside every averaged, ratio and count metric, or state one basis and use it throughout. A trader reading "profit factor 1.1432" above "net −Rs 1,934.95" must not have to reconstruct why.
3. **Q3** — fix `_first_recovery` for `peak_day is None` and flip the pinning probe.
4. **C3** — print the `INTRA_TRADE_PROVISIONAL` sentence wherever the figure appears, as `outliers_note` already is.
5. **C5** — take non-standard sessions from the published calendar on the live path, and keep the store scan as the backtest-side cross-check, before chunk 13's replay invariant is attempted.
6. **Q-16** — still `OPEN · STOP`. No report may print either blocked E13 entry as final until the architect rules. See section 0: **the fix the brief presumes has not been written.**

---

**PASS.** Nothing in this chunk deviates from CONTEXT.md. The machine that will run the full backtest walks its days correctly, counts every exclusion exactly once, wires the real factor table on 47 pairs where an empty one would have traded the wrong side, and comes back byte-identical after being killed anywhere. Its remaining defects are in how it *reports* numbers, not in how it *computes* them — and every one of them is written down above.
