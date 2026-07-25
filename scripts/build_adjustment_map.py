"""Launcher for the Q-11 adjustment-map builder -- the operator's documented command.

The implementation lives in the package at ``src/acumen/build_adjustment_map.py``; this file only
forwards to it (the same bare-clone bootstrap the other launchers use -- REVIEW_2 F12):

    acumen-build-adjustment-map            --symbol RELIANCE --allow-network --window ...
    python -m acumen.build_adjustment_map  --symbol RELIANCE --allow-network --window ...
    python scripts/build_adjustment_map.py --symbol RELIANCE --allow-network --window ...

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable


def _load_main() -> Callable[..., int]:
    try:
        from acumen.build_adjustment_map import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from acumen.build_adjustment_map import main
    return main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
