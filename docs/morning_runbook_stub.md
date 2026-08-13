# THE MORNING, ON ONE SCREEN -- operator card (chunk-14 STUB)

**This is the stub. Chunk 15 owns the full runbook** (the dry-run week, the debrief, the
incident log, latency stats). What is here is the one card an operator needs in front of him to
run a morning today, and nothing else. It is deliberately one screen: a card that scrolls is a
card nobody reads at 08:50.

**THIS TOOL PLACES NO ORDERS. It alerts; the human trades.** (CONTEXT section 1 R4, CLAUDE.md rule 4.)

---

## 1. Before the bell -- the exact commands

```
# 08:45  the pre-open refresh: yesterday's bhavcopy, today's instrument master, the
#        universe, the calendar, today's bias for every symbol, and CONTEXT 4.7's
#        verification of yesterday's live recording.
python -m acumen.run_screener --mode live --day <TODAY> --refresh --allow-network --preflight-only

# 08:50  read the preflight. If it is what you expect, run the morning:
python -m acumen.run_screener --mode live --day <TODAY> --refresh --allow-network --telegram

#        ...and add --live-alerts ONLY when the trader wants the messages on his phone:
python -m acumen.run_screener --mode live --day <TODAY> --refresh --allow-network --telegram --live-alerts
```

Three deliberate acts stand between you and a message on somebody's phone: `--mode live`,
`--telegram`, `--live-alerts`. Without the last one the morning is a DRY RUN -- every alert is
computed, shown, recorded and marked `dry_run`, and nothing is sent to anyone.

`<TODAY>` is `YYYY-MM-DD`. The session sweeps 11:15 -> 15:15 and closes itself at 15:30.
If it dies, run the **same command again**: it resumes from the recording, re-sends nothing
(the dedup key is on disk before any message leaves) and prints how many alerts it already
delivered.

## 2. What the preflight must say

| line | what to check |
|---|---|
| `instrument master` | **today's own dump** (`OpenAPIScripMaster_<TODAY>.json`) -- CONTEXT 4.7 / Q-29. If it says anything else, stop. |
| `symbols` | **204 screened** -- the settled universe. The `EXCLUDED` block names the six quarantined stocks (APLAPOLLO, ASTRAL, IEX, NTPC, UPL, VBL) and they are never screened. |
| `biases resolved` | should equal the symbol count. A short count means the bias series could not be built for some symbol; it will show as `refused` all day. |
| `gate battery` | `ORACLE-FREE, per sweep (CONTEXT 4.7)` on a live morning. |
| `calendar` | `trading day = True`, `standard session = True`. If either is False, there is no session to screen. |
| `corporate actions` | if it prints `refresh FENCED`, that is CORRECT and expected: a session never writes into the stores. |
| `telegram` | `credentials in .env: both present`. If it says MISSING, fix `.env` **now**, not at 11:30. |
| `alerts` | `DRY RUN (log only)` or `LIVE` -- the one line that says whether the trader's phone will ring. |

## 3. What each alert means

Every alert carries the numbers first, then anything that qualifies them, then the disclosed
line. Read it in that order.

| alert | what it means | what the trader does |
|---|---|---|
| `ARMED` | the 11:15 reference sits on the tradeable side of the POC (CONTEXT 3.4-1). Nothing has fired. | watch it |
| `<SYMBOL> LONG/SHORT entry ... SL ... TP ... qty ...` | **the trade.** The first 15-minute close across the POC while armed (3.4-2). Entry is that candle's close; SL is 3.4-3; TP is 3x the risk; qty is `floor(Rs 1,000 / per-share risk)` (3.5). | this is the signal |
| `EXIT stop-loss-hit / target-hit at ...` | the level was touched by a later candle (3.4-5). Both touched in one candle -> the stop wins. | the trade is over |
| `SQUARE-OFF at ...` | neither level by 15:15, so the position closes at the 15:00-15:15 candle's close (3.4-5). | close it |
| `!!` (failure) | the battery has REFUSED the day while a position was open. **The tool has stopped watching that position and 15:15 will not square it off.** | manage it by hand |

A stock that armed and then went quiet with `no trade, consumed` on the dashboard is CONTEXT
3.5's `qty == 0`: the cross was real, one share would already risk more than the Rs 1,000 budget,
so there is no trade. That is the strategy, not a fault.

## 4. The two markers that qualify a price

| marker | what it means |
|---|---|
| `!! STALE <n>m BEHIND -- this price stands on a window the screener cannot vouch for` | the last 1-minute candle in hand is `<n>` minutes older than the boundary. The feed answered but stopped growing. **Do not trade this price**; check the chart. |
| `!! POC provisional / incomplete window` | the 09:15-11:14 window was short of its 120 minutes when the POC was pinned at 11:15. The POC is never re-fixed (CONTEXT 3.3), so every number derived from it carries this flag for the day. |

Every live alert also carries, always:

> live feed, not yet verified against the exchange's end-of-day record

That is a fact about the DATA, not a disclaimer about the software: today has no bhavcopy until
evening. Tomorrow's pre-open runs the full battery over today's recording and names loudly any
day it alerted on that the exchange's record then refuses. The measured frequency is
**0.5229%-2.6808%** of settled symbol-days.

## 5. When the failure banner shows

The banner is the only full-width element on the dashboard, and it means *the screener could not
read part of the market* -- **silence below it is not calm**.

| banner says | what happened | what to do |
|---|---|---|
| `N symbol(s) never answered` | those symbols were polled twice and gave nothing. They keep their previous state and are NOT being watched. | if one of them is in a trade, manage it by hand |
| `N symbol(s) are stale` | they answered earlier but not this sweep. | as above |
| `the sweep hit its hard deadline` | the sweep ran out of time before the next boundary (CONTEXT 4.4). | let it run -- the next sweep re-polls everything; if it repeats, the feed is degraded |
| `TELEGRAM SEND FAILED ...` | the alert exists, was recorded and is on this screen; only the phone did not get it. | read the terminal; the next re-derivation retries |
| `TELEGRAM REFUSED an alert whose price the screener cannot vouch for` | the alert exists and is on this screen; the forwarding stopped because its price stands on a window the screener cannot vouch for. | look at the alert on screen and at the chart |

The banner CLEARS itself on the first complete sweep. If it does not clear for two boundaries,
stop the session (Ctrl-C), read the last lines, and restart the same command -- it resumes.

## 6. Where everything is afterwards

```
<data_root>/live/<YYYY-MM-DD>-live/
    manifest.json   the machine: code sha, spec version, instrument master + digest, calendar
    bias.json       today's bias per symbol, with the rule that produced it
    candles/        every bar the screener consumed, as it consumed it
    alerts.jsonl    every alert delivered, with its payload
    events.jsonl    sweeps, banners, POC pins, refusals, revisions
    state.json      the resume point
    dashboard.html  the trader's screen, rewritten after every sweep
```

Keep the recording. Tomorrow's pre-open verifies it against the published bhavcopy, and it is
what a parity check replays (`docs/evidence/chunk14_parity.py`).

## 7. The rules that do not change

1. **No orders, ever.** The tool has no order-placement code and a build-failing tripwire that
   scans the whole repository for the mere name of one.
2. **`.env` is never printed, logged or committed.** If you see a credential anywhere on screen
   or in a file, stop the session and say so.
3. **The stores are read-only during a session.** A morning writes its recording and nothing
   else; the corporate-action refresh is fenced and says so.
4. **Snapshot `data/` and `cache/` after any store-changing step**, before the next chunk starts
   (CLAUDE.md data-store safety). Keep two generations.
