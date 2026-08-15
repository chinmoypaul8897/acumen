# chunk-14 FIX-2 -- the store bracket, and what it certifies

**Session:** chunk 14, FIX-2 (REVIEW_14's FAIL), 15-Aug-2026.
**Generating script:** `docs/evidence/housekeeping_13aug_store_fingerprint.py` (already committed;
read-only by construction -- it opens every file `"rb"` and writes nothing). REVIEW_7 C3 binds a
claim made from real store data to its generating script and its output; this file is the output.

```
python docs/evidence/housekeeping_13aug_store_fingerprint.py
```

`cache_root` is `C:/Users/chinm/acumen-data/cache`, which is INSIDE `data_root` on this machine,
so one whole-tree fingerprint covers BOTH roots. That is the same fact REVIEW_14 B1 turned on --
a corporate-action pull into `cache_root/ca/` lands in the snapshot-protected tree.

## 0. The operator's restoration, verified from the machine before any work began

CLAUDE.md's Q-18 recovery lesson: *"operator-executed runbooks are relayed, not certified; the
next session's FIRST duty is an independent verification sweep read from the machine itself."*
REVIEW_14 PART 6 disclosed that one of its own probes wrote 11 `error` rows into
`daily_store/ledger.parquet` and named the success condition: the whole-store content digest
returns to `d97ba419...`.

```
{
  "root": "C:\\Users\\chinm\\acumen-data",
  "files": 22186,
  "bytes": 4109782853,
  "metadata_digest": "dbea5660b7734f6a71edd5e99eac0159e53174ec431a1a7fb17c2bad5bf61423",
  "content_digest": "d97ba4191339be543df9ee8a67f3a8c17aed629e0cc21e4be1d989a86dc1e089",
  "newest_mtime": "2026-08-12T23:19:20",
  "newest_file": "nse/ca/nse_ca_2026-01-01_2026-12-31.json"
}
```

**RESTORED, confirmed.** 22,186 files and 4,109,782,853 bytes, matching the committed 13-Aug
fingerprint (`docs/evidence/housekeeping_13aug_store_fingerprint.pass{1,2}.json`) exactly, and the
content digest is `d97ba419...`. The newest file in the whole store is dated 2026-08-12, which is
BEFORE the 19:48 2026-08-14 write the review disclosed -- so the contaminating rows are gone
rather than merely overwritten by newer ones. Q-18 layer 3 is no longer violated: the store is
older than the snapshot protecting it.

## 1. The bracket around the full suite, from a clean clone

The suite was run from a fresh `git clone` of this repository at `b73c6ff`, ALONE, with the
fingerprint taken immediately before and immediately after in the operator's own tree.

```
before  files 22186  bytes 4109782853  metadata dbea5660...  content d97ba419...
after   files 22186  bytes 4109782853  metadata dbea5660...  content d97ba419...
```

**Byte-identical, and metadata-identical** -- not one file was created, removed, resized or
re-stamped. `newest_mtime` is unmoved at `2026-08-12T23:19:20`. The suite reads the stores and
writes nothing under either root.

Suite result from that clone: **2,510 passed / 0 failed / 1 skipped** in 440.11s. The one skip is
the `.env`-input probe (`tests/test_review13_probes.py`, *"no .env on this machine"*), which a
clone must skip and the operator's tree must run.

The same suite was then run again **in the operator's own tree** -- **2,511 passed / 0 failed /
0 skipped** in 464.93s, the one-test difference being that same `.env` probe -- and the store was
fingerprinted a third time afterwards:

```
after the operator-tree run   files 22186  metadata dbea5660...  content d97ba419...
```

Unmoved again. Two full suite runs, two clean brackets.

## 2. What this bracket does NOT claim

Stated explicitly, because REVIEW_14 B2 is the finding that a no-write claim was made wider than
what was measured, and CLAUDE.md now carries the rule that came out of it.

* It certifies that **this suite**, and every test in it, writes zero bytes under `data_root` and
  `cache_root`. It is measured over the whole of both, file by file, size and mtime.
* It does **not** claim that a real networked morning writes nothing. It cannot: ingesting
  yesterday's bhavcopy into the daily store and fetching today's own instrument master ARE
  writes, and they are the pre-open's product. What B1 fixed is the write that was never
  anybody's product -- the corporate-action refresh into a cache inside the stores, which
  rewrites the factor tables a frozen run's `factor_digest` depends on.
* The tests that need a mutable store build a **COPY** of the slices one symbol-day needs
  (`tests/test_review14_fix.py::build_scratch_world`, ~65 MB) and point a scratch `config.yaml`
  at it. A copy, never a junction or a symlink. That is CLAUDE.md's newest rule executed: *a
  review or any session may NEVER run a mutating CLI against the real data_root/cache_root.*

## 3. Snapshot status

**No new snapshot is owed.** The stores are unchanged by this session, and unchanged since the
13-Aug fingerprint the operator restored to. The operator's existing two generations still cover
the current state.
