# R1 FIX -- THE PROBE FLIP, RED THEN GREEN

Nine tests are at stake: the eight kept probes this session adds
(`tests/test_review15b_fix.py`, one per string plus its drive) and REVIEW_15B's own MEASURED pin,
FLIPPED on its own written instruction --
`test_R15B_C1_the_SAME_dead_form_elsewhere_in_src_is_MEASURED_not_assumed_absent`
-> `test_FLIPPED_R15B_R1_the_dead_form_is_GONE_from_every_printable_string_in_src`.

A probe that passes on the pre-fix source proves nothing about the fix, so all nine were run
against `bd1be58` -- the last commit before this session -- in a clone of the repository at that
commit, with only the two test files copied in. **Every one fails, and every one fails on its own
subject**: the assertion that fires first in each probe is the one about the dead form, not an
`AttributeError` for a constant the pre-fix tree does not have yet.

## RED -- the nine at `bd1be58` (pre-fix source, this session's tests)

```
E   AssertionError: a LIVE morning runs on THE DAY'S OWN instrument master (CONTEXT 4.7 / QUESTIONS.md Q-29), fetched pre-open. The tick sizes CONTEXT 3.3's profile row grid, hence the POC,  ...
E   AssertionError: the refusal prints a command whose target is not a file in this repo: [['python', '-m', 'acumen.run_screener', '--mode', 'live', '--day', '<today>', '--refresh', '--allow ...
E   AssertionError: The instrument master 'OpenAPIScripMaster_2026-08-18.json' is not at nowhere-at-all-r1\instrument_master\OpenAPIScripMaster_2026-08-18.json. CONTEXT 4.7 runs a live morni ...
E   AssertionError: the refusal prints a command whose target is not a file in this repo: ['python', '-m', 'acumen.instrument_master', '--allow-network']
E   AssertionError: corporate-action refresh FENCED: the cache lives inside the stores, which a session treats as READ-ONLY (CLAUDE.md data-store safety, Q-18 layer 2), so the day-cache was  ...
E   AssertionError: the fence prints an ingest command whose target is not a file in this repo: ['python', '-m', 'acumen.ca_report', '--from', '<D>', '--to', '<D>', '--allow-network']
E   AssertionError: acumen.live_screener can still print the dead form: ['. Run the pre-open refresh (`python -m acumen.run_screener --mode live --day <today> --refresh --allow-network`), or ...
E   AssertionError: backtest names the launcher its two operator-facing strings print
E   AssertionError: a printable string in src/ names the dead `-m acumen.` form again: {'backtest.py': [1612, 1586], 'live_screener.py': [2372]}
FAILED tests/test_review15b_fix.py::test_R1_the_LIVE_MORNINGS_own_refusal_names_LAUNCHERS_and_not_the_dead_module_form
FAILED tests/test_review15b_fix.py::test_R1_the_LIVE_MORNINGS_two_remedies_PARSE_and_RUN_with_PYTHONPATH_stripped
FAILED tests/test_review15b_fix.py::test_R1_the_named_master_refusal_names_the_LAUNCHER_and_not_the_dead_module_form
FAILED tests/test_review15b_fix.py::test_R1_the_named_master_remedy_PARSES_and_RUNS_with_PYTHONPATH_stripped
FAILED tests/test_review15b_fix.py::test_R1_the_CA_REFRESH_FENCE_names_the_LAUNCHER_and_not_the_dead_module_form
FAILED tests/test_review15b_fix.py::test_R1_the_CA_REFRESH_ingest_path_PARSES_and_RUNS_with_PYTHONPATH_stripped
FAILED tests/test_review15b_fix.py::test_R1_no_printable_string_in_EITHER_touched_module_names_the_dead_form
FAILED tests/test_review15b_fix.py::test_R1_the_master_launcher_is_ONE_name_across_the_gate_and_the_two_fixed_sites
FAILED tests/test_review15b_probes.py::test_FLIPPED_R15B_R1_the_dead_form_is_GONE_from_every_printable_string_in_src
9 failed in 4.84s
```

Line numbers in the last one are the pre-fix sites: `backtest.py` 1586 (`named_master`'s refusal)
and 1612 (`CA_REFRESH_FENCED`), `live_screener.py` 2372 (`_require_day_master`) -- R1's three,
measured rather than assumed.

## GREEN -- the same nine at `a1764a4` (this session's fix)

```
.........                                                                [100%]
9 passed in 13.35s
```

Full suite in the operator's tree at the same commit: **2,621 passed / 0 failed / 0 skipped**
(871.53s) -- REVIEW_15B's 2,613 plus this session's 8, to the test.
