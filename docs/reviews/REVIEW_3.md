# REVIEW_3 — chunk 3 · Corporate-action engine

**Reviewer:** fresh QC review session — `personas/quant_reviewer.md` **and**
`personas/code_reviewer.md` (plan.md chunk 3 review type **QC**). Zero shared context with the
builder.
**Date:** 2026-07-25 · **Span reviewed:** `b085f07..4f4f94d` (the chunk-3-prep commit that
recorded+executed the Q-4/Q-5 rulings and applied the scheduled REVIEW_2 fixes, plus the four
chunk-3 build commits — everything after tag `chunk2-pass`).
**Builder entry reviewed:** PROGRESS.md `[2026-07-25 00:45] chunk 3 · build · done`.

## VERDICT: **PASS**

I assumed the financial math was wrong until it proved otherwise, and it proved otherwise. I
opened NSE's calculator XLSX myself with `openpyxl` and recomputed our `k` against **every**
worked cell of its BONUS/SPLIT/RIGHTS sheets; I recomputed the five parser events by hand from
the raw snapshot bytes; I recomputed the three adjustment gaps and the whole cross-source
partition from the frozen files with code that shares nothing with the module it grades; I
mutation-tested the Indian bonus convention and twenty other spec/discipline invariants in a
throwaway copy. The engine reproduces CONTEXT 4.2 to the last digit the oracle holds, refuses
to guess a factor it lacks a price for (Q-6/Q-7), never lets a debt-series row touch the
equity, and blocks a demerger from ever becoming a number.

**Full suite: 674 passed / 0 failed** from a clean state (`.pytest_cache` and every
`__pycache__` deleted first), fully offline — **668 from the build** (matching the builder's
claim exactly) plus **6 reviewer probes** I added. `git status` was clean at review start; the
only working-tree change I introduce is `tests/test_review3_probes.py`. **No file under review
was modified. No fixture was touched.**

Findings: **one LOW (a test-coverage gap I closed with a kept test), three INFO.** None is a
FAIL trigger; none blocks chunk 4. The chunk's two deliberate non-features — rights and
dividend factors left unbuildable until Q-6/Q-7 are ruled — are the STOP rule working, and I
confirmed by AST and by exhaustive count that no `k = 1` default hides on those paths.

---

## 1. Architect's directed checks

| # | Check | Result |
|---|---|---|
| 1 | Prep Q-4/Q-5 rulings verbatim + BEFORE code; Q-4 whitelist clause-by-clause; Q-5 = F11's case; re-attack M-F1 (4s pacing) and M-F2 (HTML-behind-200 on binary) | **PASS** — §2, §3 |
| 2 | Open the XLSX myself (openpyxl); recompute k against every worked cell; verify k=1/AF (bonus/split) vs k=AF (rights) from the sheets | **PASS** — §4 |
| 3 | Recompute the five parser events by hand from the frozen snapshots | **PASS** — §5 |
| 4 | Adjustment sanity: three gaps from the DERIVED cuts; adjust_pair chaining; B46 single half-even rounding; QUANT inequality preservation | **PASS (one nuance → Finding 2)** — §6 |
| 5 | Indian-convention mutant: flip bonus to US k=B/A; count catchers (≥3) | **PASS — 13 catch it** — §7 |
| 6 | Join: kind-aware ROTO + MAANALU; 27/282/24/0 partition; 22/22 BSE, 3/3 Yahoo | **PASS** — §8 |
| 7 | Q-6/Q-7 discipline: no rights w/o S, no dividend w/o class ever produced a factor; 296/328 pending with reasons; grep+AST no k=1 default | **PASS** — §9 |
| 8 | Series filter (B45): a debt-series row can never attach an event to the equity | **PASS** — §10 |
| 9 | Scratch-store discipline: no code path writes `data/daily_store` | **PASS** — §11 |
| 10 | Judge B35–B52 explicitly, one line each | **Done** — §12 |
| 11 | Fixtures: all pinned digests intact; tree clean; the rewritten tests name their defect, none silently deleted | **PASS** — §13 |

**Disclosure.** This review issued **no network traffic.** Every probe read the frozen
snapshots or a fake session on a virtual clock. `openpyxl` was installed into the review's
own scratchpad (`--target`), never into the operator's environment — `python -c "import
openpyxl"` still fails in the operator's interpreter, confirmed.

## 2. Prep discipline — rulings recorded verbatim, BEFORE any code

`git show b085f07` (the prep commit) touches `QUESTIONS.md`, `src/acumen/{backfill_daily,
bhavcopy,calendar,daily_store,nse_http}.py`, tests, and the REVIEW_2 fix log — and **zero
lines of `corp_actions.py`** (it did not exist yet; grep for `corp_action` in the commit
returns 0). So both rulings were written into QUESTIONS.md as the architect relayed them, and
the REVIEW_2 fixes landed, in a commit that strictly precedes any corporate-action code. The
Q-4 and Q-5 ruling texts in QUESTIONS.md are the architect's verbatim blocks (opening
`"ARCHITECT'S RULING: ..."`), unedited. Nothing was coded around Q-6/Q-7: they are RAISED,
open, and every affected factor is `pending` (§9).

## 3. Re-attacking the two REVIEW_2 MEDIUMs myself (M-F1, M-F2)

On a virtual clock with a fake session, so every wire gap is measured, not argued:

**M-F1 — the cookie warm-up now honours the caller's `min_interval`.** With a caller interval
of **4.0s** and a 403 that triggers the home-page warm-up, the three requests land at
t=1000, **1004**, 1008 — the warm-up waited the full 4.0s, not the old 0.5s. Re-tested at 2.0s
and 10.0s too; every wire gap ≥ the caller's interval in all three, warm-up fires exactly
once. REVIEW_2 F1 is genuinely closed.

**M-F2 — a bot-shield HTML page behind HTTP 200 is now retried on the BINARY path.** With an
identical `<!DOCTYPE html>…Access Denied…` body and `max_attempts=4`, **both** `fetch_json`
and `fetch_binary` now spend all 4 attempts before recording `error` (REVIEW_2 measured 4 vs
1). A non-HTML corrupt body (`PK\x03\x04garbage`) still fails fast on attempt 1 — the ZIP
layer judges it — and a good ZIP is accepted on attempt 1. `looks_like_html` correctly flags
`<!doctype`, `<html`, `<?xml`, `<head` (case- and leading-whitespace-insensitive) and passes a
real ZIP, a CSV and an empty body. REVIEW_2 F2 is genuinely closed. The CA fetchers also
forward a caller-supplied 4.0s interval down to the fetch layer (verified), so B50's slower
pacing is real.

## 4. The F8 oracle, recomputed cell-by-cell (directed check 2)

I loaded `docs/nse_adjustment_calculator.xlsx` with `openpyxl` (independent of the build's
`zipfile`+`ElementTree` reader) and read all three sheets, formulas and cached values.

- **BONUS** (ratio 1:2, AF cell = 1.5): our bonus `k = 2/3` reproduces `MROUND(strike/AF,
  0.05)` on all four option strikes (115→76.65, 105→70) and the future (111.95→74.65), and the
  lot multipliers `G*AF`. **k = 1/AF** confirmed from the sheet's own `=MROUND((E9/B6),0.05)`.
- **SPLIT** (10:1, AF = 10): our `k = 0.2` reproduces every strike (900→90, 920→92) and future
  (913.3→91.35). **k = 1/AF** confirmed.
- **RIGHTS** (17:74 @ S=65 on P=107.10): our `rights_factor` gives
  `0.9265654979940694226408512123`, matching the sheet's AF `0.9265654979940694` to every one
  of the 16 digits it holds. Every strike (`=MROUND(E*B11,0.05)`: 106→98.20, 107→99.15) and
  future (105.9→98.10) reproduced. **k = AF** here, the OPPOSITE direction from bonus/split —
  read straight off the sheet's own `strike * AF` formula, and `1/AF = 1.0793…` would be
  wrong. B51's implicit relation is exactly right and is now confirmed from the sheets, not
  from the build's report.

## 5. The five parser events, by hand from the raw bytes (directed check 3)

Read from the frozen JSON with plain `json`, hand-classified per CONTEXT 4.2, then compared to
the code:

| symbol | subject (verbatim) | my hand answer | engine |
|---|---|---|---|
| KOTHARIPRO | ` Bonus 1:2` | bonus, k = B/(A+B) = **2/3** | 2/3 ✓ |
| GREENPLY | ` Face Value Split … From Rs 5/- … To Re 1/-` | split, k = B/A = **1/5** = 0.2 | 0.2 ✓ |
| JMCPROJECT | ` Rights 2:7` (no price) | rights, **NO factor** — S unknown (Q-6) | raises naming Q-6, `pending` ✓ |
| RELIANCE (2023) | `Demerger` | **NO factor exists** (CONTEXT 4.2) | in demerger table, factor raises ✓ |
| RELIANCE (2024) | `Bonus 1:1` | bonus, k = **1/2** | 0.5 ✓ |

All five match. Note GREENPLY's `faceVal` field in the snapshot is `1` — the POST-split value —
which is exactly the trap Q-6 documents: the parser reads the From/To of the SUBJECT, not the
row's stale `faceVal`, so the split is priced correctly regardless.

## 6. Adjustment sanity, chaining, rounding, inequality (directed check 4)

**The three gaps**, recomputed from the DERIVED bhavcopy cuts with plain `csv`+`Decimal`:

| event | raw gap | adjusted gap | adjust_pair == my hand rounding |
|---|---|---|---|
| KOTHARIPRO bonus 1:2, ex 2016-01-05 | **−32.44%** | **+1.34%** | 35540 → 23693 ✓ |
| GREENPLY FV 5→1, ex 2016-01-06 | **−79.63%** | **+1.85%** | 98525 → 19705 ✓ |
| RELIANCE bonus 1:1, ex 2024-10-28 | **−49.76%** | **+0.49%** | 265570 → 132785 ✓ |

Every raw gap is the fake split/bonus jump CONTEXT 4.5-gate-3 targets (>20%); every adjusted
gap is well inside 20%. `factors_between` honours CONTEXT 3.2's half-open `(P, C]` window on a
6-case truth table (ex==C applies, ex==P does not, degenerate pair empty).

**Chaining** on a hand-built two-event case (split k=½ then bonus k=½): 1000.00 → 250.00,
order-independent, and equal to applying one event at a time when exact. `adjust_pair` refuses
a float, a bool, a str, `None`, and a bare `Decimal` in place of a `Factor`; an empty chain
returns the price untouched with no rounding.

**B46 — rounding once, half-even.** I proved the "round once" claim is *load-bearing*, not
cosmetic: for a realistic bonus 1:2 × split 10→4 chain, **65,334** prices in Rs 100–5000
differ between round-once and round-per-event. `adjust_pair` matches round-ONCE on every one.
Half-even is observable too: on exact .5 ties it rounds 1→0, 5→2, 25→12 (half-up would give 1,
3, 13), and cumulative rounding bias over 100k prices is **0 paise half-even vs +25000 paise
half-up** — B46's "does not creep upward" is measurable. *One caveat on test coverage →
Finding 1.*

**QUANT — inequality preservation.** CONTEXT 3.2 claims pairwise adjustment is equivalent to
comparing on a fully adjusted series. In exact arithmetic it is, and across a hand-built
5-candle / 2-event case all eight CONTEXT 3.2 comparison predicates agree between pairwise and
full-series. But once BOTH candles are rounded independently into a common *later* scale, a
knife-edge tie can flip — I found real cases with the rights/dividend factors. This is not a
defect: **CONTEXT 3.2 DEFINES the comparison as pairwise**, and the engine implements exactly
that. → Finding 2 (a note for chunks 4/9, with a kept regression test).

## 7. The Indian-convention mutant (directed check 5)

In a throwaway `git archive` copy I flipped `k = B/(A+B)` four ways. All caught, far above the
"≥3" bar:

| mutant (bonus 1:2 →) | tests that fail |
|---|---|
| **US `k = B/A`** → 2.0 (the architect's named flip) | **13** |
| `k = A/(A+B)` → 1/3 | 11 |
| the AF itself `(A+B)/B` → 1.5 | 13 |
| US split `k = A/B` → 0.5 | 13 |

I then mutation-tested **17 more** spec/discipline invariants (one-line edits, throwaway copy):
split k inverted (12 catch), rights k→1/AF (4), rights E÷A (4), dividend threshold on the cum
close (2), 2% boundary `<`→`<=` (2), **demerger→k=1** (2), **missing rights price→k=1** (4,
Q-6), **missing pre-announcement close→k=1** (2, Q-7), window `(P,C]`→`[P,C)` (3), half-even→
half-up (4), demerger precedence (1), series filter dropped (5), join kind-blind (1),
informational dustbin (1), BSE dash-money regex removed (7), dividend components not summed
(2). **16 of 17 caught.** The one survivor — round-per-event vs round-once — is Finding 1; my
added probe now kills it (verified: 3 of my tests fail on that mutation).

## 8. The cross-source join (directed check 6)

Recomputed from the frozen snapshots. Partition of the **333** comparisons: **agree 27 /
no-factor 282 / not-found 24 / disagree 0** — the architect's `27/282/24/0`. Shared ratios:
**22/22 identical to BSE**, **3/3 identical to Yahoo** (KOTHARIPRO 3:2→2/3, GREENPLY 5:1→0.2,
RELIANCE 2:1→0.5, each equal to the NSE factor as an exact `Decimal`). Zero disagreements
anywhere in three months of data.

**Kind-aware matching (B48).** Straight from the raw 2023-07 JSON: ROTO declares TWO subjects
on 2023-07-07 (a bonus and a dividend) and MAANALU TWO on 2023-07-27 (a bonus and a split).
The join produces two comparison rows per date, each matched to a BSE row of its **own** kind;
none is a false disagreement. A symbol-date-only join (the mutant) calls one of them a
disagreement — caught.

## 9. Q-6/Q-7 discipline — nothing guessed (directed check 7)

Of **328** priced events in the frozen windows, **32** factors are built (15 bonus + 12 split
+ 5 buyback) and **296** are `pending` — **7 rights (Q-6)** + **289 dividends (Q-7)**, every
one carrying its reason string. **Zero** rights factors and **zero** dividend factors were
built without their input prices. `factor_for` on a real rights event with no `S` raises naming
Q-6; on a real dividend with no pre-announcement close raises naming Q-7. The only built `k=1`
values are the 5 buybacks (CONTEXT 4.2's own answer, not a default) and any sub-2% ordinary
dividend when a price IS supplied. AST-checked: the only `Decimal(1)` returns are the ordinary-
dividend and buyback branches. A missing price is never silently `k=1`.

## 10. Series filter — a debt row can never touch the equity (directed check 8)

The frozen windows carry 19 NSE rows on non-equity series (`IV` InvIT, `GS` govt-sec, `RR`
REIT). `parse_actions` (default `instrument_series_only=True`) drops all 19 before parsing; 8
of them WOULD have become factors if parsed (e.g. a SHREMINVIT distribution → k=0.968). In
these windows none of those symbols also trades as an equity, so nothing could have leaked —
but the guard must hold in general, so I built the adversarial case the data lacks: TATASTEEL
(a real F&O equity) with a **debenture-series (N2)** "Bonus 1:1" on one date and its real EQ
split on another. The N2 row is dropped; the only TATASTEEL factor built is the EQ split
(k=0.2); no bonus factor is ever created. Kept as `test_a_debt_series_row_can_never_attach_a_
factor_to_a_real_equity`. This is defense in depth with `daily()`'s Q-4 selection, which
independently returns only EQ/BE/BZ price rows.

## 11. Scratch-store discipline (directed check 9)

No chunk-3 module references a `data/daily_store` write path (`corp_actions.py` and
`ca_report.py` write only to the CA cache under `data/nse/ca`; the CA goldens' adjustment test
writes to a `tempfile.mkdtemp` store). Running the full CA test modules changed the main
store's `ledger.parquet` — **but I proved that is the operator's concurrent backfill, not
chunk-3 code**: the ledger grows ~15 bytes every 2 seconds *with no test running at all* (PID
25236, `backfill_daily.py … --store data\daily_store`, still live from 23:30). The build's own
±10-day adjustment check used a SCRATCH store (`data/ca_check_store`), never the operator's, as
the PROGRESS entry states. No chunk-3 code path writes the main store.

## 12. Class-B decisions B35–B52 — one line each

| # | Judgment | Reason |
|---|---|---|
| B35 | **APPROVE** | Two-whitelist RAISE fires before the EQ/BE/BZ precedence order, so the order never actually decides — verified on the synthetic TWOWHITE case; message names Q-4 and both series. |
| B36 | **APPROVE** | `INSTRUMENT_SERIES` is the ONLY series choice in `src/` (AST walk: 3 constants, all on line 110); families `N*`/`P*`/`BL` matched by family, not enumeration — mutant removing the filter caught 5×. |
| B37 | **APPROVE** | Counting weekends from the ledger keeps `coverage_summary` callable after a Ctrl-C; sound, and orthogonal to correctness. |
| B38 | **APPROVE** | Launcher and packaged module both run nothing on import (`test_importing_either_entry_point_runs_nothing`); F12's import-half closed. |
| B39 | **APPROVE** | `cached_json`'s `fetcher` hook is what lets three sources share one pacing/one-pull-a-day policy; a 4.0s caller interval provably reaches the wire (§3). |
| B40 | **APPROVE** | Demerger parsed first — the costliest miss guarded first; "Scheme Of Arrangement/Bonus 1:2" → demerger; reversing precedence caught. |
| B41 | **APPROVE** | Cash components SUMMED per ex-date — SIEMENS Rs6+Rs4=Rs10 verified across all 12 multi-component subjects; not-summed mutant caught. |
| B42 | **APPROVE** | Informational requires a meeting phrase AND no amount AND no ratio — "AGM/Something Rs 5" raises rather than being binned; dustbin mutant caught. |
| B43 | **APPROVE** | Consolidation priced as a split only with From/To values; bare "Consolidation of Shares" stays an exception; "From Rs 1 To Rs 10" → k=10 verified. |
| B44 | **APPROVE** | BSE `Rs. - 5.5000` dash form accepted — removing it turns 7 tests red (measured 348 BSE dividend rows would become exceptions). |
| B45 | **APPROVE** | Non-instrument series filtered before parsing; adversarial TATASTEEL-N2 case proves a debt row cannot factor the equity (§10). |
| B46 | **APPROVE the decision · CHALLENGE the test coverage** | Round-once, half-even is correct and load-bearing (65k divergent prices; zero cumulative bias) — but the build's chain test used exact intermediates, so a round-per-event regression passed unseen. → **Finding 1**, closed by a kept reviewer test. |
| B47 | **APPROVE** | Rights/dividend factors REQUIRE their prices and raise; `build_factor_table` collects them as `pending` with the reason — 296/328, no k=1 leak (§9). |
| B48 | **APPROVE** | Join matches on KIND as well as symbol-date; ROTO and MAANALU reproduced from raw; kind-blind mutant caught. |
| B49 | **APPROVE** | BSE joined by NAME (it has no ISIN); a miss is `not-found`, never a disagreement — JMCPROJECT verified. |
| B50 | **APPROVE** | 1 req/4s during the build kept the combined rate at the repo's ~1/2s; the fetchers honour a caller-supplied interval, warm-up included (§3). |
| B51 | **APPROVE** | F8 READS the XLSX rather than transcribing it; I reproduced its cell-by-cell read independently and confirmed k=1/AF (bonus/split) vs k=AF (rights) from the sheets (§4). |
| B52 | **APPROVE** | `ca_report` is an offline entry point over the frozen snapshots; `test_the_report_counts_are_the_goldens` pins its numbers. |

## 13. Fixtures & rewritten tests (directed check 11)

**All pinned digests intact**, recomputed independently: 28 `poc/data` CSVs, the 3 chunk-1
frozen files, and the 13 new chunk-3 fixtures (10 VERBATIM CA snapshots + 2 DERIVED bhavcopy
cuts + 1 SYNTHETIC series file) plus the XLSX oracle — **20/20 chunk-1/2/3 files match**,
`test_fixture_integrity.py` green (55). `git status` clean at start. PROVENANCE.md's claims
check out (VERBATIM vs DERIVED vs SYNTHETIC clearly separated; the empty RELIANCE-2023 Yahoo
file correctly framed as evidence that a silent source is not a disagreeing one).

**No silent deletion.** The name-set diff `chunk2-pass..HEAD` shows 10 tests removed, each with
a named rewrite that asserts the new (ruled/fixed) behaviour and whose docstring names the
defect it closes: F1 pin → `…warm_up_honors_the_callers_pacing` ("CLOSES REVIEW_2 FINDING 1"),
F2 pin → `…retried_on_downloads_too` ("CLOSES REVIEW_2 FINDING 2"), F3 → `…written_atomically`
("CLOSES the atomic half of FINDING 3"), F12 → `…either_entry_point_runs_nothing`, Q-4 ×3
(the six-series pick, the debt-only empty, the whitelist-only-choice AST), Q-5 ×2 (the excluded
Saturday, the no-longer-moved Monday). Every removal is a rewrite, not a drop.

## 14. Findings

**Finding 1 — LOW — [code_reviewer] `adjust_pair`'s "round once" (B46) had no tripwire; the
build's own chain test cannot see a regression to round-per-event.**
`test_adjust_pair_multiplies_the_chain_and_rounds_once` asserts `adjust_pair(100000, [0.5,
0.2]) == 10000` — but 100000 × 0.5 = 50000 and × 0.2 = 10000 are both exact, so round-once and
round-per-event give the identical answer. The adjustment-sanity goldens only ever apply a
SINGLE factor per pair (each verified event is one bonus/split), so they don't exercise a
multi-event chain either. The behaviour is **correct** (I proved round-once is load-bearing on
65,334 prices and matches on every one), so this is a test-coverage gap, not a code defect —
which is exactly the kind of hole a reviewer is meant to fill. *Closed here:*
`tests/test_review3_probes.py::test_adjust_pair_rounds_the_chain_once_on_an_inexact_chain`
(and `…round_once_matches_a_hand_scan_of_realistic_prices`) pin a bonus 1:2 × split 10→4 chain
where the two rules disagree (10003 paise → 2667 once vs 2668 per-event). Verified these fail
on the round-per-event mutant and pass on HEAD.

**Finding 2 — INFO — [quant_reviewer] pairwise adjustment is the law; "equivalent to a fully
adjusted series" is exact-arithmetic only, and can differ by a rounding tie.**
CONTEXT 3.2 defines the bias comparison pairwise (P into C's scale, C untouched) and remarks it
is equivalent to comparing on a fully adjusted series. In integer paise, once BOTH candles are
rounded independently into a common later scale, a knife-edge comparison can flip by one paise
(I found real cases with the rights/dividend factors, e.g. P=3544735, C=3284430). The engine
implements the pairwise definition, which is correct — **but a future chunk must not substitute
a fully-adjusted series and expect byte-identical bias comparisons.** *Kept:*
`test_pairwise_adjustment_is_the_law_even_where_a_full_series_would_round_differently`.

**Finding 3 — INFO — [quant_reviewer] `rights_factor` with S ≥ P returns k > 1 without
raising.** The only guard is `k <= 0`. A rights issue priced ABOVE the cum close (S=150, P=100)
yields k=1.25 (TERP > P) and passes. This is economically impossible (rights are always at a
discount) and **unreachable in practice** — every rights factor is Q-6-`pending`, so none is
ever built without an explicitly supplied S — and it faithfully computes CONTEXT 4.2's formula.
Recorded so a later reader does not mistake the absence of an upper clamp for a bug, and so
that whoever answers Q-6 considers whether an S ≥ P sanity raise is wanted.

**Finding 4 — INFO — [code_reviewer] inherited REVIEW_2 F3(resume half)/F6/F7 remain open, and
are honestly carried.** The `--raw-dir` archive is now atomic but still not resumable (written
inside the fetch loop); `atomic_write_with` is crash- but not power-loss-safe (no fsync); no
read-side ledger/rows invariant exists. All three are forward-looking (chunk 5B/9/13), not
chunk-3 defects, and the fix log states each precisely. No action for chunk 3.

## 15. Checklist coverage

**quant_reviewer** — *Look-ahead:* factors apply only to candle P, `(P,C]` window, C never
adjusted (§6); no clock read in any pure function. *Boundary operators:* bonus B/(A+B), split
B/A, rights (P−E)/P, half-open window, 2% threshold inclusive at the boundary (`<`), demerger
suppressed — all verified character-by-character and by mutation (§4–§9). *Units:* integer
paise throughout, factors are `Decimal`, `_paise` refuses a sub-paise value rather than
rounding; no float `==`. *Corporate actions:* Indian bonus convention proven against 13
catchers and the US flip; pairwise scaling; demerger blocked from ever factoring; ordinary
dividends not adjusted; the whole §5.5 checklist green. *Data honesty:* exceptions bucketed and
counted, never dropped; the report surfaces F&O-universe exceptions and pending factors
explicitly. *Fixtures/OPEN items:* F8 untouched and reproduced; Q-6/Q-7 raise rather than
default (§9).

**code_reviewer** — *Tests:* 674 green from clean; error paths carry weight (empty subject,
junk, AGM-with-money, bare split/consolidation, non-positive ratios, missing prices, demerger
factor request, non-Factor in the chain); no test weakened, skipped or xfailed; the 10 vanished
names are all rewrites naming their defect (§13). *Failure behaviour:* CA fetchers inherit the
shared retry loop, honour the caller's pacing, retry HTML-behind-200 on both paths, treat 404
as a distinct type; opt-in `allow_network=False` by default. *Idempotency/secrets:* fetchers
day-cached and atomic; no `.env`/credential anywhere in the span. *Time & precision:* naive-IST
epoch handling for Yahoo, integer paise, no float equality, no `datetime.now()` in a pure
function. *Structure:* parser and factor halves are pure (I inspected them); only the `fetch_*`
functions do I/O; `corp_actions` imports just `INSTRUMENT_SERIES` from the storage layer. *Git
& docs:* 5 logical commits, single human author, WHAT/WHY bodies citing chunk+spec, **no AI
attribution anywhere**, build commits end `(unreviewed)`, prep keeps `chunk3-prep:`; PROGRESS
complete against the §6 template with an honest four-point limits list; QUESTIONS.md carries
Q-4/Q-5 resolved+executed and Q-6/Q-7 raised. *Dependencies:* `pyproject.toml` unchanged; no
new package (F8 uses stdlib `zipfile`+`ElementTree`).

## 16. Scope

`b085f07..4f4f94d` is chunk-3 scope plus the architect-directed prep. New code:
`corp_actions.py` (parser + factors + join + fetchers), `ca_report.py` (offline report entry
point), a 12-line `nse_http` change (the `fetcher` hook). New data: 13 frozen fixtures + the
XLSX oracle. Nothing from a later chunk appears — no bias/poc/signals/simulate, no SmartAPI
client, no instrument-master loader. The two deliberate non-features (rights/dividend factors)
are the STOP rule, not gaps. This review added exactly one file
(`tests/test_review3_probes.py`, 6 tests) and modified no file under review.

---

## 17. Fix log (appended by later sessions — the review text above is unchanged)

| Finding | Status | Closed by | What changed |
|---|---|---|---|
| F1 | closed-in-review | REVIEW_3 (2026-07-25) | Coverage gap only; the reviewer added `test_review3_probes.py` pinning round-once on an inexact chain. No code change was needed or made. |
| F2, F3, F4 | INFO | — | Notes for chunks 4/9 and for the Q-6 owner; no action for chunk 3. |
