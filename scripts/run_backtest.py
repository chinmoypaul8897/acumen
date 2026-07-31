"""Launcher for the chunk-9B full-history backtest -- the operator's documented command.

The implementation lives in the package at ``src/acumen/run_backtest.py``; this file only
forwards to it (the same bare-clone bootstrap the other launchers use -- REVIEW_2 F12):

    acumen-backtest                 [--label chunk9b_full] [--symbols A,B] [--preflight-only]
    python -m acumen.run_backtest   [--label chunk9b_full] [--symbols A,B] [--preflight-only]
    python scripts/run_backtest.py  [--label chunk9b_full] [--symbols A,B] [--preflight-only]

The first two need the project installed (``pip install -e . --no-deps``); the console script
is declared in pyproject.toml. The third is the un-installed path and is the one the operator
uses, so it must keep working from a bare clone (chunk-0 B2).

It runs the PREFLIGHT first, every time, and refuses to walk a single day if any check fails.
It is safe to Ctrl-C: a symbol's shard is written only when that symbol is complete, so
re-running the same command resumes and never duplicates a row. Read-only on both stores;
OFFLINE (the corporate-action day-cache is served from disk at any age).

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable


def _load_main() -> Callable[..., int]:
    """Return the packaged ``main``, adding ``src/`` to the path only if it is not installed."""
    try:
        from acumen.run_backtest import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from acumen.run_backtest import main
    return main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
