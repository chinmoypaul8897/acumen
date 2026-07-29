"""Generator for `docs/evidence/chunk9a_pilot.md` -- the chunk-9A pilot proof.

Committed HERE, beside its own output, because CLAUDE.md's git rules (REVIEW_7 finding C3)
require a session making claims from real store data to commit the generating script and its
output under `docs/evidence/`. A later chunk can re-run this and diff -- and it must come back
byte-identical (REVIEW_8 finding C2).

    python docs/evidence/chunk9a_pilot.py

Read-only: it opens the local parquet stores, the cached instrument master and the
corporate-action day-cache, drives four windows through the chunk-9 runner, walks two real
corporate-action bias pairs by hand, proves the resume, and rewrites the markdown pack. The
implementation lives in the package at `src/acumen/pilot_evidence.py`; this file is the
launcher, with the same bare-clone bootstrap the other launchers use (REVIEW_2 F12).

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_main() -> Callable[..., int]:
    try:
        from acumen.pilot_evidence import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from acumen.pilot_evidence import main
    return main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
