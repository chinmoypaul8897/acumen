# REVIEW_12 — chunk 12, THE VALIDATION PACK

QC review, BOTH personas (`personas/quant_reviewer.md` + `personas/code_reviewer.md`), fresh
session, over `db6c686..d1c9d72` — the architect's three plan amendments, his assigned report
edit, and the trader validation pack with its machine-readable companion, generator and tests.

The artefact under review is the one document in this repository a non-technical reader is
expected to act on. Its standard is not "correct" but "correct AND un-mistakable", and this
review is written against that standard: every figure re-derived independently, and every
sentence read as the trader will read it.

---

## PART 0 — THE ARCHITECT'S RULING, RECORDED VERBATIM

> ARCHITECT'S RULING (06-Aug-2026): chunk 11 (web report UI) joins chunks 13–15 ON HOLD pending
> the trader's decision; its content scope is satisfied by the twice-reviewed static report for
> the chunk-12 gate. plan.md's chunk-12 dependency on 11 is met by that reading. Architect.

This closes the one class-C item the build session raised and left open (QUESTIONS.md, PLAN
AMENDMENTS 06-Aug-2026, closing block): plan.md §3 lists chunk 12's dependencies as 9 AND 11,
STATUS.md's chunk-11 line was `todo`, and the 06-Aug amendment was silent on 11. The build
session did not read that silence either way and wrote down what was true on the machine
instead. The ruling now reads it: chunk 11 is ON HOLD, its content scope is discharged by
`docs/reports/chunk9b_backtest_report.md` (reviewed under REVIEW_9B_REPORT and REVIEW_9B_FINAL),
and chunk 12's dependency is met. STATUS.md's chunk-11 line is updated by this session to carry
the ruling. No chunk-11 deliverable is owed for the chunk-12 gate.

---

## 1. TEST SUITE, FROM CLEAN

**2195 passed / 0 failed / 0 skipped** in 413.34s — the build session's claim (2195/0/0)
reproduced exactly, no skips, no xfails. With this review's 6 kept probes: **2201 / 0 / 0** in 453.21s.

Test-function census over the span, `db6c686` → `d1c9d72`, across all 104 test files:
**1,502 → 1,520 functions, ZERO removed, 18 added.** No test weakened, deleted or skipped;
no assertion removed. `tests/fixtures/` and `poc/data/` byte-untouched (`git diff` empty).

The one EXTENDED test is REVIEW_9B_FINAL's kept Q2 probe
(`test_the_benchmark_factor_TALLY_counts_ONLY_the_symbols_the_benchmark_HOLDS`). Audited line by
line: the diff is **purely additive**. A special dividend is added to each fixture symbol so the
two scopes can differ at all; because `kind == "dividend"` is not in `SHARE_COUNT_KINDS`, every
original assertion is untouched in both letter and value (`share_count_events == 2`,
`share_count_symbols == 2`, `in_benchmark_share_count_events == 1`,
`in_benchmark_share_count_symbols == 1`, `share_count.total_return == 1`, and both original
rendered-line assertions). The new assertions read the mixed row's sentence off the RENDERED page
via `r9._section_benchmark`, which is what the architect's ruling (2) of 06-Aug-2026 requires.

---

## 2. THE SIX SELECTION RULES — RE-EXECUTED, THEN ATTACKED

Every rule was re-executed against the ledger by this session's own streaming census
(`docs/evidence/` is not touched; the scripts ran from the scratchpad and import nothing from
`src/acumen`). **All six rules select exactly the day the page prints.**

| slot | rule as printed | this session's re-execution | selects the printed day? |
|---|---|---|---|
| 3a winner | architect-named; must be executed, target-hit, net > 0, not a gap, inside the last 90 days | `(2026-06-10, HDFCBANK)` ∈ winners (29,852 of them); cutoff `2026-05-01`; qualifies | YES |
| 3b stop-out | last walked day's stop-outs, nearest the run's MEDIAN per-share risk | median over all 188,345 executed = **236 paise**; last day's stop-outs: HINDZINC 250 (Δ14) beats CAMS 265 (Δ29) and NYKAA 205 (Δ31) — **uniquely nearest** | YES |
| 3c gap | architect-named; must be a gap entry | `(2026-07-27, TIINDIA)` ∈ gaps (2,068 of them); qualifies — **but see finding Q1** | YES (day), claim overstated |
| 3d ==POC | most recent wait-rule day, preferring one that traded | last wait-rule day = **2026-07-29** (run's last day is 07-30, no wait-rule row on it); its three rows are IREDA (no trade), POLYCAB (entered), POWERGRID (no trade) — **POLYCAB is the only traded row** | YES |
| 3e carry | last walked day's carried-bias no-trade days, most-traded stock | 14 carries on 2026-07-30, all `inside-bar-carry`; SBIN at **1,157** trades is the most-traded of them | YES |
| 3f rounding | widest row-count gap in the last calendar year, POC moving | 51 candidates / 13 POC-moving; BAJFINANCE 2026-04-10 at separation 4 | YES |

### 2.1 The attacks — the most defensible ALTERNATE reading of each wording

**"a TYPICAL one … nearest the middle distance of all the run's trades" (3b).**
Three alternate readings constructed and measured:

* *"middle" = median over all executed trades* — the code's reading. 236 → **HINDZINC**.
* *"middle" = median over STOP-OUTS only* (the population the day is drawn from). 200 →
  **AUBANK** (200) and SBICARD (200) tie exactly; the day MOVES. **Refuted by the printed
  wording**, which says "of all the run's trades" in so many words — the population is stated.
* *"middle" = the MEAN per-share risk.* 728 paise → LODHA (740) and TECHM (740) tie; the day
  MOVES to TECHM. **Refuted**: "the middle distance" is not "the average distance" in English,
  and the code's reading is the natural one.
* Parity: `median_risk_paise` floors the average of the two central values on an even count. The
  run has an **odd** 188,345 executed trades, so the branch is not taken and the parity choice
  cannot move the day here.

**Verdict: the wording pins the reading the code uses; no defensible alternate reading moves
the day.** One narrowing IS silent — see finding C2.

**"the most recent day … the 11:15 candle closed at exactly the POC" (3d).**
Alternate reading: *"the most recent such day THAT TRADED"*. Both readings land on 2026-07-29
because POLYCAB traded on the most recent wait-rule day, so the day does not move. The failure
mode the wording would hide — a most-recent day on which nothing traded, where the page would
show a no-trade day under a sentence promising a traded one — is **not exercised on this run**;
`_pick_wait`'s `pool = traded or on_that_day` would take it. Recorded, not a finding: the day
is right and the sentence is true of the day shown.

**"the last walked carried-bias no-trade day" (3e).** Re-executed: all 14 candidates on
2026-07-30 are `inside-bar-carry`; SBIN is uniquely the most-traded. No alternate reading of
"carried" moves it — `CARRY_RULES` also admits `no-rule-carry`, `rule-3-no-1min-carry` and
`rule-3-no-break-carry`, and none of those fired on the last day. The criterion's WORDING is a
separate matter — finding Q9.

**The rounding probe (3f).** `pick_rounding_day` orders by
`(separation, poc_moves, executed, day, symbol)`. The page states the first two ("the widest gap
between the two row counts, and on it the POC itself moves") and neither of the next two. This
session's independent recount finds that **the tie in the two stated keys is actually reached**:
there are TWO candidates at the maximum separation of 4 rows, both with a moving POC —
**ZYDUSLIFE 2026-03-11** and **BAJFINANCE 2026-04-10** — and what separated them is `executed`
(ZYDUSLIFE took no trade that day). So the pack's headline exhibit was chosen by a key that lives
only in the generator's docstring. **This is finding Q14.**

**Silent tie-breaks.** The final tie-break in `_pick_stop`, `_pick_carry` and `_pick_wait` is the
SYMBOL NAME — alphabetically FIRST under `_pick_stop`'s `min`, alphabetically LAST under the
other two `max`es. No criterion mentions a name. **This is finding Q3**, pinned by
`tests/test_review12_probes.py::test_the_selection_rules_fall_back_to_the_SYMBOL_NAME_and_no_criterion_says_so`.
The symbol-name last resort is not reached on this run: each of those three selections is decided
earlier. The rounding slot's tie-break IS reached — Q14.

---

## 3. THE REPLAYS — SIX OF SIX RE-DERIVED FROM THE SPEC TEXT

The directed check asks for three days re-derived from CONTEXT's text importing nothing from
`src/acumen`, and the other three verified through the runner replay path. **All six were done
from the spec text**, and the runner path was independently re-run on top (§6).

`scratchpad/rev12_replay.py` re-implements CONTEXT 3.2 (evaluation order, bodyMin/bodyMax,
inside-bar inclusivity, Rule-1 strictness, Rule-2's mixed operators, Rule-3's 1-minute
first-break scan), CONTEXT 3.3 (half-even `totalTicks`, `tpr` with the Q-13 finer-on-tie ruling,
bottom-up rows with the remainder in the last, prorata spreading, POC = midpoint of the
max-volume row, tie → higher row), CONTEXT 7-E1/E12 (15-minute candles from open-stamped
1-minute bars, `[HH:MM−15, HH:MM)`), CONTEXT 3.4 (reference at 11:15, ARMED / WAIT-BELOW /
WAIT-ABOVE / side-unset, strict triggers, gap predicate, E7) and CONTEXT 3.5 (floor sizing, 3R
target, SL-wins-ties, square-off at the 15:00–15:15 close, Rs 100 flat). It reads the raw
1-minute parquet and the raw bhavcopy parquet directly.

**Result: 6 of 6 days, ZERO divergences, against both the page and the committed shard row.**

### 3a HDFCBANK 2026-06-10 (Rule 3, long, target)
P 2026-06-08 O 738.00 H 741.50 L 734.50 C 738.65 · C 2026-06-09 O 739.45 H 743.95 L 732.30
C 738.35 · body 738.00–738.65 · outside bar both sides · **first 1-min HIGH break 09:15 at
Rs 741.90** vs P.high 741.50, first LOW break 11:21 at Rs 734.00 vs P.low 734.50 → HIGH first,
C.close 738.35 ≥ bodyMin 738.00 → **BULLISH**. Window 120 bars / 15,220,350 shares, bottom
736.40 top 745.50, **182 ticks, tpr 8, 23 rows**, POC row 739.60–740.00 → **POC 739.80**.
Reference 738.20 below → ARMED. 11:30 close 740.95 → **entry**. Stop 738.10 (entry candle low),
risk 2.85, target 749.50, **qty 350**, notional Rs 259,332.50, at risk Rs 997.50. Target hit
13:15, fill at the LEVEL 749.50, gross Rs 2,992.50, **net Rs 2,892.50**.

### 3b HINDZINC 2026-07-30 (Rule 1, long, stop)
P 2026-07-28 O 530.05 H 530.90 L 524.00 C 526.90 · C 2026-07-29 close 536.70 > bodyMax 530.05 →
**BULLISH** by Rule 1. Window 120 / 958,338, bottom 533.50 top 542.00, **170 ticks, tpr 7,
25 rows**, POC row 537.35–537.70 → **POC Rs 537.525 — a genuine HALF-PAISE midpoint**.
Reference 535.50 below → ARMED. 11:30 close 538.00 → entry. Stop 535.50, risk 2.50, target
545.50, **qty 400**, notional Rs 215,200.00, at risk Rs 1,000.00 exactly. Stop hit 12:00, gross
−Rs 1,000.00, **net −Rs 1,100.00**.

### 3c TIINDIA 2026-07-27 (Rule 1, SHORT, GAP entry, stop)
P 2026-07-23 O 2,903.70 H 2,921.40 L 2,816.50 C 2,824.50 · C 2026-07-24 close 2,767.00 < bodyMin
2,824.50 → **BEARISH**. Window 120 / 132,143, bottom 2,754.60 top 2,865.00, exact **1,104 ticks,
tpr 46, 24 rows**, POC row 2,846.60–2,851.20 → **POC 2,848.90**. Reference 2,843.40 below on a
bearish day → **WAIT-ABOVE**; 11:30 (2,854.10) arms; 11:45 / 12:00 / 12:15 armed-not-triggered;
12:30 close 2,842.10 below → **entry, short**. **GAP**: the entry candle's high is
**Rs 2,848.80 against the POC Rs 2,848.90 — a TEN-PAISE margin** — so the stop is the previous
15-minute close 2,850.80, risk 8.70 (not 6.70), target 2,816.00, **qty 114** (not 149), notional
Rs 323,999.40, at risk Rs 991.80. Stop hit 13:00, gross −Rs 991.80, **net −Rs 1,091.80**.
All five transition rows reproduce. See finding Q6.

### 3d POLYCAB 2026-07-29 (the ==POC wait rule, long, square-off)
P 2026-07-27 · C 2026-07-28 close 9,121.50 > bodyMax 9,010.00 → **BULLISH**. Window 120 /
108,708, bottom 8,975.00 top 9,169.50, **389 ticks, tpr 16, 25 rows**, POC row 9,007.00–9,015.00
→ **POC 9,011.00**. Reference **9,011.00 — exactly ON the POC** → SIDE-UNSET (Q41-A). 11:30 close
9,010.00 below → sets the side AND arms (that candle is never the entry). 11:45 close 9,029.00 →
**entry**. Stop 9,009.00, risk 20.00, target 9,089.00, **qty 50**, notional Rs 451,450.00, at
risk Rs 1,000.00. Neither level touched → square-off at the **15:00–15:15 candle's close
9,050.00**, gross Rs 1,050.00, **net Rs 950.00**.

### 3e SBIN 2026-07-30 (inside-bar carry, no trade)
P 2026-07-28 · C 2026-07-29 sits entirely inside P (H 1,020.20 ≤ 1,022.00, L 1,012.00 ≥
1,008.30) → **inside bar, carry**. Walked back independently: the bias for trading day
2026-07-29 was set by **Rule 1 BEARISH** on the pair (2026-07-27, 2026-07-28) — exactly what the
page says. Window 120 / 1,790,868, bottom 1,007.60 top 1,016.90, **93 ticks, tpr 4, 24 rows**,
POC row 1,014.40–1,014.80 → **POC 1,014.60**. Reference 1,014.40 below on a bearish day →
WAIT-ABOVE; 11:30 (1,014.90) arms; **fifteen** transition rows, no close ever below the POC
again → **no trade**. Every one of the 15 rows reproduces.

### 3f BAJFINANCE 2026-04-10 (inside-bar carry, long, stop, THE ROUNDING PROBE)
P 2026-04-08 · C 2026-04-09 inside → carry; last SET by **Rule 1** for trading day 2026-04-09 on
the pair (2026-04-07, 2026-04-08) → BULLISH. Window 120 / 4,286,154, bottom 912.30 top 925.35 →
span 1,305 paise at a 10-paise tick = **exactly 130.5 ticks**. Half-even → **130** (130 is even),
tpr 5, **26 rows**, POC row 918.30–918.80 → **POC 918.55**. Reference 923.80 above on a bullish
day → WAIT-BELOW; six armed-none rows; 13:00 (916.60) arms; 13:15 / 13:30 armed-not-triggered;
13:45 close 920.40 → **entry**. Stop 917.30, risk 3.10, target 929.70, **qty 322**, notional
Rs 296,368.80, at risk Rs 998.20. Stop hit 14:00, gross −Rs 998.20, **net −Rs 1,098.20**.
All ten transition rows reproduce.

### The committed rows
All six shard rows carry exactly **38 keys**, so "38 of 38 pieces of the record" is the WHOLE
row and not a subset. Every field the page prints was checked against the shard by hand as well
as by the replay: zero divergences on all six.

---

## 4. BAJFINANCE'S GRID, BOTH WAYS

### 4.1 The residual, re-derived
`top − bottom = 92,535 − 91,230 = 1,305 paise`; tick 10 → `1305/10 = 130.5` ticks — an EXACT
half-tick residual, which is the only shape in which the two rounding modes can differ at all.

### 4.2 Both grids, both ways, independently
| mode | totalTicks | tpr derivation | rows | POC |
|---|---|---|---|---|
| half-even (the engine) | **130** (130 is even) | 130/24: down 5 → ⌈130/5⌉ = 26 rows (Δ2); up 6 → ⌈130/6⌉ = 22 rows (Δ2) → **TIE → the FINER profile (Q-13)** → tpr 5 | **26** | **Rs 918.55** |
| half-up | **131** | 131/24: down 5 → ⌈131/5⌉ = 27 (Δ3); up 6 → ⌈131/6⌉ = 22 (Δ2) → up wins → tpr 6 | **22** | **Rs 918.60** |

Both reproduced twice: once by this session's from-scratch prorata, once through the pack's own
`_grid_at` + `poc.spread_volume`. Both grids **conserve volume exactly** (4,286,154 in each) —
including the half-even grid, whose row stack ends at Rs 925.30 while the window's top is
Rs 925.35, because `RowGrid.top_paise` carries the true top and CONTEXT 3.3's "the topmost row
includes `top`" is honoured. `poc.build_rows` is untouched by this chunk, and `_grid_at`
reproduces it exactly when handed the engine's own tick count (pinned by the build's own test).
The two POCs are **Rs 0.05 apart**, as the page states.

### 4.3 The trade under both modes
Re-run end to end at POC 918.60: **entry 920.40, stop 917.30, risk 3.10, target 929.70, qty 322,
stop hit 14:00, net −Rs 1,098.20 — IDENTICAL in every field.** The page's claim *"On this
particular day the trade comes out the same either way, so nothing here turns on it. On other
days it would not."* is **TRUE and correctly hedged**.

### 4.4 The ask's wording
*"open BAJFINANCE on Friday 10 April 2026, put the Fixed Range Volume Profile over 09:15 to
11:15 with Row Size 24, and count the rows in the box. If you count 26, the machine is already
right. If you count 22, we change one line and re-run."* Two integers, four apart, one
instruction, no jargon — **unambiguous as a 26-vs-22 test**. The gap is that it is BINARY: see
finding Q13.

---

## 5. THE COUNTS — ALL RE-COUNTED FROM THE RAW LEDGER

One independent streaming pass over all 495,312 rows, importing nothing from `src/acumen`.

| the pack says | this session counts | |
|---|---|---|
| 188,345 trades / 2,428 days / 204 stocks | 188,345 / 2,428 / 204 | OK |
| gross before costs Rs 1,998,481.80 | 199,848,180 paise | OK |
| costs 188,345 × Rs 100.00 = Rs 18,834,500.00 | 1,883,450,000 paise; 188,345 × 10,000 exactly | OK |
| net −Rs 16,836,018.20 | −1,683,601,820 paise; and 199,848,180 − 1,883,450,000 = −1,683,601,820 | OK |
| 62 Rule-3 tie days, **62 bullish / 0 bearish** | 62; 62 / 0 / 0 other; by year 1+8+4+5+2+5+7+8+7+9+6 = 62 | OK |
| earliest BLUESTARCO Fri 16 Dec 2016, latest GLENMARK Mon 27 Jul 2026 | identical; both weekday labels correct | OK |
| 4,151 wait-rule days, 2,246 traded | 4,151 / 2,246, **all 4,151 with status `evaluated`** | OK |
| "out of the 406,488 stock-days the machine was able to judge" | evaluated = 406,488, and **every one of them carries both a reference and a POC** — so the denominator is exact, not approximate | OK |
| 51 rounding candidates / 13 POC-moving | §5.3 | OK |
| all eleven year rows (trades, win %, net) | all 33 cells reproduce; trades sum to 188,345; nets sum to −1,683,601,820 exactly | OK |
| drawdown Rs 16,852,007.80, peak Thu 6 Oct 2016 → trough Thu 30 Jul 2026, never recovered | re-derived from a from-scratch equity curve: peak equity 11,598,960 on 2016-10-06, trough −1,673,601,820 on 2026-07-30, drop 1,685,200,780 paise, **0 later observations at or above the peak** | OK |
| final running total −Rs 16,736,018.20 | 10,000,000 + (−1,683,601,820) = −1,673,601,820 | OK |
| 495,312 walked / 406,488 judged / 88,824 refused | identical | OK |

### 5.1 The 0-bearish explanation is STRUCTURAL, not prose
The page says the zero *"is your own rule showing through, not a coincidence"*. CONTEXT 3.2 v1.3
says the same in its own words (*"the bearish branch is unreachable for closes inside the body —
bullish precedence — and closes outside the body were already decided by Rule 1"*), and
`tests/test_bias.py::test_the_tie_bearish_branch_is_written_as_the_spec_writes_it` pins it on one
routed pair. Because the pack states it as a property of ten years of real days, this review
proves it **exhaustively**: over 1,401 closes on a 5-paise grid spanning far below P's body to
far above it, each with a genuine outside bar and both extremes broken inside the SAME 1-minute
candle, the routed engine produces a BEARISH tie **zero times**, every tie-case close lies inside
`[bodyMin, bodyMax]`, and every close outside the body is taken by RULE_1 before the tie is
reached. Kept as
`tests/test_review12_probes.py::test_the_packs_zero_bearish_ties_is_STRUCTURAL_over_a_dense_grid`.

### 5.2 The wait-rule equality is exact, not rounded
`reference + reference == poc_half_paise` — an integer equality in the half-paise domain, no
float and no rounding (CONTEXT 7-E11). Re-executed independently; 4,151 rows, all evaluated.

### 5.3 The rounding population — 51 / 13 reproduced exactly, twice
Recounted from scratch over the span's last calendar year (2026-01-01 … 2026-07-30) using this
session's own CONTEXT 3.3 arithmetic, over the 28,701 (symbol, day) pairs the run itself
evaluated with a POC. The only repository inputs are DATA: the pinned instrument master's tick
sizes and the run's own list of evaluated days.

* 89 of the 204 symbols carry an ODD tick and are skipped — correctly, since `top − bottom` is an
  integer number of paise and a half-tick residual is impossible unless the tick is even;
* 16,158 day-windows scanned on the remaining 115;
* **51 candidates**, of which **13 move the POC** — the page's two numbers, exactly.

Run twice under two independent I/O strategies (a per-day read and a per-symbol-month read) with
identical results. Distribution by row-count separation: **1 → 39, 2 → 2, 3 → 8, 4 → 2**. The
maximum separation is 4 and **two** candidates sit on it (§2.1, finding Q14).

### 5.4 The bias-rule tally does NOT partition anything the page prints
See finding **Q2**. The ten rows sum to **493,680**, which is neither 495,312 (walked) nor
406,488 (judged). Decomposition, measured:

* 419,599 rows carry a real bias rule (Rule 1 285,574 + inside 64,819 + Rule 2 62,385 + Rule 3
  6,724 + tie 62 + no-1min 30 + no-break 5);
* 74,081 carry a "not judged" label (no-data 73,841 + minutes-ungated 210 + suppressed 30);
* 419,599 + 74,081 = 493,680;
* **1,632 walked stock-days carry NO bias rule at all** — every one of them a
  `CONTEXT 7-E2 non-standard session` refusal — and appear in no row;
* and 419,599 − 406,488 = **13,111 rows counted under Rule 1/2/3/inside-bar were REFUSED** after
  their bias was computed, so they were not judged either.

---

## 6. BYTE-REPRODUCIBILITY, INDEPENDENTLY RE-PROVEN

`acumen.trader_pack.main` re-run from THIS session, in a fresh process, to scratch paths, over the
same run directory and the same read-only stores, then diffed against the committed files — a
cross-session reproduction rather than a repeat of the build's own two runs:

* `trader_pack.md` — **diff EMPTY**, sha256 `00503d6418413d183ecb255226d0381674dcb433220a44c816425d86c9d2b000`, 40,285 bytes, 565 lines;
* `trader_pack.json` — **diff EMPTY**, sha256 `237d3f9891ddcef2cc4703e41f2fc0553b3612c83c8bbdbee6c59064fb522ed7`, 37,484 bytes, 1,577 lines.

Both match the committed files and the build session's published digests exactly. That
regeneration is also the **independent re-run of the runner replay path**: it re-wired the run's
own `BacktestRunner` (same pinned master `ce198be44b44fc33…`, same factor table, same
non-standard-session set from the manifest) and re-walked all six days — **38 of 38 on all six,
`divergences: []` on all six**, reproduced in this session rather than read from the artefact.

Report: `docs/reports/chunk9b_backtest_report.py` re-run from this session to a scratch path
over the same run directory — the full job, all 204 symbols and all 188,345 fifteen-minute
trade paths re-assembled from the raw lake — and **diffed EMPTY** against the committed file:
sha256 `9ca0ed52cc0899c1c51ccdbe80afef6513b417abced6fe7b7690b648153f7d19`, 86,145 bytes,
897 lines, equal to the build session's published digest.

All three files are ASCII-only, as `src/acumen/config.py` requires.

---

## 7. PAGE 1, THE JSON COMPANION, THE QUOTES, THE SCAN

**Page 1's arithmetic** re-derived to the paisa: gross Rs 1,998,481.80 − costs Rs 18,834,500.00
= net −Rs 16,836,018.20; cost share `100/1000 = 10.00%` exactly.

**The break-even derivation**, recomputed from the two averages by hand:
`p* = −avg_loss / (avg_profit − avg_loss)` with avg_profit = 3,783,802,864/19,795 paise
(Rs 1,911.4942…) and avg_loss = −3,258,752,603/32,230 paise (−Rs 1,011.0929…) gives
`p* = 12,901,401,555,277/37,291,794,816,621 = 0.3459581824…` → **34.60%**, against a delivered
`11,877/37,669 = 0.3152990…` → **31.53%**. Both renderings correct. The denominators differ by
the 40 flat trades — finding **Q5**.

**Every rupee token on the page is in the JSON companion** — check re-run by this session with
its own regex over the page and its own from-scratch renderer over each recorded value, not the
generator's: **170 money tokens on the page, 170 recorded, 0 unaccounted, 0 self-inconsistent**,
and every percentage on the page is recorded too.

**The tripwire has teeth — 7-mutant matrix, 7 caught, 0 survivors.** The claim "no figure on the
page is typed" is only worth what its guard catches, so both halves were mutated (against COPIES;
no repository file was edited):

| mutant | half | result |
|---|---|---|
| M1 a rupee amount typed into a prose string | source | CAUGHT |
| M2 a grouped digit run typed into a heading | source | CAUGHT |
| M3 a paisa-shaped decimal typed into a heading | source | CAUGHT |
| M4 `RISK: int = 100000` added as a module constant | source | CAUGHT |
| M5 `Rs 4,321.99` typed into the page's prose | rendered | CAUGHT |
| M6 an existing page figure nudged by one paisa | rendered | CAUGHT |
| M7 a half-paise POC nudged in its 3-decimal form | rendered | CAUGHT |

M6 and M7 matter most: they are what a hand edit of the committed page after generation would
look like, and the rendered half catches both.

**The nine Round-3 quotes are byte-equal to QUESTIONS.md's receipts.** Each quotation was
extracted from the pack, matched against the unwrapped blockquotes of QUESTIONS.md's ROUND-3
RECEIPTS (25-Jul-2026) and ROUND-3 FINAL RECEIPTS (29-Jul-2026), and found **verbatim, 9 of 9**.
The only difference is that the receipt's `Qnn (Round 3):` prefix is lifted OUT of the quotation
marks and into the row's citation, which is the correct direction under the architect's
quotation-fidelity ruling of 06-Aug-2026: nothing inside the quotation marks is abridged or
paraphrased.

**The no-recommendation scan**: `"we recommend"` and `"you should"` are absent (the build's own
test), and this session widened the scan to `we suggest / we advise / our advice / in our view /
we think / we believe / the best option / you ought / I recommend` — **all absent**. Page 6 read
by hand: finding **Q12**.

---

## 8. THE REPORT EDIT

**369 = 94 + 275 re-derived independently** from the run manifest's factor table and the raw
2016-10 bhavcopy, importing nothing from `src/acumen`:

* members (a close on the first trade date 2016-10-03): **134**;
* IN-BENCHMARK: **369** non-unit factors on those members = **94** share-count (across **61** of
  the 134) + **275** dividend;
* TABLE-WIDE: **433** = **125** share-count (across **86**) + **308** dividend.

Both partitions close exactly. The previously published pair (94 / 61 / 134) is **unmoved** — the
`if first_close is not None:` restructure preserves `in_bench_symbols` / `in_bench_events`
exactly, because the `share_applied` test is nested rather than dropped.

**The freeze holds and gained nothing.** Verified independently against the pre-edit report
(`git show b24afcc:`): the whole-file diff is **exactly one line** (line 597, the edited
sentence); sections 1..9 are **566 lines on both sides, byte-identical**; the numeric extraction
yields **2,457 tokens on both sides, identical in order**, equal to the frozen baseline;
`lines_excluded_as_edited` is still **5** and `ref` is still `3cbfafa`. Report sha256
`9ca0ed52cc0899c1c51ccdbe80afef6513b417abced6fe7b7690b648153f7d19`, 86,145 bytes, 897 lines —
the build's published digest.

**The extended Q2 probe** is audited in §1: purely additive, every original assertion intact,
the new ones read off the RENDERED page.

---

## 9. FINDINGS

Severity: HIGH = blocks · MEDIUM = the architect should rule before the pack is handed over ·
LOW / INFO = recorded.

### Quant

**Q1 — MEDIUM. The gap day's provenance sentence overstates what the ledger records, and
nothing checks it.**
Page 3c: *"the day the architect named for this slot, and the LAST gap entry of the whole ten
years."* There are 2,068 gap entries; the last gap-entry DAY is 2026-07-27 and it carries **two**
of them — TIINDIA (entry stamp **12:30**) and **INDUSINDBK (entry stamp 12:45)**. INDUSINDBK's
gap entry is fifteen minutes later, so TIINDIA is not "the LAST gap entry"; under the kindest
day-level reading it is one of two, and the page claims uniqueness it does not have. The
qualification `_pick_gap` performs is membership only (`(day, symbol) in census.gaps`); the
superlative is unconditional prose in the named branch. The generator's OWN fallback rule for
this slot (`max` by day, then trades) would have chosen INDUSINDBK (1,104 trades vs 1,004) — the
code's definition of "the most recent gap entry" disagrees with the sentence it prints. No money
figure moves and TIINDIA's 38 fields all reconcile; what is wrong is a provenance claim on a page
whose promise is *"None of them was picked by hand: each one is the answer to a written rule."*
Pinned by `test_the_gap_days_LAST_GAP_ENTRY_claim_is_printed_without_being_checked`.

**Q2 — MEDIUM. The bias-rule table's population is unstated and reconciles to nothing else in
the pack.**
Heading: *"Which of your bias rules decided the days the machine judged."* Its rows sum to
493,680 (§5.4), which is neither of the two counts page 5 prints (495,312 walked, 406,488
judged). Three of its own rows are labelled *not judged*; 13,111 rule-labelled rows were refused
after the bias was computed; 1,632 non-standard-session days carry no rule and appear in no row.
No total is printed, so a reader has nothing to check. Pinned by
`test_the_bias_rule_table_sums_to_a_population_the_page_never_names`.

**Q3 — LOW. A tie-break the page never states.**
See §2.1. The last resort in `_pick_stop`, `_pick_carry` and `_pick_wait` is the symbol NAME, and
it runs in opposite directions in `min` and `max`. Not reached on this run. Pinned.

**Q4 — MEDIUM. Six F&O stocks are absent from the run and absent from the page that exists to
say so.**
Page 5: *"The machine ran the 204 stocks that are in the futures-and-options list NOW."* The
list is 210. Six — **APLAPOLLO, ASTRAL, IEX, NTPC, UPL, VBL** (CONTEXT 4.6 v1.5) — are
QUARANTINED for data quality and were never walked. The technical report names them; the pack
does not mention the quarantine anywhere, and asserts that 204 IS the list. NTPC is a large,
liquid F&O name a trader would expect to find. Page 5 lists survivorship, perfect fills, no
capital limit, flat costs and the coverage percentage; the one omission on it is the one that
removes whole stocks.

**Q5 — LOW. Page 1's two win rates are taken over different denominators.**
The break-even 34.60% derives from averages over the trades that made or lost money (188,305 —
`_break_even_win_rate`'s docstring says so); the delivered 31.53% is 59,385 of 188,345, which
includes the 40 flat trades. Matched, the delivered rate is 31.54% and the gap 3.06 pp rather
than 3.07 pp. Immaterial here; pinned so it stays immaterial.

**Q6 — MEDIUM. The two decisive observables on the pack's most delicate days are asserted, not
shown.**
* 3c, the gap day: the page says *"the entry candle opened clean past the POC and never traded
  back to it"* and prints **neither** the entry candle's high (Rs 2,848.80) **nor** the POC
  margin. The predicate turns on **ten paise**. One tick the other way and the stop is the entry
  candle's own high, risk Rs 6.70 instead of Rs 8.70, qty 149 instead of 114 — a different trade
  on the page. The trader is asked to confirm the machine did what he would have done, and the
  number that decides it is not there.
* 3a, the Rule-3 day: the page says *"the machine read C's one-minute candles in order and found
  that the HIGH broke first"* and gives neither time nor level. It is true (09:15 at Rs 741.90
  against P's high Rs 741.50; the low breaks at 11:21), but confirming it means scanning 375
  one-minute candles for a level the page never names as the thing to look for.

Both walks are otherwise followable with only a TradingView chart open (§10).

**Q7 — MEDIUM. A sentence a non-programmer will misread: the stop that is already touched.**
Page 2 states *"The stop. The low of the entry candle on a long"* and, four lines later,
*"If the price touches the stop, you are out at the stop."* Read literally, every long trade is
stopped out on its own entry candle — the entry candle has by definition already traded at its
own low. CONTEXT 7-E7 (the entry candle cannot trigger an exit; monitoring starts on the next
candle) appears nowhere on the page, and day 3a is a live instance: HDFCBANK's stop Rs 738.10 IS
its entry candle's low, and the trade ran on to its target at 13:15. One clause closes it.

**Q8 — MEDIUM. Two coverage figures side by side that a reader will try, and fail, to
reconcile.**
Page 5: *"Of every stock-day in the stored data, 93.9317% passed the checks"*, then in the same
paragraph *"Of the 495,312 stock-days the run walked, 406,488 were judged and 88,824 were
refused"* — which is 82.07%. Both denominators are named, and they are genuinely different
(93.9317% is 409,205/435,641 over the whole lake; 409,205 is never printed). But the two sit one
sentence apart under one heading, and nothing tells the reader they are not the same measurement.

**Q9 — LOW. The 3e criterion contradicts its own walk and page 2.**
Criterion: *"a day … where no rule fired on the two daily candles"*. The walk beneath it: *"That
is an inside bar, and your first rule says the bias does not change."* On page 2 the inside bar
is rule 1 of five and *"Nothing fits"* is rule 5. All 14 candidates on the last day are inside
bars. `CARRY_RULES` genuinely mixes "a rule fired and it says carry" with "no rule fitted".

**Q10 — LOW. "Every trade risked Rs 1,000.00, no more and no less" is contradicted three pages
later.**
Page 3 prints Rs 997.50, Rs 991.80 and Rs 998.20 *"genuinely at risk"* on 3a, 3c and 3f. Page 2
states the floor correctly (*"rounded DOWN"*); page 1's absolute phrasing does not survive it.

**Q11 — INFO. "This is the whole strategy as the machine has it" is broader than the list.**
Four rules the machine really applies are not on page 2: CONTEXT 7-E10 (a missing 11:15
reference falls back to the last 1-minute close ≤ 11:14), 7-E4 (>5 missing window minutes → no
POC → no trade), the Rule-3 tie predicate (restated on page 3 instead), and the two Rule-3
minute fallbacks (which appear only as rows in the bias table, 30 and 5 days). Also unstated:
that a first distinct close ABOVE the POC on a ==POC bullish day sets the side into WAIT-BELOW
rather than arming, and the Q-13 finer-profile tie rule. None changes a number on the page.

**Q12 — INFO. The three paths carry no recommendation and are not symmetric in valence.**
The scan is clean and the framing sentence is explicit. But the closing clause of each path
differs in kind: *Retire it* closes on a reassurance (*"Nothing is lost that was not already
spent finding out"*), *Change it* on a capability (*"the answer comes back in hours rather than
months"*), and *Take it live* is the only one closing on a caution (*"you take it knowing what
page 1 says"*). Recorded for the architect's eye; the pack states no preference and this review
does not claim it does.

**Q13 — MEDIUM. The one question the pack exists to settle is asked as a binary, and the
trader's only previous row count in this repo was neither answer.**
*"If you count 26, the machine is already right. If you count 22, we change one line and re-run."*
The chunk-6 gate is quoted on page 2 of this very pack: *"BHARTIARTL 17-Jul: POC reads about
1913.9, and I count 25 rows in the box"* — against an engine that drew **26**. His count was off
by one then, and the ruling turned on it being nearer 26 than 22. A 25 or a 27 here has no branch
on the page, and the pack gives him no instruction for it. The evidence that the binary framing
is fragile is printed in the same document, three pages earlier, unconnected.

**Q14 — MEDIUM. The rounding day's "furthest apart" is a definite description of a day that is
not unique, and the key that really chose it is on no page.**
Page 3f: *"this is the one with the widest gap between the two row counts, and on it the POC
itself moves"*, and below the table *"This is the one where the two row counts are furthest
apart, which makes it the easiest to read off a chart and be sure."* This session's independent
recount (§5.3) finds **two** candidates at the maximum separation of 4 rows, **both** with a
moving POC: **ZYDUSLIFE 2026-03-11** (26 rows @ Rs 934.85 vs 22 @ Rs 934.80) and **BAJFINANCE
2026-04-10** (26 @ Rs 918.55 vs 22 @ Rs 918.60). Both stated keys are tied. What separated them
is `pick_rounding_day`'s third key, `executed` — ZYDUSLIFE took no trade on 2026-03-11 — and that
key appears only in the function's docstring, never on the trader's page. The choice is a GOOD
one (a day that traded shows the rest of the rule), which is exactly why it deserves the half
sentence the criterion gives to the two keys above it. This is the pack's headline exhibit, so
of all the selections it is the one whose provenance most needs to be complete. Pinned by
`test_the_rounding_days_FURTHEST_APART_claim_is_not_unique_and_a_hidden_key_breaks_the_tie`.

### Code

**C1 — MEDIUM. A criterion's factual claim is pinned nowhere.**
`tests/test_trader_pack.py` exercises each selection FUNCTION on a synthetic census, which is
right and well done. Nothing anywhere asserts a printed CRITERION's factual claim against the
census it was built from. Q1 is exactly that gap realised: the sentence *"the LAST gap entry of
the whole ten years"* would survive a data change that made it badly false, with all 2,195 tests
green. This is the shape the architect's ruling (2) of 06-Aug-2026 names (pin the rendered claim,
not only the helper) — applied here to the pack's prose rather than the report's.

**C2 — LOW. The stop-out pool is narrower than the page's words.**
`census` builds `stops` under an `elif` after `if row["gap_entry"]`, so a gap-entry stop-out is
excluded. The page says *"of that day's stop-outs"*, unqualified. Not load-bearing: this session
counted **zero** gap-entry stop-outs on 2026-07-30, so the pool is the whole population there.

**C3 — LOW. The companion names a different day-3d symbol from the page.**
`figures.counts.wait_rule_most_recent` is `["2026-07-29", "POWERGRID"]` — the last element of a
tuple sorted by `(day, symbol, …)`, i.e. alphabetically last on that day. The page's 3d is
POLYCAB, chosen because it is the only one that traded. A document build consuming the companion
would print POWERGRID (a no-trade day) under a field whose name reads as "the most recent
wait-rule day". The DATE is right; the symbol is a sort artefact.

**C4 — INFO. `Census.median_risk_paise`'s even-count branch is untaken on this run.**
It floors the average of the two central values. 188,345 executed trades is odd, so the branch
never runs here; it is covered by a unit test on both parities.

**C5 — INFO. Two figures the page prints have no cross-check in the pack itself.**
`409,205` (the numerator of the 93.9317%) and the 210-symbol universe are both absent, so the
two arithmetic checks a careful reader would want to run on page 5 cannot be run without opening
the technical report. Related to Q4 and Q8.

---

## 10. THE PLAIN-ENGLISH READ (quant persona, wearing the trader's hat)

**Followable with only a TradingView chart open?** Five of the six walks: yes, completely. Every
daily OHLC, every profile bound, every tick count, every row count, every 15-minute close, every
entry / stop / target / share count and every rupee is on the page, and this session confirmed
each against the raw stores. The two gaps are Q6: the gap day's decisive candle high, and the
Rule-3 day's first-break minute.

**Sentences a non-programmer would misread**, in order of how likely:
1. the stop that is already touched (Q7) — the reader's own first question on day 3a;
2. the two coverage percentages (Q8);
3. *"Every trade risked Rs 1,000.00, no more and no less"* against three pages of Rs 991.80–998.20 (Q10);
4. *"no rule fired"* over a walk that says *"your first rule"* (Q9);
5. the bias-rule table, which invites a total that is never printed and would not match if it were (Q2).

**What is notably well done**, and is not praise for its own sake because it is what the
standard demands: the POC printed to the **half paisa** on HINDZINC (Rs 537.525) rather than
rounded to a number his chart cannot produce; the row bounds printed beside every POC so the
midpoint is checkable rather than asserted; the "count them on your own chart" instruction
attached to every row count; the criterion printed in italics above every day; the honest
*"38 of 38 pieces of the record match"* line with its stated promise to print divergences; and
page 5 existing at all.

---

## 11. THE CLASS-B DECISIONS — B297 … B303

**B297 — the mixed row's tally scoped to the members it is built from. APPROVED.**
Re-derived independently (§8): 369 = 94 + 275 on 134 members, 433 = 125 + 308 table-wide, both
partitions closing exactly. The previously published pair does not move; both new fields are
defaulted so the eleven hand-built pairs in the kept probes are unchanged; the probe extension is
purely additive and reads the RENDERED line.

**B298 — reuse `report_9b.read_run`, add ONE census pass. APPROVED.**
The pack's totals equal this session's own independent ledger census to the paisa on every
figure, which is the property the decision is for: the pack and the report cannot drift. The
second pass is genuinely necessary — the wait-rule rows and the bias-rule tally live on rows
`read_run` discards by design.

**B299 — six days chosen by RULE, the rule printed beside the day. APPROVED WITH CHALLENGE.**
The principle is right and this session re-executed all six rules against the ledger: each
selects exactly the printed day (§2). Two challenges: (i) the gap slot prints a superlative its
qualification test does not check and which the ledger does not support — finding Q1; (ii) the
last resort in three of the rules is the symbol name and no criterion says so — finding Q3. The
same shape appears once more in the rounding slot, which B303 owns — finding Q14. The principle
"the rule is printed beside the day" is only as good as the completeness of what is printed, and
in two of six slots it is incomplete.

**B300 — replay through the run's own runner, compared field by field. APPROVED.**
Strong, and independently re-run here: 38 of 38 on all six, `divergences: []` on all six, in a
regeneration this session performed. The ordering insight recorded in the decision (the runner is
wired only AFTER the rounding probe has chosen the sixth symbol, so that symbol's corporate
actions are present) is genuinely load-bearing and was a real defect caught before any artefact
was generated.

**B301 — no typed figure, enforced at the source AND at the rendered output. APPROVED.**
Both halves re-run by this session with its own tooling: no rupee-shaped literal, no grouped
digit run outside the trader's own quotes, no CONTEXT 3.5 magnitude as an integer; and 170 of 170
money tokens on the page accounted for by the companion, each agreeing with a from-scratch
re-rendering of the recorded value. The exemption for the trader's own *"1,000"* is checked
against the quote list rather than assumed, which is the right shape. **Both halves survive a
7-mutant matrix with zero survivors** (§7) — including a one-paisa nudge of an existing figure on
the committed page, which is what a post-generation hand edit would look like. This is the
strongest decision in the span.

**B302 — a POC printed to the HALF paisa. APPROVED.**
Necessary, not cosmetic: HINDZINC 2026-07-30's POC really is Rs 537.525, re-derived here from the
raw minutes as the midpoint of the row 537.35–537.70. `pf.format_paise` would have printed
Rs 537.53, which is not a price and not a midpoint.

**B303 — the rounding probe bounded to the last calendar year, the bound printed; `_grid_at`
evidence-only. APPROVED WITH CHALLENGE.**
The bound and the evidence-only construction are right: `poc.build_rows` is byte-untouched,
`_grid_at` reproduces it exactly when handed the engine's own tick count, both grids conserve
volume through the engine's own `spread_volume`, the odd-tick skip is provably safe, and the
bound is printed on the page beside the answer. The independent recount reproduces 51 / 13
exactly (§5.3). The challenge is the SELECTION the decision does not mention: the ordering's tie
is genuinely reached and the day was chosen by a key the page never states — finding Q14.

---

## 12. THE STANDARD SWEEP

* **Suite from clean**: 2195 / 0 / 0 (413.34s), the build's claim exactly; **2201 / 0 / 0**
  (453.21s) with this review's 6 probes. No skips, no xfails.
* **No test weakened**: 1,502 → 1,520 functions, zero removed, zero assertions dropped; the one
  edited test is additive (§1).
* **Fixtures frozen**: `git diff db6c686..d1c9d72 -- tests/fixtures poc/data` is EMPTY.
* **Byte-reproducibility**: pack, companion and report each regenerated to scratch by this
  session, diffs EMPTY, digests equal to the committed and published ones (§6, §8).
* **Engines untouched**: `bias`, `poc`, `signals`, `simulate`, `portfolio`, `backtest` carry no
  change in the span; the only `src/` change is `report_9b.py` (the architect's assigned edit) and
  the new `trader_pack.py`.
* **Purity**: `trader_pack.py` splits cleanly — `build_everything` does the I/O, `render` is pure
  and takes what was read; no clock read anywhere in the rendering path (the pack carries no
  generation timestamp, which is also why it is byte-reproducible).
* **Hygiene**: commits are logical units with what+why bodies and correct `chunk12:` prefixes;
  the two commits touching `src/` and `tests/` both carry `(unreviewed)`; the PROGRESS entry
  follows plan.md §6 exactly with all fields; STATUS.md updated; QUESTIONS.md carries the
  amendments verbatim.
* **No AI attribution** anywhere in the span's messages or diffs.
* **Secrets**: no `.env`, no credential, no `data/` or `cache/` path committed; the pack prints
  the ledger digest and no path.
* **ASCII-only**: pack, companion, generator and tests all clean.
* **SHA chain**: ledger `c70a72b097879914a3026331c1e651b70c7e6052327d0f34121fd30909a4d134` and
  manifest `2594c6e81d404029c655645a6eb3d8b5fe58d02a0be1891ec9040aebcd25b764` — hashed from the
  machine by this session, equal to the values three reviews have published and to the ones the
  companion records. Run code_sha `c34c0880…`, spec v1.7, pinned master `ce198be44b44fc33…`.
* **ZERO store writes**: the whole of `data_root` swept at the start of this session and again
  after every regeneration — **22,186 files both times, newest mtime unchanged at
  2026-08-05 23:37:57**, ledger and manifest digests unchanged, and **0 files modified
  anywhere under `data_root` in the last seven hours**. Every regeneration this session ran
  wrote to scratchpad paths via `--out` / `--json`; nothing was linked, junctioned or copied
  into a worktree (CLAUDE.md, Q-18 layers 1 and 2). The OPERATOR still owes the two-generation
  `data/` + `cache/` snapshot before any store-changing work.

---

## 13. VERDICT

**PASS.** 19 findings (14 quant + 5 code), none blocking, **not one of them a wrong number**.

Nothing in this span deviates from CONTEXT.md. No number on the trader's page is wrong: page 1
reconciles to the paisa, all eleven year rows and the drawdown re-derive from the raw ledger, all
six days re-derive from the SPEC TEXT digit by digit importing nothing from `src/acumen`, both
BAJFINANCE grids reproduce twice over with the trade proven identical under both, every count
re-counts, and every rupee on the page traces to a value the companion carries. No test was
weakened, deleted or skipped; no fixture byte moved; no engine module was touched; the stores
were read-only; the artefacts regenerate byte-identically.

The findings are about the second half of the standard — *un-mistakable* — and none of them
makes a figure false. **Three are recommended for the architect's ruling before the pack is
handed to the trader**, because each costs one or two sentences and each is the kind of thing a
careful reader will notice and be unable to resolve on his own:

* **Q1** — the gap day's *"LAST gap entry of the whole ten years"*, which the ledger does not
  support and no test checks;
* **Q4** — the six quarantined F&O stocks, absent from the run and unmentioned on the page whose
  job is to name what the machine did not do;
* **Q7** — the stop that page 2 says is already touched, demonstrated live on day 3a.

Two more are worth the architect's judgement rather than an edit:

* **Q13** — the row-count question is asked as a binary, and the trader's only previous row count
  in this repo (quoted on page 2 of this pack) landed between the two answers;
* **Q14** — the rounding day is described twice as *the* one furthest apart when two days tie on
  both stated keys, and the key that actually chose it is only in a docstring.

Q1 and Q14 are the same defect twice: a definite description on the trader's page that the
selection rule does not establish. C1 is why neither was caught — no test anywhere asserts a
printed criterion's factual claim against the census it was built from.

The chunk-12 TRADER GATE stays **OPEN** — it closes on the trader's confirmation, which is what
the pack asks for and what this review cannot supply.

---

## 14. KEPT PROBES

`tests/test_review12_probes.py` — six, all green:

1. `test_the_packs_zero_bearish_ties_is_STRUCTURAL_over_a_dense_grid` — **proves** the pack's
   62-bullish / 0-bearish sentence over 1,401 routed pairs.
2. `test_the_gap_days_LAST_GAP_ENTRY_claim_is_printed_without_being_checked` — **pins Q1**.
3. `test_the_selection_rules_fall_back_to_the_SYMBOL_NAME_and_no_criterion_says_so` — **pins Q3**.
4. `test_the_rounding_days_FURTHEST_APART_claim_is_not_unique_and_a_hidden_key_breaks_the_tie` —
   **pins Q14**, on the real shape (ZYDUSLIFE vs BAJFINANCE) the recount found.
5. `test_the_bias_rule_table_sums_to_a_population_the_page_never_names` — **pins Q2**, read off
   the committed artefacts.
6. `test_page_ones_two_win_rates_are_taken_over_different_denominators` — **pins Q5**.

Probes 2–6 pin findings and are written to turn RED when the finding is fixed, following the
repo's established discipline (REVIEW_9A/9B probes that pinned a defect and were later FLIPPED
to assert the corrected property).
