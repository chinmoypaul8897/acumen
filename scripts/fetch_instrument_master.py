"""Launcher for the instrument-master fetch -- the operator's documented command.

The implementation lives in the package at ``src/acumen/instrument_master.py``; this file only
forwards to it (the same bare-clone bootstrap the other launchers use -- REVIEW_2 F12):

    acumen-instrument-master            --allow-network
    python -m acumen.instrument_master  --allow-network
    python scripts/fetch_instrument_master.py --allow-network

It exists as its own step because the master's FILENAME is cited by every pack that quotes a
tick size, and the chunk-9B preflight checks for it by name -- so it is decided and printed
before the long backfill starts, not as a side effect of it (QUESTIONS.md Q-18, runbook step 3).

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable


def _load_main() -> Callable[..., int]:
    try:
        from acumen.instrument_master import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from acumen.instrument_master import main
    return main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
