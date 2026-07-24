# REVIEW_0 — chunk 0 · Repo scaffold & config

**Reviewer:** fresh code-review session (`personas/code_reviewer.md`; plan.md chunk 0 is review type **C**).
**Date:** 2026-07-24 · **Commit under review:** `563aaa0` (6 commits, `f5bf24b..563aaa0`)
**Builder entry reviewed:** PROGRESS.md `[2026-07-24 18:19] chunk 0 · build · done`

## VERDICT: **PASS**

All tests green from a clean state, the frozen fixtures are provably intact, no secret ever
entered history, and every Class-B decision is recorded and defensible. Seven findings are
recorded below; all are LOW or INFO and none meets a FAIL trigger. I would let this scaffold
carry a live market morning.

---

## 1. Architect's directed checks

| # | Check | Result |
|---|---|---|
| 1 | `poc/data/` contains EXACTLY 28 CSVs incl. `TCS_2026-07-20_1min.csv` | **PASS** — 28 files on disk, 28 tracked by git, all 28 present. The operator's pasted tree showing 27 was a paste artifact, not a missing fixture. |
| 2 | Working tree clean vs HEAD; `.gitattributes` actually applies | **PASS** — `git status` clean; `git check-attr text -- poc/data/TCS_2026-07-14_1min.csv` → `text: unset`; same for `TCS_2026-07-20` and `tests/fixtures/`. All 28 fixtures hash identically to their HEAD blobs. CRLF preserved (376 CRLF pairs in the TCS file) despite `core.autocrlf=true`. |
| 3 | `poc/data/...` NOT ignored; `/data/`, `/cache/`, `/logs/` anchoring | **PASS** — `git check-ignore -v poc/data/TCS_2026-07-14_1min.csv` → no match, exit 1 (not ignored). `data/x.csv`→`.gitignore:7:/data/`, `cache/y.json`→`:8:/cache/`, `logs/z.log`→`:9:/logs/`, `.env`→`:2:.env`, `poc/cache/a.json`→`:10:poc/cache/`. |
| 4 | `.env` never in history; no credential strings in tracked files | **PASS** — `git log --all --diff-filter=A -- .env` empty; no `env`-named path was ever added in any commit; 56 tracked files scanned against a credential-pattern set — every hit is a variable NAME or prose, never a value. `.env` contents were never read, printed or logged by this review. |
| 5 | 6 commit messages + authorship comply with CLAUDE.md | **PASS** — all 6 authored/committed by `chinmoy-paul <chinmoypaul8897@gmail.com>`; no "Generated with", no `Co-Authored-By`, no AI attribution anywhere in any subject, body or trailer. Each is a logical unit with imperative subject, `chunk0:` prefix, `(unreviewed)` suffix, and a WHAT/WHY body citing the spec. |
| 6 | Full suite rerun fresh; 60 passing from clean state | **PASS** — `.pytest_cache` and all `__pycache__` removed, then `python -m pytest -q` → **60 passed / 0 failed** in 0.42s. After this review's added tests: **91 passed / 0 failed**. |
| 7 | Judge B1–B12 | **Done** — §3 below. All 12 approved; B7 approved with a caveat recorded as Finding 3. |

## 2. Fixture integrity — the central question, verified two independent ways

The builder's evidence for a byte-faithful move is an aggregate SHA-256 in the PROGRESS
entry. That claim is **not independently reproducible** (Finding 1), and git holds no
pre-move baseline: the CSVs entered history only as *additions* in `1bd2fb7` — they were
never committed at their old root `data/` path, so no rename diff can prove byte-equality.
I therefore verified integrity two stronger ways.

**(a) Working tree ≡ git object store.** For all 28 CSVs, `git hash-object <path>` equals
`git rev-parse HEAD:<path>` — 0 mismatches. Combined with `-text`, the bytes a fresh clone
receives are exactly the bytes on this disk.

**(b) The fixtures still compute their own calibrated answers.** I reimplemented the
CONTEXT §3.3 / §5 row math and prorata spreading independently and recomputed the POC for
all 25 symbol-days directly from the frozen CSVs:

> **25/25 exact matches** against the `poc_prorata` column of the frozen
> `volume_poc_summary.csv` — zero difference at full float precision, including all five
> CONTEXT §8 F7 anchors (TCS 07-14 → 2205.25 · RELIANCE 07-16 → 1303.60 ·
> HDFCBANK 07-14 → 815.275 · DIXON 07-16 → 14263.50 · MANAPPURAM 07-15 → 329.75).

This is decisive: the CSVs in `poc/data/` are the exact data the 22-Jul-2026 calibration was
measured on. An edited, re-downloaded or line-ending-normalized file could not reproduce
those values. It also confirms F7 assertion (a) is satisfiable as written, which de-risks
chunk 6.

**F10 cross-check (rides along):** all 25 `gap_pct` values in the frozen summary lie in
`[+0.025%, +3.581%]` — inside CONTEXT §8 F10's stated `[+0.02%, +3.6%]` and comfortably
inside the §4.5 acceptance band `[−0.1%, +5.0%]`. `quality_report.csv` shows 375 candles and
zero defects on all 25 days.

**A tick-size trap worth recording.** My first pass hardcoded ₹0.05 and reproduced only
15/25 — every DIXON day failed. The real per-symbol ticks (from the cached instrument
master) are **TCS ₹0.10 · RELIANCE ₹0.10 · DIXON ₹1.00 · HDFCBANK ₹0.05 · MANAPPURAM ₹0.05**.
CONTEXT §3.3's "NEVER hardcode 0.05" is not a style rule — hardcoding it silently corrupts
the POC on 10 of the 25 calibration days while leaving the code looking correct. Those tick
values exist nowhere in the repo (Finding 6 → **Q-2**).

## 3. Class-B decisions B1–B12 — explicit judgment

| # | Judgment | One-line reason |
|---|---|---|
| B1 | **APPROVE** | Verified all 10 pins equal the installed versions exactly (smartapi-python 1.5.5 … pytest 9.1.1); one operator laptop makes exact pinning strictly better than ranges. |
| B2 | **APPROVE** | `pythonpath=["src"]` verified: a bare clone runs 91/91 green with no install step, and nothing was pip-installed to make it pass. |
| B3 | **APPROVE** | `version = {attr = "acumen.__version__"}` gives one bump point; `test_package_imports_and_reports_a_version` guards it. |
| B4 | **APPROVE** | Deferring `capital` and the ₹100 cost to the chunk that consumes them avoids config surface that drifts unread; chunk 8 must add them to config, not hardcode them. |
| B5 | **APPROVE** | Unknown/missing keys as hard `ConfigError` is CLAUDE.md rule 1 made executable; both directions are tested. |
| B6 | **APPROVE** | Confirmed independently: no credential value in any tracked file, and `env_value()`'s message names only the variable. |
| B7 | **APPROVE (caveat)** | The cp1252 rationale is real and the ASCII rule is right, but the enforcing test walks only `src/` and `tests/` — `config.yaml` is unguarded despite being named in the decision. See Finding 3. |
| B8 | **APPROVE** | The highest-value decision in the chunk. Verified by `git check-ignore`: unanchored `data/` would have silently dropped the F7/F10 fixtures from the repo. |
| B9 | **APPROVE** | `/logs/` and `.pytest_cache/` are generated artifacts that CLAUDE.md's git rules forbid committing; the PoC had indeed left two 0-byte `logs/*/app.log` files. |
| B10 | **APPROVE** | CONTEXT §6 calls `poc/` archived; preserving the scripts as-run kept the calibration auditable — this review could only attribute POC differences *because* `poc3` was unmodified. Caveat as Finding 5. |
| B11 | **APPROVE** | Verified `text: unset` on the fixtures and CRLF intact; without it every clone on an autocrlf machine would receive different bytes than F7/F10 were calibrated on. |
| B12 | **APPROVE** | Deleting nothing is correct for a scaffold chunk; the leftovers (`cache/scrip_master.json`, `logs/`, `__pycache__/`) are all gitignored and never reached history. |

## 4. Findings

**Finding 1 — LOW — fixture-integrity evidence is not reproducible.**
PROGRESS.md offers `aggregate digest of the 28 CSVs: f7e06fad…ac004100` as proof the move
preserved bytes, but records neither the aggregation recipe nor the per-file digests. Six
plausible schemes (concatenated hex digests, concatenated file bytes, `hash  name` lines,
`name hash` lines, raw digest bytes, 25-file-only) all produce different values, so no later
session can check the claim. *Impact:* the strongest stated evidence for the frozen fixtures
is unverifiable. *Mitigation applied:* integrity re-established two stronger ways (§2), and
the per-file digests are now committed as a test (Finding 2). *No code change required.*

**Finding 2 — LOW — the frozen-fixture rule had no tripwire.** (fixed by this review)
`test_frozen_poc_fixtures_are_present` asserted only that files *exist*. Any later session
could have rewritten, re-downloaded or normalized a fixture and the suite would still be
green, silently invalidating F7/F10. Added `tests/test_fixture_integrity.py`: per-file
SHA-256 for all 28 CSVs, exact-set membership (28, no additions/removals), 375-candle
session length, and a CRLF guard. Mutation-tested against five corruption modes — 1-byte
edit, CRLF→LF normalization, deletion, stray file, truncation — **all five caught**; the
control on clean copies passes. Repo fixtures were never mutated (temp copies only).

**Finding 3 — LOW — B7's ASCII guarantee is narrower than stated.**
B7 says runtime files "(`*.py`, `config.yaml`) are ASCII-only, enforced by a test", but
`test_project_python_sources_are_ascii_only` walks only `src/**/*.py` and `tests/**/*.py`.
`config.yaml` happens to be ASCII today with nothing holding it there, and
[pyproject.toml:7](pyproject.toml#L7), [:20](pyproject.toml#L20), [:24](pyproject.toml#L24)
contain `—` and `§`. Harmless today (both are read with explicit UTF-8, and neither appears
in a traceback source line), but the recorded decision overstates the enforcement.
*Suggested (not required):* extend the walk to `config.yaml`, or narrow B7's wording.

**Finding 4 — LOW — config tests load the operator's real `.env`.**
Six tests call `load_config()` letting `include_env` default to `True`, which loads the real
repo-root `.env` into `os.environ` for the rest of the pytest process — e.g.
[tests/test_config.py:44](tests/test_config.py#L44),
[:51](tests/test_config.py#L51), [:73](tests/test_config.py#L73). No leak occurs today
(nothing prints the environment and `--showlocals` is not enabled), and the tests that
matter for hermeticity already pass `include_env=False`. Still, a test suite has no reason
to touch live credentials. *Suggested:* pass `include_env=False` in those six.

**Finding 5 — INFO (forward-looking) — archived PoC login stringifies the API response.**
[poc/common.py:46](poc/common.py#L46) does `raise SystemExit(f"LOGIN FAILED: {resp}")`, and
[:93](poc/common.py#L93) catches bare `Exception` and prints `str(e)`. On a *failed* login
the response carries no credentials, so this is not a leak, and B10 archives the file
deliberately as-run — correct for chunk 0. Recorded so **chunk 5A does not carry the pattern
into the live client**: the real client must never stringify an auth response or a request
object into a message (`personas/code_reviewer.md` checklist 4).

**Finding 6 — INFO (forward-looking) → raised as Q-2 — F7's inputs are incomplete.**
CONTEXT §8 F7 calls the `poc/data` CSVs "the authoritative input", but reproducing the POC
also requires the per-symbol `tickSize`, which exists nowhere in the repo — the only local
copy is the gitignored 35 MB `cache/scrip_master.json`. The measured values (TCS ₹0.10,
RELIANCE ₹0.10, DIXON ₹1.00, HDFCBANK ₹0.05, MANAPPURAM ₹0.05) are recorded in QUESTIONS.md
Q-2 so the information survives cache deletion, and because the live instrument master is a
daily dump whose values may change, which would make F7 network-dependent. Not a chunk-0
defect — chunk 0 was told to move the CSVs and did.

**Finding 7 — INFO (forward-looking) — frozen CSVs carry tz-aware timestamps.**
Stamps are `2026-07-14 09:15:00+05:30`, while CONTEXT §7-E8 mandates naive-IST storage.
Chunk 5A/6 readers must normalize on ingest rather than assume naive. Noted only; the frozen
bytes are correct and must not be rewritten.

## 5. Checklist coverage (`personas/code_reviewer.md`)

1. **Tests** — 91/91 green; error paths well covered (non-positive/non-numeric risk, bad
   row_size, unknown/missing key, malformed YAML, non-mapping, bad paths, missing file);
   asserts are exact, not approximate; no test deleted, skipped or loosened; fixtures frozen
   and now digest-guarded. The one real hole (content integrity) is Finding 2, fixed.
2. **Failure behavior** — no network code in this chunk. `load_env` returns `None` rather
   than raising on a bare clone; no bare `except:` in `src/`; the only broad catch is
   `yaml.YAMLError`, correctly re-raised with `from exc`.
3. **Idempotency** — no ingestion in this chunk; the loader is a pure read.
4. **Secrets** — verified clean four ways: never in history, never in a tracked file, never
   on `Config`, never in an exception message. `.env` contents were not read by this review.
5. **Time & precision** — no clock reads, no price math, no `datetime.now()` anywhere in
   `src/`. Finding 7 records a tz note for later chunks.
6. **Structure** — no engine modules exist yet; `config.py` does I/O and says so explicitly
   in its docstring, keeping the boundary honest. No hardcoded tick, symbol, path or date in
   `src/` — `row_size` correctly comes from config (CONTEXT §3.3 / OPEN-2), and §2 shows
   exactly why that matters.
7. **Performance sanity** — n/a; loader is trivial, suite runs in 0.55s.
8. **Git & docs** — 6 clean logical commits, correct prefixes/suffixes, no AI attribution;
   PROGRESS entry complete against the plan §6 template with an honest
   `state-for-next-session`; STATUS.md updated; Q-1 correctly raised rather than guessed.
9. **Dependency hygiene** — all deps pinned in `pyproject.toml` and matching the installed
   environment; no unrecorded package. Root `requirements.txt` remains an unpinned second
   list (7 entries, missing pyarrow/PyYAML/pytest) — a real drift risk, already the subject
   of Q-1, which the architect has now ruled (→ `poc/`, executed in chunk 1).

## 6. Scope

The diff `f5bf24b..563aaa0` is entirely chunk-0 scaffold — no trading logic, no engine
module, no network code, nothing belonging to a later chunk. Scope discipline is clean.
This review added one file (`tests/test_fixture_integrity.py`) and modified no code under
review, per the review session's mandate.
