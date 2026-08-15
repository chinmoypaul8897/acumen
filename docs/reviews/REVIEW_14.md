# REVIEW_14 — chunk 14, THE PARITY HARNESS + TELEGRAM · QC, both personas

**Span:** `db45998..e3c43fa` (15 commits, linear, no merges).
**Personas:** `personas/quant_reviewer.md` + `personas/code_reviewer.md`.
**Law:** CONTEXT v2.1a. **Card:** plan.md chunk 14. **Rulings:** QUESTIONS.md Q-32 (14-Aug-2026).

---

# VERDICT: **FAIL**

A fix session is owed. The FAIL rests on chunk 14's **own** scope — not on the carried
inheritance — and on three findings in particular:

* **B1 — REVIEW_13B's Q3 is NOT closed, though the chunk claims it is.** The fence
  (`fence_ca_cache`) was built, works correctly on all four machine layouts, and is a genuine
  downgrade-to-cache rather than a refusal. It is simply **never asked** on the path that
  matters: `live_refresh.refresh_corporate_actions` calls `ca.fetch_nse_corporate_actions(...,
  allow_network=<the CLI flag>, cache_dir=<cache_root>)` with no fence call anywhere above it.
  A `--refresh --allow-network` morning therefore still writes inside the stores. The defect
  REVIEW_13B pinned was relocated one module away from the fence built to stop it.
* **B2 — the test that certifies it asserts its own name, not its property.**
  `test_Q3_a_LIVE_REFRESH_writes_ZERO_bytes_under_the_stores` never enters `morning_refresh`;
  it drives `bt.build_runner(..., allow_network=True)` and fingerprints only `<data_root>/nse` —
  none of the three directories a real live refresh actually writes. This is exactly the
  code_reviewer checklist item 10 pattern (the REVIEW_9B M1/M6 shape): a fix pinned at the
  helper and not at the thing it produces, leaving the property revertible with the suite green.
* **B3 — the documented morning command cannot start the screener, and writes to the stores
  before it fails.** With `--refresh`, `run_screener` hands `build_live_screener` the PUBLISHED
  holiday calendar (`run_screener.py:118`, `:164`). `live_screener.py:1907` builds the proper
  live calendar only `if live and calendar is None`, so it is skipped; `backtest.py:1858` then
  rejects any supplied calendar whose `trading_days is None`. Probed:
  `TradingCalendar.from_holidays(...)` → `source='published', trading_days=None`. The operator's
  08:45 command mutates `data_root/daily_store` and `cache_root`, then exits 1 with "the screener
  cannot start". **No test in the repository drives `--refresh` through the CLI** — the only two
  hits in `tests/` are a docstring and a comment — which is why a whole pre-open-to-screener seam
  is unexercised.

B3's mechanism was introduced by chunk 13's M17 fix and missed by REVIEW_13B. It is named here
because chunk 14 shipped `docs/morning_runbook_stub.md`, whose §1 instructs the operator to run
precisely that command, and declared the card "fully met".

Three further chunk-14-scope findings are individually blocking-adjacent and are listed in
PART 2: the Telegram three-act gate that is two acts in code, the end-of-day summary that
reports an empty day after a resume, and the M21 fix's new phase-regression hole.

---

# PART 0 — WHAT HOLDS, AND HOLDS WELL

This is a strong chunk that fails on its edges, not its centre. The following were attacked and
survived, and the review would be dishonest not to say so first.

## 0.1 THE PARITY PROJECTION IS CORRECT — hand-derived, three-way match

The one thing the harness could not self-check: `project_boundaries()` is a second reading of
CONTEXT 3.4 written by the same session as the live layer. It was re-derived **by hand from the
raw Parquet**, importing nothing from `src/acumen`, on two days.

### ITC 2026-06-10 — the carried-bias day (seed and carry both exercised)

BIAS (3.2): pair (C = 2026-06-09, P = 2026-06-08). `C.high 28170 <= P.high 28345` and
`C.low 27715 >= P.low 27695` → **inside bar** → carry. The carry needs a seed, so the chain was
walked back: the pair ending 2026-06-09 (C = 06-08, P = 06-05, body [28000, 28070]) is not
inside, and rule 1 fires strictly — `C.close 27945 < bodyMin 28000` by 55 paise → **BEARISH**.
**Seeding day 2026-06-09, seeding rule `rule-1-breakout`.** Bias = bearish by `inside-bar-carry`,
side short. Matches.

POC (3.3): window stamps 09:15..11:14, **120 of 120 bars**, zero Q-17 strays. tick = 5 paise
(ITC-EQ, from the pinned master). top 28480, bottom 27865, `totalTicks = round(615/5) = 123`.
tpr candidates: 5 → 25 rows (|25−24| = 1) vs 6 → 21 rows (|21−24| = 3) → **tpr = 5**, rows 25
paise wide. Prorata conserves volume exactly (Σ = 7,298,155). Winning row [28315, 28340) at
2,239,387.939 against a runner-up of 986,644.097 — a 2.27× margin, so no spreading nuance can
move it. **POC = 56655/2 paise = ₹283.275.** It is half-paise because the row spans an ODD
number of paise (25), so the midpoint lands on a half — the CONTEXT 7-E11 domain the comparison
must survive, and does.

REFERENCE (3.4-1): the 11:00–11:15 candle over stamps 11:00..11:14 closes **28440**. Bearish
mirror: `28440 > 28327.5` → **ARMED at 11:15**.

EVERY TRANSITION — all sixteen eligible closes, 11:30 → 15:00:
`28430, 28420, 28415, 28430, 28400, 28385, 28480, 28525, 28490, 28475, 28465, 28440, 28435,
28415, 28415` (and the 15:00–15:15 candle at 28390). **MIN = 28385**, which is 57.5 paise —
11.5 ticks — above the POC. Zero closes strictly below, zero equal. **No trigger.** Entry, stop,
target, qty and exit are all None; nothing is consumed; ARMED at all eighteen boundaries; no
square-off, because a day that never entered has no position to square off.

### ADANIENSOL 2026-05-08 — the gap-entry day (the money path, hand-derived)

Because ITC never trades, the entry/stop/target/qty/exit half of the projection was hand-derived
separately. Bias bearish by `rule-1-breakout`; POC 138155; reference 138020, so the day opens
**WAIT-ABOVE** (the Entry-2 path), arms at 11:30 on 138160, triggers at 11:45 on 137790.

The gap test is where a projection bug would live: entry candle **high 138100 < POC 138155**, so
the candle opened beyond the POC and never traded at or above it → SL is **the previous 15-min
candle's close, 138160**, not the entry candle's high. Taking the high would give risk 310 and
qty 322; the spec's rule gives **risk 370, qty floor(100000/370) = 270**, TP = 137790 − 3×370 =
**136680**, exit stop-loss-hit @ 138160 on the very next candle.

**THREE-WAY MATCH on both days: hand derivation ≡ `project_boundaries()` ≡ the live
`LiveScreener` sequence, all 36 boundary rows, all 7 fields, all 5 day fields.** No look-ahead
was found in the projection (0 of 18 boundaries on three days).

## 0.2 THE NEGATIVE CONTROLS ARE REAL

`test_the_harness_NAMES_a_difference_when_there_is_one` and
`test_the_harness_CATCHES_a_real_live_half_that_drifts` both go **RED on 4 of 4 rubber-stamp
mutations** of the comparator (comparator short-circuit; `BOUNDARY_FIELDS = ()`;
`DayParity.matched` hardcoded True; `DAY_FIELDS = ()`). The first names boundary AND field
literally — it asserts the strings `"11:15 phase: live='armed' backtest='waiting'"` and
`"11:30 entry_paise: live=74195 backtest=74095"`, not merely "differs". 23 reviewer-authored
probes confirm the harness names boundary+field for qty, late and missing exits, half-paise POC,
alert order, duplication, omission, and boundary count.

The second control is materially weaker than the first (finding M-neg, LOW): it names a field but
not the boundary, and accepts a disjunction (`"entry_paise" in row or "phase" in row`).

## 0.3 NO DECISION DRIFT EXISTS

The 15-day sample re-ran independently and reproduced **15 days / 14 judged / 14 matched / 0
mismatched / 1 disclosed**. Across **96 parity runs** — the committed sample plus three new
strata of the reviewer's own choosing (a different tie day, a different gap day, a second
oracle-refused day) plus a broader sweep — **not one genuine live-vs-backtest decision drift was
produced: zero mismatched boundaries, fields or alerts anywhere.** The central claim of the
chunk is true. What is defective is the harness's ability to *certify* it in some postures
(PART 3), not the answer it certifies.

**The ADANIPORTS 2026-02-06 disclosure is real**, re-derived from the ten-year ledger read-only:

```
{"symbol":"ADANIPORTS","day":"2026-02-06","status":"refused",
 "reason":"gate 1 (volume reconciliation)","gate1_passed":false,
 "gate1p_passed":true,"gate2_passed":true,"minute_count":375,"signalled":false}
```

The harness's own reason string is `gap 52.135% is above the band [-0.1, 5.0]` — the 52% gap,
confirmed. Because the backtest half never evaluates the day, all 38 recorded differences read
`backtest=None`; that is CONTEXT 4.7's bounded difference, correctly NOT counted as a mismatch,
and correctly named with its reason and its alerts. The escape hatch is not abusable in the
direction that matters: a day can only be excused if the *battery* refuses it, and a refused day
has no backtest answer for a drift to hide behind.

## 0.4 M21 AND M22 ARE CLOSED AS REVIEW_13B WROTE THEM

Verified on BOSCHLTD 2021-05-20, SHREECEM 2020-03-19 and HDFCBANK 2026-06-10, in the shipped
screener and in the parity harness. A `qty == 0` day is no-trade-consumed with the four numbers
in `detail`, no trigger alert, and the same `PHASE_REFUSED / qty=0` on both sides of the parity
comparison. A `None` whole-day battery is refused **by name**, and a recording really does supply
the battery the lake lacks — the 18-of-18 recording round trip is genuine.

## 0.5 CREDENTIALS, TRIPWIRE, HYGIENE

No credential reaches any byte of any outcome — sent, dry-run, refused, failed, summary-sent,
summary-dry-run, summary-failed — including `repr`, the recording, the dashboard HTML and the
exception text. **B392's dropped `__cause__` holds**: `raise TelegramError(...) from None` was
attacked with a `requests` exception carrying the token in its URL, and the token is absent from
the raised error and unreachable from any code path that prints. The no-order tripwire really
covers `telegram_sink.py` (proved by planting `placeOrder` in a copy and watching it go red).

Telegram attaches with **zero screener edits**: `live_screener.py` names Telegram only in prose
(5 comment/docstring hits), and the AST assertion at `tests/test_telegram_sink.py:80` correctly
checks Import/ImportFrom/Name/Attribute nodes only.

Hygiene is clean on every axis attacked: fixtures byte-frozen; **zero secrets**; **no AI
attribution**; perfect REVIEW_7 C1 compliance (all seven commits touching `src/` or `tests/`
carry `(unreviewed)`, all eight that do not, correctly omit it); trader pack, report and points
table are the **same git blobs** at both ends of the span; linear 15-commit chain;
`main == origin/main`; `db45998 == chunk13-pass`.

**Test census, re-derived by AST:** 1,709 functions at `db45998` → **1,742 at `fc99e2b`** (the
build's claim, exact) → **1,748 at HEAD** (after the fix's +6, exact); files under `tests/`
120 → 124 (exact). **Exactly five test names are gone and every one is an opposite-assertion
flip** of a defect pin (Q1, Q2, Q3, Q4 and the log-leak probe). No test weakened, skipped,
loosened or edited into agreement.

**No gate moved.** `fc99e2b` wraps `whole_day_from_source` in `try/except` inside
`full_day_gates`; the pre-existing `if minutes:` guard means a symbol whose source answered is
gated exactly as before, so only the previously-fatal exception path changed. Verdicts proved
identical on 895 real stored symbol-days. `GATE_DEFINITION` is correctly unbumped (B404 approved).

---

# PART 1 — BLOCKING FINDINGS (chunk-14 scope)

**B1 · Q3 is not closed** — `live_refresh.py:262-264`, called from `:713-715`.
Measured through the shipped CLI with the network fully stubbed and a scratch store:
`--mode live --day 2026-08-14 --refresh --allow-network --preflight-only` **added**
`cache_root/ca/nse_ca_2026-08-04_2026-08-14.json` and
`cache_root/instrument_master/OpenAPIScripMaster_2026-08-14.json`, and **changed**
`data_root/daily_store/ledger.parquet`. On the operator's real `config.yaml`, `cache_root` is
`C:/Users/chinm/acumen-data/cache` — *inside* `data_root` — so those files land in the
snapshot-protected tree, and `<cache_root>/ca/` does not exist there today, i.e. a real morning
**creates** it, and a new `nse_ca_<D-10>_<D>.json` accretes every morning thereafter. The fence
would have refused that very directory (proved: `fence_ca_cache(cache_dir=cache_root/'nse',
allow_network=True) → refreshed=False`). *Spec:* CLAUDE.md Q-18 layer 2.
`backtest.py:1713` claims "Every caller of this function is fenced, including one written next
year that forgets" — true only of callers routed through `build_factor_tables`.

**This finding was independently and accidentally corroborated during this review** — see PART 6.

**B2 · the certifying test asserts its name** — `tests/test_chunk14_carried_defects.py:559`,
with `docs/evidence/chunk14_verification_sweep.md` §2 bullet 3. The suite-level claim ("the suite
writes zero bytes under the stores") is **true and independently reproduced by this review**
(PART 5). The live-morning claim built on top of it is false. The correct statement is: *zero
writes by the test suite and by an offline `--refresh`; non-zero, by design and by defect, on a
networked live morning.*

**B3 · the documented live command dies after writing** — `run_screener.py:118` + `:164` against
`backtest.py:1858-1863`, with `live_screener.py:1907`. Mechanism confirmed by code and probe
(above). Net effect on a real morning: the stores are mutated, then the screener refuses to
trade. Unexercised because no test drives `--refresh`.

---

# PART 2 — HIGH (chunk-14 scope)

**H1 · the three-act gate is two acts.** `run_screener.py:142` is
`TelegramSink(live=bool(args.live_alerts and args.telegram))` — **no `args.mode` term.** Executed
through `main()`: `--day 2020-03-19 --symbols SHREECEM --telegram --live-alerts` (mode *defaults*
to replay, so merely forgetting `--mode live` suffices) put two real messages on the transport.
Message 1 verbatim: `[11:30] SHREECEM LONG  entry 740.95  SL 738.10  TP 749.50  qty 350   (POC
739.80, bias bullish)` — no date, no mode, no replay marker, and because a replay carries no
CONTEXT 4.7 disclosure, **not one byte distinguishes it on the phone from an alert about today**.
Five separate places assert the opposite: `telegram_sink.py:17-18`, `run_screener.py:16`,
`morning_runbook_stub.md:27`, decision **B393**, and the shipped test's own docstring at
`tests/test_telegram_sink.py:412-414` — which makes the three-act claim and then asserts only two
flags. Zero tests pin mode against telegram.

**H2 · the end-of-day summary reports an empty day after a resume.** `run_screener.py:246` builds
the summary from `collected.alerts` — the alerts delivered *in this process*. A resumed morning
re-delivers nothing (the restored dedup set correctly suppresses them), so the one summary of a
crashed-and-resumed day says `no alerts today -- the screener ran the whole session and nothing
fired` **while `alerts.jsonl` in the same recording holds armed 11:15, trigger 11:30, exit
11:45**. Reproduced three ways: mid-day crash, summary-send failure then restart (B401's own
documented "a restart still owes the trader his summary" path), and dry-run-then-live. This
defeats **B402's** stated purpose exactly — the message exists so a silent phone is never
ambiguous between "no signal" and "the tool has stopped", and on the one morning that ambiguity
is real it asserts the wrong one. `recording.alerts()` holds the whole day and
`_end_of_day_summary` already has the recording, so the correct list is one call away.
`tests/test_telegram_sink.py:555-601` masks it by passing the *same* alerts tuple to both calls,
which is precisely what the CLI does not do.

**H3 · the M21 fix opened a phase-regression hole.** `live_screener.py:1266-1267` and
`:1328-1330`: `_consumed_unsizable` returns its `SymbolState` **directly instead of through
`self._monotonic`**, making it the only transition in the screener that can walk backwards along
`PHASE_RANK`. Measured on BOSCHLTD 2021-05-20 with real lake bars and two ordinary late candles
(CONTEXT 4.4's normal case — no vendor revision): at 13:30 qty = 1 and the trader is sent
`[13:30] BOSCHLTD LONG entry 15,569.90 SL 14,580.00 TP 18,539.60 qty 1`; at 13:45 the late bars
land, qty → 0, and the state becomes a numberless `refused` row — **no alert, no
`ALERT_FAILURE`, no `phase-regression-refused` record, 0 of each**. The position is unmanaged and
15:15 will not square it off. That is verbatim the sentence `_alerts_for:1414-1422` exists to
shout for REVIEW_13 M5. Wrapping the return in `self._monotonic(..., previous)` produces 8
regression events and keeps the position on screen.

**H4 · Q1's vouch can be satisfied by a FALSE age.** `live_screener.py:714-715`: `data_age`
short-circuits `PHASE_REFUSED` to `(False, 0)`, so the one alert kind that names prices out of a
refused state — the "refused while a position is open" FAILURE alert — is stamped `stale=False,
data_behind_minutes=0` however old its last bar is, and `unvouched_price` accepts it. Measured: a
feed frozen at 11:29 yields, at 15:00, a failure alert carrying entry/stop/target/qty with
`last_bar_stamp=11:29` and `data_behind_minutes=0` — a true gap of **211 minutes** — forwarded,
`telegram.refused == []`. **A missing stamp is caught by the predicate; a false one is not.**
Mitigated on the phone (the failure message text carries no number), but the harm is to the
payload, the recording and the certified predicate.

**H5 · the parity harness cannot judge the LIVE posture.** `parity.py:241` with
`live_screener.py:1951`. `gates = {} if live else full_day_gates(...)`, so in live posture
`run_live`'s `gates = screener.gates.get(symbol)` is None, `live_final` stays None, and
`trails_equal` (`parity.py:480-483`) is **False for every day the backtester has a signal**.
Measured on 8 oracle-passing live-posture days: judged 8, matched 0, mismatched 8, each with
exactly one named mismatch — the trail line — while forcing the live half's own evaluation shows
its trail is byte-identical. **Had the chunk-14 sample judged one live-posture day, the published
"ZERO mismatches" headline would have read "1 mismatched".** It fails *safe* (it invents a
mismatch, it cannot hide one), which is why this is HIGH and not blocking.

**H6 · M15 — a false GREEN over an unverified morning.** `live_refresh.py:530-532`: a symbol that
alerted but whose candle file is absent gets no verdict, and the headline then asserts it alerted
zero times: `0/0 symbol-day(s) pass the FULL battery, 0 alerted, 0 alerted-then-refused` while
`alerts.jsonl` holds three alerts. The dry-run week's debrief reads that as "yesterday checked
out".

**H7 · M16 — "the oracle has not spoken" is reported as "the oracle REFUSES".**
`live_refresh.py:424` + `:578`: an absent bhavcopy row fails gate 1P with `no-raw-daily-row`, and
every alerted symbol is named in a loud "treat them as withdrawn" headline, while
`oracle_available` and the NOT-VERIFIED branch that exist for this case are dead code. Over five
dry-run days this withdraws real, correct alerts and trains the trader to ignore the one line
that must never be ignored.

**H8 · M4 — a full TRIGGER can reach the phone after the close.** `close_day`'s 15:30 poll is an
ordinary sweep, so a feed that heals after 15:29 publishes, for the first time, a trigger with
all four numbers to the screen, the bell and Telegram. Measured message: `[15:30] SYNTH LONG
entry 2,001.00 SL 1,999.00 TP 2,007.00 qty 500` with `!! STALE 240m BEHIND`. REVIEW_13's
"recording JSONL only" is no longer true at HEAD, because chunk 14 attached a phone to that
sink tuple. No *new* trade is created from post-15:29 bars (`in_session_bars` drops them), so
this is a disclosure/annunciation defect, not a strategy deviation.

---

# PART 3 — THE HARNESS'S OWN FIDELITY (MEDIUM, chunk-14 scope)

The parity answer is right; several of the harness's comparisons are weaker than the report
implies, and a reviewer relying on them would be misled about *what was checked*.

* **`parity.py:468` — `bias` and `bias_rule` are a self-comparison.** The backtest side is
  evaluated as `pipeline.evaluate(symbol, day, bias=bias, ...)` where `bias` is the **live
  screener's own bias**, and `backtest_fields` then reads `stock_day.bias`. Two of the five
  DAY_FIELDS can never differ. (The answer is still right — this review's hand derivation
  confirmed the bias independently — but the harness does not check it.)
* **`parity.py:464` — the boundary grid is taken from the live half's own output**, so
  `compare()`'s "boundary count: live=N backtest=M" guard can never fire.
* **`parity.py:186-187` — `PHASE_SKIPPED` normalisation invents and masks differences.**
  `_phase_from_numbers` has no ARMED or TRIGGERED branch, so a skipped boundary on an armed day
  reports `waiting`.
* **`parity.py:230-231` — `run_live` reads the alert sink unfiltered by symbol**, so a screener
  holding more than one symbol false-mismatches every symbol.
* **`parity.py:309` — the square-off visibility gate is load-bearing on 30 real ledger days and
  pinned by nothing**: deleting it changes no test and no row of the committed sample.
* **`parity.py:494` — the transition-trail comparison has no negative control**: replacing
  `transitions_equal=trails_equal` with `True` leaves the suite green.
* **`parity.py:509-517` — a DISCLOSED day's mismatch list is dropped from the headline** (only
  `reason` and `live_alerts` survive). Benign today; it is the shape that would hide a real drift
  behind an oracle refusal.
* **`parity.py:450-458`** — a symbol-day the harness could not compare *at all* is filed under
  the same "disclosed" bucket as a genuine oracle refusal.
* **`live_screener.py:1831-1834`** — when the lake holds the day, a recording's own bytes are
  **never** gated (`full_day_gates` consults the source only `if not minutes`), which weakens the
  recording-round-trip claim.
* **`parity.py` has zero callers in `src/` and `scripts/`** — the only decision-level comparator
  is not wired into any shipped path, and the morning-after job verifies DATA, never a DECISION.
  This matters directly for chunk 15, whose acceptance test is decision-level.

Also MEDIUM: `_deliver` stamps `correction=True` / `supersedes=[...]` but **no surface renders
either** — a corrected alert reaches the phone as a second, visually identical message with
nothing saying the first is void, leaving the trader holding two live entries on one symbol at
two prices; chunk 14 added a **fourth** unguarded participant (the only one doing network I/O) to
the sink loop that has no `try/except`, widening M19's surface; `deliver()` and
`send_end_of_day()` catch `Exception`, not `BaseException`; the default recording root is
**inside `data_root`**, so every ordinary run writes into the snapshot-protected tree; the CA
note reaches the terminal only, not the manifest, the recording or the dashboard, so REVIEW_13B
Q3's disclosure half is also half-closed; and both `SPEC_VERSION` "pins" compare the constant to
a hard-coded literal, so they pin the constant and not the law — a tautology that cannot catch
the defect it was written for.

---

# PART 4 — CARRIED-MAJOR TRIAGE FOR CHUNK 15

All seven are **still live at HEAD**.

| # | verdict |
|---|---|
| **M19** | **BLOCKS THE DRY-RUN WEEK.** Measured: a 10-symbol live morning with ONE poisoned symbol (a vendor reply carrying an in-session candle stamped on the previous trading day — `_poll` applies no date filter and `in_session_bars` filters only on TIME) raises `PocError` at the FIRST boundary and **the exception escapes `run_screener.main` entirely**. Result: **0 of 18 sweeps**, `sweeps_done == []`, 4 of 30 alerts, six symbols never evaluated once all day, 10 of 10 in a wrong phase, empty banner, **`dashboard.html` never written**, recording ending on a dangling `sweep-opened`. Poisoning from 12:00 gives 3 of 18 sweeps and no `close_day`, which by the code's own measurement flips the day to REFUSED in the next morning's verification. **A restart cannot recover it** — the poison is deterministic and `restore()` resumes into the same raise. One symbol does not lose one boundary; it loses the morning. Against plan.md chunk-15's "zero unhandled errors across 5 sessions", this is disqualifying. *Remedy:* wrap the `_evaluate` call at `live_screener.py:951` (and the sink loop at `:1575`) in a per-symbol `try/except` that records, banners and continues — CONTEXT 4.4's skip-and-continue discipline, which is already implemented on the fetch side at `:1001`. |
| **M15** | **BLOCKS.** A false GREEN over a morning that was never verified (H6). |
| **M16** | **BLOCKS.** Correct alerts loudly withdrawn as oracle-refused (H7). |
| **M4** | **CHUNK-15 SCOPE**, upgraded in consequence by chunk 14. No new trade is created from post-15:29 bars, so no money decision changes; but a trigger now reaches the *phone* after the close. *Remedy:* one flag on `close_day`'s sweep suppressing delivery. |
| **M13** | **CHUNK-15 SCOPE.** One-shot, yesterday-only, `--refresh`-gated verification: a skipped pre-open loses the loud case permanently and nothing reports the gap. Needs a `--verify <day>` flag and a scan for unverified recordings before the week starts. |
| **M14** | **CHUNK-15 SCOPE.** Only `live_recordings[-1]` is verified while `open_session` actively instructs the operator to create a second recording mid-day. |
| **M12** | **CHUNK-15 SCOPE.** Three font families and a type pair outside DESIGN.md, still present. Cosmetic; does not block a dry-run week. |
| **M25** | **CHUNK-15 SCOPE.** `_fifteen` still function-local-imports and calls `aggregate_15min` directly, so B328's recorded claim remains false as written. |

---

# PART 5 — THE STANDARD SWEEP

**Suite.** From a clean `git clone` at `e3c43fa`, run **alone**: **2,478 passed / 1 failed / 1
skipped** in 811.50s. The single failure is
`test_the_LIVE_mode_STARTS_on_a_day_the_daily_store_can_never_have_ingested`, and it is **not a
chunk-14 defect** — it is caused entirely by the machine-state contamination in PART 6. Proven
read-only, not assumed:

```
max(attempted) WITH the 11 error rows   : 2026-08-13
max(attempted) WITHOUT them             : 2026-07-30
AS-IS (contaminated)  -> CalendarError: ... 3 date(s) never attempted
                         (first: 2026-07-31), 11 unsettled
CLEANED (11 filtered) -> derivation OK
```

The test takes `max(attempted)` as its range end; the injected rows drag it across dates the
store never attempted, and Q-3 safeguard 1 correctly refuses. **On a clean store the reading is
2,479 / 0 / 1, exactly as the chunk claims.** An earlier bracketed run also failed a *different*
test on a `MemoryError`; that was resource contention from this review's own concurrency and the
test passes in isolation in 22.47s. Neither failure is chunk 14's.

**Zero store writes by the suite — CONFIRMED.** Bracketing the suite-alone run with a whole-store
metadata fingerprint plus a content hash of the ledger:

```
before  files 22186  metadata c2629dac…  ledger sha 0f1d4546…  143871 bytes
after   files 22186  metadata c2629dac…  ledger sha 0f1d4546…  143871 bytes
```

Byte-identical. **B396's claim holds** for the property it actually measured.

**Fixtures** byte-frozen. **Secrets:** none, anywhere in the span, the tree, or `logs/`.
**AI attribution:** none. **Artefacts:** trader pack, backtest report and points table are the
same git blobs at `db45998` and `e3c43fa` (and at `chunk12-round4-pass`, except `trader_pack.md`,
which moved once inside *chunk 13's* span in commit `8080457` — a one-sentence prose change, no
figure moved). **Chain:** 15 commits, linear, no merges, `main == origin/main`.

---

# PART 6 — MACHINE STATE: A STORE WRITE MADE BY THIS REVIEW (operator action owed)

**Disclosed in full, because it is this review's own error.**

While attacking Q3, one of this review's probe agents ran the shipped CLI with `--refresh` against
a config that resolved to the **real** `data_root`. The network was hard-blocked at the socket
layer, so nothing was fetched from NSE — but `morning_refresh` recorded the stubbed download
failures into the operator's store. **`C:/Users/chinm/acumen-data/daily_store/ledger.parquet`
gained 11 `error` rows** for 2026-08-03..2026-08-13, stamped 19:48:10–19:48:27 on 14-Aug-2026,
each with reason `probe: the bhavcopy download is not stubbed (...)`. That string appears nowhere
in `src/` or `tests/`; the committed suite did not write it.

```
committed 13-Aug fingerprint : 22,186 files  4,109,782,853 bytes  content d97ba419…
now                          : 22,186 files  4,109,783,146 bytes  content 829119bf…
                               newest file: daily_store/ledger.parquet @ 2026-08-14T19:48:27
```

**This is itself corroboration of finding B1** — the defect was demonstrated accidentally, by the
very path B1 names, against a real store.

**Impact:** exactly one file; no candle data touched; no network reached; no date wrongly sealed
as a non-trading day. `error` is **not** in `calendar.py:660`'s terminal set, so
`settled_through` and the new Q2 gap-raise are unaffected, and all 11 dates lie past the backtest
span end — **no walked row, no gate and no published verdict moves.** The one observable
consequence is the suite failure in PART 5.

**Remedy — OPERATOR ONLY, and not taken here** (CLAUDE.md: store deletions are never session
work): restore `daily_store/ledger.parquet` from the verified 13-Aug snapshot, which predates the
write and which this review confirmed byte-faithful before the run. Success is checkable: the
whole-store content digest should return to `d97ba419…`. Re-running the daily backfill would also
replace the rows, since `record_outcome` replaces by date. **Do not overwrite the 13-Aug snapshot
with the current store** — Q-18 layer 3 is currently violated in that the change is newer than
the snapshot protecting against it.

Until the ledger is restored, **no reviewer can reproduce chunk 14's green suite claim on the
operator tree**, and any store-fingerprint bracket starts from a contaminated baseline.

---

# PART 7 — B379–B405, ONE LINE EACH

All 27 numbers are present, no gaps. 24 implemented exactly as written; **3 CHALLENGED**.

| # | judgment |
|---|---|
| B379 | **APPROVED.** `STALE_AFTER_MINUTES`/`data_age` moved into `live_screener`; exactly one definition, dashboard imports it. |
| B380 | **APPROVED.** Every alert carries a freshness stamp — verified by driving a real day and reading every payload. Weakened in one case by H4, which is a `data_age` defect, not a flaw in this decision. |
| B381 | **APPROVED.** One source for terminal, HTML and Telegram, read off the payload. |
| B382 | **APPROVED**, and now architect-ruled (Q-32(2)). Code and ruling agree. |
| B383 | **APPROVED.** DESIGN.md really has seven states; `qty==0` correctly maps to `refused` with the four numbers. Undermined by H3, which is a `_monotonic` defect, not this decision. |
| B384–B391 | **APPROVED.** Implemented as written. |
| B392 | **APPROVED on substance**; its rationale sentence ("the one place in this repository where dropping the cause is the safer choice") is factually false — other sites do the same — but the security property holds. |
| **B393** | **CHALLENGED.** Its stated rationale is "three deliberate acts", and the code has two (H1). The decision text is wrong about its own gating. |
| B394–B397 | **APPROVED.** B396's bracketed fingerprint is the stronger measurement and this review reproduced it. B397's honest reporting of an unexplained runtime difference is exactly the right instinct. |
| **B398** | **CHALLENGED on class.** A card line item deliberately not built is a plan.md §5 **Class-C** rescope, not a Class-B implementation choice. Recording it honestly was right; recording it in the wrong class is the one thing the protocol reserves for the architect. |
| B399 | **APPROVED.** "After `run_day()` returns" really is the close, and it keeps the AST property intact. |
| B400 | **APPROVED.** The summary correctly does not count itself. |
| **B401** | **CHALLENGED.** It cites "REVIEW_13 M23's ordering, applied" for an ordering that is M23's **inverse** — M23 ruled the mark must reach disk BEFORE the send; this sends first and marks after. The *choice* is defensible (losing a summary is worse than duplicating one) and the one-fsync window is honestly disclosed; **the citation is not**, and a future reader will take the wrong rule from it. Compounded by H2, which makes the resumed summary wrong in content as well. |
| B402 | **APPROVED in intent, DEFEATED in fact** by H2 — the empty-morning sentence is asserted on exactly the morning where it is false. |
| B403 | **APPROVED.** Marker counts read off `alert_states`, not recomputed. |
| B404 | **APPROVED.** `SPEC_VERSION` on the code commit, CONTEXT alone, `GATE_DEFINITION` correctly unbumped — no gate moved, proved on 895 real symbol-days. |
| B405 | **APPROVED.** REVIEW_7 C3 satisfied; the run is dry by construction and writes outside both stores. |

**CONTEXT v2.1a is correct.** `acd2abb` carries CONTEXT.md alone; the §10 erratum is factually
true (POC immutability is §3.3's and §4.7 carries no such clause); §3 is byte-unchanged across
the span. The `SPEC_VERSION = "v2.1"` vs law `v2.1a` gap is reconciled by the 2.1a row, though
the rule that lettered errata do not move the constant is nowhere written down (LOW).

**PROGRESS entries** conform to the plan.md §6 template field for field, and the STATUS line
matches what they claim.

---

# WHAT THE FIX SESSION OWES

1. **Fence the corporate-action pull in `live_refresh.refresh_corporate_actions`** (B1), and
   rewrite `test_Q3_a_LIVE_REFRESH_writes_ZERO_bytes_under_the_stores` to actually drive
   `morning_refresh` and fingerprint `data_root` **and** `cache_root` (B2).
2. **Make `--refresh` produce a calendar the screener accepts** (B3) — the published master must
   be composed with `live_trading_calendar`, not passed raw — and add the CLI test that would
   have caught it.
3. **Add `args.mode` to the Telegram gate**, or correct all five places that claim three acts
   (H1). One or the other, not both readings in the tree.
4. **Build the end-of-day summary from `recording.alerts()`**, not from this process's sink (H2).
5. **Route `_consumed_unsizable` through `_monotonic`** (H3).
6. **Stop `data_age` short-circuiting `PHASE_REFUSED` to a false zero** (H4).
7. **Give `run_live` the live half's own whole-day evaluation in live posture** (H5).
8. Correct **B393**, **B398** and **B401**'s recorded text.
9. Carry M19/M15/M16 to chunk 15 as **blocking the dry-run week**.

The parity claim itself — that the live screener and the ten-year backtester make the identical
decision — **is true, and this review could not falsify it in 96 runs or by hand on two days.**
What fails is the scaffolding around it: a fence that is never asked, a gate with one act
missing, a summary that lies about a resumed morning, and a certifying test that asserts its own
name.

**VERDICT: FAIL.** No tag.
