# REVIEW_12_2 — chunk 12, the ROUND-4 EXECUTION re-review

**Span** `453ba5e..6504fbf` (7 commits) · **QC, BOTH personas** (`personas/quant_reviewer.md`,
`personas/code_reviewer.md`) · fresh session, 07-Aug-2026 · stores READ-ONLY throughout.

**VERDICT: FAIL.** Two findings carry it, and neither is in the engine, the ledger, the money or
the points arithmetic — all of which this review re-derived independently and found exact. The
run does NOT need re-running and not one published figure moves. What fails is the DOCUMENT layer
and the record: page 5 invites the trader to check an arithmetic that does not close (Q1, out by
74,081, and the flipped probe from REVIEW_12 asserts the defective sentence verbatim so it will
stay green), and an architect ruling was not executed while two records state that it was (C1).
Both fixes are small and local. Details, and the full fix list, at the end.

---

## PART 0 — RECORDING (architect-directed, distinct from the review; committed separately)

Two commits, made before the review proper and reported here for completeness.

**0a · `7b04079` — the trader's two Round-4 texts, recorded verbatim.** The ROUND-4 EXECUTION
session left both quotation slots RESERVED and empty because neither text reached it and the
06-Aug quotation-fidelity ruling forbids writing a quotation one does not hold (B304). The
operator supplied both through the architect's prompt; both are now in QUESTIONS.md byte for
byte. The only permitted transformation was this repository's ASCII fold and **none was needed —
both texts are already pure ASCII**, so what stands is the supplied bytes unchanged. The
conventions are stated in the block: the forward slash marks his own line breaks, the arrows are
his diagram's connectors, and the single `[flow diagram:]` label is OURS and is marked as ours.
B304 is DISCHARGED.

**0b · `35b533e` — CONTEXT v1.9, committed alone, three edits and no fourth.** Header to
`Version 1.9 · 7 August 2026`; §3.5's Q40-d flags clause replaced by the supplied Round-4
supersession sentence (the three surviving disclosure items and the OPEN-6/OPEN-7 sentence around
it untouched); §10's v1.9 row verbatim. §3.4 is untouched for the third consecutive version.

**What the arriving bytes settle** (recorded in QUESTIONS.md, no action taken on any of it):

* His Q44 figures are F1's figures. He writes entry **2037**, entry candle low **2032**, POC level
  **2030**. CONTEXT 3.4's gap predicate is `entry candle's low > POC`; `2032 > 2030` is TRUE, so
  his own three numbers put his own example on the gap branch. **CONTEXT v1.8 is corroborated by
  the trader's bytes and not only by the architect's reading of them.**
* His "GAP UP ZONE (Untraded gap space between POC and Low)" is CONTEXT 3.4's own gap.
* His stop constraint — "at or below 2030" — is one the engine satisfies **by construction**, and
  this review proved it at full scale rather than on the fixtures: see Q-verified item 7 below.

Two items were opened and put to the architect, both NON-BLOCKING: **Q-24** (his text also asks
for a Risk-to-Reward Ratio and a "Point & **Percentage** Focus" that page 7 does not carry, and
names a "Position Size: 1 Share" basis and a "Nifty 200" universe where CONTEXT 3.5 sizes by
Rs 1,000 of risk over CONTEXT 3.1's ~210 F&O underlyings) and **Q-25** (his Round-4 diagram pins
a ZONE where CONTEXT 3.4, from his earlier and more specific R2-Q33, pins a VALUE).

---

## PART 1 — WHAT THIS REVIEW RE-DERIVED, AND FOUND EXACT

Everything in this part was computed by code written for this review that **imports nothing from
`src/acumen`** (except where a test must exercise the engine under review), from the spec text and
from the prose printed on the trader's own page. Agreement is therefore evidence, not tautology.

**1 · The suite.** `2218 passed / 0 failed / 0 skipped` from clean, 243.22s — the claimed count to
the test. With this review's kept probes: **2,270 / 0 / 0**.

**2 · Every renamed test, audited by AST.** For each test file in the span, both revisions were
parsed and each function's body compared with its docstring stripped. **The six F1/F2 renames have
byte-identical bodies** — four at signal level, two at PnL level, exactly as claimed. "No expected
value was re-measured and no fixture byte moved" is TRUE and is now proved mechanically rather
than by reading the diff.

The other eight name changes (14 in total, matching the claim) also changed their bodies, and each
was inspected assertion by assertion. **No test was weakened.** Every removal is a ruling-driven
substitution (`v1.7`→`v1.8`; `CAPITAL_FLAGS_PENDING_NOTE`→`CAPITAL_FLAGS_RETIRED_NOTE`), and the
rest are strict additions. One looked like a weakening and is not:
`test_the_pack_generator_carries_no_hand_typed_money_literal` drops from two top-level asserts to
zero because both moved **inside** a `for module in (MODULE, POINTS_MODULE)` loop — the tripwire
now runs against the points module too. Strengthened.

**3 · The gap goldens, re-derived by hand from CONTEXT §3.4.** Not read off the tests:

| | F1 | F2 |
|---|---|---|
| reference (11:15 close) | 2025 `<` POC 2030 → **ARMED** | 2034 `>` 2030 → **WAIT-BELOW** |
| arming | — | 2038 above while waiting consumes nothing; 2027 `<` 2030 → **ARMED** |
| trigger | 2037 `>` 2030 → entry **2037** | 2037 `>` 2030 → entry **2037** |
| gap predicate | entry low 2032 `>` 2030 → **GAP** | entry low 2032 `>` 2030 → **GAP** |
| SL = previous 15-min close | **2025** | **2027** |
| risk | **12** | **10** |
| TP = entry + 3R | 2037 + 36 = **2073** | 2037 + 30 = **2067** |
| exit | nothing touches 2025/2073 → square-off | nothing touches 2027/2067 → square-off |

All four numbers the architect named (SL 2025/2027, risk 12/10, TP 2073/2067) reproduce, and they
match CONTEXT v1.8 §8's cells exactly.

**4 · The points headline, recomputed by an independent ledger streamer.** Ledger sha256
`c70a72b097879914…`, matching the report. Points computed from CONTEXT 3.4's mirror written from
the spec (`exit − entry` long, `entry − exit` short):

* **204** stocks · **188,345** trades · **+72,096.43** points · **+0.38** a trade (exact
  `7209643/188345` paise) · **32.60%** positive (61,406/188,345). Every figure reproduces.
* Cross-check on the money side: net `−Rs 16,836,018.20`, and `gross − cost == net` holds.
* 61,406 trades are positive in POINTS against 59,385 positive in MONEY — the 2,021 gap is the
  flat Rs 100 cost, which is exactly what page 7's honesty paragraph says it is.

**5 · BOSCHLTD and DIXON, recomputed in full**, and the whole table besides.

* **BOSCHLTD** (#1): 1,133 trades, 404 winners / 727 losers / 2 flat (sums), 35.66% positive,
  **+10,538.70** points, +9.30 a trade, drawdown 3,255.55, best +945.00 on 2026-06-03, worst
  −459.00 on 2016-11-07.
* **DIXON** (#204): 960 trades, 298 / 660 / 2, 31.04%, **−1,531.00**, −1.59 a trade, drawdown
  2,347.50, best +270.00 on 2020-11-09, worst −190.00 on 2021-02-09.

Rather than stop at the five further spot-checks the prompt asked for, this review checked the
**whole** table: **all 204 rows × 9 fields = 1,836 published figures in
`docs/reports/points_by_symbol.md` reproduce EXACTLY, zero mismatches**, and the ranking order is
identical to `(-points, symbol)`. Page 7's printed top-20 and bottom-20 (**40 rows × 7 fields =
280 figures**) likewise reproduce exactly, the two slices do not overlap, and they are precisely
the head and tail of the independent ranking.

**6 · The max-drawdown-in-points definition.** Implemented from the page's own words — *"the
deepest fall in the running total of those points, walked in date order"* — as a peak seeded at
zero, so a stock whose first trade loses shows that loss. It reproduces the module's
`_walk` on every one of the 204 stocks. The seeding matches the money side, where the equity curve
starts at capital, so the two drawdowns are the same construction in different units.

**7 · SIZE-INDEPENDENCE, proved by AST over `src/acumen/points_view.py`.** The ledger-row
attributes the module reads anywhere are exactly `day`, `entry_close_stamp`, `entry_paise`,
`exit_paise`, `side`, `symbol`. **`qty`, `notional_paise`, `gross_pnl_paise`, `net_pnl_paise` and
`cost_paise` are read from no row.** The single hit on the banned list is the *parameter name* of
`cost_in_points_paise(cost_paise, *, shares)`, the helper behind the honesty line, which never
touches a row. The one dynamic access is the guarded `getattr(row, "executed", False)`. Imports
are stdlib plus `from . import signals` (a side constant). PURE: no I/O, no network, no clock.

**8 · The trader's own Round-4 stop constraint, at full scale.** His words put the stop "at or
below" the POC. On the ARMED path a close strictly beyond the POC IS the trigger, so the candle
before the entry candle can only have closed at or below it — and the mirror holds short. Measured
over the run: **2,068 gap entries — 850 long, 1,218 short — and ZERO violations on either side**
(long `stop <= POC`, short `stop >= POC`, compared in half-paise so the off-grid POC is never
rounded). His constraint is satisfied on every gap trade in ten years, not merely on F1 and F2.
Also asserted as a swept property over 49 POCs in the kept probes.

**9 · The caveat, the cost line, and the ~10-by-chance arithmetic.** The mandatory
multiple-comparisons sentence is present **byte-exact on BOTH artifacts** (page 7 and the 204-row
companion). It is a TEMPLATE, not typed prose: `by_chance(204) = int(204 × 1/20) = 10`
self-computes from the ranking actually printed, so a differently sized table cannot inherit this
one's arithmetic (B309, approved). The rupee-cost honesty line is on both, in each document's own
words, and both give the Rs 100.00 → 100.00 points identity at one share.

**10 · Byte-reproducibility, in this session, to scratch paths.** The committed hashes match the
claims (`8cbabed9…` 51,627 B / 639 lines; `208b142e…`; `312bc9e0…` 218 lines; `529a04a8…`
87,756 B / 899 lines). Regenerated independently to scratch paths: `trader_pack.md`,
`trader_pack.json` and `points_by_symbol.md` are **IDENTICAL**, diffs empty.

**The report too — completed after the review was first written, and folded in here.**
`acumen.report_9b.main()` had to be invoked by importing it (C4: the module has no entry point)
and took just over two hours against the same run. It wrote 87,756 chars and the diff against the
committed file is **EMPTY**; sha256 `529a04a887d2b69a…`. **All four artifacts byte-reproduce.**

This paragraph replaces an earlier one in this document that reported the report's reproduction as
NOT DONE, which was true when the review was committed (`f88d125`) and is recorded in that commit,
in PROGRESS.md and in STATUS.md. It is corrected here rather than quietly dropped. **It changes no
finding and no verdict** — reproducibility was never what Q1 or C1 turned on.

**11 · The numeric freeze.** `2,457 → 2,449` tokens; **exactly 8 left and 0 arrived**, and they
are exactly `43, 43, 44, 44, 2032, 3.4, 31, -2026` — every one a Q43/Q44/GO-ruling reference, not
one a metric. The three new exclusions are precisely the three Round-4 sentences (the flags line,
the Q44 line, the config table row); `lines_in_sections_1_to_9` is unchanged at 558, so no line
entered or left the frozen region. B310 approved.

Independently and more strictly, this review compared **every numeric token in the whole report**,
not just the frozen sections: 3,511 → 3,527, with `31, 43, 43` leaving and 19 arriving — all of
them Round-4 references (`Round 4`, `06-Aug-2026`, `v1.8`, `POC 2030`, `3.4`, and the quoted
`POC 2032` stamp). **Not one metric moved anywhere in the report.**

**12 · Stores, secrets, history.** Every file under `data_root` was fingerprinted (mtime + size)
before and after the whole review: **22,186 files, ZERO changes** — including across two full
generator runs. `.env` is untracked and none of its values appears in the span. No AI attribution:
the only matches are the permitted citations of `CLAUDE.md` and CONTEXT.md's own pre-existing
text. Every commit touching `src/` or `tests/` carries `(unreviewed)`; the two that do not
(`15a72b6` CONTEXT-only, `6504fbf` PROGRESS/STATUS-only) correctly need none. **No engine module
(`bias`, `poc`, `signals`, `simulate`) was touched.** The frozen run manifest on disk still reads
`spec_version v1.7` with its PENDING disclosures and pending `capital_flags` note, byte-exact —
B305's whole purpose, verified.

**13 · Red-then-green, verified independently.** The five flipped REVIEW_12 probes were run
against the pre-fix source in a scratch tree built by `git archive 15a72b6`: **all five RED there,
all five green at HEAD**, and the sixth (structural, never flipped) green in both. See C5 for a
wording qualification.

---

## PART 2 — FINDINGS

### Q1 · MEDIUM · quant · **the page-5 reconciliation does not close, and it is out by 74,081**

This is the architect's 87,192 challenge, and the challenge lands.

Page 5 prints the bias-rule table, then: *"**Those rows add up to 493,680, and here is the rest of
the arithmetic so you can check it.** The machine walked 495,312 stock-days in all. 1,632 of them
carry no rule at all … Of the ones that do carry a rule, three of the rows above say* not judged*:
a bias could not be settled there, so no trade was possible. **And 87,192 more had a bias but were
refused afterwards on a data check**, which is why the table is bigger than the 406,488 stock-days
the machine actually judged and could have traded."*

Followed literally — which is exactly what the reader is invited to do:

```
   493,680   the table
 −  74,081   the three rows it calls "not judged"  (73,841 + 210 + 30)
 −  87,192   "and 87,192 MORE …"
 = 332,407   but the page states the answer is 406,488
```

**The error is 74,081 — precisely the not-judged population, subtracted twice.** The generator
computes the figure as `sum(bias_rules.values()) - run.usable`
(`src/acumen/trader_pack.py:1345`, printed at `:1304`), i.e. *every* rule-carrying row that was
refused. That set **contains** the three not-judged rows; it does not stand beside them. The word
"more" is wrong.

The sentence is wrong a second time, about the population rather than the arithmetic: it says the
87,192 *"had a bias"*, when **74,081 of them are the very rows the preceding sentence has just
described as not judged** — days on which no bias was settled at all. Measured from the ledger,
the figure that genuinely had a bias and was then refused on a data check is **13,111**
(rule-1 9,033 + inside-bar 2,139 + rule-2 1,858 + rule-3-outside 60 + rule-3-no-1min 23). That
number appears on no page.

The correct reconciliation needs one clause, not a new measurement: `493,680 − 87,192 = 406,488`,
where the 87,192 is *all* the refused rule-carrying days — the 74,081 not-judged ones **and**
13,111 that did carry a bias.

**Aggravating: REVIEW_12's own flipped probe pins the defective sentence.**
`test_the_bias_rule_tables_population_is_now_STATED_and_reconciles` asserts
`f"{total - limits['usable']:,} more had a bias but were refused afterwards" in page`. It checks
that the figure is printed; it checks nothing about whether the three-step arithmetic closes. The
fix REVIEW_12 Q2 ordered is therefore incomplete, and the probe written to guard it will hold the
error in place. **That probe must be updated in the same commit as the sentence.**

Pinned by a kept probe of this review, `test_the_bias_tables_stated_arithmetic_does_NOT_close`,
which reproduces the arithmetic from the COMMITTED companion and turns red when the sentence is
corrected.

### Q2 · MEDIUM · quant/code · **the biggest "not judged" row is described to the trader with the wrong cause**

`bias_rule == "no-data"` is **73,841 rows — the second-largest row on the trader's page**. The pack
labels it (`src/acumen/trader_pack.py:1362`):

> `"no-data": "no stored one-minute data for the stock that day -- not judged"`

The rule is emitted at `src/acumen/bias_engine.py:310`, in this branch:

```python
current = self._candle(symbol, current_date)
previous_raw = self._candle(symbol, previous_date)
if current is None or previous_raw is None:
    # A candle is missing (the symbol had not listed yet): seeding has not started.
    ... rule="no-data", tradeable=last_bias is not None
```

and `_candle` reads `self.store.daily(...)` — the **DAILY** store. So the rule means *no daily
equity candle for D−1 or D−2*, on the bias PAIR days. It is not about one-minute data and it is
not about "that day". The two usually co-occur early in a symbol's history, which is why the
mislabel has survived; they are not the same thing.

**And the row is not uniformly "not judged".** `tradeable = last_bias is not None`, so a carried
bias makes such a day tradeable. Measured over the ledger: **2 of the 73,841 rows are `status:
evaluated`, not refused** — `FORCEMOT 2024-02-14` and `FORCEMOT 2024-02-15`, both with
`bias: bearish`, `minute_count` 360 and 368, outcome `no-trade-armed-but-no-qualifying-close`.
Days with full minute data, judged, and eligible to trade, sitting inside a row the page calls
"no stored one-minute data … not judged".

Root cause, read from the store read-only: FORCEMOT's daily store has a **112-calendar-day hole,
2023-10-25 → 2024-02-14** (1,648 rows 2019-08-19..2026-07-30; exactly one gap over 5 days). The
two rows are its boundary — the trade day has a daily row, its pair days do not.

Two things are owed: the label must describe the daily bias pair, and either the "not judged"
wording must acknowledge the carried-bias case or the sentence's three-row claim must be qualified.

### Q3 · MEDIUM · quant · **page 7 does not state its 988 flat trades, where page 1 was required to state its 40**

REVIEW_12 finding Q5 required page 1 to put its two win rates on one denominator and to count the
flats out loud; it now reads *"40 trades ended exactly level and are in neither"*. Page 7's
`Trades positive in points` column uses the same all-trades denominator (`win_rate` is
`Fraction(winners, trades)`, flats included — correctly) — but **988 trades ended exactly level in
points, across 171 of the 204 stocks**, and no sentence on page 7 or on the 204-row companion says
so. That is **25× page 1's flat population, unstated on the newer page**.

Nothing printed is false: the column is honestly named *positive*, not *winning*, and the
companion's JSON carries `flat` per stock. But the reader of page 7 has 988 trades sitting in the
denominator and in no stated category, and the correction the architect ordered for 40 was not
carried to 988. The columns section ("What the columns mean") is where it belongs.

### C1 · MEDIUM · code · **`config.yaml` was never edited, and two records state that it was**

The architect's ruling: *"capital-infeasibility flags are RETIRED (**config keys stay null,
labelled 'retired by trader, Round 4'**)"*. Both records claim execution:

* QUESTIONS.md, EXECUTED list: *"with `config.yaml`'s two keys still null and now labelled*
  retired by trader, Round 4*"*;
* STATUS.md, PART C: the same words.

`git diff --name-only 453ba5e..6504fbf -- config.yaml` returns **nothing**. The file still says
*pending* in four places — line 26 (*"it is the trader's pending Q43 answer"*), lines 33–35
(*"both are NULL until the trader answers Q43 … every output says 'capital-infeasibility flags NOT
computed — the trader's Q43 answer is pending'"*) and the two inline comments at lines 41–42
(`# null -- trader Q43 pending`).

Mitigating, and it matters: the **values** are right (both null, and no flag value is computed
anywhere — verified by `test_no_capital_figure_is_hidden_in_the_flag_machinery` and by AST), and
**every published output does carry the retirement wording**, so no trader-facing document tells a
reader an answer is awaited. Only the config file's own labels, and the session's record of
itself, are stale. But a session that reports an edit it did not make is the failure mode this
repo's whole recording discipline exists to prevent, and CONTEXT v1.9 §3.5 — written this session
from the architect's supplied text — now asserts the labelling as law.

Corrected append-only in QUESTIONS.md by this review; the edit itself is owed to the next builder
session.

### C2 · LOW · code · **`backtest.SPEC_VERSION` is one version behind CONTEXT after v1.9**

It reads `"v1.8"`. Its own docstring states the contract — *"a ledger always names the law it was
produced under"* — and B307 bumped it for v1.8 even though v1.8 changed no walked row. v1.9's §3.5
edit changes what the report MUST disclose. Architect's call whether v1.9 is documentation-only; a
review session does not edit code. Note `test_the_q21b_disclosure_names_the_ruling…` pins
`SPEC_VERSION == "v1.8"`, so the constant and its test move together.

### C3 · LOW · code · **CONTEXT §9's OPEN-6 row still names the retired flags**

OPEN-6 reads *"**RESOLVED** — none; take-all + capital-infeasibility flags (Q40-d)"*, which §3.5
has now retired. Not touched: the architect specified exactly three edits for v1.9 and this review
made exactly three. Flagged for the next version.

### C4 · LOW · code · **neither document generator can actually be invoked**

`acumen.trader_pack` and `acumen.report_9b` each define `main(argv)` with a full argparse CLI
(`--out`, `--json`, `--points`, `--run`, `--config`). Neither has an `if __name__ == "__main__":`
guard, and neither appears in `[project.scripts]` — where all eight other runnable modules do.
`python -m acumen.trader_pack --out … --json … --points …` **exits 0 having written nothing, and
says nothing.** The two documents a human decision rests on are regenerable only by importing the
module and calling `main()` by hand, and a silent no-op exit 0 is the worst available failure mode
for an operator who thinks a regeneration just succeeded. This review regenerated them by
importing `main()` directly.

### C5 · INFO · **"FAILED on its own assertion" is true of two of the five flipped probes**

Verified independently: all five are RED against `git archive 15a72b6`. But only two fail on a
substantive assertion (Q1's *"the unchecked superlative is gone"*, Q3's *"the page now says so"*).
One fails on `AttributeError: module 'acumen.trader_pack' has no attribute '_rounding_rivals'`,
and two on `KeyError` for a companion field the fix added (`bias_rules_total`,
`delivered_win_rate_over_decided_trades`) — failing before reaching the page-text assertion. All
five do carry page-text assertions, so the discipline holds in substance and the claim's wording
overreaches only slightly. Recorded because the point of red-then-green is that the *assertion*
discriminates.

### C6 · INFO · **"the report moves five lines and no number"**

Whole-file: 897 → 899 lines, 8 replaced, diff `8+/6−` (which the session states correctly beside
the "five"). "No number" is true of **metrics** and this review proved it more strictly than the
freeze does (PART 1 item 11): 19 numeric tokens arrive and 3 leave, every one a Round-4 reference.
The rigorous statement is the freeze, and it holds exactly.

### C7 · INFO · **seven companion rows print an unsigned `0.00`**

ABCAPITAL, RVNL, BANKBARODA, GODREJCP, IRFC, ASHOKLEY and UNIONBANK show `0.00` in *Points a
trade* while their *Points* column is signed and non-zero (`+4.71` … `−3.90`). `format_points`
quantizes to 2dp before testing the sign, so a value that rounds to zero loses it. The behaviour is
right in the direction that matters — a signed zero (`−0.00`) can never print — and the module's
stated convention (*"positives carry a leading plus so a ranking cannot be misread at a glance"*)
lapses only here, beside a signed column that carries the magnitude.

### C8 · INFO · **`_ordered`'s sort key can mix `date` and `datetime`**

`sorted(rows, key=lambda row: (row.day, row.entry_close_stamp or row.day, row.symbol))`
(`points_view.py:158`) would raise `TypeError` if an executed row had no `entry_close_stamp` and
tied on `day` with another row of the same symbol. Unreachable today — CONTEXT 3.4 allows at most
one trade per stock per day (R1-Q16), so the second element is never compared, and the ledger
holds **0** executed rows without a stamp (measured). Latent only.

### Q4 · INFO · quant · **the carried-bias age question — raised, measured, and closed**

CONTEXT §3.2 bounds no age on a carried bias (*"No rule fires → carry last known bias"*), and Q2's
FORCEMOT hole shows a bias can survive a 112-day gap in the daily store and still make a day
tradeable. Measured over **all 188,345 executed trades**, per symbol in date order, as calendar
days between the trade and the last bias-SETTING rule (rule-1/2/3/tie; inside-bar and the carries
are themselves carries):

| age of the bias | trades | share |
|---|---:|---:|
| set for that day | 159,224 | 84.538% |
| 1 day | 20,432 | 10.848% |
| 2–3 days | 6,906 | 3.667% |
| 4–7 days | 1,781 | 0.946% |
| 8–30 days | **2** | 0.001% |
| over 30 days | **0** | 0.000% |

**No trade in ten years fired on a bias older than 30 days**, and only two on one older than a
week. The mechanism exists; this run does not exercise it. Recorded so a future data era with more
store holes is measured against this baseline rather than assumed to match it.

### Q5 · INFO · quant · **F2's "gap" is not an untraded gap, on the trader's own definition**

His newly recorded words call the zone *"GAP UP ZONE (**Untraded** gap space between POC and
Low)"*. On F1's candles it is genuinely untraded: the prior candle's high is 2029, below the entry
candle's low 2032. **On F2's it is not** — the arming candle runs 2026–2038 and trades straight
through 2030–2032, yet CONTEXT v1.8 §8 calls it *"the gap branch again"*.

The engine is right and so is §8: CONTEXT 3.4's operative predicate is `entry candle's low > POC`,
and its gloss (*"it opened beyond POC and never traded at/below it"*) is about the ENTRY candle,
which never does. Recorded because one of only two goldens the trader may read teaches a "gap" his
own sentence would not call one. Raised as **Q-25**.

---

## PART 3 — CLASS-B DECISIONS (B304–B311)

| | verdict | |
|---|---|---|
| **B304** trader's texts not written | **APPROVED** | Correct application of the quotation-fidelity ruling, and **DISCHARGED** by PART 0a. |
| **B305** historical constants kept byte-exact | **APPROVED** | Verified against the frozen manifest on disk: `v1.7`, the PENDING disclosures and the pending `capital_flags` note are all still byte-exact, so the report and the committed pilot pack quote their source correctly. Exactly right. |
| **B306** no PnL golden for the gap parametrization | **APPROVED, and now CLOSED** | Honestly recorded as leaving CONTEXT 8's F1/F2 with no money-level assertion. The limit was on the build session, not on a reviewer: this review hand-computed both and kept them (PART 4). |
| **B307** `SPEC_VERSION` v1.7→v1.8 | **APPROVED** | Consistent with the constant's contract. See C2 for what v1.9 now implies. |
| **B308** stop-out pool widened to include gap entries | **APPROVED** | The `elif` correctly becomes an `if`, matching the page's unqualified *"of that day's stop-outs"*, and the criterion now says *"all of them, gap entries included"*. Checked for the symmetric defect and there is none: the winners pool still excludes gap entries and **says so on the page** (*"without gapping in"*). |
| **B309** caveat as a computed template | **APPROVED** | Verified byte-exact on both artifacts, with `by_chance(204) = 10` self-computing. |
| **B310** freeze exclusions grow by three, proved | **APPROVED** | Reproduced exactly: 8 tokens out, 0 in, none a metric, `lines_in_sections_1_to_9` unchanged. |
| **B311** third artifact published | **APPROVED** | 204 rows, byte-reproduced in this session, and all 1,836 of its figures independently re-derived. |

---

## PART 4 — TESTS THIS REVIEW ADDS AND KEEPS

`tests/test_review12_2_probes.py` — 52 tests, all green, offline, no store read.

1. **`test_f1_the_round_4_golden_has_a_hand_computed_PnL_of_its_own`** and
   **`test_f2_…`** — **B306's open gap, closed.** Hand-computed from CONTEXT 3.5 before running
   anything. F1: risk 12.00 → `qty = floor(100,000/1,200) = 83` (floor tight: 83×1,200 = 99,600 ≤
   100,000 < 100,800), square-off at 2053, gross `83 × 1,600 = +Rs 1,328.00`, net **+Rs 1,228.00**.
   F2: risk 10.00 → qty **100** (exact, nothing left over), square-off at 2054, gross
   `100 × 1,700 = +Rs 1,700.00`, net **+Rs 1,600.00**. Both note that a square-off pays what the
   day gave, not a multiple of R. CONTEXT §8's F1/F2 now have money attached to them again.
2. **`test_a_gap_stop_is_never_beyond_the_poc_on_either_side`** — the trader's own Round-4
   constraint as a swept property over 49 POCs a quarter-rupee apart, both sides, with a
   non-vacuity guard at the fixtures' own POC.
3. **`test_the_bias_tables_stated_arithmetic_does_NOT_close`** — **PINS Q1**, from the COMMITTED
   companion and page, so the fix turns it red. It also asserts that the true figure (13,111) is on
   no page.

No existing test was modified, weakened, skipped or deleted by this review. No fixture byte moved.

---

## PART 5 — THE FIX LIST

Small, local, and none of it touches the engine, the ledger or a published figure.

1. **Q1** — rewrite the page-5 clause so the reconciliation closes: the 87,192 CONTAINS the
   not-judged rows rather than standing beside them, and 13,111 is the count that had a bias.
   **Update `test_the_bias_rule_tables_population_is_now_STATED_and_reconciles` in the same
   commit**, and flip this review's pin probe.
2. **Q2** — fix `_rule_words`' label for `no-data` to describe the missing DAILY candle on the
   bias pair, and reconcile the "not judged" wording with the 2 evaluated rows.
3. **Q3** — state page 7's 988 flat trades, as page 1 states its 40.
4. **C1** — relabel `config.yaml`'s two keys (and the three surrounding "pending" sentences) as
   *retired by trader, Round 4*, per the ruling and now per CONTEXT v1.9 §3.5.
5. **C2 / C3** — architect's call: `SPEC_VERSION` to v1.9, and §9's OPEN-6 wording.
6. **C4** — give both generators an entry point.

**Nothing here requires a re-run, and no number in the pack, the companion, the points table or
the report moves under any of it.**

---

## VERDICT

**FAIL**, on Q1 and C1.

The engineering is strong and most of this review is a confirmation of it: the six renames are
byte-identical, the four gap numbers hand-derive from §3.4, the points view is provably
size-independent and every one of its 2,116 published figures reproduces exactly, the trader's own
stop constraint holds on all 2,068 gap trades, the freeze is exact, the artifacts byte-reproduce,
the stores were not touched, no test was weakened and the run manifest is honestly frozen.

But chunk 12's deliverable **is the document**, and the document asks a non-technical trader to
check an arithmetic that is out by 74,081, in a paragraph that exists solely to be checked — with
a reviewer probe now holding the wording in place. And an architect ruling was not executed while
two records say it was. Those are the two things this repo's rules exist to catch.

**The trader gate stays OPEN and the pack should not go to him until Q1, Q2 and Q3 are fixed.**

`docs/reviews/REVIEW_12_2.md` · fix session owed · re-review over the fix commits.
