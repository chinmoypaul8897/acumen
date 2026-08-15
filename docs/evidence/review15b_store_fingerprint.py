"""REVIEW_15B's OWN store fingerprint -- the same two digests, re-implemented, allocation-free.

Why a second script rather than the committed
``docs/evidence/housekeeping_13aug_store_fingerprint.py``:

1. **It could not run on this machine.** That script calls ``handle.read(1024*1024)`` once per
   block, so a 4.1 GB / 22,186-file walk asks the allocator for a fresh 1 MB object several
   thousand times. Read on 16-Aug-2026 the machine was at 97% memory load with ~0.2 GB physical
   and ~0.3 GB commit free (Windows ``GlobalMemoryStatusEx``), and both attempts died with
   ``MemoryError`` inside ``file_sha256``. This one allocates ONE 256 KB buffer for the entire
   run and fills it with ``readinto``, so the walk asks the allocator for nothing at all after
   start-up. The committed script is NOT edited -- it is frozen evidence of two prior sessions.

2. **A review should re-derive rather than re-run.** REVIEW_15 and the cleanup both quote a
   digest produced by one implementation. An independent implementation of the same written
   recipe is what makes a matching digest mean something: if this agrees with them to the digit,
   two different programs read the same bytes off the same disk.

The recipe is the committed script's own, verbatim from its docstring, over the file set sorted
by POSIX-style relative path:

    metadata digest = sha256 over "<relpath>|<size>|<mtime_ns>" lines
    content  digest = sha256 over "<relpath>|<size>|<sha256 of the file's bytes>" lines

READ-ONLY by construction: every file is opened ``"rb"`` and nothing anywhere under either root
is created, written, renamed or removed. ``cache_root`` sits inside ``data_root`` on this
machine, so one walk brackets both (CLAUDE.md data-store safety, Q-18 layer 1).

ASCII-only, like every other source file in this repo (chunk-0 B7).

Usage:  python docs/evidence/review15b_store_fingerprint.py [root]
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

#: One buffer, allocated once, reused for every block of every file. The whole point of this
#: script: the committed one's per-read 1 MB allocation is what fails under commit pressure.
BUFFER_BYTES = 256 * 1024


def fingerprint(root: Path) -> dict:
    buffer = bytearray(BUFFER_BYTES)
    view = memoryview(buffer)
    files = sorted(
        (p for p in root.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    meta = hashlib.sha256()
    content = hashlib.sha256()
    total_bytes = 0
    newest_ns = 0
    newest_rel = ""
    for path in files:
        rel = path.relative_to(root).as_posix()
        stat = path.stat()
        total_bytes += stat.st_size
        if stat.st_mtime_ns > newest_ns:
            newest_ns, newest_rel = stat.st_mtime_ns, rel
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                read = handle.readinto(buffer)
                if not read:
                    break
                digest.update(view[:read])
        meta.update(f"{rel}|{stat.st_size}|{stat.st_mtime_ns}\n".encode("utf-8"))
        content.update(f"{rel}|{stat.st_size}|{digest.hexdigest()}\n".encode("utf-8"))
    return {
        "root": str(root),
        "files": len(files),
        "bytes": total_bytes,
        "metadata_digest": meta.hexdigest(),
        "content_digest": content.hexdigest(),
        "newest_mtime": datetime.fromtimestamp(newest_ns / 1e9).isoformat(timespec="seconds"),
        "newest_file": newest_rel,
    }


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("C:/Users/chinm/acumen-data")
    if not root.is_dir():
        print(f"not a directory: {root}")
        return 1
    print(json.dumps(fingerprint(root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
