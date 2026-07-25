# REVIEW_5A — chunk 5A · SmartAPI client & single-symbol backfill + quality gates

**Reviewer:** fresh QC session — `personas/quant_reviewer.md` **and** `personas/code_reviewer.md`
(plan.md chunk 5A review type **QC**). Zero shared context with any builder/fix session.
**Date:** 2026-07-25 · **Span:** `2d55919` (chunk5A-prep) .. `9f06b6d` (fix4) — **six commits**,
ONE verdict for the stack: prep · build · fix(Q-10) · fix2(k_shares) · fix3(demerger-scope + Q-11
STOP) · fix4(Q-11 EXECUTED: measured per-event reconstruction).
**Builder entries reviewed:** PROGRESS `[2026-07-25 21:15]` fix4 back through the build entry.

## VERDICT: **PASS**

I assumed every number the trader will ever see rests on this chunk being wrong until it proved
otherwise, and it proved otherwise. The heart of the stack — the Q-11 per-event vendor-adjustment
reconstruction (`vendor_adjustment.py`) — I re-derived by hand end-to-end on the RELIANCE-shaped
era-flip symbol: the demerger resolves to `measured 0.907…` in the recent `{D,B1}` era and **flips
to `absent`** in the older `{R,D,B1}` / `{B0,R,D,B1}` eras, the 2020 rights is `measured 0.97…`
(price) and `0.98…` (volume) **independently**, and the min-cost arbitration lands on the only
containment-passing chain (cost 3), exactly as the ruling requires. I recomputed the RELIANCE map
k_price per era from the map (`0.5×0.907863=0.453931`, `0.5×0.987305=0.493652`, `×0.5=0.246826`) —
all match. I built the map twice (byte-identical) and proved the committed factors are invariant to
probe-day order. I ran a **9-mutant matrix** on the un-adjustment math (8 caught, 1 equivalent). I
scanned all six commits, the evidence pack and the working tree for credentials (none), AI
attribution (none) and test weakening (none). **Full suite 911 passed / 0 failed** from a clean
state (`.pytest_cache` + every `__pycache__` deleted), fully offline — **909 from the stack**
(matching the fix4 claim exactly) plus **2 reviewer probes** I added and kept.

Findings: **two LOW** (both chunk-5B-forward, gate-1-safe today) **and five INFO**. None is a FAIL
trigger; none is a CONTEXT.md deviation. Chunk 5A's own deliverable (TCS, a clean bonus-only symbol)
is correct on every path. The Q-11 machinery is built, proven and offline-tested; its *consumption*
for era-inconsistent symbols is chunk 5B's job, honestly disclosed as such.

The `git status` was clean at review start; the only working-tree change I introduce is
`tests/test_review5A_probes.py`. **No file under review was modified. No fixture was touched.
CONTEXT.md and plan.md are provably untouched in the span.**

---

## 1. Architect's directed checks

| # | Check | Result |
|---|---|---|
| 1 | Ruling-chain coherence; AST/call-graph hunt for a fix2/fix3 path that un-adjusts WITHOUT the map; tier-2-rights un-provability survived; k_shares subsumed by measured volume | **PASS** (2 forward-notes → F1, F2) — §2 |
| 2 | Recompute RELIANCE k_price per era; era key = event-set-in-(D,F]; "decided-newest-carried-older" hand case; ≤1 unknown/era | **PASS** — §3 |
| 3 | Measurement discipline: single scalar/median; PER-DAY containment (2p + 0.1% floor); candidate set {ours,measured,absent}; preference; adversarial masking; determinism | **PASS** — §4 |
| 4 | Mutation matrix on the un-adjust math (÷↔×, era-carry, rounding, identity-guard) | **PASS (8 caught / 1 equivalent)** — §5 |
| 5 | Original build: client, master+tick, windowing+clamp, ledger resume, store schema, aggregator E12, minute_loader, gates 1–3, F10 | **PASS** — §6 |
| 6 | Evidence audit: 27/27 table, 2024-11-07 microstructure flagged, TCS days_rewritten=0, gate-1 year table | **PASS (one stale-reason doc note → F3)** — §7 |
| 7 | Secrets across six commits + evidence + logs; .env ignored; nothing printed | **PASS** — §8 |
| 8 | Round-3 receipts: risk=1000 wired + null-blocks kept; Q-8/Q-9 well-formed | **PASS** — §9 |
| 9 | Judge B63–B92, one line each | **Done — all APPROVE (3 with forward-notes)** — §10 |
| 10 | Standard sweep: no test weakened, fixture digests, commit hygiene, AI attribution, STATUS/PROGRESS/SHA | **PASS (2 hygiene INFO → F4, F5)** — §11 |

**Method.** The mutation matrix mutated source in place, ran the targeted tests, and restored exact
bytes via `git checkout` between mutants (verified clean after each). Every other probe read frozen
fixtures, injected fakes, or pure synthetic inverted-vendor data. **This review issued zero network
traffic**; the offline socket guard (`tests/conftest.py`, autouse) is intact.

## 2. Ruling-chain coherence + the dead-path hunt (directed check 1)

**The narrative is honest.** QUESTIONS.md reads Q-10 (un-adjust to raw via the chunk-3 table) →
ADDENDUM (k_price/k_shares split) → ADDENDUM 2 (demergers excluded from minute un-provability, on
the 2016-only "not demerger-adjusted" premise) → **the fix3 live re-run CONTRADICTS that premise**
(demerger baked into 2022–2023 but not 2016) → Q-11 (reconstruct per event by MEASUREMENT). Each
step records the ruling verbatim BEFORE the code, executes it, and — at fix3 — flags the
contradiction rather than silently overriding (decision B85: exemplary STOP discipline). fix4's
"How FIX-2/FIX-3 fold in" is accurate: the *measurements* stand (2016 demerger absent; 2022–2023
present ~0.908; rights vendor-scaled), only their *premises* are superseded.

**The code implements the FINAL state.** `vendor_adjustment.unadjust_with_map` is the per-event
measured path. A call-graph (not grep-only) confirms there is **no dead/bypass path that
un-adjusts an era-inconsistent symbol WITHOUT the map behind the operator's back**: the Q-10/FIX-3
factor-table path (`minute_unadjust.unadjust_bars`) survives *by design* as the documented FALLBACK
(B90) for clean bonus/split-only symbols (TCS), and is chosen only when `adjustment_map is None`
(`minute_backfill._fetch_and_store_window:353`). Tier-2-rights un-provability **survived**
(`unprovable_suppression_dates` keeps `kind != KIND_DEMERGER`; the map path makes a rights an
un-`ours` `EventSpec` that is measured-or-absent — strictly more capable). k_shares is **subsumed
and corrected** by measured volume: for a share-count event the map's `ours` volume factor == the
price factor (== what k_shares used); for a rights the map *measures* the vendor's volume factor
(0.9877), exactly the −1.24% failure k_shares alone produced (B89).

→ **F1 (LOW, code/quant)** and **F2 (LOW, quant)** below — both consumption-wiring notes for chunk
5B, gate-1-safe today, out of scope for what chunk 5A claims (TCS).

## 3. Map arithmetic, independently (directed check 2)

- **k_price per era** recomputed straight from the map's chosen factors: `{demerger,2024-bonus}` =
  `0.907863×0.5 = 0.4539315 → 0.453931`; `{rights,demerger(absent),2024-bonus}` =
  `0.987305×1×0.5 = 0.4936525 → 0.493652`; `{2017-bonus,rights,demerger(absent),2024-bonus}` =
  `0.5×0.987305×0.5 = 0.24682625 → 0.246826`. **All three match.**
- **Era key = the in-window event set.** `AdjustmentMap.in_window_ex_dates(day) = {ex : day < ex <=
  fetch_date}` — the same half-open `(D, F]` the un-adjust divides against. Verified.
- **"Decided at newest appearance, carried older."** Hand-traced the ACME (=RELIANCE shape) backward
  pass: `{B1}`→bonus ours 0.5; `{D,B1}`→ the demerger is the lone new unknown, SOLVEs to 0.90 (only
  passing chain); `{R,D,B1}`→ carried demerger 0.90 does **not** contain, but a no-`ours` event may
  FLIP to `absent`, freeing the new rights to SOLVE to 0.97 (cost-3, the unique passing chain);
  `{B0,R,D,B1}`→ carried rights stays measured (a with-`ours` event cannot flip), new bonus0 is
  `ours`. This is the era-inconsistency working exactly as the ruling describes, and matches
  `test_era_flip_demerger_resolved_present_recent_absent_old`.
- **≤1 unknown per era.** Two guards: the probe-gap guard marks any era introducing >1 new event
  un-provable (`build_map:422`), and the combo filter rejects >1 fresh SOLVE (`_resolve_pass:563`).
  Both fire; the second is redundant given the first (see §5, M8).

## 4. Measurement discipline + determinism (directed check 3)

- **Single scalar per (event,era):** phase-2 `_refine_scalars` sets each MEASURED event to the
  MEDIAN of `fetched/raw` (price) or `raw/fetched` (volume) over ALL its pre-ex probe days, dividing
  out the other events' resolved factors — "median ratio over pre-ex probe days," never a fit.
- **PER-DAY containment, not median.** `_price_contained` checks EVERY probe day within
  `max(2 paise, 0.1%×raw)` (B92 hardening of B88's median). I confirmed this catches a **bimodal**
  era (`test_bimodal_majority_era_is_unprovable_per_day_not_median`) and that the phase-3
  re-validation re-proves the *refined* chain before committing `provable=True` (`build_map:489`).
- **Candidate set is exactly {ours, measured, absent}** with preference `ours(0)>absent(1)>measured(2)`.
- **Adversarial masking (constructed, kept as a probe).** A vendor bonus factor **+0.2%** off ours
  fails ours' containment → forced to MEASURED, recovering 0.5010 (containment ≤1p); a **+0.05%**
  variant sits inside the 0.1% floor → masked as `ours` (immaterial, below the microstructure floor
  the ruling accepts). So the preference can only ever swallow a sub-0.1% variant, and the
  containment oracle catches every material one. Pinned by
  `tests/test_review5A_probes.py::test_min_cost_prefers_ours_only_within_containment_measures_a_material_variant`
  (verified to FAIL when containment is disabled).
- **Determinism.** `build_map` from identical measurements twice → **byte-identical** `to_dict`
  (`test_build_is_deterministic`, re-confirmed). Stronger: the COMMITTED factors are invariant to
  probe-day order (medians are order-free) — only the audit `probe_days` list tracks input order.
  Pinned by `test_review5A_probes.py::test_committed_map_factors_are_invariant_to_probe_day_order`.

## 5. Mutation matrix on the un-adjustment math (directed check 4)

Each mutant applied in place; targeted tests (`test_vendor_adjustment`, `test_minute_unadjust`,
`test_minute_backfill`, `test_f10_volume_gate`) rerun; exact bytes restored between.

| mutant | result |
|---|---|
| M1 price `÷k_price` → `×k_price` | **CAUGHT** (19 failed) |
| M2 volume `×k_shares` → `÷k_shares` | **CAUGHT** (15 failed) |
| M3 era-carry direction reversed (oldest-first) | **CAUGHT** (4 failed) |
| M4 nearest-tick rounding half-even → half-up | **CAUGHT** (8 failed) |
| M4a price rounding half-even → half-up | **CAUGHT** (32 failed) |
| M5 identity-guard price-check removed (volume-only) | **CAUGHT** (`test_rebuild_unadjusts_a_price_only_special_dividend_day`) |
| M6 per-day price containment disabled | **CAUGHT** (5 failed) |
| M7 probe-gap guard defeated (`>1`→`>99`) | **CAUGHT** (1 failed) |
| M8 ≤1-fresh-solve guard defeated (`>1`→`>99`) | **SURVIVED — EQUIVALENT** |

**M8 is a provably-unreachable mutant, not a coverage gap.** A `SOLVE` option is generated ONLY for
a NEW (not-yet-canonical) event, and the probe-gap guard (M7, caught) marks any era with >1 new
event un-provable and `continue`s BEFORE `_resolve_pass` runs — so `_resolve_pass` never sees >1
SOLVE candidate. The ≤1-SOLVE filter is a defensive inner layer of the same invariant the outer
guard enforces (the pattern REVIEW_4 called an EQUIVALENT survivor). No test needed. **Every mutant
the architect named — price ÷k↔×k, volume ×k↔÷k, era-carry direction, half-even rounding,
identity-guard condition — is caught or tripwired.**

## 6. Original build (directed check 5)

- **Client** (`smartapi_client.py`): fully injectable (connect/totp/sleep). Throttle 0.5s on a
  monotonic clock; backoff 1-2-4-8-16s; session-refresh on expiry markers (re-login, fresh TOTP);
  ONE_DAY 00:00 trap forced; +05:30 verified-and-dropped to naive IST, non-IST offset rejected;
  8000-response-cap flagged. Only `generateSession`/`terminateSession`/`getCandleData` are called —
  **no order-placement code anywhere in `src/` or `scripts/`** (R4/CLAUDE rule 4). Credentials
  redact (`Credentials.__repr__ = "<redacted>"`); `_quiet_library_logging` raises logzero above ERROR
  so the vendor cannot spill `Authorization: Bearer …` on a transient 403 (B71); `_safe_message` is
  credential-free.
- **Instrument master**: `tick_size = paise/100` always, a fractional-paise tick raises (no PoC
  heuristic), strict `exch_seg==NSE AND symbol==<SYM>-EQ`. The F7 tick cross-check
  (`test_instrument_master.py`) pins the master-derived ticks == frozen `tick_sizes.json` (Q-2
  tripwire), with `tick_sizes.json` documented TEST-ONLY.
- **Windowing + clamp**: `ONE_MINUTE_WINDOW_DAYS=28` (≤20 trading days ≤7500 < 8000, can't truncate);
  `clamp_start = max(2016-10 floor, requested, first_data)`; a whole-range-pre-floor request plans
  zero windows.
- **Ledger resumability**: `pending_windows` skips terminal (present/empty) rows only when
  `stored.window_end >= end`, so the `--to today` incremental tail is refetched (the silent-hole
  hazard is closed), and `write_bars` replaces by date idempotently.
- **Minute store**: explicit schema (int64 paise, date32, naive `timestamp("us")`), per-DATE
  replacement across month seams, `atomic_write_with` (fsync-before-replace), naive-IST enforced on
  write, `fetch_date` ledger column nullable+back-compat, corrupt-ledger read re-raised as a named
  `MinuteStoreError` (not a swallowed traceback).
- **Aggregator (E12)**: open-stamped `[T,T+15)`, grid 09:15..15:15 (25 bars, closing 09:30..15:30),
  off-grid 15-min stamp and out-of-session 1-min stamp rejected, duplicate-stamp rejected,
  one-trade-date-at-a-time. Matches E12 char-for-char.
- **minute_loader**: returns the day's stored bars as `bias.Candle` in stamp order, or `None` — the
  chunk-4 R3 interface, now on real data.
- **Gates 1–3**: gate 1 band `[-0.1, +5.0]` (Decimal, exact, zero-daily = FAIL); gate 2 exactly the
  spec criteria (missing>15, dupes, high<low, close-outside — `open` correctly excluded; an
  out-of-session bar is candle-level dropped, not a day-killer); gate 3 raw/adjusted/indeterminate
  with a `raw-daily-gap` k. **F10** golden intact: 25 PoC days in `[+0.02%, +3.6%]` and passing
  `[-0.1, +5.0]`, extremes MANAPPURAM/HDFCBANK, plus the Q-10 identity assertion (2026 days →
  empty (D,F] → k=1 → byte-for-byte).

## 7. Evidence audit (directed check 6)

- **27/27 probe days are internally consistent** with the six probe windows the runbook names:
  Oct-3..7 (5) + Jul-1..5 (5) + Jul-1..6 (4) + Jun-15..20 (4) + Sep-1..6 (4) + Nov-4..8 (5) = **27**.
- **2024-11-07 microstructure day is FLAGGED, not hidden** (footnote ¹): bhavcopy high 132400 vs
  1-min high 132390 = 10 paise, an odd-lot/block trade the daily counts and the continuous series
  does not — the same reason gate-1 skews positive. → **F3 (INFO)**: the footnote attributes the
  day's provability to "the MEDIAN residual (0 paise)", but the committed code (B92) is PER-DAY
  containment with a `max(2p, 0.1%)` relative floor — 10 paise < the 132-paise floor, so the day is
  provable for the *relative-floor* reason, not a median. Conclusion right, stated reason stale
  (doc-only).
- **TCS days_rewritten=0** is logic-verified and test-backed: the identity guard `_stored_day_is_raw`
  skips a day whose price+volume already reconcile, and the operator's TCS store is already-raw
  (Q-10 migration) → all skipped. Pinned by `test_rebuild_via_map_is_noop_on_an_already_raw_store`.
- **gate-1 year table** (0%/0%/56.5% → 100%/100%/97.2% for 2016/17/18, 2019+ identical) is
  internally consistent with the ADJUSTED→un-adjust mechanism and the gate-2 residuals.
- **Disclosed limitation:** the LIVE RELIANCE map + TCS regression rest on the operator's
  credentialed runbook run; a review holding no credentials cannot reproduce them. I re-derived the
  arithmetic (k_price, 27/27) for internal consistency and exhaustively offline-tested the PURE
  engine that produces them (synthetic inverted-vendor probes + my mutation matrix). This is the
  right assurance level for a live-ingestion chunk (chunk 4's review treated its one-off SmartAPI
  ONE_DAY evidence the same way).

## 8. Secrets (directed check 7)

No credential material in any of the six commits, the evidence pack, `scripts/`, or the working
tree. `.env` is gitignored (`git check-ignore .env` → `.env`) and **not tracked**. Every credential
grep hit is an env-var NAME (`SMARTAPI_*`), a dataclass field name, a docstring describing what the
vendor library must NOT leak, or a `*_ZZZ` test placeholder. The only `print()`s on the login path
are the `--allow-network`-required guard messages. Credentials are redacted at every exit
(`__repr__`, `_safe_message`, `_quiet_library_logging`), and `config.env_value` names the KEY never
the value.

## 9. Round-3 receipts (directed check 8)

- **OPEN-1 wired:** `config.yaml risk_per_trade: 1000` (cited to Q29/Round-3); `require_risk_per_trade`
  returns 1000. The money-guard is **kept and strengthened**:
  `test_a_null_risk_per_trade_still_blocks` writes a synthetic `null` config and asserts
  `require_risk_per_trade()` still raises `ConfigError`. The old "must be None" assertion was
  legitimately inverted (the value is now genuinely set), not weakened.
- **Q-8** (POC 8- vs 9-candle window) and **Q-9** (reference==POC above-branch) are well-formed
  class-A entries with correct interim behaviors — Q-8 interim = the spec's 8-candle window (blocks
  chunk-6 *gate closure*, not build); Q-9 interim = log+no-trade+count (blocks one chunk-7 branch).
  Neither blocks chunk 5A, and nothing in 5A silently resolves them.

## 10. Class-B decisions B63–B92 — one line each

| # | Judgment |
|---|---|
| B63 | **APPROVE** six-module pure/IO split; verified gates/aggregate/unadjust/vendor_adjustment are import-pure. |
| B64 | **APPROVE** injectable client + self-redacting Credentials; whole retry ladder tests offline. |
| B65 | **APPROVE** tick=paise/100 always, fractional-paise raises, no PoC heuristic; F7 tripwire. |
| B66 | **APPROVE** store keyed symbol×month, per-date replace, fsync-atomic, window ledger. |
| B67 | **APPROVE** strict `NSE ∧ <SYM>-EQ` selection; a BSE/NFO namesake is never chosen. |
| B68 | **APPROVE** 28-day window under the PoC-found 8000-response cap; cap flagged if ever hit. |
| B69 | **APPROVE** gate-3 k from the raw daily gap — self-contained; RAW vs ADJ are far apart. |
| B70 | **APPROVE** OPEN-8=ADJUSTED→STOP, Q-10 raised, no un-adjust/E11 edit in the build (correct STOP). |
| B71 | **APPROVE** logzero silenced before any request — the critical rule-4 credential-spill guard. |
| B72 | **APPROVE** real minute_loader → Candle tuples or None; satisfies the chunk-4 interface. |
| B73 | **APPROVE** un-adjust = inverse of chunk-3 `factors_between` on the same `(D,F]` window. |
| B74 | **APPROVE** k_cum==1 exact identity, tick-snap skipped (F10 stays byte-for-byte). |
| B75 | **APPROVE** tick-snap ≤2 paise else flag+count; TCS old-grid days flag cosmetically. |
| B76 | **APPROVE** un-provable spans → gate-1 exclude + systematic floor (mechanism sound; demerger scope later refined). |
| B77 | **APPROVE** fetch_date ledger column, nullable back-compat verified. |
| B78 | **APPROVE** factor table from NSE CA + raw-store cum-closes (opt-in, day-cached). |
| B79 | **APPROVE (note)** Q-10 rebuild skips identity days but is non-idempotent — superseded by the idempotent map rebuild (B90); kept as the factor-table path. |
| B80 | **APPROVE** honest: 4b RELIANCE deferred to a live re-pull, later settled by fix2/3/4. |
| B81 | **APPROVE** k_price/k_shares split; the rights-excluded-from-k_shares flag was the RIGHT thing to raise — resolved by measurement in B89. |
| B82 | **APPROVE** identity-skip needs k_price==1 AND k_shares==1 (special-dividend correctness). |
| B83 | **APPROVE** the 2016 measurement; its over-GENERALISATION was honestly flagged and later corrected. |
| B84 | **APPROVE** `unprovable_suppression_dates` centralises the demerger filter in one place both consumers call. |
| B85 | **APPROVE** fix3 executed-then-flagged the contradiction and raised Q-11 — model STOP discipline. |
| B86 | **APPROVE** per-event MEASUREMENT not policy; hand-verified correct on the era-flip case. |
| B87 | **APPROVE** single measured scalar = median over pre-ex days; proven order-invariant. |
| B88 | **APPROVE-as-superseded** median containment → tightened to PER-DAY by B92 (stricter/safer); only the evidence footnote still cites the median (F3). |
| B89 | **APPROVE** rights & demerger volume measured independently — resolves B81 by observation. |
| B90 | **APPROVE (note)** ingest consumes the map + rebuild identity guard; NOT yet wired to the CLI and the factor-table fallback is price-blind for a special dividend (F1/F2). |
| B91 | **APPROVE** era key = in-window set; unprobed/un-provable → None → gate-1 excludes; empty set = exact identity. |
| B92 | **APPROVE** adversarial-review hardening (per-day containment, refined-chain re-validate, probe-gap guard, price+volume identity guard, drop zero-vol / refuse dup ex-date) — each verified by test and my mutation matrix. |

## 11. Standard sweep (directed check 10)

- **No test deleted or weakened.** `test_config.py` is the only pre-existing edited test file: −2/+3
  (net +1), the two removals being the OPEN-1 "must be None" assertions legitimately inverted by the
  trader's answer, with the money-guard preserved as `test_a_null_risk_per_trade_still_blocks`. No
  `skip`/`xfail`/commented-assert added anywhere; the other edited test files are new. `git diff
  656bfbc 9f06b6d -- tests` is +2537/−10 (the 10 = the two old config bodies + a docstring).
- **Fixtures frozen.** `git diff 656bfbc 9f06b6d -- tests/fixtures poc/data` is only ADDED
  `instrument_master_sample.json` + an append to `PROVENANCE.md`; **no poc/data byte changed**.
  `test_fixture_integrity.py` pins 56 digests (exact-set assertion on poc/data at :198); exactly one
  digest added, none changed.
- **Commit hygiene.** All six carry imperative-summary + what/why bodies citing chunk+section.
  → **F4 (INFO):** only the main build `35aa412` ends `(unreviewed)`; the four fix commits omit the
  suffix though they are also unreviewed builds (STATUS/PROGRESS already mark the stack unreviewed).
- **No AI attribution.** Author uniform `chinmoy-paul <chinmoypaul8897@gmail.com>`; no
  "Generated with", "Co-Authored-By", "Claude"(as AI), "Anthropic", 🤖 in any message; every source
  hit for those strings is the literal filename "CLAUDE.md".
- **STATUS/PROGRESS/SHA.** STATUS = `chunk 5A: built` (not reviewed-PASS); no `chunk5A-pass` tag;
  tree clean; `HEAD == origin/main == 9f06b6d`. → **F5 (INFO):** the newest chunk-5A PROGRESS entry
  does not textually state the pushed SHA (CLAUDE.md asks the report block to); the push did land.

---

## 12. Findings

**F1 — LOW — [code/quant] the FIX-4 map is built + proven + consumable, but not wired into the
operator ingest/rebuild CLI.** `backfill_symbol(adjustment_map=…)` and `rebuild_symbol_raw_with_map`
exist and are tested, but no `src/` caller passes a persisted map: `acumen-minute-backfill`'s
`run()` always calls `backfill_symbol` on the Q-10 factor-table path, and `rebuild_symbol_raw_with_map`
is reachable only from tests. For an era-inconsistent symbol (RELIANCE) the CLI therefore stores
factor-table un-adjusted prices that gate-1 EXCLUDES (safe, nothing traded) but does not consume the
map even after `acumen-build-adjustment-map` writes it. **Not a chunk-5A defect** — 5A's deliverable
is TCS (bonus-only, correct on the factor-table path) and the PROGRESS explicitly assigns map
*consumption* to chunk 5B. **Chunk 5B must wire `backfill_symbol(adjustment_map=load_map(…))` (or a
rebuild-with-map CLI) for demerger/rights symbols.**

**F2 — LOW — [quant] the Q-10/FIX-3 factor-table fallback has no price oracle, so gate-1 (volume)
cannot catch a price-only mis-adjustment.** In `unadjust_bars`, a special dividend divides price
(`k_price`) but leaves volume (`k_shares=1`); if the vendor did NOT apply that price adjustment to
the minute feed, the fallback stores a ~2%-wrong price and gate-1 volume still passes. **Unreachable
for chunk 5A** (TCS has no special dividend). The map path closes it (per-day price containment), so
chunk 5B should route ANY symbol carrying a non-share-count event (special dividend / rights /
demerger) through the map — the Q-11 note names demerger symbols but not special-dividend-only ones.

**F3 — INFO — [code] evidence-pack footnote ¹ gives a stale reason.** It says the 2024-11-07 day is
provable via "the MEDIAN residual (0 paise)"; the committed code (B92) uses per-day containment with
a `max(2p, 0.1%)` relative floor, which is why the 10-paise day passes. Conclusion correct, reason
outdated. Doc-only.

**F4 — INFO — [code] the four fix commits omit `(unreviewed)`.** Only `35aa412` carries it; the fixes
are also unreviewed builds. Cosmetic — the stack's unreviewed state is unambiguous in STATUS/PROGRESS.

**F5 — INFO — [code] the newest PROGRESS entry does not record the pushed SHA.** CLAUDE.md asks the
final report block to; `HEAD == origin/main == 9f06b6d` regardless. This review states the SHA.

**F6 — INFO — [quant] the min-cost preference masks a vendor variant up to the 0.1% floor** (for
RELIANCE ~₹2700, ≈₹2.70). This is the ruling's stated tolerance, bounded and disclosed; my probe
pins the boundary and shows every *material* variant is measured. Not a defect.

**F7 — INFO — [quant] the map's audit `probe_days` list order tracks input order** (cosmetic); the
committed FACTORS are order-invariant (proven). "Same fetched inputs → same map" holds.

## 13. Checklist coverage

**quant_reviewer** — *Look-ahead:* the whole layer is data-provenance, not signal timing; un-adjust
uses only events with ex-date in `(D, F]` (no future leakage into a day's own price). *Units:*
integer paise throughout, volume in shares, tick=paise/100, no float `==` (Decimal + exact band
compares). *Corporate actions:* the Indian factors come from chunk-3 (reviewed); this layer INVERTS
them and, where the vendor differs, MEASURES — arbitrated by a raw-daily oracle; demerger/rights
handled by measurement, ordinary dividends drop (k=1). *Data honesty:* every un-provable/excluded
day is counted, the microstructure day is flagged, gate-1 is the per-day proof, the −0.1% floor is
NOT widened. *Fixtures/OPEN items:* F10 intact; OPEN-1 wired with the null-guard kept; Q-8/Q-9
raised not guessed.
**code_reviewer** — *Tests:* 911 green from clean, offline; error paths covered (bad candle shape,
non-IST offset, degenerate probe day, dup ex-date, corrupt ledger, missing daily row). *Failure
behaviour:* throttle+backoff+relogin; atomic fsync-before-replace; resumable ledger; no bare
`except:` swallowing a real error. *Secrets:* none anywhere; logzero silenced. *Time/precision:*
naive IST enforced, integer paise, no clock in pure code. *Structure:* engines pure, I/O isolated,
no hardcoded tick/symbol/date. *Git/docs:* six logical commits, what/why, no AI attribution,
STATUS/PROGRESS complete, CONTEXT/plan untouched. *Deps:* `pyproject.toml` gained only two console
entry points (no new package).

## 14. Scope

`2d55919..9f06b6d`: prep (Round-3 receipts, risk=1000) + build (`smartapi_client`,
`instrument_master`, `aggregate`, `quality_gates`, `minute_store`, `minute_backfill`) + Q-10 fix
(`minute_unadjust`) + fix2 (k_shares) + fix3 (demerger scope) + fix4 (`vendor_adjustment`,
`build_adjustment_map`). No later-chunk code appears (no POC/signals/simulate). This review added
exactly one file — `tests/test_review5A_probes.py` (2 tests, both verified to fail on their mutant)
— and modified no file under review.

## 15. Fix log (appended by later sessions — the review text above is unchanged)

| Finding | Status | Notes |
|---|---|---|
| F1, F2 | open — chunk 5B | Wire map consumption into the ingest/rebuild CLI; route non-share-count symbols through the map. Gate-1-safe until then. |
| F3, F4, F5, F6, F7 | INFO | Doc/hygiene/observation notes; no code change required. |
