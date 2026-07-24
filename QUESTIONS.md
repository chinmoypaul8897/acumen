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

## Q-3 · chunk 1 · class A · **RESOLVED — executed chunk 2 (2026-07-24)** · NON-BLOCKING

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

**ARCHITECT'S RULING (relayed to the chunk-2 build session, 2026-07-24), verbatim:**

> "ARCHITECT'S RULING (option a with safeguards): historical trading days are DERIVED from
> the daily store — a date with a bhavcopy IS a trading day. Safeguards: (1) the downloader
> records every date's outcome as file-present / confirmed-404 / error; ONLY a
> confirmed-404 counts as a non-trading day — a download error is NEVER treated as a
> holiday; (2) the derived calendar's 2026 trading days must exactly equal the published
> holidays_2026.json snapshot's implied trading days over the ingested range (test);
> (3) the published endpoint remains authoritative for current/future dates (live
> screener); the derived calendar serves the backtest past. Execution: chunk 2."

**RESOLVED by the chunk-2 build session (2026-07-24).** Every clause of the ruling is now
code with a test behind it:

- **The ledger.** `src/acumen/bhavcopy.py` classifies every attempted date as
  `file-present` / `confirmed-404` / `error`, spelled exactly as the ruling spells them, and
  `src/acumen/daily_store.py` persists one ledger row per date (`coverage`,
  `coverage_summary`, `pending_dates`). A date never attempted is ABSENT from the ledger —
  absence is not a 404.
- **Safeguard 1 (an error is never a holiday).** Enforced twice. The downloader records
  `error` for anything that is not an HTTP 404, and `NseNotFoundError` was added so the 404
  case is a distinct TYPE, not a string comparison. The calendar loader then REFUSES to build
  at all if any date in its range is `error` or missing, rather than deriving around it
  (`tests/test_derived_calendar.py::test_an_error_in_the_ledger_blocks_the_calendar_entirely`).
  A related hazard the ruling did not have to mention: CONTEXT 4.1 dates the UDiFF cutover
  only to the month, so a date is only called `confirmed-404` after BOTH published formats
  have answered 404 — one extra request on a non-trading day, and no run of real trading days
  can be turned into holidays by a wrong boundary.
- **Safeguard 2 (cross-check).** `tests/test_daily_goldens.py::test_golden_derived_trading_days_equal_the_published_ones_over_the_window`
  — over the ingested window 2026-07-13..2026-07-24 the derived trading days are exactly
  `[13,14,15,16,17,20,21,22,23,24]`, identical to what `holidays_2026.json` implies, and the
  two calendars also agree on CONTEXT 3.2's bias pair. The two sources share nothing: one is
  built from 12 HTTP outcomes, the other from a JSON holiday list on a different endpoint.
- **Safeguard 3 (published stays authoritative for now).** `TradingCalendar.from_daily_store`
  requires every calendar date of each named year to be settled, so the CURRENT year cannot
  be derived until it ends — the live screener keeps using the published endpoint by
  construction, not by convention. `from_daily_store_range` covers a deliberately partial
  window and refuses any date outside it.

Live proof, not just tests: this session ingested 2026-07-13..2026-07-24 (10 present, 2
confirmed-404) and 2018-01-01..2018-01-15 (11 present, 4 confirmed-404) with zero errors.

One thing the ruling does NOT settle, raised as **Q-5** below: NSE occasionally holds a
weekend session, and "a date with a bhavcopy IS a trading day" makes such a Saturday a
trading day, which CONTEXT 7-E2 may or may not want excluded. Nothing in chunk 2 depends on
the answer; the code follows the ruling as written and makes the case visible.

---

## Q-4 · chunk 2 · class A · open · NON-BLOCKING for chunk 2 (BLOCKS chunks 3, 4 and 9)

**Question.** When NSE publishes the same symbol under more than one SERIES on the same
date, which series is "the stock" for this strategy?

**Why it is a hole.** CONTEXT 4.1 names the bhavcopy as the daily OHLCV source and names the
columns to read, but never mentions the `SctySrs` / `SERIES` column. CONTEXT 3.5 says the
backtest instrument is "cash equity prices (R2-Q35 agreed)" and CONTEXT 3.1 says the universe
is the F&O stock underlyings — neither names a series code. A symbol is therefore not a
unique key for a day's candle, and nothing in the spec says how to make it one.

**This is measured, not hypothetical.** Both ingested windows contain it, in both eras:

| date | symbol | series present | what they are |
|---|---|---|---|
| 2026-07-14 | BIOCON | `EQ`, `BL` | the equity, plus a block-deal window trade |
| 2018-01-01 | JSWSTEEL | `EQ`, `P2` | the equity, plus partly-paid shares |
| 2018-01-01 | UPL / VEDL | `EQ` + `Q1` / `P1` | same shape, other partly-paid codes |
| 2018-01-01 | NTPC | `EQ`, `N4`, `N6`, `N7`, `NB`, `NC` | the equity, plus five listed debt series |
| 2018-01-01 | SBIN / PFC / RECLTD / NHPC / MUTHOOTFIN | `EQ` + 2 to 5 `N*` series | same shape |
| 2018-01-01 | IRFC | `N1`,`N2`,`NA`,`NE`,`NJ`,`NK`,`NO` — **and no `EQ` at all** | debt-only in 2018; it listed its equity in 2023 |

Eleven F&O-universe symbols are ambiguous on 2018-01-01 alone, and 437 rows across that
two-week window. `BL` rows carry a real price and a real volume, so a naive "first row wins"
or "largest volume wins" would silently hand chunk 4 the wrong candle on exactly the days a
block deal happened — and those are eventful days. The IRFC line matters for a different
reason: a rule of the form "take the highest-volume row" would hand chunk 4 a DEBENTURE's
prices for a symbol whose equity did not exist yet, and nothing downstream would notice.

**Why it matters.** CONTEXT 3.2's bias reads candle(D-1) and candle(D-2). Two rows for one
date means either a doubled candle sequence or a coin flip. Either produces a plausible
number and a wrong trade.

**What this session did meanwhile.** Did NOT choose. The store keeps EVERY row with its
series (the card's "store everything, filter on query"), and `DailyStore.daily(symbol, ...)`
**raises** when a symbol-day is not unique, naming the series it found, with an explicit
`series=` parameter as the only way to disambiguate. No default of `"EQ"` exists anywhere in
`src/` (`tests/test_daily_store.py::test_two_rows_for_one_symbol_day_raise_instead_of_doubling_a_candle`
pins this against the real BIOCON data). Chunk 2's own goldens are unaffected — none of the
five `poc/data` symbols is ambiguous on the five golden dates.

**Options for the architect:**
(a) rule that the cash-equity series **`EQ`** is the instrument (with `BE`/`BZ` — the trade-
for-trade surveillance series — considered: a stock moved to `BE` still trades, just without
netting, and CONTEXT 3.1 excludes nothing);
(b) rule `EQ` plus a named list of acceptable alternates, in a documented precedence order;
(c) rule that a symbol-day with more than one series is EXCLUDED from the backtest and
counted in the CONTEXT 7-E3 exclusion report.

Chunk 3 (corporate actions) is the first session that must read a symbol's daily history
end-to-end and therefore the first that will hit this.

---

## Q-5 · chunk 2 · class A · open · NON-BLOCKING (relevant to chunk 9's full run and chunk 13)

**Question.** NSE holds occasional **weekend trading sessions** (a Budget-day Saturday, the
disaster-recovery live sessions). A full bhavcopy is published for them. Under the Q-3 ruling
such a date IS a trading day. Should CONTEXT 7-E2 also exclude it as a "non-standard session"?

**Why it is a hole.** Two spec statements point in different directions and neither was
written with the other in mind:

1. the Q-3 ruling: "a date with a bhavcopy IS a trading day" — unconditional;
2. CONTEXT 7-E2: "Non-standard sessions (Muhurat, special/shortened sessions) are excluded.
   Detection: candle data on a date absent from the trading calendar, or outside 09:15-15:30".
   E2's own detection rule cannot see this case at all — a Budget Saturday is a full
   09:15-15:30 session on a date the derived calendar DOES list (REVIEW_1 Finding 10 already
   recorded that E2 cannot detect a shortened session either).

**Why it matters.** It is not only "should we trade that day". CONTEXT 3.2's bias pair is
defined on TRADING days, so including or excluding one Saturday shifts the (D-1, D-2) pair
for the following Monday too — the effect reaches days that are not themselves in question.

**What this session did meanwhile.** Followed the ruling exactly as written: a date with a
bhavcopy is a trading day, weekend or not. The case is made VISIBLE rather than decided —
`TradingCalendar.weekend_sessions` lists any such date, and
`tests/test_derived_calendar.py::test_a_saturday_session_is_represented_honestly` pins the
representation (not the policy). Neither ingested window contains one, so nothing in chunk 2
turns on the answer; `weekend_sessions` was empty for both.

**Options for the architect:**
(a) weekend sessions are ordinary trading days (status quo — simplest, and the ruling's
literal reading);
(b) weekend sessions are excluded under E2 and are also skipped when forming bias pairs;
(c) excluded from trading but retained in the bias pair (they are real candles).
