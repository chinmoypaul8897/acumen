"""R1's store bracket -- the METADATA half of the frozen recipe, and nothing else.

The R1 fix changes three printable strings in ``src/`` and touches no store: it runs no
mutating CLI, opens no network and reads neither root. This script is how that claim is
MEASURED rather than asserted (CLAUDE.md data-store safety; REVIEW_7 **C3** -- a session making
a claim from real store data commits the script that produced it).

**Metadata only, on purpose.** The frozen recipe
(``docs/evidence/housekeeping_13aug_store_fingerprint.py``, re-derived by
``docs/evidence/review15b_store_fingerprint.py``) computes two digests over the same file set,
sorted by POSIX-style relative path:

    metadata digest = sha256 over "<relpath>|<size>|<mtime_ns>" lines
    content  digest = sha256 over "<relpath>|<size>|<sha256 of the file's bytes>" lines

This script computes the FIRST line of that recipe, byte-for-byte, and skips the second. It
therefore reads no file's contents at all -- it opens nothing under either root -- which makes
the walk seconds rather than minutes on 22,186 files / 4.1 GB and asks the allocator for
nothing (REVIEW_15B **R5**: the committed script died with ``MemoryError`` on this machine at
97-98% memory load). ``mtime_ns`` is what makes the metadata half sufficient here: a file that
is created, written, truncated, renamed or removed moves its size, its ``mtime_ns`` or the file
set itself, and all three are inside this digest. The published metadata digest to compare
against is REVIEW_15B PART 0's ``dbea5660b7734f6a71edd5e99eac0159e53174ec431a1a7fb17c2bad5bf61423``.

READ-ONLY by construction: it stats files and never opens one. ``cache_root`` sits inside
``data_root`` on this machine, so one walk brackets both roots (Q-18 layer 1).

ASCII-only, like every other source file in this repo (chunk-0 B7).

Usage:  python docs/evidence/r1_store_metadata_fingerprint.py [root]
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


def fingerprint(root: Path) -> dict:
    files = sorted(
        (p for p in root.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    meta = hashlib.sha256()
    total_bytes = 0
    newest_ns = 0
    newest_rel = ""
    for path in files:
        rel = path.relative_to(root).as_posix()
        stat = path.stat()
        total_bytes += stat.st_size
        if stat.st_mtime_ns > newest_ns:
            newest_ns, newest_rel = stat.st_mtime_ns, rel
        meta.update(f"{rel}|{stat.st_size}|{stat.st_mtime_ns}\n".encode("utf-8"))
    return {
        "root": str(root),
        "files": len(files),
        "bytes": total_bytes,
        "metadata_digest": meta.hexdigest(),
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
