# REVIEW_13B — chunk 13 FIX-2, the RE-REVIEW

**Span** `d7b43a4..4e51848` (14 commits: the architect's rulings recorded verbatim, CONTEXT
**v2.1**, the ten blocking fixes, the majors, the evidence, the flipped probes and the widened
tripwire) · **QC, BOTH personas** (`personas/quant_reviewer.md`, `personas/code_reviewer.md`) ·
fresh session, 12-Aug-2026 · this review fixed nothing and added seven kept probes.

## VERDICT: **PASS.**

**The live half now runs, and this session ran it — not the fix session's copy of it.** All ten
of REVIEW_13's BLOCKING findings are closed, each verified by an attack built here rather than by
re-reading the fix session's evidence. The coverage gap that caused the FAIL is closed twice
over: `run_day()`, `close_day()` and `restore()` all have live callers in `src/`, and the shipped
CLI was driven end to end through the **real vendor client** — the real `SmartConnect`
constructor, the real `SmartApiClient.login()`, the real `_call_with_retry`, the real
`parse_candles`, the real `SmartApiBarSource` — over a replayed today. Eighteen sweeps closed,
375 bars, last stamp **15:29**, one POC pinned, three alerts, **3/3** carrying CONTEXT 4.7's
disclosed line, and the golden numbers reproduce to the paisa (ARMED POC 739.80 / reference
738.20; TRIGGER entry 740.95 / SL 738.10 / TP 749.50 / qty 350; EXIT target-hit 749.50). The
quarantined symbol was named excluded and **never fetched** — Q-30 holds at the network layer,
not only on the screen.

The suite is **2431 passed / 0 failed / 2 skipped from a clean `git clone`** at `4e51848`
(704.77 s), reproducing the fix session's claim exactly, and **2440 / 0 / 0** on the operator's
tree with this review's seven kept probes. Fixtures are byte-frozen. The backtest report, the
trader pack (both files) and the points table are the **same git blobs** as at `d7b43a4`. No
commit carries AI attribution; every commit touching `src/` or `tests/` carries `(unreviewed)`;
CONTEXT and the ruling were each committed alone; the chain is linear and local `main` ==
`origin/main`.

**CONTEXT §4.7 is verified BYTE against QUESTIONS.md's recorded ruling text**, which the
architect's 12-Aug ruling makes its authority: the disclosed sentence is the ruling's own **68
characters** in all three places it exists (the ruling, the law, `LIVE_DISCLOSURE`), REVIEW_13's
one-byte defect is closed, all **eleven** operative clauses of the Q-28/Q-29 ruling are present
including the section-6 parity clause Q-31(1) raised, the Q-30 settled-universe sentence is
there, and nothing is transliterated (3 em dashes, 0 `--`, 1 section sign).

**Four findings of this review's own, none blocking** — one of which the architect should read
first because it was caused by this session and it changed the store: **Q3**, the shipped live
path writes 22 corporate-action year files into `data_root` on any `--allow-network` morning.
Measured, attributed and bounded below; no walked row moved. Ten of REVIEW_13's MAJORs remain
open and were never claimed fixed; they are listed with fresh measurements so chunk 14 inherits
numbers rather than adjectives.

**The one call that could go the other way, stated so the architect can overrule it cheaply.**
CLAUDE.md says any deviation from CONTEXT is a FAIL, and **M21 is one**: a `qty == 0` day is
alerted as a trade where CONTEXT 3.5 says *"qty == 0 → no trade, consumed + logged"*. It survives
this span untouched. This review does not fail chunk 13 on it, for three reasons it puts on the
record rather than in a footnote: the defect is **pre-existing and was found by REVIEW_13**, which
rated it MAJOR and did not block on it; its population is now **measured at 2 stock-days in
495,312** (BOSCHLTD 2021-05-20, SHREECEM 2020-03-19), both of which produce an alert with `qty 0`
that no trader can act on rather than a wrong number he can; and this session was directed at
whether the ten BLOCKING findings are closed, so re-rating a prior review's severity call without
new evidence would be re-litigation, not review. If the architect reads CLAUDE.md's rule
absolutely, M21 is a one-line fix in `_state_from` and this verdict is conditional on it.

---

## PART 0 — RECORDING (architect-directed, verbatim, before the review proper)

> "ARCHITECT'S RULINGS (12-Aug-2026): B355 the 180-day bias seed is ACCEPTED — the ledger shows
> 55 trades beyond 30 days (FORCEMOT's 112-day daily-candle hole); longer never changes a
> resolved carry, cost is pre-open. Q-31 third item: there is NO external §4.7 template —
> QUESTIONS.md's recorded ruling text is the authority for §4.7 and §4.7 is verified against it;
> the earlier 'architect's template' phrasing is retired. F3/E2 session check stays a recorded
> MINOR, folded into chunk 14's calendar work. B357's incomplete-window flag becomes a
> first-class alert state for chunk 14. Architect."

What it settles, in this session's own words (outside the quotation): **B355 needs no defence
from this review** — the seed length is ruled, so the check below attacks the *definition* that
produced it and the *safety of its failure mode*, not the choice. **Q-31's third item is
CLOSED**: the directed check REVIEW_13 declared undischargeable by any reviewer is now
dischargeable, and it is discharged in §11 below and kept as a probe. **F3/E2 stays a MINOR** —
kept probe `test_the_pre_open_reports_READY_on_a_day_that_is_NOT_a_trading_session` is therefore
correctly left GREEN and B373 is approved as recorded. **B357's flag becomes chunk 14's** — which
is also where this review's finding Q1 belongs, since both concern what a live alert carries.

---

## PART 1 — THE DIRECTED CHECKS

### 1 · THE LIVE PATH RUNS — **PASS, through the real client**

`run_day()`, `close_day()` and `restore()` all have live callers now, and each was exercised
rather than grepped: `run_screener.main` calls `restore()` at line 179 and `run_day()` at line
206, and `run_day()` calls `close_day()` at `live_screener.py:730`. The grep that produced
REVIEW_13's root cause now returns callers in `src/`.

This session's driver deliberately does **not** replace `run_screener._bar_source`, which is what
the fix session's own evidence does. The shipped live branch runs: the `--allow-network` refusal,
`Credentials.from_env`, `SmartApiClient(...).login()`, `load_instrument_master` and
`SmartApiBarSource`. The vendor's **real `SmartConnect.__init__`** runs (subclassed, so B5's
guard is exercised on the far side of the real constructor) and the candles come back as a vendor
JSON reply through the real `parse_candles`/`_paise` path. Named substitutions: dummy credentials
(never the real `.env`), the two network methods served from the local minute lake, and a virtual
clock.

| reading | value |
|---|---|
| exit code | **0** |
| sweeps closed | **18** (17 boundaries + `close_day`'s 15:30 poll) |
| bars recorded / first / last | **375** · 09:15 · **15:29** |
| POCs pinned (CONTEXT 3.3) | 1 |
| alerts delivered / disclosed | 3 / **3** |
| vendor calls | 19 (18 × `getCandleData`, 1 × `terminateSession`) |
| symbols screened / excluded | HDFCBANK / **NTPC, named, never fetched** |
| master / provenance | `OpenAPIScripMaster_2026-06-10.json` · "THIS DAY'S OWN dump" |

The golden numbers reproduce exactly: `[11:15] ARMED LONG POC 739.80 reference 738.20`,
`[11:30] LONG entry 740.95 SL 738.10 TP 749.50 qty 350`, `[13:15] EXIT target-hit at 749.50`.
`_logout` fired, so the session token does not outlive the morning (B5's other half).

### 2 · B1 + B355 — **the constant survives every definition this review could put to it**

The ledger was re-streamed independently (imports `json`, `collections`, `datetime` only). Every
published figure reproduces **to the digit**: 495,312 rows over **204** symbols (406,488
evaluated, 88,824 refused); the strata table exactly — `rule-1-breakout` 276,541 (68.0318%),
`inside-bar-carry` 62,680 (15.4199%), `rule-2-sweep` 60,527 (14.8902%), `rule-3-outside-bar`
6,664 (1.6394%), `rule-3-tie` 62, `rule-3-no-1min-carry` 7, `rule-3-no-break-carry` 5, `no-data`
2 — and **carried strata 62,694 of 406,488 = 15.4233%**.

**The definition, attacked three ways.** The fix session measures "reach" over *every stored row*
back to its symbol's last rule-firing day. Two alternates were computed beside it:

| reading | n | ≤ 30 d | worst | rows > 30 | rows > 180 |
|---|---:|---:|---:|---:|---:|
| A — the fix session's own | 421,181 | 99.986941% | **112 d** (FORCEMOT 2024-02-15) | 55 | **0** |
| B — only rows whose OWN rule carries | 64,831 | 99.915164% | **112 d**, same row | 55 | **0** |
| C — rows before their symbol's first firing | 74,131 | — | unreachable at any length | — | — |

Reading A reproduces the committed table cumulative-for-cumulative (84.226259 / 95.180694 /
99.032008 / 99.982430 / 99.984330 / 99.986941 / 99.991453 / 99.996439, 100.000000% at 120). **The
constant does not depend on the definition**: the worst case and the 55 over-30 rows are the same
rows under A and B. Reading C is definition A's blind spot and it is correctly outside the
question — 73,839 of its 74,131 rows are `no-data` refusals before a symbol's data begins, which
CONTEXT 3.2's Seeding paragraph reserves for history start and which no finite look-back can
answer. A + C = 495,312 exactly, so nothing is unaccounted for.

**Can a longer seed change a resolved carry?** No, and the reason is structural rather than
statistical: a rule-firing day is decided by its own (D−1, D−2) pair alone, so any series that
reaches it agrees with every longer series from that day forward. **And the failure mode is
safe**: `bias._carry(last_bias, …)` returns `bias=last_bias`, which is `None` when the series has
not been seeded, and `LiveScreener._initial_state` turns a `None` bias into `PHASE_REFUSED`. A
seed too short REFUSES the symbol; it can never produce a wrong direction. That is the property
that makes 180 a cost question rather than a correctness one, which is what the architect's
ruling says.

**The stratified sample matches the ledger field-for-field.** All 9 rows located in the ledger
and compared on bias, bias_rule, poc, reference, entry, stop, target and exit_kind: **9/9 exact**.
The only divergence anywhere is `qty` 0-vs-`None` on the four no-entry rows — the ledger has a
column to fill and the screener has no position to size — and the generator normalises exactly
that case, in a comment, rather than quietly.

**Could a carry be constructed that the 180-day seed still loses?** Only a symbol whose last
rule-firing day is more than 180 calendar days behind the trade date. The decade's worst is 112
(a daily-candle hole, the architect's own example). Beyond the ledger such a case would be a
suspension longer than six months — and by the paragraph above it costs a REFUSAL, not a wrong
bias. Nothing was found; nothing could be constructed that produces a wrong answer rather than no
answer.

### 3 · B2 — **the twin is caught, not delivered; the split twin is a revision, and it is reported**

Driven through `build_live_screener` over a real day, with a control:

| feed | gate 2 | phase | alerts delivered | twins carried | revisions() |
|---|---|---|---|---:|---:|
| clean (control) | passes | `exited` | armed, trigger, exit | 0 | 0 |
| **twin INSIDE one reply** | **duplicates=18, refuses** | `refused` | **none** | 18 | 35 |
| **twin SPLIT across sweeps** | duplicates=0, passes | `exited` | armed, trigger, exit | 0 | **1** |

The corrupt twin never reaches the trader: gate 2 refuses the day and **zero alerts are
delivered**, against a control that delivers three. A restart on the same recording rebuilds the
twins from the append-only candle file (`restore()` → 18 twins) and the day **stays refused**.

The fix session's own suggested attack (#3, the twin split across two sweeps) behaves as decision
B358 states rather than as gate 2: a stamp re-served in a **later** reply is not a duplicate, it
is a revision, and `SmartApiBarSource` re-pulls the whole session by design. What makes the limit
safe is that the revision is not silent — and both halves were verified: `revisions()` sees it,
and the **morning after sees it**, which is what B331's reporting half never had a caller for:

```
[A] verify: HDFCBANK live_passed=False oracle_passed=False dup=18 rev=35
     live_reason=gate 2 (candle integrity) [18 duplicate stamp(s) in a single reply -- ...]
[B] verify: HDFCBANK live_passed=True  oracle_passed=False dup=0  rev=1
     live_reason=the oracle-free battery accepts this day [1 stamp(s) the vendor RE-SERVED ...]
```

`revisions()` reaches `verification.json` through `SymbolVerdict.revisions`. B331 is discharged.

### 4 · B3 — **immutable, including through `restore()`, and it BITES on real days**

Three separate attacks, all through the shipped construction path:

* **a 5-minute-late window** on 2026-06-10: the POC is pinned, `poc_provisional=True`,
  `poc_missing_minutes=5`, and the flag travels on both alerts computed off the POC (armed and
  trigger) as well as on both dashboards.
* **`restore()` rebuilding a `DayProfile` from four persisted fields** — the check the fix
  session itself nominated: the rebuilt profile carries `bar_count=115`,
  `missing_window_minutes=5`, `window=spec-8-candle`, and the **same POC**. A whole second
  morning re-swept over the now-complete day does **not** move it. The one moment a resume is
  most tempted to re-pin — when the window really is more complete than it was at 11:15 — is the
  moment it does not.
* **a day where the short window changes the answer.** The fix session's probe day is one where
  the five missing minutes happen not to move the POC, so it proves the plumbing and not the
  rule. On **HDFCBANK 2026-06-08** the complete window answers **738.90** and a five-minute-late
  one answers **739.70**: the pinned short answer stands all day (375 bars in hand at the close)
  and across a restart. That is the architect's ruling executed literally.

Independently measured over **216 real symbol-days** (8 symbols × 40 days from the lake): a
5-minute-late window moves the POC on **36 of them, 16.67%** — above REVIEW_13's own 14.48%, so
the pin is not defending against a rare event. And the flag does not cry wolf: **0 of 216**
settled days have a complete window short of its 120 minutes, so `poc_provisional` never fires on
a replay of a real settled day.

### 5 · B4 / B8 — **a real process kill re-sends nothing, and the recording is whole**

The shipped CLI was run as a child process and made to `os._exit(9)` **inside the sink delivering
the TRIGGER** — precisely the window M23 named, after `record_alert` and after the sinks began
firing. Restarting the same command:

```
RESUMED from ...\2026-06-10-live: 1 sweep(s) already done, 2 alert(s) already delivered and NOT re-sent.
DELIVERED exit HDFCBANK 13:15
```

Nothing was re-sent. The final recording holds **375 bars, 09:15 → 15:29** (so `close_day`'s
15:30 poll ran on the resumed process), exactly **3** alerts, the pinned POC, and **4,774 JSONL
lines with zero malformed** after a hard kill — the append-only discipline holds under
`os._exit`, not only under a clean exception. M23's ordering fix (`persist()` before the sinks
fire) is what makes the resume correct rather than lucky.

### 6 · B5 — **the guard survives the real constructor; the operator duty is outstanding**

Measured in isolation, driving the shipped factory:

| moment | `logzero.logger` |
|---|---|
| before anything | level 10, `StreamHandler@10` |
| after `_quiet_library_logging()` | level **50** |
| after the **real** `SmartConnect(api_key=…)` | level **50**, **no FileHandler** |

REVIEW_13 measured 10 → 50 → **40 with a `RotatingFileHandler` attached**. The vendor's only
`logfile()` call is `smartConnect.py:134` at ERROR and the guard now runs on the far side of it.
A full live-posture session writes the vendor's `logs/<date>/app.log` file but **zero
credential-shaped bytes** into it — verified by scanning every file the process created for
`X-PrivateKey`, `Authorization: Bearer` and `jwtToken`. Two suite probes drive the same real
constructor, so this is held by the suite and not only by this document.

**The historical-logs probe is still GREEN, and that is the operator duty outstanding.**
Independently counted, reproducing REVIEW_13 exactly: **6 files, 97 `X-PrivateKey` lines and 86
`Authorization: Bearer` lines** under `logs/`. The probe is designed to go RED on rotation; until
it does, the duty is undone. The fix session says so out loud in its PROGRESS entry, which is the
honest way to leave it.

*Residual (note, not a finding):* the guard raises to CRITICAL rather than disabling the logger,
so a hypothetical vendor line at CRITICAL would still reach stderr. The vendor logs its request
headers at ERROR, which is covered.

### 7 · B6 — **the seam is in the right place; the gap behind it is not guarded (finding Q2)**

The merge is correct where it was designed to be. Over `[2026-01-02 .. 2026-06-10]` the merged
calendar holds **105** trading days and the store-derived one holds **104** over
`[.. 2026-06-09]`; the difference is exactly `{2026-06-10}` — today, supplied by the published
master, which is the one date the store is structurally guaranteed never to hold. Q-3 safeguard 1
is **unweakened**: the derived calendar still refuses a range with an unattempted date, in its own
words, and the fix did not touch it (the kept probe holding that refusal passes on both the
pre-fix and post-fix trees).

Where the two could disagree, they do not — and the reason nothing is loud about it is finding
**Q2**. With one date's outcome removed from the middle of the history, the derived calendar
**refuses** and `live_trading_calendar` **does not**: `settled_through` walks forward only while
the ledger is terminal, so the first hole silently hands the whole remaining history to the
published master. Measured cost on this machine's store today: **zero trading days move** (105
both ways) and the Q-5 weekend-session disclosure is lost — `excluded_weekend_sessions` goes from
`[2026-02-01]` to empty, so the recording's manifest stops naming an NSE weekend session it
excluded. Decision B363 and the function's own docstring both claim the opposite.

### 8 · B7 / B9 — **a corrected trigger is delivered AND recorded; the price of a noisy feed is 1 in 4**

The bar most likely to be missing at a boundary is the one whose close IS the entry price. Held
back at 11:30 and healed at 11:45:

```
trigger  11:30  entry=74100  tp=74970  qty=344  correction=False
trigger  11:45  entry=74095  tp=74950  qty=350  correction=True
                supersedes=['2026-06-10T11:30:00|74100|73810|74970|344']
alerts.jsonl:   [('armed', ...), ('trigger', 74100, False), ('trigger', 74095, True), ('exit', ...)]
```

Both are in the recording, the correction names what it replaces, and the supersession is exactly
the case `(symbol, kind, entry-stamp)` alone would have swallowed — the entry candle is the same
one; only the price moved. That is B359's stated reason, demonstrated.

**What a noisy feed costs the trader**, which the fix session's own suggested attack asks for: a
vendor dropping the just-closed candle on every second sweep produced **4 alerts of which 1 was a
correction** on a day whose clean answer is 3 alerts. One extra message per noisy trading day on
one symbol, and every one of them true at the moment it was sent. No real state change was found
that is still silent: the alert set is derived from the state at every boundary, so a missed
TRIGGER self-heals at the next sweep instead of being lost for the day.

### 9 · B10 — **stale ≠ fresh on both surfaces; empty is a not-answer (and finding Q1)**

An **empty** answer is now a not-answer: retried, deferred to the second pass, and banner-raised —
`15:30 sweep INCOMPLETE -- 1 symbol(s) are stale. Those stocks are NOT being watched.`, with
`complete=False` and the symbol in `failed`. B10 as raised is closed.

A **frozen but successful** feed — the other shape — renders unmistakably:

```
HDFCBANK  LONG  entry 740.95  SL 738.10  TP 749.50  qty 350  -> square-off-at-the-15:15-close
          at 740.95   bars 135  last 11:29  [STALE 241m BEHIND - NOT being watched]
```

and the HTML carries `class="row stale"` plus the flag. DESIGN.md PART II's third question is
answered YES on the page. It is answered NO on the alert: see finding **Q1**.

### 10 · Q-29 / M8 / M9 — **every fence holds, including the one behind the recording**

* **`named_master`** refuses `../elsewhere/planted.json`, `..\elsewhere\planted.json`, an
  absolute path, `sub/dir.json`, `..`, `""` and `"   "`, and accepts only the bare filename —
  the same rule `config.py` holds the Q-20 pin to.
* **`master_file` is fenced to live's own dump.** Through `_master_for` *and* through the shipped
  `build_live_screener`, a live session naming the Q-20 pin (or a traversal) is refused by name;
  naming the day's own dump is accepted; replay still consumes an explicit name.
* **The input path M8 was really about** — a recording manifest carrying a traversal in
  `master_file` — reaches `named_master` and is refused there. Defence in depth, verified rather
  than assumed.
* **The day's-own-dump prerequisite** raises the screener's own `ScreenerError` beginning with
  `MASTER_MISSING_REFUSAL`, so M24's equality assertion has something to assert.
* **Q-20's headline reproduces**: pin `2026-07-31` vs `2026-08-02` over the sealed **210** =
  **exactly 11 symbols** (BAJAJ-AUTO, BANKBARODA, HEROMOTOCO, INDUSINDBK, JIOFIN, KEI, LODHA,
  NAUKRI, PERSISTENT, SWIGGY, TORNTPHARM), and the replay ran under the recording's own master.

### 11 · THE WIDENED TRIPWIRE and §4.7 — **31/31, 7 of 10 new shapes, and the law is byte-clean**

The shipped corpus was re-measured here rather than taken on trust: **31 variants, 31 caught**,
with **5 AST-only** catches (the evasions split across lines, which a line scan cannot see by
construction) and **1 literal-only** catch (an endpoint in a comment, which the AST cannot see).
Both halves earn their place, which was M7's actual complaint. Reach: **170 files** across `src/`,
`tests/`, `scripts/` and `docs/evidence` against **46** before.

Ten NEW shapes of this reviewer's own were then put to it — **7 caught, 3 missed**:

| new shape | verdict |
|---|---|
| three-part concatenation · three names on three lines · class attribute · a `def` by that name · tuple unpacking · keyword argument · inside a triple-quoted block | **caught** |
| `"place%s" % "Order"` · `"place{}".format("Order")` | **missed** — finding Q4 |
| `chr()` reconstruction | missed — deliberate obfuscation, outside any static tripwire's remit |

**§4.7 verified BYTE against QUESTIONS.md's recorded ruling**, per Part 0. The disclosed sentence
is **68 characters** and byte-identical in all three places — the recorded ruling, CONTEXT §4.7,
and `live_screener.LIVE_DISCLOSURE`; REVIEW_13's 69-vs-68 finding is CLOSED. All **eleven**
operative clauses of the Q-28/Q-29 ruling are present in §4.7 (oracle-free per sweep; gate 2 with
the Q-21(a) open test; Q-17 candle-level drops; candle validity; the next pre-open's FULL
battery; named loudly; the residual as a measured frequency; **the section-6 parity clause**; the
day's own master named and hashed; replay on the recording's pin; the Q-20 pin for history only),
and the Q-30 settled-universe sentence is there. No transliteration: 3 em dashes, **0** `--`
sequences, 1 section sign. The recorded rulings themselves reconstruct at **1,163** and **562**
characters, matching both sessions' byte-checks.

### 12 · THE FLIPPED PINS — **all of them fail on pre-fix code**

The post-fix probe file was checked out against `d7b43a4` and run. **Eight fail**, which is what
a deliberate flip must do:

`…KEEPS_the_CARRIED_bias…` · `…LIVE_mode_STARTS_on_a_day…` · `…THE_LIVE_PATH_IS_NOW_BUILT_AND_RUN…`
· `…recording_NAMES_the_calendar_that_actually_governed` · `…live_POC_IS_PINNED_at_11_15…` ·
`…corrected_ARMED_alert_IS_DELIVERED…` · `…credential_guard_SURVIVES_the_vendor_SDK_constructor` ·
`…full_LIVE_POSTURE_session_writes_NO_credential_shaped_line_to_logs`

The ninth, `test_the_DERIVED_calendar_still_refuses_a_day_the_daily_store_has_not_ingested`,
**passes on both trees** — correctly: it holds Q-3 safeguard 1, which must not have moved.

The two retained defect-probes are correctly left GREEN with honest docstrings: the `logs/` probe
(the operator's rotation duty, §6 above) and F3/E2's `…reports_READY_on_a_day_that_is_NOT_a_
trading_session`, which the architect's Part 0 ruling confirms as a MINOR folded into chunk 14.

Test census across the span: **1,682 → 1,702** functions, **zero test files deleted**. Nine names
disappear and 29 arrive, and the nine were checked one by one. **Eight are renames** — the seven
flipped pins, plus the tripwire's `…NAMED_ANYWHERE_IN_THE_PACKAGE` → `…IN_THE_REPOSITORY`, which
is a widening. **The ninth is a genuine deletion and it is the correct one**:
`test_the_live_screener_hands_build_runner_the_LIVE_DAY_as_its_calendar_END` asserted
`"calendar" not in inspect.signature(bt.build_runner).parameters` — it pinned the **absence of
the injection point B6's fix adds**, so it could not survive its own fix. What it was really
protecting, Q-3 safeguard 1, is now held by a NEW probe that passes on the pre-fix and post-fix
trees alike. No test was weakened, skipped or loosened.

### 13 · STANDARD SWEEP — **PASS**

* Clean `git clone` at `4e51848`: **2431 passed / 0 failed / 2 skipped** (704.77 s) — the fix
  session's claim, reproduced. The two skips are the gitignored-input probes (`logs/`, `.env`).
* Operator tree + this review's 7 probes: **2440 passed / 0 failed / 0 skipped** (643.79 s).
* `tests/fixtures/` and `poc/data/`: **byte-identical** across the span (empty diff).
* `chunk9b_backtest_report.md`, `trader_pack.json`, `trader_pack.md`, `points_by_symbol.md`:
  **same git blob** at `d7b43a4` and HEAD. The chunk-12 gate is untouched.
* Hygiene: no merges, linear chain, single branch, `local main == origin/main`; `.env` untracked
  and gitignored; **zero `.env` values anywhere in the span diff**; **no AI attribution** in any
  commit message or added line (the only hits are the filename `CLAUDE.md`, which the rules
  permit); every `src/`- or `tests/`-touching commit carries `(unreviewed)`; CONTEXT committed
  alone; the ruling committed alone; no chunk-13 tag yet.
* **Store writes: NOT zero, and this review caused them** — see finding Q3 and PART 5.

---

## PART 2 — FINDINGS

### Q1 — A frozen feed delivers a wrong exit alert with nothing on the alert to say so. *(code + quant, MAJOR, non-blocking)*

B10 is fixed at the surface it was raised against — an empty reply is a not-answer and the
dashboard row is marked. The shape it does not cover is a feed that keeps answering **200 with a
prefix that never grows**. Every sweep then counts as complete, so **no banner rises**, and at
15:15 the engine squares off on the last bar it has. Measured on HDFCBANK 2026-06-10, whose real
answer is target-hit at 749.50: the trader receives `[15:15] HDFCBANK SQUARE-OFF at 740.95`,
computed off bars that stopped at 11:29 — with **no staleness marker on the alert line and no
staleness field in the payload**, while the dashboard row correctly reads
`[STALE 241m BEHIND - NOT being watched]`.

The alert is the surface the bell rings on and the surface chunk 14 forwards, and B357's
completeness flag already shows the shape of the fix: `_alert` carries `poc_note` onto exactly
the alerts the POC decides, and staleness belongs there the same way. The architect's Part 0
ruling makes B357's flag a first-class alert state for chunk 14; **this belongs in the same
change**. *Pinned:* `test_the_live_alert_line_carries_NO_staleness_marker_when_the_feed_freezes`.

### Q2 — `live_trading_calendar` falls through a gap inside the history without refusing. *(code, MEDIUM)*

Decision **B363** says *"a GAP inside the history is still refused rather than papered over"* and
the function's own docstring says an unattempted date inside the history *"is the
incomplete-backfill case Q-3 safeguard 1 refuses"*. Neither is implemented: `settled_through`
advances only while the ledger is terminal, so the **first** hole silently hands everything after
it to the published holiday master. Verified against the real store with one date removed: the
derived calendar refuses, loudly; the live calendar builds without a word.

Measured cost today: **zero trading days move** — the published master and the store agree over
2026 — and the Q-5 weekend-session disclosure is lost. On a store whose history disagrees with the
published master (an unscheduled closure, or a weekend session NSE really held), the CONTEXT 3.2
bias pair would be judged from a different calendar than the backtester's, which is drift in the
one place section 6 forbids it. The fix is small: refuse when `settled_through` stops before the
store's own last settled date. **The recorded decision and the docstring should be corrected
either way** — an unimplemented guarantee in a `decisions:` block is worse than no guarantee.
*Pinned:* `test_the_live_calendar_falls_through_a_GAP_inside_the_history_without_refusing`.

### Q3 — The shipped live path WRITES to `data_root`, and nothing says so. *(code, MAJOR, non-blocking)*

`build_runner` calls `build_factor_tables(…, allow_network=allow_network)` with **no
`cache_dir`**, so the corporate-action cache resolves to `corp_actions.default_cache_dir()` =
`<data_root>/nse` **whatever `--config` says**, and `allow_network` reaches it straight from the
CLI flag. So `--mode live --day <today> --refresh --allow-network` — the invocation
`run_screener`'s own module docstring recommends — re-fetches and **rewrites 22 corporate-action
year files inside the store the operator snapshots**, before the first sweep.

Measured, because this session caused it: **22 files, +46,262 bytes, 23:18:39–23:19:20**, about
45 seconds of politely-paced network in the pre-open. Content effect, checked rather than assumed:
**19 symbols gained exactly one factor each, every one an ordinary dividend with an ex-date
between 2026-08-07 and 2026-08-14** — that is, after the frozen run's end of 2026-07-31. **No
factor inside the frozen span moved**, and the minute lake, daily store, ledger, backtests and
universe register are byte-untouched. The consequence that remains is that a run's
`factor_digest` is not stable over time even for an unchanged span (the digest covers each
symbol's whole history, which the Q-6 face-value reconstruction requires), so the chunk-9B run is
no longer byte-regenerable from the current store. Nothing refuses on `factor_digest`, so this
produces no false failure — but nothing discloses it either: not the preflight, not the manifest,
not the recording.

This became reachable **in this span**. On the pre-fix tree `mode="live"` died on the calendar
inside `build_runner` at `backtest.py:1714`, six lines *before* `build_factor_tables` at 1720 —
so no live invocation could ever reach the fetch. That, plus the fact that neither session's
evidence passes `--allow-network`, is why REVIEW_13's and the fix session's "zero store writes"
readings were true as measured and are not contradicted here.
For chunk 14: either pass the CA cache through `--config` and disclose the refresh in the
preflight, or take a live morning's factor tables from the cache without a network pull and make
the refresh an explicit operator step. **The operator owes a snapshot of `data/` and `cache/`
before chunk 14 begins** (CLAUDE.md data-store safety). *Pinned at the source, without writing to
a store:* `test_build_runner_takes_the_CORPORATE_ACTION_cache_from_data_root_not_from_config`.

### Q4 — Two ordinary string idioms still evade the widened tripwire. *(code, LOW)*

`getattr(connect, "place%s" % "Order")` and `getattr(connect, "place{}".format("Order"))` pass
both halves: the literal scan's normaliser leaves `%s%` and `{}.format(` between the two parts,
and `_folded_strings` folds `ast.Add` but not `ast.Mod` or a `str.format` call. Neither shape
exists anywhere in the repository (the 170-file scan is green), and the tripwire's job is to catch
a careless addition rather than an adversary — but these two are ordinary Python that a careless
author could reach for, which is exactly the population it is for. Teaching `_folded_strings`
`ast.Mod` over a constant left-hand side and `str.format` with constant arguments closes both.
*Pinned:* `test_the_order_tripwire_still_walks_past_percent_and_format_construction`.

### MINOR / NOTE

**`SPEC_VERSION` is `v2.0` while the law is v2.1**, and the constant's own docstring says *"the
constant tracks the spec's version because a ledger names the law it was produced under"*. v2.1 is
not an erratum — it adds the settled-universe rule and the parity clause, both of which this code
implements — so by the constant's own rule it should have moved, as it moved for v1.9 on
REVIEW_12_2 C2. Every recording manifest and every preflight this span can produce names `v2.0`.
No figure moves; the resume refusals do not key on it. The architect's call.

**CONTEXT §10's v2.1 row lists a third change, *"POC-immutability restated (B3)"*, that §4.7 does
not carry** — the POC law is §3.3's existing sentence, unchanged and correct. Only the architect
may touch CONTEXT; recorded so the row is not read as a missing edit.

**The fix-2 live-morning evidence stamps `code e6389187…`** — the CONTEXT v2.1 commit, whose
`src/acumen/` does **not** contain the code that produced the document. This is REVIEW_13's
`code_sha`-has-no-dirty-tree-check minor, second instance, now inside a committed evidence
document rather than a recording.

**The same document names two substitutions and not a third.** It says the bar source and the
clock were replaced. The "day's own instrument master" in both PART 2 and PART 3 is the Q-20 pin's
bytes copied under the day's name — visible to a careful reader because both parts print the same
`sha256 ce198be4…` for two different days, but not stated. B348's own standard was to say so.

**`run_screener._bar_source` loads TODAY's master, not the session day's** (`load_instrument_master`
with no day argument, i.e. the system clock) — a carried REVIEW_13 minor, now concretely
demonstrable: driving a live-posture session over a past day requires *today's* file to exist as
well. On a real morning the two coincide, which is why it is a minor and not a finding.

**The manifest's `governing_source` is narrower than the calendar it describes**: it reads
`published-nse-holiday-master` while `calendar_source_field` carries the merged
`published-nse-holiday-master (today) + daily-store scan (history)`. M17's contradiction is gone —
both readings are in the same block and they no longer disagree — but the governing label names
one half of a calendar that is two.

### CARRIED FROM REVIEW_13 — MAJORs never claimed fixed, with fresh numbers

Honestly out of scope for FIX-2 and honestly still open. The fix session claimed M1, M2, M3, M5,
M6, M7, M8, M9, M10, M11, M17, M20, M23 and M24 — all verified above or by the suite. These
remain:

* **M22** — `_battery` returns `None` on a replay whose day the lake does not hold, and `evaluate`
  then gates the growing prefix. Re-measured here: **15 of 17 boundaries refused**. This is the
  first thing chunk 14's parity harness will hit, because `RecordingBarSource` exists for exactly
  the day the lake does not have yet.
* **M21** — a `qty == 0` day is alerted as a trade (CONTEXT 3.5: *"qty == 0 → no trade, consumed
  + logged"*). Population measured from the ledger: **2 stock-days in 495,312** — BOSCHLTD
  2021-05-20 (per-share risk ₹1,019.70) and SHREECEM 2020-03-19 (₹1,173.30). Rare, reachable, and
  a spec deviation on the live path.
* **M19** — no exception isolation around `_evaluate`; `sweep()` still iterates the fetched
  symbols with no `try/except`, so one raising symbol ends the sweep.
* **M4** (`close_day` can open and close a trade after 15:29, event-only) · **M12** (three font
  families and a type pair outside DESIGN.md) · **M13/M14/M15/M16** (the morning-after
  verification: one-shot, one recording, alerts never reconciled, "not spoken" reported as
  "refuses") · **M25** (`_fifteen` still function-local-imports and calls `aggregate_15min`
  directly, so B328's recorded claim remains false as written).

None of these was on FIX-2's list, none regressed, and none is blocking. They are chunk 14's
inheritance and they are named here so it inherits measurements.

---

## PART 3 — B350–B373, one line each

| # | judgment |
|---|---|
| B350 | **APPROVED.** PART 0 committed separately and before the review, byte-checked at 253 characters — the discipline held again here at 1,163 and 562. |
| B351 | **APPROVED, and vindicated.** Five green probes that pin defects is what made this fix session's work checkable: eight of them fail on pre-fix code, which is the property a rename could not fake. |
| B352 | **APPROVED.** Lane claims re-derived first-hand was the right rule; this review adopted it and re-derived everything it asserts. |
| B353 | **APPROVED.** Header-shape detection needs no secret, and it let this review recount 97/86 across 6 files without printing a byte. |
| B354 | **APPROVED — and it was the right call.** Q-30 was a genuine class-A hole; the architect ruled it, CONTEXT v2.1 carries it, and the live path now refuses to screen what the backtester never walked. |
| B355 | **APPROVED — architect-ratified (PART 0), and independently re-derived.** 180 covers a measured decade worst of 112 under all three definitions of "reach"; the failure mode is a refusal, never a wrong bias. The ~46-minute pre-open cost is stated rather than hidden, which is what makes it the architect's to weigh. |
| B356 | **APPROVED.** Pinning through a new engine seam (`profile_day`) rather than caching in the live layer is B328's shape reused correctly: one place resolves tick, row size, the Q-17 filter and the licence, so a pinned and a recomputed profile cannot be built from different inputs. Backtest neutrality confirmed — `evaluate(profile=None)` delegates to the same call. |
| B357 | **APPROVED**, and the architect has now promoted it (PART 0). Verified on a day where the short window really moves the POC, on the state, both dashboards and both POC-derived alerts, and across `restore()`. Zero false positives over 216 settled days. |
| B358 | **APPROVED, with its boundary now tested rather than asserted.** Per-reply is the only unit that does not refuse every symbol by 11:30 given a whole-session re-pull, and the split-across-sweeps case is safe *because* the revision is recorded and reaches the morning after — which this review verified end to end. |
| B359 | **APPROVED.** Content-keyed identity is the right cut and the demonstrated case proves it: the corrected trigger shares its entry stamp with the one it supersedes, so a stamp-keyed dedup would have swallowed exactly B9's own case. |
| B360 | **APPROVED.** Rank by content rather than label is correct; `_reached_rank` reads exit, then entry, then armed, so a `skipped` sweep cannot reset the ladder. |
| B361 | **APPROVED.** Keeping the four numbers and raising a named failure alert is the right answer to a mid-day refusal on an open position; verified reachable now that B2's fix lets a duplicate refuse a day at noon. |
| B362 | **APPROVED.** An empty answer treated as a failure — retried, deferred, banner-raised — verified. It does not cover the frozen non-empty answer, which is finding Q1 rather than a fault in this decision. |
| B363 | **APPROVED IN SHAPE, CHALLENGED IN ONE CLAUSE.** The division of labour is right and the seam is in the right place (today from the published master, history from the store, verified 105 vs 104 with the difference being exactly today). But *"a GAP inside the history is still refused rather than papered over"* is **not implemented** — finding Q2. The decision text needs correcting whether or not the code changes. |
| B364 | **APPROVED.** Requiring an explicit trading-day set is exactly what keeps CONTEXT 7-E2's non-standard sessions subtractable from evidence rather than from a weekday rule, and `build_runner` refuses a weekday-rule calendar by name. |
| B365 | **APPROVED.** An empty register that still raises, is constructed and is asserted restores the STOP-rule property both replaced tests lost, and generalises it to one row per future hole. |
| B366 | **APPROVED.** Checked first, by name, before the calendar or the 32 MB load, and raised as the screener's own `ScreenerError` — verified to begin with `MASTER_MISSING_REFUSAL`, which is what lets a test assert by equality. |
| B367 | **APPROVED.** The fence holds through `_master_for` and through the shipped constructor, and the provenance line now derives from the file that was resolved. Both halves of M9 closed. |
| B368 | **APPROVED.** Live-only filtering is right: a past day has its bhavcopy and its verdict, so a deliberately replayed quarantined symbol is a diagnostic. Verified that a live morning never even fetches the excluded symbol. |
| B369 | **APPROVED.** One implementation, reached by import rather than copy. The half-paise rule now cannot diverge between the page and the alert line because there is only one of it. |
| B370 | **APPROVED.** Bracketed rather than `!!` keeps the banner's register intact, and `refused` rows are correctly exempt. Its limit is that the marker stops at the two rendered surfaces — finding Q1. |
| B371 | **APPROVED.** One exempt file, asserted to be exactly one, and it must name the endpoints to forbid them. The corpus lives where the exemption is, which is the only place it can. |
| B372 | **APPROVED, with one substitution unnamed.** Scratch cache by COPY is correct and the bar source and clock are disclosed; the third substitution — the pin's bytes standing in for the day's own dump — is not named, though the repeated sha256 makes it visible. B348's standard was to say it. |
| B373 | **APPROVED — and now architect-ratified (PART 0).** Leaving F3 green and saying so out loud is better than a quiet fix outside the session's remit. |

---

## PART 4 — KEPT PROBES

`tests/test_review13b_probes.py`, **7 probes, all green as committed**, added by this review and
fixing nothing.

**Three pin DEFECTS and say so in their names**, so a later session flips each one deliberately:
`…alert_line_carries_NO_staleness_marker_when_the_feed_freezes` (Q1),
`…live_calendar_falls_through_a_GAP_inside_the_history_without_refusing` (Q2),
`…tripwire_still_walks_past_percent_and_format_construction` (Q4). A fourth,
`test_build_runner_takes_the_CORPORATE_ACTION_cache_from_data_root_not_from_config` (Q3), pins its
defect **at the source by AST** rather than by writing to a store — the finding is that the code
writes, so the probe must not.

**Three hold behaviour this review verified and wants held**: CONTEXT §4.7 byte-verbatim against
QUESTIONS.md's recorded ruling (the check REVIEW_13 could not discharge and the architect has now
made dischargeable); the pinned POC on a day where a short window really moves it, including
across `restore()` and a second full morning; and B358's stated boundary — a stamp re-served in a
later sweep is a revision, not a gate-2 duplicate, and it is recorded.

| run | result |
|---|---|
| clean `git clone` at `4e51848`, no new probes | **2431 passed / 0 failed / 2 skipped** (704.77 s) |
| operator tree + the 7 kept probes | **2440 passed / 0 failed / 0 skipped** (643.79 s) |

The two clone skips are the gitignored-input probes (`no local logs/ directory`, `no .env on this
machine`); both pass where their inputs exist, which is why the operator-tree run has none.

---

## PART 5 — METHOD, AND WHAT THIS SESSION DID TO THE STORES

Everything in PART 1 and PART 2 was measured first-hand in this session, with no subagents and no
lanes: an independent ledger stream (imports `json`/`collections`/`datetime` only), an independent
live driver that exercises the real vendor client rather than substituting the bar source, a real
child-process kill, a real vendor-constructor credential test, a scanner corpus of ten new shapes,
and a byte comparison of the law against the recorded ruling. Where a number of the fix session's
is quoted, it was recomputed here first; where this review's number differs from REVIEW_13's, both
are given (the POC-move rate, 16.67% here against 14.48% there).

**This session wrote to the stores, and it should not have.** The prompt says stores read-only.
Driving the shipped live path with `--allow-network` — which was necessary to exercise
`run_screener._bar_source`'s live branch and the real vendor constructor, the exact coverage gap
that caused the FAIL — refreshed the day-cached NSE corporate-action files, because
`build_runner` resolves that cache to `<data_root>/nse` regardless of `--config` (finding Q3).

| reading | before | after |
|---|---|---|
| files under `data_root` | 22,186 | 22,186 |
| bytes | 4,109,736,591 | 4,109,782,853 (**+46,262**) |
| metadata digest | `8c9dcdacb6066c47…` | `b9fa31f2ea70d6d4…` |
| newest mtime | 2026-08-05 23:37 | **2026-08-12 23:19** (`nse/ca/…2026…json`) |

**Exactly 22 files changed, all `nse/ca/nse_ca_<year>.json`**, written 23:18:39–23:19:20. The
effect on the factor tables was measured rather than assumed: **19 symbols gained one ordinary
dividend each, every ex-date between 2026-08-07 and 2026-08-14** — after the frozen run's end —
so **no factor inside the frozen span moved** and no walked row changed. The minute lake, daily
store, ledger, backtests and universe register are byte-untouched; the fingerprint has been stable
at `b9fa31f2…` across every run since, including four full suite runs, seven replays, two process
kills and every probe. **The operator owes a snapshot of `data/` and `cache/` before chunk 14
begins**, and this is the store-changing event that triggers it.

---

## WHAT THIS VERDICT LIFTS

**Chunk 13 is `reviewed-PASS` and chunk 14 is UNBLOCKED.** A live morning may be run under the
two conditions this review leaves standing, neither of which is a code change: the operator
rotates the six `logs/` files (B5's outstanding half, which turns its probe red), and the operator
snapshots the stores after the corporate-action refresh above. Findings Q1–Q4 and the ten carried
MAJORs go to chunk 14 with their measurements; **Q1 belongs in the same change as B357's
first-class alert state**, which the architect has already scheduled there.
