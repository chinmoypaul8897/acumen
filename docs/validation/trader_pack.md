# Your strategy, run over ten years

This is the evidence pack. It is written for you, not for the people who built the machine, so there is no jargon in it that is not explained on the spot.

**What the machine is.** It is your strategy and nothing else: the bias rules you wrote down, the volume profile from your own chart settings, the entry, the stop and the target exactly as you described them. It was given no discretion. It took EVERY signal your rules produced, on every stock, on every day it had good data for -- 188,345 trades over 2,428 trading days and 204 stocks, risking Rs 1,000.00 on each one.

**What this pack asks of you.** Two things, and nothing else. Read your rules on page 2 and tell us whether they are right. Open the six days on page 3 on your own TradingView chart and tell us whether the machine did what you would have done. Everything else here is there so that nothing is hidden from you.

**What this pack does not do.** It does not tell you what to do next. The last page sets out three ways forward, written as flatly as we can manage, with no recommendation attached to any of them.

## 1. The arithmetic

Three lines. There is no opinion in them.

| | |
|---|---:|
| What the trades made, before costs | **Rs 1,998,481.80** |
| What the costs took: 188,345 trades x Rs 100.00 | **-Rs 18,834,500.00** |
| What is left | **-Rs 16,836,018.20** |

**The costs are the whole story, and they are not a rounding error.** Every round trip costs Rs 100.00. You risk Rs 1,000.00 on a trade. So the cost of taking a trade is 10.00% of the money you put at risk on it -- before the market has moved at all. A strategy that wins three times what it risks has to clear that on every single trade, and this one took 188,345 of them.

**The one number that explains the rest.** With this strategy's own average winner (Rs 1,911.49) and its own average loser (-Rs 1,011.09), both after costs, it would need to win **34.60%** of its trades just to end level. It won **31.53%** of them (59,385 of 188,345). That gap is the whole result. Nothing else on this page changes it.

**Say plainly what was run.** This is YOUR strategy, with your rules as YOU confirmed them -- every one of them is quoted back to you on the next page. Every signal those rules produced was taken; none was skipped, filtered, improved or second-guessed. Every trade risked Rs 1,000.00, no more and no less. The machine was never allowed to decide anything you had not already decided.

## 2. Your rules, written back to you

This is the whole strategy as the machine has it. Where we have your own words, they are quoted. Where we do not, it is because the answer reached us as an answer rather than a sentence -- those are written out plainly and marked, and they need checking just as carefully.

**Which stocks, and which days.** Every stock in the NSE futures-and-options list, on its own daily chart. No index filter, no market filter, no day-type filter: no expiry days skipped, no results days skipped, no news days skipped. Cash prices.

**The bias, decided the evening before.** Take the two daily candles before the day you are trading -- call the older one P and the newer one C -- and work down this list in order. The first one that fits decides the day, and the day's bias never changes once the day has started.

1. **Inside bar.** If C's high did not go above P's high AND C's low did not go below P's low, nothing changes: keep yesterday's bias. Touching the level exactly still counts as inside.
2. **Rule 1, a breakout on the close.** If C closed above the top of P's body, BULLISH. If C closed below the bottom of P's body, BEARISH. The body is the open-to-close range, not the wicks.
3. **Rule 2, a single sweep.** BULLISH if C's low went below P's low, C's high did NOT go above P's high, and C closed at or above the bottom of P's body. BEARISH is the mirror: C's high above P's high, C's low not below P's low, C closed at or below the top of P's body.
4. **Rule 3, a sweep of both sides.** If C's high went above P's high AND C's low went below P's low, look at C's one-minute candles and find which side broke FIRST. High first means BULLISH, low first means BEARISH.
5. **Nothing fits.** Keep yesterday's bias.

**A bullish day is a long-only day and a bearish day is a short-only day.** The colour of a candle never matters anywhere; only closes do.

**The volume profile.** Built once a day from the first two hours -- the one-minute candles from 09:15 to 11:14, which is the eight 15-minute candles up to and including the one that closes at 11:15. Row Size 24, rows laid out by number of rows, volume split across every row a candle's range touches in proportion to how much of the candle sits in each row. The POC is the middle price of the row that ends up with the most volume, and if two rows tie, the higher one wins. Once it is fixed at 11:15 it does not move again that day.

**The entry.** At 11:15 look at the close of the 11:00-11:15 candle.

* On a bullish day: if that close is BELOW the POC you are armed straight away. If it is ABOVE, you wait for a 15-minute candle to close below the POC first, and then you are armed. If it is exactly ON the POC, you have no side yet -- the first candle that closes clearly above or clearly below picks the side, and that candle is never itself the entry.
* Once armed, the FIRST 15-minute candle that closes above the POC is the entry, and you buy at that candle's close. A close exactly on the POC is not an entry.
* Bearish days are the exact mirror, selling instead of buying.
* The first entry uses the stock up for that day: one trade per stock per day, and no re-entry after an exit. Entries stop after the candle that closes at 15:00.

**The stop.** The low of the entry candle on a long, the high of it on a short -- no buffer. Unless the entry candle gapped clean past the POC and never traded back to it, in which case the stop is the previous 15-minute candle's close.

**The target.** Three times the distance from the entry to the stop.

**Getting out.** If the price touches the stop, you are out at the stop. If it touches the target, you are out at the target. If one candle touches both, the stop wins. If neither is touched, you are out at the close of the 15:00-15:15 candle. No partial exits and no trailing.

**The money.** Every trade risks the same rupee amount, and the number of shares is that amount divided by the distance from entry to stop, rounded DOWN. If that works out to zero shares the trade cannot be taken -- and the stock is still used up for the day.

### The answers of yours we have in your own words

| You said | Which fixed |
|---|---|
| *"risk per trade = 1,000 rupees."* (Round 3, Q29) | how much of your money each trade is allowed to lose |
| *"Rows Layout = 'Number of Rows'; Row Size = 24; Volume shows Up/Down split on the chart."* (Round 3, Q32) | the volume-profile settings the machine copies from your chart |
| *"the box is the first two hours -- 9:15 to 11:15. Eight candles."* (Round 3, Q42) | which candles the volume profile is built from |
| *"the colour of that one-minute candle does not matter. Red, green or a doji -- I look at where the DAY closed against the previous day's body."* (Round 3, Q38/Q39) | how an outside-bar tie is decided |
| *"on the outside-bar tie, when the deciding 1-minute candle closes red near its bottom, the low was swept last, so the real break was the high -> BULLISH."* (Round 3, Q31-WHY) | why the first break decides the outside-bar day |
| *"A -- that first candle only tells me which side I am playing. I still wait for the entry."* (Round 3, Q41) | what happens when the 11:15 candle closes exactly ON the POC |
| *"d -- no limits, show me the honest numbers."* (Round 3, Q40) | whether the machine may skip a signal because the money is already committed |
| *"confirmed -- that is what I would have called on each of those days."* (Round 3, bias table) | your confirmation of the bias engine on fifteen real days (the chunk-4 gate) |
| *"BHARTIARTL 17-Jul: POC reads about 1913.9, and I count 25 rows in the box."* (Round 3, chart reading) | the chart reading that settled how the profile's rows are counted |

Everything above that is not in that table reached us through earlier rounds of questions as an answer rather than a sentence, and it lives in the specification as our record of what you said. That is exactly why this page exists.

**Confirm these are your rules, exactly.**

## 3. Six days you can open on your own chart

Each of these is a real day out of the ten years. None of them was picked by hand: each one is the answer to a written rule, and the rule is printed with the day so you can see there was no choosing involved.

To follow along: open the stock on a 15-minute chart, put a Fixed Range Volume Profile over 09:15 to 11:15 with Row Size 24, and put the daily chart beside it for the two days before.

Every one of these days was also RE-RUN through the machine while this pack was being written, and the answer was compared with what the machine wrote down on the day it ran. Each day says how many pieces of its record matched.

### 3a. HDFCBANK -- Wednesday 10 June 2026 -- a winner

*Why this day is here: the day the architect named for this slot. It QUALIFIES on the ledger's own record: the trade was taken, it reached the target, it made money, it was not a gap entry, and it falls inside the last three months of the run.*

**Step 1 -- the bias, settled before the day opened.**

The two daily candles the machine looked at:

| | Open | High | Low | Close |
|---|---:|---:|---:|---:|
| P -- Monday 8 June 2026 | Rs 738.00 | Rs 741.50 | Rs 734.50 | Rs 738.65 |
| C -- Tuesday 9 June 2026 | Rs 739.45 | Rs 743.95 | Rs 732.30 | Rs 738.35 |

P's body runs from Rs 738.00 to Rs 738.65.

C's high (Rs 743.95) went above P's high (Rs 741.50) AND C's low (Rs 732.30) went below P's low (Rs 734.50). Both sides swept -- your Rule 3. So the machine read C's one-minute candles in order and found that the HIGH broke first, with C closing at Rs 738.35 inside P's body. That makes the day BULLISH.

**Bias: BULLISH** -- so long trades only. Nothing that happened during the day could change it.

**Step 2 -- the volume profile, fixed at 11:15.**

Between 09:15 and 11:14 the stock traded between Rs 736.40 and Rs 745.50, on 15,220,350 shares across 120 one-minute candles.

That range is 182 ticks wide at this stock's tick size of Rs 0.05. Asking for 24 rows gives 8 ticks in each row, which draws **23 rows** -- count them on your own chart.

The busiest row runs from Rs 739.60 to Rs 740.00, so the **POC is Rs 739.80** -- the middle of that row.

**Step 3 -- 11:15, and what the machine was waiting for.**

The 11:00-11:15 candle closed at Rs 738.20, below the POC. That is the side of the POC your rule wants, so the machine was armed straight away and waiting for the entry.

Then, candle by candle:

| Candle closing at | Close | Against the POC | What the machine did |
|---|---:|---|---|
| 11:30 | Rs 740.95 | above | **this is the entry** -- bought at this close |

**Step 4 -- the trade.**

| | |
|---|---|
| Entered at the close of the 11:30 candle | **Rs 740.95** |
| Stop | **Rs 738.10** -- the low of the entry candle, with no buffer |
| Distance from entry to stop | Rs 2.85 |
| Target, three times that distance | **Rs 749.50** |

The number of shares is the fixed risk divided by that distance, rounded down: **350 shares**. At the entry price that is Rs 259,332.50 of stock bought, with Rs 997.50 genuinely at risk.

**Step 5 -- how it ended.** The target was reached on the candle closing at 13:15. The fill is the target itself, Rs 749.50, even though the candle ran past it.

| | |
|---|---:|
| Profit or loss on the shares | Rs 2,992.50 |
| The round-trip cost | -Rs 100.00 |
| **What the day was worth** | **Rs 2,892.50** |

**Does the machine's own record agree?** This day was re-run from the stored candles while the pack was written and compared with the row the ten-year run wrote: **38 of 38** pieces of the record match.

### 3b. HINDZINC -- Thursday 30 July 2026 -- a stop-out

*Why this day is here: a stop-out from the last day the machine walked, chosen so it is a TYPICAL one and not a freak: of that day's stop-outs, the one whose distance from entry to stop is nearest the middle distance of all the run's trades. Ties go to the stock this run traded most often.*

**Step 1 -- the bias, settled before the day opened.**

The two daily candles the machine looked at:

| | Open | High | Low | Close |
|---|---:|---:|---:|---:|
| P -- Tuesday 28 July 2026 | Rs 530.05 | Rs 530.90 | Rs 524.00 | Rs 526.90 |
| C -- Wednesday 29 July 2026 | Rs 529.80 | Rs 541.10 | Rs 527.30 | Rs 536.70 |

P's body runs from Rs 526.90 to Rs 530.05.

C closed at Rs 536.70, above the top of P's body (Rs 530.05). That is your Rule 1, a breakout on the close: BULLISH.

**Bias: BULLISH** -- so long trades only. Nothing that happened during the day could change it.

**Step 2 -- the volume profile, fixed at 11:15.**

Between 09:15 and 11:14 the stock traded between Rs 533.50 and Rs 542.00, on 958,338 shares across 120 one-minute candles.

That range is 170 ticks wide at this stock's tick size of Rs 0.05. Asking for 24 rows gives 7 ticks in each row, which draws **25 rows** -- count them on your own chart.

The busiest row runs from Rs 537.35 to Rs 537.70, so the **POC is Rs 537.525** -- the middle of that row.

**Step 3 -- 11:15, and what the machine was waiting for.**

The 11:00-11:15 candle closed at Rs 535.50, below the POC. That is the side of the POC your rule wants, so the machine was armed straight away and waiting for the entry.

Then, candle by candle:

| Candle closing at | Close | Against the POC | What the machine did |
|---|---:|---|---|
| 11:30 | Rs 538.00 | above | **this is the entry** -- bought at this close |

**Step 4 -- the trade.**

| | |
|---|---|
| Entered at the close of the 11:30 candle | **Rs 538.00** |
| Stop | **Rs 535.50** -- the low of the entry candle, with no buffer |
| Distance from entry to stop | Rs 2.50 |
| Target, three times that distance | **Rs 545.50** |

The number of shares is the fixed risk divided by that distance, rounded down: **400 shares**. At the entry price that is Rs 215,200.00 of stock bought, with Rs 1,000.00 genuinely at risk.

**Step 5 -- how it ended.** The stop was hit on the candle closing at 12:00. The fill is the stop itself, Rs 535.50.

| | |
|---|---:|
| Profit or loss on the shares | -Rs 1,000.00 |
| The round-trip cost | -Rs 100.00 |
| **What the day was worth** | **-Rs 1,100.00** |

**Does the machine's own record agree?** This day was re-run from the stored candles while the pack was written and compared with the row the ten-year run wrote: **38 of 38** pieces of the record match.

### 3c. TIINDIA -- Monday 27 July 2026 -- a gap day

*Why this day is here: the day the architect named for this slot, and the LAST gap entry of the whole ten years. It QUALIFIES: the ledger records it as a gap entry.*

**Step 1 -- the bias, settled before the day opened.**

The two daily candles the machine looked at:

| | Open | High | Low | Close |
|---|---:|---:|---:|---:|
| P -- Thursday 23 July 2026 | Rs 2,903.70 | Rs 2,921.40 | Rs 2,816.50 | Rs 2,824.50 |
| C -- Friday 24 July 2026 | Rs 2,800.00 | Rs 2,821.10 | Rs 2,746.60 | Rs 2,767.00 |

P's body runs from Rs 2,824.50 to Rs 2,903.70.

C closed at Rs 2,767.00, below the bottom of P's body (Rs 2,824.50). That is your Rule 1, a breakout on the close: BEARISH.

**Bias: BEARISH** -- so short trades only. Nothing that happened during the day could change it.

**Step 2 -- the volume profile, fixed at 11:15.**

Between 09:15 and 11:14 the stock traded between Rs 2,754.60 and Rs 2,865.00, on 132,143 shares across 120 one-minute candles.

That range is 1,104 ticks wide at this stock's tick size of Rs 0.10. Asking for 24 rows gives 46 ticks in each row, which draws **24 rows** -- count them on your own chart.

The busiest row runs from Rs 2,846.60 to Rs 2,851.20, so the **POC is Rs 2,848.90** -- the middle of that row.

**Step 3 -- 11:15, and what the machine was waiting for.**

The 11:00-11:15 candle closed at Rs 2,843.40, below the POC. On a bearish day that is the wrong side, so the machine could not arm yet: it had to see a 15-minute candle close ABOVE the POC first.

Then, candle by candle:

| Candle closing at | Close | Against the POC | What the machine did |
|---|---:|---|---|
| 11:30 | Rs 2,854.10 | above | this is the close it was waiting for: now armed |
| 11:45 | Rs 2,851.60 | above | armed, but this close is not a trigger -- waiting |
| 12:00 | Rs 2,854.20 | above | armed, but this close is not a trigger -- waiting |
| 12:15 | Rs 2,850.80 | above | armed, but this close is not a trigger -- waiting |
| 12:30 | Rs 2,842.10 | below | **this is the entry** -- sold short at this close |

**Step 4 -- the trade.**

| | |
|---|---|
| Entered at the close of the 12:30 candle | **Rs 2,842.10** |
| Stop | **Rs 2,850.80** -- the entry candle opened clean past the POC and never traded back to it, so the stop is the PREVIOUS 15-minute candle's close |
| Distance from entry to stop | Rs 8.70 |
| Target, three times that distance | **Rs 2,816.00** |

The number of shares is the fixed risk divided by that distance, rounded down: **114 shares**. At the entry price that is Rs 323,999.40 of stock sold short, with Rs 991.80 genuinely at risk.

**Step 5 -- how it ended.** The stop was hit on the candle closing at 13:00. The fill is the stop itself, Rs 2,850.80.

| | |
|---|---:|
| Profit or loss on the shares | -Rs 991.80 |
| The round-trip cost | -Rs 100.00 |
| **What the day was worth** | **-Rs 1,091.80** |

**Does the machine's own record agree?** This day was re-run from the stored candles while the pack was written and compared with the row the ten-year run wrote: **38 of 38** pieces of the record match.

### 3d. POLYCAB -- Wednesday 29 July 2026 -- a day the 11:15 candle closed exactly ON the POC

*Why this day is here: the most recent day in the whole run where the 11:15 candle closed at exactly the POC price -- your Round-3 answer A, the one where the first candle only picks the side. Where more than one stock did that on the same day, the one that went on to take a trade is shown, because a day with no trade cannot show the rest of the rule.*

**Step 1 -- the bias, settled before the day opened.**

The two daily candles the machine looked at:

| | Open | High | Low | Close |
|---|---:|---:|---:|---:|
| P -- Monday 27 July 2026 | Rs 8,956.00 | Rs 9,050.00 | Rs 8,956.00 | Rs 9,010.00 |
| C -- Tuesday 28 July 2026 | Rs 9,061.00 | Rs 9,143.50 | Rs 9,001.00 | Rs 9,121.50 |

P's body runs from Rs 8,956.00 to Rs 9,010.00.

C closed at Rs 9,121.50, above the top of P's body (Rs 9,010.00). That is your Rule 1, a breakout on the close: BULLISH.

**Bias: BULLISH** -- so long trades only. Nothing that happened during the day could change it.

**Step 2 -- the volume profile, fixed at 11:15.**

Between 09:15 and 11:14 the stock traded between Rs 8,975.00 and Rs 9,169.50, on 108,708 shares across 120 one-minute candles.

That range is 389 ticks wide at this stock's tick size of Rs 0.50. Asking for 24 rows gives 16 ticks in each row, which draws **25 rows** -- count them on your own chart.

The busiest row runs from Rs 9,007.00 to Rs 9,015.00, so the **POC is Rs 9,011.00** -- the middle of that row.

**Step 3 -- 11:15, and what the machine was waiting for.**

The 11:00-11:15 candle closed at Rs 9,011.00, exactly ON the POC. Exactly on it -- which is the case you answered with option A. No side yet: the first candle to close clearly above or clearly below picks the side, and that candle is never itself the entry.

Then, candle by candle:

| Candle closing at | Close | Against the POC | What the machine did |
|---|---:|---|---|
| 11:30 | Rs 9,010.00 | below | the side is set by this close, and it arms the day at the same time |
| 11:45 | Rs 9,029.00 | above | **this is the entry** -- bought at this close |

**Step 4 -- the trade.**

| | |
|---|---|
| Entered at the close of the 11:45 candle | **Rs 9,029.00** |
| Stop | **Rs 9,009.00** -- the low of the entry candle, with no buffer |
| Distance from entry to stop | Rs 20.00 |
| Target, three times that distance | **Rs 9,089.00** |

The number of shares is the fixed risk divided by that distance, rounded down: **50 shares**. At the entry price that is Rs 451,450.00 of stock bought, with Rs 1,000.00 genuinely at risk.

**Step 5 -- how it ended.** Neither the stop nor the target was touched all day, so the position was closed at the close of the 15:00-15:15 candle, Rs 9,050.00.

| | |
|---|---:|
| Profit or loss on the shares | Rs 1,050.00 |
| The round-trip cost | -Rs 100.00 |
| **What the day was worth** | **Rs 950.00** |

**Does the machine's own record agree?** This day was re-run from the stored candles while the pack was written and compared with the row the ten-year run wrote: **38 of 38** pieces of the record match.

### 3e. SBIN -- Thursday 30 July 2026 -- a day with no trade at all

*Why this day is here: a day from the last day the machine walked where no rule fired on the two daily candles, so the machine kept the bias it already had -- and where no trade followed. Ties go to the stock this run traded most often.*

**Step 1 -- the bias, settled before the day opened.**

The two daily candles the machine looked at:

| | Open | High | Low | Close |
|---|---:|---:|---:|---:|
| P -- Tuesday 28 July 2026 | Rs 1,018.00 | Rs 1,022.00 | Rs 1,008.30 | Rs 1,013.20 |
| C -- Wednesday 29 July 2026 | Rs 1,020.00 | Rs 1,020.20 | Rs 1,012.00 | Rs 1,013.70 |

P's body runs from Rs 1,013.20 to Rs 1,018.00.

C's high did not go above P's high and C's low did not go below P's low: C sits entirely inside P. That is an inside bar, and your first rule says the bias does not change -- so the machine kept the bias it was already carrying. It was last SET for trading on Wednesday 29 July 2026, when your Rule 1 (a breakout on the close) fired on that day's own pair of candles, and nothing since has moved it.

**Bias: BEARISH** -- so short trades only. Nothing that happened during the day could change it.

**Step 2 -- the volume profile, fixed at 11:15.**

Between 09:15 and 11:14 the stock traded between Rs 1,007.60 and Rs 1,016.90, on 1,790,868 shares across 120 one-minute candles.

That range is 93 ticks wide at this stock's tick size of Rs 0.10. Asking for 24 rows gives 4 ticks in each row, which draws **24 rows** -- count them on your own chart.

The busiest row runs from Rs 1,014.40 to Rs 1,014.80, so the **POC is Rs 1,014.60** -- the middle of that row.

**Step 3 -- 11:15, and what the machine was waiting for.**

The 11:00-11:15 candle closed at Rs 1,014.40, below the POC. On a bearish day that is the wrong side, so the machine could not arm yet: it had to see a 15-minute candle close ABOVE the POC first.

Then, candle by candle:

| Candle closing at | Close | Against the POC | What the machine did |
|---|---:|---|---|
| 11:30 | Rs 1,014.90 | above | this is the close it was waiting for: now armed |
| 11:45 | Rs 1,016.10 | above | armed, but this close is not a trigger -- waiting |
| 12:00 | Rs 1,016.00 | above | armed, but this close is not a trigger -- waiting |
| 12:15 | Rs 1,017.10 | above | armed, but this close is not a trigger -- waiting |
| 12:30 | Rs 1,018.00 | above | armed, but this close is not a trigger -- waiting |
| 12:45 | Rs 1,022.70 | above | armed, but this close is not a trigger -- waiting |
| 13:00 | Rs 1,024.20 | above | armed, but this close is not a trigger -- waiting |
| 13:15 | Rs 1,023.70 | above | armed, but this close is not a trigger -- waiting |
| 13:30 | Rs 1,024.10 | above | armed, but this close is not a trigger -- waiting |
| 13:45 | Rs 1,026.00 | above | armed, but this close is not a trigger -- waiting |
| 14:00 | Rs 1,023.60 | above | armed, but this close is not a trigger -- waiting |
| 14:15 | Rs 1,021.80 | above | armed, but this close is not a trigger -- waiting |
| 14:30 | Rs 1,021.80 | above | armed, but this close is not a trigger -- waiting |
| 14:45 | Rs 1,023.90 | above | armed, but this close is not a trigger -- waiting |
| 15:00 | Rs 1,023.30 | above | armed, but this close is not a trigger -- waiting |

**Step 4 -- no trade.** The machine was armed and waiting all day, but no 15-minute candle ever closed on the far side of the POC, so there was never an entry. Nothing was bought or sold, and the day cost nothing.

**Does the machine's own record agree?** This day was re-run from the stored candles while the pack was written and compared with the row the ten-year run wrote: **38 of 38** pieces of the record match.

### 3f. BAJFINANCE -- Friday 10 April 2026 -- the day that settles one open question

*Why this day is here: a day where the two possible ways of rounding the profile's tick count draw a DIFFERENT number of rows -- so counting the rows on your own chart settles a question the specification still calls provisional. Of the days in the span's last calendar year where that happens, this is the one with the widest gap between the two row counts, and on it the POC itself moves.*

**Step 1 -- the bias, settled before the day opened.**

The two daily candles the machine looked at:

| | Open | High | Low | Close |
|---|---:|---:|---:|---:|
| P -- Wednesday 8 April 2026 | Rs 890.00 | Rs 926.00 | Rs 881.00 | Rs 915.05 |
| C -- Thursday 9 April 2026 | Rs 902.00 | Rs 913.40 | Rs 891.40 | Rs 903.25 |

P's body runs from Rs 890.00 to Rs 915.05.

C's high did not go above P's high and C's low did not go below P's low: C sits entirely inside P. That is an inside bar, and your first rule says the bias does not change -- so the machine kept the bias it was already carrying. It was last SET for trading on Thursday 9 April 2026, when your Rule 1 (a breakout on the close) fired on that day's own pair of candles, and nothing since has moved it.

**Bias: BULLISH** -- so long trades only. Nothing that happened during the day could change it.

**Step 2 -- the volume profile, fixed at 11:15.**

Between 09:15 and 11:14 the stock traded between Rs 912.30 and Rs 925.35, on 4,286,154 shares across 120 one-minute candles.

That range is 130 ticks wide at this stock's tick size of Rs 0.10. Asking for 24 rows gives 5 ticks in each row, which draws **26 rows** -- count them on your own chart.

The busiest row runs from Rs 918.30 to Rs 918.80, so the **POC is Rs 918.55** -- the middle of that row.

**Step 3 -- 11:15, and what the machine was waiting for.**

The 11:00-11:15 candle closed at Rs 923.80, above the POC. On a bullish day that is the wrong side, so the machine could not arm yet: it had to see a 15-minute candle close BELOW the POC first.

Then, candle by candle:

| Candle closing at | Close | Against the POC | What the machine did |
|---|---:|---|---|
| 11:30 | Rs 923.70 | above | nothing changes -- still waiting |
| 11:45 | Rs 921.70 | above | nothing changes -- still waiting |
| 12:00 | Rs 921.85 | above | nothing changes -- still waiting |
| 12:15 | Rs 921.00 | above | nothing changes -- still waiting |
| 12:30 | Rs 920.65 | above | nothing changes -- still waiting |
| 12:45 | Rs 919.70 | above | nothing changes -- still waiting |
| 13:00 | Rs 916.60 | below | this is the close it was waiting for: now armed |
| 13:15 | Rs 918.10 | below | armed, but this close is not a trigger -- waiting |
| 13:30 | Rs 917.70 | below | armed, but this close is not a trigger -- waiting |
| 13:45 | Rs 920.40 | above | **this is the entry** -- bought at this close |

**Step 4 -- the trade.**

| | |
|---|---|
| Entered at the close of the 13:45 candle | **Rs 920.40** |
| Stop | **Rs 917.30** -- the low of the entry candle, with no buffer |
| Distance from entry to stop | Rs 3.10 |
| Target, three times that distance | **Rs 929.70** |

The number of shares is the fixed risk divided by that distance, rounded down: **322 shares**. At the entry price that is Rs 296,368.80 of stock bought, with Rs 998.20 genuinely at risk.

**Step 5 -- how it ended.** The stop was hit on the candle closing at 14:00. The fill is the stop itself, Rs 917.30.

| | |
|---|---:|
| Profit or loss on the shares | -Rs 998.20 |
| The round-trip cost | -Rs 100.00 |
| **What the day was worth** | **-Rs 1,098.20** |

**Step 6 -- and the question this day is really here to settle.**

When the machine works out how many ticks wide the profile is, the answer on this day landed exactly halfway between two whole numbers. There are two normal ways to round a number that sits exactly halfway, and on most days they give the same profile. On this day they do not:

| | Ticks | Ticks per row | Rows drawn | POC |
|---|---:|---:|---:|---:|
| What the machine did | 130 | 5 | **26** | **Rs 918.55** |
| The other way of rounding | 131 | 6 | **22** | **Rs 918.60** |

So the two ways of rounding put the POC Rs 0.05 apart on this day.

On this particular day the trade comes out the same either way, so nothing here turns on it. On other days it would not.

**This is the one thing in the specification we have not been able to settle without you.** In the last calendar year the machine walked there are 51 days like this one, 13 of them with the POC in a different place under the two roundings. This is the one where the two row counts are furthest apart, which makes it the easiest to read off a chart and be sure.

**What we need: open BAJFINANCE on Friday 10 April 2026, put the Fixed Range Volume Profile over 09:15 to 11:15 with Row Size 24, and count the rows in the box.** If you count 26, the machine is already right. If you count 22, we change one line and re-run.

**Does the machine's own record agree?** This day was re-run from the stored candles while the pack was written and compared with the row the ten-year run wrote: **38 of 38** pieces of the record match.

### And two counts you asked us to make

**Days where the 11:15 candle closed exactly ON the POC: 4,151** out of the 406,488 stock-days the machine was able to judge. That is the case you answered with option A -- the first candle only picks the side. 2,246 of them went on to take a trade, so the rule is not a curiosity in the corner of the specification: it decided real money.

**Outside-bar days where BOTH sides broke inside the same one-minute candle: 62** in ten years. That is the tie you settled in Round 3 when you said the colour of that one-minute candle does not matter and that you look at where the DAY closed against the previous day's body. It is not zero, so your answer decided real days: 62 of them came out bullish and 0 bearish -- and that split is your own rule showing through, not a coincidence: a close INSIDE the previous day's body goes bullish, and a close outside it was already decided by Rule 1 before the tie was ever reached, so on a tie there is nothing left for the bearish side to catch. The earliest was BLUESTARCO on Friday 16 December 2016 and the latest GLENMARK on Monday 27 July 2026.

**Which of your bias rules decided the days the machine judged.**

| Rule | Days it decided |
|---|---:|
| Rule 1 -- a breakout on the close | 285,574 |
| no stored one-minute data for the stock that day -- not judged | 73,841 |
| Inside bar -- yesterday's bias kept | 64,819 |
| Rule 2 -- a single sweep | 62,385 |
| Rule 3 -- both sides swept, decided on the one-minute candles | 6,724 |
| the day before failed a data check, so the bias could not be settled -- not judged | 210 |
| Rule 3 -- both sides swept inside ONE one-minute candle | 62 |
| Rule 3, but no one-minute data that day -- bias kept | 30 |
| a demerger sat inside the pair, so no bias could be computed -- not judged | 30 |
| Rule 3, but no one-minute candle broke either side -- bias kept | 5 |

The days above were chosen by what happened on them rather than by which rule decided them, so they do not cover every rule: Rule 2 -- a single sweep is not among them. Said out loud rather than left to be noticed.

## 4. The years

One row per calendar year. Each row is that year's trades alone.

| Year | Trades | Won | What the year made or lost |
|---|---:|---:|---:|
| 2016 | 3,530 | 30.74% | **-Rs 225,598.97** |
| 2017 | 14,868 | 29.77% | **-Rs 1,681,333.77** |
| 2018 | 16,060 | 30.86% | **-Rs 1,178,849.98** |
| 2019 | 17,016 | 30.12% | **-Rs 1,989,896.29** |
| 2020 | 18,160 | 30.78% | **-Rs 1,890,254.58** |
| 2021 | 19,195 | 31.36% | **-Rs 1,718,596.73** |
| 2022 | 21,067 | 31.88% | **-Rs 1,660,156.74** |
| 2023 | 20,796 | 31.38% | **-Rs 2,098,184.07** |
| 2024 | 21,732 | 32.90% | **-Rs 1,300,023.08** |
| 2025 | 22,416 | 32.80% | **-Rs 1,943,790.55** |
| 2026 | 13,505 | 32.88% | **-Rs 1,149,333.44** |

11 of the 11 years lost money. Not one of them made any. The first and the last are part-years: the data starts in October of the first and the run stops at the end of July in the last, so neither is a full twelve months and neither should be read as one.

### The worst stretch

**Drawdown** means the drop from the best the account had ever been to the worst it got afterwards -- the money you would have watched disappear if you had sat through it.

The worst stretch here ran from its best day ever, Thursday 6 October 2016, down to Thursday 30 July 2026, and it took **Rs 16,852,007.80** across 2,424 trading days. It never came back inside the ten years.

Put in the plainest terms: the account started with Rs 100,000.00 and the running total of the trades ends at -Rs 16,736,018.20. A real account cannot go below zero and would have stopped a long way before that; the machine keeps adding because you asked to see the arithmetic with no limits on it, and hiding the rest would have answered your question for you.

## 5. What the machine did NOT do

Everything on the pages before this is true. This page is the list of ways in which it is easier than the real thing. None of it is hidden in a footnote somewhere else.

**The fills are perfect, and yours would not be.** An entry fills exactly at the 15-minute candle's close. A stop fills exactly at the stop price even when the candle blew straight through it, and a target fills exactly at the target price for the same reason. There is no slippage, no partial fill and no allowance for the market moving away from you. In real trading that difference costs money, and on the stops it costs money every time.

**There was no limit on how much money was in play.** You asked for the honest numbers with no limits, so the machine took every signal on every stock at the same time, whether or not the money existed. At its busiest it held **90 positions at once**. At its largest it had **Rs 42,148,077.61** of stock open at a single moment -- about **4.21 crore rupees** -- which is 421.4808 times the Rs 100,000.00 the account started with. No real account could have carried that, and the machine was never asked to check.

**We have not marked which trades your money could not have taken.** That needs one number from you (it is the first question on the last page). Until it arrives no trade is flagged, because a flag against a figure we guessed would be our opinion wearing your name.

**The list of stocks is today's list, walked backwards.** The machine ran the 204 stocks that are in the futures-and-options list NOW, all the way back to 2016. A stock that was in the list in 2017 and has since dropped out is not here at all, and a stock that only joined in 2024 was still traded from 2016. That flatters any strategy that trades large, liquid names, and it is our engineering shortcut, not your instruction.

**The cost is a flat Rs 100.00 a trade.** That is the figure you gave us. It does not vary with the size of the trade, and a trade in ten shares pays the same as a trade in thirty thousand.

**One trade per stock per day, and the money never compounds.** The first entry uses that stock up for the day, and every trade risks the same rupee amount from beginning to end regardless of what the account is worth. The running total adds up; it does not grow on itself.

**The machine could not use every day.** Of every stock-day in the stored data, **93.9317%** passed the checks that say the prices and volumes really are that stock's, on that day, at the right scale. The rest were REFUSED and counted -- never quietly traded on and never quietly dropped. Of the 495,312 stock-days the run walked, 406,488 were judged and 88,824 were refused, and the refusals are broken down by reason in the technical report.

**And two things that are still open.** The rounding question on day 3f above, and the two questions on the last page. Nothing in this pack is blocked on any of them; they are open because they are yours to answer.

## 6. What we need from you

### Two questions still waiting

Neither of these has held anything up. They are open because they are yours.

**One -- which money figure should decide whether a trade was affordable?** The machine took every signal without asking whether the cash existed. To go back and mark the trades you could NOT actually have taken, we need to know what to measure them against: the cash in the account, or the larger amount an intraday margin would have allowed, and how much larger. We have not guessed, and the machine carries this sentence wherever the question would otherwise be answered silently:

> capital-infeasibility flags NOT computed -- the trader's Q43 answer is pending

**Two -- one worked example needs your confirmation.** In the written specification there is an example of the gap rule -- where the entry candle jumps clean past the POC and the stop comes from the previous candle's close instead of from the entry candle. The numbers in that example only fit together one way, and we have taken the reading that keeps every price you ever quoted intact. If our reading is wrong, that is a change to your entry rule, and the honest consequence is that everything in this pack is computed again from scratch. The run itself carries the note:

> PENDING TRADER CONFIRMATION OF Q44 (gap-rule example, POC 2032)

### And two things to confirm

**Confirm the rules on page 2 are yours, exactly.** If one line is wrong, say which line -- the machine is built so that a rule change is a change to one place and a re-run, not a rebuild.

**Count the rows on BAJFINANCE, Friday 10 April 2026.** Day 3f explains why. If the box has 26 rows we are already right; if it has 22 we change one line and run it again.

### Three ways forward

These are set out flatly and in no order. There is no recommendation attached to any of them, and there will not be one: it is your strategy and your money.

**Retire it.** The arithmetic on page 1 is what these rules did over ten years, across every stock, with no discretion applied. If you conclude that the edge you trade by is the judgement you add on top of these rules rather than the rules themselves, then this machine has answered the question it was built to answer, and it can be put down. Nothing is lost that was not already spent finding out.

**Change it.** The rules are yours to change, and the machinery is now yours too. A different target multiple, a different profile window, a filter on which days to trade, a stop placed somewhere else, entries on a different candle -- any of these is a change to one place in the code and a re-run over the same ten years, and the answer comes back in hours rather than months. Every number in this pack would be recomputed the same way and would be as checkable as these are. What we cannot do is choose the change for you.

**Take it live knowing the arithmetic.** The live half of the tool -- the screener that watches the market and alerts you when a signal fires -- is designed and specified and is on hold, waiting for this decision. It would run the same code that produced these numbers. If you take this path, you take it knowing what page 1 says: over these ten years, on these rules, taking every signal, the arithmetic came out as it came out.

---

Everything in this pack is computed from the machine's own record of the run (ledger `c70a72b097879914...`) by `src/acumen/trader_pack.py`. Nothing in it is typed by hand. The long technical version, with every figure and every check, is `docs/reports/chunk9b_backtest_report.md`.
