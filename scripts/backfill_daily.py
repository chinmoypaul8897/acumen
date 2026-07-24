"""Launcher for the daily bhavcopy backfill -- the operator's documented command.

The implementation lives in the package now, at ``src/acumen/backfill_daily.py``, and this
file only forwards to it. Three entry points reach the same ``main()``:

    acumen-backfill                  --from 2000-01-01 --to 2026-07-24 --allow-network
    python -m acumen.backfill_daily  --from 2000-01-01 --to 2026-07-24 --allow-network
    python scripts/backfill_daily.py --from 2000-01-01 --to 2026-07-24 --allow-network

The first two need the project installed (``pip install -e . --no-deps``); the console script
is declared in pyproject.toml. The third is the un-installed path and is what the operator's
running backfill uses, so it must keep working from a bare clone.

REVIEW_2 Finding 12, executed as far as it can honestly go: **importing this module now runs
nothing** -- the ``sys.path`` bootstrap it needs when the package is not installed lives
inside :func:`_load_main`, which only ``__main__`` calls, and it only fires when the import
genuinely fails. The remaining insert is the price of chunk-0 B2 ("a bare clone runs with no
install step"); it disappears the moment the project is installed.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable


def _load_main() -> Callable[..., int]:
    """Return the packaged ``main``, adding ``src/`` to the path only if it is not installed."""
    try:
        from acumen.backfill_daily import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from acumen.backfill_daily import main
    return main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
