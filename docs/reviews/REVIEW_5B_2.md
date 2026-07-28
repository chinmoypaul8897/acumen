# REVIEW_5B_2 — chunk 5B RE-REVIEW (the FIX-5 commit, `7943ce6`)

**Review type:** QC — `personas/quant_reviewer.md` AND `personas/code_reviewer.md`, both in full.
**Span:** the FIX-5 commit ONLY — `88546cb..7943ce6` — judged against `docs/reviews/REVIEW_5B.md`'s
FAIL and its twenty-two findings, and against the architect's Q-14 ruling and its closing DoD
addendum in QUESTIONS.md.
**Session:** fresh re-reviewer, zero shared context with the builder. Read-only on `src/`, `docs/`
and every store; **offline throughout** — no `--allow-network`, no credentialed call, no candle
fetched. The only writes this session made are its own: the architect-authorized Q-14 addendum in
QUESTIONS.md, `tests/test_review5b2_probes.py`, this file, PROGRESS.md and STATUS.md.

---

## VERDICT: **PASS**

The Q-14 ruling is executed clause by clause, and the numbers it produced survive an independent
re-derivation that imports nothing from `src/acumen`:

- **the gate-1P partition reproduces to the day, on all 210 symbols.** I folded every parquet in the
  minute store, joined it to the raw bhavcopy under the Q-4 series whitelist, and applied my own
  integer-arithmetic containment test: **434,769 stored symbol-days, 424,370 pass, 10,399 fail =
  3,096 above / 7,125 below / 178 no-oracle** — identical to the ledger on the grand totals and on
  every one of the five counters for **all 210 symbols, zero mismatches**;
- **every wrong-scale day REVIEW_5B named by date is now excluded**, and the one the recovery pass
  claimed to repair is repaired to the paisa;
- **the cluster signature reproduces exactly** on both symbols that admitted an event, including the
  55%-vs-step distinction B146 was recorded for;
- **the coverage arithmetic reproduces on all seven readings**, and reading G's 1,341-day shortfall
  is exactly right;
- **the recovery pass is offline by construction** — proved by AST over real bindings, not by
  grep — and its one rejection was refused for the reason recorded;
- the suite is green from a genuinely clean state, no test was weakened, deleted, skipped or
  edited, and no fixture was touched.

The definition of done is **NOT MET at 94.6917%** and the architect has formally ACCEPTED that
shortfall in the closing addendum to Q-14. That acceptance is what this review closes the chunk on;
the shortfall is not a defect of this commit, it is the price the commit made visible.

Eleven findings follow — **two LOW on the quant side, two LOW and six INFO on the code side**. None
blocks. The two quant LOWs are a disclosure that is still inaccurate in two places, and a
per-side-floor conflation whose measured cost is 0.0012% of one symbol's volume on 135 days and
which cannot, by the acceptance guard's own construction, let a wrong day pass a gate.

---

## 1. What this review did

- **Reran the entire suite from a clean state** (`.pytest_cache` and every `__pycache__` deleted
  first): **1306 passed / 0 failed** in 168s, matching the FIX-5 claim exactly. Re-ran with this
  session's ten new probes: **1316 passed / 0 failed**.
- Read CLAUDE.md, both personas, REVIEW_5B in full, the Q-14 ruling and its `EXECUTED by` notes, the
  append-only C7/C8 execution-note corrections, the FIX-5 PROGRESS entry with decisions B141–B153
  and the freeze statement, the chunk-5B card, CONTEXT §4.5/§7-E3/§7-E11, and
  `docs/backfill_minute_report.md` in full.
- **Re-derived every load-bearing number independently.** The gate-1P sweep, the coverage readings,
  the cluster prefix, the floor totals, the un-provable counts and the residual-register rows were
  all computed from the parquet stores, the ledger and the committed maps by code that imports
  nothing from `src/acumen`.
- **Attacked the gate** with the shapes the FIX-5 suite did not carry, and kept them:
  `tests/test_review5b2_probes.py` (10 tests).

---

## 2. PART 0 — the architect-authorized append

The architect's closing ruling on the chunk-5B definition of done was appended verbatim to
QUESTIONS.md as a closing addendum to Q-14, in the same blockquote form every ruling in this chain
carries, and with nothing else added to the file. The precedent is the ops session's authorized
CLAUDE.md append. Nothing in the ruling's text was paraphrased, reordered or summarised.

---

## 3. GATE 1P versus the ruling, clause by clause (directed check 1)

| Ruling clause | Code | Verdict |
|---|---|---|
| fold `[low, high]` must sit **INSIDE** the raw `[daily_low, daily_high]` | `quality_gates.price_containment_gate`: `high_excess = (minute_high − raw_high) − limit`, `low_excess = (raw_low − minute_low) − limit`, both clamped at 0 | **PASS** — containment, correct direction, per side |
| tolerance `max(2 paise, 0.1% of the raw price)` **per side** | `price_containment_limit(raw)` evaluated separately against `raw_high` and `raw_low` | **PASS** |
| the tolerance **single-sourced** | `PRICE_CONTAINMENT_MIN_PAISE` / `PRICE_CONTAINMENT_REL` / `price_containment_limit` are defined once in `quality_gates` and IMPORTED by `vendor_adjustment` (`:93-97`), whose `DEFAULT_PRICE_CONTAINMENT_PAISE` and `_PRICE_CONTAINMENT_REL` are aliases (`is`-identity, pinned by a test) | **PASS** |
| a day with **no raw daily row FAILS** | the `raw_high is None or raw_low is None` branch returns `passed=False`, `cause=GATE1P_NO_ORACLE`; a non-positive raw row takes the same branch | **PASS** |
| **excluded AND counted under its own reason** (CONTEXT §7-E3) | `REASON_GATE1P` is a distinct row in the exclusion table; `gate1p_above/below/no_oracle` are separate ledger fields; `gate1_pass` is never touched by a 1P failure | **PASS** |
| **wired everywhere gate 1 runs** | `price_containment_gate` has exactly three call sites: `universe_backfill.gate_symbol` (the single gating loop, reached from `process_symbol` at ingest, `regate_universe` at re-gate, `reroute_quarantined_to_map` and `run_floor_pass`), `price_recovery.judge_day` (the dry run) and `vendor_adjustment.classify_stored_price_day` (the classifier). The report renders from the ledger `gate_symbol` fills | **PASS** |

Its **18 tests pass** (`tests/test_fix5_gate1p.py`, 1.3s).

### 3.1 The attacks

**(a) A wrong scale where ONE end lands inside by coincidence.** The ruling's claim is that a scale
moves both ends the same way, so one always escapes the interval. I built the hard case in both
directions — a day whose raw interval is much wider than its continuous fold, so the end that
normally catches the error is swallowed:

| Attack | Fold (scaled) | Raw | Escaping end | Gate |
|---|---|---|---|---|
| 0.667× with a block print at the top | `[7337, 8004]` | `[10000, 20000]` | HIGH is inside (8004 < 20000) | **FAIL — below**, low excess > 0 |
| 1.417× with a deep auction low | `[25506, 26923]` | `[10000, 20000]` | LOW is inside (25506 > 10000) | **FAIL — above**, high excess > 0 |

In both the surviving end fails and the failure carries the right cause. Kept as
`test_a_wrong_scale_hiding_on_the_high_end_still_fails_on_the_low_end` and its mirror.

**(b) A day exactly AT both bounds.** With raw `[99000, 100000]` (tolerances 99 and 100 paise), the
fold `[98901, 100100]` — at the limit on *both* sides at once — PASSES with both excesses exactly 0;
one paise past either side fails, and only that side. Kept.

**(c) The blind spot the claim leaves, measured.** Containment cannot see a factor smaller than the
day's own slack between the raw interval and the fold interval: a day is contained for every `f` in
`[(raw_low−tol)/fold_low, (raw_high+tol)/fold_high]`, a window that always contains 1. I measured
that window on **33,031 real gate-1P-PASSING days across 15 symbols**:

| Percentile | Largest factor error that would still be contained |
|---|---|
| p50 | 0.100% |
| p90 | 0.104% |
| p99 | 0.250% |
| p99.9 | 0.702% |
| max | 5.382% |

Only **194 days (0.587%)** could hide the smallest real wrong-chain residual the code documents (the
~0.33% rights ours-vs-vendor gap), **12 days (0.036%)** could hide a 1% error, **2 days (0.006%)** a
5% error and **none** a 10% error. Every corporate-action-scale error — rights not applied ~1.3%,
demerger ~9%, bonus ~50%, a 5:1 split 400% — is outside the window on essentially every day. The
gate's resolution is set by its own tolerance, not by the microstructure, which is the honest reading
of "one always escapes". Pinned as
`test_containment_cannot_see_a_factor_smaller_than_the_days_own_range_slack`.

**(d) The wiring, not just the arithmetic.** Two further probes drive `gate_symbol` itself: a stored
day with no bhavcopy row is counted in `gate1p_total` and NOT in `gate1_total` (the two denominators
differ by exactly the no-oracle days, which is REVIEW_5B finding Q4 closed at the wiring level), and
a day whose volume reconciles perfectly while its price sits at 2× passes gate 1, fails gate 1P and
drops out of `usable_pass` — never folded into gate 1's numerator.

### 3.2 REVIEW_5B's own examples, re-measured from the stores

| Day the review named | Fold | Raw bhavcopy | Ratio | Gate 1P now |
|---|---|---|---|---|
| TATASTEEL 2020-07-28 | `[3528, 3600]` | `[35275, 36000]` | 0.1000× | **FAIL (below)** |
| IOC 2018-04-05 | `[11447, 11610]` | `[17170, 17415]` | 0.6667× | **FAIL (below)** |
| SRF 2016-10-03 | `[887550, 962500]` | `[177510, 192500]` | 5.0000× | **FAIL (above)** |
| RECLTD 2020-08-13 | `[8036, 8325]` | `[10715, 11100]` | 0.7500× | **FAIL (below)** |
| APLAPOLLO 2018-10-01 | `[242380, 256670]` | `[121190, 128335]` | 2.0000× | **FAIL (above)** |
| NMDC 2018-03-27 | `[12000, 12225]` | `[12000, 12225]` | **1.0000×** | **PASS — repaired** |

The five that could not be repaired are excluded and counted; the sixth, which the recovery pass
claimed, is now exact to the paisa. That is the finding-Q1 population, closed.

---

## 4. Recovery discipline (directed check 2)

**(a) The two accepted floors carry full provenance, from the persisted maps.**

| | NMDC 2022-10-27 | GAIL 2022-09-06 |
|---|---|---|
| price floor | 2018-10-12, resolved, **12 probes** | 2018-06-28, resolved, **12 probes** |
| price boundary | last `event-out` **2018-10-11**, first `event-in` **2018-10-12** — adjacent sessions, so the boundary is **uniquely determined** | last `event-out` **2018-06-27**, first `event-in` **2018-06-28** — likewise |
| probe ratios | every `event-out` at 1.41726–1.41743, every `event-in` at 0.99982–1.0 — no interpolation | every `event-out` at exactly 1.5, every `event-in` at 0.99997–1.0 |
| `event_price_factor` | 0.70556776…, whose reciprocal is **1.41730** — the review's own measured NMDC ratio | 0.66666667, reciprocal **1.50000** |
| volume side | **undecided**, `event_volume_factor` = **1.000011930575124349998406075**, 1 probe, note names the reason (the newest probed day is undecided, so there is no floor to find) | floor **2018-06-28**, resolved, **12 probes**, factor 0.66666667 |

Both floors' notes, probe lists, verdicts, `k_in`/`k_out` and per-side fields are on disk. The ledger
claims exactly what the maps carry.

**(b) The BSE 2025-05-23 REJECTION reproduces from the dry-run record.** `BSE.json` carries **no
floors at all** — nothing was committed. The ledger and report section 3f both print the measurement
that was discarded:

> BSE 2025-05-23 · price — (unresolved, 2p) · volume **2017-12-20 (resolved, 13p)** · *REJECTED by
> acceptance: both-gate days would go 2115 → 2115 (gate 1 2116 → 2196); the floor is discarded, not
> applied*

A resolved 13-probe floor that would have moved **80 days into gate 1 and none into usable** was
refused, exactly as decision B148 states, and BSE's `recovery_days_rewritten` is 0. I reproduced the
refusal shape as a kept test: a synthetic symbol whose volume side genuinely RESOLVES at the splice
while its prices are off scale for a reason no event factor explains — `after.gate1 > before.gate1`
and `after.both == before.both`, so `recover_symbol` records `REJECTED by acceptance`, writes
nothing and leaves the committed map floorless
(`test_a_floor_that_buys_gate_1_but_no_usable_day_is_rejected_and_nothing_is_written`). The FIX-5
suite only exercised the refusal through a no-splice store; this is the shape that actually occurred.

**(c) The classifier is store-only — zero credentialed calls (B143), proved by AST.** A name-based
call graph reports a false path here, because `binary_search_floor` takes its classifier as a
PARAMETER and the LIVE searcher has a nested function of the same name. Walking real bindings
instead — every def on the pass, its own body and its own parameter list — **no call to
`SmartApiClient`, `SmartConnect`, `generateSession`, `getCandleData`, `get_candles`, `probe_one_day`,
`fetch_json`, `fetch_binary` or `Credentials` appears anywhere** in `price_recovery.recover_symbol`,
`measure_event_floor`, `predict_counts`, `judge_day`, `stored_days`, `candidate_days`, `rescaled`,
`_merged`, `vendor_adjustment.search_event_floor_stored`, `classify_stored_price_day`,
`classify_stored_volume_day`, `binary_search_floor` or `universe_backfill._recover_one`.
`search_event_floor_stored`'s classifier is a closure over `stored` and `adjustment_map` only, and
`_recover_one` constructs no client and is handed none. `rebuild_symbol_raw_with_map`, the only
writer on the path, is likewise clean. Kept as
`test_no_credentialed_call_is_reachable_from_the_recovery_path`.

**(d) The signature reproduces, including the reason B146 was recorded.** Re-derived from the
repaired store by undoing each committed floor arithmetically (multiply back by
`event_price_factor`), with my own `cluster_prefix`:

| Symbol | Span (previous ex-date → boundary) | Days | Failing pre-repair | Whole-span rate test | STEP |
|---|---|---|---|---|---|
| NMDC | 2018-03-27 → 2019-03-22 | 244 | **135 (55.3%)** | **REFUSE** | **135** |
| GAIL | 2018-03-27 → 2019-07-09 | 316 | **64 (20.3%)** | **REFUSE** | **64** |

Both match the ledger's own admission messages word for word ("the oldest 135 of the 244 stored
days below 2019-03-22", "the oldest 64 of the 316"), and both confirm B146's measured claim: a
whole-span rate test would have admitted **nothing** on either symbol. The floors' reach is bounded
by their eras — NMDC's era holds 244 days of which 135 sit below the floor, which is exactly
`recovery_days_rewritten = 135`; GAIL's 64 likewise. 135 + 64 = the 199 repaired days claimed.

---

## 5. Coverage, recomputed from the ledger (directed check 3)

Recomputed with my own code from `data/universe_backfill/ledger.json` (204 settled / 6 quarantined):

| Reading | Numerator | Denominator | Coverage | DoD |
|---|---|---|---|---|
| A gate 1 effective, gated denominator | 413,978 | 434,591 | **95.2569%** | MET |
| B gate 1 strict, no relief | 413,546 | 434,591 | **95.1575%** | MET |
| C gate 1 AND gate 2, overlap-aware | 413,801 | 434,591 | **95.2162%** | MET |
| D the naive subtraction (finding Q3, printed only as the correction) | 412,787 | 434,591 | **94.9829%** | NOT MET |
| E gate 1 effective, stored-day denominator | 413,978 | 434,769 | **95.2179%** | MET |
| F gate 1 AND gate 2, stored-day denominator | 413,801 | 434,769 | **95.1772%** | MET |
| **G gate 1 AND gate 2 AND gate 1P, stored-day denominator** | **411,690** | **434,769** | **94.6917%** | **NOT MET** |

All seven match the report and PROGRESS **to the digit**.

- **Gate-1P partition.** 434,769 = 424,370 + 10,399, and 10,399 = 3,096 + 7,125 + 178. Both hold
  exactly, and my independent full-universe sweep produced the same five numbers **and the same five
  numbers per symbol for all 210 symbols, with zero mismatches**.
- **The shortfall.** 95% of 434,769 is 413,030.55, so 413,031 passing days are needed; 413,031 −
  411,690 = **1,341**. Confirmed.
- **The 178 no-oracle days.** `gate1p_total − gate1_total` = 434,769 − 434,591 = 178, split 173
  settled / 5 quarantined. Every stored day now sits in exactly one bucket.
- **The +64 / +66 deltas against REVIEW_5B.** Diffing the FIX-4 and FIX-5 reports row by row, exactly
  **one** symbol's gate-1 counts changed: **GAIL, 1,990 → 2,054 strict (+64)**; relief, gate-2
  exclusions and every other symbol's row are byte-identical (ASTRAL, NESTLEIND, NMDC and GAIL gained
  a `Floors` claim, which is finding Q5's closure). So the +64 is **GAIL alone** — NMDC's floor moved
  the PRICE chain, which moves gate 1P and reading G, not gate 1. The **+66** on reading C is +64
  plus **2 days that were never a recovery effect**: REVIEW_5B computed C as 413,914 − 179, assuming
  all 179 non-missing gate-2 exclusions land on gate-1-PASSING days, while the runner's per-day
  intersection measures **177** (settled gate-2 breakdown: 1,012 missing + 181 negative + 2 OHLC =
  1,191; 413,978 − 413,801 = 177). The report's own Q3 correction of 1,014 days is the same fact from
  the other side and is right. Recorded as finding Q4 below — the arithmetic is correct, the
  attribution in PROGRESS is not quite.

---

## 6. The punch list, verified against its finding (directed check 4)

| Finding | Claim | Verified how | Verdict |
|---|---|---|---|
| **Q1 (the FAIL)** | gate 1P in the battery, days excluded + counted | §3 above; every named example day re-measured from the stores | **CLOSED** |
| **Q2** tolerance named accurately | "named as max(2 paise, 0.1%) wherever it is described" | grep over live `src/` + `docs/` | **CLOSED WITH RESIDUE** — 2 live sites remain, finding Q1 below |
| **Q3** both-gates counted per day | `gate_symbol` counts `gate1_and_gate2_pass` and `usable_pass` per day; reading D printed only as the correction; the difference is 1,014 | recomputed: 413,801 vs 412,787 = 1,014 ✔ | **CLOSED** |
| **Q4** 178 ungated days | now in gate 1P's denominator and FAILED under `GATE1P_NO_ORACLE` | independent sweep: 178, and `gate1p_total − gate1_total` = 178 | **CLOSED** |
| **Q5** floor claims re-derived from the MAP | ASTRAL and NESTLEIND claim their in-force floors; totals 14 floors / 172 probes | walked all 97 maps: **14 events carry a resolved floor** (15 resolved sides — GAIL holds both), ledger `floors_resolved` sums to **14** across 13 symbols, `floor_ex_dates` populated; ASTRAL 2023-03-14 → 2021-03-08 and NESTLEIND 2024-01-05 → 2021-12-31 both claimed and both printed in report 3c | **CLOSED** (probe-count caveat: finding C3) |
| **Q6** un-provable days measured from the map | 300 → 25,366 across 30 symbols | ledger: **25,366 across exactly 30 symbols** (20,212 settled / 5,154 quarantined, 24 settled symbols). HINDZINC, the review's counter-example, now records 1,678 | **CLOSED** (scope-label caveat: finding C4) |
| **B127 → B152** | the widening recorded as a Class-B decision | B152's text matches `carry_floors_forward` exactly — two extra keep branches, `after is None` and `after[0] == _ONE` | **CLOSED** |
| **C1** | `run_floor_pass` acceptance orchestration executed by a test | `test_c1_the_floor_passes_acceptance_orchestration_is_executed` + the round-composition test | **CLOSED** |
| **C2** | `gate_symbol` driven into the relief branch | `test_c2_gate_symbol_drives_the_auction_relief_branch` asserts `gate1_relieved == 1` and that the strict count is untouched | **CLOSED** |
| **C3** | the NOT-MET branch and its shortfall rendered | `test_c3_the_dod_not_met_branch_and_its_shortfall_are_rendered` | **CLOSED** |
| **C4** | `persist_map` through `atomic_io`, ast-pinned | `persist_map` is now `atomic_write_text`; `load_map` catches `ValueError`, which `json.JSONDecodeError` subclasses; `test_c4_persist_map_is_atomic_and_a_torn_map_raises_instead_of_crashing` pins both | **CLOSED** |
| **C5** | rebuilds arbitrate WITH the measured floors | `build_map_for` falls back to the previous map's own resolved floors when the caller passes none, with the reason in the docstring; tested | **CLOSED** |
| **C6** | the operator CLI carries floors forward | `build_adjustment_map.run` loads the previous map, passes its in-force floors into `build_map`, then `carry_floors_forward`, and prints what it carried and what it dropped; tested | **CLOSED** |
| **C7 / C8** | append-only execution-note corrections | present under a dated `APPEND-ONLY` heading; the original notes are left standing, and both corrections also disclose the FOURTH arm Q-14 adds | **CLOSED** |
| **C9** | relief numerator/denominator named apart | report 3d now prints 435 across all symbols AND 432 on settled with its own denominator, and explains the three-day gap | **CLOSED** |
| **C10** | blank `floor_discipline` | zero hunted rows carry a blank; three legacy rows carry the explicit `(unmarked: hunted under the FIX-3 provable-era discipline, B123)` marker | **CLOSED** |
| **C12** | dead-code attribution | the comment now names `_stored_day_is_raw` as having no `src/` caller and cites C12 | **CLOSED** |
| **C13** | one same-domain predicate | `same_price_domain` shared by the signature gate and the report classifier; pinned by `test_c13_the_same_domain_predicate_is_written_once` | **CLOSED** |
| **C14** | half-step docstring | `gate3_signature_events` now says HALF-steps and shows both for ASTRAL and COCHINSHIP | **CLOSED** |
| **C15** | avg min/day | the column is renamed "Avg stored bars/day" beside "Median traded min/day", with the difference explained | **CLOSED** |
| **C16** | report-only constants recorded | B144 (`QUARANTINE_GATE1_MIN_PASS_RATE`) and B145 (`_CLUSTER_RATE`, `_SCATTER_RATE`, `PATTERN_MIXED`) | **CLOSED** |
| **C11** | `(unreviewed)` suffix | the FIX-5 commit omits it too | **OPEN** — finding C5 below (INFO, the same class REVIEW_5A recorded as F4) |

---

## 7. The disclosed-residual register (directed check 5)

Spot-verified from the stores with my own arithmetic. Every row I checked reproduces **exactly** —
count, and the above/below/no-oracle split:

| Row | Register | My independent sweep |
|---|---|---|
| IOC (below-side) | 1,412 = 1 / 1,410 / 1 | **1,412 = 1 / 1,410 / 1** ✔ — e.g. 2016-10-04 fold `[15150, 15449]` vs raw `[60600, 61795]`, 0.2500× |
| SRF (above-side) | 218 = 216 / 1 / 1 | **218 = 216 / 1 / 1** ✔ — e.g. 2016-10-03 fold `[887550, 962500]` vs raw `[177510, 192500]`, 5.0000× |
| APLAPOLLO (no-oracle) | 47 = 45 / 0 / **2** | **47 = 45 / 0 / 2** ✔ — the 2 are 2026-07-27 and 2026-07-28, both with `raw = None` |
| TATASTEEL | 832 = 0 / 831 / 1 | **832 = 0 / 831 / 1** ✔ |
| BSE | 219 = 81 / 138 / 0 | **219 = 81 / 138 / 0** ✔ |
| NMDC / GAIL | 372 = 2/369/1 · 370 = 0/369/1 | **identical** ✔ |

The register is generated, not written: `--report-only` to a scratch path reproduces
`docs/backfill_minute_report.md` **byte-identically apart from the generation timestamp and the
today's-date scope line**, makes no network call, and leaves `git status --porcelain` clean. So what
chunk 9 will read is derived from the ledger and the stores, and cannot have been hand-tuned. One
qualification on *how* chunk 9 can carry it is finding C1 below.

---

## 8. The freeze (directed check 6)

- **The statement is present in both places.** QUESTIONS.md's Q-14 execution note ends "**The data
  era is FROZEN.**"; the PROGRESS entry's `questions:` field says the ruling's closing sentence is
  honoured and the era is FROZEN.
- **Nothing auto-runs.** The recovery pass is reachable only through
  `universe_backfill.run → regate_universe(recover=args.recover_prices) → _recover_one`, and
  `--recover-prices` is an explicit opt-in flag documented as "Licensed to run ONCE". `--regate`
  alone re-gates without recovering. The live FIX-4 hunt (`run_floor_pass`) sits behind
  `floor_hunt_owed → floor_hunt_in_scope` and behind the one-shot `FLOOR_DISCIPLINE` marker, and the
  whole fetching arm of `run` refuses without `--allow-network`, which the `--regate` /
  `--recover-prices` branch returns before reaching. The hunt paths remain — which is what makes the
  measurement reproducible — and none of them fires by itself.
- **Nothing was left half-applied.** A rejected floor is never written (BSE carries no floors), and
  the dry run is evaluated before any write.

---

## 9. Standards (directed check 7)

- **Tests.** 1306 passed / 0 failed from clean; 1316 with this session's probes. `git diff
  88546cb..7943ce6 -- tests/` shows **two new files and nothing else** — FIX-5 edited **no existing
  test**, so the directed check's "three updated assertions" has no subject in this span: there are
  none. No test was deleted, renamed, skipped or `xfail`ed anywhere in the suite (zero occurrences).
  1253 inherited + 53 new = 1306, which is the claimed arithmetic. The two contract markers that
  moved (`GATE_DEFINITION`, `FLOOR_DISCIPLINE`) are asserted through the constants and the
  stale-row path is covered by
  `test_needs_reprocessing_flags_a_pre_ruling_row_and_clears_after_the_pass`.
- **Fixtures.** `git diff 88546cb..7943ce6 -- tests/fixtures poc` is **empty**. CONTEXT.md and
  plan.md are untouched.
- **Commit hygiene.** One commit, `chunk5B-fix5:`-prefixed, a logical unit, with a WHAT/WHY body that
  cites the ruling it executes and states its test count. Authored and committed by
  `chinmoy-paul <chinmoypaul8897@gmail.com>`. It omits `(unreviewed)` (finding C5).
- **Secrets.** No `.env` value, credential-shaped string or token anywhere in the diff, the report,
  QUESTIONS.md or PROGRESS.md. The recovery pass cannot even construct a client (§4c).
- **No AI attribution** in any commit message, trailer or tracked file.
- **SHA chain.** `main` and `origin/main` agree at `7943ce6`. Tags run `chunk0-pass` … `chunk5A-pass`,
  `chunk6-pass`, with no `chunk5B-pass` — consistent with STATUS.md before this review.

---

## 10. Class-B sweep — B141 through B153

**APPROVED (13 of 13).**

- **B141** (containment, not equality) — the ruling's own words, and the asymmetry is real: the
  exchange's daily extremes are maxima/minima over every trade including auction and block prints the
  continuous series never held. Measured: the equality reading would fail HDFCBANK-shaped auction
  days wholesale. The claim "a wrong scale moves both ends the same way, so one always escapes" is
  verified in both directions and its residual is bounded at §3.1(c).
- **B142** (gate 1P's denominator is every stored day; no raw row FAILS) — the ruling says so in as
  many words, and it is what makes every stored day sit in exactly one bucket. Verified: 434,769
  gated, 178 no-oracle, `gate1p_total − gate1_total` = 178.
- **B143** (the classifier reads the STORE) — proved offline by AST over real bindings (§4c). The
  arithmetic is exact rather than approximate: `stored = fetched / k_applied`, so `event-in` IS gate
  1P and `event-out` is the same test after multiplying back. It also makes the measurement
  reproducible by anyone holding the two stores, which a live probe never is.
- **B144 / B145** (the 80% quarantine floor; `_CLUSTER_RATE`, `_SCATTER_RATE`, `PATTERN_MIXED`
  recorded as this repo's choices) — the honest correction of C16; nothing downstream consumes them.
- **B146** (the cluster is a STEP, not a whole-span rate) — the strongest of the thirteen, and the
  one I attacked hardest. Reproduced independently: a whole-span rate test **REFUSES both** symbols
  (NMDC 55.3%, GAIL 20.3%) while the step measures 135 and 64. The prefix rule ends on a failing day
  and requires a clean remainder, so it cannot swallow the clean block above it, and it degenerates
  to exactly the FIX-4 cliff when the whole span fails. The recorded "133" is off by two from the
  measurement (finding Q3).
- **B147** (a cluster is an ERA property, a floor an EVENT property, so candidates are the era's own
  committed chain) — correct and conservative: `gate1p_recovery_events` refuses an un-provable era
  outright, and events committed absent on both sides are skipped. NMDC admitted two candidates and
  the bisection answered "no splice" for the wrong one, which is the design working.
- **B148** (dry-run, greedy acceptance) — the guard that makes the whole pass safe: a floor is
  committed only if MORE days pass BOTH gates and no fewer pass gate 1. Verified on its refusal side
  against the real BSE case and against a new synthetic that resolves a floor and is still refused.
- **B149** (quarantine still reads gate 1 alone; gate 1P added to the hunt scope) — the ruling
  excludes DAYS and says nothing about symbols, so changing the trigger would have been a silent
  decision. Approved; its visible consequence is recorded as finding C6.
- **B150** (floor claims re-derived from the MAP on every re-gate) — makes the claim/evidence
  invariant true by construction and preserves `floor_ex_dates`. Verified: the ledger's 14 claims and
  the maps' 14 resolved-floor events agree exactly.
- **B151** (committing a fresh floor MERGES with the map's existing floors) — necessary; without it
  the Q-14 pass would have dropped GAIL's and NMDC's FIX-3/FIX-4 floors. `_merged` keys by event and
  lets the fresh measurement win, which is right because it was measured against the store as it
  stands.
- **B152** (B127's widening, recorded) — text matches code exactly; in both extra keep branches
  dropping the event from a day's chain is the identity, so the carry cannot alter one stored price.
- **B153** (the tolerance defined once; one `same_price_domain`) — verified by import and by an
  `is`-identity test.
- **The disclosed OPERATOR ACTION** (re-deriving every ledger row's floor CLAIMS from its committed
  map after the run, five rows changed) — a derived-index maintenance pass through the same code path
  the runner now uses, asserting no result and re-running no gate. The map is the authority and this
  only made the index agree with it. Disclosed, correct, approved.

---

## 11. FINDINGS

### Quant reviewer

**Q1 — LOW — REVIEW_5B's finding Q2 is closed in prose but two live sites still say "2-paise
containment".** *Spec: none — accuracy of disclosure.* The FIX-5 commit body and PROGRESS claim "the
tolerance is named as max(2 paise, 0.1%) wherever it is described". Two places that are regenerated
or read as current still describe it as a flat 2 paise:

- `src/acumen/vendor_adjustment.py:1252` — `build_map`'s own docstring: "The price oracle is 2-paise
  containment vs the raw daily high/low";
- `docs/backfill_minute_report.md:1499` (section 3e) — "every era it touches must satisfy the same
  2-paise per-day price containment".

Section 3c of the same report states it correctly and at length, so the document contradicts itself
one section later. Historical PROGRESS and STATUS entries are append-only and correctly left alone.
No behaviour is affected — the constant is single-sourced and correct — but the reader the
disclosure exists for is still told the wrong number in a live document.

**Q2 — LOW — an unresolved VOLUME-side search silently inherits the PRICE splice.** *Spec:
QUESTIONS.md Q-14 ("measured by the same bisection under the same guards"); the same-guards clause
includes "one `event-in` or one `undecided` leaves it UNRESOLVED".* `price_recovery.
measure_event_floor` sets `volume_measured=volume_search.resolved`, so a side that WAS searched and
came back UNRESOLVED is recorded identically to one that was never searched. `EventFloor.
applies_on_volume` then takes its backward-compatibility branch and **falls back to the PRICE
floor** — the opposite of what `measure_event_floor`'s own docstring promises ("a side whose search
does not resolve simply carries no floor, and the chain on that side is left exactly as the era
committed it").

Measured on the only case in the frozen era. NMDC's committed floor has `floor_volume=None`,
`volume_resolved=False`, `volume_measured=False`, and its volume search really did run (one probe,
`undecided`, note recorded). Consequence:

| NMDC day | `factors_for_day` with the floor | without it | volume ratio |
|---|---|---|---|
| 2018-10-11 (below the price floor) | `(0.33333333, 0.33333333)` | `(0.23518926, 0.33333731)` | **0.99998807** |

So the event is dropped from the VOLUME chain on the era's 135 sub-floor days too, moving `k_volume`
by **−0.0012%** — three orders of magnitude inside gate 1's `[−0.1%, +5.0%]` band, so no gate verdict
changes and no price is touched. The general failure mode is also benign by construction: a
materially wrong volume chain would *lose* gate-1 days, and B148's acceptance refuses any floor that
does, so this cannot produce a wrong-but-passing day. **Recording and a one-word semantic fix are
what is owed, not a re-measurement** — `volume_measured` should be True whenever a search ran, which
makes `applies_on_volume` return True everywhere (the era's own chain) exactly as intended. Not
changed here: the data era is FROZEN and this is inside a committed map.

**Q3 — INFO — the recorded NMDC step is 133; the measurement is 135.** The generated ledger and
report text say "the oldest **135** of the 244 stored days", and my independent `cluster_prefix`
returns **135**. Three hand-written places say 133: `universe_backfill.py:1312` ("its oldest 133
sessions"), the FIX-5 commit body, and decision B146 in PROGRESS. The argument they make is
unaffected — 135/244 is 55.3%, a whole-span rate test refuses it either way — but a recorded
measurement should be the measurement.

**Q4 — INFO — the "+64/+66" is attributed entirely to the GAIL+NMDC repairs; two of the 66 are
something else.** Diffing FIX-4's report against FIX-5's, exactly one symbol's gate-1 counts moved:
**GAIL, +64**. NMDC's floor moved the PRICE chain, so it shows in gate 1P and reading G, not in
readings A–F. Reading C's +66 is that +64 plus **2 days that come from correcting REVIEW_5B's own
approximation** — the review computed C as 413,914 − 179 by assuming all 179 non-missing gate-2
exclusions fall on gate-1-passing days, while the runner's per-day intersection measures 177. The
report's arithmetic is right (its Q3 correction of 1,014 days is the same fact); PROGRESS's sentence
"they AGREE with the review to the day once the recovery's +64/+66 is accounted for" over-attributes.

**Q5 — INFO — "197 moved into usable" is the dry run's number, not the ledger's.** The predictor's
"both" is gate 1 ∧ gate 1P (the ruling's two per-day gates); "usable" in the report is gate 1 ∧ gate
2 ∧ gate 1P. NMDC's predicted 2,050 against the ledger's authoritative `usable_pass` 2,049 differ by
exactly one day that gate 2 excludes — fully explained, and the predictor's own docstring discloses
that it does not model gate 2. The 197 is correct for what it measures; the word "usable" is the
report's name for a different quantity.

### Code reviewer

**C1 — LOW — no artifact identifies the excluded days one by one.** *Spec: the architect's closing
Q-14 addendum, "every excluded day is categorized in the residual register chunk 9 carries".* The
register (report 3f) is **per symbol**: counts, the above/below/no-oracle split, the worst excess and
a measured reason. The ledger persists only `gate1p_failure_dates = [...][:10]`
(`universe_backfill.py:602`) — ten sample dates per symbol — and there is no exclusions file
anywhere under `data/universe_backfill/`. Chunk 9 therefore cannot read a list of the 10,399 days;
it must recompute gate 1P per day. That recomputation is exact and cheap (the gate is PURE, both
sides are local, and `gate_symbol` already does it), so nothing is lost or unsafe — but "categorized"
is satisfied at the symbol level, not the day level, and the chunk-9 session should be told to call
`price_containment_gate` rather than to look for a list.

**C2 — LOW — all 178 "no raw daily row" failures are the daily store's own lag, and the register
does not say so.** The daily store's last ingested session is **2026-07-24**; the minute store holds
2026-07-25, 2026-07-27 and 2026-07-28. Counting stored minute days past 2026-07-24 across all 210
symbols gives **exactly 178** (1 + 173 + 4), over 173 symbols — i.e. **not one** of the no-oracle days
is a historical hole. The register describes them as days that "have no bhavcopy row at all and
cannot be price-proven either way", which is true and is the ruling's own treatment, but an architect
reading it would reasonably take them for damage. They are 178 of the 1,341-day shortfall (13.3%),
and they are clearable by a bhavcopy ingest that touches no minute candle, no map and no factor —
i.e. by work outside the frozen minute-data era. Disclosure, not correctness.

**C3 — INFO — the headline's "14 floors over 172 probes" pairs a map-derived count with a
pass-derived one.** B150 correctly re-derives the floor CLAIMS from the map; `floor_probes_spent` is
still whatever the row's own hunt spent. The maps carry **144 probes** behind the 15 resolved floor
sides, while the ledger sums **172** (which also counts probes spent on unresolved and rejected
searches). The mismatch is visible per row: ASTRAL claims a 12-probe floor with `floor_probes_spent
= 2`, NESTLEIND a 12-probe floor with `0`. Both numbers are meaningful; the headline reads as though
172 is the evidence behind the 14.

**C4 — INFO — the headline's un-provable row is settled-only and unlabelled.** The report prints
"Un-provable days (no map era / unknown factor) | 20,212" while PROGRESS and STATUS publish "25,366
across 30 symbols". Both are right — 20,212 settled + 5,154 quarantined = 25,366 — and the
surrounding table is settled-scoped, but this row does not say so where the row above it does.

**C5 — INFO — the FIX-5 commit omits the `(unreviewed)` suffix.** The same class REVIEW_5B recorded
as C11 and REVIEW_5A as F4.

**C6 — INFO — two SETTLED symbols now sit far below the quarantine floor on gate 1P.** A consequence
of B149 (approved), recorded so the architect sees it: **IOC at 1,020/2,432 = 41.9%** and
**TATASTEEL at 1,600/2,432 = 65.8%** are `settled`, because quarantine reads the gate-1 volume rate
alone (84.8% and 85.8%). Their days are individually excluded by gate 1P, so nothing wrong reaches
chunk 9 — but chunk 9 will backtest those two symbols on a minority of their stored history,
concentrated in recent years, and any per-symbol statistic it computes should be read against the
register rather than against the symbol's nominal depth.

---

## 12. Scope of this review

No file under review was modified. No fixture was touched — `git diff 88546cb..7943ce6 --
tests/fixtures poc` is empty and the working tree matches its committed blobs. CONTEXT.md, plan.md
and `poc/` are untouched. Every store access was read-only; the report regeneration went to a
scratch path outside the repo and `docs/backfill_minute_report.md` was never rewritten. **No network
call was made at any point**, and no credentialed call is even reachable from anything this session
ran. This session's own writes are: the architect-authorized Q-14 closing addendum in QUESTIONS.md,
`tests/test_review5b2_probes.py` (10 kept probes), this review, the PROGRESS entry and the STATUS
line.
