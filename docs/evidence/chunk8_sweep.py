"""Generator for `docs/evidence/chunk8_sweep.md` -- the chunk-8 priced sweep.

Committed HERE, beside its own output, because CLAUDE.md's git rules (REVIEW_7 finding C3)
require a session making claims from real store data to commit the generating script and its
output under `docs/evidence/`. A later chunk can re-run this and diff.

    python docs/evidence/chunk8_sweep.py

Read-only and offline: it opens the local parquet stores and the cached instrument master,
prices every stock-day of the chunk-7 sweep window, and rewrites the markdown pack. The
implementation lives in the package at `src/acumen/trade_evidence.py`; this file is the
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
        from acumen.trade_evidence import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from acumen.trade_evidence import main
    return main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
