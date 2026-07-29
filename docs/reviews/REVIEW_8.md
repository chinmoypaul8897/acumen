# REVIEW_8 — chunk 8, the trade simulator · QC (both personas)

**Span reviewed:** `79c3c79..f079a2a` — the architect's Part A (three git/evidence rules), the
simulator build, the real-data evidence pack, and the STATUS/PROGRESS commit.
**Personas:** `personas/quant_reviewer.md` **and** `personas/code_reviewer.md`, both in full.
**Session:** fresh, offline, read-only against both parquet stores. No credentialed call, no
candle fetched, nothing written to either store.

---

## VERDICT: **PASS**

Chunk 8 converts signals into rupees and a sign error here inverts the whole backtest, so it
was reviewed on the assumption that it is wrong. It is not. Every number in the golden money
table was recomputed by an independent reimplementation of CONTEXT 3.4/3.5 written from the
spec text, importing nothing from `src/acumen`, and **all 20 cases × 10 fields agree exactly —
zero divergences**. The 146-trade evidence pack re-derives to the paisa from its own printed
rows with plain arithmetic, and the named real golden re-derives from the raw minute parquet
with my own 15-minute aggregation. A 33-mutant matrix over sizing, pricing, money, config and
the sweep leaves **0 uncaught real defects**: 28 caught, 2 proved equivalent, 3 coverage gaps
in the evidence generator that are **closed by kept probes in this commit**.

No CONTEXT deviation. No look-ahead. No test weakened, deleted or skipped. No fixture byte
changed. No secret. No AI attribution. **1552 passed / 0 failed** from a genuinely clean state.

Findings: **1 MEDIUM** (a coverage gap in the evidence generator's accumulation loop —
CLOSED), **1 LOW** (the committed pack is not byte-reproducible from its own committed
generator; no number moves), and **5 INFO**. None blocks chunk 9.

---

## 1. Part A audit — the three new CLAUDE.md rules (directed check 1)

| Claim | Verdict |
|---|---|
| `79c3c79` touches CLAUDE.md only | **TRUE** — `1 file changed, 3 insertions(+)`, and the diff is exactly three appended bullets in the git section. Nothing else in the file moved. |
| The three rules match REVIEW_7's C4 / C1 / C3 rulings | **TRUE** — bullet 1 ↔ C4 ("two commit bodies name a product"; the new rule permits citing CLAUDE.md/CONTEXT.md, forbids naming AI tools), bullet 2 ↔ C1 (`75e3f98` changed engine code without `(unreviewed)`; the new rule extends the suffix to *every* commit touching `src/` or `tests/` pre-review), bullet 3 ↔ C3 (chunk 7's real-data claims existed only as prose; the new rule requires the generating script + its output under `docs/evidence/`). The commit body cites each finding by number and the mapping is faithful. |
| `(unreviewed)` suffix on both code commits | **TRUE** — `72b1e2a` (config.yaml, config.py, simulate.py, test_config.py, test_simulate.py) and `b1078f3` (trade_evidence.py, test_trade_evidence.py, docs/evidence/*) both carry it. `f079a2a` touches PROGRESS.md and STATUS.md only, so under the rule as written it correctly does not. |
| No AI tool or product named in any span commit message | **TRUE** — grepped all four bodies for Claude / Anthropic / Copilot / GPT / Cursor / "Generated with" / Co-Authored-By. The only hits are the string `CLAUDE.md`, which the new rule explicitly permits. Author is the human operator on all four. |
| Evidence committed under the new rule | **TRUE** — `docs/evidence/chunk8_sweep.py` (generator) + `docs/evidence/chunk8_sweep.md` (output), both in `b1078f3`, the same commit as the claims. |

Part A is clean. The architect's text was applied verbatim and the chunk obeys all three of
its own new rules.

---

## 2. The money, recomputed by hand (directed check 2)

I reimplemented CONTEXT 3.4 (reference / arm / trigger / stop source / 3R target / exit walk)
and CONTEXT 3.5 (floor sizing, level fills, signed gross, flat cost) from the **spec text**,
in integer paise, importing nothing from `src/acumen`. Then I ran the entire golden table
through both my implementation and the build and diffed **every field**.

### 2a. The table — every qty, gross and net, with both sizing bounds

| Case | Side | Entry | Stop | Target | Risk | qty | Sizing bounds (paise) | Exit | Fill | Gross | Net |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 | long | 2037 | 2032 | 2052 | 5.00 | **200** | 100,000 ≤ 100,000 < 100,500 | target | 2052 | **+Rs 3,000.00** | **+Rs 2,900.00** |
| F2 | long | 2037 | 2032 | 2052 | 5.00 | **200** | 100,000 ≤ 100,000 < 100,500 | target | 2052 | +Rs 3,000.00 | +Rs 2,900.00 |
| F3 | **short** | 1980 | 1988 | 1956 | 8.00 | **125** | 100,000 ≤ 100,000 < 100,800 | target | 1956 | **+Rs 3,000.00** | **+Rs 2,900.00** |
| F4 gap | long | 2042 | 2028 | 2084 | 14.00 | **71** | 99,400 ≤ 100,000 < 100,800 | target | 2084 | +Rs 2,982.00 | +Rs 2,882.00 |
| F4 stop variant | long | 2042 | 2028 | 2084 | 14.00 | 71 | 99,400 ≤ 100,000 < 100,800 | stop | 2028 | **−Rs 994.00** | **−Rs 1,094.00** |
| F4 **short** target | short | 1973 | 1987 | 1931 | 14.00 | 71 | 99,400 ≤ 100,000 < 100,800 | target | 1931 | **+Rs 2,982.00** | +Rs 2,882.00 |
| F4 **short** stop | short | 1973 | 1987 | 1931 | 14.00 | 71 | 99,400 ≤ 100,000 < 100,800 | stop | 1987 | **−Rs 994.00** | −Rs 1,094.00 |
| square-off LONG | long | 2035 | 2029 | 2053 | 6.00 | **166** | 99,600 ≤ 100,000 < 100,200 | square-off | 2044 | +Rs 1,494.00 | +Rs 1,394.00 |
| square-off SHORT | short | 1965 | 1971 | 1947 | 6.00 | 166 | 99,600 ≤ 100,000 < 100,200 | square-off | 1956 | **+Rs 1,494.00** | +Rs 1,394.00 |
| square-off at entry candle (B159) | long | 2035 | 2029 | 2053 | 6.00 | 166 | 99,600 ≤ 100,000 < 100,200 | square-off | 2035 | Rs 0.00 | **−Rs 100.00** |
| qty-zero LONG (DIXON shape) | long | 14250 | 12950 | 18150 | 1300.00 | **0** | 0 ≤ 100,000 < 130,000 | (marked, unpriced) | **none** | Rs 0.00 | Rs 0.00 |
| qty-zero SHORT | short | 13750 | 15050 | 9850 | 1300.00 | **0** | 0 ≤ 100,000 < 130,000 | (marked, unpriced) | **none** | Rs 0.00 | Rs 0.00 |
| exact-touch TARGET | long | 2035 | 2029 | 2053 | 6.00 | 166 | 99,600 ≤ 100,000 < 100,200 | target | 2053 | +Rs 2,988.00 | +Rs 2,888.00 |
| exact-touch STOP | long | 2035 | 2029 | 2053 | 6.00 | 166 | 99,600 ≤ 100,000 < 100,200 | stop | 2029 | −Rs 996.00 | −Rs 1,096.00 |
| exact-touch STOP short | short | 1965 | 1971 | 1947 | 6.00 | 166 | 99,600 ≤ 100,000 < 100,200 | stop | 1971 | −Rs 996.00 | −Rs 1,096.00 |
| exact-touch TARGET short | short | 1965 | 1971 | 1947 | 6.00 | 166 | 99,600 ≤ 100,000 < 100,200 | target | 1947 | +Rs 2,988.00 | +Rs 2,888.00 |
| both-touched LONG | long | 2035 | 2029 | 2053 | 6.00 | 166 | 99,600 ≤ 100,000 < 100,200 | **stop** | **2029** | −Rs 996.00 | −Rs 1,096.00 |
| both-touched SHORT | short | 1965 | 1971 | 1947 | 6.00 | 166 | 99,600 ≤ 100,000 < 100,200 | **stop** | **1971** | −Rs 996.00 | −Rs 1,096.00 |
| 1 share at exactly the budget | long | 2035 | 1035 | 5035 | 1000.00 | **1** | 100,000 ≤ 100,000 < 200,000 | square-off | 2035 | Rs 0.00 | −Rs 100.00 |
| TP blow-through +Rs 10 (mine) | long | 2035 | 2029 | 2053 | 6.00 | 166 | 99,600 ≤ 100,000 < 100,200 | target | **2053** | **+Rs 2,988.00** | +Rs 2,888.00 |

**Result: 20 rows × 10 fields, ZERO divergences between my reimplementation and the build.**
Both sizing bounds hold on every row: `qty × risk ≤ 100,000 < (qty + 1) × risk`, without
exception — the floor is tight everywhere and the budget is never exceeded.

### 2b. Short sign discipline — the highest-value check in this chunk

Checked on **every short branch**, not by symmetry argument but by recomputation:

* **short target gross is POSITIVE.** F3: `125 × (198,000 − 195,600) = +300,000` paise. F4
  short mirror: `71 × (197,300 − 193,100) = +298,200`. Exact-touch short target:
  `166 × 1,800 = +298,800`. A long-shaped formula returns the negation of each.
* **short stop gross is NEGATIVE.** F4 short stopped: `71 × (197,300 − 198,700) = −99,400`
  = exactly `−qty × risk`. Exact-touch short stop and both-touched short: `−99,600` each.
* **short square-off is signed by (entry − close).** `166 × (196,500 − 195,600) = +149,400`
  — a short that squared off BELOW its entry made money, and the mirror pays the identical
  rupee figure to the long (`+Rs 1,494.00` both sides), which is what "mirrored" means.
* The isolated sign test holds in all four quadrants: 100 shares moving Rs 10 pays a long
  `+Rs 1,000` / a short `−Rs 1,000` up, and the reverse down.
* The mutant that swaps the two branches (M03) and the mutant that prices a short target at
  `entry + 3R` (M24) are both **caught**.

### 2c. HDFCBANK 2026-06-10, from the STORE

Re-derived by reading `data/minute_store/minute/HDFCBANK/HDFCBANK_2026-06.parquet` directly
with pandas, aggregating the 375 raw minutes into 15-minute open-stamped bars myself
(CONTEXT 7-E1/E12), and doing the arithmetic by hand — nothing from `src/acumen`:

```
reference (ordinal 8, closes 11:15) close 738.20 < POC 739.80          -> ARMED
trigger  ordinal 9  (closes 11:30)  close 740.95 > POC, low 738.10     -> not a gap
entry 740.95   stop = the entry candle's low 738.10   risk 285 paise = Rs 2.85
target = 74,095 + 3 x 285 = 74,950 = Rs 749.50
exit: TARGET on ordinal 16 (the candle closing 13:15), its high 755.95
qty = floor(100,000 / 285) = 350       bounds: 99,750 <= 100,000 < 100,035
fill 749.50 (the LEVEL, not the 755.95 high)
gross = 350 x 855 = 299,250 paise = Rs 2,992.50      net = Rs 2,892.50
```

Matches the suite assertion, the committed pack's row 76, and REVIEW_7's independently
re-derived signal numbers, to the paisa. Had the fill been the candle's high it would have
paid **Rs 5,845.00** — nearly double. It does not.

---

## 3. Fill-level semantics (directed check 3)

| Probe | Result |
|---|---|
| Candle high blows **Rs 10 past** the target (high 2063 vs TP 2053) | Fill = **2053**, the level. Gross `166 × 3 × 600 = Rs 2,988.00` = exactly `qty × 3 × risk`. Paying the high would have been Rs 4,648.00 — Rs 1,660 of money the trade never made. **Kept as a probe.** |
| Candle runs **well past** the stop (short: high 1981 vs SL 1971) | Fill = **1971**, the level. Gross `−qty × risk` exactly. **Kept as a probe.** |
| Both levels touched in one candle | Pays the **STOP** on both sides (2029 long / 1971 short), flagged `both_touched_stop_wins`. R1-Q20 was applied upstream by chunk 7; chunk 8 prices it and does not re-decide. |
| Exact touch (`high == TP`, `low == SL`, both mirrors) | All four fill at the level. |
| Square-off fills at the **marked candle's close and only that candle** | Fill 2044 = the 15:00-stamped candle's close. It is **not** that candle's open (2041), **not** the previous candle's close (2041), **not** the last bar of the day (2058 — whose high 2060 would have paid the target). Mutants for open / last bar / previous candle are **all caught by the build's own suite**. |
| Square-off names a candle not in `bars` | Raises `SimulateError` rather than inventing a fill; the mutant that returns 0 instead is caught. |
| A non-executed day carries **no fill and no cost** | qty-zero and signal-unsizable days: `exit_paise is None`, `cost_paise == 0`, `gross == net == 0`, day still `consumed` and still recorded. The mutants that invent a fill (M11) or charge a cost (M09) are both caught. |

A structural point worth recording: `exit_price_paise`'s `_Bar` protocol declares only `stamp`
and `close_paise`. The module **cannot** read a candle's high or low — the blow-through mutant
had to reach for `getattr` to compile. The idealized-fill rule (CONTEXT 7-E9) is enforced by
the type surface, not only by tests.

---

## 4. Mutation matrix — 33 mutants (directed check 4)

Every mutant is a textual edit to a committed source file; the chunk-8 subset runs, and
anything that survives it is re-run against the **entire** 1,552-test suite. All four mutated
files (`simulate.py`, `config.py`, `signals.py`, `trade_evidence.py`) were restored and
verified **byte-identical by sha256 against their committed blobs**.

**Builder's 17, reproduced — 17/17 caught:** ceil instead of floor · half-up rounding of the
share count · long/short gross flipped · cost added not subtracted · target priced at the stop
· stop priced at the target · square-off at the bar OPEN · square-off at the LAST bar · a
non-executed day charged a cost · the qty-zero flag dropped · an unsizable day inventing a
fill · the gap flag lost · the risk budget silently defaulted · a qty-zero day dropped · a
consumed day reported unconsumed · the both-touched flag dropped · a missing square-off candle
silently priced at zero.

**My additions — 16 more:**

| # | Mutant | Result |
|---|---|---|
| M18 | floor off by one at the exact budget (Rs 1,000.01 sizes a share) | **caught** |
| M19 | cost sign: `net = cost − gross` | **caught** |
| M20 | the cost charged **twice** | **caught** |
| M21 | net and gross **swapped** in the record | **caught** |
| M22 | the `TradeRecord` dropped whenever flags are non-empty | **caught** |
| M23 | a target exit pays the candle's HIGH, not the level | **caught** (by F1 — its 12:00 candle's high 2055 overruns the target 2052) |
| M24 | short target priced at `entry + 3R` instead of `entry − 3R` | **caught** |
| M25 | `risk_per_trade` MISSING resolves to a default | **EQUIVALENT** — see below |
| M26 | `cost_per_trade` MISSING resolves to a default | **EQUIVALENT** — see below |
| M27 | B170's Decimal crossing replaced by float arithmetic | **caught** |
| M28 | a fractional-paisa amount rounded instead of refused | **caught** |
| M29 | the sweep **double-counts** every day | **SURVIVED the full 1,542-test suite** → closed by my probe |
| M30 | the sweep **drops** days that produced no executed trade | **SURVIVED the full suite** → closed by my probe |
| M31 | square-off priced at the candle **before** the marked one | **caught** (by the square-off golden) |
| M32 | the sweep resets its accumulator per symbol (keeps only the last) | **SURVIVED the full suite** → closed by my probe |
| M33 | a stop exit pays the candle's extreme, not the level | **caught** (by the both-touched golden) |

**M25/M26 proved EQUIVALENT, not a gap.** `load_config` refuses a missing key at lines
198–200 (`Missing key(s) in <path>: risk_per_trade.`) *before* any `raw[...]` lookup runs, so
the mutated `.get(key, default)` fallback is unreachable. Proved by execution, not by reading:
a config file with either money key deleted raises `ConfigError` naming the key. The hard
refusal the architect asked me to verify is genuine on both keys.

**Final tally: 33 mutants — 28 caught by the build's own suite, 2 proved EQUIVALENT, and 3
real coverage gaps (M29 / M30 / M32, all three in the evidence generator's `run_sweep` loop)
closed by the probes kept in `tests/test_review8_probes.py`. 0 survivors.**

The build's suite is genuinely strong on the engine: every mutation of sizing, exit pricing,
the money and the config validators died against it, including several I expected to slip
through (the blow-through fill, the prior-candle square-off, the doubled cost, the swapped
net/gross). The only place it had a blind spot is the evidence generator's accumulation loop.

Each kept probe was verified to **fail** on its mutant — a probe that cannot fail is
decoration. All eight mutant/probe pairs were re-run and every one is killed by a named test.
The four probes that duplicate coverage the build already has were kept anyway, as explicit
named pins on semantics that are currently protected only as a side effect of a fixture's
candle values.

---

## 5. Evidence pack, re-derived (directed check 5)

**Re-run.** `python docs/evidence/chunk8_sweep.py` executed read-only and offline against the
local stores. It reproduced **every** number: 290 stock-days walked, 146 signalled, 146
executed, net −Rs 1,934.95, and all eight invariant lines PASS with 0 violations.

**Partition.** 146 entered / 88 armed-no-qualifying-close / 56 never-armed = 290 — **identical
to chunk 7's**, which REVIEW_7 reproduced independently. The exit split (86 stop / 36
square-off / 24 target) also matches chunk 7's.

**Independent re-derivation of the pack from its own printed rows** — a parser importing
nothing from `src/acumen` read all 146 rows and recomputed, per row: the per-share risk from
`|entry − stop|` signed by side, the 3R target, `qty = 100,000 // risk`, **both** sizing
bounds, the fill level for each exit kind, the signed gross, and the net:

| Check (146 rows) | Violations |
|---|---|
| risk == \|entry − stop\|, signed by side, and > 0 | **0** |
| target == entry ± 3 × risk | **0** |
| qty == floor(100,000 / risk) | **0** |
| `qty × risk ≤ 100,000` | **0** |
| `(qty + 1) × risk > 100,000` | **0** |
| target/stop fill == the LEVEL | **0** |
| gross == qty × (fill − entry), signed by side | **0** |
| net == gross − 10,000 | **0** |
| target gross == qty × 3 × risk | **0** |
| stop gross == −qty × risk | **0** |

| Total | Pack | Recomputed | |
|---|---|---|---|
| Executed trades | 146 | 146 | MATCH |
| Shares transacted | 53,750 | 53,750 | MATCH |
| Gross PnL | Rs 12,665.05 | Rs 12,665.05 | MATCH |
| Costs paid | Rs 14,600.00 | Rs 14,600.00 | MATCH |
| **Net PnL** | **−Rs 1,934.95** | **−Rs 1,934.95** | MATCH |
| Gross profit / loss | Rs 101,099.20 / −Rs 88,434.15 | same | MATCH |
| Winners / losers / flat | 45 / 101 / 0 | 45 / 101 / 0 | MATCH |

**Rare-shape ZEROs verified against the store, not assumed:** gap entries 0, qty-zero 0,
signal-unsizable 0, both-touched 0, square-off-at-entry-candle 0, rule-3 tie days 0 — and
independently, **not one of the 146 printed rows carries any flag at all**, which is the same
statement reached from the other side.

**The exact-budget day the builder cited.** Found and recomputed — and the claim is
*understated*. There are **16** days in the window sized at exactly the budget, of which
**four** are 400-share days: RELIANCE 2026-07-13 and ICICIBANK 2026-07-06 and BHARTIARTL
2026-07-23 and HDFCBANK 2026-06-12, each `risk 250 paise × 400 = 100,000` exactly, with the
401st share at 100,250 > 100,000. The extremes are ICICIBANK 2026-05-07 (`80 × 1,250`) and
HDFCBANK 2026-05-22 / 2026-07-07 (`125 × 800`). The floor is tight on all 16.

**Honesty language present.** Section 1 states outright: *"It is **not** a backtest result.
There is no portfolio here, no equity curve, no metric and no capital constraint: those are
chunks 9 and 10. Five symbols over three months is a wiring witness, not a strategy
measurement, and nobody should read a profit into it."* The **empty-factor-table disclosure**
is present with its REVIEW_7 §6 justification and chunk 9's wire-the-real-table duty; so are
the read-only/offline disclosure (naming the cached master dump used), the idealized-fill
disclosure (CONTEXT 7-E9), and the gate-battery-recomputed-per-day note. The rare-shape table
carries its own "a zero here means this window carries NO real-data witness for that branch"
sentence. This is the standard of disclosure the persona asks for.

---

## 6. Config discipline (directed check 6)

* **No money amount hardcoded anywhere in `src/acumen`.** I walked the AST of **every** module
  in the package for the CONTEXT 3.5 amounts (1000 / 100 rupees, 100,000 / 10,000 paise). The
  amounts appear **nowhere**. The only `100` in `simulate.py` is `format_paise`'s
  `magnitude // 100, magnitude % 100` — the paise→rupee unit split for display, not an amount.
  The build's own tripwire (`{n for n in numbers if n > 2} == {100}`) is therefore accurate,
  and my sweep is strictly broader than it.
* **`risk_per_trade` MISSING → hard refusal, never a default.** `ConfigError: Missing key(s)
  in <path>: risk_per_trade.` A `null` value additionally refuses at the point of use
  (`require_risk_per_trade_paise`), which is the OPEN-1 guard kept as a regression per receipt
  R3-a. Both paths verified by execution.
* **`cost_per_trade` the same.** Missing → `Missing key(s)`. Null → refused at load with a
  message citing CONTEXT 3.5/R1-Q23. Zero and negative → refused.
* **B170's single Decimal crossing.** A fractional-paisa rupee amount is **refused, not
  rounded**, on both keys: `risk_per_trade: 1000.005` and `cost_per_trade: 100.001` each raise
  at the conversion. A whole-paisa fractional amount converts exactly (`12.34 → 1234` paise).
  The mutants that route the conversion through float (M27) or drop the integrality check
  (M28) are both caught.

---

## 7. Purity (directed check 7)

My own AST walk of `src/acumen/simulate.py`, independent of the build's test:

* **imports:** `__future__`, `dataclasses`, `datetime`, `fractions`, `typing`, `signals` —
  stdlib plus one pure engine module. No I/O library, no network, no `os`, no `pathlib`.
* **float literals: NONE.**
* **true division (`/`): NONE.** Floor division at exactly two lines: 188 (the sizer) and 456
  (the display split). `%` appears once, at 456, on integers.
* **calls:** `int`, `isinstance`, `tuple`, `dict`, `append`, `dataclass` and the module's own
  functions. **No** `now` / `today` / `utcnow` / `open` / `read_text` / `write_text` / `round`
  / `print` / `float` / any network call.

Integer paise end to end; a PnL sum over the full history is exact. CONTEXT 6 and 7-E11 hold.

---

## 8. Class-B decisions B169–B177 — judged

| # | Decision | Judgment |
|---|---|---|
| **B169** | `cost_per_trade` becomes a config key rather than a constant in `simulate.py`, required to be present | **APPROVED.** It mirrors `risk_per_trade`, the card names config+loader as the source, and my AST sweep confirms no money amount survives anywhere in the package. "Required, never defaulted" is enforced and proved. |
| **B170** | Both rupee amounts cross to paise exactly once, through `Decimal`; a fractional-paisa amount is refused | **APPROVED — with one correction to the recorded rationale.** The decision is right and the refusal works. But the rationale's witness is not reproducible: `12.34 * 100` is `1234.0` exactly in CPython, not `1233.9999999999998`. The decision stands on real witnesses I measured instead — **9,174** rupee amounts between 0.01 and 2000.00 lose a paisa under `int(value * 100)`, e.g. `0.29 → 28`, `0.57 → 56`, `1.13 → 112`. Filed as INFO C3, not a defect. |
| **B171** | Every evaluated stock-day yields exactly one `TradeRecord`, including days that traded nothing | **APPROVED.** The no-cross, signal-unsizable and qty-zero shapes each produce a record; `executed`/`signalled` separate the three shapes cleanly. Mutants that drop a record (M14, M22) are caught. This is what lets chunk 9 count records instead of inferring from nulls. |
| **B172** | A qty-zero or signal-unsizable day carries NO fill price while keeping entry/stop/target and the exit KIND | **APPROVED, and it is the right call.** Writing a counterfactual fill would let chunk 9 sum a trade that never existed. M11 (invent a fill) is caught. |
| **B173** | The square-off is priced at the CLOSE of the candle chunk 7's marker NAMES; chunk 8 does not re-decide the candle | **APPROVED.** Correct division of labour — chunk 7 chose the candle and REVIEW_7 approved it. Verified against CONTEXT 3.4-5 / R1-Q18 / E12: all 36 real square-offs filled at their marked candle's close and all 36 markers were the 15:00-stamped candle. Mutants for open / last bar / prior candle all die. |
| **B174** | The generator lives at `docs/evidence/chunk8_sweep.py`, implementation in `src/acumen/trade_evidence.py` | **APPROVED with a caveat.** The literal reading of the new rule is right, and putting the implementation in the package is what made most of it unit-testable. The caveat is that the one part which stayed untestable-by-omission — `run_sweep`'s accumulation loop — is exactly where my three surviving mutants landed (finding C1, now closed). |
| **B175** | The evidence run takes the NEWEST cached instrument-master dump and PRINTS the filename | **APPROVED.** Tick sizes are per-symbol constants, not a daily quantity, so the choice is safe; naming `OpenAPIScripMaster_2026-07-28.json` in the pack is what makes it auditable. I confirmed the pack states it. |
| **B176** | The named real golden is asserted FROM THE STORE and skips with the exact missing path in a bare clone | **APPROVED.** On this machine the store is present and the test **ran** (no skips in either full-suite run). I re-derived the same numbers from the raw parquet independently. The companion test pinning the committed pack to the same figures is a good anti-drift device. |
| **B177** | The invariant report is unit-tested to be able to FAIL, one test per line | **APPROVED, and this is the best decision in the entry.** Verified by count: **8 invariant lines in the pack, 8 can-fail tests** in `test_trade_evidence.py`, one per line. "A PASS line that cannot fail is decoration, not evidence" is exactly the right standard, and it is the standard I applied to my own probes in return. |

All nine approved; B170 carries a correction to its recorded rationale, not to its decision.

---

## 9. Findings

### Quant reviewer

**Q1 — INFO — the two rarest money branches still have no real-data witness.** The window
produces zero gap entries, zero qty-zero days, zero both-touched candles and zero rule-3 tie
days. Both branches are covered only by hand-computed fixtures. This is a fact about the
90-day, 5-symbol window, not about the code — and the pack **says so out loud in its own
counted table**, which is the honest handling. Carried forward: chunk 12's validation pack
already owes a real gap-entry day (REVIEW_7 Q3) and now also owes a real qty-zero day.

**Q2 — INFO — the B159 entry-candle square-off is a fixture-only shape, and it costs Rs 100.**
When no 15-minute candle trades after the entry candle, the trade is flat and still pays the
full round-trip cost (net −Rs 100.00). That is correct — a position was opened and closed —
and CONTEXT 3.4-5's "the 15:00–15:15 candle's close" has no other honest reading when that
candle does not exist. Chunk 7 decided it (B159), REVIEW_7 approved it, chunk 8 only prices
it. Zero occurrences in the real window. Recorded so a later reader does not re-litigate it.

**Q3 — INFO — chunk 8 correctly computes no portfolio quantity.** No capital constraint, no
notional cap, no concurrency count, no Q40-d capital-infeasibility flag. CONTEXT 3.5 assigns
all of those to the portfolio layer and the card assigns them to chunk 9. `TradeRecord` carries
`qty` and `entry_paise`, so notional is derivable without re-running anything. No scope creep;
noted because a reader could mistake the absence for an omission.

### Code reviewer

**C1 — MEDIUM — `run_sweep`'s accumulation loop had zero test coverage. *(CLOSED.)*** The
build unit-tests every function that **consumes** a `SweepResult` — the totals, the partition,
the shape counts, all eight invariants — on synthetic records, but nothing exercised the loop
that **builds** it. Three independent mutations of that loop survived the entire 1,542-test
suite: double-appending every day (every figure in the pack doubles), dropping the days that
produced no executed trade (290 walked days collapse to 146 and every printed total stays
unchanged, so the pack would still look self-consistent), and resetting the accumulator per
symbol (four of five symbols vanish). The generated numbers are **correct today** — I verified
the partition and every total against the store this session — but the committed evidence pack
is precisely the artifact CLAUDE.md's new rule exists so a later chunk can re-check, and it
rested on an untested loop. **Closed** by four probes in `tests/test_review8_probes.py`, each
verified to fail on its mutant.

**C2 — LOW — the committed evidence pack is not byte-reproducible from its own committed
generator.** Re-running `docs/evidence/chunk8_sweep.py` produces a file that differs from the
committed one by 2 insertions / 2 deletions: the "Arithmetic check: net = gross − cost…"
sentence sits **before** the rare-shapes table in the generator's output (`trade_evidence.py`
line 478 emits it ahead of line 483's rare-shapes block) and **after** it in the committed
file. Not one number moves, and every figure I re-derived matches. But the new evidence rule's
whole value is "regenerate and diff", and a chunk-9 or chunk-12 session doing exactly that will
get a diff it has to adjudicate. The committed file appears to have been hand-edited after
generation. One-line fix whenever the pack is next regenerated; not worth a commit of its own,
and **not a FAIL trigger** since no claim is affected.

**C3 — INFO — B170's recorded rationale cites a float value that does not reproduce.** See
the B170 row above. The decision is correct; the witness is not. Recorded because CLAUDE.md
makes the PROGRESS `decisions:` block the permanent record of *why*, and a wrong "why" survives
into every future reading of it.

**C4 — INFO — `simulate_day` accepts `cost_paise=0` while the loader refuses it.** The engine
validates `>= 0`, the config validates `> 0`. Nothing today can reach it: the loader is the
only sanctioned source. On reflection this is **right**, not a gap — an engine that asserted
"the cost must be Rs 100" would *be* the hardcoded spec constant the card bans, and the pure
function correctly takes whatever cost it is handed. Recorded so it is not later "fixed" into
a defect.

**C5 — INFO — the money's type surface does real work.** `exit_price_paise`'s `_Bar` protocol
exposes only `stamp` and `close_paise`, so the module structurally cannot read a candle's high
or low into a fill; and `simulate.py` contains no float literal and no true division, so a
paisa cannot be lost on the way to a report. Both are load-bearing properties that happen to
be enforced by design rather than only by assertion. Worth keeping in future refactors.

---

## 10. Standard sweep

| Check | Result |
|---|---|
| **Full suite from clean** | **1552 passed / 0 failed** (`.pytest_cache` and every `__pycache__` deleted first) = the build's 1542 + this review's 10 probes. The build's own 1542/0 claim was reproduced first, exactly. **No skips** — the store-backed golden ran. |
| **Fixtures byte-frozen** | `git diff 79c3c79~1..f079a2a -- tests/fixtures poc` is **empty**. `git diff chunk7-pass..HEAD -- tests/fixtures poc` is **empty**. **F9's 15 real TCS days are untouched**, as is every other fixture and every `poc/data` CSV. |
| **No test weakened** | `test_config.py` goes 22 → 30 test functions; **no test function removed**, **no assertion removed**. The only deleted lines are synthetic YAML config bodies gaining the newly-required `cost_per_trade` key — mandatory, not weakening. `test_simulate.py` (+1100) and `test_trade_evidence.py` (+279) are pure additions. Net strictly stronger. |
| **Scope containment** | `signals.py`, `poc.py`, `bias.py`, `signal_engine.py`, `bias_engine.py` are **untouched** in the span. `CONTEXT.md` and `plan.md` **untouched**. Every changed line traces to the card's scope (sizing, exit pricing, ₹100 cost, the record schema) or to the evidence rule. |
| **Commit hygiene under the NEW rules** | 4 commits, each a logical unit with a what+why body citing chunk + spec section. `(unreviewed)` on both commits touching `src/`/`tests/`; correctly absent on the docs-only and ledger-only commits. Evidence committed with the claims. **All three new rules obeyed.** |
| **AI attribution** | None. No `Co-Authored-By`, no "Generated with", no tool or product named. Author is the operator on all four commits. |
| **Secrets** | No `.env`, `data/` or `cache/` path is tracked. No credential, key, TOTP or PIN appears anywhere in the span. |
| **ASCII-only sources** | `simulate.py`, `trade_evidence.py`, `chunk8_sweep.py` and my probe file are all pure ASCII (chunk-0 B7). |
| **PROGRESS / STATUS per template** | The chunk-8 entry carries all eight template fields in plan.md §6's exact order, newest on top, with honest `state-for-next-session` (it names its own two uncovered branches and the reviewer's attack order). STATUS.md line set to `chunk 8: built`. |
| **Pushed-SHA chain** | `origin/main == local main == f079a2a` — the build session pushed as required. Chain intact from `chunk7-pass`. |
| **Builder's own suggested attack order** | All five items run, and exceeded: (1) short sign discipline on **every** branch — §2b; (2) exact-touch and both-touched fills — §3, plus a blow-through case the build did not have; (3) the square-off's candle incl. the B159 case — §3, plus a "no other candle of the day" probe; (4) the floor at both bounds — §2a and an end-to-end boundary test at 100,000 / 100,001 paise, plus the 16 real exact-budget days; (5) whether a record can be dropped or double-counted — **this is where the one MEDIUM came from**. |

---

## 11. Tests this review adds and keeps

`tests/test_review8_probes.py` — 10 tests, each verified to FAIL on its mutant and pass on
HEAD, each carrying its hand-computed numbers:

1. `test_the_sweep_keeps_every_walked_day_exactly_once` — kills the double-count.
2. `test_the_sweep_keeps_the_days_that_produced_no_executed_trade` — kills the drop.
3. `test_the_sweep_accumulates_across_symbols_rather_than_resetting` — kills the per-symbol reset.
4. `test_the_sweep_carries_its_money_inputs_onto_the_result` — the pack cannot claim CONTEXT
   3.5's amounts while the run used others.
Probes 1–3 close finding C1 — each kills a mutant that survived the whole 1,542-test build
suite. Probes 4–10 duplicate coverage the build already has; they are kept as **explicit named
pins** on semantics currently protected only as a side effect of a fixture's candle values
(F1's high happens to overrun its target; the square-off golden's candles happen to differ):

4. `test_the_sweep_carries_its_money_inputs_onto_the_result` — the pack cannot claim CONTEXT
   3.5's amounts while the run used others.
5. `test_a_square_off_cannot_be_priced_from_any_other_candle_of_the_day` — asserts the fill
   matches **no** other candle's close or open, not merely that it matches the right one.
6. `test_a_candle_that_blows_ten_rupees_through_the_target_still_pays_three_r` — the level-fill
   rule stated directly; the two answers differ by Rs 1,660.
7. `test_the_short_mirror_of_a_stop_blown_through` — the same on the short stop.
8–10. `test_the_floor_at_the_exact_budget_end_to_end[...]` — three parametrized cases pinning
   Rs 1,000.00 → 1 share, Rs 1,000.01 → 0 shares, Rs 999.99 → 1 share **through the whole
   pipeline**, where the risk comes off real candles rather than being passed in (the build
   pins the boundary on `position_size` alone).

They use hand-built fakes only — no store, no network, no clock — so they run in a bare clone.

---

## VERDICT: **PASS**

I would stake the trader's account on this chunk's arithmetic. The sizing floor is exact at
both bounds, the fills are the levels and provably cannot be the candle extremes, the short
mirror is right on every branch by recomputation rather than by symmetry, no day is dropped or
double-counted, the money is integer paise end to end with no float anywhere near it, and the
one real gap I found is in the evidence generator rather than the engine — and it is closed in
this commit.

Chunk 9 is unblocked. Its inherited duties are unchanged and recorded: wire the REAL chunk-3
factor table (this window's empty table is proved correct for this window only), recompute
gate 1P per day, read the disclosed-residual register before any per-symbol statistic, and add
the Q40-d capital-infeasibility flags, which are deliberately not in chunk 8.
