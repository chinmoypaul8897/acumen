# REVIEW_15B — CHUNK 15's CLEANUP · THE SCOPED RE-CHECK

**QC re-check, both personas** (`personas/quant_reviewer.md`, `personas/code_reviewer.md`), fresh
session, over `ee412a6..29cd748` — three commits, linear, zero merges. The subject is the CLEANUP
of REVIEW_15's nine findings; the chunk-15 body already passed REVIEW_15 and is not re-opened here.
**This is the last review.**

**VERDICT: PASS.** Six findings, none blocking and **none of them created by this span**: 1 MEDIUM
code (CARRIED, pre-existing, outside the cleanup diff) and 5 INFO. No CONTEXT deviation, no test
weakened, deleted or skipped, no fixture byte moved, no secret, no AI attribution, and **not one
byte of either store moved across this re-check**.

The cleanup's risk is not the defect each fix was written against — REVIEW_15 measured those. The
risk is a fix firing where it should not, and Q2 is a **fail-closed** change, whose characteristic
failure is exactly that. So the weight of this review sits on OVER-firing, and the question it
kept asking is the one that decides whether "blocks" means "blocks a morning" or "blocks for
ever".

---

# PART 0 — STORE INTEGRITY, FIRST AND LAST

```
open   files 22186  bytes 4109782853  metadata dbea5660...  content d97ba419...
                    newest 2026-08-12T23:19:20  nse/ca/nse_ca_2026-01-01_2026-12-31.json
close  files 22186  bytes 4109782853  metadata dbea5660...  content d97ba419...
                    newest 2026-08-12T23:19:20  nse/ca/nse_ca_2026-01-01_2026-12-31.json
```

**Every digit identical, metadata included, and identical to the cleanup's own
`chunk15_cleanup_store_bracket.md`, to REVIEW_15 PART 0 and to REVIEW_14B PART 6.** The required
`d97ba419...` is what this machine read. The metadata digest matters as much as the content one: a
file rewritten with identical bytes still moves its `mtime_ns`, and none did. `cache_root` sits
INSIDE `data_root`, so one walk brackets both roots.

## 0.1 · The reading was RE-DERIVED, not re-run — and why it had to be

**The committed `docs/evidence/housekeeping_13aug_store_fingerprint.py` could not run on this
machine.** It calls `handle.read(1024 * 1024)` once per block, so a 22,186-file / 4.1 GB walk asks
the allocator for a fresh 1 MB object several thousand times. Read here with Windows
`GlobalMemoryStatusEx`, the machine was at **97–98% memory load, ~0.2 GB physical and ~0.3 GB
commit free**; both attempts died with `MemoryError` inside `file_sha256`, and PowerShell itself
failed to launch with `0x800705AF` (ERROR_COMMITMENT_LIMIT). **That script was NOT edited** — it is
frozen evidence of two prior sessions.

So this review wrote its own: `docs/evidence/review15b_store_fingerprint.py`, an independent
implementation of the same written recipe (`<relpath>|<size>|<mtime_ns>` and
`<relpath>|<size>|<sha256>` lines, sorted by POSIX relpath) that allocates **one** 256 KB buffer
for the entire run and fills it with `readinto`, asking the allocator for nothing after start-up.
Read-only by construction: every file opened `"rb"`, nothing created, written, renamed or removed.

**This makes the bracket stronger rather than weaker.** REVIEW_15, REVIEW_14B and the cleanup all
quote a digest produced by ONE program. A second, independently written program reading the same
disk produced **the same two digests to the digit** — which is what makes a matching digest mean
something. It also validates the new script against the frozen recipe.

**No mutating CLI was run against either root.** Everything that could write ran against a scratch
copy or a `tmp_path` tree of its own. The one command run bare against real bytes was
`python scripts/fetch_instrument_master.py` **without** `--allow-network` (PART 3), which reads a
directory listing and returns.

**Operator note: no new snapshot is owed.** The stores are byte-unmoved by the cleanup and by this
re-check, and the existing two generations still cover the current state.

Between the two readings sat: two full suite runs, three parity re-derivations over the real
ledger / daily store / minute lake / instrument master, the reviewer probes run repeatedly on both
trees, and one bare `scripts/fetch_instrument_master.py`. Full evidence, with the generating script
committed beside it (REVIEW_7 C3): `docs/evidence/review15b_store_bracket.md`.

---

# PART 1 — Q2: THE NEW BLOCKING LOGIC, ATTACKED FOR OVER-FIRING

The fix: the blocking test takes the day from the manifest, or failing that from the directory
NAME (`recording_day_or_name`), and an entry neither can date is treated as possibly-prior and
refused. Everything below was driven by this session, in
`tests/test_review15b_probes.py`.

## 1.1 · The three outcomes, each driven

| the entry | what dates it | blocks a Monday whose prior trading day is the Friday? |
|---|---|---|
| readable manifest, any day | the manifest | **never reaches this code at all** — see 1.2 |
| Friday recording, `{ not json at all` | the NAME | **YES** — `step.ok is False` |
| Friday recording, **empty** manifest | the NAME | **YES** |
| Friday recording, manifest with **no `trade_date`** | the NAME | **YES** |
| Thursday / Wednesday / three-weeks-back, broken | the NAME | **NO** — all three NAMED, bell rings |
| directory named `2026-08-14-live`, manifest of the **14th → no, of the 13th** | the MANIFEST wins | judged as the 13th |
| `notes/`, `scratch/` — nothing can date it | nothing | **YES**, and named in `figures["unknown_day"]` |

Three different ways of being unreadable were used on purpose — corrupt JSON, an empty file, and a
well-formed manifest with no `trade_date` — because the fix must not depend on which of them
happened. All three block; none of them lands in `unknown_day`, because the NAME dated them.

## 1.2 · A legitimate week never reaches the new code

This is the precondition that makes the rest affordable, and it is structural rather than lucky.
`unverified_recordings` puts an entry in the `unreadable` list — the **only** list the name
fallback and the orphan rule touch — solely when its manifest is absent or unreadable. Driven
across five ordinary mornings, Monday to Friday, each leaving a recording and each judged by the
next: **`unreadable == ()` at every one of the five**, and with every day judged the step reports
`nothing unverified` with `pending == 0`. Whatever the fallback does, it cannot do it to a real
week.

## 1.3 · THE OVER-BLOCK ATTACK — a dated blocker stops ONE morning and ages out by itself

This is the property that separates "blocks a morning" from "blocks for ever", and **no test the
build wrote covers it.** One artefact, unchanged on disk, read by two consecutive mornings:

```
Friday recording, corrupt manifest, nothing touched between the two calls

Monday  (prior trading day = Friday) : step.ok = False   -- it IS yesterday's
Tuesday (prior trading day = Monday) : step.ok = True    -- it is not, any more
                                       ...still NAMED, still queued, still in figures
```

**The rule ages out on its own.** Nothing has to be deleted, no operator has to act, and no
architect has to rule, for the week to continue. That is what makes the conservative reading
affordable, and it is why B420's judgment — *an old unjudgeable artefact must not hold the bell
hostage* — genuinely survives a fail-closed change. The artefact is still shouted about on the
Tuesday; it simply no longer costs a morning.

The single exception is an entry **nothing can date**, which blocks every morning until it is
resolved. That is by design, it is disclosed, and PART 2 measures what the operator does about it.

## 1.4 · B431 — the name reaches the blocking test and nothing else

Proved by AST over the module rather than by one example, because the claim is a claim about
REACHABILITY. `verify_prior_recordings` has exactly two top-level loops:

```
for path, why in unreadable:   calls recording_day_or_name
                               calls NEITHER verify_prior_recording NOR write_verification
for recording in pending:      calls recording_day, verify_prior_recording, write_verification
                               NEVER calls recording_day_or_name
```

And `recording_day_or_name` has **exactly one call site in the whole of `src/`** — that loop.
`recording_day` is unchanged and still reads the manifest and only the manifest.

Driven as well as parsed, at the only place it can cost money — the file on disk. A Friday
recording dated by its NAME for the blocking test produces: `verifications == ()`, **no
`verification.json`**, `read_verification() == {}`, `figures["recordings"] == []` and
`figures["days"] == []`, and it is still on the queue on the next call. **No verdict is ever
written for a day a directory name chose** — which matters, because a verdict written under a name
would let the next morning read the entry as judged and drop it from the queue: M15's shape with
an extra step.

---

# PART 2 — Q4: THE ORPHAN DIRECTORY

**Surfaced, never invisible.** A directory with no `manifest.json` is now reported like any other
unreadable entry, with a reason that says why (*"no manifest.json — nothing here names a day, a
mode or an instrument master, so there is nothing to verify it under"*). It used to be `continue`d
past silently, and the function's own docstring says an absence from that list reads as a
recording that PASSED.

**It cannot over-block a normal operator.** A Wednesday-named orphan does not stop a Monday; it is
named and the bell rings. A Friday-named one does stop it, and ages out on the Tuesday exactly as
1.3 measures.

**What an operator does about the one that cannot be dated — the runbook's own line, section 8:**

> **A recording that cannot say WHICH day it is of stops the morning.** … the report says so by
> name (`cannot say WHICH day they are of … and STOP this morning`) and the step FAILS. … An entry
> that IS dated — by its manifest or by its name — and is older than the prior trading day is
> shouted about and does not hold the bell hostage. **Tell the architect; do not delete anything**
> (rule 3 of section 12, and store deletions are never a session's work).

So the remedy is an ESCALATION, not a self-serve clean-up, and it is correctly so: the live root
is inside the stores, and CLAUDE.md makes store deletions operator-only with a verified snapshot
first. The cost is stated honestly: such an entry blocks **every** morning until somebody acts —
driven here across three consecutive mornings. This review judges the trade right and records it
as finding **R3** so the architect sees it before a dry-run week, not during one.

**Nothing that exists today can be refused.** Read from the machine, not from the build's
assurance: `<data_root>/live` **does not exist**, and `unverified_recordings` on an absent root
returns two empty tuples before it looks at anything. The first artefact this rule can ever refuse
is one a dry-run week creates. A kept probe asserts both halves, and asserts the stronger property
if the root ever appears.

---

# PART 3 — C1: THE REMEDY, RUN BY THIS REVIEW

Not read — executed, in a bare clone at HEAD, `PYTHONPATH` stripped, no editable install:

```
$ python -c "import acumen"
ModuleNotFoundError: No module named 'acumen'          <- there is no editable install here

REFUSAL: ...refuses to start without it. Run the pre-open refresh first, or
         `python scripts/fetch_instrument_master.py --allow-network`
EXTRACTED (out of the refusal string, not written down): python scripts/fetch_instrument_master.py

$ python scripts/fetch_instrument_master.py --cache-dir <scratch>
cache dir    : ...\c1cache\instrument_master
already held : 1 dump(s), newest OpenAPIScripMaster_2026-08-02.json
STOPPING (no --allow-network). Nothing was fetched and nothing was written.
exit 0
```

No `No module named`, no traceback, exit 0, and the launcher's own bootstrap is what makes it work
— `import acumen` fails in the very same environment. The **dead** form fails there too, as do the
other two `-m acumen.*` forms:

```
python -m acumen.instrument_master  -> No module named 'acumen'
python -m acumen.run_screener       -> No module named 'acumen'
python -m acumen.ca_report          -> No module named 'acumen'
```

**AST-confirmed:** no printable (non-docstring) string in `dry_run_readiness.py` names the dead
form, and one that CAN be printed names the launcher. `check_master`'s docstring still records what
the remedy used to say and why it changed, which is the provenance a later session needs — that is
correctly excluded.

**One precision the build's evidence does not carry.** `scripts/fetch_instrument_master.py` ends
`return 0 if existing else 1`: exit 0 means *a usable dump is on disk*, and a genuinely empty cache
returns **1** with the same "Nothing was fetched" line. Run against an empty scratch cache here it
returned 1. That is correct behaviour and the operator's real cache holds two dumps, so the
committed "exit 0" is true of this machine — but the claim is conditional on a seeded cache, and
the build's evidence states it flatly. Recorded as finding **R4**.

**And the same lesson has not reached three more printable strings** — finding **R1**, below.

---

# PART 4 — Q3: THE RESUMED-SUMMARY LINE

The rule as stated is *present iff the counters cannot ACCOUNT for the day*
(`sent + refused + failed < len(alerts)`). The build drives 0/1/2/3-of-3 delivered and the
all-refused case. Both of those move **one** counter, so neither can distinguish "did this process
do nothing" from "can this process account for the day". This review drove the shape that can:

```
1 sent + 1 refused + 1 failed, of 3 alerts  -> "1 sent, 1 refused (unvouched price), 1 failed"
                                            -> the clarifying line is ABSENT   (accounted == 3)
1 sent + 1 refused,            of 3 alerts  -> the clarifying line is PRESENT  (accounted == 2)
```

Three alerts accounted for by three different counters is not a resume, and the sentence that
explains a resume is correctly not on it. Re-confirmed on the shipped sink, at HEAD.

**The one spurious-fire vector the change opens, closed at the source.** `deliver` returns without
touching a counter when `alert.kind not in self.kinds`. Under the OLD guard that could not matter —
a single delivery suppressed the line — but under the new one a filtered kind would make an
ordinary morning read as a resumed one. It cannot happen, and a kept probe pins the two sets to
each other rather than trusting the docstring's *"everything by default"*:
`TelegramSink().kinds == ls.ALERT_KINDS`, both being exactly
`{armed, trigger, exit, square-off, failure}`.

---

# PART 5 — Q1, C2, C5: THE PROSE, RE-CONFIRMED FROM THE SOURCE

**Q1 — the handover's three ARE the pack's three, parsed from the pack.** This session opened
`docs/validation/trader_pack.md`, split on its own `### Three ways forward` heading and read the
bolded options out of it rather than comparing against a list written here:

```
the pack offers : ['Retire it.', 'Change it.', 'Take it live knowing the arithmetic.']
the handover carries all three : True
in the PACK's order            : True
'Automation' anywhere in the pack's section : False
the handover states it as the v2 item       : True   ("Automation was never one of the three.")
"This is the path being delivered" sits under the THIRD option : True
```

*Change it* — the option the trader still has and which the document nowhere told him about — is
restored with the pack's own caution travelling with it (*"fitted to that history"*) and with
*"This option stays open."* The half of the old paragraph that was true and load-bearing survives.

**And the defective test is repaired at the SOURCE.**
`tests/test_handover.py::test_the_THREE_PATHS_are_the_packs_own_three_and_the_chosen_one_is_named`
now opens `trader_pack.md` and `re.findall`s the pack's headings; it no longer asserts the
handover's own three. That was the sixth pinned-at-the-wrong-place occurrence in this repository
and the repair is the point of the finding.

**The rewrite did not cost the handover its trader-facing properties**, re-swept here because
section 4 was rewritten: zero `--flags`, zero `python `, zero `acumen.*`, zero `src/`, zero `.py`
anywhere in 185 lines; the no-order sentence still at **line 19**; the 0.5229%–2.6808% bracket and
*"not the flattering end of it"* intact; success still defined as *"a test of the plumbing, not of
the strategy"*.

**C2 — the runbook quotes the constant.** `gate.NOT_READY_LINE`
(*"NOT READY for a live dry-run week -- do not start it"*) appears verbatim, in section 0 beside
the gate's own READY line, and the morning REFRESH's similar-looking
*"NOT READY -- the screener must not start"* is still quoted and still tabulated as the different
step it is. The document now says which is which by the words it uses.

**C5 — Q-30's heading marks CLOSED like Q-28 and Q-29**, by the same rulings block on the same day:

```
Q-28 · chunk 13 · class A · **CLOSED 08-Aug-2026** (see ARCHITECT'S RULINGS 08-Aug-2026, below) ...
Q-29 · chunk 13 · class A · **CLOSED 08-Aug-2026** (see ARCHITECT'S RULINGS 08-Aug-2026, below) ...
Q-30 · chunk 13 · class A · **CLOSED 08-Aug-2026** (see ARCHITECT'S RULINGS 08-Aug-2026 on
                             REVIEW_13, below) · option (a): a live morning screens the 204
                             SETTLED symbols only
```

The ruling text is unmoved; only the heading changed. Q-19 and Q-31 remain OPEN, both unchanged,
neither touching this chunk.

---

# PART 6 — THE FOUR FLIPPED PINS, EACH FAILING ON `ee412a6`

HEAD's test files were copied onto a clean checkout of `ee412a6` — pre-fix `src/` and pre-fix
`docs/` — and run by this session. Every one fails **on its own subject**, so none of them is an
import artefact:

| the pin | how it fails at `ee412a6` |
|---|---|
| `test_FLIPPED_the_HANDOVERS_THREE_PATHS_ARE_the_PACKS_own_three` | `the pack offers 'Retire it.' and the handover does not carry it` |
| `test_FLIPPED_B420_a_prior_day_recording_that_cannot_SAY_which_day_it_is_DOES_block` | `module 'acumen.live_refresh' has no attribute 'recording_day_or_name'` |
| `test_FLIPPED_B420_a_recording_with_NO_manifest_at_all_is_SURFACED_by_the_queue` | `but it is NAMED, not skipped` |
| `test_the_RUNBOOK_and_the_GATE_agree_on_the_SEVEN_CHECK_NAMES_verbatim` (C2, flipped in place) | the runbook does not carry `NOT_READY_LINE` |

And the same for the build's five new tests, the repaired handover test, C1's two assertions in
`test_dry_run_readiness.py`, Q3's extension in `test_chunk15_carried_defects.py`, and eleven of
this review's own fourteen probes — **24 failed, 3 passed** at `ee412a6`. The three that pass are
this review's own INVARIANT probes (a readable manifest never reaching the fallback; the absent
live root; the sink's kind set covering every alert kind), which are true on both trees by design
and are not flips.

All of them pass at HEAD.

---

# PART 7 — PURITY UNMOVED

**The same git blobs at `ee412a6` and `29cd748`:**

```
bias.py  poc.py  signals.py  simulate.py  bias_engine.py  signal_engine.py
backtest.py  parity.py
```

**All six published artefacts, byte-identical as git blobs across the span:**
`chunk9b_backtest_report.md`, `points_by_symbol.md`, `trader_pack.md`, `trader_pack.json`,
`chunk14_parity_report.md`, `chunk14_parity_sample.json`.

**Fixtures frozen**: zero files moved under `tests/fixtures/` or `poc/data/`.
**CONTEXT.md and plan.md: untouched.**

## 7.1 · Parity, re-derived — and one thing found on the way

`docs/evidence/chunk14_parity.py` run by this session to SCRATCH outputs, so the committed
artefacts were not overwritten: **15 days, 14 judged, 14 matched, 0 mismatched, 1 disclosed** —
the verdict REVIEW_15 and the build both state. The regenerated report is byte-identical to the
committed one apart from its own run stamp and the scratch sample's filename.

**Two days spot-checked field by field**, both identical to the committed artefact in every field:

| day | stratum | bias / rule | POC | reference | boundaries | mismatches |
|---|---|---|---|---:|---:|---:|
| **ITC 2026-06-10** | carried-witness | bearish / `inside-bar-carry` | `56655/2` (half-paise, E11) | 28440 | 18 | **0** |
| **ADANIENSOL 2026-05-08** | gap-entry | bearish / `rule-1-breakout` | 138155 | 138020 | 18 | **0** |

**And a difference the markdown report hides.** The machine-readable
`chunk14_parity_sample.json` does NOT reproduce exactly: on **ADANIPORTS 2026-02-06** — the
ORACLE-REFUSED, **disclosed** day — this session's run reports `transitions_equal: false` with 39
mismatch entries where the committed sample reports `true` with 38, the extra entry being
*"transition trail: the live day's trail differs from the backtester's"*. It is invisible in the
report because the markdown does not surface `transitions_equal` for a day it discloses rather
than judges, which is why REVIEW_15's byte-identical-report finding did not catch it.

**It is not this span's doing, and that is measured rather than argued:**

```
HEAD      29cd748 : judged 14  matched 14  mismatched 0  disclosed 1 | ADANIPORTS eq=False  39
BASE      ee412a6 : judged 14  matched 14  mismatched 0  disclosed 1 | ADANIPORTS eq=False  39
COMMITTED 14-Aug  : judged 14  matched 14  mismatched 0  disclosed 1 | ADANIPORTS eq=True   38

HEAD days payload == BASE days payload : True   (every field of every one of the 15 days)
```

The pre-fix tree and HEAD produce the **same bytes**, so the cleanup changed nothing here; and
structurally it could not have — `live_refresh`, `telegram_sink` and `dry_run_readiness`, the three
modules this span touched, are **not reachable at all** from the parity path (checked by importing
exactly what the evidence script imports and inspecting `sys.modules`: 27 `acumen.` modules load,
none of them these three). The delta therefore originates at or before `ee412a6` — the chunk-15
body or the chunk-14 fix, both already reviewed — and it lands only on a day CONTEXT 4.7 discloses
rather than judges. **No judged day moved, no decision moved, and the verdict is identical in all
three runs.** Recorded as finding **R6**.

---

# PART 8 — B431 – B435, ONE LINE EACH

All five numbers are present in `PROGRESS.md`, no gaps.

| # | judgment |
|---|---|
| **B431** | **APPROVED**, and it is the decision the whole cleanup turns on. Plain block-on-unknown closes Q2 and re-opens B420 — every undatable artefact would hold every future morning hostage. The manifest-first / name-fallback reading closes the hole and keeps the judgment, and this review proved the part that makes it affordable and that no test covered: a DATED blocker stops exactly ONE morning and ages out by itself. The claim that the name reaches the blocking test alone is proved by AST over both loops and by the absence of a `verification.json` on disk. |
| **B432** | **APPROVED.** Surfacing is right for the reason given — a recording absent from that list reads as one that PASSED, which is M15's shape one filter earlier — and the stated consequence is disclosed honestly rather than buried. Two behaviour changes it also buys are NOT stated and are measured here (finding R2): a corrupt-manifest REPLAY of the prior day now blocks, and a future-dated unreadable entry is surfaced. Both are correct; the first is B424's own approved reasoning applied from the other side. |
| **B433** | **APPROVED**, and the stronger of the two remedies the review offered. Re-wording the attribution would have left the trader's document of record silent about an option that is still his; restoring the pack's three gives it back with the pack's own caution attached. The load-bearing half of the old paragraph — automation is explicitly not built — survives and is now stated as what it is. |
| **B434** | **APPROVED.** "Accounted for", not "delivered", is the right subject: a refusal and a failed send are both this process accounting for an alert. Driven here at the mixed 1/1/1 shape the build's single-counter matrix cannot distinguish, and the one spurious-fire vector the change opens (a filtered alert kind) is closed by pinning the sink's default kinds to `ls.ALERT_KINDS`. |
| **B435** | **APPROVED.** A constant rather than a literal is right — the refusal, its tests and any later document read one string. The test's discipline is the part worth keeping: it reads the command OUT of the refusal and runs it as a real subprocess with `PYTHONPATH` stripped, because `pyproject`'s `pythonpath = ["src"]` is pytest's and not a subprocess's, which is exactly how B429's original defect stayed invisible to a green suite. Re-run independently here. One conditional in the evidence, finding R4. |

---

# PART 9 — THE STANDARD SWEEP

**Suite, from a clean `git clone` at `29cd748`, run ALONE:**

```
2598 passed, 1 skipped, 0 failed   in 1187.36s (0:19:47)
```

**Exactly the build's claim.** The one skip is the `.env`-input leak probe
(`tests/test_review13_probes.py:698`), which skips itself when `.env` is absent -- a clone must
skip it and the operator's tree must run it. Confirmed by reading the guard, not by assuming it.

**Suite in the operator's own tree, with this review's 14 kept probes:**

```
2613 passed, 0 skipped, 0 failed   in 683.57s (0:11:23)
```

**2,599 (the build's operator-tree claim) + 14, to the test.** No skips, no xfails. Both runs are
slower than the build's recorded times because this machine spent the session at 92-98% memory
load; neither the counts nor the outcomes are affected by that.

**The test census, re-derived by AST across the span** — and the build's arithmetic is right:
**1,852 -> 1,857 test functions in 100 -> 101 files (+5)**. **Three names gone, and all three are
the FLIPS**, each with its `FLIPPED_` counterpart in the new list; the only file that loses a name
is `tests/test_review15_probes.py`, which loses exactly those three and gains their flipped
versions. **No `skip` or `xfail` marker was added anywhere in the span.** Nothing weakened,
deleted or skipped.

**Chain.** 3 commits, linear, **0 merges**. `main == origin/main` at `29cd748` on entry.

**REVIEW_7 C1: correct.** Both commits touching `src/` or `tests/` (`be8c2f3`, `5acf315`) carry
`(unreviewed)`. `29cd748` touches neither — only `PROGRESS.md`, `STATUS.md` and
`docs/evidence/` — so it correctly carries none.

**No AI attribution.** Three case-insensitive hits across the span's messages, all three the
filename `CLAUDE.md`, which CLAUDE.md's own git rule explicitly permits.

**Secrets: none.** No credential-shaped string in the span diff; the only matches are prose about
*"the token's secret half"*. `.env` is untracked and gitignored, and was never read, printed or
echoed by this review.

**B420's recorded text is corrected in place with the original preserved**, in the shape the
chunk-15 build used for B328 — verified in `PROGRESS.md`. A recorded decision that was true of the
intent and false of the code is now stated correctly under the original rather than quietly
rewritten.

---

# PART 10 — FINDINGS

## R1 · MEDIUM (code) — the dead `-m acumen.` form survives in three PRINTABLE strings elsewhere

**CARRIED, pre-existing, outside this span, and not raised by REVIEW_15.** C1 named
`check_master`'s refusal and the cleanup closed exactly it. The identical defect — a printed
remedy that answers `No module named 'acumen'` on the operator's own tree — survives in three
operator-facing strings the AST sweep found:

| site | when the operator sees it |
|---|---|
| `live_screener.py:2373-2375` (`_require_day_master`) | **the LIVE MORNING's own refusal** when the day's dump is missing — names BOTH `-m acumen.run_screener --refresh` and `-m acumen.instrument_master` |
| `backtest.py:1589` (`named_master`) | reached by the pre-open verification step when a recording's master cannot be loaded |
| `backtest.py:1616` (`CA_REFRESH_FENCED`) | printed on **every** preflight; names `-m acumen.ca_report` |

All three verified failing in a bare clone here. The first is the most operator-facing of the four
sites this lesson has now been raised on: the readiness gate runs the day before, while
`_require_day_master` fires on the morning itself, at the moment CONTEXT 4.7 refuses to start.

**Why it is not blocking and not a FAIL of this span.** It is not this cleanup's doing, it was not
one of the nine findings, and a re-check scoped to the cleanup diff cannot fail the cleanup for a
defect the cleanup did not create and was not asked to fix. Every one of the three also names a
working first remedy or is informational rather than instructional.

*Remedy: three strings. The working launchers already exist —* `scripts/fetch_instrument_master.py`,
`scripts/run_screener.py`, `scripts/ca_report.py`. Pinned as MEASURED, with a flip instruction:
`tests/test_review15b_probes.py::test_R15B_C1_the_SAME_dead_form_elsewhere_in_src_is_MEASURED_not_assumed_absent`.

## R2 · INFO — two behaviour changes the surfacing buys, neither of them written down

`unverified_recordings` applies its `mode == "live"` and `day < before` filters only AFTER a
manifest has been read, so an entry that reaches the unreadable list skips both. Surfacing
therefore changes behaviour in two places neither B432 nor REVIEW_15 states:

* **a REPLAY whose manifest is corrupt, dated to the prior trading day, now BLOCKS** (it did not
  before). **Correct** — a manifest that cannot be read cannot say `replay` either, and calling it
  one would replace an unverifiable claim with a second unverifiable claim, which is **B424**'s own
  approved reasoning from the other side. A replay whose manifest IS readable is still filtered out
  and still cannot block, driven here.
* **a future-dated unreadable entry is surfaced** — named rather than skipped, and it does not
  block, because a future day is not the prior trading day.

Both measured and pinned. Recorded so a later session does not rediscover them in a market.

## R3 · INFO — an undateable entry blocks EVERY morning, and clearing it is an escalation

The disclosed price of the conservative reading, driven across three consecutive mornings. The
runbook's section 8 states it and tells the operator what to do — *"Tell the architect; do not
delete anything"* — which is right, because the live root is inside the stores and CLAUDE.md makes
store deletions operator-only with a verified snapshot first. Recorded for the architect's eye
before a dry-run week rather than during one: the only artefacts that can reach this state are ones
a dry-run week creates, and there is no operator action short of escalation that clears one.

## R4 · INFO — the launcher's exit code is conditional, and the evidence states it flatly

`scripts/fetch_instrument_master.py` ends `return 0 if existing else 1`. Run against an empty cache
it prints the same *"Nothing was fetched and nothing was written."* and returns **1**. The
committed `chunk15_cleanup_store_bracket.md` records `exit 0`, which is true of the operator's own
cache (two dumps held) and of the build's test (which seeds one), but is a property of the cache
rather than of the launcher. Nothing on the page is wrong; one number is conditional and does not
say so.

## R5 · INFO — the store-safety evidence script cannot run under memory pressure

`docs/evidence/housekeeping_13aug_store_fingerprint.py` allocates a fresh 1 MB buffer per read and
died with `MemoryError` on this machine at 97–98% memory load. It is the tool the whole data-store
safety discipline produces its evidence with, so its failing exactly when the machine is loaded is
worth a line. **Not a repo defect and not this span's doing**; the committed script is frozen
evidence and was correctly left untouched. `docs/evidence/review15b_store_fingerprint.py` is this
review's allocation-free implementation of the same recipe and reproduces the frozen digests
exactly, so a future session has a route that works under load.
## R6 · INFO — the committed parity SAMPLE no longer reproduces on the disclosed day

Measured in 7.1. `chunk14_parity_sample.json` records `transitions_equal: true` / 38 mismatches for
**ADANIPORTS 2026-02-06**; both current trees produce `false` / 39. **Not this span's doing** —
`ee412a6` and `29cd748` produce byte-identical day payloads, and none of the three modules this
span touched is reachable from the parity path. It affects only the diagnostic detail of a day
CONTEXT 4.7 **discloses rather than judges**; the verdict (14 judged / 14 matched / 0 mismatched /
1 disclosed) is identical across all three, and the committed markdown report still regenerates
byte-identically, which is why it went unseen.

Worth the architect's eye for one reason only: the sample is the artefact the suite re-runs so that
*"a regression fails the build rather than waiting for someone to re-run this script"* (the report's
own words). A committed artefact that no longer reproduces on one day is a tripwire with one leg
loose. The right owner is whoever next touches the parity harness, not this review — a review fixes
nothing, and the divergence originates outside the span under re-check.


---

# WHAT THIS REVIEW COULD NOT FALSIFY

That the fail-closed reading is affordable. A reviewer's instinct with Q2 is that the conservative
fix trades one hole for a worse one — a screener that refuses mornings on the strength of an
artefact nobody can read is a screener the operator learns to override. The build saw that and
answered it with the name fallback, and the answer holds under attack: a legitimate week never
reaches the new code, a dated blocker costs exactly one morning and clears itself with nothing
deleted and nobody consulted, and the one entry that really is permanent is one nothing can date,
which is both rare and correctly loud. The single design decision that buys all of this — read the
manifest, then the name, and only then refuse — is also the one that keeps a directory label from
ever deciding which day a verdict is written for, and both halves were checked here structurally
and on disk.

The findings that remain are of one kind, and it is the same kind REVIEW_15 ended on: a sentence
that claims slightly more than its source supports — an exit code that is conditional, two
behaviour changes nobody wrote down, and a lesson about launchers that has reached four sites and
not the fifth, sixth and seventh. Not one of them moves a number, a decision, or a rupee. That the
last findings of the last review of the last chunk are about attribution and provenance rather
than arithmetic is, again, the honest summary of where this repository ended up.

**VERDICT: PASS. The chunk-15 cleanup is sealed, every chunk is sealed, and the tool is DONE.**
