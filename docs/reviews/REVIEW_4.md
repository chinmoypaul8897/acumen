# REVIEW_4 — chunk 4 · Bias engine (+ the power-loss incident) · TRADER GATE

**Reviewer:** fresh QC review session — `personas/quant_reviewer.md` **and**
`personas/code_reviewer.md` (plan.md chunk 4 review type **QC**). Zero shared context with the
builder.
**Date:** 2026-07-25 · **Span reviewed:** `d2ea387..a0b595a` — **four commits**: the
power-loss incident fix, the two chunk-4 prep commits (Q-6/Q-7 rulings + REVIEW_3 F3; the
curated data-quirk mechanism), and the chunk-4 build. The incident commit gets its **formal
review here** (the promise made when the F6 fix was pulled forward).
**Builder entry reviewed:** PROGRESS.md `[2026-07-25 10:25] chunk 4 · build · done` and
`[2026-07-25 02:40] incident · fix · done`.

## VERDICT: **PASS**

I assumed the trader's own strategy was wrong until it proved otherwise, and it proved
otherwise. I reimplemented CONTEXT 3.2 from scratch — a second bias engine sharing not one line
with `acumen.bias` — and it agrees with the shipped engine on all **15 real TCS days of F9**
(0 mismatches), including both inside-bar carries and Rule-1/Rule-2 on both sides. I built the
**operator-by-operator boundary mutation matrix** on `bias.py` (20 mutants) and confirmed every
strict/inclusive comparison matches CONTEXT 3.2 **character-for-character**; I brute-forced
**261,282 candles** and could not reach the bullish-precedence guard or `RULE_CARRY`. I
re-derived the Q-6/Q-7 redistribution from the frozen snapshots (rights **5/1/1**, priced-event
denominator **296** = 7 rights + 289 dividends), recomputed three special-dividend factors by
hand, and confirmed the S≥P refusal (REVIEW_3 F3) and the uncited-override refusal both fire. I
formally reviewed the incident commit: fsync-before-replace holds in **both** writers, the
`--rebuild-ledger` recovery is correct on a synthetic broken store, quarantine never deletes,
and a corrupt ledger names the recovery command instead of leaking a traceback.

**Full suite: 748 passed / 0 failed** from a clean state (`.pytest_cache` and every
`__pycache__` deleted first), fully offline — **739 from the build** (matching the builder's
claim exactly) plus **9 reviewer probes** I added and kept. `git status` was clean at review
start; the only working-tree change I introduce is `tests/test_review4_probes.py`. **No file
under review was modified. No fixture was touched. CONTEXT.md and plan.md are provably
untouched in the span.**

Findings: **one LOW coverage-gap** (six unpinned Rule-3 boundaries, closed here with verified
tripwires) **and five INFO**. None is a FAIL trigger; none blocks chunk 5A/6/7. The **TRADER
GATE stays open** (a separate field): the OPEN-4 green-tie/doji assumptions and the real-day
bias table must be confirmed by the trader before the chunk-9 run (M3).

---

## 1. Architect's directed checks

| # | Check | Result |
|---|---|---|
| 1 | Incident d2ea387: fsync ordering (data before replace, both writers); `--rebuild-ledger` on a synthetic broken store; quarantine never deletes; corrupt-ledger error names the recovery command | **PASS** — §2 |
| 2 | Quirk 4718399: consulted only after validation fails; corrects only the exact documented pattern; one provenance entry; SmartAPI evidence frozen+digest-pinned; RELIANCE disclosure under OPEN-8; exactly one new store date | **PASS** — §3 |
| 3 | Operator-by-operator mutation matrix on `bias.py`; evaluation order; beyond-body→R1; red/green/doji tie; precedence-guard unreachable (attempt a counterexample) | **PASS (6 coverage tripwires added → Finding 1)** — §4 |
| 4 | F9 independently recomputed from raw candles through my own pairwise-adjustment reading; TCS actions ordinary → k=1 identity (not skipped); evidence pack matches store on ≥5 rows | **PASS** — §5 |
| 5 | F5 + synthetic minute fixtures: R3 first-break scan (time order, strict); same-minute tie; missing-1-min→carry+log | **PASS** — §4, §6 |
| 6 | Demerger + Q-6 tier-2 suppression: pair spanning ex-date blocked (D−1==E, D−2==E); resume at E+3; tier-2 rights consumed the same way | **PASS (one robustness note → Finding 2)** — §6 |
| 7 | Q-6/Q-7 audit: redistribution (5/1/1 rights; 296 sum); VCL/S≥P refusal (REVIEW_3 F3); 3 specials by hand; <1% fast-path boundary; `rights_overrides.json` schema | **PASS (dividend-count note → Finding 3)** — §7 |
| 8 | Purity: AST — `bias.py` zero I/O/clock/network; integer paise throughout; `bias_engine` the only I/O layer | **PASS** — §8 |
| 9 | Seeding: walk-forward from first settled data; no bias before the first rule fires | **PASS** — §5 |
| 10 | Judge B53–B62 explicitly, one line each | **Done — all APPROVE** — §9 |
| 11 | Standard sweep: all fixture digests (incl. the 7 new), commit hygiene across all four commits, PROGRESS/STATUS, no AI attribution, tree clean | **PASS** — §10 |

**Method.** The mutation matrix ran in an isolated git worktree (freely mutating `bias.py`,
reverting between mutants); every other probe read the frozen fixtures, the operator store
read-only, or a hermetic `tmp_path` store. This review issued **no network traffic**. The
mutation worktree was restored to HEAD and removed; `bias.py` is byte-identical to HEAD.

## 2. The incident commit d2ea387 — formal review (directed check 1)

The 2026-07-25 power cut left three valid-named-but-truncated files (ledger, a month parquet, a
raw archive CSV). REVIEW_2 F6 exactly: `os.replace` durable, the data behind it not.

- **fsync ordering — both writers.** `atomic_write_bytes` (`os.fsync(handle.fileno())` at
  `atomic_io.py:96`) and `atomic_write_with` (`_fsync_file(temp_path)` at `:128`) each flush the
  file's DATA to disk **before** `os.replace`. Proven two ways: by reading the code, and by the
  monkeypatch-order tests (`order.index("fsync") < order.index("replace")`) for **both**
  writers. The Windows directory-fsync no-op is honestly documented (NTFS journals the rename;
  the data half — the half that prevents the incident — runs on both platforms). Every store
  and ledger write goes through this path (`daily_store.py:231, :249`).
- **`--rebuild-ledger` on a synthetic broken store.** I built a two-month temp store, corrupted
  the ledger, and rebuilt: present dates return as `file-present` with `source_format`/`url`/
  `row_count` from the stored rows and `reason=REBUILT_LEDGER_REASON`; the lost 404/error
  knowledge is **not fabricated** — those dates become absent → pending again and re-resolve
  from fresh evidence (Q-3 safeguard preserved). A corrupt month is skipped and reported, not
  fatal. `test_incident_recovery.py` (and `test_atomic_io.py`) rerun **20 passed / 0 failed**.
- **Quarantine never deletes.** No code path deletes a store/month/quarantine file. The only
  `unlink` in `src/` is `atomic_io`'s temp-file cleanup on a failed write; there is no
  `os.remove`/`shutil.rmtree` of a store file anywhere. The quarantine test asserts the moved
  file still exists after rebuild. Quarantine is a manual operator move (I1), outside the
  rebuild's `daily/*/bhavcopy_*.parquet` glob.
- **Corrupt-ledger error names the recovery.** `DailyStore.outcomes()` raises `DailyStoreError`
  whose message contains `--rebuild-ledger`, the store root, and `F6` — not a raw pyarrow
  traceback. Confirmed by test and by reading `daily_store.py:487`.

## 3. The data-quirk commit 4718399 (directed check 2)

- **Consulted only after normal validation fails.** `bhavcopy.py:504` calls
  `_require_single_date` first; only on `BhavcopyError` does it consult
  `data_quirks.correct_rows`; if that returns `None` the date **stays `error`**. The store
  validator is never weakened — its refusal is what stopped the garbage file.
- **Corrects only the exact documented malformation.** `ArchiveYearQuirk.matches` fires only
  when the row date set is **exactly** `{0020-07-13}`; I constructed rows with a mixed/extra
  date and `correct_rows` returned `None`. `__post_init__` refuses a quirk whose `wrong_year`
  equals the real year (a no-op quirk that would mask a real malformation).
- **One entry, with provenance.** `QUIRKS` holds exactly one entry (2020-07-13, `0020`→`2020`),
  carrying its provenance string, stamped into the ledger row when applied.
- **Fixtures frozen + digest-pinned.** I independently recomputed sha256 for
  `smartapi_oneday_TCS/RELIANCE_2020-07-13.json` and `quirk_2020-07-13_archive_cut.csv`; each
  matches its pin in `test_fixture_integrity.py` (green, 62 passed). The RELIANCE
  raw-vs-back-adjusted disclosure (raw 1935 vs SmartAPI 878.36, ratio 0.4539 = 1:1 bonus ×
  demerger) is recorded under **OPEN-8** in QUESTIONS.md.
- **Exactly one new store date.** The operator store's ledger carries the quirk provenance on
  **one** date — 2020-07-13, `file-present`. `error` count is 0 across the 2000-01-01..2026-07-24
  span. `test_data_quirks*` rerun **green**.

## 4. The mutation matrix (directed checks 3 & 5)

Twenty boundary-flip mutants, one per strict/inclusive comparison in `bias.py`, each run
against `test_bias.py + test_bias_engine.py` with a revert between:

| result | count |
|---|---|
| **built** | 20 |
| **caught** (≥1 test fails) | 10 |
| **survived — EQUIVALENT** (M05/M08/M11/M12; provably unreachable) | 4 |
| **survived — GENUINE coverage gap** (M13–M18) | 6 |

**No operator mismatches CONTEXT 3.2.** Every comparison — inside `<=`/`>=`, R1 strict
`>`/`<`, R2 mixed `<`,`<=`,`>=` / `>`,`>=`,`<=`, R3 trigger `>`/`<`, R3 closes `>=`/`<=`,
first-break strict `>`/`<`, tie `close<open`/`close>open` — is byte-for-byte the spec's.

**The four EQUIVALENT survivors are not defects and need no test.** M05/M08 (`C.low<P.low`→`<=`,
`C.high>P.high`→`>=` in Rule 2) and M11/M12 (the Rule-3 trigger) each add only a boundary case
(`C.low==P.low`, `C.high==P.high`) that the inside-bar check or Rule 1/Rule 2 has **already
consumed** before the mutated line is reached. A grid search found **0 distinguishing inputs**
for each — I verified this reasoning independently.

**The six GENUINE survivors are reachable spec boundaries the build's comfortable-margin tests
never touch** — the R3/tie close guards at `C.close == bodyMin`/`== bodyMax`, and the
strict-break definition (a 1-min high `== P.high`, or low `== P.low`, is a **touch, not a
break**). HEAD is **correct** on all six (I confirmed each against the live engine). I wrote six
tripwires, verified they **pass on HEAD and fail on their mutant** (I re-applied M13 and M17 and
watched the tripwires go red), and kept them → **Finding 1**.

**Evaluation order** is literally `inside(168) → R1(177) → R2(187) → R3(208) → carry(212)`; the
first rule that fires returns. **Beyond-body outside bars** are decided by Rule 1 and the
minute loader is **never consulted** (grid search: 0 violations; matches
`test_an_outside_bar_closing_beyond_the_body_is_decided_by_rule_1`). **F5** (the trader's Q31
tie) passes on the frozen synthetic red-tie fixture → BULLISH; the doji and green-tie branches
are pinned by their own tests and carry the `open4` flag.

**The bullish-precedence guard is genuinely unreachable.** I attempted a counterexample: the R1
guard needs `close>bodyMax AND close<bodyMin` (impossible, `bodyMin≤bodyMax`); the R2 guard
needs `C.high≤P.high AND C.high>P.high` (a contradiction). Over 261,282 candles the guard fired
**0 times** and `RULE_CARRY` fired **0 times** for a non-outside bar. Kept as a probe
(`test_precedence_guard_and_rule_carry_are_unreachable_over_a_dense_grid`).

## 5. F9 recomputed independently + seeding (directed checks 4 & 9)

I wrote a second CONTEXT 3.2 engine (own paise parser, own inside/R1/R2/R3/carry, importing
nothing from `acumen.bias`), derived each `(D-1, D-2)` pair by previous-trading-day logic over
the fixture's own date set, and graded all **15 F9 rows against `f9_tcs_expected.csv`: 0
mismatches** — both inside-bar carries, Rule-1 both sides, Rule-2 both sides, seed day.

**The empty factor set is identity, not skipped.** TCS has no split/bonus/rights/special
dividend in or around this window: the frozen CA snapshots cover only 2016 / 2023-RELIANCE /
2024, and the operator store returns **raw** candles equal to the fixture to the paise. The max
day-over-day move is **3.43% close-to-close** (2025-07-11) — a genuine market move with no
split/bonus signature — so TCS's only actions are sub-2% ordinary dividends, which carry
`k = 1` per CONTEXT 4.2. The identity is therefore correct **because adjustment computed to
identity**, not because it was bypassed (the code path in `_adjust_previous` returns `previous`
only when `factors_between` is empty, which is the spec's correct answer here).

**Evidence pack** (`docs/gate_chunk4_bias_evidence.md`): its P/C candle numbers and BIAS match
the store's raw candles on **7 rows** (≥5 required).

**Seeding** (directed check 9): the synthetic `test_seeding_carries_none_until_a_rule_first_fires`
proves no bias (and no trade) is emitted until a rule fires; F9's seed day 2025-07-01 fires Rule
1 immediately (`C.close 342970 > bodyMax 345500`), so it seeds on a real rule. The engine's
carry is path-dependent and reseeds `last_bias=None` at `from_date`; the docstring is honest
that a full-history run passes the symbol's first data as `from_date` and chunk 9 computes the
whole series once (noted, not a defect).

## 6. Suppression blocking + resume (directed checks 5 & 6)

`_bias_for` (`bias_engine.py:142`) blocks a day D when `current_date == ex_date` (D−1==E) or
`previous_date == ex_date` (D−2==E): no bias update, no trade, carried bias unchanged. On a
hermetic synthetic store I confirmed **E+1 and E+2 are suppressed and E+3 resumes** the normal
engine carrying the pre-event bias — the first pair strictly after E is `(E+2, E+1)`, exactly
CONTEXT 3.2. The same scenario over `KIND_DEMERGER` **and** `KIND_RIGHTS` (Q-6 tier-2,
JMCPROJECT-style) blocks and resumes identically, because the loop keys only on `ex_date` and
never inspects `kind`. The missing-1-min→carry+log path and the same-minute tie are covered by
`test_bias.py` and the F5 fixture. Kept a resume-boundary probe
(`test_suppression_blocks_e1_e2_and_resumes_at_e3`). **Robustness note → Finding 2.**

## 7. Q-6/Q-7 execution (directed check 7)

Parsed the three frozen NSE windows (438 rows) — the priced-event denominator is **296 =
7 rights + 289 dividends** (independently reproduced; matches REVIEW_3), with 15 bonus / 12
split / 5 buyback / 5 demerger factors alongside.

- **Rights redistribution 5/1/1.** With a store-backed cum-close lookup: **5 factors priced /
  1 suppression (JMCPROJECT `Rights 2:7`, no price) / 1 pending (the S≥P refusal)** — the
  architect's 5/1/1. Zero unresolved rights on an F&O underlying in these windows.
- **REVIEW_3 F3 — S≥P refusal.** `rights_factor` raises when `issue_price ≥ cum_close`
  (TERP≥P → k≥1, economically impossible). Confirmed by direct call.
- **Special-dividend arithmetic.** Three specials recomputed by hand: `D/P_cum ≥ 2%` and
  `k = 1 − D/P_cum` matched `Factor.k` to the last digit (6/6 on the agent's wider spot-check).
- **Boundaries.** `classify_dividend` returns ordinary/fast just below 1%, near-threshold at
  exactly 1%, special at exactly 2% (inclusive `>=`, per the spec's `<`/`>=` wording).
- **`rights_overrides.json` (Class-B judgement).** Committed, **empty by design**;
  `load_rights_overrides` **raises** on an entry citing no NSE circular (I loaded an uncited
  entry and it refused) and rejects a non-positive/non-int price. Placement in `src/acumen/`
  beside its loader is sound — it is code-adjacent curated data, auditable to a circular.

**The dividend band split does not reproduce as `245/26/18` → Finding 3** — re-running today
gives `197/49/26 + 17 pending`. Both sum to 289; the difference is entirely in P_cum lookups
against a **non-frozen** operator store (ticker renames/delistings since the build ran). The
classifier is correct; these counts were never committed as a test (build limit d), so nothing
regresses.

## 8. Purity + structure (directed check 8)

AST parse of `bias.py`: imports are only `__future__`, `dataclasses`, `datetime`, `typing` —
**zero** `os`/`io`/`socket`/`requests`/`pathlib`/`urllib`/`http`/`csv`; **zero** `open`/`print`/
`exec`/`eval`; **zero** clock reads (there are no attribute-calls at all in the module, so
`.now()`/`.today()`/`time()` cannot appear — `datetime`/`date` exist only as `Candle.day`/
`stamp` type-hint fields). No float `==` (the only `==` are string-tag comparisons). Integer
paise is enforced empirically: `Candle.__post_init__` rejects `2000.0` and `True`; `adjust_pair`
rejects both; `_paise` rejects `100.005`. `bias_engine.py` is the **sole** I/O layer (store
reads, CSV reads, pairwise adjustment); `evaluate_pair` invokes the injected zero-arg minute
provider **only** on a Rule-3 day (call count 0 on inside/R1 days, 1 on the R3 day). This is
CLAUDE.md's pure-engine rule made structural (B57).

## 9. Class-B decisions B53–B62 — one line each

| # | Judgment | Reason |
|---|---|---|
| B53 | **APPROVE** | Q-6 tier-1 reconstructs the face value AT the ex-date from parsed split history (`reconstruct_face_value_paise`), defusing the GREENPLY stale-`faceVal` trap; S=face+premium, then the F3 guard rejects S≥P. Verified in code. |
| B54 | **APPROVE** | Q-6 tier-2 emits a `Suppression` exactly like a demerger; `suppression_dates` unions both; the bias engine blocks D−1/D−2==E and resumes at E+3 — I confirmed both kinds take the same path (§6). |
| B55 | **APPROVE** | Tier-3 overrides file committed and EMPTY; `load_rights_overrides` raises on any entry with no NSE-circular citation — the silent guess the item forbids cannot load (§7). |
| B56 | **APPROVE** | Q-7 classifies by `D/P_cum` in three bands with the special formula unchanged; boundaries inclusive at 2%; `classification` carried on `Factor` so the verification list needs no re-derivation (§7). |
| B57 | **APPROVE** | Two modules: `bias.py` pure (injected zero-arg minute provider), `bias_engine.py` all I/O — AST-verified (§8). |
| B58 | **APPROVE** | Evaluation order literal; the beyond-body→R1 precedence note falls out for free (loader not consulted); `RULE_CARRY` and both precedence guards provably unreachable (§4). |
| B59 | **APPROVE** | Tie predicate is close-vs-open (the trader's Q31 authority): red→bullish, green→bearish (OPEN-4 mirror), doji→carry+log (OPEN-4); both OPEN-4 branches set `open4` for the evidence pack. The green/doji assumptions remain UNCONFIRMED — the gate must close (→ Finding 5). |
| B60 | **APPROVE** | F9 is a contiguous adjustment-free real-TCS window (raw==adjusted); 15/15 reproduced independently. The real-CA-in-window pairwise path is only synthetic-tested (→ Finding 4). |
| B61 | **APPROVE** | The quirk is consulted only after validation fails and corrects only the exact documented pattern; the store validator is never weakened (§3). |
| B62 | **APPROVE** | Pairwise adjustment brings PREVIOUS into CURRENT's scale via `factors_between`+`adjust_pair`; empty factors = no adjustment = the correct F9 behaviour (§5). |

## 10. Fixtures, commits, docs (directed check 11)

**Fixture integrity.** `test_fixture_integrity.py` green (62). I recomputed sha256 for all 7
new chunk-4 fixtures (2 F9 cuts, 2 SYNTH minute CSVs, 1 quirk cut, 2 SmartAPI JSONs) — each
matches its pin. `git diff 2cd0eb4..a0b595a -- tests/fixtures poc/data` shows **only added
files** (150 insertions, zero deletions/modifications): no frozen expected value changed.

**Commit hygiene.** Four commits: `incident:`, two `chunk4-prep:`, one build ending
`(unreviewed)`. Every message carries a WHAT/WHY body citing chunk+spec; single human author;
the AI-attribution grep over the whole span is **empty**. `CONTEXT.md` and `plan.md` are
untouched (empty diff). `docs/reviews/REVIEW_2.md` gained only its append-only F6 fix-log line.

**Docs & ledger.** PROGRESS's chunk-4 build entry and the incident entry both carry all eight
template fields, record B53–B62 with an honest limits list; STATUS shows `chunk 4: built` with
deps 0–3 all `reviewed-PASS`; QUESTIONS carries Q-6/Q-7 resolved+executed and the OPEN-8
evidence. `git status --porcelain` was empty at review start.

## 11. Findings

**Finding 1 — LOW — [quant] six Rule-3 / tie / first-break boundary behaviors were unpinned
(mutants M13–M18 survived).** On a genuine Rule-3 day the close guards `C.close >= bodyMin` /
`C.close <= bodyMax` (high-first, low-first, tie-red, tie-green) and the strict-break definition
(`1-min high > P.high`, `low < P.low`) are all **reachable** boundaries — a close landing
exactly on the body edge, or a minute that only touches P's extreme — that the build's
comfortable-margin tests never exercise. HEAD is **correct** on every one (verified against the
live engine and by re-applying the mutants), so this is a test-coverage gap, not a code defect —
exactly the hole a reviewer fills. *Closed here:* `tests/test_review4_probes.py` (6 tripwires),
each verified to pass on HEAD and fail on its mutant.

**Finding 2 — LOW — [both] suppression matches on exact trading-date equality; a
demerger/rights ex-date on a NON-trading day would evade the block.** `_bias_for` compares
`ex_date` to the pair's `current_date`/`previous_date`, which are trading days from
`bias_pair`. NSE ex-dates are trading days by convention (the seed RELIANCE→Jio ex-date
2023-07-20 is a Thursday), so this is unreachable in practice and no factor-less gap can slip
through today. Recorded so chunk 9 (which honors the demerger blocks over full history) either
asserts every suppression ex-date is a trading day, or snaps a non-trading ex-date forward to
the next one. Not a defect.

**Finding 3 — INFO — [quant] the frozen-window dividend band counts (`245/26/18`) are not
reproducible against today's store.** Re-running the redistribution now yields `197/49/26 + 17
pending` (both total 289); the split depends on `P_cum` lookups into the **non-frozen** operator
store, and 17 dividends no longer resolve a cum close (ticker renames/delistings). The
classifier itself is correct (boundaries + special formula + spot-checks all verified, §7), and
these numbers were never committed as a test (PROGRESS limit d). Recorded so no later session
treats `245/26/18` as a frozen anchor. The rights split `5/1/1` and the denominator `296` **are**
reproducible and confirmed.

**Finding 4 — INFO — [quant] F9 is adjustment-free by construction, so the real-CA-in-window
pairwise-adjustment path is exercised only by a synthetic split test.** The orchestration's
`_adjust_previous` + `factors_between` + `adjust_pair` chain is proven by
`test_pairwise_adjustment_brings_the_previous_candle_into_current_scale` (a synthetic k=0.5
split), not by a real-day golden. Real-day Rule-3 and real-CA-in-window bias verification is
scheduled for chunk 12 (per the card). No action for chunk 4.

**Finding 5 — INFO — [quant] OPEN-4's green-tie mirror and doji-carry remain UNCONFIRMED
assumptions.** They are correctly implemented as CONTEXT 3.2 states, flagged in code via the
`open4` flag and surfaced in the evidence pack for the trader. The **chunk-4 TRADER GATE** must
be closed (trader replies CONFIRMED) before the chunk-9 run (M3, plan.md §2). This review does
not close the gate; STATUS remains `reviewed-PASS` with the gate a separate, still-pending field.

**Finding 6 — INFO — [code] the corrupt-ledger error embeds the pyarrow exception type/message
as context.** `outcomes()` includes `type(exc).__name__: exc` inside its guidance string — this
is diagnostic context, not a raw traceback, and names `--rebuild-ledger`. Appropriate; recorded
only so a reader does not mistake it for a leak.

## 12. Checklist coverage

**quant_reviewer** — *Look-ahead:* bias for day D uses only D−1/D−2 (§5); `evaluate_pair` is
pure and reads no clock; the entry candle rule is chunk 7. *Boundary operators:* every one
verified character-for-character and by a 20-mutant matrix; the six unpinned boundaries are now
pinned (§4, Finding 1). *Candle indexing:* pairs are previous TRADING days (the suppression and
F9 tests cross a weekend correctly); open-stamped minutes read in file order. *Units:* integer
paise enforced (float and bool rejected), no float `==`; factors are `Decimal`. *Corporate
actions:* pairwise (P into C's scale, C untouched); demerger and Q-6 tier-2 rights suppressed
(E+1/E+2 blocked, E+3 resume); ordinary dividends `k=1`; Indian bonus convention inherited from
chunk 3. *Data honesty:* suppression counts a no-trade, the quirk carries provenance, OPEN-4
occurrences flagged. *Fixtures/OPEN items:* F5/F9 reproduced; OPEN-4 raises no factor and is
gate-blocked; Q-6/Q-7 resolved without a `k=1` guess.

**code_reviewer** — *Tests:* 748 green from clean; error paths carry weight (missing candle,
missing 1-min, corrupt ledger, corrupt month, quarantine, non-int price); no test weakened or
skipped. *Failure behaviour:* atomic writes fsync-before-replace in both writers; rebuild is
crash- and power-loss-safe and idempotent; no bare `except:` swallowing a real error. *Secrets:*
no `.env`/credential anywhere in the span. *Time & precision:* naive-IST, integer paise, no
`datetime.now()` in any pure function. *Structure:* `bias.py` AST-pure; `bias_engine.py` the only
I/O layer; no hardcoded tick/symbol/date/path. *Git & docs:* four logical commits, WHAT/WHY
bodies, **no AI attribution**, PROGRESS/STATUS complete, CONTEXT/plan untouched.
*Dependencies:* `pyproject.toml` unchanged; no new package.

## 13. Scope

`d2ea387..a0b595a` is the incident fix + chunk-4 prep + chunk-4 build. New engine code:
`bias.py` (pure), `bias_engine.py` (orchestration + minute-loader interface), `data_quirks.py`,
`rights_overrides.json` (empty). The corp_actions changes execute the Q-6/Q-7 rulings and
REVIEW_3 F3. Nothing from a later chunk appears — no POC, signals, simulate, or SmartAPI client;
the real 1-minute loader is chunk 5A (the interface and a CSV fixture loader stand in). This
review added exactly one file (`tests/test_review4_probes.py`, 9 tests) and modified no file
under review.

---

## 14. Fix log (appended by later sessions — the review text above is unchanged)

| Finding | Status | Closed by | What changed |
|---|---|---|---|
| F1 | closed-in-review | REVIEW_4 (2026-07-25) | Coverage gap only; the reviewer added `test_review4_probes.py` (6 boundary tripwires + a guard-unreachability probe + an E+3-resume probe). No code change needed or made. |
| F2 | INFO | — | Robustness note for chunk 9 (assert/normalize non-trading-day suppression ex-dates). |
| F3, F4, F5, F6 | INFO | — | Notes: dividend counts are not a frozen anchor; the real-CA pairwise path and real-day R3 land in chunk 12; the OPEN-4 gate must close before the chunk-9 run; the corrupt-ledger error context is intentional. |
