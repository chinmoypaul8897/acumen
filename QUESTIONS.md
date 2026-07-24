# QUESTIONS.md — open items for the architect

Written by build/review sessions under the STOP rule (CLAUDE.md rule 1, CONTEXT §1-R1):
anything CONTEXT.md does not answer is written here and the affected part is halted —
never decided silently. The architect resolves each item (with the trader where needed) and
answers by amending CONTEXT.md; the session that consumes the answer marks the item closed.

Entries are appended in raised order. Each entry states: what is unanswered, why it matters,
what is blocked right now, and what the raising session did in the meantime.

Spec-question classes (plan.md §5): **A** = spec conflict or hole (this file). **B** =
implementation choice within spec (recorded in PROGRESS.md `decisions:`, not here).
**C** = plan change (architect-only).

---

## Q-1 · chunk 0 · class A · open · NON-BLOCKING

**Question.** Where do the four pre-existing PoC-era root files belong?
`RESULTS.md`, `acumen_poc.md`, `TradingView_POC_Calibration_Guide.docx`, `requirements.txt`.

**Why it is a hole.** CONTEXT §6's repo layout enumerates `src/ tests/ tests/fixtures/ data/
docs/ docs/reviews/ personas/ poc/` plus the six governance markdown files — none of these four
is named, so "restructure to the §6 layout" has no answer for them and chunk 0 refused to guess.

**Why it matters.**
1. `RESULTS.md` is load-bearing for a later session: chunk 2's done-criteria cite its verified
   TCS 2026-07-20 values (close 2251.10, volume 2,202,693), so its path must be predictable.
2. `requirements.txt` (the PoC's unpinned dependency list) is now a second source of truth
   beside `pyproject.toml`'s pinned dependencies — two lists that can drift apart.

**What chunk 0 did meanwhile.** Left all four untouched at the repo root and committed them
as-is. Nothing in chunk 0 depends on the answer; chunk 2 is the first session that reads
`RESULTS.md`.

**Options for the architect** (a ruling of "root is correct" is a perfectly good answer):
(a) move the three documents to `docs/` and `requirements.txt` to `poc/`;
(b) move all four under `poc/` as PoC-era artifacts;
(c) keep them at the root and note it in CONTEXT §6.
