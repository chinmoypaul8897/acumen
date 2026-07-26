"""Crash-safe, power-loss-safe file writes: write a temp file beside the target, ``fsync``
it, then ``os.replace`` it.

Why this exists (docs/reviews/REVIEW_1.md Finding 2, and personas/code_reviewer.md
checklist 2 -- "interrupted runs leave no half-written files"): every store this repo keeps
is written by a long, interruptible job. The chunk-2 backfill runs for hours and is meant to
be Ctrl-C-able; the chunk-13 morning refresh runs unattended before 09:15. A write that is
interrupted halfway must leave the PREVIOUS good file in place, never a truncated one -- a
truncated cache or a truncated parquet is silent corruption that the next session inherits.

``os.replace`` is atomic on both POSIX and Windows when source and destination sit on the
same filesystem, which is why the temp file is always created in the target's own directory.

**Durability against power loss (REVIEW_2 Finding 6, pulled forward after the 2026-07-25
power-loss incident).** ``os.replace`` being atomic is not enough on its own: after the
rename, the operating system may still hold the new file's *data* only in its page cache. If
the machine loses power in that window the rename can be durable while the bytes are not,
leaving a correctly-named file that is zero-length or full of un-flushed garbage -- which is
exactly the corruption the 2026-07-25 backfill hit (a 87 KB archive CSV of pure spaces, a
truncated month parquet and a truncated ledger, all with valid names). So every write here
now ``os.fsync``s the file's DATA to disk BEFORE the ``os.replace``, and best-effort
``fsync``s the containing DIRECTORY afterwards so the rename itself is durable:

* file fsync -- enforced on BOTH POSIX and Windows (``os.fsync`` -> ``FlushFileBuffers``);
* directory fsync -- POSIX only. Windows has no portable way to obtain a flushable directory
  handle (``os.open`` on a directory raises ``PermissionError``), and NTFS journals the
  rename metadata itself, so on Windows this step is an honest documented no-op. The
  data-durability half -- the half that actually prevents the incident above -- holds on both.

This module is I/O ONLY and is not part of the pure engine layer (CONTEXT 6).

Source files in this package are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Callable

__all__ = ["atomic_write_bytes", "atomic_write_text", "atomic_write_with"]

#: How many times to retry a rename that Windows transiently refuses, and the base backoff.
#: On Windows ``os.replace`` fails with ``PermissionError``/``OSError`` when ANOTHER process holds
#: an open handle to the TARGET -- an antivirus scanner or the search indexer opening a
#: just-written parquet is the ordinary cause, and it clears in milliseconds. POSIX renames a
#: file out from under an open handle happily, so this never fires there. Measured live: the
#: chunk-5B quarantine-recovery reroute rewrites ~1,500 month files for one symbol in a tight
#: loop, and one rename in a run of tens of thousands was refused. Retrying is correct because
#: the temp file is complete and fsynced BEFORE the rename -- a retry re-attempts only the
#: atomic step, and never re-writes or re-orders data. After the last attempt the error is
#: raised unchanged: a persistent denial is a real fault (a read-only file, a lost ACL) and
#: must not be swallowed.
_RENAME_ATTEMPTS: int = 6
_RENAME_BACKOFF_SECONDS: float = 0.05


def _replace_with_retry(temp_path: Path, target: Path) -> None:
    """``os.replace(temp_path, target)``, retrying a transient Windows denial. See above."""
    for attempt in range(_RENAME_ATTEMPTS):
        try:
            os.replace(temp_path, target)
            return
        except OSError:
            if attempt == _RENAME_ATTEMPTS - 1:
                raise
            time.sleep(_RENAME_BACKOFF_SECONDS * (2**attempt))


def _fsync_file(path: Path) -> None:
    """Flush ``path``'s data to physical storage. Works on POSIX and Windows.

    Opened ``O_RDWR`` because Windows' ``FlushFileBuffers`` (what ``os.fsync`` calls) needs a
    handle with write access; the open neither reads nor writes any bytes.
    """
    fd = os.open(path, os.O_RDWR)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_dir_best_effort(directory: Path) -> None:
    """Flush ``directory``'s entries so a just-completed rename is durable. Best-effort.

    POSIX: open the directory read-only and ``fsync`` its descriptor -- this is what makes
    the ``os.replace`` survive a power cut. Windows: a directory cannot be opened as a file
    descriptor (``os.open`` raises), and NTFS already journals the rename, so this is a
    documented no-op there rather than a guarantee we cannot keep. Either way the file's own
    data was already fsynced before the rename, which is the part that prevents a valid-named
    but empty/garbage file (REVIEW_2 F6, the 2026-07-25 incident).
    """
    try:
        dir_fd = os.open(directory, os.O_RDONLY)
    except (OSError, ValueError):
        return  # Windows and other platforms without directory fds: honest best-effort skip
    try:
        os.fsync(dir_fd)
    except OSError:
        pass  # some filesystems refuse to fsync a directory; the file fsync already ran
    finally:
        os.close(dir_fd)


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
            os.fsync(handle.fileno())  # data on disk BEFORE the rename (REVIEW_2 F6)
        _replace_with_retry(temp_path, target)
    except BaseException:
        # BaseException on purpose: a KeyboardInterrupt mid-write is the exact scenario this
        # module exists for, and it must not leave the temp file behind either.
        temp_path.unlink(missing_ok=True)
        raise
    _fsync_dir_best_effort(target.parent)  # make the rename itself durable (POSIX; see module)
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
        _fsync_file(temp_path)  # flush the writer's bytes to disk BEFORE the rename (F6)
        _replace_with_retry(temp_path, target)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    _fsync_dir_best_effort(target.parent)  # make the rename itself durable (POSIX; see module)
    return target
