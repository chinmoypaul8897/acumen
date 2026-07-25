"""Launcher for the single-symbol 1-minute backfill -- the operator's documented command.

The implementation lives in the package at ``src/acumen/minute_backfill.py``; this file only
forwards to it. Three entry points reach the same ``main()``:

    acumen-minute-backfill            --symbol TCS --allow-network
    python -m acumen.minute_backfill  --symbol TCS --allow-network
    python scripts/minute_backfill.py --symbol TCS --allow-network

The first two need the project installed (the console script is declared in pyproject.toml);
the third is the un-installed path and must keep working from a bare clone (chunk-0 B2). As in
the daily launcher (REVIEW_2 F12), importing this module runs nothing -- the ``sys.path``
bootstrap lives inside :func:`_load_main` and fires only when the package is not installed.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable


def _load_main() -> Callable[..., int]:
    try:
        from acumen.minute_backfill import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from acumen.minute_backfill import main
    return main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
