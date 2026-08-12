# chunk 13 FIX-2 -- the LIVE path, started on TODAY and run end to end

Run at 2026-08-12T21:45:20 from `docs/evidence/chunk13_fix2_live_morning.py`. READ-ONLY over the stores; the day's own instrument master and the published holiday master are COPIED into a scratch `cache_root` outside them.

## PART 1 -- the DERIVED calendar still refuses today, and that is correct

QUESTIONS.md Q-3 safeguard 1 -- *a download error is NEVER treated as a holiday* -- is
why the store-derived calendar refuses a range holding a date it has never attempted.
It must not weaken by one date. What B6 changed is that a live morning stopped asking
it a question only the published master can answer.

```
CalendarError: Refusing to derive a trading calendar from an incomplete ledger (2026-07-13..2026-08-12): 13 date(s) never attempted (first: 2026-07-31), 0 unsettled. QUESTIONS.md Q-3 safeguard 1: a download error is NEVER treated as a holiday, and (CONTEXT 4.6 v1.5 / Q-19) neither is a 'pending' date -- a 404 on a date too young for that answer to be final. Re-run the backfill over this range first.
```

## PART 2 -- `--mode live --day 2026-08-12 --preflight-only` (exit 0)

The date is TODAY, which the daily store has never attempted and, under Q-19's guard,
structurally never will. Before this fix the same command exited 1 with
*"the screener cannot start: CalendarError ... date(s) never attempted"*.

**Read the `biases resolved` line honestly.** This machine's daily store ends before
today (PART 1 names the first unattempted date), so today's CONTEXT 3.2 pair has no
candles and the bias shown is a CARRY across that gap -- the `no-data` branch R1-Q6
documents, reached only because the series is seeded 180 days back. On a real morning
the pre-open refresh tops the store up to the last COMPLETED trading day and the pair is
a real one. What PART 2 proves is that the morning STARTS, which is all B6 was about.

```
==============================================================================
CONTEXT 4.7 -- LIVE MODE. A live trading day has no bhavcopy oracle until evening, so this session runs the ORACLE-FREE battery per sweep: gate 2 (with the Q-21(a) open test), the Q-17 candle-level drops, and candle validity. Gates 1 and 1P are structurally INAPPLICABLE to same-day data -- what they detect is history being rewritten, and today cannot be rewritten during today. Every alert this session produces carries: 'live feed, not yet verified against the exchange's end-of-day record'. The NEXT pre-open runs the FULL battery over this day's recording against the published bhavcopy and reports both verdicts, naming loudly any day it alerted on that the oracle then refuses. Measured residual, as a BRACKET rather than a single number (B341, re-derived by REVIEW_13): 0.5229% of settled symbol-days (2,187/418,275 over the ten-year ledger) failed gate 1 alone; 2.5141% (10,516 days) failed an ORACLE-ONLY gate -- gate 1 or gate 1P, both inapplicable this morning; and the measurable ceiling, counting the 697 days whose gate-2 trigger the ledger does not name, is 2.6808%. So the frequency this morning accepts and discloses is 0.5229%-2.6808%, not 0.5229%. Section 6 parity is judged on oracle-passing days; a live-alerted day the oracle later refuses is that disclosed, bounded difference. This morning screens the SETTLED UNIVERSE ONLY (CONTEXT 4.7 / QUESTIONS.md Q-30, architect 08-Aug-2026): the symbols CONTEXT 4.6 quarantined are NOT screened and are named below, because the screener alerts on what the backtester validated. The instrument master is THIS DAY'S OWN dump (QUESTIONS.md Q-29), named and hashed into the recording. THIS TOOL PLACES NO ORDERS.
==============================================================================

==============================================================================
ACUMEN SCREENER PREFLIGHT   2026-08-12   mode=live
==============================================================================
spec                 v2.0   code e6389187c311c4155043c1b581404a249f27a169
instrument master    OpenAPIScripMaster_2026-08-12.json
                     sha256 ce198be44b44fc333540a19c3d6a7b4e5fa86ae81ef2c6798fd5bece7b29f5ab
                     THIS DAY'S OWN dump (CONTEXT 4.7 / Q-29 -- the trader's chart as of this morning)
row size             24
risk / cost (paise)  100000 / 10000
symbols              1 screened
biases resolved      1
bias series seeded   2026-02-13 (CONTEXT 3.2's carry needs history to carry from)
gate battery         ORACLE-FREE, per sweep (CONTEXT 4.7): gate 2 with the Q-21(a) open test, the Q-17 candle-level drops, candle validity. Gates 1 and 1P are structurally inapplicable to same-day data
calendar             published-nse-holiday-master governs; trading day = True, standard session = True
                     store-scan cross-check found 0 non-standard session(s)
boundaries           17 (11:15 POC pass, last 15:15)
alerts               DRY RUN (log only)   [live feed, not yet verified against the exchange's end-of-day record]
recording            C:\Users\chinm\AppData\Local\Temp\acumen-fix2-live-nw3i6ty4\today\rec\2026-08-12-live
==============================================================================
```

## PART 3 -- a whole live morning on a REPLAYED TODAY (exit 0)

```
==============================================================================
CONTEXT 4.7 -- LIVE MODE. A live trading day has no bhavcopy oracle until evening, so this session runs the ORACLE-FREE battery per sweep: gate 2 (with the Q-21(a) open test), the Q-17 candle-level drops, and candle validity. Gates 1 and 1P are structurally INAPPLICABLE to same-day data -- what they detect is history being rewritten, and today cannot be rewritten during today. Every alert this session produces carries: 'live feed, not yet verified against the exchange's end-of-day record'. The NEXT pre-open runs the FULL battery over this day's recording against the published bhavcopy and reports both verdicts, naming loudly any day it alerted on that the oracle then refuses. Measured residual, as a BRACKET rather than a single number (B341, re-derived by REVIEW_13): 0.5229% of settled symbol-days (2,187/418,275 over the ten-year ledger) failed gate 1 alone; 2.5141% (10,516 days) failed an ORACLE-ONLY gate -- gate 1 or gate 1P, both inapplicable this morning; and the measurable ceiling, counting the 697 days whose gate-2 trigger the ledger does not name, is 2.6808%. So the frequency this morning accepts and discloses is 0.5229%-2.6808%, not 0.5229%. Section 6 parity is judged on oracle-passing days; a live-alerted day the oracle later refuses is that disclosed, bounded difference. This morning screens the SETTLED UNIVERSE ONLY (CONTEXT 4.7 / QUESTIONS.md Q-30, architect 08-Aug-2026): the symbols CONTEXT 4.6 quarantined are NOT screened and are named below, because the screener alerts on what the backtester validated. The instrument master is THIS DAY'S OWN dump (QUESTIONS.md Q-29), named and hashed into the recording. THIS TOOL PLACES NO ORDERS.
==============================================================================

==============================================================================
ACUMEN SCREENER PREFLIGHT   2026-06-10   mode=live
==============================================================================
spec                 v2.0   code e6389187c311c4155043c1b581404a249f27a169
instrument master    OpenAPIScripMaster_2026-06-10.json
                     sha256 ce198be44b44fc333540a19c3d6a7b4e5fa86ae81ef2c6798fd5bece7b29f5ab
                     THIS DAY'S OWN dump (CONTEXT 4.7 / Q-29 -- the trader's chart as of this morning)
row size             24
risk / cost (paise)  100000 / 10000
symbols              1 screened
biases resolved      1
bias series seeded   2025-12-12 (CONTEXT 3.2's carry needs history to carry from)
gate battery         ORACLE-FREE, per sweep (CONTEXT 4.7): gate 2 with the Q-21(a) open test, the Q-17 candle-level drops, candle validity. Gates 1 and 1P are structurally inapplicable to same-day data
calendar             published-nse-holiday-master governs; trading day = True, standard session = True
                     store-scan cross-check found 0 non-standard session(s)
boundaries           17 (11:15 POC pass, last 15:15)
alerts               DRY RUN (log only)   [live feed, not yet verified against the exchange's end-of-day record]
recording            C:\Users\chinm\AppData\Local\Temp\acumen-fix2-live-nw3i6ty4\replayed\rec\2026-06-10-live
EXCLUDED             1 symbol(s) NOT screened -- the screener alerts on what the backtester validated (CONTEXT 4.7 / Q-30):
                     NTPC           quarantined (CONTEXT 4.6) -- gate 1P proves 1,850 of 2,433 stored days; the chunk-9B run walked none of them
==============================================================================

[11:15] HDFCBANK ARMED  LONG  POC 739.80  reference 738.20   [live feed, not yet verified against the exchange's end-of-day record]
[11:30] HDFCBANK LONG  entry 740.95  SL 738.10  TP 749.50  qty 350   (POC 739.80, bias bullish)   [live feed, not yet verified against the exchange's end-of-day record]

[13:15] HDFCBANK EXIT target-hit  at 749.50   [live feed, not yet verified against the exchange's end-of-day record]


================================================================================================
ACUMEN SCREENER   2026-06-10   15:30   DRY RUN (log only)
(live feed, not yet verified against the exchange's end-of-day record)
================================================================================================

exited  (1)  -- done for the day
------------------------------------------------------------------------------------------------
  HDFCBANK      LONG  entry      740.95  SL      738.10  TP      749.50  qty   350  -> target-hit at 749.50   bars 375  last 15:29

ALERTS (3)
------------------------------------------------------------------------------------------------
  [11:15] HDFCBANK ARMED  LONG  POC 739.80  reference 738.20   [live feed, not yet verified against the exchange's end-of-day record]
  [11:30] HDFCBANK LONG  entry 740.95  SL 738.10  TP 749.50  qty 350   (POC 739.80, bias bullish)   [live feed, not yet verified against the exchange's end-of-day record]
  [13:15] HDFCBANK EXIT target-hit  at 749.50   [live feed, not yet verified against the exchange's end-of-day record]


recording: C:\Users\chinm\AppData\Local\Temp\acumen-fix2-live-nw3i6ty4\replayed\rec\2026-06-10-live
dashboard: C:\Users\chinm\AppData\Local\Temp\acumen-fix2-live-nw3i6ty4\replayed\rec\2026-06-10-live\dashboard.html
```

### What the run produced

| reading | value |
|---|---|
| mode / posture | `live` / oracle-free per sweep |
| symbols SCREENED | HDFCBANK |
| symbols EXCLUDED (Q-30) | NTPC |
| instrument master | `OpenAPIScripMaster_2026-06-10.json` |
| master provenance | THIS DAY'S OWN dump (CONTEXT 4.7 / Q-29 -- the trader's chart as of this morning) |
| governing calendar | `published-nse-holiday-master` |
| bias series seeded from | 2025-12-12 |
| 1-minute bars recorded | 375 |
| FIRST / LAST stamp | 09:15 / 15:29 |
| sweeps closed | 18 (17 boundaries + the 15:30 close-out) |
| POCs pinned (CONTEXT 3.3) | 1 |
| alerts delivered | 3 |
| recording digest | `5bad4bf95f993006...` |

**B4 is closed by the LAST STAMP.** `close_day()`'s 15:30 poll is the reason the
recording reaches 15:29 rather than stopping at 15:14. Over
460 real July-2026 symbol-days REVIEW_13 measured that truncation flipping **22.05% of
oracle-passing days to REFUSED** the next morning -- so CONTEXT 4.7's loud banner would
have fired on roughly one alerted day in five, against a disclosed residual of 0.5229%.

### The alerts, as the trader receives them

```
[11:15] HDFCBANK     armed        {"bias": "bullish", "dry_run": true, "poc_paise": "73980", "reference_paise": 73820, "side": "long"}
[11:30] HDFCBANK     trigger      {"bias": "bullish", "dry_run": true, "entry_paise": 74095, "entry_stamp": "2026-06-10T11:30:00", "gap_entry": false, "poc_paise": "73980", "qty": 350, "risk_paise": 285, "side": "long", "stop_paise": 73810, "target_paise": 74950}
[13:15] HDFCBANK     exit         {"dry_run": true, "entry_paise": 74095, "exit_kind": "target-hit", "exit_paise": 74950, "qty": 350, "side": "long"}
```

Every one of them carries CONTEXT 4.7's disclosed line: *"live feed, not yet verified against the exchange's end-of-day record"* (3/3).

