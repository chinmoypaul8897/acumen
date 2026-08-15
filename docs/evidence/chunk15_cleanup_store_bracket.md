# Chunk 15 CLEANUP -- the stores, bracketed open and close

The final cleanup session (16-Aug-2026) over REVIEW_15's nine findings. Nothing in it was
supposed to touch a store: seven prose/attribution/one-string fixes, their tests, and two full
suite runs. This is the measurement rather than the assurance.

`docs/evidence/housekeeping_13aug_store_fingerprint.py` -- read-only by construction, committed
beside this output (REVIEW_7 C3) -- run BEFORE this session's first store-touching command and
again AFTER its last. Between the two readings sit: the full suite from a clean clone (2,598
passed, 508.08s), the full suite in the operator's own tree (2,599 passed, 482.68s), every
chunk-15 test file run twice while the fixes were being written, and one bare run of
`scripts/fetch_instrument_master.py` with no `--allow-network` (C1's verification).

```
open   files 22186  bytes 4109782853  metadata dbea5660...  content d97ba419...
                    newest 2026-08-12T23:19:20  nse/ca/nse_ca_2026-01-01_2026-12-31.json
close  files 22186  bytes 4109782853  metadata dbea5660...  content d97ba419...
                    newest 2026-08-12T23:19:20  nse/ca/nse_ca_2026-01-01_2026-12-31.json
```

Both readings in full, as the script printed them:

```json
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

**Every digit identical, metadata included** -- and identical to `chunk15_store_bracket.md`, to
REVIEW_15 PART 0 and to REVIEW_14B PART 6. The metadata digest matters as much as the content
one: a file rewritten with identical bytes still moves its `mtime_ns`, and none did. `cache_root`
sits INSIDE `data_root` (`C:/Users/chinm/acumen-data/cache`), so one fingerprint brackets both
roots.

**No mutating CLI was run against either root.** The one command this session ran against the
real store was `python scripts/fetch_instrument_master.py` with **no** `--allow-network` -- C1's
own verification that the remedy the readiness gate now prints really runs on a tree with no
editable install. It lists the cache directory and prints *"STOPPING (no --allow-network).
Nothing was fetched and nothing was written."*, exit 0. Its test drives the same launcher against
a scratch cache directory instead, so the suite never reads the real one.

```
$ python -c "import acumen"
ModuleNotFoundError: No module named 'acumen'          <- there is no editable install here
$ python scripts/fetch_instrument_master.py
cache dir    : C:\Users\chinm\acumen-data\cache\instrument_master
already held : 2 dump(s), newest OpenAPIScripMaster_2026-08-02.json
STOPPING (no --allow-network). Nothing was fetched and nothing was written.
exit 0
```

**One read-only observation, recorded because B432 turns on it:** `<data_root>/live` does not
exist on this machine. There are no live recordings yet, so the queue change this session made
(a directory with no `manifest.json` is surfaced rather than skipped, and an entry nothing can
date stops the morning) cannot refuse anything that exists today. The first artefact it can ever
refuse is one a dry-run week creates.

**Operator note: no new snapshot is owed.** The stores are byte-unmoved by this session, as they
were by the chunk-15 build and by REVIEW_15, and the existing two generations still cover the
current state.
