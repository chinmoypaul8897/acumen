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

## Q-4 · chunk 2 · class A · **RESOLVED — executed chunk 3 (2026-07-24)** · was BLOCKING chunks 3, 4, 9

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

**ARCHITECT'S RULING (relayed to the chunk-3 build session, 2026-07-24), verbatim:**

> "ARCHITECT'S RULING: the instrument is the equity series. daily() selects per symbol-date
> by whitelist EQ, else BE, else BZ (same equity in trade-for-trade settlement — matches the
> trader's TradingView chart). All other series (N* debt, P* partly-paid, BL block, and any
> other) are never the instrument: kept in store, ignored by queries. Two whitelist series on
> one symbol-date → raise loudly. No whitelist series → the equity did not exist/trade that
> day: empty result, not an error; a symbol's history starts at its first equity row
> (consistent with the per-symbol clamp). Unknown series encountered on F&O-universe symbols
> must be surfaced in the backfill/coverage report. Execution: chunk 3."

**RESOLVED — executed by the chunk-3 build session (2026-07-24).** Every clause is code with
a test behind it, in `src/acumen/daily_store.py`:

- **The whitelist.** `INSTRUMENT_SERIES = ("EQ", "BE", "BZ")` — one constant, cited to this
  ruling, used by `daily()` and by the series report. It is the ONLY series choice in `src/`
  (pinned by `tests/test_review2_probes.py::test_the_only_series_choice_in_src_is_the_q4_whitelist`,
  an `ast` walk, which replaces the probe that used to assert no choice existed at all).
- **Selection per symbol-date.** `daily()` now returns one row per date: the whitelist row if
  exactly one is present. NTPC 2018-01-01 (six series) returns its `EQ` row; BIOCON
  2026-07-14 (`EQ` + `BL`) returns `EQ`; the explicit `series=` escape still overrides.
- **Two whitelist series on one symbol-date raise loudly.** The precedence order is recorded
  in the constant, but the ruling's safety net takes priority over it, so the order never
  actually decides anything while the raise stands (recorded as decision B35). Proved on a
  synthetic DERIVED fixture (`tests/fixtures/two_whitelist_series.csv`), because no real
  bhavcopy in the repo carries the case.
- **No whitelist series is an empty result, not an error.** IRFC on 2018-01-01 is debt-only;
  `daily("IRFC", ...)` returns an EMPTY frame with the full column set. A symbol's history
  therefore starts at its first equity row, exactly as the ruling states.
- **Unknown series surfaced.** `DailyStore.series_report(symbols, from, to)` classifies every
  series seen as `instrument` (the whitelist), `known-non-instrument` (the `N*` debt, `P*`
  partly-paid and `BL` block families this ruling names) or **`unknown`**, and
  `DailyStore.unknown_series(...)` is the filtered view the backfill run prints, with the
  symbols and dates that carry each one. The two frozen bhavcopy fixtures contain no unknown
  series (they carry `EQ`, `N4/N6/N7/NB/NC/ND`, `P2`, `BL` only), so the classifier is pinned
  by unit test on the codes this item's own evidence table lists — including the one the
  ruling's examples do NOT cover: **UPL's `Q1`** on 2018-01-01 classifies as `unknown`, not
  as partly-paid, so it will be reported the moment the operator's full backfill reaches it.

**Appended by the chunk-4 prep session (2026-07-25).** IL and D1 series
(institutional/auxiliary) confirmed non-instrument — ignored by whitelist, surfaced in reports
(REVIEW_2/3 sightings: HDFCBANK, KOTAKBANK, MCX, INDHOTEL). These are `unknown` under
`classify_series` (neither the EQ/BE/BZ whitelist nor the named `N*`/`P*`/`BL` families), so
`daily()` never selects them and `series_report`/`unknown_series` surface them on the
F&O-universe symbols above — the ruling's "reported, never chosen" applied to two more codes.
`tests/test_series_selection.py` pins `IL` and `D1` as `unknown`.

---

## Q-5 · chunk 2 · class A · **RESOLVED — executed chunk 3 (2026-07-24)** · NON-BLOCKING

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

**ARCHITECT'S RULING (relayed to the chunk-3 build session, 2026-07-24), verbatim:**

> "ARCHITECT'S RULING: weekend-dated sessions are EXCLUDED from trading days, bias pairs, and
> trading, even when a bhavcopy exists (E2 applied: non-standard sessions; the Monday after
> pairs to Friday/Thursday). weekend_sessions stays surfaced; the backtest report counts
> these exclusions. CONTEXT E2 wording gains this clarification at its next version bump.
> Execution: chunk 3."

**RESOLVED — executed by the chunk-3 build session (2026-07-24).** In
`src/acumen/calendar.py`, `TradingCalendar._derive`:

- a `file-present` date that falls on a Saturday or Sunday is **not** added to
  `trading_days`. It goes to a new frozen field `excluded_weekend_sessions` instead, so
  `is_trading_day` and `is_standard_session` both answer **False** for it and `bias_pair`
  skips it exactly as it skips a holiday;
- `weekend_sessions` stays the public accessor (same name, same tuple-of-dates shape, still
  empty for a published calendar) and now reads from that field — the case remains VISIBLE,
  it simply no longer trades;
- the exclusions are **counted**: `TradingCalendar.excluded_session_counts()` returns
  `{"weekend-session": n}` for the chunk-9 report, and `DailyStore.coverage_summary()` counts
  `weekend_session` file-present dates over any range, which is what the backfill report
  prints.

Regression test = the exact case REVIEW_2 Finding 11 measured
(`tests/test_derived_calendar.py::test_q5_a_saturday_session_is_excluded_and_monday_pairs_to_friday_thursday`):
a synthetic Saturday 2019-06-01 session is `is_trading_day` **False**, `is_standard_session`
**False**, surfaced in `weekend_sessions`, and `bias_pair(Mon 2019-06-03)` is
`(Fri 2019-05-31, Thu 2019-05-30)` — the "one whole candle out" the finding warned about is
gone.

---

## Q-6 · chunk 3 · class A · **RESOLVED — executed chunk 4 prep (2026-07-25)** · was BLOCKING rights factors on real events

**Question.** CONTEXT §4.2's rights factor needs the **issue price S**. NSE's subject states a
**PREMIUM**, not S. How is S to be obtained?

**Why it is a hole.** CONTEXT §4.2 gives the formula in terms of S:

> Rights A:B at price S, cum-close P → `k = (P−E)/P` where `C = (P−S)·A`, `E = C/(A+B)`

Every rights subject in the three frozen windows carries the premium instead, or nothing at
all (measured, `tests/fixtures/ca/nse_ca_*.json`):

| symbol | ex-date | subject | what it gives |
|---|---|---|---|
| JMCPROJECT | 2016-01-11 | ` Rights 2:7` | ratio only — no price at all |
| SRPL | 2023-07-06 | `Rights 1:1 @ Premium Rs 1.30/-` | premium |
| BROOKS | 2023-07-28 | `Rights 1:16 @ Premium Rs 65/-` | premium |
| HINDWAREAP | 2024-10-25 | `Rights 119:758 @ Premium Rs 218/-` | premium |
| GEOJITFSL | 2024-10-07 | `Rights 1:6 @ Premium Rs 49/-` | premium |

The natural conversion is `S = face value + premium`. The obstacle is that the row's own
`faceVal` field is the face value **as of the query, not as of the event** — proved by
GREENPLY in the same snapshot: its January-2016 rows show `faceVal = 1`, the value AFTER the
5→1 split those very rows announce. Using it would silently mis-price any rights issue on a
symbol that later split. BSE is no help: its 21 rights rows in these windows all read
`Right Issue of Equity Shares`, with neither ratio nor price, and Yahoo is blind to rights
(CONTEXT §4.2 says so).

**Why it matters.** A wrong S moves k, and k multiplies a whole pre-ex history. With the
2016 JMCPROJECT numbers, an S that is off by one rupee moves k in the third decimal — which
is larger than the tick on most of the universe.

**What this session did meanwhile.** Did NOT guess. `factor_for` **requires**
`rights_issue_price_paise` and raises, naming this item, when it is absent;
`build_factor_table` collects the event as *pending* with the reason instead of returning a
factor. Nothing silently becomes `k = 1`. The FORMULA itself is fully tested — against the
architect's hand-derived case (1:4 @ 200 on P = 300 → k = 280/300) and against NSE's own
calculator XLSX (17:74 @ 65 on P = 107.10 → k = 0.9265654979940694, matched to the last digit
the file holds), both in `tests/test_ca_goldens.py`.

**Options for the architect:**
(a) rule `S = face value + premium`, and name the source for the face value **as of the
ex-date** (the bhavcopy carries no face value; the archive-era CSV does not either);
(b) source S from the rights circular / offer document per event (manual, but there are few
rights issues on F&O underlyings);
(c) rule that rights issues are treated like demergers — no factor, suppress the bias pair
across the ex-date — which is defensible for a strategy that only ever needs two consecutive
candles;
(d) rule that a rights issue on an F&O-universe symbol is excluded and counted (CONTEXT
§7-E3-style), with the occurrences listed in the backtest report.

Chunk 4 (bias) is the first session that consumes factors on real dates; the first rights
issue on an F&O underlying inside the backtest window is the first thing that needs this.

**ARCHITECT'S RULING (relayed to the chunk-4 prep session, 2026-07-25), verbatim:**

> "ARCHITECT'S RULING (three tiers, no guessing): (1) where the rights issue price S is
> recoverable from held data — subject price/premium plus face value AT the ex-date
> reconstructed from our own parsed split/FV history — compute k per CONTEXT §4.2. (2) Where
> S is unrecoverable: apply the demerger precedent — suppress the bias pair spanning that
> ex-date (no bias update, no trade, 2 days), counted in the report. Never invent a factor.
> (3) A curated overrides file (committed; every entry cites its NSE circular) may supply S
> later; every unresolved rights event on an F&O-universe symbol is listed by the report.
> Execution: chunk 4 prep (CA-engine side) + bias engine consumes the suppression list."

**RESOLVED — executed by the chunk-4 prep session (2026-07-25).** Every tier is code with a
test behind it, in `src/acumen/corp_actions.py`:

- **Tier 1 — recoverable S.** `recover_rights_price(event, *, face_history, overrides)`
  resolves S in a fixed precedence: (a) an explicit issue price in the subject; (b) a curated
  override (tier 3); (c) `S = face value + premium`, where the face value AT the ex-date is
  reconstructed from the symbol's parsed FACE-VALUE-SPLIT history by
  `reconstruct_face_value_paise(ex_date, splits)` — the value BEFORE the earliest split after
  the ex-date, or AFTER the latest split on/before it, or (no split touches the symbol) the
  row's `faceVal`, which is only trustworthy precisely when no split has moved it. The stale
  as-of-query `faceVal` is NEVER used when a split contradicts it (the GREENPLY trap this item
  documents). With S and the cum-close P in hand, `factor_for` computes k per CONTEXT §4.2.
- **Tier 2 — unrecoverable S -> SUPPRESSION.** When S cannot be recovered (no price, no
  premium+face, no override — JMCPROJECT `Rights 2:7` is the live case), `build_factor_table`
  emits a `Suppression(kind="rights")` instead of a factor, exactly as it does for a demerger.
  `suppression_dates()` unions the demerger and unrecoverable-rights ex-dates; the bias engine
  suppresses the bias pair and trading across each (CONTEXT 3.2's demerger precedent: for a
  day D where `D-1 == E` or `D-2 == E`, no bias update and no trade).
- **Tier 3 — curated overrides.** `src/acumen/rights_overrides.json` is committed and EMPTY
  by design; its `_note` states that every entry must carry an `nse_circular` citation and an
  issue price in integer paise. `load_rights_overrides()` reads it; an entry with no citation
  raises. The report (`acumen.ca_report`) lists every UNRESOLVED rights event on an
  F&O-universe symbol — the operator's work-list for transcribing a circular into an override.

Frozen-window redistribution (the 7 rights): 1 suppression (JMCPROJECT, no price), 6 with a
recoverable S once the cum close is supplied; **zero** are on an F&O-universe symbol, so the
unresolved-F&O-rights list is empty in these windows. Full detail in the CHUNK 4 REPORT and in
`test_ca_goldens.py` / `test_corp_actions.py`.

---

## Q-7 · chunk 3 · class A · **RESOLVED — executed chunk 4 prep (2026-07-25)** · was BLOCKING automatic special-dividend classification

**Question.** CONTEXT §4.2 tests the 2% dividend threshold against the **pre-announcement
close**. Which date is "the announcement", and where does it come from?

**Why it is a hole.** CONTEXT §4.2 is explicit and deliberate about the two reference prices:

> NOTE: the 2% threshold is tested against the PRE-ANNOUNCEMENT close, but the factor k uses
> the CUM-date close — two different reference prices, intentionally, per NSE's own rule

The corporate-actions endpoint carries `exDate`, `recDate`, `bcStartDate`/`bcEndDate` and
`ndStartDate`/`ndEndDate` — and a `caBroadcastDate` field that is **null on every row of all
three frozen windows (438 rows, 2016 / 2023 / 2024)**. So the announcement date is not in the
data this project holds, and neither BSE's CSV nor Yahoo carries it.

**Why it matters.** The threshold decides between `k = 1` and `k = 1 − D/P_cum`. Getting it
wrong in the ordinary direction leaves a real gap unadjusted; in the special direction it
invents one. It is the only row of CONTEXT §4.2's table whose classification is not
determined by the subject string alone.

**What this session did meanwhile.** Did NOT guess. `factor_for` requires
`pre_announcement_close_paise` for every dividend and raises, naming this item, when it is
absent — a dividend never quietly becomes `k = 1`, which is what "no adjustment" looks like
from the outside. Both branches of the rule are tested with supplied prices, including the
boundary (exactly 2% is SPECIAL, per the spec's `<` / `≥` wording).

**Options for the architect:**
(a) rule a proxy for the announcement date (e.g. `bcStartDate`, or ex-date minus N trading
days) and record N in CONTEXT §4.2;
(b) rule that the threshold is tested against the **cum-date** close as well, collapsing the
two reference prices into one — simpler, at the cost of the deliberate NSE distinction;
(c) source announcement dates from NSE's separate corporate-announcements feed (a different
endpoint, not yet researched, and a second daily pull);
(d) rule a fixed rupee/percentage cut in the spec that needs no announcement date at all.

Ordinary dividends are the overwhelming majority (240 of 343 rows in the July-2023 window
alone), so whatever is ruled here runs on almost every symbol in the backtest.

**ARCHITECT'S RULING (relayed to the chunk-4 prep session, 2026-07-25), verbatim:**

> "ARCHITECT'S RULING: operational special-dividend test is D / P_cum >= 2% — a documented,
> disclosed deviation from NSE's pre-announcement-close letter (that price exists in no held
> source; P_cum is the factor formula's own reference; boundary misclassification costs <=
> ~2% on one day, below the strategy's noise floor). Dividends < 1% of P_cum are ordinary
> with no further checks. Every dividend classified special lands on a verification list (vs
> NSE F&O adjustment circulars). CONTEXT gains this at next version bump. Execution: chunk 4
> prep."

**RESOLVED — executed by the chunk-4 prep session (2026-07-25).** `factor_for` now classifies
a dividend against the CUM-date close P_cum ONLY — the pre-announcement close is gone from the
path, because it exists in no source this project holds (this item's own evidence: `caBroadcastDate`
is null on all 438 frozen rows). Three bands, in `src/acumen/corp_actions.py`:

- **D / P_cum < 1%** -> ordinary, `k = 1`, no further checks (the fast path).
- **1% <= D / P_cum < 2%** -> ordinary, `k = 1`, but tagged `near-threshold` so the operator
  can see the classifications the ~2% boundary uncertainty could touch (the ruling's
  "boundary misclassification costs <= ~2% on one day").
- **D / P_cum >= 2%** -> SPECIAL, `k = 1 - D/P_cum` (CONTEXT §4.2's formula, unchanged), and
  the event lands on the **verification list** (`special_dividend_verifications()`) to be
  checked against NSE's F&O adjustment circulars.

The 2% threshold is inclusive at the boundary (`>=`), matching CONTEXT §4.2's `<` / `>=`
wording. This is a documented, disclosed deviation from CONTEXT §4.2's PRE-ANNOUNCEMENT-close
reference; CONTEXT gains it at its next version bump (the architect owns that edit — this
session records the ruling here and executes it, and does not touch CONTEXT.md). The 289
frozen-window dividends redistribute (once P_cum is supplied from the daily store) into
ordinary / near-threshold / special / still-pending — full counts in the CHUNK 4 REPORT.

---

## OPEN-8 evidence · chunk 4 prep · recorded 2026-07-25 (CONTEXT §9 registry item; architect owns the CONTEXT edit)

OPEN-8 ("SmartAPI 1-min historical: raw or pre-adjusted?") lives in CONTEXT §9, which this
session may not edit. Recording the evidence here at the architect's direction (chunk-4 prep
addendum, the 2020-07-13 SmartAPI cross-check), verbatim:

> "EVIDENCE (2026-07-25): SmartAPI ONE_DAY candles are CA-back-adjusted — proven by RELIANCE
> 2020-07-13 raw 1935 vs SmartAPI 878.36, ratio consistent with the 2024 bonus x 2023
> demerger. NOTE: this answers dailies only; the 1-min adjustment status is a separate
> question — chunk 5A gate-3 still runs in full."

Supporting detail from this session: the raw:adjusted ratio is 878.36 / 1935 = **0.4539**,
which matches a 1:1 bonus (k = 0.5, ex 2024-10-28 — in our own factor data) times the
RELIANCE -> Jio Financial Services demerger (ex 2023-07-20 — in our own demerger table),
≈ 0.5 x 0.908. TCS, which had NO intervening corporate action, matched SmartAPI ONE_DAY to
the paisa (raw close 2220.00 = SmartAPI 2220.00), which is why it was the adjustment-free leg
of the cross-check. The quirk-corrected 2020-07-13 bhavcopy was verified genuine three ways
(TCS = SmartAPI exactly; both symbols' closes continuous with the raw store neighbours
2020-07-10 / 2020-07-14; the file's own PREVCLOSE column chains to 2020-07-10) and ingested.

---

## ROUND-3 RECEIPTS (25-Jul-2026) · recorded by the chunk-5A prep session

The trader's Round-3 answers (relayed by Paul) landed while chunk 5A was being built. Each is
recorded here VERBATIM as a receipt, with what it resolves and what it newly blocks. CONTEXT.md
edits and its §9/§10 version bumps are the ARCHITECT's; this session records the receipts and
executes the code/config changes each authorises (the same discipline used for Q-4..Q-7).

### R3-a · Q29 received -> OPEN-1 RESOLVED (risk per trade = 1000)

> "Q29 (Round 3): risk per trade = 1,000 rupees."

OPEN-1 ("the trader's INR risk-per-trade amount", CONTEXT §9) is **RESOLVED**. Executed this
session: `config.yaml` now carries `risk_per_trade: 1000` with the comment
"trader answer, Round 3, 25-Jul-2026". The simulation block in the config loader
(`Config.require_risk_per_trade`) lifts by the value simply existing: it now returns 1000
instead of raising `ConfigError`. The loader test suite was updated to match --
`test_repo_config_resolves_risk_per_trade_to_the_trader_amount` asserts the repo config returns
1000, and a NEW test (`test_a_null_risk_per_trade_still_blocks`) proves a `null` value still
raises the OPEN-1 `ConfigError`, so the guard that protected real money while OPEN-1 was open
is kept as a regression, not deleted. Chunk 8 (simulator) is no longer OPEN-1-blocked; it still
depends on chunk 7 (plan.md §3). CONTEXT §9 registry + §10 version bump are the architect's.

### R3-b · Q32 received -> FRVP settings CONFIRMED (Row Size = 24)

> "Q32 (Round 3, screenshot): Rows Layout = 'Number of Rows'; Row Size = 24; Volume shows
> Up/Down split on the chart."

The trader's Fixed Range Volume Profile screenshot **confirms** the provisional setting: Rows
Layout is "Number of Rows" and Row Size = 24 -- the value CONTEXT §3.3 and `config.yaml` already
carry. Executed this session: the `config.yaml` `row_size` comment now reads "confirmed by
trader screenshot, Round 3, 25-Jul-2026" (value unchanged at 24). The screenshot's "Volume
Up/Down" is a **display-only** chart option (it colours each row's up- vs down-volume); the POC
math uses each bar's TOTAL volume, which CONTEXT §3.3 already specifies -- so §3.3 is UNCHANGED
and no F-fixture moves. OPEN-2's remaining half (reproducing 3 chart POCs against his readings)
stays chunk 6's TRADER GATE. CONTEXT §9 OPEN-2 narrowing is the architect's.

### R3-c · Q-8 (class A) — **RESOLVED by Round-3 Q42 (29-Jul-2026)** — POC window length: 8-candle vs 9-candle

> **CLOSED.** The trader confirmed the 8-candle window; see ROUND-3 FINAL RECEIPTS (29-Jul-2026),
> receipt R3F-e, at the end of this file. The interim below WAS the spec and needed no change.

**Question.** The trader's Round-3 FRVP screenshot shows Coordinates #1 = 150 and #2 = 158.
Read as an inclusive bar count that is a **9-candle** box (158 - 150 + 1 = 9), which conflicts
with the spec's **8-candle** 15-min window -- CONTEXT §3.3 / R1-Q11: candles time-stamped
09:15 through 11:14 inclusive = the eight 15-min bars closing 09:30, 09:45, ... 11:15 (the
09:15-stamp bar through the 11:00-stamp bar).

**Why it matters.** A ninth 15-min bar (the 11:15-stamp bar, covering 11:15-11:30) would extend
the profile window past 11:15 and change the POC on some days -- and the POC is load-bearing for
every trade's reference and trigger (CONTEXT §3.4). A one-bar window error silently moves the
POC and therefore the trade.

**Blocks.** Chunk-6 **gate closure** (the POC calibration must be reproduced against the
trader's chart), NOT chunk-6 build (the spec's 8-candle window is unambiguous to build against).

**Asked as Round-3 Q42.** INTERIM (unchanged from spec): the spec's **8-candle window** (09:15
stamps through the 11:00 stamp; the 15-min bar closing at 11:15 is the last one IN) stands and
chunk 6 builds it. So the gate has evidence either way, **chunk 6 must compute BOTH windows on
the calibration days** (8-candle and 9-candle POC) and print them side by side, so whichever the
trader confirms can be checked without a re-run. No code in chunk 5A depends on this (5A ingests
and aggregates minutes; it does not slice the POC window).

### R3-d · Q-9 (class A) — **RESOLVED by Round-3 Q41-A (29-Jul-2026)** — reference == POC, the ABOVE branch

> **CLOSED.** The first distinct close SETS the side only and is never itself the entry; the
> conservative "log + no-trade" interim below is superseded. See ROUND-3 FINAL RECEIPTS
> (29-Jul-2026), receipt R3F-d. OPEN-3 is closed with it.

**Question.** The trader's Q34(b) answer arrived: "if the 11:15 reference equals the POC, there
is NO side yet -- wait; the very first candle that closes distinctly above or below the POC
decides." This resolves the *direction* selection but leaves one sub-case open on a BULLISH day.

- **Below-branch (unambiguous, will be built in chunk 7):** on a bullish day, reference == POC
  -> wait; the first 15-min candle that closes **distinctly below** POC -> ARMED (this is exactly
  CONTEXT §3.4's WAIT-then-arm shape, now with the == POC start resolved). Implement in chunk 7.
- **Above-branch (still open):** on a bullish day, does that first distinct close **above** POC
  ENTER the trade directly, or only SET the side (bullish) and then require the normal ARMED
  trigger? CONTEXT §3.4 does not say, because the == POC start was previously OPEN-3.

**Why it matters.** "Enter directly" vs "set side then wait for the trigger" is the difference
between a fill and no fill on exactly the days the reference sits on the POC.

**Blocks.** ONE branch of chunk 7 (the signal engine's == POC start on the above side). Does NOT
block chunk-7 build of the mainline (reference clearly above/below POC).

**Asked as Round-3 Q41.** INTERIM for the above-branch: **log + no-trade + count occurrences**
(the same conservative posture OPEN-3 used for == POC). The below-branch is built as stated.
This SUPERSEDES the interim for OPEN-3's == POC case on the below side (now answered), but OPEN-3
stays open for the above side until Q41 returns; CONTEXT §9 OPEN-3 update is the architect's.

### R3-e · OPEN-4 record extended (Q31-WHY received; green/doji still assumed)

> "Q31-WHY (Round 3): on the outside-bar tie, when the deciding 1-minute candle closes red near
> its bottom, the low was swept last, so the real break was the high -> BULLISH."

The trader's REASONING for his Q31 red-tie answer now matches the implemented predicate exactly:
the tie 1-minute candle's `close < open` (red) means the low was swept later, so the high broke
first -> BULLISH if `C.close >= bodyMin` (CONTEXT §3.2 Rule 3, tie case; chunk-4 `bias.py`). The
two SYMMETRY-filled cases remain **assumptions** pending trader confirmation and were formally
asked as Round-3 questions:

- **Q38 (green mirror):** tie 1-minute candle closes green (`close > open`) -> BEARISH (mirror).
- **Q39 (doji):** tie 1-minute candle closes exactly at open (`close == open`) -> no new decision,
  carry the previous bias, log the day.

Both are already coded as CONTEXT §3.2 states (chunk 4, decision B59) and surfaced by the `open4`
flag in the evidence pack. Assumptions UNCHANGED pending Q38/Q39; OPEN-4 stays open and is
confirmed at the chunk-4 TRADER GATE. This receipt only records that the red-case WHY is now
explicitly the trader's own words, closing the gap between "we inferred his rule" and "he stated
his rule" for the red case.

---

## OPEN-8 RESOLVED -> **ADJUSTED** (STOP) · chunk 5A gate 3 · 25-Jul-2026 (CONTEXT §9 registry item; architect owns the CONTEXT edit)

OPEN-8 ("SmartAPI 1-min historical: raw or pre-adjusted?", CONTEXT §9; interim "treated as
RAW") is **RESOLVED by the chunk-5A gate-3 live run: the SmartAPI 1-minute historical feed is
CORPORATE-ACTION BACK-ADJUSTED, not raw.** The interim RAW assumption is WRONG. Recording the
evidence + verdict here at the architect's direction (CONTEXT ownership stays with the
architect); this triggers the STOP the chunk-5A card names ("if verdict is ADJUSTED -> STOP after
recording; architect must amend §7-E11 before chunk 6 consumes minute data").

**Evidence (live, 25-Jul-2026), honoring the GATE LESSON (raw-to-raw, no intervening CA):**

1. **TCS whole-history cross-check.** For every TCS symbol-day BEFORE its 2018 1:1 bonus, the
   SmartAPI 1-minute prices are EXACTLY half the raw daily-store prices and the 1-minute volume
   is EXACTLY double -- the signature of a feed back-adjusted for that bonus. Measured on the
   SAME day (no CA between a day and itself, a clean raw-to-raw comparison):
   - 2016-10-03: 1-min close 120585 paise vs raw daily close 241170 -> ratio **0.5000**;
     1-min volume 1,818,222 vs raw daily 909,440 -> ratio **1.9993**.
   - 2016-10-04: price ratio **0.5000**, volume ratio **1.9991**.
   - 2016-12-01: price ratio **0.5000**, volume ratio **1.9998**.
   The gate-1 volume-reconciliation pass rate by year makes it unmistakable: **0% (2016), 0%
   (2017), ~56% (2018 -- the bonus ex-date splits the year), ~98-99% every year from 2019 on**
   (2019+ is post-bonus, so adjusted == raw and gate-1 passes). A raw feed would pass every year.

2. **RELIANCE gate-3 probe (the decisive, self-contained event).** RELIANCE 1:1 bonus ex
   2024-10-28. Pre-ex day 2024-10-25: SmartAPI 1-min-derived daily OHLC vs the RAW daily store:
   - 1-min OHLC (paise): O 134348 / H 134435 / L 132200 / C 132815.
   - raw daily OHLC (paise): O 268700 / H 268870 / L 264400 / C 265570.
   - ratios (1-min / raw daily): high **0.5000**, low **0.5000**, close **0.50011** -- i.e.
     raw x k, with k = 0.5024 read from the raw store's own price gap across the ex-date.
   VERDICT for RELIANCE = **ADJUSTED**.

3. **KOTHARIPRO (bonus ex 2016-01-05) and GREENPLY (FV split ex 2016-01-06): INDETERMINATE** --
   their ex-dates predate the 2016-10 one-minute floor (RESULTS.md B), so there is no pre-ex
   1-minute data to compare. Attempted honestly and recorded indeterminate; they neither confirm
   nor contradict. The one decisive event (RELIANCE) plus the TCS whole-history cross-check are
   consistent: **COMBINED OPEN-8 VERDICT = ADJUSTED.**

This confirms and extends the chunk-4 dailies finding (SmartAPI ONE_DAY is CA-back-adjusted):
the ONE_MINUTE feed is adjusted TOO. Full numeric evidence + the per-year gate-1 table are in
`docs/gate_chunk5A_open8_evidence.md`.

## Q-10 · chunk 5A · class A · **RESOLVED — executed chunk 5A-fix (2026-07-25)** · was BLOCKING chunk 6 (POC) build

**Question.** OPEN-8 resolved ADJUSTED, which CONTRADICTS CONTEXT §7-E11: "intraday engines
(POC, signals, simulator) run on **RAW same-day 1-min prices** (tick grid preserved; PnL in that
day's real rupees)." The SmartAPI feed does NOT provide raw same-day prices for any day BEFORE a
later corporate action -- it provides those prices back-adjusted by every CA after them. How
should the intraday layer obtain the raw same-day prices E11 requires?

**Why it matters.** For a RECENT day (after the symbol's last CA) adjusted == raw, so the F10
calibration days (all 2026) and any recent backtest window are unaffected -- which is why F10
still passes and the pipeline works. But for an OLD day before an intervening CA, the stored
1-minute prices are NOT the rupees that traded that day and the tick grid is NOT preserved (0.5 x
a tick-aligned price can be half-tick). This reaches the POC row grid (`round((top-bottom)/tick)`
uses the tick), every signal price comparison, and the per-trade PnL. Silently trading on
half-scaled old prices would be a large, invisible error -- exactly what E11 exists to prevent.

**What chunk 5A did meanwhile (STOP, no silent decision).** The backfill, store, gates,
aggregator and minute loader are all BUILT and correct as infrastructure; the store holds the
feed AS FETCHED (adjusted), and gate-1 already FLAGS the affected old symbol-days (they fail
volume reconciliation, so they are excluded and counted, never silently traded -- CONTEXT §7-E3).
No un-adjustment was applied and no E11 change was made: both are the architect's call.

**Options for the architect (not decided here):**
(a) **Un-adjust on ingest** to recover raw same-day prices, using the CHUNK-3 CA factor table:
raw_same_day = adjusted / (product of factors of CAs with ex-date AFTER that day). The CA engine
already computes exactly these factors (`factors_between` / `adjust_pair`); this keeps E11 intact
and is the natural fit, but must handle demerger/suppression windows (no factor) and volume
(divide by the same k) and re-verify the tick grid lands back on-grid.
(b) **Amend E11** to run the intraday engines on ADJUSTED prices -- simplest, but abandons
"PnL in that day's real rupees" and "tick grid preserved", and needs the trader's awareness
since it changes what the numbers mean on old days.
(c) **Restrict the intraday backtest window** to each symbol's post-last-CA span (where adjusted
== raw), disclosed as a survivorship-style limitation.
(d) **Switch source** for raw 1-minute (CONTEXT §4.3 names Zerodha Kite as the fallback), if it
serves raw historical minutes.

Chunk 6 (POC) is the first consumer of minute data and is **BLOCKED** until this is answered;
chunk 5A/5B (ingestion + gates) are not blocked -- they store and flag the feed as it is.

**ARCHITECT'S RULING (relayed to the chunk-5A-fix session, 2026-07-25), verbatim:**

> "ARCHITECT'S RULING (option a, with surgical fallback): SmartAPI 1-min candles are
> UN-ADJUSTED ON INGEST back to RAW using the chunk-3 factor table: for a candle on day
> D fetched on date F, k_cum = product of factors of events with ex-date in (D, F];
> raw_price = fetched_price / k_cum ; raw_volume = fetched_volume × k_cum. The minute
> store holds RAW ONLY — CONTEXT §7-E11 stands unchanged. Gate-1 (volume reconciliation
> vs raw bhavcopy) is hereby the per-day PROOF of factor correctness. Symbol-day spans
> where un-adjustment is unprovable (unknown factor, e.g. pre-demerger spans if the
> vendor demerger-adjusts, or Q-6-pending rights) and gate-1 fails → excluded + counted,
> and if a whole pre-event span fails systematically, that symbol's minute clamp moves
> to post-event (surgical restriction, disclosed). Source switch (Kite) stays in reserve
> only if raw-restoration fails broadly. Ingest ledger must record the FETCH DATE per
> window (k_cum is fetch-dated); future top-ups un-adjust with a refreshed CA table."

**RESOLVED — executed by the chunk-5A-fix session (2026-07-25).** Every clause is code with a
test behind it. The un-adjustment is the exact inverse of the chunk-3 pairwise adjustment: the
ruling's `k_cum = product of factors with ex-date in (D, F]` is precisely
`corp_actions.factors_between(factors, D, F)` (the same half-open `(previous, current]` window
the bias engine adjusts *with*), so no new factor logic exists -- the same chunk-3 table the
bias engine multiplies by is the one this un-adjusts against.

- **The un-adjustment core** (`src/acumen/minute_unadjust.py`, PURE): `raw_price =
  round_half_even(fetched / k_cum)` and `raw_volume = round_half_even(fetched × k_cum)` --
  Decimal throughout, one half-even rounding at the end (CONTEXT §7-E11). `k_cum == 1` (a recent
  day whose factor window is empty) is the EXACT identity: fetched is stored unchanged, so F10's
  2026 days and every post-last-CA backtest window are untouched.
- **Tick-snap** (the ruling implicit in "tick grid preserved", E11): an un-adjusted price within
  2 paise of the nearest tick is snapped onto it; one further off is left as the divided value
  and the day is FLAGGED and counted (vendor rounding beyond tolerance). Snap runs only when
  un-adjustment actually happened (`k_cum != 1`), never re-gridding an identity day against a
  possibly-coarser current tick.
- **Volume direction** exactly as ruled (`× k_cum`): a 1:1 bonus doubled a pre-ex volume, so
  recovering the raw share count multiplies BACK by k_cum (RELIANCE pre-ex volume ÷ 2 = raw).
- **Un-provable spans**: where an event in `(D, F]` has NO factor -- a demerger (Suppression) or
  a Q-6-pending rights -- day D is marked un-provable; the partial un-adjustment is still stored
  so the day is visible, but gate 1 (the ruling's per-day PROOF) fails it, so it is excluded and
  counted (CONTEXT §7-E3). A systematically-failing leading span moves the symbol's minute clamp
  to post-event (`systematic_unprovable_floor`, the ruling's surgical fallback, disclosed).
- **The ingest ledger records the FETCH DATE per window** (new `fetch_date` column on the window
  ledger; `MinuteStore`/`WindowOutcome`): k_cum is fetch-dated, so a future top-up un-adjusts the
  extended tail with a refreshed CA table keyed on its own fetch date.
- **The store holds RAW ONLY**: un-adjustment runs in the ingest path
  (`minute_backfill._fetch_and_store_window` -> `unadjust_bars`) before `write_bars`, and a
  one-time `rebuild_symbol_raw` migration un-adjusts a store fetched before this ruling. CONTEXT
  §7-E11 is unchanged (the store now satisfies its "RAW same-day prices" requirement). Kite stays
  in reserve (untouched).

Acceptance evidence + the before/after gate-1-by-year table are in
`docs/gate_chunk5A_open8_evidence.md`. OPEN-8 stays **RESOLVED = ADJUSTED** (that was the finding
about the feed); Q-10 is the remedy for the E11 contradiction the finding created, now executed.
Chunk 6 (POC) is UNBLOCKED: the minute store, once rebuilt/re-pulled through the un-adjusting
ingest path, holds the RAW same-day prices E11 requires.

### Q-10 ADDENDUM (chunk 5A FIX-2, 2026-07-25) -- volume factor split + RELIANCE demerger probe

Two refinements from the architect's reading of the FIX report, executed this session.

**(1) VOLUME FACTOR REFINEMENT -- ARCHITECT'S RULING, verbatim:**

> "Volume un-adjustment uses k_shares -- the product of SHARE-COUNT event factors only (bonus,
> split, consolidation) -- because vendors scale volume for share-count changes but not for cash-
> dividend price adjustments. Price continues to use k_price = all factors. price_raw = fetched /
> k_price ; volume_raw = fetched x k_shares."

**EXECUTED.** `k_price` = product of ALL factors in `(D, F]` (bonus/split/rights/special-dividend)
-> divides the price, unchanged from the original Q-10 code. `k_shares` = product of SHARE-COUNT
factors only -> multiplies the volume. A consolidation is a reverse split, which the CA parser
already classifies as `KIND_SPLIT`, so the share-count set is exactly
`corp_actions.SHARE_COUNT_KINDS = {bonus, split}` (= bonus, split, consolidation). A special
dividend is in `k_price` but NOT in `k_shares`, so it no longer spuriously over-corrects volume
(the exact hazard the FIX report flagged). Tests: a synthetic window with a special dividend + a
bonus reconciles volume by the bonus only (raw 1000, not the wrong 900) while the price divides by
both (`test_unadjust_bars_special_dividend_plus_bonus_volume_by_bonus_only`); the TCS identity and
the F10 identity are UNCHANGED (TCS's only factor is a bonus, so `k_price == k_shares` for it, and
every F10 day is post-CA identity). Full suite 883/0 offline. **Note flagged, not decided:** a
RIGHTS issue is genuinely a share-count change but the ruling's verbatim enumeration is "bonus,
split, consolidation" and a rights factor is a TERP-based blend rather than a clean share ratio,
so rights is executed OUT of `k_shares` as written -- recorded for the architect (decision B81).

**(2) 4b RELIANCE PROBE -- EXECUTED LIVE (credentialed SmartAPI, polite pacing, 2026-07-25).**
Credentials read from `.env`, never printed (CLAUDE.md rule 4). RELIANCE factor table (our own,
built live from NSE CA history + the raw daily store): 2017-09-07 bonus k=0.5, 2020-05-13 rights
k=0.99061, 2024-10-28 bonus k=0.5; suppression 2023-07-20 Jio demerger; no pending rights.

- **2a -- 2024-10 window (bonus-only, provable).** Pre-ex 2024-10-25: SmartAPI 1-min as-fetched
  H/L = 134435/132200 = raw daily 268870/264400 x 0.5 (ratio 0.50000, the vendor's bonus
  adjustment). Un-adjusted (/ k_price = 0.5) -> **268870 / 264400, EXACTLY the raw daily H/L (|dH|
  = |dL| = 0 paise, within the 2-paise tolerance)**; un-adjusted close 265630 vs raw 265570 (60
  paise = 0.02%, the intraday-VWAP-vs-official-close noise). Gate-1 volume via **k_shares**: 1-min
  sum 9,247,981 vs raw daily 9,298,748 -> gap **0.546%**, within [-0.1%, +5.0%], **PASS**.

- **2b -- 2016 window (the demerger probe).** Un-adjusting six 2016 days by our table (k_price =
  0.5 x 0.5 x 0.99061 = 0.24765 -- both bonuses + the rights) vs the RAW daily store:
  median **R_fetched (vendor total adj / raw) = 0.24683**, median **R_unadj (our-un-adjusted /
  raw) = 0.99666**. A demerger-adjusted minute feed would give R_unadj ~ 0.908 (the Jio residual);
  0.99666 is ~1.000. **VERDICT: the SmartAPI 1-MINUTE feed is NOT demerger-adjusted -> full
  RELIANCE minute history is PROVABLE by our bonus/rights table; the surgical clamp fallback is
  NOT triggered.** **Important corollary:** this DIFFERS from the DAILY feed, which chunk 4 proved
  IS demerger-adjusted (RELIANCE daily 2020-07-13 ratio 0.4539 = bonus x demerger). So SmartAPI's
  ONE_MINUTE and ONE_DAY feeds adjust for DIFFERENT event sets -- minutes carry the bonuses (and a
  rights) but not the demerger. Minor caveat: a ~0.33% price residual remains on pre-2020-rights
  days (the vendor's rights-equivalent ~0.9873 vs our TERP 0.99061, or a cum-close difference) --
  two orders of magnitude below the ~9% demerger signal, within gate-1's volume band, off the tick
  grid (tick-flagged, not excluded).

- **2c -- identity-skip rebuild guard.** Confirmed on real data: a post-bonus day (2024-11-04,
  k_price = k_shares = 1) is stored byte-for-byte and SKIPPED by `rebuild_symbol_raw`
  (identity_days = 1, byte-for-byte unchanged); a pre-bonus day (2024-10-25, k_price = 0.5) is
  rewritten (days_rewritten = 1). No unnecessary rewrites.

**FOLLOW-UP for the ARCHITECT (before chunk 5B backfills RELIANCE) -- flagged, not decided.** The
Q-10 ruling conditioned the un-provable/clamp fallback on "pre-demerger spans **if the vendor
demerger-adjusts**". 2b settles that condition: for the 1-minute feed the vendor does **NOT**
demerger-adjust, so a pre-demerger RELIANCE minute day is actually PROVABLE. But the code as built
treats the demerger *suppression* as an unknown-factor event in `(D, F]` and marks such days
UN-PROVABLE (gate-1 excludes them; a systematic leading span moves the clamp to post-2023) -- which
would now FALSELY drop ~7 years (2016-2023) of provable RELIANCE minutes. This session did NOT
change that logic (it is a Class-A policy question the architect ruled on conditionally, and out of
FIX-2's two-item scope). The architect should rule how the minute layer treats a demerger given the
settled "minutes are not demerger-adjusted" finding -- likely: a demerger no longer marks a MINUTE
day un-provable, while the demerger's bias-pair suppression in the daily/bias engine (CONTEXT 3.2)
is a separate concern and stays. Chunk 5B is the first consumer that hits this.

### Q-10 ADDENDUM 2 (chunk 5A FIX-3, 2026-07-25) -- demerger scope for MINUTES resolved

The follow-up FIX-2 flagged (immediately above) is now ruled on and executed this session.

**ARCHITECT'S RULING (demerger scope for MINUTES), verbatim:**

> "ARCHITECT'S RULING (demerger scope for MINUTES): FIX-2's live probe proved the
> vendor's 1-MINUTE feed is NOT demerger-adjusted (median ratio ~1.000 vs ~0.908
> expected if adjusted), unlike its ONE_DAY feed. Therefore demerger events are
> EXCLUDED from the minute un-adjustment chains (k_price and k_shares) and must NOT
> mark minute spans un-provable. Un-adjustment across a demerger uses the other events
> only; gate-1 remains the per-day proof. The bias engine's demerger pair-suppression
> (CONTEXT 3.2, daily layer) is a SEPARATE rule and stays exactly as is."

**EXECUTED by the chunk-5A FIX-3 session (2026-07-25).** A demerger is a
`Suppression(kind=KIND_DEMERGER)` and was NEVER a `Factor`, so it never entered `k_price` or
`k_shares` numerically -- the "excluded from both k chains" clause was already true by
construction (a demerger has no CONTEXT 4.2 factor; `factor_for` raises for it and
`build_factor_table` emits a suppression, not a factor). The one behaviour that changed is the
un-provability marking: a new PURE helper `minute_unadjust.unprovable_suppression_dates()`
returns only the ex-dates of suppressions whose `kind != KIND_DEMERGER` (i.e. Q-6 tier-2
unrecoverable rights), so a demerger ex-date in `(D, F]` no longer marks a minute day
un-provable. `unadjust_bars` and `minute_backfill.rebuild_symbol_raw` both route their
suppression dates through this one helper. Tier-2 rights and Q-6-pending rights STILL mark a
minute day un-provable (the 1-minute feed IS rights-adjusted -- FIX-2 2b -- but we cannot
compute the factor there), so the fix does not over-reach. Pre-demerger spans of a demerger
symbol therefore become provable-by-gate-1 like any other span, un-adjusted by the symbol's
other events (bonus/split/rights) only. The bias engine's demerger pair-suppression path
(`bias_engine._bias_for`, consuming `suppression_dates()` which unions demergers + tier-2
rights) is UNTOUCHED and still suppresses the bias pair and trading across a demerger ex-date
(CONTEXT 3.2). A single test pins both halves of the separation (a demerger + bonus symbol:
its pre-demerger MINUTE day is provable and un-adjusted by the bonus only, while its daily
BIAS pair spanning the ex-date is still suppressed).

**IMPORTANT -- the live RELIANCE re-run this session CONTRADICTED the ruling's factual premise; a
new STOP (Q-11 below) is raised.** The code change is done and gate-1-safe, but the empirical basis
for "the 1-minute feed is NOT demerger-adjusted" (FIX-2's 2016-only probe) does NOT generalise. A
credentialed live pull of RECENT pre-demerger windows shows the 1-minute feed IS demerger-adjusted for
that era: un-adjusted price ratio ~0.908 (= the Jio demerger factor) with gate-1 volume -10.1% on
2022-07 AND 2023-06, while a window just AFTER the ex-date (2023-09) un-adjusts to EXACTLY 1.00000
(gate-1 +0.00%), and the 2016 window stays ~0.997 (not demerger-adjusted). So the vendor's demerger
adjustment is INCONSISTENT across its own history. gate-1 excludes the affected days (the ruling's
safety net holds -- nothing is silently traded), and no RELIANCE minute data is actually rescued by
the demerger-exclusion (every day it makes "provable" fails gate-1 anyway -- the demerger residual on
2020-2023, the rights residual on 2016-2019). Full numbers in the CHUNK 5A FIX-3 REPORT, the evidence
pack (FIX-3 section), and **Q-11**.

---

## Q-11 · chunk 5A FIX-3 · class A · **OPEN -- STOP** · BLOCKS RELIANCE minute treatment (chunk 5B)

**Question.** The Q-10 ADDENDUM 2 ruling excluded demergers from the minute un-adjustment on the
premise that "the vendor's 1-MINUTE feed is NOT demerger-adjusted" (FIX-2's live probe, measured only
on a 2016 window). The FIX-3 live re-run proves that premise does NOT hold across the vendor's history:
the 1-minute feed IS demerger-adjusted for 2020-2023 pre-demerger data but NOT for 2016 data. How
should the minute layer un-adjust a symbol whose vendor demerger adjustment is applied INCONSISTENTLY
across its own historical range?

**Why it is a hole.** The ruling assumed one uniform vendor behaviour (no demerger in the minutes).
The live evidence (credentialed SmartAPI, 2026-07-25, raw-to-raw vs the RAW daily store) shows two:

| window (RELIANCE) | in (D, F] | our k_price | un-adj/raw price | gate-1 volume | demerger baked in? |
|---|---|---|---|---|---|
| 2016-10 | 2017 bonus, 2020 rights, [demerger], 2024 bonus | 0.24765 | ~0.99666 | FAIL ~ -1.24% (k_shares) / -0.29% (k_price) | **NO** (only rights residual) |
| 2019-07 | 2020 rights, [demerger], 2024 bonus | 0.49530 | ~0.99666 | FAIL ~ -1.24% (k_shares) / -0.29% (k_price) | **NO** (only rights residual) |
| 2022-07 | [demerger], 2024 bonus | 0.50000 | **~0.90787** | **FAIL ~ -10.14%** | **YES** (~0.908 residual) |
| 2023-06 (pre-ex) | [demerger], 2024 bonus | 0.50000 | **~0.90786** | **FAIL ~ -10.14%** | **YES** (~0.908 residual) |
| 2023-09 (post-ex) | 2024 bonus only | 0.50000 | **1.00000** | **PASS +0.00%** | n/a (demerger behind it -- clean) |

The transition is somewhere between 2016 and 2022. A window straddling the 2023-07-20 ex-date settles
it beyond doubt: 2023-06 (just before) carries the 0.908 demerger residual; 2023-09 (just after) is
exact. So the vendor DOES bake the demerger into pre-demerger minute bars for the recent era, and
un-adjusting those by the other events only (as the ruling requires) leaves a ~9% price error.

**Why it matters.** The FIX-3 change is gate-1-SAFE -- every affected RELIANCE day fails gate-1 volume
(the demerger residual moves volume ~10%, or the rights residual ~1.2%) and is excluded + counted
(CONTEXT 7-E3), so no wrong price reaches the backtest. But (1) the ruling's premise is factually
wrong for RELIANCE 2020-2023, (2) the demerger-exclusion rescues NO RELIANCE minute data (its whole
purpose), and (3) the correct un-adjustment for the 2020-2023 span would actually INCLUDE the demerger
factor -- the opposite of the ruling -- while the 2016 span must EXCLUDE it. No single demerger-scope
rule un-adjusts RELIANCE correctly. Secondary finding: even the pre-2020 rights residual (~0.29% via
k_price) is just past gate-1's -0.1% floor, so those days fail too (reinforces decision B81 -- rights
convention -- and raises whether the gate-1 band should widen slightly).

**What this session did meanwhile (STOP, no silent decision).** Executed the ruling exactly as written
(demergers excluded from minute un-provability; the code change + tests are in this commit) because the
architect owns the ruling and it is gate-1-safe. Did NOT change the k chains, the gate band, or the
demerger scope beyond the ruling. Recorded the full live evidence here, in PROGRESS.md, and in the
evidence pack, and raised this STOP. The bias-engine demerger suppression (CONTEXT 3.2) is untouched
and correct regardless.

**Options for the architect (not decided here):**
(a) **Era-aware demerger scope for minutes:** include the demerger factor in k_price/k_shares for days
on/after a per-symbol "vendor-demerger-adjusted floor" (empirically ~post-2016/2017 for RELIANCE),
exclude it before -- requires detecting the floor per symbol (gate-1 by year already reveals it).
(b) **Surgical clamp (the original Q-10 fallback), demerger-aware again:** treat a demerger as
un-provable for the era where the vendor bakes it in, and move the minute clamp to post-demerger --
disclosed survivorship-style restriction (loses the pre-demerger span, which is un-provable anyway).
(c) **Keep FIX-3 as is and rely on gate-1:** accept that demerger-symbol pre-demerger minute days are
excluded by gate-1 (safe, no rescue) and disclose the coverage loss in the chunk-9 report.
(d) **Switch source** (Kite) for demerger symbols' minute history if it serves a consistently-adjusted
or raw feed.

Chunk 5B (full-universe backfill) is the first consumer that hits this on every demerger symbol; it is
**BLOCKED on RELIANCE-like demerger symbols** until this is answered (5B on non-demerger symbols is not
blocked). CONTEXT ownership and any §7-E11/§9 note stay with the architect.

**ARCHITECT'S RULING (relayed to the chunk-5A FIX-4 session, 2026-07-25), verbatim:**

> "ARCHITECT'S RULING: the vendor's historical adjustment stack is era-inconsistent
> (proven: demerger absent in 2016/2019 windows, present in 2022/2023-06, gone at
> 2023-09; rights scaled in volume with a vendor factor ~0.9873 vs our TERP 0.99061).
> Therefore un-adjustment is RECONSTRUCTED per symbol per event by MEASUREMENT, not
> policy: for each CA event, candidate factors are exactly {our factor, the measured
> vendor factor k̂, not-applied}, for price and (independently) for volume. k̂ is
> measured as the median ratio over pre-ex-date probe days between fetched prices and
> the raw daily store (single scalar per event, windows and residuals recorded -- this
> is measurement of an observable, never free fitting). Selection is arbitrated by the
> raw daily oracle: price containment within 2 paise (scaled) AND gate-1 volume band.
> The chosen chain per symbol-era is committed as an auditable adjustment map with
> provenance. No candidate fits -> span un-provable -> excluded + counted (surgical
> clamp). Gate-1 remains the per-day proof; the -0.1% floor is NOT widened."

**RESOLVED -- executed by the chunk-5A FIX-4 session (2026-07-25).** Every clause is code with a
test behind it, in `src/acumen/vendor_adjustment.py` (PURE map builder + un-adjust consumption;
the live measurement + persistence are thin I/O wrappers). The FIX-2/FIX-3 rule-guessing (a single
policy for the vendor's demerger scope) is SUPERSEDED by per-event measurement.

- **The observable.** For a fetched day D (fetch date F), `R(D) = fetched_price(D) / raw_daily(D)`
  is exactly the product of the vendor's actually-applied factors for events with ex-date in
  `(D, F]`. This is directly measured (fold the fetched 1-min day to daily OHLC; ratio its HIGH and
  LOW -- the exact multiples, not the intraday-noisy close -- against the RAW daily store). Volume:
  `Rv(D) = fetched_vol(D) / raw_daily_vol(D)`. Days sharing the same in-window event set form an
  ERA; `k̂` per (event, era) is the median over that era's pre-ex probe days (residuals recorded).
- **The candidate set + arbitration.** Working BACKWARDS from today, one era at a time, each era
  adds exactly one older event. Each in-era event's factor is chosen from
  `{ours, measured k̂, not-applied=1}` for price and (independently) for volume. A no-`ours` event
  (demerger) may FLIP between its measured value and not-applied across eras (the era-inconsistency),
  chosen by the oracle: PRICE containment within 2 paise of the raw daily high/low AND VOLUME within
  gate-1's band `[-0.1%, +5.0%]`. Min-cost prefers `ours` (an exact known factor) > `not-applied`
  (vendor omitted it) > `measured` (the vendor used a factor we had to observe); an event's source is
  decided at its newest appearance and carried older (only a no-`ours` event flips). At most ONE
  freshly-solved unknown per era -> measurement, never free fitting.
- **The map (`AdjustmentMap`).** Per symbol, one entry per (event, era): `{kind, ex_date, era,
  price_factor_used, volume_factor_used, price_source/volume_source: ours|measured|absent, probe
  windows, residuals}`. Persisted under `data/adjustment_maps/<SYMBOL>.json` (gitignored store
  artifact) AND printed into the evidence pack. Deterministic: same fetched inputs -> same map.
- **Consumption.** `unadjust_with_map(bars, map, ...)` replaces the FIX-3 factor-table path: for a
  day D it looks up the map entry whose (event set, era) covers D, forms `k_price`/`k_vol` from the
  chosen per-event factors, and divides/scales (the same `minute_unadjust` Decimal + one-half-even +
  tick-snap primitives). A day whose era is NOT in the map (unprobed) or whose events have no fitting
  candidate is UN-PROVABLE -> excluded + counted (CONTEXT 7-E3); gate-1 stays the per-day proof and
  the -0.1% floor is unchanged.
- **RELIANCE acceptance (live, credentialed, 2026-07-25).** All six windows come out PROVABLE with
  gate-1 PASS and price containment. The map shows: demerger ABSENT for 2016/2019, PRESENT (measured
  ~0.9079) for 2022->2023-07; rights 2020 measured (price ~0.9873 AND vendor-scaled volume ~0.9877,
  both differing from our TERP 0.99061); both bonuses 0.5 (ours == vendor). Full map + per-window
  numbers in `docs/gate_chunk5A_open8_evidence.md` (FIX-4 section) and the CHUNK 5A FIX-4 REPORT.
  **TCS regression:** map resolves to exactly {2018 bonus, ours, 0.5}; the already-raw store's rebuild
  is a no-op (gate-1-already-passes identity guard) and its gate-1-by-year table is unchanged
  (2016-18 ~97-100%). CONTEXT ownership and any §7-E11/§9 note stay with the architect.

### Q-11 ADDENDUM (chunk 5B PREP, 2026-07-26) -- ROUTING: which symbols must go through the map

REVIEW_5A left two LOW findings for chunk 5B, both about CONSUMING the FIX-4 map rather than
building it: **F1** (the map is built, proven and consumable, but no `src/` caller passes a
persisted map -- the operator CLI always took the Q-10 factor-table path) and **F2** (that
fallback has no PRICE oracle, so for a non-share-count event it scales price but not volume and
a ~2%-wrong price passes gate-1 volume unnoticed). F1 is a wiring job; F2 needs a RULE for which
symbols may use the cheap path at all. The architect ruled it.

**ARCHITECT'S RULING (routing), verbatim:**

> "ARCHITECT'S RULING (routing): a symbol whose CA history contains ANY
> non-share-count event (rights, special dividend, demerger) is MAP-REQUIRED -- its
> eras must be probed and its ingest must run through the adjustment map's per-day
> price containment. Bonus/split-only symbols may use the factor-table path (their
> map would be identical: ours/ours). The classifier runs off the chunk-3 CA table;
> unknown-parse events force MAP-REQUIRED conservatively."

**EXECUTED by the chunk-5B prep session (2026-07-26).** Every clause is code with a test behind
it, in `src/acumen/adjustment_route.py` (PURE) and wired into both operator entry points.

- **The classifier** (`classify_route`) runs off the chunk-3 CA table exactly as the ruling
  says -- it takes the built `Factor`s, `Suppression`s, `PendingFactor`s and the parse
  `exceptions` for one symbol and returns `map-required` / `table-path` plus the REASON for
  every event that forced the map (so the report can show why a symbol is on the expensive
  path). MAP-REQUIRED is forced by: a price-moving factor (`k != 1`) whose kind is not in
  `SHARE_COUNT_KINDS` (a rights, a special dividend); any suppression (a demerger, a Q-6
  tier-2 rights); any pending factor; any parse exception on that symbol.
- **"Non-share-count" is read as the ruling's own enumeration** -- rights, special dividend,
  demerger -- i.e. the events that MOVE a price without moving the share count. An ordinary
  dividend and a buyback carry `k = 1` (CONTEXT 4.2), move no price and fragment no era; reading
  them in would make EVERY symbol map-required and contradict the ruling's own "bonus/split-only
  symbols may use the factor-table path". Recorded as decision B93 rather than assumed silently.
- **Scoping to the minute clamp.** An event whose ex-date is older than the symbol's minute
  clamp (`max(2016-10-01, first data)`) can appear in no `(D, F]` window of any bar the ingest
  will ever store, so it cannot affect one stored price and does not force the map (`since=`).
  Recorded as decision B94.
- **The refusal** (`map_covers_route`, the ruling's "its ingest must run through the map"):
  `acumen-minute-backfill` now loads `data/adjustment_maps/<SYMBOL>.json` (or an explicit
  `--adjustment-map`), passes it to `backfill_symbol(adjustment_map=...)` and to a new
  map-backed `--rebuild`, and **refuses with exit code 2** when a MAP-REQUIRED symbol has no
  map -- printing the exact `acumen-build-adjustment-map` command that fixes it. An explicitly
  named map that does not exist RAISES rather than being silently ignored (an operator who
  names a map and is ignored would believe the run was map-backed when it was not). F1 and F2
  are closed by this commit.
- **The universe runner** (`acumen-universe-backfill`, chunk 5B proper) classifies every symbol
  up front, PROBES each map-required symbol's eras and builds+persists its map BEFORE ingesting
  it, and reports the route counts and the map inventory (events measured vs ours vs absent).

**Known limit, flagged not decided.** `vendor_adjustment.events_from_factor_table` builds era
keys from factors with `k != 1` plus suppressions plus pending RIGHTS. A pending DIVIDEND (one
whose cum close the daily store could not supply) makes a symbol map-required but does NOT enter
its era keys, so if the vendor did adjust for it the era's containment simply fails and those
days are un-provable -> excluded + counted. Safe (nothing wrong is stored, gate 1 and containment
both hold) and disclosed here rather than silently patched.

### Q-11 ADDENDUM 2 (chunk 5B FIX-3, 2026-07-26) -- VENDOR APPLICATION FLOORS

**ARCHITECT'S RULING (vendor application floors), verbatim:**

> "ARCHITECT'S RULING (vendor application floors): the vendor's back-adjustments have
> per-event APPLICATION FLOORS — internal splice dates before which the event was never
> applied to its archive (proven: CANBK's split fails only <2022-06; VEDL passes only
> after 14 consecutive failing eras; RELIANCE's demerger floor was FIX-4's unpinned
> question). The map model gains one optional measured quantity per event: floor_date
> F_e, binary-searched via daily-oracle probes (day fits with event-in vs event-out;
> ~11 probes per event); for days < F_e the event is ABSENT from that day's chain.
> Floors are hunted ONLY where failure is systematic: every quarantined symbol and
> every settled symbol with gate-1 < 98% (BPCL, IOC, GAIL, TATASTEEL, NMDC, OIL,
> JUBLFOOD, HAL, BSE, DIXON incl. table-path re-routes, MOTHERSON, PETRONET, PFC,
> HDFCBANK...). Deterministic; floor + probe evidence recorded in the map. Un-provable
> remains the honest fallback where no floor fits."

**EXECUTED by the chunk-5B FIX-3 session (2026-07-26).** Every clause is code with a test behind
it, in `src/acumen/vendor_adjustment.py` (the model + the pure binary search + the probe) and
`src/acumen/universe_backfill.py` (the hunt scope and the wiring).

- **The model.** `EventFloor(ex_date, floor_date, resolved, probes, note)` is one optional
  measured quantity per event, carried on `AdjustmentMap.floors` and persisted with the map.
  `AdjustmentMap.factors_for_day` now forms the day's chain PER EVENT from the era's committed
  `EventChoice`s and **drops any event whose floor lies above the day** -- literally the ruling's
  "for days < F_e the event is ABSENT from that day's chain". A map with no floors is
  byte-identical in behaviour to the FIX-2 map (the chain is still the era's `k_price`/`k_volume`).
- **The search is a binary search over the DAYS, not a fit.** `binary_search_floor(days, classify)`
  is PURE: it asks the classifier for the newest day (must be `event-in`, else the floor model does
  not apply and the search is UNRESOLVED), the oldest day (`event-in` -> no splice inside the span),
  and then bisects the OUT/IN boundary. `classify` is the daily oracle: probe day D, form the era's
  chain WITH the event and WITHOUT it, and test each against 2-paise price containment vs the RAW
  daily high/low. Exactly one side containing decides; both or neither is `undecided`, and an
  undecided midpoint steps at most `MAX_UNDECIDED_STEPS` neighbours before the search gives up
  UNRESOLVED rather than guessing. Budget `MAX_FLOOR_PROBES = 16` per event (the ruling's ~11 plus
  slack). PRICE containment alone decides -- it is the exact oracle; the volume observable carries
  the auction shortfall and would only add `undecided` verdicts. The gap is recorded per probe.
- **The hunt scope is the ruling's own.** `FLOOR_HUNT_GATE1_MAX_RATE = 0.98`: a symbol is hunted
  when it is QUARANTINED or its gate-1 rate is below 98%. A TABLE-PATH symbol in that set is
  rerouted through the map path first (the ruling's "incl. table-path re-routes" -- the Q-12
  addendum reroute previously fired only on quarantine), so it has the price oracle a floor search
  needs. Within a symbol, an event is only searched when its pre-ex PROVABLE-era span actually
  carries systematic failure (`FLOOR_HUNT_MIN_FAILURE_RATE`) and its price factor is not already 1
  -- there is no floor to find where nothing fails, and the ruling scopes the hunt to systematic
  failure. Every skip is recorded with its reason.
- **Floors apply to PROVABLE eras only.** An un-provable era has no committed per-event chain to
  drop an event FROM, so it stays un-provable -- the ruling's own closing sentence ("un-provable
  remains the honest fallback where no floor fits"). The search domain is therefore restricted to
  days whose era is provable, which is also what makes the classifier's two hypotheses exact.
- **Deterministic and auditable.** The same probe days produce the same floor; the floor, every
  probe day and its verdict, and the reason for every skip are persisted in the map JSON and
  printed in `docs/backfill_minute_report.md`.

### Q-11 ADDENDUM 3 (chunk 5B FIX-3, 2026-07-26) -- COMPOUND + UNPARSED MAP NODES

**ARCHITECT'S RULING (compound + unknown events), verbatim:**

> "ARCHITECT'S RULING (compound + unknown events): (i) same-ex-date events compose
> into ONE compound map node — k = product, share-count flags combined, candidates
> apply to the compound (unblocks BAJAJFINSV). (ii) An UNPARSED price-suspect event
> needs no parsing to enter the map: it participates with candidates {measured,
> absent} only (no 'ours'), one scalar per event, oracle-arbitrated as ever. Unparsed
> events therefore never block a map; they are measured or absent."

**EXECUTED by the chunk-5B FIX-3 session (2026-07-26).** In
`src/acumen/vendor_adjustment.py::events_from_factor_table`, which now groups every price-moving
event by EX-DATE and composes one node per date.

- **(i) the compound node.** `compose_event` multiplies the components' CONTEXT 4.2 factors into
  the node's `our_price_factor` (`None` if ANY component has none -- a demerger or an unparsed
  component makes the whole product unknown), combines the share-count flags (the node is
  share-count only when EVERY component is), and carries an explicit compound VOLUME `ours` --
  the product over components of the share-count factor, 1.0 for a cash dividend, `None` for
  anything whose volume scaling we cannot know. A bonus 1:1 (k=0.5) plus a 5->1 face-value split
  (k=0.2) on the same date is ONE node with k = 0.1 on both sides; a bonus plus a special dividend
  is one node whose price `ours` is the product and whose volume `ours` is the bonus alone. The
  arbitration is untouched: the candidate set applies to the compound, exactly as ruled. This
  unblocks **BAJAJFINSV**, which the FIX-2 map builder refused outright ("two price-moving events
  share an ex-date 2022-09-13"); the refusal is kept as a defensive guard for any direct caller
  that hands `build_map` two nodes on one date, and can no longer fire from this path.
- **(ii) the unparsed node.** A new pseudo-kind `KIND_UNPARSED` enters the event list for every
  subject on the symbol that the CONTEXT 4.2 parser could not classify (the same
  `ParseException`s that already force MAP-REQUIRED under the Q-11 routing rule). It carries
  `our_price_factor=None` and no volume `ours`, so its candidate list is exactly `{measured,
  absent}` on the price side -- no `ours`, as ruled -- and `{price-factor, measured, absent}` on
  the volume side (the Q-12 clause-(ii) candidate, which is not an `ours` either). One scalar per
  event, oracle-arbitrated as ever. An unparsed subject that carries no price move resolves to
  `absent` at cost 1, below `measured` at cost 2, so an informational notice costs a probe window
  and changes no chain.
- **Unparsed events therefore never block a map.** They now BUILD one instead: see the COLPAL
  diagnosis in the CHUNK 5B FIX-3 REPORT and `docs/backfill_minute_report.md`.

### Q-11 ADDENDUM 4 (chunk 5B FIX-4, 2026-07-28) -- FLOORS IN UN-PROVABLE ERAS · the FINAL data ruling

The FIX-3 report's residual gate-3 rows carried a numbers-backed signature the floor ruling did not
reach: eleven of the seventeen failures show a RAW gap near zero against an ADJUSTED gap of
50-950%, i.e. the two closes are already in the same price domain -- the pre-ex side was never
un-adjusted -- which is exactly a vendor application floor sitting inside an era that decision
B123 kept the hunt OUT of. The architect ruled.

**ARCHITECT'S RULING (floors in un-provable eras -- supersedes B123's restriction), verbatim:**

> "ARCHITECT'S RULING (floors in un-provable eras — supersedes B123's restriction):
> an un-provable era is a conclusion under the floor-less model; where the floor
> itself caused unprovability, the hunt was locked out of exactly the eras needing
> it. Floor hypotheses MAY therefore be tested inside un-provable eras, under these
> guards: (i) hunting is SIGNATURE-GATED, never blanket — an event qualifies only if
> it shows the raw-gap-near-zero gate-3 signature, or an era failure-rate cliff
> (>=95% failing) at an event boundary; (ii) the one-fresh-unknown-per-era discipline
> holds — a floor being measured is that era's fresh unknown; previously committed
> sources may combine with it; (iii) acceptance is unchanged: the era stands ONLY if
> it becomes provable under normal per-day price containment and gate-1 re-gating —
> no fit, no floor, era stays un-provable; (iv) full provenance (probe days,
> verdicts, bisection path) in the map. This is the FINAL data ruling; residuals
> after this pass are disclosed, not chased."

**EXECUTED by the chunk-5B FIX-4 session (2026-07-28).** Every clause is code with a test behind
it, in `src/acumen/vendor_adjustment.py` (the model, the hypothesis, the extended search) and
`src/acumen/universe_backfill.py` (the signature gate, the hunt, the acceptance pass).

- **(i) the SIGNATURE GATE** (`signature_gated_events`, PURE, `universe_backfill`). An event is
  admitted into an un-provable era's hunt only by one of the two signatures the ruling names, and
  the admitting reason is recorded per event:
  - **the gate-3 raw-gap-near-zero signature.** Read off the symbol's own gate-3 failure rows,
    which already carry `raw gap` and `adjusted gap` as numbers. The test is the NEAREST-HYPOTHESIS
    one rather than an invented threshold: a healthy event predicts a raw gap of size `|k - 1|`
    (its own price step), a pre-ex side that was never un-adjusted predicts a raw gap of size 0,
    and the event qualifies when `|raw gap| < |k - 1| / 2`. Magnitudes, not signed values -- a
    +38% raw gap against a -20% step is not "the same price domain" by any reading. Scale-free, so
    a 5:1 split and a 5% special dividend are judged on the same footing. On the FIX-3 residual
    table this admits EXACTLY the eleven rows the architect named (raw gaps -4.63%..+10.98%) and
    rejects the six that are a different defect (ASTRAL +38.49% against a 10% half-step, BPCL
    +101.21%, GAIL 2018 +201.98%, OIL 2018 +42.44%, VBL -65.70%, COCHINSHIP -40.00% which is
    nearly its own healthy -50%).
  - **the era failure-rate cliff.** The gated days in the span immediately below the event's
    ex-date fail gate 1 at >= 95% (`FLOOR_HUNT_ERA_CLIFF_RATE`), measured over at least
    `MIN_CLIFF_DAYS = 20` gated days so a one-week bucket cannot manufacture a cliff.
  A provable-era search keeps its FIX-3 scope gate untouched (systematic failure >= 10%); the
  signature gate is what the ruling adds, and it governs the UN-PROVABLE domain alone.
- **(ii) the hypothesis, one fresh unknown per era** (`era_hypothesis`, PURE, `vendor_adjustment`).
  An un-provable era has no committed chain, so the search builds one from PREVIOUSLY COMMITTED
  sources exactly as the ruling allows: per event, the factor committed in the newest era that
  resolved it (`canonical_event_factors`), else our exact CONTEXT 4.2 factor, else -- if the event
  has neither -- the era is REFUSED and recorded (`no committed source and no ours factor`).
  Nothing is fitted: the only fresh unknown is the floor itself, and the oracle decides it.
- **the missing outcome the deadlock needed.** Where the floor sits ABOVE our whole history the
  binary search's first probe (the newest day, beside the ex-date) answers `event-out`, and the
  FIX-3 search correctly abandoned ("no floor to find"). That verdict is now itself a measurement:
  with `absent_floor_date` given, the search probes the newest, the oldest AND a midpoint, and only
  if ALL THREE answer `event-out` does it resolve a floor AT the ex-date -- the event is absent
  from every chain we can form. One `event-in` or one `undecided` and it stays UNRESOLVED.
- **(iii) ACCEPTANCE IS UNCHANGED, and it is the map builder's own.** A measured floor is not
  applied to an era by hand. The map is REBUILT with the floors in force (`build_map(...,
  floors=...)`): an event whose floor lies above an era's probe days is forced ABSENT for that era,
  and the era then has to satisfy the SAME oracle every other era does -- 2-paise per-day price
  containment against the raw daily high/low AND gate-1's unwidened `[-0.1%, +5.0%]` band. It also
  stops being a fresh unknown for the probe-gap guard, which is what lets a cascade of
  "under-determined" older eras unwind. No fit, no floor, era stays un-provable: the refusal path is
  the builder returning `provable=False` exactly as before, and the store is left untouched.
- **(iv) FULL PROVENANCE in the map.** `EventFloor` now also carries the price factor its probes
  were classified under, so a rebuilt map can re-validate the carry; every probe day, its verdict,
  both hypothesised chains and the measured fetched/raw ratios were already persisted and still
  are. The report prints the admitting signature, the bisection path and the era promotions.
- **the enriched baseline classifier** (`minute_backfill.stored_day_baseline`). A promoted era's
  days had never been touched, so they sit at the vendor's OWN chain -- which, once a floor drops an
  event, is no longer the era chain the hypotheses were generated from. `as-fetched-floored` names
  that ratio, and every hypothesis is now corrected by the multiple it actually matched rather than
  by the day's target chain (identical arithmetic on a floorless map; the two differ only where a
  floor is committed). Without it a promoted era would be classified UNKNOWN and left uncorrected.
- **B123 is superseded, not deleted.** Floors still apply to provable eras by the same arithmetic;
  what changed is that an un-provable era is no longer a wall the hunt cannot see through.

### EXECUTION-NOTE CORRECTIONS to the Q-11 chain (chunk 5B FIX-5, 2026-07-28) -- APPEND-ONLY

REVIEW_5B findings C7 and C8: two `EXECUTED by ...` notes above describe a narrower scope than the
code they document. **The rulings themselves are untouched and the code is correct; only these
session-written notes were stale.** They are corrected here rather than rewritten in place, so the
record of what each session believed at the time survives -- the same discipline ADDENDUM 4 used
when it superseded B123 without deleting it.

- **ADDENDUM 2's "the hunt scope is the ruling's own" (finding C7).** The note states the scope as
  "QUARANTINED or gate-1 rate below 98%". The code (`universe_backfill.floor_hunt_in_scope`) also
  admits a symbol carrying a GATE-3 failure. That third arm was added by the FIX-4 session under
  ADDENDUM 4 -- the raw-gap-near-zero signature is read off exactly those rows, and a symbol can sit
  above the 98% line while one ex-date of its history is in the wrong price domain, which is a
  correctness question and not a coverage one. It is explained in the function's own docstring and
  in report section 3c; it is the addendum-2 note that was never updated. **FIX-5 adds a fourth
  arm** under the Q-14 ruling: a symbol below 98% on GATE 1P is in scope whatever its volume rate
  says, which is the whole point of finding Q1 (SRF sits at 99.5% on gate 1 and stored 216 days at
  five times the traded price).
- **ADDENDUM 4's "admitted only by one of the two signatures" (finding C8).** There is a third
  admission route, and it is correct: `force_ex_dates` re-admits an event a PREVIOUS pass already
  resolved a floor for, because the repair that floor made is exactly what erases the failure
  signature that admitted it -- requiring the signature again would make re-measurement impossible
  after the first success. It is recorded as decision B138 and is populated only from previously
  RESOLVED floors, so it cannot admit an event that was never floored. **FIX-5 adds a fourth**: the
  Q-14 gate-1P failure CLUSTER. The addendum's prose said "two"; the code has always carried the
  `force_ex_dates` route as well.

---

## Q-12 · chunk 5B · class A · **RESOLVED -- executed chunk 5B FIX-2 (2026-07-26)** · was costing COVERAGE, not correctness

**Question.** Q-11 rules that a measured factor `k̂` is "the median ratio over pre-ex-date probe
days", for price and (independently) for volume. On the PRICE side the observable is unbiased --
`fetched/raw` is the same number every day. On the VOLUME side it is **not**: the observable is
`raw_daily_vol / fetched_vol`, and the 1-minute sum systematically UNDER-counts the daily total
(the pre-open call auction the exchange counts and continuous candles do not). That is the exact
asymmetry gate 1's own band `[-0.1%, +5.0%]` exists for. Taking the MEDIAN of a positively-skewed
observable puts roughly half the probe days BELOW the true factor, and a day below it produces a
NEGATIVE gap that the -0.1% floor rejects -- so an era whose true factor reconciles every day is
marked un-provable. How should the volume `k̂` be estimated?

**Why it is a hole.** Q-11 names one estimator (the median) for both sides. It does not say what
to do when the volume observable is biased by a known, one-directional artefact that the gate's
own band already models. Deciding either way is a change to a ruled formula, so this session did
not.

**Measured, live, 2026-07-26 (ABB, demerger ex 2019-12-20, the run's first map-required symbol).**
The four pre-ex probe days the runner chose:

| probe day | fetched H/raw H | fetched L/raw L | vol recovery `raw/fetched` |
|---|---|---|---|
| 2019-12-16 | 0.897601 | 0.897600 | 0.897998 |
| 2019-12-17 | 0.897599 | 0.897601 | 0.899205 |
| 2019-12-18 | 0.897600 | 0.897598 | **0.897601** |
| 2019-12-19 | 0.897601 | 0.897599 | 0.904588 |

The PRICE factor is a rock-solid **0.8976** on all four days, to six decimals. The VOLUME
recoveries scatter upward from that same 0.8976 -- 2019-12-18 sits exactly ON it, and the others
sit 0.04%-0.78% above, which is precisely the auction shortfall. The median is 0.8986, and with it:

| probe day | un-adjusted vol | raw daily vol | gate-1 gap | verdict |
|---|---|---|---|---|
| 2019-12-16 | 124,833 | 124,749 | -0.067% | pass |
| 2019-12-17 | 44,280 | 44,311 | +0.070% | pass |
| 2019-12-18 | 121,092 | 120,958 | **-0.111%** | **FAIL (floor is -0.1%)** |
| 2019-12-19 | 89,555 | 90,154 | +0.664% | pass |

One day misses the floor by **0.011 percentage points** and `_volume_reconciled` (which requires
EVERY probe day to pass, correctly) rejects the chain -- so no candidate fits, the era is
un-provable, and **~790 ABB symbol-days (2016-10 .. 2019-12) are excluded**. With the price
factor 0.8976 used for volume instead, every probe day passes: +0.045% / +0.178% / 0.000% /
+0.773%. The right answer was available and the ruled estimator missed it.

**Why it matters.** ABB is the FIRST map-required symbol the run reached, so this is not an
exotic case -- it is the shape of every demerger/rights symbol whose vendor volume factor has to
be measured. Each one loses its whole pre-event minute span. Nothing WRONG is stored (the days
are excluded and counted, CONTEXT 7-E3, and gate 1 remains the per-day proof), so this costs
COVERAGE, not correctness -- which is why the run proceeds rather than halting.

**What this session did meanwhile (STOP, no silent decision).** Executed Q-11 exactly as ruled:
`vendor_adjustment._refine_scalars` still takes the median for both passes, `_volume_reconciled`
still requires every probe day inside the unwidened band, and an era that fails is un-provable ->
excluded + counted. The run continues and the report prints, per symbol, how many days each
un-provable era costs -- so the architect rules with numbers rather than with this one example.

**Options for the architect (not decided here):**
(a) **Estimate the volume `k̂` as the MINIMUM (or a low quantile) of `raw/fetched` over the probe
days** -- the observable's floor is the unbiased point, because the shortfall is one-directional.
(b) **Add the measured PRICE factor to the volume candidate set** ({ours, measured-price,
measured-volume, absent}), letting the containment/band oracle pick it -- the arbitration stays
exactly as ruled and only the candidate list grows. ABB's evidence says this candidate wins.
(c) **Keep the median and accept the coverage loss**, disclosed in the chunk-9 report.
(d) Something else the architect prefers; the map is rebuildable and
`rebuild_symbol_raw_with_map` is idempotent, so any ruling can be applied to the already-fetched
store WITHOUT re-downloading a single candle.

Chunk 6 is not blocked (it consumes whatever days survive gate 1). Chunk 9's coverage is what
this decides.

**ARCHITECT'S RULING (relayed to the chunk-5B FIX-2 session, 2026-07-26), verbatim:**

> "ARCHITECT'S RULING (volume estimator + candidates): the per-day volume ratio is
> one-sidedly contaminated by the pre-open auction (measured = true/(1-auction)), so
> the median is biased HIGH -- proven by ABB (0.8986 vs price 0.8976) and ADANIENT
> (0.9729 vs TERP 0.9695 which reconciles volume 4/4). Therefore: (i) the measured
> VOLUME estimator becomes the MINIMUM over probe days, taken only across days whose
> PRICE containment passes, minimum 3 such days, else no measured-volume candidate;
> (ii) the event's CHOSEN PRICE factor joins the volume candidate set. Volume
> candidate order: ours(share-count) > chosen-price-factor > measured-minimum >
> absent; per-day gate-1 band arbitration unchanged; the -0.1% floor is NOT widened."

**RESOLVED -- executed by the chunk-5B FIX-2 session (2026-07-26).** Every clause is code with a
test behind it, in `src/acumen/vendor_adjustment.py`. The arbitration itself is UNCHANGED: the
oracle is still per-day price containment AND per-day gate-1 with the band `[-0.1%, +5.0%]`
untouched (`VOLUME_GAP_MIN_PCT` is byte-identical -- pinned by
`tests/test_vendor_adjustment.py::test_the_gate1_floor_is_not_widened_by_the_q12_ruling`). Only
the ESTIMATOR and the CANDIDATE LIST changed.

- **(i) the estimator.** `volume_estimator(era, k_price, tol_paise)` replaces the median on the
  volume side: it keeps only the probe days whose PRICE containment passes under the era's
  chosen `k_price` (so a day the price oracle rejects can never set the volume floor), requires
  at least `MIN_VOLUME_ESTIMATOR_DAYS = 3` such days, and returns the **MINIMUM** of
  `raw_volume / fetched_volume` over them -- the observable's floor, which is the unbiased point
  because the auction shortfall is one-directional (`measured = true / (1 - auction)` >= true).
  Fewer than 3 qualifying days -> `None` -> **no measured-volume candidate is offered at all**
  (the era then stands or falls on `ours` / the chosen price factor / absent). The same estimator
  is used in BOTH places a volume scalar is formed: the per-era solve (`_resolve_pass`) and the
  cross-era refinement (`_refine_scalars`, which now takes the MIN over the union of an event's
  qualifying days instead of the median). The PRICE side keeps the ruled median, unchanged --
  `fetched/raw` is symmetric and unbiased there.
- **(ii) the chosen price factor as a volume candidate.** New source
  `SOURCE_PRICE_FACTOR = "price-factor"`. The price pass runs FIRST (it always did), and each
  event's resolved price factor is handed to the volume pass as an extra candidate. So a rights
  or demerger -- which has no `ours` volume factor at all, because the vendor scales volume by a
  value that is not our TERP -- can now be reconciled by the factor the price oracle already
  proved to 6 decimals, instead of only by an observed volume ratio.
- **the candidate ORDER on the volume side is exactly as ruled**: `ours` (0) > `price-factor`
  (1) > `measured` (2) > `absent` (3). Note `absent` moved from second to LAST *on the volume
  side only*; the PRICE side keeps `ours` (0) > `absent` (1) > `measured` (2). A share-count
  event and a cash dividend both carry a cost-0 volume `ours` (the price factor and 1.0
  respectively), so the reordering can only ever decide an event that has NO volume `ours` --
  a rights, a demerger, a Q-6-pending rights -- which is precisely the ruling's target.
- **Applied to the already-fetched store, no candle re-downloaded.** The persisted map now
  carries its estimator's identity (`"volume_estimator": "min-over-price-passing-days-v2"`); a
  map written under the median is STALE by that marker and is rebuilt (probe windows only --
  a handful of minute calls), and the stored days are re-un-adjusted in place by the idempotent
  `rebuild_symbol_raw_with_map`. Recovery numbers for ABB / ADANIENT / BANKBARODA / BDL /
  BHARTIARTL are in the CHUNK 5B FIX-2 REPORT and `docs/backfill_minute_report.md`.

### Q-12 ADDENDUM (chunk 5B FIX-2, 2026-07-26) -- quarantine recovery

The chunk-5B build session's own hand-off observation ("routing quarantined table-path symbols
through the map as a second pass is an option the architect may want", raised off APLAPOLLO's
77.8%) is now ruled on.

**ARCHITECT'S RULING (quarantine recovery), verbatim:**

> "ARCHITECT'S RULING (quarantine recovery): any TABLE-PATH symbol quarantined on
> gate-1 is automatically rerouted through the MAP path as a second pass (probes give
> it the price oracle; measured candidates may recover it -- e.g. unrecorded or
> vendor-variant events). Symbols still failing after the map pass stay quarantined
> with a failure-pattern analysis in the report: failures clustered before a CA
> ex-date (adjustment problem) vs scattered (auction/liquidity shape). The gate-1
> +5.0% ceiling's behavior on illiquid names (auction share of a tiny day can exceed
> 5%) is EXPLICITLY DEFERRED to the architect's review of the completed run's report
> -- flag it there with per-symbol evidence; do not tune the band."

**EXECUTED by the chunk-5B FIX-2 session (2026-07-26).**

- **The second pass** (`universe_backfill.reroute_quarantined_to_map`). A symbol that finishes
  its table-path ingest below `QUARANTINE_GATE1_MIN_PASS_RATE` is not left quarantined: its eras
  are probed, a map is built and persisted (so the recovery is auditable), the ALREADY-STORED
  days are re-un-adjusted through it, and gate 1 is re-run. The reroute is recorded on the
  symbol's ledger row (`reroute_attempted`, `route` flips to `map-required` with the reason
  `quarantine-recovery`), so a resumed run never re-probes a symbol it has already rerouted.
- **No candle is re-downloaded.** The store already holds the symbol's whole history, so the
  reroute never re-ingests. It does need the probe windows (a handful of minute calls per era --
  that IS the price oracle the ruling is buying). Applying the map to a table-path store is the
  one place the arithmetic is not a plain "divide by the map's k": those days were already
  divided by the factor-table chain at ingest, so the rebuild applies the NET factor
  `k_map / k_table` in ONE division (`rebuild_symbol_raw_with_map(..., applied_factors=...)`),
  never a second full division on top of the first -- and a net factor of 1 is the exact
  identity, so a symbol whose map agrees with its factor table is untouched.
- **The failure-pattern analysis** (`gate1_failure_profile`, PURE). For every symbol still
  quarantined the report prints: how many failing days sit ABOVE the +5.0% ceiling vs BELOW the
  -0.1% floor, the per-era failure rate, the median raw daily volume of the above-ceiling
  failing days against the symbol's own median, and a verdict of `clustered-before-ex-date
  (adjustment problem)` / `scattered (auction/liquidity shape)` / `mixed`.
- **The +5.0% ceiling question is FLAGGED, NOT TUNED.** `VOLUME_GAP_MAX_PCT` is unchanged at
  `5.0`, and the report carries a dedicated section ("Deferred to the architect: the gate-1
  +5.0% ceiling on illiquid names") holding exactly the per-symbol evidence the ruling asks for.
  No band was moved.

### Q-12 ADDENDUM 2 (chunk 5B FIX-3, 2026-07-26) -- AUCTION RELIEF: the deferred ceiling, answered

The +5.0%-ceiling question the Q-12 addendum DEFERRED ("flag it there with per-symbol evidence;
do not tune the band") came back from the architect's review of the completed run's report.

**ARCHITECT'S RULING (auction relief -- the deferred +5.0% ceiling), verbatim:**

> "ARCHITECT'S RULING (auction relief — the deferred +5.0% ceiling): the ceiling stays.
> A gate-1 failure ABOVE the ceiling may be relieved IFF ALL hold: (a) the floor side
> is not triggered; (b) stored 1-min HIGH == raw daily HIGH and 1-min LOW == raw daily
> LOW exactly; (c) first stamp's open == raw daily open exactly; (d) shortfall <= 20%
> (sanity cap). Rationale: data LOSS clips extremes with overwhelming probability; a
> day with intact extremes, matching open, and only volume short is a thin day whose
> pre-open auction exceeds 5% — a market property (PNBHOUSING: 734/746 above-ceiling
> failures at half-median volume). Relieved days are counted SEPARATELY
> ('auction-relief pass') and disclosed; the -0.1% floor is untouched; below-floor
> failures are never relieved."

**EXECUTED by the chunk-5B FIX-3 session (2026-07-26).** In
`src/acumen/quality_gates.py::auction_relief` (PURE), wired into
`universe_backfill.gate_symbol`.

- **The ceiling stays and the band is byte-identical.** `VOLUME_GAP_MIN_PCT = -0.1` and
  `VOLUME_GAP_MAX_PCT = 5.0` are untouched, and `volume_gate` itself is untouched -- pinned by
  `tests/test_vendor_adjustment.py::test_the_gate1_floor_is_not_widened_by_the_q12_ruling` and by
  a new `tests/test_quality_gates.py` probe that reads the two constants. Relief is a SEPARATE
  verdict layered on a gate-1 FAILURE, never a widening: a day that fails gate 1 still fails
  gate 1, and is then separately examined for relief.
- **The four conditions are each individually NECESSARY**, and each is tested alone
  (`tests/test_auction_relief.py` flips one condition at a time and asserts the relief is
  refused): (a) the gap must be ABOVE the +5.0% ceiling -- a below-floor failure (minute volume
  EXCEEDING the daily total, the signature of an un-recovered vendor adjustment) is NEVER
  relieved; (b) the stored day's fold HIGH must equal the raw daily HIGH and its fold LOW the raw
  daily LOW, EXACTLY, to the paisa -- no tolerance, because the ruling's whole rationale is that
  data loss clips extremes; (c) the FIRST stamp's open must equal the raw daily open exactly --
  a lost opening minute is the one loss that need not move an extreme; (d) the shortfall must be
  <= 20%.
- **Counted SEPARATELY and disclosed.** A relieved day is an `auction-relief pass`, not a gate-1
  pass: `GateTally.gate1_pass` stays the STRICT count and `gate1_relieved` is its own field, so
  the report prints the strict rate, the relief count and the effective rate side by side, per
  symbol and in the headline. Coverage and the quarantine decision use the effective rate (the
  ruling calls a relieved day a pass); the strict number is never overwritten.
- **Class-B decision, recorded not assumed (B122).** The completeness ruling makes gate 2 exclude
  a day for missing minutes only "ON A DAY WHERE GATE-1 ALSO FAILS". A relieved day's gate-1
  verdict is "pass (by relief)", so it is passed to `integrity_gate` as `volume_reconciled=True`.
  The reading is forced by the relief conditions themselves: (b) and (c) are direct evidence that
  no data was lost, which is the exact hypothesis the gate-2 missing-minutes trigger exists to
  catch -- and the thin days relief targets are precisely the days that carry tradeless minutes,
  so the other reading would cancel the relief it just granted. The report counts how many
  relieved days also carried >15 tradeless minutes, so the size of this decision is visible.

---

## CONTEXT §4.5 / §7-E4 AMENDMENT (architect-owned; CONTEXT v1.3 will carry it, effective now by this record) · recorded chunk 5B FIX-2, 2026-07-26

This is not a question -- it is an architect ruling that AMENDS CONTEXT §4.5 gate 2 and
CONTEXT §7-E4. It answers the chunk-5B gate-2-vs-LIQUIDITY finding recorded below. CONTEXT.md is
the architect's file and this session does not touch it; the ruling is recorded here verbatim and
executed, exactly as Q-4..Q-11 were.

**ARCHITECT'S RULING (completeness = volume reconciliation, not minute counts), verbatim:**

> "ARCHITECT'S RULING (completeness = volume reconciliation, not minute counts): a
> missing 1-minute stamp on a day whose gate-1 volume reconciliation PASSES is a
> NO-TRADE minute, not missing data -- the vendor omits tradeless minutes and every
> traded rupee is accounted for. Gate 2 is redefined: exclusion triggers are
> duplicates, impossible OHLC, negative values, or missing-minutes ON A DAY WHERE
> GATE-1 ALSO FAILS (indistinguishable from data loss). Missing minutes alone, with
> gate-1 passing, are recorded as liquidity statistics, never exclusions. E4 is
> redefined the same way: the 09:15-11:14 profile window is valid when the DAY passes
> gate-1 (zero-volume minutes contribute zero to the profile, which remains true);
> E4's minute-count trigger is retired. NO liquidity filter is invented (the trader
> specified none; per-symbol traded-minutes statistics are reported for his eyes)."

**EXECUTED by the chunk-5B FIX-2 session (2026-07-26).** In
`src/acumen/quality_gates.py::integrity_gate`, which now takes the day's gate-1 verdict:

- **Exclusion triggers, exactly the ruling's four.** (1) any duplicate stamp; (2) impossible
  OHLC (`high < low`, or a close outside `[low, high]` -- CONTEXT 4.5's own two); (3) **negative
  values** -- a new trigger the ruling adds, tested on every OHLC field AND on volume, because a
  negative price or share count is impossible rather than merely improbable; (4) missing minutes
  `> MAX_MISSING_MINUTES` **only on a day where gate 1 ALSO fails**.
- **Missing minutes alone, gate-1 passing -> INCLUDED and counted as liquidity.** The day passes
  gate 2 and its `missing` / `present` counts become the liquidity statistics the ruling asks be
  reported: per symbol the run now records average, median and minimum traded minutes per day
  and the number of days carrying tradeless minutes, all in
  `docs/backfill_minute_report.md`. `IntegrityGateResult.liquidity_note` names the case
  explicitly so nothing reads as a silent pass.
- **Gate-1 verdict unknown -> the CONSERVATIVE reading.** `volume_reconciled=None` (no raw daily
  row, so gate 1 could not run) keeps the pre-amendment behaviour: missing minutes exclude. The
  ruling's licence is "gate-1 PASSES", and an unrun gate 1 has not passed.
- **E4.** CONTEXT §7-E4's minute-count trigger ("missing > 5 of its 120") was NOT yet
  implemented anywhere -- chunk 6 owns the POC window -- so retiring it is a spec+docs act, not a
  code deletion. It is recorded here, in the `quality_gates` module docstring, and in
  `aggregate.py`'s E4 note, so chunk 6 builds the REDEFINED rule: the 09:15-11:14 profile window
  is valid when the DAY passes gate 1, and zero-volume minutes contribute zero volume to the
  profile (which remains arithmetically true -- a prorata row sum over 118 traded minutes and
  over the same 118 traded minutes plus 2 tradeless ones is the same number).
  `tests/test_quality_gates.py::test_e4_minute_count_trigger_is_retired_nothing_in_src_implements_it`
  is an `ast`-level probe that FAILS if any `src/` module reintroduces a 120-minute / 5-missing
  count trigger, so chunk 6 cannot rebuild the retired rule by accident.
- **NO liquidity filter was invented.** There is no new threshold anywhere: no minimum traded
  minutes, no minimum volume, no symbol drop. The statistics are printed for the trader's eyes
  and nothing consumes them.

**Measured effect of the redefinition** (the same stores, gates re-run with no refetch): counts
are in the CHUNK 5B FIX-2 REPORT and in `docs/backfill_minute_report.md` §4.

---

## chunk 5B FINDING (not a spec hole) · gate 2 vs LIQUIDITY · recorded 2026-07-26 · **ANSWERED by the CONTEXT §4.5/§7-E4 amendment above (2026-07-26)**

Not a question -- CONTEXT 4.5 gate 2 is unambiguous -- but a measured consequence the architect
should see before chunk 9 reads a coverage number.

Gate 2 excludes a day missing more than 15 of the 375 session minutes. **The vendor omits minutes
in which nothing traded.** CONTEXT 4.3's PoC measured "375/375 candles per day, zero gaps" -- on 5
LIQUID symbols in 2026. Measured this session on ABB in 2019: **318, 293, 325 and 338 traded
minutes** on four consecutive days, i.e. 37-82 missing, so gate 2 excludes every one of them. Over
ABB's whole stored history that is **828 of 2,429 days (34%)** excluded for a LIQUIDITY reason
rather than a data-quality one.

The strategy itself only needs 09:15-11:14 (the POC window, guarded separately by CONTEXT 7-E4's
"missing > 5 of 120") plus the 15-minute candles to 15:15, so a whole-day 375-minute rule is
stricter than the strategy requires. The backfill report prints average traded minutes per day per
symbol and flags every symbol losing more than 10% of its days to gate 2, so the size of this is
visible. **No code deviates**: gate 2 is applied exactly as CONTEXT 4.5 states it.

**ANSWERED (2026-07-26).** The architect's completeness ruling (the CONTEXT §4.5/§7-E4 amendment
recorded immediately above this finding) resolves it: a missing stamp on a gate-1-PASSING day is a
no-trade minute, not missing data, so it is no longer an exclusion. The finding's own numbers are
what the ruling was made on. Executed the same session; the before/after counts are in
`docs/backfill_minute_report.md`.


---

## Q-13 · chunk 6 · class A · **RESOLVED — the FINER profile (29-Jul-2026)** · was NON-BLOCKING

> **CLOSED at the interim.** The trader's BHARTIARTL 2026-07-17 chart reading settled it on the
> ROW COUNT (his 25 is one row from the finer profile's 26 and three from the coarser profile's
> 22); the price reading is inconclusive at the two candidates' Rs 0.05 separation. See ROUND-3
> FINAL RECEIPTS (29-Jul-2026), receipt R3F-f. CONTEXT v1.3 §3.3 now states it as a ruling.
> The `totalTicks` rounding MODE (the reviewer addendum's point 3) stays a pinned interim with a
> chunk-12 verification slot.

**Question.** CONTEXT 3.3 fixes the ticks-per-row rounding as *"`tpr = totalTicks/N` rounded to a
whole number (minimum 1), **direction chosen so the realized row count is closest to requested
N**"*. When the two directions are EQUALLY close, the spec does not say which wins. Which one does
TradingView take?

**Why it is a hole, and why it is not cosmetic.** The two directions build different grids, so the
POC lands on a different price. Measured this session over the stored 1-minute history (spec
window, N=24, real per-symbol ticks):

| symbol | stored days | days sitting exactly on the tie | POC differs | median difference | worst | difference exceeds one row height |
|---|---|---|---|---|---|---|
| TCS | 2,430 | 487 (20.0%) | 487 of 487 | Rs 0.45 | Rs 20.35 | 43 |
| BHARTIARTL | 2,429 | 262 (10.8%) | 262 of 262 | Rs 0.35 | Rs 18.55 | 23 |
| DIXON | 2,192 | 321 (14.6%) | 321 of 321 | Rs 3.50 | Rs 187.50 | 33 |
| ABB | 2,429 | 259 (10.7%) | 259 of 259 | Rs 1.25 | Rs 57.75 | 19 |

So on roughly **one stock-day in six to ten** the POC price -- the level every entry, stop and
target of that day hangs on (CONTEXT 3.4) -- is decided by a rule CONTEXT.md does not state.

**Why the calibration does not settle it.** SIX of the 25 frozen `poc/data` symbol-days sit on the
tie (TCS 07-20, HDFCBANK 07-20, DIXON 07-15, DIXON 07-14, MANAPPURAM 07-17, MANAPPURAM 07-14) --
but **none of the five days the trader gave a TradingView reading for** (the F7 anchors) is one of
them. The 5/5 calibration match therefore does not exercise the tie in either direction.

**INTERIM (executed, and it is a measured choice, not a preference).** The tie keeps the **smaller
`tpr`** -- the FINER profile, i.e. MORE rows. Three reasons, in order of weight:

1. It reproduces the frozen calibration printout on **all 25 days to 4e-13**, including all six tie
   days. The other direction moves six of the 25 frozen `poc_prorata` values, i.e. it would
   contradict the artifact CONTEXT 8 F7 calls authoritative.
2. It is the same direction the PoC implementation took (`poc/poc3_volume_poc_test.py`, the script
   whose output the trader's 5/5 match was measured against), so nothing about the calibration's
   provenance changes.
3. Where TradingView's own published example is NOT a tie it also lands on the finer side (100
   ticks, N=30 -> 34 rows over 25 rows), so "more rows" is at least consistent with the one datum
   TV documents. This is corroboration, not proof -- TV documents no tie case.

Pinned by `tests/test_poc.py::test_the_tpr_tie_keeps_the_finer_profile_the_direction_the_frozen_printout_was_built_with`
and by the all-25 reproduction test, so the interim cannot be flipped silently.

**Blocks.** Nothing today. It is a candidate for the chunk-6 TRADER GATE: if the trader's Q32 chart
days (or any future reading) land on a tie day, they settle it empirically. If the architect wants
certainty sooner, the cheapest oracle is one screenshot of any tie-day chart with the row count
visible -- the realized ROW COUNT alone (25 vs 26 rows for 130 ticks at N=24) answers it without a
POC reading at all.

### chunk 6 FINDING (not a spec hole) -- a window with bars but ZERO volume

CONTEXT 3.3's tie rule is unconditional, so a profile whose rows are ALL zero (a 09:15-11:14 window
holding candles but no traded volume on a day that still passes gate 1) resolves literally to the
topmost row's midpoint -- a POC carrying no information. Nothing was invented: the literal spec
answer is what the engine returns, and `DayProfile.zero_volume_profile` FLAGS the day so chunk 9
can count it instead of trusting it silently. **Measured frequency: 0 of 9,480 stored symbol-days**
across TCS, BHARTIARTL, DIXON and ABB -- the vendor omits tradeless minutes entirely, so a window
with no volume is a window with no candles, which is the separate `no-poc-no-candles-in-window`
answer (11 days per symbol, mostly non-standard sessions). Recorded so the architect can rule the
degenerate case out of trading if he wants; on today's evidence it never happens.

### Q-13 REVIEWER ADDENDUM (chunk-6 REVIEW, 2026-07-26) -- three measured additions, nothing decided

Recorded by the chunk-6 review session (docs/reviews/REVIEW_6.md). Nothing here changes the
interim, the code or any ruling; all three items are measurements the architect should have when
Q-13 goes back to the trader.

**(1) Q-13's interim and its statistics are independently confirmed.** The reviewer recomputed all
25 frozen `poc_prorata` values from the `poc/data` CSVs with a from-scratch implementation of
CONTEXT 3.3 that imports nothing from `src/acumen`: 25/25 reproduce, worst error **4.0e-13**, and
the six tie days are exactly the six named above. Flipping the tie to the coarser side moves
exactly those six and no others. BHARTIARTL's row in the table above reproduces from the store to
the digit (262 tie days, POC differs 262/262, median Rs 0.35, worst Rs 18.55, 23 beyond one row
height); the 2,429-vs-2,418 denominator difference is exactly the empty-window days (decision B118).

**(2) The chunk-6 gate's discriminating day sits on the tie under BOTH windows.**
`docs/gate_chunk6_poc_evidence.md` asks the trader to check **BHARTIARTL 2026-07-17**. Recomputed
from the minute store under both silences at once:

| window | tie -> finer (the interim) | tie -> coarser | rows drawn |
|---|---|---|---|
| 8-candle (spec) | **1914.60** | 1914.65 | 26 vs 22 |
| 9-candle (alternative) | **1914.50** | 1914.55 | 26 vs 22 |

The **Q42 window conclusion is safe either way** -- the 8-vs-9 gap is Rs 0.10 in both directions
and the ordering is preserved. But the absolute price he is asked to match depends on Q-13, so a
reading of 1914.65 would confirm the 8-candle window while REFUTING this interim. The good news is
the reverse: **one reading off that one chart settles Q42 and Q-13 together**, and the row count is
visible on the same screenshot (26 rows under the interim, 22 under the coarser direction). The
pack's closing paragraph asks for "any chart with the rows countable" without noting that the two
charts already in the pack are exactly such days. The pack is the architect's document; the review
recommends one added sentence rather than editing it.

**(3) A SECOND, smaller silence in the same CONTEXT 3.3 sentence: the rounding MODE of
`totalTicks`.** CONTEXT 3.3 says `totalTicks = round((top - bottom)/tick)` without naming a
rounding mode. On the tick grid the division is exact, so the mode is invisible -- but the
instrument master carries TODAY's tick, and NSE widened ticks, so historical days traded on a finer
grid: measured, `(top - bottom)` is not a whole number of ticks on **42.1%** of BHARTIARTL's stored
days, **68.4%** of ABB's, **43.6%** of AUBANK's and **42.8%** of ADANIENT's (BEL, whose tick did not
widen: 0.7%), and the dominant residual is **exactly half a tick**, which is precisely where the
mode decides. Measured consequence on BHARTIARTL at N=24: half-even (the implemented choice,
decision B114) and half-up give a different `totalTicks` on **449 of 2,418 days (18.6%)** and a
different **POC on 10 of them** (median Rs 0.40, worst Rs 9.85). Two orders of magnitude smaller
than the tie above, but not zero. **Not raised as a separate question** -- it is the same sentence,
the same oracle (a row count off any chart) and the same trader round-trip -- and the implemented
choice is defensible (Python's own `round`; the rounding this repo already uses for money). It is
now pinned by `tests/test_review6_probes.py::test_total_ticks_rounds_half_even_and_not_by_truncation`
so it cannot flip silently either. **The architect may want to fold it into Q-13's answer.**

**(4) Recording request.** Q-13 carries no `ARCHITECT'S RULING ... verbatim` block, unlike
Q-10/Q-11/Q-12 and the completeness amendment. The chunk-6 review was told an architect interim
confirmation exists; it is not in this file. It should be recorded here in the same verbatim form,
so a later session reads it from the repo instead of from a conversation.

---

## Q-14 · chunk 5B REVIEW · class A · **RESOLVED — ruled, executed and re-reviewed (relabelled 29-Jul-2026)** · no longer blocks chunk 9

> **CLOSED.** The architect's ruling below was recorded verbatim, executed by chunk-5B FIX-5 and
> confirmed by a fresh re-review (REVIEW_5B_2, PASS), and its closing addendum accepted the
> definition of done. Relabelled by the chunk-7 session, the first to consume the ruling
> downstream (CONTEXT v1.3 §4.6 makes recomputing gate 1P per stock-day a duty of every engine
> that reads the minute lake). **Only this status line changed -- no word of the question, the
> measurement, the ruling or the execution notes was altered.**

**Question.** CONTEXT 4.5's gate 1 proves a stored day's **VOLUME** against the bhavcopy. The Q-11
ruling's price oracle proves an **ERA's price**, over that era's probe days. 1,963 stored symbol-days
fall between the two: their 1-minute prices sit at 0.1x-5x the price the exchange printed, and every
one of them PASSES the gate battery and is counted in the run's 413,914-day usable headline. Should a
per-day PRICE containment check -- the existing `max(2 paise, 0.1% x raw)` oracle applied to each
stored day against the raw daily high/low -- join the gate battery? And are the days it flags
EXCLUDED (CONTEXT 7-E3), RE-MEASURED (a floor hunt admission signature), or DISCLOSED?

**Why it is a hole.** CONTEXT 4.5 defines the gate battery. Adding to it is a spec change, not an
implementation choice, so the review did not decide it. Nothing in Q-10, Q-11 (or its four addenda),
Q-12 (or its two) or the completeness amendment asks for a per-day price test; each ruling states that
"gate 1 remains the per-day proof", which is true of volume and, as measured below, not of price.

**The mechanism, measured not inferred.** Price and volume factors are arbitrated INDEPENDENTLY --
Q-11's own words, "for price and (independently) for volume" -- and `_price_contained`
(`src/acumen/vendor_adjustment.py:1548-1566`) quantifies over `era.probe_days`, typically the four
sessions before the era's next ex-date. When the vendor's internal splice sits inside an era but
OLDER than its probe window, and the committed `k_volume` happens to match what the vendor did to
volume while `k_price` does not, the day's price is wrong and no gate can see it.

NMDC is the clean case. Its era `pre-2019-03-22` is **provable**, with `k_price = 0.235189` against
`k_volume = 0.333337` -- two different factors -- and `probe_days = ['2019-03-15', '2019-03-18',
'2019-03-19', '2019-03-20']`, four days at the top of an era spanning roughly 600. The vendor applied
1/3 to the 2018 days; dividing them by 0.235189 leaves them at 1.4173x raw, while the volume, scaled
by the matching 0.333337, reconciles at +0.107%. Every gate passes.

**Measured over all 433,065 stored symbol-days** (read-only fold of the parquet minute store against
the raw bhavcopy; days that PASS gate 1 whose fold high differs from the bhavcopy high by >5%):

| Symbol | Days | Factor | Example |
|---|---|---|---|
| IOC | 1,042 | 0.667x | 2018-04-05: stored high Rs 116.10 vs bhavcopy Rs 174.15, gate-1 gap +0.222% |
| TATASTEEL | 498 | 0.100x | 2020-07-28: stored high **Rs 36.00** vs bhavcopy **Rs 360.00**, gap +0.071% |
| SRF | 216 | 5.000x | 2016-10-03: stored high Rs 9,625.00 vs bhavcopy Rs 1,925.00, gap -0.002% |
| NMDC | 134 | 1.417x | 2018-03-27: stored high Rs 173.26 vs bhavcopy Rs 122.25, gap +0.107% |
| RECLTD | 65 | 0.750x | 2020-08-13: stored high Rs 83.25 vs bhavcopy Rs 111.00, gap +0.066% |
| APLAPOLLO | 3 | 2.000x | 2018-10-01: stored high Rs 2,566.70 vs bhavcopy Rs 1,283.35, gap +0.000% |
| ASIANPAINT / BIOCON / PNB / SUZLON / TATAPOWER | 5 | one day each | isolated |
| **TOTAL** | **1,963** | | every one on a **SETTLED** symbol |

At the containment oracle's own 0.5% tolerance the count is 2,651 gate-1-passing days off scale,
2,640 of them on settled symbols. The 1,963 above is the conservative reading.

**Why it matters.** All of these symbols are SETTLED, so their days are inside the usable headline and
reachable by chunk 9. A POC built on TATASTEEL 2020-07-28 would be computed on a Rs 36 price grid; the
stop-loss distance would be a tenth of reality and `floor(risk / (entry - SL))` would size the
position ten times too large. The resulting trade record would look entirely ordinary. This violates
CONTEXT 7-E11 ("intraday engines run on RAW same-day 1-min prices ... PnL in that day's real rupees")
in the data the chunk exists to produce.

**Why it is not already licensed.** Q-11 ADDENDUM 4's closing sentence licenses residuals that are
**DISCLOSED**, not chased. These days are disclosed nowhere: they are counted as PASSES, and the
report's own un-provable-day count (300) is a different quantity entirely (see REVIEW_5B finding Q6).

**What the review did meanwhile (STOP, no silent decision).** Nothing. No file under review was
modified, no test was added to pin a gate the architect has not ruled should exist, and no store was
touched. The finding is recorded in `docs/reviews/REVIEW_5B.md` (finding Q1) with the full
measurement, and the chunk is FAILED so that chunk 9 cannot start on this lake.

**Options for the architect (not decided here):**
(a) **Add a per-day price containment gate** using the existing oracle, and EXCLUDE + COUNT what it
flags (CONTEXT 7-E3's own treatment) -- cheapest, needs no re-download, and would have caught all
1,963 days;
(b) **Add the same check as a floor-hunt admission SIGNATURE** (a third signature beside the gate-3
raw-gap and the era cliff), so the splice is measured and the days repaired rather than discarded;
(c) **Tighten the era oracle** so containment is quantified over the era's whole span rather than its
probe days -- correct but expensive, since it needs a probe per span rather than per era;
(d) **Accept and DISCLOSE**, listing the affected symbol-days in the residual register so chunk 9
excludes them by name.

Both sides of the check are LOCAL -- the minute store and the daily store -- so any ruling is
applied to the already-fetched store with **no candle re-downloaded**.

**ARCHITECT'S RULING (the per-day PRICE gate), relayed to the chunk-5B FIX-5 session
(2026-07-28), verbatim:**

> "ARCHITECT'S RULING (the per-day PRICE gate): gate 1 proves volume; nothing
> proved price per day -- 1,963 stored days at 0.1x-5x the traded price passed the
> battery (REVIEW_5B Q1). Therefore GATE 1P joins CONTEXT 4.5's battery
> permanently: for every stored symbol-day, the un-adjusted 1-minute fold interval
> [low, high] must sit INSIDE the raw bhavcopy interval [daily_low, daily_high]
> with tolerance max(2 paise, 0.1% of the raw price) per side; a day with no raw
> daily row cannot be price-proven and FAILS (closes REVIEW_5B Q4's 178 days). A
> day failing 1P is EXCLUDED and COUNTED under its own reason. Second: the
> mechanism is per-side vendor splices -- price and volume applied back to
> DIFFERENT dates for the same event. The floor model gains per-side floors
> (floor_price, floor_volume per event), measured by the same bisection under the
> same guards, hunts SIGNATURE-GATED by gate-1P failure clusters at era/event
> boundaries. ONE bounded recovery pass is licensed for the flagged days;
> acceptance = the era's days pass BOTH per-day gates; after this pass the data
> era FREEZES -- anything still flagged is a disclosed residual, not chased."

**EXECUTED by the chunk-5B FIX-5 session (2026-07-28).** Every clause is code with a test behind
it, in `src/acumen/quality_gates.py` (the gate itself, PURE), `src/acumen/vendor_adjustment.py`
(the per-side floor model + the store-backed classifier) and `src/acumen/universe_backfill.py`
(the wiring, the signature and the recovery pass).

- **GATE 1P, in the battery permanently** (`quality_gates.price_containment_gate`). For one stored
  symbol-day it takes the 1-minute fold `[low, high]` and the RAW bhavcopy `[daily_low,
  daily_high]` and requires the fold interval to sit INSIDE the raw interval, per side, within
  `max(2 paise, 0.1% x raw)` -- the SAME oracle `vendor_adjustment._day_price_contained` already
  applies to a probe day, with the same two constants, re-expressed for a stored day. It is
  INSIDE, not "equal": a fold high ABOVE the daily high is impossible (the exchange's high is the
  maximum of every trade, including the ones the continuous 1-minute series omits) while a fold
  high BELOW it is ordinary -- an auction or block print the bhavcopy counts and the continuous
  series never held. That asymmetry is why the gate is a containment and not a two-sided equality,
  and it is what lets a legitimate auction-print day PASS.
- **No raw daily row -> FAIL, under its own reason.** The ruling's own words, and it closes
  REVIEW_5B's finding Q4: the 178 stored days with no bhavcopy row were in neither the numerator
  nor the denominator. They are now GATED (`gate1p_total` counts them) and FAIL, so every stored
  symbol-day sits in exactly one bucket.
- **EXCLUDED and COUNTED under its own reason** (CONTEXT 7-E3). `REASON_GATE1P` is a distinct
  exclusion reason in the run's tally, the ledger row, the report's exclusion table and the
  coverage arithmetic; a gate-1P failure is never folded into gate 1's count.
- **PER-SIDE FLOORS** (`EventFloor.floor_price` / `floor_volume`). One event now carries two
  measured splice dates instead of one, because the vendor's archive was spliced per side: below
  `floor_price` the event is absent from the day's PRICE chain, below `floor_volume` from its
  VOLUME chain, and the two are independent. `AdjustmentMap.factors_for_day` drops each side
  separately. A pre-FIX-5 floor read back from disk sets BOTH sides to its single `floor_date`,
  so every map committed before this ruling behaves exactly as it did.
- **The same bisection, under the same guards.** `binary_search_floor` is untouched; each side
  gets its own run of it with its own classifier -- price containment for the price side, gate-1's
  unwidened band for the volume side -- and the same `MAX_FLOOR_PROBES`, the same
  `MAX_UNDECIDED_STEPS`, the same three-probe `absent_throughout` rule, the same "one `event-in`
  or one `undecided` leaves it UNRESOLVED".
- **The classifier reads the STORE, and spends no probe.** Recorded as decision B143 rather than
  assumed: the ruling's own closing sentence is that both sides of the check are LOCAL, and the
  observable a probe buys is `fetched/raw`, which the store already holds exactly --
  `stored = fetched / k_applied`, so `event-in` is "the stored day is contained in raw" (gate 1P
  itself) and `event-out` is "the stored day multiplied BACK by the event's own factor is
  contained in raw". Identical arithmetic, identical tolerance, zero credentialed calls, and it is
  reproducible offline by anyone holding the two stores.
- **SIGNATURE-GATED by gate-1P failure clusters** (`cluster_prefix` + `gate1p_cluster_events`,
  PURE). A third admitting signature beside the gate-3 raw-gap and the era cliff, using the same
  two constants (`FLOOR_HUNT_ERA_CLIFF_RATE` 95% over at least `MIN_CLIFF_DAYS` 20 days) on the
  PRICE gate instead of the volume one -- and measured as a STEP rather than as a whole-span rate,
  because a splice sitting INSIDE an era leaves a contiguous BLOCK of failures at the old end of
  the span with a clean remainder above it, not a uniformly failing span. NMDC is why: its
  clustered era fails 135 of 244 days, which is 55% on a whole-span reading and a perfect step at
  133. A block that covers the whole span is exactly the FIX-4 cliff, so the two signatures agree
  where they overlap. Never blanket: an event with no cluster is not hunted for a per-side floor,
  and an UN-PROVABLE era admits nothing at all -- it commits no chain, so there is no factor to
  drop and no floor could change one stored price.
- **ONE bounded recovery pass, then the FREEZE.** The pass ran once, offline, over the flagged
  population; its results are in the CHUNK 5B FIX-5 REPORT and `docs/backfill_minute_report.md`
  section 3f. Acceptance is the ruling's own -- the days must pass BOTH per-day gates -- and it is
  evaluated as a DRY RUN before anything is written: the stored days are rescaled arithmetically
  by `k_before / k_after` and re-gated, and a floor is committed only if MORE days then pass both
  gates and no fewer pass gate 1. A floor that does not earn its keep is recorded with its full
  measurement and DISCARDED; it never reaches the store, so there is nothing to revert. Everything
  still flagged after the pass is in the disclosed-residual register and is not chased. **The data
  era is FROZEN.**

**ARCHITECT'S RULING (chunk 5B definition of done), relayed to the chunk-5B RE-REVIEW session
(2026-07-29), verbatim as a closing addendum to Q-14:**

> "ARCHITECT'S RULING (chunk 5B definition of done): the DoD is judged against the
> gate battery AS IT NOW STANDS (gate 1 + gate 2 + gate 1P): reading G, 411,690 /
> 434,769 = 94.6917% — NOT MET by 1,341 days. The shortfall is formally ACCEPTED and
> the chunk closes with it: (i) under the battery the target was written against,
> coverage is 95.2162% (reading C) — the miss is created by the battery's
> strengthening, not by data regression; (ii) the freeze holds — recovering 0.31pp
> would mean chasing un-provable eras the final ruling licensed as disclosed
> residuals; (iii) every excluded day is categorized in the residual register chunk 9
> carries. The 95% line itself is unchanged for any future data work."

---

## ROUND-3 FINAL RECEIPTS (29-Jul-2026) · recorded by the chunk-7 prep session

The trader's remaining Round-3 answers landed with CONTEXT **v1.3**. Each is recorded here as a
receipt in the same form the 25-Jul receipts use: what arrived, what it RESOLVES, and what this
session executed for it. The CONTEXT edits and its §9/§10 bumps are the architect's and are
already in v1.3 (commit `c941c64`); this session records the receipts and executes the code,
fixture and ledger changes each one authorises.

**Nothing in this section is a new question.** The one genuine hole this session found is raised
separately as **Q-15**, below.

### R3F-a · the F9 bias table CONFIRMED -> the chunk-4 TRADER GATE is CLOSED

> "Bias table: confirmed -- that is what I would have called on each of those days."

The chunk-4 evidence pack (`docs/gate_chunk4_bias_evidence.md`, 15 real TCS days in plain
English) came back CONFIRMED. plan.md §2's first trader gate is **CLOSED**, well inside its
deadline (before the chunk-9 run). Executed this session: STATUS.md chunk 4 becomes
`reviewed-PASS · gate-closed(docs/gate_chunk4_bias_evidence.md -- trader CONFIRMED, Round 3)`.
No number in the pack moved; the pack is the evidence and it is unchanged.

### R3F-b · Q38 + Q39 -> **OPEN-4 RESOLVED** (the tie candle's colour is irrelevant)

> "Q38/Q39 (Round 3): the colour of that one-minute candle does not matter. Red, green or a
> doji -- I look at where the DAY closed against the previous day's body."

This **OVERTURNS** both assumptions the chunk-4 build carried and flagged (PROGRESS decision B59,
recorded in the 25-Jul receipt R3-e): the green mirror (assumed BEARISH) and the doji carry
(assumed no-decision). CONTEXT v1.3 §3.2 rewrites the tie predicate accordingly -- resolve on the
DAILY close against the body, with bullish precedence:
`C.close >= bodyMin` -> BULLISH, else `C.close <= bodyMax` -> BEARISH. The bearish branch is
unreachable for a close INSIDE the body (bullish precedence takes it) and a close OUTSIDE the body
was already decided by Rule 1, which is why the trader's own worked example -- body 2010-2040,
daily close 2020 -> BULLISH -- now holds for all three colours.

**EXECUTED this session** (the code change the architect scheduled for chunk-7 prep):
`src/acumen/bias.py` drops the 1-minute candle's direction from the tie predicate entirely --
`_rule_3_tie` no longer reads `minute.open` or `minute.close`, the three colour-keyed rule tags
collapse into one (`RULE_3_TIE`), and the F5 fixture becomes the three sub-fixtures CONTEXT v1.3
§8 now names (RED, GREEN and DOJI decisive candles, all -> BULLISH at `C.close` 2020). Two frozen
1-minute fixtures were ADDED for the green and doji sub-fixtures under that §8 change
(`tests/fixtures/minute/SYNTH_2099-01-07_1min.csv`, `..._2099-01-08_1min.csv`); the existing RED
fixture is byte-unchanged. F9's 15 REAL TCS days are untouched and still green -- none of them is
a tie day, which is exactly why the tie needed a synthetic fixture in the first place.

### R3F-c · Q40 option d -> **OPEN-6 and OPEN-7 RESOLVED** (take all, and disclose)

> "Q40 (Round 3): d -- no limits, show me the honest numbers."

No capital constraint and no concurrency cap: the backtest takes ALL signals across all stocks,
each sized by the fixed-rupee-risk rule, on ONE equity curve in trade-close order. The report owes
the disclosures CONTEXT v1.3 §3.5 now enumerates -- max concurrent positions, max aggregate
notional vs Rs 1L, the full distribution of daily concurrent-trade counts, AND per-trade flags
marking the trades his capital could not actually have taken (notional > Rs 1L cash; > Rs 5L
typical-MIS tiers). Nothing to execute in chunk 7 (the signal engine emits one stock-day at a
time and knows nothing about a portfolio); this receipt is the record chunks 8/9/10 build to.

### R3F-d · Q41 option A -> **Q-9 and OPEN-3 RESOLVED** (the first distinct close SETS the side ONLY)

> "Q41 (Round 3): A -- that first candle only tells me which side I am playing. I still wait for
> the entry."

The above-branch of the `reference == POC` start (raised as **Q-9** in the 25-Jul receipts, R3-d,
with the conservative interim "log + no-trade") is answered, and the interim is now WRONG rather
than merely cautious: on a bullish day, `reference == POC` -> wait; the first 15-minute candle
that closes strictly ABOVE the POC sets the side and puts the day in **WAIT-BELOW** (the Entry-2
path -- it is never itself the entry), and the first that closes strictly BELOW sets the side and
ARMS the day directly. Bearish mirrors 1:1. **Q-9 is CLOSED and OPEN-3 is CLOSED**; CONTEXT v1.3
§3.4 carries the rule.

**EXECUTED this session:** built as specified in `src/acumen/signals.py` (state `side-unset`,
with the two golden days the chunk-7 card asks for and their short mirrors). The old OPEN-3
"logged, no trade" fixture the chunk-7 card names is therefore built INVERTED -- the day now
trades -- and its test docstring quotes this receipt, the same discipline decision B121 used when
the E4 amendment retired a card fixture.

### R3F-e · Q42 -> **Q-8 RESOLVED** (the profile window is the 8-candle window)

> "Q42 (Round 3): the box is the first two hours -- 9:15 to 11:15. Eight candles."

**Q-8 is CLOSED.** The 9-candle reading of the screenshot's bar coordinates (#1 150, #2 158) is
dead; the spec's window -- 1-minute stamps 09:15..11:14, i.e. the eight 15-minute bars closing
09:30..11:15 -- is confirmed by the trader and is what chunk 6 already computes everywhere
(`poc.SPEC_WINDOW`). Nothing to change in `poc.py`: the interim WAS the spec. The 9-candle
`ALTERNATE_WINDOW` stays where it is, reachable only from the evidence generator, as the record of
how the question was settled.

Consequence for chunk 7, recorded because it is load-bearing: the §3.4 reference candle (the
15-minute candle closing at 11:15) is by construction the LAST candle of the confirmed profile
window. `signals.py` derives its reference stamp from the same session grid and a test pins the
two against each other, so the window and the reference cannot drift apart.

### R3F-f · the BHARTIARTL chart oracle -> **Q-13 RESOLVED** (keep the FINER profile)

> "BHARTIARTL 17-Jul: POC reads about 1913.9, and I count 25 rows in the box."

The reading the chunk-6 review asked for (REVIEW_6 finding Q1: one chart with the rows countable
answers Q42 and Q-13 together) arrived, and it answers Q-13 on the ROW COUNT, not on the price:

| candidate (8-candle window) | POC | rows drawn | distance from his reading |
|---|---|---|---|
| **finer profile (the interim)** | 1914.60 | **26** | price 0.70 · rows **1** |
| coarser profile | 1914.65 | 22 | price 0.75 · rows **3** |

**The price is INCONCLUSIVE** -- 1913.9 sits 0.70/0.75 from the two candidates, which are only
Rs 0.05 apart, and that gap is inside the feed-noise band CONTEXT §5 already documents for the
calibration set (residuals Rs 0.05-Rs 3.5). **The ROW COUNT is decisive**: his 25 is ONE row from
the finer profile's 26 and THREE from the coarser profile's 22. Every other line of evidence the
interim rested on points the same way (all 25 frozen `poc_prorata` values reproduced to 4e-13,
the coarser direction moving six of them, and TradingView's own documented non-tie example landing
finer). **Q-13 is CLOSED at the finer profile**, which is what CONTEXT v1.3 §3.3 now states as a
RULING rather than an interim, and what `poc.ticks_per_row` already implements and pins.

Two riders the architect kept in v1.3, recorded so a later session does not read Q-13 as fully
retired: `totalTicks`' rounding MODE stays **half-even as a pinned interim** with its verification
slot in the chunk-12 pack (REVIEW_6 finding Q2 measured it at 10 POC-moving days per 2,418), and
**N = 24 is trader-confirmed**. Neither blocks anything.

### R3F-g · the chunk-6 TRADER GATE is CLOSED

Q42 (the window) and the row-count oracle (the tie) are together what
`docs/gate_chunk6_poc_evidence.md` was built to ask. plan.md §2's second trader gate is
**CLOSED**, inside its deadline. Executed this session: STATUS.md chunk 6 becomes
`reviewed-PASS · gate-closed(docs/gate_chunk6_poc_evidence.md -- Q42 + row-count oracle)`. The
pack itself is unchanged -- every number in it was independently re-derived by the chunk-6 review
and none of them moved.

### Bookkeeping executed with these receipts

* **Q-14** (the per-day PRICE gate) is relabelled from `OPEN -- STOP · BLOCKS chunk 9` to
  **RESOLVED**. Its ruling was recorded verbatim, executed by chunk-5B FIX-5 and confirmed by a
  fresh re-review (REVIEW_5B_2, PASS); the architect's closing addendum accepted the definition of
  done. Chunk 7 is the first session to consume the ruling downstream (its orchestration recomputes
  gate 1P per stock-day, CONTEXT v1.3 §4.6), and this file's own rule is that the session which
  consumes an answer marks the item closed. **No text inside Q-14 was altered** -- only the status
  line of its heading.
* **Q-8**, **Q-9** and **Q-13** are marked RESOLVED at their own headings, each pointing here.

---

## Q-15 · chunk 7 · class A · **RESOLVED — ruled (a) and executed, chunk-7 fix (2026-07-29)** · was BLOCKING one assertion of fixtures F1 and F2

**Question.** CONTEXT §8's F1 and F2 pin `POC 2030, entry 2037, SL 2032 (risk 5), TP 2052`.
CONTEXT §3.4 defines a **gap entry** as "entry candle's low > POC" and gives it a DIFFERENT stop:
"the last traded price before the jump = the previous 15-min candle's close". On a long day the
only candle that produces `SL 2032` from the NORMAL rule is one whose low IS 2032 -- and
`2032 > 2030`, so §3.4 routes that very candle to the gap branch instead. **The four numbers in
F1 and F2 cannot all be true at the same time as §3.4's gap predicate.** Which gives way?

**Why it is a hole, and not a thing a session may pick.** It is a conflict between two sections of
CONTEXT.md, which §10 says is the architect's to resolve ("any conflict -> QUESTIONS.md, architect
resolves with trader"), and it moves real money: on the F1 day the two readings give a stop of
2032 (risk 5) or 2029 (risk 8), i.e. **200 shares vs 125** at the Rs 1,000 fixed risk, and a
target of 2052 or 2061.

**The arithmetic, in full, so the architect can rule without re-deriving it.** For the entry candle
E to be a trigger at all, the state must be ARMED when E closes. Every candle between the arming
candle and E closes at or below the POC (a close strictly above it while ARMED IS the trigger, so
no such candle can precede E), and the arming candle itself closes strictly below the POC. The
"previous 15-minute candle" is therefore always at or below the POC, so **the gap branch can only
ever produce a stop <= POC = 2030, hence a risk >= 7** -- never F1's 5. The single exception is a
day where the 11:00-stamped reference candle is missing and the E10 fallback supplies the
reference, which leaves the preceding candle unconstrained; that is not what F1 or F2 describe.

Equivalently: **F1's and F2's four numbers are jointly satisfiable if and only if the entry
candle's low is NOT above the POC**, i.e. if and only if the POC is at or above 2032.

**Options for the architect** (either is a complete answer; this session decides neither):

(a) **F1/F2's POC moves** to the value that makes the trader's own triple consistent (any POC in
`[2032, 2037)`; 2032 is the natural one -- the entry candle's low sits ON the POC, which is
precisely the boundary at which §3.4's strict `low > POC` does not fire). §3.4 is untouched, the
gap rule keeps its single clean witness in F4, and F1/F2 keep `entry 2037 / SL 2032 / TP 2052`
exactly.

(b) **The gap predicate narrows** -- e.g. to "the entry candle's low is above the POC **and above
the previous candle's high**", i.e. an actual discontinuity in the tape rather than any candle that
merely never traded down to the POC. Then F1/F2 keep POC 2030 and take the NORMAL stop, and F4
(prior close 2028, gap candle low 2034, i.e. a true jump ACROSS the POC) still takes the gap stop.
This is a CHANGE to §3.4 and needs the trader, because it is his rule.

**What this session did meanwhile (no silent decision).** The engine implements **§3.4 exactly as
written** -- `low > POC` is the gap predicate, with no added condition -- because §3.4 is the
operative rule statement and inventing a narrower one would be exactly the assumption CLAUDE.md
rule 1 forbids. F1 and F2 are then built **BOTH ways**, so whichever the architect rules is already
a passing golden and the other is already a recorded measurement:

* `test_f1_at_context_8_poc_2030_...` / `test_f2_at_context_8_poc_2030_...` -- CONTEXT §8's POC,
  asserting what §8 pins that the conflict does not touch (the POC, the state at 11:15, the arming
  close, the trigger candle and `entry 2037`) plus the stop and target §3.4's gap branch actually
  produces;
* `test_f1_reproduces_context_8_entry_sl_tp_exactly_...` /
  `test_f2_reproduces_context_8_entry_sl_tp_exactly_...` -- option (a)'s POC, asserting §8's
  `entry 2037 / SL 2032 (risk 5) / TP 2052` to the paisa.

**No fixture expected value was edited or weakened**, and F3 and F4 are unaffected (F3 carries no
POC in §8 and is built at a POC that makes its own triple exact; F4 IS the gap fixture and
reproduces `SL 2028 / TP 2084` exactly). If the architect rules (b), the second pair of tests
becomes the F1/F2 goldens under a corrected engine and the first pair is deleted; if (a), the
first pair is deleted and §8's F1/F2 rows gain their POC. Either way nothing is re-measured.

**ARCHITECT'S RULING (relayed to the chunk-7 fix session, 2026-07-29), verbatim:**

> "ARCHITECT'S RULING (option a): F1/F2's illustrative POC moves to 2032; CONTEXT 3.4 is
> untouched. Rationale: option (b) would change the trader's own rule; option (a) changes only
> an example parameter while preserving every number the trader ever stated (entry 2037, SL
> 2032, risk 5, TP 2052) and every rule he ever gave. Precedence (CONTEXT 10: later answers
> correct earlier text): his R1-Q13/R2-Q33 gap formalization ('never trades AT the POC price at
> all') supersedes the PDF's loosely chosen 2030. The result teaches the boundary: with POC 2032
> the entry candle's low TOUCHES the POC exactly → low > POC is FALSE → NORMAL branch → SL = low
> = 2032. F4 remains the gap witness. Q-15 RESOLVED."

**RESOLVED — executed by the chunk-7 fix session (2026-07-29).** The ruling touches an example
parameter and a designation, nothing else:

- **CONTEXT v1.4** (architect-authored text, applied by this session exactly as supplied): §8's
  F1 and F2 rows now read POC **2032**, and §10 carries the v1.4 log entry. §3.4 is UNCHANGED —
  `low > POC` remains the gap predicate, with no added condition, which is what the engine
  already implements. No engine line changed under this ruling.
- **The golden is now the POC-2032 parametrization** of F1 and F2 (`test_f1_golden_...` /
  `test_f2_golden_...` in `tests/test_signals.py`, docstrings citing this ruling): CONTEXT §8's
  `entry 2037 / SL 2032 (risk 5) / TP 2052` reproduces to the paisa, by the NORMAL branch,
  because the entry candle's low TOUCHES the POC and `low > POC` is therefore FALSE — the
  boundary the ruling says the fixture now teaches.
- **The POC-2030 parametrization is KEPT, relabelled a MEASUREMENT** (`test_measurement_...`),
  not deleted — which is where execution departs from this item's own closing sentence above.
  It measures the same candles on the gap branch: prior-close stop, and the risk floor this item
  derived (`>= 7`, since while ARMED every close is at or below the POC) is now asserted as a
  property rather than left as prose. It is no longer a golden and no longer claims to be
  CONTEXT §8.
- **Nothing was re-measured.** Every expected value in both pairs is the one the build session
  hand-computed; no fixture byte changed (`tests/fixtures/`, `poc/data/` untouched). F3 and F4
  are unaffected, and **F4 remains the single gap witness**, exactly as the ruling states.

---

## PLAN AMENDMENT (class C, architect-authored) · chunk 9 SPLITS into 9A + 9B · recorded 2026-07-29 by the chunk-9A build session

The architect amended plan.md's chunk-9 card in this session's card. Recorded here VERBATIM,
as every ruling in this file is; the build session authored none of it:

> "Chunk 9 splits: 9A = runner, ledger, portfolio layer, pilot proof (no trader dependency);
> 9B = the full-history run + report, gated on the trader's Round-4 answers (Q43 capital figure
> for the Q40-d flags; Q44 confirmation). Architect, 29-Jul-2026."

**What this session executed under it.** One line appended to plan.md's chunk-9 card recording
the split and citing this ruling (plan.md is architect-owned -- the line is the architect's
text, added on the architect's instruction, and nothing else in the file was touched);
STATUS.md gains a `chunk 9A` line; the chunk-9A scope is the runner, the run ledger + manifest,
the portfolio layer and the pilot evidence pack, and NOTHING of 9B -- no full-history run, no
report, and no capital-infeasibility flag VALUES.

**Two Round-4 items are therefore open with the trader, and the code is built to wait for
them rather than to guess:**

- **Q43** -- which capital figure the Q40-d capital-infeasibility flags must use. `config.yaml`
  carries `capital_reference` and `margin_basis` as OPTIONAL keys, both NULL. While either is
  null `acumen.portfolio.capital_flags` computes NOTHING and every output prints, verbatim:
  "capital-infeasibility flags NOT computed -- the trader's Q43 answer is pending". There is no
  default anywhere in the module -- not even CONTEXT 3.5's own 1,00,000 capital line, because
  the question the architect put to him is precisely which figure the FLAGS should use.
- **Q44** -- the confirmation 9B is gated on.

**One shape question rides along with Q43, non-blocking** (no flag value depends on it until
the answer arrives): this session modelled `capital_reference` as a rupee amount and
`margin_basis` as a MULTIPLE of it (CONTEXT 3.5's own example is 1,00,000 cash vs a 5,00,000
typical-MIS tier, i.e. `margin_basis: 5`), recorded as decision B182. If the trader's answer
arrives in a different shape -- absolute tier amounts, or several tiers -- the architect should
say so with the Q43 ruling and 9B adjusts the two keys before computing any flag.

---

## Q-16 · chunk 9A · class A · **RESOLVED — executed by the chunk-9A fix session (2026-07-30)** · was BLOCKING two CONTEXT 7-E13 metrics (nothing else)

**Question.** CONTEXT 7-E13 is "one authoritative list so the metrics chunk needs no external
PDF". Two of its entries name a metric without fixing a convention, and neither convention can
be derived from anything else in CONTEXT.md:

**(a) "outliers".** E13 lists `largest win/loss (INR and % and as % of gross), outliers`. No
threshold, no rule, no reference. TradingView's own report computes outliers by an
interquartile-range rule, but that rule is nowhere in CONTEXT.md and this repo may not import a
number from a product it cannot read. What defines an outlier trade -- and is the report to
show a COUNT, a list, or a set of metrics recomputed with outliers removed (TV shows the last)?

**(b) the intra-trade / intrabar drawdown and run-up.** E13 asks for "max drawdown (equity
close-to-close AND intra-trade/intrabar) with durations; run-ups (same forms)". The
close-to-close form is unambiguous and is computed. The intra-trade form needs an intraday
equity PATH, and a take-all portfolio (Round-3 Q40-d: every signal, all stocks, concurrently)
does not have an observable one: the ledger holds each trade's MFE and MAE but not WHEN inside
the day each occurred, and up to five trades ran concurrently even in the five-symbol pilot. A
day's true worst equity lies somewhere between "the worst excursions all coincided" and "they
never overlapped", and the ledger cannot say where.

**Why it matters.** Both are REPORT numbers the trader will read. (a) decides whether a
headline metric appears at all and, if TV's convention is adopted, changes every OTHER metric
in the "outliers removed" column. (b) is a drawdown figure -- on the pilot the provisional
construction gives Rs 18,844.65 against the close-to-close Rs 12,761.75, a 48% difference on
the number a trader judges risk by.

**What this session did meanwhile (STOP, no silent decision).**

- **(a) is NOT COMPUTED.** `acumen.portfolio.Metrics.outliers` is `None` and carries the reason
  in `outliers_note`; the evidence pack prints the sentence and no number. A test asserts the
  pack never prints an outlier count.
- **(b) IS computed but LABELLED PROVISIONAL everywhere it appears**, under one explicitly
  stated construction: the day's low equity is the previous close plus the sum of that day's
  MAEs minus that day's costs (and the high is the mirror with MFEs) -- i.e. every same-day
  excursion assumed to coincide, the worst case for a drawdown and the best case for a run-up.
  The constant `acumen.portfolio.INTRA_TRADE_PROVISIONAL` carries that sentence and is printed
  beside every such figure. Nothing downstream consumes it yet.

**Options for the architect (this session decides neither):**
(a1) adopt TV's IQR rule, stated in CONTEXT.md with its own arithmetic; (a2) define outliers
some other way (e.g. |PnL| beyond N x the average); (a3) drop the metric from E13 as
undefinable without the trader's own reading of it.
(b1) keep the provisional worst-case construction and state it in E13 as the convention;
(b2) define the intraday path some other way (e.g. excursions spread pro-rata across the day);
(b3) report the intra-trade form PER TRADE only (max single-trade MAE / MFE, which the ledger
does hold exactly) and drop the portfolio-level intrabar drawdown.

**What is blocked:** exactly these two metric entries, in chunk 9A's portfolio layer and in
chunk 10's metrics layer. Every other E13 entry is computed and hand-checked against a fixture.
The chunk-9B report must not print either figure as final until this is ruled.

**ARCHITECT'S RULINGS (30-Jul-2026), relayed to the chunk-9A fix session, recorded VERBATIM:**

> "ARCHITECT'S RULINGS (30-Jul-2026), closing Q-16 and REVIEW_9A Q1/Q2/Q4/Q6/Q7:
>  Q-16(a): outliers = trades whose net PnL falls outside [Q1 − 1.5×IQR, Q3 +
>  1.5×IQR] over all executed trades' net PnL (Tukey fences); report count, summed
>  net PnL, share of gross profit/loss, definition printed beside the number.
>  Q-16(b): the worst-case coincidence construction is RETIRED — it invents
>  co-timing, an assumption. Intra-trade drawdown/run-up compute on the TRUE
>  portfolio equity path at 15-minute resolution: every open position marked to its
>  15-min candle closes (exit candles at their exit levels), summed across
>  positions; drawdown/run-up on that path; one disclosed limit: intra-candle
>  excursions are not represented (per-trade MFE/MAE carry those). Both close-close
>  daily and 15-min-path figures reported. Nothing PROVISIONAL survives.
>  E13 PRESENTATION BASIS: single basis, NET of the ₹100/trade cost, throughout —
>  TradingView semantics, which is what E13 mimics. Winners/losers by NET sign, one
>  population everywhere; gross profit / gross loss / profit factor computed over
>  the NET-basis populations from net figures; every average, ratio, largest-win
>  line and percentage on NET (percent-of-notional = net/notional; share-of-profit
>  = net/net-basis gross profit). Before-costs totals may appear ONCE, labelled
>  'before ₹100/trade costs', nowhere else. The pack carries a definitions block
>  stating: basis, population, drawdown/run-up denominators (running peak/trough
>  seeded at opening capital), CAGR span convention (endpoint difference / 365).
>  Q-16 RESOLVED. Architect."

**RESOLVED — executed by the chunk-9A fix session (2026-07-30).** Every clause is code with a
test behind it; the hand-computed fixtures were written BEFORE the code, as this repo requires.

- **(a) Tukey fences.** `acumen.portfolio.outliers(rows)` returns an `Outliers` record over the
  net PnL of every EXECUTED trade: the two quartiles, the IQR, both fences, the count, the
  summed net PnL of the outlying trades, and their share of the (net-basis) gross profit and
  gross loss. `Metrics.outliers` is that record and `Metrics.outliers_note` now carries the
  DEFINITION — the fence arithmetic, the population, and the quartile estimator — so the number
  never appears without the rule that produced it. The estimator itself is the one thing the
  ruling does not fix and is recorded as a Class-B decision (B195): **linear interpolation
  between order statistics, R/numpy type 7**, computed in exact `Fraction` arithmetic, chosen
  because it is what a reviewer reproduces with `numpy.percentile(x, [25, 75])`. `OUTLIERS_NOT_COMPUTED`
  is gone from the module.
- **(b) The TRUE 15-minute path.** The coinciding-worst-case construction, the
  `INTRA_TRADE_PROVISIONAL` constant, `EquityPoint.low_equity_paise` / `high_equity_paise` and
  the `intrabar=` switch are all DELETED — nothing labelled PROVISIONAL survives anywhere in
  `src/`, `tests/` or the pack. In their place: `acumen.backtest.assemble_trade_paths` (I/O
  layer — it is the layer that holds the candles) marks every executed trade at each 15-minute
  candle close it was held, with the exit candle carried at its EXIT LEVEL rather than its
  close; `acumen.portfolio.intraday_equity_path` (PURE) sums those marks across every open
  position onto the running equity, and `path_max_drawdown` / `path_max_run_up` measure the
  excursion on that path with the running extreme seeded at the opening capital. The round-trip
  cost is charged at the entry mark (B194), which makes the path continuous into the realized
  net at the exit mark and makes each day's last path point equal that day's closing equity —
  asserted as an invariant. The disclosed limit is printed beside the figure in the same words
  the ruling uses: intra-candle excursions are not represented; per-trade MFE/MAE carry those.
- **E13 presentation basis.** One population everywhere, keyed on the sign of NET. `gross_profit`
  and `gross_loss` are now sums of NET PnL over the net-winners and net-losers, so
  `winners x avg profit == gross profit` is an identity a reader can check — and it is asserted
  as one. Profit factor, both largest-win/loss lines and every percentage follow the same basis.
  The before-costs totals appear exactly ONCE in the pack, on one line labelled "before
  Rs 100/trade costs", and nowhere else. The pack gained the **definitions block** the ruling
  names (section 7a), stating the basis, the population, the drawdown/run-up denominators, the
  CAGR span convention and the outlier rule — which closes REVIEW_9A Q1, Q2, Q4, Q6 and Q7 as
  well.

---

## GO RULING · chunk 9B · architect, 31-Jul-2026 (operator-confirmed) · Q43/Q44 no longer BLOCK the run

Recorded VERBATIM by the chunk-9B PREP session, as every ruling in this file is; this session
authored none of it. It supersedes, for the RUN only, the blocking half of the 29-Jul-2026 plan
amendment above ("9B = the full-history run + report, gated on the trader's Round-4 answers").
The two questions themselves stay OPEN with the trader — what changes is that the run no longer
waits on them, under four conditions.

> "GO RULING (31-Jul-2026, operator-confirmed): chunk 9B proceeds WITHOUT the
> trader's Q43/Q44 answers. Conditions: (1) every report output carries
> 'capital-infeasibility flags NOT computed — trader's Q43 answer pending'; flags
> compute post-hoc from the ledger the day the answer arrives. (2) The run manifest
> is stamped 'PENDING TRADER CONFIRMATION OF Q44 (gap-rule example, POC 2032)';
> if the trader's answer surprises, that is a §3.4 change → spec version bump →
> full re-run; the superseded ledger is retained, labelled, never deleted.
> (3) Q4 of REVIEW_9A_2: the outlier zero-branch prints all four quantities (count
> 0, summed net ₹0.00, both shares 0%) — one format on both branches. (4) Session
> records use commit-time dates (REVIEW_9A_2 Q5). Architect."

**What the PREP session executed under it** (each item is code with a test behind it):

- **Condition (1).** Already in force and unchanged: `acumen.backtest.CAPITAL_FLAGS_PENDING_NOTE`
  and `acumen.portfolio.CAPITAL_FLAGS_PENDING_NOTE` both read, verbatim,
  `"capital-infeasibility flags NOT computed -- the trader's Q43 answer is pending"`, the
  sentence recorded under the plan amendment above and asserted in the pilot pack, in every
  manifest and in the portfolio layer's own flag record. **This session did NOT reword that
  constant to the ruling's shorter phrasing.** The two say the same thing; the repo's sentence
  is the one already recorded verbatim in this file, already printed in a committed evidence
  pack and already pinned by tests, and rewording it would move committed pack text for no
  gain in meaning. Recorded here so the difference is a decision on the record rather than an
  oversight — if the architect wants the ruling's exact phrasing instead, it is a one-line
  change plus a pack regeneration.
- **Condition (2).** `acumen.run_backtest.Q44_PENDING_STAMP` carries the ruling's sentence
  verbatim and the run CLI writes BOTH disclosures into the run manifest's own `disclosures`
  block (with the retention rule beside them, so the manifest states what happens if the answer
  surprises). The stamp is passed by the RUN, not baked into `build_manifest`, so no chunk-9A
  artefact and no committed manifest digest moves.
- **Condition (3).** `acumen.pilot_evidence._outlier_line` now prints ONE format on both
  branches: count, summed net PnL, and both tails with their fences, amounts and shares —
  zeros printed as zeros. Closes REVIEW_9A_2 finding Q4.
- **Condition (4).** Every session record in this session (PROGRESS entry stamp, STATUS line,
  the dates cited in commit bodies and in this block) is the COMMIT-TIME date, 31-Jul-2026.
  Closes REVIEW_9A_2 finding Q5.

**What is still open with the trader, and therefore what the run does NOT do:** no
capital-infeasibility flag VALUE is computed anywhere (Q43); `config.yaml`'s `capital_reference`
and `margin_basis` stay null and there is still no default figure in `src/`. The gap-rule
example (Q44) is unconfirmed, so the ledger the run produces is a ledger under CONTEXT v1.4 as
written — if the confirmation contradicts §3.4, the ruling's own escalation applies (spec
version bump, full re-run, superseded ledger retained and labelled, never deleted).

---

## Q-17 · chunk 9B PREP · class A · **RULED 31-Jul-2026 — the candle-level drop is CONFIRMED as spec** · did NOT block the run

> **The ruling is recorded verbatim at the end of this file (ARCHITECT'S RULINGS, 31-Jul-2026).**
> What was already executed (below) IS the ruling; it becomes CONTEXT law in the v1.5 amendment,
> and the two follow-up readings the architect was offered are NOT taken — the drop is uniform
> for pre-open and post-close strays, and no date-level widening was ruled.

**What the smoke run found.** The chunk-9B smoke (the real runner, full era, RELIANCE +
MARUTI) died on its first symbol with an unhandled exception:

```
acumen.aggregate.AggregateError: 1-minute stamp 2017-04-28T09:14:00 is outside the
09:15..15:29 session (CONTEXT 7-E2); it belongs to no 15-minute grid bar.
```

RELIANCE 2017-04-28 stores 376 one-minute bars. 375 of them are the session; ONE is stamped
**09:14** and carries 25,015 shares at a plausible price (Rs 1,409.73) -- a pre-open /
call-auction print the vendor stamped one minute early.

**The two layers disagreed, and CONTEXT 7-E2 can be read either way.** E2's own words are
"Non-standard sessions (Muhurat, special/shortened sessions) are excluded. Detection: candle
data on a date absent from the trading calendar, **or outside 09:15-15:30** -> excluded."

- `acumen.quality_gates.integrity_gate` (chunk 5B, reviewed at REVIEW_5B_2) reads that at the
  CANDLE level and says so in its own docstring: bars outside the session "are counted
  (`out_of_session`, for the report) but do NOT by themselves exclude the day: **CONTEXT 7-E2
  excludes an out-of-session candle at the CANDLE level (drop the stray bar), not at the day
  level**". So gate 2 ADMITS such a day, deliberately.
- `acumen.aggregate.aggregate_15min` (chunk 5A, reviewed) RAISES on the same bar, because a
  stamp outside the session belongs to no 15-minute bucket.
- `acumen.backtest.scan_non_standard_sessions` (chunk 9A, reviewed at REVIEW_9A) reads E2 at
  the DATE level but only for the Muhurat shape: a date is non-standard when at least one
  symbol stored candles for it and NO symbol stored a candle inside the session.

Nothing dropped the bar, so the day reached the aggregator and the run died.

**MEASURED before anything was changed** (read-only over the frozen store; generator and
output committed at `docs/evidence/chunk9b_out_of_session.{py,md}` per CLAUDE.md's evidence
rule):

- **3,099 of ~493,900 stored symbol-days (0.63%)** carry at least one stamp outside
  09:15..15:29, across **526 distinct dates** and 204 settled symbols.
- **8 of those dates are the Muhurat shape** (no symbol has an in-session bar: 2017-10-19,
  2018-11-07, 2019-10-27, 2020-11-14, 2021-11-04, 2022-10-24, 2023-11-12, 2024-11-01, all
  stamped 18:15-18:49). Chunk 9A's date-level detector already excludes these, correctly.
- **518 dates MIX** in-session and out-of-session bars -- the shape that crashed the run. They
  are of two kinds: three market-wide dates (2017-04-28, 134 symbols of 139 with data, a 09:14
  print; 2018-11-05, 134 of 153, stamps 15:30 and 15:32; 2019-10-25, 56 of 159, 15:30) and a
  long tail of per-symbol vendor noise (RECLTD 508 symbol-days, TATASTEEL 507, PIDILITIND 124,
  mostly through 2020).

**Why this session did NOT treat it as an open STOP.** The reading is already decided in this
repo's code, by a reviewed module, in writing: gate 2's candle-level drop. The only competing
reading -- widen E2's date-level exclusion to any date carrying a stray stamp -- would exclude
**518 trading dates for all 204 symbols, roughly 105,000 symbol-days**, because one vendor
mis-stamp on TATASTEEL closed the market for everyone. That is not a defensible reading of a
rule whose stated purpose is Muhurat sessions. So the fix APPLIES gate 2's ruling in the two
places that consume the day, and nothing new was decided.

**What was executed** (commit `chunk9B: an out-of-session 1-minute stamp no longer kills the
run`):

- `acumen.aggregate.in_session_bars(bars) -> (kept, dropped)`: pure, returns the count so a
  drop can never be silent. `aggregate_15min` KEEPS its refusal -- inventing a bucket for a
  stray stamp would invent a candle.
- `signal_engine.stock_day` filters before the POC engine, the 15-minute aggregation and the
  signal engine. **Gate 1, gate 1P and gate 2 still see the WHOLE stored day**, unchanged
  chunk-5B semantics: NSE's daily volume includes the pre-open auction, so the stray bar is
  part of what gate 1 reconciles against.
- `backtest.minute_store_bars` (the 15-minute path reader) applies the same drop, or the
  Q-16(b) equity path would raise on exactly the days the engine survived.
- The day's ledger row carries `FLAG_OUT_OF_SESSION_DROPPED`. It is a FLAG rather than a new
  column so that a clean day writes the bytes it always wrote and the chunk-9A pilot ledger's
  published sha256 does not move. The run prints the total at the end.

**What the architect may still want to rule** (nothing is blocked meanwhile):

1. Whether the three MARKET-WIDE dates (2017-04-28, 2018-11-05, 2019-10-25) are
   "special/shortened sessions" in E2's sense and should be excluded at the DATE level after
   all. On the candle-level reading they trade normally; 2018-11-05 and 2019-10-25 sit beside
   that year's Muhurat, which is suggestive.
2. Whether E2's date-level detector should widen from "no symbol has an in-session bar" to a
   share-of-universe test (e.g. "no symbol has a FULL session"), which would catch a shortened
   session that still traded inside the window.

Either ruling changes which days the ledger contains, so -- exactly like Q44 under the GO
ruling -- it would mean a spec version bump and a full re-run, with the superseded ledger
retained and labelled.

---

## Q-18 · chunk 9B PREP · class A · **RULED 31-Jul-2026 — option (c), rebuild and RECONCILE** · still blocks the chunk-9B RUN until the rebuild completes

> **The ruling is recorded verbatim at the end of this file (ARCHITECT'S RULINGS, 31-Jul-2026).**
> The ordered, resumable rebuild the ruling authorises is `docs/recovery/q18_runbook.md`; the
> reconciliation it requires is `docs/recovery/q18_reconcile.py` (implementation
> `src/acumen/recovery_reconcile.py`). Nothing below is retracted — it is the incident record
> the ruling answers.

**INCIDENT, 31-Jul-2026: the local `data/` and `cache/` trees were DESTROYED by this session.**
Recorded here in full because CONTEXT 4.6 declares the minute-lake era FROZEN and "sealed at
tag chunk5B-pass", and restoring it is not a decision a build session may take.

**What happened, exactly.** To verify REVIEW_9A_2 finding C3 -- that the pilot pack regenerates
byte-identically TODAY with no harness -- this session checked the pre-fix commit `6b0436d` out
into a throwaway git worktree, applied ONLY the one-line `nse_http.cached_json` change, and ran
the pack generator there. `data/` and `cache/` are gitignored, so a worktree has neither; they
were linked in with two NTFS junctions:

    <worktree>/data  -> C:\Users\chinm\acumen\data
    <worktree>/cache -> C:\Users\chinm\acumen\cache

**The verification itself succeeded** -- the regenerated pack was byte-identical to the
committed one, sha256 `9e8a77c78644d0ffabb082987f2e4f5c07a0f0dbc19fdd7569d6b9d1b724df41`, with
no harness. The cleanup did not: `git worktree remove --force` deleted the worktree
recursively, FOLLOWED BOTH JUNCTIONS, and emptied their targets.

**What is gone** (all of it gitignored by design -- CLAUDE.md: never commit `data/`, `cache/`):

| Path | What it held |
|---|---|
| `data/minute_store/` | the chunk-5B 1-minute lake: 210 symbols, 434,769 stored symbol-days, RAW prices restored through the Q-10..Q-14 un-adjustment machinery |
| `data/daily_store/` | ~25 years of bhavcopy (319 parquet + the coverage ledger the trading calendar is DERIVED from) |
| `data/nse/ca/` | the corporate-action day-cache, 2005..2026, `fetched_on` 2026-07-29 -- the one REVIEW_9A_2 C3 was about |
| `data/universe_backfill/ledger.json` | the DISCLOSED-RESIDUAL REGISTER (CONTEXT 4.6's chunk-9 duty; the 204 settled / 6 quarantined split) |
| `data/adjustment_maps/`, `ca_raw_store/`, `ca_check_store/`, `raw_bhav/` | the measured per-event per-side application floors with their probe provenance, and the raw CA sources |
| `data/backtests/` | every chunk-9A run: the pilot ledger REVIEW_9A verified at four kill points (sha256 `c3363f6f...c1e318`), its shards and manifests |
| `cache/` | `OpenAPIScripMaster_2026-07-28.json` (the per-symbol tick grid) and `scrip_master.json` |

**What SURVIVED, verified.** The tracked repository is undamaged: `git status` clean apart from
this session's own work, `git fsck` clean, all 16 `tests/fixtures/` and 28 `poc/data/` files
byte-intact, and `docs/evidence/chunk9a_pilot.md` NOT overwritten (the regeneration crashed
before writing). Every committed evidence pack, review, ledger figure and digest is still on
disk and in history. Nothing in `src/` or `tests/` was touched.

**Recovery attempted and FAILED.** Windows Recycle Bin: 333 items, zero matching store files (a
programmatic recursive delete bypasses it). Volume shadow copies: unavailable on this machine.
The two other `acumen-*` directories under the user profile are empty. There is no backup this
session can reach.

**What it blocks right now.**

1. **The chunk-9B RUN.** `docs/evidence/chunk9b_preflight.py` now correctly returns NO-GO on
   checks 3-10 and refuses to emit the run command. That is the preflight working as designed.
2. **The pilot-pack regeneration** owed by REVIEW_9A_2 Q1/Q2 and the GO ruling's condition (3).
   The RENDERER fixes are committed (`257c0ce`, `6897387`, `227de96`, `9f0105c`); the committed
   ARTEFACT still shows the old labels, and its two defect pins in
   `tests/test_review9a2_probes.py` are still green and now carry a note saying exactly why.
3. **The chunk-9B SMOKE** and therefore the MEASURED throughput and the projected full-run
   duration. The smoke DID run before the loss and earned its keep -- it found Q-17 -- but it
   crashed on that defect, so no clean end-to-end rate was ever recorded.
4. **`docs/evidence/chunk9b_out_of_session.md`**, the Q-17 measurement's own output file. The
   generator is committed; the numbers it produced are recorded verbatim in Q-17 above (they
   were measured from the intact store before the loss), but the file itself was never written.
5. Eight data-backed tests now SKIP instead of running (they already had the "data/ is
   gitignored" skip guard, so the suite is green -- but eight real checks are no longer
   exercised on this machine).

**What the architect has to decide, and why this session decided none of it.** CONTEXT 4.6
seals the data era with exact counts (434,769 stored symbol-days, 411,690 passing all three
gates, 94.6917% coverage, 204 settled / 6 quarantined, per-event floors with full provenance).
A rebuild is chunk-2 + chunk-5B work over the network and **it may not reproduce those
numbers**: the vendor's 1-minute feed is re-fetched live, its back-adjustment is era- and
event-dependent (OPEN-8 / Q-10..Q-14), and the measured application floors would be
re-measured from whatever it returns today. Re-deriving the era therefore risks breaking the
freeze rather than restoring it, and CONTEXT 4.6's own numbers -- which chunk 9B's report was
going to be qualified by -- would need re-verification or a new architect acceptance.

Options, for the architect (this session picks none):

(a) **Restore from an operator backup** if one exists off this machine -- the only path that
    preserves the freeze exactly. Nothing else does.
(b) **Rebuild and RE-SEAL**: re-run chunk 2 (bhavcopy 2000..2026), the CA cache, the instrument
    master, then chunk 5B's full-universe backfill and the Q-11/Q-14 map machinery; then a
    fresh review re-establishes the era's numbers and CONTEXT 4.6 is amended with whatever they
    now are. Expect many hours to days of wall-clock and a genuine risk the counts move.
(c) **Rebuild and REQUIRE the old numbers**: same work, but treat any divergence from CONTEXT
    4.6's sealed counts as a FAIL to be triaged rather than accepted.

**What this session did meanwhile.** Stopped. Every code deliverable of chunk 9B PREP is
committed and its tests are green from clean; every claim that needed the stores is marked
BLOCKED here and in PROGRESS.md rather than being estimated, and the run was NOT handed to the
operator, because the preflight refuses it and the preflight is right.

---

## ARCHITECT'S RULINGS (31-Jul-2026) · Q-18 and Q-17 · recorded VERBATIM by the DATA RECOVERY session

The architect's text, exactly as supplied, quoted whole and unedited. It answers **Q-18**
(class A, STOP) and closes **Q-17** (class A, recorded). Everything after this block is what
this session executed under it — the ruling itself is the quotation, and nothing in this repo
may narrow or widen it.

> "ARCHITECT'S RULINGS (31-Jul-2026). Q-18: option (c) — rebuild through the existing reviewed
> pipeline; the rebuilt era MUST be reconciled against CONTEXT 4.6's sealed numbers; every
> divergence classified {new-CA-explained, vendor-repair-explained, unexplained}; explained
> drift is accepted only via a formal CONTEXT 4.6 amendment (v1.5) listing exact deltas;
> unexplained drift is a defect to triage. Q-17: the candle-level drop is CONFIRMED as spec —
> stray out-of-session 1-min bars are dropped at the candle level, flagged and counted, never
> silently; uniform for pre-open and post-close strays; gates continue to see the whole stored
> day for volume; becomes CONTEXT law in the v1.5 amendment. Architect."

### What the DATA RECOVERY session executed under this ruling (31-Jul-2026)
<!-- Q-19, raised by this session's smoke, is recorded after this block. -->


**Q-17 — nothing to change; the ruling confirms what is already in the code.** Every clause was
already true of the fix committed at `0b47d8e`, and each one is now pinned by a test that cites
this ruling (`tests/test_aggregate.py`, `tests/test_backtest.py`):

- *dropped at the candle level* — `acumen.aggregate.in_session_bars` drops the stray bar and
  `aggregate_15min` keeps its refusal, so no bucket is ever invented for an out-of-session stamp;
- *flagged and counted, never silently* — `in_session_bars` returns the dropped COUNT, the day's
  ledger row carries `FLAG_OUT_OF_SESSION_DROPPED`, and the run prints the total at the end;
- *uniform for pre-open and post-close strays* — the filter is the session window itself
  (09:15..15:29 open-stamps, CONTEXT 7-E12), so a 09:14 stray and a 15:32 stray take the same
  path; both shapes are measured in Q-17 above (2017-04-28 is pre-open, 2018-11-05 post-close);
- *gates continue to see the whole stored day for volume* — gate 1, gate 1P and gate 2 are handed
  the unfiltered day, because NSE's daily volume includes the pre-open auction;
- *becomes CONTEXT law in the v1.5 amendment* — the architect's edit, not a session's. CONTEXT.md
  is untouched here.

The two follow-up readings Q-17 offered the architect (excluding the three market-wide dates at
the DATE level; widening E2's date-level detector to a share-of-universe test) are **NOT taken** —
the ruling confirms the candle-level drop and rules nothing else, so the 518 mixed dates trade
normally and no ledger day moves.

**Q-18 — option (c), executed as a HANDOVER, not as a rebuild.** This session builds no ingestion
logic and fetches nothing heavy: the rebuild runs through the existing reviewed pipeline, in the
operator's terminal, from `docs/recovery/q18_runbook.md` (five ordered, resumable steps, each with
its source, its credential status and its completion check). The reconciliation the ruling
REQUIRES is built and tested here — `src/acumen/recovery_reconcile.py`, launched by
`docs/recovery/q18_reconcile.py` — and it is offline, read-only, and reads its SEALED BASELINE
from the committed `docs/backfill_minute_report.md` rather than from any number typed by a
session. It classifies every divergence into the ruling's three classes and it defaults to
**unexplained**: a divergence is only ever called explained when the evidence for the explanation
is present on disk. Its verdict is one of exactly two, in the ruling's own words — *"zero
unexplained: the deltas below are the amendment payload for CONTEXT 4.6 v1.5"* or *"N unexplained
divergences: DEFECT, triage before any number is believed"* — and the amendment itself stays the
architect's to write.

---

## ARCHITECT'S TRIAGE RULINGS (01-Aug-2026) · Q-18 · recorded VERBATIM by the VERIFICATION + TRIAGE session

The first reconciliation (operator-run, 31-Jul/01-Aug-2026) returned **354 unexplained
divergences — DEFECT, triage before any number is believed**, which is the 31-Jul ruling's own
second verdict. The architect's triage rulings on that defect follow, quoted whole and
unedited. Everything after this block is what the VERIFICATION + TRIAGE session executed under
them; the rulings themselves are the quotation, and nothing in this repo may narrow or widen
them.

> "T1 SEALED-FETCH-HORIZON: for each symbol, find the unique boundary date B such
>  that the REBUILT store's day count on dates ≤ B equals the SEALED count exactly,
>  with every extra day inside (B, 2026-07-28] and B inside the sealed fetch window
>  (2026-07-20..2026-07-28). A symbol passing this test reclassifies its stored-day
>  and matching gate-count deltas to a NEW class sealed-fetch-horizon — the sealed
>  store's per-symbol horizon was earlier than its report label; not drift. A
>  symbol failing the test STAYS unexplained.
>  T2 NEW-CA TIGHTENED: new-CA-explained requires ex-date ≤ the rebuild fetch date
>  (2026-07-31). Future ex-dates explain nothing; reclassify, letting T1 catch them.
>  T3 REGRESSION FORENSICS (APLAPOLLO −467, GAIL −60, POWERGRID −23, LODHA −21):
>  for each — (a) failing dates listed by era and by gate; (b) rebuilt adjustment-
>  map events and floors diffed against every sealed-era review quote available;
>  (c) correlate with the CA-cache delta (41,351 → 41,371: name the new rows for
>  these symbols); (d) hand-verify THREE failing days per symbol against raw
>  bhavcopy, digit by digit. Outcome per symbol: a measured, era-keyed explanation
>  (class vendor-snapshot-drift — days honestly refused by the gates, disclosed)
>  or ESCALATE to the architect with the evidence. No third option. APLAPOLLO's
>  quarantine stands unless forensics clears it.
>  T4 UNIVERSE: a REBUILD uses the SEALED universe (the 210). Re-fetch EXIDEIND
>  and NUVAMA (network sanctioned for exactly these two, --symbols), full
>  pipeline, include them in the reconciliation. Today's-F&O-list applies only to
>  a deliberate, architect-signed universe refresh (CONTEXT 7-E5 clarification,
>  goes into v1.5).
>  T5 BIG IMPROVEMENTS VERIFIED: NESTLEIND (+1,002) and BSE (+84) — hand-verify
>  FIVE flipped days each against raw bhavcopy before vendor-repair is believed;
>  show the arithmetic. Architect, 01-Aug-2026."

---

## Q-19 · Q-18 DATA RECOVERY · class A · **OPEN** · NON-BLOCKING (the rebuild has a stated, executed workaround)

**Question.** A bhavcopy 404 for a date whose file is **not published yet** is, in the ledger,
indistinguishable from a 404 for a date that **had no session**. Under the Q-3 ruling only a
`confirmed-404` counts as a non-trading day — so ingesting "up to today" during or shortly after
the session silently records TODAY as a holiday. Should the downloader be allowed to call a 404
`confirmed` for a date whose bhavcopy cannot exist yet?

**This is measured, not hypothetical.** This session's runbook smoke (the ordinary chunk-2
command, `--from 2026-07-01 --to 2026-07-31 --allow-network`, run at 10:21 IST on Friday
**2026-07-31**, with the market open):

| outcome | count | which |
|---|---|---|
| `file-present` | 22 | every completed trading day 2026-07-01..2026-07-30 |
| `confirmed-404` | 9 | the 8 weekend dates — and **2026-07-31 itself**, a normal Friday |
| `error` | 0 | — |

The 31st's row reads `http_status 404`, `reason "no published bhavcopy in either format"`, and
under Q-3 that is a settled answer meaning *not a trading day*. It is not: the session was in
progress. The date was 404 in BOTH published formats, so the chunk-2 double-check that protects
the UDiFF cutover boundary does not catch it either — both formats agree, and both are simply
early.

**Why it matters.** Exactly what Q-3 was written to prevent, arriving through a door Q-3's
safeguard 1 does not cover — that safeguard says an **error** is never a holiday, and this is not
an error. CONTEXT 3.2's `bias_pair(D)` is defined on TRADING days, so one phantom holiday shifts
the (D−1, D−2) pair for the NEXT trading day too, and CONTEXT 7-E2's exclusions key off absence
from the calendar. The failure is silent and it lands on the most recent day in the store — the
one the live screener (chunk 13) and every fresh backtest reach first.

**What this session did meanwhile.** Did NOT decide, and changed no chunk-2 code or 404 semantics
— that ruling is the architect's and `bhavcopy.py` is reviewed. Instead:

1. **Un-recorded the bad row using the existing documented recovery**, `python
   scripts/backfill_daily.py --rebuild-ledger` (REVIEW_2 F6's path: rebuild the ledger from the
   surviving monthly parquets; every non-recovered date returns to *pending* and is re-attempted
   on the next run). Verified after: **22 file-present, 0 confirmed-404, 9 pending** over the
   window — the phantom holiday is gone and the 8 genuine weekend 404s will simply be re-settled
   by the rebuild's own step 1.
2. **Made it an operator rule in the runbook.** `docs/recovery/q18_runbook.md` step 1 ends at the
   **last COMPLETED trading day**, never at today, and says why. The architect's own Q-18 card
   worded step 1 as "2000→today"; this is the one place the runbook deliberately narrows it, and
   the narrowing is stated rather than assumed.

**Options for the architect:**
(a) operator discipline only — the runbook rule above, no code change (status quo);
(b) the downloader refuses to record `confirmed-404` for a date on or after the current IST date
    (or within a stated publication lag of the close) and records it as *pending* instead — a
    small, testable change in `bhavcopy.py` that makes the guard structural rather than procedural;
(c) a publication-lag value in `config.yaml` with the same effect and an operator-visible knob.

Nothing is blocked: the rebuild proceeds under (a), which is already written into the runbook.

**MEASURED ADDENDUM (VERIFICATION + TRIAGE session, 01-Aug-2026) — what workaround (a) costs,
exactly.** The rebuild ran under (a) and the price is now measurable rather than hypothetical.
Step 1 stopped at the last COMPLETED trading day, **2026-07-30**; step 4's minute lake fetched
through **2026-07-31**, which SmartAPI serves intraday. So every symbol holds one stored day
with no raw daily row to gate against, and under the Q-14 ruling ("a day with no raw daily row
is a gate-1P FAILURE, not an absence") that day fails:

| Measured, from `data/universe_backfill/ledger.json` | Value |
|---|---|
| `gate1p_no_oracle` summed over the universe | **208** |
| symbols carrying exactly one such day | **208 of 208** |
| the date, on every symbol that lists it | **2026-07-31** |

It is fully disclosed by the existing machinery — the rebuilt report's headline prints
*"Gate-1P failures with NO raw daily row (Q-14 closes REVIEW_5B Q4) | 208"* — and it costs
208 of 432,512 stored symbol-days, i.e. **0.048 pp of coverage**. It is not a defect and
nothing is blocked; it is recorded here because it is the exact, measured shape of the
mismatch this item is about, and because option (b) or (c) would remove it by construction
(the two stores would stop on the same date). The architect's ruling is still owed; this
session decided nothing.

---

## Q-20 · chunk 9B RESUME-1 · class A · **OPEN — STOP** · BLOCKS the chunk-9B RUN's tick input (RESUME-2); nothing in RESUME-1

**Question.** The instrument master is a DAILY LIVE DUMP (CONTEXT 4.3) and CONTEXT 3.3 takes
`tickSize` per symbol from it. Two snapshots are now cached on this machine and they DISAGREE
about the tick for 11 of the sealed 210. Which snapshot must a historical backtest use?

**Why it is a hole.** CONTEXT 3.3 says "per symbol from instrument master" and CONTEXT 4.3
says the master is re-pulled daily. Neither says WHICH pull a run over 2016..2026 is entitled
to read, and nothing in the spec anticipates the two disagreeing. `latest_cached_master`
resolves it by filename — newest wins — which is a session-era implementation choice, not a
ruling, and it silently decides real numbers.

**This is measured, not hypothetical** (`docs/evidence/chunk9b_master_tick_drift.{py,md}`,
offline and read-only over the two cached snapshots):

| snapshot | NSE-EQ instruments | what it is |
|---|---|---|
| `OpenAPIScripMaster_2026-07-31.json` | 2,433 | runbook step 3 — the master the Q-18 REBUILD ran under |
| `OpenAPIScripMaster_2026-08-02.json` | 2,438 | pulled by the T4 re-fetch two days later — the one `latest_cached_master` will hand the run |

| symbol | 07-31 | 08-02 | ratio | symbol | 07-31 | 08-02 | ratio |
|---|---|---|---|---|---|---|---|
| BAJAJ-AUTO | 50p | 100p | x2 | NAUKRI | 5p | 10p | x2 |
| BANKBARODA | 5p | 1p | x0.2 | PERSISTENT | 10p | 50p | x5 |
| HEROMOTOCO | 10p | 50p | x5 | SWIGGY | 1p | 5p | x5 |
| INDUSINDBK | 5p | 10p | x2 | TORNTPHARM | 10p | 50p | x5 |
| JIOFIN | 1p | 5p | x5 | KEI | 50p | 10p | x0.2 |
| LODHA | 5p | 10p | x2 | | | | |

**All 11 are SETTLED**, i.e. every one is inside the 204-symbol universe the run walks. It is
**not** a parsing or selection artefact: each master carries exactly ONE NSE `-EQ` row for each
of these symbols and simply states a different `tick_size` in it (`rows 1 / 1` on every line of
the evidence table). No token changed; no sealed symbol is absent from either snapshot.

**Why it matters.** CONTEXT 3.3 builds the profile row grid as
`totalTicks = round((top - bottom) / tick)`, so a different tick is a different grid, a
different POC, and therefore a different entry, stop and target — for the whole history of
that symbol, not just for recent days. The failure is SILENT: the code is correct either way
and returns a plausible price. This repo has already measured that exact silence once — Q-2 /
REVIEW_0 found that a wrong tick matched 15 of 25 frozen calibration days and put every DIXON
day out by Rs 0.87 to Rs 78, which is why Q-2 was ruled the way it was.

It also touches CONTEXT 6's no-drift property and the run's reproducibility: re-running the
same span two days apart would move POCs on these 11 symbols with no code change and no data
change. The manifest RECORDS the master by filename (so a ledger is at least attributable);
nothing PINS it.

**What blocks.** The chunk-9B RUN (RESUME-2) — specifically which master it reads. Nothing in
RESUME-1: this session shipped CONTEXT v1.5, the store migration and the Q-19 guard, none of
which touch tick selection, and no engine module was changed.

**What this session did meanwhile.** Did NOT choose. No code was changed:
`latest_cached_master` still resolves newest-by-filename exactly as chunk 9A reviewed it, both
snapshots were left in place untouched, and the disagreement was measured and committed as
evidence instead of being resolved. No master was fetched (this session made no network call).

**Options for the architect:**
(a) **Pin the rebuild's master.** The run reads `OpenAPIScripMaster_2026-07-31.json` — the
    snapshot the data era was built and gated under — named explicitly in config or on the run
    manifest, so the run's tick input is the era's own. Makes the run reproducible for good;
    costs a stale tick for any symbol NSE genuinely re-banded since.
(b) **Newest wins, disclosed** (status quo behaviour, ruled rather than inherited): the run
    uses the newest cached master and the manifest carries the 11-symbol delta as a disclosed
    condition, so a reader knows which symbols' grids depend on the pull date.
(c) **Freeze a tick snapshot for the sealed universe**, committed like
    `docs/recovery/sealed_universe_210.json`, with the master remaining the source for
    everything else — the Q-2 precedent (a frozen fixture for the calibration ticks) extended
    from fixtures to the run.
(d) Something else — e.g. treat a tick change as a corporate-action-style era boundary, which
    is a much larger change and is noted only for completeness.

A related fact the architect may want to weigh under any option: the vendor moved these ticks
in BOTH directions within two days (BANKBARODA 5p -> 1p while INDUSINDBK 5p -> 10p), so
"newest is most correct" is not obviously true.
