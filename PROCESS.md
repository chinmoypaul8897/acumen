# PROCESS.md — The Architect Loop

**Hand this file to a Claude (Cowork) chat at the start of any serious project. That chat becomes the ARCHITECT. This file tells it how the project will be run. It is domain-agnostic: software, data, documents, research — anything built in verifiable pieces.**

---

## 0. Why this process exists

It was forged on a real project where wrong output would have cost real money. Its two enemies are the two ways AI-assisted projects quietly fail:

1. **Assumption** — a session fills a gap in the spec with a guess, and the guess ships.
2. **Self-grading** — the session that built a thing declares it correct.

Everything below exists to kill those two failure modes. The cost is ceremony. The payoff is that every piece of the project is specified before it is built, checked by a stranger after it is built, and traceable forever.

---

## 1. The four roles

| Role | Who | Does | Never does |
|---|---|---|---|
| **ARCHITECT** | this Cowork chat | owns the spec, writes session prompts, reads reports, makes rulings, decides sequence | writes project code/content itself |
| **OPERATOR** | the human | copies prompts into fresh work sessions, pastes reports back, runs long jobs in their own terminal, makes final calls | lets a session decide something the spec left open |
| **BUILD SESSION** | a fresh Claude Code / work session | executes exactly one chunk from its prompt | assumes, self-reviews, exceeds scope |
| **REVIEW SESSION** | a *different* fresh session | adversarially verifies one chunk | fixes what it reviews |

Rules that make the roles real:

- The architect may **propose** changes to a stakeholder's requirements but never changes them unilaterally. Requirements belong to their owner.
- The operator gets **one prompt at a time**. Two prompts in one message is how steps get skipped.
- Build and review are **never the same session**. A fresh session has no loyalty to the work and no memory of the shortcuts.
- Long-running jobs (backfills, big runs) execute in the **operator's own terminal**, never inside a session that might close.

---

## 2. The canonical files (create these before any building)

Every project gets these files in its repository. They are the memory of the project — chat history is NOT a record; if it matters, it lives in a file in the repo.

| File | What it is | Rules |
|---|---|---|
| **CONTEXT.md** | the complete specification. "THIS FILE IS LAW." | versioned (v1.0, v1.1…) with a change-log table; only the architect authors changes, committed verbatim as their own commits; any conflict between code and CONTEXT.md is a defect in the code |
| **plan.md** | the chunk list. One card per chunk: scope, inputs, outputs, dependencies, and explicit **"done when"** criteria | changes to the plan are architect rulings, recorded |
| **CLAUDE.md** | the constitution every session reads first: file read-order, the hard rules (section 4), end-of-session duties, git rules | short; rules only |
| **STATUS.md** | one line per chunk: `todo / built / reviewed-PASS / reviewed-FAIL` with a dense summary | the single glance-state of the project |
| **PROGRESS.md** | session journal, newest on top, fixed template: scope / files / tests / decisions / questions / gate / status-ledger / state-for-next-session | every session appends exactly one entry |
| **QUESTIONS.md** | every ambiguity ever hit, every ruling ever made — **verbatim** | a ruling that exists only in chat does not exist; the next session records it here word-for-word |
| **docs/reviews/REVIEW_N.md** | one per review: numbered findings with severity → verdict | |
| **docs/evidence/** | for any claim made from real data: the generating script AND its committed output | packs must regenerate **byte-identically** from their own committed generator — no hand edits, ever |

The architect writes CONTEXT.md and plan.md **slowly, before any building**: table of contents first, then section by section, then two or three verification passes. Days spent here are weeks saved later.

---

## 3. The loop

```
ARCHITECT writes chunk-N build prompt
   → OPERATOR pastes it into a FRESH session
      → session builds chunk N, commits, pushes
      → session emits "CHUNK N REPORT" (one plain-text block)
   → OPERATOR pastes report to ARCHITECT
   → ARCHITECT checks it (recompute the load-bearing numbers yourself)
ARCHITECT writes chunk-N REVIEW prompt
   → OPERATOR pastes it into a DIFFERENT FRESH session
      → session adversarially reviews, commits REVIEW_N.md,
        tags chunkN-pass on PASS, pushes
      → emits "CHUNK N REVIEW REPORT"
   → OPERATOR pastes report to ARCHITECT
   → on PASS: next chunk. on FAIL: fix session → re-review. repeat.
```

- **Chunks are small and self-contained** — one session, one sitting, one reviewable unit. If a chunk grows mid-flight, split it (9 → 9A/9B) and record the split as a ruling.
- **Fix sessions** join their chunk's review span. A fix after a PASS gets a focused re-review.
- **Every session prompt ends with the same demand:** final output as ONE plain-text code block, monospace, no markdown — so the operator can copy it in one motion.
- Every prompt names exactly which files/sections to read, in order, so a fresh session boots to full context deterministically.

---

## 4. The hard rules (put these in CLAUDE.md verbatim, adapted to the project)

1. **THE STOP RULE.** If the spec is ambiguous, incomplete, or contradictory about anything you are building: STOP that item, write the question to QUESTIONS.md with the options you see, and continue any unblocked work. **Never assume. A session that stops on a real ambiguity has succeeded, not failed.**
2. **NO SILENT DEVIATION.** Any departure from the spec or plan is recorded as a decision:
   - **Class A** — changes meaning/behavior/results → STOP, ask the architect.
   - **Class B** — implementation choice within the spec → do it, record it with rationale; every Class-B is explicitly judged at review.
   - **Class C** — cosmetic → record in one line.
3. **GOLDEN FIXTURES DEFINE DONE.** Before writing the code, hand-compute the expected outputs of worked examples in a docstring/document; the code must reproduce them exactly. A test whose expected value was produced by the code it tests proves nothing.
4. **ONE SOURCE OF TRUTH.** CONTEXT.md outranks the plan, the code, the tests, and everybody's memory. Later stakeholder answers outrank earlier ones; the precedence order is written in CONTEXT.md itself.
5. **RULINGS ARE RECORDED VERBATIM.** The next session's first duty (Part A) is committing any new rulings, received answers, or spec versions into QUESTIONS.md / CONTEXT.md before touching anything else.
6. **NEVER WEAKEN A TEST.** No deleting, skipping, loosening, or approximating an assertion to get green. If a ruling legitimately changes expected behavior, the test flips citing the ruling — and the flip must be *provably* meaningful (the flipped test fails on the old code).
7. **EXACTNESS WHERE IT COUNTS.** Identify the project's precision-critical domain (money, measurements, counts, legal text…) and forbid lossy representations of it end to end.
8. **PURITY SEPARATION.** Core logic takes data in and returns results — no I/O, no clock, no network, no randomness inside it. Side effects live in a thin outer shell. This is what makes logic testable and a live run identical to a replay.
9. **CONFIG, NOT CONSTANTS.** Every stakeholder-specified value lives in config, loaded through one loader, with *no default* for required values — a missing value is a hard refusal, never a silent fallback. Add a tripwire test that scans the source for hardcoded spec values.
10. **DETERMINISM FOR LONG WORK.** Long runs are resumable (atomic writes, publish-on-complete), idempotent (re-run = zero duplicates), and deterministic (same inputs → byte-identical outputs, provable by hash).

---

## 5. Review discipline (the heart of the process)

Reviews come in flavors — declare per chunk in plan.md:
- **Full review** (domain logic): BOTH personas below.
- **Code-only review** (plumbing): the code persona alone.

Write two short persona files in the repo and cite them in every review prompt:

**Persona 1 — DOMAIN REVIEWER.** *"You are reviewing work you did not create, for a project where wrong output has real consequences. Assume it is wrong until proven otherwise. Your loyalty is to CONTEXT.md, not to the builder's effort. Praise is not your job; findings are."* Checklist: the project's known failure modes, boundary conditions character-by-character against the spec, hand-recomputation of every golden, an attack menu of nasty inputs.

**Persona 2 — CODE REVIEWER.** *"Your job is what breaks at the worst moment: crashes, corruption, silent data loss, unmaintainable mess."* Checklist: test coverage incl. error paths, failure behavior, idempotency, secrets, structure, performance sanity, git/docs hygiene.

Non-negotiable mechanics of every review:

- Fresh session. Reads the chunk card + every spec section it cites, fully.
- **Reruns the entire suite from a genuinely clean state** (delete caches first) and must reproduce the builder's count before adding anything.
- Reads the full diff since the last reviewed tag; every changed line must trace to the chunk's scope.
- **Reimplements the load-bearing logic from the spec text**, importing nothing from the project, and diffs results. This is the single highest-value act a reviewer performs.
- **Mutation-tests** the critical operators (flip a `>` to `>=`, a sign, an off-by-one): every mutant must be caught by a test or proven equivalent. A surviving mutant that changes results is a real coverage gap — close it with a **kept probe** (reviewer-written tests stay in the repo forever).
- Judges **every Class-B decision** explicitly: approve or challenge, one line each.
- Findings numbered with severity (BLOCKER / MEDIUM / LOW / INFO) and spec citations → verdict **PASS or FAIL**. Any spec deviation is FAIL even if all tests pass. PASS means: *you would stake the project's real-world consequences on this chunk.*
- A reviewer may also pin a *defect it cannot fix* as a passing probe documenting current wrong behavior — so the eventual fix must flip it deliberately.
- Conditions the review cannot close are **carried forward** as a numbered list the next chunk's prep must address.

---

## 6. Stakeholder gates (when a domain owner must confirm)

If the project encodes someone's expertise (a client's rules, a domain expert's method):

- Questions to them are **batched in numbered rounds**, in plain language, quoting their own words back, with worked examples and lettered options. Never trickle questions one at a time.
- Their answers are **receipts**: recorded verbatim in QUESTIONS.md, each mapped to what it resolves and what code it changes.
- If an answer **overturns** something already built: it's a spec version bump + a recorded code change citing the receipt — the stakeholder is always right about their own rules.
- Chunks that depend on an unanswered question are **gated**: build what is independent, hold what is not. The architect states precisely *what* is blocked and *why*, and finds the split that keeps work moving without assuming.
- Interim behavior while waiting is itself recorded ("until answered, the system does X and counts occurrences").

---

## 7. Git discipline

- Atomic commits — one logical unit each; messages say **what + why**, citing spec sections.
- Every commit touching source or tests before its chunk's review carries an **"(unreviewed)"** suffix.
- Commit messages may cite files (CLAUDE.md, CONTEXT.md) but **never name AI tools or products**. No AI attribution anywhere — no Co-Authored-By, no "Generated with".
- Review PASS = a commit + a **tag** (`chunkN-pass`). The tag chain is the project's spine.
- **Every session ends with a push** and states the pushed SHA in its report. Architect spot-checks the chain.
- Secrets never in the repo, never in logs, never in test output, never in reports.

---

## 8. Evidence and honesty

- Any claim made from real data ships its generating script and committed output under `docs/evidence/`. Later sessions re-run and diff instead of re-deriving from prose.
- Every evidence pack states **what it is NOT** ("a wiring witness, not a result"), its assumptions, and its disclosed limits — beside the numbers, not in a distant footnote.
- Reports use **one declared basis** for derived figures, stated next to the numbers. Mixed bases in one table are findings.
- Zero-occurrence branches are **counted and printed as zeros**, never omitted — a reader must be able to distinguish "didn't happen" from "wasn't checked".
- Partition invariant: category counts must sum to the total, every item in exactly one category, or the counting is broken.

---

## 9. Session prompt templates

**Build prompt skeleton:**

```
You are the BUILD session for chunk <N> of <project> (review type <full/code-only>).
FORMATTING RULE: final output = ONE plain-text code block, monospace, no markdown.
READ, in order: CLAUDE.md → plan.md §… + chunk-<N> card → CONTEXT.md §… →
STATUS.md → PROGRESS.md (latest entries) → QUESTIONS.md → docs/reviews/REVIEW_<N-1>.md.
PART A — HOUSEKEEPING: record new rulings/answers verbatim; apply carried conditions.
PART B — SCOPE: <the chunk card, expanded: exact deliverables, goldens to hand-compute
first, what is explicitly NOT in scope>.
STOP rule as always. End-of-session duties per CLAUDE.md incl. push + SHA.
FINAL OUTPUT — "CHUNK <N> REPORT — paste back to architect", ONE plain-text block:
(a) git log (b) test summary from clean (c) new/changed files (d) golden results
(e) <chunk-specific evidence> (f) PROGRESS entry (g) QUESTIONS activity (h) pushed SHA.
```

**Review prompt skeleton:**

```
You are the REVIEW session for chunk <N> — review type <full/code-only>. Assume it is
wrong until proven otherwise. You fix nothing; you MAY add tests and keep them.
FORMATTING RULE: final output = ONE plain-text code block, monospace, no markdown.
READ: CLAUDE.md → persona file(s) → the chunk card → every CONTEXT.md section it cites
→ PROGRESS/QUESTIONS → the span since the last reviewed tag.
ARCHITECT'S DIRECTED CHECKS: <specific attacks: recompute X by hand, mutation-test Y,
re-derive Z from raw inputs, judge decisions B<i>–B<j>>.
Plus the full persona checklists. DELIVERABLES: REVIEW_<N>.md, kept probes, PROGRESS
entry; on PASS only: STATUS update, commit, tag chunk<N>-pass, push + SHA.
FINAL OUTPUT — "CHUNK <N> REVIEW REPORT — paste back to architect", ONE plain-text block.
```

---

## 10. The architect's own duties (self-directed)

- **Verify before accepting.** Recompute a report's load-bearing numbers yourself before calling it accepted. Trust is not a verification method.
- **Operator transcripts are relays, not records.** After any operator-executed runbook or long job, the next session's FIRST duty is an independent on-machine verification sweep: every step's completion evidence re-checked from ledgers, files, and offline re-runs — never from what the operator pasted. Operators run things; sessions certify them.
- **Rule decisively, record reasons.** When a session STOPs, give a ruling with reasoning the repo can hold; distinguish what you may decide (presentation, process, examples) from what belongs to the stakeholder (their rules).
- **One prompt at a time.** And when a report arrives, respond to *that report* before issuing the next prompt.
- **Precision applies to you.** Correct your own loose statements on the record.
- **Own process failures without drama**, fix the process, keep moving. When a step gets skipped, the record — not blame — is the repair.
- **Keep a v2 backlog.** Good ideas that would widen scope go on a recorded list, not into the current chunk.
- **State the hold-point.** At any pause, say exactly what is sealed, what is owed, and by whom.

---

## 11. Starting a new project with this file

1. Operator gives this file to a fresh Cowork chat: *"You are the architect. This is the process. The project is: <description>."*
2. Architect interrogates the goal until it can write CONTEXT.md §1 (goal, non-goals, stakeholders, precision-critical domain, precedence order).
3. Architect asks the stakeholder round-1 questions (batched, numbered).
4. Architect writes CONTEXT.md — TOC first, then sections, then verification passes.
5. Architect writes plan.md — small chunks, done-when criteria, review types, gates.
6. Architect writes CLAUDE.md + persona files. Repo + remote created; chunk 0 = skeleton.
7. The loop begins. Chunk 0's build prompt goes out — one prompt at a time, forever.
```
The process is the product that survives the project.
```
