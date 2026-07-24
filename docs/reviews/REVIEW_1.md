# REVIEW_1 — chunk 1 · Universe & calendar

**Reviewer:** fresh code-review session (`personas/code_reviewer.md`; plan.md chunk 1 is review type **C**).
**Date:** 2026-07-24 · **Span reviewed:** `02057c7..c047ec5` (5 commits, everything after tag `chunk0-pass`)
**Builder entry reviewed:** PROGRESS.md `[2026-07-24 20:41] chunk 1 · build · done`

## VERDICT: **PASS**

The whole suite is green from a clean state, both card goldens and all seven hand-computed
bias pairs survive an independent recomputation from the raw JSON, every frozen fixture is
byte-identical, no secret exists anywhere in the span, and Q-3 was raised instead of guessed
— which is the single most important thing this chunk did. Ten findings are recorded below:
two MEDIUM, five LOW, three INFO. None is a FAIL trigger; none blocks chunk 2's build.

Two MEDIUM findings are forward-looking and land in code chunk 2 will inherit — the offline
guard is narrower than its recorded claim (F1), and the day-cache write is not atomic (F2).
Both should be fixed in the fetch layer before chunk 13 runs anything unattended.

**One item outside chunk 1's control needs the architect before chunk 2 starts:** the Q-3
ruling relayed to this session is not recorded anywhere in the repo (F10).

---

## 1. Architect's directed checks

| # | Check | Result |
|---|---|---|
| 1 | Prep commit: four Q-1 moves are 100% renames; F3 extends ASCII to `config.yaml`; F4 on the six named tests; judge B18's seventh | **PASS** — proved stronger than `-M`: each destination blob SHA *equals* its source blob SHA (`RESULTS.md` `bd0730bf`, `acumen_poc.md` `0d5e7ca3`, the `.docx` `012a15bf`, `requirements.txt` `a2215b83`), so the bytes are provably unchanged, binary included. F3: the walk now appends `config.yaml` and a second test asserts that coverage. F4: all six converted; one `include_env=True` remains, at [tests/test_config.py:187](tests/test_config.py#L187). B18 judged in §4 → **Finding 7**. |
| 2 | `tick_sizes.json` matches the Q-2 record exactly | **PASS** — TCS 0.10 · RELIANCE 0.10 · HDFCBANK 0.05 · DIXON 1.00 · MANAPPURAM 0.05, in rupees (already ÷100 per CONTEXT 4.3), plus the `_note` naming the tests-only constraint verbatim. Five symbols, no sixth, no `src/` lookup table anywhere. |
| 3 | Prove the no-network guard trips on a socket | **FAIL as worded → Finding 1.** The guard patches `requests.Session` only. From inside a test, a raw socket **connected** to `www.nseindia.com:443` and `urllib.request.urlopen` **reached the live site** — neither tripped it. It *does* cover every `requests` entry point (`get`/`post`/`request`/module-level, and `nse_http.fetch_json` itself): 6 kept tests prove that. |
| 4 | Recompute all 7 `bias_pair` goldens by hand from the frozen JSON | **PASS** — §3 below. All 7 confirmed by hand, then by a second implementation that never imports `TradingCalendar`. Extended to **all 243** in-year pairs; two implementations agree everywhere. |
| 5 | Snapshots hash to the digests in the chunk-1 PROGRESS entry; raw payloads | **PASS (premise corrected → Finding 5)** — the PROGRESS entry records no digests; they live in `tests/test_fixture_integrity.py`, a better home. Verified anyway: all three match their pinned values *and* their HEAD blobs. Both snapshots are raw — universe is exactly `{"data": {IndexList, UnderlyingList}}`, holidays carries all 12 NSE segments. No wrapper key. |
| 6 | E2/E12 containment admits 09:15..15:29 (1-min) and 09:15..15:15 (15-min) | **PASS** — enumerated the full day, not sampled: exactly **375** 1-min stamps and exactly **25** on-grid 15-min stamps. Boundaries verified: 09:14 ✗, 15:29 ✓, 15:30 ✗ (1-min); 15:00 ✓, 15:15 ✓, 15:16 ✗ (15-min). The 15:00 15-min case was **not** covered by the build; it is now. Alignment caveat → Finding 4. |
| 7 | Naive-IST enforcement (B8): both rejections raise | **PASS** — and widened from the build's 2 entry points to the whole surface: all four date-taking methods reject a `datetime` and a tz-aware value, all three stamp-taking functions reject tz-aware, and a tz-aware holiday cannot be built into a calendar. |
| 8 | Universe hygiene: 5 indexes excluded, 210 equities, sorted/deduped | **PASS** against the frozen snapshot. 210 raw rows → 210 symbols, zero duplicates, sorted, upper-cased, TCS + RELIANCE present. The 5 index symbols (BANKNIFTY, FINNIFTY, MIDCPNIFTY, NIFTY, NIFTYNXT50) intersect the universe in **∅**. NSE's raw order is *not* sorted, so B9's normalization is real work, not a no-op. |
| 9 | Judge B1–B18 | **Done** — §4. Sixteen approved outright, B2 approved-with-challenge (F1), B18 approved-with-caveat (F7). |
| 10 | 28 `poc/data` CSVs + 3 new fixtures match pinned digests; tree clean | **PASS** — 28/28 match and the file set is exactly 28; 3/3 new fixtures match. `git status` clean at review start. |

**Disclosure.** Proving Finding 1 required issuing real traffic: one TCP connect and one GET
to `nseindia.com`'s public home page. That is one page view, not an API pull, and it is
comfortably inside CONTEXT 4.1's politeness rule. **The kept test sends nothing** — it uses a
closed loopback port.

## 2. Tests

`python -m pytest` from a clean state (`.pytest_cache` and every `__pycache__` deleted first):

> **284 passed / 0 failed** in 3.70s — 248 from the build (matching the builder's claim
> exactly: 91 at chunk-0 review, +1 prep, +156 chunk 1) and 36 added by this review.

Per file: `test_calendar.py` 96 · `test_review1_probes.py` 36 (new) · `test_fixture_integrity.py` 35 ·
`test_config.py` 33 · `test_universe.py` 32 · `test_smoke.py` 28 · `test_nse_http.py` 24.

**No test was deleted, skipped, xfailed or loosened.** A full name-set diff `chunk0-pass..HEAD`
shows exactly one name gone — `test_project_python_sources_are_ascii_only`, renamed to
`test_project_runtime_sources_are_ascii_only` while being **broadened** to cover `config.yaml`
(REVIEW_0 F3). No `skip`/`xfail`/`approx` marker exists anywhere in `tests/`. Asserts are
exact throughout; the failure paths carry real weight (403 bursts, HTML-behind-200, damaged
cache, malformed rows, bad dates, unusable segments).

**Do the new tests have teeth?** I mutation-tested my own additions on a throwaway copy —
four mutants, all **caught**, control green:

| Mutant | Result |
|---|---|
| `bias_pair` returns the pair swapped | **caught** |
| `prev_trading_day` ignores holidays (weekends only) | **caught** |
| `SESSION_CLOSE` moved to 15:29 | **caught** |
| containment uses `t <= close` instead of `t + minutes <= close` | **caught** |

## 3. The bias pair, recomputed independently (directed check 4)

The builder's comments were not trusted. I rebuilt 2026's trading days straight from
`holidays_2026.json` with a separate implementation, cross-checking every parsed date against
the `weekDay` string NSE ships beside it (**20/20 agree**, so a transposition or an off-by-one
year could not survive), then walked the pairs by hand.

All 20 CM holidays fall in 2026; four of them (15-Feb Sun, 21-Mar Sat, 15-Aug Sat, 08-Nov Sun)
already land on a weekend and therefore cost no trading day. 365 − 104 weekend days − 16
weekday holidays = **245 trading days**, which is what the calendar reports.

| D | expected `(current, previous)` | hand-derivation | verdict |
|---|---|---|---|
| Tue 27-Jan | (Fri 23-Jan, Thu 22-Jan) | Mon 26 Republic Day → Sun 25 → Sat 24 → **Fri 23**; then **Thu 22** | ✅ |
| Thu 23-Jul | (Wed 22-Jul, Tue 21-Jul) | no July holidays; plain walk | ✅ |
| Mon 20-Jul | (Fri 17-Jul, Thu 16-Jul) | Sun 19 → Sat 18 → **Fri 17**; then **Thu 16** | ✅ |
| Mon 06-Apr | (Thu 02-Apr, Wed 01-Apr) | Sun 05 → Sat 04 → Fri 03 Good Friday → **Thu 02**; then **Wed 01** | ✅ |
| Mon 16-Feb | (Fri 13-Feb, Thu 12-Feb) | Sun 15 is Mahashivratri *and* a Sunday → Sat 14 → **Fri 13**; then **Thu 12** | ✅ |
| Wed 11-Nov | (Mon 09-Nov, Fri 06-Nov) | Tue 10 Balipratipada → **Mon 09**; then Sun 08 (Laxmi Pujan + Sunday) → Sat 07 → **Fri 06** | ✅ |
| Wed 04-Mar | (Mon 02-Mar, Fri 27-Feb) | Tue 03 Holi → **Mon 02**; then Sun 01 → Sat 28-Feb → **Fri 27-Feb** | ✅ |

**7/7 confirmed by hand.** I then extended the check past the fixture: the two implementations
agree on **every** 2026 trading day whose pair stays inside the covered year (243 days), and no
leg of any pair is ever a weekend day or a holiday. CONTEXT 3.2's orientation is right —
`current` is candle(D−1), the *later* day — and the swap mutant proves the test would catch an
inversion, which is the failure mode that would silently flip every bias in chunk 4.

## 4. Class-B decisions B1–B18 — explicit judgment

| # | Judgment | One-line reason |
|---|---|---|
| B1 | **APPROVE** | A third module is scope-legal (the card names deliverables, not a ceiling) and correct: both endpoints need identical CONTEXT 4.1 discipline, and the alternative — `calendar.py` importing `universe.py` — would be a worse dependency than either. |
| B2 | **APPROVE the opt-in · CHALLENGE the claim** | `allow_network=False` by default is right and verified (a no-flag `fetch_universe` raises before any socket exists). But "FAILS any test making a real HTTP request" is broader than what conftest enforces — see **Finding 1**. |
| B3 | **APPROVE** | The most valuable decision in the chunk. Verified: a 2027 date raises rather than inventing ~12 phantom trading days. This is CLAUDE.md rule 1 made executable, and Q-3 is raised properly. Caveat: **Finding 3**. |
| B4 | **APPROVE** | Verified it is still a plain tuple (`pair == (current, previous)` unpacks), the field order matches CONTEXT 3.2, and my swap mutant confirms the naming actually buys protection for chunk 4. |
| B5 | **APPROVE** | Derived from E12 + §4.5 gate 2 rather than assumed, and it lands exactly right: 375 one-minute stamps and 25 on-grid 15-minute stamps, both boundaries tight. Caveat: **Finding 4**. |
| B6 | **APPROVE** | CLAUDE.md bans hardcoded ticks/symbols/dates/magic numbers; the 09:15–15:30 session is none of those — it is CONTEXT 3.1 law, and a config key would let it move without an architect spec change. Both constants cite the spec inline. |
| B7 | **APPROVE** | Unusually well evidenced: the locale risk in `%b` is real, and the explicit map is cross-checked against NSE's own `weekDay` field. I re-verified independently — 20/20. |
| B8 | **APPROVE** | Verified across the entire public surface, not just the two entry points the build tested. Directly closes REVIEW_0 Finding 7, and pushes normalization to the ingest layer where it belongs. |
| B9 | **APPROVE** | Verified against the frozen snapshot: NSE's raw order is *not* sorted, so this is real normalization; 210 unique symbols, zero index leakage. |
| B10 | **APPROVE** | Correctly reasoned. CONTEXT says "~210" and states no minimum; an invented floor is exactly the magic number CLAUDE.md bans. The 210 assertion lives in a test, which is its right home. |
| B11 | **APPROVE** | The split is the point: `fetch_*` raises and names the cache's date, `load_cached_*` returns `(fetched_on, value)`. A caller that accepts yesterday's universe has to say so in its own code. Both paths verified. |
| B12 | **APPROVE the principle** | Consistent with chunk-0 B5 — a damaged file must fail loudly, never fall back. It is also what makes a half-written cache unrecoverable (**Finding 2**); the fix there is atomic writes, never a silent fallback. |
| B13 | **APPROVE** | Verified the default path resolves under the gitignored `/data/` that chunk-0 B8 anchors, and a test pins the location so a later refactor cannot drift it into the repo. |
| B14 | **APPROVE** | Verified three ways: the warm-up fires once on a 403 burst, never when nothing is refused, and a *failing* warm-up does not abort the real request — which matches the observed reality that NSE's home page 403s this client while the API answers 200. |
| B15 | **APPROVE** | `default_cache_dir()` is a separate opt-in with a local import and `include_env=False`, so nothing on the parse path can reach the operator's credentials. Same spirit as REVIEW_0 F4, applied before it was asked for. |
| B16 | **APPROVE** | This is what made an independent review possible at all. Verified both payloads are raw endpoint shapes; a test asserts it, so a later prettify cannot pass unnoticed. |
| B17 | **APPROVE** | The asymmetry with `poc/data` is correct: later chunks legitimately add fixtures under `tests/fixtures/`, so an exact-set assertion would fight them, while a per-file digest still forbids the thing that must never happen. |
| B18 | **APPROVE (caveat)** | The six are done. The seventh's justification is weaker than stated — the fake token reaches `os.environ` via the explicit `load_env(env_file)` two lines earlier, so the assertions hold with `include_env=False`, and the call still pulls the operator's real `.env`. The genuine blocker is a chunk-0 API limit, not a chunk-1 choice. → **Finding 7**. |

## 5. Findings

**Finding 1 — MEDIUM — the offline guard is `requests`-shaped, not network-shaped.**
`tests/conftest.py` monkeypatches `requests.Session.request` and `.get`. Decision B2 records
this as an autouse guard that "FAILS any test making a real HTTP request". It does not: from
inside a test, `socket.socket().connect(("www.nseindia.com", 443))` **succeeded** and
`urllib.request.urlopen("https://www.nseindia.com/")` **reached the live site**, neither
tripping the guard. *Today this is a claim defect, not a behavior defect* — `nse_http.py` uses
`requests` exclusively, and I verified the guard trips on every `requests` entry point
including `post` (which delegates to the patched `request`) and through `nse_http.fetch_json`
itself. The exposure is forward: chunk 2 is a download-heavy chunk, and `pandas.read_csv(url)`,
`urllib`, or any `httpx`/`aiohttp` adoption would sail straight through a guard whose whole
purpose is to stop the suite hammering an endpoint CONTEXT 4.1 limits to one pull a day. This
is the same shape as REVIEW_0 Finding 3 — a recorded decision claiming more than its test
enforces. *Suggested (chunk 2, not a fix session):* also patch `socket.socket.connect`, or
adopt `pytest-socket`; alternatively narrow B2's wording to "any `requests` call". *Tests
kept:* `test_the_guard_trips_on_every_requests_entry_point` (5 cases),
`test_the_guard_trips_through_the_real_fetch_layer`, `test_the_guard_does_not_cover_raw_sockets`
(closed loopback port — sends nothing, and fails loudly if the boundary ever moves).

**Finding 2 — MEDIUM — the day-cache write is not atomic, and a damaged cache cannot self-heal.**
[nse_http.py:186](src/acumen/nse_http.py#L186) writes the envelope with `path.write_text(...)`
in place. A crash, a Ctrl-C or a full disk mid-write leaves truncated JSON. Because
[`cached_json`](src/acumen/nse_http.py#L218) reads the cache *before* it considers the network,
**even `allow_network=True` cannot repair it** — I confirmed both paths raise, so the operator
must delete the file by hand. The `"unreadable or not valid JSON"` message, unlike the
envelope-shape one, does not tell them that. `personas/code_reviewer.md` checklist 2 names this
explicitly ("interrupted runs leave no half-written files — write-temp-then-rename"). Impact
today is nil (nothing runs unattended); impact at chunk 13 is a pre-09:15 morning refresh that
dies and computes no bias for the day. *Verified good news, recorded so it is not lost:* a
failed live pull never clobbers a good cache (the write happens only after a successful fetch),
and refetching the same day is byte-idempotent. *Suggested (chunk 2/13, same layer):* write to
a temp file and `os.replace`, and let `allow_network=True` overwrite a damaged cache.
*Tests kept:* `test_a_half_written_cache_cannot_be_repaired_by_refetching`,
`test_a_failed_live_pull_never_clobbers_a_good_cache`, `test_refetching_the_same_day_is_idempotent`.

**Finding 3 — LOW — the covered-years guard protects the answer, not the question.**
`is_trading_day(2027-01-01)` raises, but `prev_trading_day(2027-01-01)` returns `2026-12-31`.
The answer is *correct* — every day it inspects is inside 2026 — and `bias_pair` is not
exposed, because it validates its argument first. But Q-3's whole point is that a caller must
never receive a plausible answer for a year the repo holds no data for, and this surface is
inconsistent about it. *Suggested:* call `_require_covered(checked)` at the top of
[`prev_trading_day`](src/acumen/calendar.py#L250). *Test kept:*
`test_prev_trading_day_answers_for_a_date_in_an_uncovered_year`.

**Finding 4 — LOW (forward-looking) — E2 containment says nothing about grid alignment.**
`is_session_time(..., minutes=15)` accepts 361 distinct stamps, of which only 25 sit on the
E12 grid; an off-grid stamp such as 09:20 passes. This is **correct per E2 as written** — it is
a containment rule, and inventing an alignment requirement would be exactly the silent
assumption CLAUDE.md rule 1 forbids. Recorded so chunk 5A's aggregator does not mistake this
filter for proof that a bar sits on the E12 grid. *Test kept:*
`test_containment_does_not_check_grid_alignment`.

**Finding 5 — LOW — the chunk-1 PROGRESS entry records no digests.**
It states the three new fixtures are "pinned by digest in the same commit" but carries no
digest, so directed check 5 cannot be executed from the entry alone. In substance this is an
*improvement* on REVIEW_0 Finding 1: the digests live in `tests/test_fixture_integrity.py`,
where they are executable rather than prose. Verified regardless — all three match their pinned
values and their HEAD blobs. *Suggested:* future entries say where the digests live.

**Finding 6 — LOW — the prep commit deviates from the commit-message convention.**
`02057c7` uses the prefix `chunk1-prep:` rather than CLAUDE.md's `chunk<N>:` form, and omits
the `(unreviewed)` suffix, although it changes test files and sits inside the review span. The
intent is clear and arguably clearer than the convention. Recorded because CLAUDE.md states the
format once and without exception, and any later scan keyed on `chunk<N>:` would miss this
commit. No history rewrite is warranted.

Related, same severity: the chunk-1 PROGRESS entry is stamped `20:41`, but its own commits are
timestamped 19:44–19:46 and the machine clock read 20:28 when this review ran — so the stamp is
ahead of both the work and the wall clock. Harmless, but PROGRESS.md's ordering is the ledger
later sessions trust, so this review stamped its entry with the true clock time rather than
inflating past it.

**Finding 7 — LOW — one test still loads the operator's real `.env`** (this is B18's caveat).
REVIEW_0 F4 went from six call sites to one, which is real progress. The survivor,
[tests/test_config.py:187](tests/test_config.py#L187), calls `load_config(..., include_env=True)`,
which calls `load_env()` with no argument → the repo-root `.env` → live credentials into
`os.environ` for the rest of the pytest process. B18 defends it as "that code path IS its
subject", but the assertions do not depend on it: the fake token reaches `os.environ` from the
explicit `load_env(env_file)` two lines earlier, so they hold identically with
`include_env=False`. The real obstacle is that `load_config` exposes no env-path parameter — a
chunk-0 API limit, not a chunk-1 choice. No leak occurs today (nothing prints the environment,
`--showlocals` is off). *Suggested:* `monkeypatch.setattr(config, "DEFAULT_ENV_PATH", env_file)`
and drop the last exception.

**Finding 8 — INFO — `date.today()` is the system date, not IST.**
`fetch_universe`/`fetch_calendar` default `today` to `date.today()` while CONTEXT 7-E8 mandates
IST. Both docstrings say so honestly and the parameter is injectable, and the blast radius is
confined to the cache key (on a non-IST machine, at worst an extra pull or a stale serve — the
pure engine never sees it). Recorded for chunk 13, which schedules against the clock.

**Finding 9 — INFO — `parse_index_symbols` is lenient where `parse_universe` is strict.**
[universe.py:111](src/acumen/universe.py#L111) silently drops malformed index rows in a
comprehension, while a malformed *underlying* row correctly fails the whole pull. Harmless —
indexes are never traded and the function exists only to assert the exclusion — but the
asymmetry could later be read as intent.

**Finding 10 — INFO (not chargeable to chunk 1) — E2 cannot detect a shortened session.**
A special/shortened session on a date the calendar *does* list as a trading day, whose bars all
fall inside 09:15–15:30, passes this filter. E2's detection rule is exactly two clauses and the
builder implemented both faithfully; catching this case would require inventing a third. It has
to be caught downstream by §4.5 gate 2 / E4. Recorded so chunk 9's exclusion counting does not
assume E2 covers it.

### Item for the architect, outside chunk 1's control

**The Q-3 ruling is not recorded in the repo.** This session was told the architect ruled
option (a) with safeguards, executed in chunk 2, and asked to verify the ruling is recorded.
It is not: `QUESTIONS.md` Q-3 still reads `class A · open` and closes with three unchosen
options. Q-1 and Q-2 each carry an explicit **ARCHITECT'S RULING** block; Q-3 has none. This is
not a chunk-1 defect — the ruling post-dates the build — and I did **not** act on it, per
instruction. But the repo is the record, and chunk 2's builder reads `QUESTIONS.md`, not this
chat, so it would start work believing the calendar's history problem is unanswered.
**Recommended: write the ruling into Q-3 before the chunk-2 session opens.**

## 6. Checklist coverage (`personas/code_reviewer.md`)

1. **Tests** — 284/284 green from clean; error paths carry the weight (403 bursts, exhausted
   budgets, HTML-behind-200, non-transient 404, damaged caches, malformed payloads and rows,
   bad dates, pathological calendars); no test deleted, skipped or loosened; fixtures frozen
   and digest-guarded (28 + 3). My additions are mutation-tested, 4/4 mutants caught.
2. **Failure behavior** — throttle ≥ 0.5s process-wide; four attempts with 1s/2s/4s backoff;
   403/429/5xx retried and 404 failed fast; a transient burst is never reported as an empty
   result, and the error message says so in words. No bare `except:` in `src/`; every broad
   catch is `requests.RequestException`, `OSError`/`ValueError` or `yaml.YAMLError`, re-raised
   with `from exc`. The one real gap is atomicity → Finding 2.
3. **Idempotency** — verified: the same calendar day never pulls twice across six calls, a new
   day pulls exactly once, and a repeat fetch leaves the cache byte-identical.
4. **Secrets** — clean. No credential pattern in any file changed in the span; no `.env`,
   `data/`, `cache/` or `logs/` path entered history; nothing on the parse path can read
   `.env` (B15). `.env` contents were never read by this review. Residue → Finding 7.
5. **Time & precision** — no price math in this chunk. Naive-IST is enforced loudly and now
   tested across the whole surface; E12 open-stamping is implemented as the containment rule
   and verified at every boundary; no `datetime.now()` anywhere; the only clock reads are
   `date.today()` defaults in the two opt-in fetch functions and `time.monotonic()` in the
   throttle, all outside the pure layer.
6. **Structure** — no engine module exists yet. The parse layer is verifiably pure: I
   inspected `parse_universe`, `parse_index_symbols`, `parse_holidays`, `parse_nse_date`,
   `is_session_time` and the whole `TradingCalendar` class for I/O, network and clock reads —
   all clean. Fetch halves are separated and documented as such. No hardcoded tick, symbol,
   date or path; `SESSION_OPEN`/`SESSION_CLOSE` are spec law with a recorded rationale (B6).
   `src/acumen/calendar.py` does not shadow stdlib `calendar` (only `src/` is on the path).
7. **Performance sanity** — n/a; two once-a-day JSON pulls and an O(days) walk bounded at 30.
   Suite runs in 3.7s.
8. **Git & docs** — 5 logical commits, single human author, WHAT/WHY bodies citing chunk and
   spec section, **no AI attribution anywhere** in any subject, body, trailer or file. PROGRESS
   entry complete against the plan §6 template with an honest `state-for-next-session` that
   volunteers its own weak points (2026-only calendar, no CLI entry point, live path exercised
   once). STATUS.md updated. Q-1/Q-2 closed with evidence, Q-3 raised instead of guessed.
   Convention nit → Finding 6.
9. **Dependency hygiene** — zero change to `pyproject.toml`; `requests==2.32.3` was already
   pinned at chunk 0. No new package, so no Class-B decision was owed.

## 7. Scope

`02057c7..c047ec5` is chunk-1 scope plus the architect-directed prep. New code is three
modules — `nse_http.py`, `universe.py`, `calendar.py` — and their tests; new data is three
frozen fixtures. Nothing from a later chunk appears: no bhavcopy, no SmartAPI client, no
instrument master, no `bias`/`poc`/`signals`/`simulate`, no tick table in `src/`. The prep
commit is confined to the two rulings and the two REVIEW_0 findings it names. The card's
deliverables are all present, including the E2 exclusion helper. Scope discipline is clean.

This review added exactly one file — `tests/test_review1_probes.py` (36 tests) — and modified
no file under review.
