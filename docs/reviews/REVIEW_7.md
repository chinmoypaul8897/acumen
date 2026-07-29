# REVIEW_7 — chunk 7 · signal engine (CONTEXT §3.4) · type QC (both personas)

**Session:** fresh review session, 2026-07-29. **Span reviewed:** `c941c64..0209f17` — the two
architect spec commits (v1.3, v1.4), the chunk-7 prep, the build, and the Q-15 fix.
**Personas:** `personas/quant_reviewer.md` + `personas/code_reviewer.md`, both in full.
**Everything below was run offline and read-only against the stores.**

---

## VERDICT: **PASS**

The state machine is CONTEXT §3.4 character for character. I reimplemented §3.4 from the spec
text importing nothing from `src/acumen` and it reproduces F1, F2, F3, F4 and every short mirror
to the paisa; I recomputed the HDFCBANK 2026-06-10 walk end to end — bias, all three gates, the
POC and the trade — from the parquet stores with my own §3.2/§3.3/§3.4 arithmetic and every
number the architect's directed check names came back exact; the 290-day sweep reproduces
146/88/56 with zero exceptions and zero invariant violations; and a 52-mutant matrix over the
strictness of every comparison in §3.4 leaves **no surviving mutant that changes a trade** — 41
killed by the build's own suite, 9 more by six probes this review adds and keeps, and 2 proved
EQUIVALENT rather than uncaught.

**1396 passed / 0 failed** from a genuinely clean state (every `__pycache__` and `.pytest_cache`
deleted first) = the build's 1390 plus this review's 6 kept probes.

Findings: **two MEDIUM** on the quant side, both real coverage gaps in boundary operators that
move money, both **CLOSED by kept reviewer tests in this commit**; **two LOW + four INFO**
otherwise. **No CONTEXT.md deviation. No weakened, deleted or skipped test. No fixture byte
changed. No secret. No look-ahead.** Nothing here needs a fix session.

---

## 1. Architect's directed checks

| # | Check | Result |
|---|---|---|
| 1 | PREP AUDIT: v1.3/v1.4 byte-exact; seven receipts; both gate closures; the OPEN-4 tie change, its three F5 sub-fixtures, the retired colour tests, the re-pinned probes, and the tie predicate mutation-tested | **PASS** — §2 |
| 2 | STATE-MACHINE MUTATION MATRIX | **PASS** — §3. 52 mutants: 50 caught, 2 proved equivalent, 0 surviving |
| 3 | F1–F4 + all short mirrors recomputed BY HAND | **PASS** — §4. All seven exact, incl. F3's SL-at-HIGH / TP 1956 and the Q-15 risk-floor proof |
| 4 | THE HDFCBANK 2026-06-10 WALK, independently | **PASS** — §5. Every stated number reproduced from the stores |
| 5 | THE 290-DAY SWEEP re-run + 2 extra spot-walks + the factor-table disclosure | **PASS** — §6. 146/88/56, 0 exceptions; the empty table proved *correct*, not merely convenient |
| 6 | PURITY: AST, Fraction end-to-end, float refusal, the B154 grid pin | **PASS** — §7 |
| 7 | Judge B154–B165 | **All APPROVED** — §9 (B166–B168 judged too) |
| 8 | STANDARD SWEEP | **PASS**, with 2 LOW + 2 INFO — §10 |

---

## 2. Prep audit

### 2a. The two spec commits

Both spec commits touch **`CONTEXT.md` and nothing else** (`c941c64`: 1 file, 33+/19−;
`7d4757e`: 1 file, 4+/3−). I cannot byte-diff against the architect's supplied source text —
it does not live in the repo — so what I verified is the next best thing, and it is tight:

* **v1.4 (`7d4757e`) makes exactly the three edits its message claims and no others**: the
  header `1.3 -> 1.4`; §8's F1 and F2 rows; §10's new v1.4 log row. The whole-file diff is those
  three hunks. §3.4 is untouched — confirmed by `git diff c941c64..HEAD -- CONTEXT.md`, which
  shows no hunk anywhere in §3.4.
* **v1.3 (`c941c64`)'s diff matches its own §10 log row item for item**: §3.2 tie rule rewritten;
  §3.3 window/tpr-tie/rounding/N; §3.4 ==POC wait rule; §3.5 risk ₹1,000 + Q40-d; new §4.6; §8's
  F5 row; §9 registry rebuilt; §10 log. Nothing outside those places moved.
* Header now reads **v1.4** and **§8's F1 row reads POC 2032** — the two things the card asked
  me to confirm. Both present.

*If the architect wants the byte-diff, the operator can paste the two supplied texts and I will
run it; the structural audit above is what is possible from inside the repo.*

### 2b. The seven ROUND-3 FINAL RECEIPTS

All seven present under one heading, each in the same shape (trader's words → what it resolves →
what was executed), and each **faithful to what actually happened**:

| Receipt | Resolves | Executed — verified |
|---|---|---|
| R3F-a | chunk-4 gate | STATUS.md line updated; `docs/gate_chunk4_bias_evidence.md` **unchanged** in the span |
| R3F-b | OPEN-4 (Q38/Q39) | the tie predicate rewrite + 3 F5 sub-fixtures — audited in 2c/2d |
| R3F-c | OPEN-6 + OPEN-7 (Q40-d) | correctly recorded as *nothing to execute in chunk 7* |
| R3F-d | Q-9 + OPEN-3 (Q41-A) | `STATE_SIDE_UNSET` built; the card's no-trade fixture inverted, with the ruling quoted in the docstring |
| R3F-e | Q-8 (Q42) | no `poc.py` change (the interim WAS the spec); the reference/window pin added instead |
| R3F-f | Q-13 | closes REVIEW_6's finding Q2b ("no architect ruling on Q-13 exists"); the row-count table matches REVIEW_6's own reproduction |
| R3F-g | chunk-6 gate | STATUS.md line updated; `docs/gate_chunk6_poc_evidence.md` **unchanged** in the span |

Q-8, Q-9, Q-13 and Q-14 are relabelled RESOLVED at their own headings; I diffed the span and
**no ruling text inside any of those items was altered** — status lines only, exactly as claimed.
Both gate closures carry their evidence path in STATUS.md and both are inside the plan.md §2
deadline (before the chunk-9 run, which has not started).

### 2c. The OPEN-4 tie-rule change and F5's three sub-fixtures

The predicate now reads `C.close >= bodyMin -> BULLISH; else BEARISH` and **nothing in
`_rule_3_tie` reads `minute.open` or `minute.close`** — I confirmed this by my own AST walk over
the function (attributes read off `minute`: exactly `{high, low}`). The unconditional `else` is
correct and not a shortcut: once `C.close < bodyMin`, `C.close <= bodyMax` is a tautology because
`bodyMin <= bodyMax` always — so writing the second condition out would be a genuinely dead
third branch, and CONTEXT §3.2 states the same reachability itself.

The three F5 sub-fixtures are as CONTEXT v1.3 §8 names them, and their digests are correct:

| file | decisive minute | sha256 (recomputed by me) | matches the pin |
|---|---|---|---|
| `SYNTH_2099-01-06` RED | 2018 -> 2005 | `d234acb1…78ccc9` | yes — **byte-unchanged** from before the span |
| `SYNTH_2099-01-07` GREEN | 2005 -> 2018 | `3eaa8727…b4e849` | yes (ADDED) |
| `SYNTH_2099-01-08` DOJI | 2010 -> 2010 | `f08da715…3203a1` | yes (ADDED) |

All three carry the same decisive high (2055) and low (1995), so the engine returns a
**byte-identical result object** across them — asserted, and it is the strongest available form
of "colour is irrelevant". PROVENANCE.md carries a full entry naming the architect-signed §8
change that licenses the two additions (CLAUDE.md rule 3 satisfied).

### 2d. The three retired colour tests and the two re-pinned probes — judged

**Not weakening. Ruling-driven, and net strictly stronger.** Five test functions disappear in the
span; here is each one and what replaced it:

| retired | why it is gone | what covers the ground now |
|---|---|---|
| `test_f5_rule_3_tie_red_is_bullish` | superseded, same answer | the parametrized 3-colour F5 test — a superset |
| `test_rule_3_tie_green_is_bearish_open4_mirror` | **the rule it asserted no longer exists** (trader overturned the green mirror) | the GREEN sub-fixture, now expecting BULLISH |
| `test_rule_3_tie_doji_carries_and_is_open4` | **same** (doji-carry overturned) | the DOJI sub-fixture, now expecting BULLISH |
| `test_r3_tie_red_close_exactly_on_body_min_is_bullish` | renamed only | `test_r3_tie_close_exactly_on_body_min_is_bullish_red_minute` — **identical candles, identical expected bias**, only the rule tag moved |
| `test_r3_tie_green_close_exactly_on_body_max_is_bearish` | expected bias flips BEARISH -> BULLISH | `..._is_bullish_even_on_a_green_minute` — **same boundary-equal close (== bodyMax)**, new answer under the new rule |

Neither re-pin is loosened: both still assert a boundary-equal close with a same-minute double
break, which is exactly what M15/M16 mutate. And three NEW pins arrived that did not exist
before: the identical-result-object test, the AST probe on the tie branch, and a direct call into
the unreachable bearish branch. **The docstrings are honest about all of this** — the second
probe's docstring states the flip and names the ruling; the file carries a `CONTRACT MOVED BY
ARCHITECT RULING` block. Judgment: **correct discipline, approved.**

### 2e. Tie-predicate mutation test

The architect's note is right that `close 2009` is not reachable — an outside bar closing below
`bodyMin` is taken by **Rule 1 (bearish)** before Rule 3 is consulted. I constructed the
reachable cases instead:

| mutant | what it does | result |
|---|---|---|
| M44 | `C.close >= bmin` -> `>` (the **close == bodyMin boundary**, M15) | **CAUGHT** — `test_r3_tie_close_exactly_on_body_min_is_bullish_red_minute` |
| M45 | **bullish precedence flipped**: `>= bmin` replaced by a `> bmax` test | **CAUGHT** — all three F5 sub-fixtures |
| M46 | the tie **reads the minute's colour again** (`and minute.close < minute.open`) | **CAUGHT** — the GREEN/DOJI sub-fixtures and the AST probe |

And the unreachability itself is pinned two ways: the direct call returns BEARISH as the spec
writes it, and the same pair routed through `evaluate_pair` lands on `RULE_1`. I re-verified the
routing claim exhaustively over a 63-pair grid — **zero pairs reach the tie's bearish branch.**

---

## 3. State-machine mutation matrix (the core duty)

Harness: mutate the shipped source in place, run the targeted suite, restore from an in-memory
snapshot in a `finally`. **52 mutants.**

### Caught by the build's own suite — 41

| # | Mutation | Spec sentence it breaks |
|---|---|---|
| M01 | reference == POC no longer yields side-unset | §3.4-1 ==POC |
| M02 / M03 | long / **short** reference side flipped | §3.4-1 + the mirror paragraph |
| M04 | `close > POC` -> `>=` (**== POC triggers**) | §3.4-2 R2-Q34c |
| M05 | `close < POC` -> `<=` (**== POC arms**) | §3.4-1 "== POC does not arm" |
| M06 | WAIT state never evaluated | §3.4-1 |
| M07 | **a close ON the POC arms a waiting day** | §3.4-1 strictness |
| M08 | **a close ON the POC triggers while ARMED** | §3.4-2 |
| M09 | trigger side flipped while ARMED | §3.4-2 |
| M10 | a close ON the POC counts as the first DISTINCT close | §3.4-1 Q41 |
| **M11** | **the Q41-A mutant: the first distinct close ABOVE *enters* directly** | §3.4-1 "it is never itself the entry" — **CAUGHT** |
| M12 | **long gap predicate `>` -> `>=` (low == POC -> gap branch)** | §3.4-3 / the Q-15-taught boundary — **the F1 golden screams**, exactly as the card predicted |
| M14 / M15 | long / short gap branch never fires | §3.4-3 + mirror |
| M16 / M17 | normal long stop from the open not the low / short from the open not the high | R1-Q15 / R1-Q2 |
| M18 / M19 | gap "previous candle" includes the entry candle / takes the first earlier one | §3.4-3 |
| M20 | target multiple 3 -> 2 | §3.4-4 |
| M21 | **E7 broken — the entry candle can trigger its own stop** | §7-E7 |
| M22 | **a both-touched candle pays the TARGET** | §3.4-5 R1-Q20 |
| M25 / M26 | the 15:15 candle may open a trade / the 15:00 candle may not | R2-Q30 — **the boundary both ways** |
| M27 / M28 | the reference candle becomes eligible / the 11:30 candle is skipped | §3.4-2 |
| M29 | the 15:30 candle may exit | R1-Q18 |
| M30 | reference bar drifts off the profile window | §3.4-1 + §3.3 (B154's pin) |
| M31 / M32 / M33 / M34 | **E10 fallback order** — first-not-last minute / exclusive cutoff / cutoff slides to 11:15 / fallback beats a present candle | §7-E10, all four |
| M35 | **an unsizable cross no longer consumes the day** | §3.4-2 "even if the trade is unsizable" |
| M36 | a no-cross day recorded as consumed | §3.4-2 |
| M37 | **the walk does not stop at the first cross (re-entry)** | R1-Q16 |
| M39 / M40 | duplicate / off-grid stamps accepted | §4.5 gate 2, §7-E12 |
| M41 | a no-oracle day counted under gate 1 instead of gate 1P | §4.6 / the Q-14 ruling |
| M43 | a demerger-suppressed day is evaluated anyway | §3.2 |
| M44 / M45 / M46 | the three tie mutants | §3.2 v1.3 — see §2e |

### Survived the build's suite — 6, of which 4 are real gaps (now closed) and 2 are equivalent

| # | Mutation | Verdict |
|---|---|---|
| **M13** | **short gap predicate `<` -> `<=`** (high == POC -> gap branch) | **REAL GAP → finding Q1.** Now CAUGHT by `test_a_short_entry_candle_whose_high_touches_the_poc_is_NOT_a_gap` |
| **M23** | **stop touch `<=` -> `<`** (a candle that exactly touches the stop rides on) | **REAL GAP → finding Q2.** Now CAUGHT |
| **M24** | **target touch `>=` -> `>`** | **REAL GAP → finding Q2.** Now CAUGHT |
| **M42** | **`gate1p.passed` dropped from `DayGates.usable`** | **REAL GAP → finding C2.** Now CAUGHT |
| M38 | the dedicated float-POC guard deleted | **EQUIVALENT, proved.** The type guard below it still refuses a float, with a message that even satisfies the existing test's `match="Fraction"`. Verified for `2030.0`, `2030.5`, `nan`, and `Decimal` |
| M47 | Rule-3 outside-bar predicate `>`/`<` -> `>=`/`<=` | **EQUIVALENT, proved.** Swept a 63-pair grid: 17 pairs the mutant would newly route to Rule 3, and the shipped engine already decides **all 17** earlier — 6 by Rule 1, 6 by Rule 2, 5 by inside-bar carry. Rule 3 is unreachable for every one. (Chunk-4 code, untouched by chunk 7.) |

### Added in the second pass, after the probes — 5 more, all caught

M23b / M24b (the **short** mirrors of the two touch operators), M48 (gap stop restricted to the
immediately-preceding grid stamp — kills the reading B160 rejects), plus M13/M23/M24/M42 re-run.

**Matrix result: 52 mutants — 50 CAUGHT, 2 EQUIVALENT (proved, not assumed), 0 surviving.**

---

## 4. F1–F4 and every short mirror, recomputed by hand

I wrote CONTEXT §3.4 out again from the spec text — reference, states, trigger, gap predicate,
stop, `3x` target, E7 monitoring, SL-wins — **importing nothing from `src/acumen`**, and ran the
fixtures' candles through it. All seven match the shipped engine *and* CONTEXT §8's stated
numbers:

| case | entry | stop | target | risk | gap | exit | vs CONTEXT §8 |
|---|---|---|---|---|---|---|---|
| **F1 GOLDEN, POC 2032** | 2037 | **2032** | **2052** | **5** | False | target @12:00 | **exact** — §8 F1's four numbers |
| F1 measurement, POC 2030 | 2037 | 2025 | 2073 | **12** | True | square-off | gap branch, not a §8 claim |
| **F2 GOLDEN, POC 2032** | 2037 | **2032** | **2052** | **5** | False | target @12:30 | **exact**, after WAIT-BELOW -> arm 2027 -> re-cross |
| F2 measurement, POC 2030 | 2037 | 2027 | 2067 | **10** | True | square-off | gap branch |
| **F3 bearish, POC 1985** | **1980** | **1988** | **1956** | **8** | False | target @12:00 | **exact — SL is the candle HIGH, TP 1956 not 2004** |
| **F4 gap, POC 2030** | **2042** | **2028** | **2084** | 14 | **True** | target @12:15 | **exact** — prior close 2028, low 2034 |
| F4 SHORT mirror, POC 1985 | 1973 | 1987 | 1931 | 14 | True | target @12:15 | hand-computed mirror, exact |

**F1's golden turns on the boundary the ruling teaches**: the entry candle's low is 2032 and the
POC is 2032, so `low > POC` is **FALSE** — the NORMAL branch, stop = low = 2032, risk 5. Mutant
M12 (`>` -> `>=`) breaks precisely this and is caught.

**The Q-15 proof is asserted, not asserted-about.** Both measurement tests carry
`stop_source == STOP_FROM_PREVIOUS_CLOSE`, `stop_paise <= R(2030)` and **`risk_paise >= R(7)`**.
My independent run confirms the numbers those properties bound: F1 risk **12**, F2 risk **10**,
both stops (2025, 2027) at or below the POC. So on these candles the gap branch cannot produce
§8's risk of 5 — which is exactly why the fixture's POC had to be the thing that moved. The
architect's directed check on this point is satisfied.

I also verified the arithmetic behind it holds generally: over a deterministic grid of entry-candle
shapes (lows below, on and above the POC), `entry > stop` and `risk >= 1` on every day whose
reference candle exists — and over 146 real entered days, **zero unsizable crosses**.

---

## 5. The HDFCBANK 2026-06-10 walk, verified independently

Recomputed from the parquet stores with my own §3.2 / §4.5+§4.6 / §3.3 / §3.4 arithmetic —
no `acumen` import anywhere in the check.

**Bias.** Pair = (2026-06-08, 2026-06-09), both previous trading days. P: O 738.00 H 741.50
L 734.50 C 738.65 -> bodyMin **738.00**, bodyMax **738.65**. C: O 739.45 H 743.95 L 732.30
C 738.35. Inside-bar false; Rule 1 declines (738.35 sits inside the body); Rule 2 declines on
both sides; **Rule 3 fires** — `C.high 743.95 > P.high 741.50` **and** `C.low 732.30 < P.low
734.50`. The 1-minute scan over C's 375 minutes:

* first minute whose **high > 741.50**: **09:15, high 741.90** ✔ (the architect's number, exact)
* first minute whose **low < 734.50**: 11:21, low 734.00

**P.high broke first**, and `C.close 738.35 >= bodyMin 738.00` -> **BULLISH**. A real Rule-3
outside-bar day, decided on real 1-minute data.

**Gates.** 375 stored minutes. Fold `[736.40, 755.95]` vs raw bhavcopy `[736.40, 755.95]`.
Gate 1: volume gap **1.8839%**, inside `[-0.1%, +5.0%]` — PASS. Gate 2: 0 duplicates, 0
impossible/negative OHLC — PASS. Gate 1P: excess **0 paise** on both sides against tolerances of
75.60 / 73.64 paise — PASS. All three, as §4.6 requires.

**POC.** Window 09:15–11:14 = **120 of 120** bars. Tick **5 paise** (from the instrument master,
not assumed — `tick_size` field `5.000000`). top **745.50**, bottom **736.40** -> totalTicks
**182**. tpr candidates 7 and 8 give realized row counts 26 and 23; |26−24| = 2 vs |23−24| = 1,
so **tpr = 8**, 23 rows — decided on closeness, no tie involved. Prorata spread conserves volume
**exactly** (15,220,350 == 15,220,350, rational arithmetic, not a tolerance). Busiest row
`[739.60, 740.00)` with 2,441,686.84 — sole winner, no tie — midpoint **POC = 739.80** ✔.

**Signal.** Reference = the 11:00–11:15 close **738.20** < POC 739.80 -> **ARMED** ✔. The candle
closing **11:30** closes **740.95**, strictly above -> **TRIGGER**, entry 740.95 ✔. Its low is
**738.10**, which is **below** the POC — so `low > POC` is FALSE and this is **NOT a gap** ✔ ->
SL = the entry candle's low **738.10** ✔. Risk 2.85 -> **TP = 740.95 + 3 × 2.85 = 749.50** ✔.
Exit: the candle closing **13:15** has high **755.95 >= 749.50** -> **TARGET** ✔.

**Every number in the architect's directed check reproduces exactly.**

---

## 6. The 290-day sweep, re-run

Re-ran read-only and offline over TCS, RELIANCE, HDFCBANK, ICICIBANK, BHARTIARTL,
2026-05-01..2026-07-24:

```
stock-days walked : 290      exceptions : 0
entered                                 146
no-trade-armed-but-no-qualifying-close    88
no-trade-never-armed                      56
side-never-set 0 · unsizable 0 · gate refusals 0     partition sums to 290 ✔
long 61 / short 85 · gap entries 0
exits: stop-loss-hit 86 · square-off 36 · target-hit 24
```

**The 146/88/56 partition reproduces exactly, with zero exceptions.** I then checked invariants
on all 146 entered days independently of the engine's own claims: `risk > 0`; `target = entry ±
3 × risk`; `|entry − stop| == risk`; a long entry strictly above the POC and a short strictly
below; a non-gap stop never on the wrong side of the POC. **Zero violations.**

**Two additional spot-walks, end to end, with my own arithmetic** (both reproduce the shipped
engine exactly, incl. tick, totalTicks, tpr, row count, exact volume conservation and POC):

* **ICICIBANK 2026-05-21** — bearish (Rule 1). tick 10, totalTicks 82, tpr 4, 23 rows, POC
  **1245.70**. Reference 1242.60 **below** the POC on a bearish day -> **WAIT-ABOVE**, arms
  later, triggers on the candle closing **12:00** at **1245.30**; high not below the POC -> normal
  stop **1248.30**, risk 3.00, **TP 1236.30**; **target hit** on the candle closing 13:00.
* **RELIANCE 2026-05-05** — bullish (Rule 1). tick 10, totalTicks 224, tpr 9, 25 rows, POC
  **1465.85**. Reference 1452.90 -> ARMED; triggers on the candle closing **13:15** at
  **1466.40**; stop = its low **1464.20**, risk 2.20, **TP 1473.00**; **stopped out** on the next
  candle.

**The empty-factor-table disclosure — verified, and it is stronger than the build claimed.**
The build justified it by price-move measurement. I checked the CA cache itself. There ARE five
corporate-action rows for these five symbols with ex-dates inside the window — all **ordinary
dividends**:

| symbol | ex-date | dividend | vs cum close | vs the most adverse 2026 close | §4.2 verdict |
|---|---|---|---|---|---|
| TCS | 25-May-2026 | ₹31 | 1.34% | 1.38% | ordinary, k=1 |
| RELIANCE | 05-Jun-2026 | ₹6 | 0.46% | 0.46% | ordinary, k=1 |
| HDFCBANK | 19-Jun-2026 | ₹13 | 1.63% | **1.78%** | ordinary, k=1 |
| TCS | 15-Jul-2026 | ₹12 | 0.55% | 0.61% | ordinary, k=1 |
| BHARTIARTL | 24-Jul-2026 | ₹24 | 1.24% | 1.37% | ordinary, k=1 |

Every one is under §4.2's 2% special-dividend threshold even against the most adverse 2026 close
as a pre-announcement proxy (worst case 1.78%), so **k = 1 for all five and the empty factor
table is exactly correct for this window** — not merely harmless. No split, bonus, rights or
demerger appears for any of the five symbols in 2026. **Chunk 9's duty to wire the real table is
recorded** in the build's PROGRESS `state-for-next-session`, item (4), in those words.

**Look-ahead, checked on the real data** (not in the card, but §16 of the quant checklist and the
chunk-13 replay invariant both depend on it): for each of the 146 entered days I re-evaluated the
day truncated to everything up to and including the entry candle — which is all a live screener
holds when it must fire — and compared entry, stop, target, risk, gap flag, stamp, initial state,
reference, consumption and the full transition trail. **Zero drift on all 146.** Plus 189
prefix-stability checks (the entry never changes as later candles arrive). CONTEXT §6's
"same code path, no backtest/live drift" holds behaviourally, not just structurally.

---

## 7. Purity

My own AST walk over `signals.py`, with a broader ban list than the build's:

* **imports**: `__future__`, `dataclasses`, `datetime`, `fractions`, `typing`, `.bias`,
  `.calendar` — nothing else. No `os`, `io`, `pathlib`, `requests`, `urllib`, `socket`, `json`,
  `csv`, `pandas`, `pyarrow`, `time`, `random`, `subprocess`, `logging`, and **no store module**.
* **calls**: no `open`, `now`, `today`, `utcnow`, `fromtimestamp`, `perf_counter`, `read_text`,
  `write_text`, `exec`, `eval`, `float()`, `round()`. The only hit my over-broad ban list flagged
  was `time` — all seven sites are `datetime.time()` accessors formatting a stamp into a detail
  string, not clock reads. Verified by inspection at each line.
* **no float literal** anywhere, and **zero true-division operators** — so no float can be
  produced even accidentally.

**Fraction POC end to end.** A half-paise POC (`Fraction(406101, 2)` = 203050.5 paise) goes in
and comes out of `SignalDay.poc_paise` as the **identical `Fraction`, denominator 2**, unrounded,
while every price on the `Entry` is an `int`. The orchestration passes `profile.poc_paise`
straight through — no rounding at the module boundary.

**Float refusal.** `2030.0`, `2030.5` and `nan` are all refused with `SignalError`; `Decimal` too.
(See finding C5 on how the refusal is implemented.)

**The B154 grid pin.** `signals.REFERENCE_BAR == poc.SPEC_WINDOW_CANDLES ==
poc.SPEC_WINDOW.candles == 8`, and `reference_cutoff_stamp() == SPEC_WINDOW.last_time == 11:14`,
with `bar_close_stamp(REFERENCE_BAR) == 11:15`. The §3.4 reference candle **is** the last candle
of the §3.3 profile window, structurally. Mutant M30 confirms the pin bites.

---

## 8. Findings

### Quant reviewer

**Q1 — MEDIUM — the SHORT mirror of the gap boundary was pinned by nothing.** *(CLOSED by this
review's kept test.)*
CONTEXT §3.4's mirror paragraph says "Gap entry = entry candle's **high < POC** (never traded
at/above it)" — strictly below. Mutating that `<` to `<=` **survived the entire 1390-test suite**.
The long side of this same boundary is pinned twice over (it is what CONTEXT v1.4 §8 says F1/F2
now teach); the short side had nothing. It moves money: on a bearish day whose entry candle's
high sits exactly on the POC, the mutant swaps the stop from the entry candle's high to the
previous candle's close — in my probe's numbers, stop 1985 -> 1990, risk 7 -> 12, target 1957 ->
1942, and at ₹1,000 fixed risk that is **142 shares vs 83**.
**Closed** by `test_a_short_entry_candle_whose_high_touches_the_poc_is_NOT_a_gap`
(`tests/test_review7_probes.py`), verified to fail on the mutant and pass on HEAD.

**Q2 — MEDIUM — all four exit-touch operators were unpinned at the exact level.** *(CLOSED.)*
CONTEXT §3.4-5 is inclusive on both: "candle low **<=** SL -> exit at SL. Candle high **>=** TP ->
exit at TP." No test in the build put a low exactly on the stop or a high exactly on the target,
so `<=` -> `<` and `>=` -> `>` both survived — on the long side and, by the same omission, on the
short. A candle that exactly touches the stop would ride on instead of paying ₹1,000, and the
trade would then resolve at whatever the rest of the day gave; on exact-touch target candles the
error runs the other way. Exact touches are not exotic on a 5-paise tick grid.
**Closed** by three probes covering long stop, long target, and both short mirrors.

**Q3 — LOW — the gap branch and the unsizable branch are exercised only by fixtures.**
The 290 real stock-days produced **zero gap entries and zero unsizable crosses**. That is not a
defect — it is the honest rarity of the shape — but it means the branch the Q-15 ruling turns on
has no real-data witness in this repo. Recorded for chunk 12: the validation pack should
deliberately sample a real gap-entry day if one exists in the full history, so the trader sees
the rule he gave in R2-Q33 applied to his own chart at least once.

**Q4 — INFO — the empty factor table is correct here, and now proved so.** The build justified it
by price-move measurement (an indirect argument). I verified it against the CA cache directly:
five ordinary dividends, all under §4.2's 2% threshold, k = 1 for every one. The conclusion holds
and the chunk-9 duty is recorded. No action.

**Q5 — INFO — arming and side-setting are capped at the 15:00-closing candle.** CONTEXT §3.4-1
caps only the *trigger* at 15:00; the engine also stops evaluating arming/side-setting there. I
checked: since no candle after 15:00 may trigger, a day that armed at 15:15 could never enter, so
the behaviour is **equivalent**, not a deviation. Noted so a future reader does not re-derive it.

### Code reviewer

**C1 — LOW — the prep commit is missing its `(unreviewed)` suffix.** `75e3f98`
("chunk7-prep: Round-3 receipts; gates closed; tie rule per Q38/Q39") changed **shipping engine
code** — `src/acumen/bias.py` and `src/acumen/bias_engine.py` — so under CLAUDE.md's git rules
("Build commits end `(unreviewed)`") it should have carried the suffix. The other two build
commits do; the spec commit correctly does not. History-only, non-blocking, not fixable without a
rewrite this review will not perform.

**C2 — LOW — `DayGates.usable` is unconsumed and was untested on the gate-1P-only path.**
*(CLOSED.)* `usable` is the property that states CONTEXT §4.6's "all three required", but the
pipeline routes on `refusal`, and the suite asserted `usable` only on a clean day and on a gate-1
failure — so **deleting `gate1p.passed` from the conjunction survived the whole suite**. The
pipeline's behaviour was never wrong (`refusal` handles gate 1P correctly, and M41/M43 are
caught), but the property that documents the ruling could silently stop meaning it.
**Closed** by `test_a_day_that_fails_only_gate_1p_is_not_usable`.

**C3 — INFO — chunk 7 committed no evidence artifact.** The 290-day sweep and the HDFCBANK walk
exist only as prose in PROGRESS.md/STATUS.md; every prior chunk making real-data claims shipped a
`docs/gate_*.md` or a report file a later session could re-read. I re-derived all of it
independently and **every number holds**, so nothing is wrong — but a chunk-9 or chunk-12 session
that wants to check the claim has to redo this work from scratch. Worth a committed evidence file
next time real-data claims are made outside a gate pack.

**C4 — INFO — two commit bodies name "Claude Code".** `0209f17` ("STATUS.md + PROGRESS.md per
CLAUDE.md") and `7d4757e` ("no Claude Code session may edit it (CLAUDE.md read-order rule 1)").
Neither is an authorship credit, both are citations of the repo's own constitution, and the author
is the human operator throughout — no `Co-Authored-By`, no "Generated with". But CLAUDE.md's rule
reads "no AI attribution anywhere … nothing", so I flag it for the architect's own reading rather
than decide it. **Not a FAIL trigger.**

**C5 — INFO — the dedicated float-POC guard is redundant.** `_require_exact_poc` raises on
`isinstance(poc_paise, float)` and then again on "not `int` or `Fraction`". Deleting the first
leaves behaviour identical — a float still raises `SignalError`, with a message that even
satisfies the existing test's `match="Fraction"`. That is why mutant M38 could not be killed and
is classified equivalent. The guard has real documentary value (its message is the one that
explains *why*), so this is a note, not a request: the refusal itself is genuine and I verified it
against `2030.0`, `2030.5`, `nan` and `Decimal`.

**C6 — INFO — B166's departure from Q-15's own closing sentence is properly disclosed.** Q-15 said
"if (a), the first pair is deleted"; the fix session kept the POC-2030 pair, relabelled as a
MEASUREMENT. That departure is named explicitly in QUESTIONS.md's execution record **and** in the
PROGRESS decision. Judgment: **approved** — the pair is no longer a golden, claims nothing about
CONTEXT §8, and is the only coverage of the gap branch besides F4.

---

## 9. Class-B decisions — judged

| # | Decision | Judgment |
|---|---|---|
| **B154** | every session time derived from a bar ORDINAL, never a clock literal | **APPROVE.** Verified: `REFERENCE_BAR == poc.SPEC_WINDOW_CANDLES == 8`, cutoff `11:14 == SPEC_WINDOW.last_time`. Mutant M30 caught. The §3.4-reference-is-the-§3.3-window's-last-candle fact is now structural, not coincidental |
| **B155** | full `transitions` trail, including candles that change nothing | **APPROVE.** Chunk 12's replay pack needs *why a day did nothing*; M06/M11/M27 are all caught through it |
| **B156** | three-way `poc_side` (above/below/**at**) rather than two-way comparisons | **APPROVE.** §3.4 treats "exactly on the POC" as its own case in three separate sentences; M04/M05/M07/M08/M10 are exactly the mutants a two-way predicate would ship, and all five are caught |
| **B157** | `risk <= 0` (not only `entry == SL`) refused, day CONSUMED, logged | **APPROVE.** The reachability claim checks out: with the reference candle present the stop is bounded by the POC and the entry strictly beyond it, so `risk >= 1` always — my own 290-day sweep found **0 unsizable**. Negative risk is reachable only on the E10-fallback gap shape, which the fixture exercises. Refusing rather than sizing a negative divisor is the only non-strategy-inventing choice |
| **B158** | a gap entry with no preceding candle records "consumed, no trade" instead of raising | **APPROVE.** Unreachable on a whole day but not decided silently, and a pure function chunk 9 runs over ~400k days should not raise on a shape nobody has proved impossible |
| **B159** | the square-off is a MARKER naming a candle, not a price | **APPROVE.** That is the card's own chunk-7/chunk-8 split. The "nothing traded after the entry" case marks the entry candle, whose close IS the day's last traded 15-minute price — inventing any other number would be pricing |
| **B160** | the gap stop's "previous candle" is the last that actually TRADED, not the previous grid stamp | **APPROVE.** §3.4-3's own words are "the last traded price before the jump", and the completeness ruling makes an absent stamp a tradeless quarter-hour. The build pinned this only inside an unsizable fixture; **this review adds a direct probe**, and mutant M48 confirms it kills the grid-stamp-only reading |
| **B161** | `open4` -> `tie_case`; three colour tags -> one `RULE_3_TIE` | **APPROVE.** OPEN-4 is RESOLVED, so a field named after an open question would be stale; the day is still the rare hand-checkable one plan.md's chunk-12 card wants listed, and the docstring says exactly that |
| **B162** | exactly ONE refusal reason per day, in a fixed order; a no-oracle day counted under gate 1P, never gate 1 | **APPROVE.** This is the Q-14 ruling's own wording ("gate 1 did not fail, it could not run"), and it is what makes chunk 9's counts partition rather than double-count. M41 caught; the eight reason strings are distinct and pinned |
| **B163** | a float POC refused at the door of `evaluate_day` | **APPROVE** in intent and effect — see finding **C5** on the redundancy. The refusal is real and verified |
| **B164** | F1/F2 built BOTH ways rather than picking a reading while Q-15 was open | **APPROVE, and vindicated.** The ruling landed and **nothing had to be re-measured** — every expected value in both pairs is still the build session's own hand-computed number. This is the right posture for a class-A hole |
| **B165** | `signals.py` imports `BULLISH`/`BEARISH` from `bias.py` rather than re-declaring them | **APPROVE.** Both modules are pure so the import costs nothing, and a re-declared string is a future divergence between two engines that must agree |
| **B166** | the POC-2030 pair KEPT and relabelled a MEASUREMENT, not deleted | **APPROVE** — see finding C6. The departure from Q-15's closing sentence is disclosed in two places |
| **B167** | the measurement pair asserts `stop_source`, `stop <= POC`, `risk >= 7` | **APPROVE, and this is the best change in the fix commit.** The arithmetic Q-15 rests on stops being prose in a docstring and becomes an executable assertion. Independently confirmed: F1 risk 12, F2 risk 10, both stops at or below 2030 |
| **B168** | the goldens renamed, assertions untouched | **APPROVE, and verified mechanically.** `git diff 6ded67a..0209f17 -- tests/test_signals.py` removes **zero** assertions and adds exactly three — all three on the measurement pair (B167's properties). No golden assertion moved |

---

## 10. Standard sweep

| Item | Result |
|---|---|
| **Full suite from clean** | **1396 passed / 0 failed** (`__pycache__` + `.pytest_cache` deleted first) = the build's 1390 + this review's 6 probes. No skip, no xfail |
| **Fixtures frozen** | `git diff c941c64..HEAD -- tests/fixtures poc` = **two ADDED CSVs + a PROVENANCE section, 22 insertions, 0 deletions.** No existing fixture byte changed |
| **Fixture digests** | Recomputed all three F5 minute files: the two new ones match their pins in `test_fixture_integrity.py` exactly; the RED file's digest is **unchanged** from before the span |
| **F9 byte-identical** | No F9 file appears in the span's diff at all; both F9 tests green. (The build's own note is right that no real F9 day is a tie day — which is why the tie needs a synthetic fixture) |
| **No test weakened** | 5 test functions removed, 75 added. All five removals audited in §2d: two renames, three whose *rule* was overturned by the trader. No assert loosened, no `approx` introduced, no skip/xfail added |
| **Commit hygiene** | 4 commits, each a logical unit with a what+why body and correct `chunk7`/`spec` prefix. **One LOW: `75e3f98` lacks `(unreviewed)` despite changing engine code — finding C1** |
| **AI attribution** | No `Co-Authored-By`, no "Generated with"; author is the operator on all four commits. Two bodies cite "Claude Code" while quoting CLAUDE.md's own rules — **finding C4**, INFO |
| **Secrets** | Nothing matching credential patterns in the span's diff. `.env` is untracked and gitignored; no `.env` value appears in any test output, PROGRESS entry or log line |
| **PROGRESS/STATUS** | Both chunk-7 entries follow the plan.md §6 template with every field, including honest `state-for-next-session`. STATUS.md's chunk-7 line records `built` + the Q-15 execution + "QC REVIEW OWED" |
| **Pushed-SHA chain** | `HEAD == origin/main == 0209f17` at review start; working tree clean apart from this review's new probe file. Tags `chunk0-pass`..`chunk6-pass` present; no `chunk7-pass` yet (correct) |
| **Card's "Done when"** | F1–F4 at signal level ✔; close==POC while ARMED ✔; cross during WAIT-BELOW ✔; gap day ✔; no-cross day ✔. The card's "OPEN-3 day (logged, no trade)" fixture is built **INVERTED** because Q41-A superseded the interim — the docstring quotes the receipt and names the card text it supersedes, the same discipline B121 used in chunk 6. **Correct; approved** |

*Housekeeping note, disclosed for completeness:* the mutation harness rewrote three engine files
with CRLF endings while restoring them. I detected it via `git status`, restored with
`git checkout`, and verified all three are now **byte-identical to their committed blobs**
(sha256 compared against `git show HEAD:<path>`). No content ever differed.

---

## 11. Tests this review adds and keeps

`tests/test_review7_probes.py` — 6 tests, all green on HEAD, each verified to FAIL on the mutant
that motivated it:

1. `test_a_short_entry_candle_whose_high_touches_the_poc_is_NOT_a_gap` — kills M13 (finding Q1)
2. `test_a_candle_whose_low_exactly_equals_the_stop_exits_at_the_stop` — kills M23 (Q2)
3. `test_a_candle_whose_high_exactly_equals_the_target_exits_at_the_target` — kills M24 (Q2)
4. `test_the_short_mirror_an_exact_touch_of_the_stop_and_of_the_target` — kills M23b/M24b (Q2)
5. `test_the_gap_stop_skips_a_tradeless_quarter_hour_to_the_last_traded_close` — kills M48, pins B160
6. `test_a_day_that_fails_only_gate_1p_is_not_usable` — kills M42 (finding C2)

Every expected value is hand-computed in the docstring from CONTEXT §3.4, so each is checkable
without running it.

---

## VERDICT: **PASS**

No CONTEXT.md deviation. No look-ahead. No weakened test. The two MEDIUM findings were coverage
gaps in boundary operators, not wrong behaviour — the shipped engine is correct on both; nothing
pinned it, and now something does. I would stake the trader's account on this chunk.

Chunk 8 (the simulator) is unblocked. It consumes `SignalDay.entry` (entry/stop/target/risk, all
integer paise) and `SignalDay.exit_event` (kind + candle), and it must respect `consumed` on the
unsizable days.
