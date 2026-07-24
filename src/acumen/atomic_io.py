"""Crash-safe file writes: write a temp file beside the target, then ``os.replace`` it.

Why this exists (docs/reviews/REVIEW_1.md Finding 2, and personas/code_reviewer.md
checklist 2 -- "interrupted runs leave no half-written files"): every store this repo keeps
is written by a long, interruptible job. The chunk-2 backfill runs for hours and is meant to
be Ctrl-C-able; the chunk-13 morning refresh runs unattended before 09:15. A write that is
interrupted halfway must leave the PREVIOUS good file in place, never a truncated one -- a
truncated cache or a truncated parquet is silent corruption that the next session inherits.

``os.replace`` is atomic on both POSIX and Windows when source and destination sit on the
same filesystem, which is why the temp file is always created in the target's own directory.

This module is I/O ONLY and is not part of the pure engine layer (CONTEXT 6).

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Callable

__all__ = ["atomic_write_bytes", "atomic_write_text", "atomic_write_with"]


def atomic_write_bytes(path: Path, data: bytes) -> Path:
    """Write ``data`` to ``path`` atomically, creating parent directories.

    The target either keeps its previous contents or holds the complete new bytes; it is
    never left half-written. Returns the path written.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle_fd, temp_name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle_fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
    except BaseException:
        # BaseException on purpose: a KeyboardInterrupt mid-write is the exact scenario this
        # module exists for, and it must not leave the temp file behind either.
        temp_path.unlink(missing_ok=True)
        raise
    return target


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> Path:
    """Write ``text`` to ``path`` atomically. See :func:`atomic_write_bytes`."""
    return atomic_write_bytes(path, text.encode(encoding))


def atomic_write_with(path: Path, writer: Callable[[Path], None]) -> Path:
    """Atomically produce ``path`` using a ``writer`` that writes to a path it is given.

    For libraries that insist on writing to a filename themselves (pyarrow's parquet
    writer, for one). ``writer`` receives a temp path in the target's directory; the file it
    produces is moved into place in one step, and is deleted if ``writer`` raises.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle_fd, temp_name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    os.close(handle_fd)
    temp_path = Path(temp_name)
    try:
        writer(temp_path)
        os.replace(temp_path, target)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return target
