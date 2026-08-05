# REVIEW_9B_FIX4 -- re-review of the chunk-9B FIX-4 span (Q-22 executed)

**Span reviewed:** `6b6baaa..bb2ad60` (7 commits) -- the Q-22 ruling recorded and measured
(`068222d`), CONTEXT **v1.7** (`d66d23e`, architect), Q-22(a) at `candles_for` plus the
REVIEW_9B_FIXES punch list (`df28c08`), Q-22(b) at `trade_evidence` (`7b7702a`), R4's corrected
re-gate command and staleness banner (`28ae68e`, `bb2ad60`), and the FIX-4 PROGRESS/STATUS
entries (`c0d3bb6`).
**Personas:** `personas/quant_reviewer.md` and `personas/code_reviewer.md`, both worked in full.
**Session:** fresh re-review session, 2026-08-05. Focused QC as briefed. **No `src/` file, no
existing test and no fixture was modified.** One new test file was ADDED and kept
(`tests/test_review9b_fix4_probes.py`, 4 probes, each mutation-verified).
**ZERO store writes**: every access to `<data_root>` was a read; no file under it was created,
renamed, moved or deleted; the crashed run directory was read but not touched; the owed re-gate
was NOT run; every mutation ran inside a `git archive` COPY under the scratchpad; no junction or
symlink was created at any point (CLAUDE.md Q-18 layers 1 and 2).

---

## VERDICT

### The span: **PASS**

### The relaunch: **AUTHORISATION GRANTED**

REVIEW_9B_FIXES withheld relaunch authorisation on ONE thing and one thing only: finding R1, the
Rule-3 first-break scan consuming out-of-session bars in breach of CONTEXT 4.6's Q-17 law. The
architect ruled option (a); this span executes it at the one boundary both loaders share, counts
the drop the way Q-17 requires, keeps the gates on the whole stored day the way the same sentence
requires, and measures the whole-population cost instead of sampling it. I re-derived the
decisive claim with my own walk of the shipped `BiasEngine` from the run's own span start, and it
holds. **The condition on which authorisation was withheld is discharged.** I flip that line.

Five findings, **none blocking**: one MEDIUM (a load-bearing line of this span pinned by nothing
-- the exact R5-class defect the previous review named three times), three LOW and one INFO. Two
are closed by probes this review keeps.

---

## 1. THE R1 ADJUDICATION -- the decisive item, walked by me

The question REVIEW_9B_FIXES and FIX-4 disagree on is not whether the days are re-answered (both
agree they are) but whether a **bias** moves. R1's table reads the ruled answer on GODREJCP and
LAURUSLABS 2021-02-25 as **BULLISH**, i.e. two flipped biases. FIX-4 says the probe behind that
table passed the literal string `"BULLISH"` to `evaluate_pair` as the carried bias instead of
walking the carry, that the walked carry is already **bearish** on both, and therefore that **no
bias in the whole span changes**.

That is a claim about the carry, and a carry is path-dependent, so nothing but a walk settles it.

**My method, independent of both.** Two `BiasEngine` instances per symbol -- separate objects,
separate loaders, separate `last_bias` chains -- each walked with `bias_series` from the run's own
span start **2016-10-03** to the trade day, with:

* each symbol's **real** corporate-action factor table and suppressions from
  `backtest.build_factor_tables` (GODREJCP 50 factors incl. two bonuses, ex 2017-06-22 k=1/2 and
  ex 2018-09-12 k=2/3, plus a 2008 rights suppression; LAURUSLABS 19 factors incl. the 2020-09-29
  split k=1/5) -- printed in full in my evidence output, not summarised;
* the run's calendar, with the eight CONTEXT 7-E2 non-standard sessions removed (read read-only
  from the crashed run's own cached `sessions.json`; **2021-02-24 and 2017-04-28 are asserted NOT
  to be among them**);
* loader A = **as shipped at 6b6baaa** (battery first, then a `bias.Candle` for EVERY stored bar),
  loader B = **as ruled** (identical, except `aggregate.in_session_bars` runs first). I wrote both
  loaders myself rather than importing either tree's, so the two halves differ in exactly one
  line and nothing else.

### 1a. What carries into 2021-02-25

| symbol | trade day 2021-02-24 rule | bias produced = carry INTO 2021-02-25 | FIX-4's claim | verdict |
|---|---|---|---|---|
| **GODREJCP** | `rule-1-breakout` | **bearish** | "2021-02-24 rule-1 bearish" | **CONFIRMED** |
| **LAURUSLABS** | `inside-bar-carry` | **bearish** | "2021-02-24 inside-bar-carry bearish" | **CONFIRMED** |

Both walks (shipped and ruled) agree on that carry, and agree on every one of the 1,086 walked
trading days before it. The four preceding days are printed in the evidence for each symbol:
GODREJCP runs `rule-1-breakout` bearish on 02-19, 02-22, 02-23 and 02-24; LAURUSLABS runs
`inside-bar-carry` bearish on 02-19, `rule-1-breakout` bearish on 02-22 and 02-23, and
`inside-bar-carry` bearish on 02-24.

### 1b. What that does to the trade day

| symbol | as shipped | as ruled | bias moves? |
|---|---|---|---|
| GODREJCP 2021-02-25 | `rule-3-outside-bar` -> **bearish** | `rule-3-no-break-carry` -> **bearish** | **no** |
| LAURUSLABS 2021-02-25 | `rule-3-outside-bar` -> **bearish** | `rule-3-no-break-carry` -> **bearish** | **no** |

**ADJUDICATION.** FIX-4's correction is **upheld** and REVIEW_9B_FIXES R1's ">= 2 biases change"
is **refuted**. The RULE change is real and is exactly the ruling's own `-> carry`; the BIAS does
not move, because the carry the day falls back on is the same side the 15:44 print produced. My
walk of GODREJCP over 1,086 trading days finds **1** day where the two walks disagree at all
(2021-02-25, on the rule) and **0** where the bias differs; LAURUSLABS the same. R1's finding was
right about the defect and wrong about one of its numbers, and the correcting session recorded
that rather than quietly dropping it -- which is the right disposal.

Independently of the walk, I re-ran the behavioural tripwire through the **shipped**
`gated_minute_loader` in both checkouts (section 2d): at 6b6baaa it hands the scan 224 candles of
which 77 are out-of-session and answers `rule-3-outside-bar`; at bb2ad60 it hands the scan 147
candles of which 0 are out-of-session and answers `rule-3-no-break-carry`. Same store, same
bytes, same two symbols.

### 1c. The 21 / 2 / 0 table, re-derived on 10 of the 16 symbols

The brief asks for at least 6. I re-derived **11 of the 21 days across 10 of the 16 symbols**,
both halves of every walk, my own arithmetic, each walked from 2016-10-03 with its own factor
table:

| symbol | trade day | D-1 | strays I dropped | carry into D | as shipped | as ruled | bias moves | walk-wide bias disagreements |
|---|---|---|---|---|---|---|---|---|
| GODREJCP | 2021-02-25 | 2021-02-24 | **77** | bearish (`rule-1-breakout`) | `rule-3-outside-bar` -> bearish | **`rule-3-no-break-carry`** -> bearish | no | 0 of 1,086 |
| LAURUSLABS | 2021-02-25 | 2021-02-24 | **77** | bearish (`inside-bar-carry`) | `rule-3-outside-bar` -> bearish | **`rule-3-no-break-carry`** -> bearish | no | 0 of 1,086 |
| COLPAL | 2021-02-25 | 2021-02-24 | 75 | bearish (`inside-bar-carry`) | `rule-3-outside-bar` -> bullish | `rule-3-outside-bar` -> bullish | no | 0 of 1,086 |
| GODREJPROP | 2021-02-25 | 2021-02-24 | 77 | bearish (`inside-bar-carry`) | `rule-3-outside-bar` -> bullish | `rule-3-outside-bar` -> bullish | no | 0 of 1,086 |
| VEDL | 2021-02-25 | 2021-02-24 | 77 | bullish (`rule-1-breakout`) | `rule-3-outside-bar` -> bullish | `rule-3-outside-bar` -> bullish | no | 0 of 1,086 |
| HAVELLS | 2017-05-02 | **2017-04-28** | 1 | bearish (`rule-1-breakout`) | `rule-3-outside-bar` -> bearish | `rule-3-outside-bar` -> bearish | no | 0 of 142 |
| MUTHOOTFIN | 2017-05-02 | **2017-04-28** | 1 | bearish (`inside-bar-carry`) | `rule-3-outside-bar` -> bullish | `rule-3-outside-bar` -> bullish | no | 0 of 142 |
| CDSL | 2019-10-29 | 2019-10-25 | 1 | bullish (`inside-bar-carry`) | `rule-3-outside-bar` -> bearish | `rule-3-outside-bar` -> bearish | no | 0 of 754 |
| PIDILITIND | 2021-12-21 | 2021-12-20 | 1 | bearish (`rule-1-breakout`) | `rule-3-outside-bar` -> bearish | `rule-3-outside-bar` -> bearish | no | 0 |
| RECLTD | 2020-12-30 | 2020-12-29 | 1 | bullish (`rule-1-breakout`) | `rule-3-outside-bar` -> bullish | `rule-3-outside-bar` -> bullish | no | 0 |
| RECLTD | 2021-01-14 | 2021-01-13 | 1 | bearish (`inside-bar-carry`) | `rule-3-outside-bar` -> bullish | `rule-3-outside-bar` -> bullish | no | 0 |

Every row matches `docs/evidence/chunk9b_q22_session_filter.md` section 3 exactly -- the stray
counts, the carry side, both verdicts and the "bias moves: no". Two independent cross-checks of
the population also hold: I counted the evidence's own table and it really is **21 days over 16
distinct symbols** (8 on 2021-02-24, 4 on 2017-04-28, 2 on 2019-10-25, 1 on 2021-12-20, 6
RECLTD); and those per-date counts **agree with REVIEW_9B_FIXES R1's independently sampled
"8 reach Rule 3" on 2021-02-24 and "4 reach Rule 3" on 2017-04-28**. Two measurements taken by
different sessions with different methods land on the same integers.

**Method note, in the evidence script's favour.** `chunk9b_q22_session_filter.py` decides Rule-3
reachability with a probe fed the SHIPPED carry only, which would be unsound if the two carries
could diverge. I checked `bias.evaluate_pair` and Rule-3 reachability is decided purely by pair
geometry (the inside-bar test, Rule 1's close test, Rule 2's sweep test) -- `last_bias` is read
only to BUILD a carry result, never to select a rule. So the probe's answer is carry-independent
and the asymmetry cannot bite. My own walk does not share the shortcut and agrees anyway.

---

## 2. THE FILTER -- every directed check, with its result

**2a. `candles_for` drops the strays and returns the count (B263).** PASS.
The filter is the first statement of the function, before a single `Candle` is constructed, and
the signature is `-> tuple[tuple[Candle, ...], int]`. Both loaders in `backtest.py` route through
it and nothing else in `src/` builds a scan candle from a raw bar except
`minute_backfill.minute_loader`, which carries the same filter (my own scan; see probe FIX4-P4).
On the real store: GODREJCP/LAURUSLABS 2021-02-24, 224 stored bars -> 147 candles, `dropped == 77`,
every surviving stamp inside 09:15..15:29.

**2b. The gates still see the UNFILTERED day -- arithmetic re-run by me.** PASS, and this is the
most load-bearing ordering in the span.
The shipped fixture test asserts the gates' INPUTS, and its arithmetic checks out by hand: the
five stored bars carry 12,909 + 300 + 200 + 100 + 100 = **13,609** shares, of which the three
session bars carry 12,909 + 300 + 200 = **13,409** (delta 200 = the two strays); the stored day's
fold is `[min low, max high] = [197500, 200500]` and the session's is `[198000, 200000]`; both
match the test's literals exactly.

I then re-derived it on the **real** outage day, where the two readings do not both pass:

| symbol | gate-1 volume, WHOLE day | gate-1 volume, FILTERED | gate-1P fold, WHOLE | gate-1P fold, FILTERED | gate 2 `out_of_session` | refusal WHOLE | refusal FILTERED |
|---|---|---|---|---|---|---|---|
| GODREJCP 2021-02-24 | **1,054,365** | 847,018 | `[67600, 69890]` | `[68000, 68885]` | 77 (passed) | **None** | **gate 1: gap 23.089% above [-0.1, 5.0]** |
| LAURUSLABS 2021-02-24 | **808,637** | 646,819 | `[35810, 36400]` | `[35915, 36400]` | 77 (passed) | **None** | **gate 1: gap 22.421% above [-0.1, 5.0]** |

So filtering before gating would not merely lose a counter: it would turn the two days the whole
Q-22 question was raised about into `minutes-ungated` REFUSALS. The order the code uses is the
only order that reproduces the ruling. CONTEXT 4.6's *"gates still see the whole stored day for
volume (NSE daily volume includes auctions)"* is doing real work here, and the implementation
obeys it.

I mutation-tested the ordering itself -- `gate_day` fed `in_session_bars(bars)` instead of `bars`
-- against the full shipped suite: **1 failed / 2,110 passed**. It IS caught, but only
incidentally, by the flipped R1 tripwire, which raises `UngatedMinuteDay` on GODREJCP before
reaching its own subject. No shipped test asserts the ordering *as* the ordering, or records what
reversing it costs. Kept probe FIX4-P2 does both (section 9). That is a strengthening, not a
closed gap -- stated as such.

**2c. The shared drop ledger counts DAYS once per row (B264/B265).** PASS, verified on the real
store rather than the fixture. Walking GODREJCP 2021-02-18..2021-02-26 through
`build_runner -> gated_minute_loader -> walk_symbol`:

* one recorded scan drop, `{GODREJCP 2021-02-24: 77}` -- keyed on **D-1**, not the trade day;
* two rows carry `FLAG_OUT_OF_SESSION_DROPPED`: 2021-02-24 (its own 15-minute feed) and
  2021-02-25 (its Rule-3 scan of D-1);
* each row carries it **exactly once**; manifest counter = **2**.

77 stray bars x two consumers = 154 bar-events, reported as **2 DAYS**. A clean window
(2021-03-08..12) records no drop, flags no row and prints **0**. `build_runner` creates one
`Rule3SessionDrops` and passes the same object to both the loader and the runner (read in source
and pinned by the shipped `test_q22_build_runner_shares_ONE_drop_ledger_...`).

I also traced whether a recorded drop can go uncounted. It cannot on the run path: `_row` is
called for every day with a resolvable bias, including days the trading gates refuse, so the flag
survives a refused-but-evaluated day; and every path that skips `walk_day` (a non-standard
session, a non-trading day, a `bias is None` day, a `minutes-ungated`/`minutes-malformed` refusal)
is a path where the loader either was never called or RAISED before `candles_for` returned, so no
drop was recorded to lose.

**2d. The tripwire probe: RED at 6b6baaa, GREEN at HEAD, in my own checkouts.** PASS.
Running HEAD's probe file inside a `git archive 6b6baaa` tree fails -- but on a `ValueError: too
many values to unpack`, i.e. on the signature, which proves less than it looks. I therefore wrote
a signature-agnostic behavioural version that never unpacks `candles_for` and asks the RUN's own
gated loader what it hands the scan. Result, over the real store, same script both sides:

```
AT 6b6baaa : GODREJCP   224 stored, 77 out-of-session -> loader handed the scan 224 candles,
                        77 of them out-of-session -> rule 'rule-3-outside-bar'   [CONSUMED]
             LAURUSLABS same                                                     [CONSUMED]
             VERDICT: RED (strays consumed)                                       exit 1
AT bb2ad60 : GODREJCP   224 stored, 77 out-of-session -> loader handed the scan 147 candles,
                        0 of them out-of-session -> rule 'rule-3-no-break-carry'  [DROPPED]
             LAURUSLABS same                                                      [DROPPED]
             VERDICT: GREEN (Q-17 obeyed)                                          exit 0
```

The flip is behavioural, not a test rewrite.

**2e. The unfiltered-scan mutant is caught.** PASS. Reverting `candles_for` to build a candle for
every stored bar (`session, dropped = bars, 0`) in a `git archive bb2ad60` copy: **6 failed /
2,105 passed**, exactly the count FIX-4 claims, across
`test_q22_a_stray_only_break_carries_...`, `..._a_stray_on_a_day_whose_session_bars_DO_break...`,
`..._candles_for_drops_the_strays_and_returns_the_count`,
`..._the_third_case_is_now_unreachable_through_the_gated_loader`,
`..._the_manifest_counts_the_out_of_session_drop` and the flipped R1 tripwire. Source restored and
re-verified sha256-identical to the committed blob (`8bc5377c...a201fd4`) afterwards.

The other two claimed mutants reproduce exactly too: the **unflagged-scan-drop** mutant
(`scan_dropped = False`) fails **3**; **R3's exact mutant** (suppress the flag on a
malformed-bar refusal only, leaving the day refused and the reason right) fails **exactly 1** --
`test_q21_the_third_case_still_reaches_the_ledger_flagged_and_counted`, the test written for it.
R3 is CLOSED.

---

## 3. Q-22(b) -- `trade_evidence`

**3a. It reaches `bt.gated_minute_loader` itself and the private copy is GONE.** PASS, by my own
AST rather than by grep:

* function definitions in `trade_evidence.py` no longer include `_minute_loader` (`False`);
* inside `build_context`, the `BiasEngine(...)` call's `minute_loader=` keyword unparses to
  exactly `bt.gated_minute_loader(minute_store, pipeline)`;
* **zero** `Candle(...)` constructions remain anywhere in the module;
* the only backtest import is `from . import backtest as bt`, and `backtest` does not import
  `trade_evidence` -- no cycle.

**3b. The pack's figures re-derived through the gated path, to the paisa.** PASS -- and I did it
the way the brief asks, by regenerating to a scratch path and diffing, not by reading the test.

`python -m acumen.trade_evidence --out <scratch>` under HEAD reproduces **290 walked / 146 entered
/ 146 executed**, the 146/88/56 partition, **53,750 shares**, **gross Rs 12,665.05**, **costs
Rs 14,600.00**, **net -Rs 1,934.95**, winners/losers 45/101/0, exits 36 square-off / 86 stop / 24
target, all rare shapes 0, and all eight invariants PASS with 0 violations. Diffed token by token
against the committed `docs/evidence/chunk8_sweep.md`: **the numeric token streams are identical
except for one date, and the file lengths are equal to the character (26,073 = 26,073)**.

**3c. `chunk8_sweep.md` correctly NOT regenerated.** PASS, and I can put it more strongly than
FIX-4 does. I regenerated the pack at **6b6baaa** (the private ungated loader) as well and diffed
the two regenerations:

```
diff chunk8_sweep_BASE.md chunk8_sweep_REGEN.md  ->  IDENTICAL byte for byte
```

**The Q-22(b) gating moves nothing at all in the chunk-8 pack** -- not a number, not a byte. The
decision not to regenerate is right, and the committed pack's two differences from a fresh
regeneration are both PRE-EXISTING and neither is a number:

1. the instrument-master disclosure names the cached `OpenAPIScripMaster_2026-07-28.json` while a
   regeneration today names the Q-20 pin `..._2026-07-31.json` (the cache rotated; no figure moves,
   as the identical numeric streams prove);
2. one sentence -- *"Arithmetic check: net = gross - cost ..."* -- sits after the rare-shape table
   in the committed file and before it in a regeneration. `render_markdown` is untouched by this
   span, so this is REVIEW_8's own LOW finding ("the committed pack is not byte-reproducible from
   its own generator: one sentence's position, no number moves") still standing, not new damage.

Recorded as INFO I1 below so a later session does not rediscover it as a Q-22 effect.

---

## 4. THE PUNCH LIST

**R3 -- the suppressed-flag mutant dies.** PASS. Run, not assumed: see 2e. Exactly 1 failure, and
it is the new end-to-end `walk_symbol` test R3 asked for. That test deliberately wires the BARE
loader via a new `make_runner(minute_loader=...)` override, and I checked the override's blast
radius: it is used by **exactly one test in the whole suite**, its docstring says why (after
Q-22(a) the gated loader cannot reach the case at all), and `build_runner`'s own wiring is still
pinned by REVIEW_9B_FIXES' kept R2 probe. The escape hatch is narrow and disclosed.

**R9(i) -- the pilot ledger digest.** PASS, hashed by me.
`<data_root>/backtests/chunk9a_pilot_a/ledger.jsonl` is still
`c3363f6f17757ebcbb2f08e8159e943cbbd692836d165687cbb2d91e22c1e318`, as are
`chunk9a_resume_whole` and `chunk9a_resume_killed`. Stronger: I re-serialised **all 290 committed
rows through the SHIPPED `LedgerRow.from_dict -> to_json`** and the output is **byte-identical to
the committed file**, hashing to the same `c3363f6f...`. So B266's conditional serialization is
not merely "the file has not been rewritten" -- the current code would rewrite it identically.
No committed row carries a `detail` key (0 of 290). A detail-carrying row round-trips: the key is
present when set, absent when `None`, and `from_dict(json.loads(to_json()))` equals the original.

**R9(ii) -- no "gate gate" anywhere.** PASS. Every hit in the tree is prose recording the defect
(REVIEW_9B_FIXES, PROGRESS, STATUS, one `bias_engine` docstring) or a test asserting its absence.
Rendered live for all three battery names: `"...refused by gate 2 (candle integrity) reason ..."`,
`"...refused by gate 1 (volume reconciliation)..."`, `"...refused by gate-1P (per-day price
containment)..."` -- none doubled.

**R9(iii) -- the import guard, proved on a subclass I defined.** PASS. Declaring
`class ReviewerFifthCase(UnusableMinuteEvidence)` with `rule = "minutes-invented-by-the-reviewer"`
and no flag:

* `unusable_evidence_rules()` grows to include it;
* `_unflagged_unusable_rules()` -- the predicate the module-level guard reads -- **names it**;
* re-running the guard body raises `BacktestError: ... with no ledger flag:
  minutes-invented-by-the-reviewer`;
* `unresolved_flag(rule)` raises a NAMED `BacktestError`, not `KeyError`, and its message says
  what to add and where;
* discovery is **recursive** -- a subclass two levels down (`DeeperStill(ReviewerFifthCase)`) is
  found as well, which the `__subclasses__()` walk earns rather than assumes.

**R9(iv) -- the counter reads DAYS, not bars.** PASS, on the real store: 2 on the outage window
(77 stray bars, two consumers), 0 on a clean window, one occurrence per row. Full numbers in 2c.

**R4 -- the corrected re-gate command, dry-run.** PASS, parsing and universe resolution only; no
`--regate` was executed and nothing under `<data_root>` was written.

| | parsed | universe resolved | report path |
|---|---|---|---|
| banner's command | `regate=True`, `universe_snapshot='docs/recovery/sealed_universe_210.json'` (file exists), `report_path=<scratch>`, `allow_network=False` | **210** | scratch |
| bare `--regate` | `universe_snapshot=None`, `report_path='docs\backfill_minute_report.md'` | **208** | **the committed sealed report** |

The 2 symbols the bare command would silently leave behind are **exactly `EXIDEIND` and
`NUVAMA`**, and `Path(bare.report_path) == ub.DEFAULT_REPORT_PATH` is `True`. R4's two defects
reproduce from the machine and the corrected command is right.

**The banner's direction statement.** PASS. It now says the stale rows' numbers came from a
SUPERSEDED definition, that the bump in force *"can only turn passing days into failures and moves
no gate-1P number at all"*, and therefore that the printed coverage is **OVERSTATED**, not
understated; the old claim is deleted rather than hedged, and the banner prints both mandatory
flags with the snapshot path read from `SEALED_UNIVERSE_SNAPSHOT`. The direction is correct on its
own terms: adding a violation clause to gate 2 is monotone (it can only fail more days), and
`quality_gates.py` is byte-identical across this span so gate 1P cannot have moved. See LOW L3 for
the one residual.

---

## 5. CONTEXT v1.7

**5a. `d66d23e` = CONTEXT.md alone, and exactly the listed edits.** PASS on substance.
`--numstat` shows `18 11 CONTEXT.md` and `--name-only` lists **CONTEXT.md and nothing else**.
There are **five** hunks and they are the five edits the commit body enumerates: the header
`1.6 -> 1.7`; the SUPERSEDES marker on the v1.5 RE-SEALED passing/coverage pair; the Q-17 bullet's
new universality sentence; the population correction inside the Q-21(a) COMPLETION paragraph; and
§10's new top row. No sixth edit, no incidental whitespace.

**The literal architect template is not in the repo** -- only the ruling is -- so a true byte-check
still needs the operator to paste it. The five hunks above are what to compare, and every
substantive value in them traces to the ruling or to a measurement I reproduced (below). This is
the same caveat REVIEW_9B_FIXES check 4b recorded for v1.6; it is not this session's to close.

**5b. The population arithmetic, checked against the STORE.** PASS.
CONTEXT v1.7 now reads *"51 -- 48 on the settled 204 (47 on 2023-03-03 09:15 market-wide, 1 JIOFIN
2023-08-21) plus APLAPOLLO x2 and UPL on the quarantined side, one of which (APLAPOLLO 2017-10-05
15:28) was already refused under the sealed close-only enumeration and is therefore invisible to a
flip-derived count."* I re-read all three quarantined bars:

| bar | O / H / L / C / V | `high<low` | CLOSE outside | OPEN outside | visible to the SEALED (close-only) enumeration? |
|---|---|---|---|---|---|
| APLAPOLLO 2017-10-05 15:28 | 1876000 / 1876000 / 1876000 / 1875000 / 0 | no | **yes** | no | **YES -- already refused** |
| APLAPOLLO 2023-03-03 09:15 | 125625 / 126735 / 125680 / 126635 / 2692 | no | no | **yes** | no |
| UPL 2023-03-03 09:15 | 70900 / 71400 / 70905 / 71190 / 16802 | no | no | **yes** | no |

48 + 2 + 1 = **51**, and **exactly one** of the three was already refused under the sealed
enumeration -- which is precisely why a flip-derived count could never see it. The sentence is
correct as written, including its parenthetical.

**5c. §10's measured values.** The row records *"21 Rule-3 days re-answered, 0 biases changed"*.
Both figures are the ones I re-derived in section 1 (11 of the 21 days by full walk; 21/16
recounted from the evidence table; 0 bias changes on every day I walked, and 0 divergences over
1,086, 754 and 142 walked days on the symbols I walked in full).

**5d. `SPEC_VERSION` v1.7 on the CODE commit; `GATE_DEFINITION` unbumped.** PASS, both against
their own contracts.

* `SPEC_VERSION` moves to `"v1.7"` in **`df28c08`**, the code commit -- not in the architect's
  spec commit, which touches CONTEXT.md alone. Its contract is *"a ledger always names the law it
  was produced under"*. Q-22(a) changes which BARS decide a bias and therefore what a ledger row
  can say -- demonstrated, since `bias_rule` really does move on 2 rows -- so the bump is
  compelled, exactly as the v1.6 bump was.
* `GATE_DEFINITION` is byte-identical at both ends of the span
  (`gate1p-price-containment+gate2-completeness+auction-relief-2026-07-28+gate2-open-test-2026-08-03`).
  Its contract is *"the gate DEFINITION a ledger row's numbers were produced under"*, and moving it
  re-opens all 210 stored rows for re-gating. **No gate definition moved**: `quality_gates.py` is
  byte-identical, no gate consumes `candles_for`, and `in_session_bars` is called by exactly three
  modules -- `signal_engine` (pre-existing), `minute_backfill` and `backtest` -- none of them on a
  path `universe_backfill`'s re-gate reads. Not bumping is correct; bumping would have owed the
  operator a second, pointless whole-universe re-gate.

---

## 6. Class-B decisions B263 to B270 -- one line each

| # | verdict | one line |
|---|---|---|
| B263 | **APPROVED** | `candles_for` is the single boundary both loaders already shared, so the ruling lands once and the gated and ungated paths cannot diverge; returning the count rather than swallowing it is literally what *"flagged and counted, never silently"* requires, and my own scan confirms no third builder exists in `src/`. |
| B264 | **APPROVED** | The scan reads D-1 but the only row that exists is the trade day's, so the count HAS to travel loader -> runner; `Rule3SessionDrops` is per-run, in memory, keyed `(symbol, D-1)`, never persisted (CONTEXT 4.6 forbids a per-day exclusion file) and never an input to a decision -- verified on the real store, one entry, correct key. |
| B265 | **APPROVED** | The EXISTING `FLAG_OUT_OF_SESSION_DROPPED`, set at most once per row, so the new counter counts DAYS and a reader can still recompute it from the committed ledger alone: 77 strays x 2 consumers reported as 2, one occurrence per row, 0 on a clean window. |
| B266 | **APPROVED** | `detail` serialised only when set. Proved rather than argued: re-serialising all 290 committed pilot rows through the shipped code reproduces the file byte for byte and hashes to `c3363f6f...` unchanged. Confining the stable-key change to the two Q-21 reasons -- leaving the pre-existing ones alone because they are in a committed ledger -- is the conservative call and the right one. |
| B267 | **APPROVED-WITH-CHALLENGE** | The DECISION is right: the ruling says *"every consumer"*, and leaving the module the repo calls "the REAL implementation" unfiltered would be a live inconsistency waiting to be wired. The EXECUTION shipped unpinned -- reverting the filter leaves the whole suite green (finding F1). Not a wrong line; an unguarded one, in a span whose own previous review named that failure mode three times. **Closed by kept probe FIX4-P1.** |
| B268 | **APPROVED** | Compelled by `SPEC_VERSION`'s own contract, and the paired judgement -- `GATE_DEFINITION` deliberately NOT bumped -- is equally right and independently verified (5d). Bumping the wrong one of these two constants would have cost the operator a whole-universe re-gate for nothing. |
| B269 | **APPROVED** | Keeping Q-21's third case now that it is unreachable through the gated loader is defence in depth, not dead code: `BiasEngine` catches `UnusableMinuteEvidence`, not one subclass. Deleting reviewed machinery on a reachability argument is exactly the quiet narrowing this repo forbids, and the case now has the end-to-end coverage R3 asked for. |
| B270 | **APPROVED-WITH-NOTE** | The banner naming the direction of the bump actually in force beats a generic sentence that was simply wrong, and it is now pinned by a test. NOTE: it still ASSERTS a direction it cannot COMPUTE, so it goes stale again on the next `GATE_DEFINITION` move; the constant's comment says so and the decision records it, which is the disclosure this repo asks for (LOW L3). |

---

## 7. Findings

**Severity:** HIGH = blocks. MEDIUM = must be recorded/actioned, does not block. LOW/INFO = noted.

### F1 -- MEDIUM -- B267's session filter is pinned by nothing; reverting it leaves the suite green

`minute_backfill.minute_loader` -- which this module's own docstring calls *"the REAL
implementation of the `MinuteLoader` interface"* -- gained the Q-22(a) filter under B267 because
the ruling binds *"EVERY consumer of stored minute bars"*. Deleting `session, _dropped =
in_session_bars(bars)` and iterating `bars` again, in a `git archive bb2ad60` copy, leaves the
**entire suite green -- 2,111 passed / 0 failed**, measured, not estimated. No test anywhere sees
the difference: the three tests that exercise this loader use two-bar in-session fixtures.

This is precisely the R5-class defect REVIEW_9B_FIXES found three times in the previous arc, and
this session even shipped a whole commit (`bb2ad60`) closing R4's other half *for that reason* --
then left its own new line unguarded.

**It cannot move a number today**: I grepped every caller and `minute_backfill.minute_loader` is
reached from no module in `src/` and no script in `scripts/` -- only from `tests/`. That is exactly
why nothing noticed, and exactly why an unpinned consistency fix rots: the day someone wires this
loader (it is the interface implementation, so that day is plausible) the drift is silent.
**Does not block the relaunch** -- the relaunch runs `backtest.gated_minute_loader`, which is
pinned six ways.
**CLOSED by kept probe** `test_the_third_rule3_loader_drops_out_of_session_stamps_too`
(mutation-verified: fails on the reverted filter, passes on restoration).

### F2 -- LOW -- a new test carries an assertion that cannot fail

`tests/test_backtest.py::test_r9_every_unusable_evidence_case_is_flagged_and_the_gap_fails_LOUDLY`
contains

```python
for flag in bt.UNRESOLVED_FLAG_BY_RULE.values():
    assert any(flag in label or label for label in bt.RARE_SHAPE_LABELS)
```

`label` is a non-empty string, so `flag in label or label` is truthy for **every** flag. I
confirmed the vacuity directly: the same expression returns `True` for the literal
`"ZZZ-not-a-flag"`. The intended claim is also false as written -- the flag strings are not
substrings of the labels; they are separate namespaces joined by a hardcoded pair list inside
`rare_shape_counts`, so had the `or label` been dropped the assertion would FAIL on both real
flags.

The property itself is genuinely covered, behaviourally, by REVIEW_9B_FIXES' kept probe
`test_every_unusable_evidence_rule_has_a_flag_and_that_flag_is_a_rare_shape`, so this is **not a
coverage hole** -- it is a dead assertion that reads as coverage in a test whose whole subject is
"a gap must fail loudly". **CLOSED by kept probe**
`test_every_unresolved_flag_actually_increments_a_manifest_counter`, which states the property
behaviourally, extends it to the flag Q-22(a) added, and carries the negative control that makes
it mean something.

### F3 -- LOW -- a shipped docstring still states the opposite of the ruling this span executed

`tests/test_backtest.py::test_q21_the_manifest_counts_the_rare_shape` still says:

> *"the Q-21 case remains reachable for a malformed bar gate 2 never inspects (an out-of-session
> stamp -- CONTEXT 7-E2 / Q-17)"*

After Q-22(a) that is false: an out-of-session stamp is dropped before a candle is built, which is
the ruling's own prediction and which this span asserts elsewhere
(`test_q22_the_third_case_is_now_unreachable_through_the_gated_loader`). Its sibling
`test_q21a_the_crash_day_now_refuses_under_GATE_2s_own_name` had exactly the same sentence and was
correctly updated; this one was missed. I grepped the whole tree: it is the **only** stale
reachability claim left in `src/` or `tests/` (the one hit in QUESTIONS.md is historical narration
of what the previous review was doing, and is correct in context).

Behaviourally harmless -- the assertions are right and green -- but it is a sentence a later
session will read as current, and REVIEW_9B_FIXES R3 was itself about a PROGRESS claim of coverage
that did not exist. **Owed to the next builder session, one line.**

### F4 -- LOW -- "four edits, no fifth" describes a five-edit commit

`d66d23e`'s message body opens *"Four edits, no fifth:"* and then enumerates **five** numbered
edits; the diff has **five** hunks. The same "four edits, no fifth" phrasing is repeated in
`STATUS.md` line 29. (PROGRESS.md's `files:` line lists all five correctly and makes no count
claim.)

The phrase was correct for CONTEXT v1.6, whose commit really did make four edits and whose review
verified "exactly four hunks"; it was carried forward without re-counting. Nothing substantive
follows -- I verified the commit touches CONTEXT.md alone and makes exactly the five listed edits
-- but a commit message is immutable history and a future session auditing the spec chain against
that sentence would be counting to the wrong number. **STATUS.md is editable and should be
corrected by the next session; the commit message stands as history.**

### F5 -- LOW -- one comment names the wrong test file

`src/acumen/trade_evidence.py`'s new block comment says the condition is asserted by
*"`tests/test_trade_evidence.py`"*. The tests are in `tests/test_q22_trade_evidence_gating.py`.
Cosmetic; a reader following the pointer lands nowhere.

### I1 -- INFO -- the committed chunk-8 pack is stale in two non-numeric ways, and neither is this span's doing

Recorded so a later session does not mistake either for a Q-22(b) effect. A regeneration today
differs from the committed `docs/evidence/chunk8_sweep.md` only in (1) the instrument-master
disclosure (`2026-07-28` vs the Q-20 pin `2026-07-31`) and (2) the position of one sentence --
REVIEW_8's own LOW finding, still standing. **Proved not to be this span's doing:** regenerations
at 6b6baaa and at bb2ad60 are byte-identical to each other. Every number is unmoved.

---

## 8. Standard sweep

**Suite from clean.** `.pytest_cache` and every `__pycache__` deleted first: **2,111 passed / 0
failed / 0 skipped** (365.9 s) -- exactly the count FIX-4 claims. With this review's 4 kept probes:
**2,115 / 0 / 0**. No skip anywhere; the store-backed probes do not skip on this machine.

**No test weakened.** Top-level test names diffed across the span: **1,422 -> 1,439, net +17**, with
**exactly one** name removed -- `test_the_rule3_scan_consumes_out_of_session_bars_and_it_flips_a_
REAL_bias`, renamed to `..._DROPS_out_of_session_bars_on_the_real_outage_day`, which is the flip
its own docstring promised. AST counts: functions 1,848 -> 1,870, assertions 3,731 -> 3,828,
`pytest.raises` 245 -> 246; the single apparent function "loss" is an inner `candles()` helper the
flipped probe no longer needs, and that file's assertions rose 36 -> 38.

**Every modified pre-existing test audited line by line** (six functions plus the `make_runner`
helper). All are gains or compelled value updates:

| function | change | verdict |
|---|---|---|
| `make_runner` (helper) | gains a `minute_loader=` override and shares a `Rule3SessionDrops` | used by **1** test, which documents why; `build_runner`'s wiring still pinned by the R2 probe |
| `test_q21a_the_crash_day_now_refuses_under_GATE_2s_own_name` | `reason` -> `reason` + `detail` | 1 assertion -> 2. GAIN |
| `test_q21b_a_battery_failing_D1_refuses_the_trade_day_and_counts_it` | reason/detail split + "no symbol, no date in the KEY" | 2 -> 4. GAIN |
| `test_q21b_the_gated_loader_refuses_a_battery_failing_day_and_names_the_gate` | wording + `"gate gate" not in` | GAIN |
| `test_q21b_a_battery_failing_D1_makes_the_day_unresolvable_and_never_raises` | wording + `"gate gate" not in` | GAIN |
| `test_the_manifest_carries_the_spec_version_...` | `"v1.6"` -> `"v1.7"` | compelled by B268; same strength |
| `test_the_q21b_disclosure_names_the_ruling_...` | `SPEC_VERSION == "v1.7"`, radius still v1.6 | compelled; same strength, and the comment explains why the radius does NOT move |

**Fixtures frozen.** `git diff 6b6baaa..bb2ad60 -- tests/fixtures poc` is empty and the working
tree is clean under both paths.

**Pure engines byte-identical** across the span, by blob SHA: `bias`, `poc`, `signals`, `simulate`,
`aggregate`, `quality_gates`, `portfolio`, `corp_actions`, `minute_store`, `daily_store`,
`signal_engine`, `calendar` -- all 12 unmoved. Exactly **five** `src/` files changed, all named in
PROGRESS.

**Commit hygiene.** Exactly the four commits touching `src/` or `tests/` carry `(unreviewed)`; the
three docs-only commits correctly do not (REVIEW_7 C1). `d66d23e` is `spec:`-prefixed,
architect-authored and touches CONTEXT.md alone. Every message carries a body explaining what and
why with its chunk and spec citation. Linear, no merges.

**No AI attribution** anywhere in the span's messages or diffs (the only matches are the filename
`CLAUDE.md`, which CLAUDE.md permits). **No secrets**: `.env` appears in **0** commits in the whole
history; no credential-shaped literal is added by the span (the single grep hit is the word
"secrets" inside the previous review's own STATUS prose). **No hardcoded symbol or date** reaches
production logic in any of the five changed modules (my own AST sweep: 0 suspicious literals).
**No float equality and no bare `except`** introduced.

**SHA chain.** Every 7- and 40-hex token cited in the span's prose resolves to a commit, except two
that are digest fragments (`b29f5ab` is the tail of the instrument master's sha256; `0000119` is a
figure). `HEAD == origin/main == bb2ad60` -- the FIX-4 session pushed.

**Evidence rule (REVIEW_7 C3).** This session makes claims from real store data, so its generating
scripts and their outputs are committed under `docs/evidence/`.

---

## 9. Kept probes

`tests/test_review9b_fix4_probes.py` -- 4 tests, all green, added and kept by this review. Each
was mutation-verified in a `git archive` copy: it fails on its mutant and passes on restoration.

| probe | mutant it kills | finding |
|---|---|---|
| `test_the_third_rule3_loader_drops_out_of_session_stamps_too` | B267's filter reverted in `minute_backfill.minute_loader` -- **survives the whole shipped suite, 2,111 passed** | F1 |
| `test_the_battery_is_fed_the_WHOLE_stored_day_and_the_order_is_load_bearing` | `gated_minute_loader` gates the FILTERED day -- which refuses GODREJCP and LAURUSLABS 2021-02-24 on gate 1. A STRENGTHENING, not a gap: the shipped suite already catches this mutant, but incidentally (1 failure, in the R1 tripwire) and without recording what it costs | 2b |
| `test_every_unresolved_flag_actually_increments_a_manifest_counter` | the Q-17 flag dropped from `rare_shape_counts`' join list | F2 |
| `test_no_module_outside_backtest_builds_its_own_rule3_candles` | a third private Rule-3 candle builder appearing in another module -- the Q-22(b) failure mode, from the general side | -- |

---

## 10. What is owed, and by whom

**ARCHITECT:** nothing blocking. Two items for the eye only: the v1.7 template byte-check needs the
operator/architect to paste the literal template (5a); and REVIEW_9B_FIXES R1's ">= 2 biases
change" is now formally refuted by two independent walks (section 1) -- the CONTEXT §10 row's
"0 biases changed" is the reading that survives.

**OPERATOR (before the relaunch), unchanged from REVIEW_9B_FIXES:**
1. rename -- never delete -- `<data_root>/backtests/chunk9b_full` to `chunk9b_full_crashed_0803`;
2. **snapshot `data/` and `cache/` offline**, two generations, the new one verified before the old
   is replaced (CLAUDE.md data-store safety).

Then `python scripts/run_backtest.py`, no flags, under the unchanged pin
`OpenAPIScripMaster_2026-07-31.json`. The ledger it writes will carry `spec_version v1.7`.

**OPERATOR (a data session, safe either side of the relaunch):** the owed offline re-gate, now
documented in full as step 7 of `docs/recovery/q18_runbook.md`, with both mandatory flags. I
dry-ran its parsing and it resolves the sealed 210.

**BUILDER (next chunk-9B session), all LOW:** correct the stale docstring in
`test_q21_the_manifest_counts_the_rare_shape` (F3); correct STATUS.md's "four edits, no fifth"
(F4); repoint the comment in `trade_evidence.py` to `tests/test_q22_trade_evidence_gating.py` (F5).
Optionally delete the dead assertion F2 names, now that a real one stands beside it.

---

## VERDICT: **PASS**. **RELAUNCH AUTHORISED.**

The architect's Q-22(a) and Q-22(b) rulings are executed faithfully, narrowly and at the right
boundary. The one thing REVIEW_9B_FIXES withheld authorisation for is fixed, and I proved it fixed
from the store in two independent ways rather than taking the fix session's word for it. The one
figure of that review which did not reproduce has been corrected in public with the correction
recorded rather than buried, and my own walk confirms the correction. Nothing in the span moves a
committed number, a fixture byte or a published digest.

I would let this code write the definitive ten-year ledger.

Reviewer: chunk-9B FIX-4 re-review session, 2026-08-05.
Suite at close: **2,115 passed / 0 failed / 0 skipped** from clean (2,111 shipped + 4 kept probes).
