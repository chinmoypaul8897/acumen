# plan.md — ACUMEN INTELLIGENCE · Build Plan

**Version 1.1 · 23 July 2026.** Owned by the architect. Build sessions never edit this file — chunk movement is recorded in PROGRESS.md only; plan changes (reorder/split/rescope) are architect-only version bumps. Spec questions → CONTEXT.md; behavior rules → CLAUDE.md.

## Table of contents

1. How a session runs (read → build → hand off)
2. The chunk loop (who reviews what)
3. Chunk index (dependencies, gates, blockers)
4. Chunk cards 0–15 (self-contained, one session each)
5. Deviation & tweak protocol (how on-the-go changes are recorded)
6. PROGRESS.md entry template (copy exactly)
7. Fixture → chunk map
8. Milestones & connect-the-dots checkpoints
9. Version log

---

## 1. How a session runs

**Every session starts by reading, in order:** CLAUDE.md (auto-loaded) → its own chunk card below → the CONTEXT.md sections named on that card → **STATUS.md** (the one-line-per-chunk ledger: verify every dependency shows `reviewed-PASS`) → PROGRESS.md entries **for this chunk and its dependencies** (search `chunk <N>`) plus the newest entry overall → open items in QUESTIONS.md. **Fix sessions additionally read `docs/reviews/REVIEW_<N>.md`** — that is where the findings live. Nothing else is assumed known. If the card, spec, and logs disagree → STOP, write to QUESTIONS.md.

**Every session ends by updating STATUS.md** (single line: `chunk <N>: todo | built | reviewed-PASS | gate-closed(evidence path)`). STATUS.md is the only place chunk state lives; plan.md never changes with progress.

**Every BUILD session must produce:** the deliverable files · unit tests incl. the card's golden fixtures · all tests green locally · a PROGRESS.md entry (template §6) · one or more commits (CLAUDE.md git rules) ending with `chunk<N>: <summary> (unreviewed)`.

**Every REVIEW session must produce:** rerun of all tests · adversarial probes beyond the fixtures · `docs/reviews/REVIEW_<N>.md` with PASS/FAIL + findings · a PROGRESS.md entry · on PASS: commit `chunk<N>: reviewed PASS`.

One chunk per session. Finish or hand off cleanly — a half-done chunk is recorded as half-done in PROGRESS.md, never silently continued into new scope.

## 2. The chunk loop

`architect prompt → BUILD session → fresh REVIEW session → (fix session → re-review)* → PASS commit → next chunk`

- The reviewer is ALWAYS a fresh session (zero shared context with the builder). Review is not optional — it is the next scheduled session after every build.
- Review type per card: **QC** = quant_reviewer + code_reviewer personas (finance-logic chunks). **C** = code_reviewer only (plumbing/UI).
- **Trader gates — blocking rule, stated once:** a gate does NOT block the immediately dependent chunk's BUILD (code review-PASS unblocks building). Gates MUST be closed by these deadlines: chunk-4 and chunk-6 gates before the chunk-9 full run starts (M3); chunk-12 gate before chunk 15. Gate outcome is recorded in STATUS.md as `gate-closed` with the evidence-pack path — that entry is how later sessions verify it.
- No chunk starts while its dependency is not `reviewed-PASS` in STATUS.md. FAIL findings go back to a fix session; re-review covers the fixes only.
- **One session runs at a time** (single operator). Parallel tracks mean independent ORDERING freedom across days, never simultaneous sessions — so PROGRESS.md/STATUS.md never conflict.

## 3. Chunk index

| # | Chunk | Depends on | Review | Gate/Blocker |
|---|---|---|---|---|
| 0 | Repo scaffold & config | — | C | — |
| 1 | Universe & calendar | 0 | C | — |
| 2 | Daily store (bhavcopy) | 1 | C | — |
| 3 | Corporate-action engine | 2 | QC | — |
| 4 | Bias engine | 3 | QC | **TRADER GATE (bias spot-check; OPEN-4 shown)** |
| 5A | SmartAPI client & single-symbol backfill + quality gates | 2 | QC | resolves OPEN-8 |
| 5B | Full-universe backfill run | 5A | C | — |
| 6 | POC engine | 5A | QC | **TRADER GATE (Q32 screenshots when available)** |
| 7 | Signal engine | 4, 6 | QC | — |
| 8 | Trade simulator | 7 | QC | **BLOCKED BY OPEN-1 (₹ risk amount)** |
| 9 | Backtest runner & portfolio ledger | 8, 5B | QC | — |
| 10 | Metrics layer | 9 | QC | — |
| 11 | Report UI | 10 | C | — |
| 12 | Validation pack | 9, 11 | QC | **TRADER GATE (sign-off on 20 replayed trades)** |
| 13 | Live screener loop + morning refresh | 7, 5A, 9 | QC | — |
| 14 | Alerts (dashboard + Telegram) | 13 | C | — |
| 15 | Dry-run week | 12, 14 | — | **TRADER GATE (acceptance)** |

Parallelism allowed (ordering freedom, never simultaneous sessions): {3,4} and {5A,5B,6} are independent tracks after 2 — except chunk 4's synthetic R3 fixtures (see card) and chunk 5A's self-contained split-date list keep them decoupled; 13 starts only after 9 (its replay invariant targets the backtester). Everything else is sequential.

## 4. Chunk cards

### Chunk 0 — Repo scaffold & config
**Goal:** turn the PoC folder into the project repo. **Spec:** CONTEXT §6.
**Build:** restructure to `src/acumen/`, `tests/`, `tests/fixtures/`, `docs/reviews/`, `poc/` (move PoC scripts + keep `poc/data/` CSVs — they are fixtures); verify the seed files are present and untouched (`CLAUDE.md`, `CONTEXT.md`, `plan.md`, `personas/quant_reviewer.md`, `personas/code_reviewer.md`); `pyproject.toml` + pinned requirements; pytest wired; config loader (`config.yaml` + `.env`; `risk_per_trade` present but REQUIRED-EMPTY until OPEN-1); `.gitignore` (env, data, caches); git init + genesis commit.
**Done when:** `pytest` runs green on a trivial test; tree matches CONTEXT §6; PROGRESS.md + QUESTIONS.md + STATUS.md exist with headers (STATUS.md lists chunks 0–15 as `todo`).

### Chunk 1 — Universe & calendar
**Goal:** who do we trade and on which days. **Spec:** §3.1, §4.1, §7-E2.
**Build:** `universe.py` (F&O list fetch, cached to file, gentle: max 1 pull/day); `calendar.py` (holiday JSON → trading-day helpers: `is_trading_day`, `prev_trading_day`, `bias_pair(D) → (D−1, D−2)`); E2 exclusion helper.
**Done when:** goldens pass — 2026 CM holiday count = 20; TCS/RELIANCE in universe; `bias_pair` correct across a holiday weekend (hand-computed cases in fixture).

### Chunk 2 — Daily store
**Goal:** 25 years of daily OHLCV, locally, queryable. **Spec:** §4.1.
**Build:** bhavcopy downloader (UDiFF ≥Jul-2024 + old format before; resumable; polite pacing); parquet store keyed symbol×date; filter to universe symbols; store API `daily(symbol, from, to)` returning RAW prices.
**Done when:** three sample dates from each era ingest correctly; the TCS 2026-07-20 row matches the independently verified values from `RESULTS.md` (close 2251.10, volume 2,202,693); cross-source check: bhavcopy daily OHLCV vs SmartAPI ONE_DAY candle agree for 3 recent dates (SmartAPI values already frozen in `poc/data/`); re-run is idempotent (no dupes).

### Chunk 3 — Corporate-action engine
**Goal:** correct pairwise price adjustment. **Spec:** §4.2, §3.2-Inputs, §7-E11.
**Build:** CA fetchers (NSE year-windows, cached; BSE CSV cross-check; join report); Yahoo per-ticker splits stream as third-vote tiebreaker (§4.2); subject-string parser (bonus/split/rights/dividends regex; subjects containing demerger/"scheme of arrangement" keywords → demerger table); factor table builder incl. special-dividend dual-reference rule; `adjust_pair(P_candle, events_between) → P_in_C_scale`; demerger event table (seed: RELIANCE→Jio Financial ex-date 2023-07-20; parser-detected additions → QUESTIONS.md if ambiguous).
**Done when:** **F8** passes (NSE calculator XLSX cases) + one special-dividend case validated against the §4.2 formula; parser handles the verified 2016 samples (KOTHARIPRO "Bonus 1:2", GREENPLY FV split, JMCPROJECT "Rights 2:7"); adjustment-sanity vs daily store across these 3 verified events (<20% residual gap): KOTHARIPRO bonus ex 2016-01-05, GREENPLY FV split ex 2016-01-06, RELIANCE 1:1 bonus ex 2024-10-28.

### Chunk 4 — Bias engine · TRADER GATE
**Goal:** §3.2 as pure functions. **Spec:** §3.2 complete, §7-E11.
**Build:** `bias.py`: inside-bar → R1 → R2 → R3 → carry; outside-bar precedence note implemented as written; R3 takes an injected `minute_loader` (chunk-5A provides the real one; tests use fixture CSVs); tie-case predicate (red/green/doji per spec); seeding; missing-1-min fallback; demerger blocking (day E+1, E+2) + resume (E+3).
**Done when:** **F5** passes; **F9** built and green — split by data reality: REAL TCS dates from the daily store for inside-bar carry, R1 both sides, R2 both sides, seed day (trader-checkable on his chart); the R3 day and tie-day are SYNTHETIC fixtures (clearly labeled — real 1-min data arrives in 5A; real-day R3 verification happens in chunk 12); reviewer's adversarial days pass. **Gate:** evidence pack (real-day F9 table in plain English) → trader confirms via Paul; OPEN-4 mirror explicitly shown to him. Gate deadline per §2: before chunk 9's run.

### Chunk 5A — SmartAPI client & single-symbol backfill
**Goal:** reliable 1-min ingestion with quality gates. **Spec:** §4.3, §4.5, §7-E12.
**Build:** client (TOTP login, 0.5s throttle, backoff, session refresh); **instrument-master loader** (token lookup, `tick_size` paise→/100 — consumed later by chunk 6); resumable downloader (30-day windows, per-symbol clamp = max(2016-10, listing)); minute parquet store; **gates 1–3** (§4.5: volume band vs daily store; integrity; adjustment check → record OPEN-8 verdict in PROGRESS.md using these self-contained events: KOTHARIPRO bonus ex 2016-01-05, GREENPLY split ex 2016-01-06, RELIANCE bonus ex 2024-10-28); 15-min aggregator (E12 stamping).
**Done when:** one symbol (TCS) backfills Oct-2016→today clean; **F10** passes; gate report generated; OPEN-8 answered with evidence.

### Chunk 5B — Full-universe backfill
**Goal:** run 5A for all ~210 symbols. **Spec:** §4.3 budgets.
**Build:** batch runner with progress persistence (safe to interrupt/resume); per-symbol gate summary; exclusions list (flagged symbol-days); backfill report (`docs/backfill_report.md`: depth per symbol, gate stats, old-years spot-check verdict).
**Done when:** ≥95% of symbol-days pass gates; failures categorized; report reviewed. (Pure execution — expect hours of wall-clock, minutes of attention.)

### Chunk 6 — POC engine · TRADER GATE
**Goal:** §3.3 exactly. **Spec:** §3.3, §5, §7-E4.
**Build:** `poc.py`: **E4 window-completeness check first** (missing >5 of 120 → no POC, day marked no-trade), window slice (09:15–11:14 stamps), row builder (tpr≥1, remainder rows, top-inclusive, point bars, top==bottom), prorata spread, POC midpoint + higher-row tie; per-symbol tick via chunk-5A's instrument-master loader.
**Done when:** **F6** and **F7** pass (poc/data CSVs authoritative); E4 fixture (a window with 6 missing minutes → no POC); property test: total spread volume ≡ window volume (±1e-6). **Gate (deadline per §2: before chunk 9's run):** when trader's Q32 screenshots arrive (OPEN-2): settings matched, 3 chart POCs reproduced; if his Row Size ≠ 24 → architect updates CONTEXT and F-fixtures BEFORE the chunk-9 run; if screenshots never arrive → architect records a waiver with the trader, calibration data stands.

### Chunk 7 — Signal engine
**Goal:** §3.4 state machine, both sides. **Spec:** §3.4 complete, §7-E10/E11.
**Build:** `signals.py`: reference resolution (incl. E10 fallback, OPEN-3 logging path); ARMED/WAIT logic with exact strictness; first-cross consumption (incl. unsizable-consumes rule); gap-entry detection + SL source; TP math; last-entry 15:00; bearish mirror from the explicit spec paragraph (no hand-derivation).
**Done when:** **F1, F2, F3, F4** pass at signal level; synthetic edge fixtures: close==POC while ARMED (no trigger, still armed), cross during WAIT-BELOW (not consumed), OPEN-3 day (logged, no trade), gap day, no-cross day.

### Chunk 8 — Trade simulator · BLOCKED BY OPEN-1
**Goal:** signals → trades with money. **Spec:** §3.5, §3.4-5/6.
**Build:** sizing (`floor(risk/(entry−SL))`, zero-qty consume+log); exit walk (SL/TP touch, SL-wins, 15:15 close-out at the 15:00–15:15 candle close); ₹100 cost; per-trade record schema (all prices, times, bias, POC, exit reason).
**Done when:** F1–F4 end-to-end PnL asserts (incl. F4: qty at risk 14, TP 2084); same-candle-both-touch fixture pays SL; square-off fixture; degenerate entry==SL consumed. **Cannot start until OPEN-1's ₹ amount is in config.**

### Chunk 9 — Backtest runner & portfolio ledger
**Goal:** the full machine over all stocks × all history. **Spec:** §2, §3.5-portfolio, §7-E3/E5.
**Build:** orchestrator (per stock-day: bias → POC → signals → simulate; ALL exclusion rules honored and counted: E2 non-standard sessions, E3 gate-flagged days, E4 no-POC days, §3.2 demerger blocks, OPEN-3 logged days); portfolio ledger (take-all, equity curve in trade-close order); disclosures data (max concurrency, max notional, **full distribution of daily concurrent-trade counts** per §3.5, excluded-day counts by reason, survivorship note); outputs `trades.parquet` + `summary.json`.
**Done when:** full run completes without unhandled errors; internal consistency asserts (Σ trade PnL == equity delta; trade count == ledger count); evidence pack: 3 random trades replayed step-by-step with candle values for manual check.

### Chunk 10 — Metrics layer
**Goal:** every number the trader's report shows. **Spec:** §2, §7-E13 (metric conventions — full authoritative list lives THERE, not in a PDF the session cannot read).
**Build:** `metrics.py` implementing the complete E13 list: net/gross PnL, profit factor, win rate, totals/averages/largest win-loss, expectancy, max drawdown (equity close-to-close + intrabar), run-ups, drawdown/run-up durations, Sharpe/Sortino per E13 conventions, buy&hold benchmark per E13 definition, per-symbol table, MFE/MAE per trade, commission totals.
**Done when:** goldens on a 6-trade synthetic set pass every metric AND **the review session independently recomputes all of them by hand** (the builder's own goldens are not sufficient — self-graded exams don't count); drawdown fixture with known answer.

### Chunk 11 — Report UI
**Goal:** the TradingView-style report he asked for. **Spec:** §2, §6 (getdesign).
**Build:** `npx getdesign@latest add cohere` → DESIGN.md; static web report (served locally): equity curve vs buy&hold, drawdown chart, distribution histogram, winners/losers donut, metrics tables (All/Long/Short), trade list (click → trade detail), disclosures panel (E5/E6/E9 + excluded days). Tokens from DESIGN.md only.
**Done when:** renders the chunk-9 output fully; C-review checks correctness of bindings (right number in right cell) against `summary.json`.

### Chunk 12 — Validation pack · TRADER GATE
**Goal:** the trader verifies the machine is HIS strategy. **Spec:** §8, OPEN-4.
**Build:** plain-English pack: 20 sampled trades (stratified: both sides, gap entries, SL/TP/square-off exits, at least one real R3 bias day now that minute data exists) each with a candle-by-candle replay table; F9 bias table; POC vs his 3 screenshots (OPEN-2; if still missing → calibration-days evidence + recorded waiver); list of OPEN-4 occurrences in history; instructions for him (check on his TV charts).
**Done when:** pack generated; **gate:** trader confirms ≥19/20 trades are "exactly what I'd have done" — any miss → architect triages (spec bug vs data issue) before chunks 13–15 are allowed to close.

### Chunk 13 — Live screener loop + morning refresh
**Goal:** same engine, live — including keeping the data current. **Spec:** §4.4, §4.1, §3.2, §7-E2/E12; PoC latency lessons.
**Build:** **morning refresh job (pre-09:15):** ingest yesterday's bhavcopy into the daily store, incremental CA pull (a split effective TODAY must be known before computing bias), universe + holiday refresh (gentle, cached), compute & persist today's bias for every symbol; **live loop:** scheduler (boundary ticks 11:15→15:00, E2 calendar check), 11:15 POC pass (sweep 1-min, build profiles, E4 respected), per-boundary sweep evaluator calling the SAME `bias/poc/signals` functions; live retry policy (0.5s/1s short retries, skip-symbol + end-of-sweep second pass, hard deadline); state persistence (crash-safe resume intra-day); dry-mode (log-only).
**Done when:** **replay invariant** — the live pipeline in replay mode over 3 recorded historical days produces byte-identical signals to the chunk-9 backtester on those days; morning-refresh test on a recorded day yields the same biases as the backtest path; simulated-disconnect test recovers.

### Chunk 14 — Alerts
**Goal:** the signal reaches him in seconds. **Spec:** §4.4 payload; §2.
**Build:** live dashboard view (today's states per stock, fired signals); Telegram bot (payload: symbol, side, entry, SL, TP, POC, bias, time); alert dedup; end-of-day summary message. **Manual prerequisite (Paul, ~5 min): create the bot via Telegram's @BotFather, put token + chat id in `.env`** — card includes the exact steps.
**Done when:** test-mode alerts delivered to both channels; payload fields complete; no duplicate alerts on re-poll.

### Chunk 15 — Dry-run week · TRADER GATE (acceptance)
**Goal:** five live sessions in parallel with his manual trading. **Spec:** §2.
**Run:** dry-mode live all week; daily 10-min debrief (Paul+trader): tool signals vs what he saw; incident log; latency stats.
**Done when:** zero unhandled errors across 5 sessions; every signal he took manually was also produced by the tool (or divergence explained and triaged); trader accepts. v1 ships.

## 5. Deviation & tweak protocol (record everything, surprise no one)

- **Class A — spec conflict or hole** (CONTEXT.md silent/contradictory): STOP the affected piece → QUESTIONS.md entry → architect resolves (possibly with trader) → CONTEXT version bump. Never coded around.
- **Class B — implementation choice within spec** (data structure, library, algorithm shape): allowed in-session, but MUST be recorded in the session's PROGRESS.md entry under `decisions:` with one-line rationale; reviewer explicitly approves or challenges each one; **architect scans Class-B decisions at EVERY chunk sync (Paul pastes PROGRESS after each reviewed chunk), not only at milestones.**
- **Class C — plan change** (split/reorder/rescope a chunk): architect-only, plan.md version bump; sessions request it via QUESTIONS.md.
- A deviation recorded nowhere = a defect, even if the code is right.

## 6. PROGRESS.md entry template (newest entry on TOP; copy exactly)

```
## [YYYY-MM-DD HH:MM] chunk <N> · <build|review|fix> · <done|blocked|handed-off>
scope: <one line — what this session did>
files: <created/changed paths>
tests: <pass count / fail count; fixtures touched>
decisions: <Class-B items with 1-line rationale; "none">
questions: <QUESTIONS.md items raised; "none">
gate: <n/a | pending | closed — evidence path>
status-ledger: <the STATUS.md line this session set>
state-for-next-session: <exact current situation + the single next action>
```

## 7. Fixture → chunk map

F1–F4 → chunk 7 (signal-level) and chunk 8 (PnL-level) · F5, F9 → chunk 4 · F6, F7 → chunk 6 · F8 → chunk 3 · F10 → chunk 5A · metrics goldens → chunk 10 · replay invariant → chunk 13. `poc/data/*.csv` are frozen inputs — never regenerated, only read.

## 8. Milestones & connect-the-dots checkpoints

- **M1 (after 4):** bias engine trader-confirmed → foundation trusted.
- **M2 (after 5B):** full local data lake + OPEN-8 resolved → no more network dependence for backtests.
- **M3 (after 9):** first full-history backtest exists — architect reviews the disclosures before anyone reads the PnL.
- **M4 (after 12):** trader has signed the validation pack → the numbers may be believed.
- **M5 (after 15):** acceptance → v1 done; v2 backlog opens (OPEN-5 point-in-time universe, slippage model E9, auto-execution discussion).
- At every milestone, Paul pastes PROGRESS.md + latest review into the architect chat for a drift check.

## 9. Version log

| Version | Date | Change |
|---|---|---|
| 1.0 | 23-Jul-2026 | Initial plan: 17 sessions across chunks 0–15 (5 split into 5A/5B), 4 trader gates, deviation protocol, progress template |
| 1.1 | 23-Jul-2026 | Post-adversarial-review fixes: STATUS.md ledger + per-chunk progress lookup + fix-session review-file rule; gate blocking rule stated once (deadlines at M3/15); one-session-at-a-time rule; chunk 13 gains morning-refresh job + dep on 9 (replay invariant target); E4→chunk 6, E2/E4/exclusion-counting→chunk 9; concurrency distribution→chunk 9; Yahoo tiebreak + special-dividend test + concrete event lists→chunks 3/5A; instrument-master loader→5A; F9 real/synthetic split→chunk 4; chunk 10 spec moved to CONTEXT §7-E13 + independent reviewer recompute; Q32-missing fallback; Telegram provisioning step; Class-B scan every sync; template gains gate/status fields |
