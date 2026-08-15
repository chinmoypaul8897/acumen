# CLAUDE.md — Acumen Intelligence · Session Constitution

Backtester + live screener for one frozen trading strategy. Real money depends on correctness. These rules apply to EVERY session in this repo.

## Read order (before any work)

1. `CONTEXT.md` — the master spec. **IT IS LAW.** Never edit it. Never act against it.
2. `plan.md` — your chunk card only. Never edit plan.md.
3. `STATUS.md` — verify every dependency of your chunk is `reviewed-PASS`.
4. `PROGRESS.md` — entries for your chunk + its dependencies + the newest entry.
5. `QUESTIONS.md` — open items; if one touches your chunk, STOP on that part.
6. Fix sessions: also `docs/reviews/REVIEW_<N>.md` — the findings you are fixing.

## The five hard rules

1. **STOP rule.** If CONTEXT.md doesn't answer something you need, do NOT decide. Write the question to `QUESTIONS.md`, mark the affected part blocked, continue elsewhere or halt. A silent assumption in this repo is a defect even if the code works.
2. **The strategy is frozen.** No new indicators, filters, optimizations, or "better" logic — deviations from CONTEXT §3 are bugs by definition.
3. **Tests define done.** Every build ships unit tests + its card's golden fixtures, green. Fixtures under `tests/fixtures/` and `poc/data/` are FROZEN — never regenerate, never edit expected values (that requires an architect spec change).
4. **Read-only trading APIs.** No order-placement code anywhere. Never print, log, echo, or commit `.env` contents.
5. **One chunk per session.** Finish or hand off cleanly with an honest PROGRESS entry. Never silently expand scope.

## End-of-session duties (every session, no exceptions)

- Append a `PROGRESS.md` entry using the exact template in plan.md §6 (newest on top).
- Update your chunk's line in `STATUS.md`: `todo | built | reviewed-PASS | gate-closed(evidence path)`.
- Record every Class-B implementation decision under `decisions:` (see plan.md §5). Unrecorded deviation = defect.

## Reviews

- Reviews run in a FRESH session. Builder sessions never review their own chunk.
- Reviewer reads `personas/quant_reviewer.md` and/or `personas/code_reviewer.md` per the chunk card, reruns all tests, attacks beyond the fixtures, writes `docs/reviews/REVIEW_<N>.md` ending in PASS or FAIL.
- Any deviation from CONTEXT.md = FAIL, even if all tests pass.

## Git rules (professional history, non-negotiable)

- Commit per logical unit. Message format: short imperative summary line, blank line, body explaining WHAT changed and WHY (reference chunk + spec section, e.g. `chunk4: implement rule-3 tie predicate per CONTEXT 3.2`).
- Build commits end `(unreviewed)`; the review closes with `chunk<N>: reviewed PASS` and tag `chunk<N>-pass`.
- **No AI attribution anywhere** — no "Generated with", no Co-Authored-By lines, nothing. Clean human-standard history.
- Never commit: `.env`, `data/`, `cache/`, generated artifacts. Never force-push. Single branch `main`.
- Remote: origin = the private GitHub mirror. EVERY session's final end-of-session duty is: `git push origin main --tags`, and the session's final report block must state the pushed SHA. The remote is a backup mirror ONLY: never commit, edit, or merge via the GitHub web UI; never force-push; if local and remote ever diverge, STOP and ask the architect. If a session dies before pushing, the operator pushes manually before starting the next session. The repo stays private, zero collaborators.
- Commit messages may cite files (CLAUDE.md, CONTEXT.md) but must never name AI tools or products (REVIEW_7 C4 ruling).
- Every commit touching src/ or tests/ before its chunk's review carries the (unreviewed) suffix — no exceptions (REVIEW_7 C1).
- Any session making claims from real store data commits the generating script and its output under docs/evidence/ (REVIEW_7 C3).

## Data-store safety (architect-authored, 31-Jul-2026)

- Never link, junction, or symlink mutable stores (data/, cache/) into any
   worktree, temp dir, or disposable tree. Verification needs a COPY (read-only)
   or must run in place. (Q-18 incident.)
 - After every store-changing milestone, the OPERATOR snapshots data/ and cache/
   to an offline location before the next chunk begins. Sessions remind; the
   operator executes. (Q-18 incident.)
- Operator-executed runbooks are relayed, not certified: after any
   multi-step operator procedure, the next session's FIRST duty is an
   independent verification sweep of every step's completion evidence read
   from the machine itself — ledgers, files, digests, offline re-runs.
   Pasted transcripts are never the record. (Q-18 recovery lesson.)
- Stores live OUTSIDE the repository tree (data_root/cache_root in
   config.yaml). No git command can reach them. (Q-18 layer 1.)
 - Sessions treat the stores as READ-ONLY unless the architect's prompt
   explicitly sanctions a named write. Store DELETIONS are never session work
   — operator only, snapshot verified first. (Q-18 layer 2.)
 - The operator keeps TWO snapshot generations; a new snapshot never
   overwrites the previous until verified. The preflight prints the stores'
   last-changed timestamps so the operator can confirm the snapshot is newer.
   (Q-18 layer 3.)
- A review or any session may NEVER run a mutating CLI (--refresh, or anything that writes) against the real data_root/cache_root; mutations run against a SCRATCH copy only. (REVIEW_14 store incident.)
- A test that certifies a no-write property must drive the ACTUAL write path and fingerprint EVERY affected root, never assert its own name. (REVIEW_14 Q3 / the REVIEW_9B M1/M6 pattern, now 5 deep.)

## Code standards

- Python 3.10+, pytest, type hints on public functions.
- Engine modules (`bias`, `poc`, `signals`, `simulate`) are PURE functions — no I/O, no network, no clock reads inside them.
- Prices: integer paise internally; no float equality comparisons; POC may be half-paise (CONTEXT §7-E11). Timestamps: naive IST, open-stamped bars (E12).
- No hardcoded tick sizes, symbols, dates, or magic numbers — config and instrument master only.
- Network: polite throttle (≤2 req/s historical), exponential backoff, transient "access denied" bursts are NORMAL — retry, never treat first failure as empty (CONTEXT §4.3).
- UI work (chunk 11+): tokens from `DESIGN.md` only — never invent colors or typography.
