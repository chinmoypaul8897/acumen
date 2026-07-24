# REVIEW_2 — chunk 2 · Daily store (bhavcopy)

**Reviewer:** fresh code-review session (`personas/code_reviewer.md`; plan.md chunk 2 is review type **C**).
**Date:** 2026-07-24 · **Span reviewed:** `9257008..52791e0` (5 commits: the architect-directed prep + four chunk-2 commits, everything after tag `chunk1-pass`)
**Builder entry reviewed:** PROGRESS.md `[2026-07-24 21:18] chunk 2 · build · done`

## VERDICT: **PASS**

The whole suite is green from a clean state, every frozen fixture is byte-identical to its
git blob, the card's five goldens survive an independent recomputation that shares no code
with the module it grades, ingestion is byte-idempotent across three passes and both bhavcopy
eras, and the one rule the entire chunk turns on — **a download error is never a holiday** —
holds against every attack I could aim at it. Q-4 and Q-5 were raised instead of decided,
which is the second most important thing this chunk did.

Twelve findings are recorded below: **two MEDIUM, five LOW, five INFO.** None is a FAIL
trigger; none blocks chunk 3's build. Both MEDIUMs live in the shared fetch layer
(`nse_http.py`) and are robustness/politeness defects, not correctness ones — neither can
produce a wrong answer, because both end in the `error` outcome that the calendar refuses to
build over.

**One item the architect should note before chunk 3:** Q-4 (series ambiguity) is real,
measured, and blocking exactly as the builder states — `DailyStore.daily()` cannot read a
full symbol history until it is ruled on. I reproduced it on the 2018 data and it is worse
than the 2026 example suggests: NTPC carries **six** series on 2018-01-01.

---

## 1. Architect's directed checks

| # | Check | Result |
|---|---|---|
| 1 | Prep: Q-3 ruling verbatim in QUESTIONS.md; re-attack the socket guard; crash-test atomic writes | **PASS** — §2 |
| 2 | Goldens independently: TCS row vs docs/RESULTS.md; recompute the 25-day table; judge B34 | **PASS** — §3 |
| 3 | Ledger semantics: both-formats-404, error never becomes 404, resume rules, Sunday golden | **PASS** — §4 |
| 4 | Idempotency: reproduce byte-identical re-ingest | **PASS** — §5 |
| 5 | Price path: Decimal-on-text → integer paise, no float, parquet dtypes | **PASS (B24's example is wrong → Finding 4)** — §6 |
| 6 | Derived calendar: refuses unsettled ranges, derived==published, bias-pair agreement, weekend_sessions | **PASS** — §7 |
| 7 | DERIVED fixtures: PROVENANCE, digests, size, labelling | **PASS** — §8 |
| 8 | Q-4 evidence: reproduce the ambiguity, `daily()` raises naming the series, no `"EQ"` in `src/` | **PASS** — §9 |
| 9 | `backfill_daily.py`: `--dry-run`, pacing ≥2s, resumable, import-safe, never runs under pytest | **PASS except pacing → Finding 1** — §10 |
| 10 | Judge B19–B34 explicitly | **Done** — §11 |
| 11 | 28 + 3 + 3 fixtures match pinned digests; tree clean | **PASS** — §8 |

**Disclosure.** This review issued **no network traffic of any kind.** Where a probe needed
an address it used `192.0.2.1` (RFC 5737 TEST-NET-1, reserved and unroutable) or a closed
loopback port. The chunk-1 review had to send real requests to prove Finding 1 existed;
proving it is *fixed* needs none.

## 2. Tests, and the two REVIEW_1 findings chunk 2 closed

`python -m pytest` from a clean state (`.pytest_cache` and every `__pycache__` deleted first):

> **513 passed / 0 failed** in 6.6s — **462 from the build** (matching the builder's claim
> exactly) and 51 added by this review.

Per file: `test_calendar.py` 96 · `test_daily_goldens.py` 81 · `test_review2_probes.py` 51 (new) ·
`test_fixture_integrity.py` 40 · `test_review1_probes.py` 38 · `test_bhavcopy.py` 35 ·
`test_config.py` 33 · `test_universe.py` 32 · `test_smoke.py` 28 · `test_nse_http.py` 24 ·
`test_daily_store.py` 24 · `test_derived_calendar.py` 16 · `test_atomic_io.py` 8 ·
`test_backfill_script.py` 7.

**No test was deleted, skipped, xfailed or loosened.** A full name-set diff `chunk1-pass..HEAD`
shows exactly two names gone — `test_the_guard_does_not_cover_raw_sockets` and
`test_a_half_written_cache_cannot_be_repaired_by_refetching`. Those are the chunk-1 review's
two deliberate **pins of the defects chunk 2 was asked to fix**, each written to fail the
moment the fix landed and each carrying the instruction to rewrite it. Both were rewritten,
not dropped (`test_the_guard_covers_raw_sockets`, `test_the_guard_covers_clients_that_are_not_requests`,
`test_a_half_written_cache_is_repaired_by_an_explicit_refetch`, `test_the_cache_write_is_atomic`).
No `skip`/`xfail`/`approx` marker exists anywhere in `tests/`.

**Do my additions have teeth?** Mutation-tested on a throwaway copy — ten mutants, **10/10
caught**, control green (51/51):

| Mutant | Result |
|---|---|
| a fetch `error` is recorded as `confirmed-404` (safeguard 1 breached) | **caught** (6 tests) |
| only the era's format is tried before a date is called non-trading | **caught** (3) |
| `atomic_write_with` catches `Exception`, not `BaseException` | **caught** (3) |
| prices go through `float` instead of `Decimal` | **caught** (2) |
| `ingest` records the LEDGER before the ROWS | **caught** (1) |
| the derived calendar treats an unsettled date as a holiday | **caught** (6) |
| `daily()` picks the first row instead of refusing | **caught** (1) |
| the offline guard drops its socket-level patches | **caught** (5) |
| the store returns float64 prices | **caught** (1) |
| re-ingest APPENDS instead of replacing the date | **caught** (1) |

The ledger-order mutant survived my first attempt — my probe mocked `pq.write_table`, a layer
*both* writes go through, so it could not tell the safe order from the unsafe one. It is now
sharpened to fail only the row write, and it kills the mutant.

### REVIEW_1 Finding 1 — the offline guard. **CLOSED, and independently re-attacked.**

Every attack that walked past the chunk-1 guard is now blocked, plus the ones the conftest
docstring newly claims:

| Attack | Before (REVIEW_1) | Now |
|---|---|---|
| `socket.socket().connect(...)` | reached live NSE | **blocked** |
| `socket.connect_ex(...)` (returns errno, never raises — the silent one) | untested | **blocked** |
| `socket.create_connection(...)` | untested | **blocked** |
| `urllib.request.urlopen(...)` | reached live NSE | **blocked** |
| `pandas.read_csv(url)` — the chunk-2-shaped risk | untested | **blocked** (guard message found in the raised chain) |
| `requests` get/post/Session.get/Session.request | blocked | **still blocked** |
| `nse_http.fetch_json` / the new `fetch_binary` | fetch_json only | **both blocked** |
| a **closed local port** — proving the guard is a rule, not an NSE blocklist | untested | **blocked** |

### REVIEW_1 Finding 2 — atomic writes. **CLOSED, and crash-tested four ways.**

`atomic_write_with` was interrupted after the temp file was half-written by
`KeyboardInterrupt`, `SystemExit` and `MemoryError`, and `atomic_write_bytes` was interrupted
*inside `os.replace` itself* — the narrowest window there is. In all four cases the target
still held `GOOD-ORIGINAL` and the directory held exactly one file: **no partial file, no
orphan temp.** The damaged day-cache raises under `allow_network=False` and is repaired under
`allow_network=True` behind a `RuntimeWarning` that names the path.

The same test applied to the store: with `pq.write_table` interrupted, the month file is
byte-unchanged, no `.tmp` survives, the ledger is not advanced, and the date is still in
`pending_dates`. The write **order** (`write_rows` → `record_outcome`) is what makes resume
safe, and it is the right way round.

## 3. The goldens, recomputed independently (directed check 2)

I rebuilt the whole cross-source table from the frozen `poc/data` CSVs and the DERIVED
bhavcopy fixture using plain `csv` + `Decimal`, **importing nothing from `acumen`**, so
agreement means the data agrees rather than that one implementation is self-consistent.

**GOLDEN 1 — TCS 2026-07-20.** `docs/RESULTS.md` §A, read from the document, says
"2026-07-20 close 2251.1, vol 2,202,693". The store returns `close_paise=225110`,
`volume=2202693`, `turnover_paise=497162363920`. Exact. Two vendors, three days apart,
agreeing to the paisa.

**GOLDEN 2 — the 25-day cross-source table, recomputed.**

| | Result |
|---|---|
| bhavcopy `TtlTradgVol` vs SmartAPI `ONE_DAY` volume | **25/25 EXACT** |
| bhavcopy open vs first 1-minute open | **25/25 EXACT** |
| bhavcopy high vs max 1-minute high | **25/25 EXACT** |
| bhavcopy low vs min 1-minute low | **25/25 EXACT** |
| close inside the 15:00–15:29 traded range | **25/25** |
| 1-minute shortfall vs CONTEXT 4.5 gate 1 `[-0.1%, +5.0%]` | **25/25 inside**, observed **+0.025% … +3.581%** |
| my recomputed 1-min sums vs `volume_poc_summary.csv`'s own | **25/25 EXACT** |

The observed band reproduces `docs/RESULTS.md` §C to three decimals (+0.025% … +3.581%), and
375 candles were present on all 25 symbol-days.

**B34, judged on evidence rather than on the report.** The claim is that the daily close must
not be compared to the last 1-minute close. I measured it:

- bhavcopy `ClsPric` == final 1-minute close on **1 of 25** symbol-days;
- bhavcopy `LastPric` == final 1-minute close on **25 of 25**.

So the decision is not merely defensible, it is *necessary*: an equality assertion on the
close would have failed 24 times, and any tolerance wide enough to absorb it would have been
invented rather than derived. **Verified in code:** nothing in `src/` or `tests/` compares
`close_paise` to a 1-minute close; the only close comparison anywhere is the range invariant
at `tests/test_daily_goldens.py:207`. **Verified in a comment/test, not just the report:** the
reason is stated in the module docstring of [test_daily_goldens.py:25-28](tests/test_daily_goldens.py#L25-L28)
and again in the test's own docstring at [test_daily_goldens.py:195](tests/test_daily_goldens.py#L195).
The invariant is also mathematically sound, not merely observed — a VWAP over 15:00–15:29 must
lie inside that window's traded range. See Finding 9 for its one boundary condition.

## 4. Ledger semantics (directed check 3)

| Rule | Verified how | Result |
|---|---|---|
| `confirmed-404` requires **both** formats to 404 (B19) | counted the URLs on a real Sunday: exactly `[udiff, archive]` | **holds** |
| …and if the second format *answers*, the date is `file-present` | forced the archive format to serve a 2026 date; recorded `file-present`, `source_format=archive` | **holds** |
| an `error` can never silently become `confirmed-404` | every retryable status (403, 429, 500, 502, 503, 504) ends `error`, `is_terminal=False`, and the calendar refuses to build over it | **holds, 6/6** |
| a non-404 that is *not* retryable, and a corrupt/HTML body | both end `error`, never absent | **holds** |
| a file that is not the requested date | refused with `error` | **holds** |
| an `error` date IS re-attempted, and only fresh evidence settles it | error → retried → **both** formats asked → `confirmed-404` | **holds** |
| settled dates are skipped on resume | `file-present` and `confirmed-404` never re-offered | **holds** |
| Sunday 2026-07-19 = `confirmed-404` in the live sample | ledger fixture + golden | **holds** |

The distinction is enforced at three independent layers — `NseNotFoundError` as a *type* (not
a string comparison), the loop that only concludes after both candidates, and
`TradingCalendar._derive` refusing outright — and the mutant that collapsed the first layer was
caught by six tests.

## 5. Idempotency (directed check 4) — reproduced

Ingesting both DERIVED fixtures three times over:

```
daily/2018/bhavcopy_2018-01.parquet   dffee5057cde97bc…   (pass 1 == 2 == 3)
daily/2026/bhavcopy_2026-07.parquet   89d4fa05fb323871…   (pass 1 == 2 == 3)
ledger.parquet                        39d6bebba234b971…   (pass 1 == 2 == 3)
```

Row count constant (51), ledger row count constant (7), zero `.tmp` debris. Byte-identity is
the stronger claim and the operator-relevant one: a re-run that rewrote files would defeat any
backup or sync placed around the store. The APPEND mutant is caught.

## 6. The price path (directed check 5)

`Decimal` on the CSV **text** end to end; a value that is not a whole number of paise is
refused in both formats, never rounded. Out of Parquet every price-capable column is pandas
nullable `Int64` — **no float dtype exists anywhere in the frame** — dates come back as
`datetime.date`, and the 497,162,363,920-paise turnover survives exactly. The only `float(` in
`src/` is the backoff sleep `float(2 ** (attempt - 1))`; there is no `round(` at all.

The decision is load-bearing, and I measured how much: **10 of the 217 printed price/turnover
values in the UDiFF fixture would be corrupted by a float path**, e.g. TCS's own close of
`2189.20` on 2026-07-15 → 218919 instead of 218920. But the *example* the code quotes to
justify it is numerically false → **Finding 4**.

## 7. The derived calendar (directed check 6)

- **Refuses unsettled ranges (B28):** an `error` date or a gap blocks the build entirely,
  with a message naming the count and the first offender. The mutant that derived around it
  was caught by six tests.
- **derived == published:** over 2026-07-13..24 the derived trading days are exactly
  `[13,14,15,16,17,20,21,22,23,24]`, identical to the published snapshot's. I re-derived them a
  third way, straight from the ledger CSV, and also checked the **2018** half — which has no
  published calendar in the repo — against the fact that January 2018 carried no NSE holiday
  before the 26th: the derived set is exactly that window's weekdays.
- **bias_pair agreement:** the builder's golden samples three days; I compared **every**
  trading day in the window whose pair stays inside the evidence (8 pairs) — all agree. At the
  window's own edge the derived calendar correctly *refuses* rather than answering.
- **Published path unchanged:** both new fields are `None`, `source == "published"`,
  `weekend_sessions == ()`, and 2026 still has 245 trading days — chunk 1's reviewed behaviour
  is bit-identical.
- **weekend_sessions surfaced,** and empty in both ingested windows as claimed. I built the
  case the windows do not contain, and measured the consequence the architect needs for Q-5:

  ```
  is_trading_day(Sat 2019-06-01)  = True
  is_standard_session(Sat)        = True      <- E2 does NOT exclude it
  bias_pair(Mon 2019-06-03)       = (2019-06-01, 2019-05-31)
  without the Saturday it would be  (2019-05-31, 2019-05-30)   <- one whole candle out
  ```

  The code follows the Q-3 ruling exactly as written; the consequence reaches a day that is
  not itself in question, which is precisely why Q-5 is right to be open. → Finding 11.

## 8. Fixtures (directed checks 7 and 11)

**All 34 frozen files match**, two independent ways: every working-tree file hashes identically
to its git HEAD blob, and every one matches its pinned SHA-256 in `tests/test_fixture_integrity.py`.
`poc/data` is still exactly 28 files. `git status` was clean at review start.

The three new fixtures are properly DERIVED and properly declared. Every claim in
`tests/fixtures/PROVENANCE.md` checks out against the files:

| File | PROVENANCE claim | Measured | Size |
|---|---|---|---|
| `bhavcopy_udiff_sample.csv` | 31 rows, 5 dates, 6 symbols, 34-column header | 31 / 5 / exactly `{BIOCON, DIXON, HDFCBANK, MANAPPURAM, RELIANCE, TCS}` / 34 | 5.9 KB |
| `bhavcopy_archive_sample.csv` | 20 rows, 2 dates, 4 symbols | 20 / 2 / exactly `{JSWSTEEL, NTPC, RELIANCE, TCS}` | 1.9 KB |
| `daily_ledger_window.csv` | 27 dates over the two windows | 27, and the two windows' 404s land on the four weekend dates | 1.0 KB |

PROVENANCE names the source URL, the source CSV's own SHA-256, its line count and the exact
trimming rule per file, and states the VERBATIM/DERIVED distinction up front — a DERIVED
fixture "proves the parser reads real bytes correctly; it is not evidence about the whole
file". That is the right disclaimer and it is written before anyone needed it. Source ZIPs are
not committed, so their digests cannot be re-verified offline; the internal consistency of what
*is* committed is fully verified.

## 9. Q-4 evidence (directed check 8) — reproduced, and worse than the 2026 example

From the frozen **2018** archive fixture, not taken on trust:

| date | symbol | series present |
|---|---|---|
| 2018-01-01 | **NTPC** | `EQ`, `N4`, `N6`, `N7`, `NB`, `NC` — **six** |
| 2018-01-02 | NTPC | `EQ`, `N4`, `N6`, `N7`, `NB`, `ND` — and the sixth is a *different* series |
| 2018-01-01/02 | JSWSTEEL | `EQ`, `P2` |
| 2026-07-14 | BIOCON | `EQ`, `BL` |

`DailyStore.daily("NTPC", …)` **raises** and names all six series plus the `series=` escape;
passing `series="EQ"` returns the clean two-day sequence. An `ast` walk (not a grep — the only
occurrence of the letters is inside a docstring naming it as an example argument) confirms
**no string constant `"EQ"` exists anywhere in `src/` or `scripts/`**. The store refuses to
choose, which is exactly what the STOP rule requires while Q-4 is open.

## 10. The backfill script (directed check 9)

| Requirement | Result |
|---|---|
| `--dry-run` fetches nothing | **PASS**, proved at the session boundary: with `nse_http.new_session` rigged to raise, the run completes cleanly — it never even *constructs* the HTTP session, let alone opens a socket. Same without `--allow-network`. Neither creates the store directory. |
| pacing ≥2s between requests | **PASS on the normal path** (measured on a virtual clock: 2 requests on a 404 day, gap exactly 2.0s), **FAILS on the 403 path → Finding 1** |
| resumable | **PASS** — settled dates never re-offered; error dates retried; `--no-retry-errors` leaves them alone. Ctrl-C mid-run is caught, prints the summary and returns 130 with the store consistent. |
| not importable-with-side-effects | **PASS with a note** — parsed structurally: the module body holds only its docstring, imports, function definitions and the `__main__` guard, plus **exactly one** executed statement, the `sys.path.insert` it needs to find `src/`. Nothing runs on import. → Finding 12 (INFO). |
| never runs under pytest | **PASS** — `scripts/` is not a package, nothing under `src/` imports it, both test modules load it by path, and the `__main__` guard is the only entry. |

The run summary tells the operator in words that "errors and un-attempted dates are NOT
holidays", which is the right thing to say to the person who will decide whether to re-run.

## 11. Class-B decisions B19–B34 — explicit judgment

| # | Judgment | One-line reason |
|---|---|---|
| B19 | **APPROVE** | Verified from both sides: a 404 day costs exactly two requests, and when the *other* format answers, the date is correctly `file-present` with the answering format recorded. CONTEXT 4.1 dates the cutover only to the month, so this converts a documentation ambiguity from silent and permanent into ~1.8 h of extra requests. |
| B20 | **APPROVE** | Attempting weekends is the only way the Q-3 ruling can *see* a weekend session; it also produces the card's Sunday golden. The consequence was raised as Q-5 rather than decided, which is the correct half of the decision. |
| B21 | **APPROVE** | Measured, not assumed: 21 dates x 3,400 symbols is a **113 KiB** file, one symbol's month reads back in 60 ms, and the whole 25-year store extrapolates to ~0.03 GiB. One file per date would indeed have left chunk 3 opening 6,000+ files. |
| B22 | **APPROVE** | The written schema matches field-for-field, and the mutant that let pyarrow infer types was caught immediately. |
| B23 | **APPROVE** | Verified there is **no float dtype anywhere** in a returned frame and that the 497,162,363,920-paise turnover survives exactly — a float64 could not have. |
| B24 | **APPROVE the decision · CHALLENGE the example** | Decimal-on-text is right and load-bearing: 10 of the fixture's 217 printed values would lose a paisa via float. But `float("2251.10") * 100` is exactly `225110.0`, so the number quoted five times as the justification is false → **Finding 4**. |
| B25 | **APPROVE** | Keeping identity/liquidity fields turned out to be load-bearing rather than merely tidy: `LastPric` is the evidence that settles B34 (25/25), and `SctySrs` is what makes Q-4 visible at all. |
| B26 | **APPROVE** | The most important refusal in the chunk. Reproduced on NTPC's six series; the message names every one and points at `series=`. A "largest volume wins" rule would have handed chunk 4 a debenture's candle for IRFC. |
| B27 | **APPROVE** | The reasoning ("everything downstream must behave identically whichever calendar it is handed") is right, and verified: with both new fields `None` the chunk-1 behaviour is bit-identical, 245 trading days and all. |
| B28 | **APPROVE** | Safeguard 1 made structural rather than procedural. Six of my probes fail the moment it is relaxed. Refusing the current year for free (safeguard 3) is a genuinely elegant consequence, not a rationalization. |
| B29 | **APPROVE** | An entry point, not a library, and nothing under `src/` imports it. Its single import-time statement is noted as **Finding 12** (INFO), not charged against the decision. |
| B30 | **APPROVE the intent · CHALLENGE the implementation** | Archiving the SOURCE rather than a re-serialisation is correct (chunk-1 B16 applied to files) — but the write is neither atomic nor resumable → **Finding 3**. |
| B31 | **APPROVE the type · CHALLENGE the "cannot drift" claim** | `NseNotFoundError` as a *type* is exactly right and the whole ledger rests on it. The shared loop does **not** make the two paths equivalent: `fetch_json` retries an unusable HTTP 200 and `fetch_binary` does not → **Finding 2**. |
| B32 | **APPROVE** | Crash-tested four ways including an interrupt inside `os.replace`. `BaseException` is the correct catch and the reasoning names why. Durability caveat → **Finding 6**. |
| B33 | **APPROVE** | Re-attacked with raw socket, `connect_ex`, `create_connection`, `urllib`, `pandas.read_csv(url)`, six `requests` entry points and a closed local port — all blocked; the mutant that removes the socket patches is caught by five tests. Declining `pytest-socket` for ~10 lines is right on a repo whose dependency list is deliberately short. |
| B34 | **APPROVE (strongly)** | Verified by measurement rather than by argument: `ClsPric` equals the final 1-minute close on **1/25** symbol-days and `LastPric` on **25/25**. Refusing to compare the close, and asserting the range invariant instead, is the only honest option. One boundary condition recorded as **Finding 9**. |

## 12. Findings

**Finding 1 — MEDIUM — the cookie warm-up ignores the caller's pacing, so the download path
briefly runs at 4x its own rate.**
[`_warm_up_cookies`](src/acumen/nse_http.py#L375) calls `_throttle(sleep)` **without**
`min_interval`, so it inherits the module default of 0.5 s. Measured on a virtual clock: a
bhavcopy request refused with 403 at `t=0` is followed by the home-page warm-up at `t=0.5`,
not `t=2.0`. The chunk-2 card and this module's own docstring both state one request per two
seconds, and this is the one place that is not true — firing precisely when NSE is already
refusing us, during an unattended multi-hour run. Nothing downstream is corrupted; it is a
politeness and bot-shield-provocation defect. *Suggested:* thread `min_interval` through
`_warm_up_cookies`. *Test kept:* `test_pin_finding_1_the_cookie_warm_up_ignores_the_callers_pacing`
— it asserts the **current, wrong** 0.5 s gap and fails loudly, naming this finding, the moment
it is fixed. `test_the_normal_download_path_never_exceeds_one_request_per_two_seconds` pins the
good path.

**Finding 2 — MEDIUM — a bot-shield page behind HTTP 200 is retried on the JSON path and NOT on
the download path.**
`fetch_json` raises `_Retry` when a 200 does not decode, and retries; `fetch_binary`'s decoder is
`lambda response: response.content`, which accepts anything. Measured with `max_attempts=4` and an
identical HTML body: **JSON path 4 requests, download path 1**, straight to `error`. CLAUDE.md's
network rule and CONTEXT 4.3 both say transient "access denied" bursts are NORMAL — retry — and
NSE's shield does serve HTML behind a 200 (the build's own
`test_html_behind_a_200_is_not_mistaken_for_a_zip` acknowledges the shape). Decision B31 records
the shared loop as making the policy drift-proof between the two paths; this is where it still
differs. **No data is corrupted** — the date lands in `error`, which is never a holiday and is
retried on the next run — so this is robustness, not correctness: a 25-year run gives up early
where it should retry, and the operator re-runs. *Suggested:* give `fetch_binary` a validity
predicate (e.g. treat a body that is not a ZIP as `_Retry`), or narrow B31's wording. *Test kept:*
`test_pin_finding_2_a_bot_shield_page_behind_http_200_is_not_retried_on_downloads`, which pins
both halves of the asymmetry and fails when it closes.

**Finding 3 — LOW — the `--raw-dir` audit trail is neither atomic nor resumable.**
[`_keep_raw`](scripts/backfill_daily.py#L137) writes with a plain `write_text`, bypassing
`atomic_io` — so a Ctrl-C mid-write leaves a truncated CSV in the archive. Worse, it is called
**inside the fetch loop**, after `store.ingest` has settled the date: a date settled by an
earlier run is never archived, and re-running with `--raw-dir` will not backfill it, because
`resolve_dates` correctly reports nothing pending. B30 calls this "the operator's audit trail"
and it is what the three DERIVED fixtures were cut from — so a silently incomplete or truncated
archive is a fixture-provenance risk, not just an operator inconvenience. The store itself is
unaffected. *Suggested:* write through `atomic_write_text`, and either warn when `--raw-dir` is
given for an already-settled range or offer a re-archive path. *Test kept:*
`test_the_raw_csv_archive_is_only_written_for_dates_this_run_fetched` (documents the behaviour).

**Finding 4 — LOW — B24's justifying example is numerically false, in five places.**
`bhavcopy.py`'s module docstring, [`_paise`](src/acumen/bhavcopy.py#L344), a build test's
docstring, the commit body and PROGRESS `decisions: B24` all state that
`float("2251.10") * 100` is `225109.99999999997`. **It is exactly `225110.0`** — the
mathematically exact product `225109.99999999999090…` rounds *up* to the nearest double. So
`int(float("2251.10") * 100) == 225110`, and the canonical example demonstrates nothing. The
decision is nevertheless correct and load-bearing: I measured **10 of the 217** printed values
in the UDiFF fixture where a float path loses a paisa, including TCS's own close of `2189.20`
on 2026-07-15 (→ 218919) and a turnover of `21005660491.10`. The risk of leaving it is real —
a future session that checks the claim finds it false and may conclude the guard is unnecessary
and "simplify" to float. *Suggested:* substitute a true example from this repo's own data
(`2189.20`, `326.65`, `1294.10`, `1296.60` all work). *Test kept:*
`test_a_price_a_float_would_corrupt_survives_the_whole_pipe`, which asserts both the false
example and the true one, so the correction cannot be lost.

**Finding 5 — LOW — four comments cite Q-4 for a question that is Q-5.**
The weekend-session question is **Q-5**; **Q-4** is the series ambiguity. Four places have them
crossed: [calendar.py:370](src/acumen/calendar.py#L370), [calendar.py:390](src/acumen/calendar.py#L390),
[test_derived_calendar.py:197](tests/test_derived_calendar.py#L197) and
[test_derived_calendar.py:239](tests/test_derived_calendar.py#L239). (`test_daily_store.py:228`
cites Q-4 correctly.) Both items are open and both are class A, so a session following the
`weekend_sessions` docstring to "QUESTIONS.md Q-4" lands on the series ruling and may believe the
weekend question is answered when it is not — or vice versa. Documentation only; nothing
executes on it.

**Finding 6 — LOW — `atomic_write_with` is process-crash safe but not power-loss safe.**
[`atomic_write_bytes`](src/acumen/atomic_io.py#L28) flushes and `fsync`s before replacing;
[`atomic_write_with`](src/acumen/atomic_io.py#L59) hands the path to a third-party writer and
`os.replace`s whatever it produced, with no `fsync` of the file and no `fsync` of the containing
directory in either function. Every store and ledger write goes through the un-fsynced path.
Against the failure this module was built for — a Ctrl-C or an exception — it is fully correct,
and I proved that four ways. Against a power cut or a kernel panic the rename can be durable
before the data is, leaving a zero-length or partial Parquet with a valid name. On a laptop
running an hours-long backfill this is a real if unlikely scenario. *Suggested (chunk 13, when
anything runs unattended):* `fsync` the temp file before `os.replace` and the directory after.

**Finding 7 — LOW — nothing ever cross-checks the ledger against the rows it claims exist.**
`file-present` in `ledger.parquet` and the presence of that date's rows in the month file are
maintained independently. The **write order makes this safe under a crash** (rows first — I
verified the ledger is untouched when only the row write fails, and the mutant that reverses the
order is caught), but there is no read-side invariant: a month file lost to a disk error, a bad
sync or a manual `rm` leaves a store that reports a trading day with no candles, and
`TradingCalendar.from_daily_store` would still build happily from the ledger alone. The golden
store in `tests/test_daily_goldens.py` is itself constructed this way — its ledger asserts
`file-present` for 22 dates whose rows the DERIVED fixture does not contain — so no test
exercises the agreement. *Suggested:* a `DailyStore.verify(from, to)` that reports ledger rows
with no data, run once before chunk 9's full backtest.

**Finding 8 — INFO — the ledger rewrite is O(n²); measured, and not a problem.**
`record_outcome` reads the entire ledger and rewrites it for every date. Measured: 22 ms/date at
250 rows, 45 ms/date at 2,000 rows, growing linearly, extrapolating to **~20–24 minutes** of
ledger I/O over a 9,700-date run. Month-file rewrites add **~20 minutes** at 3,400 symbols/day.
Against the ≥5.4 h the 2 s pacing alone costs, both are noise. Recorded with numbers so chunks 5B
and 9 need not re-derive them, and so the growth is a known quantity if the ledger is ever reused
for something much larger. `record_outcomes` (plural, one write) already exists for batch callers.

**Finding 9 — INFO — the closing-half-hour invariant has a boundary condition, and a stronger
comparison was left unused.**
"The close lies inside the 15:00–15:29 range" follows from NSE's last-30-minute VWAP definition
**only when trades occurred in that window**; on an illiquid symbol-day with none, NSE falls back
to the last traded price, which need not satisfy it. The golden is parametrized over five liquid
symbols, so this never fires here — recorded so chunk 5A's gate does not adopt the invariant as
universal across ~210 symbols and 25 years. Separately: `LastPric` equals the final 1-minute close
on **25/25**, an exact cross-source equality the goldens do not assert. *Test kept:*
`test_the_daily_close_is_not_the_last_traded_price_but_lastpric_is`.

**Finding 10 — INFO — `UDIFF_FIRST_DATE` is a hardcoded date in `src/`, and it is the right call.**
CLAUDE.md bans hardcoded dates. [bhavcopy.py:72](src/acumen/bhavcopy.py#L72) has one. Judged
acceptable on the same basis as chunk-1 B6's `SESSION_OPEN`/`SESSION_CLOSE`: it is CONTEXT 4.1
law rather than a tunable, it cites the spec inline, and — unlike a normal magic number — being
*wrong* about it is harmless, because `candidate_formats` tries the other format before any date
may be called non-trading. Recorded so a later reader does not mistake it for a defect, or
"fix" it into a config key where it could move without an architect spec change.

**Finding 11 — INFO (for the architect, not chargeable to chunk 2) — Q-5's consequence, measured.**
On a derived calendar containing a Saturday session: `is_trading_day` True, **`is_standard_session`
also True — E2 does not exclude it** — and Monday's CONTEXT 3.2 bias pair becomes
`(Sat, Fri)` instead of `(Fri, Thu)`: one whole candle out, on a day that is not itself in
question. The code follows the Q-3 ruling exactly as written and makes the case visible via
`weekend_sessions` rather than deciding it, which is correct. Neither ingested window contains
one, so nothing in chunk 2 turns on it — but chunk 9's full run will meet several. *Test kept:*
`test_a_weekend_session_is_surfaced_and_moves_the_following_monday`.

**Finding 12 — INFO — the backfill script mutates `sys.path` at import time.**
[backfill_daily.py:32](scripts/backfill_daily.py#L32) inserts `src/` on import so the script runs
as a plain file with no install step. It is the module body's only executed statement (verified by
parsing, not grepping), it is deliberate, and B29's "not importable as a library" framing already
covers it. Recorded because "no import side effects" is a claim worth being precise about, and
because a future `python -m` or console-entry-point packaging would make it redundant.

## 13. Checklist coverage (`personas/code_reviewer.md`)

1. **Tests** — 513/513 green from clean; error paths carry the weight (both 404s, every
   retryable status, corrupt ZIP, HTML-behind-200, wrong-date file, empty file, missing column,
   sub-paise price, non-numeric price, tz-aware stamp, unknown outcome name, ledger gaps and
   errors, backwards ranges, empty symbol list, ambiguous symbol-day). No test deleted, skipped,
   xfailed or loosened — the two vanished names are the chunk-1 pins, rewritten as instructed.
   Asserts are exact throughout; the one band in the suite is CONTEXT 4.5 gate 1's own. My 51
   additions are mutation-tested, 10/10 mutants caught, control green.
2. **Failure behavior** — throttle verified on a virtual clock (2.0 s on the download path,
   exception at Finding 1); four attempts with 1/2/4 s backoff; 401/403/429/5xx retried, 404 failed
   fast **as a distinct type**, everything else failed fast; a transient burst is never reported as
   an empty result and the message says so in words. Downloads resumable and Ctrl-C-safe;
   interrupted runs leave no half-written file and no orphan temp (proved four ways). No bare
   `except:` in `src/` or `scripts/`; every broad catch is typed and re-raised `from exc`. Errors
   are logged with the date and the reason. Gaps: Findings 1, 2, 3, 6.
3. **Idempotency** — byte-identical across three passes and both eras; re-ingest replaces rather
   than appends; the ledger keeps one row per date; a crash between the two writes re-does the
   date rather than settling it. Gap: Finding 7.
4. **Secrets** — clean. No credential pattern anywhere in the span; no `.env`, `data/`, `cache/`
   or `logs/` path entered history; `default_store_root()` uses `include_env=False` so the backfill
   path never touches the operator's credentials. `.env` was never read by this review.
5. **Time & precision** — integer paise via `Decimal` on text, refused rather than rounded; no
   float in any price path and no float dtype out of Parquet; no float equality anywhere. Naive IST
   enforced — a tz-aware ledger stamp raises, and `parse_nse_date` is still the locale-independent
   map. Clock reads are confined to `download_bhavcopy`'s `now=` default, the throttle's
   `time.monotonic`, and the script's banner — none inside a pure function. E12 is untouched by
   this chunk.
6. **Structure** — no engine module exists yet, and none was pre-built. The parse half of
   `bhavcopy.py` is verifiably pure (bytes in, rows out — I inspected `extract_csv`,
   `parse_bhavcopy`, every `_*_row`, `_paise`, `_whole`, the date parsers, `candidate_formats`,
   `url_for`, `date_range`, `summarise`); `daily_store.py` is file I/O with zero network and zero
   strategy; `calendar.py`'s new constructors duck-type the store so the calendar never imports the
   storage layer. Module boundaries match CONTEXT 6. One hardcoded spec date, judged → Finding 10.
7. **Performance sanity** — measured, not asserted: 113 KiB per month file at realistic width,
   60 ms to read one symbol's month, ~0.03 GiB for the whole store, ~40 min of total file I/O
   against ≥5.4 h of mandatory pacing → Finding 8. Nothing here will take days.
8. **Git & docs** — 5 logical commits, single human author, WHAT/WHY bodies citing chunk and spec
   section, **no AI attribution anywhere** in any subject, body, trailer or file. The prep commit
   keeps the `chunk<N>-prep:` prefix per the architect's ruling recorded in REVIEW_1 §8 (closing
   REVIEW_1 F6), and REVIEW_1.md was **append-only** — zero lines removed. PROGRESS entry is
   complete against the plan §6 template, names its digests (closing REVIEW_1 F5), and its
   `state-for-next-session` volunteers four honest limits including the one that matters most
   (Q-4 blocks chunk 3). STATUS.md updated. QUESTIONS.md: Q-3 resolved with per-clause evidence,
   Q-4 and Q-5 raised instead of decided. Cross-reference slip → Finding 5.
9. **Dependency hygiene** — `pyproject.toml` unchanged in the span; no new package; `pandas` and
   `pyarrow` were already pinned at chunk 0. `pytest-socket` was considered and declined with a
   recorded rationale (B33). No Class-B decision was owed and none is missing.

## 14. Scope

`9257008..52791e0` is chunk-2 scope plus the architect-directed prep. New code is three modules —
`atomic_io.py`, `bhavcopy.py`, `daily_store.py` — one script, and two additive changes to existing
modules (`nse_http.fetch_binary` + `NseNotFoundError` + atomic cache writes; `TradingCalendar`'s
two derived constructors and two optional fields). New data is three DERIVED fixtures.

Nothing from a later chunk appears: no corporate-action code, no SmartAPI client, no instrument
master, no `bias`/`poc`/`signals`/`simulate`, no tick table, no series default. The chunk-1
published-calendar path is provably unchanged. Every deliverable the card names is present:
downloader for both formats, resumable, politely paced; Parquet store keyed symbol x date;
universe filtering on query; and `daily(symbol, from, to)` returning RAW prices. Scope discipline
is clean.

This review added exactly one file — `tests/test_review2_probes.py` (51 tests) — and modified
**no file under review**. No fixture was touched. No file was moved.

---

## 15. Fix log (appended by later sessions — the review text above is unchanged)

| Finding | Status | Closed by | What changed |
|---|---|---|---|
| F1–F12 | open | — | Two pin tests (F1, F2) will fail loudly when those findings are fixed; each names the finding to close. |
