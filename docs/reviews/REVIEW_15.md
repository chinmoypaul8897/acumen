# REVIEW_15 — CHUNK 15 · THE OPERATOR RUNBOOK + DRY-RUN-WEEK READINESS

**QC review, both personas** (`personas/quant_reviewer.md`, `personas/code_reviewer.md`), fresh
session, over `d4d90fd..feba31d` — eight commits, linear, zero merges. The final chunk.

**VERDICT: PASS.** Nine findings, none blocking: 2 MEDIUM quant, 1 MEDIUM code, 2 LOW, 4 INFO.
No CONTEXT deviation, no look-ahead, no test weakened or deleted, no fixture byte moved, no
secret, no AI attribution, and **not one byte of either store moved across this review**.

Everything below was measured here. Where this review reproduces a number the build claims, it
re-derived it rather than reading it; where it disagrees, it says so with the measurement.

---

# PART 0 — STORE INTEGRITY, FIRST AND LAST

`docs/evidence/housekeeping_13aug_store_fingerprint.py`, read before this review's first
store-touching command and again after its last — spanning two full suite runs, two independent
runs of the flip script, a 15-day parity re-run, twenty-one new probes and a full readiness
assessment with a real `pytest` subprocess inside it:

```
open   files 22186  bytes 4109782853  metadata dbea5660...  content d97ba419...
                    newest 2026-08-12T23:19:20  nse/ca/nse_ca_2026-01-01_2026-12-31.json
close  files 22186  bytes 4109782853  metadata dbea5660...  content d97ba419...
                    newest 2026-08-12T23:19:20  nse/ca/nse_ca_2026-01-01_2026-12-31.json
```

**Every digit identical, metadata included, and identical to REVIEW_14B PART 6 and to the build's
own `docs/evidence/chunk15_store_bracket.md`.** The required `d97ba419...` is what the machine
read. The metadata digest matters as much as the content one: a file rewritten with identical
bytes still moves its `mtime_ns`, and none did.

`cache_root` sits **inside** `data_root` (`C:/Users/chinm/acumen-data/cache`), so one fingerprint
brackets both roots. No mutating CLI was run against either; everything needing real bars built a
COPY through the reviewed `test_review14_fix.build_scratch_world` — `shutil.copyfile` /
`copytree`, never a junction or a symlink (CLAUDE.md data-store safety, the Q-18 incident).

---

# PART 1 — R1: THE WIDENED GUARD, AND THE TWO DEFECTS IT COULD HAVE BOUGHT

## 1.1 · The flip, re-run on both trees by this review

`docs/evidence/chunk15_flip.py` copied unchanged onto a clean tree at **`cf53cfd`** (pre-fix) and
a clean clone at **`feba31d`**, and run by this session:

| shape | `cf53cfd` | `feba31d` |
|---|---|---|
| next-day stray stamp | CONTAINED (evaluation guard) | CONTAINED (evaluation guard) |
| high below low | no exception — the gates refuse it | unchanged |
| negative volume | no exception — the gates refuse it | unchanged |
| sub-minute stamp | no exception — the gates refuse it | unchanged |
| **tz-aware stamp** | **ESCAPED `run_day`**, 0 sweeps | **CONTAINED by the intake guard**, 18 sweeps |
| **`close_paise = None`** | **ESCAPED `run_day`**, 0 sweeps | **CONTAINED**, 18 sweeps |
| **`volume = None`** | **ESCAPED `run_day`**, 0 sweeps | **CONTAINED**, 18 sweeps |
| the locked candle file at 11:30 | **0 sweeps — "the whole morning"** | **18 sweeps; ITC loses `['11:30']` only** |

**All seven of REVIEW_14B's shapes escape-before / are-contained-after exactly as claimed.** My
two outputs are **byte-identical to the committed `chunk15_flip.before.txt` and
`chunk15_flip.after.txt`** apart from the tree path and the spelling of the `HEAD` line. The
committed evidence is faithful.

## 1.2 · B416 — the no-retry decision, ATTACKED

The build argues a retry after the reply would hand gate 2 twins. That is not an argument here;
it is a measurement, and it is **exact**:

`LiveRecording.duplicate_bars` — the method CONTEXT 4.5 gate 2 excludes a day on — keys on
**`(sweep, stamp)`**. So a second `record_bars` under the *same* sweep label does not duplicate
one bar. Driving `_poll` twice at one boundary on the real HDFCBANK 2026-06-10 session:

```
one intake                : 136 bars recorded, 0 twins
the retry the guard REFUSES: 136 twins -- the WHOLE reply, under one label
the next boundary's label  : 0 further twins (the design's own whole-session re-pull)
```

A retried intake would therefore hand tomorrow's verification a day gate 2 must refuse — for
every stamp, not one. **B416's premise holds and the distinction it rests on (same label vs next
label) is real.**

**And no-retry loses no data.** A `record_bars` failure of this review's own shape at 11:30, run
against a clean control of the same day:

```
record_bars attempts       : 1   (no loop on the same bytes)
stamps in the recording    : IDENTICAL to the clean run's
twins created in recovery  : 0
the symbol's closing phase : IDENTICAL to the clean run's
```

One boundary is lost, the next boundary re-fetches the whole session, and the day ends where it
would have ended anyway. The choice is right.

## 1.3 · B417 — a crash between statements

Driven, not read. A reply carrying twins, with `record_event` — now the last statement that can
raise before the accumulation — failed at 11:30 only:

```
control (nothing fails) : 2 twins x 18 sweeps = 36
this run                : 34  == control - one reply's worth
```

**The boundary that died contributed ZERO.** Under the pre-fix ordering (accumulate, *then*
record the event) the failed boundary accumulates before it dies and the two numbers are equal —
which is precisely the double-count B417 prevents. The ordering is also pinned structurally: a
kept probe parses `_poll`'s AST and asserts the `self.duplicate_bars[symbol]` assignment is the
**final statement of the guarded block**, so a later reorder fails here rather than in a market.

## 1.4 · An EIGHTH shape, and a failure site the build did not use

REVIEW_14B's seven are the builder's own list, so this review brought its own.

* **a `date` where a `datetime` belongs** — not one of the seven; survives the fetch, dies in
  `merge_bars`. **CONTAINED by the intake guard**, 18 sweeps, `FETCH_UNREADABLE` on disk, the
  other nine symbols swept normally.
* **`ReviewerDiskFull` (a class nothing in `src/` has ever seen) raised from `record_fetch`** —
  a different statement and a different type from the build's `OSError` in `record_bars`. This
  also drives **B418** to its worst case: the machinery that must describe the failure is the
  machinery that failed, so it is refused **twice**. The morning still completes 18 sweeps, the
  `intake-failed` event still reaches disk, the banner still names the symbol at its own
  boundary, and the symbol is re-polled at the next one.

**Nothing unguarded remains in the per-symbol body.** The `if not bars:` branch outside the
`try` contains no recording call — only a string assignment, a `sleep` and a `continue`.

---

# PART 2 — M4: WHAT DID *NOT* STOP BEING ANNOUNCED

The risk of a suppression is what it suppresses by accident, so this was measured for **delivery**.

* **A normal day is untouched.** Every alert the day produces reaches the Telegram transport;
  the recording's `alerts.jsonl` and the transport agree; **zero** withheld events; and
  `post_session` is `False` after `run_day` (it is set in a `try/finally` around one sweep).
* **Only genuinely post-15:29 events are withheld.** On the starved day the pre-fix tree put
  `[2026-06-10 15:30] HDFCBANK LONG entry 740.95 SL 738.10 TP 749.50 qty 350` **and** an EXIT on
  the phone. At HEAD: **0 messages on the transport**, both recorded as
  `post-session-alert-withheld` with their whole payloads.
* **They are EVENTS, not alerts.** No 15:30-stamped row exists in `alerts.jsonl`.
* **The summary structurally cannot see one.** `run_screener.send_end_of_day` builds the message
  from `recorded_alerts(recording)` — `alerts.jsonl` — which is exactly why writing the withheld
  alert as an event is load-bearing rather than stylistic. Searched the rendered summary for every
  money field of every withheld payload: **absent**.
* **And the summary itself still goes.** `send_end_of_day` is a different path from `_alert` and
  is called after `run_day` returns, so the one message that must arrive every day still arrives.
* **No decision moved.** Three post-15:29 bars added to the feed leave all nine decision fields
  identical, on both trees.

---

# PART 3 — M13 / M14: THE TWO-TIER QUEUE (B420)

Two stacked unverified days, the newer holding two recordings, plus a verified day and a replay:

```
on disk : 2026-08-07-live  2026-08-10-live  2026-08-10-replay  2026-08-11-live  2026-08-11-live-2
cf53cfd : 1 recording looked at -- only 2026-08-11-live-2
feba31d : 3 pending, OLDEST FIRST -- 2026-08-10-live, 2026-08-11-live, 2026-08-11-live-2, all NAMED
```

Verified independently by this review, each as its own probe:

* **all verified, oldest first** — sorted on `(day, directory name)`;
* **today's own is never judged** — `before=today` is a strict inequality; a *future*-dated
  recording is excluded too;
* **a replay is never judged** — the `mode == "live"` filter;
* **a judged day never returns** — `read_verification()` empties the queue;
* **blocking follows the prior TRADING day, not calendar-yesterday** — driven across a weekend:
  an unjudgeable **Friday** recording stops a Monday morning; an unjudgeable **Thursday** one is
  shouted about and does not.

**The "unjudged, and not yesterday" reading, attacked -> finding Q2 below.**

---

# PART 4 — THE READINESS GATE

**Every one of the seven driven to both a pass and a refusal**, through `assess` (the function the
CLI calls), as one kept matrix probe. In every refusal: the gate says `NOT READY`, **all seven
checks still ran** (one failure never hides the next), the failing check is the *only* refusal,
and the refusal line names its own check.

**The credential hunt, run harder than the build's own.** Real-looking keys planted, and the send
driven through the **real `tg.post_message`** with `requests.post` raising an exception carrying
the whole request URL — the shape a real transport failure has. Then every byte of every outcome
searched: `render()`, every `figures` dict, every `detail`, the report `repr`, and every refusal
line. **Nothing leaked** — not the token, not the chat id, not the token's secret half, not even
`api.telegram.org`. `post_message` drops the cause and reports only the exception TYPE, and that
one decision is what makes the whole gate safe. The failure is still named, by class.

**The no-write claim, fingerprinted rather than asserted** (CLAUDE.md's own rule about tests that
certify a no-write property): a full `assess` — *including a real `pytest` subprocess over the
real tripwire suite* — with both roots hashed file-by-file, size, `mtime_ns` and content, on
either side. **Identical.** No screener is built, no refresh runs, no broker session opens and no
recording is written; `--readiness` is handled first in `main()` and returns.

**An unrunnable suite is a refusal**, four ways: the file absent, the runner raising, exit 1, and
exit 0 (the only pass). **The test message is opt-in AND required**: not sent -> refusal carrying
its own remedy; a raising transport -> refusal naming the type only; sent -> the one certified pass.

**A report that is missing a check can never read READY** — driven for all seven, plus a
re-ordered report, which is also refused.

The committed `chunk15_readiness_gate.out.txt` is credential-free and its three refusals are the
true state of this machine (this review's own run of `check_master` against the real cache root
agrees: no `OpenAPIScripMaster_2026-08-17.json` exists).

---

# PART 5 — THE RUNBOOK, READ AS THE OPERATOR

**Every command parses, and the launcher really runs.** All six `python ...` commands in the
document parse against the shipped CLI. And in a **bare clone with no editable install**:

```
import acumen                      -> ModuleNotFoundError: No module named 'acumen'
python -m acumen.run_screener      -> No module named 'acumen'        <- the chunk-14 stub's form
python scripts/run_screener.py     -> usage: ... , exit 0             <- the runbook's own form
```

**B429 is real, and the runbook leads with the form that works.** The two install-dependent forms
are named and correctly labelled *"both need `pip install -e .`"*.

**Quoted sentences are pinned to their CONSTANTS, not to copies** — verified for all seven check
names, `READY_LINE`, `TEST_MESSAGE_HEADING`, `VERIFY_STEP`, `EVENT_POST_SESSION_ALERT`,
`SUMMARY_SUBJECTS`, `DRY_RUN_MARKER`, `REPLAY_MARKER`, the `UNSTAMPED_MARKER` opening, and all six
quarantined symbols. One exception, finding C2 below.

**The "refresh FENCED = correct" line is present** — section 3: *"if it prints
`corporate-action refresh FENCED`, **that is CORRECT and expected**... It is not an error and there
is nothing to fix."*

**One command rings the phone, and it is labelled.** Exactly one command carries `--live-alerts`
(*"a separate, deliberate act. Type it; do not keep it in shell history"*), and exactly one other
sends a single labelled TEST message (`--send-test-message`, tabulated as opt-in). No other
command in the document can send anything. Both are counted and pinned.

---

# PART 6 — THE HANDOVER, READ AS THE TRADER

* **The no-order sentence is in the first third** — line 19 of 170: *"It does not trade. It has
  never placed an order and it cannot place one."* Measured, not eyeballed.
* **The 0.52%-2.68% limitation is present and unflattered** — *"That is the honest range, not the
  flattering end of it."* It traces to `live_screener`'s own disclosed constant (0.5229%-2.6808%).
* **Success is alerts-match, not PnL** — *"Success is not a profit number... The week is a test of
  the plumbing, not of the strategy."*
* **No command, flag or module path leaks in** — swept for `--flags`, `python `, `acumen.*`,
  `src/` and `.py`: **zero hits**. It is genuinely a document for somebody who will never open a
  terminal.
* **The three paths -> finding Q1 below.** The delivered path is correct; the attribution is not.

---

# PART 7 — FINDINGS

## Q1 · MEDIUM (quant) — the handover's "three paths" are not the pack's three

`docs/handover.md` section 4 opens *"The validation pack (chunk 12) put three paths in front of
you"* and lists **Stop here / The complete tool used as a screener / Automation**.

The pack's own section is headed **"Three ways forward"** and its three are:

| the pack offers | the handover says |
|---|---|
| **Retire it.** | *Stop here* — the same option in the trader's terms |
| **Change it.** *(a different target multiple, profile window, stop, entry candle — one change and a re-run)* | **DROPPED — absent from the handover entirely** |
| **Take it live knowing the arithmetic.** | *The complete tool, used as a screener* — **correct, and correctly named as the delivered path** |
| — | **Automation — INVENTED**; the pack never offered it |

Automation is plan.md section 8's v2 backlog item (*"auto-execution discussion"*) — which the
handover's own next sentence says (*"listed in the plan's own backlog"*), so the document
contradicts its attribution one line later.

**Why it is MEDIUM and not blocking.** No number is wrong; the delivered path is right and is
correctly named; and the paragraph's load-bearing half — *automation is explicitly not built* —
is true and important. What is wrong is a sentence of attribution in a **trader-facing document
of record**, and the option it silently drops (*Change it*) is one the trader still has and which
this document nowhere tells him about.

**Compounding it:** `tests/test_handover.py`'s
`test_the_THREE_PATHS_are_the_packs_own_three_and_the_chosen_one_is_named` checks the handover's
own three headings **and never opens the pack** — a test that asserts its own document, the
REVIEW_14 B2 / M1-M6 shape this repo has now been bitten by six times.

*Remedy (small):* re-word the attribution, or restore *Change it* and keep automation with the
source it already names. And point the test at `docs/validation/trader_pack.md`.
Pinned: `tests/test_review15_probes.py::test_the_HANDOVERS_THREE_PATHS_are_NOT_the_PACKS_three_as_it_claims`.

## Q2 · MEDIUM (quant) — B420's stated blocking rule and its implementation part company

B420 states the rule as: a recording that cannot be judged *"stops the morning **only when it is
the prior trading day's**"*. The implementation asks
`recording_day(LiveRecording.at(path)) == prior` — and `recording_day` reads the **manifest**.

So for the one entry whose manifest is what could not be read, `recording_day` returns `None`,
`None == prior` is `False`, and **the prior trading day's own recording does not block**. Driven:
a Friday `live` recording with a corrupt `manifest.json`, a Monday morning ->
`step.ok is True`, the report reads READY.

The conservative reading is the opposite one: a recording that cannot say which day it is *could*
be yesterday's, and yesterday's is the one CONTEXT 4.7 names.

**Why it is not blocking.** It is a corner — the manifest is written once, atomically, at
`open_session`. The recording is **always NAMED**, always left on the queue, and reachable as data
(`figures["not_judged"]`), so nothing vanishes; and no decision of any day changes. The sibling
case where the manifest *is* readable and the master is gone blocks correctly, and the build
tests that one.

*Remedy:* treat an unknown day as possibly-prior (block), or read the directory name as a
fallback only for this test. Pinned as measured:
`test_B420_a_prior_day_recording_that_cannot_SAY_which_day_it_is_does_NOT_block`.

## C1 · MEDIUM (code) — the gate's own remedy prints the command B429 exists to eliminate

`check_master`'s refusal ends: *"Run the pre-open refresh first, or
`python -m acumen.instrument_master --allow-network`"*.

On the operator's own tree, verified here, `import acumen` raises **`ModuleNotFoundError`** —
there is no editable install. So the second remedy answers `No module named 'acumen'` at exactly
the moment the operator most needs it: 08:00, on a refusal, on this machine. This is the shape
REVIEW_14 **B3** failed chunk 14 for and that **B429** was written to eliminate one layer up —
and the working launcher already exists and is unnamed: `scripts/fetch_instrument_master.py`,
which this review ran bare (exit 0).

**Why it is not blocking:** the *first* remedy in the same sentence — run the pre-open refresh —
works through `scripts/run_screener.py`, and the runbook's section 3 gives that path. The
operator has a working route stated first.

*Remedy:* one string — name `scripts/fetch_instrument_master.py`.

## C2 · LOW (code) — the runbook quotes the gate's READY line and paraphrases its refusal

`READY_LINE` is quoted verbatim; `NOT_READY_LINE` (*"NOT READY for a live dry-run week -- do not
start it"*) appears nowhere. What the document does quote — *"NOT READY -- the screener must not
start"* — is the morning **refresh's** line, correctly tabulated as such in section 11. Nothing on
the page is wrong; one string simply is not pinned to its constant, which is how a paraphrase
later drifts. Pinned with a flip instruction.

## Q3 · LOW (quant) — L1's clarifying line covers the total-zero resume, not the partial one

The guard is `if alerts and not (self.sent or self.refused or self.failed)`. Measured on the
shipped sink:

```
this process sent 0 of the day's 3 alerts : "3 symbol(s) alerted / telegram: 0 sent"  + the subjects line
this process sent 1 of the day's 3 alerts : "3 symbol(s) alerted / telegram: 1 sent"  + NO line
```

The partial resume is the commoner shape — a restart mid-morning delivers some alerts after the
restart — and it is the one left without the sentence that explains it. Each number is still
right about its own subject, which is why this stays LOW.

*Remedy:* compare the counters' total against the alert count instead of testing for zero.

## Q4 · INFO — a recording directory with no manifest is invisible to the queue

`unverified_recordings` `continue`s past a directory with no `manifest.json` — into neither the
pending list nor the unreadable one. Its own docstring says a recording absent from this list
reads as one that passed, which is M15's shape. **Pre-existing** (the chunk-13 code had the same
filter) and narrow: with no manifest there is no `mode`, no `trade_date` and no `master_file`, so
there is nothing to verify it under. Recorded, pinned, not failed.

## C3 · INFO — two evidence commits carry `(unreviewed)` while touching neither `src/` nor `tests/`

`b762d74` and `a5eacb1`. **Disclosed by the build itself** in its `state-for-next-session`, and
REVIEW_7 C1 is a floor rather than a ceiling: over-applying the suffix to unreviewed documents is
not a violation. Confirmed: all four commits that DO touch `src/` or `tests/` carry it.

## C5 · INFO — `Q-30`'s heading still reads OPEN, and it is the one a live-morning session reads

Checked because chunk 15's readiness gate asserts `SETTLED_UNIVERSE_SIZE = 204` citing *"Q-30's
ruling"*. **The citation is correct**: the architect's 08-Aug-2026 rulings block closes Q-30 as
option (a) — *"a live morning screens the 204 SETTLED symbols only"* — CONTEXT v2.1 section 4.7
carries it as law, and the same session's own prose says *"Q-30 is CLOSED, option (a)"*. There is
no STOP-rule violation and no silent assumption.

But the heading eighty lines above still reads:

```
## Q-30 · chunk 13 · class A · OPEN · ... binds the first live morning
```

Every other closed question in the ledger has its heading updated — Q-14, Q-15, Q-16, Q-20, Q-23
and, by the *same* rulings block and the *same* session, **Q-28 and Q-29** (both `CLOSED
08-Aug-2026 (see ARCHITECT'S RULINGS 08-Aug-2026, below)`). Q-30 was missed.

**Why it is worth a line.** CLAUDE.md's read order step 5 is *"QUESTIONS.md — open items; if one
touches your chunk, STOP on that part"*. A dry-run-week session reads `class A · OPEN · binds the
first live morning` and would stop on the universe question that is in fact ruled and shipped.
**Pre-existing** (chunk 13's FIX-2 session), not this span's doing, and a review fixes nothing —
recorded here because chunk 15 is the chunk that ships the live morning. One-line remedy, and it
is the ledger's own bookkeeping.

## C4 · INFO — one commit does slightly more than its subject says

`3eac79f` is titled *"the dry-run-week readiness gate, and a launcher that runs"* and also
performs the runbook replacement (`A docs/morning_runbook.md` + `D docs/morning_runbook_stub.md`).
The replacement being **atomic in one commit is correct** — there is never a moment in the history
with no operator card — but the subject line under-describes the commit.

---

# PART 8 — B416 - B430, ONE LINE EACH

All fifteen numbers are present in `PROGRESS.md`, no gaps.

| # | judgment |
|---|---|
| **B416** | **APPROVED**, and the strongest of the fifteen. The premise was proved rather than argued: `duplicate_bars` keys on `(sweep, stamp)`, so a retry duplicates the WHOLE reply (136 of 136 bars), and a later sweep's label duplicates none. No-retry loses no data — the recording's stamp set and the day's closing phase are identical to a clean run's. Three outcomes were genuinely needed; the bool could not say the third thing. |
| **B417** | **APPROVED.** Driven at the statement that now precedes the accumulation: the failed boundary contributes ZERO twins where the pre-fix ordering would have contributed its share. Also pinned structurally by AST, so a future reorder fails in the suite. |
| **B418** | **APPROVED.** Driven to its worst case with this review's own exception class: both recordings refused, the morning still 18 sweeps, the banner still naming the symbol. The rationale is exactly right — the reachable cause of the branch is the recorder failing. |
| **B419** | **APPROVED.** Suppressing every kind is correct (per-kind rules rot), and writing it as an EVENT is load-bearing, not stylistic: the summary reads `alerts.jsonl`, so an alert-shaped record would have reached the phone by the back door inside the one message sent unconditionally at the close. Verified in both directions, including that the summary itself still goes. |
| **B420** | **APPROVED**, with finding Q2 recorded against it. The judgment call — an old unjudgeable artefact must not hold the bell hostage — is the right one and is argued honestly; the step's rename is warranted (a step called "verify yesterday" that verifies a backlog is the quiet kind of lie). The implementation of its own "only the prior trading day" clause has one corner it does not cover. |
| **B421** | **APPROVED.** A derived `verification` means the dashboard and the backlog cannot describe different days. Verified: three loud days produce three lines, not one. |
| **B422** | **APPROVED.** Measured: 9 font families / 1 undocumented `(size, tracking)` pair -> **6 families / 0 undocumented pairs**, with the test parsing DESIGN.md itself including the PAIR, which is what `.side` actually violated. Dropping the unbundled monospace fallbacks is right — `tabular-nums`, not the family, makes the price column scannable. |
| **B423** | **APPROVED.** The whole module by AST with docstrings removed, and the line drawn where the rule needs it: the three that DECIDE may only be reached through the pipeline; the two candle-maths helpers are pinned to their single call site. **B328's claim is corrected in place with the original preserved** — verified in `PROGRESS.md`. |
| **B424** | **APPROVED.** A payload with no `mode` is not known to be a replay either; calling it one would replace an unverifiable claim with a second unverifiable claim. Stating the unknown as unknown is the only honest option. |
| **B425** | **APPROVED**, and the `bool` exclusion is load-bearing rather than pedantic — `True` is an `int` in Python and would have satisfied the old guard. A freshness stamp is the pair, not the flag. |
| **B426** | **APPROVED.** One entry point is one thing to remember at 08:00. Verified structurally AND by fingerprint: a full assess moves zero bytes in either root, builds no screener, runs no refresh, opens no broker session and writes no recording. |
| **B427** | **APPROVED.** *"There is a tripwire"* and *"the tripwire is green on this tree, right now"* are different claims, and REVIEW_14 B2 is why that matters. An unrunnable suite being a REFUSAL rather than a pass is the correct default and is driven four ways here. |
| **B428** | **APPROVED.** Both halves are right and both are load-bearing: a gate with a side effect is a gate nobody runs twice; a chat nobody has ever reached is a chat nobody has evidence about. A wrong id, an unstarted bot and a revoked token really do all look like a quiet morning. |
| **B429** | **APPROVED**, and independently confirmed on a bare clone: the `-m` form fails, `python scripts/run_screener.py` works. This is REVIEW_14 B3's lesson applied without being asked. See finding C1 for the one place the same lesson has not yet reached. |
| **B430** | **APPROVED.** Verified atomic: one commit both adds the runbook and deletes the stub, so the history never holds two operator cards or none. Two documents both claiming to be the card is how one goes stale unnoticed. |

---

# PART 9 — THE STANDARD SWEEP

**Suite, from a clean `git clone` at `feba31d`, run ALONE:**

```
2572 passed, 1 skipped, 0 failed   in 506.37s
```

**Exactly the build's claim.** The one skip is the `.env`-input probe
(`tests/test_review13_probes.py:698`), which a clone must skip and the operator's tree must run.

**Suite in the operator's own tree, with this review's 21 kept probes:**

```
2594 passed, 0 skipped, 0 failed   in 460.83s
```

2,573 (the build's operator-tree claim) + 21, to the test. No skips, no xfails.

**The test census, re-derived by AST across the span** — and the build's numbers are right:
**1,792 -> 1,834 test functions in 96 -> 99 files (+42)**; **3 names gone and all three are
RENAMES**; **no file loses a test**; nothing weakened, deleted or skipped.

| the rename | verified |
|---|---|
| `test_DEFECT_R1_...` -> `test_FLIPPED_R1_...` | **A genuine flip.** Run against the pre-fix source it FAILS on its own subject: `AssertionError: merge_bars is outside the per-symbol guard again -- R1, reopened`. Not an import artefact. |
| `test_...fits_on_one_screen` -> `test_...the_stub_is_GONE` | **Asserts strictly more.** Keeps the no-orders and ASCII assertions, ADDS that the stub is gone; the `< 200 lines` bound becomes `> 200` because its subject changed from a stub to the full card. |
| `test_verify_yesterday_finds_...` -> `test_the_step_finds_...` | **A rename following the function's.** Every assertion kept; `verification is not None` becomes `len(verifications) == 1`, which is strictly more precise. Fails on pre-fix (`no attribute 'verify_prior_recordings'`). |

**Parity, re-derived independently** (`docs/evidence/chunk14_parity.py` to scratch outputs, so the
committed artefacts were not overwritten): **15 days, 14 judged, 14 matched, 0 mismatched, 1
disclosed** — the generated report **byte-identical to the committed one apart from its own run
stamp** and the scratch sample's filename. Three days spot-checked field by field: the
carried-bias witness **ITC 2026-06-10** (18 boundaries, 0 mismatches), the gap-entry day
**ADANIENSOL 2026-05-08** (entry 137790 / SL 138160 / TP 136680 / qty 270 identical on both halves
at every boundary, 0 mismatches), and the qty-zero day **BOSCHLTD 2021-05-20** (qty 0 both sides,
0 mismatches). **ADANIPORTS 2026-02-06** is correctly DISCLOSED rather than judged. R1 changes the
control flow of every poll of every symbol and M4 changes what the 15:30 poll delivers; **neither
moved a decision.**

**Purity.** `bias.py`, `poc.py`, `signals.py`, `simulate.py`, `bias_engine.py`, `signal_engine.py`,
**`backtest.py` and `parity.py`** are the **same git blobs** at `d4d90fd` and at `feba31d`.

**Artefacts** byte-identical as git blobs across the span: `chunk9b_backtest_report.md`,
`points_by_symbol.md`, `trader_pack.md`, `trader_pack.json`, `chunk14_parity_report.md`,
`chunk14_parity_sample.json`. **Fixtures** frozen: zero files moved under `tests/fixtures/` or
`poc/data/`. **CONTEXT.md and plan.md: untouched.**

**Chain.** 8 commits, linear, **0 merges**, `main == origin/main` at `feba31d`.

**REVIEW_7 C1: correct.** All four commits touching `src/` or `tests/` carry `(unreviewed)`; see
finding C3 for the two that carry it without needing to.

**No AI attribution.** Four case-insensitive hits across the span's messages, all four the
filename `CLAUDE.md`, which CLAUDE.md's own git rule explicitly permits.

**Secrets: none.** One credential-shaped string in the span diff — the builder's own synthetic,
self-labelling `"...this-is-the-token-value-nobody-may-see"` inside the leak probe. `.env` is
untracked and gitignored; it was never read, printed or echoed by this review.

**Operator note: no new snapshot is owed.** The stores are byte-unmoved by chunk 15 and by this
review, and the existing two generations still cover the current state.

---

# WHAT THIS REVIEW COULD NOT FALSIFY

That the widened guard is the right shape. The temptation with R1 was to retry — it reads like
robustness — and the build proved instead that retrying would have handed tomorrow's verification
a day gate 2 must refuse, and then reordered the one non-idempotent statement so that surviving a
crash costs nothing. Both halves were checked here with the reviewer's own failure shapes and
both hold. The same discipline runs through the gate: it certifies by RUNNING the tripwires rather
than citing them, refuses a suite it could not run, and cannot be made to print the thing it
checks for even when the transport itself raises carrying the token.

The two MEDIUM findings are both in prose, not in code, and both are of one kind: a sentence
claiming a provenance the source does not support — the handover's three paths, and B420's own
statement of when it blocks. Neither moves a number, a decision, or a rupee. That the last
findings on the last chunk are about attribution rather than arithmetic is the honest summary of
where this repository ended up.

**VERDICT: PASS. Chunk 15 is sealed, and with it the tool is COMPLETE.**
