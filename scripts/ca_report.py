"""Launcher for the corporate-action report/pull -- the operator's documented command.

The implementation lives in the package at ``src/acumen/ca_report.py``; this file only forwards
to it, with the same bare-clone bootstrap the other launchers use (REVIEW_2 F12), because the
project is not necessarily installed (chunk-0 decision B2):

    acumen-ca-report            --from 2005-01-01 --to 2005-12-31 --allow-network
    python -m acumen.ca_report  --from 2005-01-01 --to 2005-12-31 --allow-network
    python scripts/ca_report.py --from 2005-01-01 --to 2005-12-31 --allow-network

The first two need the project installed; the third is the un-installed path and is what
`docs/recovery/q18_runbook.md` step 2 uses -- once per YEAR, because the pipeline reads the
day-cache one year at a time and a single multi-year window would write a file nothing
downstream looks for.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable


def _load_main() -> Callable[..., int]:
    try:
        from acumen.ca_report import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from acumen.ca_report import main
    return main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
