# REVIEW_6 -- chunk 6 - POC engine (CONTEXT 3.3)

**Reviewer:** fresh QC session -- `personas/quant_reviewer.md` **and** `personas/code_reviewer.md`
(plan.md chunk-6 review type **QC**). Zero shared context with the builder.
**Date:** 2026-07-26 · **Span reviewed:** `8b053c2` (chunk6: poc engine) and `6ed863c` (chunk6:
correct the session test count) -- the chunk-6 commits only. The four `chunk5B-fix2` commits in
`c01d27d..6ed863c` were READ for context; they are chunk 5B's review scope and no verdict here
touches them.
**Builder entry reviewed:** PROGRESS `[2026-07-26 17:15] chunk 6 - build - done`.

## VERDICT: **PASS**

The POC is the number the trader reads off his chart, so I assumed it was wrong and tried to
prove it. It survived.

I re-derived TradingView's F6 example by hand at two tick sizes that appear in no fixture, and I
recomputed **all 25 frozen `poc_prorata` values from the `poc/data` CSVs with my own from-scratch
reading of CONTEXT 3.3** -- a separate implementation that imports nothing from `src/acumen`.
It reproduces every one of the 25 to a worst error of **4.0e-13** (the builder's claim, confirmed
to the digit), and the six days that sit on the ticks-per-row TIE are exactly the six Q-13 names.
Flipping my own tie direction to the coarser side moves exactly six of the 25 -- Q-13's interim is
a measurement, not a preference. I reproduced Q-13's BHARTIARTL statistics from the store
(262 tie days of 2,418, POC differs on 262/262, median Rs 0.35, worst Rs 18.55, 23 days beyond one
row height): the frequencies are real, not fabricated. I re-derived every number in the trader-gate
pack -- all 7 raw-ness proofs (gate-1 gaps and exact high/low matches) and both windows on both
chart days -- straight from the frozen CSVs and the parquet stores, read-only; every figure matches
the committed pack, including the one-tick BHARTIARTL separation (1914.60 vs 1914.50).

I ran a **16-mutant matrix** over the row math, containment, spreading, the tie, the window and the
validity rule: **14 caught, 2 survived** -- both in the evidence generator's wiring, both now closed
by reviewer tripwires I added and kept. I swept the engine over **11,905 real stored symbol-days**
across five symbols and three tick sizes: zero exceptions, volume conservation EXACT on every day,
POC inside `[bottom, top]` on every day.

**Full suite: 1099 passed / 0 failed** from a clean state (`.pytest_cache` and every `__pycache__`
deleted first) -- **1094 from the build**, matching the builder's claim exactly (57 in
`tests/test_poc.py` + 16 in `tests/test_poc_evidence.py` = the +73 the entry states), plus **5
reviewer probes**. No fixture was touched, no test was weakened, no secret appears anywhere, no AI
attribution exists in the history, and CONTEXT.md / plan.md / `tests/fixtures/` / `poc/data/` are
provably byte-unchanged across the span.

Findings: **two MEDIUM** on the quant side (both about spec silences and the gate pack, neither a
code defect), **two MEDIUM** on the code side (coverage gaps I closed with tests), and **six
INFO/LOW**. **None is a CONTEXT.md deviation and none is a FAIL trigger.** The gate stays PENDING
per the card -- Q42 (and ideally one chart POC reading) closes it.

The working tree was clean at review start; the only files I add are
`tests/test_review6_probes.py`, this review, an additive reviewer addendum under QUESTIONS.md
Q-13, and the PROGRESS/STATUS entries. **No file under review was modified.**

---

## 1. Architect's directed checks

| # | Check | Result |
|---|---|---|
| 1 | F6 independently: row EDGES, remainder shape, contiguity, both N; a second tick size | **PASS.** Rebuilt from CONTEXT 3.3's sentences at tick = 1 paise and 25 paise (neither in `tests/fixtures/tick_sizes.json`). N=30 over 100 ticks: tpr=3, 33 rows of 3 with lo/hi `bottom+3i .. bottom+3(i+1)`, then ONE remainder row `[bottom+99t, bottom+100t)` = 34 rows, contiguous (`row[i].hi == row[i+1].lo` for all i), reaching exactly `top`. N=25: tpr=4, 25 rows of 4, no remainder. Midpoints checked too. Kept as `test_f6_rebuilt_from_the_spec_on_ticks_outside_the_frozen_fixture`. The direction rule verified from the count, not the quotient: 34 rows is 4 from 30, 25 rows is 5 from 30 -> tpr=3. |
| 2 | F7 recomputed independently from the CSVs; the 4e-13 claim; the 5 anchors; audit F7(b)'s framing | **PASS.** My own implementation (no `acumen` import) reproduces **25 of 25** frozen `poc_prorata` values; worst absolute error **4.0e-13**, exactly the builder's figure. Anchors: TCS 2205.25, RELIANCE 1303.60, HDFCBANK 815.275 (printout 815.27, within the +-0.01 F7 tolerance), DIXON 14263.50, MANAPPURAM 329.75 -- all 5 reproduced. Six days sit on the tie (DIXON 07-14/07-15, HDFCBANK 07-20, MANAPPURAM 07-14/07-17, TCS 07-20) -- the exact six Q-13 lists; the coarser direction moves exactly those six and no others. F7(b) framing audited: see finding **Q4** -- it is honest, and "strictly nearest" would be false. |
| 3 | Mutation matrix (9 directed mutants + my own) | **14 caught / 2 survived**, both survivors closed by reviewer tripwires. Full table in §2. |
| 4 | EXACTNESS (B113): no float in row-volume accumulation; Fractions to the final midpoint; tie legitimacy under E11 | **PASS.** `src/acumen/poc.py` contains the token `float` only inside three docstrings; there is no float literal, no `float()` call, and no `datetime.now/today/utcnow` anywhere. The accumulation path is `Fraction(volume * overlap, span)` over integer paise; `total_ticks` divides `Decimal/Decimal` (correctly rounded, exact for the terminating quotients that matter) and never a float. The POC comparison `row_volumes[index] >= best` is exact rational comparison, so the tie predicate is a legal equality under CONTEXT 7-E11 (which bans FLOAT equality). `poc_paise` stays a `Fraction`; `poc_rupees` is Decimal and display-only. Conservation verified EXACT (`sum == window_volume`, not a tolerance) on all 25 frozen days x both windows and on 11,905 real stored days. |
| 5 | Q-13: both pin-tests fail on the coarser mutant; tie statistics reproduced from the store; the record | **PASS.** With `<=` flipped to `<` in `ticks_per_row`, BOTH pins fail and nothing else does: `test_the_tpr_tie_keeps_the_finer_profile...` (6 != 5 at 130 ticks) and `test_f7_reproduces_all_25_frozen_prorata_values...` (TCS 2026-07-20: 2260.25 vs frozen 2259.5). The F7 anchors and the conservation property still pass -- confirming Q-13's own statement that no trader-read day sits on a tie. Store reproduction on BHARTIARTL: 262 tie days, POC differs 262/262, median Rs 0.35, worst Rs 18.55, 23 beyond one row height -- identical to the Q-13 table. Q-13's denominator (2,429 stored days) vs mine (2,418 days with candles in the window) differs by 11 -- exactly B118's empty-window days. Q-13 is recorded as class A, OPEN, with the interim, the measurement and the pins. **No architect ruling on Q-13 exists in QUESTIONS.md** -- see finding **Q2b**. |
| 6 | VALIDITY: amended rule only; E4 ast probe green; B121's inverted fixture cites the ruling | **PASS.** `day_profile` tests `volume_reconciled is not True` and nothing else; `False` -> `no-poc-day-fails-gate-1`, `None` -> `no-poc-gate-1-not-run`, both with `grid is None`. Six absent stamps on a gate-1-passing day still yield a POC. `poc.py` contains no `120`, no `5`-of-`120` count, and no window-minute comparison; `test_e4_minute_count_trigger_is_retired_nothing_in_src_counts_window_minutes` is green over every `src/` module. B121's inverted fixture quotes the 2026-07-26 ruling verbatim in its docstring and names the card text it supersedes. |
| 7 | EVIDENCE PACK: 7/7 raw-ness proofs; both windows on BHARTIARTL from the store; ICICIBANK scratch-vs-store; no store writes | **PASS.** All 7 re-derived independently, read-only. Calibration days from the frozen CSVs vs the daily store: TCS 9,515,133/9,546,290 gap 0.326%; RELIANCE 15,543,513/15,631,046 0.560%; HDFCBANK 25,164,225/25,605,395 1.723%; DIXON 2,248,355/2,267,533 0.846%; MANAPPURAM 1,335,787/1,372,071 2.644% -- all PASS the -0.1%..+5.0% band, all with an EXACT 1-min-vs-daily high/low match. Chart days from the parquet stores: ICICIBANK 11,033,892/11,112,550 0.708%, BHARTIARTL 4,688,536/4,715,613 0.574%, both exact H/L. BHARTIARTL 2026-07-17 recomputed from the store: 8-candle **1914.60** (26 rows of 6 ticks, busiest row #8), 9-candle **1914.50** (26 rows of 6, row #8) -- the one-tick separation confirmed, and every row-count and busiest-row index in the pack's "Detail per day" reproduces. ICICIBANK: 1429.15 under both windows, 23 rows (8-candle) / 26 rows (9-candle) -- matches. The **scratch-vs-store** claim is not post-hoc verifiable (the scratch read was deliberately not persisted) and it is also load-bearing on nothing: the committed pack's provenance column reads "local minute store (universe run)" for BOTH chart days, `SOURCE_LIVE_SCRATCH` appears nowhere in it, and I reproduced both rows from the store. **No store write:** the structural test bans four write symbols in `poc_evidence.py`; my own call audit finds exactly one filesystem write in the module -- `out.write_text(...)` for `docs/gate_chunk6_poc_evidence.md` -- plus its `mkdir`. `poc.py` has no filesystem access at all. |
| 8 | Judge B111-B121 | §4, one line each. **All eleven approved**; three carry a reviewer note. |
| 9 | Standard sweep: fixtures, tests, commits, attribution, PROGRESS/STATUS, pushed SHA | **PASS**, with three INFO. §5. |

---

## 2. Mutation matrix

Each mutant was applied to `src/`, the chunk-6 + quality-gate tests were run, and the exact bytes
were restored with `git checkout --` (working tree verified clean after every single one).

| # | Mutant | Verdict | Killed by |
|---|---|---|---|
| M1 | POC volume tie resolves to the **LOWER** row (`>=` -> `>`) | CAUGHT | `test_a_tie_on_row_volume_goes_to_the_higher_priced_row` |
| M2 | Rows **closed at the top** `(lo, hi]` instead of half-open `[lo, hi)` | CAUGHT | `test_a_price_exactly_on_a_row_edge_belongs_to_the_row_above_it` |
| M3 | **topmost-includes-top removed** (`alloc_hi` = grid edge always) | CAUGHT | `test_property_holds_when_the_top_is_off_the_tick_grid_in_both_rounding_directions` |
| M4 | prorata denominator = **row width** instead of bar range | CAUGHT | `test_prorata_splits_a_bar_across_rows_in_proportion_to_the_price_overlap` |
| M5 | **point bar (B117) reverted** to the archived PoC's zero-overlap drop | CAUGHT | `test_a_point_bar_closing_on_a_row_edge_puts_its_whole_volume_in_the_upper_row` |
| M6 | **tpr floor removed** (`max(1, ...)` dropped) | CAUGHT | `test_tpr_is_floored_at_one_so_a_narrow_range_is_never_zero_ticks_per_row` |
| M7 | `day_profile` **window default flipped 8 -> 9** | CAUGHT | `test_the_alternate_window_is_the_9_candle_evidence_window_and_is_never_a_default` |
| M7b | `SPEC_WINDOW_CANDLES` redefined as **9** | CAUGHT | `test_the_spec_window_is_the_8_candle_0915_to_1114_window` |
| M8 | **N read from a literal (24)** instead of `config.row_size`, in `poc_evidence.run` | **SURVIVED** | now caught by reviewer probe (finding **C1**) |
| M9a | engine `day_profile` gains a **tick_paise default of 5** (0.05) | CAUGHT | `test_the_engine_has_no_tick_size_default_anywhere` |
| M9b | **tick hardcoded 0.05** in `poc_evidence.run` instead of the instrument master | **SURVIVED** | now caught by reviewer probe (finding **C1**) |
| M10 | window upper bound made exclusive (drops the **11:14** stamp) | CAUGHT | `test_the_window_slice_takes_0915_through_1114_and_drops_the_1115_stamp` |
| M11 | `volume_reconciled=None` treated as a **gate-1 PASS** | CAUGHT | `test_a_day_whose_gate_1_never_ran_gets_no_poc_either` |
| M12 | realized row count ignores the **remainder row** (floor not ceil) | CAUGHT | `test_the_tpr_direction_is_the_one_whose_row_count_lands_closest_to_n` |
| M13 | `totalTicks` **truncates** instead of rounding half-even | **SURVIVED** | now caught by reviewer probe (finding **C2**) |
| M13b | `totalTicks` rounds **half-UP** instead of half-even | **SURVIVED** | now caught by reviewer probe (finding **C2**) |
| M14 | ticks-per-row **tie -> coarser** profile (`<=` -> `<`) | CAUGHT | both Q-13 pins, and only those two (directed check 5) |

One further mutant (`filled += 0` inside `build_rows`) is **equivalent** -- the subsequent
`filled += span` makes it a no-op -- and is not counted above.

**Score: 14 caught, 3 survived (M8, M9b, M13/M13b are two distinct defects), all three now
tripwired** in `tests/test_review6_probes.py`, each verified to FAIL on its mutant and pass on HEAD.

---

## 3. Findings

### Quant reviewer

**Q1 (MEDIUM) -- the gate's one discriminating day is itself a Q-13 tie day, and the pack does not
say so.**
`docs/gate_chunk6_poc_evidence.md` presents BHARTIARTL 2026-07-17 as "the row to check against his
chart" for Q42. Recomputed from the store under both spec silences at once:

| window | Q-13 interim (finer) | Q-13 coarser | rows drawn |
|---|---|---|---|
| 8-candle (spec) | **1914.60** | 1914.65 | 26 vs 22 |
| 9-candle (alt) | **1914.50** | 1914.55 | 26 vs 22 |

The **window** conclusion is safe either way: the 8-vs-9 gap stays exactly Rs 0.10 in both
directions and the ordering is preserved. But the absolute number the trader is asked to match is
Q-13-dependent, so a reading of 1914.65 would confirm the 8-candle window while REFUTING the
interim -- and the pack's own closing ask ("if he sends any chart with the rows countable, that
answers it") does not tell him that the very chart he is being asked about is such a day (26 rows
under the interim, 22 under the coarser direction). Not a code defect and not a spec deviation: the
engine is right and the pack's numbers are right. It costs the architect a round-trip. **Recommend
one added sentence to the pack before it reaches the trader** -- pack text is the architect's to
approve, so I have not edited it; the measurement is recorded in the Q-13 reviewer addendum.

**Q2 (MEDIUM) -- CONTEXT 3.3's `round` in `totalTicks` has an unstated MODE; measured, it moves the
POC on real days.**
The same sentence family as Q-13. The builder recorded the choice as Class-B **B114** (half-even)
rather than raising it, which plan.md §5 permits -- but it is not free. Measured over BHARTIARTL's
stored history at N=24 with the master's 10-paise tick: half-even and half-up give a **different
`totalTicks` on 449 of 2,418 days (18.6%)** and a **different POC on 10 of them** (median Rs 0.40,
worst Rs 9.85). Two orders of magnitude smaller than Q-13 (which moves the POC on 262 of 262 tie
days), but non-zero and it is real money on those days. The builder's direction is the defensible
one (Python's own `round`, and the rounding this repo already uses for money). **Recorded as a
reviewer addendum under Q-13** so the architect can fold it into the same trader question, and now
**pinned** by `test_total_ticks_rounds_half_even_and_not_by_truncation` (finding C2).

**Q2b (INFO) -- the "architect interim confirmation" for Q-13 is not in the repo.**
The directed checks ask me to verify "the Q-13 record + architect-interim note". The Q-13 record is
present, complete and honest (question, why it is not cosmetic, the measured table, why the
calibration cannot settle it, the interim with three ranked reasons, the pins, and the cheapest
oracle). I can find **no architect ruling or interim confirmation for Q-13 anywhere in
QUESTIONS.md** -- unlike Q-10/Q-11/Q-12 and the completeness amendment, each of which carries an
`ARCHITECT'S RULING ... verbatim` block. This is not a builder defect (Q-13 is correctly marked
OPEN and non-blocking, and the interim blocks nothing), but the confirmation the prompt refers to
exists only in the architect's chat. **It should be recorded in QUESTIONS.md** in the same verbatim
form as the others, so a later session reads it from the repo rather than from a conversation.

**Q3 (LOW) -- the instrument-master tick is TODAY's tick, so historical row grids are off-grid on
40-68% of stored days.**
CONTEXT 3.3 mandates the per-symbol tick from the instrument master, and the engine obeys it with no
default and no table -- correct. The measured consequence: because NSE widened ticks, old prices
traded on a FINER grid than the master reports, so `(top - bottom)` is not a whole number of ticks
on a large fraction of history.

| symbol | master tick | stored days | off-grid range | dominant residual |
|---|---|---|---|---|
| BHARTIARTL | 10p | 2,418 | 1,018 (42.1%) | 5 paise (907 days) |
| ABB | 50p | 2,418 | 1,654 (68.4%) | 5p / 10p |
| ADANIENT | 10p | 2,418 | 1,035 (42.8%) | 5 paise (837 days) |
| AUBANK | 10p | 2,231 | 972 (43.6%) | 5 paise (556 days) |
| BEL | 5p | 2,420 | 16 (0.7%) | 1-4 paise |

Two consequences worth the architect's eyes, neither a defect: (i) **B116's top-inclusive stretch is
load-bearing, not a corner case** -- it fires on ~40% of stored days, and I verified conservation is
still EXACT on all 11,905 of them; (ii) a residual of exactly half a tick is precisely where B114's
rounding mode decides (finding Q2). All 25 frozen calibration days and both chart days are **on-grid
(0 of 25 off-grid)**, so F7 and the gate are unaffected -- this is a history-only effect that lands
in chunk 9/12.

**Q4 (INFO) -- F7(b)'s "no alternative STRICTLY nearer" is an honest reading, not a weakened
assertion.** Distances to the trader's readings:

| day | reading | prorata | `poc_uniform` | `poc_close` |
|---|---|---|---|---|
| TCS 07-14 | 2205.3 | **0.050** | 2.150 | 6.250 |
| RELIANCE 07-16 | 1303.7 | **0.100** | 1.100 | 1.700 |
| HDFCBANK 07-14 | 815.3 | **0.025** | **0.025** (same price) | 6.325 |
| DIXON 07-16 | 14267 | **3.500** | **3.500** (same price) | 346.500 |
| MANAPPURAM 07-15 | 329.75 | **0.000** | 3.900 | **0.000** (same price) |

Prorata is **strictly nearest on 2/5 and tied-nearest on 3/5; it is never beaten**. On the three tied
days the rival lands on *exactly* prorata's price, so an "is strictly nearest" assertion would fail
on an agreement, not on a defect -- CONTEXT 8 F7(b)'s word is "nearest", which a tie satisfies. The
residual set {0.000, 0.025, 0.050, 0.100, 3.500} also reproduces CONTEXT 5's stated "residuals
Rs 0.05-Rs 3.5" band. The framing is correct and the test is the strongest one the data supports.

### Code reviewer

**C1 (MEDIUM -- coverage gap, closed by a reviewer test).**
`acumen.poc_evidence.run()` is the only place where the two spec constants are wired, and its wiring
was untested: replacing `row_size=config.row_size` with `row_size=24`, and
`tick_paise=master.instrument(symbol).tick_size_paise` with `tick_paise=5`, each left the **entire**
chunk-6 suite green (106 passed). Both are exactly what CONTEXT 3.3/4.3 forbid ("NEVER hardcode
0.05"; N from config) and what the code_reviewer checklist calls an automatic finding. The code as
committed is **correct**; only the tripwire was missing. Closed by
`test_no_src_module_passes_a_literal_row_size_or_tick_paise` -- an `ast` probe over every
`src/acumen/*.py` that fails on any numeric literal passed to `row_size=` or `tick_paise=`
(`tick_paise=None`, the deliberate "do not snap to a grid" sentinel in `vendor_adjustment.py`, is
correctly not a hit). Verified to fail on both mutants.

**C2 (MEDIUM -- coverage gap, closed by a reviewer test).**
Decision B114 states a rounding MODE but nothing pinned it: both truncation and half-up survived the
suite. The one off-grid fixture asserts only volume conservation, which holds in every rounding
direction (that is precisely what B116 guarantees), so it cannot see the mode. Closed by
`test_total_ticks_rounds_half_even_and_not_by_truncation`, which pins 1.5/2.5/3.5 ticks -> 2/2/4 and
keeps the spec's minimum-1 floor. See Q2 for why this matters beyond hygiene.

**C3 (INFO).** In `spread_volume`, the `volume == 0` early-`continue` precedes the impossible-OHLC
check, so a **zero-volume** bar with `high < low` is not refused. It is harmless today -- CONTEXT 4.5
gate 2 excludes any such day before the engine sees it, the bar contributes no volume, and an
inversion large enough to matter makes `total_ticks` raise "top is below bottom" -- but the ordering
reads as a validated invariant when it is only validated for traded bars.

**C4 (INFO).** `6ed863c` does not carry the `(unreviewed)` suffix CLAUDE.md's git rules ask of build
commits (`8b053c2` does). Same class as REVIEW_5A F4; message body is otherwise exemplary (what +
why, chunk prefix, spec citation).

**C5 (INFO).** The chunk-6 PROGRESS entry does not textually state the pushed SHA. CLAUDE.md asks
the session's final report block to state it, and origin/main is verified in sync at `6ed863c`, so
nothing is lost -- same class as REVIEW_5A F5.

**C6 (INFO).** `evidence_for_day` computes both profiles with `volume_reconciled=True` hardcoded and
reports gate 1 separately, so a chart day that FAILED gate 1 would still print a POC beside a `FAIL`
cell. All seven days pass, so the committed pack states nothing false; but the pack's "proof that
each day's prices are the real prices" is a **report**, not a guard. Deliberate for an evidence tool
(the point is to show the number and its proof side by side) -- recorded so a later reader does not
mistake it for a validity path.

---

## 4. Class-B decisions B111-B121 -- judged

| # | Decision | Verdict |
|---|---|---|
| **B111** | Window is a PARAMETER with a module constant default, not a `config.yaml` key | **APPROVE.** Correct reading of an OPEN item: a config knob would let a later session flip a strategy-critical window with no architect ruling. Verified `ALTERNATE_WINDOW` is referenced by `poc_evidence.py` only, both entry-point defaults are `SPEC_WINDOW`, and mutants M7/M7b are caught. |
| **B112** | Window held as a COUNT of 15-min candles; 1-min stamps DERIVED | **APPROVE.** CONTEXT 3.3 states the same window twice; deriving one from the other means they cannot drift, and no clock literal enters the engine. Verified 8 -> 11:14 and 9 -> 11:29, and that `_minutes_after_open` refuses a window past the 15:30 close (CONTEXT 7-E2). |
| **B113** | Row volumes are exact `Fraction`, not floats | **APPROVE, and this is the load-bearing one.** It is what makes the POC tie an EXACT equality rather than the float equality CONTEXT 7-E11 bans, and what makes conservation exact rather than "within 1e-6". Verified: no float anywhere in the arithmetic; exact conservation on 25 frozen days x 2 windows and 11,905 real days. |
| **B114** | `totalTicks` rounds half-EVEN | **APPROVE with a note.** The mode is the defensible one, and it was properly recorded. But the entry says it "only ever decides an off-grid residual", and measured that is 18.6% of BHARTIARTL's stored days deciding a different `totalTicks` and 10 days a different POC -- understated rather than wrong. Now pinned (C2) and escalated to the architect (Q2). |
| **B115** | The ticks-per-row TIE keeps the SMALLER `tpr` (finer profile) | **APPROVE.** Exactly what CLAUDE.md rule 1 asks for: the silence was RAISED as Q-13 with measured impact, not decided quietly, and the interim is the only direction that reproduces the artifact CONTEXT 8 calls authoritative. I confirmed all three of its stated reasons independently -- 25/25 at 4e-13, six tie days moved by the alternative, and TV's own non-tie example landing on the finer side. |
| **B116** | Topmost row's ALLOCATION bound stretches to `top`; its MIDPOINT stays on the grid | **APPROVE.** The split is the literal spec reading: "the topmost row includes top" is a CONTAINMENT sentence, while "each spanning tpr ticks" fixes the height the midpoint comes from. It conserves volume in BOTH rounding directions -- verified on 11,905 real days, of which ~40% are off-grid (Q3), so this is live code, not a guard for a hypothetical. |
| **B117** | A point bar (`high == low`) puts its FULL volume in the containing row | **APPROVE.** CONTEXT 3.3's own sentence, and it repairs a real bug in the archived PoC script. The claim that F7 is unaffected is verified independently: **0 point bars in 3,000 window minutes** across all 25 frozen days. Correctly flagged as differing from `poc/poc3_volume_poc_test.py`. |
| **B118** | An empty window returns its own reason code, not a re-introduced minute count | **APPROVE.** It is the empty set, not a threshold -- `max(high)` over no bars does not exist. Frequency independently reproduced: 53 such days over 5 symbols (~10.6/symbol), matching the entry's "9-11 per symbol", and it exactly explains the 2,429-vs-2,418 denominator gap in Q-13's table. |
| **B119** | `volume_reconciled=None` (gate 1 unrun) yields no POC | **APPROVE.** The ruling's licence is "gate-1 PASSES"; an unrun gate has not passed. Consistent with B104 in the integrity gate, so the two layers cannot disagree. Mutant M11 caught. |
| **B120** | Evidence generator in its own module + a structural no-store-write test | **APPROVE.** Keeps `poc.py` pure per CONTEXT 6, and the store rule is proved rather than promised. My independent call audit agrees: one write in the module, and it is the markdown pack. |
| **B121** | plan.md's "6 missing minutes -> no POC" fixture built INVERTED | **APPROVE.** The architect's 2026-07-26 amendment retired the trigger the card's fixture tested; the card text predates it. Building the card's fixture literally would have re-implemented a retired rule. The test docstring quotes the ruling verbatim and names the card, so the difference cannot be read as drift -- this is exactly how a card/spec conflict should be handled. |

---

## 5. Standard sweep

* **Fixtures frozen.** `git diff --stat chunk5A-pass..6ed863c -- tests/fixtures poc/` is **empty**;
  so is the same diff over the review span. 64 tracked fixture paths, none added, none changed,
  none regenerated. Working tree clean over both directories.
* **No test weakened.** The chunk-6 commits add `tests/test_poc.py` and `tests/test_poc_evidence.py`
  and modify **no existing test file** (`8b053c2` touches 10 files, 2287 insertions, 1 deletion --
  the deletion is the STATUS.md chunk-6 line). No skip, no xfail, no loosened assert. The volume
  property is asserted EXACTLY and again within 1e-6, not only within the tolerance.
* **Scope.** Every changed line traces to the card: `poc.py` (engine), `poc_evidence.py` +
  `scripts/poc_window_evidence.py` + the pyproject entry point (gate pack), the two test files, the
  evidence doc, and the QUESTIONS/PROGRESS/STATUS records. **No existing `src/` module was edited.**
  CONTEXT.md and plan.md are untouched in the span.
* **Purity (CONTEXT 6).** `poc.py` imports only `__future__`, `dataclasses`, `datetime`, `decimal`,
  `fractions`, `typing` and the pure `.calendar` -- enforced by the builder's own `ast` probe. No
  I/O, no network, no clock read.
* **Secrets.** No `.env` read, no credential string, no token in `poc.py`; `poc_evidence.py` reaches
  credentials only via `Credentials.from_env()` inside the `--allow-network` scratch branch and
  prints nothing from it. Nothing in the pack, the tests or the PROGRESS entry contains a secret.
* **Commits & attribution.** Two commits, both `chunk6:`-prefixed with what+why bodies citing
  CONTEXT sections. History-wide scan for AI attribution: **zero hits** (only the filename
  `CLAUDE.md`). No force-push; single branch `main`.
* **PROGRESS / STATUS.** The entry follows plan.md §6 exactly (all nine fields present and honest).
  Its test claim is verified to the test: 57 + 16 = 73 new, 1094 total. The STATUS line matches the
  entry, and `6ed863c` exists precisely because the builder found its own count off by one and
  corrected the ledger -- the right instinct.
* **Pushed SHA chain.** `origin/main` == `HEAD` == `6ed863c188f4cfbc0a6ecfa24cb49789463ee447` at
  review start; tree clean. Tags run `chunk0-pass`..`chunk5A-pass`; `chunk6-pass` is added by this
  review.
* **Beyond-fixture sweep.** The engine run read-only over **11,905 stored symbol-days** (BHARTIARTL,
  ABB, ADANIENT, AUBANK, BEL; ticks 5p/10p/50p): 0 exceptions, conservation EXACT on every computed
  day, POC inside `[bottom, top]` on every day, 53 empty-window days, **0 zero-volume profiles**
  (matching the Q-13 finding's "0 of 9,480"), 1,160 legally half-paise POCs (~10%, E11 working as
  specified).

---

## 6. Tests this review adds and keeps

`tests/test_review6_probes.py` (5 tests, all green on HEAD, each verified to FAIL on its mutant):

1. `test_no_src_module_passes_a_literal_row_size_or_tick_paise` -- closes M8 and M9b (finding C1).
2. `test_total_ticks_rounds_half_even_and_not_by_truncation` -- closes M13 and M13b (finding C2).
3. `test_f6_rebuilt_from_the_spec_on_ticks_outside_the_frozen_fixture` (x2, ticks 1p and 25p) --
   the independent F6 of directed check 1.
4. `test_the_tpr_tie_is_reconstructed_independently_of_the_engine` -- re-derives the tie set from
   CONTEXT 3.3's "realized row count" definition rather than from `ticks_per_row`, over every tick
   count to 4000 plus the six calibration tie days.

---

## VERDICT: **PASS**

Chunk 6 implements CONTEXT 3.3 as written -- window, row math, containment, prorata, tie and the
amended validity rule -- with exact arithmetic, no I/O in the engine, no hardcoded spec constant,
and its one genuine spec silence raised as a class-A question with measured impact instead of a
silent choice. Every golden reproduces from an independent reimplementation; every number in the
trader-gate pack re-derives from the frozen CSVs and the stores. The four MEDIUM findings are two
spec silences for the architect (Q1, Q2) and two coverage gaps I closed with kept tests (C1, C2);
none is a CONTEXT.md deviation, none needs a fix session.

**I would stake the trader's account on this engine.** The `TRADER GATE stays PENDING` --
`docs/gate_chunk6_poc_evidence.md`, closed by Round-3 Q42 and, ideally, one POC price plus one row
count off the BHARTIARTL/ICICIBANK charts, which per finding Q1 would settle Q42 and Q-13 in a
single reading.
