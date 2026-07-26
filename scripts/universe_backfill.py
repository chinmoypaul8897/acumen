#!/usr/bin/env python
"""Launcher for the chunk-5B full-universe 1-minute backfill.

The implementation lives in ``src/acumen/universe_backfill.py`` and is also installed as the
``acumen-universe-backfill`` console entry point. This file exists so a bare clone can run the
backfill with no install step (chunk-0 decision B2), exactly like ``scripts/backfill_daily.py``
and ``scripts/minute_backfill.py``.

    python scripts/universe_backfill.py --allow-network
    python scripts/universe_backfill.py --report-only

Nothing executes at import time; the ``sys.path`` insert lives inside ``_load_main`` and fires
only when the package is not installed.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _load_main():
    try:
        from acumen.universe_backfill import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from acumen.universe_backfill import main
    return main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
