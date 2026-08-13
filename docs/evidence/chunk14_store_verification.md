# chunk 14 -- the 13-Aug store snapshot, VERIFIED from the machine

CLAUDE.md, data-store safety: *"Operator-executed runbooks are relayed, not certified: after any
multi-step operator procedure, the next session's FIRST duty is an independent verification sweep
of every step's completion evidence read from the machine itself -- ledgers, files, digests,
offline re-runs. Pasted transcripts are never the record."*

REVIEW_13B closed with two conditions on the operator, neither of them a code change, and both of
them prerequisites for this chunk. This document is this session's own reading of whether they
were done. Nothing here is quoted from a transcript: every number below was produced by running
the committed script on this machine, in this session, read-only.

## Condition 1 -- the store snapshot after the corporate-action refresh

REVIEW_13B PART 5 recorded that driving the shipped live path with `--allow-network` rewrote 22
`nse/ca/*.json` files inside `data_root` (+46,262 bytes, 2026-08-12 23:18:39-23:19:20), and that
**the operator owes a snapshot of `data/` and `cache/` before chunk 14 begins**.

The operator ran `docs/evidence/housekeeping_13aug_store_fingerprint.py` twice against the live
store and copied the store to `A:\acumen backup\acumen-backup-13aug`. Both of his passes are
committed beside the script (`.pass1.json`, `.pass2.json`). This session re-ran the same script a
THIRD time against the live store, and a fourth time against the copy on the backup drive:

| pass | root | files | bytes | content digest | metadata digest |
|---|---|---:|---:|---|---|
| operator 1 | `C:\Users\chinm\acumen-data` | 22,186 | 4,109,782,853 | `d97ba419…9d089` | `dbea5660…61423` |
| operator 2 | `C:\Users\chinm\acumen-data` | 22,186 | 4,109,782,853 | `d97ba419…9d089` | `dbea5660…61423` |
| **this session** | `C:\Users\chinm\acumen-data` | **22,186** | **4,109,782,853** | **`d97ba419…9d089`** | **`dbea5660…61423`** |
| **this session** | `A:\…\acumen-backup-13aug\acumen-data` | **22,186** | **4,109,782,853** | **`d97ba419…9d089`** | **`dbea5660…61423`** |

Full digests, so the table above can be checked rather than believed:

```
content   d97ba4191339be543df9ee8a67f3a8c17aed629e0cc21e4be1d989a86dc1e089
metadata  dbea5660b7734f6a71edd5e99eac0159e53174ec431a1a7fb17c2bad5bf61423
newest    2026-08-12T23:19:20  nse/ca/nse_ca_2026-01-01_2026-12-31.json
```

**The snapshot is faithful to the byte.** The CONTENT digest is what certifies a copy (the
script's own docstring says so, because a copy tool need not preserve timestamps); here the
METADATA digest matches too, so even the mtimes came across. The newest file in both trees is the
last corporate-action file REVIEW_13B's refresh wrote, which is the event that made the snapshot
owed -- so the snapshot is provably NEWER than the change it protects against, which is Q-18
layer 3's own test.

One reading needs stating so a later reader is not confused by it: the first run of the fourth
pass was taken against `A:\…\acumen-backup-13aug` itself and produced a DIFFERENT content digest
(`0ad17a8e…`) with identical file and byte counts. That is not a difference in the data: the copy
is nested one directory deeper (`…\acumen-backup-13aug\acumen-data\…`), and the digest recipe
hashes each file's path relative to the root it was given. Fingerprinting the inner directory --
the one that corresponds to `data_root` -- is the comparison that means anything, and it matches.

Also verified, from `A:\acumen backup`: the previous generation is still present
(`acumen backup 5 aug`, `acumen backup 2 aug evening`, `acumen backup 2 aug`, `acumen backup old`,
`acumen backup runday`, `acumen-data`). Q-18 layer 3 asks for TWO generations and there are six.

**The store is unchanged since REVIEW_13B measured it.** That review's "after" reading was
22,186 files / 4,109,782,853 bytes; this session's is the same to the byte, so nothing has
written to `data_root` between the review and this chunk -- including this session, which has
opened every one of those files read-only and written none of them.

## Condition 2 -- the six leaking `logs/` files

REVIEW_13's finding F6 measured this repository's own `logs/` carrying `X-PrivateKey` and
`Bearer` header lines written by the vendor SDK before the FIX-2 guard closed it, and REVIEW_13B
left the rotation with the operator: *"the operator rotates the six `logs/` files (B5's
outstanding half, which turns its probe red)"*.

Read from the machine: `logs/` exists and holds **no `*.log` file at all** -- the six are gone.

The probe that pinned the defect could not report that, and this is the one-liner this session
owed: its "nothing to pin" branch was a `pytest.skip`, so the receipt for closing the defect was
a SKIP, indistinguishable from "this machine has no logs directory". Turning that single line
into `pytest.fail` and running it produced the red REVIEW_13B was waiting for:

```
tests/test_review13_probes.py::test_the_repos_own_run_logs_carry_credential_shaped_headers
E   Failed: this machine's logs/ has been rotated since the review -- nothing to pin
1 failed in 1.01s
```

The pin is now FLIPPED to the standing guarantee it should become --
`test_the_repos_own_run_logs_carry_NO_credential_shaped_headers`, which walks every byte of every
file under `logs/` and asserts zero credential-shaped headers, and which passes trivially (rather
than skipping) on a clone that has no `logs/` at all. A clean clone therefore has ONE gitignored-
input skip left where REVIEW_13B counted two.

## What this session did to the stores

Nothing. Every access above is `open(..., "rb")` through the committed fingerprint script, plus
read-only opens of the daily store, the minute lake and the chunk-9B ledger by the parity work.
The fingerprint at the end of this session is expected to be the one at the top of this document,
and the chunk-14 report states it again after the last test run.
