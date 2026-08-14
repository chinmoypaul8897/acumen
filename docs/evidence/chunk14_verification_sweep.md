# chunk 14 -- the end-of-chunk verification sweep

Run 2026-08-14 13:46 -> 14:44 IST from `docs/evidence/chunk14_verification_sweep.sh`, against
HEAD = `3c17d9faf75f5b9c6f598229e48263cfeb1886ef`. READ-ONLY over the stores.

This document re-derives two of the chunk's own claims rather than quoting them: the suite's
result **from a clean clone**, and the property that a whole test run writes **nothing** under
`data_root`. Both are stated in the chunk-14 PROGRESS entry; both are checked here from the
machine, which is the standard CLAUDE.md sets for relayed evidence.

## 1. The suite, from a clean clone

```
$ git clone <repo> clone14 && cd clone14 && git log --oneline -1
3c17d9f chunk14: PROGRESS entry and STATUS -- the parity harness stands and the alert reaches the phone
clone has .env?: no
clone has logs/?: no

$ python -m pytest -q -p no:cacheprovider
........................................................................ [100%]
2473 passed, 1 skipped, 4 warnings in 2292.99s (0:38:12)
pytest exit=0
```

**2473 passed / 0 failed / 1 skipped.** That reproduces the build's own claim exactly. The build
measured the same 2473/0/1 at `fc99e2b`, the last code commit; this reading is at `3c17d9f`, one
commit later, and that commit touches only `PROGRESS.md` and `STATUS.md`.

The single skip is the `.env`-input probe, which cannot run on a clone that has no `.env` -- the
count REVIEW_13B's clone had was two, and the second is gone because the flipped log-leak probe
now PASSES on a clone instead of skipping (`docs/evidence/chunk14_store_verification.md` §2).

The four warnings are the vendor SDK's own `ssl.OP_NO_TLSv1` deprecations, raised inside
`SmartApi/smartConnect.py` by the two chunk-13 probes that drive the REAL vendor constructor.
They are the library's, not this repository's.

**One difference from the build's reading, and it is a runtime and not a result:** 2292.99s here
against the build's 453.25s for the same 2473/0/1. Nothing in the tree changed between the two
runs; the sweep ran with a 4.1 GB store fingerprint bracketing it on the same disk. The suite's
outcome is identical test for test.

## 2. Zero store writes, measured across the whole run

The same committed fingerprint script the operator ran, before and after the suite:

| pass | files | bytes | content digest | metadata digest |
|---|---:|---:|---|---|
| before pytest | 22,186 | 4,109,782,853 | `d97ba419…9d089` | `dbea5660…61423` |
| after pytest | 22,186 | 4,109,782,853 | `d97ba419…9d089` | `dbea5660…61423` |

```
content   d97ba4191339be543df9ee8a67f3a8c17aed629e0cc21e4be1d989a86dc1e089
metadata  dbea5660b7734f6a71edd5e99eac0159e53174ec431a1a7fb17c2bad5bf61423
newest    2026-08-12T23:19:20  nse/ca/nse_ca_2026-01-01_2026-12-31.json
diff      (empty)  ->  STORE UNCHANGED ACROSS THE RUN
```

Both digests are byte-identical before and after, and both equal the operator's 13-Aug snapshot
reading committed in `housekeeping_13aug_store_fingerprint.pass1.json`. Three things follow, and
the third is the one worth having:

1. the store is unchanged since REVIEW_13B measured it, so the operator's snapshot is still the
   current state and Q-18 layer 3's "snapshot newer than the change" still holds;
2. this chunk's work wrote nothing to the stores;
3. **the suite itself writes nothing to the stores** -- including `test_Q3_a_LIVE_REFRESH_writes_
   ZERO_bytes_under_the_stores`, which drives `build_runner(..., allow_network=True)` for real.
   The Q3 fence is therefore proved twice: by its own assertion, and by a digest taken across the
   run that contains it. The newest file under `data_root` is still the last corporate-action
   file REVIEW_13B's un-fenced refresh wrote, and no chunk-14 run has added to it.

## 3. Repository hygiene over `db45998..HEAD`

Checked here rather than asserted, all from `git` itself:

| check | result |
|---|---|
| `(unreviewed)` suffix on every commit touching `src/` or `tests/` | 5 of 5 present (REVIEW_7 C1) |
| AI attribution anywhere in the span's messages | none -- the only matches are the permitted `CLAUDE.md` filename citation (REVIEW_7 C4) |
| `.env`, `data/` or `cache/` in any committed path | none |
| tests deleted, weakened or skipped into agreement | none. 1,706 -> 1,739 unique test names; **exactly 5 names gone and all 5 are the deliberate defect-pin flips** (Q1, Q2, Q3, Q4 and the log-leak probe), 38 added |
| local `main` vs `origin/main` | identical, no divergence |

The five vanished names, listed so the claim can be checked rather than believed:

```
test_the_live_alert_line_carries_NO_staleness_marker_when_the_feed_freezes      -> Q1 pin, flipped
test_the_live_calendar_falls_through_a_GAP_inside_the_history_without_refusing  -> Q2 pin, flipped
test_build_runner_takes_the_CORPORATE_ACTION_cache_from_data_root_not_from_config -> Q3 pin, flipped
test_the_order_tripwire_still_walks_past_percent_and_format_construction        -> Q4 pin, flipped
test_the_repos_own_run_logs_carry_credential_shaped_headers                     -> log-leak probe, flipped
```

## 4. One shortfall against plan.md's card, named

plan.md's chunk-14 card lists four Build items: *"live dashboard view ...; Telegram bot ...;
alert dedup; end-of-day summary message."* Three are built and tested. **The end-of-day summary
MESSAGE is not.** `TelegramSink.summary()` exists and `run_screener` prints it, but it goes to
the operator's terminal and is never sent to the phone:

```
$ grep -rn "summary" src/acumen/telegram_sink.py src/acumen/run_screener.py
src/acumen/telegram_sink.py:200:    def summary(self) -> str:
src/acumen/run_screener.py:238:        print(telegram.summary())
```

Stated plainly rather than absorbed: it is NOT in the card's "Done when" (*"test-mode alerts
delivered to both channels; payload fields complete; no duplicate alerts on re-poll"*, all three
met), and it was not in the architect's chunk-14 session scope, which named the parity harness,
the Telegram sink and the runbook stub. So this is a card line item outstanding, not a failed
acceptance criterion -- it is the architect's call whether it lands in chunk 14's review, in
chunk 15 (which owns the debrief and the full runbook), or not at all. It is raised here rather
than in QUESTIONS.md because it is not a spec silence: the card is perfectly clear, the item is
simply not built.
