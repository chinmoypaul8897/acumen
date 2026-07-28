# REVIEW_5B — chunk 5B (full-universe 1-minute backfill + the FIX-2/3/4 data-ruling stack)

**Review type:** QC — `personas/quant_reviewer.md` AND `personas/code_reviewer.md` (upgraded from the
card's type C by the architect, because the FIX stack contains measurement logic no session has ever
reviewed).
**Span:** all commits `269c07e..708e144` EXCLUDING the three chunk-6 commits (`8b053c2`, `6ed863c`,
`9d9e702`, reviewed separately under `chunk6-pass`). Nine in-span commits, one verdict for the stack.
**Session:** fresh reviewer, zero shared context with any builder session. Read-only on `src/`,
`tests/`, `docs/` and every store; offline throughout (no `--allow-network`, no credentialed call).

---

## VERDICT: **FAIL**

The suite is green, the coverage arithmetic is honest, the ruling chain reads as a truthful narrative,
and the measurement logic — the signature gate, the floor bisection, the auction relief — is correct
and reproduces to the digit under independent re-derivation. Thirty-seven Class-B decisions were
judged; thirty-six hold.

The chunk nevertheless fails on its own deliverable. **1,963 symbol-days — all on SETTLED symbols —
are stored in the minute lake at a wrong price scale, between 0.1× and 5× the price the exchange
printed, and every one of them PASSES the gate battery and is counted inside the 413,914-day "usable"
headline.** TATASTEEL 2020-07-28 is stored with a 1-minute high of ₹36.00 against a bhavcopy high of
₹360.00, at a gate-1 volume gap of +0.071%. Chunk 9 would compute a POC, a stop-loss and a position
size from those prices and produce trades that look entirely plausible.

That is a violation of CONTEXT §7-E11 ("intraday engines run on RAW same-day 1-min prices … PnL in
that day's real rupees") in the data this chunk exists to produce, and it defeats the card's
"failures categorized" clause: these days are not categorized as failures at all — they are
categorized as passes. Per `personas/quant_reviewer.md`, "PASS only when you would stake the trader's
account on this chunk." I would not.

The verdict is **not** a judgement on the builder's execution of the rulings, which is of a high
standard throughout. The defect is an emergent hole in the ruled measurement architecture that no
ruling closed, plus a chunk-5B reporting bug that hid its size. Closing it needs an architect ruling
(Finding Q1 below), not a fix a session may choose for itself.

---

## 1. What this review did

- **Reran the entire suite from a genuinely clean state** (`.pytest_cache` and every `__pycache__`
  deleted first): **1253 passed / 0 failed** in 143s. Matches the FIX-4 PROGRESS claim exactly.
- Read CLAUDE.md, both personas, CONTEXT §3.1/§4.1/§4.3/§4.5/§5/§6/§7-E2/E3/E4/E5/E8/E11/E12,
  plan.md §1–§2 + the chunk-5B card, STATUS.md, all four 5B PROGRESS entries, the full ruling chain
  in QUESTIONS.md (Q-5, Q-10 + 2 addenda, Q-11 + 4 addenda, Q-12 + 2 addenda, the CONTEXT §4.5/§7-E4
  amendment), `docs/backfill_minute_report.md` in full, REVIEW_5A and REVIEW_6.
- Executed all twelve architect-directed checks and both persona checklists in full, fanned across
  fourteen independent read-only auditors, with **every claimed defect put through an adversarial
  refutation pass** (112 raw findings → 54 survived; 31 of 31 MEDIUMs were downgraded or refuted;
  one MEDIUM was upgraded to HIGH). Every finding below was then re-verified by the reviewer
  personally against primary data before being recorded.
- Wrote independent implementations rather than re-running the builder's code wherever the check
  allowed it: the signature-gate predicate, the four auction-relief conditions, gate 3, the coverage
  arithmetic, the CANBK bisection replay, and the price-scale sweep were all re-derived from the
  stores and the ledger importing nothing from `src/acumen`.

---

## 2. Ruling-chain audit (directed check 1)

**(a) The narrative is honest.** All seven `ARCHITECT'S RULING` blocks are present verbatim as
blockquotes, each structurally separated from the session's own `EXECUTED by …` prose, and no session
decision is dressed up as a ruling anywhere in the chain. The one reversal is stated plainly and
twice — ADDENDUM 4's own title says "supersedes B123's restriction", and its closing bullet says
"B123 is superseded, not deleted", with the superseded text left standing in the FIX-3 entry rather
than rewritten. The Q-11 → ADDENDUM 1 → 2 → 3 → 4 progression reads as a real investigation: each
addendum states the measured evidence that forced it, and Q-12's own STOP ("no silent decision") is
honoured — the session executed the ruled median and raised the bias rather than fixing it quietly.

Two execution notes have drifted from the code they describe (Findings C7, C8): ADDENDUM 2's stated
hunt scope omits the gate-3-failure arm the code also carries, and ADDENDUM 4's "admitted only by one
of the two signatures" omits the `force_ex_dates` re-admission (which is itself correct and recorded
as B138). Both are prose, not behaviour.

**(b) Code implements only the final state — no bypass found.** Proved by AST call-graph over
`src/` + `scripts/`, not by grep:

- **The factor-table path is unreachable for a map-required symbol on every writing path.**
  `unadjust_bars` has exactly two call sites; the live one (`minute_backfill.py:427`) is guarded by
  `adjustment_map is None`, and both routes into it are gated — the CLI exits 2 via
  `map_covers_route` (`minute_backfill.py:1337-1341`) and the runner returns
  `STATUS_MAP_UNBUILDABLE` before reaching `backfill_symbol`
  (`universe_backfill.py:1339-1346`). `build_symbol_factors` has zero callers in `src/`. No flag, no
  except branch and no exported test helper reaches it.
- **Floors and relief are reachable only through their ruled gates.**
  `binary_search_floor` ← `search_event_floor_live` ← `hunt_symbol_floors` ← `_hunt_rounds` ←
  `run_floor_pass` ← `process_symbol`, guarded by `floor_hunt_owed` → `floor_hunt_in_scope`; a single
  chain, no second caller. `auction_relief` has one non-test call site
  (`universe_backfill.py:765`), inside the `else:` of `if result.passed:`, and independently
  re-asserts its own above-ceiling condition at `quality_gates.py:172-174`.
- **The band constants are byte-identical everywhere.** An AST scan for every reachable literal of
  −0.1 / 5.0 / 20.0 finds only `VOLUME_GAP_MIN_PCT` (`quality_gates.py:63`),
  `VOLUME_GAP_MAX_PCT` (:64) and `AUCTION_RELIEF_MAX_SHORTFALL_PCT` (:119). `volume_gate` takes no
  band parameter, so no caller can widen it by argument, and there is no assignment or monkeypatch of
  either constant in `src/`, `tests/` or `scripts/`. `git diff chunk5A-pass..708e144 --
  src/acumen/quality_gates.py` touches neither the gate nor the constants. The price-containment
  tolerance is likewise unchanged; its expression only moved into the split-out
  `_day_price_contained`.

---

## 3. The directed checks, one by one

| # | Check | Result |
|---|---|---|
| 1 | Ruling-chain audit + bypass hunt | **PASS** — §2 above. Two prose drifts (C7, C8) |
| 2 | Signature gate reproduced independently | **PASS** — §4 |
| 3 | Floors: CANBK bisection, 3-probe rule, acceptance oracle, VEDL unwind | **PASS** — §5 |
| 4 | Auction relief: four conditions, one real day, the 432 | **PASS** — §6 |
| 5 | Coverage arithmetic + DoD both ways | **PASS on the number**, reporting defects Q3/Q4 — §7 |
| 6 | Gate-3 spot-recompute (BDL, IOC, HINDPETRO) | **PASS** — §8 |
| 7 | Q-5 probe-day fix, both enforcement points | **PASS** — §9 |
| 8 | Operator repairs derive from clean recomputation | **PASS** — §10 |
| 9 | IOC cascade finding + blast-radius judgement | **PASS**, architect note recommended — §11 |
| 10 | Store integrity, digests, atomicity, claim/evidence | **PASS**, defects C4/C5/Q5 — §12 |
| 11 | Class-B sweep B93–B140 | 36 approved, **1 challenged** (B127) — §13 |
| 12 | Standards: tests, determinism, hygiene, secrets, SHAs | **PASS** — §14 |

---

## 4. The signature gate, reproduced from scratch (directed check 2)

I recovered the FIX-3 residual table from `git show dc35b59:docs/backfill_minute_report.md` (17
gate-3 failures) and applied `|raw gap| < |k−1|/2` with my own arithmetic, importing nothing:

**ADMITTED (11):** BDL 2024-05-24 (10.44% vs half-step 25.00%) · BEL 2017-03-16 (5.22% / 45.00%) ·
GAIL 2017-03-09 (2.52% / 12.50%) · HINDPETRO 2017-07-11 (0.35% / 16.67%) · INOXWIND 2024-05-24
(10.98% / 37.50%) · IOC 2016-10-18 (0.17% / 25.00%) · IOC 2018-03-15 (2.77% / 25.00%) · IOC
2022-06-30 (1.43% / 16.67%) · OIL 2017-01-12 (4.63% / 12.50%) · PETRONET 2017-07-03 (0.87% / 25.00%)
· UPL 2019-07-02 (8.62% / 16.67%).
**REJECTED (6):** ASTRAL (38.49% / 10.00%) · BPCL (101.21% / 16.67%) · COCHINSHIP (40.00% / 25.00%) ·
GAIL 2018 (201.98% / 12.50%) · OIL 2018 (42.44% / 16.67%) · VBL (65.70% / 16.67%).

Exactly eleven and exactly six, and the six are precisely the six the docstring names. **B133 is
confirmed to the row.** The predicate is scale-free by construction, takes magnitudes rather than
signed values (a +38% gap against a −20% step is correctly refused), and is strict at the boundary,
which is the honest reading of "nearer".

**Zero probes for a non-qualifying event, proved from the run's own ledger.** Every symbol with no
admitted signature spent zero probes (APLAPOLLO, COCHINSHIP, HDFCBANK, LODHA, PGEL). Four symbols
carrying signatures spent zero probes (IOC, PETRONET, TATASTEEL, NESTLEIND) because clause (ii)
refused the era for a second uncommitted source — the refusal happens before any probe. The three
symbols that spent probes without a signature (DIXON 11, JUBLFOOD 13, RELIANCE 13) are
**provable-era** searches under the FIX-3 ≥10% scope gate, which clause (i) explicitly leaves
untouched. The ruling's "never blanket" is honoured.

The era-cliff arm is sound: the span is the gated days strictly below the ex-date, `MIN_CLIFF_DAYS =
20` cannot be dodged, and the rate test is `>= 0.95` exactly.

---

## 5. Floors (directed check 3)

**CANBK → 2022-05-10, re-derived from persisted provenance alone.** From
`data/adjustment_maps/CANBK.json`, the recorded visit order is 2024-05-14 (event-in, the newest day,
so the floor model applies) → 2017-02-17 (out, the oldest, so a splice exists inside the span) →
2020-09-30 (out) → 2022-07-21 (in) → 2021-08-27 (out) → 2022-02-08 (out) → 2022-05-04 (out) →
2022-06-13 (in) → 2022-05-24 (in) → 2022-05-13 (in) → 2022-05-09 (out) → 2022-05-11 (in) →
2022-05-10 (in). Thirteen probes; last event-out 2022-05-09, first event-in 2022-05-10; the boundary
is **uniquely determined** and lands on the recorded `floor_date`. Every probe carries
`ratio_high`/`ratio_low` of exactly 0.2 or exactly 1 — no interpolation anywhere. The ledger's 15
probes reconcile as 13 (the 2024-05-15 split) + 2 (the 2017-02-17 dividend).

**The absent-throughout 3-probe rule (B134)** holds on all four real cases. HINDPETRO 2019-06-06,
NTPC 2019-02-06, VEDL 2023-12-27 and VEDL 2018-11-06 each carry exactly three probes — newest, oldest
and a genuine midpoint — all answering `event-out`. VEDL's are 2018-11-05 / 2018-03-20 / 2018-07-11
and 2023-12-26 / 2023-05-30 / 2023-09-08. One `event-in` or one `undecided` leaves the search
UNRESOLVED, and that refusal is tested directly.

**Acceptance runs through the same builder oracle.** Measured floors are passed into
`build_map(..., floors=...)` (`universe_backfill.py:1976-1979`), not layered onto a committed map;
`_floored_events` forces a floored event absent for eras below the floor and exempts it from the
probe-gap guard; the era then satisfies the identical containment and the identical unwidened band as
any other era. There is no relaxed tolerance and no skipped check on the floored path.

**The VEDL unwind is real.** 17 of 19 eras provable, matching the report's 13 promotions, with both
floors absent-throughout and every promoted era's chain consistent with them.

---

## 6. Auction relief (directed check 4)

I re-implemented the four ruled conditions from the ruling's own text and ran them over the raw
stores, using neither `quality_gates` nor `universe_backfill`. On HDFCBANK — the largest relief
population — my implementation independently identified **exactly 43 relief-qualifying days**,
matching the ledger's 43. Sample, verified to the paisa:

> **HDFCBANK 2023-11-28** — gate-1 gap +11.613% (above the ceiling); 1-min fold H/L/O =
> 153725/152580/153520 paise; raw bhavcopy H/L/O = 153725/152580/153520 paise — exact on all three;
> first stamp 09:15:00; shortfall inside the 20% cap. Relief correctly granted.

The four conditions are each individually necessary in the code (`quality_gates.py:183-195` builds a
`failed` list and refuses on any). A below-floor failure can never be relieved — condition (a) is
re-asserted inside `auction_relief` itself, independent of the caller. `gate1_pass` stays the strict
count and is never overwritten; `gate1_relieved` is a separate field.

**The 432 traces exactly.** From the ledger alone: 432 relieved days on settled symbols; 435 across
all symbols (ASTRAL, IEX and NTPC contribute 1 each and are quarantined); strict 413,482; effective
413,914; denominator 434,591 → **95.2422% with relief, 95.1428% without**, both matching the report's
95.2%/95.1%. Section 3d pairs the 435 numerator with the settled-only 420,297 denominator without
explaining the three-day gap (Finding C9).

---

## 7. Coverage arithmetic and the definition of done (directed check 5)

Recomputed from `data/universe_backfill/ledger.json` with my own code:

| Quantity | Recomputed | Report |
|---|---|---|
| Settled / quarantined symbols | 204 / 6 | 204 / 6 |
| Gated symbol-days, settled | 420,297 | 420,297 |
| Gate-1 strict pass | 413,482 | 413,482 |
| Auction-relief pass | 432 | 432 |
| Effective pass | 413,914 | 413,914 |
| Quarantined symbol-days | 14,294 | 14,294 |
| Denominator | 434,591 | 434,591 |
| **Coverage** | **95.2422%** | **95.2%** |
| Strict-band coverage | 95.1428% | 95.1% |

**The exclusion ledger balances exactly**: 413,482 + 432 + 6,383 + 14,294 = 434,591. Every symbol-day
sits in exactly one bucket, which is what CONTEXT §7-E3 asks for at the accounting level.

**The DoD holds under every defensible reading but one — and the one that fails is the report's own
arithmetic error.**

| Reading | Result | DoD |
|---|---|---|
| A gate 1 only, gated denominator (the report's) | 413,914 / 434,591 = 95.2422% | MET |
| B gate 1 strict, no relief | 413,482 / 434,591 = 95.1428% | MET |
| C gate 1 AND gate 2, overlap-aware | 413,735 / 434,591 = 95.2010% | MET |
| D gate 1 AND gate 2, the report's naive subtraction | 412,723 / 434,591 = 94.9681% | **NOT MET** |
| E gate 1 only, denominator = every stored day | 413,914 / 434,769 = 95.2032% | MET |
| F gate 1 AND gate 2 overlap-aware, stored-day denominator | 413,735 / 434,769 = 95.1620% | MET |

Reading D is wrong: it subtracts all 1,191 gate-2 exclusions from the gate-1-passing count, but 1,012
of them are the amendment's "missing minutes **on a day where gate 1 also fails**" trigger, which by
construction fires only on days already outside that numerator (`quality_gates.py:311-320` sets it
only in the `else` of `if volume_reconciled is True`, and `universe_backfill.py:782` passes the same
predicate that gates `gate1_pass`). The report's own headline figure therefore understates the chunk's
position and is the only reading under which the DoD appears to miss (Finding Q3).

**The DoD is MET.** That is not what fails this review.

---

## 8. Gate 3, recomputed from stored data (directed check 6)

All three cases reproduce exactly from the stored 1-minute closes with my own arithmetic:

| Case | Pre-ex | Ex | k | Raw gap | Adjusted gap | Verdict |
|---|---|---|---|---|---|---|
| BDL 2024-05-24 | 2024-05-23 @ 281056 | 2024-05-24 @ 155205 | 0.5 | **−44.78%** | **+10.44%** | PASS |
| IOC 2016-10-18 | 2016-10-17 @ 16058 | 2016-10-18 @ 16085 | 0.5 | +0.17% | +100.34% | FAIL |
| HINDPETRO 2017-07-11 | 2017-07-10 @ 22773 | 2017-07-11 @ 22693 | 2/3 | −0.35% | +49.47% | FAIL |

BDL's repair is genuine, not cosmetic: at FIX-3 its raw gap was **+10.44%** (both closes in the same,
wrong domain); after the floor pass and the Q-5 measurement-day fix its raw gap is **−44.78%**, i.e.
close to the healthy k−1 = −50%, and the adjusted gap falls inside the 20% band. The pre-ex close
actually moved into the correct price domain.

118 ex-dates checked / 15 failed reconciles from the ledger, and all 15 rows appear in both section-5
tables with identical numbers. The k used is the chained same-ex-date product, and the 20% threshold
is CONTEXT §4.5's own, unwidened. HINDPETRO 2017-07-11's classification sentence is accurate: a floor
was measured for that symbol's 2019-06-06 event, and 2017-07-11's own era was refused for a second
uncommitted source, so no floor was fitted for it.

---

## 9. The Q-5 measurement-day fix (directed check 7)

`is_measurable_session` is enforced at both ends — probe-day selection and the era fold — and both are
tested. 2024-05-18 **is** a Saturday, the daily store does carry a bhavcopy row for it, and the
recovery ratio is a sharp outlier against its neighbours:

| Symbol | 2024-05-17 (Fri) | **2024-05-18 (Sat)** | 2024-05-21 (Tue) |
|---|---|---|---|
| BDL | 1.000 | **0.518** | 1.000 |
| INOXWIND | 1.000 | **0.796** | 1.000 |

These are post-repair ratios on raw stored bars. Scaled by the factors the vendor was applying at
probe time — BDL k = 0.5, INOXWIND k = 0.25 — they give 0.259 / 0.500 and 0.199 / 0.250, which are
exactly B139's recorded 0.259/0.500 and 0.196/0.246. **The evidence reproduces.** Because gate 1 must
hold on every probe day, that one excluded session was enough to make the only correct chain
un-provable, as recorded.

---

## 10. The operator repairs (directed check 8)

All three disclosures hold: a hand edit scheduled a recomputation, none asserted a result.

- **CANBK** — the ledger row was seeded with the event ex-date only; the floor value was re-measured,
  and the map carries all 13 probes with their verdicts (§5). `RunLedger.load` is a derived index and
  the re-measurement is what produced the committed answer.
- **The race** — all 210 ledger rows now carry the current `GATE_DEFINITION` and `REBUILD_DISCIPLINE`
  markers; none is stale. Clearing a marker genuinely schedules recomputation through
  `needs_reprocessing` / `floor_hunt_owed` / `reroute_owed` rather than relabelling.
- **BDL** — its map carries the current `MAP_MODEL`, and its 99.7% is produced by re-measurement on
  its own evidence (its gate-3 row now passes on recomputed closes, §8).

**Nothing hand-asserts a result anywhere.** No symbol is special-cased in `src/`; there is no
hardcoded floor date, factor or gate verdict. Every date literal in `src/acumen/` traces to a
CONTEXT- or plan-mandated constant (`MINUTE_DATA_FLOOR` = CONTEXT §4.3's own 2016-10 floor,
`UDIFF_FIRST_DATE` = §4.1's format boundary) or to a card-named evidence event
(KOTHARIPRO/GREENPLY/RELIANCE, the OPEN-8 list). Four ledger rows carry a blank `floor_discipline`
(Finding C10) — harmless, because all four are out of hunt scope.

---

## 11. The IOC cascade (directed check 9)

**The trace is recorded and reproduces.** IOC 2023-11-06: 1-minute fold LOW 9670 paise vs bhavcopy
LOW 9660 — a 10-paise, 0.1035% divergence, on a day whose high matches exactly and whose volume
reconciles. The containment limit is `max(2 paise, 0.1% × raw)` = 9.66 paise, so the day misses by
**0.34 paise**. PROGRESS's "0.3 paise past the ruled containment band" is accurate. The band was not
touched, and the probe-gap guard behaved exactly per Q-11's "at most ONE freshly-solved unknown per
era": one non-containing probe day makes its era un-provable, which leaves the next older era holding
two unknowns, and so on down the chain.

**Judgement (a finding, not a fix).** The guard is doing its job and the conservative case is strong:
the band is the acceptance criterion, a non-containing probe day means the chain is not proven, and
dropping the offending day would be free fitting of exactly the kind Q-11 forbids. But the blast
radius deserves an architect note for v2: one day, 0.34 paise past a relative tolerance, takes 14 eras
and ~370 symbol-days with it, and the deciding quantity is a **relative** floor, so the effective
tolerance scales with the share price — 2 paise on a ₹2 stock, ~140 paise on DIXON. The question worth
putting to the architect is about the tolerance's *shape*, not its width: should containment be
`max(2 paise, 0.1%)` as it is, or should a quorum rule (e.g. containment on all but one probe day,
with the outlier disclosed) replace the universal quantifier? Both are non-fitting oracles; only one
is fragile to a single microstructure print. **Recommended as a v2 question. No change proposed here.**

---

## 12. Store integrity (directed check 10)

- **Fixtures frozen.** `git diff --stat 269c07e..708e144 -- tests/fixtures poc` is empty, and so is
  the same diff against `chunk5A-pass`. CONTEXT.md and plan.md are untouched across the whole span.
- **Ledger claims are backed by map evidence.** No ledger row claims a floor its map does not carry.
  All 97 maps carry the current `MAP_MODEL` and `volume_estimator` markers; none is stale.
- **The reverse direction is not enforced** — see Finding Q5: two maps carry committed floors the
  ledger does not claim.
- **Atomicity.** Every store write goes through `atomic_io` (temp → fsync → rename, bounded retry
  with the denial re-raised) **except** `persist_map` (`vendor_adjustment.py:1884`), which is a plain
  `write_text` (Finding C4). The rebuild is genuinely idempotent by baseline classification, with an
  identity guard that makes a second application a no-op.
- **Report regeneration is deterministic.** Two `--report-only` runs to scratch paths differ only in
  the generation timestamp; against the committed report the only differences are that timestamp and
  the today's-date scope line. No network call; `git status --porcelain` clean before and after.

---

## 13. Class-B sweep — B93 through B140

`B111`–`B121` belong to chunk 6 and were approved in REVIEW_6; they are out of this span. The
thirty-seven in-span decisions:

**APPROVED (26):** B93 (the ruling's own enumeration is the code; `k == 1` events correctly excluded)
· B96 (one-pass cache + adapter, byte-identical contract) · B97 (eras derived, not hand-picked) ·
B100 (refusal, not fallback — returns before `backfill_symbol`) · B101 (MIN at both formation points)
· B102 (a chosen price factor of exactly 1 is never offered as `price-factor`) · B103 (withholds below
3 price-passing days) · B104 (unrun gate 1 keeps the conservative reading) · B105 (negative test
covers volume and open) · B106 (single net division; identity exact) · B107 (sticky reroute flag) ·
B109 (both markers self-clearing) · B110 (6 attempts, ~1.55s total, denial re-raised) · B122 (the
handoff is exactly the recorded reading and its size — 95 of 435 — is disclosed) · B123 (the
provable-only restriction is genuinely removed, not bypassed) · B124 (effective rate, as recorded) ·
B129 (every ParseException, deduped) · B130 (share-count components only) · B131 (pre-flight ceiling
scoped) · B132 (era refused outright when any non-target event lacks a committed source) · B133 (the
magnitude predicate, confirmed row-by-row in §4) · B135 (floors passed into `build_map`) · B137
(`as-fetched-floored` corrected by the matched multiple) · B139 (both enforcement points, §9) · B140
(in-loop ceiling scoped) · B99 (report name flagged, not drifted).

**APPROVED WITH NOTE (10):** B94 (both bounds wired at both entry points) · B95 (weekend row-count
routed to notes, weekday stays an anomaly) · B98 (groups and multiplies by ex-date) · B108 (the
substance is right; the recorded text and two `src` comments still attribute `_stored_day_is_raw` to a
path that never called it — now dead code) · B125 (gate and forced override exactly as recorded) ·
B126 (hypotheses well separated; the derived tolerance's gap denominator is order-dependent on the
7-hypothesis floored set only) · B128 (transient leaves the hunt open, deterministic closes it) ·
B134 (three probes required; note that the midpoint is chosen by index, not by trading-day distance)
· B136 (bounded at 3 rounds, shared cache, a round promoting nothing ends it) · B138
(`force_ex_dates` is populated only from previously RESOLVED floors, so it cannot admit an
event that was never floored).

**CHALLENGED (1):** **B127.** The recorded text says a floor is "carried only when the event still
resolves to the same committed price factor". FIX-4 widened `carry_floors_forward` to two further keep
branches — a floor is now also kept when the fresh map commits nothing for the event (`after is
None`) or commits exactly ABSENT. The widening is deliberate and correct (a floored event *should*
resolve to absent below its floor), but it is a Class-B change recorded nowhere: the FIX-4 entry
carries no decision for it, so the superseded B127 text is the only carry-rule statement the architect
scans. Per plan.md §5, "a deviation recorded nowhere = a defect". **Recording, not code, is what is
owed here.**

---

## 14. Standards (directed check 12)

- **No test weakened anywhere in the stack.** Only two test functions disappear across the span, both
  renamed and strengthened: `test_gate2_15_missing_passes_but_16_excludes` →
  `..._when_gate1_also_fails` plus three new tests and an `ast` probe that fails if the retired
  minute-count trigger returns; `test_vendor_volume_scaled_rights_measured_independently...` →
  `..._volume_takes_the_price_factor` plus the companion
  `test_a_volume_divergence_too_big_for_gate1_forces_measured_back` that PROGRESS promised. No test is
  skipped or xfailed anywhere in the suite.
- **The two re-pinned FIX-4 tests, judged on their stated reasons.** (i)
  `test_the_gate_definition_marker_moved...`: the substring assertion `"application-floors" in
  MAP_MODEL` → `"floor" in MAP_MODEL` is literally weaker, but it was replaced *because the constant
  legitimately moved* to `floor-aware-build+trading-day-probes-v4`, and two much stronger assertions
  were added in its place — `map_is_current` must be False for the v3 model and True for v4. Net:
  **re-pinned and strengthened**; the weak substring no longer carries the contract. (ii)
  `test_a_map_built_under_the_superseded_estimator_is_rebuilt_not_consumed`: `"stale under Q-12"` →
  `"map is STALE" and MAP_VOLUME_ESTIMATOR in line`, because a map can now be stale on the model
  alone. The new assertion pins strictly more (the estimator id must be named). **Re-pinned, not
  weakened.** Both contracts genuinely moved by ruling; neither test was made to pass.
- **Commit hygiene.** Nine in-span commits, all `chunk5B…`-prefixed, each a logical unit with a
  what+why body citing the ruling it executes. Five omit the `(unreviewed)` suffix (Finding C11) —
  the same class REVIEW_5A recorded as F4; four of the five are fix-session commits the rule arguably
  does not reach. No commit touches CONTEXT.md, plan.md, `tests/fixtures/` or `poc/`.
- **Secrets.** `.env` is gitignored and appears in no commit anywhere in history. No credential-shaped
  string in `src/`, `tests/`, `scripts/`, `docs/`, PROGRESS.md or QUESTIONS.md.
- **No AI attribution** in any commit message, trailer or tracked file.
- **Pushed-SHA chain.** `main` and `origin/main` agree at `708e144`; tags run `chunk0-pass` …
  `chunk5A-pass`, `chunk6-pass`, with no `chunk5B-pass` — consistent with STATUS.md.
- **Structure and hygiene.** No bare or broad `except` anywhere in the 5B modules. `vendor_adjustment`
  and `quality_gates` contain zero clock reads; every `datetime.now()` sits in the I/O shell or is
  injected. No float equality on money; the two `float()` calls are display-only. No hardcoded tick.
  `bias.py` and `poc.py` are untouched and remain pure.

---

## 15. FINDINGS

### Quant reviewer

**Q1 — HIGH — 1,963 symbol-days are stored at a wrong price scale and pass the gate battery.**
*Spec: CONTEXT §7-E11 (intraday engines run on RAW same-day 1-min prices); CONTEXT §7-E3 (a flagged
day is excluded and counted); plan.md chunk-5B card ("failures categorized"). **This is the FAIL.***

CONTEXT §4.5's gate 1 is a **volume** reconciliation, and the Q-11 ruling's price oracle is applied
**per era, over that era's probe days only** (`_price_contained` at `vendor_adjustment.py:1548-1566`
quantifies over `era.probe_days` — typically the four sessions before the next ex-date). Price and
volume factors are arbitrated *independently*, exactly as the ruling directs. When the vendor's
internal splice sits inside an era but older than its probe window, and the committed `k_volume`
happens to match what the vendor did to volume while `k_price` does not, **the day's price is wrong
and no gate can see it.**

Measured by me over **every one of the 433,065 stored symbol-days**, read-only, folding the parquet
minute store and comparing against the raw bhavcopy — counting only days that PASS gate 1 and whose
1-minute fold high differs from the bhavcopy high by a clear factor (>5%, two orders of magnitude
above microstructure):

| Symbol | Days | Factor | Status | Example |
|---|---|---|---|---|
| IOC | 1,042 | 0.667× | settled | 2018-04-05: stored high ₹116.10 vs bhavcopy ₹174.15, gate-1 gap +0.222% |
| TATASTEEL | 498 | 0.100× | settled | 2020-07-28: stored high **₹36.00** vs bhavcopy **₹360.00**, gap +0.071% |
| SRF | 216 | 5.000× | settled | 2016-10-03: stored high ₹9,625.00 vs bhavcopy ₹1,925.00, gap −0.002% |
| NMDC | 134 | 1.417× | settled | 2018-03-27: stored high ₹173.26 vs bhavcopy ₹122.25, gap +0.107% |
| RECLTD | 65 | 0.750× | settled | 2020-08-13: stored high ₹83.25 vs bhavcopy ₹111.00, gap +0.066% |
| APLAPOLLO | 3 | 2.000× | settled | 2018-10-01: stored high ₹2,566.70 vs bhavcopy ₹1,283.35, gap +0.000% |
| ASIANPAINT, BIOCON, PNB, SUZLON, TATAPOWER | 5 | one day each | settled | isolated cases |
| **Total** | **1,963** | | all **settled** | |

Widening the threshold from a clear factor to the containment oracle's own tolerance (>0.5%) gives
**2,651 gate-1-passing days off scale, 2,640 of them on settled symbols** — the additional ~690 are
smaller divergences that the same missing per-day check would also surface. The 1,963 above is the
conservative, unarguable count.

NMDC is the clearest mechanism. Its era `pre-2019-03-22` is **provable**, with `k_price = 0.235189`
and `k_volume = 0.333337` — two different factors — and `probe_days = ['2019-03-15','2019-03-18',
'2019-03-19','2019-03-20']`, four days at the top of an era spanning ~600. The vendor applied 1/3 to
the 2018 days; dividing them by 0.235189 leaves them at 1.4173× raw, while the volume, scaled by the
matching 0.333337, reconciles at +0.107%. Every gate passes.

All six symbols are **settled**, so these days sit inside the 413,914-day usable headline and would be
consumed by chunk 9. A POC built on TATASTEEL 2020-07-28 would be computed on a ₹36 price grid, the
stop-loss distance would be a tenth of reality, and `floor(risk / (entry − SL))` would size the
position ten times too large. The trade record would look entirely ordinary.

This is not a licensed residual. ADDENDUM 4's "residuals after this pass are disclosed, not chased"
licenses **disclosed** residuals; these days are disclosed nowhere and are counted as passes. Nor is
it a builder error — no ruling asked for a per-day price check, and the architecture that produced it
was reviewed and passed at chunk 5A. It is a hole in the ruled measurement architecture that only
appears at universe scale, which is precisely what chunk 5B exists to find.

**What it needs:** an architect ruling, because CONTEXT §4.5 defines the gate battery and adding to it
is Class A. The cheap closure is already implemented and already trusted: apply the *existing*
containment oracle **per stored day** against the raw daily high/low — the same test
`_day_price_contained` already performs, which costs nothing because both sides are local. That would
have flagged all 1,958 days. Whether such days are excluded, re-measured, or disclosed is the
architect's call, not a session's.

**Q2 — LOW — the acceptance oracle is described as "2-paise containment" throughout, but is
`max(2 paise, 0.1% × raw)`.** *Spec: none — accuracy of disclosure.* Every 5B document, PROGRESS entry
and report section says "the same 2-paise containment"; `vendor_adjustment.py:1581` computes
`max(Decimal(tol_paise), Decimal(raw) * _PRICE_CONTAINMENT_REL)` with `_PRICE_CONTAINMENT_REL = 0.001`.
On a ₹1,000 stock the effective tolerance is 100 paise. The constant is **inherited from chunk 5A**
(commit `9f06b6d`, decision B92) and was reviewed and passed there, so the code is out of this span —
but 5B's own prose restates it inaccurately, and the IOC cascade sentence ("0.3 paise past the band")
is only intelligible against the relative floor.

**Q3 — LOW — the report's only both-gates figure understates itself by ≥1,012 days.** *Spec: plan.md
chunk-5B card; reporting accuracy.* `universe_backfill.py:2270` computes `usable = gate1_effective −
gate2_excluded` and prints it as "gate 1 AND gate 2" (report line 25, "~412,723"), but the 1,012
missing-minute exclusions can only fire on days that already failed gate 1. The correct intersection
is 413,735 (95.2010%). The published number is the only reading under which the DoD appears to miss.

**Q4 — LOW — 178 stored symbol-days are gated by nothing.** *Spec: CONTEXT §7-E3.* Depth totals
434,769 against 434,591 gated: 178 days have no raw daily row, so gate 1 cannot run
(`volume_reconciled=None`) and they fall outside both numerator and denominator. Immaterial to the DoD
(95.2032% on the stored-day denominator) but they are neither passed nor counted as excluded.

**Q5 — LOW — two committed, chain-changing floors are claimed by no ledger row and appear in no
report table.** *Spec: decision B127's claim/evidence invariant; ADDENDUM 4 clause (iv).*
`run_floor_pass` **assigns** rather than accumulates (`universe_backfill.py:1954-1957`), so a floor
measured in an earlier pass and carried forward onto a rebuilt map is erased from the ledger's
counters. ASTRAL holds a resolved floor at 2021-03-08 on its 2023-03-14 bonus (12 probes) and
NESTLEIND one at 2021-12-31 on its 2024-01-05 split (12 probes), both **in force** in their committed
maps; both ledger rows read `floors_resolved = 0`, and report section 3c prints "no event carries a
vendor application floor" for each. The true totals are 12 floors over ~136 probes, not the headline's
10 over 108. `floor_ex_dates` is overwritten too, which discards the forced-override handle B138 exists
to preserve. No wrong price results — the map is the price authority and carries the floors, and both
symbols are quarantined — but the provenance the ruling requires is invisible outside a gitignored
JSON.

**Q6 — INFO — the report's un-provable-day count is VEDL's number alone.** *Spec: CONTEXT §7-E3;
card's "failures categorized".* `record.unprovable_days` is overwritten with the fetch pass's count
(`universe_backfill.py:1396`, and again at :1549), which is empty on a resumed store. The ledger
carries 300 for VEDL and **0 for every other symbol**, including 29 symbols that demonstrably hold
un-provable eras — HINDZINC has 10 of 11 eras un-provable and records 0 un-provable days. The report's
"Un-provable days (no map era / unknown factor) | 300" is therefore not the quantity it names. Days
inside an un-provable era are stored as fetched, so most are harmless where the vendor applied
nothing; the harmful subset is Q1.

### Code reviewer

**C1 — LOW — no test executes `run_floor_pass`'s acceptance orchestration.** 36 of 68 statements
(lines 1945-1949 and the contiguous acceptance block 1972-2024) and 12 of 29 in `_hunt_rounds` (B136's
round composition) are never executed by any of the 1253 tests — confirmed with an independent
`sys.settrace` line tracer over the whole suite. The only two tests calling `run_floor_pass` hit the
error branches. This is store-writing wiring with no regression protection.

**C2 — LOW — no test drives `gate_symbol` into the auction-relief branch.** Mutants that fold
relieved days into `gate1_pass`, or that revert B122's `volume_reconciled` handoff, both survive the
full suite. `auction_relief` itself is well tested in isolation; its wiring is not.

**C3 — LOW — the DoD verdict's NOT-MET branch, `shortfall` and `usable` are executed by no test.**
Every report the suite renders is a degenerate 100%-pass, zero-exclusion case, which is how Q3 shipped.

**C4 — LOW — `persist_map` is the only store write that bypasses `atomic_io`.**
`vendor_adjustment.py:1884` is a plain `write_text` (truncate-then-write, no temp, no fsync, no
rename), and `load_map` lets `json.JSONDecodeError` escape all four `VendorAdjustmentError` guards
written for it. A torn map — the artefact carrying the floor provenance — aborts the run with a raw
traceback instead of the designed rebuild. Loud rather than silent, but the FIX-4 disclosure's "both
write atomically" is true of the parquet and the ledger, not of the map.

**C5 — LOW — `build_map_for` is called without `floors=` on the steady-state rebuild paths**
(`universe_backfill.py:1325`, :1513), so a rebuild re-arbitrates a floor-promoted era from scratch
while `carry_floors_forward` re-attaches only the evidence, never re-deciding `era.provable`. CANBK's
committed map now marks un-provable an era whose stored days measure price-contained and in-band.
Costs coverage, not correctness.

**C6 — LOW — `acumen-build-adjustment-map` overwrites `data/adjustment_maps/<SYM>.json` without
`carry_floors_forward`**, so a manual operator re-run silently discards a measured floor. Untested and
unreachable from the refusal path that advertises it, but it is the runbook command printed to the
operator.

**C7 — LOW — ADDENDUM 2's recorded hunt scope omits the gate-3 arm the code carries.**
`floor_hunt_in_scope` admits `record.gate3_failed` in addition to quarantine and the 98% line. The
addition is correct and is explained in the code's docstring and in report section 3c; the execution
note in QUESTIONS.md is what is stale.

**C8 — LOW — ADDENDUM 4's "admitted only by one of the two signatures" omits `force_ex_dates`.**
The third admission route is correct and is recorded as B138; the addendum's prose is not qualified.

**C9 — LOW — report section 3d pairs an all-symbol numerator with a settled-only denominator.**
"435 symbol-day(s) relieved … out of 420,297 gated days on settled symbols" — the 435 includes the
three relieved days on quarantined symbols, and the three-day gap against the headline's 432 is never
explained. `_add_relief_section` sums over all records.

**C10 — INFO — four hunted ledger rows carry a blank `floor_discipline`** (CANBK, DIXON, LODHA,
RELIANCE): their hunts ran under FIX-3, before the constant existed, and FIX-4 correctly found them
out of scope. Harmless today — `floor_hunt_owed` gates on `floor_hunt_in_scope` first, and all four
are above 98% with no gate-3 failure — but the marker no longer records the discipline the recorded
measurement ran under.

**C11 — INFO — five in-span commits omit the `(unreviewed)` suffix** (`269c07e`, `c01d27d`,
`47d9768`, `90b9b39`, `0b37119`). REVIEW_5A recorded the identical class as its finding F4.

**C12 — INFO — `_stored_day_is_raw` is dead code with stale attribution.** It has no `src/` caller
after FIX-2 removed it from the map rebuild, yet B108 and two `src` comments
(`minute_backfill.py:660`, :875) attribute it to the Q-10 factor-table path, which never called it.

**C13 — INFO — the same-domain predicate is written twice**: once in the tested signature gate
(`universe_backfill.py:1036`) and again inline in the untested report classifier, so the two can drift.

**C14 — INFO — `gate3_signature_events`' docstring mislabels two worked half-steps** (ASTRAL k=0.8
shown as "step 10%" where the step is 20%; likewise COCHINSHIP). The code is right; the comment is not.

**C15 — INFO — report 3b's "Avg min/day" is stored-bars-per-day** while the median and minimum
columns are in-session traded minutes — a ~0.2 min/day cosmetic inconsistency.

**C16 — INFO — `_CLUSTER_RATE` (0.90) and `_SCATTER_RATE` (0.50), and the un-asked-for
`PATTERN_MIXED` bucket, are Class-B choices recorded in no `decisions:` entry.** Report-only, but
plan.md §5 is unconditional. Likewise `QUARANTINE_GATE1_MIN_PASS_RATE = 0.80`, whose code comment
attributes it to "the architect" with no ruling or card behind it.

---

## 16. What a fix session must do

1. **Q1 is not a fix a session may choose.** It needs the architect's ruling first, recorded verbatim
   in QUESTIONS.md as every ruling in this chain has been. The question to put is narrow: *CONTEXT
   §4.5's gate 1 proves a day's volume; the Q-11 oracle proves an era's price over its probe days.
   1,963 stored symbol-days fall between the two. Should a per-day PRICE containment check — the
   existing `max(2 paise, 0.1%)` oracle applied to each stored day against the raw daily high/low —
   join the gate battery, and are the days it flags excluded, re-measured, or disclosed?*
   Recorded as **Q-14** in QUESTIONS.md.
2. Then re-run the affected symbols from the already-stored candles (no re-download is needed; both
   sides of the check are local) and regenerate the report.
3. Fix Q3, Q5 and Q6 — three counting defects in the report, each with a named line number.
4. Record the B127 widening as a Class-B decision (§13).
5. Close C1, C2 and C3 with tests; C4 by routing `persist_map` through `atomic_io`.
6. C7, C8, C12, C14 are text corrections.

None of Q2, Q4 or the INFO findings blocks anything.

---

## 17. Scope of this review

No file under review was modified. No fixture was touched — `git diff 269c07e..708e144 -- tests/fixtures poc`
is empty and the working tree matches its committed blobs. CONTEXT.md, plan.md and `poc/` are
untouched. Every store access was read-only; every scratch artefact was written outside the repo. No
network call was made at any point. The two auditors that hit an API error mid-run (auction relief and
the CANBK bisection) cover checks the reviewer had already completed personally end-to-end, and both
are reported above from the reviewer's own evidence.

Reviewer probes were **not** added to the repo this session: the defect that decides the verdict is a
missing *gate*, not a missing test, and pinning it with a test before the architect has ruled on
whether the gate should exist would pre-empt a Class-A decision. The measurement script that produced
Q1's table is reproducible from the description in §15 in a dozen lines against the parquet stores.
