"""Launcher for the Q-18 reconciliation -- the rebuilt era vs CONTEXT 4.6's sealed numbers.

Committed HERE, beside the runbook it belongs to, because CLAUDE.md's git rules (REVIEW_7
finding C3) require a session making claims from real store data to commit the generating
script and its output. The implementation lives in the package at
`src/acumen/recovery_reconcile.py`; this file is the launcher, with the same bare-clone
bootstrap the other launchers use (REVIEW_2 F12).

    python docs/recovery/q18_reconcile.py
    python docs/recovery/q18_reconcile.py --out docs/recovery/q18_reconciliation.md

Offline and read-only. It is runbook step 5 -- run it only after steps 1-4 have completed and
step 4 has written its report to `docs/recovery/backfill_minute_report_rebuild.md` (NEVER over
the committed `docs/backfill_minute_report.md`, which is the sealed baseline this compares
against). Exit code 0 means zero unexplained divergences; 1 means the ruling's "defect to
triage"; 2 means an input was missing.

Source files in this repo are ASCII-only on purpose (see src/acumen/config.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_main() -> Callable[..., int]:
    try:
        from acumen.recovery_reconcile import main
    except ModuleNotFoundError:
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from acumen.recovery_reconcile import main
    return main


if __name__ == "__main__":
    raise SystemExit(_load_main()())
