# PROGRESS.md — session log

**Newest entry on TOP.** Every session appends one entry using the exact template from
plan.md §6 (reproduced below). An entry is the only place a Class-B implementation decision
is recorded — a deviation recorded nowhere is a defect, even if the code is right (plan.md §5).

<!-- TEMPLATE — copy exactly (plan.md §6)

## [YYYY-MM-DD HH:MM] chunk <N> · <build|review|fix> · <done|blocked|handed-off>
scope: <one line — what this session did>
files: <created/changed paths>
tests: <pass count / fail count; fixtures touched>
decisions: <Class-B items with 1-line rationale; "none">
questions: <QUESTIONS.md items raised; "none">
gate: <n/a | pending | closed — evidence path>
status-ledger: <the STATUS.md line this session set>
state-for-next-session: <exact current situation + the single next action>

-->

---

## [2026-07-24 19:09] chunk 0 · review · done
scope: fresh code-review of chunk 0 (code_reviewer persona) — reran the suite, verified the frozen fixtures two independent ways, judged B1-B12, wrote docs/reviews/REVIEW_0.md. VERDICT PASS.
files: created docs/reviews/REVIEW_0.md, tests/test_fixture_integrity.py; edited QUESTIONS.md (Q-1 marked resolved per architect ruling; Q-2 raised), STATUS.md, PROGRESS.md. NO file under review was modified; no file was moved.
tests: 91 passed / 0 failed (60 builder + 31 added by this review). Builder's 60 reran green from a clean state (.pytest_cache and all __pycache__ deleted first). Fixtures touched: NONE — all 28 poc/data CSVs hash identically to their git HEAD blobs, and the new digest test was mutation-tested against temp COPIES only.
decisions:
  - Reviewer-added test file kept (persona process step 4): tests/test_fixture_integrity.py pins SHA-256 per fixture, the exact 28-file set, 375-candle length and CRLF preservation. Rationale: the build asserted only that fixtures EXIST, so CLAUDE.md rule 3 had no tripwire — a later session could silently regenerate one and stay green.
  - Fixture integrity was established by recomputation, not by trusting the builder's digest: an independent reimplementation of the CONTEXT 3.3 row math reproduces all 25 poc_prorata values in volume_poc_summary.csv exactly, including all five CONTEXT 8 F7 anchors. Evidence, not assertion.
  - The verification scripts were written to the session scratchpad, not the repo — chunk 6 owns the POC engine and a review may not pre-build it.
questions: Q-1 marked "RESOLVED — execution scheduled chunk 1" with the architect's ruling (option (a): three documents to docs/, requirements.txt to poc/) recorded in full; NO file moved by this session. Q-2 RAISED (class A, non-blocking, first needed at chunk 6): CONTEXT 8 F7 calls the poc/data CSVs "the authoritative input", but recomputing the POC also needs the per-symbol tickSize, which lives nowhere in the repo (only the gitignored 35 MB cache/scrip_master.json). Measured values recorded in Q-2 so they survive cache deletion: TCS 0.10, RELIANCE 0.10, HDFCBANK 0.05, DIXON 1.00, MANAPPURAM 0.05.
gate: n/a
status-ledger: chunk 0: reviewed-PASS
state-for-next-session: Chunk 0 is reviewed-PASS at tag chunk0-pass; python -m pytest is green (91/0) from a bare clone. Seven findings are in docs/reviews/REVIEW_0.md — all LOW or INFO, none blocking, none requiring a fix session: F1 (builder's aggregate digest is not reproducible; superseded by the new per-file digest test), F2 (fixed by this review), F3 (B7's ASCII claim is broader than the test that enforces it), F4 (six config tests load the real .env; suggest include_env=False), F5/F6/F7 are forward-looking notes for chunks 5A and 6. NEXT ACTION: build chunk 1 (universe & calendar) — and, per the architect's Q-1 ruling, that same session moves RESULTS.md, acumen_poc.md and TradingView_POC_Calibration_Guide.docx to docs/ and requirements.txt to poc/, then marks Q-1 closed.

---

## [2026-07-24 18:19] chunk 0 · build · done
scope: turned the PoC folder into the project repo — CONTEXT §6 layout, pinned pyproject, config loader with risk_per_trade required-empty, ledgers, git history.
files: created .gitattributes, pyproject.toml, config.yaml, src/acumen/__init__.py, src/acumen/config.py, tests/test_smoke.py, tests/test_config.py, tests/fixtures/.gitkeep, docs/reviews/.gitkeep, PROGRESS.md, QUESTIONS.md, STATUS.md; rewrote .gitignore; moved common.py + poc1..poc5_*.py → poc/ and data/*.csv (28) → poc/data/; untouched: CLAUDE.md, CONTEXT.md, plan.md, personas/*, RESULTS.md, acumen_poc.md, TradingView_POC_Calibration_Guide.docx, requirements.txt, .env, cache/.
tests: 60 passed / 0 failed (python -m pytest). Fixtures touched: NONE — the 28 poc/data CSVs were moved, not rewritten; SHA-256 of all 34 moved files taken before and after the move, 34/34 identical (aggregate digest of the 28 CSVs: f7e06fad99b8d8ac6005a5f4b6ba9df61641b4973a021e9f1d12bf92ac004100).
decisions:
  - B1 Dependencies pinned exactly (`==`) to the versions verified working here (smartapi-python 1.5.5, pyotp 2.10.0, python-dotenv 1.2.2, requests 2.32.3, websocket-client 1.9.0, logzero 1.7.0, pandas 3.0.3, pyarrow 25.0.0, PyYAML 6.0.3, pytest 9.1.1) — one operator laptop, so reproducibility beats range flexibility.
  - B2 pytest resolves the src layout via `[tool.pytest.ini_options] pythonpath = ["src"]` rather than an editable install — a bare clone runs green with no install step. The package was NOT pip-installed in this session.
  - B3 Project version is single-sourced from `acumen.__version__` (setuptools dynamic metadata) — one place to bump.
  - B4 config.yaml carries only the three keys the card names (risk_per_trade, row_size, paths); capital and the ₹100 cost (CONTEXT §3.5) are left to the chunk that consumes them — no unused config surface to drift.
  - B5 Unknown or missing top-level config keys are a hard ConfigError — a typo must fail loudly, never fall back to a default (CLAUDE.md rule 1).
  - B6 Secrets never enter the Config object: `.env` values are fetched on demand by `env_value()`, and its error message names the VARIABLE only, never a value (CLAUDE.md rule 4).
  - B7 Runtime files (`*.py`, `config.yaml`) are ASCII-only, enforced by a test: the operator's console encoding is cp1252, where printing a traceback whose source line carries `₹` or `§` raises UnicodeEncodeError and hides the real error. Spec symbols stay in the markdown documents; code cites "CONTEXT 3.5" in CLAUDE.md's own style.
  - B8 `.gitignore` anchors `/data/`, `/cache/`, `/logs/` with a leading slash — an unanchored `data/` would also ignore `poc/data/`, i.e. the frozen F7/F10 golden fixtures. A test asserts both the anchored form and the absence of the unanchored one.
  - B9 `.gitignore` adds `/logs/` and `.pytest_cache/` beyond the card's list — both are generated artifacts, which CLAUDE.md's git rules forbid committing (the PoC had left two 0-byte `logs/*/app.log` files).
  - B10 PoC scripts moved verbatim, not repaired: their `Path(__file__).parent/"data"` now resolves to `poc/data` (correct), `cache` to `poc/cache` (hence that ignore entry) and `.env` to `poc/.env` (absent — the archive would need `--env` plumbing to re-run). CONTEXT §6 calls poc/ "archived PoC scripts", so it is preserved as-run.
  - B11 Added `.gitattributes` marking `poc/data/**` and `tests/fixtures/**` as `-text`: this machine has `core.autocrlf=true` and the frozen CSVs are CRLF on disk, so without it git would store them line-ending-normalized and any clone would receive different bytes than the fixtures were calibrated on (CONTEXT §8 F7/F10).
  - B12 Nothing was deleted anywhere in this chunk: root `cache/scrip_master.json` (35 MB, gitignored), `logs/`, `__pycache__/` and the four un-specified root documents were left in place; the card scoped the move to PoC scripts + PoC data.
questions: Q-1 (class A, non-blocking) — CONTEXT §6's layout does not name RESULTS.md, acumen_poc.md, TradingView_POC_Calibration_Guide.docx or requirements.txt, so chunk 0 left them at the repo root instead of guessing; chunk 2 cites RESULTS.md, so its path needs an architect ruling before then.
gate: n/a
status-ledger: chunk 0: built
state-for-next-session: Repo is at the CONTEXT §6 layout on branch `main`, `python -m pytest` is green (60/0) from a bare clone, and the history ends at `chunk0: repo scaffold (unreviewed)`. Environment note: pytest 9.1.1, PyYAML 6.0.3 and pyarrow 25.0.0 were installed into the operator's global Python 3.12.2 this session; the other pinned deps were already present from the PoC. NEXT ACTION: a FRESH session reviews chunk 0 against personas/code_reviewer.md and writes docs/reviews/REVIEW_0.md — chunk 1 must not start until STATUS.md shows `chunk 0: reviewed-PASS`.
