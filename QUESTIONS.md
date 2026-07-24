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

## Q-1 · chunk 0 · class A · **CLOSED (executed chunk 1, 2026-07-24)** · NON-BLOCKING

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

**ARCHITECT'S RULING (relayed to the chunk-0 review session, 2026-07-24): option (a).**
The three documents move to `docs/`; `requirements.txt` moves to `poc/`. **Execution is
scheduled for chunk 1** — the chunk-0 review session did not move any file itself. Chunk 1
performs the move and marks this item closed; chunk 2 must read `RESULTS.md` from `docs/`.
Moving `requirements.txt` under `poc/` also settles the drift risk noted above: it becomes a
PoC-era artifact, and `pyproject.toml` is the single source of truth for dependencies.

**CLOSED by the chunk-1 build session (2026-07-24).** All four files moved with `git mv`
(rename detection 100% on all four — bytes unchanged): `RESULTS.md`, `acumen_poc.md`,
`TradingView_POC_Calibration_Guide.docx` → `docs/`; `requirements.txt` → `poc/`. Nothing in
the test suite or in `src/` referenced any of the four paths, so no code change was needed;
`pyproject.toml`'s only mention is a prose comment. **Chunk 2 must read `docs/RESULTS.md`.**

---

## Q-2 · chunk 0 review · class A · **CLOSED (ruling (a) executed chunk 1, 2026-07-24)** · NON-BLOCKING

**Question.** Where do the per-symbol `tickSize` values used by fixture F7 live, and are
they frozen with the CSVs?

**Why it is a hole.** CONTEXT §8 F7 names the `poc/data/*.csv` files "the authoritative
input" and asserts that a recomputed prorata POC must match the frozen printout to ±0.01.
But the CSVs are not sufficient input: CONTEXT §3.3 takes `tickSize` "per symbol from
instrument master", and the row grid (`totalTicks = round((top − bottom)/tick)`) depends on
it. The instrument master is a **daily live dump** (§4.3) and is **not** in the repo — the
only local copy is `cache/scrip_master.json` (35 MB), which is gitignored and disposable.

**Why it matters.**
1. **F7 is only reproducible with the right ticks.** The chunk-0 review recomputed all 25
   calibration days: with the correct per-symbol ticks the match is 25/25 exact; with ₹0.05
   hardcoded it is 15/25, and every DIXON day is wrong by ₹0.87–₹78. The failure is silent —
   the code looks right and returns a plausible price.
2. **F7 would become network-dependent.** If the tick is fetched at test time, a frozen
   fixture starts depending on a live daily endpoint, and a future NSE tick change (e.g. the
   Jun-2024 reform that moved sub-₹250 stocks to ₹0.01) would break a test that is supposed
   to be frozen.

**Measured values** (from the cached master, 2026-07-24; `tick_size` is in paise, ÷100 per
§4.3) — recorded here so they survive deletion of the gitignored cache:

| symbol | token | raw `tick_size` | tick |
|---|---|---|---|
| TCS | 11536 | 10 | ₹0.10 |
| RELIANCE | 2885 | 10 | ₹0.10 |
| HDFCBANK | 1333 | 5 | ₹0.05 |
| DIXON | 21690 | 100 | ₹1.00 |
| MANAPPURAM | 19061 | 5 | ₹0.05 |

**What the review session did meanwhile.** Nothing was moved, added to `poc/data/` or
changed — the fixture set is frozen and a review may not alter it. The values are recorded
above and in `docs/reviews/REVIEW_0.md` §2. Chunk 0 is unaffected; chunk 6 is the first
session that needs the answer (chunk 5A builds the instrument-master loader).

**Options for the architect:**
(a) freeze these five ticks as a small committed fixture beside the CSVs (e.g.
`tests/fixtures/f7_ticks.csv`) and have F7 read it — keeps F7 fully offline and frozen;
(b) have F7 call chunk 5A's instrument-master loader against the cached master, and document
that the cache must be retained;
(c) rule that the values above, recorded in CONTEXT §8, are themselves the frozen input.

**ARCHITECT'S RULING (relayed to the chunk-1 build session, 2026-07-24): option (a) —
frozen fixture; production code reads the instrument master.**

**CLOSED by the chunk-1 build session (2026-07-24).** Created `tests/fixtures/tick_sizes.json`
with the five measured ticks in RUPEES (already divided by 100 per CONTEXT §4.3), carrying a
`_note` field that states the constraint in the file itself:

> "FROZEN F7 calibration tick sizes (rupees). Tests only - production code must always read
> the instrument master (CONTEXT 3.3)."

Scope of the ruling, so chunk 6 cannot misread it: this fixture is a **test input only**. It
does not license a tick lookup table anywhere in `src/` — CONTEXT §3.3's "NEVER hardcode
0.05" and §4.3's instrument-master rule are unchanged, and chunk 5A still owns the real
per-symbol `tick_size` loader. F7 becomes fully offline and frozen; a future NSE tick reform
cannot silently move a calibrated fixture.

---

## Q-3 · chunk 1 · class A · open · NON-BLOCKING for chunk 1 (blocks chunk 9's full run)

**Question.** Where does the trading calendar for years BEFORE the current one come from?

**Why it is a hole.** CONTEXT §4.1 names exactly one holiday source —
`https://www.nseindia.com/api/holiday-master?type=trading` — and that endpoint publishes
**one year at a time**. The pull taken during this session (2026-07-24, frozen at
`tests/fixtures/holidays_2026.json`) contains 20 CM holidays and **every one of them is in
2026**. There is no historical parameter, and CONTEXT §4.1 names no archive.

**Why it matters.** CONTEXT §2 requires a backtest over "max history (min 5 years —
trader's Q36)", and CONTEXT §3.1 makes trading days load-bearing in two places that decide
real money:

1. **`bias_pair(D)`** (§3.2) must be the previous two *trading* days. A missing holiday makes
   the engine read a holiday's non-existent candle as candle(D−1) — or, more insidiously,
   shifts the whole pair by one day and computes a bias from the wrong two candles.
2. **E2 exclusions** (§7) key off "a date absent from the trading calendar".

An unloaded year is the dangerous case because the failure is silent: with no holiday data,
every Mon–Fri looks tradable, so roughly 12–16 phantom trading days per year get invented and
every bias pair spanning one of them is wrong. The code would look fine and the backtest would
report a number.

**What this session did meanwhile.** Did NOT guess. `TradingCalendar` carries the set of
years its data actually covers and **raises `CalendarError` for any date outside it** rather
than answering (`src/acumen/calendar.py`, `_require_covered`; tested in
`tests/test_calendar.py::test_uncovered_year_raises_instead_of_guessing` and
`::test_bias_pair_refuses_to_cross_out_of_the_covered_year`). Chunk 1's own goldens are all
2026 and are unaffected. The constructor already accepts a multi-year holiday set
(`TradingCalendar.from_holidays(..., covered_years=...)`), so whichever option the architect
picks needs a loader, not a redesign — `test_a_multi_year_calendar_answers_across_the_boundary`
already proves the cross-year walk works once the data exists.

**Options for the architect:**
(a) **Derive trading days from the daily store**: chunk 2 ingests 25 years of bhavcopy, and a
date with a bhavcopy IS a trading day. Free, self-consistent with the price data, and needs
no new source — but it makes the calendar a function of ingestion success, so a failed
download would masquerade as a holiday (mitigable: cross-check against the current year's
published list, which this session's fixture makes possible).
(b) **Archive the endpoint going forward** and source past years elsewhere (NSE circulars /
a published historical holiday list), committing them as a frozen multi-year fixture.
(c) **Restrict v1's backtest window** to the years for which a published calendar is held.

Chunk 2 is the first session that could act on (a); chunk 9's full-history run is the first
that is BLOCKED without an answer.
