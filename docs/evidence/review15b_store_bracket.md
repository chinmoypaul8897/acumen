# REVIEW_15B -- the stores, bracketed open and close

The SCOPED RE-CHECK of chunk 15's cleanup (16-Aug-2026) over `ee412a6..29cd748`. A review fixes
nothing and writes nothing under the stores; this is the measurement rather than the assurance.

Between the two readings sit: **two full suite runs** (a clean clone at `29cd748`, 2,598 passed /
1 skipped in 1187.36s; the operator's own tree with this review's 14 kept probes, 2,613 passed /
0 skipped in 683.57s), **three runs of `docs/evidence/chunk14_parity.py`** over the real ledger,
daily store, minute lake and instrument master (one at HEAD, one on a clean checkout of `ee412a6`,
each writing only to scratch), the reviewer probes run repeatedly on both trees, and one bare run
of `scripts/fetch_instrument_master.py` with no `--allow-network` against a **scratch** cache
directory.

```
open   files 22186  bytes 4109782853  metadata dbea5660...  content d97ba419...
                    newest 2026-08-12T23:19:20  nse/ca/nse_ca_2026-01-01_2026-12-31.json
close  files 22186  bytes 4109782853  metadata dbea5660...  content d97ba419...
                    newest 2026-08-12T23:19:20  nse/ca/nse_ca_2026-01-01_2026-12-31.json
```

Both readings in full, as the script printed them (identical, so one block serves for both):

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

**Every digit identical, metadata included** -- and identical to `chunk15_cleanup_store_bracket.md`,
to `chunk15_store_bracket.md`, to REVIEW_15 PART 0 and to REVIEW_14B PART 6. The metadata digest
matters as much as the content one: a file rewritten with identical bytes still moves its
`mtime_ns`, and none did. `cache_root` sits INSIDE `data_root`
(`C:/Users/chinm/acumen-data/cache`), so one walk brackets both roots.

## Why a SECOND fingerprint script exists

**The committed `housekeeping_13aug_store_fingerprint.py` could not run on this machine.** It calls
`handle.read(1024 * 1024)` once per block, so a 22,186-file / 4.1 GB walk asks the allocator for a
fresh 1 MB object several thousand times. Measured here with Windows `GlobalMemoryStatusEx`, the
machine sat at **95-98% memory load, ~0.2-0.4 GB physical and ~0.3-0.7 GB commit free** for most
of the session; two attempts died with `MemoryError` inside `file_sha256`, and PowerShell itself
failed to launch with `0x800705AF` (ERROR_COMMITMENT_LIMIT). Several helper processes were killed
by the same limit.

**That script was NOT edited.** It is frozen evidence of two prior sessions. Instead this review
wrote `docs/evidence/review15b_store_fingerprint.py`: an independent implementation of the SAME
written recipe --

```
metadata digest = sha256 over "<relpath>|<size>|<mtime_ns>" lines
content  digest = sha256 over "<relpath>|<size>|<sha256 of the file's bytes>" lines
```

-- over the file set sorted by POSIX-style relative path, which allocates **one** 256 KB buffer for
the whole run and fills it with `readinto`, asking the allocator for nothing after start-up.
Read-only by construction: every file opened `"rb"`, nothing under either root created, written,
renamed or removed.

**This strengthens the bracket rather than weakening it.** REVIEW_15, REVIEW_14B and the cleanup
all quote a digest produced by ONE program. A second, independently written program reading the
same disk produced **the same two digests to the digit**, which is what makes a matching digest
mean something -- and it validates the new script against the frozen recipe at the same time. A
future session under memory load now has a route that works.

## No mutating CLI, and one read-only observation

**No mutating CLI was run against either root** (CLAUDE.md, the REVIEW_14 store incident).
Everything that could write ran against a scratch copy or a `tmp_path` tree of its own; the parity
re-derivations were pointed at scratch `--out`/`--sample` paths so the committed artefacts were
never overwritten; and `scripts/fetch_instrument_master.py` was run **without** `--allow-network`
against a scratch cache directory, where it prints *"STOPPING (no --allow-network). Nothing was
fetched and nothing was written."*

**`<data_root>/live` still does not exist on this machine**, re-verified read-only by this review.
There are no live recordings yet, so the queue changes this cleanup made (a directory with no
`manifest.json` is surfaced rather than skipped, and an entry nothing can date stops the morning)
cannot refuse anything that exists today. The first artefact they can ever refuse is one a dry-run
week creates.

**Operator note: no new snapshot is owed.** The stores are byte-unmoved by the chunk-15 build, by
REVIEW_15, by the cleanup and by this re-check, and the existing two generations still cover the
current state.
