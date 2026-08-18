# REVIEW_R1 — THE R1 FIX · SCOPED ADVERSARIAL RE-CHECK

**Code-reviewer persona** (`personas/code_reviewer.md`), fresh session, over `bd1be58..2073c29` —
two commits, linear, zero merges. The subject is the fix that closes REVIEW_15B finding **R1**:
three printable, operator-facing strings that named `python -m acumen.<x>`, a command that answers
`No module named 'acumen'` on this machine. Everything before `bd1be58` passed REVIEW_15B and is
not re-opened here.

**VERDICT: PASS.** Six findings, **all INFO, none blocking, and none of them a defect in the
fix.** No CONTEXT deviation, no test weakened, deleted or skipped, no fixture byte moved, no
secret, no published artefact changed, and **not one byte of either store moved across this
review** — content digest included, which this review re-derived rather than accepting.

The claim under review is unusually narrow and unusually easy to fake: *"only printed text
changed"*. So this review did not read the diff and agree with it. It **raised** each string in a
bare clone, **extracted** the command from what was raised, **ran** it with `PYTHONPATH` unset,
re-derived the flip on a clean pre-fix tree, broke the drift pin three separate ways to confirm it
bites, and proved the text-only claim at the level of the **AST and the rendered character
stream** rather than by inspection.

---

# PART 0 — STORE INTEGRITY, FIRST AND LAST

Read by this session's own `rev_r1_fingerprint.py`, written here from the frozen recipe in
`docs/evidence/housekeeping_13aug_store_fingerprint.py`, importing nothing from `src/acumen` and
nothing from either prior fingerprint script. Read-only by construction: `open(..., "rb")` only,
one reused 256 KB buffer filled with `readinto`, nothing created, written, renamed or removed.

```
open   files 22186  bytes 4109782853
       metadata dbea5660b7734f6a71edd5e99eac0159e53174ec431a1a7fb17c2bad5bf61423
       content  d97ba4191339be543df9ee8a67f3a8c17aed629e0cc21e4be1d989a86dc1e089
       newest 2026-08-12T23:19:20  nse/ca/nse_ca_2026-01-01_2026-12-31.json

close  files 22186  bytes 4109782853
       metadata dbea5660b7734f6a71edd5e99eac0159e53174ec431a1a7fb17c2bad5bf61423
       content  d97ba4191339be543df9ee8a67f3a8c17aed629e0cc21e4be1d989a86dc1e089
       newest 2026-08-12T23:19:20  nse/ca/nse_ca_2026-01-01_2026-12-31.json
```

**Every digit identical, and identical to REVIEW_15B PART 0, to REVIEW_15, to REVIEW_14B PART 6
and to the fix's own `r1_fix_store_bracket.md`.** `cache_root` sits inside `data_root`, so one
walk brackets both roots (Q-18 layer 1).

## 0.1 · This review closes B438's own disclosed gap

The fix session recorded **B438** honestly: its bracket computes the **metadata** half of the
recipe only, and it wrote down the limit that follows — *"a session that MUTATED a file with
identical bytes and a restored timestamp would not be caught by this half alone"*. That limit is
now closed from the outside: **this review computed the CONTENT half as well**, on the same disk,
with its own program, and got REVIEW_15B PART 0's published `d97ba419...` to the digit. The stores
are byte-identical, not merely metadata-identical. B438 is APPROVED and its gap is no longer open.

Between the two readings sat: the full suite in the operator's tree, two clones under the OS temp
directory, every probe in this review, the bare-clone transcript, three drift mutations and two
`--collect-only` censuses. **No mutating CLI was run against either root** — no `--allow-network`,
no `--refresh`, no `--backfill`. The only launcher executed with real arguments was
`scripts/fetch_instrument_master.py` **without** its network opt-in, against an empty scratch
directory, which printed *"Nothing was fetched and nothing was written."* and left that directory
empty (verified: a `find` over it returned the directory and nothing else).

---

# PART 1 — THE STRINGS WERE RUN, NOT READ

A bare clone of `2073c29` in the OS temp directory, outside the repository and outside both
stores, `PYTHONPATH` unset, no editable install anywhere on `sys.path`.

```
clone     : <OS-TEMP>/revr1_clone_5i05zq85
HEAD      : 2073c29  chunk15: PROGRESS entry, STATUS and the R1 fix's evidence
tree      : e1f41ee45a5568c9967ca105d0cd5e6d633094c8   == the source repo's 2073c29 tree
PYTHONPATH: [UNSET]
python    : Python 3.12.2

=== (a) CONTROL: is this a real operator shell? ===
python -c "import acumen"   ->  ModuleNotFoundError: No module named 'acumen'   exit=1
sys.path entries containing "acumen": []          <- no editable install, measured not assumed
```

## 1.1 · The commands were EXTRACTED from what the code RAISED

Not typed, not read out of the source. Each code path was driven in the clone and the argv pulled
out of the message it produced:

```
[site1] ls._require_day_master(day_master_filename(2026-08-18), cache_dir=Path("no-such-dir-review-r1"))
  raised: "...It is not at no-such-dir-review-r1\instrument_master\OpenAPIScripMaster_2026-08-18.json.
           Run the pre-open refresh (`python scripts/run_screener.py --mode live --day <today>
           --refresh --allow-network`), or fetch the dump directly
           (`python scripts/fetch_instrument_master.py --allow-network`)."

[site2] bt.named_master(Path("no-such-dir-review-r1"), "OpenAPIScripMaster_2026-08-18.json")
  raised: "...Run the pre-open fetch (`python scripts/fetch_instrument_master.py --allow-network`),
           or replay under the master the recording actually names."

[site3] bt.fence_ca_cache(cache_dir=<scratch>/store/nse, allow_network=True,
                          data_root=<scratch>/store, cache_root=<scratch>/store/cache)
  returned network=False and handed the caller:
          "...(the ingest path: `python scripts/ca_report.py --from <D> --to <D> --allow-network`)..."

argv extracted from those three messages:
  python scripts/run_screener.py --mode live --day <today> --refresh --allow-network
  python scripts/fetch_instrument_master.py --allow-network          (site 1, second remedy)
  python scripts/fetch_instrument_master.py --allow-network          (site 2)
  python scripts/ca_report.py --from <D> --to <D> --allow-network
```

Site 3 was driven against a scratch pair of roots so the fence fires without either real root
being named, let alone read.

## 1.2 · Those commands run in that shell; the dead forms still do not

```
=== (b) the NEW forms, REAL subprocesses, PYTHONPATH unset ===
-- scripts/run_screener.py --help          exit=0  "No module named": 0  Traceback: 0
   usage: acumen.run_screener [-h] [--mode {replay,live}] --day DAY ... [--allow-network] [--refresh] ...
-- scripts/fetch_instrument_master.py --cache-dir <SCRATCH>   (no --allow-network)
   cache dir    : <SCRATCH>/instrument_master
   already held : 0 dump(s)
   STOPPING (no --allow-network). Nothing was fetched and nothing was written.
   exit=1  "No module named": 0  Traceback: 0
-- scripts/ca_report.py --help             exit=0  "No module named": 0  Traceback: 0
   usage: acumen-ca-report [-h] [--from START] [--to END] [--allow-network] [--yahoo YAHOO]

=== (c) CONTROL: the three DEAD forms, SAME shell ===
python -m acumen.run_screener --help      -> exit=1 :: ... (ModuleNotFoundError: No module named 'acumen')
python -m acumen.instrument_master --help -> exit=1 :: ... (ModuleNotFoundError: No module named 'acumen')
python -m acumen.ca_report --help         -> exit=1 :: ... (ModuleNotFoundError: No module named 'acumen')
```

`exit=1` on the master fetch is `instrument_master.py:364`'s `return 0 if existing else 1` —
REVIEW_15B **R4**'s disclosed conditional on an empty cache, not a failure. Read at the source,
not taken from the fix's report.

**The two remedies whose real flags WRITE were not executed** (`run_screener --refresh
--allow-network` fetches and writes; the `ca_report` ingest writes into a directory inside the
stores). CLAUDE.md forbids a session either. They are proved by resolve-plus-parse, PART 2 — which
is decision **B437**, and it is the right call.

---

# PART 2 — THE FLAGS, AND THE ARGV THE OPERATOR ACTUALLY TYPES

Run in the bare clone, **one launcher per fresh process** so no launcher's `sys.path` bootstrap can
flatter the next. Each process asserts `acumen` is absent first, then executes the launcher file
(as a non-`__main__` module, so `main` is never called), then calls the launcher's own
`_load_main()`, then compares the object it returns with the module `-m` would have run:

```
[1] scripts/run_screener.py --mode live --day <today> --refresh --allow-network
    pre-state: import acumen -> No module named 'acumen'
    bootstrap OK; main is acumen.run_screener.main -> True
    parse_args([--mode live --day 2026-08-18 --refresh --allow-network]) ->
        mode='live' day='2026-08-18' refresh=True allow_network=True   (+ defaults)
[2] scripts/fetch_instrument_master.py --allow-network
    pre-state: import acumen -> No module named 'acumen'
    bootstrap OK; main is acumen.instrument_master.main -> True
    parse_args([--allow-network]) -> cache_dir=None allow_network=True
[3] scripts/ca_report.py --from <D> --to <D> --allow-network
    pre-state: import acumen -> No module named 'acumen'
    bootstrap OK; main is acumen.ca_report.main -> True
    parse_args([--from 2026-08-18 --to 2026-08-18 --allow-network]) ->
        start='2026-08-18' end='2026-08-18' allow_network=True
```

Every flag each string prints was resolved to the attribute its own parser sets (`--from`→`start`,
`--to`→`end`), and each was checked to exist rather than merely to parse.

**The argv is genuinely unchanged, and this is structural rather than coincidental.** Each
packaged module ends `if __name__ == "__main__": raise SystemExit(main())`; each launcher ends
`raise SystemExit(_load_main()())`, and `_load_main()` returns that same `main` — proved by object
identity above, in a shell where the only way to reach it is the launcher's own bootstrap. `main()`
takes `argv=None`, which argparse resolves to `sys.argv[1:]`; `sys.argv[0]` differs between the two
forms and nothing reads it. **The operator types the same flags and the same code parses them.**

---

# PART 3 — THE SWEEP, WIDER THAN THE FIX

R1 exists because C1's sweep stopped at one site. So this sweep was rebuilt from scratch over
**all of `src/`**, not the two changed files, with three independent lenses over every `.py` file:
`ast` for non-docstring string constants, `ast` for docstrings, `tokenize` for `COMMENT` tokens —
plus a raw byte count per file, so nothing can hide in a parse gap.

```
file                             raw  comment  docstring  PRINTABLE
src/acumen/backfill_daily.py       1        0          1          0
src/acumen/backtest.py             2        2          0          0
src/acumen/ca_report.py            2        0          2          0
src/acumen/dry_run_readiness.py    4        1          3          0
src/acumen/live_screener.py        2        1          1          0
src/acumen/report_9b.py            1        1          0          0
src/acumen/run_screener.py         2        0          2          0
src/acumen/trader_pack.py          1        1          0          0
                          TOTAL   15        6          9          0

raw 15 == classified 15  ->  PRINTABLE carriers of `-m acumen.` in ALL of src/: ZERO
```

**Every one of the 15 surviving occurrences is accounted for as a comment or a docstring** — the
provenance that records what the remedy used to say and why it changed. Not one is printable.

Two further lenses, both wider than R1 asked for:

* **No printable string anywhere in `src/` or `scripts/` names a `python -m` invocation at all**
  (zero hits for the literal `-m ` outside docstrings). This also forecloses runtime assembly: a
  message built as `"python -m " + module` would need a literal `"-m "` fragment, and none exists.
  f-string literal parts were walked separately for the same reason.
* **Every `scripts/*.py` named in a printable string in `src/` exists on disk** — all seven:
  `ca_report.py`, `fetch_instrument_master.py` (twice), `backfill_daily.py`, `run_screener.py`,
  `run_backtest.py`, `universe_backfill.py`. A printed remedy naming a script that is not there
  would be the same defect wearing different clothes; there is none.

**The operator-facing documents are clean too.** The only `-m acumen.` outside reviews, ledgers and
frozen evidence transcripts is `docs/morning_runbook.md:94`, which is *disclosure* and not
instruction: *"The three ways to launch are equivalent — `python scripts/run_screener.py` (works
from a bare clone, and is the one above), `python -m acumen.run_screener` and `acumen-screener`
(both need `pip install -e .`)."* That is correct, and correctly worded.

---

# PART 4 — THE FLIP, RE-DERIVED

A second clone at `bd1be58`, pristine, with **only** the two test files transplanted from
`2073c29`. Nine tests are at stake: the eight new probes plus REVIEW_15B's MEASURED pin, flipped on
its own written instruction.

```
9 failed in 9.86s     <- at bd1be58, pre-fix source, this fix's tests
exception classes across the nine failures:  9 x AssertionError
AttributeError / ImportError / ModuleNotFound / collection errors:  0
```

**Every one fails on its own subject.** The ones that could plausibly have died on a missing
constant do not:

| probe | what fires first at `bd1be58` |
|---|---|
| live-morning refusal | `assert "-m acumen." not in message` — the dead form itself |
| live-morning remedies | `the refusal prints a command whose target is not a file in this repo: ['python','-m','acumen.run_screener',...]` |
| `named_master` refusal | `assert "-m acumen." not in message` |
| `named_master` remedy | same target-is-not-a-file assertion, on `['python','-m','acumen.instrument_master','--allow-network']` |
| CA fence | `assert "-m acumen." not in message` |
| CA ingest path | same target-is-not-a-file assertion, on the `ca_report` argv |
| two-module AST sweep | `acumen.live_screener can still print the dead form: [...]` |
| the drift pin | `backtest names the launcher its two operator-facing strings print` — a `hasattr` **assertion**, deliberately written so it reads as its own subject rather than raising `AttributeError` |
| the flipped pin | `a printable string in src/ names the dead form again: {'backtest.py': [1612, 1586], 'live_screener.py': [2372]}` |

Those three line numbers are R1's three sites, measured on the pre-fix tree, and they match
REVIEW_15B's citation. Green at the other end, in the `2073c29` clone with `PYTHONPATH` unset:

```
9 passed in 20.05s
```

**The flipped pin is strictly stronger, not merely different.** It replaced
`assert "dry_run_readiness.py" not in carriers` **and** `assert set(carriers) == {"live_screener.py",
"backtest.py"}` with `assert carriers == {}`, which subsumes both, and it keeps its tail asserting
all three launcher files exist. Nothing was dropped. It sweeps all of `src/acumen`, which is the
same span PART 3 swept independently.

**Census.** `--collect-only` at both ends: **2,613 → 2,621, delta +8.** Exactly one node ID
disappears — `test_R15B_C1_the_SAME_dead_form_elsewhere_in_src_is_MEASURED_not_assumed_absent` —
and it reappears under its flipped name. No test lost, no `skip` and no `xfail` added anywhere in
the span.

---

# PART 5 — THE DRIFT PIN, BROKEN THREE WAYS

**B436**'s claim is that a later rename cannot silently desynchronise the four places that name
these launchers. That was not accepted; it was attacked, in the `2073c29` clone, restoring after
each:

| mutation, in ONE place | result |
|---|---|
| `dry_run_readiness.MASTER_LAUNCHER` → `scripts/fetch_master_v2.py` | **4 failed** — `test_R1_the_master_launcher_is_ONE_name_across_the_gate_and_the_two_fixed_sites`, plus C1's own two probes and the R15B gate pin |
| `backtest.MASTER_LAUNCHER` → `scripts/fetch_master_v2.py` | **5 failed** — the pin, both live-morning probes and both `named_master` probes |
| `live_screener.SCREENER_LAUNCHER` → `scripts/run_screener_v2.py` | **3 failed** — the pin and both live-morning probes |

The pin fires in **both** directions, and the `(REPO / launcher).is_file()` half means renaming the
launcher *file* without the constant is caught too. Clone left clean (`git status --porcelain`
empty) after each. **B436 APPROVED.**

---

# PART 6 — SCOPE: THE ONLY BEHAVIOUR CHANGE IS PRINTED TEXT

Not asserted from the diff. Proved twice, at two different levels.

## 6.1 · At the AST

Both changed modules parsed at `bd1be58` and at `2073c29` and compared top-level name by top-level
name:

```
src/acumen/backtest.py
  ADDED   : MASTER_LAUNCHER, CA_REPORT_LAUNCHER          (two str constants)
  REMOVED : (none)
  CHANGED : CA_REFRESH_FENCED   -- str literal -> f-string reading CA_REPORT_LAUNCHER
            named_master        -- ONLY the raise message, str -> f-string reading MASTER_LAUNCHER

src/acumen/live_screener.py
  ADDED   : SCREENER_LAUNCHER
  REMOVED : (none)
  CHANGED : __all__             -- gains "SCREENER_LAUNCHER"
            _require_day_master -- docstring provenance + the same two f-string substitutions
```

**No other function, class or constant in either module differs by a single AST node.** Six of the
eight engine/core blobs are the *same git object* at both ends — `bias.py`, `poc.py`, `signals.py`,
`simulate.py`, `bias_engine.py`, `signal_engine.py` — as is `parity.py`. `backtest.py` is the only
one that moved, and the above is the whole of how.

## 6.2 · At the rendered character stream

Each of the three messages was raised by the **pre-fix** code and by the **post-fix** code, from
identical inputs, and compared:

```
site1 (the live morning's 09:00 refusal): bd1be58's message with ONLY the command token
      swapped == 2073c29's message  ->  True     (579 -> 587 chars)
site2 (named_master)                                                ->  True   (440 -> 447)
site3 (CA_REFRESH_FENCED)                                           ->  True   (530 -> 531)
```

Substituting only `-m acumen.run_screener`→`scripts/run_screener.py`,
`-m acumen.instrument_master`→`scripts/fetch_instrument_master.py`,
`-m acumen.ca_report`→`scripts/ca_report.py`. **Not one other character moved** — no wording
"improvement" rode along, no CONTEXT citation shifted, no refusal softened.

## 6.3 · Nothing downstream is coupled to the old text

`_require_day_master` raises straight to its one caller (`live_screener.py:2263`), which does not
catch or reformat it. `named_master` likewise (`backtest.py:1865`, `live_refresh.py:1027`).
`CA_REFRESH_FENCED` is returned by `fence_ca_cache` for the caller to print and is embedded in no
report generator. The runbook's line about it (`docs/morning_runbook.md:133`) quotes only the
prefix *"corporate-action refresh FENCED"*, which did not change. The one committed artefact still
showing the dead form, `docs/evidence/chunk15_readiness_gate.out.txt`, is a **frozen pre-C1
transcript** that nothing regenerates — correctly left untouched.

Import direction was checked for the same reason: `live_screener.py:69` already did `from . import
backtest as bt`, so reading `bt.MASTER_LAUNCHER` adds no import and cannot cycle. All three modules
import standalone in the bare clone.

---

# PART 7 — THE STANDING SWEEP

| check | result |
|---|---|
| full suite, operator's tree, `2073c29` | **2,621 passed / 0 failed / 0 skipped** in 1148.14s — exactly the fix session's claim and exactly this review's `--collect-only` census. 4 warnings, all `DeprecationWarning` from the vendor `SmartApi` SDK's `ssl.OP_NO_TLSv1*`, pre-existing and untouched by this span |
| the 9 probes, bare clone, `PYTHONPATH` unset | 9 passed |
| engine blobs (`bias`,`poc`,`signals`,`simulate`,`bias_engine`,`signal_engine`,`parity`) | **same git objects** at `bd1be58` and `2073c29` |
| `backtest.py` | changed; AST- and character-proved text-only (PART 6) |
| published artefacts — `chunk9b_backtest_report.md`, `points_by_symbol.md`, `trader_pack.md`, `trader_pack.json`, `chunk14_parity_report.md`, `chunk14_parity_sample.json` | **all six byte-identical** |
| fixtures `tests/fixtures/`, `poc/data/` | 0 files changed in the span; working tree clean against git |
| `CONTEXT.md`, `plan.md`, `CLAUDE.md`, `pyproject.toml`, `config.yaml`, `DESIGN.md` | **untouched**, same blobs |
| `(unreviewed)` suffix | `a1764a4` touches 4 `src/`+`tests/` files and carries it; `2073c29` touches **zero** `src/` or `tests/` files (ledgers + evidence only), so the rule does not apply |
| AI attribution in commit messages, authors, committers, trailers | **none** |
| secrets | no credential-shaped string in the diff; `.env` not tracked, `.gitignore:2` carries it; nothing in the span reads, prints or names an `.env` value |
| open QUESTIONS | Q-11, Q-19, Q-31 — the only three open; none touches a printed string, a launcher or either changed module. The fix session correctly raised none: R1's remedy is named by the finding itself and every flag was verified against a real parser rather than assumed |
| PROGRESS entry | complete against plan.md §6 — all nine fields present, `state-for-next-session` honest and specific |
| STATUS line | `reviewed-PASS (cleanup re-checked), then R1 CLOSED (unreviewed) -- a SCOPED re-check of the R1 fix is owed` — accurate at the time it was written; superseded by this review |
| tags | none created or moved by the fix session, as its commit message states |
| `main` vs `origin/main` | identical at `2073c29` when this review opened |

**Class-B decisions: B436, B437, B438 — all three APPROVED**, each on evidence rather than on the
entry's own say-so (PART 5, PART 2, PART 0.1 respectively).

---

# PART 8 — FINDINGS

## F1 · INFO — an incidental host path in a committed transcript names a tool product

`docs/evidence/r1_fix_bare_clone.md:48` records the scratch cache directory the master fetch
printed, and that path runs through a temp directory named after the tool the session ran under.
CLAUDE.md's rule is *"no AI attribution anywhere"*; this is a machine path inside a pasted
transcript rather than attribution, it carries no claim of authorship, and it is **precedented** —
`docs/evidence/chunk15_flip.before.txt:1` has carried the identical fragment since `b762d74`
(15-Aug-2026), and both REVIEW_15 and REVIEW_15B passed it. Raised so the architect can rule once
rather than have it re-litigated: either scrub both to a placeholder, or state that incidental
machine paths in evidence transcripts fall outside the attribution rule. **Non-blocking; this
review's own transcript above is redacted to `<SCRATCH>` so it adds no third instance.**

## F2 · INFO — the master launcher's literal now exists twice, and only a test keeps them equal

`dry_run_readiness.MASTER_LAUNCHER` (C1's, reviewed-PASS) and `backtest.MASTER_LAUNCHER` (R1's)
both hold the literal `"scripts/fetch_instrument_master.py"`. The obvious de-duplication is
**forbidden by the dependency direction**: `dry_run_readiness.py:46` does `from . import backtest
as bt`, so `backtest` cannot read the gate's constant. Leaving C1's reviewed file untouched was the
right scoping call. What actually prevents drift is therefore
`test_R1_the_master_launcher_is_ONE_name_across_the_gate_and_the_two_fixed_sites` — and PART 5
proves it bites in both directions. Recorded because that makes the probe load-bearing: **if it is
ever deleted, two literals go silently out of step.** No action owed.

## F3 · INFO — the printed remedy is repository-root-relative and the string does not say so

`python scripts/run_screener.py ...` needs `cwd` = the repository root. The refusal does not
restate that. Not a defect of this fix, on three counts: it is character-for-character the shape
REVIEW_15's **C1** already passed (`dry_run_readiness.py:221`); all seven operator commands in
`docs/morning_runbook.md` use it; and the runbook states it once, at line 57 — *"Every command
below is run from the repository root."* And it is a strict improvement regardless of `cwd`,
because on this machine the `-m` form works from **no** directory: there is no editable install at
all (`sys.path` carries nothing acumen-ish, measured in both the repo and the clone). Recorded only
so the assumption is written where a later session meets it.

## F4 · INFO — the bare-clone evidence script clones the current HEAD rather than a pinned commit

`docs/evidence/r1_fix_bare_clone.sh:24` runs `git clone "$(git rev-parse --show-toplevel)"` with no
checkout of a named commit, so re-running it on a later HEAD reproduces a different tree. It prints
its own HEAD (`a1764a4` in the committed transcript), so the transcript is self-labelling and no
claim in it is mis-stated. Read line by line here and confirmed honest: it fetches nothing, writes
nothing, and its `--help`-only treatment of the two writing commands matches what it says it does.
A one-line `git checkout <sha>` would make it reproducible for ever. **Cosmetic.**

## F5 · INFO — the `src/`-wide pin has no non-vacuity guard

`test_FLIPPED_R15B_R1_the_dead_form_is_GONE_from_every_printable_string_in_src` asserts
`carriers == {}` over every file under `src/acumen`, and `carriers` is built from the file's own
`_printable()` AST walk. **If that helper were ever broken into returning nothing, the pin would
pass vacuously** — a green suite certifying a property it no longer measures, which is the shape
of defect this repo has now met five times. Its narrower sibling does guard against exactly this
(`tests/test_review15b_fix.py:301`, `assert printable, "the AST walk found no strings in ..."`),
but only for the two modules it sweeps, not for the package.

Three things keep it from mattering today, which is why it is INFO and not LOW: the sibling guard
covers the two modules R1 actually touched; the pin was proved **RED on `bd1be58` with the real
carriers named** (PART 4), so the helper demonstrably finds strings; and this review re-measured
the same property from outside the suite with three independent lenses plus a raw-byte accounting
that reconciles 15 of 15 occurrences (PART 3). *Remedy, if the architect wants it: one line —
`assert any(_printable(...) for ...)`, or a per-file `assert printable`.*

## F6 · INFO — B438's disclosed limit is closed by this review, not by the fix

Recorded as a positive so the record is unambiguous: the fix's own bracket was metadata-only and
said so; this review re-derived the **content** digest with an independently written program and
got `d97ba419...`, matching REVIEW_15B PART 0. The gap B438 named is measured shut. See PART 0.1.

---

# VERDICT

**PASS.**

R1's defect was that a remedy nobody had ever executed was printed to an operator at the worst
possible moment. The fix does not repeat that mistake: every command it prints was extracted from
the string that prints it and run in a shell where `import acumen` fails — by the fix session, and
again, independently, here. The two commands that could not be run were proved in the only two
halves that are provable without writing to a store: the launcher resolves on a bare clone, and it
forwards to the identical `main` object, so the argv is unchanged. That is decision **B437**, and
it is correct.

Beyond the fix's own claim: the dead form is gone from **every** printable string in `src/`, not
just the three R1 named; no printable string names a `python -m` invocation at all; every launcher
a printable string names exists on disk; the change is text-only at the AST **and** at the
character; and the drift pin that holds the four naming sites together fires in every direction it
was pushed.

I would let this run unattended on a live market morning.

**Findings: 6, all INFO, none blocking, none a defect in the fix.**
