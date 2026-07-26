"""Launcher for the chunk-6 gate evidence pack -- the operator's documented command.

The implementation lives in the package at ``src/acumen/poc_evidence.py``; this file only
forwards to it (the same bare-clone bootstrap the other launchers use -- REVIEW_2 F12):

    acumen-poc-evidence              --calibration TCS:2026-07-14 --chart ICICIBANK:2026-07-17
    python -m acumen.poc_evidence    --calibration TCS:2026-07-14 --chart ICICIBANK:2026-07-17
    python scripts/poc_window_evidence.py --calibration TCS:2026-07-14 --allow-network

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable


def _load_main() -> Callable[..., int]:
    try:
        from acumen.poc_evidence import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from acumen.poc_evidence import main
    return main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
