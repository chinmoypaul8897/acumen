# REVIEW_13 — chunk 13, THE LIVE SCREENER

**Span** `7f22f27..7459ab5` (26 commits: the build, the Q-28/Q-29 fix, and CONTEXT v2.0) ·
**QC, BOTH personas** (`personas/quant_reviewer.md`, `personas/code_reviewer.md`) · fresh
session, 08-Aug-2026 · stores READ-ONLY throughout · this review fixed nothing.

## VERDICT: **FAIL.**

The engine half of this chunk is sound and, where it was measured, it measures true. CONTEXT
4.6's settled battery did not move — 2,530 ledger symbol-days recomputed at the review head match
the chunk-9B ledger 2,530/2,530, and the same days under three source trees (span base, pre-change,
head) produce byte-identical `DayGates`. CONTEXT 4.7's published residual reproduces exactly from
an independent stream of the 400 MB ledger: **2,187 / 418,275 = 0.5229%**, and B341's bracket
**10,516 = 2.5141%**. The suite is **2392 passed / 0 failed / 0 skipped from a clean `git clone`**
(207.62 s), the fixtures are byte-frozen, the backtest report and the pack's JSON and points table
are byte-identical since chunk 12 (the pack's Markdown moved one prose line, by the chunk-12 fix
commit inside this span, with its numeric-token count unchanged), and **zero bytes were written to
the stores** by anyone — 22,186 files fingerprinted before and after everything, identical digest.

**The live half does not work, and the ways in which it does not work are the ways that cost
money.** The screener silently drops one trade in six; a duplicate vendor bar is laundered past
the one gate CONTEXT 4.7 leaves standing and the corrupt copy wins; the POC and the entry price
move after they have been published, and the correction is neither sent nor recorded; the
recording every real morning writes is fifteen minutes short, which breaks the next morning's
verification; the shipped entry point has no crash recovery at all; a broken feed renders as a
calm market; and the API key and session token are already in cleartext on this machine's disk.
**Ten blocking findings, eight of them silent** — the tool produces a wrong answer, or no answer,
with nothing on screen to say so. Only two fail loud: **B6** (the live mode refuses to start, exit
1) and **B8** (a restart re-sends the morning, which the trader at least sees as duplicates).

**One root cause accounts for three of the ten.** `LiveScreener` implements `run_day()`, which
sweeps every boundary and then calls `close_day()`; `run_screener.main` re-implements that loop
instead of calling it. So `run_day()`, `close_day()` and `restore()` all have **no caller anywhere
in `src/`** — the class is crash-safe, closes its recording and resumes correctly, and the only
entry point an operator has reaches none of it.

**This is not a close call and the fix list is not cosmetic.** Chunk 13 must not be marked
`reviewed-PASS`, chunk 14 must not start on it, and no live morning may be run.

The suite being green is part of the finding, not a mitigation: **no test, evidence document or
artefact anywhere in the repo ever successfully constructs `build_live_screener(mode="live")`.**
The two places that call it both assert a refusal, and every live-posture test builds
`LiveScreener` directly or mutates a replay screener's fields. 2,392 green tests never exercised
the path this chunk exists to deliver.

---

## PART 0 — RECORDING (architect-directed, own commits, made before the review proper)

**0a · `6789079` — CONTEXT 2.0e, the table of contents.** Sections 4.6 and 4.7 have been law
since v1.5 and v2.0 and neither was listed in the contents; 4.6 was added as a top-level section
in v1.3 and the list was never extended, and 4.7 inherited the omission. Both entries are added
under the §4 listing in the architect's words — `4.6 Minute-lake final state`, `4.7 Live-mode
validity` — and §10 gains the supplied top row `| 2.0e | 08-Aug-2026 | table of contents gains
4.6 and 4.7 (omitted since v1.3) |`. Two edits and no third. The row is an **erratum**, so the
header stays `Version 2.0`, exactly the shape `3415d75` used for v1.9e. Committed ALONE.

**0b · `5418a63` — the architect's B340 ruling, verbatim.** Recorded in its own commit before a
finding was written. Reconstructed by this session from the committed block by the stated
procedure (strip `> `, strip the outer quotation marks): **253 characters, byte-identical to the
supplied text**, one em dash preserved and not transliterated, zero `--` substitutions. B349's
lesson applied rather than merely cited. The ruling approves B340 as taken, fixes the identity
(not the name) as what carries the safety, and confines any rename to the next time `poc.py` is
opened for cause. **This review verifies the identity and raises no finding against the name.**

---

## PART 1 — THE DIRECTED CHECKS

### 1 · The one-engine split — **the seam is sound; what it does not cover is where the money goes**

**Object identity holds and is structural.** `stock_day`, `evaluate(minutes=)` and
`evaluate(minutes=, gates=)` return EQUAL `StockDay` objects on **126 real symbol-days** (six
symbols × June 2026, 63 of them traded), 126/126. The equality is not shallow: 12 fields recursing
into `DailyBias`/`DayGates`/`DayProfile`/`tuple[Bar]`/`SignalDay`, every field `compare=True`, and
**zero float fields anywhere in the tree** — POC and row volumes are exact `Fraction`s. Shuffling
the minutes returns the identical object.

But the seam guarantees only that *given the same bars and the same bias* the two paths agree.
**B1** (a different seed), **B2** (different bars), **B3**/**B9** (a growing prefix) and **M22** (a
missing battery) are all cases where the live path hands the shared engine something else, and the
seam is silent about every one. CONTEXT §6's "same code path" is necessary and, as this chunk
demonstrates, nowhere near sufficient.

**The tripwire's reach is 0.46% of the live path, and the live layer already breaks the rule it
states** — see **M25**.

### 2 · Battery neutrality — **PASS, thoroughly**

* 30 mandated ledger days (JUBLFOOD 2023-03-03; four of the 47 Q-21(a) flips; three auction
  reliefs; two gate-1P refusals; 2016→2026) recomputed against the real stores: **30/30 exact** on
  `gate1_passed`, `gate1_relieved`, `gate2_passed`, `gate1p_passed`. Extended to a seeded random
  2,500 more: **2,500/2,500**. Zero mismatches over 2,530 symbol-days.
* The same 2,530 days under `7f22f27`, `a72a17a` (= `0cff21f^`) and `7459ab5`: **byte-identical
  `DayGates`**, including every gate-2 internal and `liquidity_note`.
* A 1,200-window differential fuzz of `integrity_gate` old-vs-new with the default: every field
  equal. 600 further windows: the live reading **never tightened** the gate.
* **`GATE_DEFINITION` correctly unbumped.** It stamps all 210 `universe_backfill` ledger rows; a
  bump un-skips every one of them and compels a multi-hour, store-WRITING re-gate of 435,641
  stored symbol-days — for provably identical verdicts. `SPEC_VERSION` v1.9→v2.0 is the right
  constant to move and moves no walked row.
* **B340's identity is unconditional.** `poc_licence IS volume_reconciled` for every posture
  string that is not byte-equal to `"live"` — typos, empty string, third values all fall to the
  settled side. Exactly two `DayGates` constructions exist in `src/`; the only constructible
  divergence is `dataclasses.replace(settled, posture="live")`, which no module performs.

### 3 · The residual — **arithmetic PASS, disclosure FAIL**

Re-streamed independently (imports `json` and `collections` only). Every published figure
reproduces **exactly**: denominator 418,275, numerator 2,187, 0.5229%, union 10,516 = 2.5141%,
and all five manifest cross-checks (495,312 rows walked; 6,056 gate-1 refusals; 47 gate-2-alone;
5,157 gate-1P-alone; 407 auction reliefs). `usable` 407,015 − 527 (22 suppressed + 217 unseeded +
288 empty-window) = the run's 406,488, to the day. `chunk13_q28_residual.md` regenerates
byte-identically apart from its own `Run at` line.

The four DEFINITION clauses, attacked with their most defensible alternates:

| clause | alternate reading | headline becomes | verdict |
|---|---|---|---|
| settled-only | include the 6 quarantined symbols a live morning actually sweeps | ~0.6479% (bounded 0.5055–0.8604%) | **the shipped reading is wrong for the live question** — see M2 |
| battery-ran-only | all 495,312 rows in the denominator | 0.4415% (post-listing-only: 0.5202%) | conservative, not wrong; 97.26% of excluded rows are pre-listing |
| relief = pass | count relieved days as refusals | 0.6202% | shipped reading is RIGHT — the evening battery includes relief |
| no-oracle → 1P | fold into gate 1 | unchanged | **vacuous** — 0 such rows exist in the walked span |

The honest-limit paragraph is correct: gate 2's missing-minutes trigger is gate-1-derived, so the
headline is a genuine lower bound. The true ceiling, counting the 697 rows whose gate-2 trigger
the ledger does not name, is 2.6808%.

### 4 · Oracle-free completeness — **the FUNCTION passes; the PATH fails (B2)**

Thirty corrupt-bar shapes driven through `oracle_free_battery` and `gate_day` side by side: open
outside `[low, high]`, close outside, `high < low`, each of O/H/L/C negative and all four, a wholly
negative range, negative volume — **every bar-level trigger fires identically in both postures,
with byte-identical `reasons`**. Only the missing-minutes trigger differs, which is what CONTEXT
4.7 licenses. Out-of-session strays are counted and dropped per Q-17, not day-killers. `None` and
non-integer paise are unreachable: `smartapi_client._paise` refuses the whole vendor reply first,
and that refusal degrades to a skipped symbol.

And then the live path launders its input before the battery ever sees it — **B2**.

### 5 · The loud case, two new ways — **both work; the paths around them fail**

Both new cases were built end to end and both are named loudly: a **gate-1P** refusal on an
alerted day (carrying gate 1P's own words), and a day whose **only alert is the 15:15 square-off**.
B346's negative holds on a day that genuinely never arms. What fails is everything around the
sentence: **B4** (the recording is short, so the banner fires on ~1 alerted day in 5 and the one
that matters is buried), M13 (one-shot, `prev_trading_day` only), M14 (only one recording per day),
M15 (alerts never reconciled against verdicts), M16 (an unpublished bhavcopy is reported as "the
exchange REFUSES … treat them as withdrawn", and the honest `NOT VERIFIED` branch the code carries
is never set by any code path).

### 6 · The prefix phase (B330) — **B330 itself is CORRECT**

Verified on the real day TCS 2026-06-10: `in-trade` at all fourteen boundaries 12:45→15:00, flipped
to `exited`/`square-off-at-the-15:15-close` at 215350 exactly at 15:15, **no exit-kind alert before
15:15**, and `close_day()`'s 15:30 poll moved nothing. The four real-exit attacks also pass: a stop
at 11:45 exits immediately (the guard does not suppress it), SL-wins-ties matches the backtest, a
stop inside the 15:00–15:15 candle is an EXIT not a square-off, and a missing 15:00–15:15 candle
squares off at the 14:45–15:00 close identically to the backtest.

What fails is the machinery around it: **B7** (the trigger alert is pinned to
`entry.close_stamp == boundary` and does not self-heal), **M3** (the phase machine is not
monotonic), **M4** (`close_day` can open and close a trade after 15:29), **M5** (a corrupt bar
turns an open position into `refused`, silently).

### 7 · Replay + resilience — **the invariant holds on non-carry days; B1, B8 and B9 around it**

`chunk13_context47_walk.md` regenerates **byte-identically** (0 differing lines).
`chunk13_replay_walk.md` does **not** — 12 lines move — but every one is a provenance stamp
(`spec_version` v1.9→v2.0, `code_sha`, `config_digest`, three recording digests) and **not one
strategy figure changes**; the fix session never claimed that document reproduces, so this is a
note, not a finding.

Three **new** real symbol-days, chosen from the ledger:

| symbol-day | why chosen | screener vs ledger |
|---|---|---|
| FORCEMOT 2022-09-26 | **gap entry**, short, target-hit | **MATCH** on side/POC/reference/entry/stop/target/qty/exit |
| BHEL 2017-03-16 | **reference == POC exactly** | **MATCH** |
| MAZDOCK 2023-05-12 | plain short, target-hit | **TOTAL MISMATCH — the screener produced nothing** |

MAZDOCK is finding **B1**. A second, independent set of three new days — **WIPRO 2024-07-23** (gap
entry, short, half-paise POC 50304.5, SL = the prior 15-min close), **ZYDUSLIFE 2026-05-19** and
**ADANIPORTS 2026-07-02** (both reference == POC exactly) — all MATCH, and a `LedgerRow` rebuilt
from the bars the screener itself accumulated is **byte-identical to the committed chunk-9B ledger
line**. Six new days, five matches, one total mismatch, and the one that failed is the one whose
bias was carried.

**Crash and disconnect.** Five kill points (mid-11:15 poll, mid-alert-delivery, immediately after
the 11:45 TRIGGER, cleanly between boundaries, and a real `os._exit(9)` child) plus a real
`terminate()` of the shipped CLI: the end state always matches an uninterrupted run, no alert is
ever *lost*, and no kill leaves a half-written JSONL line — a killed-and-resumed recording still
replays through `RecordingBarSource` to the backtester's own answer. Alerts are *duplicated*,
though — **B8** and **M23**. All four resume refusals (moved code SHA, config digest, instrument
master by name and by content, trade date at both the manifest and the state file) **are** enforced
through the shipped path, each naming what moved.

### 8 · Safety — **credential leak (B5); tripwires weaker than advertised**

`--preflight-only` in LIVE mode really is sessionless — verified against a copied day-master with
`login`, `get_candles`, `Credentials.from_env`, `_default_connect_factory` and `socket.socket` all
tripwired and none touched. Crash-and-resume never re-sends an alert. A real recording is clean:
16 files / 4.6 MB scanned byte for byte, **zero `.env` values**. The tracked tree is clean.

The logs are not — **B5**. And of 22 tripwire-evasion variants, 5 are caught and 17 walk past;
the AST half turned red on 3, all 3 already red on the literal scan, so it **adds zero catches**,
and the evasion its own docstring names (`getattr(connect, "place" + "Order")`) defeats both. The
scan is `PACKAGE.glob("*.py")` — non-recursive, and `tests/`, `scripts/` and any subpackage are
invisible.

### 9 · The dashboard — **FAIL on two of PART II's four acceptance questions**

Colour and containment pass cleanly: all ten hex literals in every rendered page trace to
DESIGN.md, there are no `rgb()`/`hsl()`/named colours, **no external reach of any kind** (no
script/link/img/`@import`/`url()`/http), no `.env` byte, and all seven states render with seven
distinct CSS declarations and seven distinct labels. Question 3 — *"if the tool were broken, would
this screen look different from a quiet market?"* — is answered **NO** (**B8**). Question 4 fails
on the twelve-times-repeated disclosure and the raw-paise restatement on the TRIGGERED row.

The half-paise POC breaks on the same page: `live_dashboard.rupees` renders it exactly (148.695)
while `live_screener._rs` runs it through a **binary float** and prints 148.69 — verified on four
real 2026-06-10 POCs, all four moved, direction decided by IEEE-754 (**M10**).

### 10 · Q-29 — **the substance is implemented; the door has two holes**

`mode="live"` resolves the day's own dump, refuses when absent naming the exact file and CONTEXT
4.7, never falls back to the pin, and ignores a pre-seeded manifest. `mode="replay"` consumes the
recording's own `master_file`. The Q-20 pin still governs history through `master_path`. Q-20's
own headline reproduces: `master_tick_divergence(pin 2026-07-31, 2026-08-02, sealed 210)` =
**exactly 11 symbols**. The detector provably decides nothing — one call site, result reaches only
`step.detail`/`step.figures`, `step.ok` is the literal `True`. The kept Q-29 replay test **does**
fail on its own assertion when only the resolution is reverted, so the "proved RED" claim is
substantively honest.

The holes are **M8** (`named_master` does not sanitise a filename that `config.py` explicitly
sanitises — verified: `../../elsewhere/planted.json` and an absolute path both load a master from
outside the cache, and the manifest then records only the basename) and **M9** (`master_file` is
not fenced to replay, so a live session can run on the pin while the preflight prints "THIS DAY'S
OWN dump").

### 11 · The replaced tests, B348, B349, Q-19, C5, the evidence documents

* **The two replaced safety tests.** The *second* is genuinely stricter. The **first is looser** —
  see **M24**: `pytest.raises(BlockedByOpenQuestion)` plus an equality against a module constant
  became `pytest.raises(Exception)` plus three substring checks, and it had to, because the new
  refusal is a `BacktestError` rather than a `ScreenerError`. And **neither successor preserves the
  STOP-rule property the originals had**: nothing now goes red if a future session unblocks a live
  mode without a ruling, and `BlockedByOpenQuestion` is unraised, unconstructed and untested — the
  exit the docstring reserves for the next class-A hole is a branch no test has ever taken.
  The counted claims all reproduce exactly: **1,629 → 1,667 test functions, ZERO removed, exactly
  two names gone**; over the whole span 1,560 → 1,667 (+107, 0 removed, 0 test files deleted);
  2,352 → 2,392 collected, measured at both revisions.
* **B348 is honest.** The demonstration ran against a scratch `cache_root`; the real
  `cache/instrument_master/` holds exactly the two dumps it held before (2026-07-31, 2026-08-02),
  mtimes 31-Jul and 02-Aug. Nothing presented it as a real fetch. **What B348 does not say is
  that the demonstration day was a day the daily store already covered** — which is the difference
  between "live mode starts" and "live mode starts on a morning" (**B6**).
* **B349 byte-checked.** The HEAD quotation reconstructs to **exactly 1,163 characters**; a
  character diff against `b1bc57f` shows **exactly four edit operations** — `--`→`—` twice,
  `Section `→`§`, `section `→`§` — and nothing else moved. The fidelity note is present and
  accurate. One nit: the commit message's *"208 em dashes and 120 section signs"* are **line**
  counts, not character counts (the file carries 214 and 132). The numbers are real; the unit is
  wrong.
* **Q-19 holds on the live path.** `last_completed_trading_day` is `prev_trading_day(today)`,
  strictly before today, and `refresh_daily_store` raises if a window ever reaches today. A live
  morning cannot seal a young 404. (It is also half of **B6**.)
* **C5 is executed in `refresh_calendar` and lost before the recording** — **M17**.
* **CONTEXT 4.7 omits one operative clause of the ruling** — **M18**.

### 12 · B328–B349 — one line each

| # | judgment |
|---|---|
| B328 | **APPROVED, with its recorded claim CORRECTED.** The split is the right shape and the equality is real and structural (126/126 real symbol-days, zero float fields). But the decision states that *"a source-level test forbids the live layer from calling day_profile, aggregate_15min, gate_day or evaluate_day directly"* — and the live layer calls `aggregate_15min` directly, on the evaluation path, today (M25). The split does not, and cannot, cover a different seed or different bars — B1/B2/B3/B9/M22. |
| B329 | **APPROVED.** The whole-day battery is correctly computed once for a replay; the reasoning (a prefix fold cannot reconcile a whole-day total) is exactly right and is Q-28's own basis. |
| B330 | **APPROVED and verified** on a real day. The reading is correct in both directions; the machinery around it is not (B7, M3, M4, M5). |
| B331 | **APPROVED-WITH-NOTE.** Append-only + de-duplicate-on-read is right, but `revisions()` — the reporting half that makes it safe — has **zero callers in `src/`**, and the same de-duplication is what launders B2. |
| B332 | **CHALLENGED.** The close-out poll is load-bearing exactly as claimed — and `run_day()`, its only caller, is called by nothing in `src/`. The decision is right and the code does not execute it (B4). Its `moved` detector is also weaker than claimed: `close_day` **can** open and close a trade after 15:29, and the event goes to the recording JSONL and nowhere the trader looks (M4). |
| B333 | **SUPERSEDED** by the Q-29 ruling, correctly. |
| B334 | **CHALLENGED.** `(symbol, kind)` is right for a re-derived trigger and wrong for a corrected or repeated one: it swallows the second failure banner of the day (M6), a corrected ARMED alert, the real exit after a phase walks backwards (M3), and a TRIGGER whose entry price has since moved (B9) — and because the check sits ABOVE `record_alert`, the suppressed alert leaves no trace at all. The key is also persisted one whole sweep behind the log (M23). |
| B335 | **APPROVED.** DESIGN.md is committed generated-unedited with PART II marked as ours, and PART II is a page a reviewer can hold a screen against — which is how two of its four questions were answered NO. |
| B336 | **APPROVED.** The stray exploratory write is disclosed and the store fingerprint confirms it: 22,186 files, identical digest. |
| B337 | **APPROVED.** Stop writing the literal rather than teach the tripwire an exception. |
| B338 | **APPROVED.** One argument, default = today's behaviour, proved neutral four ways over 2,530 symbol-days and 1,800 fuzz windows. |
| B339 | **APPROVED.** `None` for an inapplicable gate, and a settled `DayGates` with no gate-1P verdict raising, is the right asymmetry. Note `usable` returns `False` silently in the same state `refusal_detail` raises on. |
| B340 | **APPROVED** — and now **architect-ratified** (PART 0b). The identity is unconditional over the whole posture space; the name stands. |
| B341 | **APPROVED as measurement, CHALLENGED as disclosure.** The evidence is exact and states its own limit; the runtime banner the operator reads prints only the narrow figure (M1). |
| B342 | **APPROVED.** The sentence belongs on the payload. Twelve on-screen copies is the dashboard's problem, not the decision's. |
| B343 | **APPROVED.** Two separate arguments is right. The fence is missing on the historical side and `""` disagrees between the two layers. |
| B344 | **APPROVED in intent, CHALLENGED in force.** The refusal is real and unbypassable through `_master_for` — and `master_file` walks straight around it (M9). |
| B345 | **APPROVED.** The verdict belongs beside the day it judges. |
| B346 | **APPROVED and verified in both directions**, including on a day that genuinely never arms rather than one whose alert file was truncated. |
| B347 | **APPROVED.** `--preflight-only` really is sessionless, proved with every credential path tripwired. |
| B348 | **APPROVED as far as it goes.** Honest about the scratch cache; silent about the demonstration day being store-covered (B6). |
| B349 | **APPROVED.** Self-caught, correctly reverted, byte-verified here at 1,163 characters and exactly four substitutions, and the fidelity note says what was corrected instead of letting history imply it was always right. This is the standard. |

### 13 · Standard sweep — **PASS**

* Suite from a clean `git clone` at `7459ab5`: **2392 passed / 0 failed / 0 skipped** (207.62 s).
* `tests/fixtures/` and `poc/data/`: **byte-identical** across the span (empty `git diff --stat`).
* `docs/reports/chunk9b_backtest_report.md`, `docs/validation/trader_pack.json`,
  `docs/reports/points_by_symbol.md`: **same git blob** at `7f22f27` and HEAD.
  `docs/validation/trader_pack.md` moved **one prose line** — in `8080457`, the Part-A commit
  closing REVIEW_12C's carried Q2 — and its **numeric-token diff is empty** (1,107 in, 1,107 out,
  none arrived, none left).
* **Zero store writes**: 22,186 files under `data_root` fingerprinted at the start and end of this
  review, digest `933cfffbcc487c65…` both times, across four suite runs, a 400 MB ledger stream,
  seven replays, twelve agent lanes and every probe.
* Commit hygiene: every commit touching `src/` or `tests/` carries `(unreviewed)` (REVIEW_7 C1);
  `2e83e41` carries it while touching only `docs/evidence/`, which errs safe. CONTEXT committed
  alone. No merge commits, linear chain, single branch. **No AI attribution** in any commit
  message or any added line. `.env` never committed and gitignored. Tags consistent
  (`chunk12-round4-pass` → `7f22f27`); no chunk-13 tag.
* STATUS.md's chunk-13 line matches the PROGRESS `status-ledger` field; dependencies 7, 5A, 9A/9B
  are all reviewed-PASS/COMPLETE; the PROGRESS entry carries every template field.

---

## PART 2 — FINDINGS

### BLOCKING

**B1 — The screener loses every CARRIED bias: 15.46% of the backtester's trades are invisible to
the live half.** *(quant)*
`build_live_screener` wires `bt.build_runner(symbols, day, day, seed_from=day)`, so the bias
SERIES begins on the trade day. CONTEXT 3.2 rule 1 (*"Inside bar … bias unchanged (carry last
known bias)"*) and rule 5 (*"No rule fires → carry last known bias"*) both need an earlier bias to
carry. The engine correctly answers "not seeded" — a state §3.2's Seeding paragraph reserves for
**history start** — and the screener refuses the symbol for the whole day.
Measured over the ten-year ledger: **62,692 of 406,488 evaluated stock-days (15.42%)** and
**29,121 of 188,345 executed trades (15.46%)** stand on a carried bias.
Witness: **ITC 2026-06-10** — ledger `bias=bearish, rule=inside-bar-carry, status=evaluated`;
screener `bias=None` → `refused`. It is in the very universe the chunk's own dashboard renders.
Proof of cause: with `seed_from = day − 30` the same engine reaches `bearish`.
The builder's three walk days are all non-carry (rule-3, rule-1, rule-1), which is exactly why
"the invariant holds on 3 of 3 real symbol-days" is true and the invariant is broken.
*Pinned:* `test_the_screener_LOSES_a_CARRIED_bias_the_backtester_keeps`.

**B2 — The live path launders duplicate stamps before gate 2 can see them, and the corrupt twin
wins.** *(quant + code)*
CONTEXT 4.5 gate 2's **first** exclusion trigger is "any duplicate stamp", and CONTEXT 4.7 leaves
gate 2 as the whole battery. `LiveScreener._poll` stores `merge_bars(previous, fetched)`, which
keys on the stamp and keeps the **last** copy, so `gate2.duplicates` is **structurally always 0 in
live mode**. Verified: the settled battery refuses the raw vendor reply (`duplicates=1,
passed=False`); after `merge_bars` the live battery returns `passed=True, duplicates=0` and the
surviving bar is the corrupt twin. Demonstrated downstream: entry 200100→200500, target
200700→202300, qty 500→166 on a **delivered TRIGGER alert**, on a day the settled battery refuses.
`parse_candles` accepts two rows with the same timestamp, so this is reachable through the shipped
client; `LiveRecording.bars` de-duplicates identically, and `revisions()` — B331's reporting half —
has **zero callers in `src/`**, so the morning-after battery cannot see it either.

**B3 — CONTEXT 3.3's "POC is fixed for the rest of the day once computed" is not implemented
live.** *(quant)*
The profile is rebuilt from the bars in hand at every boundary; nothing pins the 11:15 answer, and
`SmartApiBarSource` deliberately re-pulls the whole session each sweep. Measured on the real lake
over 290 symbol-days: the POC moves on **2.76%** if only the 11:14 bar is late (the *expected*
case — that bar closes at 11:15:00.0 and CONTEXT 4.4 measures it arriving ~0.2 s later) and on
**14.48%** if the last five minutes are. Over 20 symbols × 95 days, **53 real symbol-days** where a
1–5-minute-late window **flips the 11:15 arming decision**, in both directions. Escalated further:
a late window can publish a TRIGGER with entry/SL/TP/qty off a POC the screener abandons thirty
minutes later, on a day the backtester calls `no-trade-never-armed`.
*Pinned:* `test_the_live_POC_MOVES_when_the_11_15_window_was_incomplete`,
`test_an_ARMED_alert_can_never_be_corrected_once_the_POC_moves`.

**B4 — `close_day()` is unreachable from the shipped CLI, so every real recording is fifteen
minutes short and the next pre-open shouts on ~1 alerted day in 5.** *(code)*
`close_day()` is called only by `run_day()`, and **`run_day()` has no caller anywhere in `src/`** —
verified by grep. `run_screener.main` drives its own loop over `boundary_stamps(day)` (last 15:15,
`_clamp` capping at the 15:14 stamp) and returns. `close_day`'s own docstring states why that is
fatal: *"gate 1 reconciles the day's WHOLE folded volume … a recording that stopped at 15:14 could
never be pushed back through the backtest path at all."* Measured: over 460 real July-2026
symbol-days, truncation flips **22.05%** of oracle-passing days to REFUSED and lets 325/440 pass
only by auction relief (a second measurement over 75 symbol-days gives 21.3% / 57 of 59). CONTEXT
4.7's loud banner would therefore fire on roughly one alerted day in five, against a disclosed
residual of 0.5229% — and the one morning that matters is buried.

**B5 — The API key and session bearer token are written in cleartext to `logs/`, and the guard
that claims to prevent it does not work.** *(code)*
`_quiet_library_logging()` raises logzero to CRITICAL — and then `SmartConnect.__init__` calls
`logzero.logfile(path, loglevel=ERROR)`, whose last two lines lower the level straight back to
ERROR and install a `RotatingFileHandler`. Verified in isolation: level 10 → **50 after the guard**
→ **40 after the constructor**, with a `RotatingFileHandler@40` added. The vendor then logs full
request headers. On this machine, already: **97 `X-PrivateKey` lines and 86 `Authorization: Bearer`
lines across 6 files** in `logs/`, and the 8-character `SMARTAPI_KEY` from `.env` appears in all
six. On a refused login the same vendor line carries client code + PIN + TOTP.
CLAUDE.md hard rule 4 is *"Never print, log, echo, or commit `.env` contents"* — **logged**, not
only committed. Mitigating: `logs/` is gitignored, so nothing reached git; the leak is to local
disk. The defect is chunk-5A code, but chunk 13 is what makes it a **daily unattended event**, and
the screener never calls `logout()`, so a leaked token stays valid for the rest of the day.
*Pinned:* `test_the_vendor_SDK_constructor_UNDOES_the_credential_logging_guard`,
`test_the_repos_own_run_logs_carry_credential_shaped_headers`.

**B6 — `mode="live"` cannot start on a real morning.** *(code)*
`build_live_screener` calls `bt.build_runner(symbols, day, day, …)`, which derives its calendar
from the **daily store** over `[day−30, day]`. A derived calendar refuses any range holding a date
it has never attempted (Q-3 safeguard 1). On a live morning that date is TODAY, and today's
bhavcopy cannot exist during today — CONTEXT 4.7's own opening sentence. Both ends are closed:
`refresh_daily_store` stops at the last COMPLETED trading day (Q-19), and `build_runner` takes no
calendar argument. Reproduced: `--mode live --day 2026-08-10 --preflight-only` with the day's own
master present → *"the screener cannot start: CalendarError … 11 date(s) never attempted"*, exit 1.
The same command for `--day 2026-07-30` (a day the store covers) starts perfectly, which isolates
the cause exactly. **Fails loud**, so it cannot produce a wrong number — but the chunk's headline
claim, *"THE LIVE MODE IS UNBLOCKED"*, is not true of any real morning.
*Pinned:* four probes, `test_the_LIVE_mode_CANNOT_START_*`.

**B7 — The TRIGGER alert is lost permanently if the symbol misses its trigger boundary.** *(quant)*
`PHASE_TRIGGERED` is set only when `entry.close_stamp == boundary`, and `ALERT_TRIGGER` fires only
on entry into that phase. ARMED and EXITED are state-derived and self-heal; TRIGGERED does not. So
any of CONTEXT 4.4's **own normal degradations** at the trigger boundary — a failed skip-and-repoll,
the hard deadline, a late vendor candle — destroys the one alert the morning exists to deliver.
The dashboard still shows the position; the bell, and chunk 14's Telegram, never fire.

**B8 — The shipped entry point has no resume at all: a restart re-sends every alert already
delivered, TRIGGER included.** *(code)*
`LiveScreener.restore()` exists, works, and round-trips the `alerted` dedup set and the bars from
the recording's own candle files. **It has no caller in `src/`** — verified by grep, three callers
and all of them tests. `run_screener.main` builds a screener and sweeps from 11:15 with no
`restore()`, so after any death the dedup set starts empty and every alert of the day is delivered
a second time. Measured end to end: the CLI was killed with a real `terminate()` and restarted, and
**4 alerts were re-sent, including a TRIGGER**. plan.md's chunk-13 card requires *"state
persistence (crash-safe resume intra-day)"*; the class implements it and the operator cannot reach
it. Compounding: `restore()` itself never reloads the `SymbolState`s `persist()` wrote, so even a
correct resume starts every symbol at its pre-open phase.

**B9 — A superseded TRIGGER's correction is neither delivered nor recorded, and the bar most
likely to be missing is the one that sets the entry price.** *(quant)*
`_deliver` returns `False` **above** `recording.record_alert`, so a suppressed alert is not merely
un-sent — it leaves no trace anywhere. And the bar most likely to be absent at a boundary poll is
the *last minute of the candle that boundary is about to decide* (`_clamp` asks for stamps up to
HH:MM−1, and CONTEXT 4.4 measures the just-closed candle arriving ~0.2 s after the boundary) —
**that minute's close IS the entry price** (CONTEXT 3.4-2, R1-Q14). Demonstrated: when it heals one
sweep later the state moves from entry 2001.00 / TP 2007.00 / qty 500 to entry 2003.00 / TP 2015.00
/ qty 250, while the trader keeps the first alert and the recording keeps no evidence that anything
changed. This is B3's mechanism applied to the four numbers he actually trades on.

**B10 — A blind screener renders as a calm morning.** *(code + design)*
A feed answering 200 with an empty candle array counts as a successful fetch, so
`SweepReport.complete` stays True, no banner rises, and every `SymbolState` freezes on its last
good prefix. `SymbolState` carries `last_stamp` and `minute_count`; the dashboard renders
**neither**, so a row an hour stale is **byte-identical** to a fresh one while the header clock
asserts the current boundary. Rendered artifact at 12:30 reads *"IN TRADE (1) — position open,
being watched"* off bars that stopped at 11:29, with no banner. DESIGN.md PART II's third
acceptance question — *"If the tool were broken, would this screen look different from a quiet
market?"* — is answered **NO** by the artifact.

### MAJOR

| # | finding | persona |
|---|---|---|
| M1 | The live startup banner prices the live/oracle divergence at **0.5229%** when the same ledger measures the population a live morning is blind to at **2.5141%** (ceiling 2.6808%) — a 4.8× understatement. Gate 1P is *also* inapplicable live, which CONTEXT 4.7's own preceding sentence says. The session's evidence names 2.5141% correctly; the runtime string never prints it. | quant |
| M2 | A live morning sweeps the raw F&O list — **208 symbols including all six quarantined** (APLAPOLLO, ASTRAL, IEX, NTPC, UPL, VBL) — and no live module reads the settled/quarantined register. The backtester walked **zero** of their days (0 of 495,312 ledger rows). Their own gate-1 refusal rate is 22.1–47.2% (32.8% pooled) against a disclosed 0.5229%. The residual excludes exactly the symbols live screens, and the trader gets alerts on six stocks with no backtest evidence at all. This was never raised as a Class-A question. | quant |
| M3 | The phase machine is **not monotonic**: a vendor revision walks EXITED back to IN-TRADE with no alert and no event, after which the real exit is deleted by the `(symbol, kind)` dedup. Demonstrated: the only exit the trader receives says stop-loss 199900 while the screener's own final state says target 200700 — a ₹4,000 swing at qty 500. | quant |
| M4 | `close_day()` can **open and close a trade after 15:29**. With the last candles arriving late, 15:15 leaves the symbol ARMED and the 15:30 poll opens the trade, prices its square-off and marks it exited. B332's `moved` detector fires — into the recording JSONL only: not an alert, not a banner, not on the dashboard. | quant |
| M5 | Under the per-sweep live battery, **one corrupt bar turns an OPEN position into `refused`**: entry/stop/target/qty leave the state, `_alerts_for` has no REFUSED branch, the sweep reports complete, the banner stays empty. An open trade simply stops being watched, and 15:15 never squares it off. | quant |
| M6 | **Only one failure banner can ever be alerted per session.** `ALERT_FAILURE` is delivered with symbol `"-"`, so `("-","failure")` is spent by the first outage. A later outage updates the banner and writes an event but delivers no alert, no `alerts.jsonl` row and no bell — and `SoundAlertSink` deliberately includes failures in `loud_kinds`. | code |
| M7 | The **AST half of the order tripwire adds zero catches** over the literal scan (3 red, all already red), and misses the evasion its own docstring names. 17 of 22 variants walk past both halves. The scan is `PACKAGE.glob("*.py")` — non-recursive, and blind to `tests/`, `scripts/` and any subpackage, though CONTEXT R4 says "anywhere in this repo". | code |
| M8 | **`named_master` does not sanitise the filename `config.py` explicitly sanitises.** Verified: `../../elsewhere/planted.json` and an absolute path both load a master from **outside the cache**, while the config pin validator refuses all three shapes. The input is not a literal — `_master_for` and `verify_yesterday` feed a recording manifest's `master_file` straight in, and the manifest then records only the basename, so the day stops being replayable. | code |
| M9 | **`master_file` is not fenced to replay.** `chosen_master = master_file or _master_for(...)` short-circuits the mode-based resolution for `mode="live"` too, so a live session can run on the Q-20 pin — while the preflight, which derives its provenance line from the *mode* rather than the *file*, prints "THIS DAY'S OWN dump". B344's refusal has an unguarded bypass. The same argument is unfenced on the historical side, protected by convention rather than code. | code |
| M10 | **The same rendered page prints two different POCs for one stock.** `live_dashboard.rupees` renders a half-paise POC exactly (148.695); `live_screener._rs` converts through a **binary float** and prints 148.69 on the alert line — the line the dashboard's ALERT LOG shows, the terminal prints, and B342 sends onward. Four real 2026-06-10 POCs all moved; the direction is IEEE-754's, not a stated rule. CLAUDE.md: *"integer paise internally; no float equality comparisons; POC may be half-paise."* | quant |
| M11 | A feed that dies **across an entry boundary** and heals produces **no alert at all** and the banner clears: the symbol re-evaluates straight into IN-TRADE, `_alerts_for` fires neither ARMED nor TRIGGER, and the page then shows a position with all four numbers the trader was never told about, with nothing loud on screen. | code |
| M12 | Three font families (`SFMono-Regular`, `Consolas`, `ui-monospace`) and one type pair (12px + 0.28px) appear on the rendered page and in **no DESIGN.md row**, and the module's own comment claims the opposite. CLAUDE.md: *"tokens from DESIGN.md only — never invent colors or typography."* The chunk's colour test regexes hex literals only. | code |
| M13 | The morning-after verification is **one-shot and looks only at `prev_trading_day`**. Nothing scans for unverified recordings, nothing queues, no flag verifies a named day, and `--refresh` is opt-in. A skipped pre-open loses the loud case **permanently** and the report stays GREEN. | quant |
| M14 | **Only one recording per day is verified**, chosen by sort order — and `LiveRecording.open_session` actively instructs the operator to create the second one ("Start a new label") when the code SHA, config digest or master moves under a half-finished day. | code |
| M15 | **Alerts are never reconciled against the verdicts.** `verify_prior_recording` skips any symbol with no bars, while `alerts_by_symbol` is built from the whole `alerts.jsonl`. A symbol that alerted but whose candle file is missing gets no verdict, and the headline then asserts "0 alerted". | quant |
| M16 | *"The oracle has not spoken"* is reported as *"the oracle refuses"*. An absent bhavcopy row fails gate 1P with `no-raw-daily-row`, and every alerted symbol is named with *"treat them as withdrawn"*. `MorningVerification` carries `oracle_available` and a `NOT VERIFIED` headline for exactly this case, and **nothing in `src/` ever sets them**. | quant |
| M17 | **The recording mislabels which calendar governed.** No caller anywhere passes `calendar=` or `calendar_source=`, so every manifest stamps `governing_source: "published-nse-holiday-master"` (the parameter default) beside readings taken from the **derived** store-scan calendar — `calendar_source_field: "derived"` in the same block. The preflight prints the same false claim. Demonstrated on a real run (2026-02-01). C5's duty is executed in `refresh_calendar` and then lost before the artefact. | code |
| M18 | **CONTEXT 4.7 omits one operative clause of the ruling it records**: *"§6 parity is judged on oracle-passing days; a live-alerted-oracle-refused day is the disclosed, bounded difference (live cannot see tomorrow)."* CONTEXT §6 still reads "guaranteed no backtest/live drift" unqualified. The qualification lives only in QUESTIONS.md, and chunk 14's parity harness is the next thing to need it. | quant |
| M19 | **No exception isolation around `_evaluate`.** `sweep()` iterates the fetched symbols with no `try/except`, and the CLI's boundary loop has none either — CONTEXT 4.4's skip-and-continue discipline exists only on the fetch side. Demonstrated with a bar the live battery ACCEPTS (in-session clock, wrong date): `PocError` propagates, the symbols after it are never evaluated, no banner rises and `persist()` never runs. | code |
| M20 | **Q-17's "flagged and counted, never silently" is not honoured live.** `out_of_session_dropped`, `gate2.out_of_session`, `missing`, `duplicates` and the CONTEXT 4.7 `liquidity_note` are all computed and then discarded: `SymbolState` has no field for any of them, `persist()` writes only `SymbolState`, and neither renderer prints them. A window accepted while missing 250 of its minutes reads as a clean morning. | quant |
| M21 | **A `qty == 0` day is alerted as a trade.** CONTEXT 3.5: *"qty == 0 → no trade, consumed + logged"*; CONTEXT 3.4-2: *"logged as a skipped signal"*. `simulate.simulate_day` implements it; the live layer implements only the sizing half — the symbol enters TRIGGERED, fires `ALERT_TRIGGER` with `qty 0`, and later fires `ALERT_SQUARE_OFF` for a position that does not exist. The dashboard renders it `qty -` via a falsy check. | quant |
| M22 | **`_battery` can return `None` on a replay, and `evaluate` then gates the GROWING PREFIX** — the exact thing B329 and the method's own docstring forbid. `self.gates.get(symbol)` misses whenever `full_day_gates` (which reads the minute *lake*) has no entry while the bar *source* is a recording — i.e. replaying a live day before the nightly backfill, which is `RecordingBarSource`'s whole purpose. Measured: 13 of 17 boundaries refused on a 375-minute day, ARMED and TRIGGER lost. | quant |
| M23 | **The dedup key is persisted one whole sweep behind the alert log.** `_deliver` records and sends mid-sweep; `persist()` writes `alerted` at the end of it. A death in between leaves `alerts.jsonl` holding alerts `state.json` does not, so even a correct resume re-delivers them. The window is a whole sweep — 75–105 s over 210 symbols by CONTEXT 4.4's own measurement, and the most failure-prone part of the boundary. | code |
| M24 | **The first replaced safety test is LOOSER, not stricter.** Old: `pytest.raises(ls.BlockedByOpenQuestion)` — a named subclass of the module's own base — plus an **equality** against a module constant. New: `pytest.raises(Exception)`, which admits any exception whatsoever, plus three substring checks; the equality has no successor. The reason it had to loosen is itself a defect: the day's-own-master refusal is raised as a `BacktestError`, not a `ScreenerError`, so the module's error contract leaks. The PROGRESS claim *"What replaced them is stricter, not looser"* does not hold assertion-for-assertion. | code |
| M25 | **The forbidden-direct-call tripwire reaches 0.46% of the live path — and the live layer already breaks the rule it states.** The test unparses ONE method (16 lines of a 3,463-line live path) and substring-scans four names. `live_screener._fifteen` function-local-imports and calls `aggregate_15min` and `in_session_bars`, and is reached from `_evaluate → _state_from → _bar_close` on every square-off. There is no circular-import justification (`aggregate` imports nothing from the package, and `live_screener` already imports `Bar` from it at line 71). B328's recorded claim that *"a source-level test forbids the live layer from calling day_profile, aggregate_15min, gate_day or evaluate_day directly"* is **false as written**. | code |

### MINOR / NOTE (abbreviated)

**One MINOR deserves its own line because it concerns the law.** CONTEXT §4.7's copy of the
disclosed sentence is **69 characters** where the architect's recorded ruling has **68** — §4.7
adds a terminal full stop *inside* the quotation marks. `live_screener.LIVE_DISCLOSURE` (68) matches
the ruling byte for byte, so the code is right and the law is one byte off. The fidelity note and
B349 both assert *"CONTEXT v2.0 §4.7 was byte-verbatim from the start"*; at the one point in §4.7
that can be checked against a recorded architect text, it is not. Only the architect can correct
CONTEXT. Related: the "architect's template" §4.7 is said to be quoted from is **recorded nowhere in
the repository**, so the directed check *"§4.7 verbatim against the architect's template"* cannot be
discharged by any reviewer — this session compared §4.7 against the one architect text that IS on
record and reports the result in §11 and M18.


`posture` is an unvalidated `str` (latent, unreachable today) · `usable` returns False silently
where `refusal_detail` raises · `volume_reconciled` is ignored under `completeness_measurable=False`
· the residual document's *"gate 1 is the gate a live session cannot run"* is wrong about 1P ·
CONTEXT 4.7's "architect template" has no recorded source in the repo, so that half of the directed
check cannot be discharged by any reviewer · the verdict never names WHICH gate refused (the name
is computed and thrown away) · an auction-relief pass is reported as "the FULL battery accepts this
day" · gate 2's negative test is NaN-blind (unreachable through the client) · `StoredBar` has no
`__post_init__`, so CONTEXT 7-E11's integer-paise invariant is unenforced there · a
non-minute-aligned stamp is invisible to gate 2 and double-counts a minute into the POC, and gate 1
is the only gate that objects · nothing on the live path ever reads `StoredBar.symbol` · a symbol
refused for "no POC" at 11:15 is dead for the day even after its data arrives (safe direction,
undocumented) · the live screener never calls `logout()` · `smartapi_client`'s docstring names
`getProfile`, which nothing calls · the ARMED group renders at 2.61:1 contrast · the TRIGGERED row
restates its own prices in raw paise at full contrast · the disclosure appears 12× on a live page ·
`waiting` and `refused` share the muted foreground · the verdict banner is not full width and a
live frame carries two `class="banner"` elements while the test asserts one · `TOKENS['primary']`
never reaches the page · `master_file=""` means different things in two adjacent layers · STATUS.md's
chunk-12 line is stale (commit `8080457`, inside this span and after the `chunk12-round4-pass` tag,
changed `trader_pack.py`, `report_9b.py` and their tests — code that line certifies) · chunk 9B, a
declared chunk-13 dependency, reads `COMPLETE — …` rather than the literal `reviewed-PASS` token
plan.md §2 requires · `--config` governs the stores and the recording path but **not** row size, the
money constants or the Q-20 pin, though the code comment says it governs the whole session ·
`code_sha` is `git rev-parse HEAD` with no dirty-tree check, so a recording can name a commit that
never held the code that ran — the committed replay walk is itself an instance (`fa0ba4f`, whose
`src/acumen/` contains no `live_*` module at all) · the committed CONTEXT 4.7 walk does not disclose
in the DOCUMENT that its "live" column was produced by mutating a replay screener (the generator
says so in a comment) · the fidelity note's *"docs/reports/ ASCII"* exception is supported neither by
the 06-Aug ruling as recorded nor by `config.py`, whose ASCII rule covers `src/`, `tests/` and
`config.yaml` and never `docs/reports/` · the
divergence detector's blanket `except Exception: continue` deletes a symbol missing from either
dump (9 today) · the "every morning" divergence duty runs only on the opt-in `--refresh` path ·
a live morning resolves **two** instrument masters and records one (the bar source's token master
comes from the system clock, not the session day) · `test_THE_NEWLY_LIVE_PATH_STILL_TOUCHES_ONE_
BROKER_METHOD` counts nothing, and a third broker method passes it · the shipped B346 negative test
builds its "nobody alerted" day by truncating the alert file · five (before, after) phase pairs are
outside the documented ladder and none is named in any B-decision · `chunk13_replay_walk.md` does
not byte-reproduce (provenance stamps only; never claimed) · B349's commit message reports line
counts as character counts · the E2 calendar check named on the chunk card is **reported but never
enforced** — `refresh_calendar` returns `ok=True` on a day it knows is not a session, so the
pre-open says READY on a holiday and on an NSE weekend special session; the screener is saved only
incidentally, by the derived calendar having no bias for such a day, and tells the operator "no
bias computed for today" rather than naming E2.

---

## PART 3 — WHAT A FIX SESSION OWES

In order. Nothing below needs a re-run of the backtest and no published figure moves under any
of it.

1. **B1** — give the live bias series real history. `seed_from` already exists and already works;
   the default is the defect. Then re-run the replay invariant over a day sample that is
   **stratified by `bias_rule`**, so a carry day is in it by construction and not by luck.
2. **B2** — stop de-duplicating before the gate. Hand `_battery` the vendor's reply as received,
   or carry the duplicate count alongside the merged day. Wire `revisions()` to something.
3. **B3** — pin the POC at 11:15 as CONTEXT 3.3 says, and decide explicitly what a later-arriving
   window minute does. Whatever is decided is a Class-B decision and needs recording.
4. **B4 + B8 together — make `run_screener.main` call `run_day()`.** One change closes both: the
   CLI stops re-implementing the loop, `close_day()` runs (so the recording is 375 minutes and the
   next morning can judge it) and `restore()` becomes reachable (so a restart does not re-send the
   morning). Then fix `restore()` to reload the `SymbolState`s, and move `persist()` inside
   `_deliver` — or persist `alerted` before the sinks fire — so the dedup set is never behind the
   alert log (M23).
5. **B5** — call `_quiet_library_logging()` **after** the vendor constructor as well as before,
   and assert it at the artefact (`logs/`), not at `repr()`. The operator should rotate the six
   existing files and treat the key as exposed.
6. **B6** — the live calendar cannot come from the daily store. Take it from the published
   holiday master, which `refresh_calendar` already fetches and already cross-checks.
7. **B7 / B9 / M3 / M6 / M11** — make the alert rule state-derived and idempotent rather than
   transition-pinned, and re-key the dedup so a corrected, repeated or second-of-its-kind alert is
   not silence. Move the dedup check **below** `record_alert` so a suppressed alert still leaves a
   trace.
8. **B10 / M20** — render `last_stamp` and `minute_count`, and treat an empty answer as a
   not-answer. A stale row must not be byte-identical to a fresh one.
9. **M8 / M9** — sanitise `named_master` exactly as `config.py` does, and fence `master_file` to
   the two cases CONTEXT 4.7 licenses.
10. **M1 / M2** — put B341's bracket in the operator banner, and raise the quarantined-universe
    question to the architect as a Class-A item rather than deciding it.
11. **M18** — the architect owes CONTEXT a sentence: §6 parity is judged on oracle-passing days.

**For the architect:** three items are decisions, not fixes. **M2** — does a live morning screen the
F&O universe (CONTEXT 3.1, ~210) or the settled 204 the backtester walked? CONTEXT does not answer
it and the build sessions did not ask; this review raises it rather than deciding it. **M18** — the
§6 qualification (*"parity is judged on oracle-passing days"*) exists in QUESTIONS.md and not in the
law, and chunk 14's parity harness is the next thing to need it. **The §4.7 full stop** — one byte,
and only the architect may move it.

---

## PART 4 — KEPT PROBES

`tests/test_review13_probes.py`, 15 probes, all green as committed. Five pin defects (F0/B1,
F1/B6, F2/M17, F5/B3, F6/B5) and say so in their names, so a fix session must flip each one
deliberately; the rest hold behaviour this review verified and wants held — the oracle-free
battery's eight bar-level refusals, B340's identity over the whole posture space, the
`completeness_measurable` default's field-for-field neutrality, and the one credential check that
**passes**, on the recording.

**Counts, each one measured rather than composed.**

| run | result |
|---|---|
| review head `7459ab5`, clean `git clone`, no probes | **2392 passed / 0 failed / 0 skipped** (207.62 s) |
| clean `git clone` + the 15 probes | **2405 passed / 0 failed / 2 skipped** (760.15 s) |
| the operator's working tree + the 15 probes | **2407 passed / 0 failed / 0 skipped** (527.86 s) |

The two skips in the clone are the two probes whose inputs are **gitignored and therefore absent
from any clone** — `…_the_repos_own_run_logs_carry_credential_shaped_headers` ("no local `logs/`
directory") and `…_a_real_RECORDING_carries_no_credential_byte` ("no `.env` on this machine"). They
skip cleanly, which is this repo's own convention for store- and machine-backed tests, and both
pass where their inputs exist.

A fix session should know that the `logs/` probe is designed to go red once B5 is fixed **and** the
operator has rotated the six existing files — until the rotation it will keep passing on the
historical evidence, which is deliberate.

---

## PART 5 — METHOD

Twelve directed attack lanes ran in parallel against a disposable clone at `7459ab5`, each writing
only to scratch; **every blocking and major claim in PART 2 was then reproduced first-hand in this
session before it was written down** — including the two that read as security findings (the
credential spill, measured on the real `logs/` and then isolated to the exact two lines of the
vendor's logger setup; and `named_master`'s traversal, demonstrated by loading a real master from
outside the cache). Where a lane and this session found the same defect independently, both
measurements are quoted: **B3** three times (2.76%/14.48% over 290 symbol-days; 53 arming flips;
and a published TRIGGER the backtester denies), **B4** three times (22.05% of 460 symbol-days,
21.3% of 75, and a real CLI recording holding 360 bars), **B5** twice, **B6** twice (from the
calendar and from C5), **M2** twice, **M17** twice.

**What this session ran itself, and what it did not — stated so the reader need not guess.** Every
BLOCKING and MAJOR finding in PART 2 was reproduced first-hand here before it was written down.
Several of the PASS results in PART 1 were measured by a lane and are quoted as such rather than
re-run: the 2,530-symbol-day battery recompute and the three-tree comparison (§2), the 1,800-window
fuzz (§2), the 126-symbol-day identity check and its float scan (§1), the 30-shape corrupt-bar
table (§4), and the 11-symbol tick divergence (§10). This session independently re-derived the
residual, the B349 byte-check, the §4.7 clause comparison, B330 on a real day, three of the six new
symbol-days, the corrupt-bar behaviour of the live battery, every hygiene reading, and both
artefact-freeze checks. Where a PASS rests on a lane's measurement alone, that is a lane's
measurement — not this session's — and a re-review may want to repeat it.

The lanes ran read-only over the stores by construction and it was checked rather than assumed:
**22,186 files under `data_root` fingerprinted at the start and at the end of this review, digest
`933cfffbcc487c65…` both times** — across four full-suite runs, three 400 MB ledger streams, ten
replays, six process kills and every probe. Newest mtime anywhere under the stores: 2026-08-05.
