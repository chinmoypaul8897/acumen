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

### R3-c · NEW Q-8 (class A, OPEN) -> POC window length: 8-candle vs 9-candle

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

### R3-d · NEW Q-9 (class A, OPEN) -> reference == POC, the ABOVE branch

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

