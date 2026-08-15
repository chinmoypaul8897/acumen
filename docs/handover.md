# ACUMEN INTELLIGENCE -- handover

**For the trader, and for whoever operates the tool.** Plain English, no code. Nothing in here
needs a technical background to read, and nothing important about the tool is left out of it.

---

## 1. What this tool is

It is a **screener**. Every trading day it watches the same 204 NSE F&O stocks, applies your
strategy to each one exactly as written, and tells you the moment a stock does what your rules
say it should. It sends that to your phone and shows it on a screen.

That is all it is. It is a very fast, very literal, very patient version of you going through
204 charts every fifteen minutes.

## 2. What this tool is NOT

**It does not trade. It has never placed an order and it cannot place one.**

That is not a policy or a setting -- it is a structural fact about the software. There is no
order-placing code anywhere in it. There is a check that runs every time the code is built which
searches the entire project for the mere *name* of an order-placing instruction and fails the
build if it finds one. The readiness check the operator runs before a live week runs that scan
again, on that day, on that machine, and refuses to certify anything if it is not clean.

So:

* **it alerts; you trade.** Every decision to put money on anything is yours, made in your
  broker, by hand.
* **it cannot lose you money by acting.** The worst it can do is tell you something wrong, or
  tell you nothing. Both of those are covered below, and both are things the tool says out loud
  when they happen.
* **it is read-only at the broker.** It asks for candles and it asks for a login. Those are the
  only two things it is allowed to ask for.

It also does not manage risk for you, size your account, or know anything about your positions.
It knows one thing: what your rules say about each stock, right now.

## 3. What it does, hour by hour

| time | what it does |
|---|---|
| before the open | brings yesterday's official exchange data up to date, fetches today's instrument list, works out today's daily bias for every stock |
| 09:15 - 11:14 | collects one-minute candles. Silent, and that is correct |
| 11:15 | builds each stock's volume profile from the 09:15-11:14 window and fixes its POC for the day. The watch-list appears |
| 11:30 onward, every 15 min | checks every stock against your rules and alerts on anything that fires |
| 15:00 | the last moment a new trade can start |
| 15:15 | anything still open is squared off at that candle's close |
| 15:30 | it closes itself, sends you a one-message summary of the day, and saves everything it saw |

The POC is fixed at 11:15 and never moved. If the data for that window was incomplete, every
number that comes from it is flagged for the rest of the day, and the flag travels on every
message about that stock.

## 4. The three paths you were offered, and where this one goes

The validation pack (chunk 12) put three paths in front of you, and you chose the one this
handover exists for.

1. **Stop here.** The backtest is done and reviewed; read the numbers and decide with them.
   Nothing further is built.
2. **The complete tool, used as a screener.** The machine runs live beside you, alerts you, and
   you keep trading by hand. **This is the path being delivered.**
3. **Automation.** The tool places the trades itself. This is explicitly *not* built and is a v2
   conversation, listed in the plan's own backlog beside slippage modelling and a point-in-time
   universe. Nothing in the current code moves in that direction, and the no-order check exists
   to keep it that way until somebody decides otherwise, deliberately, in writing.

## 5. The dry-run week: what happens, and what "success" means

Five trading sessions. The tool runs live, in parallel with your own trading, and you keep
trading exactly as you would have anyway. Nothing about your week changes except that alerts
arrive on your phone.

Every afternoon, a ten-minute conversation between you and Paul:

* every signal **you** took by hand -- did the tool produce it too?
* every signal **the tool** produced -- would you have taken it?
* was anything on the screen unreadable at a glance?

**Success is not a profit number.** The week is a test of the plumbing, not of the strategy. It
passes when:

* the tool ran five sessions with no unhandled error;
* every signal you took manually was also produced by the tool -- or the difference is explained
  and understood;
* you accept it.

**Why PnL is not the test.** That the tool's live decisions match the backtester's has already
been proven, mechanically, before the week starts: fifteen stratified real days were run through
both halves candle by candle, and on all fourteen that could be judged the live screener and the
ten-year backtester reached the *identical* decision -- same entry, same stop, same target, same
quantity, same exit, at the same boundary. The fifteenth is disclosed rather than counted, for a
reason section 7 explains. So the week is not asking "is the strategy right" (the validation pack
asked that) or "does live match the backtest" (that is proven). It is asking: does this thing
survive five real mornings on a real laptop with a real internet connection, and do the messages
arrive in a form you can act on.

## 6. What the messages look like

Four kinds, and one of them is not about a stock.

* **ARMED** -- this stock is now on the watch-list: the reference price sits on the tradeable
  side of its POC. Nothing has fired.
* **the trade** -- symbol, side, entry, stop-loss, target, quantity. This is the signal. The
  quantity is `Rs 1,000 risk / per-share risk`, rounded down, exactly as specified.
* **EXIT / SQUARE-OFF** -- the stop or the target was touched, or 15:15 arrived. The trade is
  over.
* **a failure line** -- the tool has **stopped watching** something. This is the most important
  message it can send, and it is the one to read first. It means: this stock is no longer being
  tracked, 15:15 will not square it off for you, manage it by hand.

Two flags can appear on any message, and both mean *do not trade this price without checking the
chart*:

* **STALE** -- the newest candle it has is older than it should be. The feed answered but stopped
  giving it new data.
* **POC provisional** -- the 09:15-11:14 window was missing minutes when the profile was built.

And one sentence appears on every live message, always:

> live feed, not yet verified against the exchange's end-of-day record

## 7. The one honest limitation, stated plainly

**During the day, there is no way to check today's data against the exchange's official record,
because that record does not exist until the evening.**

The tool runs every check it *can* run on live data, and it names the ones it cannot. Then, the
next morning, it takes the previous day's data -- the exact bytes it made its decisions on -- and
runs the full end-of-day battery over it against the published official file. If a stock it
alerted on turns out to have had bad data, it says so, by name, loudly, and treats those alerts
as withdrawn.

How often does that happen? It was measured over ten years of data: **between 0.52% and 2.68% of
stock-days**. That is the honest range, not the flattering end of it.

That is the whole of the difference between the live tool and the backtest, and it exists because
today cannot be checked during today. Everything else about the two is the same code.

## 8. A silent phone

Silence means one of three things and the tool is built so you can tell them apart:

1. **nothing fired.** On most days, of 204 stocks, only a handful arm and fewer trade.
2. **something is broken.** Then a red banner is on the screen, and it is the only full-width
   thing on that screen. Silence *under a banner* is not calm.
3. **the tool has stopped.** This is the one silence you cannot see -- so at the close it sends
   you one message **every day, whether or not anything fired**, and that message says in words
   that nothing fired. If 15:30 comes and no message arrives, that is the signal.

## 9. Where everything is

| what | where |
|---|---|
| the operator's procedure, morning by morning | `docs/morning_runbook.md` |
| the ten-year backtest report | `docs/reports/chunk9b_backtest_report.md` |
| the validation pack you signed off | `docs/validation/trader_pack.md` |
| the strategy, written down as law | `CONTEXT.md` section 3 |
| every day the tool ran live | a dated folder holding every candle it saw, every message it sent, and the next morning's verdict on that day |

The recordings are the point of the week: they are the only record of what the tool actually saw,
and they are what any disagreement gets settled from.

## 10. If you want it to stop

Tell Paul. It is one process on one laptop; closing it stops it, and there is nothing to unwind
anywhere. It holds no positions, has no standing instructions with the broker, and leaves nothing
running when it is not running.
