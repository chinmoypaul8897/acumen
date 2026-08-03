# REVIEW_9B_FIXES -- QC review of the chunk-9B RUN-CRASH FIX ARC

**Span reviewed:** `20b45c9..a707615` (14 commits) -- FIX-1 (Q-21 malformed-bar refusal + the
progress reporter), FIX-2 (Q-21(b) bias-evidence gating + the Q-21(a) measurement), FIX-3
(Q-21(a) gate-2 completion + CONTEXT v1.6).
**Personas:** `personas/quant_reviewer.md` and `personas/code_reviewer.md`, both worked in full.
**Session:** fresh review session, 2026-08-03. No `src/` file, no existing test and no fixture
was modified. Every mutation ran inside a `git archive a707615` COPY under the scratchpad.
**ZERO store writes**: every access to `<data_root>` was a read; no file under it was created,
renamed, moved or deleted, and no junction or symlink was made at any point (CLAUDE.md Q-18
layers 1 and 2).

---

## VERDICT

### The fix arc: **PASS**

All three architect rulings are implemented correctly, narrowly and exactly as written. Every
number the arc publishes reproduces from the machine. No CONTEXT deviation is introduced by the
diff, no test is weakened, no fixture byte moves, the pure engines are byte-identical, and the
git history, secrets hygiene and SHA chain are clean. `2094 passed / 0 failed / 0 skipped` from
clean (2,083 shipped + 11 probes this review keeps).

### The relaunch: **AUTHORISATION WITHHELD**, pending ONE architect ruling (new **Q-22**)

The brief asks this review to re-authorise the full-history run. I cannot, and the reason is not
in the arc's own work.

While tracing the arc's own claim that Q-21's third case stays reachable "through a malformed
OUT-OF-SESSION bar", I found and then MEASURED a **live CONTEXT deviation on the run path**: the
Rule-3 first-break scan consumes out-of-session 1-minute bars, which CONTEXT 4.6's Q-17 law says
must be dropped at the CANDLE level. On the real store this **flips the bias on two settled
symbols** (finding R1). It is PRE-EXISTING -- the pre-arc loader did the same, and the arc in
fact NARROWED it -- so it is not a defect of this chunk. But the relaunch writes the definitive
ten-year ledger that every downstream chunk and the trader's own decisions rest on, and I will
not certify a run that I have proven will record at least two wrong biases.

The remedy is one line and one ruling; both are the architect's, not this session's (CLAUDE.md
hard rule 1). **Q-22 is raised in QUESTIONS.md.** The moment it is ruled, the relaunch can
proceed -- nothing else in this arc blocks it.

---

## 1. Findings

Severity: **HIGH** = blocks. **MEDIUM** = must be recorded/actioned, does not block the arc.
**LOW** = noted. Findings that survived adversarial verification only are marked; several
plausible findings were REFUTED on re-measurement and are listed in section 5.

### R1 -- HIGH (pre-existing; blocks the RELAUNCH, not the arc) -- the Rule-3 scan consumes out-of-session bars, in breach of CONTEXT 4.6's Q-17 law

CONTEXT 4.6: *"Q-17 IS LAW: a stored 1-minute bar stamped outside 09:15..15:29 is dropped at the
CANDLE level, flagged and counted, never silently -- uniform for pre-open and post-close
strays."* CONTEXT 7-E2 says the same.

The **trading** path obeys it: `signal_engine.stock_day` and `backtest`'s 15-minute feed both
call `aggregate.in_session_bars`, and the row gets `FLAG_OUT_OF_SESSION_DROPPED`. The **bias**
path does not. `minute_store.minutes` applies no session filter; `backtest.candles_for` builds a
`bias.Candle` for every stored bar of D-1; `bias._first_break` walks them in stamp order with no
filter. So a stray bar votes on which of P's extremes "broke first" -- undropped, unflagged,
uncounted. `aggregate.in_session_bars`' own docstring asserts the opposite of what happens here.

**Measured on the real store (read-only).** Out-of-session bars in the lake fall on 13 dates in
a 25-symbol sample. Eight are the CONTEXT 7-E2 Muhurat sessions the run already removes from its
calendar (so they can be neither a trade day nor a D-1). Of the rest:

| D-1 | what it is | battery verdict | effect on the Rule-3 scan |
|---|---|---|---|
| 2020-12-08 | pre-open vendor garbage at 04:18/04:19/04:21, cumulative volumes | **FAILS gate 1** (gap -40% to -70%) | none -- the arc's own Q-21(b) gating now refuses these days outright |
| 2017-04-28 | one 09:14 print per symbol, market-wide | PASSES | 139 symbols carry it, 4 reach Rule 3, the stray decides the first break on 2 -- **0 biases change** |
| **2021-02-24** | the NSE outage day; session ran past 15:29; **NOT** one of the 8 removed dates | **PASSES** (152 of 174) | 8 reach Rule 3, and **2 biases FLIP** |

The two flips, both **settled** symbols, both caused by a bar stamped **15:44**:

| symbol | P.low (D-2 2021-02-23) | in-session low | 15:44 bar low | as shipped | if Q-17 were obeyed |
|---|---|---|---|---|---|
| GODREJCP | 67795 | 68000 (no break) | **67600** | `rule-3-outside-bar` -> **bearish** | `rule-3-no-break-carry` -> BULLISH |
| LAURUSLABS | 35815 | 35915 (no break) | **35810** | `rule-3-outside-bar` -> **bearish** | `rule-3-no-break-carry` -> BULLISH |

A flipped bias flips the day's trade direction (CONTEXT 3.4). This is quant checklist items 1
and 3, and it is real money.

**Scope caveat, stated rather than glossed:** I measured two dates over the settled universe and
sampled out-of-session dates over 25 symbols. The full population across all 204 symbols and the
whole span is **not** measured. The true number of affected biases is >= 2 and unknown.

**The remedy is small and bounded** -- `candles_for` calling `aggregate.in_session_bars` -- but
whether the Rule-3 scan drops stray candles is a CONTEXT question, so this session records it and
decides nothing. **QUESTIONS.md Q-22.** Kept probe:
`tests/test_review9b_fixes_probes.py::test_the_rule3_scan_consumes_out_of_session_bars_and_it_flips_a_REAL_bias`
(a tripwire on the open question -- it goes RED the day the architect rules the other way).

### R2 -- MEDIUM -- the Q-21(b) wiring is pinned by nothing; reverting it leaves the run ungated and the suite green

The entire Q-21(b) ruling rests on one production line, `backtest.build_runner`:
`minute_loader=gated_minute_loader(minute_store, pipeline)`. Every unit test reaches a runner
through `tests/test_backtest.py::make_runner`, which wires the gated loader **by hand**; nothing
exercises what `build_runner` -- the function `run_backtest.execute` actually calls -- hands the
runner. Reverting that one line to the bare loader leaves the full suite green while the
relaunch reads D-1's minutes with no battery in front of them: 210 trade days across 59 symbols
ride on it. Code-reviewer checklist item 1 on the most load-bearing line of the arc.
**CLOSED by kept probe** `test_build_runner_wires_the_GATED_minute_loader_not_the_bare_one`
(mutation-verified: the mutant now fails 2 tests).

### R3 -- MEDIUM -- Q-21's THIRD case has zero run-path coverage, and PROGRESS claims otherwise

The FIX-3 entry states the `minutes-malformed` machinery, flag and counter are *"kept and TESTED
for exactly that"* (a malformed pre-open print). The **reachability** half is true -- three
agents and I confirmed it dynamically. The **tested** half is not. Before FIX-3,
`test_q21_a_malformed_bar_refuses_the_day_and_counts_it_instead_of_crashing` asserted
`row.flags == (bt.FLAG_MALFORMED_MINUTE_BAR,)` and the manifest counter at 1. FIX-3 legitimately
retargeted both at the Q-21(b) case (the fixture day now fails gate 2), turning a live `1` into a
dead `0` -- and added no replacement. `FLAG_MALFORMED_MINUTE_BAR` now appears in `tests/` only in
a docstring and in a static allow-list. Consequence, mutation-verified by two agents
independently: suppressing the flag on a malformed-bar refusal (the day is still refused, the
reason still correct, but the manifest reports **zero**) passes all 2,083 tests. That is a silent
under-report of refused symbol-days, against the ruling's explicit *"counted ... rare-shape
counter in the manifest"*.

This is a coverage regression, not a weakened assertion -- for the NEW rule the replacement is
strictly stronger (see check 8a). **Partly closed** by kept probes
`test_both_q21_rare_shapes_are_counted_from_the_row_flags` and
`test_every_unusable_evidence_rule_has_a_flag_and_that_flag_is_a_rare_shape`, which pin the
derivation and the flag->counter join. The end-to-end `walk_symbol` assertion is left for the
builder to restore, since restoring it means authoring a new fixture and this session fixes
nothing.

### R4 -- MEDIUM -- the owed offline `--regate`, as documented, would re-gate 208 of 210 rows and overwrite the committed sealed report

B259 correctly bumps `GATE_DEFINITION` and correctly defers the re-gate to the operator (it is a
store write). But the command handed to the operator -- the bare
`acumen-universe-backfill --regate` in PROGRESS.md and in the constant's own comment -- has two
defects, both reproduced from the machine:

1. `run()` resolves the universe from the cached F&O endpoint (`<data_root>/nse/underlying_information.json`),
   which holds **208** symbols. The register holds **210** and *is* the sealed universe. The two
   missing symbols are **EXIDEIND** and **NUVAMA** -- exactly the pair the Q-18 T4 pass added on
   the sealed 210. They would keep the stale marker forever, and the regenerated report's
   aggregates would print `406,154 / 93.9058%`: neither the pre- nor the post-completion truth.
   CONTEXT 4.6's E5 clarification is explicit that a rebuild uses the sealed snapshot; the
   documented command does not pass `--universe-snapshot docs/recovery/sealed_universe_210.json`.
2. It omits `--report-path`, so it would overwrite `docs/backfill_minute_report.md` -- the
   git-tracked artefact `docs/recovery/q18_runbook.md` itself calls *"the one flag you must not
   omit ... including `--regate` re-runs"*. Recoverable via git, but it is a trap the repo's own
   runbook documents.

Additionally the report's staleness banner (`universe_backfill.py`) tells the reader the coverage
is *"understated"* for stale rows. For THIS marker move it is **overstated** (409,252 printed vs
409,205 true) and gate-1P numbers are present and unchanged -- the banner was written for the
Q-14 bump and was not revisited.

**This does not block the relaunch.** I traced it: `load_residual_register` is the run's ONLY
ledger reader and takes exactly five fields -- `status`, `gate1p_pass`, `gate1p_total`,
`gate1p_no_oracle`, `residual_reason`. The completion moves gate 2 alone; gate-1P is unchanged to
the day and `status` keys off the gate-1 effective rate, also unchanged. Nothing in `src/` or
`scripts/` reads `usable_pass` or `gate2_excluded` outside `universe_backfill.py` itself. So the
staleness is confined to figures no code consumes, and running the relaunch first is safe.

### R5 -- MEDIUM -- B259's marker, B248's clock and the honest `<=0` line were each pinned by nothing

Three separate constants the arc's own PROGRESS entries call load-bearing had no test that would
notice their removal (each mutation-verified in a private copy):

* dropping `+gate2-open-test-2026-08-03` from `GATE_DEFINITION` -- suite green. The only shipped
  assertions are self-referential (`record.gate_definition == ub.GATE_DEFINITION`) or satisfied by
  the pre-arc value (`"auction-relief" in ...`).
* reverting both `time.perf_counter` defaults to `time.monotonic` -- suite green. Every shipped
  reporter test injects a `FakeClock`, so none exercises the default, which is precisely the half
  of the FIX-1 fix this machine's 15.625 ms clock floor depends on (B248).
* reverting the `<= 0` branch to the old wording -- suite green; the branch is never entered by
  any shipped test. That wording is what claimed "no symbol walked yet" while the run was a
  hundred symbols deep.

**ALL THREE CLOSED** by kept probes, each mutation-verified to fail on its mutant.

### R6 -- MEDIUM -- B255 records a rationale the ruling does not support

B255 declines to gate chunk-8's `trade_evidence._minute_loader`, reasoning *"the ruling scopes to
the RUN"*. The Q-21(b) text recorded verbatim contains no such limiter: *"a day's minutes may
serve a Rule-3 first-break scan ONLY if that day passes the ... battery."* `trade_evidence` wires
a `BiasEngine` that performs Rule-3 scans, so on the ruling's own words it is in scope. The
DECISION (do not silently move a reviewed chunk's published number) is defensible and was
disclosed rather than taken quietly, which is the right instinct -- but whether the ruling reaches
a reviewed chunk's committed artefact is a spec-scope question and therefore the architect's.
**Judged APPROVED-WITH-CHALLENGE**; recorded under Q-22 for the architect alongside R1.

### R7 -- LOW -- the whole-lake malformed population is 51, not 48 and not 50

CONTEXT v1.6 4.6 carries *"The 48-bar population"*; QUESTIONS.md corrects it to 50 over the 210
processed symbols. Both are incomplete, and the second is incomplete for a structural reason: 50
is derived from the FLIP list -- days that change verdict under the completed enumeration -- which
cannot see a day the SEALED gate 2 already refused. I scanned all six quarantined symbols
(4,938,111 bars, read-only) and found **three** malformed bars, not two:

| symbol | stamp | O | H | L | C | fault |
|---|---|---|---|---|---|---|
| APLAPOLLO | 2017-10-05 15:28 | 1876000 | 1876000 | 1876000 | 1875000 | **C outside** (a SEALED clause) |
| APLAPOLLO | 2023-03-03 09:15 | 125625 | 126735 | 125680 | 126635 | O outside |
| UPL | 2023-03-03 09:15 | 70900 | 71400 | 70905 | 71190 | O outside |

So the lake carries **48 settled + 3 quarantined = 51**. **No figure moves**: the extra bar is on
a quarantined symbol, outside the run's universe and outside the coverage numerator, its day was
refused before v1.6 and after it, and its volume is 0. The FIX-3 claim that each extra bar is
*"the only one in its symbol's whole history"* is false for APLAPOLLO, which has two. Recorded,
not decided -- CONTEXT 4.6's population sentence is the architect's. Kept probe:
`test_the_quarantined_side_carries_THREE_malformed_bars_not_two`.

### R8 -- LOW -- CONTEXT v1.6 tensions (all architect-owned)

* 4.6 now carries two current coverage figures -- the v1.5 RE-SEALED bullet (`409,252 / 93.9425%`)
  and the v1.6 COMPLETION paragraph (`409,205 / 93.9317%`) -- with no supersedes marker, under a
  heading still labelled `(v1.5 ...)`. The document header is correctly `Version 1.6`, and the
  arithmetic of both is right, so this is a readability hazard rather than an error.
* 10's v1.6 row says *"Q-21(b) bias-evidence gating and Q-21 malformed-bar refusal recorded as
  law"*, but CONTEXT's body records neither rule -- the only Q-21 hits in CONTEXT are the v1.6
  edits themselves. Only the Q-21(a) ruling carried a spec instruction. By CONTEXT's own
  convention (the v1.5 row's identical phrasing came with real body bullets) a later session
  reading 10 would conclude the question is closed. **The wording is the architect's** -- the
  commit records the template applied as supplied -- so this is reported, not charged to the
  session.
* The 50-vs-48 hand-back sits under a heading marked `RULED ... executed`, so a session scanning
  QUESTIONS.md for open items will not see the CONTEXT edits still owed.

### R9 -- LOW -- reporting-shape defects in the new refusals

* `refused_by_reason` (manifest) and `SymbolRun.counts` key on the FULL reason string, and both
  Q-21 reasons embed the symbol, the date and the bar/gate detail. The pre-run measurement says
  210 such rows, so the full-history manifest gains ~210 singleton keys where the pre-arc shape
  aggregated (baseline: the smoke manifest has 6 keys over 62 refused rows). The rare-shape
  counters still aggregate correctly, so this is reporting, not correctness.
* The emitted reason reads `... gate gate 2 (candle integrity) ...` -- `UngatedMinuteDay.detail()`
  prefixes `gate ` onto a constant that already begins with the word. Cosmetic, but it will be
  frozen into ~210 ledger rows and is pinned by a shipped test, so it survives unless fixed now.
* `walk_symbol` does `flags=(UNRESOLVED_FLAG_BY_RULE[bias.rule],)` -- an unguarded lookup. A fifth
  case reaching the ledger without an entry would raise `KeyError` and kill the run: worse than
  the failure the ruling was written to remove. The B252 tripwire is the only defence and it does
  work (mutation-verified), but it discovers subclasses via `__subclasses__()`.
* `FLAG_OUT_OF_SESSION_DROPPED` is the most frequent rare shape in the lake (3,100 symbol-days)
  yet has no manifest counter, while eight rarer shapes carry zero-valued ones.

### R10 -- LOW -- disclosure precision

* *"the ledger's refused-row count is unchanged"* (QUESTIONS.md, PROGRESS.md, the gate-2 evidence)
  is true only of trade day 2023-03-06. Across the ledger the completion adds 47 refused
  symbol-days (those days as TRADE days), which the same documents state elsewhere.
* The disclosed cost of the arc is counted in ROWS. A refusal on a Rule-3 day also deletes a bias
  TRANSITION -- a Rule-3 day is the only place a carry can turn -- so later carry-days inherit the
  pre-refusal side. Not accounted anywhere.
* The 47 days the completion refuses were TRADE days that carried real trades: the crashed run's
  committed shards contain 18 of the 47 symbols and 7 executed on 2023-03-03 (net -369,860 paise).
  A legitimate and expected cost of "corrupt days are refused, never repaired", but priced only
  as coverage, never in trades or PnL.
* B257/B249 disclose the pilot pack's rare-shape staleness; `SPEC_VERSION` v1.5 -> v1.6 also makes
  the pack's Inputs row stale. "No NUMBER moves" survives literally, and I confirmed the
  substantive claim (290/146/88/56 is untouched).

---

## 2. Directed checks -- every one, with its result

**1. CASE 3 (malformed bar).** PASS.
The decisive-corruption fixture was re-derived from the pure engine, not by running the builder's
assert: repaired -> **BULLISH** (`Rule 3: P.high 200000 broken first`), skipped -> **BEARISH**
(`P.low 198000 broken first`), both `rule-3-outside-bar`, and the shape is a genuine CONTEXT 3.2
Rule 3 (inside-bar / R1 / R2 all decline). The JUBLFOOD bar re-read from the store is exactly
`O 44210 H 44440 L 44295 C 44295 V 12909`, open 85 paise below the low; the store is natively
integer paise, no conversion was needed or done. The 2023-03 bhavcopy independently gives
`open_paise 44210` -- matching to the paisa from a different source, so the vendor's LOW is wrong,
not its open. The real pair (P 2023-03-02 `44375/44700/44010/44130`, C 2023-03-03
`44210/44765/43835/44135`) genuinely reaches the Rule-3 branch. Mutants: silent-skip **CAUGHT**
(2 tests), crash-restored **CAUGHT** (11 tests), uncounted-at-the-map **CAUGHT** -- but
uncounted-at-the-emission-site **SURVIVED the full suite** (finding R3). `bias.py` byte-identical.

**2. THE REPORTER.** PASS with findings.
All six reporter tests were run against a pre-fix `run_backtest.py` restored into a private copy
from `20b45c9` -- my own checkout, not the builder's claim -- and they fail there. The call-order
contract pin is genuine, **not** a tautology: `test_the_reporter_measures_the_runners_real_call_order`
drives the real `runner.run(...)` with the real `walk_symbol` wrapped to advance the clock, so it
exercises production's own ordering; mutating that ordering turns it red. `perf_counter` feeds
display only -- traced by AST across every module: its consumers are `_eta_line` (stdout), the RUN
COMPLETE line (stdout) and `RunOutcome.seconds`, which `main()` never reads into a ledger,
manifest or digest. Pure engines contain zero clock reads (every apparent hit is
`datetime.combine` arithmetic or a docstring). Findings: the clock default and the `<=0` branch
were unpinned (R5), now closed.

**3. CASE 4 (Q-21(b)).** PASS with findings.
Gate-before-bar verified on JIOFIN 2023-08-21's real shape, read from the store
(`O 30000 H 26185 L 29995 C 26185` -- high below low, open and close both outside): the shipped
loader raises `UngatedMinuteDay`, never `MalformedMinuteBar`, and the day is counted once. The
memo is per-run only -- a closure-local `dict[tuple[str, date], tuple[str, str] | None]` holding
the two-string verdict and never the bars; nothing is persisted, and CONTEXT 4.6's "there is no
per-day exclusion file" holds. The resumed-counter identity holds on an independently chosen kill
point. Rules 1 and 2 never load minutes (proved with a provider that raises). **Finding:** the
ruling's own rationale -- a wrong-scale D-1 producing "a garbage first-break that trades" -- is
asserted but not demonstrated: the shipped 1P fixture doubles every price, which puts every bar
above `P.high`, so the first break is the high either way and the true-scale and wrong-scale
answers are identical (`bullish`, executed, +290000 both). The gate is proven to REFUSE; the harm
it prevents is not exhibited. MEDIUM.

**Look-ahead (the attack I judged most important):** CLEAN. `SignalPipeline.gate_day` reads only
the day's own stored minutes and the day's own RAW bhavcopy row. No adjustment factor, no
whole-history suppression list, no ledger. The battery was designed as an offline whole-history
pass and is now wired into a per-day decision -- but every input is strictly `<= D-1`, so no
look-ahead is imported through the back door.

**3b. BLAST-RADIUS SPOT-RECOMPUTE.** PASS.
The evidence file is internally consistent: 59 symbols, per-symbol sum 210, era sum 210, gate
split 121 + 1 + 88 = 210, and 30 + 6,791 + 210 = 7,031, 210/7,031 = 2.99%. Five of the 210 were
re-derived from the store on both halves (Rule-3 membership via the pure engine with a raising
provider; D-1's battery verdict via the shipped pipeline) -- chosen to span the single gate-2 row,
gate 1, gate 1P, both eras and a high-count symbol -- and all five matched. Two controls (Rule-3
days on the same symbols whose D-1 PASSES) produced no refusal. The 209 -> 210 story holds:
JUBLFOOD 2023-03-06 was already a counted refusal, so the row moved counters rather than
duplicating (independently confirmed in check 5 by running the same probe against pre-FIX-3 code).

**4a. BOTH ENUMERATIONS RECOMPUTED.** PASS.
Six flipped symbol-days (including JUBLFOOD and TCS) were run through gate 2 twice -- the
COMPLETED side via the shipped `integrity_gate`, the SEALED side via the real pre-fix
`quality_gates.py` restored from `20b45c9` into a private copy. All six: SEALED **PASS**,
COMPLETED **FAIL**, failing bar the 09:15 print. Controls: JIOFIN 2023-08-21 fails under both and
its gate-1 (volume reconciliation) refusal was independently confirmed, so the completion costs it
nothing; a clean adjacent day passes under both. The sealed-side ledger control was spot-checked
on 10 symbols against `<data_root>/universe_backfill/ledger.json` with zero mismatches -- which is
what makes the completed-side numbers believable. Arithmetic verified: 1,076 + 47 = 1,123;
409,252 - 47 = 409,205; 409,252/435,641 = 93.9425%; 409,205/435,641 = 93.9317%; delta -0.0108 pp.
B261's derivation is sound, including the interaction with the other exclusion triggers and the
shared counter. **Nothing is repaired anywhere in `src/`**: the `min(low, open)` clamp exists only
in the evidence script, exactly as the ruling requires.

**4b. CONTEXT v1.6 AND THE MARGINS.** PASS with findings.
`faa7938` touches **CONTEXT.md alone**, +10/-2, in exactly **four** hunks: the header, 4.5's
completed enumeration, 4.6's COMPLETION paragraph, 10's row. No fifth edit, no incidental
whitespace. Every inserted figure matches the evidence exactly (47; 409,205; 93.9317%; zero status
flips; the 11 moved-POC days -- I counted them independently in `chunk9b_q21a_poc_impact.md`).
The 47-flip list is 47 symbols on **one** date, and scanning three of those symbols' entire stored
histories confirmed 2023-03-03 09:15 is their only open-outside bar. The quarantine margins hold:
`universe_backfill` decides quarantine on the effective gate-1 rate ALONE (gate 2 is structurally
not an input), 2,098/2,435 = 86.16%, +6.16 pp, 150 failing days of headroom; GAIL at 81.89% is the
closest settled symbol. The pilot-window assertion was re-run (3 store-backed tests, 23 s, no
skip) and independently re-derived. Findings R7, R8. **NOT byte-checkable here:** the architect's
literal edit template is not in the repo -- only the ruling is. Every substantive claim in the
edits traces to the ruling or to a measured value, but a true byte-check needs the operator to
paste the template; the four hunks above are what to compare.

**5. UNIFICATION.** PASS.
The real crash pair was driven out of the read-only store through the shipped
`build_runner -> gated_minute_loader -> BiasEngine -> walk_symbol` path. Every claim reproduced:
the exception is `UngatedMinuteDay`; rule `minutes-ungated`, tradeable False, carried bias
UNCHANGED (bearish); **exactly ONE** refused row for 2023-03-06; flag `FLAG_UNGATED_MINUTE_DAY`;
Q-21(b) counter 1, Q-21 counter 0. Actual reason emitted: *"bias unresolvable (CONTEXT 3.2 pair
could not be assembled): minutes-ungated JUBLFOOD 2023-03-03 gate gate 2 (candle integrity) reason
1 OHLC-sanity violation(s) (high<low, or open or close out of range)"* -- gate 2's own name and
gate 2's own words. Running the identical probe against pre-FIX-3 code (`3a15a38`) gives the same
single row counted the other way: **the row moved counters, it did not duplicate or vanish**.
Counted-once mutants all CAUGHT: bar-first (4 tests), double-flag (4), manifest double-count (1),
B258 separate-counter (3, including the JIOFIN counted-once test). B252's completeness guard is
real in both halves (adding a fifth subclass turns it red). Case 3 IS still reachable on the run
path -- proved dynamically, since gate 2 `continue`s past an out-of-session bar without inspecting
it -- but it is NOT tested (R3), and tracing that reachability is what exposed R1.

**6. GATE_DEFINITION MARKER (B259).** PASS with findings.
The bump is present and the two adjacent literals concatenate cleanly. Consumers traced: a stored
row whose marker differs from the current one is re-gated and a row already current is skipped, so
the re-gate is automatic and bounded as documented; the mismatch behaviour was proved dynamically
against a fake ledger in a temp dir. The real store's ledger carries the **old** marker on all
**210** rows -- confirmed read-only -- so it is stale by definition exactly as B259 says. `--regate`
exists, reads stored candles and fetches nothing (no network call is reachable), and WRITES the
ledger, so deferring it to the operator is correct. Findings R4 and R5. **Consequence of running
the relaunch first: none** -- traced above.

**7. B244-B262.** All 19 present, no gaps, no duplicate IDs, and none collides with an earlier ID.
Judged individually in section 3.

**8. STANDARD SWEEP.** PASS.
Suite from clean (`.pytest_cache` and every `__pycache__` deleted): **2,083 passed / 0 failed / 0
skipped** before this review's probes, **2,094** after. Fixtures frozen -- `git diff 20b45c9..a707615
-- tests/fixtures poc` empty and the working tree clean. **The two ruling-driven flips audited line
by line: both are STRENGTHENINGS.** `test_gate2_open_outside_range_is_not_a_spec_exclusion`
asserted two things (`ohlc_violations == 0 and passed`); its replacement asserts three
(`== 1`, `not passed`, the reason text) and ships with four new tests, including the boundary
control that `open == low` and `open == high` must still PASS -- exactly what the quant persona
demands when a new operator enters a gate. The runner flip likewise gains assertions. The three
reporter tests were rewritten because they modelled the runner's call order wrongly, and their
arithmetic assertions are unchanged where the arithmetic is. AST counts confirm the claims:
functions 1,404 -> 1,411, assertions 3,674 -> 3,695, no file losing either; zero skips (the three
store-backed probes do NOT skip on this machine). Exactly six `src/` files changed -- the named
battery/orchestration files -- and `bias`, `poc`, `signals`, `simulate`, `aggregate`,
`corp_actions`, `portfolio`, `minute_store`, `daily_store` **and** `trade_evidence` are all
byte-identical. No hardcoded symbol or date reached production logic (every `JUBLFOOD`/`JIOFIN`/
`2023-03-03` literal in `src/` is in a docstring or comment). Commit hygiene: exactly the five
commits touching `src/` or `tests/` carry `(unreviewed)` and the nine docs-only commits correctly
do not (REVIEW_7 C1); `faa7938` is correctly `spec:`-prefixed and architect-authored. No AI
attribution anywhere (every hit is the filename `CLAUDE.md`, which CLAUDE.md explicitly permits,
or CONTEXT's own pre-existing sentence). No secrets; `.env` never committed in any history. Linear
span, no merges, `HEAD == origin/main == a707615`, every SHA cited in prose resolves.
Dependency hygiene: `pyproject.toml` unchanged. No bare `except`. No float equality introduced.

**Performance (code-reviewer item 7), measured rather than argued:** `gate_day` costs 10.7 ms per
D-1 on the real store (the minute read it needs was happening anyway), so the battery adds ~75 s
across all 7,031 Rule-3 days, and the memo makes repeats free. No regression.

**Failure behaviour (code-reviewer item 2):** the new catch is narrow, not broad.
`BiasEngine._bias_for` catches `UnusableMinuteEvidence` only -- a genuine engine bug raising
`BiasError` still propagates -- and `candles_for`'s `except BiasError` is scoped to a single
`Candle(...)` construction whose only sources are the CONTEXT 7-E11 impossibility invariants, with
`from exc` preserving the cause. A real logic bug cannot be silently converted into a counted
refusal.

---

## 3. Class-B decisions -- B244 to B262, one line each

| # | verdict | one line |
|---|---|---|
| B244 | APPROVED | `MalformedMinuteBar -> UnusableMinuteEvidence -> BiasEngineError`, and `bias_map` catches it, so an escape is a counted whole-symbol no-trade, not a dead run. Defence in depth, verified. |
| B245 | APPROVED | `LedgerRow` and its `as_dict` are byte-identical to `20b45c9` (diffed), so an ordinary day's bytes cannot have moved, and the counter stays derived. |
| B246 | APPROVED | The refused row carries `bias`, `bias_rule` and `status=STATUS_REFUSED`, then `continue`s -- self-describing and nothing trades. |
| B247 | APPROVED | The two-month window is stated on the page itself; the refusal does not depend on the carry, so the count is exact. |
| B248 | APPROVED | `perf_counter` at both sites; every consumer traced to stdout or to `RunOutcome.seconds`, which no ledger, manifest or digest reads. (Was unpinned -- R5, now closed.) |
| B249 | APPROVED | The pilot pack really does list 8 rows against 10 labels; the ledger is untouched and the staleness is disclosed rather than discovered. |
| B250 | APPROVED | Battery before candles, verified on JIOFIN's real shape; one day, one counter. Bar-first mutant caught by 4 tests. |
| B251 | APPROVED-WITH-NOTE | Separate function, no default-off flag -- the B238 precedent honoured. Note: nothing pinned that `build_runner` calls it (R2, now closed). |
| B252 | APPROVED | Mutation-proved: a fifth subclass without a flag turns the tripwire red. |
| B253 | APPROVED | The memo holds only the two-string verdict, never bars; closure-local, nothing persisted; `gate_day` called once per `(symbol, D-1)`. |
| B254 | APPROVED | `refusal` derives from `refusal_detail`; the four-branch order is byte-for-byte what it was, so name and words cannot come from two verdicts. |
| B255 | **APPROVED-WITH-CHALLENGE** | The decision is defensible and disclosed, but its recorded rationale ("the ruling scopes to the RUN") is not in the ruling, and `trade_evidence` does run Rule-3 scans. Scope call -> architect (R6, Q-22). |
| B256 | APPROVED | The disclosure names the ruling, its date and its evidence, and its last sentence says the ledger's own count is the rare-shape counter -- so a stale figure cannot read as a claim about this ledger. |
| B257 | APPROVED | Re-measured independently: no stored day of the five pilot symbols in the window carries a newly-failing bar, so 290/146/88/56 really is unmoved. |
| B258 | APPROVED | One `if not (...)`, one counter, one reason; JIOFIN's three-clause bar counts ONCE, pinned by a test and confirmed by a separate-counter mutant (3 failures). |
| B259 | APPROVED | Compelled by the constant's own contract, and not running the re-gate is compelled by the store-write prohibition. The marker itself was unpinned (R5, closed); the documented command is defective (R4). |
| B260 | APPROVED | Regenerated together and internally consistent; the superseded 209/gate-2-zero figures survive in three documents and in git. |
| B261 | APPROVED | The probe-and-derive method is sound and is what let the "before" side be validated against the store's own pre-existing ledger rather than against a memory of it. |
| B262 | APPROVED | The guards are directory-existence only, and on this machine the three probes do NOT skip (`3 passed in 23.54s`). |

**Unrecorded decisions hunted for:** none material. The reason-string wording, the memo key shape,
the `refusal_detail` ordering, keeping the bare loader and the `SPEC_VERSION` bump are each either
covered by a recorded decision or compelled by an existing contract.

---

## 4. Kept probes

`tests/test_review9b_fixes_probes.py` -- 11 tests, all green, added and kept by this review. Each
exists because a mutant survived the shipped suite; each was mutation-verified to fail on its
mutant and pass on restoration.

| probe | mutant it kills |
|---|---|
| `test_build_runner_wires_the_GATED_minute_loader_not_the_bare_one` | `build_runner` reverted to the ungated loader (R2) |
| `test_the_bare_minute_loader_survives_but_reaches_no_runner` | the same, from the other side (B251) |
| `test_the_gate_definition_marker_carries_the_q21a_open_test` | the B259 bump reverted (R5) |
| `test_the_gate_definition_marker_is_one_clean_concatenation` | a broken seam between the two literals |
| `test_the_reporter_and_execute_default_to_perf_counter` | `perf_counter` reverted to `monotonic` (R5) |
| `test_the_zero_interval_line_names_WHICH_silence_it_is` | the honest `<=0` line reverted (R5) |
| `test_the_reporter_still_says_nothing_walked_when_nothing_was` | the control for the above |
| `test_every_unusable_evidence_rule_has_a_flag_and_that_flag_is_a_rare_shape` | a flag added to the map but forgotten in the counter join (R3) |
| `test_both_q21_rare_shapes_are_counted_from_the_row_flags` | a malformed-bar refusal counted nowhere (R3) |
| `test_the_quarantined_side_carries_THREE_malformed_bars_not_two` | pins the corrected population (R7) |
| `test_the_rule3_scan_consumes_out_of_session_bars_and_it_flips_a_REAL_bias` | a tripwire on Q-22 (R1) |

The last two are store-backed and SKIP without the minute store (B262's precedent). They do NOT
skip on this machine.

---

## 5. Claims examined and REFUTED

Recorded so a later session does not re-raise them. Each was independently re-measured.

* *An operator's absolute path leaked into `docs/evidence`* -- the identical string predates the
  span; not introduced here.
* *No pushed SHA is recorded for the fix sessions* -- `git ls-remote origin` returns
  `refs/heads/main = a707615`, the reflog shows three fast-forward pushes, and every SHA cited in
  prose resolves.
* *`dd30bbb` cites no CONTEXT section* -- it cites the chunk-9B prep card; the other four
  src/tests commits cite CONTEXT sections.
* *PROGRESS header timestamps postdate their commits* -- the headers as committed precede the
  pushes; the facts hold but imply nothing wrong.
* *The evidence script's enumeration probe is not orthogonal* -- the shipped predicate is one
  conjunction and the script re-checks its own claim against the gate on all 435,641 days.
* *The store ledger's staleness invalidates the coverage figures* -- the figures are measured
  independently of the ledger and the sealed side reproduces it exactly.

---

## 6. What is owed, and by whom

**ARCHITECT (blocking the relaunch):**
1. **Q-22** -- does CONTEXT 4.6's Q-17 law bind the Rule-3 first-break scan? (R1: two settled
   symbols' biases currently turn on a 15:44 bar.) The remedy, if ruled yes, is `candles_for`
   calling `aggregate.in_session_bars` and counting the drop.
2. **Q-22(b)** -- does Q-21(b) reach chunk-8's `trade_evidence` sweep? (R6/B255.)
3. Optional CONTEXT edits, none blocking: the population sentence (48 / 50 / **51**, R7); a
   supersedes marker in 4.6 and the 4.6 heading's `(v1.5)` label; the 10 v1.6 row's
   "recorded as law" clause (R8).

**OPERATOR (before the relaunch):** rename -- never delete -- `<data_root>/backtests/chunk9b_full`
to `chunk9b_full_crashed_0803`. **Snapshot `data/` and `cache/` offline** before the run
(CLAUDE.md data-store safety; two generations, new one verified before the old is replaced).

**OPERATOR (data session, NOT before the relaunch -- it is safe either way):** the owed re-gate,
**with the flags R4 shows it needs**:
`acumen-universe-backfill --regate --universe-snapshot docs/recovery/sealed_universe_210.json --report-path <a scratch path>`.
The bare command would re-gate 208 of 210 rows and overwrite the committed sealed report.

**BUILDER (next chunk-9B session):** restore the end-to-end `walk_symbol` assertion for Q-21's
third case (R3); consider the R9 reporting shapes.

---

## VERDICT: **PASS** on the fix arc. **RELAUNCH AUTHORISATION WITHHELD** pending Q-22.

The three rulings are executed faithfully and the measurement behind CONTEXT v1.6 is sound and
reproducible. I would let this arc's code run unattended. I would not yet let it write the
definitive ten-year ledger, because I can show two biases in it that CONTEXT says should not be
there -- and that is one ruling away from being fixed.

Reviewer: chunk-9B QC review session, 2026-08-03. Suite at close: **2,094 passed / 0 failed / 0
skipped** from clean.
