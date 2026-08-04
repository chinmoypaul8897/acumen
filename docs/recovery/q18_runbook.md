# Q-18 REBUILD RUNBOOK -- the operator's terminal, five ordered steps (+ the run)

**Status: steps 1-5 COMPLETE (operator, 31-Jul/01-Aug-2026); CONTEXT 4.6 v1.5 written and
committed (architect, 02-Aug-2026); step 6, THE RUN, is STAGED but NOT handed over** -- the
chunk-9B re-seal review gates it. This executes the architect's Q-18 ruling (QUESTIONS.md,
recorded verbatim): *"option (c) -- rebuild through the existing reviewed pipeline; the rebuilt
era MUST be reconciled against CONTEXT 4.6's sealed numbers"*.

Everything below runs the **existing, reviewed entry points**. No ingestion logic was written
for this rebuild, and nothing in `src/acumen` that ingests, gates or un-adjusts a candle was
touched. What was added is a launcher for step 3 (so the instrument-master filename is decided
before the long run rather than after it) and the step-5 reconciliation the ruling requires.

Run the steps **in order**. Each one is safe to Ctrl-C and re-run.

---

## Before you start

**Credentials.** Only **step 4** uses `.env`. Verified on 31-Jul-2026, without reading or
printing any value: `.env` is present (120 bytes) and all four names the SmartAPI client
requires -- `SMARTAPI_KEY`, `SMARTAPI_CLIENT_CODE`, `SMARTAPI_PIN`, `SMARTAPI_TOTP_SECRET`
(the constants in `src/acumen/smartapi_client.py`) -- are declared with non-empty values.
Steps 1, 2, 3 and 5 need no credentials at all: steps 1-3 are public downloads and step 5 is
offline. Never print, log or commit the file (CLAUDE.md rule 4).

**WHERE THE STORES ARE, as of 02-Aug-2026.** They are no longer under this repository. They
live at `paths.data_root` and `paths.cache_root` in `config.yaml` -- CLAUDE.md, "Data-store
safety", Q-18 layer 1: no git command can reach them. Every `data/...` and `cache/...` path
below is therefore relative to those roots, not to the repo. The loader refuses a store root
that is relative or inside the repository tree, so this cannot quietly revert.

**Standing orders** (CLAUDE.md, "Data-store safety"):

1. Never junction or symlink a store into a worktree or temp tree. That is how this era was
   destroyed. Verification needs a COPY, or must run in place.
2. **After each step below completes, snapshot both roots to an offline location before
   starting the next one.** Steps 2, 3 and 4 are hours of work each; a snapshot after step 4
   in particular is the difference between an incident and a re-copy.
3. Keep **TWO snapshot generations**; never overwrite the previous one until the new one is
   verified. `python scripts/run_backtest.py --preflight-only` prints each root's
   last-changed timestamp under STORE FRESHNESS, which is how you check that a snapshot is
   actually newer than the store it claims to cover.
4. Sessions treat the stores as READ-ONLY unless the architect's prompt sanctions a named
   write. **Deletions are operator-only**, snapshot verified first.

**Do not commit or check out anything while step 4 or the later chunk-9B run is going.** The
run spec's digest covers the code SHA, so a moved HEAD makes a resume refuse rather than mix
two code states into one ledger.

**On durations.** Where a figure is MEASURED it says so. Where it is extrapolated from a
measured rate it says that, with the rate. Where nothing has been measured it says
**UNKNOWN** -- no step in this runbook carries a guessed duration.

---

## Step 1 -- bhavcopy re-ingest, 2000 -> the last completed trading day

```
python scripts/backfill_daily.py --from 2000-01-01 --to <LAST_COMPLETED_TRADING_DAY> --allow-network
```

**What it fetches/builds.** The daily store: ~25 years of NSE bhavcopy into monthly Parquet
files, plus the per-date **coverage ledger** the trading calendar is DERIVED from (Q-3). This
is the gate-1 and gate-1P raw price/volume oracle everything downstream is judged against, and
it is the only step that can extend the walkable span: it clears CONTEXT 4.6's disclosed
**178-day store-lag** (the "no raw daily row" gate-1P failures, next-data-work item C2) and
moves the backtest's end date past **2026-07-24**, where the chunk-9B preflight last clamped it.

**Data source.** NSE's published bhavcopy files (CONTEXT 4.1): UDiFF
(`nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_...zip`) for dates from Jul-2024, the
archive format (`.../content/historical/EQUITIES/YYYY/MMM/cmDDMMMYYYYbhav.csv.zip`) before it.
The era's format is tried first and the other only on a 404, so a `confirmed-404` means no file
exists in **either** format. Public files, no credentials.

**`--to` IS NOT "today" -- belt AND braces now.** The architect's card says "2000->today".
Keep using the last **completed** trading day. The smoke measured why: run at 10:21 IST on
Friday 2026-07-31 with the market open, the fetch recorded **2026-07-31 as `confirmed-404`** --
and under the Q-3 ruling a confirmed-404 IS a non-trading day, so today would be sealed into
the ledger as a phantom holiday and CONTEXT 3.2's bias pair for the next session would shift
with it.

**As of 02-Aug-2026 that failure is impossible by construction.** Q-19 was ruled and is now
CONTEXT 4.6 (v1.5) law: *"a confirmed-404 bhavcopy may be SEALED as a non-trading day only
when the date is more than 7 calendar days in the past; younger 404s record as PENDING and
are retried."* The downloader enforces it (`acumen.bhavcopy.seals_as_non_trading_day`), the
ledger carries a fourth outcome `pending`, `pending_dates` re-asks it on the next run, and the
trading calendar REFUSES to derive over a pending date rather than treating it as a holiday
(tests: `tests/test_q19_seal_guard.py`, including the 2026-07-31 shape itself). The run
summary prints a `pending (Q-19)` line so the count is never silent.

**The operator rule stays anyway**, because it is free and it keeps the store's two halves in
step: stopping at the last completed trading day is also what stops the minute lake running a
day ahead of the daily oracle, which is what cost the rebuild 208 gate-1P no-oracle days
(0.048 pp, all 2026-07-31 -- the measured addendum in QUESTIONS.md Q-19). The guard removes
the silent corruption; the rule removes the noise.

If a phantom row ever exists from an older run, the fix is unchanged:
`python scripts/backfill_daily.py --rebuild-ledger` -- it rebuilds the ledger from the surviving
monthly Parquets and returns every unrecovered date to *pending*, which this session ran and
verified.

**Resumability.** Fully resumable, at DATE granularity. The ledger records every attempted
date's outcome, and a re-run only attempts what is not settled -- so Ctrl-C and re-run costs
nothing but the date in flight. An `error` is re-attempted by default (`--no-retry-errors`
turns that off); an error is **never** treated as a holiday (Q-3 safeguard 1). Re-running the
whole command after completion is a no-op that just re-prints the summary.

**Duration.** **EXTRAPOLATED, not measured end-to-end.** Measured this session: 31 calendar
dates in **1m18s** at the polite 1-request/2s pacing = **2.52 s/date**, over a date mix (22
present, 9 non-trading) whose weekend share matches the long run's. 2000-01-01 to 2026-07-30 is
~9,700 calendar dates, so **~6.8 hours**. A present date costs one request and a non-trading
date costs two (both formats), which is already inside the measured rate.

**Completion check.**

```
python scripts/backfill_daily.py --from 2000-01-01 --to <LAST_COMPLETED_TRADING_DAY>
```

(no `--allow-network` -- a dry run). It must print `to attempt : 0`. Then confirm the ledger's
own summary shows **`error : 0`** and **`never attempted : 0`** over the range: those two zeros
are what makes the derived calendar legal, because the calendar loader refuses to build at all
if any date in its range is `error` or missing.

**Snapshot `data/` before step 2.**

---

## Step 2 -- corporate-action day-cache re-pull, 2005 -> 2026

One invocation per year, of the existing chunk-3 entry point. PowerShell:

```
foreach ($y in 2005..2026) {
  python scripts/ca_report.py --from "$y-01-01" --to "$y-12-31" --allow-network
}
```

bash:

```
for y in $(seq 2005 2026); do
  python scripts/ca_report.py --from "$y-01-01" --to "$y-12-31" --allow-network
done
```

**What it fetches/builds.** The corporate-action day-cache under `data/nse/ca/`, one file per
year per source. **The year-at-a-time shape is required, not cosmetic**: the pipeline reads the
cache through `fetch_corp_action_history`, which asks for `nse_ca_<YYYY>-01-01_<YYYY>-12-31.json`
one year at a time, so a single 22-year window would write one file nothing downstream looks
for. This cache is what the chunk-4 bias engine's factor table, chunk-5B's un-adjustment maps
and the chunk-9B run all read. The era it replaces held **41,351 rows**.

**Data source.** NSE `corporates-corporateActions` (CONTEXT 4.2, verified back to 2005) plus
the BSE `CorpactCSVDownload` cross-check, both sanctioned and both day-cached. Yahoo is NOT
pulled (it is a tiebreak only; `--yahoo` is empty by default). Public endpoints, no credentials.

**Resumability.** Resumable **within the same calendar day**: online, a cache file written today
is served without a network call, so re-running the loop after a Ctrl-C re-fetches only the
years it had not reached. Across a day boundary the once-a-day rule refetches every year
(~2 minutes of requests -- cheap, and it is the politeness rule CONTEXT 4.1 states). The loop is
also safe to run per-year by hand if one year fails.

**Duration.** **UNKNOWN end-to-end** (never measured on this machine). Basis for an estimate:
22 years x 2 sources = **44 requests** at the >= 2 s/request pacing = **~1.5 minutes of
request time**, plus payload parsing and the per-year report print. Minutes, not hours.

**Completion check.**

```
python -c "import sys; sys.path.insert(0,'src'); from datetime import date; from acumen.minute_backfill import fetch_corp_action_history as f; a=f(date(2005,1,1), date(2026,12,31), allow_network=False); print(len(a), 'rows'); print(min(x.ex_date for x in a), max(x.ex_date for x in a))"
```

It must print a row count **offline** (that is the point: 22 files present, served at any age)
and a span starting in 2005. Compare the count with the era's **41,351**; a materially smaller
number means a year is missing, and the reconciliation in step 5 cannot call anything
`new-CA-explained` without this cache.

Run today, before the rebuild, that check fails with exactly the filename it wants --
`data\nse\ca\nse_ca_2005-01-01_2005-12-31.json` -- which is the per-year name the loop above
produces, and is why the year-at-a-time shape is not a stylistic choice.

**Snapshot `data/` before step 3.**

---

## Step 3 -- instrument master re-fetch

```
python scripts/fetch_instrument_master.py --allow-network
```

**What it fetches/builds.** Today's Angel One instrument master, cached to
`cache/instrument_master/OpenAPIScripMaster_<TODAY>.json`. It carries the `symboltoken` every
`getCandleData` request in step 4 is keyed on, and the **per-symbol `tick_size`** (paise, /100)
that CONTEXT 3.3/4.3 forbid hardcoding -- Q-2 measured that a hardcoded 0.05 mis-prices DIXON's
POC by rupees. The command **prints the filename it wrote**; that name is what every pack citing
a tick size must quote, and the chunk-9B preflight checks for it. The era it replaces used
`OpenAPIScripMaster_2026-07-28.json`; **the new file will carry today's date, and packs
regenerated after this rebuild must cite the new name.**

**Data source.** `margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json` --
a public daily dump, roughly 40 MB. **No credentials**: this endpoint is not the trading API.

**Resumability.** Idempotent and instant to re-run: a dump already fetched today is served from
the date-stamped cache without touching the network (asserted by a test that makes the
downloader raise). Ctrl-C mid-download leaves no cache file, because the file is written only
after the payload has parsed into a usable master -- so a re-run simply fetches again.

**Duration.** **UNKNOWN** -- one ~40 MB download, bandwidth-dependent. Seconds to a few minutes.

**Completion check.** The command exits 0 and prints `MASTER FILE`, the instrument count, and
`cite it as OpenAPIScripMaster_<TODAY>.json`. Re-running it without `--allow-network` must
report the dump as already held.

**Snapshot `cache/` before step 4.**

---

## Step 4 -- minute-lake re-backfill, the full universe

```
python scripts/universe_backfill.py --allow-network --report-path docs/recovery/backfill_minute_report_rebuild.md
```

> ### The one flag you must not omit
>
> `--report-path` defaults to **`docs/backfill_minute_report.md`** -- the COMMITTED sealed
> report. That file is the only surviving description of the era CONTEXT 4.6 sealed, and step 5
> reconciles against it. Running step 4 without `--report-path` **overwrites the baseline with
> the rebuild** and there is nothing left to reconcile against. Pass the flag on every
> invocation, including `--report-only` and `--regate` re-runs. (`git checkout
> docs/backfill_minute_report.md` restores it if it is overwritten -- it is committed, so this
> is recoverable; do not rely on that.)

**What it fetches/builds.** The whole chunk-5B machinery, in its own order, for all 210 F&O
underlyings: fetch 1-minute candles in 30-day windows -> **un-adjust to RAW prices through
freshly MEASURED per-symbol adjustment maps** (the Q-10..Q-14 apparatus: candidates
{ours, measured, absent} per event per side, application floors binary-searched, compound nodes
for same-ex-date events, full probe provenance) -> run CONTEXT 4.5's gate battery (gate 1
volume reconciliation with the auction-relief branch, gate 2 integrity, **gate 1P** per-day
price containment) -> settle or quarantine each symbol -> write the **disclosed-residual
register** at `data/universe_backfill/ledger.json`, which CONTEXT 4.6 makes a chunk-9 duty to
read, and the report.

**Data source.** Angel One SmartAPI `getCandleData` (CONTEXT 4.3), throttled to ~2 req/s with
exponential backoff. The daily store from step 1 is the gate oracle; the CA cache from step 2
feeds the maps; the instrument master from step 3 supplies tokens and ticks. **THIS IS THE ONE
STEP THAT USES `.env`** -- the SmartAPI daily session (client code + PIN + TOTP) is built from
the four variables named above. Read-only endpoints only (CONTEXT 1-R4). Transient "access
denied" bursts are NORMAL; the client retries and never treats a first failure as empty.

**Resumability.** Resumable at **window** granularity -- finer than per-symbol. The per-symbol
ledger records each 30-day window's outcome, so an interrupt costs at most the window in
flight, and the same command picks up where it stopped. The daily-store verification at the
start can be skipped with `--skip-verify` once it has passed. Useful staging flags if you want
to break the run up: `--symbols A,B,C` and `--max-symbols N`. Offline re-runs that touch no
network: `--report-only` (regenerate the report from the ledger and the stores) and `--regate`
(re-run the gates over stored candles). **Both need `--universe-snapshot` and `--report-path`
as well** -- see step 7, which spells the re-gate command out in full and says what the bare
form does.

**Duration.** **UNKNOWN end-to-end -- never measured on this machine, and this session did not
measure it.** The honest basis: the sealed report records **23,138 windows** across the 210
symbols (23,050 present, 88 empty, 0 error). At the client's ~2 requests/second that is
**~3.2 hours of request time alone**, before the un-adjustment map measurement, the gate
battery, the floor probes and the report. Expect materially more than 3.2 hours, plan for it
running overnight, and do not treat any number here as a projection -- **the first completed
run is what measures this.**

**Completion check.** The command exits 0, and then all of:

1. `data/universe_backfill/ledger.json` exists and loads as a register with an entry per symbol;
2. `docs/recovery/backfill_minute_report_rebuild.md` exists **and
   `docs/backfill_minute_report.md` is unchanged** -- verify with `git status --short docs/`,
   which must not list the sealed report;
3. the chunk-9B preflight goes GO:

```
python docs/evidence/chunk9b_preflight.py --out docs/evidence/chunk9b_preflight.md
```

It re-measures the universe from the register and the span from the store's own Parquet files
and refuses to emit the run command if any of its ten checks fails.

**Snapshot `data/` and `cache/` before step 5. This is the snapshot that matters most.**

---

## Step 5 -- the RECONCILIATION (this is what the architect judges)

```
python docs/recovery/q18_reconcile.py --out docs/recovery/q18_reconciliation.md
```

**What it builds.** The report the ruling requires: the rebuilt era against CONTEXT 4.6's
sealed numbers -- stored days, passing days, coverage %, settled/quarantined lists, per-symbol
day counts against the old backfill report, and **every divergence classified**
`{new-CA-explained, vendor-repair-explained, unexplained}` with the evidence for each. It ends
in one of two verdicts, in the ruling's own words: zero unexplained (the deltas are the payload
for a CONTEXT 4.6 **v1.5** amendment, which the **architect** writes -- no session amends
CONTEXT) or N unexplained (**a defect to triage**).

**Data source.** Offline and read-only, on the rebuilt stores: the committed
`docs/backfill_minute_report.md` as the SEALED baseline, step 4's
`docs/recovery/backfill_minute_report_rebuild.md` as the rebuilt side (both through the same
parser, so neither era is measured on its own terms), the minute store's Parquet files as an
INDEPENDENT leg, and step 2's CA day-cache to decide what counts as a new corporate action.
**No credentials, no network.**

**Resumability.** Not applicable in the usual sense -- it writes one file and takes seconds.
Re-run it as often as you like; it changes no store and fetches nothing.

**Duration.** Seconds. Basis: it parses two markdown files and lists Parquet directories.

**Completion check.** Exit code **0** means zero unexplained divergences and no contradiction
between the rebuilt report and the rebuilt store. Exit **1** means the ruling's "defect to
triage" (or a store/report contradiction, which blocks the verdict outright). Exit **2** means
an input is missing -- read the message; it names which step produces it. Either way, send
`docs/recovery/q18_reconciliation.md` to the architect: **the classification rules the report
applied are printed inside it**, so they can be overruled by reading.

---

## What happens after step 5

**Steps 1-5 are DONE.** The operator ran them 31-Jul/01-Aug-2026; the reconciliation reached
**zero unexplained** divergences after the architect's T1-T5 triage rulings; and the architect
wrote **CONTEXT 4.6 v1.5** (committed 02-Aug-2026), which re-seals the era at 435,641 stored
symbol-days / 409,252 passing = 93.9425%, 204 settled / 6 quarantined, and carries Q-17 and
Q-19 into CONTEXT law. Everything below this line is the RUN the rebuild existed to unblock.

---

## Step 6 -- THE CHUNK-9B FULL-HISTORY RUN (staged 02-Aug-2026; AUTHORIZED and started 03-Aug-2026; **RELAUNCH owed**)

> **State, 03-Aug-2026.** The re-seal review PASSED (`docs/reviews/REVIEW_9B_PRESEAL.md`, tag
> `q18-reseal-pass`) and the operator started the run. It stopped at symbol 104 of 204 on a
> vendor-corrupt 1-minute bar -- QUESTIONS.md **Q-21**, ruled and fixed the same day -- so this
> step is live again as a RELAUNCH. Read the next section before the command: one operator
> action is owed first.
>
> *(Original staging note, 02-Aug-2026: this command was written down complete while the
> re-seal review gated it, so that handover would be a decision rather than a scramble.)*

### The command

```
python scripts/run_backtest.py
```

That is the whole thing -- no flags. The label defaults to `chunk9b_full` and the run lands in
`<data_root>/backtests/chunk9b_full/`. It runs the ten-check preflight first and **refuses to
start if any check fails**, so there is no separate "check then run" step to forget.

To see the checks without running:

```
python scripts/run_backtest.py --preflight-only
```

### Before the RELAUNCH of 03-Aug-2026 -- one operator action first

The first attempt died on 2026-08-03 at symbol **104 of 204 (JUBLFOOD)**, on the vendor-corrupt
1-minute bar QUESTIONS.md **Q-21** records. The defect is fixed and the fix is tested, but the
run must start from an empty directory: a resume would refuse anyway (the code SHA moved, and
the spec digest covers it), and its 103 finished shards are worth keeping as a cross-check
against the relaunched run.

**The OPERATOR renames it -- not a session, and it is never deleted** (CLAUDE.md data-store
safety, layer 2: store deletions are operator-only, and sessions treat the stores as read-only):

```
cd <data_root>/backtests
ren chunk9b_full chunk9b_full_crashed_0803
```

Then start the run normally. The relaunch walks the whole universe under ONE code SHA, which is
what the resume law requires; the retained directory is evidence, not an input.

### Pre-run checklist -- all four, in order

1. **Reboot the machine.** Not superstition: this box is memory-starved and the run is hours
   long. See item 2 for what "starved" measures at.
2. **Free memory before starting.** Measured 02-Aug-2026 at 14:12 IST, **eleven minutes after
   a reboot**: 964 MB available of 7.7 GB physical, with **20.1 GB committed against a 27.1 GB
   limit**. The reboot did not clear it. Close the browser, the editor and anything else large;
   the run itself walks ONE symbol at a time and writes that symbol's shard before starting the
   next, so its own footprint is modest -- what hurts is competing for the last gigabyte.
   RESUME-1 measured the cost of not doing this: a 21,000-file read took 25 minutes and one
   verification pass was reaped mid-scan.
3. **Confirm your snapshot is NEWER than both stores.** `--preflight-only` prints each root's
   last-changed time under **STORE FRESHNESS**. Keep TWO generations; never overwrite the
   previous one until the new one is verified (CLAUDE.md Q-18 layer 3). The run WRITES to
   `<data_root>/backtests/`, so a snapshot taken before it covers everything except the run's
   own output -- which is exactly what you want to be able to fall back to.
4. **Do NOT commit, check out, or re-point the tick pin while it runs.** The run spec's digest
   covers the code SHA **and** the pinned instrument master's filename + sha256, so moving
   either turns a free resume into a refusal (`... belongs to a different run`). Finish the run,
   then commit.

### What to expect

| Measure | Value | Basis |
|---|---|---|
| Universe | 204 settled symbols | the disclosed-residual register, read (CONTEXT 4.6) |
| Span | 2016-10-03 -> 2026-07-30, 2,425 trading days | measured from the stores, clamped to the daily oracle |
| Symbol-days | ~495,312 | 204 x 2,428 rows |
| **Projected duration** | **~6h 04m** | MEASURED 25.56 symbol-days/s + two measured wiring terms -- `docs/evidence/chunk9b_throughput.md` has the arithmetic |
| Tick pin | `OpenAPIScripMaster_2026-07-31.json` | `config.yaml`, QUESTIONS.md Q-20 |

Progress is one line per symbol with elapsed / rate / ETA on stdout. **Redirect it to a file**
(`python scripts/run_backtest.py > logs/chunk9b_run.log 2>&1`) -- it is the only record of the
rate, and the throughput evidence is built from exactly such a log.

### Resumability

Ctrl-C at any moment and re-run the **same command**. A symbol's shard is written only when
that symbol is COMPLETE, so an interrupt costs at most the symbol in flight and no row can be
duplicated. The CONTEXT 7-E2 session scan (~39 minutes of the projection) is cached beside the
ledger on the first pass and is free on every resume.

### The two manifest stamps -- what the ledger will and will not claim

Both trader questions are still OPEN, and the run says so on its own manifest rather than in a
note somebody has to remember. This is the architect's GO ruling (31-Jul-2026), conditions (1)
and (2), and it reflects QUESTIONS.md's state as of 02-Aug-2026 -- **neither answer has
arrived**:

* **Q43 -- capital-infeasibility flags PENDING.** `config.yaml`'s `capital_reference` and
  `margin_basis` are both null, the preflight CHECKS that they still are, and every output
  carries *"capital-infeasibility flags NOT computed -- the trader's Q43 answer is pending"*.
  No flag VALUE is computed anywhere; when the answer arrives the flags compute POST-HOC from
  the ledger, with no re-run.
* **Q44 -- the gap-rule example UNCONFIRMED.** The manifest carries *"PENDING TRADER
  CONFIRMATION OF Q44 (gap-rule example, POC 2032)"* and, beside it, the escalation: if his
  answer surprises, that is a CONTEXT 3.4 change -> spec version bump -> **full re-run**, and
  this ledger is then superseded, retained and labelled, never deleted.

A third disclosure rides with them, measured rather than ruled: the span is clamped to the raw
daily oracle, which as of 02-Aug-2026 costs exactly ONE day (2026-07-31, the Q-19 residue --
down from the 178-day store lag the sealed era carried, which step 1 cleared).

### Completion check

The last line reads `RUN COMPLETE:` with the walked / usable / executed counts and the rate,
and both `ledger.jsonl` and `manifest.json` exist under `<data_root>/backtests/chunk9b_full/`.
Then **snapshot both stores again** -- the run's output is not reproducible in six hours if it
is lost -- and the chunk-9B REPORT session takes it from there.

---

## Step 7 -- the OWED offline re-gate (a data session; safe either side of step 6)

The architect's Q-21(a) ruling (CONTEXT v1.6) completed gate 2's impossible-OHLC enumeration, so
`GATE_DEFINITION` moved and **all 210 ledger rows are stale by definition**. Clearing that is a
STORE WRITE and therefore operator work, never a session's (CLAUDE.md Q-18 layer 2). It fetches
nothing -- it re-runs the gates over candles already on disk.

**It does NOT block the relaunch, and the relaunch does not block it.** Traced in
`docs/reviews/REVIEW_9B_FIXES.md` (finding R4, check 6): `load_residual_register` is the run's
only reader of that ledger and takes exactly five fields -- `status`, `gate1p_pass`,
`gate1p_total`, `gate1p_no_oracle`, `residual_reason` -- and the completion moves gate 2 alone.
Gate 1P does not move by a day, and `status` keys off the gate-1 effective rate, which does not
move either. Run it in whichever order suits you.

### The command -- both flags are mandatory

```
acumen-universe-backfill --regate \
    --universe-snapshot docs/recovery/sealed_universe_210.json \
    --report-path <a scratch path, NOT the committed report>
```

**Why each flag, measured rather than asserted (REVIEW_9B_FIXES R4):**

* **`--universe-snapshot`** -- without it `run()` resolves the universe from the cached F&O
  endpoint (`<data_root>/nse/underlying_information.json`), which holds **208** symbols. The
  register holds **210** and *is* the sealed universe. The two missing are **EXIDEIND** and
  **NUVAMA** -- exactly the pair the Q-18 T4 pass added -- and they would keep the stale marker
  forever while the regenerated aggregates printed `406,154 / 93.9058%`: neither the pre- nor
  the post-completion truth. CONTEXT 4.6's E5 clarification is explicit that a rebuild uses the
  sealed snapshot.
* **`--report-path`** -- without it the run overwrites `docs/backfill_minute_report.md`, the
  committed sealed baseline. That is the same flag step 4's box calls *"the one flag you must
  not omit ... including `--regate` re-runs"*. Recoverable with `git checkout`, but do not rely
  on that.

### What to expect

The 47 settled symbol-days the completion refuses are all **2023-03-03**, one per symbol across
47 symbols, and they are already measured day by day in
`docs/evidence/chunk9b_q21a_gate2_completion.md`: usable **409,252 -> 409,205**, coverage
**93.9425% -> 93.9317%**, gate 1 and gate 1P unchanged to the day, **zero** settled/quarantined
status flips. If the re-gate prints anything else, STOP and hand the numbers to the architect.

**Snapshot both stores first** (CLAUDE.md Q-18 layer 3: two generations, the new one verified
before the old is replaced) -- this step writes the ledger.
