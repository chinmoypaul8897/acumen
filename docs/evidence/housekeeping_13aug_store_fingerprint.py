"""Pre-snapshot fingerprint of data_root -- the 14-Aug-2026 housekeeping session.

Purpose: give the operator a CLEAN-STATE receipt to snapshot against, and a way to prove
afterwards that the copy on the backup drive is faithful. Run it once against the live store
(the digest printed below), then again against `A:\\acumen-backup-13aug` once the copy is done:
the CONTENT digest must match exactly. The metadata digest may differ if the copy tool did not
preserve timestamps, which is why the content digest is the one that certifies the snapshot.

READ-ONLY by construction: it opens every file "rb" and writes nothing anywhere under the
stores. CLAUDE.md's Q-18 layer 2 (stores are read-only to sessions) is respected.

Two recipes, both over the file set sorted by POSIX-style relative path:
  metadata digest = sha256 over "<relpath>|<size>|<mtime_ns>" lines
  content  digest = sha256 over "<relpath>|<size>|<sha256 of the file's bytes>" lines

ASCII-only, like every other source file in this repo (chunk-0 B7).

Usage:  python docs/evidence/housekeeping_13aug_store_fingerprint.py [root]
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

CHUNK = 1024 * 1024


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(CHUNK)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def fingerprint(root: Path) -> dict:
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
        meta.update(f"{rel}|{stat.st_size}|{stat.st_mtime_ns}\n".encode("utf-8"))
        content.update(f"{rel}|{stat.st_size}|{file_sha256(path)}\n".encode("utf-8"))
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
    report = fingerprint(root)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
