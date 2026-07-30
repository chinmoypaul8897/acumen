# REVIEW_9A_2 — chunk 9A · RE-REVIEW of the Q-16 / E13 fix span

**Type:** focused QC — BOTH personas (`personas/quant_reviewer.md` + `personas/code_reviewer.md`), fresh session.
**Span:** `4fa85fb..e83bc5e` — ten commits: the rulings record (2a91cde), C1 (03bd47f), Q-16(a) (ac2f4c8), Q-16(b) (19641f6), the E13 basis (7f06087), Q3/Q5/C2/C4 (5741a29), the C5/Q8 duties (fefe18d), the pack regeneration (cc796f3), and two records commits (03c4a47, e83bc5e).
**Scope:** did the fix execute the architect's rulings, and did it break anything? REVIEW_9A already passed the base at `chunk9A-pass`; that verdict is not re-litigated here.
**Suite:** **1747 passed / 0 failed** from a genuinely clean state (`.pytest_cache` + every `__pycache__` deleted first) — 1728 fix-session tests + **19 kept reviewer probes**. The fix's own 1728/0 was reproduced first. No skips, no xfails.

## VERDICT: **PASS**

with **8 findings** (3 LOW + 2 INFO quant; 1 MEDIUM + 2 LOW + 1 INFO code — numbering separate per persona), none blocking. Every clause of the architect's Q-16(a), Q-16(b) and E13 PRESENTATION BASIS rulings is executed, with a test behind it, and every headline figure in the regenerated pack was re-derived by this reviewer from the stores and the ledger **importing nothing from `src/acumen` for the arithmetic**. Nothing in the span deviates from CONTEXT.md. The findings are, without exception, about how three numbers are *labelled* and about branches the pilot never reaches — not about a number that is wrong.

---

## 1. THE PATH — 2026-05-05 re-derived by hand, and all 649 observations recomputed (directed check 1)

Reimplemented from the ruling's text: a 15-minute candle "closing at HH:MM" aggregates the open-stamped minutes in `[HH:MM−15, HH:MM)` (CONTEXT 7-E12) and its close is the last minute's close; a position is marked at every such close it was held, at its EXIT LEVEL on its exit candle; the marks are summed onto the day's opening equity. Inputs: `data/backtests/chunk9a_pilot_a/ledger.jsonl` and `data/minute_store/minute/<SYM>/*.parquet`. Nothing else.

**2026-05-05 carries four concurrent positions** — the pack's own max-concurrency day, at 13:15. Opening equity **Rs 102,745.55**.

| symbol | side | qty | entry | exit | kind | marks | last mark | ledger net |
|---|---|---|---|---|---|---|---|---|
| BHARTIARTL | short | 107 | 182,250 @ 11:45 | **180,490** @ 15:15 | square-off | 15 | +Rs 1,783.20 | +Rs 1,783.20 ✓ |
| ICICIBANK | long | 192 | 125,360 @ 13:00 | **125,230** @ 15:15 | square-off | 10 | −Rs 349.60 | −Rs 349.60 ✓ |
| HDFCBANK | long | 250 | 77,400 @ 13:15 | **77,290** @ 15:15 | square-off | 9 | −Rs 375.00 | −Rs 375.00 ✓ |
| RELIANCE | long | 454 | 146,640 @ 13:15 | **146,420** @ 13:30 | stop-loss-hit | 2 | −Rs 1,098.80 | −Rs 1,098.80 ✓ |

Every trade's FIRST mark is exactly **−Rs 100.00** — the cost charged at the entry mark (B194) — and every LAST mark reproduces the ledger's net to the paisa.

**The day's sixteen portfolio observations, summed by hand:**

| stamp | BHARTIARTL | HDFCBANK | ICICIBANK | RELIANCE | equity | open |
|---|---|---|---|---|---|---|
| 11:45 | −100.00 | | | | 102,645.55 | 1 |
| 12:00 | +1,804.60 | | | | 104,550.15 | 1 |
| 12:15 | +948.60 | | | | 103,694.15 | 1 |
| 12:30 | +1,494.30 | | | | 104,239.85 | 1 |
| 12:45 | +948.60 | | | | 103,694.15 | 1 |
| 13:00 | +156.80 | | −100.00 | | 102,802.35 | 2 |
| **13:15** | +124.70 | −100.00 | +207.20 | −100.00 | **102,877.45** | **4** |
| 13:30 | +606.20 | −525.00 | +111.20 | −1,098.80 (closed) | 101,839.15 | 3 |
| 13:45 | +178.20 | +75.00 | −157.60 | −1,098.80 | 101,742.35 | 3 |
| 14:00 | +1,323.10 | −75.00 | −42.40 | −1,098.80 | 102,852.45 | 3 |
| 14:15 | +1,291.00 | −387.50 | −464.80 | −1,098.80 | 102,085.45 | 3 |
| 14:30 | +1,066.30 | +450.00 | −23.20 | −1,098.80 | 103,139.85 | 3 |
| 14:45 | +1,430.10 | +175.00 | −100.00 | −1,098.80 | 103,151.85 | 3 |
| 15:00 | +1,793.90 | −350.00 | −349.60 | −1,098.80 | 102,741.05 | 3 |
| 15:15 | +1,783.20 | −375.00 | −349.60 | −1,098.80 | **102,705.35** | 0 |
| day close | | | | | **102,705.35** | 0 |

The day's net is **−Rs 40.20** and `102,745.55 − 40.20 = 102,705.35` — **the closing observation equals the day's closing equity exactly**, which is the invariant B194's cost placement exists to buy. The 13:15 row is the pack's "max concurrent 4 at 2026-05-05 13:15", reproduced.

### The whole path, recomputed

| Quantity | Pack | **Reviewer, independently** |
|---|---|---|
| trade paths | 146 | **146** |
| marks | 903 | **903** |
| paths whose last mark == ledger net | all | **146 / 146, 0 failures** |
| path observations | 649 | **649** |
| day-close identity | PASS | **58 / 58 days, 0 failures** |
| marks outside the session | none | **0** (earliest 11:30, latest 15:15) |
| **max drawdown** | Rs 14,231.00 (12.98%) | **Rs 14,231.00**, 1,423,100 paise / peak 10,967,790 → **12.98%** |
| its peak → trough | 2026-06-11 12:15 → 2026-07-23 11:45 | **identical** |
| observations | 302 of 649 | **302** |
| recovered | never | **never** — no later observation reaches Rs 109,677.90 |
| **max run-up** | Rs 17,515.10 (19.00%) | **Rs 17,515.10**, 1,751,510 / trough 9,216,280 → **19.00%** |
| its trough → peak | 2026-05-19 12:15 → 2026-06-11 12:15 | **identical** |
| observations | 197 of 649 | **197** |

**The three new pack invariants are verified, not accepted.** All three reproduce above.

### The exit-LEVEL rule is load-bearing on real data, not only on the fixture

The build proves the rule on one synthetic trade. Measured on the pilot: **107 of the 146 exits fill at a level their own 15-minute candle did not close at.** Marking closes instead would break the reconciliation invariant on all 107 rows, misstate HDFCBANK 2026-05-29 by **Rs 2,843.75**, and move Rs 67,554.55 of absolute error across the run. B196 is right and it bites. Closed by kept probe.

Two further assembly facts, checked because the code has fallbacks that could paper over drift:

- **The entry mark equals the entry candle's own 15-minute close on all 146 trades** — so `assemble_trade_paths`' ledger-price fallback never fires on this pilot, and the runner and the store agree about what the entry candle closed at.
- **No trade's marks skip or add a 15-minute slot inside its holding window** (0 of 146), so `_contribution`'s carry-forward across a missing bar is never exercised here.

## 2. TUKEY — the fences recomputed twice, and both hand-computed fixtures (directed check 2)

Type 7 written out from its definition by the reviewer, in exact `Fraction`s, over the 146 executed trades' net PnL — and again in the other algebraic form inside the kept probe, so `pf.quantile` cannot validate itself.

```
n = 146
position(Q1) = (n-1) x 1/4 = 145/4  = 36.25  -> x[36] + 1/4 (x[37] - x[36]) = -109,900 paise
position(Q3) = (n-1) x 3/4 = 435/4  = 108.75 -> x[108] + 3/4 (x[109] - x[108]) = +99,720 paise
IQR         = 99,720 - (-109,900) = 209,620
lower fence = -109,900 - (3/2)(209,620) = -424,330  = -Rs 4,243.30
upper fence =  +99,720 + (3/2)(209,620) = +414,150  = +Rs 4,141.50
```

| | Pack | **Reviewer** | **numpy.percentile(x, [25,75])** |
|---|---|---|---|
| Q1 | −Rs 1,099.00 | **−109,900 paise** | **−109,900.0** ✓ |
| Q3 | Rs 997.20 | **+99,720 paise** | **+99,720.0** ✓ |
| IQR | Rs 2,096.20 | **209,620** | 209,620.0 ✓ |
| fences | [−Rs 4,243.30, Rs 4,141.50] | **identical** | identical ✓ |
| outliers | NONE of 146 | **0 of 146** | — |

**The zero is a structural property, not an empty result**, and the reviewer confirmed the reason the fix session states: a fixed-rupee-risk trade is bounded by construction — the pilot's worst net is **−Rs 1,100.00** and its best is **+Rs 2,900.00**, both comfortably inside the fences. That is worth telling the trader as a property of the strategy.

**Both hand-computed docstring fixtures verified independently and against numpy:**

| fixture | n | Q1 | Q3 | IQR | fences | outliers |
|---|---|---|---|---|---|---|
| six-trade ledger (positions land BETWEEN order statistics) | 6 | −85,000 | +77,500 | 162,500 | **[−328,750, +321,250]** | **0** |
| nine-trade fixture (positions land ON order statistics) | 9 | −60,000 | +20,000 | 80,000 | **[−180,000, +140,000]** | **2** |

Every arithmetic step in both docstrings is correct: `5/4` between x[1] and x[2] gives −85,000; `15/4` between x[3] and x[4] gives +77,500; `(n−1)×1/4 = 2` and `(n−1)×3/4 = 6` land exactly on x[2] and x[6] for n = 9. The nine-trade tails, sums and shares all reproduce — count 2, summed net +100,000, shares **50/53** and **9/11**. `numpy.percentile` agrees on both to the digit. **B195 is reproducible exactly as it claims.**

The build tests a trade sitting exactly ON the UPPER fence. The **LOWER** fence had no such test; a kept probe adds it, plus the one-paise-past control.

## 3. NET BASIS — both pots, the profit factor, the identity, and a whole-pack scan (directed check 3)

Recomputed from the ledger with the reviewer's own arithmetic:

```
winners (net > 0) 45 · losers (net < 0) 101 · flat 0 · total 146
gross profit (net basis) = +9,648,960 paise = Rs 96,489.60
gross loss   (net basis) = -9,842,455 paise = -Rs 98,424.55
gross profit + gross loss = -193,495 = Rs -1,934.95 = the ledger's net PnL, EXACTLY
profit factor = 9,648,960 / 9,842,455 = 1,929,792/1,968,491 = 0.980341... -> 0.9803
```

**Every figure matches the pack.** The identity the ruling exists to buy holds on the real 146, not only on a fixture:

- `winners x avg profit` = `45 x 643,264/3` = **9,648,960 = gross profit** ✓
- `losers x avg loss` = `101 x (-9,842,455/101)` = **−9,842,455 = gross loss** ✓
- `avg profit / avg loss` = **2.2003** ✓ · expected payoff **−Rs 13.2531 → −Rs 13.25** ✓ · % profitable **30.82%** ✓
- largest win Rs 2,900.00 = **0.58%** of its own notional and **3.01%** of gross profit (290,000/9,648,960) ✓ — the old mixed 2.97% is gone
- largest loss −Rs 1,100.00 = **−0.21%** of notional and **1.12%** of gross loss ✓
- before-costs pair **Rs 101,099.20 / −Rs 88,434.15**, commission **Rs 14,600.00**, and `101,099.20 − 88,434.15 − 14,600.00 = −1,934.95` ✓

**Sections 7b and 7c recomputed row by row and all reproduce exactly** — All 146/−Rs 1,934.95/45/101/30.82%/DD Rs 12,761.75; Long 61/−Rs 17,448.75/15/46/24.59%/Rs 20,056.80; Short 85/+Rs 15,513.80/30/55/35.29%/Rs 10,902.45; and all five per-symbol rows including every largest win and largest loss. Sharpe **−0.3809**, Sortino **−0.5903**, return on capital **−1.93%**, CAGR **−8.43%** over an 81-day endpoint span — **all unchanged from REVIEW_9A**, which is the point: the basis conversion moved the pots and nothing else.

**The whole-pack before-costs scan.** Three lines in the pack carry a before-costs total under a label, exactly as designed (two in section 3's cross-document reconciliation, one in the metric table). **A fourth, unlabelled, is still there** — section 3's `| Gross PnL | Rs 12,665.05 |`, the same 146 trades before the same Rs 100s. See finding **Q1**. No *other* stray was found: every number in sections 7a–7f is net-basis and reproduces on that basis.

## 4. THE SEVEN FLIPPED PROBES against the PRE-FIX code (directed check 4)

`4fa85fb` checked out into a scratch git worktree; HEAD's `tests/test_review9a_probes.py` copied in and run against the pre-fix `src/`.

**First run: 8 failed / 6 passed — and three of those failures were an ARTIFACT.** The flip commit also removed `mfe_paise` / `mae_paise` from the `_points` helper (they were `DailyPnL` fields the retired band needed), so three tests died with `TypeError` before reaching their own assertions. A probe that fails on a helper signature proves nothing. The helper was patched in the pre-fix copy to satisfy the old signature, and the run repeated.

**Second run: exactly the SEVEN flipped probes fail, each on its own assertion, and the control passes.**

| # | probe | pre-fix failure — its OWN assertion | HEAD |
|---|---|---|---|
| 1 | `..._gross_profit_population_is_the_winner_population` | `404000 == 380000` — the gross-basis pot | **pass** |
| 2 | `..._winners_times_avg_profit_equals_gross_profit` | `2 x 190,000 == 404,000` — the identity fails | **pass** |
| 3 | `..._largest_win_line_is_net_on_every_one_of_its_three_numbers` | `Fraction(75,101) == Fraction(29,38)` — gross/gross vs net/net | **pass** |
| 4 | `..._drawdown_whose_peak_is_the_opening_capital_keeps_its_recovery_date` | `None == DAY+2` — **Q3** | **pass** |
| 5 | `..._max_run_up_reports_when_its_rise_was_given_back` | `None == DAY+3` — **Q5** | **pass** |
| 6 | `..._metrics_guard_the_initial_capital_like_every_other_ratio` | `ZeroDivisionError: Fraction(164000, 0)` — **C2** | **pass** |
| 7 | `..._two_blocked_e13_entries_never_come_back_as_numbers` | `assert None is not None` — outliers not computed | **pass** |
| — | `..._drawdown_from_a_real_peak_names_the_day_it_recovered` (**CONTROL**) | **passes on both** — correctly, that path always worked | pass |

**No flipped probe is decoration.** Each fails on the pre-fix code for the defect it was written to pin, and the control that must pass on both does.

The probe file is **14 tests before and 14 after** — none added, none removed, `pytest.raises` 2 → 0 only because the C2 behaviour legitimately changed from raising to returning `None`, and the replacement asserts more (the value *and* that the money is unaffected by the degenerate capital).

## 5. C1 CLOSURE — the capital, the required key, and the widened tripwire (directed check 5)

**The constant is gone from `src/`.** The reviewer's own AST sweep over **all 35 files in `src/acumen`** (34 modules + `__init__.py`; the brief said 36) for the five CONTEXT 3.5 magnitudes `{1,000 · 10,000 · 100,000 · 10,000,000}` finds **zero** integer literals. `DEFAULT_INITIAL_CAPITAL_PAISE` no longer exists, and all five public functions that need the figure (`equity_curve`, `metrics`, `side_split`, `per_symbol`, `buy_and_hold`) take it as a **required** keyword with no default. Only four modules mention "capital" as an identifier at all, and every one of them names a config accessor or a flag record.

**`initial_capital` is REQUIRED.** Verified on all five branches: a **missing key** fails at LOAD (`Missing key`), a **null** fails naming `initial_capital` and citing CONTEXT 3.5, a non-positive or non-numeric value is refused, and a fractional-paisa amount is refused rather than rounded (`whole number of paise`). The repo config carries **100000 → 10,000,000 paise** and the conversion goes through `Decimal` exactly once. **B199 approved.**

**The widened tripwire, attacked twice.** A money literal was injected into **two modules of the reviewer's own choosing** — `src/acumen/poc.py` (`10_000_000`, the capital in paise) and `src/acumen/universe.py` (`100_000`, the risk in paise / capital in rupees):

| | baseline | after injection | after restore |
|---|---|---|---|
| `poc.py` | tripwire **passes** | tripwire **FAILS**, naming the module and the magnitude | passes; file **sha256-identical** to baseline |
| `universe.py` | tripwire **passes** | tripwire **FAILS** | passes; file **sha256-identical** to baseline |

It trips both times, and both files were restored byte-identically (sha256 verified). The forbidden set really is derived from the committed config, so it cannot drift from the spec values it protects. **B200 approved** — with the limit written down as finding **C2**.

**The `100 * 100` rewrite moved no value.** `price_proven_ratio` is a `Fraction`, so `int(r × 10000)` and `int(r × 100 × 100)` are the same integer by exact rational associativity. Proved rather than argued: **exhaustively over every `(pass, total)` with `total ≤ 399`** — 79,800 pairs, **0 divergences** — and again through `ResidualEntry.as_dict()` itself for `total ≤ 199`. Kept as a probe.

## 6. Q3 / Q5 / C2 / C4 and their controls (directed check 6)

- **Q3 — the opening-capital peak keeps its recovery date.** `_first_recovery` now resolves the level BEFORE the walk. Verified: equity −5,000 / −3,000 / +9,000 / +1,000 has `peak_day is None` (B185), falls Rs 8,000.00, and now names **DAY+2** as the recovery. **The control matters and it holds**: a run that never gets back above its opening capital (−5,000 / −3,000 / +1,000) still reports `recovered_on is None`. The fix did not turn "never recovered" into a date that is always there.
- **Q5 — the run-up mirrors correctly.** `_first_giveback` is the exact mirror: a rise from the opening capital to +300,000 by day 3 that is handed back on day 4 reports **DAY+3**; a rise that is never handed back reports `None`. **The pilot's "given back never" is CORRECT and was verified against the equity series, not accepted**: the close-to-close run-up runs from the trough Rs 92,864.00 (2026-05-15) to the peak Rs 109,286.00 (2026-06-12), and **the lowest closing equity anywhere after that peak is Rs 96,524.25** — Rs 3,660.25 above the trough. It genuinely never comes back. The 15-minute path's run-up is likewise never given back.
- **C2 — both capital divisions guarded.** `return_on_initial_capital` and the benchmark's `total_return` both return `None` on a zero capital, and `metrics(..., initial_capital_paise=0)` still reports the money correctly. Contrast test kept.
- **C4 — the chain is right; the sentence under it is off by one.** The documented refusal order now names `REASON_BIAS_UNRESOLVED` explicitly and in the position the code executes it (second, before "no minutes" and the gates), with all three of its cases spelled out — that is the finding closed. The sentence the fix added beneath it is wrong: see finding **C1**.

## 7. NO COLLATERAL DAMAGE (directed check 7)

| Check | Result |
|---|---|
| **Run ledger sha256** | **`c3363f6f17757ebcbb2f08e8159e943cbbd692836d165687cbb2d91e22c1e318`** — unchanged, the digest REVIEW_9A verified at four kill points |
| Ledger + all shards after **three** full regenerations | **byte-identical, every file** (36 run artefacts diffed before/after) |
| Pack regenerates byte-identically | **YES — three independent regenerations to scratch paths, all sha256 `9e8a77c7…`, `diff` empty against the committed file every time** (under a reviewer-side harness — see finding **C3**) |
| `stable_manifest_digest` | pilot `89c40168…`, resume whole **==** resume killed `b1390597…` — both equal the pack's published values, **while `code_sha` on disk moved to `e83bc5e` (HEAD)**. B179 independently confirmed: the commit-dependent fields are on disk and out of the digest, which is the only reason a pack regenerated after the commit can be byte-identical |
| Fixtures frozen | `git diff chunk8-pass..HEAD -- tests/fixtures poc` **EMPTY**; the same across the fix span |
| **F9** | untouched (inside the empty fixture diff; last touched at `75e3f98`, chunk-7 prep) |
| Engine modules under prior review | `bias`, `poc`, `signals`, `simulate`, `signal_engine`, `bias_engine`, `corp_actions`, `aggregate`, `atomic_io`, `minute_backfill` — **all untouched in the span** |
| CONTEXT.md / plan.md | **untouched** |
| Resume / determinism pins | green inside the full suite; independently, both resume manifests hash equal and the ledger digest is the published one |
| Test weakening | **none.** Across the four touched test files: **106 → 134 test functions (+28)**, **256 → 387 asserts (+131)**, **0 skips, 0 xfails**. Four test *names* disappear without a same-name replacement (`..._never_prints_an_outlier_count`, `..._intrabar_drawdown_uses_the_provisional_low`, `..._intraday_band_is_the_provisional_worst_and_best_case`, `..._outliers_metric_is_blocked_on_the_architect`) — **every one pinned behaviour the architect's ruling explicitly RETIRED, and every one is replaced by a test asserting the retirement**. Ruling-driven, strictly stronger. |
| Pack diff | reviewed line by line: only the ruled changes, the three new invariants and the two recorded 9B duties. **No figure in sections 3, 4, 5 or 6 moved** — one label changed on two section-3 rows and no value with it |

## 8. Class-B decisions judged (B193–B201)

| # | Verdict | Note |
|---|---|---|
| **B193** | **APPROVED** | The pots keep E13's own vocabulary while their basis changes. The ruling itself says "gross profit / gross loss / profit factor computed over the NET-basis populations", so keeping the names follows the ruling rather than drifting from it; the basis rides in the field doc, the printed label and the `basis` field on every `Metrics`. Renaming would have broken E13's and TradingView's shared vocabulary for no gain. |
| **B194** | **APPROVED** | Cost at the ENTRY mark. Verified to be exactly what makes the last mark equal the realized net on **146/146** and the day-close identity hold on **58/58**; charging it at the exit would step every day's last observation by Rs 100 per trade and sever the path from the daily curve. Economically it is also the honest reading — the round trip is committed at open. |
| **B195** | **APPROVED** | Type 7, exact Fractions. Reproduced against `numpy.percentile` on the real 146 and on both fixtures, and against a second independent implementation in the kept probes. Naming the estimator IN the printed definition is the correct handling of a freedom the ruling left open — the architect can overrule it by reading the pack. |
| **B196** | **APPROVED** | Marks from the same `aggregate_15min` the signal engine used; exit at the LEVEL. Measured to bite on **107 of 146** real exits, worst single error Rs 2,843.75. The entry mark was checked against the store on all 146 and equals the entry candle's close, so the ledger-price fallback is a genuine safety net rather than a papering-over. |
| **B197** | **APPROVED** | Per-column paths. Verified: Long's own path is 342 observations with a Rs 20,960.50 drawdown and Short's 476 with Rs 12,069.35, against All's 649 / Rs 14,231.00 — a side's drawdown is **larger** than the portfolio's, exactly as its close-to-close drawdown already was (Rs 20,056.80 vs Rs 12,761.75). Same discipline as B184; a slice would have been wrong. |
| **B198** | **APPROVED in principle — it CREATES finding Q1** | Keeping chunk 8's before-costs figures in a cross-document reconciliation is right, and labelling them is right. But the table holds **three** before-costs rows and the decision (and the disclosed exception it produced) accounts for **two**. |
| **B199** | **APPROVED** | REQUIRED, not optional. Verified across five refusal branches. The distinction from `capital_reference` is exactly right: no open item stands behind CONTEXT 3.5's capital. |
| **B200** | **APPROVED with finding C2** | The tripwire trips on two injections of the reviewer's choosing and derives its magnitudes from the config. Excluding the cost in rupees is correctly reasoned. The `100 * 100` rewrite is proved value-neutral exhaustively. The residual limit — a literal scan cannot see a computed magnitude, and this span contains the worked precedent for splitting one — belongs written down beside the tripwire. |
| **B201** | **APPROVED** | Dropping `DailyPnL`'s excursion sums removes state that existed only for the retired band and that a later chunk could have resurrected. `metrics()` building the path from the same `series` it uses for the daily curve is what makes a subset's two views structurally unable to disagree — verified through `side_split` and `per_symbol`. |

**All nine approved.** B198's execution gap is carried as Q1 and B200's limit as C2.

## 9. Findings

### Quant

**Q1 · LOW · a THIRD before-costs figure survives outside the one labelled line and outside the disclosed exception.**
Section 3's reconciliation carries `| Gross PnL | Rs 12,665.05 |` — the sum of gross PnL over the same 146 trades, before the same Rs 100s — with no basis label. The definitions block's exception names only chunk 8's `"gross profit / gross loss"` and says "**Those two rows** are labelled"; the metric table's own line claims its pair are "**the only** before-costs figures in this pack". Both statements are literally false while this row stands. *Why it is LOW and not the verdict:* the two rows directly beneath it are "Costs paid Rs 14,600.00" and "Net PnL −Rs 1,934.95", which makes the triple self-explanatory, and "Gross PnL" is not a name the report reuses on the net basis — so it cannot mislead the way REVIEW_9A Q1 did. Fix is one label or one sentence. Pinned by `test_the_pack_still_carries_a_third_before_costs_figure` (**flip when fixed**).

**Q2 · LOW · the 15-minute run-up prints its GIVEBACK using the drawdown's vocabulary.**
`pilot_evidence._path_line` hard-codes `"never recovered in the window"` / `"recovered <stamp>"` for both forms. For a run-up that field is the **giveback** — the first later observation at or below the trough — which is precisely what Q5's fix built, and the close-to-close run-up row one line above says it correctly: "given back never in the window". The pack therefore describes one quantity two ways in adjacent rows. Pinned (**flip when fixed**).

**Q3 · LOW · the MFE/MAE rows and section 8's excursion invariant are BEFORE-COST inside a page that declares one NET basis.**
Measured on the pilot: realized **gross** sits inside `[MAE, MFE]` on **146 of 146** rows; realized **net** on **126 of 146**. Section 7a says "every other number on this page is NET" and then prints avg MFE/MAE and largest MFE/MAE, which carry no Rs 100; section 8 asserts "every executed trade's realized PnL sits inside [MAE, MFE]", which is a **gross** statement. A reader applying the declared basis finds 20 apparent violations of an invariant the pack marks PASS. No number is wrong; the basis of two rows and one invariant is undeclared — the same species of gap the E13 ruling was issued to close, on the one metric family the ruling's enumeration does not name. Pinned with the exact counts.

**Q4 · INFO · on the zero-outlier branch the ruling's other three quantities are omitted rather than printed as zeros.**
Q-16(a) asks for count, summed net PnL, both shares and the definition. With zero outliers the pack prints the count (as "NONE of 146"), the fences, the quartiles and the full definition, but not the summed net (Rs 0.00) or the two 0% shares. Defensible — printing three zeros is noise — and the non-zero branch does print all four (verified by a new probe). Recorded so the omission is a choice on the record rather than an oversight when 9B's run has outliers.

**Q5 · INFO · the pack's session records are dated one day ahead of their own commits.**
The PROGRESS entry is stamped `[2026-07-30 02:40]` and every ruling citation reads "30-Jul-2026", while all ten commits in the span are `2026-07-29 20:40–21:44 +0530`. Cosmetic, and the content is faithful; noted only because a ruling recorded before its own stated date is the kind of thing a later audit trips on.

### Code

**C1 · LOW · the C4 rewrite's own attribution sentence is off by one — the same species of slip C4 was.**
`backtest.py`'s module docstring now writes the refusal chain out correctly and in execution order (that was the finding). Beneath it, it adds: *"The first three are decided by `BacktestRunner.walk_symbol`; the rest are `acumen.signal_engine`'s own order."* Exactly **two** are: `walk_symbol` emits `REASON_E2_NON_STANDARD` and `REASON_BIAS_UNRESOLVED` and nothing else (`NO_MINUTES` does not appear anywhere in `backtest.py`). "No minutes" is `signal_engine.stock_day`'s first reason. A reader reconciling `refused_by_reason` against the stated layers would mis-attribute one bucket. Pinned by `test_walk_symbol_decides_exactly_two_of_the_documented_refusal_reasons` with a control asserting the chain itself is complete (**flip when fixed**).

**C2 · MEDIUM · the pack's own renderers had branches with ZERO coverage — the ones chunk 9B will actually take.**
`pilot_evidence._outlier_line`, `_path_line` and `_path_stamp` are referenced by **no test at all**, and the committed pilot only ever exercises their empty branches: zero outliers, an excursion that never recovers, a metric set that always has a path. The code that will print the outlier count, both tails, both shares, the recovery stamp and the "NOT COMPUTED" fallback on the full-history run had never been executed. That is exactly the shape of REVIEW_8's `run_sweep` finding one chunk earlier. **CLOSED by two kept probes** covering all of it — the non-zero outlier line (all four ruled quantities), a recovering path excursion, the no-path fallback, and all three `_path_stamp` branches. Raised as MEDIUM because it was untested output on the reporting path, not because anything printed wrong.

**C3 · LOW · the evidence pack cannot be regenerated on any day after its CA cache's `fetched_on` — so REVIEW_8 C2's rule is unverifiable from the day after it is written.**
`nse_http.cached_json` serves a day-cache only when `fetched_on == today`; anything older raises when `allow_network=False`. The frozen cache is `2026-07-29` and this review ran on `2026-07-30`, so `python docs/evidence/chunk9a_pilot.py` — the command the pack's own header prints — **refuses to run**. `minute_backfill.fetch_corp_action_history`'s docstring promises the opposite ("with `allow_network=False` this reads only the day-cache, so a reviewer with the frozen cache gets a deterministic history and a bare clone gets an empty one"); neither half holds — a stale cache raises and a missing cache raises. **PRE-EXISTING** (chunk-3's cache policy plus the chunk-9A build), not introduced by this fix span, but it blocked directed check 7 as written and will block chunk 9B and every later reviewer. *How this review verified byte-identity anyway:* a reviewer-side harness that patches `nse_http.read_cache` to report the cache's age as today and changes **no datum** — the same frozen bytes are served — after which **three** independent regenerations to scratch paths all came back sha256 `9e8a77c7…`, byte-identical to the committed file. Pinned by a probe asserting the refusal on both the stale and the missing branch (**flip when the evidence path is made age-independent**).

**C4 · INFO · the money tripwire is a literal scan and this span contains the worked precedent for evading it.**
The scan finds integer **literals**, so `10 ** 7`, `5_000_000 * 2` and `int(1e7)` all carry a CONTEXT 3.5 magnitude past it — asserted in a probe. B200's own collateral edit (`ratio * 10000` → `ratio * 100 * 100`) is that evasion applied for a legitimate reason, and it is now a pattern in the tree. The tripwire is nonetheless **strictly stronger** than the single-module version it replaces and it caught two deliberate injections here; the limit simply belongs written down beside it so a future session does not read a green tripwire as a proof.

## 10. Standard sweep

| Check | Result |
|---|---|
| Full suite from clean | **1747 / 0** (1728 fix + 19 reviewer probes); the fix's own 1728/0 reproduced first; **no skips, no xfails** |
| Commit hygiene | 10 commits, imperative subject + blank line + what/why body citing chunk and spec section; **all seven src/tests-touching commits carry `(unreviewed)`**, all three doc-only commits correctly do not (REVIEW_7 C1) |
| Evidence rule | generator + output committed together (REVIEW_7 C3); regenerates byte-identically (REVIEW_8 C2 — with the caveat in **C3**) |
| AI attribution | **none** — the only "CLAUDE" strings in the span are `CLAUDE.md`, the constitution filename, which the git rules explicitly permit |
| Secrets | no `.env` in the diff; no credential assignment added; nothing printed or logged from the environment |
| Order-placement code | **none** |
| SHA chain | `4fa85fb → 2a91cde → 03bd47f → ac2f4c8 → 19641f6 → 7f06087 → 5741a29 → fefe18d → cc796f3 → 03c4a47 → e83bc5e`, linear, single branch `main`, `origin/main == main` at review start |
| Q-16 closure in QUESTIONS.md | ruling recorded in a verbatim block with its own attribution line, the header moved `OPEN — STOP` → `RESOLVED`, and each clause's execution recorded beneath it. **Every clause of the recorded text is executed in code with a test behind it** (a byte-comparison against the operator's own copy of the ruling is available on request) |
| C5 + Q8 duties present in the pack | **YES** — both in section 9 "What chunk 9B still owes", each with its reasoning and its owner (C5 → chunk 13's live path; Q8 → 9B's pack) |
| PROGRESS entry | all 9 template fields present (plan.md §6); nine Class-B decisions recorded B193–B201; date stamp noted as **Q5** |
| Network | whole review OFFLINE; every store read read-only; nothing written to either price store; the only files this session creates are its own review, probes and records |

## 11. Reviewer probes kept

`tests/test_review9a2_probes.py` — **19 tests, all green, nothing existing modified**:

- **4** pin the Q-16(b) path on REAL data: the exit-LEVEL rule biting on 107 of 146 exits, path reconciliation + the entry-mark identity against the store, no skipped 15-minute slot, and both headline path figures recomputed with the day-close identity on all 58 days.
- **3** cover Q-16(a) estimator and fence coverage: an independently written type-7 estimator, the **LOWER** fence boundary (which the build did not test) with its one-paise-past control, and both tail shares bounded in [0, 1].
- **2** pin the net-basis identities on the committed pilot ledger and the measured MFE/MAE basis gap (Q3).
- **3** pin defects so a fix must be deliberate: the third before-costs figure (Q1), the run-up giveback printed as a recovery (Q2), and the refusal-order attribution (C1) with its completeness control.
- **3** cover C1's tripwire: its reach over the whole package, the literal-vs-computed limit (C4), and the `100 * 100` rewrite proved value-neutral over 19,900 `(pass, total)` pairs through `ResidualEntry` itself.
- **2** close the renderer coverage gap (C2): the non-zero outlier line with all four ruled quantities, and a recovering path excursion, the no-path fallback and all three `_path_stamp` branches.
- **1** pins the day-cache refusal that makes the pack un-regenerable after its cache's day (C3), on both the stale and the missing branch.
- **1** re-asserts the Q-16(a) fences against the pilot with the "why it is zero" property stated as an assertion rather than an absence.

## 12. Conditions carried forward

REVIEW_9A section 12 listed six conditions on 9B. **Four are now CLOSED** (C1, Q1+Q2, Q3, C3-of-REVIEW_9A — the PROVISIONAL construction is retired outright rather than annotated) and **Q-16 is RESOLVED**. **C5 remains open by deliberate scope** and is recorded in the pack, together with **Q8**. This re-review adds:

1. **Q1** — label section 3's "Gross PnL" row, or widen the disclosed exception to the three rows it actually covers. One line either way; before 9B's report prints.
2. **Q2** — say "given back" on the 15-minute run-up row, as the close-to-close row already does.
3. **Q3** — state the MFE/MAE basis, or restate the pair and section 8's invariant on the net basis. 9B's report will print these beside 5+ years of trades.
4. **C1** — "the first **two** are decided by `walk_symbol`".
5. **C3** — make the evidence path age-independent (serve the frozen day-cache regardless of `fetched_on` when `allow_network=False`, or pin the CA history to a committed snapshot), and correct `fetch_corp_action_history`'s docstring. Without it no future session can check REVIEW_8 C2 on any pack.
6. **C4** — record the tripwire's literal-scan limit beside the tripwire.

None of these blocks anything today; 9B is still blocked on the trader's Q43/Q44.

---

**PASS.** The architect's three rulings are executed exactly as written and every number they produce was re-derived here from the stores and the ledger without importing the code under review: the 15-minute path reconciles on all 146 trades and 903 marks, its day-close identity holds on all 58 days, and its drawdown and run-up land on Rs 14,231.00 and Rs 17,515.10 to the paisa; the Tukey fences reproduce under two independent estimators and under `numpy`; both pots, the profit factor and the `winners x avg profit == gross profit` identity reproduce on the real 146. The seven flipped probes each fail on the pre-fix code for their own defect and the control passes on both. The capital is gone from `src/`, the widened tripwire trips on two injections and restores byte-identically, the run ledger is untouched, the fixtures are frozen, no engine module moved, and no test was weakened — 106 test functions became 134 and 256 assertions became 387. What is left is three labels, one sentence, one coverage gap now closed, and one pre-existing cache policy that quietly makes evidence packs unverifiable a day after they are written.
