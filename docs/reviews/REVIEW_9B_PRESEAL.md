# REVIEW_9B_PRESEAL — the Q-18 RE-SEAL review · chunk 9B, PRE-RUN

**Type:** QC, BOTH personas (`personas/quant_reviewer.md`, `personas/code_reviewer.md`)
**Span:** `6b0436d..f4c019a` — 41 commits, five sessions (9B PREP incl. the Q-17 fix and the run
layer; Q-18 DATA RECOVERY; Q-18 VERIFICATION + TRIAGE; RESUME-1 law/migration/guard; RESUME-2
pin/pilot/projection), plus the two architect-authored spec commits.
**Session:** fresh; the reviewer built none of this and fixed none of it.
**Date:** 2026-08-02

---

## VERDICT: **PASS** — the full-history run is AUTHORIZED.

12 findings, **none blocking**: 1 MEDIUM, 5 LOW, 6 INFO (quant Q1–Q5, code C1–C7). Nothing in the
span deviates from CONTEXT.md; no test was weakened, deleted or made to skip; no fixture byte
moved; every engine module is byte-identical to its committed blob; no secret and no AI
attribution anywhere. Everything below was re-derived by the reviewer, importing nothing from
`src/acumen` wherever arithmetic was involved.

The one finding worth the architect's eye before he starts the run is **Q1**: the published
throughput does not reproduce. It changes no number in the ledger and does not fire the card's
36-hour STOP; it changes how long the operator should expect to sit there.

---

## 0. What the architect ruled before this review (Part 0)

Recorded VERBATIM in `QUESTIONS.md` under *ARCHITECT'S RULINGS (02-Aug-2026) · the Q-18 RE-SEAL
REVIEW's Part 0*. Four items that were open to this reviewer are closed by it and are therefore
**not findings here**: REVIEW_7's ICICIBANK "23 rows" stands as a document with a recorded
transcription slip; the 47 → 45 factor-scan change is ACCEPTED as a re-measured statistic of the
re-sealed era; the RESUME-2 card's chunk-6 oracle citation was in error and the repo's record
(2026-07-17; 1913.9/25 = the trader's reading) is right; Q-17's five market-wide dates ride to
the 9B report's disclosures with 2021-02-24 annotated as the probable NSE outage / extended
session, an identity candidate only.

The reviewer verified each ruling's factual premise independently before recording it — see
§3 (ICICIBANK), §5 (the two dates), §8 (the 47 → 45 refutation) — and every one holds.

---

## 1. The suite

**1927 passed / 0 failed / 0 skipped from clean** (`.pytest_cache` and every `__pycache__`
deleted first) — the build's own claim, reproduced first, with no skips and no xfails. With the
reviewer's kept probes: **2044 passed / 0 failed / 0 skipped** (`tests/test_review9b_preseal_probes.py`,
117 cases).

Across the whole span, measured by AST over both trees:

| | `6b0436d` | `f4c019a` |
|---|---|---|
| test files | 59 | 63 |
| test functions | 1,222 | **1,370** |
| `assert` statements | 3,179 | **3,523** |
| files that LOST a function or an assert | — | **none** |

Static `@pytest.mark.skip` / `xfail`: **zero**, at HEAD and across the span. The three runtime
`pytest.skip(` call sites are the store-gated probes, and on this machine none of them fires.

---

## 2. Directed check 1 — the 9B-PREP layer (never reviewed before)

### 2a. The run CLI and preflight

`python scripts/run_backtest.py --preflight-only --symbols RELIANCE,TCS` run by the reviewer:
**GO, 10 of 10**. Every check's detail re-verified against the machine — 319 daily parquet
files, 210 minute-store symbol directories, the register's 204 settled / 6 quarantined
(APLAPOLLO, ASTRAL, IEX, NTPC, UPL, VBL — exactly CONTEXT 4.6 v1.5's list), 41,372 CA rows
served offline, the pin resolved with its digest, span 2016-10-03 → 2026-07-30, 2,443 trading
days derived / 2,425 inside the span. The clamp is printed as a DISCLOSED CONDITION, the store
freshness stamps are printed and (verified structurally) never reach `notes`, therefore never
the manifest. **The preflight created no run directory** — `<data_root>/backtests/` is unchanged
by it.

### 2b. Resumability at kill points of the reviewer's choosing

Real runner, real stores (read-only), artefacts to a SCRATCH run dir. Symbols
`BHARTIARTL, HDFCBANK, TCS` (not the builder's five), span 2026-05-01..2026-05-29, 57 rows.

| kill point | shards on disk at the kill | resumed rows | duplicate keys | ledger sha256 |
|---|---|---|---|---|
| uninterrupted (baseline) | all 3 | 57 | 0 | `8893ec21…c38f986d` |
| after symbol 1 of 3 | 1 | 57 | 0 | **IDENTICAL** |
| after symbol 2 of 3 | 2 | 57 | 0 | **IDENTICAL** |
| DOUBLE interruption (1, then 2) | 2 | 57 | 0 | **IDENTICAL** |
| **mid-symbol** (crash after the walk, before the shard is durable) | 1 — the in-flight symbol left NO partial shard | 57 | 0 | **IDENTICAL** |

The mid-symbol case is the one the builder never ran: it proves the shard-on-completion
invariant rather than assuming it. All three refusal shapes fire:

| spec field moved | result |
|---|---|
| `code_sha` | **REFUSED** (`BacktestError`) |
| `master_file` → the other cached snapshot | **REFUSED** |
| `master_sha256` (same filename, different bytes) | **REFUSED** |

### 2c. The Q-17 candle-level drop — a 10-mutant matrix

Run inside a throwaway **COPY** of the repo made with `git archive` — never a junction
(CLAUDE.md data-store safety). Every mutated file restored and sha256-verified byte-identical.

| # | mutant | verdict |
|---|---|---|
| M1 | no drop at all (pre-Q-17 behaviour) | caught |
| **M2** | **DATE-LEVEL drop — the competing E2 reading** | **caught** |
| M3 | SILENT drop (the count swallowed) | caught |
| M4 | profile computed on the UNFILTERED day | **survived — proved EQUIVALENT** |
| M5 | 15-min bars aggregated UNFILTERED | caught |
| M6 | signals read the UNFILTERED minute bars | **survived — proved EQUIVALENT** |
| M7 | GATES see the FILTERED day | caught |
| M8 | the flag never reaches the ledger row | caught |
| M9 | the 15-min path reader stops dropping | caught |
| M10 | session window off by one at the close (15:30 admitted) | caught |

**The date-level mutant is caught**, which is what the directed check asked for.

M4 and M6 are EQUIVALENT, not gaps, and the proofs are structural:

* **M4** — CONTEXT 3.3's window is the stamps 09:15..11:14 and `day_profile` slices it itself;
  `is_session_time` admits exactly 09:15..15:29 for a 1-minute bar. An out-of-session stamp is
  therefore either below the window's open or above its close and can never fall inside it.
* **M6** — E10's fallback takes the LAST 1-minute close at or before 11:14. An out-of-session
  stamp at or before 11:14 must be earlier than 09:15, so it can be that maximum only on a day
  with no in-session bar before 11:15 — and such a day has an empty profile window, gets no POC,
  and never reaches the signal engine.

Both premises are now PINNED (finding C1, closed by kept probes), because the arguments hold
only while the window opens at 09:15 and the fallback has no lower bound.

### 2d. The 0.63% / 3,099-day measurement, re-derived from the store

Re-derived by the reviewer from the raw parquet stamps of all 204 settled symbols, importing
nothing from `src/acumen`: **3,100 symbol-days across 526 dates, 8 Muhurat-shaped, 518 mixed
covering 1,747 symbol-days**, and the five market-wide dates with both of their counts. Every
figure in `docs/evidence/chunk9b_out_of_session.md` reproduces exactly — see **§12** for the
full table and for one INFO refinement about which denominator the published 0.63% is taken over.

### 2e. Flagged-not-fatal, proved on the smoke's three days

From the committed smoke's own ledger:

| row | status | flags |
|---|---|---|
| RELIANCE 2017-04-28 | `evaluated` | out-of-session dropped, `no_entry` |
| MARUTI 2017-04-28 | `evaluated` | out-of-session dropped, `no_entry` |
| MARUTI 2019-10-25 | `evaluated` | out-of-session dropped |

RELIANCE 2017-04-28 is the exact bar that killed the pre-fix run. It is now walked, evaluated
and flagged. Three flagged rows, zero fatalities.

---

## 3. Directed check 5 — Q-20, the pinned instrument master

* **The pin is config, not code.** `config.yaml: instrument_master: OpenAPIScripMaster_2026-07-31.json`,
  required, no default. The reviewer attacked the validator with six malformed pins — a
  separator, an absolute path, a `..`, a null, an absent key, a backslash separator — and **all
  six are REFUSED**, each with a message naming Q-20.
* **sha256 in the manifest.** The reviewer hashed the file directly:
  `ce198be44b44fc333540a19c3d6a7b4e5fa86ae81ef2c6798fd5bece7b29f5ab`. It matches config.yaml's
  comment, the smoke manifest's `instrument_master.sha256`, the calibration pack and the
  preflight's printed digest — four places, one digest.
* **Both resume-refusal shapes re-proven** — see the table in §2b. The pin re-pointed at the
  other snapshot and the file overwritten in place both refuse, exactly as a moved code SHA does.
* **Latest-by-filename is absent from the run path** — the reviewer's OWN AST sweep, broader
  than the build's tripwire (it does not key on one literal): every string constant naming the
  vendor dump stem and every `sorted`/`max`/`min`/`glob`/`rglob`/`iterdir` call whose source text
  mentions a master, over `src/acumen`, `scripts/`, `docs/evidence/` and `docs/recovery/`.
  **13 sites, and inside `src/acumen` the glob appears at exactly one:
  `instrument_master.cached_masters`.** No run-path module sees it.
* **The 39-figure calibration table, recomputed INDEPENDENTLY.** The reviewer reimplemented
  CONTEXT 3.3 from the spec text (window, `totalTicks` half-even, the `tpr` tie → finer, rows
  stacked from `bottom` with the remainder last, the topmost row containing `top`, prorata
  spreading, tie → higher row) and read the ticks RAW out of the pinned master JSON — no
  `acumen` import anywhere in the arithmetic:

| group | result |
|---|---|
| F7's 25 frozen `poc_prorata` values | **25 / 25 reproduce exactly** |
| HDFCBANK 2026-06-10 | POC 739.80, totalTicks 182, tpr 8, **23 rows** — all four match |
| ICICIBANK 2026-05-21 | POC 1245.70, totalTicks 82, tpr 4, **21 rows** — `ceil(82/4) = 21`; REVIEW_7's printed 23 is the slip the architect has now ruled on |
| RELIANCE 2026-05-05 | POC 1465.85, totalTicks 224, tpr 9, **25 rows** — all four match |
| chunk-6 gate day BHARTIARTL **2026-07-17** | **POC 1914.60 in 26 rows** — matches |
| BHARTIARTL 2026-07-24 (the card's date) | POC 1880.75 in 25 rows — Rs 33 from the card's 1913.9, so that price is not this day's POC under any tick |

---

## 4. Directed check 2 — the Q-19 guard

`tests/test_q19_seal_guard.py`: **23 passed / 0 failed**.

Reviewer's own attacks, kept as probes:

* **The boundary as a PARTITION, not as cases.** Swept every age from 365 days in the future to
  365 days in the past (plus −1, 0, 6, 7, 8, 9): a 404 is EITHER pending OR sealed, never both
  and never neither, and the switch sits at exactly one place. **Day 7 exact stays PENDING**
  (CONTEXT 4.6 v1.5 says *more than* 7); day 8 seals.
* **The same boundary across a leap day and a year end** (run dates 2028-03-03 and 2027-01-05) —
  calendar arithmetic, not weekday arithmetic (B228), proved where a hand-rolled day count is
  most likely to be one out.
* **An ERROR still never seals.** The build already sweeps six ages; the outcome is `error` at
  every one, `is_terminal` is False, and it is neither `confirmed-404` nor `pending`. The two
  non-terminal outcomes are distinct constants and stay distinct.
* **The 2026-07-31 phantom shape is irreproducible.** Replaying the exact measured run
  (2026-07-01..07-31 asked on 07-31) gives 22 file-present, 6 confirmed-404, **3 pending**
  (07-25, 07-26 and **07-31 itself**), 0 error; the derived calendar then REFUSES to build,
  naming `2026-07-31=pending` and Q-19, rather than silently gaining a holiday. Re-run a week
  later and the date comes back as the trading day it always was.

---

## 5. Directed check 3 — the recovery, spot-re-derived

Everything here reads the raw parquet of both stores directly and imports nothing from
`src/acumen` for the arithmetic.

### 5a. T1, re-run by the reviewer on TEN symbols of the reviewer's choosing

Sealed day counts parsed straight out of the committed `docs/backfill_minute_report.md`; rebuilt
dates counted from the minute lake's own parquet.

| symbol | sealed | rebuilt | Δ | B = the sealed-count-th stored date | B inside 2026-07-20..28? |
|---|---|---|---|---|---|
| ASIANPAINT | 2,430 | 2,435 | +5 | 2026-07-24 | YES |
| BHARTIARTL | 2,429 | 2,434 | +5 | 2026-07-24 | YES |
| CIPLA | 2,430 | 2,434 | +4 | 2026-07-27 | YES |
| DRREDDY | 2,431 | 2,435 | +4 | 2026-07-27 | YES |
| HDFCBANK | 2,430 | 2,434 | +4 | 2026-07-27 | YES |
| ITC | 2,429 | 2,433 | +4 | 2026-07-27 | YES |
| MARUTI | 2,430 | 2,434 | +4 | 2026-07-27 | YES |
| SBIN | 2,430 | 2,434 | +4 | 2026-07-27 | YES |
| TITAN | 2,430 | 2,434 | +4 | 2026-07-27 | YES |
| WIPRO | 2,430 | 2,434 | +4 | 2026-07-27 | YES |

**10 of 10 pass**, every extra day inside `(B, 2026-07-31]`, and the 8-at-07-27 / 2-at-07-24
split is consistent with the record's 168 / 37 / 5 histogram.

### 5b. T3, hand-recomputed digit by digit on TWO symbols of the reviewer's choosing

**APLAPOLLO** — every field, not just the high:

| day | raw open/high/low/close (paise) | 1-min fold | ratio | volume ratio | price×volume |
|---|---|---|---|---|---|
| 2016-10-03 | 85,010 / 87,400 / 85,010 / 86,255 | 850,100 / 874,000 / 850,100 / 862,550 | **10.000000 on all four** | 0.098426 | 0.984259 |
| 2017-10-31 | 187,450 / 187,480 / 182,795 / 186,425 | 1,874,500 / 1,874,800 / 1,827,950 / 1,864,250 | **10.000000 on all four** | 0.098516 | 0.985157 |
| 2018-11-30 | 128,525 / 131,500 / 127,200 / 129,140 | 257,050 / 263,000 / 254,400 / 258,280 | **2.000000 on all four** | 0.499533 | 0.999067 |
| 2019-06-03 *(reviewer's control, OUTSIDE the named block)* | 162,090 / 162,100 / 156,530 / 157,460 | identical | **1.000000** | 0.999974 | 0.999974 |

The block is genuinely contiguous and era-keyed: the day after it is clean on both gates. Every
raw row is internally sound. Gate 1 fails at −90.16% / −90.15% / −50.05% and gate 1P fails
`fold-high-above-daily-high` on all three — re-run through the repo's own gate functions.

**POWERGRID** — the 4/3 block 2021-07-29..2021-09-06:

| day | price ratio (high) | volume ratio | price×volume | gates |
|---|---|---|---|---|
| 2021-07-29 | 1.333333 (**exactly 4/3**) | 0.749877 | 0.999836 | gate 1 FAIL −25.01%, gate 1P FAIL |
| 2021-08-16 | 1.333424 | 0.749934 | 0.999979 | gate 1 FAIL −25.01%, gate 1P FAIL |
| 2021-09-06 | 1.333428 | 0.749793 | 0.999794 | gate 1 FAIL −25.02%, gate 1P FAIL |
| 2021-09-07 *(control, the day AFTER)* | 1.000000 | 0.999084 | 0.999084 | both PASS |

Verdict CONFIRMED. See finding **Q3** on the word "exact".

### 5c. T5, BSE's 3.0×-price / 1.0×-volume split, on TWO of the five flipped days

| day | price ratio | volume ratio | gate 1 | gate 1P |
|---|---|---|---|---|
| 2017-08-24 (the first) | high **3.000000**, low **3.000000** | 0.998176 | **PASS** (gap 0.1824%) | **FAIL** `fold-high-above-daily-high` |
| 2017-11-28 (the last) | high 2.999968, low 2.999968 | 0.998486 | **PASS** (gap 0.1514%) | **FAIL** `fold-high-above-daily-high` |

Prices and volume sit in DIFFERENT domains — price×volume ≈ 2.995, not 1.0 — which is exactly
why gate 1 can pass while gate 1P refuses. **The T5 verdict stands: reading BSE's +84 gate-1
improvement as recovered coverage would be wrong**, and the register's usable count moved by 2,
not 84.

### 5d. The reconciliation regenerates byte-identically, and ZERO-unexplained holds

`python docs/recovery/q18_reconcile.py` re-run by the reviewer from a throwaway **COPY** of the
repo at HEAD (never a junction), output to scratch:

```
committed   sha256 0f99291ba70432be0ae36ebbac098ecdbb0ed02311410d81895a5fa20c3b3995
regenerated sha256 0f99291ba70432be0ae36ebbac098ecdbb0ed02311410d81895a5fa20c3b3995
BYTE-IDENTICAL: True   (313,138 bytes both)
```

Its verdict under the reviewer's own re-run: `sealed-fetch-horizon` 414 ·
`vendor-snapshot-drift` 5 · `vendor-repair-explained` 3 · `new-CA-explained` 0 ·
**`unexplained` 0**.

---

## 6. Directed check 4 — CONTEXT v1.5, CLAUDE.md, the migration

**Byte-exactness against the architect's supplied texts could NOT be checked** — the brief makes
that an operator paste on request and no paste was supplied to this session. Stated as a limit,
not assumed away. What WAS checked, structurally:

* `b895739` touches **CONTEXT.md and nothing else**, and its diff is **exactly three edits**:
  the header (`Version 1.4 · 29 July` → `Version 1.5 · 2 August 2026`), §4.6 replaced in full,
  and one new top row in §10's version log. No other section of CONTEXT.md is touched anywhere
  in the span — `git log 6b0436d..f4c019a -- CONTEXT.md` returns that one commit.
* `b3d6760` touches **CLAUDE.md and nothing else**, `+9 lines / −0`, and those nine lines are
  exactly the three Q-18 layers. Committed alone.
* **The three layers are present and behave**: layer 1 is enforced by the loader (below);
  layer 2 is written and was honoured by RESUME-2's disclosed store writes (see C5); layer 3's
  freshness stamps are printed by the preflight (verified in the reviewer's own run) and never
  enter `notes`, therefore never the manifest.

**The loader attacked with eleven malformed configs.** All refusals hold, including two the
build's own tests do not cover:

| case | result |
|---|---|
| in-repo absolute `data_root` | REFUSED — "points INSIDE the repository tree" |
| in-repo absolute `cache_root` | REFUSED |
| relative `data` | REFUSED — "must be an ABSOLUTE path" |
| relative `../acumen-data` | REFUSED |
| `data_root` key missing | REFUSED |
| `cache_root` key missing | REFUSED |
| both missing | REFUSED |
| **`<repo>/../acumen/data` — a `..` round trip back inside** | **REFUSED** (reviewer's case) |
| **the repo root ITSELF** | **REFUSED** (reviewer's case) |
| empty `paths` mapping | REFUSED |
| absolute but NON-EXISTENT directory | LOADS — correct (a bare clone has no stores; the preflight is what catches it). See C4 on the wording. |

**Zero literal store paths survive in `src/` or `scripts/`** — grepped for `"data/`, `"cache/`,
`acumen-data`, drive-letter literals and `Path("data")`: no hits. **No SIXTH caller of the dead
key exists**: `config.path("data_dir")` / `config.path("cache_dir")` appear nowhere in `src/`,
`scripts/`, `docs/` or `tests/`; the five repaired generators (B242) were the whole population.

---

## 7. Directed check 6 — pilot byte-identity

**The reviewer hashed the run ledger directly:**

```
c3363f6f17757ebcbb2f08e8159e943cbbd692836d165687cbb2d91e22c1e318   chunk9a_pilot_a/ledger.jsonl
c3363f6f17757ebcbb2f08e8159e943cbbd692836d165687cbb2d91e22c1e318   chunk9a_resume_whole/ledger.jsonl
c3363f6f17757ebcbb2f08e8159e943cbbd692836d165687cbb2d91e22c1e318   chunk9a_resume_killed/ledger.jsonl
```

That **is** the digest `docs/evidence/chunk9a_pilot.md` and REVIEW_9A published before the
incident, and it is the digest REVIEW_9A verified at four kill points. The rebuilt stores
reproduce the destroyed era's pilot **byte for byte**, on three independent run directories.

Every headline figure re-derived from those 290 rows by the reviewer, importing nothing from
`src/acumen`: 290 walked / 146 entered / 88 armed-no-cross / 56 never-armed; 53,750 shares;
gross Rs 12,665.05; costs Rs 14,600.00; **net −Rs 1,934.95**; exits 86 stop / 36 square-off /
24 target; winners 45 / losers 101; net-basis pots Rs 96,489.60 / −Rs 98,424.55 summing exactly
to the net PnL; **PF 0.9803**; Tukey Q1 −Rs 1,099.00, Q3 Rs 997.20, IQR Rs 2,096.20, fences
[−Rs 4,243.30, Rs 4,141.50], **0 outliers of 146**. Every one matches the committed pack and
REVIEW_9A_2.

**The five moved pins are all discriminating.** Run against the PRE-REGENERATION artefact (the
pack as committed at `8e67081`) inside a repo COPY:

```
FAILED  test_every_before_costs_figure_in_the_pack_is_labelled_as_one          (flip 1)
FAILED  test_the_two_run_up_rows_describe_the_same_quantity_the_same_way        (flip 2)
FAILED  ...carries_its_claims[IOC (42.0% price-proven) and TATASTEEL (65.8%...] (re-point 1)
FAILED  ...carries_its_claims[...the only before-costs figures in section 7]    (re-point 2)
FAILED  ...carries_its_claims[**0** of 146 executed trades, summed net Rs 0.00] (re-point 3)
5 failed, 13 passed
```

Exactly the five, and the other thirteen pack-claim pins still pass — so the moves are
targeted, not a blanket re-point. None is decoration.

**The pack itself was NOT regenerated by this review**, deliberately: `pilot_evidence` writes its
run artefacts under `<data_root>/backtests/`, and CLAUDE.md's Q-18 layer 2 makes the stores
read-only to a session whose prompt sanctions no named write. Stated as a limit of this
verification (C6). The pack's own diff was read line by line instead: it is presentation
corrections, the two pin rows, the architect-accepted 47 → 45, and two manifest digests that
move BECAUSE the pin and the spec version are inside the digest. **No money figure moved.**

---

## 8. Directed check 7 — the projection

**The three-term arithmetic re-derived, and it is right:**

```
walk    495,312 / 25.558  = 19,380 s = 5h 23m 00s      (204 x 2,428 rows)
wiring   11.539 s/sym x 204 = 2,354 s = 0h 39m 14s     (CONTEXT 7-E2 session scan)
wiring    0.520 s/sym x 204 =   106 s = 0h 01m 46s     (corporate-action factor tables)
TOTAL                       = 21,840 s = 6h 04m 00s
```

Every term checks: the smoke's 4,856 rows in 190 s is 25.558/s; 204 × 2,428 = 495,312; each
conversion to h/m is exact. **The 2,428 rows per symbol is also correct** and the reviewer
reconciled it: the span holds 2,425 trading days, and `walk_symbol` additionally emits a REFUSED
row for a non-standard-session date even when the calendar says it is not a trading day — the
three weekend Muhurat sessions 2019-10-27, 2020-11-14 and 2023-11-12. 2,425 + 3 = 2,428, exactly.
See Q2.

**The rate does NOT reproduce — see finding Q1.** The reviewer re-ran the identical smoke
(RELIANCE + MARUTI, same span, same HEAD, same stores, same machine, same day, nothing else
running) and measured **13.59 symbol-days/s**, against the published 25.56.

**Runbook step 6 verified**: the command (`python scripts/run_backtest.py`, no flags), the
four-item pre-run checklist (reboot / free memory / snapshot newer than both stores / do not
commit or re-point the pin), resumability, the completion check, and **both manifest stamps** —
Q43 capital-flags-pending and Q44-unconfirmed with its escalation. All three disclosure sentences
were verified present in the committed smoke log's own `DISCLOSURE:` lines, plus the measured
span-clamp note.

**The 47 → 45 refutation checked** (the architect has ACCEPTED the change; this is the premise
behind his acceptance): `pilot_evidence.scan_share_count_events` and `_bias_both_ways` take no
`master` and no `row_size` parameter and their source mentions no tick, no `SignalPipeline` and
no `day_profile` — asserted by a test in the span and independently re-checked here. CONTEXT 3.2
builds no profile, so the scan is structurally tick-blind and the pin cannot be its cause.

---

## 9. Findings

### QUANT

**Q1 · MEDIUM · the MEASURED throughput does not reproduce; the 6h 04m projection is optimistic
by ~1.9× on this machine.**
`docs/evidence/chunk9b_throughput.md` publishes **25.56 symbol-days/s**, measured on
RELIANCE + MARUTI over the full era at 15:2x IST on 2026-08-02 (RELIANCE 95 s, MARUTI 94 s). The
reviewer re-ran exactly that — same two symbols, same span 2016-10-03..2026-07-30, same HEAD,
same stores, same machine, later the same day, with nothing else running:

| symbol | published | reviewer |
|---|---|---|
| RELIANCE | 95 s | **171.0 s** |
| MARUTI | 94 s | **186.4 s** |
| combined rate | **25.56 sd/s** | **13.59 sd/s** |

A four-symbol pass (RELIANCE, MARUTI, SBIN, INFY) gave 15.47 sd/s on the same basis. Substituting
13.59 into the published arithmetic: walk 495,312 / 13.59 = 36,447 s = **10h 07m**, so the total
lands near **10h 50m** rather than 6h 04m.

*Not blocking, and not a wrong number:* the projection's own §4 discloses precisely this risk —
"the machine is memory-starved… paging does not show up in a 3-minute measurement" and "the only
thing that MEASURES a full run is a full run". The card's STOP threshold is 36 hours and even
the slower figure is far under it; resume is free, so an overrun costs nothing but the operator's
evening. What the finding buys is the operator's expectation: **the 6h 04m headline should be
read as a floor, not as a duration**, and the run should be started when there is a working day
to spare rather than an evening. The reviewer cannot say which measurement is the machine's true
steady state — only that the published one did not reproduce forty minutes later on an idle box.

**Q2 · LOW · `walked` counts three days per symbol that are not trading days, and step 6 prints
2,425 and 2,428 side by side without saying why.**
`walk_symbol` writes a REFUSED row for every date in `non_standard_sessions` BEFORE it asks
whether the calendar calls that date a trading day, so the three weekend Muhurat sessions
(2019-10-27, 2020-11-14, 2023-11-12) each add a row to every symbol. Verified from the smoke's
own ledger: `walked NOT in the calendar span` = exactly those three, `calendar span NOT walked` =
empty. The behaviour is honest (the exclusion is counted rather than silent) and it is
pre-existing chunk-9A behaviour, reviewed-PASS. The projection's 204 × 2,428 basis is therefore
RIGHT. What is missing is one clause: runbook step 6's "What to expect" table prints
*"2,425 trading days"* immediately above *"~495,312 = 204 × 2,428 rows"*, and a reader who
multiplies gets a different number. One sentence fixes it.

**Q3 · LOW · T3's "an EXACT corporate-action factor" is exact only up to paisa rounding on two of
the three POWERGRID days.**
`q18_t3_forensics.json` says each regression's fold "sits at an EXACT corporate-action factor
from the raw bhavcopy". Independently recomputed: POWERGRID 2021-07-29 is exactly 4/3 on the
high, but 2021-08-16 is 1.333424 and 2021-09-06 is 1.333428 — the fold's extremes are the max/min
of per-minute prices already rounded to the paisa, so equality with 4/3 cannot be expected and is
not what the evidence rests on. What the verdict actually rests on — the reciprocal price×volume
signature — holds tightly (0.999794 … 0.999979 across the three days, 0.984 … 0.999 on APLAPOLLO's
larger factors). **The verdict is unaffected**; the word "EXACT" overstates what two of six
hand-verified days show, and a later reader re-deriving them will trip on it exactly as this
reviewer did.

**Q4 · INFO · the coverage headline's numerator is settled-only against an all-210 denominator.**
CONTEXT 4.6 v1.5 reads *"435,641 stored symbol-days; 409,252 pass all three gates = 93.9425%"*.
Recomputed from the register: 409,252 is `usable_pass` summed over the **204 settled** symbols,
while 435,641 is `gate1p_total` summed over **all 210**. The number of stored symbol-days that
actually pass all three gates is **418,864** (96.1489%); the 9,612-day difference is days on
quarantined symbols that pass the battery but whose symbol is excluded. This is the conservative
and defensible reading, it is the SAME reading the sealed era used (so the reconciliation and
every delta in v1.5 are unaffected), and it is generated by `universe_backfill` code that chunk
5B reviewed and passed twice. Recorded only because the sentence read literally is 9,612 days
short of true, and a reader recomputing from the register will get 96.15% and think something
moved. One clarifying clause if §4.6 is ever touched again.

**Q5 · INFO · Q-17's "0.63%" is taken over the projected WALK size, not over a stored-day
population.** The narrative reads *"3,099 of ~493,900 stored symbol-days (0.63%)"*; ~493,900 is
204 symbols × ~2,421 trading days, i.e. how many symbol-days the run would WALK, whereas the
stored populations are 421,316 (settled) and 435,641 (all 210). The same 3,100 days are 0.74%
and 0.71% of those. The committed evidence file prints counts and no percentage, so nothing
published is wrong; the share simply answers a different question than the sentence implies.
Every reading is small and none changes the ruling.

### CODE

**C1 · LOW · CLOSED by kept probes · the Q-17 drop's two equivalence premises were unpinned.**
Mutants M4 and M6 survive the whole suite. Both are EQUIVALENT (§2c), but the equivalence rests
on two facts no test asserted: the profile window opening at 09:15 (so a stray can never enter
it) and E10's fallback having no lower bound but being unreachable while a profile exists. Either
could move without a red test, and the mutants would then be live defects on the exact days Q-17
is about. **Closed here**: `tests/test_review9b_preseal_probes.py` pins both premises, plus a
whole-pipeline probe that a day carrying BOTH stray shapes produces the clean day's POC, bars,
entry and exit while the gates still see the unfiltered day. The probes are discriminating —
they catch the date-level mutant, the silent-count mutant, the gates-see-filtered mutant and a
window-boundary mutant on their own.

**C2 · LOW · one commit touching `tests/` lacks its `(unreviewed)` suffix.**
CLAUDE.md: *"Every commit touching src/ or tests/ before its chunk's review carries the
(unreviewed) suffix — no exceptions (REVIEW_7 C1)."* Twenty of the span's twenty-one such commits
comply. `f4c019a` — *"chunk9B: RESUME-2 evidence, ledger entry and chunk state"* — changes
`tests/test_pilot_evidence.py` (the three re-pointed pack pins) and does not carry it. Same class
as REVIEW_7's own C1 finding, and the same severity: nothing is wrong with the change, only with
its label. History is not rewritten for it.

**C3 · LOW · six Class-B decision IDs are used TWICE inside this arc.**
`B214`–`B219` are assigned by the Q-18 DATA RECOVERY session (2026-07-31 10:55) and again, for
six entirely different decisions, by the Q-18 VERIFICATION + TRIAGE session (2026-08-02 02:15).
Six decisions in the span cannot be cited unambiguously — "B215" is both *"the instrument master
becomes its own operator step"* and *"T1's gate leg is a two-sided interval bound"*. plan.md §5
makes the decisions register the ONE place a Class-B choice lives; a duplicated name is close to
an unrecorded one for anybody who later has to look one up. (`B1`–`B12` are also duplicated,
chunk 0 vs chunk 1 — pre-existing, outside this span, noted only so the pattern is visible.)
No renumbering is proposed here: PROGRESS.md is append-only and the fix is the architect's call.

**C4 · INFO · "the loader refuses a MISSING store root" means a missing KEY, not a missing
directory.** `src/acumen/config.py`'s module docstring and decision B223 both say the loader
"REFUSES a store root that is missing, relative, or inside the repository tree". Verified: a
missing KEY is refused; a relative root is refused; an in-repo root is refused. An absolute root
naming a directory that does not exist **loads** — which is correct (a bare clone has no stores
and the preflight is what catches it), but is not what the sentence says to a fresh reader.

**C5 · INFO · layer 2's "explicitly sanctions a NAMED write" was satisfied implicitly.**
RESUME-2 wrote the pilot re-runs and the smoke under `<data_root>/backtests/`, which is a store
write. Its card asked for exactly that work and the write is disclosed in the PROGRESS entry and
in the operator-snapshot reminder, so the intent is plainly met — but the layer's own wording
asks for a NAMED sanction and none appears in the record. Worth naming the write in the card next
time, because the value of layer 2 is that the sanction is findable afterwards.

**C6 · INFO · a stated limit of this review: the pilot pack was not regenerated in place.**
For the reason in §7 (layer 2). The pack's byte-reproducibility is therefore attested here only
indirectly — by the ledger's sha256 matching the pre-incident published digest on three run
directories, by every headline figure re-deriving from those bytes, and by the five moved pins
failing against the pre-regeneration artefact. A future session with a named write sanction
should close it directly.

**C7 · INFO · byte-exactness of CONTEXT v1.5 and CLAUDE.md against the architect's own texts was
not checkable.** The brief makes those an operator paste on request; none reached this session.
Verified structurally instead (§6): both commits touch one file each, are committed alone, and
make exactly the edits their logs claim.

---

## 10. Class-B decisions B202–B243, judged

| id | verdict | one line |
|---|---|---|
| B202 | APPROVED | Not rewording a constant recorded verbatim in QUESTIONS.md, printed in a committed pack and pinned by tests is the conservative call. |
| B203 | APPROVED | `disclosures` stamped only when non-empty keeps every chunk-9A manifest digest where it was. |
| B204 | APPROVED | The E2 scan cache is keyed on universe + span + code SHA and a mismatch is ignored; my four kill-point resumes were byte-identical with it in play. |
| B205 | APPROVED | The oracle clamp is measured, printed as a DISCLOSED CONDITION and stamped on the manifest — verified in my own preflight run. |
| B206 | APPROVED | The FLAG-not-column choice is exactly what kept the pilot ledger's sha256 at `c3363f6f…`, which is now the arc's strongest continuity evidence. |
| B207 | APPROVED | The launcher path works from a bare clone; I ran it. |
| B208 | APPROVED | An empty check list must never read GO. |
| B209 | APPROVED | Parsing the sealed side from the committed report is what makes the byte-identical regeneration meaningful. |
| B210 | APPROVED | Printing the tests inside the report and defaulting to `unexplained` is what makes "zero unexplained" a claim rather than a hope. |
| B211 | APPROVED | A corporate action re-scales a history; it cannot add or remove stored days. |
| B212 | APPROVED | Requiring a sealed-era-NAMED deficiency is the right bar; the alternative would have admitted nearly every symbol. |
| B213 | APPROVED (weakest leg, and it says so) | Blocking only on a contradiction is honest about what a destroyed store cannot certify. |
| B214 *(recovery)* | APPROVED | Post-scope-end days as growth, never drift. |
| B215 *(recovery)* | APPROVED | The instrument master as its own operator step — vindicated three days later by Q-20. |
| B216 *(recovery)* | APPROVED | `scripts/ca_report.py` restores the bare-clone launcher parity chunk 3 lacked. |
| B217 *(recovery)* | APPROVED | Narrowing step 1 to the last COMPLETED trading day is the deviation that surfaced Q-19; stated, not assumed. |
| B218 *(recovery)* | APPROVED | A new "Data-store safety" heading rather than diluting the git rules. |
| B219 *(recovery)* | APPROVED | The phantom row un-recorded with the EXISTING documented recovery; no chunk-2 semantic touched. |
| B214 *(triage)* | APPROVED | B as the sealed-count-th STORED date — reproduced on 10 symbols of my own choosing, 10/10. **ID collides, see C3.** |
| B215 *(triage)* | APPROVED | The two-sided interval bound is the right correction, and the report states what it does and does not prove. **ID collides.** |
| B216 *(triage)* | APPROVED | Drift READ from a committed forensics file and ESCALATE keeping `unexplained` is what stops the class fitting the data. **ID collides.** |
| B217 *(triage)* | APPROVED | Measured classes before the merely-plausible one; T2's own ruling points the same way. **ID collides.** |
| B218 *(triage)* | APPROVED | Naming the status divergence beside the gate divergence avoids a dangling consequence. **ID collides.** |
| B219 *(triage)* | APPROVED | Running the reconciler as committed from a throwaway COPY of `src/` — I used the same technique for my mutation matrix and my pre-fix pin runs. **ID collides.** |
| B220 | APPROVED | Header date moved with the version; architect confirmed 02-Aug-2026. |
| B221 | APPROVED | A markdown table row cannot span lines; not one word changed. Architect confirmed. |
| B222 | APPROVED | REPLACE, not add: verified that zero callers of the retired keys survive anywhere in the repo. |
| B223 | APPROVED | Structural refusal, attacked with eleven configs including a `..` round trip and the repo root itself; all held. See C4 on one word. |
| B224 | APPROVED | `Path \| None` on the branch where the roots are genuinely unknown; nothing invents `data/`. |
| B225 | APPROVED | Freshness stamps rendered but never in `notes` — verified: only `notes` reaches `disclosures`, hence the manifest. |
| B226 | APPROVED | A `pending` ROW records that we asked; that is strictly more than absence, and the retry needed no change. |
| B227 | APPROVED | A cited spec constant, matching how this repo already carries `UDIFF_FIRST_DATE`. |
| B228 | APPROVED | Calendar days with no weekend exception — the reasoning is exactly right; I pinned it across a leap day and a year end. |
| B229 | APPROVED | A ledger must name the law it ran under; verified `v1.5` on the smoke manifest. |
| B230 | APPROVED | The sweep MEASURES the rewritten cache and says plainly what it cannot localise. |
| B231 | APPROVED | Terminality, not membership — the real bug a second non-terminal outcome would have created. |
| B232 | APPROVED | Independently recomputed: IOC 1,024/2,436 = 42.036% → 42.0%. The frozen 41.9% was wrong, not stale. Architect confirmed. |
| B233 | APPROVED | A self-audit correctly scoped as diligence: no REVIEW file, no PASS claimed, the QC review still fresh. |
| B234 | APPROVED | Required config key, no default; six malformed pins attacked, six refused. |
| B235 | APPROVED | DELETED, not deprecated. My own broader AST sweep finds the glob at one site in `src/acumen` and none on the run path. |
| B236 | APPROVED | One tick source beats two that agree until the day they do not. |
| B237 | APPROVED | Filename AND digest inside the spec digest; both refusal shapes fire, proved on my own runs. |
| B238 | APPROVED | An explicit path is a confirmation, never an override — and the name-only comparison is safe only because the argument is discarded, which I have now pinned. |
| B239 | APPROVED | `caveat_basis` makes the invariant checkable from the manifest alone; verified on the smoke manifest and round-tripped in a kept probe. |
| B240 | APPROVED | Recomputing under the OTHER snapshot is the right discriminator, and the architect has now ruled the one PUBLISHED-SLIP. |
| B241 | APPROVED as METHOD | Three terms and evenly-spread samples are right; the walk term's own reproducibility is finding Q1. |
| B242 | APPROVED | One word each, no output regenerated. Verified: no sixth caller exists. |
| B243 | APPROVED | Both dates computed, neither preferred — and the architect has now confirmed the repo's record was the right one. |

---

## 11. Standard sweep

| check | result |
|---|---|
| full suite from clean | **1927 / 0 / 0**, no skips, no xfails |
| with the reviewer's kept probes | **2044 / 0 / 0** |
| fixtures frozen | `git diff 6b0436d..f4c019a -- tests/fixtures poc` is EMPTY; working tree clean; 66 tracked fixture files |
| no test weakened | no file lost a function or an assert; 1,222 → 1,370 functions, 3,179 → 3,523 asserts; every removed assertion traced to a ruling (v1.5 spec version; B232's computed caveat, architect-approved; the store migration, which made the retired assertion assert the opposite of the new law; the architect's C3 offline-cache ruling; the flips) and replaced by a test asserting the NEW rule |
| commit hygiene | 41 commits, all single-parent, no merges, `chunk9B:` / `spec:` / `docs:` / `housekeeping:` prefixes, what+why bodies |
| `(unreviewed)` discipline | 20 of 21 src/tests commits comply — see **C2** |
| AI attribution | **none**; every `CLAUDE.md` hit is a permitted file citation |
| secrets | none; the runbook names the four `.env` VARIABLE names and states outright that no value was read or printed |
| engine modules | `bias`, `poc`, `signals`, `simulate`, `portfolio`, `bias_engine`, `quality_gates` byte-identical to `6b0436d`; `aggregate` and `signal_engine` changed ONLY by the Q-17 fix and byte-identical since `8e67081` |
| SHA chain | linear across all five sessions; local `main` == `origin/main` at `f4c019a` |
| store safety | this review made **zero** store writes: every probe wrote to a scratch run dir, every mutation ran in a `git archive` COPY, and no junction was created at any point |

---

## 12. The Q-17 measurement, re-derived from the store

Full-lake scan by the reviewer over all 204 settled symbols (the settled list read from the
register's own `ledger.json`), counting straight from the raw parquet `stamp` column and
importing nothing from `src/acumen`. It reproduces the committed measurement **exactly**:

| quantity | `chunk9b_out_of_session.md` | reviewer |
|---|---|---|
| settled symbols scanned | 204 | **204** |
| symbol-days with ≥1 stamp outside 09:15..15:29 | 3,100 | **3,100** |
| distinct dates touched | 526 | **526** |
| Muhurat-shaped dates (no symbol has an in-session bar) | 8 | **8 — the identical list** |
| mixed dates | 518 | **518** |
| symbol-days those mixed dates cover | 1,747 | **1,747** |
| market-wide mixed dates (≥20 symbols) | 2017-04-28 134/139 · 2018-11-05 135/153 · 2019-10-25 56/159 · **2020-12-08 143/167** · **2021-02-24 168/169** | **identical, all five, both columns** |
| top concentrations | RECLTD 508 · TATASTEEL 507 · PIDILITIND 124 | **identical** |
| top clock stamps | 18:29 1,343 · 18:21 1,337 · 18:49 1,221 | **identical** |

So the Q-17 addendum's five market-wide candidates — including **2021-02-24 at 168 of the 169
symbols that have data that day** — are the reviewer's own measurement as well, which is the
premise the architect's Part 0 ruling rests on.

**One refinement, INFO only.** Q-17's narrative quotes the share as *"3,099 of ~493,900
symbol-days (0.63%)"*. That denominator is the projected WALK size (universe × trading days),
not a stored-day population. Against the store the same 3,100 days are **0.74%** of the 421,316
stored days on settled symbols, or **0.71%** of all 435,641. The committed evidence file itself
prints counts and no percentage, so nothing published is wrong; the 0.63% simply answers a
different question than a reader would assume. Every reading is small and none changes the
ruling.

---

## 13. What this review authorizes, and what it does not

**AUTHORIZED:** the chunk-9B full-history run, exactly as staged in `docs/recovery/q18_runbook.md`
step 6 — `python scripts/run_backtest.py`, no flags, under the pin
`OpenAPIScripMaster_2026-07-31.json` (`ce198be4…b29f5ab`), over the 204 settled symbols and the
span 2016-10-03 → 2026-07-30, with the four-item pre-run checklist honoured.

**NOT authorized, and unchanged by this review:** anything that would move a number in the
ledger. The trader's Q43 and Q44 stay open and the run says so on its own manifest; Q-17's five
market-wide dates ride to the report's disclosures rather than being excluded; Q-19 stays open
for the architect with its cost measured at 0.048 pp.

**The operator owes a snapshot before starting** — both stores moved during RESUME-2 and again
during this review's read-only probes (mtimes only). The preflight prints both roots'
last-changed times; keep TWO generations.

**Read finding Q1 before choosing when to start.** The projection is a floor.
