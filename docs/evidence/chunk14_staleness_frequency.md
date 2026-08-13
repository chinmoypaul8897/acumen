# chunk 14 -- how often a HEALTHY feed looks stale at a boundary

Run at 2026-08-14T05:22:47 from `docs/evidence/chunk14_staleness_frequency.py`. READ-ONLY over the stores.

Day measured: **2026-06-10**, over **204 settled symbols** the lake holds, at each of the 17 boundaries CONTEXT 4.4 sweeps.

## The measurement

* symbol-boundary readings: **3,468**
* readings the shipped predicate calls STALE (last bar more than 1 minute behind the boundary): **9 = 0.26%**
* symbols with at least one stale reading: **5** of 204

| minutes behind the boundary | readings |
|---:|---:|
| 1 | 3,459 |
| 2 | 7 |
| 3 | 1 |
| 5 | 1 |

## What it does and does not decide

**The number is SMALL, and it is reported as measured rather than as the answer it
would have been convenient for it to be.** A 1-minute bar exists only if the stock
TRADED in that minute, so a healthy feed does produce stale readings -- 9 of
3,468 here, across 5 symbols -- but at 0.26% they would
not drown a banner. So this measurement does NOT settle the banner question on volume,
and it is not used to.

What settles it, in this session's judgment and subject to the architect's, is what the
banner MEANS. The full-width banner says *the screener could not read part of the
market*: it is the one element DESIGN.md PART II lets cover the width, and its whole
value is that it is never wrong. On a quiet stock the screener read the market
perfectly and the market said nothing, so the banner's own sentence would be false --
while the ALERT-level and ROW-level markers say exactly the true thing, that this price
stands on a window N minutes old.

REVIEW_13B's Q1 case -- a feed answering 200 with a prefix that never grows -- is
therefore caught by the marker on every alert it produces and by the row on the
dashboard, which is the fix the finding itself prescribed (*"carrying the row's
staleness onto the alert exactly as poc_note is carried"*), and not by a banner it did
not ask for.

Recorded in PROGRESS.md as a Class-B choice with this number beside it, and put to the
architect as QUESTIONS.md **Q-32** rather than settled here: at 0.26% a banner is
affordable, and whether a stale window should ALSO be loud is his call, not this
session's.
