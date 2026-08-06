# REVIEW_9B_FINAL — QC of the chunk-9B FINAL EDITS to THE REPORT

**Session:** 2026-08-06 · fresh session · BOTH personas (`personas/quant_reviewer.md`,
`personas/code_reviewer.md`) · directed span `3cbfafa..814bdb3` — the span starting at the tag
`chunk9b-pass`, exactly as REVIEW_9B_REPORT finding C3 asked.

**Subject:** the architect's **Q-23 refinement published**, REVIEW_9B_REPORT's **six
presentational corrections**, and the **numeric freeze** that claims none of it moved a number
above section 10. Five commits, 9 files, +3,692 / −106.

**Stance.** This report goes to the trader. Every figure the span touches has been recomputed
from the raw ledger, the crashed shards, the daily store and the backfill register **importing
nothing from `src/acumen`**, and every claim the span makes *about itself* — verbatim, frozen,
byte-reproducible, pinned — has been tested rather than read.

---

## VERDICT

**PASS**, 8 findings, **none blocking**, **not one of them a wrong number**: quant — 3 MEDIUM,
1 INFO; code — 1 MEDIUM, 1 LOW, 2 INFO.

* **Suite 2168 passed / 0 failed / 0 skipped from clean in 363s** — the session's claim reproduced
  exactly. **2174 / 0 / 0** with this review's 6 kept probes.
* **THE THREE BENCHMARK FIGURES ARE RIGHT.** Re-derived by re-running the PRIOR review's own
  evidence script (copied to scratch with its output path redirected, so no earlier session's
  artefact was touched): **RAW Rs 398,922.17 = 298.92%**, **SHARE-COUNT ONLY Rs 566,668.64 =
  466.67%**, **MIXED Rs 591,899.89 = 491.90%**, and the pack it writes is **byte-identical** to
  the committed one.
* **THE FREEZE HOLDS, INDEPENDENTLY.** A tokeniser written from the freeze's own description
  extracts **2,457 tokens from `git show 3cbfafa:`** and **the same 2,457, in the same order,
  from the shipped report**. A line-level diff of sections 1..9 finds **10 differing lines in the
  shipped file and 5 in the pre-edit one — every one of them marker-covered, ZERO uncovered.**
* **ALL SIX FIXES REPRODUCE TO THE DIGIT** from the raw ledger by arithmetic that shares no line
  of code with the generator — Long's fence and its 13,243 outliers, all six tie sets and all
  twelve range endpoints, both concurrency conventions, the partial-year marker, gate 1P's
  97.8444%, and Q6's 105 / 18 measured bases re-derived from the crashed shards themselves.
* No CONTEXT deviation. No test weakened, deleted or skipped (**0 removed, 17 added**). No
  fixture byte moved. `portfolio.py` and all twelve other engine modules untouched. No secrets.
  No AI attribution. `HEAD == origin/main` at entry. **ZERO store writes** — the run directory's
  mtimes are all ≤ 2026-08-05 20:25:39 and the ledger's sha256 is still
  `c70a72b097879914…a4d134`.

**What is owed before the report is handed to the trader** — three one-line prose edits, in
exactly the class the span itself was closing:

1. **Q1** — section 10's blockquote is presented as the architect's words and is not them: the
   ruling's own **“(491.90% as generated)”** is deleted and a **“QUESTIONS.md”** pointer is
   inserted. `BENCHMARK_RULING`'s own comment says *"quoted VERBATIM"*.
2. **Q2** — *"What THE BENCHMARK applies: **125** share-count factors across **86** symbols"* is
   counted over every symbol with a daily series. The benchmark's own 134 members carry **94** of
   those factors across **61** symbols.
3. **Q3** — the second concurrency row is labelled *"the 15-minute path's convention"*. Measured,
   the 15-minute path's own convention gives **90**, not 77.

---

## PART 0 — two things recorded before anything else

**(a) The span starts at the tag.** `chunk9b-pass` = `3cbfafa`; the brief's span is
`3cbfafa..814bdb3`; `git rev-list` returns exactly the five commits the brief names. The gap
REVIEW_9B_REPORT's C3 recorded does not recur — **nothing between the tag and HEAD is unreviewed
by this document.**

**(b) `QUESTIONS.md`'s own record was not edited.** The span's `QUESTIONS.md` diff is exactly
three things: the Q-23 heading moves *RULED* → *CLOSED*, the architect's **refinement** is
appended verbatim, and an *EXECUTED by …* block is appended beneath it. **The ruling recorded by
the previous session is byte-untouched.** That matters for finding Q1: the record is intact; it
is the report's quotation of it that is not.

---

## DIRECTED CHECK 1 — Q-23 PUBLICATION FIDELITY

### 1a. Is the quoted ruling + refinement byte-equal to QUESTIONS.md's record? **NO — finding Q1.**

Both blockquotes were pulled out of `QUESTIONS.md` by pattern, ASCII-folded (the only difference
the repo licenses: report files are ASCII-only by `src/acumen/config.py`'s rule, `QUESTIONS.md`
is not), and compared word for word against `BENCHMARK_RULING` as section 10 renders it.

| | QUESTIONS.md (the record) | section 10 (the quote) |
|---|---|---|
| ruling's opening | `ARCHITECT'S RULING (06-Aug-2026), Q-23:` | `ARCHITECT'S RULING (06-Aug-2026), **QUESTIONS.md** Q-23:` |
| the ruling's figure | `the SHARE-COUNT-ADJUSTED construction **(491.90% as generated)** —` | `the SHARE-COUNT-ADJUSTED construction --` |
| ruling's signature | `… the adjusted one is THE benchmark. **Architect.**` | `… the adjusted one is THE benchmark.` |
| the refinement | *(identical, word for word)* | *(identical)* |

**Those three edits are the WHOLE of the divergence** — proved, not asserted: restoring the two
substantive ones turns the published string back into the recorded one exactly (kept probe
`test_the_reports_Q23_quote_is_NOT_verbatim_against_the_QUESTIONS_md_record`).

The deletion is the one that matters. `BENCHMARK_RULING`'s own comment states *"The ruling and
its same-day refinement are quoted **VERBATIM** beside the readings they decide, which is how
every architect ruling travels in this repo"*, and B282 records *"which section 10 also quotes
verbatim so the report carries its own authority."* The refinement's figures — `(125 factors) =
466.67%` — were kept inside the quote; the ruling's own figure was removed. The bullet three
lines below the table then says the mixed reading *"is the figure the ruling first named"* — of a
quote from which that naming has been deleted.

Nothing here makes a number wrong: 491.90% is printed in the table on its own row, and the
architect's record in `QUESTIONS.md` is intact and unaltered. It is a fidelity defect in the one
sentence on the page that carries someone else's authority.

### 1b. Are the three figures right? **YES — re-derived by re-running the prior review's own script.**

`docs/evidence/review9b_benchmark_recompute.py` imports nothing from `src/acumen`: it reads the
bhavcopy parquet with pandas and re-implements E13's construction from its own words. It was
copied to the scratchpad with its `OUT` path redirected — **no earlier session's evidence artefact
was written** — and re-run against the same read-only stores.

| Reading | The prior review's script, re-run today | The report |
|---|---:|---:|
| RAW closes as stored | **Rs 398,922.17 = 298.92%** | 298.92% |
| **SHARE-COUNT ONLY (bonus / split / rights)** | **Rs 566,668.64 = 466.67%** | **466.67%** |
| Mixed (share-count + the 308 special dividends) | **Rs 591,899.89 = 491.90%** | 491.90% |

The markdown it wrote is **byte-identical to `docs/evidence/review9b_benchmark_recompute.md` as
committed** (`diff` empty), so the pack three sessions now rely on is itself reproducible.

### 1c. Labels, the STOP's removal, and the B275 re-pointing

| Item | Result |
|---|---|
| the share-count row labelled THE BENCHMARK | present, and **first** in the table |
| the other two labelled *(NOT the benchmark)* | **exactly 2 occurrences**, on the mixed row and the raw row; pinned by a shipped test that asserts `count == 2` |
| `BENCHMARK_STOP` | **gone** from `src/`, `tests/` and `docs/reports/`; the only surviving occurrences are the historical narratives in `REVIEW_9B_REPORT.md`, `QUESTIONS.md`, `PROGRESS.md`, `STATUS.md`, which is correct |
| section 13's *"Q-23 open, both readings shown"* | **gone**; replaced by *"Q-23 is RULED and CLOSED"*; `"Q-23 open"` and `"neither published"` appear nowhere in the report |
| **B275 re-pointed** | **B282 (SUPERSEDES B275)** in `PROGRESS.md`'s `decisions:`, and the same re-pointing recorded under Q-23's *EXECUTED* block. Superseded, not reversed — the wording is right |

### 1d. The arithmetic — recomputed

| Claim | Recomputed | |
|---|---|---|
| 125 share-count + 308 special-dividend = 433 non-unit factors | 125 + 308 = **433** | OK |
| kinds in span: 77 bonus + 35 split + 13 rights + 308 dividend | **77 / 35 / 13 / 308** from the run's own factor table | OK |
| `(by event kind: dividend 308)` | the excluded set is **`{"dividend": 308}`** and nothing else | OK |
| +25.23 pp of opening capital | 491.90 − 466.67 = **25.23** | OK |
| 5.13% of its own figure | 25.23 / 491.90 = **5.129…% → 5.13%** | OK |
| **125 factors across 86 symbols** | 125 across 86 — **over all 204 universe symbols** | **finding Q2** |
| the same, over the 134 symbols the benchmark is actually built from | **94 factors across 61 symbols** | |

---

## DIRECTED CHECK 2 — THE FREEZE, re-done independently

A tokeniser was written from the freeze's own prose description — *"every numeric token …
appearing on any line of sections 1 through 9, in order"* — rather than by importing
`docs/evidence/chunk9b_report_numeric_baseline.py`, and run over both artefacts.

| | Lines in §1..9 | Tokens | == the committed baseline JSON? |
|---|---:|---:|---|
| `git show 3cbfafa:docs/reports/chunk9b_backtest_report.md` | 558 | **2,457** | **YES, token for token** |
| the SHIPPED report | 566 | **2,457** | **YES, token for token** |

**The five excluded lines are exactly the edited ones, and nothing else.** A line-level
`SequenceMatcher` diff of sections 1..9 between the two files:

| | Differing lines | Covered by a marker | **Uncovered, non-blank** |
|---|---:|---:|---:|
| pre-edit side | 5 | 5 | **0** |
| shipped side | 10 | 10 | **0** |

The pre-edit five are section 1's gates sentence, section 5's `Best year` row, section 6's two
`% of its own notional` rows and section 6a's blanket fence claim. The shipped ten are the six
replacements plus the four lines the corrections add (the concurrency bullet, the tie-range
paragraph, and the two per-column fence bullets). **No line of sections 1..9 differs that the
marker list does not name, and no line the marker list names is one the corrections did not
touch** — which is the property an exclusion list has to have to be a freeze rather than a hole.

**The freeze cannot pass on an unedited report.** Running the shipped
`test_each_of_the_six_corrections_is_PRESENT_in_the_regenerated_report` logic against the
committed **pre-edit** blob: **9 of its 9 assertions FAIL**; against the shipped report, **0 of 9
fail**. Section 10's own check fails there too — `"THE BENCHMARK -- share-count events only"`
absent, `"Q-23 CLOSED"` absent, `"(NOT the benchmark)"` count **0**, and `"neither published"` and
`"Q-23 open"` both still present. Kept as a probe
(`test_the_numeric_freeze_is_not_VACUOUS_the_pre_edit_report_fails_it`), reading the blob through
`git show` so it cannot be satisfied by a string the test wrote itself.

**The last commit TIGHTENED the freeze, and that is a real strengthening.** `814bdb3` drops
`(5, "| Worst year |")` from the exclusion list: the row goes through the same rewritten renderer
as `Best year`, but 2023 is a full year so it comes out byte-identical and is now **COMPARED**.
6 exclusions / 2,455 tokens → **5 exclusions / 2,457 tokens**. Independently confirmed: the
`Worst year` row's two tokens are inside the frozen stream on both sides.

**Byte-reproducibility, verified by this session's own regeneration.** The report was regenerated
from HEAD to a scratch path, over the same run directory and the same read-only stores:

```
PYTHONPATH=src python -c "from acumen.report_9b import main; main(['--out','<scratch>/regen_review.md'])"
    -> wrote 84,700 chars in 4,037 s

diff <scratch>/regen_review.md docs/reports/chunk9b_backtest_report.md
    -> EMPTY

sha256  09b485b8beb41d2c695f7389c19b521892736d5b9c3370ceab626897761cc8b5  <scratch>/regen_review.md
sha256  09b485b8beb41d2c695f7389c19b521892736d5b9c3370ceab626897761cc8b5  docs/reports/chunk9b_backtest_report.md
        84,700 bytes on both
```

**BYTE-IDENTICAL. Diff empty.** The session's *"byte-reproducible, proved twice"* claim is now
proved a third time, by a session that did not write the generator. REVIEW_8 finding C2's rule is
satisfied. The run's artefacts were re-read and never written: after the regeneration the newest
mtime anywhere under `<data_root>/backtests/chunk9b_full` is still **2026-08-05 20:25:39**, the
ledger's sha256 is still `c70a72b097879914…a4d134`, the manifest's is still `2594c6e81d404029…`,
and a sweep of the **whole** `data_root` finds **0 files** modified since this session began.

*(Operational note, not a finding: the regeneration took **67 minutes** — about two of those hours
of wall clock were shared with this review's own suite runs and mutation matrix. REVIEW_9B_REPORT
recorded ~4 hours under similar contention and ~20 minutes for a bulk month-at-a-time read. The
stage that costs the time is unchanged: the 15-minute path assembly opens a month file per
trade-day for all 188,345 trades.)*

**Digest and size.** The committed report is sha256
`09b485b8beb41d2c695f7389c19b521892736d5b9c3370ceab626897761cc8b5`, **84,700 bytes**, 895 lines —
the digest and the size `STATUS.md` and `PROGRESS.md` publish.

---

## DIRECTED CHECK 3 — THE SIX FIXES, recomputed from the raw ledger

495,312 rows streamed once; 188,345 executed; 2,428 distinct walked days; Long 89,345 / Short
99,000. All quantiles type-7 in exact `Fraction`s, all money in integer paise, importing nothing
from `src/acumen`.

### Q1 — the Tukey claim, now made per column

| Column | Q1 | Q3 | IQR | Fences | Outliers | Worth | Share |
|---|---:|---:|---:|---|---:|---:|---:|
| All (188,345) | −Rs 1,099.60 | Rs 622.70 | Rs 1,722.30 | **[−Rs 3,683.05, Rs 3,206.15]** | **0** | — | — |
| **Long (89,345)** | −Rs 1,099.60 | **Rs 440.00** | **Rs 1,539.60** | [−Rs 3,409.00, **Rs 2,749.40**] | **13,243** | **Rs 38,311,425.93** | **76.48%** of gross profit |
| Short (99,000) | −Rs 1,099.60 | Rs 800.95 | Rs 1,900.55 | **[−Rs 3,950.42, Rs 3,651.78]** | **0** | — | — |

Every figure the report prints. The upper fence **Rs 2,749.40 < the Rs 2,900.00 largest win** on
Long and **not** on the other two, which is exactly the per-column claim the section now makes;
0 below the lower fence, 0.00% of gross loss. The All and Short containment claims — *"contains
every one of its 188,345 trades"* / *"its 99,000 trades"* — both hold: 0 outliers each, and the
populations are the columns' own.

*(Short's lower fence is exactly −Rs 3,950.425. The report prints **−Rs 3,950.42**, which is
`Decimal.quantize`'s ROUND_HALF_EVEN — this repo's standing convention, and correct. Recorded as
INFO Q4 only because a reader recomputing half-up lands on .43.)*

### Q5 — the tie sets

Every one of the six tied sets, both range endpoints and both notional endpoints, reproduced:

| Column | Largest win | Ties | % range | Notional range |
|---|---:|---:|---|---|
| All | Rs 2,900.00 | **5,383** | 0.0196% .. 8.1232% | Rs 35,700.00 .. Rs 14,800,000.00 |
| Long | Rs 2,900.00 | **2,205** | 0.0213% .. 8.1232% | Rs 35,700.00 .. Rs 13,601,000.00 |
| Short | Rs 2,900.00 | **3,178** | 0.0196% .. 7.8378% | Rs 37,000.00 .. Rs 14,800,000.00 |
| All | −Rs 1,100.00 | **20,939** | −6.6667% .. −0.0040% | Rs 16,500.00 .. Rs 27,408,000.00 |
| Long | −Rs 1,100.00 | **9,718** | −3.7931% .. −0.0066% | Rs 29,000.00 .. Rs 16,781,000.00 |
| Short | −Rs 1,100.00 | **11,221** | −6.6667% .. −0.0040% | Rs 16,500.00 .. Rs 27,408,000.00 |

**The old rows really were arbitrary**: the printed `0.29%` was one draw from a set whose members
run 0.0196% to 8.1232%. The fix is the right one.

### Q7 — the two concurrency conventions, swept independently

| Convention | This session's own sweep | The report |
|---|---|---|
| OPEN before CLOSE at a shared stamp | **90** at **2026-05-07 12:45**, Rs 29,033,458.63 | identical |
| CLOSE before OPEN at a shared stamp | **77** at **2026-03-20 12:30**, Rs 18,698,137.26 | identical |

Both figures are right. **What is not right is whose convention the second one is — finding Q3.**
`acumen.backtest.assemble_trade_paths`' own docstring: *"The marks run from the ENTRY candle's
close … **through the EXIT candle's close stamp**, and the last mark carries the trade's EXIT
LEVEL"*. A trade is therefore MARKED at every stamp in `[entry, exit]` **inclusive** — which
REVIEW_9B_REPORT confirmed from the other side (188,345 of 188,345 paths whose **last** mark
reproduces the ledger net). Counted the way the path actually holds positions:

```
max_T  #{ trades with a mark at T }  =  90  at 2026-05-07 12:45, Rs 29,033,458.63
max_T  #{ entry <= T <  exit }       =  77  at 2026-03-20 12:30, Rs 18,698,137.26
```

**The 15-minute path's own maximum is 90, not 77.** The 77 belongs to a half-open convention
`concurrency_closing_first` implements and no other artefact on the page uses. So section 4's
*"The 15-minute equity path uses the other convention, **because a trade's marks END at its exit
candle**, and it therefore reports a smaller maximum"* draws the wrong inference from a true
premise — a mark existing at the exit candle is what makes the path count the position there —
and section 11's row label *"(the 15-minute path's convention: closed AT its exit mark)"* carries
it. Finding Q7 asked for the convention to be **defined**; two are, clearly, and the pessimistic
one leads. The attribution of the second one is the defect.

**`portfolio.py` is untouched (B286).** `git diff 3cbfafa..814bdb3 -- src/acumen/portfolio.py` is
empty, as are the diffs for `bias`, `poc`, `signals`, `simulate` and `backtest`. The mirror lives
entirely in `report_9b.py`.

### Q3 — the derived partial-year marker (B288)

`_partial_years` reads only the walked index. Measured from the ledger:

* the index runs **2016-10-03 .. 2026-07-30**, 2,428 days;
* **2016: 61 walked days, 2016-10-03 .. 2016-12-30** — exactly the cell's numbers;
* 2026: 141 walked days, 2026-01-01 .. 2026-07-30 — partial by the *last* clause, not the first;
* the nine full years 2017..2025 are complete by construction;
* best year **2016 (−Rs 225,598.97)**, best FULL year **2018 (−Rs 1,178,849.98)**, worst year
  **2023 (−Rs 2,098,184.07)** and 2023 is full, so the Worst-year row correctly carries no marker.

The brief asked for a synthetic where the *last* year is the extreme one. Built as a kept probe
(`test_the_partial_year_marker_follows_the_LAST_year_of_a_ten_year_span`): a 2016..2026-shaped
index whose **best** year is the partial 2026 — the marker fires, and the best FULL year named
beside it is 2017. Hardcoding 2016 is caught (mutation matrix, M3).

### Q4 — one word, two quantities

Recomputed from `<data_root>/universe_backfill/ledger.json` directly:

| Quantity | Recomputed | The report |
|---|---:|---:|
| gate 1P alone, **settled** universe | 412,234 / 421,316 = **97.8444%** | 97.8444% |
| gate 1P alone, all 210 symbols | 422,408 / 435,641 = 96.9624% | *(not printed)* |
| all three gates (settled numerator, whole-lake denominator) | 409,205 / 435,641 = **93.9317%** | 93.9317% |

B291's scoping choice is what produces the printed figure, and it is the right domain — a
quarantined symbol is not part of the settled universe. See code finding **C2**: the 93.9317%
beside it is still a string literal.

### Q6 — the measured base, re-derived from the crashed shards

Not from the report's classifier: this session opened the 103 surviving shards of
`chunk9b_full_crashed_0803` and asked, per refusal class, how many of that class's days the
crashed run actually walked.

| Class | Days | **Days with a counterfactual** | Traded before | Their net |
|---|---:|---:|---:|---:|
| minutes-ungated | 210 | **105** | **13** | **−Rs 7,358.35** |
| gate 2 (candle integrity) | 47 | **18** | **7** | **−Rs 3,698.60** |

Identical to the report's new fourth column, and `103 of 204` is the shard count on disk. A
reader computing 13/210 was computing the wrong thing; 13/105 is the measurement.

---

## DIRECTED CHECK 4 — B282 … B291

| # | Decision | Judgment |
|---|---|---|
| **B282** *(supersedes B275)* | THE BENCHMARK is the share-count-only construction; the mixed and raw readings stay printed and labelled *NOT the benchmark*; the ruling is quoted in section 10 | **APPROVED on substance, CHALLENGED on one clause.** The construction is exactly the refinement's, the figure re-derives (Rs 566,668.64 = **466.67%**) from the prior review's own script, the labels are present and pinned (`count("(NOT the benchmark)") == 2`), and superseding rather than reversing B275 is the right relationship — B275 produced the measurement that let the architect rule with numbers in hand. The clause *"which section 10 also quotes verbatim"* is **not accurate**: finding **Q1**. |
| **B283** | a share-count event is exactly `SHARE_COUNT_KINDS = (bonus, split, rights)` | **APPROVED.** Defining the set by *what multiplies units* rather than by *excluding "dividends"* is what takes the CA engine's 2% threshold out of the benchmark, which is the refinement's stated principle. Verified over this run rather than assumed: the only non-unit factors inside the hold window are 77 bonus + 35 split + 13 rights + 308 dividend, so the by-kind exclusion removes exactly the 308 and touches nothing else. Mutation-verified (M4). |
| **B284** | the "and stated" line quantifies the exclusion in BOTH units | **APPROVED.** Both recomputed: 491.90 − 466.67 = **25.23 pp**, and 25.23 / 491.90 = **5.13%**. An exclusion a reader cannot size is one they cannot weigh, and the ruling's *"and stated"* half is what this discharges. |
| **B285** | the two %-of-notional rows print a min..max RANGE over the tied set, with the tie count and the notional range beside it | **APPROVED.** All six tied sets and all twenty-four endpoints reproduce from the raw ledger. The decision is also *provably necessary*, not merely tidy: the printed 0.29% was one draw from a set running **0.0196% to 8.1232%**, decided by ledger row order. Mutation-verified (M7). |
| **B286** | the second convention is a separate PURE function `concurrency_closing_first`, not a flag on `pf.disclosures` | **APPROVED, with two challenges.** Keeping a reviewed pure module untouched is right and it *is* untouched (`git diff` over `portfolio.py` is empty), the mirror is pure, and both figures reproduce under this session's own sweep. Challenged on: (i) the row's ATTRIBUTION to the 15-minute path, which is finding **Q3** — the path's own maximum is **90**; (ii) the same-stamp event ordering, finding **C1**. Neither touches a published number. |
| **B287** | the two new render inputs default so the 11 kept probes keep calling unchanged; the real call sites are pinned STRUCTURALLY by an AST test | **APPROVED.** The idiom is the existing `INTRADAY_PATH_NOT_SUPPLIED` one, the claim about the probes is true (they call `r9._section_e13(...)` with no `ties`, and the file is byte-untouched), and the AST pin is exactly the shape REVIEW_9B_REPORT's M1 proved was missing at `_side_split_over_walked_days`' call site. Mutation-verified in both limbs (M1, M2). |
| **B288** | partial years are DERIVED, never hardcoded | **APPROVED.** `_partial_years` reads only the walked index; 2016 (61 days, 2016-10-03 .. 2016-12-30) and 2026 (141 days, 2026-01-01 .. 2026-07-30) both fall out of the data, and 2023 — the worst year — correctly carries no marker. Mutation-verified (M3), and this review adds the LAST-year-extreme synthetic the shipped fixture reaches only for the worst-year row. |
| **B289** | refusal pricing carries its measured base in the DATA (`RefusalClass.days_measured`, `.priced`) | **APPROVED as a decision, with a test-coverage finding.** Putting the base in the dataclass rather than in prose is right and the values are correct — 105 of 210 and 18 of 47, re-derived here from the crashed shards themselves. See **C4**: the rendered cell is not pinned. |
| **B290** | the numeric baseline is read through `git show 3cbfafa:`, its exclusions are (SECTION, substring) pairs, and section 5's `Worst year` row is COMPARED rather than excluded | **APPROVED — the strongest decision in the span.** All three limbs verified independently: the baseline reproduces token-for-token from the blob (2,457) and from the shipped report (2,457); the section scoping is load-bearing (an unscoped `price-proven` would have swallowed section 9's own paragraph and the B149 caveat, both of which carry numbers); and the `Worst year` decision is a real self-imposed tightening — `814bdb3` moved it from excluded to compared, 6 exclusions / 2,455 tokens → **5 / 2,457**. A freeze whose exclusion list shrinks under its own scrutiny is the rare kind that means something. |
| **B291** | gate 1P's share is computed over the SETTLED symbols only | **APPROVED.** 412,234 / 421,316 = **97.8444%** recomputed from the register; over all 210 symbols it would be 96.9624%, and a quarantined symbol is not part of the universe the figure describes. Section 1 now says out loud that the two figures have different denominators, which was the whole of finding Q4. See **C2**: the 93.9317% beside it is still typed rather than computed. |

---

## DIRECTED CHECK 5 — STANDARD SWEEP

| Item | Result |
|---|---|
| **Suite from clean** | **2168 passed / 0 failed / 0 skipped** in 363.28s — the session's claim, exactly. **2174 / 0 / 0** with this review's 6 kept probes. |
| Arithmetic on the count | 2,140 (build) + 11 (REVIEW_9B_REPORT probes) = 2,151 at `chunk9b-pass`; + 13 report tests + 4 freeze tests = **2,168**. Consistent. |
| **The 11 prior kept probes** | `git diff 3cbfafa..814bdb3 -- tests/test_review9b_report_probes.py` is **EMPTY**. Unmodified, all 11 collected and green inside the 2,168. They still call `r9._section_e13(...)` without the new argument — which is precisely why B287's default exists. |
| **AST call-site pins** | **REAL — both limbs mutation-verified.** See the matrix below: M1 and M2 each turn one of `build_everything`'s two new call sites into the default, and `test_build_everything_supplies_the_tied_sets_and_the_second_convention` goes RED on both. B287's claim that *"a default cannot quietly become the shipped path"* holds. |
| Fixtures | `git diff 3cbfafa..814bdb3 -- tests/fixtures/ poc/data/` is **EMPTY**. Frozen. F9 untouched. |
| Tests weakened / deleted / skipped | **NONE.** Test-function names diffed base→HEAD: **0 removed, 17 added**; no test file lost a function. 0 skips, 0 xfails, no `pytest.mark` added. The only two deleted assertions are ruling-driven and strictly strengthened: `pair.stop` no longer exists (renamed `pair.ruling`, and the new assertion checks both `"Q-23"` **and** `"Q-23 CLOSED"`), and `events_applied == 0` became `events_applied == 0 and share_count_events == 0`. |
| Engine modules | `portfolio`, `bias`, `poc`, `signals`, `simulate`, `backtest` — **none touched by the span**. |
| Commit hygiene | Five commits, `chunk9B:` prefixes, what+why bodies. **All four that touch `src/` or `tests/` carry `(unreviewed)`**; the fifth (`4e87938`, `QUESTIONS.md` only) is correctly exempt. |
| AI attribution | **NONE** — every commit message and every changed file scanned. |
| Secrets | No `.env` value, credential name or key in any diff, test output, evidence artefact or this review's packs. |
| SHA chain | `HEAD == origin/main == 814bdb3` at session entry. Single branch `main`. No force-push. |
| **Store mtimes + ledger digest** | **UNCHANGED.** All 208 files under `<data_root>/backtests/chunk9b_full` carry mtimes ≤ **2026-08-05 20:25:39**; `ledger.jsonl` is 400,451,219 bytes with sha256 **`c70a72b097879914a3026331c1e651b70c7e6052327d0f34121fd30909a4d134`** — the digest four reviews have now published. Every regeneration this session ran went to the scratchpad. |
| Evidence rule (REVIEW_7 C3) | Satisfied: the store-derived claims are printed by a committed generator into a committed report, and the span adds `docs/evidence/chunk9b_report_numeric_baseline.{py,json}`. No earlier session's evidence artefact was modified — the prior review's benchmark script was re-run from a **copy** with its output redirected. |

### The mutation matrix over `src/acumen/report_9b.py`

Seven mutants, each REVERTING one thing this span decided. A mutant is CAUGHT only when a test
goes red; every run was against the **whole** suite. The file was restored and its sha256
re-verified after every one (`20fb6f95c276e4a1…88ead2`, equal before and after; `git status` on
`src/` clean afterwards).

| # | Mutant — what it reverts | Shipped suite | Caught by |
|---|---|---|---|
| **M1** | `build_everything` stops measuring the tied sets (`ties=None`, the default takes over) | **CAUGHT** | `test_build_everything_supplies_the_tied_sets_and_the_second_convention` |
| **M2** | `build_everything` stops building the second concurrency convention | **CAUGHT** | the same AST pin |
| **M3** | `_partial_years` HARDCODES `2016` instead of deriving it (B288) | **CAUGHT** | `test_section_5_marks_a_PARTIAL_best_year_and_names_the_best_FULL_year_beside_it` |
| **M4** | `SHARE_COUNT_KINDS` also applies `dividend` — the Q-23 refinement reversed (B283) | **CAUGHT** | `test_the_benchmark_applies_SHARE_COUNT_events_ONLY_and_excludes_every_cash_distribution` |
| **M5** | the gate-1P share computed over the WHOLE register, not the settled universe (B291) | **CAUGHT** | `test_section_1_separates_the_ALL_THREE_GATES_figure_from_gate_1P_ALONE` |
| **M6** | the priced refusal rows RENDER the full day count as the measured base — finding Q6 reverted in the cell (B289) | **SURVIVED** (2168 passed) | **nothing** -- CLOSED by a kept probe |
| **M7** | the tie rows print ONE trade's percentage again (B285) | **CAUGHT** | `test_the_largest_win_percentage_is_a_RANGE_over_every_TIED_trade` |

**A note on how M6 was measured, because the first measurement was wrong.** M6's first run
reported CAUGHT — by an earlier, *incorrect* version of this review's own probe file that happened
to be in the tree at the time. That is not a measurement of the shipped suite, and it is recorded
rather than quietly re-run: `-x` stops at the first failure, so a contaminating probe masks
whatever came after it. M6 was re-run with this review's probe file `--ignore`d. (The second run
also failed spuriously — on `test_project_runtime_sources_are_ascii_only`, because this reviewer's
probe file carried literal em-dashes and the repo's own ASCII guard, which covers `tests/` too,
correctly refused it. Fixed; the guard did its job.)

---

## FINDINGS

### Quant

**Q1 · MEDIUM · section 10 presents a quote as the architect's words, and it is not what the
architect wrote.**
Detailed in DIRECTED CHECK 1a. `BENCHMARK_RULING` deletes the ruling's own parenthetical
**“(491.90% as generated)”** and inserts a **“QUESTIONS.md”** pointer the architect did not
write, while its own comment says the ruling is *"quoted **VERBATIM**"* and B282 records
*"section 10 also quotes verbatim so the report carries its own authority."* The elision is not
neutral: the bullet below the table calls the mixed reading *"the figure the ruling first named"*,
and the quote above it no longer contains that naming. No number is affected — 491.90% has its own
row — and `QUESTIONS.md`'s record is intact. **Fix (owed, one string):** restore the parenthetical
and either drop the inserted pointer or move it outside the quotation marks. *Closed as arithmetic
by a kept probe that pins the divergence in both directions.*

**Q2 · MEDIUM · *"What THE BENCHMARK applies: 125 share-count factors across 86 symbols"* counts
factors the benchmark does not apply.**
`benchmark_pair` tallies `share_count_events` / `share_count_symbols` over every symbol with a
daily series in the window. THE BENCHMARK is built from the **134** symbols carrying a close on
2016-10-03 — section 10 names the other **70** in the line directly above. Measured from the run's
own factor table: of the 125, **94 sit on the 134, across 61 symbols**; the remaining 31 factors
on 25 symbols are applied to a first close that never enters the portfolio. The same holds for the
mixed row's 433 (in-benchmark: 369 = 94 + 275). **The published figures are unaffected** — 466.67%
and 491.90% are computed over the 134 and both re-derive — but the sentence that begins *"What THE
BENCHMARK applies"* describes a wider population than the benchmark. This is the same defect class
as REVIEW_9B_REPORT's Q6, which this very span closed two sections later; it is also pre-existing
in kind (the pre-edit line said *"the adjustment touches 115 symbols and applies 433 share-count
factors"*, and the prior review's own pack published the in-benchmark subset without flagging the
wording). `STATUS.md` and `PROGRESS.md` carry the same 125/86 phrasing. **Fix (owed, one clause):**
scope the tally to the benchmark's members, or say the tally is over the universe.
*Closed as arithmetic by a kept probe.*

**Q3 · MEDIUM · the second concurrency row is attributed to the 15-minute path, which does not
use that convention.**
Detailed in DIRECTED CHECK 3 / Q7. `assemble_trade_paths` marks a trade *"through the EXIT
candle's close stamp"*, so counting the positions the path holds at each stamp gives **90 at
2026-05-07 12:45 carrying Rs 29,033,458.63** — the *first* row's figure, not the second's. **77 is
a third convention** (`[entry, exit)`) that nothing else on the page uses. Section 4's stated
reason — *"because a trade's marks END at its exit candle"* — is the premise that makes the path
count the position **at** T, not the premise that makes it stop counting it. Both printed numbers
are correct as computed and the pessimistic reading leads, so no reader is misled about the
capital the book required. **Fix (owed, one clause):** call the second row what it is — a
half-open convention that closes a position at its exit stamp — and drop the claim that the
15-minute path uses it.

**Q4 · INFO · Short's lower Tukey fence is exactly −Rs 3,950.425 and prints −Rs 3,950.42.**
`pf.format_paise` quantizes through `Decimal`, whose default is ROUND_HALF_EVEN — this repo's
standing convention (and the one REVIEW_6 recorded as an unstated silence in a different engine).
Nothing is wrong; recorded because a reader recomputing the fence half-up lands on .43 and would
think the page had drifted.

### Code

**C4 · MEDIUM · finding Q6's fix can be reverted in the cell with all 2,168 tests green.**
B289 put the measured base in the DATA (`RefusalClass.days_measured`) — which is right — and three
things quote it: the column header, the paragraph beneath the table, and the evidence sentence.
**Nothing reads the rendered cell.** Changing `_section_take_all` to print `item.rows` there
instead puts **210** back where **105** belongs, reinstating the exact *"13 of 210"* reading
REVIEW_9B_REPORT's Q6 was raised for, and **the whole shipped suite stays green** — mutation
M6, run against all of `tests/` with this review's own probe file ignored: **SURVIVED, 2168
passed.** It is the same shape of hole REVIEW_9B_REPORT found at `_side_split_over_walked_days`'
call site and that this span's own AST pin (B287) was written to prevent elsewhere: the fix is
pinned at the data, not at the page. **CLOSED by a kept probe** that reads the fourth column of a
priced row and the dashes of an unpriced one, verified RED against M6 and green at HEAD.

**C1 · INFO · `concurrency_closing_first`'s running count goes negative on a zero-length holding —
and provably cannot reach the answer.**
The sweep sorts on `(stamp, kind)` with CLOSE ahead of OPEN and applies that rule to a trade's own
two events as well. **16 executed rows in this ledger carry `exit_close_stamp == entry_close_stamp`**
(the entry-candle square-off shape B159 named), and the running position count reaches **−16** —
a concurrency that cannot exist. It cannot affect the published figure, and that is a proof rather
than an observation: after every event at a stamp the count is exactly `#{entry ≤ T < exit}`, and
the maximum is read at that stamp's last OPEN, so the transient is always undone before it is
read. Confirmed empirically as well — re-running the sweep with each same-stamp trade's own open
ordered first returns **the identical 77 at 2026-03-20 12:30 carrying Rs 18,698,137.26**, with a
minimum running count of 0. What the transient *can* corrupt is the unused `symbols` tuple on
`ConcurrencyPeak`: `live[symbol]` may be popped for a symbol still holding another position. The
report prints positions, stamp and notional and never that tuple. **Pinned by a kept probe** that
also shows a zero-length holding is exactly where the two conventions diverge (half-open 0,
open-first 1).

**C2 · LOW · section 1's headline coverage figure is a string literal beside a computed one.**
The corrected sentence prints **93.9317%** twice as text while the narrower quantity next to it is
computed (`_gate1p_share`, from the register the report already read). 93.9317% is derivable from
the same object — 409,205 settled `usable_pass` over 435,641 whole-lake stored days, recomputed
here to the digit — so the asymmetry is a choice, not a constraint. The new shipped test asserts
`"93.9317% USABLE" in text`, which pins the literal **to itself**: if the register moved, section 9
would move, section 1 would not, and the suite would stay green. This is REVIEW_9B_REPORT's C4/C6
defect class, in a line this span rewrote with the register in hand. Pre-existing as a figure;
in-scope as an opportunity that was open and not taken.

**C3 · INFO · a docstring left behind by the freeze's own tightening.**
`tests/test_report_9b_numeric_freeze.py:42` still reads *"2,455 tokens, in order"*. `814bdb3`
raised the count to **2,457** by dropping the `| Worst year |` exclusion — the assertion, the
message beneath it and the JSON were all updated; this one line was not. Nothing depends on it;
it is the only sentence in the span that disagrees with the artefact it describes.

---

## KEPT PROBES

`tests/test_review9b_final_probes.py` — **6 tests**. Suite **2168 -> 2174 passed / 0 failed / 0 skipped** (394s). No existing test, no `src/` file, no fixture, no store and no earlier session's
evidence artefact was modified.

| Probe | What it closes |
|---|---|
| `test_the_reports_Q23_quote_is_NOT_verbatim_against_the_QUESTIONS_md_record` | **Q1** — pins the divergence in both directions, and asserts those two edits are the WHOLE of it |
| `test_the_benchmark_factor_TALLY_counts_symbols_the_benchmark_itself_EXCLUDES` | **Q2** — a symbol with no first-day close carries a bonus: counted by the tally, applied to nothing |
| `test_a_ZERO_LENGTH_holding_is_where_the_two_concurrency_conventions_diverge` | **C1** — the transient, the proof the maximum survives it, and the shape the two conventions differ on |
| `test_the_partial_year_marker_follows_the_LAST_year_of_a_ten_year_span` | **B288** on the side the shipped fixture reaches only for the worst-year row |
| `test_the_numeric_freeze_is_not_VACUOUS_the_pre_edit_report_fails_it` | the freeze's other direction, against the committed pre-edit blob through `git show` |
| `test_the_priced_refusal_rows_RENDER_the_measured_base_and_not_the_full_day_count` | **C4** — reads the cell M6 proved nothing reads |

Three of the six are **documentation probes** in the shape REVIEW_9B_REPORT established: they
turn a finding into arithmetic a future session inherits rather than prose it can skim, and they
go red the moment the finding is fixed — which makes fixing it a deliberate act.

---

## WHAT IS OWED

1. **Three one-line prose edits before the report reaches the trader** — Q1 (restore the ruling's
   own words), Q2 (scope the factor tally to the benchmark's members), Q3 (stop attributing the
   half-open concurrency to the 15-minute path). **No number moves**, and the numeric freeze will
   prove that again: none of the three lines is in sections 1..9.
2. **C4 is closed by a kept probe and needs no source change**, but it is worth the next session's
   eye: this is the second span running in which a correction has been pinned at the helper and
   not at the page, and the pattern is now three for three (REVIEW_9B_REPORT M1, and M6 here).
3. Optional, and cheap: C2 (compute 93.9317% from the register) and C3 (the stale docstring).
4. **Q43 and Q44 remain OPEN with the trader**, and both stamps ride on every output verbatim.
5. `STATUS.md` and `PROGRESS.md` repeat Q2's 125/86 phrasing; whatever is decided for the report
   should reach them.

---

*Reviewer's note: this review changed no source file, no test of an earlier session, no fixture
and no store. It added this document, one probe file (6 tests), and the STATUS/PROGRESS lines every
session owes. Every regeneration and every re-run of an earlier session's script went to the scratchpad;
the run directory's mtimes and the ledger's sha256 are unchanged.*
