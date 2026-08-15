# THE MORNING RUNBOOK -- operator procedure for a dry-run week

**Who this is for:** Paul, at the keyboard, from 08:30 to 15:35, five sessions running in
parallel with the trader's own manual trading (plan.md chunk 15).

**THIS TOOL PLACES NO ORDERS. It alerts; the human trades.** (CONTEXT section 1 R4, CLAUDE.md
rule 4.) Nothing in this repository can place, modify or cancel an order, and a build-failing
tripwire scans the whole repository for the mere NAME of one. Section 12 is the short list of
rules that never change; read it once and never again.

Sections 1-8 are the morning. Sections 9-11 are what to do when it does not go to plan. If you
read only one page before the bell, read section 3 (the preflight) and section 6 (the banner).

---

## 0. ONCE, before the week -- the readiness gate

Run this the evening before day 1, or on day 1 after the 08:45 refresh. It is one command and it
certifies rather than reports: seven checks, no partial pass.

```
python scripts/run_screener.py --readiness --day <TODAY>
```

It prints one line per check and then `READY for a live dry-run week` -- or it REFUSES with
`NOT READY for a live dry-run week -- do not start it` and names what is missing, with the
remedy on the same line. (That is the GATE's refusal. The morning refresh has a refusal line of
its own -- `NOT READY -- the screener must not start`, section 3 -- and they are different
steps; each says which one it is by the words it uses.) The seven:

| check | what it certifies |
|---|---|
| `telegram credentials in .env` | both keys are present. It reads no value, prints no value and keeps no value -- only whether each key exists. |
| `the day's own instrument master` | `OpenAPIScripMaster_<TODAY>.json` resolves AND is on disk. A live morning refuses to start without it (CONTEXT 4.7 / Q-29), and 09:14 is the wrong moment to find that out. |
| `the published NSE calendar` | the holiday day-cache loads OFFLINE and can answer for today. A gate that pulled would certify a network, not this machine. |
| `the settled universe` | the shipped filter screens exactly **204** symbols and excludes the six CONTEXT 4.6 quarantines BY NAME (APLAPOLLO, ASTRAL, IEX, NTPC, UPL, VBL). |
| `the store fence` | a `--refresh --allow-network` morning would write NOTHING inside either store. |
| `the safety tripwires` | `tests/test_live_safety.py` is run -- not cited -- and is green on this tree, right now. |
| `a test message to the configured chat` | one clearly-labelled message really reached the trader's phone. |

The last one is **opt-in and required**. Opt-in, because a gate that messages somebody as a side
effect of being run is a gate nobody runs twice. Required, because a wrong chat id, a bot the
trader never pressed Start on, and a revoked token all look exactly like a quiet morning. So it
reads `NOT SENT` and the gate refuses until you run it once with the flag:

```
python scripts/run_screener.py --readiness --day <TODAY> --send-test-message
```

That sends ONE message, headed `ACUMEN -- TEST MESSAGE (not an alert)`, naming no stock, no
price and no trade. Ask the trader to confirm he saw it. Then move on.

---

## 1. The morning, minute by minute

`<TODAY>` is `YYYY-MM-DD`, always. Every command below is run from the repository root.

```
# 08:45  THE PRE-OPEN REFRESH, as a dry run of the whole start-up.
#        Yesterday's bhavcopy into the daily store, today's instrument master, the
#        universe, the published calendar, today's bias for every symbol, and CONTEXT
#        4.7's verification of every prior LIVE recording nobody has judged yet.
python scripts/run_screener.py --mode live --day <TODAY> --refresh --allow-network --preflight-only

# 08:50  READ THE PREFLIGHT (section 3). If it is what you expect, start the morning.
#        This one runs the whole session and sends NOTHING: every alert is computed,
#        shown, recorded and marked dry_run.
python scripts/run_screener.py --mode live --day <TODAY> --refresh --allow-network --telegram

#        ...and ONLY when the trader wants the messages on his phone, add --live-alerts.
#        This is a separate, deliberate act. Type it; do not keep it in shell history.
python scripts/run_screener.py --mode live --day <TODAY> --refresh --allow-network --telegram --live-alerts
```

| time | what happens |
|---|---|
| 08:45 | the pre-open refresh + preflight. Takes a few minutes: the bias series is seeded 180 days back for every symbol. |
| 09:15 | the market opens. **The tool is quiet and that is correct** -- it is collecting 1-minute candles and nothing else. |
| 11:15 | the POC pass. The 09:15-11:14 window is read for all 204 symbols and each POC is pinned. The armed list appears. |
| 11:30 | the first boundary that can fire. Then every 15 minutes. |
| 15:00 | the last boundary that can OPEN a trade (CONTEXT 3.4-2). |
| 15:15 | the square-off boundary: anything still open closes at the 15:00-15:15 candle's close (3.4-5). **The last actionable moment of the day.** |
| 15:30 | the session closes itself. One last poll so the recording holds the whole 375-minute session, the end-of-day summary goes to the phone, and the dashboard is written for the last time. |

**Three deliberate acts stand between you and a message on somebody's phone**: `--mode live`,
`--telegram`, `--live-alerts`. All three live in one function (`run_screener.telegram_is_live`)
and **any one of them missing means nothing is sent**. Without `--live-alerts` the morning is a
DRY RUN. Without `--mode live` the session is a REPLAY of a past day: it never sends, and any
message it would have sent carries its trade date and a `REPLAY` marker, so a phone can never
read it as today.

The three ways to launch are equivalent -- `python scripts/run_screener.py` (works from a bare
clone, and is the one above), `python -m acumen.run_screener` and `acumen-screener` (both need
`pip install -e .`).

---

## 2. Starting late, and starting again

**If the session dies, run the SAME command again.** It resumes from the recording, re-sends
nothing (the dedup key reaches disk before any message leaves) and prints how many alerts it has
already delivered. There is no separate resume command and no state to clean up.

**If you start after 11:15**, add `--no-wait` so it sweeps the boundaries that have already
passed instead of waiting for a clock that is ahead of it:

```
python scripts/run_screener.py --mode live --day <TODAY> --refresh --allow-network --telegram --no-wait
```

Use it for a same-day catch-up and for nothing else. It is not a way to run a morning that has
not happened.

**One session at a time.** Two screeners on one day write into the same recording and will
double-count each other's work. If you need a second one for any reason, give it its own
`--label` and treat its output as a diagnostic, not as the morning.

---

## 3. What the preflight must say

The preflight is the last chance to catch a bad morning before it is a bad morning. Read every
line; these are the ones that decide.

| line | what to check |
|---|---|
| `instrument master` | **today's own dump** (`OpenAPIScripMaster_<TODAY>.json`) -- CONTEXT 4.7 / Q-29. If it says anything else, stop. |
| `symbols` | **204 screened** -- the settled universe. The `EXCLUDED` block names the six quarantined stocks (APLAPOLLO, ASTRAL, IEX, NTPC, UPL, VBL) and they are never screened. |
| `biases resolved` | should equal the symbol count. A short count means the bias series could not be built for some symbol; it will show as `refused` all day. |
| `gate battery` | `ORACLE-FREE, per sweep (CONTEXT 4.7)` on a live morning. |
| `calendar` | `trading day = True`, `standard session = True`. If either is False, there is no session to screen. |
| `corporate actions` | if it prints `corporate-action refresh FENCED`, **that is CORRECT and expected**: a session never writes into the stores, so the pull downgrades to reading the day-cache. It is not an error and there is nothing to fix. |
| `telegram` | `credentials in .env: both present`. If it says MISSING, fix `.env` **now**, not at 11:30. |
| `alerts` | `DRY RUN (log only)` or `LIVE` -- the one line that says whether the trader's phone will ring. |
| `recording` | where today's evidence will be written. Note it. |
| `EXCLUDED` | the block that names the six quarantined stocks and why each is not screened. If it names anything else, or nothing, stop. |

Above the preflight, the refresh prints one line per pre-open step and then `READY` or
`NOT READY -- the screener must not start`. **`NOT READY` means the screener does not start**,
and the failing step says why on its own line. The commonest three:

* `calendar (published NSE)` FAILED -- no network and no day-cache. Re-run with
  `--allow-network` once; everything downstream depends on it.
* `instrument master (TODAY's dump)` FAILED -- today's dump did not arrive. Same remedy.
* `verify prior LIVE recordings (CONTEXT 4.7)` FAILED -- see section 8.

If a verification found something loud, the report prints it AFTER the READY line, prefixed
`!!`, one line per day. Never read past it.

---

## 4. What each alert means

Every alert carries the numbers first, then anything that qualifies them, then the disclosed
line. Read it in that order.

| alert | what it means | what the trader does |
|---|---|---|
| `ARMED` | the 11:15 reference sits on the tradeable side of the POC (CONTEXT 3.4-1). Nothing has fired. | watch it |
| `<SYMBOL> LONG/SHORT entry ... SL ... TP ... qty ...` | **the trade.** The first 15-minute close across the POC while armed (3.4-2). Entry is that candle's close; SL is 3.4-3; TP is 3x the risk; qty is `floor(Rs 1,000 / per-share risk)` (3.5). | this is the signal |
| `EXIT stop-loss-hit / target-hit at ...` | the level was touched by a later candle (3.4-5). Both touched in one candle -> the stop wins. | the trade is over |
| `SQUARE-OFF at ...` | neither level by 15:15, so the position closes at the 15:00-15:15 candle's close (3.4-5). | close it |
| `!!` (failure) | the battery has REFUSED the day while a position was open, or a symbol could NOT be evaluated at all this sweep (the banner names it). **The tool has stopped watching that position and 15:15 will not square it off.** | manage it by hand |

**The qty-zero day is not a fault.** A stock that armed and then went quiet, showing
`qty 0 -- no trade, consumed (CONTEXT 3.5)` on the dashboard, met a real cross whose per-share
risk exceeds the whole Rs 1,000 trade budget: one share would already risk more than the
strategy allows, so there is no trade, the stock-day is consumed, and nothing later trades it.
That is the strategy. Over the ten-year ledger it happened on **2 stock-days out of 495,312**;
if you see it twice in a week, say so.

**Nothing is announced after 15:29.** If a late feed heals after the close and the tool then
works out that a trade would have fired, it records that in full and sends nothing -- the
recording holds it as `post-session-alert-withheld` and the dashboard shows the final state.
There is nothing to act on after 15:15, and an alert that arrives when the market is shut is
worse than no alert.

---

## 5. The markers that qualify a price

| marker | what it means |
|---|---|
| `!! STALE <n>m BEHIND -- this price stands on a window the screener cannot vouch for` | the last 1-minute candle in hand is `<n>` minutes older than the boundary. The feed answered but stopped growing. **Do not trade this price**; check the chart. |
| `!! POC provisional / incomplete window` | the 09:15-11:14 window was short of its 120 minutes when the POC was pinned at 11:15. The POC is never re-fixed (CONTEXT 3.3), so every number derived from it carries this flag for the day. |
| `[DRY RUN -- log only, nothing was sent to anyone else]` | on a message this session produced without `--live-alerts`. |
| `[REPLAY of a PAST day -- this is not a live alert and nothing about it is about today]` | on a message about a day that is not today. |
| `[POSTURE NOT STAMPED -- ...]` | on a message built from an alert recorded before the posture stamp existed. It is not confirmed to be a live alert; read its date. |

Every live alert also carries, always:

> live feed, not yet verified against the exchange's end-of-day record

That is a fact about the DATA, not a disclaimer about the software: today has no bhavcopy until
evening. Tomorrow's pre-open runs the full battery over today's recording and names loudly any
day it alerted on that the exchange's record then refuses. The measured frequency is
**0.5229%-2.6808%** of settled symbol-days.

---

## 6. When the failure banner shows

The banner is the only full-width element on the dashboard, and it means *the screener could not
read part of the market* -- **silence below it is not calm**.

| banner says | what happened | what to do |
|---|---|---|
| `N symbol(s) never answered` | those symbols were polled twice and gave nothing. They keep their previous state and are NOT being watched. | if one of them is in a trade, manage it by hand |
| `N symbol(s) are stale` | they answered earlier but not this sweep. | as above |
| `N symbol(s) could NOT be evaluated: <NAMES>` | their reply arrived and could not be read -- a malformed candle, or a candle file this machine could not write. The named stocks keep their previous state and are NOT being watched; **every other symbol swept normally**, and the named ones are re-polled at the next boundary. | if one of them is in a trade, manage it by hand; note it in the incident log |
| `the sweep hit its hard deadline` | the sweep ran out of time before the next boundary (CONTEXT 4.4). | let it run -- the next sweep re-polls everything; if it repeats, the feed is degraded |
| `TELEGRAM SEND FAILED ...` | the alert exists, was recorded and is on this screen; only the phone did not get it. | read the terminal; the next re-derivation retries |
| `TELEGRAM REFUSED an alert whose price the screener cannot vouch for` | the alert exists and is on this screen; the forwarding stopped because its price stands on a window the screener cannot vouch for. | look at the alert on screen and at the chart |

The banner CLEARS itself on the first complete sweep. If it does not clear for two boundaries,
stop the session (Ctrl-C), read the last lines, and restart the same command -- it resumes.

**One symbol never costs the morning.** A stock whose data cannot be fetched, cannot be read or
cannot be evaluated loses its own boundary and is named; the other 203 finish their sweep, the
dashboard is written, and the day continues.

---

## 7. When the phone is silent

Silence has three meanings and they are not the same. Work through them in this order.

1. **Is the terminal still sweeping?** Every boundary prints a sweep line. If they have stopped,
   the session has died -- restart the same command (section 2).
2. **Is the banner up?** If it is, the silence is partial and section 6 says which stocks are
   affected. If it is not, every symbol was read.
3. **Does the last line say `telegram: 0 sent, 0 refused (unvouched price), 0 failed`?** Then
   the morning genuinely produced nothing to send. On most days that is the correct answer: 204
   stocks, and only a handful arm.
   * `... 0 sent, N refused ...` -- the alerts exist and were held back because their prices
     stood on a window the tool could not vouch for. They are on the screen and in the recording.
   * `... 0 sent, 0 refused, N failed` -- the alerts exist and the sends failed. Read the
     terminal; the phone is the only thing that missed them.
   * `[DRY RUN -- nothing was sent]` on the end of that line -- you did not pass `--live-alerts`.
     That is the commonest cause of a silent phone and it is not a fault.

**At the close the phone gets one message either way**, so a silent phone at 15:30 is itself the
signal that something is wrong:

```
ACUMEN -- END OF DAY   <YYYY-MM-DD>
2 symbol(s) alerted:
  HDFCBANK   armed 11:15, trigger 11:30
  ICICIBANK  armed 11:15
telegram: 3 sent, 0 refused (unvouched price), 0 failed
markers: 1 stale, 0 provisional POC
(live feed, not yet verified against the exchange's end-of-day record)
```

A morning where nothing fired still sends it, saying
`no alerts today -- the screener ran the whole session and nothing fired` in words. A DRY RUN
prints it on the terminal, labelled, and sends nothing. If the send fails you will read
`TELEGRAM SEND FAILED ...: end-of-day summary` here: nothing is retried automatically, and
re-running the same command at the close sends it, because the "already sent" mark
(`telegram-end-of-day-summary` in `events.jsonl`) is written only after a message really left.
That mark is also why a restart does **not** send a second summary for the same day.

After a resumed morning the summary carries one extra line:
*"the list above is the whole day's, read from the recording; the counters are this process's
own -- a resumed morning delivered its alerts before the restart"*. The two numbers describe two
different things and both are right, which is why the line exists. It appears whenever this
process's three counters add up to FEWER than the day's alerts -- so a restart that delivered
some of the day's alerts after it carries the line as well as one that delivered none.

---

## 8. The next morning: verification, and how to read a "withdrawn" alert

Today has no exchange record until the evening. So the NEXT pre-open takes yesterday's recording
-- the actual bytes the morning decided on -- and runs the FULL end-of-day battery over it
against the now-published bhavcopy. That is the `verify prior LIVE recordings (CONTEXT 4.7)`
step, and it verifies **every** unverified LIVE recording, not just yesterday's: a pre-open you
skipped does not lose its day, it queues it.

Four outcomes, and they mean four different things:

| the report says | what it means | what to do |
|---|---|---|
| `verified against the published bhavcopy -- N/N symbol-day(s) pass the FULL battery` | yesterday's data holds up against the exchange's own record. | nothing |
| `THE EXCHANGE'S RECORD REFUSES ... treat them as withdrawn.` | the tool ALERTED on a symbol-day whose data the end-of-day battery does not accept. **Those alerts are withdrawn**: the signal was computed on data the exchange's record contradicts. | tell the trader, by name, before the debrief. If he traded it, that trade stands on data we now know was bad -- log it as a divergence |
| `NOT VERIFIED -- ... could NOT be judged` | the recording alerted and there is nothing to judge it against: no candle file, or `THE ORACLE HAS NOT SPOKEN` (the bhavcopy has no row for that symbol-day). **The alerts are NOT withdrawn and NOT confirmed.** | note it; if the bhavcopy simply had not published, tomorrow's pre-open judges it |
| `NOT JUDGED and still queued` | a recording names an instrument master that cannot be loaded, or its `manifest.json` cannot be read or is not there at all. A day is re-judged under the ticks it ran on and never under another, so it is left unjudged and stays on the queue. | find the dump, or tell the architect |

**A recording that cannot say WHICH day it is of stops the morning.** If the manifest is
unreadable or missing and the directory name does not date it either, the report says so by name
(`cannot say WHICH day they are of ... and STOP this morning`) and the step FAILS. That is
deliberate: an entry nobody can date could be yesterday's, and yesterday's is the one CONTEXT
4.7 makes a duty. An entry that IS dated -- by its manifest or by its name -- and is older than
the prior trading day is shouted about and does not hold the bell hostage. Tell the architect;
do not delete anything (rule 3 of section 12, and store deletions are never a session's work).

A withdrawn alert is not a bug report about the screener. It is the disclosed, bounded price of
live mode: today cannot be verified during today, and 0.5229%-2.6808% of settled symbol-days
fail an end-of-day gate. What matters is that it is **named, loudly, the next morning** rather
than discovered a month later.

On the dashboard, the previous day's verdict is a section at the bottom -- quiet when the oracle
agreed, in the banner's own red when it refuses a day this tool alerted on. On the text
dashboard an unjudged alerted day is prefixed `!!` and a refused one carries
`REFUSED-AFTER-ALERT`; an unjudged row carries `NOT-VERIFIED` with its reason beside it.

---

## 9. Where the recording is, and what is in it

```
<data_root>/live/<YYYY-MM-DD>-live/
    manifest.json     the machine: code sha, spec version, instrument master + digest, calendar
    bias.json         today's bias per symbol, with the rule that produced it
    candles/          every bar the screener consumed, as it consumed it
    alerts.jsonl      every alert delivered, with its payload
    events.jsonl      sweeps, banners, POC pins, refusals, revisions, withheld alerts, the summary mark
    state.json        the resume point
    dashboard.html    the trader's screen, rewritten after every sweep
    verification.json written by the NEXT morning: the full-battery verdict on this day
```

**Keep every recording of the week.** Tomorrow's pre-open verifies it, the debrief reads it, and
a parity check replays it (`docs/evidence/chunk14_parity.py`). It is the only record of what the
tool actually saw; the terminal scrollback is not.

---

## 10. The daily debrief (plan.md chunk 15)

Ten minutes, Paul and the trader, after the close. Three questions and an incident log:

1. **Every signal he took manually -- did the tool also produce it?** If not, note the symbol,
   the time and what he saw. That divergence is triaged before the week ends.
2. **Every signal the tool produced -- would he have taken it?** A `no` here is worth more than
   a `yes`; it is what the chunk-12 pack was for and this is the live version of it.
3. **Anything on screen he could not read at a glance?** The dashboard has one job.

Log, per session: the number of sweeps completed, whether the banner ever rose and for how long,
any symbol that was not watched and for which boundaries, any withdrawn alert from the previous
day's verification, and the wall-clock time from the boundary to the alert reaching his phone.
All of it is in the recording; the log is where it gets read.

**Success for the week** is stated in plan.md and is not about PnL: zero unhandled errors across
five sessions, and every signal he took manually was also produced by the tool -- or the
divergence is explained and triaged. Live-equals-backtest is already proven (chunk 14, 15 days,
14 judged, 14 matched); what the week tests is the plumbing around it and the trader's own
acceptance.

---

## 11. When something goes wrong

| symptom | first move |
|---|---|
| `the screener cannot start: ...` | one sentence, exit 1. Read it -- it names the missing input. Usually today's master or the published calendar. |
| `THE SCREENER IS BLOCKED, and this is not a bug` | a class-A spec question stands between this morning and an answer anyone may rely on. Do not work around it. Tell the architect. |
| the session died mid-morning | run the same command again (section 2). |
| the same symbol is named in the banner at every boundary | its data is deterministically bad today. It stays unwatched; note it and move on. The other 203 are fine. |
| `NOT READY -- the screener must not start` | do not start it. Fix the failing step or accept there is no session today. |
| anything at all that looks like a credential on screen or in a file | **stop the session** and say so. |
| the stores look wrong | stop. Store deletions are never a session's work, and a snapshot is verified before anything is removed. |

---

## 12. The rules that do not change

1. **No orders, ever.** The tool has no order-placement code and a build-failing tripwire that
   scans the whole repository for the mere name of one. The readiness gate RUNS that tripwire.
2. **`.env` is never printed, logged or committed.** If you see a credential anywhere on screen
   or in a file, stop the session and say so.
3. **The stores are read-only during a session.** A morning writes its recording and nothing
   else; the corporate-action refresh is fenced and says so on the preflight.
4. **Snapshot `data/` and `cache/` after any store-changing step**, before the next chunk starts
   (CLAUDE.md data-store safety). Keep two generations, and never overwrite the previous one
   until the new one is verified.
5. **One session at a time.** One screener, one recording, one day.
6. **The strategy is frozen.** Nothing in this runbook is a parameter. If the tool appears to
   need a different rule, that is a question for the architect, not a setting.
