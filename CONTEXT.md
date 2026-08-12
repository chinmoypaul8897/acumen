# CONTEXT.md — ACUMEN INTELLIGENCE · Master Specification

**Version 2.1 · 8 August 2026 · THIS FILE IS LAW.**
Every build/review session reads this before touching code. Nothing here may be changed by any Claude Code session — spec changes flow only through the architect (the Cowork chat), arrive as a new version of this file, and are logged in §10. If reality and this file disagree, STOP and write it to QUESTIONS.md.

## Table of contents

1. Project identity, people, prime rules
2. Product scope (v1)
3. STRATEGY SPECIFICATION (the law of the trading logic)
   - 3.1 Universe & sessions
   - 3.2 Bias engine (daily)
   - 3.3 Volume profile & POC engine
   - 3.4 Signal & trade engine (15-min)
   - 3.5 Position sizing, costs, exits accounting
4. DATA SPECIFICATION (verified facts, sources, limits)
   - 4.1 Daily layer (NSE files)
   - 4.2 Corporate-action engine
   - 4.3 Intraday layer (SmartAPI)
   - 4.4 Live polling layer
   - 4.5 Quality gates
   - 4.6 Minute-lake final state
   - 4.7 Live-mode validity
5. TradingView replication facts (why our POC matches his chart)
6. Architecture & repo
7. Engineering defaults (not trader-specified — disclosed, changeable)
8. Golden fixtures (the tests that define "correct")
9. OPEN ITEMS REGISTRY (the only permitted unknowns)
10. Source documents & version log

---

## 1. Project identity, people, prime rules

**Acumen Intelligence** — a backtester + live screener for one specific intraday strategy on NSE F&O stocks, owned by a discretionary trader.

People: **Trader** (strategy owner; not technical; communicates in simple English through Paul; his strategy is FROZEN — we implement, never "improve"). **Paul** (technical owner/operator; runs all sessions; relays trader Q&A). **Architect** (Claude, in the Cowork chat; keeper of this spec; writes chunk prompts). **Builder/Reviewer** (Claude Code sessions in this repo).

Prime rules, in force for every session:
- **R1 — No assumptions.** Anything this file does not answer → write to QUESTIONS.md, halt that piece. Never decide silently. This is a financial tool; a silent guess here loses real money.
- **R2 — The strategy is the trader's.** No new indicators, no filters, no optimizations, no "better" exits. Deviations from §3 are bugs by definition.
- **R3 — Tests define done.** A chunk without passing golden fixtures (§8) does not exist.
- **R4 — Read-only trading APIs.** No order-placement code anywhere in this repo in v1.

## 2. Product scope (v1)

- **Backtester**: runs §3 over §4 data for all F&O stocks, max history (min 5 years — trader's Q36), produces a TradingView-Strategy-Tester-style report (equity curve, win rate, drawdowns, trade list — per trader's PDF pages 7–14).
- **Live screener**: during market hours evaluates §3 in real time across the universe; on signal shows stock, side, entry, SL, target; alerts to **dashboard + Telegram** (trader's Q37b: both).
- **NOT in v1**: auto order placement (Q37a agreed), options/futures backtesting (Q35 agreed: cash prices only), any strategy variation.
- Trader trades manually in Groww/Angel One off our alerts; he may use any segment (MIS/futures/options) himself.

## 3. STRATEGY SPECIFICATION

### 3.1 Universe & sessions

- Universe: **all NSE F&O stock underlyings** (~210; source §4.1). Indexes are NOT traded and need no data (trader R1-Q10: volume profile impossible on indexes; skip them entirely).
- Bias is computed **per stock on that stock's own daily chart** (R1-Q4). No index bias, no market-wide filter.
- Session: NSE cash, 09:15–15:30 IST. Trading window for entries: after 11:15 up to and including the 15-min candle that closes at **15:00** (R2-Q30). Square-off everything at **15:15** (R1-Q17/Q18, R2-Q30).
- Days: NSE trading days only (holiday calendar §4.1). "Previous day" always means previous **trading** day. Non-standard sessions (Muhurat etc.) are excluded (§7 default).
- No day-type exclusions: trader confirmed twice (R1 final, R2 final) — no expiry-day/results-day/news-day filters.

### 3.2 Bias engine (daily)

**Inputs**: corporate-action-adjusted daily OHLC of the stock itself — the FULL §4.2 factor set (splits, bonuses, rights, special dividends; nothing for ordinary dividends/buybacks). Adjustment is applied **pairwise**: for the pair (P, C), P's prices are multiplied by the factors of events with ex-date after P and on/before C ("P in C's scale"). This is equivalent to comparing on a fully adjusted series and keeps every comparison scale-consistent.

**Which candles (R2-Q28, confirmed with Wednesday example):** to trade on day D, take candle(D−1) as **current** and candle(D−2) as **previous** (both trading days). Result = bias for day D, frozen before D's open. Nothing during D changes D's bias.

Definitions (from previous candle P): `bodyMax = max(P.open, P.close)` · `bodyMin = min(P.open, P.close)`. Current candle C.

**Evaluation order (trader's PDF, page 1–2):**
1. **Inside bar**: `C.high <= P.high AND C.low >= P.low` → bias unchanged (carry last known bias). Note: touching the extreme counts as inside (operators exactly as written).
2. **Rule 1 — breakout on close**: `C.close > bodyMax` → BULLISH. `C.close < bodyMin` → BEARISH. (Strict inequalities.)
3. **Rule 2 — simple sweep**: BULLISH if `C.low < P.low AND C.high <= P.high AND C.close >= bodyMin`. BEARISH if `C.high > P.high AND C.low >= P.low AND C.close <= bodyMax`.
4. **Rule 3 — double sweep (outside bar)**: applies when `C.high > P.high AND C.low < P.low`. Look at day C's **1-minute** data to find which side of P's range broke FIRST:
   - P.high broken first AND `C.close >= bodyMin` → BULLISH.
   - P.low broken first AND `C.close <= bodyMax` → BEARISH.
   - "Broken" at 1-min level = 1-min candle's high > P.high (resp. low < P.low), scanned in time order.
   - **Tie case** (both sides break within the SAME 1-min candle — R2-Q31 + Round-3 Q38/Q39, TRADER-FINAL): the decisive 1-min candle's direction is **IRRELEVANT** — red, green and doji all follow ONE rule (this OVERTURNS the earlier color-based assumption; the trader rejected the green mirror and the doji-carry explicitly). Resolve by the DAILY close against the body, with bullish precedence: `C.close >= bodyMin` → BULLISH; else `C.close <= bodyMax` → BEARISH (the bearish branch is unreachable for closes inside the body — bullish precedence — and closes outside the body were already decided by Rule 1). Worked example (trader-certified twice): body 2010–2040, daily close 2020 → BULLISH regardless of the 1-min candle's color.
5. **No rule fires** → carry last known bias. If Bullish and Bearish conditions ever both evaluate true (should be impossible), Bullish takes precedence (trader's PDF).

**Outside-bar precedence note (spec decision, from the PDF's own text):** rules are evaluated in the order above, so an outside bar whose close lands BEYOND the body (`close > bodyMax` or `< bodyMin`) is decided by **Rule 1** — the Rule-3 first-break test only ever decides candles whose close lands INSIDE the body `[bodyMin, bodyMax]`. Basis: the PDF says "if none of the Bullish or Bearish conditions for Rules 1, 2, or 3 are met → maintain last bias", i.e. the rule conditions co-evaluate; Rule 1's condition is met regardless of sweep order. This is verified with the trader at the chunk-4 gate via the F9 bias sequence.

**Seeding (R1-Q5)**: at history start, walk forward from the earliest data until a rule first produces a bias; before that, no trading for that stock.

**Missing 1-min data for a Rule-3 day** (old dates): keep last bias (documented plan, R1-Q6, trader did not object).

**Corporate actions**: pairwise adjustment as defined under Inputs above. **Demerger/spin-off with ex-date E**: no valid factor exists (NSE itself terminated RIL contracts rather than adjust — §4.2), so any bias pair that spans E is invalid → for trading days D where `D−1 == E` or `D−2 == E`: no bias update AND no trade in that stock on day D. From the first pair with both candles STRICTLY after E (i.e., day E+3 onward, whose pair is (E+2, E+1)), the normal engine resumes (carry from the pre-event bias is permitted; flagged in the validation pack for trader awareness).

### 3.3 Volume profile & POC engine

Computed once per stock per trading day, after 11:15, from that day's **1-minute** candles.

- **Window**: candles time-stamped 09:15 through 11:14 inclusive (= the session up to 11:15; the 15-min candle closing at 11:15 is INCLUDED — R1-Q11).
- **Row construction (TradingView's documented math, §5):** `top = max(high)`, `bottom = min(low)` over the window. `totalTicks = round((top − bottom)/tick)`; `tpr = totalTicks/N` rounded to a whole number (minimum 1), direction chosen so the realized row count is closest to requested N. Rows are stacked from `bottom` upward, each spanning `tpr` ticks; the leftover ticks (if any) form final rows of `tpr` ticks with the LAST row holding the remainder (may be smaller) — so realized row count can exceed N (TV's own example: 100 ticks, N=30 → tpr=3 → 33 rows of 3 + 1 row of 1 = 34 rows).
- **Row containment:** rows are half-open `[lo, hi)` EXCEPT the topmost row, which includes `top`. A zero-range bar (`high == low`) is a point: its full volume goes to the single row containing that price. If `top == bottom` for the whole window (frozen stock), the profile is one single-tick row.
- **POC value is a row MIDPOINT** — it may legally sit off the tick grid (half-tick values); all comparisons against it use full precision, never rounded prices.
- **Window CONFIRMED (Round-3 Q42, trader):** the 8-candle window (1-min stamps 09:15..11:14) is final; the 9-candle alternative is dead. **tpr TIE (Q-13, RULED):** when both rounding directions land equally close to N, keep the FINER profile (smaller tpr) — evidence: reproduces all 25 trader-calibrated values to 4e-13; trader's live row-count read (25) sits one from finer's 26 vs three from coarser's 22; TV's own documented example lands finer. **totalTicks rounding = half-even** (pinned interim; verification slot in the chunk-12 pack with our-data screenshots). **N = 24 trader-screenshot-confirmed.**
- **N (Row Size)** = **24 provisional** — trader's live calibration used 24 and matched; his personal everyday setting pending (OPEN-2 §9).
- **tickSize** = per symbol from instrument master (₹0.01 for lower-priced stocks after NSE's Jun-2024 tick reform; NEVER hardcode 0.05) — §4.3.
- **Volume spreading = PRORATA** (LOCKED by calibration 22-Jul-2026, 5/5 match vs trader's TradingView readings): each 1-min bar's volume is distributed across the rows its [low, high] range overlaps, proportionally to the price-overlap fraction (`overlap / (high − low)`, with `high==low` treated as one-tick span). Not "all at close", not "uniform".
- **POC** = midpoint price of the row with the maximum TOTAL volume. **Tie → the higher-priced row** (trader R1-Q9).
- POC is fixed for the rest of the day once computed.

### 3.4 Signal & trade engine (15-minute candles, one stock at a time)

Only in the direction of the day's bias (R1-Q24): bullish day → longs only; bearish day → shorts only. Candle color is irrelevant everywhere — only closes matter (R1-Q12).

**State machine (bullish day; bearish is the exact mirror):**

1. **Reference (11:15):** compare the CLOSE of the 11:00–11:15 candle with POC (R2-Q34a).
   - reference < POC → state ARMED.
   - reference > POC → state WAIT-BELOW: need a later 15-min close **strictly** < POC first (== POC does not arm; PDF wording "close below it"); when that happens → ARMED.
   - reference == POC exactly → **NO side (trader Q34b + Round-3 Q41, FINAL):** wait; the FIRST 15-min candle that closes strictly above or strictly below the POC sets the side — and ONLY sets it (it is never itself the entry — Q41 option A). First distinct close below → ARMED. First distinct close above → WAIT-BELOW (the Entry-2 path: need a close below, then buy on the close back above). OPEN-3 is resolved.
   - Reference candle missing but window valid → use the last available 1-min close ≤ 11:14 as reference (E10); none available → no trade.
2. **Trigger:** first 15-min candle (closing at 11:30 or later — the 11:15–11:30 candle is the first eligible — up to the 15:00 close, R2-Q30) that **closes strictly above POC** (`close > POC`; close == POC does NOT count — R2-Q34c) while state is ARMED. Entry price = that candle's **close** (R1-Q14).
   - A close == POC while ARMED: not a trigger, state stays ARMED, nothing is consumed.
   - Closes above POC while still WAIT-BELOW do NOT count or consume anything — "first cross" (R1-Q19b) is counted from the ARMED state only (this is exactly the PDF's Entry-2).
   - The first qualifying cross CONSUMES the stock-day even if the trade is unsizable (`entry == SL` or qty rounds to 0): no later entry that day; logged as a skipped signal. Max **one trade per stock per day** (R1-Q16); no re-entry after any exit.
3. **Stop loss:**
   - Normal: SL = entry candle's **low**, exactly, no buffer (R1-Q15; short: candle high — R1-Q2).
   - **Gap entry** (entry candle's low > POC, i.e. it opened beyond POC and never traded at/below it — R1-Q13b): SL = **the last traded price before the jump = the previous 15-min candle's close** (R2-Q33 option b; worked example: prior close 2028, entry 2042 → SL 2028).
   - Degenerate `entry == SL` → no trade (cannot size) — log to run report.
4. **Target:** TP = entry + 3 × (entry − SL). (Short: TP = entry − 3 × (SL − entry). The bearish PDF example's "TP 2004" was a confirmed typo — R1-Q1: correct value 1956.)
5. **Exit monitoring** (candles AFTER the entry candle): candle low ≤ SL → exit at SL. Candle high ≥ TP → exit at TP. **Both touched in the same candle → SL wins** (R1-Q20). Neither by 15:15 → square off at the 15:00–15:15 candle's close (R1-Q18).
6. **No-trade conditions** (from the PDF, follow from the state machine): price never gives a qualifying close across POC → no entry that day; WAIT-BELOW never resolves → no entry.

**Bearish-day mirror, explicit:** reference > POC → ARMED; reference < POC → WAIT-ABOVE (needs a close strictly > POC to arm). Trigger = first ARMED-state close strictly BELOW POC. Normal SL = entry candle's HIGH. Gap entry = entry candle's high < POC (never traded at/above it) → SL = previous 15-min candle's close. TP = entry − 3 × (SL − entry). POC tie rule (higher row) is side-independent — trader's R1-Q9 answer had no side condition. Everything else mirrors 1:1.

### 3.5 Position sizing, costs, accounting

- Capital: **₹1,00,000** (R1-Q21a).
- Sizing: **fixed ₹ risk per trade = ₹1,000** (Round-3 Q29, TRADER-FINAL; wired in config). `qty = floor(1000 / (entry − SL))` (shorts: `SL − entry`). qty == 0 → no trade, consumed + logged. OPEN-1 resolved.
- Costs: **₹100 flat per round-trip trade** (R1-Q23) subtracted from each trade's PnL.
- Backtest instrument: **cash equity prices** (R2-Q35 agreed).
- PnL per trade: `(exit − entry) × qty − 100` (long; mirrored short).
- No partial exits, no trailing (R1-Q27). No leverage/notional cap specified by trader — v1 does not cap notional but the report MUST disclose max notional used vs capital (§7, OPEN-6).
- **Portfolio semantics (Round-3 Q40, TRADER-FINAL — option d, "no limits, show me the honest numbers"):** the backtest takes ALL signals across all stocks concurrently, each sized by the fixed-₹-risk rule, NO capital/concurrency constraint. One equity curve: `capital + cumulative PnL` in trade-close order. The report MUST disclose: max concurrent positions, max aggregate notional vs ₹1L, distribution of daily concurrent-trade counts. **(Round-4 supersession, 06-Aug-2026): the per-trade capital-infeasibility flags Q40-d requested were RETIRED by the trader in Round 4 — he superseded his own Q43 question in favour of the per-stock POINTS view (size-independent, post-hoc from the ledger); the flag machinery remains built and switched off, config keys null, labelled 'retired by trader, Round 4'.** OPEN-6 and OPEN-7 resolved by this answer.

---

## 4. DATA SPECIFICATION (all facts verified against original sources, Jul-2026)

### 4.1 Daily layer — official NSE files (free, no broker dependency)

| Item | Source | Verified |
|---|---|---|
| F&O universe (~210 stocks) | `https://www.nseindia.com/api/underlying-information` (JSON: IndexList + UnderlyingList) | fetched live 21-Jul-2026, 210 stocks |
| Holiday calendar | `https://www.nseindia.com/api/holiday-master?type=trading` (per-segment JSON; use CM) | fetched live, 2026 = 20 holidays |
| Daily OHLCV | NSE bhavcopy. Current UDiFF (since Jul-2024): `nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip` (cols TckrSymb, OpnPric, HghPric, LwPric, ClsPric, TtlTradgVol). Old format (archive, ≥2000 verified): `nsearchives.nseindia.com/content/historical/EQUITIES/YYYY/MMM/cmDDMMMYYYYbhav.csv.zip` | zips downloaded for 2000/2018/2026 |
| Bhavcopy prices are UNADJUSTED | — | hence §4.2 |
| F&O membership history (survivorship) | Wayback snapshot of `fo_mktlots.csv` (verified capture 09-Sep-2021) + NSE FAOP/CML circular PDFs (dated inclusion/exclusion lists; `nsearchives.nseindia.com/content/circulars/FAOP{n}.pdf`). File discontinued Jan-2024 → circulars after | capture + sample circular fetched |

NSE ToU: bhavcopy FILES are published for download (sanctioned); the JSON endpoints are pulled gently (once/day max) — never bulk-scraped; nothing is ever redistributed.

### 4.2 Corporate-action engine (we build it; no living open-source library does this)

Events: NSE `corporates-corporateActions` JSON API — **verified returning data back to 2005** (year-per-request, ~2k rows/yr, subjects like " Bonus 1:2", " Face Value Split ... Rs 5 To Re 1", " Rights 2:7" — free-text, regex-parsed). Second source: BSE `CorpactCSVDownload` CSV (sanctioned download, ≥2010 verified, no ISIN → needs scrip-master join). Tiebreak: Yahoo per-ticker `splits` events (verified exact on 3/3 test events incl. 2016 microcaps; bonuses appear as combined split ratios; rights invisible there).

Adjustment = multiply all OHLC strictly BEFORE the ex-date by k (chain multiple events):

| Event | k (multiplier for pre-ex prices) | Note |
|---|---|---|
| Bonus A:B (A new per B held — INDIAN convention) | `B/(A+B)` | bonus 1:2 → k=2/3. US-convention libraries corrupt this — never reuse them |
| Split, face value A→B | `B/A` | FV 10→2: k=0.2 |
| Rights A:B at price S, cum-close P | `(P−E)/P` where `C=(P−S)·A`, `E=C/(A+B)` (≡ TERP/P) | NSE's own F&O formula |
| Ordinary cash dividend (<2% of pre-announcement close) | 1 (no adjustment) | NSE, Zerodha, TV-default all agree |
| Special dividend (≥2%) | `1 − D/P_cum` | NOTE: the 2% threshold is tested against the PRE-ANNOUNCEMENT close, but the factor k uses the CUM-date close — two different reference prices, intentionally, per NSE's own rule |
| Buyback | 1 (no adjustment) | |
| Demerger/spin-off | NO factor exists | suppress bias + trading across ex-date (§3.2); NSE itself terminated RIL F&O contracts rather than adjust (Jul-2023) |

Test oracle: NSE's official "Adjustment of F&O contracts Calculator" XLSX (`nsearchives.nseindia.com/.../Adjustment of Futures and Options contracts Calculator.xlsx`) — our factors must reproduce it.

### 4.3 Intraday layer — Angel One SmartAPI (Paul's own key; ₹0; confirmed by live PoC 21-Jul-2026)

- Auth: daily session (dies at midnight); login = client code + PIN + TOTP (pyotp on the TOTP text-secret). Credentials in `.env`, never printed/committed. Read-only endpoints only (R4 §1).
- Historical: POST `getCandleData` (exchange NSE, symboltoken, interval, fromdate/todate "YYYY-MM-DD HH:MM").
  - ONE_MINUTE: max 30 days/request. ONE_DAY: max 2000 days/request. FIFTEEN_MINUTE exists but we build 15-min bars from 1-min for consistency (§7).
  - **ONE_DAY candles are stamped 00:00 — daily requests MUST start at 00:00 or they return empty** (PoC-discovered bug class).
  - Rate limits: 3/s · 180/min · 5000/hr. Our client throttles to ~2/s with exponential backoff; transient false "access denied" bursts are NORMAL (esp. live hours) — retry, never treat first failure as empty.
  - **Real 1-min depth (PoC-measured): from 2016-10 for established stocks; later listings start at their listing (DIXON: 2017-10). Per-symbol backtest start = max(2016-10, first data). Jan–Sep 2016 is EMPTY — do not trust the "2016" docs claim.** Daily depth: ≥1996.
  - Data quality (PoC, 25 symbol-days): 375/375 candles per day, zero gaps/dupes/zero-vol/impossible-OHLC. Old years (2016–18) get the §4.5 gate during backfill.
- Instrument master: `https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json` (daily dump). Symbol format `RELIANCE-EQ`, exch_seg `NSE`; **tick_size is in paise → divide by 100**.
- Websocket exists (1000 tokens × 3 connections) but is NOT used in v1 — snapshot feed proven unreliable for candle-building at ~200 tokens (user evidence at 198 tokens). REST is the design (§4.4).
- Fallback source if SmartAPI ever degrades: Zerodha Kite Connect ₹500/mo (1-min from ~2015, practitioner-trusted). Dhan/Fyers rejected: fresh 2026 equity volume-integrity bugs.

### 4.4 Live polling layer (screener runtime)

- Source of truth for live bars = the SAME `getCandleData` endpoint the backtest data came from → live bars ≡ backtest bars by construction; no tick-built candles, no drift.
- Measured availability (PoC4, live market hours): just-closed 15-min candle appears **~0.2s after the boundary** when the API responds normally; 30s+ outliers were purely client backoff during transient-403 bursts; candle always present on the next poll.
- Sweep design: at each 15-min boundary (11:15…15:00) sweep all ~210 symbols at ≤3/s (~75–105s), evaluate §3.4, alert. Retry policy tuned for live: short retries (0.5s/1s), on failure SKIP the symbol and re-poll at sweep end (never block the queue 31s), hard sweep deadline before the next boundary.
- 11:15 special sweep: pull 1-min 09:15–11:14 per symbol → §3.3 POC table for the day (~75–105s; first trigger evaluation is the 11:30 close — comfortable).
- Budget check: ~16 sweeps × 210 ≈ 3.4k requests/day ≪ 5000/hr cap. Latency worst case ~34s ≈ 3.8% of a 15-min bar — acceptable.
- Alerts: dashboard + Telegram bot (both — R2-Q37b). Alert payload: symbol, side, entry, SL, TP, POC, bias, timestamp.

### 4.5 Quality gates (automated, every ingestion day)

1. **Volume reconciliation** per symbol-day: `gap% = (bhavcopy_daily_vol − Σ 1-min vol) / bhavcopy_daily_vol`. **Acceptance band: −0.1% ≤ gap ≤ +5.0%** (observed reality in the PoC: +0.02%…+3.6%, median ~0.8% = pre-open auction — the band adds margin around it). Outside the band → flag day, exclude from backtest, log.
2. **Candle integrity**: expected 375 minutes 09:15–15:29. **Missing > 15 minutes in the full day** → exclude the day (flag). Any duplicates, high<low, close outside [low,high] → exclude (flag). impossible OHLC includes an OPEN or CLOSE outside [low, high] (Q-21(a), v1.6 — the open test completed the enumeration after 47 vendor-corrupt bars passed the close-only list). (Milder window-level damage is handled by E4, which can fire on days this gate passes.)
3. **Adjustment sanity**: on every split/bonus ex-date in history, adjusted series must show |day-over-day gap| < 20% (unadjusted 1:10 split = −90% fake gap must disappear); validated against §4.2 oracle. **Also settles OPEN: SmartAPI 1-min adjustment status is UNVERIFIED — treated as RAW; this gate checks known split dates during backfill; if candles turn out pre-adjusted, architect updates §7-E11 before chunk 5 completes.**
4. Old-history spot-check rides along with the full backfill (first run over 2016–2018) — same gates.

## 4.6 MINUTE-LAKE FINAL STATE (v1.5 — the data era, RE-SEALED after Q-18)
The original era (sealed at chunk5B-pass: 434,769 stored / 411,690 passing =
94.6917%, 204 settled / 6 quarantined) was destroyed by the Q-18 incident and
rebuilt through the same reviewed pipeline, then reconciled divergence by
divergence against the sealed numbers. docs/recovery/q18_reconciliation.md is
the authoritative delta record: 422 divergences, ZERO unexplained.
- RE-SEALED NUMBERS **(SUPERSEDED for the passing/coverage pair — see the
  Q-21(a) COMPLETION paragraph below, which is the current reading)**: 435,641
  stored symbol-days; 409,252 pass all three gates = 93.9425%; 204 settled; 6
  quarantined (APLAPOLLO, ASTRAL, IEX, NTPC, UPL, VBL). Minute era 2016-10-03 →
  2026-07-31; daily store 2000-01-01 → 2026-07-30 (6,610 file-present, error 0,
  never-attempted 0 — the v1.3 178-day store lag is CLEARED).
- DIVERGENCE CLASSES vs the original seal, all explained: sealed-fetch-horizon
  414 (the original backfill's per-symbol fetch horizon ended 2026-07-24..28,
  earlier than its report label — an artifact, not drift); vendor-snapshot-
  drift 5 (the vendor's minute feed is a TODAY-snapshot of its own back-
  adjustment; contiguous era-keyed blocks with exact CA-factor price ratios
  and reciprocal volume: APLAPOLLO −467 gate-1 days → QUARANTINED at 77.9%,
  GAIL −60 incl. a per-side floor no longer earned, POWERGRID −23, LODHA −21;
  days honestly refused by the gates); vendor-repair 3 (NESTLEIND's
  pre-2020-10-29 era repaired → SETTLED, 998 days recovered, hand-verified;
  BSE VOLUME-ONLY: gate-1 +80 but prices at exactly 3.0× the exchange →
  usable +2, NOT +84 — reading BSE's gate-1 improvement as coverage is WRONG).
- GATE BATTERY unchanged (gate 1 volume band + evidence-gated auction relief;
  gate 2 integrity; gate 1P price containment, max(2 paise, 0.1%)/side; no
  raw daily row → gate-1P fail). The gates were re-run, never edited.
- Q-17 IS LAW: a stored 1-minute bar stamped outside 09:15..15:29 is dropped
  at the CANDLE level, flagged and counted, never silently — uniform for
  pre-open and post-close strays; gates still see the whole stored day for
  volume (NSE daily volume includes auctions). This binds EVERY consumer of
  stored minute bars, including the Rule-3 first-break scan (Q-22; a day whose
  only break lies in stray bars is a no-break carry).
- Q-19 IS LAW: a confirmed-404 bhavcopy may be SEALED as a non-trading day
  only when the date is more than 7 calendar days in the past; younger 404s
  record as PENDING and are retried. Measured residue at re-seal: 208 gate-1P
  no-oracle days, all 2026-07-31 (minute store one day ahead of the daily
  store), 0.048 pp — cleared by the next bhavcopy top-up.
- E5 CLARIFICATION: a REBUILD uses the sealed universe list (frozen snapshot
  docs/recovery/sealed_universe_210.json); today's F&O list applies only to a
  deliberate, architect-signed universe refresh.
- The disclosed-residual register is the REBUILT one and governs; settled-but-
  partial symbols (IOC, TATASTEEL — B149) are quoted from the register's own
  current figures, which every manifest carries verbatim. Chunk-9 duties
  (recompute gate 1P per day; read the register before any per-symbol
  statistic) unchanged.

Q-21(a) COMPLETION (v1.6): gate 2 gains the open test. Measured cost: 47
symbol-days flip usable→refused; passing days 409,205 = 93.9317% coverage;
ZERO settled/quarantined flips. The malformed-bar population of the whole lake
is 51 — 48 on the settled 204 (47 on 2023-03-03 09:15 market-wide, 1 JIOFIN
2023-08-21) plus APLAPOLLO ×2 and UPL on the quarantined side, one of which
(APLAPOLLO 2017-10-05 15:28) was already refused under the sealed close-only
enumeration and is therefore invisible to a flip-derived count. The 11
moved-POC days are documented in docs/evidence/chunk9b_q21a_poc_impact.md.
Corrupt days are refused, never repaired.

## 4.7 LIVE-MODE VALIDITY (v2.0 — the Q-28 and Q-29 rulings, 08-Aug-2026)

A live trading day has no bhavcopy oracle until evening. Live sweeps therefore run the ORACLE-FREE battery — gate 2 (with the open test), Q-17 candle-level drops, candle validity — per sweep; gates 1 and 1P are structurally inapplicable to same-day data (they detect rewritten history). Every live alert carries: "live feed, not yet verified against the exchange's end-of-day record". The next pre-open runs the FULL battery on the prior recording against the published bhavcopy and reports both verdicts; a live-alerted day the oracle refuses is named loudly. Section 6 parity is judged on oracle-passing days; a live-alerted day the oracle later refuses is the disclosed, bounded difference (live cannot see tomorrow). Measured residual: 0.5229% of settled symbol-days (2,187/418,275 over the ten-year ledger) failed gate 1 alone — the frequency a live morning accepts and discloses. A live morning uses the DAY'S OWN instrument master, fetched pre-open, named and hashed into the recording; replay consumes the recording's pin (§6 holds per day); the backtest's Q-20 pin governs the historical ledger only. A live morning screens the settled universe (204); the quarantined symbols are excluded and named at startup.

## 5. TradingView replication facts (why our POC = his POC)

- TV is an NSE-authorized realtime data vendor (NSE vendor list PDF) — its NSE volume is licensed exchange feed.
- TV's own documentation (help-center, fetched verbatim 21-Jul-2026): Fixed Range Volume Profile picks the first timeframe in {1,5,15,30,60,240,1D} that keeps the range under 5000 bars. Our window = 120 one-min bars → **TV builds his POC from 1-MINUTE bars on every plan, including his Essential** — the same 1-min data we hold.
- Row math (documented, reproduced in our code, §3.3): ticksPerRow formula + closest-count rounding + remainder rows; verified against TV's own worked example (100 ticks, N=30 → tpr=3 → 33 rows of 3 + 1 remainder row of 1 = 34 rows; N=25 → 25 rows of 4).
- What TV does NOT document — settled empirically: volume spreading = **prorata** (calibrated 5/5 vs trader's readings, residuals ₹0.05–₹3.5 = within one row, feed noise). POC-tie rule undocumented → we use trader's rule (higher row, R1-Q9).
- The trader's 3 chart screenshots (Q32, pending) become permanent regression fixtures when they arrive.

## 6. Architecture & repo

- **One engine, two modes**: `bias`, `poc`, `signals`, `simulate` are pure functions over candles (no I/O); the backtester feeds them stored history, the screener feeds them the live poll — same code path, guaranteed no backtest/live drift.
- Modules (build order = plan.md chunks): universe/calendar → daily store (bhavcopy→Parquet) → CA engine → bias engine → 1-min backfill (Parquet per symbol) → POC engine → signal engine → simulator → backtest runner → report UI → validation pack → live screener → alerts.
- Stack: Python 3.10+, pandas, Parquet flat files. No database, no cloud, runs on Paul's laptop. Frontend: web dashboard; design tokens via `npx getdesign@latest add cohere` → DESIGN.md (UI sessions copy tokens, never invent styling).
- Repo layout: `src/` `tests/` `tests/fixtures/` `data/` (gitignored) `docs/` `docs/reviews/` `personas/` `poc/` (archived PoC scripts) + `CLAUDE.md` `CONTEXT.md` `plan.md` `PROGRESS.md` `QUESTIONS.md` `STATUS.md` (one-line-per-chunk state ledger) `DESIGN.md` (chunk 11+).
- Git: detailed conventional commits (what + why), commit per logical unit, tag per reviewed chunk, `.env`/data never committed, **no AI attribution anywhere in history**.

## 7. Engineering defaults (NOT trader-specified — our disclosed defaults; changing them needs architect sign-off, not trader sign-off)

| # | Default | Rationale |
|---|---|---|
| E1 | 15-min bars are aggregated from stored 1-min bars (not fetched separately) | one source of truth; matches profile construction |
| E2 | Non-standard sessions (Muhurat, special/shortened sessions) are excluded. Detection: candle data on a date absent from the trading calendar, or outside 09:15–15:30 → excluded | window 09:15–11:15 doesn't exist there |
| E3 | A stock-day with a flagged quality gate (§4.5) is excluded and counted in the report | never trade on bad data |
| E4 | If the 09:15–11:14 window is missing > 5 of its 120 expected 1-min candles → no POC → no trading that stock-day (fires on days §4.5-gate-2 passes) | profile would be fake |
| E5 | Survivorship: v1 backtests today's 210-stock list and prints an explicit survivorship disclosure on the report; point-in-time membership (4.1 method) is a planned upgrade | honest, cheap; upgrade path documented (OPEN-5) |
| E6 | No notional/leverage cap in v1; report discloses max notional vs ₹1L capital | trader never specified; hiding it would be fantasy-adjacent (OPEN-6 to confirm with trader) |
| E7 | Entry candle itself cannot trigger SL/TP (position starts at its close); monitoring starts next candle | entry price IS the close |
| E8 | Timezone: everything IST (exchange time); timestamps stored naive-IST | single-market tool |
| E9 | Backtest fills are idealized (entry/exit exactly at computed prices; no slippage beyond the ₹100/trade cost) — disclosed on report | trader accepted candle-close entries (R1-Q14); slippage modeling is a possible v2 refinement |
| E10 | Missing 11:00–11:15 reference candle on an otherwise valid day → reference = last available 1-min close ≤ 11:14; none → no trade | deterministic fallback |
| E11 | **Price domains**: intraday engines (POC, signals, simulator) run on RAW same-day 1-min prices (tick grid preserved; PnL in that day's real rupees). The bias engine runs on pairwise-adjusted daily prices (§3.2). Rule-3's 1-min scan compares day-C's raw minutes against P's levels brought into C's scale (P × pending factors). Prices are handled as integer paise internally; POC (row midpoint) may be half-paise; NO float equality comparisons anywhere | scale-correct + deterministic |
| E12 | Bar stamping: 1-min bars are open-stamped (09:15 bar covers 09:15:00–09:15:59). A "15-min candle closing at HH:MM" aggregates the 15 open-stamps in [HH:MM−15, HH:MM). Example: the 15:00-close candle = stamps 14:45–14:59 | kills off-by-one-bucket bugs |
| E13 | **Report metrics — authoritative list & conventions** (mirrors the trader's PDF pp. 7–14 wishes): net PnL, gross profit, gross loss, profit factor, commission paid, expected payoff; total/open trades, winners, losers, % profitable, avg PnL, avg profit, avg loss, avg profit/avg loss, largest win/loss (₹ and % and as % of gross), outliers; max drawdown (equity close-to-close AND intra-trade/intrabar) with durations; run-ups (same forms); CAGR, return on initial capital; Sharpe & Sortino on the DAILY equity series, risk-free rate 0, annualized ×√252; MFE/MAE per trade; buy&hold benchmark = equal-weight portfolio of the traded universe, bought at first trade date's close, held to period end (engineering default, disclosed on report); per-symbol breakdown table; All/Long/Short column split | one authoritative list so the metrics chunk needs no external PDF |

---

## 8. Golden fixtures (tests that define "correct" — committed as small CSVs + expected values)

| Fixture | Source | Asserts |
|---|---|---|
| F1 TCS bullish Entry-1 | trader's PDF worked example, POC per his Round-4 Q44 diagram-answer | **POC 2030** — the PDF's own illustrative POC, restored: his Round-4 answer says the example day is a GAP day, so §3.4's gap branch is the branch it teaches. Entry 2037; **SL = the previous 15-min candle's close** (the F4 "prior close 2028" shape) **= 2025, risk 12**; TP 2073. Q-15's POC-2032 reading is OVERTURNED by the trader's own word (QUESTIONS.md ROUND-4 RECEIPTS, 06-Aug-2026; §10 precedence: later answers correct earlier text) |
| F2 TCS bullish Entry-2 | PDF example, POC per his Round-4 Q44 diagram-answer | initial state WAIT-BELOW (reference above POC 2030) → close below at 2027 arms → re-cross close 2037 → entry 2037; the gap branch again, so **SL = the previous 15-min candle's close = 2027, risk 10**, TP 2067 |
| F1/F2 at POC 2032 — the low == POC boundary (**ILLUSTRATION, not a golden**) | the same F1 and F2 candles, evaluated at POC 2032 | kept and labelled as an illustration: with POC 2032 the entry candle's low TOUCHES the POC, `low > POC` is FALSE, so the NORMAL branch gives SL = the entry candle's low = 2032 (risk 5) and TP 2052. It teaches the boundary the Q-15 ruling identified and it is no longer CONTEXT §8's F1/F2 |
| F3 TCS bearish Entry-1 | PDF example + R1-Q1/Q2 corrections | entry 1980, SL 1988 (candle HIGH, risk 8), **TP 1956** (not 2004) |
| F4 Gap entry SL | R2-Q33 worked numbers | prior close 2028 → gap candle low 2034, close 2042 → entry 2042, SL **2028**, TP 2084 |
| F5 Rule-3 tie day | R2-Q31 + Round-3 Q38/Q39 | P: O2010 H2050 L2000 C2040; same-minute double break; C.close 2020 → BULLISH — for RED, GREEN and DOJI decisive candles alike (color irrelevant; three sub-fixtures) |
| F6 Row engine vs TV docs | TV's documented example | 100 ticks, N=30 → tpr=3 → **34 rows: 33 of 3 ticks + 1 remainder row of 1 tick**; N=25 → tpr=4 → 25 rows of 4 |
| F7 POC calibration days | trader's TV readings 22-Jul-2026 + frozen 1-min CSVs in `poc/data/` (the CSVs are the authoritative input) | two assertions: (a) recomputed prorata POC from the CSVs matches the poc-run printout to ±0.01 (printed 2dp values: TCS 07-14→2205.25 · RELIANCE 07-16→1303.60 · HDFCBANK 07-14→815.27 · DIXON 07-16→14263.50 · MANAPPURAM 07-15→329.75; midpoints may be off-grid — §3.3); (b) on each day, prorata is the candidate nearest the trader's TV reading (2205.3 / 1303.7 / 815.3 / 14267 / 329.75) |
| F8 CA factors | NSE calculator XLSX cases | bonus 1:2 k=2/3; split FV10→2 k=0.2; rights per TERP formula |
| F9 Bias sequence | 15 hand-computed TCS days (built in chunk 4, trader-checkable) | inside-bar carry, R1/R2 flips, seeding |
| F10 Volume gate | PoC `volume_poc_summary.csv` (25 days) | all 25 observed gap% values lie in [+0.02%, +3.6%] and ALL pass the §4.5 acceptance band [−0.1%, +5.0%] |

Rules: fixtures are frozen inputs (CSV) + expected outputs; reviewers rerun them; a change to any expected value requires an architect-signed spec change in §10.

## 9. OPEN ITEMS REGISTRY — the only permitted unknowns (everything else is decided)

| ID | What | Resolution |
|---|---|---|
| OPEN-1 | ₹ risk per trade | **RESOLVED** — ₹1,000 (Round-3 Q29); in config |
| OPEN-2 | Q32 screenshots | **RESOLVED** — received; Row Size 24 confirmed; window question they raised answered by Q42 |
| OPEN-3 | reference == POC | **RESOLVED** — wait rule + side-only first distinct close (Q34b + Q41-A); §3.4 |
| OPEN-4 | Rule-3 tie green/doji | **RESOLVED** — color irrelevant; daily close vs body with bullish precedence (Q38/Q39); §3.2. Code change executed chunk-7 prep |
| OPEN-5 | Survivorship point-in-time upgrade | **OPEN (v2)** — E5 default stands: current list + disclosure |
| OPEN-6 | Notional/leverage cap | **RESOLVED** — none; take-all (Q40-d), with max notional vs capital disclosed per §3.5. The capital-infeasibility flags Q40-d also asked for were RETIRED by the trader in Round 4 (§3.5) and are no part of this resolution |
| OPEN-7 | Concurrency cap | **RESOLVED** — none (Q40-d); disclosures per §3.5 |
| OPEN-8 | SmartAPI adjustment status | **RESOLVED** — back-adjusted, era-inconsistent, per-side; fully remedied by the Q-10…Q-14 machinery (§4.6) |
| Q-13 | tpr rounding tie | **RESOLVED** — finer profile (§3.3); rounding MODE half-even = pinned interim, chunk-12 verification |

Trader gates: **chunk-4 gate CLOSED** (bias table CONFIRMED, Round 3) · **chunk-6 gate CLOSED** (Q42 + row-count oracle). The trader owes nothing further until the chunk-12 validation pack. v2 backlog: OPEN-5, probe-tolerance shape, §4.6 next-data-work list.

When anything here changes: architect updates this file (version bump §10), the affected config/test changes in the same commit.

## 10. Source documents & version log

Source documents (held by Paul, summarized faithfully here): trader's strategy PDF ("acumen trade idea", 14 pp — strategy + report-style wishes) · ACUMEN 1.0 questionnaire with trader's answers (Q1–Q27) · Round-2 questionnaire with answers (Q28–Q37, 22-Jul-2026) · TV calibration reply (5 POC readings, 22-Jul-2026) · `ACUMEN_DATA_RESEARCH.md` (2 research rounds + verifications) · `RESULTS.md` (PoC audit, 21/22-Jul-2026) · PoC raw data (`poc/data/*.csv`).

Precedence if conflict is ever found: trader's R2 answers > R1 answers > PDF text (later corrects earlier); any conflict → QUESTIONS.md, architect resolves with trader.

| Version | Date | Change |
|---|---|---|
| 2.1 | 08-Aug-2026 | §4.7 gains the section-6 parity clause (Q-31), the settled-universe rule (Q-30), the disclosed-line byte fix; POC-immutability restated (B3) |
| 2.0e | 08-Aug-2026 | table of contents gains 4.6 and 4.7 (omitted since v1.3) |
| 2.0 | 08-Aug-2026 | The live era: §4.7 live-mode validity (Q-28 oracle-free battery + next-morning verification + measured residual; Q-29 day's-own master per recording); live mode unblocked |
| 1.9e | 07-Aug-2026 | §9 OPEN-6 aligned with the Round-4 flags retirement |
| 1.9 | 07-Aug-2026 | §3.5 aligned with Round 4: capital flags retired (Q43 superseded by the trader), points view adopted; the trader's Round-4 texts recorded verbatim in QUESTIONS.md |
| 1.8 | 06-Aug-2026 | Round 4: Q44 confirms the gap rule as implemented and corrects the PDF example's parametrization (no engine change, no re-run); Q43 superseded — capital flags retired, per-stock points view adopted |
| 1.7 | 03-Aug-2026 | Q-22: Q-17 made universal (Rule-3 scan + trade_evidence bound); population corrected to 51; v1.5→v1.6 supersedes marker; 21 Rule-3 days re-answered, 0 biases changed (measured) |
| 1.6 | 03-Aug-2026 | Q-21(a): gate 2 enumeration completed with the open test; measured cost 47 days / coverage 93.9317%; Q-21(b) bias-evidence gating and Q-21 malformed-bar refusal recorded as law |
| 1.5 | 02-Aug-2026 | Q-18 re-seal: era rebuilt and reconciled to ZERO unexplained (docs/recovery/q18_reconciliation.md is the delta record); §4.6 rewritten with the re-sealed numbers (435,641 / 409,252 = 93.9425%; APLAPOLLO in, NESTLEIND out of quarantine; BSE volume-only caveat); Q-17 candle-level drop and Q-19 7-day 404-sealing guard made law; E5 rebuild-universe clarification; daily store extended to 2026-07-30 |
| 1.4 | 29-Jul-2026 | Q-15 ruling (option a): F1/F2's illustrative POC → 2032 (PDF's 2030 provably inconsistent with the trader's own gap rule — while ARMED no prior close exceeds the POC, so a gap-branch stop can never be 2032; precedence §10: later answers correct earlier text). §3.4 untouched; F4 remains the gap witness; low == POC → NORMAL branch is the taught boundary |
| 1.3 | 29-Jul-2026 | Round-3 answers + data-era close, batched: §3.2 tie rule rewritten (color irrelevant — trader overturned green-mirror + doji-carry; bullish-precedence close-vs-body rule); §3.3 window confirmed 8-candle, tpr-tie → finer (Q-13 ruled), rounding half-even pinned, N=24 confirmed; §3.4 ==POC wait rule + side-only first distinct close (Q34b/Q41-A); §3.5 risk ₹1,000 + take-all confirmed (Q40-d) with capital-infeasibility flags; NEW §4.6 minute-lake final state (measured adjustment maps, floors per event per side, 3-gate battery incl. gate 1P, coverage 94.69% architect-accepted, residual register, chunk-9 duties, next-data-work list); §8 F5 extended to 3 sub-fixtures; §9 registry: everything resolved except OPEN-5 (v2); both trader gates recorded CLOSED |
| 1.2 | 23-Jul-2026 | Added E13 (authoritative report-metric list & conventions incl. buy&hold benchmark definition — plan.md chunk 10 depends on it); repo layout gains STATUS.md ledger + docs/reviews/; DESIGN.md corrected to chunk 11 |
| 1.1 | 23-Jul-2026 | Post-adversarial-review fixes: outside-bar precedence note; exact tie-case operators (+doji→OPEN-4); demerger day-blocking + resume; row remainder/containment/top-inclusive/point-bar rules; POC off-grid note; ARMED/==POC/consumption semantics; WAIT-BELOW strictness; reference fallback (E10); explicit bearish mirror; portfolio default + OPEN-7; SmartAPI adjustment status OPEN-8 + gate-3 check; gate bands fixed (F10/§4.5); gate-2 vs E4 thresholds separated; F2 initial state; F6 corrected (33×3+1×1); F7 semantics precise; price domains E11; bar stamping E12; dividend dual-reference note |
| 1.0 | 23-Jul-2026 | Initial master spec. Open: OPEN-1…6 |