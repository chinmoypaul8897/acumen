# REVIEW_12C — chunk 12, the REVIEW_12_2 FIX re-review

**Span** `adaedbc..d893500` (10 commits, `ad48ff1` included and audited) · **QC, BOTH personas**
(`personas/quant_reviewer.md`, `personas/code_reviewer.md`) · fresh session, 07-Aug-2026 ·
stores READ-ONLY throughout.

**VERDICT: PASS.** REVIEW_12_2's two blocking findings are executed and both are executed
correctly. Page 5's reconciliation now closes, and this review re-derived every one of its
figures from the ledger with a streamer that imports nothing from `src/acumen` — the arithmetic
is exact, the two-day overlap that makes it exact is real, measured and stated on the page, and
the 13,113 population it discloses is the one the ledger holds. `config.yaml` is edited, its
values untouched, with the single surviving *pending* naming the frozen manifest on purpose. The
pack, its companion and the points table byte-reproduce from a clean clone with empty diffs; the
report is untouched and still hashes `529a04a887d2b69a…`. **Not one published figure moved that
should not have, and every figure that arrived was re-derived here independently.** Five
findings, none blocking, and the one that matters is a missing GUARD on a correct document
rather than a wrong number.

**The block REVIEW_12_2 placed on the pack is LIFTED. The pack is cleared to go to the trader.**

---

## PART 0 — RECORDING (architect-directed, own commits, made before the review proper)

**0a · `3415d75` — CONTEXT section 10's erratum row, the supplied three-cell line.** The row
committed in `adaedbc` had two cells in a three-column table, which B317 recorded verbatim and
Q-27 raised. It now reads `| 1.9e | 07-Aug-2026 | §9 OPEN-6 aligned with the Round-4 flags
retirement |` — three cells, the version labelled `1.9e` so it cannot read as a second `1.9`,
the change text unchanged and back in the Change column. Committed alone, as every CONTEXT
commit is. No section moved; the header stays `Version 1.9`. **Q-27 answered, B317 DISCHARGED.**

**0b · `ef114fb` — the architect's three rulings of 07-Aug-2026, word for word** in QUESTIONS.md,
with this session's reading kept strictly outside the quotation marks. **Q-26 is CLOSED** — the
report stays frozen, `docs/evidence/chunk12_fix_review12_2_measurements.{py,json}` is the
technical record of the FORCEMOT boundary case and page 5's clause is its pointer; the fix
direction's *"detail in the technical report"* parenthetical is amended by the architect, so
B324 stands and no freeze exclusion is owed. **B318 is RATIFIED.** **The OPERATOR RULE** — no
session starts while another is alive, terminal closed AND no surviving process, checked before
every launch — is recorded against the `ad48ff1` concurrency incident (PART 4).

---

## PART 1 — WHAT THIS REVIEW RE-DERIVED, AND FOUND EXACT

Everything below was computed by code written for this review that **imports nothing from
`src/acumen`**, read from the raw JSONL ledger
(`c70a72b097879914a3026331c1e651b70c7e6052327d0f34121fd30909a4d134`, re-hashed here) and the
parquet daily store, read-only. Agreement is evidence, not tautology.

### 1 · PAGE 5, re-derived line by line by an independent streamer

| what the page says | independently measured | |
|---|---|---|
| walked **495,312** stock-days | 495,312 ledger rows | OK |
| **1,632** carry no rule at all | 1,632 rows with `bias_rule` null | OK |
| that leaves **493,680** in the table | 495,312 − 1,632 = 493,680 | OK |
| **406,488** judged | 406,488 rows `status: evaluated` | OK |
| **74,081** in the 3 *not judged* rows | 73,841 + 210 + 30 = 74,081 | OK |
| **13,111** settled a bias, then refused | 493,680 − 406,488 − 74,081 = 13,111 | OK |
| the sum **406,488 + 74,081 + 13,111 = 493,680** | closes exactly | OK |
| the overlap is **2 days** | `no-data` × `evaluated` = 2; `minutes-ungated` 0; `suppressed` 0 | OK |
| **the true population is 13,113** | refused rows outside the three rows = 13,113 | OK |

All ten bias-rule rows reproduce to the day: rule-1 285,574 · no-data 73,841 · inside-bar 64,819
· rule-2 62,385 · rule-3-outside 6,724 · minutes-ungated 210 · rule-3-tie 62 · suppressed 30 ·
rule-3-no-1min 30 · rule-3-no-break 5, summing to 493,680.

**The 13,113, by rule** — and it is REVIEW_12_2's own breakdown, which summed to 13,113 while
that review's prose called it 13,111: rule-1 9,033 + inside-bar 2,139 + rule-2 1,858 +
rule-3-outside 60 + rule-3-no-1min 23 = **13,113**. The fix session read the parts, not the
prose, and its page is right. (The 98-row difference between "refused carrying a rule" and
"refused carrying a non-null bias" is inside-bar carries before seeding, CONTEXT 3.2.)

**The overlap, from the stores.** Both rows are FORCEMOT, **2024-02-14 and 2024-02-15**, both
`bias: bearish` (carried), both `status: evaluated`, minute counts 360 and 368, outcome
`no-trade-armed-but-no-qualifying-close`, `executed: false`, `signalled: false` — **judged,
eligible, and neither traded**, exactly as the page says. FORCEMOT's daily store holds **1,648
EQ rows, 2019-08-19 → 2026-07-30, with exactly one gap over five days: 2023-10-25 → 2024-02-14,
112 calendar days.** The mechanism is visible in the store: February 2024 rows resume on the
14th, so `bias_pair(2024-02-14)` = (02-13, 02-12) — both absent — and `bias_pair(2024-02-15)` =
(02-14 present, 02-13 absent). From 2024-02-16 both pair days exist and the engine resumes.
**Exactly two boundary days, not one and not three.**

**The rest of the paragraph, checked as prose.** *"1,632 … days the market was not open in the
normal way (a Muhurat session, say)"* — all 1,632 carry the reason `CONTEXT 7-E2 non-standard
session (stored candles outside 09:15-15:30)`, on **8 distinct dates × 204 symbols**, every one
of them a Diwali Muhurat session. *"406,488 … a bias was settled"* — **zero** evaluated rows
carry a null bias, so the claim is exactly true. Page 5's later sentence *"of the 495,312 …
406,488 were judged and 88,824 were refused"* reconciles: 88,824 = 87,192 rule-carrying refusals
+ 1,632 ruleless ones.

**The clean partition B318 declined** is real and is what it would have cost: 406,486 + 74,081 +
13,113 = 493,680, moving 406,488 — a headline on four pages. The architect has now ratified the
stated-overlap form.

### 2 · Q2's relabel, and Q3's counts

`bias_engine.py:310` emits `no-data` when `_candle()` — which is `self.store.daily(...)` —
returns nothing for `pair.current` (D−1) or `pair.previous` (D−2), both trading days from the
calendar. The new label, *"no DAILY candle for the bias pair (the two days before) -- not
judged"*, names the right store, the right resolution and the right days. The old one named none
of the three.

Q3, recounted from the ledger: **988** trades ended exactly level in points, across **171** of
the **204** stocks; **61,406** of **188,345** are positive; 125,951 negative; 61,406 + 988 +
125,951 = 188,345. 61,406/188,345 = **32.60%**. Page 1's own flats re-derive too — 59,385
positive in MONEY, **40** level, 188,305 deciding — so the two pages' constructions agree and
the new sentence's cross-reference is sound.

### 3 · C1 — the config diff

`git diff adaedbc..HEAD -- config.yaml` touches comments only: **no value line changes**, both
keys are still valueless (`capital_reference:` / `margin_basis:` load as `None`), and both now
read `# null -- retired by trader, Round 4`. **Exactly one occurrence of "pending" survives**, at
line 45, and it explains itself in place — it names the RUN's frozen manifest, kept byte-exact
under B305 and quoted by two published documents. The append-only corrections read as recorded:
QUESTIONS.md's ROUND-4 block carries the false EXECUTED bullet untouched with the review's
correction and then the fix's execution appended beneath it, and STATUS.md's chunk-12 line
records the same.

### 4 · C4 both ways, C7 against its own rows, C8's pin, C5's lesson

**C4, pre-fix** (`git archive adaedbc`): `python -m acumen.trader_pack --out … --json … --points
…` → **exit 0, three files not created, nothing printed**; `python -m acumen.report_9b --out …`
→ **exit 0, nothing written**. **C4, post-fix** (HEAD, a run label with no ledger): both **exit
1** and name the missing path — `No run ledger at …\no_such_run_12c\ledger.jsonl`. The guard
propagates `main()`'s code, which the AST test pins, and `confirm_written` reads every document
back and compares BYTES (three documents in `trader_pack.main`, one in `report_9b.main`).

**C7** — the seven rows, each against its own *Points* cell and re-derived from the ledger:

| stock | trades | points | exact average (rupees) | printed |
|---|---:|---:|---:|---:|
| ABCAPITAL | 948 | +4.71 | +0.004968 | **+0.00** |
| RVNL | 802 | +3.99 | +0.004975 | **+0.00** |
| BANKBARODA | 1,138 | +2.55 | +0.002241 | **+0.00** |
| GODREJCP | 1,109 | −0.06 | −0.000054 | **−0.00** |
| IRFC | 635 | −0.39 | −0.000614 | **−0.00** |
| ASHOKLEY | 1,079 | −2.82 | −0.002614 | **−0.00** |
| UNIONBANK | 1,098 | −3.90 | −0.003552 | **−0.00** |

Every sign matches its row's own total; **no eighth row rounds away** (nothing else in the 204 is
under half a paisa); **no stock's ten-year total is exactly zero**, so the unsigned form should
not appear and does not — `| 0.00 |` occurs zero times in the committed table. No magnitude moved
anywhere: the whole-file token diff of the points table is four `0.00` out, four `-0.00` in.

**C8** is PINNED, not fixed, as the fix direction asked, and the pin drives all three cases: two
safe orderings and the unreachable `TypeError`, with CONTEXT 3.4 / R1-Q16 named as the only
reason it is unreachable.

**C5's lesson is applied and it holds.** Both flipped probes were run here against the COMMITTED
PRE-FIX artefacts (`git archive adaedbc` with HEAD's two test files dropped in). Both are RED
there, and **each fails on its own page-text assertion** — *"the defective sentence is gone from
the document the trader receives"* and *"the sentence REVIEW_12_2 Q1 found to be wrong is GONE
from the trader's page"* — not on a `KeyError` for a field the fix added, which is how three of
the last five died. Verified by reading the source too: in both probes every pre-existing
companion key is read before the page assertions and every fix-added key after them.

### 5 · PAGE 6's gap sentence, recomputed

**2,068 executed gap entries = 850 long + 1,218 short**, and **zero** stop-side violations,
computed here in HALF PAISE off the ledger's own `poc_half_paise` (confirmed to be 2× paise on
sampled rows) so the off-grid POC is never rounded: long `stop×2 ≤ poc_half`, short
`stop×2 ≥ poc_half`. The census the page prints agrees to the row.

**The losing branch exists and the tests drive it.**
`test_page_6_reports_the_gap_stop_check_and_has_a_LOSING_branch` renders page 6 twice over a
synthetic census and asserts *"on 1 of them the stop sat on the WRONG side of the POC"* and
*"That is a defect and it is printed here"* — asserted at the RENDERED page, not at the census.
The overlap clause is driven the same way at four combinations (one stock / several, traded /
not). See Q1 below for what the property is worth.

### 6 · The numeric-token accounting, re-derived

Whole-file token diff of the pack, `adaedbc` → `d893500` (961 → 994 tokens):
**DEPARTURES = exactly `{87,192}`, one token, the defective sentence's own figure.** Every one
of the 34 arrivals is classified, none unclassified: 25 are extra occurrences of figures already
published in the pre-fix pack (`188,345`, `204`, `406,488`, `493,680` ×2, `73,841`, `210`, `30`,
`32.60`, `988`, `1` ×2, `2` ×2, `3`, `4`, `15`, `2024` ×2) and 9 are the fix's own new
disclosures — `74,081` ×3, `13,111` ×3, `13,113`, `988` (new occurrences), `171`, `61,406`,
`2,068`, `850`, `1,218`, `14` — **each of which this review re-derived from the ledger above**.
Not one arrival is a changed magnitude. The points table: four `0.00` out, four `-0.00` in, plus
Q3's sentence — no magnitude either.

**Byte-reproduction, once each, from a clean clone to scratch paths.** `acumen.trader_pack`
through the `python -m` entry point C4 created: `trader_pack.md`, `trader_pack.json` and
`points_by_symbol.md` all **IDENTICAL**, diffs empty, sha256 `9419ccb53eee6225…` (53,377 B),
`14ce2cc02f4d1f5d…` and `773cf2a1d51618e6…` (24,017 B) — the fix session's three hashes to the
digit. **The report was NOT regenerated, by instruction, and is verified by hash instead**: it is
untouched anywhere in the span (`git rev-parse adaedbc:… == HEAD:…`, same blob), 87,756 B, 899
lines, sha256 `529a04a887d2b69a6f349fbd43a26d1ce2e6de0c8f544d144ec17abc5ea999a9` — the claimed
digest exactly.

**And the whole 204-row companion re-derived, not sampled.** Every row rebuilt from the ledger
from the page's own definitions (points signed by side; positives over ALL of a stock's trades;
drawdown as the deepest fall in the running total walked in date order, peak seeded at zero;
best and worst with their dates) and formatted independently: **204 rows × 11 fields = 2,244
published figures, ZERO mismatches**, ranking order identical to `(−points, symbol)`.

### 7 · The standard sweep

* **Suite from clean: `2279 passed / 0 failed / 0 skipped`** in 425.12s, from a fresh
  `git clone` of the repository — the fix session's claimed count to the test. No skips, no
  xfails. With this review's 4 kept probes: **2,283 / 0 / 0**.
* **Test-function audit by AST over both revisions: 1,547 → 1,556.** One name removed, ten added
  = **9 new, 1 renamed, ZERO removed**, exactly as claimed; the rename is the flipped pin
  (`…_does_NOT_close` → `…_now_CLOSES`). Three surviving tests changed bodies, all three
  inspected: two are the ruling-driven `SPEC_VERSION` substitution (v1.8 → v1.9, constant and
  both pins moving together, C2) and one is the re-flipped REVIEW_12 probe. The freeze test
  gained a docstring paragraph (C6's scope statement) and no assertion. **No test weakened,
  deleted, skipped or loosened.**
* **Fixtures:** `tests/fixtures/` and `poc/data/` untouched — zero files in the span diff.
* **Engines:** `bias`, `bias_engine`, `poc`, `signals`, `simulate` — zero files touched.
* **Hygiene:** no AI attribution in any added line or any commit message (the only matches are
  the permitted `CLAUDE.md` citations); `.env` untracked, gitignored, and none of its three
  values appears anywhere in the span; every commit touching `src/` or `tests/` carries
  `(unreviewed)`, and the four that do not touch code correctly need none.
* **SHA chain:** linear, zero merges, `adaedbc → … → d893500`, and local was identical to
  `origin/main` at the start of this session.
* **Stores: ZERO writes.** 22,186 files under `data_root` fingerprinted (path + size +
  mtime_ns) before any work and again after everything — full ledger streams, a complete pack
  regeneration, four suite runs and five mutation runs — **byte-identical, digest
  `7ea13480266ebd04…` both times.**

---

## PART 2 — FINDINGS

### M1 · MEDIUM · code · **three of the four page-text fixes are pinned at the helper and not at the rendered output; Q3's is unpinned at both levels**

`personas/code_reviewer.md` checklist item 10 — the architect's 06-Aug-2026 ruling (2), added
after the pattern had occurred three times — says *"a rendering fix is pinned at the RENDERED
OUTPUT, not only at the helper that computes it"*. Of the fix's four page-text changes, only
Q1's page-5 paragraph is. **Measured by mutation, not argued:**

| mutation | what should catch it | result |
|---|---|---|
| Q2's label reverted in the committed page | any probe reading the printed table | **104 passed** |
| Q3's sentence deleted from BOTH committed documents | any probe reading page 7 | **108 passed** |
| Q3's two `emit.add` blocks deleted from the GENERATOR | any test rendering page 7 | **104 passed** |
| C7's seven signed zeros stripped in the committed table | any probe reading a cell | **108 passed** |
| C7's helper reverted in `points_view.py` | the helper's own probe | **RED** (correctly) |

Q2 and C7 are caught at the source, so a code revert cannot pass — but the trader's document can
lose either change with the suite green, and the only probe that reads the printed bias table
selects its rows by the words *not judged*, which the wrong label contains too. **Q3 is worse:
it is revertible at both levels**, because its only guard asserts `PointsTotals.flat` and
`.symbols_with_a_flat` in the dataclass, and nothing reads the sentence those fields exist to
produce. That is the M1/M6 shape at its fourth occurrence.

Nothing printed is wrong: all three changes are on both documents today and every figure in them
re-derives exactly (PART 1). What is missing is the guard. **This review writes the four probes
that close it and keeps them** (PART 5), each proven RED against its own mutation and green as
committed. Recorded as a finding rather than only as a test, because the ruling is not landing
by itself and the architect should know it is now four deep.

### C1 · LOW · code · **both `__main__` guards claim a subprocess test that does not exist**

`src/acumen/trader_pack.py:2462` and `src/acumen/report_9b.py:2586` both read
`if __name__ == "__main__":  # pragma: no cover -- exercised as a subprocess in the tests`. **No
test launches either module as a subprocess.** The test that covers C4 says so itself:
*"Asserted at the source rather than by launching a subprocess: a real invocation reads the
ledger and the stores and takes many minutes"*. The two comments describe a verification that
was deliberately not written, and they are the only account of the guard a future reader has.

Mitigating, and it is most of the finding: the guard genuinely works — this review ran both
modules through `python -m` in both directions (PART 1 item 4) — and the AST test pins its
presence and that it propagates `main()`'s exit code. Only the comment is wrong, and it is wrong
in exactly the direction this repo's recording discipline exists to prevent. One word each
(`exercised` → `asserted at the source`, or the pragma dropped) fixes it.

### C2 · LOW · code · **the generators fail with a traceback where the other runnable modules return 1**

Post-fix, a missing ledger reaches the operator as an uncaught `acumen.backtest.BacktestError`
traceback. Exit 1 and the missing path are both correct, so C4 is discharged; but
`run_backtest.main` — the model these two just joined on `[project.scripts]` — prints its
preflight and `return 1`s cleanly. For the two documents a human decision rests on, the operator
who typed the command deserves the same one-line answer. Cosmetic, non-blocking, and arguably a
traceback carries more information; recorded for consistency rather than for correctness.

### Q1 · INFO · quant · **page 6's zero gap-stop violations is guaranteed by construction**

The trader's Round-4 constraint puts the gap stop at or beyond the POC on the correct side. On
the ARMED path a close strictly beyond the POC IS the trigger, so every close between arming and
entry — including the one the gap stop is taken from — is on the near side by construction, and
the short mirror holds. So **2,068 of 2,068 is a tautology of CONTEXT 3.4, not independent
evidence about the strategy**, and its value is as a regression tripwire on the implementation.
The page does not overclaim — it says the rule *"was checked against every gap trade"*, which is
true — and B319 gave the verdict a losing branch that the tests drive, which is exactly the right
build for a property that is currently unfalsifiable by the data. Recorded so a future reader
does not mistake the zero for a finding about the market.

### Q2 · INFO · quant · **the overlap clause's parenthetical can be read as the hole's span**

Page 5 reads *"at the edge of a long hole in that one stock's daily history (Wednesday 14
February 2024 to Thursday 15 February 2024)"*. The two dates are the two OVERLAP DAYS; the hole
is 112 calendar days, 2023-10-25 → 2024-02-14. Grammatically the parenthetical lands against
*"a long hole … daily history"*, so a careful non-technical reader can take the long hole to be
the two days named beside it — which would make *"long"* read as an error. In the multi-stock
branch (*"across 3 stocks (… to …)"*) the same construction is unambiguous, so this is a
single-stock-branch wording matter and nothing is false. One word (*"on Wednesday 14 February
2024 and Thursday 15 February 2024"*) would settle it.

### C3 · INFO · code · **`d893500` calls itself an append-only correction while rewriting two committed lines in place**

The self-correction rewrote the fix entry's `scope:` and `state-for-next-session:` lines and the
chunk-12 STATUS line rather than appending beside them, which is what QUESTIONS.md's twin C1
corrections did. No record is lost — the replacement text carries the correction explicitly
inside the entry (*"CORRECTION TO THIS ENTRY'S OWN FIRST DRAFT"*), the earlier wording stands in
`3a6f85a`, and the commit message is candid about what was wrong and why. There is also no
file-level append-only rule for PROGRESS.md, unlike QUESTIONS.md, so this is not a rule breach.
The label simply overreaches its own edit.

---

## PART 3 — CLASS-B DECISIONS (B317–B324)

| | verdict | |
|---|---|---|
| **B317** the erratum row written verbatim despite its two cells | **APPROVED, and DISCHARGED** | Exactly the right refusal — a session does not reword CONTEXT to make it fit, it raises Q-27. The architect supplied the three-cell line and PART 0a executes it. |
| **B318** the stated-overlap split, not a clean partition | **APPROVED, and now RATIFIED by the architect** | The clean partition exists and this review computed it (406,486 + 74,081 + 13,113); it moves a four-page headline. The clause is what makes the stated form exactly true, and without it the sum would close by absorbing the 2 in silence — the same defect wearing a new sentence, as B318 itself says. |
| **B319** the page-6 verdict and the overlap clause COMPUTED, with losing branches | **APPROVED** | Both branches are driven at the RENDERED page, at four combinations for the clause. The right build for two properties whose current answer is the flattering one (see Q1). |
| **B320** not-judged rows selected by the page's own WORDS | **APPROVED** | Verified in the data: `suppressed` and `rule-3-no-1min-carry` both count 30, so a count-keyed selection really would pick the wrong row, and only one of the two carries *not judged*. The two-way constant/label test is the right lock. |
| **B321** C7's sign taken from the value handed in | **APPROVED** | Seven cells, signs matching their own totals, no magnitude moved, no eighth row, and an exact zero would still print unsigned. See M1 for the guard. |
| **B322** C8 PINNED, not fixed | **APPROVED** | What the fix direction asked for, and the pin names CONTEXT 3.4 / R1-Q16 as the reason it is unreachable, so the day it becomes reachable the test explains itself. |
| **B323** `confirm_written` in `report_9b`, reused by `trader_pack` | **APPROVED** | No duplication across a dependency that already exists, and the check is on BYTES rather than characters, which is the version that catches a short write on a non-ASCII page. |
| **B324** the Q2 boundary detail on the pack, not in the report | **APPROVED, and now RATIFIED** | The reasoning was right before the ruling arrived: writing it into the frozen region would have forced new exclusions and contradicted the same instruction's *"No number in any headline moves"*. Raising Q-26 rather than deciding was the correct move; the architect has now amended the direction. |

---

## PART 4 — THE CONCURRENCY INCIDENT, VERIFIED AND JUDGED

**What happened.** The REVIEW_12_2 session was still alive while the fix session worked: its
report generator (PID 9660, started 09:58) was still running, and at 11:45 it committed
`ad48ff1`, touching STATUS.md, PROGRESS.md and `docs/reviews/REVIEW_12_2.md` — three files the
fix session also edits. plan.md §2 says one session runs at a time, and gives its reason in the
same sentence: *"so PROGRESS.md/STATUS.md never conflict"*. Two ran, and those are the exact two
files that conflicted.

**The no-clobber claim, verified rather than accepted.** Comparing `ad48ff1` with `d893500` over
those three files, line by line:

* **STATUS.md** — 52 → 53 lines, **exactly ONE line removed** (the chunk-12 line) and two added.
  The removed line is re-added under `# superseded 2026-08-07 by the REVIEW_12_2 FIX session: `
  and its 7,756 bytes are **carried through byte for byte** — verified by string equality, not by
  eye — including `ad48ff1`'s own correction (`529a04a887d2b69a`, `87,756`, `BYTE-REPRODUCE` all
  present in the carried text).
* **PROGRESS.md** — **ZERO lines removed**, 18 added.
* **`docs/reviews/REVIEW_12_2.md`** — **ZERO lines changed** after `ad48ff1`, so the review
  session's own correction of its report-reproduction claim survives untouched.

**The judgment.** The handling was correct at both ends and the process was not. `ad48ff1`
committed only its own three files and said so; the fix session re-read every record at the
moment it edited it, which is the only reason nothing was lost, and it said that too — *"It
worked out because this session read every record fresh … a session that had cached its reads at
the start would have overwritten another session's commit."* It then reported the deviation
rather than judging it, which is the right division of labour. The architect's OPERATOR RULE
(PART 0b) now closes it, and it is the operator's rule, not a session's: no session starts while
another is alive, terminal closed AND no surviving process, checked before every launch.

**The (h) self-correction.** `d893500` is honest and it is prompt: the fix session had claimed to
discharge a verification that the review session had in fact discharged an hour earlier, and it
corrected that inside its own entry, in its own commit, one commit later. This review's only
reservation is the label, recorded as finding C3: the correction is *stated* append-only and
*made* by rewriting two committed lines. Nothing is lost and no rule is broken; the word is
simply larger than the edit.

**One factual correction the fix session made to REVIEW_12_2 is upheld.** C4 said the two
documents were *"regenerable only by importing the module and calling `main()` by hand"*; the
committed launchers `docs/validation/trader_pack.py` and `docs/reports/chunk9b_backtest_report.py`
already did exactly that. The finding's core stands and was proved again here: `python -m` really
did exit 0 having written nothing.

---

## PART 5 — TESTS THIS REVIEW ADDS AND KEEPS

`tests/test_review12c_probes.py` — 4 tests, all green, offline, no store read. All four close
M1, at the RENDERED OUTPUT, on the documents the trader actually receives; each was proved RED
against its own mutation and each fails on its own page-text assertion.

1. **`test_page_5s_no_data_row_names_the_DAILY_pair_ON_THE_PAGE_ITSELF`** — Q2's relabel, in the
   printed table row, selected by the companion's own count.
2. **`test_page_7_AND_its_companion_state_the_FLAT_trades_on_the_page_itself`** — Q3's sentence
   on BOTH documents, with its figures read from the companion rather than typed, plus the
   identity that makes it true.
3. **`test_a_points_a_trade_cell_that_rounds_to_zero_KEEPS_its_sign`** — C7 in the CELL: every
   rounded-away cell carries a sign, and it is the sign of that row's own *Points* total.
4. **`test_the_overlap_days_page_5_counts_are_NAMED_on_the_traders_page`** — the architect's
   Q-26 ruling pinned: the pack's clause is the pointer, so the count, the stock and the "none of
   them traded" verdict must be on the page, all taken from the companion.

No existing test was modified, weakened, skipped or deleted by this review. No fixture byte
moved. No `src/` file was touched.

---

## VERDICT

**PASS.**

REVIEW_12_2 failed this chunk on two things: a paragraph that asked a non-technical trader to
check an arithmetic that was out by 74,081, with a probe holding the wrong wording in place; and
an architect ruling recorded as executed that had not been. Both are fixed, and both are fixed in
the way that survives inspection rather than the way that goes green. The reconciliation closes
and this review closed it independently from the ledger; the overlap that makes it close is real,
is two days, is FORCEMOT at the edge of a 112-day hole, and is on the page instead of inside the
arithmetic; `config.yaml` is edited with its values untouched and its one surviving *pending*
explaining itself. The engines were not touched, no fixture moved, no test was weakened, the
suite is 2,279 green from clean, the three regenerable artefacts byte-reproduce with empty diffs,
the report is untouched at its claimed digest, and the stores took zero writes across everything
this session ran.

Five findings, none blocking. M1 is a missing guard on a correct document and this review keeps
the four probes that close it; C1, C2, Q1, Q2 and C3 are smaller than that.

**The block REVIEW_12_2 placed on the pack is LIFTED. The pack is CLEARED FOR THE TRADER.** The
chunk-12 trader gate itself remains open in the only sense that matters — it closes on his
confirmation of the rules on page 2 and his row count on day 3f, which is what the pack asks him
for.

`docs/reviews/REVIEW_12C.md` · tag `chunk12-round4-pass`
