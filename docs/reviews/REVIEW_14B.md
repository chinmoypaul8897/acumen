# REVIEW_14B — chunk 14, FIX-2 · QC RE-REVIEW, both personas

**Span:** `993d57a..fd2e2d4` (8 commits, linear, no merges).
**Against:** `docs/reviews/REVIEW_14.md`'s FAIL and its nine-item closing list.
**Personas:** `personas/quant_reviewer.md` + `personas/code_reviewer.md`.
**Law:** CONTEXT v2.1a. **Card:** plan.md chunk 14. **Rulings:** QUESTIONS.md Q-33 (15-Aug-2026)
and PART 0 below (15-Aug-2026, on FIX-2).
**This review fixed nothing.** It added three probe files — two evidence scripts and one kept
test module — their two committed outputs, and this document. No `src/` file, no test of anyone
else's, no fixture and no committed artefact was touched.

---

# PART 0 — THE ARCHITECT'S RULINGS ON FIX-2, VERBATIM

> "ARCHITECT'S RULINGS (15-Aug-2026, on FIX-2): B407 the fenced-CA-pull
> downgrade-to-cache-with-loud-disclosure is CONFIRMED (a live morning must start; the
> missing-cache-as-outage path recreates B3). B398 the chunk-14 card's end-of-day-summary line
> is MET; no rescope is owed — recorded by the architect, not a session. Architect."

Both rulings are executed below: B407 is judged APPROVED against the ruling rather than
re-litigated (PART 5), and B398's class correction is read in the light of the ruling (PART 3.3).

---

# VERDICT: **PASS**

REVIEW_14's FAIL is **LIFTED**. All three BLOCKING findings, all three architect-promoted
carried majors and all five chunk-14-scope HIGHs are closed, and every one was verified here by
an attack this session built rather than by re-reading the fix session's evidence. The parity
claim the chunk exists for — that the live screener and the ten-year backtester make the
identical decision — is unchanged and was reproduced independently: **15 days, 14 judged, 14
matched, 0 mismatched, 1 disclosed**, from a report that is byte-identical to the committed one
apart from its own timestamp.

**60 of 61 checks in this review's own attack script pass** (`docs/evidence/review14b_live_attacks.py`,
its output committed beside it). The one that does not is not a claim
the fix session made: it is a **residual** this re-review found by widening M19's own question
(PART 4, finding **R1**), it is out of reach of the shipped vendor bar source, and it is carried
to chunk 15 rather than held against chunk 14.

**The stores are byte-unmoved.** Content digest `d97ba419…` before this session's first command
and after its last, across two full suite runs, a scratch-copy `--refresh`, a 15-day parity
re-run and every probe in this document.

---

# PART 1 — STORE INTEGRITY, FIRST AND LAST

CLAUDE.md's newest rule is the one this very incident bought, so it is the one checked first.

**Fingerprint taken before any other command in this session**
(`docs/evidence/housekeeping_13aug_store_fingerprint.py`, read-only by construction):

```
root            : C:\Users\chinm\acumen-data
files           : 22186
bytes           : 4109782853
metadata_digest : dbea5660b7734f6a71edd5e99eac0159e53174ec431a1a7fb17c2bad5bf61423
content_digest  : d97ba4191339be543df9ee8a67f3a8c17aed629e0cc21e4be1d989a86dc1e089
newest_mtime    : 2026-08-12T23:19:20
newest_file     : nse/ca/nse_ca_2026-01-01_2026-12-31.json
```

**`d97ba419…` — the operator's restored 13-Aug state, confirmed from the machine.** The newest
file in the whole store predates REVIEW_14's own 19:48 2026-08-14 contamination, so the eleven
`error` rows are *gone* rather than buried under newer ones, and Q-18 layer 3 is no longer
violated. The FIX-2 session's `docs/evidence/chunk14_fix2_store_bracket.md` §0 said exactly
this; it is now independently true rather than relayed.

**Every mutation this review caused went to a COPY.** The one section that drives a mutating CLI
(`--refresh --allow-network`) runs against a copied `data_root` and `cache_root`
(`docs/evidence/review14b_q3_fence.py`), asserted to contain **0 symlinks or junctions** and to
be a disjoint tree. The real store was fingerprinted again as this session's last act; the
result is in PART 6.

---

# PART 2 — THE OWED FIXES, EACH ATTACKED

## 2.1 · B1 / B2 — the fence, on the path that matters *(REVIEW_14 BLOCKING)*

`docs/evidence/review14b_q3_fence.py`, one process, network stubbed at three layers
(`nse_http.fetch_json`, `fetch_binary`, `cached_json_fetch`) **and** at `socket.socket.connect`,
every outbound URL recorded.

**The fence is asked, and it downgrades.**

```
fence_ca_cache(cache_dir=<scratch cache_root>, allow_network=True,
               data_root=<scratch>, cache_root=<scratch>)
  -> may_network = False
     "corporate-action refresh FENCED: the cache lives inside the stores, which a session
      treats as READ-ONLY (CLAUDE.md data-store safety, Q-18 layer 2) ..."
control, a cache OUTSIDE both roots -> may_network = True, "refresh permitted"
```

**It is a downgrade, not a refusal — proved with a cache the fix session did not plant.** A
window cached **40 days** before the trade date, carrying a real bonus whose ex-date falls inside
the window (an empty payload could not show whether the cache was *read* or merely tolerated):

```
corporate actions : ok = True   fenced = True
                    events_total = 1   events_for_universe = 1
detail            : "... [read from the day-cache, NOT refreshed -- <fence reason>]"
```

**The endpoint was never asked.**

```
the CA endpoint : https://www.nseindia.com/api/corporates-corporateActions?index=equities
                  &from_date=31-05-2026&to_date=10-06-2026
attempted       : False
outbound attempts recorded : 1  -- and it is the instrument-master step, not this one
```

**Zero bytes moved, measured over EVERY file of BOTH roots** (path, size, `mtime_ns`, sha256,
before and after):

```
data_root  : 0 file(s) moved of 66
cache_root : 0 file(s) moved of 3
<cache_root>/ca contents : ['ca/nse_ca_2026-05-31_2026-06-10.json']   (the planted file, unmoved)
<cache_root>/ca touched? : False
```

That is the directory REVIEW_14 B1 measured a real morning **creating** and then accreting a
file into every day thereafter. On the operator's machine `<cache_root>` still holds nothing but
`instrument_master/` (two files) — verified directly — so `<cache_root>/ca/` does not exist, and
the factor tables every bias descends from continue to read `data_root/nse/` (45 files, the
corporate-action year files among them), which B407's rationale asserts and which is corroborated
by the fingerprint's own `newest_file`, `nse/ca/nse_ca_2026-01-01_2026-12-31.json`.

**B2's shape is gone.** The certifying test drives `morning_refresh` end to end and fingerprints
both roots; this review's independent probe does the same thing a different way and agrees. The
claim is no longer wider than the measurement.

## 2.2 · B408 / B409 — the two neighbours the fix found by driving the real path

**B408 — the one unguarded step.** An unreadable published master now leaves a REPORT:

```
returned calendar : None      report.ok : False      steps reported : 6  (none silently dropped)
  [FAIL] calendar (published NSE)      NseFetchError: Refusing to fetch ...holiday-master...
  [ok]   universe (F&O underlyings)    1 symbol(s) supplied by the operator, no pull
  [FAIL] daily store (bhavcopy top-up) NOT RUN: the published calendar step above failed, and ...
  [FAIL] corporate actions             NseFetchError: Refusing to fetch ...
  [FAIL] instrument master (TODAY's)   InstrumentMasterError: No instrument master cached ...
  [FAIL] verify yesterday (CONTEXT 4.7) NOT RUN: ... which day 'yesterday' was is a calendar question
```

A step silently absent from a report reads as a step that passed — M15's own shape, refused
before it can be made. The `None` calendar is reachable only with `report.ok` False, and
`run_screener.main` returns 1 on `not report.ok` before touching it, so the widened return type
cannot hand a caller a `None`.

**B409 — which store the top-up tops up.** Proved twice, the second time by driving the real
backfill:

```
argv handed to the backfill : ['--from','2026-07-27','--to','2026-08-06','--store','<scratch>']
step.figures['store']       : <scratch>
backfill_daily.main(--store <scratch>, --allow-network, network stubbed)
   files moved under the REAL daily_store : 0
```

This is the most valuable of the ten decisions, and it was found only because B3's CLI test drove
the real path for the first time. Unfixed, a session running against a copy would have written
into the original — the precise write CLAUDE.md's newest rule forbids.

## 2.3 · B3 — the runbook's own 08:45 command *(REVIEW_14 BLOCKING)*

Driven through `run_screener.main` on a scratch layout, with the command copied out of
`docs/morning_runbook_stub.md` §1:

```
python -m acumen.run_screener --mode live --day <TODAY> --refresh --allow-network --preflight-only
  exit                              : 0
  "the screener cannot start"       : absent
  "READY" / "NOT READY"             : READY / absent
  "ACUMEN SCREENER PREFLIGHT"       : printed -- the screener really started
  manifest calendar.governing_source: published-nse-holiday-master
  manifest calendar.is_trading_day  : True
  preflight corporate-actions line  : names the fence, as §2 of the runbook promises
```

The published master is COMPOSED through `live_trading_calendar` rather than handed raw to a
runner that refuses it, and the calendar the session RECORDS is still the one the refresh
cross-checked — REVIEW_13 M17's C5 duty is intact, which is the thing a careless fix would have
broken.

## 2.4 · H1 — the Telegram gate *(three acts, in code)*

**The review's own command, through `main()`, with the transport watched:**

```
--day 2026-06-10 --symbols HDFCBANK --telegram --live-alerts     (mode DEFAULTS to replay)
  exit 0 · 3 alerts produced · 0 messages on the transport
```

Not an empty morning: the alerts really were computed and recorded, and only the forwarding was
gated. The five-case table holds, and so does a sixth case nobody wrote down:

| mode | `--telegram` | `--live-alerts` | sends |
|---|---|---|---|
| live | yes | yes | **True** |
| live | yes | no | False |
| live | no | yes | False |
| replay | yes | yes | False |
| replay | yes | no | False |
| live | no | yes *(the sixth)* | False |

**A message a phone cannot misread.** The exact bytes a replayed 2020 trade now produces:

```
[2020-03-19 11:30] SHREECEM LONG  entry 740.95  SL 738.10  TP 749.50  qty 350   (POC 739.80, bias bullish)
[DRY RUN -- log only, nothing was sent to anyone else]
[REPLAY of a PAST day -- this is not a live alert and nothing about it is about today]
```

Against REVIEW_14's measurement of the same alert — `[11:30] SHREECEM LONG ...`, no date, no
mode, no marker. A live alert carries **neither** marker and still carries CONTEXT 4.7's
disclosed line; the end-of-day summary of a replayed day names itself a replay too.

**All five places that claim three acts now make the same claim**, and the one that said "Two
separate deliberate acts" no longer does: `src/acumen/telegram_sink.py`,
`src/acumen/run_screener.py`, `docs/morning_runbook_stub.md`, decision **B393** in `PROGRESS.md`
(original plus its marked correction) and `tests/test_telegram_sink.py` — each names `--mode
live`, `--telegram` and `--live-alerts`.

**The no-order tripwire really covers the new module.** `tests/test_live_safety.py` is 14/14
green on the shipped tree; planting `connect.placeOrder(params)` into
`src/acumen/telegram_sink.py` turns **2 tests red**
(`test_NO_ORDER_PLACEMENT_ENDPOINT_IS_NAMED_ANYWHERE_IN_THE_REPOSITORY` and
`test_the_broker_connection_is_only_ever_asked_for_candles_or_a_session`); reverting restores
14/14.

## 2.5 · M19 — one poisoned symbol, poisoned this review's way

Ten real F&O names over one real session fanned out, **ITC** poisoned (not the fix session's
INFY) with a **NEXT-day stray stamp** — the mirror of their fixture, chosen after measuring
seven malformed shapes to find one that actually reaches the evaluation guard (PART 4):

```
sweeps completed        : 18   (sweeps_done = 18)
evaluated per sweep     : [9]          <- nine symbols at every one of the eighteen
unevaluated per sweep   : [('ITC',)]
dashboard.html written  : True
banner                  : "15:30 sweep INCOMPLETE -- 1 symbol(s) could NOT be evaluated: ITC.
                           Those stocks are NOT being watched."
evaluation-failed events: 18, each naming its own sweep (11:15 ... 15:30), symbol ITC, PocError
restart                 : restore() -> 18 sweeps again
```

Against REVIEW_14's measurement of the same construction: 0 of 18 sweeps, `sweeps_done == []`,
no banner, `dashboard.html` never written, the exception escaping `run_screener.main` entirely.
The nine healthy symbols are not marked skipped and all nine alerted.

**A raising sink costs only its own delivery.** A sink that raises `RuntimeError` inside
`_deliver`: the delivery still returns True, the sink *after* the broken one receives the alert,
and the miss is recorded by sink name with its exception type.

**One honest limit, recorded here because the fix's own prose invites the question:** a
stray-stamp poison is *permanent* for its symbol inside a session, because `merge_bars`
accumulates and never forgets a stamp it was served. The morning survives; that symbol does not
come back until a new recording. The fix claims per-boundary *recording granularity*, which is
true and verified (18 distinct sweep labels) — it does not claim per-boundary recovery, and it
should not be read as claiming it.

## 2.6 · H3 / M21 — BOSCHLTD 2021-05-20, re-derived before the screener was asked

The eight events were derived **by hand from the raw minute store**, importing nothing from the
live layer, and only then measured:

```
HAND DERIVATION
  entry candle 13:15..13:29, 15 one-minute bars
  entry (13:29 close)                  : 1556990 paise   (Rs 15,569.90)
  candle low WITHOUT the two late bars  : 1458000 paise   (Rs 14,580.00)
  candle low WITH them (the true low)   : 1455020 paise   (Rs 14,550.20)
  risk without / with                   :   98990 -> qty 1   |   101970 -> qty 0
  boundaries in a session               : 18   (11:15..15:15 plus close_day's 15:30)
  boundaries AFTER the 13:30 entry      : 8    <- the regressions a consumed re-read must produce

MEASURED
  trigger alerts = 1 at 13:30, qty 1, entry 1556990 / stop 1458000
  final state    = triggered, entry 1556990, qty 1
  phase-regression-refused events = 8, each was='triggered' proposed='refused'
```

Eight, from two independent directions. The position stays on screen and 15:15 will square it
off; before the fix it became a numberless `refused` row with no alert, no `ALERT_FAILURE` and no
regression record.

**The ordinary qty-0 day is unmoved — checked to the byte, in both trees.** The same replay was
run in a clean clone at `993d57a` and at HEAD, and the resulting alert compared field by field:

```
993d57a : phase=refused  refusal='qty 0 -- no trade, consumed (CONTEXT 3.5)'  qty=0
          entry/stop/target = null   alerts=['armed']   qty-zero-unsizable events=1
          phase-regression-refused events = 0     alerts.jsonl = 366 bytes
HEAD    : ...every one of those fields identical, detail string identical by sha256...
                                                  alerts.jsonl = 383 bytes

diff of the day's ONE alert, 993d57a -> HEAD:
    12a13
    >   "mode": "settled",
```

**One added field, and it is B411's deliberate stamp** — the posture that every alert on every
day now carries so a phone can never read a replay as today. The *decision* is byte-identical:
CONTEXT 3.5's "no trade, consumed + logged", which is REVIEW_13 M21 and must not move, did not
move.

The mechanism was checked for the one thing that would have made the fix a no-op:
`_consumed_unsizable`'s state carries **no** `entry_paise` (those fields are passed separately by
`_entered`), so `_reached_rank`'s new `REFUSAL_QTY_ZERO` branch is genuinely reached rather than
short-circuited by the `entry_paise` test above it. `_monotonic` admits equal ranks (`now >=
was`), so ARMED → consumed still passes and only TRIGGERED/IN-TRADE/EXITED → consumed regresses.

## 2.7 · H4 / Q1 — a stamp that cannot lie

```
a feed frozen at 11:29, read at 15:00  -> data_age = (stale=True, behind=211)
                                          the review's own 211 minutes, exactly
an unrefused state, same numbers        -> (True, 211)   -- unchanged by the fix
unvouched_price(stale=False, behind=211)-> "the payload stamps this price FRESH while its own
                                            recorded age is 211 minute(s) behind the boundary
                                            -- a stamp that contradicts itself vouches for nothing"
TelegramSink.deliver(that alert)        -> 0 sent, 1 refused
a MARKED stale price (stale=True + MARKER_STALE + stale_note) -> travels, 1 sent, 0 refused
an age exactly at the clamp             -> NOT called a lie
```

**The risk this fix could have created does not materialise.** Making `data_age` honest for
refused states could have caused the one alert kind that names prices out of a refused state —
the "manage it by hand" FAILURE alert — to be *refused by the sink* and never reach the phone.
It is not: `_alert_payload` attaches `MARKER_STALE` and `stale_note` from the same `data_age`
call that produced the number, so the marker travels with the age and the alert still goes,
correctly labelled. Driven through the sink, not reasoned about.

## 2.8 · H2 — the summary after a resume

Alerts written into the recording by one process; the summary built by a second that delivered
nothing:

```
ACUMEN -- END OF DAY   2026-06-10
1 symbol(s) alerted:
  HDFCBANK  armed 11:15, trigger 11:30, exit 11:45
telegram: 0 sent, 0 refused (unvouched price), 0 failed
markers: 0 stale, 0 provisional POC
(live feed, not yet verified against the exchange's end-of-day record)
```

Against REVIEW_14's measurement: *"no alerts today — the screener ran the whole session and
nothing fired"*, over that same recording. **An actually-empty morning still says so**
(`SUMMARY_NO_ALERTS`), which is B402's own purpose and the half a careless fix would have lost.
The summary is still sent once per recording — a second attempt against the same recording sends
nothing and says why.

## 2.9 · M15 / M16 — what "verified" is allowed to mean, on both surfaces

```
M15  an alerted symbol with NO candle file
     -> IN the verdict list, alerted=('armed','exit','trigger'), verified=False
     -> headline: "NOT VERIFIED -- 1 LIVE-ALERTED symbol-day(s) could NOT be judged -- HDFCBANK.
                   Their alerts are NOT withdrawn and NOT confirmed ..."
     -> "0 alerted" absent; the row is marked NOT-VERIFIED

M16  a SILENT oracle (a daily store with no row for the day), over a REAL recording of a REAL
     morning written by the shipped screener
     -> verified=False, refused_after_alert=False
     -> reason names "THE ORACLE HAS NOT SPOKEN"; "treat them as withdrawn" absent
     -> the same recording against the REAL oracle: verified=True, and the headline reads
        "1/1 symbol-day(s) pass the FULL battery, 1 alerted, 0 alerted-then-refused."
```

**Oracle-silent versus oracle-refuses, reported distinctly:**

```
SILENT  : "2026-06-10: NOT VERIFIED -- 1 LIVE-ALERTED symbol-day(s) could NOT be judged ..."
REFUSES : "2026-06-10: THE EXCHANGE'S RECORD REFUSES 1 LIVE-ALERTED SYMBOL-DAY(S) -- ...
           treat them as withdrawn."
```

— and on the row too: the silent case carries `NOT-VERIFIED` and the `THE ORACLE HAS NOT SPOKEN`
reason, the refusing case carries `REFUSED-AFTER-ALERT` and its gate's own reason.

**Both dashboards.** TEXT: an unjudged alerted day is prefixed `!!`, a passing day is not. HTML:
an unjudged alerted day renders in `<div class="banner" role="alert">`, a passing day in
`<div class="row quiet">`, and the passing day carries no `role="alert"` at all.

*Recorded so a later reader is not surprised:* M15 (no candles) and M16 (no bhavcopy row) share
a **headline** — both are "could NOT be judged", which is correct, since neither has been
verified either way. They are separated on the **row**, by reason, and `render()` prints that
reason for every unverified verdict. This is a presentation choice, not a conflation.

## 2.10 · H5 — the harness can judge the posture the tool runs in

```
mode="live" -> screener.gates == {}          (CONTEXT 4.7: a live morning has no settled battery)
parity_for_screener(...)                      judged=True  transitions_equal=True  matched=True
                                              mismatches=[]
```

Against REVIEW_14's measurement of 8 oracle-passing live-posture days: judged 8, matched 0,
mismatched 8, each with exactly one invented mismatch. The input side is deliberately unchanged —
`gates = {} if live else full_day_gates(...)` is still there and is still correct.

---

# PART 3 — THE PINS AND THE CITATIONS

## 3.1 · The five flipped pins FAIL on the reviewed tip

HEAD's `tests/test_review14_probes.py` was copied into a clean clone checked out at **993d57a**
— the tree REVIEW_14 failed — and run there:

```
FAILED test_FLIPPED_B3_the_calendar_refresh_supplies_is_COMPOSED_not_handed_on_raw
FAILED test_FLIPPED_B3_a_test_in_this_repository_DOES_drive_refresh_through_the_CLI
FAILED test_FLIPPED_H1_the_telegram_gate_NAMES_the_mode
FAILED test_FLIPPED_the_three_act_claim_is_TRUE_in_every_place_it_is_made
FAILED test_FLIPPED_H5_run_live_HAS_a_live_posture_path
5 failed, 8 deselected
```

At HEAD the same file is **13 passed**. Five pins, five real flips: each fails on the defect and
passes on the fix, which is what makes the fix checkable rather than merely claimed. The three
DEFECT pins deliberately NOT flipped are correctly not flipped — B3 half one pins a permanent
property of `TradingCalendar.from_holidays` rather than a defect, and PART 3's two
self-comparison probes belong to chunk 15.

## 3.2 · The census: nothing was deleted, weakened or edited into agreement

Re-derived by AST over both trees:

```
993d57a : 1760 test functions in 94 files
HEAD    : 1778 test functions in 95 files      (+18 net)
names gone   : 6 -- and every one is a RENAME
   5 defect pins  test_DEFECT_*  ->  test_FLIPPED_*
   1              ..._sends_only_on_TWO  ->  ..._sends_only_on_THREE
names added  : 24 (the 6 renamed counterparts + 18 new)
```

The two edits inside `tests/test_telegram_sink.py` were read line by line: both follow behaviour
the fix changed (the message now carries its date; the summary now comes from the recording) and
both are **strengthenings** — the summary test now writes its alerts where the CLI writes them
instead of handing the same tuple to both calls, which is precisely what let the resumed-morning
defect live under a green test.

## 3.3 · The three corrected citations read right

None of the three was rewritten in place; each original sentence stands with a marked correction
appended under it, so the record of what was believed at the time survives.

* **B393** — the rationale was false as recorded (three acts claimed, two in code). It is
  corrected to the gate as it now is, and the decision was made **true rather than softened**.
  Correct as written.
* **B398** — corrected from Class B to plan.md §5 **Class C**, with the reasoning that a card
  rescope is architect-only. **The architect's 15-Aug ruling (PART 0) supersedes the open half of
  this:** the card's end-of-day-summary line is MET and no rescope is owed. The correction and the
  ruling are compatible — the correction is about the *route a session took in August 14's
  session*, the ruling is about the *state of the card now* — and the correction already says so
  ("It ended well ... but the route was the session's to take and it took the wrong one").
  Nothing further is owed.
* **B401** — corrected: it cited "REVIEW_13 M23's ordering, applied" for M23's **inverse**. The
  correction states the inversion plainly, keeps the choice (losing a summary is worse than
  duplicating one), and names why the two messages fail in opposite directions. Correct as
  written; the code is unchanged, as it should be.

---

# PART 4 — WHAT THIS RE-REVIEW FOUND THAT THE FIX DID NOT CLOSE

## R1 · MAJOR (chunk-15 scope) — the isolation stops where `_poll`'s guard stops

M19's remedy was implemented **exactly as REVIEW_14 prescribed it** — the `_evaluate` call and
the sink loop — and it closes the failure REVIEW_14 measured. Widening the question shows the
prescription itself was narrower than the property.

`_poll` wraps **only** `self.source.fetch(...)` (`live_screener.py:1055-1066`). The four
statements that follow it inside the same method — `merge_bars` (`:1071`), `duplicate_stamps`
(`:1076`), `recording.record_bars` (`:1088`) and `recording.record_fetch` (`:1089`) — are outside
both guards. A bar that survives the fetch and dies in that block still ends the sweep, and the
morning, in exactly the shape M19 describes.

A census of seven malformed one-minute bars, each served for one symbol of one screener and
driven through `run_day`:

| shape | outcome |
|---|---|
| NEXT-day stray stamp | **CONTAINED** by the new guard (`PocError`) |
| `high < low` | handled by the gates — no exception at all |
| negative volume | handled by the gates — no exception at all |
| sub-minute stamp | handled by the gates — no exception at all |
| **tz-AWARE stamp** | **ESCAPES `run_day`** — `TypeError` at `merge_bars` (`live_source.py:218`) |
| **`close_paise = None`** | **ESCAPES `run_day`** — `TypeError` at `record_bars` (`live_recording.py:270`) |
| **`volume = None`** | **ESCAPES `run_day`** — `TypeError` at `record_bars` |

**Why this is not blocking, stated as precisely as the finding itself.** From the shipped vendor
source these shapes cannot arrive unguarded: `smartapi_client.parse_candles` verifies the +05:30
offset and **drops** the tzinfo, `_paise` refuses a price that is not a whole number of paise,
and both raise `SmartApiError` from *inside* `SmartApiBarSource.fetch` — which is the call the
existing guard already wraps. `SmartApiBarSource.fetch` additionally filters
`bar.stamp.date() == day`, which means the fix session's own previous-day fixture is likewise
unreachable from the real vendor. So R1 is reachable only from a non-vendor `BarSource`, or from
a per-file I/O failure in `record_bars` — a locked or unwritable candle file for one symbol at
11:30 on a Windows laptop, which would take the whole morning down. That last case is real, and
it is why this is MAJOR rather than a note.

*Remedy for chunk 15:* extend the existing `_poll` guard to cover the merge-and-record block, or
wrap the per-symbol body of `sweep`'s fetch loop, with the same record-banner-continue discipline
`_evaluation_failed` already implements.

## LOW notes — recorded, none blocking, none owed before the dry-run week

* **L1 — the resumed summary's two numbers describe two different things.** The alert list is now
  the day's (correct, H2) while `summary()`'s `sent / refused / failed` counts only *this*
  process, so a resumed morning reads "1 symbol(s) alerted: … / telegram: 0 sent". Each number is
  right about its own subject and the labels say which is which, but they can be read as
  contradicting each other. The alternative — counting deliveries this process did not make —
  would be worse.
* **L2 — `posture_markers` treats a payload with no `mode` key as live.** An alert recorded before
  this fix and replayed later carries no REPLAY marker. Backwards compatibility was chosen over
  loudness; the trade date still travels, which is the part that disambiguates.
* **L3 — `unvouched_price` rule 3 needs the number to be an `int`.** A payload carrying `stale`
  without `data_behind_minutes` slips all three rules. Unreachable from `_alert_payload`, which
  always sets both together.
* **L4 — B407's blind branch catches bare `Exception`.** A programming error inside the puller
  would also read as "no cached window". It fires only when the fence has downgraded a pull the
  operator asked for, and the detail names the exception type, so it is disclosed rather than
  hidden.

---

# PART 5 — B406 – B415, ONE LINE EACH

All ten numbers are present in `PROGRESS.md`, no gaps.

| # | judgment |
|---|---|
| **B406** | **APPROVED.** The fence is judged against the roots the JOB runs under. Verified both ways: a scratch-copy run is fenced by its own scratch roots, and a cache outside both roots is permitted. This is what makes CLAUDE.md's new rule enforceable rather than aspirational. |
| **B407** | **APPROVED, and architect-CONFIRMED** (PART 0). Independently exercised: with no readable cached window the step reports `ok=True`, `events_total=None`, an `unreadable` figure naming the exception, and a detail that says THIS REPORT IS BLIND. The rationale is corroborated on the machine — `<cache_root>/` holds nothing but two instrument masters, so `<cache_root>/ca/` does not exist, while the factor tables' cache `data_root/nse/` holds 45 files, so the bias is genuinely unaffected. An operator who asked for OFFLINE still gets his failure. See L4 for the one caveat. |
| **B408** | **APPROVED.** Six steps reported, the calendar step guarded, and the two dependants say **NOT RUN by name** rather than vanishing. A silently absent step reads as a passing one — M15's shape, refused before it can be made. |
| **B409** | **APPROVED, and the most valuable of the ten.** The top-up now names the store it was handed. Verified by capturing the argv AND by driving the real backfill against a scratch store: 0 files moved under the real `daily_store`. Found only because B3's CLI test drove the real path for the first time — which is the argument for that test, made by the test itself. |
| **B410** | **APPROVED.** The gate is a named function, so the thing a reader checks and the thing a test asserts are one object. Six cases driven through `parse_args` + `telegram_is_live`, all six correct. |
| **B411** | **APPROVED.** The trade date travels always; `DRY_RUN_MARKER` and `REPLAY_MARKER` are read off the payload's own `dry_run` and `mode`, so a recording replayed months later still says what it said. A live alert is the only posture producing neither. See L2. |
| **B412** | **APPROVED.** An evaluation that raises marks the symbol `skipped` with its OWN detail naming the boundary and the exception; the banner NAMES it; the reason is on disk per symbol per boundary (18 distinct sweep labels measured). *"Missed its data window"* would have been a lie about a symbol whose data arrived. |
| **B413** | **APPROVED,** and checked for the one thing that would have made it a no-op: the qty-0 state carries no `entry_paise`, so the new branch is genuinely reached. ARMED → consumed passes on equal rank; TRIGGERED → consumed regresses and is recorded. `PHASE_RANK`'s published values are unchanged. |
| **B414** | **APPROVED.** `data_age` is a measurement for every state. The failure mode this could have created — a now-stale refused-state FAILURE alert being refused by the sink and never reaching the phone — does not occur, because the marker is attached from the same call that produces the number. Driven through the sink, not reasoned about. |
| **B415** | **APPROVED.** The store-touching tests build a COPY. Verified independently: this review's own scratch worlds contain **0** symlinks or junctions, and the real store is byte-unmoved across everything run here. |

---

# PART 6 — THE STANDARD SWEEP

**Suite, from a clean `git clone` at `fd2e2d4`, run ALONE:**

```
2510 passed, 1 skipped, 0 failed   in 617.88s
```

Exactly the fix session's claim. The one skip is the `.env`-input probe
(`tests/test_review13_probes.py:698`), which a clone must skip and the operator's tree must run.

**Suite, in the operator's own tree:**

```
2511 passed, 0 skipped, 0 failed   in 621.70s
```

Exactly the fix session's second claim, and the one-test difference is that same `.env` probe.
This review's own **14 kept probes** (`tests/test_review14b_probes.py`) are additive and green in
2.83s — store-free by construction, so the next session's suite is that count plus fourteen.

**Zero store writes, bracketed.** The whole-store fingerprint before this session's first command
and after its last — spanning two full suite runs, a scratch-copy `--refresh --allow-network`, a
15-day parity re-run, the tripwire experiment and every probe in this document:

```
before  files 22186  bytes 4109782853  metadata dbea5660...  content d97ba419...
                     newest 2026-08-12T23:19:20  nse/ca/nse_ca_2026-01-01_2026-12-31.json
after   files 22186  bytes 4109782853  metadata dbea5660...  content d97ba419...
                     newest 2026-08-12T23:19:20  nse/ca/nse_ca_2026-01-01_2026-12-31.json
```

**Every digit identical, metadata included** — not one file was created, removed, resized or
re-stamped, and `newest_mtime` did not move. The METADATA digest matching matters as much as the
content one here: a file rewritten with identical bytes would still move its `mtime_ns`, and it
did not.

**Parity, re-run independently** (`docs/evidence/chunk14_parity.py` to scratch outputs, so the
committed evidence was not overwritten): **15 days, 14 judged, 14 matched, 0 mismatched, 1
disclosed** — and the generated report is **byte-identical to the committed one** apart from its
own run timestamp and the output filename. Spot-checked in that run: the carried-bias witness
**ITC 2026-06-10** MATCH, the gap-entry day **ADANIENSOL 2026-05-08** MATCH, the qty-zero day
**BOSCHLTD 2021-05-20** MATCH, and **ADANIPORTS 2026-02-06** correctly DISCLOSED rather than
counted. The one difference in the machine-readable sample is on that disclosed day, which gains
one further *correct* mismatch line ("the live day's trail differs from the backtester's") —
H5's fix working, on a day that is disclosed and not judged either way. No verdict and no
headline moves.

**Engine purity.** `bias.py`, `poc.py`, `signals.py`, `simulate.py`, `bias_engine.py` and
`signal_engine.py` are the **same git blobs at `db45998` and at HEAD**. `backtest.py` moved
inside chunk 14's build span (the fence) and is **byte-unchanged across the FIX-2 span**.
`project_boundaries()` is untouched.

**Fixtures** byte-frozen: 0 files under `tests/fixtures/` or `poc/data/` moved in the span.
**Artefacts:** `chunk9b_backtest_report.md`, `points_by_symbol.md`, `trader_pack.md` and
`trader_pack.json` are the same git blobs at `db45998` and at HEAD; three of the four are also
identical to `chunk12-round4-pass` (the pack MD moved once inside *chunk 13's* span, as
REVIEW_14 already recorded). **CONTEXT.md and plan.md: untouched.**

**Chain.** 8 commits, linear, **0 merges**, `main == origin/main` at `fd2e2d4`,
`chunk13-pass == db45998`.

**REVIEW_7 C1: 8 of 8 correct.** Every commit touching `src/` or `tests/` carries `(unreviewed)`;
every commit that does not, correctly omits it — including the rulings commit, the citation
commit and the PROGRESS/STATUS commit.

**No AI attribution.** Five case-insensitive hits across the span's commit messages, and all five
are the filename `CLAUDE.md`, which CLAUDE.md's own git rule explicitly permits.

**Secrets: none.** Nothing credential-shaped in the span diff, the tracked tree or `logs/`. The
only real token on the machine is in `.env`, which is gitignored and untracked; it was never
read, printed or echoed by this review.

---

# PART 7 — CARRIED TO CHUNK 15

| # | status |
|---|---|
| **R1** | **NEW, MAJOR.** `_poll`'s guard stops before the merge-and-record block; three of seven malformed-bar shapes still end the morning. Out of reach of the shipped vendor source; reachable from another `BarSource` or a per-symbol file I/O failure. |
| **M4** | Chunk-15 scope, per the architect's 15-Aug ruling. A full TRIGGER can still reach the phone after the close. |
| **M12, M13, M14, M25** | Chunk-15 scope, per the same ruling. Untouched by FIX-2, as instructed. |
| PART 3 residue | REVIEW_14's harness-fidelity list: `bias`/`bias_rule` and the boundary grid are still self-comparisons (their two DEFECT pins are correctly still pinned), `parity.py` still has no caller in `src/`, and the corrected-alert `correction`/`supersedes` fields are still unrendered. All chunk-15 scope; none blocks the dry-run week. |

**Operator note:** no new snapshot is owed. The stores are unchanged by FIX-2 and unchanged by
this review, and the existing two generations still cover the current state.

---

# WHAT THIS RE-REVIEW COULD NOT FALSIFY

The parity claim, again: the live screener and the ten-year backtester make the identical
decision, boundary for boundary, on every judged day of the stratified sample. What REVIEW_14
failed was the scaffolding around that claim — a fence that was never asked, a documented command
that could not start, a gate with one act missing, a summary that lied about a resumed morning,
and a certifying test that asserted its own name. Every one of those is closed, and each was
closed by making the claim true rather than by softening it.

**VERDICT: PASS.** The FAIL is lifted. Chunk 14 is sealed: tag `chunk14-pass`.
